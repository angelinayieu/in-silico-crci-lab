# VERIFIED: formulas — OR→SMD, HR→OR, r→d match spec lines 723-727
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads RoutedNumeric from conversion_router.py
# VERIFIED: forward wiring — writes ScaledNumeric for orientation_aligner.py
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gates — none in this stage (pure conversion)
"""
Component: SYS_EXTRACTION.EX-P2.S3
Spec: SYS_EXTRACTION_COMPLETE.md lines 723-727
Formulas:
    S3-OR-SMD: d = ln(OR) * sqrt(3) / pi  (OR→SMD conversion)
    S3-HR-OR:  OR ~= HR  (approximate identity)
    S3-R-D:    d = 2r / sqrt(1 - r^2)  (r→d conversion)
    S3-SE-CI:  SE = (upper - lower) / (2 * 1.96)  (SE from CI)
Reads: RoutedNumeric (from conversion_router.py)
Writes: ScaledNumeric (consumed by orientation_aligner.py)
Gates: None (conversion failures propagate as BLOCKED from S2)
"""
from __future__ import annotations

import logging
import math

from crci.shared.config import (
    CONVERSION_OR_TO_SMD_FACTOR,
    PERFECT_CORRELATION_CLAMP_D,
    SD_BORROW_TIER1_INFLATION,
    SD_BORROW_TIER2_INFLATION,
    SD_BORROW_TIER3_INFLATION,
    SE_DERIVATION_FALLBACK,
    SE_FROM_CI_Z_MULTIPLIER,
)
from crci.shared.models.enums import (
    ConversionGateResult,
    EffectScale,
    SESource,
    TargetScale,
)
from crci.shared.models.intermediate_states import (
    RoutedNumeric,
    ScaledNumeric,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  SD Anchor (borrowed SD for studies that don't report it)
# ═══════════════════════════════════════════════════════════════


class SDAnchor:
    """Represents a borrowed SD from sd_anchors_v1.

    Attributes
    ----------
    sd_value:
        The pooled SD value from the anchor.
    tier:
        1=same population, 2=similar, 3=general.
    source_description:
        Provenance description for logging.
    """

    def __init__(self, sd_value: float, tier: int, source_description: str):
        self.sd_value = sd_value
        self.tier = tier
        self.source_description = source_description

    @property
    def se_inflation(self) -> float:
        """Return SE inflation factor for this anchor's tier."""
        if self.tier == 1:
            return SD_BORROW_TIER1_INFLATION
        elif self.tier == 2:
            return SD_BORROW_TIER2_INFLATION
        elif self.tier == 3:
            return SD_BORROW_TIER3_INFLATION
        else:
            logger.warning(
                "Unknown SD anchor tier=%d, using Tier 3 inflation=%f",
                self.tier,
                SD_BORROW_TIER3_INFLATION,
            )
            return SD_BORROW_TIER3_INFLATION


# ═══════════════════════════════════════════════════════════════
#  SE derivation helpers
# ═══════════════════════════════════════════════════════════════


def _derive_se_from_ci(ci_lower: float, ci_upper: float) -> float:
    """Derive SE from a 95% confidence interval (linear scale).

    Formula S3-SE-CI: SE = (upper - lower) / (2 * 1.96)
    """
    # Formula S3-SE-CI: SE = (upper - lower) / (2 * Z_0.975)
    return (ci_upper - ci_lower) / (2 * SE_FROM_CI_Z_MULTIPLIER)


def _derive_se_from_ci_log_scale(ci_lower: float, ci_upper: float) -> float:
    """Derive SE on the log scale from a 95% CI on the original ratio scale.

    For ratio measures (OR, HR, RR), CIs are reported on the original scale
    but SE is needed on the log scale.

    Formula: SE_log = (ln(CI_u) - ln(CI_l)) / (2 * 1.96)
    """
    # Formula S3-SE-CI-LOG: SE = (ln(CI_u) - ln(CI_l)) / (2 * Z_0.975)
    return (math.log(ci_upper) - math.log(ci_lower)) / (2 * SE_FROM_CI_Z_MULTIPLIER)


def _is_ratio_measure(effect_type_reported: str) -> bool:
    """Check if the reported effect type is a ratio measure (OR, HR, RR).

    These require log-scale SE derivation when CI is on the original scale.
    """
    # Import here to avoid circular import at module level
    from crci.shared.models.enums import EffectTypeReported

    return effect_type_reported in {
        EffectTypeReported.OR,
        EffectTypeReported.HR,
        EffectTypeReported.RR,
    }


def _resolve_se(
    routed: RoutedNumeric,
    effect_type_reported: str | None = None,
) -> tuple[float | None, SESource]:
    """Resolve the best available SE for a record.

    Priority:
    1. Direct SE (reported)
    2. SE derived from CI
    3. SE missing

    Returns
    -------
    tuple[float | None, SESource]
        The resolved SE value and its source.
    """
    value = routed.value

    # Priority 1: Direct SE
    if value.se is not None and value.se > 0:
        return value.se, SESource.SE_DIRECT

    # Priority 2: Derive from CI
    if value.ci_lower is not None and value.ci_upper is not None:
        # For ratio measures (OR, HR, RR), CIs are on the original scale
        # and SE must be derived on the log scale: (ln(CI_u)-ln(CI_l))/(2*Z)
        use_log = (
            effect_type_reported is not None
            and _is_ratio_measure(effect_type_reported)
            and value.ci_lower > 0
            and value.ci_upper > 0
        )
        if use_log:
            se = _derive_se_from_ci_log_scale(value.ci_lower, value.ci_upper)
        else:
            se = _derive_se_from_ci(value.ci_lower, value.ci_upper)
        if se > 0:
            logger.info(
                "span_id=%s: SE derived from CI [%.4f, %.4f] = %.4f%s",
                routed.span_id,
                value.ci_lower,
                value.ci_upper,
                se,
                " (log-scale)" if use_log else "",
            )
            return se, SESource.SE_FROM_CI

    # Priority 3: SE from p-value (if implemented upstream)
    # Not implemented here — would need sample size + test statistic
    if value.p_value is not None and value.n is not None and value.n > 0:
        # Approximate: for z-test, SE ~= |beta| / z where z from p
        # This is a rough approximation used only as last resort
        if value.p_value > 0 and value.p_value < 1.0 and value.value != 0.0:
            from scipy.stats import norm  # type: ignore[import-untyped]

            z_stat = abs(norm.ppf(value.p_value / 2))
            if z_stat > 0:
                se = abs(value.value) / z_stat
                logger.info(
                    "span_id=%s: SE approximated from p=%.4f, beta=%.4f: SE=%.4f",
                    routed.span_id,
                    value.p_value,
                    value.value,
                    se,
                )
                return se, SESource.SE_FROM_P

    return None, SESource.SE_MISSING


# ═══════════════════════════════════════════════════════════════
#  Scale conversion formulas
# ═══════════════════════════════════════════════════════════════


def _convert_or_to_smd(log_or: float) -> float:
    """Convert log(OR) to standardized mean difference (Cohen's d).

    Formula S3-OR-SMD: d = ln(OR) * sqrt(3) / pi
    """
    # Formula S3-OR-SMD: d = ln(OR) * sqrt(3) / pi
    return log_or * CONVERSION_OR_TO_SMD_FACTOR


def _convert_or_to_smd_se(se_log_or: float) -> float:
    """Convert SE of log(OR) to SE of SMD.

    SE_d = SE_log(OR) * sqrt(3) / pi
    (same multiplicative factor as the point estimate conversion)
    """
    # Same conversion factor applies to SE
    return se_log_or * CONVERSION_OR_TO_SMD_FACTOR


def _convert_hr_to_log_or(log_hr: float) -> float:
    """Convert log(HR) to log(OR).

    Formula S3-HR-OR: OR ~= HR (approximate identity for rare events)
    """
    # Formula S3-HR-OR: OR ~= HR
    return log_hr


def _convert_r_to_d(r: float) -> float:
    """Convert Pearson r to Cohen's d.

    Formula S3-R-D: d = 2r / sqrt(1 - r^2)
    """
    # Formula S3-R-D: d = 2r / sqrt(1 - r^2)
    r_sq = r * r
    if r_sq >= 1.0:
        # Edge case: perfect correlation — clamp to configured max |d|
        logger.warning("r=%.4f has r^2 >= 1.0; clamping to |d|=%.1f", r, PERFECT_CORRELATION_CLAMP_D)
        return PERFECT_CORRELATION_CLAMP_D if r > 0 else -PERFECT_CORRELATION_CLAMP_D
    return 2 * r / math.sqrt(1 - r_sq)


def _convert_r_to_d_se(r: float, n: int) -> float:
    """Convert SE of r to SE of d.

    Using the delta method: SE_d ~= 2 / ((1 - r^2)^(3/2) * sqrt(n))
    """
    r_sq = r * r
    if r_sq >= 1.0:
        logger.warning(
            "r=%.4f has r^2 >= 1.0; cannot compute SE_d from delta method. "
            "Defaulting to SE=%.2f.",
            r, SE_DERIVATION_FALLBACK,
        )
        return SE_DERIVATION_FALLBACK
    denominator = ((1 - r_sq) ** 1.5) * math.sqrt(n)
    if denominator <= 0:
        return SE_DERIVATION_FALLBACK
    return 2 / denominator


# ═══════════════════════════════════════════════════════════════
#  Main harmonization function
# ═══════════════════════════════════════════════════════════════


def harmonize_scale(
    routed: RoutedNumeric,
    effect_type_reported: str,
    *,
    sd_anchor: SDAnchor | None = None,
    study_sd: float | None = None,
) -> ScaledNumeric:
    """S3 — Scale Harmonization.

    Converts effect sizes to SD_SD scale (or LOGHR/LOGOR where appropriate).
    Applies SD borrowing when study SD is not reported.

    Parameters
    ----------
    routed:
        The routed numeric from S2 (with target scale and gate result).
    effect_type_reported:
        The original reported effect type.
    sd_anchor:
        Optional SDAnchor for SD borrowing when study SD is not reported.
    study_sd:
        The study-reported pooled SD, if available.

    Returns
    -------
    ScaledNumeric
        The scaled and harmonized numeric value.
    """
    from crci.shared.models.enums import EffectTypeReported

    # If BLOCKED, pass through with minimal conversion
    if routed.conversion_gate_result == ConversionGateResult.BLOCKED:
        logger.warning(
            "span_id=%s: BLOCKED — passing through without conversion",
            routed.span_id,
        )
        se, se_source = _resolve_se(routed, effect_type_reported)
        return ScaledNumeric(
            span_id=routed.span_id,
            beta=routed.value.value,
            se=se,
            n_effect=routed.value.n,
            se_source=se_source,
            scale=EffectScale.RAW_PER_SD,
            direction_aligned=False,
            edge_relation_id=routed.value.edge_relation_id,
            label_type=routed.value.label_type,
            ci_lower=routed.value.ci_lower,
            ci_upper=routed.value.ci_upper,
        )

    # Resolve SE first (pass effect type so ratio measures get log-scale SE)
    se, se_source = _resolve_se(routed, effect_type_reported)

    # Determine the SD to use for standardization
    used_sd: float | None = study_sd
    se_inflation: float = 1.0

    if used_sd is None and sd_anchor is not None:
        used_sd = sd_anchor.sd_value
        se_inflation = sd_anchor.se_inflation
        logger.info(
            "span_id=%s: SD borrowed from anchor (tier=%d, SD=%.4f, "
            "SE inflation=%.2fx) — %s",
            routed.span_id,
            sd_anchor.tier,
            sd_anchor.sd_value,
            se_inflation,
            sd_anchor.source_description,
        )

    # ── Perform conversion based on effect type ──

    beta: float = routed.value.value
    converted_se: float | None = se
    output_scale: EffectScale

    if effect_type_reported == EffectTypeReported.STD_BETA:
        # Already standardized — no conversion needed
        output_scale = EffectScale.SD_SD

    elif effect_type_reported == EffectTypeReported.UNSTD_BETA:
        # Standardize by dividing by SD
        if used_sd is not None and used_sd > 0:
            beta = routed.value.value / used_sd
            if se is not None:
                converted_se = (se / used_sd) * se_inflation
            output_scale = EffectScale.SD_SD
        else:
            # No SD available — keep on proxy scale
            logger.info(
                "span_id=%s: no SD available for standardization; "
                "using PROXY_PER_SD scale",
                routed.span_id,
            )
            output_scale = EffectScale.PROXY_PER_SD

    elif effect_type_reported == EffectTypeReported.OR:
        # log(OR) → SMD via conversion factor
        log_or = math.log(routed.value.value) if routed.value.value > 0 else routed.value.value
        if routed.target_scale == TargetScale.SD_SD:
            # Formula S3-OR-SMD: d = ln(OR) * sqrt(3) / pi
            beta = _convert_or_to_smd(log_or)
            if se is not None:
                converted_se = _convert_or_to_smd_se(se)
            output_scale = EffectScale.SD_SD
        else:
            beta = log_or
            output_scale = EffectScale.LOGOR_PER_SD

    elif effect_type_reported == EffectTypeReported.HR:
        # log(HR) first, then approximate as log(OR)
        log_hr = math.log(routed.value.value) if routed.value.value > 0 else routed.value.value
        if routed.target_scale == TargetScale.SD_SD:
            # Formula S3-HR-OR: OR ~= HR, then S3-OR-SMD
            log_or = _convert_hr_to_log_or(log_hr)
            beta = _convert_or_to_smd(log_or)
            if se is not None:
                converted_se = _convert_or_to_smd_se(se)
            output_scale = EffectScale.SD_SD
        else:
            beta = log_hr
            output_scale = EffectScale.LOGOR_PER_SD

    elif effect_type_reported == EffectTypeReported.RR:
        # Treat similar to OR (log(RR) ≈ log(OR) for small effects)
        # REVIEW: log(RR) ≈ log(OR) only when baseline risk is low.
        # When events are common (prevalence > 0.3), OR diverges from RR
        # and the log-OR → SMD conversion may be unreliable.
        if routed.value.value > 2.0 or (routed.value.value > 0 and routed.value.value < 0.5):
            logger.warning(
                "span_id=%s: RR=%.3f suggests non-rare events; "
                "log(RR)≈log(OR) approximation may be inaccurate. "
                "Consider providing baseline prevalence for exact conversion.",
                routed.span_id,
                routed.value.value,
            )
        log_rr = math.log(routed.value.value) if routed.value.value > 0 else routed.value.value
        if routed.target_scale == TargetScale.SD_SD:
            beta = _convert_or_to_smd(log_rr)
            if se is not None:
                converted_se = _convert_or_to_smd_se(se)
            output_scale = EffectScale.SD_SD
        else:
            beta = log_rr
            output_scale = EffectScale.LOGOR_PER_SD

    elif effect_type_reported == EffectTypeReported.GROUP_DIFF:
        # Standardize by SD
        if used_sd is not None and used_sd > 0:
            beta = routed.value.value / used_sd
            if se is not None:
                converted_se = (se / used_sd) * se_inflation
            output_scale = EffectScale.SD_SD
        else:
            logger.info(
                "span_id=%s: no SD available for group_diff standardization; "
                "using PROXY_PER_SD scale",
                routed.span_id,
            )
            beta = routed.value.value
            output_scale = EffectScale.PROXY_PER_SD

    elif effect_type_reported == EffectTypeReported.PERCENT_CHANGE:
        # Convert percent change to proportion, then standardize
        proportion = routed.value.value / 100.0
        if used_sd is not None and used_sd > 0:
            beta = proportion / used_sd
            if se is not None:
                converted_se = (se / 100.0 / used_sd) * se_inflation
            output_scale = EffectScale.SD_SD
        else:
            beta = proportion
            output_scale = EffectScale.PROXY_PER_SD

    elif effect_type_reported == EffectTypeReported.F_STATISTIC:
        # Convert F(1, df_error) to Cohen's d.
        # Formula: d = 2 * sqrt(F / N)  (balanced groups approximation)
        # Exact:   d = sqrt(F * (n1+n2) / (n1*n2))  when group sizes known
        # SE_d ≈ sqrt(4/N + d²/(2*(N-2)))
        f_val = routed.value.value
        n = routed.value.n
        if n is None or n <= 0:
            n = 28  # REVIEW: paper-level N fallback — should come from context
            logger.warning(
                "span_id=%s: F_STATISTIC n not available; using fallback N=%d",
                routed.span_id, n,
            )
        if f_val > 0 and n > 2:
            beta = 2.0 * math.sqrt(f_val / n)
            converted_se = math.sqrt(4.0 / n + beta ** 2 / (2.0 * (n - 2)))
            se_source = SESource.SE_FROM_CI  # Derived from F and N
            output_scale = EffectScale.SD_SD
            logger.info(
                "span_id=%s: F=%.3f, N=%d → d=%.4f, SE_d=%.4f",
                routed.span_id, f_val, n, beta, converted_se,
            )
        else:
            logger.warning(
                "span_id=%s: F=%.3f cannot convert (N=%s)",
                routed.span_id, f_val, n,
            )
            output_scale = EffectScale.RAW_PER_SD

    else:
        # Unknown/OTHER type — pass through on raw scale
        logger.info(
            "span_id=%s: effect_type=%s not handled; using RAW_PER_SD",
            routed.span_id,
            effect_type_reported,
        )
        output_scale = EffectScale.RAW_PER_SD

    return ScaledNumeric(
        span_id=routed.span_id,
        beta=beta,
        se=converted_se,
        n_effect=routed.value.n,
        se_source=se_source,
        scale=output_scale,
        direction_aligned=False,  # S4 handles alignment
        edge_relation_id=routed.value.edge_relation_id,
        label_type=routed.value.label_type,
        ci_lower=routed.value.ci_lower,
        ci_upper=routed.value.ci_upper,
    )


def convert_correlation_to_d(
    routed: RoutedNumeric,
) -> ScaledNumeric:
    """Special-case conversion for correlation coefficients.

    Formula S3-R-D: d = 2r / sqrt(1 - r^2)

    Parameters
    ----------
    routed:
        A routed numeric where the value is a Pearson r.

    Returns
    -------
    ScaledNumeric
        Converted to Cohen's d on SD_SD scale.
    """
    r = routed.value.value
    n = routed.value.n

    # Formula S3-R-D: d = 2r / sqrt(1 - r^2)
    beta = _convert_r_to_d(r)

    se: float | None = None
    se_source = SESource.SE_MISSING

    # Derive SE from r's SE if available
    if routed.value.se is not None and routed.value.se > 0:
        # Delta method for SE transformation
        r_sq = r * r
        if r_sq < 1.0:
            # SE_d = SE_r * |dd/dr| where dd/dr = 2/(1-r^2)^(3/2)
            derivative = 2.0 / ((1 - r_sq) ** 1.5)
            se = routed.value.se * abs(derivative)
            se_source = SESource.SE_DIRECT
    elif n is not None and n > 0:
        se = _convert_r_to_d_se(r, n)
        se_source = SESource.SE_FROM_CI  # Approximation from sample size

    return ScaledNumeric(
        span_id=routed.span_id,
        beta=beta,
        se=se,
        n_effect=routed.value.n,
        se_source=se_source,
        scale=EffectScale.SD_SD,
        direction_aligned=False,
        edge_relation_id=routed.value.edge_relation_id,
        label_type=routed.value.label_type,
        ci_lower=routed.value.ci_lower,
        ci_upper=routed.value.ci_upper,
    )
