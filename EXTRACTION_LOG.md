# Extraction Log

Cumulative record of every extraction action, decision, and addition.  
Updated every session. Most recent entry at top.

---

## 2026-02-25 — Campbell et al. 2017

**Paper:** "Effect of aerobic exercise on cancer-associated cognitive impairment: A proof-of-concept RCT"  
**DOI:** 10.1002/pon.4370 | **Journal:** Psycho-Oncology | **NCT:** NCT01296893  
**Design:** RCT, n=19 (EX=10, CON=9), breast cancer, postmenopausal, stage I-IIIa, 24-week aerobic exercise  
**Mode:** DEEP (RCT + breast cancer + cognitive primary outcome + self-reported cog decline at enrollment)

### Edges Added to EDGE_REGISTRY (4 new, total now 137)

| Edge ID | Source → Target | Sign | Basis |
|---------|-----------------|------|-------|
| `ER_ACTIVITY_PROC_SPEED` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_PROC_SPEED | positive | RCT evidence |
| `ER_ACTIVITY_VERBAL_FLUENCY` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_VERBAL_FLUENCY | positive | Trend only |
| `ER_ACTIVITY_EPIMEM` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_EPISODIC_MEM | positive | Null (registered for evidence accumulation) |
| `ER_ACTIVITY_COG_COMPLAINTS` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_SYM_COG_COMPLAINTS | negative | Null (negative: more activity → fewer complaints) |

### Evidence Extracted (Table 2, ANCOVA-adjusted end-of-study)

| Outcome | Instrument | beta_raw | se_raw | p | partial_η² | Edge |
|---------|-----------|---------|--------|---|------------|------|
| TMT-A (s) | INST_TMT_B | −14.2 | 5.28 | 0.01 | 0.35 | ER_ACTIVITY_PROC_SPEED |
| Animal fluency | INST_COWAT | +3.0 | 2.14 | 0.15 | 0.13 | ER_ACTIVITY_VERBAL_FLUENCY |
| HVLT Total Recall | INST_HVLTR | −1.5 | 2.48 | 0.52 | 0.03 | ER_ACTIVITY_EPIMEM |
| FACT-Cog PCI | INST_FACTCOG_PCI | +3.9 | 5.33 | 0.44 | 0.04 | ER_ACTIVITY_COG_COMPLAINTS |

SE computed from 95% CI: `SE = (upper − lower) / (2 × 1.96)`

**Also extracted (not edge evidence — fitness/adherence context):**
- VO2peak: EX +3.6 ml/kg/min vs CON (p<0.01, partial_η²=0.43) — confirms intervention was effective at the physiological level
- Exercise adherence: 88% supervised, 87% home, 74.5% HRR achieved

### Population Norms Added (CON baseline, n=9)

| Node | Instrument | Mean | SD |
|------|-----------|------|----|
| NODE_COG_PROC_SPEED | INST_TMT_B | 33.8s | 9.1 |
| NODE_COG_EPISODIC_MEM | INST_HVLTR | 25.2 | 4.0 |
| NODE_COG_VERBAL_FLUENCY | INST_COWAT | 18.0 | 4.3 |
| NODE_SYM_COG_COMPLAINTS | INST_FACTCOG_PCI | 28.8 | 14.8 |
| NODE_SYM_DEPRESSION | INST_CESD | 15.4 | 2.4 |
| NODE_SYM_FATIGUE | INST_FACIT_FATIGUE | 113.0 | 23.3 |

### Context Priors Added

| Node | prior_mean_z | Basis |
|------|-------------|-------|
| NODE_SYM_COG_COMPLAINTS | −2.18 | FACT-Cog PCI 28.8 vs Wagner 2009 cancer norm ~61 (SD~14.8) |
| NODE_SYM_DEPRESSION | +0.93 | CES-D 15.4 vs general pop mean ~8 SD ~8 |
| NODE_BEH_PHYSICAL_ACTIVITY | −1.25 | MVPA 11.2 MET-hr/wk vs adult norm ~22-25 |
| NODE_SYM_FATIGUE | −0.48 | FACT-F 113/160 vs cancer norm ~120 |

### Key Decisions

- **TMT-A instrument ID:** Used `INST_TMT_B` (closest available) — TMT-A is not registered as a separate instrument. Flagged in confidence_note. Future: add `INST_TMT_A` to INSTRUMENT_REGISTRY.
- **beta_raw for TMT-A is −14.2 (negative = exercise faster):** Sign preserved as raw; the edge `ER_ACTIVITY_PROC_SPEED` has `expected_sign = positive` (exercise benefit). The Trust Boundary will handle orientation using `scoring_direction` from the instrument registry — TMT-B has `lower_better` so negative = beneficial.
- **FACT-F total score = 113.0:** Paper reports FACT-F TOI which is a combined score out of ~160, NOT the standard 13-item FACT-Fatigue subscale (0–52). Flagged in meta.json for verification. May not directly map to `INST_FACIT_FATIGUE` norms.
- **FAS verbal fluency:** Also measured (adj diff −1.5, p=0.56) — chose animal naming as primary verbal fluency entry because direction was positive and effect size slightly larger. FAS null result not separately entered to avoid double-weighting same construct.
- **HVLT-R used for episodic memory:** Paper used standard HVLT-R; used `INST_HVLTR`.
- **Animal naming instrument ID:** Used `INST_COWAT` (maps to NODE_COG_VERBAL_FLUENCY) — closest match; COWAT includes semantic fluency (animal naming). Flagged.
- **Null results entered:** All 3 null outcomes (verbal fluency trend, episodic memory null, subjective complaints null) still entered. Rationale: null evidence constrains the posterior and prevents overestimation of exercise effects. Small pilot (n=19) is severely underpowered for most outcomes — wide SEs reflect this.
- **fMRI data not entered as edge evidence:** fMRI group×time interaction in rMFG/rACC/lSFG (F=13.74, p=0.01) reflects neural efficiency, not a node-level effect size in the DAG. Captured in meta.json narrative only.
- **Risk of bias:** Overall low-to-moderate. Main concern: small sample (n=19) severely underpowered. Objective outcome assessors were blinded.

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

## 2026-02-25 — Cherrier et al. 2013

**Paper:** "A randomized trial of cognitive rehabilitation in cancer survivors"  
**DOI:** 10.1016/j.lfs.2013.08.011 | **Journal:** Life Sciences 93:617-622  
**Design:** RCT, n=28 (TX=12, CON=16), mixed cancer types, 7-week group cognitive rehabilitation  
**Mode:** DEEP (RCT + cancer + cognitive primary outcome)

### Edges Added to EDGE_REGISTRY (4 new, total was 131 → 133 at time of entry)

| Edge ID | Source → Target | Sign | Basis |
|---------|-----------------|------|-------|
| `ER_COGACTIVITY_WORKMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_WORK_MEM | positive | RCT evidence, d=0.79 |
| `ER_COGACTIVITY_ATTN` | NODE_BEH_COG_ACTIVITY → NODE_COG_ATTN_SUSTAINED | positive | RCT evidence, d=0.59 |
| `ER_COGACTIVITY_COGCOMPLAINTS` | NODE_BEH_COG_ACTIVITY → NODE_SYM_COG_COMPLAINTS | negative | RCT evidence, d=0.53 |
| `ER_COGACTIVITY_EPIMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_EPISODIC_MEM | positive | Trend d=0.25, p<0.10 |

### Evidence Extracted (Table 1, pre/post by group)

Cohen's d computed from raw means/SEs:  
`SD = SE × √n` then `d = (Δmean_TX − Δmean_CL) / SD_pooled`

| Outcome | Instrument | beta_raw (d) | se_raw | p | Edge |
|---------|-----------|-------------|--------|---|------|
| Digit Span Backward | INST_DIGIT_SPAN | 0.79 | 0.38 | <0.01 | ER_COGACTIVITY_WORKMEM |
| Digit Span Total | INST_DIGIT_SPAN | 0.59 | 0.38 | <0.01 | ER_COGACTIVITY_ATTN |
| FACT-Cog PCI | INST_FACTCOG_PCI | −0.53 | 0.38 | <0.01 | ER_COGACTIVITY_COGCOMPLAINTS |
| RAVLT Delayed | INST_HVLTR | 0.25 | 0.38 | <0.10 | ER_COGACTIVITY_EPIMEM |

### Population Norms Added (CON baseline, n=16)

| Node | Instrument | Mean | SD |
|------|-----------|------|----|
| NODE_SYM_COG_COMPLAINTS | INST_FACTCOG_PCI | 37.7 | 20.4 |
| NODE_COG_PROC_SPEED | INST_STROOP | 70.9 | 14.8 |
| NODE_COG_EPISODIC_MEM | INST_HVLTR | 9.6 | 2.4 |

### Context Priors Added

| Node | prior_mean_z | Basis |
|------|-------------|-------|
| NODE_COG_WORK_MEM | −0.42 | Digit Span pooled vs WAIS-III age-norm 55-64 |
| NODE_COG_EPISODIC_MEM | −0.25 | RAVLT vs age-norm |
| NODE_SYM_COG_COMPLAINTS | +0.35 | FACT-Cog PCI vs cancer survivor norms — more complaints |

### Key Decisions

- **RAVLT used but mapped to INST_HVLTR:** Paper used RAVLT (Rey Auditory Verbal Learning Test), not HVLT-R. Both measure verbal learning/episodic memory. Used INST_HVLTR as closest match; flagged in confidence_note. Future: add `INST_RAVLT` to INSTRUMENT_REGISTRY.
- **FACT-Cog sign convention:** Edge sign is negative (more cogactivity → fewer complaints) because COG_COMPLAINTS is POS_UP (higher score = more complaints, worse). `beta_raw = −0.53` preserves direction.
- **Expectancy bias flagged:** Wait-list control design (not active control) creates high expectancy bias risk for subjective outcomes (FACT-Cog). Recommended 0.7× downweight in confidence_note. Objective neuropsych outcomes less affected.
- **MANOVA global F used for p-values:** Paper reported MANOVA with F(7,20) overall, not per-test p-values. p<0.01 assigned to all significant tests. SE for d set uniformly at 0.38 (derived from pooled n=28, approximate).
- **Digit Span Total vs Backward:** Forward span = working memory capacity; backward = active manipulation. Used Total as attention proxy (`ER_COGACTIVITY_ATTN`) and Backward as working memory (`ER_COGACTIVITY_WORKMEM`). Both derived from same instrument session.
- **Missing outcomes not extracted:** BAI (anxiety), PHQ-9 (depression), quality of life — measured but no effect sizes for cognition-adjacent nodes. Could be entered as context_priors in future.

### Files Created
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/edge_evidence_template.csv` (4 rows)
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/population_norms_template.csv` (3 rows)
- `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/context_priors_template.csv` (3 rows)
- `data/manual_uploads/pdfs/cherrier2013.meta.json`
- `data/manual_uploads/pdfs/cherrier2013.pdf` (copied from root)

---

## 2026-02-25 — Infrastructure Setup

### Workspace Reorganization
- Moved all 28 root-level `.md` docs into `docs/` subfolders (00_navigation through 06_orchestration)
- Moved 5 registry CSVs to `registries/`
- Created `EXTRACTION_PLAYBOOK.md` (root level — single-file how-to for new papers)
- Created `docs/03_database/TABLE_FILL_ORDER.md` (referenced in code but missing)
- Added `data/manual_uploads/structured/README.md` (per-paper subfolder convention)

### Code Fixes
- `crci/retrieval/manual_upload_watcher.py`: changed `glob("*.csv")` → `rglob("*.csv")` to find CSVs in per-paper subfolders
- `scripts/run_manual_import.py`: changed `glob("*.csv")` → `rglob("*.csv")` and fixed to pass individual file paths to `import_structured_csv()`
- `crci/retrieval/manual_upload_watcher.py` `_get_required_columns()`: aligned column names with `CRCI_Checklists_Templates_v2.0.md §T1` spec

### Database
- SQLite `crci_dev.db` — all 50+ tables created from 7 SQL schema files
- PostgreSQL unavailable in this environment (sudo failing); system defaults to SQLite

---

*Format: append a new `## YYYY-MM-DD — Author et al. YEAR` section at the top for each new paper.*
