═══════════════════════════════════════════════════════════════════════════
 CRCI — PARAMETER PROVENANCE CLASSIFICATION & CURATION PROTOCOL
 Purpose: Address the architectural gap between extraction output and
          algorithm input for non-edge parameters. Classify every
          parameter. Define curation process. Add deployment gate.
═══════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════
 PART 1: THE PROBLEM (summary of architecture analysis)
═══════════════════════════════════════════════════════════════════════════

The extraction pipeline produces edge evidence (β, SE) through a
rigorous 12-chain process. The algorithm consumes SEVEN parameter types.
Only ONE has a compiler pathway:

  edge evidence → IVW/RE → edges_v1         ✓ FULL PIPELINE
  psychometric data → ??? → instruments_v1   ✗ NO COMPILER
  cohort norms → ??? → context_matched_priors ✗ NO COMPILER
  longitudinal data → ??? → recovery_params   ✗ NO COMPILER
  RCT temporal data → ??? → intervention_kernels ✗ NO COMPILER
  dose-response data → ??? → dose_response_params ✗ NO COMPILER
  subgroup analyses → ??? → modifier_registry  ✗ NO COMPILER

Impact of using defaults instead of curated values:
  - instruments_v1 with b_k=1.0, α=0.70: inverts precision weighting
    in ALG-C3 by up to 8x. WRONG POSTERIORS.
  - context_matched_priors with Level 4 uninformative: Bayesian update
    has no prior knowledge. Wastes the entire prior specification system.
  - recovery_params with defaults: ALG-E produces temporal trajectories
    that don't reflect actual intervention kinetics. WRONG TIMELINES.

This does NOT mean the code architecture is wrong. It means Phase 0
("seed Class A tables") was under-specified. The tables are real, the
columns are real, the formulas consuming them are real. The gap is in
HOW the values get into those tables.


═══════════════════════════════════════════════════════════════════════════
 PART 2: PARAMETER PROVENANCE CLASSIFICATION
 Every value in every Class A table, classified as GREEN/YELLOW/RED
═══════════════════════════════════════════════════════════════════════════

GREEN = Our design choice. Can fill immediately from model definition.
YELLOW = Author-constructed. Fill with documented defaults + plan
         sensitivity analysis. Acceptable for v1.0.
RED = Claims about reality. Needs traced provenance from literature.
      MUST be curated before results are scientifically meaningful.

─── nodes_v1 (63 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| node_id, node_name | GREEN | Our naming convention |
| layer (latent/observed) | GREEN | Model design |
| pathway_id | GREEN | Our grouping decision |
| severity_weight | YELLOW | Author-constructed. Needs sensitivity analysis |
| population_mean_z | RED | Must come from normative studies |
| population_sd | RED | Must come from normative studies |

─── edges_v1 skeleton (118 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| source, target, edge_type | GREEN | Model design (DAG structure) |
| pathway_id, direction | GREEN | Model design |
| β̂, SE_eff, P_inclusion | RED | Filled by extraction pipeline (Process 2) |
| sigma_sq_structural | YELLOW→RED | Default 0.25, annotation-adjusted |

─── instruments_v1 (23 rows) — *** CRITICAL GAP *** ───
| Column | Classification | Notes |
|--------|---------------|-------|
| instrument_id, name | GREEN | Our catalog |
| measured_node | GREEN | Our mapping decision |
| a_k (intercept) | RED | From psychometric studies |
| b_k (loading/slope) | RED | From factor analysis / validation studies |
| α_k (reliability) | RED | From validation studies (Cronbach's α) |
| cancer_validation_status | RED | From cancer-specific validation studies |
| score_range_min/max | GREEN | From instrument manual |
| reverse_scored | GREEN | From instrument manual |

Impact: b_k and α_k directly enter ALG-C2's noise model:
  σ²_{y,k} = b²_k × (1 − α_k) / α_k
With b_k=1.0 (default), α_k=0.70 (default): σ² = 0.429
With b_k=0.6 (real), α_k=0.90 (real): σ² = 0.040
That's a 10.7x difference in observation noise. The Bayesian update
weights observations by 1/σ² — so the default OVERWEIGHTS this
observation by 10.7x compared to reality.

─── context_matched_priors_v1 (33 rows) — *** CRITICAL GAP *** ───
| Column | Classification | Notes |
|--------|---------------|-------|
| cancer_type, treatment_phase | GREEN | Our context categories |
| regimen_class | GREEN | Our categorization |
| μ_prior (63-vector) | RED | Population means from cohort studies |
| Λ_prior (63×63 matrix) | RED | Precision from population covariance |
| source_studies | RED | Provenance |
| n_total | RED | Supporting sample size |

Total RED values: 33 × (63 + 63×63) = 33 × 4,032 = 133,056
This is BY FAR the largest curation challenge. However, most entries
can start as Level 4 (uninformative: μ=0, Λ=I) and be progressively
filled. Priority: the 3-5 most common cancer×phase combinations.

─── modifier_registry_v1 (109 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| condition, target_edge | GREEN | Our rule definitions |
| multiplier | YELLOW/RED | Some are domain knowledge (age effects), some need subgroup evidence |
| grade | RED | Must reflect evidence quality for this modifier |
| bounds [0.7, 1.5] | YELLOW | Author-constructed guardrails |

─── intervention_kernels_v1 (~30 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| action_id, target_node | GREEN | Our intervention catalog |
| onset_weeks | RED | From RCT temporal data |
| peak_weeks | RED | From RCT temporal data |
| decay_rate | RED | From follow-up studies |
| kernel_shape | YELLOW | Trapezoidal assumption is author-constructed |

─── dose_response_params_v1 (~30 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| action_id | GREEN | Our catalog |
| E0, Emax, ED50, hill | RED | From dose-response studies |

─── synergy_registry_v1 (~10 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| action_a, action_b | GREEN | Our pair definitions |
| γ (synergy coefficient) | RED | From factorial/combination trials |
| JPO, CCS | RED | From joint outcome studies |

─── recovery_params_v1 (7 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| action_id | GREEN | Our catalog |
| r_∞, τ_R, γ_R | RED | From longitudinal follow-up studies |

─── sd_anchors_v1 (~10 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| node_id | GREEN | Our mapping |
| sd_value | RED | From normative/population studies |
| source_study | RED | Provenance |

─── correlation_registry_v1 (12 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| node_a, node_b | GREEN | Our pair definitions |
| correlation | RED | From multi-instrument studies |

─── literary_constraints_v1 (~20 rows) ───
| Column | Classification | Notes |
|--------|---------------|-------|
| constrained_edge | GREEN | Our constraint definitions |
| bound_type, bound_value | YELLOW | Author-constructed from domain knowledge |


═══════════════════════════════════════════════════════════════════════════
 PART 3: WHAT THIS MEANS FOR IMPLEMENTATION
═══════════════════════════════════════════════════════════════════════════

The code architecture does not change. The formulas do not change.
The 31 prompts do not change. What changes:

1. Phase 0 splits into 0A and 0B
2. Every RED value gets a provenance_status column
3. A deployment gate blocks production with unresolved RED values
4. The system runs with approximate values for development/testing
   but flags them explicitly

PHASE 0A — STRUCTURAL SEED (1-2 weeks, you can do now)
  Fill all GREEN values: node definitions, edge skeleton, pathway
  groupings, instrument catalog (IDs + names + measured nodes),
  action catalog, constraint definitions, pair definitions.
  Plus all YELLOW values with documented defaults.

  This is what our original Phase 0 actually meant.
  ~400 values. Fillable from the CRCI paper alone.

PHASE 0B — EVIDENCE CURATION (2-4 weeks, parallel with coding)
  Fill RED values through manual literature review.
  Priority order (by downstream impact):

  TIER 1 — Blocks meaningful inference (do first):
    instruments_v1: α_k, b_k for 23 instruments (~80 values)
    Source: psychometric validation papers, instrument manuals
    Effort: ~30-40 papers, ~40-60 hours

  TIER 2 — Blocks realistic priors (do second):
    context_matched_priors_v1: TOP 5 cancer×phase contexts
    Source: large cohort studies with cognitive outcomes
    Effort: ~15-25 papers, ~30-50 hours
    Note: Start with 5 of 33 contexts. Rest use Level 4 fallback.

  TIER 3 — Blocks temporal predictions (do third):
    intervention_kernels_v1: onset, peak, decay for top 10 interventions
    recovery_params_v1: r_∞, τ_R, γ_R for 7 intervention classes
    Source: RCTs with multiple timepoints
    Effort: ~20-30 papers, ~30-50 hours

  TIER 4 — Improves precision (do when time allows):
    dose_response_params_v1: Hill/Emax for interventions with dose data
    synergy_registry_v1: γ from factorial trials
    modifier_registry_v1: evidence-grading for RED modifiers
    sd_anchors_v1, correlation_registry_v1
    Effort: ~30-40 papers, ~40-60 hours

  TOTAL: ~80-115 papers, ~140-215 hours of researcher time
  This can be parallelized and done alongside coding.


═══════════════════════════════════════════════════════════════════════════
 PART 4: PROVENANCE STATUS COLUMN
 Add to every Class A table that contains RED values
═══════════════════════════════════════════════════════════════════════════

Add this column to every table with RED parameters:

  provenance_status ENUM:
    DESIGN_CHOICE        — GREEN. Our decision. No evidence needed.
    CURATED_TRACED       — RED, resolved. Has paper + table + cell ref.
    APPROXIMATE_PENDING  — RED, unresolved. Using default/approximate.
                           System runs but results are unreliable
                           for this parameter.
    SENSITIVITY_REQUIRED — YELLOW. Documented default, needs sensitivity
                           analysis to verify impact.

  provenance_ref TEXT:
    For CURATED_TRACED: "Smith2019, Table 3, row 2, N=847, α=0.91"
    For APPROXIMATE_PENDING: "Default α=0.70 per CTT convention"
    For SENSITIVITY_REQUIRED: "Author-constructed. §2.X of paper."

Code impact: Prompt 0.1 (SQL schemas) adds these 2 columns to every
Class A table. No other code changes needed — the algorithm reads the
numeric values regardless of provenance status.

The deployment gate (Part 5) is what enforces quality.


═══════════════════════════════════════════════════════════════════════════
 PART 5: DEPLOYMENT GATE (G0)
 Hard gate before any production/submission use
═══════════════════════════════════════════════════════════════════════════

Gate G0: Pre-deployment parameter readiness check
Location: scripts/validate_deployment_readiness.py
When: Run before any science project submission or patient inference

CHECKS:

G0-1: Measurement model completeness
  SELECT COUNT(*) FROM instruments_v1
  WHERE provenance_status = 'APPROXIMATE_PENDING'
  AND instrument_id IN (SELECT DISTINCT instrument_id
                        FROM question_bank_v1)
  MUST = 0
  Meaning: Every instrument that patients will actually USE must have
  real α_k, b_k values. Not all 23 — just the ones in the active
  question bank.

G0-2: Minimum edge parameterization
  SELECT COUNT(*) FROM edges_v1 WHERE beta_mean IS NOT NULL
  MUST ≥ 30
  Meaning: At least 30 of 118 edges have real evidence from extraction.

G0-3: Prior coverage
  SELECT COUNT(*) FROM context_matched_priors_v1
  WHERE provenance_status = 'CURATED_TRACED'
  MUST ≥ 3
  Meaning: At least 3 cancer×phase contexts have real priors
  (not just uninformative Level 4).

G0-4: Spectral radius
  ρ(B) < 1 with REAL edge weights (not placeholders)
  Meaning: System stability verified with actual parameters.

G0-5: No APPROXIMATE in critical path
  For the specific patient being tested: their cancer type × treatment
  phase combination must have CURATED_TRACED priors, and every
  instrument they've completed must have CURATED_TRACED psychometrics.

G0 OUTPUT:
  READY — all checks pass → can run inference
  NOT_READY — lists every failing check with specific missing values

G0 is NOT a code-blocking gate during development. It's a pre-submission
quality gate. The system RUNS with approximate values (for testing,
debugging, prompt iteration). G0 just tells you whether the output
is scientifically defensible.


═══════════════════════════════════════════════════════════════════════════
 PART 6: CURATION TEMPLATES
 What the researcher fills out per parameter type
═══════════════════════════════════════════════════════════════════════════

TEMPLATE A: Instrument Psychometrics (for instruments_v1)
─────────────────────────────────────────────────────────
Per instrument:
  Instrument: [name]
  Measured node: [node_id]
  Search: "[instrument name] reliability cancer" in PubMed

  From validation study:
    Paper: [author, year, DOI]
    Population: [cancer type, phase, N]
    Cronbach's α: [value] (Table [X], row [Y])
    Factor loading (b_k): [value] (Table [X], row [Y])
    Score range: [min]-[max]
    Cancer-validated: YES/USED/GENERAL/CONFOUNDED
    Notes: [any somatic confound concerns]

  If multiple studies: report all, use weighted mean of α by N.
  If no cancer study: use general population α, set status=GENERAL,
    cancer_SE_mult = 1.3× per ALG-C2c.

  Minimum acceptable: At least ONE published α value. If zero exist
  for this instrument, escalate — the instrument may not belong in
  the model.


TEMPLATE B: Context-Matched Priors (for context_matched_priors_v1)
─────────────────────────────────────────────────────────────────
Per cancer_type × treatment_phase:
  Context: [e.g., breast × post_treatment]
  Search: "cognitive function [cancer] [phase] cohort" in PubMed

  From cohort study (ideally N ≥ 100):
    Paper: [author, year, DOI]
    Population: [exact inclusion criteria, N]
    Cognitive measures: [which instruments used]
    Per node with available data:
      Node: [node_id]
      Population mean (z-scored): [value]
      Population SD: [value]
      Source: Table [X], row [Y]

  For nodes without direct data in this population:
    Use Level 2 fallback (cancer-type-only) or Level 3 (general cancer)
    with SE inflation per ALG-C1b.

  Priority contexts (fill these first):
    1. breast × post_treatment (largest literature)
    2. breast × active_chemo
    3. colorectal × post_treatment
    4. lung × active_chemo
    5. mixed × mixed (general cancer)


TEMPLATE C: Temporal Parameters (for intervention_kernels_v1 + recovery_params_v1)
─────────────────────────────────────────────────────────────────────────────────
Per intervention:
  Intervention: [action_id]
  Search: "[intervention] cognitive cancer randomized" in PubMed

  From RCT with multiple timepoints:
    Paper: [author, year, DOI]
    Design: [RCT, N, duration]
    Timepoints measured: [list weeks]
    Effect at each timepoint: [β, SE if available]
    Onset (first significant effect): ~[X] weeks
    Peak (maximum effect): ~[X] weeks
    Decay (if follow-up extends past intervention): rate estimate

  For kernel fitting: use the timepoint data to estimate
    {onset_weeks, peak_weeks, plateau_duration, decay_rate}
  For recovery: use post-cessation data to estimate
    {r_∞, τ_R, γ_R} for stretched exponential

  If only 2 timepoints: use linear interpolation. Flag as LOW quality.
  If only 1 timepoint: cannot fit temporal model. Use default kernel
    with APPROXIMATE_PENDING status.


═══════════════════════════════════════════════════════════════════════════
 PART 7: IMPACT ON IMPLEMENTATION PLAN
═══════════════════════════════════════════════════════════════════════════

CHANGES TO EXISTING DOCUMENTS:

1. PROMPT_SEQUENCE.md — Phase 0 header updated:
   Phase 0A: Structural seed (GREEN + YELLOW values) — 1-2 weeks
   Phase 0B: Evidence curation (RED values) — 2-4 weeks, PARALLEL
   with code development in Phases 1-5

2. TABLE_FILL_ORDER.md — Add "Process 1.5: Manual Curation"
   between structural seed and extraction pipeline

3. Prompt 0.1 (SQL schemas) — Add provenance_status and
   provenance_ref columns to all Class A tables

4. Prompt 7.1 (CLI scripts) — Add validate_deployment_readiness.py
   implementing G0 checks

5. CLAUDE.md — Add note about provenance_status column

NO CHANGES TO:
  - SYS_ALGORITHM (correct as-is)
  - SYS_EXTRACTION (correct as-is, edge pipeline is solid)
  - SYS_RUNTIME, SYS_PRESENTATION
  - FILE_CONTEXT_MANIFEST (file list unchanged)
  - CODE_QUALITY_ENFORCEMENT
  - Any formulas, gates, or chain dependencies


WHAT THIS MEANS FOR YOUR TIMELINE:

  Code development: unchanged (~12 weeks for all 7 phases)
  Curation: ~140-215 hours, parallelizable, start immediately
  Curation Tier 1 (instruments): ~40-60 hours → unblocks meaningful
    ALG-C testing by Phase 5
  Science project submission: requires G0 READY status

  Critical path: Curation Tier 1 must finish before Phase 5 testing.
  If instruments_v1 still has defaults when you run ALG-C, the
  posteriors will be wrong and you won't know if the algorithm works.


═══════════════════════════════════════════════════════════════════════════
 PART 8: COMPILER CONTRACTS (v2.0 — spec now, build later)
═══════════════════════════════════════════════════════════════════════════

These six compilers automate what Phase 0B does manually. They're NOT
needed for v1.0 but should be specified so the architecture is clear.

COMPILER 1: Psychometric → instruments_v1
  Input: Extracted α, factor loadings from validation papers
  Method: Weighted mean of α by N across studies
  Output: a_k, b_k, α_k per instrument
  Blocking issue: No AG11 (InstrumentValidationAgent) exists yet

COMPILER 2: Cohort norms → context_matched_priors_v1
  Input: Extracted population means/SDs from cohort studies
  Method: Per cancer×phase context, compute μ_prior and Σ_prior
  Output: μ, Λ per context (63-vector + 63×63 matrix)
  Blocking issue: AG03 extracts demographics but not per-node norms

COMPILER 3: Longitudinal → recovery_params_v1
  Input: Extracted timepoint effects from follow-up studies
  Method: Fit stretched exponential: r(t) = r_∞(1 − e^{−(t/τ_R)^γ_R})
  Output: {r_∞, τ_R, γ_R} per intervention class
  Blocking issue: AG08 extracts temporal annotations, not curve data

COMPILER 4: RCT temporal → intervention_kernels_v1
  Input: Extracted effect×timepoint data from multi-wave RCTs
  Method: Fit trapezoidal kernel {onset, peak, plateau, decay}
  Output: Kernel parameters per intervention
  Blocking issue: Same as Compiler 3

COMPILER 5: Dose data → dose_response_params_v1
  Input: Extracted dose×effect pairs from dose-finding studies
  Method: Fit Hill/Emax: E(d) = E0 + Emax × d^h / (ED50^h + d^h)
  Output: {E0, Emax, ED50, hill} per intervention
  Blocking issue: No dose-response extraction agent

COMPILER 6: Subgroup data → modifier_registry_v1
  Input: Extracted subgroup×interaction effects
  Method: Convert interaction β to multiplicative modifier
  Output: Multiplier + grade per modifier rule
  Blocking issue: Subgroup extraction is implicit in AG05, not structured

For v2.0: Add AG11 (Instrument Validation Agent), extend AG08 for
curve data, add AG12 (Dose-Response Agent), add structured subgroup
extraction to AG05. Then build the 6 compilers as new P7 chain.

For v1.0: Manual curation using the templates in Part 6.


═══════════════════════════════════════════════════════════════════════════
 PART 9: AGREED — WHAT DOES NOT NEED UPDATING
═══════════════════════════════════════════════════════════════════════════

Confirmed no changes needed:
  ✓ SYS_ALGORITHM — formulas, chains, gates all correct
  ✓ SYS_EXTRACTION — edge evidence pipeline correct
  ✓ SYS_RUNTIME — downstream consumer, reads from ALG outputs
  ✓ SYS_PRESENTATION — pure rendering, read-only
  ✓ Code architecture — 31 prompts, ~70 files, directory tree
  ✓ Edge evidence compilation — the one compiler that exists and works

The analysis is right: the system specs are architecturally sound.
The gap is in the supply chain for non-edge parameters, and the
solution is manual curation for v1.0 + compiler specs for v2.0.

═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
