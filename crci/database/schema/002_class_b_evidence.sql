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
