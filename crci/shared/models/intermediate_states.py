# VERIFIED: types match SYS_EX lines 330-370, 460-490, 1135-1180
# VERIFIED: types match SYS_ALG lines 1075-1200, 1630-1680, 2100-2160
# VERIFIED: imports — pydantic + shared.models.enums
# VERIFIED: downstream — passed between subsystems within chains
"""
Component: Layer 0 — Intermediate Pipeline States
Spec: SYS_EXTRACTION lines 330-370 (PaperMap, SectionSegment, SpanLabel)
      SYS_EXTRACTION lines 460-490 (RawAnnotationEmission, ReconciliationDec.)
      SYS_EXTRACTION lines 1135-1180 (GroupedEvidence, ResolvedEvidence)
      SYS_ALGORITHM lines 1075-1200 (PooledEdge, PriorSpec)
      SYS_ALGORITHM lines 1630-1680 (PreparedObservation, ModifiedState)
      SYS_ALGORITHM lines 2100-2160 (MCDraw, PerDrawEffect, SimResults)
Purpose: Pydantic models for ALL intermediate pipeline states.
         These are in-memory only — not persisted to DB.
Reads: Nothing (data structure definitions)
Writes: Nothing (instantiated by pipeline modules)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AdjudicationStatus,
    AnnotationCategory,
    AnnotationMaturity,
    BiasRisk,
    BoundType,
    ConversionBiasRisk,
    ConversionGateResult,
    EffectScale,
    ExtractionMode,
    FailureMode,
    HarmonizationStatusInMem,
    OverlapDecision,
    ParseStatus,
    PlausibilityStatus,
    PriorSource,
    PriorTypePaper,
    ProxyValidity,
    SEDerivationLevel,
    SEQualityTag,
    SESource,
    SafeMode,
    StabilityClass,
    SufficiencyRecommendation,
    TargetScale,
    TriageDecision,
    TriageTier,
)


# ═══════════════════════════════════════════════════════════════
#  EX-P0: TRIAGE
# ═══════════════════════════════════════════════════════════════


class TriageResult(BaseModel):
    """Output of P0 triage: accept/reject decision + extraction mode."""

    paper_id: str
    decision: TriageDecision
    relevance_score: float = Field(ge=0.0, le=1.0)
    extraction_mode: ExtractionMode | None = None
    paper_subtype: str | None = None
    rejection_reason: str | None = None


# ═══════════════════════════════════════════════════════════════
#  EX-P1: EXTRACTION — Canonical Reader outputs
# ═══════════════════════════════════════════════════════════════


class SectionSegment(BaseModel):
    """A labeled section of the paper."""

    section_type: str  # abstract, methods, results, discussion, etc.
    heading: str | None = None
    char_start: int
    char_end: int
    text: str


class TableEntry(BaseModel):
    """A detected table in the paper."""

    table_id: str
    caption: str | None = None
    section_type: str | None = None
    char_start: int
    char_end: int
    raw_text: str


class FigureEntry(BaseModel):
    """A detected figure in the paper."""

    figure_id: str
    caption: str | None = None
    section_type: str | None = None


class CandidateSpan(BaseModel):
    """A detected numeric claim or statistical result."""

    span_id: str
    char_start: int
    char_end: int
    text: str
    section_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class PaperMap(BaseModel):
    """CR output: structured paper representation shared by all agents.

    This is the key v2 efficiency improvement — one read, many agents.
    SYS_EX lines 330-370.

    v2.0 (MS §5.2, INV-03): PaperMap is immutable after Canonical Reader
    completes. Enforced via frozen=True. Uses tuples instead of lists
    to prevent mutation of nested collections.
    """

    model_config = ConfigDict(frozen=True)

    paper_id: str
    title: str | None = None
    full_text: str
    sections: tuple[SectionSegment, ...] = ()
    tables: tuple[TableEntry, ...] = ()
    figures: tuple[FigureEntry, ...] = ()
    candidate_spans: tuple[CandidateSpan, ...] = ()
    n_total: int | None = None
    study_design: str | None = None
    arms: tuple[str, ...] = ()


# ═══════════════════════════════════════════════════════════════
#  EX-P1: EXTRACTION — Agent outputs
# ═══════════════════════════════════════════════════════════════


class SpanLabel(BaseModel):
    """AG5 output: labeled statistical span.

    SYS_EX lines 312-330 (40 label types).
    """

    span_id: str
    label_type: str  # One of 40 span_label_type values
    value: str | None = None
    numeric_value: float | None = None
    char_start: int
    char_end: int
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_section: str | None = None
    source_table_id: str | None = None
    grouping_id: str | None = None  # Links related stats (β + CI + p + N)
    arm_assignment: str | None = None  # Which study arm (e.g., "testosterone", "placebo")


class GroundedSpan(BaseModel):
    """SpanLabel after ConceptEngine ontology grounding.

    Adds edge_relation_id resolved from edge_ontology_v1 / edge definitions.
    SYS_EX §515-520 (EX-P1-CE), Master Spec v2.0 §5.7.
    """

    span: SpanLabel
    edge_relation_id: str | None = None  # None = UNRESOLVED
    grounding_confidence: float = 0.0
    grounding_mode: str = "unresolved"  # exact_match | alias | fuzzy | unresolved


class RawAnnotationEmission(BaseModel):
    """AG10 output: extracted annotation from Discussion/Limitations.

    SYS_EX lines 460-490.
    """

    annotation_id: str
    category: AnnotationCategory
    content: str
    evidence_strength: str | None = None
    extraction_snippet: str | None = None
    source_span_id: str | None = None


class ReconciliationDecision(BaseModel):
    """Output of AG9/reconciliation: conflict resolution decision."""

    entity_pair: tuple[str, str]
    decision: OverlapDecision
    kept_entity_id: str | None = None
    reason: str


# ═══════════════════════════════════════════════════════════════
#  EX-TB: TRUST BOUNDARY
# ═══════════════════════════════════════════════════════════════


class ParsedNumeric(BaseModel):
    """Trust boundary parser output.

    SYS_EX Trust Boundary spec.
    """

    span_id: str
    value_type: str  # stat_type (37 values)
    parse_status: ParseStatus
    raw_text: str
    parsed_value: float | None = None
    parsed_lower: float | None = None
    parsed_upper: float | None = None
    unit: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class TypedNumericValue(BaseModel):
    """Typed numeric value with bound information.

    SYS_EX Trust Boundary — after parsing and group assembly.
    """

    value: float
    bound_type: BoundType = BoundType.EXACT
    original_text: str
    label_type: str | None = None  # Preserves what the primary value IS (e.g., EFFECT_SIZE, OR)
    se: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None
    n: int | None = None
    edge_relation_id: str | None = None  # From ConceptEngine grounding
    grouping_id: str | None = None  # Trace back to original span group


# ═══════════════════════════════════════════════════════════════
#  EX-P2: HARMONIZATION (in-memory)
# ═══════════════════════════════════════════════════════════════


class ValidatedNumeric(BaseModel):
    """After plausibility bounds check (S1)."""

    span_id: str
    value: TypedNumericValue
    value_type: str  # label_type from ParsedNumeric (e.g., EFFECT_SIZE, SAMPLE_SIZE)
    plausibility_status: PlausibilityStatus
    plausibility_note: str | None = None


class RoutedNumeric(BaseModel):
    """After scale routing (CG1-CG4 gate)."""

    span_id: str
    value: TypedNumericValue
    target_scale: TargetScale
    conversion_gate_result: ConversionGateResult
    blocked_reason: str | None = None


class ScaledNumeric(BaseModel):
    """After scale conversion with SE.

    v2.0: Includes SE derivation level tracking from the 6-level cascade
    (CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4) and conversion
    provenance logging (Module 1 R4).
    """

    span_id: str
    beta: float
    se: float | None = None
    n_effect: int | None = None
    se_source: SESource
    scale: EffectScale
    direction_aligned: bool = False
    # Edge provenance — carried from TypedNumericValue through P2 chain
    edge_relation_id: str | None = None
    label_type: str | None = None
    # v2.0: SE derivation cascade tracking
    se_derivation_level: SEDerivationLevel | None = None
    se_quality_tag: SEQualityTag | None = None
    se_inflation_applied: float = 1.0
    # v2.0: Conversion provenance (Module 1 R4)
    conversion_formula: str | None = None
    conversion_bias_risk: ConversionBiasRisk | None = None
    # v2.0: Family-specific freshness (Module 5)
    parameter_family: str | None = None
    fields_present: list[str] = Field(default_factory=list)
    fields_missing: list[str] = Field(default_factory=list)
    # CI fields carried through for P3 CI→SE defense-in-depth fallback
    ci_lower: float | None = None
    ci_upper: float | None = None


class HarmonizedClaim(BaseModel):
    """Final harmonized evidence claim per study-edge pair."""

    ler_id: str
    edge_relation_id: str
    profile_id: str
    study_id: str
    harmonized_beta: float
    harmonized_se: float | None = None
    harmonized_scale: EffectScale
    harmonization_status: HarmonizationStatusInMem
    quality_rating: str = "moderate"
    se_source: SESource = SESource.SE_DIRECT
    n_effect: int | None = None
    # v2.0: Family-specific freshness (Module 5)
    parameter_family: str | None = None
    # Canonical pooling scale — P4 must only pool records with matching scale
    canonical_scale: str | None = None
    # CI fields carried from upstream for P3 CI→SE fallback
    ci_lower: float | None = None
    ci_upper: float | None = None
    # ── P3 layer-input fields (Slice 8: FIX-4) ──
    # These fields carry study metadata for P3's 7-layer SE calibration,
    # eliminating unsafe getattr fallbacks in P3 layers and P4 shared-control.
    study_design: str = "unclassified"
    n_total: int | None = None
    n_treatment: int | None = None
    n_control: int | None = None
    cancer_validation_status: str = "general_population"
    grade_level: str = "MODERATE"
    pub_year: int | None = None
    days_since_measurement: float = 0.0
    is_trait: bool = False
    # P4 shared-control fields
    shared_control_flag: bool = False
    shared_control_study_id: str | None = None
    endpoint_vs_change: str = "UNCLEAR"
    is_cancer_matched: bool = False
    is_superseded: bool = False
    # P4 verification / meta-analysis source tracking
    se_derivation_level: str | None = None
    meta_source_flag: str | None = None
    parent_meta_study_id: str | None = None
    # R4.1: Published heterogeneity stats from MA papers (JSON dict with I2, tau2, etc.)
    heterogeneity_json: dict | None = None
    # Provenance tracking: records where each field value came from
    layer_fields_provenance: dict[str, str] = Field(default_factory=dict)
    # Computed flag: True when key P3 fields have non-default values
    is_complete_for_p3: bool = False


def compute_is_complete_for_p3(
    study_design: str = "unclassified",
    cancer_validation_status: str = "general_population",
    grade_level: str = "MODERATE",
    pub_year: int | None = None,
) -> bool:
    """Check if key P3 fields have non-default values.

    Returns True only when all four critical fields have been populated
    with study-specific values (not defaults).
    """
    if study_design == "unclassified":
        return False
    if cancer_validation_status == "general_population":
        return False
    if grade_level == "MODERATE":
        return False
    if pub_year is None:
        return False
    return True


# ═══════════════════════════════════════════════════════════════
#  EX-P3: HETEROGENEITY (7-layer SE system)
# ═══════════════════════════════════════════════════════════════


class LayeredSEResult(BaseModel):
    """Output of the 7-layer SE inflation system.

    Formulas P3-1 through P3-8.
    """

    ler_id: str
    se_base: float
    layer_multipliers: dict[str, float] = Field(default_factory=dict)
    se_effective: float
    layers_applied: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  EX-P3.5: DOUBLE COUNTING / GROUPING
# ═══════════════════════════════════════════════════════════════


class GroupedEvidence(BaseModel):
    """Evidence grouped by edge after overlap resolution.

    SYS_EX lines 1135-1180.
    """

    edge_relation_id: str
    claims: list[HarmonizedClaim]
    overlap_decisions: list[ReconciliationDecision] = Field(default_factory=list)
    k: int = 0  # number of independent claims


class ResolvedEvidence(BaseModel):
    """Evidence after double-counting resolution.

    Ready for meta-analysis.
    """

    edge_relation_id: str
    claims: list[HarmonizedClaim]
    k: int = 0
    total_n: int = 0
    resolution_notes: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  EX-P4: AGGREGATION (meta-analysis)
# ═══════════════════════════════════════════════════════════════


class StudyWeight(BaseModel):
    """Per-study weight attribution for IVW meta-analysis provenance.

    Records which study contributed what weight to the pooled estimate,
    enabling full audit trail from edge → individual study → paper.

    Weight semantics depend on aggregation method:
      - IVW_FIXED:    w_i = 1/SE²_i (unnormalized)
      - IVW_RANDOM:   w_i = 1/(SE²_i + τ²) (unnormalized)
      - SINGLE_BEST:  1.0 for selected study, 0.0 for others
      - DIRECT (k=1): 1.0 for the single study
    """

    ler_id: str
    study_id: str
    weight: float          # Unnormalized IVW weight
    weight_normalized: float = 0.0  # w_i / Σ(w_j) — fraction of pooled estimate
    beta: float = 0.0      # Individual study effect size
    se: float = 0.0        # Individual study standard error


class PooledEstimate(BaseModel):
    """Output of IVW meta-analysis.

    Formula P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
    Formula P4-2: τ² (DerSimonian-Laird)
    Formula P4-3: I²
    """

    edge_relation_id: str
    beta_pooled: float
    se_pooled: float
    tau_squared: float = 0.0
    i_squared: float = 0.0
    k: int = 0
    total_n: int = 0
    aggregation_method: str = "IVW_random"
    individual_weights: list[float] = Field(default_factory=list)
    # R1 provenance: per-study identified weights (supersedes individual_weights)
    study_weights: list[StudyWeight] = Field(default_factory=list)


class PriorSpec(BaseModel):
    """Prior specification for Bayesian update.

    SYS_ALG lines 1170-1190.
    """

    edge_relation_id: str | None = None
    node_id: str | None = None
    prior_source: PriorSource
    prior_type: PriorTypePaper | None = None
    mean: float = 0.0
    sd: float = 1.0
    dist_family: str = "normal"
    provenance: str | None = None


class CompiledEdge(BaseModel):
    """Fully compiled edge ready for runtime.

    Combines pooled estimate + prior + publication bias adjustment.
    """

    edge_param_id: str
    edge_relation_id: str
    beta_mean: float
    beta_se: float
    effect_scale: EffectScale
    prior_source: PriorSource
    prior_type: PriorTypePaper | None = None
    aggregation_method: str
    k: int
    total_n: int
    i_squared: float = 0.0
    tau_squared: float = 0.0
    pub_bias_risk: BiasRisk = BiasRisk.LOW
    se_inflation_pub_bias: float = 1.0
    coherence_flag: TriageTier | None = None
    se_inflation_coherence: float = 1.0


# ═══════════════════════════════════════════════════════════════
#  EX-P5: SUFFICIENCY & COHERENCE
# ═══════════════════════════════════════════════════════════════


class SufficiencyReport(BaseModel):
    """Output of sufficiency check.

    SYS_EX P5 — evidence base verdict.
    """

    recommendation: SufficiencyRecommendation
    total_edges_compiled: int
    edges_sufficient: int
    edges_marginal: int
    edges_insufficient: int
    coverage_by_pathway: dict[str, float] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ChainValidationResult(BaseModel):
    """Single pathway chain-vs-direct comparison.

    §2.13 chain-vs-direct triage.
    """

    pathway_id: str
    chain_length: int
    beta_chain: float
    se_chain: float
    beta_direct: float | None = None
    se_direct: float | None = None
    z_statistic: float | None = None
    triage_tier: TriageTier
    failure_mode: FailureMode = FailureMode.NONE
    se_inflation_applied: float = 1.0


# ═══════════════════════════════════════════════════════════════
#  ALG-A: GRAPH ASSEMBLY & INTAKE
# ═══════════════════════════════════════════════════════════════


class CalibratedRecord(BaseModel):
    """Calibrated observation ready for Bayesian update.

    SYS_ALG Chain A output.
    """

    node_id: str
    feature_id: str | None = None
    z_value: float
    observation_noise_sd: float
    proxy_validity: ProxyValidity = ProxyValidity.DIRECT
    timestamp: str | None = None
    source_type: str | None = None  # instrument, measure, derived_feature


class StandardizedFeatureVector(BaseModel):
    """Complete patient feature vector in z-space."""

    subject_ref: str
    timestamp: str
    features: dict[str, CalibratedRecord] = Field(default_factory=dict)
    coverage_fraction: float = 0.0
    missing_node_ids: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  ALG-C: BAYESIAN UPDATE
# ═══════════════════════════════════════════════════════════════


class NodeBelief(BaseModel):
    """Posterior belief for a single node."""

    node_id: str
    mean: float
    sd: float
    prior_mean: float
    prior_sd: float
    n_observations: int = 0
    conflict_score: float = 0.0


class PosteriorState(BaseModel):
    """Full posterior state after Bayesian update.

    SYS_ALG Chain C output.
    """

    state_id: str
    run_id: str
    subject_ref: str
    state_time: str
    beliefs: dict[str, NodeBelief] = Field(default_factory=dict)
    obs_used_count: int = 0
    conflict_inflation_applied: bool = False
    missingness_inflation_applied: bool = False
    sigma_floor_applied: bool = False


# ═══════════════════════════════════════════════════════════════
#  ALG-D: SCENARIO CONSTRUCTION + ALG-E: MODIFIER RESOLUTION
# ═══════════════════════════════════════════════════════════════


class PreparedObservation(BaseModel):
    """Observation prepared for Bayesian update (one per instrument).

    SYS_ALG lines 1665-1720 (PreparedObservation state after C2).
    Produced by: observation_mapper.py (C2)
    Consumed by: bayesian_update.py (C3)
    """

    instrument_id: str
    node_i: int = Field(ge=0, le=62, description="Target latent node index")
    y_k: float = Field(description="Observed measurement value")
    a_k: float = Field(description="Instrument intercept (offset)")
    b_k: float = Field(description="Instrument loading (slope)")
    sigma_sq_y_k: float = Field(gt=0, description="Total observation noise variance")
    cancer_SE_mult: float = Field(ge=1.0, le=1.5, description="Cancer validation SE mult")
    w_temporal: float = Field(gt=0, le=1.0, description="Temporal decay weight")
    t_days: float = Field(ge=0, description="Days since assessment")
    tier: str = Field(description="Observation priority tier (TIER_0, TIER_1, TIER_2)")


class ModifiedEdge(BaseModel):
    """Edge with modifiers applied for a specific patient."""

    edge_param_id: str
    beta_original: float
    beta_modified: float
    se_modified: float
    modifiers_applied: list[str] = Field(default_factory=list)
    cumulative_multiplier: float = 1.0


class ModifiedState(BaseModel):
    """State with all modifiers resolved.

    SYS_ALG lines 1630-1680.
    """

    run_id: str
    subject_ref: str
    modified_edges: dict[str, ModifiedEdge] = Field(default_factory=dict)
    modifier_trace: list[dict[str, Any]] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  ALG-F: MC SIMULATION
# ═══════════════════════════════════════════════════════════════


class MCDraw(BaseModel):
    """Single Monte Carlo draw.

    SYS_ALG lines 2100-2160.
    """

    draw_index: int
    sampled_betas: dict[str, float] = Field(default_factory=dict)
    seed_offset: int = 0


class PerDrawEffect(BaseModel):
    """Per-node effect from a single MC draw."""

    draw_index: int
    node_id: str
    delta_z: float
    contributions: dict[str, float] = Field(default_factory=dict)


class NodeEffectSummary(BaseModel):
    """Summary statistics for one node across all MC draws."""

    node_id: str
    mean_delta_z: float
    sd_delta_z: float
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    p_worsening: float = 0.0  # P(delta_z > 0 for higher_worse)


class SimulationResults(BaseModel):
    """Aggregated simulation results across all MC draws.

    SYS_ALG lines 2100-2160.
    """

    scenario_id: str
    n_draws: int
    seed_used: int
    node_summaries: dict[str, NodeEffectSummary] = Field(default_factory=dict)
    edges_used: list[str] = Field(default_factory=list)
    bridges_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  RUNTIME: OPTIMIZATION & SCORING
# ═══════════════════════════════════════════════════════════════


class SAFEScore(BaseModel):
    """SAFE score for a candidate schedule.

    §2.16.3 — Mode A: E[Δz]/uncertainty. Mode B: SAFE·burden·adherence.
    """

    schedule_id: str
    mode: SafeMode
    score: float
    expected_benefit: float
    uncertainty: float
    burden_penalty: float = 0.0
    adherence_factor: float = 1.0
    stability_class: StabilityClass = StabilityClass.STABLE
    p_rank_1: float = 0.0
    bootstrap_ci_low: float | None = None
    bootstrap_ci_high: float | None = None


class RankedSchedule(BaseModel):
    """A ranked schedule with scores."""

    rank: int
    schedule_id: str
    scenario_id: str
    safe_a: SAFEScore | None = None
    safe_b: SAFEScore | None = None
    utility_score: float = 0.0
    is_primary: bool = False


# ═══════════════════════════════════════════════════════════════
#  EX-P7: COMPILED PARAMETER TYPES
# ═══════════════════════════════════════════════════════════════


class CompiledInstrument(BaseModel):
    """Compiled psychometric properties for one instrument.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 1.
    """

    instrument_id: str
    instrument_name: str
    a_k: float = 0.0  # intercept (default if unknown)
    b_k: float  # loading coefficient
    alpha_k: float  # compiled Cronbach's α
    se_alpha: float
    cancer_validation_status: str  # CANCER_VALIDATED|USED_IN_CANCER|GENERAL_POPULATION|CONFOUNDED
    k_studies: int
    total_n: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


class CompiledPriorNode(BaseModel):
    """Compiled prior for one node in one context.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 2.
    """

    node_id: str
    cancer_type: str
    treatment_phase: str
    mu_prior: float
    sd_prior: float
    n_total: int
    k_studies: int
    provenance_status: str = "CURATED_TRACED"
    source_studies: list[str] = Field(default_factory=list)


class CompiledTemporalKernel(BaseModel):
    """Compiled temporal kernel for one intervention.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 3 (intervention kernels).
    """

    action_id: str
    onset_weeks: float
    peak_weeks: float
    plateau_duration: float
    decay_rate: float
    k_timepoints: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


class CompiledRecoveryParams(BaseModel):
    """Compiled recovery trajectory for one intervention class.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 3 (recovery params).
    Formula: r(t) = r_inf * (1 - exp(-(t/tau_r)^gamma_r))
    """

    intervention_class: str
    cancer_type: str = "any"
    r_inf: float
    tau_r: float  # months
    gamma_r: float
    k_timepoints: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


class CompiledDoseResponse(BaseModel):
    """Compiled dose-response parameters for one intervention.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 4.
    Formula: E(d) = E0 + Emax * d^h / (ED50^h + d^h)
    """

    action_id: str
    e0: float
    emax: float
    ed50: float
    hill: float
    k_dose_levels: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


class CompiledModifier(BaseModel):
    """Compiled subgroup modifier for one variable-value pair.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 5.
    """

    modifier_variable: str
    modifier_value: str
    edge_id: str | None = None
    multiplier: float
    grade: str  # HIGH|MODERATE|LOW
    k_studies: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


class CompiledSynergy(BaseModel):
    """Compiled synergy coefficient for one intervention pair.

    SYS_EXTRACTION_ADDENDUM Part 6, Compiler 6.
    """

    action_a_id: str
    action_b_id: str
    gamma: float
    interaction_type: str  # synergistic|additive|antagonistic
    k_studies: int
    provenance_status: str = "CURATED_TRACED"
    provenance_ref: str = ""


# ═══════════════════════════════════════════════════════════════
#  Gate Violation Exception
# ═══════════════════════════════════════════════════════════════


class GateViolation(Exception):
    """Raised when a pipeline gate check fails.

    Gates must raise, not log.
    """

    def __init__(self, gate_id: str, message: str, context: dict[str, Any] | None = None):
        self.gate_id = gate_id
        self.context = context or {}
        super().__init__(f"Gate {gate_id} violated: {message}")
