# CRCI Extraction Pipeline — Comprehensive Audit

**Date**: 2025-01-XX
**Scope**: Full vertical + horizontal audit of P0 → P1 → TB → P2 → P3 → P4 → P4B → P5 → P6 → P7
**Method**: Line-by-line code read of every runner + orchestrator + key sub-modules

---

## SEVERITY LEGEND

| Level | Meaning |
|-------|---------|
| **S0-FATAL** | Pipeline crashes, data destroyed, no recovery |
| **S1-CRITICAL** | Stage produces wrong/empty output, downstream cascade failure |
| **S2-HIGH** | Significant data quality degradation or silent data loss |
| **S3-MEDIUM** | Suboptimal behavior, degraded provenance, or missing enrichment |
| **S4-LOW** | Cosmetic, non-functional, or long-term improvement |

---

## ISSUE INVENTORY

### BUG-001 — Transaction Rollback Destroys All Data [S0-FATAL]

**File**: `crci/extraction/pipeline.py` lines 545-560
**Symptom**: When P6 raises `GateViolation`, the `get_session()` context manager catches the re-raised exception and calls `session.rollback()`, wiping ALL data written in P0-P5 (study_registry, annotations, evidence rows, etc.).

**Root Cause**: `_run_pipeline_with_session()` catches `GateViolation`, calls `mark_run_failed(session, run, error_msg)` which does `session.flush()`, then **re-raises**. The re-raise propagates to `run_extraction_pipeline()` which uses `with get_session() as managed_session:`. The `get_session()` context manager's `except` clause calls `session.rollback()`, undoing ALL writes including `mark_run_failed` itself.

**Impact**: Every pipeline run that hits a gate violation (which is 100% of SR papers and any paper that fails P6) loses all data.

**Fix**:
```python
# In pipeline.py — catch GateViolation and commit before re-raising
except GateViolation as exc:
    error_msg = f"Gate violation {exc.gate_id}: {exc}\nContext: {exc.context}"
    mark_run_failed(session, run, error_msg)
    session.commit()  # <-- Persist the failure record + all prior data
    raise
```
Or better: use nested transactions / savepoints so the run record + study registration survive.

---

### BUG-002 — `context["compiled_edges"]` Never Populated [S1-CRITICAL]

**File**: `crci/extraction/p4_aggregation/runner.py` lines 220-228
**Symptom**: P4-WRT calls `write_all_edges()` which returns `list[CompiledEdge]`, but the runner only saves `context["edges_written"] = len(compiled_edges)` — the count, not the actual objects.

**Impact**: P5 and P6 both read `context.get("compiled_edges", [])` and always receive `[]`. This means:
- P5 coverage analysis sees 0 edges
- P5 chain validation sees 0 edges
- P5 E-value computes on 0 edges
- P6 G1 rule ("minimum_edges") always FAILS → BLOCK → GateViolation → (cascades into BUG-001)

**Fix**:
```python
# In P4 runner, after write_all_edges:
compiled_edges = write_all_edges(compilation_inputs=compilation_inputs, session=session)
context["compiled_edges"] = compiled_edges  # <-- ADD THIS LINE
context["edges_written"] = len(compiled_edges)
```

---

### BUG-003 — No SR/MA-Aware P6 Exemption [S1-CRITICAL]

**File**: `crci/extraction/p6_deployment/validation_runner.py` line 75; `deploy_gate.py`
**Symptom**: P6 rule G1 requires `len(compiled_edges) > 0`. Systematic reviews don't produce edge evidence directly — their value is in identifying constituent studies for hop discovery. But there's no SR-aware exemption in the validation rules.

**Impact**: Every SR paper will always be BLOCKED at P6, even when the pipeline correctly identified included studies.

**Fix**: Add SR-aware logic — if `paper_subtype == "systematic_review"` and `included_study_ids` are populated, G1 should PASS (or WARN, not FAIL). The SR's job is to queue constituent studies, not produce edges itself.

---

### BUG-004 — `included_study_ids_json` Never Written [S1-CRITICAL]

**File**: `crci/extraction/p1_extraction/runner.py` (entire file — no writer exists)
**Symptom**: The MA extraction plan identifies `INCLUDED_STUDY_LIST` as a mandatory product for SR/MA papers (priority 3), and the `study_registry_v1` table has an `included_study_ids_json` column. But **no code anywhere** populates this field.

**Impact**: `hop_discoverer.py` reads this field to queue constituent studies, but it's always NULL. The entire SR→hop discovery→constituent extraction pipeline is broken.

**Evidence**:
- `ma_multi_product.py` line 95: `MAProductType.INCLUDED_STUDY_LIST` is mandatory
- `tables.py` line 760: `included_study_ids_json = Column(Text)`
- `hop_discoverer.py` line 67: `StudyRegistry.included_study_ids_json.isnot(None)`
- No `session.query(StudyRegistry).update({"included_study_ids_json": ...})` exists anywhere in the codebase

**Fix**: P1 runner needs to use an LLM agent (likely AG10 StrategicIntelAgent or a dedicated agent) to extract included study DOIs/PMIDs, then write them as JSON to `study_registry_v1.included_study_ids_json`.

---

### BUG-005 — `hop_discoverer` Never Called From Pipeline [S1-CRITICAL]

**File**: `crci/retrieval/hop_discoverer.py` (exists but disconnected)
**Symptom**: Even if BUG-004 were fixed, nothing in the extraction pipeline P0-P7 calls `hop_discoverer.discover_hops()`.

**Impact**: SR/MA papers never trigger constituent study acquisition. The hop discovery system is dead code.

**Fix**: Call `hop_discoverer.discover_hops(session)` from the pipeline after P1 for SR/MA papers, or as a post-pipeline hook.

---

### BUG-006 — P2 Hardcoded Effect Type and Orientation [S2-HIGH]

**File**: `crci/extraction/p2_harmonization/runner.py` lines 131, 162-164
**Symptom**: Four critical parameters are hardcoded for ALL claims:
1. `effect_type_reported="group_diff"` (line 131, 148)
2. `dag_orientation=Orientation.HIGHER_WORSE` (line 162)
3. `reported_direction_positive=True` (line 163)
4. `orientation_confidence=0.7` (line 164)

**Impact**:
- Claims that are correlations, odds ratios, or hazard ratios are treated as group differences
- All effects are assumed to be in the "higher is worse" direction, even for protective effects
- Orientation confidence is always moderate even when agents provide strong evidence
- This cascades into wrong sign/magnitude in P3 and P4

**Fix**: Derive these from agent annotations (AG05 `StatsLabelAgent` should provide `effect_type_reported`; DAG lookup or AG06 should provide orientation).

---

### BUG-007 — P0 Uses Random UUID for paper_id [S3-MEDIUM]

**File**: `crci/extraction/p0_triage/runner.py` line 119
**Symptom**: `paper_id = f"STUDY_{uuid.uuid4().hex[:12]}"` generates a random ID every run. The DOI from the PDF metadata is stored in the `study_registry_v1.doi` column but never used to form the `paper_id`.

**Impact**:
- Re-extracting the same paper creates a new study_id each time
- No deduplication by DOI at the study level
- Idempotency check uses `paper_hash` (binary PDF hash), which only catches exact file duplicates, not same-paper-different-PDF-scan

**Fix**: If DOI is available, derive `paper_id` from it (e.g., `"STUDY_" + doi_to_id(doi)`). Fall back to UUID only when no DOI exists.

---

### BUG-008 — P0 Doesn't Read meta.json [S3-MEDIUM]

**File**: `crci/extraction/p0_triage/runner.py`
**Symptom**: P0 reads the PDF via `ingest_pdf()` for metadata extraction, but never reads the companion `.meta.json` file that may exist alongside the PDF in `data/manual_uploads/structured/`. This file contains pre-seeded DOI, PMID, title, and author information.

**Impact**: Metadata quality depends entirely on PDF parsing quality. Manually curated metadata in `.meta.json` is ignored.

**Fix**: After ingesting the PDF, check for `pdf_path.with_suffix('.meta.json')` and also check the structured upload directory pattern `data/manual_uploads/structured/{paper_key}/meta.json`. Merge metadata from meta.json with PDF-extracted metadata.

---

### BUG-009 — AG09 ReconciliationAgent Missing From Agent List [S2-HIGH]

**File**: `crci/extraction/p1_extraction/runner.py` lines 118-129
**Symptom**: P1 imports and instantiates AG01-AG08, AG10, AG11 — but AG09 is missing. The agent list skips from AG08 (`TemporalAgent`) to AG10 (`StrategicIntelAgent`).

**Impact**: Whatever AG09 was designed to extract (reconciliation-specific extraction tasks) is never performed. There IS a separate `reconciliation.py` module called after agents run, but AG09 may have been a dedicated extraction agent for inter-study reconciliation data.

**Note**: AG09 may be intentionally omitted if reconciliation is handled by `reconciliation.py` rather than as an agent. Verify against spec to confirm.

---

### BUG-010 — P3 Silently Drops Records Without SE [S2-HIGH]

**File**: `crci/extraction/p3_heterogeneity/runner.py` lines 107-109
**Symptom**: `if se_raw is None: logger.debug("P3-ASM: skipping record with no SE"); continue`

For systematic reviews, most claims may not have standard errors (narrative synthesis, qualitative findings). These are silently dropped at P3, leaving `calibrated_records` empty.

**Impact**: SR papers lose ALL their claims at P3 because the LLM extracts narrative findings without numeric SEs. This cascades to P4 returning empty, P5 seeing nothing, P6 blocking.

**Fix**: For SR papers, either:
- Compute SE from CI or p-value (SE derivation already exists in the conversion router)
- Flag claims without SE as "qualitative" and route them through a separate non-pooling pathway
- Don't attempt pooling for narrative SRs; instead focus on the included study list

---

### BUG-011 — Study Design Always "unclassified" When AG02 Fails [S2-HIGH]

**File**: `crci/extraction/p3_heterogeneity/runner.py` line 113
**Symptom**: `study_design=getattr(rec, "study_design", "unclassified")` — when AG02 fails (schema validation error on SR papers), no study design is set, so all records default to "unclassified".

In P3-L1 (design quality layer), "unclassified" gets the maximum uncertainty multiplier (3.0x), dramatically inflating SE_eff for all records.

**Impact**: Even if records survive to P4, their SEs are 3x too large, producing unreliable pooled estimates.

**Fix**: Fall back to P0's `classified_paper.study_design` (which was correctly determined during triage) rather than relying solely on AG02.

---

### BUG-012 — P2-P3 Type Boundary Fragile [S2-HIGH]

**File**: `crci/extraction/p2_harmonization/runner.py` → `crci/extraction/p3_heterogeneity/runner.py`
**Symptom**: P2 outputs `aligned_list` (which contains `ScaledNumeric` objects with `.beta` and `.se` fields) as `context["harmonized_records"]`. P3 then reads these and accesses `.se`, `.study_design`, `.ler_id`, `.n_total`, etc. via `getattr(rec, ...)`.

The boundary is entirely duck-typed — there's no typed contract. If P2's output type changes (e.g., `ScaledNumeric` → `IdentificationResult`), P3 silently gets wrong values.

Additionally, P2's `ScaledNumeric` objects may not have `.study_design`, `.ler_id`, `.n_total`, or `.group_betas` attributes. P3 relies on `getattr` with defaults, which silently degrades.

**Impact**: Silent data loss at the P2→P3 boundary. Fields that P3 expects but P2 doesn't set are filled with defaults ("unclassified", None, 0.0).

---

### BUG-013 — P4B Doesn't Write to Context [S3-MEDIUM]

**File**: `crci/extraction/p4b_publication_bias/runner.py`
**Symptom**: P4B stores results in `context["bias_results"]` but P4-WRT (which runs before P4B in the chain sequence) has already written edges without publication bias adjustments. P4B exists as a separate chain that runs AFTER P4, but its output isn't retroactively applied to the compiled edges.

**Impact**: Publication bias SE inflation is computed but never applied to the compiled edges stored in `edges_v1`. The `pub_bias_map` parameter in `build_compilation_inputs()` is never populated from P4B output because P4B runs after P4.

**Fix**: Either (a) merge P4B into P4 before edge writing, or (b) have P4B update the existing edge rows in `edges_v1` with bias adjustments.

---

### BUG-014 — P5 Chain Validation Has No Pathway Data [S3-MEDIUM]

**File**: `crci/extraction/p5_sufficiency/runner.py` lines 86-93
**Symptom**: `pathways: list[PathwayDefinition] = []` — hardcoded empty list. No pathway definitions are loaded from the database or `PATHWAY_REGISTRY.csv`.

**Impact**: Chain validation always sees 0 chains, produces no SE inflation adjustments, and reports "0 chains validated".

**Fix**: Load pathway definitions from `pathway_registry_v1` or `PATHWAY_REGISTRY.csv` and pass to `validate_all_pathways()`.

---

### BUG-015 — P7 Runs After P6 Gate [S3-MEDIUM]

**File**: `crci/extraction/pipeline.py` _CHAIN_SEQUENCE (P7 is last)
**Symptom**: P7 compilers only run if P6 passes. But P6 always fails for SRs (BUG-003) and always fails when BUG-002 isn't fixed. This means P7 compilers never run.

**Impact**: Psychometric, prior, temporal, dose-response, modifier, and synergy compilations never execute. These are important for the downstream algorithm chains (Chain B, C, D, E).

**Note**: This is by design (P7 should only run on validated evidence), but combined with BUGs 002/003, it means P7 never gets a chance to run.

---

---

## CROSS-STAGE DATA FLOW MAP

### Context Keys Written (W) vs Read (R) by Each Stage

| Context Key | P0 | P1 | TB | P2 | P3 | P4 | P4B | P5 | P6 | P7 |
|---|---|---|---|---|---|---|---|---|---|---|
| `pdf_path` | W | R | | | | | | | | |
| `paper_hash` | W | | | | | | | | | |
| `extraction_run_id` | W | R | | | | | | | | |
| `paper_id` | W | R | R | R | R | R | | | | |
| `ingested_paper` | W | R | | | | | | | | |
| `screened_paper` | W | | | | | | | | | |
| `classified_paper` | W | | | R | | | | | | |
| `triage_result` | W | R | | | | | | | | |
| `extraction_mode` | W | R | | | | | | | | |
| `paper_map` | | W | R | | | | | | | |
| `ma_extraction_plan` | | W | | | | | | | | |
| `raw_annotations` | | W | | | | | | | | |
| `all_span_labels` | | W | R | | | | | | | |
| `reconciliation_result` | | W | | | | | | | | |
| `atb_result` | | W | | | | | | | | |
| `parsed_claims` | | | W | R | | | | | | |
| `failed_claims` | | | W | | | | | | | |
| `tb_result` | | | W | R | | | | | | |
| `harmonized_records` | | | | W | R | | | | | |
| `p2_plausibility` | | | | W | | | | | | |
| `p2_converted` | | | | W | | | | | | |
| `p2_harmonized` | | | | W | | | | | | |
| `p2_oriented` | | | | W | | | | | | |
| `p2_identified` | | | | W | | | | | | |
| `parameter_family_counts` | | | | W | | | | | | |
| `evidence_rows_written` | | | | W | | | | | | |
| `calibrated_records` | | | | | W | R | | | | |
| `pooled_estimates` | | | | | | W | R | R | | |
| `meta_analysis_results` | | | | | | W | | | | |
| `escalation_results` | | | | | | W | | | | |
| `prior_assignments` | | | | | | W | | | | |
| `prior_specs` | | | | | | W | | | | |
| `edges_written` | | | | | | W | | | | |
| **`compiled_edges`** | | | | | | **MISSING** | | **R** | **R** | |
| `shared_control_applied` | | | | | | W | | | | |
| `bias_results` | | | | | | | W | R | R | |
| `missingness_report` | | | | | | | | R | | |
| `sufficiency_report` | | | | | | | | W | R | |
| `validation_result` | | | | | | | | | W | |
| `deploy_gate_decision` | | | | | | | | | W | |

### Critical Gap (highlighted):
- **`compiled_edges`**: Read by P5 and P6, but **never written** by P4. P4 writes edges to the DB and saves the count, but not the objects.

---

## SR/MA-SPECIFIC PATH TRACE

For a systematic review paper, this is what actually happens vs what should happen:

| Stage | What Should Happen | What Actually Happens | Status |
|-------|-------------------|----------------------|--------|
| P0 | Classify as SR, register, read meta.json | Classifies as SR ✓, registers with random UUID, no meta.json | PARTIAL |
| P1 | Build MA plan, extract included studies, write to study_registry | Builds MA plan ✓, agents run ✓, but **never writes included_study_ids_json** | BROKEN |
| P1+ | Call hop_discoverer to queue constituent studies | **Never called** | BROKEN |
| TB | Parse numeric claims from agent outputs | Works ✓ (but SR claims may be sparse) | OK |
| P2 | Harmonize claims, fix orientation | Hardcoded defaults for effect type/orientation | DEGRADED |
| P3 | Apply 7-layer calibration | **Drops all records without SE** (most SR claims) | BROKEN |
| P4 | Pool estimates, write edges | Returns empty (no calibrated records) — **expected for narrative SRs** | OK-ISH |
| P4B | Assess publication bias | Skips (no pooled estimates) — expected | OK |
| P5 | Assess sufficiency | **Sees 0 compiled edges** (BUG-002) | BROKEN |
| P6 | Validate for deployment | **Always FAILS on G1** (no edges) → GateViolation | BROKEN |
| P6+ | GateViolation propagation | **Rollback destroys ALL data** including study_registry | FATAL |
| P7 | Run compilers | Never reached | BLOCKED |

**Net result**: SR papers produce NO persisted data. Not even the study_registry row survives.

---

## FIX PRIORITY ORDER

### Phase 1: Stop the Data Destruction (Day 1)
1. **BUG-001**: Fix transaction rollback — commit before re-raising GateViolation
2. **BUG-002**: Add `context["compiled_edges"] = compiled_edges` in P4 runner

### Phase 2: Make SRs Work (Day 2-3)
3. **BUG-003**: Add SR-aware P6 exemption (G1 passes if included_study_ids detected)
4. **BUG-004**: Write `included_study_ids_json` in P1 for SR/MA papers
5. **BUG-005**: Call `hop_discoverer` from pipeline or post-pipeline hook

### Phase 3: Fix Data Quality (Day 4-5)
6. **BUG-006**: Derive effect_type and orientation from agent annotations
7. **BUG-011**: Fall back to P0's study_design when AG02 fails
8. **BUG-010**: Handle records without SE (SE derivation or qualitative routing)
9. **BUG-012**: Add typed contract at P2→P3 boundary

### Phase 4: Polish (Day 6+)
10. **BUG-007**: Use DOI-derived paper_id
11. **BUG-008**: Read meta.json in P0
12. **BUG-009**: Verify AG09 intent
13. **BUG-013**: Apply P4B bias adjustments to compiled edges
14. **BUG-014**: Load pathway definitions for P5

---

## VERIFICATION CHECKLIST

After fixes are applied, verify with these test cases:

- [ ] **TC-001**: Extract primary study (RCT) — should DEPLOY with edges
- [ ] **TC-002**: Extract SR paper — should register, detect included studies, queue hop discovery, and P6 should PASS (or WARN, not BLOCK)
- [ ] **TC-003**: Extract SR paper with meta.json — should use meta.json DOI
- [ ] **TC-004**: Force P6 BLOCK — run record should persist in DB (not rolled back)
- [ ] **TC-005**: Re-extract same paper — idempotency should catch it
- [ ] **TC-006**: P2→P3 boundary — all required fields present
- [ ] **TC-007**: P4→P5→P6 flow — compiled_edges in context, not just count
