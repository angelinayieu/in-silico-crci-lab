"""
Component: SYS_EXTRACTION.EX-ACCUM
Spec: PIMP §3.6 — Cross-Paper Accumulation Promotion Logic
Purpose: Scan study_annotations_v1 for annotation clusters across
         independent studies that have hit accumulation thresholds.
         This implements the "self-improvement loop" — when enough
         independent papers report the same annotation target, the
         cluster becomes a promotion candidate.
Reads: study_annotations_v1 rows (raw/reviewed maturity)
Writes: Promotion candidates (returned in-memory, optionally
        updates maturity/promoted_to when dry_run=False)
Gates: None (advisory, no hard gates)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.enums import AnnotationCategory

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  CATEGORY → THRESHOLD MAPPING
# ═══════════════════════════════════════════════════════════════

# Maps (category) → minimum distinct study_ids for accumulation promotion.
# Uses config constants from PIMP §3.6.
_CATEGORY_THRESHOLDS: dict[AnnotationCategory, int] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS: config.ACCUM_MECHANISM_HYPOTHESIS,
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: config.ACCUM_UNMEASURED_CONFOUNDER,
    AnnotationCategory.ADHERENCE_DATA: config.ACCUM_ADHERENCE_DATA,
    AnnotationCategory.ADVERSE_EVENT: config.ACCUM_ADVERSE_EVENT_MILD,
    AnnotationCategory.TEMPORAL_ONSET: config.ACCUM_TEMPORAL_ONSET_DECAY,
    AnnotationCategory.TEMPORAL_DECAY: config.ACCUM_TEMPORAL_ONSET_DECAY,
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE: config.ACCUM_DOSE_RESPONSE_QUALITATIVE,
    AnnotationCategory.RESEARCH_GAP: config.ACCUM_RESEARCH_GAP_CYCLES,
    AnnotationCategory.MECHANISM_INTERACTION: config.ACCUM_MECHANISM_HYPOTHESIS,
    AnnotationCategory.MEASUREMENT_LIMITATION: config.ACCUM_INSTRUMENT_OBSERVATION,
}

# Proposed action per category (what happens when threshold is met)
_PROPOSED_ACTIONS: dict[AnnotationCategory, str] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS: (
        "Add to edge_relations_definitions_v1 as hypothesized edge"
    ),
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: (
        "New σ² component for sigma_structural"
    ),
    AnnotationCategory.ADHERENCE_DATA: (
        "Updated logit(P_adhere) coefficients for modifier_resolution"
    ),
    AnnotationCategory.ADVERSE_EVENT: (
        "New row in contraindication_rules_v1"
    ),
    AnnotationCategory.TEMPORAL_ONSET: (
        "Updated kernel onset parameter in intervention_kernels_v1"
    ),
    AnnotationCategory.TEMPORAL_DECAY: (
        "Updated kernel decay parameter in intervention_kernels_v1"
    ),
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE: (
        "Flag edge for RCS comparison instead of default Emax model"
    ),
    AnnotationCategory.RESEARCH_GAP: (
        "Elevated to critical gap in sufficiency reporting"
    ),
    AnnotationCategory.MECHANISM_INTERACTION: (
        "Flag pathway pair for synergy model evaluation"
    ),
    AnnotationCategory.MEASUREMENT_LIMITATION: (
        "Updated SE multiplier in observation_noise_v1"
    ),
}


# ═══════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class AccumulationCandidate:
    """An annotation cluster that has hit its accumulation threshold."""

    category: AnnotationCategory
    target_entity_type: str
    target_entity_id: str
    distinct_study_count: int
    threshold: int
    annotation_ids: list[str]
    proposed_action: str


@dataclass
class AccumulationResult:
    """Summary of accumulation check results."""

    total_groups_scanned: int = 0
    candidates_found: int = 0
    candidates: list[AccumulationCandidate] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  CORE FUNCTION
# ═══════════════════════════════════════════════════════════════


def check_accumulation_thresholds(
    session: Session,
) -> list[AccumulationCandidate]:
    """Scan study_annotations_v1 for annotation clusters at promotion threshold.

    Groups annotations by (category, target_entity_type, target_entity_id).
    Counts distinct study_id per group.
    Compares to config.ACCUM_* thresholds.
    Returns candidates that meet or exceed their threshold.

    Only considers annotations with:
    - active = True
    - maturity in ('raw', 'reviewed') — already-promoted are excluded
    - category in _CATEGORY_THRESHOLDS (not all categories accumulate)

    This is the cross-paper self-improvement loop from PIMP §3.6.
    """
    from crci.shared.models.tables import StudyAnnotations

    candidates: list[AccumulationCandidate] = []
    total_groups = 0

    # Query: group by (category, target_entity_type, target_entity_id),
    # count distinct study_id, collect annotation_ids
    for category, threshold in _CATEGORY_THRESHOLDS.items():
        cat_value = category.value

        # Count distinct study_ids per (target_entity_type, target_entity_id)
        groups = (
            session.query(
                StudyAnnotations.target_entity_type,
                StudyAnnotations.target_entity_id,
                func.count(func.distinct(StudyAnnotations.study_id)).label("n_studies"),
            )
            .filter(
                StudyAnnotations.active.is_(True),
                StudyAnnotations.category == cat_value,
                StudyAnnotations.maturity.in_(["raw", "reviewed"]),
                StudyAnnotations.target_entity_type.isnot(None),
                StudyAnnotations.target_entity_id.isnot(None),
            )
            .group_by(
                StudyAnnotations.target_entity_type,
                StudyAnnotations.target_entity_id,
            )
            .having(
                func.count(func.distinct(StudyAnnotations.study_id)) >= threshold,
            )
            .all()
        )

        total_groups += len(groups)

        for group in groups:
            entity_type = group[0]
            entity_id = group[1]
            n_studies = group[2]

            # Fetch the actual annotation IDs in this cluster
            ann_ids_rows = (
                session.query(StudyAnnotations.annotation_id)
                .filter(
                    StudyAnnotations.active.is_(True),
                    StudyAnnotations.category == cat_value,
                    StudyAnnotations.maturity.in_(["raw", "reviewed"]),
                    StudyAnnotations.target_entity_type == entity_type,
                    StudyAnnotations.target_entity_id == entity_id,
                )
                .all()
            )
            ann_ids = [r[0] for r in ann_ids_rows]

            candidates.append(AccumulationCandidate(
                category=category,
                target_entity_type=entity_type or "",
                target_entity_id=entity_id or "",
                distinct_study_count=n_studies,
                threshold=threshold,
                annotation_ids=ann_ids,
                proposed_action=_PROPOSED_ACTIONS.get(
                    category, "Review for potential promotion"
                ),
            ))

    if candidates:
        logger.info(
            "ACCUM: %d groups scanned, %d accumulation candidates found",
            total_groups,
            len(candidates),
        )
    else:
        logger.debug(
            "ACCUM: %d groups scanned, no accumulation candidates yet",
            total_groups,
        )

    return candidates


def promote_accumulated(
    session: Session,
    candidates: list[AccumulationCandidate],
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Execute promotion for accumulated annotation clusters.

    When dry_run=True: returns proposed promotions without DB writes.
    When dry_run=False: updates maturity → 'promoted', sets promoted_to.

    Per PIMP §3.6:
    - mechanism_hypothesis → new hypothesized row in edge_relations_definitions_v1
    - limitation_unmeasured_confounder → new σ² component
    - adverse_event → new row in contraindication_rules_v1
    - temporal_onset/temporal_decay → updated kernel params
    - dose_response_qualitative → flag for Emax-vs-RCS comparison
    - research_gap → elevated to "critical gap" in sufficiency reporting

    Returns list of promotion decisions (dicts with annotation_id, action, etc.)
    """
    from crci.shared.models.enums import AnnotationMaturity
    from crci.shared.models.tables import StudyAnnotations

    decisions: list[dict[str, Any]] = []

    for candidate in candidates:
        consumer = _PROPOSED_ACTIONS.get(candidate.category, "review")

        for ann_id in candidate.annotation_ids:
            decision = {
                "annotation_id": ann_id,
                "category": candidate.category.value,
                "target_entity_type": candidate.target_entity_type,
                "target_entity_id": candidate.target_entity_id,
                "distinct_study_count": candidate.distinct_study_count,
                "threshold": candidate.threshold,
                "proposed_action": candidate.proposed_action,
                "dry_run": dry_run,
                "promoted": False,
            }

            if not dry_run:
                # Update annotation in DB
                ann = (
                    session.query(StudyAnnotations)
                    .filter(StudyAnnotations.annotation_id == ann_id)
                    .first()
                )
                if ann and ann.maturity != AnnotationMaturity.PROMOTED.value:
                    ann.maturity = AnnotationMaturity.PROMOTED.value
                    ann.promoted_to = _get_consumer_for_category(candidate.category)
                    decision["promoted"] = True
                    logger.info(
                        "ACCUM: promoted annotation %s (category=%s, "
                        "target=%s:%s, %d studies)",
                        ann_id,
                        candidate.category.value,
                        candidate.target_entity_type,
                        candidate.target_entity_id,
                        candidate.distinct_study_count,
                    )

            decisions.append(decision)

    if not dry_run:
        session.flush()

    logger.info(
        "ACCUM promote: %d decisions (%s), %d promoted",
        len(decisions),
        "dry_run" if dry_run else "LIVE",
        sum(1 for d in decisions if d["promoted"]),
    )

    return decisions


def _get_consumer_for_category(category: AnnotationCategory) -> str:
    """Map category to consumer string for promotion routing."""
    from crci.extraction.p1_extraction.annotation_lifecycle import PROMOTION_RULES

    rule = PROMOTION_RULES.get(category)
    if rule:
        return rule.consumer
    return "general"
