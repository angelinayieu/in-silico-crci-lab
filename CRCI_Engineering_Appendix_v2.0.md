# CRCI — Extraction System Engineering Appendix v2.0

**Companion to:** CRCI Extraction System Master Specification v2.0
**Version 2.0 — February 2026**

This document contains the module manifest, schema reference, per-module test specifications, and cross-cutting invariants. For behavioral specifications, see the Master Spec. For CLI scripts and budget controls, see the Implementation Playbook.

---

## A. Schema Reference

### A.1 Extraction Surface Schema (edge_evidence_v1 Write Layers)

The 72-column edge_evidence_v1 table is partitioned by write ownership:

**Layer 0 — Extraction Surface (~18 cols).** What curators/agents write: ler_id, study_id, edge_id, beta_raw, se_raw, effect_type_original, effect_size_type (BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE), sample_size, study_design, cancer_type, treatment_phase, instrument_id, publication_year, meta_source_flag, parent_meta_study_id, provenance_location, confidence_note.

**Layer 1 — Trust Boundary (~8 cols).** Written by EX-TB: tb_parse_status, tb_plausibility_check, beta_validated, se_validated, effect_type_classified, tb_rejection_reason, derivation_level, inflation_factor.

**Layer 2 — Harmonization (~12 cols).** Written by EX-P2: beta_sd_sd, se_sd_sd, conversion_rule_id, sd_anchor_id, identification_status, w_scope, scope subscores, orientation_confidence.

**Layer 3 — Calibration (~16 cols).** Written by EX-P3: SE_eff, m_design, m_GRADE, m_temporal, tau_sq, w_fresh, w_scope_applied, layer multipliers, calibration_timestamp.

**Layer 4 — Aggregation (~8 cols).** Written by EX-P4: pooling_status, dcr_overlap_flag, dcr_decision, pooled_edge_contribution, aggregation_run_id.

**Layer 5 — Runtime Audit (~8 cols).** Written during execution: last_used_in_run_id, last_used_timestamp, active, superseded_by.

Manual CSV upload exposes Layer 0 only. Import script reads 18 columns, writes with Layers 1–5 null, queues for Trust Boundary.

### A.2 Fields Added by This Specification

**study_registry_v1:** +study_subtype TEXT (Master Spec §4.1 controlled vocabulary), +included_study_ids_json TEXT (JSON array), +included_k INTEGER, +pdf_path TEXT (path to .pdf or .xml source file, written by EX-INGEST), +canonical_text_path TEXT (path to .txt canonical text, written by EX-INGEST), +file_type TEXT (ENUM: pdf, xml, abstract_only), +parse_quality TEXT (ENUM: GOOD, DEGRADED, SCAN, PARSE_FAILURE, written by EX-INGEST PDFProcessor).

**edge_evidence_v1:** +meta_source_flag TEXT (controlled vocabulary: NULL, POOLED_ESTIMATE, SUBGROUP_ESTIMATE, NMA_MIXED, NMA_DIRECT, FOREST_PLOT_ENTRY, DOSE_RESPONSE_POINT), +parent_meta_study_id TEXT (FK → study_registry_v1), +heterogeneity_json TEXT (JSON), +effect_size_type TEXT (BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE).

**study_annotations_v1:** +span_id TEXT, +section_label TEXT, +adjudication_status TEXT (ENUM: unreviewed, auto_merged, conflict, human_reviewed, human_approved, human_rejected), +duplicate_of_annotation_id TEXT, +cross_agent_support_n INTEGER (default 1), +extraction_mode TEXT (ENUM: explicit_author_statement, extractor_inference, computed_from_context).

**acquisition_queue_v1:** +saturation_cycle_count INTEGER (default 0), +saturation_flag BOOLEAN (default FALSE), +paywall_flagged BOOLEAN (default FALSE), +hop_source_study_id TEXT (FK, nullable), +hop_depth INTEGER (default 0), +retrieval_status TEXT (ENUM: PENDING, FULL_TEXT_PDF, FULL_TEXT_XML, ABSTRACT_ONLY, HUMAN_NEEDED, REJECTED, DUPLICATE. Default: PENDING. Tracks each candidate through the retrieval state machine. Updated by retriever.py on each retrieval attempt. HUMAN_NEEDED set when APS ≥ 0.70 and all free/TDM routes fail. ABSTRACT_ONLY set when 0.40 ≤ APS < 0.70 and full-text unavailable.), +abstract_relevance TEXT (ENUM: HIGH, MODERATE, LOW, IRRELEVANT. Set by pre-retrieval screening per Master Spec §9.2.1. Only HIGH and MODERATE proceed to retrieval).

**New views (recomputed on demand):** pathway_evidence_audit_v1, evidence_landscape_v1 (parameterized by scope).

### A.3 study_annotations_v1 Full Column Specification

| Column | Type | Description / Constraints |
|---|---|---|
| annotation_id | TEXT PK | UUID, auto-generated |
| study_id | TEXT FK | → study_registry_v1. NOT NULL |
| ler_id | TEXT FK | → edge_evidence_v1. Nullable (some annotations are study-level) |
| category | TEXT | NOT NULL. 22 categories from Master Spec §8.1 |
| consumer | TEXT | NOT NULL. Which module reads this annotation |
| target_entity_type | TEXT | ENUM: node, edge, instrument, study, pathway, biomarker, global |
| target_entity_id | TEXT | FK to relevant entity table. Nullable for global |
| content | TEXT | NOT NULL. Free-text description |
| structured_data_json | TEXT | JSON blob. Schema varies by category (§A.4) |
| evidence_strength | TEXT | ENUM: strong, moderate, weak, speculative |
| extraction_snippet | TEXT | Verbatim text span from paper |
| maturity | TEXT | ENUM: raw, reviewed, promoted, archived. Default: raw |
| promoted_to | TEXT | Nullable. Target table + field if promoted |
| entered_by | TEXT | Agent ID (AG01–AG11) or "human" |
| entered_at | TIMESTAMP | UTC, auto-populated |
| version | INTEGER | Starts at 1. Incremented on update |
| active | BOOLEAN | Default TRUE. Set FALSE on archive |
| span_id | TEXT | FK → PaperMap spans. Nullable |
| section_label | TEXT | Source section (methods, results, discussion, etc.) |
| adjudication_status | TEXT | ENUM: unreviewed, auto_merged, conflict, human_reviewed, human_approved, human_rejected |
| duplicate_of_annotation_id | TEXT | FK → annotation_id. Nullable |
| cross_agent_support_n | INTEGER | Count of agents producing equivalent annotation. Default 1 |
| extraction_mode | TEXT | ENUM: explicit_author_statement, extractor_inference, computed_from_context |

**Indexes:** PRIMARY KEY (annotation_id). INDEX on study_id, category, (target_entity_type, target_entity_id), and maturity WHERE active = TRUE. UNIQUE CONSTRAINT: no duplicate (study_id, category, content_hash) where content_hash = SHA-256 of content.

### A.4 structured_data_json Schemas by Category

**measurement_concern:** `{"instrument_id": str, "concern_type": "ceiling|floor|cultural_bias|reading_level|administration_mode", "severity": "minor|moderate|severe", "affected_subscale": str|null, "recommendation": str}`

**adherence_data:** `{"adherence_rate": float [0-1], "dropout_rate": float [0-1], "assessment_method": "self_report|pill_count|electronic|biomarker", "predictors_of_nonadherence": [str], "intervention_id": str}`

**adverse_event_report:** `{"event_type": str, "severity_grade": int [1-5], "incidence_rate": float, "relatedness": "definite|probable|possible|unlikely|unrelated", "intervention_id": str, "n_affected": int}`

**mechanism_hypothesis:** `{"mechanism_type": "neuroinflammatory|oxidative_stress|hormonal|neurotoxic|genetic|psychological|vascular|other", "pathway_id": str|null, "biomarker_ids": [str], "direction": "supports|contradicts|extends", "cited_evidence_dois": [str]}`

**biomarker_correlation:** `{"biomarker_id_1": str, "biomarker_id_2": str, "correlation_r": float, "ci_lower": float|null, "ci_upper": float|null, "sample_size": int, "population": str, "method": "pearson|spearman|partial"}`

**research_gap:** `{"gap_type": "unmeasured_outcome|unmeasured_moderator|missing_population|insufficient_followup|missing_comparison|methodological", "target_edge_id": str|null, "target_node_id": str|null, "specificity": "actionable|directional|vague", "cited_context_dois": [str]}`

**limitation_unmeasured_confounder:** `{"confounder_name": str, "expected_direction": "positive|negative|unknown", "affected_edge_ids": [str], "measured_in_other_studies": bool|null}`

**subgroup_signal:** `{"moderator_variable": str, "subgroup_levels": [str], "effect_differences": [float], "interaction_p": float|null, "sample_sizes_per_level": [int]}`

**dose_response_signal:** `{"dose_levels": [float], "dose_unit": str, "response_values": [float], "response_metric": str, "monotonic": bool, "threshold_suggested": float|null}`

**temporal_pattern:** `{"pattern_type": "onset|peak|decay|rebound|plateau|delayed", "timepoints_weeks": [float], "values": [float], "instrument_id": str|null}`

**attrition_analysis:** `{"overall_attrition_rate": float, "differential_attrition": bool, "treatment_group_rate": float, "control_group_rate": float, "attrition_predictors": [str], "method_of_handling": "ITT|per_protocol|completer|MMRM|MI|LOCF"}`

**sample_representativeness:** `{"recruitment_setting": str, "inclusion_criteria_summary": str, "mean_age": float|null, "pct_female": float|null, "cancer_stage_distribution": str|null, "comorbidity_exclusions": [str], "generalizability_concern": str|null}`

### A.5 Interim Encoding Conventions

Before schema migration adds new columns, encode new fields in existing TEXT columns using structured prefixes. Parsing rule: `\[([A-Z_]+):\s*(.+?)\]`.

**confidence_note** (edge_evidence_v1): `[META_FLAG: POOLED_ESTIMATE]`, `[ESF_TYPE: BETWEEN_GROUP]`, `[PARENT_MA: study_id_value]`, `[HET: {"I2": 0.45, "tau2": 0.03}]`.

**notes** (study_registry_v1): `[SUBTYPE: pairwise_ma]`, `[INCLUDED_K: 15]`, `[INCLUDED_IDS: ["s001","s002",...]]`.

**content** (study_annotations_v1): `[SPAN: span_id_value]`, `[SECTION: methods]`, `[EX_MODE: explicit_author_statement]`.

After migration: interim encoding ceases; existing values migrated by scripts/migrate_interim_encoding.py.

---

## B. Module Manifest and Codebase Alignment

```
crci_core/
  registries/*.py              Master Spec §2.1 prerequisite table loaders

crci_acq/
  query_generator.py           MS §9.3 workstream query templates (uses paperscraper.pubmed.utils)
  search_coordinator.py        MS §9 multi-source orchestration
  aps_ranker.py                MS §9.5 APS scoring + annotation boost
  dedup.py                     DOI exact-match + title Jaccard ≥ 0.85 deduplication
  retriever.py                 MS §9.6 AuditedRetriever: wraps paperscraper.pdf.save_pdf
                               with audit trail, Unpaywall/EuropePMC fallbacks,
                               study_id naming, state tracking, abstract-only mode
  id_resolver.py               NCBI ID Converter: DOI ↔ PMID ↔ PMCID cross-referencing
                               (surfaces what paperscraper's BioC-PMC fallback discards)
  abstract_screener.py         MS §9.2.1 pre-retrieval abstract screening (4-level relevance)
  manual_ingest.py             MS §10 pathway 2 (manual upload) + DOI filename matching
  queue.py                     Acquisition queue management
  cache.py                     Retrieval cache
  feedback.py                  MS §12.2 loop 1 (gap → query)
  hop_generator.py             MS §9.4 content-driven hop logic
  saturation.py                MS §9.7 search saturation detection
  adapters/
    base.py                    SourceAdapter interface
    pubmed.py                  PubMed E-utilities (enriched: captures PMID + MeSH terms
                               that stock paperscraper drops from pymed output)
    europe_pmc.py              Europe PMC (NOT in paperscraper — CRCI addition)
    crossref.py                Crossref (NOT in paperscraper — CRCI addition)
    openalex.py                OpenAlex (NOT in paperscraper — CRCI addition)
    unpaywall.py               Unpaywall (NOT in paperscraper — CRCI addition)
    manual.py                  Filesystem adapter

crci_extract/
  pdf_processor.py             MS §3.2 (EX-INGEST) PDF/XML → canonical_text + quality flags
                               (paperscraper has zero text extraction capability)
  p0_triage.py                 MS §3.2 (EX-P0) relevance + classification
  reader.py                    MS §5.2 Canonical Reader
  paper_map.py                 MS §5.2 PaperMap data structure
  classifier.py                MS §4.1 subtype classification
  component_inventory.py       MS §4.3 component detection
  activation_planner.py        MS §4.5 agent activation planning
  shared_context.py            MS §5.3 section routing to agents
  span_store.py                SpanLabel storage
  completeness.py              MS §8.2 completeness report
  agents/
    metadata.py                AG01
    design.py                  AG02
    cohort.py                  AG03 + AG03-EXT
    outcomes.py                AG04
    stats_label.py             AG05 + AG05-EXT
    exposure.py                AG06 + AG06-EXT
    mediator.py                AG07
    temporal.py                AG08 + AG08-EXT
    reconcile.py               AG09 (rule-based, no LLM)
    intel.py                   AG10
    instrument_val.py          AG11

crci_harmonize/
  trust_boundary.py            MS §6 numeric firewall
  effect_convert.py            MS §6.3–6.4 conversion validity matrix + formulas
  harmonize.py                 MS §7.1 seven harmonization substages

crci_calibration/
  seven_layer.py               MS §7.2 SE calibration

crci_compile/
  grouping.py                  MS §7.3 evidence grouping
  dcr.py                       MS §7.3 double-counting resolution
  meta_analysis.py             MS §7.3 IVW aggregation
  compilers/
    psychometric.py            C1
    norms.py                   C2
    temporal.py                C3
    dose_response.py           C4
    modifiers.py               C5
    synergy.py                 C6
  gap_analysis.py              MS §7.5 sufficiency grading
  pub_bias.py                  Egger's + trim-and-fill

crci_analytics/
  pathway_audit.py             MS §7.7 pathway completeness
  evidence_landscape.py        MS §7.7 scope-conditional summary
  prior_sensitivity.py         MS §7.7 prior dominance analysis
  uncertainty_classify.py      MS §7.7 uncertainty taxonomy

crci_store/
  write_evidence.py            Idempotent upsert
  annotation_reconcile.py      MS §5.5 EX-P1-REC

crci_intel/
  promotion.py                 MS §8.1 annotation promotion engine

crci_validate/
  discrepancy.py               MS §12.2 chain-vs-direct validation

crci_obs/
  metrics.py                   Observability + QA

scripts/
  run_acquisition.py           CLI: automated acquisition cycle
  run_extraction.py            CLI: extraction pipeline
  run_manual_import.py         CLI: manual uploads
  run_full_cycle.py            CLI: end-to-end
  import_manual_csv.py         CLI: CSV template import
  migrate_interim_encoding.py  CLI: interim→column migration
```

---

## C. Test Specifications per Module

Every module requires the following minimum tests before deployment. Categories: UNIT (single function), INTEGRATION (multi-module), INVARIANT (must always hold).

### C.1 Acquisition Layer (crci_acq/)

**query_generator.py:** UNIT — each workstream template produces syntactically valid PubMed query via `paperscraper.pubmed.utils.get_query_from_keywords`. All 7 workstreams tested with mock data. Query length ≤ 4096 chars. INVARIANT — queries never contain patient-identifiable information.

**aps_ranker.py:** UNIT — APS formula produces [0, 1] for all valid inputs. Monotonicity under single-variable changes. Author-gap boost adds exactly 0.15. Citation-validation bonus adds exactly 0.10.

**search_coordinator.py:** INTEGRATION — multi-source orchestration respects rate limits. UNIT — dedup by DOI exact-match; by title Jaccard ≥ 0.85. INVARIANT — no adapter called after rate limit hit.

**retriever.py (AuditedRetriever):** INTEGRATION — calls paperscraper's save_pdf first, then CRCI fallbacks (Unpaywall, Europe PMC) in order. First success stops chain. UNIT — audit record populated on every call: fallbacks_tried list, timing, file_type, file_size. study_id-based file naming (not DOI-based). retrieval_status updated in acquisition_queue_v1 on every attempt. ABSTRACT_ONLY triggered when APS 0.40–0.69 and all full-text fails. HUMAN_NEEDED when APS ≥ 0.70 and all fails. Cached files detected and skipped. INVARIANT — paperscraper never called without wrapping try/catch.

**id_resolver.py:** UNIT — DOI→PMCID resolution via NCBI ID Converter API. PMID→DOI reverse resolution. Handles missing/unknown identifiers (returns None, not error). Rate limited (max 3 req/s). INTEGRATION — surfaces PMCID that paperscraper's BioC-PMC fallback internally computes but discards.

**abstract_screener.py:** UNIT — HIGH classification when both source+target constructs present in cancer population. IRRELEVANT when no construct match. MODERATE/LOW boundary consistent. Regex patterns for abstract effect detection functional. INTEGRATION — only HIGH and MODERATE candidates proceed to retriever.

**adapters/pubmed.py:** UNIT — captures PMID from pymed output (which stock paperscraper drops). Captures MeSH keywords. study_design_hint inferred from abstract keywords. INTEGRATION — results include all 3 identifiers (DOI, PMID, PMCID via id_resolver).

**adapters/*.py (all others):** UNIT per adapter — valid API call construction, response parsing, error handling (HTTP 429, 500, timeout), rate limit compliance. INTEGRATION — retry policy (3 retries, exponential backoff).

### C.1b Ingestion (crci_extract/pdf_processor.py)

**pdf_processor.py (PDFProcessor):** UNIT — PDF with text → quality=GOOD, canonical_text length > 500 chars. Scanned PDF (no text) → quality=SCAN. Encrypted PDF → PARSE_FAILURE. XML (BioC-PMC) → structured text extraction with section preservation. Table detection: pdfplumber finds tables in known table-containing PDFs. Figure detection: embedded images detected. Sidecar .txt file written alongside source. INTEGRATION — study_registry_v1 updated with pdf_path, canonical_text_path, file_type, parse_quality. Gate: PARSE_FAILURE → does not proceed to EX-P0. INVARIANT — canonical_text persisted before EX-P0 entry.

### C.2 Triage (crci_extract/p0_triage.py)

UNIT — PDF ingestion produces ≥3 sections for well-formed papers. Encrypted → REJECTED. Scanned → DEGRADED, routed to OCR. Relevance: known RCT → ≥ 0.8; known irrelevant → < 0.5. study_subtype matches expected for 10+ known papers. component_inventory detects primary_effect in RCTs. INTEGRATION — Gate P0-G1 blocks <3 sections; P0-G2 blocks no yield. INVARIANT — every paper gets exactly one of INCLUDE, HUMAN_REVIEW, EXCLUDE.

### C.3 Canonical Reader (crci_extract/reader.py)

UNIT — section segmentation ≥3 sections in 10+ papers. Table/figure registry detects tables. Candidate span IDs non-overlapping. PaperMap serialization roundtrip lossless. INVARIANT — PaperMap immutable after creation. Every span has unique span_id.

### C.4 Specialist Agents (crci_extract/agents/*.py)

Per agent (AG01–AG11): UNIT — reads only assigned sections. Output conforms to SpanLabel schema. Timeout at 60s → AGENT_MISS, not crash. Malformed output attempt-parsed; unparseable → AGENT_MISS. INTEGRATION — activation matches execution_mode.

**AG05 specifically:** Distinguishes BETWEEN_GROUP vs WITHIN_GROUP d. Null findings with CI → powered_adequately assessed. p-value extraction handles "p < 0.001", "p = 0.03", "NS".

**AG09 specifically:** All 7 deterministic checks implemented. No LLM calls. INVARIANT — deterministic (same input → same output).

**AG11 specifically:** α validated in (0, 1). Split-half → α uses Spearman-Brown correctly.

### C.5 Trust Boundary (crci_harmonize/trust_boundary.py)

UNIT — all 11 parse rules handle their annotation types. Precision cascade L1–L6 with exact inflation factors. Implausible rejected (|β| > 5, SE ≤ 0, CI inverted). effect_size_type enforced (NULL → TB_REJECTION). Conversion validity hard gates enforced. INTEGRATION — Gate TB-G1: every output has non-null precision_level. INVARIANT — no LLM. Deterministic.

### C.6 Conversions (crci_harmonize/effect_convert.py)

UNIT — d from mean_diff, Hedges' g, OR → d, Fisher z ↔ r roundtrip, pre-post change d all match hand-calculations for 5+ test cases each. F → d BLOCKED when df_num ≠ 1. HR → d ALWAYS BLOCKED. Chained conversions BLOCKED. Median/IQR → mean/SD matches Wan et al. published examples. INVARIANT — no conversion produces NaN or Inf.

### C.7 Harmonization (crci_harmonize/harmonize.py)

Per substage: S1 rejects |β| > 5. S2 checks matrix preconditions. S3 scale harmonization verified. S4 flips known inverted scales. S5 identification assigned per design criteria. S6 scope match produces correct w_scope. S7 flags conflicting instrument versions. INTEGRATION — all 7 substages sequential, no data loss. INVARIANT — no substage modifies Layer 0.

### C.8 Seven-Layer SE Calibration (crci_calibration/seven_layer.py)

Per layer: UNIT — multiplier applied correctly, within expected ranges. INTEGRATION — SE_eff ≥ se_raw (inflation only; concordant triangulation 0.8× is sole exception). INVARIANT — monotonically increasing uncertainty (triangulation excepted).

### C.9 Compilation (crci_compile/)

**dcr.py:** UNIT — overlap_ratio correct. 3-tier decision applied at thresholds. Forest plot supersession works. INTEGRATION — Gate P4-G1 blocks unresolved overlaps.

**meta_analysis.py:** UNIT — IVW FE and RE (DL) match hand-calculations and metafor output. Egger's identifies known biased cases. Trim-and-fill adjusts correctly. INVARIANT — k < 3 → no meta-analysis attempted.

**compilers/*.py:** UNIT per compiler — output matches expected. Sample-size-weighted mean α (C1). NLLS exponential fit (C3).

**gap_analysis.py:** UNIT — sufficiency grading correct. Gap queries target correct workstream.

### C.10 Annotation and Intelligence (crci_store/, crci_intel/)

**annotation_reconcile.py:** UNIT — Jaccard clustering at 0.60 threshold. Confidence: min(1.0, 0.3 + 0.15×n + 0.2×mean_conf). HIGH contradiction → human_review_required. Singleton → confidence × 0.8. INTEGRATION — Gate P1-G4: contradiction rate < 30%.

**promotion.py:** UNIT — threshold → maturity = promoted. Written to target table. Archived → active = FALSE.

### C.11 Evidence Store Integrity (crci_store/)

**write_evidence.py:** UNIT — idempotent upsert. Layer write ownership enforced. FK integrity. INVARIANT — referential integrity. No NULL PKs. Version hash deterministic.

### C.12 Search and Saturation (crci_acq/)

**Saturation:** UNIT — overlap_ratio correct. Flag after 2 consecutive cycles > 0.80. Prevents new queries for that WS×edge. Other workstreams unaffected.

**Content-driven hops:** UNIT — 5 signal types detected. Hop depth ≤ 3 enforced. ≤ 20 targets per source paper.

---

## D. Cross-Cutting Invariants

These invariants must hold GLOBALLY across the entire system:

- **INV-01:** No LLM output touches any numeric value after Trust Boundary.
- **INV-02:** Every numeric value in Layer 1+ has a non-null provenance chain.
- **INV-03:** PaperMap is immutable after Canonical Reader completes.
- **INV-04:** AG09 (reconciliation) uses zero LLM calls.
- **INV-05:** Annotation reconciliation clustering uses Jaccard (deterministic).
- **INV-06:** Trust Boundary is deterministic: same input → same output.
- **INV-07:** Every study_id in edge_evidence_v1 exists in study_registry_v1.
- **INV-08:** Every instrument_id referenced exists in instruments_v1.
- **INV-09:** No paper is processed twice with different study_ids.
- **INV-10:** Budget controls cannot be exceeded — hard caps enforced.
- **INV-11:** Rate limits for external APIs never exceeded.
- **INV-12:** Within-group d never combined with between-group d in IVW.
- **INV-13:** Every study_id with retrieval_status ∈ {FULL_TEXT_PDF, FULL_TEXT_XML} has non-null pdf_path and canonical_text_path in study_registry_v1.
- **INV-14:** canonical_text persisted to disk and study_registry_v1 updated before any paper enters EX-P0.
- **INV-15:** paperscraper.pdf.save_pdf never called without AuditedRetriever wrapper (audit record on every attempt).
- **INV-16:** Every candidate in acquisition_queue_v1 has non-null retrieval_status and abstract_relevance before retrieval is attempted.

---

*End of CRCI Extraction System Engineering Appendix v2.0*
