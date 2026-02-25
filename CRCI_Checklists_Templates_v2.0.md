# CRCI — Extraction System Checklists and Templates v2.0

**Companion to:** CRCI Extraction System Master Specification v2.0
**Version 2.0 — February 2026**

This document contains the six manual CSV input templates with field validations and the four operational checklists. For behavioral specifications, see the Master Spec. For schemas, see the Engineering Appendix.

---

## T1. Manual Input CSV Templates

Six CSV templates for researcher manual data entry. Each template exposes ONLY Layer 0 fields appropriate to the workstream. Import scripts validate, assign UUIDs, and queue for Trust Boundary. All templates available at data/templates/*.csv. Import script: scripts/import_manual_csv.py.

### T1.1 edge_evidence_template.csv

**Columns:** doi, edge_id, beta_raw, se_raw, effect_type_original, effect_size_type, sample_size, study_design, cancer_type, treatment_phase, instrument_id, confidence_note.

**Validations:** edge_id must exist in edges_v1. effect_size_type must be one of {BETWEEN_GROUP, WITHIN_GROUP, PRE_POST_CHANGE}. beta_raw must be numeric. sample_size must be positive integer.

### T1.2 instrument_evidence_template.csv

**Columns:** doi, instrument_id, reliability_type, reliability_value, sample_size, population_descriptor, cancer_type_sample.

**Validations:** instrument_id must exist in instruments_v1. reliability_value must be in (0, 1). reliability_type must be one of {internal_consistency, test_retest, inter_rater, split_half}.

### T1.3 norms_template.csv

**Columns:** doi, node_id, instrument_id, mean, sd, sample_size, cancer_type, treatment_phase, age_range.

**Validations:** node_id must exist in nodes_v1. mean and sd must be numeric. sd > 0.

### T1.4 temporal_template.csv

**Columns:** doi, edge_id, timepoint_label, timepoint_weeks, value, se, sample_size, instrument_id.

**Validations:** timepoint_weeks must be numeric ≥ 0. Multiple rows per doi/edge_id expected (one per timepoint).

### T1.5 biomarker_template.csv

**Columns:** doi, biomarker_id_1, biomarker_id_2, correlation_r, sample_size, population, method.

**Validations:** correlation_r must be in (−1, 1).

### T1.6 modifier_template.csv

**Columns:** doi, edge_id, moderator_variable, subgroup_level, beta_subgroup, se_subgroup, sample_size_subgroup.

**Validations:** Multiple rows per doi/edge_id/moderator_variable expected (one per subgroup level).

---

## T2. Operational Checklists

These checklists prevent missed steps during batch operations. Each checklist is a HARD sequence — steps must be completed in order. Operators must confirm each step before proceeding.

### T2.1 Meta-Analysis Extraction Checklist

For each meta-analysis entering the pipeline:

- [ ] 1. Classify study_subtype: pairwise_ma | nma | ipdma | dose_response_ma | umbrella_review.
- [ ] 2. Extract pooled estimate(s). Record WHICH meta-analysis model was used (fixed-effect, random-effects DL, REML, Hartung-Knapp).
- [ ] 3. Record heterogeneity: I², τ², Q statistic, df, p_Q.
- [ ] 4. Extract forest plot per-study data → write with meta_source_flag = FOREST_PLOT_ENTRY.
- [ ] 5. Record included_study_ids_json and included_k.
- [ ] 6. Check: Is k ≥ 10? If yes → Egger's test is meaningful. If no → do NOT run Egger's (underpowered).
- [ ] 7. Extract subgroup analyses if present. Record moderator variable, subgroup estimates, interaction test.
- [ ] 8. Mine reference list → generate acquisition_queue entries for constituent primaries not yet in study_registry_v1.
- [ ] 9. For NMA: extract league table, check consistency (node-splitting p-values). Record NMA_MIXED vs NMA_DIRECT.
- [ ] 10. For umbrella review: BLOCK all numeric extraction. Extract AMSTAR-2 ratings of constituent MAs only.
- [ ] 11. Run DCR pre-check (Master Spec §7.3): flag if ≥1 constituent primary already in edge_evidence_v1 for this edge.
- [ ] 12. Assign annotations: research_gap, heterogeneity_source, limitation_unmeasured_confounder per Master Spec §8.1 yield profiles.

### T2.2 Acquisition Batch Checklist

Before launching an automated acquisition cycle:

- [ ] 1. Verify prerequisite tables loaded (Master Spec §2.1): nodes_v1, edges_v1, instruments_v1 present and non-empty.
- [ ] 2. Confirm current phase (Master Spec §9.2): which phases are active?
- [ ] 3. Review budget controls (Playbook §P2): remaining budget for this cycle (papers, API calls, LLM tokens).
- [ ] 4. Check saturation flags: which WS × edge combinations are already saturated? These must NOT generate new queries.
- [ ] 5. Confirm API keys configured: NCBI_API_KEY, Unpaywall email, Crossref polite pool User-Agent.
- [ ] 6. Verify retrieval cache is accessible and has sufficient disk space (estimate 500MB per 100 PDFs).
- [ ] 7. Review acquisition_queue_v1 for PAYWALL_BLOCKED items: have any been manually resolved since last cycle?
- [ ] 8. Set rate limits per Playbook §P2.
- [ ] 9. Launch cycle. Monitor for HTTP errors, rate limit hits, and deduplication rates.
- [ ] 10. Post-cycle: generate acquisition report. Count: new papers retrieved, duplicates skipped, paywall-blocked, abstract-only.

### T2.3 Extraction Batch Checklist

Before running extraction on a batch of papers:

- [ ] 1. Count papers in batch. Check against LLM token budget (Playbook §P2): batch_size × avg_tokens_per_paper ≤ remaining.
- [ ] 2. Verify all PDFs parseable: run EX-P0 S1 (PDF ingestion) first. Remove REJECTED papers from batch.
- [ ] 3. Confirm agent prompts are current version (check version hash against prompt_registry).
- [ ] 4. Set execution mode per paper: DEEP for APS ≥ 0.85, STANDARD for 0.50–0.84, SHALLOW for abstract-only.
- [ ] 5. Launch extraction. Monitor for: agent timeouts (>60s), malformed outputs, gate failures (Master Spec §11).
- [ ] 6. Post-extraction: run Gate P1-G6 batch check (escape hatch rate < 15%?). Review completeness reports.
- [ ] 7. Count provenance codes: how many PRESENT, PARTIAL, ABSENT_IN_PAPER, AGENT_MISS, PARSE_FAILURE?
- [ ] 8. If AGENT_MISS > 10% of expected extractions → investigate agent prompt issues before next batch.
- [ ] 9. Queue Trust Boundary for all extracted values.
- [ ] 10. Generate batch summary: papers processed, values extracted, annotations created, gate failures, human review items.

### T2.4 Verification Spot-Check Checklist

For Tier 2 (25–30%) and Tier 3 (10–15%) verification:

- [ ] 1. Select papers for spot-check using stratified random sampling: proportional to study_subtype distribution.
- [ ] 2. For each selected paper, independently re-extract 3 key fields (beta_raw, se_raw, sample_size) from source PDF.
- [ ] 3. Compare re-extraction against pipeline extraction. Discrepancy threshold: |Δ| > 0.05 for effect sizes, |Δ| > 10% for SE, |Δ| > 5% for sample sizes.
- [ ] 4. Discrepancy found → flag for full re-extraction. Log discrepancy type: transcription error, conversion error, table parsing error, wrong cell selected, sign error.
- [ ] 5. Calculate batch error rate. If > 5% of spot-checked values have discrepancies → HALT batch, investigate root cause.
- [ ] 6. For influence-aware escalation (Master Spec §8.3): check if any spot-checked paper triggers escalation conditions. If yes, apply Tier 1 (100%) verification to that paper.

---

*End of CRCI Extraction System Checklists and Templates v2.0*
