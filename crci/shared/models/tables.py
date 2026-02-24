# VERIFIED: ORM models match SQL schemas in 001-007 column-for-column
# VERIFIED: imports — sqlalchemy
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
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ═══════════════════════════════════════════════════════════════
#  CLASS A: Knowledge (Domain Definitions) — 33 tables
# ═══════════════════════════════════════════════════════════════


class EdgeRelationsDefinition(Base):
    """A1. Every permitted causal edge in the DAG."""
    __tablename__ = "edge_relations_definitions_v1"

    edge_relation_id = Column(Text, primary_key=True)
    module = Column(Text, nullable=False)
    edge_family = Column(Text, nullable=False)
    node_x = Column(Text, nullable=False)
    node_y = Column(Text, nullable=False)
    relation_label = Column(Text, nullable=False)
    canonical_statement = Column(Text, nullable=False)
    relation_type = Column(Text, nullable=False)
    default_effect_direction = Column(Integer, nullable=False)
    allowed_measure_ids_json = Column(Text)
    allowed_upstream_instruments_json = Column(Text)
    default_temporal_family = Column(Text)
    notes = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class EdgeOntology(Base):
    """A2. Operational constraints for each edge type."""
    __tablename__ = "edge_ontology_v1"

    ontology_id = Column(Text, primary_key=True)
    edge_relation_id = Column(Text, nullable=False)
    binary_outcome_bridge_allowed = Column(Integer, nullable=False)
    proxy_mapping_policy = Column(Text, nullable=False)
    allowed_scales_json = Column(Text, nullable=False)
    estimand_compatibility_rules = Column(Text, nullable=False)
    allowed_temporal_families_json = Column(Text, nullable=False)
    max_lag_steps = Column(Integer)
    aggregation_constraints_json = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class BiomarkerNodeDefinition(Base):
    """A3. ROOT — 63 nodes in the causal DAG."""
    __tablename__ = "biomarker_node_definitions_v1"

    node_id = Column(Text, primary_key=True)
    node_label = Column(Text, nullable=False)
    node_symbol = Column(Text)
    node_role = Column(Text, nullable=False)
    orientation = Column(Text, nullable=False)
    node_domain = Column(Text, nullable=False)
    node_subtype = Column(Text)
    default_state_space = Column(Text, nullable=False)
    state_update_scale = Column(Text, nullable=False)
    default_window_days = Column(Integer)
    min_observation_window_days = Column(Integer)
    allowed_source_types_json = Column(JSONB, nullable=False)
    is_actionable_input_node = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    notes = Column(Text)


class InstrumentDefinition(Base):
    """A4. Clinical assessment instruments (PSQI, FACT-Cog, etc.)."""
    __tablename__ = "instrument_definitions_v1"

    instrument_id = Column(Text, primary_key=True)
    instrument_label = Column(Text, nullable=False)
    maps_to_node_id = Column(Text, nullable=False)
    instrument_kind = Column(Text, nullable=False)
    instrument_method = Column(Text, nullable=False)
    recall_window_days = Column(Integer)
    time_aggregation = Column(Text, nullable=False)
    raw_scale_spec = Column(Text, nullable=False)
    raw_unit = Column(Text, nullable=False)
    higher_means_pre_alignment = Column(Text, nullable=False)
    direction_rule_id = Column(Text, nullable=False)
    directionality_after_alignment = Column(Text, nullable=False)
    adapter_output_kind = Column(Text, nullable=False)
    adapter_spec_id = Column(Text)
    required_fields_json = Column(JSONB, nullable=False)
    thresholds_json = Column(JSONB)
    preferred_norm_ref_id = Column(Text)
    preferred_noise_id = Column(Text)
    compatibility_group_id = Column(Text)
    active = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    notes = Column(Text)


class MeasureDefinition(Base):
    """A5. Biomarker/wearable/proxy measurement types."""
    __tablename__ = "measure_definitions_v1"

    measure_id = Column(Text, primary_key=True)
    measure_label = Column(Text, nullable=False)
    maps_to_node_id = Column(Text, nullable=False)
    measure_kind = Column(Text, nullable=False)
    analyte = Column(Text)
    specimen_or_device = Column(Text, nullable=False)
    biospecimen = Column(Text)
    device_type = Column(Text)
    proxy_type = Column(Text, nullable=False)
    time_aggregation = Column(Text, nullable=False)
    raw_unit = Column(Text, nullable=False)
    value_transform_spec = Column(Text)
    direction_rule_id = Column(Text, nullable=False)
    directionality_after_alignment = Column(Text, nullable=False)
    measure_family_id = Column(Text, nullable=False)
    compatibility_group_id = Column(Text, nullable=False)
    effective_window_days = Column(Integer)
    min_required_samples = Column(Integer)
    required_fields_json = Column(JSONB, nullable=False)
    preferred_norm_ref_id = Column(Text)
    preferred_noise_id = Column(Text)
    active = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    notes = Column(Text)


class HarmonizationRule(Base):
    """A6. ROOT — Harmonization conversion rules."""
    __tablename__ = "harmonization_rules_v1"

    rule_id = Column(Text, primary_key=True)
    effect_type_reported = Column(Text, nullable=False)
    x_transform_required = Column(Text, nullable=False)
    y_transform_required = Column(Text, nullable=False)
    required_fields = Column(Text, nullable=False)
    output_scale = Column(Text, nullable=False)
    conversion_family = Column(Text, nullable=False)
    conversion_notes = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class PredictorAlignmentRule(Base):
    """A7. Predictor alignment rules for cohort matching."""
    __tablename__ = "predictor_alignment_rules_v1"

    align_id = Column(Text, primary_key=True)
    profile_id = Column(Text, nullable=False)
    predictor_ref_type = Column(Text, nullable=False)
    predictor_ref_id = Column(Text, nullable=False)
    outcome_measure_id = Column(Text, nullable=False)
    alignment_type = Column(Text, nullable=False)
    lag_days = Column(Integer, nullable=False)
    window_spec = Column(Text)
    notes = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class LiteraryMechanisticPrior(Base):
    """A8. Literature-derived mechanistic priors."""
    __tablename__ = "literary_mechanistic_priors_v1"

    prior_id = Column(Text, primary_key=True)
    prior_label = Column(Text, nullable=False)
    prior_type = Column(Text, nullable=False)
    target_level = Column(Text, nullable=False)
    target_ref = Column(Text, nullable=False)
    condition_spec = Column(Text, nullable=False)
    effect_on_pipeline = Column(Text, nullable=False)
    strength = Column(Text, nullable=False)
    prior_params = Column(Text)
    evidence_basis = Column(Text, nullable=False)
    study_id = Column(Text)
    population_scope = Column(Text, nullable=False)
    phase_scope = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class LiteraryConstraint(Base):
    """A9. Biological bounds on node trajectories."""
    __tablename__ = "literary_constraints_v1"

    rule_id = Column(Text, primary_key=True)
    rule_label = Column(Text, nullable=False)
    rule_type = Column(Text, nullable=False)
    strength = Column(Text, nullable=False)
    applies_to_node = Column(Text)
    applies_to_measure_id = Column(Text)
    applies_to_aux_variable = Column(Text)
    regime = Column(Text, nullable=False)
    phase_scope = Column(Text, nullable=False)
    population_scope = Column(Text, nullable=False)
    trigger_inputs_required = Column(Text)
    rule_spec = Column(Text, nullable=False)
    effect_on_engine = Column(Text, nullable=False)
    output_target = Column(Text, nullable=False)
    output_scale = Column(Text, nullable=False)
    output_range = Column(Text)
    missingness_policy = Column(Text, nullable=False)
    default_behavior = Column(Text)
    priority = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    study_id = Column(Text)
    notes = Column(Text)


class ContraindicationRule(Base):
    """A10. Contraindication safety rules."""
    __tablename__ = "contraindication_rules_v1"

    rule_id = Column(Text, primary_key=True)
    rule_label = Column(Text, nullable=False)
    applies_to_type = Column(Text, nullable=False)
    applies_to_ref = Column(Text)
    severity = Column(Text, nullable=False)
    condition_expression = Column(Text, nullable=False)
    required_inputs_json = Column(Text, nullable=False)
    unknown_input_policy = Column(Text, nullable=False)
    penalty_spec_json = Column(Text)
    escalation_id = Column(Text)
    rationale = Column(Text, nullable=False)
    provenance = Column(Text)
    tags_json = Column(Text)
    created_by = Column(Text)
    created_at = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class ActionContraindicationLink(Base):
    """A11. Links actions to contraindication rules."""
    __tablename__ = "action_contraindication_links_v1"

    link_id = Column(Text, primary_key=True)
    action_id = Column(Text, nullable=False)
    rule_id = Column(Text, nullable=False)
    override_mode = Column(Text)
    scope_constraints_json = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class ContraindicationEscalationPolicy(Base):
    """A12. ROOT — Escalation policy definitions."""
    __tablename__ = "contraindication_escalation_policy_v1"

    escalation_id = Column(Text, primary_key=True)
    policy_label = Column(Text, nullable=False)
    system_behavior = Column(Text, nullable=False)
    allowed_action_classes_json = Column(Text)
    user_message = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class ValidationRule(Base):
    """A13. Cross-table validation rules."""
    __tablename__ = "validation_rules_v1"

    rule_id = Column(Text, primary_key=True)
    rule_label = Column(Text, nullable=False)
    target_table = Column(Text, nullable=False)
    target_column = Column(Text)
    rule_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    enforcement_point = Column(Text, nullable=False)
    condition_expression = Column(Text, nullable=False)
    required_inputs_json = Column(Text, nullable=False)
    error_message_template = Column(Text, nullable=False)
    depends_on_tables_json = Column(Text)
    priority = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class VariableDefinition(Base):
    """A14. Modifier variable definitions."""
    __tablename__ = "variable_definitions_v1"

    variable_id = Column(Text, primary_key=True)
    variable_label = Column(Text, nullable=False)
    variable_description = Column(Text, nullable=False)
    variable_domain = Column(Text, nullable=False)
    variable_type = Column(Text, nullable=False)
    allowed_values_json = Column(Text)
    unit = Column(Text)
    value_range = Column(Text)
    source_namespace = Column(Text, nullable=False)
    source_ref_id = Column(Text)
    missingness_policy = Column(Text, nullable=False)
    default_value = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class VariableToInputMap(Base):
    """A15. Maps variables to intake inputs."""
    __tablename__ = "variable_to_input_map_v1"

    map_id = Column(Text, primary_key=True)
    variable_id = Column(Text, nullable=False)
    input_token = Column(Text, nullable=False)
    transform = Column(Text, nullable=False)
    transform_params_json = Column(Text)
    precedence_rank = Column(Integer, nullable=False)
    required_inputs_json = Column(Text, nullable=False)
    missing_input_policy = Column(Text, nullable=False)
    default_value = Column(Text)
    validity_check = Column(Text)
    scope_json = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class BaselineModifierDefinition(Base):
    """A16. Baseline modifier definitions."""
    __tablename__ = "baseline_modifier_definitions_v1"

    modifier_id = Column(Text, primary_key=True)
    modifier_label = Column(Text, nullable=False)
    modifier_description = Column(Text, nullable=False)
    support_class = Column(Text, nullable=False)
    evidence_required = Column(Integer, nullable=False)
    source_ler_ids = Column(Text)
    required_variable_ids_json = Column(Text, nullable=False)
    applies_to = Column(Text, nullable=False)
    parameterization_mode = Column(Text, nullable=False)
    effect_spec_json = Column(Text, nullable=False)
    bounds_json = Column(Text)
    missing_input_policy = Column(Text, nullable=False)
    conflict_input_policy = Column(Text, nullable=False)
    scope_json = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class DerivedFeatureDefinition(Base):
    """A17. Computed feature definitions."""
    __tablename__ = "derived_feature_definitions_v1"

    feature_id = Column(Text, primary_key=True)
    feature_label = Column(Text, nullable=False)
    feature_description = Column(Text, nullable=False)
    maps_to_node = Column(Text)
    mapped_nodes_json = Column(Text, nullable=False)
    feature_domain = Column(Text, nullable=False)
    feature_role = Column(Text, nullable=False)
    feature_type = Column(Text, nullable=False)
    feature_source = Column(Text, nullable=False)
    dependency_ids = Column(Text, nullable=False)
    dependency_types = Column(Text, nullable=False)
    time_window = Column(Text, nullable=False)
    time_window_spec = Column(Text)
    normalization_method = Column(Text, nullable=False)
    normalization_reference = Column(Text)
    formula_spec = Column(Text, nullable=False)
    sign_alignment = Column(Text, nullable=False)
    directionality = Column(Text, nullable=False)
    output_scale = Column(Text, nullable=False)
    output_unit = Column(Text, nullable=False)
    valid_range = Column(Text, nullable=False)
    threshold_spec = Column(Text)
    missingness_policy = Column(Text, nullable=False)
    imputation_spec = Column(Text)
    compute_priority = Column(Text, nullable=False)
    compute_stage = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class TriangulationSet(Base):
    """A18. Triangulation set definitions."""
    __tablename__ = "triangulation_sets_v1"

    triangulation_id = Column(Text, primary_key=True)
    triangulation_label = Column(Text, nullable=False)
    target_node_id = Column(Text, nullable=False)
    triangulation_scope = Column(Text, nullable=False)
    triangulation_goal = Column(Text, nullable=False)
    fusion_policy = Column(Text, nullable=False)
    conflict_policy = Column(Text, nullable=False)
    conflict_metric = Column(Text, nullable=False)
    min_members_required = Column(Integer, nullable=False)
    output_feature_id = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class TriangulationMember(Base):
    """A19. Members within triangulation sets (composite PK)."""
    __tablename__ = "triangulation_members_v1"

    triangulation_id = Column(Text, primary_key=True)
    member_order = Column(Integer, primary_key=True)
    member_entity_type = Column(Text, nullable=False)
    member_entity_id = Column(Text, nullable=False)
    member_role = Column(Text, nullable=False)
    weight_kind = Column(Text, nullable=False)
    weight_value = Column(Float)
    required_for_tri_set = Column(Integer, nullable=False)
    admissibility_qc_gate = Column(Text)
    notes = Column(Text)


class DescriptionTemplate(Base):
    """A20. ROOT — Description templates for reporting."""
    __tablename__ = "description_templates_v1"

    template_id = Column(Text, primary_key=True)
    template_label = Column(Text, nullable=False)
    template_scope = Column(Text, nullable=False)
    template_text = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class ActionCatalog(Base):
    """A21. ROOT — Intervention catalog."""
    __tablename__ = "action_catalog_v1"

    action_id = Column(Text, primary_key=True)
    action_label = Column(Text, nullable=False)
    action_class = Column(Text, nullable=False)
    dose_type = Column(Text, nullable=False)
    dose_unit = Column(Text)
    dose_semantics = Column(Text, nullable=False)
    dose_min = Column(Float, nullable=False)
    dose_max = Column(Float, nullable=False)
    dose_recommended_start = Column(Float, nullable=False)
    dose_step = Column(Float)
    time_cost_min_default = Column(Float, nullable=False)
    cognitive_load_default = Column(Float, nullable=False)
    logistics_load_default = Column(Float, nullable=False)
    overall_burden_default = Column(Float)
    adherence_rate_default = Column(Float)
    evidence_basis = Column(Text, nullable=False)
    evidence_strength = Column(Text, nullable=False)
    notes = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


class QuestionBank(Base):
    """A22. Question bank for adaptive intake."""
    __tablename__ = "question_bank_v1"

    question_id = Column(Text, primary_key=True)
    question_label = Column(Text, nullable=False)
    question_text = Column(Text, nullable=False)
    question_role = Column(Text, nullable=False)
    answer_type = Column(Text, nullable=False)
    answer_unit = Column(Text)
    answer_options_json = Column(Text)
    validation_min = Column(Float)
    validation_max = Column(Float)
    validation_rule_spec = Column(Text)
    maps_to_type = Column(Text, nullable=False)
    maps_to_ref = Column(Text, nullable=False)
    observation_model_id = Column(Text)
    time_window = Column(Text, nullable=False)
    time_window_spec = Column(Text)
    applicability_scope_json = Column(Text)
    prerequisite_inputs_json = Column(Text)
    missing_answer_policy = Column(Text, nullable=False)
    burden_time_min = Column(Float, nullable=False)
    burden_cognitive = Column(Float, nullable=False)
    burden_invasiveness = Column(Float, nullable=False)
    ask_frequency_policy = Column(Text, nullable=False)
    ask_frequency_spec = Column(Text)
    provenance = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class QuestionObservationModel(Base):
    """A23. Observation models for questions."""
    __tablename__ = "question_observation_models_v1"

    model_id = Column(Text, primary_key=True)
    question_id = Column(Text, nullable=False)
    output_type = Column(Text, nullable=False)
    output_ref_id = Column(Text, nullable=False)
    transform_spec = Column(Text, nullable=False)
    noise_spec_json = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class NormalizationRef(Base):
    """A24. Population normalization references."""
    __tablename__ = "normalization_refs_v1"

    norm_id = Column(Text, primary_key=True)
    target_entity_type = Column(Text, nullable=False)
    target_entity_id = Column(Text, nullable=False)
    population_label = Column(Text, nullable=False)
    cancer_type = Column(Text, nullable=False)
    treatment_phase = Column(Text, nullable=False)
    ref_mean = Column(Float, nullable=False)
    ref_sd = Column(Float, nullable=False)
    ref_n = Column(Integer, nullable=False)
    percentile_5 = Column(Float)
    percentile_25 = Column(Float)
    percentile_50 = Column(Float)
    percentile_75 = Column(Float)
    percentile_95 = Column(Float)
    source_study_id = Column(Text)
    source_citation = Column(Text, nullable=False)
    year_published = Column(Integer)
    is_cancer_specific = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    notes = Column(Text)


class ObservationNoise(Base):
    """A25. Measurement noise specifications."""
    __tablename__ = "observation_noise_v1"

    noise_id = Column(Text, primary_key=True)
    target_entity_type = Column(Text, nullable=False)
    target_entity_id = Column(Text, nullable=False)
    reliability_alpha = Column(Float)
    noise_variance = Column(Float, nullable=False)
    noise_source = Column(Text, nullable=False)
    cancer_validation_status = Column(Text, nullable=False)
    se_multiplier = Column(Float, nullable=False)
    proxy_r_squared = Column(Float)
    proxy_caveat = Column(Text)
    source_study_id = Column(Text)
    source_citation = Column(Text, nullable=False)
    condition_dependent = Column(Integer, nullable=False)
    condition_description = Column(Text)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class Pathway(Base):
    """A26. Mechanistic and clinical mediator pathways."""
    __tablename__ = "pathways_v1"

    pathway_id = Column(Text, primary_key=True)
    pathway_label = Column(Text, nullable=False)
    tier = Column(Text, nullable=False)
    entry_node_ids_json = Column(JSONB, nullable=False)
    exit_node_ids_json = Column(JSONB, nullable=False)
    intermediate_node_ids_json = Column(JSONB, nullable=False)
    edge_relation_ids_json = Column(JSONB, nullable=False)
    cognitive_domain_specificity_json = Column(JSONB, nullable=False)
    best_proxy_biomarker = Column(Text)
    proxy_r_squared = Column(Float)
    causal_evidence_level = Column(Text, nullable=False)
    key_citation = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class PathwayInteraction(Base):
    """A27. Cross-pathway interactions."""
    __tablename__ = "pathway_interactions_v1"

    interaction_id = Column(Text, primary_key=True)
    pathway_a_id = Column(Text, nullable=False)
    pathway_b_id = Column(Text, nullable=False)
    interaction_type = Column(Text, nullable=False)
    interaction_strength = Column(Float, nullable=False)
    directionality = Column(Text, nullable=False)
    shared_nodes_json = Column(JSONB)
    mechanism_description = Column(Text, nullable=False)
    key_citation = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class InterventionSynergy(Base):
    """A28. Pairwise intervention synergy records."""
    __tablename__ = "intervention_synergy_v1"

    synergy_id = Column(Text, primary_key=True)
    action_a_id = Column(Text, nullable=False)
    action_b_id = Column(Text, nullable=False)
    jpo = Column(Float, nullable=False)
    ccs = Column(Float, nullable=False)
    interaction_type = Column(Text, nullable=False)
    interaction_magnitude = Column(Float)
    gamma_prior_alpha = Column(Float, nullable=False)
    gamma_prior_beta = Column(Float, nullable=False)
    gamma_cap = Column(Float, nullable=False)
    source_study_id = Column(Text)
    validation_status = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    notes = Column(Text)


class RecoveryTrajectory(Base):
    """A29. ROOT — Natural recovery parameters."""
    __tablename__ = "recovery_trajectories_v1"

    trajectory_id = Column(Text, primary_key=True)
    cancer_type = Column(Text, nullable=False)
    regimen_class = Column(Text, nullable=False)
    r_infinity = Column(Float, nullable=False)
    r_infinity_se = Column(Float, nullable=False)
    tau_r_months = Column(Float, nullable=False)
    tau_r_se = Column(Float, nullable=False)
    gamma_r = Column(Float, nullable=False)
    acc_factor = Column(Float, nullable=False)
    source_citation = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    notes = Column(Text)


class BiomarkerCorrelation(Base):
    """A30. Correlated biomarker pairs for D matrix."""
    __tablename__ = "biomarker_correlations_v1"

    correlation_id = Column(Text, primary_key=True)
    node_a_id = Column(Text, nullable=False)
    node_b_id = Column(Text, nullable=False)
    rho = Column(Float, nullable=False)
    rho_se = Column(Float)
    d_block = Column(Text, nullable=False)
    source_citation = Column(Text, nullable=False)
    is_decision_critical = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class FeedbackLoop(Base):
    """A31. Feedback loop structures in the DAG."""
    __tablename__ = "feedback_loops_v1"

    loop_id = Column(Text, primary_key=True)
    loop_label = Column(Text, nullable=False)
    edge_relation_ids_json = Column(JSONB, nullable=False)
    node_ids_json = Column(JSONB, nullable=False)
    loop_gain = Column(Float, nullable=False)
    characteristic_period_weeks = Column(Text, nullable=False)
    forward_dynamics = Column(Text, nullable=False)
    reverse_dynamics = Column(Text, nullable=False)
    breaking_intervention = Column(Text)
    spectral_radius_contribution = Column(Float)
    version = Column(Integer, nullable=False)
    notes = Column(Text)


class InterventionKernel(Base):
    """A32. Per-intervention temporal kernels."""
    __tablename__ = "intervention_kernels_v1"

    kernel_id = Column(Text, primary_key=True)
    action_id = Column(Text, nullable=False)
    kernel_family = Column(Text, nullable=False)
    onset_weeks_min = Column(Float, nullable=False)
    onset_weeks_max = Column(Float, nullable=False)
    build_weeks = Column(Float, nullable=False)
    steady_state_weeks_min = Column(Float, nullable=False)
    steady_state_weeks_max = Column(Float, nullable=False)
    decay_half_life_weeks = Column(Float, nullable=False)
    pathway_specific_onset_json = Column(JSONB)
    source_citation = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)
    notes = Column(Text)


class MIDThreshold(Base):
    """A33. ROOT — Minimally Important Difference thresholds."""
    __tablename__ = "mid_thresholds_v1"

    domain_id = Column(Text, primary_key=True)
    d_mid = Column(Float, nullable=False)
    d_ce = Column(Float, nullable=False)
    d_plateau = Column(Float, nullable=False)
    anchor_source = Column(Text, nullable=False)
    anchor_method = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Integer, nullable=False)


# ═══════════════════════════════════════════════════════════════
#  CLASS B: Evidence (Extracted Study Data) — 10 tables
#  B1-B9 + E13 (extraction_audit)
# ═══════════════════════════════════════════════════════════════


class StudyRegistry(Base):
    """B1. ROOT — Paper-level canonical record."""
    __tablename__ = "study_registry_v1"

    study_id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    authors = Column(Text)
    journal = Column(Text)
    year = Column(Integer)
    doi = Column(Text)
    pmid = Column(Text)
    pmcid = Column(Text)
    study_design = Column(Text)
    notes = Column(Text)
    version = Column(Integer, default=1)


class StudyCohortProfile(Base):
    """B2. Cohort-level metadata per study."""
    __tablename__ = "study_cohort_profiles_v1"

    profile_id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    cohort_label = Column(Text)
    analysis_timepoint = Column(Text)
    N_analyzed = Column(Integer)
    N_enrolled = Column(Integer)
    recruitment_region = Column(Text)
    recruitment_sites = Column(Text)
    collection_calendar_start = Column(Text)
    collection_calendar_end = Column(Text)
    enrollment_window_text = Column(Text)
    eligibility_inclusion = Column(Text)
    eligibility_exclusion = Column(Text)
    key_exclusion_flags_json = Column(JSONB)
    index_event_time_refs_json = Column(JSONB)
    sex_female_pct = Column(Float)
    age_mean = Column(Float)
    age_sd = Column(Float)
    education_years_mean = Column(Float)
    education_years_sd = Column(Float)
    bmi_mean = Column(Float)
    bmi_sd = Column(Float)
    race_distribution_json = Column(JSONB)
    marital_distribution_json = Column(JSONB)
    income_distribution_json = Column(JSONB)
    other_demographics_json = Column(JSONB)
    cancer_context_json = Column(JSONB)
    cancer_type = Column(Text)
    treatment_phase = Column(Text)
    time_since_treatment_text = Column(Text)
    analysis_context_json = Column(JSONB)
    notes = Column(Text)
    version = Column(Integer, default=1)


class ProfileDataStream(Base):
    """B3. Data stream within a cohort profile."""
    __tablename__ = "profile_data_streams_v1"

    stream_id = Column(Text, primary_key=True)
    profile_id = Column(Text, nullable=False)
    stream_label = Column(Text)
    analyte_or_target = Column(Text)
    modality_type = Column(Text)
    capture_method = Column(Text)
    instrument_id = Column(Text)
    measure_id = Column(Text)
    administration_setting = Column(Text)
    administration_role = Column(Text)
    instrument_version = Column(Text)
    language = Column(Text, default="EN")
    translation_status = Column(Text)
    visit_context = Column(Text)
    recall_window_iso = Column(Text)
    schedule_pattern = Column(Text)
    schedule_pattern_spec = Column(Text)
    collection_time_unit = Column(Text)
    scheduled_duration_value = Column(Float)
    timestamp_source = Column(Text)
    primary_time_anchor = Column(Text)
    days_collected_value = Column(Float)
    quality_controls_summary = Column(Text)
    notes = Column(Text)
    version = Column(Integer, default=1)


class StreamTimepoint(Base):
    """B4. Timepoints within a data stream."""
    __tablename__ = "stream_timepoints_v1"

    timepoint_id = Column(Text, primary_key=True)
    stream_id = Column(Text, nullable=False)
    timepoint_label = Column(Text)
    timepoint_type = Column(Text)
    anchor_event = Column(Text)
    timepoint_minutes = Column(Integer)
    clock_time_hhmm = Column(Text)
    allowable_window_min = Column(Integer)
    required = Column(Integer, default=1)
    maps_to_measure = Column(Text)
    version = Column(Integer, default=1)


class OntologyLink(Base):
    """B5. Cross-references from studies to ontology entities."""
    __tablename__ = "ontology_links_v1"

    link_id = Column(Text, primary_key=True)
    target_table = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False)
    study_id = Column(Text, nullable=False)
    support_type = Column(Text)
    evidence_strength = Column(Text)
    snippet = Column(Text)
    locator = Column(Text)
    notes = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class EdgeEvidence(Base):
    """B6. THE main evidence store — 76-column extracted effect estimates."""
    __tablename__ = "edge_evidence_v1"

    ler_id = Column(Text, primary_key=True)
    edge_param_id = Column(Text)
    edge_relation_id = Column(Text, nullable=False)
    profile_id = Column(Text, nullable=False)
    study_id = Column(Text, nullable=False)
    edge_family = Column(Text)
    node_x = Column(Text)
    node_y = Column(Text)

    # Upstream (predictor / X) identifiers
    upstream_instrument_id = Column(Text)
    upstream_stream_id = Column(Text)
    upstream_raw_unit = Column(Text)

    # Downstream (outcome / Y) identifiers
    downstream_measure_id = Column(Text)
    downstream_stream_id = Column(Text)
    downstream_raw_unit = Column(Text)

    # Analysis model metadata
    analysis_model_family = Column(Text)
    analysis_model_family_id = Column(Text)
    model_family = Column(Text)
    random_effects_structure = Column(Text)
    cluster_unit = Column(Text)
    se_type = Column(Text)
    predictor_level = Column(Text)
    centered_level = Column(Text)
    centering_method = Column(Text)
    centering_note = Column(Text)

    # Outcome component and time definitions
    outcome_component = Column(Text)
    time_metric_definition = Column(Text)
    CAR_definition = Column(Text)
    time_unit_x = Column(Text)
    time_unit_y = Column(Text)

    # Transforms
    x_transform = Column(Text)
    y_transform = Column(Text)

    # Temporal alignment
    alignment_type = Column(Text)
    alignment_type_id = Column(Text)
    alignment_lag_days = Column(Integer)
    alignment_note = Column(Text)

    # Reported effect estimates
    effect_type_reported = Column(Text, nullable=False)
    effect_value_reported = Column(Float, nullable=False)
    se_reported = Column(Float)
    ci_low_reported = Column(Float)
    ci_high_reported = Column(Float)
    p_value = Column(Float)
    sd_x = Column(Float)
    sd_y = Column(Float)
    N_effect = Column(Integer, nullable=False)

    # Subgroup and adjustment
    subgroup_label = Column(Text)
    covariates_adjusted = Column(Text)
    adjustment_selection_method = Column(Text)

    # Harmonization
    harmonization_status = Column(Text, default="unreviewed")
    harmonized_scale = Column(Text)
    harmonized_beta = Column(Float)
    harmonized_se = Column(Float)
    blocked_reason = Column(Text)
    harmonization_rule_id = Column(Text)

    # Interaction / moderation
    interaction_reported = Column(Integer, default=0)
    interaction_variable_id = Column(Text)
    interaction_variable_raw = Column(Text)
    moderator_definition = Column(Text)
    interaction_beta = Column(Float)
    interaction_se = Column(Float)
    subgroup_beta_M0 = Column(Float)
    subgroup_se_M0 = Column(Float)
    subgroup_beta_M1 = Column(Float)
    subgroup_se_M1 = Column(Float)
    interaction_effect_reported = Column(Text)

    # Quality and audit
    quality_rating = Column(Text, default="moderate")
    extraction_snippet = Column(Text)
    entered_by = Column(Text)
    entered_at = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)

    # Risk-of-bias and causal identification
    rob_tool = Column(Text)
    rob_overall = Column(Text)
    estimand_class = Column(Text)
    identification_status = Column(Text)

    # Meta-analysis provenance
    parent_meta_study_id = Column(Text)

    notes = Column(Text)


class EdgeParamBuild(Base):
    """B7. Edge compilation build records."""
    __tablename__ = "edge_param_builds_v1"

    build_id = Column(Text, primary_key=True)
    build_label = Column(Text)
    build_time = Column(Text)
    build_version = Column(Integer, default=1)
    code_commit_hash = Column(Text)
    input_scope_spec_json = Column(JSONB)
    evidence_query_spec_json = Column(JSONB)
    harmonization_rule_ids_json = Column(JSONB)
    aggregation_policy = Column(Text)
    selection_policy_spec_json = Column(JSONB)
    timing_policy = Column(Text)
    timing_prior_ids_json = Column(JSONB)
    outputs_edge_param_ids_json = Column(JSONB)
    outputs_summary_json = Column(JSONB)
    warnings_json = Column(JSONB)
    status = Column(Text, default="ok")
    notes = Column(Text)
    active = Column(Integer, default=1)


class TriangulationEvidence(Base):
    """B8. Cross-method agreement evidence."""
    __tablename__ = "triangulation_evidence_v1"

    tri_ev_id = Column(Text, primary_key=True)
    triangulation_id = Column(Text, nullable=False)
    profile_id = Column(Text)
    scope_json = Column(JSONB)
    agreement_scope = Column(Text)
    member_a_order = Column(Integer)
    member_b_order = Column(Integer)
    agreement_metric = Column(Text)
    agreement_value = Column(Float)
    agreement_ci_low = Column(Float)
    agreement_ci_high = Column(Float)
    N_agreement = Column(Integer)
    p_value = Column(Float)
    evidence_origin = Column(Text)
    source_study_id = Column(Text)
    page_or_table = Column(Text)
    notes = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class PathwayBiomarker(Base):
    """B9. Pathway-biomarker loading evidence."""
    __tablename__ = "pathway_biomarkers_v1"

    pb_id = Column(Text, primary_key=True)
    pathway_id = Column(Text, nullable=False)
    node_id = Column(Text, nullable=False)
    measure_id = Column(Text, nullable=False)
    indicator_type = Column(Text, nullable=False)
    loading_coefficient = Column(Float, nullable=False)
    loading_se = Column(Float, nullable=False)
    source_study_id = Column(Text, nullable=False)
    source_ler_id = Column(Text)
    sample_matrix = Column(Text, nullable=False)
    assay_caveat = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ExtractionAudit(Base):
    """E13/B. Pipeline quality monitoring."""
    __tablename__ = "extraction_audit_v1"

    audit_id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    pipeline_stage = Column(Text, nullable=False)
    agent_id = Column(Text)
    status = Column(Text, nullable=False)
    records_input = Column(Integer, nullable=False, default=0)
    records_output = Column(Integer, nullable=False, default=0)
    records_rejected = Column(Integer, nullable=False, default=0)
    rejection_reasons_json = Column(JSONB)
    quality_flags_json = Column(JSONB)
    execution_time_seconds = Column(Float, nullable=False, default=0)
    llm_tokens_used = Column(Integer)
    deterministic_parser_used = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    operator_id = Column(Text)
    notes = Column(Text)


class StudyAnnotationsRaw(Base):
    """B10. Every annotation emitted by every agent before reconciliation.

    SYS_EX lines 2562-2583. 1 Row = one annotation emission from one agent.
    Written by: EX-P1-REC | Read by: Reconciliation (dedup ref), Audit.
    """
    __tablename__ = "study_annotations_raw_v1"

    raw_annotation_id = Column(Text, primary_key=True)
    extraction_run_id = Column(Text, nullable=False)
    study_id = Column(Text, nullable=False)
    entered_by = Column(Text, nullable=False)
    entered_at = Column(DateTime, nullable=False, server_default=func.now())
    category = Column(Text, nullable=False)
    target_entity_type = Column(Text)
    target_entity_id = Column(Text)
    content = Column(Text, nullable=False)
    structured_data_json = Column(JSONB)
    evidence_strength = Column(Text)
    extraction_snippet = Column(Text)
    source_span_id = Column(Text)


class StudyAnnotations(Base):
    """B11. Reconciled, deduplicated canonical annotations with maturity tracking.

    SYS_EX lines 2585-2612. 1 Row = one reconciled canonical annotation.
    Written by: EX-P1-ATB | Read by: EX-P4-MA, EX-ACQ-GAP, EX-PROM-THR.
    """
    __tablename__ = "study_annotations_v1"

    annotation_id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    ler_id = Column(Text)
    category = Column(Text, nullable=False)
    consumer = Column(Text)
    target_entity_type = Column(Text)
    target_entity_id = Column(Text)
    content = Column(Text, nullable=False)
    structured_data_json = Column(JSONB)
    evidence_strength = Column(Text)
    extraction_snippet = Column(Text)
    source_span_id = Column(Text)
    cross_agent_support_n = Column(Integer, nullable=False, default=1)
    adjudication_status = Column(Text, nullable=False, default="unreviewed")
    duplicate_of_annotation_id = Column(Text)
    reconciled_confidence = Column(Float)
    maturity = Column(Text, nullable=False, default="raw")
    promoted_to = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  CLASS C: Compiled (Aggregated Parameters) — 7 tables
# ═══════════════════════════════════════════════════════════════


class Edge(Base):
    """C1. THE KEY TABLE — compiled edge parameters."""
    __tablename__ = "edges_v1"

    edge_param_id = Column(Text, primary_key=True)
    edge_relation_id = Column(Text, nullable=False)
    measure_id = Column(Text)
    effect_scale = Column(Text)
    effect_direction = Column(Integer)
    beta_mean = Column(Float, nullable=False)
    beta_se = Column(Float)
    beta_dist_family = Column(Text, default="normal")
    ci_low = Column(Float)
    ci_high = Column(Float)
    aggregation_method = Column(Text)
    evidence_level = Column(Text)
    cancer_type = Column(Text)
    treatment_phase = Column(Text)
    scope_filters_json = Column(JSONB, default="{}")
    time_step_unit = Column(Text, default="day")
    temporal_family = Column(Text)
    lag_steps = Column(Integer, default=0)
    half_life_steps = Column(Float)
    timing_source = Column(Text)
    timing_source_ref = Column(Text)
    time_scale_compat_mode = Column(Text, default="native_step")
    baseline_modifier_mode = Column(Text, default="none")
    baseline_modifier_spec_json = Column(JSONB)
    constraint_rule_ids_json = Column(JSONB, default="[]")
    specificity_rank = Column(Integer, default=0)
    supporting_ler_ids = Column(Text)
    active = Column(Integer, default=1)
    version = Column(Integer, default=1)
    i_squared = Column(Float)
    tau_squared = Column(Float)
    total_n = Column(Integer)
    notes = Column(Text)
    pub_bias_risk = Column(Text)
    se_inflation_pub_bias = Column(Float, default=1.0)
    coherence_flag = Column(Text)
    se_inflation_coherence = Column(Float, default=1.0)
    e_value = Column(Float)
    robustness_value = Column(Float)


class DoseBridge(Base):
    """C2. Action-to-node dose response bridges."""
    __tablename__ = "dose_bridges_v1"

    bridge_id = Column(Text, primary_key=True)
    action_id = Column(Text, nullable=False)
    output_mode = Column(Text, nullable=False)
    output_feature_id = Column(Text)
    output_node_id = Column(Text)
    maps_to_node_id = Column(Text)
    dose_type = Column(Text)
    dose_unit = Column(Text)
    dose_min = Column(Float, default=0)
    dose_max = Column(Float)
    dose_step = Column(Float)
    dose_reference = Column(Float, nullable=False)
    dose_response_family = Column(Text, nullable=False)
    dose_response_params_json = Column(JSONB)
    bridge_effect_sign = Column(Integer, nullable=False)
    bridge_gain = Column(Float, nullable=False)
    bridge_noise_sd = Column(Float)
    time_step_unit = Column(Text, default="day")
    temporal_family = Column(Text, default="delta")
    lag_steps = Column(Integer, default=0)
    half_life_steps = Column(Float)
    scope_json = Column(JSONB, default="{}")
    provenance = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class NodePrior(Base):
    """C3. Scoped prior distributions for nodes."""
    __tablename__ = "node_priors_v1"

    prior_id = Column(Text, primary_key=True)
    node_id = Column(Text, nullable=False)
    prior_space = Column(Text, default="z")
    mean = Column(Float, nullable=False, default=0.0)
    sd = Column(Float, nullable=False, default=1.0)
    dist_family = Column(Text, default="normal")
    cancer_type = Column(Text)
    treatment_phase = Column(Text)
    scope_filters_json = Column(JSONB, default="{}")
    specificity_rank = Column(Integer, default=0)
    provenance = Column(Text)
    active = Column(Integer, default=1)
    version = Column(Integer, default=1)
    notes = Column(Text)


class OutcomeAnchor(Base):
    """C4. Calibration anchors for outcome mapping."""
    __tablename__ = "outcome_anchors_v1"

    anchor_id = Column(Text, primary_key=True)
    target_level = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False)
    calibration_family = Column(Text, nullable=False)
    calibration_params_json = Column(JSONB, nullable=False)
    scope_cancer_type = Column(Text)
    scope_treatment_phase = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class StateEstimatorSpec(Base):
    """C5. ROOT — Bayesian state estimation configuration."""
    __tablename__ = "state_estimator_specs_v1"

    estimator_id = Column(Text, primary_key=True)
    estimator_family = Column(Text, nullable=False)
    update_space = Column(Text, default="node_z")
    min_sigma_floor = Column(Float, default=0.2)
    max_sigma_cap = Column(Float, default=5.0)
    conflict_inflation_family = Column(Text, default="multiplicative_sd")
    conflict_inflation_params_json = Column(JSONB)
    missingness_inflation_family = Column(Text, default="additive_var")
    missingness_inflation_params_json = Column(JSONB)
    core_coverage_policy = Column(Text, default="require_safety_coverage")
    required_nodes_json = Column(JSONB)
    admissibility_filters_json = Column(JSONB)
    noise_fallback_policy = Column(Text, default="conservative_default")
    default_noise_params_json = Column(JSONB)
    independence_assumption = Column(Integer, default=1)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class ChainValidationResult(Base):
    """C6. Chain-vs-direct validation results."""
    __tablename__ = "chain_validation_results_v1"

    cv_id = Column(Text, primary_key=True)
    pathway_id = Column(Text, nullable=False)
    chain_length = Column(Integer, nullable=False)
    edges_in_chain_json = Column(JSONB)
    beta_chain = Column(Float, nullable=False)
    se_chain = Column(Float, nullable=False)
    beta_direct = Column(Float)
    se_direct = Column(Float)
    z_statistic = Column(Float)
    triage_tier = Column(Text, nullable=False)
    av_score = Column(Float)
    failure_mode = Column(Text)
    remediation = Column(Text)
    se_inflation_applied = Column(Float, default=1.0)
    build_id = Column(Text)
    version = Column(Integer, default=1)


class PublicationBiasResult(Base):
    """C7. Publication bias assessment results."""
    __tablename__ = "publication_bias_results_v1"

    pb_result_id = Column(Text, primary_key=True)
    edge_param_id = Column(Text, nullable=False)
    k_studies = Column(Integer, nullable=False)
    egger_intercept = Column(Float)
    egger_p_value = Column(Float)
    egger_significant = Column(Boolean)
    n_trimmed = Column(Integer)
    beta_adjusted_tf = Column(Float)
    loo_max_shift = Column(Float)
    loo_influential_json = Column(JSONB)
    bias_risk = Column(Text, nullable=False)
    se_inflation_pub_bias = Column(Float, default=1.0)
    build_id = Column(Text)
    version = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  CLASS D: Policy (Decision Configuration) — 7 tables
# ═══════════════════════════════════════════════════════════════


class ObjectiveSpec(Base):
    """D1. ROOT — Utility function specifications."""
    __tablename__ = "objective_specs_v1"

    objective_id = Column(Text, primary_key=True)
    objective_label = Column(Text)
    outcome_terms_json = Column(JSONB)
    risk_metric = Column(Text)
    risk_aversion_lambda = Column(Float, default=0.5)
    burden_weight = Column(Float, default=0.7)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)
    notes = Column(Text)


class SafetyPolicy(Base):
    """D2. ROOT — Safety policies."""
    __tablename__ = "safety_policies_v1"

    safety_policy_id = Column(Text, primary_key=True)
    trigger_type = Column(Text, nullable=False)
    system_behavior = Column(Text, nullable=False)
    message_template = Column(Text)
    priority = Column(Integer, default=1)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class EscalationPolicy(Base):
    """D3. ROOT — Escalation protocols."""
    __tablename__ = "escalation_policies_v1"

    escalation_id = Column(Text, primary_key=True)
    policy_label = Column(Text)
    system_behavior = Column(Text, nullable=False)
    allowed_action_classes_json = Column(JSONB)
    user_message = Column(Text)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class StatusQuoRule(Base):
    """D4. Baseline dose assumptions."""
    __tablename__ = "status_quo_rules_v1"

    sq_rule_id = Column(Text, primary_key=True)
    action_id = Column(Text, nullable=False)
    condition_expression = Column(Text)
    baseline_source_type = Column(Text)
    dose_infer_spec = Column(Text)
    default_dose = Column(Float)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class VOIRule(Base):
    """D5. Value-of-information policy rules."""
    __tablename__ = "voi_rules_v1"

    voi_rule_id = Column(Text, primary_key=True)
    rule_type = Column(Text, nullable=False)
    target_ref_type = Column(Text)
    target_ref_id = Column(Text)
    weight_value = Column(Float)
    max_questions_per_session = Column(Integer)
    version = Column(Integer, default=1)
    active = Column(Integer, default=1)


class ComplexityScalingResult(Base):
    """D6. Complexity-scaling validation results."""
    __tablename__ = "complexity_scaling_results_v1"

    cs_id = Column(Text, primary_key=True)
    horizontal_level = Column(Text, nullable=False)
    vertical_level = Column(Text, nullable=False)
    n_edges_active = Column(Integer, nullable=False)
    n_layers_active = Column(Integer, nullable=False)
    top_5_interventions_json = Column(JSONB, nullable=False)
    flip_rate_vs_full = Column(Float, nullable=False)
    mean_beta_shift = Column(Float, nullable=False)
    fragile_edges_json = Column(JSONB)
    mc_draws = Column(Integer, nullable=False)
    run_timestamp = Column(Text, nullable=False)
    version = Column(Integer, default=1)


class PopulationArchetype(Base):
    """D7. Population archetype definitions."""
    __tablename__ = "population_archetypes_v1"

    archetype_id = Column(Text, primary_key=True)
    archetype_label = Column(Text, nullable=False)
    k_clusters = Column(Integer, nullable=False)
    bic_score = Column(Float, nullable=False)
    centroid_json = Column(JSONB, nullable=False)
    n_patients_assigned = Column(Integer, default=0)
    prevalence = Column(Float)
    characteristic_interventions_json = Column(JSONB)
    model_version = Column(Integer, default=1)
    active = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  CLASS E: Output (Session Results & Audit) — 12 tables
# ═══════════════════════════════════════════════════════════════


class StateSnapshot(Base):
    """E1. Bayesian state estimates."""
    __tablename__ = "state_snapshots_v1"

    state_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    subject_ref = Column(Text, nullable=False)
    state_time = Column(Text, nullable=False)
    time_step_unit = Column(Text, default="day")
    estimator_id = Column(Text)
    prior_ref_id = Column(Text)
    node_beliefs_json = Column(JSONB, nullable=False)
    coverage_json = Column(JSONB, nullable=False, default="{}")
    conflict_flags_json = Column(JSONB, default="{}")
    evidence_contributions_json = Column(JSONB, default="[]")
    obs_used_count = Column(Integer, default=0)
    conflict_inflation_applied = Column(Integer, default=0)
    missingness_inflation_applied = Column(Integer, default=0)
    sigma_floor_applied = Column(Integer, default=0)
    notes_json = Column(JSONB, default="{}")


class ScenarioDefinition(Base):
    """E2. What-if scenario configurations."""
    __tablename__ = "scenario_definitions_v1"

    scenario_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    scenario_type = Column(Text, nullable=False)
    scenario_label = Column(Text, nullable=False)
    base_state_id = Column(Text, nullable=False)
    start_date = Column(Text)
    horizon_days = Column(Integer, nullable=False)
    time_step_unit = Column(Text, default="day")
    anchor_calendar_json = Column(JSONB, default="{}")
    generation_policy = Column(Text)
    constraints_applied_json = Column(JSONB, default="[]")
    notes_json = Column(JSONB, default="{}")


class ScenarioItem(Base):
    """E3. Actions within each scenario."""
    __tablename__ = "scenario_items_v1"

    scenario_item_id = Column(Text, primary_key=True)
    scenario_id = Column(Text, nullable=False)
    action_id = Column(Text, nullable=False)
    dose_value = Column(Float, nullable=False)
    dose_unit = Column(Text)
    timing_plan_json = Column(JSONB, nullable=False)
    frequency_plan_json = Column(JSONB, nullable=False)
    duration_days = Column(Integer, nullable=False)
    stop_rules_json = Column(JSONB, default="[]")
    source_tag = Column(Text, nullable=False)
    notes_json = Column(JSONB, default="{}")


class SchedulePlan(Base):
    """E4. Optimized schedule plans."""
    __tablename__ = "schedule_plans_v1"

    schedule_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    source_scenario_id = Column(Text, nullable=False)
    plan_rank = Column(Integer, default=1)
    plan_type = Column(Text, default="primary")
    objective_weights_json = Column(JSONB)
    constraints_applied_json = Column(JSONB, default="[]")
    expected_outcomes_json = Column(JSONB)
    risk_summary_json = Column(JSONB)
    utility_score = Column(Float)
    rationale_json = Column(JSONB)
    created_at = Column(Text, nullable=False)


class ScheduleItem(Base):
    """E5. Scheduled actions within a plan."""
    __tablename__ = "schedule_items_v1"

    schedule_item_id = Column(Text, primary_key=True)
    schedule_id = Column(Text, nullable=False)
    action_id = Column(Text, nullable=False)
    dose_value = Column(Float, nullable=False)
    dose_unit = Column(Text)
    timing_plan_json = Column(JSONB, nullable=False)
    frequency_plan_json = Column(JSONB, nullable=False)
    duration_days = Column(Integer, nullable=False)
    ramp_json = Column(JSONB)
    stop_rules_json = Column(JSONB, default="[]")
    order_index = Column(Integer, default=0)


class RecommendationRun(Base):
    """E6. Run header — one row per engine execution."""
    __tablename__ = "recommendation_runs_v1"

    run_id = Column(Text, primary_key=True)
    subject_ref = Column(Text, nullable=False)
    started_at = Column(Text, nullable=False)
    ended_at = Column(Text)
    engine_commit_hash = Column(Text)
    policy_versions_json = Column(JSONB)
    random_seed = Column(Integer, nullable=False)
    time_step_unit = Column(Text, default="day")
    horizon_days = Column(Integer, default=28)
    base_state_id = Column(Text)
    objective_spec_id = Column(Text)
    safety_policy_id = Column(Text)
    escalation_policy_id = Column(Text)
    output_mode = Column(Text, default="index_mode")
    anchor_id = Column(Text)
    primary_schedule_id = Column(Text)
    alternative_schedule_ids_json = Column(JSONB, default="[]")
    run_warnings_json = Column(JSONB, default="[]")
    p_rank_1_json = Column(JSONB)
    decision_critical_edges_json = Column(JSONB)
    var_decomp_json = Column(JSONB)
    discovery_scores_json = Column(JSONB)
    evsi_top_edges_json = Column(JSONB)
    archetype_id = Column(Text)
    archetype_distance = Column(Float)
    voi_method = Column(Text)


class SimulationTrace(Base):
    """E7. Monte Carlo simulation trace records."""
    __tablename__ = "simulation_trace_v1"

    sim_trace_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    scenario_id = Column(Text, nullable=False)
    n_samples = Column(Integer, nullable=False)
    seed_used = Column(Integer, nullable=False)
    edges_used_json = Column(JSONB, nullable=False)
    bridges_used_json = Column(JSONB, default="[]")
    modifiers_applied_json = Column(JSONB, default="[]")
    constraint_triggers_json = Column(JSONB, default="[]")
    sim_warnings_json = Column(JSONB, default="[]")


class DecisionTrace(Base):
    """E8. Decision audit trail."""
    __tablename__ = "decision_trace_v1"

    decision_trace_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    objective_spec_id = Column(Text)
    selection_rule = Column(Text)
    candidate_scores_json = Column(JSONB)
    rejected_candidates_json = Column(JSONB, default="[]")
    chosen_schedule_id = Column(Text)
    alternatives_generated_json = Column(JSONB, default="[]")
    decision_warnings_json = Column(JSONB, default="[]")


class ContraindicationEvalTrace(Base):
    """E9. Safety evaluation audit trail."""
    __tablename__ = "contraindication_eval_trace_v1"

    trace_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    timestamp = Column(Text)
    subject_ref = Column(Text, nullable=False)
    state_id = Column(Text)
    scenario_id = Column(Text)
    action_id = Column(Text)
    rule_id = Column(Text, nullable=False)
    evaluation_result = Column(Text, nullable=False)
    severity_applied = Column(Text)
    inputs_used_json = Column(JSONB)
    missing_inputs_json = Column(JSONB, default="[]")
    action_taken = Column(Text, nullable=False)
    notes_json = Column(JSONB, default="{}")


class QuestionSelectionTrace(Base):
    """E10. VOI-based question selection audit."""
    __tablename__ = "question_selection_trace_v1"

    qtrace_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    state_id = Column(Text)
    step_index = Column(Integer, nullable=False)
    selection_stage = Column(Text, nullable=False)
    burden_budget_max = Column(Float)
    candidate_question_ids_json = Column(JSONB)
    filtered_out_json = Column(JSONB, default="[]")
    chosen_question_ids_json = Column(JSONB, nullable=False)
    prerequisite_missing_inputs_json = Column(JSONB)
    voi_method = Column(Text)
    voi_params_json = Column(JSONB)
    voi_scores_json = Column(JSONB)
    expected_decision_change_prob = Column(Float)
    predicted_rank_instability = Column(Float)
    warnings_json = Column(JSONB, default="[]")
    created_at = Column(Text, nullable=False)
    version = Column(Integer, default=1)


class ModifierEvalTrace(Base):
    """E11. Personalization audit trail."""
    __tablename__ = "modifier_eval_trace_v1"

    eval_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    state_id = Column(Text, nullable=False)
    modifier_id = Column(Text, nullable=False)
    edge_param_id = Column(Text, nullable=False)
    variable_id = Column(Text, nullable=False)
    variable_value = Column(Text, nullable=False)
    multiplier_applied = Column(Float, nullable=False)
    evidence_grade = Column(Text)
    beta_before = Column(Float, nullable=False)
    beta_after = Column(Float, nullable=False)
    se_inflation_applied = Column(Float, default=1.0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)


class QuestionSequence(Base):
    """E12. Adaptive intake record."""
    __tablename__ = "question_sequence_v1"

    sequence_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    question_id = Column(Text, nullable=False)
    sequence_position = Column(Integer, nullable=False)
    state_id_before = Column(Text, nullable=False)
    state_id_after = Column(Text, nullable=False)
    observation_model_id = Column(Text, nullable=False)
    selection_trace_id = Column(Text, nullable=False)
    response_status = Column(Text, nullable=False)
    response_value = Column(Text)
    response_z_score = Column(Float)
    variance_reduction_achieved = Column(Float)
    response_time_seconds = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  OPS TABLES — 4 tables from 007_ops_tables.sql
# ═══════════════════════════════════════════════════════════════


class ReviewTask(Base):
    """HITL review queue."""
    __tablename__ = "review_tasks"

    task_id = Column(Text, primary_key=True)
    task_type = Column(Text, nullable=False)
    source_stage = Column(Text, nullable=False)
    source_entity_id = Column(Text, nullable=False)
    source_table = Column(Text, nullable=False)
    priority = Column(Integer, default=1)
    status = Column(Text, nullable=False, default="pending")
    assigned_to = Column(Text)
    summary = Column(Text, nullable=False)
    context_json = Column(JSONB, default="{}")
    resolution = Column(Text)
    resolution_json = Column(JSONB)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime)
    notes = Column(Text)


class PolicySnapshot(Base):
    """Policy version snapshot per run."""
    __tablename__ = "policy_snapshots"

    snapshot_id = Column(Text, primary_key=True)
    run_id = Column(Text, nullable=False)
    snapshot_time = Column(DateTime, nullable=False, server_default=func.now())
    config_hash = Column(Text, nullable=False)
    table_versions_json = Column(JSONB, nullable=False)
    code_commit_hash = Column(Text)
    python_version = Column(Text)
    dependency_versions_json = Column(JSONB)
    notes = Column(Text)


class BuildManifest(Base):
    """Build provenance for compilation runs."""
    __tablename__ = "build_manifests_v1"

    build_id = Column(Text, primary_key=True)
    build_label = Column(Text, nullable=False)
    build_time = Column(DateTime, nullable=False, server_default=func.now())
    build_type = Column(Text, nullable=False)
    input_tables_json = Column(JSONB, nullable=False)
    output_tables_json = Column(JSONB, nullable=False)
    config_snapshot_id = Column(Text)
    code_commit_hash = Column(Text)
    status = Column(Text, nullable=False, default="ok")
    summary_json = Column(JSONB)
    warnings_json = Column(JSONB, default="[]")
    notes = Column(Text)
    version = Column(Integer, default=1)


# ═══════════════════════════════════════════════════════════════
#  B10-B14: New Intermediate Evidence Tables
#  SYS_EXTRACTION_ADDENDUM Part 7
# ═══════════════════════════════════════════════════════════════


class InstrumentEvidence(Base):
    """B10. Raw psychometric extractions per study.

    Written by AG11 → consumed by psychometric_compiler.
    """
    __tablename__ = "instrument_evidence_v1"

    id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    extraction_run_id = Column(Text)
    instrument_id = Column(Text)
    instrument_name = Column(Text, nullable=False)
    instrument_subscale = Column(Text)
    population_descriptor = Column(Text)
    cancer_type = Column(Text)
    treatment_phase = Column(Text)
    N = Column(Integer)
    cronbachs_alpha = Column(Float)
    se_alpha = Column(Float)
    factor_loading_mean = Column(Float)
    factor_loading_per_subscale = Column(JSONB)
    test_retest_reliability = Column(Float)
    sem_value = Column(Float)
    convergent_validity = Column(Float)
    discriminant_validity = Column(Float)
    factor_structure = Column(Text)
    measurement_invariance = Column(Text)
    provenance_status = Column(Text, default="CURATED_TRACED")
    provenance_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
    version = Column(Integer, default=1)


class PopulationNorms(Base):
    """B11. Raw population cognitive scores per study.

    Written by AG03-EXT → consumed by prior_compiler.
    """
    __tablename__ = "population_norms_v1"

    id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    extraction_run_id = Column(Text)
    cancer_type = Column(Text)
    treatment_phase = Column(Text)
    node_id = Column(Text)
    instrument_id = Column(Text)
    instrument_name = Column(Text)
    cognitive_domain = Column(Text)
    population_descriptor = Column(Text)
    mean_raw = Column(Float)
    sd_raw = Column(Float)
    mean_z = Column(Float)
    sd_z = Column(Float)
    N = Column(Integer)
    percentile = Column(Float)
    provenance_status = Column(Text, default="CURATED_TRACED")
    provenance_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
    version = Column(Integer, default=1)


class TemporalEvidence(Base):
    """B12. Raw timepoint x effect data per study.

    Written by AG08-EXT → consumed by temporal_compiler.
    """
    __tablename__ = "temporal_evidence_v1"

    id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    extraction_run_id = Column(Text)
    action_id = Column(Text)
    intervention_type = Column(Text)
    timepoint_weeks = Column(Float, nullable=False)
    effect = Column(Float)
    se = Column(Float)
    is_recovery = Column(Integer, default=0)
    N = Column(Integer)
    study_design = Column(Text)
    onset_observed = Column(Text)
    peak_observed = Column(Text)
    decay_observed = Column(Text)
    provenance_status = Column(Text, default="CURATED_TRACED")
    provenance_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
    version = Column(Integer, default=1)


class DoseEvidence(Base):
    """B13. Raw dose x effect data per study.

    Written by AG06-EXT → consumed by dose_response_compiler.
    """
    __tablename__ = "dose_evidence_v1"

    id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    extraction_run_id = Column(Text)
    action_id = Column(Text)
    intervention_type = Column(Text)
    dose_level = Column(Float, nullable=False)
    dose_unit = Column(Text)
    effect = Column(Float)
    se = Column(Float)
    N = Column(Integer)
    dose_response_shape = Column(Text)
    effective_dose_range = Column(Text)
    maximum_tolerated_dose = Column(Text)
    provenance_status = Column(Text, default="CURATED_TRACED")
    provenance_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
    version = Column(Integer, default=1)


class SubgroupEvidence(Base):
    """B14. Raw subgroup interaction data per study.

    Written by AG05-EXT → consumed by modifier_compiler.
    """
    __tablename__ = "subgroup_evidence_v1"

    id = Column(Text, primary_key=True)
    study_id = Column(Text, nullable=False)
    extraction_run_id = Column(Text)
    edge_id = Column(Text)
    modifier_variable = Column(Text, nullable=False)
    modifier_value = Column(Text, nullable=False)
    interaction_beta = Column(Float)
    interaction_se = Column(Float)
    interaction_p = Column(Float)
    subgroup_effect = Column(Float)
    subgroup_se = Column(Float)
    subgroup_n = Column(Integer)
    provenance_status = Column(Text, default="CURATED_TRACED")
    provenance_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    notes = Column(Text)
    version = Column(Integer, default=1)


class ExtractionRun(Base):
    """Per-paper extraction run tracking."""
    __tablename__ = "extraction_runs"

    extraction_run_id = Column(Text, primary_key=True)
    study_id = Column(Text)
    pdf_path = Column(Text, nullable=False)
    pdf_hash = Column(Text, nullable=False)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    ended_at = Column(DateTime)
    status = Column(Text, nullable=False, default="running")
    extraction_mode = Column(Text)
    model_id = Column(Text)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    policy_snapshot_id = Column(Text)
    stages_completed_json = Column(JSONB, default="[]")
    error_message = Column(Text)
    notes = Column(Text)


# ═══════════════════════════════════════════════════════════════
#  CLASS A EXTENSION: Search Term Reference
# ═══════════════════════════════════════════════════════════════


class NodeSearchTerm(Base):
    """A34. Search synonyms per node for automated retrieval."""
    __tablename__ = "node_search_terms_v1"

    node_id = Column(Text, primary_key=True)
    term = Column(Text, primary_key=True)
    term_type = Column(Text, nullable=False)
    active = Column(Integer, nullable=False, default=1)


# ═══════════════════════════════════════════════════════════════
#  CLASS B EXTENSION: Acquisition Queue
# ═══════════════════════════════════════════════════════════════


class AcquisitionQueue(Base):
    """B13. Operational queue for directed acquisition."""
    __tablename__ = "acquisition_queue_v1"

    queue_id = Column(Text, primary_key=True)
    candidate_doi = Column(Text)
    candidate_pmid = Column(Text)
    candidate_title = Column(Text)
    target_edge_ids_json = Column(JSONB)
    aps_score = Column(Float)
    aps_components_json = Column(JSONB)
    source_annotation_ids_json = Column(JSONB)
    retrieval_tool = Column(Text)
    status = Column(Text, nullable=False, default="queued")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())
