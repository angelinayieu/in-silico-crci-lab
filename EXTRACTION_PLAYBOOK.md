# CRCI Extraction Playbook

**Purpose:** Single-file reference for adding a new paper to the system.  
**Audience:** Human researchers + AI agents performing per-paper extraction.  
**Authoritative spec:** `docs/01_v2_master/CRCI_Master_Spec_v2.0.md`

---

## Step 0 — Classify the Paper (Mode Decision)

| Condition | Mode | Notes |
|-----------|------|-------|
| RCT + cancer population + cognitive **primary** outcome | **DEEP** | All 9 agents; all templates |
| Cohort/observational + cognitive outcomes | **STANDARD** | Core templates only |
| Case report / animal / biomarker-only | **SHALLOW** | edge_evidence only |
| Unknown | **STANDARD** | Default |

**DEEP triggers:** study_design ∈ {RCT, crossover_RCT} AND cancer_type ≠ null AND any cognitive instrument used as primary outcome.

---

## Step 1 — Check/Add to EDGE_REGISTRY

File: `registries/EDGE_REGISTRY.csv`  
Add a row only if the paper tests an edge NOT already in the registry.

**Column reference:**

| Column | Required | Example |
|--------|----------|---------|
| `edge_relation_id` | YES | `ER_COGACTIVITY_WORKMEM` |
| `source_node_id` | YES | `NODE_BEH_COG_ACTIVITY` |
| `target_node_id` | YES | `NODE_COG_WORK_MEM` |
| `relation_type` | YES | `causal` or `associational` |
| `mechanism_description` | YES | Free text |
| `primary_pathway` | YES | e.g. `PW_M04_NEUROPLASTICITY` |
| `secondary_pathways_json` | YES | `[]` or `["PW_M15_COG_RESERVE"]` |
| `expected_sign` | YES | `positive` / `negative` / `context_dependent` |
| `functional_form` | YES | `linear` / `emax` / `threshold` / `u_shaped` |
| `fallback_form` | YES | usually `linear` |
| `is_feedback_edge` | YES | `0` or `1` |
| `feedback_loop_id` | YES | `N/A` if not feedback |
| `notes` | NO | Any clarifications |
| `version` | YES | `1` |
| `active` | YES | `1` |

---

## Step 2 — Create Paper Subfolder

```bash
# DOI convention: replace / with _
mkdir -p data/manual_uploads/structured/10.1016_j.JOURNAL.YEAR.ISSUE.PAGE
mkdir -p data/manual_uploads/pdfs/
# Copy blank templates from data/templates/ as your starting point
```

---

## Step 3 — Fill edge_evidence_template.csv  ← REQUIRED

`data/manual_uploads/structured/[doi-slug]/edge_evidence_template.csv`

**Column reference:**

| Column | Required | Notes |
|--------|----------|-------|
| `doi` | YES | e.g. `10.1016/j.lfs.2013.08.011` |
| `edge_id` | YES | Must exist in `registries/EDGE_REGISTRY.csv` |
| `beta_raw` | YES | Cohen's d, OR, Beta, or whatever metric they report |
| `se_raw` | YES | SE of the effect size |
| `effect_type_original` | YES | What the paper reports: `cohen_d`, `mean_diff`, `odds_ratio`, etc. |
| `effect_size_type` | YES | `BETWEEN_GROUP` / `WITHIN_GROUP` / `PRE_POST_CHANGE` |
| `sample_size` | YES | Total N in analysis |
| `study_design` | YES | `RCT`, `cohort`, `case_control`, `cross_sectional` |
| `cancer_type` | YES | `breast`, `colorectal`, `lung`, etc. |
| `treatment_phase` | YES | `active_treatment`, `early_recovery`, etc. |
| `instrument_id` | YES | Must exist in `registries/INSTRUMENT_REGISTRY.csv` |
| `confidence_note` | NO | Notes on any concerns |

### Computing Cohen's d When Not Reported

```
SD = SE × √n                          (per group)
SD_pooled = √[(SD_tx² + SD_ctrl²) / 2]
d = (mean_tx_change - mean_ctrl_change) / SD_pooled
```

For pre-post change scores where only group means ± SE are given:
```
d = (Δmean_tx - Δmean_ctrl) / SD_pooled_baseline
```

---

## Step 4 — Fill population_norms_template.csv  ← RECOMMENDED

`data/manual_uploads/structured/[doi-slug]/population_norms_template.csv`

**Column reference (per `docs/01_v2_master/CRCI_Checklists_Templates_v2.0.md` §T1.3):**

| Column | Required | Notes |
|--------|----------|-------|
| `doi` | YES | Paper DOI |
| `node_id` | YES | Must exist in `registries/NODE_REGISTRY.csv` |
| `instrument_id` | YES | Instrument used to assess the node |
| `mean` | YES | Baseline/pre-treatment mean |
| `sd` | YES | SD of the mean (SD > 0) |
| `sample_size` | YES | N contributing to this estimate |
| `cancer_type` | YES | Match NODE_REGISTRY values |
| `treatment_phase` | YES | Context for prior matching |
| `age_range` | NO | e.g. `45-65` |

---

## Step 5 — Fill context_priors_template.csv  ← RECOMMENDED

`data/manual_uploads/structured/[doi-slug]/context_priors_template.csv`

Convert raw scores to z-scores:
```
z = (observed_mean - population_mean) / population_SD
```

Use the control group baseline as the population reference if no published norms
are available, then flag `source_type = local_control_group`.

---

## Step 6 — Optional Templates

Fill ONLY if the paper provides that data:

| Template | Fill when... |
|----------|-------------|
| `temporal_evidence_template.csv` | Paper has ≥2 longitudinal timepoints |
| `instrument_evidence_template.csv` | Paper reports Cronbach's α, test-retest ICC, or split-half |
| `correlation_template.csv` | Paper reports inter-domain correlations (e.g. IL-6 × fatigue r) |

---

## Step 7 — Create companion meta.json

`data/manual_uploads/pdfs/[doi-slug].meta.json`

```json
{
  "doi": "10.1016/j.lfs.2013.08.011",
  "title": "Full paper title here",
  "authors": ["Last1 FM", "Last2 FM"],
  "year": 2013,
  "journal": "Life Sciences",
  "pmid": "24064136",
  "study_design": "RCT",
  "cancer_type": "breast",
  "treatment_phase": "early_recovery",
  "intervention_type": "cognitive_rehabilitation",
  "n_total": 28,
  "n_treatment": 12,
  "n_control": 16,
  "extraction_mode": "DEEP",
  "targeted_edges": ["ER_COGACTIVITY_WORKMEM", "ER_COGACTIVITY_ATTN"],
  "risk_of_bias": {
    "randomization": "low",
    "allocation_concealment": "unclear",
    "blinding_participants": "not_applicable",
    "blinding_outcome": "unclear",
    "attrition": "low",
    "selective_reporting": "low",
    "other": "small_sample",
    "overall": "moderate"
  },
  "completeness_pct": 80,
  "notes": "Free text notes"
}
```

---

## Step 8 — Copy PDF

```bash
# PDF naming: replace / in DOI with _, add .pdf
cp /path/to/paper.pdf data/manual_uploads/pdfs/10.1016_j.lfs.2013.08.011.pdf
```

---

## Step 9 — Run Import

```bash
cd /workspaces/in-silico-crci-lab
python scripts/run_manual_import.py --type csv --verbose
```

Expected output per CSV: `"Would import [N] rows from [file]"` (actual DB write pending Trust Boundary pipeline completion).

---

## Quick Reference: Node IDs

### Exogenous / Treatment
| Node ID | Label |
|---------|-------|
| `NODE_EXO_CHEMO_REGIMEN` | Chemotherapy Regimen Class |
| `NODE_EXO_RADIATION` | Radiation Exposure |
| `NODE_EXO_TX_PHASE` | Treatment Phase |
| `NODE_EXO_CANCER_TYPE` | Cancer Type |
| `NODE_EXO_AGE` | Age at Diagnosis |
| `NODE_EXO_SEX` | Biological Sex |
| `NODE_EXO_APOE` | APOE Genotype Status |
| `NODE_EXO_COG_RESERVE` | Premorbid Cognitive Reserve |
| `NODE_EXO_COMORBIDITY` | Comorbidity Burden |

### Behaviors (Intervention Targets)
| Node ID | Label |
|---------|-------|
| `NODE_BEH_PHYSICAL_ACTIVITY` | Physical Activity Level |
| `NODE_BEH_SLEEP_QUALITY` | Sleep Quality/Hygiene |
| `NODE_BEH_DIET` | Dietary Pattern |
| `NODE_BEH_STRESS_MGMT` | Stress Management Practice |
| `NODE_BEH_SOCIAL_ENGAGE` | Social Engagement Level |
| `NODE_BEH_LIGHT_EXPOSURE` | Light Exposure Pattern |
| `NODE_BEH_COG_ACTIVITY` | Cognitive Activity Level |
| `NODE_BEH_SELF_EFFICACY` | Self-Efficacy |

### Cognitive Domains
| Node ID | Label |
|---------|-------|
| `NODE_COG_WORK_MEM` | Working Memory |
| `NODE_COG_ATTN_SUSTAINED` | Sustained Attention |
| `NODE_COG_ATTN_SELECTIVE` | Selective Attention |
| `NODE_COG_EPISODIC_MEM` | Episodic Memory |
| `NODE_COG_VERBAL_FLUENCY` | Verbal Fluency |
| `NODE_COG_EXEC_PLANNING` | Executive Planning |
| `NODE_COG_EXEC_INHIBITION` | Executive Inhibition |
| `NODE_COG_PROC_SPEED` | Processing Speed |
| `NODE_COG_VISUOSPATIAL` | Visuospatial |
| `NODE_COG_LANGUAGE` | Language |
| `NODE_SYM_COG_COMPLAINTS` | Subjective Cognitive Complaints |
| `NODE_COMP_CRCI` | CRCI Composite |

---

## Quick Reference: Instrument IDs

### Patient-Reported Outcomes (PRO)
| Instrument ID | Name | Node | Direction |
|---------------|------|------|-----------|
| `INST_AFI` | Attentional Function Index | NODE_SYM_COG_COMPLAINTS | higher=better |
| `INST_FACTCOG_PCI` | FACT-Cog PCI | NODE_SYM_COG_COMPLAINTS | higher=better |
| `INST_PROMIS_COG` | PROMIS Cog 8a | NODE_SYM_COG_COMPLAINTS | higher=better |
| `INST_FACIT_FATIGUE` | FACIT-Fatigue | NODE_SYM_FATIGUE | higher=less fatigue |
| `INST_BFI` | Brief Fatigue Inventory | NODE_SYM_FATIGUE | lower=better |
| `INST_LFS` | Lee Fatigue Scale | NODE_SYM_FATIGUE | lower=better |
| `INST_PHQ9` | PHQ-9 | NODE_SYM_DEPRESSION | lower=better |
| `INST_CESD` | CES-D | NODE_SYM_DEPRESSION | lower=better |
| `INST_GAD7` | GAD-7 | NODE_SYM_ANXIETY | lower=better |

### Neuropsychological Tests (Performance-Based)
| Instrument ID | Name | Node | Direction |
|---------------|------|------|-----------|
| `INST_DIGIT_SPAN` | WAIS Digit Span | NODE_COG_WORK_MEM | higher=better |
| `INST_CPT` | Continuous Performance Test | NODE_COG_ATTN_SUSTAINED | higher=better |
| `INST_STROOP` | Stroop Color-Word Test | NODE_COG_EXEC_INHIBITION | higher=better |
| `INST_TMT_B` | Trail Making Test B | NODE_COG_PROC_SPEED | lower=better |
| `INST_HVLTR` | HVLT-R | NODE_COG_EPISODIC_MEM | higher=better |
| `INST_COWAT` | COWAT/FAS | NODE_COG_VERBAL_FLUENCY | higher=better |
| `INST_TOL` | Tower of London | NODE_COG_EXEC_PLANNING | higher=better |
| `INST_REY_COPY` | Rey Complex Figure | NODE_COG_VISUOSPATIAL | higher=better |
| `INST_BNT` | Boston Naming Test | NODE_COG_LANGUAGE | higher=better |
| `INST_MOCA` | MoCA | NODE_COMP_CRCI | higher=better |

> If an instrument isn't in the registry, add it to `registries/INSTRUMENT_REGISTRY.csv` first.

---

## Quick Reference: Edge IDs Added From Cherrier 2013

| Edge ID | Source → Target | d |
|---------|----------------|---|
| `ER_COGACTIVITY_WORKMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_WORK_MEM | 0.79 |
| `ER_COGACTIVITY_ATTN` | NODE_BEH_COG_ACTIVITY → NODE_COG_ATTN_SUSTAINED | 0.59 |
| `ER_COGACTIVITY_COGCOMPLAINTS` | NODE_BEH_COG_ACTIVITY → NODE_SYM_COG_COMPLAINTS | −0.53 (FACT-Cog, negative=improvement) |
| `ER_COGACTIVITY_EPIMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_EPISODIC_MEM | 0.25 (trend) |

---

## Where Things Live

```
EXTRACTION_PLAYBOOK.md          ← THIS FILE
registries/
  EDGE_REGISTRY.csv             ← add new edges here first
  NODE_REGISTRY.csv             ← reference: all node IDs
  INSTRUMENT_REGISTRY.csv       ← reference: all instrument IDs
  MEASURE_REGISTRY.csv
  PATHWAY_REGISTRY.csv
data/
  templates/                    ← BLANK templates (never fill these)
    edge_evidence_template.csv
    population_norms_template.csv
    context_priors_template.csv
    temporal_evidence_template.csv
    instrument_evidence_template.csv
    correlation_template.csv
  manual_uploads/
    structured/
      README.md                 ← subfolder convention docs
      [doi-slug]/               ← per-paper, filled CSVs go here
    pdfs/
      [doi-slug].pdf
      [doi-slug].meta.json
docs/
  00_navigation/                ← Start here, INDEX, QUICK_REFERENCE
  01_v2_master/                 ← CRCI_Master_Spec_v2.0.md (AUTHORITATIVE)
  02_system_specs/              ← SYS_EXTRACTION_COMPLETE.md
  03_database/                  ← 05_TABLE_SCHEMAS.md, FK map
  04_implementation/            ← PROMPT_SEQUENCE.md, FILE_CONTEXT_MANIFEST
  05_data_management/           ← PARAMETER_PROVENANCE, CONVERSION_VALIDITY
  06_orchestration/             ← CLAUDE_CODE_ORCHESTRATION
```

---

## Key Spec Sections by Task

| Task | Read |
|------|------|
| Understand extraction modes (DEEP/STANDARD/SHALLOW) | `docs/01_v2_master/CRCI_Master_Spec_v2.0.md` §2-3 |
| CSV column definitions | `docs/01_v2_master/CRCI_Checklists_Templates_v2.0.md` §T1 |
| effect_size_type enum | `docs/01_v2_master/CRCI_Engineering_Appendix_v2.0.md` §A.1 |
| Trust Boundary (TB) rules | `docs/02_system_specs/SYS_EXTRACTION_COMPLETE.md` lines ~500-600 |
| Seven-layer calibration | `docs/02_system_specs/SYS_EXTRACTION_COMPLETE.md` lines ~900-1100 |
| Meta-analysis extraction checklist | `docs/01_v2_master/CRCI_Checklists_Templates_v2.0.md` §T2.1 |
| Table schemas (all 56 tables) | `docs/03_database/05_TABLE_SCHEMAS.md` |
| Parameter provenance (GREEN/YELLOW/RED) | `docs/05_data_management/PARAMETER_PROVENANCE_AND_CURATION.md` |

---

## Common Controlled Vocabulary

**study_design:** `RCT`, `crossover_RCT`, `cohort`, `case_control`, `cross_sectional`, `systematic_review`, `meta_analysis`

**cancer_type:** `breast`, `colorectal`, `lung`, `prostate`, `hematological`, `gynecological`, `head_neck`, `brain_cns`, `pediatric_survivor`, `other`, `mixed`

**treatment_phase:** `pre_treatment`, `active_treatment`, `early_recovery`, `late_recovery`, `long_term_survivorship`

**effect_size_type:** `BETWEEN_GROUP`, `WITHIN_GROUP`, `PRE_POST_CHANGE`

**relation_type:** `causal`, `associational`

---

*Last updated: based on Cherrier et al. 2013 (first paper in system)*
