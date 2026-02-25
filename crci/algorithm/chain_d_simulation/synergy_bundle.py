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
from dataclasses import dataclass, field

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from .effect_propagation import EffectResult
from .intervention_loader import InterventionSet
from .safety_checker import SafetyResult, SafetyStatus

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PairwiseMetrics:
    """Pairwise synergy metrics for one (a, b) pair."""

    action_a: str
    action_b: str
    jpo: float       # Jaccard Pathway Overlap [0, 1]
    ccs: float       # Complementary Convergence Score [0, 1]


@dataclass(frozen=True)
class BundleEffects:
    """Per-draw bundle effects for one candidate bundle."""

    bundle_id: str
    member_ids: tuple[str, ...]
    delta_C_bundle: np.ndarray  # shape (n_draws,) — composite cognitive effect per draw
    mean_delta_C: float
    sd_delta_C: float
    n_draws: int


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
) -> set[str]:
    """Get the set of pathways an intervention acts on.

    Uses dose_bridges to identify which nodes/pathways are targeted.
    Falls back to empty set if no bridges defined.

    Args:
        action_id: Intervention action ID.
        intervention_set: Complete InterventionSet.

    Returns:
        Set of pathway identifiers.
    """
    idx = intervention_set.intervention_index.get(action_id)
    if idx is None:
        return set()

    interv = intervention_set.interventions[idx]
    pathways: set[str] = set()

    for bridge in interv.dose_bridges:
        if bridge.output_node_id:
            pathways.add(bridge.output_node_id)
        if bridge.maps_to_node_id:
            pathways.add(bridge.maps_to_node_id)

    return pathways


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
    gamma_draws: np.ndarray,
    n_draws: int,
) -> np.ndarray:
    """D3c: Compute bundle effect for all draws.

    Formula D3c-EQ1:
        ΔC_bundle = Σ_a ΔC_a · Π_{b≠a}(1 − JPO(a,b)·0.5)
                  + Σ_{(a,b)} γ · CCS(a,b) · √|ΔC_a·ΔC_b|

    Term 1: Discounted additive (overlap penalty)
    Term 2: Synergy bonus (complementary convergence)

    Args:
        member_ids: Tuple of action_ids in the bundle.
        delta_C_per_interv: action_id → ΔC array (n_draws,).
        pairwise: (a_id, b_id) → PairwiseMetrics.
        gamma_draws: Sampled γ values (n_draws,).
        n_draws: Number of MC draws.

    Returns:
        ΔC_bundle array (n_draws,).
    """
    delta_C_bundle = np.zeros(n_draws)

    # Term 1: Discounted additive
    for a_id in member_ids:
        delta_C_a = delta_C_per_interv[a_id]

        # Compute overlap discount product: Π_{b≠a}(1 − JPO(a,b) × penalty_factor)
        discount = np.ones(n_draws)
        for b_id in member_ids:
            if b_id == a_id:
                continue
            key = (min(a_id, b_id), max(a_id, b_id))
            metrics = pairwise.get(key)
            jpo = metrics.jpo if metrics else 0.0
            discount *= (1.0 - jpo * config.D3_JPO_OVERLAP_PENALTY_FACTOR)

        # Formula D3c-EQ1 term 1: ΔC_a · discount
        delta_C_bundle += delta_C_a * discount

    # Term 2: Synergy bonus for each pair
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

            # Formula D3c-EQ1 term 2: γ · CCS · √|ΔC_a · ΔC_b|
            geometric_mean = np.sqrt(np.abs(delta_C_a * delta_C_b))
            delta_C_bundle += gamma_draws * ccs * geometric_mean

    return delta_C_bundle


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
    gamma_draws: np.ndarray,
) -> None:
    """Gate D-G3: Bundle effects computed; γ samples in valid range.

    Conditions (spec line 2518):
        1. All bundle ΔC values are finite
        2. γ draws are in [0, γ_cap] range

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

    # Condition 2: γ in valid range [0, γ_cap]
    gamma_min = float(np.min(gamma_draws))
    gamma_max = float(np.max(gamma_draws))
    if gamma_min < 0:
        raise GateViolation(
            "D-G3",
            f"γ draws contain negative values: min={gamma_min:.4f}",
        )
    if gamma_max > config.SYNERGY_GAMMA_CAP_DEFAULT * 1.01:  # small tolerance
        raise GateViolation(
            "D-G3",
            f"γ draws exceed cap: max={gamma_max:.4f} > "
            f"{config.SYNERGY_GAMMA_CAP_DEFAULT}",
        )

    logger.info(
        "Gate D-G3 PASSED: %d bundles, all ΔC finite, γ ∈ [%.3f, %.3f]",
        len(bundle_result.bundle_effects), gamma_min, gamma_max,
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
) -> BundleResult:
    """D3-synergy: Compute pairwise synergy metrics and bundle effects.

    For each pair of non-blocked interventions:
        D3a: Compute JPO (Jaccard Pathway Overlap)
        D3b: Compute CCS (Complementary Convergence Score)
    For each candidate bundle (size 2-4):
        D3c: Compute ΔC_bundle per draw with overlap penalty + synergy bonus

    Args:
        effect_result: EffectResult from D2 with per-intervention delta_C.
        intervention_set: InterventionSet from D0 with pathway info.
        safety_result: SafetyResult from D3-safety (to exclude blocked interventions).
        n_draws: Number of MC draws (defaults to effect_result.n_draws).
        seed: Random seed for γ sampling.

    Returns:
        BundleResult with pairwise metrics and bundle effects.

    Raises:
        GateViolation: If D-G3 fails.
    """
    if n_draws is None:
        n_draws = effect_result.n_draws
    if seed is None:
        seed = config.MC_DEFAULT_SEED

    # Filter to non-blocked interventions that have effects
    eligible_ids = [
        aid for aid in effect_result.intervention_effects
        if aid not in safety_result.blocked_action_ids
    ]
    n_filtered = len(effect_result.intervention_effects) - len(eligible_ids)

    logger.info(
        "── D3-Synergy: Bundle Computation ──\n"
        "  n_eligible=%d, n_filtered_blocked=%d, n_draws=%d",
        len(eligible_ids), n_filtered, n_draws,
    )

    # Get pathway sets for each intervention
    pathway_sets: dict[str, set[str]] = {}
    for aid in eligible_ids:
        pathway_sets[aid] = _get_intervention_pathways(aid, intervention_set)

    # Get mean delta_theta for CCS computation
    mean_delta_theta: dict[str, np.ndarray] = {}
    for aid in eligible_ids:
        mean_delta_theta[aid] = np.mean(
            effect_result.intervention_effects[aid].delta_theta, axis=0,
        )

    # D3a + D3b: Compute pairwise metrics
    pairwise: dict[tuple[str, str], PairwiseMetrics] = {}
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

            pairwise[key] = PairwiseMetrics(
                action_a=a_id, action_b=b_id, jpo=jpo, ccs=ccs,
            )

    logger.info(
        "D3a/b: %d pairwise metrics computed",
        len(pairwise),
    )

    # D3c: Sample γ ~ Beta(α, β) × γ_cap
    # Formula D3c-EQ2: γ ~ Beta(2,4) × 0.40
    rng = np.random.default_rng(seed)
    gamma_draws = rng.beta(
        config.D3_GAMMA_BETA_ALPHA,
        config.D3_GAMMA_BETA_BETA,
        size=n_draws,
    ) * config.SYNERGY_GAMMA_CAP_DEFAULT

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

    # Compute bundle effects
    bundle_effects: dict[str, BundleEffects] = {}
    for combo in candidates:
        bundle_id = "+".join(sorted(combo))

        delta_C_bundle = _compute_bundle_effect_per_draw(
            combo, delta_C_per_interv, pairwise, gamma_draws, n_draws,
        )

        bundle_effects[bundle_id] = BundleEffects(
            bundle_id=bundle_id,
            member_ids=combo,
            delta_C_bundle=delta_C_bundle,
            mean_delta_C=float(np.mean(delta_C_bundle)),
            sd_delta_C=float(np.std(delta_C_bundle)),
            n_draws=n_draws,
        )

    result = BundleResult(
        pairwise_metrics=pairwise,
        bundle_effects=bundle_effects,
        n_bundles_evaluated=len(bundle_effects),
        n_candidates_filtered=n_filtered,
    )

    # Gate D-G3
    _validate_gate_d_g3(result, gamma_draws)
    result.gate_d_g3_passed = True

    logger.info(
        "D3-Synergy complete: %d pairwise, %d bundles",
        len(pairwise), len(bundle_effects),
    )

    return result
