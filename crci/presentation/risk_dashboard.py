# VERIFIED: spec IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §4.5 (PRES)
# VERIFIED: read-only — no computation, no DB writes
# VERIFIED: backward wiring — reads ClinicalRiskProfile from output_contracts.py
# VERIFIED: forward wiring — writes RiskDashboardView for renderer (no framework yet)
"""
Component: SYS_PRESENTATION.PRES-RISK
Spec: IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §4.5
Purpose: Render CRCI risk percentage dashboard — risk gauge, domain
         breakdown bars (marginal impairment + trigger-share),
         precision influence panel, coverage disclosure, and calibration
         disclaimer.
Reads: RecommendationReport.clinical_risk (ClinicalRiskProfile)
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    ClinicalRiskProfile,
    DomainRiskBreakdown,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RiskGaugeView:
    """Risk percentage gauge display."""

    risk_pct: float
    risk_range_text: str          # "32%–41%"
    risk_tier: str                # LOW / MODERATE / ELEVATED / HIGH / VERY_HIGH
    tier_color: str               # green / yellow / orange / red_orange / red
    interval_method_label: str    # "Jeffreys 90% interval" or "MC SE 90% interval"
    criteria_label: str           # "ICCTF domain-level criteria (Wefel et al., 2011)"
    calibration_label: str        # "Model-derived estimate — not calibrated..."


@dataclass(frozen=True)
class DomainRiskBar:
    """One bar in the domain risk attribution chart (panel B1)."""

    domain_id: str
    domain_label: str
    marginal_risk_pct: float      # bar fill (horizontal extent)
    trigger_share_pct: float      # annotation text: trigger-share %
    color: str                    # severity color based on mean_z
    is_observed: bool             # False → apply hatching pattern
    mean_z: float                 # for tooltip
    z_range_text: str             # "[-2.1, -0.8]" — 5th to 95th percentile


@dataclass(frozen=True)
class PrecisionBar:
    """One bar in the IVW precision influence chart (panel B2)."""

    domain_id: str
    domain_label: str
    ivw_weight_pct: float         # bar fill
    color: str = "slate"


@dataclass(frozen=True)
class CoverageDisclosure:
    """Coverage warning panel."""

    coverage_pct: float           # coverage × 100
    n_observed: int
    n_total: int
    show_warning: bool            # True if low_coverage_warning
    warning_text: str


@dataclass(frozen=True)
class RiskDashboardView:
    """PRES-RISK: Everything needed to render the CRCI risk dashboard.

    Two linked panels (§4.5):
        A. Risk Estimate — gauge, range bar, tier badge, disclosures
        B1. Risk Attribution — domain bars with marginal risk + trigger-share
        B2. Precision Influence — separate IVW weight bars
    """

    gauge: RiskGaugeView
    domain_risk_bars: list[DomainRiskBar]
    precision_bars: list[PrecisionBar]
    coverage: CoverageDisclosure
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════

_TIER_COLORS: dict[str, str] = {
    "LOW": "green",
    "MODERATE": "yellow",
    "ELEVATED": "orange",
    "HIGH": "red_orange",
    "VERY_HIGH": "red",
}


def _domain_color(mean_z: float) -> str:
    """Map mean domain z-score to bar color."""
    abs_z = abs(mean_z)
    if abs_z < 0.5:
        return "green"
    if abs_z < 1.0:
        return "light_green"
    if abs_z < 1.5:
        return "yellow"
    if abs_z < 2.0:
        return "orange"
    return "red"


def _interval_method_label(method: str, level: float) -> str:
    """Human-readable interval method label."""
    level_pct = int(level * 100)
    if method == "jeffreys":
        return f"Jeffreys {level_pct}% interval"
    return f"MC SE {level_pct}% interval"


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_risk_dashboard(report: RecommendationReport) -> RiskDashboardView:
    """Transform ClinicalRiskProfile into RiskDashboardView.

    Args:
        report: RecommendationReport containing clinical_risk field.

    Returns:
        RiskDashboardView ready for any rendering framework.
    """
    if report.clinical_risk is None:
        return RiskDashboardView(
            gauge=RiskGaugeView(
                risk_pct=0.0,
                risk_range_text="N/A",
                risk_tier="UNKNOWN",
                tier_color="gray",
                interval_method_label="N/A",
                criteria_label="N/A",
                calibration_label="N/A",
            ),
            domain_risk_bars=[],
            precision_bars=[],
            coverage=CoverageDisclosure(
                coverage_pct=0.0,
                n_observed=0,
                n_total=0,
                show_warning=True,
                warning_text="No clinical risk estimate available.",
            ),
            empty_state=True,
            empty_message="Clinical risk estimation has not been computed. "
                          "Requires posterior draws from the MC sampler (D1c).",
        )

    risk = report.clinical_risk

    # ── Panel A: Risk Gauge ──
    gauge = RiskGaugeView(
        risk_pct=risk.risk_pct,
        risk_range_text=risk.risk_range_text,
        risk_tier=risk.risk_tier,
        tier_color=_TIER_COLORS.get(risk.risk_tier, "gray"),
        interval_method_label=_interval_method_label(
            risk.interval_method, risk.interval_level,
        ),
        criteria_label=(
            "ICCTF domain-level criteria "
            "(Wefel et al., 2011, Lancet Oncol)"
        ),
        calibration_label=(
            "Model-derived estimate \u2014 not calibrated to "
            "clinical incidence rates"
        ),
    )

    # ── Panel B1: Domain Risk Attribution Bars ──
    domain_bars: list[DomainRiskBar] = []
    for db in risk.domain_breakdown:
        z_range_text = f"[{db.z_5th:.1f}, {db.z_95th:.1f}]"

        domain_bars.append(DomainRiskBar(
            domain_id=db.domain_id,
            domain_label=db.domain_label,
            marginal_risk_pct=db.marginal_risk_pct,
            trigger_share_pct=db.trigger_share_pct,
            color=_domain_color(db.mean_z),
            is_observed=db.is_directly_observed,
            mean_z=db.mean_z,
            z_range_text=z_range_text,
        ))

    # ── Panel B2: Precision Influence Bars ──
    precision_bars = [
        PrecisionBar(
            domain_id=db.domain_id,
            domain_label=db.domain_label,
            ivw_weight_pct=db.ivw_weight_pct,
        )
        for db in risk.domain_breakdown
    ]

    # ── Coverage disclosure ──
    n_observed = sum(1 for db in risk.domain_breakdown if db.is_directly_observed)
    n_total = len(risk.domain_breakdown)
    coverage_pct = risk.coverage_fraction * 100.0

    if risk.low_coverage_warning:
        warning_text = (
            f"Only {n_observed} of {n_total} cognitive domains have "
            f"direct observations ({coverage_pct:.0f}% coverage). "
            f"This risk estimate is predominantly model-driven — "
            f"interpret with caution."
        )
    else:
        warning_text = (
            f"{n_observed} of {n_total} domains directly observed "
            f"({coverage_pct:.0f}% coverage)."
        )

    coverage = CoverageDisclosure(
        coverage_pct=coverage_pct,
        n_observed=n_observed,
        n_total=n_total,
        show_warning=risk.low_coverage_warning,
        warning_text=warning_text,
    )

    logger.info(
        "PRES-RISK: Rendered risk dashboard — %.1f%% %s, "
        "%d domain bars, coverage=%.0f%%",
        risk.risk_pct, risk.risk_tier, len(domain_bars), coverage_pct,
    )

    return RiskDashboardView(
        gauge=gauge,
        domain_risk_bars=domain_bars,
        precision_bars=precision_bars,
        coverage=coverage,
    )
