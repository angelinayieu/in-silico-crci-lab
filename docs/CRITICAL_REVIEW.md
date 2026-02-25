# CRCI System — Rigorous Critical Review

**Date**: 2025-02-26  
**Updated**: 2025-02-26 (Phase A+B+C partial complete)  
**Scope**: End-to-end audit of extraction, retrieval, data, tracking, and researcher workflow  
**Original Verdict**: The mechanical plumbing works. Zero usable output has been produced.  
**Current Verdict**: 8 evidence rows loaded. Retrieval bugs fixed. Researcher CLI built. 129/137 edges still need evidence.

---

## Executive Summary

After debugging 9 extraction pipeline bugs and testing all 5 retrieval adapters, the system's code *runs*. But the database contains **zero evidence rows**. The 8 manually extracted edges sit in CSV files that cannot be loaded (the importer is a stub, and the edge IDs don't match). The single "retrieved PDF" is actually an HTML page. There is no researcher-facing tracking, approval, or visibility infrastructure. The system cannot produce a single recommendation in its current state.

---

## Question-by-Question Assessment

### 1. "Where are the results we ended up extracting?"

**Answer: Nowhere usable.**

| Location | What's there | Status |
|---|---|---|
| `edge_evidence_v1` table | 0 rows | EMPTY |
| `extraction_runs` table | 0 rows | EMPTY |
| `study_registry_v1` | 1 row (Cifu 2018 only) | Stub — SR, no direct evidence |
| `data/manual_uploads/structured/10.1002_pon.4370/` | 4 edges (Campbell 2017) | CSV on disk, NOT in DB |
| `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/` | 4 edges (Cherrier 2013) | CSV on disk, NOT in DB |
| `scripts/manual_cherrier_entry.py` | Direct SQL insert script | EXISTS but was never executed |

**Why the CSVs can't be loaded even if someone tried:**

1. **The importer is a stub.** `manual_upload_watcher.py` line ~162: `import_structured_csv()` ends with:
   ```python
   logger.info("Would import %d rows into evidence table for template '%s'", ...)
   ```
   It logs a message and returns. It never writes to the database.

2. **Edge ID naming mismatch.** The CSVs use `ER_ACTIVITY_PROC_SPEED`, `ER_COGACTIVITY_WORKMEM` etc. The database's `edge_relations_definitions_v1` table uses `EDGE_EXERCISE_FATIGUE`, `EDGE_SLEEP_COGNITION` etc. These are completely different naming conventions. No FK or mapping exists.

3. **Column schema mismatch.** The CSV template has columns like `beta_raw`, `se_raw`, `effect_size_type`. The `edge_evidence_v1` table expects `effect_value_reported`, `se_reported`, `effect_type_reported`. Different names, different semantics.

### 2. "Is there sufficient data to fill the necessary docs?"

**No. Coverage: ~3 of 25 edges, from 2 papers.**

The 8 manually extracted edges map approximately to:
- `EDGE_EXERCISE_*` family (physical activity → processing speed, verbal fluency, episodic memory, cognitive complaints) — from Campbell 2017
- `EDGE_EXERCISE_*` → cognitive subdomains (working memory, attention, episodic memory, cognitive complaints) — from Cherrier 2013

That covers the **exercise→cognition** domain only. The remaining 20+ edges (inflammation pathways, sleep, fatigue, cortisol, BDNF, pain, depression, HRV) have **zero evidence**.

To fill the DAG minimally, we need papers for at least:
- Inflammation→cognition (IL-6, CRP, TNF-α) — ~3 edges
- Sleep↔cognition — 1 edge
- Fatigue→cognition — 1 edge
- Chemo→inflammation, chemo→cognition — 2 edges
- Depression→cognition — 1 edge
- Plus mediator-mediator edges (sleep→fatigue, IL-6→fatigue, etc.)

**Minimum viable evidence**: ~15 papers covering distinct edges, each with β + SE + sample size.

### 3. "Can we read the entire retrieved paper?"

**No. The retrieved file is NOT a PDF — it's an HTML page.**

```
$ file data/retrieval_cache/dfe640a81569f5c9.pdf
HTML document, Unicode text, UTF-8 text, with very long lines (13453)

$ head -c 50 data/retrieval_cache/dfe640a81569f5c9.pdf
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"
```

The title embedded in the HTML is:
> "Clinical impact of melatonin on breast cancer patients undergoing chemotherapy; effects on cognition, sleep and depressive symptoms" — PLOS ONE

**Root cause**: `fulltext_retriever.py` downloads whatever the URL returns and saves it with a `.pdf` extension. It does not:
- Check `Content-Type` headers (should be `application/pdf`)
- Validate the file magic bytes (PDF starts with `%PDF`)
- Retry with a different URL if it gets an HTML landing page

PLOS ONE returned the article's HTML landing page instead of the actual PDF. The retriever saved it blindly.

**This means: out of 156 candidates scored, ZERO actual PDFs were retrieved.**

### 4. "How come only 1 PDF out of 156 passed screening?"

**The 156 candidates were scored but only 3 were sent to retrieval (testing budget = 3).**

Breakdown:
- Query generator produced 96 queries across 5 workstreams
- PubMed + Europe PMC returned ~197 raw candidates
- After dedup + abstract screening → 156 passed
- APS scorer ranked all 156
- **Retrieval budget was set to `max_papers=3`** (intentionally conservative for testing)
- Of those 3 attempted:
  - 1 "succeeded" → but was actually HTML, not PDF (see above)
  - 2 returned HTTP 403 Forbidden (paywalled despite OA flags)

The pipeline CAN attempt more — the limit was artificial. But even if it attempted all 156, the HTML-not-PDF bug would affect every PLOS ONE download, and most papers are paywalled (403s).

### 5. "Where is the new paper?"

**`data/retrieval_cache/dfe640a81569f5c9.pdf`** — 287 KB, but it's HTML, not PDF.

Additional usability issues:
- The filename is an MD5 hash of the DOI — completely opaque
- No human-readable mapping exists
- The only way to identify it is via SQL: `SELECT * FROM acquisition_queue_v1 WHERE status='retrieved'` → DOI `10.1371/journal.pone.0231379`
- There's no `paper_name → hash` lookup table or filename convention

### 6. "How can the developer address paywalled papers manually?"

**No workflow exists.** Here is what SHOULD happen vs. what DOES happen:

| Step | Should exist | Does exist |
|---|---|---|
| Notification when paper is paywalled | Email/CLI alert with DOI, title, why it's needed | Nothing |
| Instructions to researcher | "Download from [institution proxy / ILL], save to [path]" | Nothing |
| Drop-off location | Clear directory with naming convention | `data/manual_uploads/pdfs/` exists but undocumented |
| Metadata companion | Auto-generated `.meta.json` template | Must be created manually |
| Status update | Mark as "manually retrieved" in queue | Must update DB manually |
| Pipeline re-entry | Auto-detect and feed to extraction | `scan_pdfs()` lists files but doesn't trigger extraction |

**Current state**: A researcher would need to:
1. Run SQL to find which DOIs are `status='dispatched'` or `paywall_flagged=1`
2. Go find the paper themselves (institutional access, ILL, email authors)
3. Save it to `data/manual_uploads/pdfs/` with a specific naming convention
4. Hand-write a `.meta.json` file with DOI, title, edge hints
5. Hope the pipeline picks it up (it won't — `scan_pdfs` just lists files, it doesn't trigger anything)

### 7. "Where are we keeping track of everything?"

**Only `report_status.py` (CLI) exists. No real-time tracking, no approval, no AI proposals.**

| Capability | Exists? | Details |
|---|---|---|
| Status CLI | YES | `python scripts/report_status.py` — shows Class A fill, acquisition queue, gaps |
| Real-time paper additions | NO | No event stream, no watch mode, no webhook |
| Filtering visibility | NO | No UI showing which papers were filtered and why |
| Source attribution | PARTIAL | `acquisition_queue_v1.retrieval_tool` records which adapter was used |
| Researcher approval flow | NO | No human-in-the-loop gating |
| AI extraction proposals | NO | No mechanism for AI to propose and human to review |
| Dashboard | NO | 7 presentation modules exist but have NO rendering frontend |

The presentation layer (`crci/presentation/`) has 7 Python modules that produce dataclasses (view models), but:
- No web framework (no Flask, Django, FastAPI)
- No HTML templates
- No JavaScript frontend
- The `render_*()` functions return Python objects into the void

### 8. "Should we address the 11 gaps from the test results?"

**Yes, but they must be prioritized.** Many overlap with the problems above.

| # | Gap | Severity | Status | Recommendation |
|---|---|---|---|---|
| 1 | No `node_search_terms` seed data → fallback queries | HIGH | Same root cause as data gap | Populate search_terms first |
| 2 | PDF validation (Content-Type check) missing | CRITICAL | Causes false "retrieved" | **Fix immediately** |
| 3 | Duplicate acquisition_queue entries | MEDIUM | Same DOI appears 2x | Add UNIQUE constraint or dedup |
| 4 | No rate limiting between API calls | MEDIUM | Works for small volumes | Add before scaling |
| 5 | Hash-based filenames unreadable | LOW | Usability only | Add DOI→filename lookup |
| 6 | `import_structured_csv` is a stub | CRITICAL | CSVs can never be loaded | **Implement the writer** |
| 7 | No frontend for presentation modules | HIGH | System produces no visible output | Not needed yet |
| 8 | No paywall notification workflow | HIGH | Researcher blocked | Build basic workflow |
| 9 | Edge ID convention mismatch (ER_* vs EDGE_*) | CRITICAL | Manual extractions are orphaned | **Reconcile immediately** |
| 10 | `manual_cherrier_entry.py` never executed | HIGH | 4 ready edges not in DB | Run or integrate |
| 11 | No evidence → no Bayesian model can run | CRITICAL | System's core purpose blocked | Priority #1 |

---

## Architectural Diagnosis

### The Core Problem

The system has been built *inside-out*: infrastructure first, data last. The pipeline code calls functions that call adapters that write to tables — but the tables are empty because the data flow never completed.

```
CURRENT STATE:

  [25 edge definitions]  →  [0 evidence rows]  →  [Bayesian model]  →  [0 recommendations]
        ↑ populated              ↑ EMPTY              ↑ can't run         ↑ nothing to show
        
  [8 manual CSV edges]  →  [stub importer]  →  DEAD END
        ↑ on disk             ↑ doesn't write

  [156 scored papers]  →  [3 attempted]  →  [1 "retrieved"]  →  [HTML, not PDF]  →  DEAD END
```

### What Actually Needs to Happen (Priority Order)

```
REQUIRED STATE:

  [Manual CSVs]  →  [Working importer]  →  [edge_evidence_v1]  →  [Bayesian model]
  [Retrieved PDFs] → [Content-Type check] → [Real PDFs] → [Extraction] → [edge_evidence_v1]
  [Researcher] →  [Tracking dashboard]  →  [Approval gate]  →  [Evidence tables]
```

---

## Recommended Next Steps (Strict Priority Order)

### Phase A: Get Data Into the Database ✅ COMPLETE

1. ~~**Fix edge ID mapping**~~ ✅ Reseeded `edge_relations_definitions_v1` from EDGE_REGISTRY.csv: 25 `EDGE_*` stubs → 137 `ER_*` rows. Also fixed concatenation bug in EDGE_REGISTRY.csv line 135.

2. ~~**Implement `import_structured_csv` writer**~~ ✅ Replaced stub in `manual_upload_watcher.py` with working `_write_edge_evidence_rows()`. Maps CSV columns correctly.

3. ~~**Run `manual_cherrier_entry.py` OR integrate data**~~ ✅ Data loaded via `scripts/load_evidence_into_db.py` — 4 Cherrier + 4 Campbell edges.

4. ~~**Register Campbell 2017 in `study_registry_v1`**~~ ✅ Both Cherrier 2013 and Campbell 2017 registered.

5. ~~**Verify**~~ ✅ `edge_evidence_v1` has 8 rows. `run_manual_import.py --type csv` correctly deduplicates.

### Phase B: Fix Retrieval So It Actually Works ✅ COMPLETE

6. ~~**Add PDF validation to `fulltext_retriever.py`**~~ ✅ Added `_validate_content()` method with magic byte checks (`%PDF-`, `<?xml`). Rejects HTML pages. Also fixed `unpaywall.py` Content-Type logic bug (AND→OR).

7. ~~**Add dedup logic to acquisition queue**~~ ✅ `_write_queue_row()` now checks for existing DOI before inserting. Updates if new APS higher or status better. Cleaned 4 existing duplicates.

8. **Increase retrieval budget and re-run** — ❌ NOT YET DONE. Ready to run when desired.

### Phase C: Build Researcher Workflow — PARTIAL

9. ~~**Create `scripts/show_paywalled.py`**~~ ✅ Built with `--all` (full queue), `--coverage` (8/137 edge grid), `--mark-retrieved DOI`. Includes manual acquisition instructions.

10. **Make `scan_pdfs()` actually trigger pipeline ingestion** — ❌ NOT YET DONE.

11. **Create `scripts/approve_evidence.py`** — ❌ NOT YET DONE.

### Phase D: Dashboard & Visibility (After Data Exists)

12. **Build minimal web dashboard** — FastAPI + Jinja2 showing: edge coverage, paper status, extraction queue, evidence browser. Connects to the 7 existing presentation modules. Estimated: 4-6 hours.

13. **Add AI proposal review flow** — After LLM extraction, show proposed edges to researcher for approval before writing to DB. Estimated: 3-4 hours.

---

## Summary Table (Updated)

| Component | Code Exists? | Actually Works? | Produces Output? |
|---|---|---|---|
| Extraction pipeline (P0-P7) | YES | Runs without crashes | NO — 0 evidence rows |
| Retrieval adapters (5) | YES | All pass connectivity | FIXED — PDF validation added |
| APS scorer | YES | Scores correctly | YES — scores in DB |
| Hop discovery | YES (fixed) | Finds constituent studies | YES — 4 queued |
| CSV import | YES | FIXED — writes to DB | YES — 8 rows loaded |
| Manual entry script | YES | Never executed | Superseded by CSV loader |
| Study registry | YES | 3 papers registered | YES |
| Edge evidence DB | YES | 8 rows | YES |
| Edge definitions DB | YES | 137 ER_* rows | YES |
| Report status CLI | YES | Works | YES |
| Show paywalled CLI | NEW | Works | YES — queue + coverage |
| Presentation modules | YES (7 files) | Produce dataclasses | NO frontend to render them |
| Tracking dashboard | NO | — | — |
| Approval workflow | NO | — | — |
| AI proposal system | NO | — | — |
| Manual acquisition workflow | PARTIAL | CLI exists | Instructions provided |

**Current bottom line**: Phase A and B are complete. 8 evidence rows exist in the database. 129/137 edges still need evidence. Next priorities: (1) extract more papers, (2) build approval workflow, (3) build dashboard.
