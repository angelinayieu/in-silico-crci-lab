-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Class D — Policy (Decision Configuration)
-- Human-curated policy choices. Define how the system decides.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- D1. objective_specs_v1 — ROOT
-- Utility function and scoring specifications for schedule
-- optimization — defines how cognitive benefit, burden, and
-- adherence are weighted in SAFE score computation (§2.16.3).
-- 1 Row = One utility function specification with burden penalty
-- lambda, adherence scaling, and severity-weighted domain weights.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE objective_specs_v1 (
    objective_id                TEXT        PRIMARY KEY,
    objective_label             TEXT,
    outcome_terms_json          JSONB,
    risk_metric                 TEXT,
    risk_aversion_lambda        REAL        DEFAULT 0.5,
    burden_weight               REAL        DEFAULT 0.7,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1,
    notes                       TEXT
);

-- ───────────────────────────────────────────────────────────────
-- D2. safety_policies_v1 — ROOT
-- System-level safety policies — trigger type -> system behavior
-- mappings that govern how the engine responds to safety-relevant
-- patient states.
-- 1 Row = One trigger type -> system behavior mapping.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE safety_policies_v1 (
    safety_policy_id            TEXT        PRIMARY KEY,
    trigger_type                TEXT        NOT NULL,
    system_behavior             TEXT        NOT NULL,
    message_template            TEXT,
    priority                    INTEGER     DEFAULT 1,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- D3. escalation_policies_v1 — ROOT
-- Escalation protocols — defines when and how the system
-- escalates beyond its scope to human clinicians.
-- 1 Row = One escalation protocol definition.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE escalation_policies_v1 (
    escalation_id               TEXT        PRIMARY KEY,
    policy_label                TEXT,
    system_behavior             TEXT        NOT NULL,
    allowed_action_classes_json JSONB,
    user_message                TEXT,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- D4. status_quo_rules_v1
-- Baseline dose assumptions — default activity levels for the
-- counterfactual 'no change' scenario in intervention comparison.
-- 1 Row = One baseline dose rule for one action.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE status_quo_rules_v1 (
    sq_rule_id                  TEXT        PRIMARY KEY,
    action_id                   TEXT        NOT NULL,
    condition_expression        TEXT,
    baseline_source_type        TEXT,
    dose_infer_spec             TEXT,
    default_dose                REAL,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- D5. voi_rules_v1
-- Value-of-information policy parameters — governs adaptive
-- question selection priorities and stopping criteria (Stage H).
-- 1 Row = One VOI policy parameter or gating rule for adaptive
-- questioning.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE voi_rules_v1 (
    voi_rule_id                 TEXT        PRIMARY KEY,
    rule_type                   TEXT        NOT NULL,
    target_ref_type             TEXT,
    target_ref_id               TEXT,
    weight_value                REAL,
    max_questions_per_session   INTEGER,
    version                     INTEGER     DEFAULT 1,
    active                      INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- D6. complexity_scaling_results_v1
-- Persists complexity-scaling validation results from §2.13.1 —
-- offline batch analysis of model stability across 4x3
-- degradation configurations.
-- 1 Row = One configuration's stability result.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE complexity_scaling_results_v1 (
    cs_id                       TEXT        PRIMARY KEY,
    horizontal_level            TEXT        NOT NULL,
    vertical_level              TEXT        NOT NULL,
    n_edges_active              INTEGER     NOT NULL,
    n_layers_active             INTEGER     NOT NULL,
    top_5_interventions_json    JSONB       NOT NULL,
    flip_rate_vs_full           REAL        NOT NULL,
    mean_beta_shift             REAL        NOT NULL,
    fragile_edges_json          JSONB,
    mc_draws                    INTEGER     NOT NULL,
    run_timestamp               TEXT        NOT NULL,
    version                     INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- D7. population_archetypes_v1
-- Population archetype definitions from §4.5. GMM-derived
-- cluster centroids and patient-to-archetype mapping.
-- 1 Row = One archetype definition (centroids and metadata).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE population_archetypes_v1 (
    archetype_id                    TEXT        PRIMARY KEY,
    archetype_label                 TEXT        NOT NULL,
    k_clusters                      INTEGER     NOT NULL,
    bic_score                       REAL        NOT NULL,
    centroid_json                   JSONB       NOT NULL,
    n_patients_assigned             INTEGER     DEFAULT 0,
    prevalence                      REAL,
    characteristic_interventions_json JSONB,
    model_version                   INTEGER     DEFAULT 1,
    active                          INTEGER     DEFAULT 1
);
