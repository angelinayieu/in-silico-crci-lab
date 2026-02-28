"""
Tests for R3: Per-Edge Variance Contribution to Recommendation.

Verifies that:
1. EdgeInfluence model constructed correctly
2. DecisionTrace.edge_influences populated from sensitivity indices
3. Variance contribution percentages sum to 100%
4. _build_decision_trace() with sensitivity_indices populates edge_influences
5. _build_decision_trace() without sensitivity_indices → empty edge_influences
6. provenance_viewer annotates edge nodes with variance contribution
7. provenance_viewer weights score→edge links by variance contribution
8. assemble_report threads ranking_result.sensitivity_indices → edge_influences
"""
from __future__ import annotations

import math

import pytest

from crci.shared.models.enums import ReportOutputMode, StabilityClass
from crci.shared.models.output_contracts import (
    DecisionTrace,
    DecisionTraceEntry,
    EdgeInfluence,
    RecommendationReport,
    ScheduleAction,
    SchedulePlan,
    StudyContribution,
)
from crci.runtime.report_assembler import (
    ProvenanceEntry,
    UncertaintyDisclosure,
    SessionSummary,
    _build_decision_trace,
    assemble_report,
)
from crci.runtime.schedule_generator import (
    RankedSchedules,
    Schedule,
    ScheduleItem,
)
from crci.presentation.provenance_viewer import render_provenance_chain
from crci.algorithm.chain_d_simulation.ranker import (
    RankingResult,
    SensitivityIndex,
    InterventionRanking,
    ClaimLevel,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus
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

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

SAMPLE_SENSITIVITY_INDICES = [
    SensitivityIndex(
        edge_id="ER_EXERCISE_FATIGUE",
        source_node_id="N_EXERCISE",
        target_node_id="N_FATIGUE",
        elasticity=0.60,
        se_eff=0.10,
        discovery_score=0.06,
    ),
    SensitivityIndex(
        edge_id="ER_SLEEP_MEMORY",
        source_node_id="N_SLEEP",
        target_node_id="N_MEMORY",
        elasticity=0.40,
        se_eff=0.20,
        discovery_score=0.08,
    ),
    SensitivityIndex(
        edge_id="ER_STRESS_COG",
        source_node_id="N_STRESS",
        target_node_id="N_COGNITION",
        elasticity=0.20,
        se_eff=0.15,
        discovery_score=0.03,
    ),
]

# Hand-computed: elasticity² values = 0.36, 0.16, 0.04 → Σ=0.56
# variance_contribution_pct: 0.36/0.56=64.286%, 0.16/0.56=28.571%, 0.04/0.56=7.143%
EXPECTED_VAR_PCT = {
    "ER_EXERCISE_FATIGUE": 0.36 / 0.56 * 100,  # ≈ 64.286%
    "ER_SLEEP_MEMORY": 0.16 / 0.56 * 100,       # ≈ 28.571%
    "ER_STRESS_COG": 0.04 / 0.56 * 100,          # ≈ 7.143%
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


def _make_disclosure(critical_edges: list[str] | None = None) -> UncertaintyDisclosure:
    return UncertaintyDisclosure(
        stability_class="MODERATE",
        p_rank_1=0.75,
        cri_95_lower=0.5,
        cri_95_upper=0.9,
        variance_decomposition={"literature": 0.4, "measurement": 0.3},
        top_reducible_sources=["literature"],
        critical_edges=critical_edges or [
            "ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY", "ER_STRESS_COG",
        ],
    )


def _make_session() -> SessionSummary:
    return SessionSummary(
        n_questions_asked=5,
        n_questions_skipped=1,
        stop_reason="MAX_QUESTIONS",
        total_ig=2.5,
        timestamp="2026-02-28T00:00:00Z",
    )


def _make_stability(critical_edges: list[str] | None = None) -> StabilityState:
    edges = critical_edges or [
        "ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY", "ER_STRESS_COG",
    ]
    return StabilityState(
        rank_1_probabilities={"a0": 0.75, "a1": 0.25},
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[
            CriticalEdge(edge_id=eid, flip_influence=0.3)
            for eid in edges
        ],
        flip_counts={eid: 200 for eid in edges},
        pairwise_dominance={},
        n_draws=1000,
        n_interventions=2,
    )


def _make_ranking_result() -> RankingResult:
    """Build minimal RankingResult with sensitivity indices."""
    return RankingResult(
        intervention_rankings={
            "a0": InterventionRanking(
                action_id="a0",
                action_label="Exercise",
                safety_status=SafetyStatus.CLEAR,
                mss_cog=0.5,
                mss_burden=0.2,
                safe_a=0.44,
                safe_a_cri_lower=0.30,
                safe_a_cri_upper=0.58,
                rank_a=1,
                p_adhere=0.8,
                safe_b=0.55,
                safe_b_cri_lower=0.40,
                safe_b_cri_upper=0.70,
                rank_b=1,
                adherence_warning=False,
                dose_recommended=3.0,
                dose_conflict=False,
                dose_conflict_ratio=None,
                claim_level=ClaimLevel.CAUSAL_SUPPORTED,
                per_draw_safe_a=np.zeros(100),
            ),
        },
        bundle_rankings={},
        sensitivity_indices=SAMPLE_SENSITIVITY_INDICES,
        top_discovery_edges=SAMPLE_SENSITIVITY_INDICES[:2],
        dose_recommendations={},
        n_interventions_ranked=1,
        n_bundles_ranked=0,
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


# ═══════════════════════════════════════════════════════════════
#  TEST 1: EdgeInfluence Model
# ═══════════════════════════════════════════════════════════════


class TestEdgeInfluenceModel:
    def test_basic_construction(self):
        ei = EdgeInfluence(
            edge_id="ER_EXERCISE_FATIGUE",
            elasticity=0.60,
            discovery_score=0.06,
            variance_contribution_pct=64.3,
        )
        assert ei.edge_id == "ER_EXERCISE_FATIGUE"
        assert ei.elasticity == 0.60
        assert ei.variance_contribution_pct == 64.3

    def test_serialization_roundtrip(self):
        ei = EdgeInfluence(
            edge_id="ER_SLEEP_MEMORY",
            elasticity=-0.40,
            discovery_score=0.08,
            variance_contribution_pct=28.6,
        )
        d = ei.model_dump()
        ei2 = EdgeInfluence(**d)
        assert ei2 == ei


# ═══════════════════════════════════════════════════════════════
#  TEST 2: DecisionTrace.edge_influences
# ═══════════════════════════════════════════════════════════════


class TestDecisionTraceEdgeInfluences:
    def test_empty_by_default(self):
        dt = DecisionTrace(run_id="run_01")
        assert dt.edge_influences == {}

    def test_populated_from_data(self):
        ei = EdgeInfluence(
            edge_id="ER_TEST",
            elasticity=0.5,
            discovery_score=0.05,
            variance_contribution_pct=100.0,
        )
        dt = DecisionTrace(
            run_id="run_02",
            edge_influences={"ER_TEST": ei},
        )
        assert "ER_TEST" in dt.edge_influences
        assert dt.edge_influences["ER_TEST"].variance_contribution_pct == 100.0


# ═══════════════════════════════════════════════════════════════
#  TEST 3: _build_decision_trace with sensitivity_indices
# ═══════════════════════════════════════════════════════════════


class TestBuildDecisionTraceR3:
    def test_without_sensitivity_empty_influences(self):
        """Without sensitivity_indices, edge_influences is empty."""
        provenance = [ProvenanceEntry(
            intervention_id="a0",
            intervention_label="Label a0",
            claim_level="causal_supported",
        )]
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_01",
        )
        assert trace.edge_influences == {}

    def test_with_sensitivity_populates_influences(self):
        """With sensitivity_indices, edge_influences gets populated."""
        provenance = [ProvenanceEntry(
            intervention_id="a0",
            intervention_label="Label a0",
            claim_level="causal_supported",
        )]
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_02",
            sensitivity_indices=SAMPLE_SENSITIVITY_INDICES,
        )
        assert len(trace.edge_influences) == 3
        assert "ER_EXERCISE_FATIGUE" in trace.edge_influences
        assert "ER_SLEEP_MEMORY" in trace.edge_influences
        assert "ER_STRESS_COG" in trace.edge_influences

    def test_variance_contribution_sums_to_100(self):
        """Variance contribution percentages sum to 100%."""
        provenance = []
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_03",
            sensitivity_indices=SAMPLE_SENSITIVITY_INDICES,
        )
        total_pct = sum(
            ei.variance_contribution_pct
            for ei in trace.edge_influences.values()
        )
        assert math.isclose(total_pct, 100.0, rel_tol=1e-6)

    def test_variance_contributions_match_hand_computed(self):
        """Hand-computed: ε²/Σε² for each edge."""
        provenance = []
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_04",
            sensitivity_indices=SAMPLE_SENSITIVITY_INDICES,
        )
        for edge_id, expected in EXPECTED_VAR_PCT.items():
            actual = trace.edge_influences[edge_id].variance_contribution_pct
            assert math.isclose(actual, expected, rel_tol=1e-4), (
                f"{edge_id}: expected {expected:.3f}%, got {actual:.3f}%"
            )

    def test_single_edge_gets_100pct(self):
        """Single edge → 100% variance contribution."""
        single = [SAMPLE_SENSITIVITY_INDICES[0]]
        provenance = []
        trace = _build_decision_trace(
            provenance, _make_disclosure(["ER_EXERCISE_FATIGUE"]),
            _make_session(), "run_05",
            sensitivity_indices=single,
        )
        assert len(trace.edge_influences) == 1
        ei = trace.edge_influences["ER_EXERCISE_FATIGUE"]
        assert math.isclose(ei.variance_contribution_pct, 100.0)

    def test_elasticity_preserved(self):
        """Elasticity values carried through from SensitivityIndex."""
        provenance = []
        trace = _build_decision_trace(
            provenance, _make_disclosure(), _make_session(), "run_06",
            sensitivity_indices=SAMPLE_SENSITIVITY_INDICES,
        )
        ei = trace.edge_influences["ER_EXERCISE_FATIGUE"]
        assert math.isclose(ei.elasticity, 0.60)
        assert math.isclose(ei.discovery_score, 0.06)


# ═══════════════════════════════════════════════════════════════
#  TEST 4: Provenance Viewer with R3 edge_influences
# ═══════════════════════════════════════════════════════════════


class TestProvenanceViewerR3:
    def _make_report(
        self,
        edge_influences: dict[str, EdgeInfluence] | None = None,
        critical_edges: list[str] | None = None,
    ) -> RecommendationReport:
        edges = critical_edges or [
            "ER_EXERCISE_FATIGUE", "ER_SLEEP_MEMORY",
        ]
        ei = edge_influences or {}
        return RecommendationReport(
            run_id="run_viz",
            subject_ref="patient_01",
            output_mode=ReportOutputMode.CLINICAL,
            composite_score={"run_id": "run_viz", "subject_ref": "patient_01",
                             "composite_z": -0.5, "overall_severity": "Moderate"},
            primary_schedule=SchedulePlan(
                schedule_id="sched_01",
                run_id="run_viz",
                plan_rank=1,
                plan_type="primary",
                actions=[ScheduleAction(
                    action_id="a0",
                    action_label="Exercise",
                    action_class="physical",
                    dose_value=3.0,
                    dose_unit="sessions/week",
                    timing_summary="3× per week",
                    frequency="3x/week",
                    duration_days=90,
                )],
                utility_score=0.65,
                stability_class=StabilityClass.SOFT,
            ),
            decision_trace=DecisionTrace(
                run_id="run_viz",
                entries=[
                    DecisionTraceEntry(step="session_start",
                                       description="Session", outcome="ok"),
                    DecisionTraceEntry(step="stability_assessment",
                                       description="Stability", outcome="MOD",
                                       confidence=0.75),
                    DecisionTraceEntry(step="recommendation",
                                       description="Exercise", outcome="a0",
                                       inputs={"claim_level": "causal_supported"},
                                       confidence=0.8),
                ],
                decision_critical_edges=edges,
                edge_influences=ei,
            ),
        )

    def test_without_influences_fallback_weight(self):
        """Without edge_influences, score→edge links use 0.5 weight."""
        report = self._make_report()
        view = render_provenance_chain(report)
        score_to_edge = [
            l for l in view.links
            if l.source_id.startswith("score_") and l.target_id.startswith("edge_")
        ]
        assert all(l.weight == 0.5 for l in score_to_edge)

    def test_with_influences_weighted_links(self):
        """With edge_influences, score→edge links use variance_contribution_pct/100."""
        ei_map = {
            "ER_EXERCISE_FATIGUE": EdgeInfluence(
                edge_id="ER_EXERCISE_FATIGUE",
                elasticity=0.6, discovery_score=0.06,
                variance_contribution_pct=70.0,
            ),
            "ER_SLEEP_MEMORY": EdgeInfluence(
                edge_id="ER_SLEEP_MEMORY",
                elasticity=0.4, discovery_score=0.08,
                variance_contribution_pct=30.0,
            ),
        }
        report = self._make_report(edge_influences=ei_map)
        view = render_provenance_chain(report)

        score_to_edge = {
            l.target_id: l
            for l in view.links
            if l.source_id.startswith("score_") and l.target_id.startswith("edge_")
        }
        assert math.isclose(
            score_to_edge["edge_ER_EXERCISE_FATIGUE"].weight, 0.70, rel_tol=1e-3,
        )
        assert math.isclose(
            score_to_edge["edge_ER_SLEEP_MEMORY"].weight, 0.30, rel_tol=1e-3,
        )

    def test_edge_node_value_shows_variance_pct(self):
        """Edge node value field shows variance contribution %."""
        ei_map = {
            "ER_EXERCISE_FATIGUE": EdgeInfluence(
                edge_id="ER_EXERCISE_FATIGUE",
                elasticity=0.600, discovery_score=0.06,
                variance_contribution_pct=64.3,
            ),
        }
        report = self._make_report(
            edge_influences=ei_map,
            critical_edges=["ER_EXERCISE_FATIGUE"],
        )
        view = render_provenance_chain(report)

        edge_node = next(n for n in view.nodes if n.node_type == "edge")
        assert "64.3%" in edge_node.value
        assert "0.600" in edge_node.value

    def test_edge_without_influence_shows_decision_critical(self):
        """Edge not in edge_influences still shows 'decision-critical'."""
        report = self._make_report(
            edge_influences={},
            critical_edges=["ER_EXERCISE_FATIGUE"],
        )
        view = render_provenance_chain(report)
        edge_node = next(n for n in view.nodes if n.node_type == "edge")
        assert edge_node.value == "decision-critical"

    def test_link_label_shows_variance_pct(self):
        """Score→edge link label shows variance % when available."""
        ei_map = {
            "ER_EXERCISE_FATIGUE": EdgeInfluence(
                edge_id="ER_EXERCISE_FATIGUE",
                elasticity=0.6, discovery_score=0.06,
                variance_contribution_pct=64.3,
            ),
        }
        report = self._make_report(
            edge_influences=ei_map,
            critical_edges=["ER_EXERCISE_FATIGUE"],
        )
        view = render_provenance_chain(report)
        link = next(
            l for l in view.links
            if l.target_id == "edge_ER_EXERCISE_FATIGUE"
            and l.source_id.startswith("score_")
        )
        assert "64.3%" in link.label


# ═══════════════════════════════════════════════════════════════
#  TEST 5: assemble_report end-to-end with ranking_result
# ═══════════════════════════════════════════════════════════════


class TestAssembleReportR3:
    def test_without_ranking_result_empty_influences(self):
        """Without ranking_result, edge_influences is empty."""
        report = assemble_report(
            run_id="run_e2e_r3_01",
            subject_ref="patient_01",
            ranked_schedules=_make_ranked_schedules(),
        )
        assert report.decision_trace is not None
        assert report.decision_trace.edge_influences == {}

    def test_with_ranking_result_influences_populated(self):
        """With ranking_result having sensitivity_indices, edge_influences populated."""
        report = assemble_report(
            run_id="run_e2e_r3_02",
            subject_ref="patient_02",
            ranked_schedules=_make_ranked_schedules(),
            stability=_make_stability(),
            ranking_result=_make_ranking_result(),
        )
        assert report.decision_trace is not None
        ei = report.decision_trace.edge_influences
        assert len(ei) == 3
        assert "ER_EXERCISE_FATIGUE" in ei
        # Check variance contribution is sensible
        total = sum(e.variance_contribution_pct for e in ei.values())
        assert math.isclose(total, 100.0, rel_tol=1e-6)

    def test_sensitivity_report_also_present(self):
        """sensitivity_report still populated independently from edge_influences."""
        report = assemble_report(
            run_id="run_e2e_r3_03",
            subject_ref="patient_03",
            ranked_schedules=_make_ranked_schedules(),
            ranking_result=_make_ranking_result(),
        )
        assert report.sensitivity_report is not None
        assert len(report.sensitivity_report.sensitivity_indices) == 3

    def test_combined_r2_r3_both_populated(self):
        """Both edge_study_map (R2) and edge_influences (R3) can coexist."""
        provenance = {
            "ER_EXERCISE_FATIGUE": [
                {
                    "ler_id": "ler_001",
                    "study_id": "s_1",
                    "weight_normalized": 0.6,
                    "beta": 0.3,
                    "se": 0.1,
                    "paper_ref": "Smith 2020",
                },
            ],
        }
        report = assemble_report(
            run_id="run_e2e_r3_04",
            subject_ref="patient_04",
            ranked_schedules=_make_ranked_schedules(),
            stability=_make_stability(),
            ranking_result=_make_ranking_result(),
            edge_study_provenance=provenance,
        )
        trace = report.decision_trace
        assert trace is not None
        # R2
        assert "ER_EXERCISE_FATIGUE" in trace.edge_study_map
        assert len(trace.edge_study_map["ER_EXERCISE_FATIGUE"]) == 1
        # R3
        assert "ER_EXERCISE_FATIGUE" in trace.edge_influences
        assert trace.edge_influences["ER_EXERCISE_FATIGUE"].variance_contribution_pct > 0
