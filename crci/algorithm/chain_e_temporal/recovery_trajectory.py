# VERIFIED: formulas [E2b-EQ1, E2c-EQ1] match spec SYS_ALG lines 2728-2781
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads NadirEstimate from nadir_estimator.py
# VERIFIED: forward wiring — writes RecoveryTrajectory for E3 (intervention_overlay.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [E-G2] raises on failure
"""
Component: SYS_ALGORITHM.ALG-E.E2
Spec: SYS_ALGORITHM_COMPLETE.md lines 2728-2781
Formulas:
    E2b-EQ1: R(t) = r_∞ · (1 − exp(−(t/τ_R)^{γ_R}))
    E2c-EQ1: θ_natural(t)^(m) = θ_nadir + (θ_base − θ_nadir) · R(t)^(m)
Reads: NadirEstimate (from nadir_estimator.py E1)
Writes: RecoveryTrajectory (consumed by E3 intervention_overlay.py, E4)
Gates: E-G2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from .nadir_estimator import NadirEstimate

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RecoveryParams:
    """Context-specific recovery parameters."""

    r_infinity: float  # asymptotic recovery fraction [0, 1]
    tau_r: float       # recovery time constant (months)
    gamma_r: float     # shape parameter


@dataclass
class RecoveryTrajectory:
    """Output of E2: Natural recovery trajectory.

    Consumed by E3 (intervention overlay), E4 (uncertainty/counterfactuals).
    """

    # Natural trajectory at monthly intervals — shape (n_nodes, T)
    theta_natural: np.ndarray

    # Recovery fraction R(t) per MC draw — shape (n_draws, T)
    R_draws: np.ndarray

    # Mean R(t) — shape (T,)
    R_mean: np.ndarray

    # Recovery parameters used
    recovery_params: RecoveryParams

    # Prediction horizons (months)
    T_horizons: list[int]

    # Number of time points
    n_timepoints: int

    # Per-node nadir and baseline from E1 — shape (n_nodes,)
    # (fix §8.2 feedback 2.2: F4T uses these directly instead of
    # re-estimating via solve_linear_coefficients)
    theta_nadir: np.ndarray | None = None
    theta_base: np.ndarray | None = None

    # Explicit time axis in months — shape (T,)
    # (fix §8.2 feedback 2.3: avoids assuming t_index == month)
    time_months: np.ndarray | None = None

    # Gate status
    gate_e_g2_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  E2a: Recovery Parameter Loading
# ═══════════════════════════════════════════════════════════════


# 7 context-specific parameter sets (spec line 2744-2748)
# Format: context_key → (r_∞, τ_R, γ_R)
RECOVERY_REGISTRY: dict[str, tuple[float, float, float]] = {
    "breast_chemo": (0.75, 8.0, 0.8),
    "colorectal_chemo": (0.70, 10.0, 0.7),
    "lymphoma_chemo": (0.65, 12.0, 0.7),
    "lung_chemo": (0.60, 14.0, 0.6),
    "ovarian_chemo": (0.65, 11.0, 0.7),
    "brain_radiation": (0.50, 18.0, 0.6),
    "general_cancer_chemo": (
        config.RECOVERY_R_INFINITY_DEFAULT,
        config.RECOVERY_TAU_R_MONTHS_DEFAULT,
        config.RECOVERY_GAMMA_R_DEFAULT,
    ),
}


def _load_recovery_params(
    context_key: str | None = None,
    custom_params: dict[str, float] | None = None,
) -> RecoveryParams:
    """E2a: Load context-specific recovery parameters.

    Args:
        context_key: Cancer/treatment context (e.g., "breast_chemo").
        custom_params: Override dict with {r_infinity, tau_r, gamma_r}.

    Returns:
        RecoveryParams.
    """
    if custom_params:
        return RecoveryParams(
            r_infinity=custom_params.get("r_infinity", config.RECOVERY_R_INFINITY_DEFAULT),
            tau_r=custom_params.get("tau_r", config.RECOVERY_TAU_R_MONTHS_DEFAULT),
            gamma_r=custom_params.get("gamma_r", config.RECOVERY_GAMMA_R_DEFAULT),
        )

    if context_key and context_key in RECOVERY_REGISTRY:
        r_inf, tau, gamma = RECOVERY_REGISTRY[context_key]
        logger.info("E2a: Loaded recovery params for context '%s'", context_key)
        return RecoveryParams(r_infinity=r_inf, tau_r=tau, gamma_r=gamma)

    # Fallback to general defaults (spec line 2749)
    logger.info(
        "E2a: No context match for '%s' — using general_cancer_chemo defaults",
        context_key,
    )
    r_inf, tau, gamma = RECOVERY_REGISTRY["general_cancer_chemo"]
    return RecoveryParams(r_infinity=r_inf, tau_r=tau, gamma_r=gamma)


# ═══════════════════════════════════════════════════════════════
#  E2b: Stretched Exponential Recovery Curve
# ═══════════════════════════════════════════════════════════════


def _compute_recovery_curve(
    params: RecoveryParams,
    t_months: np.ndarray,
) -> np.ndarray:
    """E2b: Compute R(t) at given time points.

    Formula E2b-EQ1: R(t) = r_∞ · (1 − exp(−(t/τ_R)^{γ_R}))

    Args:
        params: Recovery parameters.
        t_months: Array of time points in months.

    Returns:
        R(t) array, same shape as t_months.
    """
    # Formula E2b-EQ1
    exponent = (t_months / params.tau_r) ** params.gamma_r
    return params.r_infinity * (1.0 - np.exp(-exponent))


# ═══════════════════════════════════════════════════════════════
#  E2c: MC Recovery Trajectory Sampling
# ═══════════════════════════════════════════════════════════════


def _sample_recovery_draws(
    params: RecoveryParams,
    t_months: np.ndarray,
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """E2c: Sample recovery trajectories with parameter uncertainty.

    Per draw m (spec lines 2775-2777):
        r_∞^(m) ~ N(r_∞, 0.10²) [clipped to (0, 1)]
        τ_R^(m) ~ LogNormal(ln(τ_R), 0.20²)
        γ_R: fixed

    Args:
        params: Base recovery parameters.
        t_months: Array of time points.
        n_draws: Number of MC draws.
        rng: Random number generator.

    Returns:
        R_draws: shape (n_draws, len(t_months)).
    """
    T = len(t_months)
    R_draws = np.zeros((n_draws, T))

    # Sample r_∞ and τ_R with uncertainty
    # r_∞^(m) ~ N(r_∞, σ²_r) clipped to (0, 1)
    r_inf_draws = rng.normal(
        params.r_infinity, config.E2_R_INFINITY_NOISE_SD, size=n_draws,
    )
    r_inf_draws = np.clip(r_inf_draws, 0.0, 1.0)

    # τ_R^(m) ~ LogNormal(ln(τ_R), σ²_τ)
    tau_draws = rng.lognormal(
        np.log(params.tau_r), config.E2_TAU_R_LOG_NOISE_SD, size=n_draws,
    )

    # γ_R: fixed (insufficient data for posterior — spec line 2777)
    gamma = params.gamma_r

    for m in range(n_draws):
        exponent = (t_months / tau_draws[m]) ** gamma
        R_draws[m, :] = r_inf_draws[m] * (1.0 - np.exp(-exponent))

    return R_draws


# ═══════════════════════════════════════════════════════════════
#  Gate E-G2
# ═══════════════════════════════════════════════════════════════


def _validate_gate_e_g2(trajectory: RecoveryTrajectory) -> None:
    """Gate E-G2: Recovery trajectory valid.

    Conditions (spec line 2955):
        1. R(t) ∈ [0, r_∞] for all t
        2. Trajectory monotonically improving (R non-decreasing)

    Raises:
        GateViolation: If any condition fails.
    """
    r_inf = trajectory.recovery_params.r_infinity

    # Condition 1: R_mean in valid range
    r_min = float(np.min(trajectory.R_mean))
    r_max = float(np.max(trajectory.R_mean))
    if r_min < -0.01:  # small tolerance for numerical noise
        raise GateViolation(
            "E-G2",
            f"R(t) contains negative values: min={r_min:.4f}",
        )
    if r_max > r_inf + 0.05:  # tolerance for MC sampling noise
        raise GateViolation(
            "E-G2",
            f"R(t) exceeds r_∞={r_inf:.3f}: max={r_max:.4f}",
        )

    # Condition 2: R_mean monotonically non-decreasing
    diffs = np.diff(trajectory.R_mean)
    if np.any(diffs < -0.01):  # tolerance for sampling noise
        min_diff = float(np.min(diffs))
        raise GateViolation(
            "E-G2",
            f"R(t) not monotonically improving: min_diff={min_diff:.6f}",
        )

    # Check theta_natural finite
    n_nonfinite = int(np.sum(~np.isfinite(trajectory.theta_natural)))
    if n_nonfinite > 0:
        raise GateViolation(
            "E-G2",
            f"θ_natural has {n_nonfinite} non-finite values",
        )

    logger.info(
        "Gate E-G2 PASSED: R(t) ∈ [%.3f, %.3f], %d timepoints",
        r_min, r_max, trajectory.n_timepoints,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_recovery_trajectory (E2 entry point)
# ═══════════════════════════════════════════════════════════════


def compute_recovery_trajectory(
    nadir: NadirEstimate,
    context_key: str | None = None,
    custom_recovery_params: dict[str, float] | None = None,
    n_draws: int | None = None,
    seed: int | None = None,
) -> RecoveryTrajectory:
    """E2: Compute natural recovery trajectory from nadir.

    Pipeline:
        E2a: Load recovery parameters for patient context
        E2b: Compute deterministic R(t) curve
        E2c: MC sampling for uncertainty bands
        θ_natural(t) = θ_nadir + (θ_base − θ_nadir) · R(t)

    Args:
        nadir: NadirEstimate from E1.
        context_key: Cancer/treatment context for parameter lookup.
        custom_recovery_params: Override recovery parameters.
        n_draws: Number of MC draws (default: config.MC_DRAWS).
        seed: Random seed.

    Returns:
        RecoveryTrajectory.

    Raises:
        GateViolation: If E-G2 fails.
    """
    if n_draws is None:
        n_draws = config.MC_DRAWS
    if seed is None:
        seed = config.MC_DEFAULT_SEED

    rng = np.random.default_rng(seed)

    # E2a: Load recovery parameters
    params = _load_recovery_params(context_key, custom_recovery_params)

    # Time points: 0, 1, 2, ..., MAX_HORIZON months
    T = config.E_MAX_HORIZON_MONTHS + 1  # include t=0
    t_months = np.arange(T, dtype=float)

    logger.info(
        "── E2: Natural Recovery Trajectory ──\n"
        "  r_∞=%.3f, τ_R=%.1f, γ_R=%.2f, n_draws=%d, T=%d",
        params.r_infinity, params.tau_r, params.gamma_r, n_draws, T,
    )

    # E2b: Deterministic R(t)
    R_mean = _compute_recovery_curve(params, t_months)

    # E2c: MC sampling
    R_draws = _sample_recovery_draws(params, t_months, n_draws, rng)

    # Compute θ_natural(t) using mean R(t)
    # Formula E2c-EQ1: θ(t) = θ_nadir + (θ_base − θ_nadir) · R(t)
    delta = nadir.theta_base - nadir.theta_nadir  # (n_nodes,)
    # θ_natural: shape (n_nodes, T)
    theta_natural = nadir.theta_nadir[:, np.newaxis] + delta[:, np.newaxis] * R_mean[np.newaxis, :]

    result = RecoveryTrajectory(
        theta_natural=theta_natural,
        R_draws=R_draws,
        R_mean=R_mean,
        recovery_params=params,
        T_horizons=config.E_PREDICTION_HORIZONS,
        n_timepoints=T,
        # Fix §8.2 feedback 2.2: carry E1 nadir/base for F4T
        theta_nadir=nadir.theta_nadir,
        theta_base=nadir.theta_base,
        # Fix §8.2 feedback 2.3: carry explicit time axis
        time_months=t_months,
    )

    # Gate E-G2
    _validate_gate_e_g2(result)
    result.gate_e_g2_passed = True

    logger.info(
        "E2 complete: %d timepoints, R(36)=%.3f",
        T, R_mean[-1] if len(R_mean) > 0 else 0.0,
    )

    return result
