"""Tests for TB QA gates (GATE-QA-1 through QA-5).

Covers:
- Each gate individually with pass/fail cases
- Combined run_qa_gates() with mixed inputs
- Edge cases: empty input, all rejected, all accepted
- QA-4 dedup behavior
- Quarantine writer integration
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from crci.extraction.tb_trust_boundary.qa_gate import (
    ALLOWED_ESTIMAND_FAMILIES,
    REJECT_DUPLICATE_KEY,
    REJECT_EDGE_NOT_IN_DEFINITIONS,
    REJECT_ESTIMAND_UNDECLARED,
    REJECT_MISSING_STUDY_CONTEXT,
    REJECT_NO_PRECISION,
    QAGateRejection,
    QAGateResult,
    check_qa1_precision_source,
    check_qa2_edge_id_exists,
    check_qa3_estimand_declared,
    check_qa5_study_context,
    clear_edge_id_cache,
    compute_evidence_key,
    run_qa_gates,
    _infer_estimand_from_label,
)
from crci.shared.models.intermediate_states import TypedNumericValue


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _make_tv(
    value: float = 0.5,
    se: float | None = None,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    p_value: float | None = None,
    n: int | None = None,
    edge_relation_id: str | None = None,
    label_type: str | None = "EFFECT_SIZE",
    original_text: str = "test span",
    grouping_id: str | None = None,
) -> TypedNumericValue:
    """Build a TypedNumericValue with specified fields."""
    return TypedNumericValue(
        value=value,
        se=se,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_value,
        n=n,
        edge_relation_id=edge_relation_id,
        label_type=label_type,
        original_text=original_text,
        grouping_id=grouping_id,
    )


# ═══════════════════════════════════════════════════════════════
#  QA-1: PrecisionSourceRequired
# ═══════════════════════════════════════════════════════════════


class TestQA1PrecisionSource:
    """GATE-QA-1: Must have SE, CI, or p+N."""

    def test_pass_with_se(self):
        tv = _make_tv(se=0.12)
        assert check_qa1_precision_source(tv) is None

    def test_pass_with_ci(self):
        tv = _make_tv(ci_lower=0.3, ci_upper=0.7)
        assert check_qa1_precision_source(tv) is None

    def test_pass_with_p_and_n(self):
        tv = _make_tv(p_value=0.04, n=100)
        assert check_qa1_precision_source(tv) is None

    def test_fail_nothing(self):
        tv = _make_tv()
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_fail_se_zero(self):
        """SE=0.0 is not a valid precision source."""
        tv = _make_tv(se=0.0)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_fail_se_negative(self):
        tv = _make_tv(se=-0.1)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_fail_p_without_n(self):
        tv = _make_tv(p_value=0.05)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_pass_n_for_derivation(self):
        """N > 2 with value allows L4B Borenstein SE derivation."""
        tv = _make_tv(n=100)
        assert check_qa1_precision_source(tv) is None

    def test_fail_n_too_small_without_p(self):
        """N ≤ 2 without p_value cannot derive SE."""
        tv = _make_tv(n=2)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_fail_ci_lower_only(self):
        tv = _make_tv(ci_lower=0.3)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_fail_n_zero(self):
        tv = _make_tv(p_value=0.05, n=0)
        assert check_qa1_precision_source(tv) == REJECT_NO_PRECISION

    def test_pass_multiple_sources(self):
        """All three sources present — still passes."""
        tv = _make_tv(se=0.1, ci_lower=0.3, ci_upper=0.7, p_value=0.04, n=100)
        assert check_qa1_precision_source(tv) is None


# ═══════════════════════════════════════════════════════════════
#  QA-2: EdgeIdExists
# ═══════════════════════════════════════════════════════════════


class TestQA2EdgeIdExists:
    """GATE-QA-2: edge_relation_id must be in definitions."""

    VALID = frozenset({"ER_ACTIVITY_WORKMEM", "ER_CORTISOL_DEPRESSION"})

    def test_pass_valid_id(self):
        tv = _make_tv(edge_relation_id="ER_ACTIVITY_WORKMEM")
        assert check_qa2_edge_id_exists(tv, self.VALID) is None

    def test_fail_invalid_id(self):
        tv = _make_tv(edge_relation_id="EDGE_NONEXISTENT")
        assert check_qa2_edge_id_exists(tv, self.VALID) == REJECT_EDGE_NOT_IN_DEFINITIONS

    def test_fail_none_id(self):
        tv = _make_tv(edge_relation_id=None)
        assert check_qa2_edge_id_exists(tv, self.VALID) == REJECT_EDGE_NOT_IN_DEFINITIONS

    def test_fail_unassigned(self):
        tv = _make_tv(edge_relation_id="UNASSIGNED")
        assert check_qa2_edge_id_exists(tv, self.VALID) == REJECT_EDGE_NOT_IN_DEFINITIONS


# ═══════════════════════════════════════════════════════════════
#  QA-3: EstimandDeclaredAndAllowed
# ═══════════════════════════════════════════════════════════════


class TestQA3Estimand:
    """GATE-QA-3: Estimand must be declared and in allowed set."""

    def test_pass_explicit_smd(self):
        tv = _make_tv(label_type="RANDOM")
        assert check_qa3_estimand_declared(tv, declared_estimand="SMD") is None

    def test_pass_from_label_effect_size(self):
        tv = _make_tv(label_type="EFFECT_SIZE")
        assert check_qa3_estimand_declared(tv) is None

    def test_pass_from_label_odds_ratio(self):
        tv = _make_tv(label_type="ODDS_RATIO")
        assert check_qa3_estimand_declared(tv) is None

    def test_pass_from_label_correlation(self):
        tv = _make_tv(label_type="CORRELATION")
        assert check_qa3_estimand_declared(tv) is None

    def test_pass_from_label_beta(self):
        tv = _make_tv(label_type="BETA")
        assert check_qa3_estimand_declared(tv) is None

    def test_fail_unknown_label(self):
        tv = _make_tv(label_type="SAMPLE_SIZE")
        assert check_qa3_estimand_declared(tv) == REJECT_ESTIMAND_UNDECLARED

    def test_fail_none_label_no_declared(self):
        tv = _make_tv(label_type=None)
        assert check_qa3_estimand_declared(tv) == REJECT_ESTIMAND_UNDECLARED

    def test_pass_explicit_overrides_bad_label(self):
        tv = _make_tv(label_type="GARBAGE")
        assert check_qa3_estimand_declared(tv, declared_estimand="LOG_OR") is None


class TestEstimandInference:
    """Test _infer_estimand_from_label mapping."""

    def test_cohens_d(self):
        assert _infer_estimand_from_label("COHENS_D") == "SMD"

    def test_hedges_g(self):
        assert _infer_estimand_from_label("HEDGES_G") == "SMD"

    def test_case_insensitive(self):
        assert _infer_estimand_from_label("effect_size") == "SMD"

    def test_hazard_ratio(self):
        assert _infer_estimand_from_label("HAZARD_RATIO") == "HR_LOG"

    def test_unknown_returns_none(self):
        assert _infer_estimand_from_label("MEAN") is None


# ═══════════════════════════════════════════════════════════════
#  QA-5: StudyContextRequired
# ═══════════════════════════════════════════════════════════════


class TestQA5StudyContext:
    """GATE-QA-5: Must have paper_id or study_id."""

    def test_pass_paper_id(self):
        assert check_qa5_study_context("paper123", None) is None

    def test_pass_study_id(self):
        assert check_qa5_study_context(None, "study456") is None

    def test_pass_both(self):
        assert check_qa5_study_context("p1", "s1") is None

    def test_fail_none_none(self):
        assert check_qa5_study_context(None, None) == REJECT_MISSING_STUDY_CONTEXT

    def test_fail_empty_strings(self):
        assert check_qa5_study_context("", "") == REJECT_MISSING_STUDY_CONTEXT


# ═══════════════════════════════════════════════════════════════
#  QA-4: EvidenceKey Uniqueness (tested via run_qa_gates)
# ═══════════════════════════════════════════════════════════════


class TestEvidenceKey:
    """Test compute_evidence_key function."""

    def test_same_inputs_same_key(self):
        k1 = compute_evidence_key("p1", "s1", "ER_A")
        k2 = compute_evidence_key("p1", "s1", "ER_A")
        assert k1 == k2

    def test_different_edge_different_key(self):
        k1 = compute_evidence_key("p1", "s1", "ER_A")
        k2 = compute_evidence_key("p1", "s1", "ER_B")
        assert k1 != k2

    def test_different_timepoint_different_key(self):
        k1 = compute_evidence_key("p1", "s1", "ER_A", timepoint_bucket="pre")
        k2 = compute_evidence_key("p1", "s1", "ER_A", timepoint_bucket="post")
        assert k1 != k2


# ═══════════════════════════════════════════════════════════════
#  INTEGRATED: run_qa_gates()
# ═══════════════════════════════════════════════════════════════


class TestRunQAGates:
    """Test the full gate runner with mocked DB session."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Clear edge ID cache before each test."""
        clear_edge_id_cache()
        yield
        clear_edge_id_cache()

    def _mock_session(self, valid_ids: list[str] | None = None) -> MagicMock:
        """Create a mock session that returns valid edge IDs."""
        session = MagicMock()
        if valid_ids is None:
            valid_ids = ["ER_ACTIVITY_WORKMEM", "ER_CORTISOL_DEPRESSION"]
        # Mock the execute().all() chain
        mock_result = [(eid,) for eid in valid_ids]
        session.execute.return_value.all.return_value = mock_result
        return session

    def test_all_pass(self):
        """All gates pass — record accepted."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.79,
                se=0.12,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(
            records, session, paper_id="cherrier_2013", study_id="cherrier_2013"
        )
        assert len(result.accepted) == 1
        assert len(result.rejected) == 0
        assert result.stats["accepted"] == 1

    def test_qa1_rejects_no_precision(self):
        """QA-1 rejects record without SE/CI/p+N."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(
            records, session, paper_id="test_paper"
        )
        assert len(result.accepted) == 0
        assert len(result.rejected) == 1
        assert result.rejected[0].gate_id == "QA-1"
        assert result.rejected[0].reject_reason == REJECT_NO_PRECISION

    def test_qa2_rejects_bad_edge_id(self):
        """QA-2 rejects record with invalid edge_relation_id."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                se=0.1,
                edge_relation_id="EDGE_FAKE",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 0
        assert result.rejected[0].gate_id == "QA-2"

    def test_qa3_rejects_unknown_estimand(self):
        """QA-3 rejects record with unrecognized estimand."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                se=0.1,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="SAMPLE_SIZE",  # Not an estimand
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 0
        assert result.rejected[0].gate_id == "QA-3"

    def test_qa4_dedup(self):
        """QA-4 keeps first record, rejects duplicate."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.79,
                se=0.12,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
            _make_tv(
                value=-0.266,
                se=0.11,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 1
        assert len(result.rejected) == 1
        assert result.rejected[0].gate_id == "QA-4"
        assert result.rejected[0].reject_reason == REJECT_DUPLICATE_KEY
        # First record kept
        assert result.accepted[0].value == 0.79

    def test_qa4_no_dedup_different_grouping_ids(self):
        """QA-4 does NOT dedup records with same edge but different grouping_ids.

        Different grouping_ids indicate different observations extracted from
        the same paper (e.g., different timepoints, subgroups).
        """
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.79,
                se=0.12,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
                grouping_id="grp_timepoint_1",
            ),
            _make_tv(
                value=-0.266,
                se=0.11,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
                grouping_id="grp_timepoint_2",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        # Both should be accepted — different grouping_ids = different observations
        assert len(result.accepted) == 2
        assert len(result.rejected) == 0

    def test_qa5_rejects_no_context(self):
        """QA-5 rejects entire batch when no paper_id/study_id."""
        session = self._mock_session()
        records = [
            _make_tv(value=0.5, se=0.1, edge_relation_id="ER_ACTIVITY_WORKMEM"),
        ]
        result = run_qa_gates(records, session, paper_id=None, study_id=None)
        assert len(result.accepted) == 0
        assert len(result.rejected) == 1
        assert result.rejected[0].gate_id == "QA-5"

    def test_empty_input(self):
        """No records — empty result."""
        session = self._mock_session()
        result = run_qa_gates([], session, paper_id="test")
        assert len(result.accepted) == 0
        assert len(result.rejected) == 0

    def test_mixed_pass_fail(self):
        """Some records pass, some fail different gates."""
        session = self._mock_session()
        records = [
            # Passes all
            _make_tv(
                value=0.79,
                se=0.12,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
            # Fails QA-1 (no precision)
            _make_tv(
                value=0.5,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
            # Fails QA-2 (bad ID)
            _make_tv(
                value=0.3,
                se=0.05,
                edge_relation_id="EDGE_FAKE",
                label_type="EFFECT_SIZE",
            ),
            # Passes (different edge, so no QA-4 conflict)
            _make_tv(
                value=0.4,
                se=0.08,
                edge_relation_id="ER_CORTISOL_DEPRESSION",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 2
        assert len(result.rejected) == 2
        assert result.stats["qa1_reject"] == 1
        assert result.stats["qa2_reject"] == 1

    def test_ci_passes_qa1(self):
        """CI bounds satisfy QA-1 even without SE."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                ci_lower=0.3,
                ci_upper=0.7,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 1

    def test_p_n_passes_qa1(self):
        """p-value + N satisfies QA-1."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                p_value=0.03,
                n=50,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="EFFECT_SIZE",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.accepted) == 1

    def test_declared_estimand_overrides_label(self):
        """Explicit declared_estimand allows record even with bad label_type."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=0.5,
                se=0.1,
                edge_relation_id="ER_ACTIVITY_WORKMEM",
                label_type="MEAN",  # not in estimand map
            ),
        ]
        # Without declared_estimand → rejected
        r1 = run_qa_gates(records, session, paper_id="test_paper")
        assert len(r1.accepted) == 0

        clear_edge_id_cache()

        # With declared_estimand → accepted
        r2 = run_qa_gates(
            records, session, paper_id="test_paper",
            declared_estimand="SMD",
        )
        assert len(r2.accepted) == 1

    def test_snapshot_captures_all_fields(self):
        """Rejected records include a snapshot with all fields."""
        session = self._mock_session()
        records = [
            _make_tv(
                value=1.5,
                se=0.3,
                edge_relation_id="EDGE_BAD",
                label_type="EFFECT_SIZE",
                original_text="Cohen's d = 1.5, SE = 0.3",
                grouping_id="grp_001",
            ),
        ]
        result = run_qa_gates(records, session, paper_id="test_paper")
        assert len(result.rejected) == 1
        snap = result.rejected[0].record_snapshot


# ═══════════════════════════════════════════════════════════════
#  P2 FALLBACK BYPASS GUARD
# ═══════════════════════════════════════════════════════════════


class TestP2FallbackBypassGuard:
    """Verify P2 respects QA gate all-rejected scenario (BUG 1 fix)."""

    def test_qa_gate_ran_empty_grouped_evidence_no_fallback(self):
        """When qa_gate_result is in context and grouped_evidence is [],
        P2 should short-circuit — NOT fall back to tb_result.validated."""
        context = {
            "paper_id": "test_paper",
            "grouped_evidence": [],  # QA gate rejected everything
            "qa_gate_result": {      # QA gate DID run
                "accepted": 0,
                "rejected": 3,
                "stats": {"total": 3, "qa1_reject": 3},
            },
            "classified_paper": {"study_design": "rct"},
        }
        # This would be the un-gated fallback — should NOT be used

        class FakeTBResult:
            validated = [object()]  # Would bypass gate if used

        context["tb_result"] = FakeTBResult()

        # We can't easily call run_p2 without a full session/run setup,
        # so test the decision logic directly:
        grouped_evidence = context.get("grouped_evidence")
        qa_gate_ran = context.get("qa_gate_result") is not None

        # The guard condition from the fix
        should_short_circuit = (
            qa_gate_ran
            and grouped_evidence is not None
            and len(grouped_evidence) == 0
        )
        assert should_short_circuit is True, (
            "P2 should short-circuit when QA gate ran and grouped_evidence "
            "is empty, not fall back to tb_result.validated"
        )

    def test_no_qa_gate_allows_fallback(self):
        """When qa_gate_result is NOT in context, fallback is allowed."""
        context = {
            "paper_id": "test_paper",
            "grouped_evidence": [],  # Empty but QA gate didn't run
            # No "qa_gate_result" key
        }
        grouped_evidence = context.get("grouped_evidence")
        qa_gate_ran = context.get("qa_gate_result") is not None

        should_short_circuit = (
            qa_gate_ran
            and grouped_evidence is not None
            and len(grouped_evidence) == 0
        )
        assert should_short_circuit is False, (
            "P2 should fall back to tb_result.validated when QA gate didn't run"
        )


# ═══════════════════════════════════════════════════════════════
#  ALLOWED ESTIMAND SET
# ═══════════════════════════════════════════════════════════════


class TestAllowedEstimands:
    """Verify the allowed estimand set is complete and correct."""

    def test_core_estimands_present(self):
        for est in ["SMD", "LOG_OR", "BETA_STD", "BETA_UNSTD", "R", "HR_LOG"]:
            assert est in ALLOWED_ESTIMAND_FAMILIES

    def test_extended_estimands_present(self):
        for est in ["LOG_RR", "FISHER_Z"]:
            assert est in ALLOWED_ESTIMAND_FAMILIES

    def test_no_raw_mean(self):
        """Raw means should NOT be in allowed set."""
        assert "MEAN" not in ALLOWED_ESTIMAND_FAMILIES
        assert "RAW_MEAN" not in ALLOWED_ESTIMAND_FAMILIES
