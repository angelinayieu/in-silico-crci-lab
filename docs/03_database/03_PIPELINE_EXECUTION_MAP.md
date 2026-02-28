NEEDS UPDATING TO NEW METHEOD OFS ESPECIALLY LIEK SYSTEM EXTRACTION BUT THATS NOT IMPROTANT RIGHT NOW WHATS IMPROTANT IS THAT IT ACTRUALY WORKS WE CAN REFRENCE TO SUB DOCUMENTS FIRST BUT THIS IS JSUT TO LET U KNOW THAT THIS IS NOTT UDPATED!
# CRCI Framework — Pipeline Execution Map
## Stage-by-Stage Pipeline with Table Reads/Writes and Data Flow

**Version:** 3.0 (Consolidated — supersedes 04_PIPELINE_MAP_v2_1.md)

**Corrections applied:**
- [COR-2] SYS_RUNTIME is computational only. UI rendering separated as SYS_PRESENTATION (4th system).
- [COR-3] EX-P1 corrected: 9 agents + ConceptEngine = 10 subsystems (was listed as 6).
- [COR-7] COMPILE-INT/COMPILE-MOD formalized as Offline Compilation Layer.
- [COR-8] Diagram labels corrected to match pipeline stage definitions.
- Added EX-P6 (Deployment Validation).

**Companion documents:**
- `02_MACRO_OVERVIEW_OF_SYSTEMS.md` — System decomposition and chain inventory
- `04_TABLE_REGISTRY.md` — Table identity cards
- `06_FK_WIRING_MAP.md` — Foreign key graph

---

## 1. System Architecture: Four Pipeline Systems

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                         SYS_EXTRACTION  (offline, per paper)                         │
│  EX-P0 → EX-P1 → TB → EX-P2 → [EX-P2E] → EX-P3 → EX-P4 → EX-P4B → EX-P5 → EX-P6│
│  Triage  Extract  Trust Harmonize  Ext     7-Layer  Agg     PubBias  Coher.  Deploy │
│                                            Heterog.                  +Chain          │
│                                                                      vsDirect       │
└────────────────────────────┬─────────────────────────────────────────────────────────┘
                             │ writes Class B+C tables
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              OFFLINE COMPILATION LAYER  (offline, after authoring)          │
│  COMPILE-INT: intervention ontology → action_catalog + dose_bridges        │
│  COMPILE-MOD: modifier sources → baseline_modifier_definitions             │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │ writes Class A/C tables
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYS_ALGORITHM  (runtime, per session)                    │
│  ALG-A → ALG-B → ALG-C → ALG-D → ALG-E → ALG-F                           │
│  Intake  Triang  BayesEst Scenario Modifier Simulate                       │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │ produces in-memory state + writes Class E
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYS_RUNTIME  (runtime, per session)                      │
│  Stage G → Stage H → Stage I                                               │
│  Optimize  Questions  Report                                               │
│  [computational decision pipeline — no UI rendering]                       │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │ writes Class E tables, produces RecommendationReport
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYS_PRESENTATION  (read-only rendering)                  │
│  Patient Interface │ Science Interface │ Admin Interface                    │
│  [renders from Class E tables + RecommendationReport]                      │
│  [writes nothing — pure read]                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. SYS_EXTRACTION Pipeline (Evidence Processing)

### EX-P0: Triage

| Property | Value |
|----------|-------|
| **Input** | Raw PDF/text of candidate paper |
| **Tables Read** | `study_registry_v1` (dedup check) |
| **Tables Written** | `study_registry_v1` (new entry), `extraction_audit_v1` (P0 record) |
| **In-Memory Output** | TriageDecision {accept/reject, confidence, reason} |
| **Key Logic** | DOI + content hash dedup; relevance scoring against CRCI domain |

### EX-P1: Multi-Agent Extraction [COR-3 CORRECTED]

| Property | Value |
|----------|-------|
| **Input** | Accepted paper from EX-P0 |
| **Tables Read** | `biomarker_node_definitions_v1`, `instrument_definitions_v1`, `measure_definitions_v1`, `edge_relations_definitions_v1` |
| **Tables Written** | `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1`, `extraction_audit_v1` |
| **In-Memory Output** | SpanLabel[] (raw extracted claims with text spans and confidence scores) |
| **Subsystems (10)** | MetadataAgent (AG1), DesignAgent (AG2), CohortAgent (AG3), OutcomeAgent (AG4), StatsLabelAgent (AG5), ExposureAgent (AG6), MediatorAgent (AG7), TemporalAgent (AG8), ReconciliationAgent (AG9), ConceptEngine (CE) |
| **Key Logic** | §2.5: 9 specialized LLM agents + 1 ConceptEngine extract structured claims from paper text. Agents 1–9 operate sequentially with accumulating `prior_outputs` context. ConceptEngine provides ontology grounding. |

### EX-TB: Trust Boundary (Deterministic Parser)

| Property | Value |
|----------|-------|
| **Input** | SpanLabel[] from EX-P1 |
| **Tables Read** | `edge_relations_definitions_v1` (validates edge_relation_id), `instrument_definitions_v1`, `measure_definitions_v1` |
| **Tables Written** | None (in-memory validation gate) |
| **In-Memory Output** | ParsedNumeric[] (validated, deterministically parsed numeric claims) |
| **Subsystems (2)** | NumericParser (COMPOSITE — 11 sub-parsers NP-01 through NP-11), ClaimNormalizer |
| **Key Logic** | §2.5.4: No LLM touches numbers. Deterministic regex parser + range validation. GATE: rejects claims that fail parse. Absolute boundary between LLM-generated content (SpanLabel[]) and numeric data entering Bayesian model (ParsedNumeric[]). |

### EX-P2: Harmonization

| Property | Value |
|----------|-------|
| **Input** | ParsedNumeric[] from TB |
| **Tables Read** | `harmonization_rules_v1`, `edge_ontology_v1` (CG4 gate), `normalization_refs_v1`, `observation_noise_v1` |
| **Tables Written** | `edge_evidence_v1` (core evidence rows), `extraction_audit_v1` |
| **In-Memory Output** | HarmonizedEvidence[] (SMD-scale effect sizes with seven-layer SE) |
| **Subsystems (7)** | S1: EffectClassifier, S2: UnitStandardizer, S3: ScaleHarmonizer, S4: TemporalAligner, S5: QualityScorer, S6: SEComputer, S7: EvidenceAssembler |
| **Conversion Gates (4)** | CG1: EffectTypeGate, CG2: ScaleCompatibilityGate, CG3: TemporalCompatibilityGate, CG4: OntologyGate |
| **Key Logic** | §2.9: Seven-layer heterogeneity SE pipeline. Converts OR→SMD, r→d, HR→OR. Applies scale alignment, temporal alignment, cancer-validation multipliers. |

### EX-P2E: Extended Extraction (Conditional)

| Property | Value |
|----------|-------|
| **Input** | Same paper, flagged for extended extraction |
| **Tables Read** | `triangulation_sets_v1`, `pathways_v1` |
| **Tables Written** | `triangulation_evidence_v1`, `pathway_biomarkers_v1`, `ontology_links_v1` |
| **In-Memory Output** | None (all outputs persisted) |
| **Key Logic** | Extracts cross-method agreement, biomarker-pathway loadings, and ontology provenance when papers report these |

### EX-P3: Assimilation (Seven-Layer Heterogeneity Pipeline)

| Property | Value |
|----------|-------|
| **Input** | HarmonizedEvidence[] from EX-P2 |
| **Tables Read** | `study_registry_v1`, `predictor_alignment_rules_v1`, `study_cohort_profiles_v1`, `normalization_refs_v1`, `quality_assessment_v1` |
| **Tables Written** | `edge_evidence_v1` (se_eff, scope_weight, layer_multipliers_json) |
| **In-Memory Output** | CalibratedEvidence[] (7-layer SE_eff calibrated) |
| **Key Logic** | §2.9: Full seven-layer heterogeneity pipeline. L1 Design → L2 Population → L3 Statistical → L4 Measurement → L5 Quality → L6 Temporal → L7 Freshness. Variance compounding: SE_eff = SE_pooled × Π m_i (9 subsystems). |

### EX-P4: Aggregation (Edge Compilation)

| Property | Value |
|----------|-------|
| **Input** | All evidence in `edge_evidence_v1` for target edges |
| **Tables Read** | `edge_evidence_v1`, `edge_relations_definitions_v1`, `literary_mechanistic_priors_v1`, `literary_constraints_v1` |
| **Tables Written** | `edges_v1` (compiled parameters), `node_priors_v1`, `edge_param_builds_v1` (audit) |
| **In-Memory Output** | CompiledEdgeSet (full B matrix specification) |
| **Key Logic** | §2.10: Random-effects meta-analysis (DerSimonian-Laird) with prior selection framework. Produces pooled β̂, SE, grade, P(include). Deterministic compiler decision tree — no LLM involvement. |

### EX-P4B: Publication Bias Assessment — NEW

| Property | Value |
|----------|-------|
| **Input** | CompiledEdgeSet from EX-P4 + per-study evidence from edge_evidence_v1 |
| **Tables Read** | `edges_v1`, `edge_evidence_v1` |
| **Tables Written** | `edges_v1` (pub_bias_risk, se_inflation_pub_bias), `publication_bias_results_v1` |
| **In-Memory Output** | BiasAssessment {egger, trim-fill, LOO, risk, SE inflation} per edge |
| **Key Logic** | §2.12.1: For edges with k≥10, runs Egger regression, trim-and-fill, leave-one-out. Classifies bias risk (LOW/MODERATE/HIGH/INSUFFICIENT_K). Applies SE inflation [1.0–1.5] to edges_v1. |

### EX-P5: Sufficiency & Coherence Check — EXPANDED

| Property | Value |
|----------|-------|
| **Input** | CompiledEdgeSet from EX-P4/P4B + pathway definitions |
| **Tables Read** | `edges_v1`, `edge_relations_definitions_v1`, `pathways_v1`, `edge_evidence_v1` (direct RCT rows) |
| **Tables Written** | `edges_v1` (coherence_flag, se_inflation_coherence, e_value, robustness_value), `chain_validation_results_v1`, `extraction_audit_v1` |
| **In-Memory Output** | SufficiencyReport + CDResults + ClassifiedResults + EValueResults |
| **Key Logic** | §2.13: (1) Coverage analysis (k≥3, grade≥C). (2) Chain product computation (β_chain = Π β_e per pathway). (3) Chain-vs-direct Z-test with 4-tier triage (PASS/MONITOR/INVESTIGATE/ALARM). (4) 6-mode discrepancy classification. (5) SE inflation feedback [1.0–2.0]. (6) E-value computation (§2.22). 7 subsystems. |

### EX-P6: Deployment Validation [COR-7 CLARIFIED]

| Property | Value |
|----------|-------|
| **Input** | Complete compiled edge set + all Class A/B/C tables |
| **Tables Read** | `edges_v1`, `validation_rules_v1`, all Class A tables |
| **Tables Written** | `extraction_audit_v1` (deployment validation record) |
| **In-Memory Output** | ValidationReport {pass/fail, violations[], coverage_matrix} |
| **Key Logic** | Final gate before compiled parameters are deployed to SYS_ALGORITHM. Runs validation_rules_v1 (G1–G16+). Distinct from EX-P4 aggregation and from COMPILE-INT/COMPILE-MOD (which are offline compilation, not validation). |

---

## 3. Offline Compilation Layer [COR-7 FORMALIZED]

These offline processes compile detailed Class A source tables into runtime-optimized tables. They run after knowledge authoring, not per-paper.

### COMPILE-INT: Intervention Compilation

| Property | Value |
|----------|-------|
| **Input** | Extended intervention ontology (7 codebase tables) |
| **Tables Read** | `intervention_definitions_v1`, `intervention_mapping_v1`, `intervention_protocols_v1`, `protocol_effects_v1`, `dose_response_functions_v1`, `dose_translations_v1`, `interaction_effects_v1` |
| **Tables Written** | `action_catalog_v1`, `dose_bridges_v1` |
| **Key Logic** | Flattens normalized intervention ontology into runtime-optimized tables. See `07_CODEBASE_ALIGNMENT.md` §4.2.1 for source→target mapping. |

### COMPILE-MOD: Modifier Stack Compilation

| Property | Value |
|----------|-------|
| **Input** | Extended modifier sources (5 codebase tables) |
| **Tables Read** | `effect_modifiers_v2`, `edge_modifier_params_v1`, `chemo_agent_modifiers_v1`, `modifier_activation_rules_v1`, `compliance_modifiers_v1` |
| **Tables Written** | `baseline_modifier_definitions_v1` |
| **Key Logic** | Normalizes heterogeneous modifier sources into unified modifier format with standardized modifier_function_type ENUM. See `07_CODEBASE_ALIGNMENT.md` §4.2.3. |

---

## 3B. Offline Validation Layer — NEW

These analyses run offline against the full compiled model. They test structural stability and are not part of the per-paper or per-session pipeline.

### VAL-01: Complexity-Scaling Validation

| Property | Value |
|----------|-------|
| **Input** | Full compiled model (edges_v1 + pathways_v1 + all parameters) |
| **Tables Read** | `edges_v1`, `pathways_v1`, all Class A/C tables |
| **Tables Written** | `complexity_scaling_results_v1` |
| **In-Memory Output** | StabilityReport {flip_rates, fragile_edges, mean_beta_shifts} per 12 configs |
| **Key Logic** | §2.13.1: Generates 4×3 degraded model configurations (horizontal: edge removal by grade; vertical: heterogeneity layer simplification). Runs full MC engine (10K draws) per config. Measures ranking stability (flip rate vs full model). Identifies fragile structural edges. |

---

## 4. SYS_ALGORITHM Pipeline (Per-Session Inference)

### Stage A (ALG-A): Intake Standardization

| Property | Value |
|----------|-------|
| **Input** | Raw patient data (questionnaire + biomarkers + wearables) |
| **Tables Read** | `biomarker_node_definitions_v1`, `instrument_definitions_v1`, `measure_definitions_v1`, `derived_feature_definitions_v1`, `normalization_refs_v1`, `observation_noise_v1` |
| **Tables Written** | `state_snapshots_v1` (initial raw state) |
| **In-Memory Output** | StandardizedFeatureVector (z-scored, validated, 63-dimensional) |
| **Key Logic** | §2.7: Z-score normalization, cancer-validation SE multipliers, proxy validity tagging |

### Stage B (ALG-B): Triangulation

| Property | Value |
|----------|-------|
| **Input** | StandardizedFeatureVector from Stage A |
| **Tables Read** | `triangulation_sets_v1`, `triangulation_members_v1`, `triangulation_evidence_v1` (optional), `observation_noise_v1` |
| **Tables Written** | `state_snapshots_v1` (fused state update) |
| **In-Memory Output** | FusedStateVector (within-construct fused, conflict-flagged) |
| **Key Logic** | §2.8: Within-construct fusion, precision-weighted averaging, conflict quantification (Cochran's Q analog) |

### Stage C (ALG-C): Bayesian State Estimation

| Property | Value |
|----------|-------|
| **Input** | FusedStateVector from Stage B |
| **Tables Read** | `node_priors_v1`, `observation_noise_v1`, `state_estimator_specs_v1`, `biomarker_node_definitions_v1`, `biomarker_correlations_v1` |
| **Tables Written** | `state_snapshots_v1` (posterior state) |
| **In-Memory Output** | PosteriorState (η, Λ information-form Gaussian) |
| **Key Logic** | §2.8: Information-form Gaussian update, temporal decay (α=0.05/day), context-matched prior fallback hierarchy |
| **Re-entrant** | Stage H loops back to Stage C after each patient answer — state_snapshots_v1 accumulates successive posteriors |

### Stage D (ALG-D): Scenario Construction

| Property | Value |
|----------|-------|
| **Input** | PosteriorState from Stage C |
| **Tables Read** | `action_catalog_v1`, `contraindication_rules_v1`, `status_quo_rules_v1`, `action_contraindication_links_v1`, `safety_policies_v1` |
| **Tables Written** | `scenario_definitions_v1`, `scenario_items_v1`, `contraindication_eval_trace_v1` |
| **In-Memory Output** | CandidateScenarios[] (safety-filtered action bundles) |
| **Key Logic** | §2.14: Candidate generation, safety filtering, status quo baseline construction |

### Stage E (ALG-E): Personalization (Modifier Resolution)

| Property | Value |
|----------|-------|
| **Input** | PosteriorState + CandidateScenarios from Stage D |
| **Tables Read** | `edges_v1`, `variable_definitions_v1`, `variable_to_input_map_v1`, `baseline_modifier_definitions_v1`, `derived_feature_definitions_v1` |
| **Tables Written** | `modifier_eval_trace_v1` |
| **In-Memory Output** | PersonalizedBMatrix (patient-specific edge parameter matrix with modifier-adjusted β̂, SE per edge) |
| **Key Logic** | §2.15: 109-rule modifier stack, multiplicative adjustment with [0.5, 2.0] guardrails, grade-based SE inflation |

### Stage F (ALG-F): Forward Simulation (Monte Carlo)

| Property | Value |
|----------|-------|
| **Input** | PersonalizedBMatrix + CandidateScenarios from Stage E |
| **Tables Read** | `dose_bridges_v1`, `edges_v1`, `edge_relations_definitions_v1`, `literary_mechanistic_priors_v1`, `literary_constraints_v1`, `intervention_kernels_v1`, `recovery_trajectories_v1`, `feedback_loops_v1`, `intervention_synergy_v1`, `node_priors_v1`, `observation_noise_v1` |
| **Tables Written** | `simulation_trace_v1` |
| **In-Memory Output** | SimulationResults {per_scenario: {mean_trajectory[], CI_trajectory[], Δz_distribution[]}} |
| **Key Logic** | §2.11–2.12, §2.18: 10,000-draw MC simulation with temporal kernels (onset/build/steady-state/decay from `intervention_kernels_v1`), dose-response bridges (Emax/Hill from `dose_bridges_v1`), synergy coefficients (γ from `intervention_synergy_v1`), constraint enforcement (from `literary_constraints_v1`), recovery trajectories (r∞, τR, γR from `recovery_trajectories_v1`), feedback loop dynamics (from `feedback_loops_v1`). Each draw samples from posterior + noise distributions. |

---

## 5. SYS_RUNTIME Pipeline (Decision & Reporting) [COR-2: Computational Only]

### Stage G: Schedule Optimization

| Property | Value |
|----------|-------|
| **Input** | SimulationResults from Stage F |
| **Tables Read** | `action_catalog_v1`, `contraindication_rules_v1`, `objective_specs_v1`, `intervention_synergy_v1` |
| **Tables Written** | `schedule_plans_v1`, `schedule_items_v1`, `decision_trace_v1` |
| **In-Memory Output** | RankedSchedules[] (SAFE-scored, stability-classified) |
| **Key Logic** | §2.16: SAFE score computation (Mode A: E[Δz]/uncertainty; Mode B: SAFE·burden·adherence), synergy-aware bundle scoring, rank stability classification (stable/soft/unstable via bootstrap resampling) |

### Stage H: Adaptive Questioning

| Property | Value |
|----------|-------|
| **Input** | Current PosteriorState + partial answers |
| **Tables Read** | `question_bank_v1`, `voi_rules_v1`, `triangulation_sets_v1`, `derived_feature_definitions_v1`, `question_observation_models_v1` |
| **Tables Written** | `question_sequence_v1`, `question_selection_trace_v1`, `state_snapshots_v1` (updated after each answer) |
| **In-Memory Output** | NextQuestion {question_id, expected_voi, stopping_decision} |
| **Key Logic** | §2.19: VOI-based question selection, expected posterior variance reduction, stopping when marginal VOI < threshold |
| **Loop** | Each answer triggers: Stage C re-entry (Bayesian update) → new VOI computation → next question selection. Typically 15–30 questions before stopping criterion met. |

### Stage I: Reporting & Provenance

| Property | Value |
|----------|-------|
| **Input** | RankedSchedules from Stage G + full session state |
| **Tables Read** | `outcome_anchors_v1`, `ontology_links_v1`, `edges_v1`, `edge_evidence_v1`, `description_templates_v1` |
| **Tables Written** | `recommendation_runs_v1` (final run record), `decision_trace_v1` (provenance) |
| **In-Memory Output** | RecommendationReport (TYPE 3: structured interface contract for SYS_PRESENTATION) |
| **Key Logic** | §2.20, §4.5: Six-tier severity mapping (z→Excellent/Good/Mild Concern/Moderate/Poor/Severe), evidence provenance chains (recommendation→schedule→scenario→simulation→edges→evidence→study), decision-critical edge identification (top 3 by flip influence), five-source variance decomposition (literature heterogeneity, measurement noise, structural model, proxy imprecision, missing observations), discovery score per edge (|elasticity|×SE_eff) |
| **Output Modes** | Clinical (per-patient recommendations), Population analytics (archetype analysis), Research analytics (evidence gaps + EVSI) |

---

## 6. SYS_PRESENTATION (Read-Only Rendering) [COR-2 NEW]

| Property | Value |
|----------|-------|
| **Input** | RecommendationReport from Stage I (TYPE 3 interface contract) |
| **Tables Read** | All Class E tables via `recommendation_runs_v1` FK chain, plus: `description_templates_v1` (A), `outcome_anchors_v1` (C), `action_catalog_v1` (A), `question_bank_v1` (A) |
| **Tables Written** | **None** — SYS_PRESENTATION is pure read |
| **Branches** | Patient Interface, Science Interface, Admin Interface |
| **Components** | ~15 visualization components (deferred to `10_UI_INTERFACE_SPEC.md`) |
| **Key Constraint** | No computation, inference, or data transformation occurs here. All logic lives in SYS_ALGORITHM + SYS_RUNTIME. Presentation only renders. |

---

## 7. Cross-Pipeline Data Flow Summary

### By Lifecycle Class

```
CLASS A (Knowledge, 32)   ──read by──→  ALL PIPELINES (bootstrap, immutable at runtime)
CLASS B (Evidence, 9)     ──written by→  SYS_EXTRACTION (EX-P1 through EX-P4)
                          ──read by──→  SYS_EXTRACTION (later stages), SYS_ALGORITHM (ALG-F)
CLASS C (Compiled, 5)     ──written by→  SYS_EXTRACTION (EX-P4), COMPILE-INT
                          ──read by──→  SYS_ALGORITHM (ALG-C,E,F), SYS_RUNTIME (Stage I)
CLASS D (Policy, 5)       ──read by──→  SYS_RUNTIME (Stages G,H), SYS_ALGORITHM (ALG-D)
CLASS E (Output, 13)      ──written by→  SYS_ALGORITHM (ALG-A through ALG-F), SYS_RUNTIME (Stages G,H,I)
                          ──read by──→  SYS_PRESENTATION (all branches)
```

### Data Handoff Points

| Handoff | From | To | Data Type | Classification |
|---------|------|----|-----------|----------------|
| Paper → Extraction | External | EX-P0 | Raw PDF/text | TYPE 3: Interface Contract |
| EX-P0 → EX-P1 | EX-P0 | EX-P1 | TriageDecision | TYPE 2: In-Memory |
| EX-P1 → TB | EX-P1 | EX-TB | SpanLabel[] | TYPE 2: In-Memory (TRUST BOUNDARY) |
| TB → EX-P2 | EX-TB | EX-P2 | ParsedNumeric[] | TYPE 2: In-Memory |
| EX-P2 → EX-P3 | EX-P2 | EX-P3 | HarmonizedEvidence[] | TYPE 2: In-Memory |
| Extraction → Algorithm | SYS_EXTRACTION | SYS_ALGORITHM | Class B+C tables | TYPE 1: Persisted |
| ALG-A → ALG-B → ALG-C | Sequential | Sequential | Feature/State vectors | TYPE 2: In-Memory |
| ALG-D → ALG-E → ALG-F | Sequential | Sequential | Scenarios + B matrix | TYPE 2: In-Memory |
| Algorithm → Runtime | ALG-F | Stage G | SimulationResults | TYPE 2: In-Memory |
| Stage H → Stage C | Stage H | ALG-C | Patient answer | TYPE 2: In-Memory (re-entrant loop) |
| Runtime → Presentation | Stage I | SYS_PRESENTATION | RecommendationReport | TYPE 3: Interface Contract |

### Table Read/Write Frequency (Top 10 Most Connected)

| Table | Read By (stages) | Written By (stages) | Total Connections |
|-------|-------------------|---------------------|-------------------|
| `biomarker_node_definitions_v1` | 18 | 0 | 18 |
| `edges_v1` | 8 | 1 (EX-P4) | 9 |
| `state_snapshots_v1` | 4 | 5 (ALG-A,B,C + Stage H + re-entries) | 9 |
| `edge_evidence_v1` | 5 | 1 (EX-P2) | 6 |
| `observation_noise_v1` | 5 | 0 | 5 |
| `action_catalog_v1` | 5 | 0 (or COMPILE-INT) | 5 |
| `derived_feature_definitions_v1` | 5 | 0 | 5 |
| `normalization_refs_v1` | 4 | 0 | 4 |
| `contraindication_rules_v1` | 3 | 0 | 3 |
| `recommendation_runs_v1` | 0 direct | 2 (Stage I primary) | 2 writes + 12 FK consumers |

---

## 8. Fill Order (Bootstrap → Runtime)

Tables must be populated in this order to satisfy FK constraints. See `06_FK_WIRING_MAP.md` for complete FK graph.

| Order | Phase | Tables | Gate |
|-------|-------|--------|------|
| **0** | Bootstrap Core | `biomarker_node_definitions_v1` (ROOT), `contraindication_escalation_policy_v1`, `harmonization_rules_v1`, `description_templates_v1`, `action_catalog_v1`, `state_estimator_specs_v1` | ROOT tables — no FK dependencies |
| **0.5** | Bootstrap Dedup | `study_registry_v1` (dedup gate) | Needed before any paper processing |
| **1** | Bootstrap Tier 1 | `edge_relations_definitions_v1`, `normalization_refs_v1`, `observation_noise_v1`, `pathways_v1`, `recovery_trajectories_v1`, `biomarker_correlations_v1` | FK → Order 0 tables |
| **2** | Bootstrap Tier 2 | `edge_ontology_v1`, `instrument_definitions_v1`, `measure_definitions_v1`, `derived_feature_definitions_v1`, `contraindication_rules_v1`, `variable_definitions_v1`, `triangulation_sets_v1`, `question_observation_models_v1`, `pathway_interactions_v1`, `feedback_loops_v1`, `intervention_kernels_v1` | FK → Order 0–1 tables |
| **3** | Bootstrap Tier 3 | `literary_mechanistic_priors_v1`, `literary_constraints_v1`, `predictor_alignment_rules_v1`, `baseline_modifier_definitions_v1`, `triangulation_members_v1`, `variable_to_input_map_v1`, `action_contraindication_links_v1`, `question_bank_v1`, `intervention_synergy_v1`, `pathway_biomarkers_v1` | FK → Order 0–2 tables |
| **4** | Bootstrap Config | `validation_rules_v1`, `objective_specs_v1`, `safety_policies_v1`, `escalation_policies_v1`, `status_quo_rules_v1`, `voi_rules_v1`, `outcome_anchors_v1`, `node_priors_v1` (initial) | FK → Order 0–3 tables. Policy tables are Class D. |
| **5** | Evidence Tier 1 | `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1`, `ontology_links_v1`, `extraction_audit_v1` | Per-paper. FK → study_registry_v1 |
| **6** | Evidence Tier 2 | `edge_evidence_v1`, `triangulation_evidence_v1` | Per-paper. FK → Order 5 + Class A tables |
| **7** | Compilation | `edges_v1` (recomputed), `dose_bridges_v1` (COMPILE-INT), `node_priors_v1` (recomputed), `edge_param_builds_v1` (audit) | After evidence accumulation. Triggers EX-P4 + COMPILE-INT. |
| **9** | Runtime (per session) | ALL 13 Class E tables | Per-session. FK → Order 0–7 tables + `recommendation_runs_v1` (internal FK hub) |

---

## 9. Codebase Pipeline Extensions

### 9.1 Extraction Pipeline: Granular Audit Tables

The spec's `extraction_audit_v1` (E13) provides summary-level per-stage audit. The codebase maintains granular stage-specific tables that should be retained alongside:

| Spec Stage | Codebase Granular Table | What It Adds Beyond E13 |
|-----------|------------------------|------------------------|
| EX-P0 | `search_strategy_v1` | Full PRISMA search strategy documentation |
| EX-P0 | `prisma_screening_log_v1` | Individual screening decisions (include/exclude/maybe) |
| EX-P0 | `triage_records_v1` | Per-paper triage rationale and relevance scores |
| EX-P1 | `acquisition_queue_v1` | Download/retrieval tracking (operational) |
| EX-P2 | `conversion_appropriateness_log_v1` | Per-conversion harmonization decisions |
| EX-P2 | `consistency_report_v1` | Cross-extraction consistency checks |
| EX-P3 | `assimilation_log_v1` | Per-evidence-row assimilation decisions |
| EX-P4 | `aggregation_log_v1` | Per-edge compilation decisions |
| EX-P5 | `evidence_sufficiency_v1` | Sufficiency check results (gap analysis) |

**Recommendation:** `extraction_audit_v1` aggregates FROM these tables. Keep both: granular for debugging, summary for reporting. See `07_CODEBASE_ALIGNMENT.md` §4.2.2.

### 9.2 Intervention & Modifier Compilation Sources

These codebase tables are the Class A sources consumed by the Offline Compilation Layer (§3):

| Pipeline | Source Tables (Codebase) | Compiled Target (Spec) |
|----------|------------------------|----------------------|
| COMPILE-INT | `intervention_definitions_v1`, `intervention_mapping_v1`, `intervention_protocols_v1`, `protocol_effects_v1`, `dose_response_functions_v1`, `dose_translations_v1`, `interaction_effects_v1` | `action_catalog_v1`, `dose_bridges_v1` |
| COMPILE-MOD | `effect_modifiers_v2`, `edge_modifier_params_v1`, `chemo_agent_modifiers_v1`, `modifier_activation_rules_v1`, `compliance_modifiers_v1` | `baseline_modifier_definitions_v1` |

See `07_CODEBASE_ALIGNMENT.md` §4.2.1 and §4.2.3 for detailed source→target column mapping.

---

## 10. Pipeline Execution Timing Summary

| Execution Context | Systems Active | Frequency | Duration |
|-------------------|---------------|-----------|----------|
| **Paper extraction** | SYS_EXTRACTION (EX-P0 → EX-P6) | Per paper (~446+ papers in evidence base) | Minutes per paper (LLM-bound) |
| **Knowledge authoring** | Manual → Class A tables | Infrequent (domain expert sessions) | Hours–days |
| **Compilation** | COMPILE-INT, COMPILE-MOD, EX-P4 recompile | After authoring changes | Seconds–minutes (deterministic) |
| **Patient session** | SYS_ALGORITHM → SYS_RUNTIME → SYS_PRESENTATION | Per patient encounter | Seconds (inference-bound at ALG-F MC simulation) |
| **Adaptive loop** | Stage H → ALG-C → Stage H (repeated) | Per question within session | Sub-second per loop iteration |

---

*End of Pipeline Execution Map v3.0*
