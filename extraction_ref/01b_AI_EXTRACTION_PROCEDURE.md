# AI Extraction Procedure

> Systematic protocol for AI-assisted evidence extraction from CRCI research papers.
> This document governs what the AI does during a chatbox extraction session.
> For the human operator's guide, see `01_PROCEDURE.md`.

---

## Extraction Workflow

```
INPUT:  Paper text (PDF or pasted full text)
OUTPUT: Structured CSV data + extraction decisions + meta.json
```

### Phase 1 — Classify

1. Read abstract + methods
2. Determine extraction mode:
   - **DEEP:** RCT + cancer population + cognitive primary outcome → all 12 templates
   - **STANDARD:** Cohort/observational + cognitive outcomes → 6 core templates
   - **SHALLOW:** Case report / animal / biomarker-only → edge_evidence only
3. State the classification with justification

### Phase 2 — Registry Validation

**Before extracting ANY data, check every entity:**

| Entity | Registry File | Action if Missing |
|--------|--------------|-------------------|
| Causal edges | `09_EDGE_IDS.md` | STOP — flag for registry addition |
| Cognitive instruments | `10_INSTRUMENT_IDS.md` | STOP — flag for registry addition |
| Nodes/constructs | `08_NODE_IDS.md` | STOP — flag as REVIEW_TASK |

Report: "Registry check: X edges found, Y instruments found, Z new entities flagged."

### Phase 3 — Extract Evidence

For each evidence family, produce a **markdown table** with exact CSV column headers.

**Extraction order:**
1. `edge_evidence` (REQUIRED — always extract)
2. `population_norms` (extract if control group baselines available)
3. `context_priors` (derive from population norms + published norms)
4. `temporal_evidence` (if ≥2 longitudinal timepoints)
5. `instrument_evidence` (if psychometric properties reported)
6. `correlation` (if inter-domain correlations reported)
7. `dose_evidence` (if dose-response data available)
8. `subgroup_evidence` (if subgroup/interaction analyses reported)
9. `study_cohort_profile` (DEEP mode — detailed demographics)

### Phase 4 — Document Decisions

For **every non-trivial judgment**, create a decision row:

| Field | Description |
|-------|------------|
| Category | `[INST_MAP]` / `[SIGN_CONV]` / `[MISSING_DATA]` / `[BIAS_ADJ]` / `[CONSTRUCT]` / `[DUPLICATE]` |
| Risk Level | `LOW` / `MEDIUM` / `HIGH` |
| Decision | What was decided |
| Rationale | Why |
| Spec Reference | Which formula, rule, or registry entry justifies it |

### Phase 5 — Quality Check

Apply `11_QUALITY_CHECKLIST.md`. State which checks pass and which have issues.

### Phase 6 — Output

Produce the final output package (see §Output Format below).

---

## Evidence Extraction Rules

### Rule 1: Edge Evidence (edge_evidence_template.csv → `edge_evidence_v1`)

**One row per causal/associational relationship reported.**

Required fields for every row:

| Field | Rule |
|-------|------|
| `doi` | Exact DOI of the paper |
| `edge_id` | Must exist in EDGE_REGISTRY — use exact ID from `09_EDGE_IDS.md` |
| `beta_raw` | Standardized effect size. Prefer Cohen's d. Convert if needed. |
| `se_raw` | Standard error. Derive if not reported (see §SE Derivation Priority). |
| `effect_type_original` | What the paper ACTUALLY reports: cohens_d / mean_diff / odds_ratio / correlation_r / eta_squared / regression_beta / standardized_beta |
| `effect_size_type` | BETWEEN_GROUP / WITHIN_GROUP / PRE_POST_CHANGE |
| `sample_size` | N used in the ANALYSIS (not enrollment N) |
| `study_design` | RCT / crossover_RCT / cohort / case_control / cross_sectional |
| `cancer_type` | breast / colorectal / lung / prostate / hematological / gynecological / head_neck / brain_cns / pediatric_survivor / mixed / other |
| `treatment_phase` | pre_treatment / active_treatment / early_recovery / late_recovery / long_term_survivorship |
| `instrument_id` | Must exist in INSTRUMENT_REGISTRY — use exact ID from `10_INSTRUMENT_IDS.md` |
| `se_derivation_method` | reported / from_ci / from_p_value / from_t_stat / from_f_stat / from_sd_n / fallback_4_over_n |

**Multi-arm trials:** One row per arm vs. control. Set `shared_control_flag = true`.

### Rule 2: Population Norms (population_norms_template.csv → `population_norms_v1`)

**One row per instrument × node at baseline for the control/reference group.**

| Field | Rule |
|-------|------|
| `mean` | Control group BASELINE mean (not post-treatment) |
| `sd` | Must be SD (not SE). Must be > 0. |
| `sample_size` | Control group N (not total N) |

### Rule 3: Context Priors (context_priors_template.csv → **`node_priors_v1`**)

**z-scores derived from population norms:**
```
z = (observed_mean - population_mean) / population_SD
```

| Field | Rule |
|-------|------|
| `prior_mean_z` | Computed z-score |
| `prior_sd_z` | Default 0.5 (unless strong justification) |
| `source_type` | `published_norm` if using published reference norms; `local_control_group` if using study control group |

### Rule 4: Temporal Evidence (temporal_evidence_template.csv → `temporal_evidence_v1`)

**One row per edge × timepoint.** Only when ≥2 timepoints available.

| Field | Rule |
|-------|------|
| `timepoint_weeks` | Weeks from baseline (baseline = 0) |
| `is_recovery` | 0 if during intervention, 1 if post-intervention follow-up |

### Rule 5: Instrument Evidence (instrument_evidence_template.csv → `instrument_evidence_v1`)

**One row per instrument with psychometric data.**

| Field | Rule |
|-------|------|
| `reliability_type` | cronbachs_alpha / split_half / test_retest |
| `cancer_validated` | true only if psychometric data is FROM a cancer sample |

### Rule 6: Correlations (correlation_template.csv → **`biomarker_correlations_v1`**)

**One row per pair of correlated domains.** Use node IDs for both biomarker fields.

| Field | Rule |
|-------|------|
| `correlation_r` | Must be in [-1, 1]. Report as-is from paper. |
| `partial_or_zero` | `zero_order` for bivariate; `partial` if covariates controlled |

### Rule 7: Dose Evidence (dose_evidence_template.csv → `dose_evidence_v1`)

**One row per dose level.** Only when paper reports multiple dose levels or dose-response curves.

### Rule 8: Subgroup Evidence (subgroup_evidence_template.csv → `subgroup_evidence_v1`)

**One row per subgroup × modifier combination.** Only when paper reports subgroup-specific effects.

### Rule 9: Cohort Profile (study_cohort_profile_template.csv → `study_cohort_profiles_v1`)

**One row per cohort arm** (treatment, control, etc.). DEEP mode only.

---

## SE Derivation Priority

When SE is not directly reported, derive in this order:

| Priority | Method | Formula | `se_derivation_method` |
|----------|--------|---------|----------------------|
| 1 | Reported directly | — | `reported` |
| 2 | From 95% CI | SE = (CI_upper − CI_lower) / (2 × 1.96) | `from_ci` |
| 3 | From exact p-value | z = −Φ⁻¹(p/2); SE = \|effect\| / z | `from_p_value` |
| 4 | From t-statistic | SE = effect / t | `from_t_stat` |
| 5 | From F(1,df) | SE = effect / √F | `from_f_stat` |
| 6 | From SD + N | SE(d) = √((n₁+n₂)/(n₁×n₂) + d²/(2(n₁+n₂))) | `from_sd_n` |
| 7 | Fallback | SE(d) ≈ √(4/N) | `fallback_4_over_n` |

**Always document** in `confidence_note`: which formula, what raw values, any assumptions.

---

## Effect Size Conversion Rules

When the paper doesn't report Cohen's d, convert:

| From | To Cohen's d | Formula |
|------|-------------|---------|
| Group means ± SD | d | d = (M₁ − M₂) / SD_pooled |
| t-statistic | d | d = 2t / √(df) |
| F(1,df) | d | d = 2√(F/N) |
| Odds ratio | d | d = ln(OR) × √3 / π |
| Correlation r | d | d = 2r / √(1 − r²) |
| η² (eta-squared) | d | d = 2√(η² / (1 − η²)) |
| Raw mean difference | d | d = mean_diff / SD_pooled |

Record the **original** value in `effect_type_original` and the **converted** d in `beta_raw`.

---

## Sign Convention

| Principle | Rule |
|-----------|------|
| Positive beta = improvement | Higher cognition, lower symptoms |
| Lower-is-better instruments | Still use positive d when intervention helps (fewer TMT seconds = better) |
| What to report | The PAPER's reported sign |
| Where to document | `confidence_note` column |
| What handles alignment | Pipeline uses `scoring_direction` from INSTRUMENT_REGISTRY |

**When in doubt:** Report the paper's sign, note it in `confidence_note`, and let the pipeline harmonize.

---

## Output Format

The AI must produce ALL of the following for each paper:

### A. Paper Classification

```markdown
**Mode:** DEEP / STANDARD / SHALLOW
**Justification:** [why this mode]
**Study design:** [RCT / cohort / etc.]
**Cancer type:** [breast / mixed / etc.]
**N total:** [number]
```

### B. Registry Check Report

```markdown
**Edges found:** [list edge_ids]
**Instruments found:** [list instrument_ids]
**New entities flagged:** [list any, or "None"]
```

### C. Evidence Tables

One markdown table per CSV template filled, using **exact column headers** from `06_CSV_TEMPLATES.md`:

```markdown
#### edge_evidence_template.csv → edge_evidence_v1
| doi | edge_id | beta_raw | se_raw | effect_type_original | ... |
|-----|---------|----------|--------|---------------------|-----|

#### population_norms_template.csv → population_norms_v1
| doi | node_id | instrument_id | mean | sd | sample_size | ... |
|-----|---------|---------------|------|----|-----------| ... |

[... additional templates as applicable ...]
```

### D. Extraction Decisions

```markdown
| # | Category | Risk | Decision | Rationale |
|---|----------|------|----------|-----------|
| 1 | [INST_MAP] | LOW | Mapped TMT-A → INST_TMTA | Direct match |
| 2 | [MISSING_DATA] | MEDIUM | SE derived from CI | SE not reported directly |
```

### E. What Could NOT Be Extracted

```markdown
**Missing temporal data:** [explain]
**Unreported SEs:** [explain]
**Ambiguous constructs:** [explain]
```

### F. meta.json

Complete JSON object matching the schema in `01_PROCEDURE.md` §Step 6.

### G. Verification Summary

```markdown
- [ ] All edge_ids exist in EDGE_REGISTRY
- [ ] All instrument_ids exist in INSTRUMENT_REGISTRY
- [ ] All beta_raw values verified against paper
- [ ] All se_raw values documented with derivation method
- [ ] Sign convention documented
- [ ] No double-counting (shared controls flagged)
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Edge not in registry | STOP. Report: "Edge [X→Y] not in EDGE_REGISTRY. Suggest adding: ER_{SOURCE}_{TARGET}" |
| Instrument not in registry | STOP. Report: "Instrument [name] not in INSTRUMENT_REGISTRY. Suggest adding: INST_{ABBREV}" |
| Node not in registry | Flag as REVIEW_TASK. Do NOT invent node IDs. |
| Ambiguous construct mapping | Report both options. Set risk = HIGH. Let human decide. |
| Cannot derive SE by any method | Set `se_raw = √(4/N)` with `se_derivation_method = fallback_4_over_n`. Note in `confidence_note`. |
| Effect direction unclear | Report paper's sign. Note ambiguity in `confidence_note`. |
| Data from figure (not table) | Extract best estimate. Note "estimated from Figure X" in `confidence_note`. |

---

## Table Name Mapping Warnings

These CSV template names do NOT match their DB table names:

| CSV Template | DB Table | Common Mistake |
|-------------|----------|---------------|
| `context_priors_template.csv` | **`node_priors_v1`** | ~~context_priors_v1~~ |
| `correlation_template.csv` | **`biomarker_correlations_v1`** | ~~correlation_evidence_v1~~ |

All other templates → DB tables follow the pattern `{template_name}_v1`.

---

## Cross-References

| For... | See... |
|--------|--------|
| Full column specs (all 12 templates) | `06_CSV_TEMPLATES.md` |
| SE derivation decision tree | `03_SE_DERIVATION.md` |
| All enum values | `04_CONTROLLED_VOCAB.md` |
| Node IDs (63) | `08_NODE_IDS.md` |
| Edge IDs (~143) | `09_EDGE_IDS.md` |
| Instrument IDs (67) | `10_INSTRUMENT_IDS.md` |
| CSV → DB column mapping | `07_CSV_TO_DB_MAP.md` |
| Quality checklist | `11_QUALITY_CHECKLIST.md` |
| All 83 DB tables | `12_TABLE_FILL_MASTER.md` |
