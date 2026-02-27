"""Tests for RT-I Report Assembler.

Covers:
    I1: Evidence provenance building
    I2: Mandatory uncertainty disclosure
    I3: Session summary
    I4: Full report assembly
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import ReportOutputMode, StabilityClass
from crci.shared.models.output_contracts import RecommendationReport

from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)
from crci.algorithm.chain_f_analytics.variance_decomposer import (
    CriticalEdge,
    StabilityClass as F2StabilityClass,
    StabilityState,
)
from crci.algorithm.chain_f_analytics.evsi import ReducibleSource, VarianceState

from crci.runtime.schedule_generator import (
    RankedSchedules,
    Schedule,
    ScheduleItem,
    TimingVariant,
)
from crci.runtime.adaptive_questions import (
    QuestioningState,
    StopReason,
)
from crci.runtime.report_assembler import (
    ProvenanceEntry,
    UncertaintyDisclosure,
    SessionSummary,
    _build_provenance,
    _build_uncertainty_disclosure,
    _build_session_summary,
    _build_composite_score,
    _build_variance_decomposition,
    _build_clinical_risk,
    _build_pathway_profile,
    _build_subpopulation_summary,
    _build_sensitivity_report,
    _classify_output_severity,
    assemble_report,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_schedule(aid: str = "a1", safe_b: float = 0.6, rank: int = 1) -> Schedule:
    return Schedule(
        schedule_id=f"sched_{rank:03d}",
        rank=rank,
        items=[ScheduleItem(
            action_id=aid,
            action_label=f"Label {aid}",
            dose_value=3.0,
        )],
        safe_b=safe_b,
        safe_b_cri_lower=safe_b - 0.1,
        safe_b_cri_upper=safe_b + 0.1,
        safe_a=safe_b,
        claim_level="causal_supported",
    )


def _make_ranked_schedules(n: int = 2) -> RankedSchedules:
    schedules = [
        _make_schedule(f"a{i}", safe_b=0.8 - i * 0.2, rank=i + 1)
        for i in range(n)
    ]
    return RankedSchedules(
        schedules=schedules,
        n_expanded=20,
        n_feasible=n,
        n_excluded=0,
        excluded_reasons=[],
        gate_g_g1_passed=True,
        gate_g_g2_passed=True,
    )


def _make_composite() -> CompositeState:
    return CompositeState(
        crci_composite=-0.5,
        severity_tier=F1SeverityTier.MILD_IMPAIRMENT,
        percentile=30.0,
        subdomain_scores={"processing_speed": -0.3, "memory_verbal": -0.7},
        subdomain_weights={"processing_speed": 1.0, "memory_verbal": 1.5},
        cochrans_Q=5.0,
        I_squared=20.0,
        random_effects_applied=False,
        severity_weighted_z={"processing_speed": -0.3, "memory_verbal": -1.05},
        n_domains=2,
        gate_f_g1_passed=True,
    )


def _make_stability() -> StabilityState:
    return StabilityState(
        rank_1_probabilities={"a0": 0.75, "a1": 0.25},
        stability_class=F2StabilityClass.MODERATE,
        decision_critical_edges=[
            CriticalEdge(edge_id="e1", flip_influence=0.15),
        ],
        flip_counts={},
        pairwise_dominance={},
        n_draws=200,
        n_interventions=2,
    )


def _make_variance() -> VarianceState:
    return VarianceState(
        total_variance=1.0,
        literature_pct=0.30,
        measurement_pct=0.15,
        structural_pct=0.20,
        proxy_pct=0.15,
        missing_pct=0.20,
        literature_variance=0.30,
        measurement_variance=0.15,
        structural_variance=0.20,
        proxy_variance=0.15,
        missing_variance=0.20,
        top_reducible=[
            ReducibleSource(source_name="missing_observations", reduction_pct=0.20),
            ReducibleSource(source_name="measurement_noise", reduction_pct=0.15),
        ],
        per_edge_variance_contrib={},
    )


def _make_questioning() -> QuestioningState:
    state = QuestioningState(questions_asked=[])
    state.n_questions = 5
    state.n_skipped = 1
    state.stop_reason = StopReason.STABILITY_REACHED
    state.total_ig = 1.5
    return state


# ═══════════════════════════════════════════════════════════════
#  Test I1: Provenance
# ═══════════════════════════════════════════════════════════════


class TestProvenance:
    """Test evidence provenance building."""

    def test_basic_provenance(self):
        schedules = [_make_schedule("a1", rank=1)]
        entries = _build_provenance(schedules)
        assert len(entries) == 1
        assert entries[0].intervention_id == "a1"
        assert entries[0].claim_level == "causal_supported"

    def test_multiple_schedules(self):
        schedules = [_make_schedule(f"a{i}", rank=i + 1) for i in range(3)]
        entries = _build_provenance(schedules)
        assert len(entries) == 3

    def test_empty_schedules(self):
        entries = _build_provenance([])
        assert len(entries) == 0


# ═══════════════════════════════════════════════════════════════
#  Test I2: Uncertainty Disclosure
# ═══════════════════════════════════════════════════════════════


class TestUncertaintyDisclosure:
    """Test mandatory uncertainty disclosure."""

    def test_basic_disclosure(self):
        stab = _make_stability()
        var = _make_variance()
        sched = _make_schedule()
        disc = _build_uncertainty_disclosure(stab, var, sched)
        assert disc.stability_class == "MODERATE"
        assert disc.p_rank_1 == 0.75
        assert abs(disc.variance_decomposition["literature"] - 0.30) < 1e-10
        assert len(disc.top_reducible_sources) == 2
        assert disc.warning_text is None  # Not highly unstable

    def test_highly_unstable_warning(self):
        stab = _make_stability()
        stab.stability_class = F2StabilityClass.HIGHLY_UNSTABLE
        disc = _build_uncertainty_disclosure(stab, None, None)
        assert disc.warning_text is not None
        assert "highly uncertain" in disc.warning_text.lower()

    def test_none_inputs(self):
        disc = _build_uncertainty_disclosure(None, None, None)
        assert disc.stability_class == "MODERATE"
        assert disc.p_rank_1 == 0.0

    def test_critical_edges_included(self):
        stab = _make_stability()
        disc = _build_uncertainty_disclosure(stab, None, None)
        assert "e1" in disc.critical_edges


# ═══════════════════════════════════════════════════════════════
#  Test I3: Session Summary
# ═══════════════════════════════════════════════════════════════


class TestSessionSummary:
    """Test session summary building."""

    def test_with_questioning(self):
        qs = _make_questioning()
        summary = _build_session_summary(qs)
        assert summary.n_questions_asked == 5
        assert summary.n_questions_skipped == 1
        assert summary.stop_reason == "stability_reached"

    def test_none_questioning(self):
        summary = _build_session_summary(None)
        assert summary.n_questions_asked == 0
        assert summary.timestamp is not None


# ═══════════════════════════════════════════════════════════════
#  Test Composite Score Building
# ═══════════════════════════════════════════════════════════════


class TestCompositeScore:
    """Test composite score output building."""

    def test_basic_composite(self):
        comp = _make_composite()
        cs = _build_composite_score(comp, "run1", "patient1")
        assert cs.composite_z == -0.5
        assert cs.composite_percentile == 30.0
        assert len(cs.domain_scores) == 2

    def test_none_composite(self):
        cs = _build_composite_score(None, "run1", "patient1")
        assert cs.composite_z == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test Variance Decomposition Building
# ═══════════════════════════════════════════════════════════════


class TestVarianceDecomposition:
    """Test variance decomposition output building."""

    def test_basic_decomposition(self):
        var = _make_variance()
        vd = _build_variance_decomposition(var, "run1")
        assert vd is not None
        assert len(vd.components) == 5
        assert vd.total_variance == 1.0
        assert vd.dominant_source is not None

    def test_none_variance(self):
        vd = _build_variance_decomposition(None, "run1")
        assert vd is None


# ═══════════════════════════════════════════════════════════════
#  Integration: Full Report Assembly
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full RT-I pipeline tests."""

    def test_full_report(self):
        report = assemble_report(
            run_id="run_001",
            subject_ref="patient_001",
            ranked_schedules=_make_ranked_schedules(3),
            composite=_make_composite(),
            stability=_make_stability(),
            variance=_make_variance(),
            questioning=_make_questioning(),
        )
        assert isinstance(report, RecommendationReport)
        assert report.run_id == "run_001"
        assert report.subject_ref == "patient_001"
        assert report.composite_score.composite_z == -0.5
        assert report.primary_schedule.plan_rank == 1
        assert len(report.alternative_schedules) == 2
        assert report.variance_decomposition is not None
        assert report.decision_trace is not None
        assert len(report.decision_trace.entries) > 0

    def test_minimal_report(self):
        """Report with minimal inputs (no composite, stability, etc.)."""
        report = assemble_report(
            run_id="run_002",
            subject_ref="patient_002",
            ranked_schedules=_make_ranked_schedules(1),
        )
        assert report.run_id == "run_002"
        assert report.composite_score.composite_z == 0.0
        assert report.variance_decomposition is None

    def test_empty_schedules(self):
        """Report with no schedules → empty primary."""
        rs = RankedSchedules(
            schedules=[],
            n_expanded=0,
            n_feasible=0,
            n_excluded=0,
            excluded_reasons=[],
            gate_g_g1_passed=False,
        )
        report = assemble_report(
            run_id="run_003",
            subject_ref="patient_003",
            ranked_schedules=rs,
        )
        assert report.primary_schedule.schedule_id == "empty"
        assert len(report.alternative_schedules) == 0

    def test_marginal_recommendation_warning(self):
        """Gate G-G2 not passed → warning in report."""
        rs = _make_ranked_schedules(1)
        rs.gate_g_g2_passed = False
        report = assemble_report(
            run_id="run_004",
            subject_ref="patient_004",
            ranked_schedules=rs,
        )
        assert any("Marginal" in w for w in report.run_warnings)

    def test_research_mode(self):
        report = assemble_report(
            run_id="run_005",
            subject_ref="patient_005",
            ranked_schedules=_make_ranked_schedules(1),
            output_mode=ReportOutputMode.RESEARCH,
        )
        assert report.output_mode == ReportOutputMode.RESEARCH


# ═══════════════════════════════════════════════════════════════
#  Test Clinical Risk Builder (F4 → ClinicalRiskProfile)
# ═══════════════════════════════════════════════════════════════


class TestClinicalRisk:
    """Test _build_clinical_risk mapping from F4 CRCIRiskEstimate."""

    def _make_risk_estimate(self):
        from dataclasses import dataclass, field as dc_field
        from crci.algorithm.chain_f_analytics.risk_estimator import (
            CRCIRiskEstimate,
            DomainRiskProfile,
        )
        dp = DomainRiskProfile(
            domain_id="processing_speed",
            domain_label="Processing Speed",
            node_ids=["N_PS_01"],
            marginal_risk_pct=35.0,
            trigger_share_pct=20.0,
            ivw_weight_pct=15.0,
            mean_z=-0.8,
            sd_z=0.3,
            z_5th=-1.3,
            z_95th=-0.3,
            is_directly_observed=True,
            n_observations=2,
        )
        return CRCIRiskEstimate(
            risk_pct=36.5,
            risk_lower_pct=32.0,
            risk_upper_pct=41.0,
            risk_tier="MODERATE",
            risk_range_text="32%–41%",
            interval_method="jeffreys",
            interval_level=0.90,
            mc_se=0.005,
            n_draws_used=5000,
            coverage_fraction=0.8,
            low_coverage_warning=False,
            domain_profiles=[dp],
        )

    def test_basic_clinical_risk(self):
        est = self._make_risk_estimate()
        profile = _build_clinical_risk(est)
        assert profile is not None
        assert profile.risk_pct == 36.5
        assert profile.risk_tier == "MODERATE"
        assert len(profile.domain_breakdown) == 1
        assert profile.domain_breakdown[0].domain_id == "processing_speed"
        assert profile.domain_breakdown[0].marginal_risk_pct == 35.0

    def test_none_returns_none(self):
        assert _build_clinical_risk(None) is None

    def test_full_report_with_risk(self):
        """Full report assembly including clinical risk."""
        est = self._make_risk_estimate()
        report = assemble_report(
            run_id="run_risk",
            subject_ref="patient_risk",
            ranked_schedules=_make_ranked_schedules(1),
            risk_estimate=est,
        )
        assert report.clinical_risk is not None
        assert report.clinical_risk.risk_pct == 36.5


# ═══════════════════════════════════════════════════════════════
#  Test Pathway Profile Builder (C4d → PathwayProfile)
# ═══════════════════════════════════════════════════════════════


class TestPathwayProfile:
    """Test _build_pathway_profile mapping from C4d PathwayActivation list."""

    def _make_activations(self):
        from crci.algorithm.chain_c_posterior.modifier_application import (
            PathwayActivation,
        )
        return [
            PathwayActivation(
                pathway_id="PW_INFLAM",
                pathway_label="Neuroinflammatory",
                activation_score=1.2,
                threshold=0.5,
                is_active=True,
                n_nodes=4,
                high_uncertainty=False,
            ),
            PathwayActivation(
                pathway_id="PW_OXSTR",
                pathway_label="Oxidative Stress",
                activation_score=0.3,
                threshold=0.5,
                is_active=False,
                n_nodes=3,
                high_uncertainty=False,
            ),
            PathwayActivation(
                pathway_id="PW_BBBDIS",
                pathway_label="BBB Disruption",
                activation_score=0.7,
                threshold=0.5,
                is_active=True,
                n_nodes=2,
                high_uncertainty=True,
            ),
        ]

    def test_basic_pathway_profile(self):
        activations = self._make_activations()
        profile = _build_pathway_profile(activations, "run1", "patient1")
        assert profile is not None
        assert len(profile.pathway_contributions) == 3
        assert profile.dominant_pathway_id == "PW_INFLAM"  # highest activation_score
        assert profile.coverage_fraction == pytest.approx(2 / 3)

    def test_evidence_quality_flag(self):
        activations = self._make_activations()
        profile = _build_pathway_profile(activations, "run1", "patient1")
        # BBB Disruption has high_uncertainty → flagged
        bbb = [c for c in profile.pathway_contributions if c.pathway_id == "PW_BBBDIS"][0]
        assert bbb.evidence_quality == "high_uncertainty"
        # Neuroinflammatory is normal
        inflam = [c for c in profile.pathway_contributions if c.pathway_id == "PW_INFLAM"][0]
        assert inflam.evidence_quality == "normal"

    def test_inactive_pathway_zero_activation(self):
        activations = self._make_activations()
        profile = _build_pathway_profile(activations, "run1", "patient1")
        oxstr = [c for c in profile.pathway_contributions if c.pathway_id == "PW_OXSTR"][0]
        assert oxstr.activation_z == 0.0  # Not active → 0

    def test_none_returns_none(self):
        assert _build_pathway_profile(None, "run1", "p1") is None

    def test_empty_returns_none(self):
        assert _build_pathway_profile([], "run1", "p1") is None

    def test_full_report_with_pathways(self):
        activations = self._make_activations()
        report = assemble_report(
            run_id="run_pw",
            subject_ref="patient_pw",
            ranked_schedules=_make_ranked_schedules(1),
            active_pathways=activations,
        )
        assert report.pathway_profile is not None
        assert report.pathway_profile.dominant_pathway_id == "PW_INFLAM"


# ═══════════════════════════════════════════════════════════════
#  Test Subpopulation Summary Builder (F5)
# ═══════════════════════════════════════════════════════════════


class TestSubpopulationSummary:
    """Test _build_subpopulation_summary from duck-typed F5 result."""

    def _make_subpop_result(self):
        """Create a duck-typed object matching SubpopulationComparisonResult."""
        from types import SimpleNamespace
        diff = SimpleNamespace(
            intervention_id="int_a",
            context_a="breast_premenopause",
            context_b="breast_postmenopause",
            delta_C_diff_mean=0.3,
            delta_C_diff_ci_lower=0.1,
            delta_C_diff_ci_upper=0.5,
            practically_different=True,
        )
        risk_diff = SimpleNamespace(
            context_a="breast_premenopause",
            context_b="breast_postmenopause",
            risk_diff_pct=5.0,
            risk_diff_ci_lower=1.0,
            risk_diff_ci_upper=9.0,
        )
        return SimpleNamespace(
            n_contexts_compared=2,
            comparison_valid=True,
            validity_notes=["Sufficient sample for all contexts"],
            context_results={"breast_premenopause": {}, "breast_postmenopause": {}},
            pairwise_differentials=[diff],
            risk_differentials=[risk_diff],
            rank_concordance={"kendall_tau": 0.85},
        )

    def test_basic_subpop_summary(self):
        result = self._make_subpop_result()
        summary = _build_subpopulation_summary(result)
        assert summary is not None
        assert summary.n_contexts_compared == 2
        assert summary.comparison_valid is True
        assert len(summary.pairwise_differentials) == 1
        assert summary.pairwise_differentials[0].practically_different is True
        assert len(summary.risk_differentials) == 1
        assert summary.risk_differentials[0].risk_diff_pct == 5.0
        assert summary.rank_concordance == {"kendall_tau": 0.85}
        assert "breast_premenopause" in summary.context_labels

    def test_none_returns_none(self):
        assert _build_subpopulation_summary(None) is None

    def test_invalid_object_returns_none(self):
        """An object missing expected attrs should gracefully return None."""
        assert _build_subpopulation_summary("not_a_result") is None

    def test_full_report_with_subpop(self):
        result = self._make_subpop_result()
        report = assemble_report(
            run_id="run_subpop",
            subject_ref="patient_subpop",
            ranked_schedules=_make_ranked_schedules(1),
            subpopulation_result=result,
        )
        assert report.subpopulation_comparison is not None
        assert report.subpopulation_comparison.n_contexts_compared == 2


# ═══════════════════════════════════════════════════════════════
#  Per-Domain Severity/Percentile (§4.2 item 5)
# ═══════════════════════════════════════════════════════════════


class TestPerDomainSeverity:
    """Tests that per-domain severity_tier, percentile, and confidence_sd
    are correctly computed from CompositeState subdomain data."""

    def test_domain_percentile_computed(self):
        """Each domain should get Φ(−z)×100 as percentile."""
        from scipy import stats
        composite = _make_composite()
        score = _build_composite_score(composite, "run_dom", "patient_dom")
        for ds in score.domain_scores:
            expected = float(stats.norm.cdf(-ds.z_score) * 100.0)
            assert ds.percentile == pytest.approx(expected, abs=1e-6)

    def test_domain_severity_not_all_moderate(self):
        """Severity tiers should vary with z-score, not all be MODERATE."""
        composite = _make_composite()
        # Force domains with very different z-scores
        composite.subdomain_scores = {
            "attention": -2.5,  # severe
            "memory": 0.0,     # excellent (50th percentile)
            "executive": 1.5,  # low percentile → poor/severe
        }
        composite.subdomain_weights = {
            "attention": 1.0, "memory": 1.0, "executive": 1.0,
        }
        score = _build_composite_score(composite, "run_x", "patient_x")
        tiers = {ds.domain_id: ds.severity_tier for ds in score.domain_scores}
        # attention: z=-2.5 → percentile~99.4 → EXCELLENT
        # memory: z=0.0 → percentile=50 → MILD_CONCERN
        # executive: z=1.5 → percentile~6.68 → SEVERE
        assert tiers["attention"].value != tiers["executive"].value

    def test_domain_confidence_sd_from_weights(self):
        """confidence_sd should be 1/sqrt(weight) when weight > 0."""
        import math
        composite = _make_composite()
        composite.subdomain_weights = {"attention": 4.0, "memory": 0.25}
        composite.subdomain_scores = {"attention": -1.0, "memory": 0.5}
        score = _build_composite_score(composite, "run_sd", "patient_sd")
        sd_map = {ds.domain_id: ds.confidence_sd for ds in score.domain_scores}
        assert sd_map["attention"] == pytest.approx(0.5)
        assert sd_map["memory"] == pytest.approx(2.0)

    def test_classify_output_severity_boundaries(self):
        """Verify tier boundary classification."""
        from crci.shared import config
        from crci.shared.models.enums import SeverityTier
        assert _classify_output_severity(100.0) == SeverityTier.EXCELLENT
        assert _classify_output_severity(config.F1_TIER_EXCELLENT_MIN) == SeverityTier.EXCELLENT
        assert _classify_output_severity(config.F1_TIER_GOOD_MIN) == SeverityTier.GOOD
        assert _classify_output_severity(config.F1_TIER_MILD_MIN) == SeverityTier.MILD_CONCERN
        assert _classify_output_severity(config.F1_TIER_MODERATE_MIN) == SeverityTier.MODERATE
        assert _classify_output_severity(config.F1_TIER_POOR_MIN) == SeverityTier.POOR
        assert _classify_output_severity(0.0) == SeverityTier.SEVERE


# ═══════════════════════════════════════════════════════════════
#  Sensitivity Report (§4.2 item 4)
# ═══════════════════════════════════════════════════════════════


class TestSensitivityReport:
    """Tests for _build_sensitivity_report wiring D4c → report."""

    def _make_ranking_result(self):
        import numpy as np
        from crci.algorithm.chain_d_simulation.ranker import (
            InterventionRanking,
            RankingResult,
            SensitivityIndex,
            ClaimLevel,
        )
        from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus

        si1 = SensitivityIndex(
            edge_id="e1", source_node_id="n1", target_node_id="n2",
            elasticity=0.8, se_eff=0.3, discovery_score=0.24,
        )
        si2 = SensitivityIndex(
            edge_id="e2", source_node_id="n3", target_node_id="n4",
            elasticity=0.5, se_eff=0.2, discovery_score=0.10,
        )
        ir = InterventionRanking(
            action_id="a1", action_label="Action 1",
            safety_status=SafetyStatus.CLEAR,
            mss_cog=0.5, mss_burden=0.1,
            safe_a=0.47, safe_a_cri_lower=0.2, safe_a_cri_upper=0.7,
            rank_a=1,
            p_adhere=0.9, safe_b=0.4,
            safe_b_cri_lower=0.15, safe_b_cri_upper=0.65,
            rank_b=1, adherence_warning=False,
            dose_recommended=10.0, dose_conflict=False,
            dose_conflict_ratio=None, claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.array([0.1, 0.5, -0.1, 0.3, 0.6]),
        )
        return RankingResult(
            intervention_rankings={"a1": ir},
            bundle_rankings={},
            sensitivity_indices=[si1, si2],
            top_discovery_edges=[si1],
            dose_recommendations={},
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )

    def test_sensitivity_report_built(self):
        rr = self._make_ranking_result()
        report = _build_sensitivity_report(rr, "run_sens")
        assert report is not None
        assert report.n_edges_analyzed == 2
        assert len(report.sensitivity_indices) == 2
        assert len(report.top_discovery_edges) == 1
        assert report.top_discovery_edges[0].edge_id == "e1"
        assert report.top_discovery_edges[0].discovery_score == pytest.approx(0.24)

    def test_sensitivity_report_none_input(self):
        assert _build_sensitivity_report(None, "run_x") is None

    def test_sensitivity_report_empty_indices(self):
        rr = self._make_ranking_result()
        rr.sensitivity_indices = []
        rr.top_discovery_edges = []
        assert _build_sensitivity_report(rr, "run_x") is None

    def test_full_report_with_sensitivity(self):
        rr = self._make_ranking_result()
        report = assemble_report(
            run_id="run_sens_full",
            subject_ref="patient_sens",
            ranked_schedules=_make_ranked_schedules(1),
            ranking_result=rr,
        )
        assert report.sensitivity_report is not None
        assert report.sensitivity_report.n_edges_analyzed == 2


# ═══════════════════════════════════════════════════════════════
#  Per-Schedule Safety Detail (§4.2 item 6)
# ═══════════════════════════════════════════════════════════════


class TestScheduleSafetyDetail:
    """Tests that SAFE_A CrI, P(net_benefit), and safety_status
    flow from RankingResult through to SchedulePlan."""

    def test_safety_fields_populated(self):
        """When ranking_result is provided, SchedulePlan should have
        safe_a fields and safety_status."""
        import numpy as np
        from crci.algorithm.chain_d_simulation.ranker import (
            InterventionRanking, RankingResult, ClaimLevel,
        )
        from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus

        ir = InterventionRanking(
            action_id="a0", action_label="Action 0",
            safety_status=SafetyStatus.WARNING,
            mss_cog=0.5, mss_burden=0.1,
            safe_a=0.47, safe_a_cri_lower=0.2, safe_a_cri_upper=0.7,
            rank_a=1,
            p_adhere=0.9, safe_b=0.4,
            safe_b_cri_lower=0.15, safe_b_cri_upper=0.65,
            rank_b=1, adherence_warning=False,
            dose_recommended=10.0, dose_conflict=False,
            dose_conflict_ratio=None, claim_level=ClaimLevel.CAUSAL_SUPPORTED,
            per_draw_safe_a=np.array([0.1, 0.5, -0.1, 0.3, 0.6]),
        )
        rr = RankingResult(
            intervention_rankings={"a0": ir},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=1,
            n_bundles_ranked=0,
            n_blocked=0,
        )

        report = assemble_report(
            run_id="run_safety",
            subject_ref="patient_safety",
            ranked_schedules=_make_ranked_schedules(1),
            ranking_result=rr,
        )
        plan = report.primary_schedule
        # safe_a_score comes from Schedule.safe_a (set by _make_ranked_schedules)
        assert plan.safe_a_score is not None
        # CrI and safety_status come from the RankingResult lookup
        assert plan.safe_a_cri_lower == pytest.approx(0.2)
        assert plan.safe_a_cri_upper == pytest.approx(0.7)
        # 4 of 5 draws > 0 → P(net_benefit) = 0.8
        assert plan.p_net_benefit == pytest.approx(0.8)
        assert plan.safety_status == "WARNING"

    def test_safety_fields_none_without_ranking(self):
        """Without ranking_result, safety fields should be None."""
        report = assemble_report(
            run_id="run_no_safety",
            subject_ref="patient_x",
            ranked_schedules=_make_ranked_schedules(1),
        )
        plan = report.primary_schedule
        assert plan.safe_a_cri_lower is None
        assert plan.p_net_benefit is None
        assert plan.safety_status is None


# ═══════════════════════════════════════════════════════════════
#  B6.5 Pathway Evidence in PathwayProfile
# ═══════════════════════════════════════════════════════════════


class TestPathwayEvidenceEnrichment:
    """Tests that B6.5 evidence density/distinction scores
    flow into PathwayContribution when provided."""

    def _make_pathway_activations(self):
        from crci.algorithm.chain_c_posterior.modifier_application import PathwayActivation
        return [
            PathwayActivation(
                pathway_id="pw_oxidative",
                pathway_label="Oxidative Stress",
                activation_score=1.2,
                threshold=0.5,
                is_active=True,
                n_nodes=5,
                high_uncertainty=False,
            ),
            PathwayActivation(
                pathway_id="pw_inflammation",
                pathway_label="Neuroinflammation",
                activation_score=0.3,
                threshold=0.5,
                is_active=False,
                n_nodes=3,
                high_uncertainty=True,
            ),
        ]

    def _make_evidence_scores(self):
        from crci.algorithm.chain_b_evidence.pathway_evidence_scorer import PathwayEvidenceScore
        return {
            "pw_oxidative": PathwayEvidenceScore(
                pathway_id="pw_oxidative",
                evidence_density=2.5,
                distinction_score=0.85,
                n_edges_total=10,
                n_edges_with_evidence=8,
                edge_coverage=0.8,
                is_adequate=True,
            ),
            "pw_inflammation": PathwayEvidenceScore(
                pathway_id="pw_inflammation",
                evidence_density=0.5,
                distinction_score=0.4,
                n_edges_total=6,
                n_edges_with_evidence=2,
                edge_coverage=0.333,
                is_adequate=False,
            ),
        }

    def test_evidence_scores_merged(self):
        pws = self._make_pathway_activations()
        ev = self._make_evidence_scores()
        profile = _build_pathway_profile(pws, "run_pes", "patient_pes", ev)
        assert profile is not None
        by_id = {c.pathway_id: c for c in profile.pathway_contributions}
        ox = by_id["pw_oxidative"]
        assert ox.evidence_density == pytest.approx(2.5)
        assert ox.distinction_score == pytest.approx(0.85)
        assert ox.edge_coverage == pytest.approx(0.8)
        assert ox.is_adequate is True

        inf = by_id["pw_inflammation"]
        assert inf.evidence_density == pytest.approx(0.5)
        assert inf.is_adequate is False

    def test_without_evidence_scores(self):
        pws = self._make_pathway_activations()
        profile = _build_pathway_profile(pws, "run_no_pes", "patient_no_pes")
        assert profile is not None
        for c in profile.pathway_contributions:
            assert c.evidence_density is None
            assert c.distinction_score is None

    def test_full_report_with_evidence_scores(self):
        pws = self._make_pathway_activations()
        ev = self._make_evidence_scores()
        report = assemble_report(
            run_id="run_pes_full",
            subject_ref="patient_pes_full",
            ranked_schedules=_make_ranked_schedules(1),
            active_pathways=pws,
            pathway_evidence_scores=ev,
        )
        assert report.pathway_profile is not None
        ox = [c for c in report.pathway_profile.pathway_contributions
              if c.pathway_id == "pw_oxidative"][0]
        assert ox.evidence_density == pytest.approx(2.5)
