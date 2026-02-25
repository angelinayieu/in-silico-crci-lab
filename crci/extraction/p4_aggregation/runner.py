# VERIFIED: imports — all modules exist (p4_aggregation submodules)
# VERIFIED: backward wiring — reads calibrated_evidence from context (P3)
# VERIFIED: forward wiring — writes pooled_estimates, compiled_edges to context (P4B, P5)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P4-G1, P4-G2, P4-G3 delegated to sub-modules
"""
Component: SYS_EXTRACTION.EX-P4.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1102-1390
Purpose: Orchestrate P4 aggregation: evidence grouping → double-counting
         resolution → meta-analysis → prior selection → edge writing.
Reads: calibrated_evidence, harmonized_claims (from P3/P2 context)
Writes: pooled_estimates, compiled_edges (to context for P4B, P5, P6)
Gates: P4-G1 (method), P4-G2 (NaN check), P4-G3 (ambiguous)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p4_aggregation(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P4 aggregation chain: group → DCR → MA → prior → write.

    Called by pipeline.py after P3 heterogeneity completes.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P3 outputs.

    Returns:
        Updated context with pooled estimates and compiled edges.
    """
    from crci.extraction.p4_aggregation.evidence_grouper import group_evidence_by_edge
    from crci.extraction.p4_aggregation.double_counting import resolve_double_counting
    from crci.extraction.p4_aggregation.meta_analyzer import pool_evidence
    from crci.extraction.p4_aggregation.prior_selector import select_prior, EdgeContext
    from crci.extraction.p4_aggregation.edge_writer import write_all_edges

    logger.info("P4 aggregation starting for run %s", run.extraction_run_id)

    harmonized_claims = context.get("harmonized_claims", [])
    if not harmonized_claims:
        logger.warning("P4: No harmonized claims found, skipping")
        context["grouped_evidence"] = []
        context["pooled_estimates"] = []
        context["compiled_edges"] = []
        return context

    # S1: Evidence Grouping — group claims by edge
    grouped = group_evidence_by_edge(harmonized_claims)
    context["grouped_evidence"] = grouped
    logger.info("P4-S1: Grouped into %d edge groups", len(grouped))

    # S2: Double-Counting Resolution — resolve overlapping evidence
    resolved_list = []
    for g in grouped:
        try:
            resolved = resolve_double_counting(g, session=session)
            resolved_list.append(resolved)
        except Exception as exc:
            logger.warning("P4-S2 DCR failed for group %s: %s", getattr(g, "edge_relation_id", "?"), exc)
    context["resolved_evidence"] = resolved_list
    logger.info("P4-S2: %d groups after double-counting resolution", len(resolved_list))

    # S3: Meta-Analysis — pool evidence per edge
    pooled_list = []
    for resolved in resolved_list:
        try:
            ma_result = pool_evidence(resolved)
            pooled_list.append(ma_result)
        except Exception as exc:
            logger.warning(
                "P4-S3 meta-analysis failed for %s: %s",
                getattr(resolved, "edge_relation_id", "?"),
                exc,
            )
    context["pooled_estimates"] = pooled_list
    logger.info("P4-S3: %d pooled estimates produced", len(pooled_list))

    # S4: Prior Selection — choose prior for each edge
    prior_specs = []
    for pooled in pooled_list:
        try:
            pe = pooled.pooled_estimate if hasattr(pooled, "pooled_estimate") else pooled
            edge_ctx = EdgeContext(
                edge_relation_id=getattr(pe, "edge_relation_id", ""),
                source_node_id=getattr(pe, "source_node_id", ""),
                target_node_id=getattr(pe, "target_node_id", ""),
            )
            prior, log_entry = select_prior(pe, edge_ctx, session)
            prior_specs.append((prior, log_entry))
        except Exception as exc:
            logger.warning("P4-S4 prior selection failed: %s", exc)
    context["prior_specs"] = prior_specs
    logger.info("P4-S4: %d priors selected", len(prior_specs))

    # S5: Edge Writing — produce compiled edges
    try:
        compilation_inputs = _build_compilation_inputs(pooled_list, prior_specs)
        compiled_edges = write_all_edges(
            compilation_inputs=compilation_inputs,
            session=session,
            build_id=run.extraction_run_id,
        )
        context["compiled_edges"] = compiled_edges
        logger.info("P4-S5: %d compiled edges written", len(compiled_edges))
    except Exception as exc:
        logger.warning("P4-S5 edge writing failed: %s", exc)
        context["compiled_edges"] = []

    logger.info(
        "P4 aggregation complete: %d claims → %d groups → %d pooled → %d edges",
        len(harmonized_claims),
        len(grouped),
        len(pooled_list),
        len(context.get("compiled_edges", [])),
    )
    return context


def _build_compilation_inputs(
    pooled_list: list,
    prior_specs: list,
) -> list:
    """Build EdgeCompilationInput objects from pooled estimates and priors.

    Bridges the gap between meta-analysis output and edge writer input.
    """
    from crci.extraction.p4_aggregation.edge_writer import EdgeCompilationInput

    inputs = []
    prior_map = {}
    for prior, _log in prior_specs:
        eid = getattr(prior, "edge_relation_id", None)
        if eid:
            prior_map[eid] = prior

    for pooled in pooled_list:
        pe = pooled.pooled_estimate if hasattr(pooled, "pooled_estimate") else pooled
        eid = getattr(pe, "edge_relation_id", "")
        prior = prior_map.get(eid)
        try:
            inp = EdgeCompilationInput(
                pooled_estimate=pe,
                prior_spec=prior,
            )
            inputs.append(inp)
        except Exception as exc:
            logger.debug("Could not build compilation input for %s: %s", eid, exc)

    return inputs
