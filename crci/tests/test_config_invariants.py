"""
Component: Test — Config Invariants
Purpose: Enforce structural invariants on shared/config.py constants.
         Catches duplicate semantic constants, broken weight sums,
         invalid floor/ceiling ordering, and negative floors.

Reads: crci.shared.config (all module-level constants)
Writes: Nothing (test-only)
"""
from __future__ import annotations

import pytest

from crci.shared import config


# ═══════════════════════════════════════════════════════════════
#  Weight dictionaries must sum to 1.0
# ═══════════════════════════════════════════════════════════════

class TestWeightSums:
    """Dictionaries that represent convex-combination weights must sum to 1."""

    def test_scope_weights_sum_to_one(self) -> None:
        total = sum(config.SCOPE_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"SCOPE_WEIGHTS sum={total}, expected 1.0"

    def test_aps_weights_sum_to_one(self) -> None:
        total = sum(config.APS_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"APS_WEIGHTS sum={total}, expected 1.0"


# ═══════════════════════════════════════════════════════════════
#  Floors ≤ defaults ≤ ceilings
# ═══════════════════════════════════════════════════════════════

class TestFloorCeilingOrdering:
    """Floor/ceiling pairs must be ordered sensibly."""

    def test_sigma_sq_structural(self) -> None:
        assert config.SIGMA_SQ_STRUCTURAL_DEFAULT <= config.SIGMA_SQ_STRUCTURAL_CEILING

    def test_p_inclusion_bounds(self) -> None:
        assert 0.0 <= config.P_INCLUSION_MIN <= config.P_INCLUSION_ADJ_CAP <= 1.0

    def test_min_sigma_floor_below_max_cap(self) -> None:
        assert config.MIN_SIGMA_FLOOR < config.MAX_SIGMA_CAP

    def test_freshness_floor_positive(self) -> None:
        assert 0.0 < config.FRESHNESS_FLOOR <= 1.0

    def test_scope_floor_positive(self) -> None:
        assert 0.0 < config.SCOPE_FLOOR <= 1.0

    def test_temporal_weight_floor_positive(self) -> None:
        assert config.TEMPORAL_WEIGHT_FLOOR > 0.0

    def test_d2_single_below_bundle_ceiling(self) -> None:
        assert config.D2_CEILING_SINGLE_SD <= config.D2_CEILING_BUNDLE_SD

    def test_coherence_z_thresholds_ordered(self) -> None:
        assert (
            config.COHERENCE_Z_PASS
            < config.COHERENCE_Z_MONITOR
            < config.COHERENCE_Z_ALARM
        )

    def test_coherence_se_inflation_ordered(self) -> None:
        assert (
            config.COHERENCE_SE_INFLATION_MONITOR
            < config.COHERENCE_SE_INFLATION_INVESTIGATE
            < config.COHERENCE_SE_INFLATION_ALARM
        )

    def test_c4_modifier_clamp_ordered(self) -> None:
        assert config.C4_MODIFIER_INDIVIDUAL_LOW < config.C4_MODIFIER_INDIVIDUAL_HIGH
        assert config.C4_MODIFIER_CUMULATIVE_LOW < config.C4_MODIFIER_CUMULATIVE_HIGH

    def test_pathway_activation_thresholds_ordered(self) -> None:
        # Sensitive threshold is lower (more permissive) than default
        assert (
            config.C4_PATHWAY_ACTIVATION_THRESHOLD_SENSITIVE
            < config.C4_PATHWAY_ACTIVATION_THRESHOLD_DEFAULT
        )

    def test_pub_bias_se_inflation_ordered(self) -> None:
        assert (
            config.PUB_BIAS_SE_INFLATION_LOW
            <= config.PUB_BIAS_SE_INFLATION_MODERATE
            <= config.PUB_BIAS_SE_INFLATION_HIGH
        )


# ═══════════════════════════════════════════════════════════════
#  No negative floors or weights
# ═══════════════════════════════════════════════════════════════

class TestNonNegative:
    """Floors, weights, and multipliers must be non-negative."""

    @pytest.mark.parametrize(
        "name",
        [
            "ED_QUALITY_WEIGHT_HIGH",
            "ED_QUALITY_WEIGHT_MODERATE",
            "ED_QUALITY_WEIGHT_LOW",
            "ED_QUALITY_WEIGHT_VERY_LOW",
            "MIN_PATHWAY_EVIDENCE_DENSITY",
            "MIN_EDGE_COVERAGE_FOR_DS",
            "FRESHNESS_FLOOR",
            "SCOPE_FLOOR",
            "TEMPORAL_WEIGHT_FLOOR",
        ],
    )
    def test_non_negative(self, name: str) -> None:
        value = getattr(config, name)
        assert value >= 0.0, f"{name}={value} must be non-negative"


# ═══════════════════════════════════════════════════════════════
#  Duplicate / alias consistency
# ═══════════════════════════════════════════════════════════════

class TestAliasConsistency:
    """Aliased constants must always agree with their canonical source."""

    def test_or_to_d_aliases_or_to_smd(self) -> None:
        assert config.CONVERSION_OR_TO_D_FACTOR == config.CONVERSION_OR_TO_SMD_FACTOR

    def test_tb_ci_z_aliases_se_from_ci_z(self) -> None:
        assert config.TB_CI_TO_SE_Z_MULTIPLIER == config.SE_FROM_CI_Z_MULTIPLIER

    def test_ed_quality_weights_dict_matches_scalars(self) -> None:
        assert config.ED_QUALITY_WEIGHTS["HIGH"] == config.ED_QUALITY_WEIGHT_HIGH
        assert config.ED_QUALITY_WEIGHTS["MODERATE"] == config.ED_QUALITY_WEIGHT_MODERATE
        assert config.ED_QUALITY_WEIGHTS["LOW"] == config.ED_QUALITY_WEIGHT_LOW
        assert config.ED_QUALITY_WEIGHTS["VERY_LOW"] == config.ED_QUALITY_WEIGHT_VERY_LOW


# ═══════════════════════════════════════════════════════════════
#  ED quality weights are monotonically decreasing
# ═══════════════════════════════════════════════════════════════

class TestEDQualityWeightsOrdering:
    """Higher quality grade → higher weight credit."""

    def test_quality_tier_ordering(self) -> None:
        assert (
            config.ED_QUALITY_WEIGHT_HIGH
            > config.ED_QUALITY_WEIGHT_MODERATE
            > config.ED_QUALITY_WEIGHT_LOW
            > config.ED_QUALITY_WEIGHT_VERY_LOW
            > 0.0
        )


# ═══════════════════════════════════════════════════════════════
#  GRADE/design multipliers are monotonically increasing (more penalty)
# ═══════════════════════════════════════════════════════════════

class TestMultiplierOrdering:
    """Higher SE penalty for lower quality / weaker designs."""

    def test_grade_multipliers_ordered(self) -> None:
        gm = config.GRADE_MULTIPLIERS
        assert gm["HIGH"] <= gm["MODERATE"] <= gm["LOW"] <= gm["VERY_LOW"]

    def test_scale_multipliers_ordered(self) -> None:
        sm = config.SCALE_MULTIPLIERS
        assert (
            sm["validated_cancer"]
            <= sm["used_cancer"]
            <= sm["general_population"]
            <= sm["known_somatic_confound"]
        )

    def test_design_multipliers_rct_is_best(self) -> None:
        dm = config.DESIGN_MULTIPLIERS
        assert dm["large_rct"] <= dm["small_rct_default"]
        assert dm["large_rct"] <= dm["well_adjusted_cohort"]
        assert dm["expert_opinion"] >= dm["large_rct"]
