═══════════════════════════════════════════════════════════════════════════
 CRCI — CONVERSION VALIDITY MATRIX & MATHEMATICAL HARDENING ADDENDUM
 Executable contracts for effect-size conversion, verification escalation,
 missingness provenance, shared-control handling, and freshness policies
═══════════════════════════════════════════════════════════════════════════
 v1.0 — Companion to HETEROGENEOUS_PAPER_TREATMENT_PROTOCOL.md
 Amends: SYS_EXTRACTION_COMPLETE.md (EX-TB-CN, EX-P2-S2, EX-P3-L7)
         HETEROGENEOUS_PAPER_TREATMENT_PROTOCOL.md (Part 4, Mechanisms 2-3)
═══════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════
 MODULE 1: CONVERSION VALIDITY MATRIX
 Replaces the prose conversion rules in Treatment Protocol Part 4 Stage 4
 with executable, design-conditional contracts
═══════════════════════════════════════════════════════════════════════════

PURPOSE: Every effect-size conversion has preconditions. If those
preconditions are not met, the conversion introduces systematic bias.
This matrix defines EXACTLY when each conversion is valid, what extra
fields it requires, and what happens when those fields are missing.

ENFORCEMENT: EX-TB-CN (ClaimNormalizer) and EX-P2-S2 (Conversion
Appropriateness) must implement these rules as hard gates. A conversion
that fails its validity check MUST NOT proceed — it falls through to
the next valid pathway or is BLOCKED.


1.1 EFFECT SIZE → SMD (Cohen's d) CONVERSIONS
──────────────────────────────────────────────

┌─────────────┬────────────────────────┬────────────────────┬──────────────────────┬───────────────┬──────────────┐
│ Source       │ Formula                │ Valid When          │ Required Fields       │ If Fields Miss │ Bias Risk    │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ d (reported) │ d = d                  │ Always              │ d                    │ N/A           │ NONE         │
│             │ SE_d = √(1/n₁+1/n₂    │                    │ n₁, n₂               │ Use total N/2 │              │
│             │       +d²/(2(n₁+n₂)))  │                    │                      │ inflate SE×1.1│              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Hedges' g   │ d = g × J⁻¹            │ Always              │ g, df                │ df = N-2      │ NONE         │
│ (reported)  │ J = 1−3/(4df−1)        │                    │                      │ (conservative)│              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Mean diff   │ d = (M₁−M₂)/SD_pooled  │ Two independent    │ M₁, M₂, SD₁, SD₂,  │ BLOCKED if no │ LOW          │
│ + SDs       │ SD_p = √[(SD₁²(n₁-1)  │ groups             │ n₁, n₂               │ SDs reported. │              │
│             │  +SD₂²(n₂-1))/(N-2)]  │                    │                      │ Try SD borrow.│              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Mean diff   │ d = ΔM / SD_change      │ Pre-post within-   │ ΔM, SD_change        │ If SD_change  │ MODERATE     │
│ (pre-post)  │ OR d = ΔM / SD_baseline│ subjects design     │ OR ΔM, SD_baseline   │ missing: try  │ SD_baseline  │
│             │                        │ (repeated measures) │                      │ SD_baseline.  │ inflates d   │
│             │                        │                    │                      │ Flag: APPROX  │ vs SD_change │
│             │ NOTE: SD_change ≠      │                    │                      │               │              │
│             │ SD_baseline. Prefer    │                    │                      │               │              │
│             │ SD_change when avail.  │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ t-statistic │ d = t × √(1/n₁+1/n₂)  │ Independent two-   │ t, n₁, n₂            │ If only total │ LOW          │
│             │                        │ group t-test ONLY   │                      │ N: assume n₁  │              │
│             │                        │ NOT paired t, NOT   │                      │ = n₂ = N/2    │              │
│             │                        │ one-sample t        │                      │               │              │
│             │ For paired t:          │ Paired design       │ t, n_pairs, r_pre_post│ BLOCKED if   │ HIGH if r    │
│             │ d = t/√n × √(2(1-r))  │                    │                      │ r unknown.    │ unknown      │
│             │ r = pre-post corr      │                    │                      │ Default r=0.5 │              │
│             │                        │                    │                      │ inflate SE×1.3│              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ F-statistic │ d = 2√(F/N)            │ ONE-WAY ANOVA with │ F, N, df_num=1       │ BLOCKED if    │ HIGH if      │
│ (2-group)   │                        │ EXACTLY 2 groups   │                      │ df_num ≠ 1.   │ misapplied   │
│             │                        │ (df_numerator = 1)  │                      │ Cannot convert│ to >2 groups │
│             │                        │                    │                      │ multi-group F │              │
│             │ F (>2 groups):         │ NEVER → d          │ —                    │ Use contrast  │ BLOCKED      │
│             │ d is undefined for     │                    │                      │ t-test if     │              │
│             │ omnibus F with >2 grps │                    │                      │ available     │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ η² (partial)│ d = 2√(η²_p/(1−η²_p)) │ Two-group designs  │ η²_partial, N        │ If total η²   │ MODERATE     │
│             │                        │ OR when df_num = 1  │ df_num = 1           │ reported      │ Inflated for │
│             │                        │                    │                      │ instead: d =  │ complex      │
│             │ Total η²:             │ ONLY when the model │ η²_total, df_effect, │ 2√(η²_t/(1-  │ designs      │
│             │ d = 2√(η²_t/(1−η²_t)) │ has ONE predictor   │ df_error             │ η²_t)) with   │              │
│             │ × √(df_e/df_eff)       │ (simple designs)    │                      │ flag APPROX   │              │
│             │                        │                    │                      │ inflate SE×1.2│              │
│             │ NOTE: partial ≠ total. │ Must be identified  │                      │ If ambiguous: │ HIGH if      │
│             │ Papers often don't     │ from context        │                      │ BLOCKED       │ confused     │
│             │ specify which.         │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ r (Pearson) │ d = 2r/√(1−r²)        │ Bivariate only.     │ r, N                 │ If r from     │ LOW for      │
│             │ SE_d = 4/(N(1-r²))     │ NOT partial r.      │                      │ multiple      │ bivariate.   │
│             │                        │ NOT semipartial r.  │                      │ regression:   │ HIGH for     │
│             │ For partial r:         │                    │ partial_r, N, p_cov  │ BLOCKED unless│ partial r    │
│             │ BLOCKED unless N, p are│                    │ (# covariates)       │ p known.      │ misapplied   │
│             │ known. Then Fisher z   │                    │                      │               │              │
│             │ with df = N−p−2.       │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ χ² (2×2)    │ d = 2×arcsin(√p₁)     │ 2×2 contingency    │ χ², N, cell counts   │ If no cell    │ MODERATE     │
│             │   −2×arcsin(√p₂)       │ table only          │ or proportions       │ counts:       │              │
│             │ OR approximate:        │                    │                      │ d ≈ 2√(χ²/N)  │              │
│             │ d ≈ 2√(χ²/N)           │                    │                      │ inflate SE×1.2│              │
│             │                        │ NOT for χ² with    │                      │               │              │
│             │                        │ df > 1             │                      │               │              │
└─────────────┴────────────────────────┴────────────────────┴──────────────────────┴───────────────┴──────────────┘

CRITICAL RULES:
  R1: When a formula has a "Valid When" condition, that condition is a
      HARD gate. If the condition is not met, the conversion is BLOCKED.
  R2: "If Fields Missing" defines the fallback. Fallbacks always inflate
      SE to account for the additional uncertainty.
  R3: Multiple conversions NEVER chain. You cannot go r→d→logOR.
      One conversion per record maximum.
  R4: Every conversion logs: source_type, target_type, formula_used,
      fields_present, fields_missing, se_inflation_applied.


1.2 RATIO MEASURES (OR, HR, RR) → LOG SCALE
────────────────────────────────────────────

┌─────────────┬────────────────────────┬────────────────────┬──────────────────────┬───────────────┬──────────────┐
│ Source       │ Formula                │ Valid When          │ Required Fields       │ If Fields Miss │ Bias Risk    │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ OR → ln(OR) │ β = ln(OR)             │ Always              │ OR                   │ N/A           │ NONE         │
│             │ SE = √(1/a+1/b+1/c+1/d)│ With cell counts    │ a, b, c, d           │ SE from CI or │              │
│             │ OR SE=(ln(CI_u)-        │ OR with CI          │ OR + CI              │ p-value.      │              │
│             │ ln(CI_l))/3.92         │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ HR → ln(HR) │ β = ln(HR)             │ Always              │ HR                   │ N/A           │ NONE on log  │
│             │ SE = (ln(CI_u)-         │ With CI (standard)  │ HR + CI              │ If no CI:     │ scale        │
│             │ ln(CI_l))/3.92         │                    │                      │ from p-value  │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ RR → ln(RR) │ β = ln(RR)             │ Always              │ RR                   │ N/A           │ NONE on log  │
│             │ SE = (ln(CI_u)-         │ With CI             │ RR + CI              │ From p-value  │ scale        │
│             │ ln(CI_l))/3.92         │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ OR → d      │ d = ln(OR)×√3/π        │ Logistic model with │ OR, SE_logOR         │ If not logistic│ MODERATE     │
│ (Hasselblad │ ≈ ln(OR)×0.5513       │ continuous latent   │                      │ model: BLOCKED│ Assumes      │
│  & Hedges)  │ SE_d = SE_logOR×0.5513│ outcome assumed      │                      │               │ logistic     │
│             │                        │                    │                      │               │ distribution │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ HR → OR     │ OR ≈ HR                │ ONLY when event is  │ HR, event_rate       │ BLOCKED if    │ HIGH if      │
│             │                        │ RARE (rate < 10%)   │                      │ event_rate    │ events are   │
│             │                        │ AND follow-up is    │                      │ unknown or    │ common       │
│             │                        │ SHORT relative to   │                      │ > 10%.        │              │
│             │                        │ event timing        │                      │ Keep on log   │              │
│             │                        │                    │                      │ HR scale.     │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ HR → d      │ NOT RECOMMENDED        │ NEVER directly.     │ —                    │ —             │ VERY HIGH    │
│             │ If needed: HR → ln(HR) │ Different estimands.│                      │               │ Estimand     │
│             │ and keep on log scale. │ HR is time-to-event;│                      │               │ mismatch     │
│             │                        │ d is group diff.    │                      │               │              │
└─────────────┴────────────────────────┴────────────────────┴──────────────────────┴───────────────┴──────────────┘

CRITICAL RULE for ratio measures:
  R5: HR, OR, RR are pooled on LOG SCALE (ln(HR), ln(OR), ln(RR)).
      They are NOT converted to SMD unless the pooling target for
      that edge is explicitly SMD AND the conversion conditions are met.
  R6: Mixed-scale pooling (some studies report d, others report OR
      for the same edge) requires an explicit decision:
      - If edge is primarily continuous outcomes → convert OR→d (1.2)
      - If edge is primarily binary outcomes → convert d→logOR
      - If ambiguous → BLOCKED, flag for human review
      The edge's scale_target is set in edge_relations_definitions_v1.


1.3 CORRELATION → FISHER Z (for pooling)
─────────────────────────────────────────

┌─────────────┬────────────────────────┬────────────────────┬──────────────────────┬───────────────┬──────────────┐
│ Source       │ Formula                │ Valid When          │ Required Fields       │ If Fields Miss │ Bias Risk    │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ r → Fisher z│ z = 0.5×ln((1+r)/(1-r))│ Bivariate r only    │ r, N                 │ N/A (r and N │ NONE         │
│             │ SE_z = 1/√(N-3)        │ N ≥ 10              │                      │ are required) │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Back-        │ r = (e^(2z)-1)/        │ After pooling       │ z_pooled, SE_pooled  │ N/A           │ NONE         │
│ transform   │ (e^(2z)+1)             │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Partial r   │ z = 0.5×ln((1+r_p)/    │ ONLY if df_residual │ partial_r,           │ BLOCKED if    │ MODERATE     │
│             │ (1-r_p))               │ is known            │ N, p_covariates      │ p unknown     │              │
│             │ SE_z = 1/√(N-p-3)      │                    │                      │               │              │
├─────────────┼────────────────────────┼────────────────────┼──────────────────────┼───────────────┼──────────────┤
│ Spearman ρ  │ Treat as Pearson r     │ N ≥ 20              │ ρ, N                 │ Same as r     │ LOW          │
│             │ (approximation)        │                    │                      │               │ (conservative│
│             │ inflate SE × 1.06      │                    │                      │               │  for N > 20) │
└─────────────┴────────────────────────┴────────────────────┴──────────────────────┴───────────────┴──────────────┘


1.4 SE DERIVATION CASCADE (replaces prose in Treatment Protocol)
────────────────────────────────────────────────────────────────

This formalizes the 6-level precision cascade with exact conditions:

┌───────┬──────────────────────────┬──────────────────────────┬────────────┬──────────────┐
│ Level │ Source                    │ Formula                   │ Inflation  │ Quality Tag  │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L1   │ SE reported directly      │ SE = SE_reported          │ 1.00×      │ DIRECT       │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L2a  │ 95% CI reported           │ SE = (CI_u−CI_l)/3.92    │ 1.00×      │ DERIVED_EXACT│
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L2b  │ 99% CI reported           │ SE = (CI_u−CI_l)/5.152   │ 1.00×      │ DERIVED_EXACT│
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L2c  │ 90% CI reported           │ SE = (CI_u−CI_l)/3.290   │ 1.00×      │ DERIVED_EXACT│
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L3a  │ Exact p-value + effect    │ z = Φ⁻¹(1−p/2)           │ 1.05×      │ DERIVED_PVAL │
│       │                          │ SE = |effect|/z            │            │              │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L3b  │ Bounded p (e.g. p<0.05)  │ Use boundary value        │ 1.10×      │ DERIVED_PBOUND│
│       │                          │ p<0.05 → use p=0.05       │            │              │
│       │                          │ p<0.01 → use p=0.01       │            │              │
│       │                          │ p<0.001 → use p=0.001     │            │              │
│       │                          │ This WIDENS SE (conserv.)  │            │              │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L4a  │ N per group + d          │ SE_d = √(1/n₁+1/n₂       │ 1.15×      │ ESTIMATED_N  │
│       │                          │ +d²/(2(n₁+n₂)))          │            │              │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L4b  │ Total N only + d         │ Assume n₁=n₂=N/2          │ 1.20×      │ ESTIMATED_N  │
│       │                          │ Then L4a formula           │            │ (EQUAL_ASSUMED)│
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L5   │ SD borrowed + N          │ SD from sd_anchors_v1      │ Tier-dep:  │ SD_BORROWED  │
│       │                          │ SE = SD_pooled/√(N/2)      │ T1: 1.15×  │              │
│       │                          │                          │ T2: 1.30×  │              │
│       │                          │                          │ T3: 1.50×  │              │
├───────┼──────────────────────────┼──────────────────────────┼────────────┼──────────────┤
│  L6   │ Direction only (no       │ Cannot compute SE.         │ N/A        │ QUALITATIVE  │
│       │ numeric precision)       │ Record as qualitative.     │            │              │
│       │                          │ Does NOT enter IVW pool.   │            │              │
│       │                          │ Used for sign-check only.  │            │              │
└───────┴──────────────────────────┴──────────────────────────┴────────────┴──────────────┘

EXECUTION RULE: Try levels in order (L1 → L2 → L3 → L4 → L5 → L6).
Use the FIRST level where all required fields are available.
Log: se_derivation_level, se_inflation_applied, fields_used.


═══════════════════════════════════════════════════════════════════════════
 MODULE 2: INFLUENCE-AWARE VERIFICATION ESCALATION
 Amends Treatment Protocol Part 4 Mechanism 3 (verification tiers)
═══════════════════════════════════════════════════════════════════════════

The existing Tier 1/2/3 system is correct as a baseline but insufficient.
A single edge evidence record CAN be high-stakes even though edges are
generally Tier 3 (IVW pooling protection).

2.1 ESCALATION TRIGGERS

After IVW pooling (EX-P4), compute per-record influence metrics:

  w_i = (1/SE²_i) / Σ(1/SE²_j)    [IVW weight share]

ESCALATE an edge evidence record from Tier 3 to Tier 1 (100% verify) if
ANY of the following conditions are met:

┌──────┬─────────────────────────────────┬────────────────────────────┐
│ Rule │ Condition                        │ Rationale                   │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E1   │ w_i > 0.50                       │ Record contributes >50% of │
│      │ (single record has majority      │ pooled estimate. Error in  │
│      │ weight in IVW pool)              │ this record ≈ error in     │
│      │                                 │ final parameter.           │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E2   │ k < 3 for the edge              │ With only 1-2 studies,     │
│      │ (fewer than 3 evidence records   │ there is no pooling        │
│      │ for this edge)                   │ protection regardless of   │
│      │                                 │ parameter type.            │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E3   │ Removing this record flips the  │ The sign of the pooled     │
│      │ sign of β̂_pooled                │ estimate depends on this   │
│      │ (sign-flip sensitivity)          │ one record. Clinical       │
│      │                                 │ direction is uncertain.    │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E4   │ Record is the ONLY cancer-      │ All other records are from │
│      │ matched study (w_scope = 1.0)    │ non-cancer or different    │
│      │ and k_total ≤ 5                  │ cancer populations. This   │
│      │                                 │ record anchors scope.      │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E5   │ se_derivation_level ≥ L4        │ SE was estimated from N    │
│      │ AND w_i > 0.30                   │ alone or borrowed — AND    │
│      │                                 │ the record has substantial │
│      │                                 │ weight. Precision is soft. │
├──────┼─────────────────────────────────┼────────────────────────────┤
│ E6   │ Record extracted from MA forest │ Forest plot data is        │
│      │ plot (meta_source_flag =         │ provisional and lower      │
│      │ FOREST_PLOT_ENTRY)               │ accuracy than full paper   │
│      │ AND NOT superseded               │ extraction.                │
└──────┴─────────────────────────────────┴────────────────────────────┘

2.2 IMPLEMENTATION

The escalation check runs in EX-P4 AFTER IVW pooling, BEFORE finalizing
the compiled edge. If any record triggers escalation:

  1. Flag record: verification_status = ESCALATED_TO_TIER1
  2. Flag edge: compiled_edge_status = PENDING_VERIFICATION
  3. Queue the flagged record for human verification
  4. The edge is usable in the model BUT its SE_eff gains an
     additional unverified_inflation = 1.20× until verified

After human verification:
  - If the record is confirmed correct: remove inflation, mark VERIFIED
  - If the record has errors: correct the values, re-run pooling


═══════════════════════════════════════════════════════════════════════════
 MODULE 3: MISSINGNESS PROVENANCE TAXONOMY
 Amends Treatment Protocol Part 5 (completeness tracking)
═══════════════════════════════════════════════════════════════════════════

3.1 THE PROBLEM

The completeness report says "component X: missing." But WHY is it
missing? This matters because the acquisition loop's response differs:

  - Truly absent → search for a different paper that has it
  - Our parser failed → re-run parser, don't search for more papers
  - Our agent missed it → review agent prompt, don't search
  - Guarded rejection → the data existed but was image-only or ambiguous

3.2 MISSINGNESS CODES

Add to every component in the extraction completeness report:

┌──────────────────┬────────────────────────────────────────────────────┐
│ Code              │ Meaning                                             │
├──────────────────┼────────────────────────────────────────────────────┤
│ PRESENT           │ Component successfully extracted                    │
├──────────────────┼────────────────────────────────────────────────────┤
│ ABSENT_IN_PAPER   │ Paper genuinely does not contain this data.         │
│                  │ Confirmed by component inventory (not detected)     │
│                  │ AND agent inspection found no relevant sections.    │
│                  │ Action: SEARCH for different papers.                │
├──────────────────┼────────────────────────────────────────────────────┤
│ PARSE_FAILURE     │ PDF parsing failed for relevant section/table.      │
│                  │ Text was garbled, table structure lost, OCR failed. │
│                  │ Action: RE-PARSE with different parser settings,    │
│                  │ or acquire a different PDF version.                 │
├──────────────────┼────────────────────────────────────────────────────┤
│ AGENT_MISS        │ Component inventory detected the component, but     │
│                  │ the agent failed to extract it. Agent returned      │
│                  │ empty SpanLabels for an expected component.         │
│                  │ Action: RE-RUN agent with adjusted prompt or        │
│                  │ flag for manual extraction.                         │
├──────────────────┼────────────────────────────────────────────────────┤
│ GUARDED_REJECTION │ Data exists but was blocked by a guardrail:         │
│                  │   - Figure-only data (UG-05)                        │
│                  │   - Sensitivity analysis only (UG-08)               │
│                  │   - Umbrella review estimate (MG-04)                │
│                  │ Action: ACCEPT the block. Log for audit.            │
│                  │ Search for different papers if high priority.       │
├──────────────────┼────────────────────────────────────────────────────┤
│ TB_REJECTION      │ Agent extracted it, but trust boundary rejected     │
│                  │ (implausible value, failed conversion validity).     │
│                  │ Action: REVIEW the rejection reason. If legitimate  │
│                  │ data that failed a too-strict rule, adjust rule.    │
│                  │ If genuine error, discard.                          │
├──────────────────┼────────────────────────────────────────────────────┤
│ PARTIAL           │ Component partially extracted (e.g., effect size    │
│                  │ extracted but SE could not be derived — record is   │
│                  │ qualitative-only or SE was estimated at L4/L5).     │
│                  │ Action: Usable with inflated SE. Low priority to    │
│                  │ search for replacements.                            │
└──────────────────┴────────────────────────────────────────────────────┘

3.3 SCHEMA

Add to extraction_completeness report (per component per paper):

  missingness_code: ENUM (above codes)
  missingness_detail: TEXT (specific reason)
  agent_id: TEXT (which agent was responsible)
  corrective_action: ENUM {search, reparse, rerun_agent, manual, accept, review_rule}

3.4 ACQUISITION LOOP INTEGRATION

The gap analysis (EX-P5) must check missingness codes before generating
acquisition queries:

  IF missingness_code = AGENT_MISS for ≥3 papers for the same component:
    → Agent prompt needs revision, not more papers.
  IF missingness_code = PARSE_FAILURE for ≥3 papers:
    → Parser issue, not evidence gap. Try alternate PDF sources.
  IF missingness_code = ABSENT_IN_PAPER for ≥3 papers:
    → Genuine evidence gap. Generate acquisition query.
  IF missingness_code = GUARDED_REJECTION consistently:
    → The data exists but in figure-only format. Consider whether
      manual extraction of figure data is worth the effort.


═══════════════════════════════════════════════════════════════════════════
 MODULE 4: SHARED-CONTROL & DEPENDENCY HANDLING
 Addresses multi-arm RCTs, repeated-cohort publications, and follow-up
 papers from the same trial
═══════════════════════════════════════════════════════════════════════════

4.1 SHARED CONTROL GROUPS (multi-arm RCTs)

PROBLEM: An RCT with arms {Exercise, Cognitive Training, Control}
yields two comparisons: Exercise-vs-Control and CogTraining-vs-Control.
If both are entered as independent evidence records, the control group's
variance is counted twice, inflating precision.

RULE SC-1: When a multi-arm trial contributes >1 evidence record for
the SAME edge family (same target node, same control condition), the
records share a control group and are NOT independent.

HANDLING OPTIONS (in order of preference):

  OPTION A (preferred): Split the shared control group.
    Allocate N_control evenly across comparisons.
    For k comparisons sharing one control:
      N_control_per_comparison = N_control / k
    Recompute SE using the reduced N_control.
    This is conservative (widens SE) but ensures independence.

  OPTION B: Multivariate meta-analysis.
    Model the covariance between comparisons sharing a control:
      Cov(d_1, d_2) = 1/N_control
    Requires multivariate pooling in EX-P4. More complex.
    Reserve for v2.0.

  OPTION C (for different edges): If the two comparisons map to
    DIFFERENT edges (e.g., exercise→cognition and cogtraining→cognition),
    they CAN be treated as independent because they don't pool together.
    The shared control creates correlation between edges but does NOT
    inflate precision within a single edge's pool.

DETECTION:
  At EX-P1, when AG02 (DesignAgent) detects multi-arm design:
    - Flag study_registry_v1: multi_arm = TRUE, n_arms = k
    - For each comparison extracted → edge_evidence_v1:
      shared_control_flag = TRUE
      shared_control_study_id = STUDY_XYZ
      comparison_arm_label = "exercise" / "cognitive_training"
    - At EX-P4 aggregation: detect shared_control_flag, apply SC-1.

4.2 COHORT LINEAGE (same dataset, multiple publications)

PROBLEM: A large trial publishes:
  Paper A (2020): 6-month results
  Paper B (2022): 24-month results (same cohort)
  Paper C (2023): secondary analysis of biomarkers (same cohort)

These are NOT independent studies. IVW pooling them triple-counts.

RULE CL-1: Papers from the same cohort/trial are assigned a
cohort_lineage_id. Only ONE paper per lineage contributes to IVW
pooling per edge. Selection hierarchy:

  1. Longest follow-up (most complete data)
  2. Largest sample (if follow-up equal)
  3. Most recent publication (if N and follow-up equal)
  4. Primary outcome paper over secondary analysis

RULE CL-2: Non-selected papers from the same lineage are NOT discarded.
They contribute:
  - Temporal trajectory data (different timepoints from same cohort)
  - Annotations (limitation, mechanism, etc.)
  - Completeness report data
  They are flagged: cohort_lineage_role = SUPPLEMENTARY

DETECTION:
  Automated signals for same lineage:
    - Same clinical trial registry number (e.g., NCT#)
    - Same first/senior author + same institution + overlapping N
    - Paper explicitly states "secondary analysis of [trial name]"
    - Shared funding grant number
  At EX-P0: check study_registry_v1 for potential lineage matches.
  Flag for human confirmation when automated match confidence < 0.90.

SCHEMA:
  study_registry_v1: +cohort_lineage_id TEXT (nullable, FK to self-group)
                     +lineage_role ENUM {PRIMARY, SUPPLEMENTARY, FOLLOW_UP}

4.3 CHANGE SCORES vs ENDPOINT SCORES

PROBLEM: For the same outcome, some studies report change from baseline
(Δ = post − pre) and others report endpoint scores. These have
different SDs and produce systematically different effect sizes.

RULE CS-1: Within each edge's evidence pool, track which scale is used:
  endpoint_vs_change ENUM {ENDPOINT, CHANGE, UNCLEAR}

RULE CS-2: Do not pool endpoint and change-score effect sizes directly.
  - If ≥2/3 of records are ENDPOINT: convert CHANGE to ENDPOINT
    using d_endpoint = d_change × √(1 / (2(1-ρ)))
    where ρ = pre-post correlation (borrow from sd_anchors_v1 if needed)
  - If ≥2/3 are CHANGE: convert ENDPOINT to CHANGE
  - If mixed: pool separately and take the larger-k pool.
  - If ρ is unknown: default ρ = 0.5, inflate SE × 1.20

RULE CS-3: For longitudinal studies with multiple timepoints, use
CHANGE scores consistently (effect at each timepoint relative to
baseline). This ensures temporal kernel fitting works correctly.


═══════════════════════════════════════════════════════════════════════════
 MODULE 5: FRESHNESS DECAY BY PARAMETER FAMILY
 Amends EX-P3-L7 (currently universal 1.5%/year)
═══════════════════════════════════════════════════════════════════════════

The current formula w_fresh = max(0.70, 1 − 0.015 × (2025 − pub_year))
applies identically to all evidence types. This is inappropriate because
different parameter types become obsolete at different rates.

5.1 FAMILY-SPECIFIC FRESHNESS POLICIES

┌──────────────────────┬───────────┬────────────┬─────────────────────────────────────┐
│ Parameter Family      │ Decay/yr  │ Floor      │ Rationale                            │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Instrument α, bₖ     │ 0.0%      │ 1.00       │ Psychometric properties don't expire │
│ (psychometrics)      │           │            │ unless superseded by newer validation │
│                      │           │            │ IN THE SAME POPULATION. Apply decay   │
│                      │           │            │ ONLY if a newer cancer-pop validation │
│                      │           │            │ exists (supersession, not age).       │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Population norms     │ 0.5%      │ 0.90       │ Norms shift slowly with diagnostic   │
│ (normative data)     │           │            │ criteria and population health. Very  │
│                      │           │            │ slow decay; 20-year-old norms still   │
│                      │           │            │ ~90% relevant.                        │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Biological           │ 0.5%      │ 0.90       │ Molecular mechanisms don't change,    │
│ correlations         │           │            │ but measurement technology improves.  │
│                      │           │            │ Very slow decay.                      │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Edge evidence        │ 1.5%      │ 0.70       │ Standard of care evolves. Treatment  │
│ (intervention →      │           │            │ regimens change. Measurement methods │
│  outcome effects)    │           │            │ improve. Moderate decay.              │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Edge evidence        │ 1.0%      │ 0.80       │ Biological relationships are more    │
│ (mechanism →         │           │            │ stable than intervention effects.    │
│  mechanism effects)  │           │            │ Slower decay.                        │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Intervention         │ 2.0%      │ 0.70       │ Exercise science, pharmacology, and  │
│ kernels              │           │            │ rehabilitation practices evolve.     │
│ (temporal data)      │           │            │ Delivery methods change.             │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Context priors       │ 1.0%      │ 0.80       │ Baseline cognitive levels may shift  │
│                      │           │            │ with improved supportive care. Mod.  │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Meta-analysis        │ 1.5%      │ 0.70       │ MA pooled estimates are superseded   │
│ pooled estimates     │           │            │ when larger newer MAs are published. │
│                      │           │            │ Apply standard decay PLUS check for  │
│                      │           │            │ supersession by newer MA.            │
├──────────────────────┼───────────┼────────────┼─────────────────────────────────────┤
│ Recovery curves      │ 1.0%      │ 0.80       │ Recovery trajectories change with    │
│                      │           │            │ evolving treatment protocols. Mod.   │
└──────────────────────┴───────────┴────────────┴─────────────────────────────────────┘

5.2 SUPERSESSION RULE (for psychometrics and MAs)

For parameter families with 0% or low decay, age alone doesn't degrade
value. Instead, a record is downweighted when a NEWER record from a
more relevant population exists:

  IF newer_record.population_match > older_record.population_match
  AND newer_record.sample_size ≥ older_record.sample_size × 0.5
  AND newer_record.pub_year > older_record.pub_year:
    older_record.w_fresh *= 0.70  (supersession penalty)

This ensures that a 2010 PSQI validation (N=500, general population)
is downweighted when a 2022 PSQI validation (N=300, cancer population)
is available, WITHOUT discarding valid older evidence entirely.


═══════════════════════════════════════════════════════════════════════════
 MODULE 6: SYSTEMS AFFECTED — CROSS-REFERENCE MAP
 Which existing docs, prompts, and code modules need updates
═══════════════════════════════════════════════════════════════════════════

6.1 DOCUMENT AMENDMENTS

┌─────────────────────────────────────────┬──────────────────────────────┐
│ Document                                 │ Amendment Required            │
├─────────────────────────────────────────┼──────────────────────────────┤
│ SYS_EXTRACTION_COMPLETE.md               │                              │
│   EX-TB-CN (lines 650-680)              │ Replace prose conversions    │
│                                         │ with reference to Module 1   │
│                                         │ conversion validity matrix.  │
│   EX-P2-S2 CG1-CG4 (lines 718-722)    │ CG checks now enforce the   │
│                                         │ "Valid When" column from     │
│                                         │ Module 1 tables.             │
│   EX-P3-L7 (lines 1011-1028)           │ Replace universal 1.5%/yr   │
│                                         │ with Module 5 family-        │
│                                         │ specific policies.           │
│   EX-P4 (lines 1110-1175)              │ Add Module 2 escalation     │
│                                         │ rules after IVW pooling.     │
│                                         │ Add Module 4 shared-control │
│                                         │ and cohort lineage checks.   │
├─────────────────────────────────────────┼──────────────────────────────┤
│ HETEROGENEOUS_PAPER_TREATMENT_PROTOCOL   │                              │
│   Part 4 Stage 4 (precision cascade)    │ Reference Module 1 tables   │
│                                         │ instead of inline formulas.  │
│   Part 4 Mechanism 2 (SE cascade)       │ Reference Module 1.4 for    │
│                                         │ exact level definitions.     │
│   Part 4 Mechanism 3 (verification)     │ Add Module 2 escalation     │
│                                         │ rules as Mechanism 3b.       │
│   Part 5 (completeness tracking)        │ Add Module 3 missingness    │
│                                         │ codes to all component rows. │
├─────────────────────────────────────────┼──────────────────────────────┤
│ PAPER_TYPE_ROUTING_AND_ACQUISITION       │                              │
│   §2.9 (factorial RCTs)                 │ Add Module 4.1 shared-      │
│                                         │ control handling rules.       │
│   §3 (double-counting)                  │ Add Module 4.2 cohort       │
│                                         │ lineage rules to the         │
│                                         │ existing MA overlap system.  │
├─────────────────────────────────────────┼──────────────────────────────┤
│ AUTOMATED_RETRIEVAL_PLAN                 │                              │
│   Part 6 (gap re-evaluation)            │ Integrate Module 3.4        │
│                                         │ (check missingness codes     │
│                                         │ before generating queries).  │
├─────────────────────────────────────────┼──────────────────────────────┤
│ 05_TABLE_SCHEMAS.md                      │                              │
│   study_registry_v1                     │ +cohort_lineage_id TEXT     │
│                                         │ +lineage_role ENUM          │
│   edge_evidence_v1                      │ +shared_control_flag BOOL   │
│                                         │ +shared_control_study_id    │
│                                         │ +endpoint_vs_change ENUM    │
│                                         │ +se_derivation_level ENUM   │
│                                         │ +se_inflation_applied REAL  │
│                                         │ +conversion_formula TEXT    │
│                                         │ +conversion_bias_risk TEXT  │
│   extraction_completeness (new table)   │ +missingness_code ENUM     │
│                                         │ +missingness_detail TEXT    │
│                                         │ +corrective_action ENUM    │
└─────────────────────────────────────────┴──────────────────────────────┘

6.2 PROMPT SEQUENCE AMENDMENTS

┌─────────────────────┬──────────────────────────────────────────────────┐
│ Prompt               │ Amendment                                         │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 0.2 (DB schema)     │ Add schema columns: cohort_lineage_id,           │
│                     │ shared_control_flag, endpoint_vs_change,          │
│                     │ se_derivation_level, se_inflation_applied,        │
│                     │ conversion_formula, conversion_bias_risk          │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 2.1 (trust boundary)│ Reference Module 1 conversion validity matrix.   │
│                     │ TB-CN must implement the "Valid When" gates.      │
│                     │ Log conversion provenance fields.                 │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 2.2 (harmonization) │ EX-P2-S2 CG checks enforce Module 1 conditions. │
│                     │ EX-P2-S3 uses Module 1.4 SE cascade levels.      │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 3.1 (evidence       │ Add shared-control detection (Module 4.1).       │
│  grouper)           │ Add cohort lineage check (Module 4.2).           │
│                     │ Add change-vs-endpoint partitioning (Module 4.3).│
├─────────────────────┼──────────────────────────────────────────────────┤
│ 3.2 (IVW meta-      │ Add Module 2 escalation rules after pooling.    │
│  analyzer)          │ Use Module 5 family-specific freshness.          │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 3.10 (pipeline ext) │ Add missingness provenance codes (Module 3).     │
│                     │ Wire missingness into acquisition loop.          │
└─────────────────────┴──────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 MODULE 7: PUBLICATION METHODS DRAFT
 For the paper's methods section — evidence extraction and harmonization
═══════════════════════════════════════════════════════════════════════════

The following is draft text for the methods section of the publication,
covering evidence extraction, conversion, and quality control.

--- BEGIN METHODS TEXT ---

Evidence Extraction and Harmonization

Evidence for the CRCI causal inference engine was extracted from
published literature through an automated pipeline with human-in-the-loop
verification. The extraction system treats each paper as a composite
source, detecting multiple types of extractable information (edge-weight
evidence, instrument psychometrics, population norms, temporal
trajectories, dose-response relationships, biomarker correlations, and
subgroup modifiers) and deploying specialized extraction agents for each
detected component.

Papers were classified by study design using a 27-subtype taxonomy
(Supplementary Table S1) and assigned an extraction depth level (Deep,
Standard, Shallow, or Minimal) based on design characteristics. For
meta-analyses, up to six extraction products were generated per paper:
pooled effect estimates, heterogeneity parameters (I², τ², prediction
intervals), included-study reference lists for directed acquisition,
subgroup and moderator analyses, and — for network meta-analyses or
dose-response meta-analyses — pairwise comparison matrices or
dose-response curve data points, respectively.

Effect Size Conversion and Precision Derivation

Reported effect sizes were converted to a common scale using a
conversion validity matrix that specifies, for each source statistic
(regression coefficient, odds ratio, hazard ratio, correlation, F- or
t-statistic, partial eta-squared), the exact conditions under which
conversion is valid, the required auxiliary fields, the fallback when
fields are missing, and the associated bias risk level (Table 1). For
example, conversion from F-statistic to Cohen's d is restricted to
two-group designs (numerator df = 1); omnibus F-tests with df > 1 are
blocked. Hazard ratios are retained on the log-hazard scale and not
converted to odds ratios unless events are rare (< 10%) and follow-up is
short. Each conversion logs the formula applied, fields used, fields
missing, and any standard error inflation.

Standard errors were derived through a six-level precision cascade
(Table 2). When SE was not directly reported, it was derived from 95%
confidence intervals (algebraically exact, no inflation), p-values
(1.05× SE inflation for exact p; 1.10× for bounded p such as "p < 0.05"),
sample sizes (1.15–1.20× inflation), or borrowed standard deviations
from population-matched anchors (1.15–1.50× inflation depending on anchor
similarity). Records where no quantitative precision could be derived
(direction-only evidence) were retained for qualitative sign-checking
but excluded from inverse-variance-weighted pooling.

Ratio measures (odds ratios, hazard ratios, risk ratios) were pooled on
the natural log scale. When studies within the same edge reported
a mix of standardized mean differences and odds ratios, the edge's
designated scale target in the evidence registry determined the conversion
direction.

Double-Counting Prevention

Three mechanisms prevented evidence double-counting. First, for
meta-analyses whose constituent studies were also independently extracted,
an overlap ratio was computed: when fewer than 70% of included studies
were independently available, the meta-analytic pooled estimate was
retained and overlapping constituents were excluded; above 70% overlap,
constituent studies were retained and the meta-analytic estimate was
excluded. Second, a cohort lineage identifier tracked papers reporting
on the same trial or dataset across multiple publications; only the
primary paper (longest follow-up, largest sample) contributed to pooling,
with supplementary papers contributing temporal and annotation data.
Third, multi-arm trials sharing a control group had their control-arm
sample size split evenly across comparisons to prevent precision
inflation from shared-control dependence.

Harmonization and Calibration

Extracted evidence records passed through a seven-layer standard error
calibration pipeline. Layer 1 applied study-design multipliers (RCT:
1.0×; prospective cohort: 1.15×; cross-sectional: 1.40×). Layer 2
applied population scope weights based on cancer type, treatment phase,
treatment regimen, age, and sex match to the target population. Layer 3
incorporated between-study heterogeneity (τ² via DerSimonian-Laird).
Layer 4 applied cancer-population validation multipliers for
psychometric instruments. Layer 5 applied GRADE-based quality
multipliers. Layer 6 applied measurement recency weighting for
time-sensitive biomarkers (chronic trait measures were exempt). Layer 7
applied publication freshness weighting with family-specific decay rates:
no decay for stable psychometric properties, 0.5%/year for biological
correlations and normative data, 1.0–1.5%/year for intervention efficacy
evidence, and 2.0%/year for intervention temporal kernel data.

The calibrated standard error for each evidence record was computed as:

  SE_eff = √[(SE × m_design × m_GRADE × m_temporal)² + σ²_struct + τ²]
           / (max(w_scope, 0.3) × w_fresh)

subject to the constraint SE_eff ≥ SE_raw (uncertainty was never
deflated).

Verification and Quality Control

Verification intensity was stratified by parameter error impact.
Parameters entering the model without pooling protection (instrument
reliability coefficients, factor loadings, population norms) received
100% human verification. Parameters with partial pooling protection
(context priors, recovery curves, biomarker correlations) received 25–30%
spot-checking. Parameters with full inverse-variance-weighted pooling
protection (edge weights) received 10–15% sample verification.

This baseline was augmented by influence-aware escalation: any
individual evidence record contributing more than 50% of an edge's
pooled IVW weight, belonging to an edge with fewer than three
contributing studies, or capable of flipping the pooled estimate's sign
if removed, was automatically escalated to 100% verification regardless
of parameter type.

Strategic Intelligence Extraction

Beyond numeric parameter extraction, each paper was mined for
18 categories of strategic intelligence including author-identified
research gaps, named unmeasured confounders, mechanism hypotheses,
adherence and safety data, and temporal dynamics observations.
These annotations were stored in a typed annotation table and routed
to specific downstream consumers: unmeasured-confounder annotations
contributed to per-edge structural variance estimation; research-gap
annotations informed acquisition prioritization; mechanism hypotheses
accumulated toward data-driven DAG expansion proposals when convergent
evidence from three or more independent sources supported the same
unmapped pathway.

--- END METHODS TEXT ---


═══════════════════════════════════════════════════════════════════════════
END — CONVERSION VALIDITY MATRIX & MATHEMATICAL HARDENING ADDENDUM v1.0
═══════════════════════════════════════════════════════════════════════════
