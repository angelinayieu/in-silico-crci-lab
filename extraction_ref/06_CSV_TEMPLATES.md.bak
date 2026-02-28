# CSV Template Column Specifications

> Exact column headers for each CSV template in `data/templates/`.  
> Copy templates to `data/manual_uploads/structured/<doi-slug>/` before filling.

---

## edge_evidence_template.csv (32 columns)

```
doi,edge_id,beta_raw,se_raw,effect_type_original,effect_size_type,sample_size,
study_design,cancer_type,treatment_phase,instrument_id,confidence_note,ci_low,
ci_high,p_value,n_treatment,n_control,sd_treatment,sd_control,cancer_validated,
rob_overall,pub_year,covariates_adjusted,endpoint_vs_change,comparison_arm_label,
se_derivation_method,shared_control_flag,outcome_directionality,beta_sign_convention,
timepoint_weeks,effect_size_context,outcome_node_id
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | Paper DOI |
| `edge_id` | YES | text | Must exist in EDGE_REGISTRY |
| `beta_raw` | YES | float | Effect size value |
| `se_raw` | YES | float | Standard error |
| `effect_type_original` | YES | enum | cohens_d, mean_diff, odds_ratio, etc. |
| `effect_size_type` | YES | enum | BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE |
| `sample_size` | YES | int | Total N in analysis |
| `study_design` | YES | enum | RCT, cohort, etc. |
| `cancer_type` | YES | enum | breast, mixed, etc. |
| `treatment_phase` | YES | enum | active_treatment, etc. |
| `instrument_id` | YES | text | Must exist in INSTRUMENT_REGISTRY |
| `confidence_note` | — | text | Free text: derivation notes, concerns |
| `ci_low` | — | float | 95% CI lower bound |
| `ci_high` | — | float | 95% CI upper bound |
| `p_value` | — | float | Reported p-value |
| `n_treatment` | — | int | Treatment arm N |
| `n_control` | — | int | Control arm N |
| `sd_treatment` | — | float | SD in treatment group |
| `sd_control` | — | float | SD in control group |
| `cancer_validated` | — | bool | Instrument validated in cancer? |
| `rob_overall` | — | enum | low / moderate / high / critical |
| `pub_year` | — | int | Publication year |
| `covariates_adjusted` | — | text | Comma-separated covariate list |
| `endpoint_vs_change` | — | enum | endpoint / change |
| `comparison_arm_label` | — | text | e.g. "HIIT vs CON" |
| `se_derivation_method` | — | enum | reported / from_ci / from_p_value / etc. |
| `shared_control_flag` | — | bool | True if control arm shared across comparisons |
| `outcome_directionality` | — | text | higher_better / lower_better |
| `beta_sign_convention` | — | text | positive_is_benefit / as_reported |
| `timepoint_weeks` | — | float | Assessment timepoint in weeks |
| `effect_size_context` | — | text | Free text context |
| `outcome_node_id` | — | text | Target node (usually same as edge target) |

---

## population_norms_template.csv (9 columns)

```
doi,node_id,instrument_id,mean,sd,sample_size,cancer_type,treatment_phase,age_range
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | Paper DOI |
| `node_id` | YES | text | Must exist in NODE_REGISTRY |
| `instrument_id` | YES | text | Must exist in INSTRUMENT_REGISTRY |
| `mean` | YES | float | Baseline/pre-treatment mean |
| `sd` | YES | float | SD of mean (SD > 0) |
| `sample_size` | YES | int | N contributing to estimate |
| `cancer_type` | YES | enum | |
| `treatment_phase` | YES | enum | |
| `age_range` | — | text | e.g. "45-65" |

---

## context_priors_template.csv (9 columns)

```
doi,node_id,cancer_type,treatment_phase,prior_mean_z,prior_sd_z,source_type,n_contributing,notes
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | |
| `node_id` | YES | text | |
| `cancer_type` | YES | enum | |
| `treatment_phase` | YES | enum | |
| `prior_mean_z` | YES | float | z-score relative to population norm |
| `prior_sd_z` | YES | float | Uncertainty (typically 0.5) |
| `source_type` | YES | enum | published_norm / local_control_group / expert |
| `n_contributing` | — | int | Studies contributing to prior |
| `notes` | — | text | Derivation notes |

---

## temporal_evidence_template.csv (8 columns)

```
doi,edge_id,timepoint_weeks,value,se,is_recovery,sample_size,provenance_ref
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | |
| `edge_id` | YES | text | Must exist in EDGE_REGISTRY |
| `timepoint_weeks` | YES | float | Weeks from baseline |
| `value` | YES | float | Effect at this timepoint |
| `se` | YES | float | SE at this timepoint |
| `is_recovery` | YES | int | 0 = intervention period, 1 = recovery/follow-up |
| `sample_size` | YES | int | N at this timepoint |
| `provenance_ref` | — | text | Table/figure reference in paper |

---

## instrument_evidence_template.csv (10 columns)

```
doi,instrument_id,reliability_value,reliability_type,factor_loading_mean,test_retest_icc,sample_size,cancer_type,cancer_validated,provenance_ref
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | |
| `instrument_id` | YES | text | Must exist in INSTRUMENT_REGISTRY |
| `reliability_value` | YES | float | Cronbach's α or equivalent |
| `reliability_type` | YES | enum | cronbachs_alpha / split_half / test_retest |
| `factor_loading_mean` | — | float | Mean factor loading |
| `test_retest_icc` | — | float | |
| `sample_size` | YES | int | |
| `cancer_type` | YES | enum | |
| `cancer_validated` | YES | bool | |
| `provenance_ref` | — | text | |

---

## correlation_template.csv (8 columns)

```
doi,biomarker_id_1,biomarker_id_2,correlation_r,sample_size,partial_or_zero,population,provenance_ref
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `doi` | YES | text | |
| `biomarker_id_1` | YES | text | Node ID 1 |
| `biomarker_id_2` | YES | text | Node ID 2 |
| `correlation_r` | YES | float | Pearson/Spearman r |
| `sample_size` | YES | int | |
| `partial_or_zero` | YES | enum | partial / zero_order |
| `population` | — | text | Description |
| `provenance_ref` | — | text | |

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

## dose_evidence_template.csv (17 columns)

```
id,study_id,extraction_run_id,action_id,intervention_type,dose_level,dose_unit,effect,se,N,dose_response_shape,effective_dose_range,maximum_tolerated_dose,provenance_status,provenance_ref,notes,version
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `id` | — | text | Auto-generated if blank |
| `study_id` | YES | text | DOI or study_id |
| `extraction_run_id` | — | text | |
| `action_id` | YES | text | FK to action_catalog_v1 |
| `intervention_type` | YES | text | e.g. aerobic_exercise, resistance_training |
| `dose_level` | YES | float | Dose amount (e.g. 150 for 150 min/wk) |
| `dose_unit` | YES | text | e.g. min_per_week, sessions_per_week |
| `effect` | YES | float | Effect size at this dose level |
| `se` | YES | float | SE of effect |
| `N` | YES | int | Sample size |
| `dose_response_shape` | — | text | linear / U_shaped / threshold / plateau |
| `effective_dose_range` | — | text | e.g. "90-180 min/wk" |
| `maximum_tolerated_dose` | — | text | |
| `provenance_status` | — | text | |
| `provenance_ref` | — | text | Table/figure reference |
| `notes` | — | text | |
| `version` | — | int | |

---

## subgroup_evidence_template.csv (16 columns)

```
id,study_id,extraction_run_id,edge_id,modifier_variable,modifier_value,interaction_beta,interaction_se,interaction_p,subgroup_effect,subgroup_se,subgroup_n,provenance_status,provenance_ref,notes,version
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `id` | — | text | Auto-generated if blank |
| `study_id` | YES | text | DOI or study_id |
| `extraction_run_id` | — | text | |
| `edge_id` | YES | text | Must exist in EDGE_REGISTRY |
| `modifier_variable` | YES | text | e.g. APOE_status, age_group, sex |
| `modifier_value` | YES | text | e.g. e4_carrier, >65, female |
| `interaction_beta` | — | float | Interaction (modifier × treatment) effect |
| `interaction_se` | — | float | |
| `interaction_p` | — | float | |
| `subgroup_effect` | — | float | Subgroup-specific point estimate |
| `subgroup_se` | — | float | |
| `subgroup_n` | — | int | Subgroup sample size |
| `provenance_status` | — | text | |
| `provenance_ref` | — | text | |
| `notes` | — | text | |
| `version` | — | int | |

---

## study_cohort_profile_template.csv (24 columns)

```
profile_id,study_id,cohort_label,analysis_timepoint,N_analyzed,N_enrolled,recruitment_region,recruitment_sites,collection_calendar_start,collection_calendar_end,enrollment_window_text,eligibility_inclusion,eligibility_exclusion,sex_female_pct,age_mean,age_sd,education_years_mean,education_years_sd,bmi_mean,bmi_sd,cancer_type,treatment_phase,time_since_treatment_text,notes,version
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `profile_id` | YES | text | Unique cohort profile ID |
| `study_id` | YES | text | DOI or study_id |
| `cohort_label` | YES | text | e.g. "HIIT arm", "Control" |
| `analysis_timepoint` | — | text | e.g. "baseline", "12-week" |
| `N_analyzed` | YES | int | Actual N in analysis |
| `N_enrolled` | — | int | Enrolled N |
| `recruitment_region` | — | text | |
| `recruitment_sites` | — | text | |
| `collection_calendar_start` | — | text | |
| `collection_calendar_end` | — | text | |
| `enrollment_window_text` | — | text | |
| `eligibility_inclusion` | — | text | |
| `eligibility_exclusion` | — | text | |
| `sex_female_pct` | — | float | |
| `age_mean` | — | float | |
| `age_sd` | — | float | |
| `education_years_mean` | — | float | |
| `education_years_sd` | — | float | |
| `bmi_mean` | — | float | |
| `bmi_sd` | — | float | |
| `cancer_type` | YES | text | |
| `treatment_phase` | YES | text | |
| `time_since_treatment_text` | — | text | |
| `notes` | — | text | |
| `version` | — | int | |

---

## profile_data_stream_template.csv (Detailed — Load On Demand)

> Used for detailed measurement protocol documentation in DEEP mode.  
> Most papers won't need this. See `05_DB_SCHEMA.md` § profile_data_streams_v1 for all 25 columns.

---

## stream_timepoint_template.csv (Detailed — Load On Demand)

> Used for scheduled timepoint documentation in DEEP mode.  
> See `05_DB_SCHEMA.md` § stream_timepoints_v1 for all 11 columns.

---

## ontology_link_template.csv (Detailed — Load On Demand)

> Used for linking evidence to external ontology/classification systems.  
> See `05_DB_SCHEMA.md` § ontology_links_v1 for all 11 columns.
