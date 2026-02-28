# CRCI Table Inventory Audit

**Generated:** 2026-02-27  
**Scope:** All tables documented in 05_TABLE_SCHEMAS.md, SQL schemas (001–013), ORM models (tables.py), and code references across extraction + algorithm chains.

---

## 1. Complete Table Inventory by Class

### Class A — Knowledge (33 tables in doc, 33 in SQL)

| # | Table Name | Purpose |
|---|-----------|---------|
| A1 | `edge_relations_definitions_v1` | Defines every permitted causal edge (source→target→mechanism) in the DAG |
| A2 | `edge_ontology_v1` | Operational constraints per edge type — conversions, functional forms, sign conventions |
| A3 | `biomarker_node_definitions_v1` | ROOT table: every node (biomarker, construct, cognitive domain) in the 63-node DAG |
| A4 | `instrument_definitions_v1` | Clinical assessment instruments (PSQI, FACT-Cog, MoCA) with psychometric properties |
| A5 | `measure_definitions_v1` | Biomarker/wearable/proxy measurement types with assay specs and node mappings |
| A6 | `harmonization_rules_v1` | Deterministic conversion formulas: OR→SMD, r→d, HR→OR, etc. |
| A7 | `predictor_alignment_rules_v1` | Alignment rules for study cohort→target population transportability |
| A8 | `literary_mechanistic_priors_v1` | Literature-informed prior distributions for sparse-evidence edges |
| A9 | `literary_constraints_v1` | Biological bounds on node trajectories (ceilings, rate limits, floors) |
| A10 | `contraindication_rules_v1` | Safety rules: trigger predicates → block/modify/escalate actions |
| A11 | `action_contraindication_links_v1` | Join table: action ↔ safety rule linkage |
| A12 | `contraindication_escalation_policy_v1` | Escalation behaviors when contraindication fires |
| A13 | `validation_rules_v1` | Cross-table FK integrity, range, and consistency checks |
| A14 | `variable_definitions_v1` | Patient variables that modify edge parameters (109-rule modifier stack) |
| A15 | `variable_to_input_map_v1` | Maps patient intake form fields to engine variables |
| A16 | `baseline_modifier_definitions_v1` | How patient variables multiplicatively adjust edge parameters |
| A17 | `derived_feature_definitions_v1` | Computed features: formulas, dependency chains, normalization |
| A18 | `triangulation_sets_v1` | Which measurements to fuse per latent construct (Stage B config) |
| A19 | `triangulation_members_v1` | Membership list + weights for multi-signal fusion |
| A20 | `description_templates_v1` | Text templates for UI rendering of recommendations/warnings |
| A21 | `action_catalog_v1` | Atomic interventions: dose domains, burden/adherence priors |
| A22 | `question_bank_v1` | Adaptive intake questions with VOI parameters |
| A23 | `question_observation_models_v1` | Maps question answers → node/feature updates |
| A24 | `normalization_refs_v1` | Population reference stats (mean, SD) for z-score normalization |
| A25 | `observation_noise_v1` | Measurement noise/reliability parameters for all entities |
| A26 | `pathways_v1` | 15 mechanistic + 5 clinical mediator pathways |
| A27 | `pathway_interactions_v1` | Interactions between pathway pairs (feed-forward, convergent, antagonistic) |
| A28 | `intervention_synergy_v1` | Pairwise intervention interaction records (JPO, CCS, γ priors) |
| A29 | `recovery_trajectories_v1` | Natural recovery parameters per treatment context (stretched exponential) |
| A30 | `biomarker_correlations_v1` | Correlated mediator pairs with ρ for block-diagonal D matrix |
| A31 | `feedback_loops_v1` | 5 feedback structures in the DAG (loop gain, period, stability) |
| A32 | `intervention_kernels_v1` | Per-intervention temporal kernels (onset, build, steady-state, decay) |
| A33 | `mid_thresholds_v1` | Minimally Important Difference thresholds per cognitive domain |

### Class B — Evidence (16 tables in SQL; 9 in 05_TABLE_SCHEMAS doc)

| # | Table Name | Purpose | In Schema Doc | In SQL |
|---|-----------|---------|:---:|:---:|
| B1 | `study_registry_v1` | Dedup gate + canonical record for every paper | ✅ | ✅ |
| B2 | `study_cohort_profiles_v1` | Cohort-level metadata: demographics, cancer type, treatment phase | ✅ | ✅ |
| B3 | `profile_data_streams_v1` | What was measured in each cohort (instruments × measures) | ✅ | ✅ |
| B4 | `stream_timepoints_v1` | Measurement timepoints within each data stream | ✅ | ✅ |
| B5 | `ontology_links_v1` | Provenance links: ontology entity → supporting paper | ✅ | ✅ |
| B6 | `edge_evidence_v1` | Central evidence table: every extracted effect estimate (71 cols) | ✅ | ✅ |
| B7 | `edge_param_builds_v1` | Aggregation audit trail: evidence → compiled edge params | ✅ | ✅ |
| B8 | `triangulation_evidence_v1` | Cross-method agreement results from papers | ✅ | ✅ |
| B9 | `pathway_biomarkers_v1` | Links biomarkers to pathways with evidence | ✅ | ✅ |
| B10 | `instrument_evidence_v1` | Psychometric evidence for instruments | ❌ | ✅ |
| B11 | `population_norms_v1` | Population normative data for z-score references | ❌ | ✅ |
| B12 | `temporal_evidence_v1` | Temporal effect patterns (onset, decay, recovery) | ❌ | ✅ |
| B13 | `dose_evidence_v1` | Dose-response data for interventions | ❌ | ✅ |
| B14 | `subgroup_evidence_v1` | Subgroup/modifier evidence for effect heterogeneity | ❌ | ✅ |
| B15 | `extraction_audit_v1` | Pipeline QA: stage execution records per paper | ✅ (as E13) | ✅ |
| B16 | `acquisition_queue_v1` | Paper retrieval queue | ❌ | ✅ |

### Class C — Compiled (7 tables)

| # | Table Name | Purpose |
|---|-----------|---------|
| C1 | `edges_v1` | **KEY TABLE**: compiled edge parameters (pooled β, SE, grade, inclusion prob) |
| C2 | `dose_bridges_v1` | Dose-to-effect bridge mappings (Emax/Hill → z-score effects) |
| C3 | `node_priors_v1` | Scoped prior distributions per node (cancer type × treatment phase) |
| C4 | `outcome_anchors_v1` | Calibration anchors: z-scores → clinically interpretable scales |
| C5 | `state_estimator_specs_v1` | Configuration for Bayesian state estimation engine |
| C6 | `chain_validation_results_v1` | Chain-vs-direct validation results per testable pathway |
| C7 | `publication_bias_results_v1` | Publication bias assessment results per edge |

### Class D — Policy (7 tables)

| # | Table Name | Purpose |
|---|-----------|---------|
| D1 | `objective_specs_v1` | Utility function specs for SAFE score computation |
| D2 | `safety_policies_v1` | System-level safety policies (trigger → behavior) |
| D3 | `escalation_policies_v1` | Escalation protocols for clinician handoff |
| D4 | `status_quo_rules_v1` | Baseline dose assumptions for counterfactual 'no change' scenario |
| D5 | `voi_rules_v1` | Value-of-information policy for adaptive question selection |
| D6 | `complexity_scaling_results_v1` | Complexity-scaling validation results (offline analysis) |
| D7 | `population_archetypes_v1` | Population archetype definitions (GMM clusters) |

### Class E — Output (12 tables)

| # | Table Name | Purpose |
|---|-----------|---------|
| E1 | `state_snapshots_v1` | Bayesian state estimates (μ, Σ) after each observation update |
| E2 | `scenario_definitions_v1` | What-if scenario configurations |
| E3 | `scenario_items_v1` | Actions within each scenario |
| E4 | `schedule_plans_v1` | Optimized schedule plans ranked by SAFE score |
| E5 | `schedule_items_v1` | Scheduled actions with optimized doses and timing |
| E6 | `recommendation_runs_v1` | Run header: one row per engine execution session |
| E7 | `simulation_trace_v1` | MC simulation trace records |
| E8 | `decision_trace_v1` | Decision audit trail with SAFE scores |
| E9 | `contraindication_eval_trace_v1` | Safety evaluation audit trail |
| E10 | `question_selection_trace_v1` | VOI-based question selection audit |
| E11 | `modifier_eval_trace_v1` | Personalization audit trail |
| E12 | `question_sequence_v1` | Adaptive intake record: questions asked/answered |

### Operational Tables (not classified A-E; from schemas 007-013)

| Table Name | Schema File | Purpose |
|-----------|-------------|---------|
| `review_tasks` | 007 | Cross-cutting task queue for human review |
| `policy_snapshots` | 007 | Versioned policy configuration snapshots |
| `build_manifests_v1` | 007 | Build provenance records |
| `extraction_runs` | 007 | Per-paper extraction run tracking |
| `study_annotations_v1` | 008 | Validated canonical annotations from papers |
| `study_annotations_raw_v1` | 008 | Raw annotation emissions (audit) |
| `edge_evidence_quarantine_v1` | 009 | QA-rejected evidence records |
| `extraction_completeness_v1` | 010 | Per-paper extraction completeness metrics |
| `evidence_validation_quarantine_v1` | 012 | Validation-failed evidence rows |
| `node_search_terms_v1` | 001 (tail) | Search terms for node mapping |

---

## 2. Extraction Agent "Writes To" Claims vs Actual DB Writes

### P1 Extraction Agents (AG01–AG11)

**Key Finding:** ALL P1 agents write ONLY to in-memory `AgentOutput` objects (SpanLabels + Annotations). No agent writes directly to DB.

| Agent | Claims to Write | Actually Writes to DB |
|-------|----------------|----------------------|
| AG01 MetadataAgent | `AgentOutput` with SpanLabel[] (for reconciliation) | ❌ No DB writes — in-memory only |
| AG02 DesignAgent | `AgentOutput` with SpanLabel[] + design annotations | ❌ No DB writes — in-memory only |
| AG03 CohortAgent | `AgentOutput` with SpanLabel[] + population data | ❌ No DB writes — in-memory only |
| AG04 OutcomeAgent | `AgentOutput` with SpanLabel[] + outcome measures | ❌ No DB writes — in-memory only |
| AG05 StatsLabelAgent | `AgentOutput` with SpanLabel[] (numeric spans) | ❌ No DB writes — in-memory only |
| AG06 ExposureAgent | `AgentOutput` with SpanLabel[] + dose-response pairs | ❌ No DB writes — in-memory only |
| AG07 MediatorAgent | `AgentOutput` with SpanLabel[] + mechanistic claims | ❌ No DB writes — in-memory only |
| AG08 TemporalAgent | `AgentOutput` with SpanLabel[] + temporal patterns | ❌ No DB writes — in-memory only |
| AG09 ReconciliationAgent | `ReconcReport` with per-span verdicts | ❌ No DB writes — rule-based, no LLM |
| AG10 StrategicIntelAgent | `AgentOutput` with RawAnnotationEmission[] only | ❌ No DB writes — in-memory only |
| AG11 InstrumentValidationAgent | `AgentOutput` with SpanLabel[] (12 psychometric types) | ❌ No DB writes — in-memory only |

### Downstream Writer Modules (Actual DB Write Points)

| Module | Tables Written To |
|--------|------------------|
| **p0_triage/runner.py** | `study_registry_v1` (UPSERT) |
| **pipeline.py** | `extraction_runs` (INSERT) |
| **evidence_writer.py** | `edge_evidence_v1` (UPSERT via span_hash) |
| **validated_writer/persistence.py** | `edge_evidence_v1` (UPSERT) + `evidence_validation_quarantine_v1` (quarantine) |
| **tb_trust_boundary/quarantine_writer.py** | `edge_evidence_quarantine_v1` |
| **p1_extraction/reconciliation.py** | `study_annotations_raw_v1` + `review_tasks` |
| **p1_extraction/annotation_trust_boundary.py** | `study_annotations_v1` + `review_tasks` |
| **context_wiring.py** | `extraction_audit_v1` |
| **completeness_checker.py** | `extraction_completeness_v1` + `extraction_audit_v1` |
| **promotion_monitor.py** | `review_tasks` |
| **p4_aggregation/edge_writer.py** | `edges_v1` + `edge_param_builds_v1` |
| **p4_aggregation/double_counting.py** | `review_tasks` |
| **p7_compilers/runner.py** | `node_priors_v1` + `intervention_kernels_v1` + `recovery_trajectories_v1` + `intervention_synergy_v1` |
| **family_importers.py** | `population_norms_v1`, `node_priors_v1`, `temporal_evidence_v1`, `instrument_evidence_v1`, `biomarker_correlations_v1`, `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1`, `ontology_links_v1`, `dose_evidence_v1`, `subgroup_evidence_v1` |

---

## 3. Algorithm Chain DB Reads

### Chain A — Graph Construction
| File | Reads From | Type |
|------|-----------|------|
| `node_loader.py` | `registries/NODE_REGISTRY.csv` | CSV file (not DB) |
| `edge_loader.py` | `registries/EDGE_REGISTRY.csv` | CSV file (not DB) |
| `instrument_loader.py` | `registries/INSTRUMENT_REGISTRY.csv` | CSV file (not DB) |
| `spectral_validator.py` | BSkeleton (from edge_loader) + NodeMap (from node_loader) | In-memory (not DB) |
| `graph_object.py` | All above assembled | In-memory (not DB) |

**Chain A reads NO DB tables** — reads only CSV registry files from `registries/`.

### Chain B — Evidence
| File | Reads From | Type |
|------|-----------|------|
| `evidence_loader.py` | `edge_evidence_v1` JOIN `study_registry_v1` | DB (SQL query) |
| `evidence_compiler.py` | Evidence records from evidence_loader | In-memory |
| `pathway_evidence_scorer.py` | Takes compiled evidence + pathway specs | In-memory |
| `frozen_state.py` | Immutable compiled state | In-memory |

**Chain B reads 2 DB tables:** `edge_evidence_v1` and `study_registry_v1`.

---

## 4. Tables in Schema SQL but NOT in 05_TABLE_SCHEMAS.md

These tables exist in the SQL DDL and ORM but are **not documented** in the authoritative 05_TABLE_SCHEMAS.md:

| Table | SQL File | ORM Class | Notes |
|-------|----------|-----------|-------|
| `instrument_evidence_v1` | 002 | InstrumentEvidence | B10 — Psychometric evidence; actively written by family_importers |
| `population_norms_v1` | 002 | PopulationNorms | B11 — Population normative data; actively written by family_importers |
| `temporal_evidence_v1` | 002 | TemporalEvidence | B12 — Temporal effect patterns; actively written by family_importers |
| `dose_evidence_v1` | 002 | DoseEvidence | B13 — Dose-response data; actively written by family_importers |
| `subgroup_evidence_v1` | 002 | SubgroupEvidence | B14 — Subgroup/modifier evidence; actively written by family_importers |
| `acquisition_queue_v1` | 002 | AcquisitionQueue | B16 — Paper retrieval queue |
| `review_tasks` | 007 | ReviewTask | Ops — Cross-cutting human review queue; heavily used |
| `policy_snapshots` | 007 | PolicySnapshot | Ops — Configuration version tracking |
| `build_manifests_v1` | 007 | BuildManifest | Ops — Build provenance |
| `extraction_runs` | 007 | ExtractionRun | Ops — Per-paper extraction run tracking; critical |
| `study_annotations_v1` | 008 | StudyAnnotations | Validated canonical annotations from papers |
| `study_annotations_raw_v1` | 008 | StudyAnnotationsRaw | All raw annotation emissions (audit trail) |
| `edge_evidence_quarantine_v1` | 009 | EdgeEvidenceQuarantine (in quarantine_writer) | QA-rejected evidence |
| `extraction_completeness_v1` | 010 | ExtractionCompleteness | Per-paper extraction completeness metrics |
| `evidence_validation_quarantine_v1` | 012 | EvidenceValidationQuarantine | Validation-failed rows from validated_writer |
| `node_search_terms_v1` | 001 | NodeSearchTerms | Search terms for node mapping |

**= 16 tables in schema/ORM but missing from 05_TABLE_SCHEMAS.md**

---

## 5. Tables in 05_TABLE_SCHEMAS.md but NOT in Schema SQL

| Table | Documented As | Notes |
|-------|--------------|-------|
| *(none found)* | — | All 64 documented tables have corresponding SQL CREATE TABLE statements |

All tables in the doc have SQL DDL. However, `extraction_audit_v1` is documented under E13 in the schema doc, which is technically a Class B table in the SQL (file 002), not Class E.

---

## 6. ORM Model Count Summary

| Category | Count |
|----------|-------|
| ORM models in tables.py (`__tablename__`) | **77** |
| Tables in 05_TABLE_SCHEMAS.md | **64** (A:33 + B:9 + C:7 + D:7 + E:12, with E13=extraction_audit counted under B) |
| Tables in SQL schemas (001-013) | **80** (includes IF NOT EXISTS variants and operational tables) |
| Gap: In SQL/ORM but NOT in doc | **16** |
| Gap: In doc but NOT in SQL/ORM | **0** |

---

## 7. Complete Cross-Reference: Tables Actively Written by Extraction Code

| DB Table | Written By | Code Evidence |
|----------|-----------|---------------|
| `study_registry_v1` | p0_triage/runner.py | `session.add(study_row)` — UPSERT |
| `extraction_runs` | pipeline.py | `session.add(run)` |
| `edge_evidence_v1` | evidence_writer.py, validated_writer/persistence.py | `session.add(evidence_row)` + UPSERT |
| `edge_evidence_quarantine_v1` | tb_trust_boundary/quarantine_writer.py | `session.add(row)` — EdgeEvidenceQuarantine |
| `evidence_validation_quarantine_v1` | validated_writer/persistence.py | `session.add(q_row)` — EvidenceValidationQuarantine |
| `study_annotations_raw_v1` | p1_extraction/reconciliation.py | `session.add(raw_row)` — StudyAnnotationsRaw |
| `study_annotations_v1` | p1_extraction/annotation_trust_boundary.py | `session.add(row)` — StudyAnnotations |
| `review_tasks` | annotation_trust_boundary.py, reconciliation.py, promotion_monitor.py, double_counting.py | `session.add(task)` — ReviewTask |
| `extraction_audit_v1` | context_wiring.py, completeness_checker.py | `session.add(audit_row)` — ExtractionAudit |
| `extraction_completeness_v1` | completeness_checker.py | `session.add(row)` — ExtractionCompleteness |
| `edges_v1` | p4_aggregation/edge_writer.py | `session.add(orm_edge)` |
| `edge_param_builds_v1` | p4_aggregation/edge_writer.py | `session.add(build_record)` |
| `node_priors_v1` | p7_compilers/runner.py, family_importers.py | `session.add(row)` |
| `intervention_kernels_v1` | p7_compilers/runner.py | `session.add(row)` |
| `recovery_trajectories_v1` | p7_compilers/runner.py | `session.add(row)` |
| `intervention_synergy_v1` | p7_compilers/runner.py | `session.add(row)` |
| `population_norms_v1` | family_importers.py | `session.add(orm_obj)` |
| `temporal_evidence_v1` | family_importers.py | `session.add(orm_obj)` |
| `instrument_evidence_v1` | family_importers.py | `session.add(orm_obj)` |
| `biomarker_correlations_v1` | family_importers.py | `session.add(orm_obj)` |
| `study_cohort_profiles_v1` | family_importers.py | `session.add(orm_obj)` |
| `profile_data_streams_v1` | family_importers.py | `session.add(orm_obj)` |
| `stream_timepoints_v1` | family_importers.py | `session.add(orm_obj)` |
| `ontology_links_v1` | family_importers.py | `session.add(orm_obj)` |
| `dose_evidence_v1` | family_importers.py | `session.add(orm_obj)` |
| `subgroup_evidence_v1` | family_importers.py | `session.add(orm_obj)` |

**Total tables actively written by extraction code: 26**

---

## 8. Tables NEVER Referenced in Any Code (Dormant)

These tables have SQL schemas and/or ORM models but are never written to or read from in the current extraction or algorithm code:

| Table | Class | Has ORM | In SQL | Status |
|-------|-------|:-------:|:------:|--------|
| `edge_ontology_v1` | A2 | ✅ | ✅ | **Dormant** — never read or written by extraction/algorithm code |
| `predictor_alignment_rules_v1` | A7 | ✅ | ✅ | **Dormant** — design-time curation table, no extraction writer |
| `literary_mechanistic_priors_v1` | A8 | ✅ | ✅ | **Dormant** — design-time, no code reads/writes |
| `literary_constraints_v1` | A9 | ✅ | ✅ | **Dormant** — design-time, no code reads/writes |
| `contraindication_rules_v1` | A10 | ✅ | ✅ | **Dormant** — design-time, runtime not yet built |
| `action_contraindication_links_v1` | A11 | ✅ | ✅ | **Dormant** — design-time, runtime not yet built |
| `contraindication_escalation_policy_v1` | A12 | ✅ | ✅ | **Dormant** — design-time, runtime not yet built |
| `validation_rules_v1` | A13 | ✅ | ✅ | **Dormant** — ETL validation not yet wired |
| `variable_definitions_v1` | A14 | ✅ | ✅ | **Dormant** — modifier system not yet wired |
| `variable_to_input_map_v1` | A15 | ✅ | ✅ | **Dormant** — intake form mapping not yet wired |
| `baseline_modifier_definitions_v1` | A16 | ✅ | ✅ | **Dormant** — modifier system not yet wired |
| `derived_feature_definitions_v1` | A17 | ✅ | ✅ | **Dormant** — feature computation not yet wired |
| `triangulation_sets_v1` | A18 | ✅ | ✅ | **Dormant** — triangulation not yet wired |
| `triangulation_members_v1` | A19 | ✅ | ✅ | **Dormant** — triangulation not yet wired |
| `description_templates_v1` | A20 | ✅ | ✅ | **Dormant** — UI rendering not yet built |
| `action_catalog_v1` | A21 | ✅ | ✅ | **Dormant** — runtime candidate gen not yet built |
| `question_bank_v1` | A22 | ✅ | ✅ | **Dormant** — adaptive intake not yet built |
| `question_observation_models_v1` | A23 | ✅ | ✅ | **Dormant** — adaptive intake not yet built |
| `normalization_refs_v1` | A24 | ✅ | ✅ | **Dormant** — feature normalization not yet wired |
| `observation_noise_v1` | A25 | ✅ | ✅ | **Dormant** — Bayesian weighting not yet wired |
| `pathway_interactions_v1` | A27 | ✅ | ✅ | **Dormant** — cross-pathway reasoning not yet built |
| `feedback_loops_v1` | A31 | ✅ | ✅ | **Dormant** — stability verification not yet wired |
| `mid_thresholds_v1` | A33 | ✅ | ✅ | **Dormant** — severity mapping not yet built |
| `triangulation_evidence_v1` | B8 | ✅ | ✅ | **Dormant** — multi-method agreement extraction not yet done |
| `pathway_biomarkers_v1` | B9 | ✅ | ✅ | **Dormant** — biomarker-pathway extraction not yet done |
| `dose_bridges_v1` | C2 | ✅ | ✅ | **Dormant** — dose bridge compilation not yet wired |
| `outcome_anchors_v1` | C4 | ✅ | ✅ | **Dormant** — calibration anchors not yet populated |
| `state_estimator_specs_v1` | C5 | ✅ | ✅ | **Dormant** — estimator config not yet populated |
| `chain_validation_results_v1` | C6 | ✅ | ✅ | **Dormant** — chain validation not yet run |
| `publication_bias_results_v1` | C7 | ✅ | ✅ | **Dormant** — pub bias assessment not yet run |
| `objective_specs_v1` | D1 | ✅ | ✅ | **Dormant** — optimization not yet built |
| `safety_policies_v1` | D2 | ✅ | ✅ | **Dormant** — safety gating not yet built |
| `escalation_policies_v1` | D3 | ✅ | ✅ | **Dormant** — not yet built |
| `status_quo_rules_v1` | D4 | ✅ | ✅ | **Dormant** — scenario construction not yet built |
| `voi_rules_v1` | D5 | ✅ | ✅ | **Dormant** — VOI selection not yet built |
| `complexity_scaling_results_v1` | D6 | ✅ | ✅ | **Dormant** — offline validation not yet built |
| `population_archetypes_v1` | D7 | ✅ | ✅ | **Dormant** — archetype assignment not yet built |
| ALL Class E tables (E1-E12) | E | ✅ | ✅ | **Dormant** — runtime engine not yet built |
| `policy_snapshots` | Ops | ✅ | ✅ | **Dormant** — versioning not yet wired |

---

## 9. Summary Statistics

| Metric | Count |
|--------|-------|
| Total unique tables (SQL DDL) | **80** |
| Tables documented in 05_TABLE_SCHEMAS.md | **64** |
| Tables with ORM models | **77** |
| Tables actively written to (extraction) | **26** |
| Tables actively read (algorithm chains) | **2** (both via Chain B evidence_loader) |
| Tables read from CSV (not DB) | **3** (NODE_REGISTRY, EDGE_REGISTRY, INSTRUMENT_REGISTRY) |
| Dormant tables (schema exists, no code R/W) | **~49** |
| Documentation gap (in SQL, not in doc) | **16** tables |
| Code gap (in doc, not in SQL) | **0** tables |
