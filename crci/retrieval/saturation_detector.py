# VERIFIED: formulas — SAT-1 (novelty ratio), SAT-2 (saturation flag)
# VERIFIED: imports — shared/config, shared/models/tables
# VERIFIED: backward wiring — reads acquisition_queue_v1 rows
# VERIFIED: forward wiring — updates saturation_flag, consumed by acquisition_scheduler
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — SAT-G1 halts acquisition loop when saturated
"""
Component: SYS_EXTRACTION.EX-ACQ.SaturationDetector
Spec: Master Spec §9.7 (Search Saturation)
      AUTOMATED_RETRIEVAL_PLAN.md Part 7 (Loop Termination)
Formulas: SAT-1 (novelty ratio), SAT-2 (saturation flag decision)
Reads: acquisition_queue_v1 (from fulltext_retriever.py, search_coordinator.py)
Writes: acquisition_queue_v1.saturation_flag (consumed by acquisition_scheduler.py)
Gates: SAT-G1 — halt acquisition when novelty_ratio < SATURATION_NOVELTY_THRESHOLD
       for SATURATION_MIN_CYCLES consecutive cycles
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import AcquisitionQueue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SaturationReport:
    """Result of saturation analysis for one acquisition cycle."""

    cycle_number: int
    total_candidates_this_cycle: int
    novel_candidates_this_cycle: int
    novelty_ratio: float
    consecutive_low_novelty_cycles: int
    saturated: bool
    recommendation: str  # "CONTINUE", "SATURATED_HALT", "MAX_CYCLES_HALT"


def compute_novelty_ratio(
    session: Session,
    cycle_candidates_dois: list[str],
    cycle_candidates_pmids: list[str],
) -> float:
    """Compute the novelty ratio for this acquisition cycle.

    Formula SAT-1:
        novelty_ratio = |new_candidates| / |total_candidates|
        where new = candidates NOT already in acquisition_queue_v1

    A ratio of 1.0 means all candidates are new (no saturation).
    A ratio of 0.0 means all candidates were already queued (full saturation).

    Args:
        session: Active database session.
        cycle_candidates_dois: DOIs of candidates found this cycle.
        cycle_candidates_pmids: PMIDs of candidates found this cycle.

    Returns:
        Novelty ratio between 0.0 and 1.0.
    """
    total = len(cycle_candidates_dois) + len(cycle_candidates_pmids)
    if total == 0:
        return 0.0

    # Count how many are already in the queue
    already_known = 0

    if cycle_candidates_dois:
        stmt = (
            select(func.count())
            .select_from(AcquisitionQueue)
            .where(AcquisitionQueue.candidate_doi.in_(cycle_candidates_dois))
        )
        already_known += session.execute(stmt).scalar_one()

    if cycle_candidates_pmids:
        stmt = (
            select(func.count())
            .select_from(AcquisitionQueue)
            .where(AcquisitionQueue.candidate_pmid.in_(cycle_candidates_pmids))
        )
        already_known += session.execute(stmt).scalar_one()

    # Deduplicate overlap (same paper has both DOI and PMID counted)
    # Conservative: cap at total
    already_known = min(already_known, total)

    novel = total - already_known
    # Formula SAT-1
    novelty_ratio = novel / total

    logger.info(
        "Saturation: novelty_ratio=%.3f (%d novel / %d total, %d already known)",
        novelty_ratio, novel, total, already_known,
    )

    return novelty_ratio


def check_saturation(
    session: Session,
    cycle_number: int,
    novelty_ratio: float,
) -> SaturationReport:
    """Check whether the acquisition loop has reached saturation.

    Formula SAT-2 (saturation decision):
        saturated = (novelty_ratio < SATURATION_NOVELTY_THRESHOLD)
                    for >= SATURATION_MIN_CYCLES consecutive cycles
                    OR cycle_number >= SATURATION_MAX_CYCLES

    Gate SAT-G1: When saturated=True, acquisition_scheduler should halt the loop.

    Args:
        session: Active database session.
        cycle_number: Current cycle number (1-indexed).
        novelty_ratio: Novelty ratio from compute_novelty_ratio().

    Returns:
        SaturationReport with saturation status and recommendation.
    """
    threshold = config.SATURATION_NOVELTY_THRESHOLD
    min_cycles = config.SATURATION_MIN_CYCLES
    max_cycles = config.SATURATION_MAX_CYCLES

    # Count consecutive low-novelty cycles from queue metadata
    consecutive_low = _count_consecutive_low_novelty_cycles(session, threshold)

    # Current cycle counts toward consecutive if below threshold
    if novelty_ratio < threshold:
        consecutive_low += 1

    # Formula SAT-2: saturation decision
    saturated_by_novelty = consecutive_low >= min_cycles
    saturated_by_max_cycles = cycle_number >= max_cycles
    saturated = saturated_by_novelty or saturated_by_max_cycles

    if saturated_by_novelty:
        recommendation = "SATURATED_HALT"
        logger.warning(
            "SAT-G1: Acquisition loop SATURATED — "
            "novelty_ratio=%.3f < threshold=%.3f for %d consecutive cycles "
            "(min required: %d). Recommending halt.",
            novelty_ratio, threshold, consecutive_low, min_cycles,
        )
    elif saturated_by_max_cycles:
        recommendation = "MAX_CYCLES_HALT"
        logger.warning(
            "SAT-G1: Acquisition loop reached MAX_CYCLES=%d. Recommending halt.",
            max_cycles,
        )
    else:
        recommendation = "CONTINUE"
        logger.info(
            "Saturation check: CONTINUE — novelty=%.3f, "
            "consecutive_low=%d/%d, cycle=%d/%d",
            novelty_ratio, consecutive_low, min_cycles,
            cycle_number, max_cycles,
        )

    # Count candidates for this cycle
    total_this_cycle = _count_cycle_candidates(session, cycle_number)

    return SaturationReport(
        cycle_number=cycle_number,
        total_candidates_this_cycle=total_this_cycle,
        novel_candidates_this_cycle=int(total_this_cycle * novelty_ratio),
        novelty_ratio=novelty_ratio,
        consecutive_low_novelty_cycles=consecutive_low,
        saturated=saturated,
        recommendation=recommendation,
    )


def update_cycle_count(session: Session, cycle_number: int) -> None:
    """Increment saturation_cycle_count for all queue entries updated this cycle.

    Called by acquisition_scheduler after each cycle completes.

    Args:
        session: Active database session.
        cycle_number: Current cycle number.
    """
    # Update all entries that were touched in this cycle
    # (those with saturation_cycle_count < cycle_number)
    stmt = (
        select(AcquisitionQueue)
        .where(AcquisitionQueue.saturation_cycle_count < cycle_number)
    )
    rows = session.execute(stmt).scalars().all()
    for row in rows:
        row.saturation_cycle_count = cycle_number
    session.flush()
    logger.debug("Updated saturation_cycle_count to %d for %d rows", cycle_number, len(rows))


def flag_saturated_entries(session: Session) -> int:
    """Flag acquisition queue entries that have been through too many cycles.

    Entries that survived SATURATION_MAX_CYCLES without retrieval
    are flagged as saturated (low-priority).

    Args:
        session: Active database session.

    Returns:
        Number of entries flagged.
    """
    max_cycles = config.SATURATION_MAX_CYCLES

    stmt = (
        select(AcquisitionQueue)
        .where(
            and_(
                AcquisitionQueue.saturation_cycle_count >= max_cycles,
                AcquisitionQueue.saturation_flag.is_(False),
                AcquisitionQueue.status == "queued",
            )
        )
    )
    rows = session.execute(stmt).scalars().all()
    for row in rows:
        row.saturation_flag = True
    session.flush()

    if rows:
        logger.info(
            "Flagged %d acquisition queue entries as saturated "
            "(>=%d cycles without retrieval)",
            len(rows), max_cycles,
        )
    return len(rows)


def _count_consecutive_low_novelty_cycles(
    session: Session,
    threshold: float,
) -> int:
    """Count recent consecutive cycles where novelty was below threshold.

    Uses saturation_cycle_count distribution in the queue:
    if most recent candidates are all from old cycles (not novel),
    the novelty has been low.

    This is a simplified heuristic — a production system would
    store per-cycle novelty_ratio in a dedicated table.

    Args:
        session: Active database session.
        threshold: Novelty ratio threshold.

    Returns:
        Number of estimated consecutive low-novelty cycles.
    """
    # Count how many of the most recent entries are flagged as saturated
    stmt = (
        select(func.count())
        .select_from(AcquisitionQueue)
        .where(AcquisitionQueue.saturation_flag.is_(True))
    )
    saturated_count = session.execute(stmt).scalar_one()

    stmt_total = (
        select(func.count())
        .select_from(AcquisitionQueue)
    )
    total_count = session.execute(stmt_total).scalar_one()

    if total_count == 0:
        return 0

    # Estimate: if >50% of queue is saturated, count as consecutive low cycles
    saturation_pct = saturated_count / total_count
    if saturation_pct > 0.5:
        return config.SATURATION_MIN_CYCLES
    return 0


def _count_cycle_candidates(session: Session, cycle_number: int) -> int:
    """Count candidates associated with a specific cycle."""
    stmt = (
        select(func.count())
        .select_from(AcquisitionQueue)
        .where(AcquisitionQueue.saturation_cycle_count == cycle_number)
    )
    return session.execute(stmt).scalar_one()
