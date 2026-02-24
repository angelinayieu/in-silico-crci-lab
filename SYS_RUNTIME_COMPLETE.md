═══════════════════════════════════════════════════════════════════════════
           SYS_RUNTIME — COMPLETE SPECIFICATION
           (Tier 1: System Card + Tier 2: Chain Cards + Tier 3: Subsystem Cards)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0 (merged canonical)
Date: 2026-02-24

═══════════════════════════════════════════════════════════════════════════
                    PART 1: TIER 1 — SYSTEM CARD
═══════════════════════════════════════════════════════════════════════════

1. IDENTITY
   System ID:      SYS_RUNTIME
   Name:           Computational Decision Pipeline
   Purpose:        Rank intervention schedules, conduct adaptive questioning,
                   assemble provenance reports. COMPUTATIONAL ONLY [COR-2].
   Scope:          Takes simulation results from SYS_ALGORITHM (ALG-F output),
                   produces ranked plans + provenance + session management.
                   Does NOT render UI — that is SYS_PRESENTATION.
   Timing:         Runtime (per-patient session, after ALG-F completes)
   Chain Count:    3 stages + 1 validation chain

2. MACRO CHAIN

 SimulationResults (from ALG-F)
   │
   ▼
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │  RT-G        │────▶│  RT-H        │────▶│  RT-I        │
 │  Schedule    │     │  Adaptive    │     │  Reporting   │
 │  Optimization│     │  Questioning │     │  & Provenance│
 └──────────────┘     └──────┬───────┘     └──────────────┘
                             │                     │
                             │ loops back to       ▼
                             │ ALG-C for state     RecommendationReport
                             │ update after each   → SYS_PRESENTATION
                             │ patient answer
                             │
                      ┌──────┴───────┐
                      │  VAL-01      │
                      │  Complexity  │
                      │  Scaling     │
                      └──────────────┘

3. CHAIN INVENTORY

| Order | Chain ID | Name | Input | Output | Subsystems |
|-------|----------|------|-------|--------|------------|
| G | RT-G | Schedule Optimization | SimulationResults (ALG-F) | RankedSchedules[] | 4 |
| H | RT-H | Adaptive Questioning | PosteriorState + partial answers | NextQuestion + updated state | 3 |
| I | RT-I | Reporting & Provenance | RankedSchedules + session data | RecommendationReport | 4 |
| V | VAL-01 | Complexity-Scaling Validation | edges_v1 + run config | ValidationReport | 3 |

4. TABLE INVENTORY

| Class | Table ID | Row Semantics | Writers | Readers |
|-------|----------|---------------|---------|---------|
| D (Policy) | objective_specs_v1 | Per optimization objective | Humans | RT-G |
| D (Policy) | contraindication_rules_v1 | Per rule | Humans | RT-G |
| D (Policy) | question_bank_v1 | Per question template | Humans | RT-H |
| E (Output) | schedule_plans_v1 | Per ranked schedule | RT-G | RT-I, PRES |
| E (Output) | schedule_items_v1 | Per item in schedule | RT-G | RT-I, PRES |
| E (Output) | decision_trace_v1 | Per decision step | RT-G, RT-I | PRES, Audit |
| E (Output) | question_sequence_v1 | Per question asked | RT-H | RT-I, PRES |
| E (Output) | question_selection_trace_v1 | Per selection decision | RT-H | Audit |
| E (Output) | recommendation_runs_v1 | Per session (anchor) | RT-I | PRES, Audit |

5. EXTERNAL INTERFACES
   | Direction | System | Data | Format |
   |-----------|--------|------|--------|
   | INPUT | SYS_ALGORITHM (ALG-F) | 3 Output Packages | In-memory |
   | INPUT | Patient (via PRES) | Questionnaire answers | Typed JSON |
   | OUTPUT | SYS_PRESENTATION | RecommendationReport | Class E tables |
   | LOOP | SYS_ALGORITHM (ALG-C) | Updated observations | Triggers re-inference |

═══════════════════════════════════════════════════════════════════════════
                    PART 2: TIER 2 — CHAIN CARDS
═══════════════════════════════════════════════════════════════════════════

TABLE NAME BINDING KEY (RT system):
  schedule_plans       → schedule_plans_v1 (Class E)
  schedule_items       → schedule_items_v1 (Class E)
  decision_trace       → decision_trace_v1 (Class E)
  question_sequence    → question_sequence_v1 (Class E)
  question_bank        → question_bank_v1 (Class D, human-curated)
  recommendation_runs  → recommendation_runs_v1 (Class E, session anchor)
  state_snapshots      → state_snapshots_v1 (Class E, from ALG-C)

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: RT-G (Schedule Optimization)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_RUNTIME

1. IDENTITY
   Chain ID:       RT-G
   Name:           Schedule Optimization
   Purpose:        Transform ranked interventions from ALG-F into actionable
                   schedules — ordering, timing, dose, with constraint satisfaction
                   and SAFE score optimization
   Phase:          Runtime (per-patient session)
   Paper §:        §2.16 (SAFE), §2.19 (Decision Stability), §4.5
   Subsystems:     4 (G1–G4)

2. CHAIN DIAGRAM

 ClinicalOutputPackage (from ALG-F)
   │
   ▼
 ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │  RT-G1   │───▶│  RT-G2   │───▶│  RT-G3   │───▶│  RT-G4   │
 │ Candidate│    │ Constraint│    │ Schedule │    │ Stability│
 │ Expansion│    │ Filter   │    │ Assembly │    │ Classify │
 └──────────┘    └──────────┘    └──────────┘    └──────────┘
 expanded_pool   feasible_set    schedules[]      RankedSchedules
                                                  → RT-H

3. INTERMEDIATE STATE SCHEMAS

State: ExpandedPool (after G1)
| Field | Type | Description |
|-------|------|-------------|
| singles | list[Intervention] | Top-ranked single interventions from ALG-F |
| bundles | list[Bundle] | Top-ranked bundles from ALG-D5 |
| dose_variants | list[DoseVariant] | Alternative doses from dose_response_params_v1 |

State: FeasibleSet (after G2)
| Field | Type | Description |
|-------|------|-------------|
| candidates | list[ScheduleCandidate] | Constraint-satisfied options |
| excluded | list[{candidate, reason}] | Excluded with explanation |

State: RankedSchedules (output)
| Field | Type | Description |
|-------|------|-------------|
| schedules | list[Schedule] | Ordered by SAFE_B, with timing + dose |
| stability | StabilityState | From ALG-F2 |
| provenance | dict[decision→trace] | Audit trail of all decisions |

4. SUBSYSTEM DETAIL

## RT-G1 — Candidate Expansion
   Purpose: Expand ranked interventions into concrete schedule candidates
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic:                                                       │
   │ 1. Take top-K interventions from ALG-F ranking (K from       │
   │    objective_specs_v1, default K=10)                         │
   │ 2. For each: generate dose variants (standard, low, high)    │
   │    from dose_response_params_v1                              │
   │ 3. Generate timing variants (immediate, phased, sequential)  │
   │ 4. Combine singles into bundles (top-3 pairwise, top-1 triple)│
   │ 5. Total expanded pool: ~50-100 candidates                   │
   │ Rules: Don't expand beyond 100 (computational limit)         │
   └─────────────────────────────────────────────────────────────┘

## RT-G2 — Constraint Filtering
   Purpose: Remove candidates violating hard constraints, with catch-all safety net
   ┌─────────────────────────────────────────────────────────────┐
   │ Constraints (from contraindication_rules_v1):               │
   │ 1. Medical contraindications (cancer type, comorbidities)    │
   │ 2. Drug interactions (if pharmacological)                    │
   │ 3. Patient preferences (exclude categories if specified)     │
   │ 4. Practical: cost ceiling, time commitment ceiling          │
   │ 5. Bundle ceiling: total effect ≤ 1.5 SD                    │
   │ Rules: Hard constraint → EXCLUDE; Soft constraint → WARN    │
   └─────────────────────────────────────────────────────────────┘

   ZERO-RULE CATCH-ALL SAFETY NET [Gap-3 Fix]:
   ┌─────────────────────────────────────────────────────────────┐
   │ AFTER evaluating all specific rules for each (action, patient)│
   │ pair, run post-evaluation meta-check:                        │
   │                                                              │
   │ 3 catch-all rules added to contraindication_rules_v1:       │
   │                                                              │
   │ CATCH_ACTIVE_TREATMENT:                                      │
   │   IF treatment_phase IN (active_chemo, active_radiation,     │
   │      active_immunotherapy) AND toxicity_grade_max ≥ 2        │
   │      AND action.intensity > 'light'                          │
   │   → severity: escalate (require clinician review)            │
   │   → "Active treatment + Grade 2+ toxicity. Rule base may    │
   │     not cover all treatment-specific interactions."           │
   │                                                              │
   │ CATCH_RARE_CANCER:                                           │
   │   IF cancer_type NOT IN (breast, colorectal, lung, prostate, │
   │      hematological) AND action.intensity > 'light'           │
   │   → severity: soft_warn                                      │
   │   → "Cancer type underrepresented in evidence base."         │
   │                                                              │
   │ CATCH_ZERO_MATCH_RISKY (the key meta-rule):                  │
   │   IF contraindication_eval_count = 0                         │
   │      AND (has_active_treatment OR comorbidity_count ≥ 3      │
   │           OR age > 80)                                       │
   │   → severity: soft_warn                                      │
   │   → "No specific safety rules matched for this combination,  │
   │     but patient has clinical risk factors. Clinician review   │
   │     recommended."                                            │
   │                                                              │
   │ Implementation: 5 lines of post-evaluation logic:            │
   │   eval_results = evaluate_all_matching_rules(action, patient)│
   │   IF len(eval_results) == 0 AND patient.has_risk_factors():  │
   │       eval_results.append(evaluate(CATCH_ZERO_MATCH_RISKY))  │
   │   write_all(contraindication_eval_trace_v1)                  │
   │                                                              │
   │ Schema impact: 3 new rows in contraindication_rules_v1.      │
   │ No new columns. Existing severity ENUM already has escalate  │
   │ and soft_warn. Existing escalation_id FK works as-is.        │
   └─────────────────────────────────────────────────────────────┘

## RT-G3 — Schedule Assembly
   Purpose: Assemble feasible candidates into ordered schedules with timing
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic:                                                       │
   │ 1. For each feasible candidate:                              │
   │    - Assign start time (immediate or phased)                 │
   │    - Assign duration (from intervention_kernels_v1)          │
   │    - Assign dose (from dose_response_params_v1)              │
   │    - Compute expected benefit trajectory (from ALG-E)        │
   │ 2. Sort by SAFE_B score descending                           │
   │ 3. Top 5 schedules → detailed output                        │
   │ 4. Write schedule_plans_v1 + schedule_items_v1               │
   └─────────────────────────────────────────────────────────────┘

## RT-G4 — Stability Classification
   Purpose: Attach decision stability from ALG-F2 to ranked schedules
   Input: StabilityState from ALG-F2, RankedSchedules from G3
   Output: RankedSchedules with stability flags
   Logic: P(rank₁) ≥ 0.80 → STABLE; 0.60–0.79 → MODERATE;
          0.40–0.59 → UNSTABLE; < 0.40 → HIGHLY_UNSTABLE
   Write: decision_trace_v1

5. BOUNDARY TABLES
   READS: action_catalog_v1, contraindication_rules_v1, objective_specs_v1,
          dose_response_params_v1, intervention_kernels_v1
   WRITES: schedule_plans_v1, schedule_items_v1, decision_trace_v1

6. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | G-G1 | ≥1 feasible candidate | → G3 | WARN: all filtered |
   | G-G2 | Top schedule SAFE_B > MID (0.5 SD) | Confident rec | WARN: marginal |

7. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | G-1 | SAFE_A(a) = MSS_cog(a) − 0.3 · MSS_burden(a) (from ALG-D4) | §2.16 |
   | G-2 | SAFE_B(a) = SAFE_A(a) + 0.5 · ln(P_adhere(a)) (from ALG-D4) | §2.16 |
   | G-3 | P(rank₁) classification: ≥0.80 Stable, 0.60-0.79 Moderate, 0.40-0.59 Unstable, <0.40 Highly_unstable | §2.19 |
   | G-4 | Bundle ceiling: total Δθ ≤ 1.5 SD (physiological limit) | §2.16.1 |
   | G-5 | R_intervention = min(R_e for e in critical_path_edges); <0.25→excluded, <0.50→limited [Gap-4] | §2.16.2 |

8. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | G-A1 | Top-K=10 candidates sufficient (higher K → diminishing returns) | Low |
   | G-A2 | Constraint rules in contraindication_rules_v1 are complete (catch-all mitigates [Gap-3]) | Moderate |
   | G-A3 | Dose variants (low/standard/high) cover clinically relevant range | Moderate |
   | G-A4 | Schedule timing (immediate/phased/sequential) covers practical options | Low |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: RT-H (Adaptive Questioning)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_RUNTIME

1. IDENTITY
   Chain ID:       RT-H
   Name:           Adaptive Questioning
   Purpose:        Interactively collect patient observations to maximally reduce
                   uncertainty — each answer triggers ALG-C re-inference, which
                   may change rankings
   Phase:          Runtime (interactive, per-question loop)
   Paper §:        §4.5 (implied — adaptive assessment)
   Subsystems:     3 (H1–H3)

2. CHAIN DIAGRAM

 PosteriorState (from ALG-C, current)
   │
   ┌──────────▶ RT-H1: Question Selection ──▶ NextQuestion → Patient
   │            (information gain ranking)          │
   │                                                │ (patient answers)
   │                                                ▼
   │            RT-H2: Answer Integration ◀──── PatientAnswer
   │            (parse + validate)
   │                     │
   │                     ▼ (new observation)
   │            ALG-C re-inference (loop back)
   │                     │
   │                     ▼
   │            RT-H3: Stopping Decision
   │            (enough info? or continue?)
   │                     │
   │            ┌────────┴────────┐
   │            ▼                 ▼
   │         CONTINUE          STOP → RT-I
   └──────────┘

3. SUBSYSTEM DETAIL

## RT-H1 — Question Selection
   Purpose: Select the next question that maximally reduces posterior variance
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic: For each unanswered question q in question_bank_v1:  │
   │   IG(q) = H(θ|current) − E_y[H(θ|current ∪ y_q)]          │
   │   where H = entropy of posterior                             │
   │   Expected information gain computed via:                    │
   │     - Which node(s) does this question observe?              │
   │     - What is the current uncertainty on those nodes?        │
   │     - How much would observation reduce total uncertainty?   │
   │   Select: argmax_q IG(q)                                    │
   │ Rules: Max 15 questions per session (patient burden)         │
   │        Mandatory questions (e.g., cancer type) asked first   │
   │        Instrument-specific questions grouped together         │
   └─────────────────────────────────────────────────────────────┘

## RT-H2 — Answer Integration
   Purpose: Parse patient answer, validate, package as new observation for ALG-C
   Input: PatientAnswer (raw response)
   Output: New observation → triggers ALG-C re-inference
   Logic: Parse answer → map to instrument scale → validate range → add to observation set
   Rules: Invalid answer → re-prompt; "don't know" → skip (mark as missing)

## RT-H3 — Stopping Decision
   Purpose: Decide whether to ask more questions or stop
   ┌─────────────────────────────────────────────────────────────┐
   │ Stopping criteria (any triggers STOP):                      │
   │ 1. All high-IG questions exhausted (IG < threshold)         │
   │ 2. Ranking stability reached STABLE (P(rank₁) ≥ 0.80)      │
   │ 3. Max questions reached (15)                                │
   │ 4. Patient requests stop                                    │
   │ 5. Variance reduction < 5% from last question               │
   │ If STOP: proceed to RT-I                                    │
   │ If CONTINUE: loop back to RT-H1                              │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: question_bank_v1 (question templates), state_snapshots_v1 (current posterior)
   WRITES: question_sequence_v1, question_selection_trace_v1, state_snapshots_v1 (updated)

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | H-G1 | Question parsed successfully | → ALG-C | Re-prompt patient |
   | H-G2 | Stopping criteria met | → RT-I | Continue loop |

6. INTERMEDIATE STATE SCHEMAS

   ### State: PosteriorState (from ALG-C, updated each loop)
   | Field | Type | Description |
   |-------|------|-------------|
   | theta_post | float[63] | Posterior mean per node |
   | Sigma_post | float[63×63] | Posterior covariance (sparse) |
   | observed_nodes | set[node_id] | Which nodes have observations |
   | questions_asked | int | Running count |
   | last_ig | float | Information gain from last question |

   ### State: NextQuestion (from H1 to patient)
   | Field | Type | Description |
   |-------|------|-------------|
   | question_id | str | From question_bank_v1 |
   | target_nodes | list[node_id] | Which DAG nodes this observes |
   | instrument_id | str | Maps to instruments_v1 |
   | expected_ig | float | Predicted information gain |
   | question_text | str | Patient-facing text |

   ### State: PatientAnswer (from patient to H2)
   | Field | Type | Description |
   |-------|------|-------------|
   | question_id | str | Matches NextQuestion |
   | raw_response | str | Patient's answer |
   | parsed_value | float | Instrument-scaled value |
   | valid | bool | Passed range validation |

7. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | H-1 | IG(q) = H(θ|current) − E_y[H(θ|current ∪ y_q)] (information gain) | §4.5 |
   | H-2 | H(θ) = 0.5·ln|2πe·Σ_post| (multivariate Gaussian entropy) | §4.5 |
   | H-3 | Stopping: IG < 0.01 OR P(rank₁)≥0.80 OR questions≥15 OR var_reduction<5% | §4.5 |

8. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | H-A1 | Information gain computed under Gaussian posterior (analytical) | Moderate — non-Gaussian tails ignored |
   | H-A2 | Max 15 questions sufficient for convergence | Low — empirically validated |
   | H-A3 | Question independence (answer to Q1 doesn't change meaning of Q2) | Low — instruments designed to be independent |
   | H-A4 | Patient answers are truthful and within measurement error | Moderate — self-report bias possible |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: RT-I (Reporting & Provenance)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_RUNTIME

1. IDENTITY
   Chain ID:       RT-I
   Name:           Reporting & Provenance
   Purpose:        Assemble complete recommendation report with full audit trail,
                   uncertainty disclosure, and provenance chain from evidence to
                   recommendation
   Phase:          Runtime (per-session, after RT-H completes)
   Paper §:        §4.5 (Output Architecture)
   Subsystems:     4 (I1–I4)

2. CHAIN DIAGRAM

 RankedSchedules (from RT-G) + Session data (from RT-H)
   │
   ▼
 ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │  RT-I1   │───▶│  RT-I2   │───▶│  RT-I3   │───▶│  RT-I4   │
 │ Evidence │    │ Uncertain│    │ Session  │    │ Report   │
 │ Provnance│    │ Disclosre│    │ Summary  │    │ Assembly │
 └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                  │
                                                  ▼
                                           RecommendationReport
                                           → SYS_PRESENTATION

3. SUBSYSTEM DETAIL

## RT-I1 — Evidence Provenance
   Purpose: Trace each recommendation back to its supporting evidence
   ┌─────────────────────────────────────────────────────────────┐
   │ For each recommended intervention:                          │
   │   - List supporting edges with β, SE_eff, k (study count)  │
   │   - List supporting studies (from edge_evidence_v1 LER IDs) │
   │   - Show claim level (causal/associational/model_implied)   │
   │   - Show prior type used (RobustMAP/Commensurate/etc.)     │
   │ Output: ProvenanceChain per intervention                    │
   └─────────────────────────────────────────────────────────────┘

## RT-I2 — Uncertainty Disclosure
   Purpose: Generate mandatory uncertainty disclosure for clinical output
   ┌─────────────────────────────────────────────────────────────┐
   │ Content:                                                     │
   │ 1. Decision stability class + P(rank₁)                      │
   │ 2. 95% CrI for top intervention's benefit                   │
   │ 3. 5-source variance decomposition (from ALG-F3)            │
   │ 4. Top 2 reducible uncertainty sources                      │
   │ 5. Decision-critical edges (from ALG-F2c)                   │
   │ 6. If HIGHLY_UNSTABLE: mandatory warning text               │
   │ Rules: ALWAYS included; cannot be suppressed                 │
   └─────────────────────────────────────────────────────────────┘

## RT-I3 — Session Summary
   Purpose: Summarize the full session for audit and continuity
   Content: Questions asked, answers received, state evolution, ranking changes
   Writes: recommendation_runs_v1 (session anchor with timestamp, patient_id, version)

## RT-I4 — Report Assembly
   Purpose: Package everything into RecommendationReport for SYS_PRESENTATION
   ┌─────────────────────────────────────────────────────────────┐
   │ RecommendationReport structure:                              │
   │   header: {session_id, timestamp, model_version, patient_id}│
   │   composite: {CRCI_score, severity_tier, percentile}        │
   │   recommendations: [{intervention, SAFE_A, SAFE_B, CrI,    │
   │                      schedule, provenance}]                  │
   │   trajectories: [{timepoint, mean, CrI_lower, CrI_upper}]  │
   │   uncertainty: {stability, variance_decomp, critical_edges} │
   │   pathway_profile: [{pathway, activation, dysregulation}]   │
   │   session: {questions_asked, state_updates, total_time}     │
   │   audit: {decision_trace, prior_selection_log}              │
   │ Format: JSON → SYS_PRESENTATION renders                     │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: edges_v1, edge_evidence_v1, state_snapshots_v1, schedule_plans_v1,
          question_sequence_v1, intervention_rankings_v1, temporal_trajectories_v1
   WRITES: recommendation_runs_v1, decision_trace_v1

5. INTERMEDIATE STATE SCHEMAS

   ### State: ProvenanceChain (after I1, per intervention)
   | Field | Type | Description |
   |-------|------|-------------|
   | intervention_id | str | action_catalog_v1 FK |
   | supporting_edges | list[{edge_id, β, SE_eff, k, claim_level}] | Evidence chain |
   | supporting_studies | list[ler_id] | From edge_evidence_v1 |
   | prior_type | ENUM | RobustMAP/Commensurate/Power/etc. |

   ### State: UncertaintyDisclosure (after I2)
   | Field | Type | Description |
   |-------|------|-------------|
   | stability_class | ENUM(Stable/Moderate/Unstable/Highly_unstable) | From ALG-F2 |
   | p_rank1 | float | Probability top intervention stays top |
   | cri_95 | {lower, upper} | 95% CrI for top benefit |
   | variance_decomposition | dict[source→pct] | 5-source from ALG-F3 |
   | top_reducible_sources | list[str, 2] | Actionable uncertainty |
   | critical_edges | list[edge_id] | Decision-critical from ALG-F2c |

   ### State: RecommendationReport (TYPE 3 INTERFACE CONTRACT — I4 output)
   This is the PRIMARY handoff from SYS_RUNTIME to SYS_PRESENTATION.
   | Field | Type | Description |
   |-------|------|-------------|
   | header | {session_id, timestamp, model_version, patient_id} | Session metadata |
   | composite | {CRCI_score, severity_tier, percentile, subdomains[11]} | Composite outcome |
   | recommendations | list[{intervention, SAFE_A, SAFE_B, CrI, schedule, provenance}] | Ranked |
   | trajectories | list[{timepoint, mean, CrI_lower, CrI_upper, temporal_source}] | From ALG-E |
   | uncertainty | {stability, variance_decomp, critical_edges, warning_text?} | Mandatory |
   | pathway_profile | list[{pathway, activation_z, dysregulation_flag}] | 20 pathways |
   | session | {questions_asked, state_updates[], total_time_sec} | Session log |
   | audit | {decision_trace, prior_selection_log, rankability_scores} | Full audit trail |

6. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | I-A1 | Provenance chain traces to study level (not individual patient data) | Low |
   | I-A2 | Uncertainty disclosure always included (cannot be suppressed) | Design decision |
   | I-A3 | RecommendationReport JSON contract stable across model versions | High — PRES depends on schema |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: VAL-01 (Complexity-Scaling Validation)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_RUNTIME

1. IDENTITY
   Chain ID:       VAL-01
   Name:           Complexity-Scaling Validation
   Purpose:        Validate that system behavior scales correctly with model
                   complexity — test with reduced graphs, verify convergence,
                   benchmark performance
   Phase:          Build-time + periodic runtime validation
   Paper §:        §4.5 (implied)
   Subsystems:     3 (V1–V3)

2. SUBSYSTEM DETAIL

## VAL-01-V1 — Reduced Graph Testing
   Run ALG pipeline on progressively smaller subgraphs (10, 20, 40, 63 nodes)
   Verify: output structure unchanged, computation time scales predictably

## VAL-01-V2 — Convergence Validation
   Verify MC draws converge: run 1K, 5K, 10K, 50K draws
   Check: SAFE ranking stable between 10K and 50K (< 2% rank change)

## VAL-01-V3 — Performance Benchmarking
   Measure: end-to-end latency, memory usage, disk writes per session
   Threshold: < 30 seconds for full inference + simulation (TBD)

═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
                    PART 3: TIER 3 — SUBSYSTEM CARDS
                    (14 subsystems across 4 chains)
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
CHAIN RT-G: Schedule Optimization (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## RT-G1 — Candidate Expansion
   ID: RT-G1 | Type: COMPOSITE | Phase: Runtime
   Purpose: Expand ranked interventions into ~50-100 schedule candidates
   Interface Contract:
     Inputs:  | ClinicalOutputPackage | from ALG-F | YES |
              | dose_response_params_v1 | dose variants | YES |
              | action_catalog_v1 | intervention definitions | YES |
     Outputs: | ExpandedPool | list[ScheduleCandidate] ~50-100 | → G2 | IN-MEMORY |
   Process: Top-K (default 10) → dose variants (low/standard/high) → timing variants
     (immediate/phased/sequential) → pairwise bundles (top-3) + triple (top-1)
   Validation: Pool size ≤ 100; all candidates have valid action_ids
   Connections: ALG-F→G1→G2

## RT-G2 — Constraint Filtering
   ID: RT-G2 | Type: COMPOSITE | Phase: Runtime
   Purpose: Remove candidates violating hard constraints + zero-rule catch-all [Gap-3]
   Interface Contract:
     Inputs:  | ExpandedPool | from G1 | YES |
              | contraindication_rules_v1 | safety rules | YES |
              | patient_preferences | from session | NO |
     Outputs: | FeasibleSet | {candidates[], excluded[{candidate, reason}]} | → G3 | IN-MEMORY |
   Process: Evaluate all rules per (action, patient) → hard→EXCLUDE, soft→WARN
     → post-eval meta-check: CATCH_ACTIVE_TREATMENT, CATCH_RARE_CANCER, CATCH_ZERO_MATCH_RISKY
   Validation: All candidates have rule evaluation logged; catch-all evaluated
   Writes: contraindication_eval_trace_v1
   Connections: G1→G2→G3

## RT-G3 — Schedule Assembly
   ID: RT-G3 | Type: COMPOSITE | Phase: Runtime
   Purpose: Assemble timing + dose + ordering for feasible candidates, rank by SAFE_B
   Interface Contract:
     Inputs:  | FeasibleSet | from G2 | YES |
              | intervention_kernels_v1 | duration info | YES |
     Outputs: | Schedules[] | list[Schedule] sorted by SAFE_B | → G4 | IN-MEMORY |
   Process: Assign start time → duration → dose → compute expected trajectory → sort SAFE_B
   Writes: schedule_plans_v1 (top 5), schedule_items_v1 (per item)
   Connections: G2→G3→G4

## RT-G4 — Stability Classification
   ID: RT-G4 | Type: ATOMIC | Phase: Runtime
   Purpose: Attach decision stability from ALG-F2 to ranked schedules
   Interface Contract:
     Inputs:  | Schedules[] | from G3 | YES |
              | StabilityState | from ALG-F2 | YES |
     Outputs: | RankedSchedules | with stability flags | → RT-H | IN-MEMORY |
   Process: P(rank₁) → Stable/Moderate/Unstable/Highly_unstable classification (Formula G-3)
   Writes: decision_trace_v1
   Connections: G3→G4→RT-H; Reads ALG-F2 StabilityState

───────────────────────────────────────────────────────────────────────────
CHAIN RT-H: Adaptive Questioning (3 subsystems)
───────────────────────────────────────────────────────────────────────────

## RT-H1 — Question Selection
   ID: RT-H1 | Type: COMPOSITE | Phase: Runtime (interactive loop)
   Purpose: Select next question maximizing information gain
   Interface Contract:
     Inputs:  | PosteriorState | from ALG-C (updated each loop) | YES |
              | question_bank_v1 | unanswered questions | YES |
     Outputs: | NextQuestion | {question_id, target_nodes, instrument_id, expected_ig, text} | → patient | IN-MEMORY |
   Process: For each unanswered q: compute IG(q) = H(θ|current) − E_y[H(θ|current ∪ y_q)]
     (Formula H-1/H-2); select argmax; mandatory questions first; instrument grouping
   Validation: IG computed for all candidates; selected question ∈ question_bank_v1
   Writes: question_selection_trace_v1 (IG values for all candidates)
   Connections: ALG-C→H1→patient; Reads question_bank_v1

## RT-H2 — Answer Integration
   ID: RT-H2 | Type: ATOMIC | Phase: Runtime
   Purpose: Parse patient answer, validate, package as new observation for ALG-C
   Interface Contract:
     Inputs:  | PatientAnswer | {question_id, raw_response} from patient | YES |
     Outputs: | NewObservation | {node_id, value, instrument_id} | → ALG-C | IN-MEMORY |
   Process: Parse → map to instrument scale → validate range → add to observation set
   Decision: Valid → ALG-C re-inference; Invalid → re-prompt; "don't know" → skip (missing)
   Writes: question_sequence_v1
   Connections: patient→H2→ALG-C (triggers re-inference loop)

## RT-H3 — Stopping Decision
   ID: RT-H3 | Type: ATOMIC | Phase: Runtime
   Purpose: Evaluate 5 stopping criteria (Formula H-3)
   Interface Contract:
     Inputs:  | Updated PosteriorState | from ALG-C re-inference | YES |
              | Session metrics | question count, last IG, var reduction | YES |
     Outputs: | Decision | CONTINUE or STOP | → H1 loop or RT-I | IN-MEMORY |
   5 criteria (any → STOP): IG < 0.01; P(rank₁) ≥ 0.80; questions ≥ 15;
     patient requests stop; variance reduction < 5% from last question
   Connections: H2→ALG-C→H3; H3→H1 (loop) or H3→RT-I (exit)

───────────────────────────────────────────────────────────────────────────
CHAIN RT-I: Reporting & Provenance (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## RT-I1 — Evidence Provenance
   ID: RT-I1 | Type: COMPOSITE | Phase: Runtime
   Purpose: Trace each recommendation back to supporting evidence + studies
   Interface Contract:
     Inputs:  | RankedSchedules | from RT-G | YES |
              | edges_v1, edge_evidence_v1 | evidence chain | YES |
     Outputs: | ProvenanceChain[] | per intervention: edges, studies, claim levels, priors | → I2 |
   Process: For each intervention → list supporting edges (β, SE_eff, k) → list LER IDs
     → attach claim level (causal/associational/model_implied) → attach prior type
   Connections: RT-G→I1→I2; Reads edges_v1, edge_evidence_v1

## RT-I2 — Uncertainty Disclosure (MANDATORY)
   ID: RT-I2 | Type: ATOMIC | Phase: Runtime
   Purpose: Generate mandatory uncertainty disclosure — CANNOT BE SUPPRESSED
   Interface Contract:
     Inputs:  | ALG-F2 StabilityState | stability + P(rank₁) | YES |
              | ALG-F3 VarianceDecomposition | 5-source breakdown | YES |
     Outputs: | UncertaintyDisclosure | stability, CrI, variance, critical edges, warning? | → I3 |
   Content: (1) stability class + P(rank₁), (2) 95% CrI for top benefit,
     (3) 5-source variance decomposition, (4) top 2 reducible sources,
     (5) decision-critical edges, (6) HIGHLY_UNSTABLE → mandatory warning text
   Connections: ALG-F→I2→I3

## RT-I3 — Session Summary
   ID: RT-I3 | Type: ATOMIC | Phase: Runtime
   Purpose: Summarize full session for audit trail and continuity
   Inputs: All session data (questions, answers, state evolution, ranking changes)
   Writes: recommendation_runs_v1 (session anchor: timestamp, patient_id, model_version)
   Connections: I2→I3→I4

## RT-I4 — Report Assembly
   ID: RT-I4 | Type: COMPOSITE | Phase: Runtime
   Purpose: Package RecommendationReport (TYPE 3 interface contract) for SYS_PRESENTATION
   Interface Contract:
     Inputs:  | ProvenanceChain[], UncertaintyDisclosure, SessionSummary | from I1-I3 | YES |
     Outputs: | RecommendationReport | JSON (see RT-I §5 Intermediate States) | → PRES | TYPE 3 |
   8 fields: header, composite, recommendations, trajectories, uncertainty,
     pathway_profile, session, audit
   Writes: recommendation_runs_v1 (final report payload)
   Connections: I3→I4→SYS_PRESENTATION

───────────────────────────────────────────────────────────────────────────
CHAIN VAL-01: Complexity-Scaling Validation (3 subsystems)
───────────────────────────────────────────────────────────────────────────

## VAL-01-V1 — Reduced Graph Testing
   ID: VAL-01-V1 | Type: ATOMIC | Phase: Build-time + periodic
   Purpose: Verify output structure unchanged with smaller subgraphs
   Process: Run ALG pipeline on 10, 20, 40, 63 node subgraphs; check output schema
   Validation: Output structure identical; computation time scales predictably

## VAL-01-V2 — Convergence Validation
   ID: VAL-01-V2 | Type: ATOMIC | Phase: Build-time + periodic
   Purpose: Verify MC draws converge
   Process: Run 1K, 5K, 10K, 50K draws; check SAFE ranking stability
   Validation: < 2% rank change between 10K and 50K draws

## VAL-01-V3 — Performance Benchmarking
   ID: VAL-01-V3 | Type: ATOMIC | Phase: Periodic
   Purpose: Measure end-to-end latency, memory, disk writes
   Threshold: < 30 seconds for full inference + simulation (target TBD)

                    APPENDIX: CROSS-REFERENCE VALIDATION
═══════════════════════════════════════════════════════════════════════════

A. PAPER SECTION COVERAGE
   §2.16 SAFE Score        → RT-G (schedule ranking by SAFE_A/SAFE_B)
   §2.19 Decision Stability → RT-G4 (stability classification attachment)
   §2.20 Composite Outcome → RT-I (CRCI score in report)
   §4.5 Output Architecture → RT-I4 (3-mode output packaging)

B. TABLE READS/WRITES
   RT-G: READS action_catalog_v1, contraindication_rules_v1, objective_specs_v1,
         dose_response_params_v1, intervention_kernels_v1
         WRITES schedule_plans_v1, schedule_items_v1, decision_trace_v1
   RT-H: READS question_bank_v1, state_snapshots_v1
         WRITES question_sequence_v1, question_selection_trace_v1, state_snapshots_v1
   RT-I: READS all Class E output tables + edges_v1 + edge_evidence_v1
         WRITES recommendation_runs_v1, decision_trace_v1

C. SUBSYSTEM CONSISTENCY
   RT-G: G1, G2, G3, G4           (4 subsystems)
   RT-H: H1, H2, H3               (3 subsystems)
   RT-I: I1, I2, I3, I4           (4 subsystems)
   VAL-01: V1, V2, V3             (3 subsystems)
   TOTAL: 14 subsystems ✓

D. DATA FLOW: END-TO-END
   ALG-F (3 output packages)
     → RT-G (expand → filter → schedule → rank)
       → RT-H (adaptive questions → ALG-C re-inference loop)
         → RT-I (provenance → uncertainty → session → report)
           → SYS_PRESENTATION (renders RecommendationReport)

═══════════════════════════════════════════════════════════════════════════
END OF SYS_RUNTIME COMPLETE SPECIFICATION
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
CHANGE LOG: GAP FIXES APPLIED
───────────────────────────────────────────────────────────────────────────
Gap-3 (RT-G2): Added zero-rule catch-all safety net. 3 catch-all rules
  in contraindication_rules_v1: CATCH_ACTIVE_TREATMENT (escalate),
  CATCH_RARE_CANCER (soft_warn), CATCH_ZERO_MATCH_RISKY (meta-rule:
  fires when no other rules fired AND patient has risk factors).
  5 lines of post-evaluation logic in RT-G2. No schema changes —
  existing severity ENUM and escalation_id FK handle this.
───────────────────────────────────────────────────────────────────────────
