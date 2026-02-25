# VERIFIED: spec SYS_PRES lines 161-169 (PRES-PAT5)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-PAT5
Spec: SYS_PRESENTATION_COMPLETE.md lines 161-169
Purpose: Render pathway activation heatmap with direction-aware
         color coding and plain-language tooltips.
Reads: RecommendationReport.pathway_profile (PathwayProfile)
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared import config
from crci.shared.models.output_contracts import (
    PathwayContribution,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PathwayHeatmapRow:
    """One row in the pathway activation heatmap."""

    pathway_id: str
    pathway_label: str
    activation_z: float
    dysregulation_flag: bool
    direction: str  # "+" (above prior) or "-" (below prior)
    color: str  # "green", "yellow", "red"
    tooltip: str


@dataclass(frozen=True)
class PathwayDisplayView:
    """PRES-PAT5: Everything needed to render pathway heatmap."""

    rows: list[PathwayHeatmapRow]
    dominant_pathway: str | None
    n_dysregulated: int
    n_total: int
    reference_population: str
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color / Tooltip Logic
# ═══════════════════════════════════════════════════════════════


def _classify_color(abs_z: float) -> str:
    """Map |z| to heatmap color.

    Thresholds relative to prior distribution (pre-intervention CRCI population):
    - |z| < PATHWAY_MILD_THRESHOLD → green (normal range)
    - PATHWAY_MILD_THRESHOLD ≤ |z| < PATHWAY_DYSREGULATION_THRESHOLD → yellow (mild)
    - |z| ≥ PATHWAY_DYSREGULATION_THRESHOLD → red (dysregulated)
    """
    if abs_z >= config.PATHWAY_DYSREGULATION_THRESHOLD:
        return "red"
    elif abs_z >= config.PATHWAY_MILD_THRESHOLD:
        return "yellow"
    return "green"


_PATHWAY_TOOLTIPS: dict[str, str] = {
    "green": (
        "This pathway is within the expected range for the CRCI population. "
        "No unusual activity detected."
    ),
    "yellow": (
        "This pathway shows mild deviation from the expected CRCI presentation. "
        "It may be contributing to cognitive symptoms but is not severely affected."
    ),
    "red": (
        "This pathway shows unusual activation even for someone with CRCI "
        "(top/bottom ~7%). It is likely a significant contributor to cognitive "
        "difficulties and may be a priority target for intervention."
    ),
}


def _build_tooltip(pathway_label: str, color: str, direction: str) -> str:
    """Build plain-language tooltip for a pathway row."""
    direction_text = "elevated" if direction == "+" else "reduced"
    base = _PATHWAY_TOOLTIPS.get(color, "")
    return f"{pathway_label}: Activity is {direction_text}. {base}"


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_pathway_display(
    report: RecommendationReport,
) -> PathwayDisplayView:
    """PRES-PAT5: Render pathway activation heatmap.

    Heatmap of 20 pathways with direction-aware color coding.
    Green = normal, Yellow = mild, Red = dysregulated.
    Reference population: pre-intervention CRCI population (prior distribution).

    Args:
        report: RecommendationReport containing pathway_profile.

    Returns:
        PathwayDisplayView ready for rendering.
    """
    if report.pathway_profile is None or not report.pathway_profile.pathway_contributions:
        return PathwayDisplayView(
            rows=[],
            dominant_pathway=None,
            n_dysregulated=0,
            n_total=0,
            reference_population="CRCI population (prior distribution)",
            empty_state=True,
            empty_message="No pathway activation data available for this session.",
        )

    profile = report.pathway_profile
    rows: list[PathwayHeatmapRow] = []
    n_dysregulated = 0

    for contrib in profile.pathway_contributions:
        activation_z = contrib.activation_z
        abs_z = abs(activation_z)
        direction = "+" if activation_z >= 0 else "-"
        color = _classify_color(abs_z)
        dysregulated = abs_z >= config.PATHWAY_DYSREGULATION_THRESHOLD
        if dysregulated:
            n_dysregulated += 1

        tooltip = _build_tooltip(contrib.pathway_label, color, direction)

        rows.append(PathwayHeatmapRow(
            pathway_id=contrib.pathway_id,
            pathway_label=contrib.pathway_label,
            activation_z=activation_z,
            dysregulation_flag=dysregulated,
            direction=direction,
            color=color,
            tooltip=tooltip,
        ))

    dominant = profile.dominant_pathway_id
    dominant_label = None
    if dominant:
        for r in rows:
            if r.pathway_id == dominant:
                dominant_label = r.pathway_label
                break

    return PathwayDisplayView(
        rows=rows,
        dominant_pathway=dominant_label,
        n_dysregulated=n_dysregulated,
        n_total=len(rows),
        reference_population="Relative to typical CRCI presentation",
    )
