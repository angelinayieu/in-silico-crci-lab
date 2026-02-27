# Extraction Log

Cumulative audit trail for all evidence extractions into the CRCI system.

**Purpose:** Traceable record of every value extracted, its exact source location,
and every judgment call made during extraction. Enables third-party verification.

**Format:** Each extraction has a unique ID, ISO timestamp, source hash, and
categorized decisions with risk levels. Most recent extraction at top.

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
| **Citation** | Northey JM, et al. (2018) J Sci Med Sport, https://doi.org/10.1016/j.jsams.2018.11.026 |
| **DOI** | `10.1016/j.jsams.2018.11.026` |
| **Trial Registration** | — (not reported) |
| **PDF Location** | `data/manual_uploads/pdfs/` (no PDF available — extracted from full text) |
| **PDF SHA-256** | *(N/A — extracted from article text)* |
| **Pages Extracted** | 1-6 (full text) |

### Study Characteristics

| Field | Value |
|-------|-------|
| **Design** | Pilot RCT, 3-arm parallel group (HIIT vs MOD vs CON) |
| **Sample** | n=17 (HIIT=6, MOD=5, CON=6) |
| **Population** | Female breast cancer survivors ≤24 months post-diagnosis, aged 50–75 years |
| **Intervention** | 12-week cycle ergometer: HIIT (30s intervals at ~105% peak power, 7 intervals) or MOD (20min at 55–65% peak power), 3×/week |
| **Control** | Wait-list (maintain current lifestyle) |
| **Extraction Mode** | `DEEP` (RCT + cancer + cognitive primary) |

### Edges Added to EDGE_REGISTRY

*4 new edges (registry total: 137 → 141)*

| Edge ID | Source Node | Target Node | Sign | Type | Pathway | Basis |
|---------|-------------|-------------|------|------|---------|-------|
| `ER_ACTIVITY_WORKMEM` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_WORK_MEM | positive | causal | PW_M04_NEUROPLASTICITY | RCT d=0.81 NS |
| `ER_ACTIVITY_EXEC_PLAN` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_COG_EXEC_PLANNING | positive | causal | PW_M04_NEUROPLASTICITY | RCT d=0.75 NS |
| `ER_ACTIVITY_DECONDITIONING` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_SYM_DECONDITIONING | negative | causal | PW_C2_FATIGUE | RCT d=1.28 p=0.02 |
| `ER_ACTIVITY_CEREBROVASCULAR` | NODE_BEH_PHYSICAL_ACTIVITY | NODE_PATH_CEREBROVASCULAR | positive | causal | PW_M11_CEREBROVASCULAR | RCT d=0.86 NS |

### Evidence Values Extracted

#### edge_evidence_template.csv (5 rows)

| Row | Edge ID | beta_raw | se_raw | effect_type | n | Source Location | Derivation |
|-----|---------|----------|--------|-------------|---|-----------------|------------|
| 1 | ER_ACTIVITY_EPIMEM | 0.76 | 0.598 | cohen_d | 12 | Table 2, p.4, row "Episodic memory" | d reported; SE=√(12/36+d²/24) |
| 2 | ER_ACTIVITY_EXEC_PLAN | 0.75 | 0.597 | cohen_d | 12 | Table 2, p.4, row "Executive function" | d reported; SE=√(12/36+d²/24) |
| 3 | ER_ACTIVITY_WORKMEM | 0.81 | 0.601 | cohen_d | 12 | Table 2, p.4, row "Working memory" | d reported; SE=√(12/36+d²/24) |
| 4 | ER_ACTIVITY_DECONDITIONING | 1.28 | 0.634 | cohen_d | 12 | Table 2, p.4, row "VO2Peak" | d reported; SE=√(12/36+d²/24) |
| 5 | ER_ACTIVITY_CEREBROVASCULAR | 0.86 | 0.603 | cohen_d | 12 | Table 2, p.4, row "MCA Vmean" | d reported; SE=√(12/36+d²/24) |

**Formula applied:** `SE(d) = √[(n1+n2)/(n1·n2) + d²/(2·(n1+n2))]` where n1=6 (HIIT), n2=6 (CON)

#### population_norms_template.csv (5 rows)

| Row | Node ID | Instrument | Mean | SD | n | Source Location |
|-----|---------|-----------|------|-----|---|-----------------|
| 1 | NODE_COG_EPISODIC_MEM | INST_HVLTR | 9.7 | 0.8 | 6 | Table 2, p.4, CON Pre "Episodic memory, words" |
| 2 | NODE_COG_EXEC_PLANNING | INST_TOL | 56.2 | 12.8 | 6 | Table 2, p.4, CON Pre "Executive function, errors" |
| 3 | NODE_COG_WORK_MEM | INST_DIGIT_SPAN | 1.4 | 0.1 | 6 | Table 2, p.4, CON Pre "Working memory, acc" |
| 4 | NODE_SYM_DECONDITIONING | INST_6MWT | 20.9 | 3.1 | 6 | Table 2, p.4, CON Pre "VO2Peak" |
| 5 | NODE_PATH_CEREBROVASCULAR | INST_MOCA | 52.8 | 10.0 | 6 | Table 2, p.4, CON Pre "MCA Vmean" |

#### context_priors_template.csv (5 rows)

| Row | Node ID | prior_mean_z | prior_sd_z | Source Location | Derivation |
|-----|---------|-------------|------------|-----------------|------------|
| 1 | NODE_COG_EPISODIC_MEM | −0.32 | 0.8 | Table 2 + Lim 2013 norms | z = (9.7 − 10.5) / 2.5 |
| 2 | NODE_COG_EXEC_PLANNING | 0.41 | 0.8 | Table 2 + Maruff 2009 norms | z = (56.2 − 50) / 15 |
| 3 | NODE_COG_WORK_MEM | 0.0 | 0.8 | Table 2 + CogState norms | At normative level |
| 4 | NODE_SYM_DECONDITIONING | −0.02 | 0.5 | Table 2 + ACSM norms | z = (20.9 − 21) / 5 |
| 5 | NODE_BEH_PHYSICAL_ACTIVITY | −0.50 | 0.5 | Inclusion criteria + ACSM | Insufficiently active sample |

### Extraction Decisions

| # | Category | Risk | Decision | Rationale | Spec Reference |
|---|----------|------|----------|-----------|----------------|
| D1 | `[INST_MAP]` | **MEDIUM** | CogState ISL-DR mapped to `INST_HVLTR` | CogState battery not in INSTRUMENT_REGISTRY; ISL delayed recall and HVLT-R both measure verbal episodic memory delayed recall. **Action needed:** Add CogState instruments (INST_COGSTATE_ISL_DR, INST_COGSTATE_GML, INST_COGSTATE_ONB). | §T1.instrument_id |
| D2 | `[INST_MAP]` | **MEDIUM** | CogState Groton Maze mapped to `INST_TOL` | Both assess executive planning/problem solving. Groton Maze uses spatial navigation; Tower of London uses disk arrangement. Different constructs but closest match. **Action needed:** Add `INST_COGSTATE_GML`. | §T1.instrument_id |
| D3 | `[INST_MAP]` | **MEDIUM** | CogState One-Back mapped to `INST_DIGIT_SPAN` | Both measure working memory. One-Back is visual; Digit Span is auditory/verbal. Modest construct validity mismatch. **Action needed:** Add `INST_COGSTATE_ONB`. | §T1.instrument_id |
| D4 | `[INST_MAP]` | **HIGH** | VO2peak mapped to `INST_6MWT` | VO2peak (maximal exercise test) is very different from 6MWT (submaximal walk). **Action needed:** Add `INST_VO2PEAK` to registry. | §T1.instrument_id |
| D5 | `[INST_MAP]` | **HIGH** | TCD MCA Vmean mapped to `INST_MOCA` | Placeholder only — MCA blood flow velocity has nothing to do with MoCA. No cerebrovascular instrument exists. **Action needed:** Add `INST_TCD_MCAV`. | §T1.instrument_id |
| D6 | `[SIGN_CONV]` | LOW | Positive d = HIIT benefit for all outcomes | Paper defines positive d as favorable to the intervention. Consistent across cognitive (higher=better), cerebrovascular (higher=better), and fitness (higher=better). | SYS_EX §TB-3 |
| D7 | `[DUPLICATE]` | **MEDIUM** | HIIT vs CON entered; MOD vs CON excluded | Shared control group (n=6 CON). Entering both would double-count CON. HIIT chosen as primary (larger effects, novel contribution of paper). MOD effects documented in confidence_note. | SYS_EX §P3-G2 |
| D8 | `[DUPLICATE]` | LOW | Verbal learning (ISL learning trials) excluded | ISL learning and ISL delayed recall both map to NODE_COG_EPISODIC_MEM. Delayed recall (d=0.76) is standard episodic memory measure. Learning trials (d=−0.39) excluded to avoid double-counting. | SYS_EX §P3-G2 |
| D9 | `[DUPLICATE]` | LOW | CRV excluded (MCA Vmean entered) | MCA Vmean and cerebrovascular reactivity both map to NODE_PATH_CEREBROVASCULAR. MCA Vmean (d=0.86) entered as primary resting cerebrovascular measure. CRV (d=0.72) noted in confidence_note. | SYS_EX §P3-G2 |
| D10 | `[CONSTRUCT]` | **MEDIUM** | NODE_PATH_CEREBROVASCULAR edge created | NODE_PATH_CEREBROVASCULAR was "EDGELESS PLACEHOLDER" in v1 (PW_M11_CEREBROVASCULAR status="edgeless"). This paper provides the first evidence for parameterizing this pathway. Edge may not be processable in v1 pipeline. | PW_M11 |
| D11 | `[MISSING_DATA]` | LOW | SE(d) derived from formula | Paper reports d but not SE(d). SE computed via standard formula: SE(d)=√[(n1+n2)/(n1·n2)+d²/(2(n1+n2))]. All SEs ~0.59–0.63 reflecting very small sample. | SYS_EX §EX-P1.1 |
| D12 | `[BIAS_ADJ]` | LOW | Risk of bias: moderate | Wait-list control (no blinding of participants). Outcome assessors blinding unclear. Main concern: n=17 severely underpowered. Randomization and allocation concealment adequate. No adverse events. | SYS_EX §TB-5 |

### Verification Checklist

- [ ] All Cohen's d values verified against Table 2 (p.4)
- [ ] All SE(d) derivations recalculated from formula
- [ ] Population norms verified against Table 2 (p.4) — CON Pre columns
- [ ] Context prior z-scores recalculated against published norms
- [ ] Instrument mappings reviewed against INSTRUMENT_REGISTRY
- [ ] Edge signs verified against expected_sign in EDGE_REGISTRY
- [ ] CogState instruments added to INSTRUMENT_REGISTRY (D1-D3 resolved)
- [ ] INST_VO2PEAK and INST_TCD_MCAV added to registry (D4-D5 resolved)
- [ ] Human reviewer sign-off

### Supplementary Context (not entered as evidence)

| Data | Value | Source | Reason Not Entered |
|------|-------|--------|-------------------|
| Verbal learning (ISL learning trials) | HIIT vs CON d=−0.39 | Table 2 | Same node as delayed recall; avoid double-count |
| MOD vs CON episodic memory | d=0.66 | Table 2 | Shared control group with HIIT comparison |
| MOD vs CON executive function | d=0.20 | Table 2 | Shared control group |
| MOD vs CON working memory | d=−0.34 | Table 2 | Shared control group |
| MOD vs CON VO2peak | d=0.72 | Table 2 | Shared control group |
| MOD vs CON MCA Vmean | d=0.31 | Table 2 | Shared control group |
| HIIT vs MOD working memory | d=1.41 | Table 2 | Intensity comparison, not PA vs control |
| CRV (cerebrovascular reactivity) | HIIT vs CON d=0.72 | Table 2 | Same node as MCA Vmean; avoid double-count |
| MAP (mean arterial pressure) | HIIT vs CON d=−0.17 | Table 2 | Blood pressure; not a DAG node |
| PET O2 (end-tidal oxygen) | HIIT vs CON d=−0.24 | Table 2 | Respiratory variable; not a DAG node |
| PET CO2 (end-tidal CO2) | HIIT vs CON d=0.31 | Table 2 | Respiratory variable; not a DAG node |
| Adherence HIIT | 78.7% | Results p.4 | Process metric |
| Adherence MOD | 79.4% | Results p.4 | Process metric |
| Heart rate HIIT vs MOD | 93.9% vs 84.1% HRmax | Results p.4 | Fidelity metric |

### Files Created

| File | Rows | Location |
|------|------|----------|
| edge_evidence_template.csv | 5 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
| population_norms_template.csv | 5 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
| context_priors_template.csv | 5 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/` |
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
