# Retrieval Pipeline Test Results — Cifu 2018 Systematic Review Flow

**Date:** 2025-02-25  
**Test Subject:** Cifu 2018 (BMC Cancer) — Systematic review of mindfulness-based interventions and cognitive function in breast cancer survivors  
**DOI:** 10.1186/s12885-018-5065-3

---

## Executive Summary

The automated retrieval pipeline is **architecturally complete and functional**. All 5 source adapters connect to live APIs and return real results. The full 7-step acquisition cycle (query → search → ID resolve → screen → APS score → retrieve → hop discover) runs end-to-end without crashes and produces correct database records.

**The core user question — "Does the system automatically grab constituent papers from a systematic review?" — is answered: YES, with one fix applied.** The hop_discoverer had a filter that excluded systematic reviews (only accepted meta-analysis subtypes). After adding `"systematic_review"` to the subtype filter, all 4 constituent papers from Cifu 2018 were correctly discovered and queued.

**The critical architectural gap remains:** Nothing in the extraction pipeline (P0-P7) automatically populates the `included_study_ids_json` field that hop discovery reads. The current test worked because this field was manually populated. For the system to be fully autonomous, the LLM agents must extract reference lists from SRs/MAs.

---

## Test Results by Phase

### Phase 0: Foundation Setup ✅

| Step | Result |
|------|--------|
| Seed loader | Loaded 72 rows: 20 nodes, 25 edges, 12 instruments, 9 measures, 6 pathways |
| cifu2018.meta.json | Created with DOI, PMID, constituent study DOIs |
| Environment variables | UNPAYWALL_EMAIL and OPENALEX_EMAIL set |
| Retrieval cache dir | Created at `data/retrieval_cache/` |

**Finding:** Seed loader had never been run before — database was completely empty (0 rows across 83 tables). The system requires manual seed loading before any retrieval can work.

---

### Phase 1: Source Adapter Tests ✅ (5/5 PASS)

| Adapter | API | Status | Notes |
|---------|-----|--------|-------|
| **PubMed** | NCBI E-utilities | **PASS** | 5 results with PMIDs, DOIs, abstracts. No API key = rate-limited to 3 req/s |
| **Europe PMC** | REST API | **PASS** | 5 results with PMCIDs + OA flags. PMCIDs enable XML fulltext retrieval |
| **OpenAlex** | REST API | **PASS** | Citation graph + related works. Polite pool with email |
| **Crossref** | REST API | **PASS** | DOI lookup returns complete metadata. Cifu 2018 identified as GOLD OA |
| **Unpaywall** | REST API | **PASS** | Paywall detection working correctly (see below) |

**Paywall Detection for Cifu 2018 Constituent Papers:**

| Paper | DOI | OA Status | Available | Action Required |
|-------|-----|-----------|-----------|-----------------|
| Cifu 2018 (review) | 10.1186/s12885-018-5065-3 | GOLD | ✅ PDF URL | None |
| Johns 2016 | 10.1007/s00520-015-2888-1 | CLOSED | ❌ | Researcher: manual access |
| Lengacher 2015 | 10.1007/s10549-015-3541-4 | UNKNOWN | ❌ | Researcher: manual access |
| Milbury 2013 | 10.1002/cncr.28004 | BRONZE | ⚠️ URL exists, 403 blocked | Researcher: institutional access |
| Van der Gucht 2017 | 10.1016/j.jpsychores.2017.01.011 | CLOSED | ❌ | Researcher: manual access |

---

### Phase 2: Query Generator ✅

| Metric | Result |
|--------|--------|
| Total queries generated | 96 |
| Edge evidence queries | 50 (25 edges × 2 query variants) |
| Instrument psychometrics | 24 (12 instruments × 2 variants) |
| Population norms | 12 |
| Context priors | 5 |
| Recovery parameters | 5 |

**Finding:** No `node_search_terms_v1` data exists — all terms use fallback derivations from node_id (e.g., `NODE_IL6` → `"il6"`). This produces functional but suboptimal queries. Real search terms (MeSH headings, synonyms) would significantly improve search precision.

**Sample queries produced:**
- Edge: `"sleep quality" AND "cognition" AND (cancer OR chemotherapy OR oncology) AND (cognitive OR cognition OR CRCI)`
- Instrument: `"Pittsburgh Sleep Quality Index" AND (reliability OR validation OR psychometric OR "Cronbach" OR "factor analysis") AND (cancer OR oncology)`

---

### Phase 3: Full Acquisition Cycle ✅

Tested with 1 edge (`EDGE_SLEEP_COGNITION`), 1 query, budget of 3 papers:

| Step | Input | Output |
|------|-------|--------|
| Search (PubMed + OpenAlex) | 1 query | 197 unique candidates |
| ID Resolution (NCBI) | 197 candidates | 1 enriched with cross-resolved DOI↔PMID |
| Abstract Screening | 197 candidates | 156 passed (21% filtered as IRRELEVANT) |
| APS Scoring | 156 candidates | 156 DISPATCH, 0 DEFER (threshold=0.40) |
| Fulltext Retrieval | Top 3 dispatched | 1 retrieved (PLOS ONE, 287KB PDF), 2 abstract-only |
| DB Writes | 3 results | 3 rows in `acquisition_queue_v1` with correct status |

**Finding:** APS scoring is too permissive — 100% of screened candidates exceed the 0.40 threshold, all get DISPATCH. The scoring formula may need tuning (edge_gap defaults to 0.5 when no gap context is provided).

**Finding:** Europe PMC fulltext retrieval failed for all 3 because none had PMCIDs. The retriever falls back to Unpaywall which succeeded for the PLOS ONE paper but got 403 for the other two.

---

### Phase 4: SR → Constituent Paper Discovery ✅ (with fix)

**Bug Fixed:** `hop_discoverer.py` line 68 — `study_subtype.in_()` filter excluded `systematic_review`. Added it to the allowed subtypes list.

**End-to-End Flow:**
1. Cifu 2018 registered in `study_registry_v1` with `study_subtype='systematic_review'` and `included_study_ids_json` containing 4 constituent study entries
2. `run_hop_discovery(session)` → found 1 systematic review with included study list
3. All 4 constituent papers queued in `acquisition_queue_v1`:
   - `hop_source_study_id = STUDY_CIFU_2018`
   - `hop_depth = 1`
   - `status = queued`
   - `aps_score = 0.15` (HOP_CITATION_APS_BOOST)
4. Retrieval attempted for all 4 → all returned `ABSTRACT_ONLY` (3 paywalled, 1 publisher-blocked)

**Critical Gap:** The `included_study_ids_json` field was manually populated. In the real pipeline:
- P0 triage classifies the paper as `systematic_review` ✅
- P1 extraction agents extract metadata and claims ✅
- **Nobody extracts the reference list** into `included_study_ids_json` ❌
- Without this field populated, hop_discoverer finds nothing

---

### Phase 5: Communication Interface ⚠️ (Partial)

**What works:**
- `scripts/report_status.py` — comprehensive CLI report showing:
  - Class A knowledge base completeness (20/63 nodes, 25/129 edges, etc.)
  - Class B evidence counts (1 study registered, 0 evidence rows)
  - Workstream fill rates (all 0%)
  - Acquisition queue status (11 entries: 1 retrieved, 6 dispatched, 4 queued)
  - Gap analysis with recommended next actions
- `scripts/report_status.py --gaps` — focused gap view with actionable recommendations

**What exists but can't be used yet:**
7 presentation modules with `render_*` functions that produce view models:
| Module | View Model | Purpose |
|--------|------------|---------|
| `crci_dashboard` | `ScoreDashboardView` | Composite CRCI score gauge |
| `evidence_browser` | `EvidenceBrowserView` | Edge evidence table with gap highlighting |
| `dag_viz` | `DAGVizView` | 63-node causal DAG with edge thickness ∝ |β| |
| `provenance_viewer` | `ProvenanceChainView` | Sankey/tree trace from recommendation → paper |
| `intervention_cards` | `InterventionCardsView` | Schedule recommendation cards |
| `trajectory_plot` | `ProgressTrackerView` | Recovery trajectory over time |
| `variance_pie` | `UncertaintyPanelView` | Variance decomposition pie chart |

These return dataclass view models — no HTML/web/CLI rendering exists. A frontend (React, Streamlit, CLI rich-text, etc.) would consume these to produce visual output.

**What's missing entirely:**
- No "researcher action required" notification for paywalled papers
- No acquisition progress dashboard (live view of what's being searched/retrieved)
- No visual representation of the SR → constituent paper flow
- `acquisition_queue_v1` has status tracking but no researcher-facing presentation

---

## Gap Analysis

| # | Gap | Severity | Component | Description | Fix Effort |
|---|-----|----------|-----------|-------------|------------|
| **G1** | SR reference extraction not automated | **CRITICAL** | `extraction/p1_extraction` | LLM agents don't extract reference lists from SRs into `included_study_ids_json`. The hop_discoverer code works but has no data feed. | Medium — add a P1 agent prompt for SR reference extraction |
| **G2** | `systematic_review` excluded from hop filter | **HIGH** (FIXED) | `retrieval/hop_discoverer.py` | `discover_hops_from_meta_analyses()` only accepted MA subtypes, not systematic_reviews. Fixed by adding `"systematic_review"` to the filter. | Done |
| **G3** | `node_search_terms_v1` empty | **HIGH** | `database/seeds/` | No seed file for search terms. Query generator uses fallback node_id-derived terms (`NODE_IL6` → `"il6"`) instead of proper MeSH headings / synonyms. Significantly reduces search quality. | Low — create search_terms.csv |
| **G4** | APS scoring too permissive | **MODERATE** | `retrieval/aps_scorer.py` | `_score_edge_gap()` defaults to 0.5 when no gap context is provided (most cases), pushing all candidates above threshold. All 156 candidates got DISPATCH. | Low — tune defaults or require gap context |
| **G5** | No rendering frontend | **MODERATE** | `presentation/` | 7 modules produce view model dataclasses but no web/CLI renderer exists. Researcher can't see dashboards, DAG visualizations, or evidence browsers. | High — build Streamlit/React app |
| **G6** | No paywalled paper notification surface | **MODERATE** | Missing | `ABSTRACT_ONLY` status is in the DB but no mechanism alerts the researcher about papers needing manual access. | Medium — add CLI report section + email/notification |
| **G7** | Bronze OA papers fail with 403 | **MODERATE** | `retrieval/fulltext_retriever.py` | Publishers block automated PDF downloads even for "bronze" OA papers (Milbury 2013). Unpaywall reports Available=True but actual download returns 403 Forbidden. | Low — retry with browser-like headers or flag for manual download |
| **G8** | Database requires manual seed loading | **LOW** | `database/seed_loader.py` | Seed loader exists but was never run. No setup script runs it automatically. The retrieval pipeline silently produces 0 queries on an empty DB. | Low — add `load_all_seeds()` call to setup scripts |
| **G9** | No Crossref search integration | **LOW** | `retrieval/search_coordinator.py` | SearchCoordinator uses PubMed + OpenAlex for search but doesn't use Crossref's keyword search. Crossref is only used for DOI lookup/metadata enrichment. | Low — add Crossref to search loop |
| **G10** | Missing `cifu2018.meta.json` | **LOW** (FIXED) | `data/manual_uploads/` | No metadata file existed for Cifu 2018. Created during this test. | Done |
| **G11** | Extraction→hop bridge missing | **HIGH** | Architecture | Even if P1 agents extract references, there's no code path from P1 output → `included_study_ids_json` on `study_registry_v1`. The pipeline writes extraction_runs and evidence tables but doesn't update study_registry with referenced paper lists. | Medium — add P6/P7 step to populate the field |

---

## What Works Well

1. **Source adapters** — All 5 are real implementations hitting live APIs. PubMed, Europe PMC, OpenAlex, Crossref, and Unpaywall all return valid, useful data.

2. **Search deduplication** — SearchCoordinator correctly deduplicates across PubMed and OpenAlex results (300 → 197 unique candidates in our test).

3. **Abstract screening** — Keyword-based relevance filtering removes 20% of irrelevant candidates.

4. **ID cross-resolution** — NCBI ID Converter successfully maps DOI ↔ PMID ↔ PMCID.

5. **Paywall detection** — Unpaywall correctly identifies OA status (gold, bronze, closed) and provides download URLs when available.

6. **Hop discovery** — Once data is present, constituent paper queuing works with proper dedup gates (HOP-G1 depth, HOP-G2 known-paper dedup).

7. **Acquisition queue tracking** — Correct status lifecycle (queued → dispatched → retrieved/abstract_only) with APS scores and retrieval tool attribution.

8. **Status reporting** — `report_status.py` provides comprehensive CLI-based researcher visibility into system state and gaps.

9. **Query generation** — Deterministic template expansion from Class A registry produces scientifically meaningful search queries across 5 workstreams.

---

## Recommended Priority Actions

### Immediate (enable autonomous SR → constituent paper flow)
1. **Create node search terms seed file** — `seeds/search_terms.csv` with MeSH headings and synonyms for all 20 nodes (improves query quality dramatically)
2. **Add SR reference extraction prompt** — Modify P1 extraction agents to identify and extract the included studies list from systematic reviews into structured JSON
3. **Wire extraction→hop bridge** — Add a post-extraction step (in P6 or P7) that writes extracted reference lists to `study_registry_v1.included_study_ids_json`

### Short-term (improve accuracy and usability)
4. **Tune APS scoring** — Adjust default edge_gap score when no gap context is available, or require gap context from evidence tables
5. **Add paywalled paper report** — Add a section to `report_status.py` listing papers in `acquisition_queue_v1` with `status='dispatched'` (abstract-only) that need researcher attention
6. **Handle 403 bronze OA downloads** — Add User-Agent rotation or flag for manual download instead of silent failure

### Medium-term (visualization and automation)
7. **Build minimal dashboard** — Streamlit or CLI-based frontend consuming the 7 presentation view models
8. **Auto-run seed loader** — Add `load_all_seeds()` to setup scripts so database is never empty
9. **Add Crossref to search loop** — Enable keyword search via Crossref adapter in SearchCoordinator

---

## Files Modified During Testing

| File | Change | Reason |
|------|--------|--------|
| `crci/retrieval/hop_discoverer.py` | Added `"systematic_review"` to `study_subtype.in_()` filter | Systematic reviews were excluded from hop discovery |
| `data/manual_uploads/pdfs/cifu2018.meta.json` | Created | Missing metadata file for Cifu 2018 |

---

## Database State After Testing

| Table | Rows | Content |
|-------|------|---------|
| `biomarker_node_definitions_v1` | 20 | Seeded nodes |
| `edge_relations_definitions_v1` | 25 | Seeded edges |
| `instrument_definitions_v1` | 12 | Seeded instruments |
| `measure_definitions_v1` | 9 | Seeded measures |
| `pathways_v1` | 6 | Seeded pathways |
| `study_registry_v1` | 1 | Cifu 2018 (systematic review) |
| `acquisition_queue_v1` | 11 | 3 from Phase 3 pipeline test + 4 hop-discovered + 4 from Phase 4 retrieval |

---

## Appendix: Raw Test Commands

All test commands are reproducible by setting:
```bash
export DATABASE_URL="sqlite:////workspaces/in-silico-crci-lab/crci_dev.db"
export PYTHONPATH="/workspaces/in-silico-crci-lab"
export UNPAYWALL_EMAIL="crci-test@research.dev"
export OPENALEX_EMAIL="crci-test@research.dev"
```
