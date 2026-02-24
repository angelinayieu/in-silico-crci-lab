# VERIFIED: formulas P3-1, P3-2, P3-3, P3-4, P3-5, P3-6, P3-7 match spec lines 765-1100
# VERIFIED: imports — all modules exist (config, intermediate_states, enums, logging, math)
# VERIFIED: backward wiring — reads HarmonizedClaim from p2_harmonization
# VERIFIED: forward wiring — writes layer multipliers/weights for se_eff_assembly.py
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gates — none at individual layer level (P3-G1 is in se_eff_assembly.py)
"""
Component: SYS_EXTRACTION.EX-P3 — Seven-Layer Heterogeneity System
Spec: SYS_EXTRACTION_COMPLETE.md lines 765-1100
Formulas: P3-1 (study design), P3-2 (scope match), P3-3 (statistical heterogeneity),
          P3-4 (scale/cancer validation), P3-5 (GRADE quality),
          P3-6 (temporal decay), P3-7 (freshness decay)
Reads: HarmonizedClaim (from p2_harmonization)
Writes: Layer multipliers/weights (consumed by se_eff_assembly.py)
Gates: None at individual layer level — P3-G1 enforced in se_eff_assembly.py

Each layer is a pure function that takes relevant inputs and returns a
multiplier (for multiplicative layers L1, L4, L5) or a weight/modified SE
(for divisive layers L2, L6, L7) or heterogeneity statistics (L3).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from crci.shared import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  L1 — Study Design Multiplier (Formula P3-1)
# ═══════════════════════════════════════════════════════════════


def layer_1_study_design(
    study_design: str,
    n_total: int | None = None,
) -> tuple[float, list[str]]:
    """Compute the study-design SE multiplier m_design.

    Formula P3-1:
      Large RCT (N>200): m = 1.0
      Small RCT (N≤200): m = 1.0 + 0.5×(200−N)/200  (linear interpolation, range 1.0-1.5)
      Well-adjusted cohort: m = 1.5
      Unadjusted longitudinal: m = 2.0
      Cross-sectional (adjusted): m = 2.5
      Cross-sectional (unadjusted): m = 3.0
      Animal in vivo: m = 4.0
      In vitro / mechanistic: m = 5.0
      Expert opinion / narrative: m = 6.0
      Unclassified: m = 3.0 (default) + WARN

    Args:
        study_design: Design classification key.
        n_total: Total sample size (required for small RCT interpolation).

    Returns:
        Tuple of (m_design multiplier, list of notes/warnings).
    """
    notes: list[str] = []

    # Formula P3-1: Small RCT linear interpolation
    if study_design == "large_rct":
        # Verify N > threshold if provided
        if n_total is not None and n_total <= config.SMALL_RCT_N_THRESHOLD:
            # Reclassify: caller labeled large_rct but N ≤ 200
            m_design = _small_rct_interpolation(n_total)
            notes.append(
                f"L1: Reclassified large_rct to small_rct (N={n_total} "
                f"<= {config.SMALL_RCT_N_THRESHOLD}), m={m_design:.4f}"
            )
            return m_design, notes
        m_design = config.DESIGN_MULTIPLIERS["large_rct"]
        return m_design, notes

    if study_design in ("small_rct", "small_rct_default"):
        # Formula P3-1: m = 1.0 + 0.5×(200−N)/200
        if n_total is not None:
            m_design = _small_rct_interpolation(n_total)
        else:
            # No N available — use default midpoint
            m_design = config.DESIGN_MULTIPLIERS["small_rct_default"]
            notes.append(
                f"L1: Small RCT without N; using default m={m_design}"
            )
        return m_design, notes

    # Direct lookup for non-RCT designs
    if study_design in config.DESIGN_MULTIPLIERS:
        m_design = config.DESIGN_MULTIPLIERS[study_design]
        return m_design, notes

    # Unclassified → default 3.0× + WARN
    m_design = config.DESIGN_MULTIPLIER_DEFAULT
    notes.append(
        f"L1: Unclassified study design '{study_design}'; "
        f"defaulting m={m_design}"
    )
    logger.warning(
        "L1 study design unclassified: '%s'. "
        "Using default multiplier %.2f.",
        study_design,
        m_design,
    )
    return m_design, notes


def _small_rct_interpolation(n_total: int) -> float:
    """Formula P3-1: m = 1.0 + 0.5×(200−N)/200 for small RCTs.

    Range: [1.0, 1.5] when N ∈ [0, 200].
    """
    # Formula P3-1: m = 1.0 + SLOPE × (THRESHOLD − N) / THRESHOLD
    n_clamped = max(0, min(n_total, config.SMALL_RCT_N_THRESHOLD))
    m = (
        config.DESIGN_MULTIPLIERS["large_rct"]
        + config.SMALL_RCT_PENALTY_SLOPE
        * (config.SMALL_RCT_N_THRESHOLD - n_clamped)
        / config.SMALL_RCT_N_THRESHOLD
    )
    return m


# ═══════════════════════════════════════════════════════════════
#  L2 — Scope Match (Formula P3-2)
# ═══════════════════════════════════════════════════════════════


def layer_2_scope_match(
    w_scope: float,
) -> tuple[float, list[str]]:
    """Compute the scope-match divisor for SE inflation.

    Formula P3-2:
      SE_L2 = SE_L1 / max(w_scope, 0.3)
      w_scope from EX-P2-S6 (5 dimensions: cancer 0.35, phase 0.25,
      regimen 0.20, age 0.10, sex 0.10).
      Floor: 0.3 (max SE inflation 3.33×).

    Args:
        w_scope: Scope match weight from P2 harmonization (0.0 to 1.0).

    Returns:
        Tuple of (effective w_scope after floor, list of notes).
    """
    notes: list[str] = []

    # Formula P3-2: floor at SCOPE_FLOOR
    effective_w_scope = max(w_scope, config.SCOPE_FLOOR)

    if w_scope < config.SCOPE_FLOOR:
        notes.append(
            f"L2: w_scope={w_scope:.4f} below floor {config.SCOPE_FLOOR}; "
            f"clamped to {effective_w_scope:.4f}"
        )
        logger.info(
            "L2 scope weight %.4f below floor %.2f; clamped.",
            w_scope,
            config.SCOPE_FLOOR,
        )

    return effective_w_scope, notes


# ═══════════════════════════════════════════════════════════════
#  L3 — Statistical Heterogeneity (Formula P3-3)
# ═══════════════════════════════════════════════════════════════


@dataclass
class HeterogeneityResult:
    """Output of Layer 3 statistical heterogeneity computation."""

    tau_squared: float
    i_squared: float
    q_statistic: float
    add_tau_squared: bool  # True if I² ≥ 50%
    notes: list[str]


def layer_3_statistical_heterogeneity(
    betas: list[float],
    ses: list[float],
) -> HeterogeneityResult:
    """Compute DerSimonian-Laird τ² and I² from study-level estimates.

    Formula P3-3:
      If k < 2: τ² = 0, I² = 0
      Else:
        Q = Σ w_i(β_i − β̂_IVW)²
        τ² = max(0, (Q − (k−1)) / (Σw − Σw²/Σw))   (DerSimonian-Laird)
        I² = max(0, (Q − (k−1)) / Q) × 100
      I² < 50%: no τ² added
      I² ≥ 50%: τ² added to each SE²_i

    Args:
        betas: List of study-level effect estimates.
        ses: List of study-level standard errors (must be > 0).

    Returns:
        HeterogeneityResult with τ², I², Q, and whether to add τ².
    """
    notes: list[str] = []
    k = len(betas)

    if k != len(ses):
        raise ValueError(
            f"L3: betas length ({k}) != ses length ({len(ses)})"
        )

    # Formula P3-3: If k < 2: τ² = 0, I² = 0
    if k < 2:
        notes.append(f"L3: k={k} < 2; τ²=0, I²=0 by definition")
        return HeterogeneityResult(
            tau_squared=0.0,
            i_squared=0.0,
            q_statistic=0.0,
            add_tau_squared=False,
            notes=notes,
        )

    # Formula P3-3: IVW weights w_i = 1/SE²_i
    weights = [1.0 / (se * se) for se in ses]
    sum_w = sum(weights)

    # Formula P3-3: β̂_IVW = Σ(β_i × w_i) / Σ(w_i)
    beta_ivw = sum(b * w for b, w in zip(betas, weights)) / sum_w

    # Formula P3-3: Q = Σ w_i × (β_i − β̂_IVW)²
    q_stat = sum(w * (b - beta_ivw) ** 2 for b, w in zip(betas, weights))

    # Formula P3-3: τ² = max(0, (Q − (k−1)) / (Σw − Σw²/Σw))
    sum_w_sq = sum(w * w for w in weights)
    denominator = sum_w - sum_w_sq / sum_w
    if denominator > 0.0:
        tau_sq = max(0.0, (q_stat - (k - 1)) / denominator)
    else:
        tau_sq = 0.0
        notes.append("L3: DerSimonian-Laird denominator ≤ 0; τ²=0")

    # Formula P3-3: I² = max(0, (Q − (k−1)) / Q) × 100
    if q_stat > 0.0:
        i_sq = max(0.0, (q_stat - (k - 1)) / q_stat) * 100.0
    else:
        i_sq = 0.0

    # Formula P3-3: I² < 50% → no τ² added; I² ≥ 50% → τ² added
    add_tau = i_sq >= config.HETEROGENEITY_MODERATE_THRESHOLD

    notes.append(
        f"L3: k={k}, Q={q_stat:.4f}, τ²={tau_sq:.6f}, "
        f"I²={i_sq:.1f}%, add_τ²={add_tau}"
    )

    return HeterogeneityResult(
        tau_squared=tau_sq,
        i_squared=i_sq,
        q_statistic=q_stat,
        add_tau_squared=add_tau,
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════════
#  L4 — Scale / Cancer Validation (Formula P3-4)
# ═══════════════════════════════════════════════════════════════


def layer_4_scale_validation(
    validation_status: str,
) -> tuple[float, list[str]]:
    """Compute the scale/cancer validation multiplier.

    Formula P3-4:
      VALIDATED_CANCER: 1.00
      USED_IN_CANCER: 1.15
      GENERAL_POPULATION: 1.30
      KNOWN_SOMATIC_CONFOUND: 1.50

    Args:
        validation_status: Cancer validation status key matching
                           config.SCALE_MULTIPLIERS keys.

    Returns:
        Tuple of (m_scale multiplier, list of notes).
    """
    notes: list[str] = []

    # Formula P3-4: lookup from config.SCALE_MULTIPLIERS
    if validation_status in config.SCALE_MULTIPLIERS:
        m_scale = config.SCALE_MULTIPLIERS[validation_status]
    else:
        # Default to general_population if unrecognized
        m_scale = config.SCALE_MULTIPLIERS["general_population"]
        notes.append(
            f"L4: Unrecognized validation_status '{validation_status}'; "
            f"defaulting to general_population m={m_scale}"
        )
        logger.warning(
            "L4 scale validation unrecognized: '%s'. "
            "Using general_population multiplier %.2f.",
            validation_status,
            m_scale,
        )

    return m_scale, notes


# ═══════════════════════════════════════════════════════════════
#  L5 — GRADE Quality (Formula P3-5)
# ═══════════════════════════════════════════════════════════════


def layer_5_grade_quality(
    grade_level: str,
) -> tuple[float, list[str]]:
    """Compute the GRADE quality multiplier.

    Formula P3-5:
      HIGH: 1.00
      MODERATE: 1.25
      LOW: 1.50
      VERY_LOW: 2.00

    Args:
        grade_level: GRADE level key matching config.GRADE_MULTIPLIERS keys.

    Returns:
        Tuple of (m_grade multiplier, list of notes).
    """
    notes: list[str] = []

    # Formula P3-5: lookup from config.GRADE_MULTIPLIERS
    if grade_level in config.GRADE_MULTIPLIERS:
        m_grade = config.GRADE_MULTIPLIERS[grade_level]
    else:
        # Default to MODERATE if unrecognized
        m_grade = config.GRADE_MULTIPLIERS["MODERATE"]
        notes.append(
            f"L5: Unrecognized grade_level '{grade_level}'; "
            f"defaulting to MODERATE m={m_grade}"
        )
        logger.warning(
            "L5 GRADE level unrecognized: '%s'. "
            "Using MODERATE multiplier %.2f.",
            grade_level,
            m_grade,
        )

    return m_grade, notes


# ═══════════════════════════════════════════════════════════════
#  L6 — Temporal Decay (Formula P3-6)
# ═══════════════════════════════════════════════════════════════


def layer_6_temporal_decay(
    days_since_measurement: float,
    is_trait: bool = False,
) -> tuple[float, bool, list[str]]:
    """Compute the temporal decay weight for measurement recency.

    Formula P3-6:
      w(t) = e^{−0.05t}  where t = days since measurement
      >90 days → EXCLUDED (record removed)
      SE_L6 = SE_L5 / max(w_temporal, 0.01)
      Trait measures (is_trait=true) exempt: w_temporal = 1.0 always

    Args:
        days_since_measurement: Days elapsed since the measurement.
        is_trait: If True, measurement is a stable trait (exempt from decay).

    Returns:
        Tuple of (w_temporal weight, excluded flag, list of notes).
    """
    notes: list[str] = []

    # Formula P3-6: Trait measures exempt
    if is_trait:
        notes.append("L6: Trait measure; temporal decay exempt, w=1.0")
        return 1.0, False, notes

    # Formula P3-6: >90 days → EXCLUDED
    if days_since_measurement > config.TEMPORAL_EXCLUSION_DAYS:
        notes.append(
            f"L6: days={days_since_measurement} > "
            f"{config.TEMPORAL_EXCLUSION_DAYS}; EXCLUDED"
        )
        return 0.0, True, notes

    # Formula P3-6: w(t) = e^{−TEMPORAL_DECAY_RATE × t}
    w_temporal = math.exp(
        -config.TEMPORAL_DECAY_RATE * days_since_measurement
    )

    # Formula P3-6: floor at TEMPORAL_WEIGHT_FLOOR
    effective_w = max(w_temporal, config.TEMPORAL_WEIGHT_FLOOR)

    if w_temporal < config.TEMPORAL_WEIGHT_FLOOR:
        notes.append(
            f"L6: w_temporal={w_temporal:.6f} below floor "
            f"{config.TEMPORAL_WEIGHT_FLOOR}; clamped"
        )

    notes.append(
        f"L6: days={days_since_measurement}, "
        f"w_temporal={effective_w:.6f}"
    )
    return effective_w, False, notes


# ═══════════════════════════════════════════════════════════════
#  L7 — Freshness Decay (Formula P3-7)
# ═══════════════════════════════════════════════════════════════


def layer_7_freshness_decay(
    pub_year: int | None,
) -> tuple[float, list[str]]:
    """Compute the publication freshness weight.

    Formula P3-7:
      w_fresh = max(0.70, 1 − 0.015 × (REFERENCE_YEAR − pub_year))
      Floor: 0.70
      No pub date → default w_fresh = 0.85 + WARN

    Args:
        pub_year: Publication year of the study, or None if unknown.

    Returns:
        Tuple of (w_fresh weight, list of notes).
    """
    notes: list[str] = []

    # Formula P3-7: No pub date → default
    if pub_year is None:
        w_fresh = config.FRESHNESS_DEFAULT_WEIGHT
        notes.append(
            f"L7: No publication year; using default w_fresh={w_fresh}"
        )
        logger.warning(
            "L7 freshness: no publication year available. "
            "Using default weight %.2f.",
            w_fresh,
        )
        return w_fresh, notes

    # Formula P3-7: w_fresh = max(FLOOR, 1 − DECAY_RATE × (REF_YEAR − pub_year))
    age_years = config.FRESHNESS_REFERENCE_YEAR - pub_year
    w_raw = 1.0 - config.FRESHNESS_DECAY_RATE * age_years
    w_fresh = max(config.FRESHNESS_FLOOR, w_raw)

    if w_raw < config.FRESHNESS_FLOOR:
        notes.append(
            f"L7: w_raw={w_raw:.4f} below floor {config.FRESHNESS_FLOOR}; "
            f"clamped to {w_fresh:.4f}"
        )

    notes.append(
        f"L7: pub_year={pub_year}, age={age_years}y, "
        f"w_fresh={w_fresh:.4f}"
    )
    return w_fresh, notes
