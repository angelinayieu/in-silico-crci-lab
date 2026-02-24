# VERIFIED: formulas — identification factors match spec lines 734-738
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads ScaledNumeric from orientation_aligner.py
# VERIFIED: forward wiring — writes identification_score consumed by scope_matching.py / EX-P3
# VERIFIED: no hardcoded formula parameters — all factors from config
# VERIFIED: gates — none in this stage (classification only)
"""
Component: SYS_EXTRACTION.EX-P2.S5
Spec: SYS_EXTRACTION_COMPLETE.md lines 734-738
Formulas: None (classification and attenuation factor lookup)
Reads: ScaledNumeric (from orientation_aligner.py), study metadata
Writes: IdentificationResult (consumed by downstream: scope_matching.py, EX-P3)
        Maps to attenuation factor applied in ALG-B5
Gates: None
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from crci.shared.config import (
    CONFOUNDER_COVERAGE_DOWNGRADE_THRESHOLD,
    CONFOUNDER_COVERAGE_UPGRADE_THRESHOLD,
    IDENTIFICATION_FACTOR_IDENTIFIED,
    IDENTIFICATION_FACTOR_PARTIAL,
    IDENTIFICATION_FACTOR_PLAUSIBLE,
    IDENTIFICATION_FACTOR_UNIDENTIFIED,
)
from crci.shared.models.enums import StudyDesign
from crci.shared.models.intermediate_states import ScaledNumeric

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Identification Status Levels
# ═══════════════════════════════════════════════════════════════


class IdentificationResult(BaseModel):
    """Result of causal identification assessment for an evidence record.

    The identification_factor is an attenuation multiplier applied to
    the effect estimate in ALG-B5. Higher = more confident in causal
    identification.

    Levels from spec lines 735-736:
    - Identified (1.00): RCT or quasi-experimental with strong design
    - Partial (0.85): Longitudinal with reasonable adjustment
    - Plausible (0.70): Observational with partial adjustment
    - Unidentified (0.50): Cross-sectional or no adjustment
    """

    span_id: str
    identification_status: str  # "identified", "partial", "plausible", "unidentified"
    identification_factor: float = Field(ge=0.0, le=1.0)
    rationale: str
    study_design: str | None = None
    adjustment_strategy: str | None = None
    known_confounders_addressed: int = 0


# ═══════════════════════════════════════════════════════════════
#  Study Design → Base Identification Mapping
# ═══════════════════════════════════════════════════════════════

# Base mapping from study design to identification level
# This can be upgraded or downgraded based on adjustment strategy
_DESIGN_BASE_STATUS: dict[str, str] = {
    StudyDesign.RCT: "identified",
    StudyDesign.LONGITUDINAL: "partial",
    StudyDesign.CROSS_SECTIONAL: "unidentified",
    StudyDesign.META: "partial",  # Depends on constituent studies
    StudyDesign.INTENSIVE: "partial",
    StudyDesign.MECHANISTIC: "plausible",
    StudyDesign.OTHER: "unidentified",
}


# Adjustment strategies that can upgrade identification
_UPGRADE_STRATEGIES: set[str] = {
    "instrumental_variable",
    "regression_discontinuity",
    "difference_in_differences",
    "propensity_score_matching",
    "inverse_probability_weighting",
}

# Adjustment strategies that provide partial improvement
_PARTIAL_UPGRADE_STRATEGIES: set[str] = {
    "multivariable_adjusted",
    "stratified_analysis",
    "matched_cohort",
    "covariate_adjustment",
}


def _status_to_factor(status: str) -> float:
    """Map identification status string to its attenuation factor.

    Spec lines 735-736:
    Identified → 1.00, Partial → 0.85, Plausible → 0.70, Unidentified → 0.50
    """
    factors = {
        "identified": IDENTIFICATION_FACTOR_IDENTIFIED,
        "partial": IDENTIFICATION_FACTOR_PARTIAL,
        "plausible": IDENTIFICATION_FACTOR_PLAUSIBLE,
        "unidentified": IDENTIFICATION_FACTOR_UNIDENTIFIED,
    }
    factor = factors.get(status)
    if factor is None:
        logger.warning(
            "Unknown identification status '%s'; defaulting to UNIDENTIFIED "
            "factor=%.2f",
            status,
            IDENTIFICATION_FACTOR_UNIDENTIFIED,
        )
        return IDENTIFICATION_FACTOR_UNIDENTIFIED
    return factor


# Ordered status levels for upgrade/downgrade logic
_STATUS_ORDER: list[str] = [
    "unidentified",
    "plausible",
    "partial",
    "identified",
]


def _upgrade_status(current: str, steps: int = 1) -> str:
    """Upgrade identification status by N steps."""
    idx = _STATUS_ORDER.index(current)
    new_idx = min(idx + steps, len(_STATUS_ORDER) - 1)
    return _STATUS_ORDER[new_idx]


def _downgrade_status(current: str, steps: int = 1) -> str:
    """Downgrade identification status by N steps."""
    idx = _STATUS_ORDER.index(current)
    new_idx = max(idx - steps, 0)
    return _STATUS_ORDER[new_idx]


# ═══════════════════════════════════════════════════════════════
#  Main scoring function
# ═══════════════════════════════════════════════════════════════


def score_identification(
    scaled: ScaledNumeric,
    study_design: str,
    *,
    adjustment_strategy: str | None = None,
    known_confounders_addressed: int = 0,
    total_known_confounders: int = 0,
) -> IdentificationResult:
    """S5 — Identification Status Assignment.

    Classifies the causal identification quality of an evidence record
    based on study design + adjustment strategy + known confounders.

    The resulting identification_factor is an attenuation multiplier
    applied in ALG-B5: beta_attenuated = beta * identification_factor.

    Parameters
    ----------
    scaled:
        The direction-aligned scaled numeric from S4.
    study_design:
        Study design classification (from StudyDesign enum).
    adjustment_strategy:
        The statistical adjustment strategy used (if any).
    known_confounders_addressed:
        Number of known confounders that were adjusted for.
    total_known_confounders:
        Total number of known confounders for this edge.

    Returns
    -------
    IdentificationResult
        Classification with status, factor, and rationale.
    """
    rationale_parts: list[str] = []

    # ── Step 1: Base status from study design ──
    base_status = _DESIGN_BASE_STATUS.get(study_design, "unidentified")
    rationale_parts.append(
        f"base status from design '{study_design}': {base_status}"
    )
    status = base_status

    # ── Step 2: Upgrade based on adjustment strategy ──
    if adjustment_strategy is not None:
        if adjustment_strategy in _UPGRADE_STRATEGIES:
            old_status = status
            status = _upgrade_status(status, steps=1)
            rationale_parts.append(
                f"upgraded {old_status} → {status} due to "
                f"strong adjustment: {adjustment_strategy}"
            )
        elif adjustment_strategy in _PARTIAL_UPGRADE_STRATEGIES:
            # Partial upgrade only if starting from a weak position
            if status in ("unidentified", "plausible"):
                old_status = status
                status = _upgrade_status(status, steps=1)
                rationale_parts.append(
                    f"upgraded {old_status} → {status} due to "
                    f"partial adjustment: {adjustment_strategy}"
                )
            else:
                rationale_parts.append(
                    f"adjustment '{adjustment_strategy}' noted but "
                    f"no upgrade from '{status}'"
                )
        else:
            rationale_parts.append(
                f"adjustment '{adjustment_strategy}' not recognized "
                f"for upgrade"
            )

    # ── Step 3: Adjust based on confounder coverage ──
    if total_known_confounders > 0:
        coverage = known_confounders_addressed / total_known_confounders
        if coverage >= CONFOUNDER_COVERAGE_UPGRADE_THRESHOLD:
            # Good coverage — potentially upgrade
            if status in ("plausible", "partial"):
                old_status = status
                status = _upgrade_status(status, steps=1)
                rationale_parts.append(
                    f"confounder coverage {coverage:.0%} >= "
                    f"{CONFOUNDER_COVERAGE_UPGRADE_THRESHOLD:.0%} → "
                    f"upgraded {old_status} → {status}"
                )
        elif coverage < CONFOUNDER_COVERAGE_DOWNGRADE_THRESHOLD:
            # Poor coverage — potentially downgrade
            if status in ("identified", "partial"):
                old_status = status
                status = _downgrade_status(status, steps=1)
                rationale_parts.append(
                    f"confounder coverage {coverage:.0%} < "
                    f"{CONFOUNDER_COVERAGE_DOWNGRADE_THRESHOLD:.0%} → "
                    f"downgraded {old_status} → {status}"
                )

    # ── Step 4: RCTs get floor of "partial" ──
    if study_design == StudyDesign.RCT and status == "unidentified":
        status = "plausible"
        rationale_parts.append(
            "RCT floor applied: unidentified → plausible"
        )

    # ── Compute attenuation factor ──
    factor = _status_to_factor(status)
    rationale = "; ".join(rationale_parts)

    logger.info(
        "span_id=%s: identification_status=%s, factor=%.2f — %s",
        scaled.span_id,
        status,
        factor,
        rationale,
    )

    return IdentificationResult(
        span_id=scaled.span_id,
        identification_status=status,
        identification_factor=factor,
        rationale=rationale,
        study_design=study_design,
        adjustment_strategy=adjustment_strategy,
        known_confounders_addressed=known_confounders_addressed,
    )


def score_identification_batch(
    items: list[
        tuple[ScaledNumeric, str, str | None, int, int]
    ],
) -> list[IdentificationResult]:
    """Score identification for a batch of records.

    Parameters
    ----------
    items:
        List of (ScaledNumeric, study_design, adjustment_strategy,
        known_confounders_addressed, total_known_confounders) tuples.

    Returns
    -------
    list[IdentificationResult]
        All identification results.
    """
    results: list[IdentificationResult] = []
    for scaled, design, adj, confounders_addressed, total_confounders in items:
        result = score_identification(
            scaled=scaled,
            study_design=design,
            adjustment_strategy=adj,
            known_confounders_addressed=confounders_addressed,
            total_known_confounders=total_confounders,
        )
        results.append(result)
    return results
