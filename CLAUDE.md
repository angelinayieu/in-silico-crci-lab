# CRCI System — Implementation Instructions

You are building the CRCI Bayesian Causal Model system: a scientifically
rigorous evidence-to-recommendation pipeline. Every formula must be exact.
Every gate must be enforced. Every module must connect to the next.

## Repository Documentation

All specifications and implementation guides are in `docs/`:

```
docs/
├── IMPLEMENTATION_BLUEPRINT_v1.1.md     — Architecture, phases, directory tree
├── FILE_CONTEXT_MANIFEST.md             — Per-file spec lines, formulas, tables, gates
├── PROMPT_SEQUENCE.md                   — 31 ordered prompts (your build sequence)
├── CODE_QUALITY_ENFORCEMENT.md          — 12 rules + verification prompts + red flags
├── TABLE_FILL_ORDER.md                  — When each table gets populated, by what, dependencies
├── INTERFACE_SCHEMA_LOCK.md             — Field-level definitions for ALL intermediate states
├── PARAMETER_PROVENANCE_AND_CURATION.md — GREEN/YELLOW/RED classification, curation protocol, G0 gate
├── SYS_EXTRACTION_COMPLETE.md           — Extraction spec (2,764 lines)
├── SYS_ALGORITHM_COMPLETE.md            — Algorithm spec (4,418 lines)
├── SYS_RUNTIME_COMPLETE.md              — Runtime spec (752 lines)
├── SYS_PRESENTATION_COMPLETE.md         — Presentation spec (541 lines)
├── 05_TABLE_SCHEMAS.md                  — Full column definitions for all 56 tables
├── 06_FK_WIRING_MAP.md                  — Foreign key relationships
└── 11_CONTROLLED_VOCABULARIES.md        — All enum values
```

## How You Build This System

Follow `docs/PROMPT_SEQUENCE.md` — it contains 31 prompts across 7 phases.
Execute them ONE AT A TIME in order. Never skip ahead. Never batch across
phases. The sequence is dependency-ordered: each prompt's output is the
next prompt's input.

## For Every Single File You Build, Follow This Cycle

### 1. READ (before writing any code)

a. Read the file's entry in `docs/FILE_CONTEXT_MANIFEST.md`
b. Read the EXACT spec lines the manifest references
   (e.g., "SYS_EX lines 1230-1320" → read only those 90 lines)
c. Read ALL existing code files that produce this file's inputs
   (the manifest lists upstream dependencies)
d. Read the manifest entries for this file's DOWNSTREAM consumers
   (the files that will read YOUR output — understand what they need)
e. Re-read these anchor files to maintain naming consistency:
   - `shared/config.py`
   - `shared/models/enums.py`
   - `shared/models/intermediate_states.py`
   (Skip this step during Phase 0 when these don't exist yet)
f. Read the 12 enforcement rules in `docs/CODE_QUALITY_ENFORCEMENT.md` Section 1
g. For any file that reads or writes database tables, consult
   `docs/TABLE_FILL_ORDER.md` to verify the table is populated
   at this stage and its dependencies exist
h. For any file that produces or consumes an intermediate state
   (TypedNumericValue, HarmonizedClaim, CalibratedRecord, etc.),
   consult `docs/INTERFACE_SCHEMA_LOCK.md` for exact field definitions.
   Your output types MUST match these schemas.

### 2. PLAN (think before coding)

Before writing any code, explicitly state:
- What this file receives (types + which file produces them)
- What this file outputs (types + which file consumes them)
- Which formulas it implements (by ID from spec)
- Which gates it enforces (by ID from spec)
- Which config constants it imports
- Any decisions that affect downstream files

### 3. IMPLEMENT

Write the code following ALL 12 enforcement rules:

- **No hardcoded formula parameters.** Every number from a formula must be
  imported from `shared/config.py`. If you write `0.25` instead of
  `config.SIGMA_SQ_STRUCTURAL_DEFAULT`, that is wrong.
- **No invented formulas.** Every computation has a formula ID comment:
  `# Formula P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)`
  If you cannot cite a formula ID, do not write the computation.
- **No stubs.** No `pass`, no `TODO`, no `# placeholder`. Every function
  fully implemented. If a dependency doesn't exist yet, raise
  `NotImplementedError("Requires [specific file] from Phase [N]")`.
- **Typed signatures only.** Use Pydantic models or dataclasses from
  `shared/models/`. No raw dicts for domain objects.
- **Gates must raise, not log.** `raise GateViolation("P3-G1", ...)` not
  `logger.warning(...)`.
- **Every default must be logged.** When using a fallback value, log the
  reason: which entity, which value, why.
- **Exact column names on DB operations.** No `SELECT *`. Specify columns.
- **Seeded randomness.** Every random function accepts a `seed` parameter.
- **File docstring header** on every file:
  ```python
  """
  Component: SYS_EXTRACTION.EX-P4.P4-MA
  Spec: SYS_EXTRACTION_COMPLETE.md lines 1230-1320
  Formulas: P4-1, P4-2, P4-3, P4-3b
  Reads: ResolvedEvidence (from double_counting.py)
  Writes: PooledEstimate (consumed by prior_selector.py)
  Gates: P4-G1
  """
  ```

### 4. VERIFY (mandatory — never skip)

After writing the file, perform ALL of these checks:

**a. Formula accuracy**
Re-read the spec lines. Compare every formula character by character
against your implementation. The spec equation and the code must match
exactly.

**b. Backward coherence (does this file work with existing code?)**
Read the upstream file that produces your input. Verify:
- Output type matches your input type
- Field names match exactly
- No data is silently dropped at the boundary

**c. Forward coherence (will downstream code work with this file?)**
Read the manifest entry for the NEXT file(s) that will consume your output.
Verify:
- Your output type has all fields the downstream file will need
- Your naming matches what downstream expects
- You're not making a structural decision that forces downstream to hack around it

If the downstream file already exists, read it and verify directly.
If it doesn't exist yet, verify against its manifest entry.

**d. Hardcode scan**
Search your output for float literals. If any is a formula parameter,
it must come from config.

**e. Gate enforcement**
For every gate the manifest lists, verify it raises on failure.

**f. Review tasks**
If the manifest says this file emits review_tasks rows (for AMBIGUOUS,
ATB rejection, P6 BLOCK), verify the code actually writes to the table.

**g. Import validity**
Every import references a module that exists or is documented as a future
dependency with NotImplementedError.

### 5. WRITE TESTS (for formula-dense files)

For files tagged as formula-dense in the manifest (layers.py,
meta_analyzer.py, bayesian_update.py, mc_sampler.py, composite_scorer.py):

Create `tests/test_[module].py` with:
- Hand-computable expected values (compute β̂_IVW for 3 studies by hand)
- Edge cases (k=0, k=1, missing data, boundary values)
- Gate violation tests (assert raises)
- Verify constants come from config (not hardcoded)

### 6. LOG VERIFICATION

Add a verification stamp as comments at the top of the file:
```python
# VERIFIED: formulas [IDs] match spec lines [X-Y]
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads [Type] from [file]
# VERIFIED: forward wiring — writes [Type] for [downstream file]
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates [IDs] raise on failure
```

## Phase Boundary Protocol

After completing ALL prompts in a phase (not after each prompt — after
each phase), run the corresponding verification from
`docs/CODE_QUALITY_ENFORCEMENT.md` Section 2:

- After Phase 0 → run V0 (schema + model consistency)
- After Phase 1 → run V1 (extraction wiring)
- After Phases 2-3 → run V2 (formula audit)
- After Phase 5 → run V5 (mathematical correctness) **← most critical**
- After Phase 6 → run V6 (runtime + presentation wiring)
- After Phase 7 → run V-FINAL (end-to-end trace)

After each verification passes, report what was checked and commit.

## Rules That Override Everything

1. **The spec is the source of truth.** If your intuition says the formula
   should be different, implement what the spec says. Flag your concern
   in a `# REVIEW:` comment, but implement the spec.

2. **Stop on ambiguity.** If a spec section can be interpreted two ways,
   do not guess. Report: "SPEC AMBIGUITY: [description]. Option A: [X].
   Option B: [Y]. Awaiting guidance."

3. **Stop on wiring mismatch.** If an upstream file produces a type that
   doesn't match what the manifest says you should receive, report the
   mismatch. Do not silently adapt.

4. **Never approximate.** If the spec says `SE = (upper - lower) / (2 × 1.96)`,
   write exactly that. Do not substitute `scipy.stats.norm.ppf(0.975)`.

5. **Read before writing. Always.**
