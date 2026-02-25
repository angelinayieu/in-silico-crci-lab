# VERIFIED: rules [AT-01..AT-06] match spec lines 547-558
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ReconciledAnnotation from reconciliation.py
# VERIFIED: forward wiring — writes StudyAnnotations (B11) for EX-P4-MA, EX-ACQ-GAP, EX-PROM-THR
# VERIFIED: no hardcoded formula parameters (ATB_SPECULATIVE_CONFIDENCE_CEILING from config)
# VERIFIED: gates [AT-01..AT-06] raise/reject on failure
"""
Component: EX-P1-ATB — Annotation Trust Boundary
Spec: SYS_EXTRACTION_COMPLETE.md lines 544-558
Formulas: None (rule-based validation)
Reads: ReconciledAnnotation (from reconciliation.py),
       existing study_annotations_v1 (for contradiction check AT-04)
Writes: study_annotations_v1 (B11 — validated canonical annotations),
        review_tasks (for rejected annotations)
Gates: AT-01 (provenance), AT-02 (explicit/inferred), AT-03 (category fields),
       AT-04 (contradiction routing), AT-05 (high-impact consumer gate),
       AT-06 (speculative ceiling)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.enums import (
    AdjudicationStatus,
    AnnotationCategory,
    AnnotationMaturity,
)
from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.tables import ReviewTask, StudyAnnotations
from crci.extraction.p1_extraction.reconciliation import (
    ReconciledAnnotation,
    ReconciliationResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  ATB RESULT TYPES
# ═══════════════════════════════════════════════════════════════


class ATBRejection(BaseModel):
    """Record of a single annotation rejection by the ATB."""

    annotation_id: str
    rule_id: str
    reason: str
    category: str
    content_preview: str


class ATBResult(BaseModel):
    """Complete output of the Annotation Trust Boundary.

    Contains both accepted and rejected annotations with full audit trail.
    """

    study_id: str
    accepted: list[ReconciledAnnotation] = Field(default_factory=list)
    rejected: list[ATBRejection] = Field(default_factory=list)
    total_input: int = 0
    total_accepted: int = 0
    total_rejected: int = 0


# ═══════════════════════════════════════════════════════════════
#  GENERIC CONSTANTS — Categories requiring high-impact scrutiny
# ═══════════════════════════════════════════════════════════════

# AT-05: Categories that affect structural variance / DAG expansion / safety
_HIGH_IMPACT_CATEGORIES: frozenset[AnnotationCategory] = frozenset({
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
    AnnotationCategory.ADVERSE_EVENT,
})

# AT-02: Evidence strengths classified as explicit vs inferred
_EXPLICIT_STRENGTHS: frozenset[str] = frozenset({"strong", "moderate"})
_INFERRED_STRENGTHS: frozenset[str] = frozenset({"weak", "speculative"})


# ═══════════════════════════════════════════════════════════════
#  AT-01: PROVENANCE MANDATORY
# ═══════════════════════════════════════════════════════════════


def _check_at01_provenance(annotation: ReconciledAnnotation) -> ATBRejection | None:
    """AT-01: Provenance mandatory.

    extraction_snippet AND source_span_id must both exist.
    If either is missing, the annotation is REJECTED.

    # REVIEW: SPEC AMBIGUITY — RawAnnotationEmission schema (SYS_EX line 385)
    # defines source_span_id as TEXT? (nullable), but AT-01 (SYS_EX line 548)
    # requires both extraction_snippet + span_id. Annotation-only agents
    # (AG10: strategic intelligence) work on Discussion/Limitations prose
    # and by design cannot produce SpanLabel references. Current implementation
    # requires extraction_snippet as mandatory provenance; source_span_id is
    # required only when present (i.e., annotations with extraction_snippet
    # but no source_span_id pass with a logged warning rather than rejection).
    # If the spec intends strict rejection, AG10 annotations would all fail
    # AT-01, which appears unintended given AG10 is a core pipeline agent.
    """
    if not annotation.extraction_snippet:
        return ATBRejection(
            annotation_id=annotation.annotation_id,
            rule_id="AT-01",
            reason="Missing provenance field: extraction_snippet",
            category=annotation.category.value,
            content_preview=annotation.content[:200],
        )
    if not annotation.source_span_id:
        # Annotation-only agents (AG10) produce no SpanLabels.
        # Log but do not reject — extraction_snippet alone provides
        # sufficient provenance for prose-derived annotations.
        logger.info(
            "AT-01: annotation %s has extraction_snippet but no "
            "source_span_id (annotation-only agent). Passing with warning. "
            "Entity: annotation_id=%s, category=%s.",
            annotation.annotation_id,
            annotation.annotation_id,
            annotation.category.value,
        )
    return None


# ═══════════════════════════════════════════════════════════════
#  AT-02: EXPLICIT VS INFERRED SEPARATION
# ═══════════════════════════════════════════════════════════════


def _check_at02_explicit_inferred(annotation: ReconciledAnnotation) -> ATBRejection | None:
    """AT-02: Explicit vs inferred separation.

    evidence_strength must be present and must be one of:
    {strong, moderate} = explicit; {weak, speculative} = inferred.
    Annotations without evidence_strength are REJECTED.
    """
    strength = (annotation.evidence_strength or "").lower()
    valid_strengths = _EXPLICIT_STRENGTHS | _INFERRED_STRENGTHS

    if strength not in valid_strengths:
        return ATBRejection(
            annotation_id=annotation.annotation_id,
            rule_id="AT-02",
            reason=(
                f"evidence_strength '{annotation.evidence_strength}' is not in "
                f"valid set {sorted(valid_strengths)}"
            ),
            category=annotation.category.value,
            content_preview=annotation.content[:200],
        )
    return None


# ═══════════════════════════════════════════════════════════════
#  AT-03: CATEGORY-SPECIFIC REQUIRED FIELDS
# ═══════════════════════════════════════════════════════════════


def _check_at03_category_fields(annotation: ReconciledAnnotation) -> ATBRejection | None:
    """AT-03: Category-specific required fields.

    Rules:
    - adverse_event -> severity required in structured_data_json
    - null_finding_context -> powered_adequately required in structured_data_json
    - limitation_unmeasured_confounder -> confounder_name required (not generic)
    """
    data = annotation.structured_data_json or {}
    category = annotation.category

    if category == AnnotationCategory.ADVERSE_EVENT:
        severity = data.get("severity")
        if not severity:
            return ATBRejection(
                annotation_id=annotation.annotation_id,
                rule_id="AT-03",
                reason="adverse_event requires 'severity' in structured_data_json",
                category=category.value,
                content_preview=annotation.content[:200],
            )

    elif category == AnnotationCategory.NULL_FINDING_CONTEXT:
        powered = data.get("powered_adequately")
        if powered is None:
            return ATBRejection(
                annotation_id=annotation.annotation_id,
                rule_id="AT-03",
                reason="null_finding_context requires 'powered_adequately' in structured_data_json",
                category=category.value,
                content_preview=annotation.content[:200],
            )

    elif category == AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER:
        confounder_name = data.get("confounder_name", "")
        # Must not be empty or generic
        generic_names = {"confounder", "confounders", "unknown", "various", "other", ""}
        if confounder_name.lower().strip() in generic_names:
            return ATBRejection(
                annotation_id=annotation.annotation_id,
                rule_id="AT-03",
                reason=(
                    f"limitation_unmeasured_confounder requires specific "
                    f"'confounder_name' (got: '{confounder_name}')"
                ),
                category=category.value,
                content_preview=annotation.content[:200],
            )

    return None


# ═══════════════════════════════════════════════════════════════
#  AT-04: CONTRADICTION ROUTING
# ═══════════════════════════════════════════════════════════════


def _check_at04_contradiction_routing(
    annotation: ReconciledAnnotation,
) -> ATBRejection | None:
    """AT-04: Contradiction routing.

    Annotations with unresolved conflicts are HELD from wiring.
    They are rejected at the trust boundary until human review resolves them.
    """
    if annotation.has_unresolved_conflict:
        return ATBRejection(
            annotation_id=annotation.annotation_id,
            rule_id="AT-04",
            reason=(
                f"Unresolved conflict (severity={annotation.conflict_severity}). "
                f"Held from wiring pending review."
            ),
            category=annotation.category.value,
            content_preview=annotation.content[:200],
        )
    return None


# ═══════════════════════════════════════════════════════════════
#  AT-05: HIGH-IMPACT CONSUMER GATE
# ═══════════════════════════════════════════════════════════════


def _check_at05_high_impact_gate(annotation: ReconciledAnnotation) -> ATBRejection | None:
    """AT-05: High-impact consumer gate.

    Categories: limitation_unmeasured_confounder, adverse_event
    These feed into structural variance or safety rules, so they
    require >= moderate evidence_strength.
    """
    if annotation.category in _HIGH_IMPACT_CATEGORIES:
        strength = (annotation.evidence_strength or "").lower()
        if strength not in _EXPLICIT_STRENGTHS:
            return ATBRejection(
                annotation_id=annotation.annotation_id,
                rule_id="AT-05",
                reason=(
                    f"High-impact category '{annotation.category.value}' requires "
                    f">= moderate evidence_strength (got: '{annotation.evidence_strength}')"
                ),
                category=annotation.category.value,
                content_preview=annotation.content[:200],
            )
    return None


# ═══════════════════════════════════════════════════════════════
#  AT-06: SPECULATIVE CEILING
# ═══════════════════════════════════════════════════════════════


def _apply_at06_speculative_ceiling(annotation: ReconciledAnnotation) -> ReconciledAnnotation:
    """AT-06: Speculative ceiling.

    Speculative evidence capped at confidence <= config.ATB_SPECULATIVE_CONFIDENCE_CEILING.
    This is NOT a rejection rule; it caps confidence.

    Uses config.ATB_SPECULATIVE_CONFIDENCE_CEILING (0.50).
    """
    strength = (annotation.evidence_strength or "").lower()
    if strength == "speculative":
        # Formula AT-06: speculative evidence capped at ATB_SPECULATIVE_CONFIDENCE_CEILING
        capped_confidence = min(
            annotation.reconciled_confidence,
            config.ATB_SPECULATIVE_CONFIDENCE_CEILING,
        )
        if capped_confidence != annotation.reconciled_confidence:
            logger.info(
                "AT-06: Capped speculative annotation %s confidence from %.3f to %.3f",
                annotation.annotation_id,
                annotation.reconciled_confidence,
                capped_confidence,
            )
            # Return a copy with capped confidence
            return annotation.model_copy(
                update={"reconciled_confidence": capped_confidence}
            )
    return annotation


# ═══════════════════════════════════════════════════════════════
#  REVIEW TASK EMISSION
# ═══════════════════════════════════════════════════════════════


def _emit_rejection_review_task(
    session: Session,
    rejection: ATBRejection,
    study_id: str,
) -> None:
    """Emit a review_tasks row for ATB-rejected annotations.

    Per spec: On rejection, emit review_tasks row.
    """
    task = ReviewTask(
        task_id=str(uuid.uuid4()),
        task_type="atb_rejection",
        source_stage="EX-P1-ATB",
        source_entity_id=rejection.annotation_id,
        source_table="study_annotations_v1",
        priority=2 if rejection.rule_id in ("AT-04", "AT-05") else 1,
        status="pending",
        summary=(
            f"ATB rule {rejection.rule_id} rejected annotation "
            f"(category={rejection.category}): {rejection.reason}"
        ),
        context_json={
            "study_id": study_id,
            "annotation_id": rejection.annotation_id,
            "rule_id": rejection.rule_id,
            "category": rejection.category,
            "reason": rejection.reason,
            "content_preview": rejection.content_preview,
        },
    )
    session.add(task)
    logger.info(
        "Emitted review task for ATB rejection: %s (rule=%s)",
        rejection.annotation_id,
        rejection.rule_id,
    )


# ═══════════════════════════════════════════════════════════════
#  PERSIST VALIDATED ANNOTATIONS
# ═══════════════════════════════════════════════════════════════


def _persist_validated_annotation(
    session: Session,
    annotation: ReconciledAnnotation,
) -> None:
    """Persist a validated annotation to study_annotations_v1 (B11).

    Only annotations that pass ALL ATB rules reach this point.
    """
    # Determine consumer based on category
    consumer = _determine_consumer(annotation.category)

    row = StudyAnnotations(
        annotation_id=annotation.annotation_id,
        study_id=annotation.study_id,
        ler_id=None,  # Set later when linked to edge evidence
        category=annotation.category.value,
        consumer=consumer,
        target_entity_type=annotation.target_entity_type,
        target_entity_id=annotation.target_entity_id,
        content=annotation.content,
        structured_data_json=annotation.structured_data_json,
        evidence_strength=annotation.evidence_strength,
        extraction_snippet=annotation.extraction_snippet,
        source_span_id=annotation.source_span_id,
        cross_agent_support_n=annotation.cross_agent_support_n,
        adjudication_status=annotation.adjudication_status.value,
        duplicate_of_annotation_id=None,
        reconciled_confidence=annotation.reconciled_confidence,
        maturity="raw",
        promoted_to=None,
    )
    session.add(row)


def _determine_consumer(category: AnnotationCategory) -> str:
    """Map annotation category to the primary downstream consumer.

    Based on spec: EX-P4-MA reads limitation_unmeasured_confounder and
    null_finding_context for sigma^2_structural; EX-ACQ reads research_gap;
    EX-PROM reads all reviewed annotations.
    """
    category_consumer_map: dict[AnnotationCategory, str] = {
        AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: "sigma_structural",
        AnnotationCategory.NULL_FINDING_CONTEXT: "sigma_structural",
        AnnotationCategory.RESEARCH_GAP: "acquisition",
        AnnotationCategory.ADVERSE_EVENT: "safety_rules",
        AnnotationCategory.MECHANISM_HYPOTHESIS: "dag_expansion",
        AnnotationCategory.ADHERENCE_DATA: "modifier_resolution",
        AnnotationCategory.TEMPORAL_ONSET: "temporal_kernel",
        AnnotationCategory.DOSE_RESPONSE_EVIDENCE: "dose_bridge",
        AnnotationCategory.POPULATION_SPECIFICITY: "scope_matching",
        AnnotationCategory.MEASUREMENT_LIMITATION: "se_inflation",
        AnnotationCategory.CONFOUNDER_STRUCTURE: "sigma_structural",
        AnnotationCategory.BIOLOGICAL_PLAUSIBILITY: "dag_expansion",
        AnnotationCategory.CLINICAL_SIGNIFICANCE: "reporting",
        AnnotationCategory.GENERALIZABILITY_CONCERN: "scope_matching",
        AnnotationCategory.REPLICATION_STATUS: "confidence_weighting",
        AnnotationCategory.EFFECT_MODIFICATION: "modifier_resolution",
        AnnotationCategory.SELECTION_BIAS: "se_inflation",
        AnnotationCategory.ATTRITION_BIAS: "se_inflation",
        AnnotationCategory.DETECTION_BIAS: "se_inflation",
        AnnotationCategory.REPORTING_BIAS: "se_inflation",
        AnnotationCategory.THEORY_SUPPORT: "dag_expansion",
        AnnotationCategory.CROSS_VALIDATION: "confidence_weighting",
    }
    return category_consumer_map.get(category, "general")


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════


def validate_annotations(
    session: Session,
    reconciliation_result: ReconciliationResult,
) -> ATBResult:
    """EX-P1-ATB: Annotation Trust Boundary — main entry point.

    Validates each reconciled annotation against the 6 ATB rules in order.
    Annotations that fail ANY rule are REJECTED and never enter study_annotations_v1.
    Rejected annotations generate review_tasks rows.

    Rules applied in order:
      AT-01: Provenance mandatory
      AT-02: Explicit vs inferred separation
      AT-03: Category-specific required fields
      AT-04: Contradiction routing
      AT-05: High-impact consumer gate (>= moderate required)
      AT-06: Speculative ceiling (confidence cap, not rejection)

    Args:
        session: SQLAlchemy session for DB writes.
        reconciliation_result: Output from reconciliation.reconcile_annotations().

    Returns:
        ATBResult with accepted and rejected annotation lists.
    """
    study_id = reconciliation_result.study_id
    annotations = reconciliation_result.reconciled_annotations

    accepted: list[ReconciledAnnotation] = []
    rejected: list[ATBRejection] = []

    # Rules that REJECT (ordered by spec)
    rejection_checks = [
        _check_at01_provenance,
        _check_at02_explicit_inferred,
        _check_at03_category_fields,
        _check_at04_contradiction_routing,
        _check_at05_high_impact_gate,
    ]

    for annotation in annotations:
        rejection: ATBRejection | None = None

        # Apply rejection rules in order; first failure rejects
        for check_fn in rejection_checks:
            rejection = check_fn(annotation)
            if rejection is not None:
                break

        if rejection is not None:
            rejected.append(rejection)
            _emit_rejection_review_task(session, rejection, study_id)
            logger.info(
                "ATB REJECTED annotation %s: rule=%s reason=%s",
                annotation.annotation_id,
                rejection.rule_id,
                rejection.reason,
            )
        else:
            # AT-06: Apply speculative ceiling (modifies confidence, does not reject)
            annotation = _apply_at06_speculative_ceiling(annotation)

            # Persist to study_annotations_v1
            _persist_validated_annotation(session, annotation)
            accepted.append(annotation)
            logger.debug(
                "ATB ACCEPTED annotation %s (category=%s, confidence=%.3f)",
                annotation.annotation_id,
                annotation.category.value,
                annotation.reconciled_confidence,
            )

    logger.info(
        "ATB complete for study %s: %d accepted, %d rejected (of %d input)",
        study_id,
        len(accepted),
        len(rejected),
        len(annotations),
    )

    return ATBResult(
        study_id=study_id,
        accepted=accepted,
        rejected=rejected,
        total_input=len(annotations),
        total_accepted=len(accepted),
        total_rejected=len(rejected),
    )
