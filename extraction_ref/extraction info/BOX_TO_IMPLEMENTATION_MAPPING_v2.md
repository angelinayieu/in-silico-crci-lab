# Box-to-Implementation Mapping Sheet v2.0

> **Finalized cross-reference**: Every box from the architecture diagram mapped to
> the actual codebase modules, DB tables, and their current implementation status.
> 
> **Methodology**: This document was produced by auditing every SQL schema file
> (`001_class_a_knowledge.sql` – `013_template_alignment.sql`), every extraction
> agent (`ag01` – `ag11`), every compiler (`p7_compilers/*.py`), every algorithm
> chain (`chain_a` – `chain_f`), and every runtime/presentation module. Tables
> listed below are **real tables in the schema**, not aspirational names.

---

## Table of Contents

0. [EXTRACTION → DATABASE Pipeline Overview](#extraction--database-pipeline-overview)
   - [System 1: Abstract Management System](#system-1-abstract-management-system)
   - [System 2: Extraction Management System](#system-2-extraction-management-system)
   - [System 3: Extraction → Database Transportation & Management System](#system-3-extraction--database-transportation--management-system)
1. [Layer A — Automated + Manual Acquisition (ACQ)](#a-automated--manual-acquisition-acq)
2. [Layer B — P0 Triage + Structural Decomposition](#b-p0-triage--structural-decomposition)
3. [Layer C — Parallel Extraction (P1 Agents)](#c-parallel-extraction-p1-agents)
4. [Layer D — Trust Boundary → Harmonization → Calibration (P2/P3/P4)](#d-trust-boundary--harmonization--calibration)
5. [Layer E — Evidence & Knowledge Stores](#e-evidence--knowledge-stores)
6. [Layer F — Aggregation + Compilation (P4/P4b/P5/P7)](#f-aggregation--compilation)
7. [Layer G — Runtime Causal Simulation (Algorithm Chains A–F)](#g-runtime-causal-simulation-algorithm-chains)
8. [Layer H — Feedback, Monitoring, Self-Improvement](#h-feedback-monitoring-self-improvement)
9. [Master Table Inventory — Schema vs. Coverage Audit](#master-table-inventory)
10. [Gap Analysis — Missing Wiring](#gap-analysis)

---

## EXTRACTION → DATABASE Pipeline Overview

The full evidence pipeline has three distinct management systems that operate in sequence.
Each system has clearly defined inputs, process, and outputs. Together they form the
complete path from "we need evidence" to "compiled parameters in the database."

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────────────────────┐
│  SYSTEM 1           │     │  SYSTEM 2            │     │  SYSTEM 3                    │
│  Abstract Mgmt      │────▶│  Extraction Mgmt     │────▶│  Extraction → DB Transport   │
│  (Discovery/Triage) │     │  (Per-Paper Evidence) │     │  (Load + Harmonize + Compile)│
└─────────────────────┘     └──────────────────────┘     └──────────────────────────────┘
 Papers found & ranked       CSV templates filled          Evidence in DB, edges compiled
```

---

### System 1: Abstract Management System

**Goal:** Systematically discover, screen, categorize, and prioritize the literature space
for the 143 edges × 21 pathways of the CRCI model. Produce a ranked queue of papers
ready for full extraction.

#### Inputs

| Input | Source Document | Description |
|-------|----------------|-------------|
| **Search keyword batteries** | [`DEEP_RESEARCH_STRATEGY.md`](../DEEP_RESEARCH_STRATEGY.md) Parts 1-8 | Per-pathway PubMed, Google Scholar, Scopus queries organized in 3 tiers (Critical/Important/Emerging). 143 target edges × 4 design tiers (meta-analysis → RCT → cohort → cross-sectional). |
| **Session prompts** | [`extraction_ref/13_RETRIEVAL_SESSIONS.md`](../extraction_ref/13_RETRIEVAL_SESSIONS.md) §3 | 17 ready-to-paste AI chatbox prompts across 4 phases (A: Vertical Slice, B: Instruments & Norms, C: Remaining Pathways, D: Dose-Response & Temporal). |
| **System prompt for AI agents** | [`extraction_ref/13_RETRIEVAL_SESSIONS.md`](../extraction_ref/13_RETRIEVAL_SESSIONS.md) §1 | Pinned instructions + structured output format (PAPER: / TITLE: / DOI: / EDGE_IDS: / EXTRACTABILITY: etc.) that every retrieval session must load. |
| **Edge reference (condensed)** | [`extraction_ref/13_RETRIEVAL_SESSIONS.md`](../extraction_ref/13_RETRIEVAL_SESSIONS.md) §2 | 143 edge IDs with short descriptions, pasted into AI context so it can map papers → edges. |
| **Current evidence state** | [`EXTRACTION_LOG.md`](../EXTRACTION_LOG.md) + `scripts/report_status.py --evidence` | What's already extracted — prevents duplicate discovery effort. |
| **Edge gap report** | `scripts/report_status.py --gaps` | Which edges have 0 or insufficient evidence rows — directs search priority. |
| **Registries (for validation)** | `registries/NODE_REGISTRY.csv` (63 nodes), `registries/EDGE_REGISTRY.csv` (143 edges), `registries/INSTRUMENT_REGISTRY.csv` (67 instruments) | Canonical entity IDs the AI must reference when categorizing papers. |

#### Process

| Step | What Happens | Operator | Key Rules |
|------|-------------|----------|-----------|
| **1. Session planning** | Select session from the 4-phase matrix (A1-A7 → B1-B3 → C1-C5 → D1-D3). Phase A (vertical slice pathways) runs first. | Human | Follow priority order: Phases A → B → C → D. ~17 sessions total, ~2-3 hrs for Phase A. |
| **2. AI deep research session** | Open new chatbox window. Paste: (a) system prompt, (b) edge reference, (c) session-specific prompt. AI searches PubMed/Scholar/S2/CrossRef and returns structured paper records. | AI (ChatGPT Deep Research / Perplexity Pro / Claude / Gemini) | One session = one chatbox window. Target 20-40 papers per session. ~300-500 total yield across all 17 sessions. |
| **3. Hallucination spot-check** | Verify 20% of DOIs by resolving at `https://doi.org/[DOI]`. Check PMIDs at PubMed. Mark unverifiable as `"verified": false`. | Human | AI chatboxes fabricate citations — this is a mandatory gate. |
| **4. Format to JSONL** | Convert AI output to one JSON object per line with required fields: `doi`, `pmid`, `title`, `year`, `design`, `cancer_type`, `sample_size`, `edge_ids`, `instruments`, `extractability`, `access`, `key_finding`, `session`. | Human | Save to `data/retrieval_candidates/<session_id>.jsonl` (e.g., `A1_neuroinflammation_2026-02-27.jsonl`). |
| **5. Triage scoring** | Run `python scripts/run_triage_sweep.py --stage 0`. Applies `candidate_papers_v1` schema, computes priority_score using formula: `3×multi_edge_yield + 2×longitudinal_bonus + 2×corr_matrix + 1×multi_cancer + 1×mediation + 1×subgroup`. | Automated | Priority bins: A (≥12 pts, extract immediately), B (6-11 pts, queue), C (<6 pts, deprioritize). |
| **6. Deduplication** | Cross-reference DOIs against `EXTRACTION_LOG.md` and existing `study_registry_v1` entries. Flag duplicates. Merge multi-session hits (same paper found in A1 and A7). | Automated + Human | Papers already extracted → skip. Papers in queue → merge edge coverage. |
| **7. Access classification** | For each surviving candidate: OA (open access — retrieve immediately), PAYWALLED (attempt Europe PMC → Unpaywall fallback), PREPRINT (flag for verification). | Automated (`crci/retrieval/fulltext_retriever.py`) | Retrieval fallback chain: Europe PMC → Unpaywall → Abstract-only flag. |

#### Outputs

| Output | Format | Consumed By | Description |
|--------|--------|-------------|-------------|
| **Citation map** | `data/retrieval_candidates/<session_id>.jsonl` | System 2 (extraction) | All discovered papers with DOI, design, edges covered, extractability rating, and access status. One file per session. |
| **Literature space shape** | Summary statistics from triage sweep | Planning / Gap analysis | Per-pathway paper counts, per-edge coverage depth, design-tier distribution. Answers: "How many meta-analyses do we have for PW_M01?" |
| **Extraction prioritization queue** | Triage bins A/B/C with priority_score | System 2 (extraction) | Rank-ordered list of papers to extract. Bin A papers enter extraction immediately. |
| **Categorized paper links** | Per `candidate_papers_v1` schema (YAML) | System 2 (extraction) | Each paper tagged with: study_type, cancer_types, regimen_phase_coverage, edges_supported, extractability (HIGH/MODERATE/LOW), value_flags (longitudinal, multi-edge yield, dose-response), access status. |
| **Edge saturation report** | Gap matrix | Feedback loop (H1) | Which edges now have candidate papers vs. which remain underserved → feeds next round of search sessions or APS priority boosts in `acquisition_queue_v1`. |

#### Categories & Sub-Categories (Paper Classification)

Papers are categorized along multiple dimensions, each with different extraction requirements:

| Dimension | Categories | Extraction Implications |
|-----------|-----------|------------------------|
| **Study type** | `RCT`, `cohort`, `cross_sectional`, `meta_analysis`, `SR`, `methods` | Determines extraction mode (DEEP/STANDARD/SHALLOW) and which templates to fill. |
| **Cancer type** | `BCA` (breast), `CRC` (colorectal), `HEM` (hematologic), `LNG` (lung), `PRS` (prostate), `HNC` (head/neck), `GYN`, `PED`, `CNS`, `mixed`, `non_cancer` | Affects scope matching (P3 Layer 2), population norm applicability, and prior construction. |
| **Phase coverage** | `T0` (pre-tx), `T1` (on-tx), `T2` (end/early recovery 0-6mo), `T3` (late recovery 6-24mo), `T4` (long-term >24mo) | Determines temporal evidence value. Papers with ≥3 timepoints spanning transitions are highest value. |
| **Evidence tier** | Meta-analysis → RCT → Prospective cohort → Cross-sectional → Preclinical | Affects quality_rating and SE calibration weights. |
| **Extractability** | `HIGH` (has tables with β/SE/CI), `MODERATE` (has some stats), `LOW` (mainly narrative) | HIGH = immediate extraction. MODERATE = may need SE derivation. LOW = deprioritize. |
| **Edge family** | Direct (behavior → cognition), Mechanistic (biomarker → pathway → cognition), Cross-pathway, Feedback | Routes to different extraction agents and templates. |
| **Data type present** | `regression_table`, `correlations`, `corr_matrix`, `means_SD`, `mediation`, `mixed_model`, `forest_plot`, `group_comparison`, `path_analysis` | Determines SE derivation method and which supplementary templates to fill. |

---

### System 2: Extraction Management System

**Goal:** For each prioritized paper, extract all quantitative evidence into structured
CSV templates that match the database schema exactly. Multi-procedure system that
handles different paper types, evidence families, and extraction modes.

#### Inputs

| Input | Source Document | Description |
|-------|----------------|-------------|
| **Paper text / PDF** | `data/manual_uploads/pdfs/<doi-slug>.pdf` | The actual research paper to extract from. |
| **Prioritized paper record** | System 1 output (`candidate_papers_v1` YAML) | Paper metadata, edges to target, extractability rating, instruments used. |
| **Extraction procedure** | [`extraction_ref/01_PROCEDURE.md`](../extraction_ref/01_PROCEDURE.md) | 10-step procedure (Steps 0-9) with template-to-table mapping. |
| **AI system prompt** | [`extraction_ref/01_PROCEDURE.md`](../01_PROCEDURE.md) | Single extraction procedure with AI session setup, pinned context list, system prompt, Steps 0-10, and analytics pipeline link. |
| **SE derivation formulas** | [`extraction_ref/03_SE_DERIVATION.md`](../extraction_ref/03_SE_DERIVATION.md) | All effect-size and standard-error conversion formulas: means→d, t→d, F→d, OR→d, r→d, CI→SE, p→SE, SD+N→SE. |
| **Controlled vocabulary** | [`extraction_ref/04_CONTROLLED_VOCAB.md`](../extraction_ref/04_CONTROLLED_VOCAB.md) | All enums, ID formats, naming conventions (effect types, study designs, cancer types, treatment phases, etc.). |
| **CSV column specifications** | [`extraction_ref/06_CSV_TEMPLATES.md`](../extraction_ref/06_CSV_TEMPLATES.md) | Exact column headers for all 12 template types (28-col edge_evidence, 9-col population_norms, etc.). All column names match DB table names exactly. |
| **Entity registries** | `registries/NODE_REGISTRY.csv` (63 nodes), `registries/EDGE_REGISTRY.csv` (143 edges), `registries/INSTRUMENT_REGISTRY.csv` (67 instruments) | Canonical IDs — every extracted edge_id, node_id, instrument_id MUST resolve against these. |
| **Existing extraction log** | [`EXTRACTION_LOG.md`](../EXTRACTION_LOG.md) + [`extraction_ref/EXTRACTION_LOG.md`](../extraction_ref/EXTRACTION_LOG.md) | Prevents re-extraction; provides precedent for tricky decisions. |
| **Quality checklist** | [`extraction_ref/11_QUALITY_CHECKLIST.md`](../extraction_ref/11_QUALITY_CHECKLIST.md) | Per-paper verification gates: edge evidence quality, population norms quality, context priors quality, temporal/instrument evidence quality. |

#### Process: Multi-Procedure Extraction Pipeline

**Step 0 — Classify the Paper (Mode Decision)**

| Condition | Mode | Templates to Fill |
|-----------|------|-------------------|
| RCT + cancer population + cognitive primary outcome | **DEEP** | All 12 templates + meta.json |
| Cohort/observational + cognitive outcomes | **STANDARD** | Templates 1-6 (core + conditional) + meta.json |
| Case report / animal / biomarker-only | **SHALLOW** | Template 1 (edge_evidence) only + meta.json |

**Step 1 — Registry Validation**

| Check | Action if Missing | Source |
|-------|-------------------|--------|
| Edge exists in EDGE_REGISTRY? | Add new row with all 14 required columns | `registries/EDGE_REGISTRY.csv` |
| Instrument exists in INSTRUMENT_REGISTRY? | Add new row | `registries/INSTRUMENT_REGISTRY.csv` |
| Node exists in NODE_REGISTRY? | Do NOT invent nodes. Fill `node_proposals_template.csv` row (proposed_node_id, label, layer, justification, related_existing_nodes). Use `NODE_PENDING:<id>` placeholder in edge CSVs. Enters `review_tasks` queue. | `registries/NODE_REGISTRY.csv`, `data/templates/node_proposals_template.csv` |

**Step 2 — Create Paper Subfolder**

```
data/manual_uploads/structured/<doi-slug>/
├── edge_evidence_template.csv        ← REQUIRED (28 extractor cols → 107 DB cols)
├── population_norms_template.csv     ← Recommended (9 extractor cols → 21 DB cols)
├── context_priors_template.csv       ← Recommended (9 extractor cols → 14 DB cols) → node_priors_v1
├── temporal_evidence_template.csv    ← If ≥2 longitudinal timepoints (8 extractor cols → 19 DB cols)
├── instrument_evidence_template.csv  ← If psychometric properties (15 extractor cols → 25 DB cols)
├── correlation_template.csv          ← If inter-domain correlations (6 extractor cols → 11 DB cols) → biomarker_correlations_v1
├── dose_evidence_template.csv        ← If dose-response data (17 cols → 18 DB cols)
├── subgroup_evidence_template.csv    ← If subgroup/interaction analyses (16 cols → 17 DB cols)
├── study_cohort_profile_template.csv ← DEEP mode demographics (25 cols → 33 DB cols)
├── profile_data_stream_template.csv  ← DEEP mode instruments×measures (21 cols → 25 DB cols)
├── stream_timepoint_template.csv     ← DEEP mode timepoints (11 cols = 11 DB cols)
└── ontology_link_template.csv        ← DEEP mode provenance links (11 cols = 11 DB cols)
```

**Steps 3-5 — Fill Templates (by Evidence Family)**

| Evidence Family | Template → DB Table | Required Columns | When to Fill | Key Rules |
|----------------|---------------------|-------------------|-------------|-----------|
| **Core: Edge evidence** | `edge_evidence_template.csv` → `edge_evidence_v1` | doi, edge_relation_id, effect_value_reported, se_reported, effect_type_reported, effect_size_type, N_effect, study_design, cancer_type, treatment_phase, upstream_instrument_id | ALWAYS (every paper) | One row per causal/associational relationship. Multi-arm: each arm vs control separately. `shared_control_flag` = true when arms share control. Positive β = improvement. |
| **Core: Population norms** | `population_norms_template.csv` → `population_norms_v1` | doi, node_id, instrument_id, mean_raw, sd_raw, N, cancer_type, treatment_phase | Paper reports baseline descriptive stats | Control group baseline only (not treatment). SD > 0. Enables mean_diff → Cohen's d auto-conversion. |
| **Core: Context priors** | `context_priors_template.csv` → `node_priors_v1` | doi, node_id, cancer_type, treatment_phase, mean, sd, source_type | Paper + published norms available | z = (observed_mean − population_mean) / population_SD. Default sd = 0.5. |
| **Conditional: Temporal** | `temporal_evidence_template.csv` → `temporal_evidence_v1` | doi, edge_relation_id, timepoint_weeks, effect, se, is_recovery, N | ≥2 longitudinal timepoints | One row per timepoint per edge. is_recovery = 0 (intervention) or 1 (follow-up). |
| **Conditional: Instrument** | `instrument_evidence_template.csv` → `instrument_evidence_v1` | doi, instrument_id, instrument_name, cronbachs_alpha, test_retest_reliability, N, cancer_type, treatment_phase, cancer_validated | Paper reports psychometric properties | Cronbach's α, ICC, factor loadings. Flag cancer_validated = true/false. |
| **Conditional: Correlations** | `correlation_template.csv` → `biomarker_correlations_v1` | doi, node_a_id, node_b_id, rho, N, partial_or_zero | Paper reports inter-domain correlations | rho ∈ [-1, 1]. Specify partial vs zero-order. |
| **Extended: Dose-response** | `dose_evidence_template.csv` → `dose_evidence_v1` | action_id, dose_level, dose_unit, effect, dose_response_shape | Paper reports dose-response data | Extract EC₅₀, Emax if reported — feeds Category A tables. |
| **Extended: Subgroup** | `subgroup_evidence_template.csv` → `subgroup_evidence_v1` | edge_id, modifier_variable, modifier_value, interaction_beta, subgroup_effect | Paper reports subgroup/interaction analyses | modifier_variable: APOE_status, age_group, sex, etc. |
| **Extended: Cohort profile** | `study_cohort_profile_template.csv` → `study_cohort_profiles_v1` | cohort_label, N_analyzed, sex_female_pct, age_mean, age_sd | DEEP mode | Per-arm demographics. |
| **Extended: Data streams** | `profile_data_stream_template.csv` → `profile_data_streams_v1` | — | DEEP mode | Instruments × measures per cohort. |
| **Extended: Timepoints** | `stream_timepoint_template.csv` → `stream_timepoints_v1` | — | DEEP mode | Measurement timepoints per stream. |
| **Extended: Ontology links** | `ontology_link_template.csv` → `ontology_links_v1` | — | DEEP mode | Provenance links. |

**Step 6 — Create meta.json**

```json
{
  "doi": "10.xxxx/...",
  "title": "...", "authors": ["..."], "year": 2024, "journal": "...",
  "study_design": "RCT", "cancer_type": "breast",
  "treatment_phase": "early_recovery", "extraction_mode": "DEEP",
  "n_total": 50, "n_treatment": 25, "n_control": 25,
  "targeted_edges": ["ER_ACTIVITY_PROC_SPEED"],
  "risk_of_bias": { "overall": "low" }
}
```
Saved to `data/manual_uploads/pdfs/<doi-slug>.meta.json`.

**Step 7 — Quality Gate (Pre-Load Verification)**

Complete [`extraction_ref/11_QUALITY_CHECKLIST.md`](../extraction_ref/11_QUALITY_CHECKLIST.md):
- [ ] Every edge_relation_id resolves in EDGE_REGISTRY
- [ ] Every instrument_id resolves in INSTRUMENT_REGISTRY
- [ ] effect_value_reported verified against source table/figure
- [ ] se_reported either directly reported OR derived with documented formula
- [ ] se_derivation_level filled for every row
- [ ] Sign convention documented
- [ ] No double-counting (shared controls flagged)
- [ ] Population norms from control group baseline only, SD > 0
- [ ] Context priors z-scores computed correctly

**Extraction Decision Documentation**

Every extraction records judgment calls in the extraction log:

| Decision Category | Example | Risk Level |
|------------------|---------|------------|
| `[INST_MAP]` | CogState ISL-DR mapped to INST_HVLTR | MEDIUM |
| `[SIGN_CONV]` | Flipped sign (lower TMT = better) | LOW |
| `[MISSING_DATA]` | SE derived from CI: SE = (upper-lower)/(2×1.96) | MEDIUM |
| `[BIAS_ADJ]` | No blinding → rob_overall = "moderate" | LOW |
| `[CONSTRUCT]` | "Mental flexibility" mapped to NODE_COG_EXEC_PLANNING | MEDIUM |
| `[DUPLICATE]` | Same cohort as Smith 2020; different outcome | HIGH |

#### Outputs

| Output | Format | Location | Consumed By |
|--------|--------|----------|-------------|
| **Filled CSV templates** | 1-12 CSV files per paper | `data/manual_uploads/structured/<doi-slug>/` | System 3 (load_evidence_into_db.py) |
| **meta.json** | JSON | `data/manual_uploads/pdfs/<doi-slug>.meta.json` | System 3 (study registration) |
| **Extraction log entry** | Markdown (EXT-YYYY-NNNN) | `EXTRACTION_LOG.md` / `extraction_ref/EXTRACTION_LOG.md` | Audit trail, deduplication |
| **Registry additions** | CSV rows | `registries/EDGE_REGISTRY.csv`, `registries/INSTRUMENT_REGISTRY.csv` | System 3 (seed loader) |
| **Review tasks** | Flagged decisions | `EXTRACTION_LOG.md` decision tables | Human review queue |

#### Tables / Schema (12 template types)

| # | Template CSV | Ext Cols | DB Cols | → DB Table | Category |
|---|-------------|----------|---------|-----------|----------|
| 1 | `edge_evidence_template.csv` | 28 | 107 | `edge_evidence_v1` | Core (REQUIRED) |
| 2 | `population_norms_template.csv` | 9 | 21 | `population_norms_v1` | Core |
| 3 | `context_priors_template.csv` | 9 | 14 | `node_priors_v1` ⚠️ | Core |
| 4 | `temporal_evidence_template.csv` | 8 | 19 | `temporal_evidence_v1` | Conditional |
| 5 | `instrument_evidence_template.csv` | 15 | 25 | `instrument_evidence_v1` | Conditional |
| 6 | `correlation_template.csv` | 6 | 11 | `biomarker_correlations_v1` ⚠️ | Conditional |
| 7 | `dose_evidence_template.csv` | 17 | 18 | `dose_evidence_v1` | Extended |
| 8 | `subgroup_evidence_template.csv` | 16 | 17 | `subgroup_evidence_v1` | Extended |
| 9 | `study_cohort_profile_template.csv` | 25 | 33 | `study_cohort_profiles_v1` | Extended |
| 10 | `profile_data_stream_template.csv` | 21 | 25 | `profile_data_streams_v1` | Extended |
| 11 | `stream_timepoint_template.csv` | 11 | 11 | `stream_timepoints_v1` | Extended |
| 12 | `ontology_link_template.csv` | 11 | 11 | `ontology_links_v1` | Extended |

> ⚠️ `context_priors_template.csv` → `node_priors_v1` (NOT `context_priors_v1`)
> ⚠️ `correlation_template.csv` → `biomarker_correlations_v1` (NOT `correlation_evidence_v1`)

---

### System 3: Extraction → Database Transportation & Management System

**Goal:** Load filled CSV templates into the SQLite database, harmonize effect scales,
calibrate standard errors, and compile evidence into ready-to-use edge parameters.

#### Inputs

| Input | Source | Description |
|-------|--------|-------------|
| **Filled CSV templates** | System 2 output (`data/manual_uploads/structured/<doi-slug>/*.csv`) | 1-12 CSV files per paper with extracted evidence. |
| **meta.json** | System 2 output (`data/manual_uploads/pdfs/<doi-slug>.meta.json`) | Paper metadata for study_registry_v1 registration. |
| **Registry CSVs** | `registries/EDGE_REGISTRY.csv`, `registries/NODE_REGISTRY.csv`, `registries/INSTRUMENT_REGISTRY.csv`, `registries/MEASURE_REGISTRY.csv`, `registries/PATHWAY_REGISTRY.csv` | Canonical entity definitions — reseeded on every load. |
| **Seed CSVs** | `crci/database/seeds/*.csv` | action_catalog, dose_bridges, modifier_rules, etc. |
| **Existing database** | `crci_dev.db` (SQLite) | Current state — new evidence is UPSERT-merged. |

#### Process: 12-Step Automated Pipeline

Executed by `python scripts/load_evidence_into_db.py [--verbose] [--dry-run] [--reset]`

| Step | What It Does | Tables Affected | Key Logic |
|------|-------------|-----------------|-----------|
| **1** | **Reseed edge definitions** from EDGE_REGISTRY.csv | `edge_relations_definitions_v1` (A1) | Full replace — 143 rows. Picks up any new edges added during System 2. |
| **1b** | **Reseed node + instrument definitions** from registries | `biomarker_node_definitions_v1` (A3), `instrument_definitions_v1` (A4) | Full replace — 63 nodes, 67 instruments. |
| **1c** | **Reseed measures + pathways** from registries | `measure_definitions_v1` (A5), `pathways_v1` (A26) | Full replace — 82 measures, 22 pathways. |
| **2** | **Clean up legacy entries** | Various | Remove orphaned references from prior schema versions. |
| **3** | **Register studies** from meta.json | `study_registry_v1` (B1) | Auto-discovers all DOIs in `data/manual_uploads/structured/`. Creates study_id from DOI slug. |
| **4** | **Load edge evidence** CSVs | `edge_evidence_v1` (B6) | Scans all `edge_evidence_template.csv` files. DOI → study_id lookup. Auto-generates: `ler_id`, `edge_param_id`, `span_hash`, `edge_family`, `node_x`/`node_y` from EDGE_REGISTRY. Sets `entered_by = "manual_csv_import"`. |
| **4b** | **Load 11 auxiliary family CSVs** | `node_priors_v1` (C3), `population_norms_v1` (B11), `temporal_evidence_v1` (B12), `instrument_evidence_v1` (B10), `biomarker_correlations_v1` (A30), `dose_evidence_v1` (B13), `subgroup_evidence_v1` (B14), `study_cohort_profiles_v1` (B2), `profile_data_streams_v1` (B3), `stream_timepoints_v1` (B4), `ontology_links_v1` (B5) | Each CSV type → dedicated importer in `crci/extraction/family_importers.py`. DOI → study_id resolved per row. |
| **4c** | **Harmonize scales to Cohen's d** (SD borrowing) | `edge_evidence_v1` (updates in-place) | For `mean_diff` rows: borrows SD from `population_norms_v1` to compute Cohen's d. Updates `harmonized_beta`, `harmonized_se`, `harmonized_scale`, `harmonization_status`. |
| **4d** | **Apply 7-layer SE_eff calibration** (Formula P3-8) | `edge_evidence_v1` (updates in-place) | Inflates SE to account for: σ²_sample + σ²_design + σ²_convert + σ²_scope + σ²_struct + σ²_fresh + σ²_7. Produces `calibrated_se_eff`. |
| **5** | **Seed action_catalog** | `action_catalog_v1` (A21) | 8 canonical interventions. |
| **5b** | **Seed dose_bridges** | `dose_bridges_v1` (C2) | Pre-loaded dose-response curves. |
| **6** | **Compile evidence → edges** (IVW aggregation) | `edges_v1` (C1) | Groups evidence by edge_relation_id. Inverse-Variance Weighted pooling: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i). Writes compiled edge parameters: pooled_beta, pooled_se, k_studies, evidence_grade. |

#### Column Mapping Logic (CSV → DB)

All 12 CSV templates use **DB column names directly** — the only transforms are:

| Transform | Applied To | Logic |
|-----------|-----------|-------|
| `doi` → `study_id` | All templates | Lookup DOI in `study_registry_v1` to get internal ID |
| Auto-generated IDs | `edge_evidence_v1` | `ler_id = LER_{study_id}_{edge_relation_id}_{span_hash}`, `edge_param_id = EP_{edge_relation_id}_{hash[:8]}` |
| Edge metadata lookup | `edge_evidence_v1` | `edge_family`, `node_x`, `node_y` looked up from `edge_relations_definitions_v1` |
| Harmonized columns | `edge_evidence_v1` | `harmonized_beta`, `harmonized_se`, `harmonized_scale` computed from raw values in Step 4c |
| Calibrated SE | `edge_evidence_v1` | `calibrated_se_eff` computed in Step 4d |
| Prior metadata | `node_priors_v1` | `prior_id`, `prior_space = "z_score"`, `dist_family = "normal"` auto-generated |
| Timestamps | All | `entered_at = UTC now`, `entered_by = "manual_csv_import"`, `version = 1`, `active = 1` |

#### Outputs

| Output | DB Table(s) | Consumed By | Description |
|--------|-------------|-------------|-------------|
| **Registered studies** | `study_registry_v1` (B1) | All extraction phases, Chain B | One row per paper; links DOI → study_id. |
| **Raw evidence rows** | `edge_evidence_v1` (B6, 76+ cols) | P2-P4 harmonization pipeline, Chain B evidence_loader | Core evidence store: β, SE, design, population, instruments, etc. |
| **Harmonized evidence** | `edge_evidence_v1` (harmonized_* fields) | P4 meta_analyzer | Scale-aligned (Cohen's d) with SD-borrowed conversions. |
| **Calibrated evidence** | `edge_evidence_v1` (calibrated_se_eff) | P4 meta_analyzer, Chain F | SE inflated via 7-layer decomposition for honest uncertainty. |
| **Population norms** | `population_norms_v1` (B11) | P2 scope_matching, P7 prior_compiler | Baseline cognitive scores in cancer populations — enables z-scoring. |
| **Node priors** | `node_priors_v1` (C3) | Chain C prior_loader | Scoped prior distributions (mean_z, sd_z) per node × cancer_type × treatment_phase. |
| **Temporal evidence** | `temporal_evidence_v1` (B12) | P7 temporal_compiler | Per-timepoint effect sizes for trajectory fitting. |
| **Instrument evidence** | `instrument_evidence_v1` (B10) | P7 psychometric_compiler | Reliability/validity data for measurement noise estimation. |
| **Auxiliary evidence** | `biomarker_correlations_v1`, `dose_evidence_v1`, `subgroup_evidence_v1`, `study_cohort_profiles_v1`, `profile_data_streams_v1`, `stream_timepoints_v1`, `ontology_links_v1` | P7 compilers, Chain C, Provenance audit | Supplementary evidence families. |
| **Compiled edge parameters** | `edges_v1` (C1) | Chain A edge_loader, Chain B, Chain D, Chain F | IVW-pooled β, SE, evidence grade, k_studies per edge — the final parameters consumed by the runtime algorithm. |
| **Reseeded Class A definitions** | `edge_relations_definitions_v1`, `biomarker_node_definitions_v1`, `instrument_definitions_v1`, `measure_definitions_v1`, `pathways_v1` | All pipeline stages | Canonical entity definitions kept in sync with registry CSVs. |

#### Verification Commands

```bash
# Preview without writing (dry run)
python scripts/load_evidence_into_db.py --dry-run

# Full load with verbose output
python scripts/load_evidence_into_db.py --verbose

# Wipe and reload everything
python scripts/load_evidence_into_db.py --reset --verbose

# Post-load verification
python scripts/report_status.py --schema     # Table row counts
python scripts/report_status.py --evidence   # Per-edge evidence detail
```

#### System 3 Post-Load Checks

- [ ] Row counts match expected (edge_evidence rows = sum of all template rows)
- [ ] No orphaned edge_relation_ids (all reference valid `edge_relations_definitions_v1`)
- [ ] No orphaned instrument_ids (all reference valid `instrument_definitions_v1`)
- [ ] `edges_v1` updated with new compiled estimates
- [ ] Harmonized_beta populated for all rows (Step 4c success)
- [ ] Calibrated_se_eff populated for all rows (Step 4d success)

---

## A. Automated + Manual Acquisition (ACQ)

| Box ID | Box Label | Primary Responsibility | Inputs | Outputs | DB Tables Written | Actual Module(s) | Status |
|--------|-----------|----------------------|--------|---------|-------------------|-------------------|--------|
| A1 | Class A Registries | Canonical registries for nodes / edges / instruments / pathways | CSV/SQL seeds | ORM objects in Class A tables | `biomarker_node_definitions_v1` (A3), `edge_relations_definitions_v1` (A1), `instrument_definitions_v1` (A4), `measure_definitions_v1` (A5), `pathways_v1` (A26), `node_search_terms_v1` (A34) | `crci/database/seed_loader.py`, `crci/database/seeds/*.sql`, `registries/*.csv` | ✅ Implemented |
| A2 | Query Generator | Deterministic query templates per workstream/edge gap | Registries + gap reports | Query strings | _(no dedicated table — queries are ephemeral)_ | `crci/retrieval/query_generator.py` | ✅ Implemented |
| A3 | Search Coordinator | Executes queries across PubMed / OpenAlex (primary), with Europe PMC / Crossref available adapters | Query strings | Candidate records | _(results cached in `data/retrieval_cache/`)_ | `crci/retrieval/search_coordinator.py`, `crci/retrieval/adapters/` (pubmed, openalex, europe_pmc, crossref, unpaywall) | ✅ Implemented |
| A4 | APS Scorer + Dedup | Prioritize + deduplicate candidates | Candidate records | Ranked, deduped set | `acquisition_queue_v1` | `crci/retrieval/aps_scorer.py`, `crci/retrieval/id_resolver.py`, `crci/retrieval/identifier_utils.py` | ✅ Implemented |
| A5 | Full-Text Retriever | Retrieval fallback chain (Europe PMC → Unpaywall → abstract-only) | Candidate DOIs/PMIDs | PDFs / text / abstract-only flag | _(files in `data/retrieval_cache/`)_ | `crci/retrieval/fulltext_retriever.py` | ✅ Implemented |
| A6 | Manual Upload Pathway | Human-in-the-loop PDF/CSV/DOI ingestion | PDF / CSV / JSON / DOI | Normalized ingest record | `study_registry_v1`, `extraction_runs` | `crci/retrieval/manual_upload_watcher.py` | ✅ Implemented |
| A7 | Acquisition Queue + Scheduler | Queue management + saturation detection | Retrieval tasks | Retrieved asset pointers | `acquisition_queue_v1` | `crci/retrieval/acquisition_scheduler.py`, `crci/retrieval/saturation_detector.py` | ✅ Implemented |
| A8 | Abstract Screener | Relevance pre-filter before full extraction | Abstract text | Accept/reject decision | _(decision inline, not persisted)_ | `crci/retrieval/abstract_screener.py` | ✅ Implemented |
| A9 | Hop Discoverer | Extract constituent studies from SRs/MAs | SR/MA paper | Child study DOIs | `acquisition_queue_v1` | `crci/retrieval/hop_discoverer.py` | ✅ Implemented |

---

## B. P0 Triage + Structural Decomposition

| Box ID | Box Label | Primary Responsibility | Inputs | Outputs | DB Tables Written | Actual Module(s) | Status |
|--------|-----------|----------------------|--------|---------|-------------------|-------------------|--------|
| B1 | Relevance Screening | EX-P0 triage: relevance / inclusion gate | Paper text / PDF | Accept/reject + extraction mode | `extraction_audit_v1` | `crci/extraction/p0_triage/relevance_screening.py` | ✅ Implemented |
| B2 | PDF Ingestion | Parse PDF to text, build section map | PDF file | Raw text + section boundaries | _(in-memory PaperMap artifact)_ | `crci/extraction/p0_triage/pdf_ingestion.py` | ✅ Implemented |
| B3 | Paper Type Classifier | Primary classification → subtype + execution mode | PaperMap | `PaperSubtype` + mode | `extraction_audit_v1` | `crci/extraction/p0_triage/paper_type_classifier.py` | ✅ Implemented |
| B4 | Mode Selection | Select SHALLOW/STANDARD/DEEP based on paper type + components | Classification | Extraction mode | `extraction_runs.extraction_mode` | `crci/extraction/p0_triage/mode_selection.py` | ✅ Implemented |
| B5 | P0 Runner | Orchestrate B1–B4 in sequence | PDF path | TriageResult (mode + components + PaperMap) | `extraction_runs`, `extraction_audit_v1` | `crci/extraction/p0_triage/runner.py` | ✅ Implemented |

**Note**: The original mapping included "Component Inventory (P0-S3)" and "Agent Activation Planner" as separate boxes. In the implementation, component detection is embedded in `paper_type_classifier.py` and agent activation is handled by `p1_extraction/runner.py` based on extraction mode. No separate `agent_plans_v1` table exists.

---

## C. Parallel Extraction (P1 Agents)

### C0. Pipeline Objects (shared infrastructure)

| Box ID | Primary Responsibility | Inputs | Outputs | DB Tables Written | Actual Module(s) | Status |
|--------|----------------------|--------|---------|-------------------|-------------------|--------|
| C0 | Shared input router / context builder | PaperMap + classification | Agent contexts (sections, prior outputs) | _(in-memory)_ | `crci/extraction/context_wiring.py` | ✅ Implemented |
| C16 | Annotation persistence | Agent annotation emissions | Persisted annotations | `study_annotations_raw_v1`, `study_annotations_v1` | `crci/extraction/p1_extraction/annotation_trust_boundary.py`, `crci/extraction/p1_extraction/annotation_lifecycle.py` | ✅ Implemented |
| C17 | Extraction completeness report | Expected fields vs observed | Completeness rows | `extraction_completeness_v1` | `crci/extraction/completeness_checker.py` | ✅ Implemented |

### Agent Group

| Agent ID | Agent Label | Primary Extraction Targets | DB Tables Written (via persistence layer) | Annotation Categories Emitted | Actual Module | Status |
|----------|-------------|---------------------------|------------------------------------------|-------------------------------|----------------|--------|
| AG01 | Metadata | Bibliographic, identifiers, trial registration | `study_registry_v1` (B1) | `methodological_innovation` (if methods paper) | `crci/extraction/p1_extraction/agents/ag01_metadata.py` | ✅ |
| AG02 | Design | RCT/observational design fields, bias-relevant structure | `study_registry_v1.study_design`, `edge_evidence_v1.rob_*` | `limitation_design`, `model_diagnostic` | `crci/extraction/p1_extraction/agents/ag02_design.py` | ✅ |
| AG03 | Cohort + EXT | Sample sizes, demographics, population cognitive scores | `study_cohort_profiles_v1` (B2), `population_norms_v1` (B11) | `limitation_generalizability`, `adherence_data` | `crci/extraction/p1_extraction/agents/ag03_cohort.py` | ✅ |
| AG04 | Outcomes | Outcome definitions, instruments, cognitive domains | `profile_data_streams_v1` (B3), `stream_timepoints_v1` (B4) | `instrument_observation`, `temporal_trajectory` | `crci/extraction/p1_extraction/agents/ag04_outcome.py` | ✅ |
| AG05 | StatsLabel + EXT | Effect size + precision extraction, subgroup interactions | `edge_evidence_v1` (B6, via trust boundary → persistence), `subgroup_evidence_v1` (B14) | `null_finding_context` (when β≈0 with adequate N) | `crci/extraction/p1_extraction/agents/ag05_stats_label.py` | ✅ |
| AG06 | Exposure + EXT | Lifestyle/intervention exposure, doses | `edge_evidence_v1` (exposure fields), `dose_evidence_v1` (B13) | `dose_response_qualitative`, `adverse_event` | `crci/extraction/p1_extraction/agents/ag06_exposure.py` | ✅ |
| AG07 | Mediator | Biomarkers, mediators, pathway chain nodes | `ontology_links_v1` (B5), `pathway_biomarkers_v1` (B9) | `mechanism_hypothesis`, `mechanism_detail_subnode`, `mechanism_interaction` | `crci/extraction/p1_extraction/agents/ag07_mediator.py` | ✅ |
| AG08 | Temporal + EXT | Timepoints, trajectories, onset/decay | `temporal_evidence_v1` (B12) | `temporal_onset`, `temporal_decay`, `temporal_trajectory` | `crci/extraction/p1_extraction/agents/ag08_temporal.py` | ✅ |
| AG09 | Reconciliation | Cross-agent conflict resolution | _(reconciliation report — in-memory)_ | `literature_comparison` (from Discussion) | `crci/extraction/p1_extraction/agents/ag09_reconciliation.py` | ✅ |
| AG10 | Strategic Intel | Research gaps, limitations, practical recommendations | `study_annotations_v1` only (annotation-only agent) | `research_gap`, `future_research`, `practical_recommendation`, `limitation_unmeasured_confounder`, `replication_status` | `crci/extraction/p1_extraction/agents/ag10_strategic_intel.py` | ✅ |
| AG11 | Instrument Validation | Psychometric properties (reliability, validity) | `instrument_evidence_v1` (B10) | `instrument_observation` | `crci/extraction/p1_extraction/agents/ag11_instrument_validation.py` | ✅ |

### ⚠ Agent → Table Wiring Issues (from original document)

The original mapping sheet listed tables like `paper_metadata_v1`, `study_design_v1`, `cohort_v1`, `outcomes_v1`, `stats_labels_v1`, `exposure_v1`, `mediator_v1`, `reconciled_evidence_v1`. **None of these tables exist in the schema.** The actual persistence path is:

1. **Agents emit `SpanLabel[]` + `RawAnnotationEmission[]`** (in-memory)
2. **Trust Boundary** (`tb_trust_boundary/`) validates spans → `edge_evidence_v1` (numerics) or quarantine
3. **Annotation Trust Boundary** routes annotations → `study_annotations_raw_v1` → `study_annotations_v1`
4. **Family Importers** (`family_importers.py`) route typed evidence → `B10–B14` intermediate tables
5. **Evidence Writer** (`evidence_writer.py`) persists harmonized claims → `edge_evidence_v1`

The agents themselves do NOT write directly to DB — they produce typed output objects consumed by the pipeline's persistence layer.

---

## D. Trust Boundary → Harmonization → Calibration

| Box ID | Pipeline Phase | Primary Responsibility | Inputs | Outputs | DB Tables Written | Actual Module(s) | Status |
|--------|---------------|----------------------|--------|---------|-------------------|-------------------|--------|
| D1 | Trust Boundary (TB) | Deterministic firewall: numeric parsing, consistency checks, QA gate | SpanLabels from AG01–AG11 | Validated parse objects or quarantined records | `evidence_validation_quarantine_v1`, `edge_evidence_quarantine_v1` | `crci/extraction/tb_trust_boundary/` (`numeric_parser.py`, `consistency_checker.py`, `group_assembler.py`, `qa_gate.py`, `quarantine_writer.py`) | ✅ |
| D2 | P2 Harmonization — SE Derivation | Effect/precision conversion engine (CI→SE, OR→logOR etc.) | Raw effect values + precision | Common effect + SE on SMD scale | `edge_evidence_v1` (harmonized_* fields) | `crci/extraction/p2_harmonization/se_derivation_cascade.py`, `conversion_router.py`, `conversion_executor.py` | ✅ |
| D3 | P2 Harmonization — Orientation & Scale | Orientation alignment, scale harmonization, plausibility checks | Converted effects | Aligned evidence rows | `edge_evidence_v1` (harmonization_status, harmonized_scale) | `crci/extraction/p2_harmonization/orientation_aligner.py`, `scale_harmonizer.py`, `plausibility_checker.py`, `scope_matching.py` | ✅ |
| D3b | P2 Harmonization — SD Standardization | SD standardization for beta-path conversion | Raw betas + SDs | SD-standardized effects | `edge_evidence_v1` | `crci/extraction/p2_harmonization/sd_standardization.py` | ✅ |
| D3c | P2 Harmonization — Identification | Causal identification scoring (estimand, instrument) | Evidence rows | Identification scores | `edge_evidence_v1.identification_status` | `crci/extraction/p2_harmonization/identification_scorer.py` | ✅ |
| D3d | P2 Harmonization — Parameter Family | Assign parameter families for freshness weighting | Evidence rows | Family assignment + freshness weight | `edge_evidence_v1.parameter_family`, `.freshness_w` | `crci/extraction/p2_harmonization/parameter_family_assigner.py` | ✅ |
| D4 | P3 Seven-Layer SE Calibration | Seven-layer SE decomposition (σ²_sample + σ²_design + σ²_convert + σ²_scope + σ²_struct + σ²_fresh + σ²_7) | Harmonized rows + annotations | SE_eff + decomposition | `edge_evidence_v1` (SE fields) | `crci/extraction/p3_heterogeneity/layers.py`, `se_eff_assembly.py`, `freshness_policy.py` | ✅ |
| D5 | Validated Writer | Persist calibrated evidence with UPSERT semantics | Calibrated rows | Written evidence | `edge_evidence_v1` (final), `evidence_validation_quarantine_v1` (rejected) | `crci/extraction/validated_writer/persistence.py`, `validation.py`, `standardization.py` | ✅ |

### DB Tables Read by D-Layer (from Class A)

| Table | Used By | Purpose |
|-------|---------|---------|
| `harmonization_rules_v1` (A6) | `conversion_router.py` | Look up conversion family/formula |
| `edge_ontology_v1` (A2) | `orientation_aligner.py` | Sign conventions, allowed scales |
| `edge_relations_definitions_v1` (A1) | `scope_matching.py`, `parameter_family_assigner.py` | Default direction, edge family |
| `literary_constraints_v1` (A9) | _(intended: `plausibility_checker.py`)_ | Biological bounds for plausibility gate — **NOT WIRED: no code reads this table** |
| `literary_mechanistic_priors_v1` (A8) | _(P3 structural σ² layer)_ | Literature priors for SE inflation |

---

## E. Evidence & Knowledge Stores

### Class A — Knowledge (34 tables, human-curated)

| Table ID | Table Name | Purpose | Populated By | Consumed By |
|----------|-----------|---------|-------------|-------------|
| A1 | `edge_relations_definitions_v1` | Permitted DAG edges | Seed loader / registry CSV | P2, P4, Chain A, Chain B |
| A2 | `edge_ontology_v1` | Operational constraints per edge | Seed loader | P2 orientation/scale |
| A3 | `biomarker_node_definitions_v1` | 63-node DAG definitions | Seed loader / NODE_REGISTRY.csv | Chain A, P2 scope matching |
| A4 | `instrument_definitions_v1` | Assessment instruments | Seed loader / INSTRUMENT_REGISTRY.csv + P7 psychometric_compiler | Chain C observation_mapper |
| A5 | `measure_definitions_v1` | Biomarker/wearable measures | Seed loader / MEASURE_REGISTRY.csv | P2, Chain B, Chain C |
| A6 | `harmonization_rules_v1` | Conversion formulas | Seed loader | P2 conversion_router |
| A7 | `predictor_alignment_rules_v1` | Transportability alignment | Seed + manual curation | P3 Layer 2 (scope σ²) |
| A8 | `literary_mechanistic_priors_v1` | Literature priors for sparse edges | **Manual curation + P7 prior_compiler** | P3 structural σ², P4 prior_selector |
| A9 | `literary_constraints_v1` | Biological ceiling/floor constraints | **Manual curation** | P2 plausibility, Chain D safety |
| A10 | `contraindication_rules_v1` | Safety rules | Seed + manual curation | Chain D safety_checker |
| A11 | `action_contraindication_links_v1` | Action↔safety rule links | Seed + manual curation | Chain D safety_checker |
| A12 | `contraindication_escalation_policy_v1` | Escalation behaviors | Seed | Chain D safety_checker |
| A13 | `validation_rules_v1` | Cross-table validation contracts | Seed | Unit tests / ETL validation |
| A14 | `variable_definitions_v1` | Patient modifier variables | Seed + manual curation | Chain C modifier_application |
| A15 | `variable_to_input_map_v1` | Patient input → engine variable | Seed | Runtime adaptive_questions |
| A16 | `baseline_modifier_definitions_v1` | Modifier rules (§2.15) | **Manual curation + P7 modifier_compiler** | Chain C modifier_application |
| A17 | `derived_feature_definitions_v1` | Computed feature specs | Seed | Chain C observation_mapper |
| A18 | `triangulation_sets_v1` | Measurement fusion groups | Seed | Chain C (future) |
| A19 | `triangulation_members_v1` | Members per triangulation set | Seed | Chain C (future) |
| A20 | `description_templates_v1` | UI text templates | Seed | Presentation layer |
| A21 | `action_catalog_v1` | Atomic interventions | Seed | Chain D intervention_loader |
| A22 | `question_bank_v1` | Adaptive intake questions | Seed + manual curation | Runtime adaptive_questions |
| A23 | `question_observation_models_v1` | Answer→update mappings | Seed | Runtime adaptive_questions |
| A24 | `normalization_refs_v1` | Population norms for z-scoring | **Manual curation + P7 prior_compiler** | Chain C observation_mapper |
| A25 | `observation_noise_v1` | Measurement noise/reliability | **Manual curation + P7 psychometric_compiler** | Chain C observation_mapper |
| A26 | `pathways_v1` | 15 mechanistic + 5 clinical pathways | Seed / PATHWAY_REGISTRY.csv | P5 chain_validator, Chain B pathway_evidence_scorer |
| A27 | `pathway_interactions_v1` | Pathway-pair interactions | Seed + manual curation | Chain D synergy_bundle |
| A28 | `intervention_synergy_v1` | Pairwise intervention synergy | **Manual curation + P7 synergy_compiler** | Chain D synergy_bundle |
| A29 | `recovery_trajectories_v1` | Stretched exponential recovery params | **Manual curation + P7 temporal_compiler** | Chain E recovery_trajectory |
| A30 | `biomarker_correlations_v1` | Correlated mediator pairs (D matrix) | Seed + manual curation | Chain C prior_loader, Chain D mc_sampler |
| A31 | `feedback_loops_v1` | 5 DAG feedback structures | Seed | Chain A spectral_validator |
| A32 | `intervention_kernels_v1` | Temporal kernels per intervention | **Manual curation + P7 temporal_compiler** | Chain D intervention_loader, Chain E |
| A33 | `mid_thresholds_v1` | MID per cognitive domain | Seed | Chain F composite_scorer, Presentation |
| A34 | `node_search_terms_v1` | PubMed search synonyms per node | Seed | Retrieval query_generator |

### Class B — Evidence (14 tables, extraction-populated)

| Table ID | Table Name | Purpose | Populated By | Consumed By |
|----------|-----------|---------|-------------|-------------|
| B1 | `study_registry_v1` | One row per paper | AG01 → evidence_writer | All extraction phases, Chain B |
| B2 | `study_cohort_profiles_v1` | Cohort demographics per study | AG03 → evidence_writer | P2 scope_matching, P3 Layer 2 |
| B3 | `profile_data_streams_v1` | Instruments × measures per cohort | AG04 → evidence_writer | P2, Chain C |
| B4 | `stream_timepoints_v1` | Measurement timepoints | AG04 → evidence_writer | P2, Chain C |
| B5 | `ontology_links_v1` | Provenance links | AG07 → evidence_writer | Provenance audit |
| B6 | `edge_evidence_v1` | **THE main evidence store (76+ cols)** | AG05 → TB → P2 → P3 → P4 → validated_writer | P4 meta_analyzer, Chain B, Chain F |
| B7 | `edge_param_builds_v1` | Build provenance audit trail | P4 edge_writer | Audit / reproducibility |
| B8 | `triangulation_evidence_v1` | Cross-method agreement | _(future, from multi-instrument studies)_ | Chain C fusion (future) |
| B9 | `pathway_biomarkers_v1` | Biomarker → pathway loadings | AG07 → evidence_writer | Chain B pathway_evidence_scorer |
| B10 | `instrument_evidence_v1` | Psychometric properties | AG11 → family_importers | P7 psychometric_compiler |
| B11 | `population_norms_v1` | Population cognitive scores | AG03-EXT → family_importers | P7 prior_compiler |
| B12 | `temporal_evidence_v1` | Timepoint × effect pairs | AG08-EXT → family_importers | P7 temporal_compiler |
| B13 | `dose_evidence_v1` | Dose × effect pairs | AG06-EXT → family_importers | P7 dose_response_compiler |
| B14 | `subgroup_evidence_v1` | Subgroup interactions | AG05-EXT → family_importers | P7 modifier_compiler |
| — | `acquisition_queue_v1` | Directed acquisition queue | APS scorer, hop discoverer, annotation promotion | Retrieval scheduler |
| — | `extraction_audit_v1` | Per-stage extraction audit trail | All pipeline stages | Audit / debugging |
| — | `study_annotations_raw_v1` | Pre-reconciliation annotations | AG01–AG11 (via annotation_trust_boundary) | Annotation lifecycle |
| — | `study_annotations_v1` | **Reconciled strategic intelligence (23 cols)** | Annotation lifecycle | P3 (structural σ²), P4 (P_inclusion), promotion_monitor, feedback |

### Class C — Compiled (7 tables, pipeline-generated)

| Table ID | Table Name | Purpose | Populated By | Consumed By |
|----------|-----------|---------|-------------|-------------|
| C1 | `edges_v1` | **Compiled edge parameters** (pooled β, SE, grade) | P4 edge_writer | Chain A edge_loader, Chain B, Chain D |
| C2 | `dose_bridges_v1` | Dose→effect bridge mappings (Emax/Hill) | P7 dose_response_compiler | Chain D intervention_loader |
| C3 | `node_priors_v1` | Scoped prior distributions per node | P7 prior_compiler | Chain C prior_loader |
| C4 | `outcome_anchors_v1` | z-score → clinical severity calibration | Manual curation | Presentation layer |
| C5 | `state_estimator_specs_v1` | Bayesian estimator config | Seed | Chain C bayesian_update |
| C6 | `chain_validation_results_v1` | Chain-vs-direct validation | P5 chain_validator | Chain B, P5 sufficiency_reporter |
| C7 | `publication_bias_results_v1` | Pub bias per edge | P4b publication_bias | P4 edge_writer (SE inflation) |

### Class D — Policy (7 tables)

| Table ID | Table Name | Purpose | Consumed By |
|----------|-----------|---------|-------------|
| D1 | `objective_specs_v1` | SAFE utility function config | Chain D ranker |
| D2 | `safety_policies_v1` | Trigger→behavior mappings | Chain D safety_checker |
| D3 | `escalation_policies_v1` | Clinician escalation protocols | Chain D safety_checker |
| D4 | `status_quo_rules_v1` | Baseline dose assumptions | Chain D intervention_loader |
| D5 | `voi_rules_v1` | Adaptive question policy | Runtime adaptive_questions |
| D6 | `complexity_scaling_results_v1` | Model stability analysis | Offline validation |
| D7 | `population_archetypes_v1` | GMM cluster centroids | Chain F subpopulation_comparator |

### Class E — Output (12 tables, per-session)

| Table ID | Table Name | Purpose | Written By |
|----------|-----------|---------|-----------|
| E1 | `state_snapshots_v1` | Bayesian posterior states | Chain C posterior_writer |
| E2 | `scenario_definitions_v1` | What-if scenarios | Chain D / Runtime session |
| E3 | `scenario_items_v1` | Actions within scenarios | Chain D / Runtime session |
| E4 | `schedule_plans_v1` | Optimized schedule plans | Runtime schedule_generator |
| E5 | `schedule_items_v1` | Actions within plans | Runtime schedule_generator |
| E6 | `recommendation_runs_v1` | Run header (who, when, config) | Runtime session |
| E7 | `simulation_trace_v1` | MC simulation trace | Chain D mc_sampler |
| E8 | `decision_trace_v1` | Decision audit trail | Chain D ranker |
| E9 | `contraindication_eval_trace_v1` | Safety eval audit | Chain D safety_checker |
| E10 | `question_selection_trace_v1` | VOI question selection audit | Runtime adaptive_questions |
| E11 | `modifier_eval_trace_v1` | Personalization audit | Chain C modifier_application |
| E12 | `question_sequence_v1` | Adaptive intake record | Runtime adaptive_questions |

### Operations Tables

| Table Name | Purpose | Written By |
|-----------|---------|-----------|
| `review_tasks` | HITL review queue (ATB rejections, P6 blocks, ambiguous parses) | TB, P6, promotion_monitor |
| `policy_snapshots` | Config version snapshots per run | Pipeline orchestrator |
| `build_manifests_v1` | Compilation build provenance | P7 runner |
| `extraction_runs` | Per-paper extraction tracking | Pipeline orchestrator |
| `extraction_completeness_v1` | Missingness provenance (Module 3) | completeness_checker.py |
| `edge_evidence_quarantine_v1` | QA quarantine for rejected evidence | TB qa_gate |
| `evidence_validation_quarantine_v1` | Validation quarantine | validated_writer |

---

## F. Aggregation + Compilation

| Box ID | Pipeline Phase | Primary Responsibility | Inputs | Outputs | DB Tables Written | Actual Module(s) | Status |
|--------|---------------|----------------------|--------|---------|-------------------|-------------------|--------|
| F1 | P4 — Evidence Grouping | Group evidence by edge family + double-count prevention | `edge_evidence_v1` (harmonized) | Grouped evidence sets, lineage trees | _(in-memory EvidenceGroup)_ | `crci/extraction/p4_aggregation/evidence_grouper.py`, `double_counting.py`, `cohort_lineage_detector.py`, `shared_control_handler.py` | ✅ |
| F2 | P4 — Meta-Analysis | IVW/DL pooling, prior selection | Grouped evidence | Pooled estimates + prior specs | _(in-memory PooledEstimate, PriorSpec)_ | `crci/extraction/p4_aggregation/meta_analyzer.py`, `prior_selector.py` | ✅ |
| F3 | P4 — Edge Writer | Write compiled edges | Pooled estimates + priors | Compiled edge parameters | `edges_v1` (C1), `edge_param_builds_v1` (B7) | `crci/extraction/p4_aggregation/edge_writer.py` | ✅ |
| F4 | P4b — Publication Bias | Egger's regression, trim-and-fill, leave-one-out | Grouped evidence (k≥10) | Bias risk + SE inflation | `publication_bias_results_v1` (C7) | `crci/extraction/p4b_publication_bias/publication_bias.py` | ✅ |
| F5 | P5 — Sufficiency | Coverage analysis, chain validation, E-values | Compiled edges, pathways | Sufficiency report, chain validation results | `chain_validation_results_v1` (C6) | `crci/extraction/p5_sufficiency/coverage_analyzer.py`, `chain_validator.py`, `evalue_computer.py`, `missingness_provenance.py`, `sufficiency_reporter.py` | ✅ |
| F6 | P6 — Deployment Gate | Final validation before parameter handoff | All compiled artifacts | PASS/BLOCK decision | `review_tasks` (if BLOCK) | `crci/extraction/p6_deployment/deploy_gate.py`, `validation_runner.py` | ✅ |
| F7 | P7 — Compilers (6 families) | Compile B10–B14 intermediate evidence → Class A parameters | Intermediate evidence tables | Updated Class A parameter tables | See compiler detail below | `crci/extraction/p7_compilers/` | ✅ |

### P7 Compiler Detail

| Compiler | Reads From | Writes To | Module |
|----------|-----------|----------|--------|
| Psychometric Compiler | `instrument_evidence_v1` (B10) | `instrument_definitions_v1` (A4) updates (via `CompiledInstrument`) | `psychometric_compiler.py` |
| Prior Compiler | `population_norms_v1` (B11) | context-matched priors (via `CompiledPriorNode`) — NOT directly `node_priors_v1` | `prior_compiler.py` |
| Temporal Compiler | `temporal_evidence_v1` (B12) | `intervention_kernels_v1` (A32), `recovery_trajectories_v1` (A29) updates | `temporal_compiler.py` |
| Dose-Response Compiler | `dose_evidence_v1` (B13) | `dose_bridges_v1` (C2) updates | `dose_response_compiler.py` |
| Modifier Compiler | `subgroup_evidence_v1` (B14) | `baseline_modifier_definitions_v1` (A16) updates | `modifier_compiler.py` |
| Synergy Compiler | `edge_evidence_v1` (factorial trials) | `intervention_synergy_v1` (A28) updates | `synergy_compiler.py` |

---

## G. Runtime Causal Simulation (Algorithm Chains)

| Box ID | Chain | Primary Responsibility | Reads (Tables) | Writes (Tables) | Actual Module(s) | Status |
|--------|-------|----------------------|----------------|-----------------|-------------------|--------|
| G1a | Chain A — Graph | Load DAG topology | `biomarker_node_definitions_v1`, `edge_relations_definitions_v1`, `instrument_definitions_v1`, `edges_v1`, `feedback_loops_v1`, `pathways_v1` | _(in-memory GraphObject)_ | `crci/algorithm/chain_a_graph/` (node_loader, edge_loader, instrument_loader, graph_object, spectral_validator) | ✅ |
| G1b | Chain B — Evidence | Load & freeze evidence state | `edge_evidence_v1`, `study_registry_v1`, `edges_v1`, `pathways_v1` | _(in-memory FrozenModelState)_ | `crci/algorithm/chain_b_evidence/` (evidence_loader, evidence_compiler, pathway_evidence_scorer, frozen_state) | ✅ |
| G2 | Chain C — Posterior | Bayesian state estimation + modifiers | `node_priors_v1`, `observation_noise_v1`, `normalization_refs_v1`, `baseline_modifier_definitions_v1`, `variable_definitions_v1`, `biomarker_correlations_v1` | `state_snapshots_v1` (E1) | `crci/algorithm/chain_c_posterior/` (prior_loader, observation_mapper, bayesian_update, modifier_application, posterior_writer) | ✅ |
| G3 | Chain D — Simulation | MC do-calculus simulation + SAFE ranking | `action_catalog_v1`, `dose_bridges_v1`, `intervention_kernels_v1`, `contraindication_rules_v1`, `intervention_synergy_v1`, `objective_specs_v1`, `safety_policies_v1` | `scenario_definitions_v1`, `scenario_items_v1`, `simulation_trace_v1`, `decision_trace_v1`, `contraindication_eval_trace_v1` | `crci/algorithm/chain_d_simulation/` (intervention_loader, mc_sampler, effect_propagation, safety_checker, synergy_bundle, ranker) | ✅ |
| G4 | Chain E — Temporal | Recovery trajectory + intervention overlay | `recovery_trajectories_v1`, `intervention_kernels_v1` | _(in-memory RecoveryTrajectory, OverlayResult)_ | `crci/algorithm/chain_e_temporal/` (nadir_estimator, recovery_trajectory, intervention_overlay, uncertainty_counterfactual) | ✅ |
| G5 | Chain F — Analytics | Composite scoring, variance decomposition, EVSI, risk | `mid_thresholds_v1`, + outputs from Chains C/D/E | _(in-memory CompositeState, VarianceState)_ | `crci/algorithm/chain_f_analytics/` (composite_scorer, variance_decomposer, evsi, risk_estimator, temporal_risk, subpopulation_comparator) | ✅ |

### Runtime Orchestration Layer

| Module | Responsibility | Key Tables Read | Key Tables Written |
|--------|---------------|-----------------|-------------------|
| `crci/runtime/session.py` | Full engine session orchestration (Chains A→F) | All above | `recommendation_runs_v1` (E6) |
| `crci/runtime/adaptive_questions.py` | VOI-based question selection (Stage H) | `question_bank_v1`, `voi_rules_v1`, `question_observation_models_v1` | `question_selection_trace_v1` (E10), `question_sequence_v1` (E12) |
| `crci/runtime/schedule_generator.py` | Intervention schedule optimization (Stage G) | All simulation outputs | `schedule_plans_v1` (E4), `schedule_items_v1` (E5) |
| `crci/runtime/evidence_gap_compiler.py` | Evidence gap reporting | P5 coverage matrix, Chain F variance | _(in-memory gap report)_ |
| `crci/runtime/pathway_profiler.py` | Active pathway profiling | GraphObject, posterior | _(in-memory pathway profile)_ |
| `crci/runtime/report_assembler.py` | Final output assembly | All runtime outputs | _(RecommendationReport for presentation)_ |

---

## H. Feedback, Monitoring, Self-Improvement

| Box ID | Box Label | Primary Responsibility | Inputs | Outputs | DB Tables | Actual Module(s) | Status |
|--------|-----------|----------------------|--------|---------|-----------|-------------------|--------|
| H1 | Acquisition Feedback Loop | Gap report → APS boosts for directed retrieval | Sufficiency gap report + annotations | Updated APS scores | `acquisition_queue_v1` (boosted scores) | `crci/retrieval/aps_scorer.py` (integrate gap weights), `crci/retrieval/pathway_evidence_auditor.py` | ⚠️ Dead-wired — `aps_scorer.py` has boost logic (`author_gap_boost_ids`) but `acquisition_scheduler.py` never passes the required parameters. `pathway_evidence_auditor.py` is orphaned (never imported). The annotation→APS pipeline is unconnected. |
| H2 | Annotation Promotion Engine | Monitor accumulated annotations → propose promotions | `study_annotations_v1` (reviewed) | Promotion candidates → `review_tasks` | `study_annotations_v1`, `review_tasks` | `crci/extraction/promotion_monitor.py`, `crci/extraction/p1_extraction/annotation_lifecycle.py` | ✅ Implemented |
| H3 | Chain-vs-Direct Validation | Direct vs mechanistic path comparison | Compiled edges + pathways | Discrepancy taxonomy | `chain_validation_results_v1` (C6) | `crci/extraction/p5_sufficiency/chain_validator.py` | ✅ Implemented |
| H4 | Observability + QA | Pipeline metrics, cost tracking, audit logs | Pipeline execution | Metrics + audit | `extraction_audit_v1`, `extraction_runs`, `policy_snapshots` | `crci/llm/cost_tracker.py`, `crci/extraction/pipeline.py` (audit writes) | ✅ Partial |

---

## I. Presentation Layer

> **Note:** The presentation layer produces **view-model dataclasses** (not HTML/web output). A frontend (Streamlit, React, CLI rich-text) would consume these to produce visual output. No rendering frontend exists yet.

| Module | Responsibility | Key Tables / Inputs Read | Output Type | Status |
|--------|---------------|--------------------------|-------------|--------|
| `crci/presentation/crci_dashboard.py` | Composite CRCI score gauge | Chain F `CompositeState` | `ScoreDashboardView` | ✅ |
| `crci/presentation/evidence_browser.py` | Edge evidence table with gap highlighting | `edge_evidence_v1`, `edges_v1` | `EvidenceBrowserView` | ✅ |
| `crci/presentation/dag_viz.py` | 63-node causal DAG with edge thickness ∝ |β| | Chain A `GraphObject`, `edges_v1` | `DAGVizView` | ✅ |
| `crci/presentation/provenance_viewer.py` | Sankey/tree trace from recommendation → paper | Chain D trace, `edge_evidence_v1` | `ProvenanceChainView` | ✅ |
| `crci/presentation/intervention_cards.py` | Schedule recommendation cards | Chain D ranker output | `InterventionCardsView` | ✅ |
| `crci/presentation/trajectory_plot.py` | Recovery trajectory over time | Chain E `RecoveryTrajectory` | `ProgressTrackerView` | ✅ |
| `crci/presentation/variance_pie.py` | Variance decomposition pie chart | Chain F `VarianceState` | `UncertaintyPanelView` | ✅ |
| `crci/presentation/pathway_display.py` | Pathway-level view | Pathway scores, evidence | `PathwayDisplayView` | ✅ |
| `crci/presentation/quality_disclosure.py` | Evidence quality transparency | Evidence grades, k_studies | `QualityDisclosureView` | ✅ |
| `crci/presentation/risk_dashboard.py` | Risk assessment display | Chain F risk output | `RiskDashboardView` | ✅ |
| `crci/presentation/research_dashboard.py` | Research/gap overview | P5 sufficiency report | `ResearchDashboardView` | ✅ |
| `crci/presentation/model_inspection.py` | Model internals inspection | All chain outputs | `ModelInspectionView` | ✅ |
| `crci/presentation/render_report.py` | Assembles all views into `RecommendationReport` | All view models | `RecommendationReport` | ✅ |
| `crci/presentation/terminal_renderer.py` | CLI rich-text rendering of report | `RecommendationReport` | Terminal output | ✅ |

---

## Master Table Inventory

### Complete DB Table Count: ~85 tables (including operations + migration)

| Schema File | Tables | Class |
|-------------|--------|-------|
| `001_class_a_knowledge.sql` | 34 | A — Knowledge |
| `002_class_b_evidence.sql` | 16 (includes `acquisition_queue_v1` + `extraction_audit_v1`) | B — Evidence |
| `003_class_c_compiled.sql` | 7 | C — Compiled |
| `004_class_d_reference.sql` | 7 | D — Policy |
| `005_class_e_output.sql` | 12 | E — Output |
| `006_fk_constraints.sql` | 0 (ALTER only — FK constraints) | — |
| `007_ops_tables.sql` | 4 | Ops |
| `008_v2_migration.sql` | 2 (`study_annotations_v1`, `study_annotations_raw_v1`) | B ext |
| `009_qa_quarantine.sql` | 1 (`edge_evidence_quarantine_v1`) | QA |
| `009_conversion_hardening.sql` | 0 (ALTER only — SE derivation tracking columns) | Migration |
| `010_modules_2_3_4_5.sql` | 1 (`extraction_completeness_v1`) + ALTER TABLE extensions | Migration |
| `011_study_identity.sql` | 0 (ALTER only — doi_normalized + unique indexes) | Migration |
| `012_evidence_validation_quarantine.sql` | 1 (`evidence_validation_quarantine_v1`) | QA |
| `013_template_alignment.sql` | 0 (ALTER only — alignment fixes for 002 tables) | Migration |
| `014_edge_evidence_p2p7_columns.sql` | 0 (ALTER only — P2–P7 pipeline columns) | Migration |

---

## Gap Analysis

### 1. Tables in Schema With No Clear Producer Module

These tables exist in SQL but have no implemented code path to populate them:

| Table | Class | Gap Description | Priority |
|-------|-------|----------------|----------|
| `literary_constraints_v1` (A9) | A | **Biological bounds on trajectories.** No compiler or extraction agent populates this. Currently must be manually curated. **Neither read nor written by any code module** — `plausibility_checker.py` does NOT reference it despite design intent. Design docs (PIPELINE_EXECUTION_MAP) say Chain D should also read it, but no implementation exists. | 🔴 HIGH — needed for runtime safety bounds — currently fully dormant |
| `literary_mechanistic_priors_v1` (A8) | A | **Literature priors for sparse edges.** `prior_selector.py` reads this during P4, but no extraction agent or compiler populates it beyond manual seed data. | 🔴 HIGH — needed for P4 prior selection |
| `predictor_alignment_rules_v1` (A7) | A | **Transportability alignment rules.** Read by P3 Layer 2 scope weighting but no automated population path. **No code module references this table at all** — neither reads nor writes. | 🟡 MEDIUM — fully dormant |
| `validation_rules_v1` (A13) | A | **Cross-table validation contracts.** Schema exists but no enforcement engine reads and executes these rules programmatically. | 🟡 MEDIUM — aspirational QA |
| `variable_to_input_map_v1` (A15) | A | **Patient input → engine variable mapping.** Schema exists, consumed by runtime, but needs manual curation. | 🟡 MEDIUM |
| `outcome_anchors_v1` (C4) | C | **z-score → severity calibration.** Schema exists but no compiler populates it. **No code module reads or writes it either** — fully dormant. | 🟡 MEDIUM |
| `triangulation_evidence_v1` (B8) | B | **Cross-method agreement evidence.** Schema exists but no agent or pipeline stage writes to it. | 🟢 LOW — future multi-instrument fusion |
| `triangulation_sets_v1` (A18) / `triangulation_members_v1` (A19) | A | **Measurement fusion config.** Tables exist but Chain C doesn't yet implement fusion. | 🟢 LOW — future |
| `complexity_scaling_results_v1` (D6) | D | **Offline model stability analysis.** No module performs or writes this analysis. | 🟢 LOW — offline validation |
| `population_archetypes_v1` (D7) | D | **GMM cluster definitions.** Schema exists, `subpopulation_comparator.py` could consume it, but no GMM fitting module. | 🟢 LOW — future analytics |

### 2. Content Dimensions from PIMP Not Fully Wired to Downstream Consumers

Cross-referencing the 22 content dimensions against actual downstream wiring:

| # | Content Dimension | Captured? | Annotation Category | Downstream Consumer Wired? | Gap |
|---|------------------|-----------|--------------------|-----------------------------|-----|
| 1 | Effect estimates | ✅ Full | — | ✅ `edge_evidence_v1` → P2/P3/P4 → `edges_v1` | — |
| 2 | Study metadata | ✅ Full | — | ✅ `study_registry_v1` | — |
| 3 | Cohort demographics | ✅ Full | — | ✅ `study_cohort_profiles_v1` | — |
| 4 | Instruments/measures | ✅ Full | — | ✅ `profile_data_streams_v1` | — |
| 5 | Author-reported limitations | ✅ Via AG10 | `limitation_unmeasured_confounder`, `limitation_design` | ⚠️ Annotations stored; P3 `shared_annotation_features.py` reads them for structural σ². **But `literary_constraints_v1` (the hard-bound table) is unpopulated.** | Wire annotation promotion → `literary_constraints_v1` |
| 6 | Confounders unmeasured | ✅ Via AG10 | `limitation_unmeasured_confounder` | ⚠️ Stored; P3 Layer 5 reads. **E-value computer reads annotations but no automated path to `predictor_alignment_rules_v1`.** | Wire annotation → E-value / alignment |
| 7 | Mechanism hypotheses | ✅ Via AG07/AG10 | `mechanism_hypothesis` | ⚠️ Stored; promotion_monitor watches. **No automated path to `edge_relations_definitions_v1` creation.** | Manual promotion via review_tasks ✅ (by design) |
| 8 | Research gaps | ✅ Via AG10 | `research_gap` | ⚠️ Stored. **APS weight boost from annotations → `acquisition_queue_v1` exists in design but wiring in `aps_scorer.py` needs verification.** | Verify APS annotation weight path |
| 9 | Future research recs | ✅ Via AG10 | `future_research` | ⚠️ Stored. Same as #8. | — |
| 10 | Null/negative findings | ⚠️ Via AG05 | `null_finding_context` | ⚠️ Stored. **P_inclusion calibration in `prior_selector.py` reads annotations but path needs verification.** | Verify null-finding → P_inclusion |
| 11 | Dose-response qualitative | ✅ Via AG06 | `dose_response_qualitative` | ⚠️ Stored. **`dose_response_compiler.py` reads `dose_evidence_v1` (numeric) but doesn't yet consume qualitative annotations.** | Wire annotation → compiler constraint |
| 12 | Population-specific obs | ✅ Via AG03/AG10 | `limitation_generalizability` | ⚠️ Stored. Read by P3 Layer 2 scope σ². | ✅ Working |
| 13 | Instrument psychometric obs | ✅ Via AG04/AG11 | `instrument_observation` | ⚠️ Stored. **`psychometric_compiler.py` reads `instrument_evidence_v1` (numeric) but doesn't yet consume qualitative annotations.** | Wire annotation → compiler |
| 14 | Adherence/feasibility data | ✅ Via AG03/AG10 | `adherence_data` | ❌ **No adherence model module exists.** Annotations stored but no consumer. | Build adherence model consumer |
| 15 | Adverse events/safety | ✅ Via AG06/AG10 | `adverse_event` | ⚠️ Stored. **Promotion to `contraindication_rules_v1` is via review_tasks (manual).** No automated path. | Manual path OK for safety (by design) |
| 16 | Biological mechanism detail | ⚠️ Via AG07 | `mechanism_detail_subnode` | ⚠️ Stored for future DAG expansion. No consumer. | ✅ By design (future) |
| 17 | Temporal dynamics obs | ✅ Via AG08 | `temporal_onset`, `temporal_decay` | ⚠️ Stored. **`temporal_compiler.py` reads `temporal_evidence_v1` (numeric) but promotion of qualitative annotations to kernel params is manual.** | Wire annotation → temporal compiler |
| 18 | Comparison with prior lit | ⚠️ Via AG09 | `literature_comparison` | ⚠️ Stored. **No automated consumer in chain_validator for external consistency.** | Wire to P5 / chain validation |
| 19 | Methodological innovations | ⚠️ Via AG01 | `methodological_innovation` | ⚠️ Stored. No consumer (pipeline evolution). | ✅ By design (future) |
| 20 | Practical implications | ✅ Via AG10 | `practical_recommendation` | ⚠️ Stored. **Presentation layer doesn't yet consume these.** | Wire to report_assembler |
| 21 | Statistical model diagnostics | ⚠️ Via AG02 | `model_diagnostic` | ⚠️ Stored. **Quality scoring reads annotations but path to `quality_rating` demotion needs verification.** | Verify P2 quality scoring path |
| 22 | Replication status | ✅ Via AG10 | `replication_status` | ⚠️ Stored. **P_inclusion calibration path needs verification.** | Verify replication → P_inclusion |

### 3. Summary of Key Wiring Gaps

| Priority | Gap | Components Affected | Remediation |
|----------|-----|-------------------|-------------|
| 🔴 | `literary_constraints_v1` has no producer AND no reader in code | `plausibility_checker.py` was intended to read it (per design docs) but doesn't; Chain D `safety_checker` also intended but unimplemented | Add manual curation workflow OR wire AG10 adverse_event + promotion_monitor to generate constraint proposals. **Also wire `plausibility_checker.py` to read it (currently bypassed).** |
| 🔴 | `literary_mechanistic_priors_v1` has no automated producer | P4 prior_selector (reads it) | Add manual curation workflow OR build prior extraction from mechanism annotation accumulation |
| 🟡 | Qualitative annotations not consumed by compilers | Dose-response, temporal, psychometric compilers | Add annotation query step in each compiler to use qualitative observations as constraints/priors |
| 🟡 | Adherence model has no consumer module | `adherence_data` annotations float with no downstream | Build `adherence_model.py` or wire to Chain D burden/adherence scoring |
| 🟡 | APS annotation weight boost not verified | Feedback loop (H1) from annotations → acquisition_queue | Verify/implement annotation-sourced APS weight in `aps_scorer.py` |
| 🟡 | `outcome_anchors_v1` has no compiler/producer | Presentation layer severity classification | Add manual curation or build anchor calibration from normative data |
| 🟢 | Triangulation tables unused | Chain C fusion (future) | Deferred to v2.0 |
| 🟢 | Population archetypes + complexity scaling unused | Offline analytics (future) | Deferred to v2.0 |

---

## Corrections from Original v1.0 Document

| Issue | v1.0 Had | Actual |
|-------|----------|--------|
| **Fake table names** | `paper_metadata_v1`, `study_design_v1`, `cohort_v1`, `outcomes_v1`, `stats_labels_v1`, `exposure_v1`, `mediator_v1`, `reconciled_evidence_v1` as agent write targets | Agents write `SpanLabel[]` + `RawAnnotationEmission[]` (in-memory). Persistence goes through TB → evidence_writer → `edge_evidence_v1`, or family_importers → B10–B14 |
| **Missing extraction phases** | No P2, P3, P4, P4b, P5, P6, P7 detail | Full pipeline: P0→P1→TB→P2→P3→P4→P4b→P5→P6→P7 |
| **Missing algorithm chains** | Single "Bayesian causal engine" box | 6 chains: A (Graph), B (Evidence), C (Posterior), D (Simulation), E (Temporal), F (Analytics) |
| **Missing Class A tables** | Only referenced ~5 tables | 34 Class A tables exist (see full inventory above) |
| **Module naming mismatch** | `crci_core/`, `crci_acq/`, `crci_extract/`, `crci_harmonize/`, `crci_calibration/` etc. | Actual: `crci/retrieval/`, `crci/extraction/`, `crci/algorithm/`, `crci/runtime/`, `crci/presentation/`, `crci/shared/` |
| **Missing feedback wiring** | Vague "validation/discrepancy analysis" | P5 chain_validator with specific discrepancy taxonomy + SE inflation feedback |
| **Agent count** | 9 agents + AG10 (proposed) | 11 agents implemented: AG01–AG11 (AG10 = Strategic Intel, AG11 = Instrument Validation) |
| **Missing QA infrastructure** | Not mentioned | `edge_evidence_quarantine_v1`, `evidence_validation_quarantine_v1`, `review_tasks`, `extraction_completeness_v1` |

---

_Generated 2026-02-27. Based on actual codebase audit of `crci/database/schema/*.sql`, `crci/extraction/**/*.py`, `crci/algorithm/**/*.py`, `crci/runtime/*.py`, `crci/retrieval/*.py`, `crci/presentation/*.py`._

_**Audited 2026-02-27.** Corrections applied: (1) Semantic Scholar→OpenAlex/Europe PMC in 3 places, (2) fulltext retriever fallback chain corrected to Europe PMC→Unpaywall→abstract-only, (3) P7 psychometric_compiler write target corrected to `instrument_definitions_v1` only (not `observation_noise_v1`), (4) P7 prior_compiler write target corrected to context-matched priors (not `node_priors_v1`/`normalization_refs_v1`), (5) `literary_constraints_v1` status corrected to fully dormant (no code reads or writes), (6) `predictor_alignment_rules_v1` and `outcome_anchors_v1` corrected to fully dormant, (7) H1 feedback loop downgraded from "Partial" to "Dead-wired", (8) Added Section I (Presentation Layer — 14 modules), (9) Schema file inventory corrected to 85 tables across 15 files (added 5 missing ALTER-only migration files), (10) `pathway_evidence_auditor.py` confirmed orphaned._
