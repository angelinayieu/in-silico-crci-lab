# Extraction → Computation Wiring Audit & Gap Analysis

**Date:** 2026-02-27  
**Purpose:** Identify what extraction is missing for P2–P7 and runtime, define the canonical extraction table schema, propose harmonization rule generation, and provide a complete wiring map from evidence tables → compiled tables → algorithm chains.

---

## 1. Answer: Did We Miss Extraction Instructions?

**Yes — 15 gaps identified (6 critical, 6 moderate, 3 low).** The extraction CSV captures rich metadata (32 columns in the extended format), but the P2→P3→P4 automated pipeline **drops nearly all of it** — only `harmonized_beta`, `harmonized_se`, and `edge_relation_id` survive into `HarmonizedClaim`. This means P3's 7-layer SE calibration and P4's shared-control handling are running on defaults.

### 1.1 Critical Missing Information That Must Be Extracted Per Paper

| # | Field | Why Needed | Where It Goes |
|---|-------|-----------|--------------|
| **E1** | `study_design` (RCT / cohort / cross-sectional / meta) | P3 Layer 1 uses this for SE inflation: RCT=1.0×, cohort=1.5×, cross-sectional=2.0×, unclassified=**3.0×**. Without it, every study gets 3× SE inflation — the single largest quantitative distortion. | `edge_evidence_v1.study_design` → `HarmonizedClaim.study_design` → P3 L1 |
| **E2** | `n_total`, `n_treatment`, `n_control` | P4 shared-control N-splitting requires treatment/control N. P3 L1 also uses n_total for small-sample correction. Without it, shared-control correction is impossible. | `edge_evidence_v1.N_effect` + new fields → `HarmonizedClaim` → P4 |
| **E3** | `pub_year` | P3 Layer 7 freshness weighting (older studies discounted by ~3%/yr). Without it, all records get a blanket 15% freshness penalty. | `study_registry_v1.year` → `HarmonizedClaim.pub_year` → P3 L7 |
| **E4** | `cancer_validation_status` | P3 Layer 4: cancer-validated samples get m=1.0, general pop gets m=1.3. Without it, all evidence treated as general-population (30% SE inflation). Chain B Layer 3 also uses this. | `edge_evidence_v1.cancer_validation_status` (new column needed) → P3 L4 |
| **E5** | `scope_weights` (5 dimensions: cancer_type, treatment_phase, chemo_regimen, age_range, sex) | P3 Layer 2 transportability: how well the study population matches the target context. Without it, defaults to w_scope=1.0 (perfect match, no inflation) — **optimistic bias**. Chain B Layer 7 also uses this. | Derived from `study_cohort_profiles_v1` ↔ target context → `edge_evidence_v1.scope_weights_json` (new) |
| **E6** | `shared_control_flag` + `endpoint_vs_change` | P4 detects overlapping control groups across arms of the same study. Without flags, duplicated control N double-counts evidence. | `edge_evidence_v1` existing columns → `HarmonizedClaim` → P4 |

### 1.2 Moderate Missing Information

| # | Field | Why Needed | Where It Goes |
|---|-------|-----------|--------------|
| **E7** | `temporal_distance_days` (alignment lag) | P3 Layer 6 temporal decay and Chain B Layer 6 temporal proximity weighting. Currently always 0.0 (no decay), which is only correct for concurrent measurements. | `edge_evidence_v1.alignment_lag_days` → `HarmonizedClaim.days_since_measurement` |
| **E8** | `outcome_type` (subjective / semi_objective / biomarker) | Chain B τ² prior selection (Turner et al. lookup). Always "semi_objective" currently — biases heterogeneity estimates when biomarkers are present. | `edge_evidence_v1.outcome_type` (new column or derive from measure_id) |
| **E9** | `rob_overall` (risk of bias) | Future GRADE assessment (P5). Currently captured in CSV but not propagated anywhere. | `edge_evidence_v1.rob_overall` → P5 GRADE computation → `HarmonizedClaim.grade_level` |
| **E10** | `covariates_adjusted` (list of covariates) | Identification scoring — estimand quality. A study adjusting for age, stage, chemo gets higher identification weight. | `edge_evidence_v1.covariates_adjusted` (exists) → Chain B identification scoring |
| **E11** | `timepoint_weeks` | Maps to `alignment_lag_days` for temporal alignment. Available in extended CSV but not converted. | CSV → `edge_evidence_v1.alignment_lag_days` (×7 conversion) |
| **E12** | GRADE quality level | P3 Layer 5 and P5 sufficiency gate. Currently defaults to MODERATE for everyone. | Manual or semi-automated GRADE → HarmonizedClaim.grade_level |

### 1.3 Low-Priority (Captured but Unused)

| # | Field | Status |
|---|-------|--------|
| **E13** | `sd_standardization.py` not called in P2 runner | SD borrowing happens separately in manual import |
| **E14** | `covariates_adjusted` | Captured in CSV, stored in DB, but no downstream consumer reads it yet |
| **E15** | `sigma_sq_structural` override | Annotation-informed structural variance; falls back to config default |

---

## 2. Answer: Harmonization Rule Generation + Proposals

### 2.1 Current State

- `harmonization_rules_v1` table (**A6**) is defined in schema but has **0 rows** — no seed CSV exists
- P2's `conversion_router.py` and `scale_harmonizer.py` **hardcode** all conversion logic:
  - OR → SMD: `d = ln(OR) × √3 / π`
  - HR → OR: `OR ≈ HR` (approximate identity)
  - r → d: `d = 2r / √(1 - r²)`
  - SE from CI: `SE = (upper - lower) / (2 × 1.96)`
  - Unstandardized β → per-SD: `β_sd = β_raw × SD_x`
- This hardcoded approach works for known conversions but **cannot adapt** when new effect types appear

### 2.2 Recommendation: Yes, Build Rule Generation + Proposal System

A two-tier approach:

#### Tier 1: Seed the Known Rules (immediate)

Create `crci/database/seeds/harmonization_rules.csv` with the ~12 established conversions:

```
rule_id,effect_type_reported,x_transform_required,y_transform_required,required_fields,output_scale,conversion_family,conversion_notes,version,active
HR_STD_BETA_TO_SD_SD,std_beta,none,none,"effect_value_reported,se_reported",SD_SD,std_beta_identity,"Standardized beta is already in SD/SD units",1,1
HR_UNSTD_BETA_TO_SD_SD,unstd_beta,none,none,"effect_value_reported,se_reported,sd_x,sd_y",SD_SD,unstd_beta_to_sd_sd,"β_sd = β_raw × SD_x / SD_y",1,1
HR_UNSTD_BETA_TO_PROXY_PER_SD,unstd_beta,none,none,"effect_value_reported,se_reported,sd_x",PROXY_PER_SD,unstd_beta_to_proxy_per_sd,"β_proxy = β_raw × SD_x",1,1
HR_OR_TO_SMD,OR,none,none,"effect_value_reported,se_reported",SD_SD,or_to_smd,"d = ln(OR) × √3/π; SE_d = SE_lnOR × √3/π",1,1
HR_HR_TO_LOGOR,HR,none,none,"effect_value_reported,se_reported",LOGOR_PER_SD,hr_to_logor,"OR ≈ HR; ln(OR) ≈ ln(HR)",1,1
HR_R_TO_D,correlation_r,none,none,"effect_value_reported",SD_SD,r_to_d,"d = 2r/√(1-r²)",1,1
HR_GROUP_DIFF_TO_SMD,group_diff,none,none,"effect_value_reported,sd_pooled,n_treatment,n_control",SD_SD,group_diff_to_smd,"d = (M1-M2)/SD_pooled; SE = √(1/n1+1/n2+d²/(2(n1+n2)))",1,1
HR_COHENS_D_IDENTITY,cohens_d,none,none,"effect_value_reported,se_reported",SD_SD,cohens_d_identity,"Cohen's d is already SMD",1,1
HR_HEDGES_G_IDENTITY,hedges_g,none,none,"effect_value_reported,se_reported",SD_SD,hedges_g_identity,"Hedges' g is bias-corrected SMD",1,1
HR_LOG_OR_IDENTITY,log_OR,none,none,"effect_value_reported,se_reported",LOGOR_PER_SD,log_or_identity,"Already on log-OR scale",1,1
HR_LOG_HR_TO_LOGOR,log_HR,none,none,"effect_value_reported,se_reported",LOGOR_PER_SD,log_hr_to_logor,"≈ identity for rare events",1,1
HR_RR_TO_OR,RR,none,none,"effect_value_reported,se_reported,baseline_risk",SD_SD,rr_to_or_to_smd,"OR = RR×(1-p0)/(1-RR×p0); then OR→SMD",1,1
```

#### Tier 2: Rule Proposal System (build as feature)

When P2 encounters an `effect_type_reported` with **no matching rule** in `harmonization_rules_v1`:

1. **Quarantine** the record with `harmonization_status = 'RULE_MISSING'`
2. **Generate a proposal** by:
   - Looking up the effect type in a known taxonomy (Cohen 1988, Borenstein et al. 2009)
   - Checking if the reported fields enable any known conversion family
   - Proposing a conversion formula with provenance citations
3. **Write to `harmonization_rule_proposals_v1`** (new table):

```sql
CREATE TABLE IF NOT EXISTS harmonization_rule_proposals_v1 (
    proposal_id          TEXT PRIMARY KEY,
    proposed_rule_id     TEXT NOT NULL,
    effect_type_reported TEXT NOT NULL,
    proposed_conversion  TEXT NOT NULL,     -- formula description
    required_fields      TEXT NOT NULL,
    output_scale         TEXT NOT NULL,
    confidence           TEXT NOT NULL,     -- 'high', 'medium', 'low'
    provenance           TEXT NOT NULL,     -- textbook/paper citation
    triggering_ler_ids   TEXT NOT NULL,     -- JSON array of records that need this
    status               TEXT DEFAULT 'pending',  -- 'pending','approved','rejected'
    reviewed_by          TEXT,
    reviewed_at          TEXT,
    created_at           TEXT DEFAULT (datetime('now'))
);
```

4. **Human review loop**: Dashboard shows pending proposals; on approval → insert into `harmonization_rules_v1` and re-run P2 for quarantined records

This keeps the system **honest** (no silent fallback) while being **adaptive** (discovers new conversion needs as new papers are extracted).

---

## 3. Final Extraction Table Schema (Canonical)

Below is the **complete, aligned** `edge_evidence_v1` schema — the single source of truth for extracted evidence. Every column is annotated with which downstream step consumes it.

### 3.1 edge_evidence_v1 — Complete Schema (86 columns)

All existing columns are preserved. **New columns** are marked with ⭐.

```
  IDENTITY & PROVENANCE
  ─────────────────────
  ler_id                      TEXT PK        -- Unique evidence row ID
  edge_param_id               TEXT           -- Compiled edge this contributes to (set by P4)
  edge_relation_id            TEXT NOT NULL   -- FK → edge_relations_definitions_v1
  profile_id                  TEXT NOT NULL   -- FK → study_cohort_profiles_v1
  study_id                    TEXT NOT NULL   -- FK → study_registry_v1
  edge_family                 TEXT           -- Guardrail grouping
  node_x                      TEXT           -- Upstream node
  node_y                      TEXT           -- Downstream node

  UPSTREAM (Predictor / X)
  ────────────────────────
  upstream_instrument_id      TEXT           -- FK → instrument_definitions_v1
  upstream_stream_id          TEXT           -- FK → profile_data_streams_v1
  upstream_raw_unit           TEXT           -- Original unit reported

  DOWNSTREAM (Outcome / Y)
  ────────────────────────
  downstream_measure_id       TEXT           -- FK → measure_definitions_v1
  downstream_stream_id        TEXT           -- FK → profile_data_streams_v1
  downstream_raw_unit         TEXT           -- Original unit reported

  ANALYSIS MODEL METADATA
  ───────────────────────
  analysis_model_family       TEXT           -- → P3 L1 (design-based SE inflation) 
  analysis_model_family_id    TEXT
  model_family                TEXT           -- regression, ANOVA, etc.
  random_effects_structure    TEXT           -- fixed, random, mixed
  cluster_unit                TEXT
  se_type                     TEXT           -- robust, clustered, model-based
  predictor_level             TEXT           -- between, within
  centered_level              TEXT
  centering_method            TEXT
  centering_note              TEXT

  OUTCOME & TIME DEFINITIONS
  ──────────────────────────
  outcome_component           TEXT           -- → Chain B outcome_type derivation
  time_metric_definition      TEXT
  CAR_definition              TEXT
  time_unit_x                 TEXT
  time_unit_y                 TEXT

  TRANSFORMS
  ──────────
  x_transform                 TEXT           -- → P2 conversion routing
  y_transform                 TEXT           -- → P2 conversion routing

  TEMPORAL ALIGNMENT
  ──────────────────
  alignment_type              TEXT           -- → P3 L6 temporal decay
  alignment_type_id           TEXT
  alignment_lag_days          INTEGER        -- → P3 L6, Chain B L6
  alignment_note              TEXT

  REPORTED EFFECT ESTIMATES
  ────────────────────────
  effect_type_reported        TEXT NOT NULL   -- → P2 conversion_router
  effect_value_reported       REAL NOT NULL   -- → P2 scale_harmonizer
  se_reported                 REAL           -- → P2 SE derivation cascade
  ci_low_reported             REAL           -- → P2 SE fallback (SE from CI)
  ci_high_reported            REAL           -- → P2 SE fallback
  p_value                     REAL           -- → P2 SE fallback (SE from p)
  sd_x                        REAL           -- → P2 unstandardized β conversion
  sd_y                        REAL           -- → P2 unstandardized β conversion
  N_effect                    INTEGER NOT NULL -- → P3, P4, Chain B

  SUBGROUP / ADJUSTMENT
  ─────────────────────
  subgroup_label              TEXT
  covariates_adjusted         TEXT           -- → Chain B identification scoring
  adjustment_selection_method TEXT

  HARMONIZATION (Set by P2)
  ─────────────────────────
  harmonization_status        TEXT DEFAULT 'unreviewed'  -- → P3 gate
  harmonized_scale            TEXT           -- → P3, P4, Chain B
  harmonized_beta             REAL           -- → P3, P4, Chain B (primary input!)
  harmonized_se               REAL           -- → P3, P4, Chain B (primary input!)
  blocked_reason              TEXT           -- → P6 review
  harmonization_rule_id       TEXT           -- FK → harmonization_rules_v1

  INTERACTION / MODERATION (for subgroup evidence)
  ────────────────────────
  interaction_reported        INTEGER DEFAULT 0
  interaction_variable_id     TEXT
  interaction_variable_raw    TEXT
  moderator_definition        TEXT
  interaction_beta            REAL
  interaction_se              REAL
  subgroup_beta_M0            REAL
  subgroup_se_M0              REAL
  subgroup_beta_M1            REAL
  subgroup_se_M1              REAL
  interaction_effect_reported TEXT

  QUALITY & AUDIT
  ───────────────
  quality_rating              TEXT DEFAULT 'moderate'  -- → P3 L5
  extraction_snippet          TEXT
  entered_by                  TEXT
  entered_at                  TEXT
  version                     INTEGER DEFAULT 1
  active                      INTEGER DEFAULT 1

  RISK-OF-BIAS & CAUSAL IDENTIFICATION
  ────────────────────────────────────
  rob_tool                    TEXT           -- → P5 GRADE
  rob_overall                 TEXT           -- → P5 GRADE → grade_level
  estimand_class              TEXT           -- → Chain B identification scoring
  identification_status       TEXT           -- → Chain B EvidenceRecord

  META-ANALYSIS PROVENANCE
  ────────────────────────
  parent_meta_study_id        TEXT           -- → P4 double-counting detection
  notes                       TEXT

  ⭐ NEW: FIELDS NEEDED FOR P3-P4 & CHAIN B (must be added)
  ─────────────────────────────────────────────────────────
  cancer_validation_status    TEXT DEFAULT 'general_population'  
      -- {cancer_validated, cancer_adjacent, general_population}
      -- → P3 L4 (m=1.0 / 1.15 / 1.30), Chain B L3
  
  scope_weights_json          TEXT DEFAULT '{}'   
      -- JSON: {"cancer": 0.5, "phase": 0.5, "regimen": 0.5, "age": 0.5, "sex": 0.5}
      -- → P3 L2 (w_scope), Chain B L7
  
  outcome_type                TEXT DEFAULT 'semi_objective'  
      -- {subjective, semi_objective, biomarker}
      -- → Chain B τ² prior (Turner et al.)
  
  shared_control_flag         INTEGER DEFAULT 0  
      -- → P4 shared-control N-splitting
  
  endpoint_vs_change          TEXT DEFAULT 'unclear'  
      -- {endpoint, change, unclear}  
      -- → P4 shared-control handling

  ⭐ NEW: P3 SE CALIBRATION OUTPUTS (set by P3)
  ─────────────────────────────────────────────
  se_eff                      REAL           -- Final 7-layer calibrated SE
  se_inflation_applied        REAL DEFAULT 1.0  -- Product of all 7 layers
  se_layer_details_json       TEXT           -- JSON breakdown of each layer's contribution
  escalation_se_inflation     REAL DEFAULT 1.0  -- Chain B reads this
```

### 3.2 Supporting Tables (Already Exist, Must Be Populated)

| Table | Role | Pop. Status | Needed By |
|-------|------|------------|-----------|
| `study_registry_v1` (B1) | Paper metadata (year, design, identifiers) | 4 papers populated | Chain B (joins for pub_year, study_design) |
| `study_cohort_profiles_v1` (B2) | Cohort demographics, cancer context | 4 papers populated | P2 scope_matching, Chain B transportability |
| `profile_data_streams_v1` (B3) | Instrument × measure per cohort | 4 papers populated | Edge evidence provenance |
| `stream_timepoints_v1` (B4) | Measurement schedule | Partially populated | Temporal alignment for mediation/longitudinal |
| `ontology_links_v1` (B5) | Entity provenance links | Sparsely populated | Audit trail |
| `edge_param_builds_v1` (B7) | Aggregation audit trail | Empty (P4 output) | Reproducibility |
| `triangulation_evidence_v1` (B8) | Cross-method agreement | Empty | Future triangulation scoring |

### 3.3 Auxiliary Evidence Tables (for P7 Compilers)

These tables store non-edge-effect evidence that P7 compilers transform into Class A/C tables:

| Table | What It Stores | P7 Compiler | Compiles Into |
|-------|---------------|-------------|---------------|
| `instrument_evidence_v1` (hypothetical B10) | Psychometric data per study | P7-C1 | `instrument_definitions_v1.loading_b_k, reliability_alpha` |
| `population_norms_v1` (hypothetical B11) | Population mean/SD per node×context | P7-C2 | `node_priors_v1` (C3) |
| `temporal_evidence_v1` (hypothetical B12) | Intervention onset/build/decay timing | P7-C3 | `intervention_kernels_v1` (A32) |
| `dose_evidence_v1` (hypothetical B13) | Dose-response curves from trials | P7-C4 | `dose_bridges_v1` (C2) |
| `subgroup_evidence_v1` (hypothetical B14) | Subgroup interaction effects | P7-C5 | `baseline_modifier_definitions_v1` (A16) |

**Current extraction status for auxiliary templates:**

| Template | Cherrier 2013 | Campbell 2017 | Northey 2018 | Adam 2017 |
|----------|:---:|:---:|:---:|:---:|
| population_norms | 3 rows | 6 rows | 5 rows | — |
| context_priors | 3 rows | 4 rows | 5 rows | — |
| instrument_evidence | ✓ | ✓ | — | — |
| temporal_evidence | ✓ | ✓ | — | — |

---

## 4. Wiring Map: Evidence Extraction → Node Setup → Algorithm

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                    EVIDENCE EXTRACTION → COMPUTATION WIRING MAP                              ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

      ┌─────────────────────────────────────────────────────────────────┐
      │              PHASE 1: PAPER INGESTION (P0 + P1)                │
      │                                                                 │
      │  PDF/API → P0 Triage → P1 Multi-Agent Extraction               │
      │                                                                 │
      │  OUTPUTS:                                                       │
      │   ├─ study_registry_v1 ────────────┐                           │
      │   ├─ study_cohort_profiles_v1 ─────┤  (Class B evidence)       │
      │   ├─ profile_data_streams_v1 ──────┤                           │
      │   ├─ stream_timepoints_v1 ─────────┤                           │
      │   ├─ edge_evidence_v1 ─────────────┤← RAW effects (pre-harm)  │
      │   ├─ instrument_evidence (B10) ────┤                           │
      │   ├─ population_norms (B11) ───────┤                           │
      │   ├─ temporal_evidence (B12) ──────┤                           │
      │   ├─ dose_evidence (B13) ──────────┤                           │
      │   └─ subgroup_evidence (B14) ──────┘                           │
      └───────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │              PHASE 2: HARMONIZATION (P2)                        │
      │                                                                 │
      │  edge_evidence_v1.effect_type_reported ──┐                     │
      │  + harmonization_rules_v1 (A6) ──────────┤                     │
      │  + sd_anchors (borrowed SD) ─────────────┤                     │
      │  + edge_ontology_v1 (A2, gates) ─────────┘                     │
      │                    │                                            │
      │                    ▼                                            │
      │  conversion_router → scale_harmonizer → orientation_aligner    │
      │                    │                                            │
      │  UPDATES edge_evidence_v1:                                     │
      │   ├─ harmonized_beta     (converted effect)                    │
      │   ├─ harmonized_se       (converted SE)                        │
      │   ├─ harmonized_scale    (SD_SD / PROXY_PER_SD / LOGOR_PER_SD)│
      │   ├─ harmonization_status (OK / BLOCKED / RULE_MISSING)        │
      │   └─ harmonization_rule_id (FK → which rule was applied)       │
      │                                                                 │
      │  ⚠ MISSING RULES → harmonization_rule_proposals_v1 (NEW)      │
      └───────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │              PHASE 3: HETEROGENEITY / SE CALIBRATION (P3)       │
      │                                                                 │
      │  READS FROM edge_evidence_v1 (harmonized) + context:           │
      │   ├─ study_design         → L1 (SE × 1.0–3.0)                 │
      │   ├─ scope_weights_json ⭐ → L2 (SE × 1.0–1.5)               │
      │   ├─ group betas          → L3 (τ², I²)                       │
      │   ├─ cancer_valid_status ⭐→ L4 (SE × 1.0–1.3)               │
      │   ├─ quality_rating       → L5 (SE × 1.0–2.0)                 │
      │   ├─ alignment_lag_days   → L6 (temporal decay)                │
      │   └─ pub_year (from B1)   → L7 (freshness 3%/yr)              │
      │                    │                                            │
      │  OUTPUT: SE_eff = SE_harmonized × ∏(layer_i inflation)         │
      │                                                                 │
      │  UPDATES edge_evidence_v1:                                     │
      │   ├─ se_eff ⭐                                                 │
      │   ├─ se_inflation_applied ⭐                                   │
      │   └─ se_layer_details_json ⭐                                  │
      └───────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │              PHASE 4: AGGREGATION (P4) + PUB BIAS (P4B)         │
      │                                                                 │
      │  Groups edge_evidence_v1 rows by edge_relation_id              │
      │                                                                 │
      │  READS:                                                         │
      │   ├─ harmonized_beta, se_eff (per row)                         │
      │   ├─ N_effect, n_treatment, n_control ⭐                       │
      │   ├─ shared_control_flag ⭐ (for N-splitting)                  │
      │   ├─ endpoint_vs_change ⭐                                     │
      │   └─ parent_meta_study_id (double-counting detection)          │
      │                                                                 │
      │  P4 IVW META-ANALYSIS (Formula P4-1):                         │
      │   β̂_IVW = Σ(β_i / SE²_i) / Σ(1/SE²_i)                       │
      │   SE_IVW = 1 / √Σ(1/SE²_i)                                   │
      │                                                                 │
      │  P4B PUB BIAS:                                                 │
      │   Egger's test → SE inflation if asymmetry detected            │
      │                                                                 │
      │  WRITES → edges_v1 (C1):                                      │
      │   ├─ beta_mean, beta_se (pooled)                               │
      │   ├─ i_squared, tau_squared                                    │
      │   ├─ total_n, evidence_level                                   │
      │   ├─ pub_bias_risk, se_inflation_pub_bias                      │
      │   └─ supporting_ler_ids                                        │
      └───────────────┬───────────────────────────┬─────────────────────┘
                      │                           │
                      ▼                           ▼
      ┌──────────────────────────┐  ┌──────────────────────────────────┐
      │  P5: SUFFICIENCY CHECK   │  │  P4B writes to edges_v1:        │
      │  ─────────────────────   │  │   pub_bias_risk                  │
      │  Gates:                  │  │   se_inflation_pub_bias          │
      │   - min_k ≥ 2 studies    │  │   coherence_flag                 │
      │   - I² ≤ threshold       │  │   se_inflation_coherence         │
      │   - evidence_level check │  │   e_value, robustness_value      │
      │  → PASS / BLOCK / REVIEW │  └──────────────────────────────────┘
      └───────────┬──────────────┘
                  │
                  ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │              P6: DEPLOYMENT VALIDATION                          │
      │  Final gates before evidence enters the live model             │
      │   - Sign coherence (effect direction matches ontology)         │
      │   - Boundary checks (|β| not implausible)                     │
      │   - Cross-edge consistency                                     │
      │  → DEPLOY / BLOCK                                              │
      └───────────┬──────────────────────────────────────────────────────┘
                  │
                  ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │              P7: COMPILERS (auxiliary evidence → Class A/C)      │
      │                                                                 │
      │  P7-C1: instrument_evidence (B10) ──→ instrument_defs (A4)     │
      │         • Updates: loading_b_k, reliability_alpha              │
      │         • Used by: Chain A instrument_loader, Chain C obs_mapper│
      │                                                                 │
      │  P7-C2: population_norms (B11) ────→ node_priors_v1 (C3)      │
      │         • Compiles: μ_prior, σ_prior per node×cancer×phase     │
      │         • Used by: Chain C prior_loader                        │
      │                                                                 │
      │  P7-C3: temporal_evidence (B12) ───→ intervention_kernels (A32)│
      │         • Compiles: onset_weeks, build_weeks, decay_half_life  │
      │         • Used by: Chain D intervention_loader, Chain E overlay │
      │                                                                 │
      │  P7-C4: dose_evidence (B13) ───────→ dose_bridges_v1 (C2)     │
      │         • Compiles: Emax/Hill params, bridge_gain, bridge_sign │
      │         • Used by: Chain D intervention_loader                 │
      │                                                                 │
      │  P7-C5: subgroup_evidence (B14) ───→ modifier_defs (A16)      │
      │         • Compiles: baseline modifier rules (109 rules)        │
      │         • Used by: Chain C modifier_application                │
      └───────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                    ALGORITHM CHAINS (COMPUTATION)                       ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                         ║
║  ┌──────────────────────────────────────────────────────────────┐       ║
║  │  CHAIN A: GRAPH ASSEMBLY (build-time)                        │       ║
║  │  READS: CSV registries → NODE, EDGE, INSTRUMENT, PATHWAY     │       ║
║  │  OUTPUT: GraphObject (NodeMap + BSkeleton + InstrumentMap +   │       ║
║  │          DMatrix + LambdaStructure + PathwayMap)              │       ║
║  └──────────────────────────────┬───────────────────────────────┘       ║
║                                 │                                       ║
║  ┌──────────────────────────────▼───────────────────────────────┐       ║
║  │  CHAIN B: EDGE PARAMETERIZATION (build-time)                  │       ║
║  │  READS: edge_evidence_v1 (B6) + study_registry_v1 (B1)       │       ║
║  │         ⚠ NOT edges_v1 (C1) — reads raw evidence directly    │       ║
║  │                                                                │       ║
║  │  FIELDS FROM edge_evidence_v1:                                │       ║
║  │   harmonized_beta ────────── primary effect size              │       ║
║  │   harmonized_se ──────────── primary standard error           │       ║
║  │   N_effect ───────────────── sample size                      │       ║
║  │   quality_rating ─────────── maps to grade discount           │       ║
║  │   identification_status ──── estimand quality                 │       ║
║  │   harmonized_scale ───────── which scale family               │       ║
║  │   se_inflation_applied ⭐─── avoids double-inflation          │       ║
║  │   escalation_se_inflation ⭐  Chain B additional inflation    │       ║
║  │   cancer_validation_status ⭐ L3 claim attenuation            │       ║
║  │   scope_weights_json ⭐───── L7 transportability              │       ║
║  │   outcome_type ⭐─────────── τ² prior selection               │       ║
║  │                                                                │       ║
║  │  FIELDS FROM study_registry_v1:                               │       ║
║  │   study_design ───────────── design class                     │       ║
║  │   year ───────────────────── freshness weighting              │       ║
║  │                                                                │       ║
║  │  OUTPUT: FrozenModelState (B̂, Σ_eff, Λ_prior, P_inclusion)   │       ║
║  └──────────────────────────────┬───────────────────────────────┘       ║
║                                 │                                       ║
║  ════════════ BUILD / RUNTIME BOUNDARY (FrozenModelState) ═══════       ║
║                                 │                                       ║
║  ┌──────────────────────────────▼───────────────────────────────┐       ║
║  │  CHAIN C: PATIENT STATE INFERENCE (runtime)                   │       ║
║  │  READS: FrozenModelState + node_priors_v1 (C3, from P7-C2)   │       ║
║  │         + InstrumentMap (A) + patient observations             │       ║
║  │         + modifier_defs (A16, from P7-C5)                     │       ║
║  │  OUTPUT: PatientState (θ̂, Σ_post, active_pathways)           │       ║
║  └──────────────────────────────┬───────────────────────────────┘       ║
║                                 │                                       ║
║  ┌──────────────────────────────▼───────────────────────────────┐       ║
║  │  CHAIN D: INTERVENTION SIMULATION (runtime)                   │       ║
║  │  READS: PatientState (C) + action_catalog_v1 (A21)            │       ║
║  │         + dose_bridges_v1 (C2, from P7-C4)                    │       ║
║  │         + intervention_kernels_v1 (A32, from P7-C3)           │       ║
║  │         + contraindication_rules_v1 (A10)                     │       ║
║  │         + FrozenModelState (B̂, Σ_eff, P_inclusion for MC)    │       ║
║  │  OUTPUT: RankingResult (SAFE scores, doses, causal claims)    │       ║
║  └──────────────────────────────┬───────────────────────────────┘       ║
║                                 │                                       ║
║  ┌──────────────────────────────▼───────────────────────────────┐       ║
║  │  CHAIN E: TEMPORAL PREDICTION (runtime)                       │       ║
║  │  READS: PatientState (C) + RankingResult (D)                  │       ║
║  │         + recovery_trajectories_v1 (A29)                      │       ║
║  │         + intervention_kernels_v1 (A32)                       │       ║
║  │  OUTPUT: OverlayResult (trajectories, aging projection)       │       ║
║  └──────────────────────────────┬───────────────────────────────┘       ║
║                                 │                                       ║
║  ┌──────────────────────────────▼───────────────────────────────┐       ║
║  │  CHAIN F: OUTPUT & ANALYTICS (runtime)                        │       ║
║  │  READS: PatientState (C) + RankingResult (D)                  │       ║
║  │         + OverlayResult (E)                                   │       ║
║  │  OUTPUT: Composite scores, risk indices, EVSI, variance decomp│       ║
║  └──────────────────────────────────────────────────────────────┘       ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝
```

---

## 5. Detailed Table Cross-Reference: Who Writes, Who Reads

```
TABLE                           WRITTEN BY          READ BY                         STATUS
───────────────────────────────────────────────────────────────────────────────────────────────
CLASS A (Knowledge — human curated)
  biomarker_node_definitions_v1  Manual/Seed         Chain A, Chain B, Chain C, P2    ✅ 63 nodes
  edge_relations_definitions_v1  Manual/Seed         Chain A, Chain B, P1, P2         ✅ 133 edges
  edge_ontology_v1               Manual/Seed         P2 (CG4 gate)                   ⚠ Partially
  instrument_definitions_v1      Manual/Seed+P7-C1   Chain A, Chain C                 ✅ Seeded
  measure_definitions_v1         Manual/Seed         P2, Chain D                      ✅ Seeded
  harmonization_rules_v1         Manual/Seed         P2 conversion_router             ❌ 0 ROWS
  action_catalog_v1              Manual               Chain D                          ✅ Seeded
  contraindication_rules_v1      Manual               Chain D safety_checker           ✅ Seeded
  intervention_kernels_v1        Manual+P7-C3         Chain D, Chain E                 ⚠ Partial
  recovery_trajectories_v1       Manual               Chain E                          ⚠ Hardcoded
  baseline_modifier_defs_v1      Manual+P7-C5         Chain C modifier_application     ⚠ Partial

CLASS B (Evidence — from extraction)
  study_registry_v1              P1                   Chain B (year, design)           ✅ 4 papers
  study_cohort_profiles_v1       P1                   P2 scope_matching                ✅ 4 papers
  profile_data_streams_v1        P1                   Provenance                       ✅ 4 papers
  stream_timepoints_v1           P1                   Temporal alignment               ⚠ Partial
  edge_evidence_v1               P1→P2→P3 update      Chain B (PRIMARY consumer!)      ✅ ~18 rows
  edge_param_builds_v1           P4                   Audit trail                      ❌ Empty
  triangulation_evidence_v1      P1 (future)          Triangulation scoring            ❌ Empty

CLASS C (Compiled — from P4/P7)
  edges_v1                       P4+P4B               Dashboard (NOT Chain B!)         ❌ Empty
  dose_bridges_v1                P7-C4                Chain D                          ⚠ Partial
  node_priors_v1                 P7-C2                Chain C                          ⚠ Partial

CLASS D (Runtime — session data)
  (session tables)               Runtime              Runtime                          N/A

CLASS E (Outputs — from algorithm)
  (output tables)                Chain F              Presentation                     N/A
```

---

## 6. Specific Extraction Instruction Additions Needed

To support P2–P7 and the algorithm chains, the extraction prompts (P1 agents) must capture these **additional fields per paper**:

### 6.1 For EVERY Paper (add to extraction template)

```yaml
# Add to LLM extraction prompt for every paper:
MUST_EXTRACT:
  - study_design: "RCT | prospective_cohort | retrospective_cohort | cross_sectional | case_control | meta_analysis | systematic_review"
  - n_total: "Total sample size analyzed for this specific effect"
  - n_treatment: "Treatment/exposed group N (if applicable)"
  - n_control: "Control/unexposed group N (if applicable)"
  - pub_year: "Publication year (extract from paper header)"
  - cancer_validation_status: "Was this study conducted IN cancer survivors? cancer_validated | cancer_adjacent | general_population"
  - outcome_type: "subjective (self-report only) | semi_objective (clinical test) | biomarker (lab assay)"
  - rob_overall: "Risk of bias: low | some_concerns | high (if assessed or inferable from methods)"
  - alignment_lag_days: "Days between predictor and outcome measurement (0 if concurrent)"
  - shared_control_flag: "1 if multiple treatment arms share the same control group, else 0"
  - endpoint_vs_change: "endpoint (raw score) | change (change from baseline) | unclear"
  - covariates_adjusted: "Comma-separated list of covariates in the model (e.g., age,sex,stage,chemo_regimen)"
```

### 6.2 For SCOPE MATCHING (derive from cohort profile)

```yaml
# Compute scope_weights from study_cohort_profiles_v1 fields:
scope_weights:
  cancer_match:   0.35 weight — does the study cancer type match target?
  phase_match:    0.25 weight — does treatment phase match?
  regimen_match:  0.20 weight — chemotherapy regimen overlap?
  age_match:      0.10 weight — age distribution overlap?
  sex_match:      0.10 weight — sex distribution overlap?
# This can be computed automatically from B2 demographics vs target context
```

### 6.3 For P7 COMPILERS (extract as auxiliary templates)

```yaml
# Auxiliary templates (not in edge_evidence, separate files):
instrument_evidence:
  - cronbachs_alpha, test_retest_r, factor_loadings (for P7-C1)
population_norms:
  - node_id, mean, sd, cancer_type, treatment_phase, sample_size (for P7-C2)
temporal_evidence:
  - intervention onset, build time, decay rate per pathway (for P7-C3)
dose_evidence:
  - dose levels, response at each level, dose-response model fit (for P7-C4)
subgroup_evidence:
  - interaction variable, subgroup effects, moderator definitions (for P7-C5)
```

---

## 7. Action Items — Detailed Technical Breakdown

---

### ACTION 1 [P0]: Add 5 new columns to `edge_evidence_v1` schema

**Effort:** 1 hr  
**Status:** The ORM model in `tables.py` already has these columns as v2.0 extensions (added by Slice 8), but the `CREATE TABLE` in the SQL schema file is stale.

**Files to modify:**

| # | File | What to do |
|---|------|-----------|
| 1a | `crci/database/schema/002_class_b_evidence.sql` | The `CREATE TABLE edge_evidence_v1` block (lines 141–245) is missing the v2.0 extension columns. Add the 5 columns before the closing `);` after `notes TEXT` (line 245). |
| 1b | Create `crci/database/schema/014_edge_evidence_v2_columns.sql` | Migration file using `ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS ...` for live databases. Follow pattern from `013_template_alignment.sql`. |

**Exact columns to add (SQL):**

```sql
-- In 014_edge_evidence_v2_columns.sql:
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS cancer_validation_status TEXT DEFAULT 'general_population';
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS scope_weights_json      TEXT DEFAULT '{}';
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS outcome_type            TEXT DEFAULT 'semi_objective';
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS shared_control_flag     INTEGER DEFAULT 0;
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS endpoint_vs_change      TEXT DEFAULT 'unclear';
-- P3 output columns:
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS se_eff                  REAL;
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS se_inflation_applied    REAL DEFAULT 1.0;
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS se_layer_details_json   TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN IF NOT EXISTS escalation_se_inflation REAL DEFAULT 1.0;
```

**Verification:** The ORM `EdgeEvidence` class in `crci/shared/models/tables.py` (line ~891) already declares `cancer_validation_status`, `scope_weights_json` (as `scope_weights_json` — verify naming), `outcome_type`, `shared_control_flag`, `endpoint_vs_change`, `se_inflation_applied`, `escalation_se_inflation`. Confirm 1:1 match between ORM column names and SQL column names. Three columns to check are already on the ORM: `shared_control_flag` (line ~988), `endpoint_vs_change` (line ~990), `cancer_validation_status` (line ~1003). The columns `se_eff`, `se_layer_details_json` may need to be added to the ORM if not present.

**Controlled vocabulary gates:**
- `cancer_validation_status` ∈ `{cancer_validated, cancer_adjacent, general_population}`
- `outcome_type` ∈ `{subjective, semi_objective, biomarker}`
- `endpoint_vs_change` ∈ `{endpoint, change, unclear}`

---

### ACTION 2 [P0]: Create `harmonization_rules.csv` seed

**Effort:** 2 hr  
**Status:** Seed loader already wired — `crci/database/seed_loader.py` line 212 maps `"harmonization_rules.csv"` → `(HarmonizationRule, "rule_id")` and line 251 includes it in `LOAD_ORDER`. The file just doesn't exist yet.

**File to create:** `crci/database/seeds/harmonization_rules.csv`

**Column schema** (must match ORM `HarmonizationRule` in `tables.py` line ~160):
```
rule_id,effect_type_reported,x_transform_required,y_transform_required,required_fields,output_scale,conversion_family,conversion_notes,version,active
```

**12 rules to seed** (derived from hardcoded logic in `conversion_router.py` lines 37–67 `_VALID_CONVERSIONS` + `scale_harmonizer.py` formulas):

| rule_id | effect_type_reported | required_fields | output_scale | conversion_family | Key formula |
|---------|---------------------|----------------|-------------|-------------------|-------------|
| `HR_STD_BETA_TO_SD_SD` | `std_beta` | `effect_value_reported,se_reported` | `SD_SD` | `std_beta_identity` | β already in SD/SD |
| `HR_UNSTD_BETA_SD_SD` | `unstd_beta` | `effect_value_reported,se_reported,sd_x,sd_y` | `SD_SD` | `unstd_beta_to_sd_sd` | β_sd = β_raw × SD_x / SD_y |
| `HR_UNSTD_BETA_PROXY` | `unstd_beta` | `effect_value_reported,se_reported,sd_x` | `PROXY_PER_SD` | `unstd_beta_to_proxy_per_sd` | β_proxy = β_raw × SD_x |
| `HR_OR_TO_SMD` | `OR` | `effect_value_reported,se_reported` | `SD_SD` | `or_to_smd` | d = ln(OR) × √3/π (S3-OR-SMD) |
| `HR_OR_TO_LOGOR` | `OR` | `effect_value_reported,se_reported` | `LOGOR_PER_SD` | `or_to_logor` | ln(OR) identity |
| `HR_HR_TO_LOGHR` | `HR` | `effect_value_reported,se_reported` | `LOGHR_PER_SD` | `hr_to_loghr` | ln(HR) identity |
| `HR_HR_TO_LOGOR` | `HR` | `effect_value_reported,se_reported` | `LOGOR_PER_SD` | `hr_to_logor` | OR ≈ HR (S3-HR-OR) |
| `HR_RR_TO_LOGOR` | `RR` | `effect_value_reported,se_reported,baseline_risk` | `LOGOR_PER_SD` | `rr_to_logor` | OR = RR×(1-p0)/(1-RR×p0) |
| `HR_R_TO_D` | `correlation_r` | `effect_value_reported` | `SD_SD` | `r_to_d` | d = 2r/√(1-r²) (S3-R-D) |
| `HR_GROUP_DIFF_SMD` | `group_diff` | `effect_value_reported,sd_pooled,n_treatment,n_control` | `SD_SD` | `group_diff_to_smd` | d = (M1-M2)/SD_pooled |
| `HR_COHENS_D_ID` | `cohens_d` | `effect_value_reported,se_reported` | `SD_SD` | `cohens_d_identity` | Already SMD |
| `HR_F_TO_D` | `F_statistic` | `effect_value_reported,n_treatment,n_control` | `SD_SD` | `f_to_d` | d = 2√(F/df_error) |

**After seeding:**
- Run `python scripts/load_seeds_sqlite.py` to verify it loads
- Eventually: refactor `conversion_router.py` to query `harmonization_rules_v1` instead of `_VALID_CONVERSIONS` dict (defer to P1 priority — current hardcodes are correct, this just adds auditability)

---

### ACTION 3 [P0]: Update P2 runner to propagate metadata into HarmonizedClaim

**Effort:** 3 hr  
**Status:** The `HarmonizedClaim` dataclass (in `crci/shared/models/intermediate_states.py` lines ~298–355) has 34 fields, but the constructor call in `crci/extraction/p2_harmonization/runner.py` lines 403–420 only populates 16 of them. The other 18 fields take defaults, many of which cause downstream distortion.

**File to modify:** `crci/extraction/p2_harmonization/runner.py`  
**Exact location:** Lines 403–420, the `HarmonizedClaim(...)` constructor

**Fields to add to the constructor call:**

```python
# Current (lines 403-420):
HarmonizedClaim(
    ler_id=ler_id,
    edge_relation_id=edge_relation_id,
    profile_id=profile_id,
    study_id=study_id,
    harmonized_beta=float(beta),
    harmonized_se=float(se) if se is not None else None,
    # ... 10 more fields ...
)

# ADD these fields to the constructor:
    study_design=_resolve_study_design(record, context),        # from record attr or context["classified_paper"]
    n_total=getattr(record, "n_total", None) or getattr(record, "n_effect", None),
    n_treatment=getattr(record, "n_treatment", None),
    n_control=getattr(record, "n_control", None),
    pub_year=_resolve_pub_year(record, context),                # from record or context["companion_meta"]["year"]
    cancer_validation_status=getattr(record, "cancer_validation_status", "general_population"),
    days_since_measurement=_resolve_temporal_lag(record),       # from alignment_lag_days or timepoint_weeks×7
    shared_control_flag=bool(getattr(record, "shared_control_flag", False)),
    endpoint_vs_change=getattr(record, "endpoint_vs_change", "unclear"),
    meta_source_flag=getattr(record, "meta_source_flag", False),
    se_derivation_level=getattr(record, "se_derivation_level", None),
    is_complete_for_p3=True,  # mark as complete since we populated everything
```

**Helper functions to create** (add above the constructor call in `runner.py`):

```python
def _resolve_study_design(record, context: dict) -> str:
    """Extract study_design from record or context, fallback to 'unclassified'."""
    # Priority: record attribute > classified_paper > context > default
    rd = getattr(record, "study_design", None)
    if rd and rd != "unclassified":
        return rd
    cp = context.get("classified_paper", {})
    if hasattr(cp, "study_design"):
        return cp.study_design
    if isinstance(cp, dict):
        return cp.get("study_design", "unclassified")
    return "unclassified"

def _resolve_pub_year(record, context: dict) -> int | None:
    """Extract pub_year from record or context metadata."""
    py = getattr(record, "pub_year", None)
    if py is not None:
        return int(py)
    meta = context.get("companion_meta", {})
    if isinstance(meta, dict) and "year" in meta:
        return int(meta["year"])
    return None

def _resolve_temporal_lag(record) -> float:
    """Convert timepoint_weeks or alignment_lag_days to days."""
    lag = getattr(record, "alignment_lag_days", None)
    if lag is not None:
        return float(lag)
    tw = getattr(record, "timepoint_weeks", None)
    if tw is not None:
        return float(tw) * 7.0
    return 0.0
```

**Impact of fix:** Without this change, P3 Layer 1 applies 3.0× SE inflation to ALL records (the "unclassified" penalty). With this fix, RCTs get 1.0×, prospective cohorts 1.5×, cross-sectional 2.0× — correctly differentiating evidence quality.

---

### ACTION 4 [P1]: Update extraction templates with mandatory fields

**Effort:** 2 hr  
**Status:** Two template versions exist. The canonical v1 template (`data/templates/edge_evidence_template.csv`) has 27 columns and is mostly aligned. The v2 template (`data/templates/edge_evidence_template_v2.csv`) has 32 columns with different names.

**Files to modify:**

| # | File | What to do |
|---|------|-----------|
| 4a | `data/templates/edge_evidence_template.csv` | Add 5 missing columns from §6.1: `outcome_type`, `alignment_lag_days`, `scope_cancer_match`, `scope_phase_match`, `scope_regimen_match`. The template already has `cancer_validation_status`, `shared_control_flag`, `endpoint_vs_change`. |
| 4b | `data/templates/edge_evidence_template_v2.csv` | **Deprecate** or align column names to match v1. This template uses incompatible names (`beta_raw` vs `effect_value_reported`, `se_raw` vs `se_reported`, `edge_id` vs `edge_relation_id`, etc.) |
| 4c | `EXTRACTION_PLAYBOOK.md` | Update the "Step 3: Fill templates" section to list the new mandatory fields with extraction instructions |
| 4d | LLM extraction prompts (in `crci/llm/prompts/`) | Add `MUST_EXTRACT` fields from §6.1 to the prompt templates so LLM-based extraction captures them |

**New columns to add to canonical template (4a):**

```csv
# Add after existing columns:
outcome_type          # {subjective, semi_objective, biomarker} — derive from measure type
alignment_lag_days    # Days between predictor and outcome (0 if concurrent)
timepoint_weeks       # Alternative: weeks from treatment start (extracted from paper timeline)
```

**Column name alignment table** (v2→v1 migration):

| v2 name (to deprecate) | v1 canonical name |
|------------------------|-------------------|
| `edge_id` | `edge_relation_id` |
| `beta_raw` | `effect_value_reported` |
| `se_raw` | `se_reported` |
| `sample_size` | `N_effect` |
| `instrument_id` | `upstream_instrument_id` |
| `confidence_note` | `notes` |
| `sd_treatment` | `sd_x` |
| `sd_control` | `sd_y` |
| `cancer_validated` | `cancer_validation_status` |
| `se_derivation_method` | `se_derivation_level` |
| `outcome_node_id` | (not needed — derive from edge's node_y) |

---

### ACTION 5 [P1]: Wire `scope_matching.py` into P2 runner

**Effort:** 2 hr  
**Status:** `crci/extraction/p2_harmonization/scope_matching.py` (271 lines) is fully implemented with `compute_scope_match()` and `compute_scope_match_batch()`. It returns `ScopeMatchResult` with `w_scope` (float). The P2 runner **never imports or calls it.**

**File to modify:** `crci/extraction/p2_harmonization/runner.py`

**Step-by-step:**

| # | Location | Change |
|---|----------|--------|
| 5a | runner.py line ~20 (imports) | Add: `from crci.extraction.p2_harmonization.scope_matching import compute_scope_match_batch, ScopeMatchResult` |
| 5b | runner.py lines ~430–440 (after HarmonizedClaim construction loop) | Add scope matching pass that reads `study_cohort_profiles_v1` from `context` and calls `compute_scope_match_batch()` |
| 5c | runner.py after scope computation | Write `w_scope` back to each `HarmonizedClaim` instance and also serialize to `scope_weights_json` on the `EdgeEvidence` DB row |

**Implementation sketch for 5b:**

```python
# After harmonized_claims list is built (line ~422):

# S6: Scope matching
target_pop = context.get("target_population", {
    "cancer": context.get("cancer_type", None),
    "phase": context.get("treatment_phase", None),
    "regimen": None,
    "age": None,
    "sex": None,
})

scope_records = []
for claim in harmonized_claims:
    # Look up study_cohort_profiles_v1 for this profile_id
    profile = _get_cohort_profile(session, claim.profile_id)
    scope_records.append({
        "ler_id": claim.ler_id,
        "study_population": {
            "cancer": getattr(profile, "cancer_type", None),
            "phase": getattr(profile, "treatment_phase", None),
            "regimen": None,
            "age": getattr(profile, "age_mean", None),
            "sex": getattr(profile, "sex_female_pct", None),
        },
    })

scope_results = compute_scope_match_batch(scope_records, target_pop)

# Write w_scope back to claims
scope_by_ler = {r.ler_id: r for r in scope_results}
for claim in harmonized_claims:
    sr = scope_by_ler.get(claim.ler_id)
    if sr:
        claim.w_scope = sr.w_scope  # NOTE: Need to add w_scope field to HarmonizedClaim
```

**Prerequisite:** `HarmonizedClaim` dataclass in `intermediate_states.py` may need a `w_scope: float = 1.0` field added (check if it's already there from Slice 8 additions).

---

### ACTION 6 [P1]: Create `harmonization_rule_proposals_v1` table + quarantine-on-missing-rule

**Effort:** 3 hr  
**Status:** When `conversion_router.py` encounters an unknown effect type, it returns `ConversionGateResult.BLOCKED` with a reason (line ~276), but there's no proposal mechanism. The record is simply dropped with a log warning.

**Files to create/modify:**

| # | File | What to do |
|---|------|-----------|
| 6a | Create `crci/database/schema/014_harmonization_rule_proposals.sql` | New table for rule proposals |
| 6b | `crci/shared/models/tables.py` | Add `HarmonizationRuleProposal` ORM class |
| 6c | `crci/extraction/p2_harmonization/conversion_router.py` | At CG1 BLOCKED (line ~276), instead of just logging, also write a proposal row |
| 6d | `crci/extraction/p2_harmonization/runner.py` | Accept proposals from conversion_router and write them to DB |

**6a — Table DDL:**

```sql
-- 014_harmonization_rule_proposals.sql
CREATE TABLE IF NOT EXISTS harmonization_rule_proposals_v1 (
    proposal_id             TEXT PRIMARY KEY,
    proposed_rule_id        TEXT NOT NULL,           -- suggested rule_id for harmonization_rules_v1
    effect_type_reported    TEXT NOT NULL,           -- the unknown effect type that triggered this
    x_transform_observed    TEXT,                    -- observed x transform from the record
    y_transform_observed    TEXT,                    -- observed y transform from the record
    available_fields_json   TEXT NOT NULL,           -- JSON: which fields are present on the record
    proposed_output_scale   TEXT,                    -- best-guess target scale
    proposed_conversion     TEXT,                    -- formula description / citation
    confidence              TEXT NOT NULL DEFAULT 'low',  -- {high, medium, low}
    provenance              TEXT,                    -- textbook/paper citation for proposed formula
    triggering_ler_ids_json TEXT NOT NULL DEFAULT '[]',   -- JSON array of ler_ids needing this rule
    triggering_study_ids    TEXT,                    -- comma-separated study_ids for context
    status                  TEXT NOT NULL DEFAULT 'pending',  -- {pending, approved, rejected, deferred}
    reviewed_by             TEXT,
    reviewed_at             TEXT,
    resolution_rule_id      TEXT,                    -- FK → harmonization_rules_v1.rule_id (if approved)
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    notes                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_hrp_status
    ON harmonization_rule_proposals_v1 (status)
    WHERE status = 'pending';
```

**6c — conversion_router.py modification (around line 276):**

```python
# Currently at CG1 BLOCKED:
blocked_reasons.append(f"CG1: no valid conversion path from {effect_type_reported} to {target_scale}")

# ADD after the blocked_reasons append:
# Generate a rule proposal for the unknown conversion
proposal = HarmonizationRuleProposal(
    effect_type_reported=effect_type_reported,
    x_transform_observed=getattr(validated.value, "x_transform", None),
    y_transform_observed=getattr(validated.value, "y_transform", None),
    available_fields=_inspect_available_fields(validated),
)
# Return proposal alongside the RoutedNumeric so the runner can persist it
```

**Key design decision:** The `route_conversion()` function should return the proposal as an optional attribute on `RoutedNumeric` (add `proposal: HarmonizationRuleProposal | None = None` field), rather than writing to DB directly (keep conversion_router.py DB-free).

---

### ACTION 7 [P2]: Backfill existing 4 papers with missing fields

**Effort:** 2 hr  
**Status:** 3 of 4 papers use the canonical 27-column template. Missing values need to be filled from paper knowledge.

**Files to modify:**

| Paper | File path | Known values to backfill |
|-------|-----------|-------------------------|
| Cherrier 2013 | `data/manual_uploads/structured/10.1016_j.lfs.2013.08.011/edge_evidence_template.csv` | `cancer_validation_status=cancer_validated` (prostate cancer survivors), `outcome_type=semi_objective` (cognitive tests), `alignment_lag_days=0`, `pub_year=2013` (verify already present) |
| Campbell 2017 | `data/manual_uploads/structured/10.1002_pon.4370/edge_evidence_template.csv` | `cancer_validation_status=cancer_validated` (breast cancer survivors), `outcome_type=semi_objective`, `alignment_lag_days=0`, `pub_year=2017` |
| Northey 2018 | `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/edge_evidence_template.csv` | **Major work** — only 12 columns. Must add 15 missing columns. See ACTION 8 for details. |
| Adam 2017 | `data/manual_uploads/structured/10.1016_j.psyneuen.2017.05.018/edge_evidence_template.csv` | `cancer_validation_status=general_population` (systematic review of HPA/cognition, mixed populations), `outcome_type=biomarker` (cortisol measures), `pub_year=2017` |

**For each paper, backfill this value checklist:**

```
□ study_design — verify correct value (RCT, meta_analysis, etc.)
□ cancer_validation_status — cancer_validated / cancer_adjacent / general_population
□ outcome_type — subjective / semi_objective / biomarker
□ pub_year — from paper header
□ alignment_lag_days — 0 for concurrent, or actual lag
□ n_treatment, n_control — from paper's methods section
□ shared_control_flag — 0 unless multi-arm trial
□ endpoint_vs_change — endpoint / change / unclear
□ rob_overall — low / some_concerns / high
□ covariates_adjusted — comma-separated list from paper's model specification
```

---

### ACTION 8 [P2]: Standardize Northey 2018 to canonical template

**Effort:** 1 hr  
**Status:** `10.1016_j.jsams.2018.11.026/edge_evidence_template.csv` has only 12 columns. All other papers have 27.

**File to modify:** `data/manual_uploads/structured/10.1016_j.jsams.2018.11.026/edge_evidence_template.csv`

**Column mapping from current → canonical:**

| Current 12-col name | Maps to canonical name | Notes |
|---------------------|----------------------|-------|
| `doi` | `doi` | keep |
| `edge_relation_id` | `edge_relation_id` | keep (already v1 name) |
| `effect_value_reported` | `effect_value_reported` | keep |
| `se_reported` | `se_reported` | keep |
| `effect_type_reported` | `effect_type_reported` | keep |
| `effect_size_type` | `effect_size_type` | keep |
| `N_effect` | `N_effect` | keep |
| `study_design` | `study_design` | keep (should be `meta_analysis`) |
| `cancer_type` | `cancer_type` | keep |
| `treatment_phase` | `treatment_phase` | keep |
| `upstream_instrument_id` | `upstream_instrument_id` | keep |
| `notes` | `notes` | keep |

**15 columns to ADD** (with values from the Northey 2018 meta-analysis paper):

```
ci_low_reported         — extract from paper Table 2 if available, else empty
ci_high_reported        — extract from paper Table 2 if available, else empty
p_value                 — extract from paper
n_treatment             — per meta-analysis arm N
n_control               — per meta-analysis arm N
sd_x                    — empty (meta-analysis doesn't report predictor SD)
sd_y                    — empty
cancer_validation_status — cancer_validated (meta of cancer exercise trials)
rob_overall             — low (Cochrane risk-of-bias done in paper)
pub_year                — 2018
covariates_adjusted     — empty (meta-analysis)
endpoint_vs_change      — change (SMD of change scores)
comparison_arm_label    — exercise vs. control
se_derivation_level     — reported (SE from meta-analysis)
shared_control_flag     — 0
extraction_snippet      — optional
```

---

### ACTION 9 [P3]: Build P7 compiler stubs ✅ ALREADY DONE

**Effort:** ~~4 hr~~ → **0 hr (no work needed)**  
**Status:** All 7 P7 compiler files **already exist and are fully implemented** (not stubs):

| File | Lines | Status |
|------|-------|--------|
| `crci/extraction/p7_compilers/runner.py` | 606 lines | Full orchestrator with DB queries, compiler dispatch |
| `crci/extraction/p7_compilers/psychometric_compiler.py` | Implemented | B10 → A4 (instruments) |
| `crci/extraction/p7_compilers/prior_compiler.py` | Implemented | B11 → C3 (node priors) |
| `crci/extraction/p7_compilers/temporal_compiler.py` | Implemented | B12 → A32 (kernels) |
| `crci/extraction/p7_compilers/dose_response_compiler.py` | Implemented | B13 → C2 (dose bridges) |
| `crci/extraction/p7_compilers/modifier_compiler.py` | Implemented | B14 → A16 (modifiers) |
| `crci/extraction/p7_compilers/synergy_compiler.py` | Implemented | factorial → synergy |

**Remaining work (reclassified to P2):** The compilers exist but their **input tables** (B10–B14) have sparse data. The real bottleneck is extracting auxiliary evidence templates from more papers, not building compiler code. See ACTION 7 for backfilling auxiliary templates.

---

### ACTION 10 [P3]: Implement GRADE assessment module

**Effort:** 4 hr  
**Status:** No formal GRADE assessment exists. P3 Layer 5 (`crci/extraction/p3_heterogeneity/layers.py` line ~317, function `layer_5_grade_quality()`) reads `grade_level` from `HarmonizedClaim`, but it's always `"MODERATE"` (default).

**Design Options:**

| Option | Description | Effort | Accuracy |
|--------|-------------|--------|----------|
| **A. Manual annotation** | Add `grade_level` column to extraction template; human assigns GRADE per paper | 1 hr code + ongoing curation effort | High |
| **B. Rule-based auto-GRADE** | Compute GRADE from existing fields: `study_design` + `rob_overall` + `N_effect` + `cancer_validation_status` | 3 hr | Medium |
| **C. LLM-assisted GRADE** | Prompt LLM with paper methods section to assign GRADE with justification | 4 hr | Medium-High |

**Recommended: Option B (rule-based) with Option A override**

**File to create:** `crci/extraction/p2_harmonization/grade_assessor.py`

**Core logic — simplified GRADE based on available fields:**

```python
def assess_grade(
    study_design: str,
    rob_overall: str | None,
    n_total: int | None,
    cancer_validation_status: str | None,
    has_blinding: bool | None = None,
    has_allocation_concealment: bool | None = None,
) -> str:
    """Rule-based GRADE assessment from extractable fields.
    
    GRADE starts at design default, downgrades for risk factors:
      RCT → starts HIGH
      Cohort/observational → starts LOW
      Cross-sectional → starts VERY_LOW
    
    Downgrade factors (-1 each):
      - rob_overall == "high"
      - n_total < 50
      - cancer_validation_status == "general_population"  
    
    Upgrade factors (+1 each, observational only):
      - Large effect (not assessable at this stage)
      - Dose-response gradient (not assessable)
    
    Returns: "HIGH" | "MODERATE" | "LOW" | "VERY_LOW"
    """
```

**Wire into P2 runner:**
- Call `assess_grade()` during HarmonizedClaim construction (ACTION 3)
- Set `grade_level=assess_grade(study_design, rob_overall, n_total, cancer_validation_status)`
- Allow manual override: if CSV has explicit `grade_level` column, use that instead

**Downstream impact:** P3 Layer 5 SE multipliers change from:
- Current: ALL records get 1.25× (MODERATE default)
- After fix: RCTs with low RoB get 1.00× (HIGH), observational get 1.50× (LOW), poor small studies get 2.00× (VERY_LOW)

---

### Summary — Revised Priority & Dependency Order

```
EXECUTION ORDER (respects dependencies):

  ACTION 1  ──→  Schema columns (must exist before data fills them)
       │
       ├── ACTION 2  ──→  Seed harmonization rules (independent)
       │
       ▼
  ACTION 3  ──→  P2 runner propagation (needs columns from A1)
       │
       ├── ACTION 10 ──→  GRADE assessor (wire into A3's changes)
       │
       ▼
  ACTION 5  ──→  Scope matching wiring (needs P2 runner changes from A3)
       │
       ▼
  ACTION 4  ──→  Template updates (align with new column set)
       │
       ▼
  ACTION 7  ──→  Backfill Cherrier/Campbell/Adam (use updated template)
       │
       ├── ACTION 8  ──→  Standardize Northey (extends A7)
       │
       ▼
  ACTION 6  ──→  Rule proposals table (can be done anytime, no deps)
       │
       ▼
  ACTION 9  ──→  ✅ ALREADY DONE (reclassify to "fill B10-B14 data")
```

**Total revised effort:** ~18 hrs (was 24 hrs; ACTION 9 eliminated)
