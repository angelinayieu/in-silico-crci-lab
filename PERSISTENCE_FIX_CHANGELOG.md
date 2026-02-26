# Persistence Fix Changelog

**Started:** 2026-02-26  
**Completed:** 2026-02-26  
**Goal:** Fix study identity and evidence persistence to enable idempotent reruns

---

## S0: ORM↔DB Column Verification ✅

**Status:** ✅ Complete

### Checks:
- [x] `study_registry_v1` ORM matches SQLite schema (23 columns)
- [x] `edge_evidence_v1` ORM matches SQLite schema (95 columns)
- [x] No mismatches found

---

## S1: Deterministic study_id ✅

**Status:** ✅ Complete

### Changes:
- [x] Created `crci/shared/study_identity.py` with:
  - `compute_study_id()` — DOI→PMID→PMCID→hash priority
  - `normalize_doi()` — lowercase, strip prefixes
  - `normalize_title()` — for hash fallback
  - `check_duplicate_study()` — dedup lookup
- [x] Added `doi_normalized` column to `study_registry_v1`
- [x] Added `id_source` column to track how study_id was derived
- [x] Created unique indexes:
  - `idx_study_doi_normalized_unique`
  - `idx_study_pmid_unique`
  - `idx_study_pmcid_unique`
- [x] Updated `p0_triage/runner.py` to use deterministic IDs

---

## S2: study_registry UPSERT ✅

**Status:** ✅ Complete

### Changes:
- [x] `p0_triage/runner.py` now queries for existing study before insert
- [x] If study exists, updates relevant fields
- [x] If new, inserts with `doi_normalized` and `id_source`
- [x] Sets `context["is_rerun"]` flag for downstream awareness

---

## S3: evidence_writer UPSERT ✅

**Status:** ✅ Complete

### Changes:
- [x] Created `compute_span_hash()` — deterministic hash from (study_id, edge_id, profile_id, beta, se)
- [x] Added `span_hash` column to `edge_evidence_v1`
- [x] Created `idx_evidence_dedup` unique index
- [x] `ler_id` now deterministic: `LER_{study_id}_{span_hash}`
- [x] UPSERT: checks if row exists, updates if found, inserts otherwise
- [x] Tracks `written`, `updated`, `skipped` counts

---

## S4: E2E Integration Test ✅

**Status:** ✅ Complete (13/13 tests pass)

### Tests:
- [x] `TestStudyIdentity` — DOI normalization, priority order, determinism
- [x] `TestEvidenceDedup` — span_hash determinism
- [x] `TestDatabaseConstraints` — unique indexes and new columns exist

---

## Change Log

| Date | File | Change | Notes |
|------|------|--------|-------|
| 2026-02-26 | `crci/shared/study_identity.py` | Created | Deterministic study_id computation |
| 2026-02-26 | `crci/shared/study_identity.py` | Updated | Added filename conversion helpers |
| 2026-02-26 | `crci/database/schema/011_study_identity.sql` | Created | Migration for new columns + indexes |
| 2026-02-26 | `crci/shared/models/tables.py` | Modified | Added `doi_normalized`, `id_source`, `span_hash` |
| 2026-02-26 | `crci/extraction/p0_triage/runner.py` | Modified | Use `compute_study_id()`, UPSERT semantics |
| 2026-02-26 | `crci/extraction/evidence_writer.py` | Modified | Add `compute_span_hash()`, UPSERT semantics |
| 2026-02-26 | `tests/test_persistence_idempotency.py` | Created | 13 tests for persistence correctness |

---

## Summary

**Before:** Re-running extraction on the same paper created duplicate rows because:
- `study_id` was `STUDY_{random_uuid}` — different every run
- `ler_id` was `LER_{study_id}_{random_uuid}` — different every run
- No unique constraints on DOI/PMID/PMCID

**After:** Idempotent extraction because:
- `study_id` is deterministic: `doi:X`, `pmid:Y`, or `hash:Z`
- `ler_id` is deterministic: `LER_{study_id}_{span_hash}`
- Unique indexes prevent accidental duplicates
- UPSERT semantics update existing rows on rerun

---

## ⚠️ CONSISTENCY ISSUES — Action Required

The following files/docs reference the **OLD** `STUDY_*` ID format and need updates:

### 1. Manual Scripts (MUST UPDATE)
| File | Legacy IDs | New Format |
|------|-----------|------------|
| `scripts/load_evidence_into_db.py` | `STUDY_CHERRIER_2013`, `STUDY_CAMPBELL_2017` | `doi:10.1016/j.lfs.2013.08.011`, `doi:10.1002/pon.4370` |
| `scripts/manual_cherrier_entry.py` | `CHERRIER2013`, `LER_CHERRIER2013_*` | `doi:10.1016/j.lfs.2013.08.011`, `LER_doi:..._{hash}` |

### 2. Documentation (UPDATE REFS)
| File | References |
|------|-----------|
| `docs/RETRIEVAL_PIPELINE_TEST_RESULTS.md` | `STUDY_CIFU_2018` |
| `docs/PERSISTENCE_GAP_REMEDIATION.md` | Old `LER_{study_id}_{span_id}_{uuid}` format |
| `EXTRACTION_LOG.md` | References to manual entry scripts |

### 3. Database Rows (ALREADY MIGRATED)
Current database uses new format: `hash:1a19634d5552fb63`

### Migration Strategy

**For manual data entry scripts:**
```python
# OLD (deprecated)
study_id = "STUDY_CHERRIER_2013"

# NEW (use compute_study_id)
from crci.shared.study_identity import compute_study_id
study_id, _ = compute_study_id({"doi": "10.1016/j.lfs.2013.08.011"})
# Returns: "doi:10.1016/j.lfs.2013.08.011"
```

**For ler_id in manual data:**
```python
# OLD (deprecated)
ler_id = "LER_CHERRIER2013_ATTENTION"

# NEW (use compute_span_hash)from crci.extraction.evidence_writer import compute_span_hash
span_hash = compute_span_hash(study_id, edge_id, profile_id, beta, se)
ler_id = f"LER_{study_id}_{span_hash}"
```

### Recommended Next Steps

1. **[HIGH]** Update `load_evidence_into_db.py` to use `compute_study_id()`
2. **[HIGH]** Update or deprecate `manual_cherrier_entry.py`
3. **[MEDIUM]** Update docs to reference new ID format
4. **[LOW]** Add migration script for any legacy rows still in DB

---

## ⚠️ FILESYSTEM NAMING CONFLICT

**Master Spec §9.3 (line 914-922)** specifies file naming as:
```
├── {study_id}.pdf
├── {study_id}.json
├── {study_id}.txt
├── {study_id}_papermap.json
```

**Problem:** New `study_id` format uses `:` and `/` characters:
- `doi:10.1016/j.lfs.2013.08.011` → **Invalid filename on Windows** (`:` forbidden)
- Also problematic on Unix (looks like paths)

**Resolution Options:**

| Option | Example | Pros | Cons |
|--------|---------|------|------|
| **A: URL-encode for files** | `doi%3A10.1016%2Fj.lfs.2013.08.011.pdf` | Reversible, DB stays clean | Ugly filenames |
| **B: Safe delimiter for files** | `doi--10.1016--j.lfs.2013.08.011.pdf` | Readable | Need encode/decode logic |
| **C: Hash-only for files** | `hash-1a19634d5552fb63.pdf` | Always safe | Loses human readability |
| **D: Dual ID system** | DB: `doi:X`, File: `{hash}.pdf` with lookup | Clean separation | More complexity |

**Recommendation:** Option B or D. Add a `to_filename()` helper in `study_identity.py`:

```python
def study_id_to_filename(study_id: str) -> str:
    """Convert study_id to filesystem-safe string."""
    return study_id.replace(":", "--").replace("/", "__")

def filename_to_study_id(filename: str) -> str:
    """Reverse conversion."""
    return filename.replace("--", ":").replace("__", "/")
```

**Status:** ✅ **IMPLEMENTED** in `crci/shared/study_identity.py`

Example:
```
doi:10.1016/j.lfs.2013.08.011 → doi--10.1016__j.lfs.2013.08.011.pdf
```

---

## ⚠️ DATABASE INDEX STATE

**Issue Found:** ORM-based setup (e.g., `setup_database.py`) creates columns
automatically from `tables.py`, but unique indexes from `011_study_identity.sql`
are NOT applied — the ORM doesn't know about constraint indexes.

**Tests affected:** 2 of 13 tests failed when indexes were missing:
- `test_study_registry_unique_indexes_exist`
- `test_edge_evidence_unique_index_exists`

**Fix applied:** Manually ran CREATE UNIQUE INDEX statements via sqlite3.

**For future setups**, either:
1. Run `sqlite3 crci_dev.db < crci/database/schema/011_study_identity.sql`, or
2. Add `Index()` declarations to ORM model in `tables.py` (preferred long-term)
