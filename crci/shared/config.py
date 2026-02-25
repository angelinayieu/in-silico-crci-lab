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

# Formula P3-8: w_freshness = max(FLOOR, exp(-DECAY × age_years))
FRESHNESS_DECAY_RATE: float = 0.015
FRESHNESS_FLOOR: float = 0.70
FRESHNESS_REFERENCE_YEAR: int = 2026
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

# Layer 5: GRADE quality multipliers — Formula P3-5
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
#  PRIOR SELECTION — EX-P4-PS (SYS_EX lines 1264-1275, SYS_ALG lines 1326-1350)
# ═══════════════════════════════════════════════════════════════

# Decision tree thresholds — spec SYS_EX lines 1268-1272
PRIOR_K_THRESHOLD_ROBUST_MAP: int = 5
PRIOR_K_THRESHOLD_COMMENSURATE_LOW: int = 2
PRIOR_K_THRESHOLD_COMMENSURATE_HIGH: int = 4
PRIOR_K_THRESHOLD_POWER: int = 1
PRIOR_MIN_RCTS_FOR_ROBUST_MAP: int = 2

# RobustMAP formula: w = min(0.8, 0.5 + 0.06k)
# Spec SYS_ALG lines 1346 (B3a)
PRIOR_ROBUST_MAP_W_BASE: float = 0.5
PRIOR_ROBUST_MAP_W_PER_K: float = 0.06
PRIOR_ROBUST_MAP_W_CAP: float = 0.8
PRIOR_ROBUST_MAP_VAGUE_VAR: float = 100.0  # N(0, 10^2)

# Power prior discount factors — spec SYS_ALG lines 1348 (B3c)
# Design → a_0 discount
PRIOR_POWER_DISCOUNT: dict[str, float] = {
    "RCT_same": 0.80,
    "RCT_diff": 0.50,
    "cohort": 0.40,
    "observational": 0.30,
    "animal": 0.15,
    "mechanistic": 0.05,
}

# Mechanistic synthesis discount — spec SYS_ALG lines 1349 (B3d)
PRIOR_MECHANISTIC_SYNTH_DISCOUNT: float = 0.05

# 4-level fallback SE multipliers — spec SYS_ALG line 3876
PRIOR_FALLBACK_SE_MULTIPLIER_EXACT: float = 1.0
PRIOR_FALLBACK_SE_MULTIPLIER_CANCER_TYPE: float = 1.2
PRIOR_FALLBACK_SE_MULTIPLIER_GENERAL: float = 1.5
PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE: float = 2.0

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
#  SE DERIVATION CASCADE (CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4)
# ═══════════════════════════════════════════════════════════════

# Inflation factors per SE derivation level
SE_CASCADE_INFLATION_L1: float = 1.00     # SE reported directly
SE_CASCADE_INFLATION_L2A: float = 1.00    # 95% CI → SE
SE_CASCADE_INFLATION_L2B: float = 1.00    # 99% CI → SE
SE_CASCADE_INFLATION_L2C: float = 1.00    # 90% CI → SE
SE_CASCADE_INFLATION_L3A: float = 1.05    # Exact p-value + effect → SE
SE_CASCADE_INFLATION_L3B: float = 1.10    # Bounded p (e.g. p<0.05) → SE
SE_CASCADE_INFLATION_L4A: float = 1.15    # N per group + d → SE
SE_CASCADE_INFLATION_L4B: float = 1.20    # Total N only + d (assume n₁=n₂=N/2) → SE
SE_CASCADE_INFLATION_L5_T1: float = 1.15  # SD borrowed, Tier 1 (same population)
SE_CASCADE_INFLATION_L5_T2: float = 1.30  # SD borrowed, Tier 2 (similar population)
SE_CASCADE_INFLATION_L5_T3: float = 1.50  # SD borrowed, Tier 3 (general population)

# CI divisors for different confidence levels (z-multiplier × 2)
SE_CI_DIVISOR_95: float = 3.92   # 2 × 1.96
SE_CI_DIVISOR_99: float = 5.152  # 2 × 2.576
SE_CI_DIVISOR_90: float = 3.290  # 2 × 1.645

# ═══════════════════════════════════════════════════════════════
#  CONVERSION VALIDITY MATRIX (CONVERSION_VALIDITY_AND_HARDENING.md Module 1)
# ═══════════════════════════════════════════════════════════════

# Hasselblad & Hedges OR→d conversion factor: √3/π ≈ 0.5513
CONVERSION_OR_TO_D_FACTOR: float = 0.5513288954217921

# SE inflation for missing fields (fallback paths)
CONVERSION_SE_INFLATION_MISSING_GROUP_N: float = 1.10   # d from d, using total N/2
CONVERSION_SE_INFLATION_MISSING_R_PREPOST: float = 1.30  # paired t with default r=0.5
CONVERSION_SE_INFLATION_ETA_APPROX: float = 1.20         # η² total used as partial approx
CONVERSION_SE_INFLATION_CHI2_APPROX: float = 1.20        # χ² without cell counts
CONVERSION_SE_INFLATION_SPEARMAN: float = 1.06           # Spearman ρ treated as Pearson r

# Default pre-post correlation for paired designs (when unknown)
CONVERSION_DEFAULT_R_PREPOST: float = 0.50

# Change score ↔ endpoint conversion SE inflation (when ρ unknown, Module 4.3)
CS_UNKNOWN_RHO_SE_INFLATION: float = 1.20
CS_DEFAULT_RHO: float = 0.50
CS_MAJORITY_FRACTION: float = 2.0 / 3.0  # ≥2/3 for majority rule

# ═══════════════════════════════════════════════════════════════
#  FAMILY-SPECIFIC FRESHNESS (CONVERSION_VALIDITY_AND_HARDENING.md Module 5)
# ═══════════════════════════════════════════════════════════════

# {family: (decay_per_year, floor)}
FRESHNESS_FAMILY_POLICIES: dict[str, tuple[float, float]] = {
    "psychometrics": (0.000, 1.00),
    "normative_data": (0.005, 0.90),
    "biological_correlations": (0.005, 0.90),
    "edge_intervention": (0.015, 0.70),
    "edge_mechanism": (0.010, 0.80),
    "intervention_kernels": (0.020, 0.70),
    "context_priors": (0.010, 0.80),
    "meta_analysis_pooled": (0.015, 0.70),
    "recovery_curves": (0.010, 0.80),
}

# Supersession penalty for psychometrics/MAs when newer better-matched record exists
FRESHNESS_SUPERSESSION_PENALTY: float = 0.70
FRESHNESS_SUPERSESSION_MIN_N_RATIO: float = 0.50  # newer N ≥ older N × 0.50

# ═══════════════════════════════════════════════════════════════
#  VERIFICATION ESCALATION (CONVERSION_VALIDITY_AND_HARDENING.md Module 2)
# ═══════════════════════════════════════════════════════════════

# E1: Majority IVW weight threshold
ESCALATION_E1_WEIGHT_THRESHOLD: float = 0.50

# E2: Minimum studies for pooling protection
ESCALATION_E2_MIN_K: int = 3

# E4: Maximum k for sole-cancer-match escalation
ESCALATION_E4_MAX_K: int = 5

# E5: SE derivation level threshold (L4a and above → soft SE)
ESCALATION_E5_SE_LEVEL_THRESHOLD: str = "L4a"
ESCALATION_E5_WEIGHT_THRESHOLD: float = 0.30

# Unverified inflation applied to escalated records until verified
ESCALATION_UNVERIFIED_SE_INFLATION: float = 1.20

# ═══════════════════════════════════════════════════════════════
#  RECONCILIATION CONFIDENCE (EX-P1-REC)
# ═══════════════════════════════════════════════════════════════

# Formula REC-d: conf = min(1.0, BASE + SUPPORT_N_WEIGHT×n + MEAN_CONF_WEIGHT×mean_confidence)
REC_CONFIDENCE_BASE: float = 0.3
REC_CONFIDENCE_SUPPORT_N_WEIGHT: float = 0.15
REC_CONFIDENCE_MEAN_CONF_WEIGHT: float = 0.2
REC_CONFIDENCE_CONFLICT_CAP: float = 0.50

# REC-d: evidence_strength → confidence float mapping for formula REC-d
REC_STRENGTH_TO_CONFIDENCE: dict[str, float] = {
    "strong": 0.9,
    "moderate": 0.7,
    "weak": 0.4,
    "speculative": 0.2,
}
REC_STRENGTH_TO_CONFIDENCE_DEFAULT: float = 0.5

# REC-b: Jaccard similarity threshold for merge candidates
REC_JACCARD_MERGE_THRESHOLD: float = 0.80

# AT-06: Speculative evidence confidence ceiling
ATB_SPECULATIVE_CONFIDENCE_CEILING: float = 0.50

# ═══════════════════════════════════════════════════════════════
#  ANNOTATION PROMOTION THRESHOLDS (EX-PROM, §A.3)
# ═══════════════════════════════════════════════════════════════
# min_confidence thresholds by impact tier
# High-impact (affects sigma^2_structural directly): requires human review
PROM_CONFIDENCE_HIGH_IMPACT: float = 0.70
# Medium-high (DAG expansion, confounder structure): moderate threshold
PROM_CONFIDENCE_MEDIUM_HIGH: float = 0.65
# Medium (SE inflation, temporal, dose, effect modification)
PROM_CONFIDENCE_MEDIUM: float = 0.60
# Medium-low (scope, adherence, replication, cross-validation)
PROM_CONFIDENCE_MEDIUM_LOW: float = 0.55
# Low (research gap, adverse event, theory, clinical significance)
PROM_CONFIDENCE_LOW: float = 0.50

# min_cross_agent_n thresholds
PROM_CROSS_AGENT_HIGH_IMPACT: int = 2   # High-impact categories
PROM_CROSS_AGENT_DEFAULT: int = 1       # All other categories

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

# Formula P4-3: P_incl = logistic(INTERCEPT + LN_K_COEFF·ln(k+1) + Z_COEFF·Z + RCT_COEFF·𝟙_RCT)
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

# v2.0: Abstract screening (MS §9.2.1)
ABSTRACT_SCREENING_MIN_KEYWORDS: int = 2
ABSTRACT_SCREENING_CANCER_KEYWORDS: list[str] = [
    "cancer", "tumor", "tumour", "oncology", "carcinoma", "malignancy",
    "neoplasm", "chemotherapy", "radiation", "survivor",
]
ABSTRACT_SCREENING_COGNITIVE_KEYWORDS: list[str] = [
    "cognit", "memory", "attention", "executive function", "processing speed",
    "brain fog", "chemo brain", "chemobrain", "neuropsychol", "neurocognit",
]

# v2.0: Saturation detection (MS §9.7)
SATURATION_NOVELTY_THRESHOLD: float = 0.10
SATURATION_MIN_CYCLES: int = 3
SATURATION_MAX_CYCLES: int = 20

# v2.0: Content-driven hops (MS §9.4)
HOP_MAX_DEPTH: int = 2
HOP_CITATION_APS_BOOST: float = 0.15

# v2.0: ID cross-resolution
ID_RESOLVER_CROSSREF_TIMEOUT_S: int = 10
ID_RESOLVER_PUBMED_TIMEOUT_S: int = 10

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
