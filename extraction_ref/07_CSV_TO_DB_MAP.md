# CSV → Database Column Mapping

> **Post-alignment**: CSV template columns match DB table columns exactly.
> The only non-DB column in most templates is `doi` — resolved to `study_id` by the importer.
> This file documents the transforms and auto-generated columns for each of the 12 templates.

---

## Governing Principle: Direct Mapping

```
CSV column name == DB column name
```

All 12 CSV templates use **DB column names directly**. There are zero renames.
The importer's job is limited to:

1. **`doi` → `study_id`**: Lookup DOI in `study_registry_v1` to get the internal study_id
2. **Auto-generated columns**: `ler_id`, `prior_id`, `correlation_id`, `span_hash`, etc.
3. **Computed columns**: `harmonized_beta`, `harmonized_se`, `se_eff` — set by downstream pipeline stages

> **See `06_CSV_TEMPLATES.md` for the authoritative column-by-column specification.**
> This file focuses on transform logic and auto-generation rules.

---

## 1. edge_evidence_template.csv → `edge_evidence_v1`

| Extractor Columns | 28 |
|---|---|
| DB Total Columns | 107 |
| Auto-Generated | ~79 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | Lookup via `study_registry_v1` |
| *(all other 27 columns)* | *(same name)* | Direct pass-through |

### Auto-Generated Columns (not in CSV)

| DB Column | How Generated |
|-----------|---------------|
| `ler_id` | `LER_{study_id}_{edge_relation_id}_{span_hash}` |
| `edge_param_id` | `EP_{edge_relation_id}_{span_hash[:8]}` |
| `edge_family` | Looked up from `edge_relations_definitions_v1` |
| `node_x` | Looked up from `edge_relations_definitions_v1` |
| `node_y` | Looked up from `edge_relations_definitions_v1` |
| `profile_id` | `"PROFILE_DEFAULT"` |
| `harmonized_beta` | Initially = `effect_value_reported`; later overwritten by scale harmonizer (Step 4c) |
| `harmonized_se` | Initially = `se_reported`; later overwritten by SE calibrator (Step 4c) |
| `harmonization_status` | `"harmonized"` |
| `harmonized_scale` | Inferred from `effect_type_reported` |
| `se_eff` | Computed by 7-layer SE calibration (Step 4d) |
| `se_quality_tag` | `"manual_extraction"` |
| `identification_status` | `"plausible"` |
| `quality_rating` | = `rob_overall` or `"moderate"` |
| `span_hash` | SHA-256 of (study_id, edge_relation_id, effect_value_reported, se_reported, N_effect) |
| `entered_by` | `"manual_csv_import"` |
| `entered_at` | Current UTC timestamp |
| `version` | `1` |
| `active` | `1` |
| `outcome_type` | `"semi_objective"` (default) |

---

## 2. population_norms_template.csv → `population_norms_v1`

| Extractor Columns | 9 |
|---|---|
| DB Total Columns | 21 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| *(all other 8 columns)* | *(same name)* | Direct |

### Auto-Generated

| DB Column | How Generated |
|-----------|---------------|
| `id` | UUID |
| `study_id` | From `doi` lookup |
| `extraction_run_id` | Current run ID |
| `instrument_name` | Looked up from `instrument_definitions_v1` |
| `cognitive_domain` | Inferred from `node_id` |
| `population_descriptor` | Auto-composed |
| `mean_z`, `sd_z` | Computed later from raw + norms |
| `percentile` | Computed |
| `provenance_status` | `"manual_extraction"` |
| `provenance_ref` | From doi |
| `created_at` | UTC timestamp |
| `version` | `1` |

---

## 3. context_priors_template.csv → `node_priors_v1`

> ⚠️ Target table is `node_priors_v1` (NOT `context_priors_v1`)

| Extractor Columns | 9 |
|---|---|
| DB Total Columns | 14 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `provenance` | Stored as `"doi:{value}; source_type:{source_type}"` |
| `source_type` | `provenance` | Appended to provenance string |
| `n_contributing` | `notes` | Folded into notes |
| `mean` | `mean` | Direct (z-score value) |
| `sd` | `sd` | Direct (uncertainty value) |
| *(node_id, cancer_type, treatment_phase)* | *(same name)* | Direct |

### Auto-Generated

| DB Column | How Generated |
|-----------|---------------|
| `prior_id` | `NP_{node_id}_{cancer_type}_{treatment_phase}_{hash}` |
| `prior_space` | `"z_score"` |
| `dist_family` | `"normal"` |
| `scope_filters_json` | JSON from cancer_type + treatment_phase |
| `specificity_rank` | Computed from scope specificity |
| `active` | `1` |
| `version` | `1` |

---

## 4. temporal_evidence_template.csv → `temporal_evidence_v1`

| Extractor Columns | 8 |
|---|---|
| DB Total Columns | 19 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| `edge_relation_id` | `action_id` | Edge → action mapping via edge_relations_definitions_v1 |
| *(all other 6 columns)* | *(same name)* | Direct |

### Auto-Generated

| DB Column | How Generated |
|-----------|---------------|
| `id` | UUID |
| `study_id` | From `doi` lookup |
| `extraction_run_id` | Current run ID |
| `action_id` | Mapped from `edge_relation_id` |
| `intervention_type` | Inferred from edge family |
| `study_design` | From study_registry |
| `onset_observed`, `peak_observed`, `decay_observed` | Computed from trajectory |
| `provenance_status` | `"manual_extraction"` |
| `created_at` | UTC timestamp |
| `version` | `1` |

---

## 5. instrument_evidence_template.csv → `instrument_evidence_v1`

| Extractor Columns | 15 |
|---|---|
| DB Total Columns | 25 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `study_id` | DOI → study_id lookup |
| *(all other 14 columns)* | *(same name)* | Direct |

### Auto-Generated

| DB Column | How Generated |
|-----------|---------------|
| `id` | UUID |
| `study_id` | From `doi` lookup |
| `extraction_run_id` | Current run ID |
| `population_descriptor` | Auto-composed |
| `factor_loading_per_subscale` | JSON (nullable) |
| `convergent_validity` | (nullable) |
| `discriminant_validity` | (nullable) |
| `factor_structure` | (nullable) |
| `measurement_invariance` | (nullable) |
| `provenance_status` | `"manual_extraction"` |
| `created_at` | UTC timestamp |
| `version` | `1` |

---

## 6. correlation_template.csv → `biomarker_correlations_v1`

> ⚠️ Target table is `biomarker_correlations_v1` (NOT `correlation_evidence_v1`)

| Extractor Columns | 6 |
|---|---|
| DB Total Columns | 11 |

### Transforms

| CSV Column | DB Column | Transform |
|-----------|-----------|-----------|
| `doi` | `source_citation` | `"doi:{value}"` |
| `partial_or_zero` | `d_block` | Derived from value + node prefixes |
| *(node_a_id, node_b_id, rho, N)* | *(same name or used in computation)* | Direct |

### Auto-Generated

| DB Column | How Generated |
|-----------|---------------|
| `correlation_id` | `CORR_{sha256(study_id\|node_a_id\|node_b_id)[:12]}` |
| `rho_se` | `(1 - rho²) / √(N - 2)` |
| `d_block` | From `partial_or_zero` + node prefixes |
| `source_citation` | `"doi:{doi}"` |
| `is_decision_critical` | `0` |
| `version` | `1` |
| `active` | `1` |

> **Note:** `N` is consumed to compute `rho_se` but is NOT a direct DB column.

---

## 7–12. Direct-Mapping Templates

These templates use DB column names with minimal transformation:

| # | Template | DB Table | Ext Cols | DB Cols | Only Transform |
|---|----------|----------|----------|---------|----------------|
| 7 | `dose_evidence_template.csv` | `dose_evidence_v1` | 17 | 18 | `created_at` auto-set |
| 8 | `subgroup_evidence_template.csv` | `subgroup_evidence_v1` | 16 | 17 | `created_at` auto-set |
| 9 | `study_cohort_profile_template.csv` | `study_cohort_profiles_v1` | 25 | 33 | 8 JSONB cols set programmatically |
| 10 | `profile_data_stream_template.csv` | `profile_data_streams_v1` | 21 | 25 | 4 cols auto-set |
| 11 | `stream_timepoint_template.csv` | `stream_timepoints_v1` | 11 | 11 | **PERFECT MATCH** — zero transforms |
| 12 | `ontology_link_template.csv` | `ontology_links_v1` | 11 | 11 | **PERFECT MATCH** — zero transforms |

---

## Load Command

```bash
cd /workspaces/in-silico-crci-lab
python scripts/load_evidence_into_db.py --verbose
```

The script auto-discovers all CSVs in `data/manual_uploads/structured/*/` subfolders.

### Pipeline Step Reference

| Step | Transform | Tables |
|------|-----------|--------|
| 3 | Register studies from meta.json | `study_registry_v1` |
| 4 | Load edge_evidence CSVs (doi → study_id, auto-gen IDs) | `edge_evidence_v1` |
| 4b | Load 11 auxiliary CSVs via family importers | All other 11 tables |
| 4c | Harmonize scales to Cohen's d (SD borrowing) | `edge_evidence_v1` in-place |
| 4d | 7-layer SE_eff calibration | `edge_evidence_v1` in-place |
| 6 | IVW aggregation → compiled edges | `edges_v1` |

---

_Last updated: 2026-02-28. Consistent with `06_CSV_TEMPLATES.md`._
