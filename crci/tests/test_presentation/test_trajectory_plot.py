"""Tests for PRES-PAT3/PAT6: Trajectory Visualization & Progress Tracker.

Covers:
    - Trajectory line rendering
    - MID crossing detection
    - Empty state handling
    - Progress tracker with historical data
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier
from crci.shared.models.output_contracts import (
    CompositeScore,
    NodeTrajectory,
    RecommendationReport,
    SchedulePlan,
    TemporalTrajectory,
    TrajectoryPoint,
)

from crci.presentation.trajectory_plot import (
    MIDCrossing,
    ProgressTrackerView,
    TrajectoryLine,
    TrajectoryPlotView,
    render_progress_tracker,
    render_trajectory_plot,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_points(start_z: float = -1.0, end_z: float = -0.3) -> list[TrajectoryPoint]:
    """Create trajectory points linearly interpolating from start to end."""
    days = [0, 90, 180, 360, 540, 720]
    n = len(days)
    return [
        TrajectoryPoint(
            day=d,
            z_mean=start_z + (end_z - start_z) * i / (n - 1),
            z_sd=0.2,
            z_p10=start_z + (end_z - start_z) * i / (n - 1) - 0.4,
            z_p90=start_z + (end_z - start_z) * i / (n - 1) + 0.4,
        )
        for i, d in enumerate(days)
    ]


def _make_trajectory(
    scenario_id: str = "candidate",
    label: str = "With exercise",
    start_z: float = -1.0,
    end_z: float = -0.3,
) -> TemporalTrajectory:
    return TemporalTrajectory(
        scenario_id=scenario_id,
        scenario_label=label,
        horizon_days=720,
        node_trajectories=[
            NodeTrajectory(
                node_id="cognition_composite",
                node_label="Composite Cognition",
                points=_make_points(start_z, end_z),
                final_delta_z=end_z - start_z,
            )
        ],
    )


def _make_report(trajectories: list[TemporalTrajectory] | None = None) -> RecommendationReport:
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
        trajectories=trajectories or [],
    )


# ═══════════════════════════════════════════════════════════════
#  Tests: Trajectory Plot
# ═══════════════════════════════════════════════════════════════


class TestTrajectoryPlot:

    def test_basic_rendering(self):
        report = _make_report([
            _make_trajectory("status_quo", "Natural Recovery", -1.0, -0.8),
            _make_trajectory("candidate", "With Exercise", -1.0, -0.3),
        ])
        view = render_trajectory_plot(report)
        assert isinstance(view, TrajectoryPlotView)
        assert len(view.lines) == 2
        assert view.horizon_days == 720
        assert view.mid_threshold == 0.5
        assert not view.empty_state

    def test_line_colors(self):
        report = _make_report([
            _make_trajectory("status_quo", "Natural", -1.0, -0.8),
            _make_trajectory("candidate", "Exercise", -1.0, -0.3),
        ])
        view = render_trajectory_plot(report)
        colors = {line.scenario_id: line.color for line in view.lines}
        assert colors["status_quo"] == "gray"
        assert colors["candidate"] == "blue"

    def test_baseline_flag(self):
        report = _make_report([
            _make_trajectory("status_quo", "Natural", -1.0, -0.8),
        ])
        view = render_trajectory_plot(report)
        assert view.lines[0].is_baseline

    def test_mid_crossing_detected(self):
        # Start at -1.0, end at -0.3 → delta = 0.7 > 0.5 MID
        report = _make_report([
            _make_trajectory("candidate", "Exercise", -1.0, -0.3),
        ])
        view = render_trajectory_plot(report)
        assert len(view.mid_crossings) == 1
        crossing = view.mid_crossings[0]
        assert crossing.crossing_day is not None
        assert "MID reached" in crossing.crossing_text

    def test_mid_not_crossed(self):
        # Start at -0.5, end at -0.4 → delta = 0.1 < 0.5 MID
        report = _make_report([
            _make_trajectory("candidate", "Exercise", -0.5, -0.4),
        ])
        view = render_trajectory_plot(report)
        crossing = view.mid_crossings[0]
        assert crossing.crossing_day is None
        assert "not reached" in crossing.crossing_text

    def test_empty_trajectories(self):
        report = _make_report(trajectories=[])
        view = render_trajectory_plot(report)
        assert view.empty_state
        assert len(view.lines) == 0
        assert "available" in view.empty_message.lower()

    def test_timepoints_correct(self):
        report = _make_report([_make_trajectory()])
        view = render_trajectory_plot(report)
        line = view.lines[0]
        assert len(line.timepoints_days) == 6
        assert line.timepoints_days[0] == 0
        assert line.timepoints_days[-1] == 720

    def test_bands_present(self):
        report = _make_report([_make_trajectory()])
        view = render_trajectory_plot(report)
        line = view.lines[0]
        assert len(line.lower_band) == len(line.means)
        assert len(line.upper_band) == len(line.means)
        # Lower band should be below mean
        for lb, m in zip(line.lower_band, line.means):
            assert lb <= m


# ═══════════════════════════════════════════════════════════════
#  Tests: Progress Tracker
# ═══════════════════════════════════════════════════════════════


class TestProgressTracker:

    def test_basic_progress(self):
        history = [
            ("2024-01-15", -0.8, "Poor"),
            ("2024-04-15", -0.6, "Moderate"),
        ]
        view = render_progress_tracker(history, current_z=-0.4)
        assert isinstance(view, ProgressTrackerView)
        assert len(view.entries) == 2
        assert view.current_z == -0.4
        assert "improvement" in view.trend_text.lower()
        assert not view.empty_state

    def test_worsening_trend(self):
        history = [("2024-01-15", -0.3, "Good")]
        view = render_progress_tracker(history, current_z=-0.8)
        assert "change" in view.trend_text.lower()

    def test_stable_trend(self):
        history = [("2024-01-15", -0.5, "Moderate")]
        view = render_progress_tracker(history, current_z=-0.5)
        assert "stable" in view.trend_text.lower()

    def test_empty_history(self):
        view = render_progress_tracker([], current_z=-0.5)
        assert view.empty_state
        assert "first session" in view.empty_message.lower()
