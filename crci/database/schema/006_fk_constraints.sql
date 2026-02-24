-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Foreign Key Constraints
-- Spec: 06_FK_WIRING_MAP.md — 128 FK relationships
-- Run AFTER all CREATE TABLE files (001-005, 007).
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- CLASS A: Knowledge tables
-- ───────────────────────────────────────────────────────────────

-- A1. edge_relations_definitions_v1
ALTER TABLE edge_relations_definitions_v1
    ADD CONSTRAINT fk_erd_source_node
        FOREIGN KEY (node_x) REFERENCES biomarker_node_definitions_v1(node_id),
    ADD CONSTRAINT fk_erd_target_node
        FOREIGN KEY (node_y) REFERENCES biomarker_node_definitions_v1(node_id);

-- A2. edge_ontology_v1
ALTER TABLE edge_ontology_v1
    ADD CONSTRAINT fk_eont_edge_relation
        FOREIGN KEY (edge_relation_id) REFERENCES edge_relations_definitions_v1(edge_relation_id);

-- A4. instrument_definitions_v1
ALTER TABLE instrument_definitions_v1
    ADD CONSTRAINT fk_inst_maps_to_node
        FOREIGN KEY (maps_to_node_id) REFERENCES biomarker_node_definitions_v1(node_id);

-- A5. measure_definitions_v1
ALTER TABLE measure_definitions_v1
    ADD CONSTRAINT fk_meas_maps_to_node
        FOREIGN KEY (maps_to_node_id) REFERENCES biomarker_node_definitions_v1(node_id);

-- A7. predictor_alignment_rules_v1
ALTER TABLE predictor_alignment_rules_v1
    ADD CONSTRAINT fk_par_outcome_measure
        FOREIGN KEY (outcome_measure_id) REFERENCES measure_definitions_v1(measure_id);

-- A8. literary_mechanistic_priors_v1
ALTER TABLE literary_mechanistic_priors_v1
    ADD CONSTRAINT fk_lmp_target_edge
        FOREIGN KEY (target_edge_relation_id) REFERENCES edge_relations_definitions_v1(edge_relation_id);

-- A10. contraindication_rules_v1
ALTER TABLE contraindication_rules_v1
    ADD CONSTRAINT fk_cr_escalation
        FOREIGN KEY (escalation_id) REFERENCES contraindication_escalation_policy_v1(escalation_id);

-- A11. action_contraindication_links_v1
ALTER TABLE action_contraindication_links_v1
    ADD CONSTRAINT fk_acl_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id),
    ADD CONSTRAINT fk_acl_rule
        FOREIGN KEY (rule_id) REFERENCES contraindication_rules_v1(rule_id);

-- A15. variable_to_input_map_v1
ALTER TABLE variable_to_input_map_v1
    ADD CONSTRAINT fk_vtim_variable
        FOREIGN KEY (variable_id) REFERENCES variable_definitions_v1(variable_id);

-- A18. triangulation_sets_v1
ALTER TABLE triangulation_sets_v1
    ADD CONSTRAINT fk_ts_target_node
        FOREIGN KEY (target_node_id) REFERENCES biomarker_node_definitions_v1(node_id);

-- A19. triangulation_members_v1
ALTER TABLE triangulation_members_v1
    ADD CONSTRAINT fk_tm_triangulation
        FOREIGN KEY (triangulation_id) REFERENCES triangulation_sets_v1(triangulation_id);

-- A22. question_bank_v1
ALTER TABLE question_bank_v1
    ADD CONSTRAINT fk_qb_observation_model
        FOREIGN KEY (observation_model_id) REFERENCES question_observation_models_v1(model_id);

-- A26. pathways_v1 — JSON-array FKs enforced at application level

-- A27. pathway_interactions_v1
ALTER TABLE pathway_interactions_v1
    ADD CONSTRAINT fk_pint_pathway_a
        FOREIGN KEY (pathway_a_id) REFERENCES pathways_v1(pathway_id),
    ADD CONSTRAINT fk_pint_pathway_b
        FOREIGN KEY (pathway_b_id) REFERENCES pathways_v1(pathway_id);

-- A28. intervention_synergy_v1
ALTER TABLE intervention_synergy_v1
    ADD CONSTRAINT fk_syn_action_a
        FOREIGN KEY (action_a_id) REFERENCES action_catalog_v1(action_id),
    ADD CONSTRAINT fk_syn_action_b
        FOREIGN KEY (action_b_id) REFERENCES action_catalog_v1(action_id);

-- A30. biomarker_correlations_v1
ALTER TABLE biomarker_correlations_v1
    ADD CONSTRAINT fk_bc_node_a
        FOREIGN KEY (node_a_id) REFERENCES biomarker_node_definitions_v1(node_id),
    ADD CONSTRAINT fk_bc_node_b
        FOREIGN KEY (node_b_id) REFERENCES biomarker_node_definitions_v1(node_id);

-- A32. intervention_kernels_v1
ALTER TABLE intervention_kernels_v1
    ADD CONSTRAINT fk_kern_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id);

-- ───────────────────────────────────────────────────────────────
-- CLASS B: Evidence tables
-- ───────────────────────────────────────────────────────────────

-- B2. study_cohort_profiles_v1
ALTER TABLE study_cohort_profiles_v1
    ADD CONSTRAINT fk_scp_study
        FOREIGN KEY (study_id) REFERENCES study_registry_v1(study_id);

-- B3. profile_data_streams_v1
ALTER TABLE profile_data_streams_v1
    ADD CONSTRAINT fk_pds_profile
        FOREIGN KEY (profile_id) REFERENCES study_cohort_profiles_v1(profile_id);

-- B4. stream_timepoints_v1
ALTER TABLE stream_timepoints_v1
    ADD CONSTRAINT fk_stp_stream
        FOREIGN KEY (stream_id) REFERENCES profile_data_streams_v1(stream_id);

-- B5. ontology_links_v1
ALTER TABLE ontology_links_v1
    ADD CONSTRAINT fk_ol_study
        FOREIGN KEY (study_id) REFERENCES study_registry_v1(study_id);

-- B6. edge_evidence_v1
ALTER TABLE edge_evidence_v1
    ADD CONSTRAINT fk_ee_study
        FOREIGN KEY (study_id) REFERENCES study_registry_v1(study_id),
    ADD CONSTRAINT fk_ee_edge_relation
        FOREIGN KEY (edge_relation_id) REFERENCES edge_relations_definitions_v1(edge_relation_id),
    ADD CONSTRAINT fk_ee_profile
        FOREIGN KEY (profile_id) REFERENCES study_cohort_profiles_v1(profile_id);

-- B8. triangulation_evidence_v1
ALTER TABLE triangulation_evidence_v1
    ADD CONSTRAINT fk_te_triangulation
        FOREIGN KEY (triangulation_id) REFERENCES triangulation_sets_v1(triangulation_id);

-- B9. pathway_biomarkers_v1
ALTER TABLE pathway_biomarkers_v1
    ADD CONSTRAINT fk_pb_pathway
        FOREIGN KEY (pathway_id) REFERENCES pathways_v1(pathway_id),
    ADD CONSTRAINT fk_pb_node
        FOREIGN KEY (node_id) REFERENCES biomarker_node_definitions_v1(node_id),
    ADD CONSTRAINT fk_pb_measure
        FOREIGN KEY (measure_id) REFERENCES measure_definitions_v1(measure_id),
    ADD CONSTRAINT fk_pb_study
        FOREIGN KEY (source_study_id) REFERENCES study_registry_v1(study_id);

-- B10. extraction_audit_v1
ALTER TABLE extraction_audit_v1
    ADD CONSTRAINT fk_ea_study
        FOREIGN KEY (study_id) REFERENCES study_registry_v1(study_id);

-- ───────────────────────────────────────────────────────────────
-- CLASS C: Compiled tables
-- ───────────────────────────────────────────────────────────────

-- C1. edges_v1
ALTER TABLE edges_v1
    ADD CONSTRAINT fk_edges_edge_relation
        FOREIGN KEY (edge_relation_id) REFERENCES edge_relations_definitions_v1(edge_relation_id);

-- C2. dose_bridges_v1
ALTER TABLE dose_bridges_v1
    ADD CONSTRAINT fk_db_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id);

-- C3. node_priors_v1
ALTER TABLE node_priors_v1
    ADD CONSTRAINT fk_np_node
        FOREIGN KEY (node_id) REFERENCES biomarker_node_definitions_v1(node_id);

-- C6. chain_validation_results_v1
ALTER TABLE chain_validation_results_v1
    ADD CONSTRAINT fk_cvr_pathway
        FOREIGN KEY (pathway_id) REFERENCES pathways_v1(pathway_id);

-- C7. publication_bias_results_v1
ALTER TABLE publication_bias_results_v1
    ADD CONSTRAINT fk_pbr_edge
        FOREIGN KEY (edge_param_id) REFERENCES edges_v1(edge_param_id);

-- ───────────────────────────────────────────────────────────────
-- CLASS D: Policy tables
-- ───────────────────────────────────────────────────────────────

-- D4. status_quo_rules_v1
ALTER TABLE status_quo_rules_v1
    ADD CONSTRAINT fk_sqr_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id);

-- ───────────────────────────────────────────────────────────────
-- CLASS E: Output tables
-- ───────────────────────────────────────────────────────────────

-- E1. state_snapshots_v1
ALTER TABLE state_snapshots_v1
    ADD CONSTRAINT fk_ss_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_ss_estimator
        FOREIGN KEY (estimator_id) REFERENCES state_estimator_specs_v1(estimator_id);

-- E2. scenario_definitions_v1
ALTER TABLE scenario_definitions_v1
    ADD CONSTRAINT fk_sd_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_sd_state
        FOREIGN KEY (base_state_id) REFERENCES state_snapshots_v1(state_id);

-- E3. scenario_items_v1
ALTER TABLE scenario_items_v1
    ADD CONSTRAINT fk_si_scenario
        FOREIGN KEY (scenario_id) REFERENCES scenario_definitions_v1(scenario_id),
    ADD CONSTRAINT fk_si_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id);

-- E4. schedule_plans_v1
ALTER TABLE schedule_plans_v1
    ADD CONSTRAINT fk_sp_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_sp_scenario
        FOREIGN KEY (source_scenario_id) REFERENCES scenario_definitions_v1(scenario_id);

-- E5. schedule_items_v1
ALTER TABLE schedule_items_v1
    ADD CONSTRAINT fk_schi_schedule
        FOREIGN KEY (schedule_id) REFERENCES schedule_plans_v1(schedule_id),
    ADD CONSTRAINT fk_schi_action
        FOREIGN KEY (action_id) REFERENCES action_catalog_v1(action_id);

-- E6. recommendation_runs_v1
ALTER TABLE recommendation_runs_v1
    ADD CONSTRAINT fk_rr_objective
        FOREIGN KEY (objective_spec_id) REFERENCES objective_specs_v1(objective_id),
    ADD CONSTRAINT fk_rr_safety
        FOREIGN KEY (safety_policy_id) REFERENCES safety_policies_v1(safety_policy_id),
    ADD CONSTRAINT fk_rr_escalation
        FOREIGN KEY (escalation_policy_id) REFERENCES escalation_policies_v1(escalation_id);

-- E7. simulation_trace_v1
ALTER TABLE simulation_trace_v1
    ADD CONSTRAINT fk_st_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_st_scenario
        FOREIGN KEY (scenario_id) REFERENCES scenario_definitions_v1(scenario_id);

-- E8. decision_trace_v1
ALTER TABLE decision_trace_v1
    ADD CONSTRAINT fk_dt_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id);

-- E9. contraindication_eval_trace_v1
ALTER TABLE contraindication_eval_trace_v1
    ADD CONSTRAINT fk_cet_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_cet_rule
        FOREIGN KEY (rule_id) REFERENCES contraindication_rules_v1(rule_id);

-- E10. question_selection_trace_v1
ALTER TABLE question_selection_trace_v1
    ADD CONSTRAINT fk_qst_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id);

-- E11. modifier_eval_trace_v1
ALTER TABLE modifier_eval_trace_v1
    ADD CONSTRAINT fk_met_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_met_modifier
        FOREIGN KEY (modifier_id) REFERENCES baseline_modifier_definitions_v1(modifier_id),
    ADD CONSTRAINT fk_met_edge
        FOREIGN KEY (edge_param_id) REFERENCES edges_v1(edge_param_id),
    ADD CONSTRAINT fk_met_variable
        FOREIGN KEY (variable_id) REFERENCES variable_definitions_v1(variable_id);

-- E12. question_sequence_v1
ALTER TABLE question_sequence_v1
    ADD CONSTRAINT fk_qs_run
        FOREIGN KEY (run_id) REFERENCES recommendation_runs_v1(run_id),
    ADD CONSTRAINT fk_qs_question
        FOREIGN KEY (question_id) REFERENCES question_bank_v1(question_id),
    ADD CONSTRAINT fk_qs_state_before
        FOREIGN KEY (state_id_before) REFERENCES state_snapshots_v1(state_id),
    ADD CONSTRAINT fk_qs_state_after
        FOREIGN KEY (state_id_after) REFERENCES state_snapshots_v1(state_id),
    ADD CONSTRAINT fk_qs_obs_model
        FOREIGN KEY (observation_model_id) REFERENCES question_observation_models_v1(model_id),
    ADD CONSTRAINT fk_qs_selection_trace
        FOREIGN KEY (selection_trace_id) REFERENCES question_selection_trace_v1(qtrace_id);
