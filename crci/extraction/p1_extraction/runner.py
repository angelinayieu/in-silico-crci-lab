# VERIFIED: imports — canonical_reader, base_agent, reconciliation, annotation_trust_boundary
# VERIFIED: imports — ma_multi_product (MA-1 through MA-8 dispatch)
# VERIFIED: backward wiring — reads ingested paper + triage result from context
# VERIFIED: forward wiring — writes PaperMap, agent outputs, validated annotations to context
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — delegated to individual agents and ATB
"""
Component: SYS_EXTRACTION.EX-P1.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 330-600
      PAPER_TYPE_ROUTING_AND_ACQUISITION.md §2 (MA Multi-Product)
Purpose: Orchestrate P1 extraction: canonical read → MA plan → multi-agent → reconcile → ATB.
Reads: ingested_paper, triage_result (from P0 context)
Writes: PaperMap, agent outputs, MA extraction plan, reconciled + validated annotations
Gates: Delegated to agents (AG-G*) and annotation_trust_boundary (AT-01 through AT-06)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.intermediate_states import PaperMap
from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p1_extraction(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P1 hybrid multi-agent extraction chain.

    Steps:
        P1-CR:  Canonical Reader — build PaperMap (one read, many agents)
        P1-MAP: MA multi-product plan (for MA/SR papers only)
        P1-AG:  Multi-agent extraction — 11 agents in parallel
        P1-REC: Reconciliation — cross-agent consensus
        P1-ATB: Annotation Trust Boundary — validate + persist

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with ingested_paper, triage_result.

    Returns:
        Updated context with paper_map, agent outputs, validated annotations.
    """
    ingested = context["ingested_paper"]
    paper_id = context["paper_id"]
    extraction_run_id = context["extraction_run_id"]
    extraction_mode = context.get("extraction_mode", "STANDARD")

    # ── P1-CR: Canonical Reader ──
    logger.info("P1-CR: Building PaperMap for %s", paper_id)

    from crci.extraction.p1_extraction.canonical_reader import CanonicalReader
    from crci.llm.client import LLMClient

    llm_client = LLMClient()
    reader = CanonicalReader(llm_client)

    canonical_text = ingested.get("canonical_text", "")
    paper_map: PaperMap = reader.read(
        paper_id=paper_id,
        canonical_text=canonical_text,
    )
    context["paper_map"] = paper_map

    logger.info(
        "P1-CR complete: sections=%d, tables=%d, figures=%d, spans=%d",
        len(paper_map.sections),
        len(paper_map.tables),
        len(paper_map.figures),
        len(paper_map.candidate_spans),
    )

    # ── P1-MAP: MA Multi-Product Plan ──
    # For meta-analysis and systematic review papers, build an extraction plan
    # with up to 7 products (pooled estimate, heterogeneity, forest plot, etc.)
    paper_subtype = context.get("triage_result", {})
    subtype_str = (
        paper_subtype.paper_subtype
        if hasattr(paper_subtype, "paper_subtype")
        else context.get("classified_paper", {}).get("paper_subtype", "")
    )
    subtype_val = subtype_str.value if hasattr(subtype_str, "value") else str(subtype_str)

    ma_subtypes = {"meta_analysis", "systematic_review"}
    if subtype_val in ma_subtypes:
        from crci.extraction.p1_extraction.ma_multi_product import (
            build_ma_extraction_plan,
            get_product_agents,
        )

        ma_plan = build_ma_extraction_plan(
            paper_id=paper_id,
            paper_subtype=subtype_val,
            paper_text=canonical_text,
            title=ingested.get("metadata", {}).get("title"),
        )
        context["ma_extraction_plan"] = ma_plan
        logger.info(
            "P1-MAP: MA plan built — %d products (%d mandatory), "
            "NMA=%s, dose-response=%s",
            ma_plan.product_count,
            len(ma_plan.mandatory_products),
            ma_plan.is_network_ma,
            ma_plan.is_dose_response_ma,
        )
    else:
        context["ma_extraction_plan"] = None
        logger.debug("P1-MAP: not an MA/SR paper, skipping MA plan")

    # ── P1-AG: Multi-Agent Extraction ──
    logger.info("P1-AG: Running %s-mode extraction agents", extraction_mode)

    from crci.extraction.p1_extraction.agents.base_agent import BaseAgent

    # Import all agents
    from crci.extraction.p1_extraction.agents.ag01_metadata import MetadataAgent
    from crci.extraction.p1_extraction.agents.ag02_design import DesignAgent
    from crci.extraction.p1_extraction.agents.ag03_cohort import CohortAgent
    from crci.extraction.p1_extraction.agents.ag04_outcome import OutcomeAgent
    from crci.extraction.p1_extraction.agents.ag05_stats_label import StatsLabelAgent
    from crci.extraction.p1_extraction.agents.ag06_exposure import ExposureAgent
    from crci.extraction.p1_extraction.agents.ag07_mediator import MediatorAgent
    from crci.extraction.p1_extraction.agents.ag08_temporal import TemporalAgent
    from crci.extraction.p1_extraction.agents.ag10_strategic_intel import StrategicIntelAgent
    from crci.extraction.p1_extraction.agents.ag11_instrument_validation import InstrumentValidationAgent

    agents: list[BaseAgent] = [
        MetadataAgent(llm_client),
        DesignAgent(llm_client),
        CohortAgent(llm_client),
        OutcomeAgent(llm_client),
        StatsLabelAgent(llm_client),
        ExposureAgent(llm_client),
        MediatorAgent(llm_client),
        TemporalAgent(llm_client),
        StrategicIntelAgent(llm_client),
        InstrumentValidationAgent(llm_client),
    ]

    all_raw_annotations: list[Any] = []
    all_agent_outputs: list[Any] = []
    for agent in agents:
        agent_name = agent.__class__.__name__
        logger.info("Running agent %s", agent_name)
        try:
            agent_output = agent.extract(paper_map)
            all_agent_outputs.append(agent_output)
            all_raw_annotations.extend(agent_output.annotations)
            logger.info(
                "Agent %s produced %d annotations, %d span_labels",
                agent_name, len(agent_output.annotations),
                len(agent_output.span_labels),
            )
        except Exception as exc:
            logger.error("Agent %s failed: %s", agent_name, exc)
            # Continue with other agents — partial extraction is better than none

    context["raw_annotations"] = all_raw_annotations
    context["agent_outputs"] = all_agent_outputs
    logger.info("P1-AG complete: %d total raw annotations", len(all_raw_annotations))

    # ── P1-REC: Reconciliation ──
    logger.info("P1-REC: Reconciling cross-agent annotations")
    from crci.extraction.p1_extraction.reconciliation import reconcile_annotations

    study_id = context.get("study_id", paper_id)
    reconciliation_result = reconcile_annotations(
        session=session,
        raw_annotations=all_raw_annotations,
        study_id=study_id,
        extraction_run_id=extraction_run_id,
    )
    context["reconciliation_result"] = reconciliation_result

    logger.info(
        "P1-REC complete: %d reconciled, %d conflicts",
        len(reconciliation_result.reconciled_annotations),
        reconciliation_result.total_conflicts,
    )

    # ── P1-ATB: Annotation Trust Boundary ──
    logger.info("P1-ATB: Validating annotations through trust boundary")
    from crci.extraction.p1_extraction.annotation_trust_boundary import validate_annotations

    atb_result = validate_annotations(
        session=session,
        reconciliation_result=reconciliation_result,
    )
    context["atb_result"] = atb_result

    logger.info(
        "P1-ATB complete: %d accepted, %d rejected",
        atb_result.total_accepted,
        atb_result.total_rejected,
    )

    return context
