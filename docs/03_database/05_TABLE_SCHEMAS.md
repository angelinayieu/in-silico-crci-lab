# CRCI Framework — Complete Table Schemas
## Column-Level Reference for All 64 Tables

**Version:** 3.0 (Consolidated — extracted from 02_COMPLETE_SCHEMAS_v2_1.md §3)

**Purpose:** Full column glossary for every persisted table. Each entry includes an 8-field narrative header, complete column schema, and wiring notes.

**Companion documents:**
- `01_DATA_ARCHITECTURE_PHILOSOPHY.md` — Why the data layer is structured this way
- `04_TABLE_REGISTRY.md` — 16-field identity cards and master registry
- `06_FK_WIRING_MAP.md` — Complete foreign key graph

**Format:** Each table entry contains:
1. **Narrative Header** — Purpose, 1 Row =, Executed When, Executed Where, Input Tables, Output Tables
2. **Column Schema** — Column, Type, Controlled Vocab, Example, Notes
3. **Wiring Notes** — FK relationships, key validation rules, multi-consumer notes

---

### 3.1. Class A — Knowledge (Domain Definitions, Rules, Ontology)

> Human-curated at design time. Versioned. These tables define *what the system knows* — the causal structure, measurement properties, safety rules, and pathway specifications. They change only when domain experts update the knowledge base.

#### A1. `edge_relations_definitions_v1`

**Purpose:** Defines every permitted causal edge in the DAG — one row per directed source→target→mechanism relationship. The backbone ontology from which edges_v1 is compiled.

**1 Row =** One permitted causal edge (source_node → target_node → mechanism_type) in the CRCI DAG.

**Executed When:** Design-time authoring; read by extraction validation (EX-P1, EX-P2) and runtime graph construction (ALG-A).

**Input Tables (reads from):** biomarker_node_definitions_v1 (node_id references)

**Output Tables (consumed by):** edge_ontology_v1, edge_evidence_v1, edges_v1, pathways_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| edge_relation_id | TEXT (PK) | ER_[A-D]_[A-Z0-9_]+__[A-Z0-9_]+ | ER_A_SLEEP_DISRUPTION__HPA_DYSREG | Stable directed relation ID (X→Y). Keep module letter. |
| module | TEXT | {A,B,C,D} | A | Module membership. |
| edge_family | TEXT | your family vocab | A_SLEEP__HPA | Guardrail grouping. |
| node_x | TEXT (FK) | biomarker_node_definitions_v1.node_id | NODE_SLEEP_DISRUPTION | Upstream canonical node. |
| node_y | TEXT (FK) | biomarker_node_definitions_v1.node_id | NODE_HPA_DYSREG | Downstream canonical node. |
| relation_label | TEXT | free text | Sleep disruption → HPA dysregulation | UI/figures label. |
| canonical_statement | TEXT | 1–2 sentences | Higher sleep disruption increases HPA dysregulation. | Publication definition of what the relation means. |
| relation_type | TEXT | {causal,associational,mechanistic,hypothesized} | associational | Honest semantics. |
| default_effect_direction | INTEGER | {+1,-1} | 1 | Canonical sign in “worse→worse” convention after node orientations. |
| allowed_measure_ids_json | TEXT JSON nullable | JSON array of measure_id | ["MEAS_HPA_SLOPE_LNHR", ...] | Optional operationalization guardrail. |
| allowed_upstream_instruments_json | TEXT JSON nullable | JSON array of instrument_id | ["PSQI_TOTAL","ISI_TOTAL"] | Optional upstream guardrail. |
| default_temporal_family | TEXT nullable | {delta, exponential} | delta | Optional: ontology-level default used only during compilation if timing missing in evidence. Runtime should not depend o |
| notes | TEXT nullable | free text | Bidirectionality noted; model uses X→Y. | Caveats and scope warnings. No executable logic. |
| version | INTEGER | ≥1 | 1.0 | Version. |
| active | INTEGER | {0,1} | 1.0 | Soft enable/disable. |

---

#### A2. `edge_ontology_v1`

**Purpose:** Operational constraints for each edge type — which conversions, functional forms, and sign conventions are permitted. Guards the extraction pipeline from invalid operations.

**1 Row =** One set of operational constraints for one edge relation.

**Executed When:** Design-time authoring; read during extraction harmonization (EX-P2 CG4 gate) and runtime guardrails.

**Input Tables (reads from):** edge_relations_definitions_v1.edge_relation_id

**Output Tables (consumed by):** edge_evidence_v1 (gating outcome)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| ontology_id | TEXT (PK) | ONT_[A-Z0-9_]+ | ONT_ER_A_SLEEP__HPA_V1 | Stable ID for this operational spec. |
| edge_relation_id | TEXT (FK) | ER_* | ER_A_SLEEP_DISRUPTION__HPA_DYSREG | FK to edge_relations_definitions_v1. One-to-one. |
| binary_outcome_bridge_allowed | BOOLEAN | {TRUE,FALSE} | FALSE | Whether this edge may be used with binary outcome bridges (CG4 gate). |
| proxy_mapping_policy | TEXT | {strict_match,family_match,any} | family_match | How strictly downstream proxy must match allowed_measure_ids. |
| allowed_scales_json | TEXT (JSON) | JSON array | ["SD_SD","PROXY_PER_SD"] | Which harmonized effect scales are permitted for this edge. |
| estimand_compatibility_rules | TEXT | free text | Only per-SD interpretations; no OR unless binary outcome. | Human-readable + machine-parseable estimand constraints. |
| allowed_temporal_families_json | TEXT (JSON) | JSON array | ["delta","exponential"] | Which temporal response families are valid for this edge. |
| max_lag_steps | INTEGER (nullable) | >=0 | 14 | Hard cap on lag for this edge relation. NULL = no cap. |
| aggregation_constraints_json | TEXT (JSON) | JSON object | {"min_studies":1,"require_same_proxy":true} | Constraints on evidence aggregation for edge compilation. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |
| notes | TEXT (nullable) | free text |  | Non-executable notes. |

---

#### A3. `biomarker_node_definitions_v1`

**Purpose:** Defines every node (biomarker, construct, cognitive domain) in the 63-node causal DAG. The ROOT reference table for the entire system — nearly every other table references it.

**1 Row =** One node in the causal graph with its domain assignment, hierarchical layer, observability status, and orientation convention.

**Executed When:** Design-time authoring; read by nearly all subsystems across all pipeline stages.

**Input Tables (reads from):** None (ROOT table — other tables reference this)

**Output Tables (consumed by):** instrument_definitions_v1, measure_definitions_v1, edge_relations_definitions_v1, pathways_v1, node_priors_v1, and ~15 more

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| node_id | TEXT (PK) | NODE_[A-Z0-9_]+ | NODE_SLEEP_DISRUPTION | Stable join key. ASCII only. Never changes once published. |
| node_label | TEXT | free text | Sleep disruption | Display label for UI/reports. Does not affect computation. |
| node_symbol | TEXT (nullable) | free text | S* | Optional shorthand for figures. May include symbols because it is never used for joins. |
| node_role | TEXT | {context, exposure, mediator, symptom, cognition, outcome, composite} | exposure | Coarse semantic role for pipeline guardrails. Used to enforce “no double counting” (actions should target exposures only |
| orientation | TEXT | {higher_worse, higher_better, neutral} | higher_worse | Sign alignment anchor. Every mapping into this node must be aligned to this meaning. |
| node_domain | TEXT | {sleep, exercise, hpa_axis, inflammation, autonomic, neurotrophic, cognition, fatigue, mood, treatment, demographic, oth | sleep | Single grouping axis used for organization and UI filtering. |
| node_subtype | TEXT (nullable) | snake_case | cortisol_rhythm | Optional fine tag. Keep lowercase snake_case only. |
| default_state_space | TEXT | {z, raw, probability, 0_1} | z | Default numeric representation. In v1, most nodes should be z for interoperability across edges. |
| state_update_scale | TEXT | {static, daily, weekly, monthly, study_window} | weekly | Model update timestep for this node (not how often humans perform behavior). Controls estimator/simulator step for this |
| default_window_days | INTEGER (nullable) | integer ≥ 1 | 28.0 | Fallback lookback window used when a feature that feeds this node does not declare its own window. Feature-level window |
| min_observation_window_days | INTEGER (nullable) | integer ≥ 1 or NULL | 7.0 | Hard gate: an observation/feature is inadmissible to update this node if its effective window length < min_observation_w |
| allowed_source_types_json | JSON | array of {instrument, measure, derived_feature, node} | ["instrument","measure","derived_feature"] | Namespace admissibility gate: a node only accepts updates from listed namespaces. If a mapping attempts to feed this nod |
| is_actionable_input_node | BOOLEAN | {TRUE,FALSE} | True | Control-path invariant: only nodes with TRUE may be directly perturbed by actions via dose bridges. If FALSE, the node c |
| active | BOOLEAN | true/false | True | Soft-retire nodes without breaking joins. Runtime filters on active=TRUE. |
| version | INTEGER | integer ≥ 1 | 1.0 | Version counter for reproducibility. Increment only when semantics change. |
| description | TEXT | templated text | (see template) | Must follow the description template above. This is what reviewers will read. Keep it deterministic and policy-relevant. |
| notes | TEXT (nullable) | free text | Upstream node for sleep→HPA, sleep→inflammation. | Implementation/scope clarifications only. Do not restate description. |

---

#### A4. `instrument_definitions_v1`

**Purpose:** Defines every clinical assessment instrument (PSQI, FACT-Cog, MoCA, etc.) with psychometric properties, loading factors, reliability, and cancer-validation status (§2.7).

**1 Row =** One assessment instrument with its measurement properties, node mapping, and cancer-specific SE multiplier.

**Executed When:** Design-time authoring; read during extraction (EX-P1 OutcomeAgent) and runtime measurement model (ALG-C Stage A).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id, normalization_refs_v1.norm_id, observation_noise_v1.noise_id

**Output Tables (consumed by):** edge_evidence_v1, profile_data_streams_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| instrument_id | TEXT (PK) | INST_[A-Z0-9_]+ | INST_PSQI_TOTAL | Stable join key. ASCII only. |
| instrument_label | TEXT | free text | Pittsburgh Sleep Quality Index (total) | Human name for UI/audit. |
| maps_to_node_id | TEXT (FK→biomarker_node_definitions_v1.node_id) | NODE_[A-Z0-9_]+ | NODE_SLEEP_DISRUPTION | Declares the latent construct this instrument operationalizes. |
| instrument_kind | TEXT | {questionnaire, diary, clinician_scale, cognitive_test, other} | questionnaire | High-level class. Used for defaults and filtering. |
| instrument_method | TEXT | {self_report, clinician_rated, objectively_administered, hybrid} | self_report | Method label; not a quality claim, just provenance. |
| recall_window_days | INTEGER (nullable) | ≥1 | 28.0 | Typical recall window (e.g., PSQI ≈ 28 days). Used for time-window admissibility vs node minimum window. |
| time_aggregation | TEXT | {momentary, daily, weekly, monthly, study_window, other} | monthly | Instrument’s intrinsic time basis (for diaries, typically daily). |
| raw_scale_spec | TEXT | free text | 0–21 | Records the original scoring range; no computation. |
| raw_unit | TEXT | free text | points | Unit label for audit and validator messaging. |
| higher_means_pre_alignment | TEXT | {worse, better, mixed, context} | worse | Directionality before alignment. If mixed/context → must use explicit rule. |
| direction_rule_id | TEXT | DR_[A-Z0-9_]+ | DR_PSQI_HIGHER_WORSE | Executable rule to align instrument score to node orientation. Required unless truly neutral. |
| directionality_after_alignment | TEXT | {higher_worse,higher_better,neutral,context} | higher_worse | Audit assertion; must match applying direction_rule_id. |
| adapter_output_kind | TEXT | {z, dist_gaussian, dist_other} | z | What the adapter emits into the inference pipeline: a point z-score or a distribution. v1 can be z only. |
| adapter_spec_id | TEXT (nullable) | ADAPT_[A-Z0-9_]+ | ADAPT_PSQI_TO_SLEEP_Z_V1 | Optional pointer to a formal adapter spec if you externalize rules. If NULL, adapter behavior is implied by other column |
| required_fields_json | JSON | array of strings | ["value","timestamp"] | Runtime validator for incoming instrument responses. |
| thresholds_json | JSON (nullable) | JSON object | {"poor_sleep": {"op": ">", "value": 5}} | Optional quick-check thresholds for UI/QC; never used as primary computation unless referenced by a feature spec. |
| preferred_norm_ref_id | TEXT (nullable) | NORM_[A-Z0-9_]+ | NORM_PSQI_TOTAL_CANCER_SURVIVORS | Optional hint; actual binding happens via scope matching at runtime. |
| preferred_noise_id | TEXT (nullable) | NOISE_[A-Z0-9_]+ | NOISE_PSQI_TOTAL_SELFREPORT | Optional hint; actual binding happens via scope matching at runtime. |
| compatibility_group_id | TEXT (nullable) | COMPAT_[A-Z0-9_]+ | COMPAT_SLEEP_QUESTIONNAIRE_MONTHLY | Used to prevent fusing across incompatible constructs/time bases without explicit policy. |
| active | BOOLEAN | {TRUE,FALSE} | True | Soft-retire without breaking joins. |
| version | INTEGER | ≥1 | 1.0 | Increment only when semantics change. |
| description | TEXT | templated text | (see below) | Deterministic, reviewable description (1–3 sentences). |
| notes | TEXT (nullable) | free text | Monthly recall; broad sleep quality. | Human caveats only. |

---

#### A5. `measure_definitions_v1`

**Purpose:** Defines every biomarker, wearable metric, and proxy measurement type with assay specifications, sample matrix requirements, and node mappings.

**1 Row =** One biomarker/wearable/proxy measurement type with assay specs and normalization references.

**Executed When:** Design-time authoring; read during harmonization (EX-P2) and runtime dose bridging (ALG-D).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id, normalization_refs_v1.norm_id, observation_noise_v1.noise_id

**Output Tables (consumed by):** edge_evidence_v1, profile_data_streams_v1, dose_bridges_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| measure_id | TEXT (PK) | MEAS_[A-Z0-9_]+ | MEAS_CORTISOL_DIUM_SLOPE_LNHR_SALIVA | Stable join key. ASCII only. |
| measure_label | TEXT | free text | Diurnal cortisol slope (ln per hour) | Human-readable name for UI/audit. |
| maps_to_node_id | TEXT (FK→biomarker_node_definitions_v1.node_id) | NODE_[A-Z0-9_]+ | NODE_HPA_DYSREG | Declares latent construct this measure operationalizes. |
| measure_kind | TEXT | {biomarker, wearable, clinical_lab, imaging, other} | biomarker | High-level source category. Used for filtering + defaults. |
| analyte | TEXT (nullable) | {cortisol, il6, crp, tnfa, bdnf, other} | cortisol | Required if measure_kind=biomarker. Nullable otherwise. |
| specimen_or_device | TEXT | controlled (recommended) | saliva / actigraphy | Single field to cover specimen (biomarker) or device (wearable). |
| biospecimen | TEXT (nullable) | {saliva,blood,plasma,serum,urine,other,none} | saliva | Required if biomarker; else none or NULL. |
| device_type | TEXT (nullable) | {actigraphy, smartwatch_ppg, ring, eeg, other} | actigraphy | Required if wearable; else NULL. |
| proxy_type | TEXT | {level, intercept, slope, quadratic_slope, CAR, AUC, bedtime, awakening, composite, other} | slope | Prevents mixing non-equivalent proxy semantics. Required. |
| time_aggregation | TEXT | {momentary, diurnal, 24h, daily, weekly, monthly, study_window, other} | diurnal | Declares the window the proxy summarizes. Required. |
| raw_unit | TEXT | free text | Δ ln(cortisol)/hr | Unit as reported. Used for QA + conversion requirements. |
| value_transform_spec | TEXT (nullable) | {none, log, ln, zscore, rank, other} | ln | Declares any intrinsic transform of the reported value. Not harmonization of effects; just measurement-level spec. |
| direction_rule_id | TEXT | DR_[A-Z0-9_]+ | DR_FLATTENING_IS_WORSE | Executable rule to align this measure to node orientation. |
| directionality_after_alignment | TEXT | {higher_worse,higher_better,neutral,context} | higher_worse | Audit assertion; must match result of applying direction_rule_id. |
| measure_family_id | TEXT | FAM_[A-Z0-9_]+ | FAM_CORTISOL_DIUM_SLOPE | Comparable “family” class used for grouping/reporting. |
| compatibility_group_id | TEXT | COMPAT_[A-Z0-9_]+ | COMPAT_SALIVA_CORTISOL_SLOPE_LNHR | Strict compatibility key: only same group can be fused without special policy. |
| effective_window_days | INTEGER (nullable) | ≥1 | 1 or 7 | If known, used for admissibility checks vs node min_observation_window_days. If NULL, derived from time_aggregation mapp |
| min_required_samples | INTEGER (nullable) | ≥1 | 3.0 | E.g., slope/CAR requires multiple samples; if unmet, QC block. |
| required_fields_json | JSON | array of strings | ["value","timestamp","unit"] | Runtime validator for incoming raw observations. |
| preferred_norm_ref_id | TEXT (nullable) | NORM_[A-Z0-9_]+ | NORM_CORTISOL_SLOPE_SALIVA_ADULT | Optional hint; final binding occurs in feature computation via scope matching. |
| preferred_noise_id | TEXT (nullable) | NOISE_[A-Z0-9_]+ | NOISE_CORTISOL_SLOPE_SALIVA | Optional hint; final binding occurs at runtime via scope matching. |
| active | BOOLEAN | {TRUE,FALSE} | True | Soft-retire without breaking joins. |
| version | INTEGER | ≥1 | 1.0 | Increment only if semantics change. |
| description | TEXT | templated text | (see below) | Deterministic, reviewable description (1–3 sentences). |
| notes | TEXT (nullable) | free text | Flattening indicates HPA dysregulation. | Human caveats only. No computation. |

---

#### A6. `harmonization_rules_v1`

**Purpose:** Defines deterministic conversion formulas for transforming heterogeneous effect sizes to a common SMD scale — OR→SMD (Chinn 2000), r→d, HR→OR, etc. (§2.9 Layer 4).

**1 Row =** One validated conversion formula with delta-method SE propagation formula.

**Executed When:** Design-time authoring; read during extraction harmonization (EX-P2 Stage 3).

**Input Tables (reads from):** None

**Output Tables (consumed by):** edge_evidence_v1 (harmonized effect sizes)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| rule_id | TEXT (PK) | HR_[A-Z0-9_]+ | HR_UNSTD_BETA_XZ_YLOG | Unique |
| effect_type_reported | TEXT | {std_beta,unstd_beta,OR,RR,group_diff,other} | unstd_beta | Required |
| x_transform_required | TEXT | {none,log,z,any} | z | Required |
| y_transform_required | TEXT | {none,log,z,any} | log | Required |
| required_fields | TEXT | comma-separated column tokens | effect_value_reported,se_reported | Must be present in edge_evidence_v1 row |
| output_scale | TEXT | {SD_SD,PROXY_PER_SD,LOGOR_PER_SD,RAW_PER_SD} | PROXY_PER_SD | Required |
| conversion_family | TEXT | {unstd_beta_to_proxy_per_sd,std_beta_to_sd_sd,or_to_logor_per_sd,rr_to_logrr_per_sd,group_diff_to_proxy_per_sd,other} | or_to_logor_per_sd | Required |
| conversion_notes | TEXT | free text | If sd_y missing, remain PROXY_PER_SD | No executable logic |
| version | INTEGER | ≥1 | 1.0 | Increment only on semantic change |
| active | INTEGER | {0,1} | 1.0 | If 0, rule must not be used |

---

#### A7. `predictor_alignment_rules_v1`

**Purpose:** Defines alignment rules for matching study cohort characteristics to the target population — implements Layer 2 transportability (§2.9).

**1 Row =** One alignment rule for matching a cohort dimension to evidence applicability.

**Executed When:** Design-time authoring; read during evidence assimilation (EX-P3).

**Input Tables (reads from):** study_cohort_profiles_v1.profile_id, measure_definitions_v1.measure_id

**Output Tables (consumed by):** edge_evidence_v1 (scope_weight adjustment)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| align_id | TEXT (PK) | ALIGN_[A-Z0-9_]+ | ALIGN_TELL2014_NAP_LAG1 | Unique |
| profile_id | TEXT (FK) | PROF_* | PROF_TELL2014_BASE_T1 | Must exist in study_cohort_profiles_v1 |
| predictor_ref_type | TEXT | {instrument,feature} | feature | Required |
| predictor_ref_id | TEXT | instrument_id or FEAT_* | FEAT_DIARY_NAP_Z | Must exist in referenced table |
| outcome_measure_id | TEXT (FK) | measure_id | HPA_SLOPE_LNHR | Must exist in measure_definitions_v1 |
| alignment_type | TEXT | {same_day,prior_day,prior_week,rolling_window,custom} | prior_day | Required |
| lag_days | INTEGER | ≥0 | 1.0 | Required when alignment_type implies lag; else must be 0 |
| window_spec | TEXT (nullable) | deterministic string | P7D | Required iff rolling_window/custom |
| notes | TEXT (nullable) | free text | Prior-day nap predicts next-day cortisol | No executable logic |
| version | INTEGER | ≥1 | 1.0 | Version control |
| active | INTEGER | {0,1} | 1.0 | If 0 ignore |

---

#### A8. `literary_mechanistic_priors_v1`

**Purpose:** Defines literature-informed prior distributions for edges where direct evidence is sparse — Mechanistic Synthesis priors from the prior selection framework (§2.10).

**1 Row =** One prior distribution specification with provenance and discount parameter a₀.

**Executed When:** Design-time authoring; read at build-time edge compilation and runtime simulation (Stage F).

**Input Tables (reads from):** study_registry_v1.study_id (provenance)

**Output Tables (consumed by):** edges_v1 (prior parameters), dose_bridges_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| prior_id | TEXT (PK) | Yes | PR_HPA_ACUTE_CHRONIC_SPLIT_V1 |  |
| prior_label | TEXT | — | Acute vs chronic cortisol are distinct regimes |  |
| prior_type | TEXT | {applicability,sign_constraint,bound,shape,latency,context_split,quality_guardrail} | context_split |  |
| target_level | TEXT | {node,edge_family,edge_id,feature_id,pipeline} | edge_family |  |
| target_ref | TEXT | node_id / edge_family / edge_id / feature_id | A_ACTIVITY__HPA |  |
| condition_spec | TEXT | — | IF exposure_context=exercise AND duration_minutes<10 THEN treat as acute |  |
| effect_on_pipeline | TEXT | {allow,downweight,block,flip_sign,cap_magnitude,set_latency,set_phase_scope,require_stratification} | require_stratification |  |
| strength | TEXT | {hard,soft} | hard |  |
| prior_params | TEXT | — | {“cap_abs_beta”:0.20} |  |
| evidence_basis | TEXT | {human_clinical,human_observational,human_experimental,in_vitro,animal,mixed,theory} | human_experimental |  |
| study_id | TEXT (FK) | -- | STUDY_TELL2014 |  |
| population_scope | TEXT | {breast,colorectal,lung,mixed,all} | all |  |
| phase_scope | TEXT | {active_chemo,post_treatment,mixed,all} | all |  |
| version | INTEGER | — | 1.0 |  |
| active | INTEGER | {0,1} | 1.0 |  |
| notes | TEXT | — | Mechanistic-only; not eligible for Table 1 betas |  |

---

#### A9. `literary_constraints_v1`

**Purpose:** Defines biological bounds on node trajectories — physiological ceilings (±1.0 SD single, ±1.5 SD bundle), rate limits, and floor constraints that prevent impossible simulation states (§2.12 Step 4).

**1 Row =** One biological constraint on a node or edge trajectory with enforcement mode.

**Executed When:** Design-time authoring; read at runtime simulation (Stage F) and temporal prediction (Stage E/ALG-E).

**Input Tables (reads from):** measure_definitions_v1.measure_id, study_registry_v1.study_id

**Output Tables (consumed by):** simulation_trace_v1 (constraint enforcement flags)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| rule_id | TEXT (PK) | Yes | CONSTR_HPA_POSTEX_TIMECOURSE_V1 |  |
| rule_label | TEXT | — | Post-exercise cortisol elevation timecourse |  |
| rule_type | TEXT | {bound,gate,timecourse,validity_scope,consistency} | timecourse |  |
| strength | TEXT | {hard,soft} | soft |  |
| applies_to_node | TEXT | node_id (Table 3) | H_HPA_DYSREG |  |
| applies_to_measure_id | TEXT | measure_id (Table 5) | HPA_CAR_LOG |  |
| applies_to_aux_variable | TEXT | — | CORTISOL_CONC_PROXY |  |
| regime | TEXT | {acute,chronic,post_event,baseline,all} | post_event |  |
| phase_scope | TEXT | {active_chemo,post_treatment,mixed,all} | all |  |
| population_scope | TEXT | {breast,colorectal,lung,mixed,all} | all |  |
| trigger_inputs_required | TEXT | feature_id / raw input key list (semicolon-separated) | EXERCISE_DURATION_MIN;EXERCISE_INTENSITY_BIN;TIME_SINCE_EX_END_MIN |  |
| rule_spec | TEXT | — | if EXERCISE_DURATION_MIN>=30 and EXERCISE_INTENSITY_BIN=1 then expected_recovery_min≈60; set soft_prior on CORTISOL_CONC |  |
| effect_on_engine | TEXT | {clip,reject,reweight,mask,annotate} | reweight |  |
| output_target | TEXT | {node_state,measure_value,aux_variable,edge_activation} | aux_variable |  |
| output_scale | TEXT | {z,raw,0_1,minutes,days,json} | minutes |  |
| output_range | TEXT | — | [0,180] |  |
| missingness_policy | TEXT | {block,soft_default,assume_false,assume_true,set_null} | soft_default |  |
| default_behavior | TEXT | — | No timecourse prior applied; leave cortisol unconstrained |  |
| priority | TEXT | {core,optional,experimental} | optional |  |
| version | INTEGER | — | 1.0 |  |
| active | INTEGER | {0,1} | 1.0 |  |
| study_id | TEXT | — | PAPER_LUU2025_HALF_LIFE;TEXTBOOK_HPA_DYNAMICS |  |
| notes | TEXT | — | Soft constraint only; does not assert population causal effect; prevents impossible long-lived acute spikes |  |

---

#### A10. `contraindication_rules_v1`

**Purpose:** Defines every safety rule with trigger predicates — conditions under which actions must be blocked, dose-modified, or escalated to a clinician.

**1 Row =** One safety rule with trigger condition, severity level, and prescribed response.

**Executed When:** Design-time authoring; read at runtime safety gating (Stage D, Stage G).

**Input Tables (reads from):** contraindication_escalation_policy_v1.escalation_id

**Output Tables (consumed by):** contraindication_eval_trace_v1, action_contraindication_links_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| rule_id | TEXT (PK) | RULE_[A-Z0-9_]+ | RULE_NEUROPATHY_G3_BLOCK_ACTIVITY_V1 | Stable rule identifier. Must never change once published; deprecate via active=0 instead. |
| rule_label | TEXT | — | “Block moderate-vigorous activity if neuropathy grade ≥3” | Human-readable label (for audit + reporting). |
| applies_to_type | TEXT | {global, action_class, action_id} | action_class | Defines the scope of applicability. Rule: if global, apply system-wide; if action_class, apply to all actions in that cl |
| applies_to_ref | TEXT (nullable) | if action_class: {sleep, physical_activity, light_exposure, stress_regulation, nutrition, medication_support_nonrx, cogn | physical_activity | The target reference. Rules: (i) if applies_to_type=global, must be NULL; (ii) if action_class, must be one class token; |
| severity | TEXT | {hard_block, soft_penalty, require_question, escalate} | hard_block | System behavior class. Rule: hard_block removes an action from candidate schedules; soft_penalty keeps action but penali |
| condition_expression | TEXT | Deterministic DSL string | context.neuropathy_grade >= 3 | Boolean predicate evaluated against (context, feature vector, state). Must be machine-evaluable; no free-text logic. Exp |
| required_inputs_json | TEXT | JSON array of input tokens | ["context.neuropathy_grade"] | Explicit dependency list. Rule: every symbol used in condition_expression must appear here. Tokens must follow one of: c |
| unknown_input_policy | TEXT | {treat_as_false, treat_as_true, trigger_question, escalate} | trigger_question | Defines behavior if any required input is missing or unknown. Rule: for hard_block rules, recommended allowable policies |
| penalty_spec_json | TEXT (nullable) | JSON object | {"utility_penalty":0.3,"risk_penalty":0.2} | Only used when severity=soft_penalty. Rule: NULL unless severity is soft_penalty. Penalty values must be ≥0 and used onl |
| escalation_id | TEXT (nullable) | ESC_[A-Z0-9_]+ | ESC_REQUIRE_CLINICIAN_REVIEW_V1 | Only used when severity=escalate. Links to escalation policy table (optional but recommended). Rule: must be NULL unless |
| rationale | TEXT | — | “Neuropathy increases fall risk and injury risk during exertion.” | One-sentence mechanistic/safety rationale (auditable). |
| provenance | TEXT (nullable) | citation key / guideline / consensus source | “ASCO survivorship guidance; clinical consensus v1” | Evidence source for the rule. If none, mark as “clinical consensus v1” and keep conservative. |
| tags_json | TEXT (nullable) | JSON array | ["safety","neuropathy","activity"] | Optional metadata for filtering and reporting. |
| created_by | TEXT (nullable) | — | “manual_v1” | Audit only. |
| created_at | TEXT (nullable) | ISO datetime | 2026-01-18T13:10:00-08:00 | Audit only. |
| version | INTEGER | ≥1 | 1.0 | Rule version. Rule: increment only when the predicate or behavior meaning changes. |
| active | INTEGER | {0,1} | 1.0 | Soft enable/disable. Rule: never delete rows; set active=0 when deprecated. |
| notes | TEXT (nullable) | — | “Applies only during active chemo if fatigue is high.” | Sparse free text for edge cases not worth encoding. Must not contain executable logic. |

---

#### A11. `action_contraindication_links_v1`

**Purpose:** Join table linking specific actions to the safety rules that apply to them — enables action-specific safety evaluation.

**1 Row =** One link between an action and a contraindication rule that applies to it.

**Executed When:** Design-time authoring; read at runtime safety filter.

**Input Tables (reads from):** action_catalog_v1.action_id, contraindication_rules_v1.rule_id

**Output Tables (consumed by):** contraindication_eval_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| link_id | TEXT (PK) | LNK_[A-Z0-9_]+ | LNK_ACT_WALK_LOW_INT__RULE_NEUROPATHY_G3_V1 | Stable link row identifier. |
| action_id | TEXT (FK) | ACT_* | ACT_WALK_LOW_INT | Must exist in action_catalog_v1.action_id. |
| rule_id | TEXT (FK) | RULE_* | RULE_NEUROPATHY_G3_BLOCK_ACTIVITY_V1 | Must exist in contraindication_rules_v1.rule_id and be active=1 to be effective. |
| override_mode | TEXT (nullable) | {none, strengthen, weaken, disable} | none | Optional exception handling. Rule: default none. Use disable only if an action must be exempt from a class-level rule, a |
| scope_constraints_json | TEXT (nullable) | JSON object | {"treatment_phase":["active_chemo"]} | Optional extra gating for this link. Must use only canonical scope keys. |
| version | INTEGER | ≥1 | 1.0 | Link version. |
| active | INTEGER | {0,1} | 1.0 | Soft enable/disable. |
| notes | TEXT (nullable) | — | “Exempt low-intensity walking from general activity block when supervised.” | Human justification for overrides. |

---

#### A12. `contraindication_escalation_policy_v1`

**Purpose:** Defines escalation behaviors — what the system does when a contraindication trigger fires (block action, warn clinician, modify dose, refer to specialist).

**1 Row =** One escalation behavior for a contraindication severity class.

**Executed When:** Design-time authoring; read at runtime escalation handling.

**Input Tables (reads from):** None (ROOT — referenced by contraindication_rules_v1)

**Output Tables (consumed by):** contraindication_eval_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| escalation_id | TEXT (PK) | ESC_[A-Z0-9_]+ | ESC_REQUIRE_CLINICIAN_REVIEW_V1 | Stable identifier. |
| policy_label | TEXT |  | Require clinician review before recommending activity | Human label. |
| system_behavior | TEXT | {block_all_actions,block_action_classes,allow_only_low_burden,require_clinician_review} | require_clinician_review | Deterministic engine behavior. |
| allowed_action_classes_json | TEXT (JSON, nullable) | JSON array | ["sleep","stress_regulation"] | Allowed subset. |
| user_message | TEXT (nullable) |  | Symptoms indicate possible risk; consult clinician. | Output-safe message. |
| version | INTEGER | >=1 | 1 |  |
| active | INTEGER | {0,1} | 1 |  |

---

#### A13. `validation_rules_v1`

**Purpose:** Cross-table validation contracts — FK integrity checks, range constraints, cross-column consistency rules enforced at ETL commit and runtime.

**1 Row =** One validation check applicable to a specific table, column, or cross-table relationship.

**Executed When:** Design-time authoring; executed at ETL commit and runtime validation gates.

**Input Tables (reads from):** Polymorphic — each rule references the table it validates

**Output Tables (consumed by):** None (enforcement only — fails block writes)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| rule_id | TEXT (PK) | VAL_[A-Z0-9_]+ | VAL_EDGES_005 | Unique validation rule identifier. |
| rule_label | TEXT | free text | Modifier spec consistency | Human-readable description. |
| target_table | TEXT | {edges_v1,dose_bridges_v1,edge_evidence_v1,action_catalog_v1,...} | edges_v1 | Which table this rule validates. |
| target_column | TEXT (nullable) | column name | baseline_modifier_spec_json | Specific column if single-column rule. NULL for cross-column rules. |
| rule_type | TEXT | {fk_integrity,range_check,cross_column_consistency,cross_table_consistency,enum_membership,json_schema} | cross_column_consistency | Category of validation. |
| severity | TEXT | {error,warning} | error | error = blocks write; warning = logs but allows. |
| enforcement_point | TEXT | {etl_commit,runtime_read,unit_test,all} | etl_commit | When this rule is checked. |
| condition_expression | TEXT | deterministic DSL | IF baseline_modifier_mode='rule_adjust' THEN baseline_modifier_spec_json IS NOT NULL | Machine-evaluable validation predicate. |
| required_inputs_json | TEXT (JSON) | JSON array | ["baseline_modifier_mode","baseline_modifier_spec_json"] | All symbols referenced in condition. |
| error_message_template | TEXT | free text | baseline_modifier_spec_json must be non-NULL when mode=rule_adjust | Human-readable error message. |
| depends_on_tables_json | TEXT (JSON, nullable) | JSON array | ["baseline_modifier_definitions_v1"] | Other tables this rule cross-references. |
| priority | INTEGER | >=1 | 1 | Lower = checked first. |
| version | INTEGER | >=1 | 1 | Increment on semantic change. |
| active | INTEGER | {0,1} | 1 | If 0, rule is not enforced. |
| notes | TEXT (nullable) | free text | Ensures modifier FK integrity at edge compile time | No executable logic. |

> **Note:** The original DOCX had D1–D5 policy table schemas (objective_specs, safety_policies, escalation_policies, status_quo_rules, voi_rules) erroneously embedded within this table's column listing. Those schemas now appear in their correct Class D sections (§3.4).


---

#### A14. `variable_definitions_v1`

**Purpose:** Defines every patient variable that can modify edge parameters — the variable catalog backing the 109-rule effect modifier stack (§2.15).

**1 Row =** One patient characteristic that affects model predictions via multiplicative edge adjustment.

**Executed When:** Design-time authoring; read at runtime modifier resolution (Stage E).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id or derived_feature_definitions_v1.feature_id (polymorphic via source_ref_id)

**Output Tables (consumed by):** modifier_eval_trace_v1, baseline_modifier_definitions_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| variable_id | TEXT (PK) | VAR_[A-Z0-9_]+_V[0-9]+ | VAR_TREATMENT_PHASE_V1 | Stable; never reused for new meaning |
| variable_label | TEXT | free text | Treatment phase | Required |
| variable_description | TEXT | 1–2 sentences | Active chemo vs post-treatment phase used for modifier gating | Required; publication-grade |
| variable_domain | TEXT | {demographic,treatment,behavior,symptom,physiology,other} | treatment | Required |
| variable_type | TEXT | {binary,ordinal,continuous,categorical} | categorical | Required |
| allowed_values_json | TEXT (JSON) | JSON array | ["active_chemo","post_treatment","mixed","all"] | Required iff variable_type=categorical/ordinal |
| unit | TEXT (nullable) | free text | years | Required iff variable_type=continuous |
| value_range | TEXT (nullable) | deterministic string | [0,120] | Required iff variable_type=continuous |
| source_namespace | TEXT | {context,feature,node,derived} | context | Required |
| source_ref_id | TEXT (nullable) | context.<key> or FEAT_* or NODE_* | context.treatment_phase | Required unless source_namespace=derived |
| missingness_policy | TEXT | {block,ask_question,set_unknown,default} | set_unknown | Required |
| default_value | TEXT (nullable) | must be in allowed values or parseable | unknown | Required iff missingness_policy=default |
| version | INTEGER | ≥1 | 1.0 | Increment only on semantic change |
| active | INTEGER | {0,1} | 1.0 | If 0, engine must not use |
| notes | TEXT (nullable) | free text | Used for scope matching and modifier gating | No executable logic |

---

#### A15. `variable_to_input_map_v1`

**Purpose:** Maps patient intake form fields to engine variables — the translation layer between UI question responses and internal model parameters.

**1 Row =** One mapping from a patient input field name to an engine variable_id.

**Executed When:** Design-time authoring; read at runtime intake processing.

**Input Tables (reads from):** variable_definitions_v1.variable_id

**Output Tables (consumed by):** state_snapshots_v1 (initial values via intake)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| map_id | TEXT (PK) | VIM_[A-Z0-9_]+_V[0-9]+ | VIM_TREATMENT_PHASE_FROM_CONTEXT_V1 | Unique |
| variable_id | TEXT (FK) | VAR_* | VAR_TREATMENT_PHASE_V1 | Must exist in variable_definitions_v1 and active=1 |
| input_token | TEXT | context.<key> OR feature.<FEAT_ID> OR node.<NODE_ID>.(mean\|sd) | context.treatment_phase | Must match allowed namespace; machine-parseable |
| transform | TEXT | {none,clip,log,log10,zscore,bin,threshold_map} | none | Must be compatible with variable_type |
| transform_params_json | TEXT (JSON, nullable) | JSON object | {"bins":[0,50,70,120],"labels":["<50","50-70",">70"]} | Required iff transform needs params |
| precedence_rank | INTEGER | ≥1 | 1.0 | Lower = preferred if multiple maps exist for same variable |
| required_inputs_json | TEXT (JSON) | JSON array | ["context.treatment_phase"] | Must include all referenced tokens |
| missing_input_policy | TEXT | {ask_question,set_unknown,default,block} | set_unknown | Must be consistent with variable_definitions_v1 |
| default_value | TEXT (nullable) | parseable | unknown | Required iff missing_input_policy=default |
| validity_check | TEXT (nullable) | deterministic expression | value IN ["active_chemo","post_treatment"] | If fails → treat as missing |
| scope_json | TEXT (JSON, nullable) | JSON object | {"cancer_type":"breast"} | If NULL: universal |
| version | INTEGER | ≥1 | 1.0 | Increment on semantic change |
| active | INTEGER | {0,1} | 1.0 | If 0, ignore row |
| notes | TEXT (nullable) | free text | Use intake context first; fallback to clinician form | No executable logic |

---

#### A16. `baseline_modifier_definitions_v1`

**Purpose:** Defines how specific patient variables multiplicatively adjust edge parameters — modifier functions with evidence grades (A/B/C/D) and guardrails [0.5, 2.0] (§2.15).

**1 Row =** One modifier definition specifying how a variable shifts an edge parameter, with evidence grade and bounds.

**Executed When:** Design-time authoring; read at runtime before simulation (Stage E).

**Input Tables (reads from):** variable_definitions_v1.variable_id (via required_variable_ids_json), edge_evidence_v1.ler_id (via source_ler_ids)

**Output Tables (consumed by):** modifier_eval_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| modifier_id | TEXT (PK) | MOD_[A-Z0-9_]+_V[0-9]+ | MOD_ACTIVE_CHEMO_DAMPEN_BETA_V1 | Stable; never reused |
| modifier_label | TEXT | free text | Active chemo dampens exercise→fatigue benefit | Required |
| modifier_description | TEXT | 1–2 sentences | Reduces magnitude of beta when treatment_phase is active_chemo | Required |
| support_class | TEXT | {quantitative,gate_only,variance_only} | gate_only | Required |
| evidence_required | INTEGER | {0,1} |  | Must be 1 if support_class=quantitative |
| source_ler_ids | TEXT (nullable) | semicolon LER IDs | LER_XYZ_001 | Required iff evidence_required=1 |
| required_variable_ids_json | TEXT (JSON) | JSON array of VAR_* | ["VAR_TREATMENT_PHASE_V1"] | Must all exist and active=1 |
| applies_to | TEXT | {beta,lag,half_life,gate} | beta | Required |
| parameterization_mode | TEXT | {multiplicative,additive,set_to,delta_steps} | multiplicative | Must be compatible with applies_to |
| effect_spec_json | TEXT (JSON) | JSON object | {"when":{"VAR_TREATMENT_PHASE_V1":"active_chemo"},"multiplier":0.7} | Must be machine-evaluable; no prose |
| bounds_json | TEXT (JSON, nullable) | JSON object | {"multiplier_min":0.5,"multiplier_max":1.0} | Required for quantitative |
| missing_input_policy | TEXT | {ask_question,set_unknown,no_effect,block} | no_effect | Required |
| conflict_input_policy | TEXT | {prefer_state,prefer_feature,inflate_uncertainty,no_effect} | inflate_uncertainty | Required |
| scope_json | TEXT (JSON, nullable) | JSON object | {"cancer_type":"breast"} | If NULL: universal |
| version | INTEGER | ≥1 | 1.0 | Increment on semantic change |
| active | INTEGER | {0,1} | 1.0 | If 0, ignore |
| notes | TEXT (nullable) | free text | Use gate_only until interaction evidence exists | No executable logic |

---

#### A17. `derived_feature_definitions_v1`

**Purpose:** Defines every computed feature — formulas, dependency chains, normalization references, and timing windows for derived clinical variables used in state estimation.

**1 Row =** One computed feature with its formula, dependency DAG, normalization reference, and observation noise specification.

**Executed When:** Design-time authoring; read at runtime feature computation (Stage A) and triangulation (Stage B).

**Input Tables (reads from):** normalization_refs_v1.norm_id, observation_noise_v1.noise_id, self-ref via dependency_ids

**Output Tables (consumed by):** state_snapshots_v1, triangulation_members_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| feature_id | TEXT (PK) | FEAT_[A-Z0-9_]+_V[0-9]+ | FEAT_SLEEP_FATIGUE_DISCREP_V1 | Stable feature definition ID. |
| feature_label | TEXT | free text | Sleep–Fatigue Discrepancy Score | Human-readable name. |
| feature_description | TEXT | 1–2 sentences | Relative fatigue burden compared to reported sleep disturbance (difference of standardized scores). | Publishable scientific definition. |
| maps_to_node | TEXT (FK) | node_id or NULL | NULL | Only if the feature represents a single node state. Otherwise NULL. |
| mapped_nodes_json | TEXT | JSON array of node_id | ["S_SLEEP_DISRUPTION","F_FATIGUE"] | Tagging for multi-construct diagnostics (NOT dependency inputs). |
| feature_domain | TEXT | {demographic,treatment,behavior,symptom,perception,physiology,immune,neuro,biomarker,outcome,diagnostic,qa,other} | diagnostic | Organization domain. |
| feature_role | TEXT | {state_input,state_estimation,prediction,recommendation,diagnostic,qa} | diagnostic | Prevents misuse downstream. |
| feature_type | TEXT | {status,composite,interaction,trend,variability,flag,quality_metric,cluster_code,other} | composite | Mathematical shape. |
| feature_source | TEXT | {observed_only,derived_only,hybrid} | observed_only | Guards against circular dependencies. |
| dependency_ids | TEXT | semicolon-separated IDs | PSQI_TOTAL;MFSI_TOTAL | Required upstream identifiers. |
| dependency_types | TEXT | semicolon-separated {instrument,measure,feature,node} | instrument;instrument | Must align 1:1 with dependency_ids. |
| time_window | TEXT | {momentary,daily,weekly,monthly,study_window,custom} | custom | Output time resolution. |
| time_window_spec | TEXT | free text | PSQI=P30D; MFSI=P7D (mismatch captured intentionally). | Only if needed. |
| normalization_method | TEXT | {none,within_user,within_study,external_norm} | external_norm | Scaling method. |
| normalization_reference | TEXT | NORM_* key or rule key | NORM_CANCER_SURVIVORS_50_70 | Deterministic reference definition. |
| formula_spec | TEXT | deterministic pseudo-formula | z(MFSI_TOTAL\|ref=NORM_CANCER_SURVIVORS_50_70) - z(PSQI_TOTAL\|ref=NORM_CANCER_SURVIVORS_50_70) | Implementable computation rule (no prose). |
| sign_alignment | TEXT | {as_is,flip_to_match_node,custom} | as_is | Sign handling (relevant when maps_to_node not NULL). |
| directionality | TEXT | {higher_worse,higher_better,neutral,context} | context | Meaning after normalization/sign. |
| output_scale | TEXT | {z,raw,0_1,ordinal,count,minutes,probability,text,other} | z | Output type. |
| output_unit | TEXT | free text | z | Unit label. |
| valid_range | TEXT | string | (-inf,inf) | Guardrails. |
| threshold_spec | TEXT | deterministic expression | NULL | Only for flag/ordinal features. |
| missingness_policy | TEXT | {drop_row,feature_impute,row_impute,set_null} | feature_impute | Deterministic missingness behavior. |
| imputation_spec | TEXT | deterministic method string | median_within_study (only if pre-specified; otherwise set_null) | Only if imputing. |
| compute_priority | TEXT | {core,optional,experimental} | optional | Execution priority. |
| compute_stage | TEXT | {intake,preprocess,state_estimation,postprocess,qa} | preprocess | Pipeline stage. |
| version | INTEGER | ≥1 | 1.0 | Version counter. |
| active | INTEGER | {0,1} | 1.0 | Enable/disable. |
| notes | TEXT | free text | Interpret as mismatch; do not treat as fatigue magnitude. | Caveats. |

> **Note:** The original DOCX had normalization_refs_v1 (A24) and observation_noise_v1 (A25) column schemas erroneously embedded at the end of this table's column listing. Those schemas now appear in their correct sections.


---

#### A18. `triangulation_sets_v1`

**Purpose:** Defines which measurements should be fused for each latent construct — the configuration table for Stage B triangulation and within-construct conflict quantification.

**1 Row =** One triangulation group specifying which signals estimate the same latent construct.

**Executed When:** Design-time authoring; read at runtime fusion (Stage B) and adaptive questioning (Stage H).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id (target_node_id), derived_feature_definitions_v1.feature_id (output_feature_id)

**Output Tables (consumed by):** state_snapshots_v1 (fused estimates)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| triangulation_id | TEXT (PK) | TRI_[A-Z0-9_]+ | TRI_SLEEP_DISRUPTION_V1 | Reusable triangulation set ID. |
| triangulation_label | TEXT | — | Sleep disruption triangulation | Human label. |
| target_node_id | TEXT (FK) | NODE_* | NODE_SLEEP_DISRUPTION | Node being triangulated. FK → biomarker_node_definitions_v1.node_id. |
| triangulation_scope | TEXT | {within_construct} | within_construct | Guardrail: within-construct only. |
| triangulation_goal | TEXT | {state_estimation, qa, both} | both | Whether fusion is produced or only QA/conflict. |
| fusion_policy | TEXT | {none, weighted_average, gaussian_precision_fusion, rule_based} | gaussian_precision_fusion | Deterministic fusion method. Prefer none or gaussian_precision_fusion (deterministic) for v1. |
| conflict_policy | TEXT | {flag_only, recommend_downweight, block_update} | recommend_downweight | What Stage 2 outputs. Stage 2 does not inflate σ; Stage 3 does. |
| conflict_metric | TEXT | {weighted_dispersion, sign_disagreement, both} | both | How conflict_score is computed. |
| min_members_required | INTEGER | >=1 | 1.0 | If fewer admissible members than this, triangulation returns coverage=none. |
| output_feature_id | TEXT (nullable FK) | FEAT_* | FEAT_SLEEP_TRI_FUSED_V1 | If you materialize a fused feature. NULL if fusion is internal only. |
| version | INTEGER | >=1 | 1.0 | Version. |
| active | INTEGER | {0,1} | 1.0 | Enable flag. |
| notes | TEXT | — | PSQI + diary; wearable later | Notes. |

---

#### A19. `triangulation_members_v1`

**Purpose:** Defines which variables belong to each triangulation set — membership list with weights and reliability for multi-signal fusion.

**1 Row =** One member variable in a triangulation set with its fusion weight.

**Executed When:** Design-time authoring; read at runtime fusion (Stage B).

**Input Tables (reads from):** triangulation_sets_v1.triangulation_id, derived_feature_definitions_v1.feature_id or measure_definitions_v1.measure_id (polymorphic)

**Output Tables (consumed by):** None (consumed in-memory by TriangulationEngine)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| triangulation_id | TEXT (PK part, FK) | TRI_* | TRI_SLEEP_DISRUPTION_V1 | Join to set. |
| member_order | INTEGER (PK part) | >=1 | 1.0 | Stable deterministic ordering. |
| member_entity_type | TEXT | {feature} | feature | v1: feature only. |
| member_entity_id | TEXT | FEAT_* | FEAT_PSQI_TOTAL_Z_V1 | Feature ID. |
| member_role | TEXT | {primary, secondary, auxiliary} | primary | Optional tag. |
| weight_kind | TEXT | {auto_equal, manual_weight, inverse_variance, reliability_prior, none} | inverse_variance | How Stage 2 produces recommended weights. |
| weight_value | REAL (nullable) | — | 0.6 | Used only when weight_kind=manual_weight or reliability_prior. |
| required_for_tri_set | INTEGER | {0,1} |  | If 1 and missing, set coverage=none (use sparingly). |
| admissibility_qc_gate | TEXT (nullable) | {allow, require_qc_pass} | require_qc_pass | If require_qc_pass, member is excluded when Stage 1 QC flags indicate failure. |
| notes | TEXT | — | PSQI broad; diary day-to-day | Notes. |

---

#### A20. `description_templates_v1`

**Purpose:** Text templates for consistent UI rendering of recommendations, warnings, severity descriptions, and clinical reports (Stage I).

**1 Row =** One text template for a specific output context (recommendation, warning, severity label).

**Executed When:** Design-time authoring; read at runtime report generation (Stage I).

**Input Tables (reads from):** None

**Output Tables (consumed by):** None (consumed by UI renderer)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| template_id | TEXT (PK) | TPL_[A-Z0-9_]+ | TPL_NODE_DESC_V1 | Stable identifier. |
| template_label | TEXT | free text | Node description template | Human label. |
| template_scope | TEXT | {node,edge,action,instrument,measure,feature,...} | edge | What entity type. |
| template_text | TEXT |  | {{label}} (method={{method}})... | Template with placeholders. |
| version | INTEGER | >=1 | 1 |  |
| active | INTEGER | {0,1} | 1 |  |

---

#### A21. `action_catalog_v1`

**Purpose:** Defines every atomic intervention the engine may recommend — dose domains, burden priors, adherence priors, and evidence basis. The central intervention reference table.

**1 Row =** One atomic action the engine may recommend, with its dose domain [min, max, step], burden priors, and adherence prior.

**Executed When:** Design-time authoring; read at runtime candidate generation (Stage D) and optimization (Stage G).

**Input Tables (reads from):** None (ROOT — referenced by scenario_items, schedule_items, dose_bridges, status_quo_rules, intervention_kernels, intervention_synergy, and more)

**Output Tables (consumed by):** scenario_items_v1, schedule_items_v1, decision_trace_v1, contraindication_eval_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| action_id | TEXT (PK) | ACT_[A-Z0-9_]+ | ACT_LIGHT_AM | Never reused for a different meaning. |
| action_label | TEXT | free text | Morning light exposure | UI-only; no logic. |
| action_class | TEXT | {sleep, physical_activity, light_exposure, stress_regulation, nutrition, medication_support_nonrx, cognitive_training, s | light_exposure | Must be one token. |
| dose_type | TEXT | {continuous, ordinal, binary} | continuous | If binary: dose_unit may be NULL and bounds must be [0,1]. |
| dose_unit | TEXT (nullable) | free text | minutes | Required if dose_type ∈ {continuous, ordinal}. |
| dose_semantics | TEXT | free text | Minutes of outdoor light within 2 hours of waking | Must be consistent with unit and class. |
| dose_min | REAL | ≥0 |  | Must be ≤ dose_max. |
| dose_max | REAL | ≥0 | 30.0 | Must be ≥ dose_min. |
| dose_recommended_start | REAL | — | 10.0 | Must satisfy dose_min ≤ start ≤ dose_max. |
| dose_step | REAL (nullable) | >0 | 5.0 | If present, should discretize [min,max] reasonably. |
| time_cost_min_default | REAL | ≥0 | 10.0 | Non-negative. |
| cognitive_load_default | REAL | [0,1] | 0.2 | Clamp to [0,1] at validation. |
| logistics_load_default | REAL | [0,1] | 0.3 | Clamp to [0,1] at validation. |
| overall_burden_default | REAL | [0,1] | 0.25 | If NULL, compute as mean(cognitive,logistics) after clamping. |
| adherence_rate_default | REAL | [0,1] | 0.7 | If NULL, enforce global conservative default (declared in objective_specs_v1). |
| evidence_basis | TEXT | {direct_intervention, mechanistic_only, guideline_derived, mixed} | guideline_derived | Do not label direct_intervention unless supported by intervention evidence. |
| evidence_strength | TEXT | {strong, moderate, weak} | moderate | Human-auditable label. |
| notes | TEXT (nullable) | free text | Prefer outdoor light; avoid late evening | No executable logic. |
| version | INTEGER | ≥1 | 1.0 | Increment only when semantics change. |
| active | INTEGER | {0,1} | 1.0 | If 0: must not be used at runtime. |

---

#### A22. `question_bank_v1`

**Purpose:** Defines every question the adaptive intake system can ask — with VOI relevance parameters, observation model links, skip logic, and presentation metadata.

**1 Row =** One question the system can ask, with its information value parameters and observation model mapping.

**Executed When:** Design-time authoring; read at runtime adaptive questioning (Stage H).

**Input Tables (reads from):** question_observation_models_v1.model_id, observation_noise_v1.noise_id

**Output Tables (consumed by):** question_sequence_v1, question_selection_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| question_id | TEXT (PK) | Q_[A-Z0-9_]+ | Q_SLEEP_PSQI_TOTAL_V1 | Unique; never reused for a different meaning. |
| question_label | TEXT | free text | PSQI total score | UI label only. |
| question_text | TEXT | free text | “In the past month, how would you rate your overall sleep quality?” | Must be safe, non-diagnostic phrasing. |
| question_role | TEXT | {safety_gate, baseline_intake, adaptive_profile, monitoring, calibration} | adaptive_profile | Stage 8 selection uses this field for gating and prioritization. |
| answer_type | TEXT | {binary, ordinal, integer, real, multi_select, text, date, time} | integer | Determines storage/validation behavior. |
| answer_unit | TEXT (nullable) | free text | points | Required if answer_type ∈ {integer, real}. |
| answer_options_json | TEXT (JSON, nullable) | JSON array/object | {"levels":[0,1,2,3]} | Required iff answer_type ∈ {ordinal, multi_select}. NULL otherwise. |
| validation_min | REAL (nullable) | — |  | Required for numeric types when bounded. |
| validation_max | REAL (nullable) | — | 21.0 | Required for numeric types when bounded. |
| validation_rule_spec | TEXT (nullable) | deterministic DSL string | value % 1 == 0 | Must be machine-evaluable; no prose logic. |
| maps_to_type | TEXT | {context_key, feature_id, node_id, variable_id} | feature_id | Exactly one target type per question. |
| maps_to_ref | TEXT | ID or key | FEAT_PSQI_TOTAL_Z_V1 | If maps_to_type=feature_id must exist in derived_feature_definitions_v1; if node_id must exist in biomarker_node_definit |
| observation_model_id | TEXT (nullable) | QOM_[A-Z0-9_]+ | QOM_PSQI_TO_SLEEP_DISRUPTION_V1 | Required when maps_to_type ∈ {feature_id, node_id} and the answer must be converted into z-space with noise; NULL allowe |
| time_window | TEXT | {momentary, daily, weekly, monthly, study_window, custom} | monthly | Must align with the construct definition and downstream feature windowing. |
| time_window_spec | TEXT (nullable) | deterministic string | P30D | Required iff time_window=custom. |
| applicability_scope_json | TEXT (JSON, nullable) | JSON object | {"treatment_phase":["post_treatment"],"cancer_type":["breast","all"]} | Used only for applicability filtering; canonical scope keys only. |
| prerequisite_inputs_json | TEXT (JSON, nullable) | JSON array | ["context.cancer_type","context.treatment_phase"] | Every prerequisite symbol must be canonical. |
| missing_answer_policy | TEXT | {skip, retry, set_unknown, escalate} | set_unknown | Must be deterministic and consistent with Stage 8 stopping rules. |
| burden_time_min | REAL | ≥0 | 2.0 | Non-negative. |
| burden_cognitive | REAL | [0,1] | 0.3 | Clamp to [0,1] at validation. |
| burden_invasiveness | REAL | [0,1] |  | 0 for self-report; >0 for tests. |
| ask_frequency_policy | TEXT | {once, periodic, on_change, custom} | once | If custom, define in ask_frequency_spec. |
| ask_frequency_spec | TEXT (nullable) | deterministic string | FREQ=WEEKLY | Required iff ask_frequency_policy=custom. |
| provenance | TEXT (nullable) | free text | “FACT-Cog v3 item bank; v1 subset.” | Citation key or source note; no clinical claims. |
| version | INTEGER | ≥1 | 1.0 | Increment only when semantics change. |
| active | INTEGER | {0,1} | 1.0 | If 0, question is not selectable. |
| notes | TEXT (nullable) | free text | “Use only if baseline sleep stream absent.” | No executable logic. |

> **Note:** The original DOCX had question_observation_models_v1 (A23) column schema erroneously embedded at the end of this table's column listing. That schema now appears in its correct section.


---

#### A23. `question_observation_models_v1`

**Purpose:** Maps question answers to node/feature updates — the observation model connecting the adaptive questionnaire to Bayesian state estimation.

**1 Row =** One answer→feature/node update mapping specifying how a response changes model beliefs.

**Executed When:** Design-time authoring; read at runtime answer processing (within Stage H → C loop).

**Input Tables (reads from):** question_bank_v1.question_id, derived_feature_definitions_v1.feature_id or biomarker_node_definitions_v1.node_id (polymorphic)

**Output Tables (consumed by):** state_snapshots_v1 (updated beliefs)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| model_id | TEXT (PK) | QOM_[A-Z0-9_]+ | QOM_PSQI_TO_SLEEP_DISRUPTION_V1 | Stable observation model ID. |
| question_id | TEXT (FK) | Q_* | Q_SLEEP_PSQI_TOTAL_V1 | Source question. |
| output_type | TEXT | {feature,node} | feature | What gets updated. |
| output_ref_id | TEXT | FEAT_* or NODE_* | FEAT_PSQI_TOTAL_Z_V1 | Target. |
| transform_spec | TEXT | deterministic expression | zscore(value, norm_ref) | How answer becomes feature value. |
| noise_spec_json | TEXT (JSON) | JSON object | {"sd":0.5} | Observation noise for this channel. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |
| notes | TEXT (nullable) |  |  |  |

---

#### A24. `normalization_refs_v1`

**Purpose:** Population reference statistics (mean, SD, percentiles) for z-score normalization of instruments, measures, and derived features. Enables the z-score standardization described in §2.1.

**1 Row =** One population reference statistic set for normalizing one measurement entity to z-score units.

**Executed When:** Design-time authoring; read at runtime feature normalization (Stage A) and dose bridging (Stage F).

**Input Tables (reads from):** instrument_definitions_v1 or measure_definitions_v1 or derived_feature_definitions_v1 (polymorphic via target_entity_id)

**Output Tables (consumed by):** state_snapshots_v1 (normalized features)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| norm_id (PK) | TEXT (PK) | NORM_[A-Z0-9_]+ | NORM_PSQI_TOTAL_CANCER | Globally unique. Never reused. | Stable identifier for this normalization reference. |
| target_entity_type | ENUM | {instrument, measure, feature} | instrument | Determines which parent table target_entity_id references. | Type discriminator for polymorphic FK. |
| target_entity_id (FK → polymorphic) | TEXT (FK) | INST_*/MEAS_*/FEAT_* | INST_PSQI_TOTAL | Must exist in table indicated by target_entity_type. | Which entity this norm applies to. |
| population_label | TEXT | free text | Breast cancer post-chemo female 45-65 | NOT NULL. Describes reference population. | Human-readable population description. |
| cancer_type | ENUM | {breast, lung, colorectal, hematological, mixed_solid, general_population, any} | breast | Must be valid cancer type. | Cancer type of reference population. |
| treatment_phase | ENUM | {pre_treatment, during_treatment, early_post, late_post, survivorship, any} | early_post | Must be valid phase. | Treatment phase of reference population. |
| ref_mean | REAL | any numeric | 8.2 | NOT NULL. Population mean in raw score units. | Reference mean for z-score computation. |
| ref_sd | REAL | >0 | 3.4 | NOT NULL. Must be positive. | Reference SD for z-score computation. |
| ref_n | INTEGER | ≥1 | 245 | NOT NULL. Sample size of reference. | Reference sample size for confidence. |
| percentile_5 | REAL (nullable) | any numeric | 2.1 | If present: p5 < p25 < p50 < p75 < p95. | 5th percentile of reference distribution. |
| percentile_25 | REAL (nullable) | any numeric | 5.5 | See percentile_5. | 25th percentile. |
| percentile_50 | REAL (nullable) | any numeric | 8.0 | See percentile_5. | Median of reference distribution. |
| percentile_75 | REAL (nullable) | any numeric | 10.8 | See percentile_5. | 75th percentile. |
| percentile_95 | REAL (nullable) | any numeric | 14.2 | See percentile_5. | 95th percentile. |
| source_study_id (FK → study_registry_v1) | TEXT (FK) | STUDY_* | STUDY_BUYSSE_1989 | Must exist in study_registry_v1 if provided. | Source citation for these norms. |
| source_citation | TEXT | free text | Buysse et al., 1989, J Clin Psychiatry | NOT NULL. Human-readable provenance. | Publication reference for auditability. |
| year_published | INTEGER | 1950-2026 | 1989 | Plausible year. | For freshness weighting (Layer 7). |
| is_cancer_specific | INTEGER | {0, 1} | 1 | 1 if normed on cancer population. | Flags cancer-validated norms (§2.7 SE multiplier). |
| version | INTEGER | ≥1 | 1 | Increment on semantic change. | Schema versioning. |
| notes | TEXT (nullable) | free text | Cancer-specific norms from CANTO cohort | No executable logic. | Implementation notes. |

---

#### A25. `observation_noise_v1`

**Purpose:** Measurement noise and reliability parameters for all measurement entities. Implements σ²_y = b²(1−α)/α from §2.7 and the cancer-validation SE multipliers.

**1 Row =** One noise/reliability specification for one measurement entity (instrument, measure, feature, or question).

**Executed When:** Design-time authoring; read at runtime Bayesian state estimation (Stages A/B/C) for observation weighting.

**Input Tables (reads from):** instrument_definitions_v1 or measure_definitions_v1 or derived_feature_definitions_v1 or question_bank_v1 (polymorphic)

**Output Tables (consumed by):** state_snapshots_v1 (precision-weighted updates)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| noise_id (PK) | TEXT (PK) | NOISE_[A-Z0-9_]+ | NOISE_PSQI_TOTAL | Globally unique. | Stable identifier for this noise spec. |
| target_entity_type | ENUM | {instrument, measure, feature, question} | instrument | Type discriminator for polymorphic FK. | Which kind of entity this noise applies to. |
| target_entity_id (FK → polymorphic) | TEXT (FK) | INST_*/MEAS_*/FEAT_*/Q_* | INST_PSQI_TOTAL | Must exist in table indicated by target_entity_type. | The entity whose noise is specified. |
| reliability_alpha | REAL (nullable) | [0,1] | 0.83 | Cronbach's alpha or test-retest ICC. | For noise derivation: σ²_y = b²(1−α)/α. |
| noise_variance | REAL | >0 | 0.205 | NOT NULL. Precomputed σ²_y. | Observation noise in standardized units. |
| noise_source | ENUM | {psychometric, test_retest, icc, estimated, default} | psychometric | Tracks derivation method. | Provenance of noise estimate. |
| cancer_validation_status | ENUM | {validated_cancer, used_cancer, general_population, known_somatic_confound} | used_cancer | Determines SE multiplier (§2.7). | Cancer-specific validation level. |
| se_multiplier | REAL | {1.0, 1.15, 1.3, 1.5} | 1.15 | Derived from cancer_validation_status. | Measurement invariance SE inflation (§2.7). |
| proxy_r_squared | REAL (nullable) | [0,1] | 0.42 | For biomarkers: peripheral-to-central R². | Proxy validity for latent variable inference (§2.17). |
| proxy_caveat | TEXT (nullable) | free text | Decouples under neuroinflammation | Document known limitations. | Clinical caveats for proxy interpretation. |
| source_study_id (FK → study_registry_v1) | TEXT (FK) | STUDY_* | STUDY_KLEIN_2011 | Must exist if provided. | Source citation for reliability data. |
| source_citation | TEXT | free text | Klein et al., 2011, Int J Neuropsychopharmacol | NOT NULL. | Human-readable provenance. |
| condition_dependent | INTEGER | {0, 1} | 1 | 1 if noise changes under certain conditions. | Flags context-dependent noise (e.g., BDNF + inflammation). |
| condition_description | TEXT (nullable) | free text | If neuroinflammation elevated: multiply SE by 1.3 | Required if condition_dependent=1. | Describes conditional noise adjustment. |
| version | INTEGER | ≥1 | 1 | Increment on semantic change. | Schema versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: not used at runtime. | Soft disable. |
| notes | TEXT (nullable) | free text | BDNF proxy validity uncertain in humans | No executable logic. | Implementation notes. |

---

#### A26. `pathways_v1`

**Purpose:** Defines the 15 mechanistic + 5 clinical mediator pathways from §2.3 — multi-edge chain structures used for synergy computation, pathway activation detection, and clinical reporting.

**1 Row =** One biological/behavioral pathway with its node chain, evidence tier, and cognitive domain specificity.

**Executed When:** Design-time authoring; read by algorithm pathway reasoning (ALG-A) and synergy computation (Stage G).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id (via JSON arrays), edge_relations_definitions_v1.edge_relation_id (via JSON array)

**Output Tables (consumed by):** pathway_biomarkers_v1, pathway_interactions_v1, intervention_synergy_v1

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| pathway_id (PK) | TEXT (PK) | PW_[A-Z0-9_]+ | PW_NEUROINFLAMMATION | Globally unique. Matches paper §2.3. | Stable pathway identifier. |
| pathway_label | TEXT | free text | Neuroinflammation | NOT NULL. | Human-readable name. |
| tier | ENUM | {mechanistic_model_implied, mechanistic_emerging, mechanistic_placeholder, clinical_mediator} | mechanistic_model_implied | Maps to paper §2.3.1–2.3.2. | Evidence maturity classification. |
| entry_node_ids_json | JSONB | Array of NODE_* | ["NODE_IL6", "NODE_TNF_ALPHA"] | Every element must exist in biomarker_node_definitions_v1. | Upstream entry points into this pathway. |
| exit_node_ids_json | JSONB | Array of NODE_* | ["NODE_PROCESSING_SPEED", "NODE_MEMORY"] | Every element must exist in biomarker_node_definitions_v1. | Downstream cognitive targets of this pathway. |
| intermediate_node_ids_json | JSONB | Array of NODE_* | ["NODE_MICROGLIAL_ACTIVATION"] | Every element must exist in biomarker_node_definitions_v1. | Latent intermediate nodes in the chain. |
| edge_relation_ids_json | JSONB | Array of ER_* | ["ER_A_IL6__NEUROINFLAM"] | Every element must exist in edge_relations_definitions_v1. | Edges comprising this pathway chain. |
| cognitive_domain_specificity_json | JSONB | Object: {domain: weight} | {"processing_speed": 0.8, "memory": 0.6} | Weights in [0,1]. Maps to §2.3.3. | Pathway-domain specificity matrix entry. |
| best_proxy_biomarker | TEXT (nullable) | NODE_* | NODE_IL6 | Must exist in biomarker_node_definitions_v1. | Best peripheral proxy for pathway activation. |
| proxy_r_squared | REAL (nullable) | [0,1] | 0.50 | R² between proxy and latent pathway state. | Proxy validity (§2.17). |
| causal_evidence_level | ENUM | {causal_demonstrated, strong_association, moderate_association, plausible} | causal_demonstrated | Based on paper §2.3 evidence summaries. | Strength of causal evidence for this pathway. |
| key_citation | TEXT | free text | Acharya et al., 2016, Sci Rep | NOT NULL. | Primary evidence citation. |
| version | INTEGER | ≥1 | 1 | Increment on semantic change. | Schema versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: pathway excluded from analysis. | Soft disable. |
| notes | TEXT (nullable) | free text | Most robustly supported CRCI mechanism | No executable logic. | Implementation notes. |

---

#### A27. `pathway_interactions_v1`

**Purpose:** Defines interactions between pathway pairs — feed-forward loops, convergence points, and antagonistic relationships relevant to cross-pathway reasoning.

**1 Row =** One interaction between two pathways specifying type (feed-forward, convergent, antagonistic), strength, and directionality.

**Executed When:** Design-time authoring; read by cross-pathway reasoning (ALG-A PathwayEngine).

**Input Tables (reads from):** pathways_v1.pathway_id (pathway_a_id, pathway_b_id)

**Output Tables (consumed by):** None (consumed in-memory by synergy engine)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| interaction_id (PK) | TEXT (PK) | PINT_[A-Z0-9_]+ | PINT_INFLAM_OXIDATIVE | Globally unique. | Stable interaction identifier. |
| pathway_a_id (FK → pathways_v1) | TEXT (FK) | PW_* | PW_NEUROINFLAMMATION | Must exist. pathway_a_id < pathway_b_id. | First pathway in interaction. |
| pathway_b_id (FK → pathways_v1) | TEXT (FK) | PW_* | PW_OXIDATIVE_STRESS | Must exist. | Second pathway in interaction. |
| interaction_type | ENUM | {feed_forward, convergent, antagonistic, independent} | feed_forward | NOT NULL. | Nature of pathway interaction. |
| interaction_strength | REAL | [0,1] | 0.75 | 0=independent, 1=fully coupled. | Quantified interaction magnitude. |
| directionality | ENUM | {bidirectional, a_to_b, b_to_a} | bidirectional | NOT NULL. | Direction of cross-pathway influence. |
| shared_nodes_json | JSONB (nullable) | Array of NODE_* | ["NODE_NF_KB"] | Nodes where pathways converge. | Convergence points. |
| mechanism_description | TEXT | free text | ROS activates NF-κB → cytokine release; TNF-α generates further ROS | NOT NULL. | Mechanistic explanation of interaction. |
| key_citation | TEXT | free text | Torre et al., 2021 | NOT NULL. | Evidence source. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: not used. | Soft disable. |
| notes | TEXT (nullable) | free text | Bidirectional feed-forward loop with neuroinflammation | No executable logic. | Implementation notes. |

---

#### A28. `intervention_synergy_v1`

**Purpose:** Defines pairwise intervention interaction records — JPO, CCS, interaction type, and γ prior parameters from §2.16.1. Maps to paper's synergy_registry.csv (15 records).

**1 Row =** One pairwise interaction between two interventions with synergy metrics and empirical validation status.

**Executed When:** Design-time authoring; read at runtime bundle optimization (Stage G).

**Input Tables (reads from):** action_catalog_v1.action_id (action_a_id, action_b_id), study_registry_v1.study_id

**Output Tables (consumed by):** decision_trace_v1 (synergy-adjusted SAFE scores)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| synergy_id (PK) | TEXT (PK) | SYN_[A-Z0-9_]+ | SYN_EXERCISE_SLEEP | Globally unique. | Stable synergy record identifier. |
| action_a_id (FK → action_catalog_v1) | TEXT (FK) | ACT_* | ACT_AEROBIC_MODERATE | Must exist in action_catalog_v1. | First intervention in the pair. |
| action_b_id (FK → action_catalog_v1) | TEXT (FK) | ACT_* | ACT_SLEEP_HYGIENE | Must exist. action_a_id < action_b_id (canonical order). | Second intervention in the pair. |
| jpo | REAL | [0,1] | 0.18 | Jaccard Pathway Overlap. 0=disjoint, 1=identical. | Mechanistic redundancy (§2.16.1). |
| ccs | REAL | [0,1] | 0.82 | (1-JPO) × shared_convergence_indicator. | Convergent Complementarity Score (§2.16.1). |
| interaction_type | ENUM | {synergistic, additive, antagonistic} | synergistic | Classification from factorial/combination evidence. | Direction of interaction. |
| interaction_magnitude | REAL (nullable) | any numeric | 0.15 | Excess effect beyond additive expectation (SMD units). | Quantified interaction effect. |
| gamma_prior_alpha | REAL | >0 | 2.0 | Beta distribution alpha for γ (§2.16.1). | Synergy coefficient prior shape. |
| gamma_prior_beta | REAL | >0 | 4.0 | Beta distribution beta for γ. | Synergy coefficient prior shape. |
| gamma_cap | REAL | [0,1] | 0.40 | Maximum γ scaling (§2.16.1). | Synergy ceiling. |
| source_study_id (FK → study_registry_v1) | TEXT (FK) | STUDY_* | STUDY_EXCEL_2023 | Must exist if from factorial trial. | Evidence source. |
| validation_status | ENUM | {validated, partially_validated, not_tested} | partially_validated | Tracks empirical confirmation. | Confidence in synergy prediction. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| notes | TEXT (nullable) | free text | Highest CCS pair; exercise targets inflammation while sleep targets glymphatic | No executable logic. | Implementation notes. |

---

#### A29. `recovery_trajectories_v1`

**Purpose:** Defines natural recovery parameters per treatment context — stretched exponential parameters (r∞, τR, γR) and accelerated cognitive aging coefficients from §2.18.

**1 Row =** One treatment-context-specific recovery trajectory with stretched exponential parameters and ACC factor.

**Executed When:** Design-time authoring; read at runtime temporal prediction (Stage F, ALG-E).

**Input Tables (reads from):** None (self-contained — context-matched by cancer_type + regimen_class)

**Output Tables (consumed by):** simulation_trace_v1 (trajectory predictions)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| trajectory_id (PK) | TEXT (PK) | TRAJ_[A-Z0-9_]+ | TRAJ_BREAST_ANTHRACYCLINE | Globally unique. | Stable trajectory identifier. |
| cancer_type | ENUM | {breast, colorectal, hematological, lung, any} | breast | NOT NULL. | Cancer type for context matching. |
| regimen_class | TEXT | free text | anthracycline-based | NOT NULL. | Treatment regimen classification. |
| r_infinity | REAL | [0,1] | 0.70 | NOT NULL. Asymptotic recovery fraction. | Fraction of deficit that eventually recovers (§2.18.1). |
| r_infinity_se | REAL | >0 | 0.10 | Uncertainty in r_infinity. | For MC sampling of recovery parameters. |
| tau_r_months | REAL | >0 | 8.0 | NOT NULL. Recovery time constant. | Speed of recovery in months (§2.18.1). |
| tau_r_se | REAL | >0 | 2.0 | Uncertainty in tau_r. | For MC sampling. |
| gamma_r | REAL | >0 | 0.8 | Shape parameter. <1=rapid-then-slow, =1=standard, >1=delayed. | Stretched exponential shape (§2.18.1). |
| acc_factor | REAL | ≥1.0 | 2.0 | Accelerated Cognitive aging Coefficient. | Treatment-specific aging acceleration (§2.18.2). |
| source_citation | TEXT | free text | Whittaker et al., 2022, Sci Rep | NOT NULL. | Evidence source. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| notes | TEXT (nullable) | free text | Anthracyclines show 23-26yr equivalent senescence acceleration | No executable logic. | Implementation notes. |

---

#### A30. `biomarker_correlations_v1`

**Purpose:** Defines correlated mediator pairs with empirical ρ for the block-diagonal D matrix (§2.6, §2.17.2). Maps to paper's correlation_registry.csv (8 records).

**1 Row =** One correlated biomarker pair with empirical ρ, D-matrix block assignment, and decision-criticality flag.

**Executed When:** Design-time authoring; read at build-time precision matrix construction (ALG-C).

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id (node_a_id, node_b_id)

**Output Tables (consumed by):** edges_v1 (implied precision matrix Λ)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| correlation_id (PK) | TEXT (PK) | CORR_[A-Z0-9_]+ | CORR_IL6_TNF | Globally unique. | Stable identifier. |
| node_a_id (FK → biomarker_node_definitions_v1) | TEXT (FK) | NODE_* | NODE_IL6 | Must exist. node_a_id < node_b_id (canonical). | First biomarker in pair. |
| node_b_id (FK → biomarker_node_definitions_v1) | TEXT (FK) | NODE_* | NODE_TNF_ALPHA | Must exist. | Second biomarker in pair. |
| rho | REAL | [-1,1] | 0.65 | NOT NULL. Empirical correlation. | Residual correlation for block-diagonal D (§2.6). |
| rho_se | REAL (nullable) | >0 | 0.08 | Uncertainty in rho for sensitivity sweeps. | For [0, 2×ρ] sensitivity analysis. |
| d_block | ENUM | {inflammatory, neuro_stress, independent} | inflammatory | Assigns pair to D matrix block. | Block-diagonal grouping (§2.17.2). |
| source_citation | TEXT | free text | Felger et al., 2020, Mol Psychiatry | NOT NULL. | Evidence source. |
| is_decision_critical | INTEGER | {0, 1} | 0 | 1 if sensitivity sweep changes rankings. | Flags ranking-instability pairs. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: not included in D matrix. | Soft disable. |
| notes | TEXT (nullable) | free text | Cytokine cluster: co-regulated by NF-κB | No executable logic. | Implementation notes. |

---

#### A31. `feedback_loops_v1`

**Purpose:** Defines the 5 feedback structures in the DAG from §2.11 — loop edges, gain, period, stability properties, and breaking interventions.

**1 Row =** One feedback loop with its edge chain, computed loop gain (<1 for stability), and characteristic period.

**Executed When:** Design-time authoring; read at build-time stability verification (ALG-A) and temporal dynamics (ALG-E).

**Input Tables (reads from):** edge_relations_definitions_v1.edge_relation_id (via JSON), biomarker_node_definitions_v1.node_id (via JSON), action_catalog_v1.action_id (optional)

**Output Tables (consumed by):** simulation_trace_v1 (loop dynamics)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| loop_id (PK) | TEXT (PK) | LOOP_[A-Z0-9_]+ | LOOP_FATIGUE_ACTIVITY | Globally unique. | Stable loop identifier. |
| loop_label | TEXT | free text | Fatigue ↔ Physical Activity | NOT NULL. | Human-readable description. |
| edge_relation_ids_json | JSONB | Array of ER_* | ["ER_FATIGUE__ACTIVITY", "ER_ACTIVITY__FATIGUE"] | Every element in edge_relations_definitions_v1. Must form cycle. | Edges comprising this feedback loop. |
| node_ids_json | JSONB | Array of NODE_* | ["NODE_FATIGUE", "NODE_PHYSICAL_ACTIVITY"] | Every element in biomarker_node_definitions_v1. | Nodes in the loop. |
| loop_gain | REAL | [0,1) | 0.16 | Product of constituent \|β_e\|. Must be <1 for stability. | Loop stability metric (§2.11). |
| characteristic_period_weeks | TEXT | range string | 2-4 | NOT NULL. Approximate cycle period. | Temporal dynamics of loop oscillation. |
| forward_dynamics | TEXT | free text | Rapid fatigue onset (days) → gradual activity decline (weeks) | NOT NULL. | Describes forward cascade timing. |
| reverse_dynamics | TEXT | free text | Exercise onset ~2 wk breaks cycle | NOT NULL. | Describes intervention entry point. |
| breaking_intervention | TEXT (nullable) | ACT_* | ACT_AEROBIC_MODERATE | If present: must exist in action_catalog_v1. | Which intervention breaks this loop. |
| spectral_radius_contribution | REAL (nullable) | ≥0 | 0.12 | Contribution to ρ(B). Total ρ(B)=0.41. | System stability verification. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| notes | TEXT (nullable) | free text | Strongest feedback loop in system | No executable logic. | Implementation notes. |

---

#### A32. `intervention_kernels_v1`

**Purpose:** Defines per-intervention temporal kernels — onset, build, steady-state, and decay parameters from §2.11. Maps to paper's intervention_kernel_registry.csv (9 records).

**1 Row =** One temporal kernel specification for one intervention, with kernel family and phase timing parameters.

**Executed When:** Design-time authoring; read at runtime temporal overlay (Stage F, ALG-E).

**Input Tables (reads from):** action_catalog_v1.action_id

**Output Tables (consumed by):** simulation_trace_v1 (temporal effect profiles)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| kernel_id (PK) | TEXT (PK) | KERN_[A-Z0-9_]+ | KERN_AEROBIC_MODERATE | Globally unique. | Stable kernel identifier. |
| action_id (FK → action_catalog_v1) | TEXT (FK) | ACT_* | ACT_AEROBIC_MODERATE | Must exist in action_catalog_v1. | Which intervention this kernel applies to. |
| kernel_family | ENUM | {delta, exponential, step, gamma, biexponential, saturation, adaptation, trapezoidal} | trapezoidal | Maps to §2.11 kernel families. | Mathematical form of temporal effect. |
| onset_weeks_min | REAL | ≥0 | 2.0 | NOT NULL. Lower bound of onset range. | Earliest expected effect onset. |
| onset_weeks_max | REAL | ≥0 | 4.0 | ≥ onset_weeks_min. | Latest expected effect onset. |
| build_weeks | REAL | >0 | 10.0 | NOT NULL. Time to reach steady state. | Duration of ramp-up phase. |
| steady_state_weeks_min | REAL | >0 | 12.0 | NOT NULL. | Earliest steady-state onset. |
| steady_state_weeks_max | REAL | >0 | 52.0 | ≥ steady_state_weeks_min. | Duration of plateau (if maintained). |
| decay_half_life_weeks | REAL | >0 | 3.5 | NOT NULL. Half-life after cessation. | How quickly benefit decays post-cessation. |
| pathway_specific_onset_json | JSONB (nullable) | Object: {pathway_id: onset_weeks} | {"PW_NEUROINFLAM": 3, "PW_BDNF": 6} | If present: per-pathway onset overrides. | Pathway-specific temporal dynamics. |
| source_citation | TEXT | free text | Xiong et al. 2024; Campbell et al. 2020 | NOT NULL. | Evidence source for temporal parameters. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: not used. | Soft disable. |
| notes | TEXT (nullable) | free text | Onset faster for anti-inflammatory pathway than neuroplasticity | No executable logic. | Implementation notes. |

---

### 3.2. Class B — Evidence (Extracted Study Data)

> Append-only during extraction. These tables accumulate evidence from processed papers — each extraction run adds rows but never modifies existing ones.

#### B1. `study_registry_v1`

**Purpose:** Deduplication gate and canonical record for every paper the system has processed. First table written during extraction (fill_order 0.5).

**1 Row =** One paper the system has seen, identified by DOI + content hash.

**Executed When:** Per-paper extraction (EX-P1, MetadataAgent). Dedup check on entry.

**Input Tables (reads from):** None (ROOT for evidence chain)

**Output Tables (consumed by):** study_cohort_profiles_v1, edge_evidence_v1, ontology_links_v1, extraction_audit_v1, and all evidence-linked tables

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| study_id | TEXT | STUDY_TELL2014 | Paper ID unique indicator |  |
| title | TEXT | — | Day-to-Day Dynamics of Associations between Sleep, Napping, Fatigue and the Cortisol Diurnal Rhythm in Women Diagnosed w | Canonical title for citations and audit. |
| authors | TEXT | — | Dina Tell; Herbert L Mathews; Linda Witek Janusek | Attribution for paper-level recordkeeping. |
| journal | TEXT | — | Psychosomatic Medicine | Journal context; can be used for quality heuristics but not required. |
| year | INTEGER | — | 2014.0 | Publication year; supports recency checks. |
| doi | TEXT | — | 10.xxxx/xxxxx | Stable identifier; preferred for linking. |
| pmid | TEXT | — | 25186656.0 | Stable PubMed identifier for retrieval and audit. |
| pmcid | TEXT | — | PMC4163097 | Stable PMC identifier for reproducibility. |
| study_design | TEXT | {RCT,longitudinal,cross_sectional,meta,intensive,mechanistic,other} | longitudinal | High-level design classification; used for evidence weighting. |
| notes | TEXT | — | bidirectionality noted by authors | Stores any interpretive caveats that affect directionality or validity. |
| version | INTEGER |  |  |  |

---

#### B2. `study_cohort_profiles_v1`

**Purpose:** Captures cohort-level metadata for each study — demographics, cancer type, treatment phase, sample size. Used for Layer 2 transportability (§2.9).

**1 Row =** One cohort slice within one study (e.g., treatment arm, control group).

**Executed When:** Per-paper extraction (EX-P1, CohortAgent).

**Input Tables (reads from):** study_registry_v1.study_id

**Output Tables (consumed by):** edge_evidence_v1, profile_data_streams_v1, predictor_alignment_rules_v1, triangulation_evidence_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| profile_id | TEXT (PK) | PROF_[A-Z0-9_]+ | PROF_TELL2014_BASE_T1 | Unique identifier for a cohort slice used to link evidence rows (Table 2A) and streams (Table 12). |
| study_id | TEXT (FK) | STUDY_[A-Z0-9_]+ | STUDY_TELL2014 | Links this cohort slice to the study registry (Table 11). |
| cohort_label | TEXT | — | Women with breast cancer, baseline | Human-readable label for reports. |
| analysis_timepoint | TEXT | {baseline,T1,T2,post,followup,other} | baseline | Canonical timepoint label for scoping. |
| N_analyzed | INTEGER | ≥0 | 130.0 | Final analytic N for this slice (preferred over a generic “N_profile”). |
| N_enrolled | INTEGER (nullable) | ≥0 | 146.0 | Optional if paper reports enrolled N separately from analyzed N. |
| recruitment_region | TEXT (nullable) | — | West-suburban Chicago | External validity. |
| recruitment_sites | TEXT (nullable) | — | Three breast oncology clinics | External validity (setting). |
| collection_calendar_start | TEXT (nullable) | ISO date YYYY-MM-DD | 2008-09-01 00:00:00 | Data collection start (structured). |
| collection_calendar_end | TEXT (nullable) | ISO date YYYY-MM-DD | 2012-10-31 00:00:00 | Data collection end (structured). |
| enrollment_window_text | TEXT (nullable) | — | Sep 2008–Oct 2012 | Optional human string if only reported that way. |
| eligibility_inclusion | TEXT (nullable) | — | Post-surgery; pathology available | Inclusion criteria (concise, near-verbatim). |
| eligibility_exclusion | TEXT (nullable) | — | No recurrent cancers; no corticosteroids; no systemic chemo | Exclusion criteria (concise, near-verbatim). |
| key_exclusion_flags_json | TEXT (nullable) | JSON object | {"systemic_chemo_excluded":1,"corticosteroids_excluded":1,"immune_disease_excluded":1,"sleep_aid_exclusion_applied":1,"t | Machine-readable “hard exclusions” that affect physiology/validity. Do not expand into many columns unless you will quer |
| index_event_time_refs_json | TEXT (nullable) | JSON object | {"post_surgery_min_weeks":2,"post_surgery_mean_weeks":7,"post_surgery_sd_weeks":5,"radiation_time_since_start_mean_weeks | Stores “time since surgery / chemo / radiation start” summaries without forcing rigid columns across studies. |
| sex_female_pct | REAL (nullable) | 0–100 | 100.0 | Cohort composition. |
| age_mean | REAL (nullable) | — | 55.6 | Mean age. |
| age_sd | REAL (nullable) | — | 9.4 | SD age. |
| education_years_mean | REAL (nullable) | — | 15.4 | Mean years education (if reported). |
| education_years_sd | REAL (nullable) | — | 2.8 | SD education. |
| bmi_mean | REAL (nullable) | — | 27.1 | BMI mean if reported. |
| bmi_sd | REAL (nullable) | — | 5.2 | BMI SD if reported. |
| race_distribution_json | TEXT (nullable) | JSON object | {"White":0.769,"AfricanAmerican":0.131,"Hispanic":0.054,"PI_Asian":0.046} | Normalized proportion distribution. Keys must come from your controlled race vocabulary. |
| marital_distribution_json | TEXT (nullable) | JSON object | {"Married":0.715,"DivorcedSeparated":0.154,"Single":0.131} | Same principle. |
| income_distribution_json | TEXT (nullable) | JSON object | {"10k_29k":0.092,"30k_59k":0.177,"60k_plus":0.731} | Same principle. |
| other_demographics_json | TEXT (nullable) | JSON object | {"menopausal_status":null,"employment":null} | Extensible catch-all for rarely reported fields. |
| cancer_context_json | TEXT (nullable) | JSON object | {"cancer_type":"breast","stage_dist":{"Stage0":0.215,"StageI":0.562,"StageII":0.223},"surgery_dist":{"BreastConserving": | Keeps all treatment/cancer descriptors together for interpretability and future filtering. |
| cancer_type | TEXT (nullable) | {breast,colorectal,lung,mixed,other} | breast | Redundant but useful for fast filtering without JSON parsing. |
| treatment_phase | TEXT (nullable) | {active_chemo,post_treatment,mixed,other} | post_treatment | Critical scoping for your pipeline. |
| time_since_treatment_text | TEXT (nullable) | — | ~7±5 weeks post-surgery; some started radiation | Stores heterogeneous timing narrative (do not force numeric). |
| analysis_context_json | TEXT (nullable) | JSON object | {"analysis_model_family":"HLM","software":"HLM 7.0; SPSS 20.0","predictor_standardization":"L2/L3 standardized; covariat | Minimal modeling context needed to interpret outcomes like slope/CAR. Detailed model specs live in Table 2A per estimate |
| notes | TEXT (nullable) | — | Authors note bidirectionality (sleep↔HPA). | Any cohort-slice caveats not captured elsewhere. |
| version | INTEGER |  |  |  |

---

#### B3. `profile_data_streams_v1`

**Purpose:** Captures what was measured in each cohort — which instruments and measures were used, at what timepoints.

**1 Row =** One data stream (instrument × measure) in one cohort profile.

**Executed When:** Per-paper extraction (EX-P1, CohortAgent).

**Input Tables (reads from):** study_cohort_profiles_v1.profile_id, instrument_definitions_v1.instrument_id, measure_definitions_v1.measure_id

**Output Tables (consumed by):** edge_evidence_v1, stream_timepoints_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| profile_id | TEXT (FK→study_cohort_profiles_v1.profile_id) | — | PROF_TELL2014_BASE_T1 | Links the stream to the cohort slice. |
| stream_id | TEXT (PK) | — | STR_TELL2014_SALIVA_CORT_2D | Unique identifier for this stream within the profile. |
| stream_label | TEXT | — | Saliva cortisol sampling (2 days) | Human-readable label. |
| analyte_or_target | TEXT | — | cortisol | What is measured (or the construct). |
| modality_type | TEXT | {self_report_questionnaire,self_report_diary,biospecimen_assay,medical_record_abstraction,cognitive_testing,wearable_sen | biospecimen_assay | ( Coarse stream category ) High-level modality class for filtering and weighting. |
| capture_method | TEXT | {paper,web,app,interview,phone,device_auto,lab_assay,chart_review,other,unknown} | lab_assay | How data is captured |
| instrument_id | TEXT (nullable; FK→instrument_definitions_v1.instrument_id) | instrument_id | PSQI_TOTAL | Links to upstream instrument when applicable (questionnaire/diary). |
| measure_id | TEXT (nullable; FK→measure_definitions_v1.measure_id) | measure_id | HPA_CORTISOL_RAW_UGDL | Links to downstream measure when applicable (assay/proxy base). |
| administration_setting | TEXT | {clinic,home,lab,remote,unknown} | clinic | Where the capture occurred (clinic intake vs research protocol at home). |
| administration_role | TEXT | {self_administered,interviewer_administered,clinician_administered,device_auto,unknown} | interviewer_administered | Who administered it (distinguishes interview-administered vs self). |
| instrument_version | TEXT | free text (or controlled if you standardize later) | PSQI (standard) | Tracks version differences that can change comparability. |
| language | TEXT | ISO 639-1 | EN | Captures translated versions without creating “new instruments.” |
| translation_status | TEXT | {original,translated_validated,translated_unvalidated,unknown} | translated_validated | Flags translation reliability differences. |
| visit_context | TEXT | {intake,baseline_visit,followup_visit,unscheduled,diary_day,other,unknown} | intake | Captures clinic intake vs scheduled study visit context. |
| recall_window_iso | TEXT | ISO 8601 duration | P30D | Recall window (critical for time alignment). For questionnaires: recall window (e.g., PSQI = P30D). |
| schedule_pattern | TEXT | {once,per_visit, qd,bid,tid,5_per_day,event_based,custom} | Standard schedule descriptor. |  |
| schedule_pattern_spec | TEXT (nullable) | — | wake,+30m,1200,1700,bedtime | (Human Ref) Free text for exact schedule. |
| collection_time_unit | TEXT | {moment,day,visit,week,month,study_window,custom} | day | Unit of sampling for this stream. |
| scheduled_duration_value | REAL (nullable) | — | 2.0 | Planned duration of collection in collection_unit. |
| timestamp_source | TEXT | {participant_reported,device_recorded,clinician_recorded,lab_recorded,derived,unknown} | participant_reported | Source of timestamps (critical for time alignment). |
| primary_time_anchor | TEXT | {wake_time,clock_time,index_event,visit_day,bedtime,unknown} | wake_time | What the schedule is anchored to. |
| days_collected_value | REAL (nullable) | — | 2.0 | Total days collected (if applicable). |
| quality_controls_summary | TEXT (nullable) | — | Recorded exact time of each sample; excluded protocol violators | Stream-level QC summary for validity. |
| notes | TEXT (nullable) | — | Cortisol measured by Salimetrics immunoassay; ln-transform used | Any stream-specific notes. |
| version | INTEGER |  |  |  |

---

#### B4. `stream_timepoints_v1`

**Purpose:** Captures measurement timepoints within each data stream — assessment timing relative to treatment for temporal alignment (§2.9 Layer 6).

**1 Row =** One measurement timepoint in one data stream.

**Executed When:** Per-paper extraction (EX-P1).

**Input Tables (reads from):** profile_data_streams_v1.stream_id

**Output Tables (consumed by):** edge_evidence_v1 (temporal matching)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| timepoint_id | TEXT (PK) | — | TP_TELL2014_WAKE | Unique timepoint identifier. |
| stream_id | TEXT (FK→profile_data_streams_v1.stream_id) | — | STR_TELL2014_SALIVA_CORT_2D | Attaches timepoints to the specific stream. |
| timepoint_label | TEXT | — | wake | Human label. |
| timepoint_type | TEXT | {anchor,offset,clock,bedtime,other} | offset | Encodes whether timepoint is an offset from anchor or fixed clock time. |
| anchor_event | TEXT | {awakening,exercise_end,chemo_infusion,bedtime,none} | awakening | Anchor definition used for offsets. |
| timepoint_minutes | INTEGER | — | 30.0 | Minutes after anchor_event when timepoint_type=offset. |
| clock_time_hhmm | TEXT | — | 1200.0 | Clock time when timepoint_type=clock. |
| allowable_window_min | INTEGER | — | 10.0 | Allowed deviation window for QA + simulation realism. |
| required | INTEGER | {0,1} | 1.0 | Declares whether missing this timepoint invalidates a derived measure. |
| maps_to_measure | TEXT | {awakening_level,CAR_component,diurnal_slope_component,bedtime_level,other} | CAR_component | Allows reconstruction of CAR/slope/AUC definitions. |
| version | INTEGER |  |  |  |

> **Note:** The original DOCX had ontology_links_v1 (B5) column schema erroneously embedded at the end of this table's column listing. That schema now appears in its correct section.


---

#### B5. `ontology_links_v1`

**Purpose:** Provenance links connecting ontology entities (nodes, edges, instruments, measures) to the papers that support their inclusion.

**1 Row =** One provenance link: 'this ontology entity exists because of this study.'

**Executed When:** Offline curation as supporting references are identified.

**Input Tables (reads from):** study_registry_v1.study_id, polymorphic target_id (node/edge/instrument/measure)

**Output Tables (consumed by):** None (provenance tracing only)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| link_id | TEXT (PK) | PROV_[A-Z0-9_]+ | PROV_SLEEP_ORIENT_001 | Unique provenance link. |
| target_table | TEXT | {biomarker_node_definitions_v1,instrument_definitions_v1,measure_definitions_v1,...} | measure_definitions_v1 | What entity is being justified. |
| target_id | TEXT |  | HPA_SLOPE_LNHR | Which node/instrument/measure. |
| study_id | TEXT (FK) | STUDY_* | STUDY_TELL2014 | Which paper supports it. |
| support_type | TEXT | {definition,validation,mapping,directionality,threshold,rule,background} | directionality | Nature of support. |
| evidence_strength | TEXT | {strong,moderate,weak,background} | moderate | Strength label. |
| snippet | TEXT |  | Flatter diurnal slope indicates dysregulation | Audit quote/paraphrase. |
| locator | TEXT |  | Methods; Cortisol analysis; Table 3 | Page/table/section pointer. |
| notes | TEXT (nullable) |  |  | Anything else. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |

---

#### B6. `edge_evidence_v1`

**Purpose:** The central evidence table — every extracted effect estimate from every paper for every edge. The largest table in the system (71 columns). Written by the trust boundary (§2.5.4), harmonized in EX-P2, consumed by aggregation in EX-P4.

**1 Row =** One extracted effect estimate from one paper for one edge, with full harmonization metadata and seven-layer SE.

**Executed When:** Per-paper extraction (EX-P2, ClaimNormalizer) through trust boundary.

**Input Tables (reads from):** study_registry_v1.study_id, edge_relations_definitions_v1.edge_relation_id, study_cohort_profiles_v1.profile_id, instrument_definitions_v1.instrument_id, measure_definitions_v1.measure_id, profile_data_streams_v1.stream_id, harmonization_rules_v1.rule_id

**Output Tables (consumed by):** edges_v1 (via aggregation), edge_param_builds_v1, baseline_modifier_definitions_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| ler_id | TEXT (PK) | LER_{MODULE}_{STUDY}_{NNN} | LER_A_TELL2014_001 | Unique ID for one extracted estimate row. |
| edge_param_id | TEXT (FK) | EP_{edge_relation_id}__{measure_id}__{cancer_type}__{treatment_phase}__V{version} | EP__ER_A_SLEEP_DISRUPTION__HPA_DYSREG__MEAS_HPA_DYSREG__SLOPE__LN_PER_HR_SALIVA__V1__BREAST__POST_TREATMENT__V1 | Runtime edge parameter row this estimate informs (stable linkage for future aggregation). |
| edge_relation_id | TEXT (FK) | ER_{MODULE}_{NODEX}__{NODEY} | ER_A_SLEEP_DISRUPTION__HPA_DYSREG | Conceptual directed relation (X→Y), proxy-agnostic. |
| profile_id | TEXT (FK) | PROF_* | PROF_TELL2014_BASE_T1 | Cohort slice context for this estimate. |
| study_id | TEXT (FK) | STUDY_* | STUDY_TELL2014 | Study registry linkage. |
| edge_family | TEXT | your controlled family vocab | A_SLEEP__HPA | Aggregation guardrail: only combine estimates within the same family. |
| node_x | TEXT | node_id | NODE_SLEEP_DISRUPTION | Canonical upstream node. |
| node_y | TEXT | node_id | NODE_HPA_DYSREG | Canonical downstream node. |
| upstream_instrument_id | TEXT | instrument_id | PSQI_TOTAL | What X is (upstream instrument/construct identifier). |
| upstream_stream_id | TEXT (FK) | STR_* | STRM_TELL2014_PSQI | Use when multiple upstream streams exist in the same profile. Else still allowed. |
| upstream_raw_unit | TEXT | free text | points (0–21) | Unit/scale wording exactly as in paper (audit; do not normalize here). |
| downstream_measure_id | TEXT | measure_id | HPA_SLOPE_LNHR | What Y proxy is (downstream standardized proxy). |
| downstream_stream_id | TEXT (FK) | STR_* | STRM_TELL2014_CORTISOL_SALIVA | Use when multiple downstream assay/schedule variants exist. |
| downstream_raw_unit | TEXT | free text | Δ ln(cortisol)/hr | Unit as reported (audit; do not clean). |
| analysis_model_family | TEXT | {HLM,mixed_effects,linear_regression,meta,other,unknown} | HLM | Paper’s label (audit-only; may be software-specific). |
| analysis_model_family_id | TEXT (FK, nullable) | FK → analysis_model_families_v1 | AMF_HLM | Normalized mapping of the paper label to your controlled catalog. Fill if you maintain the lookup table; else NULL. |
| model_family | TEXT | {OLS,LMM,GLMM,GEE,Cox,other,unknown} | LMM | Statistical family for comparability. Rule: HLM/mixed linear → LMM unless clearly non-Gaussian. |
| random_effects_structure | TEXT (nullable) | free text | random intercept person; random slope time_since_wake | Fill only if multilevel and reported. If omitted in paper → NULL (do not infer). |
| cluster_unit | TEXT | {person,day,clinic,study,other,unknown} | person | What clustering/nesting the variance/SE pertains to. If not stated → unknown. |
| se_type | TEXT | {model_based,robust,cluster_robust,bootstrap,unknown} | cluster_robust | How SE was computed. If paper only says “SE” with no qualifier → unknown. |
| predictor_level | TEXT | {L1,L2,L3,unknown} | L3 | Level where X lives. Rule: baseline person trait → L3; prior-day/day-level → L2; sample/moment-level → L1; else unknown. |
| centered_level | TEXT | {L1,L2,L3,unknown} | L2 | Level at which centering was applied. If paper is vague → unknown. |
| centering_method | TEXT | {none,grand_mean,group_mean,study_specific,unknown} | grand_mean | Centering used for X (or explicitly for predictors). If not reported → unknown. |
| centering_note | TEXT | free text | Not reported. | Always fill. If absent in paper, write exactly: Not reported. |
| outcome_component | TEXT | {intercept,linear_slope,quadratic_slope,CAR,other} | linear_slope | Which trajectory component the coefficient targets. |
| time_metric_definition | TEXT | free text | hours since awakening; time=0 at wake | Required when outcome_component ∈ {linear_slope, quadratic_slope, CAR}. Else optional. |
| CAR_definition | TEXT (nullable) | free text | #ERROR! | Fill only if CAR is modeled/defined. Else NULL. |
| time_unit_x | TEXT (nullable) | {per_hour,per_day,per_week,per_month,other,unknown} | per_day | Fill only if X is explicitly time-rate based. Else NULL. |
| time_unit_y | TEXT (nullable) | {per_hour,per_day,per_week,per_month,other,unknown} | per_hour | Fill only if Y is explicitly time-rate based (e.g., slope per hour). Else NULL. |
| x_transform | TEXT | {none,log,z,rank,other,unknown} | z | How X entered the model. If unclear → unknown. |
| y_transform | TEXT | {none,log,z,rank,other,unknown} | log | How Y entered the model. If unclear → unknown. |
| alignment_type | TEXT | {same_day,prior_day,prior_week,rolling_window,custom,unknown} | prior_day | Temporal meaning of the estimate. If not stated, use unknown (not same_day by default). |
| alignment_type_id | TEXT (FK, nullable) | FK → alignment_types_v1 | ALN_PRIOR_DAY | Normalized alignment catalog ID if you maintain the lookup table; else NULL. |
| alignment_lag_days | INTEGER (nullable) | ≥0 | 1.0 | Fill when alignment implies a lag. If not stated → NULL. |
| alignment_note | TEXT (nullable) | free text | “Prior-day nap predicts next-day cortisol slope.” | Fill if alignment is custom or needs clarification; else NULL. |
| effect_type_reported | TEXT | {std_beta,unstd_beta,percent_change,OR,RR,HR,group_diff,other} | unstd_beta | Effect type exactly as paper reports. |
| effect_value_reported | REAL | — | 0.026 | Numeric estimate exactly as reported (sign as reported). |
| se_reported | REAL (nullable) | — | 0.009 | Reported SE if explicitly given; else NULL. |
| ci_low_reported | REAL (nullable) | — | 0.008 | Reported CI low if given; else NULL. |
| ci_high_reported | REAL (nullable) | — | 0.044 | Reported CI high if given; else NULL. |
| p_value | REAL (nullable) | — | 0.006 | Audit only. Never used directly for runtime math. |
| sd_x | REAL (nullable) | — | 3.6 | SD of X if reported (supports harmonization). Else NULL. |
| sd_y | REAL (nullable) | — | 1.2 | SD of Y if reported (supports harmonization). Else NULL. |
| N_effect | INTEGER | ≥0 | 130.0 | N for this specific estimate/model (can differ from profile N). |
| subgroup_label | TEXT (nullable) | free text | All participants (baseline) | Only if the estimate is subgroup-specific; else NULL. |
| covariates_adjusted | TEXT | free text | Adjusted for age, BMI, stage; time since wake. | Retained adjustment set, concise. |
| adjustment_selection_method | TEXT | {pre_specified,stepwise,parsimonious,unknown} | parsimonious | How covariates were retained/selected. |
| harmonization_status | TEXT | {complete,partial,blocked,unreviewed} | partial | unreviewed until you attempt harmonization. blocked if required inputs are missing and no fallback allowed. partial if y |
| harmonized_scale | TEXT (nullable) | {SD_SD,PROXY_PER_SD,LOGOR_PER_SD,RAW_PER_SD} | PROXY_PER_SD | Scale of harmonized_beta. Must be NULL when status is unreviewed. |
| harmonized_beta | REAL (nullable) | — | 0.026 | Harmonized estimate in canonical orientation (aligned to node semantics). Must be NULL if status ∈ {blocked,unreviewed}. |
| harmonized_se | REAL (nullable) | — | 0.009 | SE on the harmonized scale if computable. NULL allowed when status is partial and SE cannot be derived. |
| blocked_reason | TEXT (nullable) | free text | sd_y missing; cannot convert to SD_SD | Required when status=blocked. Otherwise NULL. |
| harmonization_rule_id | TEXT (FK, nullable) | FK → harmonization_rules_v1.rule_id | HR_UNSTD_BETA_XZ_YLOG | Rule used. Must be NULL when status=unreviewed. If status=blocked, fill the rule you attempted (if known) or NULL if not |
| interaction_reported | INTEGER | {0,1} | 1.0 | 1 if paper reports interaction term or stratified betas by moderator. |
| interaction_variable_id | TEXT (nullable) | canonical variable_id | VAR_RADIATION_ANY | Canonical moderator ID if you maintain variable definitions; else NULL. |
| interaction_variable_raw | TEXT (nullable) | free text | radiation status | Raw term used in the paper (audit). Fill when interaction_reported=1. |
| moderator_definition | TEXT (nullable) | free text | Radiation coded as any vs none at baseline. | How the moderator was coded. Fill when interaction_reported=1 and definition exists. |
| interaction_beta | REAL (nullable) | — | 0.12 | Numeric interaction coefficient for X×M if reported. Else NULL. |
| interaction_se | REAL (nullable) | — | 0.05 | SE for interaction_beta if reported. Else NULL. |
| subgroup_beta_M0 | REAL (nullable) | — | 0.02 | Beta for subgroup with M=0 if reported as separate betas. Else NULL. |
| subgroup_se_M0 | REAL (nullable) | — | 0.01 | SE for subgroup_beta_M0 if reported. Else NULL. |
| subgroup_beta_M1 | REAL (nullable) | — | 0.05 | Beta for subgroup with M=1 if reported as separate betas. Else NULL. |
| subgroup_se_M1 | REAL (nullable) | — | 0.02 | SE for subgroup_beta_M1 if reported. Else NULL. |
| interaction_effect_reported | TEXT (nullable) | free text | β_X×M=0.12 (SE=0.05), p=0.02 | Keep only what is not captured by structured numeric fields. Leads with the exact reporting text. |
| quality_rating | TEXT | {strong,moderate,weak} | moderate | Triage label used by aggregation policies (do not “average” across quality without explicit policy). |
| extraction_snippet | TEXT | free text | “PSQI → slope: b=0.026, SE=0.009 (Table 3)” | Minimal locator snippet so you do not reopen the paper. |
| entered_by | TEXT | free text | AI_assisted_v1 | Pipeline audit. |
| entered_at | TEXT | ISO datetime | 2026-01-17T18:05:00-08:00 | Pipeline audit. |
| version | INTEGER | ≥1 | 1.0 | Data version for this row-set. |
| active | INTEGER | {0,1} | 1.0 | Soft delete/disable. |
| rob_tool | TEXT (nullable) | {RoB2,ROBINS-I,NOS,JBI,other} | RoB2 | Risk-of-bias assessment tool used. Codebase addition for evidence quality grading. |
| rob_overall | TEXT (nullable) | {low,some_concerns,high,critical,unclear} | some_concerns | Overall risk-of-bias judgment. Codebase addition — informs quality_rating and aggregation weighting. |
| estimand_class | TEXT (nullable) | {ATE,ATT,CACE,ITT,PP,other} | ATT | Estimand classification (intention-to-treat vs per-protocol vs complier average). Codebase addition for estimand-aware aggregation. |
| identification_status | TEXT (nullable) | {identified,partially_identified,not_identified} | identified | Whether causal identification strategy is valid. Codebase addition for evidence quality assessment. |
| notes | TEXT (nullable) | free text | No treatment covariates significant in final model. | Anything that does not belong elsewhere. Keep sparse. |

---

#### B7. `edge_param_builds_v1`

**Purpose:** Aggregation audit trail — records each compilation step from evidence to compiled edge parameters. Enables provenance tracing.

**1 Row =** One compilation step in the evidence→edges build process.

**Executed When:** Aggregation pipeline (EX-P4).

**Input Tables (reads from):** harmonization_rules_v1.rule_id (via JSON), edges_v1.edge_param_id (via JSON)

**Output Tables (consumed by):** None (audit trail for provenance)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| build_id | TEXT (PK) | BUILD_[0-9]{8}[A-Z0-9]+ | BUILD_20260122_SLEEP_V1 | Unique build event ID. |
| build_label | TEXT | free text | “Sleep→HPA build v1” | Human label. |
| build_time | TEXT | ISO datetime | 2026-01-22T10:35:00-08:00 | When build executed. |
| build_version | INTEGER | ≥1 | 1.0 | Increment when you change compilation semantics. |
| code_commit_hash | TEXT (nullable) | git hash | a1b2c3d | Optional, but strongly recommended. |
| input_scope_spec_json | TEXT (JSON) | JSON object | {"module":"A","cancer_type":["breast"],"treatment_phase":["post_treatment"]} | What scope this build targeted. |
| evidence_query_spec_json | TEXT (JSON) | JSON object | {"min_quality":"pass","max_age_years":20} | Deterministic evidence inclusion policy. |
| harmonization_rule_ids_json | TEXT (JSON) | JSON array | ["HR_UNSTD_BETA_XZ_YLOG"] | Rules used in this build. |
| aggregation_policy | TEXT | {IVW_fixed, IVW_random, single_best, expert_pick} | single_best | Aggregation method used. |
| selection_policy_spec_json | TEXT (JSON) | JSON object | {"tie_break":["specificity_rank","evidence_rank","version","edge_param_id"]} | Declares deterministic tie-break sequence for edge compilation (not runtime selection). |
| timing_policy | TEXT | {use_reported, mechanistic_prior_default, default_delta} | mechanistic_prior_default | How lag/decay were assigned when not reported. |
| timing_prior_ids_json | TEXT (JSON, nullable) | JSON array of prior_id | ["PR_HPA_ACUTE_CHRONIC_SPLIT_V1"] | Only if timing_policy uses priors. |
| outputs_edge_param_ids_json | TEXT (JSON) | JSON array of edge_param_id | ["EP__ER_A_SLEEP...__V1..."] | Edges produced/updated by this build. |
| outputs_summary_json | TEXT (JSON) | JSON object | {"n_edges":12,"n_evidence_rows":44,"n_scopes":3} | Counts for audit. |
| warnings_json | TEXT (JSON) | JSON array | ["missing_sd_y_fallback_used"] | Build-time warnings. |
| status | TEXT | {ok, failed, partial} | ok | Build outcome. |
| notes | TEXT (nullable) | free text | “Timing imputed for 70% of rows.” | Non-executable notes. |
| active | INTEGER | {0,1} | 1.0 | Soft enable for your build ledger. |

---

#### B8. `triangulation_evidence_v1`

**Purpose:** Cross-method agreement results from papers — when a study reports correlation between multiple measures of the same construct.

**1 Row =** One cross-method agreement result from a paper for a triangulable construct.

**Executed When:** Extended extraction (EX-P2-EXT) when papers report multi-method agreement.

**Input Tables (reads from):** triangulation_sets_v1.triangulation_id, study_cohort_profiles_v1.profile_id, study_registry_v1.study_id

**Output Tables (consumed by):** None (optional reference for TriangulationEngine)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| tri_ev_id | TEXT (PK) | TRI_EV_[A-Z0-9_]+ | TRI_EV_SLEEP_0001 | Agreement record ID. |
| triangulation_id | TEXT (FK) | TRI_* | TRI_SLEEP_DISRUPTION_V1 | Which set. |
| profile_id | TEXT (nullable FK) | PROF_* | PROF_TELL2014_BASE_T1 | Cohort slice (nullable if instrument-general). |
| scope_json | TEXT (JSON, nullable) | JSON object | {"cancer_type":"breast","treatment_phase":"post_treatment"} | Applicability constraints for this agreement record. |
| agreement_scope | TEXT | {pairwise, overall} | pairwise | Pairwise between two members or overall set. |
| member_a_order | INTEGER (nullable) | >=1 | 1.0 | Required if pairwise. Refers to T2.member_order. |
| member_b_order | INTEGER (nullable) | >=1 | 2.0 | Required if pairwise. |
| agreement_metric | TEXT | {pearson_r, spearman_r, icc, kappa, other} | pearson_r | Metric. |
| agreement_value | REAL | — | 0.37 | Value. |
| agreement_ci_low | REAL (nullable) | — | 0.2 | Optional CI. |
| agreement_ci_high | REAL (nullable) | — | 0.52 | Optional CI. |
| N_agreement | INTEGER (nullable) | >=1 | 130.0 | Sample size. |
| p_value | REAL (nullable) | — | 0.01 | p-value if reported. |
| evidence_origin | TEXT | {reported, computed} | reported | Whether from paper or internal eval. |
| source_study_id | TEXT (nullable FK) | STUDY_* | STUDY_TELL2014 | Source study if reported. |
| page_or_table | TEXT (nullable) | — | Table 2 | Location reference. |
| notes | TEXT (nullable) | — | Not all constructs reported agreement | Notes. |
| version | INTEGER | >=1 | 1.0 | Version. |
| active | INTEGER | {0,1} | 1.0 | Enable flag. |

---

#### B9. `pathway_biomarkers_v1`

**Purpose:** Links biomarkers to pathways with evidence — extracted when papers report biomarker-pathway associations. Maps to paper's Supplementary Table S2 (24 mappings).

**1 Row =** One biomarker linked to one pathway with loading coefficient and evidence source.

**Executed When:** Extended extraction (EX-P2-EXT) when papers report biomarker-pathway associations.

**Input Tables (reads from):** pathways_v1.pathway_id, biomarker_node_definitions_v1.node_id, measure_definitions_v1.measure_id, study_registry_v1.study_id, edge_evidence_v1.ler_id

**Output Tables (consumed by):** None (consumed by PathwayEngine for activation detection)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| pb_id (PK) | TEXT (PK) | PB_[A-Z0-9_]+ | PB_INFLAM_IL6 | Globally unique. | Stable link identifier. |
| pathway_id (FK → pathways_v1) | TEXT (FK) | PW_* | PW_NEUROINFLAMMATION | Must exist. | Which pathway this biomarker indicates. |
| node_id (FK → biomarker_node_definitions_v1) | TEXT (FK) | NODE_* | NODE_IL6 | Must exist. | Which biomarker node. |
| measure_id (FK → measure_definitions_v1) | TEXT (FK) | MEAS_* | MEAS_IL6_PLASMA | Must exist. | Specific measurement assay. |
| indicator_type | ENUM | {direct_marker, proxy_marker, functional_readout} | direct_marker | NOT NULL. | How this biomarker relates to the pathway. |
| loading_coefficient | REAL | any numeric | 0.72 | Standardized loading on pathway latent variable. | Measurement model coefficient (§2.17). |
| loading_se | REAL | >0 | 0.12 | NOT NULL. | Uncertainty in loading. |
| source_study_id (FK → study_registry_v1) | TEXT (FK) | STUDY_* | STUDY_FELGER_2020 | Must exist. | Evidence source. |
| source_ler_id (FK → edge_evidence_v1) | TEXT (FK) | LER_* | LER_FELGER2020_003 | Must exist if from extraction. | Link to specific evidence record. |
| sample_matrix | ENUM | {plasma, serum, csf, saliva, tissue, stool, urine} | plasma | NOT NULL. Critical for interpretation. | Biological sample type (§2.7 caveat). |
| assay_caveat | TEXT (nullable) | free text | Must be plasma not serum for BDNF | Document critical measurement notes. | Clinical measurement warnings. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| active | INTEGER | {0, 1} | 1 | If 0: not used. | Soft disable. |
| notes | TEXT (nullable) | free text | IL-6 is the best-validated peripheral marker for CNS neuroinflammation | No executable logic. | Implementation notes. |

---

### 3.3. Class C — Compiled (Aggregated Parameters)

> Recomputed from Class A + B. Never manually edited. These tables contain the pooled, harmonized parameters that the algorithm actually uses at runtime.

#### C1. `edges_v1`

**Purpose:** THE KEY TABLE — compiled edge parameters (pooled β, SE, grade, inclusion probability) produced by the aggregation pipeline from edge_evidence_v1. Read by virtually all algorithm stages.

**1 Row =** One compiled edge parameter: pooled effect size with seven-layer SE, evidence grade, and structural inclusion probability.

**Executed When:** Recomputed by aggregation pipeline (EX-P4). Never manually edited.

**Input Tables (reads from):** edge_relations_definitions_v1.edge_relation_id, measure_definitions_v1.measure_id, literary_constraints_v1.rule_id (JSON), edge_evidence_v1.ler_id (JSON)

**Output Tables (consumed by):** ALL algorithm chains (ALG-A through ALG-F), simulation_trace_v1, decision_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| edge_param_id | TEXT (PK) | EP__{edge_relation_id}__{measure_id}__{cancer_type}__{treatment_phase}__V{version} | EP__ER_A_SLEEP_DISRUPTION__HPA_DYSREG__MEAS_HPA_DYSREG__SLOPE__LN_PER_HR_SALIVA__V1__BREAST__POST_TREATMENT__V1 | Must be globally unique. Never reused for different semantics. |
| edge_relation_id | TEXT (FK) | ER_* | ER_A_SLEEP_DISRUPTION__HPA_DYSREG | Must exist in edge_relations_definitions_v1.edge_relation_id. |
| measure_id | TEXT (FK) | MEAS_* | MEAS_HPA_DYSREG__SLOPE__LN_PER_HR_SALIVA__V1 | Must exist in measure_definitions_v1.measure_id. |
| effect_scale | TEXT | {SD_SD, PROXY_PER_SD, LOGOR_PER_SD, RAW_PER_SD} | PROXY_PER_SD | Must match the harmonization output scale used to compute beta. |
| effect_direction | INTEGER | {+1, -1} | 1 | Must reflect canonical node orientation convention used across the engine. |
| beta_mean | REAL | — | 0.026 | Required. If your raw column is beta, rename to beta_mean. |
| beta_se | REAL | nullable | 0.009 | If NULL, the row is still usable but Monte Carlo must use a declared fallback (e.g., deterministic β). You must not inve |
| beta_dist_family | TEXT | {normal, student_t, lognormal, empirical, unknown} | normal | v1 default = normal unless you have a concrete reason. |
| ci_low | REAL | nullable | 0.008 | If present, must be consistent with beta_mean and beta_se when applicable. |
| ci_high | REAL | nullable | 0.044 | Same rule as ci_low. |
| aggregation_method | TEXT | {IVW_fixed, IVW_random, single_best, expert_pick} | single_best | Must match how you aggregated contributing evidence rows. |
| evidence_level | TEXT | {meta, RCT, obs, mixed} | obs | Required. Choose the strongest level used. |
| cancer_type | TEXT | {breast, colorectal, lung, mixed, all} | breast | Must match your scope vocabulary. |
| treatment_phase | TEXT | {active_chemo, post_treatment, mixed, all} | post_treatment | Must match your scope vocabulary. |
| scope_filters_json | TEXT (JSON) | JSON object | {"sex":"female","age_min":40,"age_max":70} | Use {} when none (recommended) or NULL if you enforce NULL. Do not store keys you will never match on. |
| time_step_unit | TEXT | {day, week} | day | Must equal the simulator’s Stage 6 time step. |
| temporal_family | TEXT | {exponential, delta} | exponential | If delta, then half_life_steps must be NULL and the effect is applied within the current step only. |
| lag_steps | INTEGER | >=0 | 2.0 | Must be in units of time_step_unit. Default = 0 if truly immediate. |
| half_life_steps | REAL | >0 (conditional) | 7.0 | Required iff temporal_family=exponential. Must be NULL iff temporal_family=delta. |
| timing_source | TEXT | {reported, mechanistic_prior, default_delta} | mechanistic_prior | Required |
| timing_source_ref | TEXT nullable | PR_* or LER_* or DEFAULT_V1 | PR_HPA_POSTEX_TIMECOURSE_V1 | Required if timing_source≠reported? If reported, reference at least one LER_* |
| time_scale_compat_mode | TEXT | {native_step, convertible, blocked} | native_step | Recommended; if blocked, row inadmissible |
| baseline_modifier_mode | TEXT | {none, stratified_rows, rule_adjust} | rule_adjust | If none, baseline_modifier_spec_json must be NULL. If rule_adjust, spec must be non-NULL. |
| baseline_modifier_spec_json | TEXT (JSON) | JSON object | {"modifier_ids":["MOD_RADIATION_ANY","MOD_AGE_SAT"],"applies_to":["beta","lag"]} | Required iff baseline_modifier_mode=rule_adjust. modifier_ids must exist in baseline_modifier_definitions_v1. applies_to |
| constraint_rule_ids_json | TEXT (JSON) | JSON array | ["CONSTR_HPA_POSTEX_TIMECOURSE_V1"] | Use [] when none (recommended) or NULL if you enforce NULL. Any id must exist in literary_constraints_v1.rule_id. |
| specificity_rank | INTEGER | >=0 | 2.0 | Higher wins when multiple rows match scope. |
| supporting_ler_ids | TEXT | semicolon list | LER_A_TELL2014_001;LER_A_TELL2014_002 | Each must exist in edge_evidence_v1.ler_id. |
| active | INTEGER | {0,1} | 1.0 | If 0, runtime must ignore the row. |
| version | INTEGER | >=1 | 1.0 | Increment only when semantics change. |
| i_squared | REAL (nullable) | [0,100] | 62.3 | Higgins I² heterogeneity statistic (%). Kept inline for runtime confidence reporting. |
| tau_squared | REAL (nullable) | >=0 | 0.04 | Between-study variance (τ²). Kept inline for runtime confidence reporting. |
| total_n | INTEGER (nullable) | >=1 | 847 | Total sample size across contributing studies. Kept inline for runtime confidence reporting. |
| notes | TEXT | nullable | Applies when baseline sleep measured by PSQI/ISI. | No executable logic here. |
| pub_bias_risk | ENUM | {LOW, MODERATE, HIGH, INSUFFICIENT_K} | LOW | Populated by EX-P4B. Publication bias assessment (§2.12.1). |
| se_inflation_pub_bias | REAL | [1.0, 1.5] default 1.0 | 1.0 | Multiplier from publication bias assessment. Applied to beta_se during MC sampling. |
| coherence_flag | ENUM | {PASS, MONITOR, INVESTIGATE, ALARM, UNTESTABLE} | UNTESTABLE | Populated by EX-P5-SEF. Chain-vs-direct validation result for pathways containing this edge (§2.13). |
| se_inflation_coherence | REAL | [1.0, 2.0] default 1.0 | 1.0 | SE inflation from chain-vs-direct discrepancy. Stacks with se_inflation_pub_bias. |
| e_value | REAL (nullable) | ≥1.0 | 2.34 | VanderWeele-Ding E-value for unmeasured confounding robustness (§2.22). NULL if not computed. |
| robustness_value | REAL (nullable) | [0,1] | 0.15 | Cinelli-Hazlett partial R² robustness value (§2.22). NULL if not computed. |

---

#### C2. `dose_bridges_v1`

**Purpose:** Dose-to-effect bridge mappings — translates intervention dose units (MET-min/week, sessions, hours) into standardized z-score effects on target nodes. Implements Emax/Hill models from §2.6.

**1 Row =** One dose-to-effect bridge mapping an action's dose to a node effect via Emax/Hill function parameters.

**Executed When:** Compiled from evidence (dose-response extraction). Never human-computed.

**Input Tables (reads from):** action_catalog_v1.action_id, derived_feature_definitions_v1.feature_id, biomarker_node_definitions_v1.node_id, literary_mechanistic_priors_v1.prior_id, outcome_anchors_v1.anchor_id

**Output Tables (consumed by):** simulation_trace_v1 (dose→Δz computation in Stage F)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| bridge_id | TEXT (PK) | DBR_[A-Z0-9_]+ | DBR_ACT_WALK_LOW_INT__NODE_FATIGUE__V1 | Unique and stable. Never reused. |
| action_id | TEXT (FK) | ACT_* | ACT_WALK_LOW_INT | Must exist in action_catalog_v1.action_id. |
| output_mode | TEXT | {to_feature, to_node} | to_feature | Determines which output field is required. |
| output_feature_id | TEXT (FK) | FEAT_* or NULL | FEAT_DAILY_METMIN_Z_V1 | Must be non-NULL iff output_mode=to_feature. Must exist in derived_feature_definitions_v1.feature_id. |
| output_node_id | TEXT (FK) | NODE_* or NULL | NODE_FATIGUE | Must be non-NULL iff output_mode=to_node. Must exist in biomarker_node_definitions_v1.node_id. |
| maps_to_node_id | TEXT (FK) | NODE_* or NULL | NODE_ACTIVITY | If output_mode=to_feature: if NULL, engine must resolve via derived_feature_definitions_v1.maps_to_node. If non-NULL, mu |
| dose_type | TEXT | {continuous, ordinal, binary} | continuous | Must match action_catalog_v1.dose_type. |
| dose_unit | TEXT | free text | MET_min_per_day | Must match action_catalog_v1.dose_unit. |
| dose_min | REAL | >=0 |  | Must be ≤ dose_reference ≤ dose_max. |
| dose_max | REAL | >=0 | 600.0 | Must be ≥ dose_min. |
| dose_step | REAL | nullable | 30.0 | If NULL, Stage 4/7 must use action defaults for discretization. |
| dose_reference | REAL | >0 | 150.0 | Required. Interprets f(d) scaling and bridge_gain. |
| dose_response_family | TEXT | {linear, saturating, hill} | saturating | Required. |
| dose_response_params_json | TEXT (JSON) | JSON object or NULL | {"k":150,"max":1.0} | Must be non-NULL iff family ∈ {saturating, hill}. Must be NULL iff family=linear. |
| bridge_effect_sign | INTEGER | {+1, -1} | 1 | Must be consistent with your node “higher=worse” convention for the output target. |
| bridge_gain | REAL | — | 0.2 | Interpreted as Δz per unit f(d). |
| bridge_noise_sd | REAL | nullable | 0.1 | If NULL, treat as 0 in simulation. |
| time_step_unit | TEXT | {day, week} | day | Must match Stage 6 simulator step. |
| temporal_family | TEXT | {delta, exponential} | delta | If delta, then half_life_steps must be NULL and the perturbation occurs within the same step. |
| lag_steps | INTEGER | >=0 |  | If temporal_family=delta, lag_steps still allowed (delayed impulse), but then it is “delayed delta.” |
| half_life_steps | REAL | >0 (conditional) | 3.0 | Required iff temporal_family=exponential. Must be NULL iff temporal_family=delta. |
| scope_json | TEXT (JSON) | JSON object or {} | {"cancer_type":"breast","treatment_phase":"post_treatment"} | Use {} for universal. If non-empty, keys must be canonical and must be honored in selection. |
| provenance | TEXT | free text | Guideline-derived scaling; v1 heuristic | Must state the basis (intervention trial, guideline, mechanistic assumption). |
| version | INTEGER | >=1 | 1.0 | Increment only when semantics change. |
| active | INTEGER | {0,1} | 1.0 | If 0, runtime must ignore the row. |

> **Note:** The original DOCX had node_priors_v1 (C3) and outcome_anchors_v1 (C4) column schemas erroneously embedded at the end of this table's column listing. Those schemas now appear in their correct sections. The actual dose_bridges table has 24 columns, not the inflated 56 that included embedded C3/C4.

---

#### C3. `node_priors_v1`

**Purpose:** Scoped prior distributions for each node — context-matched (cancer type × treatment phase) with four-level fallback hierarchy (§2.8).

**1 Row =** One scoped prior distribution (μ, σ) for one node in one clinical context.

**Executed When:** Compiled by PriorCompiler from evidence and clinical literature.

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id

**Output Tables (consumed by):** state_snapshots_v1 (initialization)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| prior_id | TEXT (PK) | NPR_[A-Z0-9_]+ | NPR_NODE_HPA_DYSREG__BREAST__POST_TREATMENT__V1 | Stable identifier. |
| node_id | TEXT (FK) | NODE_* | NODE_HPA_DYSREG | Which node this prior initializes. |
| prior_space | TEXT | {z} | z | v1: always z. |
| mean | REAL |  | 0.0 | Prior mean in node-aligned z-space. |
| sd | REAL | >0 | 1.0 | Prior uncertainty width. Must be >0. |
| dist_family | TEXT | {normal,student_t} | normal | Sampling/update assumption. |
| cancer_type | TEXT | {breast,colorectal,lung,mixed,all} | breast | Scope key. |
| treatment_phase | TEXT | {active_chemo,post_treatment,mixed,all} | post_treatment | Scope key. |
| scope_filters_json | TEXT (JSON) | JSON object | {} | Extra scope refinement. |
| specificity_rank | INTEGER | >=0 | 1 | Higher wins when multiple priors match. |
| provenance | TEXT | free text | Default neutral prior (v1) | Audit trail. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |
| version | INTEGER | >=1 | 1 | Version. |
| notes | TEXT (nullable) | free text |  | Non-executable notes. |

---

#### C4. `outcome_anchors_v1`

**Purpose:** Calibration anchors mapping z-scores to clinically interpretable scales — implements the six-tier severity classification from §2.20.

**1 Row =** One calibration anchor: z-score threshold → severity tier → percentile → clinical interpretation.

**Executed When:** Compiled from longitudinal CRCI studies and clinical thresholds.

**Input Tables (reads from):** biomarker_node_definitions_v1.node_id or derived_feature_definitions_v1.feature_id (polymorphic via target_id)

**Output Tables (consumed by):** recommendation_runs_v1, decision_trace_v1 (severity labeling in Stage I)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| anchor_id | TEXT (PK) | ANC_[A-Z0-9_]+ | ANC_FACTCOG_TOTAL_T_TO_TSCORE_BREAST_POST_V1 | Stable anchor ID. |
| target_level | TEXT | {node,feature,measure} | node | What is being anchored. |
| target_id | TEXT | NODE_* or FEAT_* or MEAS_* | NODE_COG_PERCEPTION | Which model target. |
| calibration_family | TEXT | {linear_z_to_score,logistic_z_to_probability,thresholds_z_to_ordinal,identity} | linear_z_to_score | Mapping family. |
| calibration_params_json | TEXT (JSON) | JSON object | {"intercept":50,"slope":10} | Mapping parameters. |
| scope_cancer_type | TEXT | {breast,colorectal,lung,mixed,all} | breast | Scope. |
| scope_treatment_phase | TEXT | {active_chemo,post_treatment,mixed,all} | post_treatment | Scope. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |
| notes | TEXT (nullable) |  |  |  |

---

#### C5. `state_estimator_specs_v1`

**Purpose:** Configuration for the Bayesian state estimation engine (§2.8) — specifies estimator variant, temporal decay rate, prior fallback hierarchy, and fusion level settings.

**1 Row =** One estimator configuration specification (information-form Gaussian with temporal weighting and context-matched priors).

**Executed When:** Engineering-compiled from algorithm design. Updated when estimator architecture changes.

**Input Tables (reads from):** None (self-contained configuration)

**Output Tables (consumed by):** state_snapshots_v1 (via estimator_id FK)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| estimator_id | TEXT (PK) | EST_[A-Z0-9_]+_V[0-9]+ | EST_GAUSS_CONJ_Z_V1 | Stable estimator spec ID. |
| estimator_family | TEXT | {gaussian_conjugate_independent, gaussian_conjugate_blockdiag} | gaussian_conjugate_independent | v1 recommended: independent. |
| update_space | TEXT | {node_z} | node_z | Enforces update occurs in node-aligned z-space only. |
| min_sigma_floor | REAL | >0 | 0.2 | Lower bound on posterior σ. |
| max_sigma_cap | REAL (nullable) | >0 | 5.0 | Optional cap to prevent blow-ups. |
| conflict_inflation_family | TEXT | {none, additive_var, multiplicative_sd} | multiplicative_sd | How conflict increases uncertainty. |
| conflict_inflation_params_json | TEXT (JSON) | JSON object | {"k":0.6,"max_mult":2.0} | Parameters for conflict inflation. |
| missingness_inflation_family | TEXT | {none, additive_var, multiplicative_sd} | additive_var | How missingness increases uncertainty. |
| missingness_inflation_params_json | TEXT (JSON) | JSON object | {"var_add":0.25} | Used when an expected core observation is missing. |
| core_coverage_policy | TEXT | {prior_only_ok, require_min_coverage, require_safety_coverage} | require_safety_coverage | How strict Stage 3 is about missing inputs. |
| required_nodes_json | TEXT (JSON, nullable) | JSON array of node_id | ["NODE_SLEEP_DISRUPTION"] | Only if core_coverage_policy enforces coverage. |
| admissibility_filters_json | TEXT (JSON) | JSON object | {"max_age_days":30,"qc_disallow":["out_of_range"]} | Filters on observation recency and QC flags. |
| noise_fallback_policy | TEXT | {conservative_default, block_update} | conservative_default | If observation_noise_v1 missing. |
| default_noise_params_json | TEXT (JSON) | JSON object | {"gaussian_sd":1.0} | Used only under noise_fallback_policy. |
| independence_assumption | INTEGER | {0,1} | 1.0 | Must match estimator_family. |
| version | INTEGER | ≥1 | 1.0 | Increment only if semantics change. |
| active | INTEGER | {0,1} | 1.0 | Soft enable/disable. |
| notes | TEXT (nullable) | free text | “Conflict inflates σ; never reduces σ.” | Non-executable notes. |

---

### 3.4. Class D — Policy (Decision Configuration)

> Human-curated policy choices. These tables define *how the system decides* — utility weights, safety thresholds, VOI priorities. They change when clinical or product policy changes.

#### D1. `objective_specs_v1`

**Purpose:** Utility function and scoring specifications for schedule optimization — defines how cognitive benefit, burden, and adherence are weighted in SAFE score computation (§2.16.3).

**1 Row =** One utility function specification with burden penalty λ, adherence scaling, and severity-weighted domain weights.

**Executed When:** Design-time policy; read at runtime optimization (Stage G).

**Input Tables (reads from):** None

**Output Tables (consumed by):** decision_trace_v1, recommendation_runs_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| objective_id | TEXT (PK) | OBJ_[A-Z0-9_]+ | OBJ_CRCI_RECOVERY_BALANCED_V1 | Stable objective ID. |
| objective_label | TEXT | free text | Balanced CRCI recovery | Human label. |
| outcome_terms_json | TEXT (JSON) | JSON array of term objects | [{"target_level":"node","target_id":"NODE_COG_PERCEPTION","direction":"decrease","weight":1.0}] | Benefit terms and weights. |
| risk_metric | TEXT | {expected,p10,p25,cvar10,worst_case} | cvar10 | Risk-sensitive summary statistic. |
| risk_aversion_lambda | REAL | >=0 | 0.5 | Scales risk penalty. |
| burden_weight | REAL | >=0 | 0.7 | Global weight on burden term. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |
| notes | TEXT (nullable) |  |  |  |

---

#### D2. `safety_policies_v1`

**Purpose:** System-level safety policies — trigger type → system behavior mappings that govern how the engine responds to safety-relevant patient states.

**1 Row =** One trigger type → system behavior mapping (e.g., 'suicidal ideation detected → block all recommendations, escalate immediately').

**Executed When:** Design-time clinical policy; read at runtime safety gating (Phase 0, Stage D, Stage G).

**Input Tables (reads from):** None

**Output Tables (consumed by):** contraindication_eval_trace_v1, recommendation_runs_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| safety_policy_id | TEXT (PK) | SAFE_[A-Z0-9_]+ | SAFE_UNKNOWN_NEUROPATHY_POLICY_V1 | Stable policy ID. |
| trigger_type | TEXT | {contra_rule_true,contra_rule_unknown,out_of_scope_model,...} | contra_rule_unknown | What kind of trigger. |
| system_behavior | TEXT | {block_action,force_question,escalate,...} | force_question | Deterministic engine behavior. |
| message_template | TEXT | free text | Please answer neuropathy severity to ensure safety. | User-facing message. |
| priority | INTEGER | >=1 | 1 | Lower runs first. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |

---

#### D3. `escalation_policies_v1`

**Purpose:** Escalation protocols — defines when and how the system escalates beyond its scope to human clinicians.

**1 Row =** One escalation protocol definition (threshold, channel, urgency, required follow-up).

**Executed When:** Design-time clinical policy; read at runtime escalation handling.

**Input Tables (reads from):** None (ROOT — referenced by recommendation_runs_v1)

**Output Tables (consumed by):** recommendation_runs_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| escalation_id | TEXT (PK) | ESC_[A-Z0-9_]+ | ESC_REQUIRE_CLINICIAN_REVIEW_V1 | Stable escalation policy ID. |
| policy_label | TEXT | free text | Require clinician review | Human label. |
| system_behavior | TEXT | {block_all_actions,allow_only_low_burden,require_clinician_review,...} | require_clinician_review | Deterministic behavior. |
| allowed_action_classes_json | TEXT (JSON, nullable) | JSON array | ["sleep","stress_regulation"] | Allowed subset if restricting. |
| user_message | TEXT | free text | Safety uncertainty detected; review with clinician. | Output-safe message. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |

---

#### D4. `status_quo_rules_v1`

**Purpose:** Baseline dose assumptions — default activity levels for the counterfactual 'no change' scenario in intervention comparison.

**1 Row =** One baseline dose rule for one action (e.g., 'current sleep hygiene = 0 sessions/week').

**Executed When:** Design-time clinical policy; read at runtime scenario construction (Stage D).

**Input Tables (reads from):** action_catalog_v1.action_id

**Output Tables (consumed by):** scenario_definitions_v1 (baseline scenario)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| sq_rule_id | TEXT (PK) | SQR_[A-Z0-9_]+ | SQR_WALK_FROM_STEPCOUNT_V1 | Rule identifier. |
| action_id | TEXT (FK) | ACT_* | ACT_WALK_LOW_INT | Which action. |
| condition_expression | TEXT | deterministic DSL | context.has_wearable == true | When this rule applies. |
| baseline_source_type | TEXT | {feature,context,default} | feature | Where baseline comes from. |
| dose_infer_spec | TEXT | deterministic expression | map_steps_to_minutes(feature.FEAT_STEPS_D7_Z_V1) | How to infer dose. |
| default_dose | REAL (nullable) | >=0 | 0.0 | Fallback dose. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |

---

#### D5. `voi_rules_v1`

**Purpose:** Value-of-information policy parameters — governs adaptive question selection priorities and stopping criteria (Stage H).

**1 Row =** One VOI policy parameter or gating rule for adaptive questioning.

**Executed When:** Design-time product/clinical policy; read at runtime VOI selection (Stage H).

**Input Tables (reads from):** Polymorphic target_ref_id (node/feature)

**Output Tables (consumed by):** question_selection_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| voi_rule_id | TEXT (PK) | VOI_[A-Z0-9_]+ | VOI_WEIGHT_SLEEP_NODE_V1 | Rule identifier. |
| rule_type | TEXT | {weight_node,weight_feature,force_question,block_question,stop_condition,...} | weight_node | Rule function. |
| target_ref_type | TEXT | {node,feature,question,global} | node | What rule targets. |
| target_ref_id | TEXT (nullable) | NODE_* or FEAT_* or Q_* | NODE_SLEEP_DISRUPTION | Target. |
| weight_value | REAL (nullable) | >=0 | 1.5 | Weight multiplier. |
| max_questions_per_session | INTEGER (nullable) | >=0 | 6 | Hard cap. |
| version | INTEGER | >=1 | 1 | Version. |
| active | INTEGER | {0,1} | 1 | Soft enable/disable. |

---

### 3.5. Class E — Output (Session Results & Audit)

> Append-only per session. These tables capture everything that happens during a single engine execution — state estimates, scenarios, traces, and audit logs.

#### E1. `state_snapshots_v1`

**Purpose:** Bayesian state estimates — the patient's inferred latent state (μ, Σ) after each observation update. The core runtime data structure.

**1 Row =** One patient's Bayesian state estimate at one timestamp, with full posterior (information vector η, precision diagonal).

**Executed When:** Runtime (Stage C, after each Phase 2 update).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_estimator_specs_v1.estimator_id, node_priors_v1.prior_id

**Output Tables (consumed by):** scenario_definitions_v1, question_sequence_v1, modifier_eval_trace_v1, contraindication_eval_trace_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| state_id | TEXT (PK) | STATE_[A-Z0-9_]+ | STATE_20260122T103500_0001 | Unique per snapshot. |
| run_id | TEXT (FK) | RUN_[A-Z0-9_]+ | RUN_20260122_0007 | Must exist in recommendation_runs_v1.run_id. |
| subject_ref | TEXT | PAT_* or PROF_* | PROF_TELL2014_BASE_T1 | Required. |
| state_time | TEXT | ISO datetime | 2026-01-22T10:35:00-08:00 | Required; monotonic within run. |
| time_step_unit | TEXT | {day, week} | day | Must match simulator step used for edges in the run. |
| estimator_id | TEXT (FK) | EST_* | EST_GAUSSIAN_CONJUGATE_V1 | Must exist in state_estimator_specs_v1.estimator_id. |
| prior_ref_id | TEXT (FK) | PRIOR_* | PRIOR_BREAST_POSTTX_V1 | Must reference node priors bundle ID used. |
| node_beliefs_json | TEXT (JSON) | JSON map | {"NODE_FATIGUE":{"mean":0.8,"sd":0.6}} | Each node must include mean, sd; sd ≥ min_sigma_floor. |
| coverage_json | TEXT (JSON) | JSON object | {"n_obs_recent":7,"recency_days":3} | Required; schema fixed by you. |
| conflict_flags_json | TEXT (JSON) | JSON object | {"NODE_SLEEP_DISRUPTION":{"conflict_score":0.7}} | Must exist even if empty {}. |
| evidence_contributions_json | TEXT (JSON) | JSON array | [{"node_id":"NODE_FATIGUE","source_id":"FEAT_MFSI_Z_V1","w":0.4}] | Must list only actually used obs/features. |
| obs_used_count | INTEGER | ≥0 | 4.0 | Equals count of contributions used in update. |
| conflict_inflation_applied | INTEGER | {0,1} | 1.0 | 1 iff σ inflated by conflict rule. |
| missingness_inflation_applied | INTEGER | {0,1} |  | 1 iff σ inflated by missingness rule. |
| sigma_floor_applied | INTEGER | {0,1} | 1.0 | 1 iff any node sd was floored. |
| notes_json | TEXT (JSON) | JSON object | {"warnings":["no objective sleep measure"]} | Must exist even if {}. |

---

#### E2. `scenario_definitions_v1`

**Purpose:** What-if scenario configurations — defines baseline vs intervention comparisons for simulation.

**1 Row =** One what-if scenario configuration (baseline + candidate interventions).

**Executed When:** Runtime (Stage D scenario construction).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_snapshots_v1.state_id

**Output Tables (consumed by):** scenario_items_v1, simulation_trace_v1, schedule_plans_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| scenario_id | TEXT (PK) | SCEN_[A-Z0-9_]+ | SCEN_RUN_20260122_0007__SQ | Unique. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Must exist in recommendation_runs_v1. |
| scenario_type | TEXT | {status_quo, candidate} | status_quo | Required. |
| scenario_label | TEXT | free text | “Status quo projection” | Required. |
| base_state_id | TEXT (FK) | STATE_* | STATE_20260122T103500_0001 | Must exist in state_snapshots_v1. |
| start_date | TEXT | YYYY-MM-DD | 2026-01-22 00:00:00 | Required. |
| horizon_days | INTEGER | ≥1 | 28.0 | Must equal run horizon. |
| time_step_unit | TEXT | {day, week} | day | Must match edges_v1.time_step_unit. |
| anchor_calendar_json | TEXT (JSON) | JSON object | {"wake":"07:30","bed":"23:00"} | Required; {} allowed only if declared. |
| generation_policy | TEXT | {status_quo_rules_v1, template, heuristic_enum} | status_quo_rules_v1 | Required. |
| constraints_applied_json | TEXT (JSON) | JSON array | ["RULE_NEUROPATHY_G3_BLOCK_ACTIVITY_V1"] | Must list applied hard filters. |
| notes_json | TEXT (JSON) | JSON object | {"warnings":["baseline behavior assumed"]} | Must exist ({} ok). |

---

#### E3. `scenario_items_v1`

**Purpose:** Actions within each scenario — the specific interventions and doses being simulated.

**1 Row =** One action within one scenario with its assigned dose.

**Executed When:** Runtime (Stage D).

**Input Tables (reads from):** scenario_definitions_v1.scenario_id, action_catalog_v1.action_id

**Output Tables (consumed by):** simulation_trace_v1 (per-action effects)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| scenario_item_id | TEXT (PK) | SCENITEM_* | SCENITEM_000012 | Unique. |
| scenario_id | TEXT (FK) | SCEN_* | SCEN_RUN_20260122_0007__CAND_03 | Must exist in scenario_definitions_v1. |
| action_id | TEXT (FK) | ACT_* | ACT_WALK_LOW_INT | Must exist in action_catalog_v1/action_definitions_v1. |
| dose_value | REAL | — | 150.0 | Must respect action dose bounds. |
| dose_unit | TEXT | free text | MET_min_per_day | Must match action.dose_unit. |
| timing_plan_json | TEXT (JSON) | JSON object | {"anchor":"wake_time","offset_min":120,"window_width_min":60} | Required. |
| frequency_plan_json | TEXT (JSON) | JSON object | {"pattern":"daily"} | Required. |
| duration_days | INTEGER | ≥1 | 28.0 | Required. |
| stop_rules_json | TEXT (JSON) | JSON array | [{"if":"node.NODE_FATIGUE.mean>2","then":"reduce_30pct"}] | Must use your rule DSL if executable. |
| source_tag | TEXT | {status_quo_inferred, candidate_generated} | candidate_generated | Required. |
| notes_json | TEXT (JSON) | JSON object | {} | Must exist. |

---

#### E4. `schedule_plans_v1`

**Purpose:** Optimized schedule plans — the output of Stage G optimization, ranked by SAFE score.

**1 Row =** One complete optimized schedule plan with SAFE scores (Mode A and Mode B).

**Executed When:** Runtime (Stage G optimization).

**Input Tables (reads from):** recommendation_runs_v1.run_id, scenario_definitions_v1.scenario_id

**Output Tables (consumed by):** schedule_items_v1, decision_trace_v1, recommendation_runs_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| schedule_id | TEXT (PK) | SCHED_* | SCHED_RUN_20260122_0007__PRIMARY | Unique. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Must exist in recommendation_runs_v1. |
| source_scenario_id | TEXT (FK) | SCEN_* | SCEN_RUN_20260122_0007__CAND_03 | Must exist in scenario_definitions_v1. |
| plan_rank | INTEGER | ≥1 | 1.0 | 1 = primary; higher = alternatives. |
| plan_type | TEXT | {primary, alternative} | primary | Required. |
| objective_weights_json | TEXT (JSON) | JSON object | {"NODE_COG_INDEX":1.0,"NODE_FATIGUE":0.7} | Must match objective_specs_v1 used in run. |
| constraints_applied_json | TEXT (JSON) | JSON array | ["RULE_NEUROPATHY_G3_BLOCK_ACTIVITY_V1"] | Required. |
| expected_outcomes_json | TEXT (JSON) | JSON object | {"NODE_FATIGUE":{"mean_delta":-0.3,"p10":-0.7,"p90":0.1}} | Must be derived from simulation. |
| risk_summary_json | TEXT (JSON) | JSON object | {"p_fatigue_worsen":0.12} | Required. |
| utility_score | REAL | — | 0.42 | Must correspond to decision_trace scoring. |
| rationale_json | TEXT (JSON) | JSON array | ["Sleep regularity reduces HPA dysregulation under post-treatment scope"] | Must reference nodes/edges/constraints in principle. |
| created_at | TEXT | ISO datetime | 2026-01-22T10:36:20-08:00 | Required. |

---

#### E5. `schedule_items_v1`

**Purpose:** Scheduled actions within a plan — specific interventions with optimized doses and timing.

**1 Row =** One scheduled action within a plan, with pathway-optimized dose and timing.

**Executed When:** Runtime (Stage G).

**Input Tables (reads from):** schedule_plans_v1.schedule_id, action_catalog_v1.action_id

**Output Tables (consumed by):** None (consumed by UI for display)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| schedule_item_id | TEXT (PK) | SCHEDITEM_* | SCHEDITEM_000044 | Unique. |
| schedule_id | TEXT (FK) | SCHED_* | SCHED_RUN_20260122_0007__PRIMARY | Must exist in schedule_plans_v1. |
| action_id | TEXT (FK) | ACT_* | ACT_LIGHT_AM | Must exist. |
| dose_value | REAL | — | 10000.0 | Must respect action bounds. |
| dose_unit | TEXT | free text | lux_min | Must match action unit. |
| timing_plan_json | TEXT (JSON) | JSON object | {"anchor":"wake_time","offset_min":30,"window_width_min":60} | Required. |
| frequency_plan_json | TEXT (JSON) | JSON object | {"pattern":"daily"} | Required. |
| duration_days | INTEGER | ≥1 | 14.0 | ≤ horizon_days. |
| ramp_json | TEXT (JSON) | JSON object | {"start":5000,"end":10000,"steps":4} | Must be consistent with dose bounds. |
| stop_rules_json | TEXT (JSON) | JSON array | [{"if":"node.NODE_FATIGUE.mean>2","then":"pause"}] | Deterministic DSL if executable. |
| order_index | INTEGER | ≥0 |  | Used for UI ordering only. |

---

#### E6. `recommendation_runs_v1`

**Purpose:** Run header — one row per engine execution capturing who, when, what configuration, and which schedule was selected. All other Class E tables reference this.

**1 Row =** One engine execution session with full configuration snapshot and outcome references.

**Executed When:** Runtime (created at session start, updated at completion).

**Input Tables (reads from):** state_snapshots_v1.state_id, objective_specs_v1.objective_id, safety_policies_v1.safety_policy_id, escalation_policies_v1.escalation_id, outcome_anchors_v1.anchor_id, schedule_plans_v1.schedule_id

**Output Tables (consumed by):** All other Class E tables (via run_id FK)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| run_id | TEXT (PK) | RUN_* | RUN_20260122_0007 | Unique. |
| subject_ref | TEXT | PAT_* or PROF_* | PROF_TELL2014_BASE_T1 | Required. |
| started_at | TEXT | ISO datetime | 2026-01-22T10:35:00-08:00 | Required. |
| ended_at | TEXT | ISO datetime | 2026-01-22T10:36:45-08:00 | Required. |
| engine_commit_hash | TEXT | git hash | 9f3c2ab | Required. |
| policy_versions_json | TEXT (JSON) | JSON object | {"edges_v1":1,"action_catalog_v1":1} | Required. |
| random_seed | INTEGER | ≥0 | 133742.0 | Required. |
| time_step_unit | TEXT | {day, week} | day | Must match edges/priors used. |
| horizon_days | INTEGER | ≥1 | 28.0 | Required. |
| base_state_id | TEXT (FK) | STATE_* | STATE_20260122T103500_0001 | Must exist in state_snapshots_v1. |
| objective_spec_id | TEXT (FK) | OBJ_* | OBJ_CRCI_BALANCED_V1 | Must exist in objective_specs_v1. |
| safety_policy_id | TEXT (FK) | SAFE_* | SAFE_V1 | Must exist in safety_policies_v1. |
| escalation_policy_id | TEXT (FK) | ESC_* | ESC_REQUIRE_CLINICIAN_REVIEW_V1 | Must exist in escalation_policies_v1. |
| output_mode | TEXT | {index_mode, calibrated_mode} | index_mode | calibrated_mode only if anchor_id present. |
| anchor_id | TEXT (FK, nullable) | ANCHOR_* | ANCH_FACTCOG_V3_BREAST_POSTTX_V1 | Required iff calibrated_mode. |
| primary_schedule_id | TEXT (FK) | SCHED_* | SCHED_RUN_20260122_0007__PRIMARY | Must exist in schedule_plans_v1. |
| alternative_schedule_ids_json | TEXT (JSON) | JSON array | ["SCHED_RUN_...__ALT1"] | Must exist for each referenced schedule. |
| run_warnings_json | TEXT (JSON) | JSON array | ["out_of_scope_age"] | Must exist ([] ok). |
| p_rank_1_json | TEXT (JSON, nullable) | JSON object | {"INT_EXERCISE":0.62,"INT_CBT_I":0.18} | P(rank=1) per intervention from bootstrap resampling (§2.19). Populated by RT-G-RS. |
| decision_critical_edges_json | TEXT (JSON, nullable) | JSON array | ["EP_SLEEP_HPA_V1","EP_IL6_COG_V1"] | Edges where ±1 SE flip changes top-1 ranking (§2.19). Populated by RT-I-PC. |
| var_decomp_json | TEXT (JSON, nullable) | JSON object | {"literature":0.42,"measurement":0.18,"structural":0.22,"proxy":0.11,"missing":0.07} | 5-source variance decomposition fractions (§2.20.1). Populated by RT-I-VD. |
| discovery_scores_json | TEXT (JSON, nullable) | JSON object | {"EP_SLEEP_HPA":3.2,"EP_IL6_COG":2.8} | \|elasticity\| × SE_eff per edge (§4.5). Populated by RT-I-VD. |
| evsi_top_edges_json | TEXT (JSON, nullable) | JSON object | {"EP_SLEEP_HPA":0.045,"EP_IL6_COG":0.032} | Top-k EVSI scores (§4.5). Populated by RT-I-EV. Only in RESEARCH output mode. |
| archetype_id | TEXT (nullable) | ARCH_* | ARCH_HIGH_INFLAM_LOW_SLEEP | Population archetype assignment (§4.5). Populated by RT-I-PA. Only in POPULATION output mode. |
| archetype_distance | REAL (nullable) | ≥0 | 1.23 | Mahalanobis distance to archetype centroid. |
| voi_method | TEXT (nullable) | {none, evsi_mc, evpi_mc, heuristic} | evsi_mc | Only for voi_ranked. |

---

#### E7. `simulation_trace_v1`

**Purpose:** Monte Carlo simulation trace records — per-draw results for provenance and decision stability analysis (§2.19).

**1 Row =** One Monte Carlo simulation trace record (summary statistics across 10,000 draws for one scenario).

**Executed When:** Runtime (Stage F MC simulation).

**Input Tables (reads from):** recommendation_runs_v1.run_id, scenario_definitions_v1.scenario_id

**Output Tables (consumed by):** decision_trace_v1 (rank stability computation)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| sim_trace_id | TEXT (PK) | SIMTR_* | SIMTR_RUN_20260122_0007__SCEN_03 | Unique. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Required. |
| scenario_id | TEXT (FK) | SCEN_* | SCEN_RUN_20260122_0007__CAND_03 | Must exist in scenario_definitions_v1. |
| n_samples | INTEGER | ≥1 | 2000.0 | Required. |
| seed_used | INTEGER | ≥0 | 133742.0 | Must equal run seed or deterministic derivation. |
| edges_used_json | TEXT (JSON) | JSON array | ["EP__ER_A_SLEEP__...__V1"] | Must list matched edges_v1 rows actually used. |
| bridges_used_json | TEXT (JSON) | JSON array | ["DBR_ACT_WALK_LOW_INT__NODE_FATIGUE__V1"] | Must list dose_bridges_v1 rows used. |
| modifiers_applied_json | TEXT (JSON) | JSON array | [{"modifier_id":"MOD_AGE_SAT","applies_to":"beta","mult":0.9}] | Must be consistent with modifier eval trace. |
| constraint_triggers_json | TEXT (JSON) | JSON array | [{"rule_id":"CONSTR_HPA_POSTEX_TIMECOURSE_V1","count":12}] | Required ([] ok). |
| sim_warnings_json | TEXT (JSON) | JSON array | ["scope_fallback_edge_param"] | Required ([] ok). |

---

#### E8. `decision_trace_v1`

**Purpose:** Decision audit trail — every ranked decision the engine made with SAFE scores, stability classification, and decision-critical edges.

**1 Row =** One decision the engine made with rationale, SAFE score, and stability classification.

**Executed When:** Runtime (Stage G/I).

**Input Tables (reads from):** recommendation_runs_v1.run_id, objective_specs_v1.objective_id, schedule_plans_v1.schedule_id

**Output Tables (consumed by):** None (consumed by UI and audit)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| decision_trace_id | TEXT (PK) | DTR_* | DTR_RUN_20260122_0007 | Unique. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Required. |
| objective_spec_id | TEXT (FK) | OBJ_* | OBJ_CRCI_BALANCED_V1 | Must match run objective_spec_id. |
| selection_rule | TEXT | {max_expected_utility, risk_averse_quantile, cvar_min} | risk_averse_quantile | Required. |
| candidate_scores_json | TEXT (JSON) | JSON array | [{"schedule_id":"SCHED_...","utility":0.42,"risk":0.12}] | Must include all candidates considered. |
| rejected_candidates_json | TEXT (JSON) | JSON array | [{"scenario_id":"SCEN_..","reason":"hard_block_rule"}] | Required ([] ok). |
| chosen_schedule_id | TEXT (FK) | SCHED_* | SCHED_RUN_20260122_0007__PRIMARY | Must exist. |
| alternatives_generated_json | TEXT (JSON) | JSON array | [{"schedule_id":"SCHED_...ALT1","pattern":"low_burden"}] | Must correspond to schedule_plans_v1 rows. |
| decision_warnings_json | TEXT (JSON) | JSON array | ["all_activity_blocked_returned_sleep_only"] | Required ([] ok). |

---

#### E9. `contraindication_eval_trace_v1`

**Purpose:** Safety evaluation audit trail — every safety rule evaluation for every action in every scenario.

**1 Row =** One safety rule evaluation for one action in one scenario (pass/fail/modify).

**Executed When:** Runtime (safety filter evaluation).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_snapshots_v1.state_id, scenario_definitions_v1.scenario_id, action_catalog_v1.action_id, contraindication_rules_v1.rule_id

**Output Tables (consumed by):** None (consumed by safety audit)

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| trace_id | TEXT (PK) | TR_* | TR_20260122_000088 | Unique. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Required. |
| timestamp | TEXT | ISO datetime | 2026-01-22T10:35:12-08:00 | Required. |
| subject_ref | TEXT | PAT_* or PROF_* | PROF_TELL2014_BASE_T1 | Required. |
| state_id | TEXT (FK, nullable) | STATE_* | STATE_... | Required if rule uses node.* symbols. |
| scenario_id | TEXT (FK, nullable) | SCEN_* | SCEN_... | Fill when evaluated during candidate filtering. |
| action_id | TEXT (FK, nullable) | ACT_* | ACT_WALK_LOW_INT | NULL allowed for global rules. |
| rule_id | TEXT (FK) | RULE_* | RULE_NEUROPATHY_G3_BLOCK_ACTIVITY_V1 | Must exist and be active. |
| evaluation_result | TEXT | {true, false, unknown} | unknown | Tri-valued evaluation. |
| severity_applied | TEXT | {hard_block, soft_penalty, require_question, escalate, none} | require_question | Must match rule severity + unknown policy. |
| inputs_used_json | TEXT (JSON) | JSON object | {"context.neuropathy_grade":null} | Must include values actually read. |
| missing_inputs_json | TEXT (JSON) | JSON array | ["context.neuropathy_grade"] | Required when unknown. |
| action_taken | TEXT | {blocked_action, penalized, asked_question, escalated, none} | asked_question | Deterministic consequence. |
| notes_json | TEXT (JSON) | JSON object | {"message_id":"Q_NEUROPATHY_GRADE"} | Must exist ({} ok). |

---

#### E10. `question_selection_trace_v1`

**Purpose:** VOI-based question selection audit — why each question was chosen, its expected information gain, and alternatives considered.

**1 Row =** One question selection decision with VOI rationale and expected variance reduction.

**Executed When:** Runtime (Stage H adaptive questioning).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_snapshots_v1.state_id

**Output Tables (consumed by):** question_sequence_v1

| Column | Type | Controlled Vocab | Example | Notes |
|--------|------|-----------------|---------|-------|
| qtrace_id | TEXT (PK) | QTR_[A-Z0-9_]+ | QTR_RUN_20260122_0007__STEP_02 | Unique selection event. |
| run_id | TEXT (FK) | RUN_* | RUN_20260122_0007 | Links to recommendation run. |
| state_id | TEXT (FK) | STATE_* | STATE_20260122T1030 | Posterior used for decision sensitivity. |
| step_index | INTEGER | ≥0 | 2.0 | 0-based selection loop index. |
| selection_stage | TEXT | {safety_prereq, identifiability_prereq, voi_ranked} | voi_ranked | Which layer chose the question. |
| burden_budget_max | REAL | ≥0 | 1.5 | Remaining burden budget. |
| candidate_question_ids_json | TEXT (JSON) | JSON array | ["Q_PSQI_TOTAL","Q_ISI_TOTAL"] | Candidate pool after applicability filtering. |
| filtered_out_json | TEXT (JSON) | JSON array of objects | [{"question_id":"Q_X","reason":"inapplicable_scope"}] | Deterministic reasons. |
| chosen_question_ids_json | TEXT (JSON) | JSON array | ["Q_PSQI_TOTAL"] | Final chosen questions. |
| prerequisite_missing_inputs_json | TEXT (JSON, nullable) | JSON array | ["context.neuropathy_grade"] | Only for prereq layers. |
| voi_method | TEXT (nullable) | {none, evsi_mc, evpi_mc, heuristic} | evsi_mc | Only for voi_ranked. |
| voi_params_json | TEXT (JSON, nullable) | JSON object | {"n_mc":400,"utility_ref":"OBJ_MAIN_V1"} | VOI computation parameters. |
| voi_scores_json | TEXT (JSON, nullable) | JSON array of objects | [{"question_id":"Q_PSQI_TOTAL","voi":0.12,"burden":0.2}] | Must include all candidates for audit. |
| expected_decision_change_prob | REAL (nullable) | [0,1] | 0.35 | Optional but useful: P(argmax changes). |
| predicted_rank_instability | REAL (nullable) | ≥0 | 0.18 | Optional: schedule-rank dispersion proxy. |
| warnings_json | TEXT (JSON) | JSON array | ["used_noise_fallback_default"] | Any fallbacks. |
| created_at | TEXT | ISO datetime | 2026-01-22T10:40:00-08:00 | Timestamp. |
| version | INTEGER | ≥1 | 1.0 | Schema semantics version. |

---

#### E11. `modifier_eval_trace_v1`

**Purpose:** Personalization audit trail — every modifier evaluation showing which patient variables adjusted which edges by how much.

**1 Row =** One modifier evaluation for one edge × one variable × one session.

**Executed When:** Runtime (Stage E modifier resolution before simulation).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_snapshots_v1.state_id, baseline_modifier_definitions_v1.modifier_id, edges_v1.edge_param_id, variable_definitions_v1.variable_id

**Output Tables (consumed by):** None (consumed by personalization audit)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| eval_id (PK) | TEXT (PK) | MEVAL_[TIMESTAMP]_[HASH] | MEVAL_20260221_a3f2 | Globally unique per evaluation. | Stable trace identifier. |
| run_id (FK → recommendation_runs_v1) | TEXT (FK) | RUN_* | RUN_20260221T143022_a3f2 | Must exist. | Which session produced this. |
| state_id (FK → state_snapshots_v1) | TEXT (FK) | STATE_* | STATE_20260221_001 | Must exist. | Patient state at evaluation time. |
| modifier_id (FK → baseline_modifier_definitions_v1) | TEXT (FK) | MOD_* | MOD_APOE4_EXERCISE | Must exist. | Which modifier was evaluated. |
| edge_param_id (FK → edges_v1) | TEXT (FK) | EP_* | EP_EXERCISE_BDNF_001 | Must exist. | Which edge was modified. |
| variable_id (FK → variable_definitions_v1) | TEXT (FK) | VAR_* | VAR_APOE_STATUS | Must exist. | Which patient variable drove this modifier. |
| variable_value | TEXT | free text | e4_carrier | NOT NULL. The patient's value. | Actual patient characteristic value. |
| multiplier_applied | REAL | [0.5, 2.0] | 1.40 | Within cumulative guardrails. | The multiplicative adjustment applied. |
| evidence_grade | ENUM | {A, B, C, D} | A | From modifier definition. | Evidence quality of this modifier. |
| beta_before | REAL | any numeric | 0.35 | Edge β before modification. | Audit: original parameter value. |
| beta_after | REAL | any numeric | 0.49 | Edge β after modification. | Audit: modified parameter value. |
| se_inflation_applied | REAL | ≥1.0 | 1.0 | Grade-based SE inflation. | Uncertainty increase from modifier grade. |
| created_at | TIMESTAMP | ISO 8601 | 2026-02-21T14:30:22Z | NOT NULL. Auto-generated. | When this evaluation occurred. |
| notes | TEXT (nullable) | free text | APOE e4 carrier: 40% exercise benefit amplification | No executable logic. | Human-readable audit note. |

---

#### E12. `question_sequence_v1`

**Purpose:** Adaptive intake record — every question asked and answered (or skipped) in sequence, with state before/after and realized information gain.

**1 Row =** One question asked and answered (or skipped) in one session, with realized variance reduction.

**Executed When:** Runtime (adaptive intake processing).

**Input Tables (reads from):** recommendation_runs_v1.run_id, state_snapshots_v1.state_id (before/after), question_bank_v1.question_id, question_observation_models_v1.model_id, question_selection_trace_v1.qtrace_id

**Output Tables (consumed by):** state_snapshots_v1 (updated state after answer)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| sequence_id (PK) | TEXT (PK) | QSEQ_[TIMESTAMP]_[NNN] | QSEQ_20260221_001 | Globally unique. | Stable sequence record identifier. |
| run_id (FK → recommendation_runs_v1) | TEXT (FK) | RUN_* | RUN_20260221T143022_a3f2 | Must exist. | Which session. |
| question_id (FK → question_bank_v1) | TEXT (FK) | Q_* | Q_SLEEP_QUALITY_GLOBAL | Must exist. | Which question was asked. |
| sequence_position | INTEGER | ≥1 | 3 | Unique within run_id. Monotonically increasing. | Order in which question was presented. |
| state_id_before (FK → state_snapshots_v1) | TEXT (FK) | STATE_* | STATE_20260221_002 | Must exist. | Patient state before this answer. |
| state_id_after (FK → state_snapshots_v1) | TEXT (FK) | STATE_* | STATE_20260221_003 | Must exist. | Patient state after incorporating answer. |
| observation_model_id (FK → question_observation_models_v1) | TEXT (FK) | QOM_* | QOM_SLEEP_QUALITY_NODE | Must exist. | How this answer updates the model. |
| selection_trace_id (FK → question_selection_trace_v1) | TEXT (FK) | QTRACE_* | QTRACE_20260221_003 | Must exist. | Links to VOI rationale for selection. |
| response_status | ENUM | {answered, skipped, timed_out} | answered | NOT NULL. | Whether patient answered. |
| response_value | TEXT (nullable) | free text | 3 | Required if response_status=answered. | Patient's response. |
| response_z_score | REAL (nullable) | any numeric | -0.85 | Normalized response in z-score units. | Standardized answer for model update. |
| variance_reduction_achieved | REAL (nullable) | [0,1] | 0.08 | Fraction of posterior variance reduced. | Realized information gain from this answer. |
| response_time_seconds | REAL (nullable) | ≥0 | 12.5 | Time to answer. | Engagement metric. |
| created_at | TIMESTAMP | ISO 8601 | 2026-02-21T14:31:45Z | NOT NULL. | Timestamp. |
| notes | TEXT (nullable) | free text | Patient reported poor sleep quality | No executable logic. | Audit notes. |

---

#### E13. `extraction_audit_v1`

**Purpose:** Pipeline quality monitoring — records each extraction stage execution for each paper with success/failure counts and rejection reasons.

**1 Row =** One extraction stage execution for one paper (stage × study combination).

**Executed When:** Per-paper extraction (all pipeline stages EX-P0 through EX-P5).

**Input Tables (reads from):** study_registry_v1.study_id

**Output Tables (consumed by):** None (consumed by pipeline QA dashboard)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------|
| audit_id (PK) | TEXT (PK) | EAUD_[STUDY]_[STAGE] | EAUD_SMITH2023_P1 | Globally unique per study×stage. | Stable audit record identifier. |
| study_id (FK → study_registry_v1) | TEXT (FK) | STUDY_* | STUDY_SMITH_2023 | Must exist. | Which paper was extracted. |
| pipeline_stage | ENUM | {P0_triage, P1_extraction, TB_trust_boundary, P2_harmonization, P2E_extended, P3_assimilation, P4_aggregation, P5_sufficiency} | P1_extraction | NOT NULL. | Which pipeline stage this audit covers. |
| agent_id | TEXT (nullable) | free text | AG3_CohortAgent | For P1: which agent ran. | Specific agent within a stage. |
| status | ENUM | {success, partial, failed, skipped} | success | NOT NULL. | Outcome of this stage. |
| records_input | INTEGER | ≥0 | 15 | NOT NULL. | Records entering this stage. |
| records_output | INTEGER | ≥0 | 12 | NOT NULL. | Records exiting this stage. |
| records_rejected | INTEGER | ≥0 | 3 | input - output ≥ rejected. | Records filtered/rejected. |
| rejection_reasons_json | JSONB (nullable) | Array of {reason, count} | [{"reason":"ambiguous_parse","count":2}] | Required if records_rejected > 0. | Why records were rejected. |
| quality_flags_json | JSONB (nullable) | Array of flag strings | ["low_confidence_span", "sign_ambiguity"] | Quality issues detected. | Pipeline quality monitoring. |
| execution_time_seconds | REAL | ≥0 | 45.2 | NOT NULL. | Performance monitoring. |
| llm_tokens_used | INTEGER (nullable) | ≥0 | 3200 | For LLM-involving stages only. | Cost tracking. |
| deterministic_parser_used | INTEGER | {0, 1} | 1 | 1 if trust boundary parser ran. | Trust boundary audit (§2.5.4). |
| created_at | TIMESTAMP | ISO 8601 | 2026-02-21T10:15:30Z | NOT NULL. | Timestamp. |
| operator_id | TEXT (nullable) | free text | auto_pipeline_v1 | Who/what ran this stage. | Provenance tracking. |
| notes | TEXT (nullable) | free text | 3 records had ambiguous SE/SD distinction | No executable logic. | Human notes. |

---



---




---

#### C6. `chain_validation_results_v1`

**Purpose:** Persists chain-vs-direct validation results from §2.13 — Z-scores, triage tiers, AV scores, discrepancy classifications, and SE inflation feedback per testable pathway.

**1 Row =** One pathway's chain-vs-direct comparison result.

**Executed When:** EX-P5 Sufficiency & Coherence Check.

**Input Tables (reads from):** pathways_v1.pathway_id, edges_v1 (beta_mean, beta_se), edge_evidence_v1 (direct RCT rows), build_manifests_v1.build_id

**Output Tables (consumed by):** edges_v1 (SE inflation feedback via coherence_flag, se_inflation_coherence)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------| 
| cv_id (PK) | TEXT | CV_{pathway_id}_V{version} | CV_PW_NEUROINFLAM_V1 | Globally unique. | Stable result identifier. |
| pathway_id (FK → pathways_v1) | TEXT | PW_* | PW_NEUROINFLAMMATION | Must exist. | Which pathway tested. |
| chain_length | INTEGER | ≥2 | 4 | NOT NULL. | Number of edges in chain. |
| edges_in_chain_json | JSONB | Array of EP_* | ["EP_IL6_NEUROINFLAM_V1"] | Every element in edges_v1. | Compiled edges in chain. |
| beta_chain | REAL | — | 0.018 | NOT NULL. Product of edge betas. | Chain-mediated total effect. |
| se_chain | REAL | >0 | 0.007 | NOT NULL. Delta-method propagated. | Chain effect uncertainty. |
| beta_direct | REAL (nullable) | — | 0.022 | NULL if no RCT shortcut. | Direct RCT evidence. |
| se_direct | REAL (nullable) | >0 | 0.009 | NULL if no RCT shortcut. | Direct evidence SE. |
| z_statistic | REAL (nullable) | ≥0 | 1.23 | NULL if untestable. | Chain-vs-direct discrepancy Z. |
| triage_tier | ENUM | {PASS, MONITOR, INVESTIGATE, ALARM, UNTESTABLE} | PASS | NOT NULL. Z<1.5/1.5-2.0/2.0-3.0/≥3.0/no direct. | §2.13 triage. |
| av_score | REAL (nullable) | [0,1] | 0.87 | NULL if untestable. | Alignment Validity composite. |
| failure_mode | ENUM (nullable) | {NONE, MEDIATION_LEAK, COLLIDER_BIAS, TEMPORAL_MISMATCH, SCALE_INCOMPATIBILITY, POPULATION_DRIFT, MISSING_MODERATOR} | NONE | NULL if PASS/UNTESTABLE. | §2.13.2 discrepancy class. |
| remediation | TEXT (nullable) | free text | — | NULL if PASS. | Suggested fix. |
| se_inflation_applied | REAL | [1.0, 2.0] | 1.0 | 1.0 = no inflation. | Feedback to edges_v1. |
| build_id (FK → build_manifests_v1) | TEXT | BLD_* | BLD_20250601 | Must exist. | Build provenance. |
| version | INTEGER | ≥1 | 1 | Increment on rebuild. | Versioning. |

---

#### C7. `publication_bias_results_v1`

**Purpose:** Persists publication bias assessment results per edge from §2.12.1 — Egger regression, trim-and-fill, leave-one-out, and overall risk classification.

**1 Row =** One edge's publication bias assessment.

**Executed When:** EX-P4B Publication Bias Assessment.

**Input Tables (reads from):** edges_v1.edge_param_id, edge_evidence_v1 (per-study betas and SEs)

**Output Tables (consumed by):** edges_v1 (pub_bias_risk, se_inflation_pub_bias)

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------| 
| pb_result_id (PK) | TEXT | PBR_{edge_param_id} | PBR_EP_SLEEP_HPA_V1 | Globally unique. | Stable result ID. |
| edge_param_id (FK → edges_v1) | TEXT | EP_* | EP_SLEEP_HPA_V1 | Must exist. | Which compiled edge. |
| k_studies | INTEGER | ≥1 | 14 | NOT NULL. | Study count. |
| egger_intercept | REAL (nullable) | — | 1.34 | NULL if k<10. | Egger regression intercept. |
| egger_p_value | REAL (nullable) | [0,1] | 0.08 | NULL if k<10. | Egger test p-value. |
| egger_significant | BOOLEAN (nullable) | — | FALSE | At p<0.10. | Binary flag. |
| n_trimmed | INTEGER (nullable) | ≥0 | 2 | NULL if k<10. | Trim-and-fill additions. |
| beta_adjusted_tf | REAL (nullable) | — | 0.024 | NULL if k<10. | Adjusted β after trim-and-fill. |
| loo_max_shift | REAL (nullable) | ≥0 | 0.004 | NULL if k<3. | Largest β shift from LOO. |
| loo_influential_json | JSONB (nullable) | Array of STUDY_* | ["STUDY_X"] | NULL if k<3. | Influential studies. |
| bias_risk | ENUM | {LOW, MODERATE, HIGH, INSUFFICIENT_K} | LOW | NOT NULL. | Overall assessment. |
| se_inflation_pub_bias | REAL | [1.0, 1.5] | 1.0 | Feedback to edges_v1.beta_se. | Publication bias SE inflation. |
| build_id (FK → build_manifests_v1) | TEXT | BLD_* | BLD_20250601 | Must exist. | Build provenance. |
| version | INTEGER | ≥1 | 1 | Increment on rebuild. | Versioning. |

---

#### A33. `mid_thresholds_v1`

**Purpose:** Minimally Important Difference thresholds per cognitive domain (§2.20.2). Curated clinical anchors for severity classification and dose optimization ceiling.

**1 Row =** One cognitive domain's MID threshold set.

**Executed When:** Design-time authoring; read by RT-I-SM (SeverityMapper) and RT-G-SF (dose optimization).

**Input Tables (reads from):** None (ROOT — curated).

**Output Tables (consumed by):** recommendation_runs_v1 (severity mapping), RT-G-SF (dose ceiling).

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------| 
| domain_id (PK) | TEXT | COG_* | COG_PROCESSING_SPEED | Maps to cognitive node_domain. | Target domain. |
| d_MID | REAL | >0 | 0.20 | Minimum clinically meaningful Cohen's d. | Clinical significance threshold. |
| d_CE | REAL | >d_MID | 0.50 | Clinically excellent response. | Upper anchor. |
| d_plateau | REAL | ≥d_CE | 0.80 | Diminishing returns threshold. | Dose optimization ceiling. |
| anchor_source | TEXT | free text | Wefel et al., 2011 | NOT NULL. | Calibration evidence. |
| anchor_method | ENUM | {distribution_based, anchor_based, expert_consensus} | anchor_based | NOT NULL. | Derivation method. |
| version | INTEGER | ≥1 | 1 | Increment on change. | Versioning. |
| active | INTEGER | {0,1} | 1 | Soft disable. | — |

---

#### D6. `complexity_scaling_results_v1`

**Purpose:** Persists complexity-scaling validation results from §2.13.1 — offline batch analysis of model stability across 4×3 degradation configurations.

**1 Row =** One configuration's stability result.

**Executed When:** Offline validation (VAL-01 chain).

**Input Tables (reads from):** edges_v1, pathways_v1 (full model specification).

**Output Tables (consumed by):** None (analysis output — consumed by human review).

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------| 
| cs_id (PK) | TEXT | CS_{h}_{v}_V{ver} | CS_FULL_FULL7_V1 | Globally unique. | Stable result ID. |
| horizontal_level | ENUM | {FULL, DROP_E, DROP_DE, DROP_CDE} | FULL | NOT NULL. | Edge removal level. |
| vertical_level | ENUM | {FULL_7LAYER, REDUCED_3LAYER, MINIMAL_1LAYER} | FULL_7LAYER | NOT NULL. | Layer simplification. |
| n_edges_active | INTEGER | ≥0 | 112 | NOT NULL. | Edges remaining. |
| n_layers_active | INTEGER | {1,3,7} | 7 | NOT NULL. | Heterogeneity layers active. |
| top_5_interventions_json | JSONB | Array of INT_* | ["INT_EXERCISE","INT_CBT_I"] | NOT NULL. | Top-5 ranking at this config. |
| flip_rate_vs_full | REAL | [0,1] | 0.0 | NOT NULL. Top-5 change fraction. | Ranking instability. |
| mean_beta_shift | REAL | ≥0 | 0.002 | NOT NULL. Average \|Δβ\|. | Parameter sensitivity. |
| fragile_edges_json | JSONB (nullable) | Array of EP_* | ["EP_SLEEP_HPA_V1"] | Edges causing flip>0.2. | Fragile assumptions. |
| mc_draws | INTEGER | >0 | 10000 | NOT NULL. | Draws used. |
| run_timestamp | TEXT | ISO datetime | 2025-06-15T10:00:00Z | NOT NULL. | When analysis ran. |
| version | INTEGER | ≥1 | 1 | Versioning. | — |

---

#### D7. `population_archetypes_v1`

**Purpose:** Population archetype definitions and per-patient assignments from §4.5. GMM-derived cluster centroids and patient-to-archetype mapping.

**1 Row =** One archetype definition (centroids) OR one patient assignment (depending on archetype_type).

**Executed When:** RT-I-PA (PopulationArchetypeAssigner) in POPULATION output mode.

**Input Tables (reads from):** state_snapshots_v1 (posterior feature space).

**Output Tables (consumed by):** recommendation_runs_v1.archetype_id.

| Column | Type | Controlled Vocab | Example | Rules | Purpose |
|--------|------|-----------------|---------|-------|---------| 
| archetype_id (PK) | TEXT | ARCH_* | ARCH_HIGH_INFLAM_LOW_SLEEP | Globally unique. | Stable archetype ID. |
| archetype_label | TEXT | free text | High-Inflammation Low-Sleep | NOT NULL. | Human-readable name. |
| k_clusters | INTEGER | ≥1 | 5 | BIC-selected. | Number of GMM clusters. |
| bic_score | REAL | — | -1234.5 | NOT NULL. | Model selection score. |
| centroid_json | JSONB | Object: {node_id: z_value} | {"NODE_IL6":1.2,"NODE_SLEEP":-0.8} | Per-node cluster center. | Archetype definition. |
| n_patients_assigned | INTEGER | ≥0 | 142 | Updated as patients are assigned. | Cluster size. |
| prevalence | REAL | [0,1] | 0.28 | n_assigned / total. | Cluster prevalence. |
| characteristic_interventions_json | JSONB (nullable) | Array of INT_* | ["INT_ANTI_INFLAM","INT_CBT_I"] | Top interventions for this archetype. | Clinical shortcut. |
| model_version | INTEGER | ≥1 | 1 | Increment when retrained. | Versioning. |
| active | INTEGER | {0,1} | 1 | Soft disable. | — |

---


---

*End of Complete Table Schemas v4.0*

**Supersedes:** v3.0. Added 5 new tables (C6 chain_validation_results, C7 publication_bias_results, A33 mid_thresholds, D6 complexity_scaling_results, D7 population_archetypes). Added 6 new columns to edges_v1 (pub_bias_risk, se_inflation_pub_bias, coherence_flag, se_inflation_coherence, e_value, robustness_value). Added 9 new columns to recommendation_runs_v1 (p_rank_1_json, decision_critical_edges_json, var_decomp_json, discovery_scores_json, evsi_top_edges_json, archetype_id, archetype_distance, voi_method).
