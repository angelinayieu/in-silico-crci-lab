# CRCI Vertical Slice — Extraction Output Schemas

**Purpose:** Single-source-of-truth schema definitions for ALL data outputs across
the deep research → triage → gold extraction → aggregation pipeline. Every prompt
in `VERTICAL_SLICE_PROMPTS.md` produces output conforming to one of these schemas.

**Key principle:** Every extracted number must carry provenance (where in the paper it
came from), conversion audit trail (how it was transformed), and confidence rating.

---

## Schema 1: `candidate_papers_v1` (Discovery/Triage Layer)

Used by: VS-1.0, VS-1.2, VS-1.3, VS-1.4, VS-1.5 output  
Format: YAML array  
Purpose: Screen and prioritize papers BEFORE full extraction

```yaml
# === Per-paper record ===
- paper_key: "cheung_2015_annoncol"           # stable: first_author_year_journal_short
  citation: "Cheung YT, et al. Ann Oncol. 2015;26(7):1446-1451."
  doi: "10.1093/annonc/mdv171"
  pmid: "25922063"
  url: "https://pubmed.ncbi.nlm.nih.gov/25922063/"

  study_type: cohort                           # ENUM: RCT | cohort | cross_sectional | meta_analysis | SR | methods
  cancer_types: [BCA]                          # ENUM: BCA | CRC | HEM | LNG | PRS | HNC | GYN | PED | CNS | mixed | non_cancer
  regimen_tags: [anthracycline, taxane]        # freeform tags for chemo regimen
  regimen_phase_coverage:
    phases: [T0, T1, T2]                       # ENUM: T0 (pre-tx) | T1 (on-tx) | T2 (end-tx/early recovery 0-6mo) | T3 (late recovery 6-24mo) | T4 (long-term >24mo)
    timepoints_detail: "Baseline, cycle 4, 1 month post-chemo"

  sample:
    N_total: 136
    N_groups:                                  # null if single-group
      chemo: 74
      control: 62
    age_mean_sd: "49.2 ± 8.1"
    sex_pct_female: 100.0

  measures_present:
    biomarkers: [IL6, CRP, TNF]                # Use short codes: IL6 | CRP | TNF | BDNF_plasma | BDNF_serum | cortisol_slope | cortisol_CAR | cortisol_AUC | DHEAS | NfL | p16 | GH2AX | MDA | 8OHdG | glucose | Shannon
    cognition_domains: [memory, proc_speed, attention]   # ENUM per Node Registry L5: memory | proc_speed | attention | working_mem | verbal_fluency | exec_planning | exec_inhibition | visuospatial | language | subjective
    instruments: [HVLT-R, TMT-A, TMT-B, DSST, FACT-Cog PCI]
    sleep_instruments: []
    activity_instruments: []

  extractability:
    stats_types: [regression_table, means_SD]  # ENUM: regression_table | correlations | corr_matrix | means_SD | mediation | mixed_model | forest_plot | group_comparison | path_analysis
    uncertainty_present: explicit_SE_CI         # ENUM: explicit_SE_CI | p_only | none
    correlation_matrix_present: false
    timepoints_count: 3
    practice_effects_addressed: false           # null if not applicable
    within_subject: true                        # repeated measures on same patients?

  edges_supported:
    edge_ids:                                  # list of ER_* IDs this paper can populate
      - ER_OIC_PROCSPEED
      - ER_OIC_EPISODIC
      - ER_OIC_ATTNSUST
    r_class_coverage: [R2, R3]                 # what level of evidence it provides

  value_flags:
    multi_edge_yield_est: 3                    # how many edges extractable
    longitudinal_value: 3tp                    # ENUM: none | 2tp | 3tp_plus
    multi_cancer_value: false
    subgroup_modifier_value: false
    correlation_matrix_value: false             # has inter-biomarker corr matrix?
    mediation_value: false                      # has formal mediation analysis?

  temporal:                                    # trajectory-relevant metadata
    phase_transitions_covered: [T0_T1, T1_T2]  # which phase transitions have data
    mixed_model_reported: false                 # reports time coefficients?
    trajectory_classes_reported: false           # latent class trajectory analysis?

  notes:
    key_findings: "IL-1β and TNF-α increased during chemo; IL-1β associated with processing speed decline"
    extraction_cues: "Table 2 has regression β for cytokines→cognitive domains with 95% CI. Table 3 has means±SD at each timepoint."
    risks: "Small sample per arm; serum not plasma for some markers; no correction for practice effects"

  priority_score: 0.0                          # computed during triage (VS-1.1)
  triage_bin: null                             # A | B | C (filled during triage)
```

### Mandatory Fields (must be non-null)
- `paper_key`, `citation`, `study_type`, `cancer_types`
- `sample.N_total`
- `measures_present.biomarkers` AND `measures_present.cognition_domains`
- `extractability.stats_types`, `extractability.uncertainty_present`
- `edges_supported.edge_ids`
- `value_flags.multi_edge_yield_est`

### Derivation Rules for `priority_score` (VS-1.1 triage)
```
priority_score = 3 × multi_edge_yield_est
               + 2 × longitudinal_bonus           # 0=none, 1=2tp, 3=3tp+
               + 2 × correlation_matrix_value      # 0 or 1
               + 1 × multi_cancer_value            # 0 or 1
               + 1 × mediation_value               # 0 or 1
               + 1 × subgroup_modifier_value       # 0 or 1
               - 2 × uncertainty_missing_penalty   # 1 if uncertainty=none, else 0
               - 1 × breast_only_penalty           # 1 if cancer_types=[BCA] only
```

---

## Schema 2: `study_profiles_v1` (Gold Extraction — Study Level)

Used by: VS-2.1, VS-3.0  
Format: CSV (one row per paper)  
Purpose: Structured metadata for each fully extracted paper

### Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `study_id` | string | YES | Auto-derived: `doi_slug` or `first_author_year` |
| `paper_key` | string | YES | Matches `candidate_papers_v1.paper_key` |
| `citation` | string | YES | Full formatted citation |
| `doi` | string | no | DOI if available |
| `pmid` | string | no | PubMed ID if available |
| `design_class` | enum | YES | `RCT` / `cohort` / `cross_sectional` / `meta_analysis` |
| `cancer_types` | string | YES | Comma-separated cancer type codes |
| `regimen_tags` | string | no | Comma-separated regimen tags |
| `N_total` | int | YES | Total sample size |
| `N_per_group` | string | no | JSON: `{"intervention": 50, "control": 48}` |
| `age_mean` | float | no | Mean age |
| `age_sd` | float | no | SD of age |
| `pct_female` | float | no | Percent female |
| `phases_measured` | string | YES | Comma-separated: `T0,T1,T2` |
| `timepoints_detail` | string | no | Human-readable timepoint descriptions |
| `instruments_biomarker` | string | no | Comma-separated instrument IDs |
| `instruments_cognition` | string | no | Comma-separated instrument IDs |
| `instruments_sleep` | string | no | Comma-separated instrument IDs |
| `instruments_activity` | string | no | Comma-separated instrument IDs |
| `instruments_subjective` | string | no | Comma-separated instrument IDs |
| `practice_effects_addressed` | bool | no | Whether alternate forms or correction used |
| `grade_quality` | enum | YES | `high` / `moderate` / `low` / `very_low` |
| `bias_notes` | string | no | Specific biases identified |
| `extraction_mode` | enum | YES | `DEEP` / `STANDARD` / `SHALLOW` |

---

## Schema 3: `edge_evidence_v1` (Gold Extraction — Per-Effect)

Used by: VS-2.1, VS-3.0  
Format: CSV (one row per extracted estimand per edge per study)  
Purpose: The core evidence table that feeds into IVW aggregation

### Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| **Identity** | | | |
| `evidence_id` | string | YES | `{study_id}__{edge_id}__{seq}` e.g. `cheung_2015__ER_OIC_PROCSPEED__01` |
| `study_id` | string | YES | FK to `study_profiles_v1.study_id` |
| `paper_key` | string | YES | Human-readable paper key |
| `edge_relation_id` | string | YES | FK to `EDGE_REGISTRY.edge_relation_id` |
| `source_node_id` | string | YES | FK to `NODE_REGISTRY.node_id` |
| `target_node_id` | string | YES | FK to `NODE_REGISTRY.node_id` |
| `r_class` | enum | YES | `R0` / `R1` / `R2` / `R3` / `AGG` / `structural` |
| **Temporal** | | | |
| `estimand_type` | enum | YES | `level` / `change` / `slope` / `lagged` / `mediation_indirect` / `mediation_direct` |
| `phase_at_measurement` | enum | cond. | Required if `estimand_type=level`; e.g. `T2` |
| `phase_from` | enum | cond. | Required if `estimand_type` ∈ {change, lagged}; e.g. `T0` |
| `phase_to` | enum | cond. | Required if `estimand_type` ∈ {change, lagged}; e.g. `T2` |
| `delta_t_days` | float | no | Actual time between measurements if reported |
| `within_subject` | bool | YES | `true` for repeated-measures; `false` for between-group |
| **Reported Values** | | | |
| `effect_metric` | enum | YES | `beta` / `r` / `d` / `OR` / `HR` / `mean_diff` / `corr_matrix_entry` / `partial_r` / `eta_sq` |
| `effect_value` | float | YES | The reported numeric value |
| `uncertainty_type` | enum | YES | `SE` / `CI95` / `p` / `none` |
| `se_reported` | float | cond. | If `uncertainty_type=SE` |
| `ci95_low` | float | cond. | If `uncertainty_type=CI95` |
| `ci95_high` | float | cond. | If `uncertainty_type=CI95` |
| `p_value` | float | cond. | If `uncertainty_type=p` |
| `N_effect` | int | YES | Sample size for this specific effect |
| `covariates_adjusted` | string | no | Comma-separated list of adjusted covariates |
| **Standardized (Converted)** | | | |
| `target_metric` | enum | YES | `SMD_d` (default for causal) or `FisherZ_r` (for loadings) |
| `d_value` | float | YES | Converted standardized mean difference |
| `d_se` | float | YES | SE of converted d |
| `conversion_method` | enum | YES | `direct` / `r_to_d` / `OR_to_d` / `CI_to_SE` / `p_to_SE` / `means_to_d` / `beta_to_d` / `eta_to_d` |
| `conversion_inputs` | string | YES | JSON string of inputs used: `{"r": 0.32, "N": 136}` |
| `conversion_steps` | int | YES | Number of conversion steps (0 if direct) |
| `se_conversion_penalty` | float | YES | 1.1^conversion_steps |
| **Orientation** | | | |
| `sign_convention_source` | string | YES | E.g. "Higher PSQI = worse sleep; higher TMT-B seconds = slower" |
| `sign_convention_target` | string | YES | E.g. "POS_UP: higher = better cognition" |
| `sign_applied` | enum | YES | `as_reported` / `flipped` |
| `sign_flip_reason` | string | cond. | Only if `sign_applied=flipped`; explain why |
| **Evidence Grading** | | | |
| `claim_level` | enum | YES | `causal_supported` / `associational_only` / `model_implied` |
| `identification_status` | enum | YES | `identified` / `partially_identified` / `plausible` / `unidentified` |
| `population_match` | int | YES | 1–8 scale (8=exact cancer+phase match; 1=general population) |
| `outcome_alignment` | int | YES | 1–8 scale (8=exact instrument+domain; 1=rough proxy) |
| `grade_quality` | enum | YES | `high` / `moderate` / `low` / `very_low` (per GRADE) |
| **Provenance** | | | |
| `source_section` | enum | YES | `Table` / `Figure` / `Results_text` / `Supplement` / `Abstract` |
| `locator_text` | string | YES | E.g. "Table 2, row 'IL-6 (log)', column 'TMT-A β (95% CI)'" |
| `page_or_elocator` | string | no | Page number or eLocator |
| `verbatim_snippet` | string | YES | ≤25 words from paper: "β = −0.23 (95% CI: −0.41, −0.05) for log IL-6 predicting TMT-A" |
| `extraction_confidence` | enum | YES | `high` (stat+uncertainty in same row) / `medium` (derived uncertainty) / `low` (narrative only) |
| **Notes** | | | |
| `notes` | string | no | Free text for any extraction issues |

### Derivation Integrity Checks (automated)
For every row, verify:
1. `d_se > 0`
2. `|d_value| < 5.0` (flag if exceeded — not necessarily wrong but verify)
3. `sign_applied` is consistent with source/target orientation in Node Registry
4. `N_effect ≥ 30` (minimum per inclusion criteria)
5. If `conversion_method != direct`, then `conversion_inputs` is non-empty
6. `se_conversion_penalty == 1.1 ^ conversion_steps`

---

## Schema 4: `biomarker_corr_matrix_v1` (D-Matrix Input)

Used by: VS-1.3, VS-3.0  
Format: CSV  
Purpose: Populate the 3×3 correlation matrix for the OIC latent variable

### Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `corr_id` | string | YES | `{study_id}__{biom_a}__{biom_b}` |
| `study_id` | string | YES | FK to `study_profiles_v1` |
| `paper_key` | string | YES | Human-readable |
| `biomarker_a` | enum | YES | `IL6` / `CRP` / `TNF` / `BDNF` / `cortisol` |
| `biomarker_b` | enum | YES | Same enum |
| `corr_r` | float | YES | Pearson r (or Spearman ρ, note in method) |
| `corr_method` | enum | YES | `pearson` / `spearman` / `partial` |
| `N` | int | YES | Sample size |
| `phase` | enum | no | `T0` / `T1` / `T2` / `T3` / `T4` / `pooled` |
| `cancer_types` | string | no | Comma-separated |
| `log_transformed` | bool | no | Whether biomarkers were log-transformed |
| `provenance_locator` | string | YES | Table/figure reference |
| `notes` | string | no | |

### Required Pairs for Slice 1
- IL-6 ↔ CRP (expected ρ ≈ 0.72)
- IL-6 ↔ TNF-α (expected ρ ≈ 0.65)
- CRP ↔ TNF-α (expected ρ ≈ 0.58)

---

## Schema 5: `temporal_trajectories_v1` (Phase-Based Dynamics)

Used by: VS-1.4, VS-3.0  
Format: CSV  
Purpose: Store phase-specific means/slopes for trajectory modeling

### Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `trajectory_id` | string | YES | `{study_id}__{node_id}__{phase}` |
| `study_id` | string | YES | |
| `paper_key` | string | YES | |
| `node_id` | string | YES | FK to Node Registry |
| `instrument_id` | string | no | |
| `phase` | enum | YES | `T0`–`T4` |
| `days_from_T0` | float | no | Actual days from baseline |
| `mean` | float | YES | Group mean at this phase |
| `sd` | float | cond. | Standard deviation |
| `se` | float | cond. | Standard error (if SD not available) |
| `N` | int | YES | Sample size at this phase |
| `group` | string | no | `total` / `chemo` / `control` / `intervention` |
| `cancer_types` | string | no | |
| `trajectory_model` | enum | no | `raw_means` / `mixed_model_slope` / `latent_class` |
| `slope_coefficient` | float | no | If mixed-model slope reported |
| `slope_se` | float | no | |
| `provenance_locator` | string | YES | |

---

## Schema 6: `edge_registry_slice1_v1` (Aggregated Output)

Used by: VS-4.0, VS-4.1 output  
Format: CSV  
Purpose: The final parameter table that feeds into the B-matrix for runtime

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `edge_relation_id` | string | FK to EDGE_REGISTRY |
| `source_node_id` | string | |
| `target_node_id` | string | |
| `k` | int | Number of evidence records pooled |
| `beta_pooled` | float | IVW pooled effect (SMD or FisherZ) |
| `se_raw` | float | IVW pooled SE before inflation |
| `se_L1_design` | float | After L1 (study design) inflation |
| `se_L2_population` | float | After L2 (population match) inflation |
| `se_L3_heterogeneity` | float | After L3 (τ² added if random effects) |
| `se_L4_scale` | float | After L4 (conversion penalty) |
| `se_L5_grade` | float | After L5 (GRADE quality) inflation |
| `se_L6_temporal` | float | After L6 (timing mismatch) inflation |
| `se_L7_freshness` | float | After L7 (year decay) inflation |
| `se_eff` | float | Final effective SE |
| `I_squared` | float | Heterogeneity statistic |
| `Q_cochran` | float | Cochran's Q |
| `tau_squared` | float | Between-study variance (0 if fixed) |
| `aggregation_method` | enum | `DIRECT` / `IVW_FIXED` / `IVW_RANDOM` / `SINGLE_BEST` / `BLOCKED` |
| `grade_overall` | enum | `high` / `moderate` / `low` / `very_low` |
| `P_inclusion` | float | Probability this edge should be in model (based on evidence strength) |
| `evidence_ids` | string | Comma-separated evidence_id list |

---

## Provenance Audit Protocol

### For every numeric value extracted (mandatory):

1. **Provenance locator:** Section + Table/Fig # + row/column
2. **Verbatim snippet:** ≤25 words copied from paper (for compliance)
3. **Extraction confidence:** high/medium/low

### For calibration papers (VS-2.1), additionally:

4. **Double-entry verification:** Extract twice independently, record agreement
5. **Conversion verification:** Hand-calculate one conversion per paper to validate formula implementation

### Sanity checks (automated, run on every batch):

```python
# Automated checks for edge_evidence_v1
assert all(row.d_se > 0), "SE must be positive"
assert all(abs(row.d_value) < 5.0), "Flag: extreme effect size"
assert all(row.N_effect >= 30), "Minimum N requirement"
assert all(row.se_conversion_penalty == 1.1 ** row.conversion_steps), "Penalty formula"

# Sign consistency check
for row in evidence:
    source_orient = node_registry[row.source_node_id].orientation
    target_orient = node_registry[row.target_node_id].orientation
    expected_sign = edge_registry[row.edge_relation_id].expected_sign
    if row.sign_applied == 'as_reported':
        assert sign(row.d_value) == expected_sign_map[expected_sign], \
            f"Sign mismatch: {row.evidence_id}"
```

---

## File Naming Convention

All outputs live under `data/vertical_slice_1/`:

```
data/vertical_slice_1/
├── MULTI_EDGE_PAPERS_slice1_v1.yaml       # VS-1.0 output
├── MULTI_EDGE_TRIAGE_slice1_v1.yaml       # VS-1.1 output
├── SLICE_TOPOLOGY_FILL_v1.yaml            # VS-1.2 output (if needed)
├── BIOMARKER_CORR_MATRICES_v1.yaml        # VS-1.3 output
├── TRAJECTORIES_slice1_v1.yaml            # VS-1.4 output
├── RCT_ANCHORS_slice1_v1.yaml             # VS-1.5 output
├── templates/
│   ├── study_profiles_slice1.csv           # VS-2.0 output
│   └── edge_evidence_slice1.csv            # VS-2.0 output
├── extractions/
│   ├── {paper_key_1}/                      # VS-2.1 / VS-3.0
│   │   ├── edge_evidence.csv
│   │   ├── biomarker_corr.csv
│   │   └── extraction_notes.md
│   └── {paper_key_2}/
│       └── ...
├── compiled/
│   ├── study_profiles_slice1_v1.csv        # VS-3.0 merged output
│   ├── edge_evidence_slice1_v1.csv         # VS-3.0 merged output
│   ├── biomarker_corr_matrix_v1.csv        # VS-3.0 merged output
│   ├── temporal_trajectories_v1.csv        # VS-3.0 merged output
│   ├── edge_registry_slice1_v1.csv         # VS-4.0/4.1 output
│   └── layer_traces_slice1_v1.csv          # VS-4.1 output
└── notebooks/
    ├── VS1_aggregation.ipynb               # VS-4.0
    └── VS1_end_to_end.ipynb                # VS-5.0
```
