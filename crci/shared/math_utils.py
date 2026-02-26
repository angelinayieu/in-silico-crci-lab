# VERIFIED: formulas match IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §2.3, §8.2.4
# VERIFIED: shared utilities for F4 (risk_estimator) and F4T (temporal_risk)
# VERIFIED: no hardcoded formula parameters — all from config.py
"""
Component: Shared Mathematical Utilities
Spec: IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §8.2.14

Shared utility functions extracted from specialized modules to avoid
code duplication between F4 (risk_estimator) and F4T (temporal_risk).

Functions:
    - solve_linear_coefficients: R(t)→θ(t) linear mapping coefficients
    - classify_crci_per_draw: ICCTF-based CRCI classification (Formula F4-1)
"""
from __future__ import annotations

import numpy as np

from crci.shared import config


# ═══════════════════════════════════════════════════════════════
#  Linear Coefficient Solving (§8.2.4 — R→θ mapping)
# ═══════════════════════════════════════════════════════════════


def solve_linear_coefficients(
    theta_natural: np.ndarray,
    R_mean: np.ndarray,
    epsilon: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve linear coefficients for R(t)→θ(t) reconstruction.

    The E3 model assumes:
        θ_i(t) = nadir_i + δ_i × R(t)

    where nadir_i is the cognitive nadir and δ_i is the recovery slope.
    This function solves for (nadir, delta) from the mean trajectory and
    mean recovery fraction.

    Formula F4T-1 (§8.2.4):
        θ^(m)_i(t) = nadir_i + δ_i × R^(m)(t) + δ_aging(t)

    Args:
        theta_natural: Shape (n_nodes, T) — mean natural trajectory from E2.
        R_mean: Shape (T,) — mean recovery fraction from E2.
        epsilon: Minimum R spread to avoid division by zero.

    Returns:
        Tuple of (nadir, delta) where:
            nadir: Shape (n_nodes,) — cognitive nadir per node
            delta: Shape (n_nodes,) — recovery slope per node
    """
    n_nodes, T = theta_natural.shape

    # R spread from start to end of trajectory
    r_spread = R_mean[-1] - R_mean[0] if T > 1 else 0.0

    nadir = np.zeros(n_nodes)
    delta = np.zeros(n_nodes)

    if abs(r_spread) > epsilon:
        for i in range(n_nodes):
            # Solve linear system: θ[0] = nadir + delta * R[0]
            #                       θ[-1] = nadir + delta * R[-1]
            delta[i] = (theta_natural[i, -1] - theta_natural[i, 0]) / r_spread
            nadir[i] = theta_natural[i, 0] - delta[i] * R_mean[0]
    else:
        # No recovery variation — flat trajectory (delta=0, nadir=initial theta)
        for i in range(n_nodes):
            nadir[i] = theta_natural[i, 0]
            delta[i] = 0.0

    return nadir, delta


# ═══════════════════════════════════════════════════════════════
#  ICCTF Classification (Formula F4-1)
# ═══════════════════════════════════════════════════════════════


def classify_crci_per_draw(
    domain_draws: dict[str, np.ndarray],
    z_multi: float | None = None,
    k_multi: int | None = None,
    z_single: float | None = None,
) -> np.ndarray:
    """Apply ICCTF criteria to each MC draw (Formula F4-1).

    CRCI^(m) = 1[Σ_d 1(z_d^(m) ≤ z_multi) ≥ k_multi]
               ∨ 1[∃d: z_d^(m) ≤ z_single]

    Reference: Wefel JS et al. Lancet Oncol. 2011;12(7):703-708.

    ICCTF criteria:
        - Multi-domain: ≥ k_multi domains with z ≤ z_multi (typically ≥2 with z ≤ -1.5)
        - Single severe: ≥1 domain with z ≤ z_single (typically z ≤ -2.0)

    Args:
        domain_draws: domain_id → (M,) z-score draws per domain.
        z_multi: Multi-domain threshold (default: F4_THRESHOLD_MULTI_DOMAIN_Z).
        k_multi: Required count for multi-domain criterion (default: F4_THRESHOLD_MULTI_DOMAIN_COUNT).
        z_single: Single severe threshold (default: F4_THRESHOLD_SINGLE_DOMAIN_Z).

    Returns:
        (M,) boolean array where True = CRCI positive for that draw.
    """
    # Use config defaults if not provided
    if z_multi is None:
        z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    if k_multi is None:
        k_multi = config.F4_THRESHOLD_MULTI_DOMAIN_COUNT
    if z_single is None:
        z_single = config.F4_THRESHOLD_SINGLE_DOMAIN_Z

    domains = list(domain_draws.keys())
    if not domains:
        return np.array([], dtype=bool)

    M = len(next(iter(domain_draws.values())))

    # Count domains below multi-domain threshold per draw
    below_multi = np.zeros(M, dtype=np.int32)
    any_below_single = np.zeros(M, dtype=bool)

    for d_id in domains:
        z_d = domain_draws[d_id]  # (M,)
        below_multi += (z_d <= z_multi).astype(np.int32)
        any_below_single |= (z_d <= z_single)

    # Formula F4-1: multi-domain criterion OR single severe criterion
    crci_indicator = (below_multi >= k_multi) | any_below_single

    return crci_indicator


def classify_crci_vectorized(
    domain_z_draws: np.ndarray,
    z_multi: float | None = None,
    k_multi: int | None = None,
    z_single: float | None = None,
) -> np.ndarray:
    """Vectorized ICCTF classification for temporal analysis (F4T).

    Same as classify_crci_per_draw but operates on a pre-stacked array
    for efficiency in temporal risk computation (§8.2.9).

    Args:
        domain_z_draws: Shape (n_domains, n_draws, T) — domain z-scores
            across draws and timepoints.
        z_multi: Multi-domain threshold.
        k_multi: Required count for multi-domain criterion.
        z_single: Single severe threshold.

    Returns:
        Shape (n_draws, T) boolean array where True = CRCI positive.
    """
    if z_multi is None:
        z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    if k_multi is None:
        k_multi = config.F4_THRESHOLD_MULTI_DOMAIN_COUNT
    if z_single is None:
        z_single = config.F4_THRESHOLD_SINGLE_DOMAIN_Z

    # domain_z_draws shape: (n_domains, n_draws, T)
    # Count domains below multi-threshold: sum across axis 0 → (n_draws, T)
    n_below_multi = np.sum(domain_z_draws <= z_multi, axis=0)

    # Any domain below single-threshold: any across axis 0 → (n_draws, T)
    any_below_single = np.any(domain_z_draws <= z_single, axis=0)

    # CRCI positive: multi-domain OR single severe
    crci_positive = (n_below_multi >= k_multi) | any_below_single

    return crci_positive


# ═══════════════════════════════════════════════════════════════
#  Domain Extraction Utilities
# ═══════════════════════════════════════════════════════════════


def aggregate_domain_draws(
    theta_draws: np.ndarray,
    domain_index_map: dict[str, list[int]],
    aggregation: str | None = None,
) -> dict[str, np.ndarray]:
    """Extract per-domain z-score draws from full posterior draws.

    For each domain, aggregate the z-scores of its constituent node(s)
    using the configured aggregation method.

    Args:
        theta_draws: Shape (M, n_nodes) or (M, T, n_nodes) — posterior draws.
        domain_index_map: domain_id → list[column_index] mapping.
        aggregation: "mean" or "min" (default: config.F4_DOMAIN_AGGREGATION).

    Returns:
        domain_id → array of per-draw domain z-scores.
        Shape matches input: (M,) for 2D input, (M, T) for 3D input.
    """
    if aggregation is None:
        aggregation = config.F4_DOMAIN_AGGREGATION

    domain_draws: dict[str, np.ndarray] = {}

    for domain_id, indices in domain_index_map.items():
        if not indices:
            continue

        if len(indices) == 1:
            # Single node — no aggregation needed
            if theta_draws.ndim == 2:
                domain_draws[domain_id] = theta_draws[:, indices[0]]
            else:  # 3D: (M, T, n_nodes)
                domain_draws[domain_id] = theta_draws[:, :, indices[0]]
        else:
            # Multiple nodes → aggregate
            if theta_draws.ndim == 2:
                node_z = theta_draws[:, indices]  # (M, n_nodes_in_domain)
                if aggregation == "min":
                    domain_draws[domain_id] = np.min(node_z, axis=1)
                else:
                    domain_draws[domain_id] = np.mean(node_z, axis=1)
            else:  # 3D: (M, T, n_nodes)
                node_z = theta_draws[:, :, indices]  # (M, T, n_nodes_in_domain)
                if aggregation == "min":
                    domain_draws[domain_id] = np.min(node_z, axis=2)
                else:
                    domain_draws[domain_id] = np.mean(node_z, axis=2)

    return domain_draws
