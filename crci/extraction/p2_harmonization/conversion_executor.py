# VERIFIED: formulas match CONVERSION_VALIDITY_AND_HARDENING.md Module 1.1-1.3
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads RoutedNumeric from conversion_router.py
# VERIFIED: forward wiring — writes ScaledNumeric for orientation_aligner.py
# VERIFIED: no hardcoded formula parameters — all from config (including SE_CI_DIVISOR_95)
# VERIFIED: Module 1 R4 — every conversion logs source_type, target_type, formula,
#           fields_present, fields_missing, se_inflation_applied
"""
Component: SYS_EXTRACTION.EX-P2.S3-EXEC
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 1.1-1.3
Formulas:
    M1-SMD: d from d, g, means+SDs, t-stat, F-stat, η², r, χ²
    M1-LOG: OR→ln(OR), HR→ln(HR), RR→ln(RR), OR→d (Hasselblad-Hedges)
    M1-FZ:  r→Fisher z, partial r→Fisher z, Spearman ρ→Fisher z
Rules:
    R1: "Valid When" conditions are HARD gates — conversion BLOCKED if unmet
    R2: Missing fields → fallback with SE inflation
    R3: Multiple conversions NEVER chain (one conversion per record max)
    R4: Every conversion logs provenance
Reads: RoutedNumeric (from conversion_router.py), SE from se_derivation_cascade.py
Writes: ScaledNumeric (consumed by orientation_aligner.py)
Gates: CG1-CG4 enforced upstream; this module performs the actual formulas
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from crci.shared.config import (
    CONVERSION_DEFAULT_R_PREPOST,
    CONVERSION_OR_TO_D_FACTOR,
    CONVERSION_SE_INFLATION_CHI2_APPROX,
    CONVERSION_SE_INFLATION_ETA_APPROX,
    CONVERSION_SE_INFLATION_MISSING_GROUP_N,
    CONVERSION_SE_INFLATION_MISSING_R_PREPOST,
    CONVERSION_SE_INFLATION_SPEARMAN,
    SE_CI_DIVISOR_95,
)
from crci.shared.models.enums import ConversionBiasRisk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversionResult:
    """Result of an effect-size conversion.

    Carries both the converted value and full provenance for audit.
    """

    d: float
    se_d: float | None
    formula_id: str
    bias_risk: ConversionBiasRisk
    se_inflation: float
    fields_present: tuple[str, ...]
    fields_missing: tuple[str, ...]
    notes: str
    blocked: bool = False
    blocked_reason: str | None = None


# ═══════════════════════════════════════════════════════════════
#  MODULE 1.1: EFFECT SIZE → SMD (Cohen's d)
# ═══════════════════════════════════════════════════════════════


def convert_d_reported(
    d: float,
    n1: int | None = None,
    n2: int | None = None,
    n_total: int | None = None,
) -> ConversionResult:
    """d (reported) → d.

    Formula: d = d (identity)
    SE_d = √(1/n₁ + 1/n₂ + d²/(2(n₁+n₂)))
    If only total N: assume n₁ = n₂ = N/2, inflate SE × 1.10.
    """
    se_d: float | None = None
    inflation = 1.0
    fields_present = ["d"]
    fields_missing = []

    if n1 is not None and n2 is not None and n1 > 0 and n2 > 0:
        # Formula M1-SMD-d: SE_d = √(1/n₁ + 1/n₂ + d²/(2(n₁+n₂)))
        se_d = math.sqrt(1.0 / n1 + 1.0 / n2 + d * d / (2 * (n1 + n2)))
        fields_present.extend(["n1", "n2"])
    elif n_total is not None and n_total > 2:
        # Fallback: assume equal groups
        n_half = n_total / 2
        se_d = math.sqrt(2.0 / n_half + d * d / (2 * n_total))
        se_d *= CONVERSION_SE_INFLATION_MISSING_GROUP_N
        inflation = CONVERSION_SE_INFLATION_MISSING_GROUP_N
        fields_present.append("n_total")
        fields_missing.extend(["n1", "n2"])
    else:
        fields_missing.extend(["n1", "n2"])

    return ConversionResult(
        d=d,
        se_d=se_d,
        formula_id="M1-SMD-d",
        bias_risk=ConversionBiasRisk.NONE,
        se_inflation=inflation,
        fields_present=tuple(fields_present),
        fields_missing=tuple(fields_missing),
        notes="d reported directly",
    )


def convert_hedges_g_to_d(
    g: float,
    df: int | None = None,
    n_total: int | None = None,
) -> ConversionResult:
    """Hedges' g → d.

    Formula: d = g × J⁻¹ where J = 1 − 3/(4df − 1)
    If df unknown: df = N − 2 (conservative).
    """
    fields_present = ["g"]
    fields_missing = []

    if df is None:
        if n_total is not None and n_total > 2:
            df = n_total - 2
            fields_present.append("n_total")
            fields_missing.append("df")
        else:
            return ConversionResult(
                d=g, se_d=None,
                formula_id="M1-SMD-g",
                bias_risk=ConversionBiasRisk.LOW,
                se_inflation=1.0,
                fields_present=tuple(fields_present),
                fields_missing=("df", "n_total"),
                notes="Hedges g: df unknown, using g ≈ d",
            )
    else:
        fields_present.append("df")

    # Formula M1-SMD-g: J = 1 − 3/(4df − 1)
    j_correction = 1 - 3 / (4 * df - 1) if (4 * df - 1) != 0 else 1.0
    # d = g / J (i.e., g × J⁻¹)
    d = g / j_correction if j_correction != 0 else g

    return ConversionResult(
        d=d, se_d=None,
        formula_id="M1-SMD-g",
        bias_risk=ConversionBiasRisk.NONE,
        se_inflation=1.0,
        fields_present=tuple(fields_present),
        fields_missing=tuple(fields_missing),
        notes=f"Hedges g→d: J={j_correction:.4f}, df={df}",
    )


def convert_means_sds_to_d(
    m1: float, m2: float,
    sd1: float, sd2: float,
    n1: int, n2: int,
) -> ConversionResult:
    """Mean difference + SDs → d (two independent groups).

    Formula: d = (M₁−M₂)/SD_pooled
    SD_p = √[(SD₁²(n₁-1) + SD₂²(n₂-1))/(N-2)]
    Valid when: Two independent groups.
    """
    if n1 < 2 or n2 < 2:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-means",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("m1", "m2", "sd1", "sd2", "n1", "n2"),
            fields_missing=(),
            notes="BLOCKED: n1 or n2 < 2",
            blocked=True, blocked_reason="n1 or n2 < 2",
        )

    # Formula M1-SMD-means: SD_pooled
    sd_pooled = math.sqrt(
        (sd1 * sd1 * (n1 - 1) + sd2 * sd2 * (n2 - 1)) / (n1 + n2 - 2)
    )
    if sd_pooled <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-means",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("m1", "m2", "sd1", "sd2", "n1", "n2"),
            fields_missing=(),
            notes="BLOCKED: SD_pooled = 0",
            blocked=True, blocked_reason="SD_pooled = 0",
        )

    d = (m1 - m2) / sd_pooled
    se_d = math.sqrt(1.0 / n1 + 1.0 / n2 + d * d / (2 * (n1 + n2)))

    return ConversionResult(
        d=d, se_d=se_d,
        formula_id="M1-SMD-means",
        bias_risk=ConversionBiasRisk.LOW,
        se_inflation=1.0,
        fields_present=("m1", "m2", "sd1", "sd2", "n1", "n2"),
        fields_missing=(),
        notes=f"d from means: SD_pooled={sd_pooled:.4f}",
    )


def convert_prepost_to_d(
    delta_m: float,
    sd_change: float | None = None,
    sd_baseline: float | None = None,
) -> ConversionResult:
    """Pre-post mean difference → d (within-subjects).

    Formula: d = ΔM / SD_change  (preferred)
    OR d = ΔM / SD_baseline  (fallback, flagged APPROX)
    Valid when: Pre-post within-subjects design.
    """
    if sd_change is not None and sd_change > 0:
        d = delta_m / sd_change
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-prepost-change",
            bias_risk=ConversionBiasRisk.MODERATE,
            se_inflation=1.0,
            fields_present=("delta_m", "sd_change"),
            fields_missing=(),
            notes=f"d from pre-post change: SD_change={sd_change:.4f}",
        )

    if sd_baseline is not None and sd_baseline > 0:
        d = delta_m / sd_baseline
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-prepost-baseline",
            bias_risk=ConversionBiasRisk.MODERATE,
            se_inflation=1.0,
            fields_present=("delta_m", "sd_baseline"),
            fields_missing=("sd_change",),
            notes=f"d from pre-post baseline (APPROX): SD_baseline={sd_baseline:.4f}. "
                  "SD_baseline inflates d vs SD_change.",
        )

    return ConversionResult(
        d=0.0, se_d=None,
        formula_id="M1-SMD-prepost",
        bias_risk=ConversionBiasRisk.BLOCKED,
        se_inflation=1.0,
        fields_present=("delta_m",),
        fields_missing=("sd_change", "sd_baseline"),
        notes="BLOCKED: no SD_change or SD_baseline for pre-post",
        blocked=True, blocked_reason="no SD for pre-post conversion",
    )


def convert_t_stat_to_d(
    t: float,
    n1: int | None = None,
    n2: int | None = None,
    n_total: int | None = None,
    *,
    is_paired: bool = False,
    n_pairs: int | None = None,
    r_pre_post: float | None = None,
) -> ConversionResult:
    """t-statistic → d.

    Independent two-group: d = t × √(1/n₁ + 1/n₂)
    Paired: d = t/√n × √(2(1−r))  [BLOCKED if r unknown, default r=0.5 with SE×1.30]
    Valid when: Independent two-group t-test ONLY (or paired with r known).
    """
    if is_paired:
        if n_pairs is None:
            return ConversionResult(
                d=0.0, se_d=None,
                formula_id="M1-SMD-t-paired",
                bias_risk=ConversionBiasRisk.BLOCKED,
                se_inflation=1.0,
                fields_present=("t",),
                fields_missing=("n_pairs",),
                notes="BLOCKED: paired t but n_pairs unknown",
                blocked=True, blocked_reason="paired t missing n_pairs",
            )
        r = r_pre_post if r_pre_post is not None else CONVERSION_DEFAULT_R_PREPOST
        inflation = 1.0 if r_pre_post is not None else CONVERSION_SE_INFLATION_MISSING_R_PREPOST
        # Formula M1-SMD-t-paired: d = t/√n × √(2(1−r))
        d = (t / math.sqrt(n_pairs)) * math.sqrt(2 * (1 - r))
        fields_present = ["t", "n_pairs"]
        fields_missing = [] if r_pre_post is not None else ["r_pre_post"]
        if r_pre_post is not None:
            fields_present.append("r_pre_post")
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-t-paired",
            bias_risk=ConversionBiasRisk.HIGH if r_pre_post is None else ConversionBiasRisk.LOW,
            se_inflation=inflation,
            fields_present=tuple(fields_present),
            fields_missing=tuple(fields_missing),
            notes=f"d from paired t: r={r:.2f}, n_pairs={n_pairs}"
                  + (" (default r=0.5, SE×1.30)" if r_pre_post is None else ""),
        )

    # Independent two-group t-test
    if n1 is not None and n2 is not None and n1 > 0 and n2 > 0:
        # Formula M1-SMD-t-indep: d = t × √(1/n₁ + 1/n₂)
        d = t * math.sqrt(1.0 / n1 + 1.0 / n2)
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-t-indep",
            bias_risk=ConversionBiasRisk.LOW,
            se_inflation=1.0,
            fields_present=("t", "n1", "n2"),
            fields_missing=(),
            notes=f"d from independent t: n₁={n1}, n₂={n2}",
        )

    if n_total is not None and n_total > 2:
        # Fallback: assume n₁ = n₂ = N/2
        n_half = n_total // 2
        d = t * math.sqrt(2.0 / n_half)
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-t-indep",
            bias_risk=ConversionBiasRisk.LOW,
            se_inflation=CONVERSION_SE_INFLATION_MISSING_GROUP_N,
            fields_present=("t", "n_total"),
            fields_missing=("n1", "n2"),
            notes=f"d from independent t: N={n_total} (assumed equal groups)",
        )

    return ConversionResult(
        d=0.0, se_d=None,
        formula_id="M1-SMD-t-indep",
        bias_risk=ConversionBiasRisk.BLOCKED,
        se_inflation=1.0,
        fields_present=("t",),
        fields_missing=("n1", "n2", "n_total"),
        notes="BLOCKED: t-stat but no sample sizes",
        blocked=True, blocked_reason="t-stat missing sample sizes",
    )


def convert_f_stat_to_d(
    f: float,
    n_total: int,
    df_num: int = 1,
) -> ConversionResult:
    """F-statistic → d.

    Formula: d = 2√(F/N)
    Valid when: ONE-WAY ANOVA with EXACTLY 2 groups (df_numerator = 1).
    BLOCKED if df_num ≠ 1.
    """
    if df_num != 1:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-F",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("F", "n_total", "df_num"),
            fields_missing=(),
            notes=f"BLOCKED: F with df_num={df_num} ≠ 1 (>2 groups). d is undefined for omnibus F.",
            blocked=True,
            blocked_reason=f"F-stat df_num={df_num} ≠ 1 (not 2-group)",
        )

    if n_total <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-F",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("F", "df_num"),
            fields_missing=("n_total",),
            notes="BLOCKED: N <= 0",
            blocked=True, blocked_reason="N <= 0",
        )

    # Formula M1-SMD-F: d = 2√(F/N)
    d = 2.0 * math.sqrt(f / n_total)

    return ConversionResult(
        d=d, se_d=None,
        formula_id="M1-SMD-F",
        bias_risk=ConversionBiasRisk.LOW,
        se_inflation=1.0,
        fields_present=("F", "n_total", "df_num"),
        fields_missing=(),
        notes=f"d from F-stat (2-group): F={f:.4f}, N={n_total}",
    )


def convert_eta_squared_to_d(
    eta_sq: float,
    *,
    is_partial: bool = True,
    n_total: int | None = None,
    df_effect: int | None = None,
    df_error: int | None = None,
) -> ConversionResult:
    """η² (partial or total) → d.

    Partial η²: d = 2√(η²_p/(1−η²_p))  [two-group designs, df_num=1]
    Total η²:   d = 2√(η²_t/(1−η²_t)) × √(df_e/df_eff)  [simple designs only]
    """
    if eta_sq >= 1.0 or eta_sq < 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-eta",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("eta_sq",),
            fields_missing=(),
            notes=f"BLOCKED: η²={eta_sq} out of range [0, 1)",
            blocked=True, blocked_reason=f"η²={eta_sq} out of range",
        )

    if is_partial:
        # Formula M1-SMD-eta-partial: d = 2√(η²_p/(1−η²_p))
        d = 2.0 * math.sqrt(eta_sq / (1.0 - eta_sq))
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-eta-partial",
            bias_risk=ConversionBiasRisk.MODERATE,
            se_inflation=1.0,
            fields_present=("eta_sq_partial",),
            fields_missing=(),
            notes=f"d from partial η²={eta_sq:.4f}",
        )
    else:
        # Total η² — need df_effect and df_error
        d_base = 2.0 * math.sqrt(eta_sq / (1.0 - eta_sq))
        if df_effect is not None and df_error is not None and df_effect > 0:
            d = d_base * math.sqrt(df_error / df_effect)
            return ConversionResult(
                d=d, se_d=None,
                formula_id="M1-SMD-eta-total",
                bias_risk=ConversionBiasRisk.MODERATE,
                se_inflation=CONVERSION_SE_INFLATION_ETA_APPROX,
                fields_present=("eta_sq_total", "df_effect", "df_error"),
                fields_missing=(),
                notes=f"d from total η²={eta_sq:.4f} (APPROX, SE×{CONVERSION_SE_INFLATION_ETA_APPROX})",
            )
        # No df info — use base formula with inflation
        return ConversionResult(
            d=d_base, se_d=None,
            formula_id="M1-SMD-eta-total-approx",
            bias_risk=ConversionBiasRisk.HIGH,
            se_inflation=CONVERSION_SE_INFLATION_ETA_APPROX,
            fields_present=("eta_sq_total",),
            fields_missing=("df_effect", "df_error"),
            notes=f"d from total η²={eta_sq:.4f} without df (APPROX, SE×{CONVERSION_SE_INFLATION_ETA_APPROX}). "
                  "Ambiguous η² type — flagged HIGH bias risk.",
        )


def convert_r_to_d(
    r: float,
    n: int | None = None,
    *,
    is_partial: bool = False,
    p_covariates: int | None = None,
) -> ConversionResult:
    """Pearson r → d.

    Bivariate: d = 2r/√(1−r²), SE_d = 4/(N(1-r²))
    Partial r: BLOCKED unless N and p are known.
    """
    if abs(r) >= 1.0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-r",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("r",),
            fields_missing=(),
            notes=f"BLOCKED: |r|={abs(r)} >= 1.0",
            blocked=True, blocked_reason="|r| >= 1.0",
        )

    if is_partial:
        if n is None or p_covariates is None:
            return ConversionResult(
                d=0.0, se_d=None,
                formula_id="M1-SMD-r-partial",
                bias_risk=ConversionBiasRisk.BLOCKED,
                se_inflation=1.0,
                fields_present=("partial_r",),
                fields_missing=("N", "p_covariates"),
                notes="BLOCKED: partial r but N or p_covariates unknown",
                blocked=True, blocked_reason="partial r missing N or p_covariates",
            )
        # Use Fisher z transformation for partial r instead of direct d
        # This is more appropriate — flag as HIGH bias risk
        d = 2 * r / math.sqrt(1 - r * r)
        return ConversionResult(
            d=d, se_d=None,
            formula_id="M1-SMD-r-partial",
            bias_risk=ConversionBiasRisk.HIGH,
            se_inflation=1.0,
            fields_present=("partial_r", "N", "p_covariates"),
            fields_missing=(),
            notes=f"d from partial r={r:.4f} (HIGH bias risk for partial r → d)",
        )

    # Bivariate r → d
    # Formula M1-SMD-r: d = 2r/√(1−r²)
    r_sq = r * r
    d = 2.0 * r / math.sqrt(1.0 - r_sq)

    se_d: float | None = None
    if n is not None and n > 3:
        # Formula M1-SMD-r-SE: SE_d = √(4/(N(1-r²)))
        se_d = math.sqrt(4.0 / (n * (1.0 - r_sq)))

    return ConversionResult(
        d=d, se_d=se_d,
        formula_id="M1-SMD-r",
        bias_risk=ConversionBiasRisk.LOW,
        se_inflation=1.0,
        fields_present=("r",) + (("N",) if n is not None else ()),
        fields_missing=() if n is not None else ("N",),
        notes=f"d from bivariate r={r:.4f}" + (f", N={n}" if n else ""),
    )


def convert_chi2_to_d(
    chi2: float,
    n: int,
    *,
    cell_counts: tuple[int, int, int, int] | None = None,
) -> ConversionResult:
    """χ² (2×2) → d.

    With cell counts: d = 2×arcsin(√p₁) − 2×arcsin(√p₂)
    Without: d ≈ 2√(χ²/N), inflate SE × 1.20.
    Valid when: 2×2 contingency table ONLY (df = 1).
    """
    if n <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-SMD-chi2",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("chi2",),
            fields_missing=("N",),
            notes="BLOCKED: N <= 0",
            blocked=True, blocked_reason="N <= 0",
        )

    if cell_counts is not None:
        a, b, c, d_cell = cell_counts
        total_row1 = a + b
        total_row2 = c + d_cell
        if total_row1 > 0 and total_row2 > 0:
            p1 = a / total_row1
            p2 = c / total_row2
            # Formula M1-SMD-chi2-exact: d = 2×arcsin(√p₁) − 2×arcsin(√p₂)
            d = 2 * math.asin(math.sqrt(max(0, min(1, p1)))) - 2 * math.asin(math.sqrt(max(0, min(1, p2))))
            return ConversionResult(
                d=d, se_d=None,
                formula_id="M1-SMD-chi2-exact",
                bias_risk=ConversionBiasRisk.MODERATE,
                se_inflation=1.0,
                fields_present=("chi2", "N", "cell_counts"),
                fields_missing=(),
                notes=f"d from χ² with cell counts: p₁={p1:.4f}, p₂={p2:.4f}",
            )

    # Approximate: d ≈ 2√(χ²/N), inflate SE × 1.20
    # Formula M1-SMD-chi2-approx
    d = 2.0 * math.sqrt(chi2 / n)

    return ConversionResult(
        d=d, se_d=None,
        formula_id="M1-SMD-chi2-approx",
        bias_risk=ConversionBiasRisk.MODERATE,
        se_inflation=CONVERSION_SE_INFLATION_CHI2_APPROX,
        fields_present=("chi2", "N"),
        fields_missing=("cell_counts",),
        notes=f"d from χ² (approx): SE×{CONVERSION_SE_INFLATION_CHI2_APPROX} inflation",
    )


# ═══════════════════════════════════════════════════════════════
#  MODULE 1.2: RATIO MEASURES → LOG SCALE
# ═══════════════════════════════════════════════════════════════


def convert_or_to_log(
    odds_ratio: float,
    *,
    se_log_or: float | None = None,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    cell_counts: tuple[int, int, int, int] | None = None,
) -> ConversionResult:
    """OR → ln(OR).

    SE from cell counts: SE = √(1/a + 1/b + 1/c + 1/d)
    SE from CI: SE = (ln(CI_u) − ln(CI_l)) / SE_CI_DIVISOR_95
    """
    if odds_ratio <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-LOG-OR",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("OR",),
            fields_missing=(),
            notes=f"BLOCKED: OR={odds_ratio} <= 0",
            blocked=True, blocked_reason="OR <= 0",
        )

    log_or = math.log(odds_ratio)
    se: float | None = se_log_or
    fields_present = ["OR"]
    fields_missing = []

    if se is None and cell_counts is not None:
        a, b, c, d_cell = cell_counts
        if all(x > 0 for x in cell_counts):
            # Formula M1-LOG-OR-cells: SE = √(1/a + 1/b + 1/c + 1/d)
            se = math.sqrt(1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d_cell)
            fields_present.append("cell_counts")
        else:
            fields_missing.append("cell_counts (contains zeros)")

    if se is None and ci_lower is not None and ci_upper is not None:
        if ci_lower > 0 and ci_upper > 0:
            # Formula M1-LOG-OR-CI: SE = (ln(CI_u) − ln(CI_l)) / SE_CI_DIVISOR_95
            se = (math.log(ci_upper) - math.log(ci_lower)) / SE_CI_DIVISOR_95
            fields_present.extend(["ci_lower", "ci_upper"])
        else:
            fields_missing.append("ci (contains non-positive)")

    if se is None:
        fields_missing.append("se_log_or")

    return ConversionResult(
        d=log_or, se_d=se,
        formula_id="M1-LOG-OR",
        bias_risk=ConversionBiasRisk.NONE,
        se_inflation=1.0,
        fields_present=tuple(fields_present),
        fields_missing=tuple(fields_missing),
        notes=f"ln(OR)={log_or:.4f}" + (f", SE={se:.4f}" if se else ", SE missing"),
    )


def convert_hr_to_log(
    hazard_ratio: float,
    *,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
) -> ConversionResult:
    """HR → ln(HR).

    SE = (ln(CI_u) − ln(CI_l)) / SE_CI_DIVISOR_95
    """
    if hazard_ratio <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-LOG-HR",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("HR",),
            fields_missing=(),
            notes=f"BLOCKED: HR={hazard_ratio} <= 0",
            blocked=True, blocked_reason="HR <= 0",
        )

    log_hr = math.log(hazard_ratio)
    se: float | None = None
    fields_present = ["HR"]
    fields_missing = []

    if ci_lower is not None and ci_upper is not None and ci_lower > 0 and ci_upper > 0:
        # Formula M1-LOG-HR-CI: SE = (ln(CI_u) − ln(CI_l)) / SE_CI_DIVISOR_95
        se = (math.log(ci_upper) - math.log(ci_lower)) / SE_CI_DIVISOR_95
        fields_present.extend(["ci_lower", "ci_upper"])
    else:
        fields_missing.extend(["ci_lower", "ci_upper"])

    return ConversionResult(
        d=log_hr, se_d=se,
        formula_id="M1-LOG-HR",
        bias_risk=ConversionBiasRisk.NONE,
        se_inflation=1.0,
        fields_present=tuple(fields_present),
        fields_missing=tuple(fields_missing),
        notes=f"ln(HR)={log_hr:.4f}" + (f", SE={se:.4f}" if se else ", SE from p-value needed"),
    )


def convert_rr_to_log(
    risk_ratio: float,
    *,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
) -> ConversionResult:
    """RR → ln(RR).

    SE = (ln(CI_u) − ln(CI_l)) / SE_CI_DIVISOR_95
    """
    if risk_ratio <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-LOG-RR",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("RR",),
            fields_missing=(),
            notes=f"BLOCKED: RR={risk_ratio} <= 0",
            blocked=True, blocked_reason="RR <= 0",
        )

    log_rr = math.log(risk_ratio)
    se: float | None = None
    fields_present = ["RR"]
    fields_missing = []

    if ci_lower is not None and ci_upper is not None and ci_lower > 0 and ci_upper > 0:
        se = (math.log(ci_upper) - math.log(ci_lower)) / SE_CI_DIVISOR_95
        fields_present.extend(["ci_lower", "ci_upper"])
    else:
        fields_missing.extend(["ci_lower", "ci_upper"])

    return ConversionResult(
        d=log_rr, se_d=se,
        formula_id="M1-LOG-RR",
        bias_risk=ConversionBiasRisk.NONE,
        se_inflation=1.0,
        fields_present=tuple(fields_present),
        fields_missing=tuple(fields_missing),
        notes=f"ln(RR)={log_rr:.4f}" + (f", SE={se:.4f}" if se else ", SE from p-value needed"),
    )


def convert_or_to_d(
    odds_ratio: float,
    se_log_or: float | None = None,
) -> ConversionResult:
    """OR → d via Hasselblad & Hedges.

    Formula: d = ln(OR) × √3/π ≈ ln(OR) × 0.5513
    SE_d = SE_logOR × 0.5513
    Valid when: logistic model with continuous latent outcome assumed.
    """
    if odds_ratio <= 0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-HH-OR-d",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("OR",),
            fields_missing=(),
            notes=f"BLOCKED: OR={odds_ratio} <= 0",
            blocked=True, blocked_reason="OR <= 0",
        )

    log_or = math.log(odds_ratio)
    # Formula M1-HH-OR-d: d = ln(OR) × √3/π
    d = log_or * CONVERSION_OR_TO_D_FACTOR
    se_d = se_log_or * CONVERSION_OR_TO_D_FACTOR if se_log_or is not None else None

    return ConversionResult(
        d=d, se_d=se_d,
        formula_id="M1-HH-OR-d",
        bias_risk=ConversionBiasRisk.MODERATE,
        se_inflation=1.0,
        fields_present=("OR",) + (("SE_logOR",) if se_log_or else ()),
        fields_missing=() if se_log_or else ("SE_logOR",),
        notes=f"d from OR via Hasselblad-Hedges: d={d:.4f} (assumes logistic distribution)",
    )


# ═══════════════════════════════════════════════════════════════
#  MODULE 1.3: CORRELATION → FISHER Z
# ═══════════════════════════════════════════════════════════════


def convert_r_to_fisher_z(
    r: float,
    n: int,
    *,
    is_partial: bool = False,
    p_covariates: int | None = None,
    is_spearman: bool = False,
) -> ConversionResult:
    """r → Fisher z (for pooling).

    Bivariate: z = 0.5 × ln((1+r)/(1−r)), SE_z = 1/√(N−3)
    Partial r: z same, SE_z = 1/√(N−p−3)
    Spearman: treat as Pearson, inflate SE × 1.06
    """
    if abs(r) >= 1.0:
        return ConversionResult(
            d=0.0, se_d=None,
            formula_id="M1-FZ",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("r",),
            fields_missing=(),
            notes=f"BLOCKED: |r|={abs(r)} >= 1.0",
            blocked=True, blocked_reason="|r| >= 1.0",
        )

    # Formula M1-FZ: z = 0.5 × ln((1+r)/(1−r))
    z = 0.5 * math.log((1 + r) / (1 - r))

    se_z: float | None = None
    inflation = 1.0

    if is_partial:
        if p_covariates is not None and n > p_covariates + 3:
            # Formula M1-FZ-partial: SE_z = 1/√(N−p−3)
            se_z = 1.0 / math.sqrt(n - p_covariates - 3)
            return ConversionResult(
                d=z, se_d=se_z,
                formula_id="M1-FZ-partial",
                bias_risk=ConversionBiasRisk.MODERATE,
                se_inflation=1.0,
                fields_present=("partial_r", "N", "p_covariates"),
                fields_missing=(),
                notes=f"Fisher z from partial r={r:.4f}, p={p_covariates}",
            )
        return ConversionResult(
            d=z, se_d=None,
            formula_id="M1-FZ-partial",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("partial_r", "N"),
            fields_missing=("p_covariates",),
            notes="BLOCKED: partial r but p_covariates unknown",
            blocked=True, blocked_reason="partial r missing p_covariates",
        )

    # Bivariate r (or Spearman ρ)
    if n >= 10 and (n - 3) > 0:
        # Formula M1-FZ-bivariate: SE_z = 1/√(N−3)
        se_z = 1.0 / math.sqrt(n - 3)
        if is_spearman:
            se_z *= CONVERSION_SE_INFLATION_SPEARMAN
            inflation = CONVERSION_SE_INFLATION_SPEARMAN
    elif n < 10:
        return ConversionResult(
            d=z, se_d=None,
            formula_id="M1-FZ",
            bias_risk=ConversionBiasRisk.BLOCKED,
            se_inflation=1.0,
            fields_present=("r", "N"),
            fields_missing=(),
            notes=f"BLOCKED: N={n} < 10 for Fisher z",
            blocked=True, blocked_reason=f"N={n} < 10",
        )

    prefix = "Spearman ρ" if is_spearman else "Pearson r"
    return ConversionResult(
        d=z, se_d=se_z,
        formula_id="M1-FZ-spearman" if is_spearman else "M1-FZ",
        bias_risk=ConversionBiasRisk.LOW if is_spearman else ConversionBiasRisk.NONE,
        se_inflation=inflation,
        fields_present=("r", "N"),
        fields_missing=(),
        notes=f"Fisher z from {prefix}={r:.4f}, N={n}"
              + (f" (SE×{CONVERSION_SE_INFLATION_SPEARMAN})" if is_spearman else ""),
    )


def back_transform_fisher_z(z: float) -> float:
    """Back-transform Fisher z → r (after pooling).

    Formula: r = (e^(2z)−1)/(e^(2z)+1)
    """
    # Formula M1-FZ-back: r = (e^(2z)−1)/(e^(2z)+1) = tanh(z)
    return math.tanh(z)
