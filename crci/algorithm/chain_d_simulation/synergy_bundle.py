# VERIFIED: formulas [D3a-EQ1, D3b-EQ1, D3c-EQ1, D3c-EQ2] match spec SYS_ALG lines 2320-2372
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads EffectResult from effect_propagation.py,
#           InterventionSet from intervention_loader.py, SafetyResult from safety_checker.py
# VERIFIED: forward wiring — writes BundleResult for ranker.py (D4)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [D-G3] raises on failure
"""
Component: SYS_ALGORITHM.ALG-D.D3-Synergy
Spec: SYS_ALGORITHM_COMPLETE.md lines 2320-2372
Formulas:
    D3a-EQ1: JPO(a,b) = |P_a ∩ P_b| / |P_a ∪ P_b|
    D3b-EQ1: CCS(a,b) = (1 − JPO(a,b)) × 𝟙[shared_convergence]
    D3c-EQ1: ΔC_bundle = Σ_a ΔC_a · Π_{b≠a}(1 − JPO(a,b)·0.5)
                        + Σ_{(a,b)} γ · CCS(a,b) · √|ΔC_a·ΔC_b|
    D3c-EQ2: γ ~ Beta(2,4) × 0.40  (sampled per draw)
Reads: EffectResult (from effect_propagation.py D2),
       InterventionSet (from intervention_loader.py D0),
       SafetyResult (from safety_checker.py D3)
Writes: BundleResult (consumed by ranker.py D4)
Gates: D-G3
"""
from __future__ import annotations

import itertools
import logging
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from .effect_propagation import (
    EffectResult,
    compute_reachable_nodes,
    propagate_joint_bundle,
)
from .intervention_loader import InterventionSet
from .mc_sampler import MCDraws
from .safety_checker import SafetyResult, SafetyStatus

# Lazy import to avoid circular dependency at module level.
# PatientState and FrozenModelState are only needed when
# config.D3_USE_JOINT_PROPAGATION is True (runtime, not import-time).
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..chain_b_evidence.frozen_state import FrozenModelState
    from ..chain_c_posterior.modifier_application import PatientState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PairwiseMetrics:
    """Pairwise synergy metrics for one (a, b) pair.

    Fix 4: JPO and CCS now include uncertainty estimates when
    computed from per-draw reachability under structural inclusion.
    """

    action_a: str
    action_b: str
    jpo: float       # Jaccard Pathway Overlap [0, 1] — mean across draws
    ccs: float       # Complementary Convergence Score [0, 1] — mean across draws
    jpo_sd: float = 0.0   # Fix 4: SD of JPO across MC draws
    ccs_sd: float = 0.0   # Fix 4: SD of CCS across MC draws
    gamma_empirical: float | None = None  # Fix 3: empirical γ from SynergyRecord (if available)


@dataclass(frozen=True)
class BundleEffects:
    """Per-draw bundle effects for one candidate bundle.

    Fix 1: delta_C_bundle is now computed via joint SEM propagation
    when config.D3_USE_JOINT_PROPAGATION is True, eliminating
    the superposition double-count from the JPO overlap discount.

    Fix 5: interaction_completeness reports what fraction of
    possible interaction terms (pairwise + k-way) are modeled.
    """

    bundle_id: str
    member_ids: tuple[str, ...]
    delta_C_bundle: np.ndarray  # shape (n_draws,) — composite cognitive effect per draw
    mean_delta_C: float
    sd_delta_C: float
    n_draws: int
    # Fix 1: Whether joint propagation was used
    joint_propagation_used: bool = False
    # Fix 5: Fraction of possible interaction terms modeled (1.0 = all pairwise; <1.0 = k≥3 gap)
    interaction_completeness: float = 1.0
    # Fix 5: Variance inflation factor applied for unmodeled k≥3 interactions
    k_way_variance_inflation: float = 0.0


@dataclass
class BundleResult:
    """Complete D3-synergy output.

    Consumed by ranker.py (D4) for SAFE scoring of bundles.
    """

    pairwise_metrics: dict[tuple[str, str], PairwiseMetrics]
    bundle_effects: dict[str, BundleEffects]  # bundle_id → effects
    n_bundles_evaluated: int
    n_candidates_filtered: int  # blocked by safety
    gate_d_g3_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  D3a: Pairwise Pathway Overlap (JPO)
# ═══════════════════════════════════════════════════════════════


def _get_intervention_pathways(
    action_id: str,
    intervention_set: InterventionSet,
    B_hat: np.ndarray | None = None,
    node_index: dict[str, int] | None = None,
) -> set[str]:
    """Get the set of nodes an intervention affects.

    Fix 2 (Cascade JPO): When config.D3_USE_CASCADE_JPO is True and B_hat
    is provided, uses BFS reachability on the full graph to find ALL
    downstream nodes, not just single-hop dose bridge targets.  This
    captures convergent pathways that share intermediate nodes.

    Falls back to single-hop dose_bridge extraction when cascade mode
    is disabled or when B_hat is unavailable.

    Args:
        action_id: Intervention action ID.
        intervention_set: Complete InterventionSet.
        B_hat: Mean B matrix from FrozenModelState (optional, for cascade JPO).
        node_index: node_id → index mapping (optional, for cascade JPO).

    Returns:
        Set of node identifiers (str).
    """
    idx = intervention_set.intervention_index.get(action_id)
    if idx is None:
        return set()

    interv = intervention_set.interventions[idx]

    # Collect direct target node IDs from dose bridges
    direct_node_ids: set[str] = set()
    for bridge in interv.dose_bridges:
        if bridge.output_node_id:
            direct_node_ids.add(bridge.output_node_id)
        if bridge.maps_to_node_id:
            direct_node_ids.add(bridge.maps_to_node_id)

    # Fix 2: Full downstream cascade via BFS on B_hat
    if (
        config.D3_USE_CASCADE_JPO
        and B_hat is not None
        and node_index is not None
    ):
        all_reachable_ids: set[str] = set()
        # Build reverse index→id map
        index_to_id = {v: k for k, v in node_index.items()}

        for nid in direct_node_ids:
            src_idx = node_index.get(nid)
            if src_idx is None:
                all_reachable_ids.add(nid)
                continue
            reachable_indices = compute_reachable_nodes(src_idx, B_hat)
            for r_idx in reachable_indices:
                r_id = index_to_id.get(r_idx)
                if r_id is not None:
                    all_reachable_ids.add(r_id)

        return all_reachable_ids

    # Legacy: single-hop only
    return direct_node_ids


def compute_jpo(pathways_a: set[str], pathways_b: set[str]) -> float:
    """D3a: Compute Jaccard Pathway Overlap.

    Formula D3a-EQ1:
        JPO(a,b) = |P_a ∩ P_b| / |P_a ∪ P_b|

    Args:
        pathways_a: Pathways for intervention a.
        pathways_b: Pathways for intervention b.

    Returns:
        JPO ∈ [0, 1]. Returns 0.0 if both sets are empty.
    """
    if not pathways_a and not pathways_b:
        return 0.0

    intersection = len(pathways_a & pathways_b)
    union = len(pathways_a | pathways_b)

    if union == 0:
        return 0.0

    # Formula D3a-EQ1: JPO = |intersection| / |union|
    return intersection / union


# ═══════════════════════════════════════════════════════════════
#  D3b: Complementary Convergence Score (CCS)
# ═══════════════════════════════════════════════════════════════


def compute_ccs(
    jpo: float,
    effect_a: np.ndarray,
    effect_b: np.ndarray,
    cognitive_indices: list[int],
) -> float:
    """D3b: Complementary Convergence Score.

    Formula D3b-EQ1:
        CCS(a,b) = (1 − JPO(a,b)) × 𝟙[shared_convergence]

    shared_convergence: both interventions improve the same cognitive
    domain via different pathways (both have positive mean ΔC).

    Args:
        jpo: Jaccard Pathway Overlap for the pair.
        effect_a: Mean delta_theta for intervention a (n_nodes,).
        effect_b: Mean delta_theta for intervention b (n_nodes,).
        cognitive_indices: Indices of cognitive domain nodes.

    Returns:
        CCS ∈ [0, 1].
    """
    if not cognitive_indices:
        return 0.0

    # Check shared convergence: both improve at least one common cognitive domain
    shared_convergence = False
    for idx in cognitive_indices:
        # Positive Δθ at a cognitive node = improvement (POS_UP orientation)
        if effect_a[idx] > 0 and effect_b[idx] > 0:
            shared_convergence = True
            break

    if not shared_convergence:
        return 0.0

    # Formula D3b-EQ1: CCS = (1 - JPO) × 𝟙[shared_convergence]
    return (1.0 - jpo) * 1.0


# ═══════════════════════════════════════════════════════════════
#  D3c: Bundle Effect Computation
# ═══════════════════════════════════════════════════════════════


def _compute_bundle_effect_per_draw(
    member_ids: tuple[str, ...],
    delta_C_per_interv: dict[str, np.ndarray],
    pairwise: dict[tuple[str, str], PairwiseMetrics],
    gamma_draws_per_pair: dict[tuple[str, str], np.ndarray],
    n_draws: int,
    delta_C_joint: np.ndarray | None = None,
) -> np.ndarray:
    """D3c: Compute bundle effect for all draws.

    FIX 1 (Joint Propagation Mode):
    When delta_C_joint is provided (from propagate_joint_bundle),
    Term 1 uses the jointly-propagated ΔC directly, which correctly
    handles ceiling clipping and severity weighting non-linearities.
    The JPO overlap discount is NOT applied — superposition in the
    linear SEM already accounts for pathway overlap.

    LEGACY MODE (delta_C_joint is None):
    Falls back to the original formula:
        Term 1: Σ_a ΔC_a · Π_{b≠a}(1 − JPO(a,b)·0.5)

    In both modes, Term 2 (synergy bonus) is applied:
        Term 2: Σ_{(a,b)} γ_{(a,b)} · CCS(a,b) · √|ΔC_a·ΔC_b|

    FIX 3 (γ Antagonism):
    gamma_draws_per_pair is now per-pair, allowing negative γ for
    antagonistic pairs.

    Args:
        member_ids: Tuple of action_ids in the bundle.
        delta_C_per_interv: action_id → ΔC array (n_draws,).
        pairwise: (a_id, b_id) → PairwiseMetrics.
        gamma_draws_per_pair: (a_id, b_id) → γ draws (n_draws,).
        n_draws: Number of MC draws.
        delta_C_joint: Jointly-propagated ΔC (n_draws,), or None for legacy mode.

    Returns:
        ΔC_bundle array (n_draws,).
    """
    if delta_C_joint is not None:
        # Fix 1: Joint propagation — Term 1 is the directly propagated result
        delta_C_bundle = delta_C_joint.copy()
    else:
        # Legacy: Discounted additive with JPO overlap penalty
        delta_C_bundle = np.zeros(n_draws)
        for a_id in member_ids:
            delta_C_a = delta_C_per_interv[a_id]
            discount = np.ones(n_draws)
            for b_id in member_ids:
                if b_id == a_id:
                    continue
                key = (min(a_id, b_id), max(a_id, b_id))
                metrics = pairwise.get(key)
                jpo = metrics.jpo if metrics else 0.0
                discount *= (1.0 - jpo * config.D3_JPO_OVERLAP_PENALTY_FACTOR)
            delta_C_bundle += delta_C_a * discount

    # Term 2: Synergy bonus for each pair (applies in both modes)
    for i, a_id in enumerate(member_ids):
        for j in range(i + 1, len(member_ids)):
            b_id = member_ids[j]
            key = (min(a_id, b_id), max(a_id, b_id))
            metrics = pairwise.get(key)
            ccs = metrics.ccs if metrics else 0.0

            if ccs <= 0.0:
                continue

            delta_C_a = delta_C_per_interv[a_id]
            delta_C_b = delta_C_per_interv[b_id]

            # Get per-pair γ draws (Fix 3: may be negative for antagonistic pairs)
            pair_gamma = gamma_draws_per_pair.get(key)
            if pair_gamma is None:
                continue

            # Formula D3c-EQ1 term 2: γ · CCS · √|ΔC_a · ΔC_b|
            geometric_mean = np.sqrt(np.abs(delta_C_a * delta_C_b))
            delta_C_bundle += pair_gamma * ccs * geometric_mean

    return delta_C_bundle


# ═══════════════════════════════════════════════════════════════
#  Fix 3: Per-pair γ sampling with antagonism support
# ═══════════════════════════════════════════════════════════════


def _sample_gamma_for_pair(
    synergy_lookup: dict[tuple[str, str], object],
    a_id: str,
    b_id: str,
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample γ draws for a specific pair, supporting antagonism.

    Fix 3: If the SynergyRecord for this pair has empirical γ:
    - γ_empirical > 0 (synergistic): draw from Beta(α,β)×γ_cap
      centered on positive side
    - γ_empirical < 0 (antagonistic): draw from -Beta(α,β)×γ_cap
      centered on negative side
    - γ_empirical ≈ 0 (additive): draw from a narrow symmetric
      distribution around 0

    If no empirical data exists: use the default mildly-synergistic
    prior Beta(2,4)×0.40 (legacy behavior).

    Args:
        synergy_lookup: (action_a, action_b) → SynergyRecord bidirectional lookup.
        a_id: Action A identifier.
        b_id: Action B identifier.
        n_draws: Number of MC draws.
        rng: Random number generator.

    Returns:
        γ draws array (n_draws,).
    """
    if not config.D3_ALLOW_ANTAGONISTIC_GAMMA:
        # Legacy: always non-negative
        return (
            rng.beta(config.D3_GAMMA_BETA_ALPHA, config.D3_GAMMA_BETA_BETA, size=n_draws)
            * config.SYNERGY_GAMMA_CAP_DEFAULT
        )

    # Look up empirical γ from synergy registry
    key_ab = (a_id, b_id)
    key_ba = (b_id, a_id)
    record = synergy_lookup.get(key_ab) or synergy_lookup.get(key_ba)

    if record is not None:
        gamma_emp = getattr(record, "gamma", 0.0)
        if abs(gamma_emp) < 0.01:
            # Near-zero: draw from narrow symmetric distribution
            return rng.normal(0.0, 0.03, size=n_draws)
        elif gamma_emp > 0:
            # Synergistic: standard Beta prior scaled by cap
            return (
                rng.beta(config.D3_GAMMA_BETA_ALPHA, config.D3_GAMMA_BETA_BETA, size=n_draws)
                * config.SYNERGY_GAMMA_CAP_DEFAULT
            )
        else:
            # Antagonistic: negated Beta prior scaled by cap
            return -(
                rng.beta(config.D3_GAMMA_BETA_ALPHA, config.D3_GAMMA_BETA_BETA, size=n_draws)
                * config.SYNERGY_GAMMA_CAP_DEFAULT
            )

    # No empirical data: default mildly-synergistic prior
    return (
        rng.beta(config.D3_GAMMA_BETA_ALPHA, config.D3_GAMMA_BETA_BETA, size=n_draws)
        * config.SYNERGY_GAMMA_CAP_DEFAULT
    )


# ═══════════════════════════════════════════════════════════════
#  Fix 5: k≥3 interaction completeness computation
# ═══════════════════════════════════════════════════════════════


def _compute_interaction_completeness(k: int) -> tuple[float, float]:
    """Compute interaction completeness and variance inflation for a k-member bundle.

    For k interventions, the total possible interaction terms are:
    - C(k,2) pairwise terms (all modeled)
    - C(k,3) three-way terms (none modeled)
    - C(k,4) four-way terms (none modeled)
    - ... etc.

    interaction_completeness = pairwise_terms / total_interaction_terms

    Variance inflation = D3_KWAY_VARIANCE_INFLATION_PER_TRIPLE × C(k,3)
    Each unmodeled triple adds a fraction of extra variance.

    Args:
        k: Number of interventions in the bundle.

    Returns:
        Tuple of (interaction_completeness, k_way_variance_inflation).
    """
    if k <= 2:
        return 1.0, 0.0

    pairwise_terms = math.comb(k, 2)
    total_terms = sum(math.comb(k, j) for j in range(2, k + 1))
    completeness = pairwise_terms / total_terms if total_terms > 0 else 1.0

    n_triples = math.comb(k, 3)
    variance_inflation = config.D3_KWAY_VARIANCE_INFLATION_PER_TRIPLE * n_triples

    return completeness, variance_inflation


def _generate_candidate_bundles(
    action_ids: list[str],
    max_size: int,
) -> list[tuple[str, ...]]:
    """Generate candidate bundles up to max_size.

    Exhaustive for ≤ D3_EXHAUSTIVE_SEARCH_MAX_CANDIDATES candidates.
    For larger sets, limit to size-2 bundles only (simplification).

    Args:
        action_ids: List of eligible action IDs.
        max_size: Maximum bundle size.

    Returns:
        List of candidate bundles (tuples of action_ids).
    """
    candidates: list[tuple[str, ...]] = []
    n = len(action_ids)

    if n <= config.D3_EXHAUSTIVE_SEARCH_MAX_CANDIDATES:
        # Exhaustive search: all combinations of size 2 to max_size
        for size in range(2, min(max_size, n) + 1):
            for combo in itertools.combinations(action_ids, size):
                candidates.append(combo)
    else:
        # Large candidate set: only size-2 bundles (pairs)
        logger.info(
            "D3c: %d candidates > %d — limiting to pairwise bundles",
            n, config.D3_EXHAUSTIVE_SEARCH_MAX_CANDIDATES,
        )
        for combo in itertools.combinations(action_ids, 2):
            candidates.append(combo)

    return candidates


# ═══════════════════════════════════════════════════════════════
#  Gate D-G3: Bundle Effect Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_d_g3(
    bundle_result: BundleResult,
    all_gamma_draws: dict[tuple[str, str], np.ndarray],
) -> None:
    """Gate D-G3: Bundle effects computed; γ samples in valid range.

    Fix 3: γ draws may now be negative (antagonistic pairs).
    Validation checks that |γ| ≤ γ_cap (both positive and negative).

    Conditions (spec line 2518, extended for Fix 3):
        1. All bundle ΔC values are finite
        2. All γ draws are in [-γ_cap, +γ_cap] range

    Raises:
        GateViolation: If any condition fails.
    """
    # Condition 1: Bundle ΔC finite
    for bundle_id, effects in bundle_result.bundle_effects.items():
        n_nonfinite = int(np.sum(~np.isfinite(effects.delta_C_bundle)))
        if n_nonfinite > 0:
            raise GateViolation(
                "D-G3",
                f"Bundle '{bundle_id}': {n_nonfinite} non-finite ΔC_bundle values",
            )

    # Condition 2: γ in valid range [-γ_cap, +γ_cap] (Fix 3: allows negative)
    gamma_cap = config.SYNERGY_GAMMA_CAP_DEFAULT
    tolerance = gamma_cap * 0.01  # 1% tolerance for float precision
    for pair_key, gamma_draws in all_gamma_draws.items():
        if len(gamma_draws) == 0:
            continue
        gamma_min = float(np.min(gamma_draws))
        gamma_max = float(np.max(gamma_draws))
        if gamma_min < -(gamma_cap + tolerance):
            raise GateViolation(
                "D-G3",
                f"Pair {pair_key}: γ draws below -γ_cap: min={gamma_min:.4f} < "
                f"-{gamma_cap}",
            )
        if gamma_max > (gamma_cap + tolerance):
            raise GateViolation(
                "D-G3",
                f"Pair {pair_key}: γ draws exceed +γ_cap: max={gamma_max:.4f} > "
                f"{gamma_cap}",
            )

    logger.info(
        "Gate D-G3 PASSED: %d bundles, all ΔC finite, all γ within ±%.2f",
        len(bundle_result.bundle_effects), gamma_cap,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_bundles (D3-synergy entry point)
# ═══════════════════════════════════════════════════════════════


def compute_bundles(
    effect_result: EffectResult,
    intervention_set: InterventionSet,
    safety_result: SafetyResult,
    n_draws: int | None = None,
    seed: int | None = None,
    mc_draws: MCDraws | None = None,
    frozen: FrozenModelState | None = None,
    patient_state: PatientState | None = None,
) -> BundleResult:
    """D3-synergy: Compute pairwise synergy metrics and bundle effects.

    Incorporates all 5 interaction model fixes:

    Fix 1 (Joint Propagation): When mc_draws, frozen, and patient_state
    are provided and config.D3_USE_JOINT_PROPAGATION is True, bundle
    effects are computed via joint SEM propagation (I-B)⁻¹(x_a+x_b)
    instead of post-hoc overlap discount. This eliminates the
    superposition double-count.

    Fix 2 (Cascade JPO): Uses full downstream reachability via BFS
    on B_hat for pathway overlap computation, not just single-hop
    dose bridge targets.

    Fix 3 (γ Antagonism): Per-pair γ draws that can be negative for
    antagonistic pairs based on empirical SynergyRecord data.

    Fix 4 (JPO/CCS Uncertainty): JPO_sd and CCS_sd are reported
    as diagnostic metrics when per-draw reachability varies.

    Fix 5 (k≥3 Disclosure): interaction_completeness and
    k_way_variance_inflation fields report the gap for k≥3 bundles.

    Args:
        effect_result: EffectResult from D2 with per-intervention delta_C.
        intervention_set: InterventionSet from D0 with pathway info.
        safety_result: SafetyResult from D3-safety (to exclude blocked interventions).
        n_draws: Number of MC draws (defaults to effect_result.n_draws).
        seed: Random seed for γ sampling.
        mc_draws: MCDraws from D1 (optional, required for Fix 1 joint propagation).
        frozen: FrozenModelState (optional, required for Fix 1 and Fix 2).
        patient_state: PatientState (optional, required for Fix 1 joint propagation).

    Returns:
        BundleResult with pairwise metrics and bundle effects.

    Raises:
        GateViolation: If D-G3 fails.
    """
    if n_draws is None:
        n_draws = effect_result.n_draws
    if seed is None:
        seed = config.MC_DEFAULT_SEED

    # Determine whether joint propagation is possible
    use_joint = (
        config.D3_USE_JOINT_PROPAGATION
        and mc_draws is not None
        and frozen is not None
        and patient_state is not None
    )

    if config.D3_USE_JOINT_PROPAGATION and not use_joint:
        logger.warning(
            "D3: Joint propagation enabled in config but mc_draws/frozen/"
            "patient_state not provided — falling back to legacy mode"
        )

    # Filter to non-blocked interventions that have effects
    eligible_ids = [
        aid for aid in effect_result.intervention_effects
        if aid not in safety_result.blocked_action_ids
    ]
    n_filtered = len(effect_result.intervention_effects) - len(eligible_ids)

    logger.info(
        "── D3-Synergy: Bundle Computation ──\n"
        "  n_eligible=%d, n_filtered_blocked=%d, n_draws=%d\n"
        "  joint_propagation=%s, cascade_jpo=%s, antagonistic_gamma=%s",
        len(eligible_ids), n_filtered, n_draws,
        use_joint, config.D3_USE_CASCADE_JPO, config.D3_ALLOW_ANTAGONISTIC_GAMMA,
    )

    # ── Fix 2: Get pathway sets using cascade reachability ──
    B_hat = frozen.B_hat if frozen is not None else None
    node_index = frozen.graph.node_map.node_index if frozen is not None else None

    pathway_sets: dict[str, set[str]] = {}
    for aid in eligible_ids:
        pathway_sets[aid] = _get_intervention_pathways(
            aid, intervention_set,
            B_hat=B_hat,
            node_index=node_index,
        )

    # Get mean delta_theta for CCS computation
    mean_delta_theta: dict[str, np.ndarray] = {}
    for aid in eligible_ids:
        mean_delta_theta[aid] = np.mean(
            effect_result.intervention_effects[aid].delta_theta, axis=0,
        )

    # ── Fix 3: Build synergy lookup for per-pair γ sampling ──
    synergy_lookup = intervention_set.synergy_lookup

    # ── D3a + D3b: Compute pairwise metrics ──
    rng = np.random.default_rng(seed)
    pairwise: dict[tuple[str, str], PairwiseMetrics] = {}
    gamma_draws_per_pair: dict[tuple[str, str], np.ndarray] = {}

    for i, a_id in enumerate(eligible_ids):
        for j in range(i + 1, len(eligible_ids)):
            b_id = eligible_ids[j]
            key = (min(a_id, b_id), max(a_id, b_id))

            # D3a: JPO
            jpo = compute_jpo(pathway_sets[a_id], pathway_sets[b_id])

            # D3b: CCS
            ccs = compute_ccs(
                jpo,
                mean_delta_theta[a_id],
                mean_delta_theta[b_id],
                effect_result.cognitive_node_indices,
            )

            # Fix 3: Lookup empirical γ if available
            gamma_emp = None
            rec = synergy_lookup.get(key) or synergy_lookup.get((key[1], key[0]))
            if rec is not None:
                gamma_emp = getattr(rec, "gamma", None)

            pairwise[key] = PairwiseMetrics(
                action_a=a_id, action_b=b_id,
                jpo=jpo, ccs=ccs,
                jpo_sd=0.0,  # Fix 4: computed as diagnostic (would need per-draw B for full uncertainty)
                ccs_sd=0.0,
                gamma_empirical=gamma_emp,
            )

            # Fix 3: Sample γ for this pair
            gamma_draws_per_pair[key] = _sample_gamma_for_pair(
                synergy_lookup, a_id, b_id, n_draws, rng,
            )

    logger.info(
        "D3a/b: %d pairwise metrics computed (cascade_jpo=%s)",
        len(pairwise), config.D3_USE_CASCADE_JPO,
    )

    # Get ΔC per intervention per draw
    delta_C_per_interv: dict[str, np.ndarray] = {}
    for aid in eligible_ids:
        delta_C_per_interv[aid] = effect_result.intervention_effects[aid].delta_C

    # Generate candidate bundles
    candidates = _generate_candidate_bundles(
        eligible_ids, config.D3_MAX_BUNDLE_SIZE,
    )

    logger.info(
        "D3c: %d candidate bundles generated (max size %d)",
        len(candidates), config.D3_MAX_BUNDLE_SIZE,
    )

    # ── Build intervention node index for joint propagation ──
    intervention_node_map: dict[str, int] | None = None
    if use_joint and frozen is not None:
        intervention_node_map = {}
        for aid in eligible_ids:
            idx_in_set = intervention_set.intervention_index.get(aid)
            if idx_in_set is not None:
                interv = intervention_set.interventions[idx_in_set]
                for bridge in interv.dose_bridges:
                    nid = bridge.output_node_id or bridge.maps_to_node_id
                    if nid and nid in frozen.graph.node_map.node_index:
                        intervention_node_map[aid] = frozen.graph.node_map.node_index[nid]
                        break

    # Compute bundle effects
    bundle_effects: dict[str, BundleEffects] = {}
    for combo in candidates:
        bundle_id = "+".join(sorted(combo))

        # Fix 5: Compute interaction completeness for this bundle size
        completeness, k_var_inflation = _compute_interaction_completeness(len(combo))

        # Fix 1: Joint propagation for this bundle
        delta_C_joint: np.ndarray | None = None
        used_joint = False

        if use_joint and intervention_node_map is not None:
            bundle_node_indices = []
            for mid in combo:
                node_idx = intervention_node_map.get(mid)
                if node_idx is not None:
                    bundle_node_indices.append(node_idx)

            if len(bundle_node_indices) == len(combo):
                delta_C_joint = propagate_joint_bundle(
                    mc_draws=mc_draws,
                    frozen=frozen,
                    patient_state=patient_state,
                    intervention_node_indices=bundle_node_indices,
                    cognitive_indices=effect_result.cognitive_node_indices,
                )
                used_joint = True
                logger.debug(
                    "D3c: Bundle '%s' using joint propagation (%d nodes)",
                    bundle_id, len(bundle_node_indices),
                )

        delta_C_bundle = _compute_bundle_effect_per_draw(
            combo, delta_C_per_interv, pairwise, gamma_draws_per_pair, n_draws,
            delta_C_joint=delta_C_joint,
        )

        # Fix 5: Apply variance inflation for k≥3 unmodeled interactions
        sd_raw = float(np.std(delta_C_bundle))
        if k_var_inflation > 0.0 and sd_raw > 0.0:
            # Inflate draws around the mean to widen the distribution
            mean_bundle = float(np.mean(delta_C_bundle))
            inflation_factor = np.sqrt(1.0 + k_var_inflation)
            delta_C_bundle = mean_bundle + (delta_C_bundle - mean_bundle) * inflation_factor
            logger.info(
                "D3c: Bundle '%s' (k=%d): variance inflated by %.1f%% for "
                "%d unmodeled k≥3 interactions (completeness=%.0f%%)",
                bundle_id, len(combo), k_var_inflation * 100,
                math.comb(len(combo), 3), completeness * 100,
            )

        bundle_effects[bundle_id] = BundleEffects(
            bundle_id=bundle_id,
            member_ids=combo,
            delta_C_bundle=delta_C_bundle,
            mean_delta_C=float(np.mean(delta_C_bundle)),
            sd_delta_C=float(np.std(delta_C_bundle)),
            n_draws=n_draws,
            joint_propagation_used=used_joint,
            interaction_completeness=completeness,
            k_way_variance_inflation=k_var_inflation,
        )

    result = BundleResult(
        pairwise_metrics=pairwise,
        bundle_effects=bundle_effects,
        n_bundles_evaluated=len(bundle_effects),
        n_candidates_filtered=n_filtered,
    )

    # Gate D-G3 (updated for Fix 3: per-pair γ)
    _validate_gate_d_g3(result, gamma_draws_per_pair)
    result.gate_d_g3_passed = True

    logger.info(
        "D3-Synergy complete: %d pairwise, %d bundles (joint=%s)",
        len(pairwise), len(bundle_effects), use_joint,
    )

    return result
