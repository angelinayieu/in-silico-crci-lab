# VERIFIED: imports — all modules exist (p1_extraction submodules)
# VERIFIED: backward wiring — reads ingested_paper, triage_result from context (P0)
# VERIFIED: forward wiring — writes raw_annotations, reconciliation_result to context (TB)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P1-G4 contradiction rate delegated to reconciliation.py
"""
Component: SYS_EXTRACTION.EX-P1.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 292-592
Purpose: Orchestrate P1 extraction: canonical reading → multi-agent
         extraction (AG01-AG11) → reconciliation → annotation trust boundary.
Reads: ingested_paper, triage_result (from P0 context)
Writes: raw_annotations, reconciliation_result, atb_result (to context for TB)
Gates: P1-G4 (contradiction rate) delegated to reconciliation.py
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p1_extraction(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P1 extraction chain: read → agents → reconcile → ATB.

    Called by pipeline.py after P0 triage completes.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P0 outputs.

    Returns:
        Updated context with P1 outputs.
    """
    from crci.extraction.p1_extraction.canonical_reader import CanonicalReader
    from crci.extraction.p1_extraction.reconciliation import reconcile_annotations
    from crci.extraction.p1_extraction.annotation_trust_boundary import validate_annotations

    logger.info("P1 extraction starting for run %s", run.extraction_run_id)

    ingested = context.get("ingested_paper", {})
    triage_result = context.get("triage_result")
    paper_id = context.get("paper_id", run.extraction_run_id)
    canonical_text = ingested.get("text", "")

    # S1: Canonical Reading — structure the paper text
    reader = CanonicalReader()
    paper_map = reader.read(paper_id=paper_id, canonical_text=canonical_text)
    context["paper_map"] = paper_map
    logger.info("P1-S1: Canonical reading complete, paper_map created")

    # S2: Multi-Agent Extraction (AG01-AG11)
    # Agents are executed by the orchestrator; results are raw annotations.
    # In the pipeline context, agents are called via LLM client.
    raw_annotations = _run_agents(paper_map, triage_result, context)
    context["raw_annotations"] = raw_annotations
    logger.info("P1-S2: %d raw annotations extracted", len(raw_annotations))

    # S3: Reconciliation — merge multi-agent outputs
    reconciliation_result = reconcile_annotations(
        session=session,
        raw_annotations=raw_annotations,
        study_id=paper_id,
        extraction_run_id=run.extraction_run_id,
    )
    context["reconciliation_result"] = reconciliation_result
    logger.info(
        "P1-S3: Reconciliation complete, %d reconciled annotations",
        len(reconciliation_result.reconciled) if hasattr(reconciliation_result, "reconciled") else 0,
    )

    # S4: Annotation Trust Boundary
    atb_result = validate_annotations(
        session=session,
        reconciliation_result=reconciliation_result,
    )
    context["atb_result"] = atb_result
    logger.info("P1-S4: Annotation trust boundary complete")

    logger.info("P1 extraction complete for run %s", run.extraction_run_id)
    return context


def _run_agents(
    paper_map: Any,
    triage_result: Any,
    context: dict[str, Any],
) -> list:
    """Execute extraction agents AG01-AG11 against the paper map.

    Each agent extracts its domain-specific annotations from the paper.
    Results are collected as RawAnnotationEmission objects.

    In production, agents use the LLM client. This orchestrator
    imports each agent and calls its extract() method.
    """
    from crci.extraction.p1_extraction.agents.ag01_metadata import AG01MetadataAgent
    from crci.extraction.p1_extraction.agents.ag02_design import AG02DesignAgent
    from crci.extraction.p1_extraction.agents.ag03_cohort import AG03CohortAgent
    from crci.extraction.p1_extraction.agents.ag04_outcome import AG04OutcomeAgent
    from crci.extraction.p1_extraction.agents.ag05_stats_label import AG05StatsLabelAgent
    from crci.extraction.p1_extraction.agents.ag06_exposure import AG06ExposureAgent
    from crci.extraction.p1_extraction.agents.ag07_mediator import AG07MediatorAgent
    from crci.extraction.p1_extraction.agents.ag08_temporal import AG08TemporalAgent
    from crci.extraction.p1_extraction.agents.ag09_reconciliation import AG09ReconciliationAgent
    from crci.extraction.p1_extraction.agents.ag10_strategic_intel import AG10StrategicIntelAgent
    from crci.extraction.p1_extraction.agents.ag11_instrument_validation import AG11InstrumentValidationAgent

    llm_client = context.get("llm_client")
    extraction_mode = context.get("extraction_mode", "STANDARD")

    agents = [
        AG01MetadataAgent,
        AG02DesignAgent,
        AG03CohortAgent,
        AG04OutcomeAgent,
        AG05StatsLabelAgent,
        AG06ExposureAgent,
        AG07MediatorAgent,
        AG08TemporalAgent,
        AG09ReconciliationAgent,
        AG10StrategicIntelAgent,
        AG11InstrumentValidationAgent,
    ]

    all_annotations: list = []
    for agent_cls in agents:
        agent = agent_cls(llm_client=llm_client)
        try:
            annotations = agent.extract(paper_map, mode=extraction_mode)
            all_annotations.extend(annotations)
            logger.debug(
                "Agent %s produced %d annotations",
                agent_cls.__name__,
                len(annotations),
            )
        except Exception as exc:
            logger.warning(
                "Agent %s failed: %s (continuing with remaining agents)",
                agent_cls.__name__,
                exc,
            )

    return all_annotations
