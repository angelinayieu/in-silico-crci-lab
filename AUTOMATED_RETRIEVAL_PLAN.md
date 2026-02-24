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
END
═══════════════════════════════════════════════════════════════════════════
