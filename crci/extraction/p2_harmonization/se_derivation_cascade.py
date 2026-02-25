# VERIFIED: formulas L1-L6 match CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads TypedNumericValue / RoutedNumeric from upstream
# VERIFIED: forward wiring — writes SEDerivationResult consumed by scale_harmonizer.py
# VERIFIED: no hardcoded formula parameters — all from config
"""
Component: SYS_EXTRACTION.EX-P2.SE-CASCADE
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4 (SE Derivation Cascade)
Formulas:
    L1:  SE = SE_reported (inflation 1.00×)
    L2a: SE = (CI_u − CI_l) / 3.92  [95% CI] (inflation 1.00×)
    L2b: SE = (CI_u − CI_l) / 5.152 [99% CI] (inflation 1.00×)
    L2c: SE = (CI_u − CI_l) / 3.290 [90% CI] (inflation 1.00×)
    L3a: z = Φ⁻¹(1 − p/2); SE = |effect|/z (inflation 1.05×)
    L3b: Use boundary p value (inflation 1.10×)
    L4a: SE_d = √(1/n₁ + 1/n₂ + d²/(2(n₁+n₂))) (inflation 1.15×)
    L4b: Assume n₁ = n₂ = N/2, then L4a formula (inflation 1.20×)
    L5:  SE = SD_borrowed / √(N/2) (inflation tier-dependent: 1.15-1.50×)
    L6:  Direction only — no numeric SE (qualitative)
Reads: TypedNumericValue (from trust boundary), RoutedNumeric (from conversion_router)
Writes: SEDerivationResult (consumed by scale_harmonizer.py / conversion_executor.py)
Gates: None (cascade is informational; L6 records excluded from IVW by downstream)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from crci.shared.config import (
    SE_CASCADE_INFLATION_L1,
    SE_CASCADE_INFLATION_L2A,
    SE_CASCADE_INFLATION_L2B,
    SE_CASCADE_INFLATION_L2C,
    SE_CASCADE_INFLATION_L3A,
    SE_CASCADE_INFLATION_L3B,
    SE_CASCADE_INFLATION_L4A,
    SE_CASCADE_INFLATION_L4B,
    SE_CASCADE_INFLATION_L5_T1,
    SE_CASCADE_INFLATION_L5_T2,
    SE_CASCADE_INFLATION_L5_T3,
    SE_CI_DIVISOR_90,
    SE_CI_DIVISOR_95,
    SE_CI_DIVISOR_99,
)
from crci.shared.models.enums import SEDerivationLevel, SEQualityTag

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SEDerivationResult:
    """Result of the SE derivation cascade.

    Attributes
    ----------
    se : float | None
        Derived standard error. None if L6 (qualitative only).
    level : SEDerivationLevel
        Which cascade level was used.
    quality_tag : SEQualityTag
        Quality classification.
    inflation : float
        Inflation factor applied.
    fields_used : tuple[str, ...]
        Which input fields contributed to the derivation.
    fields_missing : tuple[str, ...]
        Which fields were absent (forced cascade to lower level).
    notes : str
        Human-readable derivation summary.
    """

    se: float | None
    level: SEDerivationLevel
    quality_tag: SEQualityTag
    inflation: float
    fields_used: tuple[str, ...]
    fields_missing: tuple[str, ...]
    notes: str


def derive_se(
    *,
    effect_value: float | None = None,
    se_reported: float | None = None,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    ci_level: float = 0.95,
    p_value: float | None = None,
    p_is_bounded: bool = False,
    n1: int | None = None,
    n2: int | None = None,
    n_total: int | None = None,
    d_value: float | None = None,
    sd_borrowed: float | None = None,
    sd_borrow_tier: int | None = None,
    span_id: str = "unknown",
) -> SEDerivationResult:
    """Run the 6-level SE derivation cascade.

    Tries levels L1 → L2 → L3 → L4 → L5 → L6 in order.
    Uses the FIRST level where all required fields are available.

    Parameters
    ----------
    effect_value : float | None
        Point estimate (β, d, log-OR, etc.).
    se_reported : float | None
        Directly reported SE.
    ci_lower, ci_upper : float | None
        Confidence interval bounds.
    ci_level : float
        Confidence level (0.90, 0.95, or 0.99). Default 0.95.
    p_value : float | None
        P-value (exact or boundary).
    p_is_bounded : bool
        True if p_value is a boundary (e.g., "p < 0.05" → p_value=0.05).
    n1, n2 : int | None
        Per-group sample sizes.
    n_total : int | None
        Total sample size (used if per-group sizes unknown).
    d_value : float | None
        Cohen's d (if different from effect_value, e.g., after conversion).
    sd_borrowed : float | None
        Borrowed SD from sd_anchors_v1.
    sd_borrow_tier : int | None
        Anchor tier (1=same pop, 2=similar, 3=general).
    span_id : str
        For logging provenance.

    Returns
    -------
    SEDerivationResult
        The derived SE with level, inflation, and provenance.
    """
    # Use d_value if provided, otherwise fall back to effect_value
    d_for_formula = d_value if d_value is not None else effect_value

    # ── L1: SE reported directly ──
    if se_reported is not None and se_reported > 0:
        logger.info(
            "span_id=%s: SE cascade L1 — SE reported directly (%.4f)",
            span_id, se_reported,
        )
        return SEDerivationResult(
            se=se_reported * SE_CASCADE_INFLATION_L1,
            level=SEDerivationLevel.L1,
            quality_tag=SEQualityTag.DIRECT,
            inflation=SE_CASCADE_INFLATION_L1,
            fields_used=("se_reported",),
            fields_missing=(),
            notes=f"L1: SE={se_reported:.4f} reported directly",
        )

    # ── L2: SE from confidence interval ──
    if ci_lower is not None and ci_upper is not None and ci_upper > ci_lower:
        if ci_level == 0.95 or abs(ci_level - 0.95) < 0.001:
            # Formula L2a: SE = (CI_u − CI_l) / 3.92
            se = (ci_upper - ci_lower) / SE_CI_DIVISOR_95
            level = SEDerivationLevel.L2A
            inflation = SE_CASCADE_INFLATION_L2A
            tag = f"L2a: SE from 95% CI [{ci_lower:.4f}, {ci_upper:.4f}]"
        elif ci_level == 0.99 or abs(ci_level - 0.99) < 0.001:
            # Formula L2b: SE = (CI_u − CI_l) / 5.152
            se = (ci_upper - ci_lower) / SE_CI_DIVISOR_99
            level = SEDerivationLevel.L2B
            inflation = SE_CASCADE_INFLATION_L2B
            tag = f"L2b: SE from 99% CI [{ci_lower:.4f}, {ci_upper:.4f}]"
        elif ci_level == 0.90 or abs(ci_level - 0.90) < 0.001:
            # Formula L2c: SE = (CI_u − CI_l) / 3.290
            se = (ci_upper - ci_lower) / SE_CI_DIVISOR_90
            level = SEDerivationLevel.L2C
            inflation = SE_CASCADE_INFLATION_L2C
            tag = f"L2c: SE from 90% CI [{ci_lower:.4f}, {ci_upper:.4f}]"
        else:
            # Non-standard CI level — use 95% divisor with L3a-level inflation
            se = (ci_upper - ci_lower) / SE_CI_DIVISOR_95
            level = SEDerivationLevel.L2A
            inflation = SE_CASCADE_INFLATION_L3A
            tag = f"L2a(approx): SE from {ci_level*100:.0f}% CI, using 95% divisor"

        if se > 0:
            logger.info(
                "span_id=%s: SE cascade %s — SE=%.4f", span_id, level, se,
            )
            return SEDerivationResult(
                se=se * inflation,
                level=level,
                quality_tag=SEQualityTag.DERIVED_EXACT,
                inflation=inflation,
                fields_used=("ci_lower", "ci_upper"),
                fields_missing=("se_reported",),
                notes=tag,
            )

    # ── L3: SE from p-value ──
    if (
        p_value is not None
        and p_value > 0
        and p_value < 1.0
        and effect_value is not None
        and abs(effect_value) > 0
    ):
        from scipy.stats import norm  # type: ignore[import-untyped]

        if p_is_bounded:
            # Formula L3b: Use boundary p-value (conservative — widens SE)
            z_stat = abs(norm.ppf(p_value / 2))
            if z_stat > 0:
                se = abs(effect_value) / z_stat
                logger.info(
                    "span_id=%s: SE cascade L3b — SE from bounded p<%s, SE=%.4f",
                    span_id, p_value, se,
                )
                return SEDerivationResult(
                    se=se * SE_CASCADE_INFLATION_L3B,
                    level=SEDerivationLevel.L3B,
                    quality_tag=SEQualityTag.DERIVED_PBOUND,
                    inflation=SE_CASCADE_INFLATION_L3B,
                    fields_used=("p_value", "effect_value"),
                    fields_missing=("se_reported", "ci_lower", "ci_upper"),
                    notes=f"L3b: SE from bounded p<{p_value}, z={z_stat:.4f}",
                )
        else:
            # Formula L3a: z = Φ⁻¹(1 − p/2); SE = |effect| / z
            z_stat = abs(norm.ppf(p_value / 2))
            if z_stat > 0:
                se = abs(effect_value) / z_stat
                logger.info(
                    "span_id=%s: SE cascade L3a — SE from exact p=%.4f, SE=%.4f",
                    span_id, p_value, se,
                )
                return SEDerivationResult(
                    se=se * SE_CASCADE_INFLATION_L3A,
                    level=SEDerivationLevel.L3A,
                    quality_tag=SEQualityTag.DERIVED_PVAL,
                    inflation=SE_CASCADE_INFLATION_L3A,
                    fields_used=("p_value", "effect_value"),
                    fields_missing=("se_reported", "ci_lower", "ci_upper"),
                    notes=f"L3a: SE from exact p={p_value}, z={z_stat:.4f}",
                )

    # ── L4: SE from sample size + d ──
    if d_for_formula is not None:
        if n1 is not None and n2 is not None and n1 > 0 and n2 > 0:
            # Formula L4a: SE_d = √(1/n₁ + 1/n₂ + d²/(2(n₁+n₂)))
            d = d_for_formula
            se = math.sqrt(1.0 / n1 + 1.0 / n2 + d * d / (2 * (n1 + n2)))
            logger.info(
                "span_id=%s: SE cascade L4a — SE from n₁=%d, n₂=%d, d=%.4f: SE=%.4f",
                span_id, n1, n2, d, se,
            )
            return SEDerivationResult(
                se=se * SE_CASCADE_INFLATION_L4A,
                level=SEDerivationLevel.L4A,
                quality_tag=SEQualityTag.ESTIMATED_N,
                inflation=SE_CASCADE_INFLATION_L4A,
                fields_used=("n1", "n2", "d_value"),
                fields_missing=("se_reported", "ci_lower", "ci_upper", "p_value"),
                notes=f"L4a: SE from n₁={n1}, n₂={n2}, d={d:.4f}",
            )

        if n_total is not None and n_total > 2:
            # Formula L4b: Assume n₁ = n₂ = N/2, then L4a formula
            n_half = n_total / 2
            d = d_for_formula
            se = math.sqrt(2.0 / n_half + d * d / (2 * n_total))
            logger.info(
                "span_id=%s: SE cascade L4b — SE from N=%d (assumed equal groups), d=%.4f: SE=%.4f",
                span_id, n_total, d, se,
            )
            return SEDerivationResult(
                se=se * SE_CASCADE_INFLATION_L4B,
                level=SEDerivationLevel.L4B,
                quality_tag=SEQualityTag.ESTIMATED_N_EQUAL_ASSUMED,
                inflation=SE_CASCADE_INFLATION_L4B,
                fields_used=("n_total", "d_value"),
                fields_missing=("se_reported", "ci_lower", "ci_upper", "p_value", "n1", "n2"),
                notes=f"L4b: SE from N={n_total} (n₁=n₂=N/2), d={d:.4f}",
            )

    # ── L5: SD borrowed + N ──
    if sd_borrowed is not None and sd_borrowed > 0:
        n_for_se = n_total if n_total is not None and n_total > 2 else None
        if n_for_se is not None:
            # Formula L5: SE = SD_pooled / √(N/2)
            se = sd_borrowed / math.sqrt(n_for_se / 2)
            tier = sd_borrow_tier if sd_borrow_tier is not None else 3
            if tier == 1:
                inflation = SE_CASCADE_INFLATION_L5_T1
            elif tier == 2:
                inflation = SE_CASCADE_INFLATION_L5_T2
            else:
                inflation = SE_CASCADE_INFLATION_L5_T3
            logger.info(
                "span_id=%s: SE cascade L5 — SE from borrowed SD=%.4f (tier %d), N=%d: SE=%.4f × %.2f",
                span_id, sd_borrowed, tier, n_for_se, se, inflation,
            )
            return SEDerivationResult(
                se=se * inflation,
                level=SEDerivationLevel.L5,
                quality_tag=SEQualityTag.SD_BORROWED,
                inflation=inflation,
                fields_used=("sd_borrowed", "n_total"),
                fields_missing=(
                    "se_reported", "ci_lower", "ci_upper", "p_value", "n1", "n2",
                ),
                notes=f"L5: SE from borrowed SD={sd_borrowed:.4f} (tier {tier}), N={n_for_se}",
            )

    # ── L6: Direction only — no numeric SE ──
    missing = []
    if se_reported is None:
        missing.append("se_reported")
    if ci_lower is None or ci_upper is None:
        missing.append("ci")
    if p_value is None:
        missing.append("p_value")
    if n_total is None and n1 is None:
        missing.append("sample_size")
    if sd_borrowed is None:
        missing.append("sd_borrowed")

    logger.warning(
        "span_id=%s: SE cascade L6 — direction only (qualitative). Missing: %s",
        span_id, ", ".join(missing),
    )
    return SEDerivationResult(
        se=None,
        level=SEDerivationLevel.L6,
        quality_tag=SEQualityTag.QUALITATIVE,
        inflation=0.0,
        fields_used=(),
        fields_missing=tuple(missing),
        notes=f"L6: direction only (qualitative). No SE derivable.",
    )
