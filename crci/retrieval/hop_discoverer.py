# ASSUMPTIONS:
#   - StudyRegistry.included_study_ids_json is TEXT containing a JSON array of
#     objects with optional keys: doi, pmid, title, first_author, year.
#   - StudyRegistry.hop_depth is set at ingestion time (0 for directly acquired).
#   - AcquisitionQueue JSONB columns accept Python dicts directly (SQLAlchemy JSON type).
#   - Caller commits the session after calling these functions.
# TEST COVERAGE: tests/test_hop_discoverer.py
# REVIEW:
#   - _get_ma_edge_ids returns empty if P2-P4 haven't run yet for the MA.
#     This is expected — target_edge_ids_json will be None.
#   - Annotation-based hops require structured_data_json.cited_references —
#     if agents don't produce this field, no annotation hops will fire.
"""
Component: SYS_EXTRACTION.EX-ACQ.HopDiscoverer
Spec: Master Spec §9.4 (Content-Driven Hops)
      AUTOMATED_RETRIEVAL_PLAN.md Part 3 (Citation Chain Expansion)
Formulas: HOP-1 — citation APS boost = +HOP_CITATION_APS_BOOST (additive delta,
          stored in aps_components_json; aps_score is set to None pending full scoring)
Reads: study_registry_v1 (extracted papers, hop_depth column)
       study_annotations_v1 (literature_comparison, mechanism_hypothesis, research_gap)
       edge_evidence_v1 (optional — for target_edge_ids)
Writes: acquisition_queue_v1 (new hop-derived candidates)
Gates:
    HOP-G1 — hop_depth + 1 <= HOP_MAX_DEPTH (no infinite chains)
    HOP-G2 — dedup against normalized DOI/PMID in study_registry_v1 + acquisition_queue_v1
    HOP-G3 — per-paper cap: <= HOP_MAX_TARGETS_PER_PAPER per source MA/SR
    HOP-G4 — global cap: <= HOP_MAX_TOTAL_PER_RUN per discovery invocation
Transaction semantics:
    This module calls session.flush() but NOT session.commit().
    The caller (typically acquisition_scheduler or pipeline.py) is responsible
    for committing. Safe to call inside an outer transaction.
"""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import (
    AcquisitionQueue,
    StudyAnnotations,
    StudyRegistry,
    EdgeEvidence,
)
from crci.retrieval.identifier_utils import (
    normalize_doi,
    normalize_pmid,
    candidate_dedup_key,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  SUBTYPE ALLOWLIST — which study_subtype values are MA/SR
# ═══════════════════════════════════════════════════════════════

from crci.shared.models.enums import PaperSubtype

_MA_SR_SUBTYPES: set[str] = {
    # Original MA/SR subtypes
    PaperSubtype.META_ANALYSIS.value,
    PaperSubtype.SYSTEMATIC_REVIEW.value,
    # Fine-grained MA subtypes (Master Spec §4.1)
    PaperSubtype.PAIRWISE_MA.value,
    PaperSubtype.NMA.value,
    PaperSubtype.IPDMA.value,
    PaperSubtype.DOSE_RESPONSE_MA.value,
    PaperSubtype.MEGA_ANALYSIS.value,
    # Umbrella reviews — their included MAs should be acquired
    PaperSubtype.UMBRELLA_REVIEW.value,
}


def discover_hops_from_meta_analyses(
    session: Session,
    global_budget_remaining: int | None = None,
) -> int:
    """Extract included study lists from meta-analyses and queue them.

    For each MA/SR in study_registry_v1 that has included_study_ids_json,
    queue the constituent studies for acquisition.

    APS semantics (HOP-1): The hop boost (+0.15) is stored as a component
    in aps_components_json. aps_score is set to None because full APS
    scoring requires abstract/metadata that we don't have yet. The APS
    scorer will compute the real score and add the boost when the candidate
    is processed in the next acquisition cycle.

    Gates enforced:
        HOP-G1: source study's hop_depth + 1 <= HOP_MAX_DEPTH
        HOP-G2: normalized DOI/PMID/dedup_key not in known sets
        HOP-G3: <= HOP_MAX_TARGETS_PER_PAPER per source study
        HOP-G4: <= global_budget_remaining (if provided)

    Args:
        session: Active database session. Caller must commit.
        global_budget_remaining: If provided, stop after this many candidates.

    Returns:
        Number of new candidates queued.
    """
    max_depth = config.HOP_MAX_DEPTH
    per_paper_cap = config.HOP_MAX_TARGETS_PER_PAPER

    # Find meta-analyses with included study lists
    stmt = (
        select(
            StudyRegistry.study_id,
            StudyRegistry.included_study_ids_json,
            StudyRegistry.study_subtype,
            StudyRegistry.hop_depth,
        )
        .where(
            and_(
                StudyRegistry.included_study_ids_json.isnot(None),
                StudyRegistry.study_subtype.in_(list(_MA_SR_SUBTYPES)),
            )
        )
    )
    ma_rows = session.execute(stmt).all()

    if not ma_rows:
        logger.info("No meta-analyses with included study lists found")
        return 0

    # Load known identifiers for HOP-G2 dedup (normalized)
    known_keys = _load_all_known_keys(session)

    new_count = 0
    budget = global_budget_remaining

    for row in ma_rows:
        study_id = row.study_id
        source_depth = row.hop_depth or 0

        # Gate HOP-G1: check if hops from this source would exceed max depth
        candidate_depth = source_depth + 1
        if candidate_depth > max_depth:
            logger.debug(
                "HOP-G1: skipping MA %s — hop_depth %d would exceed max %d",
                study_id, candidate_depth, max_depth,
            )
            continue

        # Parse included studies
        try:
            included_ids = json.loads(row.included_study_ids_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Invalid included_study_ids_json for study %s", study_id,
            )
            continue

        if not isinstance(included_ids, list):
            logger.warning(
                "included_study_ids_json is not a list for study %s", study_id,
            )
            continue

        # Try to get target edges (may be empty if P2-P4 haven't run yet)
        target_edges = _get_ma_edge_ids(session, study_id)

        queued_this_paper = 0

        for entry in included_ids:
            # Gate HOP-G3: per-paper cap
            if queued_this_paper >= per_paper_cap:
                logger.info(
                    "HOP-G3: per-paper cap (%d) reached for MA %s, "
                    "skipping remaining %d entries",
                    per_paper_cap, study_id,
                    len(included_ids) - queued_this_paper,
                )
                break

            # Gate HOP-G4: global cap
            if budget is not None and new_count >= budget:
                logger.info(
                    "HOP-G4: global budget (%d) exhausted during MA hop discovery",
                    budget,
                )
                break

            if not isinstance(entry, dict):
                continue

            doi = entry.get("doi") or ""
            pmid = entry.get("pmid") or ""
            title = entry.get("title") or ""
            first_author = entry.get("first_author") or ""
            year = entry.get("year")

            # Build search query for entries without DOI/PMID
            search_query = None
            if not doi and not pmid:
                if first_author and year:
                    search_query = f"{first_author} {year}"
                elif first_author:
                    search_query = first_author
                elif title:
                    search_query = title
                else:
                    continue  # Skip: no identifiable info

            # Gate HOP-G2: dedup using normalized keys
            dedup_key = candidate_dedup_key(
                doi=doi or None,
                pmid=pmid or None,
                title=title or None,
                first_author=first_author or None,
                year=year,
            )
            if dedup_key in known_keys:
                continue

            # Normalize identifiers before storing
            ndoi = normalize_doi(doi) if doi else None
            npmid = normalize_pmid(pmid) if pmid else None
            display_title = title or search_query

            queue_entry = AcquisitionQueue(
                queue_id=f"HOP_{uuid.uuid4().hex[:12]}",
                candidate_doi=ndoi,
                candidate_pmid=npmid,
                candidate_title=display_title,
                target_edge_ids_json=target_edges if target_edges else None,
                # APS semantics: aps_score=None (pending full scoring).
                # The boost is stored as a component for the APS scorer to apply.
                aps_score=None,
                aps_components_json={
                    "citation_hop_boost": config.HOP_CITATION_APS_BOOST,
                    "hop_source": "meta_analysis_included_list",
                    "search_query": search_query,
                    "first_author": first_author,
                    "year": year,
                    "dedup_key": dedup_key,
                },
                status="queued",
                retrieval_status="PENDING",
                hop_source_study_id=study_id,
                hop_depth=candidate_depth,
            )
            session.add(queue_entry)
            new_count += 1
            queued_this_paper += 1

            # Track for dedup within this batch
            known_keys.add(dedup_key)

        # Check global budget after each paper
        if budget is not None and new_count >= budget:
            break

    session.flush()

    logger.info(
        "Hop discovery from MAs: queued %d new candidates from %d meta-analyses",
        new_count, len(ma_rows),
    )
    return new_count


def discover_hops_from_annotations(
    session: Session,
    global_budget_remaining: int | None = None,
) -> int:
    """Extract cited references from annotations and queue promising ones.

    Papers that cite other papers in their discussion (captured as annotations
    with category='literature_comparison' or 'mechanism_hypothesis') may
    point to high-value targets.

    APS semantics: Same as discover_hops_from_meta_analyses — aps_score=None,
    hop boost stored in aps_components_json for the APS scorer to apply.

    Gates enforced:
        HOP-G1: source study's hop_depth + 1 <= HOP_MAX_DEPTH
        HOP-G2: normalized dedup_key not in known sets
        HOP-G4: <= global_budget_remaining (if provided)

    Note: No per-paper cap (HOP-G3) applied here because annotation refs
    are typically few per paper and already filtered by category.

    Args:
        session: Active database session. Caller must commit.
        global_budget_remaining: If provided, stop after this many candidates.

    Returns:
        Number of new candidates queued.
    """
    max_depth = config.HOP_MAX_DEPTH

    # Find annotations that reference other papers
    stmt = (
        select(StudyAnnotations)
        .where(
            and_(
                StudyAnnotations.category.in_([
                    "literature_comparison",
                    "mechanism_hypothesis",
                    "research_gap",
                ]),
                StudyAnnotations.structured_data_json.isnot(None),
                StudyAnnotations.active.is_(True),
            )
        )
    )
    annotations = session.execute(stmt).scalars().all()

    if not annotations:
        logger.debug("No citation annotations found for hop discovery")
        return 0

    known_keys = _load_all_known_keys(session)

    # Cache hop_depth per study_id to avoid repeated queries
    depth_cache: dict[str, int] = {}

    new_count = 0
    budget = global_budget_remaining

    for ann in annotations:
        # Gate HOP-G4: global cap
        if budget is not None and new_count >= budget:
            logger.info(
                "HOP-G4: global budget (%d) exhausted during annotation hop discovery",
                budget,
            )
            break

        try:
            data = (
                json.loads(ann.structured_data_json)
                if isinstance(ann.structured_data_json, str)
                else ann.structured_data_json
            )
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict):
            continue

        # Look for referenced papers in annotation data
        refs = data.get("cited_references", [])
        if not isinstance(refs, list):
            continue

        # Gate HOP-G1: check source depth (cached)
        source_id = ann.study_id
        if source_id not in depth_cache:
            depth_cache[source_id] = _get_study_hop_depth(session, source_id)
        source_depth = depth_cache[source_id]
        candidate_depth = source_depth + 1

        if candidate_depth > max_depth:
            logger.debug(
                "HOP-G1: skipping annotation from %s — depth %d > max %d",
                source_id, candidate_depth, max_depth,
            )
            continue

        for ref in refs:
            if not isinstance(ref, dict):
                continue

            # Gate HOP-G4: global cap (inner loop)
            if budget is not None and new_count >= budget:
                break

            doi = ref.get("doi", "")
            pmid = ref.get("pmid", "")
            title = ref.get("title", "")

            if not doi and not pmid:
                continue

            # Gate HOP-G2: dedup via normalized keys
            dedup_key = candidate_dedup_key(
                doi=doi or None,
                pmid=pmid or None,
                title=title or None,
            )
            if dedup_key in known_keys:
                continue

            ndoi = normalize_doi(doi) if doi else None
            npmid = normalize_pmid(pmid) if pmid else None

            queue_entry = AcquisitionQueue(
                queue_id=f"HOP_{uuid.uuid4().hex[:12]}",
                candidate_doi=ndoi,
                candidate_pmid=npmid,
                candidate_title=title or None,
                # APS semantics: aps_score=None (pending full scoring)
                aps_score=None,
                aps_components_json={
                    "citation_hop_boost": config.HOP_CITATION_APS_BOOST,
                    "annotation_category": ann.category,
                    "dedup_key": dedup_key,
                },
                status="queued",
                retrieval_status="PENDING",
                hop_source_study_id=source_id,
                hop_depth=candidate_depth,
            )
            session.add(queue_entry)
            new_count += 1
            known_keys.add(dedup_key)

    session.flush()

    logger.info(
        "Hop discovery from annotations: queued %d new candidates from %d annotations",
        new_count, len(annotations),
    )
    return new_count


def run_hop_discovery(session: Session) -> int:
    """Run all hop discovery strategies, enforcing a global cap.

    Strategies run in priority order:
        1. MA/SR included study lists (highest relevance)
        2. Annotation cited references (supplementary)

    Gate HOP-G4: Total candidates across ALL strategies <=
        config.HOP_MAX_TOTAL_PER_RUN.

    Transaction semantics: This function calls session.flush() but does
    NOT commit. The caller (acquisition_scheduler Step 5) owns the
    transaction boundary and must call session.commit().

    Args:
        session: Active database session. Caller must commit.

    Returns:
        Total number of new candidates queued.
    """
    global_cap = config.HOP_MAX_TOTAL_PER_RUN

    ma_count = discover_hops_from_meta_analyses(
        session, global_budget_remaining=global_cap,
    )

    remaining = global_cap - ma_count
    ann_count = 0
    if remaining > 0:
        ann_count = discover_hops_from_annotations(
            session, global_budget_remaining=remaining,
        )
    else:
        logger.info(
            "HOP-G4: global cap (%d) already reached by MA strategy, "
            "skipping annotation strategy",
            global_cap,
        )

    total = ma_count + ann_count
    logger.info("Hop discovery complete: %d total (%d MA, %d annotation)", total, ma_count, ann_count)
    return total


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_all_known_keys(session: Session) -> set[str]:
    """Load normalized dedup keys from study_registry_v1 AND acquisition_queue_v1.

    Uses DOI-based keys when DOI is available, PMID-based otherwise.
    Also checks aps_components_json for dedup_key stored during hop queuing.

    Returns:
        Set of dedup key strings (all normalized).
    """
    keys: set[str] = set()

    # From study_registry_v1: DOIs and PMIDs
    stmt_sr = select(
        StudyRegistry.doi,
        StudyRegistry.pmid,
    ).where(
        or_(
            StudyRegistry.doi.isnot(None),
            StudyRegistry.pmid.isnot(None),
        )
    )
    for row in session.execute(stmt_sr).all():
        doi, pmid = row
        key = candidate_dedup_key(
            doi=doi,
            pmid=pmid,
        )
        keys.add(key)

    # From acquisition_queue_v1: DOIs, PMIDs, and stored dedup_keys
    stmt_aq = select(
        AcquisitionQueue.candidate_doi,
        AcquisitionQueue.candidate_pmid,
        AcquisitionQueue.aps_components_json,
    )
    for row in session.execute(stmt_aq).all():
        c_doi, c_pmid, components = row

        # Primary key from DOI/PMID
        key = candidate_dedup_key(doi=c_doi, pmid=c_pmid)
        keys.add(key)

        # Also load the stored dedup_key from components (may include
        # title-based keys for entries without DOI/PMID)
        if isinstance(components, dict):
            stored = components.get("dedup_key")
            if stored:
                keys.add(stored)
        elif isinstance(components, str):
            try:
                parsed = json.loads(components)
                stored = parsed.get("dedup_key")
                if stored:
                    keys.add(stored)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

    return keys


def _get_ma_edge_ids(session: Session, study_id: str) -> list[str]:
    """Get edge relation IDs associated with a meta-analysis study.

    NOTE: This returns empty for freshly-ingested MAs because P1 extraction
    creates StudyRegistry + included_study_ids_json, but edge_evidence rows
    are only created after P2-P4 run. This is expected — the target_edge_ids
    field on AcquisitionQueue is informational, not required for candidate
    processing. The acquisition scheduler will match candidates to edges
    during APS scoring.
    """
    stmt = (
        select(EdgeEvidence.edge_relation_id)
        .where(
            and_(
                EdgeEvidence.study_id == study_id,
                EdgeEvidence.active == 1,
            )
        )
        .distinct()
    )
    return [row[0] for row in session.execute(stmt).all()]


def _get_study_hop_depth(session: Session, study_id: str) -> int:
    """Get hop depth directly from study_registry_v1.hop_depth column.

    Returns 0 for directly-acquired studies (column default).
    Returns >0 for hop-derived studies.
    Returns 0 if study_id not found (defensive).
    """
    stmt = (
        select(StudyRegistry.hop_depth)
        .where(StudyRegistry.study_id == study_id)
    )
    result = session.execute(stmt).scalar_one_or_none()
    return result if result is not None else 0
