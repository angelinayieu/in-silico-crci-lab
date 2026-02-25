# VERIFIED: imports — chain_validator, coverage_analyzer, evalue_computer, sufficiency_reporter
# VERIFIED: backward wiring — reads pooled estimates + bias results from P4/P4B
# VERIFIED: forward wiring — writes sufficiency report for P6 gate
"""
Component: SYS_EXTRACTION.EX-P5.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1600-1800
Purpose: Orchestrate P5 sufficiency: chain validate → coverage → E-value → report.
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
        P5-CV: Chain validator — check causal chain completeness
        P5-COV: Coverage analyzer — evidence coverage per pathway
        P5-EV: E-value computer — sensitivity to unmeasured confounding
        P5-RPT: Sufficiency reporter — generate summary grade

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context.

    Returns:
        Updated context with sufficiency report.
    """
    logger.info("P5: Running sufficiency assessment")

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
