"""Tests for PRES-PAT2: Intervention Cards.

Covers:
    - Card rendering from SchedulePlan
    - Claim color mapping
    - Bundle detection
    - Empty state handling
    - Pagination (max_display)
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass
from crci.shared.models.output_contracts import (
    CompositeScore,
    RecommendationReport,
    ScheduleAction,
    SchedulePlan,
)

from crci.presentation.intervention_cards import (
    InterventionCardView,
    InterventionCardsView,
    render_intervention_cards,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_action(aid: str = "a1", label: str = "Exercise") -> ScheduleAction:
    return ScheduleAction(
        action_id=aid,
        action_label=label,
        action_class="intervention",
        dose_value=30.0,
        dose_unit="minutes",
        timing_summary="morning",
        frequency="daily",
        duration_days=84,
    )


def _make_plan(
    rank: int = 1,
    utility: float = 0.6,
    plan_type: str = "primary",
    n_actions: int = 1,
    stability: StabilityClass = StabilityClass.STABLE,
) -> SchedulePlan:
    actions = [
        _make_action(f"a{i}", f"Action {i}") for i in range(n_actions)
    ]
    return SchedulePlan(
        schedule_id=f"sched_{rank:03d}",
        run_id="run_001",
        plan_rank=rank,
        plan_type=plan_type,
        actions=actions,
        utility_score=utility,
        stability_class=stability,
        p_rank_1=0.75,
    )


def _make_report(
    n_alternatives: int = 2,
    primary_utility: float = 0.8,
) -> RecommendationReport:
    primary = _make_plan(rank=1, utility=primary_utility, plan_type="primary")
    alternatives = [
        _make_plan(rank=i + 2, utility=primary_utility - (i + 1) * 0.2, plan_type="alternative")
        for i in range(n_alternatives)
    ]

    cs = CompositeScore(
        run_id="run_001",
        subject_ref="patient_001",
        composite_z=-0.5,
        overall_severity=SeverityTier.MODERATE,
    )

    return RecommendationReport(
        run_id="run_001",
        subject_ref="patient_001",
        output_mode=ReportOutputMode.CLINICAL,
        composite_score=cs,
        primary_schedule=primary,
        alternative_schedules=alternatives,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestInterventionCards:

    def test_basic_rendering(self):
        report = _make_report(n_alternatives=2)
        view = render_intervention_cards(report)
        assert isinstance(view, InterventionCardsView)
        assert len(view.cards) == 3  # 1 primary + 2 alternatives
        assert view.n_total == 3
        assert view.showing == 3
        assert not view.empty_state

    def test_card_fields(self):
        report = _make_report(n_alternatives=0)
        view = render_intervention_cards(report)
        card = view.cards[0]
        assert card.rank == 1
        assert card.action_label == "Action 0"
        assert "SAFE_B" in card.expected_benefit_text
        assert card.stability_indicator == "STABLE"
        assert "30.0" in card.dose_text
        assert "84 days" in card.duration_text

    def test_max_display(self):
        report = _make_report(n_alternatives=9)
        view = render_intervention_cards(report, max_display=3)
        assert view.showing == 3
        assert view.n_total == 10

    def test_empty_schedule(self):
        cs = CompositeScore(
            run_id="run_001",
            subject_ref="patient_001",
            composite_z=0.0,
            overall_severity=SeverityTier.MODERATE,
        )
        primary = SchedulePlan(
            schedule_id="empty",
            run_id="run_001",
            plan_rank=1,
            plan_type="primary",
        )
        report = RecommendationReport(
            run_id="run_001",
            subject_ref="patient_001",
            output_mode=ReportOutputMode.CLINICAL,
            composite_score=cs,
            primary_schedule=primary,
        )
        view = render_intervention_cards(report)
        assert view.empty_state
        assert view.n_total == 0
        assert len(view.cards) == 0

    def test_bundle_detection(self):
        """Plans with >1 action should be marked as bundles."""
        primary = _make_plan(rank=1, utility=0.8, n_actions=3)

        cs = CompositeScore(
            run_id="run_001",
            subject_ref="patient_001",
            composite_z=-0.5,
            overall_severity=SeverityTier.MODERATE,
        )

        report = RecommendationReport(
            run_id="run_001",
            subject_ref="patient_001",
            output_mode=ReportOutputMode.CLINICAL,
            composite_score=cs,
            primary_schedule=primary,
        )
        view = render_intervention_cards(report)
        card = view.cards[0]
        assert card.is_bundle
        assert len(card.bundle_members) == 3

    def test_single_action_not_bundle(self):
        report = _make_report(n_alternatives=0)
        view = render_intervention_cards(report)
        assert not view.cards[0].is_bundle
        assert len(view.cards[0].bundle_members) == 0

    def test_utility_score_displayed(self):
        report = _make_report(primary_utility=0.75)
        view = render_intervention_cards(report)
        assert "0.75" in view.cards[0].expected_benefit_text
