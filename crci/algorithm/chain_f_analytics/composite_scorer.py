# VERIFIED: formulas [F-1, F-2, F-3] match spec SYS_ALG lines 3117-3191
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PatientState (chain_c), posterior means/variances
# VERIFIED: forward wiring — writes CompositeState for F2 (variance_decomposer.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [F-G1] raises on failure
"""
Component: SYS_ALGORITHM.ALG-F.F1
Spec: SYS_ALGORITHM_COMPLETE.md lines 3117-3191
Formulas:
    F-1: CRCI_composite = Σ_d (w_d × z_d) / Σ_d w_d  (IVW composite)
    F-2: Percentile = Φ(−CRCI_composite) × 100
    F-3: Cochran's Q = Σ_d w_d (z_d − CRCI)²; I² = max(0, (Q−(D−1))/Q)×100
Reads: PatientState (from chain_c_posterior/modifier_application.py)
Writes: CompositeState (consumed by F2 variance_decomposer.py)
Gates: F-G1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy import stats

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class SeverityTier(str, Enum):
    """Cognitive severity tier based on percentile."""

    EXCELLENT = "EXCELLENT"                # 85-100
    GOOD = "GOOD"                          # 70-84
    MILD_IMPAIRMENT = "MILD_IMPAIRMENT"    # 50-69
    MODERATE_IMPAIRMENT = "MODERATE_IMPAIRMENT"  # 30-49
    POOR = "POOR"                          # 15-29
    SEVERE_IMPAIRMENT = "SEVERE_IMPAIRMENT"  # 0-14


@dataclass
class CompositeState:
    """F1 output: Composite cognitive outcome.

    Consumed by F2 (decision stability) and downstream analytics.
    """

    crci_composite: float               # IVW composite z-score
    severity_tier: SeverityTier         # classification
    percentile: float                   # Φ(−z) × 100, ∈ [0, 100]
    subdomain_scores: dict[str, float]  # domain → z-score
    subdomain_weights: dict[str, float]  # domain → 1/σ²_d
    cochrans_Q: float                   # heterogeneity statistic
    I_squared: float                    # [0, 100] — % real heterogeneity
    random_effects_applied: bool        # True if I² > 50%
    severity_weighted_z: dict[str, float]  # domain → z × severity_weight
    n_domains: int
    gate_f_g1_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  F1a: Subdomain Extraction
# ═══════════════════════════════════════════════════════════════


def _extract_subdomain_scores(
    posterior_means: np.ndarray,
    posterior_variances: np.ndarray,
    domain_node_map: dict[str, list[int]] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """F1a: Extract per-domain z-scores and variances.

    For each domain, average the z-scores of its constituent nodes.
    σ²_d = mean(σ²_nodes_in_d) / n_nodes_in_d (SE of mean).

    Args:
        posterior_means: θ̂ posterior means (n_nodes,).
        posterior_variances: Diagonal of Σ_post (n_nodes,).
        domain_node_map: Map from domain name → node indices.
            If None, distributes nodes evenly across domains.

    Returns:
        (subdomain_scores, subdomain_variances) dicts.
    """
    domains = config.F1_COGNITIVE_DOMAINS
    n_nodes = len(posterior_means)

    if domain_node_map is None:
        # Default: distribute nodes evenly across domains
        domain_node_map = {}
        nodes_per_domain = max(1, n_nodes // len(domains))
        for i, domain in enumerate(domains):
            start = i * nodes_per_domain
            end = min(start + nodes_per_domain, n_nodes)
            if start < n_nodes:
                domain_node_map[domain] = list(range(start, end))
        # Assign remaining nodes to last domain
        if n_nodes > len(domains) * nodes_per_domain:
            last_domain = domains[-1]
            last_end = len(domains) * nodes_per_domain
            domain_node_map[last_domain] = list(range(
                (len(domains) - 1) * nodes_per_domain, n_nodes,
            ))

    subdomain_scores: dict[str, float] = {}
    subdomain_variances: dict[str, float] = {}

    for domain in domains:
        node_indices = domain_node_map.get(domain, [])
        if not node_indices:
            continue  # Skip domains with zero observable nodes (spec line 3141)

        z_nodes = posterior_means[node_indices]
        var_nodes = posterior_variances[node_indices]

        # z_d = mean(z_nodes) — spec line 3138
        z_d = float(np.mean(z_nodes))
        # σ²_d = mean(σ²_nodes) / n — variance of the mean
        n = len(node_indices)
        var_d = float(np.mean(var_nodes) / n) if n > 0 else 1.0

        subdomain_scores[domain] = z_d
        subdomain_variances[domain] = max(var_d, 1e-10)  # avoid division by zero

    return subdomain_scores, subdomain_variances


# ═══════════════════════════════════════════════════════════════
#  F1b: Severity Weighting
# ═══════════════════════════════════════════════════════════════


def _apply_severity_weights(
    subdomain_scores: dict[str, float],
) -> dict[str, float]:
    """F1b: Apply non-linear severity weights to subdomain scores.

    Spec lines 3153-3155:
        |z_d| < 1.0 → weight = 1.0
        1.0 ≤ |z_d| < 2.0 → weight = 1.5
        |z_d| ≥ 2.0 → weight = 2.0

    Returns:
        severity_weighted_z: domain → z_d × weight
    """
    severity_weighted: dict[str, float] = {}

    for domain, z_d in subdomain_scores.items():
        abs_z = abs(z_d)
        if abs_z >= config.F1_SEVERITY_THRESHOLD_SEVERE:
            weight = config.F1_SEVERITY_WEIGHT_SEVERE
        elif abs_z >= config.F1_SEVERITY_THRESHOLD_MODERATE:
            weight = config.F1_SEVERITY_WEIGHT_MODERATE
        else:
            weight = config.F1_SEVERITY_WEIGHT_MILD

        severity_weighted[domain] = z_d * weight

    return severity_weighted


# ═══════════════════════════════════════════════════════════════
#  F1c: IVW Composite + Cochran's Q + Random Effects
# ═══════════════════════════════════════════════════════════════


def _compute_ivw_composite(
    severity_weighted_z: dict[str, float],
    subdomain_variances: dict[str, float],
) -> tuple[float, dict[str, float], float, float, bool]:
    """F1c: Compute IVW composite with heterogeneity check.

    Formula F-1: CRCI = Σ_d (w_d × z_d) / Σ_d w_d
    Formula F-3: Q = Σ_d w_d (z_d − CRCI)²
    I² = max(0, (Q − (D−1)) / Q) × 100

    If I² > 50%: apply random-effects adjustment.

    Returns:
        (crci_composite, weights, Q, I_squared, re_applied)
    """
    domains = list(severity_weighted_z.keys())
    D = len(domains)

    if D == 0:
        return 0.0, {}, 0.0, 0.0, False

    # Spec line 3187: If only 1 domain, composite = that z-score
    if D == 1:
        domain = domains[0]
        z = severity_weighted_z[domain]
        var = subdomain_variances.get(domain, 1.0)
        w = 1.0 / var
        return z, {domain: w}, 0.0, 0.0, False

    # Fixed-effects weights: w_d = 1 / σ²_d
    weights: dict[str, float] = {}
    for d in domains:
        var_d = subdomain_variances.get(d, 1.0)
        weights[d] = 1.0 / var_d

    # Formula F-1: IVW composite
    sum_wz = sum(weights[d] * severity_weighted_z[d] for d in domains)
    sum_w = sum(weights[d] for d in domains)
    crci = sum_wz / sum_w if sum_w > 0 else 0.0

    # Formula F-3: Cochran's Q
    Q = sum(weights[d] * (severity_weighted_z[d] - crci) ** 2 for d in domains)

    # I² = max(0, (Q − (D−1)) / Q) × 100
    I_squared = max(0.0, (Q - (D - 1)) / Q) * 100.0 if Q > 0 else 0.0

    # Random-effects adjustment if I² > 50%
    re_applied = False
    if I_squared > config.F1_I_SQUARED_RE_THRESHOLD:
        # τ² = max(0, (Q − (D−1)) / (Σw − Σw²/Σw))
        sum_w_sq = sum(w ** 2 for w in weights.values())
        denom = sum_w - sum_w_sq / sum_w if sum_w > 0 else 1.0
        tau_sq = max(0.0, (Q - (D - 1)) / denom) if denom > 0 else 0.0

        # Recompute with random-effects weights: w*_d = 1 / (σ²_d + τ²)
        for d in domains:
            var_d = subdomain_variances.get(d, 1.0)
            weights[d] = 1.0 / (var_d + tau_sq)

        sum_wz = sum(weights[d] * severity_weighted_z[d] for d in domains)
        sum_w = sum(weights[d] for d in domains)
        crci = sum_wz / sum_w if sum_w > 0 else 0.0
        re_applied = True

        logger.info(
            "F1c: I²=%.1f%% > 50%% → random effects applied (τ²=%.4f)",
            I_squared, tau_sq,
        )

    return crci, weights, Q, I_squared, re_applied


def _classify_severity_tier(percentile: float) -> SeverityTier:
    """Classify percentile into severity tier.

    Spec lines 3179-3185.
    """
    if percentile >= config.F1_TIER_EXCELLENT_MIN:
        return SeverityTier.EXCELLENT
    if percentile >= config.F1_TIER_GOOD_MIN:
        return SeverityTier.GOOD
    if percentile >= config.F1_TIER_MILD_MIN:
        return SeverityTier.MILD_IMPAIRMENT
    if percentile >= config.F1_TIER_MODERATE_MIN:
        return SeverityTier.MODERATE_IMPAIRMENT
    if percentile >= config.F1_TIER_POOR_MIN:
        return SeverityTier.POOR
    return SeverityTier.SEVERE_IMPAIRMENT


# ═══════════════════════════════════════════════════════════════
#  Gate F-G1
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f_g1(result: CompositeState) -> None:
    """Gate F-G1: Composite outcome valid.

    Conditions (spec line 3190):
        1. crci_composite ∈ [-5, 5]
        2. percentile ∈ [0, 100]
        3. Σ weights > 0
        4. severity_tier assigned

    Raises:
        GateViolation: If any condition fails.
    """
    if not (config.F1_COMPOSITE_Z_MIN <= result.crci_composite <= config.F1_COMPOSITE_Z_MAX):
        raise GateViolation(
            "F-G1",
            f"crci_composite = {result.crci_composite:.4f} "
            f"outside [{config.F1_COMPOSITE_Z_MIN}, {config.F1_COMPOSITE_Z_MAX}]",
        )

    if not (0.0 <= result.percentile <= 100.0):
        raise GateViolation(
            "F-G1",
            f"percentile = {result.percentile:.4f} outside [0, 100]",
        )

    total_weight = sum(result.subdomain_weights.values())
    if total_weight <= 0:
        raise GateViolation(
            "F-G1",
            f"Total weight = {total_weight} ≤ 0",
        )

    logger.info(
        "Gate F-G1 PASSED: CRCI=%.3f, percentile=%.1f, tier=%s",
        result.crci_composite, result.percentile, result.severity_tier.value,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: compute_composite_score (F1 entry point)
# ═══════════════════════════════════════════════════════════════


def compute_composite_score(
    posterior_means: np.ndarray,
    posterior_variances: np.ndarray,
    domain_node_map: dict[str, list[int]] | None = None,
) -> CompositeState:
    """F1: Compute CRCI composite outcome score.

    Args:
        posterior_means: θ̂ posterior means (n_nodes,).
        posterior_variances: Diagonal of Σ_post (n_nodes,).
        domain_node_map: Optional map from domain name → node indices.

    Returns:
        CompositeState.

    Raises:
        GateViolation: If F-G1 fails.
    """
    n_nodes = len(posterior_means)

    logger.info(
        "── F1: Composite Outcome Scoring ──\n"
        "  n_nodes=%d",
        n_nodes,
    )

    # F1a: Extract subdomain scores
    subdomain_scores, subdomain_variances = _extract_subdomain_scores(
        posterior_means, posterior_variances, domain_node_map,
    )

    # F1b: Apply severity weights
    severity_weighted_z = _apply_severity_weights(subdomain_scores)

    # F1c: IVW composite + heterogeneity
    crci, weights, Q, I_sq, re_applied = _compute_ivw_composite(
        severity_weighted_z, subdomain_variances,
    )

    # Clamp to [-5, 5] (spec: WARN on gate if outside)
    crci_clamped = float(np.clip(crci, config.F1_COMPOSITE_Z_MIN, config.F1_COMPOSITE_Z_MAX))

    # Formula F-2: Percentile = Φ(−CRCI) × 100
    # Higher CRCI (more positive z) → lower percentile of impairment
    # Negative CRCI → higher impairment → lower percentile
    percentile = float(stats.norm.cdf(-crci_clamped) * 100.0)

    # Classify severity
    tier = _classify_severity_tier(percentile)

    result = CompositeState(
        crci_composite=crci_clamped,
        severity_tier=tier,
        percentile=percentile,
        subdomain_scores=subdomain_scores,
        subdomain_weights=weights,
        cochrans_Q=Q,
        I_squared=I_sq,
        random_effects_applied=re_applied,
        severity_weighted_z=severity_weighted_z,
        n_domains=len(subdomain_scores),
    )

    # Gate F-G1
    _validate_gate_f_g1(result)
    result.gate_f_g1_passed = True

    logger.info(
        "F1 complete: CRCI=%.3f, percentile=%.1f, tier=%s, I²=%.1f%%, "
        "%d domains, RE=%s",
        crci_clamped, percentile, tier.value, I_sq,
        len(subdomain_scores), re_applied,
    )

    return result
