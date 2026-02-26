# Persistence Fix Changelog

**Started:** 2026-02-26  
**Goal:** Fix study identity and evidence persistence to enable idempotent reruns

---

## S0: ORM↔DB Column Verification

**Status:** 🔄 In Progress

### Checks:
- [ ] `study_registry_v1` ORM matches SQLite schema
- [ ] `edge_evidence_v1` ORM matches SQLite schema
- [ ] `extraction_run_id` provenance confirmed

---

## S1: Deterministic study_id

**Status:** ⏳ Pending

### Changes:
- [ ] Create `compute_study_id()` function
- [ ] Add `doi_normalized` column to schema
- [ ] Create unique indexes on DOI/PMID/PMCID
- [ ] Update `p0_triage/runner.py` to use new function

---

## S2: study_registry UPSERT

**Status:** ⏳ Pending

### Changes:
- [ ] Replace INSERT with INSERT OR REPLACE
- [ ] Ensure update preserves audit fields

---

## S3: evidence_writer UPSERT

**Status:** ⏳ Pending

### Changes:
- [ ] Derive `span_id` deterministically (not UUID)
- [ ] Create unique index on `(study_id, edge_relation_id, profile_id, span_id)`
- [ ] Replace INSERT with UPSERT

---

## S4: E2E Integration Test

**Status:** ⏳ Pending

### Tests:
- [ ] Same paper twice → no duplicate rows
- [ ] Updated extraction → updates existing rows
- [ ] Transaction boundaries work correctly

---

## Change Log

| Date | File | Change | Notes |
|------|------|--------|-------|
