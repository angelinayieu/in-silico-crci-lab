# CRCI Framework — Controlled Vocabularies
## Complete Enum Registry Across All 69 Tables and In-Memory States

**Version:** 1.0

**Purpose:** Single reference for every constrained-value field in the CRCI specification. Organized by semantic domain so that related enums can be reviewed together for consistency.

**Companion documents:**
- `05_TABLE_SCHEMAS.md` — Column-level schemas where these enums appear
- `08_CHAIN_SPECS.md` — In-memory state schemas where pipeline enums appear
- `01_DATA_ARCHITECTURE_PHILOSOPHY.md` — Conventions for how enums are documented

**Notation:**
- **ENUM** = Formal database ENUM type (enforced at DB level)
- **TEXT{}** = TEXT column with application-enforced constrained values
- **In-Memory** = Used only in intermediate pipeline state, not persisted

---

# PART 1: SYSTEM-WIDE ENUMS (Used Across Multiple Tables)

## 1.1 Lifecycle Classification

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **lifecycle_class** | `A`, `B`, `C`, `D`, `E` | All 64 tables (metadata) | A=Knowledge, B=Evidence, C=Compiled, D=Policy, E=Output. See `01_DATA_ARCHITECTURE_PHILOSOPHY.md` §2. |
| **evidence_grade** | `A`, `B`, `C`, `D`, `E` | `edges_v1`, `baseline_modifier_definitions_v1`, `modifier_eval_trace_v1` | A=strongest (meta-analysis k≥5), E=weakest (no empirical data). Distinct from lifecycle_class despite same letters. |
| **evidence_strength** | `strong`, `moderate`, `weak` | `action_catalog_v1`, multiple knowledge tables | Coarser 3-level confidence. |
| **evidence_strength (ext)** | `strong`, `moderate`, `weak`, `background` | `literary_mechanistic_priors_v1` | Extended with `background` for theoretical priors. |
| **evidence_basis** | `direct_intervention`, `mechanistic_only`, `guideline_derived`, `mixed` | `action_catalog_v1` | Provenance class for intervention inclusion. |
| **evidence_basis (ext)** | `human_clinical`, `human_observational`, `human_experimental`, `in_vitro`, `animal`, `mixed`, `theory` | `literary_mechanistic_priors_v1`, `literary_constraints_v1` | Extended set for research provenance. |
| **evidence_level** | `meta`, `RCT`, `obs`, `mixed` | `edge_evidence_v1` | Study-level evidence hierarchy. |

## 1.2 Cancer & Clinical Context

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **cancer_type (full)** | `breast`, `lung`, `colorectal`, `hematological`, `mixed_solid`, `general_population`, `any` | `normalization_refs_v1` | Most inclusive set — includes `general_population` for non-cancer norms and `mixed_solid` for multi-cancer studies. |
| **cancer_type (standard)** | `breast`, `colorectal`, `hematological`, `lung`, `any` | `biomarker_correlations_v1`, `recovery_trajectories_v1` | Core cancer types without mixed/general. |
| **cancer_type (compact)** | `breast`, `colorectal`, `lung`, `mixed`, `all` | Various TEXT fields | Compact version with `mixed`/`all` replacing `any`/`mixed_solid`. **Reconciliation needed** — should align with standard set. |
| **treatment_phase (ENUM)** | `pre_treatment`, `during_treatment`, `early_post`, `late_post`, `survivorship`, `any` | `normalization_refs_v1` | Full clinical phases for norms. |
| **treatment_phase (TEXT)** | `active_chemo`, `post_treatment`, `mixed`, `all` | Variable definitions, modifier rules, scope fields | Coarser operational set. **Note:** `active_chemo` ≈ `during_treatment`, `post_treatment` ≈ `early_post`+`late_post`. |
| **cancer_validation_status** | `validated_cancer`, `used_cancer`, `general_population`, `known_somatic_confound` | `observation_noise_v1` | ENUM. Determines SE multiplier (§2.7). `known_somatic_confound` triggers highest multiplier. |

## 1.3 Pipeline Identification

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **pipeline_stage** | `P0_triage`, `P1_extraction`, `TB_trust_boundary`, `P2_harmonization`, `P2E_extended`, `P3_assimilation`, `P4_aggregation`, `P5_sufficiency` | `extraction_audit_v1` | ENUM. Maps 1:1 to SYS_EXTRACTION chains. Missing: `P6_deployment_validation` (should be added). |
| **status (pipeline)** | `success`, `partial`, `failed`, `skipped` | `extraction_audit_v1` | ENUM. Stage outcome. |
| **status (general)** | `ok`, `failed`, `partial` | Various trace tables | TEXT. Compact 3-value version. |

## 1.4 Polymorphic FK Discriminators

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **target_entity_type (norm)** | `instrument`, `measure`, `feature` | `normalization_refs_v1` | ENUM. Resolves polymorphic FK to definitions tables. |
| **target_entity_type (noise)** | `instrument`, `measure`, `feature`, `question` | `observation_noise_v1` | ENUM. Extended with `question` for adaptive questioning. |
| **member_entity_type** | `feature` | `triangulation_members_v1` | TEXT. Currently only features participate in triangulation sets. |

---

# PART 2: DOMAIN-SPECIFIC ENUMS — KNOWLEDGE (Class A)

## 2.1 Node & Edge Ontology

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **orientation** | `higher_worse`, `higher_better`, `neutral` | `biomarker_node_definitions_v1` | Scoring direction for DAG nodes. |
| **directionality (node)** | `higher_worse`, `higher_better`, `neutral`, `context` | Various schema fields | Extended with `context` for context-dependent interpretation. |
| **directionality (pathway)** | `bidirectional`, `a_to_b`, `b_to_a` | `pathway_interactions_v1` | ENUM. Pathway interaction direction. |
| **node_role** | `context`, `exposure`, `mediator`, `symptom`, `cognition`, `outcome`, `composite` | Schema fields | Functional role of nodes in DAG. |
| **relation_type** | `causal`, `associational`, `mechanistic`, `hypothesized` | `edge_relations_definitions_v1` | Edge causal status. |

## 2.2 Instruments & Measures

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **instrument_kind** | `questionnaire`, `diary`, `clinician_scale`, `cognitive_test`, `other` | `instrument_definitions_v1` | Instrument modality. |
| **instrument_method** | `self_report`, `clinician_rated`, `objectively_administered`, `hybrid` | `instrument_definitions_v1` | Administration method. |
| **administration_role** | `self_administered`, `interviewer_administered`, `clinician_administered`, `device_auto`, `unknown` | `instrument_definitions_v1` | Who administers. |
| **administration_setting** | `clinic`, `home`, `lab`, `remote`, `unknown` | `instrument_definitions_v1` | Where administered. |
| **measure_kind** | `biomarker`, `wearable`, `clinical_lab`, `imaging`, `other` | `measure_definitions_v1` | Measurement modality. |
| **proxy_type** | `level`, `intercept`, `slope`, `quadratic_slope`, `CAR`, `AUC`, `bedtime`, `awakening`, `composite`, `other` | `measure_definitions_v1` | TEXT{} — 10 values. How this measure approximates the underlying construct (§2.7). |
| **sample_matrix** | `plasma`, `serum`, `csf`, `saliva`, `tissue`, `stool`, `urine` | `pathway_biomarkers_v1` | ENUM. Biological sample type for biomarker interpretation. |
| **indicator_type** | `direct_marker`, `proxy_marker`, `functional_readout` | `pathway_biomarkers_v1` | ENUM. Biomarker-pathway relationship type. |

## 2.3 Pathways & Interactions

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **tier (pathway)** | `mechanistic_model_implied`, `mechanistic_emerging`, `mechanistic_placeholder`, `clinical_mediator` | `pathways_v1` | ENUM. Pathway evidence maturity (§2.3.1–2.3.2). |
| **causal_evidence_level** | `causal_demonstrated`, `strong_association`, `moderate_association`, `plausible` | `pathways_v1` | ENUM. Causal evidence strength for pathways. |
| **interaction_type (pathway)** | `feed_forward`, `convergent`, `antagonistic`, `independent` | `pathway_interactions_v1` | ENUM. Cross-pathway interaction type. |
| **interaction_type (synergy)** | `synergistic`, `additive`, `antagonistic` | `intervention_synergy_v1` | ENUM. Pairwise intervention interaction. |
| **validation_status** | `validated`, `partially_validated`, `not_tested` | `intervention_synergy_v1` | ENUM. Empirical confirmation status. |

## 2.4 Interventions & Actions

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **action_class** | `sleep`, `physical_activity`, `light_exposure`, `stress_regulation`, `nutrition`, `medication_support_nonrx`, `cognitive_training`, `social`, `clinical_followup`, `other` | `action_catalog_v1` | ENUM. 10-value coarse intervention taxonomy. |
| **dose_type** | `continuous`, `ordinal`, `binary` | `action_catalog_v1`, `dose_bridges_v1` | ENUM. Dose representation. |
| **dose_response_family** | `linear`, `saturating`, `hill` | `dose_bridges_v1` | Dose-response functional form. |
| **schedule_pattern** | `once`, `per_visit`, `qd`, `bid`, `tid`, `5_per_day`, `event_based`, `custom` | Schedule-related fields | Dosing frequency patterns. |

## 2.5 Temporal Dynamics

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **kernel_family** | `delta`, `exponential`, `step`, `gamma`, `biexponential`, `saturation`, `adaptation`, `trapezoidal` | `intervention_kernels_v1` | ENUM. 8 temporal kernel families (§2.11). |
| **temporal_family** | `delta`, `exponential` | Various temporal fields | Compact 2-value set for simple temporal models. |
| **time_step_unit** | `day`, `week` | `state_estimator_specs_v1` | Simulation time resolution. |
| **time_aggregation** | `momentary`, `daily`, `weekly`, `monthly`, `study_window`, `other` | Measurement fields | How temporal data is binned. |
| **time_aggregation (ext)** | `momentary`, `diurnal`, `24h`, `daily`, `weekly`, `monthly`, `study_window`, `other` | Extended measurement fields | With circadian-specific bins. |
| **time_window** | `momentary`, `daily`, `weekly`, `monthly`, `study_window`, `custom` | Various scope fields | Observation window granularity. |
| **timepoint_type** | `anchor`, `offset`, `clock`, `bedtime`, `other` | `stream_timepoints_v1` | How timepoint is anchored. |

## 2.6 Statistical Methodology

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **study_design** | `RCT`, `longitudinal`, `cross_sectional`, `meta`, `intensive`, `mechanistic`, `other` | `study_registry_v1`, `study_cohort_profiles_v1` | Study design classification. |
| **effect_type_reported (standard)** | `std_beta`, `unstd_beta`, `OR`, `RR`, `group_diff`, `other` | `edge_relations_definitions_v1` | 6-value effect type as reported. |
| **effect_type_reported (extended)** | `std_beta`, `unstd_beta`, `percent_change`, `OR`, `RR`, `HR`, `group_diff`, `other` | `edge_evidence_v1` | Extended with `percent_change` and `HR`. |
| **effect_scale** | `SD_SD`, `PROXY_PER_SD`, `LOGOR_PER_SD`, `RAW_PER_SD` | `edges_v1`, harmonization | Harmonized output scale. |
| **model_family** | `OLS`, `LMM`, `GLMM`, `GEE`, `Cox`, `other`, `unknown` | `edge_evidence_v1` | Statistical model used in source study. |
| **se_type** | `model_based`, `robust`, `cluster_robust`, `bootstrap`, `unknown` | `edge_evidence_v1` | Standard error estimation method. |
| **aggregation_method** | `IVW_fixed`, `IVW_random`, `single_best`, `expert_pick` | `edges_v1` | Meta-analytic pooling method. |
| **beta_dist_family** | `normal`, `student_t`, `lognormal`, `empirical`, `unknown` | Prior distribution fields | Parametric family for β distributions. |

## 2.7 Correlation & Noise

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **noise_source** | `psychometric`, `test_retest`, `icc`, `estimated`, `default` | `observation_noise_v1` | ENUM. How measurement noise was derived. |
| **d_block** | `inflammatory`, `neuro_stress`, `independent` | `biomarker_correlations_v1` | ENUM. Block-diagonal D matrix grouping (§2.17.2). |
| **agreement_metric** | `pearson_r`, `spearman_r`, `icc`, `kappa`, `other` | `triangulation_evidence_v1` | Cross-method agreement statistic. |
| **agreement_scope** | `pairwise`, `overall` | `triangulation_evidence_v1` | Agreement measurement scope. |

## 2.8 Derived Features & Variables

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **feature_type** | `status`, `composite`, `interaction`, `trend`, `variability`, `flag`, `quality_metric`, `cluster_code`, `other` | `derived_feature_definitions_v1` | Computed feature classification. |
| **feature_domain** | `demographic`, `treatment`, `behavior`, `symptom`, `perception`, `physiology`, `immune`, `neuro`, `biomarker`, `outcome`, `diagnostic`, `qa`, `other` | `derived_feature_definitions_v1` | Feature semantic domain. |
| **feature_source** | `observed_only`, `derived_only`, `hybrid` | `derived_feature_definitions_v1` | Data provenance. |
| **compute_stage** | `intake`, `preprocess`, `state_estimation`, `postprocess`, `qa` | `derived_feature_definitions_v1` | When feature is computed in pipeline. |
| **variable_type** | `binary`, `ordinal`, `continuous`, `categorical` | `variable_definitions_v1` | Statistical type for modifier variables. |
| **variable_domain** | `demographic`, `treatment`, `behavior`, `symptom`, `physiology`, `other` | `variable_definitions_v1` | Variable semantic domain. |

## 2.9 Questions

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **question_role** | `safety_gate`, `baseline_intake`, `adaptive_profile`, `monitoring`, `calibration` | `question_bank_v1` | Question functional purpose. |
| **answer_type** | `binary`, `ordinal`, `integer`, `real`, `multi_select`, `text`, `date`, `time` | `question_bank_v1` | Expected response type. |
| **response_status** | `answered`, `skipped`, `timed_out` | `question_sequence_v1` | ENUM. Patient response outcome. |
| **selection_stage** | `safety_prereq`, `identifiability_prereq`, `voi_ranked` | `question_selection_trace_v1` | Why question was selected. |
| **missing_answer_policy** | `skip`, `retry`, `set_unknown`, `escalate` | `question_bank_v1` | How to handle non-response. |

---

# PART 3: DOMAIN-SPECIFIC ENUMS — HARMONIZATION (Class B)

## 3.1 Harmonization Rules

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **harmonization_status** | `complete`, `partial`, `blocked`, `unreviewed` | `edge_evidence_v1` | Row-level harmonization outcome. |
| **conversion_family** | `unstd_beta_to_proxy_per_sd`, `std_beta_to_sd_sd`, `or_to_logor_per_sd`, `rr_to_logrr_per_sd`, `group_diff_to_proxy_per_sd`, `other` | `harmonization_rules_v1` | Scale conversion formula applied. |
| **effect_on_pipeline** | `allow`, `downweight`, `block`, `flip_sign`, `cap_magnitude`, `set_latency`, `set_phase_scope`, `require_stratification` | `harmonization_rules_v1`, `literary_constraints_v1` | What the rule does when matched. |

---

# PART 4: DOMAIN-SPECIFIC ENUMS — POLICY (Class D)

## 4.1 Safety & Contraindications

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **severity (contraindication)** | `hard_block`, `soft_penalty`, `require_question`, `escalate` | `contraindication_rules_v1` | Rule severity/response type. |
| **action_taken** | `blocked_action`, `penalized`, `asked_question`, `escalated`, `none` | `contraindication_eval_trace_v1` | What the system did in response. |
| **system_behavior (escalation)** | `block_all_actions`, `block_action_classes`, `allow_only_low_burden`, `require_clinician_review` | `escalation_policies_v1` | Escalation response mode. |
| **unknown_input_policy** | `treat_as_false`, `treat_as_true`, `trigger_question`, `escalate` | `contraindication_rules_v1` | How to handle missing safety-relevant data. |
| **trigger_type** | `contra_rule_true`, `contra_rule_unknown`, `out_of_scope_model`, ... | `escalation_policies_v1` | What triggered escalation. |

## 4.2 Objectives & Optimization

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **selection_rule** | `max_expected_utility`, `risk_averse_quantile`, `cvar_min` | `objective_specs_v1` | Schedule ranking method. |
| **risk_metric** | `expected`, `p10`, `p25`, `cvar10`, `worst_case` | `objective_specs_v1` | Risk quantification approach. |
| **output_mode (obj)** | `index_mode`, `calibrated_mode` | `objective_specs_v1` | Score output format. |

## 4.3 Validation Rules

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **rule_type (validation)** | `fk_integrity`, `range_check`, `cross_column_consistency`, `cross_table_consistency`, `enum_membership`, `json_schema` | `validation_rules_v1` | Validation check category. |
| **severity (validation)** | `error`, `warning` | `validation_rules_v1` | Validation failure severity. |
| **enforcement_point** | `etl_commit`, `runtime_read`, `unit_test`, `all` | `validation_rules_v1` | When check runs. |

---

# PART 5: DOMAIN-SPECIFIC ENUMS — OUTPUT (Class E)

## 5.1 Session & Scenario

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **scenario_type** | `status_quo`, `candidate` | `scenario_definitions_v1` | Distinguishes baseline from intervention scenarios. |
| **plan_type** | `primary`, `alternative` | `schedule_plans_v1` | Recommended vs fallback schedule. |
| **source_tag** | `status_quo_inferred`, `candidate_generated` | `scenario_items_v1` | How action was included. |

## 5.2 Modifier Evaluation

| Enum Name | Values | Used By | Notes |
|-----------|--------|---------|-------|
| **evaluation_result** | `true`, `false`, `unknown` | `contraindication_eval_trace_v1` | Rule evaluation outcome. |
| **parameterization_mode** | `multiplicative`, `additive`, `set_to`, `delta_steps` | `baseline_modifier_definitions_v1` | How modifier adjusts β̂. |

---

# PART 6: IN-MEMORY PIPELINE ENUMS (From Chain Specs)

These enums exist only in intermediate state objects passed between subsystems within a chain. They are not persisted to database.

## 6.1 Triage (EX-P0)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **triage_decision** | `ACCEPT`, `REJECT`, `REVIEW` | TriageDecision state | Paper screening outcome. |
| **extraction_mode** | `SHALLOW`, `STANDARD`, `DEEP` | TriageDecision → EX-P1 | Extraction depth. SHALLOW: 4 agents. STANDARD: 9 agents. DEEP: 9 agents + CE. |

## 6.2 Trust Boundary (EX-TB)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **parse_status** | `CLEAN`, `AMBIGUOUS`, `FAILED` | ParsedNumeric state | Regex parse confidence. FAILED → record blocked at TB-G1. |
| **bound_type** | `EXACT`, `UPPER`, `LOWER` | TypedNumericValue state | P-value bound type (e.g., p < 0.05 is UPPER). |
| **stat_type** | 37 values (MeanSD, MedianIQR, CI, PValue, TestStat, OddsRatio, HazardRatio, Correlation, Proportion, SampleSize, MissingData, ...) | ParsedNumeric.value_type | Maps to 11 sub-parsers NP-01 through NP-11. |
| **span_label_type** | 40 values | SpanLabel.label_type | Full taxonomy of statistical labels extracted by AG5. |

## 6.3 Harmonization (EX-P2)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **plausibility_status** | `PASS`, `WARNING`, `FAIL` | ValidatedNumeric state | Bounds check outcome (S1). |
| **target_scale** | `SD_SD`, `LOGHR`, `LOGOR`, `PROXY`, `RAW_UNSTD`, `RAW_ORIGINAL` | RoutedNumeric state | Destination harmonization scale. |
| **conversion_gate_result** | `PROCEED`, `SIGN_ONLY`, `MAGNITUDE_ONLY`, `BLOCKED` | RoutedNumeric state | CG1–CG4 gate outcome. |
| **se_source** | `SE_DIRECT`, `SE_FROM_CI`, `SE_FROM_P`, `SE_MISSING` | ScaledNumeric state | How SE was obtained. |
| **harmonization_status (inmem)** | `FULL`, `PARTIAL`, `FAILED` | HarmonizedClaim state | Chain-level outcome per claim. |

## 6.4 Aggregation (EX-P4)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **prior_source** | `EMPIRICAL`, `LITERARY`, `UNINFORMATIVE`, `SKEPTICAL` | CompiledEdge state | 4-tier prior selection outcome. |
| **prior_type_paper** | `RobustMAP`, `Commensurate`, `PowerPrior`, `MechanisticSynthesis`, `StructuralPlaceholder` | node_priors_v1 | §2.10 prior selection framework. 5 branches of prior decision tree. |

## 6.4B Publication Bias (EX-P4B) — NEW

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **bias_risk** | `LOW`, `MODERATE`, `HIGH`, `INSUFFICIENT_K` | publication_bias_results_v1, edges_v1 | §2.12.1 overall publication bias assessment. INSUFFICIENT_K when k<10. |

## 6.5 Sufficiency & Coherence (EX-P5) — EXPANDED

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **sufficiency_recommendation** | `SUFFICIENT`, `MARGINAL`, `INSUFFICIENT` | SufficiencyReport state | Evidence base verdict. |
| **triage_tier** | `PASS`, `MONITOR`, `INVESTIGATE`, `ALARM`, `UNTESTABLE` | chain_validation_results_v1, edges_v1.coherence_flag | §2.13 chain-vs-direct triage. Z<1.5 / 1.5-2.0 / 2.0-3.0 / ≥3.0 / no direct evidence. |
| **failure_mode** | `NONE`, `MEDIATION_LEAK`, `COLLIDER_BIAS`, `TEMPORAL_MISMATCH`, `SCALE_INCOMPATIBILITY`, `POPULATION_DRIFT`, `MISSING_MODERATOR` | chain_validation_results_v1 | §2.13.2 discrepancy classification. 6 failure modes with remediation guidance. |

## 6.6 Intake (ALG-A)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **proxy_validity** | `DIRECT`, `PROXY`, `INDIRECT`, `NONE` | StandardizedFeatureVector state | Per-node measurement quality classification. |

## 6.7 Optimization (RUNTIME-G)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **safe_mode** | `A`, `B` | RankedSchedules state | Mode A: E[Δz]/uncertainty. Mode B: SAFE·burden·adherence. |
| **stability_class** | `STABLE`, `SOFT`, `UNSTABLE` | RankedSchedules state | Bootstrap rank stability. |

## 6.8 Reporting (RUNTIME-I)

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **output_mode** | `CLINICAL`, `POPULATION`, `RESEARCH` | RecommendationReport state | Report variant. |
| **severity_tier** | `Excellent`, `Good`, `Mild Concern`, `Moderate`, `Poor`, `Severe` | RecommendationReport state | 6-tier z-score mapping (§2.20), MID-anchored via mid_thresholds_v1. |
| **anchor_method** | `distribution_based`, `anchor_based`, `expert_consensus` | mid_thresholds_v1 | §2.20.2 MID threshold derivation method. |

## 6.9 Offline Validation (VAL-01) — NEW

| Enum Name | Values | Used In | Notes |
|-----------|--------|---------|-------|
| **horizontal_level** | `FULL`, `DROP_E`, `DROP_DE`, `DROP_CDE` | complexity_scaling_results_v1 | §2.13.1 edge removal levels. |
| **vertical_level** | `FULL_7LAYER`, `REDUCED_3LAYER`, `MINIMAL_1LAYER` | complexity_scaling_results_v1 | §2.13.1 heterogeneity simplification levels. |

---

# PART 7: RECONCILIATION NOTES

## 7.1 Variant Enums Requiring Alignment

Several enums have multiple variants across tables that should be reconciled:

| Enum Family | Variants | Recommendation |
|-------------|----------|----------------|
| **cancer_type** | 3 variants: full (7 values), standard (5), compact (5 different) | Align on standard 5-value set + `mixed_solid` + `general_population` as optional extensions. Replace `mixed`/`all` with `mixed_solid`/`any`. |
| **treatment_phase** | ENUM (6 values) vs TEXT (4 values) | Consolidate: use 6-value ENUM everywhere. Map `active_chemo`→`during_treatment`, `post_treatment`→`late_post`, `mixed`→ multi-select, `all`→`any`. |
| **evidence_strength** | 3 values vs 4 values (with `background`) | Keep `background` as extension. Base set: 3 values. |
| **target_entity_type** | 3 values vs 4 values (with `question`) | Superset is 4 values. Use 4 everywhere. |
| **effect_type_reported** | 6 values vs 8 values | Use 8-value set (with `percent_change`, `HR`) as canonical. |
| **status** | ENUM (4 values) vs TEXT (3 values) | Align on 4-value ENUM as canonical. |
| **interaction_type** | pathway (4 values) vs synergy (3 values) | Separate enums — different domains. Rename to `pathway_interaction_type` and `synergy_interaction_type`. |

## 7.2 Missing Enum Values

| Enum | Missing Value | Reason |
|------|--------------|--------|
| **pipeline_stage** | `P6_deployment_validation` | EX-P6 was added after initial schema. Add to enum. |
| **extraction_mode** | Not in any persisted table | Exists only in-memory. Consider persisting in `extraction_audit_v1`. |

## 7.3 Enum Count Summary

| Category | Count |
|----------|-------|
| Formal ENUM columns (DB-enforced) | 28 |
| TEXT{} constrained columns (app-enforced) | ~160 |
| In-memory pipeline enums | ~25 |
| **Total unique enum sets** | **~213** |
| Total unique enum values (approx.) | **~895** |

---

*End of Controlled Vocabularies v1.0*

**Supersedes:** No prior document (new).
**Action items:** See §7.1 for reconciliation recommendations. These should be resolved before schema migration.
