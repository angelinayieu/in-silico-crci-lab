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

    For systematic reviews: SR papers don't produce edge evidence directly.
    Their value is in identifying constituent studies for hop discovery.
    If the paper is an SR/MA with detected included studies, G1 is exempted.

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

    # ── Detect SR/MA paper type ──
    classified_paper = context.get("classified_paper", {})
    paper_subtype = classified_paper.get("paper_subtype", "")
    if hasattr(paper_subtype, "value"):
        paper_subtype = paper_subtype.value
    is_sr_or_ma = str(paper_subtype) in {
        "systematic_review", "meta_analysis",
    }

    # ── Build compiled edges for validation ──
    compiled_edges = context.get("compiled_edges", [])
    sufficiency_report = context.get("sufficiency_report")
    bias_results = context.get("bias_results")

    # ── SR exemption: if no edges but SR detected included studies ──
    ma_plan = context.get("ma_extraction_plan")
    has_included_studies = (
        ma_plan is not None
        and hasattr(ma_plan, "products")
        and len(ma_plan.products) > 0
    )

    if is_sr_or_ma and not compiled_edges and has_included_studies:
        logger.info(
            "P6: SR/MA paper with no direct edges — applying SR exemption. "
            "SR value is in constituent study identification, not edge production."
        )
        # Build a minimal validation result that passes G1
        from crci.extraction.p6_deployment.validation_runner import (
            RuleResult,
            ValidationResult,
        )
        sr_result = ValidationResult(
            rule_results=[
                RuleResult(
                    rule_id="G1",
                    rule_name="minimum_edges",
                    status="PASS",
                    message=(
                        "SR/MA exemption: no direct edges expected. "
                        f"Paper subtype={paper_subtype}, MA plan has "
                        f"{len(ma_plan.products)} products."
                    ),
                ),
            ],
            n_pass=1,
            n_warn=0,
            n_fail=0,
            total_rules=1,
        )
        context["validation_result"] = sr_result
        context["deploy_gate_decision"] = {
            "decision": "DEPLOY_SR",
            "reason": "SR/MA paper — edges come from constituent studies via hop discovery",
        }
        logger.info("P6 complete: SR exemption applied — DEPLOY_SR")
        return context

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
