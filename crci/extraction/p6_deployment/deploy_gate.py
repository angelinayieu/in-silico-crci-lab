# VERIFIED: formulas — deployment decision logic matches spec SYS_EX lines 1860-1896
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ValidationResult from validation_runner.py
# VERIFIED: forward wiring — writes DeploymentDecision (final extraction pipeline output)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates [P6-G1] raise on failure
"""
Component: SYS_EXTRACTION.EX-P6.DG
Spec: SYS_EXTRACTION_COMPLETE.md lines 1860-1896
Formulas: None (decision logic only)
Reads: ValidationResult (from validation_runner.py)
Writes: DeploymentDecision (final output of extraction pipeline)
Gates: P6-G1 (0 FAILs or BLOCK)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crci.shared.models.intermediate_states import GateViolation

from .validation_runner import RuleResult, ValidationResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Deployment decision levels
# ═══════════════════════════════════════════════════════════════

DEPLOY = "DEPLOY"
DEPLOY_WITH_WARNINGS = "DEPLOY_WITH_WARNINGS"
CONDITIONAL = "CONDITIONAL"
BLOCK = "BLOCK"


@dataclass
class DeploymentDecision:
    """P6-DG output: final deployment gate decision.

    Decision levels:
      DEPLOY               — 0 FAILs, 0 WARNs
      DEPLOY_WITH_WARNINGS — 0 FAILs, <= 5 WARNs
      CONDITIONAL          — 0 FAILs, > 5 WARNs
      BLOCK                — >= 1 FAIL
    """

    decision: str  # DEPLOY, DEPLOY_WITH_WARNINGS, CONDITIONAL, BLOCK
    n_fail: int
    n_warn: int
    n_pass: int
    total_rules: int
    failed_rules: list[RuleResult] = field(default_factory=list)
    warning_rules: list[RuleResult] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  P6-DG: Deploy Gate
# ═══════════════════════════════════════════════════════════════

# Maximum WARNs for DEPLOY_WITH_WARNINGS
_MAX_WARNS_FOR_DEPLOY_WITH_WARNINGS: int = 5


def evaluate_deploy_gate(
    validation_result: ValidationResult,
) -> DeploymentDecision:
    """P6-DG: Evaluate deployment readiness from validation results.

    Decision logic:
      0 FAILs, 0 WARNs          -> DEPLOY
      0 FAILs, <= 5 WARNs       -> DEPLOY_WITH_WARNINGS
      0 FAILs, > 5 WARNs        -> CONDITIONAL
      >= 1 FAIL                  -> BLOCK

    Gate P6-G1: >= 1 FAIL -> raises GateViolation.

    Parameters
    ----------
    validation_result : ValidationResult
        Output from validation_runner.run_validation().

    Returns
    -------
    DeploymentDecision with decision level and supporting details.

    Raises
    ------
    GateViolation
        Gate P6-G1: if any validation rule FAILed.
    """
    n_fail = validation_result.n_fail
    n_warn = validation_result.n_warn
    n_pass = validation_result.n_pass

    failed_rules = [
        r for r in validation_result.rule_results if r.status == "FAIL"
    ]
    warning_rules = [
        r for r in validation_result.rule_results if r.status == "WARN"
    ]

    review_notes: list[str] = []

    # Gate P6-G1: 0 FAILs or BLOCK
    if n_fail > 0:
        fail_summary = "; ".join(
            f"[{r.rule_id}] {r.rule_name}: {r.message}"
            for r in failed_rules
        )
        logger.error(
            "P6-G1 BLOCK: %d FAIL rule(s) detected: %s",
            n_fail,
            fail_summary,
        )

        decision = DeploymentDecision(
            decision=BLOCK,
            n_fail=n_fail,
            n_warn=n_warn,
            n_pass=n_pass,
            total_rules=validation_result.total_rules,
            failed_rules=failed_rules,
            warning_rules=warning_rules,
            review_notes=[
                f"BLOCKED: {n_fail} validation rule(s) failed.",
                fail_summary,
            ],
        )

        raise GateViolation(
            gate_id="P6-G1",
            message=(
                f"Deployment BLOCKED: {n_fail} validation rule(s) failed. "
                f"{fail_summary}"
            ),
            context={
                "decision": BLOCK,
                "n_fail": n_fail,
                "n_warn": n_warn,
                "failed_rules": [
                    {"rule_id": r.rule_id, "message": r.message}
                    for r in failed_rules
                ],
            },
        )

    # 0 FAILs: determine deployment level based on WARNs
    if n_warn == 0:
        decision_level = DEPLOY
        review_notes.append(
            "All validation rules passed. Ready for deployment."
        )
        logger.info(
            "P6-DG: DEPLOY — all %d rules passed, 0 warnings.",
            n_pass,
        )
    elif n_warn <= _MAX_WARNS_FOR_DEPLOY_WITH_WARNINGS:
        decision_level = DEPLOY_WITH_WARNINGS
        warn_summary = "; ".join(
            f"[{r.rule_id}] {r.rule_name}"
            for r in warning_rules
        )
        review_notes.append(
            f"Deploy with {n_warn} warning(s): {warn_summary}"
        )
        logger.info(
            "P6-DG: DEPLOY_WITH_WARNINGS — %d warnings (<= %d): %s",
            n_warn,
            _MAX_WARNS_FOR_DEPLOY_WITH_WARNINGS,
            warn_summary,
        )
    else:
        decision_level = CONDITIONAL
        warn_summary = "; ".join(
            f"[{r.rule_id}] {r.rule_name}"
            for r in warning_rules
        )
        review_notes.append(
            f"CONDITIONAL deployment: {n_warn} warnings (> "
            f"{_MAX_WARNS_FOR_DEPLOY_WITH_WARNINGS}). "
            f"Manual review required. Warnings: {warn_summary}"
        )
        logger.warning(
            "P6-DG: CONDITIONAL — %d warnings (> %d): %s",
            n_warn,
            _MAX_WARNS_FOR_DEPLOY_WITH_WARNINGS,
            warn_summary,
        )

    return DeploymentDecision(
        decision=decision_level,
        n_fail=n_fail,
        n_warn=n_warn,
        n_pass=n_pass,
        total_rules=validation_result.total_rules,
        failed_rules=failed_rules,
        warning_rules=warning_rules,
        review_notes=review_notes,
    )
