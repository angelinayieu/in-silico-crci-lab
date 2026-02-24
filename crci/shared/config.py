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

# ═══════════════════════════════════════════════════════════════
#  TEMPORAL PARAMETERS
# ═══════════════════════════════════════════════════════════════

TEMPORAL_DECAY_RATE: float = 0.05
TEMPORAL_EXCLUSION_DAYS: int = 90

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
DESIGN_MULTIPLIERS: dict[str, float] = {
    "large_rct": 1.0,
    "small_rct": 1.25,
    "cohort": 1.75,
    "cross_sectional": 3.0,
    "animal": 4.5,
    "expert": 6.0,
}

# Layer 3: GRADE quality multipliers — Formula P3-3
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
#  META-ANALYSIS PARAMETERS (§2.12)
# ═══════════════════════════════════════════════════════════════

# Formula P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
# Formula P4-2: τ² (DerSimonian-Laird)
# Formula P4-3: I² heterogeneity
IVW_MIN_STUDIES: int = 2
HETEROGENEITY_HIGH_THRESHOLD: float = 75.0  # I² > 75% = high
HETEROGENEITY_MODERATE_THRESHOLD: float = 50.0  # I² 50-75% = moderate

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
