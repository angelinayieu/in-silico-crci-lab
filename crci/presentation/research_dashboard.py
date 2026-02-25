# VERIFIED: spec SYS_PRES lines 268-278 (PRES-SCI5)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-SCI5
Spec: SYS_PRESENTATION_COMPLETE.md lines 268-278
Purpose: Render research priority dashboard — sortable table of
         evidence gaps with EVSI and recommended study designs.
Reads: RecommendationReport.evidence_gaps (EvidenceGapReport)
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    EvidenceGapItem,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


_SEVERITY_COLORS: dict[str, str] = {
    "critical": "red",
    "high": "orange",
    "medium": "yellow",
    "low": "gray",
    "none": "green",
}

_GAP_CATEGORY: dict[str, str] = {
    "missing_evidence": "absence",
    "single_study": "absence",
    "low_k_no_rct": "weakness",
    "high_heterogeneity": "weakness",
    "weak_prior": "weakness",
    "adequate": "adequate",
}

_RECOMMENDED_ACTION: dict[str, str] = {
    "missing_evidence": "Commission new study (RCT preferred)",
    "single_study": "Seek replication study",
    "low_k_no_rct": "Search for RCT evidence",
    "high_heterogeneity": "Investigate heterogeneity sources; standardize protocols",
    "weak_prior": "Seek any empirical evidence",
    "adequate": "No immediate action needed",
}


@dataclass(frozen=True)
class GapMapRow:
    """One row in the research priority table."""

    edge_id: str
    edge_label: str
    gap_type: str
    gap_category: str  # "absence" or "weakness" or "adequate"
    severity: str
    severity_color: str
    discovery_score: float
    evsi: float | None
    recommended_action: str


@dataclass(frozen=True)
class ResearchDashboardView:
    """PRES-SCI5: Research priority dashboard."""

    gap_rows: list[GapMapRow]
    top_targets: list[str]
    total_gaps: int
    total_absence_gaps: int
    total_weakness_gaps: int
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_research_dashboard(
    report: RecommendationReport,
) -> ResearchDashboardView:
    """PRES-SCI5: Render research priority dashboard.

    Sortable table of evidence gaps ranked by discovery_score,
    with separate counts for evidence absence vs weakness.

    Args:
        report: RecommendationReport containing evidence_gaps.

    Returns:
        ResearchDashboardView ready for rendering.
    """
    if report.evidence_gaps is None or not report.evidence_gaps.gaps:
        return ResearchDashboardView(
            gap_rows=[],
            top_targets=[],
            total_gaps=0,
            total_absence_gaps=0,
            total_weakness_gaps=0,
            empty_state=True,
            empty_message="No evidence gap data available for this session.",
        )

    eg = report.evidence_gaps
    rows: list[GapMapRow] = []
    n_absence = 0
    n_weakness = 0

    for gap in eg.gaps:
        category = _GAP_CATEGORY.get(gap.gap_type, "adequate")
        if category == "absence":
            n_absence += 1
        elif category == "weakness":
            n_weakness += 1

        rows.append(GapMapRow(
            edge_id=gap.edge_param_id,
            edge_label=gap.edge_label,
            gap_type=gap.gap_type,
            gap_category=category,
            severity=gap.severity,
            severity_color=_SEVERITY_COLORS.get(gap.severity, "gray"),
            discovery_score=gap.discovery_score or 0.0,
            evsi=gap.evsi,
            recommended_action=_RECOMMENDED_ACTION.get(gap.gap_type, ""),
        ))

    # Count non-adequate gaps
    total_gaps = n_absence + n_weakness

    return ResearchDashboardView(
        gap_rows=rows,
        top_targets=eg.top_acquisition_targets,
        total_gaps=total_gaps,
        total_absence_gaps=n_absence,
        total_weakness_gaps=n_weakness,
    )
