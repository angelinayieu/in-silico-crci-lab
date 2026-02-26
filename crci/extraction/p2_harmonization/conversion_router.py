# VERIFIED: logic matches spec lines 719-721 (CG1-CG4 conversion gates)
# VERIFIED: imports — all modules exist (shared.models)
# VERIFIED: backward wiring — reads ValidatedNumeric from plausibility_checker.py
# VERIFIED: forward wiring — writes RoutedNumeric for scale_harmonizer.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates [CG1-CG4] produce ConversionGateResult
"""
Component: SYS_EXTRACTION.EX-P2.S2
Spec: SYS_EXTRACTION_COMPLETE.md lines 719-721
Formulas: None (categorical routing logic)
Reads: ValidatedNumeric (from plausibility_checker.py)
Writes: RoutedNumeric (consumed by scale_harmonizer.py)
Gates: CG1, CG2, CG3, CG4
"""
from __future__ import annotations

import logging
from typing import Any

from crci.shared.models.enums import (
    ConversionGateResult,
    EffectTypeReported,
    TargetScale,
)
from crci.shared.models.intermediate_states import (
    RoutedNumeric,
    ValidatedNumeric,
)

logger = logging.getLogger(__name__)


# ── Valid conversion paths: reported effect type → target scale ──
_VALID_CONVERSIONS: dict[str, set[str]] = {
    EffectTypeReported.STD_BETA: {
        TargetScale.SD_SD,
    },
    EffectTypeReported.UNSTD_BETA: {
        TargetScale.SD_SD,
        TargetScale.PROXY,
        TargetScale.RAW_UNSTD,
    },
    EffectTypeReported.OR: {
        TargetScale.LOGOR,
        TargetScale.SD_SD,
    },
    EffectTypeReported.HR: {
        TargetScale.LOGHR,
        TargetScale.LOGOR,
    },
    EffectTypeReported.RR: {
        TargetScale.LOGOR,
        TargetScale.SD_SD,
    },
    EffectTypeReported.PERCENT_CHANGE: {
        TargetScale.SD_SD,
        TargetScale.PROXY,
        TargetScale.RAW_ORIGINAL,
    },
    EffectTypeReported.GROUP_DIFF: {
        TargetScale.SD_SD,
        TargetScale.PROXY,
    },
    EffectTypeReported.F_STATISTIC: {
        TargetScale.SD_SD,
    },
    EffectTypeReported.OTHER: set(),
}


def _check_cg1_conversion_target_valid(
    effect_type_reported: str,
    target_scale: TargetScale,
) -> bool:
    """CG1: Is the conversion target valid for this reported effect type?

    Returns True if the conversion path exists.
    """
    valid_targets = _VALID_CONVERSIONS.get(effect_type_reported, set())
    return target_scale in valid_targets


def _check_cg2_sufficient_info(
    validated: ValidatedNumeric,
    effect_type_reported: str | None = None,
) -> bool:
    """CG2: Is there sufficient information for conversion?

    Requires either SD (for unstandardized effects) or CI (to derive SE).
    A direct SE is also acceptable.
    F_STATISTIC is special: F value + N is sufficient (SE derived during
    harmonization, not before), and N has a paper-level fallback.
    """
    # F_STATISTIC: F→d conversion derives SE internally; only needs F > 0
    if effect_type_reported == EffectTypeReported.F_STATISTIC:
        return validated.value.value is not None and validated.value.value > 0

    value = validated.value
    has_se = value.se is not None and value.se > 0
    has_ci = (
        value.ci_lower is not None
        and value.ci_upper is not None
    )
    has_p = value.p_value is not None
    has_n = value.n is not None and value.n > 0

    # Sufficient if we have SE, or CI, or (p + N for approximation)
    return has_se or has_ci or (has_p and has_n)


def _check_cg3_scale_compatibility(
    effect_type_reported: str,
    target_scale: TargetScale,
) -> bool:
    """CG3: Is the scale compatible?

    Checks whether the reported effect's inherent scale is compatible
    with the target scale. E.g., converting a correlation to an OR
    requires intermediate steps.
    """
    # Ratio measures (OR, HR, RR) are inherently on log scale
    ratio_types = {
        EffectTypeReported.OR,
        EffectTypeReported.HR,
        EffectTypeReported.RR,
    }
    log_targets = {TargetScale.LOGOR, TargetScale.LOGHR}

    if effect_type_reported in ratio_types:
        # Ratio measures can go to log targets or SD_SD (via conversion)
        return target_scale in log_targets or target_scale == TargetScale.SD_SD

    # Continuous measures (beta, group diff) are inherently compatible
    # with SD_SD and PROXY scales
    continuous_types = {
        EffectTypeReported.STD_BETA,
        EffectTypeReported.UNSTD_BETA,
        EffectTypeReported.GROUP_DIFF,
        EffectTypeReported.PERCENT_CHANGE,
        EffectTypeReported.F_STATISTIC,
    }
    if effect_type_reported in continuous_types:
        return target_scale not in log_targets

    return False


def _check_cg4_orientation_info_available(
    validated: ValidatedNumeric,
    *,
    has_orientation_metadata: bool,
) -> bool:
    """CG4: Is orientation information available?

    To properly align the sign with the DAG convention, we need some
    indication of direction. This can come from explicit metadata or
    from the effect type (e.g., OR > 1 implies direction).
    """
    if has_orientation_metadata:
        return True

    # Ratio measures have an implicit orientation (> 1 or < 1)
    # So we can infer direction even without explicit metadata
    value = validated.value
    if value.value != 0.0:
        return True

    return False


def _determine_target_scale(
    effect_type_reported: str,
) -> TargetScale:
    """Determine the default target scale for a given effect type."""
    if effect_type_reported == EffectTypeReported.STD_BETA:
        return TargetScale.SD_SD
    elif effect_type_reported == EffectTypeReported.UNSTD_BETA:
        return TargetScale.SD_SD
    elif effect_type_reported == EffectTypeReported.OR:
        return TargetScale.LOGOR
    elif effect_type_reported == EffectTypeReported.HR:
        return TargetScale.LOGHR
    elif effect_type_reported == EffectTypeReported.RR:
        return TargetScale.LOGOR
    elif effect_type_reported == EffectTypeReported.PERCENT_CHANGE:
        return TargetScale.SD_SD
    elif effect_type_reported == EffectTypeReported.GROUP_DIFF:
        return TargetScale.SD_SD
    elif effect_type_reported == EffectTypeReported.F_STATISTIC:
        return TargetScale.SD_SD
    else:
        return TargetScale.RAW_ORIGINAL


def route_conversion(
    validated: ValidatedNumeric,
    effect_type_reported: str,
    *,
    has_orientation_metadata: bool = True,
    target_scale_override: TargetScale | None = None,
) -> RoutedNumeric:
    """S2 — Conversion Appropriateness Router (CG1-CG4).

    Runs 4 gate checks to determine whether a scale conversion is
    valid for this evidence record. Result determines how the record
    proceeds through the pipeline:

    - PROCEED: full conversion allowed
    - SIGN_ONLY: only the direction (sign) is usable
    - MAGNITUDE_ONLY: only the magnitude is usable (sign stripped)
    - BLOCKED: record cannot be used in quantitative pipeline

    Parameters
    ----------
    validated:
        The plausibility-validated numeric value from S1.
    effect_type_reported:
        The original reported effect type (from EffectTypeReported).
    has_orientation_metadata:
        Whether orientation metadata is available for this record.
    target_scale_override:
        Override the default target scale selection.

    Returns
    -------
    RoutedNumeric
        The routing decision with target scale and gate result.
    """
    target_scale = target_scale_override or _determine_target_scale(
        effect_type_reported
    )
    blocked_reasons: list[str] = []

    # ── CG1: Conversion target valid ──
    cg1_pass = _check_cg1_conversion_target_valid(
        effect_type_reported, target_scale
    )
    if not cg1_pass:
        blocked_reasons.append(
            f"CG1: no valid conversion path from "
            f"{effect_type_reported} to {target_scale}"
        )

    # ── CG2: Sufficient information ──
    cg2_pass = _check_cg2_sufficient_info(validated, effect_type_reported)
    if not cg2_pass:
        blocked_reasons.append(
            "CG2: insufficient information for conversion "
            "(need SE, CI, or p+N)"
        )

    # ── CG3: Scale compatibility ──
    cg3_pass = _check_cg3_scale_compatibility(
        effect_type_reported, target_scale
    )
    if not cg3_pass:
        blocked_reasons.append(
            f"CG3: scale incompatibility between "
            f"{effect_type_reported} and {target_scale}"
        )

    # ── CG4: Orientation info available ──
    cg4_pass = _check_cg4_orientation_info_available(
        validated, has_orientation_metadata=has_orientation_metadata
    )

    # ── Decision matrix ──
    if not cg1_pass or (not cg2_pass and not cg3_pass):
        # No conversion path or both info and scale fail → BLOCKED
        gate_result = ConversionGateResult.BLOCKED
        reason = "; ".join(blocked_reasons) or "conversion blocked"
        logger.warning(
            "span_id=%s: BLOCKED — %s", validated.span_id, reason
        )
    elif not cg2_pass:
        # Insufficient info but scale is compatible → SIGN_ONLY
        gate_result = ConversionGateResult.SIGN_ONLY
        reason = "; ".join(blocked_reasons) or "sign only"
        logger.info(
            "span_id=%s: SIGN_ONLY — %s", validated.span_id, reason
        )
    elif not cg4_pass:
        # No orientation info → MAGNITUDE_ONLY
        gate_result = ConversionGateResult.MAGNITUDE_ONLY
        reason = "CG4: no orientation metadata; magnitude only"
        logger.info(
            "span_id=%s: MAGNITUDE_ONLY — %s", validated.span_id, reason
        )
    else:
        # All checks pass → PROCEED
        gate_result = ConversionGateResult.PROCEED
        reason = None

    return RoutedNumeric(
        span_id=validated.span_id,
        value=validated.value,
        target_scale=target_scale,
        conversion_gate_result=gate_result,
        blocked_reason=reason,
    )


def route_conversion_batch(
    items: list[tuple[ValidatedNumeric, str, bool]],
) -> list[RoutedNumeric]:
    """Route a batch of validated numerics through CG1-CG4.

    Parameters
    ----------
    items:
        List of (ValidatedNumeric, effect_type_reported,
        has_orientation_metadata) tuples.

    Returns
    -------
    list[RoutedNumeric]
        All routing decisions (including BLOCKED — caller decides
        whether to filter).
    """
    results: list[RoutedNumeric] = []
    for validated, effect_type, has_orient in items:
        routed = route_conversion(
            validated=validated,
            effect_type_reported=effect_type,
            has_orientation_metadata=has_orient,
        )
        results.append(routed)
    return results
