# CRCI Extraction Playbook

**Purpose:** Single-file reference for adding a new paper to the system.  
**Audience:** Human researchers + AI agents performing per-paper extraction.  
**Authoritative spec:** `docs/01_v2_master/CRCI_Master_Spec_v2.0.md`  
**Master routing doc:** [`LLM_TASK_ROUTER.md`](LLM_TASK_ROUTER.md) — start here if unsure which instructions to follow.

> **Batch import note (50+ papers):** This playbook works for one paper at a time.
> For batch imports, repeat Steps 0-8 for each paper (in any order), then run
> Step 9 once. The loader processes all papers in `data/manual_uploads/structured/`
> automatically — no code changes needed per paper. Study IDs are auto-derived
> from folder names (DOI slugs).

---

## How This Playbook Connects to Paper Discovery

**This playbook covers extraction (Steps 0-9).** It assumes you already have a PDF.

To find papers worth extracting, see:
- [`DEEP_RESEARCH_STRATEGY.md` Part 9](DEEP_RESEARCH_STRATEGY.md#part-9-manual-chatbox-retrieval-protocol) — **Manual Chatbox Retrieval Protocol**  
  Full workflow: chatbox discovery → extractability screening → PDF acquisition → hand off to this playbook
- [`DEEP_RESEARCH_STRATEGY.md` Parts 1-8](DEEP_RESEARCH_STRATEGY.md) — Search queries organized by pathway  
- [`docs/05_data_management/AUTOMATED_RETRIEVAL_PLAN.md`](docs/05_data_management/AUTOMATED_RETRIEVAL_PLAN.md) Part 14 — Automated pipeline (when operational)

**Workflow at a glance:**
```
DEEP_RESEARCH_STRATEGY.md §9    THIS PLAYBOOK           Database
 (chatbox discovery)        (per-paper extraction)     (compiled model)
                                                       
 Phase A: Find papers ──→  Step 0: Classify paper       
 Phase B: Screen      ──→  Step 1: Check EDGE_REGISTRY  
 Phase C: Get PDFs    ──→  Step 2: Create folder         
                           Step 3: Fill edge_evidence ──→ edge_evidence_v1
                           Step 4: Fill pop norms     ──→ population_norms_v1
                           Step 5: Fill context priors──→ context_priors_v1
                           Step 6: Optional templates ──→ auxiliary tables
                           Step 7: Create meta.json   ──→ study_registry_v1
                           Step 8: Copy PDF              
                           Step 9: Run import         ──→ edges_v1 (compiled)
```

---

## Pre-Extraction Checklist (read BEFORE starting)

Before extracting ANY paper, verify you have read:
- [ ] This playbook (especially Step 3 column reference)
- [ ] [`EXTRACTION_LOG.md`](EXTRACTION_LOG.md) — avoid re-extracting papers already in system
- [ ] [`registries/NODE_REGISTRY.csv`](registries/NODE_REGISTRY.csv) — valid node IDs
- [ ] [`registries/EDGE_REGISTRY.csv`](registries/EDGE_REGISTRY.csv) — existing edges (don't create duplicates)
- [ ] [`registries/INSTRUMENT_REGISTRY.csv`](registries/INSTRUMENT_REGISTRY.csv) — valid instrument IDs

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
| `beta_raw` | YES | Effect size value as reported (Cohen's d, mean diff, OR, etc.). Raw mean differences are auto-converted to Cohen's d at import time via SD borrowing from `population_norms_v1` (Step 4c of `load_evidence_into_db.py`). |
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
python scripts/load_evidence_into_db.py --verbose
# Or to wipe and reload cleanly:
python scripts/load_evidence_into_db.py --reset --verbose
```

The import pipeline performs these steps automatically:
1. Reseed edge/node/instrument definitions from registries
2. Register studies, load CSV evidence into `edge_evidence_v1`
3. Load auxiliary families (context_priors, instruments, norms, temporal)
4. **Scale harmonization (Step 4c):** Converts `mean_diff_raw` → `cohens_d` by borrowing SD from `population_norms_v1` (Tier 1: same study SD, no inflation; Tier 2: cross-study SD, 1.15× SE inflation)
5. Seed actions, compile IVW edges

> **Important:** Population norms must be loaded (Step 4b) BEFORE scale harmonization (Step 4c) can borrow SD values. Always fill `population_norms_template.csv` when extracting papers that report raw mean differences.

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

## Chatbox Extraction Session Setup

When using a chatbox (Claude or other LLM) for extraction, load this context
at the start of the session:

**Always load (pin these):**
1. This playbook (EXTRACTION_PLAYBOOK.md)
2. `extraction_ref/02_CHATBOX_CONTEXT.md` — full extraction context
3. `registries/EDGE_REGISTRY.csv` — all valid edge IDs
4. `registries/INSTRUMENT_REGISTRY.csv` — all valid instrument IDs
5. `registries/NODE_REGISTRY.csv` — all valid node IDs
6. `EXTRACTION_LOG.md` — what's already extracted (avoid duplicates)

**Load per paper:**
7. The paper's PDF (attached or pasted as text)
8. If already screened: the edge-mapping guesses from discovery phase

**Session instruction preamble (paste at session start):**
```
You are extracting quantitative evidence from a research paper into the CRCI
Bayesian Causal Model. Follow EXTRACTION_PLAYBOOK.md Steps 0-9. For every
value extracted:
  - Record the EXACT source location (table, page, row)
  - Record the derivation method (reported directly, computed from CI, etc.)
  - Flag any judgment calls as extraction decisions with risk levels
  - Use ONLY edge IDs from EDGE_REGISTRY.csv
  - Use ONLY instrument IDs from INSTRUMENT_REGISTRY.csv
  - Use ONLY node IDs from NODE_REGISTRY.csv
  - If an instrument/edge doesn't exist in the registry, flag it and propose
    a new ID following the naming convention

Output format: filled CSV templates + meta.json + EXTRACTION_LOG entry.
```

**What the chatbox CANNOT do (human must verify):**
- Compute PDF SHA-256 hash
- Run `load_evidence_into_db.py`
- Verify values against the physical PDF (if working from pasted text)
- Sign-off on extraction decisions marked MEDIUM or HIGH risk

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
| **Start here (task routing)** | [`LLM_TASK_ROUTER.md`](LLM_TASK_ROUTER.md) |
| **Category A tables (kernels, dose bridges, safety)** | [`CATEGORY_A_RESEARCH_GUIDE.md`](CATEGORY_A_RESEARCH_GUIDE.md) |
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
