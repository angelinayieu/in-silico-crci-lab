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

    # ── P5-CV: Chain validation ──
    from crci.extraction.p5_sufficiency.chain_validator import validate_chains

    chain_result = validate_chains(session=session)
    context["chain_validation"] = chain_result
    logger.info("P5-CV: %d chains validated", chain_result.get("n_chains", 0))

    # ── P5-COV: Coverage analysis ──
    from crci.extraction.p5_sufficiency.coverage_analyzer import analyze_coverage

    coverage = analyze_coverage(session=session)
    context["coverage_analysis"] = coverage
    logger.info("P5-COV: coverage analysis complete")

    # ── P5-EV: E-value computation ──
    from crci.extraction.p5_sufficiency.evalue_computer import compute_evalues

    evalues = compute_evalues(session=session)
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
    from crci.extraction.p5_sufficiency.sufficiency_reporter import generate_report

    sufficiency_report = generate_report(
        chain_result=chain_result,
        coverage=coverage,
        evalues=evalues,
        session=session,
    )
    context["sufficiency_report"] = sufficiency_report
    logger.info(
        "P5 complete: overall grade=%s",
        sufficiency_report.get("overall_grade", "unknown"),
    )

    return context
