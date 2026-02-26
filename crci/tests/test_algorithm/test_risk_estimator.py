"""
Tests for crci.algorithm.chain_f_analytics.risk_estimator (F4).

Hand-computable test cases per §6.1–6.5 of
IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md.

Covers:
    - F4-1: CRCI classification per draw (multi-domain + single severe)
    - F4-2: Point estimate P̂(CRCI)
    - F4-3a: MC-SE computation
    - F4-3b: Jeffreys Beta interval
    - F4-4: Marginal domain impairment
    - F4-5: Trigger-share attribution (Σφ_d = 1.0)
    - F4-6: IVW precision weight percentage (Σw_d% = 100%)
    - Gate F-G4a: Orientation flip rejection
    - Gate F-G4a: Missing node rejection
    - Gate F-G4b: Insufficient draws
    - Gate F-G4c: Output consistency
    - Edge cases: S=0, S=M
    - Domain aggregation divergence (mean vs min)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pytest
from scipy import stats

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation


# ═══════════════════════════════════════════════════════════════
#  Minimal mocks (mimics just enough of NodeMap and CompositeState)
# ═══════════════════════════════════════════════════════════════


@dataclass
class MockNodeDef:
    node_id: str
    node_label: str = ""
    layer: int = 5
    clinical_domain: str = "cognitive"
    is_observable: bool = True
    is_latent: bool = False
    orientation: str = "POS_UP"
    unit_of_measure: str = "z-score"
    pathway_membership: list[str] = field(default_factory=list)
    proxy_for: str | None = None
    proxy_r_squared: float | None = None
    description: str = ""


@dataclass
class MockNodeMap:
    """Minimal mock of NodeMap for testing."""

    nodes: list[MockNodeDef]
    node_index: dict[str, int]
    layer_assignment: dict[str, int] = field(default_factory=dict)
    domain_assignment: dict[str, str] = field(default_factory=dict)
    observability: dict[str, bool] = field(default_factory=dict)
    orientation: dict[str, str] = field(default_factory=dict)
    topological_order: list[str] = field(default_factory=list)
    nodes_by_layer: dict[int, list[str]] = field(default_factory=dict)
    n_observable: int = 0
    n_latent: int = 0


def _make_node_map(
    n_extra: int = 0,
    orientation_overrides: dict[str, str] | None = None,
    unit_overrides: dict[str, str] | None = None,
    excluded_ids: set[str] | None = None,
) -> MockNodeMap:
    """Build a minimal NodeMap with all F4 domain nodes + optional extras."""
    orientation_overrides = orientation_overrides or {}
    unit_overrides = unit_overrides or {}
    excluded_ids = excluded_ids or set()

    nodes = []
    node_index = {}
    orientation = {}
    idx = 0

    # Add all nodes from F4_DOMAIN_NODE_MAP
    for domain_id, node_ids in config.F4_DOMAIN_NODE_MAP.items():
        for nid in node_ids:
            if nid in excluded_ids:
                continue
            nd = MockNodeDef(
                node_id=nid,
                node_label=nid,
                orientation=orientation_overrides.get(nid, "POS_UP"),
                unit_of_measure=unit_overrides.get(nid, "z-score"),
            )
            nodes.append(nd)
            node_index[nid] = idx
            orientation[nid] = nd.orientation
            idx += 1

    # Extra nodes (e.g., non-cognitive)
    for i in range(n_extra):
        nid = f"NODE_EXTRA_{i}"
        nd = MockNodeDef(node_id=nid, node_label=nid)
        nodes.append(nd)
        node_index[nid] = idx
        orientation[nid] = "POS_UP"
        idx += 1

    return MockNodeMap(
        nodes=nodes,
        node_index=node_index,
        orientation=orientation,
    )


@dataclass
class MockCompositeState:
    """Minimal mock of CompositeState for F4-6 IVW weights."""

    crci_composite: float = 0.0
    severity_tier: str = "MILD_IMPAIRMENT"
    percentile: float = 50.0
    subdomain_scores: dict[str, float] = field(default_factory=dict)
    subdomain_weights: dict[str, float] = field(default_factory=dict)
    cochrans_Q: float = 0.0
    I_squared: float = 0.0
    random_effects_applied: bool = False
    severity_weighted_z: dict[str, float] = field(default_factory=dict)
    n_domains: int = 10
    gate_f_g1_passed: bool = True


# ═══════════════════════════════════════════════════════════════
#  Import the module under test
# ═══════════════════════════════════════════════════════════════

from crci.algorithm.chain_f_analytics.risk_estimator import (
    CRCIRiskEstimate,
    DomainRiskProfile,
    _classify_crci_per_draw,
    _classify_risk_tier,
    _compute_coverage,
    _compute_interval,
    _compute_ivw_weight_pct,
    _compute_marginal_domain_risk,
    _compute_mc_se,
    _compute_risk_point_estimate,
    _compute_trigger_share,
    _extract_domain_draws,
    _validate_domain_mapping,
    _validate_gate_f_g4b,
    _validate_gate_f_g4c,
    estimate_crci_risk,
)


# ═══════════════════════════════════════════════════════════════
#  Test F4-1: CRCI Classification Per Draw
# ═══════════════════════════════════════════════════════════════


class TestCRCIClassification:
    """Formula F4-1: CRCI^(m) indicator testing."""

    def test_multi_domain_criterion(self):
        """≥2 domains ≤ -1.5 → CRCI positive."""
        domain_draws = {
            "d1": np.array([-2.0, -1.6, -0.5]),  # below -1.5 in draws 0,1
            "d2": np.array([-1.8, -1.0, -0.3]),   # below -1.5 in draw 0
            "d3": np.array([-0.2, -1.7, -0.1]),   # below -1.5 in draw 1
        }
        result = _classify_crci_per_draw(domain_draws)
        # Draw 0: d1 ≤ -1.5, d2 ≤ -1.5 → 2 domains → CRCI+
        # Draw 1: d1 ≤ -1.5, d3 ≤ -1.5 → 2 domains → CRCI+
        # Draw 2: none below → CRCI-
        assert result[0] == True
        assert result[1] == True
        assert result[2] == False

    def test_single_severe_criterion(self):
        """≥1 domain ≤ -2.0 → CRCI positive (even if only 1 domain)."""
        domain_draws = {
            "d1": np.array([-2.1, -0.5, -1.0]),
            "d2": np.array([-0.3, -0.3, -0.3]),
            "d3": np.array([-0.1, -0.1, -0.1]),
        }
        result = _classify_crci_per_draw(domain_draws)
        # Draw 0: d1 ≤ -2.0 → CRCI+ (single severe)
        # Draws 1,2: none ≤ -2.0, and only 0 domains ≤ -1.5 → CRCI-
        assert result[0] == True
        assert result[1] == False
        assert result[2] == False

    def test_no_impairment(self):
        """All z-scores above thresholds → all draws CRCI negative."""
        domain_draws = {
            "d1": np.array([0.0, 0.5, 1.0]),
            "d2": np.array([0.2, 0.3, 0.4]),
        }
        result = _classify_crci_per_draw(domain_draws)
        assert not np.any(result)

    def test_all_impaired(self):
        """All domains severely impaired → all draws CRCI positive."""
        domain_draws = {
            "d1": np.array([-3.0, -2.5, -2.1]),
            "d2": np.array([-2.8, -2.2, -2.3]),
            "d3": np.array([-2.5, -2.0, -2.4]),
        }
        result = _classify_crci_per_draw(domain_draws)
        assert np.all(result)


# ═══════════════════════════════════════════════════════════════
#  Test F4-2: Point Estimate
# ═══════════════════════════════════════════════════════════════


class TestPointEstimate:
    def test_basic(self):
        indicator = np.array([True, True, False, False, True])
        p, S, M = _compute_risk_point_estimate(indicator)
        assert S == 3
        assert M == 5
        assert abs(p - 0.6) < 1e-10

    def test_all_positive(self):
        indicator = np.ones(100, dtype=bool)
        p, S, M = _compute_risk_point_estimate(indicator)
        assert p == 1.0
        assert S == 100

    def test_all_negative(self):
        indicator = np.zeros(100, dtype=bool)
        p, S, M = _compute_risk_point_estimate(indicator)
        assert p == 0.0
        assert S == 0


# ═══════════════════════════════════════════════════════════════
#  Test F4-3a: MC Standard Error
# ═══════════════════════════════════════════════════════════════


class TestMCSE:
    def test_basic(self):
        # P̂ = 0.3, M = 10000
        se = _compute_mc_se(0.3, 10000)
        expected = math.sqrt(0.3 * 0.7 / 10000)
        assert abs(se - expected) < 1e-10

    def test_zero_risk(self):
        se = _compute_mc_se(0.0, 10000)
        assert se == 0.0

    def test_full_risk(self):
        se = _compute_mc_se(1.0, 10000)
        assert se == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F4-3b: Jeffreys Beta Interval
# ═══════════════════════════════════════════════════════════════


class TestJeffreysInterval:
    def test_s_zero(self):
        """S=0, M=10000 → finite interval near 0%, not NaN."""
        lower, upper, method = _compute_interval(0, 10000, 0.0, 0.0)
        assert method == "jeffreys"
        assert lower >= 0.0
        assert upper > 0.0
        assert upper < 0.01  # should be tiny
        assert np.isfinite(lower)
        assert np.isfinite(upper)

    def test_s_equals_m(self):
        """S=M=10000 → finite interval near 100%, not NaN."""
        lower, upper, method = _compute_interval(10000, 10000, 1.0, 0.0)
        assert method == "jeffreys"
        assert lower > 0.99
        assert upper <= 1.0
        assert np.isfinite(lower)
        assert np.isfinite(upper)

    def test_interior(self):
        """S=3000, M=10000 → interval brackets P̂=0.30."""
        lower, upper, method = _compute_interval(3000, 10000, 0.3, 0.0)
        assert method == "jeffreys"
        assert lower < 0.3
        assert upper > 0.3
        # Should be reasonably tight (width < 3%)
        assert (upper - lower) < 0.03

    def test_mc_se_method(self):
        """MC-SE interval mode."""
        # Temporarily override config
        orig = config.F4_INTERVAL_METHOD
        config.F4_INTERVAL_METHOD = "mc_se"
        try:
            lower, upper, method = _compute_interval(3000, 10000, 0.3, 0.004583)
            assert method == "mc_se"
            assert lower < 0.3
            assert upper > 0.3
        finally:
            config.F4_INTERVAL_METHOD = orig


# ═══════════════════════════════════════════════════════════════
#  Test F4-4: Marginal Domain Impairment
# ═══════════════════════════════════════════════════════════════


class TestMarginalRisk:
    def test_basic(self):
        domain_draws = {
            "d1": np.array([-2.0, -1.6, -0.5, -1.0, -1.8]),
            "d2": np.array([-0.3, -0.3, -0.3, -0.3, -0.3]),
        }
        marginals = _compute_marginal_domain_risk(domain_draws)
        # d1: 3 of 5 draws ≤ -1.5 → 0.6
        assert abs(marginals["d1"] - 0.6) < 1e-10
        # d2: 0 of 5 draws ≤ -1.5 → 0.0
        assert marginals["d2"] == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F4-5: Trigger-Share Attribution
# ═══════════════════════════════════════════════════════════════


class TestTriggerShare:
    def test_sum_to_one(self):
        """Trigger-share must sum to 1.0 when P̂ > 0."""
        np.random.seed(42)
        # Create draws where some are CRCI-positive
        domain_draws = {
            f"d{i}": np.random.normal(-1.0, 1.0, size=1000)
            for i in range(5)
        }
        indicator = _classify_crci_per_draw(domain_draws)
        S = int(np.sum(indicator))
        if S == 0:
            pytest.skip("No positive draws in this seed")

        shares = _compute_trigger_share(domain_draws, indicator)
        total = sum(shares.values())
        assert abs(total - 1.0) < config.F4_TRIGGER_SHARE_SUM_TOLERANCE, \
            f"Σφ_d = {total}, expected 1.0 ± {config.F4_TRIGGER_SHARE_SUM_TOLERANCE}"

    def test_zero_risk_returns_zeros(self):
        """P̂ = 0 → all trigger-shares = 0.0."""
        domain_draws = {
            "d1": np.array([0.0, 0.5]),
            "d2": np.array([0.0, 0.5]),
        }
        indicator = np.array([False, False])
        shares = _compute_trigger_share(domain_draws, indicator)
        assert all(v == 0.0 for v in shares.values())

    def test_single_triggering_domain(self):
        """Only domain d1 triggers → d1 gets 100% share."""
        domain_draws = {
            "d1": np.array([-2.5, -2.0, -2.1]),  # always below -1.5
            "d2": np.array([0.0, 0.0, 0.0]),       # never below
        }
        indicator = _classify_crci_per_draw(domain_draws)
        shares = _compute_trigger_share(domain_draws, indicator)
        assert shares["d1"] > 0.99
        assert shares["d2"] < 0.01


# ═══════════════════════════════════════════════════════════════
#  Test F4-6: IVW Precision Weight
# ═══════════════════════════════════════════════════════════════


class TestIVWWeight:
    def test_sum_to_100(self):
        """IVW weights sum to 100%."""
        cs = MockCompositeState(
            subdomain_weights={
                "processing_speed": 4.0,
                "working_memory": 2.0,
                "episodic_memory": 2.0,
                "language": 2.0,
            },
        )
        domain_ids = ["processing_speed", "working_memory", "episodic_memory", "language"]
        weights = _compute_ivw_weight_pct(cs, domain_ids)
        total = sum(weights.values())
        assert abs(total - 100.0) < 0.1

    def test_missing_domain_gets_zero(self):
        """Domains not in CompositeState weights get 0%."""
        cs = MockCompositeState(
            subdomain_weights={"processing_speed": 4.0},
        )
        domain_ids = ["processing_speed", "working_memory"]
        weights = _compute_ivw_weight_pct(cs, domain_ids)
        # ps=4, wm=0 → total=4 → ps=4/4×100=100%, wm=0/4×100=0%
        assert weights["processing_speed"] == 100.0
        assert weights["working_memory"] == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test Risk Tier Classification
# ═══════════════════════════════════════════════════════════════


class TestRiskTier:
    def test_tiers(self):
        assert _classify_risk_tier(5.0) == "LOW"
        assert _classify_risk_tier(14.9) == "LOW"
        assert _classify_risk_tier(15.0) == "MODERATE"
        assert _classify_risk_tier(29.9) == "MODERATE"
        assert _classify_risk_tier(30.0) == "ELEVATED"
        assert _classify_risk_tier(49.9) == "ELEVATED"
        assert _classify_risk_tier(50.0) == "HIGH"
        assert _classify_risk_tier(69.9) == "HIGH"
        assert _classify_risk_tier(70.0) == "VERY_HIGH"
        assert _classify_risk_tier(99.0) == "VERY_HIGH"


# ═══════════════════════════════════════════════════════════════
#  Test Coverage Computation
# ═══════════════════════════════════════════════════════════════


class TestCoverage:
    def test_partial_coverage(self):
        """3 of 10 domains at L2+ → coverage = 0.3, low_coverage_warning."""
        domain_index_map = {f"d{i}": [i] for i in range(10)}
        fusion_levels = {
            0: {"L2"},        # observed
            1: {"L2", "L3"},  # observed (multi-instrument)
            2: {"L3"},        # observed
            3: {"L1"},        # NOT observed (build-time only)
            4: {"L1"},
            5: {"L1"},
            6: {"L1"},
            7: {"L1"},
            8: {"L1"},
            9: {"L1"},
        }
        cov, obs, n_obs = _compute_coverage(domain_index_map, fusion_levels)
        assert abs(cov - 0.3) < 1e-10
        assert sum(1 for v in obs.values() if v) == 3

    def test_full_coverage(self):
        domain_index_map = {f"d{i}": [i] for i in range(10)}
        fusion_levels = {i: {"L2"} for i in range(10)}
        cov, obs, n_obs = _compute_coverage(domain_index_map, fusion_levels)
        assert cov == 1.0


# ═══════════════════════════════════════════════════════════════
#  Gate F-G4a: Orientation Flip Rejection (§6.5)
# ═══════════════════════════════════════════════════════════════


class TestGateFG4a:
    def test_orientation_flip_raises(self):
        """NODE_COG_PROC_SPEED marked NEG_UP → Gate F-G4a fires."""
        node_map = _make_node_map(
            orientation_overrides={"NODE_COG_PROC_SPEED": "NEG_UP"},
        )
        with pytest.raises(GateViolation) as exc_info:
            _validate_domain_mapping(node_map)
        assert "F-G4a" in str(exc_info.value)
        assert "POS_UP" in str(exc_info.value)

    def test_missing_node_raises(self):
        """node_id in CRCI_DOMAIN_NODE_MAP absent from NodeMap → raises."""
        node_map = _make_node_map(
            excluded_ids={"NODE_COG_PROC_SPEED"},
        )
        with pytest.raises(GateViolation) as exc_info:
            _validate_domain_mapping(node_map)
        assert "F-G4a" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    def test_wrong_unit_raises(self):
        """Node with unit != z-score → Gate F-G4a fires."""
        node_map = _make_node_map(
            unit_overrides={"NODE_COG_WORK_MEM": "raw_score"},
        )
        with pytest.raises(GateViolation) as exc_info:
            _validate_domain_mapping(node_map)
        assert "F-G4a" in str(exc_info.value)
        assert "unit" in str(exc_info.value).lower()

    def test_valid_mapping_passes(self):
        """All nodes present, POS_UP, z-score → passes."""
        node_map = _make_node_map()
        result = _validate_domain_mapping(node_map)
        assert len(result) == 10  # 10 cognitive domains


# ═══════════════════════════════════════════════════════════════
#  Gate F-G4b: Draw Quality
# ═══════════════════════════════════════════════════════════════


class TestGateFG4b:
    def test_insufficient_draws_raises(self):
        """n_draws < F4_MIN_DRAWS → raises."""
        theta = np.random.normal(0, 1, size=(50, 10))  # only 50 draws
        domain_draws = {"d1": theta[:, 0]}
        with pytest.raises(GateViolation) as exc_info:
            _validate_gate_f_g4b(theta, domain_draws)
        assert "F-G4b" in str(exc_info.value)

    def test_nan_draws_raises(self):
        """NaN in domain draws → raises."""
        theta = np.random.normal(0, 1, size=(2000, 10))
        d = theta[:, 0].copy()
        d[100] = np.nan
        domain_draws = {"d1": d}
        with pytest.raises(GateViolation) as exc_info:
            _validate_gate_f_g4b(theta, domain_draws)
        assert "F-G4b" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════
#  Domain Aggregation Divergence (§6.5)
# ═══════════════════════════════════════════════════════════════


class TestDomainAggregation:
    def test_mean_vs_min_divergence(self):
        """Toy draw where mean(z_nodes) > -1.5 but min(z_nodes) < -1.5."""
        # Domain with 2 nodes: one at -2.0, one at 0.0
        # mean = -1.0 (not impaired), min = -2.0 (impaired)
        theta_draws = np.array([
            [-2.0, 0.0, -2.0, 0.0],   # domain A: nodes 0,1; domain B: nodes 2,3
        ])
        domain_index_map = {"dA": [0, 1], "dB": [2, 3]}

        # Test with mean aggregation
        orig = config.F4_DOMAIN_AGGREGATION
        config.F4_DOMAIN_AGGREGATION = "mean"
        draws_mean = _extract_domain_draws(theta_draws, domain_index_map)
        assert abs(draws_mean["dA"][0] - (-1.0)) < 1e-10  # mean(-2, 0) = -1.0

        # Test with min aggregation
        config.F4_DOMAIN_AGGREGATION = "min"
        draws_min = _extract_domain_draws(theta_draws, domain_index_map)
        assert abs(draws_min["dA"][0] - (-2.0)) < 1e-10  # min(-2, 0) = -2.0

        config.F4_DOMAIN_AGGREGATION = orig

        # Under mean: dA not impaired (mean = -1.0 > -1.5)
        # Under min: dA impaired (min = -2.0 ≤ -1.5)
        assert draws_mean["dA"][0] > config.F4_THRESHOLD_MULTI_DOMAIN_Z
        assert draws_min["dA"][0] <= config.F4_THRESHOLD_MULTI_DOMAIN_Z


# ═══════════════════════════════════════════════════════════════
#  Integration: Full estimate_crci_risk
# ═══════════════════════════════════════════════════════════════


class TestEstimateCRCIRisk:
    """Integration test with hand-computable draws."""

    def _make_theta_draws(self, M: int = 5000) -> np.ndarray:
        """Create M draws across 10 cognitive domain nodes.

        Seeded so results are deterministic.
        Domains 0 (processing_speed) and 4 (episodic_memory)
        are designed to have substantial impairment.
        """
        rng = np.random.default_rng(42)
        n_nodes = 10  # one node per domain
        theta = rng.normal(0, 1, size=(M, n_nodes))

        # Shift domain 0 (processing_speed) to mean -1.8
        theta[:, 0] -= 1.8
        # Shift domain 4 (episodic_memory) to mean -1.6
        theta[:, 4] -= 1.6

        return theta

    def test_basic_risk_estimate(self):
        """Full pipeline with deterministic draws."""
        node_map = _make_node_map()
        composite = MockCompositeState(
            subdomain_weights={d: 1.0 for d in config.F4_DOMAIN_NODE_MAP},
        )
        fusion_levels = {i: {"L2"} for i in range(10)}
        theta_draws = self._make_theta_draws(M=5000)

        result = estimate_crci_risk(
            theta_draws=theta_draws,
            node_map=node_map,
            composite_state=composite,
            fusion_levels=fusion_levels,
        )

        # Basic sanity
        assert result.gate_f_g4_passed
        assert 0.0 <= result.risk_pct <= 100.0
        assert result.risk_lower_pct <= result.risk_pct
        assert result.risk_pct <= result.risk_upper_pct
        assert result.interval_method == "jeffreys"
        assert result.n_draws_used == 5000
        assert len(result.domain_profiles) == 10
        assert result.coverage_fraction == 1.0
        assert not result.low_coverage_warning
        assert result.calibration_status == "uncalibrated_model_derived"

        # Domains 0 (proc_speed) and 4 (episodic_mem) should have
        # higher marginal risk than others
        proc_speed = next(
            dp for dp in result.domain_profiles
            if dp.domain_id == "processing_speed"
        )
        episodic = next(
            dp for dp in result.domain_profiles
            if dp.domain_id == "episodic_memory"
        )
        language = next(
            dp for dp in result.domain_profiles
            if dp.domain_id == "language"
        )

        assert proc_speed.marginal_risk_pct > language.marginal_risk_pct
        assert episodic.marginal_risk_pct > language.marginal_risk_pct

        # Trigger-share should sum to ~100%
        total_trigger = sum(
            dp.trigger_share_pct for dp in result.domain_profiles
        )
        if result.risk_pct > 0:
            assert abs(total_trigger - 100.0) < 1.0

        # IVW weights should sum to ~100%
        total_ivw = sum(
            dp.ivw_weight_pct for dp in result.domain_profiles
        )
        assert abs(total_ivw - 100.0) < 0.2

    def test_no_impairment(self):
        """All domains near zero → P̂ near 0%."""
        rng = np.random.default_rng(99)
        theta = rng.normal(0, 0.3, size=(2000, 10))  # tight around 0

        node_map = _make_node_map()
        composite = MockCompositeState(
            subdomain_weights={d: 1.0 for d in config.F4_DOMAIN_NODE_MAP},
        )
        fusion_levels = {i: {"L2"} for i in range(10)}

        result = estimate_crci_risk(theta, node_map, composite, fusion_levels)
        assert result.risk_pct < 5.0  # should be very low
        assert result.risk_tier == "LOW"

    def test_severe_impairment(self):
        """All domains at z ≈ -3 → P̂ near 100%."""
        rng = np.random.default_rng(77)
        theta = rng.normal(-3.0, 0.3, size=(2000, 10))  # all deeply impaired

        node_map = _make_node_map()
        composite = MockCompositeState(
            subdomain_weights={d: 1.0 for d in config.F4_DOMAIN_NODE_MAP},
        )
        fusion_levels = {i: {"L2"} for i in range(10)}

        result = estimate_crci_risk(theta, node_map, composite, fusion_levels)
        assert result.risk_pct > 95.0
        assert result.risk_tier == "VERY_HIGH"

    def test_low_coverage_warning(self):
        """Only 3 of 10 domains observed → low_coverage_warning."""
        theta = np.random.default_rng(42).normal(0, 1, size=(2000, 10))
        node_map = _make_node_map()
        composite = MockCompositeState(
            subdomain_weights={d: 1.0 for d in config.F4_DOMAIN_NODE_MAP},
        )
        # Only 3 domains with L2+ data
        fusion_levels: dict[int, set[str]] = {}
        for i in range(10):
            if i < 3:
                fusion_levels[i] = {"L2"}
            else:
                fusion_levels[i] = {"L1"}

        result = estimate_crci_risk(theta, node_map, composite, fusion_levels)
        assert result.coverage_fraction == 0.3
        assert result.low_coverage_warning is True
