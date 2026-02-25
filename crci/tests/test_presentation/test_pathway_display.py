"""Tests for S4: PRES-PAT5 Pathway Display.

Covers:
    - Color assignment for known z-scores
    - Direction field correctness (+/-)
    - Dysregulation count accuracy
    - Empty state when pathway_profile is None
    - Tooltip content
"""
from __future__ import annotations

import pytest

from crci.shared import config
from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass
from crci.shared.models.output_contracts import (
    CompositeScore,
    PathwayContribution,
    PathwayProfile,
    RecommendationReport,
    SchedulePlan,
)
from crci.presentation.pathway_display import (
    PathwayDisplayView,
    PathwayHeatmapRow,
    render_pathway_display,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_report(pathway_profile: PathwayProfile | None = None) -> RecommendationReport:
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
        output_mode=ReportOutputMode.CLINICAL,
        composite_score=cs,
        primary_schedule=primary,
        pathway_profile=pathway_profile,
    )


def _make_profile(
    z_scores: list[float] | None = None,
) -> PathwayProfile:
    """Build profile with 3 pathways at given z-scores."""
    if z_scores is None:
        z_scores = [0.2, -1.0, 2.0]  # normal, yellow, red

    labels = ["Inflammation", "HPA Axis", "Oxidative Stress"]
    contribs = []
    for i, z in enumerate(z_scores):
        abs_z = abs(z)
        if abs_z >= config.PATHWAY_DYSREGULATION_THRESHOLD:
            quality = "strong_signal"
        elif abs_z >= config.PATHWAY_MILD_THRESHOLD:
            quality = "moderate_signal"
        else:
            quality = "normal_range"

        contribs.append(PathwayContribution(
            pathway_id=f"pw_{i}",
            pathway_label=labels[i],
            contribution_fraction=0.3,
            activation_z=z,
            key_edges=[f"e{i}"],
            evidence_quality=quality,
        ))

    return PathwayProfile(
        run_id="run_001",
        subject_ref="patient_001",
        pathway_contributions=contribs,
        dominant_pathway_id="pw_2",
        coverage_fraction=0.9,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestPathwayDisplay:

    def test_color_green(self):
        """z = 0.2 → green (|z| < 0.5)."""
        profile = _make_profile([0.2, 0.0, 0.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.rows[0].color == "green"

    def test_color_yellow(self):
        """z = -1.0 → yellow (0.5 ≤ |z| < 1.5)."""
        profile = _make_profile([0.0, -1.0, 0.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.rows[1].color == "yellow"

    def test_color_red(self):
        """z = 2.0 → red (|z| ≥ 1.5)."""
        profile = _make_profile([0.0, 0.0, 2.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.rows[2].color == "red"

    def test_direction_positive(self):
        """Positive z → direction '+'."""
        profile = _make_profile([1.0, 0.0, 0.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.rows[0].direction == "+"

    def test_direction_negative(self):
        """Negative z → direction '-'."""
        profile = _make_profile([0.0, -1.0, 0.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.rows[1].direction == "-"

    def test_dysregulation_count(self):
        """Count of dysregulated pathways should match rows with |z| ≥ threshold."""
        profile = _make_profile([0.2, -1.0, 2.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        # Only z=2.0 exceeds 1.5 threshold
        assert view.n_dysregulated == 1

    def test_empty_state_no_profile(self):
        """Empty state when pathway_profile is None."""
        report = _make_report(None)
        view = render_pathway_display(report)
        assert view.empty_state
        assert view.n_total == 0
        assert len(view.rows) == 0

    def test_empty_state_empty_contributions(self):
        """Empty state when pathway_profile has no contributions."""
        profile = PathwayProfile(
            run_id="run_001",
            subject_ref="patient_001",
            pathway_contributions=[],
        )
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.empty_state

    def test_total_count(self):
        """n_total should match number of pathways."""
        profile = _make_profile([0.2, -1.0, 2.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert view.n_total == 3

    def test_tooltip_contains_direction(self):
        """Tooltip should mention direction (elevated/reduced)."""
        profile = _make_profile([0.0, -1.0, 0.0])
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert "reduced" in view.rows[1].tooltip.lower()

    def test_reference_population(self):
        """Reference population should be stated."""
        profile = _make_profile()
        report = _make_report(profile)
        view = render_pathway_display(report)
        assert "CRCI" in view.reference_population
