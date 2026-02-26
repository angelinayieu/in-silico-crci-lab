# CRCI Extraction Pipeline — Root-Cause Audit & Fix Specification

**Date**: 2026-02-26  
**Scope**: Structural root-cause analysis of why extraction produces low-quality or missing data  
**Method**: Code trace of every write path, column mapping, DB lifecycle, and validation gap  
**DB snapshot at audit time**: 25 `EDGE_*` definitions, 30 evidence rows (24 UNASSIGNED, 6 assigned to 1 edge), 0 population norms, 0 temporal evidence, 0 instrument evidence, 70/96 evidence columns empty

---

## Table of Contents

1. [Issue Inventory (8 root causes)](#issue-inventory)
2. [Structural Invariants (non-optional)](#structural-invariants)
3. [Fix Specifications (8 fixes, dependency-ordered)](#fix-specifications)
4. [Execution Sequence](#execution-sequence)
5. [Validation Checklist](#validation-checklist)

---

## Issue Inventory

### ISSUE-1: Two Competing Edge Definition Sources — DB Gets Overwritten

**Severity**: S0-FATAL  
**Evidence**: `edge_relations_definitions_v1` contains 25 `EDGE_*` rows (from seed). Manual CSVs use 137 `ER_*` IDs. Evidence rows referencing `ER_*` IDs cannot FK-join to edge definitions.

**Root cause**: Two files define edges with incompatible conventions:

| File | Convention | Count | Loaded by |
|------|-----------|-------|-----------|
| `crci/database/seeds/edge_relations.csv` | `EDGE_IL6_COGNITION` etc. | 25 rows | `setup_database.py --seed` → `seed_loader.py` |
| `registries/EDGE_REGISTRY.csv` | `ER_ACTIVITY_PROC_SPEED` etc. | 138 rows | `load_evidence_into_db.py` (not in seed path) |

Every DB recreation (setup scripts, container restart) reloads the 25-row seed, erasing any `ER_*` rows previously loaded. The manual CSVs reference `ER_*` IDs exclusively.

**Column schema also differs:**

| Column | Seed CSV | Registry CSV |
|--------|---------|-------------|
| Source/target nodes | `node_x`, `node_y` | `source_node_id`, `target_node_id` |
| Direction | `default_effect_direction` | `expected_sign` |
| Temporal model | `default_temporal_family` | `functional_form` |
| Pathway | (missing) | `primary_pathway` |

**Why this is fatal**: Without matching IDs, evidence cannot be joined to edge definitions. The system cannot determine source/target nodes, expected signs, or pathway membership for any evidence row — making every downstream computation (IVW pooling, sign checks, pathway analysis) impossible.

---

### ISSUE-2: No Persistence Protection — DB Can Be Silently Wiped

**Severity**: S0-FATAL  
**Evidence**: Between sessions, all 8 manually loaded evidence rows, 137 reseeded edge definitions, and 3 study registrations disappeared. DB reverted to initial 25-stub state.

**Root cause**: Four scripts can destroy the database without warning:

| Script | Destructive action | Guards? |
|--------|-------------------|---------|
| `setup_complete.sh` | `DROP DATABASE IF EXISTS crci; CREATE DATABASE crci` | None |
| `setup_database.py --init` | Runs SQL schema files (CREATE TABLE IF NOT EXISTS — safe for schema, but `--seed` re-inserts stubs) | None |
| `setup_sqlite.py` | `Base.metadata.create_all(engine)` — creates tables, does not drop existing data, but may reset via seed | None |
| `setup_with_fallback.py` | Same as above | None |

None of these scripts:
- Check if evidence data exists before overwriting
- Back up the database
- Log what data was destroyed
- Require confirmation

The `seed_loader.py` uses `upsert=False` by default, which means it skips rows that already exist by primary key. **But**: if the DB was recreated (tables dropped and recreated), all rows are gone and seeding re-inserts the 25 `EDGE_*` stubs — overwriting any `ER_*` definitions that were there.

---

### ISSUE-3: LLM Extraction Produces Structurally Deficient Evidence

**Severity**: S1-CRITICAL  
**Evidence**: The LLM pipeline ran on Cherrier 2013 and produced 30 evidence rows. Examining them reveals:

| Metric | Expected | Actual |
|--------|----------|--------|
| Distinct edges mapped | 4 (WM, Attn, CogComplaints, EpiMem) | 1 (`ER_COGACTIVITY_WORKMEM`) + 24 `UNASSIGNED` |
| N_effect per row | 28 (paper's N) | 0 for all rows |
| SE populated | 30/30 | 18/30 (12 rows have `se_reported = NULL`) |
| Populated columns | ≥20 contextual fields | 26/96 columns populated; 70 columns entirely empty |
| Beta consistency | One value per edge (paper reports d=0.79 for WM) | 6 different values for same edge: 0.797, 0.899, 1.012, 1.019, 1.618 |

**Root cause chain:**

1. **Agent edge mapping failure**: The LLM agents (P1) produce `SpanLabel` objects with labels like `"between_group_mean_diff"` or `"cohen_d"`. These labels are text, not edge IDs. The mapping from span labels → edge IDs happens in the pipeline, but 24/30 rows ended up `UNASSIGNED` — meaning the mapper couldn't determine which edge the extracted number belongs to.

2. **N_effect = 0**: The `evidence_writer.py` line 129 uses `_get_attr(record, "n") or _get_attr(record, "n_effect") or 0`. The ScaledNumeric records from P2 don't carry sample size — it's extracted by AG03 (CohortAgent) as metadata but isn't threaded into the per-span records. Default is 0.

3. **Beta duplication**: The LLM extracts multiple numeric spans from the same section (e.g., means, SDs, F-statistics, d values) and each gets harmonized separately. Without proper span-to-edge dedup, the same conceptual result appears as multiple rows with slightly different values (likely from different text spans: "d = 0.79", "F(7,20) = 4.197", etc. all getting converted to harmonized_beta).

4. **70 empty contextual columns**: `evidence_writer.py` maps only: `beta, se, scale, se_source, se_derivation_level, se_inflation_applied, se_quality_tag, conversion_formula, conversion_bias_risk, edge_relation_id, n_effect` — **11 fields**. The remaining 85 columns (cancer_type, treatment_phase, instrument_id, ROB, etc.) are never populated because the ScaledNumeric intermediate state doesn't carry them.

---

### ISSUE-4: Manual CSV Template Too Narrow for Algorithm Needs

**Severity**: S1-CRITICAL  
**Evidence**: `edge_evidence_template.csv` has 12 columns. `edge_evidence_v1` table has 96 columns. The CSV→DB loader maps 7 data columns. The 7-layer calibration system needs ≥7 additional fields that are never supplied.

**Template columns** (12):
```
doi, edge_id, beta_raw, se_raw, effect_type_original, effect_size_type,
sample_size, study_design, cancer_type, treatment_phase, instrument_id,
confidence_note
```

**Columns the loaders actually INSERT** (across all 3 write paths):

| Column | evidence_writer.py | manual_upload_watcher.py | load_evidence_into_db.py |
|--------|-------------------|------------------------|------------------------|
| `effect_value_reported` | ✅ | ✅ | ✅ |
| `se_reported` | ✅ | ✅ | ✅ |
| `N_effect` | ✅ (but gets 0) | ✅ | ✅ |
| `edge_relation_id` | ✅ | ✅ | ✅ |
| `effect_type_reported` | ✅ (hardcoded "harmonized_beta") | ✅ | ✅ |
| `effect_size_type` | ❌ | ✅ | ✅ |
| `study_id` | ✅ | ✅ | ✅ |
| `edge_family` | ✅ (from record, usually null) | ✅ (from edge_defs lookup) | ✅ |
| `node_x`, `node_y` | ❌ | ✅ (from edge_defs lookup) | ✅ |
| `upstream_instrument_id` | ❌ | ❌ | ❌ |
| `cancer_type` (implicit) | ❌ | ❌ (in CSV but not loaded) | ❌ |
| `treatment_phase` (implicit) | ❌ | ❌ (in CSV but not loaded) | ❌ |
| `rob_overall` | ❌ | ❌ | ❌ |
| `sd_x`, `sd_y` | ❌ | ❌ | ❌ |
| `ci_low_reported`, `ci_high_reported` | ❌ | ❌ | ❌ |
| `p_value` | ❌ | ❌ | ❌ |
| `covariates_adjusted` | ❌ | ❌ | ❌ |
| `endpoint_vs_change` | ❌ | ❌ | ❌ |
| `comparison_arm_label` | ❌ | ❌ | ❌ |
| `se_derivation_level` | ✅ | ❌ | ❌ |
| `freshness_w` | ❌ | ❌ | ❌ |

**Impact on 7-layer system (layers.py)**:

When `apply_all_layers()` processes these sparse rows:
- **L1** (`study_design`): No column exists → `getattr(rec, "study_design", "unclassified")` → **m_design = 3.0×** (for both papers that are actually RCTs, should be 1.0–1.25)
- **L4** (`cancer_validation_status`): Not populated → defaults to `"general_population"` → **m_scale = 1.30×** (instruments are cancer-validated, should be 1.0)
- **L5** (`grade_level`): No ROB data → defaults to `"MODERATE"` → **m_grade = 1.25×** (Campbell has low ROB, should be 1.0)
- **L7** (`pub_year`): Not populated → defaults to `None` → **w_fresh = 0.85** (2013 paper vs 2025 reference year, should be w = 1 − 0.015 × 12 = 0.82)

**Worst case combined SE inflation from wrong defaults**: 3.0 × 1.30 × 1.25 = **4.875×** instead of correct ~1.0 × 1.0 × 1.0 = **1.0×** for a well-done recent RCT with cancer-validated instruments.

---

### ISSUE-5: Effect Size Units Not Standardized — Incommensurable Scales Mixed

**Severity**: S1-CRITICAL  
**Evidence**: Examining the manual CSV extractions:

| Paper | Edge | beta_raw | effect_type_original | Units |
|-------|------|----------|---------------------|-------|
| Cherrier 2013 | ER_COGACTIVITY_WORKMEM | 0.79 | cohen_d | **SD units** ✅ |
| Cherrier 2013 | ER_COGACTIVITY_ATTN | 0.59 | cohen_d | **SD units** ✅ |
| Campbell 2017 | ER_ACTIVITY_PROC_SPEED | -14.2 | mean_diff_seconds | **Seconds** ❌ |
| Campbell 2017 | ER_ACTIVITY_VERBAL_FLUENCY | 3.0 | mean_diff_words | **Words** ❌ |
| Campbell 2017 | ER_ACTIVITY_EPIMEM | -1.5 | mean_diff_raw_score | **Raw score** ❌ |
| Campbell 2017 | ER_ACTIVITY_COG_COMPLAINTS | 3.9 | mean_diff_raw_score | **Raw score** ❌ |

The spec (§2.2) states F1 output should be **"SMD (SD units) or log-ratio"**. Four of eight manual entries are raw mean differences, not standardized.

**Root cause**: No validation exists at import time. The `effect_type_original` column documents what the paper reported, but nothing prevents raw mean differences from entering the same table as Cohen's d values. If these ever enter IVW pooling together, the result is meaningless — you'd average 0.79 SD-units with -14.2 seconds.

**Campbell conversion is possible**: The meta.json has `partial_eta_sq` values for each outcome. Cohen's d can be derived:

d = 2 × sqrt(η² / (1 − η²))    [valid only when df₁ = 1, i.e., 2-level contrast]

For TMT-A: d = 2 × sqrt(0.35 / 0.65) = 1.47. Campbell's ANCOVA uses a 2-level group factor (exercise vs control), so df₁=1 and the conversion is valid. But this conversion was never performed, and no guard exists to reject it for designs where df₁ > 1.

---

### ISSUE-6: Five of Seven Data Families Never Loaded

**Severity**: S2-HIGH  
**Evidence**: The system defines 7 parameter families. Database table state:

| Family | DB Table | Rows | CSV Data Exists? | Importer Exists? |
|--------|----------|------|-----------------|-----------------|
| F1 — Edge weights | `edge_evidence_v1` | 30 (mostly UNASSIGNED) | YES (8 rows in CSVs) | YES (3 write paths) |
| F2 — Instrument psychometrics | `instrument_evidence_v1` | 0 | NO | NO |
| F3 — Population norms | `population_norms_v1` | 0 | YES (9 rows in CSVs) | NO (stub only) |
| F3 — Context priors | `node_priors_v1` | 0 | YES (7 rows in CSVs) | NO (stub only) |
| F4 — Temporal dynamics | `temporal_evidence_v1` | 0 | NO | NO |
| F5 — Dose-response | `dose_evidence_v1` | 0 | N/A (no dose-response papers) | NO |
| F6 — Subgroup modifiers | `subgroup_evidence_v1` | 0 | NO | NO |
| F7 — Synergy | `intervention_synergy_v1` | 0 | N/A (no factorial papers) | NO |

**Root cause**: The import system was built for `edge_evidence_template.csv` only. The `manual_upload_watcher.py` has explicit code for edge evidence but only a `logger.warning("not yet implemented")` for population_norms and context_priors. Temporal, instrument, correlation, and subgroup importers don't exist.

**What was missed in the two extracted papers:**

| Template | Campbell 2017 | Cherrier 2013 |
|----------|--------------|---------------|
| Population norms | 6 rows filled ✅ | 3 rows filled ✅ |
| Context priors | 4 rows filled ✅ | 3 rows filled ✅ |
| Temporal evidence | **NOT FILLED** — paper has pre/post at week 0 and 24 | **NOT FILLED** — paper has pre/post at week 0 and 7 |
| Instrument evidence | **NOT FILLED** — both papers use validated instruments with published reliability | **NOT FILLED** |
| Correlation | **NOT FILLED** — Campbell has fMRI correlations | N/A |

---

### ISSUE-7: No Per-Paper Extraction Completeness Check

**Severity**: S2-HIGH  
**Evidence**: The spec (§4.5) defines target families per study subtype. Both papers are RCTs, which target F1, F3, F4, F6. No automated system checks whether these families were actually populated.

| Check | Exists? | Location |
|-------|---------|----------|
| "This paper is RCT → expect F1, F3, F4, F6" | ❌ | — |
| "edge_evidence_template filled?" | ❌ | — |
| "population_norms_template filled?" | ❌ | — |
| "temporal_evidence_template filled?" | ❌ | — |
| "effect_type_original compatible with target scale?" | ❌ | — |
| "ROB assessment present in meta.json?" | ❌ | — |
| "All CSV columns have valid enum values?" | ❌ | — |
| "instrument_id exists in INSTRUMENT_REGISTRY?" | ❌ | — |
| `extraction_completeness_v1` table | Schema exists (0 rows) | Never written to |

**Impact**: Extraction completeness is entirely unmonitored. A paper can be "extracted" with only 1 of 4 required templates filled, partial edge mapping, wrong units, and missing ROB — and nothing flags it.

---

### ISSUE-8: Three Parallel Write Paths With No Unified Validation

**Severity**: S2-HIGH  
**Evidence**: Evidence can enter `edge_evidence_v1` through:

1. **LLM pipeline** (`evidence_writer.py`) — Maps 11 of 96 columns, sets `effect_type_reported = "harmonized_beta"`, no cancer_type/treatment_phase/instrument
2. **CSV import** (`manual_upload_watcher.py`) — Maps 7 of 96 columns, drops cancer_type/treatment_phase from CSV despite them being present
3. **Loader script** (`load_evidence_into_db.py`) — Maps 7 of 96 columns, same gaps

**Root cause**: Each write path was implemented independently. There is no shared validation function that all three call. Each path:
- Has different column mapping logic
- Uses different study_id conventions (`doi:10.1016/...` vs `STUDY_CHERRIER_2013`)
- Has different dedup logic (span_hash vs study_id×edge_id check vs UUID)
- Generates different ler_id formats

**No path validates:**
- Effect size units against target scale
- Edge ID exists in edge definitions
- Instrument ID exists in instrument registry
- Cancer type is from controlled vocabulary
- SE derivation method is documented
- Required fields are non-null

---

## Structural Invariants

These invariants are **non-optional prerequisites** that cut across multiple fixes. They must be enforced before or alongside the fix implementations.

### INV-1: Missingness Policy — Reject vs Default

Two rules in FIX-4 appear contradictory: "reject, don't default" and "log every default." The resolution:

**REJECT (hard-fail the row) when missing:**
- `study_design` — drives L1 multiplier (default=3.0× is catastrophic)
- `rob_overall` — drives L5 GRADE multiplier
- `pub_year` — drives L7 freshness weight
- `instrument_id` — drives L4 scale validation and measurement model
- `cancer_validated` — drives L4 scale multiplier (default=1.3× is wrong for validated instruments)
- `sample_size` — drives SE derivation and IVW weight
- Precision source: at least one of `se_raw`, `(ci_low, ci_high)`, `p_value` must be present
- Scale compatibility: `effect_type_original` must be present and valid

**ALLOW DEFAULT + LOG when missing:**
- `covariates_adjusted` → default: empty list, tag `defaulted_fields_json`
- `comparison_arm_label` → default: `"unspecified"`, tag
- `endpoint_vs_change` → default: `"unspecified"`, tag
- `shared_control_flag` → default: `0`, tag
- `notes`, `confidence_note` → default: empty string

For every defaulted field, write the field name into a `defaulted_fields_json` column on the row so downstream consumers can see what was imputed.

### INV-2: UNASSIGNED Is Rejected, Not Stored

`edge_relation_id = 'UNASSIGNED'` is a sentinel string currently stored in 24/30 evidence rows. This must be treated as a validation failure:

- The validated writer (FIX-4) MUST reject any row where `edge_relation_id` is NULL, empty, or `'UNASSIGNED'`.
- Existing UNASSIGNED rows must be either re-mapped to correct ER_* IDs or deleted.
- The string `'UNASSIGNED'` must never enter `edge_evidence_v1`.

### INV-3: DB-Layer Referential Integrity

Python-only validation is insufficient. Add enforcement at the database layer:

```sql
-- Enable FK enforcement (must be set per-connection in SQLite)
PRAGMA foreign_keys = ON;

-- Add to db.py get_engine() or get_session():
-- event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))

-- FK constraints (add to schema if not present):
-- edge_evidence_v1.edge_relation_id → edge_relations_definitions_v1.edge_relation_id
-- edge_evidence_v1.upstream_instrument_id → instrument_definitions_v1.instrument_id
```

For controlled vocabularies (`effect_type_reported`, `rob_overall`, `effect_size_type`), SQLite cannot enforce CHECK constraints with enum tables. Instead, the validated writer must enforce these as a validation layer that fails inserts.

### INV-4: Semantic Uniqueness Constraint

Dedup by `span_hash` alone is unstable across PDF text variants. Add a semantic uniqueness key:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uix_evidence_semantic 
ON edge_evidence_v1(
    study_id, edge_relation_id, upstream_instrument_id, 
    effect_size_type, endpoint_vs_change
);
```

This prevents the "6 different beta values for the same conceptual result" problem. If a row with the same study×edge×instrument×type×endpoint already exists, the writer must UPDATE (not INSERT a duplicate).

### INV-5: Precision Cascade Is a Hard Contract

Every `edge_evidence_v1` row MUST have a derivable SE. The contract:

```
REQUIRED: se_raw IS NOT NULL
       OR (ci_low_reported IS NOT NULL AND ci_high_reported IS NOT NULL)
       OR (p_value IS NOT NULL AND effect_value_reported IS NOT NULL)
       OR (test_statistic IS NOT NULL — via conversion)
OTHERWISE: REJECT the row.
```

No row may enter the DB without an SE or the data to derive one. This is the only way to prevent P3 from dropping everything.

### INV-6: η²→d Conversion Guard

The formula `d = 2 × sqrt(η² / (1 − η²))` is valid ONLY when:
- The partial η² corresponds to a **2-level contrast** (df_numerator = 1)
- The effect is for a single between-group factor

If the source ANOVA has df₁ > 1 (e.g., 3-group comparison), repeated-measures structure, or multi-level factors, this conversion produces wrong values.

**Implementation rule**: The `standardize_effect_size()` function must:
1. Check that `effect_type_original = 'eta_sq_partial'` AND a `contrast_df1` field = 1 (or is unspecified for 2-group designs)
2. If `contrast_df1 > 1` or the design is ambiguous: mark `effect_type_original = 'cohen_d_approximate'` and set `conversion_bias_risk = 'HIGH'`
3. Campbell 2017 satisfies this guard: ANCOVA with group (exercise vs control) as 2-level factor, df₁=1.

### INV-7: Schema Gap — Missing Layer-Driving Columns

The `edge_evidence_v1` table lacks `study_design`, `cancer_type`, `pub_year`, and `treatment_phase` columns. These fields are required by the 7-layer calibration system (L1, L4, L5, L7).

**Resolution**: Either:
- **(A) Add columns to schema** via ALTER TABLE (preferred — keeps data co-located with evidence)
- **(B) Join through study_registry_v1** where these fields exist at study level (less flexible — can't vary per-edge)

Option A is recommended. Add these columns before implementing FIX-4:
```sql
ALTER TABLE edge_evidence_v1 ADD COLUMN study_design TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN cancer_type TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN treatment_phase TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN pub_year INTEGER;
ALTER TABLE edge_evidence_v1 ADD COLUMN cancer_validated TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN defaulted_fields_json TEXT;
```

---

## Fix Specifications

Fixes are dependency-ordered: Fix 1 must complete before Fix 2, etc.

---

### FIX-1: Unify Edge Definitions — Single Source of Truth

**Goal**: Eliminate the EDGE_*/ER_* split. One file defines edges. The seed loader reads from it.

**Implementation**:

**Step 1a** — Replace `crci/database/seeds/edge_relations.csv` with a file auto-generated from `registries/EDGE_REGISTRY.csv`.

Create `scripts/sync_edge_seeds.py`:
```python
"""
Reads registries/EDGE_REGISTRY.csv (authoritative, 138 rows, ER_* IDs)
Writes crci/database/seeds/edge_relations.csv (seed format)
Maps columns:
    REGISTRY                    SEED
    edge_relation_id         →  edge_relation_id     (keep ER_* IDs)
    source_node_id           →  node_x
    target_node_id           →  node_y
    relation_type            →  relation_type
    expected_sign            →  default_effect_direction  (positive→1, negative→-1)
    functional_form          →  default_temporal_family
    mechanism_description    →  canonical_statement
    primary_pathway          →  edge_family
    notes                    →  notes
    version                  →  version
    active                   →  active

Columns not in REGISTRY that SEED needs:
    module                   →  hardcode "A"
    relation_label           →  use edge_relation_id itself (deterministic, no free-text derivation)
    allowed_measure_ids_json →  empty string
    allowed_upstream_instruments_json → empty string
"""
```

**Step 1b** — Run `scripts/sync_edge_seeds.py` once. Verify output has 138 rows. Commit the regenerated seed CSV.

**Step 1c** — Add a CI/git hook or a startup check: if `registries/EDGE_REGISTRY.csv` has a newer mtime than `crci/database/seeds/edge_relations.csv`, warn and refuse to seed until sync is run.

**Critical detail**: The column mapping must handle `expected_sign`:
- `"positive"` → `1`
- `"negative"` → `-1`
- `"context_dependent"` → `0`
- Any other value → `0` + log warning

**Step 1d** — Make seed loader idempotent: Change `seed_loader.py` to use `INSERT OR REPLACE` (upsert) for edge definitions, so re-seeding updates existing rows rather than silently skipping or failing. This ensures dev resets and CI runs don't create divergence.

**Validation after fix**: 
```sql
SELECT COUNT(*) FROM edge_relations_definitions_v1;  -- should be 138
SELECT edge_relation_id FROM edge_relations_definitions_v1 LIMIT 3;  -- should start with ER_
```

---

### FIX-2: Add DB Persistence Protection

**Goal**: Prevent accidental data destruction. Setup scripts must never silently wipe evidence.

**Implementation**:

**Step 2a** — Create `scripts/db_guard.py`:
```python
"""
Functions:
  check_evidence_exists(engine) -> dict[str, int]
    Returns counts of rows in evidence tables:
      edge_evidence_v1, population_norms_v1, temporal_evidence_v1,
      instrument_evidence_v1, study_registry_v1
    
  guard_before_reset(engine) -> bool
    If any evidence table has data:
      - Print WARNING with exact counts
      - Print: "Run with --force to proceed (will destroy N evidence rows)"
      - Return False (block the operation)
    If no evidence: return True (allow)
    
  backup_db(db_path) -> Path
    Copy crci_dev.db to crci_dev.db.backup.{timestamp}
    Return backup path
"""
```

**Step 2b** — Modify `setup_complete.sh`: Add `python scripts/db_guard.py --check` before `DROP DATABASE`.

**Step 2c** — Modify `setup_database.py`: Import `db_guard.check_evidence_exists()`. If evidence exists and `--force` not provided, abort with message.

**Step 2d** — Modify `setup_sqlite.py`: Same guard.

**Step 2e** — Add to `load_evidence_into_db.py` verification step: After loading, print "Evidence loaded. Next DB setup will require --force to avoid data loss."

**Critical detail**: The guard checks evidence tables, NOT seed tables. Re-seeding node definitions is acceptable. Destroying edge_evidence rows is not.

---

### FIX-3: Expand CSV Template to Capture Algorithm-Required Fields

**Goal**: The edge_evidence template must capture every field the 7-layer system needs, plus every field the algorithm chain consumes.

**Implementation**:

**Step 3a** — Create `data/templates/edge_evidence_template_v2.csv` with these columns:

```
doi                        # Paper DOI (required)
edge_id                    # ER_* edge ID from EDGE_REGISTRY.csv (required)
beta_raw                   # Effect size value as reported (required)
se_raw                     # Standard error of effect size (required if available)
ci_low                     # 95% CI lower bound (required if se_raw not available)
ci_high                    # 95% CI upper bound (required if se_raw not available)
p_value                    # p-value (optional, used for SE derivation fallback)
effect_type_original       # What paper reports: cohen_d, mean_diff, odds_ratio, hazard_ratio, r, eta_sq_partial (required)
effect_size_type           # BETWEEN_GROUP, WITHIN_GROUP, PRE_POST_CHANGE (required)
sample_size                # Total N in analysis (required)
n_treatment                # N in treatment arm (required for RCTs)
n_control                  # N in control arm (required for RCTs)
sd_treatment               # SD in treatment arm (required if effect_type is mean_diff)
sd_control                 # SD in control arm (required if effect_type is mean_diff)
study_design               # RCT, cohort, cross_sectional, etc. (required for L1)
cancer_type                # breast, mixed, etc. (required for context matching)
treatment_phase            # active_treatment, early_recovery, etc. (required for context matching)
instrument_id              # INST_* from INSTRUMENT_REGISTRY.csv (required for L4, measurement model)
cancer_validated           # yes, no, unknown (required for L4)
rob_overall                # low, moderate, high, critical (required for L5/GRADE)
pub_year                   # Publication year (required for L7 freshness)
covariates_adjusted        # Comma-separated list of adjusted covariates (recommended)
endpoint_vs_change         # endpoint, change_score (recommended)
comparison_arm_label       # usual_care, waitlist, active_control (recommended)
se_derivation_method       # direct, from_ci, from_p, from_f_stat, borrowed (required)
shared_control_flag        # 0 or 1 — does this share a control group with another row? (required)
confidence_note            # Free-text notes (optional)
```

**Step 3b** — Update the EXTRACTION_PLAYBOOK.md Step 3 to reference v2 template and explain each new field.

**Step 3c** — Migration: Existing CSVs in `data/manual_uploads/structured/` must be updated to v2 format. Add the missing columns from the meta.json and paper data.

**Critical details for new fields:**

- `se_derivation_method`: MUST be one of `{direct, from_ci, from_p, from_f_stat, from_eta_sq, borrowed_sd}`. This feeds `se_derivation_level` in the DB, which affects trust weighting.
- `sd_treatment` / `sd_control`: REQUIRED when `effect_type_original` is any raw mean difference. Without them, standardization is impossible.
- `cancer_validated`: Maps directly to L4 `cancer_validation_status`. Values: `"yes"` → `VALIDATED_CANCER` (m=1.0), `"no"` → `GENERAL_POPULATION` (m=1.3), `"unknown"` → `USED_IN_CANCER` (m=1.15)
- `rob_overall`: Maps to L5 GRADE quality. `"low"` → `HIGH` (m=1.0), `"moderate"` → `MODERATE` (m=1.25), `"high"` → `LOW` (m=1.50), `"critical"` → `VERY_LOW` (m=2.0)
- `pub_year`: Used directly by L7 freshness: w = max(0.70, 1 − 0.015 × (2025 − pub_year))

---

### FIX-4: Build Unified Evidence Writer with Validation

**Goal**: A single function that all write paths call. Validates incoming data, rejects bad rows, and maps ALL columns to the DB.

**Implementation**:

Create `crci/extraction/validated_evidence_writer.py`:

```python
"""
SINGLE write path for edge_evidence_v1.

All three entry points MUST call this:
  1. evidence_writer.py (LLM pipeline path)
  2. manual_upload_watcher.py (CSV manual import path)
  3. load_evidence_into_db.py (bulk loader path)

Functions:
  validate_evidence_row(row: dict) -> tuple[bool, list[str]]
    Checks:
    - edge_id exists in edge_relations_definitions_v1
    - instrument_id exists in instrument_definitions_v1  
    - effect_type_original is valid enum
    - effect_size_type is valid enum
    - study_design is valid enum
    - cancer_type is valid enum
    - treatment_phase is valid enum
    - se_raw OR (ci_low AND ci_high) OR p_value present (precision cascade)
    - sample_size > 0
    - If effect_type_original is mean_diff_*, then sd_treatment + sd_control present
    - rob_overall is valid enum
    - pub_year is integer 1990-2026
    Returns: (is_valid, list_of_error_messages)

  standardize_effect_size(row: dict) -> dict
    If effect_type_original is NOT cohen_d or log_or:
      - If mean_diff + SDs available: compute Cohen's d
        d = (mean_diff) / SD_pooled
        SD_pooled = sqrt((SD_tx² + SD_ctrl²) / 2)
        se_d = sqrt(1/n_tx + 1/n_ctrl + d²/(2*(n_tx+n_ctrl)))
      - If eta_sq_partial available:
        d = 2 * sqrt(eta_sq / (1 - eta_sq))
      - If odds_ratio:
        d = ln(OR) * sqrt(3) / pi
      Store original in effect_type_reported, standardized in harmonized_beta
    Returns: row with harmonized_beta, harmonized_se populated

  derive_se(row: dict) -> dict
    Precision cascade:
      Level 1: SE directly reported → se_derivation_level = "L1_DIRECT"
      Level 2: SE from CI → SE = (CI_high - CI_low) / (2 * 1.96) → "L2_FROM_CI"
      Level 3: SE from p-value → SE = |beta| / z_from_p → "L3_FROM_P"
      Level 4: SE from F/t stat → SE = |beta| / sqrt(F) → "L4_FROM_F"
      Level 5: SE borrowed from SD anchors → "L5_BORROWED"
    Returns: row with se_reported, se_derivation_level populated

  compute_layer_inputs(row: dict) -> dict
    From the validated row, compute fields the 7-layer system needs:
    - study_design → directly usable by L1
    - cancer_validated → map to VALIDATED_CANCER/USED_IN_CANCER/GENERAL_POPULATION for L4
    - rob_overall → map to HIGH/MODERATE/LOW/VERY_LOW GRADE for L5
    - pub_year → directly usable by L7
    Returns: row with all layer-input fields populated

  write_validated_row(session, row: dict) -> str
    After validation + standardization + SE derivation + layer input computation:
    - Generate deterministic ler_id from span_hash
    - Check for duplicates (study_id × edge_id × profile_id)
    - INSERT or UPDATE the row
    - Populate ALL 96 columns that have data
    Returns: ler_id of written/updated row
"""
```

**Critical implementation rules:**

1. **Reject for layer-driving fields, default+log for non-calibration fields.** See INV-1 for the exact split. If `study_design`, `rob_overall`, `pub_year`, `instrument_id`, `cancer_validated`, or `sample_size` is missing → REJECT. If `covariates_adjusted`, `comparison_arm_label`, or `endpoint_vs_change` is missing → default to safe value + log + write field name to `defaulted_fields_json`.
   
2. **Standardize at write time.** All raw mean differences must be converted to Cohen's d BEFORE entering the DB. The `effect_type_reported` column stores the original type; `harmonized_beta` stores the standardized value. This prevents the incommensurable-scales problem. For η²→d conversions, enforce INV-6 (df₁=1 guard).

3. **Precision cascade is a hard contract (INV-5).** If direct SE is available, use it (Level 1). Otherwise, try CI→SE, then p→SE, then F→SE. If NO SE can be derived → REJECT the row. Document which level was used in `se_derivation_level`. No row may enter the DB without an SE.

4. **Enforce semantic uniqueness (INV-4).** Before INSERT, check the uniqueness index `(study_id, edge_relation_id, upstream_instrument_id, effect_size_type, endpoint_vs_change)`. If a match exists, UPDATE the existing row. Never create duplicate conceptual results.

---

### FIX-5: Implement Missing Family Importers

**Goal**: Load population_norms, context_priors, temporal_evidence, and instrument_evidence CSVs into their respective DB tables.

**Implementation**:

Create `crci/extraction/family_importers.py`:

```python
"""
Importers for parameter families F2-F4, F6.
Each function: validate CSV row → map columns → INSERT into target table.

  import_population_norm(session, row: dict) -> str
    CSV columns: doi, node_id, instrument_id, mean, sd, sample_size,
                 cancer_type, treatment_phase, age_range
    DB table: population_norms_v1
    DB columns: id (UUID), study_id (from DOI lookup), node_id, instrument_id,
                mean_raw, sd_raw, N, cancer_type, treatment_phase,
                provenance_status="manual", created_at, version=1
    Validation:
      - node_id exists in biomarker_node_definitions_v1
      - instrument_id exists in instrument_definitions_v1
      - sd > 0
      - sample_size > 0

  import_context_prior(session, row: dict) -> str
    CSV columns: doi, node_id, cancer_type, treatment_phase,
                 prior_mean_z, prior_sd_z, source_type, n_contributing, notes
    DB table: node_priors_v1
    DB columns: prior_id (UUID), node_id, prior_space="z_score",
                mean (= prior_mean_z), sd (= prior_sd_z),
                dist_family="normal", cancer_type, treatment_phase,
                provenance="manual:{doi}", active=1, version=1, notes
    Validation:
      - node_id exists in biomarker_node_definitions_v1
      - prior_sd_z > 0
      - source_type is one of {published_norm_comparison, local_control_group,
        domain_expert_estimate, population_registry}

  import_temporal_evidence(session, row: dict) -> str
    CSV columns: doi, edge_id, timepoint_weeks, value, se,
                 is_recovery, sample_size, provenance_ref
    DB table: temporal_evidence_v1
    DB columns: id (UUID), study_id (from DOI), action_id (from edge→action mapping),
                timepoint_weeks, effect (= value), se, is_recovery, N (= sample_size),
                provenance_status="manual", provenance_ref, created_at, version=1
    Validation:
      - edge_id exists in edge_relations_definitions_v1
      - timepoint_weeks >= 0
      - sample_size > 0
      - Multiple rows per edge expected (one per timepoint)

  import_instrument_evidence(session, row: dict) -> str
    CSV columns: doi, instrument_id, reliability_value, reliability_type,
                 factor_loading_mean, test_retest_icc, sample_size,
                 cancer_type, cancer_validated, provenance_ref
    DB table: instrument_evidence_v1
    DB columns: id (UUID), study_id (from DOI), instrument_id,
                cronbachs_alpha (if reliability_type=internal_consistency),
                test_retest_reliability (if reliability_type=test_retest),
                N (= sample_size), cancer_type, provenance_ref,
                provenance_status="manual", created_at, version=1
    Validation:
      - instrument_id exists in instrument_definitions_v1
      - reliability_value in (0, 1)
      - reliability_type in {internal_consistency, test_retest, inter_rater, split_half}
"""
```

**Step 5b** — Wire into `manual_upload_watcher.py`:  Replace the `logger.warning("not yet implemented")` stubs with calls to these importers.

**Step 5c** — Wire into `load_evidence_into_db.py`: Add Step 3b (population_norms), Step 3c (context_priors), Step 3d (temporal), Step 3e (instrument) after the existing edge evidence loading.

---

### FIX-6: Add Per-Paper Extraction Report

**Goal**: After extracting a paper (manually or via LLM), generate a completeness report that flags gaps.

**Implementation**:

Create `crci/extraction/completeness_checker.py`:

```python
"""
Generates per-paper extraction completeness report.

  check_paper_completeness(session, study_id: str) -> ExtractionReport
    
    ExtractionReport contains:
      study_id: str
      study_design: str (from study_registry_v1)
      expected_families: list[str]  # F1, F3, F4, F6 for RCTs
      populated_families: dict[str, int]  # family → row count
      missing_families: list[str]  # expected but 0 rows
      
      edge_evidence_issues: list[str]
        - "4 of 8 edges have effect_type 'mean_diff_*' — not standardized to SMD"
        - "0 of 8 edges have rob_overall populated"
        - "0 of 8 edges have cancer_type populated"
        - "N_effect = 0 for 30 rows"
        
      column_coverage: dict[str, float]  # column_name → % populated
      
      layer_readiness: dict[str, str]  # L1-L7 → "READY" / "WILL_DEFAULT"
        - L1: "WILL_DEFAULT: study_design not populated → m_design=3.0"
        - L4: "WILL_DEFAULT: cancer_validation_status not populated → m_scale=1.30"
        
      completeness_score: float  # 0.0 to 1.0
      
      family_ready: dict[str, bool]  # F1→True/False, F3→True/False, etc.
        # Gate: if ANY expected family has family_ready=False, the paper
        # is NOT ready for algorithm chain. This is a blocking boolean,
        # not just a score.
      
      blocking_issues: list[str]  # Things that MUST be fixed before valid analysis
        - "effect sizes in mixed units — standardize before pooling"
        - "0 population norms — context priors will use N(0,1) default"

  write_completeness_row(session, report: ExtractionReport)
    Write to extraction_completeness_v1 table for tracking.

  print_report(report: ExtractionReport) -> str
    Human-readable formatted report for CLI output.
```

**Step 6b** — Add completeness check to `run_manual_import.py`: After importing CSVs, automatically run `check_paper_completeness()` for each study and print the report.

**Step 6c** — Add completeness check to `run_extraction.py`: After LLM pipeline completes, run the same check and store results.

---

### FIX-7: Fix Campbell 2017 Effect Sizes — Convert to Cohen's d

**Goal**: All 4 Campbell evidence rows must be converted from raw mean differences to standardized effect sizes before entering the DB.

**Implementation**:

Update Campbell's `edge_evidence_template.csv` using the v2 template:

**TMT-A** (processing speed):
- Raw: mean_diff = -14.2 seconds, SE = 5.28, partial η² = 0.35
- From η²: d = 2 × sqrt(0.35 / 0.65) = 1.47 (exercise benefit; already negative direction for TMT where lower = better)
- SE of d: SE_d = sqrt(1/10 + 1/9 + 1.47²/(2 × 19)) ≈ 0.55
- New row: `beta_raw=1.47, se_raw=0.55, effect_type_original=cohen_d_from_eta_sq, se_derivation_method=from_eta_sq`
- Note: Sign direction requires care. TMT-A: lower = better. Exercise group improved (went down). Edge `ER_ACTIVITY_PROC_SPEED` expected_sign = positive (more activity → better speed). So d should be positive: d = +1.47.

**Animal Naming** (verbal fluency):
- Raw: mean_diff = +3.0 words, SE = 2.14, partial η² = 0.13
- From η²: d = 2 × sqrt(0.13 / 0.87) = 0.77
- SE of d: ≈ 0.51
- New row: `beta_raw=0.77, se_raw=0.51, effect_type_original=cohen_d_from_eta_sq`

**HVLT-R** (episodic memory):
- Raw: mean_diff = -1.5, SE = 2.48, partial η² = 0.03
- From η²: d = 2 × sqrt(0.03 / 0.97) = 0.35
- Note: Negative direction (exercise worse), so d = -0.35
- SE of d: ≈ 0.47

**FACT-Cog PCI** (cognitive complaints):
- Raw: mean_diff = +3.9, SE = 5.33, partial η² = 0.04
- From η²: d = 2 × sqrt(0.04 / 0.96) = 0.41
- FACT-Cog: higher = better (fewer complaints). Edge expected_sign = negative (more activity → fewer complaints). Positive d means improvement, which aligns with positive sign for FACT-Cog direction.
- SE of d: ≈ 0.47

**Critical details:**
- Every converted value MUST retain `effect_type_original=cohen_d_from_eta_sq` (not `cohen_d` — it's derived, not direct)
- `se_derivation_method=from_eta_sq` 
- `confidence_note` must document the conversion: "Converted from partial η²=0.35 using d = 2√(η²/(1−η²)). ANCOVA 2-level group factor, df1=1."
- Original raw values should be preserved in the `confidence_note` field
- **INV-6 guard**: Campbell's ANCOVA uses exercise vs control (2-level, df₁=1), so the conversion is valid. For future papers, verify df₁=1 before applying this formula. If df₁ > 1, mark as `cohen_d_approximate` with `conversion_bias_risk = 'HIGH'`.

---

### FIX-8: Fill Missing Templates for Both Papers

**Goal**: Fill temporal_evidence and instrument_evidence templates for Cherrier 2013 and Campbell 2017.

**Implementation**:

**Temporal evidence (Campbell 2017):**

```csv
doi,edge_id,timepoint_weeks,value,se,is_recovery,sample_size,provenance_ref
10.1002/pon.4370,ER_ACTIVITY_PROC_SPEED,0,0.0,0.0,0,19,Table 2 baseline
10.1002/pon.4370,ER_ACTIVITY_PROC_SPEED,24,1.47,0.55,0,19,Table 2 post-intervention
10.1002/pon.4370,ER_ACTIVITY_VERBAL_FLUENCY,0,0.0,0.0,0,19,Table 2 baseline
10.1002/pon.4370,ER_ACTIVITY_VERBAL_FLUENCY,24,0.77,0.51,0,19,Table 2 post-intervention
10.1002/pon.4370,ER_ACTIVITY_EPIMEM,0,0.0,0.0,0,19,Table 2 baseline
10.1002/pon.4370,ER_ACTIVITY_EPIMEM,24,-0.35,0.47,0,19,Table 2 post-intervention
10.1002/pon.4370,ER_ACTIVITY_COG_COMPLAINTS,0,0.0,0.0,0,19,Table 2 baseline
10.1002/pon.4370,ER_ACTIVITY_COG_COMPLAINTS,24,0.41,0.47,0,19,Table 2 post-intervention
```

**Temporal evidence (Cherrier 2013):**

```csv
doi,edge_id,timepoint_weeks,value,se,is_recovery,sample_size,provenance_ref
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_WORKMEM,0,0.0,0.0,0,28,Table baseline
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_WORKMEM,7,0.79,0.38,0,28,Table post
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_ATTN,0,0.0,0.0,0,28,Table baseline
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_ATTN,7,0.59,0.38,0,28,Table post
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_COGCOMPLAINTS,0,0.0,0.0,0,28,Table baseline
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_COGCOMPLAINTS,7,-0.53,0.38,0,28,Table post
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_EPIMEM,0,0.0,0.0,0,28,Table baseline
10.1016/j.lfs.2013.08.011,ER_COGACTIVITY_EPIMEM,7,0.25,0.38,0,28,Table post
```

**Instrument evidence — data to extract from papers or published norms:**

Both papers use instruments with published psychometric data. Populate from either (a) the paper itself if reliability is reported, or (b) the instrument's published validation study.

```csv
doi,instrument_id,reliability_value,reliability_type,factor_loading_mean,test_retest_icc,sample_size,cancer_type,cancer_validated,provenance_ref
# Cherrier 2013 instruments
10.1016/j.lfs.2013.08.011,INST_DIGIT_SPAN,0.90,internal_consistency,,0.83,28,mixed,yes,WAIS-III manual
10.1016/j.lfs.2013.08.011,INST_FACTCOG_PCI,0.95,internal_consistency,,,28,mixed,yes,Wagner 2009
10.1016/j.lfs.2013.08.011,INST_HVLTR,0.74,test_retest,,0.74,28,mixed,yes,Benedict 1998
# Campbell 2017 instruments
10.1002/pon.4370,INST_TMT_B,0.89,test_retest,,0.89,19,breast,yes,Strauss 2006
10.1002/pon.4370,INST_COWAT,0.83,test_retest,,0.83,19,breast,yes,Strauss 2006
10.1002/pon.4370,INST_HVLTR,0.74,test_retest,,0.74,19,breast,yes,Benedict 1998
10.1002/pon.4370,INST_FACTCOG_PCI,0.95,internal_consistency,,,19,breast,yes,Wagner 2009
10.1002/pon.4370,INST_CESD,0.85,internal_consistency,,,19,breast,yes,Radloff 1977
10.1002/pon.4370,INST_FACIT_FATIGUE,0.93,internal_consistency,,,19,breast,yes,Yellen 1997
```

**Critical detail**: Reliability values sourced from published norms (not the specific paper) must have `provenance_ref` citing the source (e.g., "WAIS-III manual", "Wagner 2009"). The `provenance_status` should be set to `"published_norm"` not `"manual"` to distinguish them from paper-specific reporting.

---

## Execution Sequence

Fixes must be executed in this order due to dependencies:

```
FIX-1 (edge unification) + INV-3 (FK constraints) + INV-7 (schema ALTER)
  └─→ FIX-2 (persistence guard)
        └─→ FIX-4 skeleton (validated writer: validation + precision cascade + INV-1/4/5/6)
              └─→ FIX-3 (expanded template — designed to match writer contract)
                    └─→ FIX-7 (convert Campbell effects using writer's standardize_effect_size)
                    └─→ FIX-8 (fill missing templates)
                          └─→ FIX-4 full (expand writer column mappings for all v2 fields)
                                └─→ FIX-5 (family importers)
                                      └─→ FIX-6 (completeness checker)
```

**Rationale:**
- FIX-1 must be first because all downstream writes need correct edge IDs
- INV-3 + INV-7 add FK constraints and missing schema columns — prerequisite for any data writes
- FIX-2 protects the DB so subsequent work isn't destroyed
- FIX-4 skeleton comes BEFORE FIX-3/7/8: build the ingestion contract first, then design the template and data to fit it (avoids reformatting data after discovering the validator needs different fields)
- FIX-3 template v2 is designed to match the writer's validated fields
- FIX-7/8 fix actual data using the writer's conversion functions
- FIX-4 full expands column mappings once template is stable
- FIX-5 and FIX-6 come last — they depend on the writer and template being stable

---

## Validation Checklist

After all fixes are applied, run these verification queries. ALL must pass.

### V1 — Edge Definition Unity
```sql
-- All edge IDs start with ER_
SELECT COUNT(*) FROM edge_relations_definitions_v1 
WHERE edge_relation_id NOT LIKE 'ER_%';
-- Expected: 0

-- Count matches EDGE_REGISTRY.csv
SELECT COUNT(*) FROM edge_relations_definitions_v1;
-- Expected: 138

-- Seed CSV matches registry
-- Run: diff <(cut -d, -f1 crci/database/seeds/edge_relations.csv | sort) \
--           <(cut -d, -f1 registries/EDGE_REGISTRY.csv | sort)
-- Expected: only header difference
```

### V2 — Evidence Column Coverage
```sql
-- No UNASSIGNED edge IDs (INV-2)
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE edge_relation_id = 'UNASSIGNED' OR edge_relation_id IS NULL;
-- Expected: 0

-- All evidence rows have N > 0
SELECT COUNT(*) FROM edge_evidence_v1 WHERE N_effect IS NULL OR N_effect = 0;
-- Expected: 0

-- All effect sizes are standardized (checking effect_type_reported)
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE effect_type_reported NOT IN ('cohen_d', 'cohen_d_from_eta_sq', 'log_or', 'harmonized_beta');
-- Expected: 0 (no raw mean_diff values should remain)

-- study_design populated for all rows (column added by INV-7)
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE study_design IS NULL OR study_design = '';
-- Expected: 0

-- rob_overall populated for all rows
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE rob_overall IS NULL OR rob_overall = '';
-- Expected: 0

-- Instrument ID populated for manual entries
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE entered_by LIKE 'manual%' AND upstream_instrument_id IS NULL;
-- Expected: 0

-- SE derivable for every row (INV-5)
SELECT COUNT(*) FROM edge_evidence_v1
WHERE se_reported IS NULL 
  AND harmonized_se IS NULL
  AND (ci_low_reported IS NULL OR ci_high_reported IS NULL)
  AND p_value IS NULL;
-- Expected: 0

-- FK integrity: all edge IDs exist in definitions
SELECT COUNT(*) FROM edge_evidence_v1 e
LEFT JOIN edge_relations_definitions_v1 d ON e.edge_relation_id = d.edge_relation_id
WHERE d.edge_relation_id IS NULL;
-- Expected: 0
```

### V3 — Multi-Family Coverage
```sql
-- Population norms loaded
SELECT COUNT(*) FROM population_norms_v1;
-- Expected: >= 9

-- Context priors loaded  
SELECT COUNT(*) FROM node_priors_v1;
-- Expected: >= 7

-- Temporal evidence loaded
SELECT COUNT(*) FROM temporal_evidence_v1;
-- Expected: >= 16

-- Instrument evidence loaded
SELECT COUNT(*) FROM instrument_evidence_v1;
-- Expected: >= 9
```

### V4 — Layer Readiness
```python
# Run this Python check after loading:
from crci.extraction.p3_heterogeneity.layers import apply_all_layers

# Create a mock record from an evidence row
# Verify: m_design != 3.0 (not defaulting to unclassified)
# Verify: m_scale != 1.30 (not defaulting to general_population)  
# Verify: w_fresh != 0.85 (not defaulting to unknown pub_year)
```

### V5 — Effect Size Standardization
```sql
-- No raw mean differences in evidence
SELECT edge_relation_id, effect_type_reported, effect_value_reported 
FROM edge_evidence_v1 
WHERE effect_type_reported LIKE 'mean_diff%';
-- Expected: 0 rows

-- All harmonized_beta values are in plausible SMD range (-3 to +3)
SELECT COUNT(*) FROM edge_evidence_v1 
WHERE harmonized_beta IS NOT NULL 
AND (harmonized_beta < -5 OR harmonized_beta > 5);
-- Expected: 0
```

### V6 — Persistence Guard
```bash
# Attempt DB reset — should be BLOCKED
python scripts/setup_database.py --init --seed
# Expected output: "WARNING: Evidence data exists (N rows). Use --force to proceed."
# Expected exit code: 1 (blocked)
```
