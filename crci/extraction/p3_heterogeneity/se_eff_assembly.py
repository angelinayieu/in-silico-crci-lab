# VERIFIED: formula P3-8 matches spec worked example (SE_eff ≈ 0.67)
# VERIFIED: imports — all modules exist (config, layers, intermediate_states)
# VERIFIED: backward wiring — reads HarmonizedClaim from p2_harmonization
# VERIFIED: forward wiring — writes LayeredSEResult for p4_aggregation/meta_analyzer.py
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gate P3-G1 raises GateViolation on SE_eff < SE_raw
"""
Component: SYS_EXTRACTION.EX-P3 — SE_eff Final Assembly
Spec: SYS_EXTRACTION_COMPLETE.md lines 765-1100
Formulas: P3-8 (final SE_eff assembly)
Reads: HarmonizedClaim (from p2_harmonization),
       layer functions (from layers.py)
Writes: LayeredSEResult (consumed by p4_aggregation/meta_analyzer.py)
Gates: P3-G1 (SE_eff ≥ SE_raw — calibration only inflates, never deflates)

Worked Example (from spec):
  Input: β=0.35, SE=0.12, Large RCT, cancer-validated, GRADE High,
         10 days ago, pub 2023, w_scope=0.80, k=3, I²=30%
  L1: m_design = 1.0
  L2: max(w_scope, 0.3) = 0.80
  L3: I²=30% < 50% → τ²=0
  L4: m_scale = 1.0 (validated_cancer)
  L5: m_grade = 1.0 (HIGH)
  L6: w(10) = e^{−0.5} ≈ 0.607 (no exclusion, within 90d window)
  L7: w_fresh = 1 − 0.015×3 = 0.955
  numerator² = (0.12 × 1.0 × 1.0 × 1.0)² + 0.25 + 0 = 0.2644
  SE_eff = √0.2644 / (0.80 × 0.955) = 0.514 / 0.764 ≈ 0.67
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field as dataclass_field

from crci.shared import config
from crci.shared.models.intermediate_states import (
    GateViolation,
    HarmonizedClaim,
    LayeredSEResult,
)

from .freshness_policy import compute_freshness
from .layers import (
    HeterogeneityResult,
    layer_1_study_design,
    layer_2_scope_match,
    layer_3_statistical_heterogeneity,
    layer_4_scale_validation,
    layer_5_grade_quality,
    layer_6_temporal_decay,
    layer_7_freshness_decay,
)

logger = logging.getLogger(__name__)


@dataclass
class SEEffInput:
    """All inputs needed for the 7-layer SE_eff computation.

    Collects claim data plus contextual metadata for all layers.
    """

    # Core claim data
    ler_id: str
    se_raw: float  # Original SE from harmonization

    # L1: Study design
    study_design: str
    n_total: int | None = None

    # L2: Scope match
    w_scope: float = 1.0

    # L3: Statistical heterogeneity (multi-study context)
    betas: list[float] = dataclass_field(default_factory=list)
    ses: list[float] = dataclass_field(default_factory=list)

    # L4: Scale/cancer validation
    validation_status: str = "general_population"

    # L5: GRADE quality
    grade_level: str = "MODERATE"

    # L6: Temporal decay
    days_since_measurement: float = 0.0
    # Flag indicating whether days_since_measurement is truly known
    # vs. defaulting to 0.0 because no temporal evidence exists
    temporal_data_available: bool = False
    is_trait: bool = False

    # L7: Freshness
    pub_year: int | None = None
    # v2.0: Family-specific freshness (Module 5)
    parameter_family: str | None = None
    superseded_by_newer: bool = False
    # DW#6: Annotation-derived σ²_structural (from shared_annotation_features)
    # When None, falls back to config.SIGMA_SQ_STRUCTURAL_DEFAULT
    sigma_sq_structural: float | None = None
    # Edge relation ID for logging annotation provenance
    edge_relation_id: str | None = None


def compute_se_eff(inp: SEEffInput) -> LayeredSEResult:
    """Apply all 7 layers and assemble SE_eff via Formula P3-8.

    Formula P3-8:
      SE_eff = √[(SE_pooled · m_design · m_scale · m_GRADE)²
               + σ²_struct + τ² · 𝟙[I²≥50%]]
               / (max(w_scope, 0.3) · w_fresh)

    Gate P3-G1: SE_eff ≥ SE_raw (calibration only inflates, never deflates)

    # REVIEW: The P3-8 formula text in the spec lists m_temporal as a
    # numerator multiplier, but the worked example demonstrates that
    # temporal decay (L6: w(t) = e^{-0.05t}) does NOT appear in the
    # final SE_eff arithmetic. Temporal decay acts as an exclusion
    # filter (>90 days → record removed) but does not further inflate
    # SE_eff for included records. This implementation matches the
    # worked example exactly (SE_eff ≈ 0.67).

    Args:
        inp: SEEffInput containing all layer inputs.

    Returns:
        LayeredSEResult with effective SE and per-layer breakdown.

    Raises:
        GateViolation: If P3-G1 is violated (SE_eff < SE_raw).
        ValueError: If the record is temporally excluded (L6 >90 days).
    """
    all_notes: list[str] = []
    layer_multipliers: dict[str, float] = {}
    layers_applied: list[str] = []

    # ─── L1: Study Design ─────────────────────────────────────
    # Formula P3-1
    m_design, l1_notes = layer_1_study_design(
        study_design=inp.study_design,
        n_total=inp.n_total,
    )
    layer_multipliers["L1_design"] = m_design
    layers_applied.append("L1_design")
    all_notes.extend(l1_notes)

    # ─── L2: Scope Match ──────────────────────────────────────
    # Formula P3-2
    effective_w_scope, l2_notes = layer_2_scope_match(w_scope=inp.w_scope)
    layer_multipliers["L2_scope"] = effective_w_scope
    layers_applied.append("L2_scope")
    all_notes.extend(l2_notes)

    # ─── L3: Statistical Heterogeneity ────────────────────────
    # Formula P3-3
    het_result: HeterogeneityResult = layer_3_statistical_heterogeneity(
        betas=inp.betas,
        ses=inp.ses,
    )
    layer_multipliers["L3_tau_squared"] = het_result.tau_squared
    layer_multipliers["L3_i_squared"] = het_result.i_squared
    layers_applied.append("L3_heterogeneity")
    all_notes.extend(het_result.notes)

    # ─── L4: Scale / Cancer Validation ────────────────────────
    # Formula P3-4
    m_scale, l4_notes = layer_4_scale_validation(
        validation_status=inp.validation_status,
    )
    layer_multipliers["L4_scale"] = m_scale
    layers_applied.append("L4_scale")
    all_notes.extend(l4_notes)

    # ─── L5: GRADE Quality ────────────────────────────────────
    # Formula P3-5
    m_grade, l5_notes = layer_5_grade_quality(
        grade_level=inp.grade_level,
    )
    layer_multipliers["L5_grade"] = m_grade
    layers_applied.append("L5_grade")
    all_notes.extend(l5_notes)

    # ─── L6: Temporal Decay ───────────────────────────────────
    # Formula P3-6
    w_temporal, excluded, l6_notes = layer_6_temporal_decay(
        days_since_measurement=inp.days_since_measurement,
        is_trait=inp.is_trait,
    )
    layer_multipliers["L6_temporal"] = w_temporal
    layers_applied.append("L6_temporal")
    all_notes.extend(l6_notes)

    # Flag when temporal data is absent (defaulting to 0.0 = no penalty)
    if not inp.temporal_data_available and inp.days_since_measurement == 0.0:
        # Apply conservative default from config instead of optimistic 0.0
        if config.TEMPORAL_DEFAULT_WHEN_ABSENT_DAYS > 0.0:
            effective_days = config.TEMPORAL_DEFAULT_WHEN_ABSENT_DAYS
            # Recompute L6 with conservative default
            w_temporal, excluded, l6_notes_override = layer_6_temporal_decay(
                days_since_measurement=effective_days,
                is_trait=inp.is_trait,
            )
            layer_multipliers["L6_temporal"] = w_temporal
            all_notes.extend(l6_notes_override)
            all_notes.append(
                f"L6: WARNING — temporal data absent, applied conservative "
                f"default {effective_days:.1f}d (w_temporal={w_temporal:.4f})"
            )
            logger.info(
                "L6 temporal conservative default: record '%s' has no temporal "
                "evidence — using TEMPORAL_DEFAULT_WHEN_ABSENT_DAYS=%.1f "
                "(w_temporal=%.4f instead of 1.0)",
                inp.ler_id, effective_days, w_temporal,
            )
        else:
            all_notes.append(
                "L6: WARNING — temporal data absent, "
                "days_since_measurement=0.0 assumed (w_temporal=1.0, no SE penalty)"
            )
            logger.warning(
                "L6 temporal default: record '%s' has no temporal evidence — "
                "days_since_measurement=0.0 assumed (w_temporal=1.0, no SE penalty)",
                inp.ler_id,
            )

    if excluded:
        raise ValueError(
            f"L6 temporal exclusion: record '{inp.ler_id}' excluded "
            f"(days_since_measurement={inp.days_since_measurement} > "
            f"{config.TEMPORAL_EXCLUSION_DAYS})"
        )

    # ─── L7: Freshness Decay ─────────────────────────────────
    # Formula P3-7 (universal) or F5-1 (family-specific, Module 5)
    if inp.parameter_family is not None:
        # v2.0: Use family-specific freshness policy
        fr = compute_freshness(
            pub_year=inp.pub_year,
            family=inp.parameter_family,
            superseded_by_newer=inp.superseded_by_newer,
        )
        w_fresh = fr.w_fresh
        l7_notes = [f"L7: {fr.notes}"]
    else:
        # Backward-compatible: universal 1.5%/yr
        w_fresh, l7_notes = layer_7_freshness_decay(pub_year=inp.pub_year)
    layer_multipliers["L7_freshness"] = w_fresh
    layers_applied.append("L7_freshness")
    all_notes.extend(l7_notes)

    # ═══════════════════════════════════════════════════════════
    #  Formula P3-8: SE_eff Assembly
    # ═══════════════════════════════════════════════════════════
    #
    # SE_eff = √[(SE_pooled · m_design · m_scale · m_GRADE)²
    #            + σ²_struct + τ² · 𝟙[I²≥50%]]
    #          / (max(w_scope, 0.3) · w_fresh)
    #
    # REVIEW: Temporal decay (L6) serves as an exclusion gate
    # (>90d → excluded) but per the worked example does not
    # inflate SE_eff for included records. See module docstring.

    # Numerator terms under the square root
    se_product = inp.se_raw * m_design * m_scale * m_grade
    se_product_sq = se_product * se_product

    # DW#6 fix: use annotation-derived σ²_structural when available,
    # fall back to config default otherwise
    if inp.sigma_sq_structural is not None:
        sigma_sq_struct = inp.sigma_sq_structural
        logger.debug(
            "P3-8 %s: using annotation-derived σ²_structural=%.4f (edge=%s)",
            inp.ler_id, sigma_sq_struct, inp.edge_relation_id or "?",
        )
    else:
        sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
        logger.debug(
            "P3-8 %s: using default σ²_structural=%.4f (no annotation data)",
            inp.ler_id, sigma_sq_struct,
        )

    # Formula P3-3 / P3-8: τ² added only if I² ≥ 50%
    tau_sq_term = het_result.tau_squared if het_result.add_tau_squared else 0.0

    numerator_sq = se_product_sq + sigma_sq_struct + tau_sq_term
    numerator = math.sqrt(numerator_sq)

    # Denominator
    denominator = effective_w_scope * w_fresh

    # Formula P3-8: Final SE_eff
    se_eff = numerator / denominator

    all_notes.append(
        f"P3-8: SE_product={se_product:.6f}, σ²_struct={sigma_sq_struct}, "
        f"τ²_term={tau_sq_term:.6f}, numerator={numerator:.6f}, "
        f"denom={denominator:.6f}, SE_eff={se_eff:.6f}"
    )

    # ═══════════════════════════════════════════════════════════
    #  Gate P3-G1: SE_eff ≥ SE_raw
    #  Calibration only inflates, never deflates.
    # ═══════════════════════════════════════════════════════════
    if se_eff < inp.se_raw:
        raise GateViolation(
            gate_id="P3-G1",
            message=(
                f"SE_eff ({se_eff:.6f}) < SE_raw ({inp.se_raw:.6f}). "
                f"Seven-layer calibration must only inflate SE, never deflate."
            ),
            context={
                "ler_id": inp.ler_id,
                "se_raw": inp.se_raw,
                "se_eff": se_eff,
                "layer_multipliers": layer_multipliers,
            },
        )

    return LayeredSEResult(
        ler_id=inp.ler_id,
        se_base=inp.se_raw,
        layer_multipliers=layer_multipliers,
        se_effective=se_eff,
        layers_applied=layers_applied,
        notes=all_notes,
    )


def compute_se_eff_for_claim(
    claim: HarmonizedClaim,
    study_design: str,
    n_total: int | None = None,
    w_scope: float = 1.0,
    betas: list[float] | None = None,
    ses: list[float] | None = None,
    validation_status: str = "general_population",
    grade_level: str = "MODERATE",
    days_since_measurement: float = 0.0,
    is_trait: bool = False,
    pub_year: int | None = None,
    *,
    parameter_family: str | None = None,
    superseded_by_newer: bool = False,
) -> LayeredSEResult:
    """Convenience wrapper: compute SE_eff from a HarmonizedClaim.

    Builds SEEffInput from the claim and contextual parameters,
    then delegates to compute_se_eff().

    Args:
        claim: HarmonizedClaim from P2 harmonization.
        study_design: Study design classification key.
        n_total: Total sample size (for small RCT interpolation).
        w_scope: Scope match weight (0.0 to 1.0).
        betas: Study-level betas for heterogeneity (L3).
        ses: Study-level SEs for heterogeneity (L3).
        validation_status: Cancer validation status key.
        grade_level: GRADE quality level key.
        days_since_measurement: Days since measurement (L6).
        is_trait: Whether measurement is a stable trait (L6 exemption).
        pub_year: Publication year (L7).

    Returns:
        LayeredSEResult with effective SE.

    Raises:
        GateViolation: If P3-G1 is violated.
        ValueError: If record is temporally excluded.
    """
    if claim.harmonized_se is None:
        raise ValueError(
            f"HarmonizedClaim '{claim.ler_id}' has no harmonized_se; "
            f"cannot compute SE_eff."
        )

    inp = SEEffInput(
        ler_id=claim.ler_id,
        se_raw=claim.harmonized_se,
        study_design=study_design,
        n_total=n_total or claim.n_effect,
        w_scope=w_scope,
        betas=betas or [],
        ses=ses or [],
        validation_status=validation_status,
        grade_level=grade_level,
        days_since_measurement=days_since_measurement,
        is_trait=is_trait,
        pub_year=pub_year,
        parameter_family=parameter_family,
        superseded_by_newer=superseded_by_newer,
    )
    return compute_se_eff(inp)
