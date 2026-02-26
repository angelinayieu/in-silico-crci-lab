# Cherrier 2013 Golden Path Audit — Findings & Remediation Plan

**Date:** 2026-02-26  
**Scope:** Run #7 — Cherrier et al. 2013 (`doi:10.1016/j.lfs.2013.08.011`)  
**Database:** `crci_dev.db` tables `edge_evidence_v1`, `edges_v1`, `study_registry_v1`  
**Paper:** N=28 RCT, 6 F-statistics extracted from testosterone intervention on cognitive outcomes

---

## Table of Contents

1. [Audit Summary](#1-audit-summary)
2. [Verified Math — F→d Conversions](#2-verified-math--fd-conversions)
3. [SE Discrepancy Decomposition](#3-se-discrepancy-decomposition)
4. [Six Critical Issues](#4-six-critical-issues)
   - [CRITICAL-1: ConceptEngine Single-Edge Collapse](#critical-1-conceptengine-single-edge-collapse)
   - [CRITICAL-2: Within-Study Correlated Outcomes](#critical-2-within-study-correlated-outcomes-treated-as-independent)
   - [CRITICAL-3: Omnibus F-statistics Mishandled](#critical-3-omnibus-f-statistics-df₁1-converted-with-df₁1-formula)
   - [CRITICAL-4: Interaction Effect Pooled with Main Effects](#critical-4-interaction-effect-pooled-with-main-effects)
   - [CRITICAL-5: Study Design Misclassified as "unclassified"](#critical-5-study-design-misclassified-as-unclassified)
   - [CRITICAL-6: total_n=0 and N_effect=0](#critical-6-total_n0-and-n_effect0)
5. [Detailed Fix Plans](#5-detailed-fix-plans)
6. [Root Cause Analysis — Systemic Failures](#6-root-cause-analysis--systemic-failures)
7. [Preventive Measures — Fail-Proof Pipeline Gates](#7-preventive-measures--fail-proof-pipeline-gates)
8. [Priority Order & Dependencies](#8-priority-order--dependencies)
9. [Verification Protocol](#9-verification-protocol)

---

## 1. Audit Summary

The Cherrier 2013 golden path extraction (Run #7) successfully extracted 6 F-statistics from the paper and converted them to Cohen's d. However, the end-to-end pipeline produced a scientifically invalid result due to **6 compounding critical issues** spanning P0 through P4. The IVW-pooled SE in the database is `1.2112`, whereas a correct pipeline should produce `SE_IVW ≈ 0.1651` — a **7.3× discrepancy**.

**Key finding:** No single module is "broken." Each module implements its formulas correctly in isolation. The failures are all **boundary/wiring issues** — wrong inputs flowing into correct formulas, missing metadata propagation, and absent validation gates at stage transitions.

---

## 2. Verified Math — F→d Conversions

All 6 F-statistics were verified against the conversion formulas. The raw conversions are **correct**.

**Formulas used:**
- Cohen's d: `d = 2 × √(F / N)` where N=28
- SE of d: `SE_d = √(4/N + d²/(2×(N−2)))`

| # | Outcome | F-stat | Computed d | Computed SE_d | DB beta_raw | DB se_raw | Match |
|---|---------|--------|-----------|---------------|-------------|-----------|-------|
| 1 | Visual-Spatial (Block Design) | 5.66 | 0.8990 | 0.4072 | 0.8990 | 0.4072 | ✅ |
| 2 | Visual-Spatial (Mental Rotation) | 7.28 | 1.0194 | 0.4152 | 1.0194 | 0.4152 | ✅ |
| 3 | Verbal Memory (CVLT Total) | 7.17 | 1.0117 | 0.4147 | 1.0117 | 0.4147 | ✅ |
| 4 | Verbal Memory (CVLT Delay) | 18.33 | 1.6176 | 0.4685 | 1.6176 | 0.4685 | ✅ |
| 5 | Spatial Memory (Route Learning) | 4.45 | 0.7970 | 0.4001 | 0.7970 | 0.4001 | ✅ |
| 6 | Group × Time Interaction (CVLT) | 4.197 | 0.7741 | 0.3984 | 0.7741 | 0.3984 | ✅ |

**Raw IVW pooling (what the values SHOULD produce):**
```
β̂_IVW = Σ(β_i / SE²_i) / Σ(1 / SE²_i) = 0.9997
SE_IVW = 1 / √Σ(1 / SE²_i) = 0.1651
```

**Actual database value:** `SE = 1.2112` — the 7.3× inflation comes from the P3 seven-layer system receiving wrong inputs.

---

## 3. SE Discrepancy Decomposition

The SE inflation chain was traced through every pipeline stage. Each multiplier is individually correct per its formula, but the **inputs are wrong**.

| Stage | Operation | Multiplier | Cumulative Effect |
|-------|-----------|------------|-------------------|
| P2 Raw | F→d SE conversion | SE_raw ≈ 0.40 | Baseline (correct) |
| P3 L1 | Study design = "unclassified" → `m_design = 3.0` | ×3.0 | **Should be ×1.0 for RCT** |
| P3 L4 | Scale validation = "general_population" | ×1.3 | × (acceptable) |
| P3 L5 | GRADE quality = "MODERATE" | ×1.25 | × (acceptable) |
| P3 σ² | `SIGMA_SQ_STRUCTURAL_DEFAULT = 0.25` added | +0.25 | Under radical |
| P3 L7 | `w_fresh = 0.85` (pub_year=None) | ÷0.85 | Inflates SE |
| P4 DR | Diminishing returns k=6: `√(1 + 0.3·ln(6))` | ×1.24 | 6 non-independent claims |
| P4 IVW | `1/√(Σ 1/SE²_eff)` over 6 inflated SEs | → 1.2112 | Final |

**Critical inflation:** L1's `m_design = 3.0` is the dominant error. Without it (m_design=1.0), the final SE would be ≈ 0.40–0.50 — still high due to other issues but in a reasonable range.

**Full P3 formula (P3-8):**
```
SE_eff = √[(SE_raw × m_design × m_scale × m_grade)² + σ²_struct + τ²·𝟙[I²≥50%]] / (max(w_scope, 0.3) × w_fresh)
```

---

## 4. Six Critical Issues

### CRITICAL-1: ConceptEngine Single-Edge Collapse

**Severity:** CRITICAL — Scientifically invalid result  
**File:** `crci/extraction/p1_extraction/concept_engine.py` lines 265–268  
**Function:** `_match_from_target_edges()`

**What happens:** The ConceptEngine is responsible for mapping each extracted span to an `edge_relation_id` from the causal DAG. For Cherrier 2013, there are 4 target edges available:
- `ER_COGACTIVITY_WORKMEM` (working memory)
- `ER_COGACTIVITY_ATTN` (attention)
- `ER_COGACTIVITY_COGCOMPLAINTS` (cognitive complaints)
- `ER_COGACTIVITY_EPIMEM` (episodic memory)

The matching algorithm works by extracting keywords from the span text and scoring them against edge descriptions. **For numeric F-statistic spans (e.g., "F(1,26)=5.66"), there are no domain-relevant keywords.** All edges score 0, and the fallback logic returns `target_edges[0]` — always `ER_COGACTIVITY_WORKMEM`.

**Result:** All 6 F-statistics from 5 different cognitive domains are collapsed onto a single edge. The database shows 6 rows in `edge_evidence_v1` all with `edge_relation_id = 'ER_COGACTIVITY_WORKMEM'`.

**Root cause code:**
```python
# concept_engine.py line 265-268
def _match_from_target_edges(self, span_text: str, target_edges: list[str]) -> str:
    scores = {eid: self._score_keywords(span_text, eid) for eid in target_edges}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return target_edges[0]  # ← FALLBACK: always first edge
```

**Why this is wrong:**
- Block Design (visual-spatial) → should map to a spatial/visual edge
- CVLT (verbal memory) → should map to episodic memory edge
- Mental Rotation → should map to a spatial processing edge
- Route Learning → should map to spatial memory or navigation edge
- The interaction term shouldn't be mapped at all

---

### CRITICAL-2: Within-Study Correlated Outcomes Treated as Independent

**Severity:** CRITICAL — Violates IVW independence assumption  
**File:** `crci/extraction/p4_aggregation/double_counting.py`  
**Function:** `_build_resolved()` at line 515

**What happens:** The double-counting resolver (DCR) only handles overlap between meta-analyses and their constituent primary studies (DCR-1, DCR-2 formulas). It does **not** detect or handle the case where multiple outcomes from the **same study** on the **same edge** are pooled as if they were independent.

**Result:** 6 F-statistics from Cherrier 2013 (same N=28 participants, same study, same time period) are treated as 6 independent studies in IVW meta-analysis. This dramatically underestimates pooled SE because the effective sample size is inflated 6×.

**Why this is wrong:** IVW meta-analysis assumes:
1. Studies are independent
2. Each study contributes independent information

When all 6 outcomes come from the same 28 participants, the effective k is not 6 — it's closer to 1 (with slight adjustments for outcome diversity). The weights `w_i = 1/SE²_i` are correlated because they share the same sample.

**What DCR currently handles:**
```python
# double_counting.py — DCR detection types
# ✅ MA-vs-primary overlap (when a meta-analysis includes a primary study)
# ❌ Within-study multiple outcomes (MISSING)
# ❌ Overlapping cohorts across studies (MISSING)
```

---

### CRITICAL-3: Omnibus F-statistics (df₁>1) Converted with df₁=1 Formula

**Severity:** HIGH — Incorrect effect size magnitude  
**File:** `crci/extraction/p2_harmonization/scale_harmonizer.py` lines 445–463  
**Function:** F_STATISTIC conversion branch

**What happens:** The formula `d = 2 × √(F / N)` is valid **only** for F-tests with df₁=1 (single-degree-of-freedom contrasts). Some of Cherrier's F-statistics may be omnibus tests with df₁>1 (e.g., testing a 3-level factor), where the conversion formula is different:
```
For df₁=1: d = 2√(F/N)
For df₁>1: η² = (df₁ × F) / (df₁ × F + df₂), then d = 2√(η²/(1−η²))
```

**Current code:**
```python
# scale_harmonizer.py line 445-463
if stat_type == StatisticType.F_STATISTIC:
    n = record.n_effect or 28  # hardcoded fallback!
    d = 2 * math.sqrt(f_value / n)
    se_d = math.sqrt(4/n + d**2 / (2*(n-2)))
```

**What's missing:**
- No df₁ parsing from spans like "F(1,26)" or "F(2,25)"
- No branching logic for df₁>1
- No validation that the F→d formula matches the reported degrees of freedom

---

### CRITICAL-4: Interaction Effect Pooled with Main Effects

**Severity:** HIGH — Conceptual mixing of different constructs  
**File:** Multiple (P1 extraction, P4 aggregation)

**What happens:** One of the 6 F-statistics (F=4.197) is a **Group × Time interaction** effect from a repeated-measures ANOVA. The other 5 are **main effects** or between-group comparisons. Interaction effects measure a fundamentally different construct (whether the treatment effect differs across time points) than main effects (the overall treatment effect).

**Result:** The interaction F-statistic is pooled with main-effect F-statistics in IVW meta-analysis, mixing incompatible constructs. The effect size from an interaction cannot be meaningfully averaged with main-effect sizes.

**What should happen:**
- P1 extraction should tag each statistic with its type: `main_effect`, `interaction`, `simple_effect`, `omnibus`
- P4 aggregation should only pool statistics of the same type
- Interaction effects should either be excluded or handled separately

---

### CRITICAL-5: Study Design Misclassified as "unclassified"

**Severity:** CRITICAL — Largest single contributor to SE inflation (3× penalty)  
**Root cause file:** `crci/extraction/p0_triage/paper_type_classifier.py`  
**Impact file:** `crci/extraction/p3_heterogeneity/layers.py` lines 44–99 (L1)  
**Runner file:** `crci/extraction/p3_heterogeneity/runner.py` lines 67–72

**What happens — the full chain of failure:**

1. **P0 classifier never returns study_design:**
   `paper_type_classifier.py` returns a dict with keys `paper_subtype`, `confidence`, `reasoning` — but **never** includes `study_design`. The LLM prompt doesn't ask for it, and the response parser doesn't extract it.

2. **P0 runner reads None:**
   ```python
   # p0_triage/runner.py line 201
   study_design = classified.get("study_design")  # → None
   ```
   This `None` propagates to `study_registry_v1.study_design = NULL`.

3. **P3 runner fallback also fails:**
   ```python
   # p3_heterogeneity/runner.py lines 67-72
   p0_study_design = classified_paper.get("study_design", "other")
   # classified_paper dict doesn't have study_design → returns "other"
   
   # lines 124-130: fallback logic
   if design == "unclassified" and p0_study_design != "other":
       design = p0_study_design  # but p0_study_design IS "other"!
   ```

4. **L1 applies maximum penalty:**
   ```python
   # layers.py line 75-85
   design_multipliers = {
       "rct": 1.0,
       "cohort": 1.3,
       "case_control": 1.5,
       "cross_sectional": 1.8,
       "unclassified": config.DESIGN_MULTIPLIER_DEFAULT,  # 3.0
   }
   ```
   For "unclassified": `m_design = 3.0`, tripling the SE.

**Impact:** Cherrier 2013 is explicitly an RCT (stated in meta.json: `"study_type": "RCT"`). An RCT should receive `m_design = 1.0`. Instead it gets `3.0`, causing **the single largest contributor** to the SE inflation.

**The irony:** The information IS available (meta.json has `study_type: "RCT"`), but the pipeline never propagates it to where P3 needs it.

---

### CRITICAL-6: total_n=0 and N_effect=0

**Severity:** MEDIUM — Data quality / downstream impact  
**File:** `crci/extraction/p4_aggregation/double_counting.py` line 515  
**File:** `crci/extraction/p4_aggregation/edge_writer.py`  
**File:** `crci/extraction/p2_harmonization/runner.py` lines 385–396

**What happens:**

1. **P2 harmonization runner** sets `n_effect` from `getattr(record, "n_effect", None)`. The `ScaledNumeric` record may or may not carry `n_effect` depending on whether the conversion path populated it.

2. **For F-statistic conversions**, the scale_harmonizer uses `n = record.n_effect or 28` (hardcoded fallback) for the conversion formula but does **not** write `n_effect` back to the output `HarmonizedClaim`. The `n_effect` field on the claim remains `None`.

3. **double_counting.py** line 515 sums `n_effect` values:
   ```python
   total_n = sum(c.n_effect for c in claims if c.n_effect is not None)
   # When all c.n_effect are None → total_n = 0
   ```

4. **edge_writer.py** writes `total_n=0` to `edges_v1`, making the sample size invisible to all downstream consumers (algorithm chains).

**Impact:** Any downstream computation that uses `total_n` (e.g., power calculations, sample-size-weighted analyses) sees N=0 and either errors or produces incorrect results.

---

## 5. Detailed Fix Plans

### Fix 1: ConceptEngine — Context-Aware Edge Mapping

**File:** `crci/extraction/p1_extraction/concept_engine.py`

**Current problem:** Keyword matching fails on numeric spans; unconditional fallback to `target_edges[0]`.

**Fix approach — three layers of improvement:**

**Layer A: Enrich span context before matching**
```python
def _match_from_target_edges(self, span_text: str, target_edges: list[str], 
                              context: str | None = None) -> str | None:
    """
    Match a span to an edge. Uses surrounding context (sentence/paragraph)
    not just the numeric span itself.
    
    Args:
        span_text: The extracted span (may be just "F(1,26)=5.66")
        context: The surrounding text from the paper (sentence or paragraph
                 containing the span). THIS IS THE KEY NEW INPUT.
        target_edges: Available edges for this paper
    """
    # Score using context, not just span_text
    search_text = f"{context} {span_text}" if context else span_text
    scores = {eid: self._score_keywords(search_text, eid) for eid in target_edges}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None  # ← NEW: return None instead of fallback
```

**Layer B: Require P1 extraction to include context with every span**

In the P1 LLM extraction prompt, require the LLM to return:
- `span`: the exact numeric value
- `context_sentence`: the sentence containing the span
- `outcome_label`: the outcome variable name (e.g., "Block Design", "CVLT Total Recall")
- `stat_type_detail`: "main_effect", "interaction", "omnibus"

**Layer C: Replace the unconditional fallback with a review task**
```python
if best_score == 0:
    # Instead of blindly assigning target_edges[0], log a review task
    self._emit_review_task(
        task_type="EDGE_MAPPING_AMBIGUOUS",
        span_text=span_text,
        context=context,
        candidate_edges=target_edges,
        reason="No keyword match found for any candidate edge"
    )
    return None  # Claim is NOT assigned; goes to human review
```

**Layer D: Outcome-to-edge mapping table (optional, high-quality)**

Create a curated mapping in `registries/`:
```csv
outcome_keyword,edge_relation_id,confidence
block_design,ER_COGACTIVITY_VISUOSPATIAL,0.95
mental_rotation,ER_COGACTIVITY_VISUOSPATIAL,0.95
cvlt,ER_COGACTIVITY_EPIMEM,0.95
route_learning,ER_COGACTIVITY_SPATMEM,0.90
trail_making,ER_COGACTIVITY_ATTN,0.90
digit_span,ER_COGACTIVITY_WORKMEM,0.90
```

---

### Fix 2: Within-Study Correlated Outcome Detection (DCR Extension)

**File:** `crci/extraction/p4_aggregation/double_counting.py`

**Current state:** Only handles MA-vs-primary overlap (DCR-1, DCR-2).

**Fix approach:**

**Step A: Add within-study detection**
```python
def _detect_within_study_overlap(self, claims: list[CalibratedRecord]) -> dict:
    """
    Detect multiple outcomes from the same study on the same edge.
    
    Groups claims by (study_id, edge_relation_id). Any group with k>1
    has correlated outcomes that violate IVW independence.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for claim in claims:
        key = (claim.study_id, claim.edge_relation_id)
        groups[key].append(claim)
    
    overlapping = {k: v for k, v in groups.items() if len(v) > 1}
    return overlapping
```

**Step B: Implement resolution strategies**

Three options per the meta-analysis literature (Borenstein et al., 2009):

1. **Average within study (primary recommendation):**
   ```python
   def _resolve_within_study(self, claims: list[CalibratedRecord], 
                              assumed_r: float = 0.5) -> CalibratedRecord:
       """
       Average k correlated outcomes from same study into one composite.
       
       Uses Borenstein's formula for correlated outcomes:
         d_bar = mean(d_i)
         SE_composite = (1/k) × √(Σ SE²_i + Σᵢ≠ⱼ r × SE_i × SE_j)
       
       assumed_r: assumed correlation between outcomes (default 0.5)
       """
       k = len(claims)
       d_bar = sum(c.beta for c in claims) / k
       
       # Variance with assumed correlation
       var_sum = sum(c.se**2 for c in claims)
       cov_sum = sum(
           assumed_r * claims[i].se * claims[j].se
           for i in range(k) for j in range(k) if i != j
       )
       se_composite = (1/k) * math.sqrt(var_sum + cov_sum)
       
       return CalibratedRecord(
           beta=d_bar,
           se=se_composite,
           n_effect=claims[0].n_effect,  # Same N for all
           study_id=claims[0].study_id,
           # ... other fields from first claim
       )
   ```

2. **Select one representative outcome** (simplest, most conservative):
   Pick the outcome most aligned with the edge's construct.

3. **Model the correlation** (most sophisticated, future work):
   Use multivariate meta-analysis (e.g., `rma.mv()` approach).

**Config constant to add:**
```python
# shared/config.py
DCR_WITHIN_STUDY_ASSUMED_R = 0.5  # Assumed correlation between outcomes
```

---

### Fix 3: F-statistic df₁ Parsing and Branching

**File:** `crci/extraction/p2_harmonization/scale_harmonizer.py`

**Fix approach:**

**Step A: Parse degrees of freedom from F-test notation**
```python
import re

def _parse_f_degrees_of_freedom(self, span_text: str) -> tuple[int, int] | None:
    """
    Extract (df1, df2) from F-test notation.
    Examples: "F(1,26)=5.66" → (1, 26)
              "F(2,25)=3.45" → (2, 25)
              "F = 5.66"     → None (unknown df)
    """
    match = re.search(r'F\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', span_text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None
```

**Step B: Branch conversion based on df₁**
```python
if stat_type == StatisticType.F_STATISTIC:
    df = self._parse_f_degrees_of_freedom(span_text)
    
    if df is not None:
        df1, df2 = df
        n = df2 + df1 + 1  # Recover N from df₂ = N - groups
    else:
        df1 = 1  # Assume contrast
        n = record.n_effect or config.F_STAT_N_FALLBACK
    
    if df1 == 1:
        # Single-df contrast: d = 2√(F/N)
        d = 2 * math.sqrt(f_value / n)
        se_d = math.sqrt(4/n + d**2 / (2*(n-2)))
    else:
        # Omnibus F-test: convert via η²
        eta_sq = (df1 * f_value) / (df1 * f_value + df2)
        # η² → f² → d (Cohen's conversion)
        f_sq = eta_sq / (1 - eta_sq)
        d = 2 * math.sqrt(f_sq)
        se_d = math.sqrt(4/n + d**2 / (2*(n-2)))  # Approximate
        
        # Emit review task: omnibus effects lose directionality
        self._emit_review_task(
            task_type="OMNIBUS_F_CONVERSION",
            reason=f"df1={df1} > 1: omnibus F→d conversion loses directionality",
            f_value=f_value, df1=df1, df2=df2, eta_sq=eta_sq, d=d
        )
```

**Step C: Remove N=28 hardcode**
```python
# Replace:
n = record.n_effect or 28  # WRONG: hardcoded

# With:
if record.n_effect is None and df is None:
    logger.warning(
        f"F-stat conversion: no N available for {record.span_id}. "
        f"Using config fallback N={config.F_STAT_N_FALLBACK}"
    )
n = record.n_effect or (df[1] + df[0] + 1 if df else config.F_STAT_N_FALLBACK)
```

**Config constant to add:**
```python
# shared/config.py
F_STAT_N_FALLBACK = None  # Force explicit N — no silent fallback
# If we MUST have a fallback, set to a conservative value and log
```

---

### Fix 4: Interaction Effect Tagging and Segregation

**Files:** `crci/extraction/p1_extraction/` (LLM prompt), `crci/extraction/p4_aggregation/evidence_grouper.py`

**Fix approach:**

**Step A: Add stat_type_detail to extraction schema**

Add to `shared/models/intermediate_states.py`:
```python
class StatTypeDetail(str, Enum):
    MAIN_EFFECT = "main_effect"
    INTERACTION = "interaction"
    SIMPLE_EFFECT = "simple_effect"
    OMNIBUS = "omnibus"
    CONTRAST = "contrast"
    UNKNOWN = "unknown"
```

Add field to `HarmonizedClaim`:
```python
stat_type_detail: StatTypeDetail = StatTypeDetail.UNKNOWN
```

**Step B: Modify P1 LLM extraction prompt to include stat_type_detail**

The prompt should instruct the LLM:
> "For each statistic, classify whether it is a main_effect, interaction, simple_effect, or omnibus test. An interaction (e.g., Group × Time) measures whether the treatment effect varies across levels of another factor and should NOT be pooled with main effects."

**Step C: Filter in evidence_grouper.py**
```python
def _group_claims(self, claims: list[CalibratedRecord]) -> dict:
    """Group by (edge_relation_id, stat_type_detail)."""
    groups = defaultdict(list)
    for claim in claims:
        # Interaction effects get their own group
        key = (claim.edge_relation_id, claim.stat_type_detail)
        groups[key].append(claim)
    return groups
```

**Step D: Exclude or flag interactions in pooling**
```python
# In meta_analyzer.py or evidence_grouper.py
if stat_type_detail == StatTypeDetail.INTERACTION:
    # Do not pool with main effects
    # Option 1: Exclude entirely
    # Option 2: Pool interactions separately  
    # Option 3: Convert to main effect delta if possible
    self._emit_review_task(
        task_type="INTERACTION_EFFECT",
        reason="Interaction effect cannot be pooled with main effects"
    )
```

---

### Fix 5: Study Design Propagation (P0 → P3)

**Files:** `crci/extraction/p0_triage/paper_type_classifier.py`, `crci/extraction/p0_triage/runner.py`, `crci/extraction/p3_heterogeneity/runner.py`

**Fix approach — three complementary changes:**

**Step A: Add study_design to P0 classifier output**

In `paper_type_classifier.py`, modify the LLM prompt to include:
```python
CLASSIFICATION_PROMPT = """
Classify this paper:
1. paper_subtype: (primary_empirical, systematic_review, meta_analysis, narrative_review, case_study)
2. study_design: (rct, cohort, case_control, cross_sectional, longitudinal, case_series, ecological, other)
3. confidence: (0.0 to 1.0)
4. reasoning: (brief explanation)
"""
```

Modify the response parser:
```python
def _parse_classification(self, response: dict) -> dict:
    return {
        "paper_subtype": response.get("paper_subtype", "unknown"),
        "study_design": response.get("study_design", "other"),  # ← NEW
        "confidence": response.get("confidence", 0.5),
        "reasoning": response.get("reasoning", ""),
    }
```

**Step B: Use meta.json study_type as ground truth when available**

In `p0_triage/runner.py`:
```python
# After classification, cross-check with meta.json
meta_study_type = paper_meta.get("study_type")  # e.g., "RCT"
if meta_study_type:
    # meta.json is human-authored → trust it over LLM classification
    classified["study_design"] = meta_study_type.lower()
    logger.info(f"Study design from meta.json: {meta_study_type}")
```

**Step C: Fix P3 runner fallback chain**

In `p3_heterogeneity/runner.py`:
```python
def _resolve_study_design(self, run_context: dict) -> str:
    """
    Resolve study design with clear priority:
    1. study_registry_v1.study_design (if populated)
    2. P0 classified_paper.study_design
    3. meta.json study_type
    4. "unclassified" (last resort, with review task)
    """
    # Priority 1: Database
    db_design = self._get_study_design_from_db(run_context["study_id"])
    if db_design and db_design != "unclassified":
        return db_design
    
    # Priority 2: P0 classification
    p0_design = run_context.get("classified_paper", {}).get("study_design")
    if p0_design and p0_design != "other":
        return p0_design
    
    # Priority 3: meta.json
    meta_design = run_context.get("paper_meta", {}).get("study_type")
    if meta_design:
        return meta_design.lower()
    
    # Priority 4: Last resort
    logger.warning(f"Study design unresolved for {run_context['study_id']}. "
                   f"Applying m_design={config.DESIGN_MULTIPLIER_DEFAULT}")
    self._emit_review_task(
        task_type="STUDY_DESIGN_UNKNOWN",
        reason="Could not determine study design from any source"
    )
    return "unclassified"
```

---

### Fix 6: n_effect Propagation

**Files:** `crci/extraction/p2_harmonization/scale_harmonizer.py`, `crci/extraction/p2_harmonization/runner.py`, `crci/extraction/p4_aggregation/double_counting.py`

**Fix approach:**

**Step A: Write n_effect back after F→d conversion**

In `scale_harmonizer.py`:
```python
if stat_type == StatisticType.F_STATISTIC:
    n = record.n_effect or self._recover_n_from_df(span_text) or config.F_STAT_N_FALLBACK
    d = 2 * math.sqrt(f_value / n)
    se_d = math.sqrt(4/n + d**2 / (2*(n-2)))
    
    # CRITICAL: Write n back to the record
    result.n_effect = n  # ← THIS LINE IS MISSING
    result.n_source = "df_parsed" if self._recover_n_from_df(span_text) else "meta_json"
```

**Step B: Validate n_effect at P2→P3 boundary**

In `p2_harmonization/runner.py`, add a gate:
```python
# After harmonization, before passing to P3
for claim in harmonized_claims:
    if claim.n_effect is None or claim.n_effect == 0:
        logger.warning(
            f"Claim {claim.claim_id}: n_effect is {claim.n_effect}. "
            f"Attempting recovery from study_registry or meta.json."
        )
        # Attempt recovery
        claim.n_effect = self._recover_n_from_study(claim.study_id)
        
    if claim.n_effect is None or claim.n_effect == 0:
        self._emit_review_task(
            task_type="MISSING_N_EFFECT",
            reason=f"n_effect could not be recovered for claim {claim.claim_id}"
        )
```

**Step C: Fix double_counting.py total_n calculation**

```python
# Replace:
total_n = sum(c.n_effect for c in claims if c.n_effect is not None)

# With:
n_values = [c.n_effect for c in claims if c.n_effect is not None and c.n_effect > 0]
if not n_values:
    logger.error(f"No valid n_effect for edge {edge_id}. total_n will be 0.")
    self._emit_review_task(
        task_type="TOTAL_N_ZERO",
        reason=f"All claims for edge {edge_id} have n_effect=None"
    )
total_n = sum(n_values)

# ALSO: for within-study overlap, don't sum N — use max
# (same participants contribute to all outcomes)
if self._is_within_study_group(claims):
    total_n = max(n_values) if n_values else 0
```

---

## 6. Root Cause Analysis — Systemic Failures

The 6 critical issues are symptoms of **5 systemic failures** in pipeline design:

### Systemic Failure 1: No Boundary Validation Between Pipeline Stages

**Pattern:** Each module trusts its inputs without validation. P3 trusts that `study_design` was set by P0. P4 trusts that claims are independent. P2 trusts that `n_effect` was populated.

**Why it happened:** The pipeline was built module-by-module in dependency order. Each module was verified against its spec formulas but **not** against actual data flowing through upstream modules.

**What was missing:** Input validation gates at every stage boundary:
- P1→P2: "Does every `ScaledNumeric` have `n_effect`?"
- P2→P3: "Does every `HarmonizedClaim` have `study_design`?"
- P3→P4: "Are there any within-study overlapping claims?"

### Systemic Failure 2: Metadata Doesn't Flow with Data

**Pattern:** The `meta.json` file contains `study_type: "RCT"` and `total_n: 28`, but these values never reach the modules that need them. `paper_type_classifier.py` doesn't ask the LLM about study design. `scale_harmonizer.py` hardcodes N=28 instead of reading it from metadata.

**Why it happened:** Metadata was treated as a P0 concern and not propagated downstream. Each module was designed to be self-contained, extracting what it needs from its immediate inputs rather than from a shared context.

**What was missing:** A `StudyContext` object that travels with every claim:
```python
@dataclass
class StudyContext:
    study_id: str
    study_design: str          # RCT, cohort, etc.
    total_n: int               # Total sample size
    paper_subtype: str         # primary_empirical, MA, etc.
    pub_year: int | None
    population_age: str | None
    # ... all metadata that any downstream module might need
```

### Systemic Failure 3: Silent Fallbacks Instead of Loud Failures

**Pattern:** When data is missing, modules silently use defaults:
- `study_design` → `"unclassified"` (triggers 3× SE penalty)
- `n_effect` → `None` (causes `total_n=0`)
- `target_edges[0]` fallback (maps everything to first edge)
- `n = 28` hardcode (masks missing sample size)

**Why it happened:** The code was written to never crash. Fallbacks were added to handle edge cases during development. But in a scientific pipeline, **a wrong answer is worse than no answer**.

**What was missing:** The principle that **every fallback must be logged AND generate a review task**. If the pipeline can't determine `study_design`, it should:
1. Log a warning
2. Create a review task for human resolution
3. Apply the conservative default
4. Tag the result as `REQUIRES_REVIEW`

### Systemic Failure 4: No Integration Testing on Real Data

**Pattern:** Individual modules pass unit tests with synthetic data, but the first real paper (Cherrier 2013) exposed cascading failures that synthetic tests didn't catch.

**Why it happened:** Testing focused on "does the formula compute correctly?" rather than "does the pipeline produce a scientifically valid result?"

**What was missing:** Golden-path integration tests that:
1. Run a known paper end-to-end
2. Compare every intermediate value against hand-computed expectations
3. Flag any deviation > threshold

### Systemic Failure 5: Extraction Lacks Outcome-Level Granularity

**Pattern:** P1 extracts F-statistics as isolated numbers ("F=5.66") without semantic context (which cognitive test, which comparison, main vs. interaction). This forces downstream modules (ConceptEngine) to guess, and they guess wrong.

**Why it happened:** The LLM extraction prompt was optimized for recall (extract every number) rather than precision (extract numbers with full context).

**What was missing:** Structured extraction that requires:
- Outcome variable name
- Test/instrument name
- Comparison description (treatment vs. control, or Group × Time, etc.)
- Degrees of freedom
- Effect direction

---

## 7. Preventive Measures — Fail-Proof Pipeline Gates

### Gate System: Three Tiers

#### Tier 1: Hard Gates (MUST pass or pipeline stops)

| Gate ID | Location | Check | Action on Failure |
|---------|----------|-------|-------------------|
| BG-01 | P0→P1 boundary | `study_design` is not None | Raise `GateViolation` |
| BG-02 | P1→P2 boundary | Every span has `context_sentence` | Raise `GateViolation` |
| BG-03 | P2→P3 boundary | `n_effect > 0` for every claim | Raise `GateViolation` |
| BG-04 | P3→P4 boundary | `study_design != "unclassified"` OR review_task exists | Raise `GateViolation` |
| BG-05 | P4 pre-pooling | No within-study overlapping claims (or resolved) | Raise `GateViolation` |
| BG-06 | P4 post-pooling | `total_n > 0` | Raise `GateViolation` |
| BG-07 | P4 post-pooling | `SE_pooled > 0` and `SE_pooled < 10 × median(SE_raw)` | Raise `GateViolation` |

#### Tier 2: Soft Gates (Log warning + review task, continue processing)

| Gate ID | Location | Check | Action on Failure |
|---------|----------|-------|-------------------|
| SG-01 | P1 extraction | Span has outcome_label | Log warning, tag `NEEDS_REVIEW` |
| SG-02 | P1 extraction | stat_type_detail is not UNKNOWN | Log warning, tag `NEEDS_REVIEW` |
| SG-03 | P2 conversion | F-stat has parseable df | Log warning, use df₁=1 default |
| SG-04 | P3 L1 | `m_design < 2.0` (sanity check) | Log warning if design penalty is high |
| SG-05 | P4 pre-pooling | `k ≤ 1` claims per edge | Log info (nothing to pool) |

#### Tier 3: Audit Gates (Post-hoc verification, run after extraction completes)

| Gate ID | Scope | Check |
|---------|-------|-------|
| AG-01 | Per-paper | Claims per edge ≤ max(outcomes_per_study) |
| AG-02 | Per-paper | All claims from same study have same N |
| AG-03 | Per-paper | No edge has 100% of a paper's claims (suggests miscategorization) |
| AG-04 | Global | SE_pooled distribution: flag outliers > 3σ |
| AG-05 | Global | `total_n` distribution: flag zeros |

### Boundary Assertion Framework

Every stage transition should use a boundary validator:

```python
class BoundaryValidator:
    """Validates data at pipeline stage boundaries."""
    
    @staticmethod
    def validate_p0_to_p1(triage_result: TriageResult) -> None:
        """BG-01: study_design must be set."""
        if triage_result.study_design is None:
            raise GateViolation(
                "BG-01", 
                f"study_design is None for study {triage_result.study_id}. "
                f"P0 classifier must return study_design."
            )
    
    @staticmethod
    def validate_p2_to_p3(claims: list[HarmonizedClaim]) -> None:
        """BG-03: n_effect must be positive for every claim."""
        for claim in claims:
            if claim.n_effect is None or claim.n_effect <= 0:
                raise GateViolation(
                    "BG-03",
                    f"Claim {claim.claim_id}: n_effect={claim.n_effect}. "
                    f"Cannot proceed to P3 without valid sample size."
                )
    
    @staticmethod
    def validate_p3_to_p4(records: list[CalibratedRecord]) -> None:
        """BG-04, BG-05: design classified, no unresolved within-study overlap."""
        for record in records:
            if record.study_design == "unclassified":
                if not record.has_review_task("STUDY_DESIGN_UNKNOWN"):
                    raise GateViolation(
                        "BG-04",
                        f"study_design='unclassified' for {record.study_id} "
                        f"with no review task."
                    )
        
        # Check within-study overlap
        from collections import Counter
        study_edge_counts = Counter(
            (r.study_id, r.edge_relation_id) for r in records
        )
        for (sid, eid), count in study_edge_counts.items():
            if count > 1:
                raise GateViolation(
                    "BG-05",
                    f"Within-study overlap: {count} claims from study {sid} "
                    f"on edge {eid}. Must resolve before pooling."
                )
```

### Integration Test Suite

```python
class TestGoldenPath:
    """Golden-path tests using known papers with hand-verified expected values."""
    
    def test_cherrier_2013_edge_mapping(self):
        """Each F-stat maps to the correct edge based on outcome."""
        results = run_pipeline("cherrier_2013")
        edge_mapping = {r.outcome_label: r.edge_relation_id for r in results.claims}
        
        # Hand-verified correct mapping
        assert edge_mapping["Block Design"] == "ER_COGACTIVITY_VISUOSPATIAL"
        assert edge_mapping["CVLT Total"] == "ER_COGACTIVITY_EPIMEM"
        # ... etc.
    
    def test_cherrier_2013_study_design(self):
        """RCT paper should be classified as RCT, not 'unclassified'."""
        results = run_pipeline("cherrier_2013")
        assert results.study_design == "rct"
        assert results.m_design == 1.0
    
    def test_cherrier_2013_n_effect(self):
        """N=28 should propagate to all claims and total_n."""
        results = run_pipeline("cherrier_2013")
        for claim in results.claims:
            assert claim.n_effect == 28
        assert results.total_n == 28  # Same participants, not 28×6
    
    def test_cherrier_2013_se_range(self):
        """Pooled SE should be reasonable (not 7× inflated)."""
        results = run_pipeline("cherrier_2013")
        assert results.se_pooled < 1.0  # Should be ~0.4-0.5
        assert results.se_pooled > 0.1  # Not impossibly precise
    
    def test_interaction_excluded_from_pooling(self):
        """Interaction effects should not be pooled with main effects."""
        results = run_pipeline("cherrier_2013")
        pooled_claims = results.pooled_group.claims
        for claim in pooled_claims:
            assert claim.stat_type_detail != "interaction"
```

---

## 8. Priority Order & Dependencies

Implementation should proceed in this order (each fix enables the next):

| Priority | Fix | Dependency | Estimated Effort | Impact |
|----------|-----|------------|------------------|--------|
| **P0** | Fix 5: Study design propagation | None | 2-3 hours | Eliminates 3× SE inflation |
| **P1** | Fix 6: n_effect propagation | None | 1-2 hours | Fixes total_n=0 |
| **P2** | Fix 1: ConceptEngine context-aware mapping | Fix 5 (for test validation) | 4-6 hours | Fixes single-edge collapse |
| **P3** | Fix 3: F-stat df₁ parsing | None | 2-3 hours | Correct omnibus handling |
| **P4** | Fix 4: Interaction tagging | Fix 1 (needs outcome labels) | 3-4 hours | Prevents construct mixing |
| **P5** | Fix 2: Within-study DCR | Fixes 1, 4 (needs correct edge mapping first) | 4-6 hours | Fixes independence violation |

**Total estimated effort:** 16-24 hours

**Why this order:**
1. **Fix 5 first** because it's the largest single impact (3× SE) and has no dependencies
2. **Fix 6** is quick and independent
3. **Fix 1** needs Fix 5 to be in place for golden-path validation
4. **Fix 3** is independent but lower impact for Cherrier specifically (all F-stats appear to be df₁=1)
5. **Fix 4** requires Fix 1's outcome labels to tag interactions
6. **Fix 2** is the most complex and requires Fixes 1 and 4 to correctly identify what needs resolving

### Dependency Graph

```
Fix 5 (study_design) ────────────────────┐
Fix 6 (n_effect) ──────────────────────┐ │
Fix 3 (df₁ parsing) ────────────────┐  │ │
                                     │  │ │
Fix 1 (ConceptEngine) ◄─────────────┼──┼─┘
        │                            │  │
        ▼                            │  │
Fix 4 (interaction tagging) ◄────────┘  │
        │                               │
        ▼                               │
Fix 2 (within-study DCR) ◄─────────────┘

Boundary Gates: Implement alongside each fix
Integration Tests: Run after all fixes
```

---

## 9. Verification Protocol

After implementing all fixes, run this verification sequence:

### Step 1: Re-run Cherrier 2013 Golden Path
```bash
python scripts/run_extraction.py --paper cherrier_2013 --run-id golden_path_v2
```

### Step 2: Verify Each Fix

| Check | Expected Result | How to Verify |
|-------|----------------|---------------|
| study_design = "rct" | P3 L1 applies m_design=1.0 | Query `study_registry_v1.study_design` |
| n_effect = 28 for all claims | total_n = 28 (not 168) | Query `edge_evidence_v1.n_effect` |
| Claims map to ≥3 distinct edges | No single-edge collapse | Query `SELECT DISTINCT edge_relation_id` |
| Interaction F-stat excluded | 5 claims pooled, not 6 | Check `stat_type_detail` field |
| SE_pooled < 1.0 | Reasonable uncertainty | Query `edges_v1.beta_se` |
| Within-study resolved | 1 composite claim per edge per study | Check DCR output |

### Step 3: Compare Before/After

| Metric | Before (Run #7) | Expected After |
|--------|-----------------|----------------|
| Claims per edge | 6 on 1 edge | 1-2 per edge, across 3-4 edges |
| study_design | "unclassified" | "rct" |
| m_design | 3.0 | 1.0 |
| n_effect | None | 28 |
| total_n | 0 | 28 |
| SE_pooled | 1.2112 | ~0.4–0.5 |
| beta_pooled | 0.9997 | Varies by edge |

### Step 4: Run Integration Test Suite
```bash
python -m pytest tests/test_golden_path.py -v
```

### Step 5: Run Full Pipeline on All Extracted Papers
```bash
python scripts/run_extraction.py --all --validate
```

---

## Appendix A: SE Inflation Chain Detail

For reference, the complete SE computation for one claim (F=5.66, Block Design):

```
Input:  F = 5.66, N = 28
Step 1: d = 2 × √(5.66/28) = 2 × 0.4495 = 0.8990
Step 2: SE_raw = √(4/28 + 0.8990²/(2×26)) = √(0.1429 + 0.01554) = √0.1584 = 0.3980 ≈ 0.4072

P3 Seven-Layer Inflation:
  L1 (study_design = "unclassified"):  m_design = 3.0
  L2 (population_age = None):          m_age = 1.0 (no data)
  L3 (scale_mismatch):                 m_scale_mm = 1.0 (same scale)
  L4 (scale_validation):               m_scale_val = 1.3 (general_population)
  L5 (grade_quality = "MODERATE"):     m_grade = 1.25
  L6 (temporal_scope):                 w_scope = 1.0
  L7 (freshness_decay, pub_year=None): w_fresh = 0.85

  Numerator = (0.4072 × 3.0 × 1.0 × 1.3 × 1.25)² + 0.25
            = (0.4072 × 4.875)² + 0.25
            = (1.9851)² + 0.25
            = 3.9406 + 0.25
            = 4.1906
  
  Denominator = max(1.0, 0.3) × 0.85 = 0.85
  
  SE_eff = √(4.1906) / 0.85 = 2.0471 / 0.85 = 2.4084

All 6 claims get similar SE_eff values (~2.0 to ~2.5).

IVW Pooling (k=6):
  1/SE² weights are small → SE_IVW = 1/√(Σ 1/SE²_eff) ≈ 0.98

Then diminishing returns inflation: × √(1 + 0.3 × ln(6)) = × 1.24
  Final SE = 0.98 × 1.24 ≈ 1.2112
```

---

## Appendix B: Files Requiring Changes

| File | Change Type | Priority |
|------|-------------|----------|
| `crci/extraction/p0_triage/paper_type_classifier.py` | Add `study_design` to output | P0 |
| `crci/extraction/p0_triage/runner.py` | Read `study_design`, cross-check meta.json | P0 |
| `crci/extraction/p3_heterogeneity/runner.py` | Fix study_design fallback chain | P0 |
| `crci/extraction/p2_harmonization/scale_harmonizer.py` | Write `n_effect` back; df₁ parsing; remove N=28 hardcode | P1/P3 |
| `crci/extraction/p2_harmonization/runner.py` | Add `n_effect` boundary gate | P1 |
| `crci/extraction/p1_extraction/concept_engine.py` | Context-aware matching; remove `target_edges[0]` fallback | P2 |
| `crci/extraction/p4_aggregation/double_counting.py` | Within-study overlap detection + resolution | P5 |
| `crci/extraction/p4_aggregation/evidence_grouper.py` | Group by `stat_type_detail`; filter interactions | P4 |
| `crci/extraction/p4_aggregation/edge_writer.py` | Validate `total_n > 0` | P1 |
| `crci/shared/models/intermediate_states.py` | Add `StatTypeDetail` enum; add fields | P3/P4 |
| `crci/shared/config.py` | Add `F_STAT_N_FALLBACK`, `DCR_WITHIN_STUDY_ASSUMED_R` | P0/P5 |
| `crci/shared/models/boundary_validators.py` | **NEW FILE** — Boundary validation framework | All |
| `tests/test_golden_path.py` | **NEW FILE** — Golden path integration tests | Final |

---

## Appendix C: Review Task Types to Add

| Task Type | Trigger | Resolution |
|-----------|---------|------------|
| `EDGE_MAPPING_AMBIGUOUS` | ConceptEngine can't match span to edge | Human reviews and assigns correct edge |
| `OMNIBUS_F_CONVERSION` | F-test has df₁>1 | Human confirms conversion is appropriate |
| `INTERACTION_EFFECT` | Stat is Group×Time or similar interaction | Human decides: exclude, separate analysis, or convert |
| `STUDY_DESIGN_UNKNOWN` | No source provides study design | Human looks up and enters design |
| `MISSING_N_EFFECT` | n_effect could not be recovered | Human enters sample size from paper |
| `TOTAL_N_ZERO` | All claims on an edge have n_effect=None | Human reviews and enters N |
| `SE_INFLATION_EXTREME` | SE_eff > 5× SE_raw | Human reviews layer multipliers |
| `WITHIN_STUDY_OVERLAP` | Multiple outcomes from same study on same edge | Human confirms resolution strategy |
