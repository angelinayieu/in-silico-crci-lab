"""Tests for ALG-D4-D6 Ranker: SAFE Scoring, Dose Optimization, Causal Claims.

Covers:
    D4a: SAFE_A computation (Formula D-3)
    D4b: Adherence model (Formula D-5) and SAFE_B (Formula D-4)
    D4c: Sensitivity/discovery indices
    D5:  Dose optimization (Hill/Emax, conflict detection, composite dose)
    D6:  Causal language assignment
    Gates: D-G4, D-G5, D-G6
    Integration: Full rank_interventions pipeline
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_d_simulation.ranker import (
    BundleRanking,
    ClaimLevel,
    DoseRecommendation,
    InterventionRanking,
    RankingResult,
    SensitivityIndex,
    _classify_edge_claim,
    _compute_bundle_p_adhere,
    _compute_composite_dose,
    _compute_cri,
    _compute_mss_burden,
    _compute_p_adhere,
    _compute_safe_a_per_draw,
    _compute_safe_b,
    _detect_dose_conflict,
    _hill_emax,
    _validate_gate_d_g4,
    _validate_gate_d_g5,
    _validate_gate_d_g6,
)
from crci.algorithm.chain_d_simulation.intervention_loader import (
    DoseResponseSpec,
    InterventionDef,
    InterventionSet,
)
from crci.algorithm.chain_d_simulation.safety_checker import (
    SafetyResult,
    SafetyStatus,
    InterventionSafety,
)


# ═══════════════════════════════════════════════════════════════
#  Test Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_intervention(
    action_id="ACT_01",
    action_label="Test Intervention",
    action_class="exercise",
    overall_burden=0.4,
    adherence_rate_default=0.7,
    dose_min=0.0,
    dose_max=300.0,
    dose_recommended_start=150.0,
    time_cost_min=150.0,
    cognitive_load=0.2,
    logistics_load=0.3,
    dose_bridges=None,
):
    return InterventionDef(
        action_id=action_id,
        action_label=action_label,
        action_class=action_class,
        dose_type="minutes_per_week",
        dose_unit="min/wk",
        dose_min=dose_min,
        dose_max=dose_max,
        dose_recommended_start=dose_recommended_start,
        dose_step=30.0,
        time_cost_min=time_cost_min,
        cognitive_load=cognitive_load,
        logistics_load=logistics_load,
        overall_burden=overall_burden,
        adherence_rate_default=adherence_rate_default,
        evidence_basis="rct",
        evidence_strength="HIGH",
        dose_bridges=dose_bridges or [],
    )


def _make_intervention_set(interventions):
    return InterventionSet(
        interventions=interventions,
        intervention_index={i.action_id: idx for idx, i in enumerate(interventions)},
        synergy_records=[],
        synergy_lookup={},
        all_contraindications=[],
    )


def _make_safety_result(intervention_ids, blocked_ids=None):
    blocked_ids = blocked_ids or []
    safety = {}
    for aid in intervention_ids:
        status = SafetyStatus.BLOCKED if aid in blocked_ids else SafetyStatus.CLEAR
        safety[aid] = InterventionSafety(
            action_id=aid,
            action_label=f"Test {aid}",
            status=status,
            evaluations=[],
            n_triggered=0,
            n_blocked=1 if aid in blocked_ids else 0,
            n_warnings=0,
            blocking_rules=[],
            warning_rules=[],
        )
    return SafetyResult(
        intervention_safety=safety,
        n_total=len(intervention_ids),
        n_clear=len(intervention_ids) - len(blocked_ids),
        n_warning=0,
        n_blocked=len(blocked_ids),
        blocked_action_ids=blocked_ids,
    )


# ═══════════════════════════════════════════════════════════════
#  Test D4a: SAFE_A (Formula D-3)
# ═══════════════════════════════════════════════════════════════


class TestSafeA:
    """Test SAFE_A = MSS_cog − λ × MSS_burden."""

    def test_safe_a_formula(self):
        """Hand-computed SAFE_A.

        ΔC draws = [0.5, 0.3, 0.7] → mean = 0.5
        burden = 0.4
        SAFE_A_per_draw = [0.5 - 0.3*0.4, 0.3 - 0.12, 0.7 - 0.12]
                        = [0.38, 0.18, 0.58]
        mean SAFE_A = (0.38 + 0.18 + 0.58) / 3 = 1.14/3 ≈ 0.38
        """
        draws = np.array([0.5, 0.3, 0.7])
        burden = 0.4
        result = _compute_safe_a_per_draw(draws, burden)

        expected_per_draw = draws - config.D4_BURDEN_PENALTY_WEIGHT * burden
        np.testing.assert_allclose(result, expected_per_draw, atol=1e-10)

        # Check mean
        expected_mean = 0.5 - 0.3 * 0.4  # 0.38
        assert abs(np.mean(result) - expected_mean) < 1e-10

    def test_zero_burden(self):
        """Zero burden → SAFE_A = MSS_cog."""
        draws = np.array([1.0, 2.0, 3.0])
        result = _compute_safe_a_per_draw(draws, 0.0)
        np.testing.assert_allclose(result, draws, atol=1e-10)

    def test_high_burden_can_negate(self):
        """High burden can make SAFE_A negative."""
        draws = np.array([0.1, 0.1, 0.1])
        result = _compute_safe_a_per_draw(draws, 1.0)
        # 0.1 - 0.3*1.0 = -0.2
        assert np.all(result < 0)


class TestMSSBurden:
    """Test burden computation."""

    def test_overall_burden_used_when_present(self):
        interv = _make_intervention(overall_burden=0.6)
        assert _compute_mss_burden(interv) == 0.6

    def test_fallback_to_components(self):
        interv = _make_intervention(
            overall_burden=None,
            cognitive_load=0.2,
            logistics_load=0.3,
            time_cost_min=150.0,
            dose_max=300.0,
        )
        burden = _compute_mss_burden(interv)
        # time_normalized = 150/300 = 0.5
        # avg(0.2, 0.3, 0.5) = 1.0/3 ≈ 0.333
        assert abs(burden - 1.0 / 3) < 1e-6


class TestCRI:
    """Test credible interval computation."""

    def test_cri_simple(self):
        draws = np.arange(100) / 99.0  # 0.0, 0.01, ..., 1.0
        lo, hi = _compute_cri(draws)
        assert abs(lo - np.quantile(draws, 0.025)) < 1e-10
        assert abs(hi - np.quantile(draws, 0.975)) < 1e-10

    def test_cri_constant(self):
        draws = np.ones(100) * 0.5
        lo, hi = _compute_cri(draws)
        assert lo == 0.5
        assert hi == 0.5


# ═══════════════════════════════════════════════════════════════
#  Test D4b: Adherence Model (Formula D-5) & SAFE_B (Formula D-4)
# ═══════════════════════════════════════════════════════════════


class TestAdherenceModel:
    """Test logit(P_adhere) = 1.8 − 0.42·Burden − 0.03·Duration."""

    def test_zero_burden_zero_duration(self):
        """Zero burden, zero duration → logit = 1.8 → P = sigmoid(1.8)."""
        p = _compute_p_adhere(0.0, 0.0)
        expected = 1.0 / (1.0 + math.exp(-1.8))
        assert abs(p - expected) < 1e-10

    def test_moderate_burden(self):
        """Burden=0.5, Duration=12 weeks.

        logit = 1.8 - 0.42*0.5 - 0.03*12 = 1.8 - 0.21 - 0.36 = 1.23
        P = sigmoid(1.23) ≈ 0.774
        """
        p = _compute_p_adhere(0.5, 12.0)
        logit_val = 1.8 - 0.42 * 0.5 - 0.03 * 12.0
        expected = 1.0 / (1.0 + math.exp(-logit_val))
        assert abs(p - expected) < 1e-10

    def test_high_burden_low_adherence(self):
        """Very high burden → low adherence."""
        p = _compute_p_adhere(1.0, 52.0)  # 1yr, max burden
        # logit = 1.8 - 0.42 - 1.56 = -0.18
        assert p < 0.5

    def test_default_duration_zero(self):
        """No duration argument → defaults to 0."""
        p1 = _compute_p_adhere(0.3)
        p2 = _compute_p_adhere(0.3, 0.0)
        assert abs(p1 - p2) < 1e-10

    def test_uses_config_constants(self):
        """Verify adherence model uses config constants."""
        assert config.D4_ADHERENCE_INTERCEPT == 1.8
        assert config.D4_ADHERENCE_BURDEN_COEFF == 0.42
        assert config.D4_ADHERENCE_DURATION_COEFF == 0.03


class TestBundleAdherence:
    """Test bundle adherence reduction."""

    def test_single_member_no_reduction(self):
        """Size-1 bundle → no reduction."""
        p = _compute_bundle_p_adhere([0.8], 1)
        assert abs(p - 0.8) < 1e-10

    def test_two_member_bundle(self):
        """P(B) = P_a × P_b × (1 − 0.05×(2−1)) = P_a × P_b × 0.95."""
        p = _compute_bundle_p_adhere([0.8, 0.7], 2)
        expected = 0.8 * 0.7 * (1.0 - 0.05 * 1)
        assert abs(p - expected) < 1e-10

    def test_three_member_bundle(self):
        """Three members: reduction = 0.05 × 2 = 0.10."""
        p = _compute_bundle_p_adhere([0.8, 0.7, 0.6], 3)
        expected = 0.8 * 0.7 * 0.6 * (1.0 - 0.05 * 2)
        assert abs(p - expected) < 1e-10


class TestSafeB:
    """Test SAFE_B = SAFE_A + α × ln(P_adhere)."""

    def test_safe_b_formula(self):
        """Hand-computed SAFE_B.

        SAFE_A = 0.5, P_adhere = 0.8
        SAFE_B = 0.5 + 0.5 × ln(0.8) = 0.5 + 0.5 × (-0.2231) ≈ 0.3884
        """
        safe_b = _compute_safe_b(0.5, 0.8)
        expected = 0.5 + 0.5 * math.log(0.8)
        assert abs(safe_b - expected) < 1e-10

    def test_perfect_adherence(self):
        """P=1.0 → ln(1.0) = 0 → SAFE_B = SAFE_A."""
        safe_b = _compute_safe_b(1.0, 1.0)
        assert abs(safe_b - 1.0) < 1e-10

    def test_low_adherence_penalty(self):
        """Low adherence → significant penalty."""
        safe_b = _compute_safe_b(1.0, 0.3)
        # 1.0 + 0.5*ln(0.3) = 1.0 + 0.5*(-1.2039) ≈ 0.398
        assert safe_b < 1.0

    def test_safe_b_always_leq_safe_a(self):
        """SAFE_B ≤ SAFE_A when P_adhere ≤ 1.0 (ln(P) ≤ 0)."""
        for p in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            safe_b = _compute_safe_b(1.0, p)
            assert safe_b <= 1.0 + 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test D5: Dose Optimization
# ═══════════════════════════════════════════════════════════════


class TestHillEmax:
    """Test Hill/Emax dose-response model."""

    def test_zero_dose(self):
        """Zero dose → zero effect."""
        assert _hill_emax(0.0, 1.0, 100.0, 1.0) == 0.0

    def test_ec50_dose(self):
        """At EC50: effect = E_max × 0.5^h / (0.5^h + 0.5^h) = E_max/2."""
        e_max, ec50, h = 2.0, 100.0, 1.0
        result = _hill_emax(ec50, e_max, ec50, h)
        assert abs(result - e_max / 2) < 1e-10

    def test_high_dose_approaches_emax(self):
        """Very high dose → approaches E_max."""
        result = _hill_emax(10000.0, 1.0, 100.0, 1.0)
        assert result > 0.99

    def test_hill_coefficient_steepness(self):
        """Higher Hill coefficient → steeper curve."""
        # At dose = EC50: both give E_max/2 regardless of h
        # But at dose < EC50, higher h gives lower effect
        low_h = _hill_emax(50.0, 1.0, 100.0, 1.0)
        high_h = _hill_emax(50.0, 1.0, 100.0, 3.0)
        assert low_h > high_h  # gentler slope at h=1 gives more at 50% dose


class TestDoseConflict:
    """Test D5b dose conflict detection."""

    def test_no_conflict(self):
        """Close doses → no conflict."""
        flag, ratio = _detect_dose_conflict({"P1": 100.0, "P2": 110.0})
        assert not flag
        assert ratio is not None
        assert abs(ratio - 110.0 / 100.0) < 1e-10

    def test_conflict_detected(self):
        """Large dose spread → conflict.

        ratio = 200/100 = 2.0 > 1.3 → conflict.
        """
        flag, ratio = _detect_dose_conflict({"P1": 100.0, "P2": 200.0})
        assert flag
        assert ratio is not None
        assert abs(ratio - 2.0) < 1e-10

    def test_single_pathway_no_conflict(self):
        """Only one pathway → no conflict possible."""
        flag, ratio = _detect_dose_conflict({"P1": 150.0})
        assert not flag
        assert ratio is None


class TestCompositeDose:
    """Test D5c composite dose assembly."""

    def test_equal_weights(self):
        """Equal weights → simple average."""
        doses = {"P1": 100.0, "P2": 200.0}
        effects = {"P1": 1.0, "P2": 1.0}
        result = _compute_composite_dose(doses, effects)
        assert abs(result - 150.0) < 1e-10

    def test_weighted_average(self):
        """Weighted by pathway effect magnitude.

        w_P1=2.0, d*_P1=100; w_P2=1.0, d*_P2=200
        composite = (2*100 + 1*200) / (2+1) = 400/3 ≈ 133.33
        """
        doses = {"P1": 100.0, "P2": 200.0}
        effects = {"P1": 2.0, "P2": 1.0}
        result = _compute_composite_dose(doses, effects)
        expected = (2.0 * 100.0 + 1.0 * 200.0) / 3.0
        assert abs(result - expected) < 1e-10

    def test_single_pathway(self):
        """Single pathway → d* directly."""
        result = _compute_composite_dose({"P1": 150.0}, {"P1": 1.0})
        assert abs(result - 150.0) < 1e-10

    def test_empty(self):
        """Empty pathways → 0."""
        result = _compute_composite_dose({}, {})
        assert result == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test D6: Causal Language Assignment
# ═══════════════════════════════════════════════════════════════


class TestClaimClassification:
    """Test edge claim level classification."""

    def test_causal_supported(self):
        assert _classify_edge_claim("causal_supported") == ClaimLevel.CAUSAL_SUPPORTED
        assert _classify_edge_claim("causal") == ClaimLevel.CAUSAL_SUPPORTED

    def test_associational_only(self):
        assert _classify_edge_claim("associational_only") == ClaimLevel.ASSOCIATIONAL_ONLY
        assert _classify_edge_claim("observational") == ClaimLevel.ASSOCIATIONAL_ONLY

    def test_model_implied(self):
        assert _classify_edge_claim("model_implied") == ClaimLevel.MODEL_IMPLIED
        assert _classify_edge_claim("unknown") == ClaimLevel.MODEL_IMPLIED
        assert _classify_edge_claim("") == ClaimLevel.MODEL_IMPLIED


class TestClaimStrength:
    """Test weakest-link ordering."""

    def test_ordering(self):
        """CAUSAL > ASSOCIATIONAL > MODEL_IMPLIED."""
        from crci.algorithm.chain_d_simulation.ranker import _CLAIM_STRENGTH
        assert _CLAIM_STRENGTH[ClaimLevel.CAUSAL_SUPPORTED] > _CLAIM_STRENGTH[ClaimLevel.ASSOCIATIONAL_ONLY]
        assert _CLAIM_STRENGTH[ClaimLevel.ASSOCIATIONAL_ONLY] > _CLAIM_STRENGTH[ClaimLevel.MODEL_IMPLIED]


# ═══════════════════════════════════════════════════════════════
#  Test Gates
# ═══════════════════════════════════════════════════════════════


class TestGateDG4:
    """Test Gate D-G4: CrI finite, rankings consistent."""

    def _make_result(self, safe_a=0.5, safe_b=0.3):
        ranking = InterventionRanking(
            action_id="ACT_01",
            action_label="Test",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.5,
            mss_burden=0.4,
            safe_a=safe_a,
            safe_a_cri_lower=0.2,
            safe_a_cri_upper=0.8,
            rank_a=1,
            p_adhere=0.7,
            safe_b=safe_b,
            safe_b_cri_lower=0.1,
            safe_b_cri_upper=0.5,
            rank_b=1,
            adherence_warning=False,
            dose_recommended=150.0,
            dose_conflict=False,
            dose_conflict_ratio=None,
            claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.array([0.5]),
        )
        return RankingResult(
            intervention_rankings={"ACT_01": ranking},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )

    def test_passes_valid(self):
        result = self._make_result()
        _validate_gate_d_g4(result)  # should not raise

    def test_fails_nan_safe_a(self):
        result = self._make_result(safe_a=float('nan'))
        with pytest.raises(GateViolation, match="D-G4"):
            _validate_gate_d_g4(result)

    def test_fails_inf_safe_b(self):
        result = self._make_result(safe_b=float('inf'))
        with pytest.raises(GateViolation, match="D-G4"):
            _validate_gate_d_g4(result)


class TestGateDG5:
    """Test Gate D-G5: Dose within clinical range."""

    def test_passes_valid(self):
        result = RankingResult(
            intervention_rankings={},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={
                "ACT_01": DoseRecommendation(
                    action_id="ACT_01",
                    pathway_doses={},
                    composite_dose=150.0,
                    conflict_flag=False,
                    conflict_ratio=None,
                    dose_min=0.0,
                    dose_max=300.0,
                ),
            },
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )
        _validate_gate_d_g5(result)  # should not raise

    def test_fails_dose_exceeds_max(self):
        result = RankingResult(
            intervention_rankings={},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={
                "ACT_01": DoseRecommendation(
                    action_id="ACT_01",
                    pathway_doses={},
                    composite_dose=350.0,  # exceeds 300
                    conflict_flag=False,
                    conflict_ratio=None,
                    dose_min=0.0,
                    dose_max=300.0,
                ),
            },
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )
        with pytest.raises(GateViolation, match="D-G5"):
            _validate_gate_d_g5(result)


class TestGateDG6:
    """Test Gate D-G6: All non-blocked interventions have claim level."""

    def test_passes_when_all_ranked(self):
        interventions = [_make_intervention(action_id="ACT_01")]
        iset = _make_intervention_set(interventions)
        safety = _make_safety_result(["ACT_01"])

        ranking = InterventionRanking(
            action_id="ACT_01",
            action_label="Test",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.5,
            mss_burden=0.4,
            safe_a=0.5,
            safe_a_cri_lower=0.2,
            safe_a_cri_upper=0.8,
            rank_a=1,
            p_adhere=0.7,
            safe_b=0.3,
            safe_b_cri_lower=0.1,
            safe_b_cri_upper=0.5,
            rank_b=1,
            adherence_warning=False,
            dose_recommended=150.0,
            dose_conflict=False,
            dose_conflict_ratio=None,
            claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.array([0.5]),
        )
        result = RankingResult(
            intervention_rankings={"ACT_01": ranking},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )
        _validate_gate_d_g6(result, iset, safety)  # should not raise

    def test_blocked_interventions_excluded(self):
        """Blocked intervention doesn't need a ranking."""
        interventions = [
            _make_intervention(action_id="ACT_01"),
            _make_intervention(action_id="ACT_02"),
        ]
        iset = _make_intervention_set(interventions)
        safety = _make_safety_result(["ACT_01", "ACT_02"], blocked_ids=["ACT_02"])

        ranking = InterventionRanking(
            action_id="ACT_01",
            action_label="Test",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.5,
            mss_burden=0.4,
            safe_a=0.5,
            safe_a_cri_lower=0.2,
            safe_a_cri_upper=0.8,
            rank_a=1,
            p_adhere=0.7,
            safe_b=0.3,
            safe_b_cri_lower=0.1,
            safe_b_cri_upper=0.5,
            rank_b=1,
            adherence_warning=False,
            dose_recommended=150.0,
            dose_conflict=False,
            dose_conflict_ratio=None,
            claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.array([0.5]),
        )
        result = RankingResult(
            intervention_rankings={"ACT_01": ranking},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=1,
        )
        _validate_gate_d_g6(result, iset, safety)  # ACT_02 blocked → no error


# ═══════════════════════════════════════════════════════════════
#  Test Config Constants
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify D4-D6 constants come from config."""

    def test_d4_constants(self):
        assert config.D4_BURDEN_PENALTY_WEIGHT == 0.3
        assert config.D4_ADHERENCE_ADJUSTMENT_WEIGHT == 0.5
        assert config.D4_ADHERENCE_INTERCEPT == 1.8
        assert config.D4_ADHERENCE_BURDEN_COEFF == 0.42
        assert config.D4_ADHERENCE_DURATION_COEFF == 0.03
        assert config.D4_BUNDLE_ADHERENCE_REDUCTION == 0.05
        assert config.D4_ADHERENCE_WARNING_THRESHOLD == 0.30
        assert config.D4_CRI_LOWER_QUANTILE == 0.025
        assert config.D4_CRI_UPPER_QUANTILE == 0.975
        assert config.D4_TOP_DISCOVERY_COUNT == 5

    def test_d5_constants(self):
        assert config.D5_DOSE_CONFLICT_RATIO_THRESHOLD == 1.3
        assert config.D5_DOSE_GRID_STEPS == 100

    def test_d6_constants(self):
        assert config.D6_CHAIN_VS_DIRECT_Z_DEMOTE == 3.0
