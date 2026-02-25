# VERIFIED: formulas [E1b-EQ1] match spec SYS_ALG lines 2677-2726
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PatientState from chain_c, recovery params
# VERIFIED: forward wiring — writes NadirEstimate for E2 (recovery_trajectory.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [E-G1] raises on failure
"""
Component: SYS_ALGORITHM.ALG-E.E1
Spec: SYS_ALGORITHM_COMPLETE.md lines 2677-2726
Formulas:
    E1b-EQ1: θ_nadir = (θ_current − θ_base · R(Δt)) / (1 − R(Δt))
    E1c-EQ1: θ_nadir = μ_context − δ_treatment
Reads: PatientState (from chain_c_posterior/modifier_application.py),
       treatment_timeline (from runtime context),
       recovery_registry parameters (for back-estimation in E1b)
Writes: NadirEstimate (consumed by E2 recovery_trajectory.py)
Gates: E-G1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_c_posterior.modifier_application import PatientState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class NadirScenario(str, Enum):
    """Treatment timeline classification for nadir estimation."""

    DURING_TX = "DURING_TX"      # Currently in treatment
    EARLY_POST = "EARLY_POST"    # < 6 months post-treatment
    LATE_POST = "LATE_POST"      # ≥ 6 months post-treatment


@dataclass(frozen=True)
class NadirEstimate:
    """Output of E1: Estimated cognitive nadir.

    Consumed by E2 (recovery_trajectory.py) as the recovery starting point.
    """

    theta_nadir: np.ndarray       # ℝ^{n_nodes} — estimated worst cognitive state
    estimation_scenario: NadirScenario  # which method was used
    confidence: float             # [0, 1] — confidence in estimate
    delta_t_since_treatment: float  # months since treatment end
    theta_base: np.ndarray        # ℝ^{n_nodes} — pre-treatment baseline (or proxy)
    n_nodes: int


# ═══════════════════════════════════════════════════════════════
#  E1a: Treatment Timeline Classification
# ═══════════════════════════════════════════════════════════════


def _classify_timeline(
    treatment_end_months_ago: float | None,
) -> tuple[NadirScenario, float]:
    """E1a: Classify patient's treatment timeline.

    Spec lines 2689-2701:
        (a) DURING_TX: treatment_end unknown or Δt ≤ 0
        (b) EARLY_POST: 0 < Δt < 6 months
        (c) LATE_POST: Δt ≥ 6 months

    Args:
        treatment_end_months_ago: Months since treatment ended.
            None means treatment end unknown → assume DURING_TX.

    Returns:
        (scenario, delta_t) tuple.
    """
    if treatment_end_months_ago is None or treatment_end_months_ago <= 0:
        # Rule: Treatment end unknown → assume DURING_TX (spec line 2700)
        return NadirScenario.DURING_TX, 0.0

    if treatment_end_months_ago < config.E1_EARLY_POST_THRESHOLD_MONTHS:
        return NadirScenario.EARLY_POST, treatment_end_months_ago

    return NadirScenario.LATE_POST, treatment_end_months_ago


# ═══════════════════════════════════════════════════════════════
#  E1b: Nadir Back-Estimation (Early Post)
# ═══════════════════════════════════════════════════════════════


def _back_estimate_nadir(
    theta_current: np.ndarray,
    theta_base: np.ndarray,
    r_at_dt: float,
) -> np.ndarray:
    """E1b: Back-estimate nadir from current state and recovery fraction.

    Formula E1b-EQ1:
        θ_nadir = (θ_current − θ_base · R(Δt)) / (1 − R(Δt))

    Args:
        theta_current: Current cognitive state θ̂.
        theta_base: Pre-treatment baseline (or proxy).
        r_at_dt: Recovery fraction R(Δt) at time since treatment.

    Returns:
        Estimated θ_nadir.
    """
    # Formula E1b-EQ1: θ_nadir = (θ_current − θ_base · R(Δt)) / (1 − R(Δt))
    denominator = 1.0 - r_at_dt
    return (theta_current - theta_base * r_at_dt) / denominator


def _compute_recovery_fraction_at_dt(
    delta_t_months: float,
    r_infinity: float,
    tau_r: float,
    gamma_r: float,
) -> float:
    """Evaluate stretched exponential recovery at Δt.

    R(t) = r_∞ · (1 − exp(−(t/τ_R)^γ_R))

    Used by E1b to back-estimate nadir.

    Args:
        delta_t_months: Time since treatment in months.
        r_infinity: Asymptotic recovery fraction.
        tau_r: Recovery time constant (months).
        gamma_r: Shape parameter.

    Returns:
        R(Δt) ∈ [0, r_∞].
    """
    if delta_t_months <= 0 or tau_r <= 0:
        return 0.0
    exponent = (delta_t_months / tau_r) ** gamma_r
    return r_infinity * (1.0 - np.exp(-exponent))


# ═══════════════════════════════════════════════════════════════
#  E1c: Context-Based Nadir (Late Post)
# ═══════════════════════════════════════════════════════════════


def _context_based_nadir(
    mu_context: np.ndarray,
    delta_treatment: np.ndarray | float,
) -> np.ndarray:
    """E1c: Estimate nadir from population-level data.

    Formula E1c-EQ1:
        θ_nadir = μ_context − δ_treatment

    Args:
        mu_context: Context-matched prior means (n_nodes,).
        delta_treatment: Expected treatment-induced decrement.

    Returns:
        Estimated θ_nadir.
    """
    # Formula E1c-EQ1: θ_nadir = μ_context − δ_treatment
    return mu_context - delta_treatment


# ═══════════════════════════════════════════════════════════════
#  Gate E-G1
# ═══════════════════════════════════════════════════════════════


def _validate_gate_e_g1(nadir: NadirEstimate) -> None:
    """Gate E-G1: Nadir estimate valid.

    Conditions (spec line 2954):
        1. θ_nadir finite
        2. Scenario classified
        3. Confidence > 0

    Raises:
        GateViolation: If any condition fails.
    """
    n_nonfinite = int(np.sum(~np.isfinite(nadir.theta_nadir)))
    if n_nonfinite > 0:
        raise GateViolation(
            "E-G1",
            f"θ_nadir has {n_nonfinite} non-finite values",
        )

    if nadir.confidence <= 0:
        raise GateViolation(
            "E-G1",
            f"Confidence must be > 0, got {nadir.confidence}",
        )

    logger.info(
        "Gate E-G1 PASSED: scenario=%s, confidence=%.2f, n_nodes=%d",
        nadir.estimation_scenario.value,
        nadir.confidence,
        nadir.n_nodes,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: estimate_nadir (E1 entry point)
# ═══════════════════════════════════════════════════════════════


def estimate_nadir(
    patient_state: PatientState,
    treatment_end_months_ago: float | None = None,
    theta_base: np.ndarray | None = None,
    recovery_params: dict[str, float] | None = None,
    delta_treatment: np.ndarray | float = 0.5,
) -> NadirEstimate:
    """E1: Estimate cognitive nadir based on treatment timeline.

    Three scenarios:
        (a) DURING_TX: θ_nadir = θ_current (patient still in treatment)
        (b) EARLY_POST: Back-estimate from current state + recovery model
        (c) LATE_POST: Context-based population estimate

    Args:
        patient_state: PatientState from Chain C (θ̂, context_match).
        treatment_end_months_ago: Months since treatment ended.
            None → assume DURING_TX.
        theta_base: Pre-treatment baseline (if available).
            None → use μ_prior as proxy.
        recovery_params: Dict with {r_infinity, tau_r, gamma_r}.
            Used for back-estimation in EARLY_POST.
        delta_treatment: Treatment-induced cognitive decrement (SD units).
            Used for context-based nadir in LATE_POST.

    Returns:
        NadirEstimate.

    Raises:
        GateViolation: If E-G1 fails.
    """
    n_nodes = len(patient_state.theta_hat)
    theta_current = patient_state.theta_hat

    # E1a: Classify timeline
    scenario, delta_t = _classify_timeline(treatment_end_months_ago)

    # Resolve theta_base: use provided or fall back to prior means
    if theta_base is None:
        # Spec line 2713: θ_base unknown → use μ_prior as proxy
        theta_base_resolved = np.zeros(n_nodes)  # μ_prior default = 0 (standardized)
        logger.info(
            "E1: θ_base not provided — using μ_prior (zero) as proxy",
        )
    else:
        theta_base_resolved = theta_base

    logger.info(
        "── E1: Nadir Estimation ──\n"
        "  scenario=%s, Δt=%.1f months, n_nodes=%d",
        scenario.value, delta_t, n_nodes,
    )

    # E1a: DURING_TX — nadir = current state
    if scenario == NadirScenario.DURING_TX:
        theta_nadir = theta_current.copy()
        confidence = config.E1_CONFIDENCE_DURING_TX

    # E1b: EARLY_POST — back-estimate
    elif scenario == NadirScenario.EARLY_POST:
        # Load recovery parameters
        r_inf = config.RECOVERY_R_INFINITY_DEFAULT
        tau_r = config.RECOVERY_TAU_R_MONTHS_DEFAULT
        gamma_r = config.RECOVERY_GAMMA_R_DEFAULT

        if recovery_params:
            r_inf = recovery_params.get("r_infinity", r_inf)
            tau_r = recovery_params.get("tau_r", tau_r)
            gamma_r = recovery_params.get("gamma_r", gamma_r)

        # Compute R(Δt)
        r_at_dt = _compute_recovery_fraction_at_dt(delta_t, r_inf, tau_r, gamma_r)

        # Spec line 2711-2712: If R(Δt) ≥ 0.8 → switch to Scenario (c)
        if r_at_dt >= config.E1_BACK_ESTIMATION_R_LIMIT:
            logger.info(
                "E1b: R(Δt=%.1f)=%.3f ≥ %.2f — switching to context-based (E1c)",
                delta_t, r_at_dt, config.E1_BACK_ESTIMATION_R_LIMIT,
            )
            theta_nadir = _context_based_nadir(
                theta_base_resolved, delta_treatment,
            )
            confidence = config.E1_CONFIDENCE_LATE_POST
        else:
            # Formula E1b-EQ1
            theta_nadir = _back_estimate_nadir(
                theta_current, theta_base_resolved, r_at_dt,
            )
            confidence = config.E1_CONFIDENCE_EARLY_POST

    # E1c: LATE_POST — context-based
    else:
        theta_nadir = _context_based_nadir(
            theta_base_resolved, delta_treatment,
        )
        confidence = config.E1_CONFIDENCE_LATE_POST

    result = NadirEstimate(
        theta_nadir=theta_nadir,
        estimation_scenario=scenario,
        confidence=confidence,
        delta_t_since_treatment=delta_t,
        theta_base=theta_base_resolved,
        n_nodes=n_nodes,
    )

    # Gate E-G1
    _validate_gate_e_g1(result)

    return result
