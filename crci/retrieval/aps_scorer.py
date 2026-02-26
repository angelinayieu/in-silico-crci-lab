# ASSUMPTIONS:
#   - CandidateMetadata is populated from search API responses.
#   - APS weights sum to 1.0 (enforced by config validation).
#   - Hop boost is additive, not multiplicative (spec: +0.15 delta).
# TEST COVERAGE: None yet — needs tests/test_aps_scorer.py
# REVIEW:
#   - _score_edge_gap defaults to 0.5 without gap context — this is a
#     generous assumption; real gap data requires populated edge tables.
#   - _score_source_quality uses citation counts only — journal impact
#     factor or h-index data not yet integrated.
"""
Component: SYS_EXTRACTION.EX-ACQ.APSScorer
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 3
      SYS_EXTRACTION_COMPLETE.md EX-ACQ-APS formula
Formulas: APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch
               + 0.15·Recency + 0.10·SourceQuality
          Author-gap boost: APS_final = min(1.0, APS × 1.5)
Reads: CandidateMetadata[] from search_coordinator
Writes: APSScoredCandidate[] for fulltext_retriever
Gates: APS >= APS_THRESHOLD → DISPATCH, else DEFER
"""
from __future__ import annotations

import logging
from datetime import datetime

from crci.shared import config
from crci.retrieval.models import (
    APSScoredCandidate,
    CandidateMetadata,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  APS COMPONENT SCORERS
# ═══════════════════════════════════════════════════════════════


def _score_edge_gap(
    candidate: CandidateMetadata,
    gap_edges: set[str] | None = None,
    target_entity_id: str | None = None,
) -> float:
    """Score edge gap component (0-1).

    Higher if the candidate targets an edge with insufficient evidence.
    """
    if gap_edges is None:
        # Without gap context, assume moderate gap
        return 0.5

    if target_entity_id and target_entity_id in gap_edges:
        return 1.0

    return 0.3


def _score_design_bonus(candidate: CandidateMetadata) -> float:
    """Score study design quality (0-1).

    Uses publication types and title/abstract keywords.
    """
    pub_types = " ".join(candidate.publication_types).lower()
    title = (candidate.title or "").lower()
    abstract_snippet = (candidate.abstract or "")[:500].lower()
    combined = f"{pub_types} {title} {abstract_snippet}"

    if "meta-analysis" in combined or "systematic review" in combined:
        return 1.0
    if "randomized" in combined or "clinical trial" in combined:
        return 0.9
    if "cohort" in combined or "prospective" in combined:
        return 0.7
    if "longitudinal" in combined:
        return 0.65
    if "cross-sectional" in combined:
        return 0.4
    return 0.3


def _score_pop_match(candidate: CandidateMetadata) -> float:
    """Score population match (0-1).

    Higher if abstract mentions cancer/oncology populations.
    """
    combined = " ".join([
        candidate.title or "",
        (candidate.abstract or "")[:500],
        " ".join(candidate.mesh_terms),
    ]).lower()

    cancer_terms = [
        "cancer", "oncology", "chemotherapy", "tumor", "tumour",
        "neoplasm", "carcinoma", "malignancy",
    ]
    cognitive_terms = [
        "cognitive", "cognition", "crci", "chemo brain",
        "chemobrain", "memory", "attention", "executive function",
    ]

    has_cancer = any(t in combined for t in cancer_terms)
    has_cognitive = any(t in combined for t in cognitive_terms)

    if has_cancer and has_cognitive:
        return 1.0
    if has_cancer:
        return 0.6
    if has_cognitive:
        return 0.4
    return 0.2


def _score_recency(candidate: CandidateMetadata) -> float:
    """Score publication recency (0-1).

    More recent papers score higher.
    """
    if candidate.year is None:
        return 0.3

    current_year = config.FRESHNESS_REFERENCE_YEAR
    age = current_year - candidate.year

    if age <= 2:
        return 1.0
    if age <= 5:
        return 0.8
    if age <= 10:
        return 0.5
    if age <= 20:
        return 0.3
    return 0.1


def _score_source_quality(candidate: CandidateMetadata) -> float:
    """Score source quality/reliability (0-1).

    Based on citation count and journal.
    """
    if candidate.cited_by_count is not None:
        if candidate.cited_by_count >= 100:
            return 1.0
        if candidate.cited_by_count >= 50:
            return 0.8
        if candidate.cited_by_count >= 20:
            return 0.6
        if candidate.cited_by_count >= 5:
            return 0.4
        return 0.2

    # No citation data available
    return 0.3


# ═══════════════════════════════════════════════════════════════
#  MAIN SCORER
# ═══════════════════════════════════════════════════════════════


def score_candidates(
    candidates: list[CandidateMetadata],
    gap_edges: set[str] | None = None,
    target_entity_ids: dict[str, str] | None = None,
    author_gap_boost_ids: set[str] | None = None,
    workstream: str | None = None,
    hop_boost_map: dict[str, float] | None = None,
) -> list[APSScoredCandidate]:
    """Score candidates using the APS formula.

    Formula: APS = w_edge·EdgeGap + w_design·DesignBonus + w_pop·PopMatch
                 + w_recency·Recency + w_source·SourceQuality

    Author-gap boost: If candidate maps to an edge with author-identified
    research gaps (from study_annotations_v1), APS_final = min(1.0, APS × 1.5)

    Hop citation boost: If candidate was queued via hop discovery,
    APS_final += citation_hop_boost (additive, from config.HOP_CITATION_APS_BOOST).
    This makes hop-derived candidates more likely to pass the DISPATCH threshold.

    Args:
        candidates: CandidateMetadata from search_coordinator.
        gap_edges: Set of edge IDs with insufficient evidence.
        target_entity_ids: Mapping from candidate dedup key to target entity ID.
        author_gap_boost_ids: Set of edge IDs with author-identified gaps.
        workstream: Workstream name for the candidates.
        hop_boost_map: Mapping from candidate dedup key to hop citation boost value.
            Populated from acquisition_queue_v1.aps_components_json when re-scoring
            hop-derived candidates.

    Returns:
        List of APSScoredCandidate, sorted by APS descending.
    """
    w = config.APS_WEIGHTS
    threshold = config.APS_THRESHOLD

    scored: list[APSScoredCandidate] = []

    for candidate in candidates:
        # Determine target entity for gap scoring
        target_id = None
        if target_entity_ids:
            key = _candidate_key(candidate)
            target_id = target_entity_ids.get(key)

        # Compute components
        edge_gap = _score_edge_gap(candidate, gap_edges, target_id)
        design_bonus = _score_design_bonus(candidate)
        pop_match = _score_pop_match(candidate)
        recency = _score_recency(candidate)
        source_quality = _score_source_quality(candidate)

        # Formula: APS = Σ(w_i × component_i)
        # All weights from config.APS_WEIGHTS (single source of truth)
        aps = (
            w["edge_gap"] * edge_gap
            + w["design"] * design_bonus
            + w["pop"] * pop_match
            + w["recency"] * recency
            + w["source"] * source_quality
        )

        # Author-gap boost
        boosted = False
        if author_gap_boost_ids and target_id and target_id in author_gap_boost_ids:
            aps = min(1.0, aps * config.AUTHOR_GAP_BOOST_MULTIPLIER)
            boosted = True
            logger.debug(
                "Author-gap boost applied for '%s' (target: %s)",
                candidate.title or candidate.doi,
                target_id,
            )

        # Hop citation boost (additive)
        hop_boosted = False
        if hop_boost_map:
            ckey = _candidate_key(candidate)
            hop_delta = hop_boost_map.get(ckey, 0.0)
            if hop_delta > 0:
                aps = min(1.0, aps + hop_delta)
                hop_boosted = True
                logger.debug(
                    "Hop citation boost +%.2f applied for '%s'",
                    hop_delta,
                    candidate.title or candidate.doi,
                )

        # Gate: APS >= threshold → DISPATCH, else DEFER
        decision = "DISPATCH" if aps >= threshold else "DEFER"

        scored.append(APSScoredCandidate(
            candidate=candidate,
            aps_score=round(aps, 4),
            aps_components={
                "edge_gap": round(edge_gap, 4),
                "design_bonus": round(design_bonus, 4),
                "pop_match": round(pop_match, 4),
                "recency": round(recency, 4),
                "source_quality": round(source_quality, 4),
            },
            author_gap_boosted=boosted,
            workstream=workstream,
            target_entity_id=target_id,
            decision=decision,
        ))

    # Sort by APS descending
    scored.sort(key=lambda s: s.aps_score, reverse=True)

    dispatch_count = sum(1 for s in scored if s.decision == "DISPATCH")
    defer_count = sum(1 for s in scored if s.decision == "DEFER")
    logger.info(
        "APS scoring complete: %d DISPATCH, %d DEFER (threshold=%.2f)",
        dispatch_count,
        defer_count,
        threshold,
    )

    return scored


def _candidate_key(candidate: CandidateMetadata) -> str:
    """Generate a key for candidate-to-entity mapping."""
    if candidate.doi:
        return f"doi:{candidate.doi.strip().lower()}"
    if candidate.pmid:
        return f"pmid:{candidate.pmid.strip()}"
    return f"title:{(candidate.title or '').strip().lower()[:100]}"
