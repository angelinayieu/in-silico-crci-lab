# VERIFIED: imports — all modules exist (p6_deployment submodules)
# VERIFIED: backward wiring — reads compiled_edges, sufficiency_report from context (P4/P5)
# VERIFIED: forward wiring — writes deployment_status to context (P7)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P6-G1 (deployment gate) delegated to deploy_gate.py
"""
Component: SYS_EXTRACTION.EX-P6.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1787-1898
Purpose: Orchestrate P6 deployment validation: run G1-G18 validation rules
         and evaluate the deployment gate decision.
Reads: compiled_edges, sufficiency_report (from P4/P5 context)
Writes: deployment_status (to context for P7 / pipeline decision)
Gates: P6-G1 (deployment gate) → DEPLOY / DEPLOY_WITH_WARNINGS / CONDITIONAL / BLOCK
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p6_deployment_validation(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P6 deployment validation chain.

    Executes G1-G18 validation rules on compiled edges and evaluates
    the deployment gate to produce a DEPLOY/BLOCK decision.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P4/P5 outputs.

    Returns:
        Updated context with deployment status.
    """
    from crci.extraction.p6_deployment.validation_runner import run_validation
    from crci.extraction.p6_deployment.deploy_gate import evaluate_deploy_gate

    logger.info("P6 deployment validation starting for run %s", run.extraction_run_id)

    compiled_edges = context.get("compiled_edges", [])
    sufficiency_report = context.get("sufficiency_report")
    bias_assessments = context.get("bias_assessments", [])

    if not compiled_edges:
        logger.warning("P6: No compiled edges found, setting BLOCK")
        context["deployment_status"] = {
            "decision": "BLOCK",
            "reason": "No compiled edges available for validation",
        }
        return context

    # S1: Run G1-G18 validation rules
    try:
        validation_result = run_validation(
            compiled_edges=compiled_edges,
            sufficiency_report=sufficiency_report,
            bias_assessments=bias_assessments if bias_assessments else None,
        )
        context["validation_result"] = validation_result
        logger.info(
            "P6-S1: Validation complete — %d PASS, %d WARN, %d FAIL",
            validation_result.n_pass,
            validation_result.n_warn,
            validation_result.n_fail,
        )
    except Exception as exc:
        logger.error("P6-S1 validation failed: %s", exc)
        context["deployment_status"] = {
            "decision": "BLOCK",
            "reason": f"Validation execution failed: {exc}",
        }
        return context

    # S2: Evaluate deployment gate
    try:
        decision = evaluate_deploy_gate(validation_result)
        context["deployment_status"] = {
            "decision": decision.decision,
            "review_notes": decision.review_notes,
            "n_pass": validation_result.n_pass,
            "n_warn": validation_result.n_warn,
            "n_fail": validation_result.n_fail,
        }
        logger.info("P6-S2: Deployment decision = %s", decision.decision)
    except Exception as exc:
        logger.error("P6-S2 deploy gate failed: %s", exc)
        context["deployment_status"] = {
            "decision": "BLOCK",
            "reason": f"Deploy gate evaluation failed: {exc}",
        }

    logger.info("P6 deployment validation complete for run %s", run.extraction_run_id)
    return context
