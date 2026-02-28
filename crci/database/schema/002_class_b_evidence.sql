-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Class B — Evidence (Extracted Study Data)
-- Append-only during extraction. Tables accumulate evidence
-- from processed papers.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- B1. study_registry_v1  (ROOT)
-- One row = one paper the system has seen.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_registry_v1 (
    study_id            TEXT        PRIMARY KEY,
    title               TEXT        NOT NULL,
    authors             TEXT,
    journal             TEXT,
    year                INTEGER,
    doi                 TEXT,
    pmid                TEXT,
    pmcid               TEXT,
    study_design        TEXT,
    notes               TEXT,
    version             INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B2. study_cohort_profiles_v1
-- One row = one cohort slice within one study.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_cohort_profiles_v1 (
    profile_id                  TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    cohort_label                TEXT,
    analysis_timepoint          TEXT,
    N_analyzed                  INTEGER,
    N_enrolled                  INTEGER,
    recruitment_region          TEXT,
    recruitment_sites           TEXT,
    collection_calendar_start   TEXT,
    collection_calendar_end     TEXT,
    enrollment_window_text      TEXT,
    eligibility_inclusion       TEXT,
    eligibility_exclusion       TEXT,
    key_exclusion_flags_json    JSONB,
    index_event_time_refs_json  JSONB,
    sex_female_pct              REAL,
    age_mean                    REAL,
    age_sd                      REAL,
    education_years_mean        REAL,
    education_years_sd          REAL,
    bmi_mean                    REAL,
    bmi_sd                      REAL,
    race_distribution_json      JSONB,
    marital_distribution_json   JSONB,
    income_distribution_json    JSONB,
    other_demographics_json     JSONB,
    cancer_context_json         JSONB,
    cancer_type                 TEXT,
    treatment_phase             TEXT,
    time_since_treatment_text   TEXT,
    analysis_context_json       JSONB,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B3. profile_data_streams_v1
-- One row = one data stream (instrument x measure) in one cohort.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profile_data_streams_v1 (
    stream_id                   TEXT        PRIMARY KEY,
    profile_id                  TEXT        NOT NULL,
    stream_label                TEXT,
    analyte_or_target           TEXT,
    modality_type               TEXT,
    capture_method              TEXT,
    instrument_id               TEXT,
    measure_id                  TEXT,
    administration_setting      TEXT,
    administration_role         TEXT,
    instrument_version          TEXT,
    language                    TEXT        DEFAULT 'EN',
    translation_status          TEXT,
    visit_context               TEXT,
    recall_window_iso           TEXT,
    schedule_pattern            TEXT,
    schedule_pattern_spec       TEXT,
    collection_time_unit        TEXT,
    scheduled_duration_value    REAL,
    timestamp_source            TEXT,
    primary_time_anchor         TEXT,
    days_collected_value        REAL,
    quality_controls_summary    TEXT,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B4. stream_timepoints_v1
-- One row = one measurement timepoint in one data stream.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stream_timepoints_v1 (
    timepoint_id                TEXT        PRIMARY KEY,
    stream_id                   TEXT        NOT NULL,
    timepoint_label             TEXT,
    timepoint_type              TEXT,
    anchor_event                TEXT,
    timepoint_minutes           INTEGER,
    clock_time_hhmm             TEXT,
    allowable_window_min        INTEGER,
    required                    INTEGER     DEFAULT 1,
    maps_to_measure             TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B5. ontology_links_v1
-- One row = one provenance link: entity exists because of study.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ontology_links_v1 (
    link_id                     TEXT        PRIMARY KEY,
    target_table                TEXT        NOT NULL,
    target_id                   TEXT        NOT NULL,
    study_id                    TEXT        NOT NULL,
    support_type                TEXT,
    evidence_strength           TEXT,
    snippet                     TEXT,
    locator                     TEXT,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B6. edge_evidence_v1  (THE main evidence store — 76 columns)
-- One row = one extracted effect estimate from one paper for one
-- edge, with full harmonization metadata.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS edge_evidence_v1 (
    ler_id                          TEXT        PRIMARY KEY,
    edge_param_id                   TEXT,
    edge_relation_id                TEXT        NOT NULL,
    profile_id                      TEXT        NOT NULL,
    study_id                        TEXT        NOT NULL,
    edge_family                     TEXT,
    node_x                          TEXT,
    node_y                          TEXT,

    -- Upstream (predictor / X) identifiers
    upstream_instrument_id          TEXT,
    upstream_stream_id              TEXT,
    upstream_raw_unit               TEXT,

    -- Downstream (outcome / Y) identifiers
    downstream_measure_id           TEXT,
    downstream_stream_id            TEXT,
    downstream_raw_unit             TEXT,

    -- Analysis model metadata
    analysis_model_family           TEXT,
    analysis_model_family_id        TEXT,
    model_family                    TEXT,
    random_effects_structure        TEXT,
    cluster_unit                    TEXT,
    se_type                         TEXT,
    predictor_level                 TEXT,
    centered_level                  TEXT,
    centering_method                TEXT,
    centering_note                  TEXT,

    -- Outcome component and time definitions
    outcome_component               TEXT,
    time_metric_definition          TEXT,
    CAR_definition                  TEXT,
    time_unit_x                     TEXT,
    time_unit_y                     TEXT,

    -- Transforms
    x_transform                     TEXT,
    y_transform                     TEXT,

    -- Temporal alignment
    alignment_type                  TEXT,
    alignment_type_id               TEXT,
    alignment_lag_days              INTEGER,
    alignment_note                  TEXT,

    -- Reported effect estimates
    effect_type_reported            TEXT        NOT NULL,
    effect_value_reported           REAL        NOT NULL,
    se_reported                     REAL,
    ci_low_reported                 REAL,
    ci_high_reported                REAL,
    p_value                         REAL,
    sd_x                            REAL,
    sd_y                            REAL,
    N_effect                        INTEGER     NOT NULL,

    -- Subgroup and adjustment
    subgroup_label                  TEXT,
    covariates_adjusted             TEXT,
    adjustment_selection_method     TEXT,

    -- Harmonization
    harmonization_status            TEXT        DEFAULT 'unreviewed',
    harmonized_scale                TEXT,
    harmonized_beta                 REAL,
    harmonized_se                   REAL,
    blocked_reason                  TEXT,
    harmonization_rule_id           TEXT,

    -- Interaction / moderation
    interaction_reported            INTEGER     DEFAULT 0,
    interaction_variable_id         TEXT,
    interaction_variable_raw        TEXT,
    moderator_definition            TEXT,
    interaction_beta                REAL,
    interaction_se                  REAL,
    subgroup_beta_M0                REAL,
    subgroup_se_M0                  REAL,
    subgroup_beta_M1                REAL,
    subgroup_se_M1                  REAL,
    interaction_effect_reported     TEXT,

    -- Quality and audit
    quality_rating                  TEXT        DEFAULT 'moderate',
    extraction_snippet              TEXT,
    entered_by                      TEXT,
    entered_at                      TEXT,
    version                         INTEGER     DEFAULT 1,
    active                          INTEGER     DEFAULT 1,

    -- Risk-of-bias and causal identification
    rob_tool                        TEXT,
    rob_overall                     TEXT,
    estimand_class                  TEXT,
    identification_status           TEXT,

    -- Meta-analysis provenance
    parent_meta_study_id            TEXT,

    -- v2.0: MA multi-product and effect size classification (Eng. Appendix §A.2)
    meta_source_flag                TEXT,
    heterogeneity_json              TEXT,
    effect_size_type                TEXT,

    -- v2.0: SE derivation cascade (CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4)
    se_derivation_level             TEXT,
    se_inflation_applied            REAL        DEFAULT 1.0,
    se_quality_tag                  TEXT,

    -- v2.0: Conversion provenance (CONVERSION_VALIDITY_AND_HARDENING.md R4)
    conversion_formula              TEXT,
    conversion_bias_risk            TEXT,

    -- v2.0: Shared control & dependency (CONVERSION_VALIDITY_AND_HARDENING.md Module 4)
    shared_control_flag             INTEGER     DEFAULT 0,
    shared_control_study_id         TEXT,
    endpoint_vs_change              TEXT,
    comparison_arm_label            TEXT,

    -- v2.0: Verification escalation (CONVERSION_VALIDITY_AND_HARDENING.md Module 2)
    verification_tier               TEXT        DEFAULT 'TIER_3',
    verification_status             TEXT        DEFAULT 'UNVERIFIED',
    escalation_rules_json           TEXT,
    escalation_se_inflation         REAL        DEFAULT 1.0,

    -- v2.0: Freshness provenance (CONVERSION_VALIDITY_AND_HARDENING.md Module 5)
    parameter_family                TEXT,
    freshness_w                     REAL,
    freshness_superseded            INTEGER     DEFAULT 0,

    -- v2.1: Idempotent evidence writes (PERSISTENCE_FIX_CHANGELOG.md S3)
    span_hash                       TEXT,

    -- v2.2: Study-level metadata (migration 013 — template alignment)
    study_design                    TEXT,
    cancer_type                     TEXT,
    treatment_phase                 TEXT,
    pub_year                        INTEGER,
    cancer_validation_status        TEXT,
    n_treatment                     INTEGER,
    n_control                       INTEGER,

    -- v2.3: P2–P7 pipeline columns (migration 014 — wiring audit)
    outcome_type                    TEXT        DEFAULT 'semi_objective',
    scope_weights_json              TEXT        DEFAULT '{}',
    se_eff                          REAL,
    se_layer_details_json           TEXT,

    notes                           TEXT
);

-- ───────────────────────────────────────────────────────────────
-- B7. edge_param_builds_v1
-- One row = one aggregation build step from evidence to compiled
-- edge parameters. Audit trail for provenance tracing.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS edge_param_builds_v1 (
    build_id                        TEXT        PRIMARY KEY,
    build_label                     TEXT,
    build_time                      TEXT,
    build_version                   INTEGER     DEFAULT 1,
    code_commit_hash                TEXT,
    input_scope_spec_json           JSONB,
    evidence_query_spec_json        JSONB,
    harmonization_rule_ids_json     JSONB,
    aggregation_policy              TEXT,
    selection_policy_spec_json      JSONB,
    timing_policy                   TEXT,
    timing_prior_ids_json           JSONB,
    outputs_edge_param_ids_json     JSONB,
    outputs_summary_json            JSONB,
    warnings_json                   JSONB,
    status                          TEXT        DEFAULT 'ok',
    notes                           TEXT,
    active                          INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B8. triangulation_evidence_v1
-- One row = one cross-method agreement result from a paper for a
-- triangulable construct.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS triangulation_evidence_v1 (
    tri_ev_id                       TEXT        PRIMARY KEY,
    triangulation_id                TEXT        NOT NULL,
    profile_id                      TEXT,
    scope_json                      JSONB,
    agreement_scope                 TEXT,
    member_a_order                  INTEGER,
    member_b_order                  INTEGER,
    agreement_metric                TEXT,
    agreement_value                 REAL,
    agreement_ci_low                REAL,
    agreement_ci_high               REAL,
    N_agreement                     INTEGER,
    p_value                         REAL,
    evidence_origin                 TEXT,
    source_study_id                 TEXT,
    page_or_table                   TEXT,
    notes                           TEXT,
    version                         INTEGER     DEFAULT 1,
    active                          INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B9. pathway_biomarkers_v1
-- One row = one biomarker linked to one pathway with loading
-- coefficient and evidence source.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pathway_biomarkers_v1 (
    pb_id                           TEXT        PRIMARY KEY,
    pathway_id                      TEXT        NOT NULL,
    node_id                         TEXT        NOT NULL,
    measure_id                      TEXT        NOT NULL,
    indicator_type                  TEXT        NOT NULL,
    loading_coefficient             REAL        NOT NULL,
    loading_se                      REAL        NOT NULL,
    source_study_id                 TEXT        NOT NULL,
    source_ler_id                   TEXT,
    sample_matrix                   TEXT        NOT NULL,
    assay_caveat                    TEXT,
    version                         INTEGER     DEFAULT 1,
    active                          INTEGER     DEFAULT 1,
    notes                           TEXT
);

-- ═══════════════════════════════════════════════════════════════
-- B10-B14. NEW INTERMEDIATE EVIDENCE TABLES
-- SYS_EXTRACTION_ADDENDUM Part 7: Raw extracted values BEFORE
-- compilation. Compilers read from these and write to Class A.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- B10. instrument_evidence_v1
-- One row = one psychometric property for one instrument from
-- one study. Written by AG11 → consumed by psychometric_compiler.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrument_evidence_v1 (
    id                          TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    extraction_run_id           TEXT,
    instrument_id               TEXT,
    instrument_name             TEXT        NOT NULL,
    instrument_subscale         TEXT,
    population_descriptor       TEXT,
    cancer_type                 TEXT,
    treatment_phase             TEXT,
    N                           INTEGER,
    cronbachs_alpha             REAL,
    se_alpha                    REAL,
    factor_loading_mean         REAL,
    factor_loading_per_subscale JSONB,
    test_retest_reliability     REAL,
    sem_value                   REAL,
    convergent_validity         REAL,
    discriminant_validity       REAL,
    factor_structure            TEXT,
    measurement_invariance      TEXT,
    provenance_status           TEXT        DEFAULT 'CURATED_TRACED',
    provenance_ref              TEXT,
    created_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B11. population_norms_v1
-- One row = one population cognitive score for one domain from
-- one study. Written by AG03-EXT → consumed by prior_compiler.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS population_norms_v1 (
    id                          TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    extraction_run_id           TEXT,
    cancer_type                 TEXT,
    treatment_phase             TEXT,
    node_id                     TEXT,
    instrument_id               TEXT,
    instrument_name             TEXT,
    cognitive_domain            TEXT,
    population_descriptor       TEXT,
    mean_raw                    REAL,
    sd_raw                      REAL,
    mean_z                      REAL,
    sd_z                        REAL,
    N                           INTEGER,
    percentile                  REAL,
    provenance_status           TEXT        DEFAULT 'CURATED_TRACED',
    provenance_ref              TEXT,
    created_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B12. temporal_evidence_v1
-- One row = one timepoint × effect pair from one study.
-- Written by AG08-EXT → consumed by temporal_compiler.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS temporal_evidence_v1 (
    id                          TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    extraction_run_id           TEXT,
    action_id                   TEXT,
    intervention_type           TEXT,
    timepoint_weeks             REAL        NOT NULL,
    effect                      REAL,
    se                          REAL,
    is_recovery                 INTEGER     DEFAULT 0,
    N                           INTEGER,
    study_design                TEXT,
    onset_observed              TEXT,
    peak_observed               TEXT,
    decay_observed              TEXT,
    provenance_status           TEXT        DEFAULT 'CURATED_TRACED',
    provenance_ref              TEXT,
    created_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B13. dose_evidence_v1
-- One row = one dose × effect pair from one study.
-- Written by AG06-EXT → consumed by dose_response_compiler.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dose_evidence_v1 (
    id                          TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    extraction_run_id           TEXT,
    action_id                   TEXT,
    intervention_type           TEXT,
    dose_level                  REAL        NOT NULL,
    dose_unit                   TEXT,
    effect                      REAL,
    se                          REAL,
    N                           INTEGER,
    dose_response_shape         TEXT,
    effective_dose_range        TEXT,
    maximum_tolerated_dose      TEXT,
    provenance_status           TEXT        DEFAULT 'CURATED_TRACED',
    provenance_ref              TEXT,
    created_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- B14. subgroup_evidence_v1
-- One row = one subgroup interaction from one study for one edge.
-- Written by AG05-EXT → consumed by modifier_compiler.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subgroup_evidence_v1 (
    id                          TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    extraction_run_id           TEXT,
    edge_id                     TEXT,
    modifier_variable           TEXT        NOT NULL,
    modifier_value              TEXT        NOT NULL,
    interaction_beta            REAL,
    interaction_se              REAL,
    interaction_p               REAL,
    subgroup_effect             REAL,
    subgroup_se                 REAL,
    subgroup_n                  INTEGER,
    provenance_status           TEXT        DEFAULT 'CURATED_TRACED',
    provenance_ref              TEXT,
    created_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                       TEXT,
    version                     INTEGER     DEFAULT 1
);


-- ───────────────────────────────────────────────────────────────
-- E13. extraction_audit_v1  (evidence-related audit trail)
-- One row = one extraction stage execution for one paper.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extraction_audit_v1 (
    audit_id                        TEXT        PRIMARY KEY,
    study_id                        TEXT        NOT NULL,
    pipeline_stage                  TEXT        NOT NULL,
    agent_id                        TEXT,
    status                          TEXT        NOT NULL,
    records_input                   INTEGER     NOT NULL DEFAULT 0,
    records_output                  INTEGER     NOT NULL DEFAULT 0,
    records_rejected                INTEGER     NOT NULL DEFAULT 0,
    rejection_reasons_json          JSONB,
    quality_flags_json              JSONB,
    execution_time_seconds          REAL        NOT NULL DEFAULT 0,
    llm_tokens_used                 INTEGER,
    deterministic_parser_used       INTEGER     DEFAULT 0,
    created_at                      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operator_id                     TEXT,
    notes                           TEXT
);


-- ───────────────────────────────────────────────────────────────
-- B13. acquisition_queue_v1
-- Purpose: Operational queue for directed acquisition.
--          Tracks candidate papers through the retrieval lifecycle.
-- SYS_EXTRACTION_COMPLETE.md lines 2635-2655
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS acquisition_queue_v1 (
    queue_id                        TEXT        PRIMARY KEY,
    candidate_doi                   TEXT,
    candidate_pmid                  TEXT,
    candidate_title                 TEXT,
    target_edge_ids_json            JSONB,
    aps_score                       REAL,
    aps_components_json             JSONB,
    source_annotation_ids_json      JSONB,
    retrieval_tool                  TEXT,
    status                          TEXT        NOT NULL DEFAULT 'queued',
    created_at                      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);
