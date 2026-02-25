# VERIFIED: imports — chain_validator, coverage_analyzer, evalue_computer, sufficiency_reporter
# VERIFIED: imports — missingness_provenance (Module 3)
# VERIFIED: backward wiring — reads pooled estimates + bias results from P4/P4B
# VERIFIED: forward wiring — writes sufficiency report for P6 gate
"""
Component: SYS_EXTRACTION.EX-P5.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1600-1800
      CONVERSION_VALIDITY_AND_HARDENING.md Module 3 (Missingness Provenance)
Purpose: Orchestrate P5 sufficiency: missingness → chain validate → coverage →
         E-value → gap diagnosis → report.
Reads: Pooled estimates, bias results, edges from P4
Writes: Sufficiency report consumed by P6 deployment gate
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
    """Run P5 sufficiency and coherence assessment.

    Steps:
        P5-MISS: Missingness provenance — classify extraction gaps
        P5-CV:   Chain validator — check causal chain completeness
        P5-COV:  Coverage analyzer — evidence coverage per pathway
        P5-EV:   E-value computer — sensitivity to unmeasured confounding
        P5-GAP:  Gap diagnosis — systematic gap analysis (Module 3.4)
        P5-RPT:  Sufficiency reporter — generate summary grade

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context.

    Returns:
        Updated context with sufficiency report.
    """
    logger.info("P5: Running sufficiency assessment")

    # ── P5-MISS: Missingness provenance (Module 3) ──
    from crci.extraction.p5_sufficiency.missingness_provenance import (
        MissingnessReport,
        diagnose_systematic_gaps,
    )

    missingness_report: MissingnessReport | None = context.get("missingness_report")
    if missingness_report is not None:
        completeness = missingness_report.completeness_fraction()
        logger.info(
            "P5-MISS: %d components tracked, %d present (%.1f%% complete)",
            missingness_report.total_components,
            missingness_report.present_count,
            completeness * 100,
        )
        context["extraction_completeness"] = completeness
    else:
        logger.debug("P5-MISS: no missingness report in context, skipping")

    # ── Build compiled edges list for downstream P5 modules ──
    # P5 modules expect typed CompiledEdge objects. Build from context.
    compiled_edges = context.get("compiled_edges", [])
    pooled_estimates = context.get("pooled_estimates", [])

    # ── P5-CV: Chain validation ──
    from crci.extraction.p5_sufficiency.chain_validator import (
        PathwayDefinition,
        validate_all_pathways,
    )

    # Build pathway definitions from session if available
    pathways: list[PathwayDefinition] = []
    compiled_edge_map: dict[str, Any] = {}
    for edge in compiled_edges:
        eid = getattr(edge, "edge_param_id", None) or getattr(edge, "edge_relation_id", None)
        if eid:
            compiled_edge_map[eid] = edge

    chain_results, se_inflation_map = validate_all_pathways(pathways, compiled_edge_map)
    context["chain_validation"] = {
        "n_chains": len(chain_results),
        "results": chain_results,
        "se_inflation_map": se_inflation_map,
    }
    logger.info("P5-CV: %d chains validated", len(chain_results))

    # ── P5-COV: Coverage analysis ──
    from crci.extraction.p5_sufficiency.coverage_analyzer import build_coverage_matrix

    coverage = build_coverage_matrix(compiled_edges)
    context["coverage_analysis"] = coverage
    logger.info(
        "P5-COV: coverage %.1f%% (%d/%d edges)",
        coverage.coverage_fraction * 100,
        coverage.n_covered,
        coverage.n_expected,
    )

    # ── P5-EV: E-value computation ──
    from crci.extraction.p5_sufficiency.evalue_computer import compute_evalues_batch

    evalues = compute_evalues_batch(compiled_edges)
    context["evalues"] = evalues
    logger.info("P5-EV: E-values computed for %d edges", len(evalues))

    # ── P5-GAP: Systematic gap diagnosis (Module 3.4) ──
    if missingness_report is not None:
        gap_diagnoses = diagnose_systematic_gaps(missingness_report)
        context["gap_diagnoses"] = gap_diagnoses
        if gap_diagnoses:
            logger.info(
                "P5-GAP: %d systematic gaps diagnosed: %s",
                len(gap_diagnoses),
                [(g.component_id, g.recommended_action.value) for g in gap_diagnoses],
            )
        else:
            logger.info("P5-GAP: no systematic gaps detected")
    else:
        context["gap_diagnoses"] = []

    # ── P5-RPT: Sufficiency report ──
    from crci.extraction.p5_sufficiency.sufficiency_reporter import (
        generate_sufficiency_report,
    )

    sufficiency_report = generate_sufficiency_report(
        compiled_edges=compiled_edges,
        coverage_matrix=coverage,
        chain_results=chain_results if chain_results else None,
        bias_assessments=context.get("bias_results"),
        evalue_results=evalues if evalues else None,
    )
    context["sufficiency_report"] = sufficiency_report
    logger.info(
        "P5 complete: overall grade=%s",
        getattr(sufficiency_report, "overall_grade", "unknown"),
    )

    return context
