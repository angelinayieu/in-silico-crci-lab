# CRCI System — Implementation Instructions

You are building the CRCI Bayesian Causal Model system: a scientifically
rigorous evidence-to-recommendation pipeline. Every formula must be exact.
Every gate must be enforced. Every module must connect to the next.

## Task Routing — Read This First

**What are you being asked to do?** Match the task below, then follow its bootstrap.

---

### → "Extract / add a paper"
1. Read **[EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md)** — full procedure (Steps 0–9)
2. Read **[EXTRACTION_LOG.md](EXTRACTION_LOG.md)** — what's already extracted, avoid duplication
3. Read **[registries/EDGE_REGISTRY.csv](registries/EDGE_REGISTRY.csv)** header + last 10 rows — know existing edges
4. Read **[registries/NODE_REGISTRY.csv](registries/NODE_REGISTRY.csv)** — valid node IDs
5. Read **[registries/INSTRUMENT_REGISTRY.csv](registries/INSTRUMENT_REGISTRY.csv)** — valid instrument IDs
6. List `data/manual_uploads/structured/` — see which papers already have folders
7. Check `data/manual_uploads/pdfs/` — see which PDFs + meta.json exist
8. If the paper is a **systematic review or meta-analysis**: also read `crci/retrieval/hop_discoverer.py` docstring (it auto-queues constituent studies)

**Minimum context for ANY paper extraction:** steps 1-5 above. Without them, you risk wrong IDs, duplicate edges, or inconsistent column names.

---

### → "Continue building / next slice"
1. Read **`PROGRESS.md`** — tracks exactly where you are
2. Read the **FILE_CONTEXT_MANIFEST** entry for the next file
3. Read the exact spec lines it references
4. Read upstream file(s) that produce your input types
5. Read `shared/config.py` for constants
6. Follow the Slice Implementation Protocol in PROGRESS.md

---

### → "General question about the system"
1. Read **[docs/00_navigation/QUICK_REFERENCE.md](docs/00_navigation/QUICK_REFERENCE.md)** — one-page cheat sheet
2. If deeper: **[docs/00_navigation/IMPLEMENTATION_GUIDE.md](docs/00_navigation/IMPLEMENTATION_GUIDE.md)** — full roadmap
3. If about formulas/algorithm: **[docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md](docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md)**

---

### → "Build order / prompt sequence"
1. **[docs/04_implementation/PROMPT_SEQUENCE.md](docs/04_implementation/PROMPT_SEQUENCE.md)** — 42 prompts in dependency order
2. **[docs/00_navigation/VISUAL_ROADMAP.md](docs/00_navigation/VISUAL_ROADMAP.md)** — flowcharts

## Repository Documentation

All docs are organized in `docs/` subfolders. Registries are in `registries/`.

### docs/00_navigation/ — Entry Points
```
IMPLEMENTATION_GUIDE.md              — ★ Your main roadmap (START HERE)
QUICK_REFERENCE.md                   — One-page cheat sheet
VISUAL_ROADMAP.md                    — Diagrams and flowcharts
INDEX.md                             — Full documentation catalog
QUICK_START.md                       — Fast startup guide
```

### docs/01_v2_master/ — Authoritative v2.0 Specs (govern over all older docs)
```
CRCI_Master_Spec_v2.0.md             — ★ AUTHORITATIVE behavioral spec (supersedes SYS_* docs)
CRCI_Engineering_Appendix_v2.0.md    — Module manifest, schemas, test specs
CRCI_Implementation_Playbook_v2.0.md — CLI scripts, API adapters, rate limits
CRCI_Checklists_Templates_v2.0.md    — Manual CSV templates + operational checklists
```

### docs/02_system_specs/ — System Specs (older, still referenced)
```
SYS_EXTRACTION_COMPLETE.md           — Extraction spec (2,764 lines)
SYS_EXTRACTION_ADDENDUM.md           — Full-spectrum extraction extensions
SYS_ALGORITHM_COMPLETE.md            — Algorithm spec (4,418 lines)
SYS_RUNTIME_COMPLETE.md              — Runtime spec (752 lines)
SYS_PRESENTATION_COMPLETE.md         — Presentation spec (541 lines)
IMPLEMENTATION_BLUEPRINT_v1.1.md     — Architecture, v1 scope, phases
```

### docs/03_database/ — Database Schemas
```
05_TABLE_SCHEMAS.md                  — Full column definitions for all 56 tables
06_FK_WIRING_MAP.md                  — Foreign key relationships
11_CONTROLLED_VOCABULARIES.md        — All enum values
```

### docs/04_implementation/ — Build Order & Quality
```
PROMPT_SEQUENCE.md                   — 42 ordered prompts (your build sequence)
FILE_CONTEXT_MANIFEST.md             — Per-file spec lines, formulas, tables, gates
CODE_QUALITY_ENFORCEMENT.md          — 12 rules + verification prompts
```

### docs/05_data_management/ — Data & Retrieval
```
PARAMETER_PROVENANCE_AND_CURATION.md — GREEN/YELLOW/RED classification
CONVERSION_VALIDITY_AND_HARDENING.md — Conversion matrix, verification
AUTOMATED_RETRIEVAL_PLAN.md          — Paper retrieval system (v2)
```

### docs/06_orchestration/ — Operations
```
CLAUDE_CODE_ORCHESTRATION.md         — Multi-session orchestration instructions
```

### registries/ — Class A Knowledge (Human-Authored, Fill First)
```
EDGE_REGISTRY.csv                    — All causal/associational edges (133 rows)
NODE_REGISTRY.csv                    — All DAG nodes
INSTRUMENT_REGISTRY.csv              — All assessment instruments
MEASURE_REGISTRY.csv                 — Measure definitions
PATHWAY_REGISTRY.csv                 — Biological pathways
```

### docs NOT YET CREATED (referenced in code — create when needed)
```
TABLE_FILL_ORDER.md                  — When each table gets populated
INTERFACE_SCHEMA_LOCK.md             — Field-level definitions for intermediate states
```

## How You Build This System

1. **Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** (15 minutes)
2. **Open [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)**
3. **Execute prompts ONE AT A TIME in order**
   - Never skip ahead
   - Never batch across phases
   - The sequence is dependency-ordered

## For Every Single File You Build, Follow This Cycle

### 1. READ (before writing any code)

a. Read the file's entry in `docs/04_implementation/FILE_CONTEXT_MANIFEST.md`
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
f. Read the 12 enforcement rules in `docs/04_implementation/CODE_QUALITY_ENFORCEMENT.md` Section 1
g. For any file that reads or writes database tables, consult
   `docs/03_database/TABLE_FILL_ORDER.md` to verify the table is populated (⚠ not yet created)
   at this stage and its dependencies exist
h. For any file that produces or consumes an intermediate state
   (TypedNumericValue, HarmonizedClaim, CalibratedRecord, etc.),
   consult `docs/04_implementation/INTERFACE_SCHEMA_LOCK.md` for exact field definitions. (⚠ not yet created)
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
`docs/04_implementation/CODE_QUALITY_ENFORCEMENT.md` Section 2:

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
