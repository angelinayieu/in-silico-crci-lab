# Drama vs. CRCI: Deep Code Comparison

**Date:** February 25, 2026  
**Comparison Subject:** Drama vs. CRCI actual code implementation  
**Status:** Deep technical analysis of retrieval + extraction pipelines

---

## Executive Summary

| Aspect | Drama | CRCI (your code) |
|--------|-------|------------------|
| **Domain** | General open-domain analytics | Biomedical causal model for CRCI |
| **Collection Code** | `web_browser.py` + `web_augmenter.py` (2 agents) | `retrieval/` — 4 adapters + coordinator + scheduler + 6 support modules |
| **Extraction Code** | `data_transformer.py` (single MLLM) | `extraction/` — 10-phase pipeline + 11 specialist agents + trust boundary |
| **Lines of Code** | ~5K (estimated) | ~25K+ (retrieval: 3K, extraction: 15K, algorithm: 7K) |
| **Test Coverage** | Benchmarked on 200 tasks | 720 unit tests passing |
| **API Usage** | GPT-4o (single model) | Claude (via `llm/client.py`) with structured schemas |
| **Maturity** | Published SIGMOD 2025 | v1 complete (Phase 7); retrieval not yet tested E2E |

---

## Code Architecture Comparison

### Drama: 3 Stages, 5 Components

```
DramaBot
├── data_retriever/           # Coordinates collection + transformation
│   ├── web_browser.py        # Selenium-based web browsing (single-page, precise)
│   ├── web_augmenter.py      # OpenAI search tool (parallel, broad)
│   └── data_transformer.py   # MLLM extracts PDF → CSV
└── data_analyzer/            # NL2SQL code generation + execution
```

### CRCI: 7 Phases, 50+ Modules

```
crci/
├── retrieval/                        # ≈3,200 lines
│   ├── query_generator.py            # 523 lines — 7 workstream templates
│   ├── search_coordinator.py         # 176 lines — multi-adapter orchestration
│   ├── acquisition_scheduler.py      # 328 lines — 7-step cycle
│   ├── aps_scorer.py                 # 264 lines — 5-factor scoring
│   ├── fulltext_retriever.py         # 238 lines — source priority chain
│   ├── hop_discoverer.py             # 364 lines — SR constituent extraction
│   ├── abstract_screener.py          # 196 lines — relevance filtering
│   ├── id_resolver.py                # 230 lines — DOI/PMID cross-reference
│   ├── saturation_detector.py        # 292 lines — loop termination
│   ├── manual_upload_watcher.py      # 308 lines — 3 input methods
│   └── adapters/
│       ├── pubmed.py                 # 372 lines — NCBI E-utilities
│       ├── crossref.py               # Crossref REST API
│       ├── openalex.py               # OpenAlex search + citation
│       └── unpaywall.py              # 256 lines — OA route resolution
│
├── extraction/                       # ≈15,000 lines
│   ├── pipeline.py                   # 570 lines — 10-phase orchestrator
│   ├── p0_triage/                    # PDF ingestion + relevance screening
│   ├── p1_extraction/
│   │   ├── canonical_reader.py       # 636 lines — PaperMap builder
│   │   ├── agents/ (11 agents)
│   │   │   ├── ag01_metadata.py
│   │   │   ├── ag02_design.py
│   │   │   ├── ag03_cohort.py
│   │   │   ├── ag04_outcome.py       # 223 lines — instrument extraction
│   │   │   ├── ag05_stats_label.py
│   │   │   ├── ag06_exposure.py
│   │   │   ├── ag07_mediator.py
│   │   │   ├── ag08_temporal.py
│   │   │   ├── ag09_reconciliation.py
│   │   │   ├── ag10_strategic_intel.py
│   │   │   └── ag11_instrument_validation.py
│   │   └── base_agent.py             # 272 lines — agent framework
│   ├── tb_trust_boundary/            # Numeric + annotation validation
│   ├── p2_harmonization/             # 237+ lines — plausibility/conversion
│   ├── p3_heterogeneity/             # 7-layer calibration
│   ├── p4_aggregation/               # 365+ lines — IVW, DCR, lineage
│   ├── p4b_publication_bias/
│   ├── p5_sufficiency/
│   ├── p6_deployment/
│   └── p7_compilers/
│
├── algorithm/                        # ≈7,000 lines
│   ├── chain_a_graph/
│   ├── chain_b_evidence/
│   ├── chain_c_posterior/
│   ├── chain_d_simulation/
│   ├── chain_e_temporal/
│   └── chain_f_analytics/
│
└── llm/
    └── client.py                     # 266 lines — Claude API wrapper
```

---

## Deep Code Comparison: Stage-by-Stage

### Stage 1: Collection — Actual Code Patterns

#### Drama: Web Browser Agent (2 agents, ~1K lines)

```python
# Drama's web_browser.py — simplified
class WebBrowser:
    def collect(self, query: str, blacklist: set[str]) -> tuple[Data, Sources]:
        # 1. Google search
        self.driver.get("https://google.com")
        self.type(query)
        
        # 2. Navigate iteratively via screenshot + LLM decision
        for step in range(max_steps):
            screenshot = self.driver.screenshot()
            action = self.llm.choose_action(screenshot, query)
            
            if action.type == "Click":
                self.click(action.target)
            elif action.type == "GetData":
                return self._extract_csv_from_page(), self.visited_urls
            elif action.type == "Download":
                return self._download_file(), self.visited_urls
        
        # Fallback: web_augmenter (parallel search)
        return self.augmenter.search(query)
```

#### CRCI: AcquisitionScheduler (7-step cycle, 328 lines)

Your actual code in [acquisition_scheduler.py](crci/retrieval/acquisition_scheduler.py):

```python
# CRCI's run_acquisition_cycle() — from your code
def run_acquisition_cycle(session, workstreams, max_papers, dry_run, cycle_number):
    # Step 1: Generate queries (query_generator.generate_all)
    queries = query_generator.generate_all(session, workstreams=workstreams)
    
    # Step 2: Search across sources (search_coordinator.search)
    coordinator = SearchCoordinator(session)
    candidates = coordinator.search(queries)
    
    # Step 2b: Cross-resolve DOI ↔ PMID (id_resolver.resolve_candidate_ids)
    candidates = resolve_candidate_ids(candidates)
    
    # Step 2c: Abstract screening (abstract_screener.screen_batch)
    candidates = screen_abstracts(candidates, threshold=0.5)
    
    # Step 3: APS scoring (aps_scorer.score_candidates)
    scored = score_candidates(candidates)
    
    # Step 4: Fulltext retrieval (fulltext_retriever.retrieve_batch)
    retriever = FulltextRetriever(session)
    results = retriever.retrieve_batch(scored, max_retrievals=max_papers)
    
    # Step 5: Hop discovery (hop_discoverer.run_hop_discovery)
    hop_candidates_queued = run_hop_discovery(session)
    
    # Step 6: Saturation check (saturation_detector.check_saturation)
    sat_report = check_saturation(session, cycle_number)
    
    return report
```

**Key Differences:**

| Feature | Drama | CRCI |
|---------|-------|------|
| **Step count** | 2 agents (browser + augmenter) | 7 explicit steps |
| **Query source** | User's natural language question | Class A registries (edges, nodes, instruments) |
| **Deduplication** | Implicit (LLM avoids duplicates) | Explicit (DOI/PMID cross-resolution via NCBI ID Converter) |
| **Screening** | None (trust LLM to ignore irrelevant) | Formula-based: `SCREEN-1` with keyword intersection score |
| **Scoring** | None (order by LLM relevance) | 5-factor APS: `APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch + 0.15·Recency + 0.10·SourceQuality` |
| **Hop discovery** | Web augmenter's parallel search | Explicit: extract `included_study_ids_json` from meta-analyses |
| **Saturation** | None (exit on user request) | Formula: `novelty_ratio < SATURATION_THRESHOLD` for N consecutive cycles |
| **Budget control** | Implicit (single run) | Explicit: `MAX_QUERIES_PER_DAY`, `MAX_FULLTEXT_PER_DAY`, etc. |

---

### Stage 2: Extraction — Actual Code Patterns

#### Drama: Data Transformer (single MLLM, ~1K lines)

```python
# Drama's data_transformer.py — simplified
class DataTransformer:
    def transform(self, query: str, raw_data: list[File]) -> DataFrame:
        T = pd.DataFrame()
        L = []  # Files already checked
        
        for iteration in range(max_iterations):
            # Check if data is adequate
            valid, missing = self.check_adequate_info(query, T)
            if valid:
                return T
            
            # Select next file
            F = self.file_selection(query, missing, raw_data, L)
            
            # Extract data from file (MLLM page-by-page)
            T_prime = self.extract_data(query, missing, F)
            
            # Merge
            T = self.aggregate_tables(T, T_prime, query, missing)
            L.append(F)
        
        return T
    
    def extract_data(self, query, missing, file):
        # For PDFs: page-by-page MLLM extraction
        T_prime = pd.DataFrame()
        for page in pdf.pages:
            response = gpt4o(page, context=T_prime, missing_info=missing)
            T_prime = self.update_table(T_prime, response)
        return T_prime
```

#### CRCI: 10-Phase Pipeline (15K lines, 11 agents)

Your actual code in [pipeline.py](crci/extraction/pipeline.py):

```python
# CRCI's _CHAIN_SEQUENCE — from your code
_CHAIN_SEQUENCE = [
    (PipelineStage.P0_TRIAGE, "P0: Pre-Extraction Triage", "p0_triage.runner", "run_p0_triage"),
    (PipelineStage.P1_EXTRACTION, "P1: Hybrid Multi-Agent Extraction", "p1_extraction.runner", "run_p1_extraction"),
    (PipelineStage.TB_TRUST_BOUNDARY, "TB: Trust Boundary", "tb_trust_boundary.runner", "run_tb_trust_boundary"),
    (PipelineStage.P2_HARMONIZATION, "P2: Harmonization & Gating", "p2_harmonization.runner", "run_p2_harmonization"),
    (PipelineStage.P3_ASSIMILATION, "P3: Seven-Layer Heterogeneity", "p3_heterogeneity.runner", "run_p3_heterogeneity"),
    (PipelineStage.P4_AGGREGATION, "P4: Aggregation + DCR", "p4_aggregation.runner", "run_p4_aggregation"),
    (PipelineStage.P4_AGGREGATION, "P4B: Publication Bias Assessment", "p4b_publication_bias.runner", "run_p4b_publication_bias"),
    (PipelineStage.P5_SUFFICIENCY, "P5: Sufficiency & Coherence", "p5_sufficiency.runner", "run_p5_sufficiency"),
    (PipelineStage.P6_DEPLOYMENT_VALIDATION, "P6: Deployment Validation", "p6_deployment.runner", "run_p6_deployment_validation"),
    (PipelineStage.P7_COMPILATION, "P7: Full-Spectrum Parameter Compilation", "p7_compilers.runner", "run_p7_compilation"),
]
```

Your P1 extraction (from [p1_extraction/runner.py](crci/extraction/p1_extraction/runner.py)):

```python
def run_p1_extraction(session, run, context):
    # P1-CR: Canonical Reader — build PaperMap
    reader = CanonicalReader(llm_client)
    paper_map = reader.read(paper_id, canonical_text)  # 636 lines of PaperMap logic
    
    # P1-MAP: MA multi-product plan (for systematic reviews)
    if paper_type in ["SR", "MA"]:
        ma_plan = build_ma_extraction_plan(paper_map)
    
    # P1-AG: 11 agents run in parallel
    agents = [
        AG01_Metadata, AG02_Design, AG03_Cohort, AG04_Outcome,
        AG05_StatsLabel, AG06_Exposure, AG07_Mediator, AG08_Temporal,
        AG09_Reconciliation, AG10_StrategicIntel, AG11_InstrumentValidation
    ]
    agent_outputs = parallel_execute(agents, paper_map)
    
    # P1-REC: Reconciliation — cross-agent consensus
    reconciled = reconcile(agent_outputs)
    
    # P1-ATB: Annotation Trust Boundary
    validated = annotation_trust_boundary(reconciled)
    
    return context
```

**Key Differences:**

| Feature | Drama | CRCI |
|---------|-------|------|
| **Extraction model** | Single MLLM (GPT-4o) | 11 specialist agents (Claude via `llm/client.py`) |
| **Structure awareness** | Page-by-page accumulation | PaperMap with sections, tables, figures, spans |
| **Quality gates** | Code execution validation | 6 explicit gates (P0-G1 through P6-G2) |
| **Trust model** | Implicit (LLM correctness) | Explicit: `tb_trust_boundary/` with confidence + provenance |
| **Schema validation** | Ad-hoc (column renaming) | Pydantic schemas per agent (`response_schemas.py`) |
| **Reconciliation** | None (single MLLM) | Cross-agent consensus (`reconciliation.py`) |
| **Numeric validation** | None | `numeric_parser.py` + `consistency_checker.py` |

---

## Feature-by-Feature Code Comparison

### 1. Query Generation

**Drama:** Natural language → LLM search terms
```python
search_term = llm.generate_search_term(user_query)
google.search(search_term)
```

**CRCI:** Template expansion from registries (your [query_generator.py](crci/retrieval/query_generator.py)):
```python
def generate_edge_queries(session, edge_ids):
    requests = []
    for edge in edges:
        node_x_terms = _get_node_synonyms(session, edge.node_x)  # From node_search_terms_v1
        node_y_terms = _get_node_synonyms(session, edge.node_y)
        
        q1 = f'{_build_or_clause(node_x_terms)} AND {_build_or_clause(node_y_terms)} ' \
             f'AND (cancer OR chemotherapy) AND (cognitive OR cognition OR CRCI)'
        
        requests.append(APSQueryRequest(
            query_string=q1,
            target_entity_id=edge.edge_relation_id,
            workstream="edge_evidence",
        ))
    return requests
```

**CRCI Advantage:** Deterministic, reproducible, registry-driven.  
**Drama Advantage:** Handles novel domains without pre-curated registry.

---

### 2. Candidate Scoring

**Drama:** No explicit scoring — relies on search engine ranking + LLM selection.

**CRCI:** 5-factor APS formula (your [aps_scorer.py](crci/retrieval/aps_scorer.py)):
```python
def score_candidate(candidate, gap_edges):
    components = {
        "edge_gap": _score_edge_gap(candidate, gap_edges),          # 0.35 weight
        "design_bonus": _score_design_bonus(candidate),              # 0.20 weight
        "pop_match": _score_pop_match(candidate),                    # 0.20 weight
        "recency": _score_recency(candidate),                        # 0.15 weight
        "source_quality": _score_source_quality(candidate),          # 0.10 weight
    }
    aps = sum(w * components[k] for k, w in APS_WEIGHTS.items())
    
    # Author-gap boost (from study_annotations_v1.research_gap)
    if _has_author_gap_flag(candidate):
        aps = min(1.0, aps * 1.5)
    
    return aps
```

**CRCI Advantage:** Transparent, auditable scoring with domain-specific factors.  
**Drama Advantage:** Simpler; no manual weight tuning.

---

### 3. Fulltext Retrieval

**Drama:** Browser download or curl
```python
if action == "Download":
    self.driver.click(download_button)
    wait_for_download()
```

**CRCI:** Source priority chain (your [fulltext_retriever.py](crci/retrieval/fulltext_retriever.py)):
```python
def _retrieve_single(self, scored):
    for source_name in config.FULLTEXT_SOURCE_PRIORITY:  # ["europe_pmc", "unpaywall"]
        adapter = self._ft_adapters.get(source_name)
        if adapter is None:
            continue
        
        identifier = scored.candidate.pmcid if source_name == "europe_pmc" else scored.candidate.doi
        result = adapter.fetch_fulltext(identifier)
        
        if result.status == "SUCCESS":
            self._cache_dir.write(result.content)
            return RetrievalResult(status=RetrievalStatus.RETRIEVED, path=...)
    
    return RetrievalResult(status=RetrievalStatus.ABSTRACT_ONLY)  # Fallback
```

**CRCI Advantage:** Explicit OA status tracking (gold/green/closed), legal compliance.  
**Drama Advantage:** Can bypass paywalls via browser simulation.

---

### 4. Hop Discovery (Systematic Review Expansion)

**Drama:** Web augmenter parallel search with broader queries.

**CRCI:** Meta-analysis included study extraction (your [hop_discoverer.py](crci/retrieval/hop_discoverer.py)):
```python
def discover_hops_from_meta_analyses(session):
    # Find meta-analyses with included study lists
    ma_rows = session.execute(
        select(StudyRegistry.study_id, StudyRegistry.included_study_ids_json)
        .where(StudyRegistry.study_subtype.in_(["pairwise_ma", "nma", "ipdma"]))
    ).all()
    
    for row in ma_rows:
        included_ids = json.loads(row.included_study_ids_json)
        target_edges = _get_ma_edge_ids(session, row.study_id)
        
        for entry in included_ids:
            if entry["doi"] not in known_dois:  # Gate HOP-G2: dedup
                session.add(AcquisitionQueue(
                    candidate_doi=entry["doi"],
                    aps_score=config.HOP_CITATION_APS_BOOST,  # +0.15
                    hop_source_study_id=row.study_id,
                    hop_depth=1,  # Gate HOP-G1: max depth
                ))
```

**CRCI Advantage:** Extracts exact constituent studies from MA authors' reference lists.  
**Drama Advantage:** Can discover related papers not explicitly cited.

---

### 5. Extraction Agent Architecture

**Drama:** Single MLLM with page-by-page accumulation
```python
for page in pdf.pages:
    response = gpt4o.extract(page_image, context=prior_table, missing=M)
    table = merge(table, response)
```

**CRCI:** 11 specialist agents (your [base_agent.py](crci/extraction/p1_extraction/agents/base_agent.py)):
```python
class BaseAgent(ABC):
    @property
    @abstractmethod
    def agent_id(self) -> str: ...  # e.g., "AG04"
    
    @property
    @abstractmethod
    def target_sections(self) -> list[str]: ...  # e.g., ["methods", "results"]
    
    @property
    @abstractmethod
    def response_schema(self) -> type[BaseModel]: ...  # Pydantic schema
    
    def run(self, paper_map: PaperMap) -> AgentOutput:
        focused_text = self._focus_sections(paper_map)
        prompt = self._build_prompt(focused_text, paper_map)
        response = self._llm_client.call(prompt, self.response_schema)
        return self._parse_response(response, paper_map)
```

Example: AG04_Outcome (your [ag04_outcome.py](crci/extraction/p1_extraction/agents/ag04_outcome.py)):
```python
class OutcomeAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "AG04"
    
    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results"]
    
    def _parse_response(self, response, paper_map) -> AgentOutput:
        outcome_resp: OutcomeResponse = response
        return AgentOutput(
            agent_id="AG04",
            span_labels=[...],  # SpanLabel[] for numeric trust boundary
            annotations=[...],  # RawAnnotationEmission[] for annotation trust
        )
```

**CRCI Advantage:** Domain expertise encoded per agent; schema-validated outputs.  
**Drama Advantage:** Simpler; single model handles all extraction.

---

### 6. Trust Boundary

**Drama:** Code execution validation
```python
try:
    result = execute_code(generated_sql, table)
    if is_plausible(result):
        return result
except:
    return fallback_answer
```

**CRCI:** Multi-stage validation (your [tb_trust_boundary/runner.py](crci/extraction/tb_trust_boundary/runner.py)):
```python
def run_tb_trust_boundary(session, run, context):
    # TB-S1: Numeric Parser — parse and type-check raw claims
    parsed_numerics = parse_spans(context["all_span_labels"])
    valid_claims = [p for p in parsed_numerics if p.parse_status == "CLEAN"]
    
    # TB-S2: Consistency Checker — cross-validate related claims
    consistency_result = check_consistency(valid_claims, paper_id)
    
    return context  # Contains validated/warnings/rejected
```

**CRCI Advantage:** Explicit provenance codes, confidence scores, evidence trail.  
**Drama Advantage:** Simpler; validation via execution.

---

## Summary: What Each System Does Better

### Drama Wins On

| Feature | Why |
|---------|-----|
| **Speed** | Single LLM call → answer in ~1.5 min |
| **Cost** | $0.05/task (minimal API usage) |
| **Flexibility** | Handles any web data format |
| **Simplicity** | 3-stage pipeline vs. 10-phase |
| **Novel domains** | No registry curation required |

### CRCI Wins On

| Feature | Why |
|---------|-----|
| **Domain depth** | 11 specialized agents for biomedical extraction |
| **Reproducibility** | Deterministic templates, formula IDs, gate enforcement |
| **Quality assurance** | Trust boundary + 6 gates + 720 tests |
| **Causal reasoning** | Full Bayesian DAG + MC simulation |
| **Auditability** | Provenance codes, evidence trails, extraction logs |
| **Patient personalization** | Per-patient state inference |

---

## What CRCI Could Adopt from Drama

### Pattern 1: Multi-Agent Coordination

Drama's **data retriever** coordinates two complementary sub-agents:
- **Web browser:** Fine-grained, step-by-step exploration of narrow sources
- **Web augmenter:** Broad parallel search over many sources

**Result:** 63.5% of tasks use web browser (91.2% accuracy); 36.5% use web augmenter (68% accuracy).  
**CRCI could apply:** Coordinate PubMed (precise, structured) + OpenAlex (broad, citation graph) adaptively based on paper type.

### 2. **Incremental Data Accumulation**

Drama's data transformer maintains a list `L` of processed files and iteratively:
1. `check_adequate_info(Q, T)` — Is the structured table `T` sufficient to answer `Q`?
2. If NO → identify missing information `M`
3. `file_selection()` — Pick next file likely to have `M`
4. `extract_data()` — Extract `M` from that file incrementally
5. `update_database(T, T')` — Merge new data

**CRCI already does this** in `p1_extraction/` → `p2_harmonization/` → `p4_aggregation/`, but **could benefit from** explicit `check_adequate_info()` gates that halt when SE estimates drop below confidence thresholds.

### 3. **Source Reliability Ranking**

Drama's *rank_website* function:
```
rank_website(Q, sources, response, code, inline_annotations) → ranked_sources
```

Ranks sources by:
- Relevance to query `Q`
- Contribution to response generation
- Authoritativeness (government >> academic >> blog)

**CRCI could apply:** Rank papers by:
- Publication venue (Nature > journal > preprint)
- Study design (RCT > cohort > case report)
- Methodological quality (PEDro score, GRADE)
- Relevance to edges in registry

### 4. **Explicit Workload Distribution**

Drama reports workload share (Table 7):
- Web browser: 63.5% of tasks, 91.2% accuracy
- Web augmenter: 36.5% of tasks, 68% accuracy

**Insight:** Assign hard tasks to precise agent; use broad agent as fallback.

**CRCI could apply:** 
- Easy queries (single-node evidence) → PubMed direct search
- Complex queries (multi-pathway, contradictory) → OpenAlex citation graph + broad screening

### 5. **Sampling Strategy for Unstructured Data**

Drama's approach to PDFs:
```python
for page in pdf.pages:
    T' = MLLM(page, context=T', M=missing_info)  # Incremental expansion
    if check_adequate_info(T', M):
        break
```

**CRCI could apply:** Instead of extracting all tables from a paper, extract **adaptively**:
1. First 50 pages: abstract + methods + results overview
2. Missing: (e.g., mechanism data) → search deeper into results
3. Missing: (e.g., patient count) → extract from tables on demand

---

## Lessons CRCI Offers Back to Drama

### 1. **Domain-Specific Evidence Quality**

CRCI's **trust boundary** is a generalizable pattern:
```python
@dataclass
class EvidenceClaim:
    value: float
    se: float
    confidence: Confidence  # 0–1
    provenance: ProvenanceCode  # FOUND_IN_TEXT, ESTIMATED, INFERRED
    source_text: str  # Original quote or figure caption
    agent_id: str  # Which NLP agent extracted this
    datetime_extracted: datetime
```

**Drama could adopt:** Annotate every data cell with `(value, confidence, source_url, extraction_method)`.  
This would:
- Enable conflict resolution (pick highest-confidence estimate)
- Support explainability (user can drill down to source)
- Allow graceful degradation (use lower-confidence data if better not available)

### 2. **Gate-Based Validation**

CRCI's gate system:
```python
if spectral_radius > MAX_SPECTRAL_RADIUS:
    raise GateViolation("P2-G1", f"Spectral radius {spectral_radius} exceeds {MAX_SPECTRAL_RADIUS}")
```

**Drama could adopt:**
```python
# After code generation
code_gates = [
    ("execution_success", exec(code) does not raise),
    ("result_type_match", type(result) == expected_type),
    ("result_plausibility", result in expected_range),
]
for gate_id, gate_check in code_gates:
    if not gate_check:
        raise GateViolation(gate_id, ...)
```

### 3. **Explicit Heterogeneity Modeling**

CRCI's **p3_heterogeneity/** stage explicitly classifies study types:
- Mechanistic vs. clinical
- Animal vs. human
- Observational vs. experimental

**Drama could adopt:** Before aggregating data from multiple sources, classify them:
- Official government source vs. NGO vs. news article
- Primary data vs. summary statistic vs. estimate
- 2023 data vs. 2022 vs. "latest available"

This would prevent mixing (e.g., averaging apples + oranges).

---

## Integrated Vision: Drama + CRCI = Next-Gen Evidence Pipeline

### Scenario: Automated Systematic Review & Causal Model

**Using Drama's collection/transformation + CRCI's causal analysis:**

```
User Goal: "Compile evidence for mindfulness → cognitive improvement 
            in breast cancer survivors"

Phase 1: Automated Retrieval (Drama-style)
──────────────────────────────────
  Query Generator (from CRCI registries)
      → "mindfulness" + "breast cancer" + "cognition" + "RCT"
  
  Multi-agent Collection (Drama's web browser + augmenter)
      → PubMed search (narrow, precise)
      → OpenAlex citation graph (broad, contextualized)
      → Hop discovery (systematic reviews citing Cifu 2018)
  
  Adaptive Scoring & Retrieval (CRCI's APS + Drama's ranking)
      → Rank by: relevance + methodological quality + paywall status
      → Download w/ Unpaywall + PMC + Firecrawl fallback

Phase 2: Transformation & Extraction
──────────────────────────────────
  PDF Ingestion (CRCI's p0_triage extends Drama's per-page strategy)
      → Page-by-page extraction (Drama's incremental approach)
      → Study-level evidence assembly (CRCI's 11-agent team)
  
  Harmonization & Trust (CRCI's p2 + tb_boundary with Drama's source ranking)
      → Normalize: Cohen's d → Hedges' g
      → Annotate: journal impact + sample size + risk of bias
      → Mark: which claims from which papers

Phase 3: Causal Analysis & Inference
──────────────────────────────────
  Compile DAG (CRCI's chain_a)
      → 12 nodes × 8 edges (extracted + registered)
  
  Meta-analyze Evidence (CRCI's chain_b with Drama's code-generation style)
      → IVW per edge → posterior β̂ + SE
      → Can generate SQL-like "show me the evidence" queries per edge
  
  Patient Inference & Simulation (CRCI's chain_c + d)
      → Given: patient questionnaire responses
      → Infer: likelihood to benefit from mindfulness (vs. other interventions)
  
  Explanation (CRCI's presentation + Drama's traceability)
      → "Patient risk: 7.2/10. Key factors: baseline PSQI=18 (high),
         age=52 (median). Mindfulness predicted to reduce CRCI by 2.1 points
         (95% CI: 0.5–3.7) over 12 weeks, vs. cognitive training (1.8 points)
         and exercise (1.5 points). Evidence comes from N=5 RCTs, publication
         bias-adjusted with Egger's p=0.23."
      → Interactive: drill down to original papers, see figures, check trust scores
```

---

## Recommendations for CRCI Integration

### Short-term (v1 completion):
1. **Extend hop_discoverer** per Drama's web augmenter model — parallel OpenAlex + Crossref searches
2. **Add source confidence scoring** to acquisition_queue (Drama's rank_website pattern)
3. **Test fulltext_retriever** end-to-end with 5 systematic reviews

### Medium-term (v2):
1. **Migrate query_generator** to use multiple strategies per workstream (Drama's per-task tuning)
2. **Implement incremental adequacy checks** in p1_extraction (Drama's check_adequate_info pattern)
3. **Add explicit heterogeneity scoring** to acquisition (document type, source authority, temporal currency)

### Long-term (v3+):
1. **Unified evidence cell schema:** `(value, confidence, source, extraction_method, datetime)`
2. **Code-generation analyses:** Generate SQL-like queries "show me RCT evidence for this edge"
3. **Horizontal retrieval scaling:** Parallelize adapters, extraction agents, algorithm chains

---

## Conclusion

| Dimension | Winner | Why |
|-----------|--------|-----|
| **General-purpose data analytics** | Drama | Handles arbitrary web data, fast iteration, low cost |
| **Biomedical evidence synthesis** | CRCI | Deep domain knowledge, causal reasoning, clinical output |
| **Architecture elegance** | Tie | Drama: simple 3-stage unification; CRCI: complex but principled gate system |
| **Maturity** | Drama | 86.5% accuracy on benchmark; CRCI at early integration phase |
| **Explainability** | CRCI | Trust boundary + provenance; Drama relies on code execution validation |
| **Extensibility** | CRCI | Registry-driven design scales to new nodes/edges; Drama requires prompt tuning |

**Optimal design for future CRCI v2:** Keep CRCI's specialized domain reasoning; adopt Drama's multi-agent coordination patterns for retrieval and transformation stages.

