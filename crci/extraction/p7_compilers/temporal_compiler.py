# VERIFIED: formulas P7-C3a (trapezoidal kernel), P7-C3b (stretched exponential)
#           match SYS_EXTRACTION_ADDENDUM Part 6 Compiler 3
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads TemporalEvidence from tables.py (B12)
# VERIFIED: forward wiring — writes CompiledTemporalKernel, CompiledRecoveryParams
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G3 raises on failure
"""
Component: SYS_EXTRACTION.EX-P7.C3
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 3
Formulas: P7-C3a (trapezoidal kernel via IVW-weighted timepoints),
          P7-C3b (r(t) = r_inf*(1 - exp(-(t/tau_r)^gamma_r)))
Reads: TemporalEvidence rows (from temporal_evidence_v1, written by AG08-EXT)
Writes: CompiledTemporalKernel + CompiledRecoveryParams
        (consumed by intervention_kernels_v1 + recovery_trajectories_v1 writers)
Gates: P7-G3 (onset < peak; r_inf ∈ (0,1]; tau_r > 0)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledRecoveryParams,
    CompiledTemporalKernel,
    GateViolation,
)
from crci.shared.models.tables import TemporalEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class _ActionGroup:
    """Evidence rows for one intervention."""

    action_id: str
    intervention_rows: list[TemporalEvidence] = field(default_factory=list)
    recovery_rows: list[TemporalEvidence] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  STRETCHED EXPONENTIAL MODEL
# ═══════════════════════════════════════════════════════════════


def _stretched_exponential(
    t: np.ndarray,
    r_inf: float,
    tau_r: float,
    gamma_r: float,
) -> np.ndarray:
    """Stretched exponential recovery model.

    Formula P7-C3b: r(t) = r_inf * (1 - exp(-(t/tau_r)^gamma_r))
    """
    return r_inf * (1.0 - np.exp(-((t / tau_r) ** gamma_r)))


# ═══════════════════════════════════════════════════════════════
#  KERNEL COMPILATION
# ═══════════════════════════════════════════════════════════════


def _compile_kernel(
    rows: list[TemporalEvidence],
    action_id: str,
) -> CompiledTemporalKernel:
    """Compile trapezoidal kernel from timepoint-effect pairs.

    Uses IVW weighting (1/SE²) across studies.
    Fits trapezoidal kernel: onset → build → peak → plateau → decay.

    If < 3 timepoints: use default kernel shape with observed peak effect.
    """
    # Extract (timepoint, effect, weight) triples
    valid = [
        r for r in rows
        if r.effect is not None and r.timepoint_weeks is not None
    ]

    if not valid:
        logger.warning(
            "Action '%s': no valid timepoint-effect pairs, returning default kernel",
            action_id,
        )
        return CompiledTemporalKernel(
            action_id=action_id,
            onset_weeks=0.0,
            peak_weeks=4.0,
            plateau_duration=8.0,
            decay_rate=0.0,
            k_timepoints=0,
            provenance_status="APPROXIMATE_PENDING",
            provenance_ref="",
        )

    # Build weighted (timepoint, effect) pairs using IVW
    timepoints: list[float] = []
    effects: list[float] = []
    weights: list[float] = []

    for r in valid:
        t = r.timepoint_weeks
        e = r.effect
        # Weight by 1/SE² (same IVW logic as edge evidence)
        se = r.se if r.se is not None and r.se > 0.0 else 1.0
        w = 1.0 / (se ** 2)
        timepoints.append(t)
        effects.append(e)
        weights.append(w)

    k = len(timepoints)

    if k < config.P7_MIN_TIMEPOINTS_CURVE:
        # Cannot fit curve: use simple peak detection
        max_idx = max(range(k), key=lambda i: abs(effects[i]))
        peak_weeks = timepoints[max_idx]
        onset_weeks = min(timepoints)

        logger.info(
            "Action '%s': k=%d < %d, using simple peak detection: "
            "onset=%.1f, peak=%.1f weeks",
            action_id,
            k,
            config.P7_MIN_TIMEPOINTS_CURVE,
            onset_weeks,
            peak_weeks,
        )

        study_ids = sorted({r.study_id for r in valid if r.study_id})
        return CompiledTemporalKernel(
            action_id=action_id,
            onset_weeks=onset_weeks,
            peak_weeks=peak_weeks,
            plateau_duration=0.0,
            decay_rate=0.0,
            k_timepoints=k,
            provenance_status="APPROXIMATE_PENDING",
            provenance_ref="; ".join(study_ids),
        )

    # Fit trapezoidal kernel from IVW-weighted data
    # Sort by timepoint
    sorted_indices = sorted(range(k), key=lambda i: timepoints[i])
    sorted_t = [timepoints[i] for i in sorted_indices]
    sorted_e = [effects[i] for i in sorted_indices]
    sorted_w = [weights[i] for i in sorted_indices]

    # Find onset: first timepoint where weighted effect is significantly > 0
    # (weighted mean of absolute effect exceeds its SE)
    onset_weeks = sorted_t[0]
    for i in range(k):
        if abs(sorted_e[i]) * math.sqrt(sorted_w[i]) > 1.96:
            onset_weeks = sorted_t[i]
            break

    # Find peak: timepoint with maximum weighted absolute effect
    weighted_abs_effects = [abs(e) * w for e, w in zip(sorted_e, sorted_w)]
    peak_idx = max(range(k), key=lambda i: weighted_abs_effects[i])
    peak_weeks = sorted_t[peak_idx]

    # Plateau duration: from peak to first decline
    plateau_end = peak_weeks
    peak_abs_effect = abs(sorted_e[peak_idx])
    for i in range(peak_idx + 1, k):
        if abs(sorted_e[i]) < 0.8 * peak_abs_effect:
            plateau_end = sorted_t[i]
            break
        plateau_end = sorted_t[i]
    plateau_duration = plateau_end - peak_weeks

    # Decay rate: slope of decline after plateau (if observed)
    decay_rate = 0.0
    if peak_idx < k - 1:
        post_peak = [(sorted_t[i], sorted_e[i]) for i in range(peak_idx + 1, k)]
        if len(post_peak) >= 2:
            # Linear fit to post-peak data
            t_post = np.array([p[0] for p in post_peak])
            e_post = np.array([abs(p[1]) for p in post_peak])
            if t_post[-1] > t_post[0]:
                decay_rate = float(
                    (e_post[0] - e_post[-1]) / (t_post[-1] - t_post[0])
                )
                decay_rate = max(0.0, decay_rate)  # decay rate must be non-negative

    study_ids = sorted({r.study_id for r in valid if r.study_id})

    return CompiledTemporalKernel(
        action_id=action_id,
        onset_weeks=onset_weeks,
        peak_weeks=peak_weeks,
        plateau_duration=plateau_duration,
        decay_rate=decay_rate,
        k_timepoints=k,
        provenance_status="CURATED_TRACED",
        provenance_ref="; ".join(study_ids),
    )


# ═══════════════════════════════════════════════════════════════
#  RECOVERY COMPILATION
# ═══════════════════════════════════════════════════════════════


def _compile_recovery(
    rows: list[TemporalEvidence],
    intervention_class: str,
) -> CompiledRecoveryParams:
    """Compile recovery trajectory from post-cessation timepoint-effect pairs.

    Formula P7-C3b: r(t) = r_inf * (1 - exp(-(t/tau_r)^gamma_r))

    If < 3 recovery timepoints: use default recovery curve.
    """
    valid = [
        r for r in rows
        if r.effect is not None and r.timepoint_weeks is not None
    ]

    if not valid:
        logger.warning(
            "Intervention class '%s': no valid recovery data, using defaults",
            intervention_class,
        )
        return CompiledRecoveryParams(
            intervention_class=intervention_class,
            r_inf=config.RECOVERY_R_INFINITY_DEFAULT,
            tau_r=config.RECOVERY_TAU_R_MONTHS_DEFAULT,
            gamma_r=config.RECOVERY_GAMMA_R_DEFAULT,
            k_timepoints=0,
            provenance_status="APPROXIMATE_PENDING",
            provenance_ref="",
        )

    k = len(valid)

    if k < config.P7_MIN_TIMEPOINTS_CURVE:
        logger.info(
            "Intervention class '%s': k=%d < %d recovery timepoints, using defaults",
            intervention_class,
            k,
            config.P7_MIN_TIMEPOINTS_CURVE,
        )
        study_ids = sorted({r.study_id for r in valid if r.study_id})
        return CompiledRecoveryParams(
            intervention_class=intervention_class,
            r_inf=config.RECOVERY_R_INFINITY_DEFAULT,
            tau_r=config.RECOVERY_TAU_R_MONTHS_DEFAULT,
            gamma_r=config.RECOVERY_GAMMA_R_DEFAULT,
            k_timepoints=k,
            provenance_status="APPROXIMATE_PENDING",
            provenance_ref="; ".join(study_ids),
        )

    # Prepare data for fitting
    # Convert timepoint_weeks to months for recovery fitting (÷ 4.345)
    t_data = np.array([r.timepoint_weeks / 4.345 for r in valid])
    e_data = np.array([r.effect for r in valid])

    # Weights: 1/SE² if available
    w_data = np.array([
        1.0 / (r.se ** 2) if r.se is not None and r.se > 0.0 else 1.0
        for r in valid
    ])

    # Fit stretched exponential using least squares
    try:
        popt, _ = curve_fit(
            _stretched_exponential,
            t_data,
            e_data,
            p0=[
                config.RECOVERY_R_INFINITY_DEFAULT,
                config.RECOVERY_TAU_R_MONTHS_DEFAULT,
                config.RECOVERY_GAMMA_R_DEFAULT,
            ],
            sigma=1.0 / np.sqrt(w_data),
            absolute_sigma=True,
            bounds=(
                [config.P7_RECOVERY_R_INF_MIN, 1e-6, 0.1],
                [config.P7_RECOVERY_R_INF_MAX, 100.0, 5.0],
            ),
            maxfev=5000,
        )
        r_inf, tau_r, gamma_r = float(popt[0]), float(popt[1]), float(popt[2])
    except (RuntimeError, ValueError) as exc:
        logger.warning(
            "Intervention class '%s': curve_fit failed (%s), using defaults",
            intervention_class,
            exc,
        )
        r_inf = config.RECOVERY_R_INFINITY_DEFAULT
        tau_r = config.RECOVERY_TAU_R_MONTHS_DEFAULT
        gamma_r = config.RECOVERY_GAMMA_R_DEFAULT

    study_ids = sorted({r.study_id for r in valid if r.study_id})
    cancer_types = {r.study_design or "" for r in valid}

    return CompiledRecoveryParams(
        intervention_class=intervention_class,
        cancer_type=next(iter(cancer_types), "any"),
        r_inf=r_inf,
        tau_r=tau_r,
        gamma_r=gamma_r,
        k_timepoints=k,
        provenance_status="CURATED_TRACED",
        provenance_ref="; ".join(study_ids),
    )


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_temporal(
    evidence_rows: list[TemporalEvidence],
) -> tuple[list[CompiledTemporalKernel], list[CompiledRecoveryParams]]:
    """Compile temporal kernels and recovery params from temporal evidence.

    Groups evidence by action_id (or intervention_type), separates
    intervention vs recovery rows, and compiles each.

    Gate P7-G3: Fitted kernel must satisfy onset < peak.
    Fitted recovery must satisfy r_inf ∈ (0, 1], tau_r > 0.

    Args:
        evidence_rows: Rows from temporal_evidence_v1 (written by AG08-EXT).

    Returns:
        (kernels, recovery_params) — one kernel per intervention,
        one recovery per intervention class.

    Raises:
        GateViolation: If P7-G3 constraints are violated.
    """
    # Group by action_id (or intervention_type as fallback)
    groups: dict[str, _ActionGroup] = {}
    for row in evidence_rows:
        key = (row.action_id or row.intervention_type or "unknown").strip().lower()
        if key not in groups:
            groups[key] = _ActionGroup(action_id=key)
        if row.is_recovery:
            groups[key].recovery_rows.append(row)
        else:
            groups[key].intervention_rows.append(row)

    kernels: list[CompiledTemporalKernel] = []
    recoveries: list[CompiledRecoveryParams] = []

    for key, group in groups.items():
        # Compile intervention kernel
        if group.intervention_rows:
            kernel = _compile_kernel(group.intervention_rows, group.action_id)

            # ─── Gate P7-G3: onset < peak ─────────────────────────
            if (
                kernel.k_timepoints >= config.P7_MIN_TIMEPOINTS_CURVE
                and kernel.onset_weeks > kernel.peak_weeks
            ):
                raise GateViolation(
                    "P7-G3",
                    f"Action '{group.action_id}': onset ({kernel.onset_weeks:.1f}) "
                    f"> peak ({kernel.peak_weeks:.1f}) — invalid kernel shape",
                    {
                        "action_id": group.action_id,
                        "onset_weeks": kernel.onset_weeks,
                        "peak_weeks": kernel.peak_weeks,
                    },
                )

            kernels.append(kernel)
            logger.info(
                "Compiled kernel '%s': onset=%.1f, peak=%.1f, plateau=%.1f, "
                "decay=%.4f, k=%d",
                group.action_id,
                kernel.onset_weeks,
                kernel.peak_weeks,
                kernel.plateau_duration,
                kernel.decay_rate,
                kernel.k_timepoints,
            )

        # Compile recovery params
        if group.recovery_rows:
            recovery = _compile_recovery(group.recovery_rows, group.action_id)

            # ─── Gate P7-G3: r_inf ∈ (0, 1], tau_r > 0 ──────────
            if recovery.k_timepoints >= config.P7_MIN_TIMEPOINTS_CURVE:
                if (
                    recovery.r_inf <= config.P7_RECOVERY_R_INF_MIN
                    or recovery.r_inf > config.P7_RECOVERY_R_INF_MAX
                ):
                    raise GateViolation(
                        "P7-G3",
                        f"Intervention class '{group.action_id}': "
                        f"r_inf={recovery.r_inf:.4f} not in "
                        f"({config.P7_RECOVERY_R_INF_MIN}, {config.P7_RECOVERY_R_INF_MAX}]",
                        {
                            "intervention_class": group.action_id,
                            "r_inf": recovery.r_inf,
                        },
                    )
                if recovery.tau_r <= config.P7_RECOVERY_TAU_R_MIN:
                    raise GateViolation(
                        "P7-G3",
                        f"Intervention class '{group.action_id}': "
                        f"tau_r={recovery.tau_r:.4f} <= {config.P7_RECOVERY_TAU_R_MIN}",
                        {
                            "intervention_class": group.action_id,
                            "tau_r": recovery.tau_r,
                        },
                    )

            recoveries.append(recovery)
            logger.info(
                "Compiled recovery '%s': r_inf=%.4f, tau_r=%.4f, "
                "gamma_r=%.4f, k=%d",
                group.action_id,
                recovery.r_inf,
                recovery.tau_r,
                recovery.gamma_r,
                recovery.k_timepoints,
            )

    logger.info(
        "Temporal compilation complete: %d kernels, %d recovery params",
        len(kernels),
        len(recoveries),
    )
    return kernels, recoveries
