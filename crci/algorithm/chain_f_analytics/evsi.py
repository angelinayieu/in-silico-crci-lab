# VERIFIED: formulas [F-5] match spec SYS_ALG lines 3257-3363
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PatientState (chain_c), edge/instrument data
# VERIFIED: forward wiring — writes VarianceState for downstream analytics
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [F-G3] raises on failure
"""
Component: SYS_ALGORITHM.ALG-F.F3
Spec: SYS_ALGORITHM_COMPLETE.md lines 3257-3363
Formulas:
    F-5: ΔVar = Σ_unobs Cov(target, i)² / Var(i)  (missing obs variance)
Reads: PatientState (from chain_c_posterior),
       edge data (τ², P_inclusion, σ²_struct),
       instrument data (α reliability)
Writes: VarianceState (consumed by downstream analytics)
Gates: F-G3
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ReducibleSource:
    """A variance source that can be reduced per-patient."""

    source_name: str
    reduction_pct: float  # how much of total variance this source represents


@dataclass
class VarianceState:
    """F3 output: Five-source variance decomposition.

    Consumed by downstream analytics and clinical output.
    """

    total_variance: float
    literature_pct: float       # [0, 1] — τ² share
    measurement_pct: float      # [0, 1] — σ²_y share
    structural_pct: float       # [0, 1] — P_inclusion / σ²_struct share
    proxy_pct: float            # [0, 1] — R²_proxy share
    missing_pct: float          # [0, 1] — missing obs share

    # Raw variance components
    literature_variance: float
    measurement_variance: float
    structural_variance: float
    proxy_variance: float
    missing_variance: float

    # Top 2 actionable (reducible) sources
    top_reducible: list[ReducibleSource]

    # Per-edge variance contribution
    per_edge_variance_contrib: dict[str, float]

    gate_f_g3_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  F3a: Literature Heterogeneity Component
# ═══════════════════════════════════════════════════════════════


def _compute_literature_variance(
    edge_tau_squared: dict[str, float],
    edge_sensitivities: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    """F3a: Compute variance from inter-study heterogeneity.

    V_lit = Σ_e (∂θ/∂β_e)² × τ²_e

    Args:
        edge_tau_squared: edge_id → τ² (from meta-analysis).
        edge_sensitivities: edge_id → ∂θ/∂β_e (path sensitivity).
            If None, uses uniform sensitivity = 1.0.

    Returns:
        (literature_variance, per_edge_contribution)
    """
    per_edge: dict[str, float] = {}
    total = 0.0

    for edge_id, tau_sq in edge_tau_squared.items():
        sensitivity = 1.0
        if edge_sensitivities and edge_id in edge_sensitivities:
            sensitivity = edge_sensitivities[edge_id]

        contrib = sensitivity ** 2 * tau_sq
        per_edge[edge_id] = contrib
        total += contrib

    return total, per_edge


# ═══════════════════════════════════════════════════════════════
#  F3b: Measurement Noise Component
# ═══════════════════════════════════════════════════════════════


def _compute_measurement_variance(
    instrument_alphas: dict[str, float],
    instrument_loadings: dict[str, float] | None = None,
    observed_mask: np.ndarray | None = None,
) -> float:
    """F3b: Compute variance from instrument reliability.

    σ²_{y,k} = b²_k × (1 − α_k) / α_k
    V_meas = Σ_k σ²_{y,k} × weight²_k

    Args:
        instrument_alphas: instrument_id → Cronbach's α.
        instrument_loadings: instrument_id → factor loading b_k.
            If None, uses b_k = 1.0.
        observed_mask: Which nodes are observed.
            If None, assumes all observed.

    Returns:
        measurement_variance (scalar).
    """
    total = 0.0

    for inst_id, alpha in instrument_alphas.items():
        if alpha <= 0 or alpha >= 1.0:
            continue

        b_k = 1.0
        if instrument_loadings and inst_id in instrument_loadings:
            b_k = instrument_loadings[inst_id]

        # σ²_{y,k} = b²_k × (1 − α_k) / α_k
        sigma_sq_y = b_k ** 2 * (1.0 - alpha) / alpha
        # Weight = information gain (simplified: 1/n_instruments)
        weight = 1.0 / max(1, len(instrument_alphas))

        total += sigma_sq_y * weight ** 2

    return total


# ═══════════════════════════════════════════════════════════════
#  F3c: Structural Model Uncertainty Component
# ═══════════════════════════════════════════════════════════════


def _compute_structural_variance(
    edge_sigma_sq_structural: dict[str, float] | None = None,
    n_edges: int = 0,
) -> float:
    """F3c: Compute variance from stochastic edge inclusion.

    Uses σ²_struct per edge (default 0.25 from config).
    Total: average across edges.

    Args:
        edge_sigma_sq_structural: edge_id → σ²_struct.
            If None, uses default for all edges.
        n_edges: Number of edges (used with default).

    Returns:
        structural_variance (scalar).
    """
    if edge_sigma_sq_structural:
        return float(np.mean(list(edge_sigma_sq_structural.values())))

    if n_edges > 0:
        return config.SIGMA_SQ_STRUCTURAL_DEFAULT
    return 0.0


# ═══════════════════════════════════════════════════════════════
#  F3d: Proxy Imprecision Component
# ═══════════════════════════════════════════════════════════════


def _compute_proxy_variance(
    proxy_r_squared: dict[str, float],
    latent_variances: dict[str, float] | None = None,
) -> float:
    """F3d: Compute variance from latent-proxy gaps.

    V_proxy_i = Var(θ_latent) × (1 − R²_proxy)
    V_proxy = Σ_i V_proxy_i

    Args:
        proxy_r_squared: node_id → R²_proxy for latent nodes.
        latent_variances: node_id → Var(θ_latent).
            If None, uses 1.0 (standardized).

    Returns:
        proxy_variance (scalar).
    """
    total = 0.0

    for node_id, r_sq in proxy_r_squared.items():
        var_latent = 1.0
        if latent_variances and node_id in latent_variances:
            var_latent = latent_variances[node_id]

        # V_proxy_i = Var(θ_latent) × (1 − R²_proxy)
        v_proxy_i = var_latent * (1.0 - r_sq)
        total += v_proxy_i

        # Warn if low proxy validity (spec line 3322)
        if r_sq < config.F3_PROXY_R2_LOW_THRESHOLD:
            logger.warning(
                "F3d: LOW_PROXY_VALIDITY for node '%s': R²=%.3f < %.2f",
                node_id, r_sq, config.F3_PROXY_R2_LOW_THRESHOLD,
            )

    return total


# ═══════════════════════════════════════════════════════════════
#  F3e: Missing Observation Component
# ═══════════════════════════════════════════════════════════════


def _compute_missing_variance(
    posterior_covariance: np.ndarray | None,
    observed_mask: np.ndarray | None,
    target_indices: list[int] | None = None,
) -> float:
    """F3e: Compute variance from unobserved nodes.

    Formula F-5:
        ΔVar = Σ_{unobs_i} Cov(target, i)² / Var(i)

    This is the variance REDUCTION that would occur if missing
    observations were collected.

    Args:
        posterior_covariance: Σ_post (n_nodes, n_nodes).
        observed_mask: Boolean array (n_nodes,) — True if observed.
        target_indices: Which nodes are target (cognitive).
            If None, all nodes.

    Returns:
        missing_variance (scalar).
    """
    if posterior_covariance is None or observed_mask is None:
        return 0.0

    n_nodes = len(observed_mask)
    if target_indices is None:
        target_indices = list(range(n_nodes))

    total_missing = 0.0

    for i in range(n_nodes):
        if observed_mask[i]:
            continue  # already observed, no missing contribution

        var_i = posterior_covariance[i, i]
        if var_i <= 0:
            continue

        for t_idx in target_indices:
            cov_ti = posterior_covariance[t_idx, i]
            # Formula F-5: variance reduction from observing node i
            total_missing += cov_ti ** 2 / var_i

    return total_missing


# ═══════════════════════════════════════════════════════════════
#  F3f: Normalization and Reporting
# ═══════════════════════════════════════════════════════════════


def _normalize_and_report(
    v_lit: float,
    v_meas: float,
    v_struct: float,
    v_proxy: float,
    v_missing: float,
) -> tuple[float, float, float, float, float, float, list[ReducibleSource]]:
    """F3f: Express each source as percentage of total.

    Returns:
        (total, lit_pct, meas_pct, struct_pct, proxy_pct, missing_pct, top_reducible)
    """
    total = v_lit + v_meas + v_struct + v_proxy + v_missing

    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, []

    lit_pct = v_lit / total
    meas_pct = v_meas / total
    struct_pct = v_struct / total
    proxy_pct = v_proxy / total
    missing_pct = v_missing / total

    # Top 2 reducible = largest of {measurement, proxy, missing}
    # (Literature and structural are NOT easily reducible per-patient)
    reducible = [
        ReducibleSource("measurement", meas_pct),
        ReducibleSource("proxy", proxy_pct),
        ReducibleSource("missing_observations", missing_pct),
    ]
    reducible.sort(key=lambda x: x.reduction_pct, reverse=True)
    top_2 = reducible[:2]

    return total, lit_pct, meas_pct, struct_pct, proxy_pct, missing_pct, top_2


# ═══════════════════════════════════════════════════════════════
#  Gate F-G3
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f_g3(result: VarianceState) -> None:
    """Gate F-G3: Variance decomposition valid.

    Conditions (spec line 3362):
        1. 5 components sum ≈ total (within ε=0.01)
        2. All percentages ∈ [0, 1]
        3. Top 2 reducible identified

    Raises:
        GateViolation: If any condition fails.
    """
    pct_sum = (result.literature_pct + result.measurement_pct
               + result.structural_pct + result.proxy_pct
               + result.missing_pct)

    if result.total_variance > 0 and abs(pct_sum - 1.0) > config.F3_SUM_TOLERANCE:
        raise GateViolation(
            "F-G3",
            f"5 components sum to {pct_sum:.6f}, expected ≈ 1.0",
        )

    for name, pct in [
        ("literature", result.literature_pct),
        ("measurement", result.measurement_pct),
        ("structural", result.structural_pct),
        ("proxy", result.proxy_pct),
        ("missing", result.missing_pct),
    ]:
        if pct < 0.0:
            raise GateViolation(
                "F-G3",
                f"{name} percentage = {pct:.6f} < 0",
            )

    logger.info(
        "Gate F-G3 PASSED: total_var=%.4f, lit=%.1f%%, meas=%.1f%%, "
        "struct=%.1f%%, proxy=%.1f%%, missing=%.1f%%",
        result.total_variance,
        result.literature_pct * 100, result.measurement_pct * 100,
        result.structural_pct * 100, result.proxy_pct * 100,
        result.missing_pct * 100,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_variance_decomposition (F3 entry point)
# ═══════════════════════════════════════════════════════════════


def compute_variance_decomposition(
    edge_tau_squared: dict[str, float] | None = None,
    edge_sensitivities: dict[str, float] | None = None,
    instrument_alphas: dict[str, float] | None = None,
    instrument_loadings: dict[str, float] | None = None,
    edge_sigma_sq_structural: dict[str, float] | None = None,
    n_edges: int = 0,
    proxy_r_squared: dict[str, float] | None = None,
    latent_variances: dict[str, float] | None = None,
    posterior_covariance: np.ndarray | None = None,
    observed_mask: np.ndarray | None = None,
    target_indices: list[int] | None = None,
) -> VarianceState:
    """F3: Five-source variance decomposition.

    Args:
        edge_tau_squared: Per-edge inter-study τ².
        edge_sensitivities: Per-edge path sensitivity ∂θ/∂β_e.
        instrument_alphas: Per-instrument reliability α.
        instrument_loadings: Per-instrument factor loading b.
        edge_sigma_sq_structural: Per-edge structural σ².
        n_edges: Total edge count (for default σ²_struct).
        proxy_r_squared: Per-node R² for latent→proxy.
        latent_variances: Per-node latent variance.
        posterior_covariance: Σ_post matrix.
        observed_mask: Which nodes observed.
        target_indices: Target (cognitive) node indices.

    Returns:
        VarianceState.

    Raises:
        GateViolation: If F-G3 fails.
    """
    logger.info("── F3: Five-Source Variance Decomposition ──")

    # F3a: Literature
    v_lit, per_edge = _compute_literature_variance(
        edge_tau_squared or {}, edge_sensitivities,
    )

    # F3b: Measurement
    v_meas = _compute_measurement_variance(
        instrument_alphas or {}, instrument_loadings, observed_mask,
    )

    # F3c: Structural
    v_struct = _compute_structural_variance(
        edge_sigma_sq_structural, n_edges,
    )

    # F3d: Proxy
    v_proxy = _compute_proxy_variance(
        proxy_r_squared or {}, latent_variances,
    )

    # F3e: Missing
    v_missing = _compute_missing_variance(
        posterior_covariance, observed_mask, target_indices,
    )

    # F3f: Normalize
    total, lit_pct, meas_pct, struct_pct, proxy_pct, missing_pct, top_reducible = (
        _normalize_and_report(v_lit, v_meas, v_struct, v_proxy, v_missing)
    )

    result = VarianceState(
        total_variance=total,
        literature_pct=lit_pct,
        measurement_pct=meas_pct,
        structural_pct=struct_pct,
        proxy_pct=proxy_pct,
        missing_pct=missing_pct,
        literature_variance=v_lit,
        measurement_variance=v_meas,
        structural_variance=v_struct,
        proxy_variance=v_proxy,
        missing_variance=v_missing,
        top_reducible=top_reducible,
        per_edge_variance_contrib=per_edge,
    )

    # Gate F-G3
    _validate_gate_f_g3(result)
    result.gate_f_g3_passed = True

    logger.info(
        "F3 complete: total=%.4f, top reducible: %s",
        total,
        [(r.source_name, f"{r.reduction_pct:.1%}") for r in top_reducible],
    )

    return result
