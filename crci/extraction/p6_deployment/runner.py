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
        P6-VAL: Validation runner — comprehensive check suite (G1-G18)
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

    # ── Build compiled edges for validation ──
    compiled_edges = context.get("compiled_edges", [])
    sufficiency_report = context.get("sufficiency_report")
    bias_results = context.get("bias_results")

    # ── P6-VAL: Validation Runner (G1-G18 rules) ──
    from crci.extraction.p6_deployment.validation_runner import run_validation

    validation_result = run_validation(
        compiled_edges=compiled_edges,
        sufficiency_report=sufficiency_report,
        bias_assessments=bias_results,
    )
    context["validation_result"] = validation_result
    logger.info(
        "P6-VAL: %d passed, %d warnings, %d failed",
        validation_result.n_pass,
        validation_result.n_warn,
        validation_result.n_fail,
    )

    # ── P6-GATE: Deploy Gate ──
    from crci.extraction.p6_deployment.deploy_gate import evaluate_deploy_gate

    gate_decision = evaluate_deploy_gate(validation_result)
    context["deploy_gate_decision"] = gate_decision

    if gate_decision.decision == "BLOCK":
        logger.warning(
            "P6-G1: Deployment BLOCKED — %s",
            gate_decision.reason,
        )
        raise GateViolation(
            "P6-G1",
            f"Deployment blocked: {gate_decision.reason}",
            {"decision": gate_decision.decision, "reason": gate_decision.reason},
        )

    logger.info("P6 complete: deployment gate %s", gate_decision.decision)
    return context
