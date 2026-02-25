"""Tests for ALG-E2 Natural Recovery Trajectory.

Covers:
    E2a: Recovery parameter loading (context matching, defaults)
    E2b: Stretched exponential R(t) curve (Formula E2b-EQ1)
    E2c: MC sampling with uncertainty (r_∞ noise, τ_R lognormal)
    θ_natural trajectory computation
    Gate E-G2: R(t) valid range, monotonicity
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_e_temporal.nadir_estimator import NadirEstimate, NadirScenario
from crci.algorithm.chain_e_temporal.recovery_trajectory import (
    RecoveryParams,
    RecoveryTrajectory,
    _compute_recovery_curve,
    _load_recovery_params,
    _sample_recovery_draws,
    _validate_gate_e_g2,
    compute_recovery_trajectory,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_nadir(n_nodes=3, theta_nadir=None, theta_base=None):
    if theta_nadir is None:
        theta_nadir = np.array([-0.5, -0.8, -0.3])
    if theta_base is None:
        theta_base = np.zeros(len(theta_nadir))
    return NadirEstimate(
        theta_nadir=theta_nadir,
        estimation_scenario=NadirScenario.DURING_TX,
        confidence=0.9,
        delta_t_since_treatment=0.0,
        theta_base=theta_base,
        n_nodes=len(theta_nadir),
    )


# ═══════════════════════════════════════════════════════════════
#  Test E2a: Parameter Loading
# ═══════════════════════════════════════════════════════════════


class TestParameterLoading:
    """Test recovery parameter context matching."""

    def test_known_context(self):
        params = _load_recovery_params("breast_chemo")
        assert params.r_infinity == 0.75
        assert params.tau_r == 8.0
        assert params.gamma_r == 0.8

    def test_unknown_context_falls_back(self):
        params = _load_recovery_params("unknown_context")
        assert params.r_infinity == config.RECOVERY_R_INFINITY_DEFAULT
        assert params.tau_r == config.RECOVERY_TAU_R_MONTHS_DEFAULT

    def test_none_context_falls_back(self):
        params = _load_recovery_params(None)
        assert params.r_infinity == config.RECOVERY_R_INFINITY_DEFAULT

    def test_custom_params_override(self):
        params = _load_recovery_params(
            "breast_chemo",  # would be 0.75
            custom_params={"r_infinity": 0.9, "tau_r": 5.0, "gamma_r": 1.0},
        )
        assert params.r_infinity == 0.9
        assert params.tau_r == 5.0
        assert params.gamma_r == 1.0


# ═══════════════════════════════════════════════════════════════
#  Test E2b: Recovery Curve
# ═══════════════════════════════════════════════════════════════


class TestRecoveryCurve:
    """Test stretched exponential R(t) computation."""

    def test_r_at_zero(self):
        """R(0) = 0."""
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.array([0.0])
        r = _compute_recovery_curve(params, t)
        assert r[0] == 0.0

    def test_r_monotonically_increasing(self):
        """R(t) should be non-decreasing."""
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(37, dtype=float)
        r = _compute_recovery_curve(params, t)
        assert np.all(np.diff(r) >= 0)

    def test_r_bounded_by_r_infinity(self):
        """R(t) ≤ r_∞ for all t."""
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(100, dtype=float)
        r = _compute_recovery_curve(params, t)
        assert np.all(r <= params.r_infinity + 1e-10)

    def test_r_at_tau_with_gamma_1(self):
        """R(τ) = r_∞ · (1 − 1/e) when γ=1.

        R(8) = 0.7 · (1 - exp(-1)) ≈ 0.7 · 0.6321 ≈ 0.4425
        """
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=1.0)
        t = np.array([8.0])
        r = _compute_recovery_curve(params, t)
        expected = 0.7 * (1.0 - np.exp(-1.0))
        assert abs(r[0] - expected) < 1e-10

    def test_formula_exact(self):
        """Hand-computed R(t) = r_∞ · (1 − exp(−(t/τ)^γ)).

        t=4, r_∞=0.7, τ=8, γ=0.8
        exponent = (4/8)^0.8 = 0.5^0.8 = 0.5743
        R = 0.7 · (1 - exp(-0.5743)) = 0.7 · (1 - 0.5631) = 0.7 · 0.4369 ≈ 0.3058
        """
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.array([4.0])
        r = _compute_recovery_curve(params, t)
        exponent = (4.0 / 8.0) ** 0.8
        expected = 0.7 * (1.0 - np.exp(-exponent))
        assert abs(r[0] - expected) < 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test E2c: MC Sampling
# ═══════════════════════════════════════════════════════════════


class TestMCSampling:
    """Test MC recovery trajectory sampling."""

    def test_shape(self):
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(37, dtype=float)
        rng = np.random.default_rng(42)
        R_draws = _sample_recovery_draws(params, t, 100, rng)
        assert R_draws.shape == (100, 37)

    def test_r_draws_nonnegative(self):
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(37, dtype=float)
        rng = np.random.default_rng(42)
        R_draws = _sample_recovery_draws(params, t, 1000, rng)
        assert np.all(R_draws >= -0.01)  # small tolerance

    def test_r_draws_reproducible(self):
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(10, dtype=float)
        R1 = _sample_recovery_draws(params, t, 50, np.random.default_rng(99))
        R2 = _sample_recovery_draws(params, t, 50, np.random.default_rng(99))
        np.testing.assert_array_equal(R1, R2)

    def test_mean_r_close_to_deterministic(self):
        """Mean of MC draws should approximate deterministic R(t)."""
        params = RecoveryParams(r_infinity=0.7, tau_r=8.0, gamma_r=0.8)
        t = np.arange(37, dtype=float)
        R_det = _compute_recovery_curve(params, t)
        rng = np.random.default_rng(42)
        R_draws = _sample_recovery_draws(params, t, 5000, rng)
        R_mean = np.mean(R_draws, axis=0)
        # Should be close (within ~2 SE of mean)
        np.testing.assert_allclose(R_mean, R_det, atol=0.05)


# ═══════════════════════════════════════════════════════════════
#  Test Gate E-G2
# ═══════════════════════════════════════════════════════════════


class TestGateEG2:
    """Test Gate E-G2 validation."""

    def _make_trajectory(self, R_mean=None, theta_natural=None):
        if R_mean is None:
            R_mean = np.linspace(0, 0.7, 37)
        if theta_natural is None:
            theta_natural = np.zeros((3, len(R_mean)))
        return RecoveryTrajectory(
            theta_natural=theta_natural,
            R_draws=np.zeros((10, len(R_mean))),
            R_mean=R_mean,
            recovery_params=RecoveryParams(0.7, 8.0, 0.8),
            T_horizons=[3, 6, 12, 24],
            n_timepoints=len(R_mean),
        )

    def test_passes_valid(self):
        traj = self._make_trajectory()
        _validate_gate_e_g2(traj)  # should not raise

    def test_fails_negative_r(self):
        R_mean = np.linspace(0, 0.7, 37)
        R_mean[5] = -0.5  # violate
        traj = self._make_trajectory(R_mean=R_mean)
        with pytest.raises(GateViolation, match="E-G2"):
            _validate_gate_e_g2(traj)

    def test_fails_nonfinite_theta(self):
        theta = np.zeros((3, 37))
        theta[1, 10] = float('nan')
        traj = self._make_trajectory(theta_natural=theta)
        with pytest.raises(GateViolation, match="E-G2"):
            _validate_gate_e_g2(traj)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_recovery_trajectory
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full E2 pipeline tests."""

    def test_basic_trajectory(self):
        nadir = _make_nadir()
        result = compute_recovery_trajectory(
            nadir, context_key="breast_chemo", n_draws=100, seed=42,
        )
        assert result.gate_e_g2_passed
        assert result.n_timepoints == config.E_MAX_HORIZON_MONTHS + 1
        assert result.theta_natural.shape == (3, result.n_timepoints)
        assert result.R_draws.shape == (100, result.n_timepoints)

    def test_trajectory_starts_at_nadir(self):
        """θ_natural(0) = θ_nadir."""
        nadir = _make_nadir(theta_nadir=np.array([-0.5, -0.8]))
        result = compute_recovery_trajectory(nadir, n_draws=50, seed=42)
        np.testing.assert_allclose(
            result.theta_natural[:, 0],
            nadir.theta_nadir,
            atol=1e-10,
        )

    def test_trajectory_improves_toward_base(self):
        """θ_natural(t) should move from nadir toward baseline."""
        nadir = _make_nadir(
            theta_nadir=np.array([-1.0]),
            theta_base=np.array([0.0]),
        )
        result = compute_recovery_trajectory(nadir, n_draws=50, seed=42)
        # At t=0: θ = -1.0 (nadir)
        # At t=36: θ should be closer to 0.0 (baseline)
        assert result.theta_natural[0, -1] > result.theta_natural[0, 0]

    def test_custom_recovery_params(self):
        nadir = _make_nadir()
        result = compute_recovery_trajectory(
            nadir,
            custom_recovery_params={"r_infinity": 0.9, "tau_r": 4.0, "gamma_r": 1.0},
            n_draws=50,
            seed=42,
        )
        assert result.recovery_params.r_infinity == 0.9
        assert result.recovery_params.tau_r == 4.0

    def test_uses_config_constants(self):
        assert config.E2_R_INFINITY_NOISE_SD == 0.10
        assert config.E2_TAU_R_LOG_NOISE_SD == 0.20
        assert config.E_MAX_HORIZON_MONTHS == 36
        assert config.E_PREDICTION_HORIZONS == [3, 6, 12, 24]
