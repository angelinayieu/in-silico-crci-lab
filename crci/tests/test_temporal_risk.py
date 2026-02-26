"""
Tests for temporal_risk.py (F4T module).

Per §8.2.15: hand-computable expected values, edge cases, gate violations.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation
from crci.algorithm.chain_f_analytics.temporal_risk import (
    _reconstruct_theta_draws_natural,
    _aggregate_to_domains,
    _compute_risk_curve,
    _compute_risk_reduction,
    classify_crci_vectorized,
    solve_linear_coefficients,
    PredictiveRiskEstimate,
    TemporalRiskCurve,
    TemporalRiskPoint,
    compute_temporal_risk,
)


# ══════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture
def simple_recovery_data():
    """Synthetic recovery data: 3 cognitive nodes, 10 draws, 12 months."""
    n_nodes = 3
    n_draws = 10
    T = 12

    # Linear recovery: R(t) = t / T
    R_mean = np.linspace(0, 1, T)
    R_draws = np.tile(R_mean, (n_draws, 1))

    # Add variability: draws ±0.1 around mean
    np.random.seed(42)
    R_draws += np.random.uniform(-0.1, 0.1, (n_draws, T))
    R_draws = np.clip(R_draws, 0.0, 1.0)

    # theta_natural: starts at nadir, ends at nadir + delta * 1.0
    # Node 0: nadir=-2.0, delta=2.0  → ends at 0.0
    # Node 1: nadir=-1.5, delta=1.0  → ends at -0.5
    # Node 2: nadir=-2.5, delta=2.5  → ends at 0.0
    nadir = np.array([-2.0, -1.5, -2.5])
    delta = np.array([2.0, 1.0, 2.5])

    theta_natural = np.zeros((n_nodes, T))
    for i in range(n_nodes):
        theta_natural[i, :] = nadir[i] + delta[i] * R_mean

    # No aging for simplicity
    aging = np.zeros(T)

    return {
        "R_mean": R_mean,
        "R_draws": R_draws,
        "theta_natural": theta_natural,
        "aging": aging,
        "nadir": nadir,
        "delta": delta,
        "n_nodes": n_nodes,
        "n_draws": n_draws,
        "T": T,
    }


@pytest.fixture
def mock_node_map():
    """Mock NodeMap with 3 cognitive nodes in 2 domains."""
    node_map = MagicMock()
    node_map.node_index = {
        "memory": 0,
        "attention": 1,
        "executive": 2,
    }
    # Provide proper nodes list so len(node_map.nodes) works and
    # gate F4T-G1b can validate orientation + unit_of_measure
    mock_nodes = []
    for nid in ["memory", "attention", "executive"]:
        node = MagicMock()
        node.node_id = nid
        node.orientation = "POS_UP"
        node.unit_of_measure = "z-score"
        mock_nodes.append(node)
    node_map.nodes = mock_nodes
    return node_map


# ══════════════════════════════════════════════════════════════
#  Unit Tests: solve_linear_coefficients
# ══════════════════════════════════════════════════════════════


def test_solve_linear_coefficients_basic():
    """Hand-computed: θ(t) = -2 + 2*R(t), check nadir=-2, delta=2."""
    T = 5
    R_mean = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    theta = np.array([[-2.0, -1.5, -1.0, -0.5, 0.0]])  # (1, T)

    nadir, delta = solve_linear_coefficients(theta, R_mean)

    np.testing.assert_allclose(nadir, [-2.0], atol=1e-10)
    np.testing.assert_allclose(delta, [2.0], atol=1e-10)


def test_solve_linear_coefficients_multi_node():
    """Multiple nodes with different linear relationships."""
    T = 3
    R_mean = np.array([0.0, 0.5, 1.0])

    # Node 0: -1 + 3*R → [-1, 0.5, 2]
    # Node 1: -3 + 1*R → [-3, -2.5, -2]
    theta = np.array([
        [-1.0, 0.5, 2.0],
        [-3.0, -2.5, -2.0],
    ])

    nadir, delta = solve_linear_coefficients(theta, R_mean)

    np.testing.assert_allclose(nadir, [-1.0, -3.0], atol=1e-10)
    np.testing.assert_allclose(delta, [3.0, 1.0], atol=1e-10)


# ══════════════════════════════════════════════════════════════
#  Unit Tests: classify_crci_vectorized
# ══════════════════════════════════════════════════════════════


def test_classify_crci_all_impaired():
    """All domains severely impaired → CRCI positive."""
    n_domains, n_draws, T = 4, 5, 3
    domain_z = np.full((n_domains, n_draws, T), -2.0)

    result = classify_crci_vectorized(domain_z)

    assert result.shape == (n_draws, T)
    assert np.all(result)  # All draws positive


def test_classify_crci_none_impaired():
    """All domains normal → CRCI negative."""
    n_domains, n_draws, T = 4, 5, 3
    domain_z = np.zeros((n_domains, n_draws, T))

    result = classify_crci_vectorized(domain_z)

    assert result.shape == (n_draws, T)
    assert not np.any(result)  # All draws negative


def test_classify_crci_single_severe():
    """One domain at -2.0 single threshold → CRCI positive."""
    n_domains, n_draws, T = 4, 5, 3
    domain_z = np.zeros((n_domains, n_draws, T))

    # Set one domain below single-domain threshold
    z_single = config.F4_THRESHOLD_SINGLE_DOMAIN_Z  # -2.0
    domain_z[0, :, :] = z_single - 0.1

    result = classify_crci_vectorized(domain_z)

    assert np.all(result)  # Should trigger single-domain criterion


def test_classify_crci_two_moderate():
    """Two domains at -1.5 multi threshold → CRCI positive."""
    n_domains, n_draws, T = 4, 5, 3
    domain_z = np.zeros((n_domains, n_draws, T))

    # Set two domains at multi-domain threshold
    z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z  # -1.5
    domain_z[0, :, :] = z_multi - 0.1
    domain_z[1, :, :] = z_multi - 0.1

    result = classify_crci_vectorized(domain_z)

    assert np.all(result)  # Should trigger multi-domain criterion


# ══════════════════════════════════════════════════════════════
#  Unit Tests: theta reconstruction (F4T-1)
# ══════════════════════════════════════════════════════════════


def test_reconstruct_theta_shape(simple_recovery_data):
    """Output shape: (n_cog, n_draws, T)."""
    data = simple_recovery_data
    cognitive_indices = [0, 1, 2]

    result = _reconstruct_theta_draws_natural(
        theta_natural=data["theta_natural"],
        R_draws=data["R_draws"],
        R_mean=data["R_mean"],
        aging=data["aging"],
        cognitive_indices=cognitive_indices,
    )

    assert result.shape == (3, data["n_draws"], data["T"])


def test_reconstruct_theta_at_endpoints(simple_recovery_data):
    """At R=0, theta should equal nadir; at R=1, theta ≈ nadir + delta."""
    data = simple_recovery_data

    # Make R_draws exact at endpoints (no noise)
    R_draws_exact = np.zeros((2, data["T"]))
    R_draws_exact[0, :] = 0.0  # Draw 0: always at nadir
    R_draws_exact[1, :] = np.linspace(0, 1, data["T"])  # Draw 1: linear recovery

    result = _reconstruct_theta_draws_natural(
        theta_natural=data["theta_natural"],
        R_draws=R_draws_exact,
        R_mean=data["R_mean"],
        aging=data["aging"],
        cognitive_indices=[0, 1, 2],
    )

    # Draw 0, t=0 should be nadir (since R=0)
    np.testing.assert_allclose(result[:, 0, 0], data["nadir"], atol=1e-6)

    # Draw 1, t=T-1 should be nadir + delta (since R=1)
    expected_end = data["nadir"] + data["delta"]
    np.testing.assert_allclose(result[:, 1, -1], expected_end, atol=1e-6)


# ══════════════════════════════════════════════════════════════
#  Unit Tests: risk curve
# ══════════════════════════════════════════════════════════════


def test_compute_risk_curve_all_positive():
    """All draws CRCI positive → risk = 100%."""
    n_domains, n_draws, T = 4, 100, 6
    domain_z = np.full((n_domains, n_draws, T), -2.0)  # All severely impaired

    curve = _compute_risk_curve(domain_z, "test", "Test", horizons=[3])

    assert len(curve.points) == T
    for pt in curve.points:
        assert pt.risk_pct == pytest.approx(100.0, abs=0.1)


def test_compute_risk_curve_all_negative():
    """All draws CRCI negative → risk = 0%."""
    n_domains, n_draws, T = 4, 100, 6
    domain_z = np.zeros((n_domains, n_draws, T))  # All normal

    curve = _compute_risk_curve(domain_z, "test", "Test", horizons=[3])

    for pt in curve.points:
        assert pt.risk_pct == pytest.approx(0.0, abs=0.1)


def test_compute_risk_curve_mixed():
    """50% draws CRCI positive → risk ≈ 50%."""
    n_domains, n_draws, T = 4, 100, 6
    domain_z = np.zeros((n_domains, n_draws, T))

    # First half of draws: impaired (2 domains below threshold)
    z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    domain_z[0, :50, :] = z_multi - 0.5
    domain_z[1, :50, :] = z_multi - 0.5

    curve = _compute_risk_curve(domain_z, "test", "Test", horizons=[3])

    for pt in curve.points:
        assert 40.0 <= pt.risk_pct <= 60.0  # Around 50%


# ══════════════════════════════════════════════════════════════
#  Unit Tests: risk reduction (F4T-8/9/10)
# ══════════════════════════════════════════════════════════════


def test_compute_risk_reduction_basic():
    """ARR = P_nat - P_int, hand-check."""
    # Natural: 80% risk at all timepoints
    natural_points = [
        TemporalRiskPoint(month=t, risk_pct=80.0, risk_lower_pct=70.0,
                         risk_upper_pct=90.0, mc_se=0.02, n_domains_impaired_mean=2.0,
                         n_draws_crci_positive=80)
        for t in range(6)
    ]
    natural_curve = TemporalRiskCurve(
        scenario_id="natural",
        scenario_label="Natural",
        points=natural_points,
    )

    # Intervention: 50% risk at all timepoints → ARR = 30%
    intv_points = [
        TemporalRiskPoint(month=t, risk_pct=50.0, risk_lower_pct=40.0,
                         risk_upper_pct=60.0, mc_se=0.02, n_domains_impaired_mean=1.0,
                         n_draws_crci_positive=50)
        for t in range(6)
    ]
    intv_curve = TemporalRiskCurve(
        scenario_id="intv1",
        scenario_label="Intervention 1",
        points=intv_points,
    )

    reduction = _compute_risk_reduction(
        natural_curve, intv_curve, horizons=[3],
        calibration_status="calibrated",  # NNT only reported when calibrated (§8.2 feedback 3.1)
    )

    # ARR = 80 - 50 = 30 at all t
    assert reduction.arr_curve == pytest.approx([30.0] * 6, abs=0.01)

    # RRR = 30 / 80 = 0.375 = 37.5%
    assert reduction.rrr_at_horizons[3] == pytest.approx(37.5, abs=0.1)

    # NNT = 100 / 30 ≈ 3.33
    assert reduction.nnt_at_horizons[3] == pytest.approx(3.33, abs=0.1)


# ══════════════════════════════════════════════════════════════
#  Integration Test
# ══════════════════════════════════════════════════════════════


def test_compute_temporal_risk_smoke(mock_node_map):
    """End-to-end smoke test with mocked inputs."""
    # Mock RecoveryTrajectory
    n_draws, T = 50, 12
    recovery = MagicMock()
    recovery.R_draws = np.random.uniform(0, 1, (n_draws, T))
    recovery.R_mean = np.mean(recovery.R_draws, axis=0)
    recovery.theta_natural = np.random.uniform(-2, 0, (3, T))
    recovery.theta_nadir = None  # Force fallback path (solve_linear_coefficients)
    recovery.theta_base = None
    recovery.time_months = np.arange(T, dtype=float)

    # Mock OverlayResult
    overlay = MagicMock()
    overlay.aging_projection = np.linspace(0, -0.2, T)
    overlay.n_interventions = 1
    overlay.intervention_trajectories = {
        "cognitive_training": MagicMock(
            delta_C=0.5,
            delta_theta_mean=None,  # Force scalar fallback path
            K_a=np.linspace(0, 1, T),
        ),
    }

    # Patch config to use our mock nodes
    original_map = config.F4_DOMAIN_NODE_MAP
    config.F4_DOMAIN_NODE_MAP = {
        "memory": ["memory"],
        "attention": ["attention"],
        "executive": ["executive"],
    }

    try:
        result = compute_temporal_risk(
            recovery=recovery,
            overlay=overlay,
            node_map=mock_node_map,
            horizons=[3, 6],
        )

        assert isinstance(result, PredictiveRiskEstimate)
        assert result.n_draws == n_draws
        assert result.n_timepoints == T
        assert len(result.natural_curve.points) == T
        assert "cognitive_training" in result.intervention_curves
        assert result.gate_f4t_g1_passed

    finally:
        config.F4_DOMAIN_NODE_MAP = original_map


# ══════════════════════════════════════════════════════════════
#  Edge Cases
# ══════════════════════════════════════════════════════════════


def test_empty_cognitive_nodes(mock_node_map):
    """No cognitive nodes mapped → GateViolation (fix §8.2 feedback 3.2)."""
    mock_node_map.node_index = {}  # No nodes
    mock_node_map.nodes = []  # No nodes in list

    recovery = MagicMock()
    recovery.R_draws = np.random.uniform(0, 1, (10, 6))
    recovery.theta_nadir = None
    recovery.theta_base = None
    recovery.time_months = np.arange(6, dtype=float)

    overlay = MagicMock()
    overlay.intervention_trajectories = {}
    overlay.n_interventions = 0
    overlay.aging_projection = np.zeros(6)

    # Patch to empty domain map → should raise GateViolation per §8.2 feedback 3.2
    # (all ICCTF domains missing from NodeMap)
    original_map = config.F4_DOMAIN_NODE_MAP
    config.F4_DOMAIN_NODE_MAP = {"processing_speed": ["NODE_COG_PROC_SPEED"]}

    try:
        with pytest.raises(GateViolation) as exc_info:
            compute_temporal_risk(recovery, overlay, mock_node_map)
        assert "F4T-G1b" in str(exc_info.value)

    finally:
        config.F4_DOMAIN_NODE_MAP = original_map


# ══════════════════════════════════════════════════════════════
#  Gate Violation Tests
# ══════════════════════════════════════════════════════════════


def test_gate_f4t_g1_degenerate_draws(mock_node_map):
    """R_draws with no variation should fail gate F4T-G1."""
    n_draws, T = 50, 12

    # All draws identical → no variation
    recovery = MagicMock()
    recovery.R_draws = np.tile(np.linspace(0, 1, T), (n_draws, 1))
    recovery.R_mean = recovery.R_draws[0, :]
    recovery.theta_natural = np.random.uniform(-2, 0, (3, T))
    recovery.theta_nadir = None  # Force fallback path
    recovery.theta_base = None
    recovery.time_months = np.arange(T, dtype=float)

    overlay = MagicMock()
    overlay.aging_projection = np.zeros(T)
    overlay.n_interventions = 0
    overlay.intervention_trajectories = {}

    # Patch config
    original_map = config.F4_DOMAIN_NODE_MAP
    config.F4_DOMAIN_NODE_MAP = {
        "memory": ["memory"],
        "attention": ["attention"],
        "executive": ["executive"],
    }

    try:
        with pytest.raises(GateViolation) as exc_info:
            compute_temporal_risk(recovery, overlay, mock_node_map)

        assert "F4T-G1" in str(exc_info.value)
        # Gate may fire for various reasons (degenerate draws, insufficient
        # variation, or time dimension mismatch) — just verify it fires

    finally:
        config.F4_DOMAIN_NODE_MAP = original_map
