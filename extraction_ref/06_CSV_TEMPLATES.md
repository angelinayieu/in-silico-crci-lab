# CSV Template Column Specifications

> **AUTHORITATIVE column reference** for all 13 CSV templates in `data/templates/`.
> Every column name matches the target DB table column **exactly**.
> The only non-DB column is `doi` (resolved to `study_id` by the importer).
>
> Copy templates to `data/manual_uploads/structured/<doi-slug>/` before filling.

---

## Governing Rule

```
CSV column name == DB column name (1:1)
No renames. No translation layer. No silent mapping.
```

The importer performs only:
1. `doi` → `study_id` lookup (via `study_registry_v1`)
2. Auto-generated IDs (`ler_id`, `prior_id`, `correlation_id`, etc.)
3. Computed columns (`harmonized_beta`, `se_eff`, `span_hash`, etc.)

---

## 1. edge_evidence_template.csv → `edge_evidence_v1` (28 extractor columns)

The DB table has 107 columns total. The extractor fills the 28 below.
The remaining ~79 are auto-generated, computed, or set by downstream pipeline stages.

```csv
doi,edge_relation_id,effect_value_reported,se_reported,effect_type_reported,effect_size_type,N_effect,study_design,cancer_type,treatment_phase,upstream_instrument_id,notes,ci_low_reported,ci_high_reported,p_value,n_treatment,n_control,sd_x,sd_y,cancer_validation_status,rob_overall,pub_year,covariates_adjusted,endpoint_vs_change,comparison_arm_label,se_derivation_level,shared_control_flag,extraction_snippet
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → resolved to `study_id` by importer. Not a DB column. |
| 2 | `edge_relation_id` | YES | TEXT | Must exist in `edge_relations_definitions_v1`. E.g. `ER_ACTIVITY_PROC_SPEED` |
| 3 | `effect_value_reported` | YES | FLOAT | Standardized effect size – prefer Cohen's d |
| 4 | `se_reported` | YES | FLOAT | Standard error – derive if not directly reported (see `03_SE_DERIVATION.md`) |
| 5 | `effect_type_reported` | YES | TEXT | What the paper actually reports: `cohens_d`, `mean_diff`, `odds_ratio`, `log_odds_ratio`, `correlation_r`, `hazard_ratio`, `eta_squared`, `partial_eta_squared` |
| 6 | `effect_size_type` | YES | TEXT | `BETWEEN_GROUP` / `WITHIN_GROUP` / `PRE_POST_CHANGE` |
| 7 | `N_effect` | YES | INTEGER | Analysis N (not enrollment N) |
| 8 | `study_design` | YES | TEXT | `RCT`, `crossover_RCT`, `cohort`, `cross_sectional`, `case_control`, `pre_post` |
| 9 | `cancer_type` | YES | TEXT | `breast`, `colorectal`, `hematologic`, `lung`, `prostate`, `mixed`, etc. |
| 10 | `treatment_phase` | YES | TEXT | `active_treatment`, `early_recovery`, `late_recovery`, `long_term_survivorship`, `mixed` |
| 11 | `upstream_instrument_id` | YES | TEXT | Must exist in `instrument_definitions_v1`. E.g. `INST_HVLTR` |
| 12 | `notes` | — | TEXT | Free text: derivation notes, concerns, extraction decisions |
| 13 | `ci_low_reported` | — | FLOAT | 95% CI lower bound (as reported in paper) |
| 14 | `ci_high_reported` | — | FLOAT | 95% CI upper bound (as reported in paper) |
| 15 | `p_value` | — | FLOAT | Reported p-value |
| 16 | `n_treatment` | — | INTEGER | Treatment arm N (for multi-arm or group comparisons) |
| 17 | `n_control` | — | INTEGER | Control arm N |
| 18 | `sd_x` | — | FLOAT | SD of predictor/treatment group |
| 19 | `sd_y` | — | FLOAT | SD of outcome/control group |
| 20 | `cancer_validation_status` | — | TEXT | Whether instrument is validated in cancer: `validated`, `not_validated`, `unknown` |
| 21 | `rob_overall` | — | TEXT | Overall risk of bias: `low`, `moderate`, `high`, `critical` |
| 22 | `pub_year` | — | INTEGER | Publication year |
| 23 | `covariates_adjusted` | — | TEXT | Comma-separated covariate list, e.g. `"age,sex,education,depression"` |
| 24 | `endpoint_vs_change` | — | TEXT | `endpoint` / `change` — whether the effect is on final score or change from baseline |
| 25 | `comparison_arm_label` | — | TEXT | E.g. `"HIIT vs CON"`, `"yoga vs waitlist"` |
| 26 | `se_derivation_level` | — | TEXT | How SE was obtained: `reported`, `from_ci`, `from_p_value`, `from_sd_n`, `fallback_4_over_n` |
| 27 | `shared_control_flag` | — | BOOLEAN | `true` if control arm shared across multiple comparisons in multi-arm trial |
| 28 | `extraction_snippet` | — | TEXT | Verbatim quote from paper supporting this data point |

### Auto-generated columns (NOT in template — set by pipeline)

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `ler_id` | Step 4 (load) | `LER_{study_id}_{edge_relation_id}_{span_hash}` |
| `edge_param_id` | Step 4 (load) | `EP_{edge_relation_id}_{span_hash[:8]}` |
| `study_id` | Step 4 (load) | Looked up from `doi` via `study_registry_v1` |
| `profile_id` | Step 4 (load) | `"PROFILE_DEFAULT"` |
| `edge_family` | Step 4 (load) | Looked up from `edge_relations_definitions_v1` |
| `node_x`, `node_y` | Step 4 (load) | Looked up from `edge_relations_definitions_v1` |
| `harmonized_beta` | Step 4c (harmonize) | Initially = `effect_value_reported`; later overwritten |
| `harmonized_se` | Step 4c (harmonize) | Initially = `se_reported`; later overwritten |
| `harmonization_status` | Step 4c (harmonize) | `"harmonized"` |
| `harmonized_scale` | Step 4c (harmonize) | Inferred from `effect_type_reported` |
| `se_eff` | Step 4d (calibrate) | 7-layer SE calibration result |
| `span_hash` | Step 4 (load) | SHA-256 of (study_id, edge_relation_id, beta, se, n) |
| `quality_rating` | Step 4 (load) | = `rob_overall` or `"moderate"` default |
| `se_quality_tag` | Step 4 (load) | `"manual_extraction"` |
| `identification_status` | Step 4 (load) | `"plausible"` |
| `entered_by` | Step 4 (load) | `"manual_csv_import"` |
| `entered_at` | Step 4 (load) | Current UTC timestamp |
| `version` | Step 4 (load) | `1` |
| `active` | Step 4 (load) | `1` |
| `outcome_type` | Step 4 (load) | `"semi_objective"` (default) |

---

## 2. population_norms_template.csv → `population_norms_v1` (9 extractor columns)

DB table has 21 columns total.

```csv
doi,node_id,instrument_id,mean_raw,sd_raw,N,cancer_type,treatment_phase,age_range
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → `study_id` |
| 2 | `node_id` | YES | TEXT | Must exist in `biomarker_node_definitions_v1` |
| 3 | `instrument_id` | YES | TEXT | Must exist in `instrument_definitions_v1` |
| 4 | `mean_raw` | YES | FLOAT | Control/reference group baseline mean (raw score) |
| 5 | `sd_raw` | YES | FLOAT | SD of mean (must be > 0) |
| 6 | `N` | YES | INTEGER | Sample size contributing to this estimate |
| 7 | `cancer_type` | YES | TEXT | Same enum as edge_evidence |
| 8 | `treatment_phase` | YES | TEXT | Same enum as edge_evidence |
| 9 | `age_range` | — | TEXT | E.g. `"45-65"` |

### Auto-generated columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `id` | Importer | Auto-generated UUID |
| `study_id` | Importer | From `doi` lookup |
| `extraction_run_id` | Importer | Current run ID |
| `instrument_name` | Importer | Looked up from `instrument_definitions_v1` (nullable) |
| `cognitive_domain` | Importer | Inferred from node_id (nullable) |
| `population_descriptor` | Importer | Auto-composed (nullable) |
| `mean_z` | Pipeline | Computed from raw + norms (nullable initially) |
| `sd_z` | Pipeline | Computed from raw + norms (nullable initially) |
| `percentile` | Pipeline | Computed (nullable) |
| `provenance_status` | Importer | `"manual_extraction"` |
| `provenance_ref` | Importer | From doi |
| `created_at` | Importer | UTC timestamp |
| `notes` | Importer | From CSV if present |
| `version` | Importer | `1` |

---

## 3. context_priors_template.csv → `node_priors_v1` (9 extractor columns)

> ⚠️ **Table name warning:** This template loads into **`node_priors_v1`** (NOT `context_priors_v1`).

DB table has 14 columns total.

```csv
doi,node_id,cancer_type,treatment_phase,mean,sd,source_type,n_contributing,notes
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → stored in `provenance` field |
| 2 | `node_id` | YES | TEXT | Must exist in `biomarker_node_definitions_v1` |
| 3 | `cancer_type` | YES | TEXT | Scoping dimension |
| 4 | `treatment_phase` | YES | TEXT | Scoping dimension |
| 5 | `mean` | YES | FLOAT | z-score — maps directly to `node_priors_v1.mean` |
| 6 | `sd` | YES | FLOAT | Uncertainty (typically 0.5) — maps directly to `node_priors_v1.sd` |
| 7 | `source_type` | YES | TEXT | `published_norm` / `local_control_group` / `expert` |
| 8 | `n_contributing` | — | INTEGER | Studies contributing to this prior — folded into `notes` |
| 9 | `notes` | — | TEXT | Derivation notes |

### Auto-generated columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `prior_id` | Importer | `NP_{node_id}_{cancer_type}_{treatment_phase}_{hash}` |
| `prior_space` | Importer | `"z_score"` |
| `dist_family` | Importer | `"normal"` |
| `scope_filters_json` | Importer | JSON from cancer_type + treatment_phase |
| `specificity_rank` | Importer | Computed from scope specificity |
| `provenance` | Importer | `"doi:{doi}; source_type:{source_type}"` |
| `active` | Importer | `1` |
| `version` | Importer | `1` |

### How to compute the z-score

```
z = (observed_mean − population_mean) / population_SD
```

If no published norms available, use control group baseline and set `source_type = local_control_group`.

---

## 4. temporal_evidence_template.csv → `temporal_evidence_v1` (8 extractor columns)

DB table has 19 columns total.

```csv
doi,edge_relation_id,timepoint_weeks,effect,se,is_recovery,N,provenance_ref
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → `study_id` |
| 2 | `edge_relation_id` | YES | TEXT | Must exist in EDGE_REGISTRY. Mapped to `action_id` by importer. |
| 3 | `timepoint_weeks` | YES | FLOAT | Weeks from baseline |
| 4 | `effect` | YES | FLOAT | Effect size at this timepoint |
| 5 | `se` | YES | FLOAT | SE at this timepoint |
| 6 | `is_recovery` | YES | INTEGER | `0` = intervention period, `1` = recovery/follow-up |
| 7 | `N` | YES | INTEGER | Sample size at this timepoint |
| 8 | `provenance_ref` | — | TEXT | Table/figure reference in paper |

### Auto-generated columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `id` | Importer | Auto-generated UUID |
| `study_id` | Importer | From `doi` lookup |
| `extraction_run_id` | Importer | Current run ID |
| `action_id` | Importer | Mapped from `edge_relation_id` |
| `intervention_type` | Importer | Inferred from edge family (nullable) |
| `study_design` | Importer | From study_registry (nullable) |
| `onset_observed`, `peak_observed`, `decay_observed` | Pipeline | Computed from trajectory (nullable) |
| `provenance_status` | Importer | `"manual_extraction"` |
| `created_at` | Importer | UTC timestamp |
| `notes` | Importer | From CSV if present |
| `version` | Importer | `1` |

> **Note:** The CSV uses `edge_relation_id` for consistency with other templates.
> The importer maps this to `action_id` in the DB (temporal evidence is keyed by action, not edge).

---

## 5. instrument_evidence_template.csv → `instrument_evidence_v1` (15 extractor columns)

DB table has 25 columns total.

```csv
doi,instrument_id,instrument_name,instrument_subscale,cronbachs_alpha,se_alpha,test_retest_reliability,factor_loading_mean,sem_value,N,cancer_type,treatment_phase,cancer_validated,provenance_ref,notes
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → `study_id` |
| 2 | `instrument_id` | YES | TEXT | Must exist in `instrument_definitions_v1` |
| 3 | `instrument_name` | YES | TEXT | Full name (e.g. `"Hopkins Verbal Learning Test-Revised"`) |
| 4 | `instrument_subscale` | — | TEXT | Subscale name if applicable (e.g. `"Delayed Recall"`) |
| 5 | `cronbachs_alpha` | — | FLOAT | Cronbach's α (if reported) |
| 6 | `se_alpha` | — | FLOAT | SE of Cronbach's α (if reported) |
| 7 | `test_retest_reliability` | — | FLOAT | Test-retest ICC (if reported) |
| 8 | `factor_loading_mean` | — | FLOAT | Mean factor loading (if reported) |
| 9 | `sem_value` | — | FLOAT | Standard error of measurement (if reported) |
| 10 | `N` | YES | INTEGER | Sample size |
| 11 | `cancer_type` | YES | TEXT | Cancer population tested |
| 12 | `treatment_phase` | YES | TEXT | Treatment phase |
| 13 | `cancer_validated` | — | TEXT | `true` / `false` — validated in cancer population? |
| 14 | `provenance_ref` | — | TEXT | Table/figure reference in paper |
| 15 | `notes` | — | TEXT | Any additional notes |

### Auto-generated columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `id` | Importer | Auto-generated UUID |
| `study_id` | Importer | From `doi` lookup |
| `extraction_run_id` | Importer | Current run ID |
| `population_descriptor` | Importer | Auto-composed (nullable) |
| `factor_loading_per_subscale` | Importer | JSON (nullable) |
| `convergent_validity` | Importer | (nullable) |
| `discriminant_validity` | Importer | (nullable) |
| `factor_structure` | Importer | (nullable) |
| `measurement_invariance` | Importer | (nullable) |
| `provenance_status` | Importer | `"manual_extraction"` |
| `created_at` | Importer | UTC timestamp |
| `version` | Importer | `1` |

---

## 6. correlation_template.csv → `biomarker_correlations_v1` (6 extractor columns)

> ⚠️ **Table name warning:** This template loads into **`biomarker_correlations_v1`** (NOT `correlation_evidence_v1`).

DB table has 11 columns total.

```csv
doi,node_a_id,node_b_id,rho,N,partial_or_zero
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `doi` | YES | — | Lookup key → stored in `source_citation` as `"doi:{value}"` |
| 2 | `node_a_id` | YES | TEXT | First node ID (from NODE_REGISTRY) |
| 3 | `node_b_id` | YES | TEXT | Second node ID (from NODE_REGISTRY) |
| 4 | `rho` | YES | FLOAT | Pearson/Spearman r (must be in [-1, 1]) |
| 5 | `N` | — | INTEGER | Sample size (used to compute `rho_se`) |
| 6 | `partial_or_zero` | YES | TEXT | `partial` / `zero_order` — maps to `d_block` |

### Auto-generated columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `correlation_id` | Importer | `CORR_{sha256(study_id\|node_a\|node_b)[:12]}` |
| `rho_se` | Importer | `(1 - rho²) / √(N - 2)` |
| `d_block` | Importer | Derived from `partial_or_zero` + node prefixes |
| `source_citation` | Importer | `"doi:{doi}"` |
| `is_decision_critical` | Importer | `0` (default) |
| `version` | Importer | `1` |
| `active` | Importer | `1` |
| `notes` | Importer | From CSV if present |

---

## 7. dose_evidence_template.csv → `dose_evidence_v1` (17 columns → DB-direct)

DB table has 18 columns. Template has all except `created_at` (auto-set).

```csv
id,study_id,extraction_run_id,action_id,intervention_type,dose_level,dose_unit,effect,se,N,dose_response_shape,effective_dose_range,maximum_tolerated_dose,provenance_status,provenance_ref,notes,version
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `id` | — | TEXT | Auto-generated if blank |
| 2 | `study_id` | YES | TEXT | DOI slug or study_id |
| 3 | `extraction_run_id` | — | TEXT | |
| 4 | `action_id` | YES | TEXT | FK to `action_catalog_v1` (e.g. `ACT_AEROBIC_EXERCISE`) |
| 5 | `intervention_type` | YES | TEXT | `aerobic_exercise`, `resistance_training`, etc. |
| 6 | `dose_level` | YES | FLOAT | Dose amount (e.g. 150 for 150 min/wk) |
| 7 | `dose_unit` | YES | TEXT | `min_per_week`, `sessions_per_week`, `mg_per_day` |
| 8 | `effect` | YES | FLOAT | Effect size at this dose level |
| 9 | `se` | YES | FLOAT | SE of effect |
| 10 | `N` | YES | INTEGER | Sample size |
| 11 | `dose_response_shape` | — | TEXT | `linear`, `U_shaped`, `threshold`, `plateau` |
| 12 | `effective_dose_range` | — | TEXT | E.g. `"90-180 min/wk"` |
| 13 | `maximum_tolerated_dose` | — | TEXT | If reported |
| 14 | `provenance_status` | — | TEXT | |
| 15 | `provenance_ref` | — | TEXT | Table/figure reference |
| 16 | `notes` | — | TEXT | |
| 17 | `version` | — | INTEGER | |

> **Note:** This template uses `study_id` directly (not `doi`). If using DOI, the importer resolves to study_id.

---

## 8. subgroup_evidence_template.csv → `subgroup_evidence_v1` (16 columns → DB-direct)

DB table has 17 columns. Template has all except `created_at` (auto-set).

```csv
id,study_id,extraction_run_id,edge_id,modifier_variable,modifier_value,interaction_beta,interaction_se,interaction_p,subgroup_effect,subgroup_se,subgroup_n,provenance_status,provenance_ref,notes,version
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `id` | — | TEXT | Auto-generated if blank |
| 2 | `study_id` | YES | TEXT | DOI slug or study_id |
| 3 | `extraction_run_id` | — | TEXT | |
| 4 | `edge_id` | YES | TEXT | Must exist in EDGE_REGISTRY |
| 5 | `modifier_variable` | YES | TEXT | E.g. `APOE_status`, `age_group`, `sex`, `treatment_type` |
| 6 | `modifier_value` | YES | TEXT | E.g. `e4_carrier`, `>65`, `female` |
| 7 | `interaction_beta` | — | FLOAT | Interaction (modifier × treatment) effect |
| 8 | `interaction_se` | — | FLOAT | SE of interaction |
| 9 | `interaction_p` | — | FLOAT | p-value of interaction |
| 10 | `subgroup_effect` | — | FLOAT | Subgroup-specific point estimate |
| 11 | `subgroup_se` | — | FLOAT | Subgroup-specific SE |
| 12 | `subgroup_n` | — | INTEGER | Subgroup sample size |
| 13 | `provenance_status` | — | TEXT | |
| 14 | `provenance_ref` | — | TEXT | Table/figure reference |
| 15 | `notes` | — | TEXT | |
| 16 | `version` | — | INTEGER | |

> **Note:** This template uses `study_id` directly (not `doi`).
> The `edge_id` here maps to `subgroup_evidence_v1.edge_id` (not `edge_relation_id`).

---

## 9. study_cohort_profile_template.csv → `study_cohort_profiles_v1` (25 extractor columns)

DB table has 33 columns. Template covers all non-JSONB columns.

```csv
profile_id,study_id,cohort_label,analysis_timepoint,N_analyzed,N_enrolled,recruitment_region,recruitment_sites,collection_calendar_start,collection_calendar_end,enrollment_window_text,eligibility_inclusion,eligibility_exclusion,sex_female_pct,age_mean,age_sd,education_years_mean,education_years_sd,bmi_mean,bmi_sd,cancer_type,treatment_phase,time_since_treatment_text,notes,version
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `profile_id` | YES | TEXT | Unique ID (e.g. `PROF_{study_id}_{arm_label}`) |
| 2 | `study_id` | YES | TEXT | DOI slug or study_id |
| 3 | `cohort_label` | YES | TEXT | E.g. `"HIIT arm"`, `"Control"`, `"Chemo-treated"` |
| 4 | `analysis_timepoint` | — | TEXT | E.g. `"baseline"`, `"12-week"` |
| 5 | `N_analyzed` | YES | INTEGER | Actual N in analysis |
| 6 | `N_enrolled` | — | INTEGER | Enrolled N |
| 7 | `recruitment_region` | — | TEXT | |
| 8 | `recruitment_sites` | — | TEXT | |
| 9 | `collection_calendar_start` | — | TEXT | |
| 10 | `collection_calendar_end` | — | TEXT | |
| 11 | `enrollment_window_text` | — | TEXT | |
| 12 | `eligibility_inclusion` | — | TEXT | |
| 13 | `eligibility_exclusion` | — | TEXT | |
| 14 | `sex_female_pct` | — | FLOAT | Percentage female |
| 15 | `age_mean` | — | FLOAT | |
| 16 | `age_sd` | — | FLOAT | |
| 17 | `education_years_mean` | — | FLOAT | |
| 18 | `education_years_sd` | — | FLOAT | |
| 19 | `bmi_mean` | — | FLOAT | |
| 20 | `bmi_sd` | — | FLOAT | |
| 21 | `cancer_type` | YES | TEXT | |
| 22 | `treatment_phase` | YES | TEXT | |
| 23 | `time_since_treatment_text` | — | TEXT | |
| 24 | `notes` | — | TEXT | |
| 25 | `version` | — | INTEGER | |

### JSONB columns (not in template — set programmatically when data available)

| DB Column | Type | Description |
|-----------|------|-------------|
| `key_exclusion_flags_json` | JSON | Structured exclusion criteria flags |
| `index_event_time_refs_json` | JSON | Time reference points |
| `race_distribution_json` | JSON | Race/ethnicity breakdown |
| `marital_distribution_json` | JSON | Marital status breakdown |
| `income_distribution_json` | JSON | Income distribution |
| `other_demographics_json` | JSON | Additional demographic data |
| `cancer_context_json` | JSON | Cancer-specific context (stage, receptor status, etc.) |
| `analysis_context_json` | JSON | Analysis context (imputation method, model type, etc.) |

---

## 10. profile_data_stream_template.csv → `profile_data_streams_v1` (21 extractor columns)

DB table has 25 columns.

```csv
stream_id,profile_id,stream_label,analyte_or_target,modality_type,capture_method,instrument_id,measure_id,administration_setting,administration_role,instrument_version,language,visit_context,recall_window_iso,schedule_pattern,collection_time_unit,scheduled_duration_value,primary_time_anchor,quality_controls_summary,notes,version
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `stream_id` | YES | TEXT | Unique stream ID |
| 2 | `profile_id` | YES | TEXT | FK to `study_cohort_profiles_v1.profile_id` |
| 3 | `stream_label` | — | TEXT | Human-readable label |
| 4 | `analyte_or_target` | — | TEXT | What's being measured |
| 5 | `modality_type` | — | TEXT | questionnaire, neuropsych_test, biomarker_assay, wearable |
| 6 | `capture_method` | — | TEXT | |
| 7 | `instrument_id` | — | TEXT | FK to `instrument_definitions_v1` |
| 8 | `measure_id` | — | TEXT | FK to `measure_definitions_v1` |
| 9 | `administration_setting` | — | TEXT | clinic, home, remote |
| 10 | `administration_role` | — | TEXT | self, clinician, caregiver |
| 11 | `instrument_version` | — | TEXT | |
| 12 | `language` | — | TEXT | |
| 13 | `visit_context` | — | TEXT | |
| 14 | `recall_window_iso` | — | TEXT | ISO 8601 duration (e.g. `"P7D"`) |
| 15 | `schedule_pattern` | — | TEXT | |
| 16 | `collection_time_unit` | — | TEXT | |
| 17 | `scheduled_duration_value` | — | FLOAT | |
| 18 | `primary_time_anchor` | — | TEXT | |
| 19 | `quality_controls_summary` | — | TEXT | |
| 20 | `notes` | — | TEXT | |
| 21 | `version` | — | INTEGER | |

### Not-in-template columns

| DB Column | Set By | Logic |
|-----------|--------|-------|
| `translation_status` | Importer | (nullable) |
| `schedule_pattern_spec` | Importer | (nullable) |
| `timestamp_source` | Importer | (nullable) |
| `days_collected_value` | Importer | (nullable) |

---

## 11. stream_timepoint_template.csv → `stream_timepoints_v1` (11 columns → PERFECT MATCH)

Template has all 11 DB columns. No transforms needed.

```csv
timepoint_id,stream_id,timepoint_label,timepoint_type,anchor_event,timepoint_minutes,clock_time_hhmm,allowable_window_min,required,maps_to_measure,version
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `timepoint_id` | YES | TEXT | Unique timepoint ID |
| 2 | `stream_id` | YES | TEXT | FK to `profile_data_streams_v1.stream_id` |
| 3 | `timepoint_label` | — | TEXT | Human-readable label |
| 4 | `timepoint_type` | — | TEXT | `scheduled`, `event_driven`, `ad_hoc` |
| 5 | `anchor_event` | — | TEXT | E.g. `"chemotherapy_start"` |
| 6 | `timepoint_minutes` | — | INTEGER | Minutes from anchor |
| 7 | `clock_time_hhmm` | — | TEXT | Clock time if applicable |
| 8 | `allowable_window_min` | — | INTEGER | Allowable window in minutes |
| 9 | `required` | — | INTEGER | `1` = required, `0` = optional |
| 10 | `maps_to_measure` | — | TEXT | FK to measure |
| 11 | `version` | — | INTEGER | |

---

## 12. ontology_link_template.csv → `ontology_links_v1` (11 columns → PERFECT MATCH)

Template has all 11 DB columns. No transforms needed.

```csv
link_id,target_table,target_id,study_id,support_type,evidence_strength,snippet,locator,notes,version,active
```

| # | Column | Required | DB Type | Notes |
|---|--------|----------|---------|-------|
| 1 | `link_id` | YES | TEXT | Unique link ID |
| 2 | `target_table` | YES | TEXT | Which table this links to |
| 3 | `target_id` | YES | TEXT | Row ID in target table |
| 4 | `study_id` | YES | TEXT | FK to `study_registry_v1` |
| 5 | `support_type` | — | TEXT | E.g. `"hypothesis"`, `"confirmation"`, `"replication"` |
| 6 | `evidence_strength` | — | TEXT | `strong`, `moderate`, `weak` |
| 7 | `snippet` | — | TEXT | Verbatim quote |
| 8 | `locator` | — | TEXT | Page/section reference |
| 9 | `notes` | — | TEXT | |
| 10 | `version` | — | INTEGER | |
| 11 | `active` | — | INTEGER | `1` = active |

---

## Which Templates to Fill

### Core Evidence Templates (Per Paper)

| Mode | edge_evidence | population_norms | context_priors | temporal | instrument | correlation |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **DEEP** | ✅ | ✅ | ✅ | if available | if available | if available |
| **STANDARD** | ✅ | ✅ | ✅ | — | — | — |
| **SHALLOW** | ✅ | — | — | — | — | — |

### Extended Templates (Fill When Data Available)

| Template | Fill When... | DB Table |
|----------|-------------|----------|
| `dose_evidence_template.csv` | Paper reports dose-response data | `dose_evidence_v1` |
| `subgroup_evidence_template.csv` | Paper reports subgroup/interaction analyses | `subgroup_evidence_v1` |
| `study_cohort_profile_template.csv` | DEEP mode — detailed demographics | `study_cohort_profiles_v1` |
| `profile_data_stream_template.csv` | DEEP mode — measurement protocol details | `profile_data_streams_v1` |
| `stream_timepoint_template.csv` | DEEP mode — timepoint schedule details | `stream_timepoints_v1` |
| `ontology_link_template.csv` | Linking evidence to external ontologies | `ontology_links_v1` |

---

## Column Name Alignment Summary

All "old" column names from v1 templates have been retired. This table documents the
historical mapping for reference only — **DO NOT use old names in templates.**

| Old Template Name | DB Column Name (use this) | Template |
|------------------|---------------------------|----------|
| `edge_id` | `edge_relation_id` | edge_evidence |
| `beta_raw` | `effect_value_reported` | edge_evidence |
| `se_raw` | `se_reported` | edge_evidence |
| `effect_type_original` | `effect_type_reported` | edge_evidence |
| `sample_size` | `N_effect` | edge_evidence |
| `instrument_id` | `upstream_instrument_id` | edge_evidence |
| `confidence_note` | `notes` | edge_evidence |
| `ci_low` | `ci_low_reported` | edge_evidence |
| `ci_high` | `ci_high_reported` | edge_evidence |
| `sd_treatment` | `sd_x` | edge_evidence |
| `sd_control` | `sd_y` | edge_evidence |
| `cancer_validated` | `cancer_validation_status` | edge_evidence |
| `se_derivation_method` | `se_derivation_level` | edge_evidence |
| `mean` | `mean_raw` | population_norms |
| `sd` | `sd_raw` | population_norms |
| `sample_size` | `N` | population_norms |
| `prior_mean_z` | `mean` | context_priors |
| `prior_sd_z` | `sd` | context_priors |
| `edge_id` | `edge_relation_id` | temporal |
| `value` | `effect` | temporal |
| `sample_size` | `N` | temporal |
| `reliability_value` | `cronbachs_alpha` | instrument |
| `test_retest_icc` | `test_retest_reliability` | instrument |
| `sample_size` | `N` | instrument |
| `biomarker_id_1` | `node_a_id` | correlation |
| `biomarker_id_2` | `node_b_id` | correlation |
| `correlation_r` | `rho` | correlation |
| `sample_size` | `N` | correlation |

---

## 13. node_proposals_template.csv → `review_tasks` (15 extractor columns)

> **Purpose:** Structured proposal for nodes NOT yet in NODE_REGISTRY.csv. Used when a paper references a construct that cannot be mapped to any existing node. Proposals enter the `review_tasks` queue for human adjudication. Do NOT add nodes directly to NODE_REGISTRY during extraction — use this template instead.

```csv
doi,proposed_node_id,proposed_node_label,proposed_node_layer,proposed_clinical_domain,is_observable,is_latent,proposed_orientation,proposed_unit_of_measure,pathway_membership,proxy_for,justification,related_existing_nodes,example_instruments,source_quote,proposal_status
```

| # | Column | Required | Type | Notes |
|---|--------|----------|------|-------|
| 1 | `doi` | YES | TEXT | Paper DOI proposing this node |
| 2 | `proposed_node_id` | YES | TEXT | Follows `NODE_[DOMAIN]_[CONSTRUCT]` convention |
| 3 | `proposed_node_label` | YES | TEXT | Human-readable name |
| 4 | `proposed_node_layer` | YES | INTEGER | 0=Exogenous, 1=Behavior, 2=Biomarker, 3=Pathway, 4=Symptom, 5=Cognitive, 6=Composite |
| 5 | `proposed_clinical_domain` | YES | TEXT | e.g., inflammatory, neurotrophic, cognitive |
| 6 | `is_observable` | YES | INTEGER | 1 if directly measurable, 0 if latent |
| 7 | `is_latent` | YES | INTEGER | 1 if latent construct, 0 if observable |
| 8 | `proposed_orientation` | YES | TEXT | POS_UP, POS_DOWN, or CATEGORICAL |
| 9 | `proposed_unit_of_measure` | — | TEXT | e.g., pg/mL, z-score, hours/week |
| 10 | `pathway_membership` | — | TEXT | JSON array of pathway IDs, e.g., `["M1","M4"]` |
| 11 | `proxy_for` | — | TEXT | If this node proxies a latent, which node_id |
| 12 | `justification` | YES | TEXT | Why no existing node covers this construct |
| 13 | `related_existing_nodes` | YES | TEXT | Comma-separated list of similar nodes in registry |
| 14 | `example_instruments` | — | TEXT | Instruments that could measure this construct |
| 15 | `source_quote` | — | TEXT | Verbatim text from paper defining the construct |
| 16 | `proposal_status` | — | TEXT | Default: `pending`. Values: pending, approved, rejected, merged |

### Placeholder convention

When an edge CSV references a proposed (not-yet-approved) node, use `NODE_PENDING:<proposed_node_id>` as the node_id value. Example:
```
NODE_PENDING:NODE_BIO_IRISIN
```
The load pipeline will quarantine rows with `NODE_PENDING:` prefixes until the proposal is resolved.

### Adjudication outcomes

| Outcome | Action |
|---------|--------|
| **Approved** | Human adds node to NODE_REGISTRY.csv, replaces `NODE_PENDING:` refs, re-runs loader |
| **Rejected** | Human removes proposal; `NODE_PENDING:` edge rows are dropped or remapped |
| **Merged** | Construct is covered by existing node under different name; human remaps edge refs |

---

_Last updated: 2026-02-28. Authoritative source for all CSV template column definitions._
