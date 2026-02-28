# ASSUMPTIONS:
#   - edge_evidence_v1 and edge_relations_definitions_v1 are populated before audit.
#   - Gap reports include edge IDs that map to valid entries in EDGE_REGISTRY.
# TEST COVERAGE: None yet — needs tests/test_pathway_evidence_auditor.py
# REVIEW:
#   - Sufficiency thresholds are config-driven but may need tuning.
"""
Component: SYS_EXTRACTION.EX-ACQ.PathwayEvidenceAuditor
Spec: Master Spec §9.6 (Evidence Landscape Monitoring)
      AUTOMATED_RETRIEVAL_PLAN.md Part 8 (Feedback Loop)
Formulas: AUDIT-1 (sufficiency grade per edge)
          AUDIT-2 (gap priority score for acquisition targeting)
Reads: edge_evidence_v1, edge_relations_definitions_v1, pathways_v1,
       study_annotations_v1 (research_gap annotations)
Writes: In-memory GapReport (consumed by query_generator workstream priority)
Gates: None (informational module — no hard gates)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import json

from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import (
    EdgeEvidence,
    EdgeRelationsDefinition,
    Pathway,
    StudyAnnotations,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  OUTPUT MODELS
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EdgeGapReport:
    """Evidence gap report for a single edge relation."""

    edge_relation_id: str
    node_x_id: str
    node_y_id: str
    pathway_id: str | None
    k_total: int
    k_primary: int
    k_meta: int
    n_studies: int
    sufficiency_grade: str  # A, B, C, D, F
    has_research_gap_annotation: bool
    gap_priority_score: float  # 0.0-1.0


@dataclass
class LandscapeReport:
    """Full evidence landscape report across all pathways."""

    total_edges: int = 0
    grade_distribution: dict[str, int] = field(default_factory=dict)
    gaps: list[EdgeGapReport] = field(default_factory=list)
    top_priority_gaps: list[EdgeGapReport] = field(default_factory=list)
    mean_k: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  CORE AUDIT
# ═══════════════════════════════════════════════════════════════


def audit_evidence_landscape(
    session: Session,
    pathway_ids: list[str] | None = None,
    top_n_gaps: int = 20,
) -> LandscapeReport:
    """Audit the evidence landscape and identify priority gaps.

    Computes per-edge sufficiency grades and generates a prioritized
    list of edges needing more evidence. This feeds directly back
    into query_generator workstream priorities.

    Formula AUDIT-1 (sufficiency grade):
        k >= 10 → A (rich)
        k >= 5  → B (adequate)
        k >= 2  → C (sparse)
        k >= 1  → D (minimal)
        k == 0  → F (empty)

    Formula AUDIT-2 (gap priority score):
        gap_priority = w_sufficiency × (1 - k/10)
                     + w_pathway    × pathway_centrality
                     + w_research_gap × has_author_gap_annotation
        where:
            w_sufficiency = 0.50
            w_pathway     = 0.30
            w_research_gap = 0.20

    Args:
        session: Active database session.
        pathway_ids: Optional filter to specific pathways. None = all.
        top_n_gaps: Number of highest-priority gaps to return.

    Returns:
        LandscapeReport with grades, gaps, and priorities.
    """
    report = LandscapeReport()

    # Load all edge relations (optionally filtered by pathway)
    edge_rows = _load_edge_relations(session, pathway_ids)
    if not edge_rows:
        logger.warning("No edge relations found for audit")
        return report

    # Build edge→pathway reverse lookup
    edge_to_pathway = _build_edge_to_pathway(session)

    # Load evidence counts per edge
    evidence_counts = _load_evidence_counts(session)

    # Load research gap annotations per edge
    research_gaps = _load_research_gap_edges(session)

    # Compute per-edge gap reports
    grade_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    total_k = 0

    for edge in edge_rows:
        edge_id = edge.edge_relation_id
        counts = evidence_counts.get(edge_id, {"k_total": 0, "k_primary": 0, "k_meta": 0, "n_studies": 0})

        k_total = counts["k_total"]
        total_k += k_total

        # Formula AUDIT-1: sufficiency grade
        grade = _compute_sufficiency_grade(k_total)
        grade_dist[grade] = grade_dist.get(grade, 0) + 1

        has_gap = edge_id in research_gaps

        # Formula AUDIT-2: gap priority score
        priority = _compute_gap_priority(k_total, has_gap)

        gap_report = EdgeGapReport(
            edge_relation_id=edge_id,
            node_x_id=edge.node_x,
            node_y_id=edge.node_y,
            pathway_id=edge_to_pathway.get(edge_id),
            k_total=k_total,
            k_primary=counts["k_primary"],
            k_meta=counts["k_meta"],
            n_studies=counts["n_studies"],
            sufficiency_grade=grade,
            has_research_gap_annotation=has_gap,
            gap_priority_score=priority,
        )
        report.gaps.append(gap_report)

    # Sort by priority (highest first)
    report.gaps.sort(key=lambda g: g.gap_priority_score, reverse=True)
    report.top_priority_gaps = report.gaps[:top_n_gaps]

    report.total_edges = len(edge_rows)
    report.grade_distribution = grade_dist
    report.mean_k = total_k / max(len(edge_rows), 1)

    logger.info(
        "Evidence landscape audit: %d edges, grade distribution=%s, "
        "mean_k=%.1f, top gap priority=%.3f",
        report.total_edges,
        report.grade_distribution,
        report.mean_k,
        report.top_priority_gaps[0].gap_priority_score if report.top_priority_gaps else 0,
    )

    return report


def get_priority_edge_ids(
    session: Session,
    max_edges: int = 50,
) -> list[str]:
    """Get edge relation IDs with highest acquisition priority.

    Convenience function for query_generator to get the edges
    that most need new evidence.

    Args:
        session: Active database session.
        max_edges: Maximum number of edge IDs to return.

    Returns:
        List of edge_relation_id strings, sorted by priority.
    """
    landscape = audit_evidence_landscape(session, top_n_gaps=max_edges)
    return [g.edge_relation_id for g in landscape.top_priority_gaps]


# ═══════════════════════════════════════════════════════════════
#  FORMULAS
# ═══════════════════════════════════════════════════════════════


def _compute_sufficiency_grade(k_total: int) -> str:
    """Formula AUDIT-1: evidence sufficiency grade.

    k >= 10 → A (rich evidence base)
    k >= 5  → B (adequate for pooling)
    k >= 2  → C (sparse but usable)
    k >= 1  → D (minimal — single study)
    k == 0  → F (no evidence)
    """
    if k_total >= 10:
        return "A"
    if k_total >= 5:
        return "B"
    if k_total >= 2:
        return "C"
    if k_total >= 1:
        return "D"
    return "F"


def _compute_gap_priority(k_total: int, has_research_gap: bool) -> float:
    """Formula AUDIT-2: gap priority score for acquisition targeting.

    gap_priority = 0.50 × (1 - k/10)     # sufficiency gap weight
                 + 0.30 × 1.0             # pathway centrality (simplified)
                 + 0.20 × has_research_gap # author-identified gap

    Clamped to [0.0, 1.0].
    """
    # Sufficiency component: higher when k is low
    w_sufficiency = 0.50
    sufficiency_score = max(0.0, 1.0 - k_total / 10.0)

    # Pathway centrality: simplified to 1.0 for all edges
    # (full implementation would use graph centrality from Chain A)
    w_pathway = 0.30
    pathway_score = 1.0

    # Research gap annotation boost
    w_research_gap = 0.20
    gap_score = 1.0 if has_research_gap else 0.0

    priority = (
        w_sufficiency * sufficiency_score
        + w_pathway * pathway_score
        + w_research_gap * gap_score
    )
    return min(1.0, max(0.0, priority))


# ═══════════════════════════════════════════════════════════════
#  DATA LOADERS
# ═══════════════════════════════════════════════════════════════


def _build_edge_to_pathway(session: Session) -> dict[str, str | None]:
    """Build reverse lookup: edge_relation_id → pathway_id.

    pathways_v1.edge_relation_ids_json is a JSON array of edge IDs.
    We invert this to a dict for O(1) lookups.
    """
    mapping: dict[str, str | None] = {}
    stmt = select(Pathway.pathway_id, Pathway.edge_relation_ids_json)
    for row in session.execute(stmt).all():
        edge_ids_raw = row.edge_relation_ids_json
        if not edge_ids_raw:
            continue
        try:
            if isinstance(edge_ids_raw, str):
                edge_ids = json.loads(edge_ids_raw)
            else:
                edge_ids = edge_ids_raw
            for eid in edge_ids:
                mapping[eid] = row.pathway_id
        except (json.JSONDecodeError, TypeError):
            logger.debug("Could not parse edge_relation_ids_json for %s", row.pathway_id)
    return mapping


def _load_edge_relations(
    session: Session,
    pathway_ids: list[str] | None = None,
) -> list:
    """Load edge relation definitions, optionally filtered by pathway.

    Note: EdgeRelationsDefinition has node_x/node_y (not node_x_id/node_y_id)
    and does not have a pathway_id column — we derive it from pathways_v1.
    """
    stmt = select(
        EdgeRelationsDefinition.edge_relation_id,
        EdgeRelationsDefinition.node_x,
        EdgeRelationsDefinition.node_y,
    )
    rows = session.execute(stmt).all()

    if pathway_ids:
        # Filter to edges belonging to the requested pathways
        edge_to_pw = _build_edge_to_pathway(session)
        pw_set = set(pathway_ids)
        rows = [r for r in rows if edge_to_pw.get(r.edge_relation_id) in pw_set]

    return rows


def _load_evidence_counts(session: Session) -> dict[str, dict[str, int]]:
    """Load per-edge evidence counts from edge_evidence_v1."""
    stmt = (
        select(
            EdgeEvidence.edge_relation_id,
            func.count(EdgeEvidence.ler_id).filter(
                EdgeEvidence.active == 1
            ).label("k_total"),
            func.count(EdgeEvidence.ler_id).filter(
                and_(
                    EdgeEvidence.active == 1,
                    EdgeEvidence.meta_source_flag.is_(None),
                )
            ).label("k_primary"),
            func.count(EdgeEvidence.ler_id).filter(
                and_(
                    EdgeEvidence.active == 1,
                    EdgeEvidence.meta_source_flag == "POOLED_ESTIMATE",
                )
            ).label("k_meta"),
            func.count(func.distinct(EdgeEvidence.study_id)).filter(
                EdgeEvidence.active == 1
            ).label("n_studies"),
        )
        .group_by(EdgeEvidence.edge_relation_id)
    )

    results: dict[str, dict[str, int]] = {}
    for row in session.execute(stmt).all():
        results[row.edge_relation_id] = {
            "k_total": row.k_total,
            "k_primary": row.k_primary,
            "k_meta": row.k_meta,
            "n_studies": row.n_studies,
        }
    return results


def _load_research_gap_edges(session: Session) -> set[str]:
    """Load edge IDs that have research_gap annotations.

    Returns set of edge_relation_ids where at least one research_gap
    annotation exists from a domain expert paper.
    """
    stmt = (
        select(func.distinct(StudyAnnotations.target_entity_id))
        .where(
            and_(
                StudyAnnotations.category == "research_gap",
                StudyAnnotations.target_entity_type == "edge",
                StudyAnnotations.active.is_(True),
            )
        )
    )
    return {row[0] for row in session.execute(stmt).all() if row[0]}
