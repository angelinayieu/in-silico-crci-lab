# VERIFIED: formulas [F-4] match spec SYS_ALG lines 3193-3255
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads per_draw_safe_a from RankingResult (D4-D6)
# VERIFIED: forward wiring — writes StabilityState for F3 (evsi.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [F-G2] raises on failure
# VERIFIED: pairwise dominance handles ties correctly (stores p_gt, p_lt, p_tie)
# VERIFIED: pre-gate validates score array lengths and finiteness
# VERIFIED: score_mode selects SAFE_A or SAFE_B for stability analysis
"""
Component: SYS_ALGORITHM.ALG-F.F2
Spec: SYS_ALGORITHM_COMPLETE.md lines 3193-3255
Formulas:
    F-4: P(rank₁ = a) = (1/N) Σ_m 𝟙[rank₁^(m) = a]
Reads: RankingResult.per_draw_safe_a (from chain_d_simulation/ranker.py)
Writes: StabilityState (consumed by F3 evsi.py)
Gates: F-G2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_d_simulation.ranker import RankingResult

logger = logging.getLogger(__name__)

# Type alias for score_mode parameter
ScoreMode = Literal["SAFE_A", "SAFE_B"]


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class StabilityClass(str, Enum):
    """Ranking stability classification."""

    STABLE = "STABLE"                        # P(rank₁) ≥ 0.80
    MODERATE = "MODERATE"                    # 0.60 ≤ P < 0.80
    UNSTABLE = "UNSTABLE"                    # 0.40 ≤ P < 0.60
    HIGHLY_UNSTABLE = "HIGHLY_UNSTABLE"      # P < 0.40


@dataclass(frozen=True)
class PairwiseDominanceEntry:
    """Tie-correct pairwise dominance between two interventions.

    Invariant: p_gt + p_lt + p_tie ≈ 1.0
    """

    p_gt: float   # P(SAFE_a > SAFE_b)
    p_lt: float   # P(SAFE_a < SAFE_b)
    p_tie: float  # P(SAFE_a == SAFE_b)


@dataclass(frozen=True)
class CriticalEdge:
    """An edge whose uncertainty most affects the ranking."""

    edge_id: str
    flip_influence: float  # |rank₁_above − rank₁_below| / N


@dataclass
class StabilityState:
    """F2 output: Decision stability analysis.

    Consumed by F3 (variance decomposition) and downstream analytics.
    """

    rank_1_probabilities: dict[str, float]   # action_id → P(rank₁)
    stability_class: StabilityClass
    decision_critical_edges: list[CriticalEdge]
    flip_counts: dict[str, int]             # edge_id → flip count
    pairwise_dominance: dict[tuple[str, str], PairwiseDominanceEntry]  # (a, b) → dominance
    n_draws: int
    n_interventions: int
    score_mode: ScoreMode = "SAFE_A"         # which score stream was evaluated
    critical_edge_analysis_available: bool = False
    critical_edge_method: str | None = None
    gate_f_g2_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  F2a: Per-Draw Ranking
# ═══════════════════════════════════════════════════════════════


def _compute_per_draw_rankings(
    per_draw_scores: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], int]:
    """F2a: Rank interventions within each MC draw.

    For each draw, sort by SAFE score descending, assign rank 1 to highest.
    Tie-breaking: deterministic by sorted action_id (lexicographic). This is
    documented and intentional — ties between interventions are broken by
    alphabetical action_id order, making results reproducible regardless of
    dict insertion order.

    Args:
        per_draw_scores: action_id → array of SAFE scores (n_draws,).

    Returns:
        (per_draw_ranks: action_id → rank array, n_draws)
    """
    # Sort action_ids for deterministic tie-breaking
    action_ids = sorted(per_draw_scores.keys())
    if not action_ids:
        return {}, 0

    n_draws = len(per_draw_scores[action_ids[0]])
    n_actions = len(action_ids)

    # Build score matrix: (n_draws, n_actions)
    score_matrix = np.column_stack([per_draw_scores[a] for a in action_ids])

    # Rank per draw: argsort descending → rank
    # np.argsort is stable, so equal scores preserve column order = sorted action_id order
    per_draw_ranks: dict[str, np.ndarray] = {a: np.zeros(n_draws, dtype=int) for a in action_ids}

    for m in range(n_draws):
        # Sort descending: highest score gets rank 1
        order = np.argsort(-score_matrix[m, :], kind="stable")
        for rank, idx in enumerate(order):
            per_draw_ranks[action_ids[idx]][m] = rank + 1

    return per_draw_ranks, n_draws


# ═══════════════════════════════════════════════════════════════
#  F2b: Rank Probability + Stability Classification
# ═══════════════════════════════════════════════════════════════


def _compute_rank_probabilities(
    per_draw_ranks: dict[str, np.ndarray],
    n_draws: int,
) -> tuple[dict[str, float], StabilityClass]:
    """F2b: Compute P(rank₁ = a) and classify stability.

    Formula F-4: P(rank₁ = a) = (1/N) Σ_m 𝟙[rank₁^(m) = a]

    Returns:
        (rank_1_probabilities, stability_class)
    """
    if n_draws == 0:
        return {}, StabilityClass.HIGHLY_UNSTABLE

    rank_1_probs: dict[str, float] = {}

    for aid, ranks in per_draw_ranks.items():
        # Formula F-4: count draws where this action is rank 1
        rank_1_probs[aid] = float(np.sum(ranks == 1)) / n_draws

    # Stability classification based on max P(rank₁)
    max_prob = max(rank_1_probs.values()) if rank_1_probs else 0.0

    if max_prob >= config.F2_STABILITY_STABLE:
        stability = StabilityClass.STABLE
    elif max_prob >= config.F2_STABILITY_MODERATE:
        stability = StabilityClass.MODERATE
    elif max_prob >= config.F2_STABILITY_UNSTABLE:
        stability = StabilityClass.UNSTABLE
    else:
        stability = StabilityClass.HIGHLY_UNSTABLE

    return rank_1_probs, stability


def _compute_pairwise_dominance(
    per_draw_scores: dict[str, np.ndarray],
) -> dict[tuple[str, str], PairwiseDominanceEntry]:
    """Compute tie-correct pairwise dominance for all intervention pairs.

    For each pair (a, b):
        P(a > b) = (1/N) Σ_m 𝟙[SAFE(a)^(m) > SAFE(b)^(m)]
        P(a < b) = (1/N) Σ_m 𝟙[SAFE(a)^(m) < SAFE(b)^(m)]
        P(tie)   = 1.0 − P(a > b) − P(a < b)

    This correctly handles ties: P(a>b) + P(b>a) + P(tie) = 1.0.
    The old code used complement (1 - P(a>b)) which silently assigned
    tie mass to P(b>a), biasing the dominance matrix.
    """
    action_ids = sorted(per_draw_scores.keys())
    n_draws = len(per_draw_scores[action_ids[0]]) if action_ids else 0
    dominance: dict[tuple[str, str], PairwiseDominanceEntry] = {}

    for i, a in enumerate(action_ids):
        for j, b in enumerate(action_ids):
            if i >= j:
                continue
            scores_a = per_draw_scores[a]
            scores_b = per_draw_scores[b]

            p_gt = float(np.sum(scores_a > scores_b)) / n_draws
            p_lt = float(np.sum(scores_a < scores_b)) / n_draws
            p_tie = 1.0 - p_gt - p_lt

            dominance[(a, b)] = PairwiseDominanceEntry(p_gt=p_gt, p_lt=p_lt, p_tie=p_tie)
            dominance[(b, a)] = PairwiseDominanceEntry(p_gt=p_lt, p_lt=p_gt, p_tie=p_tie)

    return dominance


# ═══════════════════════════════════════════════════════════════
#  F2c: Decision-Critical Edge Identification
# ═══════════════════════════════════════════════════════════════


def _identify_critical_edges(
    per_draw_ranks: dict[str, np.ndarray],
    per_draw_edge_betas: dict[str, np.ndarray] | None,
    n_draws: int,
) -> tuple[list[CriticalEdge], dict[str, int]]:
    """F2c: Find top 3 edges whose uncertainty most affects ranking.

    For each edge e:
        Partition draws by β_e > median vs ≤ median.
        flip_influence(e) = |rank₁_above − rank₁_below| / N

    Args:
        per_draw_ranks: action_id → ranks (n_draws,).
        per_draw_edge_betas: edge_id → β values (n_draws,).
            If None, returns empty (no edge data available).
        n_draws: Number of MC draws.

    Returns:
        (top_critical_edges, flip_counts)
    """
    if per_draw_edge_betas is None or not per_draw_edge_betas or n_draws == 0:
        return [], {}

    action_ids = list(per_draw_ranks.keys())
    if not action_ids:
        return [], {}

    # Get the rank-1 action per draw
    rank_1_per_draw = np.zeros(n_draws, dtype=int)
    for idx, aid in enumerate(action_ids):
        mask = per_draw_ranks[aid] == 1
        rank_1_per_draw[mask] = idx

    flip_counts: dict[str, int] = {}
    edge_influences: list[tuple[str, float]] = []

    for edge_id, betas in per_draw_edge_betas.items():
        if len(betas) != n_draws:
            continue

        median_beta = float(np.median(betas))
        above_mask = betas > median_beta
        below_mask = ~above_mask

        n_above = int(np.sum(above_mask))
        n_below = int(np.sum(below_mask))

        # Spec line 3251: edge must have ≥100 draws in each partition
        if n_above < config.F2_MIN_DRAWS_PER_PARTITION or n_below < config.F2_MIN_DRAWS_PER_PARTITION:
            continue

        # Count rank-1 differences between partitions
        # For each action, check how many times it's rank-1 in each partition
        total_flips = 0
        for idx in range(len(action_ids)):
            rank1_above = np.sum(rank_1_per_draw[above_mask] == idx)
            rank1_below = np.sum(rank_1_per_draw[below_mask] == idx)
            total_flips += abs(int(rank1_above) - int(rank1_below))

        flip_influence = total_flips / n_draws
        flip_counts[edge_id] = total_flips
        edge_influences.append((edge_id, flip_influence))

    # Sort by influence descending, take top N
    edge_influences.sort(key=lambda x: x[1], reverse=True)
    n_critical = config.F2_N_CRITICAL_EDGES
    critical = [
        CriticalEdge(edge_id=eid, flip_influence=fi)
        for eid, fi in edge_influences[:n_critical]
    ]

    return critical, flip_counts


# ═══════════════════════════════════════════════════════════════
#  Gate F-G2
# ═══════════════════════════════════════════════════════════════


def _validate_score_arrays(
    per_draw_scores: dict[str, np.ndarray],
) -> int:
    """Pre-gate: validate all score arrays are consistent and finite.

    Checks:
        1. All arrays have the same length (n_draws).
        2. All values are finite (no NaN/Inf).
        3. n_draws >= 1 (when interventions exist).

    Returns:
        n_draws (validated).

    Raises:
        GateViolation: If any check fails.
    """
    if not per_draw_scores:
        return 0

    lengths = {aid: len(arr) for aid, arr in per_draw_scores.items()}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        raise GateViolation(
            "F-G2a",
            f"Score array lengths differ across interventions: {lengths}",
        )

    n_draws = unique_lengths.pop()
    if n_draws < 1:
        raise GateViolation(
            "F-G2a",
            "n_draws = 0 but interventions exist; cannot compute stability",
        )

    for aid, arr in per_draw_scores.items():
        if not np.all(np.isfinite(arr)):
            n_bad = int(np.sum(~np.isfinite(arr)))
            raise GateViolation(
                "F-G2a",
                f"Intervention {aid} has {n_bad} non-finite score(s) "
                f"(NaN/Inf) out of {n_draws} draws",
            )

    return n_draws


def _validate_gate_f_g2(result: StabilityState) -> None:
    """Gate F-G2: Decision stability valid.

    Conditions (spec line 3254):
        1. Σ P(rank₁ = a) ≈ 1.0 (within ε=0.001)
        2. stability_class assigned

    Raises:
        GateViolation: If any condition fails.
    """
    if result.rank_1_probabilities:
        prob_sum = sum(result.rank_1_probabilities.values())
        if abs(prob_sum - 1.0) > 0.001:
            raise GateViolation(
                "F-G2",
                f"Σ P(rank₁) = {prob_sum:.6f}, expected ≈ 1.0",
            )

    logger.info(
        "Gate F-G2 PASSED: stability=%s, max_P(rank₁)=%.3f, %d interventions, "
        "score_mode=%s",
        result.stability_class.value,
        max(result.rank_1_probabilities.values()) if result.rank_1_probabilities else 0.0,
        result.n_interventions,
        result.score_mode,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_decision_stability (F2 entry point)
# ═══════════════════════════════════════════════════════════════


def compute_decision_stability(
    ranking_result: RankingResult,
    per_draw_edge_betas: dict[str, np.ndarray] | None = None,
    score_mode: ScoreMode = "SAFE_A",
) -> StabilityState:
    """F2: Compute decision stability analysis.

    Args:
        ranking_result: RankingResult from D4-D6.
        per_draw_edge_betas: Optional edge β values per draw for
            decision-critical edge analysis (F2c).
        score_mode: Which score stream to evaluate stability on.
            "SAFE_A" — efficacy-only (default).
            "SAFE_B" — feasibility-adjusted (SAFE_A + 0.5·ln(p_adhere)).
            Must match the score stream used for the presented recommendation
            to avoid inconsistency between ranking and stability reports.

    Returns:
        StabilityState.

    Raises:
        GateViolation: If F-G2 or pre-gate F-G2a fails.
    """
    # Extract per-draw scores from ranking result
    per_draw_scores: dict[str, np.ndarray] = {}
    for aid, ranking in ranking_result.intervention_rankings.items():
        if score_mode == "SAFE_B":
            # Formula D-4: SAFE_B(a) = SAFE_A(a) + 0.5 × ln(P_adhere(a))
            # p_adhere is scalar per intervention; apply to all draws
            if ranking.p_adhere <= 0.0:
                raise GateViolation(
                    "F-G2a",
                    f"Intervention {aid}: p_adhere={ranking.p_adhere} ≤ 0, "
                    "cannot compute ln(p_adhere) for SAFE_B",
                )
            per_draw_scores[aid] = (
                ranking.per_draw_safe_a
                + config.D4_ADHERENCE_ADJUSTMENT_WEIGHT * np.log(ranking.p_adhere)
            )
        else:
            per_draw_scores[aid] = ranking.per_draw_safe_a

    n_interventions = len(per_draw_scores)

    logger.info(
        "── F2: Decision Stability Analysis ──\n"
        "  n_interventions=%d, score_mode=%s",
        n_interventions,
        score_mode,
    )

    # Pre-gate F-G2a: validate score arrays
    n_draws = _validate_score_arrays(per_draw_scores)

    # F2a: Per-draw ranking
    per_draw_ranks, n_draws = _compute_per_draw_rankings(per_draw_scores)

    # F2b: Rank probabilities + stability
    rank_1_probs, stability = _compute_rank_probabilities(per_draw_ranks, n_draws)

    # F2b: Pairwise dominance (tie-correct)
    dominance = _compute_pairwise_dominance(per_draw_scores)

    # F2c: Decision-critical edges
    has_edge_data = per_draw_edge_betas is not None and len(per_draw_edge_betas) > 0
    critical_edges, flip_counts = _identify_critical_edges(
        per_draw_ranks, per_draw_edge_betas, n_draws,
    )

    result = StabilityState(
        rank_1_probabilities=rank_1_probs,
        stability_class=stability,
        decision_critical_edges=critical_edges,
        flip_counts=flip_counts,
        pairwise_dominance=dominance,
        n_draws=n_draws,
        n_interventions=n_interventions,
        score_mode=score_mode,
        critical_edge_analysis_available=has_edge_data,
        critical_edge_method="median_split_rank1_distribution" if has_edge_data else None,
    )

    # Gate F-G2
    _validate_gate_f_g2(result)
    result.gate_f_g2_passed = True

    logger.info(
        "F2 complete: stability=%s, %d interventions, %d draws, mode=%s",
        stability.value, n_interventions, n_draws, score_mode,
    )

    return result
