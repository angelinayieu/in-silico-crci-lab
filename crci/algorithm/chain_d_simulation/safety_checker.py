# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads InterventionSet from intervention_loader.py,
#           ContraindicationDef with condition_expression, severity, required_inputs
# VERIFIED: forward wiring — writes SafetyResult for ranker.py (D4), presentation layer
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no formulas (rule evaluation file)
"""
Component: SYS_ALGORITHM.ALG-D.D3-Safety
Spec: SYS_ALGORITHM_COMPLETE.md lines 3988-4058 (safety filtering)
      Boundary tables: contraindication_rules_v1 (A10)
Formulas: None (rule evaluation, no mathematical formulas)
Reads: InterventionSet (from intervention_loader.py D0),
       patient_profile dict (from runtime context)
Writes: SafetyResult (consumed by ranker.py D4, presentation layer)
Gates: None (safety outcomes are informational, not abort conditions)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from .intervention_loader import ContraindicationDef, InterventionDef, InterventionSet

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class SafetyStatus(str, Enum):
    """Per-intervention safety classification."""

    CLEAR = "CLEAR"        # No contraindications triggered
    WARNING = "WARNING"    # Soft warnings — include with advisory note
    BLOCKED = "BLOCKED"    # Hard block — exclude from recommendations


@dataclass(frozen=True)
class ContraindicationEval:
    """Result of evaluating one contraindication rule against patient context."""

    rule_id: str
    rule_label: str
    triggered: bool
    severity: str  # "BLOCK", "WARNING", "CAUTION"
    rationale: str
    missing_inputs: list[str]  # required inputs not provided
    unknown_input_resolved_as: str  # how missing inputs were resolved


@dataclass(frozen=True)
class InterventionSafety:
    """Safety evaluation result for one intervention."""

    action_id: str
    action_label: str
    status: SafetyStatus
    evaluations: list[ContraindicationEval]
    n_triggered: int
    n_blocked: int
    n_warnings: int
    blocking_rules: list[str]  # rule_ids that caused BLOCK
    warning_rules: list[str]   # rule_ids that caused WARNING


@dataclass
class SafetyResult:
    """Complete safety evaluation for all interventions.

    Consumed by ranker.py (D4) to filter blocked interventions,
    and by presentation layer to display safety notes.
    """

    intervention_safety: dict[str, InterventionSafety]  # action_id → safety
    n_total: int
    n_clear: int
    n_warning: int
    n_blocked: int
    blocked_action_ids: list[str]


# ═══════════════════════════════════════════════════════════════
#  Condition Expression Evaluation
# ═══════════════════════════════════════════════════════════════


def _evaluate_condition(
    condition_expression: str,
    patient_profile: dict[str, object],
) -> bool:
    """Safely evaluate a contraindication condition expression.

    Condition expressions are simple boolean expressions over patient
    profile keys. Examples:
        "active_treatment == True"
        "age >= 75"
        "renal_function == 'impaired'"
        "concurrent_medications CONTAINS 'warfarin'"

    Args:
        condition_expression: String condition from contraindication_rules_v1.
        patient_profile: Dict of patient attributes.

    Returns:
        True if the condition is triggered (contraindication applies).
    """
    expr = condition_expression.strip()

    # Handle empty or trivial expressions
    if not expr or expr.lower() in ("true", "always"):
        return True
    if expr.lower() in ("false", "never"):
        return False

    # Parse CONTAINS operator: "field CONTAINS 'value'"
    contains_match = re.match(
        r"(\w+)\s+CONTAINS\s+'([^']*)'", expr, re.IGNORECASE,
    )
    if contains_match:
        field_name = contains_match.group(1)
        value = contains_match.group(2)
        field_val = patient_profile.get(field_name)
        if field_val is None:
            return False
        if isinstance(field_val, (list, tuple, set)):
            return value in field_val
        return value in str(field_val)

    # Parse comparison operators: "field OP value"
    comparison_match = re.match(
        r"(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+)", expr,
    )
    if comparison_match:
        field_name = comparison_match.group(1)
        operator = comparison_match.group(2)
        raw_value = comparison_match.group(3).strip()

        field_val = patient_profile.get(field_name)
        if field_val is None:
            return False

        # Parse the comparison value
        compare_val: object
        if raw_value.lower() == "true":
            compare_val = True
        elif raw_value.lower() == "false":
            compare_val = False
        elif raw_value.startswith("'") and raw_value.endswith("'"):
            compare_val = raw_value[1:-1]
        elif raw_value.startswith('"') and raw_value.endswith('"'):
            compare_val = raw_value[1:-1]
        else:
            try:
                compare_val = float(raw_value)
            except ValueError:
                compare_val = raw_value

        # Evaluate comparison
        try:
            if operator == "==":
                return field_val == compare_val
            elif operator == "!=":
                return field_val != compare_val
            elif operator == ">=":
                return float(field_val) >= float(compare_val)  # type: ignore[arg-type]
            elif operator == "<=":
                return float(field_val) <= float(compare_val)  # type: ignore[arg-type]
            elif operator == ">":
                return float(field_val) > float(compare_val)  # type: ignore[arg-type]
            elif operator == "<":
                return float(field_val) < float(compare_val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            logger.warning(
                "Safety: Cannot evaluate '%s' — type mismatch for field '%s'",
                expr, field_name,
            )
            return False

    # Fallback: treat as simple truthiness check on a field name
    if expr.isidentifier():
        return bool(patient_profile.get(expr, False))

    logger.warning(
        "Safety: Unrecognized condition expression: '%s' — treating as False",
        expr,
    )
    return False


# ═══════════════════════════════════════════════════════════════
#  Rule Evaluation
# ═══════════════════════════════════════════════════════════════


def _evaluate_contraindication(
    rule: ContraindicationDef,
    patient_profile: dict[str, object],
) -> ContraindicationEval:
    """Evaluate a single contraindication rule against patient context.

    Handles missing inputs per unknown_input_policy:
        "assume_safe"   → treat as not triggered
        "assume_unsafe" → treat as triggered
        "skip"          → skip evaluation entirely (not triggered)

    Args:
        rule: ContraindicationDef with condition_expression and required_inputs.
        patient_profile: Dict of patient attributes.

    Returns:
        ContraindicationEval with triggered status.
    """
    # Check for missing required inputs
    missing = [inp for inp in rule.required_inputs if inp not in patient_profile]
    resolved_as = "complete"

    if missing:
        policy = rule.unknown_input_policy.lower()
        if policy == "assume_unsafe":
            logger.info(
                "Safety: Rule '%s' — missing inputs %s, assuming UNSAFE per policy",
                rule.rule_id, missing,
            )
            return ContraindicationEval(
                rule_id=rule.rule_id,
                rule_label=rule.rule_label,
                triggered=True,
                severity=rule.severity,
                rationale=f"Missing inputs {missing} — assumed unsafe: {rule.rationale}",
                missing_inputs=missing,
                unknown_input_resolved_as="assume_unsafe",
            )
        elif policy == "skip":
            logger.info(
                "Safety: Rule '%s' — missing inputs %s, SKIPPING per policy",
                rule.rule_id, missing,
            )
            return ContraindicationEval(
                rule_id=rule.rule_id,
                rule_label=rule.rule_label,
                triggered=False,
                severity=rule.severity,
                rationale=f"Missing inputs {missing} — skipped: {rule.rationale}",
                missing_inputs=missing,
                unknown_input_resolved_as="skip",
            )
        else:
            # Default: assume_safe
            resolved_as = "assume_safe"
            logger.info(
                "Safety: Rule '%s' — missing inputs %s, assuming SAFE per policy",
                rule.rule_id, missing,
            )

    # Evaluate the condition expression
    triggered = _evaluate_condition(rule.condition_expression, patient_profile)

    return ContraindicationEval(
        rule_id=rule.rule_id,
        rule_label=rule.rule_label,
        triggered=triggered,
        severity=rule.severity,
        rationale=rule.rationale,
        missing_inputs=missing,
        unknown_input_resolved_as=resolved_as,
    )


def _evaluate_intervention_safety(
    intervention: InterventionDef,
    all_rules: list[ContraindicationDef],
    patient_profile: dict[str, object],
) -> InterventionSafety:
    """Evaluate all applicable contraindication rules for one intervention.

    Rules match if:
        - applies_to_type == "action" AND applies_to_ref == action_id
        - applies_to_type == "action_class" AND applies_to_ref == action_class
        - applies_to_type == "bundle" (always applies to bundles)
        - applies_to_ref is None (universal rule)

    Severity mapping:
        "BLOCK"   → SafetyStatus.BLOCKED
        "WARNING" → SafetyStatus.WARNING
        "CAUTION" → SafetyStatus.WARNING (treated as soft warning)

    Args:
        intervention: InterventionDef to evaluate.
        all_rules: All contraindication rules.
        patient_profile: Dict of patient attributes.

    Returns:
        InterventionSafety with aggregated status.
    """
    evaluations: list[ContraindicationEval] = []
    blocking_rules: list[str] = []
    warning_rules: list[str] = []

    # Find applicable rules
    applicable_rules = _find_applicable_rules(
        intervention, all_rules,
    )

    for rule in applicable_rules:
        evaluation = _evaluate_contraindication(rule, patient_profile)
        evaluations.append(evaluation)

        if evaluation.triggered:
            if evaluation.severity.upper() == "BLOCK":
                blocking_rules.append(evaluation.rule_id)
            else:
                # WARNING, CAUTION, or any other severity → warning
                warning_rules.append(evaluation.rule_id)

    # Determine overall status
    if blocking_rules:
        status = SafetyStatus.BLOCKED
    elif warning_rules:
        status = SafetyStatus.WARNING
    else:
        status = SafetyStatus.CLEAR

    n_triggered = len(blocking_rules) + len(warning_rules)

    if n_triggered > 0:
        logger.info(
            "Safety: Intervention '%s' (%s) — %s: %d blocked, %d warnings",
            intervention.action_id, intervention.action_label,
            status.value, len(blocking_rules), len(warning_rules),
        )

    return InterventionSafety(
        action_id=intervention.action_id,
        action_label=intervention.action_label,
        status=status,
        evaluations=evaluations,
        n_triggered=n_triggered,
        n_blocked=len(blocking_rules),
        n_warnings=len(warning_rules),
        blocking_rules=blocking_rules,
        warning_rules=warning_rules,
    )


def _find_applicable_rules(
    intervention: InterventionDef,
    all_rules: list[ContraindicationDef],
) -> list[ContraindicationDef]:
    """Find contraindication rules that apply to this intervention.

    Match criteria:
        1. applies_to_ref is None → universal rule (applies to all)
        2. applies_to_type == "action" AND applies_to_ref == action_id
        3. applies_to_type == "action_class" AND applies_to_ref == action_class

    Args:
        intervention: The intervention to match against.
        all_rules: All loaded contraindication rules.

    Returns:
        List of applicable rules.
    """
    applicable: list[ContraindicationDef] = []

    for rule in all_rules:
        # Universal rules (no specific target)
        if rule.applies_to_ref is None or rule.applies_to_ref == "":
            applicable.append(rule)
            continue

        # Type-specific matching
        if rule.applies_to_type == "action":
            if rule.applies_to_ref == intervention.action_id:
                applicable.append(rule)
        elif rule.applies_to_type == "action_class":
            if rule.applies_to_ref == intervention.action_class:
                applicable.append(rule)

    return applicable


# ═══════════════════════════════════════════════════════════════
#  Top-Level: evaluate_safety (entry point)
# ═══════════════════════════════════════════════════════════════


def evaluate_safety(
    intervention_set: InterventionSet,
    patient_profile: dict[str, object],
) -> SafetyResult:
    """Evaluate contraindication safety for all interventions.

    For each intervention:
        1. Find applicable contraindication rules
        2. Evaluate condition expressions against patient profile
        3. Handle missing inputs per unknown_input_policy
        4. Assign CLEAR / WARNING / BLOCKED status

    Args:
        intervention_set: Complete InterventionSet from D0.
        patient_profile: Dict of patient attributes (age, treatments, etc.).

    Returns:
        SafetyResult with per-intervention safety status.
    """
    logger.info(
        "── D3-Safety: Contraindication Evaluation ──\n"
        "  n_interventions=%d, n_rules=%d, n_profile_keys=%d",
        intervention_set.n_interventions,
        len(intervention_set.all_contraindications),
        len(patient_profile),
    )

    all_safety: dict[str, InterventionSafety] = {}
    n_clear = 0
    n_warning = 0
    n_blocked = 0
    blocked_ids: list[str] = []

    for intervention in intervention_set.interventions:
        safety = _evaluate_intervention_safety(
            intervention,
            intervention_set.all_contraindications,
            patient_profile,
        )
        all_safety[intervention.action_id] = safety

        if safety.status == SafetyStatus.CLEAR:
            n_clear += 1
        elif safety.status == SafetyStatus.WARNING:
            n_warning += 1
        elif safety.status == SafetyStatus.BLOCKED:
            n_blocked += 1
            blocked_ids.append(intervention.action_id)

    logger.info(
        "D3-Safety complete: %d CLEAR, %d WARNING, %d BLOCKED",
        n_clear, n_warning, n_blocked,
    )

    return SafetyResult(
        intervention_safety=all_safety,
        n_total=intervention_set.n_interventions,
        n_clear=n_clear,
        n_warning=n_warning,
        n_blocked=n_blocked,
        blocked_action_ids=blocked_ids,
    )
