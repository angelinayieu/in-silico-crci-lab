# Retrieval Pipeline Test Plan — Cifu 2018 Systematic Review Flow

**Date:** 2025-02-25  
**Scope:** End-to-end test of the automated retrieval + SR constituent-paper discovery pipeline  
**Test Subject:** Cifu 2018 (BMC Cancer) — "Mindfulness-based interventions and cognitive function among breast cancer survivors: a systematic review"  
**DOI:** 10.1186/s12885-018-5065-3

---

## Current State Assessment

| Component | Status | Detail |
|-----------|--------|--------|
| Database (83 tables) | **EMPTY** — 0 rows in all tables | Seed loader exists but was never run |
| Class A seeds | 5 CSV files (77 rows total) | nodes=20, edges=25, instruments=12, measures=9, pathways=6 |
| Env: NCBI_API_KEY | **NOT SET** | PubMed adapter will still work (rate-limited to 3 req/sec vs 10) |
| Env: UNPAYWALL_EMAIL | **NOT SET** | Unpaywall adapter will fail — requires email |
| Env: OPENALEX_EMAIL | **NOT SET** | OpenAlex works but deprioritized in "polite pool" |
| cifu2018.pdf | Present in `data/manual_uploads/pdfs/` | No `.meta.json` file exists for it |
| cifu2018 meta.json | **MISSING** | Must be created before import |
| Retrieval cache dir | **Does not exist** | `data/retrieval_cache/` needs to be created |
| Presentation layer | 7 modules exist | All are render-only view-model generators — no web/CLI frontend yet |

---

## What We're Testing (User's Requirements)

1. **SR → Constituent Papers:** When Cifu 2018 (systematic review) enters the system, does it automatically identify and queue the constituent source papers for retrieval?
2. **Web Scraping / API Retrieval:** Do the 4 source adapters (PubMed, Europe PMC, OpenAlex, Crossref) successfully search for and find papers?
3. **Paywall / Access Detection:** When a paper is behind a paywall, is its status clearly communicated (ABSTRACT_ONLY vs RETRIEVED)?
4. **Communication Interface:** What infrastructure exists for the researcher to see retrieval progress and decisions?
5. **Gap Identification:** What's broken, missing, or disconnected across the entire retrieval→extraction flow?

---

## Test Plan — 6 Phases

### Phase 0: Foundation Setup (Pre-requisites)

**Goal:** Get the database populated so the retrieval pipeline has something to work with.

| Step | Action | Why |
|------|--------|-----|
| 0.1 | Run seed loader to populate Class A tables | Query generator needs nodes/edges/instruments to generate search queries |
| 0.2 | Create `cifu2018.meta.json` | Manual upload watcher needs metadata to register the paper |
| 0.3 | Set environment variables (UNPAYWALL_EMAIL, OPENALEX_EMAIL) | Adapters need them; NCBI_API_KEY optional (still works without, just slower) |
| 0.4 | Create `data/retrieval_cache/` directory | Fulltext retriever saves downloads here |

**Deliverable:** Class A tables populated, Cifu 2018 registered in study_registry_v1, env ready.

---

### Phase 1: Unit-Test Each Source Adapter Independently

**Goal:** Verify each adapter can actually reach its API, return results, and produce valid `CandidateMetadata`.

| Step | Test | Expected Outcome |
|------|------|-----------------|
| 1.1 | **PubMed search** — query: `"mindfulness" AND "breast cancer" AND "cognition"` | Returns candidate list with PMIDs, titles, abstracts |
| 1.2 | **Europe PMC search** — same query | Returns candidates; OA articles marked with PMCIDs |
| 1.3 | **OpenAlex search** — search for Cifu 2018 by DOI | Returns citation graph: papers citing Cifu 2018 + papers it cites |
| 1.4 | **Crossref lookup** — DOI `10.1186/s12885-018-5065-3` | Returns metadata (title, authors, year), reference list |
| 1.5 | **Unpaywall check** — same DOI | Returns OA status (Cifu 2018 is a BMC Cancer OA paper → should be gold/green) |

**What we learn:** Which APIs are reachable from this environment, what data quality looks like, whether rate limits are a problem.

---

### Phase 2: Test the Query Generator

**Goal:** Verify the query generator produces meaningful search queries from Class A registry data.

| Step | Test | Expected Outcome |
|------|------|-----------------|
| 2.1 | Run `query_generator.generate_all(session)` | Produces `APSQueryRequest` objects with PubMed-style Boolean queries |
| 2.2 | Inspect queries for edge workstream | Queries should reference CRCI-relevant terms (cognition, cancer, biomarkers) |
| 2.3 | Inspect queries for instrument workstream | Queries should reference instruments from registry (PSQI, FACIT-F, etc.) |

**What we learn:** Whether the deterministic template expansion produces usable queries, and what gaps exist in seed data.

---

### Phase 3: Test the Search → Screen → Score → Retrieve Pipeline

**Goal:** Run the full 7-step acquisition cycle once (single cycle, small budget) and observe results.

| Step | Test | Expected Outcome |
|------|------|-----------------|
| 3.1 | Run `run_acquisition_cycle()` with `max_papers=5, dry_run=True` | Generates queries, searches APIs, reports candidate counts — no downloads |
| 3.2 | Run `run_acquisition_cycle()` with `max_papers=5, dry_run=False` | Full cycle: search → ID resolve → screen → APS score → retrieve → hop discover |
| 3.3 | Inspect `acquisition_queue_v1` rows | Papers should have APS scores, retrieval status (RETRIEVED / ABSTRACT_ONLY / FAILED) |
| 3.4 | Inspect `data/retrieval_cache/` | Should contain PDFs/XMLs for successfully retrieved papers |
| 3.5 | Check paywall reporting | ABSTRACT_ONLY entries should be clearly identifiable with their DOIs/PMIDs |

**What we learn:** Whether the end-to-end acquisition pipeline actually works in practice, and what the paywall detection looks like.

---

### Phase 4: Test SR → Constituent Paper Discovery (The Core Question)

**Goal:** This is the main thing the user wants to test — when Cifu 2018 (a systematic review) is in the system, does the pipeline automatically discover and queue its constituent papers?

**The Architecture Gap (discovered during research):**

The hop discovery system (`hop_discoverer.py`) has TWO discovery methods:
1. `discover_hops_from_meta_analyses()` — reads `included_study_ids_json` from `study_registry_v1`
2. `discover_hops_from_annotations()` — reads `cited_references` from `study_annotations_v1`

**The problem:** Neither field gets populated automatically. For method 1, the LLM extraction agents (P1) don't extract reference lists into `included_study_ids_json`. For method 2, P7 annotation agents don't populate `cited_references` in `structured_data_json`. The hop discoverer code exists but has no upstream data source.

| Step | Test | What We'll Discover |
|------|------|-------------------|
| 4.1 | Check if P1 agents extract reference lists from SRs | Almost certainly: NO — agents extract metadata labels, not structured reference lists |
| 4.2 | Manually populate `included_study_ids_json` for Cifu 2018 | Gives hop_discoverer data to work with |
| 4.3 | Run `run_hop_discovery(session)` | Should discover constituent papers and queue them to `acquisition_queue_v1` |
| 4.4 | Run acquisition cycle again | Should search for the newly-queued constituent papers |
| 4.5 | Check retrieval results for Cifu 2018's constituent papers | Which are OA? Which are paywalled? |

**Cifu 2018's constituent studies (from the review itself):**
The review covers mindfulness-based interventions (MBSR/MBCT) for cognitive function in breast cancer survivors. Its included studies should be identifiable from the reference list within the PDF.

**What we learn:** Whether hop discovery works when given data, and where the "data feeding" gap needs to be bridged.

---

### Phase 5: Communication Interface / Researcher Visibility

**Goal:** Test what the researcher actually sees — progress reporting, gap analysis, paywall status.

| Step | Test | Expected Outcome |
|------|------|-----------------|
| 5.1 | Run `scripts/report_status.py` | Should show Class A completeness, Class B evidence counts, workstream fill rates, acquisition queue status |
| 5.2 | Run `scripts/report_status.py --gaps` | Should identify which edges lack evidence, suggest next acquisitions |
| 5.3 | Review presentation module capabilities | `crci_dashboard.py`, `evidence_browser.py`, `dag_viz.py`, `provenance_viewer.py` — all produce view models but have NO rendering frontend |
| 5.4 | Assess acquisition_queue_v1 for researcher-facing status | Are paywall-blocked papers clearly flagged? Is there an "action required" surface? |

**What we learn:** How much visibility the researcher has into the pipeline's activities and decisions.

---

### Phase 6: Gap Analysis & Recommendations

**Goal:** Document all findings — what works, what's broken, what's missing.

**Expected gaps (from research so far):**

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| G1 | **No SR reference extraction** | CRITICAL | LLM agents don't extract structured reference lists from systematic reviews into `included_study_ids_json` or `cited_references` |
| G2 | **Empty database** | CRITICAL | Seed loader was never run; no Class A data means query generator produces nothing |
| G3 | **No cifu2018 meta.json** | HIGH | Paper can't be registered without metadata file |
| G4 | **No rendering frontend** | MODERATE | Presentation modules produce view models but no web/CLI rendering — researcher can't see dashboards |
| G5 | **Missing env vars** | MODERATE | Unpaywall requires EMAIL; without it, OA resolution fails |
| G6 | **Missing Crossref adapter** | LOW | crossref.py exists but may not have `retrieve_fulltext` method (search-only) |
| G7 | **No extraction→hop bridge** | HIGH | Even if agents extract reference data, it doesn't flow into the hop_discoverer's expected schema fields |
| G8 | **Paywall communication** | MODERATE | ABSTRACT_ONLY status exists but there's no researcher-facing "needs manual access" surface |

**Deliverable:** Updated gap analysis document with actionable recommendations for each gap.

---

## Execution Order

```
Phase 0  →  Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6
 setup      adapters    queries     full cycle    SR hops     comms       gaps doc
 ~10 min    ~15 min     ~5 min      ~15 min       ~15 min     ~10 min     ~10 min
```

**Total estimated time:** ~80 minutes  
**API costs:** Minimal — adapter tests use free/low-cost academic APIs (PubMed, Europe PMC, OpenAlex, Crossref, Unpaywall). No LLM calls needed for retrieval pipeline.

---

## Success Criteria

| Criterion | Pass Condition |
|-----------|---------------|
| Adapters reach APIs | ≥ 3 of 4 adapters return results |
| Query generator produces queries | ≥ 5 queries generated from seed data |
| Full acquisition cycle completes | No crashes; produces acquisition_queue rows |
| Hop discovery from Cifu 2018 | ≥ 3 constituent papers queued from manually populated refs |
| Paywall visibility | ABSTRACT_ONLY papers have DOI/PMID logged for researcher identification |
| Status report works | `report_status.py` produces readable output |
| Gap document complete | All gaps documented with severity and recommended fix |

---

## What This Plan Does NOT Cover

- Re-testing the extraction pipeline (P0→P6) — already documented in `docs/PIPELINE_TESTING_REPORT.md`
- LLM-based extraction of reference lists from PDFs — identified as a gap, but fixing it is a separate task
- Building a web frontend for presentation modules — out of scope for this test
- Running acquisition in continuous mode — single cycle is sufficient for testing
