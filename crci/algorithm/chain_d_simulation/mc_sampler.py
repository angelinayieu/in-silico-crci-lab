# VERIFIED: formulas [D1a-EQ1, D1a-EQ2, D1b-EQ1, D1c-EQ1, D1c-EQ2] match spec SYS_ALG lines 2185-2229
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads FrozenModelState from frozen_state.py, PatientState from modifier_application.py
# VERIFIED: forward wiring — writes MCDraws for D2 effect_propagation (same file, future slice)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [D-G1] raises on failure
"""
Component: SYS_ALGORITHM.ALG-D.D1
Spec: SYS_ALGORITHM_COMPLETE.md lines 2173-2229
Formulas:
    D1a-EQ1: β_e^(m) ~ N(μ_e, σ²_{eff,e})
    D1a-EQ2: σ²_{sampling} = σ²_{eff,e} × SE_modifier_adj²  (C4c inflation)
    D1b-EQ1: Include_e^(m) ~ Bernoulli(P_inclusion(e))
    D1c-EQ1: Σ_post = L·Lᵀ  (Cholesky decomposition, pre-computed once)
    D1c-EQ2: θ₀^(m) = θ̂ + L · z^(m),  z ~ N(0, I)
Reads: FrozenModelState (from chain_b_evidence/frozen_state.py),
       PatientState (from chain_c_posterior/modifier_application.py)
Writes: MCDraws (consumed by D2 effect propagation, D3, D4)
Gates: D-G1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import linalg as sp_linalg

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_b_evidence.frozen_state import FrozenModelState
from ..chain_c_posterior.modifier_application import PatientState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class MCDraws:
    """Output of D1: 10,000 joint Monte Carlo draws.

    Fields per spec SYS_ALG lines 2118-2125.
    Consumed by D2 (effect propagation), D3 (synergy), D4 (ranking).
    """

    # Number of draws
    n_draws: int

    # D1a: Sampled edge weights — shape (n_draws, n_nodes, n_nodes)
    beta_draws: np.ndarray

    # D1b: Structural inclusion masks — shape (n_draws, n_nodes, n_nodes)
    include_draws: np.ndarray

    # D1: Effective B per draw = beta_draws × include_draws
    # shape (n_draws, n_nodes, n_nodes)
    B_draws: np.ndarray

    # D1c: Sampled patient baselines — shape (n_draws, n_nodes)
    theta0_draws: np.ndarray

    # Metadata
    seed: int
    n_nodes: int
    n_edges_sampled: int  # edges that were actively sampled (not always-present/absent)
    n_always_present: int  # edges with P >= 0.99
    n_always_absent: int  # edges with P <= 0.05
    n_sign_rejections: int  # total sign-flip rejection events across all draws


# ═══════════════════════════════════════════════════════════════
#  D1a: Edge Weight Sampling
# ═══════════════════════════════════════════════════════════════


def _sample_edge_weights(
    B_hat: np.ndarray,
    Sigma_eff: dict[str, float],
    modifier_se_inflation: dict[str, float],
    edge_map: dict[str, tuple[int, int]],
    edge_signs: dict[str, float],
    n_draws: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """D1a: Sample edge weights from posterior distributions.

    Formula D1a-EQ1:
        β_e^(m) ~ N(μ_e, σ²_{eff,e})

    Formula D1a-EQ2 (C4c inflation):
        σ²_{sampling} = σ²_{eff,e} × SE_modifier_adj²

    Sign preservation: reject draws that flip biological sign constraint.

    Args:
        B_hat: Mean edge weight matrix (n_nodes × n_nodes).
        Sigma_eff: edge_id → SE_eff (from Chain B).
        modifier_se_inflation: edge_id → SE multiplier (from C4c).
        edge_map: edge_id → (source_idx, target_idx).
        edge_signs: edge_id → expected sign (+1 or -1), 0 if unconstrained.
        n_draws: Number of MC draws.
        rng: Seeded random number generator.

    Returns:
        Tuple of (beta_draws array [n_draws, n, n], n_sign_rejections).
    """
    n = B_hat.shape[0]
    beta_draws = np.zeros((n_draws, n, n))
    total_rejections = 0

    for edge_id, (src, tgt) in edge_map.items():
        mu_e = B_hat[src, tgt]
        if mu_e == 0.0 and edge_id not in Sigma_eff:
            # Zero edge with no SE — skip
            continue

        # Formula D1a-EQ1: σ² = SE²_eff
        se_eff = Sigma_eff.get(edge_id, 0.0)
        if se_eff <= 0.0 or not np.isfinite(se_eff):
            # Deterministic edge (no uncertainty) or infinite SE (no evidence)
            beta_draws[:, src, tgt] = mu_e
            continue

        # Formula D1a-EQ2: Apply C4c modifier SE inflation
        se_mult = modifier_se_inflation.get(edge_id, 1.0)
        sigma_sq_sampling = (se_eff * se_mult) ** 2

        # Sample: β_e^(m) ~ N(μ_e, σ²_{sampling})
        samples = rng.normal(mu_e, np.sqrt(sigma_sq_sampling), size=n_draws)

        # Sign preservation: reject draws that flip sign (biological constraint)
        expected_sign = edge_signs.get(edge_id, 0.0)
        if expected_sign != 0.0:
            for attempt in range(config.D1_SIGN_PRESERVATION_MAX_RETRIES):
                if expected_sign > 0:
                    violations = samples < 0
                elif expected_sign < 0:
                    violations = samples > 0
                else:
                    break

                n_violations = int(np.sum(violations))
                if n_violations == 0:
                    break

                total_rejections += n_violations
                # Resample only the violating draws
                samples[violations] = rng.normal(
                    mu_e, np.sqrt(sigma_sq_sampling), size=n_violations,
                )
            else:
                # After max retries, clip remaining violations to 0
                if expected_sign > 0:
                    samples = np.maximum(samples, 0.0)
                else:
                    samples = np.minimum(samples, 0.0)

        beta_draws[:, src, tgt] = samples

    return beta_draws, total_rejections


# ═══════════════════════════════════════════════════════════════
#  D1b: Structural Inclusion Sampling
# ═══════════════════════════════════════════════════════════════


def _sample_structural_inclusion(
    P_inclusion: dict[str, float],
    edge_map: dict[str, tuple[int, int]],
    n_draws: int,
    n_nodes: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int, int, int]:
    """D1b: Sample which edges exist in each model realization.

    Formula D1b-EQ1:
        Include_e^(m) ~ Bernoulli(P_inclusion(e))

    Optimizations (spec lines 2214-2216):
        P >= 0.99 → always present (skip sampling)
        P <= 0.05 → always absent (skip sampling)

    Args:
        P_inclusion: edge_id → inclusion probability (from Chain B4).
        edge_map: edge_id → (source_idx, target_idx).
        n_draws: Number of MC draws.
        n_nodes: Number of nodes in graph.
        rng: Seeded random number generator.

    Returns:
        Tuple of (include_draws [n_draws, n, n],
                  n_sampled, n_always_present, n_always_absent).
    """
    include_draws = np.zeros((n_draws, n_nodes, n_nodes))
    n_always_present = 0
    n_always_absent = 0
    n_sampled = 0

    for edge_id, (src, tgt) in edge_map.items():
        p = P_inclusion.get(edge_id, 1.0)

        if p >= config.D1_INCLUSION_ALWAYS_PRESENT:
            # Always present — no sampling needed
            include_draws[:, src, tgt] = 1.0
            n_always_present += 1
        elif p <= config.D1_INCLUSION_ALWAYS_ABSENT:
            # Always absent — no sampling needed
            include_draws[:, src, tgt] = 0.0
            n_always_absent += 1
        else:
            # Formula D1b-EQ1: Include ~ Bernoulli(P)
            include_draws[:, src, tgt] = rng.binomial(1, p, size=n_draws).astype(
                float,
            )
            n_sampled += 1

    logger.info(
        "D1b: Structural inclusion — %d sampled, %d always-present, %d always-absent",
        n_sampled, n_always_present, n_always_absent,
    )

    return include_draws, n_sampled, n_always_present, n_always_absent


# ═══════════════════════════════════════════════════════════════
#  D1c: Patient Baseline Sampling
# ═══════════════════════════════════════════════════════════════


def _sample_patient_baselines(
    theta_hat: np.ndarray,
    Sigma_post: np.ndarray,
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """D1c: Sample patient's true state from posterior distribution.

    Formula D1c-EQ1:
        Σ_post = L · Lᵀ  (Cholesky, pre-computed once)

    Formula D1c-EQ2:
        θ₀^(m) = θ̂ + L · z^(m),  z ~ N(0, I)

    Clipping: θ₀^(m) clipped to ±4 SD per node (numerical guard, spec line 2228).

    Args:
        theta_hat: Posterior mean (n_nodes,).
        Sigma_post: Posterior covariance (n_nodes × n_nodes).
        n_draws: Number of MC draws.
        rng: Seeded random number generator.

    Returns:
        theta0_draws array (n_draws, n_nodes).
    """
    n = len(theta_hat)

    # Formula D1c-EQ1: Cholesky decomposition (pre-compute once)
    try:
        L = sp_linalg.cholesky(Sigma_post, lower=True)
    except np.linalg.LinAlgError:
        # Sigma_post not PD — add small diagonal jitter
        jitter = 1e-8 * np.eye(n)
        logger.warning(
            "D1c: Sigma_post not PD — adding jitter %.1e", 1e-8,
        )
        L = sp_linalg.cholesky(Sigma_post + jitter, lower=True)

    # Formula D1c-EQ2: θ₀^(m) = θ̂ + L · z^(m)
    z_draws = rng.standard_normal(size=(n_draws, n))  # z ~ N(0, I)
    theta0_draws = theta_hat[np.newaxis, :] + z_draws @ L.T  # (n_draws, n)

    # Clip to ±4 SD per node (spec line 2228)
    sd_per_node = np.sqrt(np.diag(Sigma_post))
    clip_bound = config.D1_BASELINE_CLIP_SD * sd_per_node
    lower = theta_hat - clip_bound
    upper = theta_hat + clip_bound
    n_clipped = int(np.sum(
        (theta0_draws < lower[np.newaxis, :])
        | (theta0_draws > upper[np.newaxis, :]),
    ))

    theta0_draws = np.clip(theta0_draws, lower[np.newaxis, :], upper[np.newaxis, :])

    if n_clipped > 0:
        logger.info(
            "D1c: Clipped %d extreme baseline values to ±%.0f SD",
            n_clipped, config.D1_BASELINE_CLIP_SD,
        )

    return theta0_draws


# ═══════════════════════════════════════════════════════════════
#  Utility: Build edge map from graph
# ═══════════════════════════════════════════════════════════════


def _build_edge_map(
    frozen: FrozenModelState,
) -> tuple[dict[str, tuple[int, int]], dict[str, float]]:
    """Build edge_id → (source_idx, target_idx) and expected sign mappings.

    Args:
        frozen: FrozenModelState with graph reference.

    Returns:
        Tuple of (edge_map, edge_signs).
        edge_signs: edge_id → +1.0 (positive), -1.0 (negative), 0.0 (unconstrained).
    """
    edge_map: dict[str, tuple[int, int]] = {}
    edge_signs: dict[str, float] = {}
    node_index = frozen.graph.node_map.node_index

    for edge in frozen.graph.b_skeleton.edges:
        src_idx = node_index.get(edge.source_node_id)
        tgt_idx = node_index.get(edge.target_node_id)
        if src_idx is not None and tgt_idx is not None:
            edge_map[edge.edge_id] = (src_idx, tgt_idx)
            # Map expected_sign string to float
            if edge.expected_sign == "positive":
                edge_signs[edge.edge_id] = 1.0
            elif edge.expected_sign == "negative":
                edge_signs[edge.edge_id] = -1.0
            else:
                edge_signs[edge.edge_id] = 0.0

    return edge_map, edge_signs


# ═══════════════════════════════════════════════════════════════
#  Gate D-G1: Sampling Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_d_g1(mc_draws: MCDraws) -> None:
    """Gate D-G1: 10,000 draws generated; no NaN in β; all Include ∈ {0,1}.

    Conditions (spec line 2516):
        1. Correct number of draws generated
        2. No NaN values in beta_draws
        3. All include_draws values are exactly 0 or 1

    Raises:
        GateViolation: If any condition fails.
    """
    # Condition 1: Correct draw count
    if mc_draws.n_draws != mc_draws.beta_draws.shape[0]:
        raise GateViolation(
            "D-G1",
            f"Draw count mismatch: expected {mc_draws.n_draws}, "
            f"got {mc_draws.beta_draws.shape[0]}",
        )

    # Condition 2: No NaN in beta_draws
    n_nan_beta = int(np.sum(np.isnan(mc_draws.beta_draws)))
    if n_nan_beta > 0:
        raise GateViolation(
            "D-G1",
            f"Found {n_nan_beta} NaN values in beta_draws",
        )

    # Also check B_draws (the effective matrix)
    n_nan_B = int(np.sum(np.isnan(mc_draws.B_draws)))
    if n_nan_B > 0:
        raise GateViolation(
            "D-G1",
            f"Found {n_nan_B} NaN values in B_draws",
        )

    # Condition 3: Include values are exactly 0 or 1
    unique_include = np.unique(mc_draws.include_draws[mc_draws.include_draws != 0.0])
    if len(unique_include) > 0 and not np.allclose(unique_include, 1.0):
        bad_vals = unique_include[~np.isclose(unique_include, 1.0)]
        raise GateViolation(
            "D-G1",
            f"Include draws contain non-binary values: {bad_vals[:5]}",
        )

    # Check theta0_draws for NaN/Inf
    n_nan_theta = int(np.sum(~np.isfinite(mc_draws.theta0_draws)))
    if n_nan_theta > 0:
        raise GateViolation(
            "D-G1",
            f"Found {n_nan_theta} non-finite values in theta0_draws",
        )

    logger.info(
        "Gate D-G1 PASSED: %d draws, 0 NaN in β, "
        "all Include ∈ {0,1}, θ₀ finite. "
        "(%d always-present, %d always-absent, %d sign rejections)",
        mc_draws.n_draws,
        mc_draws.n_always_present,
        mc_draws.n_always_absent,
        mc_draws.n_sign_rejections,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: generate_mc_draws (D1 entry point)
# ═══════════════════════════════════════════════════════════════


def generate_mc_draws(
    frozen: FrozenModelState,
    patient_state: PatientState,
    n_draws: int | None = None,
    seed: int | None = None,
) -> MCDraws:
    """D1: Generate Monte Carlo draws for intervention simulation.

    Produces joint samples of:
        D1a — Edge weights β^(m) from posterior distributions
        D1b — Structural inclusion masks Include^(m)
        D1c — Patient baselines θ₀^(m) from posterior

    Common random numbers: same seed → same model realization →
    only the intervention differs between comparisons.

    Args:
        frozen: FrozenModelState with B̂, Σ_eff, P_inclusion.
        patient_state: PatientState with θ̂, Σ_post, modifier_se_inflation.
        n_draws: Number of MC draws (default: config.MC_DRAWS = 10,000).
        seed: Random seed (default: config.MC_DEFAULT_SEED = 42).

    Returns:
        MCDraws with all sampled arrays.

    Raises:
        GateViolation: If D-G1 fails.
    """
    if n_draws is None:
        n_draws = config.MC_DRAWS
    if seed is None:
        seed = config.MC_DEFAULT_SEED

    n_nodes = frozen.B_hat.shape[0]

    logger.info(
        "── D1: Monte Carlo Sampling ──\n"
        "  n_draws=%d, seed=%d, n_nodes=%d",
        n_draws, seed, n_nodes,
    )

    # Seeded RNG for reproducibility (common random numbers)
    rng = np.random.default_rng(seed)

    # Build edge map from graph
    edge_map, edge_signs = _build_edge_map(frozen)

    # D1a: Sample edge weights
    beta_draws, n_sign_rejections = _sample_edge_weights(
        B_hat=frozen.B_hat,
        Sigma_eff=frozen.Sigma_eff,
        modifier_se_inflation=patient_state.modifier_se_inflation,
        edge_map=edge_map,
        edge_signs=edge_signs,
        n_draws=n_draws,
        rng=rng,
    )

    # D1b: Sample structural inclusion
    include_draws, n_sampled, n_always_present, n_always_absent = (
        _sample_structural_inclusion(
            P_inclusion=frozen.P_inclusion,
            edge_map=edge_map,
            n_draws=n_draws,
            n_nodes=n_nodes,
            rng=rng,
        )
    )

    # D1c: Sample patient baselines
    theta0_draws = _sample_patient_baselines(
        theta_hat=patient_state.theta_hat,
        Sigma_post=patient_state.Sigma_post,
        n_draws=n_draws,
        rng=rng,
    )

    # Compute effective B per draw: B_draw = beta_draw × include_draw
    B_draws = beta_draws * include_draws

    mc_draws = MCDraws(
        n_draws=n_draws,
        beta_draws=beta_draws,
        include_draws=include_draws,
        B_draws=B_draws,
        theta0_draws=theta0_draws,
        seed=seed,
        n_nodes=n_nodes,
        n_edges_sampled=n_sampled,
        n_always_present=n_always_present,
        n_always_absent=n_always_absent,
        n_sign_rejections=n_sign_rejections,
    )

    # Gate D-G1
    _validate_gate_d_g1(mc_draws)

    logger.info(
        "D1: MC sampling complete — %d draws, %d edges "
        "(%d sampled, %d always-present, %d always-absent)",
        n_draws, len(edge_map),
        n_sampled, n_always_present, n_always_absent,
    )

    return mc_draws
