# VERIFIED: spec SYS_PRES lines 132-145 (PRES-PAT3) + 171-180 (PRES-PAT6)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-PAT3 / PRES-PAT6
Spec: SYS_PRESENTATION_COMPLETE.md lines 132-145, 171-180
Purpose: Render temporal trajectory visualization — line chart with
         confidence bands, MID threshold, recovery markers.
         Also supports progress tracking across sessions (PAT6).
Reads: RecommendationReport.trajectories, TemporalTrajectory
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    RecommendationReport,
    TemporalTrajectory,
    NodeTrajectory,
    TrajectoryPoint,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TrajectoryLine:
    """One line in the trajectory chart."""

    label: str
    scenario_id: str
    color: str
    timepoints_days: list[int]
    means: list[float]
    lower_band: list[float]  # 95% CrI lower
    upper_band: list[float]  # 95% CrI upper
    is_baseline: bool = False


@dataclass(frozen=True)
class MIDCrossing:
    """MID threshold crossing annotation."""

    scenario_id: str
    crossing_day: int | None  # None if never crosses
    crossing_text: str


@dataclass(frozen=True)
class TrajectoryPlotView:
    """PRES-PAT3: Everything needed to render trajectory chart."""

    lines: list[TrajectoryLine]
    mid_threshold: float  # 0.5 SD default
    horizon_days: int
    x_label: str
    y_label: str
    mid_crossings: list[MIDCrossing] = field(default_factory=list)
    empty_state: bool = False
    empty_message: str = ""


@dataclass(frozen=True)
class ProgressEntry:
    """PAT6: One session in the progress timeline."""

    session_date: str
    composite_z: float
    severity_tier: str


@dataclass(frozen=True)
class ProgressTrackerView:
    """PRES-PAT6: Longitudinal progress across sessions."""

    entries: list[ProgressEntry]
    current_z: float
    trend_text: str
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════


_SCENARIO_COLORS: dict[str, str] = {
    "status_quo": "gray",
    "candidate": "blue",
}

MID_THRESHOLD_SD = 0.5  # Minimally Important Difference


# ═══════════════════════════════════════════════════════════════
#  Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _find_mid_crossing(
    points: list[TrajectoryPoint],
    baseline_z: float,
    mid_threshold: float,
) -> int | None:
    """Find the first day where improvement exceeds MID threshold."""
    for pt in points:
        if abs(pt.z_mean - baseline_z) >= mid_threshold:
            return pt.day
    return None


def _render_trajectory_line(
    traj: TemporalTrajectory,
    node_id: str | None = None,
) -> TrajectoryLine | None:
    """Render one trajectory scenario to a line."""
    # Pick the first node trajectory or a specific one
    nt: NodeTrajectory | None = None
    if node_id is not None:
        for n in traj.node_trajectories:
            if n.node_id == node_id:
                nt = n
                break
    elif traj.node_trajectories:
        nt = traj.node_trajectories[0]

    if nt is None or not nt.points:
        return None

    color = _SCENARIO_COLORS.get(traj.scenario_id, "blue")

    return TrajectoryLine(
        label=traj.scenario_label,
        scenario_id=traj.scenario_id,
        color=color,
        timepoints_days=[p.day for p in nt.points],
        means=[p.z_mean for p in nt.points],
        lower_band=[p.z_p10 for p in nt.points],
        upper_band=[p.z_p90 for p in nt.points],
        is_baseline=(traj.scenario_id == "status_quo"),
    )


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_trajectory_plot(
    report: RecommendationReport,
    node_id: str | None = None,
) -> TrajectoryPlotView:
    """PRES-PAT3: Render trajectory visualization.

    Shows predicted cognitive trajectory with and without intervention.

    Args:
        report: RecommendationReport containing trajectories.
        node_id: Specific node to visualize (default: first available).

    Returns:
        TrajectoryPlotView ready for rendering.
    """
    if not report.trajectories:
        return TrajectoryPlotView(
            lines=[],
            mid_threshold=MID_THRESHOLD_SD,
            horizon_days=0,
            x_label="Time (days)",
            y_label="Cognitive z-score",
            empty_state=True,
            empty_message="No trajectory data available for this session.",
        )

    lines: list[TrajectoryLine] = []
    crossings: list[MIDCrossing] = []
    horizon = 0

    for traj in report.trajectories:
        line = _render_trajectory_line(traj, node_id)
        if line is not None:
            lines.append(line)
            horizon = max(horizon, traj.horizon_days)

            # MID crossing detection
            baseline_z = line.means[0] if line.means else 0.0
            cross_day = _find_mid_crossing(
                traj.node_trajectories[0].points if traj.node_trajectories else [],
                baseline_z,
                MID_THRESHOLD_SD,
            )
            cross_text = (
                f"MID reached at day {cross_day}"
                if cross_day is not None
                else "MID not reached within horizon"
            )
            crossings.append(MIDCrossing(
                scenario_id=traj.scenario_id,
                crossing_day=cross_day,
                crossing_text=cross_text,
            ))

    return TrajectoryPlotView(
        lines=lines,
        mid_threshold=MID_THRESHOLD_SD,
        horizon_days=horizon,
        x_label="Time (days)",
        y_label="Cognitive z-score",
        mid_crossings=crossings,
    )


def render_progress_tracker(
    historical_scores: list[tuple[str, float, str]],
    current_z: float,
) -> ProgressTrackerView:
    """PRES-PAT6: Render longitudinal progress tracker.

    Args:
        historical_scores: List of (date_str, composite_z, severity_tier) tuples.
        current_z: Current session's composite z-score.

    Returns:
        ProgressTrackerView ready for rendering.
    """
    if not historical_scores:
        return ProgressTrackerView(
            entries=[],
            current_z=current_z,
            trend_text="No previous sessions to compare.",
            empty_state=True,
            empty_message="This is the first session for this patient.",
        )

    entries = [
        ProgressEntry(
            session_date=date,
            composite_z=z,
            severity_tier=sev,
        )
        for date, z, sev in historical_scores
    ]

    # Simple trend: compare current to first historical
    first_z = historical_scores[0][1]
    delta = current_z - first_z
    if delta > 0.1:
        trend = f"Overall improvement of {delta:.2f} SD since first session"
    elif delta < -0.1:
        trend = f"Overall change of {delta:.2f} SD since first session"
    else:
        trend = "Scores have remained stable across sessions"

    return ProgressTrackerView(
        entries=entries,
        current_z=current_z,
        trend_text=trend,
    )
