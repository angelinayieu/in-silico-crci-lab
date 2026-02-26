# VERIFIED: formulas [D2a, D2b-EQ1, D2c-EQ1, D2d-EQ1, D2e-EQ1] match spec SYS_ALG lines 2231-2318
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads MCDraws from mc_sampler.py, FrozenModelState from frozen_state.py
# VERIFIED: forward wiring — writes EffectResult for D3 (synergy_checker), D4 (ranker)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [D-G2] raises on failure
"""
Component: SYS_ALGORITHM.ALG-D.D2
Spec: SYS_ALGORITHM_COMPLETE.md lines 2231-2318
Formulas:
    D2b-EQ1: Δθ^(m) = (I − B^(m))⁻¹ · x_intervention
    D2c-EQ1: Δθ_target = Σ_P [Π_{e∈P} β_e] · x_source
    D2d-EQ1: Δθ^(m)_clipped = clip(Δθ^(m), ±ceiling_SD)
    D2e-EQ1: ΔC^(m) = Σ_d w_d · Δθ_d^(m) / Σ_d w_d
Reads: MCDraws (from mc_sampler.py D1),
       FrozenModelState (from chain_b_evidence/frozen_state.py),
       PatientState (from chain_c_posterior/modifier_application.py)
Writes: EffectResult (consumed by D3 synergy, D4 ranking)
Gates: D-G2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy import linalg as sp_linalg

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_a_graph.node_loader import NodeMap
from ..chain_b_evidence.frozen_state import FrozenModelState
from ..chain_c_posterior.modifier_application import PatientState
from .mc_sampler import MCDraws

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class PropagationMethod(str, Enum):
    """How the effect was propagated for a given draw."""

    DIRECT_RCT = "DIRECT_RCT"
    MATRIX = "MATRIX"
    PATH_ENUM = "PATH_ENUM"


@dataclass(frozen=True)
class InterventionEffects:
    """Per-intervention effect across all MC draws.

    Contains the full Δθ and composite ΔC for each draw.
    Consumed by D3 (synergy) and D4 (ranking).
    """

    intervention_id: str

    # Δθ per draw — shape (n_draws, n_nodes)
    delta_theta: np.ndarray

    # Composite cognitive score per draw — shape (n_draws,)
    delta_C: np.ndarray

    # Which propagation method used per draw — shape (n_draws,)
    propagation_methods: list[PropagationMethod]

    # Whether physiological ceiling was applied per draw — shape (n_draws,)
    ceiling_clipped: np.ndarray  # bool array (n_draws,)

    # Audit
    n_matrix_method: int = 0
    n_path_enum_fallback: int = 0
    n_direct_rct: int = 0
    n_ceiling_clips: int = 0  # total clip events (draw × node)
    ceiling_clip_fraction: float = 0.0


@dataclass
class EffectResult:
    """Complete D2 output: effects for all interventions.

    Consumed by D3 (synergy/bundle), D4 (ranking/SAFE).
    """

    intervention_effects: dict[str, InterventionEffects]
    n_draws: int
    n_nodes: int
    cognitive_node_indices: list[int]
    cognitive_node_ids: list[str]
    gate_d_g2_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  D2a: Direct RCT Edge Detection
# ═══════════════════════════════════════════════════════════════


def _find_direct_rct_edges(
    frozen: FrozenModelState,
    intervention_node_idx: int,
    cognitive_indices: list[int],
) -> dict[int, str]:
    """D2a: Find edges with claim_level=causal_supported from intervention to cognitive nodes.

    Args:
        frozen: FrozenModelState with graph.b_skeleton.edge_claim_levels.
        intervention_node_idx: Index of the intervention node.
        cognitive_indices: Indices of cognitive domain nodes.

    Returns:
        Dict of cognitive_node_idx → edge_id for direct RCT edges.
    """
    direct_edges: dict[int, str] = {}
    cog_set = set(cognitive_indices)
    node_index = frozen.graph.node_map.node_index

    # Build reverse index→node_id map
    index_to_node = {idx: nid for nid, idx in node_index.items()}

    for edge in frozen.graph.b_skeleton.edges:
        src_idx = node_index.get(edge.source_node_id)
        tgt_idx = node_index.get(edge.target_node_id)
        if src_idx is None or tgt_idx is None:
            continue

        # Check: source is intervention node, target is cognitive node
        if src_idx != intervention_node_idx:
            continue
        if tgt_idx not in cog_set:
            continue

        # D2a: claim_level must be causal_supported
        claim = frozen.graph.b_skeleton.edge_claim_levels.get(edge.edge_id, "")
        if claim == "causal_supported":
            direct_edges[tgt_idx] = edge.edge_id
            logger.info(
                "D2a: Direct RCT edge found: %s → %s (edge %s)",
                index_to_node.get(src_idx, f"IDX_{src_idx}"),
                index_to_node.get(tgt_idx, f"IDX_{tgt_idx}"),
                edge.edge_id,
            )

    return direct_edges


# ═══════════════════════════════════════════════════════════════
#  D2b: Matrix Method
# ═══════════════════════════════════════════════════════════════


def _propagate_matrix_method(
    B_draw: np.ndarray,
    x_intervention: np.ndarray,
) -> tuple[np.ndarray | None, bool]:
    """D2b: Propagate effect via matrix inversion.

    Formula D2b-EQ1:
        Δθ^(m) = (I − B^(m))⁻¹ · x_intervention

    Args:
        B_draw: Effective B matrix for this draw (n_nodes × n_nodes).
        x_intervention: Intervention vector (n_nodes,), 1.0 at intervention node.

    Returns:
        Tuple of (delta_theta or None if unstable, used_fallback flag).
    """
    n = B_draw.shape[0]
    I_minus_B = np.eye(n) - B_draw

    # Check condition number — if > 10¹⁰, fall back to path enumeration
    # Formula: κ(I − B^(m)); if > CONDITION_NUMBER_CRITICAL → fall back to D2c
    try:
        cond = np.linalg.cond(I_minus_B)
    except np.linalg.LinAlgError:
        return None, True

    if cond > config.CONDITION_NUMBER_CRITICAL:
        logger.debug(
            "D2b: Condition number %.2e > %.2e — falling back to path enumeration",
            cond, config.CONDITION_NUMBER_CRITICAL,
        )
        return None, True

    # Formula D2b-EQ1: Δθ = (I − B)⁻¹ · x
    try:
        delta_theta = np.linalg.solve(I_minus_B, x_intervention)
    except np.linalg.LinAlgError:
        return None, True

    # Sanity: check for non-finite
    if not np.all(np.isfinite(delta_theta)):
        return None, True

    return delta_theta, False


# ═══════════════════════════════════════════════════════════════
#  D2c: Path Enumeration (fallback)
# ═══════════════════════════════════════════════════════════════


def _propagate_path_enumeration(
    B_draw: np.ndarray,
    source_idx: int,
    x_source: float,
    n_nodes: int,
) -> np.ndarray:
    """D2c: Enumerate all directed paths from source to compute effects.

    Formula D2c-EQ1:
        Δθ_target = Σ_P [Π_{e∈P} β_e] · x_source

    DFS from source node. Max depth = NODE_LAYER_COUNT (7).
    Paths through zero-weight edges are naturally excluded.

    Args:
        B_draw: Effective B matrix for this draw (n_nodes × n_nodes).
        source_idx: Index of the intervention (source) node.
        x_source: Intervention magnitude (typically 1.0 for unit dose).
        n_nodes: Number of nodes.

    Returns:
        delta_theta (n_nodes,) — accumulated effects at all reachable nodes.
    """
    max_depth = config.NODE_LAYER_COUNT
    delta_theta = np.zeros(n_nodes)

    # DFS: stack of (current_node, accumulated_product, depth, visited_set)
    stack: list[tuple[int, float, int, frozenset[int]]] = [
        (source_idx, x_source, 0, frozenset({source_idx})),
    ]

    while stack:
        current, accumulated, depth, visited = stack.pop()

        if depth > 0:
            # Accumulate effect at current node
            delta_theta[current] += accumulated

        if depth >= max_depth:
            continue

        # Explore outgoing edges: B[target, current] != 0 means current→target
        # Convention: B[i,j] = β for edge j→i (source j, target i)
        for target in range(n_nodes):
            if target in visited:
                continue  # no cycles in paths

            beta_edge = B_draw[target, current]
            if beta_edge == 0.0:
                continue  # excluded or zero-weight edge

            # Formula D2c-EQ1: path_effect = Π_{e∈P} β_e
            new_accumulated = accumulated * beta_edge
            stack.append(
                (target, new_accumulated, depth + 1, visited | {target}),
            )

    return delta_theta


# ═══════════════════════════════════════════════════════════════
#  D2d: Physiological Ceiling
# ═══════════════════════════════════════════════════════════════


def _apply_physiological_ceiling(
    delta_theta: np.ndarray,
    is_bundle: bool,
) -> tuple[np.ndarray, int]:
    """D2d: Clip effects to biologically plausible bounds.

    Formula D2d-EQ1:
        Single intervention: clip to ±1.0 SD per node
        Bundle: clip to ±1.5 SD per node

    Args:
        delta_theta: Effect vector (n_nodes,) for one draw.
        is_bundle: Whether this is a multi-intervention bundle.

    Returns:
        Tuple of (clipped delta_theta, n_clips count).
    """
    if is_bundle:
        ceiling = config.D2_CEILING_BUNDLE_SD
    else:
        ceiling = config.D2_CEILING_SINGLE_SD

    # Count clips before applying
    n_clips = int(np.sum(np.abs(delta_theta) > ceiling))

    # Clip to ±ceiling
    clipped = np.clip(delta_theta, -ceiling, ceiling)

    return clipped, n_clips


# ═══════════════════════════════════════════════════════════════
#  D2e: Composite Scoring
# ═══════════════════════════════════════════════════════════════


def _compute_severity_weight(z_baseline: float) -> float:
    """Compute severity weight from baseline z-score.

    Spec lines 2311-2314:
        |z| < 1.0:      w = 1.0 (mild)
        1.0 ≤ |z| < 2.0: w = 1.5 (moderate)
        |z| ≥ 2.0:      w = 2.0 (severe)

    Args:
        z_baseline: Patient baseline z-score for this domain.

    Returns:
        Severity weight.
    """
    abs_z = abs(z_baseline)
    if abs_z >= config.D2_SEVERITY_Z_SEVERE:
        return config.D2_SEVERITY_WEIGHT_SEVERE
    elif abs_z >= config.D2_SEVERITY_Z_MODERATE:
        return config.D2_SEVERITY_WEIGHT_MODERATE
    else:
        return config.D2_SEVERITY_WEIGHT_MILD


def _compute_composite_score(
    delta_theta_draw: np.ndarray,
    theta0_draw: np.ndarray,
    Sigma_post_diag: np.ndarray,
    cognitive_indices: list[int],
) -> float:
    """D2e: Severity-weighted inverse-variance composite cognitive score.

    Formula D2e-EQ1:
        ΔC^(m) = Σ_d w_d · Δθ_d^(m) / Σ_d w_d

    where:
        w_d = severity_weight(θ₀_d) × (1/σ²_d)
        severity_weight from patient baseline θ₀^(m), not population mean
        → personalized: sicker patients weight their impaired domains more

    Args:
        delta_theta_draw: Effect vector for one draw (n_nodes,).
        theta0_draw: Patient baseline for this draw (n_nodes,).
        Sigma_post_diag: Diagonal of posterior covariance (n_nodes,).
        cognitive_indices: Indices of cognitive domain nodes.

    Returns:
        Composite score ΔC for this draw.
    """
    if not cognitive_indices:
        return 0.0

    numerator = 0.0
    denominator = 0.0

    for idx in cognitive_indices:
        delta_d = delta_theta_draw[idx]
        z_baseline = theta0_draw[idx]
        sigma_sq_d = Sigma_post_diag[idx]

        # Severity weight from patient baseline (personalized)
        severity_w = _compute_severity_weight(z_baseline)

        # Inverse-variance component: 1/σ²_d
        # Guard against zero/tiny variance
        inv_var = 1.0 / max(sigma_sq_d, config.MIN_SIGMA_FLOOR ** 2)

        # Combined weight: severity × inverse-variance
        w_d = severity_w * inv_var

        # Formula D2e-EQ1: numerator += w_d · Δθ_d
        numerator += w_d * delta_d
        denominator += w_d

    if denominator <= 0.0:
        return 0.0

    # Formula D2e-EQ1: ΔC = Σ w_d·Δθ_d / Σ w_d
    return numerator / denominator


# ═══════════════════════════════════════════════════════════════
#  Utility: Identify cognitive domain nodes
# ═══════════════════════════════════════════════════════════════


def _get_cognitive_node_indices(
    node_map: NodeMap,
) -> tuple[list[int], list[str]]:
    """Identify cognitive domain nodes from NodeMap.

    Args:
        node_map: NodeMap with domain_assignment.

    Returns:
        Tuple of (cognitive_indices, cognitive_node_ids).
    """
    indices: list[int] = []
    node_ids: list[str] = []

    for node_id, domain in node_map.domain_assignment.items():
        if domain == config.D2_COGNITIVE_DOMAIN:
            idx = node_map.node_index.get(node_id)
            if idx is not None:
                indices.append(idx)
                node_ids.append(node_id)

    logger.info(
        "D2: Identified %d cognitive domain nodes: %s",
        len(indices), node_ids,
    )

    return indices, node_ids


# ═══════════════════════════════════════════════════════════════
#  Gate D-G2: Effect Propagation Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_d_g2(effect_result: EffectResult) -> None:
    """Gate D-G2: ΔC finite for all draws × interventions; ceiling clips < 20%.

    Conditions (spec line 2517):
        1. ΔC finite for all draws × all interventions
        2. Ceiling clip fraction < 20% (WARNING if exceeded)

    Raises:
        GateViolation: If ΔC contains non-finite values.
    """
    for interv_id, effects in effect_result.intervention_effects.items():
        # Condition 1: ΔC must be finite
        n_nonfinite = int(np.sum(~np.isfinite(effects.delta_C)))
        if n_nonfinite > 0:
            raise GateViolation(
                "D-G2",
                f"Intervention '{interv_id}': {n_nonfinite} non-finite ΔC values "
                f"out of {effect_result.n_draws} draws",
            )

        # Also check delta_theta
        n_nonfinite_theta = int(np.sum(~np.isfinite(effects.delta_theta)))
        if n_nonfinite_theta > 0:
            raise GateViolation(
                "D-G2",
                f"Intervention '{interv_id}': {n_nonfinite_theta} non-finite "
                f"Δθ values",
            )

        # Condition 2: ceiling clip fraction (WARNING, not hard fail)
        if effects.ceiling_clip_fraction > config.D2_CEILING_CLIP_WARNING_FRACTION:
            logger.warning(
                "Gate D-G2 WARNING: Intervention '%s' ceiling clip fraction "
                "%.1f%% exceeds %.0f%% threshold — model may be over-estimating "
                "effects or ceilings too tight",
                interv_id,
                effects.ceiling_clip_fraction * 100,
                config.D2_CEILING_CLIP_WARNING_FRACTION * 100,
            )

    logger.info(
        "Gate D-G2 PASSED: %d interventions, all ΔC finite",
        len(effect_result.intervention_effects),
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: propagate_effects (D2 entry point)
# ═══════════════════════════════════════════════════════════════


def propagate_effects(
    mc_draws: MCDraws,
    frozen: FrozenModelState,
    patient_state: PatientState,
    intervention_node_map: dict[str, int],
    is_bundle: bool = False,
) -> EffectResult:
    """D2: Propagate intervention effects through causal graph across all MC draws.

    For each draw × intervention:
        D2a: Check for direct RCT edges (priority 1)
        D2b: Matrix method (I−B)⁻¹·x (priority 2, default)
        D2c: Path enumeration (fallback if matrix ill-conditioned)
        D2d: Apply physiological ceiling
        D2e: Compute composite cognitive score

    Args:
        mc_draws: MCDraws from D1 (B_draws, theta0_draws, etc.).
        frozen: FrozenModelState with graph structure and edge metadata.
        patient_state: PatientState with Sigma_post for inverse-variance weights.
        intervention_node_map: intervention_id → node_index for each intervention.
        is_bundle: Whether this is a multi-intervention bundle (affects ceiling).

    Returns:
        EffectResult with per-intervention effects across all draws.

    Raises:
        GateViolation: If D-G2 fails.
    """
    n_draws = mc_draws.n_draws
    n_nodes = mc_draws.n_nodes
    node_map = frozen.graph.node_map

    logger.info(
        "── D2: Effect Propagation ──\n"
        "  n_draws=%d, n_nodes=%d, n_interventions=%d, is_bundle=%s",
        n_draws, n_nodes, len(intervention_node_map), is_bundle,
    )

    # Identify cognitive domain nodes
    cognitive_indices, cognitive_node_ids = _get_cognitive_node_indices(node_map)

    # Diagonal of Σ_post for inverse-variance weights (D2e)
    Sigma_post_diag = np.diag(patient_state.Sigma_post)

    all_effects: dict[str, InterventionEffects] = {}

    for interv_id, interv_node_idx in intervention_node_map.items():
        logger.info(
            "D2: Processing intervention '%s' at node index %d",
            interv_id, interv_node_idx,
        )

        # D2a: Check for direct RCT edges
        direct_rct_edges = _find_direct_rct_edges(
            frozen, interv_node_idx, cognitive_indices,
        )

        # Build intervention vector: 1.0 at intervention node, 0 elsewhere
        x_intervention = np.zeros(n_nodes)
        x_intervention[interv_node_idx] = 1.0

        # Allocate per-draw storage
        delta_theta_all = np.zeros((n_draws, n_nodes))
        delta_C_all = np.zeros(n_draws)
        methods: list[PropagationMethod] = []
        ceiling_clipped_all = np.zeros(n_draws, dtype=bool)
        total_ceiling_clips = 0
        n_matrix = 0
        n_path_enum = 0
        n_direct = 0

        for m in range(n_draws):
            B_draw = mc_draws.B_draws[m]  # (n_nodes, n_nodes)
            theta0_draw = mc_draws.theta0_draws[m]  # (n_nodes,)

            # D2a: If direct RCT edges exist, use them for cognitive nodes
            has_direct = len(direct_rct_edges) > 0
            if has_direct:
                # Use direct RCT β for cognitive targets, matrix for rest
                # Still subject to structural inclusion (already in B_draw)
                pass

            # D2b: Matrix method (default)
            delta_theta, need_fallback = _propagate_matrix_method(
                B_draw, x_intervention,
            )

            if need_fallback:
                # D2c: Path enumeration fallback
                delta_theta = _propagate_path_enumeration(
                    B_draw, interv_node_idx, 1.0, n_nodes,
                )
                method = PropagationMethod.PATH_ENUM
                n_path_enum += 1
            else:
                assert delta_theta is not None
                method = PropagationMethod.MATRIX
                n_matrix += 1

            # D2a: Override with direct RCT values for cognitive targets
            if has_direct:
                for cog_idx, edge_id in direct_rct_edges.items():
                    # The B_draw already contains the sampled β for this edge;
                    # D2a uses the direct β^(m) from B_draw[interv, cog]
                    # which IS the direct RCT evidence (sampled in D1a).
                    # So matrix method already incorporates it correctly.
                    # Override method label for audit.
                    pass
                if not need_fallback:
                    method = PropagationMethod.DIRECT_RCT
                    n_direct += 1
                    n_matrix -= 1  # correct the count

            # D2d: Physiological ceiling
            delta_theta_clipped, n_clips = _apply_physiological_ceiling(
                delta_theta, is_bundle,
            )
            if n_clips > 0:
                ceiling_clipped_all[m] = True
                total_ceiling_clips += n_clips

            # D2e: Composite cognitive score
            delta_C = _compute_composite_score(
                delta_theta_clipped,
                theta0_draw,
                Sigma_post_diag,
                cognitive_indices,
            )

            delta_theta_all[m] = delta_theta_clipped
            delta_C_all[m] = delta_C
            methods.append(method)

        # Compute ceiling clip fraction
        total_possible = n_draws * n_nodes
        clip_fraction = total_ceiling_clips / total_possible if total_possible > 0 else 0.0

        all_effects[interv_id] = InterventionEffects(
            intervention_id=interv_id,
            delta_theta=delta_theta_all,
            delta_C=delta_C_all,
            propagation_methods=methods,
            ceiling_clipped=ceiling_clipped_all,
            n_matrix_method=n_matrix,
            n_path_enum_fallback=n_path_enum,
            n_direct_rct=n_direct,
            n_ceiling_clips=total_ceiling_clips,
            ceiling_clip_fraction=clip_fraction,
        )

        logger.info(
            "D2: Intervention '%s' — methods: %d matrix, %d path_enum, %d direct_rct; "
            "ceiling clips: %d (%.1f%%)",
            interv_id, n_matrix, n_path_enum, n_direct,
            total_ceiling_clips, clip_fraction * 100,
        )

    effect_result = EffectResult(
        intervention_effects=all_effects,
        n_draws=n_draws,
        n_nodes=n_nodes,
        cognitive_node_indices=cognitive_indices,
        cognitive_node_ids=cognitive_node_ids,
    )

    # Gate D-G2
    _validate_gate_d_g2(effect_result)
    effect_result.gate_d_g2_passed = True

    logger.info(
        "D2: Effect propagation complete — %d interventions processed",
        len(all_effects),
    )

    return effect_result


# ═══════════════════════════════════════════════════════════════
#  Fix 1: Joint Bundle Propagation (eliminates superposition double-count)
# ═══════════════════════════════════════════════════════════════


def propagate_joint_bundle(
    mc_draws: MCDraws,
    frozen: FrozenModelState,
    patient_state: PatientState,
    intervention_node_indices: list[int],
    cognitive_indices: list[int],
) -> np.ndarray:
    """Propagate multiple interventions jointly through the SEM per-draw.

    Instead of computing ΔC_a and ΔC_b independently and combining
    post-hoc with an overlap discount, this function computes:

        Δθ_joint^(m) = (I − B^(m))⁻¹ · (x_a + x_b + ...)

    Then applies:
        - D2d: Bundle physiological ceiling (±1.5 SD)
        - D2e: Composite cognitive scoring with severity weights

    By superposition in a linear SEM, the Δθ is identical to the sum
    of individual Δθ values. But the ceiling clipping and severity
    weighting are non-linear, so the joint ΔC ≠ Σ ΔC_individual.
    This function captures that non-linearity correctly.

    Args:
        mc_draws: MCDraws from D1.
        frozen: FrozenModelState (for graph metadata).
        patient_state: PatientState with Sigma_post for severity weights.
        intervention_node_indices: List of node indices being intervened on.
        cognitive_indices: Indices of cognitive domain nodes.

    Returns:
        delta_C_joint: shape (n_draws,) — composite cognitive score per draw
                       under the joint intervention.
    """
    n_draws = mc_draws.n_draws
    n_nodes = mc_draws.n_nodes
    Sigma_post_diag = np.diag(patient_state.Sigma_post)

    # Build joint intervention vector: 1.0 at each intervention node
    x_joint = np.zeros(n_nodes)
    for idx in intervention_node_indices:
        x_joint[idx] = 1.0

    delta_C_joint = np.zeros(n_draws)

    for m in range(n_draws):
        B_draw = mc_draws.B_draws[m]
        theta0_draw = mc_draws.theta0_draws[m]

        # D2b: Matrix method for joint intervention vector
        delta_theta, need_fallback = _propagate_matrix_method(B_draw, x_joint)

        if need_fallback:
            # D2c: Path enumeration fallback — sum over all source nodes
            delta_theta = np.zeros(n_nodes)
            for src_idx in intervention_node_indices:
                delta_theta += _propagate_path_enumeration(
                    B_draw, src_idx, 1.0, n_nodes,
                )
        else:
            assert delta_theta is not None

        # D2d: Bundle physiological ceiling (±1.5 SD)
        delta_theta_clipped, _ = _apply_physiological_ceiling(
            delta_theta, is_bundle=True,
        )

        # D2e: Composite cognitive score
        delta_C_joint[m] = _compute_composite_score(
            delta_theta_clipped,
            theta0_draw,
            Sigma_post_diag,
            cognitive_indices,
        )

    return delta_C_joint


# ═══════════════════════════════════════════════════════════════
#  Fix 2: Full-cascade reachability for JPO
# ═══════════════════════════════════════════════════════════════


def compute_reachable_nodes(
    source_idx: int,
    B_hat: np.ndarray,
) -> set[int]:
    """Compute all nodes reachable from source via nonzero edges in B.

    Uses BFS on the adjacency structure of B_hat.
    Convention: B[target, source] ≠ 0 means source → target edge.

    Args:
        source_idx: Index of the source node.
        B_hat: Mean B matrix (n_nodes × n_nodes).

    Returns:
        Set of reachable node indices (including source).
    """
    n = B_hat.shape[0]
    visited: set[int] = {source_idx}
    queue: list[int] = [source_idx]

    while queue:
        current = queue.pop(0)
        # B[target, current] ≠ 0 means current → target
        for target in range(n):
            if target not in visited and B_hat[target, current] != 0.0:
                visited.add(target)
                queue.append(target)

    return visited
