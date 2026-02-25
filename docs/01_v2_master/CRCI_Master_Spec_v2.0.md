# CRCI — Extraction System Master Specification v2.0

**Version 2.0 — February 2026**
**Status: AUTHORITATIVE — Supersedes all prior extraction documents**

This document is the single authoritative specification for the CRCI extraction system. It consolidates, de-duplicates, and extends content from seven prior documents. In any conflict with a prior document, this document governs.

**Companion documents** (content split to eliminate duplication):

- **Engineering Appendix v2.0:** Module manifest, box→module mapping, file paths, per-module test specifications, cross-cutting invariants.
- **Implementation Playbook v2.0:** Prompt sequences, coding order, CLI scripts, budget controls, rate limits, API adapter endpoint details.
- **Checklists and Templates v2.0:** Manual CSV templates, meta.json schemas, operational checklists (meta-analysis extraction, acquisition batch, extraction batch, verification spot-check).

---

## 1. System Boundary and Purpose

### 1.1 Purpose

The extraction system transforms published research literature into algorithm-ready parameter tables. It accepts PDF documents as input and produces seven families of structured, validated, uncertainty-quantified parameters as output, plus a strategic intelligence layer.

### 1.2 Operational Boundary

The system operates at BUILD TIME, not patient time. It runs once per evidence cycle (when new literature is acquired) and writes to database tables that the runtime algorithm reads. No part of the extraction system executes during patient interaction.

The system is self-contained. Given prerequisite tables (§3.2), it operates independently of the algorithm, runtime, and presentation subsystems.

### 1.3 What the System Does Not Do

The system does not perform Bayesian updating on patient data, generate intervention recommendations, interact with patients or clinicians, perform causal inference (propagation, counterfactual estimation), or determine DAG structure (but can propose changes via annotation promotion, requiring human approval).

### 1.4 Known Limitations and First-Run Expectations

These limitations are inherent to the system design and cannot be eliminated by implementation quality alone.

**L-01 — Paywall coverage gap.** Automated retrieval reaches only open-access and PubMed Central full-text. Estimated 30–50% of high-APS papers will require manual acquisition (§9.6). First-run coverage will be incomplete until a researcher processes the acquisition report.

**L-02 — Abstract-only extraction quality.** Papers processed in SHALLOW mode (abstract + title only) yield m_design = 3.0× SE inflation and are missing instrument detail, temporal resolution, and subgroup data. Expect 15–25% of first-cycle papers to be abstract-only.

**L-03 — LLM extraction error rate.** Specialist agents (§5.3) will produce extraction errors. Expected per-field accuracy: 92–97% for numeric values, 85–93% for categoricals, 78–88% for free-text spans. The verification architecture (§8.3) catches high-impact errors; low-impact errors are attenuated by IVW pooling but not eliminated. Accuracy improves with calibration across runs.

**L-04 — Search recall ceiling.** Automated keyword + citation-chain search will miss relevant studies that use non-standard terminology or appear in journals outside PubMed/Crossref indexing. Estimated recall: 60–75% of existing evidence in first cycle, approaching 85–90% after 3+ cycles with gap-filling.

**L-05 — First-run noise.** Initial parameter estimates will have wider confidence intervals due to small k (contributing studies per edge). For edges with k < 5, prior_dominance uncertainty will be flagged. This is expected and is reduced by each acquisition cycle, not by tuning.

**L-06 — Temporal parameter sparsity.** Fewer than 20% of oncology RCTs report ≥3 longitudinal timepoints. Temporal kernel parameters (F4) will be poorly constrained for most edges until dedicated longitudinal search saturates. Expect TEMPORAL uncertainty classification for >60% of edges initially.

**L-07 — Biomarker correlation data scarcity.** Inter-biomarker correlation matrices are rarely reported in intervention RCTs. Workstream 7 depends heavily on observational cohort literature accessed via citation-chain expansion. First-cycle yield for F7 will be sparse.

**L-08 — Table parsing fragility.** PDF table extraction relies on heuristic and ML-based parsers. Complex multi-level headers, merged cells, and landscape-oriented tables will produce parsing failures at an estimated 10–20% rate. Fallback is LLM re-extraction from raw text spans.

### 1.5 How Extraction Quality Affects Patient Predictions

Each extraction design decision connects to a specific runtime accuracy mechanism. This tracing exists so implementers understand why precision matters at each stage.

**Mechanism 1 — Edge weight accuracy → intervention recommendation quality.** F1 (edge weights) feeds Bayesian belief propagation across the DAG. A 0.1 SD error in a single edge weight shifts the posterior for all downstream nodes by 0.1 × path_coefficient. For a node with 3 incoming edges, combined error can shift intervention ranking. IVW pooling attenuates random error by 1/√k but does not correct systematic extraction bias (e.g., consistent misreading of effect signs, within-group d classified as between-group).

**Mechanism 2 — Measurement model accuracy → patient score validity.** F2 (instrument psychometrics) feeds the latent variable measurement model, converting raw questionnaire scores → latent factor estimates. If extracted α = 0.85 but true α = 0.70, the measurement model under-corrects for attenuation, producing biased latent scores for every patient assessed with that instrument. No pooling protection — F2 values are used directly, not averaged.

**Mechanism 3 — Population prior accuracy → baseline estimate quality.** F3 (population norms / context priors) feeds prior distributions in Bayesian updating. Incorrect priors dominate posterior estimates for patients with sparse personal data (first visit). A mean shift of 0.5 SD in a prior produces biased estimates until ≥3 personal observations accumulate. Context matching (cancer_type, treatment_phase) reduces transportability error.

**Mechanism 4 — Temporal parameter accuracy → trajectory prediction.** F4 (temporal dynamics: onset, decay, recovery) feeds the time-varying kernel in the longitudinal model. Poorly constrained temporal kernels produce inaccurate between-visit predictions. If onset_weeks is estimated at 4 but true onset is 8, the model predicts improvement too early, potentially triggering premature intervention changes.

**Mechanism 5 — Uncertainty calibration → recommendation confidence.** SE calibration factors, precision cascade levels, and GRADE scores feed posterior variance → confidence intervals → recommendation strength classification. Under-inflated SE → over-confident recommendations. Over-inflated SE → under-confident recommendations. The 7-layer SE calibration (§7.2) is the primary defense.

---

## 2. Inputs and Outputs

### 2.1 Inputs

**Primary:** PDF files of published research literature, acquired via automated search or manual upload.

**Manual structured uploads:** CSV files conforming to six workstream templates, JSON override files, DOI-list files (one DOI per line). See Checklists and Templates companion document for template specifications.

**Prerequisite tables (three tiers):**

**Tier 1 — Required (extraction fails without these):**
- **biomarker_node_definitions_v1** (63 rows): Defines biological/psychological constructs. Without this: ConceptEngine cannot ground terms, agents cannot map effects to edges, system has no target structure.
- **edge_relations_definitions_v1** (129 rows): Defines causal/associational/mechanistic edges between nodes. Without this: extracted effect sizes cannot be assigned to edges, aggregation has no grouping targets.
- **instrument_definitions_v1** (63 rows): Defines assessment instruments with scoring direction, item count, score ranges, reliability, node mappings. Without this: agents cannot recognize instruments, trust boundary cannot validate scores.

**Tier 2 — Strongly recommended (major capability loss without):**
- **sd_anchors_v1:** Provides borrowed SDs for precision cascade Level 5. Without this: papers lacking SDs produce qualitative-only records excluded from IVW pooling (~30–40% of observational papers). Derivable: SD ≈ score_range / 6 for normally distributed measures.
- **node_search_terms_v1:** Maps each node to PubMed-compatible synonyms (3–8 terms/node, ~200–500 rows). Without this: automated acquisition non-functional. Derivable from node descriptions and example_instruments fields.

**Tier 3 — Enhancing (degraded mode without):**
- pathway_map_v1 (23 rows): Groups edges into named pathways.
- measure_definitions_v1 (82 rows): Subscale decomposition, MCID values.
- observation_noise_v1: Instrument measurement error parameters. Computable: noise_var = pop_var × (1 − α).
- normalization_refs_v1: Reference population means/SDs for z-scoring.
- harmonization_rules_v1: Scope matching rules.
- feedback_loops_v1 (5–6 rows): Feedback loops for stability. Derivable from edge registry feedback flags.

### 2.2 Outputs

**Seven parameter families** (see §3.2 for pipeline overview):

| # | Family | Scale | Aggregation Method | Output Table |
|---|--------|-------|--------------------|--------------|
| F1 | Edge Weights | SMD (SD units) or log-ratio | IVW random-effects meta-analysis + 7-layer SE calibration | edges_v1 (118 rows) |
| F2 | Instrument Psychometrics | Cronbach's α, factor loadings | Sample-size-weighted mean per instrument per population | instruments_v1 (23 rows) |
| F3 | Population Norms and Context Priors | Raw scores or z-scores | Sample-size-weighted mean of means, pooled SD, 4-level fallback hierarchy | context_matched_priors_v1 (variable) |
| F4 | Temporal Dynamics | Weeks (onset/peak), dimensionless (decay) | NLLS fit of stretched exponential model | intervention_kernels_v1, recovery_params_v1 |
| F5 | Dose-Response Parameters | Emax (SD units), EC50 (dose units), Hill coefficient | NLLS fit of Emax/Hill model with AIC comparison | dose_response_params_v1 |
| F6 | Subgroup Modifiers | Multiplicative (0.7–1.5 clamp) | IVW pooling of interaction terms | modifier_registry_v1 (109 rules) |
| F7 | Intervention Synergy | Interaction coefficient (SD units) | Extracted from factorial RCTs, calibrated vs Jaccard Overlap | synergy_registry_v1 (15 records) |

**Algorithm consumers:** F1 → ALG-A (graph assembly), ALG-B (evidence pooling). F2 → ALG-A5b (proxy registration), ALG-C2 (observation noise). F3 → ALG-C1 (context matching), ALG-C2 (Bayesian prior construction). F4 → ALG-E (temporal trajectory prediction). F5 → ALG-D5 (dose optimization). F6 → ALG-C4a (modifier matching). F7 → ALG-D5b (synergy-corrected bundle scoring).

**Strategic intelligence layer:** study_annotations_v1 — 22 annotation categories across 5 groups, routed to specific downstream consumers. See §8.1.

**Provenance and audit:** extraction_runs, triage_records_v1, provenance chains on every numeric value.

---

## 3. End-to-End Pipeline Overview

### 3.1 Stage Table (Single Canonical Representation)

Every paper passes through the same initial sequence, then branches into family-specific compilation pathways. This is the one authoritative description of the pipeline flow.

```
  PDF / DOI
      │
  ┌───▼────┐
  │ EX-ACQ │  Acquisition: find, score, retrieve papers
  └───┬────┘
      │
  ┌───▼───────┐
  │ EX-INGEST │  Ingestion: PDF/XML → canonical_text + quality flags
  └───┬───────┘
      │
  ┌───▼────┐
  │ EX-P0  │  Triage: relevance, classification, component inventory
  └───┬────┘
      │
  ┌───▼────┐
  │ EX-P1  │  Hybrid Multi-Agent Extraction (§5)
  └───┬────┘
      │
  ┌───▼────┐
  │ EX-TB  │  Trust Boundary: deterministic numeric parsing (§6)
  └───┬────┘
      │
  ┌───▼────┐
  │ EX-P2  │  Harmonization: 7 substages (§7.1)
  └───┬────┘
      │
  ┌───▼────┐
  │ EX-P3  │  Seven-Layer SE Calibration (§7.2)
  └───┬────┘
      │
  ┌───▼────────────────────────────────────────────┐
  │ DIVERGENCE: Family-Specific Compilation         │
  │  F1 → EX-P4 IVW Aggregation → edges_v1         │
  │  F2 → C1 Psychometric Compiler → instruments_v1 │
  │  F3 → C2 Norms Compiler → context_priors_v1     │
  │  F4 → C3 Temporal Compiler → kernels_v1          │
  │  F5 → C4 Dose-Response Compiler → dose_resp_v1   │
  │  F6 → C5 Modifier Compiler → modifier_reg_v1     │
  │  F7 → C6 Synergy Compiler → synergy_reg_v1       │
  └───┬────────────────────────────────────────────┘
      │
  ┌───▼────┐
  │ EX-P5  │  Sufficiency Assessment + Gap Analysis
  └───┬────┘
      │
      └──→ Loop back to EX-ACQ (acquisition feedback)
```

### 3.2 Stage Specifications

**EX-ACQ — Acquisition.** Input: evidence gap queries from EX-P5, scored candidates from reference mining, manually deposited PDFs. Output: PDF/XML files in retrieval cache, metadata in acquisition_queue_v1. Includes candidate deduplication: DOI exact-match (primary) and title Jaccard similarity ≥ 0.85 (fallback for DOI-less preprints). PubMed adapter must capture PMID (which stock paperscraper drops from pymed output) and MeSH terms. IDResolver (NCBI ID Converter API) enriches each candidate with DOI ↔ PMID ↔ PMCID cross-references. Fully specified in §9.

**EX-INGEST — PDF/XML Ingestion.** Input: downloaded file (PDF or XML) from EX-ACQ. This step converts raw file bytes into parseable text. paperscraper downloads files but never opens them — EX-INGEST bridges that gap.

- *PDF processing (pdfplumber):* Extract text page-by-page. Detect tables (line/cell extraction). Detect figures (embedded images). Assess quality: GOOD (>500 chars extracted, coherent text), DEGRADED (text extracted but sparse/garbled), SCAN (no text extracted — route to OCR), PARSE_FAILURE (pdfplumber exception).
- *XML processing (BioC-PMC / JATS):* Parse structured XML. Extract section elements (abstract, methods, results, discussion). Detect table-wrap and fig elements. Quality is typically GOOD for structured XML.
- *Persist outputs:* Write canonical_text as sidecar `.txt` file alongside source. Write paperscraper's sidecar `.json` metadata (title, authors, abstract). Update study_registry_v1 with pdf_path, canonical_text_path, file_type, parse_quality. See §10.1 for file storage architecture.
- *Gate:* canonical_text length > 0 and parse_quality ≠ PARSE_FAILURE → proceed to EX-P0. SCAN → route to OCR pipeline then re-assess. PARSE_FAILURE → log, flag for manual review.

**EX-P0 — Triage and Classification.** Input: canonical_text from EX-INGEST + metadata.

- *S1 — PDF Ingestion (deterministic, no LLM):* pdfplumber or pymupdf. Table detection via line/cell extraction. Paragraph and section header preservation. Character density assessment. Scanned PDFs → OCR pipeline, flagged DEGRADED. Encrypted PDFs → REJECTED.
- *S2 — Relevance Screening:* 5 inclusion criteria (cancer population, cognitive outcome or biological mechanism, original data, human subjects, peer-reviewed venue). 3 exclusion criteria (duplicate DOI, retracted publication, N < 10). Scoring: ≥0.8 → INCLUDE; 0.5–0.8 → HUMAN_REVIEW; <0.5 → EXCLUDE. LLM only for ambiguous cases in 0.5–0.8 range.
- *S3 — Two-Level Classification:* Level 1: study_subtype assignment (§4.1 taxonomy). Level 2: component_inventory detection (§4.2). Both feed Agent Activation Planner.
- *S4 — Route Decision:* INCLUDE → EX-P1. HUMAN_REVIEW → queue. EXCLUDE → log and stop.
- *Output:* PaperMap, ComponentInventory, route decision, execution mode, agent activation list. Writes to triage_records_v1, study_registry_v1.

**EX-P1 — Hybrid Multi-Agent Extraction.** Parallel extraction over shared PaperMap. Produces numeric SpanLabels and strategic annotations. Fully specified in §5.

**EX-TB — Trust Boundary.** Deterministic numeric parsing. No LLM past this point for any numeric value. Fully specified in §6.

**EX-P2 — Harmonization.** Seven substages: plausibility, conversion appropriateness, scale harmonization, orientation alignment, identification status, scope matching, composability. Fully specified in §7.1.

**EX-P3 — Seven-Layer SE Calibration.** Seven multiplicative layers applied to each record's SE. Fully specified in §7.2.

**EX-P4 — Family 1 IVW Aggregation.** Evidence grouping → double-counting resolution → IVW pooling under random effects → publication bias assessment. Fully specified in §7.3.

**C1–C6 — Family 2–7 Compilers.** Each compiler uses family-specific aggregation logic. Fully specified in §7.4.

**EX-P5 — Sufficiency Assessment and Gap Analysis.** Evaluates all seven families together, grades each edge A–F, generates acquisition queries for gaps. Fully specified in §7.5.


---

## 4. Paper Routing and Extraction Mode

### 4.1 Study Subtype Taxonomy (27 Types)

Every paper receives two independent classifications:

- **Level 1 — study_subtype:** Determines execution mode and extraction depth.
- **Level 2 — component_inventory:** Determines extraction breadth.

These are independent. A paper's subtype does not limit which components are extracted. An RCT can yield psychometric data. A validation study can yield edge evidence.

| study_design | study_subtype | Mode | Products / Notes |
|---|---|---|---|
| meta | pairwise_ma | DEEP | 4 products (§7.6) |
| meta | nma | DEEP | 5 products (§7.6) |
| meta | ipdma | DEEP | 6 products (§7.6) |
| meta | dose_response_ma | DEEP | 5 products (§7.6) |
| meta | umbrella_review | SHALLOW | ALL NUMERIC EXTRACTION BLOCKED (§7.6) |
| meta | mega_analysis | DEEP | 4 products |
| other | systematic_review | SHALLOW | Reference mining + vote count only |
| other | scoping_review | SHALLOW | Reference mining + ontology mapping |
| other | narrative_review | MINIMAL | Reference mining only |
| other | practice_guideline | SHALLOW | Graded recommendations + cited evidence |
| RCT | standard_rct | DEEP | All agents |
| RCT | factorial_rct | DEEP | All agents + synergy interaction terms |
| RCT | pilot_rct | STANDARD | Quality capped at moderate (N < 50) |
| RCT | crossover_rct | STANDARD | + period-effect check required |
| longitudinal | prospective_cohort | STANDARD | |
| longitudinal | retrospective_cohort | STANDARD | identification capped at partially_ident |
| cross_sect | cross_sectional | STANDARD | identification = not_identified |
| intensive | ema_eld | STANDARD | ≥3 assessments/day + alignment metadata |
| mechanistic | animal_model | STANDARD | Translation penalty, species required |
| mechanistic | in_vitro | MINIMAL | Sign-direction only |
| mechanistic | computational_model | SHALLOW | Parameter extraction only |
| other | case_report | MINIMAL | Ontology only, NO evidence rows |
| other | qualitative | MINIMAL | Ontology only, NO evidence rows |
| other | methods_paper | SHALLOW | Instrument/method extraction |
| other | psychometric_validation | STANDARD | AG11 primary, reliability + validity |
| other | normative_cohort | STANDARD | AG03-EXT primary, baseline norms |
| other | dose_response_study | STANDARD | AG06-EXT primary |
| other | longitudinal_followup | STANDARD | AG08-EXT primary |

### 4.2 Execution Modes

| Mode | Agents Activated | LLM Calls | Tokens/Paper |
|---|---|---|---|
| DEEP | AG01–AG10 + extensions + ConceptEngine | 11–15 | 40,000–70,000 |
| STANDARD | AG01–AG10 | 8–9 | 25,000–40,000 |
| SHALLOW | AG01 + AG02 + AG05 + AG09 | 3 | 8,000–15,000 |
| MINIMAL | AG01 only + reference scan | 1 | 3,000–5,000 |

### 4.3 Component Inventory

The component inventory detects what information types are present in the paper REGARDLESS of study subtype. Two groups:

**Parameter-yielding (activate extraction agent extensions):**
EDGE_EVIDENCE, INSTRUMENT_PSYCHOMETRICS, BASELINE_COHORT_DATA, TEMPORAL_TRAJECTORY, DOSE_RESPONSE, NORMATIVE_DATA, CORRELATION_MATRIX, SUBGROUP_ANALYSIS, META_ANALYTIC_DATA.

**Intelligence-yielding (activate annotation extraction):**
AUTHOR_LIMITATIONS, UNMEASURED_CONFOUNDERS, MECHANISM_HYPOTHESES, RESEARCH_GAPS, ADHERENCE_DATA, ADVERSE_EVENTS, TEMPORAL_OBSERVATIONS, DOSE_OBSERVATIONS, REPLICATION_STATUS.

**Routing rule:** execution_mode is determined by study_subtype. Agent extensions are activated by component_inventory detections with confidence ≥ MEDIUM.

**Detection method:** Component inventory runs during EX-P0-S3. One LLM call inspects the PaperMap for structural signals (has_tables, section types, candidate spans) and classifies components as HIGH (explicitly present), MEDIUM (mentioned but not primary focus), or LOW (might be inferrable).

### 4.4 Paper-Type Routing Decision Tree

```
PAPER ARRIVES
│
├─ Has quantitative pooling across multiple studies?
│   ├─ YES → study_design = 'meta'
│   │   ├─ Compares >2 interventions in network? → nma
│   │   ├─ Uses individual patient data? → ipdma
│   │   ├─ Models dose-response curve? → dose_response_ma
│   │   ├─ Meta-analysis of meta-analyses? → umbrella_review
│   │   └─ Standard pairwise comparison? → pairwise_ma
│   └─ NO → Structured review?
│       ├─ Systematic search + PRISMA? → systematic_review
│       ├─ Scoping review? → scoping_review
│       ├─ Clinical practice guideline? → practice_guideline
│       └─ Narrative review? → narrative_review
│
├─ Primary empirical study?
│   ├─ Random assignment?
│   │   ├─ Factorial design? → factorial_rct
│   │   ├─ Crossover design? → crossover_rct
│   │   ├─ N < 50 or "pilot/feasibility"? → pilot_rct
│   │   └─ Standard parallel? → standard_rct
│   ├─ Multiple timepoints?
│   │   ├─ EMA (≥3 assessments/day)? → ema_eld
│   │   ├─ Prospective enrollment? → prospective_cohort
│   │   └─ Retrospective/registry? → retrospective_cohort
│   ├─ Single timepoint? → cross_sectional
│   └─ Preclinical?
│       ├─ Animal model? → animal_model
│       ├─ Cell culture? → in_vitro
│       └─ Computational? → computational_model
│
└─ Other?
    ├─ Case report (N < 10)? → case_report
    ├─ Qualitative? → qualitative
    ├─ Psychometric validation? → psychometric_validation
    └─ Methods paper? → methods_paper
```

### 4.5 Per-Subtype Agent Activation and Target Families

This table is the definitive routing rule consumed by activation_planner.py.

| study_subtype | Mode | Agents Activated | Target Families |
|---|---|---|---|
| standard_rct | STD | AG01–AG10 | F1, F3, F4, F6 |
| pilot_rct | STD | AG01–AG10 | F1 (with m_design inflation), F3 |
| crossover_rct | STD | AG01–AG10 | F1 (crossover SE adjust), F3, F4 |
| factorial_rct | DEEP | AG01–AG10 + AG06-EXT | F1, F5, F6, F7 |
| pairwise_ma | DEEP | AG01, AG02, AG05, AG10 | F1, F6 |
| nma | DEEP | AG01, AG02, AG05, AG10 | F1, F6 |
| ipdma | DEEP | AG01, AG02, AG05, AG10 | F1, F6, F7 |
| dose_response_ma | DEEP | AG01, AG02, AG05, AG06, AG10 | F1, F5 |
| umbrella_review | MIN | AG01, AG10 (ref mining only) | NONE (numeric blocked) |
| systematic_review | SHAL | AG01, AG10 | NONE (ref mining) |
| prospective_cohort | STD | AG01–AG10 | F1, F3, F4, F6 |
| retrospective_cohort | STD | AG01–AG08, AG10 | F1, F3 |
| cross_sectional | STD | AG01–AG05, AG07, AG10 | F1, F3 |
| ema_eld | DEEP | AG01–AG10 + AG08-EXT | F1, F4 |
| psychometric_validation | STD | AG01, AG02, AG11 | F2 |
| case_report | SHAL | AG01, AG03, AG10 | NONE (intel only) |
| qualitative | MIN | AG01, AG10 | NONE (intel only) |
| animal_model | SHAL | AG01, AG07, AG10 | NONE (intel only) |
| in_vitro | MIN | AG01, AG07 | NONE (intel only) |
| narrative_review | SHAL | AG01, AG10 | NONE (ref mining) |
| practice_guideline | MIN | AG01, AG10 | NONE (intel only) |
| methods_paper | MIN | AG01 | NONE |
| computational_model | SHAL | AG01, AG07, AG10 | NONE (intel only) |
| scoping_review | SHAL | AG01, AG10 | NONE (ref mining) |

**Conditional agent extensions:**
- **AG03-EXT** (adverse event detail): Activated when AG03 detects AE mention AND paper is RCT/cohort with N ≥ 50.
- **AG05-EXT** (subgroup stats): Activated when component_inventory contains subgroup_analysis AND paper is RCT/MA.
- **AG06-EXT** (dose detail): Activated when component_inventory contains dose_response_data AND paper is factorial_rct or dose_response_ma.
- **AG08-EXT** (temporal trajectory): Activated when paper has ≥3 timepoints AND paper is RCT/cohort/EMA.
- **AG11** (instrument validation): Activated when component_inventory contains psychometric_data, regardless of subtype.


---

## 5. EX-P1 v2: Canonical Reader + Parallel Agents

### 5.1 Architecture Rationale

The system uses a HYBRID architecture: one canonical reader builds a shared paper map, multiple specialist agents extract from targeted sections, one reconciliation layer resolves conflicts.

This architecture was selected because the system must capture 22+ content dimensions per paper, dimensions differ in section location and linguistic form, a single-agent approach consistently under-captures rare dimensions (null context, diagnostics, psychometric caveats), and full-independence (every agent reads entire paper) costs 3–5× more in tokens with worse coordination.

### 5.2 Layer A: Canonical Reader

**Module:** crci_extract/reader.py + crci_extract/paper_map.py

The Canonical Reader reads the paper EXACTLY ONCE and produces an IMMUTABLE PaperMap. No agent modifies it. All agents read from it.

**Step A1 — Section Segmentation.** Method: regex patterns for standard headings as primary signal. LLM classification fallback only when headings absent or ambiguous. Escape-hatch rate monitor: if LLM fallback >15% of batch, expand regex library rather than relying on LLM. Output per section: section_type (ENUM: abstract, introduction, methods, results, discussion, limitations, conclusion, supplement, references, acknowledgments, appendix, unknown), start_offset, end_offset, heading_text, confidence.

**Step A2 — Table and Figure Registry.** Method: DETERMINISTIC. pdfplumber line detection + cell extraction. Caption extraction via positional proximity. Output per table/figure: type (ENUM: table, figure, supplementary_table, supplementary_figure), label, caption, content (structured rows for tables, NULL for figures), text_mentions (list of character offsets where referenced in body), page_number.

**Step A3 — Candidate Span Identification.** Method: DETERMINISTIC. Three detection methods:
- *Regex:* numeric patterns (p < 0.05, d = 0.XX, 95% CI, OR = X.XX, α = 0.XX, r = 0.XX, F(df1,df2) = X.XX).
- *Keyword proximity:* "limitation", "however", "future research", "adverse", "adherence", "dropout", "did not differ", "no significant", "mediating", "moderating".
- *Structural:* Table 1 rows (typically baseline data).

Output per span: span_id (SPAN_{paper_id}_{NNN}), start_offset, end_offset, section_id, span_type (ENUM: numeric_result, limitation_statement, mechanism_claim, temporal_marker, instrument_mention, statistical_test, sample_description, effect_direction, dose_mention, adherence_mention, adverse_event_mention, null_finding, research_gap_statement), text (50–300 characters), detection_method. This step identifies regions of interest; it does not interpret them.

**Step A4 — Basic Study Object.** Method: HYBRID. Keyword matching + section scanning primary. LLM fallback for ambiguous cases only. Output: probable_design, probable_n, probable_interventions, probable_outcomes, probable_timepoints, probable_cancer_type, has_tables, has_biomarker_outcomes, has_multiple_timepoints, has_dose_arms.

**Combined output — PaperMap:** sections[], tables_figures[], candidate_spans[], basic_study, full_text (for escape-hatch access), paper_id, parse_quality (ENUM: high, medium, degraded).

LLM cost: 0–1 calls per paper for the Canonical Reader.

### 5.3 Layer B: Specialist Agents with Section Targeting

Each agent receives a TARGETED CONTEXT derived from the PaperMap. Agents read only their assigned sections plus relevant candidate spans.

| Agent | Label | Sections Read | Primary Extraction Targets | LLM Calls | Runs In |
|---|---|---|---|---|---|
| AG01 | MetadataAgent | abstract, references, acknowledgments | Title, DOI, authors, funding, trial registration | 1 | ALL |
| AG02 | DesignAgent | methods, abstract + spans: sample_description, statistical_test | Study design, randomization, blinding, control type. ANNOTATIONS: limitation_design, model_diagnostic | 1 | ALL |
| AG03 | CohortAgent | methods, results Table 1 + spans: sample_description | Sample size, demographics, cancer type, treatment phase. ANNOTATIONS: limit_generalizability, adherence_data | 1 | STD/DEEP |
| AG03-X | CohortAgent Extension | results tables (Table 1) | Per-node cognitive means/SDs linked to instruments + subgroups → context_matched_priors pipeline | +1 | IF BASELINE_COHORT |
| AG04 | OutcomeAgent | methods, results + spans: instrument_mention | Outcome measures, instruments, measurement timepoints. ANNOTATIONS: instrument_observation, temporal_trajectory | 1 | STD/DEEP |
| AG05 | StatsLabelAgent | results, results tables + spans: numeric_result, statistical_test, null_finding | SpanLabels with 40+ label types: mean, SD, SE, CI, p, N, d, OR, HR, RR, F, η², r, χ². ANNOTATIONS: null_finding_context. CRITICAL: SpanLabel objects with char offsets ONLY. No parsed floats. | 1–2 | ALL |
| AG05-X | StatsLabel Extension | results subgroup tables | Interaction effects, subgroup-specific effect sizes + N | +1 | IF SUBGROUP |
| AG06 | ExposureAgent | methods (protocol), results + spans: dose_mention | Dose, duration, adherence. ANNOTATIONS: dose_response_qual | 1 | STD/DEEP |
| AG06-X | Exposure Extension | results (dose-arm data) | Structured dose × effect pairs → dose_response_params pipeline | +1 | IF DOSE_RSP |
| AG07 | MediatorAgent | introduction, discussion, biomarker results + spans: mechanism_claim | Biomarker pathways, mechanistic claims. ANNOTATIONS: mechanism_hypothesis, mechanism_detail_subnode | 1 | STD/DEEP |
| AG08 | TemporalAgent | methods (timepoints), results (by-timepoint) + spans: temporal_marker | Measurement timepoints, follow-up duration, temporal patterns. ANNOTATIONS: temporal_onset_decay | 1 | STD/DEEP |
| AG08-X | Temporal Extension | results (effect × time data) | Structured effect × timepoint arrays. Onset, peak, decay. → kernels + recovery pipeline | +1 | IF TEMPORAL |
| AG09 | ReconciliationAgent | DOES NOT READ PAPER. Reads AG01–AG08 outputs. RULE-BASED. NO LLM. | 7 deterministic consistency checks: (1) Duplicate SpanLabel detection, (2) CI bracketing, (3) p-value/CI consistency, (4) N consistency across agents, (5) Effect direction consistency, (6) Missing grouping detection, (7) Orphan span detection | 0 | ALL |
| AG10 | StrategicIntelAgent | discussion, limitations, conclusion + spans: limitation_stmt, mechanism_claim, research_gap_stmt, adverse_event_mention. Runs AFTER AG01–AG09 (has prior_agent_outputs) | Non-numeric intelligence ONLY. 7 primary annotation categories: research_gap, future_research, practical_recommendation, mechanism_hypothesis, limitation_unmeasured_confounder, limitation_design, limitation_generalizability | 1–2 | STD/DEEP |
| AG11 | InstrumentValidation | methods (instrument desc), results (reliability) + spans: instrument_mention, numeric_result | Cronbach's α, test-retest ICC, factor loadings, convergent/discriminant validity, SEM. Grouped by instrument × subscale × population. → instruments_v1 pipeline | 1 | IF INST_PSYCHO |

**Escape hatch:** Any agent can request raw text chunks beyond assigned sections. Each request is logged (agent_id, reason, chunk_requested). Per-batch escape rate >15% per agent → review that agent's section assignment.

**All agent outputs** are two types: (1) SpanLabels — character-offset-anchored numeric annotations, (2) RawAnnotations — strategic intelligence records (§8.1). Extensions (AG03-X, AG05-X, AG06-X, AG08-X, AG11) write to the same output targets as parent agents but add "EXT" provenance tags.

### 5.4 Two-Tier Extraction Strategy

**Tier 1 (default, all papers):** Each agent reads assigned sections once.

**Tier 2 (triggered re-read, ~20–30% of papers):** Adds 1–3 targeted LLM calls when specific high-risk content is detected in Tier 1.

| Trigger | Re-Read Agent | Sections Re-Read | Impact |
|---|---|---|---|
| Null finding, adequacy ambiguous (β ≈ 0, powered_adequately = UNKNOWN) | AG05 | Methods (sample size justification) + Results (CI width assessment) | Well-powered null shifts P_inclusion by −0.80 logits |
| Adverse event mention detected | AG03 | Results (AE table) + Methods (safety monitoring) | Feeds contraindication rules (safety-critical) |
| Strong mechanism hypothesis (evidence_strength = strong) | AG10 | Discussion (look for counter-evidence or qualifications) | Accumulates toward DAG expansion proposals |
| Temporal onset/decay mention | AG08 | Results (by-timepoint tables) for numeric data supporting the qualitative claim | Directly calibrates kernel parameters |
| Named unmeasured confounder | AG07 | Check if confounder measured in cited studies (via literature_comparison) | Inflates structural σ² unless resolved elsewhere |

### 5.5 Layer C: Reconciliation

Two reconciliation streams run after all agents complete.

**Stream 1 — SpanLabel Reconciliation (AG09, deterministic).** Seven checks as specified in the AG09 row above.

**Stream 2 — Annotation Reconciliation (EX-P1-REC).**

*Step R1 — Clustering:* Group raw annotations by (a) same category, (b) same target_entity_type + target_entity_id, (c) Jaccard similarity on content tokens > 0.60.

*Step R2 — Pairwise Comparison within each cluster:* AGREEMENT (compatible annotations → merge), CONTRADICTION (incompatible claims → severity classification: LOW = disagreement about degree, HIGH = disagreement about direction), SUBSUMPTION (one more specific → keep specific version).

*Step R3 — Merge Decision:*

| Cluster State | Action |
|---|---|
| All AGREE | Merge into one canonical annotation. confidence = min(1.0, 0.3 + 0.15×support_n + 0.2×mean_agent_confidence). cross_agent_support_n = count of agents. |
| SUBSUMPTION | Keep most specific as canonical. Link less specific via duplicate_of_ann_id. |
| CONTRADICTION LOW | Keep both, adjudication_status = conflict. Cap confidence at 0.50. |
| CONTRADICTION HIGH | Keep both, adjudication_status = human_review_required. Cap confidence at 0.50. |
| Singleton | Keep as-is, cross_agent_support_n = 1. confidence = agent_confidence × 0.8. |

*Step R4 — Annotation Trust Boundary (EX-P1-ATB):* 6 validation rules before persisting to study_annotations_v1: AT-01: Provenance required (extraction_snippet + span_id). AT-02: Separate explicit from inferred (evidence_strength field). AT-03: Category-specific required fields (adverse_event → severity required; null_finding_context → powered_adequately required; limitation_unmeasured_confounder → named confounder required). AT-04: Contradictions route to hold status. AT-05: High-impact annotations (structural_variance, DAG expansion, safety) → require human adjudication. AT-06: Speculative annotations cannot promote alone.

### 5.6 Execution Sequence

Phase 1: Canonical Reader (sequential) → PaperMap. Phase 2: Agent Activation Planning (deterministic) → AgentPlan. Phase 3: Parallel Agent Execution — AG01–AG08 + extensions run concurrently; AG09 runs after AG01–AG08 complete; AG10 runs after AG01–AG09 complete. Phase 4: Tier 2 Re-reads (conditional, sequential). Phase 5: SpanLabel Reconciliation (AG09, deterministic). Phase 6: Annotation Reconciliation (EX-P1-REC). Phase 7: ConceptEngine (DEEP mode only, hybrid rule+fuzzy). Phase 8: Completeness Report (missingness provenance codes).

**Agent failure handling:** Timeout (>60s) → skip agent, mark AGENT_MISS. No output → log, mark AGENT_MISS. Malformed output → attempt parse, mark unparseable as AGENT_MISS.

### 5.7 ConceptEngine (EX-P1-CE)

ConceptEngine resolves extracted text spans to canonical system entities. It ensures that agent outputs (free-text instrument names, biomarker mentions, node descriptions) are grounded to the ontology tables.

Input: All extracted spans with entity references from AG01–AG10.
Output: Grounded entity_id values (node_id, instrument_id, edge_relation_id, biomarker_id) appended to each span.

**Three-mode resolution:**

*Mode 1 — Exact Match (deterministic, always runs first):* Extracted string → lowercase + strip punctuation → exact lookup against canonical_names column in nodes_v1, instruments_v1, edges_v1, biomarkers_v1. Match → entity_id, confidence = 1.0. Expected resolution rate: 55–70% of spans.

*Mode 2 — Alias + Abbreviation Match (deterministic, runs on unresolved):* Extracted string → lookup against alias_registry_v1 (canonical_id, alias_string, alias_type: abbreviation | synonym | former_name | brand_name | informal). Match → entity_id, confidence = 0.95. Expected resolution rate: 15–25% of remaining spans.

*Mode 3 — Fuzzy Match (LLM-assisted, DEEP mode only, runs on still-unresolved):* Extracted string + surrounding context (±100 tokens) → LLM prompt with top 5 candidates by edit distance. LLM selects → entity_id, confidence = LLM-reported value. Confidence < 0.70 → UNRESOLVED, queued for human review. Expected resolution rate: 40–60% of remaining spans.

*Unresolved spans:* entity_id = NULL, grounding_status = UNRESOLVED, queued in concept_review_queue_v1. Do not block extraction. Cannot contribute to compilation until manually grounded.

### 5.8 Extended Extraction (EX-P2E, conditional)

Runs only when flagged by AG09 or triggered by DEEP mode.

**TriangulationExtractor:** Identifies edges measured by ≥2 methods within same paper (RCT + biomarker mediation + observational). Records both estimates + agreement score. Concordant triangulation (agreement < 1.5) → 0.8× SE reduction in ALG-B. Writes to triangulation_evidence_v1.

**PathwayLoadingExtractor:** Extracts biomarker-to-pathway loading factors from mediation or factor analysis. Writes to pathway_biomarkers_v1.

**OntologyLinker:** Maps extracted concepts to MeSH, SNOMED, and system node definitions. Writes to ontology_links_v1.


---

## 6. Trust Boundary and Numeric Firewall

Input: SpanLabel array from EX-P1. Rule: Deterministic numeric parsing. NO LLM permitted past this point for ANY numeric value.

### 6.1 Eleven Parse Rules

Convert character-offset annotations into typed numeric values using regex extraction and Python float parsing. Each rule handles one annotation label type: mean, SD, SE, CI_lower, CI_upper, p_value, N, effect_size, OR, HR, RR.

### 6.2 Precision Cascade (SE Derivation)

When a paper does not report SE directly, derive it through a 6-level fallback chain. Each level has an explicit inflation factor.

| Level | Derivation Method | Inflation | Quality Grade |
|---|---|---|---|
| L1 | SE directly reported | 1.00× | DIRECT |
| L2 | From 95% CI: SE = (upper − lower) / 3.92. From 99% CI: SE = (upper − lower) / 5.152 | 1.00× | DERIVED_EXACT |
| L3 | From p-value + effect: z = Φ⁻¹(1−p/2), SE = \|β\|/z. If p reported as "<0.05": use p=0.05 (conservative) | 1.05× (1.10× if p is bounded) | DERIVED_APPROXIMATE |
| L4 | From sample sizes + effect: SE ≈ √(1/n₁ + 1/n₂) for SMD | 1.15× (1.20× if unequal groups) | ESTIMATED_FROM_N |
| L5 | Borrowed SD from sd_anchors_v1 + N to derive SE. Tier 1: same population match (1.15×). Tier 2: same construct, different population (1.30×). Tier 3: general population (1.50×) | 1.15×–1.50× | SD_BORROWED |
| L6 | Direction only. Cannot compute SE. Record as QUALITATIVE_ONLY. Does NOT enter IVW pooling. Used only for sign-check. | N/A | QUALITATIVE |

Every record logs: derivation_level, inflation_factor, borrowed_source_id.

### 6.3 Effect Size Conversion Validity Matrix

11 rows for effect-size-to-SMD conversions. Each specifies "Valid When" conditions that are HARD GATES — conversion is blocked if unmet.

| Source Statistic | Target Scale | Valid When (HARD GATE) |
|---|---|---|
| Cohen's d | SMD (already) | Always valid |
| Hedges' g | SMD | Always valid (g ≈ d for N > 20) |
| Mean difference | SMD | Requires SD in BOTH groups |
| Pre-post change | SMD | Requires r_pre_post or assumed r=0.5 with 1.15× inflation |
| t-statistic | SMD | d = t × √(1/n₁ + 1/n₂) |
| F-statistic | SMD | REQUIRES df_num = 1, 2-group |
| Partial η² | SMD | REQUIRES df_num = 1 or simple 2-group |
| r (correlation) | SMD | d = 2r / √(1−r²) |
| χ² | SMD | REQUIRES df = 1 |
| OR (odds ratio) | log scale → SMD | d = ln(OR) × √3/π |
| HR (hazard ratio) | log scale | HR→OR BLOCKED unless event <10%. HR→d NEVER RECOMMENDED |

**Critical rules:** No chained conversions (e.g., r → OR → d is BLOCKED). All ratio measures pooled on log scale. Between-group d, within-group d, and pre-post d MUST be distinguished via effect_size_type field (BETWEEN_GROUP, WITHIN_GROUP, PRE_POST_CHANGE). Mixing types without distinction corrupts pooling.

### 6.4 Conversion Formula Reference

All formulas are implemented in crci_harmonize/conversions.py. No approximations beyond those stated. No LLM involvement.

**Mean difference → d:** d = (M_treatment − M_control) / SD_pooled. SD_pooled = √[((n₁−1)×SD₁² + (n₂−1)×SD₂²) / (n₁+n₂−2)].

**Hedges' g correction (applied to ALL d values):** g = d × (1 − 3/(4×(n₁+n₂−2) − 1)). SE_g = SE_d × (1 − 3/(4×(n₁+n₂−2) − 1)).

**Pre-post change score → d:** d = (M_change_tx − M_change_ctrl) / SD_pooled_change. SD_change = SD_pre × √(2×(1−r_pre_post)). If r_pre_post unreported: assume r = 0.50, apply m_inflation = 1.15×. If only within-group d available (no control comparison): effect_size_type = WITHIN_GROUP. Do NOT combine with BETWEEN_GROUP d in pooling.

**t-statistic → d:** d = t × √(1/n₁ + 1/n₂). SE_d = √(1/n₁ + 1/n₂ + d²/(2×(n₁+n₂))).

**F-statistic → d (REQUIRES df_numerator = 1):** d = √(F × (1/n₁ + 1/n₂)) for equal groups. d = √(F) × √(n₁+n₂)/(√(n₁×n₂)) for general case. HARD GATE: If df_numerator ≠ 1 → CONVERSION_BLOCKED.

**Partial η² → d (REQUIRES simple 2-group comparison):** d = 2 × √(η² / (1 − η²)). HARD GATE: If design has >2 groups or covariates beyond the one factor of interest → CONVERSION_BLOCKED.

**r (correlation) → d:** d = 2r / √(1 − r²). SE_d = 4 × SE_r / (1 − r²)^(3/2). SE_r = (1 − r²) / √(N − 1) for Fisher z-transformed r.

**χ² → d (REQUIRES df = 1):** d = 2 × √(χ² / N). HARD GATE: If df ≠ 1 → CONVERSION_BLOCKED.

**OR (odds ratio) → d:** d = ln(OR) × √3 / π. SE_d = SE_ln_OR × √3 / π. SE_ln_OR = √(1/a + 1/b + 1/c + 1/d) where a,b,c,d are the four 2×2 table cells. Pooling of ORs occurs on log scale. Convert to d only for cross-metric comparison, not for pooling.

**HR (hazard ratio):** HR → d: NEVER RECOMMENDED. Not implemented. HR → OR: BLOCKED unless event rate < 10%. HRs pooled on log scale as a separate metric. Do NOT mix with ORs or ds in the same IVW aggregation.

**SE derivation formulas (referenced by §6.2 precision cascade):** From 95% CI: SE = (CI_upper − CI_lower) / 3.92. From 99% CI: SE = (CI_upper − CI_lower) / 5.15. From p-value (two-sided): z = Φ⁻¹(1 − p/2), SE = |effect| / z, inflation 1.05×. From N only: SE ≈ 1 / √(N), inflation 1.15×. Borrowed SD: SE = SD_borrowed / √(N), inflation 1.15×–1.50×.

**Median/IQR → Mean/SD (Wan et al. 2014):** Case 1 ({min, Q1, median, Q3, max}): mean ≈ (min + 2×Q1 + 2×median + 2×Q3 + max) / 8; SD ≈ (max − min) / (4×Φ⁻¹((N−0.375)/(N+0.25))). Case 2 ({Q1, median, Q3} only): mean ≈ (Q1 + median + Q3) / 3; SD ≈ (Q3 − Q1) / (2×Φ⁻¹((0.75×N−0.125)/(N+0.25))). Case 3 ({min, median, max} only): mean ≈ (min + 2×median + max) / 4; SD ≈ (max − min) / (2×Φ⁻¹((N−0.375)/(N+0.25))).

**Fisher z transformation:** z = 0.5 × ln((1+r) / (1−r)). SE_z = 1 / √(N − 3). Back-transform: r = (e^(2z) − 1) / (e^(2z) + 1). All correlation pooling occurs in Fisher z space.

**Split-half → Cronbach's alpha (Spearman-Brown):** α = 2r_split / (1 + r_split).

### 6.5 Family-Specific Trust Boundary Extensions

**TB-PSYCH:** α ∈ (0, 1). Flag if α > 0.99 or < 0.50. Loadings ∈ (−1, 1). Split-half → α via Spearman-Brown: α = 2r/(1+r).

**TB-NORMS:** |z-score| < 4 vs known references. SD > 0. Median/IQR → mean/SD: mean ≈ (Q1+med+Q3)/3, SD ≈ IQR/1.35.

**TB-DOSE:** Dose > 0 (zero is control, not a dose). Check monotonicity.

**TB-TEMPORAL:** Normalize timepoints to weeks from baseline. months × 4.33, days / 7, cycles × cycle_weeks. |baseline effect| < 0.3 (flag if exceeded).

**TB-SUBGROUP:** Interaction sign consistency check.


---

## 7. Harmonization, Calibration, and Compilation

### 7.1 Harmonization (EX-P2): Seven Substages

**S1 — Plausibility:** |β| ≤ 5, SE > 0, CI_lower < β < CI_upper.

**S2 — Conversion Appropriateness:** Validity matrix preconditions (§6.3) met before any conversion proceeds.

**S3 — Scale Harmonization:** Convert to SD_SD or log-ratio scale. SD borrowing from sd_anchors_v1 when study SD unreported.

**S4 — Orientation Alignment:** Effect sign matches DAG convention. Confidence ≥ 0.60 → full effect. Below → magnitude-only.

**S5 — Identification Status:**

| Status | Score | Criteria |
|---|---|---|
| Identified | 1.00 | RCT with adequate randomization |
| Partially identified | 0.85 | Good adjustment strategy |
| Plausibly causal | 0.70 | Some adjustment but residual confounding |
| Not identified | 0.50 | Cross-sectional or unadjusted |

**S6 — Scope Matching:** Transportability score across five dimensions: cancer type (0.35) + treatment phase (0.25) + regimen (0.20) + age (0.10) + sex (0.10). Floor: 0.30.

**S7 — Composability:** Five tests verifying each record is compatible with the existing evidence pool for its target edge.

Output: Harmonized evidence records with classification flags. Writes to edge_evidence_v1.

### 7.2 Seven-Layer SE Calibration (EX-P3)

Seven multiplicative layers applied to each record's SE.

| Layer | What It Calibrates | Values |
|---|---|---|
| L1 | Study design | RCT: 1.0×. Prospective cohort: 1.15×. Retrospective: 1.25×. Cross-sectional: 1.40×. Abstract-only: 3.00× |
| L2 | Scope match weighting | w_scope from S6. Floor: 0.30 |
| L3 | Between-study heterogeneity | τ² via DerSimonian-Laird. I² = max(0, (Q−df)/Q). Prediction interval when k ≥ 3 |
| L4 | Cancer population validation (instruments) | Validated in cancer: 1.00×. General population only: 1.30× |
| L5 | GRADE quality | High: 1.00×. Moderate: 1.15×. Low: 1.30×. Very low: 1.60× |
| L6 | Measurement recency | For time-sensitive biomarkers: e^{−0.05×t_days}. >90 days: EXCLUDED |
| L7 | Publication freshness | Psychometrics: 0%/yr. Bio correlations/norms: 0.5%/yr. Mechanism/recovery: 1.0%/yr. Intervention efficacy: 1.5%/yr. Temporal kernels: 2.0%/yr. Floor: 0.70 |

**Final formula:** SE_eff = √[(SE × m_design × m_GRADE × m_temporal)² + σ²_struct + τ²] / (max(w_scope, 0.3) × w_fresh)

**Constraint:** SE_eff ≥ SE_raw. Uncertainty is never deflated.

### 7.3 Family 1 Compilation: IVW Aggregation (EX-P4)

**Stage 6a — Evidence Grouping (EX-P4-EG).** Group calibrated records by target edge. Partition into primary study records and meta-analysis-derived records using meta_source_flag.

**Stage 6b — Double-Counting Resolution (EX-P4-DCR).** Detect overlap between meta-analysis constituent lists and independently extracted primaries. Compute overlap_ratio = |primary_studies_in_registry ∩ MA_included| / |MA_included|.

| Overlap Ratio | Decision |
|---|---|
| 0.00 | USE MA POOLED. No double-counting risk. |
| 0.01–0.69 | USE MA POOLED + EXCLUDE overlapping primaries. MA captures more evidence. |
| 0.70–1.00 | USE PRIMARIES + EXCLUDE MA POOLED. Near-complete data; finer-grained control. |

Additional DCR rules: Forest plot entries superseded (active=0) when full paper extracted. Subgroup estimates from same MA are NOT independent — do not IVW-pool. Subgroups from different MAs can be pooled. NMA three-way overlap: if NMA more recent and includes pairwise MA's studies → use NMA; if pairwise MA more focused → use pairwise; record both as sensitivity analysis.

**Stage 6c — Meta-Analysis (EX-P4-MA).** IVW pooling under random effects (DerSimonian-Laird). Structural variance informed by annotation streams: limitation_unmeasured_confounder → +σ²_struct per edge; null_finding_context → adjusts structural inclusion probability. Six-branch decision tree selects aggregation method. Writes to edges_v1 (118 rows).

**Stage 6d — Publication Bias (EX-P4B).** For edges with k ≥ 10: Egger's regression + trim-and-fill. Adjusts SE where significant asymmetry detected.

### 7.4 Families 2–7 Compilation (C1–C6)

| Compiler | Source Agent | Aggregation Logic | Output Table |
|---|---|---|---|
| C1 Psychometric | AG11 | Sample-size-weighted mean α. Prefer CFA from largest cancer sample for loadings | instruments_v1 |
| C2 Norms | AG03-EXT | Weighted mean of means, pooled SD. 4-level fallback for missing nodes | context_matched_priors_v1 |
| C3 Temporal | AG08-EXT | NLLS fit of stretched exponential: R(t) = r∞(1−e^{−(t/τ)^γ}). V1 fallback: discrete categories when <3 timepoints | intervention_kernels_v1, recovery_params_v1 |
| C4 Dose-Response | AG06-EXT | Hill/Emax model via NLLS: E(d) = Emax × d^γ/(EC50^γ + d^γ). AIC comparison vs linear/threshold | dose_response_params_v1 |
| C5 Modifiers | AG05-EXT | IVW on interaction terms. Clamped to [0.7, 1.5] | modifier_registry_v1 |
| C6 Synergy | Factorial RCT interaction terms | Interaction coefficients calibrated vs Jaccard Pathway Overlap | synergy_registry_v1 |

### 7.5 Sufficiency Assessment and Gap Analysis (EX-P5)

After compilation, all seven families are evaluated together. Gaps generate acquisition queries feeding back to §9.

| Grade | Criteria |
|---|---|
| A | k ≥ 10, low heterogeneity, multiple designs |
| B | k ≥ 5, moderate heterogeneity |
| C | k ≥ 2, any heterogeneity |
| D | k = 1 (single study) |
| E | k = 0, literary prior only |
| F | k = 0, structural assumption only |

### 7.6 Meta-Analysis as Multi-Product Source

Meta-analyses are not single-product sources. Each produces 4–6 distinct extraction products routed to different destinations.

**Step 1 — Determine MA subtype:** pairwise_ma, nma, ipdma, dose_response_ma, umbrella_review.

**Pairwise MA products:** Product 1 (ALWAYS) — pooled effect estimate → edge_evidence_v1 with meta_source_flag = POOLED_ESTIMATE. Product 2 (ALWAYS) — heterogeneity parameters (I², τ², Q, prediction interval) → edge_evidence_v1.heterogeneity_json. Product 3 (ALWAYS) — included studies list → acquisition_queue_v1 (force multiplier: 1 MA → 15–50 high-priority targets). Forest plot entries → provisional edge_evidence_v1 rows with meta_source_flag = FOREST_PLOT_ENTRY, superseded when full paper extracted. Product 4 (when reported) — subgroup/moderator analyses → edge_evidence_v1 with meta_source_flag = SUBGROUP_ESTIMATE.

**NMA adds:** Product 5 — pairwise league table → edge_evidence_v1 with meta_source_flag = NMA_MIXED. Indirect estimates: identification = partially_identified. Incoherence check: node-splitting p < 0.05 → quality = weak.

**IPDMA adds:** Product 6 — individual-level interaction coefficients → edge_evidence_v1 with interaction_reported = 1. GRADE A modifier evidence.

**Dose-response MA:** Product 5-DR — dose-response curve points → edge_evidence_v1 with meta_source_flag = DOSE_RESPONSE_POINT. One row per dose category; reference category must be documented.

**Umbrella review:** ALL NUMERIC EXTRACTION BLOCKED. Write only study_registry_v1, ontology_links_v1, acquisition_queue_v1. Extract AMSTAR-2 ratings of constituent MAs.

### 7.7 Evidence Landscape Analytics

These components sit between extraction completion and algorithm execution.

**Pathway Completeness Auditor.** For each pathway: map to constituent edges → classify each edge (STRONG: k ≥ 5, SE_eff < 0.20, ≥2 research groups; MODERATE: k ≥ 2, SE_eff < 0.35; WEAK: k = 1; LITERARY_PRIOR: k = 0, default prior; STRUCTURAL_ASSUMPTION: k = 0, no prior) → compute chain confidence (serial: weakest link; parallel: weighted combination) → compute uncertainty floor → recommend (TRUST, CAUTION, DO_NOT_TRAVERSE, PARTIALLY_SUPPORTED).

**Scope-Conditional Evidence Summary.** For a given patient profile (cancer_type × treatment_phase × age_band): per edge, k_direct, k_transported, evidence_status (HAS_DIRECT, TRANSPORTED_ONLY, PRIOR_ONLY).

**Prior Sensitivity Analysis.** Standard Bayesian update vs prior shifted ±1 SD. If recommendation changes → PRIOR_SENSITIVE; all stable → EVIDENCE_ROBUST. Run as offline batch per scope profile, cached.

**Uncertainty Classification Taxonomy:** STATISTICAL (small samples), TRANSPORTABILITY (different populations), PRIOR_DOMINANCE (insufficient evidence), STRUCTURAL (model uncertainty), MEASUREMENT (instrument unreliability), TEMPORAL (kernel poorly constrained), EVIDENCE_CEILING (literature exhaustively searched, not reducible by search).


---

## 8. Cross-Cutting Contracts

### 8.1 Annotations: Category Taxonomy and Consumer Registry

Every paper contains approximately 22 content dimensions. The extraction pipeline fully captures 4 (effects, metadata, demographics, instruments). The annotation system captures the remaining 18 as typed strategic intelligence routed to specific downstream consumers. Annotations are not numeric values; they cross the Annotation Trust Boundary (§5.5 R4), not the numeric trust boundary (§6).

**Group 1 — Validity and Bias (7 types):**

| Category | Consumer | Required JSON Fields |
|---|---|---|
| limitation_unmeasured_confounder | Structural σ² inflation (EX-P4-MA) | confounder_name, direction_of_bias, magnitude_estimate |
| limitation_design | quality_rating demotion (EX-P2 S5) | limitation_type, severity |
| limitation_generalizability | Scope weight penalty (EX-P3 L2) | restriction, missing_population |
| limitation_measurement | Observation noise update | instrument_id, issue_type |
| model_diagnostic | quality_rating refinement | diagnostic_type, severity |
| null_finding_context | P_inclusion calibration (EX-P4-MA) | powered_adequately (REQUIRED boolean), post_hoc_explanation |
| replication_status | P_inclusion calibration | replicates: [ids], contradicts: [ids] |

**Group 2 — Mechanism and Biology (3 types):**

| Category | Consumer | Required JSON Fields |
|---|---|---|
| mechanism_hypothesis | DAG expansion queue | proposed_path: [nodes], evidence_type |
| mechanism_detail_subnode | Future DAG resolution | parent_node_id, detail_level |
| mechanism_interaction | Synergy model calibration | mechanism_a, mechanism_b, interaction_type |

**Group 3 — Dose-Response and Temporal (4 types):**

| Category | Consumer | Required JSON Fields |
|---|---|---|
| dose_response_qualitative | Emax model constraint | pattern, dose_at_plateau, units |
| temporal_onset | Kernel calibration | intervention_id, onset_weeks |
| temporal_decay | Kernel calibration | intervention_id, decay_half_life_weeks |
| temporal_trajectory | Recovery model | trajectory_class, inflection_weeks |

**Group 4 — Clinical and Practical (4 types):**

| Category | Consumer | Required JSON Fields |
|---|---|---|
| adherence_data | Adherence model coefficients | adherence_rate, dropout_rate, predictors, intervention_id |
| adverse_event | Contraindication rules | event_type, severity (REQUIRED), intervention_id, treatment_phase |
| practical_recommendation | Clinical output templates | recommendation, timing, population |
| instrument_observation | Measurement model update | instrument_id, observation_type |

**Group 5 — Evidence Landscape (4 types):**

| Category | Consumer | Required JSON Fields |
|---|---|---|
| research_gap | APS boost (1.5×) for matching acquisition candidates | gap_description, target_edge_ids, recommended_design |
| future_research | Study design templates | study_design_recommended |
| literature_comparison | Chain-vs-direct validation | consistent_with: [ids], inconsistent_with: [ids] |
| methodological_innovation | Pipeline evolution | innovation_type, description |

**Promotion thresholds:** Annotations accumulate until convergence triggers promotion to structured Class A table entries (with human approval): mechanism_hypothesis ≥3 papers, same edge → edge_relations_definitions. limitation_unmeasured_confounder ≥5 papers → structural σ² component. instrument_observation ≥2 papers, same DIF → observation_noise_v1. adherence_data ≥4 datapoints → logit(P_adhere) coefficients. adverse_event ANY serious OR ≥3 mild/moderate → contraindication_rules_v1. temporal_onset/decay ≥3 consistent observations → intervention_kernels_v1. dose_response_qualitative ≥2 same nonlinear → Emax-vs-RCS flag. research_gap persists ≥2 acquisition cycles → "Critical gap" status.

**Annotation lifecycle:** Raw → Reviewed → Promoted → Archived. Raw: freshly extracted, unverified. Reviewed: human/automated QA verified. Promoted: integrated into structured table. Archived: superseded.

### 8.2 Completeness Report and Provenance

Every extraction produces a report with 7 provenance codes:

| Code | Meaning | Acquisition Loop Response |
|---|---|---|
| PRESENT | Successfully extracted | — |
| ABSENT_IN_PAPER | Genuinely not reported | Generate acquisition query |
| PARSE_FAILURE | PDF parsing failed | Re-parse or different PDF |
| AGENT_MISS | Component detected but agent failed | Re-run or manual. ≥3× on same component → agent prompt revision, NOT more papers |
| GUARDED_REJECTION | Blocked by guardrail (figure-only, sensitivity analysis) | Consider manual extraction |
| TB_REJECTION | Trust boundary rejected (implausible, conversion invalid) | Review conversion validity |
| PARTIAL | Partially extracted (effect but no SE, qualitative only) | — |

**Completeness requirements by parameter family:**

**Family 1 — Edge Evidence.** Required: beta_raw, se_raw OR ci OR p-value, sample_size, study_design, effect_size_type. Desired: cancer_type (default "mixed" with scope penalty 1.25×), treatment_phase, instrument_id (unknown → m_measure = 1.15×), comparison_group_detail. Optional: publication_year, follow_up_duration, blinding, attrition_rate. COMPLETE: all R + all D. USABLE: all R, ≥1 D missing (proceeds with SE inflation). INSUFFICIENT: any R missing (excluded from compilation, acquisition query generated).

**Family 2 — Instrument Psychometrics.** Required: instrument_id, reliability_coefficient (α, ICC, or test-retest r), reliability_type, sample_size. Desired: population_descriptor, cancer_type_sample, subscale_detail. Optional: SEM_reported, MDC_reported, factor_structure. CRITICAL: No pooling protection for F2 — every error corrupts all patient scores. Verification is Tier 1 (100% check).

**Family 3 — Population Norms / Context Priors.** Required: node_id, mean, sd OR se OR ci, sample_size, cancer_type. Desired: treatment_phase, age_range, time_since_diagnosis, instrument_id. Optional: sex_distribution, comorbidity_profile.

**Family 4 — Temporal Dynamics.** Required: edge_id or node_id, timepoint_values (≥3), timepoint_labels (weeks/months post-tx), sample_size_per_timepoint. Desired: instrument_id, dropout_per_timepoint. Optional: assessment_window, treatment_duration. Minimum for temporal fit: ≥3 timepoints with labels, values, and N. Papers with <3 timepoints contribute to F1 but NOT F4.

**Families 5–7.** Each requires ≥3 data points for curve fitting (F5), ≥2 subgroup strata with independent estimates (F6), or ≥1 factorial/combination RCT with interaction term (F7).

### 8.3 Verification Architecture

Verification intensity stratified by error impact on patient predictions.

| Tier | Parameters | Protocol | Rationale |
|---|---|---|---|
| Tier 1 | Instrument α, factor loadings, population norms (~45–75 papers, ~130 values) | 100% human verify | No pooling protection. One error corrupts every patient using that instrument/norm. |
| Tier 2 | Context priors, recovery curves, kernels, biomarker correlations, modifiers (~40–70 papers, ~200 values) | 25–30% spot-check | Partial pooling protection. One error shifts compiled value by ~30–50%. |
| Tier 3 | Edge weights (β̂) (~150–300 papers, ~200+ values) | 10–15% sample verify | Full IVW pooling. Error in 1 of 5 studies shifts pool by ~10%. Within SE_eff band. |

**Influence-aware escalation (overrides tier assignment):** E1: Contributes >50% of edge's pooled weight → Tier 1. E2: Edge has <3 contributing studies → Tier 1. E3: Removing record flips sign of pooled estimate → Tier 1. E4: Only cancer-matched study for edge with ≤5 total → Tier 1. E5: SE at Level 4+ AND >30% pool weight → Tier 1. E6: Forest plot entry not yet superseded → Tier 1. Escalated records: unverified_inflation = 1.20× until human verification.

### 8.4 AI vs Compute Boundary

**Uses LLM (Claude API):** AG01–AG08, AG10, AG11 specialist extraction. Section classification fallback (<15% of papers). ConceptEngine fuzzy matching (DEEP mode only). Abstract relevance screening for ambiguous cases (0.5–0.8 range).

**Must be deterministic Python:** PDF parsing. Candidate span identification. AG09 reconciliation. Annotation reconciliation clustering (Jaccard). Trust boundary (all 11 parse rules, precision cascade, conversion matrix). Harmonization (all 7 substages). SE calibration (all multiplier formulas). IVW aggregation and all compilation. Gap analysis. Search saturation detection. APS scoring. Budget controls and rate limiting.

**Hard rule:** No LLM output touches any numeric value after the Trust Boundary.


---

## 9. Acquisition Loop (Behavioral Spec)

This section defines the behavioral specification of the acquisition loop — query generation, scoring gates, retrieval statuses, and phased strategy. For API endpoints, rate limits, retry policies, and CLI scripts, see the Implementation Playbook companion document.

### 9.1 Two Input Pathways

**Pathway 1 — Automated:** Registries → queries → search → score → retrieve → extract. **Pathway 2 — Manual:** Human drops PDF/CSV/JSON into manual_uploads/ → pipeline. Both feed into EX-P0 (triage).

### 9.2 Phased Search Strategy

Phases are ordered. Each phase generates inputs for subsequent phases.

| Phase | Targets | Rationale |
|---|---|---|
| 0 — Bootstrap | Compute derived tables from Class A registries. No search. Cost: 0 API calls. | Generate node_search_terms_v1, seed sd_anchors_v1, compute observation_noise_v1. Prerequisites for all search. |
| 1 — Meta-Analysis Harvest | MAs and systematic reviews for CRCI interventions. Expected: 5–15 MAs. | Force multiplier: each MA yields 15–50 scored acquisition candidates for Phase 3. Immediate pooled estimates + heterogeneity. |
| 2 — Measurement Infrastructure (concurrent with Phase 1) | Psychometric validation + normative reference data. Expected: 30–50 papers. | Wrong α corrupts every patient. Validated properties feed Phase 3 trust boundary. Normative papers populate sd_anchors_v1. |
| 3 — Core Evidence | Primary studies from Phase 1 MA constituent lists. By pathway priority: neuroinflammation, sleep/fatigue, neuroplasticity, then by tier. Expected: 60–200 papers. | Direct DOI/PMID retrieval. Full pipeline support now operational. |
| 4 — Context + Temporal (concurrent with Phase 3) | Large observational cohorts + longitudinal studies with ≥3 timepoints. Expected: 20–40 papers. | Prioritize prior and kernel searches for most-represented populations. |
| 5 — Gap-Filling (ongoing until termination) | Gap analysis output, annotation-boosted APS, citation-chain, content-driven hops. | System knows exactly what's missing. Targeted gap-filling replaces blind keyword search. |

### 9.2.1 Pre-Retrieval Abstract Screening

Candidates undergo pre-retrieval abstract screening before full-text retrieval is attempted. This conserves retrieval budget by filtering irrelevant candidates based on abstract content alone.

Pre-retrieval screening classifies each candidate into one of four relevance levels:

| Level | Criteria | Action |
|---|---|---|
| HIGH | Both source and target constructs present in cancer population. Study design matches workstream need. | Proceed to full-text retrieval |
| MODERATE | Partial match — one construct present, or cancer population implied but not confirmed, or relevant design with ambiguous outcome measures | Proceed to full-text retrieval |
| LOW | Tangential — related domain but no clear construct match, or non-cancer population with potentially transportable findings | DEFER. Retained in acquisition_queue_v1 for future re-scoring if edge gaps persist |
| IRRELEVANT | No construct match. Wrong domain entirely, or pediatric-only, or non-human without translational framing | REJECT. No retrieval attempted |

Screening is deterministic for HIGH and IRRELEVANT (keyword/MeSH matching against node_search_terms_v1 and edge_relations_definitions). MODERATE and LOW cases in the 0.5–0.8 confidence range use LLM-assisted classification (see §8.4). Abstract effect detection uses regex patterns for common statistical reporting (e.g., `r\s*=\s*[\-\d\.]+`, `p\s*[<>=]\s*[\d\.]+`, `CI\s*[\[\(]`) to boost relevance scores for abstracts containing extractable quantitative results.

### 9.3 Seven Workstreams

**WS1 — Edge Evidence (350–600 queries).** Primary: meta-analysis decomposition (80%). Secondary: keyword search for uncovered edges (15%). Tertiary: citation-chain (5%).

**WS2 — Instrument Psychometrics (46–69 queries).** Primary: instrument-name search with reliability filters, cancer-specific with fallback (70%). Secondary: citation-chain (30%).

**WS3 — Population Norms (15–30 queries).** Primary: instrument + normative search (40%). Secondary: Table 1 extraction from already-acquired papers (60%).

**WS4 — Context-Matched Priors (10–24 queries).** Primary: cancer-type × treatment-phase search. Secondary: Table 1 from RCTs. Similar split to WS3.

**WS5 — Recovery Parameters (8–15 queries).** Primary: longitudinal filter on already-acquired RCTs (80%). Secondary: keyword search for follow-up publications (20%).

**WS6 — Intervention Kernels (20–30 queries).** Same split as WS5.

**WS7 — Biomarker Correlations (8–12 queries).** Primary: citation-chain expansion from biomarker-measuring studies (60%). Secondary: keyword search for multi-biomarker panels (40%).

### 9.4 Content-Driven Hop Decisions

After extracting Paper X, the pipeline examines extraction outputs and annotation-to-reference links to generate targeted next-hop queries.

**Five hop signals:** (1) Instrument cited without psychometrics extracted → queue validation paper for WS2. (2) Biomarker measured without correlation reported → queue cited references for WS7. (3) Mechanism hypothesis with cited supporting evidence → queue for matching edge workstream. (4) Research gap with cited context → queue for matching workstream. (5) Companion dataset publications → search for companion papers (same PI, trial registration, cohort name, ±3 years).

**Hop execution:** Resolve to DOI/PMID → check study_registry_v1 → score with APS + 0.15 citation-validation bonus → queue to acquisition_queue_v1. Hard ceiling: hop_depth ≤ 3, ≤20 targets per source paper.

### 9.5 Acquisition Priority Score (APS)

APS = 0.35×EdgeGap + 0.20×DesignBonus + 0.20×PopMatch + 0.15×Recency + 0.10×SourceQuality.

- **EdgeGap:** 1 − (sufficiency_grade / 5).
- **DesignBonus:** RCT=1.0, MA=0.9, longitudinal=0.7, cross-sectional=0.4, other=0.2.
- **PopMatch:** Exact cancer=1.0, same organ=0.7, different solid=0.4, hematological=0.2.
- **Recency:** max(0, 1 − (current_year − pub_year) / 20).
- **SourceQuality:** AMSTAR-2 or journal impact proxy.

Author-gap boost: if candidate maps to edge with research_gap from ≥1 domain expert paper: APS_final = min(1.0, APS × 1.5). Citation-validation bonus: APS_final = APS + 0.15 for papers found via citation chain. Gate: APS ≥ 0.40 → DISPATCH. APS < 0.40 → DEFER.

### 9.6 Paywall Handling and APS-Based Retrieval Triage

**Full-text retrieval priority (first success wins):** (1) paperscraper fallback chain — publisher direct, BioC-PMC, eLife XML, Wiley TDM, Elsevier TDM (see Implementation Playbook §P1.7). (2) Europe PMC full-text XML. (3) Unpaywall best OA PDF. (4) PubMed Central PDF. (5) Triage by APS (below).

Papers with APS ≥ 0.40 that fail all free and TDM retrieval routes are triaged by APS into three tiers:

| APS Range | Retrieval Status | Action |
|---|---|---|
| ≥ 0.70 | HUMAN_NEEDED | Flagged for manual acquisition. Appears in human acquisition report (see Playbook §P3). Researcher downloads to manual_uploads/ using DOI-based filename (see Playbook §P1.6). Full pipeline on receipt. |
| 0.40–0.69 | ABSTRACT_ONLY | Extracted in SHALLOW mode with m_design = 3.0×, providing lower-confidence evidence without human effort. Contributes to gap analysis but with inflated SE. |
| < 0.40 | DEFERRED | Not retrieved. Retained in acquisition_queue_v1 for re-scoring if edge gaps persist. |

### 9.7 Search Saturation

Track per workstream × per edge: overlap_ratio > 0.80 for 2 consecutive cycles → saturation_flag = TRUE. Stop generating queries for that thread. Other workstreams for same edge can continue.

### 9.8 Loop Termination

Stop when any of: all edges ≥ Grade C; no candidates with APS ≥ 0.40 remain; daily budget exhausted; manual stop command; search saturation on all active threads.

### 9.9 Dataset Clustering for Observational Cohorts

Multiple papers from same longitudinal cohort must be grouped as one evidence source. Detection: same PI + same cohort name + overlapping enrollment period. Resolution: select one primary paper per trial registration for pooling; others contribute secondary yields without double-counting.

### 9.10 Edge Coverage Matrix

Each acquisition cycle produces an edge coverage matrix as a required output artifact. For each edge in edges_v1, the matrix reports: count of full-text papers extracted, count of abstract-only papers, count of pending HUMAN_NEEDED acquisitions, current sufficiency grade (A–F), and the dominant evidence gap type (if any). This matrix is the primary input to EX-P5 gap analysis and drives the next cycle's query generation. The matrix is persisted as evidence_landscape_v1 (parameterized by scope) and is regenerated at the end of each acquisition cycle.

---

## 10. Manual Input Protocol

Three manual pathways, each feeding into EX-P0 triage:

**Pathway 1 — PDF Drop.** Researcher deposits PDFs into data/manual_uploads/pdfs/. File watcher detects → validates → routes to EX-P0 → full pipeline. Used for paywall-resolved papers, pre-prints, and non-indexed sources.

**Pathway 2 — Structured CSV.** Six CSV templates (see Checklists and Templates companion document) expose only Layer 0 fields appropriate to each workstream. Import script validates, assigns UUIDs, and queues for Trust Boundary. Templates: edge_evidence, instrument_evidence, norms, temporal, biomarker, modifier.

**Pathway 3 — DOI Override.** DOI-list files (one DOI per line). System resolves DOIs via automated retrieval pipeline. Used when researcher identifies relevant papers from conference proceedings, reference lists, or expert recommendations.

### 10.1 File Storage Architecture

All paper files use study_id-based naming with sidecar files:

```
data/papers/
├── {study_id}.pdf              ← Downloaded by AuditedRetriever (via paperscraper)
├── {study_id}.json             ← paperscraper sidecar metadata (title, authors, abstract)
├── {study_id}.txt              ← EX-INGEST canonical_text output
├── {study_id}_papermap.json    ← EX-P1 Canonical Reader PaperMap (immutable after creation)
├── {study_id}.xml              ← Alternative: BioC-PMC/JATS XML (instead of .pdf)
└── ...
```

study_registry_v1 carries four file-tracking columns: `pdf_path` TEXT (path to .pdf or .xml), `canonical_text_path` TEXT (path to .txt), `file_type` TEXT (ENUM: pdf, xml, abstract_only), `parse_quality` TEXT (ENUM: GOOD, DEGRADED, SCAN, PARSE_FAILURE). These are written by EX-INGEST.

**Audit chain:** extraction_snippet (edge_evidence_v1) → study_id → study_registry_v1.pdf_path (original source) + study_registry_v1.canonical_text_path (parseable text). PaperMap references span_ids back to canonical_text character offsets. Every numeric value traces to a source file on disk.

---

## 11. Quality Gates

Every gate is a HARD STOP. A paper does not proceed past a gate until the gate condition is satisfied.

| Gate | Location | Condition | Failure Action |
|---|---|---|---|
| P0-G1 | End of EX-P0 S1 (post-PDF-parse) | PaperMap has ≥3 detected sections AND ≥1 table or figure. Abstract present. | OCR-eligible → OCR → re-check. Else → REJECTED (STRUCTURAL_FAILURE). |
| P0-G2 | End of EX-P0 S3 (post-classification) | component_inventory contains ≥1 parameter-yielding OR ≥1 intelligence-yielding component. | Log NO_YIELD_POTENTIAL. Do not extract. Metadata retained for reference mining. |
| P1-G1 | End of Canonical Reader | PaperMap has ≥3 detected sections. | Section-classification fallback (LLM). If fallback fails → DEGRADED mode. |
| P1-G3 | End of AG09 (SpanLabel reconciliation) | All 7 deterministic checks pass: (1) span_id referential integrity, (2) no orphaned labels, (3) cross-agent entity_id consistency, (4) numeric sign coherence, (5) design classification consensus ≥2 agents, (6) no self-contradicting labels, (7) provenance chain complete. | Per-check remediation. >3 simultaneous failures → HUMAN_REVIEW queue. |
| P1-G4 | End of annotation reconciliation | Contradiction rate < 30% of reconciled clusters. | High-contradiction clusters flagged HUMAN_REVIEW. Numeric extraction proceeds; annotation batch quarantined. |
| P1-G5 | End of EX-P1 (post all agents) | Agents activated match execution_mode: DEEP ≥8, STD ≥8, SHALLOW = 3, MINIMAL = 1. | Log EXECUTION_MODE_MISMATCH. Under-extracted → re-run. Over-extracted → proceed + budget flag. |
| P1-G6 | Batch-level (every 20 papers) | escape_hatch_rate < 15% across batch. | LOG WARNING. Generate diagnostic report. Trigger section-assignment review. Does not block individual papers. |
| TB-G1 | End of Trust Boundary | Every numeric value in Layer 1 has non-null precision_level and se_final. | TB_PARSE_FAIL values retained in Layer 0, not promoted. Paper continues with partial extraction. |
| P2-G1 | End of EX-P2 (Harmonization) | Every converted effect size has conversion_validity_flag = TRUE. No blocked conversions bypassed. | CONVERSION_BLOCKED values excluded from compilation. |
| P4-G1 | Start of EX-P4 (post-DCR) | No study_id appears in both MA included_k set AND as independent primary without resolution. | HALT compilation for that edge. Generate overlap report. Route to human adjudication. |

### 11.1 LLM Guardrails

**Universal (all paper types):** UG-01: LLMs never output parsed floats (SpanLabel char offsets only). UG-02: DOIs format-validated (regex). UG-03: Study counts cross-validated against abstract. UG-04: Effect direction sign-verified. UG-05: No extraction from figures/images. UG-06: No imputation (NULL, not estimated). UG-07: Extraction snippets mandatory. UG-08: Sensitivity analysis results flagged [SENSITIVITY].

**Meta-analysis specific:** MG-01: Extract from summary/abstract, not forest plot entries. MG-02: Random-effects default. MG-03: Heterogeneity mandatory. MG-04: Umbrella review estimates blocked. MG-05: NMA indirect → partially_identified. MG-06: Dose-response requires reference category. MG-07: Forest plot data provisional. MG-08: Publication bias informs, doesn't modify estimate.

**Primary study specific:** PG-01: RCT requires explicit randomization language. PG-02: Crossover RCTs require period-effect check. PG-03: Pilot RCTs quality capped. PG-04: Animal studies require species/strain documentation. PG-05: Cross-sectional → not_identified. PG-06: EMA requires ≥3 assessments/day. PG-07: Case reports/qualitative: no evidence rows.

**Annotation specific:** AG-01: Attributed to paper sections. AG-02: Distinguish author-proposed vs extractor-inferred. AG-03: Null findings require powered_adequately. AG-04: Name specific confounders. AG-05: Adverse events require severity. AG-06: Research gaps link to edge_relation_ids. AG-07: Annotations never modify numeric extraction.

---

## 12. Version History and Migration Notes

### 12.1 EX-P1 v1 → v2 Migration

**v1 (sequential, deprecated):** Agents ran in fixed order. Each agent read the full paper. No shared PaperMap. Reconciliation was ad-hoc.

**v2 (parallel, canonical):** Canonical Reader builds immutable PaperMap. Agents run in parallel on targeted sections. AG09 reconciliation is deterministic with 7 formal checks. Annotation reconciliation added with Jaccard clustering. ConceptEngine added for entity grounding. Two-tier extraction strategy added. Completeness reporting with provenance codes added.

The v1 sequential flow is deprecated. It may be retained in historical documentation but must not be referenced as current architecture.

### 12.2 Convergence Points and Feedback Loops

**Six convergence points:** C1 PaperMap (fan-out from shared representation). C2 Trust Boundary (all numeric SpanLabels through same firewall). C3 Reconciliation (all agent annotations unified). C4 Evidence Grouper (records grouped by edge). C5 Structural Variance (numeric stream meets annotation stream — only point where annotations affect numeric parameters). C6 Sufficiency Assessment (all 7 families evaluated together).

**Two feedback loops:** Loop 1 (Evidence Acquisition): sufficiency → gaps → queries → retrieval → triage → extraction → compilation → sufficiency. Termination per §9.8. Loop 2 (Annotation Promotion): annotations accumulate → convergence threshold → promotion proposal → human approval → Class A update. Timescale: months.

### 12.3 Documents Superseded

This specification supersedes: Extraction System Architecture v2.0, Heterogeneous Paper Treatment Protocol, Paper Intelligence Maximization Protocol, Paper-Type Routing and Directed Acquisition Protocol, Automated Retrieval and Acquisition Implementation Plan, Box-to-Implementation Mapping Sheet v1.0, Extraction System Finalizing Addendum v1.0.

---

*End of CRCI Extraction System Master Specification v2.0*

*Companion documents:*
- *Engineering Appendix v2.0 — module manifest, test specifications, file paths*
- *Implementation Playbook v2.0 — prompt sequences, CLI scripts, budgets, rate limits*
- *Checklists and Templates v2.0 — CSV templates, operational checklists*
