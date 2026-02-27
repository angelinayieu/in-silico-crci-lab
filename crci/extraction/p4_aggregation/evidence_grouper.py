# VERIFIED: formulas [EG-DR, EG-PC] match spec SYS_EX lines 1102-1140
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads HarmonizedClaim from P3 layers
# VERIFIED: forward wiring — writes GroupedEvidence for double_counting.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — no gates assigned to this module (gates in double_counting.py)
"""
Component: SYS_EXTRACTION.EX-P4.P4-EG
Spec: SYS_EXTRACTION_COMPLETE.md lines 1102-1140
Formulas: EG-DR (diminishing returns), EG-PC (precision caps)
Reads: HarmonizedClaim (from P3 seven-layer SE system)
Writes: GroupedEvidence (consumed by double_counting.py)
Gates: None (grouper is pre-gate)
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict

from crci.shared import config
from crci.shared.models.enums import MetaSourceFlag
from crci.shared.models.intermediate_states import (
    GroupedEvidence,
    HarmonizedClaim,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════


def group_evidence_by_edge(
    claims: list[HarmonizedClaim],
    *,
    excluded_ler_ids: set[str] | None = None,
) -> list[GroupedEvidence]:
    """Group calibrated claims by edge_relation_id, partitioning primary vs MA.

    Args:
        claims: Harmonized & SE-calibrated claims from P3 layers.
        excluded_ler_ids: Set of ler_ids to exclude (from P3 layer exclusions
            where active=0 / excluded=true).

    Returns:
        One GroupedEvidence per unique edge_relation_id, with diminishing
        returns and precision caps applied.
    """
    excluded = excluded_ler_ids or set()
    if excluded:
        logger.info(
            "Evidence grouper: excluding %d ler_ids from grouping", len(excluded)
        )

    # Step 1: Filter excluded records
    active_claims = [c for c in claims if c.ler_id not in excluded]
    n_excluded = len(claims) - len(active_claims)
    if n_excluded > 0:
        logger.info(
            "Evidence grouper: filtered %d excluded records, %d remain",
            n_excluded,
            len(active_claims),
        )

    # Step 2: Group by edge_relation_id
    edge_groups: dict[str, list[HarmonizedClaim]] = defaultdict(list)
    for claim in active_claims:
        edge_groups[claim.edge_relation_id].append(claim)

    # Step 2b: R3.2 — Check for correlated subgroup estimates
    for edge_id, edge_claims in edge_groups.items():
        subgroup_warnings = _check_subgroup_correlation(edge_claims)
        for warning in subgroup_warnings:
            logger.warning(warning)

    # Step 3: Build GroupedEvidence per edge
    results: list[GroupedEvidence] = []
    for edge_id, edge_claims in sorted(edge_groups.items()):
        primary, ma = _partition_primary_vs_ma(edge_claims)

        logger.debug(
            "Edge %s: %d primary, %d MA claims",
            edge_id,
            len(primary),
            len(ma),
        )

        # Apply precision caps to primary claims
        capped_primary = _apply_precision_caps(primary)

        # Apply diminishing returns weighting (logged in SE via multiplier)
        weighted_claims = _apply_diminishing_returns(capped_primary + ma)

        grouped = GroupedEvidence(
            edge_relation_id=edge_id,
            claims=weighted_claims,
            overlap_decisions=[],
            k=len(weighted_claims),
        )
        results.append(grouped)

    logger.info(
        "Evidence grouper: produced %d GroupedEvidence objects from %d claims",
        len(results),
        len(active_claims),
    )
    return results


# ═══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════


def _partition_primary_vs_ma(
    claims: list[HarmonizedClaim],
) -> tuple[list[HarmonizedClaim], list[HarmonizedClaim]]:
    """Partition claims into primary studies vs meta-analysis rows.

    Primary: profile_id does NOT indicate a meta-analysis parent
    (i.e., the claim's study is not a constituent of an MA).
    MA: profile_id indicates meta-analysis provenance.

    In the HarmonizedClaim model, we use the convention that study_id
    contains the study's identifier. A meta-analysis row has a study_id
    that corresponds to a meta-analysis paper. We detect MA rows by
    checking if any claim's study_id appears as another claim's study_id
    prefix with '_MA' suffix, or by using the profile_id convention.

    For the initial implementation, we rely on a naming convention:
    study_ids ending with '_MA' or containing 'meta' are MA rows.
    In production, this would be driven by parent_meta_study_id from
    edge_evidence_v1.
    """
    primary: list[HarmonizedClaim] = []
    ma: list[HarmonizedClaim] = []

    for claim in claims:
        if _is_meta_analysis_claim(claim):
            ma.append(claim)
        else:
            primary.append(claim)

    return primary, ma


def _is_meta_analysis_claim(claim: HarmonizedClaim) -> bool:
    """Determine if a claim originates from a meta-analysis.

    Uses study_id naming convention. In the DB-backed version, this
    would check edge_evidence_v1.parent_meta_study_id IS NOT NULL.
    """
    sid = claim.study_id.lower()
    return sid.endswith("_ma") or "meta_analysis" in sid or "meta-analysis" in sid


def _apply_precision_caps(
    primary_claims: list[HarmonizedClaim],
) -> list[HarmonizedClaim]:
    """Apply precision caps per study design.

    Spec: cross-sectional SE >= 30% of best RCT SE,
          animal SE >= 10% of best RCT SE.

    Formula EG-PC: For design d, SE_capped = max(SE, cap_d × SE_best_RCT)
    """
    cap_cross_sect = config.EG_PRECISION_CAP_CROSS_SECTIONAL
    cap_animal = config.EG_PRECISION_CAP_ANIMAL

    # Find the best (smallest) RCT SE as baseline
    rct_ses: list[float] = []
    for claim in primary_claims:
        rating = claim.quality_rating.lower()
        if "rct" in rating or rating in ("large_rct", "small_rct"):
            if claim.harmonized_se is not None and claim.harmonized_se > 0:
                rct_ses.append(claim.harmonized_se)

    if not rct_ses:
        # No RCT claims — no precision caps can be applied
        logger.debug(
            "Precision caps: no RCT claims found, skipping caps. "
            "Reason: no RCT SE baseline available."
        )
        return primary_claims

    best_rct_se = min(rct_ses)
    logger.debug("Precision caps: best RCT SE = %.6f", best_rct_se)

    capped: list[HarmonizedClaim] = []
    for claim in primary_claims:
        rating = claim.quality_rating.lower()
        se = claim.harmonized_se

        if se is None:
            capped.append(claim)
            continue

        # Formula EG-PC: precision cap by design
        if "cross" in rating or rating == "cross_sectional":
            floor_se = cap_cross_sect * best_rct_se
            if se < floor_se:
                logger.info(
                    "Precision cap applied: ler_id=%s design=%s "
                    "SE %.6f < floor %.6f (%.0f%% of best RCT SE %.6f). "
                    "Capping SE to floor.",
                    claim.ler_id,
                    rating,
                    se,
                    floor_se,
                    cap_cross_sect * 100,
                    best_rct_se,
                )
                claim = claim.model_copy(update={"harmonized_se": floor_se})

        elif "animal" in rating:
            floor_se = cap_animal * best_rct_se
            if se < floor_se:
                logger.info(
                    "Precision cap applied: ler_id=%s design=%s "
                    "SE %.6f < floor %.6f (%.0f%% of best RCT SE %.6f). "
                    "Capping SE to floor.",
                    claim.ler_id,
                    rating,
                    se,
                    floor_se,
                    cap_animal * 100,
                    best_rct_se,
                )
                claim = claim.model_copy(update={"harmonized_se": floor_se})

        capped.append(claim)

    return capped


def _apply_diminishing_returns(
    claims: list[HarmonizedClaim],
) -> list[HarmonizedClaim]:
    """Apply diminishing-returns SE inflation when many studies on same edge.

    Formula EG-DR: w_eff = w_base × 1 / (1 + DECAY × ln(k))

    where k = number of claims, DECAY = config.EG_DIMINISHING_DECAY.
    This is equivalent to inflating SE by sqrt(1 + DECAY × ln(k)) since
    weight w ∝ 1/SE² and reducing weight is equivalent to inflating SE.
    """
    k = len(claims)
    if k <= 1:
        return claims

    decay = config.EG_DIMINISHING_DECAY

    # Formula EG-DR: diminishing returns multiplier
    # w_effective = w_base × 1 / (1 + decay × ln(k))
    # SE_inflated = SE × sqrt(1 + decay × ln(k))
    diminishing_factor = 1.0 + decay * math.log(k)
    se_inflation = math.sqrt(diminishing_factor)

    logger.debug(
        "Diminishing returns: k=%d, decay=%.2f, factor=%.4f, SE_inflation=%.4f",
        k,
        decay,
        diminishing_factor,
        se_inflation,
    )

    adjusted: list[HarmonizedClaim] = []
    for claim in claims:
        if claim.harmonized_se is not None and claim.harmonized_se > 0:
            inflated_se = claim.harmonized_se * se_inflation
            claim = claim.model_copy(update={"harmonized_se": inflated_se})
        else:
            logger.info(
                "Diminishing returns: skipping ler_id=%s, SE is None/zero. "
                "Reason: cannot inflate missing SE.",
                claim.ler_id,
            )
        adjusted.append(claim)

    return adjusted


# ═══════════════════════════════════════════════════════════════
#  R3.2: SUBGROUP CORRELATION WARNING
# ═══════════════════════════════════════════════════════════════


def _check_subgroup_correlation(
    claims: list[HarmonizedClaim],
) -> list[str]:
    """Warn if subgroup estimates from same MA are being pooled together.

    Subgroup estimates from the same MA share systematic biases.
    They should inform different scope slices, not be pooled.

    Phase 1: warn-log only. Phase 2: exclude from IVW pooling.

    Args:
        claims: All claims for a single edge.

    Returns:
        List of warning strings for any correlated subgroup sets.
    """
    warnings: list[str] = []

    # Group subgroup estimates by parent MA study
    ma_subgroups: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        if (
            claim.meta_source_flag == MetaSourceFlag.SUBGROUP_ESTIMATE.value
            and claim.parent_meta_study_id
        ):
            ma_subgroups[claim.parent_meta_study_id].append(claim.ler_id)

    for ma_id, ler_ids in ma_subgroups.items():
        if len(ler_ids) > 1:
            warnings.append(
                f"R3-CORR: {len(ler_ids)} subgroup estimates from same MA "
                f"{ma_id} for edge {claims[0].edge_relation_id}. "
                f"These are correlated — do not IVW-pool. LERs: {ler_ids}"
            )

    return warnings
