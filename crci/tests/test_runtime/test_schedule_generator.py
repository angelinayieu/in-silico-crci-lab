"""Tests for RT-G Schedule Optimization.

Covers:
    G1: Candidate expansion (top-K, dose/timing variants, bundles)
    G2: Constraint filtering (hard exclude, soft warn, bundle ceiling)
    G3: Schedule assembly (sort by SAFE_B, top N)
    G4: Stability classification attachment
    Gate G-G1: ≥1 feasible candidate
    Gate G-G2: SAFE_B > MID threshold
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_d_simulation.ranker import (
    ClaimLevel,
    InterventionRanking,
    BundleRanking,
    DoseRecommendation,
    RankingResult,
    SensitivityIndex,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus
from crci.algorithm.chain_f_analytics.variance_decomposer import StabilityClass, StabilityState

from crci.runtime.schedule_generator import (
    ConstraintSeverity,
    RankedSchedules,
    Schedule,
    ScheduleCandidate,
    TimingVariant,
    _assemble_schedules,
    _attach_stability,
    _expand_candidates,
    _filter_constraints,
    _validate_gate_g_g1,
    _validate_gate_g_g2,
    generate_schedule,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_intervention(aid: str, safe_b: float, safe_a: float = 0.0) -> InterventionRanking:
    """Create a minimal InterventionRanking for testing."""
    return InterventionRanking(
        action_id=aid,
        action_label=f"Label {aid}",
        safety_status=SafetyStatus.CLEAR,
        mss_cog=0.3,
        mss_burden=0.1,
        safe_a=safe_a or safe_b,
        safe_a_cri_lower=safe_b - 0.1,
        safe_a_cri_upper=safe_b + 0.1,
        rank_a=1,
        p_adhere=0.8,
        safe_b=safe_b,
        safe_b_cri_lower=safe_b - 0.15,
        safe_b_cri_upper=safe_b + 0.15,
        rank_b=1,
        adherence_warning=False,
        dose_recommended=3.0,
        dose_conflict=False,
        dose_conflict_ratio=None,
        claim_level=ClaimLevel.CAUSAL_SUPPORTED,
        per_draw_safe_a=np.array([safe_b] * 100),
    )


def _make_ranking_result(
    interventions: dict[str, float] | None = None,
    bundles: dict[str, tuple[float, tuple]] | None = None,
) -> RankingResult:
    """Create RankingResult from action_id → safe_b mapping."""
    rankings = {}
    if interventions:
        for i, (aid, sb) in enumerate(interventions.items()):
            r = _make_intervention(aid, sb)
            rankings[aid] = r

    bundle_rankings = {}
    if bundles:
        for bid, (sb, members) in bundles.items():
            bundle_rankings[bid] = BundleRanking(
                bundle_id=bid,
                member_ids=members,
                safe_a=sb,
                safe_a_cri_lower=sb - 0.1,
                safe_a_cri_upper=sb + 0.1,
                rank_a=1,
                p_adhere=0.7,
                safe_b=sb,
                safe_b_cri_lower=sb - 0.15,
                safe_b_cri_upper=sb + 0.15,
                rank_b=1,
                adherence_warning=False,
                claim_level=ClaimLevel.ASSOCIATIONAL_ONLY,
                per_draw_safe_a=np.array([sb] * 100),
            )

    return RankingResult(
        intervention_rankings=rankings,
        bundle_rankings=bundle_rankings,
        sensitivity_indices=[],
        top_discovery_edges=[],
        dose_recommendations={},
        n_interventions_ranked=len(rankings),
        n_bundles_ranked=len(bundle_rankings),
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


def _make_stability(probs: dict[str, float] | None = None) -> StabilityState:
    """Create a minimal StabilityState."""
    if probs is None:
        probs = {"a": 0.7, "b": 0.3}
    return StabilityState(
        rank_1_probabilities=probs,
        stability_class=StabilityClass.MODERATE,
        decision_critical_edges=[],
        flip_counts={},
        pairwise_dominance={},
        n_draws=100,
        n_interventions=len(probs),
    )


# ═══════════════════════════════════════════════════════════════
#  Test G1: Candidate Expansion
# ═══════════════════════════════════════════════════════════════


class TestCandidateExpansion:
    """Test RT-G1 candidate expansion."""

    def test_single_intervention_expands(self):
        """1 intervention → 6 candidates (3 dose × 2 timing)."""
        rr = _make_ranking_result({"a": 0.5})
        cands = _expand_candidates(rr)
        assert len(cands) == 6  # 3 dose × 2 timing

    def test_two_interventions(self):
        """2 interventions → 12 candidates."""
        rr = _make_ranking_result({"a": 0.5, "b": 0.4})
        cands = _expand_candidates(rr)
        assert len(cands) == 12

    def test_top_k_limits(self):
        """Only top_k interventions are expanded."""
        rr = _make_ranking_result({"a": 0.5, "b": 0.4, "c": 0.3})
        cands = _expand_candidates(rr, top_k=2)
        action_ids = {c.action_id for c in cands}
        assert "a" in action_ids
        assert "b" in action_ids
        assert "c" not in action_ids

    def test_bundles_included(self):
        """Bundle rankings are included in expanded pool."""
        rr = _make_ranking_result(
            interventions={"a": 0.5},
            bundles={"b_ab": (0.6, ("a", "b"))},
        )
        cands = _expand_candidates(rr)
        bundle_cands = [c for c in cands if c.is_bundle]
        assert len(bundle_cands) == 1
        assert bundle_cands[0].action_id == "b_ab"

    def test_max_pool_size_cap(self):
        """Pool capped at RT_G_MAX_POOL_SIZE."""
        many_interventions = {f"a{i}": float(i) / 100 for i in range(50)}
        rr = _make_ranking_result(many_interventions)
        cands = _expand_candidates(rr)
        assert len(cands) <= config.RT_G_MAX_POOL_SIZE

    def test_empty_ranking(self):
        rr = _make_ranking_result()
        cands = _expand_candidates(rr)
        assert len(cands) == 0

    def test_dose_variants_correct(self):
        """Low = 0.5×, standard = 1×, high = 1.5× of recommended dose."""
        rr = _make_ranking_result({"a": 0.5})
        cands = _expand_candidates(rr)
        dose_map = {c.dose_variant: c.dose_value for c in cands if c.timing == TimingVariant.IMMEDIATE}
        assert dose_map["standard"] == 3.0
        assert dose_map["low"] == 1.5
        assert dose_map["high"] == 4.5


# ═══════════════════════════════════════════════════════════════
#  Test G2: Constraint Filtering
# ═══════════════════════════════════════════════════════════════


class TestConstraintFiltering:
    """Test RT-G2 constraint filtering."""

    def test_no_constraints_all_pass(self):
        """No patient context → all candidates pass."""
        cands = [
            ScheduleCandidate(candidate_id="c1", action_id="a", action_label="A", is_bundle=False),
        ]
        feasible, excluded = _filter_constraints(cands)
        assert len(feasible) == 1
        assert len([e for e in excluded if e.severity == ConstraintSeverity.HARD_EXCLUDE]) == 0

    def test_patient_preference_exclusion(self):
        """Patient excludes a category → hard exclude."""
        cands = [
            ScheduleCandidate(candidate_id="c1", action_id="exercise", action_label="Exercise", is_bundle=False),
            ScheduleCandidate(candidate_id="c2", action_id="meditation", action_label="Meditation", is_bundle=False),
        ]
        feasible, excluded = _filter_constraints(
            cands, {"excluded_categories": ["exercise"]},
        )
        assert len(feasible) == 1
        assert feasible[0].action_id == "meditation"

    def test_bundle_ceiling_exceeded(self):
        """Bundle with |SAFE_A| > ceiling → hard exclude."""
        ceiling = config.RT_G_BUNDLE_CEILING_SD
        cands = [
            ScheduleCandidate(
                candidate_id="c1", action_id="b1", action_label="Bundle 1",
                is_bundle=True, safe_a=ceiling + 0.5,
            ),
        ]
        feasible, excluded = _filter_constraints(cands)
        assert len(feasible) == 0

    def test_bundle_within_ceiling_passes(self):
        """Bundle with |SAFE_A| ≤ ceiling → passes."""
        cands = [
            ScheduleCandidate(
                candidate_id="c1", action_id="b1", action_label="Bundle 1",
                is_bundle=True, safe_a=1.0,
            ),
        ]
        feasible, _ = _filter_constraints(cands)
        assert len(feasible) == 1

    def test_high_risk_patient_soft_warn(self):
        """Patient with active treatment → soft warning."""
        cands = [
            ScheduleCandidate(candidate_id="c1", action_id="a", action_label="A", is_bundle=False),
        ]
        feasible, excluded = _filter_constraints(
            cands, {"has_active_treatment": True},
        )
        assert len(feasible) == 1  # soft warn doesn't exclude
        soft_warns = [e for e in excluded if e.severity == ConstraintSeverity.SOFT_WARN]
        assert len(soft_warns) == 1


# ═══════════════════════════════════════════════════════════════
#  Test G3: Schedule Assembly
# ═══════════════════════════════════════════════════════════════


class TestScheduleAssembly:
    """Test RT-G3 schedule assembly."""

    def test_sort_by_safe_b(self):
        """Schedules sorted by SAFE_B descending."""
        cands = [
            ScheduleCandidate(candidate_id="c1", action_id="a", action_label="A",
                              is_bundle=False, safe_b=0.3),
            ScheduleCandidate(candidate_id="c2", action_id="b", action_label="B",
                              is_bundle=False, safe_b=0.8),
        ]
        schedules = _assemble_schedules(cands)
        assert schedules[0].safe_b == 0.8
        assert schedules[1].safe_b == 0.3

    def test_top_n_limit(self):
        """Only top N schedules returned."""
        cands = [
            ScheduleCandidate(
                candidate_id=f"c{i}", action_id=f"a{i}", action_label=f"A{i}",
                is_bundle=False, safe_b=float(i) / 10,
            )
            for i in range(20)
        ]
        schedules = _assemble_schedules(cands)
        assert len(schedules) == config.RT_G_TOP_SCHEDULES

    def test_rank_numbering(self):
        """Ranks are 1-indexed."""
        cands = [
            ScheduleCandidate(candidate_id="c1", action_id="a", action_label="A",
                              is_bundle=False, safe_b=0.5),
        ]
        schedules = _assemble_schedules(cands)
        assert schedules[0].rank == 1


# ═══════════════════════════════════════════════════════════════
#  Test G4: Stability Attachment
# ═══════════════════════════════════════════════════════════════


class TestStabilityAttachment:
    """Test RT-G4 stability classification."""

    def test_stability_attached(self):
        """Stability class is transferred to schedules."""
        schedules = [
            Schedule(schedule_id="s1", rank=1, items=[], safe_b=0.5,
                     safe_b_cri_lower=0.4, safe_b_cri_upper=0.6, safe_a=0.5),
        ]
        stab = _make_stability({"a": 0.9, "b": 0.1})
        stab.stability_class = StabilityClass.STABLE
        _attach_stability(schedules, stab)
        assert schedules[0].stability_class == StabilityClass.STABLE

    def test_none_stability_no_error(self):
        schedules = [
            Schedule(schedule_id="s1", rank=1, items=[], safe_b=0.5,
                     safe_b_cri_lower=0.4, safe_b_cri_upper=0.6, safe_a=0.5),
        ]
        _attach_stability(schedules, None)  # Should not raise


# ═══════════════════════════════════════════════════════════════
#  Test Gates
# ═══════════════════════════════════════════════════════════════


class TestGates:
    """Test RT-G gates."""

    def test_g_g1_passes_with_feasible(self):
        _validate_gate_g_g1(5)  # no raise

    def test_g_g1_fails_zero_feasible(self):
        with pytest.raises(GateViolation, match="G-G1"):
            _validate_gate_g_g1(0)

    def test_g_g2_confident(self):
        schedules = [
            Schedule(schedule_id="s1", rank=1, items=[], safe_b=0.8,
                     safe_b_cri_lower=0.6, safe_b_cri_upper=1.0, safe_a=0.8),
        ]
        assert _validate_gate_g_g2(schedules) is True

    def test_g_g2_marginal(self):
        schedules = [
            Schedule(schedule_id="s1", rank=1, items=[], safe_b=0.3,
                     safe_b_cri_lower=0.1, safe_b_cri_upper=0.5, safe_a=0.3),
        ]
        assert _validate_gate_g_g2(schedules) is False

    def test_g_g2_empty(self):
        assert _validate_gate_g_g2([]) is False


# ═══════════════════════════════════════════════════════════════
#  Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full RT-G pipeline tests."""

    def test_basic_pipeline(self):
        rr = _make_ranking_result({"ex_1": 0.6, "ex_2": 0.4})
        stab = _make_stability({"ex_1": 0.8, "ex_2": 0.2})
        result = generate_schedule(rr, stability_state=stab)
        assert result.gate_g_g1_passed
        assert result.n_expanded > 0
        assert result.n_feasible > 0
        assert len(result.schedules) > 0
        # Top schedule should be ex_1 (higher SAFE_B)
        assert result.schedules[0].items[0].action_id == "ex_1"

    def test_empty_ranking(self):
        """No interventions → GateViolation G-G1."""
        rr = _make_ranking_result()
        with pytest.raises(GateViolation, match="G-G1"):
            generate_schedule(rr)

    def test_all_excluded(self):
        """All candidates excluded → GateViolation G-G1."""
        rr = _make_ranking_result({"a": 0.5})
        ctx = {"excluded_categories": ["a"]}
        with pytest.raises(GateViolation, match="G-G1"):
            generate_schedule(rr, patient_context=ctx)


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify RT-G constants come from config."""

    def test_top_k_default(self):
        assert config.RT_G_TOP_K_DEFAULT == 10

    def test_max_pool_size(self):
        assert config.RT_G_MAX_POOL_SIZE == 100

    def test_bundle_ceiling(self):
        assert config.RT_G_BUNDLE_CEILING_SD == 1.5

    def test_top_schedules(self):
        assert config.RT_G_TOP_SCHEDULES == 5

    def test_safe_b_mid_threshold(self):
        assert config.RT_G_SAFE_B_MID_THRESHOLD == 0.5
