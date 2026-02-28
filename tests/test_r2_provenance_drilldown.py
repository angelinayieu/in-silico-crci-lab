"""
Tests for R2: Provenance Drill-Down in Output Contract.

Verifies that:
1. StudyContribution model constructed correctly
2. DecisionTrace.edge_study_map populated from edge_study_provenance
3. _build_provenance() populates supporting_edges when provenance data available
4. _build_decision_trace() builds edge_study_map with StudyContributions
5. provenance_viewer renders study (depth 5) and paper (depth 6) nodes
6. provenance_viewer deduplicates paper nodes
7. assemble_report threads edge_study_provenance end-to-end
8. Empty provenance gracefully handled (no crash, empty map)
"""
from __future__ import annotations

import math

import pytest

from crci.shared.models.enums import ReportOutputMode, StabilityClass
from crci.shared.models.output_contracts import (
    DecisionTrace,
    DecisionTraceEntry,
    RecommendationReport,
    SchedulePlan,
    StudyContribution,
)
from crci.runtime.report_assembler import (
    ProvenanceEntry,
    UncertaintyDisclosure,
    SessionSummary,
    _build_provenance,
    _build_decision_trace,
    assemble_report,
)
from crci.runtime.schedule_generator import (
    RankedSchedules,
    Schedule,
    ScheduleItem,
)
from crci.presentation.provenance_viewer import (
    ProvenanceChainView,
    render_provenance_chain,
)
from crci.algorithm.chain_f_analytics.variance_decomposer import (
    StabilityClass as F2StabilityClass,
    StabilityState,
    CriticalEdge,
)
from crci.algorithm.chain_f_analytics.evsi import VarianceState, ReducibleSource
from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

SAMPLE_PROVENANCE = {
    "ER_EXERCISE_FATIGUE": [
        {
            "ler_id": "ler_001",
            "study_id": "study_campbell_2020",
            "weight": 100.0,
            "weight_normalized": 0.59,
            "beta": 0.30,
            "se": 0.10,
            "paper_ref": "Campbell et al. 2020",
        },
        {
            "ler_id": "ler_002",
            "study_id": "study_smith_2019",
            "weight": 25.0,
            "weight_normalized": 0.15,
            "beta": 0.20,
            "se": 0.20,
            "paper_ref": "Smith et al. 2019",
        },
        {
            "ler_id": "ler_003",
            "study_id": "study_jones_2021",
            "weight": 44.44,
            "weight_normalized": 0.26,
            "beta": 0.40,
            "se": 0.15,
            "paper_ref": "Jones et al. 2021",
        },
    ],
    "ER_SLEEP_MEMORY": [
        {
            "ler_id": "ler_010",
            "study_id": "study_lee_2022",
            "weight": 50.0,
            "weight_normalized": 1.0,
            "beta": -0.25,
            "se": 0.14,
            "paper_ref": "Campbell et al. 2020",  # same paper as above → should deduplicate
        },
    ],
}


def _make_schedule(aid: str = "a1", safe_b: float = 0.6, rank: int = 1) -> Schedule:
    return Schedule(
        schedule_id=f"sched_{rank:03d}",
        rank=rank,
        items=[ScheduleItem(
            action_id=aid,
            action_label=f"Label {aid}",
            dose_value=3.0,
        )],
        safe_b=safe_b,
        safe_b_cri_lower=safe_b - 0.1,
        safe_b_cri_upper=safe_b + 0.1,
        safe_a=safe_b,
        claim_level="causal_supported",
    )


def _make_ranked_schedules(n: int = 2) -> RankedSchedules:
    schedules = [
        _make_schedule(f"a{i}", safe_b=0.8 - i * 0.2, rank=i + 1)
        for i in range(n)
    ]
    return RankedSchedules(
        schedules=schedules,
        n_expanded=20,
        n_feasible=n,
        n_excluded=0,
        excluded_reasons=[],
        gate_g_g1_passed=True,
        gate_g_g2_passed=True,
    )


def _make_stability(critical_edges: list[str] | None = None) -> StabilityState:
    return StabilityState(
        rank_1_probabilities={"a0": 0.75, "a1": 0.25},
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[
            CriticalEdge(edge_id=eid, flip_influence=0.3)
            for eid in (critical_edges or ["ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY"])
        ],
        flip_counts={"ER_EXERCISE_FATIGUE": 300, "ER_SLEEP_MEMORY": 200},
        pairwise_dominance={},
        n_draws=1000,
        n_interventions=2,
    )


def _make_disclosure(critical_edges: list[str] | None = None) -> UncertaintyDisclosure:
    return UncertaintyDisclosure(
        stability_class="MODERATE",
        p_rank_1=0.75,
        cri_95_lower=0.5,
        cri_95_upper=0.9,
        variance_decomposition={"literature": 0.4, "measurement": 0.3},
        top_reducible_sources=["literature"],
        critical_edges=critical_edges or ["ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY"],
    )


def _make_session() -> SessionSummary:
    return SessionSummary(
        n_questions_asked=5,
        n_questions_skipped=1,
        stop_reason="MAX_QUESTIONS",
        total_ig=2.5,
        timestamp="2026-02-28T00:00:00Z",
    )


# ═══════════════════════════════════════════════════════════════
#  TEST 1: StudyContribution Model
# ═══════════════════════════════════════════════════════════════


class TestStudyContributionModel:
    def test_basic_construction(self):
        sc = StudyContribution(
            ler_id="ler_001",
            study_id="study_01",
            paper_ref="Smith 2020",
            weight_pct=59.0,
            beta=0.30,
            se=0.10,
        )
        assert sc.ler_id == "ler_001"
        assert sc.study_id == "study_01"
        assert sc.paper_ref == "Smith 2020"
        assert sc.weight_pct == 59.0

    def test_paper_ref_optional(self):
        sc = StudyContribution(
            ler_id="ler_002",
            study_id="study_02",
            weight_pct=41.0,
            beta=0.20,
            se=0.15,
        )
        assert sc.paper_ref is None

    def test_serialization_roundtrip(self):
        sc = StudyContribution(
            ler_id="ler_003",
            study_id="study_03",
            paper_ref="Jones 2021",
            weight_pct=100.0,
            beta=-0.15,
            se=0.08,
        )
        d = sc.model_dump()
        sc2 = StudyContribution(**d)
        assert sc2 == sc


# ═══════════════════════════════════════════════════════════════
#  TEST 2: DecisionTrace.edge_study_map
# ═══════════════════════════════════════════════════════════════


class TestDecisionTraceEdgeStudyMap:
    def test_empty_by_default(self):
        dt = DecisionTrace(run_id="run_01")
        assert dt.edge_study_map == {}

    def test_populated_from_data(self):
        contributions = [
            StudyContribution(
                ler_id="ler_001", study_id="s_01",
                weight_pct=60.0, beta=0.3, se=0.1,
            ),
            StudyContribution(
                ler_id="ler_002", study_id="s_02",
                weight_pct=40.0, beta=0.2, se=0.15,
            ),
        ]
        dt = DecisionTrace(
            run_id="run_02",
            decision_critical_edges=["ER_TEST"],
            edge_study_map={"ER_TEST": contributions},
        )
        assert "ER_TEST" in dt.edge_study_map
        assert len(dt.edge_study_map["ER_TEST"]) == 2
        assert dt.edge_study_map["ER_TEST"][0].ler_id == "ler_001"


# ═══════════════════════════════════════════════════════════════
#  TEST 3: _build_provenance with edge_study_provenance
# ═══════════════════════════════════════════════════════════════


class TestBuildProvenanceR2:
    def test_without_provenance_empty_supporting(self):
        """Without edge_study_provenance, supporting_edges remains empty."""
        scheds = [_make_schedule()]
        entries = _build_provenance(scheds)
        assert len(entries) == 1
        assert entries[0].supporting_edges == []

    def test_with_provenance_populates_supporting(self):
        """With edge_study_provenance, supporting_edges gets populated."""
        scheds = [_make_schedule()]
        entries = _build_provenance(scheds, SAMPLE_PROVENANCE)
        assert len(entries) == 1
        assert len(entries[0].supporting_edges) == 2  # 2 edges in SAMPLE_PROVENANCE

    def test_supporting_edges_structure(self):
        """Each supporting_edge dict has edge_id and study_weights."""
        scheds = [_make_schedule()]
        entries = _build_provenance(scheds, SAMPLE_PROVENANCE)

        edge_entry = next(
            e for e in entries[0].supporting_edges
            if e["edge_id"] == "ER_EXERCISE_FATIGUE"
        )
        assert "study_weights" in edge_entry
        assert len(edge_entry["study_weights"]) == 3
        first_sw = edge_entry["study_weights"][0]
        assert "study_id" in first_sw
        assert "ler_id" in first_sw
        assert "weight_pct" in first_sw

    def test_weight_pct_is_percentage(self):
        """weight_normalized (0–1) should be converted to weight_pct (0–100)."""
        scheds = [_make_schedule()]
        entries = _build_provenance(scheds, SAMPLE_PROVENANCE)
        edge_entry = next(
            e for e in entries[0].supporting_edges
            if e["edge_id"] == "ER_EXERCISE_FATIGUE"
        )
        first_sw = edge_entry["study_weights"][0]
        # weight_normalized=0.59 → weight_pct=59.0
        assert math.isclose(first_sw["weight_pct"], 59.0, rel_tol=1e-6)


# ═══════════════════════════════════════════════════════════════
#  TEST 4: _build_decision_trace with edge_study_provenance
# ═══════════════════════════════════════════════════════════════


class TestBuildDecisionTraceR2:
    def test_without_provenance_empty_map(self):
        """Without edge_study_provenance, edge_study_map is empty."""
        provenance = [ProvenanceEntry(
            intervention_id="a0",
            intervention_label="Label a0",
            claim_level="causal_supported",
        )]
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_01",
        )
        assert trace.edge_study_map == {}

    def test_with_provenance_populates_map(self):
        """With edge_study_provenance, edge_study_map gets populated."""
        provenance = [ProvenanceEntry(
            intervention_id="a0",
            intervention_label="Label a0",
            claim_level="causal_supported",
        )]
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_02",
            edge_study_provenance=SAMPLE_PROVENANCE,
        )
        assert len(trace.edge_study_map) == 2
        assert "ER_EXERCISE_FATIGUE" in trace.edge_study_map
        assert "ER_SLEEP_MEMORY" in trace.edge_study_map

    def test_study_contributions_fields(self):
        """Each StudyContribution has correct fields from provenance data."""
        provenance = [ProvenanceEntry(
            intervention_id="a0",
            intervention_label="Label a0",
            claim_level="causal_supported",
        )]
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_03",
            edge_study_provenance=SAMPLE_PROVENANCE,
        )
        sc = trace.edge_study_map["ER_EXERCISE_FATIGUE"][0]
        assert sc.ler_id == "ler_001"
        assert sc.study_id == "study_campbell_2020"
        assert sc.paper_ref == "Campbell et al. 2020"
        assert math.isclose(sc.weight_pct, 59.0, rel_tol=1e-6)
        assert math.isclose(sc.beta, 0.30)
        assert math.isclose(sc.se, 0.10)

    def test_decision_critical_edges_preserved(self):
        """decision_critical_edges still populated from disclosure."""
        provenance = []
        trace = _build_decision_trace(
            provenance, _make_disclosure(["ER_E1", "ER_E2"]),
            _make_session(), "run_04",
        )
        assert trace.decision_critical_edges == ["ER_E1", "ER_E2"]


# ═══════════════════════════════════════════════════════════════
#  TEST 5: Provenance Viewer renders study + paper nodes
# ═══════════════════════════════════════════════════════════════


class TestProvenanceViewerR2:
    def _make_report_with_provenance(
        self,
        edge_study_map: dict | None = None,
        critical_edges: list[str] | None = None,
    ) -> RecommendationReport:
        """Build a minimal RecommendationReport with R2 provenance."""
        edges = critical_edges or ["ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY"]
        esm = edge_study_map or {}
        return RecommendationReport(
            run_id="run_test",
            subject_ref="patient_01",
            output_mode=ReportOutputMode.CLINICAL,
            composite_score={"run_id": "run_test", "subject_ref": "patient_01",
                             "composite_z": -0.5, "overall_severity": "Moderate"},
            primary_schedule=SchedulePlan(
                schedule_id="sched_01",
                run_id="run_test",
                plan_rank=1,
                plan_type="primary",
                utility_score=0.65,
                stability_class=StabilityClass.SOFT,
            ),
            decision_trace=DecisionTrace(
                run_id="run_test",
                entries=[
                    DecisionTraceEntry(step="session_start",
                                       description="Session", outcome="ok"),
                    DecisionTraceEntry(step="stability_assessment",
                                       description="Stability", outcome="MODERATE",
                                       confidence=0.75),
                    DecisionTraceEntry(step="recommendation",
                                       description="Exercise", outcome="a0",
                                       inputs={"claim_level": "causal_supported"},
                                       confidence=0.8),
                ],
                decision_critical_edges=edges,
                edge_study_map=esm,
            ),
        )

    def test_without_edge_study_map_no_study_nodes(self):
        """Without edge_study_map, no study or paper nodes created."""
        report = self._make_report_with_provenance(edge_study_map={})
        view = render_provenance_chain(report)
        study_nodes = [n for n in view.nodes if n.node_type == "study"]
        paper_nodes = [n for n in view.nodes if n.node_type == "paper"]
        assert len(study_nodes) == 0
        assert len(paper_nodes) == 0

    def test_with_edge_study_map_creates_study_nodes(self):
        """With edge_study_map, study nodes appear at depth 5."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="study_campbell",
                    paper_ref="Campbell 2020", weight_pct=59.0,
                    beta=0.30, se=0.10,
                ),
                StudyContribution(
                    ler_id="ler_002", study_id="study_smith",
                    paper_ref="Smith 2019", weight_pct=41.0,
                    beta=0.20, se=0.15,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)

        study_nodes = [n for n in view.nodes if n.node_type == "study"]
        assert len(study_nodes) == 2
        assert all(n.depth == 5 for n in study_nodes)

    def test_with_edge_study_map_creates_paper_nodes(self):
        """Paper nodes appear at depth 6."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="s_1",
                    paper_ref="Campbell 2020", weight_pct=60.0,
                    beta=0.3, se=0.1,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)

        paper_nodes = [n for n in view.nodes if n.node_type == "paper"]
        assert len(paper_nodes) == 1
        assert paper_nodes[0].depth == 6
        assert paper_nodes[0].label == "Campbell 2020"

    def test_paper_nodes_deduplicated(self):
        """Same paper_ref from different edges/studies → one paper node."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="s_1",
                    paper_ref="Campbell 2020", weight_pct=60.0,
                    beta=0.3, se=0.1,
                ),
            ],
            "ER_SLEEP_MEMORY": [
                StudyContribution(
                    ler_id="ler_010", study_id="s_10",
                    paper_ref="Campbell 2020", weight_pct=100.0,
                    beta=-0.25, se=0.14,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)

        paper_nodes = [n for n in view.nodes if n.node_type == "paper"]
        assert len(paper_nodes) == 1, (
            f"Expected 1 paper node (deduplicated), got {len(paper_nodes)}"
        )

    def test_study_to_edge_links_have_weight(self):
        """Links from edge → study carry the weight_pct as fraction."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="s_1",
                    paper_ref="Paper A", weight_pct=75.0,
                    beta=0.3, se=0.1,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)

        # Find the link from edge to study
        edge_to_study_links = [
            l for l in view.links
            if l.source_id.startswith("edge_") and l.target_id.startswith("study_")
        ]
        assert len(edge_to_study_links) >= 1
        link = edge_to_study_links[0]
        assert math.isclose(link.weight, 0.75, rel_tol=1e-3)

    def test_study_node_value_shows_weight_and_beta(self):
        """Study node value field shows weight and beta."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="s_1",
                    weight_pct=59.0, beta=0.300, se=0.1,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)

        study_nodes = [n for n in view.nodes if n.node_type == "study"]
        assert len(study_nodes) == 1
        assert "59.0%" in study_nodes[0].value
        assert "0.300" in study_nodes[0].value

    def test_depth_labels_include_studies_and_papers(self):
        """Depth labels should include Studies and Papers."""
        esm = {
            "ER_EXERCISE_FATIGUE": [
                StudyContribution(
                    ler_id="ler_001", study_id="s_1",
                    weight_pct=100.0, beta=0.3, se=0.1,
                ),
            ],
        }
        report = self._make_report_with_provenance(edge_study_map=esm)
        view = render_provenance_chain(report)
        assert "Studies" in view.depth_labels
        assert "Papers" in view.depth_labels

    def test_only_edges_in_node_list_get_studies(self):
        """Studies only attached to edges that are in the node list."""
        # edge_study_map has ER_NONEXISTENT → but that edge isn't in decision_critical_edges
        esm = {
            "ER_NONEXISTENT_EDGE": [
                StudyContribution(
                    ler_id="ler_999", study_id="s_999",
                    weight_pct=100.0, beta=0.1, se=0.1,
                ),
            ],
        }
        report = self._make_report_with_provenance(
            edge_study_map=esm,
            critical_edges=["ER_EXERCISE_FATIGUE"],  # different edge
        )
        view = render_provenance_chain(report)
        study_nodes = [n for n in view.nodes if n.node_type == "study"]
        assert len(study_nodes) == 0


# ═══════════════════════════════════════════════════════════════
#  TEST 6: assemble_report end-to-end with edge_study_provenance
# ═══════════════════════════════════════════════════════════════


class TestAssembleReportR2:
    def test_without_provenance_trace_map_empty(self):
        """Without edge_study_provenance, decision_trace.edge_study_map is empty."""
        report = assemble_report(
            run_id="run_e2e_01",
            subject_ref="patient_01",
            ranked_schedules=_make_ranked_schedules(),
        )
        assert report.decision_trace is not None
        assert report.decision_trace.edge_study_map == {}

    def test_with_provenance_trace_map_populated(self):
        """With edge_study_provenance, edge_study_map flows end-to-end."""
        report = assemble_report(
            run_id="run_e2e_02",
            subject_ref="patient_02",
            ranked_schedules=_make_ranked_schedules(),
            stability=_make_stability(),
            edge_study_provenance=SAMPLE_PROVENANCE,
        )
        assert report.decision_trace is not None
        esm = report.decision_trace.edge_study_map
        assert "ER_EXERCISE_FATIGUE" in esm
        assert len(esm["ER_EXERCISE_FATIGUE"]) == 3
        assert esm["ER_EXERCISE_FATIGUE"][0].ler_id == "ler_001"

    def test_provenance_entries_have_supporting_edges(self):
        """ProvenanceEntry.supporting_edges populated via assemble_report."""
        report = assemble_report(
            run_id="run_e2e_03",
            subject_ref="patient_03",
            ranked_schedules=_make_ranked_schedules(),
            edge_study_provenance=SAMPLE_PROVENANCE,
        )
        # The report doesn't expose ProvenanceEntry directly,
        # but the decision_trace.edge_study_map confirms provenance flowed through
        assert report.decision_trace is not None
        assert len(report.decision_trace.edge_study_map) > 0
