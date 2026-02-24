-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Class C — Compiled (Aggregated Parameters)
-- Recomputed from Class A + B. Never manually edited.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- C1. edges_v1 — THE KEY TABLE
-- Compiled edge parameters (pooled beta, SE, grade, inclusion
-- probability) produced by the aggregation pipeline from
-- edge_evidence_v1. Read by virtually all algorithm stages.
-- 1 Row = One compiled edge parameter: pooled effect size with
-- seven-layer SE, evidence grade, and structural inclusion
-- probability.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE edges_v1 (
    edge_param_id               TEXT        PRIMARY KEY,
    edge_relation_id            TEXT        NOT NULL,
    measure_id                  TEXT,
    effect_scale                TEXT,
    effect_direction            INTEGER,
    beta_mean                   REAL        NOT NULL,
    beta_se                     REAL,
    beta_dist_family            TEXT        DEFAULT 'normal',
    ci_low                      REAL,
    ci_high                     REAL,
    aggregation_method          TEXT,
    evidence_level              TEXT,
    cancer_type                 TEXT,
    treatment_phase             TEXT,
    scope_filters_json          JSONB       DEFAULT '{}',
    time_step_unit              TEXT        DEFAULT 'day',
    temporal_family             TEXT,
    lag_steps                   INTEGER     DEFAULT 0,
    half_life_steps             REAL,
    timing_source               TEXT,
    timing_source_ref           TEXT,
    time_scale_compat_mode      TEXT        DEFAULT 'native_step',
    baseline_modifier_mode      TEXT        DEFAULT 'none',
    baseline_modifier_spec_json JSONB,
    constraint_rule_ids_json    JSONB       DEFAULT '[]',
    specificity_rank            INTEGER     DEFAULT 0,
    supporting_ler_ids          TEXT,
    active                      INTEGER     DEFAULT 1,
    version                     INTEGER     DEFAULT 1,
    i_squared                   REAL,
    tau_squared                 REAL,
    total_n                     INTEGER,
    notes                       TEXT,
    pub_bias_risk               TEXT,
    se_inflation_pub_bias       REAL        DEFAULT 1.0,
    coherence_flag              TEXT,
    se_inflation_coherence      REAL        DEFAULT 1.0,
    e_value                     REAL,
    robustness_value            REAL
);

-- ───────────────────────────────────────────────────────────────
-- C2. dose_bridges_v1
-- Dose-to-effect bridge mappings — translates intervention dose
-- units into standardized z-score effects on target nodes.
-- Implements Emax/Hill models from §2.6.
-- 1 Row = One dose-to-effect bridge mapping an action's dose to
-- a node effect via Emax/Hill function parameters.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE dose_bridges_v1 (
    bridge_id                   TEXT        PRIMARY KEY,
    action_id                   TEXT        NOT NULL,
    output_mode                 TEXT        NOT NULL,
    output_feature_id           TEXT,
    output_node_id              TEXT,
    maps_to_node_id             TEXT,
    dose_type                   TEXT,
    dose_unit                   TEXT,
    dose_min                    REAL        DEFAULT 0,
    dose_max                    REAL,
    dose_step                   REAL,
    dose_reference              REAL        NOT NULL,
    dose_response_family        TEXT        NOT NULL,
    dose_response_params_json   JSONB,
    bridge_effect_sign          INTEGER     NOT NULL,
    bridge_gain                 REAL        NOT NULL,
    bridge_noise_sd             REAL,
    time_step_unit              TEXT        DEFAULT 'day',
    temporal_family             TEXT        DEFAULT 'delta',
    lag_steps                   INTEGER     DEFAULT 0,
    half_life_steps             REAL,
    scope_json                  JSONB       DEFAULT '{}',
    provenance                  TEXT        NOT NULL,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- C3. node_priors_v1
-- Scoped prior distributions for each node — context-matched
-- (cancer type x treatment phase) with four-level fallback
-- hierarchy (§2.8).
-- 1 Row = One scoped prior distribution (mu, sigma) for one node
-- in one clinical context.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE node_priors_v1 (
    prior_id                    TEXT        PRIMARY KEY,
    node_id                     TEXT        NOT NULL,
    prior_space                 TEXT        DEFAULT 'z',
    mean                        REAL        NOT NULL DEFAULT 0.0,
    sd                          REAL        NOT NULL DEFAULT 1.0,
    dist_family                 TEXT        DEFAULT 'normal',
    cancer_type                 TEXT,
    treatment_phase             TEXT,
    scope_filters_json          JSONB       DEFAULT '{}',
    specificity_rank            INTEGER     DEFAULT 0,
    provenance                  TEXT,
    active                      INTEGER     DEFAULT 1,
    version                     INTEGER     DEFAULT 1,
    notes                       TEXT
);

-- ───────────────────────────────────────────────────────────────
-- C4. outcome_anchors_v1
-- Calibration anchors mapping z-scores to clinically
-- interpretable scales — implements the six-tier severity
-- classification from §2.20.
-- 1 Row = One calibration anchor: z-score threshold -> severity
-- tier -> percentile -> clinical interpretation.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE outcome_anchors_v1 (
    anchor_id                   TEXT        PRIMARY KEY,
    target_level                TEXT        NOT NULL,
    target_id                   TEXT        NOT NULL,
    calibration_family          TEXT        NOT NULL,
    calibration_params_json     JSONB       NOT NULL,
    scope_cancer_type           TEXT,
    scope_treatment_phase       TEXT,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1,
    notes                       TEXT
);

-- ───────────────────────────────────────────────────────────────
-- C5. state_estimator_specs_v1 — ROOT
-- Configuration for the Bayesian state estimation engine (§2.8)
-- — specifies estimator variant, temporal decay rate, prior
-- fallback hierarchy, and fusion level settings.
-- 1 Row = One estimator configuration specification.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE state_estimator_specs_v1 (
    estimator_id                    TEXT        PRIMARY KEY,
    estimator_family                TEXT        NOT NULL,
    update_space                    TEXT        DEFAULT 'node_z',
    min_sigma_floor                 REAL        DEFAULT 0.2,
    max_sigma_cap                   REAL        DEFAULT 5.0,
    conflict_inflation_family       TEXT        DEFAULT 'multiplicative_sd',
    conflict_inflation_params_json  JSONB,
    missingness_inflation_family    TEXT        DEFAULT 'additive_var',
    missingness_inflation_params_json JSONB,
    core_coverage_policy            TEXT        DEFAULT 'require_safety_coverage',
    required_nodes_json             JSONB,
    admissibility_filters_json      JSONB,
    noise_fallback_policy           TEXT        DEFAULT 'conservative_default',
    default_noise_params_json       JSONB,
    independence_assumption         INTEGER     DEFAULT 1,
    version                         INTEGER     DEFAULT 1,
    active                          INTEGER     DEFAULT 1,
    notes                           TEXT
);

-- ───────────────────────────────────────────────────────────────
-- C6. chain_validation_results_v1
-- Persists chain-vs-direct validation results from §2.13 —
-- Z-scores, triage tiers, AV scores, discrepancy
-- classifications, and SE inflation feedback per testable
-- pathway.
-- 1 Row = One pathway's chain-vs-direct comparison result.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE chain_validation_results_v1 (
    cv_id                       TEXT        PRIMARY KEY,
    pathway_id                  TEXT        NOT NULL,
    chain_length                INTEGER     NOT NULL,
    edges_in_chain_json         JSONB,
    beta_chain                  REAL        NOT NULL,
    se_chain                    REAL        NOT NULL,
    beta_direct                 REAL,
    se_direct                   REAL,
    z_statistic                 REAL,
    triage_tier                 TEXT        NOT NULL,
    av_score                    REAL,
    failure_mode                TEXT,
    remediation                 TEXT,
    se_inflation_applied        REAL        DEFAULT 1.0,
    build_id                    TEXT,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- C7. publication_bias_results_v1
-- Persists publication bias assessment results per edge from
-- §2.12.1 — Egger regression, trim-and-fill, leave-one-out,
-- and overall risk classification.
-- 1 Row = One edge's publication bias assessment.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE publication_bias_results_v1 (
    pb_result_id                TEXT        PRIMARY KEY,
    edge_param_id               TEXT        NOT NULL,
    k_studies                   INTEGER     NOT NULL,
    egger_intercept             REAL,
    egger_p_value               REAL,
    egger_significant           BOOLEAN,
    n_trimmed                   INTEGER,
    beta_adjusted_tf            REAL,
    loo_max_shift               REAL,
    loo_influential_json        JSONB,
    bias_risk                   TEXT        NOT NULL,
    se_inflation_pub_bias       REAL        DEFAULT 1.0,
    build_id                    TEXT,
    version                     INTEGER     DEFAULT 1
);
