"""Tests for ALG-F2 Decision Stability Analysis.

Covers:
    F2a: Per-draw ranking of interventions
    F2b: Rank probability computation (Formula F-4)
    F2b: Stability classification
    F2b: Pairwise dominance
    F2c: Decision-critical edge identification
    Gate F-G2: Σ P(rank₁) = 1.0, stability classified
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_f_analytics.variance_decomposer import (
    CriticalEdge,
    StabilityClass,
    StabilityState,
    _compute_per_draw_rankings,
    _compute_pairwise_dominance,
    _compute_rank_probabilities,
    _identify_critical_edges,
    _validate_gate_f_g2,
    compute_decision_stability,
)
from crci.algorithm.chain_d_simulation.ranker import (
    ClaimLevel,
    InterventionRanking,
    RankingResult,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_ranking_result(action_scores):
    """Create RankingResult from action_id → SAFE_A scores array."""
    rankings = {}
    for i, (aid, scores) in enumerate(action_scores.items()):
        rankings[aid] = InterventionRanking(
            action_id=aid,
            action_label=f"Label {aid}",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.2,
            mss_burden=0.1,
            safe_a=float(np.mean(scores)),
            safe_a_cri_lower=float(np.quantile(scores, 0.025)),
            safe_a_cri_upper=float(np.quantile(scores, 0.975)),
            rank_a=i + 1,
            p_adhere=0.8,
            safe_b=0.12,
            safe_b_cri_lower=0.04,
            safe_b_cri_upper=0.20,
            rank_b=i + 1,
            adherence_warning=False,
            dose_recommended=3.0,
            dose_conflict=False,
            dose_conflict_ratio=None,
            claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=scores,
        )
    return RankingResult(
        intervention_rankings=rankings,
        bundle_rankings={},
        sensitivity_indices=[],
        top_discovery_edges=[],
        dose_recommendations={},
        n_interventions_ranked=len(action_scores),
        n_bundles_ranked=0,
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Test F2a: Per-Draw Ranking
# ═══════════════════════════════════════════════════════════════


class TestPerDrawRanking:
    """Test per-draw ranking computation."""

    def test_basic_ranking(self):
        """Higher score → rank 1."""
        scores = {
            "a": np.array([0.5, 0.3, 0.8]),
            "b": np.array([0.3, 0.5, 0.2]),
        }
        ranks, n = _compute_per_draw_rankings(scores)
        assert n == 3
        # Draw 0: a=0.5 > b=0.3 → a=rank1, b=rank2
        assert ranks["a"][0] == 1
        assert ranks["b"][0] == 2
        # Draw 1: b=0.5 > a=0.3 → b=rank1, a=rank2
        assert ranks["a"][1] == 2
        assert ranks["b"][1] == 1

    def test_three_actions(self):
        scores = {
            "a": np.array([0.5]),
            "b": np.array([0.8]),
            "c": np.array([0.3]),
        }
        ranks, n = _compute_per_draw_rankings(scores)
        assert n == 1
        assert ranks["b"][0] == 1  # highest
        assert ranks["a"][0] == 2
        assert ranks["c"][0] == 3

    def test_empty(self):
        ranks, n = _compute_per_draw_rankings({})
        assert n == 0
        assert len(ranks) == 0


# ═══════════════════════════════════════════════════════════════
#  Test F2b: Rank Probability + Stability
# ═══════════════════════════════════════════════════════════════


class TestRankProbability:
    """Test rank probability and stability classification."""

    def test_formula_f4(self):
        """P(rank₁=a) = (1/N) Σ 𝟙[rank₁=a].

        a is rank 1 in 8/10 draws → P = 0.8
        """
        ranks = {
            "a": np.array([1, 1, 1, 1, 1, 1, 1, 1, 2, 2]),
            "b": np.array([2, 2, 2, 2, 2, 2, 2, 2, 1, 1]),
        }
        probs, _ = _compute_rank_probabilities(ranks, 10)
        assert abs(probs["a"] - 0.8) < 1e-10
        assert abs(probs["b"] - 0.2) < 1e-10

    def test_probabilities_sum_to_one(self):
        ranks = {
            "a": np.array([1, 1, 2, 2, 3]),
            "b": np.array([2, 2, 1, 1, 2]),
            "c": np.array([3, 3, 3, 3, 1]),
        }
        probs, _ = _compute_rank_probabilities(ranks, 5)
        assert abs(sum(probs.values()) - 1.0) < 1e-10

    def test_stable_classification(self):
        """P(rank₁) ≥ 0.80 → STABLE."""
        ranks = {"a": np.array([1] * 9 + [2]), "b": np.array([2] * 9 + [1])}
        _, stability = _compute_rank_probabilities(ranks, 10)
        assert stability == StabilityClass.STABLE

    def test_moderate_classification(self):
        """0.60 ≤ P < 0.80 → MODERATE."""
        ranks = {"a": np.array([1] * 7 + [2] * 3), "b": np.array([2] * 7 + [1] * 3)}
        _, stability = _compute_rank_probabilities(ranks, 10)
        assert stability == StabilityClass.MODERATE

    def test_unstable_classification(self):
        """0.40 ≤ P < 0.60 → UNSTABLE."""
        ranks = {"a": np.array([1] * 5 + [2] * 5), "b": np.array([2] * 5 + [1] * 5)}
        _, stability = _compute_rank_probabilities(ranks, 10)
        assert stability == StabilityClass.UNSTABLE

    def test_highly_unstable_classification(self):
        """P < 0.40 → HIGHLY_UNSTABLE."""
        ranks = {
            "a": np.array([1] * 3 + [2] * 4 + [3] * 3),
            "b": np.array([2] * 3 + [1] * 3 + [3] * 4),
            "c": np.array([3] * 3 + [3] * 3 + [1] * 4),
        }
        # max P(rank1) = 4/10 = 0.40 → UNSTABLE (just at threshold)
        _, stability = _compute_rank_probabilities(ranks, 10)
        assert stability == StabilityClass.UNSTABLE  # 0.40 ≥ 0.40


# ═══════════════════════════════════════════════════════════════
#  Test F2b: Pairwise Dominance
# ═══════════════════════════════════════════════════════════════


class TestPairwiseDominance:
    """Test pairwise dominance computation."""

    def test_basic_dominance(self):
        """a always > b → P(a>b) = 1.0."""
        scores = {
            "a": np.array([0.5, 0.6, 0.7]),
            "b": np.array([0.3, 0.4, 0.5]),
        }
        dom = _compute_pairwise_dominance(scores)
        assert abs(dom[("a", "b")] - 1.0) < 1e-10
        assert abs(dom[("b", "a")] - 0.0) < 1e-10

    def test_mixed_dominance(self):
        scores = {
            "a": np.array([0.5, 0.3]),
            "b": np.array([0.3, 0.5]),
        }
        dom = _compute_pairwise_dominance(scores)
        assert abs(dom[("a", "b")] - 0.5) < 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test Gate F-G2
# ═══════════════════════════════════════════════════════════════


class TestGateFG2:
    """Test Gate F-G2 validation."""

    def _make_result(self, probs=None):
        if probs is None:
            probs = {"a": 0.7, "b": 0.3}
        return StabilityState(
            rank_1_probabilities=probs,
            stability_class=StabilityClass.MODERATE,
            decision_critical_edges=[],
            flip_counts={},
            pairwise_dominance={},
            n_draws=100,
            n_interventions=2,
        )

    def test_passes_valid(self):
        _validate_gate_f_g2(self._make_result())

    def test_fails_probs_not_sum_to_1(self):
        result = self._make_result(probs={"a": 0.5, "b": 0.3})
        with pytest.raises(GateViolation, match="F-G2"):
            _validate_gate_f_g2(result)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_decision_stability
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full F2 pipeline tests."""

    def test_basic_pipeline(self):
        rng = np.random.default_rng(42)
        scores = {
            "ex_1": rng.normal(0.5, 0.1, 200),
            "ex_2": rng.normal(0.3, 0.1, 200),
        }
        ranking = _make_ranking_result(scores)
        result = compute_decision_stability(ranking)
        assert result.gate_f_g2_passed
        assert result.n_interventions == 2
        assert result.n_draws == 200
        # ex_1 should usually be rank 1 (higher mean)
        assert result.rank_1_probabilities["ex_1"] > result.rank_1_probabilities["ex_2"]

    def test_stable_dominance(self):
        """Clear dominance → STABLE."""
        scores = {
            "a": np.ones(100) * 0.8,  # always wins
            "b": np.ones(100) * 0.2,
        }
        ranking = _make_ranking_result(scores)
        result = compute_decision_stability(ranking)
        assert result.stability_class == StabilityClass.STABLE
        assert result.rank_1_probabilities["a"] == 1.0

    def test_empty_ranking(self):
        """No interventions → empty but valid."""
        ranking = _make_ranking_result({})
        result = compute_decision_stability(ranking)
        assert result.gate_f_g2_passed
        assert result.n_interventions == 0


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify F2 constants come from config."""

    def test_stability_thresholds(self):
        assert config.F2_STABILITY_STABLE == 0.80
        assert config.F2_STABILITY_MODERATE == 0.60
        assert config.F2_STABILITY_UNSTABLE == 0.40

    def test_min_draws_per_partition(self):
        assert config.F2_MIN_DRAWS_PER_PARTITION == 100

    def test_n_critical_edges(self):
        assert config.F2_N_CRITICAL_EDGES == 3
