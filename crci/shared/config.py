# VERIFIED: constants match FILE_CONTEXT_MANIFEST config.py entry
# VERIFIED: constants match SYS_EX lines 853-870, 1310-1320
# VERIFIED: constants match SYS_ALG lines 1298-1320, 3301-3310
# VERIFIED: imports — stdlib + dataclasses only
# VERIFIED: downstream — imported by every formula-implementing module
"""
Component: Layer 0 — Central Configuration
Spec: SYS_EXTRACTION lines 853-870 (P3 layer multipliers)
      SYS_EXTRACTION lines 1310-1320 (P4 formula constants)
      SYS_ALGORITHM lines 1298-1320 (σ²_struct, B2 constants)
      SYS_ALGORITHM lines 3301-3310 (worked example constants)
      FILE_CONTEXT_MANIFEST — config.py entry
Purpose: ALL numeric constants from specs, centralized.
         No formula parameter may be hardcoded outside this file.
Reads: Nothing (root configuration)
Writes: Nothing (imported by all downstream modules)
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
#  STRUCTURAL UNCERTAINTY (§2.6, §2.8)
# ═══════════════════════════════════════════════════════════════

# Formula P4-MA: σ²_struct default and ceiling
SIGMA_SQ_STRUCTURAL_DEFAULT: float = 0.25
SIGMA_SQ_STRUCTURAL_CEILING: float = 0.50

# Inclusion probability bounds
P_INCLUSION_ADJ_CAP: float = 1.0
P_INCLUSION_MIN: float = 0.05

# ═══════════════════════════════════════════════════════════════
#  EVIDENCE FRESHNESS (§2.9, Layer 7)
# ═══════════════════════════════════════════════════════════════

# Formula P3-7/B2-L7: w_fresh = max(FLOOR, 1 − DECAY × (REF_YEAR − pub_year))
# Calibration: Poynard et al. (2002) — 45-year half-life → ln(2)/45 ≈ 1.54%/yr
FRESHNESS_DECAY_RATE: float = 0.015
FRESHNESS_FLOOR: float = 0.70
FRESHNESS_REFERENCE_YEAR: int = 2025  # Spec lines 1091, 1307 all use 2025
FRESHNESS_DEFAULT_WEIGHT: float = 0.85  # No pub date → default w_fresh = 0.85 + WARN

# ═══════════════════════════════════════════════════════════════
#  TEMPORAL PARAMETERS
# ═══════════════════════════════════════════════════════════════

TEMPORAL_DECAY_RATE: float = 0.05
TEMPORAL_EXCLUSION_DAYS: int = 90
TEMPORAL_WEIGHT_FLOOR: float = 0.01  # max(w_temporal, 0.01) floor in Formula P3-6

# ═══════════════════════════════════════════════════════════════
#  MONTE CARLO SAMPLING (§2.16)
# ═══════════════════════════════════════════════════════════════

MC_DRAWS: int = 10_000
MC_DEFAULT_SEED: int = 42

# ═══════════════════════════════════════════════════════════════
#  SCOPE MATCHING (§2.9) — Formula P3-2: w_scope
# ═══════════════════════════════════════════════════════════════

# 5-dimensional scope weights (must sum to 1.0)
SCOPE_WEIGHTS: dict[str, float] = {
    "cancer": 0.35,
    "phase": 0.25,
    "regimen": 0.20,
    "age": 0.10,
    "sex": 0.10,
}

SCOPE_FLOOR: float = 0.3

# ═══════════════════════════════════════════════════════════════
#  SEVEN-LAYER SE SYSTEM (§2.9) — Formulas P3-1 through P3-7
# ═══════════════════════════════════════════════════════════════

# Layer 1: Study design multipliers — Formula P3-1
# Spec SYS_EX lines 765-790: 9 design categories + linear interpolation for small RCT
DESIGN_MULTIPLIERS: dict[str, float] = {
    "large_rct": 1.0,                   # N > 200
    "small_rct_default": 1.25,          # midpoint placeholder; actual via interpolation
    "well_adjusted_cohort": 1.5,
    "unadjusted_longitudinal": 2.0,
    "cross_sectional_adjusted": 2.5,
    "cross_sectional_unadjusted": 3.0,
    "animal_in_vivo": 4.0,
    "in_vitro_mechanistic": 5.0,
    "expert_opinion": 6.0,
}
DESIGN_MULTIPLIER_DEFAULT: float = 3.0       # unclassified → 3.0× + WARN
SMALL_RCT_N_THRESHOLD: int = 200             # N ≤ 200 triggers interpolation
SMALL_RCT_PENALTY_SLOPE: float = 0.5         # m = 1.0 + 0.5×(200−N)/200

# Layer 5: GRADE quality multipliers — Formula P3-5 / ALG-B2 L5
# REVIEW: SPEC AMBIGUITY — ALG-B chain card line 1305 says MODERATE=1.15, LOW=1.3.
#   SYS_EXTRACTION line 1089 and ALG-B worked example line 3857 say MODERATE=1.25, LOW=1.50.
#   Using 1.25/1.50 (majority across specs + worked example agreement).
GRADE_MULTIPLIERS: dict[str, float] = {
    "HIGH": 1.0,
    "MODERATE": 1.25,
    "LOW": 1.50,
    "VERY_LOW": 2.00,
}

# Layer 4: Measurement invariance / cancer validation multipliers — Formula P3-4 (§2.7)
SCALE_MULTIPLIERS: dict[str, float] = {
    "validated_cancer": 1.0,
    "used_cancer": 1.15,
    "general_population": 1.30,
    "known_somatic_confound": 1.50,
}

# ═══════════════════════════════════════════════════════════════
#  AGGREGATION PRIORITY SCORE (APS) — §2.5
# ═══════════════════════════════════════════════════════════════

APS_WEIGHTS: dict[str, float] = {
    "edge_gap": 0.35,
    "design": 0.20,
    "pop": 0.20,
    "recency": 0.15,
    "source": 0.10,
}

APS_THRESHOLD: float = 0.40

# ═══════════════════════════════════════════════════════════════
#  BAYESIAN UPDATE PARAMETERS (§2.8)
# ═══════════════════════════════════════════════════════════════

# Prior defaults for node estimation
PRIOR_MEAN_DEFAULT: float = 0.0
PRIOR_SD_DEFAULT: float = 1.0

# Posterior sigma floor and cap
MIN_SIGMA_FLOOR: float = 0.2
MAX_SIGMA_CAP: float = 5.0

# Conflict inflation
CONFLICT_INFLATION_K: float = 0.6
CONFLICT_INFLATION_MAX_MULT: float = 2.0

# Missingness inflation
MISSINGNESS_INFLATION_VAR_ADD: float = 0.25

# ═══════════════════════════════════════════════════════════════
#  HARMONIZATION — EX-P2 (§2.5)
# ═══════════════════════════════════════════════════════════════

# S1 — Plausibility bounds (Gate P2-G1)
PLAUSIBILITY_BETA_MAX: float = 5.0
PLAUSIBILITY_CORRELATION_MAX: float = 1.0

# S3 — Scale Harmonization: SD borrowing SE inflation tiers
SD_BORROW_TIER1_INFLATION: float = 1.0    # same population
SD_BORROW_TIER2_INFLATION: float = 1.15   # similar population
SD_BORROW_TIER3_INFLATION: float = 1.30   # general population

# S3 — Conversion formulas: mathematical constants
# OR→SMD: d = ln(OR) × √3 / π
CONVERSION_OR_TO_SMD_FACTOR: float = 0.5513288954217921  # √3/π

# S4 — Orientation Alignment (Gate P2-G2)
ORIENTATION_CONFIDENCE_THRESHOLD: float = 0.60

# S5 — Identification Status attenuation factors
IDENTIFICATION_FACTOR_IDENTIFIED: float = 1.00
IDENTIFICATION_FACTOR_PARTIAL: float = 0.85
IDENTIFICATION_FACTOR_PLAUSIBLE: float = 0.70
IDENTIFICATION_FACTOR_UNIDENTIFIED: float = 0.50

# S5 — Confounder coverage thresholds for identification upgrade/downgrade
CONFOUNDER_COVERAGE_UPGRADE_THRESHOLD: float = 0.80   # >= 80% → upgrade
CONFOUNDER_COVERAGE_DOWNGRADE_THRESHOLD: float = 0.30  # < 30% → downgrade

# SE derivation constant: SE = (upper - lower) / (2 × 1.96)
SE_FROM_CI_Z_MULTIPLIER: float = 1.96

# ═══════════════════════════════════════════════════════════════
#  RECONCILIATION CONFIDENCE (EX-P1-REC)
# ═══════════════════════════════════════════════════════════════

# Formula REC-d: conf = min(1.0, BASE + SUPPORT_N_WEIGHT×n + MEAN_CONF_WEIGHT×mean_confidence)
REC_CONFIDENCE_BASE: float = 0.3
REC_CONFIDENCE_SUPPORT_N_WEIGHT: float = 0.15
REC_CONFIDENCE_MEAN_CONF_WEIGHT: float = 0.2
REC_CONFIDENCE_CONFLICT_CAP: float = 0.50

# REC-b: Jaccard similarity threshold for merge candidates
REC_JACCARD_MERGE_THRESHOLD: float = 0.80

# AT-06: Speculative evidence confidence ceiling
ATB_SPECULATIVE_CONFIDENCE_CEILING: float = 0.50

# ═══════════════════════════════════════════════════════════════
#  TRUST BOUNDARY PLAUSIBILITY (EX-TB, §2.5)
# ═══════════════════════════════════════════════════════════════

# Gate TB-G2: Plausibility bounds for parsed numeric values
TB_PLAUSIBILITY_BETA_MAX: float = 5.0        # |β| ≤ 5
TB_PLAUSIBILITY_CORRELATION_MAX: float = 1.0  # |r| ≤ 1
TB_PLAUSIBILITY_P_VALUE_MIN: float = 0.0      # p ≥ 0
TB_PLAUSIBILITY_P_VALUE_MAX: float = 1.0      # p ≤ 1
TB_PLAUSIBILITY_N_MIN: int = 1                # N > 0
TB_PLAUSIBILITY_I_SQUARED_MAX: float = 100.0  # I² ≤ 100

# Rule NP-11: SE derivation from CI
# SE = (upper - lower) / (2 × 1.96)
TB_CI_TO_SE_Z_MULTIPLIER: float = 1.96

# Rule NP-02/NP-03: CI and p-value consistency thresholds
TB_P_VALUE_SIGNIFICANCE_THRESHOLD: float = 0.05

# ═══════════════════════════════════════════════════════════════
#  EVIDENCE GROUPER — P4-EG (§2.12)
# ═══════════════════════════════════════════════════════════════

# Diminishing returns: w_base × 1 / (1 + DIMINISHING_DECAY × ln(k))
EG_DIMINISHING_DECAY: float = 0.3

# Precision caps (fraction of best RCT SE)
EG_PRECISION_CAP_CROSS_SECTIONAL: float = 0.30  # cross-sect ≥ 30% best RCT
EG_PRECISION_CAP_ANIMAL: float = 0.10            # animal ≥ 10%

# ═══════════════════════════════════════════════════════════════
#  DOUBLE-COUNTING RESOLVER — P4-DCR (§2.12)
# ═══════════════════════════════════════════════════════════════

# Threshold pairs for dual-metric overlap decision
DCR_MINIMAL_OVERLAP_THRESHOLD: float = 0.10   # both < 0.10 → USE_MA_POOLED
DCR_HIGH_OVERLAP_THRESHOLD: float = 0.70       # either > 0.70 → USE_PRIMARIES
DCR_AMBIGUITY_THRESHOLD: float = 0.30          # disagree > 0.30 → AMBIGUOUS

# ═══════════════════════════════════════════════════════════════
#  META-ANALYSIS PARAMETERS (§2.12)
# ═══════════════════════════════════════════════════════════════

# Formula P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
# Formula P4-2: τ² (DerSimonian-Laird)
# Formula P4-3: I² heterogeneity
IVW_MIN_STUDIES: int = 2
HETEROGENEITY_HIGH_THRESHOLD: float = 75.0  # I² > 75% = high
HETEROGENEITY_MODERATE_THRESHOLD: float = 50.0  # I² 50-75% = moderate

# Formula B4-1 / P4-3: P_incl = logistic(INTERCEPT + LN_K_COEFF·ln(k+1) + Z_COEFF·Z + RCT_COEFF·𝟙_RCT)
# Used by ALG-B4 (structural inclusion probability)
P4_3_INTERCEPT: float = -0.5
P4_3_LN_K_COEFF: float = 1.2
P4_3_Z_COEFF: float = 0.4
P4_3_RCT_COEFF: float = 0.6

# Formula P4-3b / P4-MA-c: null_finding_context annotation adjustment
P4_3B_NULL_FINDING_POWERED_ADJ: float = -0.3

# P4-MA-c: σ²_structural annotation severity weights
# severity_weight: moderate=0.05, high=0.10, critical=0.15
ANNOTATION_SEVERITY_WEIGHTS: dict[str, float] = {
    "moderate": 0.05,
    "high": 0.10,
    "critical": 0.15,
}

# ═══════════════════════════════════════════════════════════════
#  PUBLICATION BIAS (§2.12.1)
# ═══════════════════════════════════════════════════════════════

PUB_BIAS_MIN_K_EGGER: int = 10
PUB_BIAS_EGGER_ALPHA: float = 0.10
PUB_BIAS_SE_INFLATION_LOW: float = 1.0
PUB_BIAS_SE_INFLATION_MODERATE: float = 1.15
PUB_BIAS_SE_INFLATION_HIGH: float = 1.30

# ═══════════════════════════════════════════════════════════════
#  CHAIN-VS-DIRECT VALIDATION (§2.13)
# ═══════════════════════════════════════════════════════════════

# Z-score triage thresholds
COHERENCE_Z_PASS: float = 1.5
COHERENCE_Z_MONITOR: float = 2.0
COHERENCE_Z_ALARM: float = 3.0

# SE inflation for coherence failures
COHERENCE_SE_INFLATION_MONITOR: float = 1.1
COHERENCE_SE_INFLATION_INVESTIGATE: float = 1.3
COHERENCE_SE_INFLATION_ALARM: float = 2.0

# ═══════════════════════════════════════════════════════════════
#  DOSE-RESPONSE (§2.6)
# ═══════════════════════════════════════════════════════════════

# Default Emax parameters
EMAX_DEFAULT_K: float = 150.0  # half-max dose
EMAX_DEFAULT_MAX: float = 1.0

# ═══════════════════════════════════════════════════════════════
#  SYNERGY (§2.16.1)
# ═══════════════════════════════════════════════════════════════

SYNERGY_GAMMA_CAP_DEFAULT: float = 0.40

# ═══════════════════════════════════════════════════════════════
#  P7 COMPILER PARAMETERS (SYS_EXTRACTION_ADDENDUM Part 6)
# ═══════════════════════════════════════════════════════════════

# Gate P7-G1: Every compiled α must be based on ≥1 study with N≥20
P7_MIN_N_FOR_ALPHA: int = 20

# Compiler 1 (psychometric): tau-equivalent assumption fallback
P7_DEFAULT_NUM_ITEMS: int = 10  # fallback if instrument num_items unknown

# Compiler 2 (prior): Level 4 uninformative prior SE inflation
P7_UNINFORMATIVE_SE_INFLATION: float = 2.0

# Compiler 3 (temporal): minimum timepoints for curve fitting
P7_MIN_TIMEPOINTS_CURVE: int = 3

# Gate P7-G3: Recovery parameter constraints
P7_RECOVERY_R_INF_MIN: float = 0.0
P7_RECOVERY_R_INF_MAX: float = 1.0
P7_RECOVERY_TAU_R_MIN: float = 0.0

# Compiler 4 (dose-response): minimum dose levels for Emax fitting
P7_MIN_DOSE_LEVELS_EMAX: int = 3
P7_HILL_COEFFICIENT_DEFAULT: float = 1.0
P7_EMAX_E0_DEFAULT: float = 0.0

# Gate P7-G4: Dose-response constraints
P7_HILL_MIN: float = 0.0
P7_ED50_MIN: float = 0.0

# Compiler 5 (modifier): ALG-C4b guardrails
P7_MODIFIER_CLAMP_LOW: float = 0.7
P7_MODIFIER_CLAMP_HIGH: float = 1.5

# Gate P7-G6: Synergy γ bounds
P7_SYNERGY_GAMMA_MIN: float = -1.0
P7_SYNERGY_GAMMA_MAX: float = 1.0

# Compiler 6 (synergy): γ classification thresholds
P7_SYNERGY_GAMMA_CLASSIFY_THRESHOLD: float = 0.05  # |γ| > 0.05 → non-additive

# ═══════════════════════════════════════════════════════════════
#  P5 CHAIN VALIDATION THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# FM5 nonlinearity ratio: chain_product > ratio × |direct_beta| → FM5
P5_FM5_NONLINEARITY_RATIO: float = 3.0

# ═══════════════════════════════════════════════════════════════
#  P6 DEPLOYMENT VALIDATION THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# G4: Plausible beta range
P6_BETA_MAX_PLAUSIBLE: float = 5.0

# G5: Maximum plausible SE
P6_SE_MAX_PLAUSIBLE: float = 10.0

# G12: High heterogeneity threshold for I²
P6_I_SQUARED_HIGH: float = 75.0

# ═══════════════════════════════════════════════════════════════
#  P4 PRIOR SELECTION — FALLBACK SE MULTIPLIERS (SYS_ALG line 3876)
# ═══════════════════════════════════════════════════════════════

# 4-level fallback SE multipliers
P4_FALLBACK_SE_MULTIPLIER_EXACT: float = 1.0
P4_FALLBACK_SE_MULTIPLIER_CANCER_TYPE: float = 1.2
P4_FALLBACK_SE_MULTIPLIER_GENERAL: float = 1.5
P4_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE: float = 2.0

# Mechanistic synthesis discount a₀ (95% discount)
P4_MECHANISTIC_SYNTH_DISCOUNT: float = 0.05

# ═══════════════════════════════════════════════════════════════
#  OPTIMIZATION (§2.16.3) — SAFE score
# ═══════════════════════════════════════════════════════════════

SAFE_MODE_A_DEFAULT_LAMBDA: float = 0.5  # burden penalty weight
SAFE_BOOTSTRAP_RESAMPLES: int = 1000
SAFE_STABILITY_THRESHOLD_STABLE: float = 0.80
SAFE_STABILITY_THRESHOLD_SOFT: float = 0.60

# ═══════════════════════════════════════════════════════════════
#  SEVERITY TIERS (§2.20)
# ═══════════════════════════════════════════════════════════════

# z-score → severity tier boundaries
SEVERITY_Z_BOUNDARIES: dict[str, tuple[float, float]] = {
    "Excellent": (-999.0, -1.0),
    "Good": (-1.0, -0.5),
    "Mild Concern": (-0.5, 0.0),
    "Moderate": (0.0, 0.5),
    "Poor": (0.5, 1.0),
    "Severe": (1.0, 999.0),
}

# ═══════════════════════════════════════════════════════════════
#  RECOVERY TRAJECTORIES (§2.18)
# ═══════════════════════════════════════════════════════════════

# Formula: R(t) = r∞ × (1 - exp(-(t/τ_R)^γ_R))
# Parameters are per-row in recovery_trajectories_v1; these are defaults
RECOVERY_R_INFINITY_DEFAULT: float = 0.70
RECOVERY_TAU_R_MONTHS_DEFAULT: float = 8.0
RECOVERY_GAMMA_R_DEFAULT: float = 0.8
ACC_FACTOR_DEFAULT: float = 2.0

# ═══════════════════════════════════════════════════════════════
#  ADAPTIVE QUESTIONING (§2.21)
# ═══════════════════════════════════════════════════════════════

VOI_MAX_QUESTIONS_DEFAULT: int = 6
VOI_MIN_EVSI_THRESHOLD: float = 0.01
VOI_MC_DRAWS: int = 400

# ═══════════════════════════════════════════════════════════════
#  E-VALUE / SENSITIVITY (§2.22)
# ═══════════════════════════════════════════════════════════════

# E-value formula: E = RR + sqrt(RR × (RR - 1))
# Where RR = exp(0.91 × |β|) for standardized effects
EVALUE_RR_CONVERSION_FACTOR: float = 0.91

# ═══════════════════════════════════════════════════════════════
#  SIMULATION PARAMETERS
# ═══════════════════════════════════════════════════════════════

DEFAULT_HORIZON_DAYS: int = 28
DEFAULT_TIME_STEP_UNIT: str = "day"

# ═══════════════════════════════════════════════════════════════
#  LOOP STABILITY (§2.11)
# ═══════════════════════════════════════════════════════════════

MAX_SPECTRAL_RADIUS: float = 1.0  # ρ(B) must be < 1 for stability
SPECTRAL_RADIUS_WARNING: float = 0.8  # warn if approaching instability

# Condition number thresholds (A4)
CONDITION_NUMBER_WARNING: float = 1e8   # κ(Λ) > 10⁸ → WARNING
CONDITION_NUMBER_CRITICAL: float = 1e10  # κ(Λ) > 10¹⁰ → CRITICAL (force path enumeration)

# ═══════════════════════════════════════════════════════════════
#  GRAPH ASSEMBLY — ALG-A (§2.6, §2.11, §2.17)
# ═══════════════════════════════════════════════════════════════

# A1: Expected node count
EXPECTED_NODE_COUNT: int = 63

# A2: Edge functional forms
EXPECTED_EDGE_COUNT_MIN: int = 100  # minimum edges for validation (actual registry may exceed 118)

# A3: Residual variance floor (§2.6)
# Formula A3-2: σ²_{ε,i} = max(1 − R²_i, RESIDUAL_VARIANCE_FLOOR)
RESIDUAL_VARIANCE_FLOOR: float = 0.05

# A3: Known residual correlation pairs (§2.17.2)
# Format: (node_a, node_b, rho, block_name, source)
RESIDUAL_CORRELATION_PAIRS: list[tuple[str, str, float, str, str]] = [
    ("NODE_BIO_IL6", "NODE_BIO_TNF", 0.65, "inflammatory", "Felger et al., 2020"),
    ("NODE_BIO_IL6", "NODE_BIO_CRP", 0.72, "inflammatory", "Felger et al., 2020"),
    ("NODE_BIO_TNF", "NODE_BIO_CRP", 0.58, "inflammatory", "Felger et al., 2020"),
    ("NODE_BIO_BDNF", "NODE_BIO_IL6", -0.35, "neuro_stress", "Ng et al., 2023"),
    ("NODE_BIO_CORTISOL", "NODE_BIO_IL6", 0.28, "neuro_stress", "Adam et al., 2017"),
    ("NODE_BIO_BDNF", "NODE_BIO_CORTISOL", -0.22, "neuro_stress", "Estimated"),
    ("NODE_BIO_MDA", "NODE_BIO_IL6", 0.38, "inflammatory", "Zhao et al., 2025 [VERIFY]"),
    ("NODE_BIO_NFL", "NODE_BIO_TNF", 0.31, "neuro_stress", "Schroyen et al., 2021"),
]

# A5b: Proxy validity R² thresholds and SE multiplier tiers (§2.17)
PROXY_R_SQ_HIGH_THRESHOLD: float = 0.5   # R² threshold for HIGH validity
PROXY_R_SQ_MODERATE_THRESHOLD: float = 0.3  # R² threshold for MODERATE
PROXY_R_SQ_LOW_THRESHOLD: float = 0.2   # R² threshold for LOW
PROXY_SE_MULTIPLIER_HIGH: float = 1.0    # R² ≥ 0.5
PROXY_SE_MULTIPLIER_MODERATE: float = 1.25  # R² 0.3–0.5
PROXY_SE_MULTIPLIER_LOW: float = 1.5     # R² 0.2–0.3
PROXY_SE_MULTIPLIER_VERY_LOW: float = 2.0  # R² < 0.2

# A2b: Secondary instrument loading factor
INSTRUMENT_SECONDARY_LOADING_FACTOR: float = 0.5

# S3: Conversion edge cases
PERFECT_CORRELATION_CLAMP_D: float = 10.0  # |d| cap when |r| ≥ 1.0
SE_DERIVATION_FALLBACK: float = 1.0        # Conservative SE fallback

# A5c: Feedback loop stability thresholds
FEEDBACK_GAIN_CRITICAL: float = 1.0   # gain ≥ 1 → CRITICAL: system unstable
FEEDBACK_GAIN_WARNING: float = 0.5    # gain > 0.5 → WARNING: slow convergence

# Node layer count (7 layers: 0-6)
NODE_LAYER_COUNT: int = 7

# ═══════════════════════════════════════════════════════════════
#  ALG-B: EDGE PARAMETERIZATION (§2.8, §2.9, §2.10, §2.13)
# ═══════════════════════════════════════════════════════════════

# B2: Temporal mismatch (Layer 6) — range 1.0–1.6×
B2_TEMPORAL_MISMATCH_MAX: float = 1.6
B2_TEMPORAL_MISMATCH_HALF_DAYS: float = 180.0  # halflife for SE inflation

# B3: RobustMAP prior (Schmidli et al., 2014)
# Formula: w = min(W_MAX, W_BASE + W_PER_K × k)
B3_ROBUST_MAP_W_BASE: float = 0.5
B3_ROBUST_MAP_W_PER_K: float = 0.06
B3_ROBUST_MAP_W_MAX: float = 0.8
B3_ROBUST_MAP_VAGUE_VAR: float = 100.0  # N(0, 10²)

# B3: Power Prior discount a₀ (Ibrahim & Chen, 2000)
# Calibration: Hackam & Redelmeier 2006 (~37% overall); Kola & Landis 2004 (CNS ~8%)
B3_POWER_PRIOR_A0: dict[str, float] = {
    "rct_same": 0.80,
    "rct_diff": 0.50,
    "cohort": 0.40,
    "observational": 0.30,
    "animal": 0.15,
    "mechanistic": 0.05,
}

# B3: Mechanistic Synthesis — enters as Power Prior with a₀ = 0.05 (95% discount)
B3_MECHANISTIC_SYNTH_A0: float = 0.05

# B3: Structural Placeholder variance: N(0, σ²) — wide to express ignorance
B3_STRUCTURAL_PLACEHOLDER_VAR: float = 100.0  # σ² = 10²

# B3: Commensurate prior (Hobbs et al., 2011) — k ∈ [2,4]
B3_COMMENSURATE_MIN_K: int = 2
B3_COMMENSURATE_MAX_K: int = 4

# B3: Design level threshold for RobustMAP ("best_design ≥ prospective")
# Designs at or above this level qualify
B3_PROSPECTIVE_DESIGNS: list[str] = [
    "large_rct", "small_rct_default", "well_adjusted_cohort",
    "unadjusted_longitudinal",
]

# B5: Turner et al. (2012) τ² prior distributions (14,886 meta-analyses)
# Subjective outcomes (self-reported cognition)
B5_TURNER_SUBJECTIVE_LOG_MU: float = -2.13
B5_TURNER_SUBJECTIVE_LOG_SIGMA: float = 1.58   # median τ² ≈ 0.12

# Semi-objective outcomes (neuropsych tests) & biomarkers
B5_TURNER_SEMIOBJECTIVE_LOG_MU: float = -2.56
B5_TURNER_SEMIOBJECTIVE_LOG_SIGMA: float = 1.07  # median τ² ≈ 0.08

# B6: Chain-vs-Direct Z-score triage thresholds
B6_Z_PASS: float = 1.5
B6_Z_MILD: float = 2.0
B6_Z_MODERATE: float = 3.0

# B6: SE multipliers for chain-vs-direct triage tiers
B6_SE_MULT_PASS: float = 1.0
B6_SE_MULT_MILD: float = 1.2
B6_SE_MULT_MODERATE: float = 1.5
B6_SE_MULT_SUBSTANTIAL: float = 2.0

# B6: Alignment Validity formula: AV(e) = 1 − min(Z/DIVISOR, 1.0)
B6_AV_Z_DIVISOR: float = 3.0

# B7: Number of context-matched prior specifications
B7_N_CONTEXT_SPECS: int = 33

# ═══════════════════════════════════════════════════════════════
#  DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

DB_SCHEMA_VERSION: int = 1
DB_DEFAULT_BATCH_SIZE: int = 500

# ═══════════════════════════════════════════════════════════════
#  LLM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

LLM_MAX_RETRIES: int = 3
LLM_RETRY_BASE_DELAY_SECONDS: float = 2.0
LLM_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"
LLM_DEFAULT_MAX_TOKENS: int = 4096

# LLM cost estimation (approx. Claude Sonnet per 1M tokens)
LLM_PROMPT_COST_PER_M: float = 3.0
LLM_COMPLETION_COST_PER_M: float = 15.0

# ═══════════════════════════════════════════════════════════════
#  AUTOMATED RETRIEVAL (AUTOMATED_RETRIEVAL_PLAN.md Part 9)
# ═══════════════════════════════════════════════════════════════

# Daily budget caps
RETRIEVAL_MAX_QUERIES_PER_DAY: int = 500
RETRIEVAL_MAX_CANDIDATES_SCORED_PER_DAY: int = 2000
RETRIEVAL_MAX_FULLTEXT_PER_DAY: int = 100
RETRIEVAL_MAX_EXTRACTIONS_PER_DAY: int = 50
RETRIEVAL_MAX_LLM_COST_USD_PER_DAY: float = 20.0

# Per-source rate limits (requests per second)
PUBMED_RPS: int = 3          # 10 with API key
CROSSREF_RPS: int = 50
OPENALEX_RPS: int = 10
EUROPE_PMC_RPS: int = 5
UNPAYWALL_RPD: int = 100_000  # per day
UNPAYWALL_RPS_THROTTLE: float = 10.0  # per-second throttle for base adapter interface

# Full-text source priority order
FULLTEXT_SOURCE_PRIORITY: list[str] = [
    "europe_pmc", "unpaywall", "manual", "abstract_only",
]

# Acquisition loop
ACQUISITION_LOOP_HOURS: int = 6
AUTHOR_GAP_BOOST_MULTIPLIER: float = 1.5

# Workstream priority (higher = searched first)
WORKSTREAM_PRIORITY: list[str] = [
    "instrument_psychometrics",
    "population_norms",
    "edge_evidence",
    "context_priors",
    "recovery_parameters",
    "intervention_kernels",
    "correlations",
]


@dataclass(frozen=True)
class CRCIConfig:
    """Immutable configuration object aggregating all constants.

    Use this when you need to pass configuration as a single object
    rather than importing individual constants.
    """

    # Structural uncertainty
    sigma_sq_structural_default: float = SIGMA_SQ_STRUCTURAL_DEFAULT
    sigma_sq_structural_ceiling: float = SIGMA_SQ_STRUCTURAL_CEILING
    p_inclusion_adj_cap: float = P_INCLUSION_ADJ_CAP
    p_inclusion_min: float = P_INCLUSION_MIN

    # Freshness
    freshness_decay_rate: float = FRESHNESS_DECAY_RATE
    freshness_floor: float = FRESHNESS_FLOOR
    freshness_reference_year: int = FRESHNESS_REFERENCE_YEAR

    # Temporal
    temporal_decay_rate: float = TEMPORAL_DECAY_RATE
    temporal_exclusion_days: int = TEMPORAL_EXCLUSION_DAYS

    # MC
    mc_draws: int = MC_DRAWS
    mc_default_seed: int = MC_DEFAULT_SEED

    # Scope
    scope_weights: dict[str, float] = field(default_factory=lambda: dict(SCOPE_WEIGHTS))
    scope_floor: float = SCOPE_FLOOR

    # Bayesian update
    prior_mean_default: float = PRIOR_MEAN_DEFAULT
    prior_sd_default: float = PRIOR_SD_DEFAULT
    min_sigma_floor: float = MIN_SIGMA_FLOOR
    max_sigma_cap: float = MAX_SIGMA_CAP

    # Simulation
    default_horizon_days: int = DEFAULT_HORIZON_DAYS
    default_time_step_unit: str = DEFAULT_TIME_STEP_UNIT
