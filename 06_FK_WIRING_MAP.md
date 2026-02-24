# CRCI Framework — Foreign Key Wiring Map
## Complete FK Graph with Design Rationale

**Version:** 3.0 (Consolidated — merges 03_FK_WIRING_v2_1.md + TABLE_IDENTITY_v2 Part 4)

**Purpose:** Complete foreign key relationships across all 64 tables, with design rationale explaining why FKs matter and how they wire.

**Companion documents:**
- `04_TABLE_REGISTRY.md` — Table identity cards (ownership, fill order, readers/writers)
- `05_TABLE_SCHEMAS.md` — Full column schemas with inline wiring notes

---

## 1. Why Foreign Keys Matter in This System

A foreign key (FK) is a column in one table whose values MUST exist as a primary key (PK) in another table — a pointer saying "this row refers to THAT row over there."

FKs serve four purposes simultaneously:

### 1.1 JOIN WIRING — "How do I combine data from two tables?"

FKs make joins explicit and unambiguous. Without them, you'd guess which columns to join on.

### 1.2 FILL ORDER ENFORCEMENT — "What must exist before this can exist?"

FKs create a dependency graph. You can't insert a row into `edge_evidence_v1` with `study_id = "STUDY_001"` unless `study_registry_v1` already has that row. This ENFORCES the fill order documented in `02_MACRO_OVERVIEW_OF_SYSTEMS.md` Part 5.

### 1.3 DATA INTEGRITY — "Can this value be wrong?"

FK constraints catch errors at write time. A typo in `edge_relation_id` is rejected because it doesn't exist in the parent table. This is a free validation gate.

### 1.4 PROVENANCE TRACING — "Where did this come from?"

FKs create audit trails. Given any row in `edges_v1`, you can trace backward:

```
edges_v1.edge_param_id
  → edge_param_builds_v1.build_id (how it was compiled)
    → edge_evidence_v1.ler_id (which papers contributed)
      → study_registry_v1.study_id (which study)
```

### 1.5 FK Direction vs Data Flow

FKs point FROM child TO parent (upstream), while data flows downstream:

```
DATA FLOW (downstream):        FK DIRECTION (upstream):

  A (Knowledge)                  A (Knowledge)
       ↓ reads                        ↑ FK
  B (Evidence)                   B (Evidence)
       ↓ aggregates                   ↑ FK
  C (Compiled)                   C (Compiled)
       ↓ consumed by                  ↑ FK
  E (Outputs)                    E (Outputs)
```

These are two views of the same graph. The FK graph and the data flow graph are mirrors.

---

## 2. FK Pattern Summary

| Pattern | Count | Description |
|---------|-------|-------------|
| **Direct FK** | ~95 | source.col → target.pk |
| **Polymorphic FK** | ~12 | source.entity_id + source.entity_type → one of N target tables |
| **JSON-array FK** | ~18 | source.col_json contains array of IDs referencing target.pk |
| **Self-referential** | ~3 | source.col → source.pk (dependency chains) |
| **Composite FK** | ~12 | Multiple columns jointly reference a target |

### Polymorphic FK Tables (Require Type Discriminator)

| Table | Type Column | Possible Targets |
|-------|-------------|-----------------|
| `normalization_refs_v1` | `target_entity_type` | instrument_definitions, measure_definitions, derived_feature_definitions |
| `observation_noise_v1` | `target_entity_type` | instrument_definitions, measure_definitions, derived_feature_definitions, question_bank |
| `ontology_links_v1` | `target_type` | biomarker_node_definitions, edge_relations_definitions, instrument_definitions, measure_definitions |
| `outcome_anchors_v1` | `target_type` | biomarker_node_definitions, derived_feature_definitions |
| `voi_rules_v1` | `target_ref_type` | biomarker_node_definitions, derived_feature_definitions |
| `variable_definitions_v1` | `source_ref_type` | biomarker_node_definitions, derived_feature_definitions |
| `triangulation_members_v1` | `member_entity_type` | derived_feature_definitions, measure_definitions |
| `question_observation_models_v1` | `target_entity_type` | biomarker_node_definitions, derived_feature_definitions |

---

## 3. Complete FK Map by Table

### Class A

**`edge_relations_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `source_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `target_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |

**`edge_ontology_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `edge_relation_id` | `edge_relations_definitions_v1.edge_relation_id` | 1:1 | STRICT |

**`biomarker_node_definitions_v1`** — ROOT (no outbound FKs)

**`instrument_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `maps_to_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `norm_id` | `normalization_refs_v1.norm_id` | N:1 | STRICT |
| `noise_id` | `observation_noise_v1.noise_id` | N:1 | STRICT |

**`measure_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `maps_to_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `norm_id` | `normalization_refs_v1.norm_id` | N:1 | STRICT |
| `noise_id` | `observation_noise_v1.noise_id` | N:1 | STRICT |

**`harmonization_rules_v1`** — ROOT (no outbound FKs)

**`predictor_alignment_rules_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_measure_id` | `measure_definitions_v1.measure_id` | N:1 | STRICT |

**`literary_mechanistic_priors_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `source_study_id` | `study_registry_v1.study_id` | N:1 | NULLABLE |
| `target_edge_relation_id` | `edge_relations_definitions_v1.edge_relation_id` | N:1 | STRICT |

**`literary_constraints_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | NULLABLE |
| `target_measure_id` | `measure_definitions_v1.measure_id` | N:1 | NULLABLE |
| `source_study_id` | `study_registry_v1.study_id` | N:1 | NULLABLE |

**`contraindication_rules_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `escalation_id` | `contraindication_escalation_policy_v1.escalation_id` | N:1 | STRICT |

**`action_contraindication_links_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |
| `rule_id` | `contraindication_rules_v1.rule_id` | N:1 | STRICT |

**`contraindication_escalation_policy_v1`** — ROOT (no outbound FKs)

**`validation_rules_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_table` | `Polymorphic — any table name` | N:1 | SOFT — commit-time validation |

**`variable_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `source_ref_id` | `biomarker_node_definitions_v1.node_id OR derived_feature_definitions_v1.feature_id` | N:1 | POLYMORPHIC via source_ref_type |

**`variable_to_input_map_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `variable_id` | `variable_definitions_v1.variable_id` | N:1 | STRICT |

**`baseline_modifier_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `required_variable_ids_json` | `variable_definitions_v1.variable_id (JSON array)` | N:M | JSON-ARRAY FK |
| `source_ler_ids` | `edge_evidence_v1.ler_id (JSON array)` | N:M | JSON-ARRAY FK |

**`derived_feature_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `norm_id` | `normalization_refs_v1.norm_id` | N:1 | STRICT |
| `noise_id` | `observation_noise_v1.noise_id` | N:1 | STRICT |
| `dependency_ids_json` | `self.feature_id (JSON array, SELF-REF)` | N:M | JSON-ARRAY SELF-REF — must be acyclic |

**`triangulation_sets_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `output_feature_id` | `derived_feature_definitions_v1.feature_id` | N:1 | NULLABLE |

**`triangulation_members_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `triangulation_id` | `triangulation_sets_v1.triangulation_id` | N:1 | STRICT |
| `member_entity_id` | `derived_feature_definitions_v1 OR measure_definitions_v1` | N:1 | POLYMORPHIC via member_entity_type |

**`description_templates_v1`** — ROOT (no outbound FKs)

**`action_catalog_v1`** — ROOT (no outbound FKs)

**`question_bank_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `observation_model_id` | `question_observation_models_v1.model_id` | N:1 | STRICT |
| `noise_id` | `observation_noise_v1.noise_id` | N:1 | STRICT |

**`question_observation_models_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_entity_id` | `biomarker_node_definitions_v1 OR derived_feature_definitions_v1` | N:1 | POLYMORPHIC via target_entity_type |

**`normalization_refs_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_entity_id` | `instrument_definitions_v1 OR measure_definitions_v1 OR derived_feature_definitions_v1` | N:1 | POLYMORPHIC via target_entity_type |
| `source_study_id` | `study_registry_v1.study_id` | N:1 | NULLABLE |

**`observation_noise_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_entity_id` | `instrument_definitions_v1 OR measure_definitions_v1 OR derived_feature_definitions_v1 OR question_bank_v1` | N:1 | POLYMORPHIC via target_entity_type |
| `source_study_id` | `study_registry_v1.study_id` | N:1 | NULLABLE |

**`pathways_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `entry_node_ids_json` | `biomarker_node_definitions_v1.node_id (JSON array)` | N:M | JSON-ARRAY FK |
| `exit_node_ids_json` | `biomarker_node_definitions_v1.node_id (JSON array)` | N:M | JSON-ARRAY FK |
| `intermediate_node_ids_json` | `biomarker_node_definitions_v1.node_id (JSON array)` | N:M | JSON-ARRAY FK |
| `edge_relation_ids_json` | `edge_relations_definitions_v1.edge_relation_id (JSON array)` | N:M | JSON-ARRAY FK |

**`pathway_interactions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `pathway_a_id` | `pathways_v1.pathway_id` | N:1 | STRICT |
| `pathway_b_id` | `pathways_v1.pathway_id` | N:1 | STRICT |

**`intervention_synergy_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `action_a_id` | `action_catalog_v1.action_id` | N:1 | STRICT |
| `action_b_id` | `action_catalog_v1.action_id` | N:1 | STRICT |
| `source_study_id` | `study_registry_v1.study_id` | N:1 | NULLABLE |

**`recovery_trajectories_v1`** — ROOT (no outbound FKs)

**`biomarker_correlations_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `node_a_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `node_b_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |

**`feedback_loops_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `edge_relation_ids_json` | `edge_relations_definitions_v1.edge_relation_id (JSON array)` | N:M | JSON-ARRAY FK |
| `node_ids_json` | `biomarker_node_definitions_v1.node_id (JSON array)` | N:M | JSON-ARRAY FK |
| `breaking_intervention` | `action_catalog_v1.action_id` | N:1 | NULLABLE |

**`intervention_kernels_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |

---

### Class B

**`study_registry_v1`** — ROOT (no outbound FKs)

**`study_cohort_profiles_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `study_id` | `study_registry_v1.study_id` | N:1 | STRICT |

**`profile_data_streams_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `profile_id` | `study_cohort_profiles_v1.profile_id` | N:1 | STRICT |
| `instrument_id` | `instrument_definitions_v1.instrument_id` | N:1 | NULLABLE |
| `measure_id` | `measure_definitions_v1.measure_id` | N:1 | NULLABLE |

**`stream_timepoints_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `stream_id` | `profile_data_streams_v1.stream_id` | N:1 | STRICT |

**`ontology_links_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `study_id` | `study_registry_v1.study_id` | N:1 | STRICT |
| `target_id` | `Polymorphic via target_type` | N:1 | POLYMORPHIC |

**`edge_evidence_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `study_id` | `study_registry_v1.study_id` | N:1 | STRICT |
| `edge_relation_id` | `edge_relations_definitions_v1.edge_relation_id` | N:1 | STRICT |
| `profile_id` | `study_cohort_profiles_v1.profile_id` | N:1 | STRICT |
| `instrument_id` | `instrument_definitions_v1.instrument_id` | N:1 | NULLABLE |
| `measure_id` | `measure_definitions_v1.measure_id` | N:1 | NULLABLE |
| `stream_id` | `profile_data_streams_v1.stream_id` | N:1 | NULLABLE |
| `harmonization_rule_id` | `harmonization_rules_v1.rule_id` | N:1 | NULLABLE |

**`edge_param_builds_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `edge_param_id` | `edges_v1.edge_param_id` | N:1 | STRICT |
| `contributing_ler_ids_json` | `edge_evidence_v1.ler_id (JSON array)` | N:M | JSON-ARRAY FK |

**`triangulation_evidence_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `triangulation_id` | `triangulation_sets_v1.triangulation_id` | N:1 | STRICT |
| `profile_id` | `study_cohort_profiles_v1.profile_id` | N:1 | STRICT |
| `study_id` | `study_registry_v1.study_id` | N:1 | STRICT |

**`pathway_biomarkers_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `pathway_id` | `pathways_v1.pathway_id` | N:1 | STRICT |
| `node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `measure_id` | `measure_definitions_v1.measure_id` | N:1 | STRICT |
| `source_study_id` | `study_registry_v1.study_id` | N:1 | STRICT |
| `source_ler_id` | `edge_evidence_v1.ler_id` | N:1 | NULLABLE |

---

### Class C

**`edges_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `edge_relation_id` | `edge_relations_definitions_v1.edge_relation_id` | N:1 | STRICT |
| `outcome_measure_id` | `measure_definitions_v1.measure_id` | N:1 | NULLABLE |
| `constraint_ids_json` | `literary_constraints_v1.rule_id (JSON array)` | N:M | JSON-ARRAY FK |
| `supporting_ler_ids_json` | `edge_evidence_v1.ler_id (JSON array)` | N:M | JSON-ARRAY FK |

**`dose_bridges_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |
| `target_feature_id` | `derived_feature_definitions_v1.feature_id` | N:1 | NULLABLE |
| `target_node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |
| `prior_id` | `literary_mechanistic_priors_v1.prior_id` | N:1 | NULLABLE |
| `anchor_id` | `outcome_anchors_v1.anchor_id` | N:1 | NULLABLE |

**`node_priors_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `node_id` | `biomarker_node_definitions_v1.node_id` | N:1 | STRICT |

**`outcome_anchors_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_id` | `biomarker_node_definitions_v1 OR derived_feature_definitions_v1` | N:1 | POLYMORPHIC via target_type |

**`state_estimator_specs_v1`** — ROOT (no outbound FKs)

---

### Class D

**`objective_specs_v1`** — ROOT (no outbound FKs)

**`safety_policies_v1`** — ROOT (no outbound FKs)

**`escalation_policies_v1`** — ROOT (no outbound FKs)

**`status_quo_rules_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |

**`voi_rules_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `target_ref_id` | `biomarker_node_definitions_v1 OR derived_feature_definitions_v1` | N:1 | POLYMORPHIC via target_ref_type |

---

### Class E

**`state_snapshots_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `estimator_id` | `state_estimator_specs_v1.estimator_id` | N:1 | STRICT |
| `prior_id` | `node_priors_v1.prior_id` | N:1 | NULLABLE |

**`scenario_definitions_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `state_id` | `state_snapshots_v1.state_id` | N:1 | STRICT |

**`scenario_items_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `scenario_id` | `scenario_definitions_v1.scenario_id` | N:1 | STRICT |
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |

**`schedule_plans_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `scenario_id` | `scenario_definitions_v1.scenario_id` | N:1 | STRICT |

**`schedule_items_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `schedule_id` | `schedule_plans_v1.schedule_id` | N:1 | STRICT |
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |

**`recommendation_runs_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `state_id` | `state_snapshots_v1.state_id` | N:1 | STRICT |
| `objective_id` | `objective_specs_v1.objective_id` | N:1 | STRICT |
| `safety_policy_id` | `safety_policies_v1.safety_policy_id` | N:1 | STRICT |
| `escalation_id` | `escalation_policies_v1.escalation_id` | N:1 | STRICT |
| `selected_schedule_id` | `schedule_plans_v1.schedule_id` | N:1 | NULLABLE |

**`simulation_trace_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `scenario_id` | `scenario_definitions_v1.scenario_id` | N:1 | STRICT |

**`decision_trace_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `schedule_id` | `schedule_plans_v1.schedule_id` | N:1 | NULLABLE |

**`contraindication_eval_trace_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `state_id` | `state_snapshots_v1.state_id` | N:1 | STRICT |
| `scenario_id` | `scenario_definitions_v1.scenario_id` | N:1 | STRICT |
| `action_id` | `action_catalog_v1.action_id` | N:1 | STRICT |
| `rule_id` | `contraindication_rules_v1.rule_id` | N:1 | STRICT |

**`question_selection_trace_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `state_id` | `state_snapshots_v1.state_id` | N:1 | STRICT |

**`modifier_eval_trace_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `state_id` | `state_snapshots_v1.state_id` | N:1 | STRICT |
| `modifier_id` | `baseline_modifier_definitions_v1.modifier_id` | N:1 | STRICT |
| `edge_param_id` | `edges_v1.edge_param_id` | N:1 | STRICT |
| `variable_id` | `variable_definitions_v1.variable_id` | N:1 | STRICT |

**`question_sequence_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `run_id` | `recommendation_runs_v1.run_id` | N:1 | STRICT |
| `question_id` | `question_bank_v1.question_id` | N:1 | STRICT |
| `state_id_before` | `state_snapshots_v1.state_id` | N:1 | STRICT |
| `state_id_after` | `state_snapshots_v1.state_id` | N:1 | STRICT |
| `observation_model_id` | `question_observation_models_v1.model_id` | N:1 | STRICT |
| `selection_trace_id` | `question_selection_trace_v1.qtrace_id` | N:1 | STRICT |

**`extraction_audit_v1`**

| Source Column | → Target | Cardinality | Enforcement |
|-------------|----------|-------------|-------------|
| `study_id` | `study_registry_v1.study_id` | N:1 | STRICT |

---

## 4. FK Count Summary

**Total FK relationships: 128**
---

## 5. Codebase FK Extensions

The codebase maintains additional FK relationships through tables not in the 64-table spec. Key extended wiring:

### 5.1 Extended Intervention Chain (7 codebase tables → spec's 2)

```
intervention_definitions_v1
  → intervention_mapping_v1.intervention_id
    → intervention_protocols_v1.intervention_id
      → protocol_effects_v1.protocol_id
        → dose_response_functions_v1.protocol_effect_id
          → dose_translations_v1.function_id
  → interaction_effects_v1.intervention_a_id, intervention_b_id
```

**Spec equivalent:** This chain compiles into `action_catalog_v1` + `dose_bridges_v1`. The extended chain is the Class A source; the spec tables are the Class C compiled output.

### 5.2 Extended Modifier Chain (5 codebase tables → spec's 2)

```
effect_modifiers_v2
  → edge_modifier_params_v1.modifier_id
  → chemo_agent_modifiers_v1.modifier_id
  → modifier_activation_rules_v1.modifier_id
  → compliance_modifiers_v1.modifier_id
```

**Spec equivalent:** All migrate into `baseline_modifier_definitions_v1` + `variable_definitions_v1`.

### 5.3 Extraction Pipeline FKs (not in spec)

```
search_strategy_v1
  → prisma_screening_log_v1.strategy_id
    → triage_records_v1.screening_id
      → study_registry_v1.study_id  ← (enters spec FK chain here)
```

**Recommendation:** Retain these for PRISMA compliance. They feed into the spec's evidence chain at `study_registry_v1`.


---

## 6. Dependency Tiers (Fill Order Enforcement)

The FK graph enforces this fill order (from `02_MACRO_OVERVIEW_OF_SYSTEMS.md`):

| Tier | Fill Order | Tables | FK Constraint |
|------|-----------|--------|---------------|
| 0 | Bootstrap Core | `biomarker_node_definitions_v1` (ROOT), `harmonization_rules_v1` (ROOT), `contraindication_escalation_policy_v1` (ROOT), `description_templates_v1` (ROOT), `action_catalog_v1` (ROOT), `state_estimator_specs_v1` (ROOT), Class D policy tables (ROOT) | No FK parents — can be filled in any order |
| 1 | Bootstrap Dependent | `edge_relations_definitions_v1`, `instrument_definitions_v1`, `measure_definitions_v1`, `variable_definitions_v1`, most other Class A tables | FK to Tier 0 tables — Tier 0 must exist first |
| 2 | Bootstrap Extended | `edge_ontology_v1`, `triangulation_members_v1`, `pathways_v1`, `baseline_modifier_definitions_v1` | FK to Tier 1 tables |
| 0.5 | Per-Paper Entry | `study_registry_v1` | ROOT for evidence chain — no FK parents |
| 3 | Per-Paper Extraction | `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1` | FK chain: study → cohort → stream → timepoint |
| 4 | Per-Paper Evidence | `edge_evidence_v1`, `triangulation_evidence_v1`, `ontology_links_v1` | FK to both Class A definitions AND Class B study tables |
| 5 | Per-Paper Audit | `pathway_biomarkers_v1` | FK to pathways + evidence |
| 6 | Compilation | `edge_param_builds_v1` | FK to edge_evidence |
| 7 | Compiled Output | `edges_v1`, `dose_bridges_v1`, `node_priors_v1`, `outcome_anchors_v1` | FK to Class A + B, compiled from evidence |
| 7.5 | Post-Compilation Validation | `publication_bias_results_v1`, `chain_validation_results_v1` | FK to edges_v1 + pathways_v1 + build_manifests_v1. Writes back to edges_v1 (SE inflation). |
| 8 | Offline Analysis | `complexity_scaling_results_v1` | FK to edges_v1 + pathways_v1. Offline batch job (VAL-01). |
| 9 | Runtime (per-session) | All Class E tables, `population_archetypes_v1` | FK to `recommendation_runs_v1` (session anchor) + compiled tables |

**New FK Relationships (from architecture patch):**

| Source Table | Source Column | → Target Table | Target Column | Cardinality | Notes |
|-------------|-------------|---------------|---------------|-------------|-------|
| chain_validation_results_v1 | pathway_id | → pathways_v1 | pathway_id | N:1 | Each validation result tests one pathway |
| chain_validation_results_v1 | build_id | → build_manifests_v1 | build_id | N:1 | Build provenance |
| publication_bias_results_v1 | edge_param_id | → edges_v1 | edge_param_id | 1:1 | One bias assessment per compiled edge |
| publication_bias_results_v1 | build_id | → build_manifests_v1 | build_id | N:1 | Build provenance |
| recommendation_runs_v1 | archetype_id | → population_archetypes_v1 | archetype_id | N:1 | Patient-to-archetype assignment |
| mid_thresholds_v1 | domain_id | — (maps to node_domain values) | — | 1:1 per domain | Curated; no FK enforced (semantic mapping) |

**Feedback FKs (write-back from validation to compiled tables):**

| Source (validator) | Target (updated) | Columns Updated | Trigger |
|-------------------|-------------------|----------------|---------|
| EX-P4B (pub bias) | edges_v1 | pub_bias_risk, se_inflation_pub_bias | After publication bias assessment |
| EX-P5-SEF (coherence) | edges_v1 | coherence_flag, se_inflation_coherence | After chain-vs-direct validation |
| EX-P5-EV (E-values) | edges_v1 | e_value, robustness_value | After E-value computation |

**Rule:** No table can be populated until ALL of its FK parent tables contain the referenced rows.

---

*End of FK Wiring Map v4.0*

**Supersedes:** v3.0. Added Tier 7.5 (post-compilation validation), Tier 8 (offline analysis). Added 6 new FK relationships for 5 new tables. Added 3 feedback FK paths (write-back from validation into edges_v1).
