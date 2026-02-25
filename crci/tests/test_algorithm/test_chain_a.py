"""
Tests for ALG-A: Chain A Graph Assembly.

Hand-computable verification of:
- Node loading and layer assignment
- Edge loading, B matrix, and acyclicity
- Residual covariance D matrix
- Precision matrix Λ
- Proxy table, feedback loops, edgeless nodes
- Gate violations

Spec: SYS_ALGORITHM_COMPLETE.md lines 697-999
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

# ═══════════════════════════════════════════════════════════════
#  Fixtures: Minimal CSV data for controlled tests
# ═══════════════════════════════════════════════════════════════


MINI_NODE_HEADER = (
    "node_id,node_label,node_layer,clinical_domain,is_observable,is_latent,"
    "orientation,unit_of_measure,pathway_membership,proxy_for,"
    "proxy_r_squared,description,example_instruments,version,active"
)

MINI_NODES = [
    "NODE_A,Node A,0,treatment,1,0,CATEGORICAL,categorical,[],N/A_EXOGENOUS,N/A,Exogenous input,,1,1",
    "NODE_B,Node B,1,behavior,1,0,POS_UP,z,[],N/A_BEHAVIOR,N/A,Behavior node,,1,1",
    "NODE_C,Node C,2,biomarker,1,0,POS_DOWN,pg/mL,[],N/A_BIOMARKER,N/A,Biomarker node,,1,1",
    "NODE_D,Node D,3,pathway,0,1,POS_DOWN,z-score_latent,[],N/A_IS_LATENT,N/A_IS_LATENT,Latent pathway,,1,1",
    "NODE_E,Node E,4,symptom,1,0,POS_DOWN,z,[],N/A_SYMPTOM,N/A,Symptom node,,1,1",
    "NODE_F,Node F,5,cognition,1,0,POS_UP,z,[],N/A_COGNITIVE,N/A,Cognitive domain,,1,1",
    "NODE_G,Node G,6,composite,1,0,POS_UP,composite,[],N/A_COMPOSITE,N/A,Composite score,,1,1",
]

MINI_EDGE_HEADER = (
    "edge_relation_id,source_node_id,target_node_id,relation_type,"
    "mechanism_description,primary_pathway,secondary_pathways_json,"
    "expected_sign,functional_form,fallback_form,is_feedback_edge,"
    "feedback_loop_id,notes,version,active"
)

MINI_EDGES = [
    "ER_AB,NODE_A,NODE_B,causal,A→B,PW_1,[],negative,linear,linear,0,N/A,,1,1",
    "ER_AC,NODE_A,NODE_C,causal,A→C,PW_1,[],positive,linear,linear,0,N/A,,1,1",
    "ER_BD,NODE_B,NODE_D,causal,B→D,PW_1,[],positive,hill,linear,0,N/A,,1,1",
    "ER_CD,NODE_C,NODE_D,associational,C→D,PW_1,[],positive,linear,linear,0,N/A,,1,1",
    "ER_DE,NODE_D,NODE_E,causal,D→E,PW_2,[],positive,linear,linear,0,N/A,,1,1",
    "ER_EF,NODE_E,NODE_F,causal,E→F,PW_2,[],negative,linear,linear,0,N/A,,1,1",
    "ER_FG,NODE_F,NODE_G,causal,F→G,PW_2,[],positive,linear,linear,0,N/A,,1,1",
]

MINI_INSTRUMENT_HEADER = (
    "instrument_id,instrument_name,instrument_short,instrument_type,"
    "maps_to_node_id,maps_to_node_ids_json,scoring_direction,response_type,"
    "item_count,subscale_count,subscale_names_json,total_score_range_min,"
    "total_score_range_max,time_window_days,administration_minutes,"
    "loading_b_k,intercept_a_k,reliability_alpha,reliability_type,"
    "cancer_validation_status,se_multiplier,clinical_cutoff_value,"
    "clinical_cutoff_direction,normative_population,tier_assignment,"
    "norm_id,noise_id,language,citation_key,administration_mode,"
    "somatic_confound_risk,version,active,notes"
)

MINI_INSTRUMENTS = [
    "INST_1,Test Instrument,TI,PRO,NODE_E,\"[\"\"NODE_F\"\"]\",higher_better,likert,10,1,[],0,40,7,5,1.0,0.0,0.90,internal_consistency,validated_in_cancer,1.0,20,below,Cancer patients,0,,,English,,self_report,low,1,1,",
    "INST_2,Biomarker Assay,BA,biomarker,NODE_C,[],higher_worse,continuous,1,0,[],0,1000,1,0,1.0,0.0,0.95,test_retest,used_in_cancer,1.15,N/A,N/A,General,0,,,English,,lab_test,low,1,1,",
]

MINI_PATHWAY_HEADER = (
    "pathway_id,pathway_label,pathway_short,pathway_class,tier,"
    "evidence_tier_readable,se_multiplier,edge_count,status,"
    "entry_node_ids_json,exit_node_ids_json,intermediate_node_ids_json,"
    "component_nodes_json,composite_membership,best_proxy_biomarker,"
    "proxy_r_squared_qualitative,causal_evidence_level,key_citation,"
    "activation_threshold,is_sensitive_pathway,cognitive_domain_specificity_json,"
    "notes,version,active"
)

MINI_PATHWAYS = [
    "PW_1,Test Pathway 1,TP1,mechanistic,mechanistic_model_implied,High,1.0,4,connected,"
    "\"[\"\"NODE_A\"\"]\",\"[\"\"NODE_D\"\"]\",\"[\"\"NODE_B\"\",\"\"NODE_C\"\"]\","
    "\"[\"\"NODE_A\"\",\"\"NODE_B\"\",\"\"NODE_C\"\",\"\"NODE_D\"\"]\","
    "N/A,NODE_C,high,causal_demonstrated,Test,0.3,0,{},N/A,1,1",
    "PW_2,Test Pathway 2,TP2,clinical_mediator,clinical_mediator,Moderate,1.25,3,connected,"
    "\"[\"\"NODE_D\"\"]\",\"[\"\"NODE_G\"\"]\",\"[\"\"NODE_E\"\",\"\"NODE_F\"\"]\","
    "\"[\"\"NODE_D\"\",\"\"NODE_E\"\",\"\"NODE_F\"\",\"\"NODE_G\"\"]\","
    "N/A,,low,moderate_association,Test,0.5,0,{},N/A,1,1",
]


@pytest.fixture
def mini_csvs(tmp_path: Path) -> dict[str, Path]:
    """Create minimal CSV registry files for testing."""
    files: dict[str, Path] = {}

    # Node registry
    node_path = tmp_path / "nodes.csv"
    with open(node_path, "w", newline="") as f:
        f.write(MINI_NODE_HEADER + "\n")
        for row in MINI_NODES:
            f.write(row + "\n")
    files["nodes"] = node_path

    # Edge registry
    edge_path = tmp_path / "edges.csv"
    with open(edge_path, "w", newline="") as f:
        f.write(MINI_EDGE_HEADER + "\n")
        for row in MINI_EDGES:
            f.write(row + "\n")
    files["edges"] = edge_path

    # Instrument registry
    inst_path = tmp_path / "instruments.csv"
    with open(inst_path, "w", newline="") as f:
        f.write(MINI_INSTRUMENT_HEADER + "\n")
        for row in MINI_INSTRUMENTS:
            f.write(row + "\n")
    files["instruments"] = inst_path

    # Pathway registry
    pw_path = tmp_path / "pathways.csv"
    with open(pw_path, "w", newline="") as f:
        f.write(MINI_PATHWAY_HEADER + "\n")
        for row in MINI_PATHWAYS:
            f.write(row + "\n")
    files["pathways"] = pw_path

    return files


# ═══════════════════════════════════════════════════════════════
#  A1: Node Loader Tests
# ═══════════════════════════════════════════════════════════════


class TestNodeLoader:
    """Tests for node_loader.py."""

    def test_load_nodes_count(self, mini_csvs: dict[str, Path]) -> None:
        """Load nodes and verify count matches CSV rows."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        assert len(nodes) == 7

    def test_node_layer_assignment(self, mini_csvs: dict[str, Path]) -> None:
        """Verify each node gets the correct layer from CSV."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        expected_layers = {
            "NODE_A": 0,
            "NODE_B": 1,
            "NODE_C": 2,
            "NODE_D": 3,
            "NODE_E": 4,
            "NODE_F": 5,
            "NODE_G": 6,
        }
        for node in nodes:
            assert node.layer == expected_layers[node.node_id], (
                f"{node.node_id}: expected layer {expected_layers[node.node_id]}, "
                f"got {node.layer}"
            )

    def test_latent_observable_classification(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """NODE_D is latent; all others observable."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_dict = {n.node_id: n for n in nodes}
        assert node_dict["NODE_D"].is_latent is True
        assert node_dict["NODE_D"].is_observable is False
        assert node_dict["NODE_A"].is_observable is True
        assert node_dict["NODE_A"].is_latent is False

    def test_topological_order_respects_layers(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """Topological order should respect layer 0 → 6."""
        from crci.algorithm.chain_a_graph.node_loader import (
            compute_topological_order,
            load_nodes,
        )

        nodes = load_nodes(mini_csvs["nodes"])
        order = compute_topological_order(nodes)

        # Verify ordering: NODE_A (L0) before NODE_B (L1) before ...
        for i in range(len(order) - 1):
            node_i = next(n for n in nodes if n.node_id == order[i])
            node_j = next(n for n in nodes if n.node_id == order[i + 1])
            assert node_i.layer <= node_j.layer

    def test_assemble_node_map_gate_validates(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """Gate A-G1 should raise if node count is insufficient."""
        from crci.algorithm.chain_a_graph.node_loader import (
            assemble_node_map,
            load_nodes,
        )

        nodes = load_nodes(mini_csvs["nodes"])
        # With 7 nodes < EXPECTED_NODE_COUNT (63), gate should fire
        with pytest.raises(GateViolation, match="A-G1"):
            assemble_node_map(nodes)

    def test_file_not_found_raises_gate(self, tmp_path: Path) -> None:
        """Missing file should raise GateViolation."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        with pytest.raises(GateViolation, match="A-G1"):
            load_nodes(tmp_path / "nonexistent.csv")


# ═══════════════════════════════════════════════════════════════
#  A2: Edge Loader Tests
# ═══════════════════════════════════════════════════════════════


class TestEdgeLoader:
    """Tests for edge_loader.py."""

    def _make_node_map(self, mini_csvs: dict[str, Path]):
        """Create a NodeMap with gate disabled for testing."""
        from crci.algorithm.chain_a_graph.node_loader import NodeMap, load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_index = {n.node_id: i for i, n in enumerate(nodes)}
        return NodeMap(
            nodes=nodes,
            node_index=node_index,
            layer_assignment={n.node_id: n.layer for n in nodes},
            domain_assignment={n.node_id: n.clinical_domain for n in nodes},
            observability={n.node_id: n.is_observable for n in nodes},
            orientation={n.node_id: n.orientation for n in nodes},
            topological_order=[n.node_id for n in sorted(nodes, key=lambda n: n.layer)],
        )

    def test_load_edges_count(self, mini_csvs: dict[str, Path]) -> None:
        """Load edges and verify count."""
        from crci.algorithm.chain_a_graph.edge_loader import load_edges

        edges = load_edges(mini_csvs["edges"])
        assert len(edges) == 7

    def test_b_struct_shape(self, mini_csvs: dict[str, Path]) -> None:
        """B matrix should be n_nodes × n_nodes."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )

        nm = self._make_node_map(mini_csvs)
        edges = load_edges(mini_csvs["edges"])
        # Bypass gate A-G2 by patching config
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
            assert skeleton.B_struct.shape == (7, 7)
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original

    def test_b_struct_sign_encoding(self, mini_csvs: dict[str, Path]) -> None:
        """B[src, tgt] should be -1.0 for negative, +1.0 for positive."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )

        nm = self._make_node_map(mini_csvs)
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
            B = skeleton.B_struct
            # ER_AB: NODE_A→NODE_B, negative → B[0,1] = -1.0
            assert B[nm.node_index["NODE_A"], nm.node_index["NODE_B"]] == -1.0
            # ER_AC: NODE_A→NODE_C, positive → B[0,2] = 1.0
            assert B[nm.node_index["NODE_A"], nm.node_index["NODE_C"]] == 1.0
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original

    def test_acyclicity_passes_for_dag(self, mini_csvs: dict[str, Path]) -> None:
        """Acyclicity should pass for our layered mini DAG."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )

        nm = self._make_node_map(mini_csvs)
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
            assert skeleton.acyclicity_verified is True
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original

    def test_edge_density_formula(self, mini_csvs: dict[str, Path]) -> None:
        """Formula A2-2: density = |E| / (N × (N−1))."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )

        nm = self._make_node_map(mini_csvs)
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
            # Hand calculation: 7 edges / (7 × 6) = 7/42 ≈ 0.1667
            expected_density = 7.0 / (7 * 6)
            assert abs(skeleton.edge_density - expected_density) < 1e-6
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original

    def test_functional_forms_recorded(self, mini_csvs: dict[str, Path]) -> None:
        """Each edge should have its functional form recorded."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )

        nm = self._make_node_map(mini_csvs)
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
            assert skeleton.functional_forms["ER_BD"] == "hill"
            assert skeleton.functional_forms["ER_AB"] == "linear"
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original


# ═══════════════════════════════════════════════════════════════
#  A3: Instrument Loader Tests
# ═══════════════════════════════════════════════════════════════


class TestInstrumentLoader:
    """Tests for instrument_loader.py."""

    def _make_node_map(self, mini_csvs: dict[str, Path]):
        from crci.algorithm.chain_a_graph.node_loader import NodeMap, load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_index = {n.node_id: i for i, n in enumerate(nodes)}
        return NodeMap(
            nodes=nodes,
            node_index=node_index,
            layer_assignment={n.node_id: n.layer for n in nodes},
            domain_assignment={n.node_id: n.clinical_domain for n in nodes},
            observability={n.node_id: n.is_observable for n in nodes},
            orientation={n.node_id: n.orientation for n in nodes},
            topological_order=[n.node_id for n in sorted(nodes, key=lambda n: n.layer)],
        )

    def test_load_instruments_count(self, mini_csvs: dict[str, Path]) -> None:
        """Load instruments and verify count."""
        from crci.algorithm.chain_a_graph.instrument_loader import load_instruments

        instruments = load_instruments(mini_csvs["instruments"])
        assert len(instruments) == 2

    def test_h_matrix_shape(self, mini_csvs: dict[str, Path]) -> None:
        """H matrix should be n_instruments × n_nodes."""
        from crci.algorithm.chain_a_graph.instrument_loader import (
            assemble_instrument_map,
            load_instruments,
        )

        nm = self._make_node_map(mini_csvs)
        instruments = load_instruments(mini_csvs["instruments"])
        imap = assemble_instrument_map(instruments, nm)
        assert imap.H.shape == (2, 7)

    def test_h_matrix_primary_loading(self, mini_csvs: dict[str, Path]) -> None:
        """Primary node should get full loading b_k."""
        from crci.algorithm.chain_a_graph.instrument_loader import (
            assemble_instrument_map,
            load_instruments,
        )

        nm = self._make_node_map(mini_csvs)
        instruments = load_instruments(mini_csvs["instruments"])
        imap = assemble_instrument_map(instruments, nm)

        # INST_1 maps to NODE_E (idx=4) with loading 1.0
        assert imap.H[0, nm.node_index["NODE_E"]] == 1.0
        # INST_2 maps to NODE_C (idx=2) with loading 1.0
        assert imap.H[1, nm.node_index["NODE_C"]] == 1.0

    def test_observation_noise_formula(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """σ²_{y,k} = (1 − α) / α × se_mult²."""
        from crci.algorithm.chain_a_graph.instrument_loader import (
            assemble_instrument_map,
            load_instruments,
        )

        nm = self._make_node_map(mini_csvs)
        instruments = load_instruments(mini_csvs["instruments"])
        imap = assemble_instrument_map(instruments, nm)

        # INST_1: α=0.90, se_mult=1.0
        # σ² = (1 - 0.90) / 0.90 × 1.0² = 0.1/0.9 ≈ 0.1111
        expected_noise_1 = (1.0 - 0.90) / 0.90 * (1.0 ** 2)
        assert abs(imap.observation_noise_var["INST_1"] - expected_noise_1) < 1e-6

        # INST_2: α=0.95, se_mult=1.15
        # σ² = (1 - 0.95) / 0.95 × 1.15² = 0.05/0.95 × 1.3225 ≈ 0.0696
        expected_noise_2 = (1.0 - 0.95) / 0.95 * (1.15 ** 2)
        assert abs(imap.observation_noise_var["INST_2"] - expected_noise_2) < 1e-6


# ═══════════════════════════════════════════════════════════════
#  A3-A4: Spectral Validator Tests
# ═══════════════════════════════════════════════════════════════


class TestSpectralValidator:
    """Tests for spectral_validator.py."""

    def _make_skeleton_and_node_map(self, mini_csvs: dict[str, Path]):
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )
        from crci.algorithm.chain_a_graph.node_loader import NodeMap, load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_index = {n.node_id: i for i, n in enumerate(nodes)}
        nm = NodeMap(
            nodes=nodes,
            node_index=node_index,
            layer_assignment={n.node_id: n.layer for n in nodes},
            domain_assignment={n.node_id: n.clinical_domain for n in nodes},
            observability={n.node_id: n.is_observable for n in nodes},
            orientation={n.node_id: n.orientation for n in nodes},
            topological_order=[n.node_id for n in sorted(nodes, key=lambda n: n.layer)],
        )
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original
        return skeleton, nm

    def test_residual_variance_floor(self, mini_csvs: dict[str, Path]) -> None:
        """Formula A3-2: σ²_{ε,i} = max(1 − R²_i, FLOOR)."""
        from crci.algorithm.chain_a_graph.spectral_validator import build_d_matrix

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)

        # All residual variances must be ≥ RESIDUAL_VARIANCE_FLOOR
        assert np.all(
            d_matrix.residual_variances >= config.RESIDUAL_VARIANCE_FLOOR
        )

    def test_d_diagonal_matches_residual_var(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """D diagonal should equal residual variances."""
        from crci.algorithm.chain_a_graph.spectral_validator import build_d_matrix

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)

        np.testing.assert_allclose(
            np.diag(d_matrix.D),
            d_matrix.residual_variances,
            atol=1e-10,
        )

    def test_d_positive_definite(self, mini_csvs: dict[str, Path]) -> None:
        """D should be positive-definite."""
        from crci.algorithm.chain_a_graph.spectral_validator import build_d_matrix

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)
        assert d_matrix.is_positive_definite is True

    def test_r_squared_node_a_zero(self, mini_csvs: dict[str, Path]) -> None:
        """NODE_A (L0, exogenous) has no parents → R²=0."""
        from crci.algorithm.chain_a_graph.spectral_validator import build_d_matrix

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)

        idx_a = nm.node_index["NODE_A"]
        assert d_matrix.R_squared_per_node[idx_a] == 0.0

    def test_r_squared_node_d_two_parents(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """NODE_D has 2 parents (B→D, C→D) → R²=0.20 (2×0.10)."""
        from crci.algorithm.chain_a_graph.spectral_validator import build_d_matrix

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)

        idx_d = nm.node_index["NODE_D"]
        # 2 parents × 0.10 = 0.20
        assert abs(d_matrix.R_squared_per_node[idx_d] - 0.20) < 1e-10

    def test_lambda_positive_definite(self, mini_csvs: dict[str, Path]) -> None:
        """Lambda should be positive-definite."""
        from crci.algorithm.chain_a_graph.spectral_validator import (
            build_d_matrix,
            build_lambda_structure,
        )

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)
        ls = build_lambda_structure(skeleton, d_matrix, nm)
        assert ls.is_positive_definite is True

    def test_spectral_radius_below_one(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """ρ(B) < 1 for a stable DAG."""
        from crci.algorithm.chain_a_graph.spectral_validator import (
            build_d_matrix,
            build_lambda_structure,
        )

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)
        ls = build_lambda_structure(skeleton, d_matrix, nm)
        assert ls.spectral_radius_B < config.MAX_SPECTRAL_RADIUS

    def test_condition_number_finite(self, mini_csvs: dict[str, Path]) -> None:
        """κ(Λ) should be finite and below critical threshold."""
        from crci.algorithm.chain_a_graph.spectral_validator import (
            build_d_matrix,
            build_lambda_structure,
        )

        skeleton, nm = self._make_skeleton_and_node_map(mini_csvs)
        d_matrix = build_d_matrix(skeleton, nm)
        ls = build_lambda_structure(skeleton, d_matrix, nm)
        assert np.isfinite(ls.condition_number)
        assert ls.condition_number < config.CONDITION_NUMBER_CRITICAL


# ═══════════════════════════════════════════════════════════════
#  A5: Graph Object Assembly Tests
# ═══════════════════════════════════════════════════════════════


class TestGraphObject:
    """Tests for graph_object.py."""

    def test_proxy_table_latent_coverage(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """Every latent node should appear in the proxy table."""
        from crci.algorithm.chain_a_graph.graph_object import build_proxy_table
        from crci.algorithm.chain_a_graph.node_loader import NodeMap, load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_index = {n.node_id: i for i, n in enumerate(nodes)}
        nm = NodeMap(
            nodes=nodes,
            node_index=node_index,
            layer_assignment={n.node_id: n.layer for n in nodes},
            domain_assignment={n.node_id: n.clinical_domain for n in nodes},
            observability={n.node_id: n.is_observable for n in nodes},
            orientation={n.node_id: n.orientation for n in nodes},
            topological_order=[n.node_id for n in sorted(nodes, key=lambda n: n.layer)],
        )

        proxy_table = build_proxy_table(nm)
        proxied_ids = {p.latent_node_id for p in proxy_table}
        latent_ids = {n.node_id for n in nodes if n.is_latent}
        assert latent_ids <= proxied_ids

    def test_edgeless_node_identification(
        self, mini_csvs: dict[str, Path]
    ) -> None:
        """All nodes have edges in our mini DAG → no edgeless."""
        from crci.algorithm.chain_a_graph.edge_loader import (
            build_b_skeleton,
            load_edges,
        )
        from crci.algorithm.chain_a_graph.graph_object import (
            identify_edgeless_nodes,
        )
        from crci.algorithm.chain_a_graph.node_loader import NodeMap, load_nodes

        nodes = load_nodes(mini_csvs["nodes"])
        node_index = {n.node_id: i for i, n in enumerate(nodes)}
        nm = NodeMap(
            nodes=nodes,
            node_index=node_index,
            layer_assignment={n.node_id: n.layer for n in nodes},
            domain_assignment={n.node_id: n.clinical_domain for n in nodes},
            observability={n.node_id: n.is_observable for n in nodes},
            orientation={n.node_id: n.orientation for n in nodes},
            topological_order=[n.node_id for n in sorted(nodes, key=lambda n: n.layer)],
        )
        edges = load_edges(mini_csvs["edges"])
        original = config.EXPECTED_EDGE_COUNT_MIN
        config.EXPECTED_EDGE_COUNT_MIN = 1
        try:
            skeleton = build_b_skeleton(edges, nm)
        finally:
            config.EXPECTED_EDGE_COUNT_MIN = original

        edgeless = identify_edgeless_nodes(skeleton, nm)
        assert edgeless == []

    def test_proxy_se_multiplier_tiers(self) -> None:
        """Verify SE multiplier tiers from config match spec."""
        assert config.PROXY_SE_MULTIPLIER_HIGH == 1.0
        assert config.PROXY_SE_MULTIPLIER_MODERATE == 1.25
        assert config.PROXY_SE_MULTIPLIER_LOW == 1.5
        assert config.PROXY_SE_MULTIPLIER_VERY_LOW == 2.0


# ═══════════════════════════════════════════════════════════════
#  Integration: Full Chain A with Real Data
# ═══════════════════════════════════════════════════════════════


class TestChainAIntegration:
    """Integration tests running Chain A against real registry CSVs."""

    @pytest.fixture
    def registry_paths(self) -> dict[str, Path]:
        """Paths to the real registry CSV files."""
        root = Path("/home/user/in-silico-crci-lab")
        paths = {
            "nodes": root / "NODE_REGISTRY.csv",
            "edges": root / "EDGE_REGISTRY.csv",
            "instruments": root / "INSTRUMENT_REGISTRY.csv",
            "pathways": root / "PATHWAY_REGISTRY.csv",
        }
        # Only run if files exist
        for name, path in paths.items():
            if not path.exists():
                pytest.skip(f"Registry file missing: {path}")
        return paths

    def test_full_chain_a_real_data(
        self, registry_paths: dict[str, Path]
    ) -> None:
        """Run complete Chain A against real registry data."""
        from crci.algorithm.chain_a_graph.graph_object import run_chain_a

        graph = run_chain_a(
            node_registry_path=registry_paths["nodes"],
            edge_registry_path=registry_paths["edges"],
            instrument_registry_path=registry_paths["instruments"],
            pathway_registry_path=registry_paths["pathways"],
        )

        # Verify expected counts (64 rows in CSV = header + 63 data)
        assert graph.n_nodes == 63
        assert graph.n_edges >= 100
        assert graph.n_pathways >= 15
        assert graph.lambda_structure.is_positive_definite is True
        assert graph.lambda_structure.spectral_radius_B < 1.0

    def test_node_count_matches_csv(
        self, registry_paths: dict[str, Path]
    ) -> None:
        """Node count should match NODE_REGISTRY.csv row count."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(registry_paths["nodes"])
        # 64 lines in CSV - 1 header = 63 data rows
        assert len(nodes) >= 63

    def test_all_layers_populated(
        self, registry_paths: dict[str, Path]
    ) -> None:
        """All 7 layers (0-6) should have at least one node."""
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(registry_paths["nodes"])
        layers_present = {n.layer for n in nodes}
        for expected_layer in range(7):
            assert expected_layer in layers_present, (
                f"Layer {expected_layer} has no nodes"
            )

    def test_edge_endpoints_valid(
        self, registry_paths: dict[str, Path]
    ) -> None:
        """All edge source/target node IDs should exist in node registry."""
        from crci.algorithm.chain_a_graph.edge_loader import load_edges
        from crci.algorithm.chain_a_graph.node_loader import load_nodes

        nodes = load_nodes(registry_paths["nodes"])
        node_ids = {n.node_id for n in nodes}
        edges = load_edges(registry_paths["edges"])

        for edge in edges:
            assert edge.source_node_id in node_ids, (
                f"Edge {edge.edge_id}: source {edge.source_node_id} not found"
            )
            assert edge.target_node_id in node_ids, (
                f"Edge {edge.edge_id}: target {edge.target_node_id} not found"
            )
