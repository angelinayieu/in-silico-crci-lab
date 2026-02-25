# Extraction Pipeline Testing Report

**Date:** 2025-02-25  
**Scope:** End-to-end testing of automated extraction pipeline (P0→P1→TB→P2→P3→P4→P4B→P5→P6)  
**Papers tested:** Cherrier 2013 (RCT), Campbell 2017 (RCT), Cifu 2018 (systematic review)  
**LLM model:** `claude-sonnet-4-20250514` via `crci/llm/client.py`  
**Database:** SQLite at `crci_dev.db` (83 tables)

---

## 1. Executive Summary

The automated extraction pipeline was tested on 3 papers across 10+ iterative runs. **9 inter-chain wiring bugs** were discovered and fixed across 7 files. After all fixes, the pipeline runs through all 9 chains (P0→P1→TB→P2→P3→P4→P4B→P5→P6) without crashes on both RCT papers.

**However, the pipeline produces zero deployable evidence.** The root cause is an architecture-level gap: the LLM agents extract metadata labels (instrument names, timepoints, sample sizes as isolated tokens) rather than structured effect-size evidence records (β + SE + CI linked to DAG edges). This means no records survive P3's SE_eff assembly, P4 has nothing to aggregate, and P6 correctly blocks deployment.

---

## 2. Test Matrix — Per-Paper Results

### 2.1 Cherrier 2013 (RCT, cognitive rehabilitation, N=28)

| Chain | Status | Detail |
|-------|--------|--------|
| **P0 Triage** | ✅ PASS | `RCT_cognitive`, confidence=0.95, mode=DEEP |
| **P1 Extraction** | ✅ PASS | 10 agents, 29 annotations, 79 span_labels, 25 ATB-accepted, 3 ATB-rejected |
| **TB Trust Boundary** | ✅ PASS | 34/79 spans parsed CLEAN (45 are text labels → expected FAILED), 34 validated, 0 warnings, 0 rejected |
| **P2 Harmonization** | ✅ PASS | 32/32 passed plausibility, 32 converted, 32 harmonized, 32 aligned, 32 scored, 32 assigned family=`edge_intervention` |
| **P3 Heterogeneity** | ⚠️ PASS (0 output) | 32 records through 7 layers, but **0/32 have SE** → 0 records with SE_eff assembled |
| **P4 Aggregation** | ✅ PASS (empty) | No calibrated records to aggregate |
| **P4B Pub Bias** | ✅ PASS (empty) | No pooled estimates to assess |
| **P5 Sufficiency** | ✅ PASS (trivial) | 0 edges, 0 coverage, grade=unknown |
| **P6 Deployment** | 🛑 BLOCK (correct) | Gate P6-G1: "No compiled edges found. Pipeline produced no usable evidence." 16 PASS, 1 WARN, 1 FAIL |

**LLM usage:** 14 calls, 84,267 prompt tokens, 5,913 completion tokens (~$0.35)

### 2.2 Campbell 2017 (RCT, exercise intervention, N=19)

| Chain | Status | Detail |
|-------|--------|--------|
| **P0 Triage** | ✅ PASS | `RCT_exercise`, confidence=0.95, mode=DEEP |
| **P1 Extraction** | ✅ PASS | 10 agents, 36 annotations, 73 span_labels, 31 ATB-accepted, 5 ATB-rejected |
| **TB Trust Boundary** | ✅ PASS | 33/73 spans parsed CLEAN, all validated |
| **P2 Harmonization** | ✅ PASS | 31 records through all 6 submodules |
| **P3 Heterogeneity** | ⚠️ PASS (0 output) | 31 records through 7 layers, **0/31 have SE** → 0 SE_eff |
| **P4–P5** | ✅ PASS (empty) | Same as Cherrier |
| **P6 Deployment** | 🛑 BLOCK (correct) | Same P6-G1 failure |

**LLM usage:** 14 calls, 88,882 prompt tokens, 9,944 completion tokens (~$0.42)

### 2.3 Cifu 2018 (systematic review, mindfulness-based interventions)

| Chain | Status | Detail |
|-------|--------|--------|
| **P0 Triage** | ✅ PASS | `systematic_review`, confidence=0.95 |
| **P1 Extraction** | ⏳ In progress | SHALLOW mode (only AG01+AG10), long-running due to large PDF |

Cifu 2018 is expected to produce no deployable evidence even if it completes, because systematic reviews contain summary tables rather than primary outcome data.

---

## 3. Bugs Found and Fixed — Complete Catalog

### Bug #1: SQLite JSONB Import Failure

**File:** `crci/shared/models/tables.py` (line 24)  
**Symptom:** `ImportError` / schema creation failure — `study_registry_v1` table missing columns  
**Root cause:** `from sqlalchemy.dialects.postgresql import JSONB` fails silently on SQLite; columns defined with `JSONB` type were not created  
**Fix:** Changed to `from sqlalchemy import JSON as JSONB` — standard `JSON` type works on all backends  
**Impact:** Without this fix, no tables could be created correctly. Schema was dropped and recreated (83 tables).

```python
# BEFORE (broken on SQLite)
from sqlalchemy.dialects.postgresql import JSONB

# AFTER (works on all backends)
from sqlalchemy import JSON as JSONB
```

---

### Bug #2: Span Labels Never Forwarded to Trust Boundary

**File:** `crci/extraction/p1_extraction/runner.py`  
**Symptom:** TB received 0 span_labels despite agents producing 79  
**Root cause:** P1 runner collected `agent_output.annotations` into `all_raw_annotations` but never collected `agent_output.span_labels`. The `context` dict only contained annotations, not span_labels.  
**Fix:** Added `all_span_labels` accumulator, extended it from each agent output, and stored in `context["all_span_labels"]`  
**Impact:** This was the primary data flow break. Without span_labels, TB had nothing to parse, and the entire numeric pipeline was dead.

```python
# ADDED to P1 runner
all_span_labels: list[Any] = []
# ... in agent loop:
all_span_labels.extend(agent_output.span_labels)
# ... after loop:
context["all_span_labels"] = all_span_labels
```

---

### Bug #3: Wrong Attribute Name on ParsedNumeric

**File:** `crci/extraction/tb_trust_boundary/runner.py`  
**Symptom:** `AttributeError: 'ParsedNumeric' object has no attribute 'status'`  
**Root cause:** TB runner used `p.status.value` but the actual field is `p.parse_status`  
**Fix:** Changed `p.status.value` to `p.parse_status.value`

```python
# BEFORE
if p.status.value == "PARSED":

# AFTER
if p.parse_status.value == "CLEAN":
```

(Note: This fix also involved Bug #4 — the enum value was wrong too.)

---

### Bug #4: Wrong Enum Value for Parse Success

**File:** `crci/extraction/tb_trust_boundary/runner.py`  
**Symptom:** 0 spans passed the CLEAN filter even though 34 parsed successfully  
**Root cause:** TB runner filtered by `"PARSED"` but the `ParseStatus` enum uses `"CLEAN"` for successful parses  
**Fix:** Changed filter string from `"PARSED"` to `"CLEAN"`

```python
# ParseStatus enum values:
class ParseStatus(StrEnum):
    CLEAN = "CLEAN"         # ← this is what successful parse produces
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"
```

---

### Bug #5: Wrong Call Signature for consistency_checker

**File:** `crci/extraction/tb_trust_boundary/runner.py`  
**Symptom:** `TypeError: check_consistency() got unexpected keyword argument 'parsed_claims'`  
**Root cause:** TB runner called `check_consistency(parsed_claims=valid_claims, paper_id=paper_id)` but the actual signature is `check_consistency(parsed_values=..., paper_id=...)`  
**Fix:** Changed kwarg name from `parsed_claims` to `parsed_values`

```python
# BEFORE
consistency_result = check_consistency(parsed_claims=valid_claims, paper_id=paper_id)

# AFTER
consistency_result = check_consistency(parsed_values=valid_claims, paper_id=paper_id)
```

---

### Bug #6: Raw Float Passed Where TypedNumericValue Expected

**File:** `crci/extraction/tb_trust_boundary/consistency_checker.py`  
**Symptom:** `ValidationError: TypedNumericValue expected, got float` in `_check_plausibility()`  
**Root cause:** The function constructed `ValidatedNumeric(value=pv.parsed_value, ...)` but `ValidatedNumeric.value` expects a `TypedNumericValue` object, not a raw float.  
**Fix:** Construct a proper `TypedNumericValue` from the `ParsedNumeric` fields before wrapping in `ValidatedNumeric`

```python
# BEFORE (broken)
return ValidatedNumeric(
    span_id=pv.span_id,
    value=pv.parsed_value,  # ← raw float, wrong type
    ...
)

# AFTER (correct)
typed_value = TypedNumericValue(
    value=pv.parsed_value if pv.parsed_value is not None else 0.0,
    original_text=pv.raw_text,
    ci_lower=pv.parsed_lower,
    ci_upper=pv.parsed_upper,
)
return ValidatedNumeric(
    span_id=pv.span_id,
    value=typed_value,  # ← proper TypedNumericValue
    ...
)
```

---

### Bug #7: ConsistencyResult Treated as Dict

**File:** `crci/extraction/p2_harmonization/runner.py` (line 52)  
**Symptom:** `AttributeError: 'ConsistencyResult' object has no attribute 'get'`  
**Root cause:** P2 runner called `context.get("tb_result", {}).get("valid_claims", [])`, treating `tb_result` as a dict. But `tb_result` is a `ConsistencyResult` dataclass with `.validated`, `.warnings`, `.rejected` attributes.  
**Fix:** Access `tb_result.validated` instead of dict `.get()` calls

```python
# BEFORE
claims = context.get("tb_result", {}).get("valid_claims", [])

# AFTER
tb_result = context.get("tb_result")
if tb_result is not None and hasattr(tb_result, "validated"):
    claims = tb_result.validated
```

---

### Bug #8: P2 Submodule Call Signatures Entirely Wrong

**File:** `crci/extraction/p2_harmonization/runner.py` (entire orchestration logic)  
**Symptom:** `TypeError: check_plausibility() got an unexpected keyword argument 'session'`  
**Root cause:** The P2 runner called ALL 6 submodules with incorrect signatures:

| Submodule | Runner called | Actual signature |
|-----------|---------------|------------------|
| `check_plausibility` | `(claims, session=session)` (batch + session) | `(span_id, value, *, is_correlation=False)` (single item) |
| `route_conversion` | mostly OK but wrong input type | `(validated, effect_type_reported, ...)` |
| `harmonize_scale` | mostly OK | `(routed, effect_type_reported, ...)` |
| `align_orientation` | `(list, session=session)` (batch) | `(scaled, dag_orientation, reported_direction_positive, orientation_confidence)` (single) |
| `score_identification` | `(list, session=session)` (batch) | `(scaled, study_design, ...)` (single) |
| `assign_parameter_family` | correct | correct (keyword-only) |

**Fix:** Complete rewrite of P2 runner orchestration to iterate per-item with correct parameter names and types. Also changed output from `IdentificationResult` list to `ScaledNumeric` list (P3 needs `.beta` and `.se` fields).

---

### Bug #9: CoverageMatrix Missing Attributes

**File:** `crci/extraction/p5_sufficiency/runner.py` (line 105)  
**Symptom:** `AttributeError: 'CoverageMatrix' object has no attribute 'n_covered'`  
**Root cause:** P5 runner referenced `coverage.n_covered` and `coverage.n_expected` but `CoverageMatrix` dataclass fields are `n_strong`, `n_moderate`, `n_weak`, `n_gap`, `total_edges`  
**Fix:** Computed `n_covered = coverage.n_strong + coverage.n_moderate + coverage.n_weak` and `n_expected = coverage.total_edges`

---

## 4. Bug Pattern Analysis

All 9 bugs fall into **inter-chain wiring mismatches**. Each chain's internal logic is correctly implemented, but the boundaries between chains are broken:

```
Type mismatches:     Bugs #6, #7      (float vs TypedNumericValue, dataclass vs dict)
Attribute names:     Bugs #3, #9      (status vs parse_status, n_covered vs n_strong+...)
Enum values:         Bug  #4          ("PARSED" vs "CLEAN")
Call signatures:     Bugs #5, #8      (wrong kwargs for consistency_checker, all P2 submodules)
Data flow omission:  Bug  #2          (span_labels not forwarded)
Platform compat:     Bug  #1          (PostgreSQL JSONB on SQLite)
```

**Root cause of the pattern:** The codebase was built file-by-file (per the PROMPT_SEQUENCE build order) without integration testing between phases. Each file was verified against its spec in isolation, but the actual runtime types, attribute names, and call conventions diverge at every boundary.

---

## 5. Architecture Gap — Why Zero Evidence Is Produced

### 5.1 The Data Flow Problem

The pipeline has two parallel data paths from P1:

```
Path A: span_labels → TB numeric parser → P2 harmonization → P3 → P4 → ...
Path B: annotations → reconciliation → ATB → stored in DB (dead end for pipeline)
```

**Path A** is the quantitative pipeline. **Path B** stores qualitative metadata. The problem is that Path A receives metadata labels, not effect-size data.

### 5.2 What Span Labels Actually Contain

Distribution of span label types from Cherrier 2013 (79 total, 34 parsed CLEAN):

```
MEASUREMENT_TIMEPOINT:  16  → "Week 12", "Month 6" etc.
OUTCOME_INSTRUMENT:      7  → "FACT-Cog", "Stroop", "TMT-A"
MEDIATOR:                6  → "cortisol", "BDNF", "neuroplasticity"
TIMEPOINT:               3  → "baseline", "post-intervention", "follow-up"
STUDY_ARM:               2  → "intervention", "control"
FOLLOW_UP_DURATION:      2  → "12 weeks", "6 months"
TITLE:                   1
JOURNAL:                 1
STUDY_DESIGN:            1
RANDOMIZATION:           1
CONTROL_TYPE:            1
SAMPLE_SIZE:             1  → "28"
P_VALUE:                 1  → "0.05"
ATTRITION_N:             1  → "3"
INTERVENTION_TYPE:       1
FREQUENCY:               1
```

From Campbell 2017 (73 total):

```
MEASUREMENT_TIMEPOINT:   9
OUTCOME_INSTRUMENT:      8
MEDIATOR:                8
INTERNAL_CONSISTENCY_N:  6  → Cronbach's alpha values
STUDY_ARM:               2
CONVERGENT_VALIDITY:     2
TITLE:                   1
TIMEPOINT:               1
STUDY_DESIGN:            1
RANDOMIZATION:           1
INTERVENTION_TYPE:       1
CONTROL_TYPE:            1
BLINDING:                1
```

### 5.3 What the Pipeline Needs

For the downstream pipeline (P2→P3→P4) to produce usable evidence, each record needs:

```python
TypedNumericValue(
    value=β,              # Point estimate (effect size)
    se=SE,                # Standard error
    ci_lower=CI_lower,    # 95% CI lower bound
    ci_upper=CI_upper,    # 95% CI upper bound
    p_value=p,            # p-value
    n=N,                  # Sample size
)
```

**Plus** linkage to a DAG edge (`edge_relation_id`), study design, and effect type.

What it actually receives: isolated tokens like `SAMPLE_SIZE=28` or `P_VALUE=0.05` with no way to assemble them into a complete evidence record.

### 5.4 The SE Derivation Cascade

The scale harmonizer (`_resolve_se()`) has a 3-level cascade to recover SE:

1. **Direct SE** → `value.se` → Always `None` (never extracted)
2. **Derive from CI** → `value.ci_lower + value.ci_upper` → Rarely both present on the same token
3. **Approximate from p-value + N** → `value.p_value + value.n` → Never both present on the same token

Result: **0% SE recovery rate** across 63 total spans from both papers.

### 5.5 What the Annotations Contain

The 25 ATB-accepted annotations (Cherrier) are qualitative metadata:

```
measurement_limitation:     7  → Instrument validity notes
mechanism_hypothesis:       6  → Biological pathway hypotheses
temporal_onset:             5  → Timing observations
population_specificity:     3  → Participant characteristics
generalizability_concern:   1
clinical_significance:      1
attrition_bias:             1
adherence_data:             1
```

These are useful for contextual analysis but contain no numeric effect-size data. They are stored in the DB via `study_annotations_raw_v1` but not fed into the quantitative pipeline.

---

## 6. Chain-by-Chain Status (Post-Fix)

### P0: Pre-Extraction Triage ✅ FULLY OPERATIONAL

- **PDF ingestion** (`pdfplumber`): Extracts canonical text, section headers
- **Paper type classification** (LLM): Correctly identifies RCT subtypes, SRs with 0.95 confidence
- **Mode selection**: DEEP for primary studies, SHALLOW for reviews
- **Output:** `classified_paper` dict with `paper_subtype`, `confidence`, `reasoning`

### P1: Hybrid Multi-Agent Extraction ✅ OPERATIONAL (but agents need prompt redesign)

- **10 agents run sequentially:** AG01 (Metadata), AG02 (Design), AG03 (Cohort), AG04 (Outcome), AG05 (Stats), AG06 (Risk of Bias), AG07 (Biological), AG08 (Quality), AG10 (Strategic), AG11 (Instrument)
- **Each agent** receives relevant paper sections and produces:
  - `span_labels`: Character-offset labeled spans (metadata tokens)
  - `annotations`: Structured qualitative observations
- **Reconciliation**: Clusters 29 raw annotations into 9 clusters, produces 28 reconciled
- **ATB (Annotation Trust Boundary)**: Validates provenance, applies AT-01 through AT-05 rules

**Issue:** Agent prompts extract metadata labels, not structured effect-size evidence. The prompts need to be redesigned to output `{edge_id, β, SE, CI, N, effect_type}` tuples.

### TB: Trust Boundary ✅ OPERATIONAL (after 5 fixes)

- **Numeric parser**: 37 value types, regex + rule-based parsing, plausibility validation
- **Consistency checker**: Cross-validates parsed values within paper
- **Gate TB-G1**: Enforced (requires ≥1 valid parsed span)

**Performance:** 34/79 spans parse CLEAN on Cherrier; 33/73 on Campbell. The "failed" 45-40 are text labels (JOURNAL, STUDY_DESIGN, etc.) that correctly fail numeric parsing.

### P2: Harmonization & Gating ✅ OPERATIONAL (after complete rewrite)

Six submodules, all running correctly per-item:

| Step | Module | Function | Status |
|------|--------|----------|--------|
| P2-S1 | `plausibility_checker` | Bounds check (Gate P2-G1) | ✅ 32/34 pass (2 rejected: year=2013, sample=72) |
| P2-S2 | `conversion_router` | CG1-CG4 gate checks | ✅ 32/32 routed |
| P2-S3 | `scale_harmonizer` | SMD/log-scale conversion | ✅ 32/32 scaled (all SE=None) |
| P2-S4 | `orientation_aligner` | Direction standardization (Gate P2-G2) | ✅ 32/32 aligned |
| P2-S5 | `identification_scorer` | Causal identification | ✅ 32/32 scored |
| P2-FA | `parameter_family_assigner` | Freshness family | ✅ 32/32 → `edge_intervention` |

**Output type:** `ScaledNumeric` (has `.beta`, `.se`, `.scale`, `.span_id`)

### P3: Seven-Layer Heterogeneity ⚠️ OPERATIONAL (but no SE → 0 output)

All 7 layers apply correctly:

| Layer | Function | Status |
|-------|----------|--------|
| L1 | Study design multiplier | ✅ (defaults to `m_design=3.0` for unclassified) |
| L2 | Scope matching weight | ✅ (`w_scope=1.0` default) |
| L3 | Statistical heterogeneity (I², τ²) | ✅ (no group data → trivial) |
| L4 | Cancer-validation scale | ✅ (general_population default) |
| L5 | GRADE quality | ✅ (MODERATE default) |
| L6 | Temporal decay | ✅ (0 days → no exclusion) |
| L7 | Freshness decay | ✅ (no pub_year → default weight 0.85) |

**Bottleneck:** `se_raw = getattr(rec, "se", None)` → always `None` → record skipped

### P4: Aggregation + DCR ✅ OPERATIONAL (empty path tested)

- Correctly handles 0 calibrated records
- IVW meta-analysis, double-counting resolution ready but untested with data

### P4B: Publication Bias Assessment ✅ OPERATIONAL (empty path tested)

- Correctly skips when no pooled estimates exist

### P5: Sufficiency & Coherence ✅ OPERATIONAL (after attribute fix)

- Chain validation: 0 pathways (no data)
- Coverage analysis: 0 edges (no data)
- E-value computation: 0 edges
- Sufficiency reporter: grade=unknown (no data)

### P6: Deployment Validation ✅ OPERATIONAL

18 validation rules execute:

| Rule | Status |
|------|--------|
| G1: minimum_edges | 🛑 FAIL — No compiled edges |
| G2-G9: quality checks | ✅ PASS (trivially, on empty set) |
| G10: coverage_minimum | ⚠️ WARN — 0% < 50% |
| G11-G18: consistency checks | ✅ PASS |

**Gate P6-G1 correctly BLOCKs deployment.** This is the expected behavior when no evidence survives.

### P7: Compilation ❌ NOT REACHED

P7 only runs after P6 deployment gate passes. Since P6 blocks, P7 has never executed.

---

## 7. Data Type Flow Map (Actual Runtime)

```
P0 outputs:
  context["classified_paper"]  = dict{paper_subtype: PaperSubtype, confidence: float}
  context["paper_id"]          = str (STUDY_xxxx)
  context["extraction_mode"]   = "DEEP" | "SHALLOW"
  context["ingested_paper"]    = dict{canonical_text, sections, ...}

P1 outputs:
  context["all_span_labels"]   = list[SpanLabel]           ← Bug #2 fix
  context["accepted_annotations"] = list[dict]             ← ATB-validated
  context["reconciled_annotations"] = list[dict]

TB outputs:
  context["tb_result"]         = ConsistencyResult         ← Bug #7 (was treated as dict)
    .validated                 = list[ValidatedNumeric]    ← 34 items
    .warnings                  = list[ValidatedNumeric]    ← 0 items
    .rejected                  = list[...]                 ← 0 items

P2 outputs:
  context["p2_plausibility"]   = dict{passed: list, failed: list}
  context["p2_converted"]      = dict{converted: list, failed: list}
  context["p2_harmonized"]     = list[ScaledNumeric]       ← 32 items, all se=None
  context["p2_oriented"]       = list[ScaledNumeric]
  context["p2_identified"]     = list[IdentificationResult]
  context["harmonized_records"]= list[ScaledNumeric]       ← P3 input (was IdentificationResult)
  context["parameter_family_counts"] = dict{str: int}

P3 outputs:
  context["calibrated_records"]= list[ScaledNumeric]       ← 0 items (SE filter)

P4 outputs:
  context["pooled_estimates"]  = list[...]                 ← 0 items

P5 outputs:
  context["coverage_analysis"] = CoverageMatrix
  context["sufficiency_report"]= dict

P6 outputs:
  Gate P6-G1 BLOCK → raises GateViolation
```

---

## 8. LLM Agent Prompt Analysis

Each of the 10 agents uses a structured prompt that instructs the LLM to output specific JSON schemas. The prompts are stored in `crci/llm/prompts/` and loaded by each agent.

### What agents are asked to extract:

| Agent | ID | Extracts | Output Format |
|-------|-----|----------|---------------|
| Metadata | AG01 | Title, journal, year, DOI | span_labels (TITLE, JOURNAL, YEAR) |
| Design | AG02 | Study design, arms, randomization | span_labels + annotations |
| Cohort | AG03 | Sample size, demographics, inclusion/exclusion | span_labels + annotations |
| Outcome | AG04 | Outcome instruments, measurement timepoints | span_labels (OUTCOME_INSTRUMENT, MEASUREMENT_TIMEPOINT) |
| Stats | AG05 | Statistical results, p-values | span_labels (P_VALUE, SAMPLE_SIZE, etc.) |
| Risk of Bias | AG06 | Bias assessment, blinding, attrition | span_labels + annotations |
| Biological | AG07 | Biological mechanisms, pathways | annotations (mechanism_hypothesis) |
| Quality | AG08 | Study quality indicators | annotations |
| Strategic | AG10 | Strategic intelligence, research gaps | annotations (research_gap) |
| Instrument | AG11 | Instrument psychometric properties | span_labels (INTERNAL_CONSISTENCY_N, etc.) |

### The missing agent behavior:

None of the agents extract **structured effect-size records** like:
```json
{
  "edge_relation_id": "E_ADT_COG_001",
  "outcome_measure": "FACT-Cog PCI",
  "effect_type": "group_diff",
  "beta": -4.2,
  "se": 1.8,
  "ci_lower": -7.7,
  "ci_upper": -0.7,
  "p_value": 0.02,
  "n_treatment": 14,
  "n_control": 14,
  "timepoint": "post_intervention"
}
```

This structured extraction is what the pipeline actually needs to produce usable evidence.

---

## 9. Recommendations

### 9.1 Critical Path: Agent Prompt Redesign (Priority 1)

The agents need prompts that extract **complete evidence records** linking:
- A specific DAG edge (from `EDGE_REGISTRY.csv`)
- A point estimate with uncertainty (β ± SE, or β with CI, or mean difference with p-value + N)
- Effect type classification (group_diff, std_beta, OR, HR, etc.)

**Approach options:**

| Option | Description | Effort | Risk |
|--------|-------------|--------|------|
| **A: New evidence agent** | Add AG09 focused solely on extracting structured numeric evidence tables | Medium | Need to avoid duplicate extraction |
| **B: Restructure AG05** | Redesign StatsLabelAgent to output complete evidence records instead of isolated p-values | Medium | May lose current metadata extraction |
| **C: Post-P1 assembly** | Add a claim assembly stage that groups related spans (outcome + p-value + N) into records | High | Complex cross-referencing logic |
| **D: Single-pass structured extraction** | Replace multi-agent with a single comprehensive structured extraction prompt | Low | May reduce extraction quality |

**Recommendation: Option A** — Add a dedicated evidence extraction agent (AG09) that receives the paper text and outputs structured `{edge_id, β, SE/CI, N, effect_type}` records. Keep existing agents for metadata enrichment.

### 9.2 SE Derivation (Priority 2)

Even with structured extraction, many papers report results as mean ± SD or p-values without explicit SE. The `_resolve_se()` cascade in `scale_harmonizer.py` already handles CI→SE and p+N→SE derivation. What's missing:

- **SD→SE conversion**: If group means and SDs are extracted with sample sizes, compute `SE = SD / √N`
- **Mean difference + p-value → SE**: `SE = |mean_diff| / z(p)` where `z = norm.ppf(1 - p/2)`
- **F-statistic → SE**: `SE = |mean_diff| / √F` for 2-group comparisons

These conversions exist in the spec (SYS_EXTRACTION_COMPLETE.md) but need to be wired through the consistency checker's `TypedNumericValue` construction.

### 9.3 Edge Linkage (Priority 3)

Currently no mechanism links extracted numeric values to specific DAG edges. The pipeline needs:
- Agent prompts that reference `EDGE_REGISTRY.csv` edge IDs
- Or a post-extraction matching step that maps (outcome_instrument + treatment_type) → edge_relation_id

### 9.4 Integration Testing (Priority 4)

Add integration tests that verify chain boundaries:

```python
# test_chain_wiring.py
def test_p1_to_tb_types():
    """Verify P1 span_labels are correctly typed for TB input."""
    
def test_tb_to_p2_types():
    """Verify ConsistencyResult.validated contains ValidatedNumeric objects."""
    
def test_p2_to_p3_types():
    """Verify P2 output has .beta and .se attributes P3 needs."""
```

---

## 10. Files Modified in This Testing Session

| File | Lines Changed | Nature of Change |
|------|--------------|------------------|
| `crci/shared/models/tables.py` | +1 -1 | JSONB→JSON alias |
| `crci/extraction/p1_extraction/runner.py` | +12 -0 | span_labels forwarding |
| `crci/extraction/tb_trust_boundary/runner.py` | +20 -20 | 4 fixes (attribute, enum, kwargs, result access) |
| `crci/extraction/tb_trust_boundary/consistency_checker.py` | +8 -3 | TypedNumericValue construction |
| `crci/extraction/p2_harmonization/runner.py` | +100 -37 | Complete rewrite of submodule orchestration |
| `crci/extraction/p3_heterogeneity/runner.py` | +16 -0 | Debug logging for SE availability |
| `crci/extraction/p5_sufficiency/runner.py` | +4 -2 | CoverageMatrix attribute fix |

**Total:** 162 insertions, 62 deletions across 7 files.

---

## 11. Appendix: Verified Chain Signatures

For future reference, the actual function signatures of all P2 submodules (the source of Bug #8):

```python
# P2-S1: plausibility_checker.py
def check_plausibility(span_id: str, value: TypedNumericValue, *, is_correlation: bool = False) -> ValidatedNumeric

# P2-S2: conversion_router.py
def route_conversion(validated: ValidatedNumeric, effect_type_reported: str, *, has_orientation_metadata: bool = True, target_scale_override: TargetScale | None = None) -> RoutedNumeric

# P2-S3: scale_harmonizer.py
def harmonize_scale(routed: RoutedNumeric, effect_type_reported: str, *, sd_anchor: SDAnchor | None = None, study_sd: float | None = None) -> ScaledNumeric

# P2-S4: orientation_aligner.py
def align_orientation(scaled: ScaledNumeric, dag_orientation: Orientation, reported_direction_positive: bool, orientation_confidence: float) -> ScaledNumeric

# P2-S5: identification_scorer.py
def score_identification(scaled: ScaledNumeric, study_design: str, *, adjustment_strategy: str | None = None, known_confounders_addressed: int = 0, total_known_confounders: int = 0) -> IdentificationResult

# P2-FA: parameter_family_assigner.py
def assign_parameter_family(*, paper_subtype: PaperSubtype | str | None = None, edge_family: str | None = None, meta_source_flag: MetaSourceFlag | str | None = None, extraction_context: str | None = None) -> ParameterFamily
```
