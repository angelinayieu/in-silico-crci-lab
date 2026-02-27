# Table Fill Order — Complete Reference

**Purpose:** Authoritative document specifying when, how, and by whom each of the
83 database tables is populated. Used to verify that a table contains data before
writing code that reads it, and to trace the provenance of every row in the system.

**Cross-referenced by:** `CLAUDE.md` step 1g, `FILE_CONTEXT_MANIFEST.md`  
**Companion docs:** `05_TABLE_SCHEMAS.md` (column definitions), `06_FK_WIRING_MAP.md` (foreign keys), `11_CONTROLLED_VOCABULARIES.md` (enums)

**Last verified against DB:** 83 tables in `crci_dev.db` as of 2025-02-27

---

## Part I — Quick-Reference Status Matrix

Every table in the database, sorted by spec class and ID. Tables not in the spec
(from `007_ops_tables.sql` or `008_v2_migration.sql`) are listed under class "Ops".

**Legend:**  
✅ = Populated with data  |  ⬚ = Empty (0 rows)  |  🔧 = Seed CSV exists but not loading  
**Fill Stage** numbers correspond to Part II below.

### Class A — Knowledge Base (33 tables)

| Spec ID | Table Name | Rows | Status | Fill Stage | Population Method |
|---------|-----------|------|--------|------------|-------------------|
| A1 | `edge_relations_definitions_v1` | 141 | ✅ | 1A, 2A | Seed CSV + registry reseed |
| A2 | `edge_ontology_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A3 | `biomarker_node_definitions_v1` | 63 | ✅ | 1A, 2A | Seed CSV + registry reseed |
| A4 | `instrument_definitions_v1` | 67 | ✅ | 1A, 2A | Seed CSV + registry reseed |
| A5 | `measure_definitions_v1` | 90 | ✅ | 1A | Seed CSV |
| A6 | `harmonization_rules_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A7 | `predictor_alignment_rules_v1` | 0 | ⬚ | 1C | No seed path defined |
| A8 | `literary_mechanistic_priors_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A9 | `literary_constraints_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A10 | `contraindication_rules_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A11 | `action_contraindication_links_v1` | 0 | ⬚ | 1C | No seed path defined |
| A12 | `contraindication_escalation_policy_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A13 | `validation_rules_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A14 | `variable_definitions_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A15 | `variable_to_input_map_v1` | 0 | ⬚ | 1C | No seed path defined |
| A16 | `baseline_modifier_definitions_v1` | 0 | 🔧 | 1A* | Seed CSV exists (`modifier_rules.csv`) but custom loader broken |
| A17 | `derived_feature_definitions_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A18 | `triangulation_sets_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A19 | `triangulation_members_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A20 | `description_templates_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A21 | `action_catalog_v1` | 8 | ✅ | 1A, 5A | Seed CSV + load_evidence Step 5 |
| A22 | `question_bank_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A23 | `question_observation_models_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A24 | `normalization_refs_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A25 | `observation_noise_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A26 | `pathways_v1` | 28 | ✅ | 1A | Seed CSV |
| A27 | `pathway_interactions_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A28 | `intervention_synergy_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A29 | `recovery_trajectories_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A30 | `biomarker_correlations_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A31 | `feedback_loops_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A32 | `intervention_kernels_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |
| A33 | `mid_thresholds_v1` | 0 | ⬚ | 1B | Seed CSV (not yet created) |

### Class B — Per-Paper Evidence (9 tables)

| Spec ID | Table Name | Rows | Status | Fill Stage | Population Method |
|---------|-----------|------|--------|------------|-------------------|
| B1 | `study_registry_v1` | 4 | ✅ | 3A | `load_evidence_into_db.py` Step 3 (from `meta.json`) |
| B2 | `study_cohort_profiles_v1` | 0 | ⬚ | 3B | **PROTOCOL GAP** — not yet extracted |
| B3 | `profile_data_streams_v1` | 0 | ⬚ | 3B | **PROTOCOL GAP** — not yet extracted |
| B4 | `stream_timepoints_v1` | 0 | ⬚ | 3B | **PROTOCOL GAP** — not yet extracted |
| B5 | `ontology_links_v1` | 0 | ⬚ | 3B | **PROTOCOL GAP** — not yet extracted |
| B6 | `edge_evidence_v1` | 18 | ✅ | 4A, 4C, 4D | CSV import + harmonization + calibration |
| B7 | `edge_param_builds_v1` | 0 | ⬚ | 5B | P4 aggregation output (not yet running) |
| B8 | `triangulation_evidence_v1` | 0 | ⬚ | 3C | **PROTOCOL GAP** — not yet extracted |
| B9 | `pathway_biomarkers_v1` | 0 | ⬚ | 3C | **PROTOCOL GAP** — no extraction template |

### Class C — Compiled / Derived (7 tables)

| Spec ID | Table Name | Rows | Status | Fill Stage | Population Method |
|---------|-----------|------|--------|------------|-------------------|
| C1 | `edges_v1` | 15 | ✅ | 5A | `load_evidence_into_db.py` Step 6 (compiled from edge_evidence) |
| C2 | `dose_bridges_v1` | 10 | ✅ | 1A, 5A | Seed CSV + load_evidence Step 5b |
| C3 | `node_priors_v1` | 9 | ✅ | 4B | `load_evidence_into_db.py` Step 4b (from `context_priors_template.csv`) |
| C4 | `outcome_anchors_v1` | 0 | ⬚ | 5C | Algorithm compilation (not yet implemented) |
| C5 | `state_estimator_specs_v1` | 0 | ⬚ | 5C | Algorithm compilation (not yet implemented) |
| C6 | `chain_validation_results_v1` | 0 | ⬚ | 6 | Algorithm chain validation output |
| C7 | `publication_bias_results_v1` | 0 | ⬚ | 5B | P4B publication bias output |

### Class D — Policy & Configuration (7 tables)

| Spec ID | Table Name | Rows | Status | Fill Stage | Population Method |
|---------|-----------|------|--------|------------|-------------------|
| D1 | `objective_specs_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |
| D2 | `safety_policies_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |
| D3 | `escalation_policies_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |
| D4 | `status_quo_rules_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |
| D5 | `voi_rules_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |
| D6 | `complexity_scaling_results_v1` | 0 | ⬚ | 6 | Algorithm Chain D output |
| D7 | `population_archetypes_v1` | 0 | ⬚ | 5D | Admin configuration (pre-runtime) |

### Class E — Runtime Output (13 tables)

| Spec ID | Table Name | Rows | Status | Fill Stage | Population Method |
|---------|-----------|------|--------|------------|-------------------|
| E1 | `state_snapshots_v1` | 0 | ⬚ | 6 | Chain C posterior output |
| E2 | `scenario_definitions_v1` | 0 | ⬚ | 6 | Chain D simulation output |
| E3 | `scenario_items_v1` | 0 | ⬚ | 6 | Chain D simulation output |
| E4 | `schedule_plans_v1` | 0 | ⬚ | 6 | Chain D simulation output |
| E5 | `schedule_items_v1` | 0 | ⬚ | 6 | Chain D simulation output |
| E6 | `recommendation_runs_v1` | 0 | ⬚ | 6 | Runtime session output |
| E7 | `simulation_trace_v1` | 0 | ⬚ | 6 | Chain D simulation trace |
| E8 | `decision_trace_v1` | 0 | ⬚ | 6 | Chain D decision trace |
| E9 | `contraindication_eval_trace_v1` | 0 | ⬚ | 6 | Chain D safety evaluation trace |
| E10 | `question_selection_trace_v1` | 0 | ⬚ | 6 | Runtime question selection trace |
| E11 | `modifier_eval_trace_v1` | 0 | ⬚ | 6 | Chain C modifier evaluation trace |
| E12 | `question_sequence_v1` | 0 | ⬚ | 6 | Runtime question sequence output |
| E13 | `extraction_audit_v1` | 0 | ⬚ | 5B | Extraction pipeline audit output |

### Ops — Operations & Infrastructure (14 tables, not in 05_TABLE_SCHEMAS.md)

These tables are defined in `007_ops_tables.sql`, `008_v2_migration.sql`, or
`011_study_identity.sql`. They support pipeline operations, retrieval, and
evidence families from `SYS_EXTRACTION_ADDENDUM.md`.

| Table Name | Rows | Status | Fill Stage | Population Method |
|-----------|------|--------|------------|-------------------|
| `acquisition_queue_v1` | 15 | ✅ | Ops | Retrieval system (`search_coordinator.py`) |
| `build_manifests_v1` | 0 | ⬚ | 5A | Compilation provenance tracking |
| `dose_evidence_v1` | 0 | ⬚ | 3C | Per-paper extraction — CSV template not yet created |
| `extraction_completeness_v1` | 0 | ⬚ | Ops | Pipeline QA tracking |
| `extraction_runs` | 0 | ⬚ | Ops | Pipeline run metadata |
| `instrument_evidence_v1` | 9 | ✅ | 4B | `load_evidence_into_db.py` Step 4b (from `instrument_evidence_template.csv`) |
| `node_search_terms_v1` | 0 | ⬚ | Ops | Retrieval system search terms |
| `policy_snapshots` | 0 | ⬚ | Ops | Runtime policy versioning |
| `population_norms_v1` | 13 | ✅ | 4B | `load_evidence_into_db.py` Step 4b (from `population_norms_template.csv`) |
| `review_tasks` | 0 | ⬚ | Ops | Pipeline QA tasks (ATB rejections, AMBIGUOUS flags) |
| `study_annotations_raw_v1` | 0 | ⬚ | 3A | P1 multi-agent extraction raw output |
| `study_annotations_v1` | 0 | ⬚ | 3A | P1 extraction harmonized output |
| `subgroup_evidence_v1` | 0 | ⬚ | 3C | Per-paper extraction — CSV template not yet created |
| `temporal_evidence_v1` | 16 | ✅ | 4B | `load_evidence_into_db.py` Step 4b (from `temporal_evidence_template.csv`) |

### Summary Counts

| Category | Total | Populated (✅) | Empty (⬚) | Broken (🔧) |
|----------|-------|----------------|-----------|-------------|
| Class A — Knowledge | 33 | 7 | 25 | 1 |
| Class B — Evidence | 9 | 2 | 7 | 0 |
| Class C — Compiled | 7 | 3 | 4 | 0 |
| Class D — Policy | 7 | 0 | 7 | 0 |
| Class E — Output | 13 | 0 | 13 | 0 |
| Ops — Infrastructure | 14 | 4 | 10 | 0 |
| **Total** | **83** | **16** | **66** | **1** |

---

## Part II — Fill Stages (Detailed)

### Stage 0 — Schema Creation (DDL)

**Executor:** `scripts/setup_database.py`  
**SQL files:** `crci/database/schema/001_class_a_knowledge.sql` through `012_evidence_validation_quarantine.sql`  
**Result:** All 83 tables created empty with constraints and indexes.

```bash
python scripts/setup_database.py          # Creates crci_dev.db with all tables
```

No data is inserted at this stage. All tables exist with 0 rows.

---

### Stage 1 — Class A Knowledge Base Seeding

Class A tables define the domain ontology — nodes, edges, instruments, measures,
pathways, rules, and constraints. They are populated from CSV seed files and
updated only by domain experts.

#### Stage 1A — Existing Seed CSVs (8 files → 7 tables populated)

**Executor:** `scripts/setup_database.py --seed` → `crci/database/seed_loader.py`  
**Source directory:** `crci/database/seeds/`

| Seed CSV | Target Table | Rows | PK Column |
|----------|-------------|------|-----------|
| `nodes.csv` | `biomarker_node_definitions_v1` (A3) | 63 | `node_id` |
| `edge_relations.csv` | `edge_relations_definitions_v1` (A1) | 141 | `edge_relation_id` |
| `instruments.csv` | `instrument_definitions_v1` (A4) | 67 | `instrument_id` |
| `measures.csv` | `measure_definitions_v1` (A5) | 90 | `measure_id` |
| `pathways.csv` | `pathways_v1` (A26) | 28 | `pathway_id` |
| `actions.csv` | `action_catalog_v1` (A21) | 8 | `action_id` |
| `dose_bridges.csv` | `dose_bridges_v1` (C2) | 10 | `bridge_id` |
| `modifier_rules.csv` | `baseline_modifier_definitions_v1` (A16) | **0** ⚠ | `modifier_id` |

> **⚠ Known issue:** `modifier_rules.csv` (15 rows) exists but `seed_loader.py`
> maps `"modifiers.csv": (None, "modifier_id")` — filename mismatch and `None`
> model class prevent loading. `baseline_modifier_definitions_v1` remains at 0 rows.

**Regenerating seeds from registries:**
```bash
python scripts/generate_derived_seeds.py   # NODE_REGISTRY → nodes.csv, etc.
python scripts/setup_database.py --seed    # Loads CSVs into tables
```

The `seed_loader.py` LOAD_ORDER enforces FK-safe dependency ordering in 4 tiers:
- **ROOT:** `nodes`, `actions`, `description_templates`, `recovery_trajectories`, `harmonization_rules`, `validation_rules`, `mid_thresholds`, `contraindication_escalation`
- **Level 1:** `edge_relations`, `instruments`, `measures`, `variables`, `pathways`, `normalization_refs`, `observation_noise`, `intervention_kernels`, `biomarker_correlations`, `feedback_loops`, `question_obs_models`
- **Level 2:** `edge_ontology`, `literary_priors`, `literary_constraints`, `contraindication_rules`, `features`, `triangulation_sets`, `pathway_interactions`, `synergy`, `question_bank`
- **Level 3:** `triangulation_members`

#### Stage 1B — Missing Seed CSVs (23 files mapped but not yet authored)

These tables have entries in `seed_loader.py` SEED_TABLE_MAP and LOAD_ORDER,
but the corresponding CSV files in `crci/database/seeds/` do not exist yet.

**Curation guide:** See `CATEGORY_A_RESEARCH_GUIDE.md` for domain-expert
research instructions per table.

| Missing CSV | Target Table | Spec ID | Priority |
|-------------|-------------|---------|----------|
| `edge_ontology.csv` | `edge_ontology_v1` | A2 | HIGH — gates extraction harmonization (P2 CG4) |
| `harmonization_rules.csv` | `harmonization_rules_v1` | A6 | HIGH — used by P2 harmonization |
| `literary_priors.csv` | `literary_mechanistic_priors_v1` | A8 | MEDIUM — used by P4 aggregation |
| `literary_constraints.csv` | `literary_constraints_v1` | A9 | LOW — optional runtime guardrails |
| `contraindication_rules.csv` | `contraindication_rules_v1` | A10 | HIGH — blocks Chain D safety |
| `contraindication_escalation.csv` | `contraindication_escalation_policy_v1` | A12 | MEDIUM — needed by Chain D |
| `validation_rules.csv` | `validation_rules_v1` | A13 | MEDIUM — pipeline validation gates |
| `variables.csv` | `variable_definitions_v1` | A14 | LOW — variable registry |
| `features.csv` | `derived_feature_definitions_v1` | A17 | LOW — derived feature specs |
| `triangulation_sets.csv` | `triangulation_sets_v1` | A18 | LOW — multi-method grouping |
| `triangulation_members.csv` | `triangulation_members_v1` | A19 | LOW — depends on A18 |
| `description_templates.csv` | `description_templates_v1` | A20 | LOW — presentation templates |
| `question_bank.csv` | `question_bank_v1` | A22 | MEDIUM — runtime question system |
| `question_obs_models.csv` | `question_observation_models_v1` | A23 | MEDIUM — runtime question system |
| `normalization_refs.csv` | `normalization_refs_v1` | A24 | MEDIUM — population norms anchoring |
| `observation_noise.csv` | `observation_noise_v1` | A25 | LOW — state estimation noise |
| `pathway_interactions.csv` | `pathway_interactions_v1` | A27 | LOW — pathway model |
| `synergy.csv` | `intervention_synergy_v1` | A28 | LOW — multi-intervention synergy |
| `recovery_trajectories.csv` | `recovery_trajectories_v1` | A29 | LOW — temporal decay profiles |
| `biomarker_correlations.csv` | `biomarker_correlations_v1` | A30 | LOW — cross-node correlation |
| `feedback_loops.csv` | `feedback_loops_v1` | A31 | LOW — cycle detection |
| `intervention_kernels.csv` | `intervention_kernels_v1` | A32 | HIGH — blocks Chain D simulation |
| `mid_thresholds.csv` | `mid_thresholds_v1` | A33 | MEDIUM — clinically meaningful change |

#### Stage 1C — Class A Tables Without Any Seed Path

These Class A tables are not mapped in `seed_loader.py` SEED_TABLE_MAP and have
no CSV seed mechanism. They require either new SEED_TABLE_MAP entries or a
dedicated curation script.

| Table | Spec ID | Notes |
|-------|---------|-------|
| `predictor_alignment_rules_v1` | A7 | Alignment rules for predictor variables |
| `action_contraindication_links_v1` | A11 | Links actions to contraindication rules (depends on A10 + A21) |
| `variable_to_input_map_v1` | A15 | Maps variables to model inputs (depends on A14) |

---

### Stage 2 — Registry Reseed

**Executor:** `scripts/load_evidence_into_db.py` Steps 1 and 1b  
**Runs:** Each time evidence is reloaded (idempotent upsert)

This stage refreshes canonical registries from the authoritative CSV files in
`registries/`, which may contain more current data than the derived seed CSVs.

| Step | Source Registry | Target Table | Registry Rows |
|------|----------------|-------------|---------------|
| 1 | `registries/EDGE_REGISTRY.csv` | `edge_relations_definitions_v1` (A1) | 142 |
| 1b | `registries/NODE_REGISTRY.csv` | `biomarker_node_definitions_v1` (A3) | 63 |
| 1b | `registries/INSTRUMENT_REGISTRY.csv` | `instrument_definitions_v1` (A4) | 67 |

> **Note:** `MEASURE_REGISTRY.csv` (82 rows) and `PATHWAY_REGISTRY.csv` (22 rows)
> exist in `registries/` but are **not** reseeded by `load_evidence_into_db.py`.
> The seed CSVs (`measures.csv` = 90 rows, `pathways.csv` = 28 rows) may diverge
> from these registries over time.

---

### Stage 3 — Per-Paper Study Registration & Annotation

#### Stage 3A — Study Registration and Extraction Output

**Executor:** `scripts/load_evidence_into_db.py` Step 3 (for study registration)  
**Executor:** `crci/extraction/p1_extraction/` (for annotations, when pipeline runs)

| Table | How Populated | Current Status |
|-------|--------------|----------------|
| `study_registry_v1` (B1) | Step 3 reads `meta.json` from each paper folder in `data/manual_uploads/structured/` | ✅ 4 rows (4 papers) |
| `study_annotations_raw_v1` (Ops) | P1 multi-agent extraction writes raw LLM output | ⬚ — P1 agents not yet running |
| `study_annotations_v1` (Ops) | P1 extraction harmonizes raw annotations | ⬚ — P1 agents not yet running |

#### Stage 3B — Per-Paper Cohort & Stream Tables (PROTOCOL GAP)

These tables describe the study cohort, measurement instruments, timepoints, and
ontology links. They are defined in `05_TABLE_SCHEMAS.md` (B2–B5) but no
extraction protocol or CSV templates exist.

| Table | Spec ID | What It Stores | Impact of Being Empty |
|-------|---------|---------------|----------------------|
| `study_cohort_profiles_v1` | B2 | Cohort demographics, sample size, diagnosis | `context_wiring.py` L221: `scope_weights` hardcoded to 1.0 → **transportability is a no-op** |
| `profile_data_streams_v1` | B3 | Which instruments/measures each cohort used | No instrument→measure linkage per study |
| `stream_timepoints_v1` | B4 | Actual measurement timepoints per stream | No temporal alignment verification |
| `ontology_links_v1` | B5 | Maps study variables to canonical edge relations | No provenance trail from study measures to DAG edges |

> **Action required:** Create CSV templates and extraction protocol for B2–B5.
> These are foundational for transportability scoring (P2 Layer 2).

#### Stage 3C — Additional Per-Paper Evidence Tables (PARTIALLY IMPLEMENTED)

Specialized per-paper evidence beyond the core `edge_evidence_v1` table.

| Table | Spec/Origin | Has CSV Template? | Current Status |
|-------|------------|-------------------|----------------|
| `triangulation_evidence_v1` (B8) | Spec B8 | ❌ | ⬚ — No template or extraction path |
| `pathway_biomarkers_v1` (B9) | Spec B9 | ❌ | ⬚ — No template or extraction path |
| `dose_evidence_v1` (Ops) | Addendum | ❌ | ⬚ — Template not yet created |
| `subgroup_evidence_v1` (Ops) | Addendum | ❌ | ⬚ — Template not yet created |

---

### Stage 4 — Per-Paper Evidence CSV Loading

**Executor:** `scripts/load_evidence_into_db.py` Steps 4, 4b, 4c, 4d  
**Source:** `data/manual_uploads/structured/[doi-slug]/*.csv`

#### Stage 4A — Edge Evidence Loading (Step 4)

Loads `edge_evidence_template.csv` files from each paper folder.

| Table | Template CSV | Current Rows | Notes |
|-------|-------------|-------------|-------|
| `edge_evidence_v1` (B6) | `edge_evidence_template.csv` | 18 | Core evidence: effect sizes, SEs, study design |

#### Stage 4B — Auxiliary Evidence Families (Step 4b)

Loads 4 auxiliary CSV template families from each paper folder.

| Table | Template CSV | Current Rows | Notes |
|-------|-------------|-------------|-------|
| `instrument_evidence_v1` (Ops) | `instrument_evidence_template.csv` | 9 | Instrument psychometric data |
| `population_norms_v1` (Ops) | `population_norms_template.csv` | 13 | Population baseline norms |
| `temporal_evidence_v1` (Ops) | `temporal_evidence_template.csv` | 16 | Temporal response data |
| `node_priors_v1` (C3) | `context_priors_template.csv` | 9 | Context-dependent node priors |

> **Note:** `correlation_template.csv` files exist in paper folders but the loader
> does not currently import them into `biomarker_correlations_v1` (A30).

#### Stage 4C — Scale Harmonization (Step 4c)

**In-place updates** to `edge_evidence_v1` — converts all effect sizes to a
common Cohen's d scale. No new tables are created.

Affected columns: `beta_sd_sd`, `se_sd_sd`, `conversion_rule_id`, `conversion_notes`

#### Stage 4D — Seven-Layer SE Calibration (Step 4d)

**In-place updates** to `edge_evidence_v1` — applies the P3-8 seven-layer SE
effective calibration pipeline.

Affected columns: `SE_eff`, `m_design`, `m_GRADE`, `tau_sq`, `w_fresh`,
`w_scope`, `m_impute`, `m_indirect`

---

### Stage 5 — Compilation & Aggregation

Derived tables compiled from evidence, plus policy configuration.

#### Stage 5A — Edge Compilation and Seeding (Steps 5, 5b, 6)

**Executor:** `scripts/load_evidence_into_db.py` Steps 5, 5b, 6

| Table | How Populated | Current Rows |
|-------|-------------|-------------|
| `action_catalog_v1` (A21) | Step 5 seeds from `actions.csv` (also seeded at Stage 1A) | 8 |
| `dose_bridges_v1` (C2) | Step 5b seeds from `dose_bridges.csv` (also seeded at Stage 1A) | 10 |
| `edges_v1` (C1) | Step 6 compiles via IVW aggregation of `edge_evidence_v1` per edge relation | 15 |
| `build_manifests_v1` (Ops) | Step 6 compilation provenance records | 0 |

#### Stage 5B — Extraction Pipeline Outputs (when P4, P4B, P6 run)

Tables written by extraction pipeline stages not yet operating in the current
manual-import workflow.

| Table | Written By | Notes |
|-------|-----------|-------|
| `edge_param_builds_v1` (B7) | `p4_aggregation/` | IVW pooling per-edge build records |
| `publication_bias_results_v1` (C7) | `p4b_publication_bias/` | Egger test, trim-fill results |
| `extraction_audit_v1` (E13) | `p6_deployment/` | Extraction audit trail |

#### Stage 5C — Algorithm Compilation (when algorithm chains run)

| Table | Written By | Notes |
|-------|-----------|-------|
| `outcome_anchors_v1` (C4) | Algorithm compilation | Anchoring data for outcomes |
| `state_estimator_specs_v1` (C5) | Algorithm compilation | State estimation parameters |
| `chain_validation_results_v1` (C6) | Algorithm validation | Cross-chain consistency checks |

#### Stage 5D — Policy & Configuration (Manual / Admin)

Class D tables that must be configured before the algorithm can run. These define
operational policy, not scientific knowledge.

| Table | Spec ID | Purpose |
|-------|---------|---------|
| `objective_specs_v1` | D1 | User objective definitions |
| `safety_policies_v1` | D2 | Safety constraint definitions |
| `escalation_policies_v1` | D3 | When to escalate recommendations |
| `status_quo_rules_v1` | D4 | Status quo comparator definitions |
| `voi_rules_v1` | D5 | Value-of-information decision rules |
| `population_archetypes_v1` | D7 | Reference population profiles |

---

### Stage 6 — Algorithm Runtime (Chains A → F)

All Class E tables are populated when the algorithm runs for a user session.
They are **output-only** — never manually populated.

**Prerequisites:** Stages 1–5 must be complete. Key blocking dependencies:
- **Chain A** (Graph): `edges_v1`, `pathways_v1`, `biomarker_node_definitions_v1`
- **Chain B** (Evidence): `edge_evidence_v1`, `study_registry_v1`
- **Chain C** (Posterior): `state_snapshots_v1`, `recommendation_runs_v1`, `scenario_definitions_v1`
- **Chain D** (Simulation): `action_catalog_v1`, `intervention_kernels_v1`, `dose_bridges_v1`, `contraindication_rules_v1`

| Table | Spec ID | Written By | Notes |
|-------|---------|-----------|-------|
| `state_snapshots_v1` | E1 | Chain C | Current posterior state estimates |
| `scenario_definitions_v1` | E2 | Chain D | Candidate intervention scenarios |
| `scenario_items_v1` | E3 | Chain D | Items within each scenario |
| `schedule_plans_v1` | E4 | Chain D | Temporal intervention schedules |
| `schedule_items_v1` | E5 | Chain D | Items within schedule plans |
| `recommendation_runs_v1` | E6 | Runtime | Top-level session records |
| `simulation_trace_v1` | E7 | Chain D | Monte Carlo simulation trace |
| `decision_trace_v1` | E8 | Chain D | Decision logic trace |
| `contraindication_eval_trace_v1` | E9 | Chain D | Safety evaluation trace |
| `question_selection_trace_v1` | E10 | Runtime | Question selection audit |
| `modifier_eval_trace_v1` | E11 | Chain C | Baseline modifier trace |
| `question_sequence_v1` | E12 | Runtime | Ordered question presentation |
| `complexity_scaling_results_v1` | D6 | Chain D | Complexity scaling output |

---

### Ops Stage — Operations & Infrastructure

Populated as side effects of various system activities.

| Table | Populated By | Current Rows | Notes |
|-------|-------------|-------------|-------|
| `acquisition_queue_v1` | `crci/retrieval/search_coordinator.py` | 15 | Paper retrieval queue |
| `node_search_terms_v1` | `crci/retrieval/query_generator.py` | 0 | Auto-generated search terms |
| `extraction_runs` | `crci/extraction/pipeline.py` | 0 | Pipeline run metadata |
| `extraction_completeness_v1` | Extraction pipeline | 0 | Per-paper completeness tracking |
| `review_tasks` | Trust boundary + extraction pipeline | 0 | Human review tasks |
| `policy_snapshots` | Runtime | 0 | Policy version snapshots |

---

## Part III — Key Consumers (Who Reads What)

Tables referenced by ≥3 Python files in `crci/`, sorted by reference count.

| Table | Refs | Key Consumers |
|-------|------|---------------|
| `edge_evidence_v1` | 17 | p2_harmonization, p3_heterogeneity, p4_aggregation, p7_compilers, chain_b, load_evidence |
| `study_registry_v1` | 17 | p0_triage, p1_extraction, p4_aggregation, chain_b, load_evidence |
| `study_annotations_v1` | 13 | p1_extraction, p3_heterogeneity, p4_aggregation, load_evidence |
| `edge_relations_definitions_v1` | 11 | p1_extraction, tb_trust_boundary, seed_loader, load_evidence |
| `acquisition_queue_v1` | 7 | retrieval (search_coordinator, acquisition_scheduler, aps_scorer) |
| `instrument_definitions_v1` | 7 | p1_extraction, p7_compilers, seed_loader, load_evidence |
| `intervention_kernels_v1` | 6 | p1_extraction, chain_d, p7_compilers |
| `biomarker_node_definitions_v1` | 5 | p1_extraction, load_evidence, seed_loader |
| `action_catalog_v1` | 5 | chain_d, load_evidence |
| `contraindication_rules_v1` | 5 | p1_extraction, chain_d |
| `review_tasks` | 5 | extraction pipeline (multiple stages) |
| `edges_v1` | 4 | load_evidence (compilation), presentation |
| `instrument_evidence_v1` | 4 | p7_compilers, load_evidence |
| `population_norms_v1` | 4 | p7_compilers, load_evidence |
| `temporal_evidence_v1` | 4 | p7_compilers, load_evidence |
| `subgroup_evidence_v1` | 4 | p7_compilers, load_evidence |
| `recovery_trajectories_v1` | 4 | p7_compilers |
| `observation_noise_v1` | 4 | p1_extraction |
| `pathways_v1` | 3 | seed_loader |
| `node_priors_v1` | 3 | p7_compilers, load_evidence |
| `dose_bridges_v1` | 3 | chain_d, p7_compilers, load_evidence |
| `node_search_terms_v1` | 3 | retrieval |
| `intervention_synergy_v1` | 3 | p7_compilers |

---

## Part IV — Critical Dependency Chains

### Chain B (Evidence Scoring) — READY ✅
```
edge_evidence_v1        ✅ 18 rows
study_registry_v1       ✅  4 rows
```

### Chain D (Simulation) — BLOCKED ❌
```
action_catalog_v1       ✅  8 rows
dose_bridges_v1         ✅ 10 rows
intervention_kernels_v1 ⬚ ← BLOCKER (needs intervention_kernels.csv seed)
contraindication_rules_v1 ⬚ ← BLOCKER (needs contraindication_rules.csv seed)
```

### Transportability Scoring (P2 Layer 2) — BLOCKED ❌
```
study_cohort_profiles_v1 ⬚ ← BLOCKER (needs B2 extraction template + protocol)
```

### P7 Compilers (Full Compilation) — PARTIALLY BLOCKED
```
edge_evidence_v1               ✅ 18 rows
dose_bridges_v1                ✅ 10 rows
instrument_definitions_v1      ✅ 67 rows
instrument_evidence_v1         ✅  9 rows
node_priors_v1                 ✅  9 rows
population_norms_v1            ✅ 13 rows
temporal_evidence_v1           ✅ 16 rows
intervention_kernels_v1        ⬚ ← BLOCKER
intervention_synergy_v1        ⬚ ← BLOCKER
recovery_trajectories_v1       ⬚ ← BLOCKER
baseline_modifier_definitions_v1 ⬚ ← BLOCKER (seed exists but broken)
dose_evidence_v1               ⬚ (no template)
subgroup_evidence_v1           ⬚ (no template)
```

---

## Part V — Known Issues & Action Items

### ~~Critical~~ — Resolved

1. ~~**`baseline_modifier_definitions_v1` seed not loading**~~ ✅  
   Fixed: `modifier_rules.csv` rewritten with correct schema columns,
   `seed_loader.py` SEED_TABLE_MAP updated — 15 rows now load.

2. ~~**B2–B5 extraction protocol gap**~~ ✅  
   Fixed: 6 CSV templates created (`study_cohort_profile_template.csv`,
   `profile_data_stream_template.csv`, `stream_timepoint_template.csv`,
   `ontology_link_template.csv`, `dose_evidence_template.csv`,
   `subgroup_evidence_template.csv`). 6 importer functions added to
   `family_importers.py` and wired into `_FAMILY_IMPORTERS` (now 11 entries).
   **Data still needed** — templates exist but no paper data populated yet.

### ~~High Priority~~ — Partially Resolved

3. **Chain D blocked** on `intervention_kernels_v1` and `contraindication_rules_v1`  
   Both need seed CSVs authored by a domain expert. See `CATEGORY_A_RESEARCH_GUIDE.md`.

4. **20 missing seed CSVs** — Mapped in `seed_loader.py` but files don't exist on disk.  
   Down from 23 — added `predictor_alignment_rules.csv`, `action_contraindication_links.csv`,
   `variable_to_input_map.csv`.  See Stage 1B table for full list.

5. ~~**3 Class A tables with no seed path**~~ ✅  
   Fixed: `predictor_alignment_rules_v1` (7 rows), `action_contraindication_links_v1`
   (6 rows), `variable_to_input_map_v1` (12 rows) — SEED_TABLE_MAP entries added,
   CSV seed files created, data loaded.

6. ~~**MEASURE_REGISTRY.csv and PATHWAY_REGISTRY.csv not reseeded**~~ ✅  
   Fixed: `reseed_measure_and_pathway_definitions()` added to `load_evidence_into_db.py`
   as Step 1c. Loads 82 measures from MEASURE_REGISTRY.csv and 22 pathways from
   PATHWAY_REGISTRY.csv with full column mapping.

### ~~Medium Priority~~ — Resolved

7. ~~**`dose_evidence_v1` and `subgroup_evidence_v1` templates**~~ ✅  
   Fixed: Templates created + `import_dose_evidence()` and `import_subgroup_evidence()`
   importers added to `family_importers.py`.

8. ~~**`correlation_template.csv` loader**~~ ✅ (was already wired)  
   `_FAMILY_IMPORTERS` already included `correlation_template` → `import_correlation`.
   No code change needed — just no data files exist yet.

### Remaining Open Items

- **20 seed CSVs still missing** (SEED_TABLE_MAP has 33 entries, 11 (+2 backup) on disk)
- **Chain D domain-expert authoring** needed for `intervention_kernels_v1`,
  `contraindication_rules_v1`, and other Class A knowledge tables
- **B2-B5 data population** — templates+importers are wired but no paper
  data has been extracted into them yet

---

### Summary of Populated Tables (19 of 83)

| Table | Rows | Source |
|-------|------|--------|
| `acquisition_queue_v1` | 15 | Pipeline |
| `action_catalog_v1` | 8 | Seed CSV |
| `action_contraindication_links_v1` | 6 | Seed CSV (new) |
| `baseline_modifier_definitions_v1` | 15 | Seed CSV (fixed) |
| `biomarker_node_definitions_v1` | 63 | NODE_REGISTRY.csv |
| `dose_bridges_v1` | 10 | Seed CSV |
| `edge_evidence_v1` | 18 | Manual extraction |
| `edge_relations_definitions_v1` | 141 | EDGE_REGISTRY.csv |
| `edges_v1` | 15 | Seed CSV |
| `instrument_definitions_v1` | 67 | INSTRUMENT_REGISTRY.csv |
| `instrument_evidence_v1` | 9 | Manual extraction |
| `measure_definitions_v1` | 82 | MEASURE_REGISTRY.csv (new) |
| `node_priors_v1` | 9 | Manual extraction |
| `pathways_v1` | 22 | PATHWAY_REGISTRY.csv (new) |
| `population_norms_v1` | 13 | Manual extraction |
| `predictor_alignment_rules_v1` | 7 | Seed CSV (new) |
| `study_registry_v1` | 4 | Manual extraction |
| `temporal_evidence_v1` | 16 | Manual extraction |
| `variable_to_input_map_v1` | 12 | Seed CSV (new) |

---

## Appendix A — Schema SQL File Inventory

| SQL File | Creates | Description |
|----------|---------|-------------|
| `001_class_a_knowledge.sql` | A1–A32 | Domain knowledge tables |
| `002_class_b_evidence.sql` | B1–B9 | Per-paper evidence tables |
| `003_class_c_compiled.sql` | C1–C5 | Compiled/derived tables |
| `004_class_d_reference.sql` | D1–D5 | Policy & reference tables |
| `005_class_e_output.sql` | E1–E13 | Runtime output tables |
| `006_fk_constraints.sql` | — | Foreign key constraints |
| `007_ops_tables.sql` | 5 Ops tables | Operations infrastructure |
| `008_v2_migration.sql` | Various Ops | V2 additions (auxiliary families, search terms, etc.) |
| `009_conversion_hardening.sql` | — | Conversion validation columns |
| `009_qa_quarantine.sql` | — | QA quarantine columns |
| `010_modules_2_3_4_5.sql` | — | Module 2–5 schema extensions |
| `011_study_identity.sql` | — | Study identity columns |
| `012_evidence_validation_quarantine.sql` | — | Evidence validation quarantine |

## Appendix B — Seed Loader Configuration Reference

**File:** `crci/database/seed_loader.py`  
**Map:** `SEED_TABLE_MAP` — 31 entries mapping CSV filenames → (ORM model, PK column)  
**Order:** `LOAD_ORDER` — 31 filenames in FK-safe dependency order (4 tiers)

Of 31 mapped CSVs: **8 exist** on disk, **23 missing**, **1 broken** (filename mismatch).
