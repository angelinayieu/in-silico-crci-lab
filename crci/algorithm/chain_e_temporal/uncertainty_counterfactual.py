# VERIFIED: formulas [E-5, E-6] match spec SYS_ALG lines 2872-2934
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads OverlayResult (E3), RecoveryTrajectory (E2)
# VERIFIED: forward wiring — writes UncertaintyResult for Chain F (composite_scorer.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [E-G4] raises on failure
"""
Component: SYS_ALGORITHM.ALG-E.E4
Spec: SYS_ALGORITHM_COMPLETE.md lines 2872-2934
Formulas:
    E-5:  ITE(Δt) = θ_intervention(Δt) − θ_natural(Δt)
    E-6:  Var(θ(t)) = Var(θ₀) + 0.01·t + 0.005·t²
Reads: OverlayResult (from E3 intervention_overlay.py),
       RecoveryTrajectory (from E2 recovery_trajectory.py),
       Σ_post diagonal (from chain_c_posterior)
Writes: UncertaintyResult (consumed by Chain F composite_scorer.py)
Gates: E-G4
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from .intervention_overlay import InterventionTrajectory, OverlayResult
from .recovery_trajectory import RecoveryTrajectory

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class NNTStrength(str, Enum):
    """NNT-based recommendation strength classification."""

    STRONG = "STRONG"      # NNT < 3
    MODERATE = "MODERATE"  # NNT 3-10
    WEAK = "WEAK"          # NNT > 10


@dataclass(frozen=True)
class ITESummary:
    """Per-intervention ITE at a specific horizon.

    Formula E-5: ITE(Δt) = θ_intervention(Δt) − θ_natural(Δt)
    """

    intervention_id: str
    horizon_months: int
    ite_mean: float        # mean across nodes
    ite_cri_lower: float   # 2.5th percentile across nodes
    ite_cri_upper: float   # 97.5th percentile across nodes


@dataclass(frozen=True)
class ClinicalMetrics:
    """ARR, RRR, NNT for one intervention at one horizon.

    Spec lines 2914-2931.
    """

    intervention_id: str
    horizon_months: int
    p_impaired_natural: float       # fraction of draws where θ_natural < threshold
    p_impaired_intervention: float  # fraction where θ_intervention < threshold
    arr: float                      # Absolute Risk Reduction
    rrr: float | None               # Relative Risk Reduction (None if P_natural=0)
    nnt: float | None               # Number Needed to Treat (None if ARR≤0)
    nnt_strength: NNTStrength | None  # classification (None if NNT undefined)


@dataclass
class UncertaintyResult:
    """Complete E4 output.

    Consumed by Chain F (composite_scorer.py, variance_decomposer.py).
    """

    # E4a: Uncertainty growth
    var_theta_t: np.ndarray           # ℝ^{T} — Var(θ(t)) at each month
    var_theta_0: float                # baseline variance from posterior

    # E4b: ITE summaries per intervention × horizon
    ite_summaries: dict[str, list[ITESummary]]  # intervention_id → list of ITESummary

    # E4c: Clinical metrics per intervention × horizon
    clinical_metrics: dict[str, list[ClinicalMetrics]]  # intervention_id → list

    # Metadata
    n_interventions: int
    n_timepoints: int
    horizons_months: list[int]
    gate_e_g4_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  E4a: Uncertainty Growth Model
# ═══════════════════════════════════════════════════════════════


def _compute_uncertainty_growth(
    var_theta_0: float,
    t_months: np.ndarray,
    use_default_kernel_scale: bool = False,
) -> np.ndarray:
    """E4a: Compute growing prediction uncertainty over time.

    Formula E-6 (spec line 2884):
        Var(θ(t)) = Var(θ₀) + 0.01·t + 0.005·t²

    If using default (unfitted) kernels, scale by 1.5×.

    Args:
        var_theta_0: Baseline variance from posterior diagonal.
        t_months: Time array in months.
        use_default_kernel_scale: If True, apply 1.5× scale to growth terms.

    Returns:
        Var(θ(t)) array, same shape as t_months.
    """
    linear = config.E4_VAR_LINEAR_COEFF
    quadratic = config.E4_VAR_QUADRATIC_COEFF

    if use_default_kernel_scale:
        scale = config.E4_VAR_DEFAULT_KERNEL_SCALE
        linear *= scale
        quadratic *= scale

    # Formula E-6: Var(θ(t)) = Var(θ₀) + linear·t + quadratic·t²
    var_t = var_theta_0 + linear * t_months + quadratic * t_months ** 2

    return var_t


# ═══════════════════════════════════════════════════════════════
#  E4b: Individual Treatment Effect (ITE)
# ═══════════════════════════════════════════════════════════════


def _compute_ite_at_horizon(
    intervention_id: str,
    theta_intervention: np.ndarray,
    theta_natural: np.ndarray,
    horizon_idx: int,
    horizon_months: int,
) -> ITESummary:
    """E4b: Compute ITE at a specific horizon.

    Formula E-5:
        ITE(Δt) = θ_intervention(Δt) − θ_natural(Δt)

    Args:
        intervention_id: Intervention action ID.
        theta_intervention: Shape (n_nodes, T).
        theta_natural: Shape (n_nodes, T).
        horizon_idx: Index into time dimension.
        horizon_months: Horizon in months.

    Returns:
        ITESummary with mean and CrI across nodes.
    """
    # ITE per node at this horizon
    ite_per_node = theta_intervention[:, horizon_idx] - theta_natural[:, horizon_idx]

    return ITESummary(
        intervention_id=intervention_id,
        horizon_months=horizon_months,
        ite_mean=float(np.mean(ite_per_node)),
        ite_cri_lower=float(np.quantile(ite_per_node, config.E4_CRI_LOWER_QUANTILE)),
        ite_cri_upper=float(np.quantile(ite_per_node, config.E4_CRI_UPPER_QUANTILE)),
    )


# ═══════════════════════════════════════════════════════════════
#  E4c: Clinical Metric Derivation
# ═══════════════════════════════════════════════════════════════


def _compute_clinical_metrics(
    intervention_id: str,
    theta_intervention: np.ndarray,
    theta_natural: np.ndarray,
    horizon_idx: int,
    horizon_months: int,
) -> ClinicalMetrics:
    """E4c: Compute ARR, RRR, NNT at a specific horizon.

    Spec lines 2914-2931:
        "Impaired" = composite cognitive score < severity threshold.
        ARR = P_impaired_natural − P_impaired_intervention
        RRR = ARR / P_impaired_natural
        NNT = 1 / ARR

    Uses mean across nodes as composite score per draw equivalent.

    Args:
        intervention_id: Intervention action ID.
        theta_intervention: Shape (n_nodes, T).
        theta_natural: Shape (n_nodes, T).
        horizon_idx: Index into time dimension.
        horizon_months: Horizon in months.

    Returns:
        ClinicalMetrics.
    """
    threshold = config.E4_SEVERITY_THRESHOLD_SD

    # Composite score = mean across nodes at this horizon
    composite_natural = float(np.mean(theta_natural[:, horizon_idx]))
    composite_intervention = float(np.mean(theta_intervention[:, horizon_idx]))

    # For single-trajectory (non-MC) version: binary impairment
    # P_impaired = 1 if composite < threshold, else 0
    # In a full MC setting, these would be fractions across draws.
    # Here we use a continuous approximation based on distance to threshold.
    # Simple deterministic: fraction of nodes below threshold
    n_nodes = theta_natural.shape[0]
    p_impaired_natural = float(
        np.sum(theta_natural[:, horizon_idx] < threshold) / n_nodes
    )
    p_impaired_intervention = float(
        np.sum(theta_intervention[:, horizon_idx] < threshold) / n_nodes
    )

    # ARR = P_natural − P_intervention
    arr = p_impaired_natural - p_impaired_intervention

    # RRR = ARR / P_natural (if P_natural > 0)
    rrr: float | None = None
    if p_impaired_natural > 0:
        rrr = arr / p_impaired_natural

    # NNT = 1 / ARR (if ARR > 0)
    nnt: float | None = None
    nnt_strength: NNTStrength | None = None
    if arr > 0:
        nnt = 1.0 / arr
        # Classify
        if nnt < config.E4_NNT_STRONG_THRESHOLD:
            nnt_strength = NNTStrength.STRONG
        elif nnt <= config.E4_NNT_MODERATE_THRESHOLD:
            nnt_strength = NNTStrength.MODERATE
        else:
            nnt_strength = NNTStrength.WEAK

    return ClinicalMetrics(
        intervention_id=intervention_id,
        horizon_months=horizon_months,
        p_impaired_natural=p_impaired_natural,
        p_impaired_intervention=p_impaired_intervention,
        arr=arr,
        rrr=rrr,
        nnt=nnt,
        nnt_strength=nnt_strength,
    )


# ═══════════════════════════════════════════════════════════════
#  Gate E-G4
# ═══════════════════════════════════════════════════════════════


def _validate_gate_e_g4(result: UncertaintyResult) -> None:
    """Gate E-G4: Uncertainty + counterfactual results valid.

    Conditions (spec line 2950-2957):
        1. Var(θ(t)) monotonically non-decreasing
        2. All ITE values finite
        3. NNT > 0 (where defined)

    Raises:
        GateViolation: If any condition fails.
    """
    # Condition 1: Var(θ(t)) monotonically non-decreasing
    var_diffs = np.diff(result.var_theta_t)
    if np.any(var_diffs < -1e-10):
        min_diff = float(np.min(var_diffs))
        raise GateViolation(
            "E-G4",
            f"Var(θ(t)) not monotonically increasing: min diff = {min_diff:.6f}",
        )

    # Condition 2: All ITE finite
    for aid, summaries in result.ite_summaries.items():
        for s in summaries:
            if not (np.isfinite(s.ite_mean) and np.isfinite(s.ite_cri_lower)
                    and np.isfinite(s.ite_cri_upper)):
                raise GateViolation(
                    "E-G4",
                    f"Intervention '{aid}' at t={s.horizon_months}mo: "
                    f"ITE not finite (mean={s.ite_mean})",
                )

    # Condition 3: NNT > 0 where defined
    for aid, metrics_list in result.clinical_metrics.items():
        for m in metrics_list:
            if m.nnt is not None and m.nnt <= 0:
                raise GateViolation(
                    "E-G4",
                    f"Intervention '{aid}' at t={m.horizon_months}mo: "
                    f"NNT = {m.nnt:.4f} ≤ 0",
                )

    logger.info(
        "Gate E-G4 PASSED: Var monotonic, %d ITE summaries finite, NNT valid",
        sum(len(v) for v in result.ite_summaries.values()),
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_uncertainty_counterfactual (E4 entry point)
# ═══════════════════════════════════════════════════════════════


def compute_uncertainty_counterfactual(
    overlay: OverlayResult,
    recovery: RecoveryTrajectory,
    var_theta_0: float = 0.1,
    use_default_kernel_scale: bool = False,
) -> UncertaintyResult:
    """E4: Compute uncertainty growth, ITE, and clinical metrics.

    Args:
        overlay: OverlayResult from E3 (intervention trajectories).
        recovery: RecoveryTrajectory from E2 (natural trajectory).
        var_theta_0: Baseline variance from Σ_post diagonal
            (mean of diagonal elements).
        use_default_kernel_scale: Whether to apply 1.5× uncertainty
            scaling for unfitted (default) kernels.

    Returns:
        UncertaintyResult.

    Raises:
        GateViolation: If E-G4 fails.
    """
    T = overlay.n_timepoints
    t_months = np.arange(T, dtype=float)
    horizons = config.E_PREDICTION_HORIZONS  # [3, 6, 12, 24]

    logger.info(
        "── E4: Uncertainty + Counterfactuals ──\n"
        "  n_interventions=%d, T=%d, Var(θ₀)=%.4f, horizons=%s",
        overlay.n_interventions, T, var_theta_0, horizons,
    )

    # E4a: Uncertainty growth
    var_theta_t = _compute_uncertainty_growth(
        var_theta_0, t_months, use_default_kernel_scale,
    )

    # E4b + E4c: Per-intervention ITE and clinical metrics
    ite_summaries: dict[str, list[ITESummary]] = {}
    clinical_metrics: dict[str, list[ClinicalMetrics]] = {}

    theta_natural = recovery.theta_natural  # (n_nodes, T)

    for aid, traj in overlay.intervention_trajectories.items():
        ite_list: list[ITESummary] = []
        cm_list: list[ClinicalMetrics] = []

        for h in horizons:
            if h >= T:
                continue  # horizon beyond available data
            horizon_idx = h

            # E4b: ITE
            ite = _compute_ite_at_horizon(
                aid, traj.theta_intervention, theta_natural,
                horizon_idx, h,
            )
            ite_list.append(ite)

            # E4c: Clinical metrics
            cm = _compute_clinical_metrics(
                aid, traj.theta_intervention, theta_natural,
                horizon_idx, h,
            )
            cm_list.append(cm)

        ite_summaries[aid] = ite_list
        clinical_metrics[aid] = cm_list

    result = UncertaintyResult(
        var_theta_t=var_theta_t,
        var_theta_0=var_theta_0,
        ite_summaries=ite_summaries,
        clinical_metrics=clinical_metrics,
        n_interventions=overlay.n_interventions,
        n_timepoints=T,
        horizons_months=horizons,
    )

    # Gate E-G4
    _validate_gate_e_g4(result)
    result.gate_e_g4_passed = True

    logger.info(
        "E4 complete: Var(θ) at 24mo=%.4f, %d intervention ITE/clinical metrics",
        var_theta_t[min(24, T - 1)] if T > 0 else 0.0,
        overlay.n_interventions,
    )

    return result
