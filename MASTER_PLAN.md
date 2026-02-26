# CRCI Master Plan — Thin Slice Implementation

**Created:** 2026-02-26  
**Purpose:** Single source of truth for what to build, in what order, with explicit dependencies  
**Goal:** Produce stable posterior domain draws → enable F4 clinical risk computation

---

## System State Summary

### What Exists (Code Complete)
| Component | Lines | Tests | Status |
|-----------|-------|-------|--------|
| Algorithm Chain A (Graph) | 2,285 | 73 | ✅ WORKING |
| Algorithm Chain B (Evidence) | 2,893 | 124 | ✅ WORKING |
| Algorithm Chain C (Posterior) | 2,641 | 89 | ✅ WORKING |
| Algorithm Chain D (Simulation) | 3,750 | 187 | ✅ WORKING |
| Algorithm Chain E (Temporal) | 1,453 | 94 | ✅ WORKING |
| Algorithm Chain F (Analytics) | 1,205 | 67 | ✅ WORKING |
| Runtime (RT-G, RT-H, RT-I) | 2,035 | 87 | ✅ WORKING |
| Presentation (7 modules) | 1,993 | 61 | ✅ WORKING |
| Extraction Pipeline (P0-P7 runners) | 9,847 | 158 | ⚠️ STRUCTURE OK, DATA FLOW BROKEN |
| Retrieval (adapters, hop discovery) | 4,201 | 10 | ⚠️ WORKS BUT DISCONNECTED |
| LLM Client + Agents | 5,437 | 0 | ⚠️ UNTESTED WITH REAL DATA |
| **Total** | **75,624** | **940** | |

### What's Broken (The Data Flow Gap)

```
EXTRACTION                          ALGORITHM
═══════════                         ═════════
P0-P7 runs without crash    BUT    No EvidenceRecord reaches Chain B
                            ↓
AG05 extracts stats tokens  BUT    Tokens not grouped into records
                            ↓
ConceptEngine exists        BUT    Edge linkage incomplete
                            ↓
TB parses numbers          BUT    Each span is isolated (no SE with β)
                            ↓
P3 requires SE             →      Drops 100% of records
                            ↓
P4-P7 get empty inputs     →      0 edges deployed
                            ↓
Chain B has no evidence    →      FrozenModelState has no edge params
                            ↓
Chain C-D run on priors    →      Posteriors are uninformative
                            ↓
F4 risk layer              →      Would produce invalid confident numbers
```

### SR/MA Pipeline Status

| Step | Code Exists | Wired | Works | Gap |
|------|-------------|-------|-------|-----|
| P0 classifies as `systematic_review` | ✅ | ✅ | ✅ | — |
| P1 calls `included_study_extractor.py` | ✅ | ✅ | ⚠️ | Writes to DB but untested |
| P1 writes `included_study_ids_json` | ✅ | ✅ | ⚠️ | Session flush may not persist |
| Pipeline calls `hop_discoverer` | ✅ | ✅ | ⚠️ | Only if `included_study_ids` populated |
| Hop discoverer filters SR papers | ✅ | ✅ | ✅ | Fixed (`systematic_review` added to allowlist) |
| Constituent studies queued | ✅ | ✅ | ✅ | Tested with Cifu 2018 |
| Acquisition retrieves constituents | ✅ | ✅ | ✅ | OA papers only (paywalled = manual) |

**Verdict:** SR/MA → hop discovery pipeline is **architecturally complete**. Needs end-to-end validation.

---

## Critical Path to Working Posteriors

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 1: Fix Data Flow (P0 → P3 survival)                                  │
│  ───────────────────────────────────────────                                │
│  Gate: ≥1 evidence record survives P3 with SE_eff ≠ None                    │
│  Target: Cherrier 2013 (RCT with clear effect sizes)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 2: Edge Deployment (P4 → P7)                                         │
│  ──────────────────────────────────                                         │
│  Gate: ≥1 compiled edge in edge_evidence_v1 with β ≠ 0, SE_eff ≠ 0          │
│  Depends: Slice 1 gate must pass                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 3: Evidence → Algorithm Bridge                                       │
│  ────────────────────────────────────                                       │
│  Gate: Chain B produces FrozenModelState with ≥1 edge having μ_e ≠ 0        │
│  Depends: Slice 2 gate must pass                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 4: Full Vertical Integration                                         │
│  ─────────────────────────────────                                          │
│  Gate: Chain D produces RankingResult with interventions ranked by real data│
│  Depends: Slice 3 gate must pass                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 5: SR/MA Validation                                                  │
│  ─────────────────────────────                                              │
│  Gate: SR paper (Cifu 2018) triggers hop discovery → constituents extracted │
│  Parallel with Slices 1-4 (independent data path)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SLICE 6: F4 Clinical Risk Layer                                            │
│  ───────────────────────────────                                            │
│  Gate: Risk probability computed from real posteriors, not priors           │
│  Depends: Slice 4 gate must pass (stable posteriors)                        │
│  BLOCKED until slices 1-4 complete                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Slice 1: Fix Data Flow (Evidence Survival)

**Goal:** At least 1 evidence record survives P3 with `SE_eff` populated.  
**Target Paper:** Cherrier 2013 (RCT with explicit Cohen's d in tables)  
**Estimated Effort:** 6-8 hours

### 1.1 Add `grouping_id` to SpanLabel

**File:** `crci/shared/models/intermediate_states.py`  
**Why:** AG05 prompt asks for `grouping_id` but SpanLabel model lacks the field.

```python
class SpanLabel(BaseModel):
    # ... existing fields ...
    grouping_id: str | None = None  # Links β + CI + p + N
```

**Also update:**
- `crci/llm/response_schemas.py` — add `grouping_id` to span response schema
- `crci/extraction/p1_extraction/agents/ag05_stats_label.py` — propagate field

**Verification:** 
- [ ] `SpanLabel` model has `grouping_id`
- [ ] AG05 produces spans with `grouping_id` set

---

### 1.2 Add `label_type` to TypedNumericValue

**File:** `crci/shared/models/intermediate_states.py`  
**Why:** P2 currently can't distinguish EFFECT_SIZE from SAMPLE_SIZE.

```python
class TypedNumericValue(BaseModel):
    # ... existing fields ...
    label_type: str | None = None    # What this value IS (EFFECT_SIZE, P_VALUE, etc.)
    edge_relation_id: str | None = None  # From ConceptEngine
```

**Verification:**
- [ ] `TypedNumericValue` has `label_type`
- [ ] `TypedNumericValue` has `edge_relation_id`

---

### 1.3 Build Group Assembler in TB

**File:** NEW `crci/extraction/tb_trust_boundary/group_assembler.py`  
**Why:** 5 separate ParsedNumeric objects for one stat result → need reassembly.

**Input:** `list[SpanLabel]` (with grouping_id) + `list[ParsedNumeric]`  
**Output:** `list[TypedNumericValue]` with multi-field records (β + SE + CI + p + n)

**Logic:**
1. Group spans by `grouping_id`
2. Find primary span (EFFECT_SIZE, OR, HR, etc.)
3. Attach secondary spans (SE, CI_LOWER, CI_UPPER, P_VALUE, SAMPLE_SIZE)
4. Build `TypedNumericValue` with all fields populated

**QA Metric:** `group_completion_rate` = groups with primary + (SE or CI) / total groups

**Verification:**
- [ ] `reassemble_groups()` function exists
- [ ] Called from TB runner
- [ ] Produces multi-field records

---

### 1.4 Wire ConceptEngine for Edge Linkage

**File:** `crci/extraction/p1_extraction/concept_engine.py` (EXISTS — verify it works)  
**Why:** Spans need `edge_relation_id` for P2 orientation lookup.

**Check current implementation:**
- [ ] ConceptEngine called from P1 runner (line ~233)
- [ ] Produces `grounded_spans` in context
- [ ] `edge_relation_id` propagates to TypedNumericValue

**If broken, fix:**
- Mode 1: Instrument → node + intervention → node → find connecting edge
- Mode 2: Section context + keyword matching
- Fallback: `edge_relation_id = None` with low confidence

---

### 1.5 Fix P2 Hardcoded Defaults

**File:** `crci/extraction/p2_harmonization/runner.py`  
**Why:** Lines 131, 162-164 hardcode effect_type and orientation.

**Fix 1:** `effect_type_reported` from `label_type`:
```python
_LABEL_TO_EFFECT_TYPE = {
    "EFFECT_SIZE": "group_diff",
    "OR": "odds_ratio",
    "HR": "hazard_ratio",
    # ...
}
```

**Fix 2:** `dag_orientation` from DB lookup:
```python
def _lookup_orientation(session, edge_relation_id):
    # Query edge_ontology_v1 for expected_sign
    # Return Orientation.HIGHER_WORSE or HIGHER_BETTER
```

**Verification:**
- [ ] No hardcoded `"group_diff"` in runner
- [ ] Orientation lookup queries DB

---

### 1.6 Fix P3 Gate Semantics

**File:** `crci/extraction/p3_heterogeneity/runner.py`  
**Why:** Silent `continue` on missing SE violates "gates must raise" rule.

**Pattern:**
```python
try:
    if se_raw is None:
        raise GateViolation("P3-G-SE", f"Record has no SE", context={...})
    # ... SE_eff computation ...
except GateViolation as gv:
    p3_gate_failures.append(gv.context)
    continue
```

**QA Metric:** `p3_survival_rate` = calibrated_out / layered_in

**Verification:**
- [ ] Gate raises per-record
- [ ] Caught at loop boundary
- [ ] `p3_survival_rate` in context

---

### 1.7 Slice 1 Validation

**Test Command:**
```bash
python scripts/run_extraction.py data/manual_uploads/pdfs/cherrier2013.pdf --verbose
```

**Expected:**
- [ ] Pipeline completes without crash
- [ ] Log shows `P3-ASM: N/M records survived (X% survival rate)` with N > 0
- [ ] `qa_metrics.group_completion_rate > 0`
- [ ] At least 1 record has `SE_eff != None`

---

## Slice 2: Edge Deployment

**Goal:** At least 1 compiled edge in `edge_evidence_v1`  
**Depends:** Slice 1 gate passed  
**Estimated Effort:** 2-3 hours

### 2.1 Verify P4 Aggregation Flow

**Check:**
- [ ] `context["calibrated_records"]` has records (from Slice 1)
- [ ] `group_by_edge_id()` produces non-empty groups
- [ ] `meta_analyzer.run_ivw()` produces pooled estimates
- [ ] `edge_writer.write_all_edges()` writes to DB

**If broken:**
- Records may lack `edge_relation_id` → fix ConceptEngine (1.4)
- Records may lack study metadata → check P2 harmonization

---

### 2.2 Verify P4 Writes compiled_edges to Context

**File:** `crci/extraction/p4_aggregation/runner.py` line 235  
**Current:** `context["compiled_edges"] = compiled_edges` ✅ (already fixed)

**Verification:**
- [ ] Context has `compiled_edges` list
- [ ] List contains `CompiledEdge` objects

---

### 2.3 Verify P5-P6 Flow

**Check:**
- [ ] P5 reads `compiled_edges` from context
- [ ] P5 `coverage_analyzer` runs on edges
- [ ] P6 `validation_runner` evaluates G1 rule
- [ ] P6 makes deploy decision (DEPLOY, WARN, or BLOCK)

**For SR papers:** Verify BUG-003 fix (SR-aware P6 exemption)

---

### 2.4 Verify P7 Compilers Run

**Check:** P7 only runs if P6 passes. After fixing Slice 1:
- [ ] `temporal_compiler.py` produces temporal parameters
- [ ] `psychometric_compiler.py` produces instrument reliability
- [ ] `dose_response_compiler.py` produces dose curves

---

### 2.5 Slice 2 Validation

**Query:**
```sql
SELECT edge_relation_id, beta_pooled, se_pooled, k_studies 
FROM edge_evidence_v1 
WHERE extraction_run_id = (SELECT MAX(extraction_run_id) FROM extraction_runs);
```

**Expected:**
- [ ] At least 1 row
- [ ] `beta_pooled != 0`
- [ ] `se_pooled != 0`
- [ ] `k_studies >= 1`

---

## Slice 3: Evidence → Algorithm Bridge

**Goal:** Chain B produces FrozenModelState with evidence-informed edges  
**Depends:** Slice 2 gate passed  
**Estimated Effort:** 3-4 hours

### 3.1 Build Evidence Loader for Chain B

**File:** NEW `crci/algorithm/chain_b_evidence/evidence_loader.py`  
**Why:** Chain B's `EvidenceRecord` dataclass needs population from DB.

**Function:**
```python
def load_evidence_from_db(session: Session) -> list[EvidenceRecord]:
    """Query edge_evidence_v1 and transform to EvidenceRecord list."""
    rows = session.execute(select(EdgeEvidence).where(...)).all()
    return [
        EvidenceRecord(
            study_id=row.study_id,
            edge_id=row.edge_relation_id,
            beta=row.beta_pooled,
            se=row.se_pooled,
            # ... map all fields ...
        )
        for row in rows
    ]
```

**Verification:**
- [ ] Function exists
- [ ] Returns non-empty list when DB has evidence

---

### 3.2 Wire Loader into Chain B Entry Point

**File:** `crci/algorithm/chain_b_evidence/evidence_compiler.py` or new orchestrator  
**Why:** Currently Chain B tests use mock data; need real DB integration.

**Entry point pattern:**
```python
def run_chain_b(session: Session, graph: GraphObject) -> FrozenModelState:
    evidence_records = load_evidence_from_db(session)
    b1_b6 = run_b1_through_b6(graph, evidence_records)
    frozen = assemble_frozen_state(graph, b1_b6)
    return frozen
```

---

### 3.3 Slice 3 Validation

**Test:**
```python
from crci.algorithm.chain_b_evidence.evidence_loader import load_evidence_from_db
from crci.algorithm.chain_b_evidence.frozen_state import run_chain_b

with get_session() as session:
    evidence = load_evidence_from_db(session)
    print(f"Loaded {len(evidence)} evidence records")
    
    graph = build_graph_from_db(session)  # Chain A
    frozen = run_chain_b(session, graph)
    
    # Check at least one edge has evidence-informed μ_e
    for edge_id, mu_e in frozen.B_hat.items():
        if mu_e != 0:
            print(f"Edge {edge_id} has μ_e = {mu_e}")
```

**Expected:**
- [ ] `len(evidence) >= 1`
- [ ] At least one edge has `μ_e != 0` (not prior-only)

---

## Slice 4: Full Vertical Integration

**Goal:** End-to-end: Paper → Extraction → Chain B → Chain C → Chain D → Ranking  
**Depends:** Slice 3 gate passed  
**Estimated Effort:** 2-3 hours

### 4.1 Build Integration Test

**File:** `crci/tests/test_end_to_end/test_vertical_slice.py`

```python
def test_paper_to_ranking():
    """Extract Cherrier 2013 → produce ranking based on real evidence."""
    # 1. Run extraction
    run = run_extraction_pipeline("data/manual_uploads/pdfs/cherrier2013.pdf")
    assert run.status == "completed"
    
    # 2. Load evidence into Chain B
    frozen = run_chain_b(session, graph)
    assert len([e for e in frozen.B_hat.values() if e != 0]) > 0
    
    # 3. Run Chain C (patient state)
    patient_state = run_chain_c(frozen, patient_observations={})
    
    # 4. Run Chain D (simulation + ranking)
    ranking = run_chain_d(frozen, patient_state, interventions)
    assert ranking.n_interventions_ranked > 0
    
    # 5. Verify ranking uses evidence (not just priors)
    top = ranking.ranked_interventions[0]
    # The ranking should reflect cognitive rehabilitation benefit
```

---

### 4.2 Verify Posteriors Are Informative

**Check:** Chain C posterior should differ from prior when evidence exists.

```python
# Prior (no evidence)
prior_mean = frozen.context_specs[context_key].node_prior_means[node_id]

# Posterior (with evidence)
posterior = patient_state.node_posteriors[node_id]

# Should differ if evidence exists for this node's edges
assert posterior.mean != prior_mean or posterior.sd < prior_sd
```

---

### 4.3 Slice 4 Validation

**Command:**
```bash
python -m pytest crci/tests/test_end_to_end/test_vertical_slice.py -v
```

**Expected:**
- [ ] Test passes
- [ ] Ranking reflects evidence (not random/prior-only)
- [ ] Posteriors narrower than priors for evidenced nodes

---

## Slice 5: SR/MA Pipeline Validation (Parallel Track)

**Goal:** Confirm SR papers trigger hop discovery and constituent extraction  
**Independent of:** Slices 1-4 (can run in parallel)  
**Estimated Effort:** 2-3 hours

### 5.1 End-to-End SR Test

**Paper:** Cifu 2018 (systematic review of mindfulness interventions)

```bash
python scripts/run_extraction.py data/manual_uploads/pdfs/cifu2018.pdf --verbose
```

**Expected Log:**
```
P0: Classified as systematic_review
P1: Built MA extraction plan
P1-ISL: Extracted 4 included study IDs
Post-pipeline hop discovery: queued 4 constituent studies
```

---

### 5.2 Verify `included_study_ids_json` Persisted

```sql
SELECT study_id, study_subtype, included_study_ids_json, included_k
FROM study_registry_v1
WHERE study_subtype = 'systematic_review';
```

**Expected:**
- [ ] Row exists for Cifu 2018
- [ ] `included_study_ids_json` is valid JSON array
- [ ] `included_k` = number of included studies

---

### 5.3 Verify Constituents Queued

```sql
SELECT candidate_doi, status, hop_source_study_id, hop_depth
FROM acquisition_queue_v1
WHERE hop_source_study_id IS NOT NULL;
```

**Expected:**
- [ ] Rows exist for constituent papers
- [ ] `hop_depth = 1`
- [ ] `status = 'queued'`

---

### 5.4 Run Acquisition for Constituents

```bash
python scripts/run_acquisition.py --max-papers 5 --verbose
```

**Expected:**
- [ ] Constituents are searched/retrieved (OA) or flagged (paywalled)
- [ ] Retrieved constituents can be extracted (back to Slice 1)

---

## Slice 6: F4 Clinical Risk Layer (BLOCKED)

**Prerequisite:** Slice 4 gate passed (stable posteriors from real evidence)

### Why Blocked

The F4 risk layer (clinical impairment probability) requires:
1. **Correct random variable:** Sample θ_t (current state), not θ_0 (baseline)
2. **Calibrated posteriors:** Evidence-informed, not prior-only
3. **Verified node orientation:** Lower = worse for all cognitive nodes
4. **Domain coverage:** Most cognitive domains have at least partial evidence

Without these, F4 would produce confident-looking invalid numbers.

### Pre-F4 Checklist

Before implementing F4, verify:
- [ ] Slice 4 test passes
- [ ] At least 3 edges have k ≥ 2 (poolable)
- [ ] Cognitive domain nodes have evidence (direct or pathway-propagated)
- [ ] `scoring_direction` in INSTRUMENT_REGISTRY is correct for all instruments
- [ ] Posteriors visibly narrower than priors for evidenced nodes

### F4 Implementation Notes (for when unblocked)

1. **Rename `theta0_draws` to `theta_t_draws`** — sample current state, not baseline
2. **Use Beta posterior for interval** — not normal MC error
3. **Implement domain-level vs test-level criteria** — document approximation
4. **Rename "Shapley-style" to "trigger-share attribution"** — not actually Shapley
5. **Add missingness policy** — latent-completion vs observed-only
6. **Add calibration placeholder** — "model-derived, not clinically calibrated"

---

## Dependency Graph Summary

```
                    ┌──────────────────────────┐
                    │  SLICE 5: SR/MA Pipeline │
                    │  (parallel, independent) │
                    └──────────────────────────┘
                              
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  SLICE 1    │────▶│  SLICE 2    │────▶│  SLICE 3    │────▶│  SLICE 4    │
│  Data Flow  │     │  Edge Deploy│     │  Alg Bridge │     │  Vertical   │
│  P0→P3      │     │  P4→P7      │     │  Chain B    │     │  Integration│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                    │
                                                                    ▼
                                                           ┌─────────────┐
                                                           │  SLICE 6    │
                                                           │  F4 Risk    │
                                                           │  (BLOCKED)  │
                                                           └─────────────┘
```

---

## Files Modified by Slice

### Slice 1 (Data Flow)
| File | Change |
|------|--------|
| `crci/shared/models/intermediate_states.py` | Add `grouping_id` to SpanLabel, `label_type`+`edge_relation_id` to TypedNumericValue |
| `crci/llm/response_schemas.py` | Add `grouping_id` to span schema |
| `crci/extraction/p1_extraction/agents/ag05_stats_label.py` | Propagate `grouping_id` |
| `crci/extraction/tb_trust_boundary/group_assembler.py` | **NEW** — `reassemble_groups()` |
| `crci/extraction/tb_trust_boundary/runner.py` | Wire group assembler |
| `crci/extraction/p2_harmonization/runner.py` | Fix hardcoded defaults |
| `crci/extraction/p3_heterogeneity/runner.py` | Gate-per-record pattern |

### Slice 2 (Edge Deployment)
| File | Change |
|------|--------|
| `crci/extraction/p4_aggregation/runner.py` | Verify `compiled_edges` wiring |
| `crci/extraction/p6_deployment/deploy_gate.py` | Verify SR exemption |

### Slice 3 (Algorithm Bridge)
| File | Change |
|------|--------|
| `crci/algorithm/chain_b_evidence/evidence_loader.py` | **NEW** — DB→EvidenceRecord |
| `crci/algorithm/chain_b_evidence/evidence_compiler.py` | Wire loader |

### Slice 4 (Vertical Integration)
| File | Change |
|------|--------|
| `crci/tests/test_end_to_end/test_vertical_slice.py` | **NEW** — integration test |

### Slice 5 (SR/MA)
| File | Change |
|------|--------|
| `crci/extraction/p1_extraction/included_study_extractor.py` | Verify LLM extraction works |
| `crci/extraction/p1_extraction/runner.py` | Verify `included_study_ids_json` persisted |

### Slice 6 (F4 Risk)
| File | Change |
|------|--------|
| `crci/algorithm/chain_f_analytics/clinical_risk.py` | **NEW** — CRCI probability |
| `crci/presentation/risk_dashboard.py` | **NEW** — risk tier visualization |

---

## Execution Protocol

### Before Each Slice

1. **Read this plan** — understand the slice goal and gate
2. **Check dependencies** — verify previous slice gate passed
3. **Read upstream code** — understand what produces your inputs
4. **Read downstream code** — understand what consumes your outputs

### During Implementation

1. **Test-first when possible** — write failing test, then fix
2. **Log at INFO level** — visibility into pipeline state
3. **Use config constants** — no hardcoded numbers
4. **Gates raise, not log** — `GateViolation` on failure

### After Each Slice

1. **Run validation test** — must pass before proceeding
2. **Update EXTRACTION_LOG.md** — if paper data changed
3. **Commit with descriptive message**
4. **Update this plan** — mark slice complete

---

## Current Blockers

| Blocker | Severity | Resolution |
|---------|----------|------------|
| No LLM API key configured | HIGH | Set `ANTHROPIC_API_KEY` env var |
| SQLite single-writer | MEDIUM | Sequential processing OK for development |
| Paywalled constituent papers | MEDIUM | Manual acquisition required |
| Missing OCR for scanned PDFs | MEDIUM | Out of scope; use text PDFs |

---

## Success Criteria (End State)

When all slices complete:

1. **Extraction → Algorithm bridge works** — evidence flows from papers to posteriors
2. **SR/MA papers trigger hop discovery** — constituent studies auto-queued
3. **Posteriors are evidence-informed** — not prior-only
4. **Chain D rankings reflect evidence** — interventions ranked by real data
5. **F4 risk layer can be implemented** — stable posteriors exist to sample

**Final validation:** Run the full pipeline on 3 papers (Cherrier, Campbell, Cifu)
and verify end-to-end data flow.

---

*Last updated: 2026-02-26*
