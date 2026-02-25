"""Tests for SYS_RUNTIME session orchestrator.

Covers:
    - Full pipeline: RT-G → RT-I → RecommendationReport
    - Session configuration
    - Graceful handling of missing optional inputs
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared.models.enums import ReportOutputMode
from crci.shared.models.output_contracts import RecommendationReport

from crci.algorithm.chain_d_simulation.ranker import (
    ClaimLevel,
    InterventionRanking,
    RankingResult,
)
from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus
from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)
from crci.algorithm.chain_f_analytics.variance_decomposer import (
    StabilityClass as F2StabilityClass,
    StabilityState,
)

from crci.runtime.session import (
    SessionConfig,
    SessionResult,
    run_session,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_intervention(aid: str, safe_b: float) -> InterventionRanking:
    return InterventionRanking(
        action_id=aid,
        action_label=f"Label {aid}",
        safety_status=SafetyStatus.CLEAR,
        mss_cog=0.3,
        mss_burden=0.1,
        safe_a=safe_b,
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


def _make_ranking_result() -> RankingResult:
    return RankingResult(
        intervention_rankings={
            "ex_1": _make_intervention("ex_1", 0.6),
            "ex_2": _make_intervention("ex_2", 0.4),
        },
        bundle_rankings={},
        sensitivity_indices=[],
        top_discovery_edges=[],
        dose_recommendations={},
        n_interventions_ranked=2,
        n_bundles_ranked=0,
        n_blocked=0,
        gate_d_g4_passed=True,
        gate_d_g5_passed=True,
        gate_d_g6_passed=True,
    )


def _make_composite() -> CompositeState:
    return CompositeState(
        crci_composite=-0.5,
        severity_tier=F1SeverityTier.MILD_IMPAIRMENT,
        percentile=30.0,
        subdomain_scores={"processing_speed": -0.3},
        subdomain_weights={"processing_speed": 1.0},
        cochrans_Q=2.0,
        I_squared=10.0,
        random_effects_applied=False,
        severity_weighted_z={"processing_speed": -0.3},
        n_domains=1,
        gate_f_g1_passed=True,
    )


def _make_stability() -> StabilityState:
    return StabilityState(
        rank_1_probabilities={"ex_1": 0.75, "ex_2": 0.25},
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[],
        flip_counts={},
        pairwise_dominance={},
        n_draws=200,
        n_interventions=2,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestRunSession:
    """Test full session orchestration."""

    def test_basic_session(self):
        """Full pipeline produces a valid report."""
        cfg = SessionConfig(subject_ref="patient_001")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
            composite=_make_composite(),
            stability=_make_stability(),
        )
        assert isinstance(result, SessionResult)
        assert isinstance(result.report, RecommendationReport)
        assert result.report.subject_ref == "patient_001"
        assert result.report.composite_score.composite_z == -0.5
        assert len(result.ranked_schedules.schedules) > 0

    def test_minimal_session(self):
        """Session with only required inputs."""
        cfg = SessionConfig(subject_ref="patient_002")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        assert result.report.composite_score.composite_z == 0.0  # no composite provided
        assert result.report.variance_decomposition is None

    def test_research_mode(self):
        cfg = SessionConfig(
            subject_ref="patient_003",
            output_mode=ReportOutputMode.RESEARCH,
        )
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        assert result.report.output_mode == ReportOutputMode.RESEARCH

    def test_run_id_unique(self):
        cfg = SessionConfig(subject_ref="patient_004")
        rr = _make_ranking_result()
        r1 = run_session(session_config=cfg, ranking_result=rr)
        r2 = run_session(session_config=cfg, ranking_result=rr)
        assert r1.run_id != r2.run_id

    def test_top_schedule_is_best(self):
        """Primary schedule should have highest SAFE_B."""
        cfg = SessionConfig(subject_ref="patient_005")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        primary = result.report.primary_schedule
        for alt in result.report.alternative_schedules:
            assert primary.utility_score >= alt.utility_score

    def test_timestamps_populated(self):
        cfg = SessionConfig(subject_ref="patient_006")
        result = run_session(
            session_config=cfg,
            ranking_result=_make_ranking_result(),
        )
        assert result.start_time != ""
        assert result.end_time != ""
