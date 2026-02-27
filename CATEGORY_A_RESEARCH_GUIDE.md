# Category A Knowledge Tables — Research & Curation Guide

**Purpose:** Instructions for filling the 5 empty knowledge-base tables that the algorithm
chains need but that are NOT populated from per-paper extraction.  
**These are one-time curation tasks**, not per-paper extraction. You author them once
from domain knowledge, then the algorithm reads them at runtime.

---

## Table of Contents

1. [Overview: What Are Category A Tables?](#1-overview)
2. [Table 1: `intervention_kernels_v1`](#2-intervention-kernels) — 8 rows needed
3. [Table 2: `dose_bridges_v1`](#3-dose-bridges) — ~16-24 rows needed
4. [Table 3: `contraindication_rules_v1`](#4-contraindication-rules) — ~15-20 rows needed
5. [Table 4: `biomarker_correlations_v1`](#5-biomarker-correlations) — 8 rows needed
6. [Table 5: `normalization_refs_v1`](#6-normalization-refs) — ~20-40 rows needed
7. [Research Strategy](#7-research-strategy)
8. [CSV Templates & Import](#8-csv-templates)

---

## 1. Overview

Category A tables are **human-curated domain-knowledge tables** — they describe HOW
interventions work (temporal dynamics, dose-response), SAFETY constraints, and
REFERENCE populations. They are NOT extracted from a single paper; they synthesize
knowledge across the literature.

### Current State (what's populated vs empty)

| Table | Status | Rows Needed | Blocks Which Chain |
|-------|--------|-------------|-------------------|
| `intervention_kernels_v1` | **EMPTY** | 8 (one per action) | Chain E (temporal) |
| `dose_bridges_v1` | **EMPTY** | ~16-24 | Chain D (simulation) |
| `contraindication_rules_v1` | **EMPTY** | ~15-20 | Chain D (safety) |
| `biomarker_correlations_v1` | **EMPTY** | 8 | Chain A (graph) |
| `normalization_refs_v1` | **EMPTY** | ~20-40 | Chain C (state estimation) |

### Our 8 Actions (from `action_catalog_v1`)

Every kernel, dose bridge, and many contraindication rules reference these:

| Action ID | Label | Class | Dose Type | Dose Unit |
|-----------|-------|-------|-----------|-----------|
| `ACT_EXERCISE_AEROBIC` | Aerobic Exercise | physical_activity | continuous | minutes |
| `ACT_EXERCISE_RESISTANCE` | Resistance Training | physical_activity | continuous | minutes |
| `ACT_COGNITIVE_TRAINING` | Cognitive Training | cognitive_training | continuous | minutes |
| `ACT_MINDFULNESS` | Mindfulness Meditation | stress_regulation | continuous | minutes |
| `ACT_SLEEP_HYGIENE` | Sleep Hygiene Protocol | sleep | binary | — |
| `ACT_LIGHT_AM` | Morning Light Exposure | light_exposure | continuous | minutes |
| `ACT_SOCIAL_ENGAGE` | Social Engagement | social | continuous | minutes |
| `ACT_NUTRITION_ANTI_INFLAM` | Anti-inflammatory Diet | nutrition | binary | — |

---

## 2. Intervention Kernels (`intervention_kernels_v1`) {#2-intervention-kernels}

### What This Table Does

Models the **temporal shape** of each intervention's effect:
- **Onset:** How many weeks before any benefit appears
- **Build:** How long to ramp from first effect to full effect
- **Steady-state:** How long the plateau lasts (while adhering)
- **Decay:** Half-life of benefit after cessation

The algorithm applies a trapezoidal kernel:
```
Phase 1 — Onset:  linear ramp 0 → 1 over onset_weeks
Phase 2 — Build:  linear ramp 1 → peak over build_weeks  
Phase 3 — Steady: plateau at peak for steady_state_weeks
Phase 4 — Decay:  K(t) = peak × e^{−0.693(t − t_steady) / half_life}
```

### Schema (14 columns)

| Column | Type | Required | Example |
|--------|------|----------|---------|
| `kernel_id` | TEXT PK | YES | `KERN_EXERCISE_AEROBIC` |
| `action_id` | TEXT FK → action_catalog_v1 | YES | `ACT_EXERCISE_AEROBIC` |
| `kernel_family` | ENUM | YES | `trapezoidal` |
| `onset_weeks_min` | FLOAT | YES | `2.0` |
| `onset_weeks_max` | FLOAT | YES | `4.0` |
| `build_weeks` | FLOAT | YES | `10.0` |
| `steady_state_weeks_min` | FLOAT | YES | `12.0` |
| `steady_state_weeks_max` | FLOAT | YES | `52.0` |
| `decay_half_life_weeks` | FLOAT | YES | `3.5` |
| `pathway_specific_onset_json` | JSON | NO | `{"PW_M01_NEUROINFLAMMATION": 3, "PW_M04_NEUROPLASTICITY": 6}` |
| `source_citation` | TEXT | YES | `Campbell et al. 2020; Xiong et al. 2024` |
| `version` | INT | YES | `1` |
| `active` | INT | YES | `1` |
| `notes` | TEXT | NO | free text |

### Research Instructions Per Action

For each of the 8 actions, you need to find:

#### ACT_EXERCISE_AEROBIC — Aerobic Exercise
**Search terms:** `aerobic exercise cognitive function onset weeks`, `exercise intervention temporal dynamics cognition`, `exercise detraining cognitive decline half-life`

**Key questions to answer from literature:**
- How soon after starting a regular aerobic program do cognitive benefits appear? (onset)
- How long does the ramp-up to full benefit take? (build)
- Is there a known plateau duration? (steady-state)
- After stopping exercise, how fast do cognitive benefits decay? (decay half-life)

**Expected findings (calibration anchors):**
- Onset: 2-4 weeks (anti-inflammatory effects faster; neuroplasticity slower)
- Build: 8-12 weeks (most RCTs use 12-week programs for this reason)
- Steady-state: 12-52 weeks (maintained while adhering)
- Decay half-life: 2-4 weeks (detraining is relatively fast)

**Priority sources:**
- Northey et al. 2019 (systematic review, exercise + cognition in cancer)
- Campbell et al. 2020 (ACSM exercise guidelines for cancer)
- Xiong et al. 2024 (exercise duration effects)
- Detraining literature: Mujika & Padilla 2000; Themanson et al. 2008

**Pathway-specific onsets (optional JSON):**
- `PW_M01_NEUROINFLAMMATION`: 2-3 weeks (acute anti-inflammatory via IL-6 myokine response)
- `PW_M04_NEUROPLASTICITY`: 4-8 weeks (BDNF upregulation requires sustained stimulus)
- `PW_M11_CEREBROVASCULAR`: 4-6 weeks (cerebral blood flow adaptations)

#### ACT_EXERCISE_RESISTANCE — Resistance Training
**Search terms:** `resistance training cognitive function timeline`, `strength training neuroplasticity onset`

**Expected findings:**
- Onset: 4-6 weeks (generally slower than aerobic for cognitive effects)
- Build: 10-16 weeks
- Steady-state: 12-52 weeks
- Decay half-life: 3-6 weeks

**Priority sources:**
- Liu-Ambrose et al. 2010, 2012 (resistance training + executive function)
- Cassilhas et al. 2007 (resistance exercise + cognition)

#### ACT_COGNITIVE_TRAINING — Cognitive Training
**Search terms:** `cognitive training transfer effects duration`, `brain training onset cognitive improvement`, `cognitive training cessation maintenance`

**Expected findings:**
- Onset: 1-2 weeks (immediate practice effects, but transfer takes longer)
- Build: 6-12 weeks (far transfer requires sustained training)
- Steady-state: while training + 6-12 months post (some evidence of durable transfer)
- Decay half-life: 8-16 weeks (slower decay than exercise — learned skills persist)

**Priority sources:**
- Von Ah et al. 2012 (cognitive training in cancer survivors)
- Bray et al. 2018 (cognitive rehabilitation post-chemotherapy)
- ACTIVE trial long-term follow-up (Rebok et al. 2014)

#### ACT_MINDFULNESS — Mindfulness Meditation
**Search terms:** `mindfulness meditation cognitive effects timeline`, `MBSR onset cognitive improvement`, `meditation cessation cognitive decline`

**Expected findings:**
- Onset: 2-4 weeks (stress reduction effects precede cognitive effects)
- Build: 8-12 weeks (standard MBSR is 8 weeks)
- Steady-state: variable (depends heavily on continued practice)
- Decay half-life: 4-8 weeks

**Priority sources:**
- Johns et al. 2016 (mindfulness + cognitive function in cancer)
- Lengacher et al. 2015 (MBSR in breast cancer)

#### ACT_SLEEP_HYGIENE — Sleep Hygiene Protocol
**Search terms:** `sleep hygiene cognitive improvement onset`, `CBT-I cognitive function timeline`

**Expected findings:**
- Onset: 1-2 weeks (sleep quality improvements can be rapid)
- Build: 4-8 weeks
- Steady-state: indefinite (habitual behavior)
- Decay half-life: 2-4 weeks (sleep problems recur quickly without habits)

**Priority sources:**
- Garland et al. 2014 (CBT-I in cancer)
- Savard et al. 2005 (insomnia treatment in cancer patients)

#### ACT_LIGHT_AM — Morning Light Exposure
**Search terms:** `morning light exposure circadian cognition onset`, `bright light therapy cognitive function`

**Expected findings:**
- Onset: 0.5-1 week (circadian entrainment is rapid)
- Build: 2-4 weeks
- Steady-state: while adhering
- Decay half-life: 0.5-1 week (circadian rhythm shifts quickly without light cue)

**Priority sources:**
- Ancoli-Israel et al. 2012 (bright light + fatigue/cognition in cancer)
- Wu et al. 2018 (light therapy systematic review)

#### ACT_SOCIAL_ENGAGE — Social Engagement
**Search terms:** `social engagement cognitive decline prevention`, `social activity onset cognitive benefit`

**Expected findings:**
- Onset: 2-4 weeks (mood/motivation effects early; cognitive effects later)
- Build: 8-16 weeks (social networks take time to establish cognitive stimulus)
- Steady-state: indefinite (habitual behavior)
- Decay half-life: 4-8 weeks

**Priority sources:**
- Fratiglioni et al. 2004 (social network + dementia risk)
- Shankar et al. 2013 (social isolation + cognitive function)

#### ACT_NUTRITION_ANTI_INFLAM — Anti-inflammatory Diet
**Search terms:** `anti-inflammatory diet cognitive function onset`, `Mediterranean diet cognition timeline`, `omega-3 cognitive improvement weeks`

**Expected findings:**
- Onset: 4-8 weeks (anti-inflammatory effects take time; gut microbiome adaptation)
- Build: 12-24 weeks (slow)
- Steady-state: indefinite
- Decay half-life: 4-8 weeks

**Priority sources:**
- Valls-Pedret et al. 2015 (Mediterranean diet + cognition, PREDIMED)
- Yurko-Mauro et al. 2010 (DHA + memory)

### Output CSV

Create: `data/seeds/intervention_kernels.csv`

```csv
kernel_id,action_id,kernel_family,onset_weeks_min,onset_weeks_max,build_weeks,steady_state_weeks_min,steady_state_weeks_max,decay_half_life_weeks,pathway_specific_onset_json,source_citation,version,active,notes
KERN_EXERCISE_AEROBIC,ACT_EXERCISE_AEROBIC,trapezoidal,2.0,4.0,10.0,12.0,52.0,3.0,"{""PW_M01_NEUROINFLAMMATION"": 2, ""PW_M04_NEUROPLASTICITY"": 6}","Campbell 2020; Northey 2019",1,1,"Most evidence; fastest onset via inflammation pathway"
```

---

## 3. Dose Bridges (`dose_bridges_v1`) {#3-dose-bridges}

### What This Table Does

Translates intervention **dose** (minutes of exercise, sessions of CBT, etc.) into
**standardized z-score effects** on target nodes. Uses Emax/Hill dose-response models.

Each action can affect MULTIPLE nodes (e.g., aerobic exercise affects fatigue,
depression, processing speed, etc.), so you need ~2-3 rows per action.

### Key Formula

For `dose_response_family = saturating`:
```
f(dose) = max_effect × dose / (EC₅₀ + dose)
Δz = bridge_gain × f(dose) × bridge_effect_sign
```

For `dose_response_family = linear`:
```
Δz = bridge_gain × (dose / dose_reference) × bridge_effect_sign
```

### Schema (24 columns — key ones)

| Column | Type | Example | What to Research |
|--------|------|---------|-----------------|
| `bridge_id` | TEXT PK | `DBR_AEROBIC__FATIGUE__V1` | You assign |
| `action_id` | TEXT FK | `ACT_EXERCISE_AEROBIC` | From action catalog |
| `output_mode` | ENUM | `to_node` | Usually `to_node` |
| `output_node_id` | TEXT FK | `NODE_SYM_FATIGUE` | Target node |
| `dose_type` | TEXT | `continuous` | Must match action catalog |
| `dose_unit` | TEXT | `minutes` | Must match action catalog |
| `dose_min` | FLOAT | `0.0` | Minimum dose |
| `dose_max` | FLOAT | `90.0` | Maximum feasible dose |
| `dose_reference` | FLOAT | `30.0` | Reference dose (typical session) |
| `dose_response_family` | ENUM | `saturating` | `linear`, `saturating`, or `hill` |
| `dose_response_params_json` | JSON | `{"k": 30, "max": 1.0}` | EC₅₀ and max for saturating |
| `bridge_effect_sign` | INT | `1` or `-1` | Does more dose improve (+1) or worsen (-1)? |
| `bridge_gain` | FLOAT | `0.2` | Δz per unit f(dose) at reference |
| `provenance` | TEXT | citation | Source |

### Research Instructions

**For each action, identify which nodes it affects and the dose-response curve.**

#### Mapping Actions → Nodes (which bridges to create)

| Action | Primary Target Nodes | Expected Sign |
|--------|---------------------|---------------|
| `ACT_EXERCISE_AEROBIC` | `NODE_SYM_FATIGUE` (-1), `NODE_SYM_DEPRESSION` (-1), `NODE_COG_PROC_SPEED` (+1), `NODE_BIO_BDNF` (+1), `NODE_BIO_CRP` (-1) | See sign column |
| `ACT_EXERCISE_RESISTANCE` | `NODE_SYM_FATIGUE` (-1), `NODE_SYM_DECONDITIONING` (-1), `NODE_COG_EXEC_PLANNING` (+1) | |
| `ACT_COGNITIVE_TRAINING` | `NODE_COG_WORK_MEM` (+1), `NODE_COG_ATTN_SUSTAINED` (+1), `NODE_COG_EXEC_PLANNING` (+1) | |
| `ACT_MINDFULNESS` | `NODE_SYM_ANXIETY` (-1), `NODE_SYM_DEPRESSION` (-1), `NODE_BIO_CORTISOL` (-1) | |
| `ACT_SLEEP_HYGIENE` | `NODE_BEH_SLEEP_QUALITY` (+1), `NODE_SYM_SLEEP_DISRUPTION` (-1), `NODE_SYM_FATIGUE` (-1) | |
| `ACT_LIGHT_AM` | `NODE_BEH_SLEEP_QUALITY` (+1), `NODE_SYM_SLEEP_DISRUPTION` (-1) | |
| `ACT_SOCIAL_ENGAGE` | `NODE_SYM_DEPRESSION` (-1), `NODE_BEH_SOCIAL_ENGAGE` (+1), `NODE_BEH_SELF_EFFICACY` (+1) | |
| `ACT_NUTRITION_ANTI_INFLAM` | `NODE_BIO_CRP` (-1), `NODE_BIO_IL6` (-1), `NODE_BEH_DIET` (+1) | |

#### Key Research Questions Per Bridge

For each (action, target_node) pair:
1. **What is the dose-response shape?** Linear? Saturating? Hill?
2. **What is the EC₅₀?** (dose at 50% max effect) — for saturating/hill
3. **What is the bridge_gain?** (SD units of effect per unit dose at reference)
4. **What is the plausible dose range?** (min, max, reference)

**Search terms by action:**
- Exercise: `dose-response exercise fatigue cancer`, `MET-minutes dose-response cognitive function`, `exercise volume cognitive benefit plateau`
- Key paper: Gallardo-Gómez et al. 2022 (exercise EC₅₀ ≈ 625 MET-min/wk for cognitive outcomes)
- Cognitive training: `dose-response cognitive training hours`, `training frequency cognitive improvement`
- Mindfulness: `mindfulness dose minutes stress reduction`, `MBSR session frequency effect`

**Estimating bridge_gain when no dose-response data exists:**
```
bridge_gain ≈ Cohen's_d_from_RCTs / (dose_used_in_RCT / dose_reference)
```
Example: If an RCT found d=0.5 at 150 min/wk exercise, and your dose_reference is 30 min/session:
`bridge_gain ≈ 0.5 / (150/30) = 0.1 Δz per f(dose) unit`

---

## 4. Contraindication Rules (`contraindication_rules_v1`) {#4-contraindication-rules}

### What This Table Does

Safety gating — defines conditions under which interventions are blocked, penalized,
or escalated to clinician review.

### Required Rules (from spec)

The algorithm spec defines 3 mandatory catch-all rules plus domain-specific rules:

#### 3 Mandatory Catch-All Rules

| rule_id | condition_expression | severity | rationale |
|---------|---------------------|----------|-----------|
| `RULE_CATCH_ACTIVE_TREATMENT` | `context.treatment_phase IN ('active_chemo','active_radiation','active_immunotherapy') AND context.toxicity_grade_max >= 2` | `escalate` | Patient on active treatment with Grade 2+ toxicity |
| `RULE_CATCH_RARE_CANCER` | `context.cancer_type NOT IN ('breast','colorectal','lung','prostate','hematological') AND action.intensity > 'light'` | `soft_warn` | Cancer type has limited evidence representation |
| `RULE_CATCH_ZERO_MATCH_RISKY` | `eval_count = 0 AND (context.has_active_treatment OR context.comorbidity_count >= 3 OR context.age > 80)` | `soft_warn` | No specific safety rules fired but patient has risk factors |

#### Domain-Specific Rules to Research

| Action Class | Example Rule | Search Terms |
|-------------|-------------|--------------|
| Physical activity | Block if neuropathy grade ≥ 3 | `exercise contraindication neuropathy cancer`, `ACSM exercise precautions oncology` |
| Physical activity | Block if active bone metastasis + weight-bearing | `bone metastasis exercise safety`, `skeletal precautions exercise cancer` |
| Physical activity | Escalate if cardiotoxicity history | `cardiotoxicity exercise safety cancer`, `anthracycline cardiac exercise` |
| Physical activity | Soft_warn if lymphedema risk | `lymphedema exercise precautions`, `upper body exercise breast cancer lymphedema` |
| Nutrition | Soft_warn if on specific chemo (drug interactions) | `dietary supplement chemotherapy interaction`, `anti-inflammatory diet drug interaction` |
| Light exposure | Block if photosensitizing medication | `photosensitivity medication light therapy` |
| Mindfulness | Soft_warn if active psychosis | `mindfulness contraindication psychosis` |
| All | Escalate if ECOG ≥ 3 (severe debility) | `ECOG performance status exercise oncology` |

**Priority sources:**
- ACSM Exercise Guidelines for Cancer Survivors (Campbell et al. 2019)
- ASCO Survivorship Care Guidelines
- NCI PDQ Cancer Treatment Side Effects
- Schmitz et al. 2019 (exercise oncology safety)

### Schema Key Columns

| Column | What to Fill In |
|--------|----------------|
| `rule_id` | `RULE_[CONDITION]_[ACTION]_V1` |
| `rule_label` | Human-readable description |
| `applies_to_type` | `global`, `action_class`, or `action_id` |
| `applies_to_ref` | The class or action ID (NULL if global) |
| `severity` | `hard_block`, `soft_penalty`, `require_question`, `escalate` |
| `condition_expression` | Machine-evaluable predicate (DSL) |
| `required_inputs_json` | JSON array of all input tokens in condition |
| `unknown_input_policy` | What to do if input missing: `treat_as_false`, `trigger_question`, `escalate` |
| `rationale` | One-sentence safety rationale |
| `provenance` | Citation source |

---

## 5. Biomarker Correlations (`biomarker_correlations_v1`) {#5-biomarker-correlations}

### What This Table Does

Defines 8 correlated biomarker pairs for the block-diagonal residual covariance
matrix D. Without this, the model assumes all biomarkers are independent (which
overstates precision).

### Expected 8 Pairs (from spec §2.6, §2.17.2)

| Pair | node_a_id | node_b_id | Expected ρ | D-block | Search Terms |
|------|-----------|-----------|-----------|---------|--------------|
| 1 | `NODE_BIO_IL6` | `NODE_BIO_TNF` | 0.5-0.7 | inflammatory | `IL-6 TNF-alpha correlation cancer`, `cytokine correlation analysis` |
| 2 | `NODE_BIO_IL6` | `NODE_BIO_CRP` | 0.4-0.6 | inflammatory | `IL-6 CRP correlation`, `inflammatory marker correlation` |
| 3 | `NODE_BIO_CRP` | `NODE_BIO_TNF` | 0.3-0.5 | inflammatory | `CRP TNF-alpha correlation` |
| 4 | `NODE_BIO_CORTISOL` | `NODE_SYM_FATIGUE` | 0.2-0.4 | neuro_stress | `cortisol fatigue correlation cancer`, `HPA axis fatigue` |
| 5 | `NODE_SYM_DEPRESSION` | `NODE_SYM_ANXIETY` | 0.5-0.7 | neuro_stress | `depression anxiety correlation cancer patients` |
| 6 | `NODE_SYM_FATIGUE` | `NODE_SYM_DEPRESSION` | 0.3-0.5 | neuro_stress | `fatigue depression correlation cancer` |
| 7 | `NODE_SYM_FATIGUE` | `NODE_SYM_SLEEP_DISRUPTION` | 0.4-0.6 | neuro_stress | `fatigue sleep disruption correlation cancer` |
| 8 | `NODE_BIO_BDNF` | `NODE_BIO_CORTISOL` | -0.2 to -0.4 | neuro_stress | `BDNF cortisol correlation`, `neurotrophic stress interaction` |

**For each pair, find:**
1. Pearson or Spearman ρ from a cancer cohort study (preferred)
2. If unavailable: ρ from general population meta-analysis
3. SE of ρ (if reported) — for sensitivity analysis
4. Source citation

**Rule:** node_a_id must be alphabetically < node_b_id (canonical ordering).

---

## 6. Normalization References (`normalization_refs_v1`) {#6-normalization-refs}

### What This Table Does

Population reference means + SDs for z-score normalization. When a patient's raw
score arrives (e.g., PSQI = 12), the system converts: `z = (12 - ref_mean) / ref_sd`.

### What Needs Normalization

Every instrument in `instrument_definitions_v1` (67 instruments) ideally needs a
normalization reference. **Priority:** instruments that appear in our evidence.

#### Priority 1 — Instruments in Current Evidence (must have)

| Instrument | Node | Search Terms |
|------------|------|-------------|
| `INST_HVLTR` | Episodic Memory | `HVLT-R normative data cancer`, `Hopkins Verbal Learning Test norms` |
| `INST_TMT_B` | Processing Speed | `Trail Making Test B normative data`, `TMT-B cancer population norms` |
| `INST_COWAT` | Verbal Fluency | `COWAT FAS normative data`, `verbal fluency test norms` |
| `INST_FACTCOG_PCI` | Cog Complaints | `FACT-Cog PCI normative data cancer`, `FACT-Cog scoring norms` |
| `INST_CESD` | Depression | `CES-D normative data cancer`, `CES-D population norms` |
| `INST_FACIT_FATIGUE` | Fatigue | `FACIT-Fatigue normative data cancer`, `FACIT-F norms` |
| `INST_ISL_DR` | Episodic Memory | `CogState ISL normative data`, `International Shopping List norms` |
| `INST_GROTON_MAZE` | Exec Planning | `CogState Groton Maze normative data` |
| `INST_ONEBACK` | Working Memory | `CogState One-Back normative data` |
| `INST_VO2PEAK` | Deconditioning | `VO2peak normative women cancer survivors`, `cardiorespiratory fitness norms` |

#### Priority 2 — Common instruments (should have)

`INST_PHQ9`, `INST_GAD7`, `INST_BFI`, `INST_PSQI`, `INST_MOCA`, `INST_DIGIT_SPAN`,
`INST_CPT`, `INST_STROOP`, `INST_TOL`, `INST_REY_COPY`, `INST_BNT`

### For Each Instrument, Find

| Field | What to Look For |
|-------|-----------------|
| `ref_mean` | Population mean in raw score units |
| `ref_sd` | Population SD |
| `ref_n` | Sample size of normative study |
| `cancer_type` | Which cancer population (or `general_population`) |
| `treatment_phase` | Which treatment phase (or `any`) |
| `is_cancer_specific` | 1 if normed on cancer patients, 0 if general pop |
| `percentile_5/25/50/75/95` | If reported in normative tables |
| `source_citation` | Full citation |

**Preference hierarchy:**
1. Cancer-specific norms (same cancer type + treatment phase) — best
2. Cancer-general norms (mixed cancer types) — good
3. Age-matched general population norms — acceptable
4. General population norms — use with `is_cancer_specific = 0`

---

## 7. Research Strategy {#7-research-strategy}

### Efficient Approach for Deep Research

**Phase 1: Meta-analyses and guidelines (covers most tables)**
Start here — a single well-done meta-analysis or guideline often provides data
for multiple tables:

| Source | Tables It Can Fill |
|--------|-------------------|
| Campbell et al. 2019 (ACSM Exercise Guidelines) | kernels, dose_bridges, contraindications |
| Mustian et al. 2017 (exercise meta-analysis cancer) | dose_bridges (effect sizes by dose) |
| Gallardo-Gómez et al. 2022 (dose-response) | dose_bridges (EC₅₀ per outcome) |
| Felger et al. 2020 (cytokine network in cancer) | biomarker_correlations |
| Wagner et al. 2009 (FACT-Cog validation) | normalization_refs |
| FACIT.org scoring manuals | normalization_refs |
| Schmitz et al. 2019 (exercise oncology safety) | contraindication_rules |
| ASCO Survivorship Guidelines | contraindication_rules |

**Phase 2: Fill gaps from primary studies**
After Phase 1, identify which cells are still empty and search for targeted primary
studies.

**Phase 3: Author-constructed estimates (last resort)**
For cells where no empirical data exists, construct estimates using:
- Adjacent evidence (e.g., exercise detraining half-life from athletic populations)
- Mechanistic reasoning (e.g., inflammation half-life from pharmacokinetic models)
- Conservative defaults (e.g., `bridge_gain = 0.1` when uncertain)

Mark these as `provenance = "author_constructed_v1"` so they can be refined later.

### Research Prompt Template for Deep Research LLM

```
I need to fill the [TABLE_NAME] for the CRCI Bayesian Causal Model system.

CONTEXT: This is a clinical decision support system for cancer-related cognitive 
impairment. It models 63 biomarker/symptom/behavior nodes and 8 intervention actions.

SPECIFIC QUESTION: For [ACTION_ID] ([action label]):
[Insert specific questions from the relevant section above]

REQUIREMENTS:
- Provide exact numerical values with citation (author, year, journal)
- Prefer cancer population data over general population
- State confidence level: HIGH (direct evidence), MEDIUM (adjacent evidence), 
  LOW (author estimate)
- If multiple values exist, provide range and recommended value
- Flag any cancer-type or treatment-phase specificity
```

---

## 8. CSV Templates & Import {#8-csv-templates}

### Where to Put Completed CSVs

```
data/seeds/
  intervention_kernels.csv       ← new
  dose_bridges.csv               ← new
  contraindication_rules.csv     ← new
  biomarker_correlations.csv     ← new
  normalization_refs.csv         ← new
```

### Import Path

These will be loaded by `scripts/bootstrap_db.sh` or by adding a new seed step
to `crci/database/seed_loader.py`. The import uses the same pattern as existing
seeds (actions.csv, pathways.csv, etc.):

```python
# In seed_loader.py, add:
def seed_intervention_kernels(session, csv_path):
    """Load intervention_kernels.csv → intervention_kernels_v1"""
    ...
```

Until the import code exists, you can load manually:
```bash
sqlite3 crci_dev.db ".import --csv data/seeds/intervention_kernels.csv intervention_kernels_v1"
```

### Validation Rules

Before importing, verify:
- All `action_id` values exist in `action_catalog_v1`
- All `node_id` FK references exist in `biomarker_node_definitions_v1`
- All `instrument_id` references exist in `instrument_definitions_v1`
- `onset_weeks_max >= onset_weeks_min`
- `steady_state_weeks_max >= steady_state_weeks_min`
- `decay_half_life_weeks > 0`
- `bridge_effect_sign` is +1 or -1
- `rho` is between -1 and 1
- `ref_sd > 0`

---

## Quick Checklist

- [ ] **Intervention Kernels:** 8 rows (one per action), temporal dynamics researched
- [ ] **Dose Bridges:** ~16-24 rows (2-3 per action), dose-response data from literature
- [ ] **Contraindication Rules:** 3 catch-alls + ~12-17 domain rules, sourced from guidelines
- [ ] **Biomarker Correlations:** 8 pairs, ρ values from cancer cohort studies
- [ ] **Normalization Refs:** Priority 1 (10 instruments) + Priority 2 (11 instruments)
- [ ] All CSVs validated and imported to DB
- [ ] Run algorithm chain tests to verify tables are being read

---

*This guide was generated from the table schemas in `docs/03_database/05_TABLE_SCHEMAS.md`
and algorithm spec in `docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md`.*
