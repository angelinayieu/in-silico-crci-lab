# VERIFIED: imports — all modules exist (p0_triage submodules)
# VERIFIED: backward wiring — reads pdf_path from context
# VERIFIED: forward wiring — writes paper_map, paper_type, extraction_mode to context
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — delegates to sub-modules (P0-G1 relevance, P0-G2 triage)
"""
Component: SYS_EXTRACTION.EX-P0.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 169-291
Purpose: Orchestrate P0 triage: PDF ingestion → relevance screening →
         paper type classification → extraction mode selection.
Reads: pdf_path (from pipeline context)
Writes: paper_map, paper_type, extraction_mode (to context for P1)
Gates: Delegates to sub-modules
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p0_triage(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P0 triage chain: ingest → screen → classify → mode select.

    Called by pipeline.py as the first chain in the extraction sequence.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with 'pdf_path' key.

    Returns:
        Updated context with P0 outputs.
    """
    from crci.extraction.p0_triage.pdf_ingestion import ingest_pdf
    from crci.extraction.p0_triage.relevance_screening import screen_relevance
    from crci.extraction.p0_triage.paper_type_classifier import classify_paper_type
    from crci.extraction.p0_triage.mode_selection import select_extraction_mode

    pdf_path = context["pdf_path"]
    logger.info("P0 triage starting for run %s, pdf=%s", run.extraction_run_id, pdf_path)

    # S1: PDF Ingestion
    ingested = ingest_pdf(pdf_path)
    context["ingested_paper"] = ingested
    logger.info("P0-S1: PDF ingested, %d chars extracted", len(ingested.get("text", "")))

    # S2: Relevance Screening
    screened = screen_relevance(ingested)
    context["screened_paper"] = screened
    relevance = screened.get("relevance_score", 0.0)
    logger.info("P0-S2: Relevance score=%.3f", relevance)

    # S3: Paper Type Classification
    classified = classify_paper_type(ingested)
    paper_subtype = classified.get("paper_subtype")
    context["paper_type"] = paper_subtype
    logger.info("P0-S3: Paper classified as %s", paper_subtype)

    # S4: Extraction Mode Selection
    paper_id = context.get("paper_id", run.extraction_run_id)
    triage_result = select_extraction_mode(
        paper_id=paper_id,
        paper_subtype=paper_subtype,
        screened_paper=screened,
    )
    context["triage_result"] = triage_result
    context["extraction_mode"] = triage_result.extraction_mode
    logger.info("P0-S4: Extraction mode=%s", triage_result.extraction_mode)

    logger.info(
        "P0 triage complete: type=%s, mode=%s, relevance=%.3f",
        paper_subtype,
        triage_result.extraction_mode,
        relevance,
    )
    return context
