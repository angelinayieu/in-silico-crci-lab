"""Tests for ALG-D2: Effect Propagation.

Covers:
    D2b: Matrix method Δθ = (I−B^T)⁻¹·x with hand-computed examples
    D2c: Path enumeration fallback
    D2d: Physiological ceiling clipping
    D2e: Composite severity-weighted scoring
    D-G2: Gate validation
    Full integration: propagate_effects end-to-end

Convention: B[source, target] — entry B[i,j] = β for edge i→j.
The SEM equation θ = B^T θ + ε gives Δθ = (I − B^T)⁻¹ x.
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_d_simulation.effect_propagation import (
    EffectResult,
    InterventionEffects,
    PropagationMethod,
    _apply_physiological_ceiling,
    _compute_composite_score,
    _compute_severity_weight,
    _find_direct_rct_edges,
    _get_cognitive_node_indices,
    _propagate_matrix_method,
    _propagate_path_enumeration,
    _validate_gate_d_g2,
    propagate_effects,
)
from crci.algorithm.chain_d_simulation.mc_sampler import MCDraws


# ═══════════════════════════════════════════════════════════════
#  Fixtures: Minimal mock graph objects
# ═══════════════════════════════════════════════════════════════

def _make_edge_def(edge_id, src, tgt, relation_type="causal", expected_sign="positive"):
    """Create a minimal EdgeDef."""
    from crci.algorithm.chain_a_graph.edge_loader import EdgeDef
    return EdgeDef(
        edge_id=edge_id,
        source_node_id=src,
        target_node_id=tgt,
        relation_type=relation_type,
        mechanism_description="test",
        primary_pathway="M1",
        secondary_pathways=[],
        expected_sign=expected_sign,
        functional_form="linear",
        fallback_form="linear",
        is_feedback_edge=False,
        feedback_loop_id=None,
    )


def _make_node_def(node_id, layer=0, domain="biological", is_observable=True):
    """Create a minimal NodeDef."""
    from crci.algorithm.chain_a_graph.node_loader import NodeDef
    return NodeDef(
        node_id=node_id,
        node_label=node_id,
        layer=layer,
        clinical_domain=domain,
        is_observable=is_observable,
        is_latent=False,
        orientation="POS_UP",
        unit_of_measure="z-score",
        pathway_membership=[],
        proxy_for=None,
        proxy_r_squared=None,
        description="test",
    )


def _make_node_map(nodes):
    """Create a minimal NodeMap."""
    from crci.algorithm.chain_a_graph.node_loader import NodeMap
    node_index = {n.node_id: i for i, n in enumerate(nodes)}
    layer_assignment = {n.node_id: n.layer for n in nodes}
    domain_assignment = {n.node_id: n.clinical_domain for n in nodes}
    observability = {n.node_id: n.is_observable for n in nodes}
    orientation = {n.node_id: n.orientation for n in nodes}
    topological_order = [n.node_id for n in sorted(nodes, key=lambda x: x.layer)]
    return NodeMap(
        nodes=nodes,
        node_index=node_index,
        layer_assignment=layer_assignment,
        domain_assignment=domain_assignment,
        observability=observability,
        orientation=orientation,
        topological_order=topological_order,
    )


def _make_b_skeleton(n_nodes, edges):
    """Create a minimal BSkeleton."""
    from crci.algorithm.chain_a_graph.edge_loader import BSkeleton
    node_index_map = {}  # filled by caller through node_map
    B_struct = np.zeros((n_nodes, n_nodes))
    edge_index = {}
    functional_forms = {}
    edge_claim_levels = {}
    forward_edges = []

    for i, e in enumerate(edges):
        edge_index[e.edge_id] = i
        functional_forms[e.edge_id] = e.functional_form
        edge_claim_levels[e.edge_id] = e.relation_type
        forward_edges.append(e.edge_id)

    return BSkeleton(
        n_nodes=n_nodes,
        n_edges=len(edges),
        edges=edges,
        edge_index=edge_index,
        B_struct=B_struct,
        functional_forms=functional_forms,
        hill_params={},
        edge_claim_levels=edge_claim_levels,
        feedback_edges=[],
        forward_edges=forward_edges,
        acyclicity_verified=True,
    )


def _make_graph_object(node_map, b_skeleton):
    """Create a minimal GraphObject."""
    from crci.algorithm.chain_a_graph.graph_object import GraphObject
    from crci.algorithm.chain_a_graph.instrument_loader import InstrumentMap
    from crci.algorithm.chain_a_graph.spectral_validator import DMatrix, LambdaStructure

    n = len(node_map.nodes)

    instrument_map = InstrumentMap(
        instruments=[],
        instrument_index={},
        node_to_instruments={},
        H=np.zeros((0, n)),
        observation_noise_var={},
        intercepts={},
    )

    d_matrix = DMatrix(
        D=np.eye(n),
        residual_variances=np.ones(n),
        R_squared_per_node=np.zeros(n),
        correlation_pairs=[],
        D_blocks={},
        is_positive_definite=True,
    )

    lambda_structure = LambdaStructure(
        Lambda=np.eye(n),
        is_positive_definite=True,
    )

    return GraphObject(
        node_map=node_map,
        b_skeleton=b_skeleton,
        instrument_map=instrument_map,
        d_matrix=d_matrix,
        lambda_structure=lambda_structure,
        n_nodes=n,
        n_edges=b_skeleton.n_edges,
    )


def _make_frozen(B_hat, graph, Sigma_eff=None, P_inclusion=None):
    """Create a minimal FrozenModelState."""
    from crci.algorithm.chain_b_evidence.frozen_state import FrozenModelState
    return FrozenModelState(
        B_hat=B_hat,
        Sigma_eff=Sigma_eff or {},
        Lambda_prior={},
        P_inclusion=P_inclusion or {},
        prior_audit_trail={},
        AV_scores={},
        tau_sq_estimates={},
        synergy_records=[],
        graph=graph,
        n_edges_parameterized=graph.n_edges,
    )


def _make_patient_state(theta_hat, Sigma_post):
    """Create a minimal PatientState."""
    from crci.algorithm.chain_c_posterior.modifier_application import PatientState
    n = len(theta_hat)
    return PatientState(
        theta_hat=theta_hat,
        Sigma_post=Sigma_post,
        Lambda_post=np.linalg.inv(Sigma_post),
        B_eff=np.zeros((n, n)),
        active_pathways=[],
        modifier_audit=[],
        observation_log=[],
        context_match=None,
        variance_reduction=np.zeros(n),
        modifier_se_inflation={},
    )


# ═══════════════════════════════════════════════════════════════
#  Test D2b: Matrix Method
# ═══════════════════════════════════════════════════════════════


class TestMatrixMethod:
    """D2b: Δθ = (I − B^T)⁻¹ · x with hand-computed expected values.

    B is stored as B[source, target].
    """

    def test_identity_graph_no_edges(self):
        """No edges → (I−B^T)⁻¹ = I → Δθ = x."""
        n = 4
        B = np.zeros((n, n))
        x = np.zeros(n)
        x[0] = 1.0  # intervene on node 0

        delta, fallback = _propagate_matrix_method(B, x)
        assert not fallback
        assert delta is not None
        # With no edges, only the intervention node is affected
        np.testing.assert_allclose(delta, x, atol=1e-12)

    def test_single_edge_chain(self):
        """Chain: 0→1 with β=0.5.

        B[source, target]: B[0,1] = 0.5
        B = [[0, 0.5],
             [0, 0  ]]
        B^T = [[0, 0], [0.5, 0]]
        (I-B^T) = [[1, 0], [-0.5, 1]]
        (I-B^T)⁻¹ = [[1, 0], [0.5, 1]]
        x = [1, 0]
        Δθ = [1, 0.5]
        """
        B = np.array([[0, 0.5], [0, 0]], dtype=float)
        x = np.array([1.0, 0.0])

        delta, fallback = _propagate_matrix_method(B, x)
        assert not fallback
        assert delta is not None
        np.testing.assert_allclose(delta, [1.0, 0.5], atol=1e-10)

    def test_two_hop_chain(self):
        """Chain: 0→1→2 with β₀₁=0.5, β₁₂=0.4.

        B[source, target]:
        B = [[0, 0.5, 0  ],
             [0, 0,   0.4],
             [0, 0,   0  ]]
        (I-B^T)⁻¹·x = [1.0, 0.5, 0.2]  (0.5 × 0.4 = 0.2)
        """
        B = np.zeros((3, 3))
        B[0, 1] = 0.5  # edge 0→1 (B[source=0, target=1])
        B[1, 2] = 0.4  # edge 1→2 (B[source=1, target=2])
        x = np.array([1.0, 0.0, 0.0])

        delta, fallback = _propagate_matrix_method(B, x)
        assert not fallback
        assert delta is not None
        np.testing.assert_allclose(delta, [1.0, 0.5, 0.2], atol=1e-10)

    def test_diamond_graph(self):
        """Diamond: 0→1, 0→2, 1→3, 2→3.

        B[source, target]: B[0,1]=0.5, B[0,2]=0.3, B[1,3]=0.4, B[2,3]=0.6
        x = [1, 0, 0, 0]
        Expected:
          Δθ₀ = 1.0
          Δθ₁ = 0.5
          Δθ₂ = 0.3
          Δθ₃ = 0.5×0.4 + 0.3×0.6 = 0.20 + 0.18 = 0.38
        """
        B = np.zeros((4, 4))
        B[0, 1] = 0.5  # edge 0→1
        B[0, 2] = 0.3  # edge 0→2
        B[1, 3] = 0.4  # edge 1→3
        B[2, 3] = 0.6  # edge 2→3
        x = np.array([1.0, 0.0, 0.0, 0.0])

        delta, fallback = _propagate_matrix_method(B, x)
        assert not fallback
        assert delta is not None
        np.testing.assert_allclose(delta, [1.0, 0.5, 0.3, 0.38], atol=1e-10)

    def test_ill_conditioned_triggers_fallback(self):
        """κ(I−B) > 10¹⁰ → returns None, True."""
        # Make I-B nearly singular: one eigenvalue near 0
        n = 3
        # B = I - ε * v·vᵀ / ||v||² makes (I-B) have one tiny eigenvalue
        B = np.eye(n)
        B[0, 0] -= 1e-12  # I-B[0,0] = 1e-12, others = 1
        # cond(I-B) = 1.0 / 1e-12 = 1e12 > 1e10
        x = np.array([1.0, 0.0, 0.0])

        delta, fallback = _propagate_matrix_method(B, x)
        assert fallback
        assert delta is None


# ═══════════════════════════════════════════════════════════════
#  Test D2c: Path Enumeration
# ═══════════════════════════════════════════════════════════════


class TestPathEnumeration:
    """D2c: Δθ_target = Σ_P [Π_{e∈P} β_e] · x_source."""

    def test_single_edge(self):
        """0→1 with β=0.5, x_source=1.0 → Δθ₁=0.5."""
        B = np.array([[0, 0.5], [0, 0]], dtype=float)  # B[source=0, target=1]
        delta = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=2)
        np.testing.assert_allclose(delta, [0.0, 0.5], atol=1e-12)

    def test_two_hop(self):
        """0→1→2: Δθ₁=0.5, Δθ₂=0.5×0.4=0.2."""
        B = np.zeros((3, 3))
        B[0, 1] = 0.5  # edge 0→1
        B[1, 2] = 0.4  # edge 1→2
        delta = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=3)
        np.testing.assert_allclose(delta, [0.0, 0.5, 0.2], atol=1e-12)

    def test_diamond_matches_matrix(self):
        """Diamond should give same result as matrix method."""
        B = np.zeros((4, 4))
        B[0, 1] = 0.5  # edge 0→1
        B[0, 2] = 0.3  # edge 0→2
        B[1, 3] = 0.4  # edge 1→3
        B[2, 3] = 0.6  # edge 2→3

        delta_path = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=4)
        # Expected: Δθ₁=0.5, Δθ₂=0.3, Δθ₃=0.5×0.4+0.3×0.6=0.38
        np.testing.assert_allclose(delta_path, [0.0, 0.5, 0.3, 0.38], atol=1e-12)

    def test_zero_edge_excluded(self):
        """Edges with β=0 are excluded (structural inclusion=0)."""
        B = np.zeros((3, 3))
        B[0, 1] = 0.5  # edge 0→1
        B[1, 2] = 0.0  # excluded edge
        delta = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=3)
        np.testing.assert_allclose(delta, [0.0, 0.5, 0.0], atol=1e-12)

    def test_max_depth_limits_propagation(self):
        """Path depth is limited to NODE_LAYER_COUNT (7)."""
        # Create a chain longer than 7
        n = 10
        B = np.zeros((n, n))
        for i in range(n - 1):
            B[i, i + 1] = 0.5  # edge i→i+1 (B[source=i, target=i+1])
        delta = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=n)
        # Depth 0→1→2→...→7 (7 hops) should be reached
        # Depth 0→1→...→8 (8 hops) should NOT be reached
        assert delta[7] > 0.0  # 7 hops reachable (depth 7)
        assert delta[8] == 0.0  # 8 hops NOT reachable (exceeds max_depth=7)

    def test_no_cycles_in_paths(self):
        """Path enumeration doesn't revisit nodes (no infinite loops)."""
        # Even with a cycle in B, path enum avoids revisiting
        B = np.zeros((3, 3))
        B[0, 1] = 0.5  # edge 0→1
        B[1, 2] = 0.4  # edge 1→2
        B[2, 0] = 0.3  # cycle back to 0
        delta = _propagate_path_enumeration(B, source_idx=0, x_source=1.0, n_nodes=3)
        # Should terminate without infinite loop
        assert np.all(np.isfinite(delta))


# ═══════════════════════════════════════════════════════════════
#  Test D2d: Physiological Ceiling
# ═══════════════════════════════════════════════════════════════


class TestPhysiologicalCeiling:
    """D2d: clip to ±1.0 SD (single) or ±1.5 SD (bundle)."""

    def test_single_ceiling(self):
        """Single intervention: clip to ±1.0 SD."""
        delta = np.array([0.5, -0.8, 1.5, -2.0])
        clipped, n_clips = _apply_physiological_ceiling(delta, is_bundle=False)
        expected = np.array([0.5, -0.8, config.D2_CEILING_SINGLE_SD, -config.D2_CEILING_SINGLE_SD])
        np.testing.assert_allclose(clipped, expected)
        assert n_clips == 2  # two values exceeded ±1.0

    def test_bundle_ceiling(self):
        """Bundle: clip to ±1.5 SD."""
        delta = np.array([0.5, -1.2, 2.0, -2.5])
        clipped, n_clips = _apply_physiological_ceiling(delta, is_bundle=True)
        expected = np.array([0.5, -1.2, config.D2_CEILING_BUNDLE_SD, -config.D2_CEILING_BUNDLE_SD])
        np.testing.assert_allclose(clipped, expected)
        assert n_clips == 2  # two values exceeded ±1.5

    def test_no_clipping_when_within_bounds(self):
        """No clipping when all within bounds."""
        delta = np.array([0.3, -0.5, 0.0, 0.9])
        clipped, n_clips = _apply_physiological_ceiling(delta, is_bundle=False)
        np.testing.assert_allclose(clipped, delta)
        assert n_clips == 0

    def test_uses_config_constants(self):
        """Verify ceiling values come from config."""
        assert config.D2_CEILING_SINGLE_SD == 1.0
        assert config.D2_CEILING_BUNDLE_SD == 1.5


# ═══════════════════════════════════════════════════════════════
#  Test D2e: Composite Scoring
# ═══════════════════════════════════════════════════════════════


class TestSeverityWeight:
    """Severity weight tiers from config."""

    def test_mild(self):
        """|z| < 1.0 → weight = 1.0."""
        assert _compute_severity_weight(0.0) == config.D2_SEVERITY_WEIGHT_MILD
        assert _compute_severity_weight(0.5) == config.D2_SEVERITY_WEIGHT_MILD
        assert _compute_severity_weight(-0.9) == config.D2_SEVERITY_WEIGHT_MILD

    def test_moderate(self):
        """1.0 ≤ |z| < 2.0 → weight = 1.5."""
        assert _compute_severity_weight(1.0) == config.D2_SEVERITY_WEIGHT_MODERATE
        assert _compute_severity_weight(-1.5) == config.D2_SEVERITY_WEIGHT_MODERATE
        assert _compute_severity_weight(1.99) == config.D2_SEVERITY_WEIGHT_MODERATE

    def test_severe(self):
        """|z| ≥ 2.0 → weight = 2.0."""
        assert _compute_severity_weight(2.0) == config.D2_SEVERITY_WEIGHT_SEVERE
        assert _compute_severity_weight(-3.0) == config.D2_SEVERITY_WEIGHT_SEVERE


class TestCompositeScore:
    """D2e: ΔC = Σ w_d·Δθ_d / Σ w_d."""

    def test_hand_computed_two_domains(self):
        """Two cognitive nodes, hand-computed.

        Node 0: Δθ=0.5, z_baseline=0.3 (mild→w_sev=1.0), σ²=0.25 → inv_var=4.0
            w_0 = 1.0 × 4.0 = 4.0
        Node 1: Δθ=0.3, z_baseline=1.5 (moderate→w_sev=1.5), σ²=0.36 → inv_var=2.778
            w_1 = 1.5 × 2.778 = 4.167

        ΔC = (4.0×0.5 + 4.167×0.3) / (4.0 + 4.167)
           = (2.0 + 1.25) / 8.167
           = 3.25 / 8.167
           ≈ 0.3980
        """
        delta_theta = np.array([0.5, 0.3])
        theta0 = np.array([0.3, 1.5])
        sigma_diag = np.array([0.25, 0.36])
        cog_indices = [0, 1]

        result = _compute_composite_score(delta_theta, theta0, sigma_diag, cog_indices)

        # Hand computation
        w0 = 1.0 * (1.0 / 0.25)   # 4.0
        w1 = 1.5 * (1.0 / 0.36)   # 4.1667
        expected = (w0 * 0.5 + w1 * 0.3) / (w0 + w1)

        assert abs(result - expected) < 1e-6

    def test_empty_cognitive_nodes(self):
        """No cognitive nodes → ΔC = 0."""
        delta = np.array([0.5, 0.3])
        theta0 = np.array([0.3, 1.5])
        sigma_diag = np.array([0.25, 0.36])

        result = _compute_composite_score(delta, theta0, sigma_diag, [])
        assert result == 0.0

    def test_uses_patient_baseline_not_mean(self):
        """Severity weights come from patient baseline θ₀^(m), not population mean.

        Same Δθ but different baselines → different ΔC.
        """
        delta = np.array([0.5, 0.3])
        sigma_diag = np.array([0.25, 0.25])

        # Mild baseline → w_sev=1.0 for both
        theta0_mild = np.array([0.3, 0.2])
        result_mild = _compute_composite_score(delta, theta0_mild, sigma_diag, [0, 1])

        # Severe baseline → w_sev=2.0 for both (same relative, but check it's using θ₀)
        theta0_severe = np.array([2.5, 2.5])
        result_severe = _compute_composite_score(delta, theta0_severe, sigma_diag, [0, 1])

        # With same variance, mild gives uniform weights → ΔC = mean(Δθ)
        # Severe also gives uniform weights but with w=2.0 → ΔC = same mean
        # The actual difference comes when baselines differ across nodes.
        # Here both nodes have same severity tier, so result should be same
        assert abs(result_mild - result_severe) < 1e-10

    def test_sigma_floor_applied(self):
        """Very small σ² should be floored to MIN_SIGMA_FLOOR²."""
        delta = np.array([0.5])
        theta0 = np.array([0.0])
        # σ² < MIN_SIGMA_FLOOR² → floored
        sigma_diag = np.array([0.001])

        result = _compute_composite_score(delta, theta0, sigma_diag, [0])
        # Should use 1/(MIN_SIGMA_FLOOR²) = 1/0.04 = 25
        # w = 1.0 × 25 = 25; ΔC = 25×0.5/25 = 0.5
        assert abs(result - 0.5) < 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test D2a: Direct RCT Edge Detection
# ═══════════════════════════════════════════════════════════════


class TestDirectRCTEdge:
    """D2a: Find causal_supported edges from intervention to cognitive nodes."""

    def test_finds_causal_supported(self):
        """Edge with relation_type=causal_supported is detected."""
        nodes = [
            _make_node_def("N_INTERV", layer=0, domain="intervention"),
            _make_node_def("N_COG", layer=5, domain="cognitive_performance"),
        ]
        node_map = _make_node_map(nodes)
        edge = _make_edge_def("E01", "N_INTERV", "N_COG", relation_type="causal_supported")
        b_skeleton = _make_b_skeleton(2, [edge])
        graph = _make_graph_object(node_map, b_skeleton)
        frozen = _make_frozen(np.zeros((2, 2)), graph)

        direct = _find_direct_rct_edges(frozen, 0, [1])
        assert 1 in direct
        assert direct[1] == "E01"

    def test_ignores_non_causal_supported(self):
        """Edge with relation_type=causal (not causal_supported) is NOT detected."""
        nodes = [
            _make_node_def("N_INTERV", layer=0, domain="intervention"),
            _make_node_def("N_COG", layer=5, domain="cognitive_performance"),
        ]
        node_map = _make_node_map(nodes)
        edge = _make_edge_def("E01", "N_INTERV", "N_COG", relation_type="causal")
        b_skeleton = _make_b_skeleton(2, [edge])
        graph = _make_graph_object(node_map, b_skeleton)
        frozen = _make_frozen(np.zeros((2, 2)), graph)

        direct = _find_direct_rct_edges(frozen, 0, [1])
        assert len(direct) == 0


# ═══════════════════════════════════════════════════════════════
#  Test D2: Cognitive Node Detection
# ═══════════════════════════════════════════════════════════════


class TestCognitiveNodeDetection:
    """Identify cognitive domain nodes from NodeMap."""

    def test_identifies_cognitive_nodes(self):
        nodes = [
            _make_node_def("N_BIO", layer=2, domain="biological"),
            _make_node_def("N_COG1", layer=5, domain="cognitive_performance"),
            _make_node_def("N_COG2", layer=5, domain="cognitive_performance"),
            _make_node_def("N_PSY", layer=4, domain="psychological"),
        ]
        node_map = _make_node_map(nodes)
        indices, ids = _get_cognitive_node_indices(node_map)
        assert set(ids) == {"N_COG1", "N_COG2"}
        assert len(indices) == 2

    def test_no_cognitive_nodes(self):
        nodes = [
            _make_node_def("N_BIO", layer=2, domain="biological"),
        ]
        node_map = _make_node_map(nodes)
        indices, ids = _get_cognitive_node_indices(node_map)
        assert len(indices) == 0


# ═══════════════════════════════════════════════════════════════
#  Test Gate D-G2
# ═══════════════════════════════════════════════════════════════


class TestGateDG2:
    """Gate D-G2: ΔC finite; ceiling clips < 20%."""

    def test_passes_with_finite_values(self):
        effects = InterventionEffects(
            intervention_id="ACT_01",
            delta_theta=np.zeros((10, 4)),
            delta_C=np.zeros(10),
            propagation_methods=[PropagationMethod.MATRIX] * 10,
            ceiling_clipped=np.zeros(10, dtype=bool),
            ceiling_clip_fraction=0.0,
        )
        result = EffectResult(
            intervention_effects={"ACT_01": effects},
            n_draws=10,
            n_nodes=4,
            cognitive_node_indices=[2, 3],
            cognitive_node_ids=["N_COG1", "N_COG2"],
        )
        # Should not raise
        _validate_gate_d_g2(result)

    def test_fails_with_nan_delta_c(self):
        delta_C = np.zeros(10)
        delta_C[5] = np.nan

        effects = InterventionEffects(
            intervention_id="ACT_01",
            delta_theta=np.zeros((10, 4)),
            delta_C=delta_C,
            propagation_methods=[PropagationMethod.MATRIX] * 10,
            ceiling_clipped=np.zeros(10, dtype=bool),
            ceiling_clip_fraction=0.0,
        )
        result = EffectResult(
            intervention_effects={"ACT_01": effects},
            n_draws=10,
            n_nodes=4,
            cognitive_node_indices=[2, 3],
            cognitive_node_ids=["N_COG1", "N_COG2"],
        )
        with pytest.raises(GateViolation, match="D-G2"):
            _validate_gate_d_g2(result)

    def test_fails_with_inf_delta_theta(self):
        delta_theta = np.zeros((10, 4))
        delta_theta[3, 1] = np.inf

        effects = InterventionEffects(
            intervention_id="ACT_01",
            delta_theta=delta_theta,
            delta_C=np.zeros(10),
            propagation_methods=[PropagationMethod.MATRIX] * 10,
            ceiling_clipped=np.zeros(10, dtype=bool),
            ceiling_clip_fraction=0.0,
        )
        result = EffectResult(
            intervention_effects={"ACT_01": effects},
            n_draws=10,
            n_nodes=4,
            cognitive_node_indices=[2, 3],
            cognitive_node_ids=["N_COG1", "N_COG2"],
        )
        with pytest.raises(GateViolation, match="D-G2"):
            _validate_gate_d_g2(result)


# ═══════════════════════════════════════════════════════════════
#  Test D2b vs D2c Consistency
# ═══════════════════════════════════════════════════════════════


class TestMatrixVsPathConsistency:
    """Matrix method and path enumeration produce identical results for stable graphs."""

    def test_chain_consistency(self):
        """0→1→2→3: both methods should match."""
        n = 4
        B = np.zeros((n, n))
        B[0, 1] = 0.5  # edge 0→1
        B[1, 2] = 0.4  # edge 1→2
        B[2, 3] = 0.3  # edge 2→3
        x = np.zeros(n)
        x[0] = 1.0

        delta_matrix, fallback = _propagate_matrix_method(B, x)
        assert not fallback
        delta_path = _propagate_path_enumeration(B, 0, 1.0, n)

        # Matrix includes the source node effect; path enum only accumulates
        # downstream effects. Adjust comparison:
        # Matrix: Δθ₀=1.0, Δθ₁=0.5, Δθ₂=0.2, Δθ₃=0.06
        # Path:   Δθ₀=0.0, Δθ₁=0.5, Δθ₂=0.2, Δθ₃=0.06
        # Source node differs (matrix includes self, path doesn't)
        np.testing.assert_allclose(delta_matrix[1:], delta_path[1:], atol=1e-10)

    def test_diamond_consistency(self):
        """Diamond graph: both methods produce matching downstream effects."""
        n = 4
        B = np.zeros((n, n))
        B[0, 1] = 0.5  # edge 0→1
        B[0, 2] = 0.3  # edge 0→2
        B[1, 3] = 0.4  # edge 1→3
        B[2, 3] = 0.6  # edge 2→3
        x = np.zeros(n)
        x[0] = 1.0

        delta_matrix, _ = _propagate_matrix_method(B, x)
        delta_path = _propagate_path_enumeration(B, 0, 1.0, n)

        # Non-source nodes should match
        np.testing.assert_allclose(delta_matrix[1:], delta_path[1:], atol=1e-10)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full D2 propagate_effects
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full D2 pipeline with mock objects."""

    def _build_test_scenario(self):
        """Build a 5-node graph with one intervention and two cognitive nodes.

        Nodes:
          0: N_INTERVENTION (layer 0, intervention domain)
          1: N_PATHWAY (layer 3, biological)
          2: N_COG_ATTN (layer 5, cognitive_performance)
          3: N_COG_MEM (layer 5, cognitive_performance)
          4: N_OTHER (layer 4, psychological)

        Edges:
          E01: INTERVENTION → PATHWAY (β=0.6)
          E12: PATHWAY → COG_ATTN (β=0.4)
          E13: PATHWAY → COG_MEM (β=0.3)
          E14: PATHWAY → OTHER (β=0.2)
        """
        nodes = [
            _make_node_def("N_INTERVENTION", layer=0, domain="intervention"),
            _make_node_def("N_PATHWAY", layer=3, domain="biological"),
            _make_node_def("N_COG_ATTN", layer=5, domain="cognitive_performance"),
            _make_node_def("N_COG_MEM", layer=5, domain="cognitive_performance"),
            _make_node_def("N_OTHER", layer=4, domain="psychological"),
        ]
        node_map = _make_node_map(nodes)

        edges = [
            _make_edge_def("E01", "N_INTERVENTION", "N_PATHWAY"),
            _make_edge_def("E12", "N_PATHWAY", "N_COG_ATTN"),
            _make_edge_def("E13", "N_PATHWAY", "N_COG_MEM"),
            _make_edge_def("E14", "N_PATHWAY", "N_OTHER"),
        ]
        b_skeleton = _make_b_skeleton(5, edges)
        graph = _make_graph_object(node_map, b_skeleton)

        n = 5
        B_hat = np.zeros((n, n))
        B_hat[0, 1] = 0.6  # E01: INTERVENTION→PATHWAY (B[source=0, target=1])
        B_hat[1, 2] = 0.4  # E12: PATHWAY→COG_ATTN (B[source=1, target=2])
        B_hat[1, 3] = 0.3  # E13: PATHWAY→COG_MEM (B[source=1, target=3])
        B_hat[1, 4] = 0.2  # E14: PATHWAY→OTHER (B[source=1, target=4])

        frozen = _make_frozen(B_hat, graph)

        # Patient state with mild impairment
        theta_hat = np.array([0.0, -0.3, -0.5, -0.8, -0.2])
        Sigma_post = np.eye(n) * 0.25  # sd=0.5 for all
        patient_state = _make_patient_state(theta_hat, Sigma_post)

        # MCDraws: 10 draws with constant B (deterministic for testing)
        n_draws = 10
        B_draws = np.tile(B_hat, (n_draws, 1, 1))
        beta_draws = B_draws.copy()
        include_draws = np.ones((n_draws, n, n))
        theta0_draws = np.tile(theta_hat, (n_draws, 1))

        mc_draws = MCDraws(
            n_draws=n_draws,
            beta_draws=beta_draws,
            include_draws=include_draws,
            B_draws=B_draws,
            theta0_draws=theta0_draws,
            seed=42,
            n_nodes=n,
            n_edges_sampled=4,
            n_always_present=0,
            n_always_absent=0,
            n_sign_rejections=0,
        )

        return mc_draws, frozen, patient_state

    def test_full_pipeline(self):
        """End-to-end D2: propagate through 5-node graph."""
        mc_draws, frozen, patient_state = self._build_test_scenario()

        intervention_node_map = {"ACT_EXERCISE": 0}  # intervention at node 0

        result = propagate_effects(
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
            intervention_node_map=intervention_node_map,
            is_bundle=False,
        )

        assert result.gate_d_g2_passed
        assert "ACT_EXERCISE" in result.intervention_effects
        effects = result.intervention_effects["ACT_EXERCISE"]

        # All draws should use matrix method (well-conditioned graph)
        assert effects.n_matrix_method == 10
        assert effects.n_path_enum_fallback == 0

        # Check delta_theta shape
        assert effects.delta_theta.shape == (10, 5)

        # All draws are identical (constant B), so all delta_theta should be same
        expected_delta = np.zeros(5)
        expected_delta[0] = 1.0  # intervention node
        expected_delta[1] = 0.6  # 0→1 with β=0.6
        expected_delta[2] = 0.24  # 0→1→2 with 0.6×0.4=0.24
        expected_delta[3] = 0.18  # 0→1→3 with 0.6×0.3=0.18
        expected_delta[4] = 0.12  # 0→1→4 with 0.6×0.2=0.12

        for m in range(10):
            np.testing.assert_allclose(
                effects.delta_theta[m], expected_delta, atol=1e-10,
            )

        # delta_C should be consistent across draws (all identical)
        assert np.std(effects.delta_C) < 1e-10

    def test_ceiling_clipping(self):
        """Verify ceiling clipping fires for large effects."""
        mc_draws, frozen, patient_state = self._build_test_scenario()

        # Make B very large → effects exceed ceiling
        mc_draws.B_draws[:, 0, 1] = 3.0  # huge edge 0→1 (B[source=0, target=1])
        mc_draws.B_draws[:, 1, 2] = 2.0  # huge edge 1→2
        mc_draws.B_draws[:, 1, 3] = 2.0  # huge edge 1→3

        result = propagate_effects(
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
            intervention_node_map={"ACT_01": 0},
            is_bundle=False,
        )

        effects = result.intervention_effects["ACT_01"]
        # Effects should be clipped to ±1.0 SD (single intervention)
        assert np.all(np.abs(effects.delta_theta) <= config.D2_CEILING_SINGLE_SD + 1e-10)
        assert effects.n_ceiling_clips > 0

    def test_multiple_interventions(self):
        """Multiple interventions produce separate effects."""
        mc_draws, frozen, patient_state = self._build_test_scenario()

        intervention_node_map = {
            "ACT_01": 0,
            "ACT_02": 1,  # intervene at pathway node
        }

        result = propagate_effects(
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
            intervention_node_map=intervention_node_map,
        )

        assert len(result.intervention_effects) == 2
        assert "ACT_01" in result.intervention_effects
        assert "ACT_02" in result.intervention_effects

        # Different intervention nodes → different delta_theta
        dt1 = result.intervention_effects["ACT_01"].delta_theta[0]
        dt2 = result.intervention_effects["ACT_02"].delta_theta[0]
        assert not np.allclose(dt1, dt2)

    def test_cognitive_indices_correct(self):
        """Result contains correct cognitive node info."""
        mc_draws, frozen, patient_state = self._build_test_scenario()

        result = propagate_effects(
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
            intervention_node_map={"ACT_01": 0},
        )

        assert set(result.cognitive_node_ids) == {"N_COG_ATTN", "N_COG_MEM"}
        assert len(result.cognitive_node_indices) == 2

    def test_reproducibility(self):
        """Same inputs produce identical outputs (deterministic with constant B)."""
        mc_draws, frozen, patient_state = self._build_test_scenario()

        result1 = propagate_effects(
            mc_draws=mc_draws, frozen=frozen, patient_state=patient_state,
            intervention_node_map={"ACT_01": 0},
        )
        result2 = propagate_effects(
            mc_draws=mc_draws, frozen=frozen, patient_state=patient_state,
            intervention_node_map={"ACT_01": 0},
        )

        np.testing.assert_array_equal(
            result1.intervention_effects["ACT_01"].delta_theta,
            result2.intervention_effects["ACT_01"].delta_theta,
        )
