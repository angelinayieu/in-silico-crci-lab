# VERIFIED: spec SYS_PRES lines 103-116 (PRES-PAT1)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-PAT1
Spec: SYS_PRESENTATION_COMPLETE.md lines 103-116
Purpose: Render CRCI composite score dashboard — gauge/dial, severity tier,
         percentile, 11-domain bar chart, delta from previous session.
Reads: RecommendationReport.composite_score
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import CompositeScore, DomainScore, RecommendationReport

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models (presentation-ready data structures)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DomainBar:
    """One bar in the subdomain breakdown chart."""

    domain_id: str
    domain_label: str
    z_score: float
    color: str  # green, light_green, yellow, orange, red_orange, red


@dataclass(frozen=True)
class ScoreDashboardView:
    """PRES-PAT1: Everything needed to render the CRCI score dashboard."""

    composite_z: float
    severity_tier: str
    severity_color: str
    percentile: float | None
    percentile_text: str
    domain_bars: list[DomainBar]
    delta_from_previous: float | None = None
    delta_text: str | None = None
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════

_SEVERITY_COLORS: dict[str, str] = {
    "Excellent": "green",
    "Good": "light_green",
    "Mild Concern": "yellow",
    "Moderate": "orange",
    "Poor": "red_orange",
    "Severe": "red",
}


def _domain_color(z: float) -> str:
    """Map z-score to bar color."""
    abs_z = abs(z)
    if abs_z < 0.5:
        return "green"
    elif abs_z < 1.0:
        return "yellow"
    elif abs_z < 1.5:
        return "orange"
    else:
        return "red"


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_score_dashboard(
    report: RecommendationReport,
    previous_composite_z: float | None = None,
) -> ScoreDashboardView:
    """PRES-PAT1: Render CRCI score dashboard.

    Gate PAT-G1: RecommendationReport exists → render; else → empty state.

    Args:
        report: Current session's RecommendationReport.
        previous_composite_z: Previous session's composite z-score (if available).

    Returns:
        ScoreDashboardView ready for UI rendering.
    """
    cs = report.composite_score

    # Domain bars
    bars = [
        DomainBar(
            domain_id=d.domain_id,
            domain_label=d.domain_label,
            z_score=d.z_score,
            color=_domain_color(d.z_score),
        )
        for d in cs.domain_scores
    ]

    # Percentile text
    pct = cs.composite_percentile
    pct_text = f"Your score is in the {pct:.0f}th percentile" if pct is not None else "Percentile not available"

    # Delta from previous
    delta = None
    delta_text = None
    if previous_composite_z is not None:
        delta = cs.composite_z - previous_composite_z
        if delta > 0.1:
            delta_text = f"Improved by {delta:.2f} SD since last session"
        elif delta < -0.1:
            delta_text = f"Changed by {delta:.2f} SD since last session"
        else:
            delta_text = "Score stable since last session"

    severity_str = cs.overall_severity.value
    color = _SEVERITY_COLORS.get(severity_str, "gray")

    return ScoreDashboardView(
        composite_z=cs.composite_z,
        severity_tier=severity_str,
        severity_color=color,
        percentile=pct,
        percentile_text=pct_text,
        domain_bars=bars,
        delta_from_previous=delta,
        delta_text=delta_text,
    )
