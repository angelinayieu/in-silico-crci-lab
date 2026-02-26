# Rigorous Review of CHERRIER_AUDIT_REMEDIATION.md

**Date:** 2026-02-26
**Reviewer:** Automated code/data verification
**Document reviewed:** `docs/CHERRIER_AUDIT_REMEDIATION.md`
**Verdict:** Document contains **valid code-level diagnoses** but **materially incorrect data analysis** and several **factual errors** in line numbers, math, and DB values.

---

## Severity Summary

| Category | Rating | Detail |
|----------|--------|--------|
| Code issue identification | ✅ MOSTLY CORRECT | 5 of 6 code issues verified in source |
| Database values cited | ❌ WRONG | None of the cited beta/SE/pooled values match actual DB |
| Math verification table | ❌ WRONG | SE_d values are systematically ~2–7% too high |
| Line numbers in code refs | ⚠️ PARTIALLY WRONG | Several line numbers are off by 5–50 lines |
| Fix plans (proposed code) | ⚠️ INCOMPLETE | Fix 5 has a critical gap (L1 key mismatch) |
| Remediation priority order | ✅ CORRECT | Dependency chain is sound |

---

## CRITICAL ERROR 1: Database Values Are Fabricated

The document claims the DB contains 6 F-statistic rows with specific beta/SE values. **The actual database contains 9 rows with completely different values.**

### What the document claims (§2, Table):
| Outcome | d (claimed) | SE (claimed) | Edge (claimed) |
|---------|------------|-------------|----------------|
| Block Design | 0.8990 | 0.4072 | ER_COGACTIVITY_WORKMEM |
| Mental Rotation | 1.0194 | 0.4152 | ER_COGACTIVITY_WORKMEM |
| CVLT Total | 1.0117 | 0.4147 | ER_COGACTIVITY_WORKMEM |
| CVLT Delay | 1.6176 | 0.4685 | ER_COGACTIVITY_WORKMEM |
| Route Learning | 0.7970 | 0.4001 | ER_COGACTIVITY_WORKMEM |
| Group×Time | 0.7741 | 0.3984 | ER_COGACTIVITY_WORKMEM |

### What the database actually contains:

**4 manual CSV import rows** (entered_by=`manual_csv_import_v2`):
| LER ID suffix | Edge | Beta | SE | N | Design |
|---------------|------|------|----|---|--------|
| WORKMEM_a88c8a | ER_COGACTIVITY_WORKMEM | 0.7670 | 0.3883 | 28 | RCT |
| ATTN_ba9280 | ER_COGACTIVITY_ATTN | 0.5728 | 0.3786 | 28 | RCT |
| COGCOMPLAINTS_d838 | ER_COGACTIVITY_COGCOMPLAINTS | -0.5146 | 0.3786 | 28 | RCT |
| EPIMEM_ce589f | ER_COGACTIVITY_EPIMEM | 0.2427 | 0.3689 | 28 | RCT |

**5 automated extraction rows** (entered_by=`extraction_pipeline:RUN_20260226T084244`):
| LER ID suffix | Edge | Beta | SE | N | Design |
|---------------|------|------|----|---|--------|
| afd29608 | ER_COGACTIVITY_WORKMEM | -0.2656 | 0.1121 | 0 | None |
| cb79bdec | ER_COGACTIVITY_WORKMEM | -0.4866 | 0.1830 | 0 | None |
| 42ecfe89 | ER_COGACTIVITY_WORKMEM | -0.4829 | 0.1830 | 0 | None |
| 23e3adc9 | ER_COGACTIVITY_WORKMEM | -0.7721 | 0.1870 | 0 | None |
| ea298427 | ER_COGACTIVITY_WORKMEM | -0.3804 | 0.1820 | 0 | None |

### Key discrepancies:
1. **Row count**: 9 actual vs 6 claimed
2. **No F→d conversions visible**: The automated betas are negative (impossible from `d = 2√(F/N)`), suggesting F→d conversion did NOT occur — the LLM likely extracted regression coefficients directly
3. **Manual rows ARE correctly distributed** across 4 edges (not collapsed)
4. **Document's "all on WORKMEM" claim**: True for the 5 automated rows, false for the 4 manual rows

### Actual pooled edge (edges_v1):
- `ER_COGACTIVITY_WORKMEM`: beta_mean = **-0.4431**, beta_se = **0.6041**, total_n = **0**
- Document claims: beta = 0.9997, SE = **1.2112** — both wrong

### study_registry_v1 actual:
- study_design = **"RCT"**, study_subtype = **"RCT_cognitive"**
- Document claims study_design is NULL → "unclassified" — **WRONG for study_registry**
- However, the 5 automated evidence rows DO have study_design = None (correct observation)

---

## CRITICAL ERROR 2: SE_d Math Is Wrong

The document's §2 table lists SE_d values that don't match the formula `SE_d = √(4/N + d²/(2(N-2)))` with N=28.

### Verified computation (Python, N=28):

| Outcome | F | d (correct) | SE (correct) | SE (doc claims) | Error |
|---------|---|-------------|-------------|-----------------|-------|
| Block Design | 5.66 | 0.8992 | **0.3980** | 0.4072 | +2.3% |
| Mental Rotation | 7.28 | 1.0198 | **0.4036** | 0.4152 | +2.9% |
| CVLT Total | 7.17 | 1.0121 | **0.4032** | 0.4147 | +2.9% |
| CVLT Delay | 18.33 | 1.6182 | **0.4396** | 0.4685 | +6.6% |
| Route Learning | 4.45 | 0.7973 | **0.3938** | 0.4001 | +1.6% |
| Group×Time | 4.197 | 0.7743 | **0.3929** | 0.3984 | +1.4% |

The IVW pooled estimates with **correct** SEs:
- β̂_IVW = 0.9997 (matches doc)
- SE_IVW = 0.1651 (matches doc)

The IVW results happen to match because the relative ordering/weights are similar, but the individual SE values used to compute them are all wrong in the document.

### Appendix A math error:
The document writes: `√0.1584 = 0.3980 ≈ 0.4072`

This is mathematically false. 0.3980 ≠ 0.4072 (2.3% difference). The `≈` symbol is misleading — these are not approximately equal values.

---

## CRITICAL ERROR 3: Fix 5 Has a Gap — L1 Key Mismatch

The document's Fix 5 proposes propagating `study_design = "rct"` (from meta.json lowercase) through the pipeline. But **this wouldn't fix the L1 penalty** because `"rct"` is NOT a valid key in `config.DESIGN_MULTIPLIERS`.

### Actual config.DESIGN_MULTIPLIERS keys:
```python
DESIGN_MULTIPLIERS = {
    "large_rct": 1.0,
    "small_rct_default": 1.25,
    "well_adjusted_cohort": 1.5,
    "unadjusted_longitudinal": 2.0,
    "cross_sectional_adjusted": 2.5,
    "cross_sectional_unadjusted": 3.0,
    "animal_in_vivo": 4.0,
    "in_vitro_mechanistic": 5.0,
    "expert_opinion": 6.0,
}
```

The key `"rct"` is absent. The L1 function (`layer_1_study_design()`) in layers.py checks:
1. `study_design == "large_rct"` → m=1.0
2. `study_design in ("small_rct", "small_rct_default")` → interpolation
3. `study_design in config.DESIGN_MULTIPLIERS` → lookup
4. **Fall-through → DESIGN_MULTIPLIER_DEFAULT = 3.0**

So propagating `"rct"` would STILL result in `m_design = 3.0` because `"rct"` doesn't match any of the above checks.

### Missing fix step:
Fix 5 needs an additional step: **normalize generic design labels to config-compatible keys**:
```python
def _normalize_study_design(raw: str, n_total: int | None) -> str:
    """Map generic labels to config-compatible keys."""
    mapping = {
        "rct": lambda n: "large_rct" if n and n > 200 else "small_rct",
        "cohort": lambda n: "well_adjusted_cohort",
        "cross_sectional": lambda n: "cross_sectional_adjusted",
        "longitudinal": lambda n: "unadjusted_longitudinal",
    }
    normalizer = mapping.get(raw.lower())
    if normalizer:
        return normalizer(n_total)
    return raw
```

---

## ERROR 4: Line Number Inaccuracies

| Document ref | Claimed location | Actual location | Impact |
|-------------|-----------------|-----------------|--------|
| concept_engine.py "lines 265–268" | Fallback logic | Lines 267–268 (`if best_edge is None...return target_edges[0]`) | Minor (off by 2) |
| scale_harmonizer.py "lines 445–463" | F-stat branch | Lines ~448–468 (F_STATISTIC branch) | Minor (off by 3) |
| layers.py "lines 44–99" | L1 design dict | Lines 37–107 (entire L1 function) | Misleading — no hardcoded dict, uses config |
| layers.py "lines 75–85" | Design multiplier dict literal | Does NOT exist — actual code uses `config.DESIGN_MULTIPLIERS` | **Wrong** — doc shows a dict literal that's not in the code |
| double_counting.py "line 515" | `total_n = sum(...)` | **Line 562** | Off by 47 lines |
| p3_runner.py "lines 67–72" | p0_study_design fallback | Lines 65–70 | Minor (off by 2) |
| p3_runner.py "lines 124–130" | unclassified fallback check | **Line 192** | Off by 62 lines |
| p2_runner.py "lines 385–396" | n_effect assignment | Line 434 | Off by 39–48 lines |

---

## ERROR 5: Code Snippets Don't Match Actual Code

### layers.py L1 dict representation
The document shows:
```python
design_multipliers = {
    "rct": 1.0,
    "cohort": 1.3,
    "case_control": 1.5,
    "cross_sectional": 1.8,
    "unclassified": config.DESIGN_MULTIPLIER_DEFAULT,  # 3.0
}
```

Actual code uses `config.DESIGN_MULTIPLIERS` (different keys: `large_rct`, `well_adjusted_cohort`, etc.) with a fall-through to `DESIGN_MULTIPLIER_DEFAULT` for unrecognized keys. The document's simplified dict is misleading about what keys the code actually recognizes.

### concept_engine.py _match_from_target_edges
The document shows a function signature:
```python
def _match_from_target_edges(self, span_text: str, target_edges: list[str]) -> str:
```

Actual code: The function is `_match_from_target_edges(self, span: SpanLabel, target_edges: list[str]) -> str | None` — it takes a `SpanLabel` object, not a `span_text` string. The actual matching uses `span.source_section` and `span.value`, not a single `span_text` parameter.

### double_counting.py _build_resolved
The document implies it's a method (with `self`). Actual code: it's a module-level function, not a method.

---

## ERROR 6: Appendix A SE Chain Computation

The "full P3 formula worked example" in Appendix A has errors cascading from the wrong SE_raw starting value (0.4072 instead of 0.3980). The chain then produces:

Document's computation:
```
SE_product = 0.4072 × 3.0 × 1.0 × 1.3 × 1.25 = 1.9851
```

But the actual P3-8 formula (verified in se_eff_assembly.py lines 220-231):
```
se_product = SE_raw × m_design × m_scale × m_grade
```
where m_scale comes from L4 (scale validation) and the 1.3 in the doc is labeled "L4 scale validation = general_population". Looking at the actual config:

```python
# config.py — L4 scale validation multipliers
SCALE_VALIDATION_MULTIPLIERS = {
    "validated_cancer": 1.0,
    "validated_general": 1.15,
    "general_population": 1.3,
    ...
}
```

The 1.3 for `general_population` is correct. But the SE_raw starting value is wrong, and the document also omits the formula multiplication factor correctly: it should be `m_design × m_scale × m_grade = 3.0 × 1.3 × 1.25 = 4.875` which is correct in the doc.

The cascade with the CORRECT SE_raw:
```
SE_product = 0.3980 × 4.875 = 1.9403    (doc says 1.9851)
SE_product² = 3.7648                      (doc says 3.9406)
+ σ²_struct = 3.7648 + 0.25 = 4.0148    (doc says 4.1906)
numerator = √4.0148 = 2.0037             (doc says 2.0471)
/ denominator (0.85) = 2.3573            (doc says 2.4084)
```

2.3573 vs 2.4084 — ~2% difference in the final SE_eff. Not huge, but the specific numbers cited are wrong.

---

## WHAT THE DOCUMENT GETS RIGHT

### Code-level issue identification (5 of 6 confirmed):

1. **ConceptEngine single-edge collapse** — ✅ CONFIRMED
   - 5 of 5 automated extraction rows map to ER_COGACTIVITY_WORKMEM
   - The `target_edges[0]` fallback at line 267 is real
   - Root cause (keyword matching fails on numeric spans) is correctly diagnosed

2. **Within-study DCR gap** — ✅ CONFIRMED
   - `double_counting.py` only handles MA-vs-primary overlap
   - No within-study correlated outcome detection exists
   - The concern is legitimate (though for current data, the 5 automated rows on WORKMEM wouldn't trigger it since they're already on the same edge)

3. **F-stat df₁ handling** — ✅ CONFIRMED
   - `scale_harmonizer.py` does not parse degrees of freedom
   - The N=28 hardcode fallback is real (line ~454)
   - However, the actual automated extraction may not even be producing F→d conversions (betas are negative)

4. **Interaction effect pooling** — ✅ CONFIRMED (as a code gap)
   - No `stat_type_detail` field exists in `HarmonizedClaim`
   - `evidence_grouper.py` groups only by `edge_relation_id` (line 71)
   - No mechanism to segregate interaction from main effects

5. **study_design propagation** — ✅ PARTIALLY CONFIRMED
   - `paper_type_classifier.py` DOES NOT return `study_design` (confirmed: returns only `paper_subtype`, `confidence`, `reasoning`)
   - The 5 automated evidence rows have `study_design = None`
   - BUT: `study_registry_v1` already has `study_design = "RCT"` (from either the manual import or the pipeline's meta.json reading)
   - The document is wrong that study_registry has NULL — it has "RCT"

6. **n_effect/total_n propagation** — ✅ CONFIRMED
   - Automated evidence rows have `N_effect = 0`
   - `scale_harmonizer.py` line 487: writes `n_effect=routed.value.n` (the original, possibly None value) instead of the computed `n` used in the formula
   - `double_counting.py` line 562: `total_n = sum(c.n_effect for c in claims if c.n_effect is not None)` → 0 when all None
   - `edges_v1` shows `total_n = 0` — confirmed

### Systemic failure analysis — ✅ SOUND
The 5 systemic failure categories are well-identified:
1. No boundary validation — confirmed
2. Metadata doesn't flow with data — confirmed
3. Silent fallbacks — confirmed
4. No integration testing — confirmed
5. Extraction lacks outcome-level granularity — confirmed

### Fix plan structure — ✅ WELL-DESIGNED
- Priority ordering is logical
- Dependency graph is correct
- Proposed boundary gates (BG-01 through BG-07) are appropriate
- Integration test approach is sound

---

## ISSUES MISSED BY THE DOCUMENT

1. **L1 key mismatch** (described above): Even after Fix 5, `"rct"` won't match `config.DESIGN_MULTIPLIERS` keys

2. **Multiple extraction runs mixing**: The DB has data from BOTH manual and automated extraction, all active. The document doesn't address deduplication between manual and automated entries for the same paper.

3. **Negative beta values**: The 5 automated rows have negative betas, which is impossible from `d = 2√(F/N)`. This suggests the automated extraction did NOT do F→d conversion at all — the P1 LLM may have extracted regression coefficients or standardized mean differences directly. The document's entire premise ("6 F-statistics were converted to Cohen's d") may be wrong for the automated run.

4. **Manual entries use different study_id format**: Manual CSV rows use `STUDY_CHERRIER_2013` while `manual_cherrier_entry.py` creates `CHERRIER2013` — these are different study_ids, so the manual script's entries may not even be in the current query results.

5. **The actual SE inflation mechanism may differ**: Since the automated extraction produced different values than F→d conversion, the SE inflation chain described in §3 and Appendix A is hypothetical, not observed.

---

## RECOMMENDATIONS

1. **Correct the data section**: Replace the fabricated table with actual DB values from both manual and automated extraction rows
2. **Fix the math**: Recompute all SE_d values using the correct formula (my verified values above)
3. **Add L1 key normalization to Fix 5**: The `_normalize_study_design()` function gap
4. **Clarify which extraction run the analysis applies to**: Manual vs automated, and note that findings differ
5. **Investigate what the automated pipeline actually extracted**: The negative betas suggest it's not doing F→d conversion
6. **Address multi-run deduplication**: How should manual + automated rows coexist?

---

## APPENDIX: Verification Commands

All data was verified by:
1. Direct Python computation of F→d and SE formulas
2. SQLite queries against `crci_dev.db` (`edge_evidence_v1`, `edges_v1`, `study_registry_v1`)
3. Source code review of all referenced files with line-by-line comparison
