"""Tests for S2: Trajectory Builder in report_assembler.

Covers:
    - Empirical percentile computation from MC draws
    - Day conversion from time steps
    - Status quo and intervention scenario generation
    - numpy-to-float conversion
    - Hand-computed expected values
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.algorithm.chain_e_temporal.recovery_trajectory import (
    RecoveryParams,
    RecoveryTrajectory,
)
from crci.algorithm.chain_e_temporal.intervention_overlay import (
    InterventionTrajectory,
    OverlayResult,
)
from crci.algorithm.chain_e_temporal.uncertainty_counterfactual import (
    UncertaintyResult,
)
from crci.runtime.report_assembler import _build_trajectories


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_recovery(
    n_nodes: int = 3,
    n_tp: int = 5,
    n_draws: int = 100,
    seed: int = 42,
) -> RecoveryTrajectory:
    """Build a minimal RecoveryTrajectory for testing."""
    rng = np.random.default_rng(seed)

    # Recovery fraction: R(t) grows from 0 to ~0.7 over time
    t = np.arange(n_tp, dtype=float)
    R_mean = 0.7 * (1 - np.exp(-t / 3.0))

    # MC draws: add noise around R_mean
    R_draws = np.clip(
        R_mean[np.newaxis, :] + rng.normal(0, 0.05, size=(n_draws, n_tp)),
        0.0, 1.0,
    )

    # theta_natural: nadir + delta * R_mean per node
    nadirs = np.array([-1.0, -0.5, -0.8])[:n_nodes]
    deltas = np.array([0.8, 0.4, 0.6])[:n_nodes]
    theta_natural = np.zeros((n_nodes, n_tp))
    for i in range(n_nodes):
        theta_natural[i, :] = nadirs[i] + deltas[i] * R_mean

    return RecoveryTrajectory(
        theta_natural=theta_natural,
        R_draws=R_draws,
        R_mean=R_mean,
        recovery_params=RecoveryParams(r_infinity=0.7, tau_r=3.0, gamma_r=1.0),
        T_horizons=[3, 6, 12, 24],
        n_timepoints=n_tp,
        gate_e_g2_passed=True,
    )


def _make_overlay(
    recovery: RecoveryTrajectory,
) -> OverlayResult:
    """Build a minimal OverlayResult with one intervention."""
    n_nodes, n_tp = recovery.theta_natural.shape
    K_a = np.ones(n_tp) * 0.8  # flat kernel
    delta_aging = np.zeros(n_tp)
    delta_C = 0.3

    theta_intervention = recovery.theta_natural.copy()
    for i in range(n_nodes):
        theta_intervention[i, :] += delta_C * K_a + delta_aging

    return OverlayResult(
        intervention_trajectories={
            "exercise": InterventionTrajectory(
                intervention_id="exercise",
                theta_intervention=theta_intervention,
                K_a=K_a,
                delta_aging=delta_aging,
                delta_C=delta_C,
            ),
        },
        aging_projection=delta_aging,
        n_interventions=1,
        n_timepoints=n_tp,
        gate_e_g3_passed=True,
    )


def _make_uncertainty(n_tp: int = 5) -> UncertaintyResult:
    """Build minimal UncertaintyResult."""
    t = np.arange(n_tp, dtype=float)
    var_theta_t = 0.1 + 0.01 * t + 0.005 * t**2

    return UncertaintyResult(
        var_theta_t=var_theta_t,
        var_theta_0=0.1,
        ite_summaries={},
        clinical_metrics={},
        n_interventions=0,
        n_timepoints=n_tp,
        horizons_months=[3, 6, 12, 24],
        gate_e_g4_passed=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestTrajectoryBuilder:

    def test_status_quo_scenario_present(self):
        """Should produce at least one trajectory with scenario_id='status_quo'."""
        recovery = _make_recovery()
        result = _build_trajectories(recovery, None, None)
        assert len(result) >= 1
        assert result[0].scenario_id == "status_quo"

    def test_intervention_scenario_present(self):
        """Should produce intervention trajectory when overlay provided."""
        recovery = _make_recovery()
        overlay = _make_overlay(recovery)
        result = _build_trajectories(recovery, overlay, None)
        assert len(result) == 2  # status_quo + exercise
        ids = {t.scenario_id for t in result}
        assert "status_quo" in ids
        assert "exercise" in ids

    def test_day_conversion(self):
        """Day at time step t should be t * TRAJECTORY_DAYS_PER_MONTH."""
        recovery = _make_recovery(n_tp=5)
        result = _build_trajectories(recovery, None, None)
        sq = result[0]
        points = sq.node_trajectories[0].points
        for t, pt in enumerate(points):
            assert pt.day == t * config.TRAJECTORY_DAYS_PER_MONTH

    def test_empirical_percentiles_hand_computed(self):
        """Verify percentiles match hand computation for known draws."""
        n_draws = 1000
        n_tp = 3
        n_nodes = 1

        rng = np.random.default_rng(123)
        # Simple draws: R = [0, 0.5, 0.7] mean with uniform noise ±0.1
        R_mean = np.array([0.0, 0.5, 0.7])
        noise = rng.uniform(-0.1, 0.1, size=(n_draws, n_tp))
        R_draws = np.clip(R_mean + noise, 0.0, 1.0)

        nadir = -1.0
        delta = 1.0
        theta_natural = np.array([[nadir + delta * R_mean[t] for t in range(n_tp)]])

        recovery = RecoveryTrajectory(
            theta_natural=theta_natural,
            R_draws=R_draws,
            R_mean=R_mean,
            recovery_params=RecoveryParams(r_infinity=0.7, tau_r=3.0, gamma_r=1.0),
            T_horizons=[3],
            n_timepoints=n_tp,
        )

        result = _build_trajectories(recovery, None, None)
        pts = result[0].node_trajectories[0].points

        # At t=0: R_draws[:, 0] ~ Uniform(-0.1, 0.1) clipped to [0, 1]
        # theta_draws = -1.0 + 1.0 * R_draws[:, 0]
        expected_draws_t0 = nadir + delta * R_draws[:, 0]
        expected_p10_t0 = float(np.percentile(expected_draws_t0, 10))
        expected_p90_t0 = float(np.percentile(expected_draws_t0, 90))

        assert abs(pts[0].z_p10 - expected_p10_t0) < 0.01
        assert abs(pts[0].z_p90 - expected_p90_t0) < 0.01

        # At t=2: R_draws[:, 2] ~ 0.7 + Uniform(-0.1, 0.1)
        expected_draws_t2 = nadir + delta * R_draws[:, 2]
        expected_p10_t2 = float(np.percentile(expected_draws_t2, 10))
        expected_p90_t2 = float(np.percentile(expected_draws_t2, 90))

        assert abs(pts[2].z_p10 - expected_p10_t2) < 0.01
        assert abs(pts[2].z_p90 - expected_p90_t2) < 0.01

    def test_intervention_shifts_trajectory_upward(self):
        """Intervention trajectory means should exceed status quo means."""
        recovery = _make_recovery(n_draws=500)
        overlay = _make_overlay(recovery)
        result = _build_trajectories(recovery, overlay, None)

        sq_pts = result[0].node_trajectories[0].points
        int_pts = result[1].node_trajectories[0].points

        # Intervention adds delta_C * K_a = 0.3 * 0.8 = 0.24 per time step
        for sq_pt, int_pt in zip(sq_pts, int_pts):
            assert int_pt.z_mean > sq_pt.z_mean

    def test_numpy_to_float_conversion(self):
        """All numeric outputs should be native Python floats, not numpy types."""
        recovery = _make_recovery()
        result = _build_trajectories(recovery, None, None)
        for traj in result:
            for nt in traj.node_trajectories:
                for pt in nt.points:
                    assert isinstance(pt.z_mean, float), f"z_mean is {type(pt.z_mean)}"
                    assert isinstance(pt.z_sd, float), f"z_sd is {type(pt.z_sd)}"
                    assert isinstance(pt.z_p10, float), f"z_p10 is {type(pt.z_p10)}"
                    assert isinstance(pt.z_p90, float), f"z_p90 is {type(pt.z_p90)}"

    def test_horizon_days(self):
        """horizon_days should be (n_timepoints - 1) * TRAJECTORY_DAYS_PER_MONTH."""
        recovery = _make_recovery(n_tp=7)
        result = _build_trajectories(recovery, None, None)
        expected = (7 - 1) * config.TRAJECTORY_DAYS_PER_MONTH
        assert result[0].horizon_days == expected

    def test_node_count_matches(self):
        """Each trajectory should have n_nodes NodeTrajectory objects."""
        recovery = _make_recovery(n_nodes=3, n_tp=4)
        result = _build_trajectories(recovery, None, None)
        assert len(result[0].node_trajectories) == 3

    def test_bands_ordered(self):
        """z_p10 <= z_mean <= z_p90 for all points."""
        recovery = _make_recovery(n_draws=500)
        result = _build_trajectories(recovery, None, None)
        for traj in result:
            for nt in traj.node_trajectories:
                for pt in nt.points:
                    assert pt.z_p10 <= pt.z_mean + 1e-10
                    assert pt.z_mean <= pt.z_p90 + 1e-10
