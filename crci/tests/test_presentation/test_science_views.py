"""Tests for PRES-SCI1, SCI2, SCI3: Science Interface modules.

Covers:
    SCI1: Evidence browser rendering, gap highlighting, sorting
    SCI2: DAG visualization, pathway highlighting
    SCI3: Provenance chain rendering, trace traversal
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass
from crci.shared.models.output_contracts import (
    CompositeScore,
    DecisionTrace,
    DecisionTraceEntry,
    EvidenceGapItem,
    EvidenceGapReport,
    PathwayContribution,
    PathwayProfile,
    RecommendationReport,
    ScheduleAction,
    SchedulePlan,
)

from crci.presentation.evidence_browser import (
    EdgeRow,
    EvidenceBrowserView,
    render_evidence_browser,
)
from crci.presentation.dag_viz import (
    DAGVizView,
    render_dag_viz,
)
from crci.presentation.provenance_viewer import (
    ProvenanceChainView,
    render_provenance_chain,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_gaps() -> EvidenceGapReport:
    return EvidenceGapReport(
        run_id="run_001",
        gaps=[
            EvidenceGapItem(
                edge_param_id="e1",
                edge_label="Sleep → Cognition",
                gap_type="missing_evidence",
                severity="high",
                description="No studies for this edge.",
                discovery_score=0.8,
                evsi=0.15,
            ),
            EvidenceGapItem(
                edge_param_id="e2",
                edge_label="Exercise → BDNF",
                gap_type="low_k",
                severity="medium",
                description="Only 2 studies available.",
                discovery_score=0.5,
                evsi=0.10,
            ),
            EvidenceGapItem(
                edge_param_id="e3",
                edge_label="Cortisol → Memory",
                gap_type="high_heterogeneity",
                severity="low",
                description="High I² across studies.",
                discovery_score=0.3,
                evsi=0.05,
            ),
        ],
        top_acquisition_targets=["e1", "e2"],
    )


def _make_trace() -> DecisionTrace:
    return DecisionTrace(
        run_id="run_001",
        entries=[
            DecisionTraceEntry(
                step="session_start",
                description="Session with 0 questions",
                outcome="stop_reason=N/A",
            ),
            DecisionTraceEntry(
                step="stability_assessment",
                description="Decision stability: SOFT",
                outcome="P(rank1)=0.650",
                confidence=0.65,
            ),
            DecisionTraceEntry(
                step="recommendation",
                description="Recommend: Exercise",
                inputs={"claim_level": "causal_supported"},
                outcome="intervention_id=ex_1",
            ),
            DecisionTraceEntry(
                step="recommendation",
                description="Recommend: Sleep Hygiene",
                inputs={"claim_level": "associational_only"},
                outcome="intervention_id=sh_1",
            ),
        ],
        decision_critical_edges=["e1", "e2"],
    )


def _make_pathway_profile() -> PathwayProfile:
    return PathwayProfile(
        run_id="run_001",
        subject_ref="patient_001",
        pathway_contributions=[
            PathwayContribution(
                pathway_id="p1",
                pathway_label="Neuroinflammation",
                contribution_fraction=0.4,
                key_edges=["e1", "e3"],
            ),
            PathwayContribution(
                pathway_id="p2",
                pathway_label="HPA Axis",
                contribution_fraction=0.3,
                key_edges=["e2", "e4"],
            ),
        ],
        dominant_pathway_id="p1",
        coverage_fraction=0.7,
    )


def _make_report(
    gaps: EvidenceGapReport | None = None,
    trace: DecisionTrace | None = None,
    pathway: PathwayProfile | None = None,
    primary_actions: bool = True,
) -> RecommendationReport:
    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=-0.5,
        overall_severity=SeverityTier.MODERATE,
    )
    actions = []
    if primary_actions:
        actions = [ScheduleAction(
            action_id="ex_1",
            action_label="Exercise",
            action_class="intervention",
            dose_value=30.0,
            dose_unit="minutes",
            timing_summary="morning",
            frequency="daily",
            duration_days=84,
        )]
    primary = SchedulePlan(
        schedule_id="sched_001",
        run_id="run_001",
        plan_rank=1,
        plan_type="primary",
        actions=actions,
        utility_score=0.65,
        stability_class=StabilityClass.SOFT,
    )
    return RecommendationReport(
        run_id="run_001",
        subject_ref="patient_001",
        output_mode=ReportOutputMode.RESEARCH,
        composite_score=cs,
        primary_schedule=primary,
        evidence_gaps=gaps,
        decision_trace=trace,
        pathway_profile=pathway,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests: SCI1 - Evidence Browser
# ═══════════════════════════════════════════════════════════════


class TestEvidenceBrowser:

    def test_basic_rendering(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report)
        assert isinstance(view, EvidenceBrowserView)
        assert len(view.rows) == 3
        assert view.n_total == 3
        assert view.n_gaps == 2  # missing_evidence + low_k
        assert not view.empty_state

    def test_gap_highlighting(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report)
        gap_rows = [r for r in view.rows if r.has_evidence_gap]
        assert len(gap_rows) == 2

    def test_severity_colors(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report)
        colors = {r.edge_id: r.severity_color for r in view.rows}
        assert colors["e1"] == "red"
        assert colors["e2"] == "orange"
        assert colors["e3"] == "yellow"

    def test_sorted_by_discovery_score(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report, sort_by="discovery_score")
        scores = [r.discovery_score for r in view.rows]
        assert scores == sorted(scores, reverse=True)

    def test_sorted_by_severity(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report, sort_by="severity")
        severities = [r.severity for r in view.rows]
        assert severities[0] == "high"

    def test_gap_summary_includes_targets(self):
        report = _make_report(gaps=_make_gaps())
        view = render_evidence_browser(report)
        assert "e1" in view.gap_summary
        assert "e2" in view.gap_summary

    def test_empty_gaps(self):
        report = _make_report(gaps=None)
        view = render_evidence_browser(report)
        assert view.empty_state
        assert view.n_total == 0

    def test_empty_gap_list(self):
        empty_gaps = EvidenceGapReport(run_id="run_001", gaps=[])
        report = _make_report(gaps=empty_gaps)
        view = render_evidence_browser(report)
        assert view.empty_state


# ═══════════════════════════════════════════════════════════════
#  Tests: SCI2 - DAG Visualization
# ═══════════════════════════════════════════════════════════════


class TestDAGViz:

    def test_basic_rendering(self):
        report = _make_report(
            trace=_make_trace(),
            pathway=_make_pathway_profile(),
        )
        view = render_dag_viz(report)
        assert isinstance(view, DAGVizView)
        assert view.n_nodes > 0
        assert not view.empty_state

    def test_pathway_highlights(self):
        report = _make_report(
            trace=_make_trace(),
            pathway=_make_pathway_profile(),
        )
        view = render_dag_viz(report)
        assert len(view.pathways) == 2
        assert view.pathways[0].pathway_label == "Neuroinflammation"

    def test_recommendation_nodes(self):
        report = _make_report(trace=_make_trace())
        view = render_dag_viz(report)
        rec_nodes = [n for n in view.nodes if "Exercise" in n.label or "Sleep" in n.label]
        assert len(rec_nodes) == 2

    def test_color_mode(self):
        report = _make_report(trace=_make_trace())
        view = render_dag_viz(report, color_mode="layer")
        assert view.color_mode == "layer"

    def test_empty_state(self):
        report = _make_report(trace=None, pathway=None)
        view = render_dag_viz(report)
        assert view.empty_state
        assert view.n_nodes == 0


# ═══════════════════════════════════════════════════════════════
#  Tests: SCI3 - Provenance Chain
# ═══════════════════════════════════════════════════════════════


class TestProvenanceChain:

    def test_basic_rendering(self):
        report = _make_report(trace=_make_trace())
        view = render_provenance_chain(report)
        assert isinstance(view, ProvenanceChainView)
        assert len(view.nodes) > 0
        assert len(view.links) > 0
        assert view.n_recommendations == 2
        assert not view.empty_state

    def test_depth_labels(self):
        report = _make_report(trace=_make_trace())
        view = render_provenance_chain(report)
        assert "Session" in view.depth_labels
        assert "Recommendation" in view.depth_labels

    def test_critical_edges_traced(self):
        report = _make_report(trace=_make_trace())
        view = render_provenance_chain(report)
        assert view.n_edges_traced == 2
        edge_nodes = [n for n in view.nodes if n.node_type == "edge"]
        assert len(edge_nodes) == 2

    def test_score_node_present(self):
        report = _make_report(trace=_make_trace())
        view = render_provenance_chain(report)
        score_nodes = [n for n in view.nodes if n.node_type == "score"]
        assert len(score_nodes) == 1
        assert "SAFE_B" in score_nodes[0].label

    def test_links_exist(self):
        report = _make_report(trace=_make_trace())
        view = render_provenance_chain(report)
        # Should have links: session→stability, stability→rec×2, rec→score, score→edge×2
        assert len(view.links) >= 4

    def test_empty_trace(self):
        report = _make_report(trace=None)
        view = render_provenance_chain(report)
        assert view.empty_state
        assert view.n_recommendations == 0

    def test_empty_trace_entries(self):
        empty_trace = DecisionTrace(run_id="run_001", entries=[])
        report = _make_report(trace=empty_trace)
        view = render_provenance_chain(report)
        assert view.empty_state
