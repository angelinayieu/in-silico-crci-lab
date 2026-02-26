# CRCI Master Plan — Thin Slice Implementation

**Created:** 2026-02-26  
**Last reviewed:** 2026-02-26 (external feedback incorporated — see §Feedback Audit)  
**Purpose:** Single source of truth for what to build, in what order, with explicit dependencies  
**Goal:** Produce stable posterior domain draws → enable F4 clinical risk computation

---

## Feedback Audit (2026-02-26)

External review of this plan identified 5 must-fix issues and 4 tightening recommendations.  
Disposition of each, verified against the actual codebase:

| # | Feedback | Verdict | Action Taken |
|---|----------|---------|---------------|
| 1 | Label-type naming inconsistent (`OR` vs `ODDS_RATIO`) | **Plan-only bug.** Code already maps both forms in `_LABEL_TO_EFFECT_TYPE` (P2) and `PRIMARY_TYPES` (group_assembler). AG05 has normalization map `OR` → `ODDS_RATIO`. | Fixed plan examples to use enum-exact strings only. |
| 2 | Offsets undefined across `focused_text` vs `table_text` | **Valid but non-blocking.** Offsets are provenance metadata, not part of the survival path. | Tracked as hardening task (post-Slice 4). |
| 3 | Grouping cannot rely on LLM alone — need fallback | **Partially addressed.** `group_assembler.py` handles orphans as standalone, derives Cohen's d from arm pairs. But no proximity-based fallback for co-located spans. | Added proximity fallback to Slice 1.3. |
| 4 | SE required is too strict — need CI→SE derivation | **CI→SE exists in TB** (`numeric_parser.py` NP-11) but field propagation to P3 may break. P3 itself has no CI→SE fallback. | Added P3-level CI→SE derivation to Slice 1.6. |
| 5 | No explicit effect normalization contract | **Valid.** TB log-transforms ratios, but no documented canonical scale contract. P4 pools without confirming like-with-like. | Added §1.5b: Effect Scale Contract. |
| A | Boundary contract tests | **Valid.** | Added §Boundary Contract Tests. |
| B | Slice-level hard stop when survival = 0 | **`p3_survival_rate` tracked but no halt.** Pipeline continues with empty records. | Added hard stop to Slice 1.6. |
| C | Remove time estimates | **Agree.** | Removed. |
| D | Reproducibility metadata | **Valid for LLM runs.** | Added §Reproducibility Metadata. |

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

**Proximity Fallback (new — from feedback #3):**

When `grouping_id` is null (LLM omitted it), the assembler must attempt proximity-based grouping before falling back to standalone:

```python
def _proximity_fallback_groups(
    orphan_spans: list[tuple[str, SpanLabel, ParsedNumeric]],
    char_window: int = 200,
) -> dict[str, list[str]]:
    """Group orphan spans by character proximity.
    
    Heuristic: spans within `char_window` characters sharing the same
    source_block (table row, sentence) are likely from the same result.
    Anchored on primary types.
    """
```

Rules:
1. Primary: group by `grouping_id` when present  
2. Fallback: group orphans by proximity window + anchor tokens in same sentence/row  
3. Set `confidence = 0.5` on fallback groups (vs 0.8+ for LLM-grouped)  
4. Never drop orphans — emit as standalone at minimum  

**Verification:**
- [ ] `reassemble_groups()` function exists (YES — 484 lines)
- [ ] Called from TB runner (YES — line ~99)
- [ ] Produces multi-field records (YES)
- [ ] Proximity fallback rescues co-located orphans (NEW — implement)

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
**Current state:** `_LABEL_TO_EFFECT_TYPE` already maps both short and enum-exact forms (`"OR"` AND `"ODDS_RATIO"`) with `_infer_effect_type()` doing the lookup. ✅

**Remaining fixes:**

**Fix 1:** `dag_orientation` from DB lookup (currently hardcoded):
```python
def _lookup_orientation(session, edge_relation_id):
    # Query edge_ontology_v1 for expected_sign
    # Return Orientation.HIGHER_WORSE or HIGHER_BETTER
```

**Fix 2:** `canonical_scale` assignment (see §1.5b):
```python
def _assign_canonical_scale(label_type: str) -> str:
    """Assign canonical pooling scale based on effect type."""
    if label_type in {"ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO", "INCIDENCE_RATE_RATIO"}:
        return "LOG_RATIO"  # Already log-transformed by TB NP-04
    elif label_type in {"EFFECT_SIZE", "MEAN_DIFFERENCE"}:
        return "SMD"
    elif label_type == "CORRELATION":
        return "FISHER_Z"
    elif label_type in {"STD_BETA", "UNSTD_BETA"}:
        return "RAW"
    return "RAW"
```

**Verification:**
- [ ] `_infer_effect_type` uses enum-exact strings ✅ (already implemented)
- [ ] Orientation lookup queries DB (implement)
- [ ] `canonical_scale` assigned to every harmonized record (implement)

---

### 1.5b Effect Scale Contract (new — from feedback #5)

**Why:** Chain B expects `beta_pooled` in a consistent scale. P4 must only pool like-with-like.  
Without an explicit normalization step, pooling Cohen's d with log-OR produces nonsense.

**Contract:**

| Reported Type | Canonical Scale | Transformation | Where |
|--------------|----------------|----------------|-------|
| Cohen's d, Hedges' g, SMD | SMD | None (already standardized) | TB |
| Mean difference | SMD | Divide by pooled SD (requires SD + N) | P2 |
| OR, aOR | log-OR | `log(OR)`, SE on log scale | TB (already implemented NP-04) |
| HR, aHR | log-HR | `log(HR)`, SE on log scale | TB (already implemented NP-04) |
| RR, aRR | log-RR | `log(RR)`, SE on log scale | TB (already implemented NP-04) |
| Correlation (r) | Fisher-z | `0.5 * log((1+r)/(1-r))` | P2 (implement) |
| Unstd β | No pooling | Keep separate; do not mix with SMD | P4 grouping |

**Implementation:**
- P2 must tag each record with `canonical_scale` (enum: `SMD`, `LOG_OR`, `LOG_HR`, `LOG_RR`, `FISHER_Z`, `RAW`)
- P4 must only pool records with matching `canonical_scale`
- TB already handles log-transformation for ratio measures; P2 must handle Fisher-z for correlations

**Verification:**
- [ ] `canonical_scale` field exists on harmonized record
- [ ] P4 groups by `(edge_relation_id, canonical_scale)`, not just edge_id
- [ ] Correlations Fisher-z transformed before pooling

---

### 1.6 Fix P3 Gate Semantics

**File:** `crci/extraction/p3_heterogeneity/runner.py`  
**Why:** P3 gates per-record (correct), but has no CI→SE fallback and no slice-level hard stop.

**Current state (already implemented):**
- Gate raises `GateViolation("P3-G-SE", ...)` per record when SE is null ✅
- Caught at loop boundary, appended to `p3_gate_failures` ✅
- `p3_survival_rate` computed and stored in context ✅

**Fix 1 — CI→SE derivation before gate (from feedback #4):**

P3 currently checks `se_raw = getattr(rec, "se", None)` but does NOT attempt to derive SE from CI when SE is missing. The invariant should be:

> P3 requires either `SE_raw` OR (`CI_LOWER` + `CI_UPPER` + `CI_LEVEL`) sufficient to derive SE.

```python
# BEFORE the gate check:
if se_raw is None:
    ci_lo = getattr(rec, "ci_lower", None) or getattr(rec, "harmonized_ci_lower", None)
    ci_hi = getattr(rec, "ci_upper", None) or getattr(rec, "harmonized_ci_upper", None)
    if ci_lo is not None and ci_hi is not None:
        # NP-11: SE = (upper - lower) / (2 × z)
        se_raw = (ci_hi - ci_lo) / (2 * config.TB_CI_TO_SE_Z_MULTIPLIER)
        logger.info(
            "P3: Derived SE=%.4f from CI [%.4f, %.4f] for %s",
            se_raw, ci_lo, ci_hi, getattr(rec, 'ler_id', '?'),
        )
```

Note: TB's `numeric_parser.py` already does CI→SE derivation (NP-11), but the derived SE may not propagate through P2 to the harmonized record. This P3 fallback is defense-in-depth.

**Fix 2 — Slice-level hard stop (from feedback B):**

```python
# After the per-record loop:
if context["p3_survival_rate"] == 0.0 and len(layered_records) > 0:
    raise GateViolation(
        "P3-SLICE-HALT",
        f"Zero records survived P3 ({len(p3_gate_failures)} failures). "
        f"Pipeline cannot produce evidence. Halting.",
        context={"n_in": len(layered_records), "n_failed": len(p3_gate_failures)},
    )
```

This prevents P4-P7 from running on empty input and producing false "completed" status.

**QA Metric:** `p3_survival_rate` = calibrated_out / layered_in

**Verification:**
- [ ] Gate raises per-record ✅ (already implemented)
- [ ] CI→SE fallback attempted before gate (NEW — implement)
- [ ] Slice-level halt when survival = 0 (NEW — implement)
- [ ] `p3_survival_rate` in context ✅ (already implemented)

---

### 1.7 Slice 1 Validation

**Test Command:**
```bash
python scripts/run_extraction.py data/manual_uploads/pdfs/cherrier2013.pdf --verbose
```

**Expected (full gate — all must pass before starting Slice 2):**
- [ ] Pipeline completes without crash
- [ ] Log shows `P3-ASM: N/M records survived (X% survival rate)` with N > 0
- [ ] `qa_metrics.group_completion_rate > 0`
- [ ] At least 1 record has `SE_eff != None`
- [ ] At least 1 record has `effect_type_reported` correct (not defaulted)
- [ ] At least 1 record has `edge_relation_id` present or explicitly unknown
- [ ] At least 1 record has `canonical_scale` assigned
- [ ] No `P3-SLICE-HALT` exception raised

---

## Slice 2: Edge Deployment

**Goal:** At least 1 compiled edge in `edge_evidence_v1`  
**Depends:** Slice 1 gate passed (tightened — see below)

### 2.1 Verify P4 Aggregation Flow

**Check:**
- [ ] `context["calibrated_records"]` has records (from Slice 1)
- [ ] `group_by_edge_id()` groups by `(edge_relation_id, canonical_scale)` — not just edge_id (from feedback #5)
- [ ] `meta_analyzer.run_ivw()` produces pooled estimates
- [ ] `edge_writer.write_all_edges()` writes to DB

**If broken:**
- Records may lack `edge_relation_id` → fix ConceptEngine (1.4)
- Records may lack `canonical_scale` → fix P2 (1.5b)
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
└──────┬──────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                                                            │
       ▼                                                            ▼
┌──────────────┐                                           ┌─────────────┐
│  SLICE R1    │                                           │  SLICE 6    │
│  Subtype Enum│                                           │  F4 Risk    │
│  + Mode Sel  │                                           │  (BLOCKED)  │
└──────┬───────┘                                           └─────────────┘
       │
  ┌────┴──────┐
  ▼           ▼
┌───────┐  ┌───────┐
│  R2   │  │  R3   │  (parallel after R1)
│ Gates │  │ MA    │
│       │  │ Life  │
└───┬───┘  └───┬───┘
    └─────┬────┘
          ▼
    ┌───────────┐
    │  R4: Agg  │  (after Slice 2 + R1)
    │ Amendments│
    └─────┬─────┘
          ▼
    ┌───────────┐
    │  R5: LLM  │  (hardening — any time)
    │ Guardrails│
    └───────────┘
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

## Slice 1→2 Transition Gate (Tightened)

Do NOT start Slice 2 until Slice 1 produces at least one fully assembled record where **all** of these hold:

- [ ] `effect_type_reported` is correct (not defaulted to `group_diff`)
- [ ] `SE_eff` is present — either from raw SE or derived from CI
- [ ] `edge_relation_id` is present — or explicitly `None` with `confidence < 0.5` (not silently defaulted)
- [ ] `canonical_scale` is assigned
- [ ] P3 produces `SE_eff` and `p3_survival_rate > 0`

Everything downstream is noise until this is true.

---

## Boundary Contract Tests

Add one test per interface boundary so failures localize instantly:

| Boundary | Test | File |
|----------|------|------|
| AG05 → TB | Every span has valid offsets; `label_type ∈ SPAN_LABEL_TYPES`; no duplicate `span_id` | `tests/test_extraction/test_ag05_tb_contract.py` |
| TB → TypedNumericValue | Every TNV has primary effect measure + at least one precision measure (SE or CI-derived SE) | `tests/test_extraction/test_tb_tnv_contract.py` |
| P2 → P3 | Every record has `canonical_scale` + orientation metadata or explicit "unknown" (never implicit defaults) | `tests/test_extraction/test_p2_p3_contract.py` |
| P3 output | `p3_survival_rate > 0` for target paper; no silent empty-list pass-through | `tests/test_extraction/test_p3_survival_contract.py` |

These tests use synthetic data (not LLM), so they run fast and deterministically.

---

## Reproducibility Metadata

Every LLM-based extraction run must capture:

| Field | Source | Stored In |
|-------|--------|-----------|
| `llm_model_name` | e.g. `claude-sonnet-4-20250514` | `extraction_runs.metadata_json` |
| `prompt_hash` | SHA-256 of prompt template text | `extraction_runs.metadata_json` |
| `code_version` | `git rev-parse HEAD` | `extraction_runs.metadata_json` |
| `config_fingerprint` | Hash of `shared/config.py` constants used | `extraction_runs.metadata_json` |
| `seed` | Random seed for any stochastic step | `extraction_runs.metadata_json` |

This turns debugging from "it changed" into "these specific knobs changed."

**Implementation:** Add to `pipeline.py` at run creation time. Non-blocking for Slice 1 (no LLM call in the manual extraction path), but required before any LLM-driven extraction.

---

## Routing Slices: Paper-Type Routing Gap Remediation

**Origin:** Audit of the Paper-Type Routing & Directed Acquisition Protocol against
the current codebase. The audit identified 5 gap categories. These slices close them.

**Relationship to Slices 1–6:** These routing slices (R1–R5) are **parallel** with the
critical-path data flow slices. R1 should be done after Slice 1 (it changes classification
behavior, which affects downstream routing). R2–R3 can proceed alongside Slice 2–4.
R4 requires Slice 2 (edge evidence must exist for aggregation amendments). R5 is
hardening and can be done at any time.

```
┌───────────────────────────────────────┐
│  SLICE R1: Subtype Enum + Mode Select │ ← after Slice 1 data flow works
│  Gate: PaperSubtype covers all spec   │
│        subtypes; mode_selection routes │
│        correctly for all 30+ subtypes │
└──────────────┬────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌───────────┐   ┌────────────────┐
│ SLICE R2  │   │  SLICE R3      │  ← parallel, after R1
│ Enforce-  │   │  MA Product    │
│ ment Gates│   │  Lifecycle     │
└─────┬─────┘   └───────┬────────┘
      │                 │
      └────────┬────────┘
               ▼
      ┌────────────────┐
      │  SLICE R4      │  ← after Slice 2 + R1
      │  Aggregation   │
      │  Amendments    │
      └────────┬───────┘
               ▼
      ┌────────────────┐
      │  SLICE R5      │  ← hardening, any time
      │  LLM Guardrail │
      │  Enforcement   │
      └────────────────┘
```

### Vocabulary Alignment

The Paper-Type Routing Protocol uses the Master Spec §4.1 taxonomy. Our codebase
uses `PaperSubtype` in `enums.py` with a different taxonomy (intervention-oriented
rather than design-oriented). The hop_discoverer already references spec subtypes
as raw strings (`"pairwise_ma"`, `"nma"`, etc.) but they don't exist in the enum.

**Principle:** Extend the existing `PaperSubtype` enum. Keep all current values for
backward compatibility. Add new values using the same naming convention (UPPER_CASE
member name, lowercase_with_underscores string value). The table below maps external
reference names to our codebase names:

| Spec / External Name | Codebase Enum Member | String Value | Action |
|---|---|---|---|
| `pairwise_ma` | `PaperSubtype.PAIRWISE_MA` | `"pairwise_ma"` | **ADD** |
| `nma` | `PaperSubtype.NMA` | `"nma"` | **ADD** |
| `ipdma` | `PaperSubtype.IPDMA` | `"ipdma"` | **ADD** |
| `dose_response_ma` | `PaperSubtype.DOSE_RESPONSE_MA` | `"dose_response_ma"` | **ADD** |
| `umbrella_review` | `PaperSubtype.UMBRELLA_REVIEW` | `"umbrella_review"` | **ADD** |
| `mega_analysis` | `PaperSubtype.MEGA_ANALYSIS` | `"mega_analysis"` | **ADD** |
| `scoping_review` | `PaperSubtype.SCOPING_REVIEW` | `"scoping_review"` | **ADD** |
| `factorial_rct` | `PaperSubtype.FACTORIAL_RCT` | `"factorial_rct"` | **ADD** |
| `pilot_rct` | `PaperSubtype.PILOT_RCT` | `"pilot_rct"` | **ADD** |
| `crossover_rct` | `PaperSubtype.CROSSOVER_RCT` | `"crossover_rct"` | **ADD** |
| `standard_rct` | `PaperSubtype.STANDARD_RCT` | `"standard_rct"` | **ADD** |
| `prospective_cohort` | `PaperSubtype.PROSPECTIVE_COHORT` | `"prospective_cohort"` | **ADD** |
| `retrospective_cohort` | `PaperSubtype.RETROSPECTIVE_COHORT` | `"retrospective_cohort"` | **ADD** |
| `computational_model` | `PaperSubtype.COMPUTATIONAL_MODEL` | `"computational_model"` | **ADD** |
| `methods_paper` | `PaperSubtype.METHODS_PAPER` | `"methods_paper"` | **ADD** |
| `practice_guideline` | `PaperSubtype.GUIDELINE` | `"guideline"` | **EXISTS** (keep as-is) |
| `narrative_review` | `PaperSubtype.REVIEW_NARRATIVE` | `"review_narrative"` | **EXISTS** (keep as-is) |
| `ema_eld` | `PaperSubtype.INTENSIVE_LONGITUDINAL` | `"intensive_longitudinal"` | **EXISTS** (keep as-is) |
| `animal_model` | `PaperSubtype.MECHANISTIC_ANIMAL` | `"mechanistic_animal"` | **EXISTS** (keep as-is) |
| `in_vitro` | `PaperSubtype.MECHANISTIC_IN_VITRO` | `"mechanistic_in_vitro"` | **ADD** (distinct from `EvidenceBasisExtended.IN_VITRO`) |
| `case_report` | `PaperSubtype.CASE_REPORT` | `"case_report"` | **EXISTS** |
| `qualitative` | `PaperSubtype.QUALITATIVE` | `"qualitative"` | **EXISTS** |

**Key decisions:**
- Existing subtypes (`RCT_EXERCISE`, `RCT_COGNITIVE`, etc.) are NOT renamed. They
  remain valid and the classifier can still output them. Mode selection will map
  coarse RCT subtypes the same as `STANDARD_RCT` unless the new fine-grained subtype
  is assigned.
- `ExtractionMode.MINIMAL` is added (4th level) to support umbrella_review,
  case_report, qualitative, and in-vitro paper types.
- The identifier mapping between old and new is documented in hop_discoverer's
  `_MA_SR_SUBTYPES` set — which already references the new names as strings. After
  R1, it can reference enum members directly.

---

### Slice R1: Extend PaperSubtype + Mode Selection

**Goal:** Every paper type in the spec taxonomy has a `PaperSubtype` enum member
and a deterministic routing rule in `mode_selection.py`.

**Gate:** All 30+ subtypes classified correctly → extraction mode assigned → mode
matches spec table (DEEP/STANDARD/SHALLOW/MINIMAL).

#### R1.1 Add MINIMAL to ExtractionMode

**File:** `crci/shared/models/enums.py`

```python
class ExtractionMode(StrEnum):
    MINIMAL = "MINIMAL"
    SHALLOW = "SHALLOW"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
```

**Why:** The spec defines 4 extraction depths, but the enum only has 3. MINIMAL
(AG01 only + reference scan) is needed for umbrella reviews, case reports,
qualitative studies, in-vitro, and narrative reviews.

**Verification:**
- [ ] `ExtractionMode.MINIMAL` member exists
- [ ] No existing code breaks (search all uses of `ExtractionMode`)

#### R1.2 Add Fine-Grained Subtypes to PaperSubtype

**File:** `crci/shared/models/enums.py`

Add 15 new members to `PaperSubtype` (see Vocabulary Alignment table above).
Place them after the existing 27, grouped by design family with comments:

```python
    # ─── Fine-grained MA subtypes (Master Spec §4.1) ────────
    PAIRWISE_MA = "pairwise_ma"
    NMA = "nma"
    IPDMA = "ipdma"
    DOSE_RESPONSE_MA = "dose_response_ma"
    UMBRELLA_REVIEW = "umbrella_review"
    MEGA_ANALYSIS = "mega_analysis"
    SCOPING_REVIEW = "scoping_review"
    # ─── Fine-grained RCT subtypes ──────────────────────────
    STANDARD_RCT = "standard_rct"
    FACTORIAL_RCT = "factorial_rct"
    PILOT_RCT = "pilot_rct"
    CROSSOVER_RCT = "crossover_rct"
    # ─── Fine-grained observational subtypes ─────────────────
    PROSPECTIVE_COHORT = "prospective_cohort"
    RETROSPECTIVE_COHORT = "retrospective_cohort"
    # ─── Fine-grained mechanistic/other ──────────────────────
    MECHANISTIC_IN_VITRO = "mechanistic_in_vitro"
    COMPUTATIONAL_MODEL = "computational_model"
    METHODS_PAPER = "methods_paper"
```

**Verification:**
- [ ] 42+ members total in PaperSubtype (27 existing + 15 new)
- [ ] `_VALID_SUBTYPES` set in `paper_type_classifier.py` auto-updates (uses enum iteration)
- [ ] `hop_discoverer._MA_SR_SUBTYPES` can now reference enum values instead of strings

#### R1.3 Update Mode Selection Routing Table

**File:** `crci/extraction/p0_triage/mode_selection.py`

Extend `_SUBTYPE_TO_MODE` dict with new subtypes. The routing must match the
Master Spec §4.5 table exactly:

```python
_SUBTYPE_TO_MODE: dict[PaperSubtype, ExtractionMode] = {
    # ─── DEEP: RCTs ─────────────────────────────────────────
    PaperSubtype.RCT_EXERCISE: ExtractionMode.DEEP,
    PaperSubtype.RCT_COGNITIVE: ExtractionMode.DEEP,
    PaperSubtype.RCT_PHARMACOLOGICAL: ExtractionMode.DEEP,
    PaperSubtype.RCT_MULTIMODAL: ExtractionMode.DEEP,
    PaperSubtype.STANDARD_RCT: ExtractionMode.DEEP,     # NEW
    PaperSubtype.FACTORIAL_RCT: ExtractionMode.DEEP,    # NEW — + synergy agents

    # ─── DEEP: Meta-analyses ────────────────────────────────
    PaperSubtype.META_ANALYSIS: ExtractionMode.DEEP,
    PaperSubtype.PAIRWISE_MA: ExtractionMode.DEEP,      # NEW
    PaperSubtype.NMA: ExtractionMode.DEEP,               # NEW
    PaperSubtype.IPDMA: ExtractionMode.DEEP,             # NEW
    PaperSubtype.DOSE_RESPONSE_MA: ExtractionMode.DEEP,  # NEW
    PaperSubtype.MEGA_ANALYSIS: ExtractionMode.DEEP,     # NEW

    # ─── DEEP: Other intensive designs ───────────────────────
    PaperSubtype.DOSE_RESPONSE_STUDY: ExtractionMode.DEEP,
    PaperSubtype.LONGITUDINAL_FOLLOWUP: ExtractionMode.DEEP,
    PaperSubtype.INTENSIVE_LONGITUDINAL: ExtractionMode.DEEP,  # PROMOTED (ema_eld)

    # ─── STANDARD: Observational with cognitive outcomes ─────
    PaperSubtype.PILOT_RCT: ExtractionMode.STANDARD,    # NEW — quality capped
    PaperSubtype.CROSSOVER_RCT: ExtractionMode.STANDARD, # NEW — + period check
    PaperSubtype.SYSTEMATIC_REVIEW: ExtractionMode.STANDARD,
    PaperSubtype.LONGITUDINAL_COHORT: ExtractionMode.STANDARD,
    PaperSubtype.PROSPECTIVE_COHORT: ExtractionMode.STANDARD,   # NEW
    PaperSubtype.RETROSPECTIVE_COHORT: ExtractionMode.STANDARD, # NEW
    PaperSubtype.CROSS_SECTIONAL: ExtractionMode.STANDARD,
    PaperSubtype.MECHANISTIC_HUMAN: ExtractionMode.STANDARD,
    PaperSubtype.IMAGING_STRUCTURAL: ExtractionMode.STANDARD,
    PaperSubtype.IMAGING_FUNCTIONAL: ExtractionMode.STANDARD,
    PaperSubtype.DOSE_RESPONSE: ExtractionMode.STANDARD,
    PaperSubtype.PSYCHOMETRIC_VALIDATION: ExtractionMode.STANDARD,
    PaperSubtype.NORMATIVE_COHORT: ExtractionMode.STANDARD,
    PaperSubtype.MECHANISTIC_ANIMAL: ExtractionMode.STANDARD,

    # ─── SHALLOW: Designs with limited extractable evidence ──
    PaperSubtype.SCOPING_REVIEW: ExtractionMode.SHALLOW,         # NEW
    PaperSubtype.BIOMARKER_DISCOVERY: ExtractionMode.SHALLOW,
    PaperSubtype.SAFETY_REPORT: ExtractionMode.SHALLOW,
    PaperSubtype.COMPUTATIONAL_MODEL: ExtractionMode.SHALLOW,    # NEW
    PaperSubtype.METHODS_PAPER: ExtractionMode.SHALLOW,          # NEW
    PaperSubtype.GUIDELINE: ExtractionMode.SHALLOW,

    # ─── MINIMAL: No evidence rows, reference/ontology only ──
    PaperSubtype.UMBRELLA_REVIEW: ExtractionMode.MINIMAL,        # NEW — BLOCKS numeric
    PaperSubtype.REVIEW_NARRATIVE: ExtractionMode.MINIMAL,       # DEMOTED (was SHALLOW)
    PaperSubtype.CASE_REPORT: ExtractionMode.MINIMAL,            # DEMOTED
    PaperSubtype.QUALITATIVE: ExtractionMode.MINIMAL,            # DEMOTED
    PaperSubtype.MECHANISTIC_IN_VITRO: ExtractionMode.MINIMAL,   # NEW — sign-direction only
    PaperSubtype.EDITORIAL: ExtractionMode.SHALLOW,
    PaperSubtype.PROTOCOL: ExtractionMode.SHALLOW,

    PaperSubtype.OTHER: ExtractionMode.STANDARD,
}
```

**Changes from current code:**
- `INTENSIVE_LONGITUDINAL` promoted STANDARD → DEEP (Master Spec: ema_eld = DEEP)
- `REVIEW_NARRATIVE` demoted SHALLOW → MINIMAL (narrative reviews don't produce evidence)
- `CASE_REPORT` demoted SHALLOW → MINIMAL (no evidence rows allowed)
- `QUALITATIVE` demoted SHALLOW → MINIMAL (no evidence rows allowed)
- `MECHANISTIC_ANIMAL` promoted SHALLOW → STANDARD (Master Spec: animal_model = STANDARD)

**Verification:**
- [ ] Every `PaperSubtype` member has an entry in `_SUBTYPE_TO_MODE`
- [ ] Routing matches Master Spec §4.5 table
- [ ] Unit test covers all enum members

#### R1.4 Update MA Plan Builder

**File:** `crci/extraction/p1_extraction/ma_multi_product.py`

Currently `build_ma_extraction_plan()` checks if subtype is in
`{"meta_analysis", "systematic_review"}`. Update to include new MA subtypes:

```python
ma_subtypes = {
    PaperSubtype.META_ANALYSIS.value,
    PaperSubtype.SYSTEMATIC_REVIEW.value,
    PaperSubtype.PAIRWISE_MA.value,        # NEW
    PaperSubtype.NMA.value,                 # NEW
    PaperSubtype.IPDMA.value,              # NEW
    PaperSubtype.DOSE_RESPONSE_MA.value,   # NEW
    PaperSubtype.MEGA_ANALYSIS.value,      # NEW
    PaperSubtype.UMBRELLA_REVIEW.value,    # NEW (limited products)
}
```

For `UMBRELLA_REVIEW`: build plan with ONLY `INCLUDED_STUDY_LIST` product.
Block `POOLED_ESTIMATE`, `FOREST_PLOT_ENTRIES`, `SUBGROUP_MODERATOR`.

For `NMA` and `DOSE_RESPONSE_MA`: skip keyword detection (type already known).

**Verification:**
- [ ] Each MA subtype produces the correct product set
- [ ] Umbrella review plan has 0 evidence-producing products
- [ ] NMA plan includes `NMA_PAIRWISE_MATRIX` without relying on keyword heuristic

#### R1.5 Update hop_discoverer Allowlist

**File:** `crci/retrieval/hop_discoverer.py`

Replace string literals with enum references:

```python
_MA_SR_SUBTYPES: set[str] = {
    PaperSubtype.META_ANALYSIS.value,
    PaperSubtype.SYSTEMATIC_REVIEW.value,
    PaperSubtype.PAIRWISE_MA.value,
    PaperSubtype.NMA.value,
    PaperSubtype.IPDMA.value,
    PaperSubtype.DOSE_RESPONSE_MA.value,
    PaperSubtype.MEGA_ANALYSIS.value,
    # Umbrella reviews: yes — their included MAs should be acquired
    PaperSubtype.UMBRELLA_REVIEW.value,
}
```

**Verification:**
- [ ] No raw string literals remain for MA subtypes
- [ ] Hop discovery triggered for all MA-family subtypes

#### R1.6 Update Paper-Type Classifier Prompt

**File:** `crci/llm/prompts/ptc_prompt.txt` (or inline fallback in
`paper_type_classifier.py`)

The LLM prompt must list all 42+ valid subtypes so the classifier can output
fine-grained types. Group by family for the LLM's benefit.

**Verification:**
- [ ] Prompt lists every `PaperSubtype` value
- [ ] Inline fallback also updated
- [ ] `_validate_subtype()` in classifier already handles case/underscore normalization ✅

#### R1 Validation

```bash
python -c "
from crci.shared.models.enums import PaperSubtype, ExtractionMode
from crci.extraction.p0_triage.mode_selection import _SUBTYPE_TO_MODE
missing = [p for p in PaperSubtype if p not in _SUBTYPE_TO_MODE]
assert not missing, f'PaperSubtypes without routing: {missing}'
print(f'All {len(PaperSubtype)} subtypes routed.')
# Verify spec alignment:
assert _SUBTYPE_TO_MODE[PaperSubtype.UMBRELLA_REVIEW] == ExtractionMode.MINIMAL
assert _SUBTYPE_TO_MODE[PaperSubtype.PAIRWISE_MA] == ExtractionMode.DEEP
assert _SUBTYPE_TO_MODE[PaperSubtype.PILOT_RCT] == ExtractionMode.STANDARD
assert _SUBTYPE_TO_MODE[PaperSubtype.CASE_REPORT] == ExtractionMode.MINIMAL
print('Spec alignment verified.')
"
```

---

### Slice R2: Per-Subtype Enforcement Gates

**Goal:** Paper-type-specific quality caps, identification demotions, and evidence
row blocking are enforced in code — not just documented.

**Gate:** For each rule below, a unit test proves the enforcement triggers.

**Depends:** R1 (subtypes must exist before gates can reference them).

#### R2.1 Umbrella Review Numeric Block

**Where:** `crci/extraction/tb_trust_boundary/runner.py` + MA plan builder (R1.4)

**Rule:** When `paper_subtype` is `UMBRELLA_REVIEW`, ALL
`edge_evidence_v1` row creation is blocked. Only `study_registry_v1` (B1) and
`ontology_links_v1` (B5) writes are allowed.

**Implementation:**
1. MA plan builder (R1.4) already restricts products for umbrella reviews.
2. Add defense-in-depth in `evidence_writer.py`: if paper subtype is
   `UMBRELLA_REVIEW`, raise `GateViolation("R2-G1", "Umbrella review numeric
   extraction blocked")` on any attempt to write an evidence row.

**Verification:**
- [ ] Test: attempt to write evidence row for umbrella review → `GateViolation`
- [ ] Test: umbrella review extraction produces 0 evidence rows, ≥1 registry row

#### R2.2 MINIMAL-Mode Evidence Row Block (Generalized)

**Where:** `crci/extraction/evidence_writer.py`

**Rule:** Papers with `ExtractionMode.MINIMAL` must never produce
`edge_evidence_v1` rows. This covers: `UMBRELLA_REVIEW`, `REVIEW_NARRATIVE`,
`CASE_REPORT`, `QUALITATIVE`, `MECHANISTIC_IN_VITRO`.

**Implementation:**

```python
# In evidence_writer.py — before ANY row insert:
_EVIDENCE_BLOCKED_SUBTYPES: set[str] = {
    PaperSubtype.UMBRELLA_REVIEW.value,
    PaperSubtype.REVIEW_NARRATIVE.value,
    PaperSubtype.CASE_REPORT.value,
    PaperSubtype.QUALITATIVE.value,
    PaperSubtype.MECHANISTIC_IN_VITRO.value,
}

def _check_evidence_row_allowed(paper_subtype: str, mode: str):
    if paper_subtype in _EVIDENCE_BLOCKED_SUBTYPES:
        raise GateViolation(
            "R2-G2",
            f"Evidence rows blocked for paper subtype '{paper_subtype}'. "
            f"Only registry and ontology writes permitted.",
        )
```

**Note on `SYSTEMATIC_REVIEW`:** The spec says systematic reviews without
quantitative pooling should not produce evidence rows. However, some systematic
reviews DO report vote counts or direction-of-effect summaries. Our existing
`SYSTEMATIC_REVIEW` subtype is kept at STANDARD mode (not MINIMAL) because the
pipeline already handles vote counts via `harmonization_status = blocked`. We do
NOT add it to the blocked set — the trust boundary and P3 gates already filter
appropriately.

**Verification:**
- [ ] Test: MINIMAL-mode paper produces 0 evidence rows
- [ ] Test: SYSTEMATIC_REVIEW **can** produce vote-count rows (not blocked)

#### R2.3 Pilot RCT Quality Cap

**Where:** `crci/extraction/p2_harmonization/runner.py` (or a new
`quality_caps.py` module)

**Rule:** When `paper_subtype` is `PILOT_RCT`, `quality_rating` is capped at
`moderate` regardless of design quality score. Rationale: N < 50, typically
underpowered.

**Implementation:**

```python
def _apply_subtype_quality_caps(
    quality_rating: str,
    paper_subtype: str,
) -> str:
    """Cap quality rating based on study design limitations."""
    if paper_subtype == PaperSubtype.PILOT_RCT.value:
        _QUALITY_ORDER = ["weak", "moderate", "strong"]
        if quality_rating == "strong":
            logger.info(
                "R2-CAP: pilot_rct quality capped moderate←strong. "
                "Reason: N < 50, insufficient power."
            )
            return "moderate"
    return quality_rating
```

Called during P2 harmonization after quality is assessed.

**Verification:**
- [ ] Test: pilot RCT with strong quality → capped to moderate
- [ ] Test: pilot RCT with weak quality → stays weak (cap is upper-bound)

#### R2.4 Cross-Sectional Identification Demotion

**Where:** `crci/extraction/p2_harmonization/runner.py`

**Rule:** When `paper_subtype` is `CROSS_SECTIONAL`, `identification_status`
is always `not_identified` regardless of statistical adjustment.

**Implementation:**

```python
def _apply_subtype_identification_rules(
    identification_status: str,
    paper_subtype: str,
) -> str:
    """Enforce design-based identification limits."""
    if paper_subtype == PaperSubtype.CROSS_SECTIONAL.value:
        if identification_status != IdentificationStatus.NOT_IDENTIFIED.value:
            logger.info(
                "R2-ID: cross_sectional identification demoted to not_identified←%s. "
                "Reason: single-timepoint design cannot establish causation.",
                identification_status,
            )
            return IdentificationStatus.NOT_IDENTIFIED.value
    if paper_subtype == PaperSubtype.RETROSPECTIVE_COHORT.value:
        if identification_status == IdentificationStatus.IDENTIFIED.value:
            logger.info(
                "R2-ID: retrospective_cohort identification capped at "
                "partially_identified←identified."
            )
            return IdentificationStatus.PARTIALLY_IDENTIFIED.value
    return identification_status
```

**Verification:**
- [ ] Test: cross-sectional study → always `not_identified`
- [ ] Test: retrospective cohort → capped at `partially_identified`

#### R2.5 NMA Indirect Identification Demotion

**Where:** `crci/extraction/p2_harmonization/runner.py` or `evidence_writer.py`

**Rule:** NMA-derived rows with `meta_source_flag = NMA_MIXED` always have
`identification_status = partially_identified`.

**Implementation:** Applied when setting fields on evidence rows extracted from NMAs.

**Verification:**
- [ ] Test: NMA mixed estimate → `partially_identified`

#### R2 Validation

```bash
python -m pytest tests/test_extraction/test_routing_gates.py -v
```

Tests cover:
- Umbrella numeric block
- MINIMAL-mode evidence block
- Pilot quality cap
- Cross-sectional identification demotion
- Retrospective identification cap
- NMA identification demotion

---

### Slice R3: MA Product Lifecycle & Forest Plot Superseding

**Goal:** Forest plot entries are automatically deactivated when their corresponding
primary study is independently extracted. Subgroup estimate correlation is documented
and warn-logged.

**Gate:** Forest plot row with `meta_source_flag = FOREST_PLOT_ENTRY` gets
`active = 0` when same study's primary extraction arrives.

**Depends:** R1 (MA subtypes needed for product routing).

#### R3.1 Forest Plot Auto-Supersede

**Where:** `crci/extraction/evidence_writer.py` (or a new `supersede_checker.py`)

**When:** A new `edge_evidence_v1` row is inserted with `meta_source_flag = NULL`
(i.e., primary study evidence), check if any existing rows match the same
`study_id` with `meta_source_flag = FOREST_PLOT_ENTRY`:

```python
def _supersede_forest_plot_entries(
    session: Session,
    study_id: str,
    edge_relation_id: str,
):
    """Deactivate forest plot entries when full primary extraction arrives.

    Spec §3.4: Forest plot entries exist only as placeholders.
    When the full paper is extracted, the placeholder is superseded.
    """
    updated = session.execute(
        update(EdgeEvidence)
        .where(
            EdgeEvidence.study_id == study_id,
            EdgeEvidence.edge_relation_id == edge_relation_id,
            EdgeEvidence.meta_source_flag == MetaSourceFlag.FOREST_PLOT_ENTRY.value,
        )
        .values(active=0)
    )
    if updated.rowcount > 0:
        logger.info(
            "R3-SUPERSEDE: deactivated %d forest plot entries for study %s "
            "edge %s — replaced by full primary extraction.",
            updated.rowcount, study_id, edge_relation_id,
        )
```

Called from `evidence_writer.write_evidence_row()` when `meta_source_flag is None`.

**Verification:**
- [ ] Test: insert FOREST_PLOT_ENTRY row → insert primary row → forest plot `active = 0`
- [ ] Test: insert primary row without existing forest plot → no error / no-op

#### R3.2 Subgroup Correlation Warning

**Where:** `crci/extraction/p4_aggregation/evidence_grouper.py`

**When:** Multiple subgroup estimates from the SAME parent MA exist for the
SAME edge. These are correlated and must NOT be IVW-pooled together.

**Implementation:**

```python
def _check_subgroup_correlation(claims: list[HarmonizedClaim]) -> list[str]:
    """Warn if subgroup estimates from same MA are being pooled together.

    Subgroup estimates from the same MA share systematic biases.
    They should inform different scope slices, not be pooled.
    """
    warnings = []
    # Group by parent_meta_study_id
    ma_subgroups: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        if (hasattr(claim, 'meta_source_flag') and
                claim.meta_source_flag == MetaSourceFlag.SUBGROUP_ESTIMATE.value and
                hasattr(claim, 'parent_meta_study_id') and
                claim.parent_meta_study_id):
            ma_subgroups[claim.parent_meta_study_id].append(claim.ler_id)

    for ma_id, ler_ids in ma_subgroups.items():
        if len(ler_ids) > 1:
            warnings.append(
                f"R3-CORR: {len(ler_ids)} subgroup estimates from same MA "
                f"{ma_id} for this edge. These are correlated — do not IVW-pool."
            )
            logger.warning(warnings[-1])
    return warnings
```

Phase 1 action: warn-log only. Phase 2: exclude from IVW pooling.

**Verification:**
- [ ] Test: 2 subgroup estimates from same MA → warning emitted
- [ ] Test: 2 subgroup estimates from DIFFERENT MAs → no warning

#### R3.3 IPD-MA Product Skeleton

**Where:** `crci/extraction/p1_extraction/ma_multi_product.py`

Add `MAProductType.IPD_INTERACTION` for IPD-MA papers. Not fully implemented
(extraction logic deferred), but the product type and routing stub exist:

```python
# Add to MAProductType enum:
IPD_INTERACTION = "ipd_interaction"

# In build_ma_extraction_plan, for IPDMA subtype:
if subtype_str == PaperSubtype.IPDMA.value:
    products.append(MAProduct(
        product_type=MAProductType.IPD_INTERACTION,
        meta_source_flag=MetaSourceFlag.POOLED_ESTIMATE,
        priority=7,
        is_mandatory=False,
        description="Individual-level interaction coefficients (IPD-MA only)",
    ))
```

**Verification:**
- [ ] IPDMA plan includes `IPD_INTERACTION` product
- [ ] Product agents map exists (even if agents not yet implemented)

---

### Slice R4: Aggregation Pipeline Amendments

**Goal:** MA heterogeneity parameters pass through to Layer 3, and dose-response
point rows are compiled into Emax curves.

**Gate:** For an edge with MA-derived evidence that includes `heterogeneity_json`,
the aggregation pipeline uses the published I²/τ² rather than re-estimating.

**Depends:** Slice 2 (edge evidence must exist), R1 (MA subtypes).

#### R4.1 Heterogeneity Passthrough

**Where:** `crci/extraction/p4_aggregation/meta_analyzer.py`

**When:** The DCR decision is `USE_MA_POOLED` and the MA row has populated
`heterogeneity_json`, pass through the published values:

```python
def _use_published_heterogeneity(
    ma_claim: HarmonizedClaim,
) -> dict | None:
    """Extract published heterogeneity from MA claim when available.

    When the aggregation pipeline uses an MA pooled estimate (DCR decision),
    we should use the MA's published I²/τ² rather than re-estimating from
    constituent studies. Re-estimation from a mix of MA-pooled and primary
    estimates is methodologically incoherent.
    """
    het_json = getattr(ma_claim, 'heterogeneity_json', None)
    if het_json and isinstance(het_json, dict):
        logger.info(
            "R4-HET: Using published heterogeneity from MA %s: I²=%.2f, τ²=%.4f",
            ma_claim.study_id,
            het_json.get('I2', -1),
            het_json.get('tau2', -1),
        )
        return het_json
    return None
```

Wire into `meta_analyzer.analyze_edge()`: when the input includes an MA row with
heterogeneity data AND the DCR decision chose the MA, skip τ² estimation and use
the published values.

**Verification:**
- [ ] Test: MA with `heterogeneity_json` → pipeline uses published I²/τ²
- [ ] Test: primary-only evidence → pipeline estimates τ² normally
- [ ] Published I² stored in `PooledEstimate` output for downstream consumption

#### R4.2 NMA Three-Way Overlap Detection

**Where:** `crci/extraction/p4_aggregation/double_counting.py`

**When:** Both a pairwise MA and an NMA cover the same edge comparison.

**Implementation:** Phase 1 — detection + warn-log:

```python
def _detect_nma_pairwise_overlap(
    ma_claims: list[HarmonizedClaim],
    edge_relation_id: str,
) -> list[str]:
    """Detect if both NMA and pairwise MA claims exist for same edge.

    Phase 1: warn and log. Phase 2: implement preference rules.
    """
    nma_claims = [c for c in ma_claims
                  if getattr(c, 'meta_source_flag', None) == MetaSourceFlag.NMA_MIXED.value]
    pw_claims = [c for c in ma_claims
                 if getattr(c, 'meta_source_flag', None) == MetaSourceFlag.POOLED_ESTIMATE.value]

    warnings = []
    if nma_claims and pw_claims:
        msg = (
            f"R4-NMA3: Edge {edge_relation_id} has both NMA mixed estimate(s) "
            f"({len(nma_claims)}) and pairwise MA pooled estimate(s) "
            f"({len(pw_claims)}). Three-way overlap possible. "
            f"Manual review recommended."
        )
        warnings.append(msg)
        logger.warning(msg)
    return warnings
```

**Verification:**
- [ ] Test: NMA + pairwise MA for same edge → warning emitted
- [ ] No crash; conservative behavior (keeps both, logs warning)

#### R4.3 Dose-Response Point Compilation Wiring

**Where:** `crci/extraction/p7_compilers/dose_response_compiler.py` (EXISTS)

**Current state:** The compiler exists but the pipeline path from
`DOSE_RESPONSE_POINT` rows in `edge_evidence_v1` → Emax curve fitting is not
explicitly triggered.

**Fix:** In P7 runner, query for `DOSE_RESPONSE_POINT` rows per edge and
pass to the dose-response compiler:

```python
# In p7_compilers/runner.py:
dr_rows = session.execute(
    select(EdgeEvidence).where(
        EdgeEvidence.meta_source_flag == MetaSourceFlag.DOSE_RESPONSE_POINT.value,
        EdgeEvidence.active == 1,
    )
).scalars().all()

if dr_rows:
    from crci.extraction.p7_compilers.dose_response_compiler import compile_dose_response
    dr_results = compile_dose_response(dr_rows)
    context["dose_response_compilations"] = dr_results
```

**Verification:**
- [ ] Test: `DOSE_RESPONSE_POINT` rows exist → compiler invoked
- [ ] Test: compiler produces Emax/Hill parameters
- [ ] No crash when 0 dose-response rows exist

---

### Slice R5: LLM Guardrail Enforcement

**Goal:** The 8 universal guardrails (UG-01 through UG-08) and key paper-type
guardrails (MG/PG) have code enforcement — not just documentation.

**Gate:** Each guardrail has a code-level check that either blocks, flags, or
transforms the violating extraction.

**Depends:** None (can run in parallel with any slice). Implementation in the
trust boundary and P1 runner.

**Philosophy:** Guardrails are defense-in-depth. Some are already partially
enforced (UG-01, UG-02, UG-04). The goal is to close gaps and make enforcement
explicit with guardrail IDs in log messages.

#### R5.1 UG-05: No Extraction from Figures

**Where:** `crci/extraction/tb_trust_boundary/runner.py`

**Current state:** `missingness_provenance.py` references `guardrail_blocked` for
figure-only sources, but no code checks provenance for figure-only values.

**Implementation:**

```python
def _check_figure_only(span: SpanLabel) -> bool:
    """UG-05: Block values sourced only from figures/images.

    LLMs cannot reliably extract numbers from plots. If the source
    snippet references a figure, block the span.
    """
    snippet = (span.extraction_snippet or "").lower()
    figure_markers = ["figure ", "fig.", "fig ", "plot ", "graph "]
    # Only block if source is EXCLUSIVELY a figure reference
    if any(m in snippet for m in figure_markers):
        if not any(t in snippet for t in ["table", "results section", "text"]):
            return True
    return False
```

When triggered: set `parse_status = AMBIGUOUS`, `blocked_reason = "UG-05:
source_is_figure_only"`.

**Verification:**
- [ ] Test: span with `extraction_snippet="Figure 3"` → blocked
- [ ] Test: span with `extraction_snippet="Table 2 (see also Figure 3)"` → NOT blocked

#### R5.2 UG-08: Sensitivity Analysis Flagging

**Where:** `crci/extraction/p1_extraction/agents/ag05_stats_label.py` or
`crci/extraction/tb_trust_boundary/runner.py`

**Implementation:**

```python
_SENSITIVITY_MARKERS = frozenset({
    "sensitivity analysis", "sensitivity analyses",
    "robustness check", "supplementary analysis",
    "leave-one-out", "trim and fill", "trim-and-fill",
})

def _flag_sensitivity_analysis(span: SpanLabel) -> bool:
    """UG-08: Flag values from sensitivity/supplementary analyses."""
    snippet = (span.extraction_snippet or "").lower()
    return any(m in snippet for m in _SENSITIVITY_MARKERS)
```

When triggered: append `[SENSITIVITY_ANALYSIS]` to notes, apply lower weight
in aggregation.

**Verification:**
- [ ] Test: span from "sensitivity analysis" section → flagged
- [ ] Test: primary result → not flagged

#### R5.3 MG-04: Umbrella Review Numeric Rejection at Trust Boundary

**Where:** `crci/extraction/tb_trust_boundary/runner.py`

This is defense-in-depth behind R2.1 (which blocks at the plan level).

**Implementation:** If `paper_subtype == UMBRELLA_REVIEW` and the TB receives
numeric spans that would produce evidence rows, reject them with
guardrail code `MG-04`.

**Verification:**
- [ ] Test: umbrella review with numeric spans → all rejected by TB
- [ ] Cross-validates with R2.1 (belt + suspenders)

#### R5.4 PG-01: RCT Randomization Language Verification

**Where:** `crci/extraction/p2_harmonization/runner.py`

**Implementation:**

```python
_RCT_SUBTYPES = {
    PaperSubtype.RCT_EXERCISE.value,
    PaperSubtype.RCT_COGNITIVE.value,
    PaperSubtype.RCT_PHARMACOLOGICAL.value,
    PaperSubtype.RCT_MULTIMODAL.value,
    PaperSubtype.STANDARD_RCT.value,
    PaperSubtype.FACTORIAL_RCT.value,
    PaperSubtype.CROSSOVER_RCT.value,
    PaperSubtype.PILOT_RCT.value,
}

def _verify_rct_randomization(
    paper_subtype: str,
    canonical_text: str | None,
) -> str:
    """PG-01: Verify RCT papers describe randomization.

    If randomization language absent, demote identification_status.
    """
    if paper_subtype not in _RCT_SUBTYPES:
        return IdentificationStatus.IDENTIFIED.value

    text = (canonical_text or "").lower()[:10000]
    randomization_terms = [
        "randomized", "randomised", "random assignment",
        "random allocation", "randomly assigned", "randomly allocated",
    ]
    if any(term in text for term in randomization_terms):
        return IdentificationStatus.IDENTIFIED.value

    logger.info(
        "PG-01: RCT paper lacks randomization language. "
        "Demoting identification_status to partially_identified."
    )
    return IdentificationStatus.PARTIALLY_IDENTIFIED.value
```

**Verification:**
- [ ] Test: RCT text with "randomly assigned" → identified
- [ ] Test: RCT text without any randomization language → partially_identified

#### R5.5 PG-04: Animal Model Species Documentation

**Where:** `crci/extraction/p1_extraction/agents/ag03_cohort.py` (or P2)

**Implementation:** When `paper_subtype` is `MECHANISTIC_ANIMAL`, the cohort
agent must extract species, strain, sex, and model. If missing, append note:
`[PG-04: species not documented]`.

Phase 1: warn-log only. Phase 2: make species extraction mandatory field for
animal studies.

**Verification:**
- [ ] Test: animal study with species in text → species recorded
- [ ] Test: animal study without species → warning logged

#### R5.6 MG-02: Random-Effects Default for MAs

**Where:** `crci/extraction/p1_extraction/ma_multi_product.py` or AG05 prompt

**Current state:** The spec says "if both fixed and random models reported,
extract random-effects as primary." Not currently enforced — LLM picks whatever
it finds first.

**Implementation:**

```python
# In MA product extraction post-processing:
def _enforce_random_effects_default(
    pooled_row: dict,
    notes: str,
) -> dict:
    """MG-02: When both RE and FE reported, use RE as primary.

    Record FE estimate in notes for sensitivity comparison.
    """
    if pooled_row.get("model_reported") == "fixed_effects":
        if "random" in (notes or "").lower() and "fixed" in (notes or "").lower():
            logger.info(
                "MG-02: Both RE and FE reported. Using RE as primary."
            )
            # Swap is handled by the LLM prompt instruction;
            # this is defense-in-depth.
    return pooled_row
```

Primary enforcement is in the AG05 prompt. Code check is defense-in-depth.

**Verification:**
- [ ] AG05 prompt instructs RE preference when both reported ✅ (verify)
- [ ] Notes field records FE estimate when both available

#### R5 Validation

```bash
python -m pytest tests/test_extraction/test_guardrails.py -v
```

New test file covering UG-05, UG-08, MG-04, PG-01, PG-04, MG-02.

---

### Routing Slices: Files Modified Summary

| Slice | File | Change |
|-------|------|--------|
| R1.1 | `crci/shared/models/enums.py` | Add `MINIMAL` to `ExtractionMode` |
| R1.2 | `crci/shared/models/enums.py` | Add 15 new `PaperSubtype` members |
| R1.3 | `crci/extraction/p0_triage/mode_selection.py` | Extend routing table, handle `MINIMAL` mode |
| R1.4 | `crci/extraction/p1_extraction/ma_multi_product.py` | Add MA subtypes to plan builder, umbrella block |
| R1.5 | `crci/retrieval/hop_discoverer.py` | Replace string literals with enum refs |
| R1.6 | `crci/llm/prompts/ptc_prompt.txt` | Update classifier prompt with all subtypes |
| R2.1 | `crci/extraction/evidence_writer.py` | Umbrella review evidence block gate |
| R2.2 | `crci/extraction/evidence_writer.py` | MINIMAL-mode evidence block gate |
| R2.3 | `crci/extraction/p2_harmonization/runner.py` | Pilot RCT quality cap |
| R2.4 | `crci/extraction/p2_harmonization/runner.py` | Cross-sectional ID demotion |
| R2.5 | `crci/extraction/p2_harmonization/runner.py` | NMA identification demotion |
| R3.1 | `crci/extraction/evidence_writer.py` | Forest plot auto-supersede |
| R3.2 | `crci/extraction/p4_aggregation/evidence_grouper.py` | Subgroup correlation warning |
| R3.3 | `crci/extraction/p1_extraction/ma_multi_product.py` | IPD-MA product skeleton |
| R4.1 | `crci/extraction/p4_aggregation/meta_analyzer.py` | Heterogeneity passthrough |
| R4.2 | `crci/extraction/p4_aggregation/double_counting.py` | NMA three-way overlap detection |
| R4.3 | `crci/extraction/p7_compilers/runner.py` | Dose-response point compilation wiring |
| R5.1 | `crci/extraction/tb_trust_boundary/runner.py` | UG-05 figure-only block |
| R5.2 | `crci/extraction/tb_trust_boundary/runner.py` | UG-08 sensitivity analysis flag |
| R5.3 | `crci/extraction/tb_trust_boundary/runner.py` | MG-04 umbrella numeric rejection |
| R5.4 | `crci/extraction/p2_harmonization/runner.py` | PG-01 RCT randomization check |
| R5.5 | `crci/extraction/p1_extraction/agents/ag03_cohort.py` | PG-04 animal species doc |
| R5.6 | `crci/extraction/p1_extraction/ma_multi_product.py` | MG-02 RE default |
| Tests | `tests/test_extraction/test_routing_gates.py` | **NEW** — R2 enforcement tests |
| Tests | `tests/test_extraction/test_guardrails.py` | **NEW** — R5 guardrail tests |

---

## Hardening Tasks (Post-Slice 4)

These are valid concerns that don't block the critical path:

| Task | Priority | Why Deferred |
|------|----------|-------------|
| Canonical text buffer for offsets | MEDIUM | Offsets are provenance, not survival-path |
| `source_block` field on spans | MEDIUM | Debugging aid, not data flow |
| OCR support for scanned PDFs | LOW | Out of scope; use text PDFs |

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

*Last updated: 2026-02-26 (post-review revision)*
