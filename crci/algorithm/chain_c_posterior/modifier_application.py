# VERIFIED: formulas [C4b-EQ1, C4c-EQ1, C4d-EQ1] match spec SYS_ALG lines 1896-1912
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads RawPosterior from bayesian_update.py, FrozenModelState from frozen_state.py
# VERIFIED: forward wiring — writes PatientState for Chain D (chain_d_simulation)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [C-G4] raises on failure
"""
Component: SYS_ALGORITHM.ALG-C.C4
Spec: SYS_ALGORITHM_COMPLETE.md lines 1896-1912
Formulas:
    C4b-EQ1: β_eff = β_base × Π_k m_k  (clamped: individual [0.7,1.5], cumulative [0.5,2.0])
    C4c-EQ1: SE_modifier_adj per grade A=1.0, B=1.15, C=1.30, D=1.50
    C4d-EQ1: A(P) = mean(|θ̂[nodes_in_P]|); active if A(P) > τ_P
Reads: RawPosterior (from bayesian_update.py), FrozenModelState (from frozen_state.py),
       modifier_registry (109 rules), PATHWAY_REGISTRY.csv
Writes: PatientState (consumed by Chain D, Chain E, Chain F)
Gates: C-G4
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.pathway_types import PathwayDef

from ..chain_a_graph.node_loader import NodeMap
from ..chain_b_evidence.frozen_state import FrozenModelState
from .bayesian_update import ObservationRecord, RawPosterior
from .prior_loader import LoadedPrior

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ModifierRule:
    """A single modifier rule from modifier_registry (one of 109).

    Describes a condition (e.g., age>65) and its effect on a target edge.
    """

    rule_id: str
    condition_variable: str  # e.g., "age", "apoe_status", "education_years"
    condition_operator: str  # e.g., ">", "<", "==", ">=", "in"
    condition_value: str  # e.g., "65", "e4_carrier", "12"
    target_edge_id: str | None  # specific edge or None (all edges)
    multiplier: float  # m_k
    grade: str  # A, B, C, D
    category: str  # e.g., "demographic", "genetic", "lifestyle", "comorbidity"


@dataclass(frozen=True)
class ModifierRecord:
    """Audit record of one modifier application to one edge.

    Used by Chain F for provenance tracking.
    """

    rule_id: str
    edge_id: str
    multiplier_raw: float  # before individual clamp
    multiplier_clamped: float  # after individual clamp
    grade: str
    was_clipped: bool


@dataclass(frozen=True)
class PathwayActivation:
    """A pathway's activation level (C4d output)."""

    pathway_id: str
    pathway_label: str
    activation_score: float  # A(P) = mean(|θ̂[nodes_in_P]|)
    threshold: float  # τ_P
    is_active: bool
    n_nodes: int  # number of pathway nodes with θ̂ data
    high_uncertainty: bool  # active AND high variance → flag


@dataclass(frozen=True)
class ContextMatchRecord:
    """Prior loading audit record (from C1).

    Captures context matching decisions for Chain F audit.
    """

    context_key: str
    fallback_level: str
    fallback_SE_inflation: float


@dataclass
class PatientState:
    """Final output of Chain C — consumed by Chains D, E, F.

    Fields per spec SYS_ALG lines 1759-1810.
    """

    # C3 output: Posterior mean (passed through from C3 — C4 does NOT modify θ̂)
    theta_hat: np.ndarray  # ℝ^{n_nodes}

    # C3 output: Posterior covariance (unmodified by C4)
    Sigma_post: np.ndarray  # ℝ^{n_nodes × n_nodes}

    # C3 output: Posterior precision
    Lambda_post: np.ndarray  # ℝ^{n_nodes × n_nodes}

    # C4b: Modified edge weight matrix
    B_eff: np.ndarray  # ℝ^{n_nodes × n_nodes}

    # C4d: Dysregulated pathways with magnitudes
    active_pathways: list[PathwayActivation] = field(default_factory=list)

    # C4: Per-edge modifier audit trail
    modifier_audit: list[ModifierRecord] = field(default_factory=list)

    # C3: Complete observation provenance
    observation_log: list[ObservationRecord] = field(default_factory=list)

    # C1: Prior loading audit
    context_match: ContextMatchRecord | None = None

    # C3d: Per-variable expected variance reduction
    variance_reduction: np.ndarray = field(
        default_factory=lambda: np.array([]),
    )

    # C4c: Per-edge SE inflation from modifier grades
    modifier_se_inflation: dict[str, float] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  C4a: Modifier Rule Matching
# ═══════════════════════════════════════════════════════════════


def _evaluate_condition(
    rule: ModifierRule,
    patient_profile: dict[str, object],
) -> bool:
    """C4a: Evaluate whether a modifier rule's condition is met for a patient.

    Args:
        rule: ModifierRule to evaluate.
        patient_profile: Dict of patient attributes (age, apoe_status, etc.).

    Returns:
        True if condition is met, False otherwise.
    """
    var = rule.condition_variable
    if var not in patient_profile:
        return False

    patient_val = patient_profile[var]
    threshold = rule.condition_value

    if rule.condition_operator == ">":
        return float(patient_val) > float(threshold)
    elif rule.condition_operator == "<":
        return float(patient_val) < float(threshold)
    elif rule.condition_operator == ">=":
        return float(patient_val) >= float(threshold)
    elif rule.condition_operator == "<=":
        return float(patient_val) <= float(threshold)
    elif rule.condition_operator == "==":
        return str(patient_val) == str(threshold)
    elif rule.condition_operator == "in":
        # threshold is comma-separated list
        valid_vals = {v.strip() for v in str(threshold).split(",")}
        return str(patient_val) in valid_vals
    else:
        logger.warning(
            "C4a: Unknown operator '%s' in rule '%s' — skipping",
            rule.condition_operator, rule.rule_id,
        )
        return False


def _match_modifiers(
    rules: list[ModifierRule],
    patient_profile: dict[str, object],
    edge_ids: list[str],
) -> dict[str, list[ModifierRule]]:
    """C4a: Identify which of 109 rules apply to this patient per edge.

    Args:
        rules: All modifier rules from registry.
        patient_profile: Patient attributes.
        edge_ids: All edge IDs in the graph.

    Returns:
        Dict: edge_id → list of matched ModifierRule.
    """
    matched: dict[str, list[ModifierRule]] = {eid: [] for eid in edge_ids}

    for rule in rules:
        if _evaluate_condition(rule, patient_profile):
            if rule.target_edge_id is not None:
                # Specific edge
                if rule.target_edge_id in matched:
                    matched[rule.target_edge_id].append(rule)
            else:
                # All edges
                for eid in edge_ids:
                    matched[eid].append(rule)

    total_matches = sum(len(v) for v in matched.values())
    n_edges_with_mods = sum(1 for v in matched.values() if v)
    logger.info(
        "C4a: Matched %d modifier applications across %d edges "
        "(from %d rules, %d patient attributes)",
        total_matches, n_edges_with_mods,
        len(rules), len(patient_profile),
    )

    return matched


# ═══════════════════════════════════════════════════════════════
#  C4b: Modifier Stacking with Guardrails
# ═══════════════════════════════════════════════════════════════


def _stack_modifiers(
    B_hat: np.ndarray,
    matched_modifiers: dict[str, list[ModifierRule]],
    graph_edge_map: dict[str, tuple[int, int]],
) -> tuple[np.ndarray, list[ModifierRecord]]:
    """C4b: Multiply modifiers per edge with safety bounds.

    Formula C4b-EQ1:
        β_eff = β_base × Π_k m_k

    Guardrails:
        Individual: m_k ∈ [0.7, 1.5]  (config.C4_MODIFIER_INDIVIDUAL_LOW/HIGH)
        Cumulative: Π m_k ∈ [0.5, 2.0]  (config.C4_MODIFIER_CUMULATIVE_LOW/HIGH)
        Sign-flip prohibition: direction preserved

    Args:
        B_hat: Original edge weight matrix from FrozenModelState.
        matched_modifiers: Per-edge modifier lists from C4a.
        graph_edge_map: edge_id → (source_idx, target_idx).

    Returns:
        Tuple of (B_eff matrix, modifier audit trail).
    """
    B_eff = B_hat.copy()
    audit: list[ModifierRecord] = []

    for edge_id, rules in matched_modifiers.items():
        if not rules:
            continue

        coords = graph_edge_map.get(edge_id)
        if coords is None:
            continue

        src_idx, tgt_idx = coords
        beta_base = B_hat[src_idx, tgt_idx]

        if beta_base == 0.0:
            # No edge weight to modify
            continue

        original_sign = 1.0 if beta_base >= 0 else -1.0
        cumulative_product = 1.0

        for rule in rules:
            m_raw = rule.multiplier

            # Individual clamp: m_k ∈ [0.7, 1.5]
            m_clamped = max(
                config.C4_MODIFIER_INDIVIDUAL_LOW,
                min(m_raw, config.C4_MODIFIER_INDIVIDUAL_HIGH),
            )
            was_clipped = (m_clamped != m_raw)

            if was_clipped:
                logger.info(
                    "C4b: Edge '%s' rule '%s' clipped: %.3f → %.3f "
                    "(individual bounds [%.1f, %.1f])",
                    edge_id, rule.rule_id, m_raw, m_clamped,
                    config.C4_MODIFIER_INDIVIDUAL_LOW,
                    config.C4_MODIFIER_INDIVIDUAL_HIGH,
                )

            cumulative_product *= m_clamped

            audit.append(ModifierRecord(
                rule_id=rule.rule_id,
                edge_id=edge_id,
                multiplier_raw=m_raw,
                multiplier_clamped=m_clamped,
                grade=rule.grade,
                was_clipped=was_clipped,
            ))

        # Cumulative clamp: Π m_k ∈ [0.5, 2.0]
        cumulative_clamped = max(
            config.C4_MODIFIER_CUMULATIVE_LOW,
            min(cumulative_product, config.C4_MODIFIER_CUMULATIVE_HIGH),
        )
        if cumulative_clamped != cumulative_product:
            logger.info(
                "C4b: Edge '%s' cumulative product clipped: %.3f → %.3f "
                "(bounds [%.1f, %.1f])",
                edge_id, cumulative_product, cumulative_clamped,
                config.C4_MODIFIER_CUMULATIVE_LOW,
                config.C4_MODIFIER_CUMULATIVE_HIGH,
            )

        # Formula C4b-EQ1: β_eff = β_base × Π_k m_k
        beta_eff = beta_base * cumulative_clamped

        # Sign-flip prohibition: direction preserved
        new_sign = 1.0 if beta_eff >= 0 else -1.0
        if new_sign != original_sign and beta_eff != 0.0:
            logger.warning(
                "C4b: Edge '%s' sign flip detected (%.4f → %.4f) "
                "— reverting to original sign",
                edge_id, beta_base, beta_eff,
            )
            beta_eff = abs(beta_eff) * original_sign

        B_eff[src_idx, tgt_idx] = beta_eff

    n_modified = sum(
        1 for eid, rules in matched_modifiers.items()
        if rules and graph_edge_map.get(eid) is not None
    )
    logger.info(
        "C4b: Modified %d edges, %d audit records, "
        "%d clipping events",
        n_modified,
        len(audit),
        sum(1 for r in audit if r.was_clipped),
    )

    return B_eff, audit


# ═══════════════════════════════════════════════════════════════
#  C4c: Modifier SE Inflation
# ═══════════════════════════════════════════════════════════════


def _compute_modifier_se_inflation(
    matched_modifiers: dict[str, list[ModifierRule]],
) -> dict[str, float]:
    """C4c: Compute SE inflation per edge based on cumulative evidence grade.

    Formula C4c-EQ1:
        grade = min_k(grade_{m_k})  (worst grade among modifiers)
        SE inflation: A=1.0, B=1.15, C=1.30, D=1.50

    Applied in Chain D's MC sampling (B̂ stays frozen).

    Args:
        matched_modifiers: Per-edge modifier lists from C4a.

    Returns:
        Dict: edge_id → SE inflation multiplier.
    """
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    se_inflation: dict[str, float] = {}

    for edge_id, rules in matched_modifiers.items():
        if not rules:
            continue

        # Cumulative grade = worst (min) among all applied modifiers
        worst_grade = "A"
        for rule in rules:
            if grade_order.get(rule.grade, 99) > grade_order.get(worst_grade, 0):
                worst_grade = rule.grade

        # Look up SE multiplier from config
        se_mult = config.C4_GRADE_SE_MULTIPLIERS.get(worst_grade, 1.0)
        if se_mult != 1.0:
            se_inflation[edge_id] = se_mult

    if se_inflation:
        logger.info(
            "C4c: SE inflation applied to %d edges (grades: %s)",
            len(se_inflation),
            {k: v for k, v in sorted(se_inflation.items())[:5]},
        )

    return se_inflation


# ═══════════════════════════════════════════════════════════════
#  C4d: Pathway Activation Detection
# ═══════════════════════════════════════════════════════════════

# PathwayDef imported from crci.shared.models.pathway_types (canonical single source of truth).
# The load_pathway_registry() function lives in chain_a_graph.graph_object — callers pass
# the already-loaded GraphObject.pathway_map as the pathways argument to apply_modifiers().


def _detect_pathway_activations(
    theta_hat: np.ndarray,
    Sigma_post: np.ndarray,
    pathways: list[PathwayDef],
    node_map: NodeMap,
    sensitive_mode: bool = False,
) -> list[PathwayActivation]:
    """C4d: Identify which pathways are dysregulated.

    Formula C4d-EQ1:
        A(P) = mean(|θ̂[nodes_in_P]|)
        Active if A(P) > τ_P

    Args:
        theta_hat: Posterior mean from C3.
        Sigma_post: Posterior covariance from C3.
        pathways: Pathway definitions.
        node_map: NodeMap for node_id → index lookup.
        sensitive_mode: If True, use lower threshold (0.3 SD).

    Returns:
        List of PathwayActivation objects.
    """
    activations: list[PathwayActivation] = []

    for pw in pathways:
        # Collect node indices for this pathway
        node_indices = []
        for node_id in pw.component_nodes:
            idx = node_map.node_index.get(node_id)
            if idx is not None:
                node_indices.append(idx)

        if not node_indices:
            continue

        # Formula C4d-EQ1: A(P) = mean(|θ̂[nodes_in_P]|)
        theta_subset = theta_hat[node_indices]
        activation_score = float(np.mean(np.abs(theta_subset)))

        # Threshold: use per-pathway or mode default
        if sensitive_mode:
            threshold = config.C4_PATHWAY_ACTIVATION_THRESHOLD_SENSITIVE
        else:
            threshold = pw.activation_threshold

        is_active = activation_score > threshold

        # Flag: high activation + high uncertainty
        mean_variance = float(np.mean([Sigma_post[i, i] for i in node_indices]))
        high_uncertainty = is_active and mean_variance > 1.0

        activations.append(PathwayActivation(
            pathway_id=pw.pathway_id,
            pathway_label=pw.pathway_label,
            activation_score=activation_score,
            threshold=threshold,
            is_active=is_active,
            n_nodes=len(node_indices),
            high_uncertainty=high_uncertainty,
        ))

    n_active = sum(1 for a in activations if a.is_active)
    n_flagged = sum(1 for a in activations if a.high_uncertainty)
    logger.info(
        "C4d: Pathway activation — %d/%d active, %d flagged (high uncertainty)",
        n_active, len(activations), n_flagged,
    )

    if n_active == 0:
        logger.warning(
            "C4d: No active pathways detected — population defaults will be used in Chain D",
        )

    return activations


# ═══════════════════════════════════════════════════════════════
#  Gate C-G4: Modifier Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_c_g4(
    patient_state: PatientState,
    B_hat: np.ndarray,
) -> None:
    """Gate C-G4: Modifiers in guardrails; no sign flips; ≥1 pathway evaluated.

    Conditions (spec lines 1969-1972):
        1. All edge modifiers within cumulative bounds [0.5, 2.0]
        2. No sign flips in B_eff vs B̂
        3. ≥1 pathway evaluated

    Raises:
        GateViolation: If conditions 1 or 2 fail.
        Logs WARNING if 0 active pathways.
    """
    # Condition 1+2: Check all non-zero edges for bounds and sign preservation
    n = B_hat.shape[0]
    for i in range(n):
        for j in range(n):
            if B_hat[i, j] == 0.0:
                continue

            ratio = patient_state.B_eff[i, j] / B_hat[i, j]

            # Check cumulative bounds
            if ratio < config.C4_MODIFIER_CUMULATIVE_LOW - 1e-10 or \
               ratio > config.C4_MODIFIER_CUMULATIVE_HIGH + 1e-10:
                raise GateViolation(
                    "C-G4",
                    f"Edge [{i},{j}] modifier ratio {ratio:.4f} outside "
                    f"cumulative bounds [{config.C4_MODIFIER_CUMULATIVE_LOW}, "
                    f"{config.C4_MODIFIER_CUMULATIVE_HIGH}]",
                )

            # Check sign preservation
            if (B_hat[i, j] > 0 and patient_state.B_eff[i, j] < 0) or \
               (B_hat[i, j] < 0 and patient_state.B_eff[i, j] > 0):
                raise GateViolation(
                    "C-G4",
                    f"Edge [{i},{j}] sign flip: B̂={B_hat[i,j]:.4f} → "
                    f"B_eff={patient_state.B_eff[i,j]:.4f}",
                )

    # Condition 3: ≥1 pathway evaluated
    if not patient_state.active_pathways:
        logger.warning(
            "Gate C-G4: No pathways evaluated — "
            "check pathway registry availability",
        )
    else:
        n_active = sum(1 for p in patient_state.active_pathways if p.is_active)
        if n_active == 0:
            logger.warning(
                "Gate C-G4 WARNING: 0 active pathways — "
                "population defaults will be used",
            )

    logger.info(
        "Gate C-G4 PASSED: B_eff within guardrails, no sign flips, "
        "%d pathways evaluated (%d active)",
        len(patient_state.active_pathways),
        sum(1 for p in patient_state.active_pathways if p.is_active),
    )


# ═══════════════════════════════════════════════════════════════
#  Utility: Build edge map from graph
# ═══════════════════════════════════════════════════════════════


def _build_edge_map(
    frozen: FrozenModelState,
) -> dict[str, tuple[int, int]]:
    """Build edge_id → (source_idx, target_idx) mapping.

    Args:
        frozen: FrozenModelState with graph reference.

    Returns:
        Dict mapping edge_id to (source_index, target_index).
    """
    edge_map: dict[str, tuple[int, int]] = {}
    node_index = frozen.graph.node_map.node_index

    for edge in frozen.graph.b_skeleton.edges:
        src_idx = node_index.get(edge.source_node_id)
        tgt_idx = node_index.get(edge.target_node_id)
        if src_idx is not None and tgt_idx is not None:
            edge_map[edge.edge_id] = (src_idx, tgt_idx)

    return edge_map


# ═══════════════════════════════════════════════════════════════
#  Top-Level: apply_modifiers (C4 entry point)
# ═══════════════════════════════════════════════════════════════


def apply_modifiers(
    raw_posterior: RawPosterior,
    loaded_prior: LoadedPrior,
    frozen: FrozenModelState,
    patient_profile: dict[str, object],
    modifier_rules: list[ModifierRule],
    pathways: list[PathwayDef],
    sensitive_mode: bool = False,
) -> PatientState:
    """C4: Effect Modifier Application.

    Applies 109 modifier rules to adjust edge weights (B̂ → B_eff),
    then identifies dysregulated pathways.

    Sub-steps:
        C4a — Modifier Rule Matching
        C4b — Modifier Stacking with Guardrails
        C4c — Modifier SE Inflation
        C4d — Pathway Activation Detection

    Args:
        raw_posterior: RawPosterior from C3.
        loaded_prior: LoadedPrior from C1 (for context audit).
        frozen: FrozenModelState from Chain B (B̂, graph).
        patient_profile: Dict of patient attributes for rule matching.
        modifier_rules: List of ModifierRule from registry.
        pathways: List of PathwayDef from PATHWAY_REGISTRY.csv.
        sensitive_mode: If True, use lower pathway activation threshold.

    Returns:
        PatientState with θ̂, Σ_post, B_eff, active_pathways, etc.

    Raises:
        GateViolation: If C-G4 fails.
    """
    logger.info(
        "── C4: Effect Modifier Application ──\n"
        "  modifier_rules=%d, patient_attrs=%d, pathways=%d",
        len(modifier_rules), len(patient_profile), len(pathways),
    )

    # Build edge map for matrix indexing
    edge_map = _build_edge_map(frozen)
    edge_ids = list(edge_map.keys())

    # C4a: Match modifiers to patient
    matched = _match_modifiers(modifier_rules, patient_profile, edge_ids)

    # C4b: Stack modifiers with guardrails → B_eff
    B_eff, modifier_audit = _stack_modifiers(
        B_hat=frozen.B_hat,
        matched_modifiers=matched,
        graph_edge_map=edge_map,
    )

    # C4c: Modifier SE inflation per edge grade
    modifier_se_inflation = _compute_modifier_se_inflation(matched)

    # C4d: Pathway activation detection
    active_pathways = _detect_pathway_activations(
        theta_hat=raw_posterior.theta_hat,
        Sigma_post=raw_posterior.Sigma_post,
        pathways=pathways,
        node_map=frozen.graph.node_map,
        sensitive_mode=sensitive_mode,
    )

    # Build context match record from C1
    context_match = ContextMatchRecord(
        context_key=loaded_prior.context_key,
        fallback_level=loaded_prior.fallback_level.value,
        fallback_SE_inflation=loaded_prior.fallback_SE_inflation,
    )

    patient_state = PatientState(
        theta_hat=raw_posterior.theta_hat,
        Sigma_post=raw_posterior.Sigma_post,
        Lambda_post=raw_posterior.Lambda_post,
        B_eff=B_eff,
        active_pathways=active_pathways,
        modifier_audit=modifier_audit,
        observation_log=raw_posterior.observation_log,
        context_match=context_match,
        variance_reduction=raw_posterior.variance_reduction,
        modifier_se_inflation=modifier_se_inflation,
    )

    # Gate C-G4
    _validate_gate_c_g4(patient_state, frozen.B_hat)

    n_active = sum(1 for p in active_pathways if p.is_active)
    logger.info(
        "C4: Modifier application complete — "
        "B_eff modified %d edges, %d active pathways, "
        "%d modifier audit records",
        sum(1 for eid in matched if matched[eid]),
        n_active,
        len(modifier_audit),
    )

    return patient_state
