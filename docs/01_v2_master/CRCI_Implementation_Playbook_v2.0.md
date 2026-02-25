# CRCI — Extraction System Implementation Playbook v2.0

**Companion to:** CRCI Extraction System Master Specification v2.0
**Version 2.0 — February 2026**

This document contains source adapter API details, rate limits, CLI scripts, budget controls, and build order. For behavioral specifications, see the Master Spec. For schemas and test specs, see the Engineering Appendix.

---

## P1. Source Adapters

All adapters implement the SourceAdapter interface (crci_acq/adapters/base.py): search(query, max_results) → List[CandidateRecord], fetch_metadata(identifier) → PaperMetadata, fetch_fulltext(identifier) → Optional[bytes], get_citations(identifier) → List[str].

### P1.1 PubMed E-utilities (Primary Discovery)

**Base URL:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

**Endpoints:** esearch.fcgi?db=pubmed&term={query}&retmax={max}&retmode=json. efetch.fcgi?db=pubmed&id={pmid_list}&rettype=xml. elink.fcgi?dbfrom=pubmed&db=pubmed&id={pmid}&linkname=pubmed_pubmed_citedin.

**Rate limit:** 3 req/s without API key, 10 req/s with NCBI API key (set via NCBI_API_KEY env var). **Returns:** PMID, title, abstract, MeSH terms, DOI, PMC ID. No full text. **Retry:** 3 retries with exponential backoff (1s, 2s, 4s). HTTP 429 → back off to 1 req/s for 60s. HTTP 500 → retry.

### P1.2 Europe PMC (Primary Full Text)

**Base URL:** `https://www.ebi.ac.uk/europepmc/webservices/rest/`

**Endpoints:** search?query={query}&format=json&pageSize={max}&resultType=core. {pmcid}/fullTextXML.

**Rate limit:** No published limit; use 5 req/s max as courtesy. **Returns:** Full-text XML (structured sections, tables, figures for OA). Coverage: ~4.5M full-text articles. Best structured source.

### P1.3 Crossref (DOI Enrichment)

**Base URL:** `https://api.crossref.org/`

**Endpoints:** works?query={query}&rows={max}. works/{doi}.

**Rate limit:** 50 req/s with polite pool. **Header:** User-Agent: CRCI/1.0 (mailto:contact@project.org). **Returns:** DOI, title, references list, license, citation count, ISSN. Use case: reference list extraction for citation-chain hops.

### P1.4 OpenAlex (Citation Graph)

**Base URL:** `https://api.openalex.org/`

**Endpoints:** works?search={query}&per_page={max}. works/{openalex_id} (includes cited_by_api_url, referenced_works).

**Rate limit:** 10 req/s with polite pool (set mailto: in params). **Returns:** Citation graph, related works, concepts, institutional data. Use case: content-driven hops (Master Spec §9.4), citation-chain expansion (WS7).

### P1.5 Unpaywall (OA Route Resolution)

**Base URL:** `https://api.unpaywall.org/v2/`

**Endpoint:** {doi}?email={email}.

**Rate limit:** 100,000 req/day. **Returns:** best_oa_location.url_for_pdf, host_type, license. Use case: resolve free PDF URL for paywalled DOIs.

### P1.6 Manual Upload (Human Input)

**Watches:** data/manual_uploads/ directory. **Accepts:** PDF files, CSV templates (see Checklists & Templates doc), JSON override files, DOI-list files (.txt, one DOI per line). **Processing:** File watcher detects → validates format → routes PDF to EX-P0, CSV to import_manual_csv.py, DOI list to automated retrieval pipeline.

**DOI-based filename convention:** PDFs deposited for human-acquired papers must follow DOI-based naming: replace `/` in DOI with `_`, append `.pdf`. Example: DOI `10.1016/j.bbi.2023.01.005` → filename `10.1016_j.bbi.2023.01.005.pdf`. The ingestion script matches filenames against acquisition_queue_v1 entries with retrieval_status = HUMAN_NEEDED. Fuzzy matching (substring containment) handles minor naming variations. Matched PDFs update retrieval_status to FULL_TEXT_PDF and enter the pipeline with their existing APS and metadata. Unmatched PDFs are treated as new manual submissions and enter EX-P0 triage from scratch.

### P1.7 paperscraper Integration

The acquisition layer uses [paperscraper](https://github.com/jannisborn/paperscraper) (MIT license, `pip install paperscraper`) as a pip dependency — not forked, wrapped. paperscraper provides ~25% of what the acquisition layer needs (search + download). The other 75% (state tracking, audit, text extraction, deduplication, abstract-only fallback, rate limiting) is CRCI code built around it.

**What paperscraper actually provides (6 modules):**

1. **PubMed query builder** (`pubmed.utils.get_query_from_keywords`). Converts nested Python lists into Boolean PubMed queries. CRCI's WorkstreamQueryGenerator (crci_acq/query_generator.py) calls this function, adding workstream-specific term templates and MeSH field tags.

2. **PubMed search** (via pymed). Returns title, authors, date, abstract, journal, DOI. **Known gap:** paperscraper drops PMID despite pymed providing it, and drops MeSH keywords. CRCI's PubMed adapter must use pymed directly with enriched field mapping to capture PMID and MeSH terms, then feed results to IDResolver for PMCID cross-referencing.

3. **Preprint server dumps** (bioRxiv ~400K papers/~800MB, medRxiv ~90K/~200MB, chemRxiv ~30K/~50MB). Downloads entire server history to local `.jsonl` files for fast offline keyword search. Supports date-bounded incremental scraping. CRCI refreshes dumps weekly via scheduled task.

4. **Multi-source PDF/XML download** (`pdf.save_pdf`). This is paperscraper's strongest component — ~500 lines of battle-tested download logic. The fallback chain *internal to paperscraper* is:

| Step | Source | Notes |
|---|---|---|
| 1 | arXiv direct | URL construction from arXiv DOI |
| 2 | chemRxiv | Cambridge Open Engage API |
| 3 | bioRxiv direct | `biorxiv.org/content/{doi}.full.pdf` |
| 4 | DOI resolution | HEAD/GET on doi.org → follow redirects → scrape `citation_pdf_url` meta tag |
| 5 | BioC-PMC | DOI → PMCID conversion (NCBI ID Converter) → open-access XML. **Note:** paperscraper internally converts DOI→PMCID but discards the PMCID after use |
| 6 | eLife GitHub | Structured XML from eLife's open repository |
| 7 | Wiley TDM API | Requires `WILEY_TDM_API_TOKEN`. Hardcoded 10s delay between requests (only rate-limited source) |
| 8 | Elsevier TDM API | Requires `ELSEVIER_TDM_API_KEY`. Returns XML |
| 9 | bioRxiv S3 | Requester-pays AWS bucket with concurrent MECA archive search (32 workers). Requires `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` with S3 read-only |

Validates PDF by checking first 4 bytes = `%PDF`. Optional sidecar `.json` metadata (title, authors, abstract) via `save_metadata=True`.

5. **Semantic Scholar citations** (`citations.get_citations_by_doi`). Clean wrapper around SemanticScholar API. CRCI wires this into APS SourceQuality component.

6. **Journal impact factor lookup** (`impact.Impactor.search`). Fuzzy matching of journal names to bundled IF database. Returns IF, JCR quartile, ISSN, NLM ID. CRCI uses as quality heuristic in APS scoring.

**What paperscraper does NOT provide (CRCI must build):**

- **No PDF text extraction.** Downloads file bytes to disk and stops. Never calls pdfplumber, pymupdf, or any OCR library. CRCI's PDFProcessor (crci_extract/pdf_processor.py) handles this in EX-INGEST (Master Spec §3.2).
- **No canonical_text persistence.** No `.txt` sidecar, no database storage.
- **No Unpaywall.** CRCI's Unpaywall adapter (§P1.5) adds legal OA route resolution.
- **No Europe PMC full-text search.** CRCI's Europe PMC adapter (§P1.2) adds structured XML retrieval.
- **No state machine.** Paper is either "not downloaded" or "file exists." No PENDING→RETRIEVED→EXTRACTED lifecycle. CRCI's retrieval_status enum (Engineering Appendix §A.2) provides this.
- **No deduplication.** Same paper from PubMed and bioRxiv downloads twice. CRCI's dedup.py handles DOI exact-match + title Jaccard ≥ 0.85.
- **No rate limiting** (except Wiley 10s delay). At scale (350–600 queries), PubMed and NCBI will throttle. CRCI budget controls (§P2) and per-adapter rate limiting are mandatory.
- **No audit trail.** No record of which fallbacks were tried, timing, or failure reasons.
- **No abstract-only mode.** Failed download → skip. CRCI falls back to SHALLOW extraction (m_design = 3.0×).
- **No PMID/PMCID enrichment.** CRCI's IDResolver surfaces cross-references that paperscraper's BioC-PMC fallback internally computes but discards.

**Wrapper pattern — AuditedRetriever:**

CRCI does not call `paperscraper.pdf.save_pdf` directly. Instead, `crci_acq/retriever.py` implements an AuditedRetriever that:

1. Checks retrieval cache (study_id-based, not DOI-based naming)
2. Calls `paperscraper.pdf.save_pdf()` with the full publisher TDM fallback chain
3. If paperscraper fails: tries CRCI-specific fallbacks (Unpaywall §P1.5, Europe PMC §P1.2)
4. If all full-text routes fail: applies APS-based triage (Master Spec §9.6) — HUMAN_NEEDED or ABSTRACT_ONLY
5. Logs audit record: study_id, DOI, fallbacks_tried[], timing, file_type, file_size, success/failure
6. Persists file with study_id-based naming and sidecar metadata
7. Updates acquisition_queue_v1.retrieval_status

The combined chain (paperscraper 9 steps + CRCI 3 additions) is estimated to achieve 70–85% full-text retrieval for oncology/psychology journals. The exact rate depends on institutional TDM API access.

**Configuration.** API keys stored in `.env` file (auto-loaded by paperscraper from cwd or any parent to home): `NCBI_API_KEY`, `WILEY_TDM_API_TOKEN`, `ELSEVIER_TDM_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. CRCI adds: `UNPAYWALL_EMAIL` (required by Unpaywall API).

---

## P2. Budget Controls

| Parameter | Value |
|---|---|
| MAX_QUERIES_PER_DAY | 500 |
| MAX_CANDIDATES_SCORED_PER_DAY | 2,000 |
| MAX_FULLTEXT_RETRIEVALS_PER_DAY | 100 |
| MAX_EXTRACTIONS_PER_DAY | 50 |
| MAX_LLM_COST_USD_PER_DAY | $20.00 |

**Per-source rate limits:**

| Source | Rate Limit |
|---|---|
| PubMed | 3 req/s (10 with API key) |
| Crossref | 50 req/s |
| OpenAlex | 10 req/s |
| Europe PMC | 5 req/s |
| Unpaywall | 100,000 req/day |

---

## P3. CLI Scripts

**run_acquisition.py** — Automated acquisition cycle. Executes phased search strategy (Master Spec §9.2), scores with APS, retrieves full text, queues for extraction. The `--report` flag generates a **human acquisition report** listing all HUMAN_NEEDED papers sorted by APS descending, including: DOI, DOI URL (https://doi.org/{doi}), PubMed link (if PMID available), title, journal, year, target edge(s), study design, APS score, relevance reasons (which workstream, which gap), and expected filename for manual_uploads/ (per §P1.6 DOI naming convention). The report additionally lists ABSTRACT_ONLY papers as lower-priority optional acquisitions that could be upgraded to full-text if convenient. Output format: CSV (machine-readable) + human-readable Markdown summary.

**run_extraction.py** — Extraction pipeline. Runs EX-P0 through EX-P5 for a batch of papers. Options: --mode (DEEP/STANDARD/SHALLOW), --batch-size, --dry-run.

**run_manual_import.py** — Manual uploads. Watches data/manual_uploads/ and processes incoming files.

**run_full_cycle.py** — End-to-end. Runs acquisition → extraction → compilation → gap analysis in one invocation.

**import_manual_csv.py** — CSV template import. Validates CSV against template schema, assigns UUIDs, writes to Layer 0, queues for Trust Boundary.

**migrate_interim_encoding.py** — Interim→column migration. Extracts interim-encoded values from TEXT columns and populates proper columns after ALTER TABLE.

---

## P4. Build Order

### Phase 1 (Weeks 1–2) — Foundation

Build: Source adapters, query generator, search coordinator. Build: Canonical Reader + PaperMap. Build: AG01–AG09 with section routing. Test: 10–20 manually provided PDFs end-to-end.

### Phase 2 (Weeks 3–4) — Strategic Search

Build: Phased search strategy (MAs first, then instruments). Build: APS scorer with annotation boost. Build: Full-text retriever with paywall flagging. Build: Content-driven hop logic. Run: First automated cycle (instruments + MAs).

### Phase 3 (Weeks 5–6) — Intelligence + Quality

Build: AG10 (StrategicIntelAgent). Build: Annotation reconciliation layer. Build: Two-tier extraction triggers. Build: Search saturation detector. Run: 50–100 papers with reconciliation. Verify: Tier 1 spot-check (instruments, norms).

### Phase 4 (Weeks 7–8) — Analytics + Monitoring

Build: Pathway completeness auditor. Build: Scope-conditional evidence summary. Build: Uncertainty classification. Run: Full campaign (300+ papers).

### Phase 5 (Ongoing) — Refinement

Build: Prior sensitivity analysis (batch). Build: Dataset clustering for observational cohorts. Iterate: Agent prompts, synonym tables, APS weights.

### Infrastructure Assessment

**Fully specified (ready to build):** PDF ingestion, relevance screening, 27-subtype taxonomy, Canonical Reader, agent section targeting, two-tier extraction, annotation reconciliation, trust boundary, conversion validity, precision cascade, harmonization, SE calibration, IVW aggregation + DCR, 6 compilers, sufficiency grading, source adapters, APS formula, phased search, content-driven hops, search saturation, LLM guardrails, verification tiers, annotation system, paywall handling.

**Needs more design:** Pathway completeness auditor (needs populated pathways_v1). Prior sensitivity analysis (computational cost optimization). Evidence landscape dashboard (UI specification only).

### Bottleneck Dependency Map

**Layer 0 — Data (blocks everything):** pathways_v1, sd_anchors_v1, instrument psychometrics, biomarker correlations, non-breast norms.

**Layer 1 — Pipeline (depends on Layer 0):** EX-P0 → EX-P1 → TB → P2 → P3 → P4–P7 → P5.

**Layer 2 — Strategic Search (depends on Layer 1):** Phased acquisition, content-driven hops, saturation detection.

**Layer 3 — Analytics (depends on Layers 1–2):** Pathway auditor, evidence landscape, prior sensitivity.

---

*End of CRCI Extraction System Implementation Playbook v2.0*
