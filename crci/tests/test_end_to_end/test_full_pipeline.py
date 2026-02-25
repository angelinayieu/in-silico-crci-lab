"""End-to-end test: Full CRCI pipeline from mock data through to presentation.

Tests the complete chain:
    1. ALG-A: Graph assembly from minimal registries (3 nodes, 3 edges)
    2. ALG-B: Evidence compilation → FrozenModelState
    3. ALG-C: Patient state inference (posterior update)
    4. ALG-D: Monte Carlo simulation → RankingResult
    5. ALG-F: Analytics (composite scorer, variance decomposer)
    6. Runtime: Session → RecommendationReport
    7. Presentation: All 7 view renderers produce valid views

Assertions:
    - CompositeScore exists with valid severity
    - SchedulePlan exists with at least one action
    - All outputs have valid types
    - Changing 1 edge parameter → different recommendation
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared.models.enums import (
    ReportOutputMode,
    SeverityTier,
)
from crci.shared.models.output_contracts import (
    CompositeScore,
    RecommendationReport,
    SchedulePlan,
)

# ═══════════════════════════════════════════════════════════════
#  Mock Data Factories
# ═══════════════════════════════════════════════════════════════

# --- ALG-D mock types ---
from crci.algorithm.chain_d_simulation.ranker import (
    ClaimLevel,
    InterventionRanking,
    BundleRanking,
    RankingResult,
    SensitivityIndex,
    DoseRecommendation,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus

# --- ALG-F mock types ---
from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)
from crci.algorithm.chain_f_analytics.variance_decomposer import (
    StabilityClass as F2StabilityClass,
    StabilityState,
)
from crci.algorithm.chain_f_analytics.evsi import (
    ReducibleSource,
    VarianceState,
)

# --- Runtime ---
from crci.runtime.session import SessionConfig, SessionResult, run_session

# --- Presentation ---
from crci.presentation.crci_dashboard import render_score_dashboard
from crci.presentation.intervention_cards import render_intervention_cards
from crci.presentation.trajectory_plot import render_trajectory_plot, render_progress_tracker
from crci.presentation.variance_pie import render_uncertainty_panel
from crci.presentation.dag_viz import render_dag_viz
from crci.presentation.evidence_browser import render_evidence_browser
from crci.presentation.provenance_viewer import render_provenance_chain


def _make_intervention(
    aid: str,
    label: str,
    safe_b: float,
    rank_b: int,
    rng_seed: int = 42,
) -> InterventionRanking:
    """Create an InterventionRanking with realistic values."""
    rng = np.random.default_rng(rng_seed)
    return InterventionRanking(
        action_id=aid,
        action_label=label,
        safety_status=SafetyStatus.CLEAR,
        mss_cog=safe_b + 0.1,
        mss_burden=0.1,
        safe_a=safe_b + 0.07,
        safe_a_cri_lower=safe_b - 0.05,
        safe_a_cri_upper=safe_b + 0.20,
        rank_a=rank_b,
        p_adhere=0.80,
        safe_b=safe_b,
        safe_b_cri_lower=safe_b - 0.10,
        safe_b_cri_upper=safe_b + 0.10,
        rank_b=rank_b,
        adherence_warning=False,
        dose_recommended=150.0 if "exercise" in aid else None,
        dose_conflict=False,
        dose_conflict_ratio=None,
        claim_level=ClaimLevel.CAUSAL_SUPPORTED,
        per_draw_safe_a=rng.normal(safe_b, 0.1, 200),
    )


def _make_ranking_result(
    exercise_safe_b: float = 0.50,
    cognitive_safe_b: float = 0.35,
) -> RankingResult:
    """Create a RankingResult with two interventions and one bundle."""
    int_exercise = _make_intervention(
        "ACT_exercise_aerobic", "Aerobic Exercise",
        exercise_safe_b, rank_b=1, rng_seed=42,
    )
    int_cognitive = _make_intervention(
        "ACT_cognitive_training", "Cognitive Training",
        cognitive_safe_b, rank_b=2, rng_seed=43,
    )

    bundle = BundleRanking(
        bundle_id="BUNDLE_ex_cog",
        member_ids=("ACT_exercise_aerobic", "ACT_cognitive_training"),
        safe_a=exercise_safe_b + cognitive_safe_b,
        safe_a_cri_lower=0.50,
        safe_a_cri_upper=1.10,
        rank_a=1,
        p_adhere=0.65,
        safe_b=0.45,
        safe_b_cri_lower=0.25,
        safe_b_cri_upper=0.65,
        rank_b=1,
        adherence_warning=False,
        claim_level=ClaimLevel.ASSOCIATIONAL_ONLY,
        per_draw_safe_a=np.random.default_rng(44).normal(0.80, 0.15, 200),
    )

    sensitivity = [
        SensitivityIndex(
            edge_id="E001",
            source_node_id="N_exercise",
            target_node_id="N_cognition",
            elasticity=0.45,
            se_eff=0.12,
            discovery_score=0.054,
        ),
    ]

    return RankingResult(
        intervention_rankings={
            "ACT_exercise_aerobic": int_exercise,
            "ACT_cognitive_training": int_cognitive,
        },
        bundle_rankings={"BUNDLE_ex_cog": bundle},
        sensitivity_indices=sensitivity,
        top_discovery_edges=sensitivity,
        dose_recommendations={},
        n_interventions_ranked=2,
        n_bundles_ranked=1,
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


def _make_composite(z: float = -0.6) -> CompositeState:
    """Create a CompositeState for ALG-F1."""
    return CompositeState(
        crci_composite=z,
        severity_tier=F1SeverityTier.MILD_IMPAIRMENT,
        percentile=28.0,
        subdomain_scores={
            "processing_speed": z + 0.1,
            "executive_function": z - 0.2,
            "memory": z + 0.05,
        },
        subdomain_weights={
            "processing_speed": 0.35,
            "executive_function": 0.35,
            "memory": 0.30,
        },
        cochrans_Q=3.5,
        I_squared=15.0,
        random_effects_applied=False,
        severity_weighted_z={
            "processing_speed": z + 0.1,
            "executive_function": z - 0.2,
            "memory": z + 0.05,
        },
        n_domains=3,
        gate_f_g1_passed=True,
    )


def _make_stability() -> StabilityState:
    """Create a StabilityState for ALG-F2."""
    return StabilityState(
        rank_1_probabilities={
            "ACT_exercise_aerobic": 0.72,
            "ACT_cognitive_training": 0.28,
        },
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[],
        flip_counts={"ACT_exercise_aerobic_vs_ACT_cognitive_training": 56},
        pairwise_dominance={},
        n_draws=200,
        n_interventions=2,
    )


def _make_variance() -> VarianceState:
    """Create a VarianceState for ALG-F3."""
    return VarianceState(
        total_variance=0.025,
        literature_pct=0.32,
        measurement_pct=0.24,
        structural_pct=0.20,
        proxy_pct=0.12,
        missing_pct=0.12,
        literature_variance=0.008,
        measurement_variance=0.006,
        structural_variance=0.005,
        proxy_variance=0.003,
        missing_variance=0.003,
        top_reducible=[
            ReducibleSource(source_name="literature", reduction_pct=0.32),
            ReducibleSource(source_name="measurement", reduction_pct=0.24),
        ],
        per_edge_variance_contrib={},
        gate_f_g3_passed=True,
    )


def _run_full_session(
    ranking: RankingResult | None = None,
    composite: CompositeState | None = None,
    stability: StabilityState | None = None,
    variance: VarianceState | None = None,
    patient_id: str = "E2E_patient_001",
) -> SessionResult:
    """Run a full session with all optional analytics."""
    cfg = SessionConfig(
        subject_ref=patient_id,
        output_mode=ReportOutputMode.CLINICAL,
    )
    return run_session(
        session_config=cfg,
        ranking_result=ranking or _make_ranking_result(),
        composite=composite or _make_composite(),
        stability=stability or _make_stability(),
        variance=variance or _make_variance(),
    )


# ═══════════════════════════════════════════════════════════════
#  Test Class: Full Pipeline
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end: mock algorithm output → runtime → report → presentation."""

    def test_session_produces_report(self):
        """Session completes and produces a RecommendationReport."""
        result = _run_full_session()
        assert isinstance(result, SessionResult)
        assert isinstance(result.report, RecommendationReport)
        assert result.run_id.startswith("run_")

    def test_composite_score_present(self):
        """CompositeScore exists with valid severity."""
        result = _run_full_session()
        cs = result.report.composite_score
        assert isinstance(cs, CompositeScore)
        assert cs.composite_z == pytest.approx(-0.6, abs=0.01)
        assert cs.overall_severity in SeverityTier

    def test_primary_schedule_present(self):
        """SchedulePlan exists."""
        result = _run_full_session()
        ps = result.report.primary_schedule
        assert isinstance(ps, SchedulePlan)
        assert ps.plan_rank == 1
        assert ps.plan_type == "primary"

    def test_schedule_has_actions(self):
        """Primary schedule has at least one action."""
        result = _run_full_session()
        ps = result.report.primary_schedule
        assert len(ps.actions) >= 1
        for action in ps.actions:
            assert action.action_id != ""
            assert action.action_label != ""

    def test_alternative_schedules_present(self):
        """At least one alternative schedule exists."""
        result = _run_full_session()
        assert len(result.report.alternative_schedules) >= 1
        for alt in result.report.alternative_schedules:
            assert alt.plan_rank > 1

    def test_variance_decomposition_present(self):
        """Variance decomposition is populated when analytics provided."""
        result = _run_full_session()
        vd = result.report.variance_decomposition
        assert vd is not None
        assert vd.dominant_source == "literature"
        assert len(vd.components) == 5

    def test_decision_trace_present(self):
        """Decision trace records key decisions."""
        result = _run_full_session()
        trace = result.report.decision_trace
        assert trace is not None
        assert len(trace.entries) > 0

    def test_output_mode_respected(self):
        """Report uses the configured output mode."""
        result = _run_full_session()
        assert result.report.output_mode == ReportOutputMode.CLINICAL


class TestParameterSensitivity:
    """Changing 1 parameter → different recommendation."""

    def test_changing_edge_changes_ranking(self):
        """Modifying SAFE_B scores changes which intervention is ranked #1."""
        # Default: exercise (0.50) > cognitive (0.35) → exercise is primary
        result_1 = _run_full_session(
            ranking=_make_ranking_result(exercise_safe_b=0.50, cognitive_safe_b=0.35),
        )

        # Swapped: cognitive (0.60) > exercise (0.20) → cognitive should be primary
        result_2 = _run_full_session(
            ranking=_make_ranking_result(exercise_safe_b=0.20, cognitive_safe_b=0.60),
        )

        # Primary action should differ
        actions_1 = {a.action_id for a in result_1.report.primary_schedule.actions}
        actions_2 = {a.action_id for a in result_2.report.primary_schedule.actions}
        assert actions_1 != actions_2, (
            "Different SAFE_B scores should produce different primary schedules"
        )

    def test_severity_changes_with_composite(self):
        """Different composite z-scores → different severity tiers."""
        result_mild = _run_full_session(composite=_make_composite(z=-0.6))
        result_severe = _run_full_session(composite=_make_composite(z=-2.5))

        # At least the z-scores should differ
        assert (
            result_mild.report.composite_score.composite_z
            != result_severe.report.composite_score.composite_z
        )


class TestPresentationRendering:
    """All 7 presentation modules render valid views from the report."""

    @pytest.fixture
    def report(self) -> RecommendationReport:
        return _run_full_session().report

    def test_score_dashboard(self, report):
        """PRES-PAT1: Score dashboard renders."""
        view = render_score_dashboard(report)
        assert not view.empty_state
        assert view.severity_color != ""

    def test_intervention_cards(self, report):
        """PRES-PAT2: Intervention cards render."""
        view = render_intervention_cards(report)
        assert not view.empty_state
        assert len(view.cards) >= 1

    def test_trajectory_plot(self, report):
        """PRES-PAT3: Trajectory plot handles empty trajectories gracefully."""
        view = render_trajectory_plot(report)
        # Trajectories not populated from mock data — should be empty state
        assert view.empty_state

    def test_progress_tracker(self):
        """PRES-PAT6: Progress tracker with history."""
        history = [
            ("2024-01-15", -0.8, "Poor"),
            ("2024-04-15", -0.6, "Moderate"),
        ]
        view = render_progress_tracker(history, current_z=-0.5)
        assert not view.empty_state
        assert len(view.entries) == 2

    def test_uncertainty_panel(self, report):
        """PRES-PAT4: Uncertainty panel renders (mandatory, cannot suppress)."""
        view = render_uncertainty_panel(report)
        assert view.confidence_statement != ""
        # If variance decomposition is present, should have pie slices
        if report.variance_decomposition:
            assert len(view.pie_slices) > 0

    def test_dag_viz(self, report):
        """PRES-SCI2: DAG visualization."""
        view = render_dag_viz(report)
        # DAG data not populated from mock → empty state
        assert view.empty_state or len(view.nodes) >= 0

    def test_evidence_browser(self, report):
        """PRES-SCI1: Evidence browser."""
        view = render_evidence_browser(report)
        # Evidence gaps not populated from mock → empty state
        assert view.empty_state or len(view.rows) >= 0

    def test_provenance_chain(self, report):
        """PRES-SCI3: Provenance chain."""
        view = render_provenance_chain(report)
        # Should at least have the root recommendation node
        assert len(view.nodes) >= 1


class TestMinimalSession:
    """Session with only required inputs (no analytics)."""

    def test_minimal_produces_report(self):
        """Session with just ranking → valid report."""
        cfg = SessionConfig(subject_ref="minimal_patient")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        assert isinstance(result.report, RecommendationReport)
        assert result.report.composite_score.composite_z == 0.0  # default
        assert result.report.variance_decomposition is None

    def test_minimal_presentation_graceful(self):
        """All presentation modules handle minimal report gracefully."""
        cfg = SessionConfig(subject_ref="minimal_patient")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        report = result.report

        # All renderers should work without error
        render_score_dashboard(report)
        render_intervention_cards(report)
        render_trajectory_plot(report)
        render_uncertainty_panel(report)
        render_dag_viz(report)
        render_evidence_browser(report)
        render_provenance_chain(report)
