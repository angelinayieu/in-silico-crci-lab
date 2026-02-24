-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Class E — Output (Session Results & Audit)
-- Append-only per session. Captures everything during engine execution.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- E6. recommendation_runs_v1
-- Run header — one row per engine execution capturing who, when,
-- what configuration, and which schedule was selected. All other
-- Class E tables reference this via run_id FK.
-- 1 Row = One engine execution session with full configuration
-- snapshot and outcome references.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE recommendation_runs_v1 (
    run_id                          TEXT        PRIMARY KEY,
    subject_ref                     TEXT        NOT NULL,
    started_at                      TEXT        NOT NULL,
    ended_at                        TEXT,
    engine_commit_hash              TEXT,
    policy_versions_json            JSONB,
    random_seed                     INTEGER     NOT NULL,
    time_step_unit                  TEXT        DEFAULT 'day',
    horizon_days                    INTEGER     DEFAULT 28,
    base_state_id                   TEXT,
    objective_spec_id               TEXT,
    safety_policy_id                TEXT,
    escalation_policy_id            TEXT,
    output_mode                     TEXT        DEFAULT 'index_mode',
    anchor_id                       TEXT,
    primary_schedule_id             TEXT,
    alternative_schedule_ids_json   JSONB       DEFAULT '[]',
    run_warnings_json               JSONB       DEFAULT '[]',
    p_rank_1_json                   JSONB,
    decision_critical_edges_json    JSONB,
    var_decomp_json                 JSONB,
    discovery_scores_json           JSONB,
    evsi_top_edges_json             JSONB,
    archetype_id                    TEXT,
    archetype_distance              REAL,
    voi_method                      TEXT
);

-- ───────────────────────────────────────────────────────────────
-- E1. state_snapshots_v1
-- Bayesian state estimates — the patient's inferred latent state
-- (mu, Sigma) after each observation update. The core runtime
-- data structure.
-- 1 Row = One patient's Bayesian state estimate at one timestamp,
-- with full posterior (information vector eta, precision diagonal).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE state_snapshots_v1 (
    state_id                        TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    subject_ref                     TEXT        NOT NULL,
    state_time                      TEXT        NOT NULL,
    time_step_unit                  TEXT        DEFAULT 'day',
    estimator_id                    TEXT,
    prior_ref_id                    TEXT,
    node_beliefs_json               JSONB       NOT NULL,
    coverage_json                   JSONB       NOT NULL DEFAULT '{}',
    conflict_flags_json             JSONB       DEFAULT '{}',
    evidence_contributions_json     JSONB       DEFAULT '[]',
    obs_used_count                  INTEGER     DEFAULT 0,
    conflict_inflation_applied      INTEGER     DEFAULT 0,
    missingness_inflation_applied   INTEGER     DEFAULT 0,
    sigma_floor_applied             INTEGER     DEFAULT 0,
    notes_json                      JSONB       DEFAULT '{}'
);

-- ───────────────────────────────────────────────────────────────
-- E2. scenario_definitions_v1
-- What-if scenario configurations — defines baseline vs
-- intervention comparisons for simulation.
-- 1 Row = One what-if scenario configuration (baseline +
-- candidate interventions).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE scenario_definitions_v1 (
    scenario_id                     TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    scenario_type                   TEXT        NOT NULL,
    scenario_label                  TEXT        NOT NULL,
    base_state_id                   TEXT        NOT NULL,
    start_date                      TEXT,
    horizon_days                    INTEGER     NOT NULL,
    time_step_unit                  TEXT        DEFAULT 'day',
    anchor_calendar_json            JSONB       DEFAULT '{}',
    generation_policy               TEXT,
    constraints_applied_json        JSONB       DEFAULT '[]',
    notes_json                      JSONB       DEFAULT '{}'
);

-- ───────────────────────────────────────────────────────────────
-- E3. scenario_items_v1
-- Actions within each scenario — the specific interventions and
-- doses being simulated.
-- 1 Row = One action within one scenario with its assigned dose.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE scenario_items_v1 (
    scenario_item_id                TEXT        PRIMARY KEY,
    scenario_id                     TEXT        NOT NULL,
    action_id                       TEXT        NOT NULL,
    dose_value                      REAL        NOT NULL,
    dose_unit                       TEXT,
    timing_plan_json                JSONB       NOT NULL,
    frequency_plan_json             JSONB       NOT NULL,
    duration_days                   INTEGER     NOT NULL,
    stop_rules_json                 JSONB       DEFAULT '[]',
    source_tag                      TEXT        NOT NULL,
    notes_json                      JSONB       DEFAULT '{}'
);

-- ───────────────────────────────────────────────────────────────
-- E4. schedule_plans_v1
-- Optimized schedule plans — the output of Stage G optimization,
-- ranked by SAFE score.
-- 1 Row = One complete optimized schedule plan with SAFE scores.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE schedule_plans_v1 (
    schedule_id                     TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    source_scenario_id              TEXT        NOT NULL,
    plan_rank                       INTEGER     DEFAULT 1,
    plan_type                       TEXT        DEFAULT 'primary',
    objective_weights_json          JSONB,
    constraints_applied_json        JSONB       DEFAULT '[]',
    expected_outcomes_json          JSONB,
    risk_summary_json               JSONB,
    utility_score                   REAL,
    rationale_json                  JSONB,
    created_at                      TEXT        NOT NULL
);

-- ───────────────────────────────────────────────────────────────
-- E5. schedule_items_v1
-- Scheduled actions within a plan — specific interventions with
-- optimized doses and timing.
-- 1 Row = One scheduled action within a plan, with
-- pathway-optimized dose and timing.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE schedule_items_v1 (
    schedule_item_id                TEXT        PRIMARY KEY,
    schedule_id                     TEXT        NOT NULL,
    action_id                       TEXT        NOT NULL,
    dose_value                      REAL        NOT NULL,
    dose_unit                       TEXT,
    timing_plan_json                JSONB       NOT NULL,
    frequency_plan_json             JSONB       NOT NULL,
    duration_days                   INTEGER     NOT NULL,
    ramp_json                       JSONB,
    stop_rules_json                 JSONB       DEFAULT '[]',
    order_index                     INTEGER     DEFAULT 0
);

-- ───────────────────────────────────────────────────────────────
-- E7. simulation_trace_v1
-- Monte Carlo simulation trace records — per-draw results for
-- provenance and decision stability analysis (§2.19).
-- 1 Row = One Monte Carlo simulation trace record (summary
-- statistics across draws for one scenario).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE simulation_trace_v1 (
    sim_trace_id                    TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    scenario_id                     TEXT        NOT NULL,
    n_samples                       INTEGER     NOT NULL,
    seed_used                       INTEGER     NOT NULL,
    edges_used_json                 JSONB       NOT NULL,
    bridges_used_json               JSONB       DEFAULT '[]',
    modifiers_applied_json          JSONB       DEFAULT '[]',
    constraint_triggers_json        JSONB       DEFAULT '[]',
    sim_warnings_json               JSONB       DEFAULT '[]'
);

-- ───────────────────────────────────────────────────────────────
-- E8. decision_trace_v1
-- Decision audit trail — every ranked decision the engine made
-- with SAFE scores, stability classification, and
-- decision-critical edges.
-- 1 Row = One decision the engine made with rationale, SAFE
-- score, and stability classification.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE decision_trace_v1 (
    decision_trace_id               TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    objective_spec_id               TEXT,
    selection_rule                  TEXT,
    candidate_scores_json           JSONB,
    rejected_candidates_json        JSONB       DEFAULT '[]',
    chosen_schedule_id              TEXT,
    alternatives_generated_json     JSONB       DEFAULT '[]',
    decision_warnings_json          JSONB       DEFAULT '[]'
);

-- ───────────────────────────────────────────────────────────────
-- E9. contraindication_eval_trace_v1
-- Safety evaluation audit trail — every safety rule evaluation
-- for every action in every scenario.
-- 1 Row = One safety rule evaluation for one action in one
-- scenario (pass/fail/modify).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE contraindication_eval_trace_v1 (
    trace_id                        TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    timestamp                       TEXT,
    subject_ref                     TEXT        NOT NULL,
    state_id                        TEXT,
    scenario_id                     TEXT,
    action_id                       TEXT,
    rule_id                         TEXT        NOT NULL,
    evaluation_result               TEXT        NOT NULL,
    severity_applied                TEXT,
    inputs_used_json                JSONB,
    missing_inputs_json             JSONB       DEFAULT '[]',
    action_taken                    TEXT        NOT NULL,
    notes_json                      JSONB       DEFAULT '{}'
);

-- ───────────────────────────────────────────────────────────────
-- E10. question_selection_trace_v1
-- VOI-based question selection audit — why each question was
-- chosen, its expected information gain, and alternatives
-- considered.
-- 1 Row = One question selection decision with VOI rationale
-- and expected variance reduction.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE question_selection_trace_v1 (
    qtrace_id                       TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    state_id                        TEXT,
    step_index                      INTEGER     NOT NULL,
    selection_stage                  TEXT        NOT NULL,
    burden_budget_max               REAL,
    candidate_question_ids_json     JSONB,
    filtered_out_json               JSONB       DEFAULT '[]',
    chosen_question_ids_json        JSONB       NOT NULL,
    prerequisite_missing_inputs_json JSONB,
    voi_method                      TEXT,
    voi_params_json                 JSONB,
    voi_scores_json                 JSONB,
    expected_decision_change_prob   REAL,
    predicted_rank_instability      REAL,
    warnings_json                   JSONB       DEFAULT '[]',
    created_at                      TEXT        NOT NULL,
    version                         INTEGER     DEFAULT 1
);

-- ───────────────────────────────────────────────────────────────
-- E11. modifier_eval_trace_v1
-- Personalization audit trail — every modifier evaluation showing
-- which patient variables adjusted which edges by how much.
-- 1 Row = One modifier evaluation for one edge x one variable x
-- one session.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE modifier_eval_trace_v1 (
    eval_id                         TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    state_id                        TEXT        NOT NULL,
    modifier_id                     TEXT        NOT NULL,
    edge_param_id                   TEXT        NOT NULL,
    variable_id                     TEXT        NOT NULL,
    variable_value                  TEXT        NOT NULL,
    multiplier_applied              REAL        NOT NULL,
    evidence_grade                  TEXT,
    beta_before                     REAL        NOT NULL,
    beta_after                      REAL        NOT NULL,
    se_inflation_applied            REAL        DEFAULT 1.0,
    created_at                      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                           TEXT
);

-- ───────────────────────────────────────────────────────────────
-- E12. question_sequence_v1
-- Adaptive intake record — every question asked and answered
-- (or skipped) in sequence, with state before/after and realized
-- information gain.
-- 1 Row = One question asked and answered (or skipped) in one
-- session, with realized variance reduction.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE question_sequence_v1 (
    sequence_id                     TEXT        PRIMARY KEY,
    run_id                          TEXT        NOT NULL,
    question_id                     TEXT        NOT NULL,
    sequence_position               INTEGER     NOT NULL,
    state_id_before                 TEXT        NOT NULL,
    state_id_after                  TEXT        NOT NULL,
    observation_model_id            TEXT        NOT NULL,
    selection_trace_id              TEXT        NOT NULL,
    response_status                 TEXT        NOT NULL,
    response_value                  TEXT,
    response_z_score                REAL,
    variance_reduction_achieved     REAL,
    response_time_seconds           REAL,
    created_at                      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes                           TEXT
);
