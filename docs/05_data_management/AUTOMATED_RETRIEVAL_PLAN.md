═══════════════════════════════════════════════════════════════════════════
 CRCI — AUTOMATED RETRIEVAL & ACQUISITION IMPLEMENTATION PLAN
 Purpose: Make the extraction pipeline self-feeding. The system reads
          your Class A registries, generates search queries, finds papers,
          retrieves full text, and feeds them into the existing extraction
          pipeline — while preserving manual input flexibility.
═══════════════════════════════════════════════════════════════════════════

COMPANION DOCUMENT CROSS-REFERENCES
────────────────────────────────────
This Plan is authoritative for: source adapters, query generation from
Class A tables, APS scoring, full-text retrieval priority, manual input
protocol, budget controls, and the Prompts 3.11-3.15 implementation.

**Part 14 (added 2026-02-27) is the authoritative pipeline execution
design.** It supersedes Parts 2 and 6 for stage gates and decision logic.
Read Part 14 FIRST if you are implementing or running the pipeline.

  DEEP_RESEARCH_STRATEGY.md — Search queries, prompts, and keyword
  batteries that produce the INPUT to Stage 0 of this pipeline.
  (Located at repo root: /DEEP_RESEARCH_STRATEGY.md)

Two features in this Plan originate from companion docs:

  P. Intelligence Maximization — Author-identified research_gap
     annotations boost APS by 1.5× (see Step 3 below). These
     annotations come from study_annotations_v1, populated during
     extraction by AG10 (StrategicIntelAgent).

  R. Conversion Validity Module 3 — Missingness provenance codes
     (ABSENT_IN_PAPER, PARSE_FAILURE, AGENT_MISS, GUARDED_REJECTION)
     are checked before generating new acquisition queries, to avoid
     searching for data we already have but failed to extract (see
     Step 6 below).

These two features are fully specified inline below. Prompts 3.11-3.15
do NOT need the companion docs — everything needed is in this Plan.


═══════════════════════════════════════════════════════════════════════════
 PART 1: CURRENT STATE — WHAT EXISTS VS WHAT'S MISSING
═══════════════════════════════════════════════════════════════════════════

FULLY SPECCED AND PROMPTED (37 prompts → code):
  ✓ Database schemas (all Class A/B/C/D/E tables)
  ✓ PDF ingestion + text extraction
  ✓ Canonical Reader + PaperMap
  ✓ 11 specialist agents (AG01-AG11)
  ✓ Trust boundary (numeric + annotation)
  ✓ 7-layer SE calibration
  ✓ IVW aggregation + overlap resolution
  ✓ 6 parameter compilers (psychometric, prior, temporal, etc.)
  ✓ ALG-A through ALG-F (algorithm)
  ✓ Runtime + presentation

FULLY SPECCED BUT NOT PROMPTED (exists in SYS_EXTRACTION spec):
  ✗ EX-ACQ chain (SYS_EX lines 1899-2013) — gap generator, APS scorer,
    retrieval dispatcher. Complete chain card with schemas and gates.
  ✗ acquisition_queue_v1 table — schema exists in 05_TABLE_SCHEMAS.md
  ✗ Source priority: PMC > Publisher API > Unpaywall > Firecrawl

NOT SPECCED AT ALL:
  ✗ Source adapter code (PubMed E-utilities, Crossref, OpenAlex, etc.)
  ✗ Query generator that reads Class A tables and constructs searches
  ✗ Full-text retrieval coordinator
  ✗ PDF download + cache management
  ✗ Workstream-aware query routing (7 different search strategies)
  ✗ Manual upload ingestion pathway (standardized)
  ✗ Budget/rate-limit controller
  ✗ Scheduler (cron or loop)

CURRENT Phase 4 WORKFLOW (broken):
  YOU search PubMed → YOU download PDFs → YOU put in folder →
  python scripts/run_extraction.py papers/*.pdf

TARGET Phase 4 WORKFLOW (automated):
  System reads registries → generates queries → searches APIs →
  scores candidates → retrieves full text → feeds to pipeline →
  extracts → compiles → identifies gaps → generates more queries
  (YOU can also drop PDFs into manual_uploads/ at any time)


═══════════════════════════════════════════════════════════════════════════
 PART 2: THE AUTOMATED ACQUISITION ARCHITECTURE
 ⚠ NOTE: Part 14 supersedes this section for pipeline execution flow.
    Part 2 remains valid for high-level architecture context.
═══════════════════════════════════════════════════════════════════════════

The system has TWO input pathways. Both feed into EX-P0 (triage).

PATHWAY 1 — AUTOMATED (the red arrow in your diagram)
  ┌─────────────────────────────────────────────────────────────┐
  │ Class A Registries                                          │
  │ (edge_relations, nodes, instruments, pathways)              │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ QUERY GENERATOR                                             │
  │ Reads registries → constructs workstream-specific queries    │
  │ 7 query templates (edge, instrument, norms, priors,         │
  │   recovery, kernels, correlations)                          │
  └────────────────────┬────────────────────────────────────────┘
                       │ APSQueryRequest[]
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ SOURCE ADAPTERS (parallel)                                   │
  │ PubMed E-utils → Crossref → OpenAlex → Europe PMC           │
  │ Each returns: title, DOI, PMID, abstract, OA status         │
  └────────────────────┬────────────────────────────────────────┘
                       │ CandidateMetadata[]
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ APS SCORER + DEDUP                                          │
  │ Score candidates. Dedup against study_registry_v1.          │
  │ APS ≥ 0.40 → proceed. APS < 0.40 → defer.                 │
  └────────────────────┬────────────────────────────────────────┘
                       │ APSScoredCandidate[] (APS ≥ 0.40)
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ FULL-TEXT RETRIEVER                                         │
  │ Try: PMC OA → Europe PMC → Unpaywall → Publisher → skip     │
  │ Downloads PDF → saves to retrieval_cache/                   │
  │ Writes acquisition_queue_v1 row                             │
  └────────────────────┬────────────────────────────────────────┘
                       │ Retrieved PDF
                       ▼
                  ┌──────────┐
                  │  EX-P0   │ ← EXISTING PIPELINE (triage → extract)
                  └──────────┘

PATHWAY 2 — MANUAL (your flexibility requirement)
  ┌─────────────────────────────────────────────────────────────┐
  │ YOU drop files into: data/manual_uploads/                    │
  │                                                              │
  │ Supported formats:                                           │
  │   PDF → goes to EX-P0 directly                              │
  │   CSV → structured data, goes to specific compiler          │
  │   JSON → extraction output format, goes to evidence tables  │
  │                                                              │
  │ Each file MUST have a companion .meta.json:                  │
  │   { "doi": "...", "workstream": "edge_evidence",            │
  │     "source": "manual", "notes": "..." }                   │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
                  ┌──────────┐
                  │  EX-P0   │ (or direct to compiler if CSV/JSON)
                  └──────────┘


═══════════════════════════════════════════════════════════════════════════
 PART 3: QUERY GENERATION FROM CLASS A TABLES
 This is the brain of the automated system. It reads YOUR registries
 and constructs searches for each of the 7 workstreams.
═══════════════════════════════════════════════════════════════════════════

File: retrieval/query_generator.py

The query generator reads your Class A tables and produces
APSQueryRequest[] objects. It does NOT use an LLM — it's deterministic
template expansion from your structured registry data.

─── WORKSTREAM 1: EDGE EVIDENCE ───
  Input table: edge_relations_definitions_v1
  Input columns: node_x, node_y, relation_label, canonical_statement

  Query template:
    "{node_x_label}" AND "{node_y_label}" AND (cancer OR chemotherapy
    OR oncology) AND (cognitive OR cognition OR CRCI)

  Example:
    edge: NODE_SLEEP_DISRUPTION → NODE_HPA_DYSREG
    query: "sleep disruption" AND "HPA" AND "cortisol" AND cancer

  Batching: Group by pathway. Search all edges in neuroinflammation
    pathway together (papers often report multiple edges).

  Query expansion: For each node, maintain a synonym list in
    node_search_terms_v1 (NEW reference table):
    NODE_HPA_DYSREG → ["HPA axis", "cortisol", "cortisol rhythm",
                        "diurnal cortisol", "hypothalamic-pituitary"]

  Queries per edge: 3-5 (increasing specificity)
  Total queries: ~350-600 for 118 edges (batched by pathway ≈ 100-150)

  Paper types sought: RCT, cohort, cross-sectional, meta-analysis
  Design filter: Prefer "randomized" OR "cohort" OR "meta-analysis"

─── WORKSTREAM 2: INSTRUMENT PSYCHOMETRICS ───
  Input table: instrument_definitions_v1
  Input columns: instrument_id, instrument_label

  Query template:
    "{instrument_name}" AND (reliability OR validation OR psychometric
    OR "Cronbach" OR "factor analysis") AND (cancer OR oncology)

  Fallback query (if no cancer-specific results):
    "{instrument_name}" AND (reliability OR validation OR psychometric)

  Example:
    INST_PSQI_TOTAL → "PSQI" AND "reliability" AND "cancer"

  Queries per instrument: 2-3
  Total queries: ~46-69 for 23 instruments

  Paper types sought: Validation studies, psychometric analyses
  Design filter: Prefer "validation" OR "psychometric" OR "factor"

─── WORKSTREAM 3: POPULATION NORMS ───
  Input table: instrument_definitions_v1 + normalization_refs_v1
  Input columns: instrument_label, maps_to_node_id

  Query template:
    "{instrument_name}" AND (normative OR norms OR "reference values"
    OR "general population" OR "healthy controls")

  For biomarker nodes:
    "{biomarker_name}" AND "reference range" AND (healthy OR normal)

  Queries per instrument: 1-2
  Total queries: ~15-30

  Paper types sought: Normative studies, large population surveys
  Design filter: Prefer "normative" OR "population" OR "reference"

─── WORKSTREAM 4: CONTEXT-MATCHED PRIORS ───
  Input tables: biomarker_node_definitions_v1 + context definition
  (cancer_type × treatment_phase combinations)

  Query template:
    "{cancer_type}" AND "{treatment_phase}" AND (cognitive OR cognition
    OR fatigue OR depression OR sleep) AND (baseline OR cohort OR
    prospective) AND (N > 50 OR "sample size")

  Example:
    breast × post_treatment →
    "breast cancer" AND "post-treatment" AND "cognitive" AND "cohort"

  Priority contexts (search these first):
    1. breast × post_chemotherapy
    2. breast × active_chemotherapy
    3. colorectal × post_treatment
    4. lung × active_chemotherapy
    5. mixed_cancer × mixed_treatment

  Queries per context: 2-3
  Total queries: ~10-24 for 5-8 priority contexts

  Paper types sought: Large cohort studies with Table 1 data
  Design filter: Prefer "cohort" AND N ≥ 100

─── WORKSTREAM 5: RECOVERY PARAMETERS ───
  Input table: action_catalog_v1 (intervention classes)

  Query template:
    "{cancer_type}" AND (cognitive OR "chemo brain" OR CRCI) AND
    (longitudinal OR "follow-up" OR recovery OR trajectory) AND
    (months OR years)

  Queries: ~8-15 total
  Paper types sought: Longitudinal studies with ≥3 timepoints

─── WORKSTREAM 6: INTERVENTION KERNELS ───
  Input table: action_catalog_v1

  Query template:
    "{intervention_name}" AND (cognitive OR cognition) AND
    (cancer OR oncology) AND "randomized" AND (weeks OR months)

  Example:
    ACT_EXERCISE_AEROBIC →
    "aerobic exercise" AND "cognitive" AND "cancer" AND "randomized"

  Queries per intervention: 2-3
  Total queries: ~20-30 for 10 interventions

  Paper types sought: RCTs with ≥2 assessment timepoints

─── WORKSTREAM 7: BIOMARKER CORRELATIONS ───
  Input table: correlation_registry_v1 (the 8-12 biomarker pairs)

  Query template:
    "{biomarker_A}" AND "{biomarker_B}" AND (correlation OR association)
    AND (cancer OR oncology)

  Queries: ~8-12 total
  Paper types sought: Multi-biomarker studies

─── TOTAL AUTOMATED QUERY VOLUME ───
  Initial sweep: ~500-800 queries across all 7 workstreams
  Expected candidates: ~2,000-5,000 abstracts to score
  Expected retrievals: ~200-400 full texts (APS ≥ 0.40)
  Expected extractions: ~150-300 papers through pipeline

─── NEW REFERENCE TABLE: node_search_terms_v1 ───
  Purpose: Map each node to its PubMed-friendly search synonyms
  Columns:
    node_id (FK → biomarker_node_definitions_v1)
    term (TEXT) — one synonym per row
    term_type (ENUM: primary, synonym, abbreviation, mesh_heading)
    active (BOOL)

  Example rows:
    NODE_IL6 | "interleukin-6" | primary
    NODE_IL6 | "IL-6" | abbreviation
    NODE_IL6 | "interleukin 6" | synonym
    NODE_IL6 | "Interleukin-6" [MeSH] | mesh_heading

  This table is filled during Phase 0A (you populate it alongside
  node definitions). It's GREEN (your design choice) and drives all
  automated query generation.


═══════════════════════════════════════════════════════════════════════════
 PART 4: SOURCE ADAPTERS
 Each API has specific capabilities, rate limits, and data it returns.
═══════════════════════════════════════════════════════════════════════════

All adapters implement the same interface:

  class SourceAdapter:
    def search(query, filters, max_results) → CandidateMetadata[]
    def fetch_metadata(identifier) → PaperMetadata
    def check_fulltext(doi_or_pmid) → FullTextAvailability
    def retrieve_fulltext(identifier) → PDF bytes | None
    def health() → AdapterStatus

─── ADAPTER 1: PubMed E-utilities (PRIMARY DISCOVERY) ───
  API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
  Endpoints used:
    esearch.fcgi — search PubMed, returns PMID list
    efetch.fcgi — fetch abstract + metadata by PMID
    elink.fcgi — find related articles (citation expansion)

  Rate limit: 3 requests/second without API key
              10 requests/second with API key (free, register at NCBI)

  Returns: PMID, title, authors, journal, year, abstract, MeSH terms,
           publication type, DOI (usually), PMC ID (if OA)

  Full text: NO (metadata + abstract only)
  Use for: Primary search across all 7 workstreams

  Query format: PubMed Boolean syntax
    "sleep disruption"[Title/Abstract] AND "cortisol"[Title/Abstract]
    AND "cancer"[MeSH] AND "humans"[MeSH]

  Implementation: retrieval/adapters/pubmed.py
  Dependencies: requests (HTTP), xml.etree (XML parsing)
  Auth: API key via environment variable NCBI_API_KEY

─── ADAPTER 2: Europe PMC (PRIMARY FULL TEXT) ───
  API: https://www.ebi.ac.uk/europepmc/webservices/rest/
  Endpoints used:
    search — search across PMC + PubMed + preprints
    fullTextXML/{pmcid} — full text XML for OA articles

  Rate limit: Reasonable use (no hard published limit, be polite)

  Returns: Same metadata as PubMed + full text XML for OA articles
  Full text: YES (for articles with PMC ID and OA license)
  Use for: Full-text retrieval of OA papers

  Implementation: retrieval/adapters/europe_pmc.py

─── ADAPTER 3: Crossref (DOI ENRICHMENT) ───
  API: https://api.crossref.org/works/
  Endpoints used:
    /works?query=... — search by keywords
    /works/{doi} — fetch metadata by DOI

  Rate limit: 50 requests/second with polite pool
              (include mailto: in User-Agent header)

  Returns: DOI, title, authors, journal, year, references,
           license, abstract (sometimes), citation count

  Full text: NO (but provides links to publisher full text)
  Use for: DOI resolution, citation metadata, reference expansion

  Implementation: retrieval/adapters/crossref.py

─── ADAPTER 4: OpenAlex (CITATION GRAPH) ───
  API: https://api.openalex.org/works
  Endpoints used:
    /works?search=... — search
    /works/{id}/related_works — find related papers

  Rate limit: 10 requests/second (polite pool with email)

  Returns: OpenAlex ID, DOI, title, abstract, cited_by_count,
           concepts, related_works, OA status

  Full text: NO
  Use for: Citation graph expansion (find papers that cite key studies),
           discover related works not found by keyword search

  Implementation: retrieval/adapters/openalex.py

─── ADAPTER 5: Unpaywall (OA ROUTE RESOLUTION) ───
  API: https://api.unpaywall.org/v2/{doi}
  Endpoints used:
    Single DOI lookup → OA status + best OA URL

  Rate limit: 100,000/day with registered email

  Returns: is_oa, best_oa_location (URL to PDF/HTML),
           oa_status (gold, green, hybrid, bronze)

  Full text: YES (provides URL to legal OA copy)
  Use for: Finding free full text for papers with DOIs

  Implementation: retrieval/adapters/unpaywall.py

─── ADAPTER 6: Manual Upload (YOUR INPUT) ───
  Not an API — watches data/manual_uploads/ directory

  Returns: Whatever you put there
  Full text: YES (you provide it)
  Use for: Papers behind paywalls, your own curated finds,
           pre-existing extraction data (CSV/JSON)

  Implementation: retrieval/adapters/manual_upload.py

─── SOURCE PRIORITY FOR FULL TEXT (per EX-ACQ spec) ───
  1. Europe PMC (free, XML, best structured)
  2. Unpaywall (free, PDF, legal OA)
  3. Manual upload (you provide)
  4. Skip (abstract-only extraction with reduced confidence)

  Papers without full text are NOT discarded. They enter the pipeline
  with extraction_mode=SHALLOW (AG1, AG2, AG5 only, from abstract).
  SHALLOW extractions have wider SE (m_design multiplier 3.0×).


═══════════════════════════════════════════════════════════════════════════
 PART 5: MANUAL INPUT PROTOCOL
 Your flexibility requirement: you can always input your own data.
═══════════════════════════════════════════════════════════════════════════

Three manual input methods, all going through the same pipeline:

─── METHOD 1: DROP PDF ───
  Location: data/manual_uploads/pdfs/
  What you do: Put PDF files in the folder
  What happens: Manual upload adapter detects new PDFs, registers them
    in study_registry_v1, feeds to EX-P0 triage
  Companion file: {filename}.meta.json (optional but recommended)
    {
      "doi": "10.xxxx/...",
      "pmid": "12345678",
      "title": "...",
      "workstream_hints": ["edge_evidence", "instrument_psychometrics"],
      "target_edges": ["ER_A_SLEEP_DISRUPTION__HPA_DYSREG"],
      "target_instruments": ["INST_PSQI_TOTAL"],
      "priority": "high",
      "notes": "Key validation study for PSQI in breast cancer"
    }
  If no .meta.json: pipeline infers metadata from PDF content
  This is PATHWAY 2 in the architecture diagram

─── METHOD 2: STRUCTURED DATA CSV ───
  Location: data/manual_uploads/structured/
  What you do: Fill a CSV template with extracted values
  What happens: CSV loader validates against schema, writes directly
    to the appropriate evidence table, skips LLM extraction

  Templates (one per workstream):
    edge_evidence_template.csv
      study_doi, edge_id, beta, se, ci_lower, ci_upper, p_value,
      sample_size, study_design, population, timepoint_weeks,
      is_adjusted, provenance_ref

    instrument_evidence_template.csv
      study_doi, instrument_id, cronbachs_alpha, factor_loading_mean,
      test_retest_icc, sample_size, population, cancer_type,
      cancer_validated, provenance_ref

    population_norms_template.csv
      study_doi, instrument_id, population_mean, population_sd,
      sample_size, population_type, age_range, provenance_ref

    context_priors_template.csv
      study_doi, cancer_type, treatment_phase, node_id, mean_z,
      sd, sample_size, instrument_id, provenance_ref

    temporal_evidence_template.csv
      study_doi, action_id, timepoint_weeks, effect, se,
      is_recovery, sample_size, provenance_ref

    correlation_template.csv
      study_doi, node_a, node_b, correlation, sample_size,
      partial_or_zero, population, provenance_ref

  This bypasses the LLM extraction entirely — for when YOU have already
  extracted values and just want them in the database.

─── METHOD 3: BULK SEARCH OVERRIDE ───
  Location: data/manual_uploads/search_overrides/
  What you do: Provide a list of DOIs or PMIDs to fetch and extract
  File format: search_override.json
    {
      "override_type": "specific_papers",
      "papers": [
        {"doi": "10.xxxx/...", "workstream": "edge_evidence",
         "target_edges": ["ER_A_SLEEP__HPA"]},
        {"pmid": "12345678", "workstream": "instrument_psychometrics"}
      ]
    }
  What happens: Retrieval coordinator fetches these specific papers
    (skipping APS scoring) and feeds them into the pipeline.
  Use case: You found a paper yourself and want the pipeline to extract it.


═══════════════════════════════════════════════════════════════════════════
 PART 6: THE RETRIEVAL → EXTRACTION → COMPILATION FLOW
 End-to-end: how a query becomes a parameter value
 ⚠ NOTE: Part 14 supersedes this section for stage gates and decision
    logic. Part 6 remains valid for the internal extraction chain.
═══════════════════════════════════════════════════════════════════════════

STEP 1: QUERY GENERATION (retrieval/query_generator.py)
  Input: Class A tables + node_search_terms_v1
  Output: APSQueryRequest[] grouped by workstream
  Logic: Template expansion from Part 3 above
  Schedule: On demand OR every N hours (configurable)

STEP 2: SOURCE SEARCH (retrieval/search_coordinator.py)
  Input: APSQueryRequest[]
  For each query:
    a. Search PubMed (primary) → PMID list
    b. Search OpenAlex (expansion) → additional DOIs
    c. Fetch metadata for all candidates via Crossref
    d. Normalize to CandidateMetadata schema
    e. Dedup against study_registry_v1 (DOI + PMID match)
  Output: CandidateMetadata[] (deduplicated)

STEP 3: APS SCORING (retrieval/aps_scorer.py)
  Input: CandidateMetadata[] + gap context
  Logic: EX-ACQ-APS formula from SYS_EXTRACTION:
    APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch
          + 0.15·Recency + 0.10·SourceQuality

  AUTHOR-GAP BOOST (from Intelligence Maximization §7):
    If the candidate maps to an edge where study_annotations_v1
    contains research_gap annotations from ≥1 domain expert paper:
      APS_final = min(1.0, APS × 1.5)
    Rationale: Author-identified gaps carry more weight than
    algorithm-detected gaps because authors understand clinical
    context. A meta-analysis that says "no RCT has tested this in
    colorectal cancer" is stronger evidence of a gap than an
    algorithm counting k < 2 for that edge.

  Output: APSScoredCandidate[]
  Gate: APS ≥ 0.40 → proceed to retrieval
        APS < 0.40 → write to acquisition_queue_v1 as DEFERRED

STEP 4: FULL-TEXT RETRIEVAL (retrieval/fulltext_retriever.py)
  Input: APSScoredCandidate[] (APS ≥ 0.40)
  For each candidate:
    a. Check Europe PMC for OA full text → download XML/PDF
    b. If not OA: check Unpaywall for legal OA copy → download PDF
    c. If neither: mark as ABSTRACT_ONLY (still enters pipeline)
    d. Save to retrieval_cache/{doi_hash}.pdf
    e. Update acquisition_queue_v1 status → RETRIEVED
  Output: Retrieved PDFs + metadata
  Rate limiting: Respect per-source limits (configurable in config)

STEP 5: PIPELINE INGESTION (existing EX-P0 → EX-P1 → ... → P7)
  Retrieved PDFs → run_extraction.py → full pipeline
  Paper subtype classifier routes to appropriate agents:
    Edge evidence papers → AG01-AG09 → P2-P4 → edges_v1
    Validation papers → AG11 → Compiler 1 → instruments_v1
    Cohort papers → AG03-EXT → Compiler 2 → context_matched_priors_v1
    Temporal papers → AG08-EXT → Compiler 3 → kernels + recovery
    Dose papers → AG06-EXT → Compiler 4 → dose_response_params_v1
    etc.

STEP 6: GAP RE-EVALUATION (extraction/p5_sufficiency/grading.py)
  After each extraction batch:
    a. Re-grade all edges (how many now have k≥2?)
    b. Re-check instrument coverage (how many have real α?)
    c. Re-check prior coverage (how many contexts populated?)
    d. Update sufficiency grades
    e. Feed back to Step 1 (new queries for remaining gaps)

  MISSINGNESS-AWARE GAP FILTERING (from Conversion Validity Module 3):
    Before generating new acquisition queries for a gap, check
    missingness codes from the extraction completeness report:

    IF missingness_code = AGENT_MISS for ≥3 papers on same component:
      → Agent prompt needs revision, NOT more papers.
        Action: Flag for agent prompt review. Do NOT generate query.

    IF missingness_code = PARSE_FAILURE for ≥3 papers:
      → Parser issue, not evidence gap.
        Action: Try alternate PDF source or parser settings first.

    IF missingness_code = ABSENT_IN_PAPER for ≥3 papers:
      → Genuine evidence gap. Generate acquisition query normally.

    IF missingness_code = GUARDED_REJECTION consistently:
      → Data exists in figure-only format.
        Action: Consider manual extraction. Low-priority search.

    This prevents the acquisition loop from wasting retrieval cycles
    searching for data that exists in papers already processed but
    was missed due to parser or agent failures.

STEP 7: LOOP TERMINATION (EX-ACQ-G3)
  Stop when ANY of:
    - All edges ≥ Grade C
    - No candidates with APS ≥ 0.40 remain
    - Daily budget exhausted
    - Manual stop command

  This is the "next-paper loop" from your diagram.


═══════════════════════════════════════════════════════════════════════════
 PART 7: FILE MANIFEST — NEW FILES TO BUILD
═══════════════════════════════════════════════════════════════════════════

retrieval/
├── __init__.py
├── query_generator.py          # Reads Class A tables → APSQueryRequest[]
│                                # 7 workstream query templates
│                                # Synonym expansion from node_search_terms_v1
│
├── search_coordinator.py       # Orchestrates multi-source search
│                                # Dedup, merge, normalize candidates
│
├── aps_scorer.py               # EX-ACQ-APS formula implementation
│                                # 5-component score + author-gap boost
│
├── fulltext_retriever.py       # PMC → Unpaywall → skip chain
│                                # PDF download + cache management
│                                # Rate-limit compliance
│
├── acquisition_scheduler.py    # Runs the acquisition loop
│                                # Configurable: on-demand, cron, continuous
│                                # Budget-aware, backlog-aware
│
├── manual_upload_watcher.py    # Watches data/manual_uploads/
│                                # Routes PDFs, CSVs, JSONs appropriately
│
├── adapters/
│   ├── __init__.py
│   ├── base.py                 # SourceAdapter interface
│   ├── pubmed.py               # NCBI E-utilities (esearch, efetch, elink)
│   ├── europe_pmc.py           # Europe PMC search + full text XML
│   ├── crossref.py             # DOI resolution + metadata
│   ├── openalex.py             # Citation graph + related works
│   ├── unpaywall.py            # OA route resolution
│   └── manual.py               # Local filesystem adapter
│
├── models.py                   # CandidateMetadata, FullTextAvailability,
│                                # RetrievalResult dataclasses
│
└── config.py                   # API keys, rate limits, budget caps,
                                 # source priority order, cache paths

scripts/
├── run_acquisition.py          # CLI: run one acquisition cycle
│                                # --workstream edge|instruments|all
│                                # --max-papers 50
│                                # --dry-run (show queries, don't fetch)
│
├── run_manual_import.py        # CLI: import from manual_uploads/
│                                # --type pdf|csv|json|override
│
└── run_full_cycle.py           # CLI: query → search → retrieve → extract
                                 # → compile → grade → report

data/
├── manual_uploads/
│   ├── pdfs/                   # Drop PDFs here
│   ├── structured/             # Drop filled CSV templates here
│   └── search_overrides/       # Drop DOI/PMID lists here
│
├── retrieval_cache/            # Downloaded PDFs (cached, deletable)
│
└── templates/                  # CSV templates for manual structured input
    ├── edge_evidence_template.csv
    ├── instrument_evidence_template.csv
    ├── population_norms_template.csv
    ├── context_priors_template.csv
    ├── temporal_evidence_template.csv
    └── correlation_template.csv

database/schema/ additions:
  Add to 001_class_a_knowledge.sql:
    node_search_terms_v1 (node_id FK, term, term_type, active)

  Already exists in spec:
    acquisition_queue_v1 (in 05_TABLE_SCHEMAS.md)


═══════════════════════════════════════════════════════════════════════════
 PART 8: NEW PROMPTS TO ADD
═══════════════════════════════════════════════════════════════════════════

These go AFTER Prompt 3.10 and BEFORE Phase 4.

PROMPT 3.11 — Source Adapter Base + PubMed + Europe PMC
─────────────────────────────────────────────────────────
Context: E + F + SYS_EX lines 1983-2010 (EX-ACQ-RET)
         + this document Part 4 (adapter specs)

Prompt:
  Create retrieval/adapters/base.py — abstract SourceAdapter with:
    search(query, filters, max_results) → CandidateMetadata[]
    fetch_metadata(identifier) → PaperMetadata
    check_fulltext(doi_or_pmid) → FullTextAvailability
    retrieve_fulltext(identifier) → bytes | None
    health() → AdapterStatus

  Create retrieval/adapters/pubmed.py:
    Uses NCBI E-utilities (esearch.fcgi, efetch.fcgi)
    API key from env NCBI_API_KEY (optional, affects rate limit)
    Rate limit: 3 req/s without key, 10 req/s with key
    Parses XML responses into CandidateMetadata
    Supports PubMed Boolean query syntax
    Handles pagination (retstart, retmax)

  Create retrieval/adapters/europe_pmc.py:
    Search endpoint + fullTextXML/{pmcid} for OA
    Returns structured full text when available
    Converts XML to clean text sections for Canonical Reader

  Create retrieval/models.py with Pydantic models:
    CandidateMetadata, PaperMetadata, FullTextAvailability,
    RetrievalResult, AdapterStatus

Output: 4 Python files


PROMPT 3.12 — Crossref + OpenAlex + Unpaywall Adapters
──────────────────────────────────────────────────────
Context: E + F + this document Part 4

Prompt:
  Create retrieval/adapters/crossref.py:
    /works?query=... for search, /works/{doi} for lookup
    Polite pool: include mailto in User-Agent
    Normalize to CandidateMetadata schema

  Create retrieval/adapters/openalex.py:
    /works?search=... for discovery
    Related works expansion for citation graph
    Polite pool with email

  Create retrieval/adapters/unpaywall.py:
    /v2/{doi}?email=... for OA route resolution
    Returns best_oa_location URL for PDF download

Output: 3 Python files


PROMPT 3.13 — Query Generator + node_search_terms_v1
────────────────────────────────────────────────────
Context: E + F + G (table schemas) + this document Part 3

Prompt:
  Add node_search_terms_v1 to database/schema/001_class_a_knowledge.sql:
    node_id (FK), term (TEXT), term_type (ENUM), active (BOOL)

  Create retrieval/query_generator.py:
    Reads: edge_relations_definitions_v1, biomarker_node_definitions_v1,
           instrument_definitions_v1, action_catalog_v1,
           correlation_registry_v1, node_search_terms_v1

    For each of the 7 workstreams, generates APSQueryRequest[] using
    the template patterns in Part 3 of this document.

    Key methods:
      generate_edge_queries(edge_ids=None) → APSQueryRequest[]
      generate_instrument_queries(inst_ids=None) → APSQueryRequest[]
      generate_norms_queries() → APSQueryRequest[]
      generate_prior_queries(contexts) → APSQueryRequest[]
      generate_recovery_queries() → APSQueryRequest[]
      generate_kernel_queries() → APSQueryRequest[]
      generate_correlation_queries() → APSQueryRequest[]
      generate_all() → APSQueryRequest[]

    Uses node_search_terms_v1 for synonym expansion.
    Returns queries grouped by workstream with metadata about
    which table/parameter each query targets.

Output: 1 SQL addition + 1 Python file


PROMPT 3.14 — Search Coordinator + APS Scorer + Full-Text Retriever
───────────────────────────────────────────────────────────────────
Context: E + F + SYS_EX lines 1899-2013 (full EX-ACQ chain card)
         + this document Parts 3-6

Prompt:
  Create retrieval/search_coordinator.py:
    Takes APSQueryRequest[], dispatches to source adapters,
    collects CandidateMetadata[], deduplicates against
    study_registry_v1 (DOI + PMID match), returns unique candidates.

  Create retrieval/aps_scorer.py:
    Implements EX-ACQ-APS formula:
    APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch
          + 0.15·Recency + 0.10·SourceQuality
    Author-gap boost: APS × 1.5 (capped at 1.0)
    Gate: APS ≥ 0.40 → DISPATCH, < 0.40 → DEFER
    All constants from shared/config.py

  Create retrieval/fulltext_retriever.py:
    Source priority chain: Europe PMC → Unpaywall → skip
    Downloads PDF to retrieval_cache/{hash}.pdf
    Writes/updates acquisition_queue_v1 rows
    Respects rate limits per adapter
    Returns RetrievalResult with status

  Create retrieval/config.py:
    API keys (from env vars), rate limits, budget caps,
    source priority order, cache paths, max papers/day

Output: 4 Python files


PROMPT 3.15 — Acquisition Scheduler + Manual Upload + CLI Scripts
────────────────────────────────────────────────────────────────
Context: E + F + this document Parts 5, 7

Prompt:
  Create retrieval/acquisition_scheduler.py:
    Runs the full acquisition cycle:
    1. Call query_generator.generate_all()
    2. Call search_coordinator.search(queries)
    3. Call aps_scorer.score(candidates)
    4. Call fulltext_retriever.retrieve(scored, budget)
    5. Feed retrieved PDFs to extraction pipeline
    6. Report: queries sent, candidates found, retrieved, extracted
    Modes: single_run, continuous (loop with sleep), dry_run
    Budget-aware: stops when daily cap reached
    Configurable: which workstreams to include

  Create retrieval/manual_upload_watcher.py:
    Watches data/manual_uploads/ for new files
    PDFs → register in study_registry_v1 → feed to EX-P0
    CSVs → validate against template schema → write to evidence table
    JSONs → validate → write to evidence table
    search_overrides → fetch specific DOIs/PMIDs → feed to pipeline

  Create scripts/run_acquisition.py:
    CLI entry point:
    --workstream {edge|instruments|norms|priors|recovery|kernels|
                  correlations|all}
    --max-papers N (default: 50)
    --dry-run (show queries and candidates, don't fetch)
    --manual (process manual_uploads/ instead of automated search)
    --cycle (run full cycle: search + retrieve + extract + compile)

  Create scripts/run_manual_import.py:
    CLI for importing manual uploads:
    --type {pdf|csv|override}
    --validate-only (check format without importing)

  Create CSV templates in data/templates/

Output: 4 Python files + 6 CSV templates


═══════════════════════════════════════════════════════════════════════════
 PART 9: BUDGET AND RATE-LIMIT CONTROLS
═══════════════════════════════════════════════════════════════════════════

Add to shared/config.py:

  # Retrieval budget (daily caps)
  MAX_QUERIES_PER_DAY = 500
  MAX_CANDIDATES_SCORED_PER_DAY = 2000
  MAX_FULLTEXT_RETRIEVALS_PER_DAY = 100
  MAX_EXTRACTIONS_PER_DAY = 50
  MAX_LLM_COST_USD_PER_DAY = 20.0

  # Per-source rate limits (requests per second)
  PUBMED_RPS = 3          # 10 with API key
  CROSSREF_RPS = 50
  OPENALEX_RPS = 10
  EUROPE_PMC_RPS = 5
  UNPAYWALL_RPD = 100000  # per day, not per second

  # Source priority for full text
  FULLTEXT_SOURCE_PRIORITY = [
      "europe_pmc", "unpaywall", "manual", "abstract_only"
  ]

  # Acquisition loop
  ACQUISITION_LOOP_HOURS = 6   # run every 6 hours if continuous
  APS_THRESHOLD = 0.40
  WORKSTREAM_PRIORITY = [
      "instrument_psychometrics",  # Tier 1 - highest impact
      "population_norms",          # Tier 1
      "edge_evidence",             # Tier 3 but highest volume
      "context_priors",            # Tier 2
      "recovery_parameters",       # Tier 2
      "intervention_kernels",      # Tier 2
      "correlations",              # Tier 2
  ]

The budget controller is simple: count API calls per day in a SQLite
counter file. When any cap is reached, stop that workstream. Report
remaining budget in CLI output.


═══════════════════════════════════════════════════════════════════════════
 PART 10: INTEGRATION WITH EXISTING 37 PROMPTS
═══════════════════════════════════════════════════════════════════════════

The 5 new prompts (3.11-3.15) integrate as follows:

EXISTING PROMPT 0.1 (SQL schemas):
  ADD: node_search_terms_v1 table + acquisition_queue_v1 table

EXISTING PROMPT 0.4 (seed data):
  ADD: Seed node_search_terms_v1 with 3-5 synonyms per node
  (you provide these — they're GREEN design choices)

EXISTING PROMPT 3.10 (pipeline extension):
  UNCHANGED but now pipeline.py has a new caller:
  acquisition_scheduler.py can invoke it programmatically
  (not just scripts/run_extraction.py from CLI)

EXISTING Phase 4:
  REPLACES manual workflow with automated + manual hybrid:

  OLD: You search → you download → you run extraction manually
  NEW: System searches → retrieves → extracts automatically
       You can ALSO drop PDFs/CSVs into manual_uploads/ anytime
       You run: python scripts/run_acquisition.py --cycle
       Or: python scripts/run_acquisition.py --manual

TOTAL PROMPTS: 42 (was 37 + 5 new retrieval prompts)

UPDATED PROMPT SEQUENCE:
  Phase 0: 8 prompts (foundation + schemas + seeds)
  Phase 1: 6 prompts (LLM client + extraction skeleton)
  Phase 2: 3 prompts (trust boundary + harmonization + calibration)
  Phase 3: 15 prompts (aggregation + compilers + full-spectrum + retrieval)
  Phase 4: 0 prompts (running the full automated pipeline)
  Phase 5: 6 prompts (algorithm)
  Phase 6: 2 prompts (runtime + presentation)
  Phase 7: 2 prompts (integration + CLI)


═══════════════════════════════════════════════════════════════════════════
 PART 11: IMPLEMENTATION SEQUENCE
═══════════════════════════════════════════════════════════════════════════

BEFORE CODING (you do this):
  1. Populate node_search_terms_v1 with synonyms for all 63 nodes
     (3-5 terms per node = ~200-300 rows)
     This is a GREEN design choice — you know the domain vocabulary.

  2. Register for free API keys:
     - NCBI API key: https://www.ncbi.nlm.nih.gov/account/
     - Unpaywall: just need a valid email address
     - OpenAlex: just need a valid email address
     - Crossref: polite pool uses mailto in User-Agent (no key needed)

  3. Decide your daily budget caps (start conservative):
     50 papers/day max, $20 LLM spend/day max

CODING ORDER (Claude Code builds this):
  1. Prompt 3.11: Base adapter + PubMed + Europe PMC (core search)
  2. Prompt 3.12: Crossref + OpenAlex + Unpaywall (enrichment)
  3. Prompt 3.13: Query generator + node_search_terms table
  4. Prompt 3.14: Search coordinator + APS scorer + retriever
  5. Prompt 3.15: Scheduler + manual upload + CLI scripts

  After these 5 prompts: the system can find its own papers.

TESTING ORDER:
  1. Test PubMed adapter: search "PSQI reliability cancer" →
     should return ~30-50 PMIDs with metadata
  2. Test query generator: give it edge_relations table →
     should produce ~300-500 queries across workstreams
  3. Test search coordinator: run 10 queries → should return
     ~50-100 deduplicated candidates with APS scores
  4. Test full-text retrieval: for 10 OA papers → should download PDFs
  5. Test full cycle: run_acquisition.py --workstream instruments
     --max-papers 5 --cycle → should produce extraction results

FIRST AUTOMATED RUN:
  python scripts/run_acquisition.py \
    --workstream instruments \
    --max-papers 10 \
    --cycle

  This searches for psychometric validation papers for your 23
  instruments, retrieves OA full texts, extracts α and factor
  loadings, and writes to instrument_evidence_v1.

  Then:
  python scripts/run_acquisition.py --workstream edge --max-papers 20
  python scripts/run_acquisition.py --workstream all --max-papers 50


═══════════════════════════════════════════════════════════════════════════
 PART 12: WHAT THIS GIVES YOU (the full picture)
═══════════════════════════════════════════════════════════════════════════

After all 42 prompts are built and Phase 0A seeds are populated:

  python scripts/run_acquisition.py --workstream all --cycle

  This single command:
  1. Reads your 63 nodes, 118 edges, 23 instruments, 20 pathways
  2. Generates ~500-800 search queries across 7 workstreams
  3. Searches PubMed + OpenAlex for candidates
  4. Scores ~2,000-5,000 abstracts with APS formula
  5. Retrieves ~100-200 OA full texts
  6. Feeds them through the full extraction pipeline
  7. Runs 6 compilers to produce algorithm-ready parameters
  8. Re-grades evidence sufficiency
  9. Reports: what's filled, what's still missing, what to search next

  You can ALSO at any time:
  - Drop PDFs into manual_uploads/pdfs/
  - Fill CSV templates with your own extracted values
  - Provide specific DOI lists to override the automated search

  Run it again tomorrow → it finds NEW papers, skips duplicates,
  fills more gaps. This is your red arrow feedback loop, automated.


═══════════════════════════════════════════════════════════════════════════
 PART 13: HONEST LIMITATIONS
═══════════════════════════════════════════════════════════════════════════

1. PAYWALLED PAPERS: The automated system only retrieves OA papers
   (~40-60% of biomedical literature). For paywalled papers, you use
   the manual upload pathway. This is a real constraint, not a fixable
   software limitation.

2. SEARCH QUALITY: PubMed keyword search is not as good as a trained
   researcher's Boolean queries. The synonym table (node_search_terms_v1)
   is critical — bad synonyms = missed papers. You should review and
   refine the synonym table after the first automated run.

3. ABSTRACT-ONLY EXTRACTION: Papers without full text get SHALLOW
   extraction (abstract only). This produces lower-quality evidence
   (wider SE). The system flags these, and you can manually provide
   full text later via manual upload.

4. LLM EXTRACTION ERRORS: The extraction pipeline can hallucinate
   numbers. The trust boundary catches obvious errors (α > 1.0,
   negative SE), but subtle errors (reading the wrong column in a
   table) still get through. The spot-check protocol from the
   workstream analysis applies: 100% verification for Tier 1
   (instruments, norms), 25-30% for Tier 2, 10-15% for Tier 3.

5. FIRST RUN WILL BE NOISY: The first automated run will find many
   irrelevant papers, miss some important ones, and produce some bad
   extractions. This is expected. You iterate: tune synonyms, adjust
   APS weights, review extraction errors, re-run. The system improves
   with each cycle.


═══════════════════════════════════════════════════════════════════════════
 PART 14: REVISED 4-STAGE TRIAGE PIPELINE (AUTHORITATIVE)
 Supersedes the simple flow in Parts 2 and 6 for pipeline execution.
 Parts 2 and 6 remain valid for architecture context; this Part governs
 the actual stage gates and decision logic.
═══════════════════════════════════════════════════════════════════════════

DESIGN RATIONALE
────────────────
The original pipeline (Parts 2/6) goes:
  query → search → APS score → retrieve full text → extract

The problem: ~40-60% of papers that pass APS scoring and enter full
extraction (Stage 2, costing $0.30-2.00/paper in LLM calls) turn out
to contain no extractable statistics. The abstract says "associated
with" but the full text has only narrative discussion or unconvertible
results (e.g., only figures, no tables with CIs/SEs).

The revised pipeline adds two cheap intermediate gates that eliminate
this waste mode:

  Stage 0 (FREE)     → metadata + dedup + OA routing + relevance + APS
  Stage 1 (CHEAP)    → LLM abstract pre-extraction for edge mapping
  Stage 1.5 (V.CHEAP)→ deterministic full-text extractability scan
  Stage 2 (EXPENSIVE)→ full deep extraction + quality + CSV writes

Expected savings: ~50% reduction in wasted Stage 2 runs.


─── THE 4-STAGE PIPELINE ───

  ┌─────────────────────────────────────────────────────────────┐
  │ INPUT: DOIs/PMIDs/URLs from:                                │
  │   • DEEP_RESEARCH_STRATEGY.md search prompts                │
  │   • Automated query_generator.py workstream queries         │
  │   • Manual DOI lists (search_overrides/)                    │
  │   • Hop discovery (hop_discoverer.py citation expansion)    │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STAGE 0 — METADATA + TRIAGE (FREE)                         │
  │                                                              │
  │ Existing modules used:                                       │
  │   • search_coordinator.py → ID normalization, multi-source  │
  │   • abstract_screener.py  → SCREEN-1 relevance label        │
  │   • aps_scorer.py         → 5-component APS score           │
  │   • Unpaywall adapter     → OA status + best URL            │
  │                                                              │
  │ Performs:                                                     │
  │   1. ID normalization (DOI→PMID→PMC cross-resolve)          │
  │   2. Dedup: DOI first, then PMID, then title+year fuzzy     │
  │   3. Fetch abstract + metadata from PubMed/OpenAlex         │
  │   4. Run SCREEN-1: → HIGH / MODERATE / LOW / IRRELEVANT     │
  │   5. Run APS scoring (5-component formula)                  │
  │   6. Check Unpaywall: OA status + best_oa_url               │
  │   7. Classify access route:                                  │
  │      OA_AVAILABLE | PAYWALLED | ABSTRACT_ONLY               │
  │                                                              │
  │ Output per paper (written to acquisition_queue_v1):          │
  │   doi, pmid, pmcid, title, year, journal, abstract          │
  │   oa_status, best_oa_url, access_route                      │
  │   relevance_label (HIGH/MOD/LOW/IRRELEVANT)                 │
  │   aps_score, aps_components{}                                │
  │   target_edges[], target_pathways[]                          │
  │   stage0_status: PASSED | REJECTED | PARKED                 │
  │                                                              │
  │ Gate S0-G1:                                                  │
  │   IRRELEVANT → REJECT (stop)                                │
  │   APS < 0.40 → DEFER (park for later re-evaluation)        │
  │   HIGH/MOD + APS ≥ 0.40 → PASS to Stage 1                  │
  │   PAYWALLED papers: still pass to Stage 1 for abstract      │
  │     mapping (decide later whether manual acquisition is      │
  │     worth it)                                                │
  └────────────────────┬────────────────────────────────────────┘
                       │ PASSED candidates
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STAGE 1 — ABSTRACT PRE-EXTRACTION (CHEAP, ~$0.01-0.05/ea)  │
  │                                                              │
  │ New module: retrieval/abstract_pre_extractor.py              │
  │   Uses: LLM call on abstract text only                      │
  │                                                              │
  │ Extracts (categorical only — NEVER numeric claims):          │
  │   • design_guess: RCT / cohort / cross_sectional / etc.     │
  │   • population_guess: cancer_type + treatment_phase          │
  │   • instruments_guess[]: which instruments mentioned         │
  │   • edges_covered_guess[]: edge_ids with per-edge confidence │
  │   • extractability_guess: YES / MAYBE / NO                  │
  │     (does abstract imply tables with stats exist?)           │
  │   • multi_edge_flag: covers ≥2 target edges?                │
  │   • priority_band: CRITICAL / HIGH / MODERATE / LOW         │
  │                                                              │
  │ CRITICAL classification (any ONE sufficient):                │
  │   • covers a k=0 edge in the active slice                   │
  │   • RCT/longitudinal/mediation design for a k<3 edge        │
  │   • multi-biomarker panel paper (≥3 of: IL-6, CRP, TNF-α,  │
  │     cortisol, BDNF) likely to provide correlation matrix     │
  │   • covers ≥2 target edges with extractability_guess ≠ NO   │
  │                                                              │
  │ STRICT RULE: Stage 1 NEVER produces effect sizes, sample    │
  │ sizes, SE values, or any numeric claims. It produces only    │
  │ categorical metadata for prioritization. Numeric extraction  │
  │ happens exclusively in Stage 2.                              │
  │                                                              │
  │ Output per paper (appended to acquisition_queue_v1 row):     │
  │   stage1_design_guess, stage1_population_guess               │
  │   stage1_instruments_json[], stage1_edges_json[]             │
  │   stage1_extractability, stage1_priority_band                │
  │   stage1_status: PROCEED | SKIP | PARK_PAYWALLED            │
  │                                                              │
  │ Gate S1-G1:                                                  │
  │   extractability_guess = NO → SKIP (stop)                   │
  │   priority_band = LOW and no unique edge coverage → SKIP     │
  │   CRITICAL/HIGH → PROCEED to Stage 1.5                      │
  │   MODERATE → PROCEED only if edge gap is k≤1                │
  │   PAYWALLED + CRITICAL → PARK with "manual_acquisition_     │
  │     recommended" flag for human review                       │
  └────────────────────┬────────────────────────────────────────┘
                       │ PROCEED candidates (OA available)
                       │ PARK_PAYWALLED candidates (for human)
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STAGE 1.5 — FULL-TEXT EXTRACTABILITY SCAN (V.CHEAP, no LLM) │
  │                                                              │
  │ New module: retrieval/fulltext_extractability_scanner.py     │
  │   Uses: regex/string matching on full text — NO LLM cost    │
  │   Runs on: any paper whose full text is already available:   │
  │     • OA papers fetched by fulltext_retriever.py             │
  │     • Manual uploads in data/manual_uploads/pdfs/           │
  │     • Already-cached papers in retrieval_cache/             │
  │   Skipped for: paywalled papers without cached text          │
  │     (these go straight to Stage 2 if manually obtained)      │
  │                                                              │
  │ Scan 1 — Statistical extractability markers:                 │
  │   Searches for strings that imply extractable statistics:    │
  │     "95% confidence interval", "standard error", "SE =",    │
  │     "β =", "beta =", "B =", "regression coefficient",      │
  │     "odds ratio", "OR =", "hazard ratio", "HR =",          │
  │     "Pearson r", "r =", "correlation", "η²", "eta",        │
  │     "Cohen", "effect size", "d =", "g =",                  │
  │     "Table 2", "Table 3", "Table 4",                       │
  │     "mixed-effects", "ANCOVA", "ANOVA", "adjusted for",    │
  │     "mediated by", "mediation", "path coefficient",         │
  │     "multilevel", "hierarchical linear",                    │
  │     "p < 0.0", "p = 0.0", "p<.0", "p=.0",                 │
  │     "(F(", "(t(", "(χ²", "(chi-square",                    │
  │     "Supplementary Table"                                    │
  │                                                              │
  │ Scan 2 — Construct/instrument matching:                      │
  │   For each target edge from Stage 1 edges_covered_guess[],  │
  │   looks for the specific instrument names or construct terms │
  │   that would provide evidence for that edge:                 │
  │     PSQI, ISI, salivary cortisol, CAR, AUC,                │
  │     IL-6, CRP, TNF, C-reactive protein,                    │
  │     plasma BDNF, serum BDNF,                                │
  │     HVLT, RAVLT, TMT, Trail Making, DSST,                  │
  │     FACT-Cog, EORTC, digit span, Stroop,                   │
  │     (full list from INSTRUMENT_REGISTRY.csv labels)          │
  │                                                              │
  │ Scan 3 — Table/figure section detection:                     │
  │   Regex scan for table captions that suggest quantitative    │
  │   results: "Table \d+[.:] .*(?:regression|model|           │
  │   coefficient|association|correlation|comparison|outcome)"   │
  │                                                              │
  │ Output per paper:                                            │
  │   fulltext_scan_pass: PASS / FAIL / UNCLEAR                 │
  │   extractability_markers_found[]: which trigger strings hit  │
  │   table_hints[]: candidate table captions with page/section  │
  │   construct_matches[]: which instruments/constructs found    │
  │   marker_count: total distinct markers found                 │
  │   stage1p5_status: PROCEED | FAIL | UNCLEAR                 │
  │                                                              │
  │ Classification:                                              │
  │   marker_count ≥ 3 AND table_hints ≥ 1 → PASS              │
  │   marker_count ≥ 1 OR table_hints ≥ 1  → UNCLEAR           │
  │   marker_count = 0 AND table_hints = 0  → FAIL             │
  │                                                              │
  │ Gate S1.5-G1:                                                │
  │   FAIL  → do NOT deep-extract (unless paper is uniquely      │
  │           important: only candidate for a k=0 critical edge) │
  │   PASS  → PROCEED to Stage 2                                │
  │   UNCLEAR → PROCEED only if edge gap is critical (k=0) and  │
  │             no PASS alternatives exist for that edge         │
  └────────────────────┬────────────────────────────────────────┘
                       │ PROCEED candidates
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ PRE-STAGE 2: GREEDY EDGE-COVERAGE SET COVER                │
  │                                                              │
  │ Before paying for Stage 2, optimize which papers to extract. │
  │                                                              │
  │ New module: retrieval/extraction_batch_optimizer.py          │
  │                                                              │
  │ Inputs:                                                      │
  │   • All PROCEED candidates from Stage 1.5                    │
  │   • edges_covered_guess[] from Stage 1 (candidate → edges)  │
  │   • Edge gap report from pathway_evidence_auditor.py        │
  │   • Daily extraction budget (from config)                    │
  │                                                              │
  │ Algorithm:                                                   │
  │   1. Build matrix: candidate_i → {edges_covered_guess}      │
  │   2. Initialize: uncovered_edges = all target edges with     │
  │      k < sufficiency_target                                  │
  │   3. Greedy loop:                                            │
  │      a. Score each candidate:                                │
  │         extraction_priority = w1·APS                         │
  │                             + w2·new_edges_covered           │
  │                             + w3·extractability_score        │
  │                             + w4·design_rank                 │
  │                             - w5·access_cost_penalty         │
  │         Where:                                               │
  │           w1=0.20, w2=0.35, w3=0.20, w4=0.15, w5=0.10      │
  │           new_edges_covered = |edges_guess ∩ uncovered|      │
  │                              / |uncovered|                   │
  │           extractability_score =                             │
  │             1.0 if scan_pass=PASS                            │
  │             0.4 if scan_pass=UNCLEAR                         │
  │             0.1 if no scan (paywalled, manually obtained)    │
  │           design_rank =                                      │
  │             1.0 meta-analysis, 0.9 RCT, 0.7 cohort,        │
  │             0.5 cross-sectional, 0.3 unknown                 │
  │           access_cost_penalty =                              │
  │             0.0 if OA+cached, 0.3 if needs fetch,           │
  │             0.8 if paywalled                                 │
  │         (all weights from shared/config.py)                  │
  │      b. Select candidate with highest extraction_priority    │
  │      c. Remove its covered edges from uncovered_edges        │
  │      d. Add to extraction_batch                              │
  │      e. Repeat until:                                        │
  │         - extraction_batch reaches daily budget, OR          │
  │         - all target edges have ≥1 candidate scheduled, OR  │
  │         - no candidates with extraction_priority > 0.20      │
  │   4. Reserve exploration_budget = max(3, 0.10 × daily_cap)  │
  │      slots for borderline/surprising candidates              │
  │   5. Log: why_selected[] per paper (which edges, design,    │
  │      gap reason)                                             │
  │                                                              │
  │ Output: extraction_queue — ordered list of papers for        │
  │         Stage 2, with priority scores and reasons            │
  └────────────────────┬────────────────────────────────────────┘
                       │ extraction_queue (sorted by priority)
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STAGE 2 — DEEP EXTRACTION (EXPENSIVE, ~$0.30-2.00/paper)   │
  │                                                              │
  │ Existing modules used:                                       │
  │   • fulltext_retriever.py    → fetch PDF/XML if not cached  │
  │   • extraction/pipeline.py   → full P0→P7 chain            │
  │   • p0_triage/runner.py      → classify + route             │
  │   • AG01-AG11 agents         → multi-agent extraction       │
  │   • Trust boundary           → numeric validation           │
  │   • SE calibration           → 7-layer calibration          │
  │   • Compilers                → write to DB tables           │
  │                                                              │
  │ Enhanced with stage metadata:                                │
  │   • Pass table_hints[] from Stage 1.5 to agents (helps      │
  │     agents know where to look in the paper)                  │
  │   • Pass edges_covered_guess[] to P0 triage (pre-identifies │
  │     which edges to prioritize in extraction)                 │
  │   • Pass design_guess to P0 (confirms extraction mode)      │
  │                                                              │
  │ Output: standard extraction output → DB tables               │
  │   edge_evidence_v1, instrument_evidence_v1, etc.            │
  │   + update acquisition_queue_v1 status → EXTRACTED          │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ POST-STEP: GAP RE-EVALUATION + LOOP CONTROL                │
  │                                                              │
  │ Existing module: pathway_evidence_auditor.py                 │
  │                                                              │
  │ After each extraction batch:                                 │
  │   1. Re-grade all edges (AUDIT-1 formula)                   │
  │   2. Check missingness codes (from Part 6 Step 6):          │
  │      AGENT_MISS ≥3 → fix agent prompt, not more papers      │
  │      PARSE_FAILURE ≥3 → fix parser, not more papers         │
  │      ABSENT_IN_PAPER ≥3 → genuine gap, search more          │
  │   3. Update remaining gaps for next cycle                    │
  │   4. Feed back to Stage 0 for next query batch              │
  │                                                              │
  │ Loop termination (EX-ACQ-G3 from Part 6):                   │
  │   • All target edges ≥ Grade C, OR                          │
  │   • No candidates with APS ≥ 0.40 remain, OR               │
  │   • Daily budget exhausted, OR                              │
  │   • Manual stop command                                      │
  └─────────────────────────────────────────────────────────────┘


─── PERSISTENCE MODEL ───

Source of truth: acquisition_queue_v1 table (extended)

Each paper gets ONE row in acquisition_queue_v1 that accumulates
stage results as it progresses. No separate CSV files as primary
storage — CSVs are export views for human review.

Extended columns for acquisition_queue_v1:

  -- Stage 0 fields (already exist or add)
  doi, pmid, pmcid                         -- identifiers
  title, year, journal, abstract           -- metadata
  oa_status, best_oa_url, access_route     -- OA routing
  relevance_label                          -- SCREEN-1 output
  aps_score, aps_components_json           -- APS output
  target_edges_json, target_pathways_json  -- workstream targets
  stage0_status                            -- PASSED/REJECTED/PARKED

  -- Stage 1 fields (NEW)
  stage1_design_guess                      -- RCT/cohort/etc.
  stage1_population_guess                  -- cancer_type+phase
  stage1_instruments_json                  -- instrument IDs guessed
  stage1_edges_json                        -- edge IDs + confidence
  stage1_extractability                    -- YES/MAYBE/NO
  stage1_priority_band                     -- CRITICAL/HIGH/MOD/LOW
  stage1_status                            -- PROCEED/SKIP/PARK
  stage1_timestamp                         -- when Stage 1 ran

  -- Stage 1.5 fields (NEW)
  stage1p5_scan_pass                       -- PASS/FAIL/UNCLEAR
  stage1p5_markers_json                    -- extractability markers
  stage1p5_table_hints_json                -- candidate table captions
  stage1p5_construct_matches_json          -- instruments found in text
  stage1p5_marker_count                    -- total distinct markers
  stage1p5_status                          -- PROCEED/FAIL/UNCLEAR
  stage1p5_timestamp                       -- when Stage 1.5 ran

  -- Extraction queue fields (NEW)
  extraction_priority                      -- composite priority score
  extraction_batch_id                      -- which batch it was in
  why_selected_json                        -- reasons for selection
  extraction_status                        -- QUEUED/RUNNING/DONE/FAILED

CSV export views (generated on demand, not primary storage):

  python scripts/export_triage_snapshot.py --stage 0    → stage0_snapshot.csv
  python scripts/export_triage_snapshot.py --stage 1    → stage1_snapshot.csv
  python scripts/export_triage_snapshot.py --stage 1.5  → stage1p5_snapshot.csv
  python scripts/export_triage_snapshot.py --queue      → extraction_queue.csv
  python scripts/export_triage_snapshot.py --all        → full_pipeline_snapshot.csv

These CSVs are for human review/audit. The DB remains the single
source of truth. No dual-write risk.


─── VERTICAL SLICE STRATEGY (IMPLEMENTATION SEQUENCE) ───

DO NOT attempt global retrieval across all 143 edges at once.
Implement and prove the pipeline on ONE vertical slice first.

Recommended first slice (Sleep/Activity → HPA → Neuroplasticity):

  Target pathways:
    PW_M08_HPA_AXIS            (HPA dysregulation)
    PW_M04_NEUROPLASTICITY     (BDNF-mediated plasticity)
    PW_M01_NEUROINFLAMMATION   (IL-6, CRP, TNF-α)

  Target edges (from EDGE_REGISTRY, ~15-20 edges):
    All edges where source OR target is in:
      NODE_BEH_SLEEP, NODE_BEH_PHYS_ACTIVITY,
      NODE_BIO_HPA, NODE_BIO_CORTISOL,
      NODE_BIO_BDNF, NODE_BIO_IL6, NODE_BIO_CRP, NODE_BIO_TNF,
      NODE_COG_WORK_MEM, NODE_COG_PROC_SPEED, NODE_COG_EXEC_FUNC

  Why this slice:
    • Contains edges at all evidence tiers (k=0 through k>5)
    • Spans biomarker + behavioral + cognitive layers
    • Has enough OA literature to test all 4 stages
    • Small enough (~15-20 edges) to manually verify end-to-end
    • The HPA→BDNF→cognition chain passes through the most
      mechanistically interesting part of the model

Slice execution order:
  1. Run pathway_evidence_auditor.py on these edges → get gap report
  2. Generate queries for these edges only (query_generator --slice)
  3. Run Stage 0 → expect ~200-500 candidates
  4. Run Stage 1 → expect ~80-200 proceed
  5. Retrieve OA full text for PROCEED candidates
  6. Run Stage 1.5 → expect ~40-100 PASS
  7. Run set-cover → select ~15-25 for extraction
  8. Run Stage 2 on batch → extract
  9. Re-audit → check which edges improved
  10. Iterate once more if critical gaps remain

After slice is proven: extend to remaining pathways in priority order
  (PW_M05_OXIDATIVE → PW_M06_METABOLIC → PW_C01_FATIGUE → etc.)


─── NEW MODULES TO BUILD ───

  retrieval/abstract_pre_extractor.py       (Stage 1 — NEW)
    Input: CandidateMetadata with abstract
    Output: Stage1Result (categorical metadata, NO numeric claims)
    Uses: LLM call on abstract. Structured output parsing.
    Cost: ~$0.01-0.05 per paper (1 short LLM call)
    Registry context: reads EDGE_REGISTRY, INSTRUMENT_REGISTRY
    to validate edge/instrument guesses

  retrieval/fulltext_extractability_scanner.py  (Stage 1.5 — NEW)
    Input: full text string (from cached PDF/XML)
    Output: ScanResult (markers, table hints, construct matches)
    Uses: regex only — NO LLM
    Cost: ~0 (CPU only)
    Registry context: reads INSTRUMENT_REGISTRY for construct names

  retrieval/extraction_batch_optimizer.py    (Set-cover — NEW)
    Input: list of PROCEED candidates + gap report
    Output: ordered extraction_queue with reasons
    Uses: greedy set-cover algorithm — NO LLM
    Cost: ~0 (CPU only)
    Config: weights from shared/config.py

  scripts/run_triage_sweep.py               (Orchestrator — NEW)
    CLI entry point for the 4-stage pipeline:
    --stage {0|1|1.5|2|all}
    --slice {pathway_ids or "all"}
    --max-papers N
    --dry-run
    --export-csv (generate snapshot CSVs)

  scripts/export_triage_snapshot.py         (CSV export — NEW)
    Exports DB state to CSV for human review

Existing modules that participate (NO modification needed):
  abstract_screener.py    → Stage 0
  aps_scorer.py           → Stage 0
  fulltext_retriever.py   → Stage 1.5 input + Stage 2
  search_coordinator.py   → Stage 0
  query_generator.py      → Stage 0
  pathway_evidence_auditor.py → Post-step + set-cover input
  extraction/pipeline.py  → Stage 2


─── CONFIG ADDITIONS (shared/config.py) ───

  # Stage 1.5 extractability scan
  EXTRACTABILITY_MARKER_THRESHOLD_PASS = 3
  EXTRACTABILITY_TABLE_HINT_REQUIRED = True
  EXTRACTABILITY_MARKERS: list[str] = [
      "95% confidence interval", "confidence interval",
      "standard error", "SE =", "SE=",
      "β =", "beta =", "B =", "regression coefficient",
      "odds ratio", "OR =", "OR=",
      "hazard ratio", "HR =", "HR=",
      "Pearson r", "r =", "r=", "correlation coefficient",
      "η²", "eta squared", "partial eta",
      "Cohen", "effect size", "d =", "g =",
      "Table 2", "Table 3", "Table 4", "Table 5",
      "mixed-effects", "ANCOVA", "ANOVA",
      "adjusted for", "controlling for",
      "mediated by", "mediation analysis", "path coefficient",
      "multilevel model", "hierarchical linear",
      "p < 0.0", "p = 0.0", "p<.0", "p=.0",
      "Supplementary Table", "Supplemental Table",
  ]

  # Extraction batch optimizer weights (additive, not multiplicative)
  EXTRACTION_PRIORITY_WEIGHTS: dict[str, float] = {
      "aps": 0.20,
      "new_edge_coverage": 0.35,
      "extractability": 0.20,
      "design_rank": 0.15,
      "access_cost_penalty": 0.10,
  }
  EXPLORATION_BUDGET_FRACTION = 0.10
  EXPLORATION_BUDGET_MIN = 3

  # Vertical slice targeting
  DEFAULT_SLICE_PATHWAYS: list[str] = [
      "PW_M08_HPA_AXIS",
      "PW_M04_NEUROPLASTICITY",
      "PW_M01_NEUROINFLAMMATION",
  ]


─── CROSS-REFERENCES ───

This Part 14 connects to:

  DEEP_RESEARCH_STRATEGY.md
    The search queries and AI prompts in that document produce the
    INPUT to Stage 0. After running Deep Research prompts, the user
    collects DOIs/PMIDs/URLs and feeds them to:
      python scripts/run_triage_sweep.py --stage all --slice default

  LLM_TASK_ROUTER.md
    Needs new Task F: "Search for papers / Triage candidates"
    Route: read DEEP_RESEARCH_STRATEGY.md → collect links →
           read this Part 14 → run pipeline

  CLAUDE.md
    Needs new routing arrow: "Search / triage papers" →
    read DEEP_RESEARCH_STRATEGY.md + this document Part 14

  extraction_ref/02_CHATBOX_CONTEXT.md
    Needs triage-mode variant: lighter context for Stage 1
    (abstract pre-extraction only, not full CSV-filling)

  docs/00_navigation/INDEX.md
    Needs entry for DEEP_RESEARCH_STRATEGY.md under
    Level 4 "Data Management" section

  extraction_ref/00_INDEX.md
    Needs entry referencing this pipeline for batch operations


─── SESSION TYPES FOR OUTSOURCED CHATBOXES ───

When outsourcing work to different AI chatboxes, each session type
needs specific context loaded:

SESSION TYPE A: "Discovery Session" (find candidate papers)
  Context to load:
    • DEEP_RESEARCH_STRATEGY.md Parts 1-8 (search queries + keywords)
    • DEEP_RESEARCH_STRATEGY.md Part 9 §9.4 (copy-paste prompt templates)
    • DEEP_RESEARCH_STRATEGY.md Part 9 §9.5 (controlled vocab bundles)
    • registries/EDGE_REGISTRY.csv (know what edges exist)
    • registries/PATHWAY_REGISTRY.csv (know pathway structure)
    • EXTRACTION_LOG.md (avoid re-discovering extracted papers)
    • This doc Part 14 vertical slice definition (know priority edges)
  Workflow:
    1. Pick 3-5 target edges from the vertical slice gap list
    2. Copy synonym bundles from §9.5 for those nodes
    3. Use Prompt A (§9.4) for edge discovery
    4. Use Prompt B (§9.4) to screen each candidate's abstract
    5. Record: DOI, title, year, edges covered, OA status
    6. Stop when each target edge has ≥2 candidates
  Output: DOI/PMID/title list with edge-mapping guesses + OA status
  Does NOT need: extraction_ref/, pipeline code, CSV templates

SESSION TYPE B: "Triage Session" (assess candidates — OPTIONAL)
  Useful when Discovery yielded many candidates and you want to
  prioritize before spending time on full extraction.
  Context to load:
    • This document Part 14 (pipeline stages + gates)
    • registries/EDGE_REGISTRY.csv (validate edge mapping)
    • registries/INSTRUMENT_REGISTRY.csv (validate instruments)
    • registries/NODE_REGISTRY.csv (validate constructs)
    • EXTRACTION_LOG.md (avoid re-processing known papers)
  Workflow:
    1. For each candidate from Session A, check abstract for:
       - Extractable statistics (β, SE, CI, OR, r, group means±SD)
       - Cancer-specific vs general population
       - Sample size (>30 preferred)
       - Study design (RCT > longitudinal > cross-sectional)
       - Instruments used (check against INSTRUMENT_REGISTRY)
    2. Rank candidates by: (a) edges covered (b) extractability
       (c) design quality (d) population match
    3. Kill papers with no extractability signals
  Output: prioritized extraction queue with edge mapping
  Does NOT need: full extraction_ref/, CSV templates

SESSION TYPE C: "Extraction Session" (full per-paper extraction)
  THIS IS THE MAIN WORK SESSION — produces actual data for the model.
  Context to load:
    • EXTRACTION_PLAYBOOK.md (Steps 0-9 — follow exactly)
    • extraction_ref/02_CHATBOX_CONTEXT.md (full pinned context)
    • registries/EDGE_REGISTRY.csv (validate edge IDs)
    • registries/INSTRUMENT_REGISTRY.csv (validate instrument IDs)
    • registries/NODE_REGISTRY.csv (validate node IDs)
    • EXTRACTION_LOG.md (avoid duplicates, see decision conventions)
    • The paper's PDF (attached or pasted as text)
    • If available: the Stage A/B metadata (edge mapping from discovery)
  Workflow:
    Per paper, follow EXTRACTION_PLAYBOOK.md Steps 0-9:
    1. Classify paper (DEEP/STANDARD/SHALLOW)
    2. Check/add edges to EDGE_REGISTRY
    3. Create folder in data/manual_uploads/structured/[doi-slug]/
    4. Fill edge_evidence_template.csv (REQUIRED)
    5. Fill population_norms_template.csv (RECOMMENDED)
    6. Fill context_priors_template.csv (RECOMMENDED)
    7. Fill optional templates if data available
    8. Create meta.json in data/manual_uploads/pdfs/
    9. Append entry to EXTRACTION_LOG.md
  Output: filled CSV templates + meta.json + EXTRACTION_LOG entry
  Human follow-up: copy PDFs, run load_evidence_into_db.py

SESSION TYPE D: "Audit Session" (post-extraction gap review)
  Context to load:
    • This document Part 14 (loop control logic)
    • EXTRACTION_LOG.md (what's been extracted)
    • DEEP_RESEARCH_STRATEGY.md Appendix B (edge gap list)
    • Optionally: run pathway_evidence_auditor output
  Workflow:
    1. Count evidence rows per edge in the vertical slice
    2. Identify edges still at k=0
    3. Identify edges where all evidence is low-quality
    4. Update priority list for next Discovery session
    5. Check if any spine papers from §9.3 remain unextracted
  Output: updated gap priorities, specific queries for next cycle


─── MANUAL-FIRST OPERATIONAL STANCE ───

As of 2026-02-27, the automated pipeline (Stages 0-2) is CODED but has
NEVER been tested against live APIs. The following components are missing
or unverified:

  NOT BUILT:
    • abstract_pre_extractor.py (Stage 1 — LLM abstract triage)
    • fulltext_extractability_scanner.py (Stage 1.5 — regex stat scan)
    • extraction_batch_optimizer.py (set-cover selection)
    • scripts/run_triage_sweep.py (CLI orchestrator)

  BUILT BUT UNTESTED AGAINST LIVE APIs:
    • All 5 source adapters (PubMed, Crossref, OpenAlex, EuropePMC, Unpaywall)
    • search_coordinator.py (multi-source orchestration)
    • aps_scorer.py (APS scoring)
    • query_generator.py (7 workstreams)
    • fulltext_retriever.py (PMC > Publisher > Unpaywall cascade)

  BLOCKING:
    • No API keys configured (NCBI_API_KEY, CROSSREF_MAILTO, etc.)
    • node_search_terms_v1 table is EMPTY (0 rows) — query generator
      falls back to splitting node IDs into words

THEREFORE: use the Manual Chatbox Retrieval Protocol
(DEEP_RESEARCH_STRATEGY.md Part 9) as the primary operational workflow.
The pipeline code is preserved for future activation when:
  1. node_search_terms_v1 is populated (§9.5 vocab → DB rows)
  2. API keys are configured
  3. Stage 1 + Stage 1.5 modules are built
  4. At least one end-to-end integration test passes


─── INTEGRATION AUDIT: RESEARCH ACQUISITION STRATEGY ALIGNMENT ───

Date: 2026-02-27
Prompted by review of proposed research acquisition strategy against
actual codebase. Findings:

ALREADY SOLVED (do not rebuild):
  1. Query Registry concept = node_search_terms_v1 + query_generator.py
  2. APS scoring = aps_scorer.py (formula matches strategy exactly)
  3. Gap auditing / coverage matrix = pathway_evidence_auditor.py
  4. Edge evidence schema = edge_evidence_v1 (71 columns, superset of
     the strategy's PAPER_PACKET template)
  5. Spine paper pathway = data/manual_uploads/ (operational, 18 rows)

GAPS TO ADDRESS (when moving to automation):
  1. Populate node_search_terms_v1 for vertical slice nodes (~100-200 rows)
     This is the single highest-ROI pre-automation task.
  2. Add extractability trigger terms to generate_edge_queries():
     AND ("95% CI" OR "standard error" OR "β" OR "effect size"
      OR "odds ratio" OR "regression" OR "mixed-effects")
  3. Add Workstream 8: Proxy Validity to query_generator.py
     Target: peripheral↔central biomarker R², especially BDNF
  4. Wire Unpaywall as automatic post-step in search_coordinator.py
  5. Build abstract_pre_extractor.py + fulltext_extractability_scanner.py
  6. Add is_sufficient(edge_id, min_grade) method to auditor

DO NOT BUILD (redundant with existing system):
  • Template A (Protocol Header) — belongs in docs/ as markdown
  • Template D (Chain Assembly) — algorithm layer already handles this
  • Separate "EDGE_PACKET" format — use existing edge_ontology_v1 +
    node_search_terms_v1 tables instead


═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
