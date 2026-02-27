# Extraction Log

Cumulative audit trail for all evidence extractions into the CRCI system.

**Purpose:** Traceable record of every value extracted, its exact source location,
and every judgment call made during extraction. Enables third-party verification.

**Format:** Each extraction has a unique ID, ISO timestamp, source hash, and
categorized decisions with risk levels. Most recent extraction at top.

---

## EXT-2026-0004 — Adam et al. 2017

### Extraction Metadata

| Field | Value |
|-------|-------|
| **Extraction ID** | `EXT-2026-0004` |
| **Timestamp** | 2026-02-27T12:00:00Z |
| **Extractor** | Claude (automated) |
| **Reviewer** | — (pending human review) |
| **Status** | `EXTRACTED` → awaiting `VERIFIED` |

### Source Document

| Field | Value |
|-------|-------|
| **Citation** | Adam EK, Quinn ME, Tavernier R, McQuillan MT, Dahlke KA, Gilbert KE (2017) Psychoneuroendocrinology, 83, 25-41 |
| **DOI** | `10.1016/j.psyneuen.2017.05.018` |
| **PMID** | 28578301 |
| **PDF Location** | `data/manual_uploads/pdfs/nihms881368.pdf` |
| **PDF SHA-256** | *(to be computed on verification)* |
| **Pages Extracted** | 1-40 (full text including supplemental tables) |

### Study Characteristics

| Field | Value |
|-------|-------|
| **Design** | Systematic review + meta-analysis |
| **Sample** | k=80 studies, 179 associations, N=36,823 (26,167 unique) |
| **Population** | Mixed (general population, clinical, cancer); predominantly adult; 68.5% female across studies |
| **Exposure** | Diurnal cortisol slope (DCS) — flatter slope = worse HPA regulation |
| **Outcomes** | 12 health outcome subtypes across mental and physical health |
| **Extraction Mode** | `STANDARD` (meta-analysis, not cancer-specific intervention) |

### Edges Added to EDGE_REGISTRY

*2 new edges (registry total: 141 → 143)*

| Edge ID | Source Node | Target Node | Sign | Type | Pathway | Basis |
|---------|-------------|-------------|------|------|---------|-------|
| `ER_HPA_FATIGUE` | NODE_PATH_HPA | NODE_SYM_FATIGUE | positive | associational | PW_M03_HPA | Meta-analytic r=.167 (k=8) |
| `ER_HPA_OIC` | NODE_PATH_HPA | NODE_PATH_OIC | positive | associational | PW_M03_HPA | Meta-analytic r=.288 (k=14) |

### Evidence Values Extracted

#### edge_evidence_template.csv (5 rows)

| Row | Edge ID | beta_raw (d) | se_raw | r_original | k | N | p | CI (r) | Source Location | Derivation |
|-----|---------|-------------|--------|------------|---|---|---|--------|-----------------|------------|
| 1 | ER_CORTISOL_HPA | 0.2972 | 0.0374 | .147 | 179 | 36823 | <.001 | .112–.183 | Table 2 / §3.1 Overall | d=2r/√(1-r²); SE via delta method |
| 2 | ER_HPA_OIC | 0.6015 | 0.2167 | .288 | 14 | ~1100 | .005 | .091–.464 | Table 2 / §3.3 Immune/inflammatory | Largest subgroup effect |
| 3 | ER_HPA_DEPRESSION | 0.2132 | 0.0612 | .106 | 52 | ~8000 | <.001 | .047–.165 | Table 2 / §3.2 Depression | Most common outcome (29.1% of findings) |
| 4 | ER_HPA_FATIGUE | 0.3388 | 0.1240 | .167 | 8 | ~800 | .006 | .048–.281 | Table 2 / §3.2 Fatigue | Includes cancer-related fatigue studies |
| 5 | ER_HPA_ANXIETY | -0.1686 | 0.0923 | -.084 | 15 | ~2000 | .066 | -.173–.006 | Table 2 / §3.2 Anxiety | **NOT SIGNIFICANT** — CI crosses zero |

**Conversion formula:** `d = 2r / √(1 - r²)` — standard r→d transformation.
**SE conversion:** `SE(d) = SE(r) × 2 / (1 - r²)^(3/2)` — delta method.
**SE(r) derivation:** From 95% CI: `SE(r) = (CI_upper - CI_lower) / (2 × 1.96)`

#### Publication Bias Assessment

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Egger's regression | b=1.22, t(82)=3.05, p=.002 | Significant funnel asymmetry |
| Trim-and-fill | 0 missing studies | No adjustment needed |
| Adjusted estimate | r=.147, CI .111–.183 | Identical to original |
| Conclusion | Small bias with minimal impact | Results robust |

### Extraction Decisions

| # | Category | Risk | Decision | Rationale | Spec Reference |
|---|----------|------|----------|-----------|----------------|
| D1 | `[EFFECT_SIZE]` | LOW | Converted r→d for all subgroups | All effects reported as Pearson r. Converted using d=2r/√(1-r²) for compatibility with cohens_d pipeline. SE propagated via delta method. | SYS_EX §TB-1 |
| D2 | `[CONSTRUCT]` | LOW | DCS→overall health mapped to ER_CORTISOL_HPA | Overall pooled r=.147 represents diurnal cortisol slope ↔ general health. Maps to the cortisol→HPA dysregulation edge as it reflects aggregate HPA function. | NODE_REGISTRY |
| D3 | `[CONSTRUCT]` | LOW | DCS→inflammation mapped to ER_HPA_OIC | Inflammatory markers (IL-6, CRP, TNF-α) cluster as NODE_PATH_OIC (neuroinflammation pathway). Largest effect in the meta-analysis (r=.288). | EDGE_REGISTRY |
| D4 | `[SIGN_CONV]` | **MEDIUM** | Anxiety result entered despite non-significance | r=-.084, CI -.173 to .006, p=.066. NOT SIGNIFICANT. Entered because anxiety is key CRCI construct. Negative d means flatter DCS→LESS anxiety (unexpected direction). Flagged in confidence_note. Interpret with caution. | SYS_EX §P3-G1 |
| D5 | `[DUPLICATE]` | LOW | DCS→Cancer not entered separately | r=.231 (k=9) for cancer outcomes. Would duplicate ER_CORTISOL_HPA (same edge_id). Cancer is subsumed in overall estimate. Noted in meta.json effect_size_notes. | SYS_EX §P3-G2 |
| D6 | `[CONSTRUCT]` | LOW | DCS→Fatigue mapped to new ER_HPA_FATIGUE | r=.167 (k=8). Created new edge. Includes cancer-related fatigue studies (e.g., Bower 2005). Directly relevant to CRCI fatigue pathway. | EDGE_REGISTRY |
| D7 | `[MISSING_DATA]` | LOW | N estimated for subgroups | Total N only reported for overall (36,823). Subgroup N estimated from k × typical study size. Documented in confidence_note. | — |
| D8 | `[BIAS_ADJ]` | **MEDIUM** | High heterogeneity (I²=83.23%) | Very high heterogeneity in overall estimate. Random effects model appropriate. Some subgroups have smaller I². Cross-sectional=91.1% of findings limits causal inference. | SYS_EX §TB-5 |
| D9 | `[CONSTRUCT]` | LOW | Excluded non-mapped outcomes | Obesity/BMI (r=.101), cardiovascular (r=.098), PTSD (r=.138), externalizing behavior (r=.273), mortality (HR=2.40) — no matching edges in registry. Could be added as future edges. | NODE_REGISTRY |
| D10 | `[BIAS_ADJ]` | LOW | Publication bias acknowledged, no adjustment | Egger p=.002 (significant) but trim-and-fill found 0 missing studies. Adjusted estimate identical. Documented in confidence_note. | SYS_EX §TB-5 |

### Verification Checklist

- [x] All r→d conversions verified by hand calculation
- [x] 95% CI bounds consistent with reported p-values
- [x] Edge IDs match EDGE_REGISTRY.csv (including 2 newly created)
- [x] Instrument ID (INST_CORTISOL_SLOPE) exists in INSTRUMENT_REGISTRY.csv
- [x] Non-significant anxiety result flagged in confidence_note
- [x] meta.json created with full study details
- [x] DB load successful: 5 new evidence rows, 5 new compiled edges
- [ ] Human review pending

---

## EXT-2026-0003 — Northey et al. 2018

### Extraction Metadata

| Field | Value |
|-------|-------|
| **Extraction ID** | `EXT-2026-0003` |
| **Timestamp** | 2026-02-26T12:00:00Z |
| **Extractor** | Claude (automated) |
| **Reviewer** | — (pending human review) |
| **Status** | `EXTRACTED` → awaiting `VERIFIED` |

### Source Document

| Field | Value |
|-------|-------|
| **Citation** | Northey JM, et al. (2018) J Sci Med Sport, in press |
| **DOI** | `10.1016/j.jsams.2018.11.026` |
| **Trial Registration** | — (not stated in text) |
| **PDF Location** | `data/manual_uploads/pdfs/10.1016_j.jsams.2018.11.026.meta.json` |
| **PDF SHA-256** | *(to be computed on verification)* |
| **Pages Extracted** | 1-6 (full text) |

### Study Characteristics

| Field | Value |
|-------|-------|
| **Design** | Pilot RCT, 3-arm parallel group |
| **Sample** | n=17 (HIIT=6, MOD=5, CON=6) |
| **Population** | Female breast cancer survivors, ≤24mo post-diagnosis, age 50-75, excluded if ≥30 min MVPA 5+ days/wk |
| **Intervention** | HIIT: 30s intervals × 4-7 on cycle ergometer 3×/wk 12 wks; MOD: 55-65% peak power continuous 20 min 3×/wk 12 wks |
| **Control** | Wait-list (maintain current lifestyle) |
| **Extraction Mode** | `DEEP` (RCT + breast cancer + cognitive primary) |

### Three-Arm Design Resolution

| Comparison | Usage | Rationale |
|------------|-------|-----------|
| **HIIT vs CON** | Primary evidence rows | Strongest effects; maps to exercise intervention |
| **MOD vs CON** | Secondary evidence rows | Dose-response; lower intensity comparison |
| **HIIT vs MOD** | NOT entered | Same source node (physical activity), intensity comparison only |

### Edges Added to EDGE_REGISTRY

*2 new edges (registry total: 140 → 142)*

| Edge ID | Source Node | Target Node | Sign | Type | Pathway | Basis |
|---------|-------------|-------------|------|------|---------|-------|
| `ER_ACTIVITY_WORKMEM` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_WORK_MEM | positive | causal | PW_M04_NEUROPLASTICITY | Pilot RCT d=0.81 (NS) |
| `ER_ACTIVITY_EXEC` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_EXEC_PLANNING | positive | causal | PW_M04_NEUROPLASTICITY | Pilot RCT d=0.75 (NS) |

### Instruments Added to INSTRUMENT_REGISTRY

*4 new instruments (registry total: 63 → 67)*

| Instrument ID | Name | Maps To | Type | Source |
|---------------|------|---------|------|--------|
| `INST_ISL_DR` | International Shopping List — Delayed Recall | NODE_COG_EPISODIC_MEM | CogState | Lim 2013 |
| `INST_GROTON_MAZE` | Groton Maze Learning Task | NODE_COG_EXEC_PLANNING | CogState | Lim 2013 |
| `INST_ONEBACK` | CogState One-Back Task | NODE_COG_WORK_MEM | CogState | Lim 2013 |
| `INST_VO2PEAK` | Peak Oxygen Uptake (VO2peak) | NODE_SYM_DECONDITIONING | Clinician | ACSM 2017 |

### Existing Edges Receiving Additional Evidence

| Edge ID | Previous Evidence | New Evidence | Combined Status |
|---------|-------------------|-------------|-----------------|
| `ER_ACTIVITY_EPIMEM` | Campbell 2017 (null, d≈-0.1) | Northey 2018 HIIT d=0.76 + MOD d=0.66 | Strengthened — moderate positive effects from two comparisons |

### Evidence Values Extracted

#### edge_evidence_template.csv (5 rows)

| Row | Edge ID | beta_raw | se_raw | effect_type | n | Comparison | Source Location | Derivation |
|-----|---------|----------|--------|-------------|---|------------|-----------------|------------|
| 1 | ER_ACTIVITY_EPIMEM | 0.76 | 0.60 | cohens_d | 12 | HIIT vs CON | Table 2, ISL-DR | d from pooled SD of LMM; SE≈√((n1+n2)/(n1·n2)+d²/(2(n1+n2))) |
| 2 | ER_ACTIVITY_EXEC | 0.75 | 0.60 | cohens_d | 12 | HIIT vs CON | Table 2, Groton Maze | d from pooled SD of LMM; lower errors=better→positive d |
| 3 | ER_ACTIVITY_WORKMEM | 0.81 | 0.60 | cohens_d | 12 | HIIT vs CON | Table 2, One-Back | d from pooled SD of LMM; higher accuracy=better |
| 4 | ER_ACTIVITY_EPIMEM | 0.66 | 0.62 | cohens_d | 11 | MOD vs CON | Table 2, ISL-DR | SE adjusted for n=5+6=11 |
| 5 | ER_ACTIVITY_EXEC | 0.20 | 0.61 | cohens_d | 11 | MOD vs CON | Table 2, Groton Maze | Small effect; secondary comparison |

**SE formula applied:** `SE(d) = √((n1+n2)/(n1×n2) + d²/(2(n1+n2)))` per standard approximation.  
For HIIT vs CON (n1=6, n2=6): SE ≈ √(0.333 + d²/24) ≈ 0.60  
For MOD vs CON (n1=5, n2=6): SE ≈ √(0.367 + d²/22) ≈ 0.61-0.62

#### population_norms_template.csv (4 rows)

| Row | Node ID | Instrument | Mean | SD | n | Source Location |
|-----|---------|-----------|------|-----|---|-----------------|
| 1 | NODE_COG_EPISODIC_MEM | INST_ISL_DR | 9.7 | 0.8 | 6 | Table 2, CON baseline ISL-DR |
| 2 | NODE_COG_EXEC_PLANNING | INST_GROTON_MAZE | 56.2 | 12.8 | 6 | Table 2, CON baseline Groton Maze errors |
| 3 | NODE_COG_WORK_MEM | INST_ONEBACK | 1.4 | 0.1 | 6 | Table 2, CON baseline One-Back accuracy |
| 4 | NODE_SYM_DECONDITIONING | INST_VO2PEAK | 20.9 | 3.1 | 6 | Table 2, CON baseline VO2peak |

#### context_priors_template.csv (2 rows)

| Row | Node ID | prior_mean_z | prior_sd_z | Source | Derivation |
|-----|---------|-------------|------------|--------|------------|
| 1 | NODE_SYM_DECONDITIONING | −0.68 | 0.5 | published norm | z=(20.9−24)/5; age-matched healthy women VO2peak ~24 ml/kg/min SD=5 (ACSM) |
| 2 | NODE_BEH_PHYSICAL_ACTIVITY | −1.0 | 0.5 | inclusion criteria | Excluded if ≥30 min MVPA 5+ days; sedentary-to-light baseline |

### Extraction Decisions

| # | Category | Risk | Decision | Rationale | Spec Reference |
|---|----------|------|----------|-----------|----------------|
| D1 | `[INST_MAP]` | LOW | CogState ISL-DR → `INST_ISL_DR` (new) | ISL-DR is distinct from HVLT-R (different battery). Added new instrument. CogState validated in cancer (Lim 2013). | §T1.instrument_id |
| D2 | `[INST_MAP]` | LOW | CogState Groton Maze → `INST_GROTON_MAZE` (new) | Groton Maze measures executive function (planning + spatial WM). Lower errors = better. Added new instrument. | §T1.instrument_id |
| D3 | `[INST_MAP]` | LOW | CogState One-Back → `INST_ONEBACK` (new) | One-Back WM task. Arcsine-transformed accuracy. Added new instrument. | §T1.instrument_id |
| D4 | `[INST_MAP]` | LOW | VO2peak → `INST_VO2PEAK` (new) | Maximal incremental cycle test. ml/kg/min. Added as deconditioning proxy. | §T1.instrument_id |
| D5 | `[SIGN_CONV]` | LOW | Groton Maze d positive despite lower_better | Error count is lower_better, but d=0.75 already oriented as benefit direction (HIIT improved more). Consistent with registry expected_sign=positive. | SYS_EX §TB-3 |
| D6 | `[CONSTRUCT]` | **MEDIUM** | VO2peak not entered as edge evidence | Significant HIIT effect (d=1.28, p=0.02) but `NODE_PATH_CEREBROVASCULAR` is EDGELESS PLACEHOLDER. VO2peak → fitness; captured in population_norms for NODE_SYM_DECONDITIONING. Future edge candidate. | NODE_REGISTRY |
| D7 | `[CONSTRUCT]` | **MEDIUM** | Cerebrovascular outcomes (MCA Vmean, CRV) excluded from edges | TCD-measured cerebral blood flow velocity. MCA Vmean d=0.86, CRV d=0.72 (HIIT vs CON). `NODE_PATH_CEREBROVASCULAR` has no parameterized edges in v1. Flagged for future PW_M11 edge creation. | Pathway Registry PW_M11 |
| D8 | `[CONSTRUCT]` | LOW | ISL learning trials (verbal learning) excluded | ISL 3-trial learning is verbal learning, not episodic memory. d=−0.39 (wrong direction). No `NODE_COG_VERBAL_LEARNING` exists. Domain overlaps with episodic memory. Entered ISL-DR only. | NODE_REGISTRY |
| D9 | `[DUPLICATE]` | LOW | HIIT vs MOD not entered | Same source node (physical activity). Intensity comparison adds no new edge information. Both arms already compared to CON. | SYS_EX §P3-G2 |
| D10 | `[BIAS_ADJ]` | **MEDIUM** | Pilot study: no statistical significance | All cognitive outcomes NS after FDR correction. Effect sizes are informative but imprecise (SE ≈ 0.60). Very small n (5-6/arm). Recommend interpreting with caution. | SYS_EX §TB-5 |
| D11 | `[MISSING_DATA]` | LOW | One-Back accuracy values unusual | Table 2 shows accuracy >1.0 (1.2, 1.3, 1.4). Likely arcsine-transformed (standard CogState practice). No raw proportion available. Entered as-is. | Table 2 |
| D12 | `[BIAS_ADJ]` | LOW | Unblinded participants | Participants knew group assignment (sealed envelope). Outcome assessors not described as blinded. Low risk for objective cognitive tests (CogState computerized), moderate for subjective. | Risk of bias table |

### Verification Checklist

- [ ] PDF SHA-256 hash computed and recorded
- [ ] All Cohen's d values verified against Table 2 (reported directly)
- [ ] SE derivation formula documented and verified
- [ ] Population norms verified against Table 2 CON baseline
- [ ] Context prior z-scores recalculated
- [ ] New instruments verified in INSTRUMENT_REGISTRY
- [ ] New edges verified in EDGE_REGISTRY
- [ ] Edge signs verified against expected_sign
- [ ] Human reviewer sign-off

### Supplementary Context (not entered as evidence)

| Data | Value | Source | Reason Not Entered |
|------|-------|--------|-------------------|
| VO2peak HIIT d=1.28 (p=0.02) | +19.3% increase | Table 2 | Entered as population_norm only; cerebrovascular edge placeholder |
| MCA Vmean HIIT d=0.86 | +3.5 cm/s | Table 2 | NODE_PATH_CEREBROVASCULAR edgeless placeholder |
| CRV HIIT d=0.72 | % mmHg⁻¹ | Table 2 | Same — cerebrovascular edgeless |
| ISL learning d=−0.39 | HIIT vs CON | Table 2 | Wrong direction; no verbal learning node |
| Adherence HIIT/MOD | 78.7%/79.4% | Results p.4 | Process metric |
| Heart rate response | 93.9% vs 84.1% HRmax | Results p.4 | Process metric confirming intensity |

### Files Created

| File | Rows | Location |
|------|------|----------|
| edge_evidence_template.csv | 5 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
| population_norms_template.csv | 4 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
| context_priors_template.csv | 2 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
| 10.1016_j.jsams.2018.11.026.meta.json | — | `data/manual_uploads/pdfs/` |

---

## EXT-2026-0002 — Campbell et al. 2017

### Extraction Metadata

| Field | Value |
|-------|-------|
| **Extraction ID** | `EXT-2026-0002` |
| **Timestamp** | 2026-02-25T14:30:00Z |
| **Extractor** | Claude (automated) |
| **Reviewer** | — (pending human review) |
| **Status** | `EXTRACTED` → awaiting `VERIFIED` |

### Source Document

| Field | Value |
|-------|-------|
| **Citation** | Campbell KL, et al. (2017) Psycho-Oncology 26:266-274 |
| **DOI** | `10.1002/pon.4370` |
| **Trial Registration** | NCT01296893 |
| **PDF Location** | `data/manual_uploads/pdfs/campbell2017.pdf` |
| **PDF SHA-256** | *(to be computed on verification)* |
| **Pages Extracted** | 1-9 (full text) |

### Study Characteristics

| Field | Value |
|-------|-------|
| **Design** | RCT, parallel group, assessor-blinded |
| **Sample** | n=19 (EX=10, CON=9) |
| **Population** | Postmenopausal breast cancer, stage I-IIIa, self-reported post-chemo cognitive decline, on aromatase inhibitor |
| **Intervention** | 24-week aerobic exercise (150 min/wk MVPA, 60-80% HRR) |
| **Control** | Usual care (wait-list) |
| **Extraction Mode** | `DEEP` (RCT + cancer + cognitive primary) |

### Edges Added to EDGE_REGISTRY

*4 new edges (registry total: 133 → 137)*

| Edge ID | Source Node | Target Node | Sign | Type | Pathway | Basis |
|---------|-------------|-------------|------|------|---------|-------|
| `ER_ACTIVITY_PROC_SPEED` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_PROC_SPEED | positive | causal | PW_M04_NEUROPLASTICITY | RCT p=0.01 |
| `ER_ACTIVITY_VERBAL_FLUENCY` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_VERBAL_FLUENCY | positive | causal | PW_M04_NEUROPLASTICITY | Trend p=0.15 |
| `ER_ACTIVITY_EPIMEM` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_EPISODIC_MEM | positive | causal | PW_M04_NEUROPLASTICITY | Null (for evidence accumulation) |
| `ER_ACTIVITY_COG_COMPLAINTS` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_SYM_COG_COMPLAINTS | negative | causal | PW_C2_FATIGUE | Null (negative = more activity → fewer complaints) |

### Evidence Values Extracted

#### edge_evidence_template.csv (4 rows)

| Row | Edge ID | beta_raw | se_raw | effect_type | n | Source Location | Derivation |
|-----|---------|----------|--------|-------------|---|-----------------|------------|
| 1 | ER_ACTIVITY_PROC_SPEED | −14.2 | 5.28 | mean_diff_seconds | 19 | Table 2, p.270, row "Trail Making Test A" | SE = (−3.9 − (−24.6)) / (2 × 1.96) |
| 2 | ER_ACTIVITY_VERBAL_FLUENCY | +3.0 | 2.14 | mean_diff_words | 19 | Table 2, p.270, row "Animal naming" | SE = (7.2 − (−1.2)) / (2 × 1.96) |
| 3 | ER_ACTIVITY_EPIMEM | −1.5 | 2.48 | mean_diff_raw_score | 19 | Table 2, p.270, row "HVLT-R Total Recall" | SE = (3.4 − (−6.2)) / (2 × 1.96) |
| 4 | ER_ACTIVITY_COG_COMPLAINTS | +3.9 | 5.33 | mean_diff_raw_score | 19 | Table 2, p.270, row "FACT-Cog PCI" | SE = (14.3 − (−6.6)) / (2 × 1.96) |

> **Scale harmonization note (2026-02-27):** These 4 `mean_diff` rows are auto-converted to Cohen's d at import time (Step 4c of `load_evidence_into_db.py`) using SD borrowed from `population_norms_v1`. The `effect_type_original` column preserves the original metric; `harmonized_beta` and `harmonized_scale` store the standardized values (d = mean_diff / SD_pooled). All evidence is uniform `cohens_d` scale in the DB.

**Formula applied:** `SE = (CI_upper − CI_lower) / (2 × 1.96)` per SYS_EXTRACTION §EX-P1.1

#### population_norms_template.csv (6 rows)

| Row | Node ID | Instrument | Mean | SD | n | Source Location |
|-----|---------|-----------|------|-----|---|-----------------|
| 1 | NODE_COG_PROC_SPEED | INST_TMT_B | 33.8 | 9.1 | 9 | Table 1, p.269, CON baseline "TMT-A (s)" |
| 2 | NODE_COG_EPISODIC_MEM | INST_HVLTR | 25.2 | 4.0 | 9 | Table 1, p.269, CON baseline "HVLT-R" |
| 3 | NODE_COG_VERBAL_FLUENCY | INST_COWAT | 18.0 | 4.3 | 9 | Table 1, p.269, CON baseline "Animal naming" |
| 4 | NODE_SYM_COG_COMPLAINTS | INST_FACTCOG_PCI | 28.8 | 14.8 | 9 | Table 1, p.269, CON baseline "FACT-Cog PCI" |
| 5 | NODE_SYM_DEPRESSION | INST_CESD | 15.4 | 2.4 | 9 | Table 1, p.269, CON baseline "CES-D" |
| 6 | NODE_SYM_FATIGUE | INST_FACIT_FATIGUE | 113.0 | 23.3 | 9 | Table 1, p.269, CON baseline "FACT-F TOI" |

#### context_priors_template.csv (4 rows)

| Row | Node ID | prior_mean_z | prior_sd_z | Source Location | Derivation |
|-----|---------|-------------|------------|-----------------|------------|
| 1 | NODE_SYM_COG_COMPLAINTS | −2.18 | 0.5 | Table 1 + Wagner 2009 | z = (28.8 − 61) / 14.8 |
| 2 | NODE_SYM_DEPRESSION | +0.93 | 0.5 | Table 1 + Radloff 1977 | z = (15.4 − 8) / 8 |
| 3 | NODE_BEH_PHYSICAL_ACTIVITY | −1.25 | 0.5 | p.268 "MVPA" + CDC norms | z = (11.2 − 22) / 8.6 |
| 4 | NODE_SYM_FATIGUE | −0.48 | 0.5 | Table 1 + FACIT norms | z = (113 − 120) / 15 |

### Extraction Decisions

Each decision is categorized and risk-rated. Categories:
- `[INST_MAP]` — Instrument/measure mapping to registry ID
- `[SIGN_CONV]` — Sign convention or directionality
- `[MISSING_DATA]` — Handling absent or ambiguous data
- `[BIAS_ADJ]` — Bias or quality adjustment
- `[CONSTRUCT]` — Construct validity or mapping
- `[DUPLICATE]` — Avoiding double-counting

| # | Category | Risk | Decision | Rationale | Spec Reference |
|---|----------|------|----------|-----------|----------------|
| D1 | `[INST_MAP]` | **MEDIUM** | TMT-A mapped to `INST_TMT_B` | TMT-A not in INSTRUMENT_REGISTRY; TMT-B is closest (same battery). **Action needed:** Add `INST_TMT_A` to registry. | §T1.instrument_id |
| D2 | `[SIGN_CONV]` | LOW | beta_raw = −14.2 preserved as negative | TMT-A is "lower = better" (seconds); negative diff = exercise benefit. Trust Boundary will orient using `scoring_direction`. | SYS_EX §TB-3 |
| D3 | `[INST_MAP]` | **MEDIUM** | FACT-F TOI mapped to `INST_FACIT_FATIGUE` | Paper reports TOI combined score (~160 max), not standard 13-item subscale (0-52). **Flagged for verification** — may need separate instrument ID. | §T1.instrument_id |
| D4 | `[DUPLICATE]` | LOW | FAS verbal fluency excluded | Animal naming + FAS both measure verbal fluency. Entered animal naming only (positive direction, larger effect). Avoids double-weighting. | SYS_EX §P3-G2 |
| D5 | `[INST_MAP]` | LOW | Animal naming mapped to `INST_COWAT` | COWAT includes semantic fluency (animals). Standard mapping. | §T1.instrument_id |
| D6 | `[CONSTRUCT]` | LOW | Null results entered | Null outcomes (HVLT, FACT-Cog) entered with wide SE. Rationale: null evidence constrains posterior. n=19 is severely underpowered. | SYS_ALGO §P4-1 |
| D7 | `[MISSING_DATA]` | LOW | fMRI excluded from edge evidence | fMRI G×T interaction (F=13.74, p=0.01) = neural efficiency, not DAG node. Captured in meta.json only. | SYS_EX §EX-P1.2 |
| D8 | `[BIAS_ADJ]` | LOW | Risk of bias: low-to-moderate | Objective assessors blinded. Main concern: n=19 underpowered. No downweight applied (RCT). | SYS_EX §TB-5 |

### Verification Checklist

- [ ] PDF SHA-256 hash computed and recorded
- [ ] All beta_raw values verified against Table 2 (p.270)
- [ ] All SE derivations recalculated from published CIs
- [ ] Population norms verified against Table 1 (p.269)
- [ ] Context prior z-scores recalculated
- [ ] Instrument mappings reviewed against INSTRUMENT_REGISTRY
- [ ] Edge signs verified against expected_sign in EDGE_REGISTRY
- [ ] Human reviewer sign-off

### Supplementary Context (not entered as evidence)

| Data | Value | Source | Reason Not Entered |
|------|-------|--------|-------------------|
| VO2peak change | +3.6 ml/kg/min (p<0.01) | Table 2, p.270 | Fitness outcome, not cognition |
| Adherence (supervised) | 88% | p.268 | Process metric |
| Adherence (home) | 87% | p.268 | Process metric |
| fMRI rMFG/rACC/lSFG | G×T F=13.74, p=0.01 | p.272 | Neural efficiency, not node-level |

### Files Created

| File | Rows | Location |
|------|------|----------|
| edge_evidence_template.csv | 4 | `data/manual_uploads/structured/10.1002_pon.4370/` |
| population_norms_template.csv | 6 | `data/manual_uploads/structured/10.1002_pon.4370/` |
| context_priors_template.csv | 4 | `data/manual_uploads/structured/10.1002_pon.4370/` |
| 10.1002_pon.4370.meta.json | — | `data/manual_uploads/pdfs/` |

### Files Created
- `data/manual_uploads/structured/10.1002_pon.4370/edge_evidence_template.csv` (4 rows)
- `data/manual_uploads/structured/10.1002_pon.4370/population_norms_template.csv` (6 rows)
- `data/manual_uploads/structured/10.1002_pon.4370/context_priors_template.csv` (4 rows)
- `data/manual_uploads/pdfs/10.1002_pon.4370.meta.json`

### Bugs Fixed This Session
- `manual_upload_watcher.py` `_get_required_columns()`: column names were `study_doi`, `beta`, `se` (mismatched with spec). Updated to `doi`, `beta_raw`, `se_raw` per `CRCI_Checklists_Templates_v2.0.md §T1`.
- `scripts/run_manual_import.py`: was passing directory to `import_structured_csv()` instead of individual file paths. Fixed to iterate `rglob("*.csv")`.
- Both Cherrier 2013 CSVs also updated to use spec-canonical column names after the fix.

---

## EXT-2026-0001 — Cherrier et al. 2013

### Extraction Metadata

| Field | Value |
|-------|-------|
| **Extraction ID** | `EXT-2026-0001` |
| **Timestamp** | 2026-02-25T10:00:00Z |
| **Extractor** | Claude (automated) |
| **Reviewer** | — (pending human review) |
| **Status** | `EXTRACTED` → awaiting `VERIFIED` |

### Source Document

| Field | Value |
|-------|-------|
| **Citation** | Cherrier MM, et al. (2013) Life Sciences 93:617-622 |
| **DOI** | `10.1016/j.lfs.2013.08.011` |
| **Trial Registration** | — (not registered) |
| **PDF Location** | `data/manual_uploads/pdfs/cherrier2013.pdf` |
| **PDF SHA-256** | *(to be computed on verification)* |
| **Pages Extracted** | 1-6 (full text) |

### Study Characteristics

| Field | Value |
|-------|-------|
| **Design** | RCT, parallel group, wait-list control |
| **Sample** | n=28 (TX=12, CON=16) |
| **Population** | Mixed cancer types, post-treatment, self-reported cognitive complaints |
| **Intervention** | 7-week group cognitive rehabilitation (memory strategies, attention training) |
| **Control** | Wait-list (usual care) |
| **Extraction Mode** | `DEEP` (RCT + cancer + cognitive primary) |

### Edges Added to EDGE_REGISTRY

*4 new edges (registry total: 129 → 133)*

| Edge ID | Source Node | Target Node | Sign | Type | Pathway | Basis |
|---------|-------------|-------------|------|------|---------|-------|
| `ER_COGACTIVITY_WORKMEM` | NODE_BEH_COG_ACTIVITY | NODE_COG_WORK_MEM | positive | causal | PW_M04_NEUROPLASTICITY | RCT d=0.79 |
| `ER_COGACTIVITY_ATTN` | NODE_BEH_COG_ACTIVITY | NODE_COG_ATTN_SUSTAINED | positive | causal | PW_M04_NEUROPLASTICITY | RCT d=0.59 |
| `ER_COGACTIVITY_COGCOMPLAINTS` | NODE_BEH_COG_ACTIVITY | NODE_SYM_COG_COMPLAINTS | negative | causal | PW_C2_FATIGUE | RCT d=0.53 |
| `ER_COGACTIVITY_EPIMEM` | NODE_BEH_COG_ACTIVITY | NODE_COG_EPISODIC_MEM | positive | causal | PW_M04_NEUROPLASTICITY | Trend d=0.25 |

### Evidence Values Extracted

#### edge_evidence_template.csv (4 rows)

| Row | Edge ID | beta_raw | se_raw | effect_type | n | Source Location | Derivation |
|-----|---------|----------|--------|-------------|---|-----------------|------------|
| 1 | ER_COGACTIVITY_WORKMEM | 0.79 | 0.38 | cohens_d | 28 | Table 1, p.619, row "Digit Span Backward" | d = (Δ_TX − Δ_CON) / SD_pooled; SE ≈ √(4/n) |
| 2 | ER_COGACTIVITY_ATTN | 0.59 | 0.38 | cohens_d | 28 | Table 1, p.619, row "Digit Span Total" | d = (Δ_TX − Δ_CON) / SD_pooled |
| 3 | ER_COGACTIVITY_COGCOMPLAINTS | −0.53 | 0.38 | cohens_d | 28 | Table 1, p.619, row "FACT-Cog PCI" | d negative because more cogactivity → fewer complaints |
| 4 | ER_COGACTIVITY_EPIMEM | 0.25 | 0.38 | cohens_d | 28 | Table 1, p.619, row "RAVLT Delayed" | d = (Δ_TX − Δ_CON) / SD_pooled |

**Formula applied:** `d = (M1 - M2) / SD_pooled`; `SE(d) ≈ √(2(1 + d²/8) × (n1+n2)/(n1×n2))` simplified to ~0.38 for n=28

#### population_norms_template.csv (3 rows)

| Row | Node ID | Instrument | Mean | SD | n | Source Location |
|-----|---------|-----------|------|-----|---|-----------------|
| 1 | NODE_SYM_COG_COMPLAINTS | INST_FACTCOG_PCI | 37.7 | 20.4 | 16 | Table 1, p.619, CON baseline "FACT-Cog PCI" |
| 2 | NODE_COG_PROC_SPEED | INST_STROOP | 70.9 | 14.8 | 16 | Table 1, p.619, CON baseline "Stroop Color-Word" |
| 3 | NODE_COG_EPISODIC_MEM | INST_HVLTR | 9.6 | 2.4 | 16 | Table 1, p.619, CON baseline "RAVLT Delayed" |

#### context_priors_template.csv (3 rows)

| Row | Node ID | prior_mean_z | prior_sd_z | Source Location | Derivation |
|-----|---------|-------------|------------|-----------------|------------|
| 1 | NODE_COG_WORK_MEM | −0.42 | 0.5 | Table 1 + WAIS-III norms | z = (pooled_mean − norm_mean) / norm_sd |
| 2 | NODE_COG_EPISODIC_MEM | −0.25 | 0.5 | Table 1 + RAVLT age norms | z = (9.6 − 10.5) / 3.6 |
| 3 | NODE_SYM_COG_COMPLAINTS | +0.35 | 0.5 | Table 1 + cancer survivor norms | Higher = more complaints |

### Extraction Decisions

| # | Category | Risk | Decision | Rationale | Spec Reference |
|---|----------|------|----------|-----------|----------------|
| D1 | `[INST_MAP]` | **MEDIUM** | RAVLT mapped to `INST_HVLTR` | RAVLT not in registry; both measure verbal episodic memory. **Action needed:** Add `INST_RAVLT`. | §T1.instrument_id |
| D2 | `[SIGN_CONV]` | LOW | FACT-Cog d = −0.53 (negative) | Edge is negative (more cogactivity → fewer complaints). Complaints are POS_UP (bad). Negative d = benefit. | SYS_EX §TB-3 |
| D3 | `[BIAS_ADJ]` | **MEDIUM** | Wait-list expectancy bias flagged | No active control → high expectancy bias for subjective outcomes. Recommend 0.7× weight for FACT-Cog. Objective tests less affected. | SYS_EX §TB-5 |
| D4 | `[CONSTRUCT]` | LOW | Digit Span split: Forward→attention, Backward→WM | Forward = capacity; Backward = manipulation. Standard neuropsych convention. | §T1.node_id |
| D5 | `[MISSING_DATA]` | LOW | MANOVA global p used | Paper: MANOVA F(7,20) overall, not per-test p. Assigned p<0.01 to all significant outcomes uniformly. | SYS_EX §EX-P1.3 |
| D6 | `[MISSING_DATA]` | LOW | SE for d approximated | SE(d) ≈ 0.38 for all (derived from n=28, formula √(4/n) baseline). Sufficient for pilot-level evidence. | SYS_EX §EX-P1.1 |

### Verification Checklist

- [ ] PDF SHA-256 hash computed and recorded
- [ ] All Cohen's d values verified against Table 1 (p.619)
- [ ] SE approximation formula documented
- [ ] Population norms verified against Table 1 (p.619)
- [ ] Context prior z-scores recalculated
- [ ] Instrument mappings reviewed against INSTRUMENT_REGISTRY
- [ ] Edge signs verified against expected_sign in EDGE_REGISTRY
- [ ] Human reviewer sign-off

### Supplementary Context (not entered as evidence)

| Data | Value | Source | Reason Not Entered |
|------|-------|--------|-------------------|
| BAI (anxiety) | Measured | Table 1 | No cognitive edge; could be context_prior |
| PHQ-9 (depression) | Measured | Table 1 | No cognitive edge; could be context_prior |
| Quality of life | Measured | Table 1 | No cognitive edge |

### Files Created

| File | Rows | Location |
|------|------|----------|
| edge_evidence_template.csv | 4 | `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/` |
| population_norms_template.csv | 3 | `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/` |
| context_priors_template.csv | 3 | `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/` |
| cherrier2013.meta.json | — | `data/manual_uploads/pdfs/` |

### Files Created
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/edge_evidence_template.csv` (4 rows)
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/population_norms_template.csv` (3 rows)
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/context_priors_template.csv` (3 rows)
- `data/manual_uploads/pdfs/cherrier2013.meta.json`
- `data/manual_uploads/pdfs/cherrier2013.pdf` (copied from root)

---

## SYS-2026-0001 — Infrastructure Setup

### Session Metadata

| Field | Value |
|-------|-------|
| **Record ID** | `SYS-2026-0001` |
| **Timestamp** | 2026-02-25T08:00:00Z |
| **Type** | Infrastructure / Setup |

### Changes Made

#### Workspace Reorganization

| Action | Details |
|--------|---------|
| Moved 28 `.md` docs | Root → `docs/` with 7 numbered subfolders (00_navigation – 06_orchestration) |
| Moved 5 registry CSVs | Root → `registries/` |
| Created `EXTRACTION_PLAYBOOK.md` | Single-file extraction how-to at project root |
| Created `TABLE_FILL_ORDER.md` | `docs/03_database/` — pipeline stage table reference |
| Created `README.md` | `data/manual_uploads/structured/` — per-paper subfolder convention |

#### Code Fixes

| File | Issue | Fix | Risk |
|------|-------|-----|------|
| `crci/retrieval/manual_upload_watcher.py` | `glob("*.csv")` missed subfolders | Changed to `rglob("*.csv")` | LOW |
| `scripts/run_manual_import.py` | Passed directory to `import_structured_csv()` | Now iterates `rglob("*.csv")` per-file | LOW |
| `crci/retrieval/manual_upload_watcher.py` | Column names mismatched spec | Updated `_get_required_columns()` to §T1 canonical names | **MEDIUM** |

#### Database

| Item | Status |
|------|--------|
| Engine | SQLite `crci_dev.db` (PostgreSQL unavailable in codespace) |
| Tables | 50+ created from 7 SQL schema files |
| Seed data | Registries loaded |

---

## Appendix: Decision Categories

| Code | Meaning | Example |
|------|---------|---------|
| `[INST_MAP]` | Instrument/measure mapped to registry ID | TMT-A → INST_TMT_B |
| `[SIGN_CONV]` | Sign or directionality decision | Negative β = benefit for "lower is better" |
| `[MISSING_DATA]` | Handling absent or incomplete data | Using global MANOVA p when per-test p unavailable |
| `[BIAS_ADJ]` | Quality or bias adjustment | Wait-list expectancy → 0.7× weight |
| `[CONSTRUCT]` | Construct validity or node mapping | Forward span → attention; backward → WM |
| `[DUPLICATE]` | Avoiding double-counting | Entered animal naming but not FAS |

## Appendix: Risk Levels

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| **LOW** | Standard mapping, unlikely to affect results | None |
| **MEDIUM** | Approximation or workaround; may need future correction | Flag for review |
| **HIGH** | Significant uncertainty; could materially affect inference | Block until resolved |

## Appendix: Status Workflow

```
EXTRACTED → VERIFIED → INTEGRATED
    ↓           ↓
  (needs     (human
  review)   sign-off)
```

---

*Format: Each extraction = `## EXT-YYYY-NNNN — Author et al. YEAR` block. System changes = `## SYS-YYYY-NNNN`.*  
*Most recent entry at top. Append new entries above the previous one.*
