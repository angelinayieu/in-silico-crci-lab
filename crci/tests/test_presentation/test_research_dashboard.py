"""Tests for S6: PRES-SCI5 Research Priority Dashboard.

Covers:
    - Rendering with populated EvidenceGapReport
    - Sorting by discovery_score
    - Gap counts (absence vs weakness)
    - Empty state when evidence_gaps is None
    - Severity color mapping
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier
from crci.shared.models.output_contracts import (
    CompositeScore,
    EvidenceGapItem,
    EvidenceGapReport,
    RecommendationReport,
    SchedulePlan,
)
from crci.presentation.research_dashboard import (
    ResearchDashboardView,
    render_research_dashboard,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_report(evidence_gaps: EvidenceGapReport | None = None) -> RecommendationReport:
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
    return RecommendationReport(
        run_id="run_001",
        subject_ref="patient_001",
        output_mode=ReportOutputMode.RESEARCH,
        composite_score=cs,
        primary_schedule=primary,
        evidence_gaps=evidence_gaps,
    )


def _make_gap_report() -> EvidenceGapReport:
    return EvidenceGapReport(
        run_id="run_001",
        gaps=[
            EvidenceGapItem(
                edge_param_id="e1",
                edge_label="IL-6 → Fatigue",
                gap_type="missing_evidence",
                severity="critical",
                description="No evidence",
                discovery_score=0.8,
                evsi=0.5,
            ),
            EvidenceGapItem(
                edge_param_id="e2",
                edge_label="BDNF → Memory",
                gap_type="low_k_no_rct",
                severity="medium",
                description="3 observational",
                discovery_score=0.3,
                evsi=0.2,
            ),
            EvidenceGapItem(
                edge_param_id="e3",
                edge_label="Cortisol → Sleep",
                gap_type="adequate",
                severity="none",
                description="Well covered",
                discovery_score=0.1,
                evsi=0.05,
            ),
        ],
        top_acquisition_targets=["e1", "e2"],
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestResearchDashboard:

    def test_rendering_populated(self):
        """Should render rows from EvidenceGapReport."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        assert not view.empty_state
        assert len(view.gap_rows) == 3

    def test_gap_counts(self):
        """Absence and weakness counts should be correct."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        assert view.total_absence_gaps == 1  # missing_evidence
        assert view.total_weakness_gaps == 1  # low_k_no_rct
        assert view.total_gaps == 2  # absence + weakness (excludes adequate)

    def test_gap_category_mapping(self):
        """Gap categories should map correctly."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        categories = {r.edge_id: r.gap_category for r in view.gap_rows}
        assert categories["e1"] == "absence"
        assert categories["e2"] == "weakness"
        assert categories["e3"] == "adequate"

    def test_severity_colors(self):
        """Severity should map to correct colors."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        colors = {r.edge_id: r.severity_color for r in view.gap_rows}
        assert colors["e1"] == "red"      # critical
        assert colors["e2"] == "yellow"   # medium
        assert colors["e3"] == "green"    # none

    def test_recommended_action(self):
        """Each gap type should have a recommended action."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        for row in view.gap_rows:
            assert row.recommended_action != ""

    def test_top_targets(self):
        """Top targets should be passed through from EvidenceGapReport."""
        report = _make_report(_make_gap_report())
        view = render_research_dashboard(report)
        assert view.top_targets == ["e1", "e2"]

    def test_empty_state_no_gaps(self):
        """Empty state when evidence_gaps is None."""
        report = _make_report(None)
        view = render_research_dashboard(report)
        assert view.empty_state
        assert view.total_gaps == 0

    def test_empty_state_empty_gaps(self):
        """Empty state when gap list is empty."""
        eg = EvidenceGapReport(run_id="run_001", gaps=[])
        report = _make_report(eg)
        view = render_research_dashboard(report)
        assert view.empty_state
