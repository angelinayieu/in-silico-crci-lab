"""Tests for PRES-RISK: CRCI Risk Percentage Dashboard.

Covers:
    - Risk gauge rendering with tier colors
    - Domain risk attribution bars
    - Precision influence bars
    - Coverage disclosure logic
    - Empty state when clinical_risk is None
    - Domain color mapping
    - Interval method label formatting
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier
from crci.shared.models.output_contracts import (
    ClinicalRiskProfile,
    CompositeScore,
    DomainRiskBreakdown,
    DomainScore,
    RecommendationReport,
    SchedulePlan,
)

from crci.presentation.risk_dashboard import (
    CoverageDisclosure,
    DomainRiskBar,
    PrecisionBar,
    RiskDashboardView,
    RiskGaugeView,
    _domain_color,
    _interval_method_label,
    render_risk_dashboard,
)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _make_domain_breakdown(
    domain: str = "processing_speed",
    *,
    marginal: float = 35.0,
    trigger: float = 20.0,
    ivw: float = 15.0,
    mean_z: float = -1.2,
    sd_z: float = 0.4,
    z_5th: float = -1.8,
    z_95th: float = -0.6,
    observed: bool = True,
) -> DomainRiskBreakdown:
    return DomainRiskBreakdown(
        domain_id=domain,
        domain_label=domain.replace("_", " ").title(),
        node_ids=[f"{domain}_n1"],
        marginal_risk_pct=marginal,
        trigger_share_pct=trigger,
        ivw_weight_pct=ivw,
        mean_z=mean_z,
        sd_z=sd_z,
        z_5th=z_5th,
        z_95th=z_95th,
        is_directly_observed=observed,
        n_observations=3 if observed else 0,
    )


def _make_risk_profile(
    risk_pct: float = 37.0,
    tier: str = "MODERATE",
    domains: list[DomainRiskBreakdown] | None = None,
    coverage: float = 0.6,
    low_coverage: bool = False,
) -> ClinicalRiskProfile:
    if domains is None:
        domains = [
            _make_domain_breakdown("processing_speed", mean_z=-1.2, observed=True),
            _make_domain_breakdown("memory_verbal", mean_z=-0.8, observed=True),
            _make_domain_breakdown("executive_function", mean_z=-0.3, observed=False),
        ]
    return ClinicalRiskProfile(
        risk_pct=risk_pct,
        risk_lower_pct=32.0,
        risk_upper_pct=41.0,
        risk_range_text="32%–41%",
        risk_tier=tier,
        interval_method="jeffreys",
        interval_level=0.90,
        mc_se=0.02,
        n_draws_used=10000,
        coverage_fraction=coverage,
        low_coverage_warning=low_coverage,
        domain_breakdown=domains,
    )


def _make_report(
    risk: ClinicalRiskProfile | None = None,
) -> RecommendationReport:
    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=-0.5,
        composite_percentile=30.0,
        overall_severity=SeverityTier.MILD_CONCERN,
        domain_scores=[
            DomainScore(
                domain_id="processing_speed",
                domain_label="Processing Speed",
                z_score=-0.3,
                severity_tier=SeverityTier.MODERATE,
            ),
        ],
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
        clinical_risk=risk,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests: Domain Color Mapping
# ═══════════════════════════════════════════════════════════════


class TestDomainColor:
    """_domain_color maps |mean_z| to severity color."""

    def test_green_low_z(self):
        assert _domain_color(0.0) == "green"
        assert _domain_color(0.4) == "green"
        assert _domain_color(-0.3) == "green"

    def test_light_green_zone(self):
        assert _domain_color(0.5) == "light_green"
        assert _domain_color(-0.9) == "light_green"

    def test_yellow_zone(self):
        assert _domain_color(1.0) == "yellow"
        assert _domain_color(-1.4) == "yellow"

    def test_orange_zone(self):
        assert _domain_color(1.5) == "orange"
        assert _domain_color(-1.9) == "orange"

    def test_red_severe(self):
        assert _domain_color(2.0) == "red"
        assert _domain_color(-3.0) == "red"


# ═══════════════════════════════════════════════════════════════
#  Tests: Interval Method Label
# ═══════════════════════════════════════════════════════════════


class TestIntervalMethodLabel:

    def test_jeffreys(self):
        label = _interval_method_label("jeffreys", 0.90)
        assert label == "Jeffreys 90% interval"

    def test_mc_se(self):
        label = _interval_method_label("mc_se", 0.95)
        assert label == "MC SE 95% interval"

    def test_unknown_method(self):
        label = _interval_method_label("bootstrap", 0.80)
        assert label == "MC SE 80% interval"


# ═══════════════════════════════════════════════════════════════
#  Tests: Empty State (no clinical_risk)
# ═══════════════════════════════════════════════════════════════


class TestEmptyState:

    def test_none_risk_produces_empty(self):
        report = _make_report(risk=None)
        view = render_risk_dashboard(report)

        assert isinstance(view, RiskDashboardView)
        assert view.empty_state is True
        assert "not been computed" in view.empty_message
        assert view.gauge.risk_pct == 0.0
        assert view.gauge.risk_tier == "UNKNOWN"
        assert view.gauge.tier_color == "gray"
        assert view.domain_risk_bars == []
        assert view.precision_bars == []
        assert view.coverage.show_warning is True


# ═══════════════════════════════════════════════════════════════
#  Tests: Risk Gauge
# ═══════════════════════════════════════════════════════════════


class TestRiskGauge:

    def test_basic_gauge_values(self):
        risk = _make_risk_profile(risk_pct=37.0, tier="MODERATE")
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        assert view.gauge.risk_pct == 37.0
        assert view.gauge.risk_range_text == "32%–41%"
        assert view.gauge.risk_tier == "MODERATE"
        assert view.gauge.tier_color == "yellow"
        assert "Jeffreys" in view.gauge.interval_method_label
        assert "90%" in view.gauge.interval_method_label
        assert "ICCTF" in view.gauge.criteria_label
        assert "not calibrated" in view.gauge.calibration_label

    @pytest.mark.parametrize(
        "tier,expected_color",
        [
            ("LOW", "green"),
            ("MODERATE", "yellow"),
            ("ELEVATED", "orange"),
            ("HIGH", "red_orange"),
            ("VERY_HIGH", "red"),
        ],
    )
    def test_tier_colors(self, tier: str, expected_color: str):
        risk = _make_risk_profile(tier=tier)
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)
        assert view.gauge.tier_color == expected_color

    def test_unknown_tier_gray(self):
        risk = _make_risk_profile(tier="UNKNOWN_TIER")
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)
        assert view.gauge.tier_color == "gray"


# ═══════════════════════════════════════════════════════════════
#  Tests: Domain Risk Bars (Panel B1)
# ═══════════════════════════════════════════════════════════════


class TestDomainRiskBars:

    def test_bar_count_matches_domains(self):
        risk = _make_risk_profile()
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)
        assert len(view.domain_risk_bars) == 3

    def test_bar_fields(self):
        domain = _make_domain_breakdown(
            "attention", marginal=42.0, trigger=25.0, mean_z=-1.6, observed=True,
        )
        risk = _make_risk_profile(domains=[domain])
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        bar = view.domain_risk_bars[0]
        assert isinstance(bar, DomainRiskBar)
        assert bar.domain_id == "attention"
        assert bar.marginal_risk_pct == 42.0
        assert bar.trigger_share_pct == 25.0
        assert bar.mean_z == -1.6
        assert bar.color == "orange"  # |1.6| in [1.5, 2.0)

    def test_unobserved_domain(self):
        domain = _make_domain_breakdown("language", observed=False, mean_z=-0.2)
        risk = _make_risk_profile(domains=[domain])
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        bar = view.domain_risk_bars[0]
        assert bar.is_observed is False  # should be False for unobserved

    def test_empty_domains(self):
        risk = _make_risk_profile(domains=[])
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)
        assert view.domain_risk_bars == []


# ═══════════════════════════════════════════════════════════════
#  Tests: Precision Bars (Panel B2)
# ═══════════════════════════════════════════════════════════════


class TestPrecisionBars:

    def test_precision_bar_count(self):
        risk = _make_risk_profile()
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)
        assert len(view.precision_bars) == 3

    def test_precision_bar_fields(self):
        domain = _make_domain_breakdown("memory_verbal", ivw=18.5)
        risk = _make_risk_profile(domains=[domain])
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        bar = view.precision_bars[0]
        assert isinstance(bar, PrecisionBar)
        assert bar.domain_id == "memory_verbal"
        assert bar.ivw_weight_pct == 18.5
        assert bar.color == "slate"


# ═══════════════════════════════════════════════════════════════
#  Tests: Coverage Disclosure
# ═══════════════════════════════════════════════════════════════


class TestCoverageDisclosure:

    def test_adequate_coverage(self):
        risk = _make_risk_profile(coverage=0.8, low_coverage=False)
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        cov = view.coverage
        assert isinstance(cov, CoverageDisclosure)
        assert cov.coverage_pct == pytest.approx(80.0)
        assert cov.show_warning is False
        assert "directly observed" in cov.warning_text

    def test_low_coverage_warning(self):
        risk = _make_risk_profile(coverage=0.3, low_coverage=True)
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        cov = view.coverage
        assert cov.show_warning is True
        assert "caution" in cov.warning_text.lower()

    def test_observed_count(self):
        domains = [
            _make_domain_breakdown("d1", observed=True),
            _make_domain_breakdown("d2", observed=False),
            _make_domain_breakdown("d3", observed=True),
        ]
        risk = _make_risk_profile(domains=domains, coverage=0.67)
        report = _make_report(risk=risk)
        view = render_risk_dashboard(report)

        # The dashboard counts is_observed based on domain breakdown
        assert view.coverage.n_total == 3
