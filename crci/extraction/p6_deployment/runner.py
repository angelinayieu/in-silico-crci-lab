# VERIFIED: imports — deploy_gate, validation_runner
# VERIFIED: backward wiring — reads sufficiency report from P5
# VERIFIED: forward wiring — gate decision consumed by P7
# VERIFIED: gates — P6-G1 (deployment readiness)
"""
Component: SYS_EXTRACTION.EX-P6.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1800-1950
Purpose: Orchestrate P6 deployment validation gate.
         Must pass before P7 compilation proceeds.
Reads: Sufficiency report from P5
Writes: Gate decision (PASS/BLOCK) — P7 only runs on PASS
Gates: P6-G1 (deployment readiness — BLOCK creates review task)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p6_deployment_validation(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P6 deployment validation gate.

    Steps:
        P6-VAL: Validation runner — comprehensive check suite
        P6-GATE: Deploy gate — final PASS/BLOCK decision

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with sufficiency report.

    Returns:
        Updated context with deployment decision.

    Raises:
        GateViolation: P6-G1 if deployment is blocked.
    """
    logger.info("P6: Running deployment validation")

    # ── P6-VAL: Validation Runner ──
    from crci.extraction.p6_deployment.validation_runner import run_validations

    validation_result = run_validations(session=session, context=context)
    context["validation_result"] = validation_result
    logger.info(
        "P6-VAL: %d checks passed, %d warnings, %d errors",
        validation_result.get("passed", 0),
        validation_result.get("warnings", 0),
        validation_result.get("errors", 0),
    )

    # ── P6-GATE: Deploy Gate ──
    from crci.extraction.p6_deployment.deploy_gate import check_deploy_gate

    gate_decision = check_deploy_gate(
        validation_result=validation_result,
        sufficiency_report=context.get("sufficiency_report", {}),
        session=session,
    )
    context["deploy_gate_decision"] = gate_decision

    if gate_decision.get("decision") == "BLOCK":
        logger.warning(
            "P6-G1: Deployment BLOCKED — %s",
            gate_decision.get("reason", "unknown reason"),
        )
        raise GateViolation(
            "P6-G1",
            f"Deployment blocked: {gate_decision.get('reason', 'unknown')}",
            gate_decision,
        )

    logger.info("P6 complete: deployment gate PASSED")
    return context
