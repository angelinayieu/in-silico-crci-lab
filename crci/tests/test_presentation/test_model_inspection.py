"""Tests for S7: PRES-SCI4 Model Transparency Panel.

Covers:
    - Rendering with populated decision trace
    - Empty state when no trace data
    - Assumption impact levels are valid
    - Decision steps extracted from trace
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier
from crci.shared.models.output_contracts import (
    CompositeScore,
    DecisionTrace,
    DecisionTraceEntry,
    RecommendationReport,
    SchedulePlan,
)
from crci.presentation.model_inspection import (
    ModelInspectionView,
    PriorSelectionRow,
    SECalibrationRow,
    render_model_inspection,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_report(
    with_trace: bool = True,
) -> RecommendationReport:
    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=-0.5,
        overall_severity=SeverityTier.MODERATE,
    )
    primary = SchedulePlan(
        schedule_id="s1",
        run_id="run_001",
        plan_rank=1,
        plan_type="primary",
    )
    trace = None
    if with_trace:
        trace = DecisionTrace(
            run_id="run_001",
            entries=[
                DecisionTraceEntry(
                    step="stability_assessment",
                    description="Decision stability: STABLE",
                    outcome="P(rank1)=0.850",
                    confidence=0.85,
                ),
                DecisionTraceEntry(
                    step="recommendation",
                    description="Recommend: Exercise",
                    inputs={"claim_level": "causal_supported"},
                    outcome="intervention_id=exercise_001",
                ),
            ],
            decision_critical_edges=["edge_1", "edge_2"],
        )

    return RecommendationReport(
        run_id="run_001",
        subject_ref="patient_001",
        output_mode=ReportOutputMode.RESEARCH,
        composite_score=cs,
        primary_schedule=primary,
        decision_trace=trace,
        engine_version="CRCI-v0.8",
        timestamp="2025-01-15T10:30:00Z",
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestModelInspection:

    def test_rendering_with_trace(self):
        """Should render non-empty view when decision trace is present."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        assert not view.empty_state
        assert len(view.decision_steps) == 2

    def test_decision_steps_content(self):
        """Decision steps should contain trace entries."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        assert "stability_assessment" in view.decision_steps[0]
        assert "STABLE" in view.decision_steps[0]
        assert "Exercise" in view.decision_steps[1]

    def test_empty_state_no_trace(self):
        """Empty state when no trace and no prior log."""
        report = _make_report(with_trace=False)
        view = render_model_inspection(report)
        assert view.empty_state

    def test_assumptions_present(self):
        """Default assumptions should always be populated."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        assert len(view.assumptions) >= 3

    def test_assumption_impact_levels_valid(self):
        """All assumption impact levels should be HIGH, MEDIUM, or LOW."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        valid_impacts = {"HIGH", "MEDIUM", "LOW"}
        for a in view.assumptions:
            assert a.impact in valid_impacts, f"Invalid impact: {a.impact}"

    def test_model_metadata(self):
        """Model version and timestamp should be passed through."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        assert view.model_version == "CRCI-v0.8"
        assert view.deploy_timestamp == "2025-01-15T10:30:00Z"

    def test_prior_log_passthrough(self):
        """Prior log rows should be passed through when provided."""
        report = _make_report(with_trace=True)
        prior_rows = [
            PriorSelectionRow(
                edge_id="edge_1",
                prior_type="RobustMAP",
                rationale="k≥5 with 2 RCTs",
                k=7,
                has_rct=True,
            ),
        ]
        view = render_model_inspection(report, prior_log=prior_rows)
        assert len(view.prior_log) == 1
        assert view.prior_log[0].prior_type == "RobustMAP"

    def test_se_calibration_passthrough(self):
        """SE calibration rows should be passed through when provided."""
        report = _make_report(with_trace=True)
        se_rows = [
            SECalibrationRow(
                edge_id="edge_1",
                layers_applied=["design", "GRADE", "temporal"],
                final_se_eff=0.35,
                inflation_factor=1.75,
            ),
        ]
        view = render_model_inspection(report, se_calibration=se_rows)
        assert len(view.se_calibration) == 1
        assert view.se_calibration[0].inflation_factor == 1.75

    def test_node_edge_counts(self):
        """Default node and edge counts should match expected values."""
        report = _make_report(with_trace=True)
        view = render_model_inspection(report)
        assert view.n_nodes == 63
        assert view.n_edges == 118
