# VERIFIED: formulas [F4-1, F4-2, F4-3a, F4-3b, F4-4, F4-5, F4-6] match
#           IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §2–4
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads MCDraws.theta0_draws (mc_sampler.py D1c),
#           NodeMap (node_loader.py A1), CompositeState (composite_scorer.py F1),
#           RawPosterior.fusion_levels (bayesian_update.py C3c)
# VERIFIED: forward wiring — writes CRCIRiskEstimate for report_assembler.py
#           → ClinicalRiskProfile → risk_dashboard.py (PRES)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [F-G4a, F-G4b, F-G4c] raise on failure
"""
Component: SYS_ALGORITHM.ALG-F.F4
Spec: IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §2–4
Formulas:
    F4-1: CRCI^(m) = 1[Σ_d 1(z_d^(m) ≤ z_multi) ≥ k_multi] ∨
                      1[∃d: z_d^(m) ≤ z_single]
    F4-2: P̂(CRCI) = (1/M) Σ_m CRCI^(m)
    F4-3a: MC-SE = √(P̂(1−P̂)/M)  (simulation error)
    F4-3b: P ~ Beta(S+0.5, F+0.5)  (Jeffreys interval)
    F4-4: P_d = (1/M) Σ_m 1(z_d^(m) ≤ z_multi)  (marginal domain impairment)
    F4-5: φ_d = trigger-share heuristic  (NOT Shapley — see §2.5B)
    F4-6: w_d% = w_d / Σw × 100  (IVW precision weight)
Reads: MCDraws.theta0_draws (from D1 — posterior samples at time t),
       NodeMap (from A1 — index + orientation), CompositeState (from F1 —
       IVW weights), RawPosterior.fusion_levels (from C3c — coverage)
Writes: CRCIRiskEstimate (consumed by report_assembler.py, risk_dashboard.py)
Gates: F-G4a (orientation/mapping), F-G4b (draw quality), F-G4c (output)
Approximations declared:
    - Domain-level aggregation replaces individual test scores (§2.1)
    - Trigger-share attribution replaces true Shapley values (§2.5B)
    - Jeffreys Beta smoothing replaces model-structural posterior (§2.4B)
    - No clinical calibration (§5.3) — output is model-derived, not calibrated
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_a_graph.node_loader import NodeMap
from .composite_scorer import CompositeState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class DomainRiskProfile:
    """Risk profile for a single cognitive domain.

    Three complementary views (§2.5):
        A. marginal_risk_pct — P(domain is impaired) [F4-4]
        B. trigger_share_pct — trigger-share attribution [F4-5] (NOT Shapley)
        C. ivw_weight_pct   — precision influence [F4-6] (NOT risk contribution)
    """

    domain_id: str
    domain_label: str
    node_ids: list[str]
    marginal_risk_pct: float          # P_d × 100 — Formula F4-4
    trigger_share_pct: float          # φ_d × 100 — Formula F4-5 (NOT Shapley)
    ivw_weight_pct: float             # w_d% — Formula F4-6 (precision influence)
    mean_z: float                     # E[z_d] across MC draws
    sd_z: float                       # SD[z_d] across MC draws
    z_5th: float                      # 5th percentile of z_d draws
    z_95th: float                     # 95th percentile of z_d draws
    is_directly_observed: bool        # True if any node had L2+ fusion level
    n_observations: int               # count of nodes with L2+ data


@dataclass
class CRCIRiskEstimate:
    """Complete clinical risk estimate output.

    risk_pct is a MODEL-DERIVED probability, NOT a clinically calibrated
    incidence rate. See calibration_status and §5.3 of the implementation plan.
    """

    # Primary risk estimate
    risk_pct: float                   # P̂(CRCI) × 100 — Formula F4-2
    risk_lower_pct: float             # Interval lower bound (× 100)
    risk_upper_pct: float             # Interval upper bound (× 100)
    risk_tier: str                    # LOW / MODERATE / ELEVATED / HIGH / VERY_HIGH
    risk_range_text: str              # e.g. "32%–41%"

    # Interval metadata
    interval_method: str              # "jeffreys" or "mc_se"
    interval_level: float             # 0.90
    mc_se: float                      # simulation standard error (always computed)
    n_draws_used: int

    # Coverage
    coverage_fraction: float          # fraction of 10 domains directly observed
    low_coverage_warning: bool        # True if coverage < F4_MIN_COVERAGE

    # Domain decomposition
    domain_profiles: list[DomainRiskProfile] = field(default_factory=list)

    # Provenance
    criteria_used: str = "ICCTF_Wefel2011_domain_level"
    domain_aggregation: str = "mean"
    thresholds: dict[str, float] = field(default_factory=dict)
    conditioning: str = "posterior_at_t"
    calibration_status: str = "uncalibrated_model_derived"

    # Gate
    gate_f_g4_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  F-G4a: Orientation & Mapping Validity (hard gate, pre-compute)
# ═══════════════════════════════════════════════════════════════


def _validate_domain_mapping(
    node_map: NodeMap,
) -> dict[str, list[int]]:
    """Resolve F4_DOMAIN_NODE_MAP node_ids → column indices, validating
    existence and orientation per Gate F-G4a.

    Gate F-G4a conditions (§4.6):
        1. Every node_id in F4_DOMAIN_NODE_MAP must exist in node_map.
        2. Every mapped node must have orientation == "POS_UP".
        3. Every mapped node must have unit_of_measure == "z-score".

    If ANY mapped node fails → raise GateViolation("F-G4a", ...).
    Do NOT silently skip the domain.

    Returns:
        domain_id → list[node_column_index] mapping.
    """
    domain_index_map: dict[str, list[int]] = {}
    violations: list[str] = []

    for domain_id, node_ids in config.F4_DOMAIN_NODE_MAP.items():
        indices: list[int] = []
        for nid in node_ids:
            idx = node_map.node_index.get(nid)
            if idx is None:
                violations.append(
                    f"domain={domain_id}: node_id={nid} not found in NodeMap"
                )
                continue

            # Check orientation — must be POS_UP for ICCTF z-score
            node_orientation = node_map.orientation.get(nid, "UNKNOWN")
            if node_orientation != "POS_UP":
                violations.append(
                    f"domain={domain_id}: node_id={nid} has "
                    f"orientation={node_orientation}, expected POS_UP"
                )

            # Check unit — must be z-score
            # NodeDef stores unit_of_measure; look up by index
            if idx < len(node_map.nodes):
                node_def = node_map.nodes[idx]
                if node_def.unit_of_measure != "z-score":
                    violations.append(
                        f"domain={domain_id}: node_id={nid} has "
                        f"unit={node_def.unit_of_measure}, expected z-score"
                    )

            indices.append(idx)

        domain_index_map[domain_id] = indices

    if violations:
        raise GateViolation(
            "F-G4a",
            "Domain mapping validation failed:\n  " + "\n  ".join(violations),
        )

    logger.info(
        "Gate F-G4a PASSED: %d domains, %d total nodes mapped, all POS_UP z-score",
        len(domain_index_map),
        sum(len(v) for v in domain_index_map.values()),
    )

    return domain_index_map


# ═══════════════════════════════════════════════════════════════
#  F4-1: Per-Draw Domain Z-Scores + CRCI Classification
# ═══════════════════════════════════════════════════════════════


def _extract_domain_draws(
    theta_draws: np.ndarray,
    domain_index_map: dict[str, list[int]],
) -> dict[str, np.ndarray]:
    """Extract per-domain z-score draws from posterior draws.

    For each domain, aggregate the z-scores of its constituent node(s)
    using the configured aggregation method (F4_DOMAIN_AGGREGATION).

    Args:
        theta_draws: (M, n_nodes) posterior draws from D1c.
        domain_index_map: domain_id → list[column index].

    Returns:
        domain_id → (M,) array of per-draw domain z-scores.
    """
    agg = config.F4_DOMAIN_AGGREGATION
    domain_draws: dict[str, np.ndarray] = {}

    for domain_id, indices in domain_index_map.items():
        if len(indices) == 0:
            # No nodes mapped — should not happen after F-G4a
            continue

        if len(indices) == 1:
            # Single node — no aggregation needed
            domain_draws[domain_id] = theta_draws[:, indices[0]]
        else:
            # Multiple nodes → aggregate across nodes per draw
            node_z = theta_draws[:, indices]  # (M, n_nodes_in_domain)
            if agg == "min":
                # §2.1: min across node z-scores (closer to test-level ICCTF)
                domain_draws[domain_id] = np.min(node_z, axis=1)
            else:
                # §2.1: mean across node z-scores (default)
                domain_draws[domain_id] = np.mean(node_z, axis=1)

    return domain_draws


def _classify_crci_per_draw(
    domain_draws: dict[str, np.ndarray],
) -> np.ndarray:
    """Formula F4-1: Apply ICCTF criteria to each MC draw.

    CRCI^(m) = 1[Σ_d 1(z_d^(m) ≤ z_multi) ≥ k_multi]
               ∨ 1[∃d: z_d^(m) ≤ z_single]

    Args:
        domain_draws: domain_id → (M,) z-score draws.

    Returns:
        (M,) boolean array where True = CRCI positive for that draw.
    """
    z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    k_multi = config.F4_THRESHOLD_MULTI_DOMAIN_COUNT
    z_single = config.F4_THRESHOLD_SINGLE_DOMAIN_Z

    domains = list(domain_draws.keys())
    M = len(next(iter(domain_draws.values())))

    # Count domains below multi-domain threshold per draw
    # Stack: (n_domains, M) → sum domains below threshold → (M,)
    below_multi = np.zeros(M, dtype=np.int32)
    any_below_single = np.zeros(M, dtype=bool)

    for d_id in domains:
        z_d = domain_draws[d_id]  # (M,)
        below_multi += (z_d <= z_multi).astype(np.int32)
        any_below_single |= (z_d <= z_single)

    # Formula F4-1: multi-domain criterion OR single severe criterion
    crci_indicator = (below_multi >= k_multi) | any_below_single

    return crci_indicator


# ═══════════════════════════════════════════════════════════════
#  F4-2: Point Estimate
# ═══════════════════════════════════════════════════════════════


def _compute_risk_point_estimate(
    crci_indicator: np.ndarray,
) -> tuple[float, int, int]:
    """Formula F4-2: P̂(CRCI) = (1/M) Σ_m CRCI^(m).

    Returns:
        (risk_probability, n_positive, n_draws)
    """
    M = len(crci_indicator)
    S = int(np.sum(crci_indicator))
    p_hat = S / M if M > 0 else 0.0
    return p_hat, S, M


# ═══════════════════════════════════════════════════════════════
#  F4-3: Interval Estimation
# ═══════════════════════════════════════════════════════════════


def _compute_mc_se(p_hat: float, M: int) -> float:
    """Formula F4-3a: MC-SE = √(P̂(1−P̂)/M).

    This is the Monte Carlo simulation error — how precisely we've
    estimated this probability given M draws. NOT posterior uncertainty.
    """
    if M <= 0:
        return 0.0
    return np.sqrt(p_hat * (1.0 - p_hat) / M)


def _compute_interval(
    S: int, M: int, p_hat: float, mc_se: float,
) -> tuple[float, float, str]:
    """Compute risk interval using configured method.

    Method "jeffreys" (Formula F4-3b):
        P ~ Beta(S + 0.5, M - S + 0.5)
        Interval = [Beta^{-1}(α/2), Beta^{-1}(1 - α/2)]
        Justification: Brown et al., Statist Sci, 2001.

    Method "mc_se":
        P̂ ± z_α √(P̂(1-P̂)/M)

    Returns:
        (lower, upper, method_name)
    """
    method = config.F4_INTERVAL_METHOD
    level = config.F4_CI_LEVEL
    alpha_half = (1.0 - level) / 2.0

    if method == "jeffreys":
        # Formula F4-3b: Jeffreys prior Beta(0.5, 0.5) → posterior Beta(S+0.5, F+0.5)
        a = S + 0.5
        b = (M - S) + 0.5
        lower = float(stats.beta.ppf(alpha_half, a, b))
        upper = float(stats.beta.ppf(1.0 - alpha_half, a, b))
        return lower, upper, "jeffreys"
    else:
        # MC-SE normal interval
        z_alpha = float(stats.norm.ppf(1.0 - alpha_half))
        lower = max(0.0, p_hat - z_alpha * mc_se)
        upper = min(1.0, p_hat + z_alpha * mc_se)
        return lower, upper, "mc_se"


# ═══════════════════════════════════════════════════════════════
#  F4-4: Marginal Domain Impairment Probability
# ═══════════════════════════════════════════════════════════════


def _compute_marginal_domain_risk(
    domain_draws: dict[str, np.ndarray],
) -> dict[str, float]:
    """Formula F4-4: P_d = (1/M) Σ_m 1(z_d^(m) ≤ z_multi).

    These are marginal probabilities — they do NOT sum to any particular
    value. Each answers: "What is the probability that this specific
    domain is impaired?"
    """
    z_thresh = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    marginals: dict[str, float] = {}

    for d_id, z_d in domain_draws.items():
        M = len(z_d)
        marginals[d_id] = float(np.sum(z_d <= z_thresh) / M) if M > 0 else 0.0

    return marginals


# ═══════════════════════════════════════════════════════════════
#  F4-5: Trigger-Share Attribution (NOT Shapley)
# ═══════════════════════════════════════════════════════════════


def _compute_trigger_share(
    domain_draws: dict[str, np.ndarray],
    crci_indicator: np.ndarray,
) -> dict[str, float]:
    """Formula F4-5: Trigger-share heuristic.

    For each draw where CRCI is positive, identify which domain(s)
    triggered it and split credit equally:

        φ_d = (1 / (M · P̂)) Σ_{m: CRCI^(m)=1} 1(z_d^(m) ≤ z_thresh) / N_triggered^(m)

    where N_triggered^(m) is the count of domains below threshold in draw m.
    Σ_d φ_d = 1.0.

    This is NOT a Shapley value. True Shapley values would require
    permutation sampling over domain subsets — O(K! × M) — and
    computing marginal contributions. See §2.5B.

    When P̂ = 0 (no draws positive), returns 0.0 for all domains.
    """
    domains = list(domain_draws.keys())
    M = len(crci_indicator)
    S = int(np.sum(crci_indicator))

    shares: dict[str, float] = {d: 0.0 for d in domains}

    if S == 0:
        # No positive draws → trigger-share undefined, return zeros
        return shares

    # Both thresholds can trigger — use the union of domains below either
    z_multi = config.F4_THRESHOLD_MULTI_DOMAIN_Z
    z_single = config.F4_THRESHOLD_SINGLE_DOMAIN_Z

    # For each positive draw, find triggering domains and split credit
    positive_mask = crci_indicator.astype(bool)

    for d_id in domains:
        z_d = domain_draws[d_id]
        # A domain "triggers" if it was below either threshold
        # (it contributed to the positive classification)
        below = (z_d <= z_multi) | (z_d <= z_single)
        shares[d_id] = float(np.sum(below[positive_mask]))

    # Compute N_triggered per positive draw for equal-split
    triggered_counts = np.zeros(M)
    for d_id in domains:
        z_d = domain_draws[d_id]
        below = (z_d <= z_multi) | (z_d <= z_single)
        triggered_counts += below.astype(float)

    # Avoid division by zero for draws where no domain is technically below
    # (should not happen if CRCI is positive, but guard)
    triggered_counts = np.maximum(triggered_counts, 1.0)

    # Recompute shares with proper equal-split
    shares = {d: 0.0 for d in domains}
    for d_id in domains:
        z_d = domain_draws[d_id]
        below = ((z_d <= z_multi) | (z_d <= z_single)).astype(float)
        # Credit for this domain in each positive draw = 1/N_triggered
        per_draw_credit = below / triggered_counts
        shares[d_id] = float(np.sum(per_draw_credit[positive_mask]))

    # Normalize: divide by S (number of positive draws) so Σ φ_d = 1
    total = sum(shares.values())
    if total > 0:
        for d_id in shares:
            shares[d_id] /= total

    return shares


# ═══════════════════════════════════════════════════════════════
#  F4-6: IVW Precision Weight Percentage
# ═══════════════════════════════════════════════════════════════


def _compute_ivw_weight_pct(
    composite_state: CompositeState,
    domain_ids: list[str],
) -> dict[str, float]:
    """Formula F4-6: w_d% = w_d / Σw × 100.

    Uses IVW precision weights from F1's CompositeState.subdomain_weights.
    Note: F1 uses 11 domains (including mood/fatigue), F4 uses 10 cognitive-only.
    We extract only the cognitive domains that appear in both.

    When a domain has no F1 weight, it gets 0% precision influence.
    This is a property of the evidence base, NOT a risk contribution.
    """
    weights_pct: dict[str, float] = {}
    raw_weights: dict[str, float] = {}

    for d_id in domain_ids:
        # Try to find matching F1 weight
        # F1 may use different domain names — try direct match first,
        # then fall back to 0.0 if the domain isn't in F1's vocabulary
        w = composite_state.subdomain_weights.get(d_id, 0.0)
        raw_weights[d_id] = w

    total_w = sum(raw_weights.values())

    for d_id in domain_ids:
        if total_w > 0:
            weights_pct[d_id] = (raw_weights[d_id] / total_w) * 100.0
        else:
            weights_pct[d_id] = 100.0 / len(domain_ids) if domain_ids else 0.0
            logger.warning(
                "F4-6: Total IVW weight = 0 for cognitive domains. "
                "Using uniform 1/D weights. domain=%s", d_id,
            )

    return weights_pct


# ═══════════════════════════════════════════════════════════════
#  Coverage Computation (§2.6)
# ═══════════════════════════════════════════════════════════════


def _compute_coverage(
    domain_index_map: dict[str, list[int]],
    fusion_levels: dict[int, set[str]],
) -> tuple[float, dict[str, bool], dict[str, int]]:
    """Compute observation coverage across cognitive domains.

    A domain is "directly observed" if at least one of its mapped
    node_ids received a non-zero precision increment during C3a —
    i.e., the C3c fusion_levels dict records that node at fusion
    level L2 (direct scalar observation) or L3 (multi-source fusion).

    See §2.6 for the formal definition of "directly observed."

    Returns:
        (coverage_fraction, domain_observed, domain_n_obs)
    """
    n_domains = len(domain_index_map)
    domain_observed: dict[str, bool] = {}
    domain_n_obs: dict[str, int] = {}

    for d_id, indices in domain_index_map.items():
        n_obs = 0
        for idx in indices:
            levels = fusion_levels.get(idx, set())
            # L2 or L3 = directly observed (see §2.6 definition)
            if "L2" in levels or "L3" in levels:
                n_obs += 1
        domain_observed[d_id] = (n_obs > 0)
        domain_n_obs[d_id] = n_obs

    n_observed = sum(1 for v in domain_observed.values() if v)
    coverage = n_observed / n_domains if n_domains > 0 else 0.0

    return coverage, domain_observed, domain_n_obs


# ═══════════════════════════════════════════════════════════════
#  Risk Tier Classification (§5.4)
# ═══════════════════════════════════════════════════════════════


def _classify_risk_tier(risk_pct: float) -> str:
    """Map continuous risk percentage to communication tier.

    These are communication-only defaults, NOT evidence-based thresholds.
    See §5.4 for justification.
    """
    if risk_pct < config.F4_TIER_LOW_MAX:
        return "LOW"
    if risk_pct < config.F4_TIER_MODERATE_MAX:
        return "MODERATE"
    if risk_pct < config.F4_TIER_ELEVATED_MAX:
        return "ELEVATED"
    if risk_pct < config.F4_TIER_HIGH_MAX:
        return "HIGH"
    return "VERY_HIGH"


# ═══════════════════════════════════════════════════════════════
#  F-G4b: Draw Quality (hard gate)
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f_g4b(
    theta_draws: np.ndarray,
    domain_draws: dict[str, np.ndarray],
) -> None:
    """Gate F-G4b: Draw quality checks.

    Conditions (§4.6):
        1. n_draws ≥ F4_MIN_DRAWS (default 1000)
        2. All domain z-score draws are finite (no NaN/Inf)
        3. At least 1 domain has observable variation (SD > 1e-10)
    """
    M = theta_draws.shape[0]
    violations: list[str] = []

    # Condition 1: Minimum draw count
    if M < config.F4_MIN_DRAWS:
        violations.append(
            f"n_draws={M} < F4_MIN_DRAWS={config.F4_MIN_DRAWS}"
        )

    # Condition 2: All domain draws finite
    for d_id, z_d in domain_draws.items():
        n_nonfinite = int(np.sum(~np.isfinite(z_d)))
        if n_nonfinite > 0:
            violations.append(
                f"domain={d_id}: {n_nonfinite} non-finite z-score draws"
            )

    # Condition 3: At least 1 domain has variation
    any_variation = False
    for z_d in domain_draws.values():
        if np.std(z_d) > 1e-10:
            any_variation = True
            break

    if not any_variation and len(domain_draws) > 0:
        violations.append(
            "No domain has observable variation (all SD < 1e-10). "
            "Posterior may be degenerate."
        )

    if violations:
        raise GateViolation(
            "F-G4b",
            "Draw quality validation failed:\n  " + "\n  ".join(violations),
        )

    logger.info(
        "Gate F-G4b PASSED: M=%d draws, all finite, variation present",
        M,
    )


# ═══════════════════════════════════════════════════════════════
#  F-G4c: Output Consistency (hard gate)
# ═══════════════════════════════════════════════════════════════


def _validate_gate_f_g4c(result: CRCIRiskEstimate) -> None:
    """Gate F-G4c: Output consistency checks.

    Conditions (§4.6):
        1. risk_pct ∈ [0, 100]
        2. risk_lower_pct ≤ risk_pct ≤ risk_upper_pct
        3. Σ trigger_share_pct = 100% (±0.5% tolerance) when P̂ > 0
        4. Σ ivw_weight_pct = 100% (±0.1% tolerance)
        5. coverage_fraction ∈ [0, 1]
    """
    violations: list[str] = []

    # Condition 1
    if not (0.0 <= result.risk_pct <= 100.0):
        violations.append(f"risk_pct={result.risk_pct:.4f} outside [0, 100]")

    # Condition 2
    if result.risk_lower_pct > result.risk_pct + 0.01:  # tiny float tolerance
        violations.append(
            f"risk_lower_pct={result.risk_lower_pct:.4f} > "
            f"risk_pct={result.risk_pct:.4f}"
        )
    if result.risk_upper_pct < result.risk_pct - 0.01:
        violations.append(
            f"risk_upper_pct={result.risk_upper_pct:.4f} < "
            f"risk_pct={result.risk_pct:.4f}"
        )

    # Condition 3: Trigger-share sums to 100% (skip if P̂ = 0)
    if result.risk_pct > 0.0 and result.domain_profiles:
        trigger_sum = sum(dp.trigger_share_pct for dp in result.domain_profiles)
        if abs(trigger_sum - 100.0) > config.F4_TRIGGER_SHARE_SUM_TOLERANCE * 100:
            violations.append(
                f"Σ trigger_share_pct = {trigger_sum:.4f}%, "
                f"expected 100% ± {config.F4_TRIGGER_SHARE_SUM_TOLERANCE * 100}%"
            )

    # Condition 4: IVW weight sums to 100%
    if result.domain_profiles:
        ivw_sum = sum(dp.ivw_weight_pct for dp in result.domain_profiles)
        if abs(ivw_sum - 100.0) > config.F4_IVW_WEIGHT_SUM_TOLERANCE:
            violations.append(
                f"Σ ivw_weight_pct = {ivw_sum:.4f}%, "
                f"expected 100% ± {config.F4_IVW_WEIGHT_SUM_TOLERANCE}%"
            )

    # Condition 5
    if not (0.0 <= result.coverage_fraction <= 1.0):
        violations.append(
            f"coverage_fraction={result.coverage_fraction:.4f} outside [0, 1]"
        )

    if violations:
        raise GateViolation(
            "F-G4c",
            "Output consistency validation failed:\n  "
            + "\n  ".join(violations),
        )

    logger.info(
        "Gate F-G4c PASSED: risk=%.1f%% [%.1f%%–%.1f%%], "
        "trigger_share_sum=%.1f%%, ivw_sum=%.1f%%, coverage=%.2f",
        result.risk_pct,
        result.risk_lower_pct,
        result.risk_upper_pct,
        sum(dp.trigger_share_pct for dp in result.domain_profiles),
        sum(dp.ivw_weight_pct for dp in result.domain_profiles),
        result.coverage_fraction,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: estimate_crci_risk (F4 entry point)
# ═══════════════════════════════════════════════════════════════


def estimate_crci_risk(
    theta_draws: np.ndarray,
    node_map: NodeMap,
    composite_state: CompositeState,
    fusion_levels: dict[int, set[str]],
) -> CRCIRiskEstimate:
    """F4: Estimate P̂(CRCI | y_{≤t}, model) from posterior draws.

    This function computes the posterior predictive event probability for
    clinically significant CRCI as defined by domain-level ICCTF criteria
    (Wefel et al. 2011, Lancet Oncol 12(7):703-708).

    The output is a MODEL-DERIVED probability, not a clinically calibrated
    rate. It inherits all model assumptions: DAG structure, prior
    specifications, evidence quality weights, and the domain-level
    approximation to ICCTF test-level criteria.

    Args:
        theta_draws: Posterior draws (M × n_nodes). These are samples from
            N(θ̂, Σ_post) after Bayesian update on patient observations,
            NOT pre-treatment baselines. Produced by mc_sampler.py D1c
            (MCDraws.theta0_draws).
        node_map: Loaded NodeMap for index lookups and orientation validation.
        composite_state: F1 output — used ONLY for IVW weights (view C,
            Formula F4-6). Not used for risk classification.
        fusion_levels: From C3c (RawPosterior.fusion_levels) — identifies
            which nodes were directly observed (L2+). Used for coverage
            computation (§2.6).

    Returns:
        CRCIRiskEstimate with risk %, interval, domain profiles, and
        all provenance metadata.

    Raises:
        GateViolation: F-G4a (orientation/mapping), F-G4b (draw quality),
                       F-G4c (output consistency).
    """
    M, n_nodes = theta_draws.shape

    logger.info(
        "── F4: Clinical Risk Estimation ──\n"
        "  M=%d draws, n_nodes=%d, aggregation=%s, interval=%s",
        M, n_nodes, config.F4_DOMAIN_AGGREGATION, config.F4_INTERVAL_METHOD,
    )

    # ── Gate F-G4a: Validate domain mapping ──
    domain_index_map = _validate_domain_mapping(node_map)

    # ── Extract per-domain z-score draws ──
    domain_draws = _extract_domain_draws(theta_draws, domain_index_map)

    # ── Gate F-G4b: Validate draw quality ──
    _validate_gate_f_g4b(theta_draws, domain_draws)

    # ── Formula F4-1: CRCI classification per draw ──
    crci_indicator = _classify_crci_per_draw(domain_draws)

    # ── Formula F4-2: Point estimate ──
    p_hat, S, M_draws = _compute_risk_point_estimate(crci_indicator)

    # ── Formula F4-3a: MC standard error (always computed) ──
    mc_se = _compute_mc_se(p_hat, M_draws)

    # ── Formula F4-3b: Interval estimation ──
    lower, upper, method = _compute_interval(S, M_draws, p_hat, mc_se)

    # ── Formula F4-4: Marginal domain impairment ──
    marginal_risk = _compute_marginal_domain_risk(domain_draws)

    # ── Formula F4-5: Trigger-share attribution ──
    trigger_shares = _compute_trigger_share(domain_draws, crci_indicator)

    # ── Formula F4-6: IVW precision weights ──
    domain_ids = list(config.F4_DOMAIN_NODE_MAP.keys())
    ivw_weights = _compute_ivw_weight_pct(composite_state, domain_ids)

    # ── Coverage computation (§2.6) ──
    coverage, domain_observed, domain_n_obs = _compute_coverage(
        domain_index_map, fusion_levels,
    )
    low_coverage = coverage < config.F4_MIN_COVERAGE

    if low_coverage:
        logger.warning(
            "F4: Low coverage — %.0f%% of domains directly observed "
            "(threshold: %.0f%%). Risk estimate is predominantly "
            "model-driven.",
            coverage * 100, config.F4_MIN_COVERAGE * 100,
        )

    # ── Assemble domain profiles ──
    domain_profiles: list[DomainRiskProfile] = []
    for d_id in domain_ids:
        z_d = domain_draws.get(d_id, np.array([0.0]))
        node_ids = config.F4_DOMAIN_NODE_MAP[d_id]

        domain_profiles.append(DomainRiskProfile(
            domain_id=d_id,
            domain_label=config.F4_DOMAIN_LABELS.get(d_id, d_id),
            node_ids=node_ids,
            marginal_risk_pct=marginal_risk.get(d_id, 0.0) * 100.0,
            trigger_share_pct=trigger_shares.get(d_id, 0.0) * 100.0,
            ivw_weight_pct=ivw_weights.get(d_id, 0.0),
            mean_z=float(np.mean(z_d)),
            sd_z=float(np.std(z_d)),
            z_5th=float(np.percentile(z_d, 5)),
            z_95th=float(np.percentile(z_d, 95)),
            is_directly_observed=domain_observed.get(d_id, False),
            n_observations=domain_n_obs.get(d_id, 0),
        ))

    # ── Risk tier ──
    risk_pct = p_hat * 100.0
    risk_lower_pct = lower * 100.0
    risk_upper_pct = upper * 100.0
    risk_tier = _classify_risk_tier(risk_pct)

    risk_range_text = f"{risk_lower_pct:.0f}%–{risk_upper_pct:.0f}%"

    # ── Assemble result ──
    result = CRCIRiskEstimate(
        risk_pct=risk_pct,
        risk_lower_pct=risk_lower_pct,
        risk_upper_pct=risk_upper_pct,
        risk_tier=risk_tier,
        risk_range_text=risk_range_text,
        interval_method=method,
        interval_level=config.F4_CI_LEVEL,
        mc_se=mc_se,
        n_draws_used=M_draws,
        coverage_fraction=coverage,
        low_coverage_warning=low_coverage,
        domain_profiles=domain_profiles,
        criteria_used="ICCTF_Wefel2011_domain_level",
        domain_aggregation=config.F4_DOMAIN_AGGREGATION,
        thresholds={
            "multi_domain_z": config.F4_THRESHOLD_MULTI_DOMAIN_Z,
            "multi_domain_count": float(config.F4_THRESHOLD_MULTI_DOMAIN_COUNT),
            "single_domain_z": config.F4_THRESHOLD_SINGLE_DOMAIN_Z,
        },
        conditioning="posterior_at_t",
        calibration_status="uncalibrated_model_derived",
    )

    # ── Gate F-G4c: Output consistency ──
    _validate_gate_f_g4c(result)
    result.gate_f_g4_passed = True

    logger.info(
        "F4 complete: P̂(CRCI)=%.1f%% [%.1f%%–%.1f%% %s], tier=%s, "
        "coverage=%.0f%%, %d domains, low_coverage=%s",
        risk_pct, risk_lower_pct, risk_upper_pct, method,
        risk_tier, coverage * 100, len(domain_profiles), low_coverage,
    )

    return result
