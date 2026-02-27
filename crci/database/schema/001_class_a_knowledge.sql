-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Class A — Knowledge (Domain Definitions)
-- Human-curated at design time. Versioned.
-- Tables: 33 tables defining causal structure, measurements,
--         safety rules, pathway specifications.
-- ═══════════════════════════════════════════════════════════════
--
-- Dependency order: ROOT tables first, then tables with FK dependencies.
-- No FK CONSTRAINT clauses in this file (those go in 006_fk_constraints.sql).
-- All PKs are TEXT (not SERIAL). Enums are TEXT (application-enforced).
-- JSONB for structured JSON columns. REAL for floats. INTEGER for ints.
--
-- ROOT tables (no FK dependencies):
--   A3  biomarker_node_definitions_v1
--   A6  harmonization_rules_v1
--   A12 contraindication_escalation_policy_v1
--   A20 description_templates_v1
--   A21 action_catalog_v1
--   A29 recovery_trajectories_v1
--   A33 mid_thresholds_v1
--
-- Then dependent tables in topological order.
-- ═══════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- A3. biomarker_node_definitions_v1 (ROOT)
-- Purpose: Defines every node (biomarker, construct, cognitive domain)
--          in the 63-node causal DAG. The ROOT reference table for the
--          entire system.
-- 1 Row = One node in the causal graph.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE biomarker_node_definitions_v1 (
    node_id                         TEXT        NOT NULL,
    node_label                      TEXT        NOT NULL,
    node_symbol                     TEXT,
    node_role                       TEXT        NOT NULL,  -- {context, exposure, mediator, symptom, cognition, outcome, composite}
    orientation                     TEXT        NOT NULL,  -- {higher_worse, higher_better, neutral}
    node_domain                     TEXT        NOT NULL,  -- {sleep, exercise, hpa_axis, inflammation, autonomic, neurotrophic, cognition, fatigue, mood, treatment, demographic, other}
    node_subtype                    TEXT,
    default_state_space             TEXT        NOT NULL,  -- {z, raw, probability, 0_1}
    state_update_scale              TEXT        NOT NULL,  -- {static, daily, weekly, monthly, study_window}
    default_window_days             INTEGER,
    min_observation_window_days     INTEGER,
    allowed_source_types_json       JSONB       NOT NULL,  -- array of {instrument, measure, derived_feature, node}
    is_actionable_input_node        INTEGER     NOT NULL,  -- {0,1} treated as boolean
    active                          INTEGER     NOT NULL,  -- {0,1} treated as boolean
    version                         INTEGER     NOT NULL,
    description                     TEXT        NOT NULL,
    notes                           TEXT,
    PRIMARY KEY (node_id)
);

COMMENT ON TABLE biomarker_node_definitions_v1 IS
    'A3: ROOT. Defines every node in the 63-node causal DAG — biomarkers, constructs, cognitive domains.';


-- ───────────────────────────────────────────────────────────────
-- A6. harmonization_rules_v1 (ROOT)
-- Purpose: Deterministic conversion formulas for transforming
--          heterogeneous effect sizes to a common SMD scale.
-- 1 Row = One validated conversion formula.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE harmonization_rules_v1 (
    rule_id                     TEXT        NOT NULL,
    effect_type_reported        TEXT        NOT NULL,  -- {std_beta, unstd_beta, OR, RR, group_diff, other}
    x_transform_required        TEXT        NOT NULL,  -- {none, log, z, any}
    y_transform_required        TEXT        NOT NULL,  -- {none, log, z, any}
    required_fields             TEXT        NOT NULL,  -- comma-separated column tokens
    output_scale                TEXT        NOT NULL,  -- {SD_SD, PROXY_PER_SD, LOGOR_PER_SD, RAW_PER_SD}
    conversion_family           TEXT        NOT NULL,  -- {unstd_beta_to_proxy_per_sd, std_beta_to_sd_sd, or_to_logor_per_sd, ...}
    conversion_notes            TEXT,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (rule_id)
);

COMMENT ON TABLE harmonization_rules_v1 IS
    'A6: ROOT. Deterministic conversion formulas for effect size harmonization (OR→SMD, r→d, HR→OR, etc.).';


-- ───────────────────────────────────────────────────────────────
-- A12. contraindication_escalation_policy_v1 (ROOT)
-- Purpose: Defines escalation behaviors when a contraindication
--          trigger fires (block, warn, modify dose, refer).
-- 1 Row = One escalation behavior for a contraindication severity class.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE contraindication_escalation_policy_v1 (
    escalation_id                   TEXT        NOT NULL,
    policy_label                    TEXT        NOT NULL,
    system_behavior                 TEXT        NOT NULL,  -- {block_all_actions, block_action_classes, allow_only_low_burden, require_clinician_review}
    allowed_action_classes_json     TEXT,                   -- JSON array (nullable)
    user_message                    TEXT,
    version                         INTEGER     NOT NULL,
    active                          INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (escalation_id)
);

COMMENT ON TABLE contraindication_escalation_policy_v1 IS
    'A12: ROOT. Escalation behaviors when contraindication triggers fire.';


-- ───────────────────────────────────────────────────────────────
-- A20. description_templates_v1 (ROOT)
-- Purpose: Text templates for consistent UI rendering of
--          recommendations, warnings, severity descriptions.
-- 1 Row = One text template for a specific output context.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE description_templates_v1 (
    template_id         TEXT        NOT NULL,
    template_label      TEXT        NOT NULL,
    template_scope      TEXT        NOT NULL,  -- {node, edge, action, instrument, measure, feature, ...}
    template_text       TEXT        NOT NULL,
    version             INTEGER     NOT NULL,
    active              INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (template_id)
);

COMMENT ON TABLE description_templates_v1 IS
    'A20: ROOT. Text templates for consistent UI rendering (recommendations, warnings, severity labels).';


-- ───────────────────────────────────────────────────────────────
-- A21. action_catalog_v1 (ROOT)
-- Purpose: Defines every atomic intervention the engine may recommend.
--          Central intervention reference table with dose domains,
--          burden priors, and adherence priors.
-- 1 Row = One atomic action with dose domain [min, max, step].
-- ───────────────────────────────────────────────────────────────
CREATE TABLE action_catalog_v1 (
    action_id                   TEXT        NOT NULL,
    action_label                TEXT        NOT NULL,
    action_class                TEXT        NOT NULL,  -- {sleep, physical_activity, light_exposure, stress_regulation, nutrition, medication_support_nonrx, cognitive_training, social_engagement}
    dose_type                   TEXT        NOT NULL,  -- {continuous, ordinal, binary}
    dose_unit                   TEXT,
    dose_semantics              TEXT        NOT NULL,
    dose_min                    REAL        NOT NULL,
    dose_max                    REAL        NOT NULL,
    dose_recommended_start      REAL        NOT NULL,
    dose_step                   REAL,
    time_cost_min_default       REAL        NOT NULL,
    cognitive_load_default      REAL        NOT NULL,
    logistics_load_default      REAL        NOT NULL,
    overall_burden_default      REAL,
    adherence_rate_default      REAL,
    evidence_basis              TEXT        NOT NULL,  -- {direct_intervention, mechanistic_only, guideline_derived, mixed}
    evidence_strength           TEXT        NOT NULL,  -- {strong, moderate, weak}
    notes                       TEXT,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (action_id)
);

COMMENT ON TABLE action_catalog_v1 IS
    'A21: ROOT. Every atomic intervention the engine may recommend, with dose domains, burden, and adherence priors.';


-- ───────────────────────────────────────────────────────────────
-- A29. recovery_trajectories_v1 (ROOT)
-- Purpose: Natural recovery parameters per treatment context —
--          stretched exponential parameters (r_inf, tau_R, gamma_R)
--          and accelerated cognitive aging coefficients.
-- 1 Row = One treatment-context-specific recovery trajectory.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE recovery_trajectories_v1 (
    trajectory_id       TEXT        NOT NULL,
    cancer_type         TEXT        NOT NULL,  -- {breast, colorectal, hematological, lung, any}
    regimen_class       TEXT        NOT NULL,
    r_infinity          REAL        NOT NULL,
    r_infinity_se       REAL        NOT NULL,
    tau_r_months        REAL        NOT NULL,
    tau_r_se            REAL        NOT NULL,
    gamma_r             REAL        NOT NULL,
    acc_factor          REAL        NOT NULL,
    source_citation     TEXT        NOT NULL,
    version             INTEGER     NOT NULL,
    notes               TEXT,
    PRIMARY KEY (trajectory_id)
);

COMMENT ON TABLE recovery_trajectories_v1 IS
    'A29: ROOT. Stretched exponential recovery parameters and ACC factors per treatment context (§2.18).';


-- ───────────────────────────────────────────────────────────────
-- A33. mid_thresholds_v1 (ROOT)
-- Purpose: Minimally Important Difference thresholds per cognitive
--          domain. Clinical anchors for severity classification
--          and dose optimization ceiling.
-- 1 Row = One cognitive domain MID threshold set.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE mid_thresholds_v1 (
    domain_id           TEXT        NOT NULL,
    d_mid               REAL        NOT NULL,
    d_ce                REAL        NOT NULL,
    d_plateau           REAL        NOT NULL,
    anchor_source       TEXT        NOT NULL,
    anchor_method       TEXT        NOT NULL,  -- {distribution_based, anchor_based, expert_consensus}
    version             INTEGER     NOT NULL,
    active              INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (domain_id)
);

COMMENT ON TABLE mid_thresholds_v1 IS
    'A33: ROOT. MID thresholds per cognitive domain for severity classification and dose optimization ceiling (§2.20.2).';


-- ═══════════════════════════════════════════════════════════════
-- DEPENDENT TABLES (Level 1: depend only on ROOT tables)
-- ═══════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- A1. edge_relations_definitions_v1
-- Purpose: Defines every permitted causal edge in the DAG.
--          Backbone ontology from which edges_v1 is compiled.
-- FK: node_x, node_y → biomarker_node_definitions_v1.node_id
-- 1 Row = One permitted causal edge (source→target→mechanism).
-- ───────────────────────────────────────────────────────────────
CREATE TABLE edge_relations_definitions_v1 (
    edge_relation_id                TEXT        NOT NULL,
    module                          TEXT        NOT NULL,  -- {A, B, C, D}
    edge_family                     TEXT        NOT NULL,
    node_x                          TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    node_y                          TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    relation_label                  TEXT        NOT NULL,
    canonical_statement             TEXT        NOT NULL,
    relation_type                   TEXT        NOT NULL,  -- {causal, associational, mechanistic, hypothesized}
    default_effect_direction        INTEGER     NOT NULL,  -- {+1, -1}
    allowed_measure_ids_json        TEXT,                   -- JSON array of measure_id (nullable)
    allowed_upstream_instruments_json TEXT,                  -- JSON array of instrument_id (nullable)
    default_temporal_family         TEXT,                   -- {delta, exponential} (nullable)
    notes                           TEXT,
    version                         INTEGER     NOT NULL,
    active                          INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (edge_relation_id)
);

COMMENT ON TABLE edge_relations_definitions_v1 IS
    'A1: Defines every permitted causal edge in the DAG (source→target→mechanism). FK to biomarker_node_definitions_v1.';


-- ───────────────────────────────────────────────────────────────
-- A4. instrument_definitions_v1
-- Purpose: Defines every clinical assessment instrument with
--          psychometric properties, loading factors, reliability,
--          and cancer-validation status.
-- FK: maps_to_node_id → biomarker_node_definitions_v1.node_id
-- 1 Row = One assessment instrument.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE instrument_definitions_v1 (
    instrument_id                   TEXT        NOT NULL,
    instrument_label                TEXT        NOT NULL,
    maps_to_node_id                 TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    instrument_kind                 TEXT        NOT NULL,  -- {questionnaire, diary, clinician_scale, cognitive_test, other}
    instrument_method               TEXT        NOT NULL,  -- {self_report, clinician_rated, objectively_administered, hybrid}
    recall_window_days              INTEGER,
    time_aggregation                TEXT        NOT NULL,  -- {momentary, daily, weekly, monthly, study_window, other}
    raw_scale_spec                  TEXT        NOT NULL,
    raw_unit                        TEXT        NOT NULL,
    higher_means_pre_alignment      TEXT        NOT NULL,  -- {worse, better, mixed, context}
    direction_rule_id               TEXT        NOT NULL,
    directionality_after_alignment  TEXT        NOT NULL,  -- {higher_worse, higher_better, neutral, context}
    adapter_output_kind             TEXT        NOT NULL,  -- {z, dist_gaussian, dist_other}
    adapter_spec_id                 TEXT,
    required_fields_json            JSONB       NOT NULL,
    thresholds_json                 JSONB,
    preferred_norm_ref_id           TEXT,       -- FK → normalization_refs_v1.norm_id (hint)
    preferred_noise_id              TEXT,       -- FK → observation_noise_v1.noise_id (hint)
    compatibility_group_id          TEXT,
    active                          INTEGER     NOT NULL,  -- {0,1}
    version                         INTEGER     NOT NULL,
    description                     TEXT        NOT NULL,
    notes                           TEXT,
    PRIMARY KEY (instrument_id)
);

COMMENT ON TABLE instrument_definitions_v1 IS
    'A4: Every clinical assessment instrument with psychometric properties and cancer-validation status (§2.7).';


-- ───────────────────────────────────────────────────────────────
-- A5. measure_definitions_v1
-- Purpose: Defines every biomarker, wearable metric, and proxy
--          measurement type with assay specs and node mappings.
-- FK: maps_to_node_id → biomarker_node_definitions_v1.node_id
-- 1 Row = One biomarker/wearable/proxy measurement type.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE measure_definitions_v1 (
    measure_id                      TEXT        NOT NULL,
    measure_label                   TEXT        NOT NULL,
    maps_to_node_id                 TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    measure_kind                    TEXT        NOT NULL,  -- {biomarker, wearable, clinical_lab, imaging, other}
    analyte                         TEXT,                   -- {cortisol, il6, crp, tnfa, bdnf, other} (nullable)
    specimen_or_device              TEXT        NOT NULL,
    biospecimen                     TEXT,                   -- {saliva, blood, plasma, serum, urine, other, none} (nullable)
    device_type                     TEXT,                   -- {actigraphy, smartwatch_ppg, ring, eeg, other} (nullable)
    proxy_type                      TEXT        NOT NULL,  -- {level, intercept, slope, quadratic_slope, CAR, AUC, bedtime, awakening, composite, other}
    time_aggregation                TEXT        NOT NULL,  -- {momentary, diurnal, 24h, daily, weekly, monthly, study_window, other}
    raw_unit                        TEXT        NOT NULL,
    value_transform_spec            TEXT,                   -- {none, log, ln, zscore, rank, other} (nullable)
    direction_rule_id               TEXT        NOT NULL,
    directionality_after_alignment  TEXT        NOT NULL,  -- {higher_worse, higher_better, neutral, context}
    measure_family_id               TEXT        NOT NULL,
    compatibility_group_id          TEXT        NOT NULL,
    effective_window_days           INTEGER,
    min_required_samples            INTEGER,
    required_fields_json            JSONB       NOT NULL,
    preferred_norm_ref_id           TEXT,       -- FK → normalization_refs_v1.norm_id (hint)
    preferred_noise_id              TEXT,       -- FK → observation_noise_v1.noise_id (hint)
    active                          INTEGER     NOT NULL,  -- {0,1}
    version                         INTEGER     NOT NULL,
    description                     TEXT        NOT NULL,
    notes                           TEXT,
    PRIMARY KEY (measure_id)
);

COMMENT ON TABLE measure_definitions_v1 IS
    'A5: Every biomarker, wearable metric, and proxy measurement type with assay specs and node mappings.';


-- ───────────────────────────────────────────────────────────────
-- A10. contraindication_rules_v1
-- Purpose: Defines every safety rule with trigger predicates.
-- FK: escalation_id → contraindication_escalation_policy_v1.escalation_id
-- 1 Row = One safety rule with trigger condition and response.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE contraindication_rules_v1 (
    rule_id                     TEXT        NOT NULL,
    rule_label                  TEXT        NOT NULL,
    applies_to_type             TEXT        NOT NULL,  -- {global, action_class, action_id}
    applies_to_ref              TEXT,                   -- nullable (NULL if global)
    severity                    TEXT        NOT NULL,  -- {hard_block, soft_penalty, require_question, escalate}
    condition_expression        TEXT        NOT NULL,
    required_inputs_json        TEXT        NOT NULL,  -- JSON array
    unknown_input_policy        TEXT        NOT NULL,  -- {treat_as_false, treat_as_true, trigger_question, escalate}
    penalty_spec_json           TEXT,                   -- JSON object (nullable, only for soft_penalty)
    escalation_id               TEXT,                   -- FK → contraindication_escalation_policy_v1.escalation_id (nullable)
    rationale                   TEXT        NOT NULL,
    provenance                  TEXT,
    tags_json                   TEXT,                   -- JSON array (nullable)
    created_by                  TEXT,
    created_at                  TEXT,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (rule_id)
);

COMMENT ON TABLE contraindication_rules_v1 IS
    'A10: Every safety rule with trigger predicates, severity, and prescribed responses for action gating.';


-- ───────────────────────────────────────────────────────────────
-- A13. validation_rules_v1
-- Purpose: Cross-table validation contracts — FK integrity checks,
--          range constraints, cross-column consistency rules.
-- 1 Row = One validation check applicable to a table or relationship.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE validation_rules_v1 (
    rule_id                     TEXT        NOT NULL,
    rule_label                  TEXT        NOT NULL,
    target_table                TEXT        NOT NULL,
    target_column               TEXT,
    rule_type                   TEXT        NOT NULL,  -- {fk_integrity, range_check, cross_column_consistency, cross_table_consistency, enum_membership, json_schema}
    severity                    TEXT        NOT NULL,  -- {error, warning}
    enforcement_point           TEXT        NOT NULL,  -- {etl_commit, runtime_read, unit_test, all}
    condition_expression        TEXT        NOT NULL,
    required_inputs_json        TEXT        NOT NULL,  -- JSON array
    error_message_template      TEXT        NOT NULL,
    depends_on_tables_json      TEXT,                   -- JSON array (nullable)
    priority                    INTEGER     NOT NULL,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (rule_id)
);

COMMENT ON TABLE validation_rules_v1 IS
    'A13: Cross-table validation contracts — FK integrity, range checks, consistency rules. Enforcement-only table.';


-- ───────────────────────────────────────────────────────────────
-- A14. variable_definitions_v1
-- Purpose: Defines every patient variable that can modify edge
--          parameters (109-rule effect modifier stack, §2.15).
-- FK: polymorphic via source_ref_id to nodes or features
-- 1 Row = One patient characteristic affecting model predictions.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE variable_definitions_v1 (
    variable_id             TEXT        NOT NULL,
    variable_label          TEXT        NOT NULL,
    variable_description    TEXT        NOT NULL,
    variable_domain         TEXT        NOT NULL,  -- {demographic, treatment, behavior, symptom, physiology, other}
    variable_type           TEXT        NOT NULL,  -- {binary, ordinal, continuous, categorical}
    allowed_values_json     TEXT,                   -- JSON array (required iff categorical/ordinal)
    unit                    TEXT,                   -- required iff continuous
    value_range             TEXT,                   -- required iff continuous
    source_namespace        TEXT        NOT NULL,  -- {context, feature, node, derived}
    source_ref_id           TEXT,                   -- context.<key> or FEAT_* or NODE_*
    missingness_policy      TEXT        NOT NULL,  -- {block, ask_question, set_unknown, default}
    default_value           TEXT,                   -- required iff missingness_policy=default
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (variable_id)
);

COMMENT ON TABLE variable_definitions_v1 IS
    'A14: Every patient variable that can multiplicatively adjust edge parameters (§2.15 modifier stack).';


-- ───────────────────────────────────────────────────────────────
-- A26. pathways_v1
-- Purpose: Defines the 15 mechanistic + 5 clinical mediator
--          pathways from §2.3.
-- FK: entry/exit/intermediate nodes → biomarker_node_definitions_v1;
--     edge_relation_ids → edge_relations_definitions_v1 (via JSON)
-- 1 Row = One biological/behavioral pathway.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE pathways_v1 (
    pathway_id                          TEXT        NOT NULL,
    pathway_label                       TEXT        NOT NULL,
    tier                                TEXT        NOT NULL,  -- {mechanistic_model_implied, mechanistic_emerging, mechanistic_placeholder, clinical_mediator}
    entry_node_ids_json                 JSONB       NOT NULL,
    exit_node_ids_json                  JSONB       NOT NULL,
    intermediate_node_ids_json          JSONB       NOT NULL,
    edge_relation_ids_json              JSONB       NOT NULL,
    cognitive_domain_specificity_json   JSONB       NOT NULL,
    best_proxy_biomarker                TEXT,       -- FK → biomarker_node_definitions_v1.node_id (nullable)
    proxy_r_squared                     REAL,
    causal_evidence_level               TEXT        NOT NULL,  -- {causal_demonstrated, strong_association, moderate_association, plausible}
    key_citation                        TEXT        NOT NULL,
    version                             INTEGER     NOT NULL,
    active                              INTEGER     NOT NULL,  -- {0,1}
    notes                               TEXT,
    PRIMARY KEY (pathway_id)
);

COMMENT ON TABLE pathways_v1 IS
    'A26: The 15 mechanistic + 5 clinical mediator pathways with node chains and evidence tiers (§2.3).';


-- ───────────────────────────────────────────────────────────────
-- A30. biomarker_correlations_v1
-- Purpose: Correlated mediator pairs with empirical rho for
--          the block-diagonal D matrix (§2.6, §2.17.2).
-- FK: node_a_id, node_b_id → biomarker_node_definitions_v1.node_id
-- 1 Row = One correlated biomarker pair.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE biomarker_correlations_v1 (
    correlation_id          TEXT        NOT NULL,
    node_a_id               TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id (canonical: a < b)
    node_b_id               TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    rho                     REAL        NOT NULL,
    rho_se                  REAL,
    d_block                 TEXT        NOT NULL,  -- {inflammatory, neuro_stress, independent}
    source_citation         TEXT        NOT NULL,
    is_decision_critical    INTEGER     NOT NULL,  -- {0,1}
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (correlation_id)
);

COMMENT ON TABLE biomarker_correlations_v1 IS
    'A30: Correlated mediator pairs with empirical rho for block-diagonal D matrix (§2.6, §2.17.2).';


-- ───────────────────────────────────────────────────────────────
-- A31. feedback_loops_v1
-- Purpose: Defines the 5 feedback structures in the DAG (§2.11)
--          with loop edges, gain, period, and stability properties.
-- FK (via JSON): edge_relation_ids → edge_relations_definitions_v1;
--                node_ids → biomarker_node_definitions_v1;
--                breaking_intervention → action_catalog_v1
-- 1 Row = One feedback loop with edge chain and loop gain.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE feedback_loops_v1 (
    loop_id                         TEXT        NOT NULL,
    loop_label                      TEXT        NOT NULL,
    edge_relation_ids_json          JSONB       NOT NULL,
    node_ids_json                   JSONB       NOT NULL,
    loop_gain                       REAL        NOT NULL,
    characteristic_period_weeks     TEXT        NOT NULL,
    forward_dynamics                TEXT        NOT NULL,
    reverse_dynamics                TEXT        NOT NULL,
    breaking_intervention           TEXT,       -- FK → action_catalog_v1.action_id (nullable)
    spectral_radius_contribution    REAL,
    version                         INTEGER     NOT NULL,
    notes                           TEXT,
    PRIMARY KEY (loop_id)
);

COMMENT ON TABLE feedback_loops_v1 IS
    'A31: The 5 feedback structures in the DAG with loop gain, characteristic period, and stability properties (§2.11).';


-- ───────────────────────────────────────────────────────────────
-- A32. intervention_kernels_v1
-- Purpose: Per-intervention temporal kernels with onset, build,
--          steady-state, and decay parameters (§2.11).
-- FK: action_id → action_catalog_v1.action_id
-- 1 Row = One temporal kernel for one intervention.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE intervention_kernels_v1 (
    kernel_id                       TEXT        NOT NULL,
    action_id                       TEXT        NOT NULL,  -- FK → action_catalog_v1.action_id
    kernel_family                   TEXT        NOT NULL,  -- {delta, exponential, step, gamma, biexponential, saturation, adaptation, trapezoidal}
    onset_weeks_min                 REAL        NOT NULL,
    onset_weeks_max                 REAL        NOT NULL,
    build_weeks                     REAL        NOT NULL,
    steady_state_weeks_min          REAL        NOT NULL,
    steady_state_weeks_max          REAL        NOT NULL,
    decay_half_life_weeks           REAL        NOT NULL,
    pathway_specific_onset_json     JSONB,
    source_citation                 TEXT        NOT NULL,
    version                         INTEGER     NOT NULL,
    active                          INTEGER     NOT NULL,  -- {0,1}
    notes                           TEXT,
    PRIMARY KEY (kernel_id)
);

COMMENT ON TABLE intervention_kernels_v1 IS
    'A32: Per-intervention temporal kernels — onset, build, steady-state, decay parameters (§2.11).';


-- ═══════════════════════════════════════════════════════════════
-- DEPENDENT TABLES (Level 2: depend on Level-1 tables)
-- ═══════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- A2. edge_ontology_v1
-- Purpose: Operational constraints for each edge type — conversions,
--          functional forms, and sign conventions.
-- FK: edge_relation_id → edge_relations_definitions_v1.edge_relation_id
-- 1 Row = One set of operational constraints for one edge relation.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE edge_ontology_v1 (
    ontology_id                     TEXT        NOT NULL,
    edge_relation_id                TEXT        NOT NULL,  -- FK → edge_relations_definitions_v1.edge_relation_id
    binary_outcome_bridge_allowed   INTEGER     NOT NULL,  -- {0,1} boolean
    proxy_mapping_policy            TEXT        NOT NULL,  -- {strict_match, family_match, any}
    allowed_scales_json             TEXT        NOT NULL,  -- JSON array
    estimand_compatibility_rules    TEXT        NOT NULL,
    allowed_temporal_families_json  TEXT        NOT NULL,  -- JSON array
    max_lag_steps                   INTEGER,
    aggregation_constraints_json    TEXT        NOT NULL,  -- JSON object
    version                         INTEGER     NOT NULL,
    active                          INTEGER     NOT NULL,  -- {0,1}
    notes                           TEXT,
    PRIMARY KEY (ontology_id)
);

COMMENT ON TABLE edge_ontology_v1 IS
    'A2: Operational constraints per edge type — allowed conversions, functional forms, sign conventions.';


-- ───────────────────────────────────────────────────────────────
-- A7. predictor_alignment_rules_v1
-- Purpose: Alignment rules for matching study cohort characteristics
--          to the target population (Layer 2 transportability, §2.9).
-- FK: profile_id → study_cohort_profiles_v1 (Class B);
--     outcome_measure_id → measure_definitions_v1.measure_id
-- 1 Row = One alignment rule for a cohort dimension.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE predictor_alignment_rules_v1 (
    align_id                TEXT        NOT NULL,
    profile_id              TEXT        NOT NULL,  -- FK → study_cohort_profiles_v1.profile_id
    predictor_ref_type      TEXT        NOT NULL,  -- {instrument, feature}
    predictor_ref_id        TEXT        NOT NULL,
    outcome_measure_id      TEXT        NOT NULL,  -- FK → measure_definitions_v1.measure_id
    alignment_type          TEXT        NOT NULL,  -- {same_day, prior_day, prior_week, rolling_window, custom}
    lag_days                INTEGER     NOT NULL,
    window_spec             TEXT,                   -- required iff rolling_window/custom
    notes                   TEXT,
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    PRIMARY KEY (align_id)
);

COMMENT ON TABLE predictor_alignment_rules_v1 IS
    'A7: Alignment rules for matching cohort characteristics to target population (Layer 2 transportability, §2.9).';


-- ───────────────────────────────────────────────────────────────
-- A8. literary_mechanistic_priors_v1
-- Purpose: Literature-informed prior distributions for edges
--          with sparse direct evidence (§2.10).
-- FK: study_id → study_registry_v1 (Class B, provenance)
-- 1 Row = One prior distribution specification with provenance.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE literary_mechanistic_priors_v1 (
    prior_id                TEXT        NOT NULL,
    prior_label             TEXT        NOT NULL,
    prior_type              TEXT        NOT NULL,  -- {applicability, sign_constraint, bound, shape, latency, context_split, quality_guardrail}
    target_level            TEXT        NOT NULL,  -- {node, edge_family, edge_id, feature_id, pipeline}
    target_ref              TEXT        NOT NULL,
    condition_spec          TEXT        NOT NULL,
    effect_on_pipeline      TEXT        NOT NULL,  -- {allow, downweight, block, flip_sign, cap_magnitude, set_latency, set_phase_scope, require_stratification}
    strength                TEXT        NOT NULL,  -- {hard, soft}
    prior_params            TEXT,
    evidence_basis          TEXT        NOT NULL,  -- {human_clinical, human_observational, human_experimental, in_vitro, animal, mixed, theory}
    study_id                TEXT,                   -- FK → study_registry_v1.study_id (nullable)
    population_scope        TEXT        NOT NULL,  -- {breast, colorectal, lung, mixed, all}
    phase_scope             TEXT        NOT NULL,  -- {active_chemo, post_treatment, mixed, all}
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (prior_id)
);

COMMENT ON TABLE literary_mechanistic_priors_v1 IS
    'A8: Literature-informed prior distributions for edges with sparse direct evidence (§2.10).';


-- ───────────────────────────────────────────────────────────────
-- A9. literary_constraints_v1
-- Purpose: Biological bounds on node trajectories — physiological
--          ceilings, rate limits, floor constraints preventing
--          impossible simulation states (§2.12 Step 4).
-- FK: applies_to_measure_id → measure_definitions_v1;
--     study_id → study_registry_v1 (provenance)
-- 1 Row = One biological constraint on a node or edge trajectory.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE literary_constraints_v1 (
    rule_id                     TEXT        NOT NULL,
    rule_label                  TEXT        NOT NULL,
    rule_type                   TEXT        NOT NULL,  -- {bound, gate, timecourse, validity_scope, consistency}
    strength                    TEXT        NOT NULL,  -- {hard, soft}
    applies_to_node             TEXT,
    applies_to_measure_id       TEXT,                   -- FK → measure_definitions_v1.measure_id
    applies_to_aux_variable     TEXT,
    regime                      TEXT        NOT NULL,  -- {acute, chronic, post_event, baseline, all}
    phase_scope                 TEXT        NOT NULL,  -- {active_chemo, post_treatment, mixed, all}
    population_scope            TEXT        NOT NULL,  -- {breast, colorectal, lung, mixed, all}
    trigger_inputs_required     TEXT,
    rule_spec                   TEXT        NOT NULL,
    effect_on_engine            TEXT        NOT NULL,  -- {clip, reject, reweight, mask, annotate}
    output_target               TEXT        NOT NULL,  -- {node_state, measure_value, aux_variable, edge_activation}
    output_scale                TEXT        NOT NULL,  -- {z, raw, 0_1, minutes, days, json}
    output_range                TEXT,
    missingness_policy          TEXT        NOT NULL,  -- {block, soft_default, assume_false, assume_true, set_null}
    default_behavior            TEXT,
    priority                    TEXT        NOT NULL,  -- {core, optional, experimental}
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    study_id                    TEXT,
    notes                       TEXT,
    PRIMARY KEY (rule_id)
);

COMMENT ON TABLE literary_constraints_v1 IS
    'A9: Biological bounds on node trajectories — ceilings, rate limits, floor constraints (§2.12 Step 4).';


-- ───────────────────────────────────────────────────────────────
-- A11. action_contraindication_links_v1
-- Purpose: Join table linking specific actions to safety rules.
-- FK: action_id → action_catalog_v1.action_id;
--     rule_id → contraindication_rules_v1.rule_id
-- 1 Row = One link between an action and a contraindication rule.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE action_contraindication_links_v1 (
    link_id                     TEXT        NOT NULL,
    action_id                   TEXT        NOT NULL,  -- FK → action_catalog_v1.action_id
    rule_id                     TEXT        NOT NULL,  -- FK → contraindication_rules_v1.rule_id
    override_mode               TEXT,                   -- {none, strengthen, weaken, disable} (nullable)
    scope_constraints_json      TEXT,                   -- JSON object (nullable)
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (link_id)
);

COMMENT ON TABLE action_contraindication_links_v1 IS
    'A11: Join table linking specific actions to the safety rules that apply to them.';


-- ───────────────────────────────────────────────────────────────
-- A15. variable_to_input_map_v1
-- Purpose: Maps patient intake form fields to engine variables.
-- FK: variable_id → variable_definitions_v1.variable_id
-- 1 Row = One mapping from patient input field to engine variable.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE variable_to_input_map_v1 (
    map_id                  TEXT        NOT NULL,
    variable_id             TEXT        NOT NULL,  -- FK → variable_definitions_v1.variable_id
    input_token             TEXT        NOT NULL,
    transform               TEXT        NOT NULL,  -- {none, clip, log, log10, zscore, bin, threshold_map}
    transform_params_json   TEXT,                   -- JSON object (nullable, required iff transform needs params)
    precedence_rank         INTEGER     NOT NULL,
    required_inputs_json    TEXT        NOT NULL,  -- JSON array
    missing_input_policy    TEXT        NOT NULL,  -- {ask_question, set_unknown, default, block}
    default_value           TEXT,                   -- required iff missing_input_policy=default
    validity_check          TEXT,
    scope_json              TEXT,                   -- JSON object (nullable)
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (map_id)
);

COMMENT ON TABLE variable_to_input_map_v1 IS
    'A15: Maps patient intake form fields to engine variables — translation layer between UI and model parameters.';


-- ───────────────────────────────────────────────────────────────
-- A16. baseline_modifier_definitions_v1
-- Purpose: Defines how patient variables multiplicatively adjust
--          edge parameters — modifier functions with evidence grades
--          and guardrails [0.5, 2.0] (§2.15).
-- FK: required_variable_ids_json → variable_definitions_v1 (via JSON);
--     source_ler_ids → edge_evidence_v1 (via semicolon list)
-- 1 Row = One modifier definition.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE baseline_modifier_definitions_v1 (
    modifier_id                 TEXT        NOT NULL,
    modifier_label              TEXT        NOT NULL,
    modifier_description        TEXT        NOT NULL,
    support_class               TEXT        NOT NULL,  -- {quantitative, gate_only, variance_only}
    evidence_required           INTEGER     NOT NULL,  -- {0,1}
    source_ler_ids              TEXT,                   -- semicolon-separated LER IDs (nullable)
    required_variable_ids_json  TEXT        NOT NULL,  -- JSON array of VAR_*
    applies_to                  TEXT        NOT NULL,  -- {beta, lag, half_life, gate}
    parameterization_mode       TEXT        NOT NULL,  -- {multiplicative, additive, set_to, delta_steps}
    effect_spec_json            TEXT        NOT NULL,  -- JSON object
    bounds_json                 TEXT,                   -- JSON object (nullable)
    missing_input_policy        TEXT        NOT NULL,  -- {ask_question, set_unknown, no_effect, block}
    conflict_input_policy       TEXT        NOT NULL,  -- {prefer_state, prefer_feature, inflate_uncertainty, no_effect}
    scope_json                  TEXT,                   -- JSON object (nullable)
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (modifier_id)
);

COMMENT ON TABLE baseline_modifier_definitions_v1 IS
    'A16: How patient variables multiplicatively adjust edge parameters with evidence grades (§2.15).';


-- ───────────────────────────────────────────────────────────────
-- A17. derived_feature_definitions_v1
-- Purpose: Defines every computed feature — formulas, dependency
--          chains, normalization, and timing windows for derived
--          clinical variables.
-- FK: normalization_reference → normalization_refs_v1 (hint);
--     maps_to_node → biomarker_node_definitions_v1.node_id
-- 1 Row = One computed feature definition.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE derived_feature_definitions_v1 (
    feature_id                  TEXT        NOT NULL,
    feature_label               TEXT        NOT NULL,
    feature_description         TEXT        NOT NULL,
    maps_to_node                TEXT,       -- FK → biomarker_node_definitions_v1.node_id (nullable)
    mapped_nodes_json           TEXT        NOT NULL,  -- JSON array of node_id
    feature_domain              TEXT        NOT NULL,  -- {demographic, treatment, behavior, symptom, perception, physiology, immune, neuro, biomarker, outcome, diagnostic, qa, other}
    feature_role                TEXT        NOT NULL,  -- {state_input, state_estimation, prediction, recommendation, diagnostic, qa}
    feature_type                TEXT        NOT NULL,  -- {status, composite, interaction, trend, variability, flag, quality_metric, cluster_code, other}
    feature_source              TEXT        NOT NULL,  -- {observed_only, derived_only, hybrid}
    dependency_ids              TEXT        NOT NULL,  -- semicolon-separated IDs
    dependency_types            TEXT        NOT NULL,  -- semicolon-separated {instrument, measure, feature, node}
    time_window                 TEXT        NOT NULL,  -- {momentary, daily, weekly, monthly, study_window, custom}
    time_window_spec            TEXT,
    normalization_method        TEXT        NOT NULL,  -- {none, within_user, within_study, external_norm}
    normalization_reference     TEXT,       -- NORM_* key or rule key
    formula_spec                TEXT        NOT NULL,
    sign_alignment              TEXT        NOT NULL,  -- {as_is, flip_to_match_node, custom}
    directionality              TEXT        NOT NULL,  -- {higher_worse, higher_better, neutral, context}
    output_scale                TEXT        NOT NULL,  -- {z, raw, 0_1, ordinal, count, minutes, probability, text, other}
    output_unit                 TEXT        NOT NULL,
    valid_range                 TEXT        NOT NULL,
    threshold_spec              TEXT,
    missingness_policy          TEXT        NOT NULL,  -- {drop_row, feature_impute, row_impute, set_null}
    imputation_spec             TEXT,
    compute_priority            TEXT        NOT NULL,  -- {core, optional, experimental}
    compute_stage               TEXT        NOT NULL,  -- {intake, preprocess, state_estimation, postprocess, qa}
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (feature_id)
);

COMMENT ON TABLE derived_feature_definitions_v1 IS
    'A17: Every computed feature with formula, dependency chain, normalization, and timing window specifications.';


-- ───────────────────────────────────────────────────────────────
-- A18. triangulation_sets_v1
-- Purpose: Defines which measurements should be fused for each
--          latent construct — configuration for Stage B triangulation.
-- FK: target_node_id → biomarker_node_definitions_v1.node_id;
--     output_feature_id → derived_feature_definitions_v1.feature_id
-- 1 Row = One triangulation group for a latent construct.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE triangulation_sets_v1 (
    triangulation_id        TEXT        NOT NULL,
    triangulation_label     TEXT        NOT NULL,
    target_node_id          TEXT        NOT NULL,  -- FK → biomarker_node_definitions_v1.node_id
    triangulation_scope     TEXT        NOT NULL,  -- {within_construct}
    triangulation_goal      TEXT        NOT NULL,  -- {state_estimation, qa, both}
    fusion_policy           TEXT        NOT NULL,  -- {none, weighted_average, gaussian_precision_fusion, rule_based}
    conflict_policy         TEXT        NOT NULL,  -- {flag_only, recommend_downweight, block_update}
    conflict_metric         TEXT        NOT NULL,  -- {weighted_dispersion, sign_disagreement, both}
    min_members_required    INTEGER     NOT NULL,
    output_feature_id       TEXT,       -- FK → derived_feature_definitions_v1.feature_id (nullable)
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (triangulation_id)
);

COMMENT ON TABLE triangulation_sets_v1 IS
    'A18: Which measurements fuse for each latent construct — Stage B triangulation configuration.';


-- ───────────────────────────────────────────────────────────────
-- A22. question_bank_v1
-- Purpose: Every question the adaptive intake system can ask,
--          with VOI parameters, observation model links, and
--          presentation metadata.
-- FK: observation_model_id → question_observation_models_v1.model_id
-- 1 Row = One question with information value parameters.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE question_bank_v1 (
    question_id                 TEXT        NOT NULL,
    question_label              TEXT        NOT NULL,
    question_text               TEXT        NOT NULL,
    question_role               TEXT        NOT NULL,  -- {safety_gate, baseline_intake, adaptive_profile, monitoring, calibration}
    answer_type                 TEXT        NOT NULL,  -- {binary, ordinal, integer, real, multi_select, text, date, time}
    answer_unit                 TEXT,
    answer_options_json         TEXT,                   -- JSON array/object (nullable)
    validation_min              REAL,
    validation_max              REAL,
    validation_rule_spec        TEXT,
    maps_to_type                TEXT        NOT NULL,  -- {context_key, feature_id, node_id, variable_id}
    maps_to_ref                 TEXT        NOT NULL,
    observation_model_id        TEXT,       -- FK → question_observation_models_v1.model_id (nullable)
    time_window                 TEXT        NOT NULL,  -- {momentary, daily, weekly, monthly, study_window, custom}
    time_window_spec            TEXT,
    applicability_scope_json    TEXT,                   -- JSON object (nullable)
    prerequisite_inputs_json    TEXT,                   -- JSON array (nullable)
    missing_answer_policy       TEXT        NOT NULL,  -- {skip, retry, set_unknown, escalate}
    burden_time_min             REAL        NOT NULL,
    burden_cognitive            REAL        NOT NULL,
    burden_invasiveness         REAL        NOT NULL,
    ask_frequency_policy        TEXT        NOT NULL,  -- {once, periodic, on_change, custom}
    ask_frequency_spec          TEXT,
    provenance                  TEXT,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (question_id)
);

COMMENT ON TABLE question_bank_v1 IS
    'A22: Every question the adaptive intake system can ask with VOI parameters and observation model links.';


-- ───────────────────────────────────────────────────────────────
-- A24. normalization_refs_v1
-- Purpose: Population reference statistics (mean, SD, percentiles)
--          for z-score normalization of instruments, measures,
--          and derived features (§2.1).
-- FK: polymorphic via target_entity_id;
--     source_study_id → study_registry_v1 (Class B)
-- 1 Row = One population reference for normalizing one entity.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE normalization_refs_v1 (
    norm_id                 TEXT        NOT NULL,
    target_entity_type      TEXT        NOT NULL,  -- {instrument, measure, feature}
    target_entity_id        TEXT        NOT NULL,  -- polymorphic FK → INST_*/MEAS_*/FEAT_*
    population_label        TEXT        NOT NULL,
    cancer_type             TEXT        NOT NULL,  -- {breast, lung, colorectal, hematological, mixed_solid, general_population, any}
    treatment_phase         TEXT        NOT NULL,  -- {pre_treatment, during_treatment, early_post, late_post, survivorship, any}
    ref_mean                REAL        NOT NULL,
    ref_sd                  REAL        NOT NULL,
    ref_n                   INTEGER     NOT NULL,
    percentile_5            REAL,
    percentile_25           REAL,
    percentile_50           REAL,
    percentile_75           REAL,
    percentile_95           REAL,
    source_study_id         TEXT,       -- FK → study_registry_v1.study_id (nullable)
    source_citation         TEXT        NOT NULL,
    year_published          INTEGER,
    is_cancer_specific      INTEGER     NOT NULL,  -- {0,1}
    version                 INTEGER     NOT NULL,
    notes                   TEXT,
    PRIMARY KEY (norm_id)
);

COMMENT ON TABLE normalization_refs_v1 IS
    'A24: Population reference statistics (mean, SD, percentiles) for z-score normalization (§2.1).';


-- ───────────────────────────────────────────────────────────────
-- A25. observation_noise_v1
-- Purpose: Measurement noise and reliability parameters for all
--          measurement entities. Implements sigma_y^2 = b^2(1-alpha)/alpha
--          from §2.7 and cancer-validation SE multipliers.
-- FK: polymorphic via target_entity_id;
--     source_study_id → study_registry_v1 (Class B)
-- 1 Row = One noise/reliability specification for one entity.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE observation_noise_v1 (
    noise_id                    TEXT        NOT NULL,
    target_entity_type          TEXT        NOT NULL,  -- {instrument, measure, feature, question}
    target_entity_id            TEXT        NOT NULL,  -- polymorphic FK → INST_*/MEAS_*/FEAT_*/Q_*
    reliability_alpha           REAL,
    noise_variance              REAL        NOT NULL,
    noise_source                TEXT        NOT NULL,  -- {psychometric, test_retest, icc, estimated, default}
    cancer_validation_status    TEXT        NOT NULL,  -- {validated_cancer, used_cancer, general_population, known_somatic_confound}
    se_multiplier               REAL        NOT NULL,  -- {1.0, 1.15, 1.3, 1.5}
    proxy_r_squared             REAL,
    proxy_caveat                TEXT,
    source_study_id             TEXT,       -- FK → study_registry_v1.study_id (nullable)
    source_citation             TEXT        NOT NULL,
    condition_dependent         INTEGER     NOT NULL,  -- {0,1}
    condition_description       TEXT,
    version                     INTEGER     NOT NULL,
    active                      INTEGER     NOT NULL,  -- {0,1}
    notes                       TEXT,
    PRIMARY KEY (noise_id)
);

COMMENT ON TABLE observation_noise_v1 IS
    'A25: Measurement noise and reliability parameters. Implements sigma_y^2 = b^2(1-alpha)/alpha (§2.7).';


-- ───────────────────────────────────────────────────────────────
-- A27. pathway_interactions_v1
-- Purpose: Interactions between pathway pairs — feed-forward,
--          convergence, antagonistic relationships.
-- FK: pathway_a_id, pathway_b_id → pathways_v1.pathway_id
-- 1 Row = One pathway-pair interaction.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE pathway_interactions_v1 (
    interaction_id          TEXT        NOT NULL,
    pathway_a_id            TEXT        NOT NULL,  -- FK → pathways_v1.pathway_id (canonical: a < b)
    pathway_b_id            TEXT        NOT NULL,  -- FK → pathways_v1.pathway_id
    interaction_type        TEXT        NOT NULL,  -- {feed_forward, convergent, antagonistic, independent}
    interaction_strength    REAL        NOT NULL,
    directionality          TEXT        NOT NULL,  -- {bidirectional, a_to_b, b_to_a}
    shared_nodes_json       JSONB,
    mechanism_description   TEXT        NOT NULL,
    key_citation            TEXT        NOT NULL,
    version                 INTEGER     NOT NULL,
    active                  INTEGER     NOT NULL,  -- {0,1}
    notes                   TEXT,
    PRIMARY KEY (interaction_id)
);

COMMENT ON TABLE pathway_interactions_v1 IS
    'A27: Interactions between pathway pairs — feed-forward, convergent, and antagonistic relationships.';


-- ───────────────────────────────────────────────────────────────
-- A28. intervention_synergy_v1
-- Purpose: Pairwise intervention interaction records with JPO, CCS,
--          and gamma prior parameters (§2.16.1).
-- FK: action_a_id, action_b_id → action_catalog_v1.action_id;
--     source_study_id → study_registry_v1 (Class B)
-- 1 Row = One pairwise intervention interaction.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE intervention_synergy_v1 (
    synergy_id              TEXT        NOT NULL,
    action_a_id             TEXT        NOT NULL,  -- FK → action_catalog_v1.action_id (canonical: a < b)
    action_b_id             TEXT        NOT NULL,  -- FK → action_catalog_v1.action_id
    jpo                     REAL        NOT NULL,
    ccs                     REAL        NOT NULL,
    interaction_type        TEXT        NOT NULL,  -- {synergistic, additive, antagonistic}
    interaction_magnitude   REAL,
    gamma_prior_alpha       REAL        NOT NULL,
    gamma_prior_beta        REAL        NOT NULL,
    gamma_cap               REAL        NOT NULL,
    source_study_id         TEXT,       -- FK → study_registry_v1.study_id (nullable)
    validation_status       TEXT        NOT NULL,  -- {validated, partially_validated, not_tested}
    version                 INTEGER     NOT NULL,
    notes                   TEXT,
    PRIMARY KEY (synergy_id)
);

COMMENT ON TABLE intervention_synergy_v1 IS
    'A28: Pairwise intervention synergy records with JPO, CCS, and gamma prior parameters (§2.16.1).';


-- ═══════════════════════════════════════════════════════════════
-- DEPENDENT TABLES (Level 3: depend on Level-2 tables)
-- ═══════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- A19. triangulation_members_v1
-- Purpose: Which variables belong to each triangulation set —
--          membership with weights and reliability for fusion.
-- FK: triangulation_id → triangulation_sets_v1.triangulation_id;
--     member_entity_id → derived_feature_definitions_v1 (polymorphic)
-- 1 Row = One member in a triangulation set.
-- PK: (triangulation_id, member_order) composite
-- ───────────────────────────────────────────────────────────────
CREATE TABLE triangulation_members_v1 (
    triangulation_id        TEXT        NOT NULL,  -- FK → triangulation_sets_v1.triangulation_id
    member_order            INTEGER     NOT NULL,
    member_entity_type      TEXT        NOT NULL,  -- {feature}
    member_entity_id        TEXT        NOT NULL,  -- FK → derived_feature_definitions_v1.feature_id
    member_role             TEXT        NOT NULL,  -- {primary, secondary, auxiliary}
    weight_kind             TEXT        NOT NULL,  -- {auto_equal, manual_weight, inverse_variance, reliability_prior, none}
    weight_value            REAL,
    required_for_tri_set    INTEGER     NOT NULL,  -- {0,1}
    admissibility_qc_gate   TEXT,                   -- {allow, require_qc_pass} (nullable)
    notes                   TEXT,
    PRIMARY KEY (triangulation_id, member_order)
);

COMMENT ON TABLE triangulation_members_v1 IS
    'A19: Membership list for triangulation sets with fusion weights and reliability specifications.';


-- ───────────────────────────────────────────────────────────────
-- A23. question_observation_models_v1
-- Purpose: Maps question answers to node/feature updates —
--          observation model connecting adaptive questionnaire
--          to Bayesian state estimation.
-- FK: question_id → question_bank_v1.question_id;
--     output_ref_id → polymorphic (FEAT_* or NODE_*)
-- 1 Row = One answer-to-update mapping.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE question_observation_models_v1 (
    model_id            TEXT        NOT NULL,
    question_id         TEXT        NOT NULL,  -- FK → question_bank_v1.question_id
    output_type         TEXT        NOT NULL,  -- {feature, node}
    output_ref_id       TEXT        NOT NULL,  -- FK → FEAT_* or NODE_*
    transform_spec      TEXT        NOT NULL,
    noise_spec_json     TEXT        NOT NULL,  -- JSON object
    version             INTEGER     NOT NULL,
    active              INTEGER     NOT NULL,  -- {0,1}
    notes               TEXT,
    PRIMARY KEY (model_id)
);

COMMENT ON TABLE question_observation_models_v1 IS
    'A23: Maps question answers to node/feature updates for Bayesian state estimation.';


-- ───────────────────────────────────────────────────────────────
-- A34. node_search_terms_v1
-- Purpose: PubMed-friendly search synonyms for each biomarker node.
--          Used by query_generator.py for automated retrieval.
--          GREEN provenance — human-curated design choices.
-- FK: node_id → biomarker_node_definitions_v1.node_id
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS node_search_terms_v1 (
    node_id             TEXT        NOT NULL,
    term                TEXT        NOT NULL,
    term_type           TEXT        NOT NULL,  -- {primary, synonym, abbreviation, mesh_heading, instrument, exclude}
    active              INTEGER     NOT NULL DEFAULT 1,  -- {0,1}
    PRIMARY KEY (node_id, term)
);

COMMENT ON TABLE node_search_terms_v1 IS
    'A34: Search synonyms per node for automated retrieval query generation.';


-- ═══════════════════════════════════════════════════════════════
-- End of Class A — Knowledge tables (34 tables total)
-- ═══════════════════════════════════════════════════════════════
