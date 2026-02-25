"""Tests for ALG-B: Edge Parameterization.

Tests cover:
- B1: IVW pooling with hand-computable expected values
- B2: Seven-layer SE_eff computation
- B3: Prior selection decision tree
- B4: Structural inclusion probability (logistic formula)
- B5: Turner et al. τ² priors
- B6: Chain-vs-direct validation
- B7: FrozenModelState assembly
- Gate violations
- Integration with Chain A GraphObject
"""
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_b_evidence.evidence_compiler import (
    ChainDirectResult,
    EdgePriorSpec,
    EvidenceRecord,
    HeterogeneityAdjustedEdge,
    InclusionProbEdge,
    PooledEdge,
    TauSquaredPrior,
    _compute_ivw,
    _get_attenuation_factor,
    _select_aggregation_method,
    compute_p_inclusion,
    compute_se_eff,
    pool_edge,
    select_prior,
    assign_tau_sq_prior,
    validate_chain_vs_direct,
    _validate_gate_b_g1,
    _validate_gate_b_g2,
)
from crci.algorithm.chain_b_evidence.frozen_state import (
    ContextPriorSpec,
    FrozenModelState,
    SynergyRecord,
    assemble_frozen_state,
    build_b_hat_matrix,
    compile_context_priors,
    _compute_frozen_hash,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures: Mini GraphObject for testing
# ═══════════════════════════════════════════════════════════════


def _make_mini_graph():
    """Create a minimal 5-node, 4-edge GraphObject for testing.

    Graph: N0 → N1 → N3
           N0 → N2 → N3
                N2 → N4 (chain: N0→N2→N4 gives indirect for N0→N4)
    """
    from crci.algorithm.chain_a_graph.node_loader import NodeDef, NodeMap
    from crci.algorithm.chain_a_graph.edge_loader import EdgeDef, HillParams, BSkeleton
    from crci.algorithm.chain_a_graph.instrument_loader import InstrumentDef, InstrumentMap
    from crci.algorithm.chain_a_graph.spectral_validator import (
        DMatrix, LambdaStructure, CorrelationPair,
    )
    from crci.algorithm.chain_a_graph.graph_object import GraphObject

    nodes = [
        NodeDef(node_id="N0", node_label="Exo", layer=0,
                clinical_domain="exo", is_observable=True, is_latent=False,
                orientation="none", unit_of_measure="", pathway_membership=[],
                proxy_for=None, proxy_r_squared=None, description=""),
        NodeDef(node_id="N1", node_label="Bio1", layer=1,
                clinical_domain="bio", is_observable=True, is_latent=False,
                orientation="negative", unit_of_measure="mg/L", pathway_membership=[],
                proxy_for=None, proxy_r_squared=None, description=""),
        NodeDef(node_id="N2", node_label="Bio2", layer=1,
                clinical_domain="bio", is_observable=True, is_latent=False,
                orientation="positive", unit_of_measure="ng/mL", pathway_membership=[],
                proxy_for=None, proxy_r_squared=None, description=""),
        NodeDef(node_id="N3", node_label="Cog", layer=3,
                clinical_domain="cog", is_observable=True, is_latent=False,
                orientation="positive", unit_of_measure="score", pathway_membership=[],
                proxy_for=None, proxy_r_squared=None, description=""),
        NodeDef(node_id="N4", node_label="Sym", layer=4,
                clinical_domain="sym", is_observable=True, is_latent=False,
                orientation="negative", unit_of_measure="score", pathway_membership=[],
                proxy_for=None, proxy_r_squared=None, description=""),
    ]

    node_index = {n.node_id: i for i, n in enumerate(nodes)}
    node_map = NodeMap(
        nodes=nodes,
        node_index=node_index,
        layer_assignment={n.node_id: n.layer for n in nodes},
        domain_assignment={n.node_id: n.clinical_domain for n in nodes},
        observability={n.node_id: n.is_observable for n in nodes},
        orientation={n.node_id: n.orientation for n in nodes},
        topological_order=["N0", "N1", "N2", "N3", "N4"],
        nodes_by_layer={0: ["N0"], 1: ["N1", "N2"], 3: ["N3"], 4: ["N4"]},
        n_observable=5,
        n_latent=0,
    )

    edges = [
        EdgeDef(edge_id="E01", source_node_id="N0", target_node_id="N1",
                relation_type="causal", mechanism_description="",
                primary_pathway="", secondary_pathways=[],
                expected_sign="-", functional_form="linear",
                fallback_form="linear", is_feedback_edge=False,
                feedback_loop_id=None),
        EdgeDef(edge_id="E02", source_node_id="N0", target_node_id="N2",
                relation_type="causal", mechanism_description="",
                primary_pathway="", secondary_pathways=[],
                expected_sign="+", functional_form="linear",
                fallback_form="linear", is_feedback_edge=False,
                feedback_loop_id=None),
        EdgeDef(edge_id="E13", source_node_id="N1", target_node_id="N3",
                relation_type="causal", mechanism_description="",
                primary_pathway="", secondary_pathways=[],
                expected_sign="-", functional_form="linear",
                fallback_form="linear", is_feedback_edge=False,
                feedback_loop_id=None),
        EdgeDef(edge_id="E23", source_node_id="N2", target_node_id="N3",
                relation_type="causal", mechanism_description="",
                primary_pathway="", secondary_pathways=[],
                expected_sign="+", functional_form="linear",
                fallback_form="linear", is_feedback_edge=False,
                feedback_loop_id=None),
        EdgeDef(edge_id="E24", source_node_id="N2", target_node_id="N4",
                relation_type="causal", mechanism_description="",
                primary_pathway="", secondary_pathways=[],
                expected_sign="-", functional_form="linear",
                fallback_form="linear", is_feedback_edge=False,
                feedback_loop_id=None),
    ]

    edge_index = {e.edge_id: i for i, e in enumerate(edges)}
    n = 5
    B_struct = np.zeros((n, n))
    B_struct[0, 1] = -1  # N0→N1
    B_struct[0, 2] = 1   # N0→N2
    B_struct[1, 3] = -1  # N1→N3
    B_struct[2, 3] = 1   # N2→N3
    B_struct[2, 4] = -1  # N2→N4

    b_skeleton = BSkeleton(
        n_nodes=n,
        n_edges=5,
        edges=edges,
        edge_index=edge_index,
        B_struct=B_struct,
        functional_forms={e.edge_id: "linear" for e in edges},
        hill_params={},
        edge_claim_levels={e.edge_id: "causal" for e in edges},
        feedback_edges=[],
        forward_edges=[e.edge_id for e in edges],
    )

    instrument_map = InstrumentMap(
        instruments=[],
        instrument_index={},
        node_to_instruments={},
        H=np.eye(n),
        observation_noise_var={},
        intercepts={},
    )

    D = np.eye(n) * 0.8
    d_matrix = DMatrix(
        D=D,
        residual_variances=np.full(n, 0.8),
        R_squared_per_node=np.full(n, 0.2),
        correlation_pairs=[],
        D_blocks={},
        is_positive_definite=True,
    )

    I_minus_B = np.eye(n) - B_struct * 0.1
    D_inv = np.linalg.inv(D)
    Lambda = I_minus_B.T @ D_inv @ I_minus_B
    Lambda = (Lambda + Lambda.T) / 2.0

    lambda_structure = LambdaStructure(
        Lambda=Lambda,
        is_positive_definite=True,
        condition_number=float(np.linalg.cond(Lambda)),
        sparsity_pattern=set(),
        spectral_radius_B=0.1,
    )

    graph = GraphObject(
        node_map=node_map,
        b_skeleton=b_skeleton,
        instrument_map=instrument_map,
        d_matrix=d_matrix,
        lambda_structure=lambda_structure,
        n_nodes=n,
        n_edges=5,
    )

    return graph


def _make_evidence(
    edge_id: str,
    beta: float,
    se: float,
    study_id: str = "S001",
    design: str = "large_rct",
    year: int = 2023,
    n: int = 200,
    identification: str = "identified",
    grade: str = "HIGH",
    outcome: str = "semi_objective",
) -> EvidenceRecord:
    """Helper to create test evidence records."""
    return EvidenceRecord(
        study_id=study_id,
        edge_id=edge_id,
        beta=beta,
        se=se,
        study_design=design,
        publication_year=year,
        sample_size=n,
        identification_status=identification,
        quality_grade=grade,
        scope_weights={"cancer": 1.0, "phase": 1.0, "regimen": 1.0, "age": 1.0, "sex": 1.0},
        cancer_validation_status="validated_cancer",
        temporal_distance_days=0.0,
        outcome_type=outcome,
        has_rct_component=(design in ("large_rct", "small_rct_default")),
    )


# ═══════════════════════════════════════════════════════════════
#  B1: IVW Pooling Tests
# ═══════════════════════════════════════════════════════════════


class TestIVWPooling:
    """Test B1 IVW pooling with hand-computable values."""

    def test_ivw_two_studies(self):
        """Hand computation: 2 studies with β=[0.3, 0.5], SE=[0.1, 0.2].

        w1 = 1/0.01 = 100, w2 = 1/0.04 = 25
        μ_e = (0.3*100 + 0.5*25) / (100+25) = (30+12.5)/125 = 0.34
        SE_within = 1/√125 ≈ 0.0894
        Q = 100*(0.3-0.34)² + 25*(0.5-0.34)² = 100*0.0016 + 25*0.0256
          = 0.16 + 0.64 = 0.80
        τ² = max(0, (0.80-1)/(125-500/125)) = max(0, -0.20/121) = 0
        I² = max(0, (0.80-1)/0.80) = 0
        """
        mu, se, Q, tau_sq, I_sq = _compute_ivw([0.3, 0.5], [0.1, 0.2])

        assert abs(mu - 0.34) < 1e-6
        assert abs(se - 1.0 / math.sqrt(125)) < 1e-6
        assert abs(Q - 0.80) < 1e-6
        assert tau_sq == 0.0  # Q < k-1
        assert I_sq == 0.0

    def test_ivw_heterogeneous(self):
        """3 studies with high heterogeneity: β=[-0.5, 0.2, 0.8], SE=[0.1, 0.1, 0.1].

        All equal precision → w_i = 100 each, sum_w = 300
        μ = (-0.5+0.2+0.8)/3 × 100 / (300/3) = 0.1667
        Q = 100 × [(-0.5-0.1667)² + (0.2-0.1667)² + (0.8-0.1667)²]
          = 100 × [0.4444 + 0.0011 + 0.4011] = 84.67
        I² = max(0, (84.67-2)/84.67) = 0.9764
        """
        mu, se, Q, tau_sq, I_sq = _compute_ivw([-0.5, 0.2, 0.8], [0.1, 0.1, 0.1])

        # μ = Σ(β/σ²)/Σ(1/σ²) = ((-0.5+0.2+0.8)*100)/300 = 50/300
        expected_mu = (-0.5 + 0.2 + 0.8) / 3.0
        assert abs(mu - expected_mu) < 1e-6
        assert I_sq > 0.95  # high heterogeneity

    def test_pool_edge_k0_blocked(self):
        """k=0 → BLOCKED with μ_e=0, SE=inf."""
        pooled = pool_edge("E_test", [])
        assert pooled.aggregation_method == "BLOCKED"
        assert pooled.mu_e == 0.0
        assert pooled.SE_within == float("inf")
        assert pooled.k == 0

    def test_pool_edge_k1_direct(self):
        """k=1 → DIRECT passthrough with attenuation."""
        rec = _make_evidence("E_test", beta=0.4, se=0.15, identification="partially_identified")
        pooled = pool_edge("E_test", [rec])

        assert pooled.aggregation_method == "DIRECT"
        assert pooled.k == 1
        expected_mu = 0.4 * config.IDENTIFICATION_FACTOR_PARTIAL
        assert abs(pooled.mu_e - expected_mu) < 1e-6
        assert abs(pooled.attenuation_factor - config.IDENTIFICATION_FACTOR_PARTIAL) < 1e-6

    def test_pool_edge_k2_fixed(self):
        """k=2, low heterogeneity → IVW_FIXED."""
        recs = [
            _make_evidence("E_test", beta=0.30, se=0.10, study_id="S1"),
            _make_evidence("E_test", beta=0.32, se=0.12, study_id="S2"),
        ]
        pooled = pool_edge("E_test", recs)

        assert pooled.aggregation_method == "IVW_FIXED"
        assert pooled.k == 2
        assert 0.29 < pooled.mu_e < 0.33  # close to weighted mean

    def test_attenuation_factors(self):
        """Verify all 4 identification status mappings."""
        assert _get_attenuation_factor("identified") == 1.00
        assert _get_attenuation_factor("partially_identified") == 0.85
        assert _get_attenuation_factor("plausible") == 0.70
        assert _get_attenuation_factor("unidentified") == 0.50

    def test_aggregation_sign_conflict_blocks(self):
        """High-quality studies with conflicting signs → BLOCKED."""
        recs = [
            _make_evidence("E_test", beta=0.5, se=0.1, study_id="S1", grade="HIGH"),
            _make_evidence("E_test", beta=-0.3, se=0.1, study_id="S2", grade="HIGH"),
        ]
        method = _select_aggregation_method(recs, I_sq=0.1)
        assert method == "BLOCKED"


# ═══════════════════════════════════════════════════════════════
#  B2: Seven-Layer SE Tests
# ═══════════════════════════════════════════════════════════════


class TestSevenLayerSE:
    """Test B2 seven-layer SE_eff computation."""

    def test_se_eff_basic(self):
        """SE_eff with known layer contributions.

        Setup: SE_within=0.1, m_claim=1.0 (large_rct), m_grade=1.0 (HIGH),
               m_temporal=1.0, w_scope=1.0, w_fresh=1.0, σ²_struct=0.25, τ²=0
        Fixed method → τ² not added

        SE_eff = √[(0.1×1.0×1.0×1.0)² + 0.25 + 0] / (1.0×1.0)
               = √[0.01 + 0.25] / 1.0
               = √0.26 ≈ 0.5099
        """
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.3, SE_within=0.1,
            tau_sq=0.0, k=3, I_sq=0.1,
            aggregation_method="IVW_FIXED",
            contributing_studies=["S1", "S2", "S3"],
            attenuation_factor=1.0,
        )
        recs = [
            _make_evidence("E_test", 0.3, 0.1, study_id=f"S{i}",
                           design="large_rct", grade="HIGH", year=2026)
            for i in range(3)
        ]

        adj = compute_se_eff(pooled, recs)

        expected = math.sqrt(0.1 ** 2 + config.SIGMA_SQ_STRUCTURAL_DEFAULT)
        assert abs(adj.SE_eff - expected) < 0.01
        assert adj.w_scope == 1.0
        assert adj.w_fresh == 1.0

    def test_se_eff_with_grade_inflation(self):
        """GRADE LOW inflates SE by 1.5×."""
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.3, SE_within=0.1,
            tau_sq=0.0, k=1, I_sq=0.0,
            aggregation_method="DIRECT",
            contributing_studies=["S1"],
            attenuation_factor=1.0,
        )
        rec = _make_evidence("E_test", 0.3, 0.1, grade="LOW", year=2026)
        adj = compute_se_eff(pooled, [rec])

        # m_grade=1.5 → multiplicative SE = 0.1 × 1.0 × 1.5 × 1.0 = 0.15
        assert adj.layer_contributions["L5_grade"] == pytest.approx(
            config.GRADE_MULTIPLIERS["LOW"], abs=0.01
        )

    def test_se_eff_blocked_returns_inf(self):
        """BLOCKED edge → SE_eff = inf."""
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.0, SE_within=float("inf"),
            tau_sq=0.0, k=0, I_sq=0.0,
            aggregation_method="BLOCKED",
            contributing_studies=[], attenuation_factor=1.0,
        )
        adj = compute_se_eff(pooled, [])
        assert adj.SE_eff == float("inf")

    def test_freshness_decay(self):
        """Old study (2000) → w_fresh = max(0.70, 1-0.015×26) = 0.61 → capped at 0.70."""
        rec = _make_evidence("E_test", 0.3, 0.1, year=2000)
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.3, SE_within=0.1,
            tau_sq=0.0, k=1, I_sq=0.0,
            aggregation_method="DIRECT",
            contributing_studies=["S1"], attenuation_factor=1.0,
        )
        adj = compute_se_eff(pooled, [rec])
        assert adj.w_fresh == pytest.approx(config.FRESHNESS_FLOOR, abs=0.01)


# ═══════════════════════════════════════════════════════════════
#  B3: Prior Selection Tests
# ═══════════════════════════════════════════════════════════════


class TestPriorSelection:
    """Test B3 prior selection decision tree."""

    def test_robust_map_k5_prospective(self):
        """k≥5, best_design ≥ prospective → RobustMAP."""
        graph = _make_mini_graph()
        adj = HeterogeneityAdjustedEdge(
            edge_id="E01", mu_e=0.3, SE_within=0.05,
            tau_sq=0.01, k=6, I_sq=0.2,
            aggregation_method="IVW_FIXED",
            contributing_studies=[f"S{i}" for i in range(6)],
            attenuation_factor=1.0, SE_eff=0.52,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E01", 0.3, 0.05, study_id=f"S{i}", design="large_rct")
                for i in range(6)]

        prior = select_prior(adj, recs, graph)

        assert prior.prior_type == "RobustMAP"
        # w = min(0.8, 0.5 + 0.06×6) = min(0.8, 0.86) = 0.8
        assert prior.prior_params["w"] == pytest.approx(config.B3_ROBUST_MAP_W_MAX, abs=0.001)

    def test_robust_map_w_formula(self):
        """Verify w = min(0.8, 0.5 + 0.06k) for k=5."""
        graph = _make_mini_graph()
        adj = HeterogeneityAdjustedEdge(
            edge_id="E01", mu_e=0.3, SE_within=0.05,
            tau_sq=0.01, k=5, I_sq=0.2,
            aggregation_method="IVW_FIXED",
            contributing_studies=[f"S{i}" for i in range(5)],
            attenuation_factor=1.0, SE_eff=0.52,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E01", 0.3, 0.05, study_id=f"S{i}", design="well_adjusted_cohort")
                for i in range(5)]

        prior = select_prior(adj, recs, graph)
        # w = min(0.8, 0.5 + 0.06×5) = min(0.8, 0.80) = 0.80
        assert prior.prior_params["w"] == pytest.approx(0.80, abs=0.001)

    def test_commensurate_k3(self):
        """k ∈ [2,4] → Commensurate."""
        graph = _make_mini_graph()
        adj = HeterogeneityAdjustedEdge(
            edge_id="E01", mu_e=0.3, SE_within=0.05,
            tau_sq=0.01, k=3, I_sq=0.2,
            aggregation_method="IVW_FIXED",
            contributing_studies=["S1", "S2", "S3"],
            attenuation_factor=1.0, SE_eff=0.52,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E01", 0.3, 0.05, study_id=f"S{i}")
                for i in range(3)]

        prior = select_prior(adj, recs, graph)
        assert prior.prior_type == "Commensurate"

    def test_power_prior_k1(self):
        """k=1 → PowerPrior."""
        graph = _make_mini_graph()
        adj = HeterogeneityAdjustedEdge(
            edge_id="E01", mu_e=0.3, SE_within=0.1,
            tau_sq=0.0, k=1, I_sq=0.0,
            aggregation_method="DIRECT",
            contributing_studies=["S1"],
            attenuation_factor=1.0, SE_eff=0.52,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E01", 0.3, 0.1, design="large_rct")]

        prior = select_prior(adj, recs, graph)
        assert prior.prior_type == "PowerPrior"
        assert prior.prior_params["a0"] == config.B3_POWER_PRIOR_A0["rct_same"]

    def test_structural_placeholder_k0(self):
        """k=0, no chain → StructuralPlaceholder."""
        graph = _make_mini_graph()
        adj = HeterogeneityAdjustedEdge(
            edge_id="E01", mu_e=0.0, SE_within=float("inf"),
            tau_sq=0.0, k=0, I_sq=0.0,
            aggregation_method="BLOCKED",
            contributing_studies=[],
            attenuation_factor=1.0, SE_eff=float("inf"),
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=0.3, w_fresh=0.7,
        )
        prior = select_prior(adj, [], graph, all_adjusted={})
        assert prior.prior_type == "StructuralPlaceholder"
        assert prior.prior_params["sigma_sq"] == config.B3_STRUCTURAL_PLACEHOLDER_VAR


# ═══════════════════════════════════════════════════════════════
#  B4: Structural Inclusion Probability Tests
# ═══════════════════════════════════════════════════════════════


class TestInclusionProbability:
    """Test B4 logistic inclusion formula with calibration targets."""

    def test_calibration_k0_z0_no_rct(self):
        """Calibration (i): k=0, Z=0, no RCT → P ≈ 0.38."""
        adj = HeterogeneityAdjustedEdge(
            edge_id="E_test", mu_e=0.0, SE_within=float("inf"),
            tau_sq=0.0, k=0, I_sq=0.0,
            aggregation_method="BLOCKED",
            contributing_studies=[], attenuation_factor=1.0,
            SE_eff=float("inf"),
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=0.3, w_fresh=0.7,
        )
        incl = compute_p_inclusion(adj, [])

        # linear = -0.5 + 1.2×ln(1) + 0.4×0 + 0.6×0 = -0.5
        # P = 1/(1+exp(0.5)) = 1/1.649 ≈ 0.378
        assert abs(incl.P_inclusion - 0.378) < 0.02

    def test_calibration_k3_moderate_z(self):
        """Calibration (ii): k=3, moderate Z → P ≈ 0.80."""
        adj = HeterogeneityAdjustedEdge(
            edge_id="E_test", mu_e=0.6, SE_within=0.1,
            tau_sq=0.01, k=3, I_sq=0.1,
            aggregation_method="IVW_FIXED",
            contributing_studies=["S1", "S2", "S3"],
            attenuation_factor=1.0, SE_eff=0.3,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E_test", 0.6, 0.1, study_id=f"S{i}")
                for i in range(3)]

        incl = compute_p_inclusion(adj, recs)

        # Z = |0.6|/0.3 = 2.0
        # linear = -0.5 + 1.2×ln(4) + 0.4×2.0 + 0.6×1.0
        #        = -0.5 + 1.663 + 0.8 + 0.6 = 2.563
        # P = 1/(1+exp(-2.563)) ≈ 0.928
        assert incl.P_inclusion > 0.75

    def test_calibration_k5_z3_rct(self):
        """Calibration (iv): k≥5, Z>3, RCT → P ≈ 0.99."""
        adj = HeterogeneityAdjustedEdge(
            edge_id="E_test", mu_e=1.5, SE_within=0.05,
            tau_sq=0.01, k=6, I_sq=0.1,
            aggregation_method="IVW_FIXED",
            contributing_studies=[f"S{i}" for i in range(6)],
            attenuation_factor=1.0, SE_eff=0.4,
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=1.0, w_fresh=1.0,
        )
        recs = [_make_evidence("E_test", 1.5, 0.1, study_id=f"S{i}")
                for i in range(6)]

        incl = compute_p_inclusion(adj, recs)
        # Z = 1.5/0.4 = 3.75
        # linear = -0.5 + 1.2×ln(7) + 0.4×3.75 + 0.6×1 = -0.5+2.334+1.5+0.6 = 3.934
        # P = 1/(1+exp(-3.934)) ≈ 0.981
        assert incl.P_inclusion > 0.95

    def test_p_inclusion_clamped(self):
        """P_inclusion clamped to [P_INCLUSION_MIN, P_INCLUSION_ADJ_CAP]."""
        adj = HeterogeneityAdjustedEdge(
            edge_id="E_test", mu_e=0.0, SE_within=float("inf"),
            tau_sq=0.0, k=0, I_sq=0.0,
            aggregation_method="BLOCKED",
            contributing_studies=[], attenuation_factor=1.0,
            SE_eff=float("inf"),
            layer_contributions={}, sigma_sq_structural=0.25,
            w_scope=0.3, w_fresh=0.7,
        )
        incl = compute_p_inclusion(adj, [])
        assert incl.P_inclusion >= config.P_INCLUSION_MIN
        assert incl.P_inclusion <= config.P_INCLUSION_ADJ_CAP


# ═══════════════════════════════════════════════════════════════
#  B5: Turner τ² Prior Tests
# ═══════════════════════════════════════════════════════════════


class TestTurnerPriors:
    """Test B5 empirical τ² prior assignment."""

    def test_subjective_outcome(self):
        """Subjective → LogNormal(-2.13, 1.58²), median ≈ 0.12."""
        graph = _make_mini_graph()
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.3, SE_within=0.1,
            tau_sq=0.01, k=3, I_sq=0.1,
            aggregation_method="IVW_FIXED",
            contributing_studies=["S1", "S2", "S3"],
            attenuation_factor=1.0,
        )
        recs = [_make_evidence("E_test", 0.3, 0.1, outcome="subjective")]

        tp = assign_tau_sq_prior(pooled, recs, graph)
        assert tp.outcome_type == "subjective"
        assert tp.log_mu == config.B5_TURNER_SUBJECTIVE_LOG_MU
        assert tp.log_sigma == config.B5_TURNER_SUBJECTIVE_LOG_SIGMA
        assert abs(tp.median_tau_sq - math.exp(-2.13)) < 0.01

    def test_biomarker_outcome(self):
        """Biomarker → same as semi-objective."""
        graph = _make_mini_graph()
        pooled = PooledEdge(
            edge_id="E_test", mu_e=0.3, SE_within=0.1,
            tau_sq=0.01, k=2, I_sq=0.1,
            aggregation_method="IVW_FIXED",
            contributing_studies=["S1", "S2"],
            attenuation_factor=1.0,
        )
        recs = [_make_evidence("E_test", 0.3, 0.1, outcome="biomarker")]

        tp = assign_tau_sq_prior(pooled, recs, graph)
        assert tp.log_mu == config.B5_TURNER_SEMIOBJECTIVE_LOG_MU
        assert tp.log_sigma == config.B5_TURNER_SEMIOBJECTIVE_LOG_SIGMA


# ═══════════════════════════════════════════════════════════════
#  B6: Chain-vs-Direct Validation Tests
# ═══════════════════════════════════════════════════════════════


class TestChainVsDirect:
    """Test B6 chain-vs-direct validation."""

    def test_no_chain_evidence_pass(self):
        """Edge with only direct evidence → Pass."""
        graph = _make_mini_graph()
        adjusted = {
            "E01": HeterogeneityAdjustedEdge(
                edge_id="E01", mu_e=0.3, SE_within=0.05,
                tau_sq=0.0, k=3, I_sq=0.1,
                aggregation_method="IVW_FIXED",
                contributing_studies=["S1", "S2", "S3"],
                attenuation_factor=1.0, SE_eff=0.52,
                layer_contributions={}, sigma_sq_structural=0.25,
                w_scope=1.0, w_fresh=1.0,
            ),
        }
        result = validate_chain_vs_direct("E01", adjusted, graph)
        assert result.triage_action == "Pass"
        assert result.se_multiplier == config.B6_SE_MULT_PASS

    def test_av_formula(self):
        """AV(e) = 1 − min(Z/3.0, 1.0)."""
        # Z=1.5 → AV = 1 - 0.5 = 0.5
        # Z=0 → AV = 1.0
        # Z=3.0 → AV = 0.0
        # Z=6.0 → AV = 0.0 (clamped)
        av_z0 = 1.0 - min(0.0 / config.B6_AV_Z_DIVISOR, 1.0)
        av_z15 = 1.0 - min(1.5 / config.B6_AV_Z_DIVISOR, 1.0)
        av_z30 = 1.0 - min(3.0 / config.B6_AV_Z_DIVISOR, 1.0)
        av_z60 = 1.0 - min(6.0 / config.B6_AV_Z_DIVISOR, 1.0)

        assert av_z0 == pytest.approx(1.0)
        assert av_z15 == pytest.approx(0.5)
        assert av_z30 == pytest.approx(0.0)
        assert av_z60 == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════
#  B7: FrozenModelState Assembly Tests
# ═══════════════════════════════════════════════════════════════


class TestFrozenModelState:
    """Test B7 FrozenModelState assembly."""

    def test_b_hat_matrix_shape(self):
        """B̂ matrix has shape (n_nodes, n_nodes)."""
        graph = _make_mini_graph()
        adjusted = {
            "E01": HeterogeneityAdjustedEdge(
                edge_id="E01", mu_e=-0.3, SE_within=0.05,
                tau_sq=0.0, k=3, I_sq=0.1,
                aggregation_method="IVW_FIXED",
                contributing_studies=["S1", "S2", "S3"],
                attenuation_factor=1.0, SE_eff=0.52,
                layer_contributions={}, sigma_sq_structural=0.25,
                w_scope=1.0, w_fresh=1.0,
            ),
        }
        B_hat = build_b_hat_matrix(graph, adjusted, {})
        assert B_hat.shape == (5, 5)
        # E01: N0→N1, node_index N0=0, N1=1
        assert B_hat[0, 1] == pytest.approx(-0.3)

    def test_b_hat_blocked_is_zero(self):
        """BLOCKED edges have 0 in B̂."""
        graph = _make_mini_graph()
        adjusted = {
            "E01": HeterogeneityAdjustedEdge(
                edge_id="E01", mu_e=0.0, SE_within=float("inf"),
                tau_sq=0.0, k=0, I_sq=0.0,
                aggregation_method="BLOCKED",
                contributing_studies=[],
                attenuation_factor=1.0, SE_eff=float("inf"),
                layer_contributions={}, sigma_sq_structural=0.25,
                w_scope=0.3, w_fresh=0.7,
            ),
        }
        B_hat = build_b_hat_matrix(graph, adjusted, {})
        assert B_hat[0, 1] == 0.0

    def test_lambda_prior_positive_definite(self):
        """All context priors should be PD."""
        graph = _make_mini_graph()
        B_hat = np.zeros((5, 5))
        B_hat[0, 1] = -0.2
        B_hat[0, 2] = 0.15

        Lambda_prior = compile_context_priors(graph, B_hat)

        assert "general_cancer" in Lambda_prior
        L = Lambda_prior["general_cancer"]
        # Verify PD via Cholesky
        np.linalg.cholesky(L)  # should not raise

    def test_sha256_deterministic(self):
        """SHA-256 hash is deterministic for same inputs."""
        B = np.array([[0.0, 0.3], [0.0, 0.0]])
        sigma = {"E01": 0.5}
        p_incl = {"E01": 0.8}

        h1 = _compute_frozen_hash(B, sigma, p_incl)
        h2 = _compute_frozen_hash(B, sigma, p_incl)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_sha256_changes_with_input(self):
        """SHA-256 changes when inputs change."""
        B1 = np.array([[0.0, 0.3], [0.0, 0.0]])
        B2 = np.array([[0.0, 0.4], [0.0, 0.0]])
        sigma = {"E01": 0.5}
        p_incl = {"E01": 0.8}

        h1 = _compute_frozen_hash(B1, sigma, p_incl)
        h2 = _compute_frozen_hash(B2, sigma, p_incl)
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════
#  Gate Violation Tests
# ═══════════════════════════════════════════════════════════════


class TestGateViolations:
    """Test that gates raise on failure."""

    def test_gate_b_g1_nan_mu(self):
        """B-G1: NaN μ_e for non-BLOCKED → raises."""
        edges = {
            "E01": PooledEdge(
                edge_id="E01", mu_e=float("nan"), SE_within=0.1,
                tau_sq=0.0, k=2, I_sq=0.0,
                aggregation_method="IVW_FIXED",
            ),
        }
        with pytest.raises(GateViolation, match="B-G1"):
            _validate_gate_b_g1(edges)

    def test_gate_b_g2_se_zero(self):
        """B-G2: SE_eff ≤ 0 for non-BLOCKED → raises."""
        edges = {
            "E01": HeterogeneityAdjustedEdge(
                edge_id="E01", mu_e=0.3, SE_within=0.1,
                tau_sq=0.0, k=2, I_sq=0.1,
                aggregation_method="IVW_FIXED",
                contributing_studies=["S1", "S2"],
                attenuation_factor=1.0, SE_eff=0.0,
                layer_contributions={}, sigma_sq_structural=0.25,
                w_scope=1.0, w_fresh=1.0,
            ),
        }
        with pytest.raises(GateViolation, match="B-G2"):
            _validate_gate_b_g2(edges)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full Chain B Pipeline
# ═══════════════════════════════════════════════════════════════


class TestChainBIntegration:
    """Integration test: run Chain B on mini GraphObject with synthetic evidence."""

    def test_full_pipeline_with_evidence(self):
        """Run full Chain B with synthetic evidence records."""
        from crci.algorithm.chain_b_evidence.frozen_state import run_chain_b

        graph = _make_mini_graph()

        # Create evidence records for 3 of 5 edges
        evidence = [
            # E01: 3 studies → IVW
            _make_evidence("E01", -0.3, 0.10, study_id="S1a", design="large_rct"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b", design="well_adjusted_cohort"),
            _make_evidence("E01", -0.35, 0.08, study_id="S1c", design="large_rct"),
            # E02: 1 study → DIRECT
            _make_evidence("E02", 0.2, 0.15, study_id="S2a", design="cross_sectional_adjusted",
                           grade="MODERATE", identification="plausible"),
            # E13: 2 studies → IVW
            _make_evidence("E13", -0.4, 0.10, study_id="S3a", design="large_rct"),
            _make_evidence("E13", -0.38, 0.11, study_id="S3b", design="large_rct"),
            # E23 and E24 have no evidence → BLOCKED → StructuralPlaceholder
        ]

        frozen = run_chain_b(graph, evidence)

        # Verify FrozenModelState
        assert frozen.B_hat.shape == (5, 5)
        assert frozen.n_edges_parameterized >= 3  # E01, E02, E13 parameterized
        assert frozen.n_edges_blocked >= 2  # E23, E24 blocked
        assert len(frozen.Sigma_eff) == 5  # all edges have SE_eff
        assert len(frozen.P_inclusion) == 5
        assert frozen.sha256_hash  # hash computed
        assert "general_cancer" in frozen.Lambda_prior

        # Prior types should include both RobustMAP-eligible and others
        prior_types = {ps.prior_type for ps in frozen.prior_audit_trail.values()}
        assert "StructuralPlaceholder" in prior_types  # E23, E24 have k=0

    def test_pipeline_no_evidence(self):
        """Run Chain B with zero evidence → all BLOCKED."""
        from crci.algorithm.chain_b_evidence.frozen_state import run_chain_b

        graph = _make_mini_graph()
        frozen = run_chain_b(graph, [])

        assert frozen.n_edges_parameterized == 0
        assert frozen.n_edges_blocked == 5
        for ps in frozen.prior_audit_trail.values():
            assert ps.prior_type == "StructuralPlaceholder"
