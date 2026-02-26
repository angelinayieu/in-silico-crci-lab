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
#  DECISION TRACE (presentation-ready)
# ═══════════════════════════════════════════════════════════════


class DecisionTraceEntry(BaseModel):
    """Single decision in the audit trail."""

    step: str
    description: str
    inputs: dict[str, str] = Field(default_factory=dict)
    outcome: str
    confidence: float | None = None


class DecisionTrace(BaseModel):
    """Full decision audit trail for transparency."""

    run_id: str
    entries: list[DecisionTraceEntry] = Field(default_factory=list)
    decision_critical_edges: list[str] = Field(default_factory=list)


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

    # Safety & warnings
    safety_flags: list[str] = Field(default_factory=list)
    escalation_triggered: bool = False
    run_warnings: list[str] = Field(default_factory=list)

    # Metadata
    engine_version: str | None = None
    timestamp: str | None = None
