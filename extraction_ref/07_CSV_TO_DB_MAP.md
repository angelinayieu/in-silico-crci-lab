# CSV → Database Column Mapping

> How CSV template columns map to database table columns.  
> The load script (`scripts/load_evidence_into_db.py`) performs these mappings.

---

## edge_evidence_template.csv → edge_evidence_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | Lookup via study_registry_v1 (doi → study_id) |
| `edge_id` | `edge_relation_id` | Direct |
| `beta_raw` | `effect_value_reported` | Direct |
| `se_raw` | `se_reported` | Direct |
| `effect_type_original` | `effect_type_reported` | Direct |
| `effect_size_type` | `effect_size_type` | Direct |
| `sample_size` | `N_effect` | Direct |
| `study_design` | `study_design` | Direct |
| `cancer_type` | `cancer_type` | Direct |
| `treatment_phase` | `treatment_phase` | Direct |
| `instrument_id` | `upstream_instrument_id` | Direct |
| `confidence_note` | `notes` | Direct |
| `ci_low` | `ci_low_reported` | Direct |
| `ci_high` | `ci_high_reported` | Direct |
| `p_value` | `p_value` | Direct |
| `n_treatment` | *(used for SE derivation)* | Not stored directly |
| `n_control` | *(used for SE derivation)* | Not stored directly |
| `sd_treatment` | `sd_x` | Direct |
| `sd_control` | `sd_y` | Direct |
| `cancer_validated` | `cancer_validation_status` | Direct (text) |
| `rob_overall` | `rob_overall` | Direct |
| `pub_year` | `pub_year` | Direct |
| `covariates_adjusted` | `covariates_adjusted` | Direct |
| `endpoint_vs_change` | `endpoint_vs_change` | Direct |
| `comparison_arm_label` | `comparison_arm_label` | Direct |
| `se_derivation_method` | `se_derivation_level` | Direct |
| `shared_control_flag` | `shared_control_flag` | Direct |
| `outcome_directionality` | *(used for harmonization)* | Pipeline |
| `beta_sign_convention` | *(used for harmonization)* | Pipeline |
| `timepoint_weeks` | *(links to temporal_evidence)* | |
| `effect_size_context` | `extraction_snippet` | Direct |
| `outcome_node_id` | `node_y` | Direct |

### Auto-Generated Columns (not in CSV)

| DB Column | How Generated |
|-----------|---------------|
| `ler_id` | `LER_{study_id}_{edge_id}_{span_hash}` |
| `profile_id` | `"PROFILE_DEFAULT"` (hardcoded; future: `{cancer_type}:{treatment_phase}`) |
| `entered_by` | `"manual_csv_import"` |
| `entered_at` | Current timestamp |
| `version` | `1` |
| `active` | `1` |
| `harmonized_beta` | Copied from `beta_raw` at load time (already clean effect sizes). Later overwritten by `harmonize_scales_to_cohens_d()` if scale is `mean_diff_raw`. |
| `harmonized_se` | Copied from `se_raw` at load time. Later overwritten with SD-borrowing inflation if applicable. |

---

## population_norms_template.csv → population_norms_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| `node_id` | `node_id` | Direct |
| `instrument_id` | `instrument_id` | Direct |
| `mean` | `mean_raw` | Direct |
| `sd` | `sd_raw` | Direct |
| `sample_size` | `N` | Direct |
| `cancer_type` | `cancer_type` | Direct |
| `treatment_phase` | `treatment_phase` | Direct |
| `age_range` | `population_descriptor` | Direct |

---

## context_priors_template.csv → node_priors_v1

> **Actual DB table:** `node_priors_v1` (NOT `context_priors_v1`)

| CSV Column | DB Column | Transform |
|-----------|-----------|----------|
| `doi` | *(used for provenance)* | Stored in `provenance` field |
| `node_id` | `node_id` | Direct |
| `cancer_type` | `cancer_type` | Direct |
| `treatment_phase` | `treatment_phase` | Direct |
| `prior_mean_z` | `mean` | Direct |
| `prior_sd_z` | `sd` | Direct |
| `source_type` | `provenance` | Direct |
| `n_contributing` | *(stored in notes)* | |
| `notes` | `notes` | Direct |

---

## temporal_evidence_template.csv → temporal_evidence_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| `edge_id` | `action_id` | Edge → action mapping |
| `timepoint_weeks` | `timepoint_weeks` | Direct |
| `value` | `effect` | Direct |
| `se` | `se` | Direct |
| `is_recovery` | `is_recovery` | Direct |
| `sample_size` | `N` | Direct |
| `provenance_ref` | `provenance_ref` | Direct |

---

## instrument_evidence_template.csv → instrument_evidence_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| `instrument_id` | `instrument_id` | Direct |
| `reliability_value` | `cronbachs_alpha` | Direct |
| `reliability_type` | *(routes to correct column)* | |
| `factor_loading_mean` | `factor_loading_mean` | Direct |
| `test_retest_icc` | `test_retest_reliability` | Direct |
| `sample_size` | `N` | Direct |
| `cancer_type` | `cancer_type` | Direct |
| `cancer_validated` | *(metadata)* | |
| `provenance_ref` | `provenance_ref` | Direct |

---

## correlation_template.csv → biomarker_correlations_v1

> **Note:** The DB table is `biomarker_correlations_v1` (not `correlation_evidence_v1`).

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `source_citation` | `"doi:{value}"` (or `provenance_ref` if set) |
| `biomarker_id_1` | `node_a_id` | Direct |
| `biomarker_id_2` | `node_b_id` | Direct |
| `correlation_r` | `rho` | Direct |
| `sample_size` | *(used for `rho_se` derivation)* | SE ≈ (1 − r²) / √(n − 2) |
| `partial_or_zero` | *(stored in `notes`)* | |
| `population` | *(stored in `notes`)* | |
| `provenance_ref` | `source_citation` | Direct |

### Auto-Generated Columns

| DB Column | How Generated |
|-----------|---------------|
| `correlation_id` | `CORR_{sha256(study_id|node_a|node_b)[:12]}` |
| `rho_se` | `(1 - r²) / √(n - 2)` |
| `d_block` | Derived from node prefixes (e.g. `"BC"` for BIO↔COG) |
| `is_decision_critical` | `0` (default) |

---dose_evidence_template.csv → dose_evidence_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `id` | `id` | Auto-generated if blank |
| `study_id` | `study_id` | DOI → study_id lookup |
| `extraction_run_id` | `extraction_run_id` | Direct |
| `action_id` | `action_id` | FK to action_catalog_v1 |
| `intervention_type` | `intervention_type` | Direct |
| `dose_level` | `dose_level` | Direct |
| `dose_unit` | `dose_unit` | Direct |
| `effect` | `effect` | Direct |
| `se` | `se` | Direct |
| `N` | `N` | Direct |
| `dose_response_shape` | `dose_response_shape` | Direct |
| `effective_dose_range` | `effective_dose_range` | Direct |
| `maximum_tolerated_dose` | `maximum_tolerated_dose` | Direct |
| `provenance_status` | `provenance_status` | Direct |
| `provenance_ref` | `provenance_ref` | Direct |
| `notes` | `notes` | Direct |
| `version` | `version` | Direct |

---

## subgroup_evidence_template.csv → subgroup_evidence_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `id` | `id` | Auto-generated if blank |
| `study_id` | `study_id` | DOI → study_id lookup |
| `extraction_run_id` | `extraction_run_id` | Direct |
| `edge_id` | `edge_id` | FK to edge_relations_definitions_v1 |
| `modifier_variable` | `modifier_variable` | Direct |
| `modifier_value` | `modifier_value` | Direct |
| `interaction_beta` | `interaction_beta` | Direct |
| `interaction_se` | `interaction_se` | Direct |
| `interaction_p` | `interaction_p` | Direct |
| `subgroup_effect` | `subgroup_effect` | Direct |
| `subgroup_se` | `subgroup_se` | Direct |
| `subgroup_n` | `subgroup_n` | Direct |
| `provenance_status` | `provenance_status` | Direct |
| `provenance_ref` | `provenance_ref` | Direct |
| `notes` | `notes` | Direct |
| `version` | `version` | Direct |

---

## study_cohort_profile_template.csv → study_cohort_profiles_v1

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `profile_id` | `profile_id` | Direct |
| `study_id` | `study_id` | DOI → study_id lookup |
| `cohort_label` | `cohort_label` | Direct |
| `analysis_timepoint` | `analysis_timepoint` | Direct |
| `N_analyzed` | `N_analyzed` | Direct |
| `N_enrolled` | `N_enrolled` | Direct |
| `sex_female_pct` | `sex_female_pct` | Direct |
| `age_mean` | `age_mean` | Direct |
| `age_sd` | `age_sd` | Direct |
| `cancer_type` | `cancer_type` | Direct |
| `treatment_phase` | `treatment_phase` | Direct |
| *(+ 12 more demographic columns)* | *(direct mapping)* | See `05_DB_SCHEMA.md` |

---

## profile_data_stream_template.csv → profile_data_streams_v1

Direct column mapping. 25 columns total. See `05_DB_SCHEMA.md` for full schema.

---

## stream_timepoint_template.csv → stream_timepoints_v1

Direct column mapping. 11 columns total. See `05_DB_SCHEMA.md` for full schema.

---

## ontology_link_template.csv → ontology_links_v1

Direct column mapping. 11 columns total. See `05_DB_SCHEMA.md` for full schema.

---

## 

## Load Command

```bash
cd /workspaces/in-silico-crci-lab
python scripts/load_evidence_into_db.py
```

The script auto-discovers all CSVs in `data/manual_uploads/structured/*/` subfolders.
