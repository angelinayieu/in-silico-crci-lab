# CRCI Framework — Complete Table Registry
## 64-Table Master Registry with Identity Cards

**Version:** 3.0 (Consolidated — merges TABLE_IDENTITY_SYSTEM_v2.md Part 6 + 5 resolved phantom tables from 02_COMPLETE_SCHEMAS_v2_1.md)

**Purpose:** The single source of truth for table metadata. Every persisted table gets a 16-field identity card documenting its lifecycle class, ownership, wiring, fill order, and scaling behavior.

**Companion documents:**
- `01_DATA_ARCHITECTURE_PHILOSOPHY.md` — What the identity card fields mean
- `05_TABLE_SCHEMAS.md` — Full column schemas (the detailed view)
- `06_FK_WIRING_MAP.md` — Foreign key graph

---

## Summary Registry (64 Tables)

| # | Table | Class | Cols | System | Role | Fill Order | Scales With |
|---|-------|-------|------|--------|------|------------|-------------|
| A1 | `edge_relations_definitions_v1` | A | 15 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A2 | `edge_ontology_v1` | A | 12 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A3 | `biomarker_node_definitions_v1` | A | 17 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A4 | `instrument_definitions_v1` | A | 33 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A5 | `measure_definitions_v1` | A | 36 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A6 | `harmonization_rules_v1` | A | 10 | SYS_EXTRACTION | SOURCE | Bootstrap | domain_complexity |
| A7 | `predictor_alignment_rules_v1` | A | 11 | SYS_EXTRACTION | SOURCE | Bootstrap | domain_complexity |
| A8 | `literary_mechanistic_priors_v1` | A | 16 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A9 | `literary_constraints_v1` | A | 23 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A10 | `contraindication_rules_v1` | A | 18 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A11 | `action_contraindication_links_v1` | A | 8 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A12 | `contraindication_escalation_policy_v1` | A | 7 | SYS_RUNTIME | SOURCE | Bootstrap | policy_choices |
| A13 | `validation_rules_v1` | A | 15 | SHARED | CONFIG | Bootstrap | domain_complexity |
| A14 | `variable_definitions_v1` | A | 15 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A15 | `variable_to_input_map_v1` | A | 14 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A16 | `baseline_modifier_definitions_v1` | A | 17 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A17 | `derived_feature_definitions_v1` | A | 59 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A18 | `triangulation_sets_v1` | A | 13 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A19 | `triangulation_members_v1` | A | 10 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A20 | `description_templates_v1` | A | 6 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A21 | `action_catalog_v1` | A | 20 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A22 | `question_bank_v1` | A | 39 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A23 | `question_observation_models_v1` | A | 9 | SYS_RUNTIME | SOURCE | Bootstrap | domain_complexity |
| A24 | `normalization_refs_v1` | A | 20 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A25 | `observation_noise_v1` | A | 17 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A26 | `pathways_v1` | A | 15 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A27 | `pathway_interactions_v1` | A | 12 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A28 | `intervention_synergy_v1` | A | 14 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A29 | `recovery_trajectories_v1` | A | 12 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A30 | `biomarker_correlations_v1` | A | 11 | SHARED | SOURCE | Bootstrap | fixed |
| A31 | `feedback_loops_v1` | A | 12 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A32 | `intervention_kernels_v1` | A | 14 | SHARED | SOURCE | Bootstrap | domain_complexity |
| A33 | `mid_thresholds_v1` | A | 8 | SHARED | SOURCE | Bootstrap | fixed |
| B1 | `study_registry_v1` | B | 11 | SYS_EXTRACTION | DERIVED | 0.5 | papers_processed |
| B2 | `study_cohort_profiles_v1` | B | 33 | SYS_EXTRACTION | DERIVED | 1 | papers_processed |
| B3 | `profile_data_streams_v1` | B | 25 | SYS_EXTRACTION | DERIVED | 1 | papers_processed |
| B4 | `stream_timepoints_v1` | B | 20 | SYS_EXTRACTION | DERIVED | 1 | papers_processed |
| B5 | `ontology_links_v1` | B | 11 | SHARED | DERIVED | 1 | papers_processed |
| B6 | `edge_evidence_v1` | B | 75 | SHARED | DERIVED | 2 | papers_processed |
| B7 | `edge_param_builds_v1` | B | 18 | SYS_EXTRACTION | AUDIT | 6 | edges_compiled |
| B8 | `triangulation_evidence_v1` | B | 19 | SHARED | DERIVED | 2 | papers_processed |
| B9 | `pathway_biomarkers_v1` | B | 14 | SHARED | DERIVED | 3 | papers_processed |
| C1 | `edges_v1` | C | 39 | SHARED | DERIVED | 7 | edges_compiled |
| C2 | `dose_bridges_v1` | C | 24 | SHARED | DERIVED | 7 | domain_complexity |
| C3 | `node_priors_v1` | C | 14 | SHARED | DERIVED | 7 | domain_complexity |
| C4 | `outcome_anchors_v1` | C | 10 | SHARED | DERIVED | 7 | domain_complexity |
| C5 | `state_estimator_specs_v1` | C | 18 | SYS_ALGORITHM | CONFIG | Bootstrap | fixed |
| C6 | `chain_validation_results_v1` | C | 17 | SHARED | DERIVED | 7 | edges_compiled |
| C7 | `publication_bias_results_v1` | C | 14 | SHARED | DERIVED | 7 | edges_compiled |
| D1 | `objective_specs_v1` | D | 9 | SYS_RUNTIME | CONFIG | Bootstrap | policy_choices |
| D2 | `safety_policies_v1` | D | 7 | SYS_RUNTIME | CONFIG | Bootstrap | policy_choices |
| D3 | `escalation_policies_v1` | D | 7 | SYS_RUNTIME | CONFIG | Bootstrap | policy_choices |
| D4 | `status_quo_rules_v1` | D | 8 | SYS_RUNTIME | CONFIG | Bootstrap | policy_choices |
| D5 | `voi_rules_v1` | D | 8 | SYS_RUNTIME | CONFIG | Bootstrap | policy_choices |
| D6 | `complexity_scaling_results_v1` | D | 12 | SYS_VALIDATION | AUDIT | Offline | offline_validation |
| D7 | `population_archetypes_v1` | D | 10 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E1 | `state_snapshots_v1` | E | 16 | SYS_ALGORITHM | OUTPUT | 9 | users_x_sessions |
| E2 | `scenario_definitions_v1` | E | 12 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E3 | `scenario_items_v1` | E | 11 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E4 | `schedule_plans_v1` | E | 12 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E5 | `schedule_items_v1` | E | 11 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E6 | `recommendation_runs_v1` | E | 18 | SYS_RUNTIME | AUDIT | 9 | users_x_sessions |
| E7 | `simulation_trace_v1` | E | 10 | SYS_ALGORITHM | AUDIT | 9 | users_x_sessions |
| E8 | `decision_trace_v1` | E | 9 | SYS_RUNTIME | AUDIT | 9 | users_x_sessions |
| E9 | `contraindication_eval_trace_v1` | E | 14 | SYS_RUNTIME | AUDIT | 9 | users_x_sessions |
| E10 | `question_selection_trace_v1` | E | 18 | SYS_RUNTIME | AUDIT | 9 | users_x_sessions |
| E11 | `modifier_eval_trace_v1` | E | 15 | SYS_ALGORITHM | AUDIT | 9 | users_x_sessions |
| E12 | `question_sequence_v1` | E | 17 | SYS_RUNTIME | OUTPUT | 9 | users_x_sessions |
| E13 | `extraction_audit_v1` | E | 16 | SYS_EXTRACTION | AUDIT | 1 | papers_processed |

**Total: 69 tables, ~1,231 columns** (includes 6 new columns on edges_v1, 7 new columns on evaluation_results_v1)
---

## Identity Cards

Every table's 16-field identity card. See `01_DATA_ARCHITECTURE_PHILOSOPHY.md` Part 4 for field definitions.

## CLASS A — KNOWLEDGE TABLES (27 tables)

### A1. edge_relations_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by EX-P1, EX-P2, ALG-A)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Ontology authors (offline)
readers:            ExtractionValidator, Router, CausalGraph, UI
foreign_keys:       biomarker_node_definitions_v1.node_id (source/target)
row_semantics:      One row = one permitted causal edge (source→target→mechanism)
fill_order:         Bootstrap
write_condition:    Human decision: "this causal relationship exists in our model"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       16
```

### A2. edge_ontology_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by EX-P2 CG4 gate, ALG runtime guardrails)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Ontology authors (offline)
readers:            ConversionAppropriatenessGate (CG4), RuntimeGuardrails
foreign_keys:       edge_relations_definitions_v1.edge_relation_id
row_semantics:      One row = operational constraints for one edge type
fill_order:         Bootstrap
write_condition:    Human decision: "these operations are allowed on this edge"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       13
```

### A3. biomarker_node_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by nearly everything)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Ontology authors (offline)
readers:            CausalGraph, Orientation, MeasurementModel, MCEngine, UI, and ~15 more
foreign_keys:       none (ROOT table — other tables reference this)
row_semantics:      One row = one node in the causal graph
fill_order:         Bootstrap
write_condition:    Human decision: "this biomarker/construct exists in our model"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       18
```

### A4. instrument_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by EX-P1, EX-P2, ALG-C measurement model)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            OutcomeAgent, Orientation, MeasurementModel, UI
foreign_keys:       biomarker_node_definitions_v1.node_id (maps_to_node_id),
                    normalization_refs_v1.norm_id, observation_noise_v1.noise_id
row_semantics:      One row = one assessment instrument (PSQI, FACT-Cog, etc.)
fill_order:         Bootstrap
write_condition:    Human decision: "we recognize this instrument"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       34
```

### A5. measure_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by EX-P2 harmonization, ALG-C)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            Harmonizer, MeasurementModel, DoseBridge, UI
foreign_keys:       biomarker_node_definitions_v1.node_id (maps_to_node_id),
                    normalization_refs_v1.norm_id, observation_noise_v1.noise_id
row_semantics:      One row = one biomarker/wearable/proxy measurement type
fill_order:         Bootstrap
write_condition:    Human decision: "we track this measurement"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       37
```

### A6. harmonization_rules_v1
```
lifecycle_class:    A
system:             SYS_EXTRACTION
pipeline_phase:     EX-P2 (evidence harmonization)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Methods team (offline)
readers:            Harmonizer (EX-P2-S3), EdgeCompilation
foreign_keys:       none
row_semantics:      One row = one deterministic conversion formula (effect type → common scale)
fill_order:         Bootstrap
write_condition:    Human decision: "this conversion is statistically valid"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       11
```

### A7. predictor_alignment_rules_v1
```
lifecycle_class:    A
system:             SYS_EXTRACTION
pipeline_phase:     EX-P2 (cohort alignment)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Methods team (offline)
readers:            AlignmentEngine
foreign_keys:       study_cohort_profiles_v1.profile_id, measure_definitions_v1.measure_id
row_semantics:      One row = one alignment rule for matching cohorts to evidence
fill_order:         Bootstrap
write_condition:    Human decision: "this alignment is methodologically appropriate"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       12
```

### A8. literary_mechanistic_priors_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read at runtime Stage 6)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            SimulationEngine (Stage 6), EdgeCompilation
foreign_keys:       study_registry_v1.study_id (provenance)
row_semantics:      One row = one literature-informed prior distribution
fill_order:         Bootstrap
write_condition:    Human decision: "this prior is supported by domain literature"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       17
```

### A9. literary_constraints_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read at runtime Stage 6)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            ConstraintEnforcer (Stage 6), SimulationEngine
foreign_keys:       measure_definitions_v1.measure_id, study_registry_v1.study_id
row_semantics:      One row = one biological bound on trajectories
fill_order:         Bootstrap
write_condition:    Human decision: "this biological constraint is real"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       24
```

### A10. contraindication_rules_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (safety gating Stage 4, Stage 7)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            SafetyFilter, ContraindicationEvaluator
foreign_keys:       contraindication_escalation_policy_v1.escalation_id
row_semantics:      One row = one safety rule with trigger predicate
fill_order:         Bootstrap
write_condition:    Human decision: "this safety rule must be enforced"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       19
```

### A11. action_contraindication_links_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (safety gating)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            SafetyFilter
foreign_keys:       action_catalog_v1.action_id, contraindication_rules_v1.rule_id
row_semantics:      One row = one action↔safety rule link
fill_order:         Bootstrap
write_condition:    Human decision: "this safety rule applies to this action"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       9
```

### A12. contraindication_escalation_policy_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (escalation handling)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            EscalationHandler
foreign_keys:       none (ROOT — referenced by contraindication_rules_v1)
row_semantics:      One row = one escalation behavior for contraindication context
fill_order:         Bootstrap
write_condition:    Human decision: "this is how we escalate this type of trigger"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       8
```

### A13. validation_rules_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     ETL validation + Runtime validation
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Engineering + clinical team (offline)
readers:            ValidationEngine (commit-time), RuntimeValidator
foreign_keys:       (polymorphic — each rule references the table it validates)
row_semantics:      One row = one validation check (FK integrity, range, consistency)
fill_order:         Bootstrap
write_condition:    Engineering decision: "this invariant must hold"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       68
```

### A14. variable_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (modifier resolution), ETL validation
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            ModifierResolver, VariableMapper, StateEstimator
foreign_keys:       biomarker_node_definitions_v1.node_id OR
                    derived_feature_definitions_v1.feature_id (polymorphic via source_ref_id)
row_semantics:      One row = one patient variable that modifies edge parameters
fill_order:         Bootstrap
write_condition:    Human decision: "this patient characteristic affects predictions"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       16
```

### A15. variable_to_input_map_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (intake processing)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Engineering team (offline)
readers:            IntakeProcessor, ModifierResolver
foreign_keys:       variable_definitions_v1.variable_id
row_semantics:      One row = one mapping from patient input field to engine variable
fill_order:         Bootstrap
write_condition:    Engineering decision: "this input field maps to this variable"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       15
```

### A16. baseline_modifier_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (before simulation)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            ModifierEngine, SimulationEngine
foreign_keys:       variable_definitions_v1.variable_id (via required_variable_ids_json),
                    edge_evidence_v1.ler_id (via source_ler_ids)
row_semantics:      One row = one modifier definition (how a variable shifts an edge parameter)
fill_order:         Bootstrap
write_condition:    Human decision: "this baseline variable modifies this relationship"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       18
```

### A17. derived_feature_definitions_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (feature computation, every invocation)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Engineering + clinical team (offline)
readers:            FeatureEngine, StateEstimator, TriangulationEngine
foreign_keys:       normalization_refs_v1.norm_id, observation_noise_v1.noise_id,
                    derived_feature_definitions_v1.feature_id (self-ref via dependency_ids)
row_semantics:      One row = one computed feature (formula, dependencies, timing)
fill_order:         Bootstrap
write_condition:    Engineering decision: "this derived feature is needed by the model"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       60
```

### A18. triangulation_sets_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (within-construct fusion)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            TriangulationEngine, StateEstimator
foreign_keys:       biomarker_node_definitions_v1.node_id (target_node_id),
                    derived_feature_definitions_v1.feature_id (output_feature_id)
row_semantics:      One row = one triangulation group for a target construct
fill_order:         Bootstrap
write_condition:    Human decision: "these measurements triangulate the same construct"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       14
```

### A19. triangulation_members_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (fusion membership)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            TriangulationEngine
foreign_keys:       triangulation_sets_v1.triangulation_id,
                    derived_feature_definitions_v1.feature_id OR measure_definitions_v1.measure_id (polymorphic)
row_semantics:      One row = one member variable in a triangulation set
fill_order:         Bootstrap
write_condition:    Human decision: "this variable belongs to this triangulation set"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       11
```

### A20. description_templates_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (UI text generation)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Product team (offline)
readers:            UIRenderer, ReportGenerator
foreign_keys:       none
row_semantics:      One row = one text template for consistent UI generation
fill_order:         Bootstrap
write_condition:    Product decision: "we need this standardized text pattern"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       7
```

### A21. action_catalog_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (candidate gen Stage 4, optimization Stage 7)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            CandidateGenerator, Optimizer, SafetyFilter, UI
foreign_keys:       none (ROOT — referenced by many tables)
row_semantics:      One row = one atomic intervention the engine may recommend
fill_order:         Bootstrap
write_condition:    Clinical decision: "this intervention should be recommendable"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       21
```

### A22. question_bank_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (adaptive questioning)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            VOISelector, QuestionPresenter, UI
foreign_keys:       question_observation_models_v1.model_id,
                    observation_noise_v1.noise_id
row_semantics:      One row = one question the system can ask
fill_order:         Bootstrap
write_condition:    Clinical decision: "this question provides useful information"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       40
```

### A23. question_observation_models_v1
```
lifecycle_class:    A
system:             SYS_RUNTIME
pipeline_phase:     Runtime (answer→state update)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical + engineering team (offline)
readers:            StateUpdater
foreign_keys:       question_bank_v1.question_id,
                    derived_feature_definitions_v1.feature_id OR biomarker_node_definitions_v1.node_id (polymorphic)
row_semantics:      One row = one answer→feature/node update mapping
fill_order:         Bootstrap
write_condition:    Clinical decision: "this answer maps to this model update"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       10
```

### A24. normalization_refs_v1 [NEW]
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (feature normalization), ETL (z-scoring)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Methods team (offline, from psychometric/biomarker literature)
readers:            FeatureEngine, DoseBridge, MeasurementModel
foreign_keys:       instrument_definitions_v1 OR measure_definitions_v1 OR
                    derived_feature_definitions_v1 (polymorphic via target_entity_id)
row_semantics:      One row = population reference stats for normalizing one entity
fill_order:         Bootstrap
write_condition:    Methods decision: "this norming reference is appropriate for our population"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       20
```

### A25. observation_noise_v1 [NEW]
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Runtime (Bayesian state estimation observation weighting)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Methods team (offline, from psychometric/biomarker literature)
readers:            StateEstimator, TriangulationEngine, FeatureEngine
foreign_keys:       instrument_definitions_v1 OR measure_definitions_v1 OR
                    derived_feature_definitions_v1 OR question_bank_v1 (polymorphic)
row_semantics:      One row = measurement noise/reliability for one entity
fill_order:         Bootstrap
write_condition:    Methods decision: "this reliability estimate is appropriate"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       17
```

### A26. pathways_v1 [NEW]
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG pathway reasoning)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            PathwayEngine, CausalGraph, UI
foreign_keys:       biomarker_node_definitions_v1.node_id (via JSON arrays),
                    edge_relations_definitions_v1.edge_relation_id (via JSON array)
row_semantics:      One row = one biological/behavioral pathway in the CRCI model
fill_order:         Bootstrap
write_condition:    Clinical decision: "this pathway is relevant to CRCI"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       15
```

### A27. pathway_interactions_v1 [NEW]
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG cross-pathway reasoning)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            PathwayEngine
foreign_keys:       pathways_v1.pathway_id (pathway_a_id, pathway_b_id)
row_semantics:      One row = one interaction between two pathways
fill_order:         Bootstrap
write_condition:    Clinical decision: "these pathways interact in this way"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       12
```

---

## CLASS B — EVIDENCE ACCUMULATION (9 tables)


### A28. intervention_synergy_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG-F, Stage G)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Domain experts (offline, from pathway structure analysis)
readers:            ForwardSimulator (ALG-F), ScheduleOptimizer (Stage G)
foreign_keys:       action_catalog_v1.action_id (intervention_a_id, intervention_b_id)
row_semantics:      One row = one pairwise intervention interaction record (synergy/antagonism)
fill_order:         Bootstrap
write_condition:    Human decision: "this intervention pair has a known interaction"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       14
```

### A29. recovery_trajectories_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG-F)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Domain experts (offline, from longitudinal study analysis)
readers:            ForwardSimulator (ALG-F)
foreign_keys:       None (standalone)
row_semantics:      One row = one treatment-context-specific recovery trajectory (r∞, τR, γR)
fill_order:         Bootstrap
write_condition:    Human decision: "this treatment context has a characterized recovery trajectory"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       12
```

### A30. biomarker_correlations_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG-C)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Domain experts (offline, from correlation analysis)
readers:            BayesianEstimator (ALG-C)
foreign_keys:       biomarker_node_definitions_v1.node_id (node_a_id, node_b_id)
row_semantics:      One row = one correlated biomarker pair with empirical ρ for block-diagonal D matrix
fill_order:         Bootstrap
write_condition:    Human decision: "these biomarkers are correlated and the correlation matters for precision"
scales_with:        fixed
retention_policy:   permanent
column_count:       11
```

### A31. feedback_loops_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG-F)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Domain experts (offline, from DAG analysis)
readers:            ForwardSimulator (ALG-F)
foreign_keys:       biomarker_node_definitions_v1.node_id (entry_node_id, exit_node_id); edge_relations_definitions_v1.edge_relation_id (loop_edges_json)
row_semantics:      One row = one feedback loop structure in the DAG with gain, period, stability, and breaking interventions
fill_order:         Bootstrap
write_condition:    Human decision: "this feedback structure exists in the causal model"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       12
```

### A32. intervention_kernels_v1
```
lifecycle_class:    A
system:             SHARED
pipeline_phase:     Bootstrap (read by ALG-F)
role:               SOURCE
mutability:         HUMAN_CURATED
writers:            Domain experts (offline, from temporal dynamics analysis)
readers:            ForwardSimulator (ALG-F)
foreign_keys:       action_catalog_v1.action_id
row_semantics:      One row = one temporal kernel specification per intervention (onset, build, steady-state, decay timing)
fill_order:         Bootstrap
write_condition:    Human decision: "this intervention has characterized temporal dynamics"
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       14
```

### B1. study_registry_v1
```
lifecycle_class:    B
system:             SYS_EXTRACTION
pipeline_phase:     EX-P1 (dedup gate, fill_order 0.5)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            MetadataAgent (EX-P1-AG1), or human
readers:            DedupChecker, AllDownstreamExtraction, UI
foreign_keys:       none (ROOT for evidence chain)
row_semantics:      One row = one paper the system has seen (DOI + content hash)
fill_order:         0.5
write_condition:    A new paper enters the extraction pipeline
scales_with:        papers_processed
retention_policy:   permanent
column_count:       12
```

### B2. study_cohort_profiles_v1
```
lifecycle_class:    B
system:             SYS_EXTRACTION
pipeline_phase:     EX-P1 (fill_order 1)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            CohortAgent (EX-P1-AG3), or human
readers:            AlignmentEngine, Aggregation, UI
foreign_keys:       study_registry_v1.study_id
row_semantics:      One row = one cohort slice within one study
fill_order:         1
write_condition:    A paper's cohorts are identified during extraction
scales_with:        papers_processed
retention_policy:   permanent
column_count:       34
```

### B3. profile_data_streams_v1
```
lifecycle_class:    B
system:             SYS_EXTRACTION
pipeline_phase:     EX-P1 (fill_order 1)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            CohortAgent, or human
readers:            AlignmentEngine, MeasurementModel
foreign_keys:       study_cohort_profiles_v1.profile_id,
                    instrument_definitions_v1.instrument_id,
                    measure_definitions_v1.measure_id
row_semantics:      One row = one data stream in one cohort profile
fill_order:         1
write_condition:    A cohort profile has identifiable data streams
scales_with:        papers_processed
retention_policy:   permanent
column_count:       26
```

### B4. stream_timepoints_v1
```
lifecycle_class:    B
system:             SYS_EXTRACTION
pipeline_phase:     EX-P1 (fill_order 1)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            CohortAgent, or human
readers:            TemporalEngine, AlignmentEngine
foreign_keys:       profile_data_streams_v1.stream_id
row_semantics:      One row = one measurement timepoint in one data stream
fill_order:         1
write_condition:    A data stream has identifiable timepoints
scales_with:        papers_processed
retention_policy:   permanent
column_count:       21
```

### B5. ontology_links_v1
```
lifecycle_class:    B
system:             SHARED
pipeline_phase:     Offline curation
role:               DERIVED
mutability:         APPEND_ONLY
writers:            Ontology curators (offline)
readers:            ProvenanceTracer, UI
foreign_keys:       study_registry_v1.study_id,
                    (polymorphic target_id → node/edge/instrument/measure)
row_semantics:      One row = one provenance link (why an entity exists in our ontology)
fill_order:         1
write_condition:    A supporting reference is identified for an ontology entity
scales_with:        papers_processed
retention_policy:   permanent
column_count:       12
```

### B6. edge_evidence_v1
```
lifecycle_class:    B
system:             SHARED
pipeline_phase:     EX-P2 (written), EX-P3 (assimilation), EX-P4 (aggregation), ALG-B
role:               DERIVED
mutability:         APPEND_ONLY
writers:            ClaimNormalizer (EX-P2-S7), or human
readers:            Assimilation, Aggregation, EvidenceBrowser, UI
foreign_keys:       study_registry_v1.study_id,
                    edge_relations_definitions_v1.edge_relation_id,
                    study_cohort_profiles_v1.profile_id,
                    instrument_definitions_v1.instrument_id,
                    measure_definitions_v1.measure_id,
                    profile_data_streams_v1.stream_id,
                    harmonization_rules_v1.rule_id
row_semantics:      One row = one extracted effect estimate from one paper for one edge
fill_order:         2
write_condition:    A paper yields a parseable effect size for a recognized edge
scales_with:        papers_processed
retention_policy:   permanent
column_count:       72
```

### B7. edge_param_builds_v1
```
lifecycle_class:    B
system:             SYS_EXTRACTION
pipeline_phase:     EX-P4 (aggregation audit trail)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            AggregationPipeline
readers:            ProvenanceTracer, QA
foreign_keys:       harmonization_rules_v1.rule_id (via JSON),
                    edges_v1.edge_param_id (via JSON)
row_semantics:      One row = one compilation step in evidence→edges build
fill_order:         6
write_condition:    Aggregation pipeline runs for an edge
scales_with:        edges_compiled
retention_policy:   permanent
column_count:       19
```

### B8. triangulation_evidence_v1
```
lifecycle_class:    B
system:             SHARED
pipeline_phase:     Offline (primary), Runtime (read-only reference)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            ExtractionPipeline (when papers report cross-method agreement)
readers:            TriangulationEngine (optional)
foreign_keys:       triangulation_sets_v1.triangulation_id,
                    study_cohort_profiles_v1.profile_id,
                    study_registry_v1.study_id
row_semantics:      One row = one cross-method agreement result from a paper
fill_order:         2
write_condition:    A paper reports multi-method agreement for a triangulable construct
scales_with:        papers_processed
retention_policy:   permanent
column_count:       20
```

### B9. pathway_biomarkers_v1 [NEW]
```
lifecycle_class:    B
system:             SHARED
pipeline_phase:     EX-P2 (extended extraction when pathway biomarkers are reported)
role:               DERIVED
mutability:         APPEND_ONLY
writers:            ExtractionPipeline, or human
readers:            PathwayEngine, CausalGraph
foreign_keys:       pathways_v1.pathway_id,
                    biomarker_node_definitions_v1.node_id,
                    measure_definitions_v1.measure_id,
                    study_registry_v1.study_id,
                    edge_evidence_v1.ler_id
row_semantics:      One row = one biomarker linked to one pathway with evidence
fill_order:         3
write_condition:    A paper reports a biomarker-pathway association
scales_with:        papers_processed
retention_policy:   permanent
column_count:       14
```

---

## CLASS C — COMPILED PARAMETERS (5 tables)

### C1. edges_v1
```
lifecycle_class:    C
system:             SHARED
pipeline_phase:     EX-P4 (written), ALG-A/C/D/E/F (read), Runtime (consumed)
role:               DERIVED
mutability:         COMPUTED
writers:            AggregationPipeline (THE ONLY WRITER)
readers:            CausalGraph, BayesianEstimator, MCEngine, DecisionStability,
                    TemporalEngine, SufficiencyAuditor, UI
foreign_keys:       edge_relations_definitions_v1.edge_relation_id,
                    measure_definitions_v1.measure_id,
                    literary_constraints_v1.rule_id (JSON),
                    edge_evidence_v1.ler_id (JSON)
row_semantics:      One row = one compiled edge parameter (pooled β, SE, grade)
fill_order:         7
write_condition:    Aggregation pipeline recompiles
scales_with:        edges_compiled
retention_policy:   until_recompile
column_count:       31
```

### C2. dose_bridges_v1
```
lifecycle_class:    C
system:             SHARED
pipeline_phase:     Runtime (dose translation)
role:               DERIVED
mutability:         COMPUTED (or HUMAN_CURATED — classification TBD)
writers:            DoseBridgeCompiler OR clinical team
readers:            SimulationEngine, Optimizer
foreign_keys:       action_catalog_v1.action_id,
                    derived_feature_definitions_v1.feature_id,
                    biomarker_node_definitions_v1.node_id,
                    literary_mechanistic_priors_v1.prior_id,
                    outcome_anchors_v1.anchor_id
row_semantics:      One row = one dose-to-effect bridge mapping
fill_order:         Bootstrap (if curated) or 7 (if compiled)
write_condition:    Dose equivalence is established for an action-node pair
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       57
```

### C3. node_priors_v1
```
lifecycle_class:    C
system:             SHARED
pipeline_phase:     Runtime (state estimation initialization)
role:               DERIVED
mutability:         COMPUTED
writers:            PriorCompiler
readers:            StateEstimator
foreign_keys:       biomarker_node_definitions_v1.node_id
row_semantics:      One row = one scoped prior distribution for one node
fill_order:         7
write_condition:    Prior compilation runs for a node
scales_with:        domain_complexity
retention_policy:   until_recompile
column_count:       15
```

### C4. outcome_anchors_v1
```
lifecycle_class:    C
system:             SHARED
pipeline_phase:     Runtime (Stage 9 reporting)
role:               DERIVED
mutability:         COMPUTED (or HUMAN_CURATED)
writers:            AnchorCompiler OR clinical team
readers:            ReportGenerator, UI
foreign_keys:       biomarker_node_definitions_v1.node_id OR
                    derived_feature_definitions_v1.feature_id (polymorphic)
row_semantics:      One row = one calibration anchor (z-space → interpretable scale)
fill_order:         Bootstrap (if curated) or 7 (if compiled)
write_condition:    Calibration reference is established for a target
scales_with:        domain_complexity
retention_policy:   permanent
column_count:       11
```

### C5. state_estimator_specs_v1
```
lifecycle_class:    C
system:             SYS_ALGORITHM
pipeline_phase:     Runtime (state estimation configuration)
role:               CONFIG
mutability:         COMPUTED (or HUMAN_CURATED)
writers:            Engineering team or SpecCompiler
readers:            StateEstimator
foreign_keys:       none (self-contained configuration)
row_semantics:      One row = one estimator configuration specification
fill_order:         Bootstrap
write_condition:    Estimator configuration is defined/updated
scales_with:        fixed
retention_policy:   permanent
column_count:       19
```

---

## CLASS D — RUNTIME POLICIES (5 tables)

### D1. objective_specs_v1
```
lifecycle_class:    D
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 7 optimization)
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Clinical + product team (offline)
readers:            Optimizer, DecisionEngine
foreign_keys:       none
row_semantics:      One row = one utility function / scoring specification
fill_order:         Bootstrap
write_condition:    Product decision: "this is how we score schedules"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       10
```

### D2. safety_policies_v1
```
lifecycle_class:    D
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Phase 0, Stage 4, Stage 7)
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            SafetyFilter
foreign_keys:       none
row_semantics:      One row = one trigger type → system behavior mapping
fill_order:         Bootstrap
write_condition:    Clinical decision: "this is how we respond to this trigger"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       8
```

### D3. escalation_policies_v1
```
lifecycle_class:    D
system:             SYS_RUNTIME
pipeline_phase:     Runtime (escalation handling)
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            EscalationHandler
foreign_keys:       none (ROOT)
row_semantics:      One row = one escalation behavior definition
fill_order:         Bootstrap
write_condition:    Clinical decision: "this is our escalation protocol"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       8
```

### D4. status_quo_rules_v1
```
lifecycle_class:    D
system:             SYS_RUNTIME
pipeline_phase:     Runtime (baseline dose construction)
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Clinical team (offline)
readers:            ScenarioBuilder
foreign_keys:       action_catalog_v1.action_id
row_semantics:      One row = baseline dose rule for one action
fill_order:         Bootstrap
write_condition:    Clinical decision: "this is the default dose assumption"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       9
```

### D5. voi_rules_v1
```
lifecycle_class:    D
system:             SYS_RUNTIME
pipeline_phase:     Runtime (adaptive questioning VOI)
role:               CONFIG
mutability:         HUMAN_CURATED
writers:            Clinical + product team (offline)
readers:            VOISelector
foreign_keys:       (polymorphic target_ref_id → node/feature)
row_semantics:      One row = one VOI policy parameter or gating rule
fill_order:         Bootstrap
write_condition:    Product decision: "this VOI heuristic governs question selection"
scales_with:        policy_choices
retention_policy:   permanent
column_count:       9
```

---

## CLASS E — RUNTIME OUTPUTS (13 tables)

### E1. state_snapshots_v1
```
lifecycle_class:    E
system:             SYS_ALGORITHM
pipeline_phase:     Runtime (Stage 3, after each Phase 2 update)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            StateEstimator
readers:            ScenarioBuilder, VOISelector, ContraindicationEvaluator, UI
foreign_keys:       recommendation_runs_v1.run_id,
                    state_estimator_specs_v1.estimator_id,
                    node_priors_v1.prior_id
row_semantics:      One row = one patient's Bayesian state estimate at one timestamp
fill_order:         9
write_condition:    Runtime engine performs state estimation
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       17
```

### E2. scenario_definitions_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 5)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            ScenarioBuilder
readers:            SimulationEngine, DecisionEngine
foreign_keys:       recommendation_runs_v1.run_id,
                    state_snapshots_v1.state_id
row_semantics:      One row = one what-if scenario configuration
fill_order:         9
write_condition:    Runtime engine generates candidate scenarios
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       13
```

### E3. scenario_items_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 5)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            ScenarioBuilder
readers:            SimulationEngine
foreign_keys:       scenario_definitions_v1.scenario_id,
                    action_catalog_v1.action_id
row_semantics:      One row = one action within one scenario
fill_order:         9
write_condition:    A scenario includes this action
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       12
```

### E4. schedule_plans_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 7)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            Optimizer
readers:            SchedulePresenter, UI
foreign_keys:       recommendation_runs_v1.run_id,
                    scenario_definitions_v1.scenario_id
row_semantics:      One row = one complete optimized schedule plan
fill_order:         9
write_condition:    Optimizer produces a schedule
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       13
```

### E5. schedule_items_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 7)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            Optimizer
readers:            SchedulePresenter, UI
foreign_keys:       schedule_plans_v1.schedule_id,
                    action_catalog_v1.action_id
row_semantics:      One row = one scheduled action within a plan
fill_order:         9
write_condition:    A schedule includes this action
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       12
```

### E6. recommendation_runs_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (run header — created first, referenced by all others)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            RuntimeOrchestrator
readers:            All Class E tables (via run_id FK), UI, AuditLog
foreign_keys:       state_snapshots_v1.state_id (base_state_id),
                    objective_specs_v1.objective_id,
                    safety_policies_v1.safety_policy_id,
                    escalation_policies_v1.escalation_id,
                    outcome_anchors_v1.anchor_id,
                    schedule_plans_v1.schedule_id (primary)
row_semantics:      One row = one engine execution (who, when, what config)
fill_order:         9
write_condition:    Engine starts a session
scales_with:        users_x_sessions
retention_policy:   regulatory_7_years
column_count:       19
```

### E7. simulation_trace_v1
```
lifecycle_class:    E
system:             SYS_ALGORITHM
pipeline_phase:     Runtime (Stage 6)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            MCEngine
readers:            DecisionEngine, QA
foreign_keys:       recommendation_runs_v1.run_id,
                    scenario_definitions_v1.scenario_id
row_semantics:      One row = one Monte Carlo simulation trace record
fill_order:         9
write_condition:    MC simulation runs for a scenario
scales_with:        users_x_sessions
retention_policy:   session_ttl_90
column_count:       11
```

### E8. decision_trace_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (Stage 7)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            DecisionEngine
readers:            RecommendationAssembler, QA
foreign_keys:       recommendation_runs_v1.run_id,
                    objective_specs_v1.objective_id,
                    schedule_plans_v1.schedule_id
row_semantics:      One row = one decision the engine made with rationale
fill_order:         9
write_condition:    Engine makes a ranked decision
scales_with:        users_x_sessions
retention_policy:   regulatory_7_years
column_count:       10
```

### E9. contraindication_eval_trace_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (safety evaluation)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            ContraindicationEvaluator
readers:            SafetyAudit, DecisionEngine
foreign_keys:       recommendation_runs_v1.run_id,
                    state_snapshots_v1.state_id,
                    scenario_definitions_v1.scenario_id,
                    action_catalog_v1.action_id,
                    contraindication_rules_v1.rule_id
row_semantics:      One row = one safety rule evaluation for one action
fill_order:         9
write_condition:    Safety filter evaluates a rule for an action
scales_with:        users_x_sessions
retention_policy:   regulatory_7_years
column_count:       15
```

### E10. question_selection_trace_v1
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (adaptive questioning)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            VOISelector
readers:            QuestionPresenter, QA
foreign_keys:       recommendation_runs_v1.run_id,
                    state_snapshots_v1.state_id
row_semantics:      One row = one question selection decision with VOI rationale
fill_order:         9
write_condition:    VOI selector chooses next question
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       19
```

### E11. modifier_eval_trace_v1 [NEW]
```
lifecycle_class:    E
system:             SYS_ALGORITHM
pipeline_phase:     Runtime (modifier resolution before simulation)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            ModifierEngine
readers:            PersonalizationAudit, QA
foreign_keys:       recommendation_runs_v1.run_id,
                    state_snapshots_v1.state_id,
                    baseline_modifier_definitions_v1.modifier_id,
                    edges_v1.edge_param_id,
                    variable_definitions_v1.variable_id
row_semantics:      One row = one modifier evaluation for one edge, one variable, one session
fill_order:         9
write_condition:    Modifier engine evaluates a baseline modifier
scales_with:        users_x_sessions
retention_policy:   session_ttl_365
column_count:       15
```

### E12. question_sequence_v1 [NEW]
```
lifecycle_class:    E
system:             SYS_RUNTIME
pipeline_phase:     Runtime (adaptive intake)
role:               OUTPUT
mutability:         APPEND_ONLY
writers:            IntakeProcessor
readers:            StateUpdater, SessionReview, UI
foreign_keys:       recommendation_runs_v1.run_id,
                    state_snapshots_v1.state_id (before/after),
                    question_bank_v1.question_id,
                    question_observation_models_v1.model_id,
                    question_selection_trace_v1.qtrace_id
row_semantics:      One row = one question asked and answered (or skipped) in one session
fill_order:         9
write_condition:    Patient answers (or skips) a question during intake
scales_with:        users_x_sessions
retention_policy:   regulatory_7_years
column_count:       17
```

### E13. extraction_audit_v1 [NEW]
```
lifecycle_class:    E
system:             SYS_EXTRACTION
pipeline_phase:     EX-P0 through EX-P5 (pipeline audit)
role:               AUDIT
mutability:         APPEND_ONLY
writers:            ExtractionOrchestrator
readers:            PipelineQA, Dashboard
foreign_keys:       study_registry_v1.study_id
row_semantics:      One row = one extraction stage execution for one paper
fill_order:         1
write_condition:    Extraction pipeline runs a stage for a paper
scales_with:        papers_processed
retention_policy:   permanent
column_count:       16
```

---


---

*End of Complete Table Registry v3.0*

**Supersedes:** `TABLE_IDENTITY_SYSTEM_v2.md` Part 6 (59 tables → 64 tables). Phantom tables A28–A32 now have full identity cards. Table count updated from 59 to 64 throughout.

**Note on column counts:** Column counts in identity cards reflect the spec schema (`05_TABLE_SCHEMAS.md`). Codebase column counts may differ — see `07_CODEBASE_ALIGNMENT.md` for reconciliation.
