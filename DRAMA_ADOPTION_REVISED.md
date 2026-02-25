# Drama → CRCI: Final Technical Assessment

**Status:** Code-verified analysis  
**Method:** Reviewed actual implementations in `crci/retrieval/`, `crci/extraction/`, `crci/shared/config.py`  
**Verdict:** 1 genuine enhancement, 1 partial enhancement, 3 duplicates

---

## Existing System Capabilities (Verified)

Before evaluating Drama patterns, here's what CRCI already has:

### 1. APS (Acquisition Priority Score) — `crci/retrieval/aps_scorer.py`

**What it does:** Ranks papers for retrieval priority using a weighted formula.

```python
# Lines 167-215: Already implements weighted multi-factor scoring
APS = (
    w["edge_gap"] × edge_gap           # 0.35
    + w["design"] × design_bonus       # 0.20  
    + w["pop"] × pop_match             # 0.20
    + w["recency"] × recency           # 0.15
    + w["source"] × source_quality     # 0.10
)
```

**Components already implemented:**
- `_score_edge_gap()` — gaps from `evidence_gap_compiler.py`
- `_score_design_bonus()` — detects meta-analysis, RCT, cohort from abstract
- `_score_pop_match()` — cancer + cognitive term matching
- `_score_recency()` — decay by publication year
- `_score_source_quality()` — citation count proxy

**Drama's Pattern 3 (Source Reliability Ranking) duplicates this entirely.**

---

### 2. Extraction Mode Selection — `crci/extraction/p0_triage/mode_selection.py`

**What it does:** Routes papers to extraction depth based on paper subtype.

```python
# Lines 37-80: ExtractionMode enum and _SUBTYPE_TO_MODE mapping
class ExtractionMode(StrEnum):
    SHALLOW = "SHALLOW"
    STANDARD = "STANDARD"  
    DEEP = "DEEP"

# 27 paper subtypes map to 3 extraction depths
_SUBTYPE_TO_MODE = {
    PaperSubtype.RCT_EXERCISE: ExtractionMode.DEEP,
    PaperSubtype.META_ANALYSIS: ExtractionMode.DEEP,
    PaperSubtype.LONGITUDINAL_COHORT: ExtractionMode.STANDARD,
    PaperSubtype.CASE_REPORT: ExtractionMode.SHALLOW,
    # ... 27 total
}
```

**What it lacks:** No `ABSTRACT_ONLY` mode. No edge-aware routing.

---

### 3. Saturation Detection — `crci/retrieval/saturation_detector.py`

**What it does:** Tracks novelty ratio across acquisition cycles.

```python
# Lines 50-90: Formula SAT-1
novelty_ratio = |new_candidates| / |total_candidates|

# SAT-G1: halt when novelty_ratio < threshold for N consecutive cycles
```

**Already provides:** Loop termination when evidence acquisition saturates.

---

### 4. Evidence Gap Analysis — `crci/runtime/evidence_gap_compiler.py`

**What it does:** Classifies edges by evidence strength, computes EVSI.

```python
# Lines 76-100: 5-tier gap classification
gap_type, severity = _classify_gap(k, has_rct, i_sq, prior_source)

# Lines 101-110: Discovery score and EVSI
disc_score = |elasticity| × sqrt(variance_contrib)
evsi = variance_contrib × (1 - 1/(k + 1 + EVSI_HYPOTHETICAL_N))
```

**Already tracks:** Study count `k` per edge, RCT flags, heterogeneity (I²).

---

### 5. Shared Control Handling — `crci/extraction/p4_aggregation/shared_control_handler.py`

**What it does:** Adjusts SE when studies share control groups.

```python
# Lines 65-120: SC-1 formula
n_control_adj = n_control / k_shared
se_adj = sqrt(1/n_t + 1/n_control_adj + d²/(2(n_t + n_control_adj)))
```

**Important:** The system already knows studies aren't independent. My original `_estimate_pooled_se()` in the revised doc was a worse implementation of what already exists.

---

### 6. Coverage Matrix — `crci/extraction/p5_sufficiency/coverage_analyzer.py`

**What it does:** Classifies all 118 edges by evidence strength.

```python
# Lines 70-100: Classification thresholds
k >= 5 AND has_rct → STRONG
k >= 2 → MODERATE  
k == 1 → WEAK
k == 0 → GAP
```

**Provides:** Per-edge study counts, already used by APS for edge_gap scoring.

---

### 7. LLM Client — `crci/llm/client.py`

**What it does:** Single-provider Claude API wrapper.

```python
# Lines 55-85: Uses config.LLM_DEFAULT_MODEL = "claude-sonnet-4-20250514"
# No multi-model routing. All tasks use Sonnet.
```

**This is the actual gap.** No cost-tier routing currently exists.

---

## Pattern-by-Pattern Evaluation

### ❌ Pattern 1: Multi-Agent Coordination

**Drama's version:** web_browser (precise) + web_augmenter (broad) coordination.

**CRCI already has:**
1. `acquisition_scheduler.py` lines 80-140: Sequential adapter orchestration
2. `query_generator.py`: PubMed Boolean queries (precise)
3. `hop_discoverer.py`: Citation graph expansion (broad)
4. APS scoring determines search intensity per edge

**Why sequential is correct:** PubMed rate-limits to 3 req/sec. Running adapters in parallel hits limits faster, doesn't speed things up. The existing flow already does precision-first (PubMed), then broad (OpenAlex citation graph via hop discovery).

**Verdict:** Drop. Existing system already implements this with domain-appropriate ordering.

---

### ❌ Pattern 3: Source Reliability Ranking

**Drama's `rank_website()`:** Score sources by authoritativeness + contribution.

**CRCI's APS (`aps_scorer.py`):** Already does this with:
- `_score_design_bonus()` — study type quality
- `_score_source_quality()` — citation count
- `_score_edge_gap()` — contribution to model gaps
- `_score_pop_match()` — relevance to domain

**Why APS is better calibrated:**
- Weights from domain model (0.35 edge_gap, 0.20 design, etc.)
- Uses `config.APS_WEIGHTS` — single source of truth
- Author-gap boost from `study_annotations_v1`
- Integrates with `evidence_gap_compiler.py` gap classifications

**My proposed `SourceRanker._classify_venue()` was worse:**
```python
# My proposal (fragile):
if "cancer" in journal_lower:
    return 2  # Incorrectly catches "Cancer Research UK Blog"
```

**Verdict:** Drop. APS handles this better.

---

### ❌ Pattern 5: Blacklist-Driven Iteration

**Drama's version:** Track failed sources, avoid retrying.

**CRCI already has:**
1. `fulltext_retriever.py` fallback chain
2. `id_resolver.py` cross-resolves DOI↔PMID
3. `saturation_detector.py` tracks what's already queued

**The "problem" is rare:** 4 APIs, all stable. paperscraper's 9-step cascade handles DOI failures.

**Verdict:** Drop. A `Set[str]` in acquisition state is sufficient if needed.

---

### ⚠️ Pattern 2: Tiered Extraction Depth — PARTIAL Enhancement

**Drama's insight:** Extract incrementally, stop when adequate.

**What CRCI has:** Three extraction modes (SHALLOW/STANDARD/DEEP) routed by paper subtype.

**What CRCI lacks:** 
1. No `ABSTRACT_ONLY` mode
2. No edge-aware routing ("this paper covers an edge that already has k≥5")

**The genuine enhancement:**

```python
# Modify crci/extraction/p0_triage/mode_selection.py

# ADD: New mode
class ExtractionMode(StrEnum):
    ABSTRACT_ONLY = "ABSTRACT_ONLY"  # NEW
    SHALLOW = "SHALLOW"
    STANDARD = "STANDARD"
    DEEP = "DEEP"

# ADD: Edge-aware routing logic in select_extraction_mode()
def select_extraction_mode(..., edge_evidence: dict[str, EdgeCoverage] | None = None):
    """
    If paper targets edge with k >= 5 AND strength == STRONG,
    use ABSTRACT_ONLY (confirmatory evidence only).
    """
    if edge_evidence is not None:
        target_edges = get_target_edges_from_paper(screened_paper)
        all_strong = all(
            edge_evidence.get(e, {}).strength == "STRONG" 
            for e in target_edges
        )
        if all_strong:
            return TriageResult(
                extraction_mode=ExtractionMode.ABSTRACT_ONLY,
                ...
            )
    
    # Fall back to existing subtype-based routing
    return existing_logic(...)
```

**Dependencies already exist:**
- `coverage_analyzer.py` provides `EdgeCoverage` with `k` and `strength`
- `evidence_gap_compiler.py` already computes study counts per edge

**Effort:** 1-2 days (modify existing module, not new module)

**But wait — is this even needed?** The existing SHALLOW mode already does minimal extraction. The question is: what's the difference between ABSTRACT_ONLY and SHALLOW?

| Mode | What it does | When to use |
|------|--------------|-------------|
| ABSTRACT_ONLY | Parse abstract only, no PDF reading | Edge has k≥5, just need confirmation |
| SHALLOW | Full PDF parse, but skip deep extraction | Low-value paper types (case reports) |

**Real enhancement:** Skip PDF ingestion entirely for confirmatory papers. This saves PDF parsing time and LLM tokens.

---

### ✅ Pattern 4: Model Routing — GENUINE Enhancement

**What CRCI has:** Single model (`claude-sonnet-4-20250514`) for all tasks.

**What CRCI lacks:** No task-based model selection.

**This is the genuine gap.** Current `llm/client.py`:
```python
# Line 1079 in config.py:
LLM_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"

# All agents use this. No differentiation.
```

**Enhancement validity:** This is not Drama-specific. It's standard LLM engineering. But it's genuinely not implemented.

**Careful implementation required:**

The 27 paper subtypes require Sonnet or Opus. Example:
- PaperSubtype.RCT_EXERCISE vs PaperSubtype.RCT_COGNITIVE vs PaperSubtype.RCT_PHARMACOLOGICAL
- These distinctions require understanding exercise physiology vs cognitive training vs drug mechanisms
- Haiku cannot reliably distinguish these from abstract text

**Safe Haiku tasks (binary classification only):**
- `has_effect_size` — yes/no
- `has_confidence_interval` — yes/no  
- `is_rct` — yes/no (not subtype)
- `population_is_cancer` — yes/no

**Sonnet tasks (extraction + multi-class):**
- `effect_size_extract`
- `sample_size_extract`
- `study_design_classify_27` (27 subtypes)
- All current extraction agents

**Opus tasks (complex reasoning):**
- `ambiguity_resolve`
- `heterogeneity_assess`
- `mechanistic_pathway_infer`

**Implementation:**

```python
# New file: crci/llm/model_router.py

from enum import Enum
from crci.shared import config

class ModelTier(Enum):
    HAIKU = "claude-3-5-haiku-20241022"
    SONNET = "claude-sonnet-4-20250514"
    OPUS = "claude-opus-4-20250514"

# Conservative defaults — validated tasks only
HAIKU_SAFE_TASKS = frozenset({
    'has_effect_size',
    'has_confidence_interval', 
    'is_rct',
    'population_is_cancer',
    'abstract_relevance_binary',
})

def get_model_for_task(task_type: str) -> str:
    """Return model ID for task. Conservative: default to Sonnet."""
    if task_type in HAIKU_SAFE_TASKS:
        return ModelTier.HAIKU.value
    # OPUS tasks would go here if identified
    return ModelTier.SONNET.value  # Safe default
```

**Modify `llm/client.py`:**

```python
# Add optional model_id parameter to call()
def call(
    self,
    prompt: str,
    response_schema: type[T],
    system_prompt: str | None = None,
    temperature: float = 0.0,
    model_id: str | None = None,  # NEW: override default
) -> T:
    model = model_id or self.model_id
    # ... rest unchanged
```

**Effort:** 3-4 days including validation

---

## Final Assessment

| Pattern | Status | Rationale |
|---------|--------|-----------|
| 1. Multi-Agent Coordination | **DROP** | `acquisition_scheduler.py` + APS already implements this |
| 2. Tiered Extraction | **PARTIAL** | Add `ABSTRACT_ONLY` mode for confirmatory evidence |
| 3. Source Ranking | **DROP** | APS in `aps_scorer.py` is better calibrated |
| 4. Model Routing | **IMPLEMENT** | Genuine gap — all tasks use Sonnet |
| 5. Blacklist | **DROP** | `Set[str]` sufficient if needed |

---

## True Enhancers — Precise Specification

### Enhancement A: ABSTRACT_ONLY Extraction Mode

**Location:** `crci/extraction/p0_triage/mode_selection.py`

**Change:**
1. Add `ABSTRACT_ONLY` to `ExtractionMode` enum in `crci/shared/models/enums.py`
2. Add edge-aware routing in `select_extraction_mode()`
3. Modify `crci/extraction/pipeline.py` to skip PDF ingestion for ABSTRACT_ONLY

**Trigger condition:** Paper targets edges where ALL target edges have `strength == "STRONG"` (k ≥ 5 + RCT).

**Effect:** Skip PDF parsing, extract from abstract only, save ~30 seconds + ~$0.05 per paper.

**Effort:** 1-2 days

**Risk:** Low. Falls back to STANDARD if edge coverage unknown.

---

### Enhancement B: Cost-Aware Model Routing

**Location:** New file `crci/llm/model_router.py`, modify `crci/llm/client.py`

**Change:**
1. Create `ModelTier` enum with Haiku/Sonnet/Opus
2. Create `get_model_for_task()` with conservative Haiku-safe list
3. Add `model_id` parameter to `LLMClient.call()`
4. Update extraction agents to pass task_type

**Conservative approach:** Only 5 simple binary tasks use Haiku initially. Expand after empirical validation.

**Effect:** ~30-40% cost reduction on high-volume simple tasks.

**Effort:** 3-4 days

**Risk:** Medium. Must validate Haiku accuracy on each task before adding to safe list.

---

## What Was Wrong in My Previous Analysis

1. **`_estimate_pooled_se_with_overlap()`** — Duplicates `shared_control_handler.py` which already handles this better with SC-1 formula.

2. **`AdequacyChecker` class** — Duplicates `evidence_gap_compiler.py` + `coverage_analyzer.py` which already track k, has_rct, I², and gap classifications per edge.

3. **Routing validation harness** — Overcomplicated. A simple A/B test script comparing Haiku vs Sonnet on 50 samples per task is sufficient.

4. **8-week estimate** — Way too long. True scope is 1-2 days (ABSTRACT_ONLY) + 3-4 days (model routing) = ~1 week total.

---

## Revised Implementation Plan

### Days 1-2: ABSTRACT_ONLY Mode

- [ ] Add `ABSTRACT_ONLY` to `ExtractionMode` enum
- [ ] Modify `select_extraction_mode()` to accept `edge_coverage` parameter
- [ ] Add routing logic: if all target edges STRONG → ABSTRACT_ONLY
- [ ] Modify `pipeline.py` to skip PDF ingestion for ABSTRACT_ONLY mode
- [ ] Test on 5 papers targeting well-covered edges

### Days 3-6: Model Routing

- [ ] Create `crci/llm/model_router.py` with conservative Haiku list
- [ ] Add `model_id` parameter to `LLMClient.call()`
- [ ] Run validation: 50 samples each for `has_effect_size`, `is_rct`, `population_is_cancer`
- [ ] If Haiku accuracy ≥ 95%, keep in safe list; else remove
- [ ] Wire into extraction agents
- [ ] Measure cost before/after on 20 papers

### Day 7: Documentation

- [ ] Update `PROGRESS.md` with routing validation results
- [ ] Archive old Drama analysis documents
- [ ] Document which tasks are validated for Haiku

---

## Files to Archive

```
docs/analysis/archived/
├── DRAMA_ADOPTION_ROADMAP.md      # Original overengineered proposal  
├── DRAMA_PATTERNS_for_CRCI.md     # Detailed patterns (most not applicable)
├── DRAMA_CRCI_QUICK_REF.md        # Quick reference (outdated)
└── DRAMA_vs_CRCI_ANALYSIS.md      # Initial comparison (superseded)
```
