# Extraction Reference — Final Package

> **What this is:** The single authoritative reference for extracting research papers
> into the CRCI database. Replaces all prior scattered docs as the extraction truth.
>
> **Current DB state (2026-02-27):** 4 papers partially extracted (CSVs on disk),
> 0 rows in `edge_evidence_v1`, 0 rows in `edges_v1`. The core evidence tables are empty.
> 18 of 83 tables populated (mostly seed/reference data). **Priority #1 is getting
> basic evidence loaded.**

---

## Table of Contents

1. [The Procedure (What Humans + AI Do)](#1-the-procedure)
2. [What We Extract and Why (5 Knowledge Categories)](#2-what-we-extract-and-why)
3. [Tables Filled Per Phase — Locked Reference](#3-tables-filled-per-phase)
4. [Complexity Assessment — What's Overengineered vs Essential](#4-complexity-assessment)
5. [The Intelligence Question — Are We Capturing Enough?](#5-the-intelligence-question)
6. [Citation Graph & Research Landscape](#6-citation-graph)
7. [Appendix: Table→Purpose Quick Reference](#appendix)

---

## 1. The Procedure

### The Actual Flow

```
Human finds paper
    ↓
Save PDF to data/manual_uploads/pdfs/
    ↓
Claude Code + Extraction Procedure
    ↓
Parse text → Match content to tables that need filling
    ↓
Output: CSV files in data/manual_uploads/structured/<doi-slug>/
    ↓
python scripts/load_evidence_into_db.py --verbose
    ↓
DB populated → Pipeline compiles → Algorithm can run
```

### What the AI Needs in Context

```
ALWAYS:
  extraction_ref/01_PROCEDURE.md       ← Steps
  extraction_ref/06_CSV_TEMPLATES.md   ← Column specs
  extraction_ref/08_NODE_IDS.md        ← 63 node IDs
  extraction_ref/09_EDGE_IDS.md        ← 143 edge IDs
  extraction_ref/10_INSTRUMENT_IDS.md  ← 67 instrument IDs
  extraction_ref/03_SE_DERIVATION.md   ← SE formulas

PER PAPER:
  The paper text (PDF or pasted)
  Any existing CSVs in the paper's folder
```

### What the AI Does

1. **Parse text** — read the paper, identify sections (methods, results, discussion)
2. **Match to tables** — for each thing found, determine which CSV template it fills
3. **Output CSV rows** — exact column values matching template specs
4. **Flag what's missing** — explicitly state what the paper doesn't provide

That's it. No fancy agent protocols. No annotation lifecycle. Just: read paper → fill templates.

---

## 2. What We Extract and Why

Every piece of information from a paper serves one of 5 purposes in the knowledge base.
This is the fundamental mental model.

### Category 1: Edge Evidence + Statistics → Wires the Knowledge Base

**What it is:** "Paper X found that Node A affects Node B with effect size d = 0.3, SE = 0.1"

**Why we need it:** This is the core data. Every edge in our 63-node causal graph needs
quantitative evidence connecting the nodes. Without this, the model has no weights.

**Tables filled:**
| Table | What goes in | Example |
|-------|-------------|---------|
| `edge_evidence_v1` (B6) | One row per reported effect (β, SE, CI, p, N, design) | Exercise → processing speed: d = 0.45, SE = 0.12, N = 50, RCT |
| `subgroup_evidence_v1` (B14) | Interaction effects (modifier × treatment) | APOE-ε4 carriers: effect 2× stronger |
| `population_norms_v1` (B11) | Baseline cognitive scores for z-score normalization | Breast cancer control group HVLT-R mean = 24.3, SD = 5.1 |
| `node_priors_v1` (C3) | Context-matched priors (z-scores relative to healthy norms) | Processing speed in chemo-treated: z = -0.8, SD = 0.5 |
| `biomarker_correlations_v1` (A30) | Inter-node correlations (IL-6 × fatigue r = 0.4) | For the block-diagonal covariance matrix |
| `study_cohort_profiles_v1` (B2) | Demographics, inclusion criteria, cancer context | N=50, 80% female, age 52±8, stage II-III breast |

**Priority: 🔴 CRITICAL — nothing works without edge evidence**

### Category 2: Temporal Data → Adds Time Dimension

**What it is:** "The effect appeared at week 8, peaked at week 16, decayed by month 6 post-cessation"

**Why we need it:** Without temporal data, the model is a static snapshot. With it, we can
predict when interventions start working, how long effects last, and what recovery looks like.

**Tables filled:**
| Table | What goes in | Example |
|-------|-------------|---------|
| `temporal_evidence_v1` (B12) | Timepoint × effect pairs from longitudinal studies | Week 0: d=0, Week 8: d=0.2, Week 16: d=0.4 |
| `intervention_kernels_v1` (A32) | Compiled onset/build/decay parameters per intervention | Exercise: onset 4-8wk, build 12wk, decay half-life 8wk |
| `recovery_trajectories_v1` (A29) | Natural recovery curves post-treatment | Breast/chemo: r_∞=0.85, τ=18mo, γ=0.7 |

**Priority: 🟡 HIGH — needed for temporal predictions (Chain E)**

### Category 3: Action Interventions → Real-World Application Knowledge

**What it is:** "Exercise at 150 min/week of moderate intensity improved cognition,
with 72% adherence. Two adverse events (falls) reported."

**Why we need it:** The model needs to know what interventions are available, how dose
translates to effect, what's safe, and what's realistic for patients.

**Tables filled:**
| Table | What goes in | Example |
|-------|-------------|---------|
| `action_catalog_v1` (A21) | Intervention definitions with dose ranges | ACT_AEROBIC: 0-300 min/wk, step 30 |
| `dose_bridges_v1` (C2) | Dose → effect mappings (Emax/Hill curves) | 150 min/wk → 0.3 SD improvement |
| `dose_evidence_v1` (B13) | Raw dose × effect data points from papers | 75 min: d=0.1, 150 min: d=0.3, 300 min: d=0.35 |
| `intervention_synergy_v1` (A28) | How interventions interact | Exercise + cognitive training: γ = 1.15 (synergistic) |
| `contraindication_rules_v1` (A10) | Safety rules | Block high-intensity during active chemo if platelet < 50k |

**Priority: 🟡 HIGH — needed for dose simulation (Chain D) and safety**

### Category 4: Literary Constraints + Mechanistic Priors → Shapes the Knowledge Base

**What it is:** Information that constrains what the model believes is possible, even
when we don't have direct statistical evidence. Two sub-types:

**4a. Literary Constraints (biological bounds)**
"Cortisol levels cannot exceed X. Cognitive improvement from exercise cannot exceed 2 SD.
Recovery plateaus at 85% of baseline for chemo-treated patients."

These are hard/soft rules that prevent the model from producing impossible states.

**4b. Mechanistic Priors (pathway knowledge)**
"Multiple papers say BDNF mediates exercise→cognition. Animal studies show the effect
operates via TrkB receptor. The pathway exercise→BDNF→neuroplasticity→cognition
is supported by convergent evidence even if direct human RCT data is sparse."

These are literature-informed beliefs about edges that have weak direct evidence but
strong mechanistic support.

**Tables filled:**
| Table | What goes in | Example |
|-------|-------------|---------|
| `literary_constraints_v1` (A9) | Biological bounds, rate limits, floor/ceiling constraints | Cortisol: physiological floor 0.1 µg/dL; cognition recovery caps at r_∞ ≤ 1.0 |
| `literary_mechanistic_priors_v1` (A8) | Literature-based priors for sparse edges | Exercise→BDNF: prior N(0.3, 0.2) based on 15 animal + 3 human studies |
| `observation_noise_v1` (A25) | Measurement reliability that constrains precision | PHQ-9 in cancer: α=0.82, SE multiplier 1.15 (somatic confounding) |
| `normalization_refs_v1` (A24) | Reference statistics for z-score calibration | Healthy adults HVLT-R: mean=28.5, SD=4.8, N=500 |
| `harmonization_rules_v1` (A6) | Conversion formulas (OR→d, r→d, etc.) | OR_to_logOR_per_SD: ln(OR) × √3/π |

**Why this matters for maximizing intelligence:**
Literary constraints and mechanistic priors are how we capture the 75-80% of paper
intelligence that doesn't fit into structured β/SE rows. When a paper says "exercise
benefits plateau above 600 MET-min/week" — that's not an edge_evidence row, that's
a literary constraint on the dose-response curve. When a paper says "this pathway
operates via vagal nerve stimulation" — that's a mechanistic prior.

**Currently: both tables are EMPTY (0 rows). This is a real gap.**

**Priority: 🟡 HIGH — constraints prevent impossible model states; priors fill sparse edges**

### Category 5: Citations + Research Landscape → Expands the Knowledge Base

**What it is:** "This paper cites Smith 2020 and Jones 2019. Authors say 'no RCT has
tested this in colorectal cancer.' They recommend factorial designs."

**Why we need it:** To find more papers worth extracting, to understand which papers
are foundational vs incremental, and to identify gaps in our evidence.

**Tables filled:**
| Table | What goes in | Example |
|-------|-------------|---------|
| `study_registry_v1` (B1) | Paper metadata (DOI, authors, year, design) | Auto-populated from meta.json |
| `acquisition_queue_v1` | Papers worth retrieving (from reference lists, gap analysis) | "Smith 2020 cited in 4 papers on this edge → APS score 8.5" |
| `study_annotations_v1` | Strategic intelligence (research gaps, limitations, recommendations) | "Authors: no RCT in colorectal population" → research_gap annotation |

**Priority: 🟢 MEDIUM — important for growth but system works without it initially**

---

## 3. Tables Filled Per Phase — Locked Reference

### Phase 0: Seed Tables (Load Once, Before Any Papers)

These define the structure of the knowledge base. Loaded from registries and seed CSVs.

| Table | Source | Rows | Status | What It Is (Plain English) |
|-------|--------|------|--------|---------------------------|
| `biomarker_node_definitions_v1` | NODE_REGISTRY.csv | 63 | ✅ Loaded | The 63 things we track (cortisol, BDNF, processing speed, etc.) |
| `edge_relations_definitions_v1` | EDGE_REGISTRY.csv | 141 | ✅ Loaded | The 141 permitted connections between nodes (A→B relationships) |
| `instrument_definitions_v1` | INSTRUMENT_REGISTRY.csv | 67 | ✅ Loaded | The 67 assessment tools (HVLT-R, PHQ-9, actigraphy, etc.) |
| `measure_definitions_v1` | MEASURE_REGISTRY.csv | 82 | ✅ Loaded | The 82 biomarker measurement types (serum cortisol, salivary IL-6, etc.) |
| `pathways_v1` | PATHWAY_REGISTRY.csv | 22 | ✅ Loaded | The 22 mechanistic pathways (neuroinflammation, HPA axis, etc.) |
| `node_search_terms_v1` | seed | 504 | ✅ Loaded | PubMed synonyms per node (for paper discovery) |
| `action_catalog_v1` | seeds/actions.csv | 8 | ✅ Loaded | The 8 intervention types (aerobic exercise, sleep hygiene, etc.) |
| `dose_bridges_v1` | seeds/dose_bridges.csv | 10 | ✅ Loaded | How dose translates to node effects (Emax curves) |
| `baseline_modifier_definitions_v1` | seeds/modifier_rules.csv | 15 | ✅ Loaded | How patient variables adjust edge strength (age, APOE, etc.) |

### Phase 1: Per-Paper Extraction (Repeat for Each Paper)

**Core templates (every paper):**

| # | Template CSV → DB Table | What to Extract | Why |
|---|------------------------|-----------------|-----|
| 1 | `edge_evidence_template.csv` → `edge_evidence_v1` | Every reported effect size with β, SE, N, design | **Wires the knowledge base** — without this, no model weights |
| 2 | `population_norms_template.csv` → `population_norms_v1` | Baseline cognitive scores from control/reference groups | Enables z-score normalization; feeds prior_compiler |
| 3 | `context_priors_template.csv` → `node_priors_v1` | z-scores of this population relative to healthy norms | Tells the model "how impaired is this population at baseline" |

**Conditional templates (when data available):**

| # | Template CSV → DB Table | When to Fill | Why |
|---|------------------------|-------------|-----|
| 4 | `temporal_evidence_template.csv` → `temporal_evidence_v1` | Paper has ≥2 timepoints | Onset/decay timing for temporal kernels |
| 5 | `instrument_evidence_template.csv` → `instrument_evidence_v1` | Paper reports Cronbach's α, ICC, factor loadings | Measurement quality → SE calibration |
| 6 | `correlation_template.csv` → `biomarker_correlations_v1` | Paper reports biomarker inter-correlations | Block-diagonal covariance matrix for Bayesian update |

**Extended templates (DEEP mode / when available):**

| # | Template CSV → DB Table | When to Fill | Why |
|---|------------------------|-------------|-----|
| 7 | `dose_evidence_template.csv` → `dose_evidence_v1` | Paper has multiple dose levels | Calibrates dose-response curves |
| 8 | `subgroup_evidence_template.csv` → `subgroup_evidence_v1` | Paper reports interaction effects | Personalizes model to patient subgroups |
| 9 | `study_cohort_profile_template.csv` → `study_cohort_profiles_v1` | DEEP mode | Transportability scoring (how similar to target population) |

**meta.json (every paper):**

| What | → DB Table | Why |
|------|-----------|-----|
| Paper metadata + risk of bias | `study_registry_v1` | Track what we've extracted; bias assessment |

### Phase 2: Curation Tables (Fill from Literature Review, Not Per-Paper)

These tables are filled by reviewing accumulated evidence across papers, not from
single paper extraction. They represent synthesized knowledge.

| Table | How to Fill | Rows Now | Why It Matters | Blocks What |
|-------|------------|---------|----------------|-------------|
| `literary_constraints_v1` (A9) | Review biological literature; define bounds per node/measure | **0** | Prevents impossible model states (negative cortisol, >100% recovery) | Chain D plausibility checks |
| `literary_mechanistic_priors_v1` (A8) | Review pathway literature; define priors for sparse edges | **0** | Fills edges with no direct RCT evidence using mechanistic support | P4 prior selection |
| `observation_noise_v1` (A25) | Review psychometric literature; fill reliability per instrument | 13 | SE calibration — unreliable instruments get wider error bars | Chain C observation mapper |
| `normalization_refs_v1` (A24) | Collect healthy population norms from published norm studies | **0** | z-score reference — "what is normal?" | Chain C z-scoring |
| `harmonization_rules_v1` (A6) | Define conversion formulas (coded, not from papers) | **0** | OR→d, r→d, HR→logOR conversions | P2 harmonization |
| `intervention_kernels_v1` (A32) | Synthesize onset/build/decay from temporal evidence | **0** | Temporal prediction — "when does exercise start working?" | Chain E temporal |
| `recovery_trajectories_v1` (A29) | Synthesize recovery curves from longitudinal studies | **0** | Natural recovery baseline — "what happens without intervention?" | Chain E recovery |
| `mid_thresholds_v1` (A33) | Look up Minimally Important Difference per domain | **0** | Clinical significance thresholds | Chain F scoring |
| `contraindication_rules_v1` (A10) | Review safety literature; define hard stops | **0** | "Don't recommend this if..." | Chain D safety |

### Phase 3: Pipeline-Generated Tables (Automated, No Manual Work)

| Table | Generated By | From What | Why |
|-------|-------------|----------|-----|
| `edges_v1` (C1) | P4 edge_writer / load_evidence_into_db Step 6 | IVW aggregation of `edge_evidence_v1` | Compiled edge parameters for the runtime engine |
| `publication_bias_results_v1` (C7) | P4b publication_bias.py | Egger's regression on grouped evidence | Trust calibration — inflates SE for biased edges |
| `chain_validation_results_v1` (C6) | P5 chain_validator.py | Chain-vs-direct pathway comparison | Detects mechanistic inconsistencies |
| `edge_param_builds_v1` (B7) | P4 edge_writer.py | Build audit metadata | Reproducibility trace |

### Phase 4: Runtime Tables (Written During Engine Execution)

Not manually filled. Written when a patient runs through the system.

| Table | Written By | What It Stores |
|-------|-----------|---------------|
| `state_snapshots_v1` | Chain C | Patient posterior state (θ̂, Σ) |
| `scenario_definitions_v1` / `scenario_items_v1` | Chain D | What-if scenarios |
| `simulation_trace_v1` | Chain D | MC draw results |
| `schedule_plans_v1` / `schedule_items_v1` | Runtime | Optimized intervention plans |
| `recommendation_runs_v1` | Runtime | Session header |
| `decision_trace_v1` | Chain D | Why the model chose what it chose |
| + 6 more trace tables | Various | Audit trail |

---

## 4. Complexity Assessment — What's Overengineered vs Essential

### Honest Assessment

| Component | Verdict | Reasoning |
|-----------|---------|-----------|
| **12 CSV templates** | ✅ **Right-sized** | Each maps to a real table with a real purpose. Nothing redundant. |
| **3 extraction modes (DEEP/STANDARD/SHALLOW)** | ✅ **Useful** | Different papers yield different data. Avoids wasted effort on shallow papers. |
| **11 extraction agents (AG01–AG11)** | ⚠️ **Overengineered for now** | The automated LLM pipeline is fully built but we haven't loaded a single paper through it. Manual CSV extraction works. Agents are for scaling later — not needed for the first 50 papers. |
| **Annotation lifecycle (raw→reviewed→promoted)** | ⚠️ **Premature** | Promotion thresholds, convergence detection, lifecycle management — all for 0 annotations. Build this after we have 100+ papers, not before. |
| **22 content dimensions (PIMP protocol)** | ⚠️ **Aspirational overkill** | The 5-category model above (edge evidence, temporal, interventions, constraints, citations) covers the same ground without the complexity. The 22-dimension taxonomy adds granularity we don't need yet. |
| **7-layer SE calibration** | ✅ **Essential** | This is a real statistical need. Literature-validated SE decomposition. Keep it. |
| **Trust boundary (numeric parsing + quarantine)** | ✅ **Essential** | Prevents garbage data from entering the DB. Keep it. |
| **P7 compilers (6 families)** | ✅ **Essential** | Each compiler turns raw evidence into usable parameters. All needed. |
| **study_annotations_v1 (23-column EAV table)** | ⚠️ **Over-specified for now** | The annotation table is well-designed but we have 0 rows. For now, a simpler approach: capture non-numeric intelligence as notes fields in existing templates, or a simple key-value file per paper. Promote to the full schema when we have enough papers to benefit. |
| **Acquisition feedback loop** | 🟢 **Future** | Makes sense when we have 200+ papers and need directed search. Not now. |

### What to Simplify Now

**Don't remove anything.** The code is built and correct. Instead, **ignore the complexity
and use the simple path:**

1. **Manual CSV extraction** (not LLM agents) for the next 20-30 papers
2. **5 knowledge categories** (not 22 content dimensions) as the mental model
3. **Notes fields + meta.json** for qualitative intelligence (not annotation lifecycle)
4. **Load via `load_evidence_into_db.py`** (not the full pipeline.py)

Once we have 50+ papers loaded and the model actually runs, THEN activate:
- The LLM agent pipeline for scaling
- The annotation table for strategic intelligence
- The promotion monitor for knowledge evolution

---

## 5. The Intelligence Question

### "Are we capturing enough information from each paper?"

**Short answer:** The 12 CSV templates capture the core structured data well.
The gap is in **semi-structured qualitative intelligence** — things that don't fit
neatly into β/SE rows but still matter for the model.

### What We're Missing (Ranked by Priority)

| # | Intelligence Type | Currently Captured? | Impact if Missing | Practical Fix |
|---|------------------|--------------------|--------------------|--------------|
| 1 | **Biological bounds / constraints** | ❌ `literary_constraints_v1` = 0 rows | Model can produce impossible states (negative concentrations, >100% recovery) | **Fill from review papers and textbooks.** Not per-paper — synthesized knowledge. Start with 10-15 constraints for the most important nodes. |
| 2 | **Healthy population norms** | ❌ `normalization_refs_v1` = 0 rows | Can't convert raw scores to z-scores; priors are uncalibrated | **Fill from published norm studies.** HVLT-R, TMT, COWAT etc. have published norms. ~20 rows needed. |
| 3 | **Measurement reliability** | ⚠️ 13 rows in `observation_noise_v1` | SE calibration is approximate for uncovered instruments | Continue filling as papers report psychometrics. |
| 4 | **Conversion formulas** | ❌ `harmonization_rules_v1` = 0 rows | Can't convert OR→d, r→d etc. across papers | **Define ~10 standard conversion rules.** These are mathematical, not empirical. |
| 5 | **Temporal kernel parameters** | ❌ `intervention_kernels_v1` = 0 rows | Temporal predictions use defaults only | **Synthesize from temporal_evidence_v1** after loading 10+ papers with longitudinal data. |
| 6 | **Dose-response shapes** | ⚠️ Templates exist, 0 rows in `dose_evidence_v1` | Dose optimization uses linear assumption only | Extract dose data from multi-arm trials. |
| 7 | **Safety rules** | ❌ `contraindication_rules_v1` = 0 rows | No safety gates (the model could recommend dangerous things) | **Fill from clinical guidelines.** Not from papers — from ACSM, NCCN guidelines. |
| 8 | **Mechanistic priors** | ❌ `literary_mechanistic_priors_v1` = 0 rows | Sparse edges have flat (uninformative) priors | Fill from review papers. Identify edges with strong mechanistic support but weak direct evidence. |
| 9 | **Author-identified limitations & gaps** | ❌ 0 annotations | Missing information for SE inflation and directed acquisition | Low priority. Add notes field to meta.json for now. |

### Practical Intelligence Extraction Strategy

For each paper, ask these questions in order:

```
MUST EXTRACT (every paper):
  □ What causal relationships are tested? → edge_evidence
  □ What are the baseline cognitive scores? → population_norms  
  □ How impaired is this population? → context_priors (node_priors)

SHOULD EXTRACT (when available):
  □ Multiple timepoints? → temporal_evidence
  □ Psychometric properties reported? → instrument_evidence
  □ Biomarker correlations reported? → correlation
  □ Multiple dose levels? → dose_evidence
  □ Subgroup analyses? → subgroup_evidence

CAPTURE AS NOTES (in meta.json or confidence_note):
  □ Author-stated limitations
  □ Suggested mechanisms not in the DAG
  □ Research gaps identified
  □ Safety concerns mentioned
  □ Dose-response pattern observations (plateau, threshold, U-shape)
  □ Adherence rates and dropout
```

When we accumulate enough notes on a topic (e.g., 5+ papers mention APOE as unmeasured
confounder), that becomes a curation task to fill `literary_constraints_v1` or
`literary_mechanistic_priors_v1`.

---

## 6. Citation Graph & Research Landscape

### How Papers Relate to Each Other

Papers in our system have different roles. Understanding this helps prioritize extraction:

```
FOUNDATIONAL KNOWLEDGE PAPERS
  │  Set literary constraints
  │  Define biological bounds
  │  Examples: Review articles, textbook chapters, 
  │  animal studies establishing mechanisms
  │  → Fill: literary_constraints_v1, literary_mechanistic_priors_v1
  │
  ├─── META-ANALYSES / SYSTEMATIC REVIEWS
  │      Pool effects across studies
  │      Identify research gaps explicitly
  │      Richest source of compiled evidence
  │      → Fill: edge_evidence (pooled), research gap annotations
  │
  ├─── RCTs (The Gold Standard)
  │      Direct causal evidence
  │      Richest for: dose-response, temporal, adherence, safety
  │      → Fill: edge_evidence, temporal, dose, subgroup, cohort
  │
  ├─── OBSERVATIONAL / COHORT STUDIES
  │      Associational evidence (weaker but broader)  
  │      Good for: correlations, population norms, subgroups
  │      → Fill: edge_evidence, correlations, population_norms
  │
  └─── PSYCHOMETRIC / VALIDATION STUDIES
         Measurement quality evidence
         → Fill: instrument_evidence, observation_noise
```

### Citation Utility for Extraction Queue

When extracting a paper, its reference list is a discovery tool:

| What to Look For | Why | Action |
|-----------------|-----|--------|
| Papers cited as "foundational" or "consistent with" | Core evidence for the same edge | Add to extraction queue (high priority) |
| Papers cited in a contradiction | Conflicting evidence → publication bias signal | Add to extraction queue (high priority) |
| Papers cited for methodology only | Not evidence-bearing | Skip |
| Review/MA papers cited for context | May contain pooled estimates | Add to queue (medium priority) |
| Papers in "Future Research" section | May not exist yet | Note the gap in meta.json |

---

## Appendix: Complete Table→Purpose Quick Reference

### Tables That Extraction Fills Directly (14 tables)

| Table | Category | Plain English Purpose |
|-------|----------|---------------------|
| `edge_evidence_v1` | Edge Evidence | "Paper X says A→B with effect size d and precision SE" |
| `population_norms_v1` | Edge Evidence | "Control group scored M=24.3, SD=5.1 on the HVLT-R" |
| `node_priors_v1` | Edge Evidence | "This cancer population is 0.8 SD below healthy norms on processing speed" |
| `temporal_evidence_v1` | Temporal | "At week 8 the effect was 0.2, at week 16 it was 0.4" |
| `instrument_evidence_v1` | Temporal | "The HVLT-R has Cronbach's α = 0.87 in this cancer population" |
| `biomarker_correlations_v1` | Edge Evidence | "IL-6 and fatigue correlate at r = 0.42" |
| `dose_evidence_v1` | Interventions | "At 150 min/wk the effect was 0.3, at 300 min/wk it was 0.35" |
| `subgroup_evidence_v1` | Edge Evidence | "The effect was 2× stronger in APOE-ε4 carriers" |
| `study_cohort_profiles_v1` | Edge Evidence | "N=50, 80% female, age 52±8, stage II-III breast cancer" |
| `profile_data_streams_v1` | Edge Evidence | "Used actigraphy for 14 days + HVLT-R at 3 visits" |
| `stream_timepoints_v1` | Temporal | "Measurement at baseline, week 8, week 16, month 6" |
| `ontology_links_v1` | Citations | "Study X provides evidence for edge Y" |
| `study_registry_v1` | Citations | "Paper metadata: DOI, authors, year, design, cancer type" |
| `study_annotations_v1` | Citations | "Author says: no RCT in colorectal population" |

### Tables That Curation Fills (Synthesized Knowledge, Not Per-Paper)

| Table | Category | Plain English Purpose | Priority |
|-------|----------|---------------------|----------|
| `literary_constraints_v1` | Constraints | "Cortisol can't go below 0. Recovery caps at 100%." | 🔴 HIGH |
| `literary_mechanistic_priors_v1` | Constraints | "Strong mechanistic evidence says exercise→BDNF with prior N(0.3, 0.2)" | 🔴 HIGH |
| `normalization_refs_v1` | Constraints | "Healthy adults score 28.5±4.8 on HVLT-R (N=500)" | 🔴 HIGH |
| `harmonization_rules_v1` | Constraints | "To convert OR to d: d = ln(OR) × √3/π" | 🔴 HIGH |
| `intervention_kernels_v1` | Interventions | "Exercise onset: 4-8wk, build: 12wk, decay half-life: 8wk" | 🟡 HIGH |
| `recovery_trajectories_v1` | Interventions | "Breast/chemo recovery: r_∞=0.85, τ=18mo" | 🟡 HIGH |
| `mid_thresholds_v1` | Constraints | "MID for processing speed = 0.3 SD (clinically meaningful)" | 🟡 MEDIUM |
| `contraindication_rules_v1` | Interventions | "Block vigorous exercise if platelets < 50k" | 🟡 MEDIUM |
| `observation_noise_v1` | Constraints | "FACT-Cog PCI: α=0.92, SE multiplier 1.0 in cancer" | ⚠️ Partial (13 rows) |

### Tables That Are Seed-Loaded (Don't Touch)

| Table | Rows | What It Is |
|-------|------|-----------|
| `biomarker_node_definitions_v1` | 63 | The DAG nodes |
| `edge_relations_definitions_v1` | 141 | The DAG edges |
| `instrument_definitions_v1` | 67 | Assessment instruments |
| `measure_definitions_v1` | 82 | Measurement definitions |
| `pathways_v1` | 22 | Mechanistic pathways |
| `action_catalog_v1` | 8 | Interventions |
| `dose_bridges_v1` | 10 | Dose→effect mappings |
| `baseline_modifier_definitions_v1` | 15 | Patient modifiers |
| `node_search_terms_v1` | 504 | PubMed search synonyms |

### Tables That Are Auto-Generated (Never Manually Fill)

| Table | Generated By | Plain English |
|-------|-------------|--------------|
| `edges_v1` | P4/Step 6 | Compiled version of all edge_evidence (pooled β, SE) |
| `publication_bias_results_v1` | P4b | Egger's test results per edge |
| `chain_validation_results_v1` | P5 | Chain-vs-direct pathway consistency checks |
| `state_snapshots_v1` | Chain C | Patient state during runtime |
| `scenario_definitions_v1` | Chain D | What-if scenarios during runtime |
| `simulation_trace_v1` | Chain D | MC simulation results |
| + 10 more output/trace tables | Runtime | Session-level audit trail |

---

## Priority Execution Order

### Immediate (Do Now)

| # | Action | Impact |
|---|--------|--------|
| 1 | **Run `load_evidence_into_db.py`** to load 4 existing paper extractions | Gets `edge_evidence_v1` from 0 → ~18 rows; `edges_v1` from 0 → ~15 compiled edges |
| 2 | **Extract 10 more high-value papers** using manual CSV approach | Broadens edge coverage from ~5 to ~20 edges |
| 3 | **Fill `harmonization_rules_v1`** with standard conversion formulas | Enables OR→d, r→d conversion across papers |
| 4 | **Fill `normalization_refs_v1`** with published cognitive norms | Enables accurate z-score normalization |

### Next (After Immediate)

| # | Action | Impact |
|---|--------|--------|
| 5 | Fill `literary_constraints_v1` with 15-20 biological bounds | Prevents impossible model outputs |
| 6 | Fill `literary_mechanistic_priors_v1` for 10 sparse edges | Better priors for poorly-evidenced edges |
| 7 | Fill `intervention_kernels_v1` for 8 interventions | Enables temporal predictions |
| 8 | Fill `contraindication_rules_v1` from clinical guidelines | Safety gates for recommendations |
| 9 | Fill `observation_noise_v1` for remaining instruments | Better SE calibration |

### Later (After System Runs End-to-End)

| # | Action | Impact |
|---|--------|--------|
| 10 | Activate LLM extraction pipeline for scaling | 10× extraction throughput |
| 11 | Enable annotation table for strategic intelligence | Self-improving evidence acquisition |
| 12 | Fill remaining design/policy tables for full runtime | Complete patient-facing system |

---

*Generated 2026-02-27. Based on actual DB state audit and full codebase review.*
