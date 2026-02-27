# Table Fill Master Reference

> **Last verified:** 2026-02-27 against actual `crci_dev.db` and `load_evidence_into_db.py`  
> **Canonical detailed reference:** [docs/03_database/TABLE_FILL_ORDER.md](../docs/03_database/TABLE_FILL_ORDER.md)

---

## Summary

| Metric | Value |etric | Value |
|--------|-------||--------|-------|
| Total tables in DB | 83 |
| Currently populated | 19 || Currently populated | 19 |
| Seed-loadable (SEED_TABLE_MAP) | 33 | 33 |
| Family importers wired | 11 |
| Pipeline steps | 12 (Steps 1, 1b, 1c, 2, 3, 4, 4b, 4c, 4d, 5, 5b, 6, 7) | 5, 5b, 6, 7) |

------

## Category S — Seed/Reference Tables (Class A, Pre-Loaded)## Category S — Seed/Reference Tables (Class A, Pre-Loaded)

Loaded by `crci/database/seed_loader.py` or `scripts/load_evidence_into_db.py` Steps 1/1b/1c/5/5b.Loaded by `crci/database/seed_loader.py` or `scripts/load_evidence_into_db.py` Steps 1/1b/1c/5/5b.

| Table | Rows | Source | Loader |ource | Loader |
|-------|------|--------|--------|---|--------|
| `edge_relations_definitions_v1` | 141 | `registries/EDGE_REGISTRY.csv` | Step 1 reseed |ns_v1` | 141 | `registries/EDGE_REGISTRY.csv` | Step 1 reseed |
| `biomarker_node_definitions_v1` | 63 | `registries/NODE_REGISTRY.csv` | Step 1b reseed |itions_v1` | 63 | `registries/NODE_REGISTRY.csv` | Step 1b reseed |
| `instrument_definitions_v1` | 67 | `registries/INSTRUMENT_REGISTRY.csv` | Step 1b reseed |_v1` | 67 | `registries/INSTRUMENT_REGISTRY.csv` | Step 1b reseed |
| `measure_definitions_v1` | 82 | `registries/MEASURE_REGISTRY.csv` | Step 1c reseed || 82 | `registries/MEASURE_REGISTRY.csv` | Step 1c reseed |
| `pathways_v1` | 22 | `registries/PATHWAY_REGISTRY.csv` | Step 1c reseed |`registries/PATHWAY_REGISTRY.csv` | Step 1c reseed |
| `action_catalog_v1` | 8 | `seeds/actions.csv` | Step 5 || `action_catalog_v1` | 8 | `seeds/actions.csv` | Step 5 |
| `dose_bridges_v1` | 10 | `seeds/dose_bridges.csv` | Step 5b |dose_bridges_v1` | 10 | `seeds/dose_bridges.csv` | Step 5b |
| `baseline_modifier_definitions_v1` | 15 | `seeds/modifier_rules.csv` | seed_loader || `baseline_modifier_definitions_v1` | 15 | `seeds/modifier_rules.csv` | seed_loader |
| `predictor_alignment_rules_v1` | 7 | `seeds/predictor_alignment_rules.csv` | seed_loader |ment_rules_v1` | 7 | `seeds/predictor_alignment_rules.csv` | seed_loader |
| `action_contraindication_links_v1` | 6 | `seeds/action_contraindication_links.csv` | seed_loader || `action_contraindication_links_v1` | 6 | `seeds/action_contraindication_links.csv` | seed_loader |
| `variable_to_input_map_v1` | 12 | `seeds/variable_to_input_map.csv` | seed_loader | | 12 | `seeds/variable_to_input_map.csv` | seed_loader |

### Registered but empty (CSV seeds not yet created)

These have SEED_TABLE_MAP entries but no CSV files on disk yet:

| Table | Seed CSV | Priority |
|-------|----------|----------|
| `observation_noise_v1` | `observation_noise.csv` | HIGH — needed for Algorithm Chain C |
| `normalization_refs_v1` | `normalization_refs.csv` | HIGH — needed for z-score normalization || `normalization_refs_v1` | `normalization_refs.csv` | HIGH — needed for z-score normalization |
| `intervention_kernels_v1` | `intervention_kernels.csv` | HIGH — needed for temporal prediction |intervention_kernels_v1` | `intervention_kernels.csv` | HIGH — needed for temporal prediction |
| `recovery_trajectories_v1` | `recovery_trajectories.csv` | MEDIUM || `recovery_trajectories_v1` | `recovery_trajectories.csv` | MEDIUM |
| `harmonization_rules_v1` | `harmonization_rules.csv` | MEDIUM |monization_rules.csv` | MEDIUM |
| `mid_thresholds_v1` | `mid_thresholds.csv` | MEDIUM || `mid_thresholds_v1` | `mid_thresholds.csv` | MEDIUM |
| `literary_constraints_v1` | `literary_constraints.csv` | LOW | | LOW |
| `literary_mechanistic_priors_v1` | `literary_priors.csv` | LOW || `literary_mechanistic_priors_v1` | `literary_priors.csv` | LOW |
| `contraindication_rules_v1` | `contraindication_rules.csv` | LOW (runtime) |dication_rules.csv` | LOW (runtime) |
| + 10 more | See SEED_TABLE_MAP (33 total entries) | Various |ious |

---

## Category X — Extracted Evidence (Per-Paper, Manual CSV → DB)r, Manual CSV → DB)

Loaded by `scripts/load_evidence_into_db.py` Steps 4 and 4b.

### Step 4: Edge evidence (direct CSV loading)

| Table | Rows | Template CSV | Notes |
|-------|------|-------------|-------|
| `edge_evidence_v1` | 18 | `edge_evidence_template.csv` (32 cols) | Core evidence. Step 4 loads + Step 4c harmonizes + Step 4d calibrates SE |. Step 4 loads + Step 4c harmonizes + Step 4d calibrates SE |
| `study_registry_v1` | 4 | *(auto-discovered from DOIs)* | Step 3 registers studies |

### Step 4b: Family CSVs (11 importers via `crci/extraction/family_importers.py`)ers via `crci/extraction/family_importers.py`)

| Table | Rows | Template CSV | Importer |
|-------|------|-------------|----------|
| `node_priors_v1` | 9 | `context_priors_template.csv` | `import_context_prior` |s_template.csv` | `import_context_prior` |
| `population_norms_v1` | 13 | `population_norms_template.csv` | `import_population_norm` |population_norms_v1` | 13 | `population_norms_template.csv` | `import_population_norm` |
| `temporal_evidence_v1` | 16 | `temporal_evidence_template.csv` | `import_temporal_evidence` || `temporal_evidence_v1` | 16 | `temporal_evidence_template.csv` | `import_temporal_evidence` |
| `instrument_evidence_v1` | 9 | `instrument_evidence_template.csv` | `import_instrument_evidence` |instrument_evidence_v1` | 9 | `instrument_evidence_template.csv` | `import_instrument_evidence` |
| `biomarker_correlations_v1` | 0 | `correlation_template.csv` | `import_correlation` || `biomarker_correlations_v1` | 0 | `correlation_template.csv` | `import_correlation` |
| `study_cohort_profiles_v1` | 0 | `study_cohort_profile_template.csv` | `import_study_cohort_profile` |_cohort_profile_template.csv` | `import_study_cohort_profile` |
| `profile_data_streams_v1` | 0 | `profile_data_stream_template.csv` | `import_profile_data_stream` || `profile_data_streams_v1` | 0 | `profile_data_stream_template.csv` | `import_profile_data_stream` |
| `stream_timepoints_v1` | 0 | `stream_timepoint_template.csv` | `import_stream_timepoint` |imepoint` |
| `ontology_links_v1` | 0 | `ontology_link_template.csv` | `import_ontology_link` |y_link` |
| `dose_evidence_v1` | 0 | `dose_evidence_template.csv` | `import_dose_evidence` |` |
| `subgroup_evidence_v1` | 0 | `subgroup_evidence_template.csv` | `import_subgroup_evidence` |

> **Important table name mappings:**
> - CSV template `context_priors_template.csv` → DB table `node_priors_v1` (NOT `context_priors_v1`)ext_priors_v1`)
> - CSV template `correlation_template.csv` → DB table `biomarker_correlations_v1` (NOT `correlation_evidence_v1`)rker_correlations_v1` (NOT `correlation_evidence_v1`)

### Compiled tables (pipeline-generated from evidence)### Compiled tables (pipeline-generated from evidence)

| Table | Rows | Generated By | Notes |
|-------|------|-------------|-------|
| `edges_v1` | 15 | Step 6 (IVW aggregation) | Compiled from all edge_evidence_v1 rows |
| `acquisition_queue_v1` | 15 | Retrieval pipeline | Auto-populated |

---

## Category P — Pipeline/Extraction Tables (Automated, Not Manual)

Written by the extraction pipeline (EX-P0 through EX-P6) when fully operational:EX-P6) when fully operational:

| Table | Written By | Status |
|-------|-----------|--------|
| `extraction_runs` | Pipeline orchestrator | 0 rows || `extraction_runs` | Pipeline orchestrator | 0 rows |
| `study_annotations_v1` | EX-P1 (LLM extraction) | 0 rows |X-P1 (LLM extraction) | 0 rows |
| `study_annotations_raw_v1` | EX-P1 (raw output) | 0 rows |) | 0 rows |
| `edge_param_builds_v1` | EX-P4 aggregation | 0 rows |
| `build_manifests_v1` | Build system | 0 rows |
| `publication_bias_results_v1` | EX-P4B | 0 rows |
| `chain_validation_results_v1` | EX-P5 | 0 rows || `chain_validation_results_v1` | EX-P5 | 0 rows |
| `extraction_completeness_v1` | EX-P5 | 0 rows |
| `extraction_audit_v1` | All stages | 0 rows |
| `review_tasks` | Trust boundary | 0 rows |
| `triangulation_sets_v1` | Extended extraction | 0 rows |
| `triangulation_members_v1` | Extended extraction | 0 rows |s |
| `triangulation_evidence_v1` | Extended extraction | 0 rows |
| `pathway_biomarkers_v1` | Extended extraction | 0 rows |

---

## Category D — Design/Policy Tables (Human-Authored, Pre-Runtime)

Must be authored before the algorithm engine can run:t be authored before the algorithm engine can run:

| Table | Purpose | Priority | Rows |
|-------|---------|----------|------||-------|---------|----------|------|
| `safety_policies_v1` | Safety triggers | Before runtime | 0 |
| `escalation_policies_v1` | Escalation protocols | Before runtime | 0 |
| `contraindication_rules_v1` | Hard safety blocks | Before runtime | 0 |time | 0 |
| `objective_specs_v1` | SAFE score weights | Before Stage G | 0 |ts | Before Stage G | 0 |
| `status_quo_rules_v1` | Baseline dose assumptions | Before Stage D | 0 || `status_quo_rules_v1` | Baseline dose assumptions | Before Stage D | 0 |
| `voi_rules_v1` | VOI question policy | Before Stage H | 0 |
| `question_bank_v1` | Adaptive questions | Before Stage H | 0 |
| `question_observation_models_v1` | Answer → state updates | Before Stage H | 0 || `question_observation_models_v1` | Answer → state updates | Before Stage H | 0 |
| `state_estimator_specs_v1` | Bayesian config | Before Stage C | 0 |0 |
| `derived_feature_definitions_v1` | Feature specs | Before Stage B | 0 || `derived_feature_definitions_v1` | Feature specs | Before Stage B | 0 |
| `mid_thresholds_v1` | Clinical thresholds | Before Stage I | 0 | 0 |
| `outcome_anchors_v1` | z→clinical calibration | Before Stage I | 0 |e I | 0 |
| `description_templates_v1` | UI templates | Before presentation | 0 |
| `validation_rules_v1` | QA rules | QA support | 0 |
| `feedback_loops_v1` | Cycle detection | Before Stage F | 0 |
| `pathway_interactions_v1` | Pathway effects | Before Stage F | 0 || `pathway_interactions_v1` | Pathway effects | Before Stage F | 0 |

------

## Category R — Runtime Tables (Append-Only, Never Manual)## Category R — Runtime Tables (Append-Only, Never Manual)

Written by the algorithm engine during each recommendation run:n:

| Table | Algorithm Stage | Rows || Table | Algorithm Stage | Rows |
|-------|----------------|------|
| `recommendation_runs_v1` | Session header | 0 | |
| `state_snapshots_v1` | Stage C | 0 | Stage C | 0 |
| `scenario_definitions_v1` | Stage D | 0 |Stage D | 0 |
| `scenario_items_v1` | Stage D | 0 || Stage D | 0 |
| `simulation_trace_v1` | Stage F | 0 | | 0 |
| `schedule_plans_v1` | Stage G | 0 || `schedule_plans_v1` | Stage G | 0 |
| `schedule_items_v1` | Stage G | 0 |
| `decision_trace_v1` | Stage G/I | 0 || `decision_trace_v1` | Stage G/I | 0 |
| `contraindication_eval_trace_v1` | Safety filter | 0 |
| `modifier_eval_trace_v1` | Stage E | 0 || `modifier_eval_trace_v1` | Stage E | 0 |
| `question_selection_trace_v1` | Stage H | 0 |
| `question_sequence_v1` | Adaptive intake | 0 |
| `policy_snapshots` | Session start | 0 |

------

## Category V — Validation/Offline## Category V — Validation/Offline

| Table | Purpose | Rows || Table | Purpose | Rows |
|-------|---------|------|
| `complexity_scaling_results_v1` | Model stability testing | 0 | stability testing | 0 |
| `population_archetypes_v1` | GMM population clustering | 0 |

---

## Uncategorized

| Table | Purpose | Rows |able | Purpose | Rows |
|-------|---------|------||-------|---------|------|
| `edge_ontology_v1` | Edge→ontology links | 0 |
| `node_search_terms_v1` | PubMed search terms | 0 || `node_search_terms_v1` | PubMed search terms | 0 |
| `variable_definitions_v1` | Variable definitions | 0 |
| `contraindication_escalation_policy_v1` | Escalation policy | 0 | | 0 |
| `intervention_synergy_v1` | Synergy evidence | 0 |

---

## Priority Execution Order

### NOW — Continue Per-Paper Extraction

| # | Action | Templates | DB Tables || # | Action | Templates | DB Tables |
|---|--------|-----------|-----------|
| 1 | Extract more papers (DEEP mode) | All 9 templates | edge_evidence, norms, priors, temporal, instrument, correlation, dose, subgroup, cohort profiles || 1 | Extract more papers (DEEP mode) | All 9 templates | edge_evidence, norms, priors, temporal, instrument, correlation, dose, subgroup, cohort profiles |
| 2 | Backfill existing papers with new template types | dose, subgroup, cohort profile | dose_evidence_v1, subgroup_evidence_v1, study_cohort_profiles_v1 |mplate types | dose, subgroup, cohort profile | dose_evidence_v1, subgroup_evidence_v1, study_cohort_profiles_v1 |

### NEXT — Curation (Category A Seed Tables)

| # | Tables | Effort | Blocks |
|---|--------|--------|--------|
| 3 | `observation_noise_v1`, `normalization_refs_v1` | ~40 hrs | Algorithm Chain C inference | | Algorithm Chain C inference |
| 4 | `intervention_kernels_v1`, `recovery_trajectories_v1` | ~30 hrs | Temporal prediction || 4 | `intervention_kernels_v1`, `recovery_trajectories_v1` | ~30 hrs | Temporal prediction |
| 5 | `literary_constraints_v1`, node priors curation | ~30 hrs | Bayesian priors |ode priors curation | ~30 hrs | Bayesian priors |

### BEFORE RUNTIME — Policy Authoring

| # | Tables | Reference |
|---|--------|-----------|
| 6 | `safety_policies_v1`, `contraindication_rules_v1` | 05_TABLE_SCHEMAS.md §D2-D3 || 6 | `safety_policies_v1`, `contraindication_rules_v1` | 05_TABLE_SCHEMAS.md §D2-D3 |
| 7 | `objective_specs_v1` | 05_TABLE_SCHEMAS.md §D1 |ABLE_SCHEMAS.md §D1 |
| 8 | `question_bank_v1`, `question_observation_models_v1` | 05_TABLE_SCHEMAS.md §E12 || 8 | `question_bank_v1`, `question_observation_models_v1` | 05_TABLE_SCHEMAS.md §E12 |

---

## Cross-Reference

| Document | Location | Covers ||
|----------|----------|--------||----------|----------|--------|
| Full table fill order (591 lines) | [docs/03_database/TABLE_FILL_ORDER.md](../docs/03_database/TABLE_FILL_ORDER.md) | Detailed per-table analysis with FK dependencies |s/03_database/TABLE_FILL_ORDER.md](../docs/03_database/TABLE_FILL_ORDER.md) | Detailed per-table analysis with FK dependencies |
| Extraction procedure | [01_PROCEDURE.md](01_PROCEDURE.md) | Steps 0–9 per paper |](01_PROCEDURE.md) | Steps 0–9 per paper |
| CSV templates | [06_CSV_TEMPLATES.md](06_CSV_TEMPLATES.md) | Column specs for all 12 template types |2 template types |
| CSV→DB mapping | [07_CSV_TO_DB_MAP.md](07_CSV_TO_DB_MAP.md) | How CSV columns map to DB columns ||
| DB schemas | [05_DB_SCHEMA.md](05_DB_SCHEMA.md) | All extraction-facing table columns |-facing table columns |

------

*This file is a concise summary. For the complete 591-line analysis, see [TABLE_FILL_ORDER.md](../docs/03_database/TABLE_FILL_ORDER.md).**This file is a concise summary. For the complete 591-line analysis, see [TABLE_FILL_ORDER.md](../docs/03_database/TABLE_FILL_ORDER.md).*
