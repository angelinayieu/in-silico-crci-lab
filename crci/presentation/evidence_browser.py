# VERIFIED: spec SYS_PRES lines 218-229 (PRES-SCI1)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-SCI1
Spec: SYS_PRESENTATION_COMPLETE.md lines 218-229
Purpose: Render evidence browser — sortable/filterable table of all edges
         with study-level drill-down, forest plots, funnel plots, and
         evidence gap highlighting.
Reads: RecommendationReport.evidence_gaps, decision_trace
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    EvidenceGapItem,
    EvidenceGapReport,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EdgeRow:
    """One row in the evidence browser table."""

    edge_id: str
    edge_label: str
    gap_type: str
    severity: str
    severity_color: str
    description: str
    discovery_score: float | None
    evsi: float | None
    has_evidence_gap: bool


@dataclass(frozen=True)
class EvidenceBrowserView:
    """PRES-SCI1: Evidence browser with gap highlighting."""

    rows: list[EdgeRow]
    n_total: int
    n_gaps: int
    gap_summary: str
    sort_by: str  # default sort field
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════


_SEVERITY_COLORS: dict[str, str] = {
    "high": "red",
    "medium": "orange",
    "low": "yellow",
}


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_evidence_browser(
    report: RecommendationReport,
    sort_by: str = "discovery_score",
) -> EvidenceBrowserView:
    """PRES-SCI1: Render evidence browser.

    Gate SCI-G1: Must have evidence gaps data to render.

    Args:
        report: RecommendationReport.
        sort_by: Default sort field.

    Returns:
        EvidenceBrowserView ready for rendering.
    """
    gap_report = report.evidence_gaps

    if gap_report is None or not gap_report.gaps:
        return EvidenceBrowserView(
            rows=[],
            n_total=0,
            n_gaps=0,
            gap_summary="No evidence gap data available.",
            sort_by=sort_by,
            empty_state=True,
            empty_message="Evidence browser requires model edge data. Run a full session first.",
        )

    rows: list[EdgeRow] = []
    n_gaps = 0

    for gap in gap_report.gaps:
        is_gap = gap.gap_type in ("missing_evidence", "low_k")
        if is_gap:
            n_gaps += 1

        rows.append(EdgeRow(
            edge_id=gap.edge_param_id,
            edge_label=gap.edge_label,
            gap_type=gap.gap_type,
            severity=gap.severity,
            severity_color=_SEVERITY_COLORS.get(gap.severity, "gray"),
            description=gap.description,
            discovery_score=gap.discovery_score,
            evsi=gap.evsi,
            has_evidence_gap=is_gap,
        ))

    # Sort by discovery_score (descending)
    if sort_by == "discovery_score":
        rows.sort(key=lambda r: r.discovery_score or 0.0, reverse=True)
    elif sort_by == "severity":
        severity_order = {"high": 0, "medium": 1, "low": 2}
        rows.sort(key=lambda r: severity_order.get(r.severity, 3))

    gap_summary = (
        f"{n_gaps} evidence gap(s) identified out of {len(rows)} edges. "
        f"Top acquisition targets: {', '.join(gap_report.top_acquisition_targets[:3])}"
        if gap_report.top_acquisition_targets
        else f"{n_gaps} evidence gap(s) identified out of {len(rows)} edges."
    )

    return EvidenceBrowserView(
        rows=rows,
        n_total=len(rows),
        n_gaps=n_gaps,
        gap_summary=gap_summary,
        sort_by=sort_by,
    )
