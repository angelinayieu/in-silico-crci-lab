# VERTICAL SLICE 1 — CONTRACT & EXECUTION TRACKER

**Pathway:** Sleep/Activity → HPA → BDNF + Inflammation → CRCI  
**Status:** ACTIVE  
**Created:** 2026-02-27  
**Gate rule:** Each micro-slice has a pass/fail gate. Do NOT proceed to the next slice until the current gate passes.

---

## VS-0.0: FROZEN NODE SET (11 nodes)

Using simplified topology (Decisions: B=cortisol direct, A=inflammation latent, B=BDNF direct, 3+1 cog domains).

| # | Node ID (Registry) | Label | Layer | Orientation | Primary Instrument | Sign Convention | Confirmed |
|---|---------------------|-------|-------|-------------|-------------------|-----------------|-----------|
| 1 | `NODE_BEH_SLEEP_QUALITY` | Sleep Quality | L1 (Behavior) | POS_UP | INST_PSQI (inverted) | Higher PSQI raw = worse → POS_UP means good sleep = higher | ☐ |
| 2 | `NODE_BEH_PHYSICAL_ACTIVITY` | Physical Activity | L1 (Behavior) | POS_UP | INST_IPAQ, INST_GLTEQ, INST_ACCEL | More activity = higher = better | ☐ |
| 3 | `NODE_BIO_CORTISOL` | Cortisol Diurnal Slope | L2 (Biomarker) | POS_DOWN | INST_CORTISOL_SLOPE | Flatter slope = higher raw = worse (POS_DOWN) | ☐ |
| 4 | `NODE_BIO_BDNF` | Plasma BDNF | L2 (Biomarker) | POS_UP | INST_BDNF_PLASMA | Higher BDNF = better neuroplasticity | ☐ |
| 5 | `NODE_BIO_IL6` | Interleukin-6 | L2 (Biomarker) | POS_DOWN | INST_IL6_PLASMA | Higher IL-6 = worse inflammation | ☐ |
| 6 | `NODE_BIO_CRP` | C-Reactive Protein | L2 (Biomarker) | POS_DOWN | INST_CRP_HS | Higher CRP = worse | ☐ |
| 7 | `NODE_BIO_TNF` | TNF-Alpha | L2 (Biomarker) | POS_DOWN | INST_TNF_PLASMA | Higher TNF = worse | ☐ |
| 8 | `NODE_COG_EPISODIC_MEM` | Episodic Memory | L5 (Cognitive) | POS_UP | INST_HVLTR | Higher = better memory | ☐ |
| 9 | `NODE_COG_PROC_SPEED` | Processing Speed | L5 (Cognitive) | POS_UP | INST_TMT_B (inverted) | Lower time = better → POS_UP | ☐ |
| 10 | `NODE_COG_ATTN_SUSTAINED` | Sustained Attention | L5 (Cognitive) | POS_UP | INST_CPT, Stroop | Higher = better attention | ☐ |
| 11 | `NODE_COMP_CRCI` | CRCI Composite | L6 (Composite) | POS_UP | Computed (IVW F-1) | Higher = better cognition | ☐ |

### Latent Construct: Neuroinflammation (OIC)

`NODE_PATH_OIC` (Oxidative-Inflammatory Cascade) is the **latent node** in this slice.  
Indicators: `NODE_BIO_IL6` (primary), `NODE_BIO_CRP`, `NODE_BIO_TNF`.  
This is NOT a separate "node" in the B-matrix — it's a latent variable with indicator loadings.

---

## VS-0.0: FROZEN EDGE SET (14 edges)

### Causal / Associational Edges (10 edges with β + SE)

| # | Edge ID (Registry) | Source → Target | Relation Type | Expected Sign | Mechanism | R-Class | Preferred Estimand |
|---|--------------------|-----------------|--------------:|---------------|-----------|---------|-------------------|
| E1 | `ER_SLEEP_CORTISOL` | sleep_quality → cortisol | causal | negative | Poor sleep disrupts cortisol rhythm | R2 | β (adjusted, sleep→cortisol) |
| E2 | `ER_ACTIVITY_CORTISOL` | physical_activity → cortisol | causal | negative | Exercise normalizes cortisol rhythm | R2 | β or r (activity→cortisol slope) |
| E3 | `ER_IL6_BDNF_CROSS` | IL-6 → BDNF | associational | negative | Chronic inflammation suppresses BDNF | R3 | r (cross-sectional correlation) |
| E4 | `ER_ACTIVITY_BDNF` | physical_activity → BDNF | causal | positive | Exercise ↑ BDNF via irisin/FNDC5 | R1/R2 | SMD (RCT) or β (cohort) |
| E5 | `ER_NEUROPLAST_EPISODIC` | BDNF → episodic_memory | causal | positive | BDNF→TrkB→hippocampal LTP→memory | R2/R3 | r or β (BDNF→memory) |
| E6 | `ER_OIC_PROCSPEED` | OIC → processing_speed | causal | negative | Inflammation→white matter damage→slow | R2/R3 | β (IL-6/CRP→TMT/DSST) |
| E7 | `ER_OIC_EPISODIC` | OIC → episodic_memory | causal | negative | Inflammation→hippocampal damage→memory | R2/R3 | β (IL-6/CRP→HVLT) |
| E8 | `ER_OIC_ATTNSUST` | OIC → sustained_attention | causal | negative | Inflammation→sickness behavior→attention | R2/R3 | β (IL-6/CRP→CPT/attention) |
| E9 | `ER_CORTISOL_HPA` → then `ER_HPA_EPISODIC` | cortisol → episodic_memory | serial (via HPA) | negative | Glucocorticoid hippocampal damage | R2/R3 | β (cortisol slope→memory) |
| E10 | `ER_CORTISOL_HPA` → then `ER_HPA_WORKMEM` | cortisol → attention (via HPA) | serial (via HPA) | negative | HPA→prefrontal dysfunction | R2/R3 | β (cortisol→executive/attn) |

### Indicator Loadings (3 loadings for latent OIC)

| # | Edge ID | Indicator → Latent | Type | Required Data |
|---|---------|-------------------|------|---------------|
| L1 | `ER_IL6_OIC` | IL-6 → OIC | indicator loading | Inter-biomarker correlation (r, N) |
| L2 | `ER_CRP_OIC` | CRP → OIC | indicator loading | Inter-biomarker correlation (r, N) |
| L3 | `ER_TNF_OIC` | TNF-α → OIC | indicator loading | Inter-biomarker correlation (r, N) |

**Required correlation pairs for D-matrix:**
- IL-6 ↔ CRP: expected ρ ≈ 0.72 (from registry)
- IL-6 ↔ TNF-α: expected ρ ≈ 0.65
- CRP ↔ TNF-α: expected ρ ≈ 0.58

### Aggregation Edge (1)

| # | Type | Description |
|---|------|-------------|
| A1 | IVW aggregation | `{episodic_mem, proc_speed, attn_sustained}` → `crci_composite` via Formula F-1 |

---

## VS-0.1: EDGE SLOTTING TABLE

For each edge: what estimand do we prefer, what fallbacks are acceptable, and what minimum confounding adjustment is required.

| Edge # | Edge ID | R-Class | Preferred Estimand | Fallback 1 | Fallback 2 | Min Adjustment | SE Multiplier if Fallback |
|--------|---------|---------|-------------------|------------|------------|----------------|--------------------------|
| E1 | `ER_SLEEP_CORTISOL` | R2 | β (PSQI→cortisol slope, adjusted) | r (sleep metric↔cortisol) cross-sectional | Δ cortisol pre/post sleep intervention | Age, sex, cancer type | 1.0 (preferred) / 1.15 (r→β) / 1.25 (intervention Δ) |
| E2 | `ER_ACTIVITY_CORTISOL` | R2 | β (activity→cortisol slope, adjusted) | r (activity↔cortisol) | RCT SMD exercise vs control (cortisol) | Age, sex, BMI | 1.0 / 1.15 / 1.1 |
| E3 | `ER_IL6_BDNF_CROSS` | R3 | r (IL-6 ↔ BDNF, cancer population) | β (IL-6 predicting BDNF) | r (non-cancer population) | None required (correlational) | 1.0 / 1.0 / 1.5 (pop mismatch) |
| E4 | `ER_ACTIVITY_BDNF` | R1/R2 | SMD (RCT: exercise vs control, BDNF) | β (activity→BDNF, cohort) | r (activity↔BDNF, cross-sectional) | Randomization (RCT) or age, BMI | 1.0 / 1.15 / 1.25 |
| E5 | `ER_NEUROPLAST_EPISODIC` | R2/R3 | r or β (BDNF→memory score, cancer) | r (BDNF→memory, non-cancer) | Mediation indirect effect (exercise→BDNF→memory) | Age, education | 1.0 / 1.5 (pop) / 1.25 (mediation) |
| E6 | `ER_OIC_PROCSPEED` | R2/R3 | β (IL-6/CRP→TMT/DSST, adjusted) | r (inflammation↔processing speed) | SMD (high vs low inflammation groups) | Age, education, depression | 1.0 / 1.15 / 1.25 |
| E7 | `ER_OIC_EPISODIC` | R2/R3 | β (IL-6/CRP→HVLT/RAVLT, adjusted) | r (inflammation↔memory) | Group SMD | Age, education, depression | 1.0 / 1.15 / 1.25 |
| E8 | `ER_OIC_ATTNSUST` | R2/R3 | β (IL-6/CRP→attention measure, adjusted) | r (inflammation↔attention) | Group SMD | Age, education | 1.0 / 1.15 / 1.25 |
| E9 | `ER_HPA_EPISODIC` | R2/R3 | β (cortisol slope→memory, adjusted) | r (cortisol↔memory) | Time-lagged cortisol T0→memory T2 | Age, depression | 1.0 / 1.15 / 1.0 (lagged=good) |
| E10 | `ER_HPA_WORKMEM` | R2/R3 | β (cortisol→executive/attention, adjusted) | r (cortisol↔executive) | — | Age, depression | 1.0 / 1.15 |
| L1 | `ER_IL6_OIC` | Structural | r (IL-6 ↔ CRP, same sample) | r from meta-analysis | — | — | 1.0 / 1.1 |
| L2 | `ER_CRP_OIC` | Structural | r (CRP ↔ TNF-α, same sample) | — | — | — | 1.0 |
| L3 | `ER_TNF_OIC` | Structural | r (TNF-α ↔ IL-6, same sample) | — | — | — | 1.0 |
| A1 | Aggregation | Formula F-1 | Domain z-scores + SEs | — | — | — | N/A |

### Conversion Priority Rules

When converting reported statistics to target estimand:
1. **Direct SMD** (d reported) → no conversion needed
2. **β from regression** → keep as-is if standardized; if unstandardized, convert via SD ratio
3. **r → d**: `d = 2r/√(1−r²)`, SE via delta method: `SE_d = 2·SE_r / (1−r²)^(3/2)`
4. **OR → d**: `d = ln(OR)·√3/π`, `SE_d = SE_ln(OR)·√3/π`
5. **CI → SE**: `SE = (upper − lower) / 3.92` (95% CI)
6. **p → SE**: `SE = |β| / Φ⁻¹(1 − p/2)` — only if β is given
7. **Means ± SD → d**: `d = (M₁−M₂) / SD_pooled`, `SE = √(1/n₁ + 1/n₂ + d²/(2(n₁+n₂)))`

**Conversion SE Penalty:** +10% SE per conversion step (multiplicative: 1.1× per step).

---

## MICRO-SLICE EXECUTION PLAN

### VS-1.0: P1 Slice-Targeted Multi-Edge Sweep
- **Goal:** Find 15–20 candidate papers covering ≥2 edges each with longitudinal preference
- **Output artifact:** `data/vertical_slice_1/MULTI_EDGE_PAPERS_slice1_v1.yaml`
- **Gate:** ≥6 papers plausibly cover ≥2 edges each; ≥8/14 edges have ≥1 candidate
- **Status:** ☐ NOT STARTED

### VS-1.1: Triage to Download List
- **Goal:** Score and bin papers into A/B/C; produce top-8 ranked download list
- **Output artifact:** `data/vertical_slice_1/MULTI_EDGE_TRIAGE_slice1_v1.yaml`
- **Gate:** Top-8 collectively cover ≥8 of 14 edges
- **Status:** ☐ NOT STARTED

### VS-1.2: Topology Gap Fill (conditional)
- **Goal:** Find 1–2 anchor studies per edge still missing from VS-1.0
- **Output artifact:** `data/vertical_slice_1/SLICE_TOPOLOGY_FILL_v1.yaml`
- **Gate:** All 10 causal edges have ≥1 candidate paper
- **Status:** ☐ NOT STARTED (skip if VS-1.1 gate passes without gaps)

### VS-1.3: Correlation Matrix Papers (D-matrix)
- **Goal:** Find 3–5 papers reporting IL-6/CRP/TNF-α correlation matrices in cancer
- **Output artifact:** `data/vertical_slice_1/BIOMARKER_CORR_MATRICES_v1.yaml`
- **Gate:** ≥2 independent correlation matrices with all 3 pairs
- **Status:** ☐ NOT STARTED

### VS-1.4: Temporal Trajectory Papers
- **Goal:** Find 5–10 papers with ≥3 timepoints for biomarkers + cognition
- **Output artifact:** `data/vertical_slice_1/TRAJECTORIES_slice1_v1.yaml`
- **Gate:** ≥3 papers with biomarker OR cognition trajectories across ≥2 phases
- **Status:** ☐ NOT STARTED

### VS-1.5: RCT Intervention Anchors
- **Goal:** Find 3–5 exercise/sleep RCTs with cognitive outcomes ± biomarkers
- **Output artifact:** `data/vertical_slice_1/RCT_ANCHORS_slice1_v1.yaml`
- **Gate:** ≥1 exercise RCT with extractable SMD for exercise→cognition (chain-vs-direct validation)
- **Status:** ☐ NOT STARTED

### VS-2.0: Gold Extraction Template
- **Goal:** Create and validate CSV templates for study_profiles + edge_evidence
- **Output artifact:** `data/vertical_slice_1/templates/study_profiles_slice1.csv`, `edge_evidence_slice1.csv`
- **Gate:** Can fill 1 dummy row end-to-end without ambiguity
- **Status:** ☐ NOT STARTED

### VS-2.1: Calibration Pair Extraction (2 papers)
- **Goal:** Fully extract 2 high-yield papers; validate conversion pipeline
- **Output artifact:** `data/vertical_slice_1/extractions/` (2 paper folders)
- **Gate:** Can compute pooled β + SE for ≥2 edges from just these 2 papers
- **Status:** ☐ NOT STARTED

### VS-3.0: Full Extraction Batch (remaining 6–10 papers)
- **Goal:** Extract all prioritized papers
- **Output artifact:** `data/vertical_slice_1/edge_evidence_slice1_v1.csv` (20–40 rows), `study_profiles_slice1_v1.csv` (8–12 rows)
- **Gate:** ≥10/14 edges have ≥1 record; ≥8/14 have ≥2
- **Status:** ☐ NOT STARTED

### VS-4.0: Per-Edge IVW Aggregation
- **Goal:** Compute pooled β + SE for each edge using IVW
- **Output artifact:** Jupyter notebook `notebooks/VS1_aggregation.ipynb`
- **Gate:** Produces `edge_registry_slice1_v1.csv` with no NaN, no sign flips
- **Status:** ☐ NOT STARTED

### VS-4.1: 7-Layer SE Inflation Trace
- **Goal:** Apply full SE inflation pipeline per edge
- **Output artifact:** `data/vertical_slice_1/layer_traces_slice1_v1.csv`
- **Gate:** Every edge has full SE_raw → SE_eff trace; inflation drivers are interpretable
- **Status:** ☐ NOT STARTED

### VS-5.0: Minimal Runtime (1 synthetic patient)
- **Goal:** Build B-matrix, run Bayesian update, MC simulation for 1 patient
- **Output artifact:** `notebooks/VS1_end_to_end.ipynb`
- **Gate:** Output is numerically stable (PD, spectral radius < 1) and clinically directional
- **Status:** ☐ NOT STARTED

### VS-5.1: Chain-vs-Direct Validation
- **Goal:** Compare chain product vs direct RCT effect for exercise→cognition
- **Output artifact:** Results in VS1_end_to_end.ipynb
- **Gate:** Z-score for chain-vs-direct mismatch < 2.0 (or documented explanation)
- **Status:** ☐ NOT STARTED

### VS-5.2: Sensitivity Analysis
- **Goal:** Perturb each edge β by ±1 SE, check rank stability of top intervention
- **Output artifact:** Results in VS1_end_to_end.ipynb
- **Gate:** Top intervention remains stable under ≥80% of perturbations
- **Status:** ☐ NOT STARTED

### VS-6.0: Document Lessons Learned
- **Goal:** Scientific narrative of what worked, what didn't, gaps found
- **Output artifact:** `docs/outputs/VS1_LESSONS_LEARNED.md`
- **Gate:** Document exists and covers topology decisions, evidence gaps, surprises
- **Status:** ☐ NOT STARTED

---

## EXECUTION ORDER (STRICT)

```
VS-0.0 (this contract)          ← YOU ARE HERE
    ↓
VS-1.0 (P1 multi-edge sweep)   ← FIRST RESEARCH ACTION
    ↓
VS-1.1 (triage)
    ↓
VS-1.2 (gap fill, if needed)  ──┐
VS-1.3 (D-matrix correlations)  │── can run in parallel
VS-1.4 (trajectories)           │
VS-1.5 (RCT anchors)          ──┘
    ↓
VS-2.0 (template)
    ↓
VS-2.1 (calibration pair)      ← CRITICAL CHECKPOINT
    ↓
VS-3.0 (full extraction)
    ↓
VS-4.0 (aggregation)
    ↓
VS-4.1 (SE inflation)
    ↓
VS-5.0 (runtime test)
    ↓
VS-5.1 + VS-5.2 (validation)   ← can run in parallel
    ↓
VS-6.0 (lessons learned)
```

**Estimated total:** ~20 focused days for first slice. Each subsequent pathway: ~10 days.
