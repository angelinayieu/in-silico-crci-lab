"""
Tests for crci/extraction/heterogeneity/se_eff_assembly.py

Formula-dense file: tests cover the worked example from the spec,
edge cases, Gate P3-G1 enforcement, and config constant verification.

Formulas tested: P3-8 (final SE_eff assembly), P3-G1 (gate)
"""
from __future__ import annotations

import math

import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import (
    GateViolation,
    HarmonizedClaim,
    LayeredSEResult,
)
from crci.shared.models.enums import EffectScale, HarmonizationStatusInMem, SESource
from crci.extraction.p3_heterogeneity.se_eff_assembly import (
    SEEffInput,
    compute_se_eff,
    compute_se_eff_for_claim,
)


class TestWorkedExample:
    """Spec worked example (SYS_EX lines ~1080-1100).

    Input: β=0.35, SE=0.12, Large RCT, cancer-validated, GRADE High,
           10 days ago, pub 2023, w_scope=0.80, k=3, I²=30%
    L1: m_design = 1.0
    L2: max(w_scope, 0.3) = 0.80
    L3: I²=30% < 50% → τ²=0
    L4: m_scale = 1.0 (validated_cancer)
    L5: m_grade = 1.0 (HIGH)
    L6: w(10) = e^{−0.5} ≈ 0.607
    L7: w_fresh = 1 − 0.015×3 = 0.955
    numerator² = (0.12 × 1.0 × 1.0 × 1.0)² + 0.25 + 0 = 0.2644
    SE_eff = √0.2644 / (0.80 × 0.955) = 0.514 / 0.764 ≈ 0.67
    """

    def test_worked_example_exact(self) -> None:
        """SE_eff ≈ 0.67 as per spec worked example."""
        inp = SEEffInput(
            ler_id="test_worked",
            se_raw=0.12,
            study_design="large_rct",
            n_total=500,
            w_scope=0.80,
            # k=3 context for heterogeneity, but I²=30% < 50% → τ²=0
            # We provide 3 nearly-identical studies to get low I²
            betas=[0.34, 0.35, 0.36],
            ses=[0.12, 0.12, 0.12],
            validation_status="validated_cancer",
            grade_level="HIGH",
            days_since_measurement=10.0,
            is_trait=False,
            pub_year=2023,
        )
        result = compute_se_eff(inp)

        # Verify layer multipliers
        assert result.layer_multipliers["L1_design"] == pytest.approx(1.0)
        assert result.layer_multipliers["L2_scope"] == pytest.approx(0.80)
        assert result.layer_multipliers["L4_scale"] == pytest.approx(1.0)
        assert result.layer_multipliers["L5_grade"] == pytest.approx(1.0)

        # L6: temporal weight
        expected_w_temporal = math.exp(-config.TEMPORAL_DECAY_RATE * 10.0)
        assert result.layer_multipliers["L6_temporal"] == pytest.approx(
            expected_w_temporal, rel=1e-4
        )

        # L7: freshness
        expected_w_fresh = 1.0 - config.FRESHNESS_DECAY_RATE * 3.0
        assert result.layer_multipliers["L7_freshness"] == pytest.approx(
            expected_w_fresh, rel=1e-6
        )

        # Formula P3-8: SE_eff computation
        # numerator = sqrt((0.12*1.0*1.0*1.0)^2 + 0.25 + 0)
        # With nearly-identical studies, I² < 50% so τ²=0
        se_product = 0.12 * 1.0 * 1.0 * 1.0
        numerator_sq = se_product**2 + config.SIGMA_SQ_STRUCTURAL_DEFAULT
        numerator = math.sqrt(numerator_sq)
        denominator = 0.80 * expected_w_fresh

        expected_se_eff = numerator / denominator
        assert result.se_effective == pytest.approx(expected_se_eff, rel=1e-4)

        # Spec says ≈ 0.67
        assert result.se_effective == pytest.approx(0.67, abs=0.02)

        # Gate P3-G1: SE_eff ≥ SE_raw
        assert result.se_effective >= inp.se_raw

    def test_worked_example_numerator_arithmetic(self) -> None:
        """Verify numerator² = (0.12×1.0×1.0×1.0)² + 0.25 = 0.2644."""
        se_product = 0.12 * 1.0 * 1.0 * 1.0
        numerator_sq = se_product**2 + config.SIGMA_SQ_STRUCTURAL_DEFAULT
        # 0.0144 + 0.25 = 0.2644
        assert numerator_sq == pytest.approx(0.2644, rel=1e-4)


class TestGateP3G1:
    """Gate P3-G1: SE_eff ≥ SE_raw (calibration only inflates)."""

    def test_gate_passes_normally(self) -> None:
        """Normal case: SE_eff > SE_raw due to σ²_struct."""
        inp = SEEffInput(
            ler_id="test_gate_pass",
            se_raw=0.10,
            study_design="large_rct",
            n_total=500,
            w_scope=1.0,
            betas=[],
            ses=[],
            validation_status="validated_cancer",
            grade_level="HIGH",
            days_since_measurement=0.0,
            is_trait=False,
            pub_year=config.FRESHNESS_REFERENCE_YEAR,
        )
        result = compute_se_eff(inp)
        assert result.se_effective >= inp.se_raw

    def test_gate_always_satisfied_due_to_sigma_struct(self) -> None:
        """σ²_struct = 0.25 ensures SE_eff always > SE_raw.

        Even with all multipliers = 1.0 and all weights = 1.0:
        SE_eff = sqrt(SE² + 0.25) / 1.0 ≥ SE
        since sqrt(SE² + 0.25) > SE for any finite SE.
        """
        for se_raw in [0.01, 0.10, 0.50, 1.0, 5.0]:
            inp = SEEffInput(
                ler_id=f"test_se_{se_raw}",
                se_raw=se_raw,
                study_design="large_rct",
                n_total=500,
                w_scope=1.0,
                betas=[],
                ses=[],
                validation_status="validated_cancer",
                grade_level="HIGH",
                days_since_measurement=0.0,
                is_trait=False,
                pub_year=config.FRESHNESS_REFERENCE_YEAR,
            )
            result = compute_se_eff(inp)
            assert result.se_effective >= se_raw


class TestTemporalExclusion:
    """L6 temporal exclusion (>90 days) raises ValueError."""

    def test_excluded_record(self) -> None:
        """91 days → ValueError."""
        inp = SEEffInput(
            ler_id="test_excluded",
            se_raw=0.12,
            study_design="large_rct",
            days_since_measurement=91.0,
        )
        with pytest.raises(ValueError, match="temporal exclusion"):
            compute_se_eff(inp)

    def test_boundary_not_excluded(self) -> None:
        """90 days → NOT excluded (boundary case)."""
        inp = SEEffInput(
            ler_id="test_boundary",
            se_raw=0.12,
            study_design="large_rct",
            days_since_measurement=90.0,
            pub_year=2026,
        )
        result = compute_se_eff(inp)
        assert result.se_effective > 0


class TestHighHeterogeneity:
    """When I² ≥ 50%, τ² is added to SE²."""

    def test_tau_added_when_i_squared_high(self) -> None:
        """Divergent studies → I² ≥ 50% → τ² added to numerator."""
        inp = SEEffInput(
            ler_id="test_high_het",
            se_raw=0.12,
            study_design="large_rct",
            n_total=500,
            w_scope=1.0,
            betas=[0.1, 0.5, 1.0, 2.0],
            ses=[0.05, 0.05, 0.05, 0.05],
            validation_status="validated_cancer",
            grade_level="HIGH",
            days_since_measurement=0.0,
            pub_year=config.FRESHNESS_REFERENCE_YEAR,
        )
        result = compute_se_eff(inp)

        # Should have higher SE_eff than without τ²
        assert result.layer_multipliers["L3_i_squared"] >= 50.0
        assert result.layer_multipliers["L3_tau_squared"] > 0.0


class TestLayerMultiplierEffects:
    """Verify that layer multipliers increase SE_eff."""

    def _base_input(self) -> SEEffInput:
        """Base case: all layers neutral."""
        return SEEffInput(
            ler_id="test_base",
            se_raw=0.12,
            study_design="large_rct",
            n_total=500,
            w_scope=1.0,
            betas=[],
            ses=[],
            validation_status="validated_cancer",
            grade_level="HIGH",
            days_since_measurement=0.0,
            pub_year=config.FRESHNESS_REFERENCE_YEAR,
        )

    def test_worse_design_increases_se(self) -> None:
        """Weaker study design → higher SE_eff."""
        base = self._base_input()
        result_base = compute_se_eff(base)

        worse = self._base_input()
        worse.study_design = "cross_sectional_unadjusted"
        result_worse = compute_se_eff(worse)

        assert result_worse.se_effective > result_base.se_effective

    def test_worse_grade_increases_se(self) -> None:
        """Lower GRADE → higher SE_eff."""
        base = self._base_input()
        result_base = compute_se_eff(base)

        worse = self._base_input()
        worse.grade_level = "VERY_LOW"
        result_worse = compute_se_eff(worse)

        assert result_worse.se_effective > result_base.se_effective

    def test_lower_scope_increases_se(self) -> None:
        """Lower scope match → higher SE_eff."""
        base = self._base_input()
        result_base = compute_se_eff(base)

        worse = self._base_input()
        worse.w_scope = 0.3
        result_worse = compute_se_eff(worse)

        assert result_worse.se_effective > result_base.se_effective

    def test_older_pub_increases_se(self) -> None:
        """Older publication → higher SE_eff."""
        base = self._base_input()
        result_base = compute_se_eff(base)

        worse = self._base_input()
        worse.pub_year = 2000
        result_worse = compute_se_eff(worse)

        assert result_worse.se_effective > result_base.se_effective


class TestComputeSeEffForClaim:
    """Test the convenience wrapper with HarmonizedClaim."""

    def test_from_claim(self) -> None:
        """HarmonizedClaim wrapper produces valid LayeredSEResult."""
        claim = HarmonizedClaim(
            ler_id="claim_001",
            edge_relation_id="edge_001",
            profile_id="profile_001",
            study_id="study_001",
            harmonized_beta=0.35,
            harmonized_se=0.12,
            harmonized_scale=EffectScale.SD_SD,
            harmonization_status=HarmonizationStatusInMem.FULL,
            se_source=SESource.SE_DIRECT,
            n_effect=500,
        )
        result = compute_se_eff_for_claim(
            claim,
            study_design="large_rct",
            w_scope=0.80,
            validation_status="validated_cancer",
            grade_level="HIGH",
            days_since_measurement=10.0,
            pub_year=2023,
        )
        assert isinstance(result, LayeredSEResult)
        assert result.ler_id == "claim_001"
        assert result.se_base == 0.12
        assert result.se_effective >= 0.12

    def test_from_claim_no_se_raises(self) -> None:
        """HarmonizedClaim with no SE → ValueError."""
        claim = HarmonizedClaim(
            ler_id="claim_no_se",
            edge_relation_id="edge_001",
            profile_id="profile_001",
            study_id="study_001",
            harmonized_beta=0.35,
            harmonized_se=None,
            harmonized_scale=EffectScale.SD_SD,
            harmonization_status=HarmonizationStatusInMem.FULL,
        )
        with pytest.raises(ValueError, match="no harmonized_se"):
            compute_se_eff_for_claim(claim, study_design="large_rct")


class TestConfigConstants:
    """Verify all formula parameters come from config (not hardcoded)."""

    def test_sigma_sq_structural(self) -> None:
        assert config.SIGMA_SQ_STRUCTURAL_DEFAULT == 0.25

    def test_scope_floor(self) -> None:
        assert config.SCOPE_FLOOR == 0.3

    def test_heterogeneity_threshold(self) -> None:
        assert config.HETEROGENEITY_MODERATE_THRESHOLD == 50.0

    def test_temporal_constants(self) -> None:
        assert config.TEMPORAL_DECAY_RATE == 0.05
        assert config.TEMPORAL_EXCLUSION_DAYS == 90
        assert config.TEMPORAL_WEIGHT_FLOOR == 0.01

    def test_freshness_constants(self) -> None:
        assert config.FRESHNESS_DECAY_RATE == 0.015
        assert config.FRESHNESS_FLOOR == 0.70
        assert config.FRESHNESS_REFERENCE_YEAR == 2025
        assert config.FRESHNESS_DEFAULT_WEIGHT == 0.85
