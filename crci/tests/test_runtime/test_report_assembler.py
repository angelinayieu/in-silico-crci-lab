"""Tests for RT-I Report Assembler.

Covers:
    I1: Evidence provenance building
    I2: Mandatory uncertainty disclosure
    I3: Session summary
    I4: Full report assembly
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, StabilityClass
from crci.shared.models.output_contracts import RecommendationReport

from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)
from crci.algorithm.chain_f_analytics.variance_decomposer import (
    CriticalEdge,
    StabilityClass as F2StabilityClass,
    StabilityState,
)
from crci.algorithm.chain_f_analytics.evsi import ReducibleSource, VarianceState

from crci.runtime.schedule_generator import (
    RankedSchedules,
    Schedule,
    ScheduleItem,
    TimingVariant,
)
from crci.runtime.adaptive_questions import (
    QuestioningState,
    StopReason,
)
from crci.runtime.report_assembler import (
    ProvenanceEntry,
    UncertaintyDisclosure,
    SessionSummary,
    _build_provenance,
    _build_uncertainty_disclosure,
    _build_session_summary,
    _build_composite_score,
    _build_variance_decomposition,
    assemble_report,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


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


def _make_composite() -> CompositeState:
    return CompositeState(
        crci_composite=-0.5,
        severity_tier=F1SeverityTier.MILD_IMPAIRMENT,
        percentile=30.0,
        subdomain_scores={"processing_speed": -0.3, "memory_verbal": -0.7},
        subdomain_weights={"processing_speed": 1.0, "memory_verbal": 1.5},
        cochrans_Q=5.0,
        I_squared=20.0,
        random_effects_applied=False,
        severity_weighted_z={"processing_speed": -0.3, "memory_verbal": -1.05},
        n_domains=2,
        gate_f_g1_passed=True,
    )


def _make_stability() -> StabilityState:
    return StabilityState(
        rank_1_probabilities={"a0": 0.75, "a1": 0.25},
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[
            CriticalEdge(edge_id="e1", flip_influence=0.15),
        ],
        flip_counts={},
        pairwise_dominance={},
        n_draws=200,
        n_interventions=2,
    )


def _make_variance() -> VarianceState:
    return VarianceState(
        total_variance=1.0,
        literature_pct=0.30,
        measurement_pct=0.15,
        structural_pct=0.20,
        proxy_pct=0.15,
        missing_pct=0.20,
        literature_variance=0.30,
        measurement_variance=0.15,
        structural_variance=0.20,
        proxy_variance=0.15,
        missing_variance=0.20,
        top_reducible=[
            ReducibleSource(source_name="missing_observations", reduction_pct=0.20),
            ReducibleSource(source_name="measurement_noise", reduction_pct=0.15),
        ],
        per_edge_variance_contrib={},
    )


def _make_questioning() -> QuestioningState:
    state = QuestioningState(questions_asked=[])
    state.n_questions = 5
    state.n_skipped = 1
    state.stop_reason = StopReason.STABILITY_REACHED
    state.total_ig = 1.5
    return state


# ═══════════════════════════════════════════════════════════════
#  Test I1: Provenance
# ═══════════════════════════════════════════════════════════════


class TestProvenance:
    """Test evidence provenance building."""

    def test_basic_provenance(self):
        schedules = [_make_schedule("a1", rank=1)]
        entries = _build_provenance(schedules)
        assert len(entries) == 1
        assert entries[0].intervention_id == "a1"
        assert entries[0].claim_level == "causal_supported"

    def test_multiple_schedules(self):
        schedules = [_make_schedule(f"a{i}", rank=i + 1) for i in range(3)]
        entries = _build_provenance(schedules)
        assert len(entries) == 3

    def test_empty_schedules(self):
        entries = _build_provenance([])
        assert len(entries) == 0


# ═══════════════════════════════════════════════════════════════
#  Test I2: Uncertainty Disclosure
# ═══════════════════════════════════════════════════════════════


class TestUncertaintyDisclosure:
    """Test mandatory uncertainty disclosure."""

    def test_basic_disclosure(self):
        stab = _make_stability()
        var = _make_variance()
        sched = _make_schedule()
        disc = _build_uncertainty_disclosure(stab, var, sched)
        assert disc.stability_class == "MODERATE"
        assert disc.p_rank_1 == 0.75
        assert abs(disc.variance_decomposition["literature"] - 0.30) < 1e-10
        assert len(disc.top_reducible_sources) == 2
        assert disc.warning_text is None  # Not highly unstable

    def test_highly_unstable_warning(self):
        stab = _make_stability()
        stab.stability_class = F2StabilityClass.HIGHLY_UNSTABLE
        disc = _build_uncertainty_disclosure(stab, None, None)
        assert disc.warning_text is not None
        assert "highly uncertain" in disc.warning_text.lower()

    def test_none_inputs(self):
        disc = _build_uncertainty_disclosure(None, None, None)
        assert disc.stability_class == "MODERATE"
        assert disc.p_rank_1 == 0.0

    def test_critical_edges_included(self):
        stab = _make_stability()
        disc = _build_uncertainty_disclosure(stab, None, None)
        assert "e1" in disc.critical_edges


# ═══════════════════════════════════════════════════════════════
#  Test I3: Session Summary
# ═══════════════════════════════════════════════════════════════


class TestSessionSummary:
    """Test session summary building."""

    def test_with_questioning(self):
        qs = _make_questioning()
        summary = _build_session_summary(qs)
        assert summary.n_questions_asked == 5
        assert summary.n_questions_skipped == 1
        assert summary.stop_reason == "stability_reached"

    def test_none_questioning(self):
        summary = _build_session_summary(None)
        assert summary.n_questions_asked == 0
        assert summary.timestamp is not None


# ═══════════════════════════════════════════════════════════════
#  Test Composite Score Building
# ═══════════════════════════════════════════════════════════════


class TestCompositeScore:
    """Test composite score output building."""

    def test_basic_composite(self):
        comp = _make_composite()
        cs = _build_composite_score(comp, "run1", "patient1")
        assert cs.composite_z == -0.5
        assert cs.composite_percentile == 30.0
        assert len(cs.domain_scores) == 2

    def test_none_composite(self):
        cs = _build_composite_score(None, "run1", "patient1")
        assert cs.composite_z == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test Variance Decomposition Building
# ═══════════════════════════════════════════════════════════════


class TestVarianceDecomposition:
    """Test variance decomposition output building."""

    def test_basic_decomposition(self):
        var = _make_variance()
        vd = _build_variance_decomposition(var, "run1")
        assert vd is not None
        assert len(vd.components) == 5
        assert vd.total_variance == 1.0
        assert vd.dominant_source is not None

    def test_none_variance(self):
        vd = _build_variance_decomposition(None, "run1")
        assert vd is None


# ═══════════════════════════════════════════════════════════════
#  Integration: Full Report Assembly
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full RT-I pipeline tests."""

    def test_full_report(self):
        report = assemble_report(
            run_id="run_001",
            subject_ref="patient_001",
            ranked_schedules=_make_ranked_schedules(3),
            composite=_make_composite(),
            stability=_make_stability(),
            variance=_make_variance(),
            questioning=_make_questioning(),
        )
        assert isinstance(report, RecommendationReport)
        assert report.run_id == "run_001"
        assert report.subject_ref == "patient_001"
        assert report.composite_score.composite_z == -0.5
        assert report.primary_schedule.plan_rank == 1
        assert len(report.alternative_schedules) == 2
        assert report.variance_decomposition is not None
        assert report.decision_trace is not None
        assert len(report.decision_trace.entries) > 0

    def test_minimal_report(self):
        """Report with minimal inputs (no composite, stability, etc.)."""
        report = assemble_report(
            run_id="run_002",
            subject_ref="patient_002",
            ranked_schedules=_make_ranked_schedules(1),
        )
        assert report.run_id == "run_002"
        assert report.composite_score.composite_z == 0.0
        assert report.variance_decomposition is None

    def test_empty_schedules(self):
        """Report with no schedules → empty primary."""
        rs = RankedSchedules(
            schedules=[],
            n_expanded=0,
            n_feasible=0,
            n_excluded=0,
            excluded_reasons=[],
            gate_g_g1_passed=False,
        )
        report = assemble_report(
            run_id="run_003",
            subject_ref="patient_003",
            ranked_schedules=rs,
        )
        assert report.primary_schedule.schedule_id == "empty"
        assert len(report.alternative_schedules) == 0

    def test_marginal_recommendation_warning(self):
        """Gate G-G2 not passed → warning in report."""
        rs = _make_ranked_schedules(1)
        rs.gate_g_g2_passed = False
        report = assemble_report(
            run_id="run_004",
            subject_ref="patient_004",
            ranked_schedules=rs,
        )
        assert any("Marginal" in w for w in report.run_warnings)

    def test_research_mode(self):
        report = assemble_report(
            run_id="run_005",
            subject_ref="patient_005",
            ranked_schedules=_make_ranked_schedules(1),
            output_mode=ReportOutputMode.RESEARCH,
        )
        assert report.output_mode == ReportOutputMode.RESEARCH
