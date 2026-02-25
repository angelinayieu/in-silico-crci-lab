# VERIFIED: imports — all modules exist (p5_sufficiency submodules)
# VERIFIED: backward wiring — reads compiled_edges, bias_assessments from context (P4/P4B)
# VERIFIED: forward wiring — writes sufficiency_report to context (P6)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P5-G1, P5-G2 delegated to sub-modules
"""
Component: SYS_EXTRACTION.EX-P5.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1535-1786
Purpose: Orchestrate P5 sufficiency assessment: coverage analysis →
         chain validation → E-value computation → sufficiency reporting.
Reads: compiled_edges, bias_assessments (from P4/P4B context)
Writes: sufficiency_report, evidence_gaps (to context for P6)
Gates: P5-G1 (coverage), P5-G2 (chain consistency)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p5_sufficiency(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P5 sufficiency chain: coverage → chains → E-values → report.

    Called by pipeline.py after P4B publication bias completes.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P4/P4B outputs.

    Returns:
        Updated context with sufficiency report and evidence gaps.
    """
    from crci.extraction.p5_sufficiency.coverage_analyzer import build_coverage_matrix
    from crci.extraction.p5_sufficiency.chain_validator import validate_all_pathways
    from crci.extraction.p5_sufficiency.evalue_computer import compute_evalues_batch
    from crci.extraction.p5_sufficiency.sufficiency_reporter import generate_sufficiency_report

    logger.info("P5 sufficiency starting for run %s", run.extraction_run_id)

    compiled_edges = context.get("compiled_edges", [])
    bias_assessments = context.get("bias_assessments", [])

    if not compiled_edges:
        logger.warning("P5: No compiled edges found, skipping")
        context["sufficiency_report"] = None
        context["evidence_gaps"] = []
        return context

    # S1: Coverage Analysis
    coverage_matrix = build_coverage_matrix(compiled_edges)
    context["coverage_matrix"] = coverage_matrix
    logger.info(
        "P5-S1: Coverage matrix built (%d edges analyzed)",
        len(compiled_edges),
    )

    # S2: Chain Validation — validate pathway consistency
    pathways = context.get("pathway_definitions", [])
    chain_results = []
    edge_se_inflations = {}
    if pathways:
        edge_dict = {
            getattr(e, "edge_id", getattr(e, "edge_relation_id", str(i))): e
            for i, e in enumerate(compiled_edges)
        }
        try:
            chain_results, edge_se_inflations = validate_all_pathways(
                pathways=pathways,
                compiled_edges=edge_dict,
            )
            context["chain_validation_results"] = chain_results
            logger.info("P5-S2: %d pathways validated", len(chain_results))
        except Exception as exc:
            logger.warning("P5-S2 chain validation failed: %s", exc)
    else:
        logger.info("P5-S2: No pathway definitions available, skipping chain validation")

    # S3: E-Value Computation
    try:
        evalue_results = compute_evalues_batch(compiled_edges)
        context["evalue_results"] = evalue_results
        logger.info("P5-S3: E-values computed for %d edges", len(evalue_results))
    except Exception as exc:
        logger.warning("P5-S3 E-value computation failed: %s", exc)
        evalue_results = []

    # S4: Sufficiency Report
    try:
        report = generate_sufficiency_report(
            compiled_edges=compiled_edges,
            coverage_matrix=coverage_matrix,
            chain_results=chain_results if chain_results else None,
            bias_assessments=bias_assessments if bias_assessments else None,
            evalue_results=evalue_results if evalue_results else None,
        )
        context["sufficiency_report"] = report
        context["evidence_gaps"] = getattr(report, "evidence_gaps", [])
        logger.info("P5-S4: Sufficiency report generated")
    except Exception as exc:
        logger.warning("P5-S4 sufficiency reporting failed: %s", exc)
        context["sufficiency_report"] = None
        context["evidence_gaps"] = []

    logger.info("P5 sufficiency complete for run %s", run.extraction_run_id)
    return context
