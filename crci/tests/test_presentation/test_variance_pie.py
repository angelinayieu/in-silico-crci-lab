"""Tests for PRES-PAT4: Uncertainty Disclosure Panel.

Covers:
    - Confidence statement generation
    - Pie slice rendering
    - Actionable message with dominant source
    - HIGHLY_UNSTABLE warning banner
    - Empty/missing data handling
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass
from crci.shared.models.output_contracts import (
    CompositeScore,
    DecisionTrace,
    DecisionTraceEntry,
    RecommendationReport,
    SchedulePlan,
    VarianceComponent,
    VarianceDecomposition,
)

from crci.presentation.variance_pie import (
    PieSlice,
    UncertaintyPanelView,
    render_uncertainty_panel,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_variance() -> VarianceDecomposition:
    return VarianceDecomposition(
        run_id="run_001",
        components=[
            VarianceComponent(source="literature", fraction=0.30),
            VarianceComponent(source="measurement", fraction=0.15),
            VarianceComponent(source="structural", fraction=0.20),
            VarianceComponent(source="proxy", fraction=0.15),
            VarianceComponent(source="missing", fraction=0.20),
        ],
        total_variance=1.0,
        dominant_source="literature",
    )


def _make_trace(stability: str = "SOFT", p_rank_1: float = 0.65) -> DecisionTrace:
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
                description=f"Decision stability: {stability}",
                outcome=f"P(rank1)={p_rank_1:.3f}",
                confidence=p_rank_1,
            ),
            DecisionTraceEntry(
                step="recommendation",
                description="Recommend: Exercise",
                inputs={"claim_level": "causal_supported"},
                outcome="intervention_id=ex_1",
            ),
        ],
        decision_critical_edges=["e1"],
    )


def _make_report(
    variance: VarianceDecomposition | None = None,
    trace: DecisionTrace | None = None,
    safety_flags: list[str] | None = None,
) -> RecommendationReport:
    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=-0.5,
        overall_severity=SeverityTier.MODERATE,
    )
    primary = SchedulePlan(
        schedule_id="sched_001",
        run_id="run_001",
        plan_rank=1,
        plan_type="primary",
    )
    return RecommendationReport(
        run_id="run_001",
        subject_ref="patient_001",
        output_mode=ReportOutputMode.CLINICAL,
        composite_score=cs,
        primary_schedule=primary,
        variance_decomposition=variance,
        decision_trace=trace,
        safety_flags=safety_flags or [],
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestUncertaintyPanel:

    def test_basic_rendering(self):
        report = _make_report(
            variance=_make_variance(),
            trace=_make_trace("SOFT", 0.65),
        )
        view = render_uncertainty_panel(report)
        assert isinstance(view, UncertaintyPanelView)
        assert "moderately confident" in view.confidence_statement
        assert "65%" in view.confidence_statement
        assert len(view.pie_slices) == 5
        assert view.dominant_source == "literature"
        assert view.warning_banner is None
        assert not view.empty_state

    def test_pie_slice_colors(self):
        report = _make_report(variance=_make_variance(), trace=_make_trace())
        view = render_uncertainty_panel(report)
        source_colors = {s.source: s.color for s in view.pie_slices}
        assert source_colors["literature"] == "#4C78A8"
        assert source_colors["measurement"] == "#F58518"

    def test_pie_slice_fractions(self):
        report = _make_report(variance=_make_variance(), trace=_make_trace())
        view = render_uncertainty_panel(report)
        total = sum(s.fraction for s in view.pie_slices)
        assert total == pytest.approx(1.0, abs=1e-10)

    def test_stable_confidence(self):
        report = _make_report(
            variance=_make_variance(),
            trace=_make_trace("STABLE", 0.90),
        )
        view = render_uncertainty_panel(report)
        assert "confident" in view.confidence_statement
        assert "90%" in view.confidence_statement

    def test_unstable_confidence(self):
        report = _make_report(
            variance=_make_variance(),
            trace=_make_trace("UNSTABLE", 0.40),
        )
        view = render_uncertainty_panel(report)
        assert "less confident" in view.confidence_statement

    def test_highly_unstable_warning(self):
        report = _make_report(
            variance=_make_variance(),
            trace=_make_trace("UNSTABLE", 0.30),
            safety_flags=["HIGHLY_UNSTABLE_WARNING"],
        )
        view = render_uncertainty_panel(report)
        assert view.warning_banner is not None
        assert "high uncertainty" in view.warning_banner.lower()

    def test_no_variance(self):
        report = _make_report(variance=None, trace=_make_trace())
        view = render_uncertainty_panel(report)
        assert len(view.pie_slices) == 0
        assert view.dominant_source is None
        assert "not available" in view.actionable_message.lower()

    def test_no_trace(self):
        report = _make_report(variance=_make_variance(), trace=None)
        view = render_uncertainty_panel(report)
        # Should default to SOFT
        assert view.stability_class == "SOFT"
        assert view.p_rank_1 == 0.0

    def test_actionable_message_with_dominant(self):
        report = _make_report(variance=_make_variance(), trace=_make_trace())
        view = render_uncertainty_panel(report)
        assert "published evidence" in view.actionable_message.lower()
        assert "improve" in view.actionable_message.lower()
