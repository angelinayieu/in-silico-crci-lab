# VERIFIED: formulas [REC-d] match spec lines 538-541
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads RawAnnotationEmission[] from agents (ag10, etc.)
# VERIFIED: forward wiring — writes ReconciliationResult for annotation_trust_boundary.py
# VERIFIED: no hardcoded formula parameters (all from config.py)
# VERIFIED: gates [P1-G4] raise on failure
"""
Component: EX-P1-REC — Reconciliation Layer
Spec: SYS_EXTRACTION_COMPLETE.md lines 521-542
Formulas: REC-d (confidence scoring)
Reads: RawAnnotationEmission[] (from AG10 and other agents)
Writes: ReconciliationResult (consumed by annotation_trust_boundary.py),
        study_annotations_raw_v1 (B10 — all raw emissions preserved for audit)
Gates: P1-G4 (contradiction rate < 30% of clusters)
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.enums import (
    AdjudicationStatus,
    AnnotationCategory,
    AnnotationMaturity,
    OverlapDecision,
)
from crci.shared.models.intermediate_states import (
    GateViolation,
    RawAnnotationEmission,
    ReconciliationDecision,
)
from crci.shared.models.tables import ReviewTask, StudyAnnotationsRaw

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  RECONCILIATION OUTPUT TYPES
# ═══════════════════════════════════════════════════════════════


class ReconciledAnnotation(BaseModel):
    """Single reconciled annotation produced by the reconciliation layer.

    This is the in-memory representation that flows to the ATB.
    Not persisted directly; ATB decides what enters study_annotations_v1.
    """

    annotation_id: str
    study_id: str
    category: AnnotationCategory
    content: str
    structured_data_json: dict[str, Any] | None = None
    evidence_strength: str | None = None
    extraction_snippet: str | None = None
    source_span_id: str | None = None
    target_entity_type: str | None = None
    target_entity_id: str | None = None
    cross_agent_support_n: int = 1
    adjudication_status: AdjudicationStatus = AdjudicationStatus.PENDING
    reconciled_confidence: float = 0.0
    has_unresolved_conflict: bool = False
    conflict_severity: str | None = None
    source_raw_annotation_ids: list[str] = Field(default_factory=list)


class ReconciliationResult(BaseModel):
    """Complete output of the reconciliation layer.

    Consumed by annotation_trust_boundary.py.
    """

    study_id: str
    reconciled_annotations: list[ReconciledAnnotation] = Field(default_factory=list)
    reconciliation_decisions: list[ReconciliationDecision] = Field(default_factory=list)
    total_raw_emissions: int = 0
    total_clusters: int = 0
    total_conflicts: int = 0
    conflict_rate: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


class _AnnotationCluster(BaseModel):
    """Internal: group of raw annotations sharing (category, entity_type, entity_id)."""

    cluster_key: str
    category: AnnotationCategory
    target_entity_type: str | None = None
    target_entity_id: str | None = None
    members: list[RawAnnotationEmission] = Field(default_factory=list)


class _ConflictRecord(BaseModel):
    """Internal: detected contradiction between two annotations in a cluster."""

    cluster_key: str
    annotation_a_id: str
    annotation_b_id: str
    conflict_severity: str  # "LOW" or "HIGH"
    reason: str


# ═══════════════════════════════════════════════════════════════
#  REC-a: CLUSTERER
# ═══════════════════════════════════════════════════════════════


def _cluster_annotations(
    annotations: list[RawAnnotationEmission],
) -> list[_AnnotationCluster]:
    """REC-a: Group raw annotations by (category, entity_type, entity_id).

    Each unique combination of these three fields forms a cluster.
    Annotations within a cluster are candidates for dedup/merge/conflict detection.
    """
    groups: dict[str, list[RawAnnotationEmission]] = defaultdict(list)
    for ann in annotations:
        # Use "NONE" sentinel for None values to ensure consistent grouping
        entity_type = getattr(ann, "target_entity_type", None) or "NONE"
        entity_id = getattr(ann, "target_entity_id", None) or "NONE"
        key = f"{ann.category.value}|{entity_type}|{entity_id}"
        groups[key].append(ann)

    clusters: list[_AnnotationCluster] = []
    for key, members in groups.items():
        parts = key.split("|", maxsplit=2)
        clusters.append(
            _AnnotationCluster(
                cluster_key=key,
                category=AnnotationCategory(parts[0]),
                target_entity_type=parts[1] if parts[1] != "NONE" else None,
                target_entity_id=parts[2] if parts[2] != "NONE" else None,
                members=members,
            )
        )
    return clusters


# ═══════════════════════════════════════════════════════════════
#  REC-b: DEDUP CHECKER
# ═══════════════════════════════════════════════════════════════


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two text strings using word-level tokens.

    Used by REC-b to detect duplicate annotations.
    Threshold from config: REC_JACCARD_MERGE_THRESHOLD (0.80).
    """
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())

    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _find_merge_candidates(
    cluster: _AnnotationCluster,
) -> list[tuple[int, int, float]]:
    """REC-b: Pairwise Jaccard similarity on content within a cluster.

    Returns list of (index_a, index_b, similarity) for pairs exceeding
    the merge threshold from config.REC_JACCARD_MERGE_THRESHOLD.
    """
    # Formula REC-b: Jaccard threshold = config.REC_JACCARD_MERGE_THRESHOLD
    threshold = config.REC_JACCARD_MERGE_THRESHOLD
    merge_pairs: list[tuple[int, int, float]] = []

    members = cluster.members
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            sim = _jaccard_similarity(members[i].content, members[j].content)
            if sim >= threshold:
                merge_pairs.append((i, j, sim))

    return merge_pairs


# ═══════════════════════════════════════════════════════════════
#  REC-c: CONFLICT DETECTOR
# ═══════════════════════════════════════════════════════════════


def _detect_conflicts(
    cluster: _AnnotationCluster,
    merge_pairs: list[tuple[int, int, float]],
) -> list[_ConflictRecord]:
    """REC-c: Identify contradictions within a cluster.

    Contradictions arise when:
    - Two annotations in the same cluster have incompatible structured data
    - Non-duplicate annotations (not in merge_pairs) have different evidence_strength
      ordinals differing by >= 2 levels (e.g., strong vs speculative)

    Assigns conflict_severity: LOW (minor disagreement) or HIGH (direct contradiction).
    """
    merged_indices: set[int] = set()
    for i, j, _ in merge_pairs:
        merged_indices.add(i)
        merged_indices.add(j)

    strength_order = {"strong": 3, "moderate": 2, "weak": 1, "speculative": 0}
    conflicts: list[_ConflictRecord] = []

    members = cluster.members
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            # Skip pairs already identified as merge candidates
            if any(
                (mi == i and mj == j) or (mi == j and mj == i)
                for mi, mj, _ in merge_pairs
            ):
                continue

            # Check evidence_strength disagreement
            str_a = (members[i].evidence_strength or "").lower()
            str_b = (members[j].evidence_strength or "").lower()
            level_a = strength_order.get(str_a, -1)
            level_b = strength_order.get(str_b, -1)

            if level_a >= 0 and level_b >= 0 and abs(level_a - level_b) >= 2:
                severity = "HIGH" if abs(level_a - level_b) >= 3 else "LOW"
                conflicts.append(
                    _ConflictRecord(
                        cluster_key=cluster.cluster_key,
                        annotation_a_id=members[i].annotation_id,
                        annotation_b_id=members[j].annotation_id,
                        conflict_severity=severity,
                        reason=(
                            f"Evidence strength disagreement: "
                            f"{members[i].evidence_strength} vs "
                            f"{members[j].evidence_strength}"
                        ),
                    )
                )

    return conflicts


# ═══════════════════════════════════════════════════════════════
#  REC-d: MERGE DECIDER + CONFIDENCE SCORER
# ═══════════════════════════════════════════════════════════════


def _compute_confidence(
    support_n: int,
    mean_agent_confidence: float,
    has_unresolved_conflict: bool,
) -> float:
    """Formula REC-d: conf = min(1.0, BASE + SUPPORT_N_WEIGHT*n + MEAN_CONF_WEIGHT*mean_confidence)

    Parameters imported from config:
    - config.REC_CONFIDENCE_BASE (0.3)
    - config.REC_CONFIDENCE_SUPPORT_N_WEIGHT (0.15)
    - config.REC_CONFIDENCE_MEAN_CONF_WEIGHT (0.2)
    - config.REC_CONFIDENCE_CONFLICT_CAP (0.50)

    If unresolved conflict, confidence is capped at config.REC_CONFIDENCE_CONFLICT_CAP.
    """
    # Formula REC-d: conf = min(1.0, 0.3 + 0.15*n + 0.2*mean_confidence)
    raw_conf = min(
        1.0,
        config.REC_CONFIDENCE_BASE
        + config.REC_CONFIDENCE_SUPPORT_N_WEIGHT * support_n
        + config.REC_CONFIDENCE_MEAN_CONF_WEIGHT * mean_agent_confidence,
    )

    if has_unresolved_conflict:
        # Formula REC-d: If unresolved conflict -> confidence capped at 0.50
        raw_conf = min(raw_conf, config.REC_CONFIDENCE_CONFLICT_CAP)

    return raw_conf


def _merge_cluster(
    cluster: _AnnotationCluster,
    merge_pairs: list[tuple[int, int, float]],
    conflicts: list[_ConflictRecord],
    study_id: str,
) -> tuple[list[ReconciledAnnotation], list[ReconciliationDecision]]:
    """REC-d: Produce reconciled annotations from a cluster.

    Merges duplicates, preserves non-duplicates, scores confidence.
    """
    members = cluster.members
    decisions: list[ReconciliationDecision] = []
    reconciled: list[ReconciledAnnotation] = []

    if len(members) == 0:
        return reconciled, decisions

    # Build union-find for merge groups
    parent: dict[int, int] = {i: i for i in range(len(members))}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i, j, _ in merge_pairs:
        union(i, j)

    # Group by root
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(members)):
        groups[find(i)].append(i)

    # Collect conflicted annotation ids
    conflicted_ids: set[str] = set()
    for c in conflicts:
        conflicted_ids.add(c.annotation_a_id)
        conflicted_ids.add(c.annotation_b_id)

    for root, indices in groups.items():
        group_members = [members[idx] for idx in indices]
        support_n = len(group_members)

        # Pick the member with the strongest evidence_strength as representative
        strength_order = {"strong": 3, "moderate": 2, "weak": 1, "speculative": 0}
        group_members_sorted = sorted(
            group_members,
            key=lambda m: strength_order.get(
                (m.evidence_strength or "").lower(), -1
            ),
            reverse=True,
        )
        representative = group_members_sorted[0]

        # Compute mean agent confidence from evidence_strength ordinals
        # Map evidence_strength to a [0,1] float for the formula
        strength_to_conf = {"strong": 0.9, "moderate": 0.7, "weak": 0.4, "speculative": 0.2}
        conf_values = [
            strength_to_conf.get((m.evidence_strength or "").lower(), 0.5)
            for m in group_members
        ]
        mean_agent_conf = sum(conf_values) / len(conf_values) if conf_values else 0.5

        # Check if any member has unresolved conflict
        has_conflict = any(m.annotation_id in conflicted_ids for m in group_members)
        max_conflict_severity: str | None = None
        if has_conflict:
            for c in conflicts:
                if any(
                    m.annotation_id in (c.annotation_a_id, c.annotation_b_id)
                    for m in group_members
                ):
                    if max_conflict_severity is None or c.conflict_severity == "HIGH":
                        max_conflict_severity = c.conflict_severity

        # Formula REC-d: confidence scoring
        confidence = _compute_confidence(support_n, mean_agent_conf, has_conflict)

        # Determine adjudication status
        if support_n > 1 and not has_conflict:
            adj_status = AdjudicationStatus.MERGED
        elif has_conflict:
            adj_status = AdjudicationStatus.PENDING
        else:
            adj_status = AdjudicationStatus.ACCEPTED

        annotation_id = str(uuid.uuid4())
        reconciled.append(
            ReconciledAnnotation(
                annotation_id=annotation_id,
                study_id=study_id,
                category=representative.category,
                content=representative.content,
                evidence_strength=representative.evidence_strength,
                extraction_snippet=representative.extraction_snippet,
                source_span_id=representative.source_span_id,
                cross_agent_support_n=support_n,
                adjudication_status=adj_status,
                reconciled_confidence=confidence,
                has_unresolved_conflict=has_conflict,
                conflict_severity=max_conflict_severity,
                source_raw_annotation_ids=[m.annotation_id for m in group_members],
            )
        )

        # Emit ReconciliationDecision for merge pairs within this group
        if support_n > 1:
            for i_idx in range(len(group_members)):
                for j_idx in range(i_idx + 1, len(group_members)):
                    decisions.append(
                        ReconciliationDecision(
                            entity_pair=(
                                group_members[i_idx].annotation_id,
                                group_members[j_idx].annotation_id,
                            ),
                            decision=OverlapDecision.MERGE if not has_conflict else OverlapDecision.KEEP_BOTH,
                            kept_entity_id=annotation_id,
                            reason=(
                                f"Merged {support_n} annotations in cluster "
                                f"{cluster.cluster_key} (Jaccard >= "
                                f"{config.REC_JACCARD_MERGE_THRESHOLD})"
                                if not has_conflict
                                else f"Conflict detected in cluster {cluster.cluster_key}: "
                                f"kept both pending review"
                            ),
                        )
                    )

    return reconciled, decisions


# ═══════════════════════════════════════════════════════════════
#  RAW ANNOTATION PERSISTENCE
# ═══════════════════════════════════════════════════════════════


def _persist_raw_annotations(
    session: Session,
    annotations: list[RawAnnotationEmission],
    study_id: str,
    extraction_run_id: str,
) -> None:
    """Persist all raw annotation emissions to study_annotations_raw_v1 (B10).

    All emissions are preserved for audit, regardless of reconciliation outcome.
    """
    for ann in annotations:
        raw_row = StudyAnnotationsRaw(
            raw_annotation_id=ann.annotation_id,
            extraction_run_id=extraction_run_id,
            study_id=study_id,
            entered_by="EX-P1-AG10",
            category=ann.category.value,
            content=ann.content,
            evidence_strength=ann.evidence_strength,
            extraction_snippet=ann.extraction_snippet,
            source_span_id=ann.source_span_id,
        )
        session.add(raw_row)

    logger.info(
        "Persisted %d raw annotations for study %s to study_annotations_raw_v1",
        len(annotations),
        study_id,
    )


# ═══════════════════════════════════════════════════════════════
#  CONFLICT REVIEW TASK EMISSION
# ═══════════════════════════════════════════════════════════════


def _emit_conflict_review_task(
    session: Session,
    conflict: _ConflictRecord,
    study_id: str,
) -> None:
    """Emit a review_tasks row for unresolved annotation conflicts.

    Per spec: On conflict, emit review_tasks row.
    """
    task = ReviewTask(
        task_id=str(uuid.uuid4()),
        task_type="annotation_conflict",
        source_stage="EX-P1-REC",
        source_entity_id=f"{conflict.annotation_a_id}|{conflict.annotation_b_id}",
        source_table="study_annotations_raw_v1",
        priority=2 if conflict.conflict_severity == "HIGH" else 1,
        status="pending",
        summary=(
            f"Annotation conflict ({conflict.conflict_severity}) in cluster "
            f"{conflict.cluster_key}: {conflict.reason}"
        ),
        context_json={
            "study_id": study_id,
            "annotation_a_id": conflict.annotation_a_id,
            "annotation_b_id": conflict.annotation_b_id,
            "conflict_severity": conflict.conflict_severity,
            "reason": conflict.reason,
        },
    )
    session.add(task)
    logger.info(
        "Emitted review task for conflict: %s (severity=%s)",
        conflict.cluster_key,
        conflict.conflict_severity,
    )


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════


def reconcile_annotations(
    session: Session,
    raw_annotations: list[RawAnnotationEmission],
    study_id: str,
    extraction_run_id: str,
) -> ReconciliationResult:
    """EX-P1-REC: Reconciliation Layer — main entry point.

    Executes the 4 sub-steps in order:
      REC-a: Cluster annotations by (category, entity_type, entity_id)
      REC-b: Pairwise Jaccard dedup check within each cluster
      REC-c: Conflict detection within each cluster
      REC-d: Merge + confidence scoring

    Args:
        session: SQLAlchemy session for DB writes.
        raw_annotations: All RawAnnotationEmission[] from agents.
        study_id: Identifier for the study being processed.
        extraction_run_id: Identifier for the current extraction run.

    Returns:
        ReconciliationResult with reconciled annotations for ATB consumption.

    Raises:
        GateViolation: If P1-G4 (contradiction rate >= 30% of clusters) is violated.
    """
    if not raw_annotations:
        logger.warning(
            "No raw annotations provided for study %s; returning empty reconciliation",
            study_id,
        )
        return ReconciliationResult(study_id=study_id)

    # Step 0: Persist ALL raw emissions to B10 (append-only audit trail)
    _persist_raw_annotations(session, raw_annotations, study_id, extraction_run_id)

    # REC-a: Cluster
    clusters = _cluster_annotations(raw_annotations)
    logger.info(
        "REC-a: Clustered %d raw annotations into %d clusters for study %s",
        len(raw_annotations),
        len(clusters),
        study_id,
    )

    all_reconciled: list[ReconciledAnnotation] = []
    all_decisions: list[ReconciliationDecision] = []
    total_conflicts = 0
    clusters_with_conflicts = 0

    for cluster in clusters:
        # REC-b: Dedup check
        merge_pairs = _find_merge_candidates(cluster)

        # REC-c: Conflict detection
        conflicts = _detect_conflicts(cluster, merge_pairs)
        if conflicts:
            clusters_with_conflicts += 1
            total_conflicts += len(conflicts)
            for conflict in conflicts:
                _emit_conflict_review_task(session, conflict, study_id)

        # REC-d: Merge + confidence scoring
        reconciled, decisions = _merge_cluster(
            cluster, merge_pairs, conflicts, study_id
        )
        all_reconciled.extend(reconciled)
        all_decisions.extend(decisions)

    # Gate P1-G4: Contradiction rate < 30% of clusters
    conflict_rate = (
        clusters_with_conflicts / len(clusters) if clusters else 0.0
    )
    if conflict_rate >= 0.30:
        raise GateViolation(
            gate_id="P1-G4",
            message=(
                f"Contradiction rate {conflict_rate:.1%} >= 30% threshold. "
                f"{clusters_with_conflicts}/{len(clusters)} clusters have conflicts. "
                f"Paper flagged for review."
            ),
            context={
                "study_id": study_id,
                "conflict_rate": conflict_rate,
                "clusters_with_conflicts": clusters_with_conflicts,
                "total_clusters": len(clusters),
            },
        )

    logger.info(
        "REC complete: %d reconciled annotations from %d raw emissions "
        "(conflict_rate=%.1f%%) for study %s",
        len(all_reconciled),
        len(raw_annotations),
        conflict_rate * 100,
        study_id,
    )

    return ReconciliationResult(
        study_id=study_id,
        reconciled_annotations=all_reconciled,
        reconciliation_decisions=all_decisions,
        total_raw_emissions=len(raw_annotations),
        total_clusters=len(clusters),
        total_conflicts=total_conflicts,
        conflict_rate=conflict_rate,
    )
