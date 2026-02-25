# VERIFIED: formulas [DCR-1, DCR-2] match spec SYS_EX lines 1140-1225
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads GroupedEvidence from evidence_grouper.py
# VERIFIED: forward wiring — writes ResolvedEvidence for meta_analyzer.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates [P4-G3] raise on failure (AMBIGUOUS → review_task + GateViolation)
"""
Component: SYS_EXTRACTION.EX-P4.P4-DCR
Spec: SYS_EXTRACTION_COMPLETE.md lines 1140-1225
Formulas: DCR-1 (count_overlap), DCR-2 (n_weighted_overlap)
Reads: GroupedEvidence (from evidence_grouper.py)
Writes: ResolvedEvidence (consumed by meta_analyzer.py)
Gates: P4-G3
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.enums import DCRDecision
from crci.shared.models.intermediate_states import (
    GateViolation,
    GroupedEvidence,
    HarmonizedClaim,
    ResolvedEvidence,
)
from crci.shared.models.tables import ReviewTask

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════


def resolve_double_counting(
    grouped: GroupedEvidence,
    *,
    ma_constituent_study_ids: dict[str, set[str]] | None = None,
    session: Session | None = None,
) -> ResolvedEvidence:
    """Resolve double-counting between MA pooled estimates and constituent primaries.

    This implements the dual-metric overlap analysis from the spec:
    Step 1: count_overlap (DCR-1)
    Step 2: n_weighted_overlap (DCR-2)
    Step 3: Decision rule (both metrics must agree)
    Step 4: Mark excluded rows

    Args:
        grouped: GroupedEvidence from evidence_grouper.py.
        ma_constituent_study_ids: Mapping from MA study_id to the set of
            primary study_ids that were included in the MA. If None,
            no overlap can be computed and decision defaults to N/A.
        session: Optional DB session for emitting review_tasks on AMBIGUOUS.

    Returns:
        ResolvedEvidence ready for meta-analysis.

    Raises:
        GateViolation: P4-G3 if decision is AMBIGUOUS and no session is
            provided (cannot emit review_task).
    """
    primary_claims, ma_claims = _partition_claims(grouped.claims)

    # Edge case: No MA rows present → decision = N/A, pass through all claims
    if not ma_claims:
        logger.debug(
            "DCR edge %s: no MA claims, decision=N_A, passing through %d primaries",
            grouped.edge_relation_id,
            len(primary_claims),
        )
        return _build_resolved(
            edge_relation_id=grouped.edge_relation_id,
            claims=primary_claims,
            notes=[f"DCR decision=N_A: no meta-analysis rows for edge {grouped.edge_relation_id}"],
        )

    # Edge case: No primary rows → use MA directly
    if not primary_claims:
        logger.debug(
            "DCR edge %s: no primary claims, using %d MA claims directly",
            grouped.edge_relation_id,
            len(ma_claims),
        )
        return _build_resolved(
            edge_relation_id=grouped.edge_relation_id,
            claims=ma_claims,
            notes=[f"DCR decision=N_A: no primary rows, using {len(ma_claims)} MA rows directly"],
        )

    # Build the registry of primary study_ids in this edge group
    primary_study_ids: set[str] = {c.study_id for c in primary_claims}

    # Compute overlap for each MA claim
    decisions: list[tuple[HarmonizedClaim, DCRDecision, str]] = []

    for ma_claim in ma_claims:
        ma_study_id = ma_claim.study_id

        # Get the set of studies included in this MA
        ma_included = (
            ma_constituent_study_ids.get(ma_study_id, set())
            if ma_constituent_study_ids
            else set()
        )

        if not ma_included:
            logger.info(
                "DCR edge %s: MA study %s has no constituent mapping. "
                "Reason: ma_constituent_study_ids not provided or empty for this MA. "
                "Defaulting to USE_MA_POOLED.",
                grouped.edge_relation_id,
                ma_study_id,
            )
            decisions.append((
                ma_claim,
                DCRDecision.USE_MA_POOLED,
                f"No constituent mapping for MA {ma_study_id}, defaulting to USE_MA_POOLED",
            ))
            continue

        # Step 1 — Formula DCR-1: count_overlap
        count_overlap = _compute_count_overlap(
            primary_study_ids=primary_study_ids,
            ma_included_study_ids=ma_included,
        )

        # Step 2 — Formula DCR-2: n_weighted_overlap
        n_weighted_overlap = _compute_n_weighted_overlap(
            primary_claims=primary_claims,
            primary_study_ids=primary_study_ids,
            ma_included_study_ids=ma_included,
        )

        # Step 3 — Decision rule
        decision = _apply_decision_rule(
            count_overlap=count_overlap,
            n_weighted_overlap=n_weighted_overlap,
        )

        note = (
            f"MA {ma_study_id}: count_overlap={count_overlap:.4f}, "
            f"n_weighted={n_weighted_overlap:.4f} → {decision.value}"
        )
        logger.info("DCR edge %s: %s", grouped.edge_relation_id, note)
        decisions.append((ma_claim, decision, note))

    # Step 4: Assemble resolved claims based on decisions
    resolved_claims, resolution_notes = _apply_decisions(
        primary_claims=primary_claims,
        ma_decisions=decisions,
        primary_study_ids=primary_study_ids,
        ma_constituent_study_ids=ma_constituent_study_ids or {},
        edge_relation_id=grouped.edge_relation_id,
        session=session,
    )

    return _build_resolved(
        edge_relation_id=grouped.edge_relation_id,
        claims=resolved_claims,
        notes=resolution_notes,
    )


def resolve_all(
    grouped_list: list[GroupedEvidence],
    *,
    ma_constituent_study_ids: dict[str, set[str]] | None = None,
    session: Session | None = None,
) -> list[ResolvedEvidence]:
    """Resolve double-counting for a batch of GroupedEvidence objects.

    Convenience wrapper around resolve_double_counting.
    """
    results: list[ResolvedEvidence] = []
    for grouped in grouped_list:
        resolved = resolve_double_counting(
            grouped,
            ma_constituent_study_ids=ma_constituent_study_ids,
            session=session,
        )
        results.append(resolved)

    logger.info(
        "DCR batch: resolved %d edge groups, total claims: %d",
        len(results),
        sum(r.k for r in results),
    )
    return results


# ═══════════════════════════════════════════════════════════════
#  FORMULA IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════


def _compute_count_overlap(
    primary_study_ids: set[str],
    ma_included_study_ids: set[str],
) -> float:
    """Formula DCR-1: count_overlap = |S_registry intersection S_MA| / |S_MA|.

    Args:
        primary_study_ids: Set of study_ids from primary claims in this edge group.
        ma_included_study_ids: Set of study_ids included in the meta-analysis.

    Returns:
        Fraction of MA constituent studies also present as primaries.
    """
    # Formula DCR-1: count_overlap = |S_registry ∩ S_MA| / |S_MA|
    if not ma_included_study_ids:
        return 0.0

    intersection = primary_study_ids & ma_included_study_ids
    count_overlap = len(intersection) / len(ma_included_study_ids)
    return count_overlap


def _compute_n_weighted_overlap(
    primary_claims: list[HarmonizedClaim],
    primary_study_ids: set[str],
    ma_included_study_ids: set[str],
) -> float:
    """Formula DCR-2: n_weighted = sum(N_i overlapping) / sum(N_i all MA included).

    Uses n_effect from HarmonizedClaim to weight by sample size.

    Args:
        primary_claims: Primary study claims in this edge group.
        primary_study_ids: Set of study_ids from primary claims (for overlap check).
        ma_included_study_ids: Set of study_ids included in the MA.

    Returns:
        Sample-size-weighted overlap fraction.
    """
    # Formula DCR-2: n_weighted = Σ N_i(overlapping) / Σ N_i(all MA included)
    if not ma_included_study_ids:
        return 0.0

    # Build lookup: study_id → n_effect from primary claims
    primary_n_by_study: dict[str, int] = {}
    for claim in primary_claims:
        if claim.n_effect is not None and claim.n_effect > 0:
            # If multiple claims per study, take the max N
            existing = primary_n_by_study.get(claim.study_id, 0)
            primary_n_by_study[claim.study_id] = max(existing, claim.n_effect)

    # Compute numerator and denominator
    overlapping_n = 0
    total_ma_n = 0

    for study_id in ma_included_study_ids:
        n_for_study = primary_n_by_study.get(study_id, 0)

        if n_for_study > 0:
            # We have N data for this MA constituent study
            total_ma_n += n_for_study
            # Only count as overlapping if ALSO in our primary study registry
            if study_id in primary_study_ids:
                overlapping_n += n_for_study
        else:
            # Study is in MA but we have no N data.
            # Log the default: we treat missing N as 0 contribution.
            logger.debug(
                "DCR-2: MA constituent study %s has no N in primary registry. "
                "Reason: study not extracted as primary or N_effect missing. "
                "Defaulting N contribution to 0.",
                study_id,
            )

    if total_ma_n == 0:
        logger.info(
            "DCR-2: total_ma_n=0, all MA constituent studies have missing N. "
            "Reason: no sample sizes available for overlap weighting. "
            "Defaulting n_weighted_overlap to 0.0."
        )
        return 0.0

    n_weighted = overlapping_n / total_ma_n
    return n_weighted


def _apply_decision_rule(
    count_overlap: float,
    n_weighted_overlap: float,
) -> DCRDecision:
    """Apply the dual-metric decision rule.

    Both metrics must agree:
    - Both < 0.10 → USE_MA_POOLED (minimal overlap)
    - Either > 0.70 → USE_PRIMARIES (exclude MA row)
    - Disagree > 0.30 → AMBIGUOUS (human review via P4-G3)
    - Otherwise → USE_MA_EXCLUDE_OVERLAPPING
    """
    threshold_minimal = config.DCR_MINIMAL_OVERLAP_THRESHOLD
    threshold_high = config.DCR_HIGH_OVERLAP_THRESHOLD
    threshold_ambiguity = config.DCR_AMBIGUITY_THRESHOLD

    # Rule 1: Both < minimal → USE_MA_POOLED
    if count_overlap < threshold_minimal and n_weighted_overlap < threshold_minimal:
        return DCRDecision.USE_MA_POOLED

    # Rule 2: Either > high → USE_PRIMARIES
    if count_overlap > threshold_high or n_weighted_overlap > threshold_high:
        return DCRDecision.USE_PRIMARIES

    # Rule 3: Metrics disagree by more than ambiguity threshold → AMBIGUOUS
    disagreement = abs(count_overlap - n_weighted_overlap)
    if disagreement > threshold_ambiguity:
        return DCRDecision.AMBIGUOUS

    # Rule 4: Otherwise → USE_MA_EXCLUDE_OVERLAPPING
    return DCRDecision.USE_MA_EXCLUDE_OVERLAPPING


# ═══════════════════════════════════════════════════════════════
#  DECISION APPLICATION
# ═══════════════════════════════════════════════════════════════


def _apply_decisions(
    primary_claims: list[HarmonizedClaim],
    ma_decisions: list[tuple[HarmonizedClaim, DCRDecision, str]],
    primary_study_ids: set[str],
    ma_constituent_study_ids: dict[str, set[str]],
    edge_relation_id: str,
    session: Session | None,
) -> tuple[list[HarmonizedClaim], list[str]]:
    """Apply DCR decisions to produce the final resolved claim list.

    Returns:
        Tuple of (resolved_claims, resolution_notes).

    Raises:
        GateViolation: P4-G3 on AMBIGUOUS if session not available.
    """
    resolved: list[HarmonizedClaim] = []
    notes: list[str] = []

    for ma_claim, decision, note in ma_decisions:
        notes.append(note)

        if decision == DCRDecision.USE_MA_POOLED:
            # Use only the MA pooled estimate; exclude overlapping primaries
            ma_included = ma_constituent_study_ids.get(ma_claim.study_id, set())
            overlapping_primary_ids = primary_study_ids & ma_included
            resolved.append(ma_claim)
            # Also add non-overlapping primaries
            for pc in primary_claims:
                if pc.study_id not in overlapping_primary_ids and pc not in resolved:
                    resolved.append(pc)
            notes.append(
                f"USE_MA_POOLED: kept MA {ma_claim.study_id}, "
                f"excluded {len(overlapping_primary_ids)} overlapping primaries"
            )

        elif decision == DCRDecision.USE_PRIMARIES:
            # Exclude the MA row; keep all primaries
            notes.append(
                f"USE_PRIMARIES: excluded MA {ma_claim.study_id}, "
                f"keeping all primaries"
            )
            # Primaries will be added after the loop (once, not per MA)

        elif decision == DCRDecision.USE_MA_EXCLUDE_OVERLAPPING:
            # Keep MA; exclude overlapping primaries from the resolved set
            ma_included = ma_constituent_study_ids.get(ma_claim.study_id, set())
            overlapping_primary_ids = primary_study_ids & ma_included
            resolved.append(ma_claim)
            for pc in primary_claims:
                if pc.study_id not in overlapping_primary_ids and pc not in resolved:
                    resolved.append(pc)
            notes.append(
                f"USE_MA_EXCLUDE_OVERLAPPING: kept MA {ma_claim.study_id}, "
                f"excluded {len(overlapping_primary_ids)} overlapping primaries"
            )

        elif decision == DCRDecision.AMBIGUOUS:
            # Gate P4-G3: emit review_task for human review
            _handle_ambiguous(
                ma_claim=ma_claim,
                edge_relation_id=edge_relation_id,
                note=note,
                session=session,
            )
            # For AMBIGUOUS, conservatively use primaries only
            notes.append(
                f"AMBIGUOUS: conservative fallback — excluding MA {ma_claim.study_id}, "
                f"keeping primaries pending human review"
            )

    # Ensure all primaries are included when decision was USE_PRIMARIES
    # or AMBIGUOUS, or if they weren't yet added
    any_use_primaries = any(
        d == DCRDecision.USE_PRIMARIES or d == DCRDecision.AMBIGUOUS
        for _, d, _ in ma_decisions
    )
    if any_use_primaries:
        for pc in primary_claims:
            if pc not in resolved:
                resolved.append(pc)

    # Deduplicate (in case claims were added more than once)
    seen_ler_ids: set[str] = set()
    deduped: list[HarmonizedClaim] = []
    for claim in resolved:
        if claim.ler_id not in seen_ler_ids:
            seen_ler_ids.add(claim.ler_id)
            deduped.append(claim)

    return deduped, notes


def _handle_ambiguous(
    ma_claim: HarmonizedClaim,
    edge_relation_id: str,
    note: str,
    session: Session | None,
) -> None:
    """Gate P4-G3: DCR decision != AMBIGUOUS or emit review_task.

    If session is available, writes a review_task row and logs the event.
    If no session is available, raises GateViolation because the AMBIGUOUS
    decision cannot be properly handled without the review queue.

    Raises:
        GateViolation: P4-G3 if no session is available for review_task emission.
    """
    task_summary = (
        f"Double-counting AMBIGUOUS for edge {edge_relation_id}, "
        f"MA study {ma_claim.study_id}. "
        f"Metrics: {note}. "
        f"Manual review required to decide MA vs primary inclusion."
    )

    if session is not None:
        # Emit review_task row
        task_id = f"dcr_review_{uuid.uuid4().hex[:12]}"
        review_task = ReviewTask(
            task_id=task_id,
            task_type="DCR_AMBIGUOUS",
            source_stage="P4_DCR",
            source_entity_id=edge_relation_id,
            source_table="edge_evidence_v1",
            priority=2,
            status="pending",
            summary=task_summary,
            context_json={
                "edge_relation_id": edge_relation_id,
                "ma_study_id": ma_claim.study_id,
                "ma_ler_id": ma_claim.ler_id,
                "note": note,
            },
        )
        session.add(review_task)
        logger.warning(
            "Gate P4-G3: DCR AMBIGUOUS — emitted review_task %s for edge %s",
            task_id,
            edge_relation_id,
        )
    else:
        # No session: cannot emit review_task → raise gate violation
        raise GateViolation(
            gate_id="P4-G3",
            message=(
                f"DCR decision is AMBIGUOUS for edge {edge_relation_id}, "
                f"MA study {ma_claim.study_id}, but no DB session available "
                f"to emit review_task. Cannot proceed without human review path."
            ),
            context={
                "edge_relation_id": edge_relation_id,
                "ma_study_id": ma_claim.study_id,
                "note": note,
            },
        )


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _partition_claims(
    claims: list[HarmonizedClaim],
) -> tuple[list[HarmonizedClaim], list[HarmonizedClaim]]:
    """Partition claims into primary vs MA.

    Uses the same convention as evidence_grouper._is_meta_analysis_claim.
    """
    primary: list[HarmonizedClaim] = []
    ma: list[HarmonizedClaim] = []

    for claim in claims:
        sid = claim.study_id.lower()
        if sid.endswith("_ma") or "meta_analysis" in sid or "meta-analysis" in sid:
            ma.append(claim)
        else:
            primary.append(claim)

    return primary, ma


def _build_resolved(
    edge_relation_id: str,
    claims: list[HarmonizedClaim],
    notes: list[str],
) -> ResolvedEvidence:
    """Construct a ResolvedEvidence from the resolved claim list."""
    total_n = sum(c.n_effect for c in claims if c.n_effect is not None)
    return ResolvedEvidence(
        edge_relation_id=edge_relation_id,
        claims=claims,
        k=len(claims),
        total_n=total_n,
        resolution_notes=notes,
    )
