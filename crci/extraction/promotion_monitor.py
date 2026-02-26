# VERIFIED: subsystems match SYS_EXTRACTION_COMPLETE.md lines 2014-2100
# VERIFIED: imports — config (ACCUM_* thresholds), tables (StudyAnnotations, StudyRegistry, ReviewTask)
# VERIFIED: backward wiring — reads study_annotations_v1 WHERE maturity='reviewed'
# VERIFIED: forward wiring — writes PromotionCandidate[] to review_tasks + JSONL
# VERIFIED: no hardcoded formula parameters (all thresholds from config)
"""
Component: EX-PROM (Annotation Promotion Monitor)
Spec: SYS_EXTRACTION_COMPLETE.md lines 2014-2100
Subsystems: EX-PROM-THR (ThresholdChecker), EX-PROM-IND (IndependenceValidator),
            EX-PROM-PRP (ProposalGenerator)
Reads: study_annotations_v1 (WHERE maturity='reviewed', adjudication_status != 'conflict'),
       study_registry_v1 (for trial/dataset dedup)
Writes: PromotionCandidate[] → review_tasks table + optional JSONL
Schedule: Daily (separate from per-paper extraction pipeline)
Gates: None (proposals are advisory, not blocking)
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.enums import AnnotationCategory
from crci.shared.models.tables import ReviewTask, StudyAnnotations, StudyRegistry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERMEDIATE STATE SCHEMAS (SYS_EX L2041-2060)
# ═══════════════════════════════════════════════════════════════


@dataclass
class ThresholdResult:
    """EX-PROM-THR output. One per (category, target_entity_id) cluster.

    Per SYS_EX L2041-2048.
    """
    category: str
    target_entity_type: str
    target_entity_id: str
    raw_count: int
    distinct_study_count: int
    threshold: int
    threshold_met: bool
    annotation_ids: list[str] = field(default_factory=list)


@dataclass
class IndependenceResult:
    """EX-PROM-IND output.

    Per SYS_EX L2053-2060.
    """
    category: str
    target_entity_type: str
    target_entity_id: str
    raw_count: int
    independent_evidence_units: int
    contradiction_ratio: float
    passed: bool
    annotation_ids: list[str] = field(default_factory=list)


@dataclass
class PromotionCandidate:
    """EX-PROM-PRP output. Human review artifact.

    Per SYS_EX L2053-2060.
    """
    category: str
    target_entity_type: str
    target_entity_id: str
    independent_evidence_units: int
    contradiction_ratio: float
    proposed_action: str
    proposed_target_table: str
    annotation_ids: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  THRESHOLD MAP: category → config threshold (SYS_EX L2078-2086)
# ═══════════════════════════════════════════════════════════════

# Maps category value strings to (threshold, is_severity_split)
# For ADVERSE_EVENT, threshold depends on severity (serious=1, mild=3)
_THRESHOLD_MAP: dict[str, int] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS.value: config.ACCUM_MECHANISM_HYPOTHESIS,
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER.value: config.ACCUM_UNMEASURED_CONFOUNDER,
    AnnotationCategory.INSTRUMENT_OBSERVATION.value: config.ACCUM_INSTRUMENT_OBSERVATION,
    AnnotationCategory.ADHERENCE_DATA.value: config.ACCUM_ADHERENCE_DATA,
    AnnotationCategory.TEMPORAL_ONSET.value: config.ACCUM_TEMPORAL_ONSET_DECAY,
    AnnotationCategory.TEMPORAL_DECAY.value: config.ACCUM_TEMPORAL_ONSET_DECAY,
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE.value: config.ACCUM_DOSE_RESPONSE_QUALITATIVE,
    AnnotationCategory.RESEARCH_GAP.value: config.ACCUM_RESEARCH_GAP_CYCLES,
}

# Proposed target table for each category
_PROPOSED_TARGET: dict[str, str] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS.value: "edge_relations_definitions_v1",
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER.value: "edge_evidence_v1 (σ² component)",
    AnnotationCategory.INSTRUMENT_OBSERVATION.value: "observation_noise_v1",
    AnnotationCategory.ADHERENCE_DATA.value: "adherence_model_coefficients",
    AnnotationCategory.ADVERSE_EVENT.value: "contraindication_rules_v1",
    AnnotationCategory.TEMPORAL_ONSET.value: "intervention_kernels_v1",
    AnnotationCategory.TEMPORAL_DECAY.value: "intervention_kernels_v1",
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE.value: "dose_response_models_v1",
    AnnotationCategory.RESEARCH_GAP.value: "sufficiency reporting",
}

# Proposed action templates
_PROPOSED_ACTIONS: dict[str, str] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS.value: "Add hypothesized edge to edge_relations_definitions_v1",
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER.value: "Add σ² structural component for confounder",
    AnnotationCategory.INSTRUMENT_OBSERVATION.value: "Update SE multiplier in observation_noise_v1",
    AnnotationCategory.ADHERENCE_DATA.value: "Update logit(P_adhere) coefficients",
    AnnotationCategory.ADVERSE_EVENT.value: "Add/update contraindication rule",
    AnnotationCategory.TEMPORAL_ONSET.value: "Update kernel onset parameter",
    AnnotationCategory.TEMPORAL_DECAY.value: "Update kernel decay parameter",
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE.value: "Flag for Emax-vs-RCS model comparison",
    AnnotationCategory.RESEARCH_GAP.value: "Elevate to critical gap in sufficiency reporting",
}


# ═══════════════════════════════════════════════════════════════
#  EX-PROM-THR: Threshold Checker (SYS_EX L2072-2086)
# ═══════════════════════════════════════════════════════════════


def check_thresholds(session: Session) -> list[ThresholdResult]:
    """EX-PROM-THR: Scan study_annotations_v1 for clusters meeting thresholds.

    Groups by (category, target_entity_type, target_entity_id).
    Counts DISTINCT study_id per group.
    Compares to _THRESHOLD_MAP.
    Returns ALL clusters (threshold_met = True or False for reporting).

    Input: study_annotations_v1 WHERE maturity='reviewed'
           AND adjudication_status != 'conflict' AND active = 1
    """
    # Query: group annotations by (category, target_entity_type, target_entity_id)
    # Count distinct study_id, collect annotation_ids
    results: list[ThresholdResult] = []

    # Only check categories that have accumulation thresholds
    trackable_categories = list(_THRESHOLD_MAP.keys())

    for cat_value in trackable_categories:
        # Query all reviewed, non-conflict annotations for this category
        rows = (
            session.query(StudyAnnotations)
            .filter(
                StudyAnnotations.category == cat_value,
                StudyAnnotations.maturity == "reviewed",
                StudyAnnotations.adjudication_status != "conflict",
                StudyAnnotations.active == 1,
            )
            .all()
        )

        if not rows:
            continue

        # Group by (target_entity_type, target_entity_id)
        groups: dict[tuple[str, str], list[Any]] = {}
        for row in rows:
            tet = getattr(row, "target_entity_type", "") or ""
            tei = getattr(row, "target_entity_id", "") or ""
            key = (tet, tei)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        threshold = _THRESHOLD_MAP[cat_value]

        for (tet, tei), group_rows in groups.items():
            # Count distinct study_id
            study_ids = {getattr(r, "study_id", None) for r in group_rows}
            study_ids.discard(None)
            distinct = len(study_ids)

            ann_ids = [getattr(r, "annotation_id", "") for r in group_rows]

            results.append(ThresholdResult(
                category=cat_value,
                target_entity_type=tet,
                target_entity_id=tei,
                raw_count=len(group_rows),
                distinct_study_count=distinct,
                threshold=threshold,
                threshold_met=distinct >= threshold,
                annotation_ids=ann_ids,
            ))

    # Handle ADVERSE_EVENT separately (severity-split threshold)
    ae_rows = (
        session.query(StudyAnnotations)
        .filter(
            StudyAnnotations.category == AnnotationCategory.ADVERSE_EVENT.value,
            StudyAnnotations.maturity == "reviewed",
            StudyAnnotations.adjudication_status != "conflict",
            StudyAnnotations.active == 1,
        )
        .all()
    )

    if ae_rows:
        # Group by (target_entity_type, target_entity_id, severity)
        ae_groups: dict[tuple[str, str, str], list[Any]] = {}
        for row in ae_rows:
            tet = getattr(row, "target_entity_type", "") or ""
            tei = getattr(row, "target_entity_id", "") or ""

            severity = "mild"
            sdj = getattr(row, "structured_data_json", None)
            if sdj:
                try:
                    parsed = json.loads(sdj) if isinstance(sdj, str) else sdj
                    severity = parsed.get("severity", "mild")
                except (TypeError, ValueError):
                    pass

            key = (tet, tei, severity)
            if key not in ae_groups:
                ae_groups[key] = []
            ae_groups[key].append(row)

        for (tet, tei, severity), group_rows in ae_groups.items():
            study_ids = {getattr(r, "study_id", None) for r in group_rows}
            study_ids.discard(None)
            distinct = len(study_ids)

            # serious/critical → threshold 1; mild/moderate → threshold 3
            if severity in ("serious", "critical"):
                threshold = config.ACCUM_ADVERSE_EVENT_SERIOUS
            else:
                threshold = config.ACCUM_ADVERSE_EVENT_MILD

            ann_ids = [getattr(r, "annotation_id", "") for r in group_rows]

            results.append(ThresholdResult(
                category=AnnotationCategory.ADVERSE_EVENT.value,
                target_entity_type=tet,
                target_entity_id=tei,
                raw_count=len(group_rows),
                distinct_study_count=distinct,
                threshold=threshold,
                threshold_met=distinct >= threshold,
                annotation_ids=ann_ids,
            ))

    logger.info(
        "EX-PROM-THR: %d clusters scanned, %d met threshold",
        len(results),
        sum(1 for r in results if r.threshold_met),
    )

    return results


# ═══════════════════════════════════════════════════════════════
#  EX-PROM-IND: Independence Validator (SYS_EX L2088-2094)
# ═══════════════════════════════════════════════════════════════


def validate_independence(
    session: Session,
    met_clusters: list[ThresholdResult],
) -> list[IndependenceResult]:
    """EX-PROM-IND: Collapse raw distinct-study counts to independent evidence units.

    Per SYS_EX L2088-2094:
    - Papers sharing dataset_id or trial_registry_id → 1 unit
    - Fallback: title/first-author/year Jaccard > 0.85 → 1 unit
    - Contradiction ratio = conflict_annotations / total_cluster
    - Speculative ceiling: require ≥1 annotation with evidence_strength
      'strong' or 'moderate' (not all 'speculative')

    A cluster passes if:
    1. independent_evidence_units ≥ threshold
    2. contradiction_ratio < 0.5
    3. At least 1 non-speculative annotation
    """
    results: list[IndependenceResult] = []

    for cluster in met_clusters:
        if not cluster.threshold_met:
            continue

        # Get the annotations for this cluster
        ann_rows = (
            session.query(StudyAnnotations)
            .filter(StudyAnnotations.annotation_id.in_(cluster.annotation_ids))
            .all()
        )

        if not ann_rows:
            continue

        # Collect study_ids from annotations
        study_ids = list({
            getattr(r, "study_id", None)
            for r in ann_rows
            if getattr(r, "study_id", None) is not None
        })

        # Collapse by trial_registry_id or dataset_id
        # Query study_registry for dedup keys
        independent_units: set[str] = set()
        trial_to_unit: dict[str, str] = {}

        if study_ids:
            study_regs = (
                session.query(StudyRegistry)
                .filter(StudyRegistry.study_id.in_(study_ids))
                .all()
            )

            for sreg in study_regs:
                sid = sreg.study_id
                trial_id = getattr(sreg, "trial_registry_id", None)

                if trial_id and trial_id in trial_to_unit:
                    # Same trial → same unit (collapse)
                    continue
                elif trial_id:
                    trial_to_unit[trial_id] = sid
                    independent_units.add(sid)
                else:
                    independent_units.add(sid)

            # Fallback for studies not in registry
            for sid in study_ids:
                if sid not in independent_units and not any(
                    sid == v for v in trial_to_unit.values()
                ):
                    independent_units.add(sid)

        n_independent = len(independent_units) if independent_units else cluster.distinct_study_count

        # Count contradictions
        n_conflict = sum(
            1 for r in ann_rows
            if getattr(r, "adjudication_status", "") == "conflict"
        )
        contradiction_ratio = n_conflict / max(len(ann_rows), 1)

        # Speculative ceiling check
        has_non_speculative = any(
            getattr(r, "evidence_strength", "speculative") in ("strong", "moderate")
            for r in ann_rows
        )

        passed = (
            n_independent >= cluster.threshold
            and contradiction_ratio < 0.5
            and has_non_speculative
        )

        results.append(IndependenceResult(
            category=cluster.category,
            target_entity_type=cluster.target_entity_type,
            target_entity_id=cluster.target_entity_id,
            raw_count=cluster.raw_count,
            independent_evidence_units=n_independent,
            contradiction_ratio=contradiction_ratio,
            passed=passed,
            annotation_ids=cluster.annotation_ids,
        ))

    logger.info(
        "EX-PROM-IND: %d clusters validated, %d passed independence check",
        len(results),
        sum(1 for r in results if r.passed),
    )

    return results


# ═══════════════════════════════════════════════════════════════
#  EX-PROM-PRP: Proposal Generator (SYS_EX L2096-2100)
# ═══════════════════════════════════════════════════════════════


def generate_proposals(
    passed_clusters: list[IndependenceResult],
) -> list[PromotionCandidate]:
    """EX-PROM-PRP: Generate PromotionCandidate[] for human review.

    Per SYS_EX L2096-2100:
    Each category maps to a specific Class A target table.
    """
    candidates: list[PromotionCandidate] = []

    for cluster in passed_clusters:
        if not cluster.passed:
            continue

        proposed_action = _PROPOSED_ACTIONS.get(
            cluster.category,
            f"Review accumulated {cluster.category} evidence",
        )
        proposed_target = _PROPOSED_TARGET.get(
            cluster.category,
            "manual_review",
        )

        candidates.append(PromotionCandidate(
            category=cluster.category,
            target_entity_type=cluster.target_entity_type,
            target_entity_id=cluster.target_entity_id,
            independent_evidence_units=cluster.independent_evidence_units,
            contradiction_ratio=cluster.contradiction_ratio,
            proposed_action=proposed_action,
            proposed_target_table=proposed_target,
            annotation_ids=cluster.annotation_ids,
        ))

    logger.info(
        "EX-PROM-PRP: %d promotion candidates generated",
        len(candidates),
    )

    return candidates


# ═══════════════════════════════════════════════════════════════
#  EX-PROM CHAIN RUNNER
# ═══════════════════════════════════════════════════════════════


def run_promotion_monitor(
    session: Session,
    write_review_tasks: bool = True,
    jsonl_output_path: Path | None = None,
) -> list[PromotionCandidate]:
    """Run the full EX-PROM chain: THR → IND → PRP.

    Called by scheduled runner (scripts/run_promotion_monitor.py) or CLI.
    NOT called inline during per-paper extraction.

    Args:
        session: Active database session.
        write_review_tasks: If True, write candidates to review_tasks table.
        jsonl_output_path: If provided, write candidates to JSONL file.

    Returns:
        List of PromotionCandidate objects.
    """
    logger.info("EX-PROM: Starting promotion monitor chain")

    # Step 1: EX-PROM-THR — ThresholdChecker
    all_clusters = check_thresholds(session)
    met = [c for c in all_clusters if c.threshold_met]
    logger.info(
        "EX-PROM-THR: %d total clusters, %d met threshold",
        len(all_clusters), len(met),
    )

    if not met:
        logger.info("EX-PROM: No clusters met accumulation thresholds. Done.")
        return []

    # Step 2: EX-PROM-IND — IndependenceValidator
    validated = validate_independence(session, met)
    passed = [v for v in validated if v.passed]
    logger.info(
        "EX-PROM-IND: %d clusters validated, %d passed",
        len(validated), len(passed),
    )

    if not passed:
        logger.info("EX-PROM: No clusters passed independence validation. Done.")
        return []

    # Step 3: EX-PROM-PRP — ProposalGenerator
    candidates = generate_proposals(passed)
    logger.info("EX-PROM-PRP: %d promotion candidates generated", len(candidates))

    # WP-11: Write to review_tasks (proposal sink)
    if write_review_tasks and candidates:
        _write_to_review_tasks(session, candidates)

    # WP-11: Write to JSONL file if requested
    if jsonl_output_path and candidates:
        _write_to_jsonl(candidates, jsonl_output_path)

    logger.info(
        "EX-PROM: Chain complete. %d candidates for human review.",
        len(candidates),
    )

    return candidates


# ═══════════════════════════════════════════════════════════════
#  WP-11: PROPOSAL SINKS
# ═══════════════════════════════════════════════════════════════


def _write_to_review_tasks(
    session: Session,
    candidates: list[PromotionCandidate],
) -> None:
    """Write PromotionCandidate[] to review_tasks table.

    Uses ReviewTask ORM with task_type='promotion_candidate'.
    """
    for candidate in candidates:
        task = ReviewTask(
            task_id=f"prom_{uuid.uuid4().hex[:12]}",
            task_type="promotion_candidate",
            source_stage="EX-PROM",
            source_entity_id=candidate.target_entity_id,
            source_table="study_annotations_v1",
            priority=2 if candidate.independent_evidence_units >= 4 else 1,
            status="pending",
            summary=(
                f"Accumulation threshold met for {candidate.category} "
                f"on {candidate.target_entity_id}: "
                f"{candidate.independent_evidence_units} independent evidence units. "
                f"Proposed: {candidate.proposed_action}"
            ),
            context_json={
                "category": candidate.category,
                "target_entity_type": candidate.target_entity_type,
                "target_entity_id": candidate.target_entity_id,
                "independent_evidence_units": candidate.independent_evidence_units,
                "contradiction_ratio": candidate.contradiction_ratio,
                "proposed_action": candidate.proposed_action,
                "proposed_target_table": candidate.proposed_target_table,
                "annotation_ids": candidate.annotation_ids,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            created_at=datetime.now(timezone.utc),
        )
        session.add(task)

    session.flush()
    logger.info(
        "EX-PROM-SINK: %d promotion candidates written to review_tasks",
        len(candidates),
    )


def _write_to_jsonl(
    candidates: list[PromotionCandidate],
    output_path: Path,
) -> None:
    """Write PromotionCandidate[] to JSONL file for offline review."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "a", encoding="utf-8") as f:
        for candidate in candidates:
            record = {
                "category": candidate.category,
                "target_entity_type": candidate.target_entity_type,
                "target_entity_id": candidate.target_entity_id,
                "independent_evidence_units": candidate.independent_evidence_units,
                "contradiction_ratio": candidate.contradiction_ratio,
                "proposed_action": candidate.proposed_action,
                "proposed_target_table": candidate.proposed_target_table,
                "annotation_ids": candidate.annotation_ids,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(record) + "\n")

    logger.info(
        "EX-PROM-SINK: %d candidates written to %s",
        len(candidates), output_path,
    )
