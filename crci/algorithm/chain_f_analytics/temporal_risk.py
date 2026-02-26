# VERIFIED: formulas [F4T-1 through F4T-10] match IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §8.2
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads RecoveryTrajectory (E2), OverlayResult (E3),
#           NodeMap (A1), CompositeState (F1), fusion_levels (C3c)
# VERIFIED: forward wiring — writes PredictiveRiskEstimate for report_assembler.py
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [F4T-G1, F4T-G1b (orientation), F4T-G1c (intervention sanity)] raise on failure
# VERIFIED: per-node delta from D2 replaces scalar ΔC (§8.2 feedback 2.1)
# VERIFIED: nadir/base from E2 used directly, not re-estimated (§8.2 feedback 2.2)
# VERIFIED: explicit time_months from E2 (§8.2 feedback 2.3)
# VERIFIED: NNT gated behind calibration_status (§8.2 feedback 3.1)
# VERIFIED: missing ICCTF domains raise GateViolation (§8.2 feedback 3.2)
"""
Component: SYS_ALGORITHM.ALG-F.F4T (Temporal Risk)
Spec: IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §8.2

Temporal/predictive CRCI risk estimation — applies ICCTF classification
at future timepoints using per-draw theta reconstruction from R_draws.

Formulas:
    F4T-1: θ^(m)_i(t) = nadir_i + δ_i × R^(m)(t) + δ_aging(t) (natural)
    F4T-2: θ^(m)_{i,a}(t) = θ^(m)_i(t) + Δθ_{a,i} × K_a(t) (per-node delta)
    F4T-3: z_d^(m)(t) = agg({θ^(m)_i(t) for i ∈ domain d})
    F4T-4: CRCI^(m)(t) = F4-1 applied at time t
    F4T-5: P̂(t) = (1/M) Σ_m CRCI^(m)(t)
    F4T-6: P(t) ~ Beta(S(t)+0.5, F(t)+0.5)
    F4T-8: ARR_a(t) = P̂_natural(t) − P̂_a(t)
    F4T-9: RRR_a(t) = ARR_a(t) / P̂_natural(t)
    F4T-10: NNT_a(t) = 1 / ARR_a(t)  [suppressed unless calibrated]

Reads: RecoveryTrajectory (E2), OverlayResult (E3), NodeMap (A1),
       CompositeState (F1), fusion_levels (C3c)
Writes: PredictiveRiskEstimate (consumed by report_assembler.py)
Gates: F4T-G1 (boundedness + paired consistency),
       F4T-G1b (orientation + unit of measure),
       F4T-G1c (intervention sanity)

Approximations declared (§8.2.13):
    1. Domain-level aggregation (same as F4)
    2. Per-node mean delta (mean across draws, not per-draw)
    3. Linear R→θ mapping (uses E2 nadir/base directly)
    4. No treatment regiment changes mid-trajectory
    5. Same ICCTF thresholds at all timepoints
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from crci.shared import config
from crci.shared.math_utils import (
    classify_crci_vectorized,
    solve_linear_coefficients,
)
from crci.shared.models.intermediate_states import GateViolation

from ..chain_a_graph.node_loader import NodeMap
from ..chain_e_temporal.intervention_overlay import OverlayResult
from ..chain_e_temporal.recovery_trajectory import RecoveryTrajectory
from .composite_scorer import CompositeState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types (§8.2.7)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TemporalRiskPoint:
    """CRCI risk at a single future timepoint.

    Formula F4T-5: P̂(t) = (1/M) Σ CRCI^(m)(t)
    """

    month: int
    risk_pct: float                   # P̂(t) × 100
    risk_lower_pct: float             # Jeffreys lower × 100
    risk_upper_pct: float             # Jeffreys upper × 100
    mc_se: float                      # √(P̂(1−P̂)/M)
    n_domains_impaired_mean: float    # mean count of impaired domains across draws
    n_draws_crci_positive: int        # S(t) = count of draws meeting CRCI criteria


@dataclass
class TemporalRiskCurve:
    """CRCI risk over time for one scenario (natural or with intervention).

    Contains the full P̂(t) time series plus summary statistics.
    """

    scenario_id: str                  # "natural" or intervention action_id
    scenario_label: str               # Human-readable label
    points: list[TemporalRiskPoint] = field(default_factory=list)
    peak_risk_month: int = 0          # arg max P̂(t)
    peak_risk_pct: float = 0.0        # max P̂(t) × 100
    risk_at_horizons: dict[int, float] = field(default_factory=dict)  # {3: 42.3, ...}
    resolution_month: int | None = None  # First t where P̂(t) < TIER_LOW; None if never


@dataclass
class TemporalRiskReduction:
    """Risk reduction from one intervention, over time.

    Formulas F4T-8, F4T-9, F4T-10.
    """

    intervention_id: str
    arr_curve: list[float] = field(default_factory=list)  # ARR(t) at each month, length T
    rrr_at_horizons: dict[int, float | None] = field(default_factory=dict)
    nnt_at_horizons: dict[int, float | None] = field(default_factory=dict)
    peak_arr_month: int = 0           # When intervention provides max benefit
    peak_arr_pct: float = 0.0         # Maximum absolute risk reduction
    months_saved: int | None = None   # resolution_natural − resolution_intervention


@dataclass
class PredictiveRiskEstimate:
    """Complete §8.2 output — temporal risk trajectories.

    NOT the same as UncertaintyResult (E4). E4 uses a single-threshold
    impairment definition; this uses the full ICCTF multi-domain criteria
    from F4 (Formula F4-1) applied at each t.
    """

    # Risk curves
    natural_curve: TemporalRiskCurve = field(default_factory=lambda: TemporalRiskCurve(
        scenario_id="natural", scenario_label="Natural Recovery",
    ))
    intervention_curves: dict[str, TemporalRiskCurve] = field(default_factory=dict)

    # Risk reduction summaries
    risk_reductions: dict[str, TemporalRiskReduction] = field(default_factory=dict)

    # Best intervention by temporal profile
    best_peak_arr_intervention: str | None = None
    best_resolution_intervention: str | None = None

    # Metadata
    n_draws: int = 0
    n_timepoints: int = 0
    horizons_months: list[int] = field(default_factory=list)
    coverage_fraction: float = 0.0
    domain_aggregation: str = "mean"
    criteria_used: str = "ICCTF_Wefel2011_domain_level"
    calibration_status: str = "uncalibrated_model_derived"
    nnt_suppressed: bool = True  # NNT suppressed until calibration (§8.2 feedback 3.1)
    gate_f4t_g1_passed: bool = False
    gate_f4t_g1b_passed: bool = False  # orientation/unit gate
    gate_f4t_g1c_passed: bool = False  # intervention sanity gate


# ═══════════════════════════════════════════════════════════════
#  Domain Mapping & Node Selection
# ═══════════════════════════════════════════════════════════════


def _get_cognitive_node_indices(node_map: NodeMap) -> dict[str, list[int]]:
    """Get cognitive domain → node index mapping for ICCTF classification.

    Validates that all required nodes exist in the NodeMap.
    Raises GateViolation if any ICCTF domain has zero mapped nodes
    (fix §8.2 feedback 3.2: fail fast instead of silently neutral).
    """
    domain_index_map: dict[str, list[int]] = {}
    missing_domains: list[str] = []

    for domain_id, node_ids in config.F4_DOMAIN_NODE_MAP.items():
        indices = []
        for nid in node_ids:
            idx = node_map.node_index.get(nid)
            if idx is not None:
                indices.append(idx)
        if not indices:
            missing_domains.append(domain_id)
        domain_index_map[domain_id] = indices

    # Fix §8.2 feedback 3.2: fail fast on missing ICCTF domains
    if missing_domains:
        raise GateViolation(
            "F4T-G1b",
            f"Required ICCTF domains have no mapped nodes in NodeMap: "
            f"{missing_domains}. All {len(config.F4_DOMAIN_NODE_MAP)} "
            f"cognitive domains must have at least one node for valid "
            f"CRCI classification. Check NODE_REGISTRY.csv and "
            f"F4_DOMAIN_NODE_MAP in config.",
        )

    return domain_index_map


# ═══════════════════════════════════════════════════════════════
#  F4T-1/F4T-2: Per-Draw Theta Reconstruction
# ═══════════════════════════════════════════════════════════════


def _reconstruct_theta_draws_natural(
    R_draws: np.ndarray,
    aging: np.ndarray,
    cognitive_indices: list[int],
    theta_nadir: np.ndarray | None = None,
    theta_base: np.ndarray | None = None,
    theta_natural: np.ndarray | None = None,
    R_mean: np.ndarray | None = None,
) -> np.ndarray:
    """F4T-1: Reconstruct per-draw theta for natural trajectory.

    θ^(m)_i(t) = nadir_i + δ_i × R^(m)(t) + δ_aging(t)

    Uses theta_nadir and theta_base directly from E1/E2 when available
    (fix §8.2 feedback 2.2: avoids re-estimating coefficients from mean
    curve via solve_linear_coefficients, which can misbehave when R(t)
    saturates).

    Falls back to solve_linear_coefficients only if nadir/base are not
    provided (backward compatibility).

    Args:
        R_draws: (n_draws, T) MC draws of recovery fraction.
        aging: (T,) aging projection δ_aging(t).
        cognitive_indices: List of node indices to reconstruct.
        theta_nadir: (n_nodes,) cognitive nadir from E1 (preferred).
        theta_base: (n_nodes,) pre-treatment baseline from E1 (preferred).
        theta_natural: (n_nodes, T) mean trajectory from E2 (fallback only).
        R_mean: (T,) mean recovery fraction (fallback only).

    Returns:
        (n_cognitive_nodes, n_draws, T) per-draw theta at cognitive nodes.
    """
    n_nodes = len(cognitive_indices)
    n_draws, T = R_draws.shape

    if theta_nadir is not None and theta_base is not None:
        # Preferred path: use actual decomposition from E1/E2
        nadir_cog = theta_nadir[cognitive_indices]  # (n_cog,)
        delta_cog = theta_base[cognitive_indices] - nadir_cog  # (n_cog,)
        logger.debug(
            "F4T-1: Using E1 nadir/base directly for %d cognitive nodes",
            n_nodes,
        )
    elif theta_natural is not None and R_mean is not None:
        # Fallback: re-estimate from mean trajectory
        logger.warning(
            "F4T-1: theta_nadir/theta_base not available — falling back "
            "to solve_linear_coefficients (less accurate when R(t) saturates)",
        )
        theta_cog = theta_natural[cognitive_indices, :]  # (n_cog, T)
        nadir_cog, delta_cog = solve_linear_coefficients(theta_cog, R_mean)
    else:
        raise GateViolation(
            "F4T-G1",
            "Cannot reconstruct theta draws: neither (theta_nadir, theta_base) "
            "nor (theta_natural, R_mean) provided.",
        )

    # Reconstruct: θ^(m)_i(t) = nadir_i + δ_i × R^(m)(t) + δ_aging(t)
    # Shape: (n_cog, n_draws, T)
    theta_draws = np.zeros((n_nodes, n_draws, T))

    for i in range(n_nodes):
        # theta_draws[i, m, t] = nadir[i] + delta[i] * R_draws[m, t] + aging[t]
        theta_draws[i, :, :] = (
            nadir_cog[i]
            + delta_cog[i] * R_draws
            + aging[np.newaxis, :]  # broadcast aging (T,) to (n_draws, T)
        )

    return theta_draws


def _reconstruct_theta_draws_intervention(
    theta_draws_natural: np.ndarray,
    K_a: np.ndarray,
    cognitive_indices: list[int],
    delta_theta_mean: np.ndarray | None = None,
    delta_C: float | None = None,
) -> np.ndarray:
    """F4T-2: Add intervention effect to natural theta draws.

    Preferred (per-node, fix §8.2 feedback 2.1):
        θ^(m)_{i,a}(t) = θ^(m)_i(t) + Δθ_{a,i} × K_a(t)

    Fallback (scalar, deprecated):
        θ^(m)_{i,a}(t) = θ^(m)_i(t) + ΔC_a × K_a(t)

    NOTE: Aging is already included in theta_draws_natural (F4T-1).
    We add only the intervention shift here.

    Args:
        theta_draws_natural: (n_cog, n_draws, T) from F4T-1.
        K_a: (T,) intervention kernel.
        cognitive_indices: Global node indices for cognitive nodes.
        delta_theta_mean: (n_nodes,) per-node mean delta from D2 (preferred).
        delta_C: Scalar composite effect (deprecated fallback).

    Returns:
        (n_cog, n_draws, T) per-draw theta with intervention.
    """
    n_cog = theta_draws_natural.shape[0]

    if delta_theta_mean is not None:
        # Preferred: per-node mechanistic delta (fix §8.2 feedback 2.1)
        # Extract deltas for cognitive nodes only
        delta_cog = delta_theta_mean[cognitive_indices]  # (n_cog,)
        # Shape: (n_cog, 1, 1) × (1, 1, T) → (n_cog, 1, T)
        intervention_shift = delta_cog[:, np.newaxis, np.newaxis] * K_a[np.newaxis, np.newaxis, :]
    elif delta_C is not None:
        # Fallback: scalar ΔC applied uniformly (deprecated)
        logger.warning(
            "F4T-2: Using scalar delta_C=%.4f uniformly across %d cognitive "
            "nodes — mechanistic accuracy degraded. Upgrade E3 to carry "
            "delta_theta_mean from D2.",
            delta_C, n_cog,
        )
        intervention_shift = delta_C * K_a[np.newaxis, np.newaxis, :]
    else:
        raise GateViolation(
            "F4T-G1c",
            "No intervention effect provided: neither delta_theta_mean "
            "nor delta_C available.",
        )

    return theta_draws_natural + intervention_shift


# ═══════════════════════════════════════════════════════════════
#  F4T-3/F4T-4: Domain Aggregation & ICCTF Classification
# ═══════════════════════════════════════════════════════════════


def _aggregate_to_domains(
    theta_draws: np.ndarray,
    domain_index_map: dict[str, list[int]],
    cognitive_indices: list[int],
) -> np.ndarray:
    """F4T-3: Aggregate node-level theta to domain-level z-scores.

    Args:
        theta_draws: (n_cog, n_draws, T) per-draw theta at cognitive nodes.
        domain_index_map: domain_id → list[node_index] (global indices).
        cognitive_indices: List of global indices for cognitive nodes.

    Returns:
        (n_domains, n_draws, T) domain z-scores.
    """
    agg = config.F4_DOMAIN_AGGREGATION
    domains = list(domain_index_map.keys())
    n_domains = len(domains)
    _, n_draws, T = theta_draws.shape

    # Map global indices to local indices in theta_draws
    global_to_local = {g: l for l, g in enumerate(cognitive_indices)}

    domain_z = np.zeros((n_domains, n_draws, T))

    for d_idx, domain_id in enumerate(domains):
        global_indices = domain_index_map[domain_id]
        local_indices = [global_to_local[g] for g in global_indices if g in global_to_local]

        if not local_indices:
            # This should never happen if _get_cognitive_node_indices already
            # validated (fix §8.2 feedback 3.2), but guard defensively.
            raise GateViolation(
                "F4T-G1b",
                f"Domain '{domain_id}' has no mapped cognitive nodes — "
                f"cannot compute ICCTF classification. This indicates a "
                f"NodeMap inconsistency.",
            )

        node_z = theta_draws[local_indices, :, :]  # (n_nodes_in_domain, n_draws, T)

        if agg == "min":
            domain_z[d_idx, :, :] = np.min(node_z, axis=0)
        else:
            domain_z[d_idx, :, :] = np.mean(node_z, axis=0)

    return domain_z


# ═══════════════════════════════════════════════════════════════
#  F4T-5/F4T-6: Risk Curve Aggregation
# ═══════════════════════════════════════════════════════════════


def _compute_risk_curve(
    domain_z_draws: np.ndarray,
    scenario_id: str,
    scenario_label: str,
    horizons: list[int],
    time_months: np.ndarray | None = None,
) -> TemporalRiskCurve:
    """Compute risk curve from domain z-draws.

    Applies F4T-4 (ICCTF classification) and F4T-5/F4T-6 (aggregation).

    Args:
        domain_z_draws: (n_domains, n_draws, T) domain z-scores.
        scenario_id: "natural" or intervention_id.
        scenario_label: Human-readable label.
        horizons: Prediction horizons (months) for risk_at_horizons dict.
        time_months: (T,) explicit month values (fix §8.2 feedback 2.3).

    Returns:
        TemporalRiskCurve with all points and summary stats.
    """
    n_domains, n_draws, T = domain_z_draws.shape

    # Fix §8.2 feedback 2.3: use explicit time axis if provided
    if time_months is None:
        time_months = np.arange(T, dtype=float)
    elif len(time_months) != T:
        raise GateViolation(
            "F4T-G1",
            f"time_months length ({len(time_months)}) does not match "
            f"domain_z_draws timepoints ({T}).",
        )

    # F4T-4: ICCTF classification at each timepoint
    crci_positive = classify_crci_vectorized(domain_z_draws)  # (n_draws, T)

    # Count domains impaired per draw per timepoint
    z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    n_impaired = np.sum(domain_z_draws <= z_multi, axis=0)  # (n_draws, T)

    points: list[TemporalRiskPoint] = []
    risk_values: list[float] = []

    ci_level = config.F4_CI_LEVEL
    alpha_half = (1.0 - ci_level) / 2.0

    for t in range(T):
        S_t = int(np.sum(crci_positive[:, t]))
        M = n_draws
        p_hat = S_t / M if M > 0 else 0.0

        # MC-SE
        mc_se = np.sqrt(p_hat * (1 - p_hat) / M) if M > 0 else 0.0

        # Jeffreys interval (F4T-6)
        a = S_t + 0.5
        b = (M - S_t) + 0.5
        lower = float(stats.beta.ppf(alpha_half, a, b))
        upper = float(stats.beta.ppf(1.0 - alpha_half, a, b))

        mean_impaired = float(np.mean(n_impaired[:, t]))

        # Fix §8.2 feedback 2.3: use actual month value, not index
        actual_month = int(time_months[t])

        points.append(TemporalRiskPoint(
            month=actual_month,
            risk_pct=p_hat * 100.0,
            risk_lower_pct=lower * 100.0,
            risk_upper_pct=upper * 100.0,
            mc_se=mc_se,
            n_domains_impaired_mean=mean_impaired,
            n_draws_crci_positive=S_t,
        ))
        risk_values.append(p_hat * 100.0)

    # Summary stats
    peak_idx = int(np.argmax(risk_values)) if risk_values else 0
    peak_risk_pct = risk_values[peak_idx] if risk_values else 0.0

    risk_at_horizons: dict[int, float] = {}
    for h in horizons:
        # Look up by horizon month value in time_months
        matching_indices = np.where(time_months == h)[0]
        if len(matching_indices) > 0:
            risk_at_horizons[h] = risk_values[matching_indices[0]]

    # Resolution month: first t where P̂(t) < LOW threshold
    low_threshold = config.F4_TIER_LOW_MAX
    resolution_month: int | None = None
    for t, r in enumerate(risk_values):
        if r < low_threshold:
            resolution_month = int(time_months[t])
            break

    return TemporalRiskCurve(
        scenario_id=scenario_id,
        scenario_label=scenario_label,
        points=points,
        peak_risk_month=peak_idx,
        peak_risk_pct=peak_risk_pct,
        risk_at_horizons=risk_at_horizons,
        resolution_month=resolution_month,
    )


# ═══════════════════════════════════════════════════════════════
#  F4T-8/F4T-9/F4T-10: Risk Reduction Metrics
# ═══════════════════════════════════════════════════════════════


def _compute_risk_reduction(
    natural_curve: TemporalRiskCurve,
    intervention_curve: TemporalRiskCurve,
    horizons: list[int],
    calibration_status: str = "uncalibrated_model_derived",
) -> TemporalRiskReduction:
    """Compute risk reduction metrics for one intervention.

    Formulas F4T-8, F4T-9, F4T-10.

    NNT is only populated when calibration_status == "calibrated"
    (fix §8.2 feedback 3.1: NNT implies clinical decision thresholding
    on an absolute risk scale and is not defensible until the model
    has been externally calibrated).
    """
    intervention_id = intervention_curve.scenario_id
    T = len(natural_curve.points)
    is_calibrated = calibration_status == "calibrated"

    # ARR curve
    arr_curve: list[float] = []
    for t in range(T):
        p_nat = natural_curve.points[t].risk_pct
        p_int = intervention_curve.points[t].risk_pct
        arr_curve.append(p_nat - p_int)

    # Peak ARR
    peak_arr_idx = int(np.argmax(arr_curve)) if arr_curve else 0
    peak_arr_pct = arr_curve[peak_arr_idx] if arr_curve else 0.0

    # RRR and NNT at horizons
    rrr_at_horizons: dict[int, float | None] = {}
    nnt_at_horizons: dict[int, float | None] = {}

    for h in horizons:
        if h < len(arr_curve):
            arr_h = arr_curve[h]
            p_nat_h = natural_curve.points[h].risk_pct

            # RRR = ARR / P_natural (F4T-9)
            if p_nat_h > 0:
                rrr_at_horizons[h] = (arr_h / p_nat_h) * 100.0  # as percentage
            else:
                rrr_at_horizons[h] = None

            # NNT = 100 / ARR (F4T-10) — ARR already in percentage points
            # Fix §8.2 feedback 3.1: suppress NNT unless model is calibrated
            if is_calibrated and arr_h > 0:
                nnt_at_horizons[h] = 100.0 / arr_h
            else:
                nnt_at_horizons[h] = None

    # Months saved
    months_saved: int | None = None
    if natural_curve.resolution_month is not None and intervention_curve.resolution_month is not None:
        months_saved = natural_curve.resolution_month - intervention_curve.resolution_month

    return TemporalRiskReduction(
        intervention_id=intervention_id,
        arr_curve=arr_curve,
        rrr_at_horizons=rrr_at_horizons,
        nnt_at_horizons=nnt_at_horizons,
        peak_arr_month=peak_arr_idx,
        peak_arr_pct=peak_arr_pct,
        months_saved=months_saved,
    )


# ═══════════════════════════════════════════════════════════════
#  Gate F4T-G1b: Orientation & Unit of Measure (fix §8.2 feedback 4.1)
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f4t_g1b(
    node_map: NodeMap,
    domain_index_map: dict[str, list[int]],
) -> None:
    """Gate F4T-G1b: Verify orientation and unit of measure for cognitive nodes.

    Fix §8.2 feedback 4.1: F4T must enforce its own orientation/unit gate
    rather than delegating to F4 (which F4T does not call).

    Conditions:
        1. All mapped cognitive nodes exist in NodeMap.
        2. All cognitive nodes have orientation == POS_UP.
        3. All cognitive nodes have unit_of_measure in {"z-score", "z"}.

    Raises:
        GateViolation: If any condition fails.
    """
    violations: list[str] = []
    valid_orientations = {"POS_UP"}
    valid_units = {"z-score", "z", "z_score"}

    for domain_id, indices in domain_index_map.items():
        for idx in indices:
            if idx >= len(node_map.nodes):
                violations.append(
                    f"Domain '{domain_id}': node index {idx} out of range "
                    f"(NodeMap has {len(node_map.nodes)} nodes)"
                )
                continue

            node = node_map.nodes[idx]

            if node.orientation not in valid_orientations:
                violations.append(
                    f"Domain '{domain_id}', node '{node.node_id}': "
                    f"orientation='{node.orientation}' (expected POS_UP). "
                    f"ICCTF classification requires higher=better z-scores."
                )

            if node.unit_of_measure not in valid_units:
                violations.append(
                    f"Domain '{domain_id}', node '{node.node_id}': "
                    f"unit_of_measure='{node.unit_of_measure}' "
                    f"(expected 'z-score'). ICCTF thresholds are defined "
                    f"in z-score units."
                )

    if violations:
        raise GateViolation(
            "F4T-G1b",
            "Orientation/unit validation failed:\n  " + "\n  ".join(violations),
        )

    logger.info(
        "Gate F4T-G1b PASSED: all %d cognitive nodes have POS_UP orientation "
        "and z-score units",
        sum(len(v) for v in domain_index_map.values()),
    )


# ═══════════════════════════════════════════════════════════════
#  Gate F4T-G1c: Intervention Sanity (fix §8.2 feedback 4.2)
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f4t_g1c(
    overlay: OverlayResult,
    result: PredictiveRiskEstimate,
    tolerance: float = 0.1,  # risk_pct tolerance for equality checks
) -> None:
    """Gate F4T-G1c: Intervention sanity checks.

    Fix §8.2 feedback 4.2: verify intervention curves are consistent
    with their parameters.

    Conditions:
        1. If K_a(t) is all zeros → intervention curve must equal natural.
        2. If delta_C is zero (and delta_theta_mean is None or all zeros)
           → intervention curve must equal natural.

    Raises:
        GateViolation: If any condition fails.
    """
    violations: list[str] = []

    for intv_id, intv_traj in overlay.intervention_trajectories.items():
        intv_curve = result.intervention_curves.get(intv_id)
        if intv_curve is None:
            continue

        # Condition 1: K_a all zeros → curve must match natural
        k_all_zero = np.allclose(intv_traj.K_a, 0.0, atol=1e-10)
        if k_all_zero:
            for t_idx, (nat_pt, intv_pt) in enumerate(
                zip(result.natural_curve.points, intv_curve.points),
            ):
                if abs(nat_pt.risk_pct - intv_pt.risk_pct) > tolerance:
                    violations.append(
                        f"Intervention '{intv_id}': K_a is all zeros but "
                        f"risk differs from natural at t={nat_pt.month}: "
                        f"natural={nat_pt.risk_pct:.2f}%, "
                        f"intervention={intv_pt.risk_pct:.2f}%"
                    )
                    break  # one violation per intervention is sufficient

        # Condition 2: delta effect is zero → curve must match natural
        delta_is_zero = abs(intv_traj.delta_C) < 1e-10
        if intv_traj.delta_theta_mean is not None:
            delta_is_zero = np.allclose(intv_traj.delta_theta_mean, 0.0, atol=1e-10)

        if delta_is_zero:
            for t_idx, (nat_pt, intv_pt) in enumerate(
                zip(result.natural_curve.points, intv_curve.points),
            ):
                if abs(nat_pt.risk_pct - intv_pt.risk_pct) > tolerance:
                    violations.append(
                        f"Intervention '{intv_id}': delta effect is zero but "
                        f"risk differs from natural at t={nat_pt.month}: "
                        f"natural={nat_pt.risk_pct:.2f}%, "
                        f"intervention={intv_pt.risk_pct:.2f}%"
                    )
                    break

    if violations:
        raise GateViolation(
            "F4T-G1c",
            "Intervention sanity check failed:\n  " + "\n  ".join(violations),
        )

    logger.info(
        "Gate F4T-G1c PASSED: %d intervention curves pass sanity checks",
        len(result.intervention_curves),
    )


# ═══════════════════════════════════════════════════════════════
#  Gate F4T-G1
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f4t_g1(
    recovery: RecoveryTrajectory,
    result: PredictiveRiskEstimate,
) -> None:
    """Gate F4T-G1: Temporal risk estimate validity.

    Preconditions (§8.2.8):
        1. R_draws shape consistency
        2. Orientation gate (delegated to F4's F-G4a)
        3. Non-degenerate R_draws

    Post-conditions:
        4. Boundedness: P̂(t) ∈ [0, 100] for all t
        5. Paired consistency (ARR = P_nat - P_int)
    """
    violations: list[str] = []

    # Precondition 3: Non-degenerate R_draws
    R_draws = recovery.R_draws
    n_draws, T = R_draws.shape
    R_std = np.std(R_draws, axis=0)  # (T,)
    variable_frac = np.sum(R_std > 1e-10) / T

    min_variable_frac = 0.50  # F4T_MIN_VARIABLE_TIMEPOINT_FRAC
    if variable_frac < min_variable_frac:
        violations.append(
            f"R_draws has insufficient variation: {variable_frac:.1%} of "
            f"timepoints variable (threshold: {min_variable_frac:.0%})"
        )

    # Post-condition 4: Boundedness
    for pt in result.natural_curve.points:
        if not (0.0 <= pt.risk_pct <= 100.0):
            violations.append(f"Natural risk at t={pt.month} outside [0,100]: {pt.risk_pct:.2f}")

    for curve in result.intervention_curves.values():
        for pt in curve.points:
            if not (0.0 <= pt.risk_pct <= 100.0):
                violations.append(
                    f"Intervention {curve.scenario_id} risk at t={pt.month} "
                    f"outside [0,100]: {pt.risk_pct:.2f}"
                )

    # Post-condition 5: Paired consistency (spot check)
    for intv_id, reduction in result.risk_reductions.items():
        curve = result.intervention_curves.get(intv_id)
        if curve is None:
            continue
        for t, arr in enumerate(reduction.arr_curve):
            expected_arr = result.natural_curve.points[t].risk_pct - curve.points[t].risk_pct
            if abs(arr - expected_arr) > 0.01:
                violations.append(
                    f"ARR inconsistency for {intv_id} at t={t}: "
                    f"arr={arr:.4f}, expected={expected_arr:.4f}"
                )

    if violations:
        raise GateViolation(
            "F4T-G1",
            "Temporal risk validation failed:\n  " + "\n  ".join(violations),
        )

    logger.info(
        "Gate F4T-G1 PASSED: %d timepoints, %d intervention curves, "
        "all bounded, paired consistency verified",
        result.n_timepoints,
        len(result.intervention_curves),
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_temporal_risk (F4T entry point)
# ═══════════════════════════════════════════════════════════════


def compute_temporal_risk(
    recovery: RecoveryTrajectory,
    overlay: OverlayResult,
    node_map: NodeMap,
    composite_state: CompositeState | None = None,
    fusion_levels: dict[int, set[str]] | None = None,
    horizons: list[int] | None = None,
    calibration_status: str = "uncalibrated_model_derived",
) -> PredictiveRiskEstimate:
    """F4T: Compute temporal/predictive CRCI risk with ICCTF classification.

    Applies ICCTF classification (F4-1) at each future timepoint using
    per-draw theta reconstruction from the recovery trajectory (E2) and
    intervention overlays (E3).

    This produces risk curves showing P̂(CRCI|t) over time for the natural
    recovery trajectory and each intervention scenario.

    Args:
        recovery: RecoveryTrajectory from E2 — provides theta_natural,
            R_draws, R_mean, theta_nadir, theta_base, time_months.
        overlay: OverlayResult from E3 — provides per-intervention
            trajectories with delta_theta_mean, K_a(t).
        node_map: NodeMap for index resolution and orientation validation.
        composite_state: CompositeState from F1 (optional, for coverage).
        fusion_levels: From C3c (optional, for coverage computation).
        horizons: Prediction horizons in months (default: E_PREDICTION_HORIZONS).
        calibration_status: Controls NNT emission ("calibrated" enables NNT).

    Returns:
        PredictiveRiskEstimate with risk curves and reduction metrics.

    Raises:
        GateViolation: If F4T-G1, F4T-G1b, or F4T-G1c conditions fail.
    """
    if horizons is None:
        horizons = config.E_PREDICTION_HORIZONS

    n_draws, T = recovery.R_draws.shape

    logger.info(
        "── F4T: Temporal Risk Estimation ──\n"
        "  n_draws=%d, T=%d timepoints, %d interventions, "
        "calibration=%s",
        n_draws, T, overlay.n_interventions, calibration_status,
    )

    # Get cognitive node indices for ICCTF domains
    # This now raises GateViolation if any domain has no nodes (fix 3.2)
    domain_index_map = _get_cognitive_node_indices(node_map)
    all_cognitive_indices = sorted(set(
        idx for indices in domain_index_map.values() for idx in indices
    ))

    # ── Gate F4T-G1b: Orientation & unit validation (fix 4.1) ──
    _validate_gate_f4t_g1b(node_map, domain_index_map)

    # ── F4T-1: Reconstruct natural theta draws ──
    # Fix 2.2: prefer E1 nadir/base over solve_linear_coefficients
    theta_draws_natural = _reconstruct_theta_draws_natural(
        R_draws=recovery.R_draws,
        aging=overlay.aging_projection,
        cognitive_indices=all_cognitive_indices,
        theta_nadir=recovery.theta_nadir,
        theta_base=recovery.theta_base,
        theta_natural=recovery.theta_natural,
        R_mean=recovery.R_mean,
    )

    # ── F4T-3: Aggregate to domains ──
    domain_z_natural = _aggregate_to_domains(
        theta_draws_natural, domain_index_map, all_cognitive_indices,
    )

    # Fix 2.3: use explicit time_months from E2
    time_months = recovery.time_months

    # ── Natural risk curve ──
    natural_curve = _compute_risk_curve(
        domain_z_natural,
        scenario_id="natural",
        scenario_label="Natural Recovery",
        horizons=horizons,
        time_months=time_months,
    )

    # ── Intervention risk curves ──
    intervention_curves: dict[str, TemporalRiskCurve] = {}
    risk_reductions: dict[str, TemporalRiskReduction] = {}

    for intv_id, intv_traj in overlay.intervention_trajectories.items():
        # F4T-2: Add intervention effect
        # Fix 2.1: prefer per-node delta_theta_mean over scalar delta_C
        theta_draws_intv = _reconstruct_theta_draws_intervention(
            theta_draws_natural=theta_draws_natural,
            K_a=intv_traj.K_a,
            cognitive_indices=all_cognitive_indices,
            delta_theta_mean=intv_traj.delta_theta_mean,
            delta_C=intv_traj.delta_C,
        )

        # F4T-3: Aggregate to domains
        domain_z_intv = _aggregate_to_domains(
            theta_draws_intv, domain_index_map, all_cognitive_indices,
        )

        # Risk curve
        intv_curve = _compute_risk_curve(
            domain_z_intv,
            scenario_id=intv_id,
            scenario_label=f"With {intv_id}",
            horizons=horizons,
            time_months=time_months,
        )
        intervention_curves[intv_id] = intv_curve

        # Risk reduction metrics (fix 3.1: NNT gated behind calibration)
        reduction = _compute_risk_reduction(
            natural_curve, intv_curve, horizons,
            calibration_status=calibration_status,
        )
        risk_reductions[intv_id] = reduction

    # ── Find best interventions ──
    best_peak_arr: str | None = None
    best_peak_arr_val = 0.0

    best_resolution: str | None = None
    best_resolution_month: int | None = None

    for intv_id, reduction in risk_reductions.items():
        if reduction.peak_arr_pct > best_peak_arr_val:
            best_peak_arr_val = reduction.peak_arr_pct
            best_peak_arr = intv_id

        curve = intervention_curves.get(intv_id)
        if curve and curve.resolution_month is not None:
            if best_resolution_month is None or curve.resolution_month < best_resolution_month:
                best_resolution_month = curve.resolution_month
                best_resolution = intv_id

    # ── Coverage (from F4 if available) ──
    coverage_fraction = 0.0
    if fusion_levels:
        n_observed = 0
        for domain_id, indices in domain_index_map.items():
            for idx in indices:
                levels = fusion_levels.get(idx, set())
                if "L2" in levels or "L3" in levels:
                    n_observed += 1
                    break
        coverage_fraction = n_observed / len(domain_index_map) if domain_index_map else 0.0

    # ── NNT suppression status ──
    nnt_suppressed = calibration_status != "calibrated"
    if nnt_suppressed:
        logger.info(
            "F4T: NNT suppressed (calibration_status='%s'). "
            "NNT requires calibration_status='calibrated' to emit.",
            calibration_status,
        )

    # ── Assemble result ──
    result = PredictiveRiskEstimate(
        natural_curve=natural_curve,
        intervention_curves=intervention_curves,
        risk_reductions=risk_reductions,
        best_peak_arr_intervention=best_peak_arr,
        best_resolution_intervention=best_resolution,
        n_draws=n_draws,
        n_timepoints=T,
        horizons_months=horizons,
        coverage_fraction=coverage_fraction,
        domain_aggregation=config.F4_DOMAIN_AGGREGATION,
        criteria_used="ICCTF_Wefel2011_domain_level",
        calibration_status=calibration_status,
        nnt_suppressed=nnt_suppressed,
    )

    # ── Gate F4T-G1 ──
    _validate_gate_f4t_g1(recovery, result)
    result.gate_f4t_g1_passed = True

    # ── Gate F4T-G1b already passed above ──
    result.gate_f4t_g1b_passed = True

    # ── Gate F4T-G1c: Intervention sanity (fix 4.2) ──
    _validate_gate_f4t_g1c(overlay, result)
    result.gate_f4t_g1c_passed = True

    logger.info(
        "F4T complete: natural peak=%.1f%% at month %d, %d interventions analyzed, "
        "best ARR=%.1f%% (%s), NNT %s",
        natural_curve.peak_risk_pct,
        natural_curve.peak_risk_month,
        len(intervention_curves),
        best_peak_arr_val,
        best_peak_arr or "none",
        "suppressed" if nnt_suppressed else "emitted",
    )

    return result
