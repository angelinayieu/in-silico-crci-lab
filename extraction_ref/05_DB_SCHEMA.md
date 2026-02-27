# Database Schema Reference

> Exact columns for all tables that extraction populates.  
> Database: `crci_dev.db` (SQLite 3, project root)

---

## Evidence Tables (Populated During Extraction)

### edge_evidence_v1 (101 columns)

The primary evidence table. Each row = one effect size from one paper.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `ler_id` | TEXT | PK | Auto-generated line-evidence-record ID |
| `edge_param_id` | TEXT | | FK to edges_v1 |
| `edge_relation_id` | TEXT | NOT NULL | FK to edge_relations_definitions_v1 |
| `profile_id` | TEXT | NOT NULL | Context profile (cancer_type + treatment_phase) |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `edge_family` | TEXT | | |
| `node_x` | TEXT | | Source node |
| `node_y` | TEXT | | Target node |
| `upstream_instrument_id` | TEXT | | |
| `upstream_stream_id` | TEXT | | |
| `upstream_raw_unit` | TEXT | | |
| `downstream_measure_id` | TEXT | | |
| `downstream_stream_id` | TEXT | | |
| `downstream_raw_unit` | TEXT | | |
| `analysis_model_family` | TEXT | | |
| `analysis_model_family_id` | TEXT | | |
| `model_family` | TEXT | | |
| `random_effects_structure` | TEXT | | |
| `cluster_unit` | TEXT | | |
| `se_type` | TEXT | | |
| `predictor_level` | TEXT | | |
| `centered_level` | TEXT | | |
| `centering_method` | TEXT | | |
| `centering_note` | TEXT | | |
| `outcome_component` | TEXT | | |
| `time_metric_definition` | TEXT | | |
| `CAR_definition` | TEXT | | |
| `time_unit_x` | TEXT | | |
| `time_unit_y` | TEXT | | |
| `x_transform` | TEXT | | |
| `y_transform` | TEXT | | |
| `alignment_type` | TEXT | | |
| `alignment_type_id` | TEXT | | |
| `alignment_lag_days` | INTEGER | | |
| `alignment_note` | TEXT | | |
| `effect_type_reported` | TEXT | NOT NULL | e.g. cohens_d, mean_diff |
| `effect_value_reported` | FLOAT | NOT NULL | The raw effect size value |
| `se_reported` | FLOAT | | Standard error |
| `ci_low_reported` | FLOAT | | 95% CI lower bound |
| `ci_high_reported` | FLOAT | | 95% CI upper bound |
| `p_value` | FLOAT | | |
| `sd_x` | FLOAT | | SD of predictor |
| `sd_y` | FLOAT | | SD of outcome |
| `N_effect` | INTEGER | NOT NULL | Sample size for this effect |
| `subgroup_label` | TEXT | | |
| `covariates_adjusted` | TEXT | | |
| `adjustment_selection_method` | TEXT | | |
| `harmonization_status` | TEXT | | |
| `harmonized_scale` | TEXT | | |
| `harmonized_beta` | FLOAT | | Pipeline-computed |
| `harmonized_se` | FLOAT | | Pipeline-computed |
| `blocked_reason` | TEXT | | |
| `harmonization_rule_id` | TEXT | | |
| `interaction_reported` | INTEGER | | |
| `interaction_variable_id` | TEXT | | |
| `interaction_variable_raw` | TEXT | | |
| `moderator_definition` | TEXT | | |
| `interaction_beta` | FLOAT | | |
| `interaction_se` | FLOAT | | |
| `subgroup_beta_M0` | FLOAT | | |
| `subgroup_se_M0` | FLOAT | | |
| `subgroup_beta_M1` | FLOAT | | |
| `subgroup_se_M1` | FLOAT | | |
| `interaction_effect_reported` | TEXT | | |
| `quality_rating` | TEXT | | |
| `extraction_snippet` | TEXT | | |
| `entered_by` | TEXT | | |
| `entered_at` | TEXT | | |
| `version` | INTEGER | | |
| `active` | INTEGER | | |
| `rob_tool` | TEXT | | |
| `rob_overall` | TEXT | | |
| `estimand_class` | TEXT | | |
| `identification_status` | TEXT | | |
| `parent_meta_study_id` | TEXT | | |
| `meta_source_flag` | TEXT | | |
| `heterogeneity_json` | TEXT | | |
| `effect_size_type` | TEXT | | BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE |
| `se_derivation_level` | TEXT | | |
| `se_inflation_applied` | FLOAT | | |
| `se_quality_tag` | TEXT | | |
| `conversion_formula` | TEXT | | |
| `conversion_bias_risk` | TEXT | | |
| `shared_control_flag` | BOOLEAN | | |
| `shared_control_study_id` | TEXT | | |
| `endpoint_vs_change` | TEXT | | |
| `comparison_arm_label` | TEXT | | |
| `verification_tier` | TEXT | | |
| `verification_status` | TEXT | | |
| `escalation_rules_json` | TEXT | | |
| `escalation_se_inflation` | FLOAT | | |
| `parameter_family` | TEXT | | |
| `freshness_w` | FLOAT | | |
| `freshness_superseded` | BOOLEAN | | |
| `span_hash` | TEXT | | |
| `notes` | TEXT | | |
| `study_design` | TEXT | | RCT, cohort, etc. |
| `cancer_type` | TEXT | | breast, mixed, etc. |
| `treatment_phase` | TEXT | | active_treatment, etc. |
| `pub_year` | INTEGER | | |
| `cancer_validation_status` | TEXT | | |

---

### population_norms_v1 (21 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `extraction_run_id` | TEXT | | |
| `cancer_type` | TEXT | | |
| `treatment_phase` | TEXT | | |
| `node_id` | TEXT | | FK to biomarker_node_definitions_v1 |
| `instrument_id` | TEXT | | FK to instrument_definitions_v1 |
| `instrument_name` | TEXT | | |
| `cognitive_domain` | TEXT | | |
| `population_descriptor` | TEXT | | |
| `mean_raw` | FLOAT | | |
| `sd_raw` | FLOAT | | |
| `mean_z` | FLOAT | | |
| `sd_z` | FLOAT | | |
| `N` | INTEGER | | |
| `percentile` | FLOAT | | |
| `provenance_status` | TEXT | | |
| `provenance_ref` | TEXT | | |
| `created_at` | DATETIME | NOT NULL | DEFAULT CURRENT_TIMESTAMP |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### instrument_evidence_v1 (25 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | |
| `extraction_run_id` | TEXT | | |
| `instrument_id` | TEXT | | |
| `instrument_name` | TEXT | NOT NULL | |
| `instrument_subscale` | TEXT | | |
| `population_descriptor` | TEXT | | |
| `cancer_type` | TEXT | | |
| `treatment_phase` | TEXT | | |
| `N` | INTEGER | | |
| `cronbachs_alpha` | FLOAT | | |
| `se_alpha` | FLOAT | | |
| `factor_loading_mean` | FLOAT | | |
| `factor_loading_per_subscale` | JSON | | |
| `test_retest_reliability` | FLOAT | | |
| `sem_value` | FLOAT | | |
| `convergent_validity` | FLOAT | | |
| `discriminant_validity` | FLOAT | | |
| `factor_structure` | TEXT | | |
| `measurement_invariance` | TEXT | | |
| `provenance_status` | TEXT | | |
| `provenance_ref` | TEXT | | |
| `created_at` | DATETIME | NOT NULL | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### temporal_evidence_v1 (19 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | |
| `extraction_run_id` | TEXT | | |
| `action_id` | TEXT | | |
| `intervention_type` | TEXT | | |
| `timepoint_weeks` | FLOAT | NOT NULL | |
| `effect` | FLOAT | | |
| `se` | FLOAT | | |
| `is_recovery` | INTEGER | | 0 or 1 |
| `N` | INTEGER | | |
| `study_design` | TEXT | | |
| `onset_observed` | TEXT | | |
| `peak_observed` | TEXT | | |
| `decay_observed` | TEXT | | |
| `provenance_status` | TEXT | | |
| `provenance_ref` | TEXT | | |
| `created_at` | DATETIME | NOT NULL | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### biomarker_correlations_v1 (11 columns)

> **Actual DB table name:** `biomarker_correlations_v1` (NOT `correlation_evidence_v1`)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `correlation_id` | TEXT | PK | Auto-generated |
| `node_a_id` | TEXT | | FK to biomarker_node_definitions_v1 |
| `node_b_id` | TEXT | | FK to biomarker_node_definitions_v1 |
| `rho` | FLOAT | | Pearson/Spearman r |
| `rho_se` | FLOAT | | SE of correlation |
| `d_block` | TEXT | | Derived from node layer prefixes |
| `source_citation` | TEXT | | DOI or provenance text |
| `is_decision_critical` | INTEGER | | 0/1 |
| `version` | INTEGER | | |
| `active` | INTEGER | | |
| `notes` | TEXT | | |

---

### node_priors_v1 (14 columns)

> **Actual DB table name:** `node_priors_v1` (NOT `context_priors_v1`).  
> The CSV template is still called `context_priors_template.csv` — the load script maps it to this table.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `prior_id` | TEXT | PK | Auto-generated |
| `node_id` | TEXT | NOT NULL | FK to biomarker_node_definitions_v1 |
| `prior_space` | TEXT | | |
| `mean` | FLOAT | | Prior mean (z-score) |
| `sd` | FLOAT | | Prior SD |
| `dist_family` | TEXT | | Distribution family |
| `cancer_type` | TEXT | | |
| `treatment_phase` | TEXT | | |
| `scope_filters_json` | TEXT | | JSON scope filters |
| `specificity_rank` | INTEGER | | |
| # dose_evidence_v1 (18 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `extraction_run_id` | TEXT | | |
| `action_id` | TEXT | | FK to action_catalog_v1 |
| `intervention_type` | TEXT | | |
| `dose_level` | FLOAT | NOT NULL | Dose amount |
| `dose_unit` | TEXT | | |
| `effect` | FLOAT | | Effect size at this dose |
| `se` | FLOAT | | SE of effect |
| `N` | INTEGER | | Sample size |
| `dose_response_shape` | TEXT | | linear / U_shaped / threshold / etc. |
| `effective_dose_range` | TEXT | | |
| `maximum_tolerated_dose` | TEXT | | |
| `provenance_status` | TEXT | | |
| `provenance_ref` | TEXT | | |
| `created_at` | DATETIME | NOT NULL | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### subgroup_evidence_v1 (17 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `extraction_run_id` | TEXT | | |
| `edge_id` | TEXT | | FK to edge_relations_definitions_v1 |
| `modifier_variable` | TEXT | NOT NULL | e.g. APOE_status, age_group |
| `modifier_value` | TEXT | NOT NULL | e.g. e4_carrier, >65 |
| `interaction_beta` | FLOAT | | Interaction effect |
| `interaction_se` | FLOAT | | |
| `interaction_p` | FLOAT | | |
| `subgroup_effect` | FLOAT | | Subgroup-specific effect |
| `subgroup_se` | FLOAT | | |
| `subgroup_n` | INTEGER | | |
| `provenance_status` | TEXT | | |
| `provenance_ref` | TEXT | | |
| `created_at` | DATETIME | NOT NULL | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### study_cohort_profiles_v1 (33 columns)

Detailed demographics and recruitment info per study cohort.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `profile_id` | TEXT | PK | |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `cohort_label` | TEXT | | e.g. "Treatment arm", "Control" |
| `analysis_timepoint` | TEXT | | |
| `N_analyzed` | INTEGER | | |
| `N_enrolled` | INTEGER | | |
| `recruitment_region` | TEXT | | |
| `recruitment_sites` | TEXT | | |
| `collection_calendar_start` | TEXT | | |
| `collection_calendar_end` | TEXT | | |
| `enrollment_window_text` | TEXT | | |
| `eligibility_inclusion` | TEXT | | |
| `eligibility_exclusion` | TEXT | | |
| `key_exclusion_flags_json` | JSON | | |
| `index_event_time_refs_json` | JSON | | |
| `sex_female_pct` | FLOAT | | |
| `age_mean` | FLOAT | | |
| `age_sd` | FLOAT | | |
| `education_years_mean` | FLOAT | | |
| `education_years_sd` | FLOAT | | |
| `bmi_mean` | FLOAT | | |
| `bmi_sd` | FLOAT | | |
| `race_distribution_json` | JSON | | |
| `marital_distribution_json` | JSON | | |
| `income_distribution_json` | JSON | | |
| `other_demographics_json` | JSON | | |
| `cancer_context_json` | JSON | | |
| `cancer_type` | TEXT | | |
| `treatment_phase` | TEXT | | |
| `time_since_treatment_text` | TEXT | | |
| `analysis_context_json` | JSON | | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### profile_data_streams_v1 (25 columns)

Instrument/assay measurement streams within a cohort profile.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `stream_id` | TEXT | PK | |
| `profile_id` | TEXT | NOT NULL | FK to study_cohort_profiles_v1 |
| `stream_label` | TEXT | | |
| `analyte_or_target` | TEXT | | |
| `modality_type` | TEXT | | |
| `capture_method` | TEXT | | |
| `instrument_id` | TEXT | | FK to instrument_definitions_v1 |
| `measure_id` | TEXT | | FK to measure_definitions_v1 |
| `administration_setting` | TEXT | | |
| `administration_role` | TEXT | | |
| `instrument_version` | TEXT | | |
| `language` | TEXT | | |
| `translation_status` | TEXT | | |
| `visit_context` | TEXT | | |
| `recall_window_iso` | TEXT | | |
| `schedule_pattern` | TEXT | | |
| `schedule_pattern_spec` | TEXT | | |
| `collection_time_unit` | TEXT | | |
| `scheduled_duration_value` | FLOAT | | |
| `timestamp_source` | TEXT | | |
| `primary_time_anchor` | TEXT | | |
| `days_collected_value` | FLOAT | | |
| `quality_controls_summary` | TEXT | | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |

---

### stream_timepoints_v1 (11 columns)

Scheduled measurement timepoints within a data stream.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `timepoint_id` | TEXT | PK | |
| `stream_id` | TEXT | NOT NULL | FK to profile_data_streams_v1 |
| `timepoint_label` | TEXT | | |
| `timepoint_type` | TEXT | | |
| `anchor_event` | TEXT | | |
| `timepoint_minutes` | INTEGER | | |
| `clock_time_hhmm` | TEXT | | |
| `allowable_window_min` | INTEGER | | |
| `required` | INTEGER | | 0/1 |
| `maps_to_measure` | TEXT | | |
| `version` | INTEGER | | |

---

### ontology_links_v1 (11 columns)

Links evidence to ontology terms or external classification systems.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `link_id` | TEXT | PK | |
| `target_table` | TEXT | NOT NULL | Which table this links to |
| `target_id` | TEXT | NOT NULL | FK to target row |
| `study_id` | TEXT | NOT NULL | FK to study_registry_v1 |
| `support_type` | TEXT | | |
| `evidence_strength` | TEXT | | |
| `snippet` | TEXT | | |
| `locator` | TEXT | | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |
| `active` | INTEGER | | |

---

##`provenance` | TEXT | | |
| `active` | INTEGER | | |
| `version` | INTEGER | | |
| `notes` | TEXT | | |

---

## Definition Tables (Pre-Populated from Registries)

### study_registry_v1 (28 columns)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `study_id` | TEXT | PK | |
| `title` | TEXT | NOT NULL | |
| `authors` | TEXT | | |
| `journal` | TEXT | | |
| `year` | INTEGER | | |
| `doi` | TEXT | | |
| `doi_normalized` | TEXT | | |
| `id_source` | TEXT | | |
| `pmid` | TEXT | | |
| `pmcid` | TEXT | | |
| `study_design` | TEXT | | |
| `notes` | TEXT | | |
| `version` | INTEGER | | |
| `study_subtype` | TEXT | | |
| `included_study_ids_json` | TEXT | | |
| `included_k` | INTEGER | | |
| `pdf_path` | TEXT | | |
| `canonical_text_path` | TEXT | | |
| `file_type` | TEXT | | |
| `parse_quality` | TEXT | | |
| `cohort_lineage_id` | TEXT | | |
| `lineage_role` | TEXT | | |
| `multi_arm` | BOOLEAN | | |
| `n_arms` | INTEGER | | |
| `trial_registry_id` | TEXT | | |
| `hop_depth` | INTEGER | | |
| `hop_source_study_id` | TEXT | | |
| `acquisition_queue_id` | TEXT | | |

### biomarker_node_definitions_v1 (17 columns)

| Key Columns | Type | Notes |
|-------------|------|-------|
| `node_id` | TEXT PK | e.g. NODE_COG_WORK_MEM |
| `node_label` | TEXT NOT NULL | Human-readable name |
| `node_role` | TEXT NOT NULL | |
| `orientation` | TEXT NOT NULL | |
| `node_domain` | TEXT NOT NULL | |
| `default_state_space` | TEXT NOT NULL | |

### edge_relations_definitions_v1 (15 columns)

| Key Columns | Type | Notes |
|-------------|------|-------|
| `edge_relation_id` | TEXT PK | e.g. ER_ACTIVITY_EPIMEM |
| `node_x` | TEXT NOT NULL | Source |
| `node_y` | TEXT NOT NULL | Target |
| `relation_type` | TEXT NOT NULL | causal / associational |
| `default_effect_direction` | INTEGER NOT NULL | |

### instrument_definitions_v1 (23 columns)

| Key Columns | Type | Notes |
|-------------|------|-------|
| `instrument_id` | TEXT PK | e.g. INST_HVLTR |
| `instrument_label` | TEXT NOT NULL | |
| `maps_to_node_id` | TEXT NOT NULL | FK to nodes |
| `instrument_kind` | TEXT NOT NULL | PRO / neuropsych_test / biomarker_assay |
| `higher_means_pre_alignment` | TEXT NOT NULL | higher_better / lower_better |

---

## Compiled Tables (Pipeline-Generated from Evidence)

### edges_v1 (39 columns)

Compiled by `load_evidence_into_db.py` Step A6 from all edge_evidence_v1 rows.

| Key Columns | Type | Notes |
|-------------|------|-------|
| `edge_param_id` | TEXT PK | |
| `edge_relation_id` | TEXT NOT NULL | |
| `beta_mean` | FLOAT NOT NULL | Pooled effect size |
| `beta_se` | FLOAT | Pooled SE |
| `ci_low` | FLOAT | |
| `ci_high` | FLOAT | |
| `evidence_level` | TEXT | |
| `cancer_type` | TEXT | |
| `treatment_phase` | TEXT | |
| `total_n` | INTEGER | |
| `i_squared` | FLOAT | Heterogeneity |
| `tau_squared` | FLOAT | |

### node_priors_v1 (14 columns)

Compiled from population_norms + context_priors.

| Key Columns | Type | Notes |
|-------------|------|-------|
| `prior_id` | TEXT PK | |
| `node_id` | TEXT NOT NULL | |
| `mean` | FLOAT NOT NULL | |
| `sd` | FLOAT NOT NULL | |
| `cancer_type` | TEXT | |
| `treatment_phase` | TEXT | |
