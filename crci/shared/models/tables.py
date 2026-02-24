# VERIFIED: ORM models match 05_TABLE_SCHEMAS.md column definitions
# VERIFIED: imports — sqlalchemy + shared.models.enums
# VERIFIED: downstream — used by all DB-accessing modules
"""
Component: Layer 0 — SQLAlchemy ORM Models
Spec: 05_TABLE_SCHEMAS.md (all table definitions)
      06_FK_WIRING_MAP.md (relationship definitions)
Purpose: Declarative ORM for all persisted tables.
Reads: Nothing (defines table structure)
Writes: Nothing (imported by modules that do DB operations)
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ═══════════════════════════════════════════════════════════════
#  CLASS A: Knowledge (Domain Definitions)
# ═══════════════════════════════════════════════════════════════


class BiomarkerNodeDefinition(Base):
    """A3. ROOT table — 63 nodes in the causal DAG."""
    __tablename__ = "biomarker_node_definitions_v1"

    node_id = Column(String, primary_key=True)
    node_label = Column(Text, nullable=False)
    node_symbol = Column(Text)
    node_role = Column(String, nullable=False)
    orientation = Column(String, nullable=False)
    node_domain = Column(String, nullable=False)
    node_subtype = Column(String)
    default_state_space = Column(String, default="z")
    state_update_scale = Column(String)
    default_window_days = Column(Integer)
    min_observation_window_days = Column(Integer)
    allowed_source_types_json = Column(JSONB)
    is_actionable_input_node = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    description = Column(Text)
    notes = Column(Text)


class EdgeRelationsDefinition(Base):
    """A1. Every permitted causal edge in the DAG."""
    __tablename__ = "edge_relations_definitions_v1"

    edge_relation_id = Column(String, primary_key=True)
    module = Column(String, nullable=False)
    edge_family = Column(String)
    node_x = Column(String, nullable=False)
    node_y = Column(String, nullable=False)
    relation_label = Column(Text)
    canonical_statement = Column(Text)
    relation_type = Column(String)
    default_effect_direction = Column(Integer, default=1)
    allowed_measure_ids_json = Column(JSONB)
    allowed_upstream_instruments_json = Column(JSONB)
    default_temporal_family = Column(String)
    notes = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class EdgeOntology(Base):
    """A2. Operational constraints for each edge type."""
    __tablename__ = "edge_ontology_v1"

    ontology_id = Column(String, primary_key=True)
    edge_relation_id = Column(String, nullable=False)
    binary_outcome_bridge_allowed = Column(Boolean, default=False)
    proxy_mapping_policy = Column(String, default="family_match")
    allowed_scales_json = Column(JSONB)
    estimand_compatibility_rules = Column(Text)
    allowed_temporal_families_json = Column(JSONB)
    max_lag_steps = Column(Integer)
    aggregation_constraints_json = Column(JSONB)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class InstrumentDefinition(Base):
    """A4. Clinical assessment instruments (PSQI, FACT-Cog, etc.)."""
    __tablename__ = "instrument_definitions_v1"

    instrument_id = Column(String, primary_key=True)
    instrument_label = Column(Text, nullable=False)
    maps_to_node_id = Column(String, nullable=False)
    instrument_kind = Column(String)
    instrument_method = Column(String)
    recall_window_days = Column(Integer)
    time_aggregation = Column(String)
    raw_scale_spec = Column(Text)
    raw_unit = Column(Text)
    higher_means_pre_alignment = Column(String)
    direction_rule_id = Column(String)
    directionality_after_alignment = Column(String)
    adapter_output_kind = Column(String, default="z")
    adapter_spec_id = Column(String)
    required_fields_json = Column(JSONB)
    thresholds_json = Column(JSONB)
    preferred_norm_ref_id = Column(String)
    preferred_noise_id = Column(String)
    compatibility_group_id = Column(String)
    active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    description = Column(Text)
    notes = Column(Text)


class MeasureDefinition(Base):
    """A5. Biomarker/wearable/proxy measurement types."""
    __tablename__ = "measure_definitions_v1"

    measure_id = Column(String, primary_key=True)
    measure_label = Column(Text, nullable=False)
    maps_to_node_id = Column(String, nullable=False)
    measure_kind = Column(String)
    analyte = Column(String)
    specimen_or_device = Column(String)
    biospecimen = Column(String)
    device_type = Column(String)
    proxy_type = Column(String, nullable=False)
    time_aggregation = Column(String)
    raw_unit = Column(Text)
    value_transform_spec = Column(String)
    direction_rule_id = Column(String)
    directionality_after_alignment = Column(String)
    measure_family_id = Column(String)
    compatibility_group_id = Column(String)
    effective_window_days = Column(Integer)
    min_required_samples = Column(Integer)
    required_fields_json = Column(JSONB)
    preferred_norm_ref_id = Column(String)
    preferred_noise_id = Column(String)
    active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    description = Column(Text)
    notes = Column(Text)


class HarmonizationRule(Base):
    """A6. ROOT — Harmonization conversion rules."""
    __tablename__ = "harmonization_rules_v1"

    rule_id = Column(String, primary_key=True)
    rule_label = Column(Text, nullable=False)
    conversion_family = Column(String, nullable=False)
    input_effect_type = Column(String, nullable=False)
    output_scale = Column(String, nullable=False)
    formula_spec = Column(Text, nullable=False)
    required_inputs_json = Column(JSONB, nullable=False)
    fallback_inputs_json = Column(JSONB)
    applicability_conditions_json = Column(JSONB)
    effect_on_pipeline = Column(String, default="allow")
    priority = Column(Integer, default=1)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class PredictorAlignmentRule(Base):
    """A7. Predictor alignment rules."""
    __tablename__ = "predictor_alignment_rules_v1"

    rule_id = Column(String, primary_key=True)
    target_measure_id = Column(String, nullable=False)
    alignment_type = Column(String, nullable=False)
    alignment_spec_json = Column(JSONB)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class LiteraryMechanisticPrior(Base):
    """A8. Literature-derived mechanistic priors."""
    __tablename__ = "literary_mechanistic_priors_v1"

    prior_id = Column(String, primary_key=True)
    prior_label = Column(Text, nullable=False)
    target_edge_relation_id = Column(String, nullable=False)
    prior_type = Column(String, nullable=False)
    prior_mean = Column(Float)
    prior_sd = Column(Float)
    prior_dist_family = Column(String, default="normal")
    evidence_basis = Column(String)
    evidence_strength = Column(String)
    source_study_id = Column(String)
    source_citation = Column(Text, nullable=False)
    temporal_spec_json = Column(JSONB)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class LiteraryConstraint(Base):
    """A9. Literature-derived constraints."""
    __tablename__ = "literary_constraints_v1"

    rule_id = Column(String, primary_key=True)
    rule_label = Column(Text, nullable=False)
    constraint_type = Column(String, nullable=False)
    target_node_id = Column(String)
    target_measure_id = Column(String)
    effect_on_pipeline = Column(String, nullable=False)
    condition_expression = Column(Text)
    params_json = Column(JSONB)
    evidence_basis = Column(String)
    source_study_id = Column(String)
    source_citation = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ContraindicationEscalationPolicy(Base):
    """A12. ROOT — Escalation policy definitions."""
    __tablename__ = "contraindication_escalation_policy_v1"

    escalation_id = Column(String, primary_key=True)
    policy_label = Column(Text, nullable=False)
    system_behavior = Column(String, nullable=False)
    allowed_action_classes_json = Column(JSONB)
    user_message = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class ContraindicationRule(Base):
    """A10. Contraindication safety rules."""
    __tablename__ = "contraindication_rules_v1"

    rule_id = Column(String, primary_key=True)
    rule_label = Column(Text, nullable=False)
    condition_expression = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    target_action_classes_json = Column(JSONB)
    escalation_id = Column(String)
    unknown_input_policy = Column(String, default="trigger_question")
    required_question_id = Column(String)
    message_template = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ActionContraindicationLink(Base):
    """A11. Links actions to contraindication rules."""
    __tablename__ = "action_contraindication_links_v1"

    link_id = Column(String, primary_key=True)
    action_id = Column(String, nullable=False)
    rule_id = Column(String, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class ValidationRule(Base):
    """A13. Cross-table validation rules."""
    __tablename__ = "validation_rules_v1"

    validation_rule_id = Column(String, primary_key=True)
    rule_label = Column(Text, nullable=False)
    rule_type = Column(String, nullable=False)
    target_table = Column(String, nullable=False)
    target_column = Column(String)
    check_expression = Column(Text, nullable=False)
    severity = Column(String, default="error")
    enforcement_point = Column(String, default="etl_commit")
    error_message_template = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class VariableDefinition(Base):
    """A14. Modifier variable definitions."""
    __tablename__ = "variable_definitions_v1"

    variable_id = Column(String, primary_key=True)
    variable_label = Column(Text, nullable=False)
    variable_type = Column(String, nullable=False)
    variable_domain = Column(String)
    source_ref_type = Column(String)
    source_ref_id = Column(String)
    allowed_values_json = Column(JSONB)
    default_value = Column(Text)
    description = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class VariableToInputMap(Base):
    """A15. Maps variables to intake inputs."""
    __tablename__ = "variable_to_input_map_v1"

    map_id = Column(String, primary_key=True)
    variable_id = Column(String, nullable=False)
    input_source_type = Column(String, nullable=False)
    input_source_id = Column(String)
    transform_spec = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class BaselineModifierDefinition(Base):
    """A16. Baseline modifier definitions."""
    __tablename__ = "baseline_modifier_definitions_v1"

    modifier_id = Column(String, primary_key=True)
    modifier_label = Column(Text, nullable=False)
    target_edge_param_ids_json = Column(JSONB, nullable=False)
    required_variable_ids_json = Column(JSONB, nullable=False)
    parameterization_mode = Column(String, nullable=False)
    multiplier_spec_json = Column(JSONB, nullable=False)
    evidence_grade = Column(String, default="C")
    se_inflation_factor = Column(Float, default=1.0)
    cumulative_guard_min = Column(Float, default=0.5)
    cumulative_guard_max = Column(Float, default=2.0)
    source_ler_ids = Column(JSONB)
    source_citation = Column(Text)
    cancer_type = Column(String)
    treatment_phase = Column(String)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class DerivedFeatureDefinition(Base):
    """A17. Computed feature definitions."""
    __tablename__ = "derived_feature_definitions_v1"

    feature_id = Column(String, primary_key=True)
    feature_label = Column(Text, nullable=False)
    maps_to_node_id = Column(String)
    feature_type = Column(String, nullable=False)
    feature_domain = Column(String)
    feature_source = Column(String)
    compute_stage = Column(String)
    formula_spec = Column(Text, nullable=False)
    input_ids_json = Column(JSONB, nullable=False)
    dependency_ids_json = Column(JSONB)
    output_unit = Column(String, default="z")
    norm_id = Column(String)
    noise_id = Column(String)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class TriangulationSet(Base):
    """A18. Triangulation set definitions."""
    __tablename__ = "triangulation_sets_v1"

    triangulation_id = Column(String, primary_key=True)
    triangulation_label = Column(Text, nullable=False)
    target_node_id = Column(String, nullable=False)
    output_feature_id = Column(String)
    aggregation_method = Column(String, default="weighted_mean")
    min_members_required = Column(Integer, default=2)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class TriangulationMember(Base):
    """A19. Members within triangulation sets."""
    __tablename__ = "triangulation_members_v1"

    member_id = Column(String, primary_key=True)
    triangulation_id = Column(String, nullable=False)
    member_entity_type = Column(String, nullable=False)
    member_entity_id = Column(String, nullable=False)
    member_order = Column(Integer, nullable=False)
    weight = Column(Float, default=1.0)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class DescriptionTemplate(Base):
    """A20. ROOT — Description templates for reporting."""
    __tablename__ = "description_templates_v1"

    template_id = Column(String, primary_key=True)
    template_label = Column(Text, nullable=False)
    target_entity_type = Column(String, nullable=False)
    template_text = Column(Text, nullable=False)
    variables_json = Column(JSONB)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class ActionCatalog(Base):
    """A21. ROOT — Intervention catalog."""
    __tablename__ = "action_catalog_v1"

    action_id = Column(String, primary_key=True)
    action_label = Column(Text, nullable=False)
    action_class = Column(String, nullable=False)
    description = Column(Text)
    dose_type = Column(String, nullable=False)
    dose_unit = Column(String)
    dose_min = Column(Float)
    dose_max = Column(Float)
    dose_default = Column(Float)
    burden_score = Column(Float)
    adherence_estimate = Column(Float)
    evidence_basis = Column(String)
    evidence_strength = Column(String)
    target_pathways_json = Column(JSONB)
    contraindication_notes = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class QuestionObservationModel(Base):
    """A23. Observation models for questions."""
    __tablename__ = "question_observation_models_v1"

    model_id = Column(String, primary_key=True)
    model_label = Column(Text, nullable=False)
    target_entity_type = Column(String, nullable=False)
    target_entity_id = Column(String, nullable=False)
    observation_function = Column(String, nullable=False)
    params_json = Column(JSONB, nullable=False)
    noise_id = Column(String)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class QuestionBank(Base):
    """A22. Question bank for adaptive intake."""
    __tablename__ = "question_bank_v1"

    question_id = Column(String, primary_key=True)
    question_text = Column(Text, nullable=False)
    question_role = Column(String, nullable=False)
    answer_type = Column(String, nullable=False)
    answer_options_json = Column(JSONB)
    observation_model_id = Column(String, nullable=False)
    noise_id = Column(String)
    burden_cost = Column(Float, default=1.0)
    applicability_expression = Column(Text)
    missing_answer_policy = Column(String, default="skip")
    display_order = Column(Integer)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class NormalizationRef(Base):
    """A24. Population normalization references."""
    __tablename__ = "normalization_refs_v1"

    norm_id = Column(String, primary_key=True)
    target_entity_type = Column(String, nullable=False)
    target_entity_id = Column(String, nullable=False)
    population_label = Column(Text, nullable=False)
    cancer_type = Column(String)
    treatment_phase = Column(String)
    ref_mean = Column(Float, nullable=False)
    ref_sd = Column(Float, nullable=False)
    ref_n = Column(Integer, nullable=False)
    percentile_5 = Column(Float)
    percentile_25 = Column(Float)
    percentile_50 = Column(Float)
    percentile_75 = Column(Float)
    percentile_95 = Column(Float)
    source_study_id = Column(String)
    source_citation = Column(Text, nullable=False)
    year_published = Column(Integer)
    is_cancer_specific = Column(Integer, default=0)
    version = Column(Integer, default=1)
    notes = Column(Text)


class ObservationNoise(Base):
    """A25. Measurement noise specifications."""
    __tablename__ = "observation_noise_v1"

    noise_id = Column(String, primary_key=True)
    target_entity_type = Column(String, nullable=False)
    target_entity_id = Column(String, nullable=False)
    reliability_alpha = Column(Float)
    noise_variance = Column(Float, nullable=False)
    noise_source = Column(String)
    cancer_validation_status = Column(String)
    se_multiplier = Column(Float, default=1.0)
    proxy_r_squared = Column(Float)
    proxy_caveat = Column(Text)
    source_study_id = Column(String)
    source_citation = Column(Text, nullable=False)
    condition_dependent = Column(Integer, default=0)
    condition_description = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class Pathway(Base):
    """A26. Mechanistic and clinical mediator pathways."""
    __tablename__ = "pathways_v1"

    pathway_id = Column(String, primary_key=True)
    pathway_label = Column(Text, nullable=False)
    tier = Column(String, nullable=False)
    entry_node_ids_json = Column(JSONB, nullable=False)
    exit_node_ids_json = Column(JSONB, nullable=False)
    intermediate_node_ids_json = Column(JSONB)
    edge_relation_ids_json = Column(JSONB)
    cognitive_domain_specificity_json = Column(JSONB)
    best_proxy_biomarker = Column(String)
    proxy_r_squared = Column(Float)
    causal_evidence_level = Column(String)
    key_citation = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class PathwayInteraction(Base):
    """A27. Cross-pathway interactions."""
    __tablename__ = "pathway_interactions_v1"

    interaction_id = Column(String, primary_key=True)
    pathway_a_id = Column(String, nullable=False)
    pathway_b_id = Column(String, nullable=False)
    interaction_type = Column(String, nullable=False)
    interaction_strength = Column(Float)
    directionality = Column(String, nullable=False)
    shared_nodes_json = Column(JSONB)
    mechanism_description = Column(Text, nullable=False)
    key_citation = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class InterventionSynergy(Base):
    """A28. Pairwise intervention synergy records."""
    __tablename__ = "intervention_synergy_v1"

    synergy_id = Column(String, primary_key=True)
    action_a_id = Column(String, nullable=False)
    action_b_id = Column(String, nullable=False)
    jpo = Column(Float, nullable=False)
    ccs = Column(Float, nullable=False)
    interaction_type = Column(String, nullable=False)
    interaction_magnitude = Column(Float)
    gamma_prior_alpha = Column(Float, nullable=False)
    gamma_prior_beta = Column(Float, nullable=False)
    gamma_cap = Column(Float, nullable=False)
    source_study_id = Column(String)
    validation_status = Column(String)
    version = Column(Integer, default=1)
    notes = Column(Text)


class RecoveryTrajectory(Base):
    """A29. ROOT — Natural recovery parameters."""
    __tablename__ = "recovery_trajectories_v1"

    trajectory_id = Column(String, primary_key=True)
    cancer_type = Column(String, nullable=False)
    regimen_class = Column(Text, nullable=False)
    r_infinity = Column(Float, nullable=False)
    r_infinity_se = Column(Float)
    tau_r_months = Column(Float, nullable=False)
    tau_r_se = Column(Float)
    gamma_r = Column(Float, nullable=False)
    acc_factor = Column(Float, nullable=False)
    source_citation = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    notes = Column(Text)


class BiomarkerCorrelation(Base):
    """A30. Correlated biomarker pairs for D matrix."""
    __tablename__ = "biomarker_correlations_v1"

    correlation_id = Column(String, primary_key=True)
    node_a_id = Column(String, nullable=False)
    node_b_id = Column(String, nullable=False)
    rho = Column(Float, nullable=False)
    rho_se = Column(Float)
    d_block = Column(String, nullable=False)
    source_citation = Column(Text, nullable=False)
    is_decision_critical = Column(Integer, default=0)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class FeedbackLoop(Base):
    """A31. Feedback loop structures in the DAG."""
    __tablename__ = "feedback_loops_v1"

    loop_id = Column(String, primary_key=True)
    loop_label = Column(Text, nullable=False)
    edge_relation_ids_json = Column(JSONB, nullable=False)
    node_ids_json = Column(JSONB, nullable=False)
    loop_gain = Column(Float, nullable=False)
    characteristic_period_weeks = Column(String)
    forward_dynamics = Column(Text, nullable=False)
    reverse_dynamics = Column(Text, nullable=False)
    breaking_intervention = Column(String)
    spectral_radius_contribution = Column(Float)
    version = Column(Integer, default=1)
    notes = Column(Text)


class InterventionKernel(Base):
    """A32. Per-intervention temporal kernels."""
    __tablename__ = "intervention_kernels_v1"

    kernel_id = Column(String, primary_key=True)
    action_id = Column(String, nullable=False)
    kernel_family = Column(String, nullable=False)
    onset_weeks_min = Column(Float, nullable=False)
    onset_weeks_max = Column(Float, nullable=False)
    build_weeks = Column(Float, nullable=False)
    steady_state_weeks_min = Column(Float, nullable=False)
    steady_state_weeks_max = Column(Float, nullable=False)
    decay_half_life_weeks = Column(Float, nullable=False)
    pathway_specific_onset_json = Column(JSONB)
    source_citation = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class MIDThreshold(Base):
    """A33. Minimally Important Difference thresholds."""
    __tablename__ = "mid_thresholds_v1"

    domain_id = Column(String, primary_key=True)
    d_mid = Column(Float, nullable=False)
    d_ce = Column(Float, nullable=False)
    d_plateau = Column(Float, nullable=False)
    anchor_source = Column(Text, nullable=False)
    anchor_method = Column(String, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  CLASS B: Evidence (Extracted Study Data)
# ═══════════════════════════════════════════════════════════════


class StudyRegistry(Base):
    """B1. ROOT — Paper-level canonical record."""
    __tablename__ = "study_registry_v1"

    study_id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    authors = Column(Text)
    journal = Column(Text)
    year = Column(Integer)
    doi = Column(Text)
    pmid = Column(Text)
    pmcid = Column(Text)
    study_design = Column(String)
    notes = Column(Text)
    version = Column(Integer, default=1)


class StudyCohortProfile(Base):
    """B2. Cohort-level metadata per study."""
    __tablename__ = "study_cohort_profiles_v1"

    profile_id = Column(String, primary_key=True)
    study_id = Column(String, nullable=False)
    cohort_label = Column(Text)
    analysis_timepoint = Column(String)
    N_analyzed = Column(Integer)
    N_enrolled = Column(Integer)
    cancer_type = Column(String)
    treatment_phase = Column(String)
    sex_female_pct = Column(Float)
    age_mean = Column(Float)
    age_sd = Column(Float)
    cancer_context_json = Column(JSONB)
    analysis_context_json = Column(JSONB)
    notes = Column(Text)
    version = Column(Integer, default=1)


class EdgeEvidence(Base):
    """B6. THE main evidence store — extracted effect estimates."""
    __tablename__ = "edge_evidence_v1"

    ler_id = Column(String, primary_key=True)
    edge_param_id = Column(String)
    edge_relation_id = Column(String, nullable=False)
    profile_id = Column(String, nullable=False)
    study_id = Column(String, nullable=False)
    edge_family = Column(String)
    node_x = Column(String)
    node_y = Column(String)
    effect_type_reported = Column(String, nullable=False)
    effect_value_reported = Column(Float, nullable=False)
    se_reported = Column(Float)
    ci_low_reported = Column(Float)
    ci_high_reported = Column(Float)
    p_value = Column(Float)
    N_effect = Column(Integer, nullable=False)
    harmonization_status = Column(String, default="unreviewed")
    harmonized_scale = Column(String)
    harmonized_beta = Column(Float)
    harmonized_se = Column(Float)
    quality_rating = Column(String, default="moderate")
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ExtractionAudit(Base):
    """E13/B. Pipeline quality monitoring."""
    __tablename__ = "extraction_audit_v1"

    audit_id = Column(String, primary_key=True)
    study_id = Column(String, nullable=False)
    pipeline_stage = Column(String, nullable=False)
    agent_id = Column(String)
    status = Column(String, nullable=False)
    records_input = Column(Integer, nullable=False, default=0)
    records_output = Column(Integer, nullable=False, default=0)
    records_rejected = Column(Integer, nullable=False, default=0)
    rejection_reasons_json = Column(JSONB)
    quality_flags_json = Column(JSONB)
    execution_time_seconds = Column(Float, nullable=False, default=0)
    llm_tokens_used = Column(Integer)
    deterministic_parser_used = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    operator_id = Column(String)
    notes = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  CLASS C: Compiled (Aggregated Parameters)
# ═══════════════════════════════════════════════════════════════


class Edge(Base):
    """C1. THE KEY TABLE — compiled edge parameters."""
    __tablename__ = "edges_v1"

    edge_param_id = Column(String, primary_key=True)
    edge_relation_id = Column(String, nullable=False)
    measure_id = Column(String)
    effect_scale = Column(String)
    effect_direction = Column(Integer)
    beta_mean = Column(Float, nullable=False)
    beta_se = Column(Float)
    beta_dist_family = Column(String, default="normal")
    ci_low = Column(Float)
    ci_high = Column(Float)
    aggregation_method = Column(String)
    evidence_level = Column(String)
    cancer_type = Column(String)
    treatment_phase = Column(String)
    scope_filters_json = Column(JSONB)
    time_step_unit = Column(String, default="day")
    temporal_family = Column(String)
    lag_steps = Column(Integer, default=0)
    half_life_steps = Column(Float)
    specificity_rank = Column(Integer, default=0)
    supporting_ler_ids = Column(Text)
    active = Column(Integer, default=1)
    version = Column(Integer, default=1)
    i_squared = Column(Float)
    tau_squared = Column(Float)
    total_n = Column(Integer)
    pub_bias_risk = Column(String)
    se_inflation_pub_bias = Column(Float, default=1.0)
    coherence_flag = Column(String)
    se_inflation_coherence = Column(Float, default=1.0)
    e_value = Column(Float)
    robustness_value = Column(Float)
    notes = Column(Text)


class NodePrior(Base):
    """C3. Scoped prior distributions for nodes."""
    __tablename__ = "node_priors_v1"

    prior_id = Column(String, primary_key=True)
    node_id = Column(String, nullable=False)
    prior_space = Column(String, default="z")
    mean = Column(Float, nullable=False, default=0.0)
    sd = Column(Float, nullable=False, default=1.0)
    dist_family = Column(String, default="normal")
    cancer_type = Column(String)
    treatment_phase = Column(String)
    scope_filters_json = Column(JSONB)
    specificity_rank = Column(Integer, default=0)
    provenance = Column(Text)
    active = Column(Integer, default=1)
    version = Column(Integer, default=1)
    notes = Column(Text)


class StateEstimatorSpec(Base):
    """C5. ROOT — Bayesian state estimation configuration."""
    __tablename__ = "state_estimator_specs_v1"

    estimator_id = Column(String, primary_key=True)
    estimator_family = Column(String, nullable=False)
    update_space = Column(String, default="node_z")
    min_sigma_floor = Column(Float, default=0.2)
    max_sigma_cap = Column(Float, default=5.0)
    conflict_inflation_family = Column(String, default="multiplicative_sd")
    conflict_inflation_params_json = Column(JSONB)
    missingness_inflation_family = Column(String, default="additive_var")
    missingness_inflation_params_json = Column(JSONB)
    core_coverage_policy = Column(String, default="require_safety_coverage")
    required_nodes_json = Column(JSONB)
    admissibility_filters_json = Column(JSONB)
    independence_assumption = Column(Integer, default=1)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  CLASS D: Policy (Decision Configuration)
# ═══════════════════════════════════════════════════════════════


class ObjectiveSpec(Base):
    """D1. ROOT — Utility function specifications."""
    __tablename__ = "objective_specs_v1"

    objective_id = Column(String, primary_key=True)
    objective_label = Column(Text)
    outcome_terms_json = Column(JSONB)
    risk_metric = Column(String)
    risk_aversion_lambda = Column(Float, default=0.5)
    burden_weight = Column(Float, default=0.7)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class SafetyPolicy(Base):
    """D2. ROOT — Safety policies."""
    __tablename__ = "safety_policies_v1"

    safety_policy_id = Column(String, primary_key=True)
    trigger_type = Column(String, nullable=False)
    system_behavior = Column(String, nullable=False)
    message_template = Column(Text)
    priority = Column(Integer, default=1)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class EscalationPolicy(Base):
    """D3. ROOT — Escalation protocols."""
    __tablename__ = "escalation_policies_v1"

    escalation_id = Column(String, primary_key=True)
    policy_label = Column(Text)
    system_behavior = Column(String, nullable=False)
    allowed_action_classes_json = Column(JSONB)
    user_message = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  CLASS E: Output (Session Results & Audit)
# ═══════════════════════════════════════════════════════════════


class RecommendationRun(Base):
    """E6. Run header — one row per engine execution."""
    __tablename__ = "recommendation_runs_v1"

    run_id = Column(String, primary_key=True)
    subject_ref = Column(String, nullable=False)
    started_at = Column(String, nullable=False)
    ended_at = Column(String)
    engine_commit_hash = Column(String)
    policy_versions_json = Column(JSONB)
    random_seed = Column(Integer, nullable=False)
    time_step_unit = Column(String, default="day")
    horizon_days = Column(Integer, default=28)
    base_state_id = Column(String)
    objective_spec_id = Column(String)
    safety_policy_id = Column(String)
    escalation_policy_id = Column(String)
    output_mode = Column(String, default="index_mode")
    primary_schedule_id = Column(String)
    run_warnings_json = Column(JSONB)
    var_decomp_json = Column(JSONB)
    notes = Column(Text)


class StateSnapshot(Base):
    """E1. Bayesian state estimates."""
    __tablename__ = "state_snapshots_v1"

    state_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    subject_ref = Column(String, nullable=False)
    state_time = Column(String, nullable=False)
    estimator_id = Column(String)
    node_beliefs_json = Column(JSONB, nullable=False)
    coverage_json = Column(JSONB)
    conflict_flags_json = Column(JSONB)
    obs_used_count = Column(Integer, default=0)
    notes_json = Column(JSONB)


# ═══════════════════════════════════════════════════════════════
#  OPS TABLES
# ═══════════════════════════════════════════════════════════════


class ReviewTask(Base):
    """HITL review queue."""
    __tablename__ = "review_tasks"

    task_id = Column(String, primary_key=True)
    task_type = Column(String, nullable=False)
    source_stage = Column(String, nullable=False)
    source_entity_id = Column(String, nullable=False)
    source_table = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    status = Column(String, nullable=False, default="pending")
    assigned_to = Column(String)
    summary = Column(Text, nullable=False)
    context_json = Column(JSONB)
    resolution = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime)
    notes = Column(Text)


class ExtractionRun(Base):
    """Per-paper extraction run tracking."""
    __tablename__ = "extraction_runs"

    extraction_run_id = Column(String, primary_key=True)
    study_id = Column(String)
    pdf_path = Column(Text, nullable=False)
    pdf_hash = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    ended_at = Column(DateTime)
    status = Column(String, nullable=False, default="running")
    extraction_mode = Column(String)
    model_id = Column(String)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    policy_snapshot_id = Column(String)
    stages_completed_json = Column(JSONB)
    error_message = Column(Text)
    notes = Column(Text)


class PolicySnapshot(Base):
    """Policy version snapshot per run."""
    __tablename__ = "policy_snapshots"

    snapshot_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    snapshot_time = Column(DateTime, nullable=False, server_default=func.now())
    config_hash = Column(String, nullable=False)
    table_versions_json = Column(JSONB, nullable=False)
    code_commit_hash = Column(String)
    python_version = Column(String)
    dependency_versions_json = Column(JSONB)
    notes = Column(Text)


class BuildManifest(Base):
    """Build provenance for compilation runs."""
    __tablename__ = "build_manifests_v1"

    build_id = Column(String, primary_key=True)
    build_label = Column(Text, nullable=False)
    build_time = Column(DateTime, nullable=False, server_default=func.now())
    build_type = Column(String, nullable=False)
    input_tables_json = Column(JSONB, nullable=False)
    output_tables_json = Column(JSONB, nullable=False)
    config_snapshot_id = Column(String)
    code_commit_hash = Column(String)
    status = Column(String, nullable=False, default="ok")
    summary_json = Column(JSONB)
    warnings_json = Column(JSONB)
    notes = Column(Text)
    version = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  REMAINING CLASS B TABLES
# ═══════════════════════════════════════════════════════════════


class ProfileDataStream(Base):
    """B3. Data stream within a cohort profile."""
    __tablename__ = "profile_data_streams_v1"

    stream_id = Column(String, primary_key=True)
    profile_id = Column(String, nullable=False)
    stream_label = Column(Text)
    analyte_or_target = Column(String)
    modality_type = Column(String)
    capture_method = Column(String)
    instrument_id = Column(String)
    measure_id = Column(String)
    version = Column(Integer, default=1)
    notes = Column(Text)


class StreamTimepoint(Base):
    """B4. Timepoints within a data stream."""
    __tablename__ = "stream_timepoints_v1"

    timepoint_id = Column(String, primary_key=True)
    stream_id = Column(String, nullable=False)
    timepoint_label = Column(Text)
    timepoint_type = Column(String)
    anchor_event = Column(String)
    timepoint_minutes = Column(Integer)
    clock_time_hhmm = Column(String)
    version = Column(Integer, default=1)


class OntologyLink(Base):
    """B5. Cross-references from studies to ontology entities."""
    __tablename__ = "ontology_links_v1"

    link_id = Column(String, primary_key=True)
    target_table = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    study_id = Column(String, nullable=False)
    support_type = Column(String)
    evidence_strength = Column(String)
    snippet = Column(Text)
    locator = Column(Text)
    notes = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class EdgeParamBuild(Base):
    """B7. Edge compilation build records."""
    __tablename__ = "edge_param_builds_v1"

    build_id = Column(String, primary_key=True)
    build_label = Column(Text)
    build_time = Column(String)
    build_version = Column(Integer, default=1)
    aggregation_policy = Column(String)
    status = Column(String, default="ok")
    notes = Column(Text)
    active = Column(Integer, default=1)


class TriangulationEvidence(Base):
    """B8. Cross-method agreement evidence."""
    __tablename__ = "triangulation_evidence_v1"

    tri_ev_id = Column(String, primary_key=True)
    triangulation_id = Column(String, nullable=False)
    profile_id = Column(String)
    agreement_metric = Column(String)
    agreement_value = Column(Float)
    N_agreement = Column(Integer)
    source_study_id = Column(String)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class PathwayBiomarker(Base):
    """B9. Pathway-biomarker loading evidence."""
    __tablename__ = "pathway_biomarkers_v1"

    pb_id = Column(String, primary_key=True)
    pathway_id = Column(String, nullable=False)
    node_id = Column(String, nullable=False)
    measure_id = Column(String, nullable=False)
    indicator_type = Column(String, nullable=False)
    loading_coefficient = Column(Float, nullable=False)
    loading_se = Column(Float, nullable=False)
    source_study_id = Column(String, nullable=False)
    sample_matrix = Column(String, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  REMAINING CLASS C TABLES
# ═══════════════════════════════════════════════════════════════


class DoseBridge(Base):
    """C2. Action-to-node dose response bridges."""
    __tablename__ = "dose_bridges_v1"

    bridge_id = Column(String, primary_key=True)
    action_id = Column(String, nullable=False)
    output_mode = Column(String, nullable=False)
    maps_to_node_id = Column(String)
    dose_type = Column(String)
    dose_unit = Column(String)
    dose_reference = Column(Float, nullable=False)
    dose_response_family = Column(String, nullable=False)
    dose_response_params_json = Column(JSONB)
    bridge_effect_sign = Column(Integer, nullable=False)
    bridge_gain = Column(Float, nullable=False)
    temporal_family = Column(String, default="delta")
    lag_steps = Column(Integer, default=0)
    provenance = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class OutcomeAnchor(Base):
    """C4. Calibration anchors for outcome mapping."""
    __tablename__ = "outcome_anchors_v1"

    anchor_id = Column(String, primary_key=True)
    target_level = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    calibration_family = Column(String, nullable=False)
    calibration_params_json = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ChainValidationResult(Base):
    """C6. Chain-vs-direct validation results."""
    __tablename__ = "chain_validation_results_v1"

    cv_id = Column(String, primary_key=True)
    pathway_id = Column(String, nullable=False)
    chain_length = Column(Integer, nullable=False)
    edges_in_chain_json = Column(JSONB)
    beta_chain = Column(Float, nullable=False)
    se_chain = Column(Float, nullable=False)
    beta_direct = Column(Float)
    se_direct = Column(Float)
    z_statistic = Column(Float)
    triage_tier = Column(String, nullable=False)
    failure_mode = Column(String)
    se_inflation_applied = Column(Float, default=1.0)
    build_id = Column(String)
    version = Column(Integer, default=1)


class PublicationBiasResult(Base):
    """C7. Publication bias assessment results."""
    __tablename__ = "publication_bias_results_v1"

    pb_result_id = Column(String, primary_key=True)
    edge_param_id = Column(String, nullable=False)
    k_studies = Column(Integer, nullable=False)
    egger_intercept = Column(Float)
    egger_p_value = Column(Float)
    egger_significant = Column(Boolean)
    n_trimmed = Column(Integer)
    beta_adjusted_tf = Column(Float)
    bias_risk = Column(String, nullable=False)
    se_inflation_pub_bias = Column(Float, default=1.0)
    build_id = Column(String)
    version = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  REMAINING CLASS D TABLES
# ═══════════════════════════════════════════════════════════════


class StatusQuoRule(Base):
    """D4. Baseline dose assumptions."""
    __tablename__ = "status_quo_rules_v1"

    sq_rule_id = Column(String, primary_key=True)
    action_id = Column(String, nullable=False)
    condition_expression = Column(Text)
    baseline_source_type = Column(String)
    dose_infer_spec = Column(Text)
    default_dose = Column(Float)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class VOIRule(Base):
    """D5. Value-of-information policy rules."""
    __tablename__ = "voi_rules_v1"

    voi_rule_id = Column(String, primary_key=True)
    rule_type = Column(String, nullable=False)
    target_ref_type = Column(String)
    target_ref_id = Column(String)
    weight_value = Column(Float)
    max_questions_per_session = Column(Integer)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class ComplexityScalingResult(Base):
    """D6. Complexity-scaling validation results."""
    __tablename__ = "complexity_scaling_results_v1"

    cs_id = Column(String, primary_key=True)
    horizontal_level = Column(String, nullable=False)
    vertical_level = Column(String, nullable=False)
    n_edges_active = Column(Integer, nullable=False)
    n_layers_active = Column(Integer, nullable=False)
    top_5_interventions_json = Column(JSONB, nullable=False)
    flip_rate_vs_full = Column(Float, nullable=False)
    mean_beta_shift = Column(Float, nullable=False)
    mc_draws = Column(Integer, nullable=False)
    run_timestamp = Column(String, nullable=False)
    version = Column(Integer, default=1)


class PopulationArchetype(Base):
    """D7. Population archetype definitions."""
    __tablename__ = "population_archetypes_v1"

    archetype_id = Column(String, primary_key=True)
    archetype_label = Column(Text, nullable=False)
    k_clusters = Column(Integer, nullable=False)
    bic_score = Column(Float, nullable=False)
    centroid_json = Column(JSONB, nullable=False)
    n_patients_assigned = Column(Integer, default=0)
    prevalence = Column(Float)
    model_version = Column(Integer, default=1)
    active = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  REMAINING CLASS E TABLES
# ═══════════════════════════════════════════════════════════════


class ScenarioDefinition(Base):
    """E2. What-if scenario configurations."""
    __tablename__ = "scenario_definitions_v1"

    scenario_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    scenario_type = Column(String, nullable=False)
    scenario_label = Column(Text, nullable=False)
    base_state_id = Column(String, nullable=False)
    start_date = Column(String)
    horizon_days = Column(Integer, nullable=False)
    time_step_unit = Column(String, default="day")
    generation_policy = Column(String)
    constraints_applied_json = Column(JSONB)
    notes_json = Column(JSONB)


class ScenarioItem(Base):
    """E3. Actions within each scenario."""
    __tablename__ = "scenario_items_v1"

    scenario_item_id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False)
    action_id = Column(String, nullable=False)
    dose_value = Column(Float, nullable=False)
    dose_unit = Column(String)
    timing_plan_json = Column(JSONB, nullable=False)
    frequency_plan_json = Column(JSONB, nullable=False)
    duration_days = Column(Integer, nullable=False)
    source_tag = Column(String, nullable=False)
    notes_json = Column(JSONB)


class SchedulePlan(Base):
    """E4. Optimized schedule plans."""
    __tablename__ = "schedule_plans_v1"

    schedule_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    source_scenario_id = Column(String, nullable=False)
    plan_rank = Column(Integer, default=1)
    plan_type = Column(String, default="primary")
    objective_weights_json = Column(JSONB)
    expected_outcomes_json = Column(JSONB)
    utility_score = Column(Float)
    rationale_json = Column(JSONB)
    created_at = Column(String, nullable=False)


class ScheduleItem(Base):
    """E5. Scheduled actions within a plan."""
    __tablename__ = "schedule_items_v1"

    schedule_item_id = Column(String, primary_key=True)
    schedule_id = Column(String, nullable=False)
    action_id = Column(String, nullable=False)
    dose_value = Column(Float, nullable=False)
    dose_unit = Column(String)
    timing_plan_json = Column(JSONB, nullable=False)
    frequency_plan_json = Column(JSONB, nullable=False)
    duration_days = Column(Integer, nullable=False)
    order_index = Column(Integer, default=0)


class SimulationTrace(Base):
    """E7. Monte Carlo simulation trace records."""
    __tablename__ = "simulation_trace_v1"

    sim_trace_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False)
    n_samples = Column(Integer, nullable=False)
    seed_used = Column(Integer, nullable=False)
    edges_used_json = Column(JSONB, nullable=False)
    bridges_used_json = Column(JSONB)
    modifiers_applied_json = Column(JSONB)
    sim_warnings_json = Column(JSONB)


class DecisionTrace(Base):
    """E8. Decision audit trail."""
    __tablename__ = "decision_trace_v1"

    decision_trace_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    objective_spec_id = Column(String)
    selection_rule = Column(String)
    candidate_scores_json = Column(JSONB)
    chosen_schedule_id = Column(String)
    decision_warnings_json = Column(JSONB)


class ContraindicationEvalTrace(Base):
    """E9. Safety evaluation audit trail."""
    __tablename__ = "contraindication_eval_trace_v1"

    trace_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    timestamp = Column(String)
    subject_ref = Column(String, nullable=False)
    state_id = Column(String)
    action_id = Column(String)
    rule_id = Column(String, nullable=False)
    evaluation_result = Column(String, nullable=False)
    severity_applied = Column(String)
    action_taken = Column(String, nullable=False)
    notes_json = Column(JSONB)


class QuestionSelectionTrace(Base):
    """E10. VOI-based question selection audit."""
    __tablename__ = "question_selection_trace_v1"

    qtrace_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    state_id = Column(String)
    step_index = Column(Integer, nullable=False)
    selection_stage = Column(String, nullable=False)
    chosen_question_ids_json = Column(JSONB, nullable=False)
    voi_method = Column(String)
    created_at = Column(String, nullable=False)
    version = Column(Integer, default=1)


class ModifierEvalTrace(Base):
    """E11. Personalization audit trail."""
    __tablename__ = "modifier_eval_trace_v1"

    eval_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    state_id = Column(String, nullable=False)
    modifier_id = Column(String, nullable=False)
    edge_param_id = Column(String, nullable=False)
    variable_id = Column(String, nullable=False)
    variable_value = Column(String, nullable=False)
    multiplier_applied = Column(Float, nullable=False)
    evidence_grade = Column(String)
    beta_before = Column(Float, nullable=False)
    beta_after = Column(Float, nullable=False)
    se_inflation_applied = Column(Float, default=1.0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)


class QuestionSequence(Base):
    """E12. Adaptive intake record."""
    __tablename__ = "question_sequence_v1"

    sequence_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False)
    question_id = Column(String, nullable=False)
    sequence_position = Column(Integer, nullable=False)
    state_id_before = Column(String, nullable=False)
    state_id_after = Column(String, nullable=False)
    observation_model_id = Column(String, nullable=False)
    selection_trace_id = Column(String, nullable=False)
    response_status = Column(String, nullable=False)
    response_value = Column(String)
    response_z_score = Column(Float)
    variance_reduction_achieved = Column(Float)
    response_time_seconds = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
