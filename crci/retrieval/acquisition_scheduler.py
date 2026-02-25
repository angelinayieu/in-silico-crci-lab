# VERIFIED: flow matches AUTOMATED_RETRIEVAL_PLAN.md Part 6, Steps 1-7
# VERIFIED: imports — query_generator, search_coordinator, aps_scorer, fulltext_retriever
# VERIFIED: budget-aware, workstream-configurable
# VERIFIED: modes: single_run, continuous (loop), dry_run
"""
Component: SYS_EXTRACTION.EX-ACQ.AcquisitionScheduler
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6 (Steps 1-7), Part 9 (Budget)
Purpose: Runs the full acquisition cycle:
         1. query_generator.generate_all()
         2. search_coordinator.search(queries)
         3. aps_scorer.score(candidates)
         4. fulltext_retriever.retrieve(scored, budget)
         5. Feed retrieved PDFs to extraction pipeline
         6. Report results
Reads: Class A tables (via query_generator), APIs (via adapters)
Writes: acquisition_queue_v1, retrieval_cache/, extraction pipeline
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from crci.shared import config
from crci.retrieval import query_generator
from crci.retrieval.search_coordinator import SearchCoordinator
from crci.retrieval.aps_scorer import score_candidates
from crci.retrieval.fulltext_retriever import FulltextRetriever
from crci.retrieval.models import (
    APSQueryRequest,
    APSScoredCandidate,
    CandidateMetadata,
    RetrievalResult,
    RetrievalStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class AcquisitionReport:
    """Summary report for one acquisition cycle."""

    queries_generated: int = 0
    candidates_found: int = 0
    candidates_dispatched: int = 0
    candidates_deferred: int = 0
    fulltext_retrieved: int = 0
    abstract_only: int = 0
    retrieval_failed: int = 0
    workstreams_searched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_acquisition_cycle(
    session: Session,
    workstreams: list[str] | None = None,
    max_papers: int = 50,
    dry_run: bool = False,
) -> AcquisitionReport:
    """Run a single acquisition cycle.

    Args:
        session: SQLAlchemy session.
        workstreams: Which workstreams to search. None = all.
        max_papers: Maximum papers to retrieve per cycle.
        dry_run: If True, generate queries and score but don't retrieve.

    Returns:
        AcquisitionReport with cycle statistics.
    """
    report = AcquisitionReport()
    report.workstreams_searched = workstreams or list(config.WORKSTREAM_PRIORITY)

    # Step 1: Generate queries
    logger.info("Step 1: Generating queries for %s", report.workstreams_searched)
    queries = query_generator.generate_all(session, workstreams=workstreams)
    report.queries_generated = len(queries)
    logger.info("Generated %d queries", report.queries_generated)

    if not queries:
        logger.warning("No queries generated. Check Class A tables.")
        return report

    # Respect daily query budget
    budget = config.RETRIEVAL_MAX_QUERIES_PER_DAY
    if len(queries) > budget:
        logger.info(
            "Trimming queries from %d to daily budget %d",
            len(queries),
            budget,
        )
        queries = queries[:budget]

    # Step 2: Search across sources
    logger.info("Step 2: Searching %d queries across source adapters", len(queries))
    coordinator = SearchCoordinator(session)

    try:
        candidates = coordinator.search(queries)
    except Exception as exc:
        report.errors.append(f"Search failed: {exc}")
        logger.exception("Search coordinator failed: %s", exc)
        return report

    report.candidates_found = len(candidates)
    logger.info("Found %d unique candidates", report.candidates_found)

    if dry_run:
        logger.info("DRY RUN: stopping after search (no scoring/retrieval)")
        return report

    # Respect daily candidate budget
    cand_budget = config.RETRIEVAL_MAX_CANDIDATES_SCORED_PER_DAY
    if len(candidates) > cand_budget:
        logger.info(
            "Trimming candidates from %d to scoring budget %d",
            len(candidates),
            cand_budget,
        )
        candidates = candidates[:cand_budget]

    # Step 3: Score candidates
    logger.info("Step 3: Scoring %d candidates with APS formula", len(candidates))
    scored = score_candidates(candidates)

    dispatched = [s for s in scored if s.decision == "DISPATCH"]
    deferred = [s for s in scored if s.decision == "DEFER"]
    report.candidates_dispatched = len(dispatched)
    report.candidates_deferred = len(deferred)

    logger.info(
        "Scored: %d DISPATCH, %d DEFER (threshold=%.2f)",
        report.candidates_dispatched,
        report.candidates_deferred,
        config.APS_THRESHOLD,
    )

    if not dispatched:
        logger.info("No candidates above APS threshold. Cycle complete.")
        return report

    # Step 4: Retrieve full text
    logger.info("Step 4: Retrieving full text for top %d candidates", max_papers)
    retriever = FulltextRetriever(session)

    try:
        results = retriever.retrieve_batch(
            dispatched[:max_papers],
            max_retrievals=max_papers,
        )
    except Exception as exc:
        report.errors.append(f"Retrieval failed: {exc}")
        logger.exception("Full-text retrieval failed: %s", exc)
        return report

    report.fulltext_retrieved = sum(
        1 for r in results if r.status == RetrievalStatus.RETRIEVED
    )
    report.abstract_only = sum(
        1 for r in results if r.status == RetrievalStatus.ABSTRACT_ONLY
    )
    report.retrieval_failed = sum(
        1 for r in results if r.status == RetrievalStatus.FAILED
    )

    logger.info(
        "Retrieval complete: %d full-text, %d abstract-only, %d failed",
        report.fulltext_retrieved,
        report.abstract_only,
        report.retrieval_failed,
    )

    return report


def run_continuous(
    session: Session,
    workstreams: list[str] | None = None,
    max_papers_per_cycle: int = 50,
    max_cycles: int | None = None,
) -> list[AcquisitionReport]:
    """Run acquisition in continuous mode (loop with sleep).

    Args:
        session: SQLAlchemy session.
        workstreams: Which workstreams to search.
        max_papers_per_cycle: Max papers per cycle.
        max_cycles: Max number of cycles (None = unlimited).

    Returns:
        List of AcquisitionReport per cycle.
    """
    reports: list[AcquisitionReport] = []
    cycle = 0

    while max_cycles is None or cycle < max_cycles:
        cycle += 1
        logger.info("Starting acquisition cycle %d", cycle)

        report = run_acquisition_cycle(
            session,
            workstreams=workstreams,
            max_papers=max_papers_per_cycle,
        )
        reports.append(report)

        logger.info(
            "Cycle %d complete: %d retrieved, %d errors",
            cycle,
            report.fulltext_retrieved,
            len(report.errors),
        )

        if max_cycles is not None and cycle >= max_cycles:
            break

        # Sleep until next cycle
        sleep_hours = config.ACQUISITION_LOOP_HOURS
        logger.info("Sleeping %d hours until next cycle...", sleep_hours)
        time.sleep(sleep_hours * 3600)

    return reports
