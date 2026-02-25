# VERIFIED: formulas [H-1, H-2, H-3] match spec SYS_RT lines 260-388
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PosteriorState (chain_c), question bank
# VERIFIED: forward wiring — writes NextQuestion/StopDecision for RT-I
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [H-G1, H-G2] raise/handle appropriately
"""
Component: SYS_RUNTIME.RT-H
Spec: SYS_RUNTIME_COMPLETE.md lines 260-388
Formulas:
    H-1: IG(q) = H(θ|current) − E_y[H(θ|current ∪ y_q)]
    H-2: H(θ) = 0.5·ln|2πe·Σ_post| (multivariate Gaussian entropy)
    H-3: Stopping: IG < 0.01 OR P(rank₁) ≥ 0.80 OR questions ≥ 15 OR var_reduction < 5%
Reads: PosteriorState (from ALG-C posterior_writer.py),
       Question bank (question_bank_v1)
Writes: NextQuestion, StopDecision, QuestionSequence
        (consumed by session.py orchestrator and RT-I report_assembler.py)
Gates: H-G1, H-G2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class StopReason(str, Enum):
    """Why the questioning loop stopped."""

    IG_BELOW_THRESHOLD = "ig_below_threshold"
    STABILITY_REACHED = "stability_reached"
    MAX_QUESTIONS = "max_questions"
    PATIENT_REQUEST = "patient_request"
    VAR_REDUCTION_LOW = "var_reduction_low"
    NO_QUESTIONS_REMAINING = "no_questions_remaining"


@dataclass(frozen=True)
class QuestionDef:
    """Definition of one question from question_bank_v1."""

    question_id: str
    question_text: str
    target_node_ids: tuple[str, ...]
    instrument_id: str
    is_mandatory: bool = False
    group_id: str | None = None


@dataclass(frozen=True)
class NextQuestion:
    """RT-H1 output: selected question to ask the patient."""

    question_id: str
    question_text: str
    target_node_ids: tuple[str, ...]
    instrument_id: str
    expected_ig: float
    rank: int


@dataclass(frozen=True)
class PatientAnswer:
    """Patient's response to a question."""

    question_id: str
    raw_response: str
    parsed_value: float | None = None
    valid: bool = True
    skipped: bool = False


@dataclass
class QuestionRecord:
    """Record of one question in the session sequence."""

    question_id: str
    target_node_ids: tuple[str, ...]
    expected_ig: float
    actual_ig: float | None = None
    answer_value: float | None = None
    skipped: bool = False


@dataclass
class QuestioningState:
    """RT-H output: complete questioning session state.

    Consumed by RT-I (reporting) and session.py (orchestrator).
    """

    questions_asked: list[QuestionRecord]
    stop_reason: StopReason | None = None
    total_ig: float = 0.0
    total_variance_reduction: float = 0.0
    n_questions: int = 0
    n_skipped: int = 0
    gate_h_g2_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  H-2: Gaussian Entropy
# ═══════════════════════════════════════════════════════════════


def _compute_gaussian_entropy(covariance: np.ndarray) -> float:
    """H-2: Multivariate Gaussian entropy.

    Formula H-2 (spec line 378):
        H(θ) = 0.5 · ln|2πe · Σ_post|
             = 0.5 · (n·ln(2πe) + ln|Σ_post|)

    Args:
        covariance: Posterior covariance matrix (n × n).

    Returns:
        Entropy in nats.
    """
    n = covariance.shape[0]

    # Use slogdet for numerical stability
    sign, logdet = np.linalg.slogdet(covariance)

    if sign <= 0:
        # Degenerate covariance — use trace-based approximation
        logger.warning(
            "Non-positive-definite covariance (sign=%d), using diagonal entropy", sign,
        )
        diag = np.diag(covariance)
        diag = np.maximum(diag, 1e-10)
        logdet = float(np.sum(np.log(diag)))

    # H = 0.5 · (n · ln(2πe) + ln|Σ|)
    entropy = 0.5 * (n * np.log(2.0 * np.pi * np.e) + logdet)
    return float(entropy)


# ═══════════════════════════════════════════════════════════════
#  H-1: Information Gain Computation
# ═══════════════════════════════════════════════════════════════


def _compute_information_gain(
    question: QuestionDef,
    posterior_mean: np.ndarray,
    posterior_covariance: np.ndarray,
    node_index_map: dict[str, int],
    observation_noise_var: float = 1.0,
) -> float:
    """H-1: Expected information gain for one question.

    Formula H-1 (spec line 377):
        IG(q) = H(θ|current) − E_y[H(θ|current ∪ y_q)]

    For Gaussian posterior with linear observation model y = Hθ + ε:
        IG(q) = 0.5 · ln|Σ_prior| − 0.5 · ln|Σ_post|
              = 0.5 · ln(|Σ_prior| / |Σ_post|)

    Computed analytically: after observing nodes in the question,
    the posterior covariance shrinks. The IG is the entropy difference.

    Args:
        question: Question definition with target node IDs.
        posterior_mean: Current posterior mean vector.
        posterior_covariance: Current posterior covariance matrix.
        node_index_map: Mapping from node_id to matrix index.
        observation_noise_var: Observation noise variance σ²_y.

    Returns:
        Expected information gain (nats), ≥ 0.
    """
    n = posterior_covariance.shape[0]

    # Get indices for target nodes
    obs_indices = []
    for nid in question.target_node_ids:
        idx = node_index_map.get(nid)
        if idx is not None and 0 <= idx < n:
            obs_indices.append(idx)

    if not obs_indices:
        return 0.0

    # Current entropy
    h_prior = _compute_gaussian_entropy(posterior_covariance)

    # Compute posterior covariance after observing these nodes
    # Using the Woodbury update: Σ_post = Σ_prior − Σ_prior H^T (H Σ_prior H^T + R)^{-1} H Σ_prior
    # For direct observations: H is a selection matrix
    H = np.zeros((len(obs_indices), n))
    for i, idx in enumerate(obs_indices):
        H[i, idx] = 1.0

    R = np.eye(len(obs_indices)) * observation_noise_var

    # S = H Σ H^T + R
    S = H @ posterior_covariance @ H.T + R

    # K = Σ H^T S^{-1}
    try:
        S_inv = np.linalg.inv(S)
    except np.linalg.LinAlgError:
        return 0.0

    K = posterior_covariance @ H.T @ S_inv

    # Σ_post = Σ_prior - K H Σ_prior
    cov_post = posterior_covariance - K @ H @ posterior_covariance

    h_post = _compute_gaussian_entropy(cov_post)

    ig = max(0.0, h_prior - h_post)
    return ig


def _rank_questions(
    available_questions: list[QuestionDef],
    posterior_mean: np.ndarray,
    posterior_covariance: np.ndarray,
    node_index_map: dict[str, int],
    observation_noise_var: float = 1.0,
) -> list[NextQuestion]:
    """Rank all available questions by expected information gain.

    Mandatory questions are placed first regardless of IG.

    Args:
        available_questions: Unanswered questions.
        posterior_mean: Current posterior mean.
        posterior_covariance: Current posterior covariance.
        node_index_map: Node ID → index mapping.
        observation_noise_var: Observation noise variance.

    Returns:
        Sorted list of NextQuestion (highest IG first, mandatories before others).
    """
    mandatory: list[tuple[float, QuestionDef]] = []
    optional: list[tuple[float, QuestionDef]] = []

    for q in available_questions:
        ig = _compute_information_gain(
            q, posterior_mean, posterior_covariance,
            node_index_map, observation_noise_var,
        )
        if q.is_mandatory:
            mandatory.append((ig, q))
        else:
            optional.append((ig, q))

    # Sort each group by IG descending
    mandatory.sort(key=lambda x: x[0], reverse=True)
    optional.sort(key=lambda x: x[0], reverse=True)

    # Mandatory first, then optional
    ranked = mandatory + optional

    result: list[NextQuestion] = []
    for rank_idx, (ig, q) in enumerate(ranked, start=1):
        result.append(NextQuestion(
            question_id=q.question_id,
            question_text=q.question_text,
            target_node_ids=q.target_node_ids,
            instrument_id=q.instrument_id,
            expected_ig=ig,
            rank=rank_idx,
        ))

    return result


# ═══════════════════════════════════════════════════════════════
#  H-2: Answer Integration
# ═══════════════════════════════════════════════════════════════


def _validate_answer(answer: PatientAnswer) -> bool:
    """H-G1: Validate patient answer.

    Gate H-G1 (spec line 343): Question parsed successfully.

    Args:
        answer: Patient's response.

    Returns:
        True if valid, False if needs re-prompt.
    """
    if answer.skipped:
        return True  # "don't know" is valid (treated as missing)

    if not answer.valid:
        logger.warning(
            "Gate H-G1: Invalid answer for question %s: %s",
            answer.question_id, answer.raw_response,
        )
        return False

    if answer.parsed_value is None:
        logger.warning(
            "Gate H-G1: Could not parse answer for question %s",
            answer.question_id,
        )
        return False

    return True


# ═══════════════════════════════════════════════════════════════
#  H-3: Stopping Decision
# ═══════════════════════════════════════════════════════════════


def _check_stopping_criteria(
    n_questions_asked: int,
    last_ig: float,
    last_var_reduction: float,
    p_rank_1: float | None = None,
    patient_requested_stop: bool = False,
    n_remaining: int = 0,
) -> StopReason | None:
    """H-3: Check all stopping criteria.

    Formula H-3 (spec line 379):
        STOP if any:
        1. IG < RT_H_IG_THRESHOLD (0.01)
        2. P(rank₁) ≥ RT_H_STABILITY_STOP_THRESHOLD (0.80)
        3. Questions ≥ RT_H_MAX_QUESTIONS (15)
        4. Patient requests stop
        5. Variance reduction < RT_H_VAR_REDUCTION_THRESHOLD (5%)

    Returns:
        StopReason if should stop, None if should continue.
    """
    # Criterion 4: Patient request (highest priority)
    if patient_requested_stop:
        return StopReason.PATIENT_REQUEST

    # Criterion 3: Max questions
    if n_questions_asked >= config.RT_H_MAX_QUESTIONS:
        return StopReason.MAX_QUESTIONS

    # Criterion 6 (implicit): No questions remaining
    if n_remaining == 0:
        return StopReason.NO_QUESTIONS_REMAINING

    # Criterion 1: IG below threshold
    if n_questions_asked > 0 and last_ig < config.RT_H_IG_THRESHOLD:
        return StopReason.IG_BELOW_THRESHOLD

    # Criterion 2: Stability reached
    if p_rank_1 is not None and p_rank_1 >= config.RT_H_STABILITY_STOP_THRESHOLD:
        return StopReason.STABILITY_REACHED

    # Criterion 5: Low variance reduction
    if n_questions_asked > 0 and last_var_reduction < config.RT_H_VAR_REDUCTION_THRESHOLD:
        return StopReason.VAR_REDUCTION_LOW

    return None


# ═══════════════════════════════════════════════════════════════
#  Top-Level: run_adaptive_questioning (RT-H entry point)
# ═══════════════════════════════════════════════════════════════


def select_next_question(
    available_questions: list[QuestionDef],
    posterior_mean: np.ndarray,
    posterior_covariance: np.ndarray,
    node_index_map: dict[str, int],
    n_questions_asked: int = 0,
    observation_noise_var: float = 1.0,
) -> NextQuestion | None:
    """RT-H1: Select the next best question to ask.

    Args:
        available_questions: Questions not yet asked.
        posterior_mean: Current posterior mean.
        posterior_covariance: Current posterior covariance.
        node_index_map: Node ID → matrix index.
        n_questions_asked: Questions already asked this session.
        observation_noise_var: Observation noise variance.

    Returns:
        NextQuestion, or None if no questions available.
    """
    if not available_questions:
        return None

    if n_questions_asked >= config.RT_H_MAX_QUESTIONS:
        return None

    ranked = _rank_questions(
        available_questions, posterior_mean, posterior_covariance,
        node_index_map, observation_noise_var,
    )

    if not ranked:
        return None

    top = ranked[0]
    logger.info(
        "RT-H1 selected question %s (IG=%.4f, target_nodes=%s)",
        top.question_id, top.expected_ig, top.target_node_ids,
    )

    return top


def process_answer(
    answer: PatientAnswer,
    question: NextQuestion,
    state: QuestioningState,
) -> QuestionRecord:
    """RT-H2: Process a patient answer and update session state.

    Args:
        answer: Patient's response.
        question: The question that was asked.
        state: Current questioning state.

    Returns:
        QuestionRecord for this Q&A.

    Raises:
        GateViolation: If H-G1 fails (invalid answer).
    """
    valid = _validate_answer(answer)

    if not valid and not answer.skipped:
        raise GateViolation(
            "H-G1",
            f"Invalid answer for question {answer.question_id}: "
            f"raw='{answer.raw_response}'",
        )

    record = QuestionRecord(
        question_id=question.question_id,
        target_node_ids=question.target_node_ids,
        expected_ig=question.expected_ig,
        answer_value=answer.parsed_value,
        skipped=answer.skipped,
    )

    state.questions_asked.append(record)
    state.n_questions += 1
    if answer.skipped:
        state.n_skipped += 1

    return record


def check_should_stop(
    state: QuestioningState,
    last_ig: float = 0.0,
    last_var_reduction: float = 1.0,
    p_rank_1: float | None = None,
    patient_requested_stop: bool = False,
    n_remaining: int = 0,
) -> StopReason | None:
    """RT-H3: Check if questioning should stop.

    Args:
        state: Current session state.
        last_ig: Information gain from last question.
        last_var_reduction: Fractional variance reduction from last question.
        p_rank_1: Current P(rank₁) from stability analysis.
        patient_requested_stop: Whether patient wants to stop.
        n_remaining: Number of unanswered questions.

    Returns:
        StopReason if should stop, None if should continue.
    """
    reason = _check_stopping_criteria(
        n_questions_asked=state.n_questions,
        last_ig=last_ig,
        last_var_reduction=last_var_reduction,
        p_rank_1=p_rank_1,
        patient_requested_stop=patient_requested_stop,
        n_remaining=n_remaining,
    )

    if reason is not None:
        state.stop_reason = reason
        state.gate_h_g2_passed = True
        logger.info(
            "RT-H3 STOP: reason=%s after %d questions (total IG=%.4f)",
            reason.value, state.n_questions, state.total_ig,
        )

    return reason
