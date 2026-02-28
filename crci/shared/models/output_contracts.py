# VERIFIED: contracts match SYS_RUNTIME lines 61-66
# VERIFIED: contracts match SYS_PRESENTATION lines 87-200
# VERIFIED: imports — pydantic + shared.models.enums
# VERIFIED: downstream — written by ALG-F/RT-I, read by PRES
"""
Component: Layer 0 — Output Contracts
Spec: SYS_RUNTIME lines 61-66 (output tables)
      SYS_PRESENTATION lines 87-200 (PRES-PAT reads)
      IMPLEMENTATION_BLUEPRINT Part 6 (output schemas)
Purpose: Typed schemas for final system outputs.
Reads: Nothing (data structure definitions)
Writes: Nothing (instantiated by runtime/presentation modules)
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import (
    SeverityTier,
    StabilityClass,
    ReportOutputMode,
)


# ═══════════════════════════════════════════════════════════════
#  COMPOSITE SCORE
# ═══════════════════════════════════════════════════════════════


class DomainScore(BaseModel):
    """Single cognitive domain score."""

    domain_id: str
    domain_label: str
    z_score: float
    severity_tier: SeverityTier
    percentile: float | None = None
    contributing_nodes: list[str] = Field(default_factory=list)
    confidence_sd: float | None = None


class CompositeScore(BaseModel):
    """CRCI Composite Score — severity-weighted mean across subdomains.

    Population-normed percentile.
    """

    run_id: str
    subject_ref: str
    composite_z: float
    composite_percentile: float | None = None
    overall_severity: SeverityTier
    domain_scores: list[DomainScore] = Field(default_factory=list)
    population_norm_used: str | None = None
    calibration_mode: str = "index_mode"

    # Heterogeneity diagnostics (from F1 — Cochran's Q, Higgins I²)
    cochrans_Q: float | None = None
    I_squared: float | None = None  # [0, 100] — proportion of real heterogeneity
    random_effects_applied: bool = False


# ═══════════════════════════════════════════════════════════════
#  SCHEDULE PLAN (presentation-ready)
# ═══════════════════════════════════════════════════════════════


class ScheduleAction(BaseModel):
    """Single action within a schedule plan."""

    action_id: str
    action_label: str
    action_class: str
    dose_value: float
    dose_unit: str
    timing_summary: str
    frequency: str
    duration_days: int
    expected_benefit_z: float | None = None
    rationale: str | None = None


class SynergyMetrics(BaseModel):
    """Synergy diagnostics for a bundle schedule.

    Surfaces JPO, CCS, and γ from D3 synergy analysis so the
    presentation layer can explain intervention interactions.
    """

    bundle_id: str
    member_ids: list[str] = Field(default_factory=list)
    mean_delta_C: float = 0.0  # composite cognitive effect of the bundle
    interaction_completeness: float = 1.0  # fraction of interaction terms modeled
    pairwise: list[dict] = Field(
        default_factory=list,
        description="[{action_a, action_b, jpo, ccs, gamma_empirical}, ...]",
    )


class SchedulePlan(BaseModel):
    """Complete schedule plan for presentation."""

    schedule_id: str
    run_id: str
    plan_rank: int
    plan_type: str  # primary, alternative
    actions: list[ScheduleAction] = Field(default_factory=list)
    utility_score: float = 0.0
    stability_class: StabilityClass = StabilityClass.STABLE
    p_rank_1: float = 0.0
    expected_outcomes: dict[str, float] = Field(default_factory=dict)
    risk_summary: dict[str, float] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)
    constraints_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # REVIEW: CrI values originate from Chain D MC draws. Interval calibration
    # (actual coverage ≈ 95%) should be verified via simulation before clinical
    # deployment. This passthrough is correct but the upstream intervals may need
    # calibration tuning.
    cri_95_lower: float | None = None
    cri_95_upper: float | None = None
    # SAFE_A detail (from D4 — efficacy-only score)
    safe_a_score: float | None = None
    safe_a_cri_lower: float | None = None
    safe_a_cri_upper: float | None = None
    p_net_benefit: float | None = None  # P(SAFE_A > 0) from per_draw_safe_a
    safety_status: str | None = None    # CLEARED, CAUTION, BLOCKED
    # D3 synergy diagnostics (populated for bundle schedules)
    synergy: SynergyMetrics | None = None


# ═══════════════════════════════════════════════════════════════
#  PATHWAY PROFILE
# ═══════════════════════════════════════════════════════════════


class PathwayContribution(BaseModel):
    """Single pathway's contribution to a node."""

    pathway_id: str
    pathway_label: str
    contribution_fraction: float
    activation_z: float = 0.0  # signed pathway z-score (direction matters)
    key_edges: list[str] = Field(default_factory=list)
    evidence_quality: str | None = None
    # B6.5 pathway evidence metrics (if available)
    evidence_density: float | None = None   # ED(P): quality-weighted studies/edge
    distinction_score: float | None = None  # DS(P): 1 − max cosine similarity
    edge_coverage: float | None = None      # fraction of edges with ≥1 study
    is_adequate: bool | None = None         # ED ≥ threshold


class PathwayProfile(BaseModel):
    """Per-patient pathway activation profile."""

    run_id: str
    subject_ref: str
    pathway_contributions: list[PathwayContribution] = Field(default_factory=list)
    dominant_pathway_id: str | None = None
    coverage_fraction: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  TEMPORAL TRAJECTORY
# ═══════════════════════════════════════════════════════════════


class TrajectoryPoint(BaseModel):
    """Single time point in a trajectory."""

    day: int
    z_mean: float
    z_sd: float
    z_p10: float
    z_p90: float


class NodeTrajectory(BaseModel):
    """Trajectory for a single node under a scenario."""

    node_id: str
    node_label: str
    points: list[TrajectoryPoint] = Field(default_factory=list)
    final_delta_z: float | None = None


class TemporalTrajectory(BaseModel):
    """Projected temporal trajectory over simulation horizon."""

    scenario_id: str
    scenario_label: str
    horizon_days: int
    time_step_unit: str = "day"
    node_trajectories: list[NodeTrajectory] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  VARIANCE DECOMPOSITION
# ═══════════════════════════════════════════════════════════════


class VarianceComponent(BaseModel):
    """Single variance source."""

    source: str  # literature, measurement, structural, proxy, missing
    fraction: float
    description: str | None = None


class VarianceDecomposition(BaseModel):
    """5-source variance decomposition (§2.20.1)."""

    run_id: str
    components: list[VarianceComponent] = Field(default_factory=list)
    total_variance: float = 0.0
    dominant_source: str | None = None
    per_edge_contributions: dict[str, float] = Field(
        default_factory=dict,
        description="edge_id → variance contribution (absolute). From F3 per_edge_variance_contrib.",
    )
    per_study_contributions: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description=(
            "R4: Per-study variance decomposition within each edge. "
            "{edge_id: {ler_id: variance_share}}. Weight-proportional "
            "allocation of edge literature variance to individual studies."
        ),
    )


# ═══════════════════════════════════════════════════════════════
#  EVIDENCE GAP
# ═══════════════════════════════════════════════════════════════


class EvidenceGapItem(BaseModel):
    """Single evidence gap."""

    edge_param_id: str
    edge_label: str
    gap_type: str  # missing_evidence, low_k, high_heterogeneity, low_grade
    severity: str  # high, medium, low
    description: str
    discovery_score: float | None = None  # |elasticity| × SE_eff
    evsi: float | None = None  # Expected Value of Sample Information


class EvidenceGapReport(BaseModel):
    """Prioritized evidence gap report (§4.5)."""

    run_id: str
    gaps: list[EvidenceGapItem] = Field(default_factory=list)
    top_acquisition_targets: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  SENSITIVITY REPORT (D4c — decision sensitivity analysis)
# ═══════════════════════════════════════════════════════════════


class SensitivityIndexItem(BaseModel):
    """Single edge sensitivity index from D4c."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    elasticity: float       # Corr(β_e, ΔC_top)
    se_eff: float           # effective SE
    discovery_score: float  # |elasticity| × SE_eff


class SensitivityReport(BaseModel):
    """Sensitivity analysis report — which edges most influence the ranking.

    Built from D4c sensitivity indices (Sobol-style elasticities).
    """

    run_id: str
    sensitivity_indices: list[SensitivityIndexItem] = Field(default_factory=list)
    top_discovery_edges: list[SensitivityIndexItem] = Field(default_factory=list)
    n_edges_analyzed: int = 0


# ═══════════════════════════════════════════════════════════════
#  DECISION TRACE (presentation-ready)
# ═══════════════════════════════════════════════════════════════


class StudyContribution(BaseModel):
    """Per-study weight attribution for a single edge (R2 provenance).

    Maps each contributing study to its IVW weight percentage,
    enabling drill-down from edge → study → paper.
    """

    ler_id: str
    study_id: str
    paper_ref: str | None = None
    weight_pct: float  # normalised weight as percentage (0–100)
    beta: float
    se: float


class EdgeInfluence(BaseModel):
    """Per-edge variance contribution to the recommendation (R3 provenance).

    Derived from D4c sensitivity analysis: elasticity = Corr(β_e, ΔC_top).
    variance_contribution_pct = elasticity² / Σ(elasticity²) × 100, giving
    the fraction of recommendation-score variance attributable to this edge.
    """

    edge_id: str
    elasticity: float            # Corr(β_e^(m), ΔC_top^(m))
    discovery_score: float       # |elasticity| × SE_eff
    variance_contribution_pct: float  # R² fraction as percentage (0–100)


class DecisionTraceEntry(BaseModel):
    """Single decision in the audit trail."""

    step: str
    description: str
    inputs: dict[str, str] = Field(default_factory=dict)
    outcome: str
    confidence: float | None = None


class DecisionTrace(BaseModel):
    """Full decision audit trail for transparency.

    edge_study_map: edge_id → list of StudyContribution (R2).
    edge_influences: edge_id → EdgeInfluence (R3).
    When populated, enables provenance drill-down from
    critical edges to contributing studies, papers, and
    per-edge variance attribution.
    """

    run_id: str
    entries: list[DecisionTraceEntry] = Field(default_factory=list)
    decision_critical_edges: list[str] = Field(default_factory=list)
    edge_study_map: dict[str, list[StudyContribution]] = Field(default_factory=dict)
    edge_influences: dict[str, EdgeInfluence] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  CLINICAL RISK PROFILE (§4.1 — CRCI Risk Percentage)
# ═══════════════════════════════════════════════════════════════


class DomainRiskBreakdown(BaseModel):
    """Per-domain risk attribution for the CRCI Risk Percentage."""

    domain_id: str
    domain_label: str
    node_ids: list[str] = Field(default_factory=list)
    marginal_risk_pct: float
    trigger_share_pct: float
    ivw_weight_pct: float
    mean_z: float
    sd_z: float
    z_5th: float
    z_95th: float
    is_directly_observed: bool = False
    n_observations: int = 0


class ClinicalRiskProfile(BaseModel):
    """CRCI Risk Percentage output — probability of meeting ICCTF criteria.

    Computed by Chain F4 (risk_estimator.py) from Monte Carlo draws.
    """

    risk_pct: float
    risk_lower_pct: float
    risk_upper_pct: float
    risk_range_text: str = ""
    risk_tier: str = "UNKNOWN"
    interval_method: str = "jeffreys"
    interval_level: float = 0.90
    mc_se: float = 0.0
    n_draws_used: int = 0
    coverage_fraction: float = 0.0
    low_coverage_warning: bool = False
    domain_breakdown: list[DomainRiskBreakdown] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  SUBPOPULATION COMPARISON SUMMARY (F5)
# ═══════════════════════════════════════════════════════════════


class DifferentialEffectSummary(BaseModel):
    """Pairwise intervention effect comparison across two contexts."""

    intervention_id: str
    context_a: str
    context_b: str
    delta_C_diff_mean: float
    delta_C_diff_ci_lower: float
    delta_C_diff_ci_upper: float
    practically_different: bool = False


class RiskDifferentialSummary(BaseModel):
    """Pairwise CRCI risk comparison across two contexts."""

    context_a: str
    context_b: str
    risk_diff_pct: float
    risk_diff_ci_lower: float
    risk_diff_ci_upper: float


class SubpopulationComparisonSummary(BaseModel):
    """Presentation-ready summary of F5 subpopulation comparison.

    Mapped from SubpopulationComparisonResult (algorithm internal type)
    by report_assembler.py.
    """

    n_contexts_compared: int = 0
    comparison_valid: bool = False
    validity_notes: list[str] = Field(default_factory=list)
    context_labels: list[str] = Field(default_factory=list)
    pairwise_differentials: list[DifferentialEffectSummary] = Field(default_factory=list)
    risk_differentials: list[RiskDifferentialSummary] = Field(default_factory=list)
    rank_concordance: dict[str, float] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  EXTRACTION QUALITY SUMMARY
# ═══════════════════════════════════════════════════════════════


class ExtractionQualitySummary(BaseModel):
    """Aggregated extraction quality metrics across all studies in a session.

    Computed by check_paper_completeness() in completeness_checker.py,
    aggregated across all studies used in the run, and threaded through
    to the presentation layer for quality disclosure.
    """

    study_count: int = 0
    overall_completeness: float = 0.0  # Mean completeness_score across studies [0.0–1.0]
    total_defaults_fired: dict[str, int] = Field(
        default_factory=dict,
        description="Aggregate defaults per layer: {'L1': 0, 'L4': 2, 'L6': 5, ...}",
    )
    missing_families_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Family code → count of studies missing it: {'F4': 3}",
    )
    blocking_issue_count: int = 0
    quality_caveats: list[str] = Field(
        default_factory=list,
        description="Human-readable quality warnings for presentation layer",
    )


# ═══════════════════════════════════════════════════════════════
#  RECOMMENDATION REPORT (top-level output)
# ═══════════════════════════════════════════════════════════════


class RecommendationReport(BaseModel):
    """Top-level output contract — everything the presentation layer needs.

    This is the single object that flows from Runtime to Presentation.
    """

    run_id: str
    subject_ref: str
    output_mode: ReportOutputMode

    # Core outputs
    composite_score: CompositeScore
    primary_schedule: SchedulePlan
    alternative_schedules: list[SchedulePlan] = Field(default_factory=list)

    # Supporting outputs
    pathway_profile: PathwayProfile | None = None
    trajectories: list[TemporalTrajectory] = Field(default_factory=list)
    variance_decomposition: VarianceDecomposition | None = None
    evidence_gaps: EvidenceGapReport | None = None
    decision_trace: DecisionTrace | None = None
    clinical_risk: ClinicalRiskProfile | None = None
    extraction_quality: ExtractionQualitySummary | None = None
    subpopulation_comparison: SubpopulationComparisonSummary | None = None
    sensitivity_report: SensitivityReport | None = None

    # Safety & warnings
    safety_flags: list[str] = Field(default_factory=list)
    escalation_triggered: bool = False
    run_warnings: list[str] = Field(default_factory=list)

    # Metadata
    engine_version: str | None = None
    timestamp: str | None = None
