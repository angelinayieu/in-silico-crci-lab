# Quality Checklist — Per-Paper Verification

> Complete this checklist for every extracted paper before marking `VERIFIED`.

---

## Pre-Extraction Checks

- [ ] Paper DOI identified and normalized
- [ ] Extraction mode classified: DEEP / STANDARD / SHALLOW
- [ ] Existing extractions checked (no duplicate DOI in EXTRACTION_LOG)
- [ ] All edges in paper exist in EDGE_REGISTRY (or new edges added)
- [ ] All instruments in paper exist in INSTRUMENT_REGISTRY (or new ones added)
- [ ] Paper subfolder created: `data/manual_uploads/structured/<doi-slug>/`

---

## Edge Evidence Quality

- [ ] Every `edge_id` exists in `registries/EDGE_REGISTRY.csv`
- [ ] Every `instrument_id` exists in `registries/INSTRUMENT_REGISTRY.csv`
- [ ] `beta_raw` values verified against source table/figure in paper
- [ ] `se_raw` values either:
  - [ ] Directly reported (method = `reported`), OR
  - [ ] Derived with documented formula (see `03_SE_DERIVATION.md`)
- [ ] `se_derivation_method` column filled for every row
- [ ] `effect_type_original` accurately describes what the paper reports
- [ ] `effect_size_type` correct: BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE
- [ ] `sample_size` matches the analysis N (not enrollment N)
- [ ] `study_design` matches paper (RCT, cohort, etc.)
- [ ] `cancer_type` matches paper population
- [ ] `treatment_phase` matches paper timing
- [ ] For multi-arm trials: each arm vs control is a separate row
- [ ] No double-counting: shared controls flagged with `shared_control_flag`
- [ ] Sign convention documented in `confidence_note`

---

## Population Norms Quality

- [ ] All norms from **control group baseline** (not treatment group)
- [ ] `mean` and `sd` verified against source table
- [ ] `sd > 0` (no zero or negative SDs)
- [ ] `sample_size` = control group N (not total N)
- [ ] `node_id` correctly maps the instrument → construct

---

## Context Priors Quality

> **Note:** CSV `context_priors_template.csv` → DB table `node_priors_v1` (NOT `context_priors_v1`)

- [ ] z-scores calculated correctly: `z = (observed - norm_mean) / norm_SD`
- [ ] Population norms referenced and documented in `notes`
- [ ] `prior_sd_z` set to 0.5 (default) unless strong justification
- [ ] `source_type` correct: published_norm / local_control_group / expert

---

## Extended Templates Quality (When Filled)

### Dose Evidence
- [ ] `action_id` exists in `action_catalog_v1`
- [ ] `dose_level` and `dose_unit` are consistent and documented
- [ ] `effect` and `se` verified against paper
- [ ] `dose_response_shape` documented if multiple dose levels

### Subgroup Evidence
- [ ] `edge_id` exists in EDGE_REGISTRY
- [ ] `modifier_variable` clearly defined (e.g., APOE_status, age_group)
- [ ] Either `interaction_beta`+`interaction_se` OR `subgroup_effect`+`subgroup_se` filled
- [ ] `subgroup_n` verified

### Correlation Evidence
> **Note:** CSV `correlation_template.csv` → DB table `biomarker_correlations_v1` (NOT `correlation_evidence_v1`)
- [ ] `biomarker_id_1` and `biomarker_id_2` are valid node IDs
- [ ] `correlation_r` within [-1, 1]
- [ ] `partial_or_zero` correctly classified

---

## Extraction Decisions

- [ ] Every non-trivial judgment documented as a decision row
- [ ] Each decision has: category, risk level, rationale, spec reference
- [ ] MEDIUM-risk decisions flagged for human review
- [ ] HIGH-risk decisions block extraction until resolved

---

## Registry Updates

- [ ] Any new edges added to `registries/EDGE_REGISTRY.csv`
- [ ] Any new instruments added to `registries/INSTRUMENT_REGISTRY.csv`
- [ ] New entries have all required columns filled
- [ ] New edge IDs follow naming convention: `ER_{SOURCE}_{TARGET}`
- [ ] New instrument IDs follow convention: `INST_{ABBREVIATION}`

---

## meta.json Completeness

- [ ] `doi` matches CSV files
- [ ] `study_design` matches CSV `study_design`
- [ ] `cancer_type` matches CSV `cancer_type`
- [ ] `treatment_phase` matches CSV `treatment_phase`
- [ ] `n_total`, `n_treatment`, `n_control` filled
- [ ] `extraction_mode` = DEEP/STANDARD/SHALLOW
- [ ] `targeted_edges` lists all edge_ids extracted
- [ ] `risk_of_bias` object complete (7 domains + overall)

---

## Post-Load Verification

After running `python scripts/load_evidence_into_db.py`:

- [ ] Row counts match expectations
- [ ] `python scripts/report_status.py` shows updated counts
- [ ] No orphaned edge_ids (all reference valid edge_relations_definitions_v1)
- [ ] No orphaned instrument_ids (all reference valid instrument_definitions_v1)

---

## EXTRACTION_LOG Entry

- [ ] New entry added at top of `extraction_ref/EXTRACTION_LOG.md`
- [ ] Extraction ID assigned: `EXT-{YEAR}-{NNNN}`
- [ ] All evidence tables included
- [ ] All decisions documented with risk levels
- [ ] Verification checklist included
- [ ] Files created listed with locations

---

## Sign-Off

| Field | Value |
|-------|-------|
| Extraction ID | `EXT-____-____` |
| Extractor | |
| Reviewer | |
| Date Extracted | |
| Date Verified | |
| Status | `EXTRACTED` / `VERIFIED` / `INTEGRATED` |
