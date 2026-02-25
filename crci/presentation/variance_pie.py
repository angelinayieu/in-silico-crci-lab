# VERIFIED: spec SYS_PRES lines 147-159 (PRES-PAT4)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-PAT4
Spec: SYS_PRESENTATION_COMPLETE.md lines 147-159
Purpose: Render mandatory uncertainty disclosure panel — 5-source variance
         pie chart, confidence statement, actionable message, and
         HIGHLY_UNSTABLE warning banner.
Reads: RecommendationReport.variance_decomposition, decision_trace
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    RecommendationReport,
    VarianceDecomposition,
    VarianceComponent,
    DecisionTrace,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PieSlice:
    """One slice in the variance pie chart."""

    source: str
    label: str
    fraction: float
    color: str
    description: str


@dataclass(frozen=True)
class UncertaintyPanelView:
    """PRES-PAT4: Mandatory uncertainty disclosure panel.

    CRITICAL: Cannot be suppressed (spec line 150).
    """

    confidence_statement: str
    pie_slices: list[PieSlice]
    actionable_message: str
    warning_banner: str | None  # Non-None for HIGHLY_UNSTABLE
    stability_class: str
    p_rank_1: float
    dominant_source: str | None
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color & Label Mapping
# ═══════════════════════════════════════════════════════════════


_SOURCE_COLORS: dict[str, str] = {
    "literature": "#4C78A8",
    "measurement": "#F58518",
    "structural": "#E45756",
    "proxy": "#72B7B2",
    "missing": "#54A24B",
}

_SOURCE_LABELS: dict[str, str] = {
    "literature": "Published evidence variability",
    "measurement": "Measurement noise",
    "structural": "Model structure uncertainty",
    "proxy": "Proxy approximation error",
    "missing": "Missing data impact",
}

_SOURCE_DESCRIPTIONS: dict[str, str] = {
    "literature": "Variation across published studies that inform this recommendation.",
    "measurement": "Imprecision in cognitive tests and questionnaires used.",
    "structural": "Uncertainty about how different factors connect to each other.",
    "proxy": "Using approximate measures when direct ones aren't available.",
    "missing": "Information we don't yet have about your situation.",
}

_CONFIDENCE_LABELS: dict[str, str] = {
    "STABLE": "confident",
    "SOFT": "moderately confident",
    "UNSTABLE": "less confident",
}


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_uncertainty_panel(
    report: RecommendationReport,
) -> UncertaintyPanelView:
    """PRES-PAT4: Render mandatory uncertainty disclosure panel.

    Gate PAT-G2: Uncertainty disclosure MUST be present.
    CANNOT be suppressed (spec line 150).

    Args:
        report: RecommendationReport.

    Returns:
        UncertaintyPanelView ready for rendering.
    """
    vd = report.variance_decomposition
    trace = report.decision_trace

    # Extract stability info from decision trace
    stability_class = "SOFT"
    p_rank_1 = 0.0
    if trace is not None:
        for entry in trace.entries:
            if entry.step == "stability_assessment":
                # Parse from outcome text: "P(rank1)=0.750"
                if "P(rank1)=" in entry.outcome:
                    try:
                        p_rank_1 = float(entry.outcome.split("P(rank1)=")[1])
                    except (ValueError, IndexError):
                        pass
                # Parse stability class from description
                # Check longest match first to avoid "STABLE" matching "UNSTABLE"
                for cls in ("UNSTABLE", "STABLE", "SOFT"):
                    if cls in entry.description:
                        stability_class = cls
                        break

    # Also check safety_flags for HIGHLY_UNSTABLE
    is_highly_unstable = "HIGHLY_UNSTABLE_WARNING" in report.safety_flags

    # Confidence statement (grade 8 reading level)
    confidence_word = _CONFIDENCE_LABELS.get(stability_class, "moderately confident")
    confidence_statement = (
        f"We are {confidence_word} in this recommendation. "
        f"There is a {p_rank_1 * 100:.0f}% chance that the top-ranked option is truly the best."
    )

    # Pie slices
    pie_slices: list[PieSlice] = []
    dominant_source: str | None = None
    if vd is not None and vd.components:
        dominant_source = vd.dominant_source
        for comp in vd.components:
            pie_slices.append(PieSlice(
                source=comp.source,
                label=_SOURCE_LABELS.get(comp.source, comp.source),
                fraction=comp.fraction,
                color=_SOURCE_COLORS.get(comp.source, "#999999"),
                description=_SOURCE_DESCRIPTIONS.get(comp.source, ""),
            ))

    # Actionable message
    if dominant_source is not None:
        source_label = _SOURCE_LABELS.get(dominant_source, dominant_source)
        actionable = (
            f"The largest source of uncertainty is \"{source_label.lower()}\". "
            f"Collecting additional data in this area could meaningfully improve "
            f"the precision of your recommendation."
        )
    else:
        actionable = (
            "Uncertainty information is not available for this session. "
            "Additional assessments may help improve recommendation confidence."
        )

    # Warning banner for HIGHLY_UNSTABLE
    warning = None
    if is_highly_unstable:
        warning = (
            "Important: This recommendation has high uncertainty. "
            "Rankings may change significantly with additional information. "
            "Please discuss all options carefully with your healthcare provider."
        )

    return UncertaintyPanelView(
        confidence_statement=confidence_statement,
        pie_slices=pie_slices,
        actionable_message=actionable,
        warning_banner=warning,
        stability_class=stability_class,
        p_rank_1=p_rank_1,
        dominant_source=dominant_source,
    )
