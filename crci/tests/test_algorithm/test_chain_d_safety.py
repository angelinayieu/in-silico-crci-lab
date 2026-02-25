"""Tests for ALG-D3 Safety Checker: Contraindication Evaluation.

Covers:
    Condition expression evaluation (==, !=, >=, <=, >, <, CONTAINS)
    Missing input handling (assume_safe, assume_unsafe, skip)
    Rule matching (action, action_class, universal)
    Safety status aggregation (CLEAR, WARNING, BLOCKED)
    Full integration: evaluate_safety end-to-end
"""
from __future__ import annotations

import pytest

from crci.algorithm.chain_d_simulation.safety_checker import (
    ContraindicationEval,
    InterventionSafety,
    SafetyResult,
    SafetyStatus,
    _evaluate_condition,
    _evaluate_contraindication,
    _evaluate_intervention_safety,
    _find_applicable_rules,
    evaluate_safety,
)
from crci.algorithm.chain_d_simulation.intervention_loader import (
    ContraindicationDef,
    InterventionDef,
    InterventionSet,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_rule(
    rule_id="R01",
    severity="BLOCK",
    condition="active_treatment == True",
    required_inputs=None,
    unknown_input_policy="assume_safe",
    applies_to_type="action",
    applies_to_ref=None,
):
    return ContraindicationDef(
        rule_id=rule_id,
        rule_label=f"Test rule {rule_id}",
        applies_to_type=applies_to_type,
        applies_to_ref=applies_to_ref,
        severity=severity,
        condition_expression=condition,
        required_inputs=required_inputs or [],
        unknown_input_policy=unknown_input_policy,
        penalty_spec=None,
        escalation_id=None,
        rationale=f"Test rationale for {rule_id}",
    )


def _make_intervention(
    action_id="ACT_EXERCISE",
    action_class="exercise",
    contraindications=None,
):
    return InterventionDef(
        action_id=action_id,
        action_label=f"Test {action_id}",
        action_class=action_class,
        dose_type="minutes_per_week",
        dose_unit="min/wk",
        dose_min=0.0,
        dose_max=300.0,
        dose_recommended_start=150.0,
        dose_step=30.0,
        time_cost_min=150.0,
        cognitive_load=0.2,
        logistics_load=0.3,
        overall_burden=0.4,
        adherence_rate_default=0.7,
        evidence_basis="rct",
        evidence_strength="HIGH",
        contraindications=contraindications or [],
    )


def _make_intervention_set(interventions, rules=None):
    return InterventionSet(
        interventions=interventions,
        intervention_index={i.action_id: idx for idx, i in enumerate(interventions)},
        synergy_records=[],
        synergy_lookup={},
        all_contraindications=rules or [],
    )


# ═══════════════════════════════════════════════════════════════
#  Test Condition Expression Evaluation
# ═══════════════════════════════════════════════════════════════


class TestConditionEvaluation:
    """Test the condition expression parser/evaluator."""

    def test_equality_true(self):
        assert _evaluate_condition("active_treatment == True", {"active_treatment": True})

    def test_equality_false(self):
        assert not _evaluate_condition("active_treatment == True", {"active_treatment": False})

    def test_string_equality(self):
        assert _evaluate_condition("cancer_type == 'breast'", {"cancer_type": "breast"})

    def test_string_inequality(self):
        assert not _evaluate_condition("cancer_type == 'lung'", {"cancer_type": "breast"})

    def test_not_equal(self):
        assert _evaluate_condition("status != 'remission'", {"status": "active"})

    def test_greater_equal(self):
        assert _evaluate_condition("age >= 75", {"age": 80})
        assert _evaluate_condition("age >= 75", {"age": 75})
        assert not _evaluate_condition("age >= 75", {"age": 60})

    def test_less_than(self):
        assert _evaluate_condition("gfr < 30", {"gfr": 25})
        assert not _evaluate_condition("gfr < 30", {"gfr": 35})

    def test_contains_list(self):
        profile = {"concurrent_medications": ["warfarin", "metformin"]}
        assert _evaluate_condition("concurrent_medications CONTAINS 'warfarin'", profile)
        assert not _evaluate_condition("concurrent_medications CONTAINS 'aspirin'", profile)

    def test_contains_string(self):
        profile = {"treatments": "chemo_radiation"}
        assert _evaluate_condition("treatments CONTAINS 'chemo'", profile)

    def test_missing_field_returns_false(self):
        assert not _evaluate_condition("nonexistent >= 5", {})

    def test_always_true(self):
        assert _evaluate_condition("true", {})
        assert _evaluate_condition("always", {})

    def test_always_false(self):
        assert not _evaluate_condition("false", {})
        assert not _evaluate_condition("never", {})

    def test_empty_expression(self):
        assert _evaluate_condition("", {})

    def test_simple_truthiness(self):
        assert _evaluate_condition("has_neuropathy", {"has_neuropathy": True})
        assert not _evaluate_condition("has_neuropathy", {"has_neuropathy": False})
        assert not _evaluate_condition("has_neuropathy", {})


# ═══════════════════════════════════════════════════════════════
#  Test Missing Input Handling
# ═══════════════════════════════════════════════════════════════


class TestMissingInputPolicy:
    """Test unknown_input_policy handling."""

    def test_assume_safe_allows(self):
        """Missing inputs with assume_safe → not triggered."""
        rule = _make_rule(
            condition="renal_function == 'impaired'",
            required_inputs=["renal_function"],
            unknown_input_policy="assume_safe",
        )
        result = _evaluate_contraindication(rule, {})
        assert not result.triggered
        assert result.unknown_input_resolved_as == "assume_safe"
        assert "renal_function" in result.missing_inputs

    def test_assume_unsafe_blocks(self):
        """Missing inputs with assume_unsafe → triggered."""
        rule = _make_rule(
            condition="renal_function == 'impaired'",
            required_inputs=["renal_function"],
            unknown_input_policy="assume_unsafe",
        )
        result = _evaluate_contraindication(rule, {})
        assert result.triggered
        assert result.unknown_input_resolved_as == "assume_unsafe"

    def test_skip_not_triggered(self):
        """Missing inputs with skip → not triggered."""
        rule = _make_rule(
            condition="renal_function == 'impaired'",
            required_inputs=["renal_function"],
            unknown_input_policy="skip",
        )
        result = _evaluate_contraindication(rule, {})
        assert not result.triggered
        assert result.unknown_input_resolved_as == "skip"

    def test_complete_inputs_evaluate_normally(self):
        """When all required inputs present, evaluate the expression."""
        rule = _make_rule(
            condition="age >= 75",
            required_inputs=["age"],
            unknown_input_policy="assume_unsafe",
        )
        result = _evaluate_contraindication(rule, {"age": 80})
        assert result.triggered
        assert result.unknown_input_resolved_as == "complete"


# ═══════════════════════════════════════════════════════════════
#  Test Rule Matching
# ═══════════════════════════════════════════════════════════════


class TestRuleMatching:
    """Test _find_applicable_rules matching logic."""

    def test_universal_rule_matches_all(self):
        """Rule with applies_to_ref=None matches any intervention."""
        rule = _make_rule(applies_to_ref=None, applies_to_type="action")
        intervention = _make_intervention()
        applicable = _find_applicable_rules(intervention, [rule])
        assert len(applicable) == 1

    def test_action_specific_match(self):
        """Rule targeting specific action_id."""
        rule = _make_rule(applies_to_type="action", applies_to_ref="ACT_EXERCISE")
        intervention = _make_intervention(action_id="ACT_EXERCISE")
        applicable = _find_applicable_rules(intervention, [rule])
        assert len(applicable) == 1

    def test_action_specific_no_match(self):
        """Rule for different action_id doesn't match."""
        rule = _make_rule(applies_to_type="action", applies_to_ref="ACT_MEDITATION")
        intervention = _make_intervention(action_id="ACT_EXERCISE")
        applicable = _find_applicable_rules(intervention, [rule])
        assert len(applicable) == 0

    def test_action_class_match(self):
        """Rule targeting action_class matches."""
        rule = _make_rule(applies_to_type="action_class", applies_to_ref="exercise")
        intervention = _make_intervention(action_class="exercise")
        applicable = _find_applicable_rules(intervention, [rule])
        assert len(applicable) == 1

    def test_action_class_no_match(self):
        rule = _make_rule(applies_to_type="action_class", applies_to_ref="pharmacological")
        intervention = _make_intervention(action_class="exercise")
        applicable = _find_applicable_rules(intervention, [rule])
        assert len(applicable) == 0


# ═══════════════════════════════════════════════════════════════
#  Test Safety Status Aggregation
# ═══════════════════════════════════════════════════════════════


class TestSafetyStatusAggregation:
    """Test how individual rule results aggregate into overall status."""

    def test_no_rules_clear(self):
        """No contraindication rules → CLEAR."""
        intervention = _make_intervention()
        safety = _evaluate_intervention_safety(intervention, [], {})
        assert safety.status == SafetyStatus.CLEAR
        assert safety.n_triggered == 0

    def test_block_rule_triggered(self):
        """BLOCK severity + triggered → BLOCKED."""
        rule = _make_rule(
            severity="BLOCK",
            condition="active_treatment == True",
            applies_to_ref=None,
        )
        intervention = _make_intervention()
        safety = _evaluate_intervention_safety(
            intervention, [rule], {"active_treatment": True},
        )
        assert safety.status == SafetyStatus.BLOCKED
        assert safety.n_blocked == 1

    def test_warning_rule_triggered(self):
        """WARNING severity + triggered → WARNING."""
        rule = _make_rule(
            severity="WARNING",
            condition="age >= 70",
            applies_to_ref=None,
        )
        intervention = _make_intervention()
        safety = _evaluate_intervention_safety(
            intervention, [rule], {"age": 75},
        )
        assert safety.status == SafetyStatus.WARNING
        assert safety.n_warnings == 1

    def test_block_overrides_warning(self):
        """BLOCK + WARNING → BLOCKED (strictest wins)."""
        rules = [
            _make_rule(rule_id="R1", severity="BLOCK", condition="true", applies_to_ref=None),
            _make_rule(rule_id="R2", severity="WARNING", condition="true", applies_to_ref=None),
        ]
        intervention = _make_intervention()
        safety = _evaluate_intervention_safety(intervention, rules, {})
        assert safety.status == SafetyStatus.BLOCKED
        assert safety.n_blocked == 1
        assert safety.n_warnings == 1

    def test_untriggered_rules_stay_clear(self):
        """Rules exist but none triggered → CLEAR."""
        rule = _make_rule(
            severity="BLOCK",
            condition="active_treatment == True",
            applies_to_ref=None,
        )
        intervention = _make_intervention()
        safety = _evaluate_intervention_safety(
            intervention, [rule], {"active_treatment": False},
        )
        assert safety.status == SafetyStatus.CLEAR
        assert safety.n_triggered == 0


# ═══════════════════════════════════════════════════════════════
#  Integration: Full evaluate_safety
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full safety evaluation pipeline."""

    def test_mixed_safety_statuses(self):
        """Three interventions: one CLEAR, one WARNING, one BLOCKED."""
        interventions = [
            _make_intervention(action_id="ACT_EXERCISE", action_class="exercise"),
            _make_intervention(action_id="ACT_MEDITATION", action_class="behavioral"),
            _make_intervention(action_id="ACT_DRUG_X", action_class="pharmacological"),
        ]
        rules = [
            # Universal age warning
            _make_rule(
                rule_id="R_AGE",
                severity="WARNING",
                condition="age >= 75",
                applies_to_ref=None,
            ),
            # Block drug for renal patients
            _make_rule(
                rule_id="R_RENAL",
                severity="BLOCK",
                condition="renal_function == 'impaired'",
                applies_to_type="action",
                applies_to_ref="ACT_DRUG_X",
            ),
        ]
        intervention_set = _make_intervention_set(interventions, rules)

        patient = {"age": 80, "renal_function": "impaired"}
        result = evaluate_safety(intervention_set, patient)

        # Exercise: WARNING (age rule)
        assert result.intervention_safety["ACT_EXERCISE"].status == SafetyStatus.WARNING
        # Meditation: WARNING (age rule)
        assert result.intervention_safety["ACT_MEDITATION"].status == SafetyStatus.WARNING
        # Drug X: BLOCKED (age warning + renal block → BLOCKED wins)
        assert result.intervention_safety["ACT_DRUG_X"].status == SafetyStatus.BLOCKED

        assert result.n_blocked == 1
        assert result.n_warning == 2
        assert result.n_clear == 0
        assert "ACT_DRUG_X" in result.blocked_action_ids

    def test_all_clear(self):
        """Healthy patient, no triggered rules → all CLEAR."""
        interventions = [
            _make_intervention(action_id="ACT_01"),
            _make_intervention(action_id="ACT_02"),
        ]
        rules = [
            _make_rule(
                rule_id="R1",
                severity="BLOCK",
                condition="active_treatment == True",
                applies_to_ref=None,
            ),
        ]
        intervention_set = _make_intervention_set(interventions, rules)

        patient = {"active_treatment": False, "age": 45}
        result = evaluate_safety(intervention_set, patient)

        assert result.n_clear == 2
        assert result.n_blocked == 0
        assert result.n_warning == 0

    def test_empty_interventions(self):
        """No interventions → empty result."""
        intervention_set = _make_intervention_set([], [])
        result = evaluate_safety(intervention_set, {})
        assert result.n_total == 0

    def test_missing_inputs_with_assume_unsafe(self):
        """Missing input + assume_unsafe → rule triggers."""
        interventions = [_make_intervention(action_id="ACT_01")]
        rules = [
            _make_rule(
                rule_id="R1",
                severity="BLOCK",
                condition="cardiac_risk == 'high'",
                required_inputs=["cardiac_risk"],
                unknown_input_policy="assume_unsafe",
                applies_to_ref=None,
            ),
        ]
        intervention_set = _make_intervention_set(interventions, rules)

        # No cardiac_risk in profile → assume_unsafe → BLOCKED
        result = evaluate_safety(intervention_set, {"age": 50})
        assert result.intervention_safety["ACT_01"].status == SafetyStatus.BLOCKED
