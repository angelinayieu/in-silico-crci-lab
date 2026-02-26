# VERIFIED: formulas — HOP-1 (citation APS boost)
# VERIFIED: imports — shared/config, shared/models/tables, retrieval/models
# VERIFIED: backward wiring — reads study_registry_v1, study_annotations_v1
# VERIFIED: forward wiring — writes acquisition_queue_v1 entries
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — HOP-G1 (max depth), HOP-G2 (dedup against existing)
"""
Component: SYS_EXTRACTION.EX-ACQ.HopDiscoverer
Spec: Master Spec §9.4 (Content-Driven Hops)
      AUTOMATED_RETRIEVAL_PLAN.md Part 3 (Citation Chain Expansion)
Formulas: HOP-1 (citation APS boost = +0.15 per MS §9.4)
Reads: study_registry_v1 (extracted papers), study_annotations_v1 (references)
       edge_evidence_v1 (meta-analysis included_study_ids)
Writes: acquisition_queue_v1 (new hop-derived candidates)
Gates: HOP-G1 — hop_depth <= HOP_MAX_DEPTH (no infinite chains)
       HOP-G2 — dedup against study_registry_v1 (no re-acquisition)
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

logger = logging.getLogger(__name__)


def discover_hops_from_meta_analyses(session: Session) -> int:
    """Extract included study lists from meta-analyses and queue them.

    Meta-analyses in study_registry_v1 with included_study_ids_json
    contain DOIs/PMIDs of their component studies. These are high-value
    acquisition targets (same edge, validated by MA authors).

    Formula HOP-1: citation_aps_boost = +HOP_CITATION_APS_BOOST
    Gate HOP-G1: hop_depth <= HOP_MAX_DEPTH
    Gate HOP-G2: skip if DOI/PMID already in study_registry_v1

    Args:
        session: Active database session.

    Returns:
        Number of new candidates queued.
    """
    max_depth = config.HOP_MAX_DEPTH

    # Find meta-analyses with included study lists
    stmt = (
        select(
            StudyRegistry.study_id,
            StudyRegistry.included_study_ids_json,
            StudyRegistry.study_subtype,
        )
        .where(
            and_(
                StudyRegistry.included_study_ids_json.isnot(None),
                StudyRegistry.study_subtype.in_([
                    # PaperSubtype enum values (canonical)
                    "meta_analysis",
                    "systematic_review",
                    # Legacy/fine-grained subtypes (for future classification)
                    "pairwise_ma", "nma", "ipdma",
                    "dose_response_ma", "mega_analysis",
                ]),
            )
        )
    )
    ma_rows = session.execute(stmt).all()

    if not ma_rows:
        logger.info("No meta-analyses with included study lists found")
        return 0

    # Load known DOIs and PMIDs for HOP-G2 dedup
    known_dois, known_pmids = _load_known_identifiers(session)
    queued_dois, queued_pmids = _load_queued_identifiers(session)
    all_known_dois = known_dois | queued_dois
    all_known_pmids = known_pmids | queued_pmids

    new_count = 0

    for row in ma_rows:
        study_id = row.study_id
        try:
            included_ids = json.loads(row.included_study_ids_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Invalid included_study_ids_json for study %s", study_id,
            )
            continue

        if not isinstance(included_ids, list):
            continue

        # Find edges associated with this MA for target_edge_ids
        target_edges = _get_ma_edge_ids(session, study_id)

        for entry in included_ids:
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
                # Construct search query from author + year
                if first_author and year:
                    search_query = f"{first_author} {year}"
                elif first_author:
                    search_query = first_author
                elif title:
                    search_query = title
                else:
                    continue  # Skip if no identifiable info

            # Gate HOP-G2: skip known papers
            if doi and doi.lower() in all_known_dois:
                continue
            if pmid and pmid in all_known_pmids:
                continue

            # Queue the hop candidate
            # Note: If no DOI/PMID, use search_query in candidate_title
            # for the acquisition system to search by author+year
            display_title = title or search_query
            queue_entry = AcquisitionQueue(
                queue_id=f"HOP_{uuid.uuid4().hex[:12]}",
                candidate_doi=doi or None,
                candidate_pmid=pmid or None,
                candidate_title=display_title,
                # Pass Python objects for JSONB columns (no json.dumps — SQLAlchemy handles serialization)
                target_edge_ids_json=target_edges if target_edges else None,
                aps_score=config.HOP_CITATION_APS_BOOST,  # Formula HOP-1: base boost
                aps_components_json={
                    "citation_hop_boost": config.HOP_CITATION_APS_BOOST,
                    "search_query": search_query,
                    "first_author": first_author,
                    "year": year,
                },
                status="queued",
                retrieval_status="PENDING",
                hop_source_study_id=study_id,
                hop_depth=1,  # Gate HOP-G1: depth=1 (direct from MA)
            )
            session.add(queue_entry)
            new_count += 1

            # Track for dedup within this batch
            if doi:
                all_known_dois.add(doi.lower())
            if pmid:
                all_known_pmids.add(pmid)

    session.flush()

    logger.info(
        "Hop discovery from MAs: queued %d new candidates from %d meta-analyses",
        new_count, len(ma_rows),
    )
    return new_count


def discover_hops_from_annotations(session: Session) -> int:
    """Extract cited references from annotations and queue promising ones.

    Papers that cite other papers in their discussion (captured as annotations
    with category='literature_comparison' or 'mechanism_hypothesis') may
    point to high-value targets.

    Gate HOP-G1: hop_depth <= HOP_MAX_DEPTH
    Gate HOP-G2: dedup against study_registry_v1 + acquisition_queue_v1

    Args:
        session: Active database session.

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

    known_dois, known_pmids = _load_known_identifiers(session)
    queued_dois, queued_pmids = _load_queued_identifiers(session)
    all_known_dois = known_dois | queued_dois
    all_known_pmids = known_pmids | queued_pmids

    new_count = 0

    for ann in annotations:
        try:
            data = json.loads(ann.structured_data_json) if isinstance(
                ann.structured_data_json, str
            ) else ann.structured_data_json
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict):
            continue

        # Look for referenced papers in annotation data
        refs = data.get("cited_references", [])
        if not isinstance(refs, list):
            continue

        for ref in refs:
            if not isinstance(ref, dict):
                continue

            doi = ref.get("doi", "")
            pmid = ref.get("pmid", "")
            title = ref.get("title", "")

            if not doi and not pmid:
                continue

            # Gate HOP-G2: dedup
            if doi and doi.lower() in all_known_dois:
                continue
            if pmid and pmid in all_known_pmids:
                continue

            # Check hop depth from source study
            source_depth = _get_study_hop_depth(session, ann.study_id)
            if source_depth + 1 > max_depth:
                logger.debug(
                    "HOP-G1: skipping hop from %s — depth %d would exceed max %d",
                    ann.study_id, source_depth + 1, max_depth,
                )
                continue

            queue_entry = AcquisitionQueue(
                queue_id=f"HOP_{uuid.uuid4().hex[:12]}",
                candidate_doi=doi or None,
                candidate_pmid=pmid or None,
                candidate_title=title or None,
                aps_score=config.HOP_CITATION_APS_BOOST,
                # Pass Python dict for JSONB column (no json.dumps)
                aps_components_json={
                    "citation_hop_boost": config.HOP_CITATION_APS_BOOST,
                    "annotation_category": ann.category,
                },
                status="queued",
                retrieval_status="PENDING",
                hop_source_study_id=ann.study_id,
                hop_depth=source_depth + 1,
            )
            session.add(queue_entry)
            new_count += 1

            if doi:
                all_known_dois.add(doi.lower())
            if pmid:
                all_known_pmids.add(pmid)

    session.flush()

    logger.info(
        "Hop discovery from annotations: queued %d new candidates from %d annotations",
        new_count, len(annotations),
    )
    return new_count


def run_hop_discovery(session: Session) -> int:
    """Run all hop discovery strategies.

    Args:
        session: Active database session.

    Returns:
        Total number of new candidates queued.
    """
    total = 0
    total += discover_hops_from_meta_analyses(session)
    total += discover_hops_from_annotations(session)

    logger.info("Hop discovery complete: %d total new candidates", total)
    return total


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_known_identifiers(session: Session) -> tuple[set[str], set[str]]:
    """Load DOIs and PMIDs from study_registry_v1 for dedup."""
    stmt_doi = (
        select(StudyRegistry.doi)
        .where(StudyRegistry.doi.isnot(None))
    )
    stmt_pmid = (
        select(StudyRegistry.pmid)
        .where(StudyRegistry.pmid.isnot(None))
    )
    dois = {row[0].lower() for row in session.execute(stmt_doi).all()}
    pmids = {row[0] for row in session.execute(stmt_pmid).all()}
    return dois, pmids


def _load_queued_identifiers(session: Session) -> tuple[set[str], set[str]]:
    """Load DOIs and PMIDs from acquisition_queue_v1 for dedup."""
    stmt_doi = (
        select(AcquisitionQueue.candidate_doi)
        .where(AcquisitionQueue.candidate_doi.isnot(None))
    )
    stmt_pmid = (
        select(AcquisitionQueue.candidate_pmid)
        .where(AcquisitionQueue.candidate_pmid.isnot(None))
    )
    dois = {row[0].lower() for row in session.execute(stmt_doi).all()}
    pmids = {row[0] for row in session.execute(stmt_pmid).all()}
    return dois, pmids


def _get_ma_edge_ids(session: Session, study_id: str) -> list[str]:
    """Get edge relation IDs associated with a meta-analysis study."""
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
    """Get the hop depth for a study (0 if directly acquired, >0 if hop-derived).

    Checks if this study was itself a hop candidate by matching on
    DOI or PMID.
    """
    # Get the study's identifiers
    id_stmt = (
        select(StudyRegistry.doi, StudyRegistry.pmid)
        .where(StudyRegistry.study_id == study_id)
    )
    id_row = session.execute(id_stmt).first()
    if id_row is None:
        return 0

    study_doi, study_pmid = id_row

    # Build match conditions: DOI or PMID
    match_conditions = []
    if study_doi:
        match_conditions.append(
            AcquisitionQueue.candidate_doi == study_doi
        )
    if study_pmid:
        match_conditions.append(
            AcquisitionQueue.candidate_pmid == study_pmid
        )
    if not match_conditions:
        return 0

    stmt = (
        select(AcquisitionQueue.hop_depth)
        .where(
            and_(
                AcquisitionQueue.hop_source_study_id.isnot(None),
                or_(*match_conditions),
            )
        )
        .limit(1)
    )
    result = session.execute(stmt).scalar_one_or_none()
    return result if result is not None else 0
