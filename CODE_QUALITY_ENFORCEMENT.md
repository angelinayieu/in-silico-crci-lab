═══════════════════════════════════════════════════════════════════════════
 CRCI — CODE QUALITY ENFORCEMENT & VERIFICATION PROTOCOL
 Purpose: Prevent hallucinated code, hardcoded values, disconnected
          modules, skipped gates, and approximated formulas.
 Usage: Append Section 1 to EVERY implementation prompt.
        Run Section 2 verification prompts between phases.
        Use Section 3 red-flag checklist on every file received.
═══════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════
 SECTION 1: ENFORCEMENT RULES
 Append these to every implementation prompt (after the Master Template)
═══════════════════════════════════════════════════════════════════════════

Paste the following block at the END of every prompt, after the spec
excerpt and the Master Prompt Template content:

--- START ENFORCEMENT BLOCK (paste this every time) ---

## MANDATORY CODE RULES — violations make the output unusable

RULE 1 — NO HARDCODED NUMERIC VALUES
  Every number that appears in a formula must be imported from
  shared/config.py. If you write 0.25 in the code body instead of
  config.SIGMA_SQ_STRUCTURAL_DEFAULT, that is a violation.
  Allowed exceptions: 0, 1, 2 (structural), array indices,
  and loop counters only.
  Self-check: grep your output for any float literal. If it's a
  formula parameter, it must come from config.

RULE 2 — NO INVENTED FORMULAS
  Every formula you implement must have a formula ID comment.
  Example:
    # Formula P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
    beta_ivw = np.sum(beta / se**2) / np.sum(1 / se**2)
  If you cannot cite a formula ID from the spec for a computation,
  do not write it. Ask instead: "The spec does not define how to
  compute X. Should I use [approach] or is there a spec section
  I'm missing?"

RULE 3 — NO STUBS, NO TODO, NO PASS
  Every function must be fully implemented. If you write:
    def apply_gate_p4_g3(result):
        pass  # TODO: implement
  that is a violation. If a function requires upstream code that
  doesn't exist yet, raise NotImplementedError("Requires [file]
  from Phase [N]") with the specific dependency.

RULE 4 — EXPLICIT IMPORTS FROM REAL MODULES
  Every import must reference a file that either:
  (a) already exists (built in a previous prompt), or
  (b) is being built in this same prompt
  Do not import from modules that don't exist yet. Instead, define
  the interface you need and note the dependency:
    # DEPENDENCY: requires shared/models/intermediate_states.py
    # Expected: GroupedEvidence dataclass with fields [...]
    from shared.models.intermediate_states import GroupedEvidence

RULE 5 — INPUT/OUTPUT TYPE CONTRACTS
  Every function must have typed signatures using the Pydantic models
  or dataclasses from shared/models/. Example:
    def compute_se_eff(
        record: CalibratedRecord,
        config: PipelineConfig,
    ) -> float:
  Do not use raw dicts or untyped parameters for domain objects.

RULE 6 — EVERY GATE MUST RAISE ON FAILURE
  Validation gates are not warnings. They are hard stops.
  Example:
    # Gate P3-G1: SE_eff must not be less than SE_raw
    if se_eff < record.se_raw:
        raise GateViolation("P3-G1", f"SE_eff {se_eff} < SE_raw {record.se_raw}")
  Do not log and continue. Do not silently clamp. RAISE.

RULE 7 — EVERY DEFAULT/FALLBACK MUST BE LOGGED
  When using a default value (e.g., σ²_struct=0.25 because no
  annotations exist), log it with the specific reason:
    logger.info(f"Edge {edge_id}: σ²_struct defaulting to "
                f"{config.SIGMA_SQ_STRUCTURAL_DEFAULT} — "
                f"no annotations in study_annotations_v1")
  Silent defaults are the #1 source of untraceable bugs.

RULE 8 — DATABASE READS MUST SPECIFY EXACT COLUMNS
  Do not SELECT *. Specify exactly which columns you read:
    query = select(EdgeEvidence.beta, EdgeEvidence.se,
                   EdgeEvidence.study_design, EdgeEvidence.year)
  This catches schema mismatches immediately.

RULE 9 — DATABASE WRITES MUST MATCH SCHEMA EXACTLY
  Before writing, assert that your output has all required columns
  and correct types. Example:
    assert hasattr(row, 'sigma_sq_structural'), "Missing σ²_struct"
    assert 0 <= row.sigma_sq_structural <= config.SIGMA_SQ_CEILING

RULE 10 — RANDOM SEEDS MUST BE PARAMETERIZED
  Any function involving randomness must accept a seed parameter:
    def mc_simulate(state, n_draws=10000, seed=42):
        rng = np.random.default_rng(seed)
  Never use global random state. Never use unseeded randomness.

RULE 11 — EVERY FILE MUST HAVE A DOCSTRING HEADER
  Format:
    """
    Component: SYS_EXTRACTION.EX-P4.P4-MA
    File: extraction/p4_aggregation/meta_analyzer.py
    Spec: SYS_EXTRACTION_COMPLETE.md lines 1230-1320
    Formulas: P4-1, P4-2, P4-3, P4-3b
    Reads: edge_evidence_v1, study_annotations_v1
    Writes: PooledEstimate (in-memory) → edge_writer.py
    Gates: P4-G1 (all 118 edges have method)
    """

RULE 12 — NO APPROXIMATIONS UNLESS SPEC SAYS SO
  If the spec says SE = (upper - lower) / (2 × 1.96), implement:
    se = (ci_upper - ci_lower) / (2 * 1.96)
  Do not "improve" it with 2*scipy.stats.norm.ppf(0.975) unless
  the spec explicitly allows it. The spec IS the source of truth.

--- END ENFORCEMENT BLOCK ---


═══════════════════════════════════════════════════════════════════════════
 SECTION 2: VERIFICATION PROMPTS
 Run these BETWEEN phases to catch problems before they compound
═══════════════════════════════════════════════════════════════════════════

After each phase, before starting the next, give the LLM one of these
verification prompts. This catches disconnections early.

VERIFICATION PROMPT V0 — After Phase 0 (Database + Shared)
──────────────────────────────────────────────────────────
Context: All Phase 0 output files + E + F + G + H

Prompt:
  Review the following files for internal consistency:
  [paste all SQL schemas, enums.py, config.py, intermediate_states.py,
   output_contracts.py, tables.py]

  Check and report:
  1. Do all tables in the SQL match the ORM models in tables.py?
  2. Do all enum values in enums.py match the CHECK constraints in SQL?
  3. Do all constants in config.py have a comment citing their formula ID?
  4. Do all FK constraints in 006_fk_constraints.sql reference tables
     that exist in 001-005?
  5. Do all intermediate state dataclasses have typed fields that match
     the spec's intermediate state tables?
  6. Are there any hardcoded numbers in config.py without formula
     references?
  7. List any field name mismatches between SQL and ORM.

  Fix any issues found. Output a VERIFICATION REPORT listing what
  was checked and what was fixed.


VERIFICATION PROMPT V1 — After Phase 1 (Extraction Skeleton)
────────────────────────────────────────────────────────────
Context: All Phase 0+1 files + E + F + A

Prompt:
  Review the extraction pipeline for wiring integrity:
  [paste pipeline.py, all p0 files, base_agent.py, ag01, ag02, ag05,
   reconciliation.py, annotation_trust_boundary.py, llm/client.py]

  Check and report:
  1. Does pipeline.py actually call each chain function (not stubs)?
  2. Does base_agent.py call llm/client.py with the correct interface?
  3. Do agent outputs match the types expected by reconciliation.py?
  4. Does reconciliation.py output match annotation_trust_boundary.py input?
  5. Does annotation_trust_boundary.py write to the exact columns in
     study_annotations_raw_v1 and study_annotations_v1?
  6. Are there any imports that reference files not yet created?
     (These should use NotImplementedError, not phantom imports)
  7. Does the extraction_runs row get created with ALL required columns
     from the B12 schema?
  8. Is the checkpoint/resume logic actually implemented (not stubbed)?
  9. Does the idempotency check query the right columns?
  10. Are prompt templates in llm/prompts/ internally consistent with
      the response schemas in llm/response_schemas.py?

  Fix any issues. Output VERIFICATION REPORT.


VERIFICATION PROMPT V2 — After Phases 2-3 (Trust Boundary through Compilation)
──────────────────────────────────────────────────────────────────────────────
Context: All extraction files + E + F + A

Prompt:
  Review the full extraction pipeline from TB through P6:
  [paste all Phase 2-3 files]

  FORMULA AUDIT — for each formula in the code, verify:
  1. The formula ID comment matches the actual implementation
  2. The implementation matches the spec EXACTLY (not approximately)
  3. All parameters come from config.py (no hardcoded floats)

  Specific checks:
  4. P3-8 (SE_eff): Does the implementation match
     √[(SE·m_claim·m_GRADE·m_temporal)²+σ²_struct+τ²·𝟙]/(w_scope·w_fresh)?
     Check: is σ²_struct read from edges_v1 or hardcoded?
  5. P4-1/P4-2: Does IVW use the correct weights?
  6. DCR-1/DCR-2: Does the overlap computation use set intersection?
  7. P4-3b: Is the logit adjustment capped at ±1.0?
  8. Gate P3-G1: Is it enforced (raises), not just logged?
  9. Gate P4-G1: Does it check ALL 118 edges?
  10. Does double_counting.py emit review_tasks for AMBIGUOUS?
  11. Does edge_writer.py write ALL required columns to edges_v1?
  12. Does se_eff_assembly.py import multiplier tables from config?

  For every issue found, show the incorrect code and the fix.
  Output VERIFICATION REPORT.


VERIFICATION PROMPT V5 — After Phase 5 (Algorithm)
──────────────────────────────────────────────────
Context: All algorithm files + E + F + B

Prompt:
  Review the algorithm pipeline for mathematical correctness:
  [paste all Phase 5 files]

  CRITICAL CHECKS:
  1. spectral_validator.py: Does it compute ρ(B) using numpy.linalg
     eigenvalues? Does it ABORT if ρ(B) ≥ 1?
  2. bayesian_update.py (THE MOST IMPORTANT FILE):
     a. Is the information-form update correct?
        Λ_post += (b²_k/σ²_{y,k}) · eᵢeᵢᵀ
        η_post += (b_k(y_k−a_k)/σ²_{y,k}) · eᵢ
     b. Is posterior recovery via Cholesky? (not generic inverse)
     c. Are updates commutative? (order shouldn't matter)
     d. Is the 90-day temporal exclusion enforced?
  3. mc_sampler.py:
     a. Does it accept a random seed parameter?
     b. Are edge inclusions sampled as Bernoulli(P_incl)?
     c. Is (I-B)⁻¹ computed correctly for each draw?
     d. Are there 10,000 draws (from config, not hardcoded)?
  4. modifier_application.py:
     a. Are individual modifiers clamped to [0.7, 1.5]?
     b. Is cumulative product clamped to [0.5, 2.0]?
     c. Are clipping events logged?
  5. composite_scorer.py: Are severity weights from outcome_anchors_v1
     (not hardcoded)?
  6. Does frozen_state.py assign a frozen_model_version_id?

  WIRING CHECK:
  7. Does chain_c read from FrozenModelState (from chain_b)?
  8. Does chain_d read from state_snapshots_v1 (from chain_c)?
  9. Does chain_f read from intervention_rankings_v1 (from chain_d)?
  10. Are all DB reads using the correct table and column names?

  For every issue, show the problem and the fix.
  Output VERIFICATION REPORT.


VERIFICATION PROMPT V6 — After Phase 6 (Runtime + Presentation)
──────────────────────────────────────────────────────────────
Context: All runtime + presentation files + E + F + C + D

Prompt:
  Review runtime and presentation wiring:
  [paste all Phase 6 files]

  1. Does session.py pin frozen_model_version_id at start?
  2. Does session.py call ALG chains C→D→E→F in correct order?
  3. Does report_assembler.py read ALL Class E output tables?
  4. Does each presentation file read from the correct table
     and correct columns per the manifest?
  5. Are there any presentation files that hardcode sample data
     instead of reading from the database?
  6. Does adaptive_questions.py implement IG using the Gaussian
     conditioning formula from the spec (not an approximation)?

  Output VERIFICATION REPORT.


VERIFICATION PROMPT V-FINAL — End-to-End Wiring Audit
─────────────────────────────────────────────────────
Context: ALL code files + E + F

Prompt:
  Perform a complete end-to-end wiring audit of the CRCI system.

  TRACE 1: Follow a paper from PDF to recommendation.
  For each step, verify the actual code connects:
    pdf_ingestion.py output → relevance_screening.py input
    → paper_type_classifier.py → mode_selection.py
    → canonical_reader.py → base_agent.py → ag05_stats_label.py
    → numeric_parser.py → consistency_checker.py
    → [p2 files] → layers.py → se_eff_assembly.py
    → evidence_grouper.py → double_counting.py → meta_analyzer.py
    → prior_selector.py → edge_writer.py
    → graph_object.py → evidence_compiler.py → frozen_state.py
    → prior_loader.py → observation_mapper.py → bayesian_update.py
    → modifier_application.py → mc_sampler.py → ranker.py
    → composite_scorer.py → report_assembler.py → [presentation]

  For EACH arrow (→), verify:
  a. The output type of the left file matches the input type of the right
  b. The column names / field names match
  c. No data is silently dropped between steps

  TRACE 2: Follow σ²_structural from annotation to wider CrI.
  Verify: AG10 → reconciliation → ATB → study_annotations_v1 →
  meta_analyzer.py (reads annotation) → edges_v1.sigma_sq_structural →
  evidence_compiler.py (reads it) → mc_sampler.py (uses it in SE) →
  wider CrI in output.

  Report every disconnection found. For each, show the exact mismatch
  and the fix.


═══════════════════════════════════════════════════════════════════════════
 SECTION 3: RED-FLAG CHECKLIST
 Run this mentally on EVERY file you receive from the LLM
═══════════════════════════════════════════════════════════════════════════

After every prompt response, before accepting the code, scan for these:

□ HARDCODED NUMBERS
  Ctrl+F for float literals: 0.25, 0.50, 0.015, 0.05, 1.96, 0.3, 6.0
  If any appear in function bodies (not tests), they should be
  config.SOMETHING. Flag if not.

□ STUBS AND TODOS
  Ctrl+F for: pass, TODO, FIXME, NotImplemented, "placeholder",
  "simplified", "for now"
  Every one of these is a potential silent failure.

□ SELECT *
  Ctrl+F for: SELECT *, .all(), query(Table)
  Every DB read should specify columns.

□ PHANTOM IMPORTS
  Check every import line. Does that module exist?
  If it's from a future phase, is it documented as a dependency?

□ MISSING GATES
  For formula-dense files, cross-reference against the manifest.
  Does the manifest say "Gates: P3-G1, P4-G1, P4-G3"?
  Ctrl+F for each gate name. Is it actually enforced?

□ MISSING LOGGING
  Every default/fallback path should have a log line.
  Every gate check should log on pass AND raise on fail.
  Every DB write should log what was written.

□ WRONG FORMULA
  For the key formulas (P3-8, P4-1, P4-2, P4-3, DCR-1, DCR-2,
  Kalman update, SAFE computation), manually compare the code
  against the spec equation character by character.
  This is the most important check. A wrong formula passes all
  other tests but produces wrong science.

□ MISSING REVIEW_TASKS EMIT
  For DCR AMBIGUOUS, ATB rejections, P6 BLOCK:
  does the code actually write to review_tasks table?

□ UNSEEDED RANDOMNESS
  Ctrl+F for: random, np.random, Random
  Is every random call using a seeded RNG?

□ TYPE MISMATCHES
  Do function signatures use shared/models/ types?
  Or do they use raw dicts, tuples, Any?


═══════════════════════════════════════════════════════════════════════════
 SECTION 4: RECOVERY PROMPTS
 Use when you catch problems
═══════════════════════════════════════════════════════════════════════════

RECOVERY PROMPT R1 — Fix Hardcoded Values
─────────────────────────────────────────
  The following file has hardcoded numeric values that should come
  from shared/config.py:
  [paste file]

  Replace every hardcoded formula parameter with the corresponding
  config constant. Add the config import. For each replacement, add
  a comment with the formula ID. List all replacements made.


RECOVERY PROMPT R2 — Fix Disconnected Wiring
────────────────────────────────────────────
  The output of [file_A.py] produces [TypeX] but [file_B.py] expects
  [TypeY] as input. Here are both files:
  [paste both files]
  [paste the shared/models/ type definitions]

  Fix the mismatch. Do not change the shared model definitions.
  Adjust whichever file is wrong to match the contract.


RECOVERY PROMPT R3 — Implement Stubbed Function
───────────────────────────────────────────────
  The following function is stubbed with pass/TODO:
  [paste function]

  Here is the spec section that defines what this function should do:
  [paste spec lines from manifest]

  Implement it fully. Follow all enforcement rules. No stubs.


RECOVERY PROMPT R4 — Fix Wrong Formula
──────────────────────────────────────
  The following formula implementation does not match the spec:

  SPEC says (formula [ID]):
  [paste exact formula from spec]

  CODE has:
  [paste the incorrect implementation]

  Fix the code to match the spec exactly. Show the diff.


═══════════════════════════════════════════════════════════════════════════
 SECTION 5: HOW THIS ALL FITS TOGETHER
═══════════════════════════════════════════════════════════════════════════

Your workflow per prompt is now:

  1. Open PROMPT_SEQUENCE.md → find next prompt
  2. Assemble context (manifest + spec lines + blueprint)
  3. Append the ENFORCEMENT BLOCK from Section 1
  4. Send to LLM → receive code
  5. Run RED-FLAG CHECKLIST (Section 3) on received code
  6. If issues found → use RECOVERY PROMPTS (Section 4)
  7. Accept code when checklist passes
  8. After completing a phase → run VERIFICATION PROMPT (Section 2)
  9. Fix any issues found in verification
  10. Proceed to next phase

This adds ~5-10 minutes per prompt for quality checking.
It saves days of debugging disconnected/wrong code later.

The verification prompts (V0, V1, V2, V5, V6, V-FINAL) are the most
important. They catch wiring failures that individual file reviews miss.
Do not skip them.

═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
