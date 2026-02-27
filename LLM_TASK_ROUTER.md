# LLM Task Router — Master Context Instructions

**Purpose:** Single entry point for any LLM session working with the CRCI system.  
Read this FIRST. It routes you to the exact instructions you need based on what you're doing.

---

## How to Use This Document

1. Identify your task from the routing table below
2. Read the listed files **in order** — they are dependencies
3. Follow the instructions in each file exactly
4. Return here if you switch tasks mid-session

---

## Task Routing Table

### A. Paper Extraction (Adding Evidence from a Research Paper)

**Trigger:** You have a PDF of a study and need to extract its data into the system.

| Step | Read This | Why |
|------|-----------|-----|
| 1 | **[EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md)** | Complete step-by-step procedure (Steps 0-9) |
| 2 | **[EXTRACTION_LOG.md](EXTRACTION_LOG.md)** | See what's already extracted, avoid duplication |
| 3 | **[registries/NODE_REGISTRY.csv](registries/NODE_REGISTRY.csv)** | Valid node IDs (63 nodes) |
| 4 | **[registries/EDGE_REGISTRY.csv](registries/EDGE_REGISTRY.csv)** | Valid edge IDs (139 edges) |
| 5 | **[registries/INSTRUMENT_REGISTRY.csv](registries/INSTRUMENT_REGISTRY.csv)** | Valid instrument IDs (67 instruments) |
| 6 | List `data/manual_uploads/structured/` | See which papers already have folders |

**Paper-type routing:**

| Paper Type | How to Identify | Extraction Mode | Templates to Fill | Extra Steps |
|-----------|-----------------|-----------------|-------------------|-------------|
| **RCT + cancer + cognitive primary outcome** | Randomized trial, cancer population, cognitive test as primary/secondary endpoint | `DEEP` | ALL 5 templates (edge_evidence, population_norms, context_priors, instrument_evidence, temporal_evidence) | Check for multi-arm resolution, compute SE from CIs |
| **Cohort/observational + cognitive outcomes** | Longitudinal cohort, cross-sectional, case-control | `STANDARD` | edge_evidence + population_norms + context_priors | May need to borrow SDs from other studies |
| **Meta-analysis / systematic review** | Aggregates multiple studies | `DEEP` | edge_evidence (pooled estimates) + constituent study extraction | Extract both pooled AND per-study effects if Table available |
| **Biomarker / mechanistic only** | No behavioral intervention, just biomarker associations | `SHALLOW` | edge_evidence only | Often reports correlations (r) — convert to β |
| **Dose-response study** | Reports effects at multiple dose levels | `DEEP` | edge_evidence + **dose_bridges info** | Extract EC₅₀, Emax if reported — feeds Category A tables |
| **Longitudinal (≥3 timepoints)** | Reports cognitive change over time | `DEEP` | ALL templates, especially temporal_evidence | Extract per-timepoint effects for trajectory modeling |
| **Psychometric validation study** | Reports instrument reliability/validity, no intervention | `SHALLOW` | instrument_evidence only | Extract Cronbach's α, test-retest ICC, cancer validation status |

**For each paper, capture these in every relevant CSV:**

| Always Record | Column | Where |
|--------------|--------|-------|
| DOI | `doi` | Every CSV row |
| Edge relationship | `edge_id` | edge_evidence (must exist in EDGE_REGISTRY) |
| Effect size + SE | `beta_raw`, `se_raw` | edge_evidence |
| Effect type | `effect_type_original` | edge_evidence (`cohen_d`, `mean_diff`, `odds_ratio`, `correlation_r`) |
| Sample size | `sample_size` | Every CSV |
| Cancer type | `cancer_type` | Every CSV |
| Treatment phase | `treatment_phase` | Every CSV |
| Instrument used | `instrument_id` | edge_evidence (must exist in INSTRUMENT_REGISTRY) |

**Common gotchas at scale:**
- **Always check EDGE_REGISTRY first.** If the paper tests an edge that already exists, add evidence to that edge. Only create new edges for genuinely new relationships.
- **Effect sign convention:** symptom burden nodes are higher-is-worse. If the paper reports improvement as positive, you may need to flip the sign. Check `expected_sign` in EDGE_REGISTRY.
- **SE from CI:** If only confidence intervals are given: `SE = (upper - lower) / (2 × 1.96)`
- **Mean diff → Cohen's d:** The loader auto-converts if you fill population_norms. Set `effect_type_original = mean_diff_[unit]` and always provide the population_norms CSV.
- **Multi-arm trials:** Only compare each arm to control. Don't enter arm-vs-arm comparisons (double-counts the control).

**After filling CSVs → Run import:**
```bash
python scripts/load_evidence_into_db.py --verbose
```

---

### B. Category A Knowledge Tables (Domain Knowledge Curation)

**Trigger:** You need to fill the knowledge-base tables that the algorithm needs
but are NOT populated from individual papers.

| Step | Read This | Why |
|------|-----------|-----|
| 1 | **[CATEGORY_A_RESEARCH_GUIDE.md](CATEGORY_A_RESEARCH_GUIDE.md)** | Full instructions, schemas, research prompts per table |
| 2 | The specific table schema in **[docs/03_database/05_TABLE_SCHEMAS.md](docs/03_database/05_TABLE_SCHEMAS.md)** | Exact column definitions and validation rules |
| 3 | **[docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md](docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md)** §Chain D-E | How the algorithm USES these tables |

**Sub-task routing:**

| What You're Filling | Go To | Key Data Needed |
|--------------------|-------|-----------------|
| `intervention_kernels_v1` (temporal dynamics) | CATEGORY_A_RESEARCH_GUIDE §2 | onset_weeks, build_weeks, steady_state, decay_half_life per action |
| `dose_bridges_v1` (dose-response curves) | CATEGORY_A_RESEARCH_GUIDE §3 | EC₅₀, Emax, bridge_gain per (action, target_node) pair |
| `contraindication_rules_v1` (safety rules) | CATEGORY_A_RESEARCH_GUIDE §4 | condition_expression, severity, rationale per risk |
| `biomarker_correlations_v1` (inter-node correlations) | CATEGORY_A_RESEARCH_GUIDE §5 | ρ between 8 biomarker pairs |
| `normalization_refs_v1` (population reference norms) | CATEGORY_A_RESEARCH_GUIDE §6 | ref_mean, ref_sd per instrument in cancer population |

---

### C. Adding a New Node, Edge, or Instrument to Registries

**Trigger:** A paper references a construct, relationship, or instrument not yet in the system.

| Step | Read This | Why |
|------|-----------|-----|
| 1 | **[registries/NODE_REGISTRY.csv](registries/NODE_REGISTRY.csv)** | Check it doesn't already exist under a different name |
| 2 | **[registries/EDGE_REGISTRY.csv](registries/EDGE_REGISTRY.csv)** | Check the edge doesn't already exist |
| 3 | **[registries/INSTRUMENT_REGISTRY.csv](registries/INSTRUMENT_REGISTRY.csv)** | Check the instrument doesn't already exist |
| 4 | **[EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md)** Step 1 | Column reference for EDGE_REGISTRY |

**Rules:**
- Node IDs: `NODE_[DOMAIN]_[CONSTRUCT]` (e.g., `NODE_COG_WORK_MEM`)
- Edge IDs: `ER_[SOURCE]_[TARGET]` (e.g., `ER_ACTIVITY_WORKMEM`)
- Instrument IDs: `INST_[ABBREVIATION]` (e.g., `INST_HVLTR`)
- Every new node must have: `node_id`, `node_label`, `node_role`, `orientation`, `node_domain`, `default_state_space`, `state_update_scale`
- Every new edge must have: `source_node_id`, `target_node_id`, `relation_type`, `expected_sign`, `primary_pathway`
- After adding to registries, run `python scripts/load_evidence_into_db.py --reset --verbose` to sync to DB

---

### D. Understanding the System Architecture

**Trigger:** You need to understand how the system works before starting work.

| Depth | Read This |
|-------|-----------|
| 5-minute overview | **[docs/00_navigation/QUICK_REFERENCE.md](docs/00_navigation/QUICK_REFERENCE.md)** |
| Full architecture | **[docs/00_navigation/IMPLEMENTATION_GUIDE.md](docs/00_navigation/IMPLEMENTATION_GUIDE.md)** |
| Algorithm details | **[docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md](docs/02_system_specs/SYS_ALGORITHM_COMPLETE.md)** |
| Database schemas | **[docs/03_database/05_TABLE_SCHEMAS.md](docs/03_database/05_TABLE_SCHEMAS.md)** |
| Data flow | **[docs/00_navigation/VISUAL_ROADMAP.md](docs/00_navigation/VISUAL_ROADMAP.md)** |

---

### E. Continuing Code Implementation

**Trigger:** Building the next code slice.

| Step | Read This | Why |
|------|-----------|-----|
| 1 | **[PROGRESS.md](PROGRESS.md)** | Where we are in the build |
| 2 | **[docs/04_implementation/PROMPT_SEQUENCE.md](docs/04_implementation/PROMPT_SEQUENCE.md)** | Build order |
| 3 | **[docs/04_implementation/FILE_CONTEXT_MANIFEST.md](docs/04_implementation/FILE_CONTEXT_MANIFEST.md)** | Per-file dependencies |
| 4 | **[CLAUDE.md](CLAUDE.md)** | Full implementation cycle (Read → Plan → Implement → Verify) |

---

## Data Flow Summary

```
                    REGISTRIES (human-authored, fixed)
                    ├── NODE_REGISTRY.csv (63 nodes)
                    ├── EDGE_REGISTRY.csv (139 edges)
                    └── INSTRUMENT_REGISTRY.csv (67 instruments)
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │            PAPER EXTRACTION (Task A)                 │
    │  PDF → fill CSVs → data/manual_uploads/structured/  │
    │  Templates: edge_evidence, population_norms,         │
    │  context_priors, instrument_evidence, temporal_evid  │
    └──────────────────────┬──────────────────────────────┘
                           │
                           ▼
    ┌─────────────────────────────────────────────────────┐
    │    load_evidence_into_db.py (import pipeline)        │
    │  1. Reseed registries → DB                           │
    │  2. Register studies → study_registry_v1             │
    │  3. Load edge evidence → edge_evidence_v1            │
    │  4. Load aux families → node_priors, pop_norms, etc  │
    │  5. Scale harmonization (mean_diff → cohens_d)       │
    │  6. IVW compilation → edges_v1 (compiled)            │
    └──────────────────────┬──────────────────────────────┘
                           │
                           ▼
    ┌─────────────────────────────────────────────────────┐
    │          ALGORITHM CHAINS (runtime)                   │
    │                                                       │
    │  Chain A (Graph)  ← registries (CSV)                 │
    │  Chain B (Evidence) ← edge_evidence_v1, edges_v1     │
    │  Chain C (Posterior) ← node_priors, state_snapshots  │
    │  Chain D (Simulation) ← action_catalog, edges_v1     │
    │    ❌ NEEDS: intervention_kernels, dose_bridges,     │
    │             contraindication_rules (Task B)           │
    │  Chain E (Temporal) ← Chain D output + kernels       │
    │  Chain F (Analytics) ← all upstream                   │
    └─────────────────────────────────────────────────────┘
                           │
              CATEGORY A TABLES (Task B)
              ├── intervention_kernels_v1     ← temporal dynamics
              ├── dose_bridges_v1            ← dose-response
              ├── contraindication_rules_v1  ← safety
              ├── biomarker_correlations_v1  ← covariance matrix
              └── normalization_refs_v1      ← z-score references
```

---

## Controlled Vocabulary Quick Reference

### Cancer Types
`breast`, `colorectal`, `lung`, `prostate`, `hematological`, `gynecological`,
`head_neck`, `brain_cns`, `pediatric_survivor`, `other`, `mixed`

### Treatment Phases
`pre_treatment`, `active_treatment`, `early_recovery`, `late_recovery`,
`long_term_survivorship`

### Study Designs
`RCT`, `crossover_RCT`, `cohort`, `case_control`, `cross_sectional`,
`systematic_review`, `meta_analysis`

### Effect Size Types
`BETWEEN_GROUP`, `WITHIN_GROUP`, `PRE_POST_CHANGE`

### Node Domains
`cognitive_performance`, `symptom_burden`, `lifestyle_behavior`, `inflammatory`,
`neurotrophic`, `neuroendocrine`, `metabolic`, `microbiome_immune`,
`cellular_damage`, `demographics`, `treatment_exposure`

---

## Session Checklist

Before starting any work session:

- [ ] Identified task type from routing table above
- [ ] Read all listed prerequisite files for that task
- [ ] Checked EXTRACTION_LOG.md for prior work (if extraction)
- [ ] Verified registry IDs are current (node, edge, instrument)
- [ ] Have the paper PDF accessible (if extraction)

---

*This is the master routing document. All other docs are referenced FROM here.
When starting a new LLM session, paste this document as context first.*
