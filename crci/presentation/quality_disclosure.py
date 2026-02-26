# VERIFIED: read-only — no computation, no DB writes
# VERIFIED: backward wiring — reads ExtractionQualitySummary from output_contracts.py
# VERIFIED: forward wiring — writes QualityDisclosureView for renderer
"""
Component: SYS_PRESENTATION.PRES-QUAL
Spec: Remediation — extraction quality disclosure panel
Purpose: Render extraction quality disclosure — completeness score,
         layer default warnings, missing data caveats, and overall
         quality tier. Ensures users know what data was and wasn't
         available for their recommendation.

         CANNOT be suppressed in clinical mode (analogous to PAT4
         mandatory uncertainty disclosure).

Reads: RecommendationReport.extraction_quality (ExtractionQualitySummary)
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    ExtractionQualitySummary,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DefaultItem:
    """One layer's default-firing summary."""

    layer: str         # "L6"
    label: str         # "Temporal data"
    count: int         # Number of evidence rows defaulting
    caveat: str        # Human-readable explanation


@dataclass(frozen=True)
class QualityDisclosureView:
    """PRES-QUAL: Everything needed to render the extraction quality panel.

    Mandatory panel — analogous to PRES-PAT4 (uncertainty).
    """

    completeness_score: float          # 0.0–1.0 overall
    completeness_pct: int              # 0–100 for display
    study_count: int
    defaults_summary: list[DefaultItem]
    missing_data_warnings: list[str]
    quality_tier: str                  # "HIGH" / "MODERATE" / "LOW"
    tier_color: str                    # green / yellow / red
    overall_message: str               # Grade-8 reading level summary
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Tier Classification
# ═══════════════════════════════════════════════════════════════


def _classify_quality_tier(score: float) -> tuple[str, str]:
    """Classify completeness score into tier + color.

    Args:
        score: Completeness score 0.0–1.0.

    Returns:
        (tier_label, color).
    """
    if score >= 0.80:
        return "HIGH", "green"
    if score >= 0.50:
        return "MODERATE", "yellow"
    return "LOW", "red"


# ═══════════════════════════════════════════════════════════════
#  Layer Labels
# ═══════════════════════════════════════════════════════════════

_LAYER_LABELS: dict[str, str] = {
    "L1": "Study design",
    "L4": "Cancer validation",
    "L5": "Risk-of-bias / GRADE",
    "L6": "Temporal data",
    "L7": "Publication freshness",
}

_LAYER_CAVEATS: dict[str, str] = {
    "L1": "study design unknown — maximum SE multiplier applied",
    "L4": "cancer validation status unknown — defaulting to general population",
    "L5": "risk-of-bias/GRADE unknown — defaulting to MODERATE",
    "L6": "temporal data absent — no measurement-recency SE penalty applied",
    "L7": "publication year unknown — freshness decay not applied",
}


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_quality_disclosure(
    report: RecommendationReport,
) -> QualityDisclosureView:
    """PRES-QUAL: Render extraction quality disclosure panel.

    Mandatory panel — CANNOT be suppressed in clinical mode.

    Args:
        report: RecommendationReport containing extraction_quality field.

    Returns:
        QualityDisclosureView ready for rendering.
    """
    eq = report.extraction_quality

    if eq is None:
        return QualityDisclosureView(
            completeness_score=0.0,
            completeness_pct=0,
            study_count=0,
            defaults_summary=[],
            missing_data_warnings=[],
            quality_tier="UNKNOWN",
            tier_color="gray",
            overall_message=(
                "Extraction quality information is not available for this session."
            ),
            empty_state=True,
            empty_message=(
                "Quality disclosure requires extraction completeness analysis. "
                "Run the completeness checker after loading evidence."
            ),
        )

    tier, color = _classify_quality_tier(eq.overall_completeness)

    # Build defaults summary
    defaults: list[DefaultItem] = []
    for layer in ("L1", "L4", "L5", "L6", "L7"):
        count = eq.total_defaults_fired.get(layer, 0)
        if count > 0:
            defaults.append(DefaultItem(
                layer=layer,
                label=_LAYER_LABELS.get(layer, layer),
                count=count,
                caveat=_LAYER_CAVEATS.get(layer, f"{layer} data missing"),
            ))

    # Quality caveats become missing_data_warnings
    warnings = list(eq.quality_caveats)

    # Build overall message (grade-8 reading level)
    if tier == "HIGH":
        overall = (
            f"Good data quality: {eq.study_count} studies contribute to "
            f"this recommendation with {eq.overall_completeness:.0%} "
            f"overall completeness."
        )
    elif tier == "MODERATE":
        overall = (
            f"Some data is missing: {eq.study_count} studies contribute, "
            f"but completeness is {eq.overall_completeness:.0%}. "
            f"Some assumptions were made where data was unavailable."
        )
    else:
        overall = (
            f"Limited data quality: {eq.study_count} studies contribute "
            f"with only {eq.overall_completeness:.0%} completeness. "
            f"Multiple assumptions were made. Results should be "
            f"interpreted with extra caution."
        )

    return QualityDisclosureView(
        completeness_score=eq.overall_completeness,
        completeness_pct=round(eq.overall_completeness * 100),
        study_count=eq.study_count,
        defaults_summary=defaults,
        missing_data_warnings=warnings,
        quality_tier=tier,
        tier_color=color,
        overall_message=overall,
    )
