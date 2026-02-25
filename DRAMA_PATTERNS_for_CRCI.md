# Drama → CRCI: Concrete Implementation Patterns

**Purpose:** Specific code patterns from Drama that CRCI could adopt to improve retrieval & transformation efficiency.

---

## Pattern 1: Multi-Agent Workload Coordination

### Drama's Approach

```python
# Drama: Web browser (fine-grained) + Web augmenter (broad) coordination
# Table 7: Web browser 63.5% accuracy, Web augmenter 36.5% accuracy
# But together they achieve 86.5%

class DataRetriever:
    def __init__(self, web_browser, web_augmenter):
        self.browser = web_browser  # ~91% accuracy (narrow)
        self.augmenter = web_augmenter  # ~68% accuracy (broad)
        self.S = set()  # sources accumulated
        
    def retrieve(self, query, blacklist):
        # Step 1: Try detailed exploration first
        data_D, sources_S_browser = self.browser.collect(query, blacklist)
        
        # Step 2: Assess adequacy
        if self.data_transformer.check_adequate_info(data_D, query):
            return data_D, sources_S_browser
        
        # Step 3: Fall back to broad search
        data_D_broad, sources_S_broad = self.augmenter.search(query, blacklist)
        
        # Step 4: Merge carefully (verify sources not blacklisted)
        if all(s not in blacklist for s in sources_S_broad):
            return data_D + data_D_broad, sources_S_browser | sources_S_broad
        else:
            # Clean and retry
            sources_clean = sources_S_broad - blacklist
            return self.browser.explore_sources(sources_clean)
```

### Applied to CRCI

```python
# CRCI: PubMed (precise) + OpenAlex (broad) coordination

class QueryCoordinator:
    def __init__(self):
        self.pubmed = PubMedAdapter()      # ~90% precision (RCTs, abstracts available)
        self.openalex = OpenAlexAdapter()  # ~70% recall (citation graph, broad)
        self.crossref = CrossrefAdapter()  # ~80% (DOI resolution)
        
    def acquire(self, node_ids: list[str], edge_ids: list[str]) -> AcquisitionQueue:
        """
        Strategy:
        1. PubMed: High-precision searches for edge-specific queries
        2. OpenAlex: Discover citing/cited papers (systematic review chains)
        3. Crossref: Validate DOIs + get reference lists
        """
        results = {}
        
        # Phase A: Precise PubMed queries (Drama's "browser" equivalent)
        for edge_id in edge_ids:
            query = self.generate_boolean_query(edge_id)
            pmid_results = self.pubmed.search(query)
            results[edge_id] = pmid_results
            
            # Check adequacy: do we have N >= 3 studies?
            if len(pmid_results) >= 3:
                continue
                
            # Phase B: Broad OpenAlex search (Drama's "augmenter" equivalent)
            missing = 3 - len(pmid_results)
            aa_results = self.openalex.find_citing_papers(
                edge_id, count=missing*2
            )
            results[edge_id].extend(aa_results)
        
        # Phase C: Merge and deduplicate
        queue = AcquisitionQueue()
        for edge_id, paper_list in results.items():
            for paper in paper_list:
                if paper.pmid not in queue.pmids_seen:
                    queue.add(
                        pmid=paper.pmid,
                        edge_id=edge_id,
                        source='pubmed' if paper.source=='pm' else 'openalex',
                        aps_score=self.aps_scorer.score(paper, edge_id)
                    )
        
        return queue
```

**Benefits:**
- Avoids redundant searches (PubMed finds obvious papers; OpenAlex fills gaps)
- Clear division of labor (Drama's approach)
- Recovers gracefully from adapter failures
- Trackable sources for reproducibility

---

## Pattern 2: Incremental Adequacy Checking

### Drama's Approach

```python
def check_adequate_info(query: str, structured_table: DataFrame) -> Tuple[bool, List[str]]:
    """
    Determine: (1) Is there enough data? (2) If not, what's missing?
    
    Drama's strategy: Try to generate executable code. If it works, data is adequate.
    """
    try:
        code = llm_generate_code(query, table=structured_table)
        result = execute_code(code, structured_table)
        
        if result is not None and is_plausible(result, query):
            return True, []
        else:
            # Code executed but result doesn't make sense
            return False, ["Result type mismatch or out of expected range"]
            
    except CodeExecutionError as e:
        # Code couldn't execute — data is missing
        # Extract missing column/condition from error message
        missing = parse_missing_from_error(str(e))
        return False, missing
```

### Applied to CRCI

```python
class ExtractionAdequacyChecker:
    """
    Instead of: "Process all 50 pages + all tables"
    Ask: "Do we have enough data to answer this edge question?"
    """
    
    def check_adequate_info_for_edge(self, edge_id: str, extracted_data: Dict) -> Tuple[bool, List[str]]:
        """
        Edge needs: (1) N >= 3 studies, (2) effect sizes, (3) SDs or N per group
        Missing anything? Flag it so extraction agent targets it.
        """
        required_fields = {
            'effect_size': (float, "β or d or OR"),
            'se': (float, "Standard error or CI"),
            'sample_size': (int, "Total N or n1, n2"),
            'study_type': (str, "RCT, cohort, case, etc."),
        }
        
        missing_fields = []
        for field, (ftype, description) in required_fields.items():
            if field not in extracted_data or extracted_data[field] is None:
                missing_fields.append(f"{field}: {description}")
        
        # Check: Can we meta-analyze with what we have?
        try:
            estimates = [d['effect_size'] for d in extracted_data.values() 
                        if 'effect_size' in d and d['effect_size'] is not None]
            
            if len(estimates) >= 3:
                # Attempt IVW
                result = ivw_meta_analyze(estimates, extracted_data)
                
                if result.se < 0.5:  # CRCI confidence threshold
                    return True, []
                else:
                    return False, ["Heterogeneity too high (se > 0.5)"]
            else:
                return False, [f"Only {len(estimates)} estimates, need ≥3"]
                
        except Exception as e:
            return False, [f"Meta-analysis failed: {str(e)}"]
    
    def extraction_guidance(self, edge_id: str, missing_list: List[str]) -> str:
        """
        Tell the NLP agent what to search for next
        
        Example output:
        "For edge CRCI→PSQI: We have 2 studies but need ≥3.
         Missing from study #2: sample_size (try 'N = 120' in methods).
         Missing from study #3: effect_size (convert figure data to Cohen's d)."
        """
        return f"For edge {edge_id}: {', '.join(missing_list)}"
```

**Benefits:**
- Prevents over-extraction (stops early when adequate data exists)
- Guides agent effort (tells NLP what to search for)
- Measures extraction quality objectively (can we actually use the data?)
- Matches Drama's code-execution validation approach

---

## Pattern 3: Source Ranking by Contribution

### Drama's Approach

```python
def rank_website(query: str, sources: List[str], response: str, code: str, 
                 inline_annotations: Dict[str, List[str]]) -> List[Tuple[str, float]]:
    """
    Rank sources 0–1 by: How much did each contribute to generating the answer?
    
    Example inline_annotations:
    {
        "hypothesis.org": ["Line 1-5 of response uses this source"],
        "census.gov": ["Line 6-10, also cited in generated code query"],
        "unverified-blog.com": ["No contribution — ignored"],
    }
    """
    
    scored = []
    for source in sources:
        if source not in inline_annotations or not inline_annotations[source]:
            score = 0.0  # Source not used
        else:
            # Score: fraction of response that used this source
            lines_from_source = len(inline_annotations[source])
            total_lines = response.count('\n')
            contribution = lines_from_source / max(total_lines, 1)
            
            # Boost for official sources
            if is_authoritative(source):  # .gov, .org, major publisher
                contribution *= 1.3
            
            score = min(contribution, 1.0)
        
        scored.append((source, score))
    
    return sorted(scored, key=lambda x: x[1], reverse=True)
```

### Applied to CRCI

```python
class PaperSourceRanker:
    """
    Rank papers by contribution to the compiled causal model
    
    Score factors:
    - How many of our target edges does this paper address?
    - What methodological quality?
    - How recent?
    - How much unique information vs. overlap with others?
    """
    
    def score_paper(self, paper: PaperRecord, target_edges: List[str]) -> float:
        """
        Scoring function: 0–1, for acquisition priority
        """
        score = 0.0
        
        # Factor 1: Relevance to target edges
        edges_addressed = self.get_edges_from_abstract(paper)
        overlap = len(edges_addressed & set(target_edges))
        relevance_score = overlap / len(target_edges)  # 0–1
        
        # Factor 2: Methodological quality (GRADE / PEDro)
        quality_score = self.estimate_quality(paper.study_type, paper.sample_size)
        
        # Factor 3: Recency (prefer ≤5 years old)
        years_old = datetime.now().year - paper.year
        recency_score = max(0, 1 - years_old / 10)  # Linear decay
        
        # Factor 4: Uniqueness (avoid redundant papers)
        overlap_with_known = self.overlap_detector.estimate_redundancy(paper)
        uniqueness_score = 1 - overlap_with_known  # 0–1
        
        # Combine: weighted average
        score = (0.5 * relevance_score + 
                0.3 * quality_score + 
                0.1 * recency_score + 
                0.1 * uniqueness_score)
        
        return score
    
    def rank_acquisition_queue(self, candidates: List[PaperRecord], 
                               target_edges: List[str]) -> List[PaperRecord]:
        """
        Sort queue by descending score.
        
        High-priority (score > 0.7): Download fulltext
        Medium-priority (0.4–0.7): Review abstract, decide on fulltext
        Low-priority (< 0.4): Skip or defer
        """
        
        scored = [(p, self.score_paper(p, target_edges)) for p in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        for paper, score in scored:
            if score > 0.7:
                paper.priority = "HIGH"
            elif score > 0.4:
                paper.priority = "MEDIUM"
            else:
                paper.priority = "LOW"
        
        return [p for p, _ in scored]
```

**Benefits:**
- Objective prioritization (scores are reproducible)
- Matches Drama's ranking logic
- Reduces wasted effort (skip low-contribution papers)
- Explains acquisition decisions (transparent scoring)

---

## Pattern 4: Incremental Data Accumulation with Fallback

### Drama's Approach

```python
for iteration in range(max_iterations):
    # Phase 1: Check if we have enough
    valid, missing = check_adequate_info(query, current_data)
    if valid:
        return current_data, sources_used
    
    # Phase 2: Try precise method (web_browser)
    data_precise, sources_precise = web_browser.collect(query, blacklist)
    current_data = merge(current_data, data_precise)
    sources_used |= sources_precise
    
    # Phase 3: If still insufficient, try broad method (web_augmenter)
    valid, missing = check_adequate_info(query, current_data)
    if valid:
        return current_data, sources_used
    
    data_broad, sources_broad = web_augmenter.search(query, blacklist)
    current_data = merge(current_data, data_broad)
    sources_used |= sources_broad
    
    # Phase 4: Fallback to LLM-driven refinement
    if not valid:
        refined_query = llm_refine_query(query, missing)
        # Continue loop with refined_query
```

### Applied to CRCI

```python
class AdaptiveExtractionPipeline:
    """
    Instead of: "Extract everything from every paper"
    Do: "Extract incrementally until requirements are met,
          then stop or fall back to more aggressive tactics"
    """
    
    def extract_paper_adaptively(self, paper: PaperRecord, target_edge_ids: List[str]):
        """
        Tier 1: Fast extraction (NLP agents on abstract only)
        Tier 2: Standard (agents on full text, incremental)
        Tier 3: Deep (manual review + table extraction + figure digitization)
        """
        
        extracted = {}
        
        # TIER 1: Abstract-only (fast)
        print(f"[TIER 1] Extracting from abstract of {paper.pmid}...")
        extracted = self.tier1_abstract_extraction(paper, target_edge_ids)
        
        # Check adequacy
        valid, missing = self.check_adequate_info_for_edges(target_edge_ids, extracted)
        if valid and len(extracted) >= len(target_edge_ids) * 0.8:
            print(f"  → Adequate at Tier 1. Stopping.")
            return extracted
        
        # TIER 2: Full text (standard)
        print(f"[TIER 2] Extracting from full text of {paper.pmid}...")
        extracted = self.tier2_fulltext_extraction(paper, target_edge_ids, extracted)
        
        # Check adequacy
        valid, missing = self.check_adequate_info_for_edges(target_edge_ids, extracted)
        if valid:
            print(f"  → Adequate at Tier 2. Stopping.")
            return extracted
        
        # TIER 3: Deep (aggressive)
        print(f"[TIER 3] Manual deep review flags: {missing}...")
        extracted = self.tier3_deep_extraction(paper, target_edge_ids, extracted, missing)
        
        return extracted
    
    def tier1_abstract_extraction(self, paper, target_edges):
        """Quick NLP agents on abstract only"""
        return self.npl_agents.extract_from_text(
            paper.abstract,
            edge_ids=target_edges,
            mode='fast'
        )
    
    def tier2_fulltext_extraction(self, paper, target_edges, prior_extracted):
        """Incremental agents on full paper, focusing on missing data"""
        return self.npl_agents.extract_from_text(
            paper.fulltext,
            edge_ids=target_edges,
            focus_on=self.identify_missing_sections(prior_extracted),
            mode='standard'
        )
    
    def tier3_deep_extraction(self, paper, target_edges, prior_extracted, missing):
        """Guided manual review + table/figure extraction"""
        missing_descriptions = '; '.join(missing)
        return self.human_annotator.review_and_extract(
            paper=paper,
            focus=f"Missing: {missing_descriptions}",
            mode='deep'
        )
```

**Benefits:**
- Matches Drama's multi-iteration fallback strategy
- Cost-effective (most papers stop at Tier 1–2)
- Graceful degradation (continue if partial data available)
- Transparent effort (shows which tier was sufficient)

---

## Pattern 5: Explicit Code Execution Validation

### Drama's Approach

```python
def analyze(query: str, structured_table: DataFrame) -> Tuple[Any, str]:
    """
    Stage 3: Execute analytical code.
    
    Gates:
    1. Code must be valid Python/SQL syntax
    2. Code must execute without errors
    3. Result must match expected type
    4. Result must be plausible (within expected range)
    """
    
    code = llm_generate_code(query, schema=structured_table.schema())
    
    # Gate 1: Syntax
    try:
        compile(code, '<string>', 'exec')
    except SyntaxError as e:
        raise GateViolation("SYN-G1", f"Invalid syntax: {e}")
    
    # Gate 2: Execution
    try:
        result = execute_code(code, structured_table)
    except Exception as e:
        raise GateViolation("EXE-G1", f"Execution failed: {e}")
    
    # Gate 3: Type
    expected_type = infer_expected_type(query)
    if not isinstance(result, expected_type):
        raise GateViolation("TYP-G1", f"Expected {expected_type}, got {type(result)}")
    
    # Gate 4: Plausibility
    if not is_plausible(result, query):
        raise GateViolation("PLB-G1", f"Result out of expected range: {result}")
    
    return result, code
```

### Applied to CRCI

```python
# CRCI ALREADY HAS THIS! But Drama's explicit gate style is cleaner.

class BayesianCompilationValidator:
    """
    CRCI gates P2-G1, P2-G2 already exist, but could benefit from
    Drama's more explicit gate documentation + failure messages.
    """
    
    def validate_compiled_edges(self, edges: List[Edge]) -> List[Edge]:
        """
        Apply CRCI's existing gates in Drama's explicit style
        """
        
        validated = []
        failures = []
        
        for edge in edges:
            try:
                # Gate P2-G1: Spectral radius must be < MAX
                if edge.spectral_radius > config.MAX_SPECTRAL_RADIUS:
                    raise GateViolation(
                        "P2-G1",
                        f"Edge {edge.id}: spectral_radius={edge.spectral_radius} "
                        f"> {config.MAX_SPECTRAL_RADIUS}. "
                        f"Cause: Likely cyclic feedback or high correlation. "
                        f"Action: Remove edge or decompose into subgraph."
                    )
                
                # Gate P2-G2: Condition number
                if edge.condition_number > config.CONDITION_NUMBER_WARNING:
                    raise GateViolation(
                        "P2-G2",
                        f"Edge {edge.id}: condition_number={edge.condition_number} "
                        f"> {config.CONDITION_NUMBER_WARNING}. "
                        f"Cause: High multicollinearity. "
                        f"Action: Review correlations, drop redundant edges."
                    )
                
                # Gate P4-G1: P-inclusion must exceed threshold
                if edge.p_inclusion < config.P_INCLUSION_THRESHOLD:
                    raise GateViolation(
                        "P4-G1",
                        f"Edge {edge.id}: p_inclusion={edge.p_inclusion} "
                        f"< {config.P_INCLUSION_THRESHOLD}. "
                        f"Cause: Insufficient evidence for inclusion. "
                        f"Action: Flag for review or remove from model."
                    )
                
                validated.append(edge)
                
            except GateViolation as e:
                failures.append(e)
        
        # Report: successes and failures
        print(f"Compilation validation: {len(validated)} pass, {len(failures)} fail")
        for failure in failures:
            print(f"  {failure.gate_id}: {failure.message}")
        
        if failures:
            raise GateViolationBatch(failures)
        
        return validated
```

**Benefits:**
- Matches Drama's explicit gate style
- Improves error messages (clear cause + action)
- Makes gates testable (mock gate violations)
- CRCI already has this — formalize it per Drama's pattern

---

## Implementation Priority

### Phase 1: High-ROI, Low-Effort
1. **Pattern 3 + 5**: Source ranking + gate formalization (drama-style messages)
2. **Pattern 2**: Adequacy checker for extraction guidance
3. Both are retrofits to existing code; no new modules

### Phase 2: Medium-ROI, Medium-Effort
1. **Pattern 4**: Adaptive extraction tiers (Tier 1/2/3)
2. **Pattern 1**: Dual-adapter coordination (PubMed precise + OpenAlex broad)
3. Requires new code but not new dependencies

### Phase 3: Advanced
1. Integrate all patterns into unified `retrieval/coordinator.py` + `extraction/adaptive_runner.py`
2. Add metrics dashboard showing: coverage by tier, source contribution, gate violations
3. Add human-in-loop: review flagged papers before deep extraction

