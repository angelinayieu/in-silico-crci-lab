# Drama → CRCI: Professional Adoption Roadmap

**Purpose:** Detailed engineering recommendations for integrating Drama's proven patterns into CRCI's retrieval and extraction pipelines.

**Document Status:** Technical specification for v2 implementation planning

---

## Executive Summary

Drama (SIGMOD 2025) achieves 86.5% accuracy on open-domain analytics at $0.05/task. CRCI can adopt 6 key patterns while retaining domain-specific advantages:

| Pattern | Drama Implementation | CRCI Adoption Priority | Engineering Effort |
|---------|---------------------|----------------------|-------------------|
| Multi-agent workload coordination | web_browser + web_augmenter | **HIGH** | 2-3 weeks |
| Incremental adequacy checking | check_adequate_info() | **HIGH** | 1-2 weeks |
| Source reliability ranking | rank_website() | **MEDIUM** | 1 week |
| Adaptive data accumulation | Tiered extraction loop | **HIGH** | 2-3 weeks |
| Cost-aware model routing | Task complexity → model selection | **MEDIUM** | 1 week |
| Blacklist-driven iteration | Failed source tracking | **LOW** | 3 days |

**Total estimated effort:** 8-12 weeks of engineering time

---

## Pattern 1: Multi-Agent Workload Coordination

### What Drama Does Well

Drama's data retrieval splits into two complementary agents:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Data Retriever                              │
├────────────────────────────┬────────────────────────────────────┤
│     Web Browser Agent      │      Web Augmenter Agent           │
│  (Fine-grained, slow)      │    (Broad-coverage, fast)          │
├────────────────────────────┼────────────────────────────────────┤
│ • Single page exploration  │ • Parallel multi-source search     │
│ • Click-through navigation │ • Summary extraction               │
│ • Table parsing per-page   │ • Google/Bing/DuckDuckGo           │
│ • 63.5% of tasks           │ • 36.5% of tasks                   │
│ • 91.2% accuracy on used   │ • 68% accuracy on used             │
└────────────────────────────┴────────────────────────────────────┘
```

**Key insight:** Drama doesn't pick one strategy—it runs both and intelligently merges.

### Why This Matters for CRCI

CRCI currently runs adapters sequentially:
```python
# Current: crci/retrieval/acquisition_scheduler.py
for adapter_name in ['pubmed', 'crossref', 'openalex', 'europe_pmc']:
    results = adapters[adapter_name].search(query)
    all_results.extend(results)
```

This misses Drama's key optimization: **adaptive coordination based on task difficulty**.

### Recommended Implementation

```python
# File: crci/retrieval/adaptive_coordinator.py
"""
Component: DRAMA-P1.COORDINATION
Purpose: Multi-agent workload coordination following Drama's proven pattern
Reads: Query specifications from query_generator.py
Writes: Coordinated search results to acquisition_queue
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
import asyncio

from crci.retrieval.adapters import PubMedAdapter, OpenAlexAdapter, CrossrefAdapter
from crci.retrieval.models import PaperCandidate, SearchResult
from crci.shared.config import (
    PRECISION_ADAPTER_THRESHOLD,
    BROAD_ADAPTER_THRESHOLD,
    MIN_RESULTS_FOR_ADEQUACY
)


class QueryComplexity(Enum):
    """Query complexity determines coordination strategy"""
    SIMPLE = "simple"        # Single node, well-defined terms
    MODERATE = "moderate"    # Two nodes, standard edge query
    COMPLEX = "complex"      # Multi-pathway, rare condition, contradictory literature


class AdapterRole(Enum):
    PRECISION = "precision"  # High accuracy, lower recall (PubMed)
    BROAD = "broad"          # Higher recall, lower precision (OpenAlex)
    VALIDATION = "validation"  # DOI resolution, metadata enrichment (Crossref)


@dataclass
class CoordinatedResult:
    """Result from multi-agent coordination"""
    candidates: List[PaperCandidate]
    sources_used: List[str]
    precision_contribution: float  # 0-1, fraction from precision adapter
    broad_contribution: float      # 0-1, fraction from broad adapter
    coordination_strategy: str
    total_api_calls: int
    estimated_cost_usd: float


class AdaptiveCoordinator:
    """
    Drama-inspired multi-agent coordinator for paper retrieval.
    
    Strategy:
    1. Assess query complexity
    2. Run precision adapter first (Drama's web_browser equivalent)
    3. Check adequacy (do we have enough high-quality results?)
    4. If inadequate, run broad adapter (Drama's web_augmenter equivalent)
    5. Merge with deduplication and source tracking
    """
    
    def __init__(self):
        # Precision adapters: high accuracy, structured search
        self.precision_adapters = {
            'pubmed': PubMedAdapter(),
            'europe_pmc': EuropePMCAdapter(),
        }
        
        # Broad adapters: high recall, citation graph exploration
        self.broad_adapters = {
            'openalex': OpenAlexAdapter(),
            'semantic_scholar': SemanticScholarAdapter(),
        }
        
        # Validation adapters: metadata enrichment
        self.validation_adapters = {
            'crossref': CrossrefAdapter(),
        }
        
        self.blacklist: set = set()  # Failed sources to avoid
        self.api_call_count = 0
    
    def coordinate(
        self, 
        query: str, 
        edge_id: str, 
        target_count: int = 10
    ) -> CoordinatedResult:
        """
        Main coordination entry point.
        
        Args:
            query: Boolean search query
            edge_id: Target edge from EDGE_REGISTRY
            target_count: Desired number of qualifying papers
            
        Returns:
            CoordinatedResult with merged candidates and metrics
        """
        # Step 1: Assess complexity
        complexity = self._assess_complexity(query, edge_id)
        
        # Step 2: Run precision adapters
        precision_results = self._run_precision_phase(query, edge_id)
        
        # Step 3: Check adequacy
        if self._is_adequate(precision_results, target_count, threshold=0.8):
            return self._build_result(
                precision_results, 
                broad_results=[],
                strategy=f"precision_only_{complexity.value}"
            )
        
        # Step 4: Run broad adapters (Drama's fallback)
        broad_results = self._run_broad_phase(query, edge_id, precision_results)
        
        # Step 5: Merge and deduplicate
        merged = self._merge_results(precision_results, broad_results)
        
        return self._build_result(
            precision_results,
            broad_results,
            strategy=f"precision_plus_broad_{complexity.value}"
        )
    
    def _assess_complexity(self, query: str, edge_id: str) -> QueryComplexity:
        """
        Drama insight: Task complexity determines optimal strategy.
        
        Simple: Direct queries, common terms → precision adapter sufficient
        Complex: Rare conditions, contradictory literature → need broad search
        """
        complexity_signals = {
            'term_count': len(query.split(' AND ')) + len(query.split(' OR ')),
            'has_negation': ' NOT ' in query,
            'edge_coverage_gap': self._get_edge_coverage_gap(edge_id),
        }
        
        if (complexity_signals['term_count'] <= 3 and 
            not complexity_signals['has_negation'] and
            complexity_signals['edge_coverage_gap'] < 0.3):
            return QueryComplexity.SIMPLE
        elif complexity_signals['edge_coverage_gap'] > 0.7:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.MODERATE
    
    def _run_precision_phase(
        self, 
        query: str, 
        edge_id: str
    ) -> List[PaperCandidate]:
        """
        Phase A: High-precision structured search (Drama's web_browser equivalent).
        
        - PubMed: Controlled vocabulary, MeSH terms, structured abstracts
        - Europe PMC: OA subset, better fulltext availability
        """
        results = []
        
        for name, adapter in self.precision_adapters.items():
            if name in self.blacklist:
                continue
                
            try:
                self.api_call_count += 1
                adapter_results = adapter.search(query, max_results=50)
                
                for r in adapter_results:
                    r.source_adapter = name
                    r.source_role = AdapterRole.PRECISION
                    
                results.extend(adapter_results)
                
            except AdapterError as e:
                # Drama pattern: blacklist failed sources for this session
                self.blacklist.add(name)
                logger.warning(f"Blacklisting {name}: {e}")
        
        return results
    
    def _run_broad_phase(
        self, 
        query: str, 
        edge_id: str,
        precision_results: List[PaperCandidate]
    ) -> List[PaperCandidate]:
        """
        Phase B: Broad citation-graph search (Drama's web_augmenter equivalent).
        
        Only run if precision phase insufficient.
        Uses citation relationships to find related papers.
        """
        results = []
        
        # Get seed DOIs from precision results
        seed_dois = [r.doi for r in precision_results if r.doi][:10]
        
        for name, adapter in self.broad_adapters.items():
            if name in self.blacklist:
                continue
                
            try:
                self.api_call_count += 1
                
                # Citation graph exploration
                citing = adapter.get_citing_papers(seed_dois)
                cited = adapter.get_referenced_papers(seed_dois)
                
                for r in citing + cited:
                    r.source_adapter = name
                    r.source_role = AdapterRole.BROAD
                    
                results.extend(citing + cited)
                
            except AdapterError as e:
                self.blacklist.add(name)
                logger.warning(f"Blacklisting {name}: {e}")
        
        return results
    
    def _is_adequate(
        self, 
        results: List[PaperCandidate], 
        target_count: int,
        threshold: float = 0.8
    ) -> bool:
        """
        Drama's check_adequate_info() equivalent.
        
        Adequacy = (qualifying_results / target_count) >= threshold
        
        A result "qualifies" if:
        - Has abstract available
        - Published in peer-reviewed venue
        - Study type is extractable (RCT, cohort, etc.)
        """
        qualifying = [r for r in results if self._qualifies(r)]
        return len(qualifying) >= target_count * threshold
    
    def _qualifies(self, candidate: PaperCandidate) -> bool:
        """Check if a candidate paper qualifies for extraction"""
        return (
            candidate.abstract is not None and
            len(candidate.abstract) > 100 and
            candidate.pub_year >= 2000 and
            candidate.study_type in ['rct', 'cohort', 'meta-analysis', 'systematic_review']
        )
    
    def _merge_results(
        self, 
        precision: List[PaperCandidate], 
        broad: List[PaperCandidate]
    ) -> List[PaperCandidate]:
        """
        Merge with deduplication and source preference.
        
        Preference order:
        1. Precision adapter (higher trust)
        2. Broad adapter (fill gaps)
        """
        seen_ids = {}
        merged = []
        
        # Precision results first (higher priority)
        for r in precision:
            key = r.doi or r.pmid or r.title_normalized
            if key not in seen_ids:
                seen_ids[key] = r
                merged.append(r)
        
        # Broad results fill gaps
        for r in broad:
            key = r.doi or r.pmid or r.title_normalized
            if key not in seen_ids:
                seen_ids[key] = r
                merged.append(r)
        
        return merged
    
    def _build_result(
        self,
        precision_results: List[PaperCandidate],
        broad_results: List[PaperCandidate],
        strategy: str
    ) -> CoordinatedResult:
        """Build final coordination result with metrics"""
        
        merged = self._merge_results(precision_results, broad_results)
        total = len(merged)
        
        return CoordinatedResult(
            candidates=merged,
            sources_used=list(set(r.source_adapter for r in merged)),
            precision_contribution=len(precision_results) / max(total, 1),
            broad_contribution=len(broad_results) / max(total, 1),
            coordination_strategy=strategy,
            total_api_calls=self.api_call_count,
            estimated_cost_usd=self._estimate_cost()
        )
```

### Migration Path

| Phase | Action | Files Modified |
|-------|--------|----------------|
| 1 | Add `AdaptiveCoordinator` class | New: `crci/retrieval/adaptive_coordinator.py` |
| 2 | Wire into `acquisition_scheduler.py` | Modify: `run_acquisition_cycle()` |
| 3 | Add complexity assessment | Modify: `query_generator.py` |
| 4 | Add metrics logging | Modify: `crci/shared/models/` |
| 5 | Add config constants | Modify: `crci/shared/config.py` |

---

## Pattern 2: Incremental Adequacy Checking

### What Drama Does Well

Drama's transformer continuously asks: **"Is this enough data to answer the question?"**

```python
# Drama's pattern
while not check_adequate_info(query, structured_data):
    missing_info = identify_missing_columns(query, structured_data)
    next_file = file_selection(missing_info, available_files)
    new_data = extract_data(next_file, focus=missing_info)
    structured_data = update_database(structured_data, new_data)
```

**Key insight:** Extraction is **goal-directed**, not exhaustive. Stop when you have enough.

### Why This Matters for CRCI

CRCI currently extracts all available data from each paper:
```python
# Current: crci/extraction/p1_extraction/runner.py
def run_p1_extraction(paper_map: PaperMap) -> ExtractionInsight:
    for agent in ALL_AGENTS:
        agent.extract(paper_map.fulltext)  # Always extracts everything
```

This wastes compute on papers where abstract-only extraction would suffice.

### Recommended Implementation

```python
# File: crci/extraction/adequacy_checker.py
"""
Component: DRAMA-P2.ADEQUACY
Purpose: Goal-directed extraction with early stopping
Spec: Drama's check_adequate_info pattern
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum

from crci.shared.config import (
    MIN_STUDIES_FOR_META_ANALYSIS,
    MAX_SE_FOR_DEPLOYMENT,
    MIN_CONFIDENCE_THRESHOLD
)


class AdequacyLevel(Enum):
    """Extraction adequacy levels"""
    INSUFFICIENT = "insufficient"   # Cannot proceed to meta-analysis
    MARGINAL = "marginal"           # Borderline, consider more extraction
    ADEQUATE = "adequate"           # Ready for meta-analysis
    EXCELLENT = "excellent"         # High-quality, publication-ready


@dataclass
class AdequacyReport:
    """Result of adequacy check"""
    level: AdequacyLevel
    missing_fields: List[str]
    recommendations: List[str]
    can_meta_analyze: bool
    estimated_se_if_proceed: Optional[float]
    extraction_depth_used: str  # "abstract", "methods", "full"


@dataclass
class EdgeRequirements:
    """What we need to meta-analyze an edge"""
    edge_id: str
    min_studies: int = 3
    required_fields: List[str] = None
    
    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = [
                'effect_size',      # β, d, OR, RR
                'se_or_ci',         # SE or 95% CI bounds
                'sample_size',      # N or n1+n2
                'study_design',     # RCT, cohort, case-control
            ]


class AdequacyChecker:
    """
    Drama-inspired adequacy checker for extraction pipeline.
    
    Philosophy: Extract incrementally. Stop when adequate. Flag gaps.
    """
    
    def check_edge_adequacy(
        self,
        edge_id: str,
        extracted_studies: List[Dict],
        requirements: Optional[EdgeRequirements] = None
    ) -> AdequacyReport:
        """
        Core adequacy check: Can we meta-analyze this edge with current data?
        
        Args:
            edge_id: Target edge from EDGE_REGISTRY
            extracted_studies: List of study-level extractions
            requirements: Custom requirements (or use defaults)
            
        Returns:
            AdequacyReport with level, gaps, and recommendations
        """
        if requirements is None:
            requirements = EdgeRequirements(edge_id=edge_id)
        
        # Count studies with complete required data
        complete_studies = []
        missing_by_study = {}
        
        for i, study in enumerate(extracted_studies):
            missing = self._get_missing_fields(study, requirements.required_fields)
            if not missing:
                complete_studies.append(study)
            else:
                missing_by_study[f"study_{i}"] = missing
        
        # Assess adequacy level
        n_complete = len(complete_studies)
        n_required = requirements.min_studies
        
        if n_complete >= n_required:
            # Can we actually run meta-analysis?
            try:
                projected_se = self._estimate_pooled_se(complete_studies)
                
                if projected_se <= MAX_SE_FOR_DEPLOYMENT:
                    level = AdequacyLevel.EXCELLENT
                else:
                    level = AdequacyLevel.ADEQUATE
                    
                can_meta = True
                
            except InsufficientDataError:
                level = AdequacyLevel.MARGINAL
                projected_se = None
                can_meta = False
        else:
            level = AdequacyLevel.INSUFFICIENT
            projected_se = None
            can_meta = False
        
        # Build recommendations
        recommendations = self._build_recommendations(
            level, n_complete, n_required, missing_by_study
        )
        
        # Flatten missing fields
        all_missing = []
        for study_id, fields in missing_by_study.items():
            for field in fields:
                all_missing.append(f"{study_id}.{field}")
        
        return AdequacyReport(
            level=level,
            missing_fields=all_missing,
            recommendations=recommendations,
            can_meta_analyze=can_meta,
            estimated_se_if_proceed=projected_se,
            extraction_depth_used=self._infer_depth(extracted_studies)
        )
    
    def _get_missing_fields(
        self, 
        study: Dict, 
        required_fields: List[str]
    ) -> List[str]:
        """Identify missing required fields in a study extraction"""
        missing = []
        for field in required_fields:
            value = study.get(field)
            if value is None or value == '' or value == 'MISSING':
                missing.append(field)
            elif field == 'se_or_ci' and not self._has_valid_uncertainty(study):
                missing.append(field)
        return missing
    
    def _has_valid_uncertainty(self, study: Dict) -> bool:
        """Check if study has valid uncertainty measure (SE or CI)"""
        if study.get('se') is not None and study['se'] > 0:
            return True
        if (study.get('ci_lower') is not None and 
            study.get('ci_upper') is not None):
            return True
        return False
    
    def _estimate_pooled_se(self, studies: List[Dict]) -> float:
        """
        Quick estimate of pooled SE if we proceed with meta-analysis.
        
        Uses IVW formula: SE_pooled = 1 / sqrt(sum(1/SE_i^2))
        """
        if not studies:
            raise InsufficientDataError("No studies")
        
        weights_sum = 0.0
        for study in studies:
            se = study.get('se')
            if se is None:
                # Estimate from CI
                ci_lower = study.get('ci_lower')
                ci_upper = study.get('ci_upper')
                if ci_lower is not None and ci_upper is not None:
                    se = (ci_upper - ci_lower) / 3.92  # 95% CI
                else:
                    continue
            
            if se > 0:
                weights_sum += 1 / (se ** 2)
        
        if weights_sum <= 0:
            raise InsufficientDataError("No valid SE values")
        
        return 1.0 / (weights_sum ** 0.5)
    
    def _build_recommendations(
        self,
        level: AdequacyLevel,
        n_complete: int,
        n_required: int,
        missing_by_study: Dict[str, List[str]]
    ) -> List[str]:
        """Generate actionable recommendations based on adequacy level"""
        
        recs = []
        
        if level == AdequacyLevel.INSUFFICIENT:
            gap = n_required - n_complete
            recs.append(f"Need {gap} more complete studies")
            
            # Most common missing fields
            all_missing = [f for fields in missing_by_study.values() for f in fields]
            common_missing = self._most_common(all_missing, top_n=3)
            
            for field in common_missing:
                recs.append(f"Prioritize extracting '{field}' from existing papers")
        
        elif level == AdequacyLevel.MARGINAL:
            recs.append("Consider deeper extraction from existing papers")
            recs.append("Check tables/figures for missing effect sizes")
        
        elif level == AdequacyLevel.ADEQUATE:
            recs.append("Ready for meta-analysis")
            recs.append("Consider additional studies to reduce SE")
        
        else:  # EXCELLENT
            recs.append("High-quality evidence base")
            recs.append("Proceed to algorithm chain B")
        
        return recs
    
    def _most_common(self, items: List[str], top_n: int = 3) -> List[str]:
        """Get most frequently occurring items"""
        from collections import Counter
        return [item for item, _ in Counter(items).most_common(top_n)]
    
    def _infer_depth(self, studies: List[Dict]) -> str:
        """Infer extraction depth used based on data completeness"""
        if not studies:
            return "none"
        
        avg_fields = sum(len(s.keys()) for s in studies) / len(studies)
        
        if avg_fields < 5:
            return "abstract"
        elif avg_fields < 15:
            return "methods"
        else:
            return "full"


class TieredExtractionController:
    """
    Orchestrates tiered extraction with adequacy checks at each level.
    
    Tier 1: Abstract only (fast, low cost)
    Tier 2: Methods + Results sections  
    Tier 3: Full text + tables + figures
    Tier 4: Manual review queue
    """
    
    def __init__(self, adequacy_checker: AdequacyChecker):
        self.checker = adequacy_checker
    
    def extract_to_adequacy(
        self,
        paper: PaperRecord,
        edge_id: str,
        current_extractions: List[Dict]
    ) -> Tuple[List[Dict], str]:
        """
        Extract incrementally until adequate or exhausted.
        
        Returns:
            Tuple of (updated extractions, final tier used)
        """
        
        # Tier 1: Abstract
        tier1_result = self._extract_tier1(paper)
        extractions = current_extractions + [tier1_result]
        
        report = self.checker.check_edge_adequacy(edge_id, extractions)
        if report.level >= AdequacyLevel.ADEQUATE:
            return extractions, "tier1_abstract"
        
        # Tier 2: Methods + Results
        tier2_result = self._extract_tier2(paper, focus=report.missing_fields)
        extractions[-1].update(tier2_result)  # Merge into same study
        
        report = self.checker.check_edge_adequacy(edge_id, extractions)
        if report.level >= AdequacyLevel.ADEQUATE:
            return extractions, "tier2_sections"
        
        # Tier 3: Full text + tables
        tier3_result = self._extract_tier3(paper, focus=report.missing_fields)
        extractions[-1].update(tier3_result)
        
        report = self.checker.check_edge_adequacy(edge_id, extractions)
        if report.level >= AdequacyLevel.ADEQUATE:
            return extractions, "tier3_full"
        
        # Tier 4: Flag for manual review
        self._queue_for_manual_review(paper, edge_id, report)
        return extractions, "tier4_manual_queued"
    
    def _extract_tier1(self, paper: PaperRecord) -> Dict:
        """Fast extraction from abstract only"""
        # Implementation calls existing agents in fast mode
        pass
    
    def _extract_tier2(self, paper: PaperRecord, focus: List[str]) -> Dict:
        """Focused extraction from methods/results sections"""
        # Implementation calls agents on specific sections
        pass
    
    def _extract_tier3(self, paper: PaperRecord, focus: List[str]) -> Dict:
        """Deep extraction including tables and figures"""
        # Implementation calls table extraction, figure digitization
        pass
    
    def _queue_for_manual_review(
        self, 
        paper: PaperRecord, 
        edge_id: str,
        report: AdequacyReport
    ):
        """Add to manual review queue with context"""
        # Implementation writes to review_tasks table
        pass
```

### Integration Points

```python
# Modified: crci/extraction/pipeline.py

def run_extraction_pipeline(paper: PaperRecord, target_edges: List[str]):
    """
    Modified pipeline with adequacy-driven extraction.
    """
    
    checker = AdequacyChecker()
    controller = TieredExtractionController(checker)
    
    all_extractions = {}
    
    for edge_id in target_edges:
        # Get existing extractions for this edge
        current = get_existing_extractions(edge_id)
        
        # Check if we even need this paper
        report = checker.check_edge_adequacy(edge_id, current)
        
        if report.level >= AdequacyLevel.EXCELLENT:
            logger.info(f"Edge {edge_id} already adequate, skipping paper")
            continue
        
        # Extract to adequacy
        updated, tier_used = controller.extract_to_adequacy(
            paper, edge_id, current
        )
        
        all_extractions[edge_id] = updated
        logger.info(f"Edge {edge_id}: extracted at {tier_used}")
    
    return all_extractions
```

---

## Pattern 3: Source Reliability Ranking

### What Drama Does Well

Drama tracks **how much each source contributed** to the final answer:

```python
# Drama's inline annotation tracking
inline_annotations = {
    "nih.gov": ["Used for claim 1, claim 3, claim 5"],
    "blog.example.com": ["Not used"],
    "pubmed.ncbi.nlm.nih.gov": ["Used for claim 2, claim 4"],
}

# Score = (contribution_count / total_claims) * authority_weight
```

### Recommended Implementation for CRCI

```python
# File: crci/retrieval/source_ranker.py
"""
Component: DRAMA-P3.SOURCE_RANKING
Purpose: Rank papers by expected contribution to model
"""

from dataclasses import dataclass
from typing import List, Dict
from crci.shared.config import (
    VENUE_AUTHORITY_WEIGHTS,
    STUDY_DESIGN_WEIGHTS,
    RECENCY_DECAY_YEARS
)


@dataclass
class SourceRankingFactors:
    """Factors that determine source contribution score"""
    
    # Authority factors (Drama's is_authoritative equivalent)
    venue_tier: int              # 1=Nature/Lancet, 2=specialty, 3=other, 4=preprint
    study_design: str            # rct, cohort, case_series, case_report
    sample_size: int             # N
    impact_factor: float         # Journal IF
    
    # Relevance factors
    edges_addressed: List[str]   # Which target edges this paper covers
    keyword_match_score: float   # 0-1, how well abstract matches query
    
    # Recency factors
    publication_year: int
    
    # Uniqueness factors (avoid redundancy)
    overlap_with_existing: float # 0-1, semantic overlap with papers we have


class SourceRanker:
    """
    Rank sources for acquisition priority.
    
    Drama insight: Not all sources contribute equally.
    Prioritize by expected contribution to model quality.
    """
    
    def rank_candidates(
        self,
        candidates: List[PaperCandidate],
        target_edges: List[str],
        existing_papers: List[PaperRecord]
    ) -> List[Tuple[PaperCandidate, float]]:
        """
        Score and rank candidates.
        
        Returns list of (candidate, score) sorted descending.
        """
        scored = []
        
        for candidate in candidates:
            factors = self._extract_factors(candidate, target_edges, existing_papers)
            score = self._compute_score(factors, target_edges)
            scored.append((candidate, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def _extract_factors(
        self,
        candidate: PaperCandidate,
        target_edges: List[str],
        existing_papers: List[PaperRecord]
    ) -> SourceRankingFactors:
        """Extract ranking factors from candidate metadata"""
        
        return SourceRankingFactors(
            venue_tier=self._classify_venue(candidate.journal),
            study_design=self._classify_design(candidate.abstract),
            sample_size=self._estimate_sample_size(candidate.abstract),
            impact_factor=self._get_impact_factor(candidate.journal),
            edges_addressed=self._match_edges(candidate.abstract, target_edges),
            keyword_match_score=self._keyword_match(candidate.abstract, target_edges),
            publication_year=candidate.pub_year,
            overlap_with_existing=self._compute_overlap(candidate, existing_papers),
        )
    
    def _compute_score(
        self,
        factors: SourceRankingFactors,
        target_edges: List[str]
    ) -> float:
        """
        Weighted scoring function.
        
        Formula: S = Σ(w_i × f_i)
        
        Weights (configurable):
        - Edge coverage: 0.30 (how many target edges?)
        - Study design: 0.25 (RCT > cohort > case)
        - Venue authority: 0.15 (Nature > specialty > preprint)
        - Recency: 0.15 (prefer <5 years)
        - Uniqueness: 0.15 (avoid redundancy)
        """
        
        # Edge coverage score (0-1)
        edge_coverage = len(factors.edges_addressed) / len(target_edges)
        
        # Study design score (0-1)
        design_weights = {
            'rct': 1.0,
            'meta-analysis': 0.95,
            'cohort': 0.7,
            'case_control': 0.5,
            'case_series': 0.3,
            'case_report': 0.1,
        }
        design_score = design_weights.get(factors.study_design, 0.2)
        
        # Venue authority score (0-1)
        venue_score = 1.0 / factors.venue_tier
        
        # Recency score (0-1, linear decay)
        years_old = 2026 - factors.publication_year
        recency_score = max(0, 1 - years_old / RECENCY_DECAY_YEARS)
        
        # Uniqueness score (0-1, inverse of overlap)
        uniqueness_score = 1 - factors.overlap_with_existing
        
        # Weighted combination
        score = (
            0.30 * edge_coverage +
            0.25 * design_score +
            0.15 * venue_score +
            0.15 * recency_score +
            0.15 * uniqueness_score
        )
        
        return score
    
    def _classify_venue(self, journal: str) -> int:
        """Classify journal into authority tier"""
        tier1 = ['nature', 'lancet', 'nejm', 'jama', 'bmj', 'cell', 'science']
        tier2 = ['cancer', 'oncology', 'neurology', 'psychiatry', 'medicine']
        tier4 = ['preprint', 'arxiv', 'medrxiv', 'biorxiv']
        
        journal_lower = journal.lower()
        
        if any(t in journal_lower for t in tier1):
            return 1
        elif any(t in journal_lower for t in tier4):
            return 4
        elif any(t in journal_lower for t in tier2):
            return 2
        else:
            return 3
    
    def _classify_design(self, abstract: str) -> str:
        """Classify study design from abstract text"""
        abstract_lower = abstract.lower()
        
        patterns = [
            ('meta-analysis', 'meta-analysis'),
            ('systematic review', 'meta-analysis'),
            ('randomized', 'rct'),
            ('randomised', 'rct'),
            ('controlled trial', 'rct'),
            ('cohort', 'cohort'),
            ('prospective', 'cohort'),
            ('longitudinal', 'cohort'),
            ('case-control', 'case_control'),
            ('cross-sectional', 'case_control'),
            ('case series', 'case_series'),
            ('case report', 'case_report'),
        ]
        
        for pattern, design in patterns:
            if pattern in abstract_lower:
                return design
        
        return 'unknown'
```

---

## Pattern 4: Cost-Aware Model Routing

### What Drama Does Well

Drama optimizes for cost ($0.05/task) by:
1. Using a single model (GPT-4o) efficiently
2. Stopping early when data is adequate
3. Not over-processing simple tasks

### Recommended Implementation for CRCI

```python
# File: crci/llm/model_router.py
"""
Component: DRAMA-P4.MODEL_ROUTING
Purpose: Route extraction tasks to appropriate model tier
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional

from crci.shared.config import (
    MODEL_OPUS_COST_PER_1K,
    MODEL_SONNET_COST_PER_1K,
    MODEL_HAIKU_COST_PER_1K,
    COMPLEXITY_THRESHOLDS
)


class ModelTier(Enum):
    """Model tiers by capability and cost"""
    HAIKU = "haiku"       # Fast, cheap: simple extraction, classification
    SONNET = "sonnet"     # Balanced: standard extraction, harmonization
    OPUS = "opus"         # Full: complex reasoning, ambiguity resolution


@dataclass
class RoutingDecision:
    """Result of model routing decision"""
    model_tier: ModelTier
    estimated_tokens: int
    estimated_cost_usd: float
    reasoning: str


class ModelRouter:
    """
    Route tasks to cost-appropriate models.
    
    Drama insight: Not every task needs the most powerful model.
    Simple tasks can use faster, cheaper models.
    """
    
    def route_extraction_task(
        self,
        task_type: str,
        complexity_signals: dict
    ) -> RoutingDecision:
        """
        Route extraction task to appropriate model.
        
        Task types:
        - study_design_classify: Simple classification → Haiku
        - effect_size_extract: Standard extraction → Sonnet
        - ambiguity_resolve: Complex reasoning → Opus
        """
        
        # Simple classification tasks
        if task_type in ['study_design_classify', 'population_classify', 'outcome_classify']:
            return RoutingDecision(
                model_tier=ModelTier.HAIKU,
                estimated_tokens=500,
                estimated_cost_usd=500 * MODEL_HAIKU_COST_PER_1K / 1000,
                reasoning="Simple classification task"
            )
        
        # Standard extraction
        if task_type in ['effect_size_extract', 'sample_size_extract', 'ci_extract']:
            # Check complexity
            has_tables = complexity_signals.get('has_tables', False)
            text_length = complexity_signals.get('text_length', 0)
            
            if has_tables or text_length > 5000:
                return RoutingDecision(
                    model_tier=ModelTier.SONNET,
                    estimated_tokens=2000,
                    estimated_cost_usd=2000 * MODEL_SONNET_COST_PER_1K / 1000,
                    reasoning="Standard extraction with tables/long text"
                )
            else:
                return RoutingDecision(
                    model_tier=ModelTier.HAIKU,
                    estimated_tokens=1000,
                    estimated_cost_usd=1000 * MODEL_HAIKU_COST_PER_1K / 1000,
                    reasoning="Simple extraction, short text"
                )
        
        # Complex reasoning tasks
        if task_type in ['ambiguity_resolve', 'conflation_detect', 'heterogeneity_assess']:
            return RoutingDecision(
                model_tier=ModelTier.OPUS,
                estimated_tokens=4000,
                estimated_cost_usd=4000 * MODEL_OPUS_COST_PER_1K / 1000,
                reasoning="Complex reasoning required"
            )
        
        # Default: Sonnet
        return RoutingDecision(
            model_tier=ModelTier.SONNET,
            estimated_tokens=1500,
            estimated_cost_usd=1500 * MODEL_SONNET_COST_PER_1K / 1000,
            reasoning="Default routing"
        )
```

---

## Pattern 5: Blacklist-Driven Iteration

### What Drama Does Well

Drama tracks failed sources and avoids them in subsequent iterations:

```python
# Drama's blacklist pattern
blacklist = set()

for attempt in range(max_attempts):
    data = retrieve(query, blacklist=blacklist)
    
    if validate(data):
        return data
    
    # Identify problematic sources
    failed_sources = identify_invalid_sources(data)
    blacklist |= failed_sources
    
    # Retry with blacklist
```

### Recommended Implementation for CRCI

```python
# File: crci/retrieval/failure_tracker.py
"""
Component: DRAMA-P5.BLACKLIST
Purpose: Track and avoid failed sources
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set, Optional


@dataclass
class FailureRecord:
    """Record of a source failure"""
    source_id: str              # Adapter name or paper ID
    failure_type: str           # 'rate_limit', 'paywall', 'invalid_data', 'timeout'
    timestamp: datetime
    retry_after: Optional[datetime] = None
    permanent: bool = False


class FailureTracker:
    """
    Track failed sources and manage retry logic.
    
    Drama pattern: Don't repeat failed retrievals within same session.
    """
    
    def __init__(self):
        self.failures: Dict[str, FailureRecord] = {}
        self.session_blacklist: Set[str] = set()
    
    def record_failure(
        self,
        source_id: str,
        failure_type: str,
        retry_after: Optional[datetime] = None,
        permanent: bool = False
    ):
        """Record a source failure"""
        
        record = FailureRecord(
            source_id=source_id,
            failure_type=failure_type,
            timestamp=datetime.now(),
            retry_after=retry_after,
            permanent=permanent
        )
        
        self.failures[source_id] = record
        
        if permanent or failure_type in ['paywall', 'does_not_exist']:
            self.session_blacklist.add(source_id)
    
    def is_blacklisted(self, source_id: str) -> bool:
        """Check if source is currently blacklisted"""
        
        if source_id in self.session_blacklist:
            return True
        
        if source_id in self.failures:
            record = self.failures[source_id]
            
            # Check if retry_after has passed
            if record.retry_after and datetime.now() < record.retry_after:
                return True
            
            if record.permanent:
                return True
        
        return False
    
    def get_blacklist(self) -> Set[str]:
        """Get current blacklist for retrieval calls"""
        return self.session_blacklist.copy()
    
    def clear_session(self):
        """Clear session-specific blacklist (keep permanent)"""
        permanent = {
            sid for sid, rec in self.failures.items() 
            if rec.permanent
        }
        self.session_blacklist = permanent
```

---

## Implementation Prioritization Matrix

| Pattern | Impact on Quality | Engineering Effort | Dependencies | Priority |
|---------|------------------|-------------------|--------------|----------|
| Multi-agent coordination | **HIGH** | 2-3 weeks | None | **P0** |
| Adequacy checking | **HIGH** | 1-2 weeks | Coordination | **P0** |
| Source ranking | **MEDIUM** | 1 week | None | **P1** |
| Model routing | **MEDIUM** | 1 week | LLM client | **P1** |
| Blacklist tracking | **LOW** | 3 days | Coordination | **P2** |
| Cost estimation | **LOW** | 3 days | Model routing | **P2** |

---

## Migration Checklist

### Phase 1: Foundation (Weeks 1-2)

- [ ] Create `crci/retrieval/adaptive_coordinator.py`
- [ ] Create `crci/extraction/adequacy_checker.py`
- [ ] Add config constants to `crci/shared/config.py`:
  - `MIN_STUDIES_FOR_META_ANALYSIS = 3`
  - `MAX_SE_FOR_DEPLOYMENT = 0.5`
  - `PRECISION_ADAPTER_THRESHOLD = 0.8`
  - `BROAD_ADAPTER_THRESHOLD = 0.6`
  - `RECENCY_DECAY_YEARS = 10`
- [ ] Add tests for coordination logic
- [ ] Add tests for adequacy checking

### Phase 2: Integration (Weeks 3-4)

- [ ] Modify `acquisition_scheduler.py` to use `AdaptiveCoordinator`
- [ ] Modify `pipeline.py` to use `TieredExtractionController`
- [ ] Add metrics logging for coordination decisions
- [ ] Add metrics logging for adequacy levels

### Phase 3: Optimization (Weeks 5-6)

- [ ] Create `crci/retrieval/source_ranker.py`
- [ ] Create `crci/llm/model_router.py`
- [ ] Create `crci/retrieval/failure_tracker.py`
- [ ] Wire source ranking into acquisition queue
- [ ] Wire model routing into extraction agents

### Phase 4: Validation (Weeks 7-8)

- [ ] Run end-to-end extraction on 10 papers
- [ ] Compare cost/quality vs. current approach
- [ ] Measure adequacy levels achieved
- [ ] Document lessons learned

---

## Success Metrics

| Metric | Current Baseline | Target with Drama Patterns |
|--------|-----------------|---------------------------|
| Papers processed/hour | ~5 | ~15 (3x) |
| API cost/paper | ~$0.50 | ~$0.20 (60% reduction) |
| Extraction completeness | ~70% fields | ~90% fields |
| Adequate edges (first pass) | Unknown | >80% |
| Manual review queue | Unknown | <10% of papers |

---

## Appendix: Drama Paper Key Excerpts

### Multi-Agent Workload (Table 7)

> "The web browser agent was activated for 63.5% of tasks, achieving 91.2% correctness when used. The web augmenter was activated for 36.5% of tasks, with 68% correctness when used."

### Incremental Data Accumulation (Section 4.2)

> "The data transformer maintains a running list L of processed files and iteratively checks whether the structured table T contains adequate information to answer Q."

### Source Ranking (Section 4.1)

> "rank_website evaluates sources based on their relevance to Q, contribution to generating the response, and authoritativeness."

### Cost Efficiency (Table 6)

> "Drama achieves an average cost of $0.05 per task, with GPT-4o as the backbone model."
