# CRCI Pipeline Fix — Slice-by-Slice Implementation Plan

**Date**: 2026-02-26  
**Source**: PIPELINE_AUDIT.md root-cause analysis  
**Scope**: 9 implementation slices covering 8 root-cause issues  
**Estimated LOC**: ~1,260 new + ~200 modifications

---

## Table of Contents

1. [Current State](#current-state)
2. [Problem Layers](#problem-layers)
3. [**Slice 0: Pre-Implementation Invariants (MUST DO FIRST)**](#slice-0-pre-implementation-invariants)
4. [Slice 1: Edge Definition Unification (FIX-1)](#slice-1-edge-definition-unification-fix-1)
5. [Slice 2: DB Persistence Protection (FIX-2)](#slice-2-db-persistence-protection-fix-2)
6. [Slice 3: Expand the CSV Template (FIX-3)](#slice-3-expand-the-csv-template-fix-3)
7. [Slice 4: Fix Existing Paper Data (FIX-7 + FIX-8)](#slice-4-fix-existing-paper-data-fix-7--fix-8)
8. [Slice 5: Unified Evidence Writer with Validation (FIX-4)](#slice-5-unified-evidence-writer-with-validation-fix-4)
9. [Slice 6: Family Importers (FIX-5)](#slice-6-family-importers-fix-5)
10. [Slice 7: Completeness Checker (FIX-6)](#slice-7-completeness-checker-fix-6)
11. [Slice 8: Wire P3 Intermediate State Fields](#slice-8-wire-p3-intermediate-state-fields)
12. [Slice 9: Wire Remaining Broken Spots](#slice-9-wire-remaining-broken-spots)
13. [Execution Order](#execution-order)
14. [Verification Matrix](#verification-matrix)
15. [Definition of Done per Slice](#definition-of-done-per-slice)

---

## Current State

### DB Snapshot (live-verified)

| Data Family | DB Table | Rows | Status |
|---|---|---|---|
| Edge definitions | `edge_relations_definitions_v1` | 137 | ✅ `ER_*` format loaded |
| F1 — Edge evidence | `edge_evidence_v1` | 8 | ✅ Cohen's d, study_design, cancer_type, rob_overall, instrument_id populated |
| F3 — Population norms | `population_norms_v1` | 9 | ✅ Loaded |
| F3 — Context priors | `node_priors_v1` | 7 | ✅ Loaded |
| F4 — Temporal evidence | `temporal_evidence_v1` | 16 | ✅ Loaded |
| F2 — Instrument evidence | `instrument_evidence_v1` | 0 | ❌ MISSING — nobody writes |
| F5 — Dose evidence | `dose_evidence_v1` | 0 | N/A (no dose-response papers) |
| F6 — Subgroup evidence | `subgroup_evidence_v1` | 0 | N/A (no subgroup data reported) |
| F7 — Synergy | `intervention_synergy_v1` | 0 | N/A (no factorial papers) |

### Study Registry

| study_id | doi | study_design | study_subtype | included_study_ids_json |
|---|---|---|---|---|
| STUDY_CHERRIER_2013 | 10.1016/j.lfs.2013.08.011 | RCT | (null) | (null) |
| STUDY_CAMPBELL_2017 | 10.1002/pon.4370 | RCT | (null) | (null) |

### Evidence Column Coverage

All 8 evidence rows have: `study_design` ✅, `cancer_type` ✅, `rob_overall` ✅, `instrument_id` ✅, `meta_source_flag` ❌ (0/8).

### Edge Definition State

Seed file: 29 rows with `EDGE_*` IDs (stale).  
Registry: 138 rows with `ER_*` IDs (authoritative).  
DB: 137 `ER_*` rows loaded (matches registry minus header).

---

## Problem Layers

The 8 issues fall into **3 layers of depth**:

```
Layer 1: FOUNDATION  — Can the data even survive and be correct?
  ISSUE-1: Edge ID split (EDGE_* vs ER_*)
  ISSUE-2: DB gets wiped on restart

Layer 2: DATA QUALITY — Is what enters the DB complete and comparable?
  ISSUE-3: LLM extraction maps 11/96 columns
  ISSUE-4: Manual CSV template too narrow
  ISSUE-5: Mixed effect-size units (seconds vs Cohen's d)
  ISSUE-7: No completeness checking

Layer 3: DATA COVERAGE — Are all 7 parameter families populated?
  ISSUE-6: 5/7 families have no importer
  ISSUE-8: Three write paths with no shared validation
```

---

## Slice 0: Pre-Implementation Invariants

> **Do NOT start Slice 5 until all three invariants below are locked.**  
> These are the three rigor gaps that will force a rewrite if discovered later.
> Implementing Slice 5 without these is building on sand.

### Gap 1 — Canonical Controlled Vocabulary + Mapping Layer

**The problem**: Different parts of the system use different keys for the same concept.
If the validated writer persists `RCT` but P3 Layer 1 looks up `large_rct`, the
design multiplier falls through to `"unclassified"` → 3.0× SE inflation — exactly
the same bug we're trying to fix, just moved from "missing field" to "wrong key."

**Concrete mismatch** (verified in `crci/shared/config.py` lines 111-123):

| What Writer Would Accept | What P3 L1 Actually Keys On | P3 Multiplier |
|---|---|---|
| `RCT` | ❌ not a key | 3.0× (default) |
| `quasi_experimental` | ❌ not a key | 3.0× (default) |
| `cohort` | ❌ not a key | 3.0× (default) |
| — | `large_rct` ✅ | 1.0× |
| — | `small_rct_default` ✅ | 1.25× |
| — | `well_adjusted_cohort` ✅ | 1.5× |
| — | `cross_sectional_adjusted` ✅ | 2.5× |

**Required fix**: Define a single canonical mapping in `crci/shared/vocab.py` (new file, ~120 lines):

```python
"""Canonical controlled vocabularies + human-friendly → internal key mappings.

Every constrained field that crosses a system boundary (CSV → DB → P3/P4)
must have its mapping defined here. The validated_evidence_writer accepts
human-friendly inputs and persists canonical keys only.
"""

# ── study_design: human-friendly → P3 L1 internal key ──
STUDY_DESIGN_MAP: dict[str, str] = {
    # Human-friendly CSV inputs (left) → config.DESIGN_MULTIPLIERS keys (right)
    "RCT":                      "large_rct",    # reclassified by N in L1
    "rct":                      "large_rct",
    "randomized_controlled":    "large_rct",
    "quasi_experimental":       "well_adjusted_cohort",
    "cohort":                   "well_adjusted_cohort",
    "cohort_adjusted":          "well_adjusted_cohort",
    "longitudinal":             "unadjusted_longitudinal",
    "longitudinal_unadjusted":  "unadjusted_longitudinal",
    "cross_sectional":          "cross_sectional_unadjusted",
    "cross_sectional_adjusted": "cross_sectional_adjusted",
    "cross_sectional_unadjusted": "cross_sectional_unadjusted",
    "animal":                   "animal_in_vivo",
    "animal_in_vivo":           "animal_in_vivo",
    "in_vitro":                 "in_vitro_mechanistic",
    "mechanistic":              "in_vitro_mechanistic",
    "expert_opinion":           "expert_opinion",
    "narrative_review":         "expert_opinion",
    # Internal keys map to themselves (idempotent)
    "large_rct":                "large_rct",
    "small_rct_default":        "small_rct_default",
    "well_adjusted_cohort":     "well_adjusted_cohort",
    "unadjusted_longitudinal":  "unadjusted_longitudinal",
    "animal_in_vivo":           "animal_in_vivo",
    "in_vitro_mechanistic":     "in_vitro_mechanistic",
}

# ── rob_overall: human-friendly → config.GRADE_MULTIPLIERS key ──
ROB_TO_GRADE_MAP: dict[str, str] = {
    "low":      "HIGH",       # low risk-of-bias = HIGH quality
    "moderate": "MODERATE",
    "high":     "LOW",        # high risk-of-bias = LOW quality
    "critical": "VERY_LOW",
}

# ── cancer_validated: human-friendly → config.SCALE_MULTIPLIERS key ──
CANCER_VALIDATION_MAP: dict[str, str] = {
    "yes":     "validated_cancer",
    "true":    "validated_cancer",
    "no":      "general_population",
    "false":   "general_population",
    "unknown": "used_cancer",
    "partial": "used_cancer",
    # Internal keys map to themselves
    "validated_cancer":       "validated_cancer",
    "used_cancer":            "used_cancer",
    "general_population":     "general_population",
    "known_somatic_confound": "known_somatic_confound",
}

# ── effect_type_original: allowed values ──
EFFECT_TYPE_VOCAB: set[str] = {
    "cohen_d", "cohen_d_from_eta_sq", "log_or",
    "odds_ratio", "hazard_ratio", "r_correlation",
    "mean_diff", "partial_eta_sq", "hedges_g",
}

# ── effect_size_context: allowed values ──
EFFECT_SIZE_CONTEXT_VOCAB: set[str] = {
    "BETWEEN_GROUP", "WITHIN_GROUP", "PRE_POST_CHANGE",
}

# ── treatment_phase: allowed values ──
TREATMENT_PHASE_VOCAB: set[str] = {
    "active_treatment", "early_recovery", "late_recovery",
    "maintenance", "survivorship", "mixed", "not_specified",
}

# ── cancer_type: allowed values ──
CANCER_TYPE_VOCAB: set[str] = {
    "breast", "prostate", "colorectal", "lung", "hematologic",
    "head_neck", "gynecologic", "brain", "mixed", "any_solid",
    "not_specified",
}

def resolve_study_design(raw: str, n_total: int | None = None) -> str:
    """Map human-friendly study_design to P3 L1 internal key.

    If raw is 'RCT' and n_total <= 200, returns 'small_rct_default'
    so L1 can apply the interpolation formula.
    """
    canonical = STUDY_DESIGN_MAP.get(raw.strip())
    if canonical is None:
        raise ValueError(
            f"Unknown study_design '{raw}'. "
            f"Valid: {sorted(set(STUDY_DESIGN_MAP.values()))}"
        )
    # RCT reclassification by sample size
    if canonical == "large_rct" and n_total is not None and n_total <= 200:
        return "small_rct_default"
    return canonical
```

**Integration point**: The `validated_evidence_writer` (Slice 5) calls `resolve_study_design()` and the other mapping functions at write time. The DB stores the **canonical** key, not the human-friendly input. P3's `getattr(rec, "study_design")` returns a key that exists in `config.DESIGN_MULTIPLIERS` — guaranteed by the vocabulary layer.

### Gap 2 — Evidence Quarantine Path

**The problem**: "Reject, don't default" (Slice 5 rule #1) is correct, but the LLM
extraction path currently produces incomplete objects. Hard-rejecting without a
quarantine channel means: nothing writes, no debugging visibility, pipeline stalls.

**Required fix**: Add an `evidence_quarantine_v1` table (or reuse `extraction_audit_v1`):

```sql
CREATE TABLE IF NOT EXISTS evidence_quarantine_v1 (
    quarantine_id     TEXT PRIMARY KEY,
    study_id          TEXT NOT NULL,
    edge_relation_id  TEXT,
    source_path       TEXT NOT NULL,   -- 'llm' | 'manual_csv' | 'bulk_loader'
    raw_payload_json  TEXT NOT NULL,   -- the complete row as JSON
    validation_errors TEXT NOT NULL,   -- JSON array of error strings
    quarantine_reason TEXT NOT NULL,   -- 'missing_study_design' | 'unknown_edge_id' | ...
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at       TEXT,            -- NULL until manually fixed and re-submitted
    resolved_by       TEXT             -- 'manual_resubmit' | 'auto_retry'
);
```

**Writer behavior becomes**:
1. `validate_evidence_row(row)` → errors?
2. **YES** → `INSERT INTO evidence_quarantine_v1` + log warning + continue batch
3. **NO** → `write_validated_row()` → `INSERT INTO edge_evidence_v1`

This keeps strictness (bad rows never enter `edge_evidence_v1`) while preserving
observability (you can query quarantine to see what failed and why).

**Quarantine CLI**: Add `scripts/review_quarantine.py` that shows
pending quarantine rows, lets you fix and re-submit them.

### Gap 3 — Evidence Row Dedup Identity

**The problem**: The original plan uses `study_id + edge_id + span_hash` for dedup.
Real papers often contribute **multiple valid rows per edge**:
- Multiple outcomes (e.g., verbal memory + processing speed both map to same edge)
- Multiple timepoints (4-week, 12-week, 24-week)
- Multiple instruments (HVLT-R, COWAT both measure cognitive function)
- Multiple comparisons (usual care vs active control)
- Multiple arms (shared control)

Aggressive dedup on just `study_id + edge_id` will **overwrite valid distinct rows**.

**Required fix**: Define the unique identity of an evidence row as a deterministic
hash over **all** distinguishing dimensions:

```python
def compute_evidence_identity(row: dict) -> str:
    """Deterministic identity hash for an evidence row.

    Two rows with the same identity are considered the same observation.
    Two rows with different identities are distinct observations even
    if they share study_id and edge_id.
    """
    import hashlib
    identity_fields = [
        str(row.get("study_id", "")),
        str(row.get("edge_relation_id", "")),
        str(row.get("instrument_id", "")),           # different instruments = different rows
        str(row.get("timepoint_weeks", "")),          # different timepoints = different rows
        str(row.get("comparison_arm_label", "")),     # different comparators = different rows
        str(row.get("effect_size_context", "")),      # between vs within = different rows
        str(row.get("endpoint_vs_change", "")),       # endpoint vs change score = different rows
        str(row.get("outcome_node_id", "")),          # different outcome domains = different rows
    ]
    identity_str = "|".join(identity_fields)
    return "ler_" + hashlib.sha256(identity_str.encode()).hexdigest()[:16]
```

**DB enforcement**: Add a `UNIQUE` constraint on `ler_id` in `edge_evidence_v1`
(should already exist as PK). The writer uses `INSERT OR REPLACE` keyed on this hash.

**Critical rule**: If a re-import changes any non-identity field (e.g., updated SE),
the row is **updated in place** (same `ler_id`). If a re-import adds a new timepoint,
it gets a **new** `ler_id` (different `timepoint_weeks` → different hash).

### Invariant Verification

Before proceeding to any code slice, confirm these three tests pass:

| Invariant | Test | Expected |
|---|---|---|
| Vocab mapping | `resolve_study_design("RCT", n_total=19)` | `"small_rct_default"` |
| Vocab mapping | `resolve_study_design("RCT", n_total=500)` | `"large_rct"` |
| Vocab mapping | `resolve_study_design("cohort")` | `"well_adjusted_cohort"` |
| Vocab mapping | `resolve_study_design("bogus_design")` | `ValueError` raised |
| Quarantine | Insert row with `study_design=None` | Row in `evidence_quarantine_v1`, NOT in `edge_evidence_v1` |
| Dedup identity | Same study+edge, different instruments | Two distinct `ler_id` values |
| Dedup identity | Same study+edge+instrument, re-import | Same `ler_id`, row updated in place |

---

## Slice 1: Edge Definition Unification (FIX-1)

### What's Broken

Two files define edges with **incompatible ID formats and column names**:

| File | IDs | Columns | Count |
|---|---|---|---|
| `crci/database/seeds/edge_relations.csv` | `EDGE_IL6_COGNITION` | `node_x`, `node_y`, `default_effect_direction` | 29 rows |
| `registries/EDGE_REGISTRY.csv` | `ER_ACTIVITY_PROC_SPEED` | `source_node_id`, `target_node_id`, `expected_sign` | 138 rows |

**Current state**: The DB already has 137 `ER_*` definitions loaded (via `scripts/load_evidence_into_db.py`), so this is *partially* resolved. But the seed file still has 29 `EDGE_*` rows. If anyone runs `setup_database.py --seed` or the DB is recreated, it reverts to 29 `EDGE_*` stubs and all 8 evidence rows become FK orphans.

### Wiring Diagram

```
registries/EDGE_REGISTRY.csv  (138 ER_* rows — SOURCE OF TRUTH)
        │
        ▼
scripts/sync_edge_seeds.py    (NEW — column mapper)
        │
        ▼
crci/database/seeds/edge_relations.csv  (overwritten with ER_* format)
        │
        ▼
crci/database/seed_loader.py → load_all_seeds()
        │
        ▼
edge_relations_definitions_v1  (DB table — 138 ER_* rows)
        │
        ├──► edge_evidence_v1.edge_relation_id  (FK join)
        ├──► edges_v1.edge_relation_id           (FK join)
        └──► all algorithm chains                (read edge defs)
```

### Implementation Steps

**Step 1a** — Create `scripts/sync_edge_seeds.py`:
- Read `registries/EDGE_REGISTRY.csv` (138 rows)
- Map columns:
  - `source_node_id` → `node_x`
  - `target_node_id` → `node_y`
  - `expected_sign` → `default_effect_direction` (`"positive"→1`, `"negative"→-1`, else `0`)
  - `functional_form` → `default_temporal_family`
  - `mechanism_description` → `canonical_statement`
  - `primary_pathway` → `edge_family`
  - Add `module = "A"`, `relation_label = mechanism_description[:80]`
- Write to `crci/database/seeds/edge_relations.csv` in the seed format
- ~50 lines of Python

**Step 1b** — Run it once, commit the regenerated seed CSV (29 → 138 rows).

**Step 1c** — **Preferred alternative**: Eliminate the seed CSV as an independent source of truth entirely. Modify `crci/database/seed_loader.py` to read **directly** from `registries/EDGE_REGISTRY.csv` (the registry is the only truth). The column mapping from Step 1a happens at load time, not as a separate sync script.

**Acceptable alternative**: Auto-regenerate seed CSV at build/startup and **block seeding** (not just warn) if the seed CSV is out-of-date relative to the registry. A warning is too weak — it should hard-fail in strict mode.

**Critical detail**: The column mapping must handle `expected_sign`:
- `"positive"` → `1`
- `"negative"` → `-1`
- `"context_dependent"` → `0`
- Any other value → `0` + log warning

**Validation after fix**:
```sql
SELECT COUNT(*) FROM edge_relations_definitions_v1;  -- should be 138
SELECT edge_relation_id FROM edge_relations_definitions_v1 LIMIT 3;  -- should start with ER_
```

**Dependencies**: None. This is the root fix.  
**Risk**: Low — the DB already has `ER_*` rows; this just makes the seed file match.  
**LOC**: ~60

---

## Slice 2: DB Persistence Protection (FIX-2)

### What's Broken

Four scripts can silently destroy evidence data:

| Script | Destructive Action | Guards? |
|---|---|---|
| `setup_complete.sh` | `DROP DATABASE IF EXISTS crci` | None |
| `scripts/setup_database.py --reset` | `DROP SCHEMA public CASCADE` | None |
| `scripts/setup_with_fallback.py` | `DROP DATABASE IF EXISTS crci` | None |
| `scripts/setup_sqlite.py` | `Base.metadata.create_all()` (safe, but seed after can overwrite) | None |

None of these scripts check if evidence data exists, back up the database, log what was destroyed, or require confirmation.

### Wiring Diagram

```
User runs any setup script
        │
        ▼
scripts/db_guard.py  (NEW — checks evidence before destruction)
        │
        ├── evidence exists? ──YES──► BLOCK unless --force
        │                             Print counts, abort
        └── evidence exists? ──NO───► Allow proceed
```

### Implementation Steps

**Step 2a** — Create `scripts/db_guard.py`:
```python
def check_evidence_exists(db_path: str) -> dict[str, int]:
    """Returns row counts for evidence tables."""
    # Query: edge_evidence_v1, population_norms_v1, temporal_evidence_v1,
    #         instrument_evidence_v1, study_registry_v1

def guard_before_reset(db_path: str, force: bool = False) -> bool:
    """If evidence exists and not --force, print warning and return False."""

def backup_db(db_path: str) -> Path:
    """Copy crci_dev.db to crci_dev.db.backup.{timestamp}"""
```
~80 lines.

**Step 2b** — Modify `scripts/setup_database.py`:
- Import `db_guard`
- Before `--reset`: call `guard_before_reset()`. If returns False, `sys.exit(1)`.
- Add `--force` flag to argparse.

**Step 2c** — Modify `scripts/setup_sqlite.py`: same guard.

**Step 2d** — Modify `scripts/setup_with_fallback.py`: same guard.

**Critical detail**: The guard checks **evidence** tables, NOT **seed** tables. Re-seeding node definitions is acceptable. Destroying `edge_evidence` rows is not.

**Step 2e** — **Environment separation guard** (prevents "pointed at wrong DB" disasters):
- Destructive commands must check `CRCI_ENV` environment variable
- If `CRCI_ENV` is not set or not `dev`, destructive commands **hard-fail** unless both `--force` AND `CRCI_ENV=dev` are present
- This prevents accidentally running `setup_database.py --reset` against a non-dev DB

```python
def require_dev_environment(force: bool) -> None:
    """Block destructive operations outside dev environment."""
    env = os.environ.get("CRCI_ENV", "unknown")
    if env != "dev":
        if not force:
            print(f"ERROR: CRCI_ENV={env}. Destructive ops require CRCI_ENV=dev.")
            sys.exit(1)
        else:
            print(f"WARNING: CRCI_ENV={env} but --force specified. Proceeding.")
```

**Dependencies**: None (parallel with Slice 1).  
**Risk**: Very low — only adds a safety check, doesn't change data flow.  
**LOC**: ~120 total across 4 files.

---

## Slice 3: Expand the CSV Template (FIX-3)

### What's Broken

The current `data/templates/edge_evidence_template.csv` has **12 columns**. The 7-layer calibration system (`crci/extraction/p3_heterogeneity/layers.py`) needs 7+ additional fields that the template doesn't capture.

Current template columns:
```
doi, edge_id, beta_raw, se_raw, effect_type_original, effect_size_type,
sample_size, study_design, cancer_type, treatment_phase, instrument_id,
confidence_note
```

### What Each Layer Needs (and where it comes from)

| Layer | Field Needed | Template Has It? | Effect of Missing |
|---|---|---|---|
| L1 (Design) | `study_design` | ✅ YES | — |
| L1 (Design) | `sample_size` | ✅ YES | — |
| L4 (Cancer) | `cancer_validated` | ❌ NO | Default `general_population` → **1.3× SE inflation** on cancer-validated instruments |
| L5 (GRADE) | `rob_overall` | ❌ NO | Default `MODERATE` → **1.25× SE inflation** on low-ROB studies |
| L7 (Fresh) | `pub_year` | ❌ NO | Default `None` → **0.85× weight** instead of correct weight |
| SC-1 | `shared_control_flag` | ❌ NO | Shared-control split never fires |
| CS-2 | `endpoint_vs_change` | ❌ NO | Endpoint/change alignment never fires |
| SE cascade | `se_derivation_method` | ❌ NO | SE provenance undocumented |
| P4 | `n_treatment`, `n_control` | ❌ NO (only total `sample_size`) | Can't compute per-arm precision |

**Worst case combined SE inflation from wrong defaults**: 3.0 × 1.30 × 1.25 = **4.875×** instead of correct ~1.0 × 1.0 × 1.0 = **1.0×** for a well-done recent RCT with cancer-validated instruments.

### Wiring Diagram

```
Extractor fills edge_evidence_template_v2.csv (26 columns)
        │
        ▼
manual_upload_watcher.py OR load_evidence_into_db.py
        │
        ▼
validated_evidence_writer.py (Slice 5)
        │  ├─ validate all fields
        │  ├─ standardize effect sizes
        │  ├─ derive SE via cascade
        │  └─ compute layer inputs
        ▼
edge_evidence_v1  (DB — now with all 7-layer fields populated)
        │
        ▼
P3 layers.py reads via getattr() → L1-L7 all fire correctly
```

### Implementation Steps

**Step 3a** — Create `data/templates/edge_evidence_template_v2.csv` with 28 columns (the 12 existing + 16 new):

New columns:
```
ci_low                     # 95% CI lower bound (required if se_raw not available)
ci_high                    # 95% CI upper bound (required if se_raw not available)
p_value                    # p-value (optional, used for SE derivation fallback)
n_treatment                # N in treatment arm (required for RCTs)
n_control                  # N in control arm (required for RCTs)
sd_treatment               # SD in treatment arm (required if effect_type is mean_diff)
sd_control                 # SD in control arm (required if effect_type is mean_diff)
cancer_validated           # L4: yes/no/unknown
rob_overall                # L5: low/moderate/high/critical
pub_year                   # L7: integer year
covariates_adjusted        # Audit: comma-separated list
endpoint_vs_change         # CS-2: endpoint/change_score
comparison_arm_label       # Audit: usual_care/waitlist/active_control
se_derivation_method       # SE provenance: direct/from_ci/from_p/from_f_stat/borrowed
shared_control_flag        # SC-1: 0 or 1
outcome_directionality     # higher_is_better / higher_is_worse (sign convention)
beta_sign_convention       # positive_is_benefit / positive_is_harm (canonical sign)
```

> **Why `outcome_directionality` and `beta_sign_convention`?** Without these, you
> standardize to Cohen's d but still mix sign conventions across instruments.
> TMT-B (lower = better) produces a negative d for improvement, while HVLT-R
> (higher = better) produces a positive d. The writer must flip signs to a
> canonical convention (positive = benefit) before persisting, and these fields
> tell it which direction to flip.

**Step 3b** — Update `EXTRACTION_PLAYBOOK.md` to document each new field with examples.

**Dependencies**: None (this is template-only).  
**Risk**: Zero — doesn't touch code.  
**LOC**: ~2 lines (CSV header + docs update).

---

## Slice 4: Fix Existing Paper Data (FIX-7 + FIX-8)

### What's Already Done vs Still Missing

**Current DB state** (checked live):

| Data Family | Table | Rows | Status |
|---|---|---|---|
| F1 — Edge evidence | `edge_evidence_v1` | 8 | ✅ Cohen's d already converted, study_design/cancer_type/rob_overall/instrument_id populated |
| F3 — Population norms | `population_norms_v1` | 9 | ✅ Loaded |
| F3 — Context priors | `node_priors_v1` | 7 | ✅ Loaded |
| F4 — Temporal evidence | `temporal_evidence_v1` | 16 | ✅ Loaded |
| F2 — Instrument evidence | `instrument_evidence_v1` | 0 | ❌ MISSING |
| F5 — Dose evidence | `dose_evidence_v1` | 0 | N/A (no dose-response data in these papers) |
| F6 — Subgroup evidence | `subgroup_evidence_v1` | 0 | N/A (no subgroup data reported) |

The CSV data for Campbell was already converted to Cohen's d (the `confidence_note` shows conversion provenance). So FIX-7 (convert Campbell effects) is **already done**.

### What's Still Missing: Instrument Evidence

Both papers use validated instruments but `instrument_evidence_v1` has 0 rows. This means:
- P7 `psychometric_compiler.py` reads 0 rows → produces nothing → `observation_noise_v1` never updated
- L4 cancer-validation multiplier can't use instrument reliability data

### Implementation Steps

**Step 4a** — Create instrument evidence CSVs. For each paper, extract reliability data from published norms:

Campbell 2017 instruments:
- `INST_TMT_B`: test-retest r=0.89 (Strauss 2006)
- `INST_COWAT`: test-retest r=0.83 (Strauss 2006)
- `INST_HVLTR`: test-retest r=0.74 (Benedict 1998)
- `INST_FACTCOG_PCI`: Cronbach's α=0.95 (Wagner 2009)

Cherrier 2013 instruments:
- `INST_DIGIT_SPAN`: α=0.90 (WAIS-III manual)
- `INST_FACTCOG_PCI`: α=0.95 (Wagner 2009)
- `INST_HVLTR`: test-retest r=0.74 (Benedict 1998)

**Step 4b** — Place CSVs in structured upload directories:
- `data/manual_uploads/structured/10.1002_pon.4370/instrument_evidence_template.csv`
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/instrument_evidence_template.csv`

**Step 4c** — Expand existing CSVs with v2 fields. Add to Campbell CSV:
```
cancer_validated=yes, pub_year=2017, n_treatment=10, n_control=9,
se_derivation_method=from_mean_diff_sd
```
Add to Cherrier CSV:
```
cancer_validated=yes, pub_year=2013, n_treatment=12, n_control=16,
se_derivation_method=direct
```

**Dependencies**: Slice 3 (template definition).  
**Risk**: Low — data curation, no code changes.

---

## Slice 5: Unified Evidence Writer with Validation (FIX-4)

### What's Broken — Three Competing Write Paths

Currently, evidence enters `edge_evidence_v1` through **three independent paths** that each populate different columns:

```
Path 1: LLM Pipeline
  P1 agents → P2 harmonization → evidence_writer.py
  Writes: 11/96 columns
  Misses: study_design, cancer_type, instrument_id, rob_overall, ALL layer inputs

Path 2: Manual CSV Import
  CSV file → manual_upload_watcher.py → raw INSERT
  Writes: ~18/96 columns (recently improved)
  Misses: some layer inputs, no standardization validation

Path 3: Bulk Loader
  CSV file → load_evidence_into_db.py → raw INSERT
  Writes: ~18/96 columns
  Misses: same as Path 2
```

None of these paths validate that:
- Edge IDs exist in `edge_relations_definitions_v1`
- Instrument IDs exist in `instrument_definitions_v1`
- Effect sizes are in commensurable units
- SE derivation method is documented
- Required fields for the 7-layer system are present

### Wiring Diagram (After Fix)

```
                    ┌─ LLM Pipeline (evidence_writer.py)
                    │
 All 3 paths ──────►│─ CSV Import (manual_upload_watcher.py)
                    │
                    └─ Bulk Loader (load_evidence_into_db.py)
                         │
                         ▼
              validated_evidence_writer.py  (NEW — single chokepoint)
                         │
                    ┌────┴────┐
                    │ Validate │
                    └────┬────┘
                         │ ✅ pass
                    ┌────┴────────────┐
                    │ Standardize     │ (raw mean diff → Cohen's d)
                    │ Derive SE       │ (L1→L5 cascade)
                    │ Compute layers  │ (cancer_validated→L4, rob→L5, etc.)
                    └────┬────────────┘
                         │
                         ▼
                  edge_evidence_v1  (DB — all 7-layer fields populated)
```

### Architecture: Three Internal Modules

Split `validated_evidence_writer.py` into **3 internal modules** (can be one file
with clear sections, or 3 files in a `validated_writer/` package). This prevents
"god object writer" entropy:

```
crci/extraction/validated_writer/
    __init__.py          — re-exports write_evidence_row()
    validation.py        — schema + enum + FK checks (~120 lines)
    standardization.py   — effect size conversion + sign harmonization (~120 lines)
    persistence.py       — dedup identity, insert/update, quarantine (~160 lines)
```

### Implementation Steps

**Step 5a** — Create the validation module (~120 lines):

**`validate_evidence_row(row: dict, session) -> tuple[bool, list[str]]`**
```
Checks (using vocab.py from Slice 0):
- row["edge_id"] exists in edge_relations_definitions_v1 (FK check)
- row["instrument_id"] (if present) exists in instrument_definitions_v1 (FK check)
- row["study_design"] resolves via vocab.resolve_study_design() (raises on unknown)
- row["effect_type_original"] ∈ vocab.EFFECT_TYPE_VOCAB
- row["effect_size_context"] ∈ vocab.EFFECT_SIZE_CONTEXT_VOCAB
- row["cancer_type"] ∈ vocab.CANCER_TYPE_VOCAB
- row["treatment_phase"] ∈ vocab.TREATMENT_PHASE_VOCAB
- SE precision: se_raw OR (ci_low AND ci_high) OR p_value present
- sample_size > 0
- If effect_type_original is mean_diff, sd_treatment + sd_control present
- rob_overall resolves via vocab.ROB_TO_GRADE_MAP (if present)
- pub_year is integer 1990-2026
Returns: (is_valid, list_of_error_messages)
```

**Step 5b** — Create the standardization module (~120 lines):

**`standardize_effect_size(row: dict) -> dict`**
```
If effect_type_original NOT IN {cohen_d, cohen_d_from_eta_sq, log_or}:
  - mean_diff + SDs → Cohen's d: d = mean_diff / SD_pooled
  - partial_eta_sq → d = 2√(η²/(1−η²))
  - odds_ratio → d = ln(OR) × √3/π
  - r_correlation → d = 2r/√(1−r²)

Store in row:
  effect_type_reported  — original type before conversion
  harmonized_beta       — standardized Cohen's d
  harmonized_se         — SE in Cohen's d scale
  hedges_g              — small-sample corrected: g = d × (1 - 3/(4(n1+n2)-9))
  conversion_formula    — which formula was used (e.g., "mean_diff_to_cohen_d")
  conversion_inputs     — JSON of inputs present/missing for audit trail
```

> **Why Hedges' g?** For publication-grade rigor, store both `cohen_d` and `hedges_g`.
> Small-sample correction matters for N<50 studies (both our current papers qualify:
> Campbell N=19, Cherrier N=28). Use Cohen's d as canonical for the pipeline but
> store Hedges' g for sensitivity analysis.

**`harmonize_sign(row: dict) -> dict`**
```
Using outcome_directionality and beta_sign_convention (from Slice 3):
  If outcome_directionality == "higher_is_worse":
    Flip sign: harmonized_beta = -harmonized_beta
  Store: sign_flipped = True/False for audit

Canonical convention: positive harmonized_beta = benefit (improvement)
```

**`derive_se(row: dict) -> dict`**
```
SE cascade (6 levels):
  L1: SE directly reported         → se_derivation_level = "L1_DIRECT"
  L2: SE from CI                   → SE = (CI_high - CI_low) / (2 × 1.96)  → "L2_FROM_CI"
  L3: SE from p-value              → SE = |beta| / z_from_p               → "L3_FROM_P"
  L4: SE from F/t stat             → SE = |beta| / √F                     → "L4_FROM_F"
  L5: SE borrowed from SD anchors  → "L5_BORROWED"
  L6: Heuristic                    → "L6_HEURISTIC"
```

**`compute_layer_inputs(row: dict) -> dict`**
```
Uses vocab.py mappings (from Slice 0) — NOT inline string checks:
  study_design     → vocab.resolve_study_design()    → canonical P3 L1 key
  cancer_validated → vocab.CANCER_VALIDATION_MAP      → canonical P3 L4 key
  rob_overall      → vocab.ROB_TO_GRADE_MAP           → canonical P3 L5 key
  pub_year         → stored directly for L7 freshness decay
```

**Step 5c** — Create the persistence module (~160 lines):

**`compute_evidence_identity(row: dict) -> str`**
```
Deterministic hash over ALL distinguishing dimensions (from Slice 0 Gap 3):
  study_id + edge_relation_id + instrument_id + timepoint_weeks +
  comparison_arm_label + effect_size_context + endpoint_vs_change +
  outcome_node_id
→ ler_id = "ler_" + sha256(identity_str)[:16]
```

**`write_validated_row(session, row: dict) -> str`**
```
After all validation/standardization:
- Compute ler_id via compute_evidence_identity()
- Dedup: if existing ler_id → UPDATE non-identity fields; else INSERT
- Map ALL fields to edge_evidence_v1 columns
- session.flush() (caller manages transaction)
Returns: ler_id
```

**`quarantine_row(session, row: dict, errors: list[str], source: str) -> str`**
```
For invalid rows (from Slice 0 Gap 2):
- Serialize raw row as JSON
- Write to evidence_quarantine_v1 with validation errors
- Log: "QUARANTINED {study_id}×{edge_id}: {errors}"
Returns: quarantine_id
```

**Top-level entry point** (`__init__.py`):
```python
def write_evidence_row(session, row: dict, source: str = "unknown") -> str | None:
    """Single entry point for all evidence writes.

    Returns ler_id if written, None if quarantined.
    """
    is_valid, errors = validate_evidence_row(row, session)
    if not is_valid:
        quarantine_row(session, row, errors, source)
        return None
    row = standardize_effect_size(row)
    row = harmonize_sign(row)
    row = derive_se(row)
    row = compute_layer_inputs(row)
    return write_validated_row(session, row)
```

**Step 5d** — Modify `crci/extraction/evidence_writer.py`: refactor `write_evidence_rows()` to call `write_evidence_row()` from the validated writer instead of direct ORM manipulation.

**Step 5e** — Modify `crci/retrieval/manual_upload_watcher.py`: refactor `_write_edge_evidence_rows()` to call `write_evidence_row()`.

**Step 5f** — Modify `scripts/load_evidence_into_db.py`: refactor `load_csv_evidence()` to call `write_evidence_row()`.

### Critical Wiring Detail: How the Writer Connects to P3 Layers

The reason this matters is the exact chain of attribute access. P3's `layers.py` reads evidence rows from the DB via `getattr(rec, "study_design", "unclassified")`. If the DB column is NULL, getattr returns the default, and the layer inflates SE by the wrong amount.

**Before fix**: `evidence_writer.py` writes 11/96 columns → P3 getattr hits default for 13 attributes → SE inflated 4.875×  
**After fix**: `validated_evidence_writer.py` writes 30+/96 columns → P3 getattr finds real values → SE inflated correctly (1.0× for good RCTs)

**Implementation rules**:

1. **Reject, don't default.** If `study_design` is missing, REJECT the row — don't silently default to "unclassified" (m=3.0×). Force the extractor to provide this critical field.

2. **Standardize at write time.** All raw mean differences must be converted to Cohen's d BEFORE entering the DB. The `effect_type_reported` column stores the original type; `harmonized_beta` stores the standardized value. This prevents the incommensurable-scales problem.

3. **Cascade SE derivation.** If direct SE is available, use it (Level 1). Otherwise, try CI→SE, then p→SE, then F→SE. Document which level was used in `se_derivation_level`. This ensures every row has an SE.

4. **Log every default.** If any field uses a fallback value, log: `"DEFAULTED {field} to {value} for {study_id}×{edge_id}. Reason: {why}."` This makes defaults visible and auditable.

**Dependencies**: Slice 0 (vocab + quarantine schema + dedup identity), Slice 3 (template).  
**Risk**: Medium — refactoring 3 write paths. All 3 must be changed atomically.  
**LOC**: ~400 for writer package + ~50 per modified file = ~550 total.

---

## Slice 6: Family Importers (FIX-5)

### What's Broken

5 of 7 DB tables have code that **reads** them but **nobody writes** to them:

```
  P7 Compiler               Reads Table                      Rows    Writer Exists?
  ─────────────             ──────────                       ────    ──────────────
  psychometric_compiler  → instrument_evidence_v1             0      ❌ NO
  prior_compiler         → population_norms_v1                9      ✅ (manual_upload_watcher)
  temporal_compiler      → temporal_evidence_v1              16      ✅ (load_evidence_into_db)
  dose_response_compiler → dose_evidence_v1                   0      ❌ NO
  modifier_compiler      → subgroup_evidence_v1               0      ❌ NO
  synergy_compiler       → context["synergy_trial_data"]      —      ❌ NO (context key, not DB)
```

The watcher has **stubs** for population_norms and context_priors (`logger.warning("not yet implemented")`), but the actual importers don't exist. Instrument, temporal, dose, and subgroup importers are completely absent.

### Wiring Diagram

```
data/manual_uploads/structured/{doi}/
    ├── edge_evidence_template.csv       ─► validated_evidence_writer (Slice 5)
    ├── population_norms_template.csv    ─► import_population_norm()   (NEW)
    ├── context_priors_template.csv      ─► import_context_prior()     (NEW)
    ├── temporal_evidence_template.csv   ─► import_temporal_evidence() (NEW)
    ├── instrument_evidence_template.csv ─► import_instrument_evidence() (NEW)
    └── correlation_template.csv         ─► import_correlation()       (FUTURE)
                │
                ▼
  manual_upload_watcher.py -- dispatch by filename
                │
                ▼
  family_importers.py  (NEW — one validate+insert function per family)
                │
        ┌───────┴────────┐
        │ Validate       │ (node_id exists? instrument_id exists? sd > 0?)
        └───────┬────────┘
                │
                ▼
  B10-B14 tables in DB
                │
                ▼
  P7 Compilers read from these tables
                │
                ▼
  Update Class A tables (observation_noise_v1, node_priors_v1, etc.)
```

### Implementation Steps

**Step 6a** — Create `crci/extraction/family_importers.py` (~250 lines):

**`import_population_norm(session, row: dict) -> str`**
- Validates: `node_id` ∈ `biomarker_node_definitions_v1`, `sd > 0`, `sample_size > 0`
- Maps: CSV `doi` → `study_id` (lookup in study_registry), CSV `mean` → `mean_raw`, CSV `sd` → `sd_raw`, CSV `sample_size` → `N`
- Inserts into: `population_norms_v1`
- Key: deterministic `id` from `study_id + node_id + cancer_type`

**`import_context_prior(session, row: dict) -> str`**
- Validates: `node_id` ∈ `biomarker_node_definitions_v1`, `prior_sd_z > 0`
- Maps: CSV `prior_mean_z` → `mean`, CSV `prior_sd_z` → `sd`, `dist_family = "normal"`, `prior_space = "z"`
- Inserts into: `node_priors_v1`

**`import_temporal_evidence(session, row: dict) -> str`**
- Validates: `edge_id` ∈ `edge_relations_definitions_v1`, `timepoint_weeks >= 0`, `sample_size > 0`
- Maps: CSV `value` → `effect`, CSV `is_recovery` → `is_recovery` (0/1)
- Inserts into: `temporal_evidence_v1`

**`import_instrument_evidence(session, row: dict) -> str`**
- Validates: `instrument_id` ∈ `instrument_definitions_v1`, `reliability_value ∈ (0, 1)`
- Maps: CSV `reliability_type` determines which column gets the value:
  - `internal_consistency` → `cronbachs_alpha`
  - `test_retest` → `test_retest_reliability`
- **Required provenance fields** (reliability is population-dependent):
  - `reliability_source_citation` — doi / isbn / manual reference (e.g., "Strauss 2006")
  - `population_match` — `general` / `cancer` / `age_matched` / `gender_matched`
  - Without `reliability_source_citation`, reject the row
- Inserts into: `instrument_evidence_v1`

**Step 6b** — Modify `crci/retrieval/manual_upload_watcher.py`:
- Replace the `logger.warning("not yet implemented")` stubs with calls to `family_importers.*`
- Add dispatch for `instrument_evidence_template.csv` and `temporal_evidence_template.csv`

**Step 6c** — Modify `scripts/load_evidence_into_db.py`:
- Add loading steps for each family after the existing edge evidence loading

**Dependencies**: Slice 5 (writer must exist for edge evidence path to be unified).  
**Risk**: Medium — new DB write paths. Each importer needs careful FK validation.  
**LOC**: ~250 for importers + ~50 for watcher mods = ~300 total.

---

## Slice 7: Completeness Checker (FIX-6)

### What's Broken

No automated system verifies whether a paper's extraction is complete. A paper can be "extracted" with 1/4 required families filled, wrong units, missing ROB — and nothing flags it. The `extraction_completeness_v1` table exists in the schema but has zero rows and zero writers.

### Wiring Diagram

```
Paper extraction completes (any path)
        │
        ▼
completeness_checker.py  (NEW)
  check_paper_completeness(session, study_id)
        │
        ├── Query study_registry_v1 for study_design → determine expected families
        │     RCT → expect F1, F3, F4, F6
        │     SR  → expect F1 (included_study_ids_json), NOT F3-F6
        │     Cross-sectional → expect F1, F3
        │
        ├── Query each family table for this study_id → count rows
        │     edge_evidence_v1 → F1 count
        │     population_norms_v1 → F3 count
        │     temporal_evidence_v1 → F4 count
        │     instrument_evidence_v1 → F2 count
        │     subgroup_evidence_v1 → F6 count
        │
        ├── Check L1-L7 readiness:
        │     For each evidence row, are the layer-input columns populated?
        │     L1: study_design ≠ NULL?
        │     L4: cancer_validation_status ≠ NULL?
        │     L5: rob_overall ≠ NULL?
        │     L7: pub_year ≠ NULL?
        │
        ├── Check effect-size unit consistency:
        │     All harmonized_beta in same scale (SMD vs log-ratio)?
        │     No raw mean differences mixed with Cohen's d?
        │
        └── Write report to extraction_completeness_v1 + print CLI report
```

### Implementation Steps

**Step 7a** — Create `crci/extraction/completeness_checker.py` (~200 lines):

```python
@dataclass
class ExtractionReport:
    study_id: str
    study_design: str
    expected_families: list[str]       # ["F1", "F3", "F4"]
    populated_families: dict[str, int] # {"F1": 4, "F3": 3, "F4": 0}
    missing_families: list[str]        # ["F4"]
    edge_evidence_issues: list[str]    # ["rob_overall NULL for 2/4 rows"]
    layer_readiness: dict[str, str]    # {"L1": "READY", "L4": "WILL_DEFAULT"}
    completeness_score: float          # 0.0 to 1.0
    blocking_issues: list[str]         # ["effect sizes in mixed units"]
    non_blocking_issues: list[str]     # ["missing instrument_evidence"]
    defaults_fired: dict[str, int]     # {"L1": 0, "L4": 2, "L5": 0, "L7": 4}
```

**Two failure classes**:

| Class | Examples | Pipeline Effect |
|---|---|---|
| **BLOCKING** | Missing canonical IDs, mixed effect-size units, null `study_design`, null `edge_relation_id` | Cannot proceed to compilation. Extraction must be fixed. |
| **NON-BLOCKING** | Missing `instrument_evidence`, missing `temporal_evidence`, `pub_year` null on some rows | Proceed but flag. Layers will use defaults — logged as `defaults_fired`. |

**`defaults_fired` counter**: The system's failure mode is *silent defaulting*.
The checker explicitly counts how many times each layer will fire its default
path for this paper's evidence rows. This makes the defaulting visible:

```
ExtractionReport for STUDY_CAMPBELL_2017:
  Completeness: 0.85
  BLOCKING issues: 0
  NON-BLOCKING issues: 1
    - instrument_evidence_v1: 0 rows (expected ≥4)
  Defaults that WILL fire:
    L1 (design):   0/4 rows → all have canonical study_design ✅
    L4 (cancer):   2/4 rows → cancer_validation_status will default to general_population
    L5 (GRADE):    0/4 rows → all have rob_overall ✅
    L7 (freshness): 0/4 rows → all have pub_year ✅
```

def check_paper_completeness(session, study_id: str) -> ExtractionReport: ...
def write_completeness_rows(session, report: ExtractionReport): ...
def print_report(report: ExtractionReport) -> str: ...
```

**Step 7b** — Wire into `scripts/run_manual_import.py`: after import, call `check_paper_completeness()` and print report.

**Step 7c** — Wire into `scripts/run_extraction.py`: after LLM pipeline, call the checker.

**Dependencies**: Slices 5+6 (importers must exist so family counts are meaningful).  
**Risk**: Low — read-only analysis + reporting.  
**LOC**: ~200.

---

## Slice 8: Wire P3 Intermediate State Fields

### What's Broken — The Duck-Typing Problem

P3 and P4 read 23+ attributes via `getattr(rec, "field", default)` that don't exist on `ScaledNumeric` or `HarmonizedClaim`. This is the "nobody writes this field" problem on **in-memory objects** rather than DB tables.

### P3 (7-Layer SE Calibration) — 13 Phantom Attributes

| Attribute | Default Used | Effect |
|---|---|---|
| `study_design` | `"unclassified"` | L1: Max SE multiplier (3.0×) applied to ALL records |
| `n_total` / `sample_size` | `None` | L1: No sample-size adjustment possible |
| `w_scope` / `scope_match` | `1.0` | L2: No transportability penalty/credit |
| `group_betas` / `group_ses` | `[]` | L3: I²=0, τ²=0 — heterogeneity layer is dead |
| `cancer_validation_status` | `"general_population"` | L4: Cancer-validation SE multiplier always 1.3× |
| `grade_level` | `"MODERATE"` | L5: GRADE layer always moderate |
| `days_since_measurement` | `0` | L6: Temporal decay layer never fires |
| `is_trait` | `False` | L6: Never applies trait-stable exception |
| `pub_year` | `None` | L7: Freshness decay never fires |

### P4 (Aggregation) — 10 Phantom Attributes

| Attribute | Default Used | Effect |
|---|---|---|
| `study_design` | `""` | Prior selection can't identify RCTs |
| `n_treatment` / `n_control` | `0` | SC-1 shared control split never engages |
| `shared_control_flag` | `False` | SC-1 completely bypassed |
| `endpoint_vs_change` | `"UNCLEAR"` | CS-2 alignment never engages |
| `se_derivation_level` | `None` | Verification escalation has no SE quality info |
| `meta_source_flag` | `None` | Can't distinguish primary vs meta-analytic claims |
| `is_cancer_matched` | `False` | Cancer-specificity weighting ignored |
| `is_superseded` | `False` | Freshness supersession check disabled |

### P4 StudyRegistry — 4 Column Mismatches

| Attribute Read | Actual Column | Issue |
|---|---|---|
| `n_analyzed` (lowercase) | `N_analyzed` (uppercase) | Case mismatch → always `None` |
| `follow_up_months` | — | Column doesn't exist on `study_registry_v1` |
| `funding_grant` | — | Column doesn't exist on `study_registry_v1` |
| `is_secondary_analysis` | — | Column doesn't exist on `study_registry_v1` |

### Two Options

**Option A** (recommended): Add all missing fields to `ScaledNumeric` and `HarmonizedClaim` in `crci/shared/models/intermediate_states.py`, and populate them upstream in P2.

**Option B**: When P3/P4 loads records from the DB (via `edge_evidence_v1`), use the DB columns directly instead of the intermediate state objects.

**Option A is better** because the LLM extraction path creates in-memory objects that flow through P2→P3→P4 without touching the DB until P4-WRT. Adding fields to the intermediate states means both the LLM path and DB-loaded path benefit.

### What Needs to Change

In `crci/shared/models/intermediate_states.py`, add to `HarmonizedClaim`:
```python
# ── Layer input fields (populated by P2 runner, consumed by P3/P4) ──
study_design: str = "unclassified"             # canonical key from vocab.py
n_total: int | None = None
n_treatment: int | None = None
n_control: int | None = None
cancer_validation_status: str = "general_population"  # canonical key from vocab.py
grade_level: str = "MODERATE"                  # canonical key from vocab.py
pub_year: int | None = None
days_since_measurement: float = 0.0
is_trait: bool = False
shared_control_flag: bool = False
shared_control_study_id: str | None = None
endpoint_vs_change: str = "UNCLEAR"
meta_source_flag: str | None = None
se_derivation_level: str | None = None
is_cancer_matched: bool = False
is_superseded: bool = False

# ── Provenance tracking (prevents "is this defaulted or real?") ──
layer_fields_provenance: dict[str, str] = {}   # {"study_design": "from_study_registry", ...}
is_complete_for_p3: bool = False                # computed, not defaulted
```

> **Why `layer_fields_provenance` and `is_complete_for_p3`?** Adding fields with
> defaults recreates the same problem at a different layer — you can't tell whether
> `grade_level = "MODERATE"` is a real extraction result or the default. The
> provenance dict tracks where each field came from:
> - `"from_study_registry"` — looked up from study_registry_v1
> - `"from_agent_annotation"` — extracted by P1 agent and promoted
> - `"from_csv_template"` — manually entered in the CSV
> - `"default"` — not populated, using model default
>
> `is_complete_for_p3` is a computed boolean: `True` only when `study_design`,
> `cancer_validation_status`, `grade_level`, and `pub_year` are ALL non-default.
> P3 can check this flag and log a warning if False.

Then in `crci/extraction/p2_harmonization/runner.py`, populate these fields from:
1. The `study_registry_v1` row (study_design, year→pub_year)
2. The P0 classification (cancer_type mapping → cancer_validation_status)
3. The agent annotations (rob → grade_level)

**Dependencies**: Can be done in parallel with any slice (but uses vocab.py from Slice 0).  
**Risk**: Medium — touches the intermediate state model that all stages use.  
**LOC**: ~40 for model changes + ~50 for P2 runner wiring = ~90.

---

## Slice 9: Wire Remaining Broken Spots

These are the additional gaps found in the previous audit that weren't in the PIPELINE_AUDIT.

### 9A: Context Key Orphans

| Key | Reader | Fix |
|---|---|---|
| `missingness_report` | P5 runner (line 57) | Create a `MissingnessReport` in P1 or P2 from agent completeness data, set `context["missingness_report"]` |
| `synergy_trial_data` | P7 synergy compiler (line 327) | Skip for now — only relevant for factorial trials (none extracted yet) |
| `outcomes` | `concept_engine.py` (line 211) | Set `context["outcomes"]` from AG04 output in P1 runner |

### 9B: P4 StudyRegistry Column Mismatches

In `crci/extraction/p4_aggregation/runner.py` line ~288:
- `getattr(row, "n_analyzed", None)` — case mismatch, should be `N_analyzed`
- `getattr(row, "follow_up_months", None)` — column doesn't exist
- `getattr(row, "funding_grant", None)` — column doesn't exist
- `getattr(row, "is_secondary_analysis", False)` — column doesn't exist

**Fix**: Use correct column name for `N_analyzed`; remove or add the missing columns to the schema.

### 9C: Chain B EvidenceRecord Gap

The algorithm's Chain B expects rich per-study `EvidenceRecord` objects with fields like `identification_status`, `quality_grade`, `scope_weights`, `cancer_validation_status`. These are only populated via hardcoded defaults in `scripts/run_build.py`.

| Field | Required By Chain B | Populated By Extraction? |
|---|---|---|
| `identification_status` | B4 inclusion prob | ❌ NO |
| `quality_grade` | B2 SE_eff (m_GRADE) | ❌ NO |
| `scope_weights` (5-dim dict) | B2 SE_eff (w_scope) | ❌ NO |
| `cancer_validation_status` | B2 SE_eff, B4 | ❌ NO |
| `temporal_distance_days` | B2 SE_eff (w_temporal) | ❌ NO |
| `outcome_type` | B2+ | ❌ NO |
| `is_animal` | B1a precision cap | ❌ NO |
| `is_cross_sectional` | B1a precision cap | ❌ NO |
| `has_rct_component` | B4 inclusion prob | ❌ NO |
| `sigma_sq_structural` | B2 SE_eff | ❌ NO |

**Fix**: After Slice 5 (validated writer) populates all `edge_evidence` columns, Chain B's evidence compiler should read from `edge_evidence_v1` directly instead of requiring manual CSV.

### 9D: DB Tables Never Written (Beyond B10-B14)

| Table | Schema Exists | Any Writer? | Any Reader? |
|---|---|---|---|
| `extraction_audit_v1` | ✅ | ❌ NO | ❌ NO |
| `extraction_completeness_v1` | ✅ | ❌ NO | ❌ NO |

**Fix**: `extraction_audit_v1` — add audit row emission to each pipeline stage. `extraction_completeness_v1` — populated by Slice 7 (completeness checker).

**Dependencies**: Slices 5+8.

---

## Execution Order

Optimal parallelization — slices grouped by dependency:

```
Week 0 — Lock Invariants (Slice 0 — MUST COMPLETE BEFORE ANYTHING ELSE)
  └── Slice 0: vocab.py + quarantine schema + dedup identity  (120 LOC)
              Define-of-Done test: resolve_study_design("RCT", 19) == "small_rct_default"

Week 1 — Foundation (Slices 1+2+3, all independent)
  ├── Slice 1: seed loader reads from registry directly  (60 LOC)
  ├── Slice 2: db_guard.py + env separation guard          (120 LOC)
  └── Slice 3: edge_evidence_template_v2.csv                (template only)

Week 2 — Data + Intermediate States (Slices 4+8, parallelizable)
  ├── Slice 4: Fill instrument_evidence CSVs                 (data curation)
  └── Slice 8: Add fields + provenance to HarmonizedClaim     (90 LOC)

Week 3 — Unified Writer (Slice 5 — the big one)
  └── Slice 5: validated_writer/ package                      (550 LOC)
              + refactor 3 write paths
              + quarantine persistence

Week 4 — Importers + Checker (Slices 6+7, sequential)
  ├── Slice 6: family_importers.py + wire watcher            (300 LOC)
  └── Slice 7: completeness_checker.py + wire scripts        (200 LOC)

Week 5 — Cross-cutting Wiring (Slice 9)
  └── Slice 9: Fix context orphans + P4 column               (~150 LOC)
              mismatches + Chain B bridge
```

**Total estimated LOC**: ~1,590 new code + ~200 modifications to existing files.

### Dependency Graph

```
Slice 0 (invariants: vocab + quarantine + dedup) ───────┐
                                                        │
        ┌───────────────────────────────────────────────┘
Slice 1 (edge unification) ──────────────────────────────┐
                                                          │
Slice 2 (persistence guard) ─────────────────────────────→│
                                                          │
Slice 3 (expanded template) ─────► Slice 4 (paper data) ─┤
                                                          │
Slice 8 (intermediate states) ───────────────────────────→│
                                                          │
                                          ┌───────────────┘
                                          ▼
                                   Slice 5 (unified writer)
                                          │
                                          ▼
                                   Slice 6 (family importers)
                                          │
                                          ▼
                                   Slice 7 (completeness checker)
                                          │
                                          ▼
                                   Slice 9 (cross-cutting wiring)
```

---

## Verification Matrix

| Slice | Verification Command / Query | Expected Result |
|---|---|---|
| 0 | `resolve_study_design("RCT", n_total=500)` | `"large_rct"` |
| 0 | `resolve_study_design("RCT", n_total=19)` | `"small_rct_default"` |
| 0 | `resolve_study_design("bogus")` | `ValueError` raised |
| 0 | Insert row with `study_design=None` via writer | Row in `evidence_quarantine_v1`, NOT in `edge_evidence_v1` |
| 0 | Same study+edge, different instruments | Two distinct `ler_id` values |
| 1 | `SELECT COUNT(*) FROM edge_relations_definitions_v1 WHERE edge_relation_id LIKE 'ER_%'` | 138 |
| 1 | `SELECT COUNT(*) FROM edge_relations_definitions_v1 WHERE edge_relation_id LIKE 'EDGE_%'` | 0 |
| 2 | `python scripts/setup_database.py --init --seed` (without `--force`) | Blocked with warning |
| 2 | `CRCI_ENV=prod python scripts/setup_database.py --reset` | Hard-fail regardless of `--force` |
| 3 | `head -1 data/templates/edge_evidence_template_v2.csv \| tr ',' '\n' \| wc -l` | 28 |
| 4 | `SELECT COUNT(*) FROM instrument_evidence_v1` | ≥ 7 |
| 5 | Insert evidence row with `effect_type_original=mean_diff` | Auto-converted to `cohen_d`, `hedges_g` computed, all layer columns populated |
| 5 | `SELECT COUNT(*) FROM edge_evidence_v1 WHERE study_design IS NULL` | 0 |
| 5 | `SELECT COUNT(*) FROM edge_evidence_v1 WHERE effect_type_reported LIKE 'mean_diff%'` | 0 (all standardized) |
| 5 | `SELECT COUNT(*) FROM evidence_quarantine_v1` | ≥ 0 (table exists) |
| 6 | After import: `SELECT COUNT(*) FROM population_norms_v1` | ≥ 9 |
| 6 | After import: `SELECT COUNT(*) FROM temporal_evidence_v1` | ≥ 16 |
| 6 | After import: `SELECT COUNT(*) FROM instrument_evidence_v1` | ≥ 7 |
| 7 | `check_paper_completeness("STUDY_CAMPBELL_2017")` | `completeness_score > 0.8`, no blocking issues |
| 8 | Run P3 on evidence for Campbell | `m_design ≠ 3.0`, `m_scale ≠ 1.3` |
| 9 | `context.get("missingness_report")` after P2 | Not `None` |
| 9 | Chain B reads complete evidence records from DB | All 10 fields populated |

### End-to-End Smoke Test

After all slices are complete:

```bash
# 1. Reset DB safely
python scripts/setup_database.py --init --seed --force

# 2. Load evidence for both papers
python scripts/load_evidence_into_db.py

# 3. Check completeness
python -c "
from crci.extraction.completeness_checker import check_paper_completeness, print_report
from crci.shared.db import get_session
with get_session() as s:
    r = check_paper_completeness(s, 'STUDY_CAMPBELL_2017')
    print(print_report(r))
"

# 4. Verify layer readiness (no WILL_DEFAULT for L1, L4, L5, L7)
# 5. Verify all harmonized_beta values in plausible SMD range (-3 to +3)
# 6. Verify instrument_evidence_v1 has rows
# 7. Run P3 and verify SE inflation is < 2.0× for Campbell RCT
```

---

## Definition of Done per Slice

> **If you cannot write the test for a slice, you do not yet understand the slice.**

Each slice must include a **failing test that becomes passing**. This is not optional —
it is the definition of "done." Without it, you're shipping hope, not engineering.

| Slice | Definition of Done Test |
|---|---|
| **0** | `test_vocab_mapping`: `resolve_study_design("RCT", 19)` returns `"small_rct_default"`. `resolve_study_design("bogus")` raises `ValueError`. `compute_evidence_identity()` returns distinct hashes for same-edge different-instrument rows. |
| **1** | `test_seed_roundtrip`: Drop and recreate DB via seed loader → `SELECT COUNT(*) FROM edge_relations_definitions_v1` = 138. All evidence FK joins still resolve (0 orphans). |
| **2** | `test_guard_blocks`: With 8 evidence rows in DB, `setup_database.py --reset` (without `--force`) exits non-zero. With `--force` AND `CRCI_ENV=dev`, succeeds and creates backup file. |
| **3** | `test_template_columns`: Template v2 CSV header has exactly 28 columns including `outcome_directionality` and `beta_sign_convention`. |
| **4** | `test_instrument_data`: After loading Cherrier + Campbell instrument CSVs, `instrument_evidence_v1` has ≥ 7 rows. Each has non-null `reliability_source_citation`. |
| **5** | `test_write_valid`: Insert a valid `mean_diff` row → auto-converted to `cohen_d`, `hedges_g` stored, `study_design` is canonical P3 key, all critical layer columns non-null. |
| **5** | `test_write_invalid`: Insert a row with missing `study_design` → quarantined. `evidence_quarantine_v1` has the row. `edge_evidence_v1` does NOT. |
| **5** | `test_dedup`: Re-import same row → same `ler_id`, row updated in place (not duplicated). Import with different `instrument_id` → new `ler_id`. |
| **6** | `test_family_import`: After importing all CSVs for Campbell, all 4 family tables have > 0 rows. FK constraints all satisfied. |
| **7** | `test_completeness`: `check_paper_completeness("STUDY_CAMPBELL_2017")` returns `completeness_score > 0.8`, 0 blocking issues, `defaults_fired["L1"] == 0`. |
| **8** | `test_p3_no_defaults`: Run P3 on an LLM-extracted HarmonizedClaim with all fields populated via provenance → `is_complete_for_p3 == True`. Zero critical defaults fired (m_design ≠ 3.0, m_scale ≠ 1.3). |
| **9** | `test_chain_b_bridge`: Build Chain B EvidenceRecord from `edge_evidence_v1` → all 10 fields populated, no hardcoded defaults from `run_build.py`. |

### Execution Discipline

> You are at high risk of scope creep in Slice 5. The way to prevent that:

1. **Write the test FIRST** (the definition-of-done test above)
2. **Make it fail** (it should fail because the code doesn't exist yet)
3. **Implement the minimum code to make it pass**
4. **Stop** — do not add "nice to have" features until all slices are done

If you switch tasks mid-slice, you will end up coding Slice 5 and then discovering
the enum/key mismatch later, which will force a rewrite. **Stay on Slice 0 in full
focus until all three invariant tests pass.**
