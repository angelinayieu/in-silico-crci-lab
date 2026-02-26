"""
Component: Test — Pathway Evidence Integration (S5 / S7)
Purpose: End-to-end tests verifying that score_pathway_evidence is correctly
         wired into run_chain_b and its results flow through to FrozenModelState.

Tests:
    - run_chain_b with pathways → pathway_evidence_scores populated
    - run_chain_b without pathways → pathway_evidence_scores empty
    - active_pathway_ids derived from is_adequate flag
    - Hash includes pathway contribution
    - assemble_frozen_state handles None vs populated pathway_evidence_scores
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.pathway_types import PathwayDef

from crci.algorithm.chain_a_graph.node_loader import NodeDef, NodeMap
from crci.algorithm.chain_a_graph.edge_loader import (
    BSkeleton,
    EdgeDef,
    HillParams,
)
from crci.algorithm.chain_a_graph.instrument_loader import (
    InstrumentDef,
    InstrumentMap,
)
from crci.algorithm.chain_a_graph.spectral_validator import (
    CorrelationPair,
    DMatrix,
    LambdaStructure,
)
from crci.algorithm.chain_a_graph.graph_object import GraphObject

from crci.algorithm.chain_b_evidence.evidence_compiler import EvidenceRecord
from crci.algorithm.chain_b_evidence.frozen_state import (
    FrozenModelState,
    run_chain_b,
)
from crci.algorithm.chain_b_evidence.pathway_evidence_scorer import (
    PathwayEvidenceScore,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_graph_with_pathways(
    pathways: list[PathwayDef] | None = None,
) -> GraphObject:
    """Build a 5-node, 5-edge graph with optional pathway_map.

    Graph topology:
        N0 → N1 → N3
        N0 → N2 → N3
                → N4

    Edges: E01(N0→N1), E02(N0→N2), E13(N1→N3), E23(N2→N3), E24(N2→N4)
    """
    nodes = [
        NodeDef(
            node_id=f"N{i}", node_label=f"Node{i}", layer=l,
            clinical_domain=d, is_observable=True, is_latent=False,
            orientation="none", unit_of_measure="", pathway_membership=[],
            proxy_for=None, proxy_r_squared=None, description="",
        )
        for i, l, d in [
            (0, 0, "exo"), (1, 1, "bio"), (2, 1, "bio"),
            (3, 3, "cog"), (4, 4, "sym"),
        ]
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

    edge_defs = [
        ("E01", "N0", "N1", "-"),
        ("E02", "N0", "N2", "+"),
        ("E13", "N1", "N3", "-"),
        ("E23", "N2", "N3", "+"),
        ("E24", "N2", "N4", "-"),
    ]
    edges = [
        EdgeDef(
            edge_id=eid, source_node_id=src, target_node_id=tgt,
            relation_type="causal", mechanism_description="",
            primary_pathway="", secondary_pathways=[],
            expected_sign=sign, functional_form="linear",
            fallback_form="linear", is_feedback_edge=False,
            feedback_loop_id=None,
        )
        for eid, src, tgt, sign in edge_defs
    ]

    n = 5
    edge_index = {e.edge_id: i for i, e in enumerate(edges)}
    B_struct = np.zeros((n, n))
    B_struct[0, 1] = -1
    B_struct[0, 2] = 1
    B_struct[1, 3] = -1
    B_struct[2, 3] = 1
    B_struct[2, 4] = -1

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

    return GraphObject(
        node_map=node_map,
        b_skeleton=b_skeleton,
        instrument_map=instrument_map,
        d_matrix=d_matrix,
        lambda_structure=lambda_structure,
        n_nodes=n,
        n_edges=5,
        pathway_map=pathways or [],
    )


def _make_evidence(
    edge_id: str,
    beta: float,
    se: float,
    study_id: str = "S001",
    quality_grade: str = "HIGH",
) -> EvidenceRecord:
    """Create a minimal EvidenceRecord for testing."""
    return EvidenceRecord(
        study_id=study_id,
        edge_id=edge_id,
        beta=beta,
        se=se,
        study_design="large_rct",
        publication_year=2023,
        sample_size=200,
        identification_status="identified",
        quality_grade=quality_grade,
        scope_weights={
            "cancer": 1.0, "phase": 1.0, "regimen": 1.0,
            "age": 1.0, "sex": 1.0,
        },
        cancer_validation_status="validated_cancer",
        temporal_distance_days=0.0,
        outcome_type="semi_objective",
        has_rct_component=True,
    )


def _make_pathway(
    pathway_id: str, edge_ids: list[str],
) -> PathwayDef:
    """Create a minimal PathwayDef."""
    return PathwayDef(
        pathway_id=pathway_id,
        pathway_label=f"Test {pathway_id}",
        tier="mechanistic_model_implied",
        edge_ids=tuple(edge_ids),
    )


# ═══════════════════════════════════════════════════════════════
#  Integration: run_chain_b with pathway_map
# ═══════════════════════════════════════════════════════════════


class TestRunChainBPathwayWiring:
    """Verify score_pathway_evidence is wired into run_chain_b (S5)."""

    def test_no_pathways_skips_scoring(self) -> None:
        """Graph with empty pathway_map → pathway_evidence_scores is {}."""
        graph = _make_graph_with_pathways(pathways=[])
        evidence = [
            _make_evidence("E01", -0.3, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
            _make_evidence("E13", -0.4, 0.10, study_id="S3a"),
        ]
        frozen = run_chain_b(graph, evidence)

        assert frozen.pathway_evidence_scores == {}
        assert frozen.active_pathway_ids == ()

    def test_pathways_with_evidence(self) -> None:
        """Graph with pathways and matching evidence → scores populated."""
        pw_alpha = _make_pathway("PW_alpha", ["E01", "E13"])
        pw_beta = _make_pathway("PW_beta", ["E02", "E23"])

        graph = _make_graph_with_pathways(pathways=[pw_alpha, pw_beta])

        # Provide evidence for PW_alpha's edges (E01, E13) but not PW_beta's
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
            _make_evidence("E01", -0.35, 0.08, study_id="S1c"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a"),
            _make_evidence("E13", -0.38, 0.11, study_id="S3b"),
        ]

        frozen = run_chain_b(graph, evidence)

        # Both pathways scored
        assert "PW_alpha" in frozen.pathway_evidence_scores
        assert "PW_beta" in frozen.pathway_evidence_scores

        # PW_alpha has evidence (all edges covered)
        alpha = frozen.pathway_evidence_scores["PW_alpha"]
        assert alpha.evidence_density > 0
        assert alpha.edge_coverage == 1.0  # 2/2 edges have evidence

        # PW_beta has no evidence
        beta = frozen.pathway_evidence_scores["PW_beta"]
        assert beta.evidence_density == 0.0
        assert beta.edge_coverage == 0.0

    def test_active_pathway_ids_set(self) -> None:
        """active_pathway_ids should contain only adequate pathways."""
        pw_alpha = _make_pathway("PW_alpha", ["E01", "E13"])
        pw_beta = _make_pathway("PW_beta", ["E02", "E23"])

        graph = _make_graph_with_pathways(pathways=[pw_alpha, pw_beta])

        # Give PW_alpha enough evidence to be adequate
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a"),
        ]

        frozen = run_chain_b(graph, evidence)

        alpha = frozen.pathway_evidence_scores["PW_alpha"]
        beta = frozen.pathway_evidence_scores["PW_beta"]

        if alpha.is_adequate:
            assert "PW_alpha" in frozen.active_pathway_ids
        else:
            assert "PW_alpha" not in frozen.active_pathway_ids

        # PW_beta has no evidence → never adequate
        assert not beta.is_adequate
        assert "PW_beta" not in frozen.active_pathway_ids

    def test_active_pathway_ids_sorted(self) -> None:
        """active_pathway_ids must be sorted for deterministic hashing."""
        pw_a = _make_pathway("PW_Z", ["E01"])
        pw_b = _make_pathway("PW_A", ["E13"])

        graph = _make_graph_with_pathways(pathways=[pw_a, pw_b])

        # Give both pathways evidence
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a"),
            _make_evidence("E13", -0.38, 0.11, study_id="S3b"),
        ]

        frozen = run_chain_b(graph, evidence)

        # If both are active, order should be sorted
        if len(frozen.active_pathway_ids) == 2:
            assert frozen.active_pathway_ids == tuple(
                sorted(frozen.active_pathway_ids)
            )


class TestFrozenStatePathwayFields:
    """Verify FrozenModelState pathway fields are properly set."""

    def test_pathway_evidence_scores_type(self) -> None:
        """pathway_evidence_scores should be dict[str, PathwayEvidenceScore]."""
        pw = _make_pathway("PW_test", ["E01"])
        graph = _make_graph_with_pathways(pathways=[pw])
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
        ]
        frozen = run_chain_b(graph, evidence)

        for pid, score in frozen.pathway_evidence_scores.items():
            assert isinstance(pid, str)
            assert isinstance(score, PathwayEvidenceScore)

    def test_hash_differs_with_pathways(self) -> None:
        """Different active_pathway_ids should produce different hashes."""
        # Graph without pathways
        graph_no_pw = _make_graph_with_pathways(pathways=[])

        # Graph with pathways
        pw = _make_pathway("PW_test", ["E01", "E13"])
        graph_pw = _make_graph_with_pathways(pathways=[pw])

        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a"),
        ]

        frozen_no_pw = run_chain_b(graph_no_pw, evidence)
        frozen_pw = run_chain_b(graph_pw, evidence)

        # If the pathway is adequate (active), hashes must differ
        if frozen_pw.active_pathway_ids:
            assert frozen_no_pw.sha256_hash != frozen_pw.sha256_hash

    def test_frozen_state_is_frozen(self) -> None:
        """FrozenModelState must reject attribute mutation."""
        from dataclasses import FrozenInstanceError

        pw = _make_pathway("PW_test", ["E01"])
        graph = _make_graph_with_pathways(pathways=[pw])
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b"),
        ]
        frozen = run_chain_b(graph, evidence)

        with pytest.raises(FrozenInstanceError):
            frozen.pathway_evidence_scores = {}  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            frozen.active_pathway_ids = ("hacked",)  # type: ignore[misc]

    def test_pathway_scores_hashable_frozen_state(self) -> None:
        """FrozenModelState with pathway scores must be hashable."""
        pw = _make_pathway("PW_test", ["E01"])
        graph = _make_graph_with_pathways(pathways=[pw])
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
        ]
        frozen = run_chain_b(graph, evidence)

        # Must not raise
        h = hash(frozen)
        assert isinstance(h, int)


class TestPathwayEvidenceEndToEnd:
    """End-to-end: evidence → scoring → FrozenModelState → consumer access."""

    def test_evidence_density_computation(self) -> None:
        """Verify ED is computed correctly through the full pipeline.

        PW has 2 edges (E01, E13).
        E01 has 2 HIGH studies → k_quality = 2 × ED_QUALITY_WEIGHT_HIGH
        E13 has 1 HIGH study → k_quality = 1 × ED_QUALITY_WEIGHT_HIGH
        ED = (k_quality(E01) + k_quality(E13)) / 2
        """
        pw = _make_pathway("PW_test", ["E01", "E13"])
        graph = _make_graph_with_pathways(pathways=[pw])

        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a", quality_grade="HIGH"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b", quality_grade="HIGH"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a", quality_grade="HIGH"),
        ]

        frozen = run_chain_b(graph, evidence)
        score = frozen.pathway_evidence_scores["PW_test"]

        w_high = config.ED_QUALITY_WEIGHT_HIGH
        expected_ed = (2 * w_high + 1 * w_high) / 2
        assert score.evidence_density == pytest.approx(expected_ed)
        assert score.n_edges_total == 2
        assert score.n_edges_with_evidence == 2

    def test_mixed_quality_evidence(self) -> None:
        """Different quality grades should use their respective weights."""
        pw = _make_pathway("PW_test", ["E01"])
        graph = _make_graph_with_pathways(pathways=[pw])

        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a", quality_grade="HIGH"),
            _make_evidence("E01", -0.25, 0.12, study_id="S1b", quality_grade="MODERATE"),
        ]

        frozen = run_chain_b(graph, evidence)
        score = frozen.pathway_evidence_scores["PW_test"]

        w_high = config.ED_QUALITY_WEIGHT_HIGH
        w_mod = config.ED_QUALITY_WEIGHT_MODERATE
        expected_ed = (w_high + w_mod) / 1  # 1 edge
        assert score.evidence_density == pytest.approx(expected_ed)

    def test_no_evidence_yields_zero_density(self) -> None:
        """Pathway with no matching evidence → ED = 0."""
        pw = _make_pathway("PW_test", ["E24"])  # no evidence for E24
        graph = _make_graph_with_pathways(pathways=[pw])

        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
        ]

        frozen = run_chain_b(graph, evidence)
        score = frozen.pathway_evidence_scores["PW_test"]

        assert score.evidence_density == 0.0
        assert score.n_edges_with_evidence == 0
        assert not score.is_adequate

    def test_multiple_pathways_independent(self) -> None:
        """Each pathway scored independently; no cross-contamination."""
        pw_a = _make_pathway("PW_A", ["E01", "E13"])
        pw_b = _make_pathway("PW_B", ["E02", "E24"])

        graph = _make_graph_with_pathways(pathways=[pw_a, pw_b])

        # Only E01 and E13 have evidence
        evidence = [
            _make_evidence("E01", -0.30, 0.10, study_id="S1a"),
            _make_evidence("E13", -0.40, 0.10, study_id="S3a"),
        ]

        frozen = run_chain_b(graph, evidence)

        score_a = frozen.pathway_evidence_scores["PW_A"]
        score_b = frozen.pathway_evidence_scores["PW_B"]

        # PW_A has evidence on both edges
        assert score_a.evidence_density > 0
        assert score_a.edge_coverage == 1.0

        # PW_B has no evidence
        assert score_b.evidence_density == 0.0
        assert score_b.edge_coverage == 0.0
