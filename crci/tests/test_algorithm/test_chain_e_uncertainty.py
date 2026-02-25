"""Tests for ALG-E4 Uncertainty Growth + Counterfactuals.

Covers:
    E4a: Uncertainty growth model (Formula E-6)
    E4b: Individual Treatment Effect (Formula E-5)
    E4c: Clinical metrics (ARR, RRR, NNT)
    Gate E-G4: Var monotonic, ITE finite, NNT > 0
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_e_temporal.uncertainty_counterfactual import (
    ClinicalMetrics,
    ITESummary,
    NNTStrength,
    UncertaintyResult,
    _compute_clinical_metrics,
    _compute_ite_at_horizon,
    _compute_uncertainty_growth,
    _validate_gate_e_g4,
    compute_uncertainty_counterfactual,
)
from crci.algorithm.chain_e_temporal.intervention_overlay import (
    InterventionTrajectory,
    OverlayResult,
)
from crci.algorithm.chain_e_temporal.recovery_trajectory import (
    RecoveryParams,
    RecoveryTrajectory,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_recovery(n_nodes=3, T=37):
    """Recovery with θ_natural linearly improving."""
    theta_natural = np.zeros((n_nodes, T))
    for i in range(n_nodes):
        theta_natural[i, :] = np.linspace(-0.5, -0.1, T)
    return RecoveryTrajectory(
        theta_natural=theta_natural,
        R_draws=np.zeros((10, T)),
        R_mean=np.linspace(0, 0.7, T),
        recovery_params=RecoveryParams(0.7, 8.0, 0.8),
        T_horizons=[3, 6, 12, 24],
        n_timepoints=T,
    )


def _make_overlay(n_nodes=3, T=37, delta_C=0.2, aids=None):
    """Create an OverlayResult with intervention trajectories."""
    if aids is None:
        aids = ["ex_1"]
    trajectories = {}
    delta_aging = np.linspace(0, -0.03, T)
    for aid in aids:
        theta_interv = np.zeros((n_nodes, T))
        for i in range(n_nodes):
            # θ_intervention = θ_natural + delta_C (improved)
            theta_interv[i, :] = np.linspace(-0.5, -0.1, T) + delta_C
        trajectories[aid] = InterventionTrajectory(
            intervention_id=aid,
            theta_intervention=theta_interv,
            K_a=np.ones(T) * 0.8,
            delta_aging=delta_aging,
            delta_C=delta_C,
        )
    return OverlayResult(
        intervention_trajectories=trajectories,
        aging_projection=delta_aging,
        n_interventions=len(aids),
        n_timepoints=T,
        gate_e_g3_passed=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Test E4a: Uncertainty Growth Model
# ═══════════════════════════════════════════════════════════════


class TestUncertaintyGrowth:
    """Test growing prediction uncertainty."""

    def test_var_at_zero(self):
        """Var(0) = Var(θ₀)."""
        t = np.array([0.0])
        var = _compute_uncertainty_growth(0.1, t)
        assert abs(var[0] - 0.1) < 1e-10

    def test_formula_hand_computed(self):
        """Hand-computed Var(θ(t)).

        Var(θ₀) = 0.1, t = 12
        Var(12) = 0.1 + 0.01×12 + 0.005×144 = 0.1 + 0.12 + 0.72 = 0.94
        """
        t = np.array([12.0])
        var = _compute_uncertainty_growth(0.1, t)
        expected = 0.1 + config.E4_VAR_LINEAR_COEFF * 12.0 + config.E4_VAR_QUADRATIC_COEFF * 144.0
        assert abs(var[0] - expected) < 1e-10

    def test_var_at_3_months(self):
        """Spec says: at 3mo, +0.075 variance.

        Var(3) = Var₀ + 0.01×3 + 0.005×9 = Var₀ + 0.03 + 0.045 = Var₀ + 0.075
        """
        t = np.array([3.0])
        var_0 = 0.0  # isolate growth
        var = _compute_uncertainty_growth(var_0, t)
        expected = config.E4_VAR_LINEAR_COEFF * 3.0 + config.E4_VAR_QUADRATIC_COEFF * 9.0
        assert abs(var[0] - expected) < 1e-10
        assert abs(expected - 0.075) < 1e-10

    def test_var_monotonically_increasing(self):
        """Var(θ(t)) should be monotonically non-decreasing."""
        t = np.arange(37, dtype=float)
        var = _compute_uncertainty_growth(0.1, t)
        assert np.all(np.diff(var) >= 0)

    def test_default_kernel_scale(self):
        """With default kernel scale (1.5×), growth is faster."""
        t = np.array([12.0])
        var_standard = _compute_uncertainty_growth(0.1, t, use_default_kernel_scale=False)
        var_scaled = _compute_uncertainty_growth(0.1, t, use_default_kernel_scale=True)
        assert var_scaled[0] > var_standard[0]
        # Scaled growth = 1.5 × (0.01×12 + 0.005×144) = 1.5 × 0.84 = 1.26
        expected_scaled = 0.1 + 1.5 * (0.01 * 12.0 + 0.005 * 144.0)
        assert abs(var_scaled[0] - expected_scaled) < 1e-10

    def test_var_zero_baseline(self):
        """Even with zero baseline, uncertainty still grows."""
        t = np.array([6.0])
        var = _compute_uncertainty_growth(0.0, t)
        assert var[0] > 0


# ═══════════════════════════════════════════════════════════════
#  Test E4b: Individual Treatment Effect
# ═══════════════════════════════════════════════════════════════


class TestITE:
    """Test ITE computation."""

    def test_ite_positive_when_intervention_helps(self):
        """ITE > 0 when intervention improves cognition."""
        # (3 nodes, 3 timepoints)
        theta_natural = np.array([[-0.5, -0.4, -0.3],
                                   [-0.6, -0.5, -0.4],
                                   [-0.4, -0.3, -0.2]])
        theta_interv = np.array([[-0.3, -0.2, -0.1],
                                  [-0.4, -0.3, -0.2],
                                  [-0.2, -0.1, 0.0]])
        ite = _compute_ite_at_horizon("ex_1", theta_interv, theta_natural, 1, 1)
        assert ite.ite_mean > 0

    def test_ite_zero_identical_trajectories(self):
        """ITE = 0 when trajectories are identical."""
        theta = np.zeros((3, 10))
        ite = _compute_ite_at_horizon("ex_1", theta, theta, 5, 5)
        assert abs(ite.ite_mean) < 1e-10

    def test_ite_formula(self):
        """Hand-computed ITE.

        θ_natural = [-0.5, -0.3], θ_intervention = [-0.2, -0.1] at t=0
        ITE per node = [0.3, 0.2]
        Mean ITE = 0.25
        """
        theta_natural = np.array([[-0.5, -0.3, 0.0],
                                   [-0.3, -0.1, 0.0]])
        theta_interv = np.array([[-0.2, -0.1, 0.0],
                                  [-0.1, 0.0, 0.0]])
        ite = _compute_ite_at_horizon("ex_1", theta_interv, theta_natural, 0, 0)
        expected_mean = np.mean([0.3, 0.2])
        assert abs(ite.ite_mean - expected_mean) < 1e-10

    def test_ite_cri_bounds(self):
        """CrI should bracket the mean."""
        theta_natural = np.zeros((10, 20))
        theta_interv = np.zeros((10, 20))
        # Add varying effect across nodes
        for i in range(10):
            theta_interv[i, :] = 0.1 * (i + 1)
        ite = _compute_ite_at_horizon("ex_1", theta_interv, theta_natural, 10, 10)
        assert ite.ite_cri_lower <= ite.ite_mean <= ite.ite_cri_upper


# ═══════════════════════════════════════════════════════════════
#  Test E4c: Clinical Metrics
# ═══════════════════════════════════════════════════════════════


class TestClinicalMetrics:
    """Test ARR, RRR, NNT computation."""

    def test_arr_positive_when_intervention_reduces_impairment(self):
        """ARR > 0 when intervention reduces impairment fraction."""
        # All nodes impaired naturally, none impaired with intervention
        theta_natural = np.ones((5, 10)) * -1.0  # all < -0.5
        theta_interv = np.ones((5, 10)) * 0.0    # all > -0.5
        cm = _compute_clinical_metrics("ex_1", theta_interv, theta_natural, 5, 5)
        assert cm.p_impaired_natural == 1.0
        assert cm.p_impaired_intervention == 0.0
        assert cm.arr == 1.0

    def test_arr_zero_same_trajectories(self):
        """ARR = 0 when trajectories identical."""
        theta = np.ones((5, 10)) * -1.0
        cm = _compute_clinical_metrics("ex_1", theta, theta, 5, 5)
        assert cm.arr == 0.0
        assert cm.nnt is None  # undefined when ARR = 0

    def test_rrr_formula(self):
        """RRR = ARR / P_natural.

        P_natural = 0.8, P_intervention = 0.2
        ARR = 0.6, RRR = 0.6/0.8 = 0.75
        """
        # 4 out of 5 nodes impaired naturally
        theta_natural = np.array([[-1.0, -1.0], [-1.0, -1.0], [-1.0, -1.0],
                                   [-1.0, -1.0], [0.0, 0.0]])
        # 1 out of 5 nodes impaired with intervention
        theta_interv = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0],
                                  [-1.0, -1.0], [0.0, 0.0]])
        cm = _compute_clinical_metrics("ex_1", theta_interv, theta_natural, 0, 0)
        assert abs(cm.p_impaired_natural - 0.8) < 1e-10
        assert abs(cm.p_impaired_intervention - 0.2) < 1e-10
        assert abs(cm.arr - 0.6) < 1e-10
        assert cm.rrr is not None
        assert abs(cm.rrr - 0.75) < 1e-10

    def test_nnt_formula(self):
        """NNT = 1 / ARR."""
        # ARR = 0.5 → NNT = 2
        theta_natural = np.array([[-1.0], [-1.0], [0.0], [0.0]])
        theta_interv = np.array([[0.0], [0.0], [0.0], [0.0]])
        cm = _compute_clinical_metrics("ex_1", theta_interv, theta_natural, 0, 0)
        assert abs(cm.arr - 0.5) < 1e-10
        assert cm.nnt is not None
        assert abs(cm.nnt - 2.0) < 1e-10

    def test_nnt_strength_strong(self):
        """NNT < 3 → STRONG."""
        theta_natural = np.array([[-1.0], [-1.0]])
        theta_interv = np.array([[0.0], [0.0]])
        cm = _compute_clinical_metrics("ex_1", theta_interv, theta_natural, 0, 0)
        # ARR = 1.0, NNT = 1.0 → STRONG
        assert cm.nnt_strength == NNTStrength.STRONG

    def test_nnt_strength_moderate(self):
        """NNT 3-10 → MODERATE."""
        # Need ARR = 1/5 = 0.2 → NNT = 5
        # 1 out of 5 nodes: impaired in natural, not in intervention
        theta_natural = np.array([[-1.0], [0.0], [0.0], [0.0], [0.0]])
        theta_interv = np.array([[0.0], [0.0], [0.0], [0.0], [0.0]])
        cm = _compute_clinical_metrics("ex_1", theta_interv, theta_natural, 0, 0)
        assert abs(cm.arr - 0.2) < 1e-10
        assert cm.nnt is not None
        assert abs(cm.nnt - 5.0) < 1e-10
        assert cm.nnt_strength == NNTStrength.MODERATE

    def test_nnt_none_when_no_arr(self):
        """No improvement → NNT undefined."""
        theta = np.ones((3, 5)) * 0.0  # none impaired
        cm = _compute_clinical_metrics("ex_1", theta, theta, 2, 2)
        assert cm.arr == 0.0
        assert cm.nnt is None
        assert cm.nnt_strength is None

    def test_rrr_none_when_no_natural_impairment(self):
        """RRR undefined when P_natural = 0."""
        theta = np.ones((3, 5)) * 0.0  # none impaired
        cm = _compute_clinical_metrics("ex_1", theta, theta, 2, 2)
        assert cm.rrr is None


# ═══════════════════════════════════════════════════════════════
#  Test Gate E-G4
# ═══════════════════════════════════════════════════════════════


class TestGateEG4:
    """Test Gate E-G4 validation."""

    def _make_result(self, var_t=None, ite_mean=0.1, nnt=2.0):
        T = 37
        if var_t is None:
            var_t = np.arange(T, dtype=float) * 0.01 + 0.1
        return UncertaintyResult(
            var_theta_t=var_t,
            var_theta_0=0.1,
            ite_summaries={
                "test": [ITESummary("test", 12, ite_mean, 0.05, 0.15)],
            },
            clinical_metrics={
                "test": [ClinicalMetrics(
                    "test", 12, 0.5, 0.3, 0.2, 0.4, nnt, NNTStrength.STRONG,
                )],
            },
            n_interventions=1,
            n_timepoints=T,
            horizons_months=[3, 6, 12, 24],
        )

    def test_passes_valid(self):
        result = self._make_result()
        _validate_gate_e_g4(result)  # should not raise

    def test_fails_nonmonotonic_var(self):
        var_t = np.arange(37, dtype=float) * 0.01 + 0.1
        var_t[20] = 0.0  # violate monotonicity
        result = self._make_result(var_t=var_t)
        with pytest.raises(GateViolation, match="E-G4"):
            _validate_gate_e_g4(result)

    def test_fails_nonfinite_ite(self):
        result = self._make_result(ite_mean=float('nan'))
        with pytest.raises(GateViolation, match="E-G4"):
            _validate_gate_e_g4(result)

    def test_fails_negative_nnt(self):
        result = self._make_result(nnt=-1.0)
        with pytest.raises(GateViolation, match="E-G4"):
            _validate_gate_e_g4(result)

    def test_passes_nnt_none(self):
        """NNT=None is acceptable (ARR ≤ 0 → NNT undefined)."""
        T = 37
        result = UncertaintyResult(
            var_theta_t=np.arange(T, dtype=float) * 0.01 + 0.1,
            var_theta_0=0.1,
            ite_summaries={"test": [ITESummary("test", 12, 0.1, 0.05, 0.15)]},
            clinical_metrics={
                "test": [ClinicalMetrics("test", 12, 0.3, 0.3, 0.0, None, None, None)],
            },
            n_interventions=1,
            n_timepoints=T,
            horizons_months=[3, 6, 12, 24],
        )
        _validate_gate_e_g4(result)  # should not raise


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_uncertainty_counterfactual
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full E4 pipeline tests."""

    def test_basic_pipeline(self):
        recovery = _make_recovery()
        overlay = _make_overlay()
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.1,
        )
        assert result.gate_e_g4_passed
        assert result.n_interventions == 1
        assert result.n_timepoints == 37
        assert "ex_1" in result.ite_summaries
        assert "ex_1" in result.clinical_metrics

    def test_ite_positive_for_positive_effect(self):
        """Positive ΔC → positive ITE."""
        recovery = _make_recovery()
        overlay = _make_overlay(delta_C=0.5)
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.1,
        )
        for s in result.ite_summaries["ex_1"]:
            assert s.ite_mean > 0

    def test_var_growth_shape(self):
        """Var array has correct shape and grows."""
        recovery = _make_recovery(T=25)
        overlay = _make_overlay(T=25)
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.05,
        )
        assert result.var_theta_t.shape == (25,)
        assert result.var_theta_t[0] < result.var_theta_t[-1]

    def test_multiple_interventions(self):
        recovery = _make_recovery()
        overlay = _make_overlay(aids=["ex_1", "ex_2"])
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.1,
        )
        assert result.n_interventions == 2
        assert "ex_1" in result.ite_summaries
        assert "ex_2" in result.ite_summaries

    def test_horizons_from_config(self):
        """Horizons come from config.E_PREDICTION_HORIZONS."""
        recovery = _make_recovery()
        overlay = _make_overlay()
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.1,
        )
        assert result.horizons_months == config.E_PREDICTION_HORIZONS

    def test_empty_overlay(self):
        """No interventions → empty ITE/metrics but still valid."""
        recovery = _make_recovery()
        overlay = _make_overlay(aids=[])
        result = compute_uncertainty_counterfactual(
            overlay, recovery, var_theta_0=0.1,
        )
        assert result.gate_e_g4_passed
        assert len(result.ite_summaries) == 0


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify E4 constants come from config."""

    def test_var_linear_coeff(self):
        assert config.E4_VAR_LINEAR_COEFF == 0.01

    def test_var_quadratic_coeff(self):
        assert config.E4_VAR_QUADRATIC_COEFF == 0.005

    def test_default_kernel_scale(self):
        assert config.E4_VAR_DEFAULT_KERNEL_SCALE == 1.5

    def test_severity_threshold(self):
        assert config.E4_SEVERITY_THRESHOLD_SD == -0.5

    def test_nnt_strong_threshold(self):
        assert config.E4_NNT_STRONG_THRESHOLD == 3.0

    def test_nnt_moderate_threshold(self):
        assert config.E4_NNT_MODERATE_THRESHOLD == 10.0

    def test_cri_quantiles(self):
        assert config.E4_CRI_LOWER_QUANTILE == 0.025
        assert config.E4_CRI_UPPER_QUANTILE == 0.975
