# CRCI Pipeline — Implementation Plan (v2, spec-aligned)

**Date:** 2026-02-26 | **Revised:** 2026-02-26 after spec-alignment review  
**Status:** Post-audit, single-paper pipeline verified on Cifu 2018 SR  
**Objective:** Produce at least 1 evidence record that survives P3 with SE_eff populated

---

## Current Reality

The pipeline runs all 10 stages (P0→P7) without crashing. But **zero deployable
evidence records survive P3** because of a root-cause chain:

```
AG05 outputs isolated tokens (a p-value here, an N there)
    ↓ grouping_id exists in prompt but is discarded (not on SpanLabel model)
TB parses them individually (no grouping)
    ↓ each ParsedNumeric has one field; TypedNumericValue.se/ci/p/n all None
P2 has no SE, CI, or edge linkage on any record
    ↓ hardcoded defaults for orientation, effect_type
P3 drops everything (SE is None)
    ↓ 0 records survive
P4-P7 operate on empty inputs
```

**Focus directive:** Stay on Workstream 1 until `edge_evidence_v1` has at least 1
record surviving P3 with `SE_eff != None`. Dashboard and batch automation are
distractions until the golden-path evidence record exists.

**Validation target:** Cherrier 2013 (RCT with effect sizes in tables), NOT an SR.

---

## Architecture Constraints (from spec review)

These constraints override previous plan decisions:

| Constraint | Source | Implication |
|------------|--------|-------------|
| `SpanLabel` must not carry `edge_relation_id` | SYS_EX §312-330 defines SpanLabel as stats-only. Cross-boundary fields = schema drift. | Edge linkage goes in ConceptEngine (1C), not SpanLabel |
| Edge linkage belongs in ConceptEngine (EX-P1-CE) | Master Spec v2.0 §5.7, SYS_EX §515-520 | Implement ConceptEngine as the spec-defined ontology grounding step, not AG05 bloat |
| Gates must raise, not log | CLAUDE.md enforcement rules | P3 SE-missing must `raise GateViolation` per record, caught at loop boundary |
| Don't invent acquisition queue statuses | Spec defines terminal states for `acquisition_queue_v1` | Use `extraction_runs.status` for extraction outcome, don't add `"extracted"` to queue |
| EDGE_REGISTRY.csv is a seed artifact, not runtime truth | Spec architecture is table-driven (`edge_ontology_v1`) | Load CSV into DB at seed time; ConceptEngine reads from DB tables |
| Missingness provenance codes (AGENT_MISS, PARSE_FAILURE, etc.) | AUTOMATED_RETRIEVAL_PLAN Module 3.2 | Track WHY SE is missing so we know whether to acquire more papers or fix an agent |

---

## Workstream 1: Fix Evidence Extraction

**Gate:** At least 1 record survives P3 with `SE_eff != None` on Cherrier 2013.  
Do NOT proceed to Workstream 2 or 3 until this gate passes.

### 1A. Add `grouping_id` to `SpanLabel` model

**File:** `crci/shared/models/intermediate_states.py` line 146  
**Spec basis:** SYS_EX §312-330 defines SpanLabel with `grouping_id` for AG05.
The model is missing it.

**Current code:**
```python
class SpanLabel(BaseModel):
    span_id: str
    label_type: str
    value: str | None = None
    numeric_value: float | None = None
    char_start: int
    char_end: int
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_section: str | None = None
    source_table_id: str | None = None
```

**Change — add `grouping_id` only (NOT `edge_relation_id`):**
```python
class SpanLabel(BaseModel):
    span_id: str
    label_type: str
    value: str | None = None
    numeric_value: float | None = None
    char_start: int
    char_end: int
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_section: str | None = None
    source_table_id: str | None = None
    grouping_id: str | None = None  # Links related stats (β + CI + p + N)
```

**Why NOT edge_relation_id here:** SpanLabel is a stats extraction artifact. Edge
linkage is ontology grounding — a separate concern that belongs in ConceptEngine
(step 1C). Mixing them creates duplicated logic and harder debugging ("was the edge
wrong because stats labeling was wrong or mapping was wrong?").

**Also update:**
- `SpanLabelResponse` in `crci/llm/response_schemas.py` — ensure span item class
  includes `grouping_id: str | None = None` (the prompt already asks for it)
- AG05's `_parse_response()` in `ag05_stats_label.py` — propagate
  `grouping_id=getattr(span, "grouping_id", None)` into SpanLabel constructor

**Also add `label_type` to `TypedNumericValue`:**
```python
class TypedNumericValue(BaseModel):
    value: float
    bound_type: BoundType = BoundType.EXACT
    original_text: str
    label_type: str | None = None    # ← ADD: preserves what this value IS
    se: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None
    n: int | None = None
```

This is needed because P2 currently can't distinguish an EFFECT_SIZE from a
SAMPLE_SIZE — they're all `TypedNumericValue` with only `.value` set. Adding
`label_type` lets P2 infer `effect_type_reported` instead of hardcoding it.

---

### 1B. Build span-group reassembly in TB

**File:** NEW `crci/extraction/tb_trust_boundary/group_assembler.py`  
**Called from:** `crci/extraction/tb_trust_boundary/runner.py`

**Problem:** `parse_spans()` produces 5 separate `ParsedNumeric` objects for a
single statistical result. No code reassembles them. P2 receives individual values
where `.se`, `.ci_lower`, `.ci_upper`, `.p_value`, `.n` are all `None`.

**Contract:**
- **Input:** `list[SpanLabel]` (with `grouping_id`) + `list[ParsedNumeric]` (CLEAN only)
- **Output:** `list[TypedNumericValue]` with multi-field records

**Implementation (`reassemble_groups()`):**

```python
PRIMARY_TYPES = {
    "EFFECT_SIZE", "OR", "HR", "RR", "IRR", "MEAN_DIFFERENCE",
    "STD_BETA", "UNSTD_BETA", "CORRELATION", "PERCENT_CHANGE",
}
SECONDARY_MAP = {
    "SE": "se",
    "CI_LOWER": "ci_lower",
    "CI_UPPER": "ci_upper",
    "P_VALUE": "p_value",
    "SAMPLE_SIZE": "n",
    "SAMPLE_SIZE_ARM": "n",
}
```

**Logic:**
1. Build `groups: dict[str, list[tuple[SpanLabel, ParsedNumeric]]]` keyed by
   `grouping_id`. Spans with `grouping_id=None` → each becomes its own single-key group.
2. For each group:
   a. Find the "primary" span (label_type ∈ `PRIMARY_TYPES`). If none exists,
      emit each member as a standalone `TypedNumericValue` (preserves current behavior).
   b. Build `TypedNumericValue`:
      - `value = primary.parsed_value`
      - `label_type = primary_span.label_type`  ← NEW field from 1A
      - `original_text = primary.raw_text`
      - For each secondary member, set the corresponding field
   c. **QA counter: group_completion_rate** — track `{grouping_id, has_primary,
      has_se_or_ci, has_n}` for metrics (step 1F).
3. Return assembled list.

**Where to call it — TB runner update:**

Current TB runner flow:
```
SpanLabel[] → parse_spans() → ParsedNumeric[] → check_consistency() → ConsistencyResult
```

New flow:
```
SpanLabel[] → parse_spans() → ParsedNumeric[]
    ↓
    reassemble_groups(span_labels, parsed_clean) → TypedNumericValue[]
    ↓
    check_consistency() → ConsistencyResult
    ↓
context["grouped_evidence"] = assembled TypedNumericValue[]
context["tb_result"] = consistency_result  (kept for backward compat)
```

**P2's input changes:** P2 currently reads `tb_result.validated` (a list of
`ParsedNumeric` objects). After this change, P2 should read `context["grouped_evidence"]`
(a list of `TypedNumericValue` objects with populated fields). This is a cleaner
contract — `TypedNumericValue` already has all the fields P2 needs.

**Critical decision: what happens to ungrouped spans?**
Spans with `grouping_id=None` become single-field `TypedNumericValue` objects.
These will still have `se=None`, `ci_lower=None`, etc. They flow through P2 and
P3 as before — P3 will drop them if SE remains unresolvable. This is correct
behavior: ungrouped spans represent incomplete extraction, and tracking them via
missingness codes (step 1F) tells us whether to fix the agent or acquire more papers.

---

### 1C. Implement ConceptEngine for edge linkage (EX-P1-CE)

**File:** NEW `crci/extraction/p1_extraction/concept_engine.py`  
**Called from:** `crci/extraction/p1_extraction/runner.py` (after agents, before TB)  
**Spec:** Master Spec v2.0 §5.7, SYS_EX §515-520

**Why not in AG05:** The spec explicitly defines ConceptEngine as the component that
maps extracted concepts to ontology IDs (node_id, instrument_id, edge_relation_id).
This is a separate concern from statistical extraction. Putting edge mapping in AG05
creates: (1) token bloat (~3K extra tokens per call), (2) duplicated ontology logic,
(3) harder debugging.

**ConceptEngine contract:**
- **Input:** `list[SpanLabel]` from all agents + ontology tables from DB
- **Output:** `list[GroundedSpan]` — SpanLabel + resolved `edge_relation_id`
- **Also writes:** `context["concept_groundings"]` mapping `span_id → edge_relation_id`

**New intermediate type (`GroundedSpan`):**
```python
class GroundedSpan(BaseModel):
    """SpanLabel after ConceptEngine ontology grounding.

    Adds edge_relation_id resolved from edge_ontology_v1 / edge definitions.
    SYS_EX §515-520 (EX-P1-CE).
    """
    span: SpanLabel
    edge_relation_id: str | None = None  # None = UNRESOLVED
    grounding_confidence: float = 0.0
    grounding_mode: str = "unresolved"  # exact_match | alias | fuzzy | unresolved
```

**Resolution modes (matching spec §5.7):**

**Mode 1 — Section Context + Outcome Mapping (deterministic):**
- AG04 (OutcomeAgent) already extracts `instrument_name` + `instrument_id`.
- AG06 (ExposureAgent) extracts `intervention_type`.
- Use these to look up the corresponding edge in `edge_ontology_v1`:
  - If instrument maps to a `target_node_id` and intervention maps to a
    `source_node_id`, find the edge connecting them.
- Example: instrument="FACT-Cog" → node=`N_COGCOMPLAINTS`,
  intervention="cognitive_rehabilitation" → node=`N_COGACTIVITY`,
  edge=`ER_COGACTIVITY_COGCOMPLAINTS`.

**Mode 2 — Group-level context (heuristic):**
- For each `grouping_id` group, examine non-primary spans for contextual clues:
  - `source_section` (e.g., "results:working_memory")
  - Nearby text from `original_text` field for outcome keywords
- Match against `edge_ontology_v1.mechanism_description` using substring matching.

**Mode 3 — LLM-assisted (DEEP mode only):**
- If Mode 1+2 fail, and extraction mode is DEEP, present the span group +
  candidate edges to the LLM for selection.
- Only if CE is insufficient do we use this path.

**Where in the pipeline:**
```
P1 agents → AG09 reconciliation → ConceptEngine → TB
```

ConceptEngine runs AFTER agent span extraction and reconciliation, BEFORE Trust
Boundary. This way TB receives spans that already have edge linkage context, and
the `TypedNumericValue` objects produced by `reassemble_groups()` can carry the
`edge_relation_id` from `GroundedSpan`.

**Carry edge_relation_id through TB:**
The `reassemble_groups()` function (1B) receives `GroundedSpan[]` instead of plain
`SpanLabel[]`. When building `TypedNumericValue`, it sets a new field:
```python
class TypedNumericValue(BaseModel):
    ...
    edge_relation_id: str | None = None  # from ConceptEngine grounding
```

This is on `TypedNumericValue` (which is an internal pipeline state), NOT on `SpanLabel`
(which is a spec-defined extraction artifact). The separation is clean:
- `SpanLabel` = what the agent extracted (spec-aligned, no cross-boundary fields)
- `TypedNumericValue` = what the pipeline assembled (internal, can carry enrichments)

---

### 1D. Fix P2 hardcoded defaults

**File:** `crci/extraction/p2_harmonization/runner.py`

**Depends on:** 1A (label_type on TypedNumericValue), 1C (edge_relation_id on
TypedNumericValue)

#### 1D-i. Replace hardcoded `effect_type_reported`

**Lines ~117, ~140:** `effect_type_reported="group_diff"` hardcoded.

**Fix:** Infer from `TypedNumericValue.label_type` (added in 1A):
```python
_LABEL_TO_EFFECT_TYPE = {
    "EFFECT_SIZE": "group_diff",
    "MEAN_DIFFERENCE": "group_diff",
    "OR": "odds_ratio",
    "HR": "hazard_ratio",
    "RR": "risk_ratio",
    "IRR": "incidence_rate_ratio",
    "STD_BETA": "std_beta",
    "UNSTD_BETA": "unstd_beta",
    "CORRELATION": "correlation",
    "PERCENT_CHANGE": "percent_change",
}

def _infer_effect_type(label_type: str | None) -> str:
    if label_type is None:
        return "group_diff"  # fallback with logged default
    return _LABEL_TO_EFFECT_TYPE.get(label_type, "group_diff")
```

Apply at each callsite:
```python
effect_type = _infer_effect_type(getattr(claim, "label_type", None))
routed = route_conversion(validated=claim, effect_type_reported=effect_type)
```

#### 1D-ii. Replace hardcoded `dag_orientation`

**Lines ~155-157:** `dag_orientation=Orientation.HIGHER_WORSE` hardcoded.

**Fix:** Look up from DB table `edge_ontology_v1` (NOT the CSV) using the record's
`edge_relation_id` (from ConceptEngine, step 1C):

```python
def _lookup_orientation(
    session: Session, edge_relation_id: str | None
) -> tuple[Orientation, float]:
    """Query edge_ontology_v1 for expected_sign to determine orientation."""
    if not edge_relation_id or edge_relation_id == "UNASSIGNED":
        logger.info("P2-S4: no edge linkage for record, using default HIGHER_WORSE")
        return Orientation.HIGHER_WORSE, 0.5  # low confidence default

    row = session.execute(
        text("SELECT expected_sign FROM edge_ontology_v1 WHERE edge_relation_id = :eid"),
        {"eid": edge_relation_id},
    ).first()
    if row is None:
        logger.info("P2-S4: edge %s not in ontology, using default", edge_relation_id)
        return Orientation.HIGHER_WORSE, 0.5

    sign = row[0]
    if sign == "negative":
        return Orientation.HIGHER_WORSE, 0.9
    elif sign == "positive":
        return Orientation.HIGHER_BETTER, 0.9
    else:  # "variable"
        return Orientation.HIGHER_WORSE, 0.5
```

**Fallback behavior:** When `edge_relation_id` is None or UNASSIGNED (ConceptEngine
couldn't ground the span), fall back to current defaults but at **low confidence** (0.5)
and log the specific record. This makes the gap visible without blocking the pipeline.

---

### 1E. Fix P3 gate-per-record pattern

**File:** `crci/extraction/p3_heterogeneity/runner.py` lines ~99-101

**Current code:**
```python
if se_raw is None:
    logger.debug("P3-ASM: skipping record with no SE")
    continue
```

**Problem:** This silently drops records. Per CLAUDE.md enforcement rules, gates must
raise, not log.

**Correct pattern — raise per record, catch at loop boundary:**
```python
from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.enums import MissingnessCode

calibrated_records = []
p3_gate_failures = []

for layered in layered_records:
    rec = layered.record
    se_raw = getattr(rec, "se", None) or getattr(rec, "harmonized_se", None)

    try:
        if se_raw is None:
            se_source = getattr(rec, "se_source", "UNKNOWN")
            raise GateViolation(
                "P3-G-SE",
                f"Record {getattr(rec, 'ler_id', '?')} has no SE "
                f"(se_source={se_source})",
                context={
                    "ler_id": getattr(rec, "ler_id", ""),
                    "has_ci": getattr(rec, "ci_lower", None) is not None,
                    "has_p": getattr(rec, "p_value", None) is not None,
                    "has_n": getattr(rec, "n", None) is not None,
                    "missingness_code": MissingnessCode.PARSE_FAILURE.value,
                },
            )

        # ... rest of SE_eff computation ...
        calibrated_records.append(rec)

    except GateViolation as gv:
        logger.info("P3-ASM: %s", gv)
        p3_gate_failures.append({
            "ler_id": gv.context.get("ler_id", ""),
            "gate_id": gv.gate_id,
            "reason": str(gv),
            "missingness_code": gv.context.get("missingness_code",
                                                MissingnessCode.PARSE_FAILURE.value),
        })
        continue

# Persist gate failures for missingness tracking
context["p3_gate_failures"] = p3_gate_failures
context["p3_survival_rate"] = (
    len(calibrated_records) / len(layered_records)
    if layered_records else 0.0
)
logger.info(
    "P3-ASM: %d/%d records survived (%.0f%% survival rate)",
    len(calibrated_records), len(layered_records),
    context["p3_survival_rate"] * 100,
)
```

This gives us: spec-compliant gate semantics (raise on failure), batch robustness
(catch and continue), visibility (logged + tracked in context), and missingness
provenance (codes tell us whether to fix agent or acquire more papers).

**Note on `_resolve_se()` in `scale_harmonizer.py`:** The 3-tier SE cascade
(SE_DIRECT → SE_FROM_CI → SE_FROM_P) is correct. Once 1B populates
`TypedNumericValue.ci_lower/ci_upper/p_value/n` from grouped spans, this cascade
will start producing SE values. No code change needed in `_resolve_se()` itself.

---

### 1F. Wire AG09 + add QA metrics

#### 1F-i. Wire AG09 reconciliation checks

**File:** `crci/extraction/p1_extraction/runner.py`

AG09 (`ReconciliationAgent`) has 7 implemented span-level consistency checks:
1. Duplicate detection (overlapping offsets + same label_type)
2. CI bracketing (CI_LOWER ≤ point estimate ≤ CI_UPPER)
3. p/CI consistency (p<0.05 ↔ CI excludes null)
4. N consistency (total N ≥ sum of group Ns)
5. Effect direction sign consistency
6. Missing groupings (effect spans without CI or p-value)
7. Orphan spans (isolated spans with no neighbors)

These are never called. The runner calls a different `reconcile_annotations()`
module that does annotation-level (not span-level) reconciliation.

**Fix:** Call AG09 after the agent loop, before ConceptEngine:
```python
# After agent loop, before ConceptEngine
from crci.extraction.p1_extraction.agents.ag09_reconciliation import ReconciliationAgent

ag09 = ReconciliationAgent()
ag09_result = ag09.reconcile(all_span_labels, paper_id=paper_id)

for w in ag09_result.warnings:
    logger.warning("AG09: %s", w)

rejected_ids = {r.span_id for r in ag09_result.rejected}
all_span_labels = [s for s in all_span_labels if s.span_id not in rejected_ids]

logger.info("AG09: %d spans rejected, %d warnings", len(rejected_ids), len(ag09_result.warnings))
```

**Pipeline order becomes:**
```
P1 agents (AG01-AG08, AG10-AG11)
    → AG09 span-level reconciliation (consistency checks)
    → reconcile_annotations() (annotation-level reconciliation)
    → ConceptEngine (edge linkage)
    → TB (numeric parsing + grouping)
```

#### 1F-ii. Add extraction QA metrics

Track these counters at each stage for the monitoring dashboard (Workstream 3)
and immediate debugging. Store in `context["qa_metrics"]`:

| Metric | Where computed | What it tells you |
|--------|---------------|-------------------|
| `group_completion_rate` | 1B `reassemble_groups()` | % of groups with primary + (CI or SE or p+n). Low = LLM not grouping well |
| `orphan_span_rate` | 1B `reassemble_groups()` | % of spans with `grouping_id=None`. High = LLM ignoring grouping instruction |
| `unmapped_edge_rate` | 1C ConceptEngine | % of groups without `edge_relation_id`. High = poor ontology coverage |
| `p3_survival_rate` | 1E P3 loop | records_out / records_in. 0% = still broken |
| `missingness_breakdown` | 1E P3 gate failures | Dict of `{MissingnessCode: count}`. Tells you *why* records die |

**Emit metrics to context:**
```python
context["qa_metrics"] = {
    "group_completion_rate": n_complete / n_groups if n_groups else 0,
    "orphan_span_rate": n_orphan / n_total_spans if n_total_spans else 0,
    "unmapped_edge_rate": n_unmapped / n_groups if n_groups else 0,
    "p3_survival_rate": context.get("p3_survival_rate", 0),
    "missingness_breakdown": missingness_counts,
}
```

These don't require a dashboard to be useful — they appear in the pipeline log at
INFO level and are available in `context` for programmatic checks.

---

### Workstream 1 Summary & Dependency Graph

```
1A (add grouping_id to SpanLabel + label_type to TypedNumericValue)
  ↓
1F-i (wire AG09 reconciliation) ← parallel with 1B, no dependency
  ↓
1B (reassemble groups in TB) ← depends on 1A
  ↓
1C (ConceptEngine for edge linkage) ← parallel with 1B, but must complete before 1D
  ↓
1D (fix P2 hardcoded defaults) ← depends on 1A + 1C
  ↓
1E (P3 gate-per-record) ← depends on 1B (fields populated)
  ↓
1F-ii (QA metrics) ← depends on 1B + 1C + 1E
  ↓
GATE: Run Cherrier 2013. ≥1 record survives P3 with SE_eff.
```

**Estimated effort:** 5-7 hours. 1A+1B+1C are the critical path (~3-4 hrs).

---

## Workstream 2: Batch Infrastructure (BLOCKED until Workstream 1 gate passes)

**Goal:** Process 100+ papers with tracking, cost control, and error recovery.

### 2A. Build the queue→extraction bridge

**New file:** `scripts/run_batch_extraction.py`

**What it does:**
1. Queries `acquisition_queue_v1 WHERE status='retrieved'` for retrieved papers
2. Also scans `data/manual_uploads/pdfs/*.pdf` for unprocessed manual uploads
3. Checks `extraction_runs` to skip already-processed PDFs (by `pdf_hash`)
4. For each unprocessed paper:
   - Reads companion `.meta.json` if available
   - Calls `run_extraction_pipeline(pdf_path, skip_idempotency=False)`
   - On success: updates `extraction_runs.status = 'completed'` (already happens)
   - On failure: logs error, continues to next paper
5. Enforces cost cap before each paper
6. Prints summary

**Key decisions:**
- **Sequential processing** — SQLite single-writer lock. One paper at a time.
- **No new queue statuses** — `acquisition_queue_v1.status` stays in its defined
  lifecycle (`queued → dispatched → retrieved / failed`). Extraction completion is
  tracked by `extraction_runs.status` (`completed / partial / failed`). The bridge
  between them is DOI: `acquisition_queue_v1.candidate_doi` ↔ `study_registry_v1.doi`.
- **No retry logic in v1** — failed papers are skipped. `--retry-failed` is a v2 flag.

### 2B. P0 reads `.meta.json`

**File:** `crci/extraction/p0_triage/runner.py`

After PDF ingestion, check for companion `.meta.json`:
```python
meta_json_path = pdf_path.with_suffix(".meta.json")
# Also check alternate naming patterns
```
Merge DOI, PMID, title into metadata dict. When DOI is available, derive
deterministic `paper_id = f"STUDY_{sha256(doi)[:12]}"` for idempotency.

### 2C. Persist canonical text to disk

Write `data/canonical_texts/{paper_id}.txt` during P0. Set
`study_registry_v1.canonical_text_path`. ~50KB per paper, negligible storage.

### 2D. Cost cap enforcement

Check `CostTracker.get_summary()` against `config.RETRIEVAL_MAX_LLM_COST_USD_PER_DAY`
before each LLM call in `LLMClient.call()`. Raise `CostCapExceeded` when exceeded.
Session-level cap initially; daily enforcement via CSV log summation later.

---

## Workstream 3: Monitoring Dashboard (BLOCKED until Workstream 1 gate passes)

**Goal:** Real-time visibility into queue, extraction, evidence, cost.

### 3A. Technology: FastAPI + Jinja2

- Python ecosystem, no JS build chain
- SSE for live log streaming
- The 10 existing `crci/presentation/` modules produce dataclass view models —
  trivial to serialize to HTML

### 3B. Pages

| Page | Data Source | Key Content |
|------|------------|-------------|
| `/queue` | `acquisition_queue_v1` + `extraction_runs` | Paper status, APS score, extraction outcome |
| `/extraction/{run_id}` | `extraction_runs` + `extraction_audit_v1` | Per-stage breakdown, agent results, QA metrics |
| `/evidence` | `edge_evidence_v1` + `edge_ontology_v1` | DAG coverage heatmap, per-edge k/β/SE |
| `/cost` | `logs/llm_cost_log.csv` | Spend per day/paper/agent, budget remaining |

**Note:** `extraction_audit_v1` table exists in schema but pipeline doesn't write
to it yet. Need to add `session.add(ExtractionAudit(...))` at end of each runner.

### 3C. Live log streaming

SSE endpoint `/logs/stream` tailing `logs/extraction.log`. Requires adding
`FileHandler` to the logger in `scripts/run_extraction.py`.

---

## Issues Tracked but Not Blocking

| ID | Issue | Severity | When to fix |
|----|-------|----------|-------------|
| ISS-10 | P4B bias corrections computed but not applied | MEDIUM | After evidence flows through P4 |
| ISS-14 | P7 compilers untested with real data | MEDIUM | After Workstream 1 gate passes |
| ISS-16 | P2 fail-open on plausibility exception | LOW | Acceptable for now |
| ISS-20 | SR papers enter SHALLOW mode | LOW | By design — SRs extract metadata only |
| AG02 | DesignAgent fails on SRs (`arms=None`) | LOW | Make `arms` optional in `DesignResponse` |
| OCR | No OCR for scanned PDFs | HIGH | Out of scope, add `ocrmypdf` later |
| PostgreSQL | SQLite limits concurrency | MEDIUM | Sequential works for 100 papers (~5 hrs) |

---

## Validation Gates (strict — do not proceed past without confirmation)

**Gate 1 (Workstream 1 exit):**
Run Cherrier 2013 (RCT). Requirements:
- ≥1 evidence record survives P3 with `SE_eff != None`
- `group_completion_rate > 0` (at least some groups assembled)
- `edge_relation_id != "UNASSIGNED"` for at least 1 record
- P6 reaches deploy decision (not necessarily DEPLOY, but processes edges)

**Gate 2 (Workstream 2 exit):**
Batch run on 3 PDFs (Cherrier 2013 + Campbell 2017 + Cifu 2018).
- All 3 complete (status=completed or partial)
- Cost tracking shows nonzero spend
- `.meta.json` DOIs appear in `study_registry_v1.doi`

**Gate 3 (Workstream 3 exit):**
Dashboard shows queue + extraction + evidence pages for all 3 papers.

---

## Files Modified Per Workstream

### Workstream 1
| File | Change |
|------|--------|
| `crci/shared/models/intermediate_states.py` | Add `grouping_id` to `SpanLabel`, `label_type` + `edge_relation_id` to `TypedNumericValue`, add `GroundedSpan` type |
| `crci/llm/response_schemas.py` | Ensure `grouping_id` on span response item |
| `crci/extraction/p1_extraction/agents/ag05_stats_label.py` | Propagate `grouping_id` |
| `crci/extraction/p1_extraction/concept_engine.py` | **NEW** — ontology grounding (Modes 1-2, optional Mode 3) |
| `crci/extraction/p1_extraction/runner.py` | Wire AG09 + ConceptEngine into pipeline |
| `crci/extraction/tb_trust_boundary/group_assembler.py` | **NEW** — `reassemble_groups()` |
| `crci/extraction/tb_trust_boundary/runner.py` | Call `reassemble_groups()`, emit grouped evidence |
| `crci/extraction/p2_harmonization/runner.py` | Replace hardcoded defaults with lookups |
| `crci/extraction/p3_heterogeneity/runner.py` | Gate-per-record pattern, missingness codes, QA metrics |

### Workstream 2
| File | Change |
|------|--------|
| `scripts/run_batch_extraction.py` | **NEW** — batch runner |
| `crci/extraction/p0_triage/runner.py` | Read `.meta.json`, DOI-derived paper_id, persist canonical text |
| `crci/llm/client.py` | Cost cap check before LLM calls |

### Workstream 3
| File | Change |
|------|--------|
| `crci/dashboard/` | **NEW** — FastAPI app, routes, templates |
| `scripts/run_extraction.py` | Add file logger handler |
| 10 runner files | Add `extraction_audit_v1` writes |
