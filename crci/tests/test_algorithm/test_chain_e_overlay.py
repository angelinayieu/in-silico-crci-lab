"""Tests for ALG-E3 Intervention Temporal Overlay.

Covers:
    E3a: Trapezoidal temporal kernel (onset → build → steady → decay)
    E3b: Accelerated cognitive aging (δ_aging formula)
    E3d: Full trajectory θ(t) = θ_natural + ΔC·K(t) + δ_aging
    Gate E-G3: K∈[0,1], δ_aging≤0, θ finite
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_e_temporal.intervention_overlay import (
    InterventionTrajectory,
    OverlayResult,
    _compute_aging,
    _compute_trapezoidal_kernel,
    _get_kernel_for_intervention,
    _validate_gate_e_g3,
    compute_intervention_overlay,
)
from crci.algorithm.chain_e_temporal.recovery_trajectory import (
    RecoveryParams,
    RecoveryTrajectory,
)
from crci.algorithm.chain_e_temporal.nadir_estimator import NadirEstimate, NadirScenario
from crci.algorithm.chain_d_simulation.effect_propagation import (
    EffectResult,
    InterventionEffects,
)
from crci.algorithm.chain_d_simulation.intervention_loader import (
    InterventionDef,
    InterventionSet,
    TemporalKernel,
)
from crci.algorithm.chain_d_simulation.ranker import (
    InterventionRanking,
    RankingResult,
    SensitivityIndex,
    DoseRecommendation,
    ClaimLevel,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_recovery(n_nodes=3, T=37):
    """Create a simple RecoveryTrajectory."""
    theta_natural = np.zeros((n_nodes, T))
    # Linear recovery from -0.5 to -0.1 across time for each node
    for i in range(n_nodes):
        theta_natural[i, :] = np.linspace(-0.5, -0.1, T)
    R_mean = np.linspace(0, 0.7, T)
    return RecoveryTrajectory(
        theta_natural=theta_natural,
        R_draws=np.zeros((10, T)),
        R_mean=R_mean,
        recovery_params=RecoveryParams(0.7, 8.0, 0.8),
        T_horizons=[3, 6, 12, 24],
        n_timepoints=T,
    )


def _make_effect_result(action_ids, n_draws=100, n_nodes=3):
    """Create an EffectResult with given action IDs."""
    from crci.algorithm.chain_d_simulation.effect_propagation import PropagationMethod
    effects = {}
    for aid in action_ids:
        effects[aid] = InterventionEffects(
            intervention_id=aid,
            delta_theta=np.random.default_rng(42).normal(0, 0.1, (n_draws, n_nodes)),
            delta_C=np.random.default_rng(42).normal(0.2, 0.05, n_draws),
            propagation_methods=[PropagationMethod.DIRECT_RCT] * n_draws,
            ceiling_clipped=np.zeros(n_draws, dtype=bool),
        )
    return EffectResult(
        intervention_effects=effects,
        n_draws=n_draws,
        n_nodes=n_nodes,
        cognitive_node_indices=list(range(n_nodes)),
        cognitive_node_ids=[f"cog_{i}" for i in range(n_nodes)],
        gate_d_g2_passed=True,
    )


def _make_intervention_set(action_ids, kernels=None):
    """Create an InterventionSet."""
    interventions = []
    index = {}
    for i, aid in enumerate(action_ids):
        kernel = kernels.get(aid) if kernels else None
        interventions.append(InterventionDef(
            action_id=aid,
            action_label=f"Label {aid}",
            action_class="exercise",
            dose_type="frequency",
            dose_unit="sessions/week",
            dose_min=1.0,
            dose_max=7.0,
            dose_recommended_start=3.0,
            dose_step=1.0,
            time_cost_min=30.0,
            cognitive_load=0.2,
            logistics_load=0.3,
            overall_burden=0.25,
            adherence_rate_default=0.8,
            evidence_basis="RCT",
            evidence_strength="moderate",
            temporal_kernel=kernel,
        ))
        index[aid] = i
    return InterventionSet(
        interventions=interventions,
        intervention_index=index,
        synergy_records=[],
        synergy_lookup={},
        all_contraindications=[],
    )


def _make_ranking_result(action_ids):
    """Create a RankingResult with given action IDs."""
    rankings = {}
    for i, aid in enumerate(action_ids):
        rankings[aid] = InterventionRanking(
            action_id=aid,
            action_label=f"Label {aid}",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.2,
            mss_burden=0.1,
            safe_a=0.15,
            safe_a_cri_lower=0.05,
            safe_a_cri_upper=0.25,
            rank_a=i + 1,
            p_adhere=0.8,
            safe_b=0.12,
            safe_b_cri_lower=0.04,
            safe_b_cri_upper=0.20,
            rank_b=i + 1,
            adherence_warning=False,
            dose_recommended=3.0,
            dose_conflict=False,
            dose_conflict_ratio=None,
            claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.ones(100) * 0.15,
        )
    return RankingResult(
        intervention_rankings=rankings,
        bundle_rankings={},
        sensitivity_indices=[],
        top_discovery_edges=[],
        dose_recommendations={},
        n_interventions_ranked=len(action_ids),
        n_bundles_ranked=0,
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Test E3a: Trapezoidal Temporal Kernel
# ═══════════════════════════════════════════════════════════════


class TestTrapezoidalKernel:
    """Test trapezoidal kernel computation."""

    def test_kernel_at_zero(self):
        """K(0) = 0 (onset hasn't started yet)."""
        t = np.array([0.0])
        K = _compute_trapezoidal_kernel(t, 4.0, 4.0, 12.0, 26.0)
        assert K[0] == 0.0

    def test_kernel_during_onset_ramp(self):
        """During onset phase, K ramps linearly from 0 to 1.

        onset_weeks=4. At t=0.5 months ≈ 2.17 weeks:
        K = 2.17 / 4.0 ≈ 0.543
        """
        t = np.array([0.5])
        K = _compute_trapezoidal_kernel(t, 4.0, 4.0, 12.0, 26.0)
        t_weeks = 0.5 * config.P7_WEEKS_TO_MONTHS
        expected = t_weeks / 4.0
        assert abs(K[0] - expected) < 1e-10

    def test_kernel_at_steady_state(self):
        """During steady phase, K = 1.0.

        onset=4wk + build=4wk + some steady → plateau at 1.
        At t = (4+4+6)/4.345 months ≈ 3.22 months, should be in steady.
        """
        t_steady_weeks = 4.0 + 4.0 + 6.0  # 14 weeks, mid-steady
        t_months = np.array([t_steady_weeks / config.P7_WEEKS_TO_MONTHS])
        K = _compute_trapezoidal_kernel(t_months, 4.0, 4.0, 12.0, 26.0)
        assert abs(K[0] - 1.0) < 1e-10

    def test_kernel_decay_phase(self):
        """After steady, K decays exponentially.

        Total steady end = (4+4+12) = 20 weeks.
        At t = 30 weeks: dt = 10 weeks after steady end.
        K = exp(-0.693 * 10 / 26) ≈ exp(-0.2665) ≈ 0.766
        """
        t_weeks = 30.0
        t_months = np.array([t_weeks / config.P7_WEEKS_TO_MONTHS])
        K = _compute_trapezoidal_kernel(t_months, 4.0, 4.0, 12.0, 26.0)
        dt = 10.0  # weeks after steady end
        expected = np.exp(-config.E3_DECAY_LN2 * dt / 26.0)
        assert abs(K[0] - expected) < 1e-6

    def test_kernel_bounded_01(self):
        """K(t) ∈ [0, 1] for all t."""
        t = np.arange(100, dtype=float)
        K = _compute_trapezoidal_kernel(t, 4.0, 4.0, 12.0, 26.0)
        assert np.all(K >= 0.0)
        assert np.all(K <= 1.0)

    def test_kernel_negative_time(self):
        """K(t) = 0 for t < 0."""
        t = np.array([-1.0, -5.0])
        K = _compute_trapezoidal_kernel(t, 4.0, 4.0, 12.0, 26.0)
        assert np.all(K == 0.0)

    def test_kernel_zero_onset(self):
        """If onset=0, jump immediately to 1."""
        t = np.array([0.01])  # tiny positive time
        K = _compute_trapezoidal_kernel(t, 0.0, 0.0, 12.0, 26.0)
        assert K[0] == 1.0

    def test_kernel_zero_decay_halflife(self):
        """If decay_half_life=0, K drops to 0 after steady."""
        t_weeks_after_steady = 21.0  # past onset(4)+build(4)+steady(12)=20
        t_months = np.array([t_weeks_after_steady / config.P7_WEEKS_TO_MONTHS])
        K = _compute_trapezoidal_kernel(t_months, 4.0, 4.0, 12.0, 0.0)
        assert K[0] == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test E3a: Kernel for Intervention
# ═══════════════════════════════════════════════════════════════


class TestKernelForIntervention:
    """Test _get_kernel_for_intervention."""

    def test_missing_intervention_returns_flat(self):
        """Unknown intervention → flat kernel (all ones)."""
        iset = _make_intervention_set(["ex_1"])
        t = np.arange(10, dtype=float)
        K = _get_kernel_for_intervention("nonexistent", iset, t)
        np.testing.assert_array_equal(K, np.ones(10))

    def test_no_kernel_uses_defaults(self):
        """InterventionDef with kernel=None → default kernel."""
        iset = _make_intervention_set(["ex_1"])
        t = np.arange(37, dtype=float)
        K = _get_kernel_for_intervention("ex_1", iset, t)
        # Should match default: onset=4, build=4, steady=12, decay=26
        K_expected = _compute_trapezoidal_kernel(t, 4.0, 4.0, 12.0, 26.0)
        np.testing.assert_allclose(K, K_expected)

    def test_with_custom_kernel(self):
        """InterventionDef with TemporalKernel → uses those params."""
        kernel = TemporalKernel(
            kernel_id="k1",
            action_id="ex_1",
            kernel_family="exponential_rise_decay",
            onset_weeks_min=2.0,
            onset_weeks_max=6.0,
            build_weeks=3.0,
            steady_state_weeks_min=8.0,
            steady_state_weeks_max=16.0,
            decay_half_life_weeks=20.0,
            pathway_specific_onset={},
            source_citation="test",
        )
        iset = _make_intervention_set(["ex_1"], kernels={"ex_1": kernel})
        t = np.arange(37, dtype=float)
        K = _get_kernel_for_intervention("ex_1", iset, t)
        # onset = (2+6)/2 = 4, build=3, steady=(8+16)/2=12, decay=20
        K_expected = _compute_trapezoidal_kernel(t, 4.0, 3.0, 12.0, 20.0)
        np.testing.assert_allclose(K, K_expected)


# ═══════════════════════════════════════════════════════════════
#  Test E3b: Accelerated Cognitive Aging
# ═══════════════════════════════════════════════════════════════


class TestAging:
    """Test aging contribution computation."""

    def test_aging_at_zero(self):
        """δ_aging(0) = 0."""
        t = np.array([0.0])
        delta = _compute_aging(t, age=60.0)
        assert delta[0] == 0.0

    def test_aging_formula_hand_computed(self):
        """Hand-computed δ_aging.

        age=60, t=12 months (1 year), treatment_type="standard_chemo" (ACC=1.5)
        age_factor = max(1, (60-50)/10) = max(1, 1.0) = 1.0
        dt_years = 12/12 = 1.0
        δ_aging = -0.02 × 1.0 × 1.5 × 1.0 = -0.03
        """
        t = np.array([12.0])
        delta = _compute_aging(t, age=60.0, treatment_type="standard_chemo")
        expected = -config.E3_BASE_AGING_RATE_SD_PER_YEAR * 1.0 * 1.5 * 1.0
        assert abs(delta[0] - expected) < 1e-10

    def test_aging_increases_with_age(self):
        """Older patients have faster cognitive aging.

        age=70: age_factor = max(1, (70-50)/10) = 2.0
        age=50: age_factor = max(1, (50-50)/10) = max(1, 0) = 1.0
        """
        t = np.array([12.0])
        delta_70 = _compute_aging(t, age=70.0)
        delta_50 = _compute_aging(t, age=50.0)
        # More negative for older
        assert delta_70[0] < delta_50[0]

    def test_aging_always_negative(self):
        """δ_aging ≤ 0 for all positive time."""
        t = np.arange(1, 37, dtype=float)
        delta = _compute_aging(t, age=65.0, treatment_type="anthracycline")
        assert np.all(delta <= 0)

    def test_aging_young_patient_floor(self):
        """age < 50 → age_factor floors at 1.0.

        age=30: (30-50)/10 = -2.0, max(1, -2) = 1.0
        """
        t = np.array([12.0])
        delta_30 = _compute_aging(t, age=30.0)
        delta_50 = _compute_aging(t, age=50.0)
        # Should be equal (both have age_factor=1.0)
        np.testing.assert_allclose(delta_30, delta_50)

    def test_aging_unknown_treatment_uses_default(self):
        """Unknown treatment_type → ACC = E3_ACC_DEFAULT (1.5)."""
        t = np.array([12.0])
        delta_unknown = _compute_aging(t, age=60.0, treatment_type="unknown_tx")
        delta_standard = _compute_aging(t, age=60.0, treatment_type="standard_chemo")
        # Both should use ACC=1.5
        np.testing.assert_allclose(delta_unknown, delta_standard)

    def test_aging_no_chemo_coefficient(self):
        """no_chemotherapy has ACC=1.0 (least aging)."""
        t = np.array([24.0])
        delta = _compute_aging(t, age=60.0, treatment_type="no_chemotherapy")
        # dt_years = 2, age_factor=1.0, ACC=1.0
        expected = -config.E3_BASE_AGING_RATE_SD_PER_YEAR * 1.0 * 1.0 * 2.0
        assert abs(delta[0] - expected) < 1e-10

    def test_aging_anthracycline_coefficient(self):
        """Anthracycline has ACC=2.0 (high aging)."""
        t = np.array([12.0])
        delta = _compute_aging(t, age=60.0, treatment_type="anthracycline")
        expected = -config.E3_BASE_AGING_RATE_SD_PER_YEAR * 1.0 * 2.0 * 1.0
        assert abs(delta[0] - expected) < 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test Gate E-G3
# ═══════════════════════════════════════════════════════════════


class TestGateEG3:
    """Test Gate E-G3 validation."""

    def _make_result(self, K_a=None, delta_aging=None, theta=None):
        T = 37
        if K_a is None:
            K_a = np.ones(T) * 0.5
        if delta_aging is None:
            delta_aging = np.linspace(0, -0.03, T)
        if theta is None:
            theta = np.zeros((3, T))
        traj = InterventionTrajectory(
            intervention_id="test",
            theta_intervention=theta,
            K_a=K_a,
            delta_aging=delta_aging,
            delta_C=0.2,
        )
        return OverlayResult(
            intervention_trajectories={"test": traj},
            aging_projection=delta_aging,
            n_interventions=1,
            n_timepoints=T,
        )

    def test_passes_valid(self):
        result = self._make_result()
        _validate_gate_e_g3(result)  # should not raise

    def test_fails_k_above_one(self):
        K_a = np.ones(37) * 1.5  # violate K > 1
        result = self._make_result(K_a=K_a)
        with pytest.raises(GateViolation, match="E-G3"):
            _validate_gate_e_g3(result)

    def test_fails_k_below_zero(self):
        K_a = np.ones(37) * (-0.5)  # violate K < 0
        result = self._make_result(K_a=K_a)
        with pytest.raises(GateViolation, match="E-G3"):
            _validate_gate_e_g3(result)

    def test_fails_positive_aging(self):
        delta_aging = np.ones(37) * 0.1  # violate δ_aging > 0
        result = self._make_result(delta_aging=delta_aging)
        with pytest.raises(GateViolation, match="E-G3"):
            _validate_gate_e_g3(result)

    def test_fails_nonfinite_theta(self):
        theta = np.zeros((3, 37))
        theta[1, 10] = float('nan')
        result = self._make_result(theta=theta)
        with pytest.raises(GateViolation, match="E-G3"):
            _validate_gate_e_g3(result)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_intervention_overlay
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full E3 pipeline tests."""

    def test_basic_overlay(self):
        """Basic E3 pipeline: 2 interventions, valid output."""
        aids = ["ex_1", "ex_2"]
        recovery = _make_recovery()
        effect = _make_effect_result(aids)
        ranking = _make_ranking_result(aids)
        iset = _make_intervention_set(aids)

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=60.0,
        )
        assert result.gate_e_g3_passed
        assert result.n_interventions == 2
        assert result.n_timepoints == 37
        assert len(result.intervention_trajectories) == 2

    def test_trajectory_shape(self):
        """θ_intervention has shape (n_nodes, T)."""
        aids = ["ex_1"]
        recovery = _make_recovery(n_nodes=4, T=25)
        effect = _make_effect_result(aids, n_nodes=4)
        ranking = _make_ranking_result(aids)
        iset = _make_intervention_set(aids)

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=55.0,
        )
        traj = result.intervention_trajectories["ex_1"]
        assert traj.theta_intervention.shape == (4, 25)
        assert traj.K_a.shape == (25,)
        assert traj.delta_aging.shape == (25,)

    def test_intervention_improves_trajectory(self):
        """Positive ΔC should shift θ upward (improved cognition)."""
        aids = ["ex_1"]
        recovery = _make_recovery()
        # Force a clearly positive mean ΔC
        from crci.algorithm.chain_d_simulation.effect_propagation import PropagationMethod
        effect = EffectResult(
            intervention_effects={
                "ex_1": InterventionEffects(
                    intervention_id="ex_1",
                    delta_theta=np.ones((100, 3)) * 0.3,
                    delta_C=np.ones(100) * 0.3,
                    propagation_methods=[PropagationMethod.DIRECT_RCT] * 100,
                    ceiling_clipped=np.zeros(100, dtype=bool),
                ),
            },
            n_draws=100,
            n_nodes=3,
            cognitive_node_indices=[0, 1, 2],
            cognitive_node_ids=["c0", "c1", "c2"],
            gate_d_g2_passed=True,
        )
        ranking = _make_ranking_result(aids)
        iset = _make_intervention_set(aids)

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=60.0,
        )
        traj = result.intervention_trajectories["ex_1"]
        # θ_intervention should be above θ_natural at mid-timepoints
        # (where K(t) > 0 and ΔC > 0)
        mid = 15  # mid-time
        assert np.all(
            traj.theta_intervention[:, mid] >= recovery.theta_natural[:, mid] - 0.01
        )

    def test_aging_projection_negative(self):
        """Aging projection should be ≤ 0."""
        aids = ["ex_1"]
        recovery = _make_recovery()
        effect = _make_effect_result(aids)
        ranking = _make_ranking_result(aids)
        iset = _make_intervention_set(aids)

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=65.0,
        )
        assert np.all(result.aging_projection <= 0)

    def test_missing_effect_skips_intervention(self):
        """If EffectResult doesn't have an intervention, skip it."""
        recovery = _make_recovery()
        effect = _make_effect_result(["ex_1"])  # only ex_1
        ranking = _make_ranking_result(["ex_1", "ex_2"])  # both
        iset = _make_intervention_set(["ex_1", "ex_2"])

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=60.0,
        )
        # Only ex_1 should appear (ex_2 has no effect data)
        assert "ex_1" in result.intervention_trajectories
        assert "ex_2" not in result.intervention_trajectories
        assert result.n_interventions == 1

    def test_empty_ranking_produces_empty_result(self):
        """No ranked interventions → empty trajectories (but aging still computed)."""
        recovery = _make_recovery()
        effect = _make_effect_result([])
        ranking = _make_ranking_result([])
        iset = _make_intervention_set([])

        result = compute_intervention_overlay(
            recovery, effect, ranking, iset, age=60.0,
        )
        assert result.n_interventions == 0
        assert len(result.intervention_trajectories) == 0
        assert result.gate_e_g3_passed


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify E3 constants come from config."""

    def test_decay_ln2(self):
        assert config.E3_DECAY_LN2 == 0.693

    def test_base_aging_rate(self):
        assert config.E3_BASE_AGING_RATE_SD_PER_YEAR == 0.02

    def test_aging_age_reference(self):
        assert config.E3_AGING_AGE_REFERENCE == 50.0

    def test_aging_age_divisor(self):
        assert config.E3_AGING_AGE_DIVISOR == 10.0

    def test_acc_default(self):
        assert config.E3_ACC_DEFAULT == 1.5

    def test_acc_coefficients_exist(self):
        assert "anthracycline" in config.E3_ACC_COEFFICIENTS
        assert "standard_chemo" in config.E3_ACC_COEFFICIENTS
        assert "no_chemotherapy" in config.E3_ACC_COEFFICIENTS

    def test_weeks_to_months(self):
        assert config.P7_WEEKS_TO_MONTHS == 4.345
