# VERIFIED: imports — pdf_ingestion, relevance_screening, paper_type_classifier, mode_selection
# VERIFIED: backward wiring — reads PDF path from pipeline context
# VERIFIED: forward wiring — writes TriageResult + PaperMap inputs to context
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P0-G1 (parse failure), P0-G2 (relevance reject)
"""
Component: SYS_EXTRACTION.EX-P0.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 168-330
Purpose: Orchestrate P0 triage: ingest → screen → classify → route.
         Registers paper in study_registry_v1 with v2.0 columns.
Reads: PDF file path (from pipeline context)
Writes: TriageResult, ingested paper data, study_registry_v1 row
Gates: P0-G1 (parse failure blocks), P0-G2 (REJECT excludes from extraction)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.enums import PipelineStatus
from crci.shared.models.intermediate_states import GateViolation, TriageResult
from crci.shared.models.tables import ExtractionRun, StudyRegistry
from crci.shared.study_identity import compute_study_id, normalize_doi, check_duplicate_study

logger = logging.getLogger(__name__)


def run_p0_triage(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P0 triage chain: ingest → screen → classify → route.

    Steps:
        P0-S1: PDF ingestion (pdf_ingestion.ingest_pdf)
        P0-S2: Relevance screening (relevance_screening.screen_relevance)
        P0-PTC: Paper type classification (paper_type_classifier.classify_paper_type)
        P0-S3/S4: Mode selection + routing (mode_selection.select_extraction_mode)

    Side effects:
        - Creates study_registry_v1 row with v2.0 columns
        - Sets run.study_id and run.extraction_mode

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with 'pdf_path' key.

    Returns:
        Updated context with triage results.

    Raises:
        GateViolation: P0-G1 on parse failure, P0-G2 on relevance rejection.
    """
    pdf_path = Path(context["pdf_path"])

    # ── P0-S1: PDF Ingestion ──
    logger.info("P0-S1: Ingesting PDF %s", pdf_path.name)
    from crci.extraction.p0_triage.pdf_ingestion import ingest_pdf

    ingested = ingest_pdf(pdf_path)
    context["ingested_paper"] = ingested

    logger.info(
        "P0-S1 complete: quality=%s, pages=%d, tables=%s, figures=%s",
        ingested.get("pdf_quality", "unknown"),
        ingested.get("page_count", 0),
        ingested.get("has_tables", False),
        ingested.get("has_figures", False),
    )

    # ── P0-S2: Relevance Screening ──
    logger.info("P0-S2: Screening relevance")
    from crci.extraction.p0_triage.relevance_screening import screen_relevance

    screened = screen_relevance(ingested)
    context["screened_paper"] = screened

    decision = screened.get("decision", "REVIEW")
    logger.info(
        "P0-S2 complete: score=%.2f, decision=%s",
        screened.get("relevance_score", 0.0),
        decision,
    )

    # Gate P0-G2: REJECT excludes from further extraction
    if decision == "REJECT":
        logger.warning(
            "P0-G2: Paper rejected — relevance score=%.2f below threshold. "
            "Skipping extraction.",
            screened.get("relevance_score", 0.0),
        )
        raise GateViolation(
            "P0-G2",
            f"Paper rejected at relevance screening (score={screened.get('relevance_score', 0.0):.2f})",
            {"pdf_path": str(pdf_path), "decision": decision},
        )

    # ── P0-PTC: Paper Type Classification ──
    logger.info("P0-PTC: Classifying paper type")
    from crci.extraction.p0_triage.paper_type_classifier import classify_paper_type

    classified = classify_paper_type(ingested)
    context["classified_paper"] = classified

    paper_subtype = classified.get("paper_subtype")
    logger.info(
        "P0-PTC complete: subtype=%s, confidence=%.2f",
        paper_subtype,
        classified.get("confidence", 0.0),
    )

    # ── P0-S3/S4: Mode Selection + Routing ──
    logger.info("P0-S3: Selecting extraction mode")
    from crci.extraction.p0_triage.mode_selection import select_extraction_mode
    from crci.shared.models.enums import PaperSubtype

    # ── Compute deterministic study_id (S1 fix) ──
    metadata = ingested.get("metadata", {})
    paper_id, id_source = compute_study_id(metadata)
    doi_normalized = normalize_doi(metadata.get("doi"))

    # ── Check for existing study (dedup) ──
    existing_id = check_duplicate_study(
        session,
        doi=metadata.get("doi"),
        pmid=metadata.get("pmid"),
        pmcid=metadata.get("pmcid"),
    )
    if existing_id:
        logger.info(
            "P0: Study already exists as %s, reusing (dedup by %s)",
            existing_id,
            id_source,
        )
        paper_id = existing_id
        context["is_rerun"] = True
    else:
        context["is_rerun"] = False

    # Convert raw subtype string to enum
    try:
        subtype_enum = PaperSubtype(paper_subtype) if paper_subtype else PaperSubtype.OTHER
    except ValueError:
        logger.warning("Unknown paper subtype '%s', defaulting to OTHER", paper_subtype)
        subtype_enum = PaperSubtype.OTHER

    triage_result: TriageResult = select_extraction_mode(
        paper_id=paper_id,
        paper_subtype=subtype_enum,
        screened_paper=screened,
    )
    context["triage_result"] = triage_result
    context["paper_id"] = paper_id
    context["extraction_mode"] = triage_result.extraction_mode.value

    logger.info(
        "P0-S3 complete: paper_id=%s, mode=%s, subtype=%s",
        paper_id,
        triage_result.extraction_mode.value,
        triage_result.paper_subtype,
    )

    # ── Register/Update in study_registry_v1 with v2.0 columns (UPSERT) ──
    existing_study = session.query(StudyRegistry).filter(
        StudyRegistry.study_id == paper_id
    ).first()

    if existing_study:
        # Update existing study (rerun case)
        existing_study.title = metadata.get("title", pdf_path.stem)
        existing_study.authors = metadata.get("author", "") or existing_study.authors
        existing_study.doi = metadata.get("doi") or existing_study.doi
        existing_study.doi_normalized = doi_normalized or existing_study.doi_normalized
        existing_study.year = metadata.get("year") or existing_study.year
        existing_study.study_design = classified.get("study_design") or existing_study.study_design
        existing_study.study_subtype = str(subtype_enum.value) if subtype_enum else existing_study.study_subtype
        existing_study.pdf_path = str(pdf_path)
        existing_study.parse_quality = ingested.get("pdf_quality", "GOOD")
        logger.info("Updated existing study %s in study_registry_v1", paper_id)
    else:
        # Insert new study
        study_row = StudyRegistry(
            study_id=paper_id,
            title=metadata.get("title", pdf_path.stem),
            authors=metadata.get("author", ""),
            doi=metadata.get("doi"),
            doi_normalized=doi_normalized,
            id_source=id_source,
            pmid=metadata.get("pmid"),
            pmcid=metadata.get("pmcid"),
            year=metadata.get("year"),
            study_design=classified.get("study_design"),
            # v2.0 columns
            study_subtype=str(subtype_enum.value) if subtype_enum else None,
            pdf_path=str(pdf_path),
            canonical_text_path=None,
            file_type="pdf",
            parse_quality=ingested.get("pdf_quality", "GOOD"),
            hop_depth=0,  # Directly acquired, not a hop-derived study
        )
        session.add(study_row)
        logger.info("Registered new study %s in study_registry_v1 (id_source=%s)", paper_id, id_source)

    # Link extraction run to study
    run.study_id = paper_id
    run.extraction_mode = triage_result.extraction_mode.value
    session.flush()

    return context
