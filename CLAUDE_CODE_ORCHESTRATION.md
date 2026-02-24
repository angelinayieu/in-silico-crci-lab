═══════════════════════════════════════════════════════════════════════════
 CRCI — CLAUDE CODE MASTER ORCHESTRATION PROMPT
 Purpose: Drop this into Claude Code. It reads your repo, follows the
          prompt sequence one-at-a-time, verifies after each, and stops
          if quality degrades.
═══════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════
 PART 1: THE META-PROMPT (give this to Claude Code)
═══════════════════════════════════════════════════════════════════════════

--- START META-PROMPT ---

You are building the CRCI Bayesian Causal Model system. This is a
scientifically rigorous evidence-to-recommendation pipeline. Every formula
must be exact. Every gate must be enforced. Every module must connect.

## YOUR REPO STRUCTURE

The repository contains these documentation files that govern everything:

  docs/IMPLEMENTATION_BLUEPRINT_v1.1.md   — Architecture, phases, v1/v2 split
  docs/FILE_CONTEXT_MANIFEST.md           — Per-file spec line ranges + dependencies
  docs/PROMPT_SEQUENCE.md                 — 31 ordered implementation prompts
  docs/CODE_QUALITY_ENFORCEMENT.md        — 12 rules + verification protocol
  docs/SYS_EXTRACTION_COMPLETE.md         — Extraction spec (2,764 lines)
  docs/SYS_ALGORITHM_COMPLETE.md          — Algorithm spec (4,418 lines)
  docs/SYS_RUNTIME_COMPLETE.md            — Runtime spec (752 lines)
  docs/SYS_PRESENTATION_COMPLETE.md       — Presentation spec (541 lines)
  docs/05_TABLE_SCHEMAS.md                — Full column definitions
  docs/06_FK_WIRING_MAP.md                — FK relationships
  docs/11_CONTROLLED_VOCABULARIES.md      — Enum values

## YOUR WORKFLOW — FOLLOW THIS EXACTLY

For each prompt in PROMPT_SEQUENCE.md (Prompts 0.1 through 7.2):

### STEP 1: READ BEFORE WRITING
  a. Read the prompt entry in PROMPT_SEQUENCE.md
  b. Read the manifest entries in FILE_CONTEXT_MANIFEST.md for the
     files being built in this prompt
  c. Read the EXACT spec lines referenced by the manifest
     (e.g., "SYS_EX lines 1230-1320" → read those 90 lines)
  d. Read the enforcement rules in CODE_QUALITY_ENFORCEMENT.md Section 1
  e. If this is Phase 1+, read the EXISTING code files that are
     upstream dependencies for the current file

  DO NOT START WRITING until you have read all of the above.

### STEP 2: IMPLEMENT
  Write the code files specified in the prompt. Follow ALL 12 enforcement
  rules from CODE_QUALITY_ENFORCEMENT.md.

### STEP 3: SELF-VERIFY (mandatory — do not skip)
  After writing each file, immediately perform these checks:

  a. FORMULA CHECK: For every formula in the code, verify the formula ID
     comment matches the spec. Read the spec lines again and compare
     character by character.

  b. IMPORT CHECK: For every import statement, verify the imported module
     exists in the repo. If it doesn't exist yet, verify it's documented
     as a dependency with NotImplementedError.

  c. WIRING CHECK: Read the upstream file that produces this file's input.
     Verify the output type/fields match what you're consuming. Read the
     downstream file (if it exists) that consumes this file's output.
     Verify your output type/fields match what it expects.

  d. HARDCODE CHECK: Search your output for float literals. Every formula
     parameter must come from shared/config.py.

  e. GATE CHECK: For every gate the manifest lists for this file, verify
     it raises an exception on failure (not just logs).

  f. REVIEW_TASKS CHECK: If the manifest says this file should emit
     review_tasks rows (for AMBIGUOUS, ATB rejection, P6 BLOCK), verify
     the code actually writes to the review_tasks table.

### STEP 4: FIX AND LOG
  If self-verify found issues, fix them. Then write a brief verification
  note as a comment at the top of the file:

  # VERIFIED: formulas P4-1,P4-2,P4-3,P4-3b match spec lines 1230-1320
  # VERIFIED: imports — all modules exist or documented as future dependency
  # VERIFIED: wiring — reads ResolvedEvidence (from double_counting.py),
  #           writes PooledEstimate (consumed by prior_selector.py)
  # VERIFIED: no hardcoded formula parameters (all from config.py)
  # VERIFIED: gate P4-G1 raises GateViolation on failure

### STEP 5: PHASE BOUNDARY VERIFICATION
  At the end of each PHASE (not each prompt — each phase), run the
  corresponding verification prompt from CODE_QUALITY_ENFORCEMENT.md
  Section 2 (V0, V1, V2, V5, V6, or V-FINAL).

  Read ALL files produced in that phase plus their upstream dependencies.
  Check wiring, formulas, types, gates, imports.
  Fix any issues before proceeding to the next phase.

## CRITICAL RULES

1. ONE PROMPT AT A TIME. Do not batch. Do not skip ahead. The sequence
   exists because each prompt's output is the next prompt's dependency.

2. READ EXISTING CODE before writing new code. If you're building
   meta_analyzer.py, first read double_counting.py (upstream) and
   prior_selector.py's manifest entry (downstream). Your output
   must connect to both.

3. NEVER INVENT. If the spec doesn't define a computation, do not
   create one. Flag it: "SPEC GAP: [description]. Awaiting guidance."

4. NEVER APPROXIMATE. If the spec says formula X, implement formula X.
   Do not "improve" it. Do not use a library function that computes
   something "similar." The spec is the source of truth.

5. STOP AND REPORT if you encounter:
   - A spec ambiguity that could go two ways
   - A wiring mismatch between files from different prompts
   - A formula that seems wrong or self-contradictory
   - A situation where you need to make an architectural decision
   Do not guess. Report and wait.

6. WHEN IN DOUBT, RE-READ THE SPEC. The answer is almost always
   in the spec lines referenced by the manifest. If you find yourself
   inventing logic, you probably missed a sub-step.

--- END META-PROMPT ---


═══════════════════════════════════════════════════════════════════════════
 PART 2: REPO SETUP INSTRUCTIONS (for you, the human)
═══════════════════════════════════════════════════════════════════════════

Your GitHub repo should look like this BEFORE you start Claude Code:

crci/
├── docs/
│   ├── IMPLEMENTATION_BLUEPRINT_v1.1.md
│   ├── FILE_CONTEXT_MANIFEST.md
│   ├── PROMPT_SEQUENCE.md
│   ├── CODE_QUALITY_ENFORCEMENT.md
│   ├── SYS_EXTRACTION_COMPLETE.md
│   ├── SYS_ALGORITHM_COMPLETE.md
│   ├── SYS_RUNTIME_COMPLETE.md
│   ├── SYS_PRESENTATION_COMPLETE.md
│   ├── 05_TABLE_SCHEMAS.md
│   ├── 06_FK_WIRING_MAP.md
│   └── 11_CONTROLLED_VOCABULARIES.md
│
├── database/
│   ├── schema/         (empty — will be populated by Phase 0)
│   └── seeds/          (empty — you populate CSVs manually)
│
├── shared/
│   └── models/         (empty — will be populated by Phase 0)
│
├── llm/
│   └── prompts/        (empty — will be populated by Phase 1)
│
├── extraction/         (empty directory structure from Blueprint)
├── algorithm/          (empty)
├── runtime/            (empty)
├── presentation/       (empty)
├── tests/              (empty)
├── scripts/            (empty)
│
├── CLAUDE.md           (the meta-prompt from Part 1 above)
├── pyproject.toml      (dependencies: numpy, scipy, sqlalchemy,
│                        psycopg2, pydantic, anthropic, pdfplumber,
│                        matplotlib, pytest)
└── .env.example        (ANTHROPIC_API_KEY=, DATABASE_URL=)

CLAUDE.md is the file Claude Code reads for project instructions.
Put the meta-prompt from Part 1 into CLAUDE.md.


═══════════════════════════════════════════════════════════════════════════
 PART 3: HOW TO ACTUALLY RUN THIS
═══════════════════════════════════════════════════════════════════════════

OPTION A: SEMI-AUTOMATED (recommended — higher quality)
─────────────────────────────────────────────────────────
You trigger each phase manually. Claude Code does the prompts within
each phase, you review between phases.

  You say: "Read PROMPT_SEQUENCE.md. Execute Phase 0 (prompts 0.1
  through 0.8). After each prompt, perform the self-verify steps from
  the meta-prompt. After all Phase 0 prompts, run verification V0 from
  CODE_QUALITY_ENFORCEMENT.md. Report what you built and any issues."

  [Claude Code executes 8 prompts, self-verifies, runs V0]
  [You review the verification report]
  [You scan a few files using the red-flag checklist]

  You say: "Phase 0 looks good. Execute Phase 1 (prompts 1.1 through
  1.6). Same process — self-verify after each, run V1 at end."

  ...repeat for each phase...

Why this is better: You catch problems at phase boundaries before they
propagate. A bad enum definition in Phase 0 ruins everything downstream.
A wrong intermediate state type in Phase 0 means every agent in Phase 1
produces mismatched output. Catching it at V0 costs 10 minutes. Catching
it at V5 costs hours of rework.

OPTION B: FULLY AUTOMATED (faster, riskier)
────────────────────────────────────────────
You trigger the entire build and review at the end.

  You say: "Read PROMPT_SEQUENCE.md. Execute ALL prompts from 0.1
  through 7.2 in order. Follow the meta-prompt workflow for each.
  Run phase verification prompts between phases. At the end, run
  V-FINAL (end-to-end wiring audit). Report all verification results."

Why this is riskier: If Phase 0 has a subtle type mismatch, Claude Code
will build 60+ files on top of that mismatch, then discover it during
V-FINAL and need to rewrite half the codebase.

RECOMMENDATION: Use Option A for at least Phase 0 and Phase 5 (the
foundational and the mathematically critical phases). The other phases
can potentially be batched: Phase 1-3 together, Phase 6-7 together.


═══════════════════════════════════════════════════════════════════════════
 PART 4: BEST PRACTICES FROM REAL-WORLD LLM CODING
 (what actually works, based on experience and research)
═══════════════════════════════════════════════════════════════════════════

1. SHOW, DON'T JUST TELL
─────────────────────────
The #1 predictor of code quality is whether the LLM has seen a concrete
example of what "good" looks like for THIS codebase.

After Phase 0 produces config.py and enums.py, EVERY subsequent prompt
benefits from seeing those files. The LLM learns "oh, this project uses
config.SIGMA_SQ_STRUCTURAL_DEFAULT, not hardcoded 0.25."

This is why the meta-prompt says "read existing code before writing new
code." It's not just for wiring — it's for style consistency.

Practical tip: After Phase 0, write ONE file yourself (or heavily edit
one LLM-produced file) to be the gold standard. Maybe a simple one like
sd_standardization.py. Make it perfect: typed signatures, formula ID
comments, config imports, gate enforcement, docstring header. Then tell
Claude Code: "Use extraction/p2_harmonization/sd_standardization.py as
the reference implementation for code style and quality standards."


2. TESTS BEFORE OR ALONGSIDE IMPLEMENTATION
────────────────────────────────────────────
The second biggest quality lever: write the test first (or at the same
time), then implement until the test passes.

For formula-dense files, add this to each prompt:

  "Also write a test file tests/test_[filename].py that:
  1. Tests the formula with hand-computed expected values
  2. Tests edge cases (k=0, k=1, missing data)
  3. Tests that gates raise on violation
  4. Tests that config values are imported (not hardcoded)"

Example for meta_analyzer.py:
  test_meta_analyzer.py should include:
  - 3 studies with known β/SE → compute IVW by hand → assert match
  - k=0 → assert BLOCKED
  - k=1 → assert DIRECT passthrough (no pooling)
  - I²>75% + not stratifiable → assert SINGLE_BEST selected
  - DCR AMBIGUOUS → assert review_tasks row created

Hand-computed test values are the GOLD STANDARD for catching wrong
formulas. If you compute β̂_IVW by hand for 3 known studies and the
code produces a different number, the formula is wrong. Period.

For the most critical files (bayesian_update.py, mc_sampler.py,
se_eff_assembly.py, meta_analyzer.py), consider computing expected
values yourself and providing them in the prompt:

  "For the test: given β=[0.3, 0.5, 0.2], SE=[0.1, 0.15, 0.2],
  the correct IVW pooled estimate is β̂ = 0.339 (I computed this).
  Your implementation must produce this value ± 0.001."


3. SMALL FILES > LARGE FILES
─────────────────────────────
LLMs produce better code in files under 200 lines than over 400 lines.
The prompt sequence already splits the work into small files. If a file
is growing past 250 lines, that's a signal to split it.

Exception: layers.py (7 layers + SE_eff) may legitimately be 200-300
lines. That's fine — it's one coherent computation.


4. TYPE CONTRACTS ARE THE IMMUNE SYSTEM
────────────────────────────────────────
The single most effective thing against hallucinated wiring:
strong types at every boundary.

If meta_analyzer.py returns PooledEstimate(beta=float, se=float,
method=AggregationMethod, i_squared=float, k=int), then
prior_selector.py CANNOT silently receive the wrong shape.

This is why Prompt 0.7 (intermediate states + output contracts)
comes before any implementation. Build the type system first.
Everything that flows between files should be a named type.

If the LLM produces code where a function returns a raw dict
instead of a typed model — REJECT IT. Dicts are where bugs hide.


5. DEPENDENCY-ORDER MATTERS MORE THAN PHASE ORDER
──────────────────────────────────────────────────
The prompt sequence is ordered so that every file's dependencies exist
before it's built. This is critical. If the LLM builds meta_analyzer.py
before double_counting.py, it will GUESS what ResolvedEvidence looks
like instead of reading it from the actual code.

If you batch prompts within a phase (e.g., Phase 1), ensure the LLM
still builds them in the order listed. The order within each phase
is also dependency-sequenced.


6. ANCHOR FILES REDUCE DRIFT
─────────────────────────────
Over 31 prompts, the LLM's "style" and assumptions will drift.
File #25 may use different naming conventions than file #3.

Combat this with anchor files — files that the LLM reads before
every implementation prompt:
  - shared/config.py (all constants — naming conventions)
  - shared/models/enums.py (all vocabulary — enum names)
  - shared/models/intermediate_states.py (all types — field names)

These three files establish the "language" of the codebase. If the
LLM reads them before writing ag05_stats_label.py AND before writing
mc_sampler.py, both files will use the same field names and types.

Add to the meta-prompt: "Before implementing any file, re-read
shared/config.py, shared/models/enums.py, and
shared/models/intermediate_states.py to refresh naming conventions."


7. THE "READ BACK" TECHNIQUE
─────────────────────────────
After the LLM writes a file, ask it to read the file back and
explain what it does in plain English. Mismatches between "what I
meant to write" and "what I actually wrote" surface immediately.

For critical files (bayesian_update.py, mc_sampler.py), add:

  "After writing this file, read it back and explain the computation
  step by step. For each step, cite the spec sub-step (e.g., C3a)
  and the formula (e.g., Λ_post += ...). If your explanation doesn't
  match the spec, fix the code."


8. PROMPT ENRICHMENT THAT ACTUALLY HELPS
─────────────────────────────────────────
Research and real-world experience shows these prompt additions
measurably improve code quality:

a. "Think step-by-step before writing code."
   Forces the LLM to plan, not just generate. Especially important
   for formula-dense files.

b. "Show your work: before implementing formula X, write it out
   in a comment, then implement it, then verify they match."
   Catches transcription errors between understanding and code.

c. "List all imports at the top of the file before writing any
   functions. For each import, note whether the module exists."
   Prevents phantom imports.

d. "After writing the file, list every database table you read from
   and write to. Verify each column name against the SQL schema."
   Catches column name mismatches.

e. "If you're unsure about anything, add a REVIEW comment:
   # REVIEW: [question about spec interpretation]"
   Better than guessing silently.

These are already embedded in the enforcement rules and meta-prompt,
but being explicit about them in individual prompts makes them
more likely to be followed.


9. VERSION CONTROL AS CHECKPOINTS
──────────────────────────────────
After each phase verification passes:
  git add -A && git commit -m "Phase 0 complete — verified"

If Phase 1 goes badly, you can roll back to the verified Phase 0 state
and re-do Phase 1 with adjusted prompts. Without commits, a bad Phase 1
contaminates Phase 0 files (if the LLM "fixes" things that weren't broken).


10. CONTEXT WINDOW MANAGEMENT
──────────────────────────────
Claude Code has a large context window but it's not infinite. Over a long
session building 31 prompts, earlier context will fall off.

Mitigation strategies:
  a. Start a fresh Claude Code session for each phase (not each prompt —
     each phase). Phase 0 = one session. Phase 1 = new session. etc.
  b. At the start of each session, have Claude Code read the anchor files
     (config, enums, intermediate_states) plus any upstream code it needs.
  c. The manifest tells it exactly which spec lines to read — it doesn't
     need the entire 4,418-line ALG spec in context, just the 90 lines
     for the current chain card.

The manifest was specifically designed for context window efficiency.
"Read lines 1230-1320" uses 90 lines of context. "Read the whole spec"
uses 4,418 lines and dilutes attention on the relevant section.


═══════════════════════════════════════════════════════════════════════════
 PART 5: UPDATED PROMPT TEMPLATE (with enforcement baked in)
═══════════════════════════════════════════════════════════════════════════

Each prompt from PROMPT_SEQUENCE.md should be wrapped in this structure
when given to Claude Code. The meta-prompt handles this automatically,
but if you're doing it manually, use this template:

--- START PROMPT WRAPPER ---

## STEP A: READ CONTEXT (do this before writing any code)

1. Read docs/FILE_CONTEXT_MANIFEST.md entries for: [list files]
2. Read docs/[RELEVANT_SPEC].md lines [X-Y] as referenced by manifest
3. Read these existing code files (upstream dependencies):
   [list files that produce inputs for the current file]
4. Re-read shared/config.py, shared/models/enums.py,
   shared/models/intermediate_states.py (anchor files)
5. Read docs/CODE_QUALITY_ENFORCEMENT.md Section 1 (12 rules)

## STEP B: PLAN (think step-by-step)

Before writing code, outline:
- What this file receives as input (types + source)
- What this file produces as output (types + destination)
- Which formulas it implements (by ID)
- Which gates it enforces
- Which config constants it needs

## STEP C: IMPLEMENT

[Specific implementation instructions from PROMPT_SEQUENCE.md]

Follow ALL 12 enforcement rules. Key reminders:
- No hardcoded formula parameters (import from config.py)
- No stubs/TODO/pass (fully implement or raise NotImplementedError
  with specific dependency)
- Every formula has a formula ID comment
- Every gate raises on failure
- Every default/fallback is logged with reason
- Every function has typed signature using shared/models types
- Every file has docstring header with Component/Spec/Formulas/etc.

## STEP D: SELF-VERIFY (do this after writing, before moving on)

1. Re-read the spec lines. Compare every formula character by character.
2. Check every import — does the module exist?
3. Search for float literals — are any formula parameters hardcoded?
4. Check every gate — does it raise or just log?
5. Check DB operations — exact column names specified?
6. Verify output type matches what downstream expects

## STEP E: ALSO WRITE TESTS

Create tests/test_[module_name].py with:
- Hand-computable test case for each formula
- Edge case tests (k=0, missing data, boundary values)
- Gate violation tests (assert raises)
- Config import verification (no hardcoded values)

--- END PROMPT WRAPPER ---


═══════════════════════════════════════════════════════════════════════════
 PART 6: WHEN TO INTERVENE MANUALLY
═══════════════════════════════════════════════════════════════════════════

Even with all this automation, there are moments where you MUST review
personally. These are the highest-risk points:

1. AFTER PHASE 0 (foundation)
   Review config.py manually. Every constant here propagates everywhere.
   If SIGMA_SQ_STRUCTURAL_DEFAULT is wrong, every SE_eff in the system
   is wrong. 10 minutes of review saves days.

2. AFTER PROMPT 2.3 (SE_eff implementation)
   This is the most formula-dense extraction file. Open layers.py,
   find the P3-8 implementation, and compare it against the paper's
   equation visually. This formula has 7 multiplied/divided components.
   If one is in the wrong position, everything downstream shifts.

3. AFTER PROMPT 5.3 (Bayesian update)
   This is THE most important file. Open bayesian_update.py and verify:
   - Information-form update equations are correct
   - Cholesky is used for inversion
   - 90-day temporal exclusion is enforced
   If you can, run it with a trivial case (1 node, 1 observation, known
   prior) and verify the posterior matches hand calculation.

4. AFTER PROMPT 5.4 (MC sampler)
   Verify: random seed parameter exists, 10K draws from config (not
   hardcoded), (I-B)⁻¹ computation exists. Run with seed=42 twice
   and verify identical output.

5. AFTER V-FINAL (end-to-end audit)
   Read the wiring audit report carefully. Every disconnection found
   here is a bug that will silently produce wrong recommendations.


═══════════════════════════════════════════════════════════════════════════
 PART 7: SUMMARY — YOUR COMPLETE TOOLKIT
═══════════════════════════════════════════════════════════════════════════

DOCUMENTS IN REPO (docs/):
  1. IMPLEMENTATION_BLUEPRINT_v1.1.md    — what to build
  2. FILE_CONTEXT_MANIFEST.md            — where each file's truth lives
  3. PROMPT_SEQUENCE.md                  — 31 prompts in order
  4. CODE_QUALITY_ENFORCEMENT.md         — 12 rules + verification prompts
  5. 4 system specs                      — the deep truth
  6. 3 supporting docs                   — schemas, FKs, vocabs

ORCHESTRATION:
  7. CLAUDE.md (this file's Part 1)      — meta-prompt for Claude Code

PROCESS:
  Phase 0 → manual review → commit
  Phase 1-3 → semi-automated → V1,V2 verification → commit
  Phase 4 → you run extraction, debug as needed
  Phase 5 → manual review of critical files → V5 verification → commit
  Phase 6-7 → semi-automated → V6 verification → commit
  V-FINAL → full wiring audit → fix → final commit

═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
