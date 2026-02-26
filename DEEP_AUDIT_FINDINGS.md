# Deep Audit: Extraction Pipeline Root-Cause Analysis

**Date**: 2026-02-26 (session 2)  
**Scope**: End-to-end trace of every failure mode from PDF → compiled edge  
**Method**: Code reading + DB forensics + data quality inspection  
**Verdict**: **The extraction protocol has 8 structural failures, 5 of which are fatal.**  
**Prior audit (PIPELINE_AUDIT.md) identified 8 issues; 6 remain unfixed.**  
**Expert review (2026-02-26): 6 corrections integrated, 2 missing root causes added.**

---

## Executive Summary

The pipeline *runs to completion* (10/10 stages) but **0/31 evidence records
meet Deployable Evidence Record criteria**. Every compiled edge is unusable.

### Deployable Evidence Record Criteria (DER)

A record is deployable if and only if ALL of the following hold:

| # | Criterion | 31/31 pass? |
|---|-----------|-------------|
| DER-1 | `edge_relation_id ∈ edge_relations_definitions_v1` | ❌ (EDGE_CORTISOL_DEPRESSION not in definitions) |
| DER-2 | Has precision source: `se_reported` OR (`ci_low` & `ci_high`) OR (`p_value` & `N_effect`) | ❌ (0/31 have any precision source) |
| DER-3 | `study_id` and `paper_id` present | ⚠️ (study_id present but = paper_id, no independent study fingerprint) |
| DER-4 | `effect_type_reported` ∈ allowed estimand set {SMD, LOG_OR, BETA_STD, BETA_UNSTD, R, HR_LOG} | ❌ (all say "harmonized_beta" — no declared estimand family) |
| DER-5 | Timepoint / contrast minimally disambiguated | ❌ (no timepoint_bucket or contrast_id populated) |
| DER-6 | Passes semantic dedup uniqueness constraint (one primary record per EvidenceKey) | ❌ (12 duplicate betas for ER_COGACTIVITY_WORKMEM) |

**Result: 0/31 records meet deployable criteria.** This is an auditable fact.

### Compiled Edge Failures

| Compiled Edge | β | SE | Usable? | Why Not |
|---|---|---|---|---|
| `ER_COGACTIVITY_WORKMEM` | -1.001 | 1.211 | ❌ | 12 duplicate betas from the same paper, all using L6 SE=1.0 |
| `EDGE_CORTISOL_DEPRESSION` | 0.289 | 2.004 | ❌ | Orphaned: zero evidence rows exist. Edge ID not in definitions. |
| `ER_ACTIVITY_PROC_SPEED` | -0.155 | 2.302 | ❌ | 2 records, SE=None for one, L6 SE=1.0 for the other. |

The pipeline succeeds technically but fails scientifically. The root cause
is not any single bug — it's a cascading failure chain where each
component's "graceful degradation" passes garbage to the next stage.

---

## The Cascade of Failure

```
PDF Text
  ↓
AG05 (LLM) extracts spans → ✅ Finds numbers
  BUT: grouping_id not returned for SE/CI → 0% group completion
  ↓
Trust Boundary assembles groups → ⚠️ All TypedNumericValue have SE=None
  200-char proximity fallback rarely matches
  ↓
Concept Engine grounds to edges → ⚠️ 60-80% end up UNASSIGNED
  Only works when meta.json has target_edges
  DB has 137 ER_* definitions but concept engine keyword matching is weak
  ↓
P2 harmonizes → writes ALL to DB (including UNASSIGNED with SE=None)
  BUT: skips UNASSIGNED for P3/P4 (correct)
  Creates 8+ stale UNASSIGNED rows in DB
  ↓
P3 calibrates SE → SE=None triggers L6 fallback (SE=1.0)
  se_derivation_tag computed but NEVER stored/logged (dead code)
  ↓
P4 pools via IVW → 1/(1.0²) = 1.0 weight per study
  All studies get EQUAL weight regardless of actual precision
  Pooled SE = 1/√(k×1.0) ≈ 2.0 for k=15 — meaningless
  ↓
edges_v1 stores compiled edge → β ± 2×SE = [-3.7, 4.3] for cortisol
  95% CI includes zero AND the entire plausible range
  This is NOT evidence — it's noise
```

---

## Finding 1: FATAL — Trust Boundary Group Assembly Fails (0% Completion)

**Severity**: S0-FATAL  
**Location**: `crci/extraction/tb_trust_boundary/group_assembler.py`  
**Impact**: Every record downstream has SE=None, CI=None, p_value=None, n=None

### What should happen
AG05 extracts spans like `{label: "EFFECT_SIZE", value: "0.79", grouping_id: "grp_001"}` and
`{label: "SE", value: "0.12", grouping_id: "grp_001"}`. The group assembler joins them into a
single `TypedNumericValue(beta=0.79, se=0.12)`.

### What actually happens
AG05 either:
- Returns no `grouping_id` at all (makes grouping impossible)
- Returns inconsistent grouping_ids (SE gets "grp_002" while EFFECT_SIZE gets "grp_001")
- Returns only PRIMARY spans (EFFECT_SIZE) without SECONDARY spans (SE, CI, p-value)

The group assembler's proximity fallback (200-char window in source text) rarely catches
the SE because paper text often has tables, headers, and paragraph breaks between
effect size and SE reporting.

### Evidence
- All 31 evidence rows in DB have `se_reported=None` or `se_derivation_level=None`
- The 12 Cherrier 2013 pipeline-extracted rows all have `N_effect=0` and SE derived
  from P2/P3 fallbacks, not from the original paper
- TB logs show "0% group completion" in pipeline runs

### Root cause
The AG05 prompt (334 lines in `crci/llm/prompts/ag05_stats_label.txt`) instructs:
> "Use grouping_id to link related statistics... Format: 'grp_001', 'grp_002'"

But the LLM doesn't follow this instruction reliably. The prompt is too long and complex
(40 label types, anchor-gating rules, disambiguation rules). The grouping instruction
is buried in the middle. The LLM prioritizes finding numbers over linking them.

### Why this is fatal
Without SE from the source paper, the entire precision stack collapses:
- P2 scale_harmonizer._resolve_se() tries: direct SE → CI → p-value+N → returns None
- P3 runner falls to L6 (SE=1.0)
- IVW gives equal weight to a study with N=500 and SE=0.05 as to one with N=10 and SE=0.90
- The pooled estimate is entirely driven by the number of extracted spans, not by study quality

---

## Finding 2: FATAL — Concept Engine Grounding Fails (60-80% UNASSIGNED)

**Severity**: S0-FATAL  
**Location**: `crci/extraction/p1_extraction/concept_engine.py`  
**Impact**: Most extracted evidence is discarded before reaching P3/P4

### Three resolution modes exist

| Mode | Works When | Success Rate |
|---|---|---|
| Mode 1: meta.json `target_edges` | Meta.json manually prepared with correct ER_* IDs | ~100% when available |
| Mode 2: Instrument → node → edge | AG04 identifies instruments AND instrument maps to single edge | Rare |
| Mode 3: Keyword matching | Edge canonical_statement contains words from span section | ~20-40% |

### Current state of DB
- 31 evidence rows total
- 11 UNASSIGNED (35% of total)
- Mode 1 works only when meta.json has `target_edges` AND the IDs are valid ER_* IDs

### The `EDGE_CORTISOL_DEPRESSION` failure
The hop paper's meta.json contained `target_edges: ["EDGE_CORTISOL_DEPRESSION"]`.
This ID uses the old `EDGE_*` convention. The DB definitions table has 137 `ER_*` IDs
and **zero** `EDGE_*` IDs. The concept engine loaded edge definitions, found
`EDGE_CORTISOL_DEPRESSION` as a target_edge from meta.json, and Mode 1 mapped all
spans to it. BUT: this edge has no definition in `edge_relations_definitions_v1`.

**Result**: The pipeline successfully compiled an edge that doesn't exist in the ontology.
It has no `node_x`, no `node_y`, no `canonical_statement`. It can never be used by the
algorithm chain because there's no DAG wiring for it.

### Why keyword matching is unreliable
`_match_from_keywords()` requires ≥2 keyword overlaps between span source_section text
and edge canonical_statement. Edge canonical statements use formal terminology
("physical activity → working memory") while paper sections use informal language
("Results", "Table 3", "Cognitive outcomes"). The overlap is minimal.

---

## Finding 3: FATAL — Orphaned Compiled Edge (Data Loss)

**Severity**: S0-FATAL  
**Location**: `edges_v1` table  
**Impact**: EDGE_CORTISOL_DEPRESSION exists as a compiled edge with zero backing evidence

### Timeline reconstruction (forensic hypothesis)

> **Note**: This is a plausible reconstruction based on terminal history
> and DB state. We have not reproduced the exact persistence failure.
> Regardless of root cause, the system lacks referential integrity guards,
> so any such loss is catastrophic.

1. `RUN_20260226T083151_80cdd296`: Hop paper extracted successfully (10/10 stages)
2. P2 wrote evidence rows to edge_evidence_v1 via `session.add()` + `session.flush()`
3. P4 wrote compiled edge to edges_v1 via `session.add()` + `session.flush()`
4. Pipeline returned, `get_session()` called `session.commit()`
5. SQLite WAL mode: commit writes to WAL file, not main DB
6. Between runs: process killed (`kill 144111`), WAL+SHM deleted (`rm -f crci_dev.db-wal crci_dev.db-shm`)
7. Evidence rows in WAL were lost. Compiled edge somehow survived (possibly auto-checkpointed).

### Current state
```
edges_v1: EDGE_CORTISOL_DEPRESSION, β=0.289, SE=2.004, k=unknown
edge_evidence_v1: ZERO rows for this edge
```

This is a **referential integrity violation** that the system has no guard against.
No tool, script, or check detects compiled edges without backing evidence.

---

## Finding 4: HIGH — SE Derivation Produces Meaningless Estimates

**Severity**: S1-CRITICAL  
**Location**: `crci/extraction/p3_heterogeneity/runner.py` lines 125-193  

### The L6 fallback problem
When SE, CI, p-value, and N are all missing (which is EVERY pipeline-extracted record
due to Finding 1), the P3 runner assigns `SE = 1.0` (config.SE_DERIVATION_FALLBACK).

### Layer separation (two distinct inflation stages)

**Stage 1 — P4 IVW with SE=1.0 inputs:**
- Weight per record = 1/SE² = 1/1.0² = 1.0 (all records identical weight)
- This is equivalent to an unweighted mean
- IVW pooled SE = 1/√(Σ 1/SE²) = 1/√k
- For k=15: SE_pooled = 1/√15 ≈ 0.258

**Stage 2 — P3 7-layer SE inflation (applied BEFORE P4):**
- L1 (study_design missing → "unclassified" → 3.0×)
- L4 (cancer_validated missing → "general_population" → 1.30×)
- L5 (rob_overall missing → "MODERATE" → 1.25×)
- **Per-record: SE_eff = 1.0 × 3.0 × 1.30 × 1.25 = 4.875**
- P4 IVW with SE=4.875: weight = 1/4.875² = 0.042 per record
- SE_pooled = 1/√(k × 0.042) ≈ 1/√0.63 ≈ 1.26 for k=15

The compiled SE≈2.004 for cortisol reflects this two-stage inflation. These
stages must not be conflated — the P3 inflation is per-record (correct by design
when real metadata exists), while P4 IVW aggregates across records.

### Dead code: `se_derivation_tag`
```python
se_derivation_tag = "DIRECT"
# ... fallback logic assigns "L2_CI", "L4B_N_DERIVED", "L6_QUALITATIVE"
# BUT: se_derivation_tag is NEVER:
#   - stored to context
#   - written to DB
#   - logged at record level
#   - available to downstream consumers
```
This means there is NO provenance tracking for which SE derivation method was used.
A record with L1_EXACT SE and one with L6_QUALITATIVE SE are indistinguishable
in P4 pooling.

---

## Finding 5: HIGH — P2 Writes UNASSIGNED to DB (Stale Pollution)

**Severity**: S2-HIGH  
**Location**: `crci/extraction/p2_harmonization/runner.py` lines 459-472  
**Evidence**: 11 UNASSIGNED rows in edge_evidence_v1

### The dual-write split
```python
# P2 writes ALL records to DB (including UNASSIGNED):
write_evidence_rows(session=session, run=run, harmonized_records=aligned_list, ...)

# But only passes non-UNASSIGNED to P3/P4:
for record in aligned_list:
    if edge_relation_id == "UNASSIGNED":
        skipped_missing_edge += 1
        continue
    harmonized_claims.append(...)
```

UNASSIGNED records:
- Enter the DB with `edge_relation_id = "UNASSIGNED"`, `se_reported = None`, `N_effect = 0`
- Are never processed by P3/P4/P5/P6/P7
- Are never cleaned up
- Inflate row counts in status reports
- Cannot be joined to edge definitions or used by the algorithm chain
- Are invisible "dark data" that makes the system look more populated than it is

---

## Finding 6: HIGH — Beta Duplication (Same Paper, Same Edge, Multiple Values)

**Severity**: S2-HIGH  
**Evidence**: 12 distinct ER_COGACTIVITY_WORKMEM betas from Cherrier 2013 pipeline extraction

| beta | SE | Source |
|---|---|---|
| 0.767 | 0.3883 | manual_csv_import (correct: d=0.79 from paper) |
| -0.266 | 0.112 | pipeline RUN_084244 |
| -0.487 | 0.183 | pipeline RUN_084244 |
| -0.483 | 0.183 | pipeline RUN_084244 |
| -0.772 | 0.187 | pipeline RUN_084244 |
| -0.380 | 0.182 | pipeline RUN_084244 |
| -0.899 | 0.398 | pipeline RUN_105637 |
| -1.020 | 0.404 | pipeline RUN_105637 |
| -1.012 | 0.403 | pipeline RUN_105637 |
| -1.618 | 0.440 | pipeline RUN_105637 |
| -0.797 | 0.394 | pipeline RUN_105637 |
| -0.774 | 0.393 | pipeline RUN_105637 |

The paper reports a single Cohen's d = 0.79 for this edge. The pipeline extracted
12 different values across 2 runs. These likely come from:
- Raw means (not effect sizes)
- F-statistics converted to d
- p-values converted to d
- Multiple subgroup/timepoint contrasts treated as independent effects

There is NO dedup beyond `span_hash` (which varies with beta value). The `semantic
uniqueness` invariant from PIPELINE_AUDIT.md (INV-4) was never implemented.

The IVW pools all 12 as independent studies, producing β̂=-1.001 which is far from
the paper's actual d=0.79 (and has the WRONG SIGN — the manual import correctly
captured d=0.767 positive).

---

## Finding 7: MEDIUM — 70/96 Evidence Columns Empty

**Severity**: S2-HIGH  
**Evidence**: All 31 evidence rows

The evidence_writer maps 11 fields. The remaining 85 columns are permanently NULL:
- `node_x`, `node_y`: Never populated (algorithm can't determine source/target)
- `upstream_instrument_id`: Never populated (measurement model can't run)
- `cancer_type`, `treatment_phase`: Never populated (context matching impossible)
- `rob_overall`: Never populated (L5 GRADE calibration uses wrong defaults)
- `pub_year`: Never populated (L7 freshness weight wrong)
- `study_design`: Never populated via pipeline (L1 design multiplier defaults to 3.0×)
- `sd_x`, `sd_y`, `ci_low_reported`, `ci_high_reported`: Never populated
- `endpoint_vs_change`, `comparison_arm_label`: Never populated

Combined effect of wrong defaults on 7-layer SE inflation:
- L1 (study_design missing → "unclassified" → 3.0×)
- L4 (cancer_validated missing → "general_population" → 1.30×)
- L5 (rob_overall missing → "MODERATE" → 1.25×)
- **Worst case: 3.0 × 1.30 × 1.25 = 4.875× SE inflation** instead of ~1.0× for a well-done RCT

---

## Finding 8: FATAL — No Canonical Record Identity (EvidenceKey)

**Severity**: S0-FATAL  
**Location**: System-wide — no stable key exists  
**Impact**: Semantic dedup is impossible; 12 duplicate betas for one edge

### The identity gap
The system has no stable key defining what a single evidence record IS.
The current `span_hash` varies with beta value, so different numeric values
for the same conceptual result create separate records.

Without a canonical identity, you will always get:
- Multiple contrasts (baseline vs follow-up, arm A vs B, subgroup vs overall)
- Multiple metrics (raw means, regression coefficients, p-values)
- Multiple timepoints

...all collapsed into "same edge" with no disambiguation.

### Required identity schema
```
EvidenceKey = (
    paper_id,
    study_id,
    edge_relation_id,
    outcome_node_id,
    exposure_node_id,
    timepoint_bucket,
    contrast_id,
    analysis_id,
)
```

If this key is not defined, semantic dedup (INV-4) cannot be implemented
robustly. GATE-QA-4 (see fix plan) depends on this.

---

## Finding 9: FATAL — No Scale/Estimand Validator Before DB Write

**Severity**: S0-FATAL  
**Location**: No validation exists between TB output and P2 DB write  
**Impact**: Sign-flipped nonsense, raw means pooled as effect sizes

### The estimand problem
The system does not validate that the extracted numeric value is actually
the declared estimand. Observed failure modes:

- Raw mean treated as effect size (Cohen's d)
- p-value converted into "d" (spurious transformation)
- F-statistic converted to d (without checking denominator df)
- Subgroup effects treated as independent overall effects

### Required gate
Before any record enters `edge_evidence_v1`:

1. `effect_size_family` must be declared and ∈ {SMD, LOG_OR, BETA_STD, BETA_UNSTD, R, HR_LOG}
2. Allowed transformations must be logged and reversible
3. If a value cannot be mapped into an approved family with precision, it is **rejected**

This is GATE-QA-3 (EstimandDeclaredAndAllowed) in the fix plan.

---

## Summary: Root Cause Analysis

**The pipeline has 3 design flaws and 2 missing primitives.**

### Design Flaw 1: "Graceful Degradation" as a Philosophy

Every component is designed to "not crash" by falling back to defaults:
- TB: Missing grouping? Use proximity fallback. Proximity fails? Emit record with SE=None.
- Concept engine: Can't ground? Emit as UNRESOLVED.
- P2: UNASSIGNED? Write to DB anyway.
- P3: SE=None? Use SE=1.0.
- P4: SE=1.0 for all? Equal-weight IVW.
- Pipeline: Any stage can fail silently, and the next stage "handles" it.

This means the pipeline NEVER crashes, but it ALWAYS produces garbage.
**The correct design**: hard-fail early, reject incomplete records, and only
compile edges from records that have genuine SE from the source paper.

### Design Flaw 2: LLM → Structured Data Without Validation

The pipeline trusts the LLM (AG05) to produce structured output (grouping_ids,
calibrated labels) but has no validation layer that checks:
- "Did the LLM actually group SE with its effect size?"
- "Is this beta value a Cohen's d or a raw mean?"
- "Does this effect size match the paper's reported value?"
- "Are there duplicate extractions for the same conceptual result?"

### Design Flaw 3: No Canonical Record Identity

Without `EvidenceKey`, every dedup strategy is brittle. The current
`span_hash` is a value-based hash, not an identity-based key.

### Missing Primitive 1: Estimand Family Declaration

The system pools numbers without verifying they are the same *kind* of number.

### Missing Primitive 2: Precision Source Enforcement

The system accepts records without SE/CI/p+N and fabricates precision (SE=1.0).

---

## Status of PIPELINE_AUDIT.md Issues (Previous Audit)

| Issue | Status | Why Still Open |
|---|---|---|
| ISSUE-1: Dual edge ID conventions | ✅ FIXED | DB now has 137 ER_* definitions (EDGE_* removed from seeds) |
| ISSUE-2: No DB persistence protection | ❌ UNFIXED | No `db_guard.py`, no backup, WAL deletion caused data loss |
| ISSUE-3: LLM produces deficient evidence | ❌ UNFIXED | 0% TB group completion, N=0, 70 empty columns |
| ISSUE-4: CSV template too narrow | ❌ UNFIXED | Template not updated to v2 |
| ISSUE-5: Effect size units not standardized | ❌ UNFIXED | No unit validation at import |
| ISSUE-6: 5/7 data families never loaded | ❌ UNFIXED | Only F1 (edge evidence) populated |
| ISSUE-7: No extraction completeness check | ❌ UNFIXED | No completeness monitoring |
| ISSUE-8: Three parallel write paths | ❌ UNFIXED | No unified validation |
| INV-1: Missingness policy | ❌ UNFIXED | No reject-on-missing enforcement |
| INV-2: UNASSIGNED rejection | ❌ UNFIXED | 11 UNASSIGNED rows in DB |
| INV-3: DB referential integrity | ❌ UNFIXED | No FK enforcement, EDGE_CORTISOL_DEPRESSION orphan |
| INV-4: Semantic uniqueness | ❌ UNFIXED | 12 duplicate betas for same edge |
| INV-5: Precision cascade contract | ❌ UNFIXED | Records with SE=None enter DB freely |

**Score: 1/13 addressed (8%).**

---

## Recommended Fix Plan

> **STRICT RULE**: Do not run more extractions until the TB→P2 reject gates
> exist and SE=1.0 fallback is removed or quarantined. Otherwise every new
> run contaminates the DB and makes debugging harder.

### Tier 1: Hard Gates (stop garbage at TB→P2 boundary)

Implement `qa_gate.py` with 5 explicit reject gates:

| Gate | Name | Rule | Reject Reason |
|------|------|------|---------------|
| **GATE-QA-1** | PrecisionSourceRequired | Reject unless: `se` OR (`ci_lower` & `ci_upper`) OR (`p_value` & `n`) | `"NO_PRECISION_SOURCE"` |
| **GATE-QA-2** | EdgeIdExists | Reject unless `edge_relation_id` exists in `edge_relations_definitions_v1` | `"EDGE_ID_NOT_IN_DEFINITIONS"` |
| **GATE-QA-3** | EstimandDeclaredAndAllowed | Reject unless `metric_type ∈ {SMD, LOG_OR, BETA_STD, BETA_UNSTD, R, HR_LOG}` | `"ESTIMAND_UNDECLARED"` |
| **GATE-QA-4** | EvidenceKeyUniqueness | For a given EvidenceKey, keep only one "primary" record; others labeled secondary or discarded | `"DUPLICATE_EVIDENCE_KEY"` |
| **GATE-QA-5** | StudyContextRequired | Reject if no `paper_id` or no `study_id` (or deterministic study_fingerprint) | `"MISSING_STUDY_CONTEXT"` |

### Tier 2: Remove Poison Defaults

- Delete/disable `SE_DERIVATION_FALLBACK = 1.0` in config
- Replace with: record **rejected** (hard fail) or **quarantined** (stored outside `edge_evidence_v1`, not pooled)
- Quarantine table: `edge_evidence_quarantine_v1` — same schema, with `reject_reason` and `reject_gate` columns

### Tier 3: DB Integrity

Add post-P4 integrity check (in P7 or post-pipeline):
- `edges_v1.k > 0`
- `∃ edge_evidence_v1 WHERE edge_relation_id = edges_v1.edge_relation_id`
- `edges_v1.edge_relation_id ∈ edge_relations_definitions_v1`
- If any fail → rollback compilation

### Tier 4: Previously Identified Fixes

5. **Fix AG05 prompt for grouping** — Move grouping_id instruction to the TOP of the prompt. Reduce label types from 40 to the 10 most important.
6. **Implement semantic dedup** (INV-4, requires EvidenceKey) — Prevent 12 betas for the same concept.
7. **Store se_derivation_tag** — Add column to edge_evidence_v1, propagate from P3.
8. **Add DB guards** — Implement db_guard.py to prevent WAL deletion.
9. **Populate contextual columns** — study_design, cancer_type, instrument_id, rob_overall, pub_year.
10. **Implement extraction completeness checks** — Per-paper family coverage tracking.
11. **Standardize effect size units** — Validate at import, convert mean_diff → SMD when SD available.

---

## Success Metrics

**"What does 'fixed' mean?"**  Define target KPIs for the next extraction run:

| KPI | Current | Initial Target | Full Target |
|-----|---------|----------------|-------------|
| TB group completion (SE/CI/p+N paired with effect size) | 0% | ≥ 60% | ≥ 80% |
| Evidence rows with real precision source (SE/CI/p+N) | 0/31 (0%) | ≥ 70% | ≥ 90% |
| UNASSIGNED rows written to DB | 11 | 0 | 0 |
| Compiled edges with k≥2 and finite SE_eff | 0/3 | ≥ 1 | all |
| Evidence rows with study_design, pub_year, rob_overall coverage | 0% | ≥ 50% | ≥ 80% |
| Records meeting DER criteria (all 6 checks pass) | 0/31 | ≥ 50% | ≥ 90% |
| Quarantined records (rejected with reason, not silently dropped) | N/A | tracked | tracked |

Without success metrics, you can "fix" code and still not fix science.
