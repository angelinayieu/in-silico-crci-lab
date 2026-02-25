"""Tests for ALG-E1 Nadir Estimator.

Covers:
    E1a: Treatment timeline classification (DURING_TX, EARLY_POST, LATE_POST)
    E1b: Nadir back-estimation from current state + recovery fraction
    E1c: Context-based nadir from population data
    Gate E-G1: θ_nadir finite, scenario classified, confidence > 0
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_e_temporal.nadir_estimator import (
    NadirEstimate,
    NadirScenario,
    _back_estimate_nadir,
    _classify_timeline,
    _compute_recovery_fraction_at_dt,
    _context_based_nadir,
    _validate_gate_e_g1,
    estimate_nadir,
)
from crci.algorithm.chain_c_posterior.modifier_application import PatientState


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_patient_state(n_nodes=5, theta_hat=None):
    if theta_hat is None:
        theta_hat = np.array([0.3, -0.5, 0.1, -0.2, 0.4])
    n = len(theta_hat)
    return PatientState(
        theta_hat=theta_hat,
        Sigma_post=np.eye(n) * 0.1,
        Lambda_post=np.eye(n) * 10.0,
        B_eff=np.zeros((n, n)),
    )


# ═══════════════════════════════════════════════════════════════
#  Test E1a: Timeline Classification
# ═══════════════════════════════════════════════════════════════


class TestTimelineClassification:
    """Test treatment timeline scenario assignment."""

    def test_during_tx_when_none(self):
        """Unknown treatment end → DURING_TX."""
        scenario, dt = _classify_timeline(None)
        assert scenario == NadirScenario.DURING_TX
        assert dt == 0.0

    def test_during_tx_when_zero(self):
        """Δt = 0 → DURING_TX."""
        scenario, dt = _classify_timeline(0.0)
        assert scenario == NadirScenario.DURING_TX
        assert dt == 0.0

    def test_during_tx_when_negative(self):
        """Negative Δt → DURING_TX."""
        scenario, dt = _classify_timeline(-1.0)
        assert scenario == NadirScenario.DURING_TX
        assert dt == 0.0

    def test_early_post(self):
        """3 months post → EARLY_POST."""
        scenario, dt = _classify_timeline(3.0)
        assert scenario == NadirScenario.EARLY_POST
        assert dt == 3.0

    def test_early_post_boundary(self):
        """Just under 6 months → still EARLY_POST."""
        scenario, dt = _classify_timeline(5.9)
        assert scenario == NadirScenario.EARLY_POST

    def test_late_post(self):
        """6 months → LATE_POST."""
        scenario, dt = _classify_timeline(6.0)
        assert scenario == NadirScenario.LATE_POST
        assert dt == 6.0

    def test_late_post_well_past(self):
        """24 months → LATE_POST."""
        scenario, dt = _classify_timeline(24.0)
        assert scenario == NadirScenario.LATE_POST


# ═══════════════════════════════════════════════════════════════
#  Test E1b: Recovery Fraction
# ═══════════════════════════════════════════════════════════════


class TestRecoveryFraction:
    """Test stretched exponential R(t) computation."""

    def test_r_at_zero(self):
        """R(0) = 0."""
        r = _compute_recovery_fraction_at_dt(0.0, 0.7, 8.0, 0.8)
        assert r == 0.0

    def test_r_approaches_r_infinity(self):
        """R(∞) → r_∞."""
        r = _compute_recovery_fraction_at_dt(1000.0, 0.7, 8.0, 0.8)
        assert abs(r - 0.7) < 1e-6

    def test_r_at_tau(self):
        """R(τ_R) should be significant fraction of r_∞.

        At t=τ_R: R = r_∞ · (1 - exp(-1^γ)) = r_∞ · (1 - exp(-1))
        For γ=1: R(τ) = 0.7 · (1 - 0.368) ≈ 0.7 · 0.632 ≈ 0.443
        """
        r = _compute_recovery_fraction_at_dt(8.0, 0.7, 8.0, 1.0)
        expected = 0.7 * (1.0 - np.exp(-1.0))
        assert abs(r - expected) < 1e-10

    def test_gamma_effect(self):
        """Lower γ → faster early recovery.

        At t=2, τ=8: exponent = (2/8)^γ = 0.25^γ
        γ=0.5: 0.25^0.5 = 0.5 → R = r_∞·(1-exp(-0.5)) ≈ 0.7·0.394 = 0.276
        γ=1.0: 0.25^1.0 = 0.25 → R = r_∞·(1-exp(-0.25)) ≈ 0.7·0.221 = 0.155
        Lower γ gives MORE early recovery.
        """
        r_low_gamma = _compute_recovery_fraction_at_dt(2.0, 0.7, 8.0, 0.5)
        r_high_gamma = _compute_recovery_fraction_at_dt(2.0, 0.7, 8.0, 1.0)
        assert r_low_gamma > r_high_gamma


# ═══════════════════════════════════════════════════════════════
#  Test E1b: Back-Estimation
# ═══════════════════════════════════════════════════════════════


class TestBackEstimation:
    """Test E1b nadir back-estimation formula."""

    def test_back_estimation_formula(self):
        """Hand-computed back-estimation.

        θ_current = [0.3, -0.2], θ_base = [0.0, 0.0], R(Δt) = 0.5
        θ_nadir = (θ_current - θ_base·R) / (1-R)
                = ([0.3, -0.2] - [0, 0]) / 0.5
                = [0.6, -0.4]
        """
        theta_current = np.array([0.3, -0.2])
        theta_base = np.array([0.0, 0.0])
        r = 0.5
        result = _back_estimate_nadir(theta_current, theta_base, r)
        expected = np.array([0.6, -0.4])
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_with_nonzero_baseline(self):
        """With actual pre-treatment baseline.

        θ_current = [0.5], θ_base = [1.0], R = 0.4
        θ_nadir = (0.5 - 1.0·0.4) / (1-0.4) = 0.1/0.6 ≈ 0.167
        """
        theta_current = np.array([0.5])
        theta_base = np.array([1.0])
        r = 0.4
        result = _back_estimate_nadir(theta_current, theta_base, r)
        expected = np.array([(0.5 - 0.4) / 0.6])
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_zero_recovery_returns_current(self):
        """R = 0 → θ_nadir = θ_current (no recovery yet)."""
        theta = np.array([0.3, -0.5])
        result = _back_estimate_nadir(theta, np.zeros(2), 0.0)
        np.testing.assert_allclose(result, theta, atol=1e-10)


# ═══════════════════════════════════════════════════════════════
#  Test E1c: Context-Based Nadir
# ═══════════════════════════════════════════════════════════════


class TestContextBasedNadir:
    """Test E1c context-based nadir estimation."""

    def test_context_nadir_formula(self):
        """θ_nadir = μ_context − δ_treatment."""
        mu = np.array([0.0, 0.0, 0.0])
        delta = np.array([0.5, 0.3, 0.8])
        result = _context_based_nadir(mu, delta)
        expected = np.array([-0.5, -0.3, -0.8])
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_scalar_delta_treatment(self):
        """Scalar δ_treatment applied uniformly."""
        mu = np.array([0.1, 0.2])
        result = _context_based_nadir(mu, 0.5)
        expected = np.array([-0.4, -0.3])
        np.testing.assert_allclose(result, expected, atol=1e-10)


# ═══════════════════════════════════════════════════════════════
#  Test Gate E-G1
# ═══════════════════════════════════════════════════════════════


class TestGateEG1:
    """Test Gate E-G1 validation."""

    def test_passes_valid(self):
        nadir = NadirEstimate(
            theta_nadir=np.array([0.1, -0.3]),
            estimation_scenario=NadirScenario.DURING_TX,
            confidence=0.9,
            delta_t_since_treatment=0.0,
            theta_base=np.zeros(2),
            n_nodes=2,
        )
        _validate_gate_e_g1(nadir)  # should not raise

    def test_fails_nan_theta(self):
        nadir = NadirEstimate(
            theta_nadir=np.array([float('nan'), -0.3]),
            estimation_scenario=NadirScenario.DURING_TX,
            confidence=0.9,
            delta_t_since_treatment=0.0,
            theta_base=np.zeros(2),
            n_nodes=2,
        )
        with pytest.raises(GateViolation, match="E-G1"):
            _validate_gate_e_g1(nadir)

    def test_fails_zero_confidence(self):
        nadir = NadirEstimate(
            theta_nadir=np.array([0.1]),
            estimation_scenario=NadirScenario.LATE_POST,
            confidence=0.0,
            delta_t_since_treatment=12.0,
            theta_base=np.zeros(1),
            n_nodes=1,
        )
        with pytest.raises(GateViolation, match="E-G1"):
            _validate_gate_e_g1(nadir)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full estimate_nadir
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full E1 pipeline tests."""

    def test_during_tx(self):
        """DURING_TX: nadir = current state."""
        ps = _make_patient_state()
        result = estimate_nadir(ps, treatment_end_months_ago=None)
        assert result.estimation_scenario == NadirScenario.DURING_TX
        np.testing.assert_allclose(result.theta_nadir, ps.theta_hat)
        assert result.confidence == config.E1_CONFIDENCE_DURING_TX

    def test_early_post(self):
        """EARLY_POST: back-estimation."""
        ps = _make_patient_state()
        result = estimate_nadir(
            ps,
            treatment_end_months_ago=3.0,
            recovery_params={"r_infinity": 0.7, "tau_r": 8.0, "gamma_r": 0.8},
        )
        assert result.estimation_scenario == NadirScenario.EARLY_POST
        assert result.confidence == config.E1_CONFIDENCE_EARLY_POST
        # Nadir should be more extreme than current state
        # (back-estimation undoes partial recovery)
        assert result.delta_t_since_treatment == 3.0

    def test_late_post(self):
        """LATE_POST: context-based."""
        ps = _make_patient_state()
        result = estimate_nadir(
            ps,
            treatment_end_months_ago=12.0,
            delta_treatment=0.5,
        )
        assert result.estimation_scenario == NadirScenario.LATE_POST
        assert result.confidence == config.E1_CONFIDENCE_LATE_POST
        # θ_nadir = θ_base - δ = 0 - 0.5 = -0.5 (all nodes)
        expected = np.zeros(5) - 0.5
        np.testing.assert_allclose(result.theta_nadir, expected, atol=1e-10)

    def test_early_post_switches_to_context_when_r_high(self):
        """If R(Δt) ≥ 0.8, EARLY_POST switches to context-based."""
        ps = _make_patient_state()
        # Large Δt with fast recovery → R will be high
        result = estimate_nadir(
            ps,
            treatment_end_months_ago=5.9,  # just under 6 → EARLY_POST
            recovery_params={"r_infinity": 0.99, "tau_r": 1.0, "gamma_r": 1.0},
            delta_treatment=0.3,
        )
        # R(5.9) with τ=1 → R ≈ 0.99 · (1-exp(-5.9)) ≈ 0.99·0.997 ≈ 0.987
        # R > 0.8 → switches to context-based → lower confidence
        assert result.confidence == config.E1_CONFIDENCE_LATE_POST

    def test_custom_theta_base(self):
        """Pre-treatment baseline provided → used for estimation."""
        theta = np.array([0.5, -0.3, 0.2])
        ps = _make_patient_state(theta_hat=theta)
        theta_base = np.array([1.0, 0.5, 0.8])

        result = estimate_nadir(
            ps,
            treatment_end_months_ago=3.0,
            theta_base=theta_base,
            recovery_params={"r_infinity": 0.7, "tau_r": 8.0, "gamma_r": 0.8},
        )
        assert result.estimation_scenario == NadirScenario.EARLY_POST
        np.testing.assert_allclose(result.theta_base, theta_base)

    def test_uses_config_constants(self):
        """Verify E1 constants come from config."""
        assert config.E1_EARLY_POST_THRESHOLD_MONTHS == 6.0
        assert config.E1_BACK_ESTIMATION_R_LIMIT == 0.8
        assert config.E1_CONFIDENCE_DURING_TX == 0.90
        assert config.E1_CONFIDENCE_EARLY_POST == 0.70
        assert config.E1_CONFIDENCE_LATE_POST == 0.50
