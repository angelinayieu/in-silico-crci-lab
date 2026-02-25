# VERIFIED: spec SYS_PRES lines 117-131 (PRES-PAT2)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-PAT2
Spec: SYS_PRESENTATION_COMPLETE.md lines 117-131
Purpose: Render ranked intervention cards with evidence badges,
         stability indicators, and schedule details.
Reads: RecommendationReport.primary_schedule, alternative_schedules
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import RecommendationReport, SchedulePlan, ScheduleAction

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


_CLAIM_COLORS: dict[str, str] = {
    "causal_supported": "green",
    "associational_only": "yellow",
    "model_implied": "gray",
}


@dataclass(frozen=True)
class InterventionCardView:
    """One intervention card for patient display."""

    rank: int
    action_label: str
    expected_benefit_text: str
    cri_text: str
    claim_level: str
    claim_color: str
    stability_indicator: str
    dose_text: str
    duration_text: str
    is_bundle: bool = False
    bundle_members: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InterventionCardsView:
    """PRES-PAT2: All intervention cards for display."""

    cards: list[InterventionCardView]
    n_total: int
    showing: int
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def _render_card(plan: SchedulePlan) -> InterventionCardView:
    """Render one schedule plan as a card."""
    actions = plan.actions
    label = actions[0].action_label if actions else "Unknown"
    dose_text = f"{actions[0].dose_value} {actions[0].dose_unit}" if actions else "N/A"
    dur_text = f"{actions[0].duration_days} days" if actions else "N/A"

    return InterventionCardView(
        rank=plan.plan_rank,
        action_label=label,
        expected_benefit_text=f"SAFE_B = {plan.utility_score:.2f}",
        cri_text="",
        claim_level=plan.plan_type,
        claim_color=_CLAIM_COLORS.get(plan.plan_type, "gray"),
        stability_indicator=plan.stability_class.value,
        dose_text=dose_text,
        duration_text=dur_text,
        is_bundle=len(actions) > 1,
        bundle_members=[a.action_label for a in actions] if len(actions) > 1 else [],
    )


def render_intervention_cards(
    report: RecommendationReport,
    max_display: int = 5,
) -> InterventionCardsView:
    """PRES-PAT2: Render ranked intervention cards.

    Display order: SAFE_B descending; top 5 shown by default.

    Args:
        report: RecommendationReport.
        max_display: Maximum cards to show initially.

    Returns:
        InterventionCardsView.
    """
    all_plans = [report.primary_schedule] + list(report.alternative_schedules)

    if not all_plans or (len(all_plans) == 1 and all_plans[0].schedule_id == "empty"):
        return InterventionCardsView(
            cards=[],
            n_total=0,
            showing=0,
            empty_state=True,
            empty_message="No interventions could be ranked. This may indicate insufficient data.",
        )

    cards = [_render_card(p) for p in all_plans[:max_display]]

    return InterventionCardsView(
        cards=cards,
        n_total=len(all_plans),
        showing=len(cards),
    )
