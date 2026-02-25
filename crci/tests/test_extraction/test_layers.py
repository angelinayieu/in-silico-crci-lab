"""
Tests for crci/extraction/heterogeneity/layers.py

Formula-dense file: tests cover hand-computable expected values,
edge cases (k=0, k=1, missing data, boundary values),
gate violation tests, and config constant verification.

Formulas tested: P3-1, P3-2, P3-3, P3-4, P3-5, P3-6, P3-7
"""
from __future__ import annotations

import math

import pytest

from crci.shared import config
from crci.extraction.p3_heterogeneity.layers import (
    HeterogeneityResult,
    layer_1_study_design,
    layer_2_scope_match,
    layer_3_statistical_heterogeneity,
    layer_4_scale_validation,
    layer_5_grade_quality,
    layer_6_temporal_decay,
    layer_7_freshness_decay,
)


# ═══════════════════════════════════════════════════════════════
#  L1 — Study Design (Formula P3-1)
# ═══════════════════════════════════════════════════════════════


class TestLayer1StudyDesign:
    """Tests for Formula P3-1: study design multiplier."""

    def test_large_rct(self) -> None:
        """Large RCT (N>200) → m = 1.0."""
        m, notes = layer_1_study_design("large_rct", n_total=500)
        assert m == config.DESIGN_MULTIPLIERS["large_rct"]
        assert m == 1.0

    def test_large_rct_no_n(self) -> None:
        """Large RCT with no N → still 1.0."""
        m, notes = layer_1_study_design("large_rct", n_total=None)
        assert m == 1.0

    def test_large_rct_reclassified_small(self) -> None:
        """Large RCT labeled but N ≤ 200 → reclassified to small RCT."""
        m, notes = layer_1_study_design("large_rct", n_total=100)
        # Formula P3-1: m = 1.0 + 0.5×(200−100)/200 = 1.0 + 0.25 = 1.25
        expected = 1.0 + 0.5 * (200 - 100) / 200
        assert m == pytest.approx(expected)
        assert m == pytest.approx(1.25)
        assert any("Reclassified" in n for n in notes)

    def test_small_rct_interpolation_n0(self) -> None:
        """Small RCT with N=0 → maximum penalty m = 1.5."""
        m, notes = layer_1_study_design("small_rct", n_total=0)
        # m = 1.0 + 0.5×(200−0)/200 = 1.5
        assert m == pytest.approx(1.5)

    def test_small_rct_interpolation_n200(self) -> None:
        """Small RCT with N=200 → minimum penalty m = 1.0."""
        m, notes = layer_1_study_design("small_rct", n_total=200)
        # m = 1.0 + 0.5×(200−200)/200 = 1.0
        assert m == pytest.approx(1.0)

    def test_small_rct_interpolation_n100(self) -> None:
        """Small RCT with N=100 → m = 1.25 (hand computed)."""
        m, notes = layer_1_study_design("small_rct", n_total=100)
        # m = 1.0 + 0.5×(200−100)/200 = 1.25
        assert m == pytest.approx(1.25)

    def test_small_rct_no_n_default(self) -> None:
        """Small RCT without N → use default midpoint."""
        m, notes = layer_1_study_design("small_rct", n_total=None)
        assert m == config.DESIGN_MULTIPLIERS["small_rct_default"]
        assert any("default" in n.lower() for n in notes)

    def test_well_adjusted_cohort(self) -> None:
        """Well-adjusted cohort → m = 1.5."""
        m, notes = layer_1_study_design("well_adjusted_cohort")
        assert m == pytest.approx(1.5)

    def test_unadjusted_longitudinal(self) -> None:
        """Unadjusted longitudinal → m = 2.0."""
        m, notes = layer_1_study_design("unadjusted_longitudinal")
        assert m == pytest.approx(2.0)

    def test_cross_sectional_adjusted(self) -> None:
        """Cross-sectional adjusted → m = 2.5."""
        m, notes = layer_1_study_design("cross_sectional_adjusted")
        assert m == pytest.approx(2.5)

    def test_cross_sectional_unadjusted(self) -> None:
        """Cross-sectional unadjusted → m = 3.0."""
        m, notes = layer_1_study_design("cross_sectional_unadjusted")
        assert m == pytest.approx(3.0)

    def test_animal_in_vivo(self) -> None:
        """Animal in vivo → m = 4.0."""
        m, notes = layer_1_study_design("animal_in_vivo")
        assert m == pytest.approx(4.0)

    def test_in_vitro_mechanistic(self) -> None:
        """In vitro / mechanistic → m = 5.0."""
        m, notes = layer_1_study_design("in_vitro_mechanistic")
        assert m == pytest.approx(5.0)

    def test_expert_opinion(self) -> None:
        """Expert opinion / narrative → m = 6.0."""
        m, notes = layer_1_study_design("expert_opinion")
        assert m == pytest.approx(6.0)

    def test_unclassified_default(self) -> None:
        """Unclassified design → default 3.0 + WARN."""
        m, notes = layer_1_study_design("unknown_design_xyz")
        assert m == config.DESIGN_MULTIPLIER_DEFAULT
        assert m == pytest.approx(3.0)
        assert any("Unclassified" in n for n in notes)

    def test_constants_from_config(self) -> None:
        """All multipliers come from config, not hardcoded."""
        assert "large_rct" in config.DESIGN_MULTIPLIERS
        assert "expert_opinion" in config.DESIGN_MULTIPLIERS
        assert config.SMALL_RCT_N_THRESHOLD == 200
        assert config.SMALL_RCT_PENALTY_SLOPE == 0.5
        assert config.DESIGN_MULTIPLIER_DEFAULT == 3.0


# ═══════════════════════════════════════════════════════════════
#  L2 — Scope Match (Formula P3-2)
# ═══════════════════════════════════════════════════════════════


class TestLayer2ScopeMatch:
    """Tests for Formula P3-2: scope match divisor."""

    def test_perfect_scope(self) -> None:
        """w_scope = 1.0 → no inflation."""
        w_eff, notes = layer_2_scope_match(1.0)
        assert w_eff == pytest.approx(1.0)

    def test_partial_scope(self) -> None:
        """w_scope = 0.80 → SE / 0.80 (1.25× inflation)."""
        w_eff, notes = layer_2_scope_match(0.80)
        assert w_eff == pytest.approx(0.80)

    def test_below_floor(self) -> None:
        """w_scope = 0.10 → clamped to floor 0.3."""
        w_eff, notes = layer_2_scope_match(0.10)
        assert w_eff == pytest.approx(config.SCOPE_FLOOR)
        assert w_eff == pytest.approx(0.3)
        assert any("below floor" in n for n in notes)

    def test_at_floor(self) -> None:
        """w_scope = 0.3 → exactly at floor."""
        w_eff, notes = layer_2_scope_match(0.3)
        assert w_eff == pytest.approx(0.3)

    def test_zero_scope(self) -> None:
        """w_scope = 0.0 → clamped to floor 0.3 (max 3.33× inflation)."""
        w_eff, notes = layer_2_scope_match(0.0)
        assert w_eff == pytest.approx(config.SCOPE_FLOOR)


# ═══════════════════════════════════════════════════════════════
#  L3 — Statistical Heterogeneity (Formula P3-3)
# ═══════════════════════════════════════════════════════════════


class TestLayer3StatisticalHeterogeneity:
    """Tests for Formula P3-3: DerSimonian-Laird τ² and I²."""

    def test_k_zero(self) -> None:
        """k = 0: τ² = 0, I² = 0."""
        result = layer_3_statistical_heterogeneity([], [])
        assert result.tau_squared == 0.0
        assert result.i_squared == 0.0
        assert result.add_tau_squared is False

    def test_k_one(self) -> None:
        """k = 1: τ² = 0, I² = 0."""
        result = layer_3_statistical_heterogeneity([0.5], [0.1])
        assert result.tau_squared == 0.0
        assert result.i_squared == 0.0
        assert result.add_tau_squared is False

    def test_k_two_homogeneous(self) -> None:
        """k = 2 with identical studies: Q ≈ 0, τ² = 0, I² = 0."""
        result = layer_3_statistical_heterogeneity(
            [0.5, 0.5], [0.1, 0.1]
        )
        assert result.tau_squared == pytest.approx(0.0, abs=1e-10)
        assert result.i_squared == pytest.approx(0.0, abs=1e-10)
        assert result.add_tau_squared is False

    def test_k_three_hand_computed(self) -> None:
        """k = 3 with hand-computed values.

        betas = [0.3, 0.5, 0.7], SEs = [0.1, 0.15, 0.2]
        w_i = [100, 44.44, 25]
        sum_w = 169.44
        beta_IVW = (30 + 22.22 + 17.5) / 169.44 = 69.72 / 169.44 ≈ 0.4115
        Q = 100×(0.3−0.4115)² + 44.44×(0.5−0.4115)² + 25×(0.7−0.4115)²
          = 100×0.01244 + 44.44×0.00783 + 25×0.08332
          = 1.244 + 0.348 + 2.083 = 3.675
        τ² = max(0, (3.675 − 2) / (169.44 − (100²+44.44²+25²)/169.44))
        sum_w_sq = 10000 + 1974.9 + 625 = 12599.9
        denom = 169.44 − 12599.9/169.44 = 169.44 − 74.36 = 95.08
        τ² = max(0, 1.675 / 95.08) = 0.01762
        I² = max(0, (3.675 − 2) / 3.675) × 100 = 45.58%
        I² < 50% → no τ² added
        """
        betas = [0.3, 0.5, 0.7]
        ses = [0.1, 0.15, 0.2]
        result = layer_3_statistical_heterogeneity(betas, ses)

        # Hand-computed Q
        w = [1.0 / (s * s) for s in ses]
        sum_w = sum(w)
        beta_ivw = sum(b * wi for b, wi in zip(betas, w)) / sum_w
        q_expected = sum(
            wi * (b - beta_ivw) ** 2 for b, wi in zip(betas, w)
        )

        assert result.q_statistic == pytest.approx(q_expected, rel=1e-6)
        assert result.i_squared < config.HETEROGENEITY_MODERATE_THRESHOLD
        assert result.add_tau_squared is False

    def test_high_heterogeneity_adds_tau(self) -> None:
        """Highly heterogeneous studies: I² ≥ 50% → τ² added."""
        # Very divergent betas should produce high I²
        betas = [0.1, 0.5, 1.0, 2.0]
        ses = [0.05, 0.05, 0.05, 0.05]
        result = layer_3_statistical_heterogeneity(betas, ses)
        assert result.i_squared >= config.HETEROGENEITY_MODERATE_THRESHOLD
        assert result.add_tau_squared is True
        assert result.tau_squared > 0.0

    def test_mismatched_lengths_raises(self) -> None:
        """Mismatched betas/ses lengths should raise ValueError."""
        with pytest.raises(ValueError, match="betas length"):
            layer_3_statistical_heterogeneity([0.3, 0.5], [0.1])


# ═══════════════════════════════════════════════════════════════
#  L4 — Scale / Cancer Validation (Formula P3-4)
# ═══════════════════════════════════════════════════════════════


class TestLayer4ScaleValidation:
    """Tests for Formula P3-4: cancer validation multiplier."""

    def test_validated_cancer(self) -> None:
        m, notes = layer_4_scale_validation("validated_cancer")
        assert m == pytest.approx(1.0)

    def test_used_cancer(self) -> None:
        m, notes = layer_4_scale_validation("used_cancer")
        assert m == pytest.approx(1.15)

    def test_general_population(self) -> None:
        m, notes = layer_4_scale_validation("general_population")
        assert m == pytest.approx(1.30)

    def test_known_somatic_confound(self) -> None:
        m, notes = layer_4_scale_validation("known_somatic_confound")
        assert m == pytest.approx(1.50)

    def test_unrecognized_defaults_to_general(self) -> None:
        """Unrecognized validation status → default to general_population."""
        m, notes = layer_4_scale_validation("unknown_status")
        assert m == pytest.approx(config.SCALE_MULTIPLIERS["general_population"])
        assert any("Unrecognized" in n for n in notes)

    def test_constants_from_config(self) -> None:
        """All multipliers come from config.SCALE_MULTIPLIERS."""
        assert config.SCALE_MULTIPLIERS["validated_cancer"] == 1.0
        assert config.SCALE_MULTIPLIERS["used_cancer"] == 1.15
        assert config.SCALE_MULTIPLIERS["general_population"] == 1.30
        assert config.SCALE_MULTIPLIERS["known_somatic_confound"] == 1.50


# ═══════════════════════════════════════════════════════════════
#  L5 — GRADE Quality (Formula P3-5)
# ═══════════════════════════════════════════════════════════════


class TestLayer5GradeQuality:
    """Tests for Formula P3-5: GRADE quality multiplier."""

    def test_high(self) -> None:
        m, notes = layer_5_grade_quality("HIGH")
        assert m == pytest.approx(1.0)

    def test_moderate(self) -> None:
        m, notes = layer_5_grade_quality("MODERATE")
        assert m == pytest.approx(1.25)

    def test_low(self) -> None:
        m, notes = layer_5_grade_quality("LOW")
        assert m == pytest.approx(1.50)

    def test_very_low(self) -> None:
        m, notes = layer_5_grade_quality("VERY_LOW")
        assert m == pytest.approx(2.00)

    def test_unrecognized_defaults_to_moderate(self) -> None:
        """Unrecognized GRADE → default to MODERATE."""
        m, notes = layer_5_grade_quality("UNKNOWN")
        assert m == pytest.approx(config.GRADE_MULTIPLIERS["MODERATE"])
        assert any("Unrecognized" in n for n in notes)

    def test_constants_from_config(self) -> None:
        """All multipliers come from config.GRADE_MULTIPLIERS."""
        assert config.GRADE_MULTIPLIERS["HIGH"] == 1.0
        assert config.GRADE_MULTIPLIERS["MODERATE"] == 1.25
        assert config.GRADE_MULTIPLIERS["LOW"] == 1.50
        assert config.GRADE_MULTIPLIERS["VERY_LOW"] == 2.00


# ═══════════════════════════════════════════════════════════════
#  L6 — Temporal Decay (Formula P3-6)
# ═══════════════════════════════════════════════════════════════


class TestLayer6TemporalDecay:
    """Tests for Formula P3-6: temporal decay weight."""

    def test_zero_days(self) -> None:
        """0 days → w = e^0 = 1.0."""
        w, excluded, notes = layer_6_temporal_decay(0.0)
        assert w == pytest.approx(1.0)
        assert excluded is False

    def test_10_days(self) -> None:
        """10 days → w = e^{-0.05×10} = e^{-0.5} ≈ 0.6065."""
        w, excluded, notes = layer_6_temporal_decay(10.0)
        expected = math.exp(-config.TEMPORAL_DECAY_RATE * 10.0)
        assert w == pytest.approx(expected)
        assert w == pytest.approx(math.exp(-0.5), rel=1e-6)
        assert excluded is False

    def test_90_days_boundary(self) -> None:
        """90 days → w = e^{-4.5} ≈ 0.0111, NOT excluded (== threshold)."""
        w, excluded, notes = layer_6_temporal_decay(90.0)
        assert excluded is False
        expected = math.exp(-config.TEMPORAL_DECAY_RATE * 90.0)
        assert w == pytest.approx(max(expected, config.TEMPORAL_WEIGHT_FLOOR))

    def test_91_days_excluded(self) -> None:
        """91 days → EXCLUDED (>90 days)."""
        w, excluded, notes = layer_6_temporal_decay(91.0)
        assert excluded is True

    def test_trait_exempt(self) -> None:
        """Trait measure → w = 1.0 always, regardless of days."""
        w, excluded, notes = layer_6_temporal_decay(50.0, is_trait=True)
        assert w == pytest.approx(1.0)
        assert excluded is False
        assert any("Trait" in n for n in notes)

    def test_trait_exempt_even_beyond_90_days(self) -> None:
        """Trait measure → w = 1.0 even for >90 days."""
        w, excluded, notes = layer_6_temporal_decay(200.0, is_trait=True)
        assert w == pytest.approx(1.0)
        assert excluded is False

    def test_temporal_weight_floor(self) -> None:
        """Very large days (but ≤90) should clamp at floor."""
        # At 89 days: w = e^{-0.05×89} = e^{-4.45} ≈ 0.01168 > floor 0.01
        w, excluded, notes = layer_6_temporal_decay(89.0)
        assert excluded is False
        assert w >= config.TEMPORAL_WEIGHT_FLOOR

    def test_constants_from_config(self) -> None:
        """Temporal constants come from config."""
        assert config.TEMPORAL_DECAY_RATE == 0.05
        assert config.TEMPORAL_EXCLUSION_DAYS == 90
        assert config.TEMPORAL_WEIGHT_FLOOR == 0.01


# ═══════════════════════════════════════════════════════════════
#  L7 — Freshness Decay (Formula P3-7)
# ═══════════════════════════════════════════════════════════════


class TestLayer7FreshnessDecay:
    """Tests for Formula P3-7: publication freshness weight."""

    def test_current_year(self) -> None:
        """pub_year = reference year → w = 1.0."""
        w, notes = layer_7_freshness_decay(config.FRESHNESS_REFERENCE_YEAR)
        assert w == pytest.approx(1.0)

    def test_3_years_old(self) -> None:
        """pub_year = 2023, ref = 2026 → w = 1 − 0.015×3 = 0.955."""
        w, notes = layer_7_freshness_decay(2023)
        expected = 1.0 - config.FRESHNESS_DECAY_RATE * (
            config.FRESHNESS_REFERENCE_YEAR - 2023
        )
        assert w == pytest.approx(expected)
        assert w == pytest.approx(0.955, rel=1e-6)

    def test_20_years_old_floor(self) -> None:
        """Very old study → floor at 0.70.

        pub_year = 2006 → age = 20 → w_raw = 1 − 0.015×20 = 0.70 (exactly at floor)
        """
        w, notes = layer_7_freshness_decay(2006)
        assert w == pytest.approx(config.FRESHNESS_FLOOR)
        assert w == pytest.approx(0.70)

    def test_very_old_below_floor(self) -> None:
        """Very old study → clamped at floor 0.70.

        pub_year = 2000 → age = 26 → w_raw = 1 − 0.015×26 = 0.61 → clamped to 0.70
        """
        w, notes = layer_7_freshness_decay(2000)
        assert w == pytest.approx(config.FRESHNESS_FLOOR)
        assert any("below floor" in n for n in notes)

    def test_no_pub_year_default(self) -> None:
        """No publication year → default 0.85 + WARN."""
        w, notes = layer_7_freshness_decay(None)
        assert w == pytest.approx(config.FRESHNESS_DEFAULT_WEIGHT)
        assert w == pytest.approx(0.85)
        assert any("No publication year" in n for n in notes)

    def test_constants_from_config(self) -> None:
        """Freshness constants come from config."""
        assert config.FRESHNESS_DECAY_RATE == 0.015
        assert config.FRESHNESS_FLOOR == 0.70
        assert config.FRESHNESS_REFERENCE_YEAR == 2026
        assert config.FRESHNESS_DEFAULT_WEIGHT == 0.85
