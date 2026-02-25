"""Tests for RT-H Adaptive Questioning.

Covers:
    H-1: Information gain computation
    H-2: Gaussian entropy
    H-3: Stopping criteria
    H-G1: Answer validation
    Question ranking (mandatory first, then by IG)
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.runtime.adaptive_questions import (
    NextQuestion,
    PatientAnswer,
    QuestionDef,
    QuestionRecord,
    QuestioningState,
    StopReason,
    _check_stopping_criteria,
    _compute_gaussian_entropy,
    _compute_information_gain,
    _rank_questions,
    _validate_answer,
    check_should_stop,
    process_answer,
    select_next_question,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_question(qid: str, nodes: tuple[str, ...], mandatory: bool = False) -> QuestionDef:
    return QuestionDef(
        question_id=qid,
        question_text=f"Question {qid}",
        target_node_ids=nodes,
        instrument_id="inst_1",
        is_mandatory=mandatory,
    )


def _make_state(n=0) -> QuestioningState:
    return QuestioningState(
        questions_asked=[],
        n_questions=n,
    )


# ═══════════════════════════════════════════════════════════════
#  Test H-2: Gaussian Entropy
# ═══════════════════════════════════════════════════════════════


class TestGaussianEntropy:
    """Test multivariate Gaussian entropy computation."""

    def test_1d_unit_variance(self):
        """H(X) = 0.5·ln(2πe·1) = 0.5·ln(2πe) ≈ 1.4189."""
        cov = np.array([[1.0]])
        h = _compute_gaussian_entropy(cov)
        expected = 0.5 * np.log(2.0 * np.pi * np.e)
        assert abs(h - expected) < 1e-10

    def test_2d_identity(self):
        """H = 0.5·(2·ln(2πe) + ln|I₂|) = 0.5·(2·ln(2πe) + 0)."""
        cov = np.eye(2)
        h = _compute_gaussian_entropy(cov)
        expected = 0.5 * (2 * np.log(2.0 * np.pi * np.e) + 0.0)
        assert abs(h - expected) < 1e-10

    def test_larger_variance_more_entropy(self):
        """Higher variance → more entropy."""
        h_small = _compute_gaussian_entropy(np.array([[0.5]]))
        h_large = _compute_gaussian_entropy(np.array([[2.0]]))
        assert h_large > h_small

    def test_2d_correlated(self):
        """2D with correlation: |Σ| = 1·1 − 0.5² = 0.75."""
        cov = np.array([[1.0, 0.5], [0.5, 1.0]])
        h = _compute_gaussian_entropy(cov)
        expected = 0.5 * (2 * np.log(2.0 * np.pi * np.e) + np.log(0.75))
        assert abs(h - expected) < 1e-6


# ═══════════════════════════════════════════════════════════════
#  Test H-1: Information Gain
# ═══════════════════════════════════════════════════════════════


class TestInformationGain:
    """Test information gain computation."""

    def test_observing_uncertain_node(self):
        """Observing a high-variance node gives positive IG."""
        cov = np.diag([2.0, 0.1])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}
        q = _make_question("q1", ("n0",))
        ig = _compute_information_gain(q, mean, cov, node_map, observation_noise_var=0.5)
        assert ig > 0.0

    def test_observing_certain_node_low_ig(self):
        """Observing a low-variance node gives lower IG."""
        cov = np.diag([2.0, 0.1])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}
        q_uncertain = _make_question("q1", ("n0",))
        q_certain = _make_question("q2", ("n1",))
        ig_uncertain = _compute_information_gain(q_uncertain, mean, cov, node_map, 0.5)
        ig_certain = _compute_information_gain(q_certain, mean, cov, node_map, 0.5)
        assert ig_uncertain > ig_certain

    def test_no_target_nodes_zero_ig(self):
        """Question targeting no known nodes → IG = 0."""
        cov = np.diag([1.0, 1.0])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}
        q = _make_question("q1", ("unknown_node",))
        ig = _compute_information_gain(q, mean, cov, node_map)
        assert ig == 0.0

    def test_ig_always_non_negative(self):
        """IG should always be ≥ 0."""
        cov = np.array([[1.0, 0.3], [0.3, 0.5]])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}
        q = _make_question("q1", ("n0",))
        ig = _compute_information_gain(q, mean, cov, node_map)
        assert ig >= 0.0


# ═══════════════════════════════════════════════════════════════
#  Test Question Ranking
# ═══════════════════════════════════════════════════════════════


class TestQuestionRanking:
    """Test question ranking by IG."""

    def test_mandatory_first(self):
        """Mandatory questions appear before optional regardless of IG."""
        cov = np.diag([1.0, 0.01])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}

        # Optional q targets high-variance node; mandatory targets low-variance
        q_opt = _make_question("q_opt", ("n0",), mandatory=False)
        q_mand = _make_question("q_mand", ("n1",), mandatory=True)

        ranked = _rank_questions([q_opt, q_mand], mean, cov, node_map)
        assert ranked[0].question_id == "q_mand"  # mandatory first

    def test_within_group_sorted_by_ig(self):
        """Within optional group, sorted by IG descending."""
        cov = np.diag([2.0, 0.5])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}

        q1 = _make_question("q1", ("n1",))  # lower variance → less IG
        q2 = _make_question("q2", ("n0",))  # higher variance → more IG

        ranked = _rank_questions([q1, q2], mean, cov, node_map)
        assert ranked[0].question_id == "q2"  # higher IG first


# ═══════════════════════════════════════════════════════════════
#  Test H-3: Stopping Criteria
# ═══════════════════════════════════════════════════════════════


class TestStoppingCriteria:
    """Test stopping decision logic."""

    def test_patient_request_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=2, last_ig=0.5, last_var_reduction=0.5,
            patient_requested_stop=True, n_remaining=5,
        )
        assert reason == StopReason.PATIENT_REQUEST

    def test_max_questions_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=config.RT_H_MAX_QUESTIONS,
            last_ig=0.5, last_var_reduction=0.5, n_remaining=5,
        )
        assert reason == StopReason.MAX_QUESTIONS

    def test_no_remaining_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=3, last_ig=0.5, last_var_reduction=0.5,
            n_remaining=0,
        )
        assert reason == StopReason.NO_QUESTIONS_REMAINING

    def test_low_ig_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=3, last_ig=0.005,
            last_var_reduction=0.5, n_remaining=5,
        )
        assert reason == StopReason.IG_BELOW_THRESHOLD

    def test_stability_reached_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=3, last_ig=0.5, last_var_reduction=0.5,
            p_rank_1=0.85, n_remaining=5,
        )
        assert reason == StopReason.STABILITY_REACHED

    def test_low_var_reduction_stops(self):
        reason = _check_stopping_criteria(
            n_questions_asked=3, last_ig=0.5,
            last_var_reduction=0.01, n_remaining=5,
        )
        assert reason == StopReason.VAR_REDUCTION_LOW

    def test_continue_when_all_criteria_satisfied(self):
        reason = _check_stopping_criteria(
            n_questions_asked=3, last_ig=0.5, last_var_reduction=0.5,
            p_rank_1=0.5, n_remaining=5,
        )
        assert reason is None

    def test_first_question_doesnt_check_ig(self):
        """Before first question, IG threshold not checked."""
        reason = _check_stopping_criteria(
            n_questions_asked=0, last_ig=0.0, last_var_reduction=0.0,
            n_remaining=5,
        )
        assert reason is None


# ═══════════════════════════════════════════════════════════════
#  Test H-G1: Answer Validation
# ═══════════════════════════════════════════════════════════════


class TestAnswerValidation:
    """Test answer validation gate."""

    def test_valid_answer(self):
        answer = PatientAnswer(question_id="q1", raw_response="3", parsed_value=3.0)
        assert _validate_answer(answer) is True

    def test_skipped_is_valid(self):
        answer = PatientAnswer(question_id="q1", raw_response="", skipped=True)
        assert _validate_answer(answer) is True

    def test_invalid_answer(self):
        answer = PatientAnswer(question_id="q1", raw_response="abc", valid=False)
        assert _validate_answer(answer) is False

    def test_none_parsed_value(self):
        answer = PatientAnswer(question_id="q1", raw_response="x", parsed_value=None)
        assert _validate_answer(answer) is False


# ═══════════════════════════════════════════════════════════════
#  Test Process Answer
# ═══════════════════════════════════════════════════════════════


class TestProcessAnswer:
    """Test answer processing."""

    def test_valid_answer_recorded(self):
        state = _make_state()
        question = NextQuestion(
            question_id="q1", question_text="How?",
            target_node_ids=("n1",), instrument_id="i1",
            expected_ig=0.3, rank=1,
        )
        answer = PatientAnswer(question_id="q1", raw_response="4", parsed_value=4.0)
        record = process_answer(answer, question, state)
        assert record.answer_value == 4.0
        assert state.n_questions == 1

    def test_invalid_answer_raises(self):
        state = _make_state()
        question = NextQuestion(
            question_id="q1", question_text="How?",
            target_node_ids=("n1",), instrument_id="i1",
            expected_ig=0.3, rank=1,
        )
        answer = PatientAnswer(question_id="q1", raw_response="abc", valid=False)
        with pytest.raises(GateViolation, match="H-G1"):
            process_answer(answer, question, state)

    def test_skipped_recorded(self):
        state = _make_state()
        question = NextQuestion(
            question_id="q1", question_text="How?",
            target_node_ids=("n1",), instrument_id="i1",
            expected_ig=0.3, rank=1,
        )
        answer = PatientAnswer(question_id="q1", raw_response="", skipped=True)
        record = process_answer(answer, question, state)
        assert record.skipped is True
        assert state.n_skipped == 1


# ═══════════════════════════════════════════════════════════════
#  Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full RT-H integration tests."""

    def test_select_next_question(self):
        cov = np.diag([2.0, 0.5])
        mean = np.array([0.0, 0.0])
        node_map = {"n0": 0, "n1": 1}
        questions = [
            _make_question("q1", ("n0",)),
            _make_question("q2", ("n1",)),
        ]
        result = select_next_question(questions, mean, cov, node_map)
        assert result is not None
        assert result.question_id == "q1"  # n0 has higher variance

    def test_select_returns_none_at_max(self):
        result = select_next_question(
            [_make_question("q1", ("n0",))],
            np.array([0.0]), np.eye(1), {"n0": 0},
            n_questions_asked=config.RT_H_MAX_QUESTIONS,
        )
        assert result is None

    def test_check_should_stop_updates_state(self):
        state = _make_state(n=3)
        reason = check_should_stop(state, last_ig=0.001, n_remaining=5)
        assert reason == StopReason.IG_BELOW_THRESHOLD
        assert state.gate_h_g2_passed is True

    def test_full_loop_simulation(self):
        """Simulate a mini questioning loop."""
        cov = np.diag([2.0, 1.0, 0.5])
        mean = np.zeros(3)
        node_map = {"n0": 0, "n1": 1, "n2": 2}
        questions = [
            _make_question("q1", ("n0",)),
            _make_question("q2", ("n1",)),
            _make_question("q3", ("n2",)),
        ]

        state = _make_state()
        asked = set()

        for _ in range(10):
            remaining = [q for q in questions if q.question_id not in asked]
            nq = select_next_question(remaining, mean, cov, node_map, state.n_questions)
            if nq is None:
                break
            asked.add(nq.question_id)
            answer = PatientAnswer(
                question_id=nq.question_id, raw_response="3", parsed_value=3.0,
            )
            process_answer(answer, nq, state)
            stop = check_should_stop(
                state, last_ig=nq.expected_ig, last_var_reduction=0.5,
                n_remaining=len(remaining) - 1,
            )
            if stop is not None:
                break

        assert state.n_questions > 0


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify RT-H constants come from config."""

    def test_max_questions(self):
        assert config.RT_H_MAX_QUESTIONS == 15

    def test_ig_threshold(self):
        assert config.RT_H_IG_THRESHOLD == 0.01

    def test_var_reduction_threshold(self):
        assert config.RT_H_VAR_REDUCTION_THRESHOLD == 0.05

    def test_stability_stop_threshold(self):
        assert config.RT_H_STABILITY_STOP_THRESHOLD == 0.80
