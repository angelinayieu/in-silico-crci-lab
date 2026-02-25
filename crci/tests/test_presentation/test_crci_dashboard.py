"""Tests for PRES-PAT1: CRCI Score Dashboard.

Covers:
    - Domain bar rendering
    - Severity color mapping
    - Percentile text generation
    - Delta from previous session
    - Empty state handling
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass
from crci.shared.models.output_contracts import (
    CompositeScore,
    DomainScore,
    RecommendationReport,
    SchedulePlan,
)

from crci.presentation.crci_dashboard import (
    DomainBar,
    ScoreDashboardView,
    _domain_color,
    render_score_dashboard,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_domain_score(domain: str, z: float) -> DomainScore:
    return DomainScore(
        domain_id=domain,
        domain_label=domain.replace("_", " ").title(),
        z_score=z,
        severity_tier=SeverityTier.MODERATE,
    )


def _make_report(
    composite_z: float = -0.5,
    severity: SeverityTier = SeverityTier.MILD_CONCERN,
    percentile: float | None = 30.0,
    domains: list[DomainScore] | None = None,
) -> RecommendationReport:
    if domains is None:
        domains = [
            _make_domain_score("processing_speed", -0.3),
            _make_domain_score("memory_verbal", -0.7),
        ]

    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=composite_z,
        composite_percentile=percentile,
        overall_severity=severity,
        domain_scores=domains,
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
    )


# ═══════════════════════════════════════════════════════════════
#  Tests: Domain Color
# ═══════════════════════════════════════════════════════════════


class TestDomainColor:

    def test_green_zone(self):
        assert _domain_color(0.0) == "green"
        assert _domain_color(0.4) == "green"
        assert _domain_color(-0.3) == "green"

    def test_yellow_zone(self):
        assert _domain_color(0.5) == "yellow"
        assert _domain_color(-0.8) == "yellow"

    def test_orange_zone(self):
        assert _domain_color(1.0) == "orange"
        assert _domain_color(-1.2) == "orange"

    def test_red_zone(self):
        assert _domain_color(1.5) == "red"
        assert _domain_color(-2.0) == "red"


# ═══════════════════════════════════════════════════════════════
#  Tests: Score Dashboard Rendering
# ═══════════════════════════════════════════════════════════════


class TestScoreDashboard:

    def test_basic_rendering(self):
        report = _make_report()
        view = render_score_dashboard(report)
        assert isinstance(view, ScoreDashboardView)
        assert view.composite_z == -0.5
        assert view.severity_tier == "Mild Concern"
        assert view.severity_color == "yellow"
        assert view.percentile == 30.0
        assert "30th percentile" in view.percentile_text
        assert len(view.domain_bars) == 2
        assert not view.empty_state

    def test_domain_bars_correct(self):
        report = _make_report()
        view = render_score_dashboard(report)
        bar_ids = [b.domain_id for b in view.domain_bars]
        assert "processing_speed" in bar_ids
        assert "memory_verbal" in bar_ids

    def test_severity_colors(self):
        for tier, expected_color in [
            (SeverityTier.EXCELLENT, "green"),
            (SeverityTier.GOOD, "light_green"),
            (SeverityTier.MILD_CONCERN, "yellow"),
            (SeverityTier.MODERATE, "orange"),
            (SeverityTier.POOR, "red_orange"),
            (SeverityTier.SEVERE, "red"),
        ]:
            report = _make_report(severity=tier)
            view = render_score_dashboard(report)
            assert view.severity_color == expected_color, f"Failed for {tier}"

    def test_no_percentile(self):
        report = _make_report(percentile=None)
        view = render_score_dashboard(report)
        assert view.percentile is None
        assert "not available" in view.percentile_text.lower()

    def test_delta_improved(self):
        report = _make_report(composite_z=-0.3)
        view = render_score_dashboard(report, previous_composite_z=-0.6)
        assert view.delta_from_previous is not None
        assert view.delta_from_previous == pytest.approx(0.3, abs=1e-10)
        assert "Improved" in view.delta_text

    def test_delta_worsened(self):
        report = _make_report(composite_z=-0.8)
        view = render_score_dashboard(report, previous_composite_z=-0.3)
        assert view.delta_from_previous is not None
        assert view.delta_from_previous < 0
        assert "Changed" in view.delta_text

    def test_delta_stable(self):
        report = _make_report(composite_z=-0.5)
        view = render_score_dashboard(report, previous_composite_z=-0.5)
        assert "stable" in view.delta_text.lower()

    def test_no_previous(self):
        report = _make_report()
        view = render_score_dashboard(report, previous_composite_z=None)
        assert view.delta_from_previous is None
        assert view.delta_text is None

    def test_no_domains(self):
        report = _make_report(domains=[])
        view = render_score_dashboard(report)
        assert len(view.domain_bars) == 0
