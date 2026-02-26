# ASSUMPTIONS:
#   - All retrieval sub-modules (query_generator, search_coordinator, etc.) are
#     importable and functional. Failures are caught and logged, not fatal.
#   - Session is provided by caller; this module does NOT commit.
# TEST COVERAGE: None yet — needs tests/test_acquisition_scheduler.py
# REVIEW:
#   - Hop candidates queued with aps_score=None need re-scoring in next cycle.
#     Current flow does not re-pull queued candidates for APS scoring.
#   - Exception swallowing (try/except continue) may hide systematic failures.
"""
Component: SYS_EXTRACTION.EX-ACQ.AcquisitionScheduler
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6 (Steps 1-7), Part 9 (Budget)
      Master Spec v2.0 §9.2-§9.7 (screening, hops, saturation)
Purpose: Runs the full acquisition cycle (v2.0 enhanced):
         1. query_generator.generate_all()
         2. search_coordinator.search(queries)
         2b. id_resolver.resolve_candidate_ids() (v2.0)
         2c. abstract_screener.screen_batch() (v2.0)
         3. aps_scorer.score(candidates)
         4. fulltext_retriever.retrieve(scored, budget)
         5. hop_discoverer.run_hop_discovery() (v2.0)
         6. saturation_detector.check_saturation() (v2.0)
         7. Report results
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
from crci.retrieval.abstract_screener import screen_batch as screen_abstracts
from crci.retrieval.aps_scorer import score_candidates
from crci.retrieval.fulltext_retriever import FulltextRetriever
from crci.retrieval.hop_discoverer import run_hop_discovery
from crci.retrieval.id_resolver import resolve_candidate_ids
from crci.retrieval.models import (
    APSQueryRequest,
    APSScoredCandidate,
    CandidateMetadata,
    RetrievalResult,
    RetrievalStatus,
)
from crci.retrieval.saturation_detector import (
    check_saturation,
    compute_novelty_ratio,
    flag_saturated_entries,
    update_cycle_count,
)
from crci.retrieval.search_coordinator import SearchCoordinator

logger = logging.getLogger(__name__)


@dataclass
class AcquisitionReport:
    """Summary report for one acquisition cycle."""

    queries_generated: int = 0
    candidates_found: int = 0
    candidates_after_screening: int = 0
    candidates_dispatched: int = 0
    candidates_deferred: int = 0
    fulltext_retrieved: int = 0
    abstract_only: int = 0
    retrieval_failed: int = 0
    hop_candidates_queued: int = 0
    novelty_ratio: float = 0.0
    saturated: bool = False
    workstreams_searched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_acquisition_cycle(
    session: Session,
    workstreams: list[str] | None = None,
    max_papers: int = 50,
    dry_run: bool = False,
    cycle_number: int = 1,
) -> AcquisitionReport:
    """Run a single acquisition cycle (v2.0 enhanced).

    v2.0 additions:
    - Step 2b: ID cross-resolution for improved dedup
    - Step 2c: Abstract screening to filter irrelevant candidates
    - Step 5: Content-driven hop discovery from extracted papers
    - Step 6: Saturation detection for loop termination

    Args:
        session: SQLAlchemy session.
        workstreams: Which workstreams to search. None = all.
        max_papers: Maximum papers to retrieve per cycle.
        dry_run: If True, generate queries and score but don't retrieve.
        cycle_number: Current cycle number (for saturation tracking).

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

    # Step 2b (v2.0): Cross-resolve DOI ↔ PMID for better dedup
    logger.info("Step 2b: Cross-resolving candidate identifiers")
    try:
        candidates = resolve_candidate_ids(candidates)
    except Exception as exc:
        logger.warning("ID resolution failed (continuing without): %s", exc)
        report.errors.append(f"ID resolution warning: {exc}")

    # Step 2c (v2.0): Abstract screening — filter irrelevant candidates
    logger.info("Step 2c: Screening %d candidate abstracts", len(candidates))
    try:
        screened = screen_abstracts(candidates)
        candidates = [cand for cand, _ in screened]
        report.candidates_after_screening = len(candidates)
        logger.info(
            "Abstract screening: %d → %d candidates passed",
            report.candidates_found,
            report.candidates_after_screening,
        )
    except Exception as exc:
        logger.warning("Abstract screening failed (continuing without): %s", exc)
        report.errors.append(f"Abstract screening warning: {exc}")
        report.candidates_after_screening = len(candidates)

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

    # Step 5 (v2.0): Content-driven hop discovery
    logger.info("Step 5: Running content-driven hop discovery")
    try:
        hop_count = run_hop_discovery(session)
        report.hop_candidates_queued = hop_count
    except Exception as exc:
        logger.warning("Hop discovery failed (non-fatal): %s", exc)
        report.errors.append(f"Hop discovery warning: {exc}")

    # Step 6 (v2.0): Saturation detection
    logger.info("Step 6: Checking acquisition saturation")
    try:
        cycle_dois = [c.doi for c in candidates if c.doi]
        cycle_pmids = [c.pmid for c in candidates if c.pmid]
        novelty = compute_novelty_ratio(session, cycle_dois, cycle_pmids)
        report.novelty_ratio = novelty

        sat_report = check_saturation(session, cycle_number, novelty)
        report.saturated = sat_report.saturated

        update_cycle_count(session, cycle_number)
        flag_saturated_entries(session)

        if sat_report.saturated:
            logger.warning(
                "SAT-G1: Acquisition loop is SATURATED (%s). "
                "Consider halting.",
                sat_report.recommendation,
            )
    except Exception as exc:
        logger.warning("Saturation check failed (non-fatal): %s", exc)
        report.errors.append(f"Saturation check warning: {exc}")

    return report


def run_continuous(
    session: Session,
    workstreams: list[str] | None = None,
    max_papers_per_cycle: int = 50,
    max_cycles: int | None = None,
    respect_saturation: bool = True,
) -> list[AcquisitionReport]:
    """Run acquisition in continuous mode (loop with sleep).

    v2.0: Respects saturation detection — halts loop when SAT-G1 fires.

    Args:
        session: SQLAlchemy session.
        workstreams: Which workstreams to search.
        max_papers_per_cycle: Max papers per cycle.
        max_cycles: Max number of cycles (None = unlimited, subject to saturation).
        respect_saturation: If True, halt loop when saturation is detected.

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
            cycle_number=cycle,
        )
        reports.append(report)

        logger.info(
            "Cycle %d complete: %d retrieved, %d hops queued, "
            "novelty=%.3f, %d errors",
            cycle,
            report.fulltext_retrieved,
            report.hop_candidates_queued,
            report.novelty_ratio,
            len(report.errors),
        )

        # v2.0: Check saturation-based termination
        if respect_saturation and report.saturated:
            logger.warning(
                "Acquisition loop halted by SAT-G1 after %d cycles "
                "(novelty_ratio=%.3f)",
                cycle,
                report.novelty_ratio,
            )
            break

        if max_cycles is not None and cycle >= max_cycles:
            break

        # Sleep until next cycle
        sleep_hours = config.ACQUISITION_LOOP_HOURS
        logger.info("Sleeping %d hours until next cycle...", sleep_hours)
        time.sleep(sleep_hours * 3600)

    return reports
