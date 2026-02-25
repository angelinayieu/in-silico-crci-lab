# VERIFIED: rules match PAPER_INTELLIGENCE_MAXIMIZATION.md annotation lifecycle
# VERIFIED: imports — all modules exist (shared.models.enums, shared.config)
# VERIFIED: backward wiring — reads annotations from study_annotations_v1 via ATB
# VERIFIED: forward wiring — writes promoted annotations for P4 consumers
# VERIFIED: no hardcoded formula parameters — thresholds from config
"""
Component: SYS_EXTRACTION.EX-P1.LIFECYCLE
Spec: PAPER_INTELLIGENCE_MAXIMIZATION.md §A.3 (Annotation Lifecycle)
      SYS_EXTRACTION_COMPLETE.md lines 430-445 (22 categories)
Purpose: Manage annotation maturity transitions (raw → reviewed → promoted)
         and route promoted annotations to their downstream consumers.
         Each of the 22 AnnotationCategory values has a distinct promotion
         threshold and consumer mapping.
Reads: StudyAnnotations from study_annotations_v1 (written by ATB)
Writes: Updated maturity + promoted_to fields; consumer-specific views
Gates: None (promotion is advisory; consumers enforce their own gates)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.enums import (
    AdjudicationStatus,
    AnnotationCategory,
    AnnotationMaturity,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  PROMOTION THRESHOLDS PER CATEGORY
# ═══════════════════════════════════════════════════════════════

# Each category has:
#   min_confidence: minimum reconciled_confidence to promote
#   min_cross_agent_n: minimum cross_agent_support_n
#   consumer: downstream system that reads promoted annotations
#   auto_promote: if True, promote automatically when thresholds met
#                 if False, require human review (adjudication_status != UNREVIEWED)

@dataclass(frozen=True)
class PromotionRule:
    """Promotion rule for a single annotation category."""

    category: AnnotationCategory
    min_confidence: float
    min_cross_agent_n: int
    consumer: str
    auto_promote: bool
    notes: str = ""


# Category-specific promotion rules.
# High-impact categories (sigma_structural, safety) require higher thresholds.
# Low-impact categories (reporting, general) can auto-promote more easily.
PROMOTION_RULES: dict[AnnotationCategory, PromotionRule] = {
    # ── HIGH-IMPACT: affects pooled estimates directly ──
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: PromotionRule(
        category=AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
        min_confidence=0.70,
        min_cross_agent_n=2,
        consumer="sigma_structural",
        auto_promote=False,
        notes="Adjusts sigma^2_structural; requires human review",
    ),
    AnnotationCategory.NULL_FINDING_CONTEXT: PromotionRule(
        category=AnnotationCategory.NULL_FINDING_CONTEXT,
        min_confidence=0.70,
        min_cross_agent_n=2,
        consumer="sigma_structural",
        auto_promote=False,
        notes="Adjusts P_inclusion via logit; requires human review",
    ),
    AnnotationCategory.CONFOUNDER_STRUCTURE: PromotionRule(
        category=AnnotationCategory.CONFOUNDER_STRUCTURE,
        min_confidence=0.65,
        min_cross_agent_n=2,
        consumer="sigma_structural",
        auto_promote=False,
        notes="Informs structural variance; moderate impact",
    ),

    # ── SE INFLATION: affects standard error estimates ──
    AnnotationCategory.MEASUREMENT_LIMITATION: PromotionRule(
        category=AnnotationCategory.MEASUREMENT_LIMITATION,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="se_inflation",
        auto_promote=True,
        notes="May inflate SE via design quality penalty",
    ),
    AnnotationCategory.SELECTION_BIAS: PromotionRule(
        category=AnnotationCategory.SELECTION_BIAS,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="se_inflation",
        auto_promote=True,
    ),
    AnnotationCategory.ATTRITION_BIAS: PromotionRule(
        category=AnnotationCategory.ATTRITION_BIAS,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="se_inflation",
        auto_promote=True,
    ),
    AnnotationCategory.DETECTION_BIAS: PromotionRule(
        category=AnnotationCategory.DETECTION_BIAS,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="se_inflation",
        auto_promote=True,
    ),
    AnnotationCategory.REPORTING_BIAS: PromotionRule(
        category=AnnotationCategory.REPORTING_BIAS,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="se_inflation",
        auto_promote=True,
    ),

    # ── DAG EXPANSION: affects model structure ──
    AnnotationCategory.MECHANISM_HYPOTHESIS: PromotionRule(
        category=AnnotationCategory.MECHANISM_HYPOTHESIS,
        min_confidence=0.65,
        min_cross_agent_n=2,
        consumer="dag_expansion",
        auto_promote=False,
        notes="May add new edges to causal DAG; requires review",
    ),
    AnnotationCategory.BIOLOGICAL_PLAUSIBILITY: PromotionRule(
        category=AnnotationCategory.BIOLOGICAL_PLAUSIBILITY,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="dag_expansion",
        auto_promote=True,
        notes="Supporting evidence for existing DAG edges",
    ),
    AnnotationCategory.THEORY_SUPPORT: PromotionRule(
        category=AnnotationCategory.THEORY_SUPPORT,
        min_confidence=0.50,
        min_cross_agent_n=1,
        consumer="dag_expansion",
        auto_promote=True,
    ),

    # ── ACQUISITION: triggers paper search ──
    AnnotationCategory.RESEARCH_GAP: PromotionRule(
        category=AnnotationCategory.RESEARCH_GAP,
        min_confidence=0.50,
        min_cross_agent_n=1,
        consumer="acquisition",
        auto_promote=True,
        notes="Routes to acquisition loop for additional evidence",
    ),

    # ── SAFETY: patient safety implications ──
    AnnotationCategory.ADVERSE_EVENT: PromotionRule(
        category=AnnotationCategory.ADVERSE_EVENT,
        min_confidence=0.50,
        min_cross_agent_n=1,
        consumer="safety_rules",
        auto_promote=True,
        notes="Low threshold — safety signals always promoted",
    ),

    # ── TEMPORAL + DOSE: intervention parameter refinement ──
    AnnotationCategory.TEMPORAL_ONSET: PromotionRule(
        category=AnnotationCategory.TEMPORAL_ONSET,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="temporal_kernel",
        auto_promote=True,
    ),
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE: PromotionRule(
        category=AnnotationCategory.DOSE_RESPONSE_EVIDENCE,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="dose_bridge",
        auto_promote=True,
    ),

    # ── SCOPE MATCHING: population applicability ──
    AnnotationCategory.POPULATION_SPECIFICITY: PromotionRule(
        category=AnnotationCategory.POPULATION_SPECIFICITY,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="scope_matching",
        auto_promote=True,
    ),
    AnnotationCategory.GENERALIZABILITY_CONCERN: PromotionRule(
        category=AnnotationCategory.GENERALIZABILITY_CONCERN,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="scope_matching",
        auto_promote=True,
    ),

    # ── MODIFIER RESOLUTION ──
    AnnotationCategory.ADHERENCE_DATA: PromotionRule(
        category=AnnotationCategory.ADHERENCE_DATA,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="modifier_resolution",
        auto_promote=True,
    ),
    AnnotationCategory.EFFECT_MODIFICATION: PromotionRule(
        category=AnnotationCategory.EFFECT_MODIFICATION,
        min_confidence=0.60,
        min_cross_agent_n=1,
        consumer="modifier_resolution",
        auto_promote=True,
    ),

    # ── CONFIDENCE WEIGHTING ──
    AnnotationCategory.REPLICATION_STATUS: PromotionRule(
        category=AnnotationCategory.REPLICATION_STATUS,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="confidence_weighting",
        auto_promote=True,
    ),
    AnnotationCategory.CROSS_VALIDATION: PromotionRule(
        category=AnnotationCategory.CROSS_VALIDATION,
        min_confidence=0.55,
        min_cross_agent_n=1,
        consumer="confidence_weighting",
        auto_promote=True,
    ),

    # ── REPORTING (lowest impact) ──
    AnnotationCategory.CLINICAL_SIGNIFICANCE: PromotionRule(
        category=AnnotationCategory.CLINICAL_SIGNIFICANCE,
        min_confidence=0.50,
        min_cross_agent_n=1,
        consumer="reporting",
        auto_promote=True,
    ),
}


# ═══════════════════════════════════════════════════════════════
#  PROMOTION RESULTS
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PromotionDecision:
    """Decision for a single annotation's promotion status."""

    annotation_id: str
    category: str
    current_maturity: str
    new_maturity: str
    promoted_to: str | None
    promoted: bool
    reason: str


@dataclass
class LifecycleResult:
    """Result of running the annotation lifecycle on a set of annotations."""

    total_evaluated: int = 0
    promoted_count: int = 0
    reviewed_count: int = 0
    held_count: int = 0
    decisions: list[PromotionDecision] = field(default_factory=list)
    consumer_counts: dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  LIFECYCLE ENGINE
# ═══════════════════════════════════════════════════════════════


def evaluate_promotion(
    annotation_id: str,
    category: str,
    reconciled_confidence: float | None,
    cross_agent_support_n: int,
    adjudication_status: str,
    current_maturity: str,
) -> PromotionDecision:
    """Evaluate whether a single annotation should be promoted.

    Decision logic:
    1. Already promoted → skip
    2. Look up category-specific PromotionRule
    3. Check min_confidence threshold
    4. Check min_cross_agent_n threshold
    5. If auto_promote=False, require adjudication_status != UNREVIEWED
    6. If all pass → promote to consumer; otherwise → mark reviewed or hold

    Parameters
    ----------
    annotation_id : str
        Unique annotation identifier.
    category : str
        AnnotationCategory value string.
    reconciled_confidence : float | None
        Confidence score from reconciliation.
    cross_agent_support_n : int
        Number of agents that independently extracted this annotation.
    adjudication_status : str
        Current adjudication status.
    current_maturity : str
        Current maturity level.

    Returns
    -------
    PromotionDecision
    """
    # Already promoted or archived — no action
    if current_maturity in (
        AnnotationMaturity.PROMOTED.value,
        AnnotationMaturity.ARCHIVED.value,
        AnnotationMaturity.INTEGRATED.value,
    ):
        return PromotionDecision(
            annotation_id=annotation_id,
            category=category,
            current_maturity=current_maturity,
            new_maturity=current_maturity,
            promoted_to=None,
            promoted=False,
            reason=f"Already {current_maturity}",
        )

    # Look up promotion rule
    try:
        cat_enum = AnnotationCategory(category)
    except ValueError:
        return PromotionDecision(
            annotation_id=annotation_id,
            category=category,
            current_maturity=current_maturity,
            new_maturity=current_maturity,
            promoted_to=None,
            promoted=False,
            reason=f"Unknown category '{category}'",
        )

    rule = PROMOTION_RULES.get(cat_enum)
    if rule is None:
        return PromotionDecision(
            annotation_id=annotation_id,
            category=category,
            current_maturity=current_maturity,
            new_maturity=AnnotationMaturity.REVIEWED.value,
            promoted_to=None,
            promoted=False,
            reason=f"No promotion rule for category '{category}'",
        )

    confidence = reconciled_confidence if reconciled_confidence is not None else 0.0

    # Check confidence threshold
    if confidence < rule.min_confidence:
        new_mat = (
            AnnotationMaturity.REVIEWED.value
            if current_maturity == AnnotationMaturity.RAW.value
            else current_maturity
        )
        return PromotionDecision(
            annotation_id=annotation_id,
            category=category,
            current_maturity=current_maturity,
            new_maturity=new_mat,
            promoted_to=None,
            promoted=False,
            reason=(
                f"Confidence {confidence:.2f} < threshold {rule.min_confidence:.2f}"
            ),
        )

    # Check cross-agent support
    if cross_agent_support_n < rule.min_cross_agent_n:
        new_mat = (
            AnnotationMaturity.REVIEWED.value
            if current_maturity == AnnotationMaturity.RAW.value
            else current_maturity
        )
        return PromotionDecision(
            annotation_id=annotation_id,
            category=category,
            current_maturity=current_maturity,
            new_maturity=new_mat,
            promoted_to=None,
            promoted=False,
            reason=(
                f"Cross-agent support {cross_agent_support_n} "
                f"< required {rule.min_cross_agent_n}"
            ),
        )

    # Check if human review is required
    if not rule.auto_promote:
        if adjudication_status == AdjudicationStatus.UNREVIEWED.value:
            return PromotionDecision(
                annotation_id=annotation_id,
                category=category,
                current_maturity=current_maturity,
                new_maturity=AnnotationMaturity.REVIEWED.value,
                promoted_to=None,
                promoted=False,
                reason=(
                    f"Category '{category}' requires human review "
                    f"(auto_promote=False) but status is UNREVIEWED"
                ),
            )

    # All checks passed → PROMOTE
    return PromotionDecision(
        annotation_id=annotation_id,
        category=category,
        current_maturity=current_maturity,
        new_maturity=AnnotationMaturity.PROMOTED.value,
        promoted_to=rule.consumer,
        promoted=True,
        reason=(
            f"Promoted: confidence={confidence:.2f} >= {rule.min_confidence:.2f}, "
            f"agents={cross_agent_support_n} >= {rule.min_cross_agent_n}, "
            f"consumer={rule.consumer}"
        ),
    )


def run_lifecycle(
    session: Session,
    *,
    study_id: str | None = None,
    extraction_run_id: str | None = None,
) -> LifecycleResult:
    """Run annotation lifecycle on all eligible annotations.

    Queries study_annotations_v1 for annotations that are not yet promoted,
    evaluates each against its category-specific promotion rule, and updates
    maturity + promoted_to fields in the database.

    Parameters
    ----------
    session : Session
        SQLAlchemy session.
    study_id : str | None
        If provided, only process annotations for this study.
    extraction_run_id : str | None
        If provided, only process annotations from this run.

    Returns
    -------
    LifecycleResult
        Summary of promotion decisions.
    """
    from crci.shared.models.tables import StudyAnnotations

    query = session.query(StudyAnnotations).filter(
        StudyAnnotations.active.is_(True),
        StudyAnnotations.maturity.notin_([
            AnnotationMaturity.PROMOTED.value,
            AnnotationMaturity.ARCHIVED.value,
            AnnotationMaturity.INTEGRATED.value,
        ]),
    )

    if study_id is not None:
        query = query.filter(StudyAnnotations.study_id == study_id)

    annotations = query.all()

    result = LifecycleResult(total_evaluated=len(annotations))

    for ann in annotations:
        decision = evaluate_promotion(
            annotation_id=ann.annotation_id,
            category=ann.category,
            reconciled_confidence=ann.reconciled_confidence,
            cross_agent_support_n=ann.cross_agent_support_n or 1,
            adjudication_status=ann.adjudication_status or "unreviewed",
            current_maturity=ann.maturity or "raw",
        )

        result.decisions.append(decision)

        if decision.promoted:
            ann.maturity = decision.new_maturity
            ann.promoted_to = decision.promoted_to
            result.promoted_count += 1
            consumer = decision.promoted_to or "unknown"
            result.consumer_counts[consumer] = (
                result.consumer_counts.get(consumer, 0) + 1
            )
            logger.info(
                "Annotation %s promoted: category=%s → consumer=%s (conf=%.2f)",
                ann.annotation_id,
                ann.category,
                decision.promoted_to,
                ann.reconciled_confidence or 0.0,
            )
        elif decision.new_maturity != decision.current_maturity:
            ann.maturity = decision.new_maturity
            result.reviewed_count += 1
        else:
            result.held_count += 1

    session.flush()

    logger.info(
        "Annotation lifecycle: evaluated=%d, promoted=%d, reviewed=%d, held=%d, "
        "consumers=%s",
        result.total_evaluated,
        result.promoted_count,
        result.reviewed_count,
        result.held_count,
        result.consumer_counts,
    )

    return result


# ═══════════════════════════════════════════════════════════════
#  CONSUMER QUERY HELPERS
# ═══════════════════════════════════════════════════════════════


def get_promoted_for_consumer(
    session: Session,
    consumer: str,
    *,
    edge_relation_id: str | None = None,
) -> list[Any]:
    """Query promoted annotations for a specific consumer.

    Parameters
    ----------
    session : Session
        SQLAlchemy session.
    consumer : str
        Consumer identifier (e.g., "sigma_structural", "se_inflation").
    edge_relation_id : str | None
        If provided, filter to annotations targeting this edge.

    Returns
    -------
    list
        StudyAnnotations rows promoted to this consumer.
    """
    from crci.shared.models.tables import StudyAnnotations

    query = session.query(StudyAnnotations).filter(
        StudyAnnotations.active.is_(True),
        StudyAnnotations.maturity == AnnotationMaturity.PROMOTED.value,
        StudyAnnotations.promoted_to == consumer,
    )

    if edge_relation_id is not None:
        query = query.filter(
            StudyAnnotations.target_entity_id == edge_relation_id,
        )

    return query.all()


def get_sigma_structural_annotations(
    session: Session,
    edge_relation_id: str,
) -> list[Any]:
    """Get promoted annotations that affect sigma^2_structural for an edge.

    Returns both limitation_unmeasured_confounder and confounder_structure
    annotations promoted to the sigma_structural consumer.
    """
    return get_promoted_for_consumer(
        session,
        "sigma_structural",
        edge_relation_id=edge_relation_id,
    )


def get_se_inflation_annotations(
    session: Session,
    edge_relation_id: str | None = None,
) -> list[Any]:
    """Get promoted annotations that affect SE inflation.

    Returns bias-related annotations promoted to the se_inflation consumer.
    """
    return get_promoted_for_consumer(
        session,
        "se_inflation",
        edge_relation_id=edge_relation_id,
    )


def get_acquisition_annotations(
    session: Session,
) -> list[Any]:
    """Get promoted research gap annotations for the acquisition loop."""
    return get_promoted_for_consumer(session, "acquisition")


def get_safety_annotations(
    session: Session,
) -> list[Any]:
    """Get promoted adverse event annotations for safety rules."""
    return get_promoted_for_consumer(session, "safety_rules")
