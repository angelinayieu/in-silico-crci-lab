# CRCI Extraction Procedure

> **THE** single-source-of-truth procedure for extracting a research paper into
> the CRCI database. This document governs what both the AI and the human do.
> Follow Steps 0–10 in order. Skip only what the paper doesn't provide.
>
> **All CSV column names match DB column names exactly.**
> See `06_CSV_TEMPLATES.md` for authoritative column specs.

---

## AI Session Setup

When starting an extraction session, the AI must have these files in context:

### Always Load (Pinned Context)

| # | File | Purpose |
|---|------|---------|
| 1 | **This file** (`extraction_ref/01_PROCEDURE.md`) | Step-by-step extraction procedure |
| 2 | `extraction_ref/03_SE_DERIVATION.md` | SE/effect-size derivation formulas |
| 3 | `extraction_ref/04_CONTROLLED_VOCAB.md` | All enum values and naming conventions |
| 4 | `extraction_ref/06_CSV_TEMPLATES.md` | Exact CSV column specifications (12 templates) |
| 5 | `extraction_ref/08_NODE_IDS.md` | All 63 valid node IDs |
| 6 | `extraction_ref/09_EDGE_IDS.md` | All ~143 valid edge IDs |
| 7 | `extraction_ref/10_INSTRUMENT_IDS.md` | All 67 valid instrument IDs |
| 8 | `extraction_ref/EXTRACTION_LOG.md` | What's already extracted (avoid duplicates) |

### Per Paper

- The paper's PDF (attached or pasted as text)

### On Demand (Load If Needed)

| File | When |
|------|------|
| `extraction_ref/05_DB_SCHEMA.md` | If DB column questions arise |
| `extraction_ref/07_CSV_TO_DB_MAP.md` | If CSV→DB mapping questions arise |
| `extraction_ref/11_QUALITY_CHECKLIST.md` | At end of extraction |
| `registries/EDGE_REGISTRY.csv` | If adding new edges |
| `registries/INSTRUMENT_REGISTRY.csv` | If adding new instruments |
| `registries/NODE_REGISTRY.csv` | If verifying node IDs |

### System Prompt (Paste at Session Start)

```
You are extracting evidence from a cancer-related cognitive impairment (CRCI)
research paper into the CRCI database.

YOUR TASK: Read the paper, identify all extractable causal relationships,
and output structured CSV files ready for database loading.

RULES:
1. Every edge_relation_id MUST exist in the edge registry (09_EDGE_IDS.md).
   If the relationship isn't registered, STOP and flag for registry addition.
2. Every node_id MUST exist in the node registry (08_NODE_IDS.md).
3. Every instrument_id MUST exist in the instrument registry (10_INSTRUMENT_IDS.md).
4. Always derive SE when not directly reported (see 03_SE_DERIVATION.md).
5. Use Cohen's d as the default effect size metric. Convert if needed.
6. Follow extraction_ref/01_PROCEDURE.md Steps 0–10 in order.
7. YOU create the CSV files on disk and run the load pipeline.
8. Report what you CANNOT extract as explicitly as what you CAN.

SIGN CONVENTION:
- Positive beta = outcome improves (cognition ↑, symptoms ↓)
- Report the PAPER's sign, document it, let the pipeline harmonize

OUTPUT: CSV files saved to data/manual_uploads/structured/<doi-slug>/,
        meta.json, pipeline run, EXTRACTION_LOG entry.
```

---

## Quick Reference

| Item | Count |
|------|-------|
| Template CSV files | 12 evidence types |
| DB tables filled by extraction | 12 (see §Template-to-Table Map) |
| Pipeline steps (auto) | 12 (run by `load_evidence_into_db.py`) |
| Registry files to check | 3 (edges, nodes, instruments) |

### Template-to-Table Map

Every CSV template maps to exactly one DB table. **Know these mappings.**

| # | Template CSV | → DB Table | Ext Cols | DB Cols | Category |
|---|-------------|-----------|----------|---------|----------|
| 1 | `edge_evidence_template.csv` | `edge_evidence_v1` | 28 | 107 | Core (REQUIRED) |
| 2 | `population_norms_template.csv` | `population_norms_v1` | 9 | 21 | Core |
| 3 | `context_priors_template.csv` | **`node_priors_v1`** ⚠️ | 9 | 14 | Core |
| 4 | `temporal_evidence_template.csv` | `temporal_evidence_v1` | 8 | 19 | Conditional |
| 5 | `instrument_evidence_template.csv` | `instrument_evidence_v1` | 15 | 25 | Conditional |
| 6 | `correlation_template.csv` | **`biomarker_correlations_v1`** ⚠️ | 6 | 11 | Conditional |
| 7 | `dose_evidence_template.csv` | `dose_evidence_v1` | 17 | 18 | Extended |
| 8 | `subgroup_evidence_template.csv` | `subgroup_evidence_v1` | 16 | 17 | Extended |
| 9 | `study_cohort_profile_template.csv` | `study_cohort_profiles_v1` | 25 | 33 | Extended |
| 10 | `profile_data_stream_template.csv` | `profile_data_streams_v1` | 21 | 25 | Extended |
| 11 | `stream_timepoint_template.csv` | `stream_timepoints_v1` | 11 | 11 | Extended |
| 12 | `ontology_link_template.csv` | `ontology_links_v1` | 11 | 11 | Extended |

> ⚠️ **Table name warnings:**
> - `context_priors_template.csv` loads into **`node_priors_v1`** (NOT `context_priors_v1`)
> - `correlation_template.csv` loads into **`biomarker_correlations_v1`** (NOT `correlation_evidence_v1`)

### Extraction Modes

| Mode | Triggers | Templates to Fill |
|------|----------|-------------------|
| **DEEP** | RCT + cancer population + cognitive primary outcome | All 12 templates + meta.json |
| **STANDARD** | Cohort/observational + cognitive outcomes | Templates 1–6 + meta.json |
| **SHALLOW** | Case report / animal / biomarker-only | Template 1 only + meta.json |

---

## Step 0 — Classify the Paper

Read the abstract and methods. Assign an extraction mode:

**DEEP mode triggers** (ALL must be true):
- `study_design ∈ {RCT, crossover_RCT}`
- `cancer_type ≠ null`
- At least one cognitive instrument used as a primary outcome

**STANDARD mode:** Any study with cognitive outcomes that doesn't qualify for DEEP.
**SHALLOW mode:** Case reports, animal studies, biomarker-only papers with no cognitive outcomes.

---

## Step 1 — Check Registries

**Before extracting ANY data**, verify the paper's entities exist in the registries.

### 1a. Edge Check → `registries/EDGE_REGISTRY.csv`

For each causal or associational relationship the paper tests:
- If edge exists → record the `edge_relation_id` (e.g., `ER_ACTIVITY_PROC_SPEED`)
- If edge is NEW → add a row to EDGE_REGISTRY.csv first (see `04_CONTROLLED_VOCAB.md` for column spec)

### 1b. Instrument Check → `registries/INSTRUMENT_REGISTRY.csv`

For each cognitive test, questionnaire, or biomarker assay used:
- If instrument exists → record the `instrument_id` (e.g., `INST_HVLTR`)
- If instrument is NEW → add to INSTRUMENT_REGISTRY.csv with all required columns

### 1c. Node Check → `registries/NODE_REGISTRY.csv`

Verify the paper's constructs map to existing nodes:
- If a construct has NO corresponding node → flag as `REVIEW_TASK` (do NOT invent nodes)

---

## Step 2 — Create Paper Subfolder & Templates

The AI creates the folder and copies the required templates:

```bash
# DOI convention: replace / with _
DOI_SLUG="10.xxxx_j.JOURNAL.YEAR.ISSUE.PAGE"
DEST="data/manual_uploads/structured/$DOI_SLUG"
mkdir -p "$DEST"

# Copy templates based on extraction mode (Step 0)
# DEEP: all 12, STANDARD: 1-6, SHALLOW: 1 only
cp data/templates/edge_evidence_template.csv       "$DEST/"
cp data/templates/population_norms_template.csv    "$DEST/"
cp data/templates/context_priors_template.csv      "$DEST/"
cp data/templates/temporal_evidence_template.csv   "$DEST/"
cp data/templates/instrument_evidence_template.csv "$DEST/"
cp data/templates/correlation_template.csv         "$DEST/"

# Extended templates (DEEP mode)
cp data/templates/dose_evidence_template.csv       "$DEST/"
cp data/templates/subgroup_evidence_template.csv   "$DEST/"
cp data/templates/study_cohort_profile_template.csv "$DEST/"
cp data/templates/profile_data_stream_template.csv "$DEST/"
cp data/templates/stream_timepoint_template.csv    "$DEST/"
cp data/templates/ontology_link_template.csv       "$DEST/"
```

> **The AI writes extracted data directly into these CSV files.**
> Do NOT output markdown tables for the human to copy — write the actual .csv files.

---

## Step 3 — Fill Core Templates

### 3a. `edge_evidence_template.csv` → `edge_evidence_v1` — REQUIRED

One row per causal/associational relationship reported. This is the **primary evidence table**.

**For each reported effect (28 columns):**

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI (lookup key → resolved to `study_id` by importer) |
| `edge_relation_id` | From EDGE_REGISTRY (Step 1a). E.g. `ER_ACTIVITY_PROC_SPEED` |
| `effect_value_reported` | Standardized effect size — prefer Cohen's d |
| `se_reported` | Standard error — derive if needed (see `03_SE_DERIVATION.md`) |
| `effect_type_reported` | What the paper actually reports: `cohens_d`, `mean_diff`, `odds_ratio`, etc. |
| `effect_size_type` | `BETWEEN_GROUP` / `WITHIN_GROUP` / `PRE_POST_CHANGE` |
| `N_effect` | Analysis N (not enrollment N) |
| `study_design` | `RCT`, `cohort`, `cross_sectional`, etc. |
| `cancer_type` | `breast`, `mixed`, `lung`, etc. |
| `treatment_phase` | `active_treatment`, `early_recovery`, etc. |
| `upstream_instrument_id` | From INSTRUMENT_REGISTRY (Step 1b). E.g. `INST_HVLTR` |
| `se_derivation_level` | `reported` / `from_ci` / `from_p_value` / `from_sd_n` / `fallback_4_over_n` |
| `ci_low_reported` | 95% CI lower bound (if available) |
| `ci_high_reported` | 95% CI upper bound (if available) |
| `p_value` | Reported p-value |
| `n_treatment` | Treatment arm N |
| `n_control` | Control arm N |
| `sd_x` | SD in predictor/treatment group |
| `sd_y` | SD in outcome/control group |
| `rob_overall` | `low` / `moderate` / `high` / `critical` |
| `pub_year` | Publication year |
| `covariates_adjusted` | Comma-separated covariate list |
| `endpoint_vs_change` | `endpoint` / `change` |
| `comparison_arm_label` | E.g. `"HIIT vs CON"` |
| `shared_control_flag` | `true` if control arm shared across comparisons |
| `cancer_validation_status` | `validated` / `not_validated` / `unknown` |
| `extraction_snippet` | Verbatim quote from paper |
| `notes` | Free text derivation notes |

Full column spec: see `06_CSV_TEMPLATES.md` §1.

> **All column names match `edge_evidence_v1` DB columns exactly.** Only `doi` is a lookup key.

**Deriving Cohen's d when not directly reported:**

```
From means ± SD:    d = (M_tx - M_ctrl) / SD_pooled
From t-statistic:   d = 2t / √(df)
From F(1,df):       d = 2√(F/N)
From odds ratio:    d = ln(OR) × √3 / π
From correlation:   d = 2r / √(1 - r²)
```

**Multi-arm trials:** Create one row per arm vs. control. Set `shared_control_flag = true` if arms share a control group.

### 3b. `population_norms_template.csv` → `population_norms_v1` — RECOMMENDED

Baseline descriptive statistics for the control/reference group. **9 columns.**

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI |
| `node_id` | From NODE_REGISTRY — the cognitive construct measured |
| `instrument_id` | From INSTRUMENT_REGISTRY |
| `mean_raw` | Control group baseline mean (raw score) |
| `sd_raw` | Control group baseline SD (must be > 0) |
| `N` | Control group N |
| `cancer_type` | Paper's cancer population |
| `treatment_phase` | Timing of assessment |
| `age_range` | E.g. `"45-65"` (optional) |

> Column names match `population_norms_v1` directly.

### 3c. `context_priors_template.csv` → **`node_priors_v1`** — RECOMMENDED

Convert population norms to z-scores relative to published norms. **9 columns.**

```
z = (observed_mean - population_mean) / population_SD
```

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI |
| `node_id` | From NODE_REGISTRY |
| `cancer_type` | Scoping dimension |
| `treatment_phase` | Scoping dimension |
| `mean` | z-score (computed above) — maps to `node_priors_v1.mean` |
| `sd` | Default 0.5 unless strong justification — maps to `node_priors_v1.sd` |
| `source_type` | `published_norm` / `local_control_group` / `expert` |
| `n_contributing` | Number of studies contributing (optional) |
| `notes` | Derivation notes |

> If no published norms available, use control group baseline and set `source_type = local_control_group`.

---

## Step 4 — Fill Conditional Templates (When Data Available)

### 4a. `temporal_evidence_template.csv` → `temporal_evidence_v1`

**Fill when:** Paper has ≥2 longitudinal timepoints for the same effect. **8 columns.**

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI |
| `edge_relation_id` | Same as in edge_evidence |
| `timepoint_weeks` | Weeks from baseline |
| `effect` | Effect size at this timepoint |
| `se` | SE at this timepoint |
| `is_recovery` | `0` = intervention period, `1` = follow-up/recovery |
| `N` | Sample size at this timepoint |
| `provenance_ref` | Table/figure reference (optional) |

> The importer maps `edge_relation_id` to `action_id` in the DB.

### 4b. `instrument_evidence_template.csv` → `instrument_evidence_v1`

**Fill when:** Paper reports psychometric properties (Cronbach's α, ICC, factor loadings). **15 columns.**

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI |
| `instrument_id` | From INSTRUMENT_REGISTRY |
| `instrument_name` | Full instrument name |
| `instrument_subscale` | Subscale name if applicable |
| `cronbachs_alpha` | Cronbach's α (if reported) |
| `se_alpha` | SE of α (if reported) |
| `test_retest_reliability` | Test-retest ICC (if reported) |
| `factor_loading_mean` | Mean factor loading (if reported) |
| `sem_value` | Standard error of measurement (if reported) |
| `N` | Sample size |
| `cancer_type` | Cancer population |
| `treatment_phase` | Treatment phase |
| `cancer_validated` | `true` / `false` — validated in cancer population? |
| `provenance_ref` | Table/figure reference (optional) |
| `notes` | Additional notes (optional) |

### 4c. `correlation_template.csv` → **`biomarker_correlations_v1`**

**Fill when:** Paper reports inter-domain correlations (e.g., IL-6 × fatigue r, BDNF × memory r). **6 columns.**

| Field | How to Fill |
|-------|------------|
| `doi` | Paper DOI → stored as `source_citation` |
| `node_a_id` | First node ID (from NODE_REGISTRY) |
| `node_b_id` | Second node ID (from NODE_REGISTRY) |
| `rho` | Pearson/Spearman r (must be in [-1, 1]) |
| `N` | Sample size |
| `partial_or_zero` | `partial` / `zero_order` |

---

## Step 5 — Fill Extended Templates (DEEP Mode / When Data Available)

### 5a. `dose_evidence_template.csv` → `dose_evidence_v1`

**Fill when:** Paper reports dose-response data (multiple dose levels, dose-response curves). **17 columns.**

| Field | How to Fill |
|-------|------------|
| `action_id` | FK to action_catalog_v1 (e.g., exercise type) |
| `intervention_type` | `aerobic_exercise`, `resistance_training`, etc. |
| `dose_level` | Numeric dose amount (e.g., 150 for 150 min/wk) |
| `dose_unit` | `min_per_week` / `sessions_per_week` / `mg_per_day` |
| `effect` | Effect size at this dose level |
| `se` | SE of effect |
| `N` | Sample size |
| `dose_response_shape` | `linear` / `U_shaped` / `threshold` / `plateau` |

### 5b. `subgroup_evidence_template.csv` → `subgroup_evidence_v1`

**Fill when:** Paper reports subgroup analyses or interaction effects (e.g., APOE × treatment, age × response). **16 columns.**

| Field | How to Fill |
|-------|------------|
| `edge_id` | Must exist in EDGE_REGISTRY (DB column: `subgroup_evidence_v1.edge_id`) |
| `modifier_variable` | E.g., `APOE_status`, `age_group`, `sex`, `treatment_type` |
| `modifier_value` | E.g., `e4_carrier`, `>65`, `female` |
| `interaction_beta` | Interaction (modifier × treatment) effect |
| `interaction_se` | SE of interaction |
| `interaction_p` | p-value of interaction |
| `subgroup_effect` | Subgroup-specific point estimate |
| `subgroup_se` | Subgroup-specific SE |
| `subgroup_n` | Subgroup sample size |

### 5c. `study_cohort_profile_template.csv` → `study_cohort_profiles_v1`

**Fill when:** DEEP mode — capture detailed cohort demographics. **25 columns.**

| Field | How to Fill |
|-------|------------|
| `profile_id` | Unique ID (e.g., `PROF_{study_id}_{arm}`) |
| `cohort_label` | E.g., `"HIIT arm"`, `"Control"`, `"Chemo-treated"` |
| `N_analyzed` | Actual N in analysis |
| `N_enrolled` | Enrolled N (optional) |
| `sex_female_pct` | Percentage female |
| `age_mean` / `age_sd` | Mean ± SD of age |
| `education_years_mean` / `education_years_sd` | Education (optional) |
| `bmi_mean` / `bmi_sd` | BMI (optional) |
| `eligibility_inclusion` | Inclusion criteria text |
| `eligibility_exclusion` | Exclusion criteria text |
| `cancer_type` | Cancer population |
| `treatment_phase` | Treatment phase |

---

## Step 6 — Create meta.json

Save to `data/manual_uploads/pdfs/<doi-slug>.meta.json`:

```json
{
  "doi": "10.xxxx/...",
  "title": "Full paper title",
  "authors": ["Last1 FM", "Last2 FM"],
  "year": 2024,
  "journal": "Journal Name",
  "pmid": "12345678",
  "study_design": "RCT",
  "cancer_type": "breast",
  "treatment_phase": "early_recovery",
  "intervention_type": "exercise",
  "n_total": 50,
  "n_treatment": 25,
  "n_control": 25,
  "extraction_mode": "DEEP",
  "targeted_edges": ["ER_ACTIVITY_PROC_SPEED"],
  "risk_of_bias": {
    "randomization": "low",
    "allocation_concealment": "low",
    "blinding_participants": "not_applicable",
    "blinding_outcome": "low",
    "attrition": "low",
    "selective_reporting": "low",
    "other": "none",
    "overall": "low"
  },
  "notes": ""
}
```

---

## Step 7 — Load Into Database

The AI runs the pipeline directly:

```bash
cd /workspaces/in-silico-crci-lab
python scripts/load_evidence_into_db.py --verbose
```

The pipeline is **idempotent** — re-running it won't create duplicates (edge_evidence uses
span_hash dedup, family importers use upsert via `session.merge()`).

Use `--reset` only if you need to wipe and reload ALL evidence from scratch.

The pipeline runs **12 automated steps** in sequence:

| Step | What It Does | Tables Affected |
|------|-------------|-----------------|
| **1** | Reseed edge definitions from EDGE_REGISTRY.csv | `edge_relations_definitions_v1` |
| **1b** | Reseed nodes + instruments from registries | `biomarker_node_definitions_v1`, `instrument_definitions_v1` |
| **1c** | Reseed measures + pathways from registries | `measure_definitions_v1`, `pathways_v1` |
| **2** | Clean up legacy entries | Various |
| **3** | Register study in study_registry_v1 | `study_registry_v1` |
| **4** | Load edge_evidence CSVs | `edge_evidence_v1` |
| **4b** | Load all 11 auxiliary family CSVs | `node_priors_v1`, `population_norms_v1`, `temporal_evidence_v1`, `instrument_evidence_v1`, `biomarker_correlations_v1`, `dose_evidence_v1`, `subgroup_evidence_v1`, `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1`, `ontology_links_v1` |
| **4c** | Harmonize scales to Cohen's d (SD borrowing) | `edge_evidence_v1` (updates in-place) |
| **4d** | Apply 7-layer SE_eff calibration (Formula P3-8) | `edge_evidence_v1` (updates in-place) |
| **5** | Seed action_catalog_v1 | `action_catalog_v1` |
| **5b** | Seed dose_bridges_v1 | `dose_bridges_v1` |
| **6** | Compile evidence → edges (IVW aggregation) | `edges_v1` |

> **Dry run available:** `python scripts/load_evidence_into_db.py --dry-run` to preview without writing.
> **Reset available:** `python scripts/load_evidence_into_db.py --reset` to wipe and reload all evidence.

---

## Step 8 — Update Extraction Log

The AI appends a new `## EXT-YYYY-NNNN` entry to `extraction_ref/EXTRACTION_LOG.md`:

- Extraction ID, timestamp, extractor name
- Source document (DOI, title, design, N)
- All evidence tables as markdown (one per CSV filled)
- All extraction decisions with risk ratings ([INST_MAP], [SIGN_CONV], [MISSING_DATA], [BIAS_ADJ], [CONSTRUCT], [DUPLICATE])
- Verification checklist (completed)
- Files created with locations

---

## Step 9 — Verify

```bash
python scripts/report_status.py --schema     # Check DB table row counts
python scripts/report_status.py --evidence   # Check per-edge evidence detail
```

**Post-load checklist:**
- [ ] Row counts match expectations
- [ ] No orphaned edge_relation_ids (all reference valid `edge_relations_definitions_v1`)
- [ ] No orphaned instrument_ids / upstream_instrument_ids (all reference valid `instrument_definitions_v1`)
- [ ] `edges_v1` updated with new compiled estimates
- [ ] `harmonized_beta` populated for all rows
- [ ] `se_eff` populated for all rows *(future — requires populated SE calibration layers)*

---

## Sign Convention (Critical)

| Rule | Detail |
|------|--------|
| **Positive beta = improvement** | Cognition increases, symptoms decrease |
| **Lower-is-better instruments** | Still use positive d when intervention helps (e.g., fewer TMT seconds = better) |
| **Report the paper's sign** | Document in `notes`, let the pipeline handle alignment |
| **Pipeline alignment** | Uses `scoring_direction` from INSTRUMENT_REGISTRY to auto-flip signs |

---

## Step 10 — What Happens Next (Extraction → Analytics Link)

Extraction populates the **evidence tables**. The algorithm pipeline reads
from those tables to produce patient-specific recommendations.

### Data Flow: Extraction → Algorithm → Output

```
extraction_ref/01_PROCEDURE.md (THIS FILE)
  ↓  Steps 0-9 produce CSV files
  ↓
scripts/load_evidence_into_db.py
  ↓  Loads CSVs → DB tables, harmonizes scales, calibrates SE, compiles edges
  ↓
  ├─ edge_evidence_v1     ← individual study effects
  ├─ edges_v1             ← IVW-compiled per-edge estimates (β̂, SE, k, N)
  ├─ node_priors_v1       ← context priors (z-scores)
  ├─ population_norms_v1  ← baseline reference ranges
  ├─ temporal_evidence_v1 ← longitudinal trajectories
  ├─ instrument_evidence_v1 ← psychometric properties
  └─ biomarker_correlations_v1 ← cross-domain r values
  ↓
  ↓  Algorithm reads from these tables
  ↓
scripts/run_full_model.py --patient-id PAT_001 --cancer-type breast ...
  ↓
  Chain A: Build DAG from registries (nodes, edges, pathways)
  ↓        (crci/algorithm/chain_a_graph/)
  Chain B: Parameterize edges — reads edge_evidence_v1 via evidence_loader.py
  ↓        B1: IVW pooling → β̂, SE_within
  ↓        B2: 7-layer SE calibration
  ↓        B3: Prior selection (RobustMAP / Commensurate / PowerPrior)
  ↓        B4: Inclusion probability
  ↓        B5: τ² prior (heterogeneity)
  ↓        B6: Coherence audit
  ↓        → FrozenModelState (crosses to runtime)
  ↓        (crci/algorithm/chain_b_evidence/)
  Chain C: Bayesian update — combine prior + evidence → posterior
  ↓        (crci/algorithm/chain_c_posterior/)
  Chain D: Monte Carlo simulation → rank interventions
  ↓        (crci/algorithm/chain_d_simulation/)
  Chain E: Temporal modeling — recovery trajectories + overlays
  ↓        (crci/algorithm/chain_e_temporal/)
  Chain F: Analytics — composite scoring, risk estimation, EVSI
  ↓        (crci/algorithm/chain_f_analytics/)
  Runtime: Session → Schedule optimization → Report assembly
  ↓        (crci/runtime/)
  Presentation: Formatted output (clinical/research reports)
           (crci/presentation/)
```

### Key Entry Points

| Script | What It Does |
|--------|-------------|
| `scripts/load_evidence_into_db.py --verbose` | Load extraction → DB (you just ran this) |
| `scripts/run_full_model.py --patient-id X --cancer-type Y` | Run full A→B→C→D→E→F→Session|
| `scripts/run_session.py --patient-id X` | Run session only (requires pre-computed chains) |
| `scripts/validate_deployment_readiness.py` | Validate system is ready for production |

### What Chain B Reads From Your Extraction

Chain B's `evidence_loader.py` queries `edge_evidence_v1` for these columns:

| Column | Purpose in Algorithm |
|--------|---------------------|
| `ler_id` | Unique evidence row ID |
| `edge_relation_id` | Which edge this evidence is for |
| `study_id` | Study linkage for study-level metadata |
| `harmonized_beta` | Effect size in Cohen's d (from your `effect_value_reported`) |
| `harmonized_se` | Calibrated SE (from your `se_reported`, after 7-layer inflation) |
| `N_effect` | Sample size (weighs the evidence) |
| `quality_rating` | Maps to GRADE multiplier in B2 |
| `identification_status` | Causal identification level → structural prior σ² |
| `harmonized_scale` | Confirms unit consistency |
| `study_design` | From study_registry → design multiplier in B2 |
| `publication_year` | Freshness weighting in B2 |

> **Bottom line:** Every value you extract in Steps 3-5 eventually flows into
> the Bayesian algorithm. The more papers extracted, the more evidence per edge,
> the narrower the posterior confidence intervals, the better the recommendations.

---

## AI Output Format

When extracting, the AI should produce for the human to review:

### A. Paper Classification

```
Mode: DEEP / STANDARD / SHALLOW
Justification: [why]
Study design: [RCT / cohort / etc.]
Cancer type: [breast / mixed / etc.]
N total: [number]
```

### B. Registry Check Report

```
Edges matched: [list edge_relation_ids]
Instruments matched: [list instrument_ids]
New entities flagged: [list, or "None"]
```

### C. Extraction Decisions

| # | Category | Risk | Decision | Rationale |
|---|----------|------|----------|-----------|
| 1 | [INST_MAP] | LOW | Mapped TMT-A → INST_TMTA | Direct match |
| 2 | [MISSING_DATA] | MEDIUM | SE derived from CI | SE not reported directly |

Categories: `[INST_MAP]`, `[SIGN_CONV]`, `[MISSING_DATA]`, `[BIAS_ADJ]`, `[CONSTRUCT]`, `[DUPLICATE]`

### D. What Could NOT Be Extracted

```
Missing temporal data: [explain]
Unreported SEs: [explain]
Ambiguous constructs: [explain]
```

### E. Files Created

List all files created in `data/manual_uploads/structured/<doi-slug>/`.

### F. Pipeline Output

Show the output of `python scripts/load_evidence_into_db.py --verbose` confirming successful load.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Edge not in registry | STOP. Flag: "Edge [X→Y] not in EDGE_REGISTRY. Suggest: ER_{SOURCE}_{TARGET}" |
| Instrument not in registry | STOP. Flag: "Instrument [name] not in INSTRUMENT_REGISTRY. Suggest: INST_{ABBREV}" |
| Node not in registry | Flag as REVIEW_TASK. Do NOT invent node IDs. |
| Ambiguous construct mapping | Report both options. Set risk = HIGH. Let human decide. |
| Cannot derive SE | Use `se_reported = √(4/N)` with `se_derivation_level = fallback_4_over_n`. Note in `notes`. |
| Effect direction unclear | Report paper's sign. Note ambiguity in `notes`. |
| Data from figure (not table) | Extract best estimate. Note "estimated from Figure X" in `notes`. |

---

## Reference Documents

| Document | Purpose |
|----------|---------|
| `03_SE_DERIVATION.md` | SE/effect-size computation formulas |
| `04_CONTROLLED_VOCAB.md` | All enum values and naming conventions |
| `06_CSV_TEMPLATES.md` | Full column specifications for all 12 template types |
| `07_CSV_TO_DB_MAP.md` | How CSV columns map to DB columns |
| `08_NODE_IDS.md` | All 63 node IDs |
| `09_EDGE_IDS.md` | All ~143 edge IDs |
| `10_INSTRUMENT_IDS.md` | All 67 instrument IDs |
| `11_QUALITY_CHECKLIST.md` | Per-paper quality gate checklist |
| `12_TABLE_FILL_MASTER.md` | All 83 DB tables — fill mechanism and status |
