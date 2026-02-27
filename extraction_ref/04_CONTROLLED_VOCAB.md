# Controlled Vocabulary

> All enum values and naming conventions used in extraction CSVs and the database.

---

## study_design

| Value | Use When |
|-------|----------|
| `RCT` | Randomized controlled trial |
| `crossover_RCT` | Randomized crossover design |
| `cohort` | Prospective or retrospective cohort |
| `case_control` | Case-control design |
| `cross_sectional` | Cross-sectional / one-time assessment |
| `systematic_review` | Systematic review (qualitative) |
| `meta_analysis` | Quantitative meta-analysis |

---

## cancer_type

| Value | Includes |
|-------|----------|
| `breast` | All breast cancer subtypes |
| `colorectal` | Colon, rectal |
| `lung` | NSCLC, SCLC |
| `prostate` | Prostate cancer |
| `hematological` | Leukemia, lymphoma, myeloma |
| `gynecological` | Ovarian, cervical, uterine |
| `head_neck` | Head and neck cancers |
| `brain_cns` | Primary brain tumors, CNS |
| `pediatric_survivor` | Childhood cancer survivors |
| `other` | Specific type not listed |
| `mixed` | Multi-cancer-type cohort |

---

## treatment_phase

| Value | Definition |
|-------|-----------|
| `pre_treatment` | Before any cancer treatment begins |
| `active_treatment` | During chemotherapy, radiation, or surgery |
| `early_recovery` | 0–12 months post-treatment completion |
| `late_recovery` | 12–36 months post-treatment |
| `long_term_survivorship` | >36 months post-treatment |

---

## effect_size_type

| Value | Meaning |
|-------|---------|
| `BETWEEN_GROUP` | Difference between treatment and control groups |
| `WITHIN_GROUP` | Change within a single group (pre-post) |
| `PRE_POST_CHANGE` | Pre-post change score comparison between groups |

---

## effect_type_original

What the paper actually reports (before conversion):

| Value | Description |
|-------|-------------|
| `cohens_d` | Cohen's d or Hedges' g |
| `mean_diff` | Raw mean difference |
| `mean_diff_seconds` | Time-based mean difference (e.g., TMT) |
| `mean_diff_words` | Count-based mean difference (e.g., fluency) |
| `mean_diff_raw_score` | Generic raw score difference |
| `odds_ratio` | Odds ratio |
| `hazard_ratio` | Hazard ratio |
| `correlation_r` | Pearson/Spearman r |
| `eta_squared` | η² from ANOVA |
| `regression_beta` | Unstandardized regression β |
| `standardized_beta` | Standardized regression β |

---

## relation_type

| Value | Meaning |
|-------|---------|
| `causal` | Directed causal relationship (RCT-supported or strong theory) |
| `associational` | Observed association (correlation, observational) |
| `mechanistic` | Supported by biological mechanism, limited direct evidence |

---

## rob_overall (Risk of Bias)

| Value | Meaning |
|-------|---------|
| `low` | Low risk across all domains |
| `moderate` | Some concerns in 1-2 domains |
| `high` | High risk in ≥1 domain |
| `critical` | Fatal flaws |

---

## extraction_mode

| Value | Triggers | Templates |
|-------|----------|-----------|
| `DEEP` | RCT + cancer + cognitive primary outcome | All 6 templates |
| `STANDARD` | Cohort/observational + cognitive outcomes | edge_evidence + population_norms + context_priors |
| `SHALLOW` | Case report / animal / biomarker-only | edge_evidence only |

---

## expected_sign (Edge Registry)

| Value | Meaning |
|-------|---------|
| `positive` | Higher source → higher target (both beneficial) |
| `negative` | Higher source → lower target (inverse relationship) |
| `context_dependent` | Direction depends on context or dosage |

---

## scoring_direction (Instrument Registry)

| Value | Example Instruments |
|-------|-------------------|
| `higher_better` | HVLT-R, Digit Span, MoCA, FACT-Cog PCI |
| `lower_better` | TMT-A, TMT-B, BFI, PHQ-9, CES-D |

---

## ID Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Node | `NODE_{LAYER}_{CONCEPT}` | `NODE_COG_WORK_MEM` |
| Edge | `ER_{SOURCE}_{TARGET}` | `ER_ACTIVITY_EPIMEM` |
| Instrument | `INST_{ABBREVIATION}` | `INST_HVLTR` |
| Measure | `MEAS_{ANALYTE}_{METHOD}` | `MEAS_IL6_PLASMA` |
| Pathway | `PW_{CODE}_{NAME}` | `PW_M04_NEUROPLASTICITY` |
| Study | `STU_{DOI_SLUG}` | `STU_10.1016_j.lfs.2013.08.011` |
| Extraction | `EXT-{YEAR}-{NNNN}` | `EXT-2026-0001` |

### Node Layer Prefixes

| Prefix | Layer | Layer # |
|--------|-------|---------|
| `EXO_` | Exogenous / Treatment | 0 |
| `BEH_` | Behavioral Interventions | 1 |
| `BIO_` | Biomarkers | 2 |
| `PATH_` | Biological Pathways | 3 |
| `SYM_` | Symptom Clusters | 4 |
| `COG_` | Cognitive Domains | 5 |
| `COMP_` | Composite Scores | 6 |

---

## Sign Convention Rules

1. **Positive beta** = outcome improves (cognition increases, symptoms decrease)
2. If instrument is "lower is better" (e.g., TMT seconds), positive d still means benefit
3. Report the **paper's** sign, document in `confidence_note`
4. The pipeline handles alignment via `scoring_direction` in INSTRUMENT_REGISTRY

---

## Extraction Decision Categories

| Code | Meaning |
|------|---------|
| `[INST_MAP]` | Instrument/measure mapped to registry ID |
| `[SIGN_CONV]` | Sign or directionality decision |
| `[MISSING_DATA]` | Handling absent or incomplete data |
| `[BIAS_ADJ]` | Quality or bias adjustment |
| `[CONSTRUCT]` | Construct validity or node mapping |
| `[DUPLICATE]` | Avoiding double-counting |

## Risk Levels

| Level | Meaning | Action |
|-------|---------|--------|
| `LOW` | Standard mapping, unlikely to affect results | None |
| `MEDIUM` | Approximation or workaround | Flag for review |
| `HIGH` | Significant uncertainty | Block until resolved |
