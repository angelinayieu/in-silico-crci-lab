═══════════════════════════════════════════════════════════════════════════
 CRCI — SYS_EXTRACTION ADDENDUM: FULL-SPECTRUM PARAMETER EXTRACTION
 Purpose: Extend the extraction pipeline to cover ALL 7 parameter types
          the algorithm needs, not just edge evidence.
 Relationship: Addendum to SYS_EXTRACTION_COMPLETE.md. Same architecture.
               Same Canonical Reader → agent → trust boundary → aggregation
               pattern. New agents, extended agents, and 6 new compilers.
═══════════════════════════════════════════════════════════════════════════

COMPANION DOCUMENT CROSS-REFERENCES
────────────────────────────────────
This Addendum is authoritative for: agent definitions (AG11, AG03-EXT,
AG05-EXT, AG06-EXT, AG08-EXT), trust boundary extensions for non-edge
parameters (TB-PSYCH, TB-NORMS, TB-DOSE, TB-TEMPORAL, TB-SUBGROUP),
and the 6 compilers (psychometric, norms, temporal, dose-response,
synergy, modifier).

The following companion docs extend adjacent concerns. When Claude Code
receives this Addendum, it may also receive these at prompt time:

  O. Routing Protocol — 27 study_subtypes (including the 4 this
     Addendum added), meta-analysis multi-product routing, double-
     counting prevention, and 23 LLM guardrails. Authoritative for
     PAPER CLASSIFICATION and ROUTING DECISIONS.

  P. Intelligence Maximization — study_annotations_v1 schema, 22
     annotation categories, AG10 (StrategicIntelAgent), annotation
     emission rules per agent. Authoritative for ANNOTATION SYSTEM.
     NOTE: Every agent defined in this Addendum (AG11, AG03-EXT, etc.)
     should ALSO emit typed annotations alongside SpanLabels, per
     Intelligence Maximization §4.

  Q. Treatment Protocol — Component inventory (the bridge between
     paper classification and agent activation), precision cascade,
     completeness tracking. Authoritative for MULTI-YIELD EXTRACTION.

  R. Conversion Validity Matrix — Executable conversion gates for
     effect-size conversions. Authoritative for edge evidence
     conversions. This Addendum's TB extensions (Part 5) cover
     non-edge conversions (psychometric, temporal, dose-response,
     normative), which are a DIFFERENT domain.

Where this Addendum and companion docs overlap, the companion doc
is authoritative for its stated domain. This Addendum is authoritative
for agent implementation details and compiler logic.


═══════════════════════════════════════════════════════════════════════════
 PART 1: THE GAP AND THE FIX
═══════════════════════════════════════════════════════════════════════════

The algorithm consumes 7 parameter types. The extraction pipeline
currently has a full pathway for 1:

  TYPE 1: edge evidence → IVW → edges_v1              ✓ EXISTS
  TYPE 2: psychometrics → ??? → instruments_v1          THIS ADDENDUM
  TYPE 3: population norms → ??? → context_matched_priors THIS ADDENDUM
  TYPE 4: temporal curves → ??? → recovery_params +      THIS ADDENDUM
                                   intervention_kernels
  TYPE 5: dose-response → ??? → dose_response_params     THIS ADDENDUM
  TYPE 6: synergy data → ??? → synergy_registry          THIS ADDENDUM
  TYPE 7: subgroup effects → ??? → modifier_registry      THIS ADDENDUM

The fix: extend the existing pipeline with 3 new agents, 4 agent
extensions, new trust boundary rules, and 6 compiler subsystems.
All following the SAME architecture pattern as edge evidence.


═══════════════════════════════════════════════════════════════════════════
 PART 2: PAPER TYPE ROUTING EXTENSION
 Extends: EX-P0-S2 (relevance screening) + EX-P0-S3 (mode selection)
═══════════════════════════════════════════════════════════════════════════

Add 4 new paper subtypes to the P0 classifier:

  PSYCHOMETRIC_VALIDATION — paper primarily reports instrument
    reliability, validity, factor structure in cancer/clinical populations
    Route: STANDARD mode. Activate AG11 (new). Skip AG05-AG07.

  NORMATIVE_COHORT — large cohort study reporting population-level
    cognitive scores by cancer type/phase without intervention
    Route: STANDARD mode. Activate AG03-extended, AG04-extended.

  DOSE_RESPONSE_STUDY — RCT or systematic review specifically reporting
    dose-response relationships for cognitive interventions
    Route: DEEP mode. Activate AG06-extended, AG05.

  LONGITUDINAL_FOLLOWUP — study with 3+ timepoints measuring cognitive
    trajectory during/after intervention or cancer treatment
    Route: DEEP mode. Activate AG08-extended, AG05.

The P0 classifier prompt (llm/prompts/ptc_prompt.txt) is updated to
include these 4 subtypes. The existing 23 subtypes remain unchanged.
Total subtypes: 27.

Relevance screening update: Papers matching these types but NOT about
cancer+cognition are still EXCLUDED. The cancer+cognition inclusion
criteria remain the universal gate.


═══════════════════════════════════════════════════════════════════════════
 PART 3: NEW AGENT — AG11 (InstrumentValidationAgent)
 Pattern: Same as AG01-AG10. LLM-based. Reads PaperMap. Outputs SpanLabels.
═══════════════════════════════════════════════════════════════════════════

## EX-P1-AG11 — InstrumentValidationAgent (NEW)
  ID: EX-P1-AG11 | Type: ATOMIC (LLM) | Runs for: PSYCHOMETRIC_VALIDATION papers
  Purpose: Extract instrument psychometric properties from validation studies

  Reads: PaperMap.sections[Methods, Results, Tables]

  Outputs — SpanLabel[] with these NEW label types (extend SpanLabelEnum):
    CRONBACHS_ALPHA          — reliability coefficient α ∈ (0, 1)
    TEST_RETEST_RELIABILITY  — r_tt ∈ (0, 1)
    FACTOR_LOADING           — standardized loading λ ∈ (0, 1)
    FACTOR_STRUCTURE          — number of factors, model fit indices
    CONVERGENT_VALIDITY       — correlation with gold standard
    DISCRIMINANT_VALIDITY     — correlation with unrelated measure
    INTERNAL_CONSISTENCY_N    — sample size for reliability estimate
    MEASUREMENT_INVARIANCE    — DIF/invariance test results
    INSTRUMENT_NAME           — which instrument these properties describe
    INSTRUMENT_SUBSCALE       — which subscale (if applicable)
    POPULATION_DESCRIPTOR     — which population (cancer type, phase, N)
    SEM_VALUE                 — standard error of measurement

  Prompt template: llm/prompts/ag11_instrument_validation.txt
  Key instruction: "For each instrument reported in this paper, extract
  ALL psychometric properties. Link each property to the specific
  instrument and subscale. Record the population and sample size for
  each estimate. If multiple populations are reported (e.g., cancer vs.
  healthy controls), extract BOTH with population labels."

  Output schema: Same SpanLabel structure as AG05, with new label types.
  Grouping: SpanLabels grouped by {instrument_name × subscale × population}


═══════════════════════════════════════════════════════════════════════════
 PART 4: AGENT EXTENSIONS (existing agents, new extraction targets)
═══════════════════════════════════════════════════════════════════════════

## AG03-EXT — CohortAgent Extension (population norms)
  Current: Extracts N, age, demographics, cancer type
  Extension: ALSO extract per-domain cognitive scores for the population

  New SpanLabel types:
    POPULATION_COGNITIVE_MEAN    — mean score on cognitive domain
    POPULATION_COGNITIVE_SD      — SD of score
    POPULATION_COGNITIVE_DOMAIN  — which cognitive domain (memory, attention, etc.)
    POPULATION_COGNITIVE_INSTRUMENT — which instrument measured it
    POPULATION_PERCENTILE        — percentile vs normative data (if reported)

  Trigger: Activated for NORMATIVE_COHORT papers AND any paper reporting
  baseline cognitive scores by cancer subgroup.

  Prompt extension: Add to llm/prompts/ag03_cohort.txt:
  "If this paper reports mean cognitive scores by cancer type, treatment
  phase, or demographic subgroup: extract EVERY reported mean and SD,
  linked to the specific instrument, domain, and population subgroup.
  These are used to build population-level priors."


## AG06-EXT — ExposureAgent Extension (dose-response data)
  Current: Extracts dose, duration, adherence qualitatively
  Extension: ALSO extract structured dose × effect pairs

  New SpanLabel types:
    DOSE_LEVEL              — specific dose amount
    DOSE_UNIT               — unit (mg, minutes, sessions/week)
    EFFECT_AT_DOSE          — effect size at this dose level
    EFFECT_SE_AT_DOSE       — SE of effect at this dose
    DOSE_RESPONSE_SHAPE     — linear/plateau/U-shaped/threshold
    EFFECTIVE_DOSE_RANGE    — reported therapeutic range
    MAXIMUM_TOLERATED_DOSE  — safety ceiling

  Trigger: Activated for DOSE_RESPONSE_STUDY papers AND any RCT
  with multiple dose arms.

  Prompt extension: "If this paper compares multiple doses of the same
  intervention: extract the effect size and SE at EACH dose level as
  separate SpanLabels. If the paper reports a dose-response curve or
  model parameters (EC50, Emax, Hill coefficient), extract those directly."


## AG08-EXT — TemporalAgent Extension (curve data)
  Current: Extracts timepoints and temporal annotations
  Extension: ALSO extract effect × timepoint structured data

  New SpanLabel types:
    EFFECT_AT_TIMEPOINT     — effect size at specific timepoint
    SE_AT_TIMEPOINT         — SE at that timepoint
    TIMEPOINT_WEEKS         — weeks from baseline/intervention start
    ONSET_OBSERVED          — first timepoint with significant effect
    PEAK_OBSERVED           — timepoint with maximum effect
    DECAY_OBSERVED          — timepoint where effect starts declining
    RECOVERY_POSTCESSATION  — effect size after intervention stops
    RECOVERY_TIMEPOINT      — weeks after cessation for recovery measure

  Trigger: Activated for LONGITUDINAL_FOLLOWUP papers AND any RCT
  with 3+ measurement timepoints.

  Prompt extension: "If this paper reports effects at multiple timepoints:
  extract the effect size, SE, and timepoint (in weeks) for EACH
  measurement as separate SpanLabels. If the paper reports effects after
  the intervention ended (follow-up/recovery), extract those separately
  with RECOVERY_ prefix."


## AG05-EXT — StatsLabelAgent Extension (subgroup interactions)
  Current: Extracts 40 label types for effect sizes, CIs, p-values
  Extension: ALSO extract subgroup interaction effects

  New SpanLabel types:
    SUBGROUP_VARIABLE       — what defines the subgroup (age, sex, cancer type)
    SUBGROUP_VALUE          — specific subgroup (>65, female, breast cancer)
    INTERACTION_EFFECT      — interaction β (subgroup × treatment)
    INTERACTION_SE          — SE of interaction
    INTERACTION_P           — p-value for interaction test
    SUBGROUP_EFFECT         — effect size within subgroup
    SUBGROUP_N              — sample size for subgroup

  Trigger: Always active (AG05 already always runs), but subgroup
  extraction only fires when the paper contains subgroup analyses.

  Prompt extension: "If this paper reports subgroup analyses or
  treatment × moderator interactions: extract the interaction effect,
  SE, and p-value for EACH subgroup comparison. Also extract the
  within-subgroup effect sizes if reported."


═══════════════════════════════════════════════════════════════════════════
 PART 5: TRUST BOUNDARY EXTENSIONS
 Extends: EX-TB (numeric_parser.py + consistency_checker.py)
═══════════════════════════════════════════════════════════════════════════

Add validation rules for non-edge parameter types:

## TB-PSYCH: Psychometric Parameter Validation
  CRONBACHS_ALPHA: must be ∈ (0, 1). Typical range (0.60, 0.98).
    Flag if < 0.50 (likely misparse) or > 0.99 (likely ICC not α)
  FACTOR_LOADING: must be ∈ (0, 1). Typical range (0.30, 0.95).
    Flag if < 0.20 (item doesn't load) or > 0.98 (likely r not λ)
  TEST_RETEST: must be ∈ (0, 1). Flag if < 0.40 (poor reliability).
  INTERNAL_CONSISTENCY_N: must be ≥ 20.
  Cross-check: If α reported AND factor loadings reported, verify
    α ≈ (k × mean_loading²) / (1 + (k-1) × mean_loading²)
    within reasonable tolerance. Flag large discrepancies.

## TB-NORMS: Population Norm Validation
  POPULATION_COGNITIVE_MEAN: range depends on instrument. Flag if
    z-score equivalent |z| > 4 (implausible for group mean).
  POPULATION_COGNITIVE_SD: must be > 0. Flag if SD > 3× expected
    population SD for that instrument (likely misparse of variance).
  Cross-check: If mean and SD reported for same group, verify
    coefficient of variation is plausible for cognitive scores.

## TB-DOSE: Dose-Response Validation
  DOSE_LEVEL: must be > 0 and ≤ MAXIMUM_TOLERATED_DOSE (if reported).
  EFFECT_AT_DOSE: must be consistent with overall effect direction.
  Cross-check: Effect should generally increase (or plateau) with dose.
    Non-monotonic patterns get flagged for review (may be real but rare).

## TB-TEMPORAL: Temporal Data Validation
  TIMEPOINT_WEEKS: must be ≥ 0. Flag if > 520 (10 years — implausible
    follow-up for most cognitive studies).
  EFFECT_AT_TIMEPOINT: must have valid SE or derivable SE.
  Cross-check: Effect at timepoint 0 should be ≈ 0 (baseline).
    If not, likely a post-baseline measurement mislabeled.

## TB-SUBGROUP: Subgroup Interaction Validation
  INTERACTION_EFFECT: no range constraint but SE must exist.
  Cross-check: Main effect ± interaction should approximate
    within-subgroup effects if both are reported. Flag large
    discrepancies (>2 SE).


═══════════════════════════════════════════════════════════════════════════
 PART 6: THE SIX COMPILERS
 New chain: EX-P7 (Parameter Compilation)
 Runs AFTER P6 validation, BEFORE ALG-A graph assembly
═══════════════════════════════════════════════════════════════════════════

CHAIN CARD: EX-P7 (Parameter Compilation)
  Purpose: Convert extracted non-edge evidence into algorithm-consumable
           table formats. Six compilers, one per parameter type.
  Phase: Build-time (after all papers extracted, before model freeze)
  Reads: edge_evidence_v1 (for some compilers), plus new extraction tables
  Writes: Updates to Class A tables (instruments_v1, context_matched_priors_v1,
          recovery_params_v1, intervention_kernels_v1, dose_response_params_v1,
          modifier_registry_v1, synergy_registry_v1)

  CRITICAL: Compilers write to Class A tables but with provenance_status =
  CURATED_TRACED and provenance_ref = full citation chain. They do NOT
  overwrite DESIGN_CHOICE values (structural parameters).


## COMPILER 1: Psychometric → instruments_v1
  File: extraction/p7_compilers/psychometric_compiler.py

  Input: Extracted SpanLabels from AG11 where label_type IN
    (CRONBACHS_ALPHA, FACTOR_LOADING, TEST_RETEST_RELIABILITY,
     INSTRUMENT_NAME, POPULATION_DESCRIPTOR, INTERNAL_CONSISTENCY_N)

  Storage: instrument_evidence_v1 (NEW intermediate table)
    | instrument_id | study_id | population | N | alpha | loading_mean |
    | loading_per_subscale | test_retest | cancer_type | se_alpha |

  Compilation method:
    Per instrument:
    1. Collect all α estimates across studies
    2. Weight by sample size: α_compiled = Σ(N_i × α_i) / Σ(N_i)
    3. SE_alpha = √(Σ(N_i × (α_i − α_compiled)²) / Σ(N_i)) / √(k)
    4. b_k: Use mean factor loading if available. If only α available,
       derive: b_k ≈ √(α / num_items) (tau-equivalent assumption)
    5. a_k: If instrument has known intercept, use it. Else a_k = 0.
    6. cancer_validation_status:
       If ≥1 cancer-specific validation study → CANCER_VALIDATED
       If used in ≥1 cancer study but no validation → USED_IN_CANCER
       If only general population data → GENERAL_POPULATION
       If potential somatic confound flagged → CONFOUNDED

  Output writes: instruments_v1 columns {a_k, b_k, alpha_k,
    cancer_validation_status, provenance_status='CURATED_TRACED',
    provenance_ref='[study list]'}

  Gate P7-G1: Every compiled α must be based on ≥1 study with N≥20.
    If not met → provenance_status='APPROXIMATE_PENDING', keep default.

  Minimum for v1.0: Top 10 most-used instruments (by question_bank_v1
    coverage). Others can stay APPROXIMATE_PENDING.


## COMPILER 2: Population Norms → context_matched_priors_v1
  File: extraction/p7_compilers/prior_compiler.py

  Input: Extracted SpanLabels from AG03-EXT where label_type IN
    (POPULATION_COGNITIVE_MEAN, POPULATION_COGNITIVE_SD,
     POPULATION_COGNITIVE_DOMAIN, POPULATION_COGNITIVE_INSTRUMENT)
  Plus: study_cohort_profiles_v1 (cancer type, phase, N)

  Storage: population_norms_v1 (NEW intermediate table)
    | study_id | cancer_type | treatment_phase | node_id | mean_z |
    | sd | N | instrument_id | population_desc |

  Compilation method:
    Per cancer_type × treatment_phase context:
    1. Collect all population means for each node with available data
    2. z-score against instrument norms (from instrument manuals or
       healthy control groups in the same studies)
    3. μ_prior[node_i] = weighted mean of z-scores by N
    4. For nodes WITHOUT direct data in this context:
       Use Level 2/3 fallback per ALG-C1b (inherit from broader context)
    5. Σ_prior: Compute from observed covariance if multi-instrument
       studies available. Otherwise use shrinkage estimator toward
       diagonal with estimated marginal variances.
    6. Λ_prior = Σ_prior⁻¹ (via Cholesky, must be positive definite)

  Output writes: context_matched_priors_v1 columns {μ_prior, Λ_prior,
    provenance_status, provenance_ref, n_total, source_studies}

  Gate P7-G2: Compiled Λ_prior must be positive definite.
    If not → fall back to diagonal Λ with marginal precisions only.

  Minimum for v1.0: Top 5 contexts (breast×post, breast×active,
    colorectal×post, lung×active, mixed×mixed).
    Others use Level 4 uninformative (μ=0, Λ=I) with 2.0× SE inflation.


## COMPILER 3: Temporal Data → intervention_kernels_v1 + recovery_params_v1
  File: extraction/p7_compilers/temporal_compiler.py

  Input: Extracted SpanLabels from AG08-EXT where label_type IN
    (EFFECT_AT_TIMEPOINT, SE_AT_TIMEPOINT, TIMEPOINT_WEEKS,
     ONSET_OBSERVED, PEAK_OBSERVED, DECAY_OBSERVED,
     RECOVERY_POSTCESSATION, RECOVERY_TIMEPOINT)

  Storage: temporal_evidence_v1 (NEW intermediate table)
    | study_id | action_id | timepoint_weeks | effect | se | is_recovery |
    | N | design |

  Compilation method — INTERVENTION KERNELS:
    Per intervention:
    1. Collect all (timepoint, effect) pairs across studies
    2. Weight by 1/SE² (same IVW logic as edge evidence)
    3. Fit trapezoidal kernel:
       onset_weeks = first timepoint where effect significantly > 0
       peak_weeks = timepoint with maximum weighted effect
       plateau_duration = peak to first decline
       decay_rate = slope of decline after plateau (if observed)
    4. If < 3 timepoints: cannot fit curve. Use default kernel shape
       with observed peak effect. provenance_status = APPROXIMATE_PENDING.

  Compilation method — RECOVERY PARAMS:
    Per intervention class:
    1. Collect all post-cessation (timepoint, effect) pairs
    2. Fit stretched exponential: r(t) = r_∞(1 − e^{−(t/τ_R)^γ_R})
       using least-squares on the weighted data
    3. If < 3 recovery timepoints: cannot fit. Use default recovery
       curve. provenance_status = APPROXIMATE_PENDING.

  Output writes: intervention_kernels_v1 {onset_weeks, peak_weeks,
    plateau_duration, decay_rate, provenance_status, provenance_ref}
  Output writes: recovery_params_v1 {r_inf, tau_R, gamma_R,
    provenance_status, provenance_ref}

  Gate P7-G3: Fitted kernel must satisfy onset < peak.
    Fitted recovery must satisfy r_∞ ∈ (0, 1], τ_R > 0.


## COMPILER 4: Dose-Response → dose_response_params_v1
  File: extraction/p7_compilers/dose_response_compiler.py

  Input: Extracted SpanLabels from AG06-EXT where label_type IN
    (DOSE_LEVEL, DOSE_UNIT, EFFECT_AT_DOSE, EFFECT_SE_AT_DOSE)

  Storage: dose_evidence_v1 (NEW intermediate table)
    | study_id | action_id | dose | dose_unit | effect | se | N |

  Compilation method:
    Per intervention:
    1. Collect all (dose, effect) pairs across studies
    2. Normalize doses to common unit per intervention
    3. Fit Hill/Emax model: E(d) = E0 + Emax × d^h / (ED50^h + d^h)
       using nonlinear least squares weighted by 1/SE²
    4. If < 3 dose levels: cannot fit Emax. Use linear dose-response
       with max observed effect as Emax. Flag as APPROXIMATE_PENDING.

  Output writes: dose_response_params_v1 {E0, Emax, ED50, hill,
    provenance_status, provenance_ref}

  Gate P7-G4: Emax must have same sign as observed effect direction.
    ED50 must be > 0. Hill must be > 0.


## COMPILER 5: Subgroup Data → modifier_registry_v1
  File: extraction/p7_compilers/modifier_compiler.py

  Input: Extracted SpanLabels from AG05-EXT where label_type IN
    (SUBGROUP_VARIABLE, SUBGROUP_VALUE, INTERACTION_EFFECT,
     INTERACTION_SE, INTERACTION_P, SUBGROUP_EFFECT, SUBGROUP_N)

  Storage: subgroup_evidence_v1 (NEW intermediate table)
    | study_id | edge_id | modifier_variable | modifier_value |
    | interaction_beta | interaction_se | subgroup_n |

  Compilation method:
    Per modifier rule:
    1. Collect all interaction effects matching this modifier condition
    2. Pool interactions via IVW (same as edge evidence, formula P4-1)
    3. Convert interaction β to multiplicative modifier:
       multiplier = exp(β_interaction) for log-scale effects
       multiplier = 1 + β_interaction/β_main for linear-scale
    4. Clamp to [0.7, 1.5] per ALG-C4b guardrails
    5. Grade: based on evidence quality (RCT interaction = HIGH,
       observational = MODERATE, single study = LOW)

  Output writes: modifier_registry_v1 {multiplier, grade,
    provenance_status, provenance_ref}

  For modifier rules that are genuinely domain knowledge (e.g.,
  "older adults respond differently to exercise"): keep as
  SENSITIVITY_REQUIRED, not RED. The extraction system only covers
  modifiers where subgroup analysis data exists.


## COMPILER 6: Synergy Data → synergy_registry_v1
  File: extraction/p7_compilers/synergy_compiler.py

  Input: Extracted SpanLabels from papers reporting factorial designs
    or combination interventions

  This compiler is the MOST limited because factorial trials in
  cancer cognition are rare. Realistic expectation: 0-3 synergy
  pairs will have direct extraction evidence. Others use expert
  estimates (SENSITIVITY_REQUIRED).

  Compilation method:
    Per intervention pair:
    1. If factorial trial exists: extract interaction term directly
    2. γ = (effect_AB − effect_A − effect_B) / max(|effect_A|, |effect_B|)
    3. If γ > 0: synergistic. If γ < 0: antagonistic. If ≈0: additive.
    4. If no factorial data: check for observational combination studies
       with much wider SE.

  Gate P7-G6: γ must be ∈ (-1, 1). Values outside this range suggest
    misparse or implausible interaction.


═══════════════════════════════════════════════════════════════════════════
 PART 7: NEW INTERMEDIATE TABLES (Class B — pipeline-written)
═══════════════════════════════════════════════════════════════════════════

Add these 5 new tables to 002_class_b_evidence.sql:

  instrument_evidence_v1 — raw psychometric extractions per study
  population_norms_v1 — raw population cognitive scores per study
  temporal_evidence_v1 — raw timepoint × effect data per study
  dose_evidence_v1 — raw dose × effect data per study
  subgroup_evidence_v1 — raw subgroup interaction data per study

These mirror edge_evidence_v1 in concept: they store the raw extracted
values BEFORE compilation. The compilers read from these and write to
the Class A tables.

All 5 have the same base columns:
  | id | study_id (FK) | extraction_run_id (FK) | created_at |
  | provenance_status | provenance_ref |

Plus type-specific columns per the compiler input schemas above.


═══════════════════════════════════════════════════════════════════════════
 PART 8: IMPACT ON IMPLEMENTATION
═══════════════════════════════════════════════════════════════════════════

NEW FILES (add to FILE_CONTEXT_MANIFEST):
  extraction/p1_extraction/agents/ag11_instrument_validation.py
  extraction/p7_compilers/psychometric_compiler.py
  extraction/p7_compilers/prior_compiler.py
  extraction/p7_compilers/temporal_compiler.py
  extraction/p7_compilers/dose_response_compiler.py
  extraction/p7_compilers/modifier_compiler.py
  extraction/p7_compilers/synergy_compiler.py
  llm/prompts/ag11_instrument_validation.txt
  + extensions to existing agent prompts (ag03, ag05, ag06, ag08)

NEW PROMPTS (add to PROMPT_SEQUENCE, after Phase 3):

  PROMPT 3.5 — AG11 + Extended Agent Prompts
    Build ag11_instrument_validation.py
    Update ag03, ag05, ag06, ag08 prompts with new SpanLabel types
    Add new SpanLabel types to enums.py

  PROMPT 3.6 — Trust Boundary Extensions
    Add TB-PSYCH, TB-NORMS, TB-DOSE, TB-TEMPORAL, TB-SUBGROUP
    validation rules to numeric_parser.py + consistency_checker.py

  PROMPT 3.7 — New Intermediate Tables
    Add 5 new tables to 002_class_b_evidence.sql
    Update seed_loader.py

  PROMPT 3.8 — Compilers 1-3 (psychometric, prior, temporal)
    These are the highest-impact compilers

  PROMPT 3.9 — Compilers 4-6 (dose-response, modifier, synergy)
    These are lower-impact but complete the system

  PROMPT 3.10 — Pipeline Extension
    Update pipeline.py to run P7 compilers after P6 validation
    Update run_extraction.py to support paper type routing

TOTAL: 6 new prompts → 37 total (was 31)

UPDATED EXTRACTION FLOW:
  P0 (triage — now routes 27 subtypes)
  → P1 (agents AG01-AG11 based on paper type)
  → TB (extended with 5 new validation rule sets)
  → P2 (harmonization — unchanged)
  → P3 (7-layer SE — for edge evidence only)
  → P4 (aggregation — for edge evidence only)
  → P4B, P5, P6 (unchanged)
  → P7 (NEW — 6 compilers producing algorithm-ready parameters)

PHASE 4 (batch extraction) now includes:
  - Traditional intervention/cohort papers → edge evidence (existing)
  - Validation papers → instruments_v1 via Compiler 1 (new)
  - Normative cohort papers → context_matched_priors via Compiler 2 (new)
  - Multi-timepoint papers → kernels + recovery via Compiler 3 (new)
  - Dose-finding papers → dose_response via Compiler 4 (new)
  - Papers with subgroup analyses → modifiers via Compiler 5 (new)


═══════════════════════════════════════════════════════════════════════════
 PART 9: PAPER COLLECTION GUIDANCE
═══════════════════════════════════════════════════════════════════════════

Your paper collection for Phase 4 now needs to include:

EDGE EVIDENCE (existing scope): ~50-150 papers
  RCTs, cohort studies, meta-analyses of cancer × cognitive interventions
  Search: "[intervention] cognitive cancer randomized"

PSYCHOMETRIC VALIDATION: ~30-40 papers
  Instrument validation studies in cancer populations
  Search: "[instrument name] reliability cancer" OR
          "[instrument name] validation oncology"
  Target: At least 1 validation paper per instrument in question_bank_v1

NORMATIVE COHORTS: ~15-25 papers
  Large cohort studies with cognitive baseline data by cancer type
  Search: "cognitive function [cancer type] cohort baseline"
  Target: At least 1 cohort per priority cancer×phase context

TEMPORAL/LONGITUDINAL: ~20-30 papers
  RCTs with 3+ cognitive measurement timepoints
  Search: "[intervention] cognitive cancer longitudinal trajectory"
  Target: Top 10 interventions with multi-timepoint data

DOSE-RESPONSE: ~10-15 papers
  Studies comparing multiple doses of same intervention
  Search: "[intervention] dose cognitive cancer"
  Target: Interventions where dose-response is clinically meaningful

TOTAL: ~125-260 papers across all types
  This replaces the "140-215 hours of manual curation" with
  "run the extraction pipeline on more paper types."


═══════════════════════════════════════════════════════════════════════════
 PART 10: WHAT STAYS MANUAL (genuinely)
═══════════════════════════════════════════════════════════════════════════

Even with full-spectrum extraction, some values remain GREEN/YELLOW:

GENUINELY DESIGN CHOICES (GREEN — you decide these):
  - Node definitions (what the 63 nodes are)
  - Edge skeleton (which 118 causal relationships exist)
  - Pathway groupings
  - Instrument ↔ node mappings (which instrument measures which node)
  - Action catalog (which interventions to model)
  - Contraindication rules (safety decisions)

GENUINELY AUTHOR-CONSTRUCTED (YELLOW — sensitivity analysis):
  - Severity weights (how to weight cognitive subdomains)
  - Guardrail bounds ([0.7, 1.5] modifier range)
  - Scope dimension weights (cancer 0.35, phase 0.25, etc.)
  - Literary constraints (plausibility bounds on β)
  - Kernel SHAPE (trapezoidal assumption — but parameters are RED)

These are ~400 values total. They ARE filled from the CRCI paper
in Phase 0A. The extraction pipeline handles the other ~3,000+.


═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
