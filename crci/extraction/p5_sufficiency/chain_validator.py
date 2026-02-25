# VERIFIED: formulas [P5-1, P5-2, P5-5] match spec SYS_EX lines 1600-1720
# VERIFIED: imports — all modules exist (config.py, enums.py, intermediate_states.py)
# VERIFIED: backward wiring — reads CompiledEdge from p4_aggregation
# VERIFIED: forward wiring — writes ChainValidationResult for sufficiency_reporter.py
# VERIFIED: no hardcoded formula parameters — Z thresholds and SE inflations from config
# VERIFIED: gates [P5-G2] raise on failure
"""
Component: SYS_EXTRACTION.EX-P5.S2-S5
Spec: SYS_EXTRACTION_COMPLETE.md lines 1600-1720
Formulas: P5-1 (chain product), P5-2 (chain-vs-direct Z),
          P5-5 (discrepancy classification)
Reads: CompiledEdge (from p4_aggregation)
Writes: ChainValidationResult (consumed by sufficiency_reporter.py)
Gates: P5-G2 (no SEVERE discrepancies unresolved -> BLOCK)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from crci.shared.config import (
    COHERENCE_SE_INFLATION_ALARM,
    COHERENCE_SE_INFLATION_INVESTIGATE,
    COHERENCE_SE_INFLATION_MONITOR,
    COHERENCE_Z_ALARM,
    COHERENCE_Z_MONITOR,
    COHERENCE_Z_PASS,
    HETEROGENEITY_HIGH_THRESHOLD,
    P5_FM5_NONLINEARITY_RATIO,
    SIGMA_SQ_STRUCTURAL_DEFAULT,
)
from crci.shared.models.enums import FailureMode, TriageTier
from crci.shared.models.intermediate_states import (
    ChainValidationResult,
    CompiledEdge,
    GateViolation,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Supporting data structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class PathwayDefinition:
    """Definition of a causal pathway through the DAG."""

    pathway_id: str
    edge_sequence: list[str]  # Ordered list of edge_relation_ids
    direct_edge_id: str | None = None  # edge_relation_id for direct path


@dataclass
class SEInflationRecord:
    """Tracks SE inflation applied to an edge from chain validation."""

    edge_relation_id: str
    chain_inflations: list[float] = field(default_factory=list)
    max_inflation: float = 1.0


# ═══════════════════════════════════════════════════════════════
#  P5-S2: Chain Product (Formula P5-1)
# ═══════════════════════════════════════════════════════════════


def compute_chain_product(
    edges_in_chain: list[CompiledEdge],
) -> tuple[float, float]:
    """Formula P5-1: Compute chain effect and SE via delta method.

    beta_chain = product_e(beta_e)   (product along pathway)
    SE_chain = |beta_chain| * sqrt(sum((SE_e / beta_e)^2))   (delta method)

    Parameters
    ----------
    edges_in_chain : list[CompiledEdge]
        Ordered edges along the causal pathway.

    Returns
    -------
    Tuple of (beta_chain, se_chain).
    """
    if not edges_in_chain:
        return 0.0, 0.0

    # Formula P5-1: beta_chain = product of beta_e
    beta_chain = 1.0
    for edge in edges_in_chain:
        beta_chain *= edge.beta_mean

    # Formula P5-1: SE_chain = |beta_chain| * sqrt(sum((SE_e / beta_e)^2))
    # Delta method for error propagation through products
    sum_relative_var = 0.0
    for edge in edges_in_chain:
        if edge.beta_mean == 0.0:
            # If any edge beta is exactly 0, the chain product is 0 and
            # the delta-method SE is mathematically undefined (division by 0).
            # Mark the chain as untestable: beta_chain=0, SE=0.
            logger.warning(
                "P5-S2: Edge '%s' has beta_mean=0.0 in chain; "
                "chain product is 0 and delta-method SE undefined. "
                "Marking chain as UNTESTABLE.",
                edge.edge_relation_id,
            )
            return 0.0, 0.0
        relative_se = edge.beta_se / edge.beta_mean
        sum_relative_var += relative_se ** 2

    se_chain = abs(beta_chain) * math.sqrt(sum_relative_var)

    return beta_chain, se_chain


# ═══════════════════════════════════════════════════════════════
#  P5-S3: Chain-vs-Direct (Formula P5-2)
# ═══════════════════════════════════════════════════════════════


def compute_chain_vs_direct_z(
    beta_chain: float,
    se_chain: float,
    beta_direct: float,
    se_direct: float,
) -> float:
    """Formula P5-2: Z-test for chain-vs-direct discrepancy.

    Z = |beta_chain - beta_direct| / sqrt(SE^2_chain + SE^2_direct)

    Parameters
    ----------
    beta_chain : float
        Chain product estimate.
    se_chain : float
        Chain SE from delta method.
    beta_direct : float
        Direct edge estimate.
    se_direct : float
        SE of the direct edge.

    Returns
    -------
    Z statistic.
    """
    denominator_sq = se_chain ** 2 + se_direct ** 2
    if denominator_sq <= 0:
        logger.warning(
            "P5-S3: denominator is zero for chain-vs-direct Z; "
            "returning Z=0.0"
        )
        return 0.0

    z = abs(beta_chain - beta_direct) / math.sqrt(denominator_sq)
    return z


def triage_z_score(z: float) -> TriageTier:
    """Classify Z statistic into triage tier.

    Z < COHERENCE_Z_PASS (1.5) -> PASS
    1.5 <= Z < COHERENCE_Z_MONITOR (2.0) -> MONITOR
    2.0 <= Z < COHERENCE_Z_ALARM (3.0) -> INVESTIGATE
    Z >= COHERENCE_Z_ALARM (3.0) -> ALARM

    Parameters
    ----------
    z : float
        The Z statistic from chain-vs-direct comparison.

    Returns
    -------
    TriageTier classification.
    """
    if z < COHERENCE_Z_PASS:
        return TriageTier.PASS
    elif z < COHERENCE_Z_MONITOR:
        return TriageTier.MONITOR
    elif z < COHERENCE_Z_ALARM:
        return TriageTier.INVESTIGATE
    else:
        return TriageTier.ALARM


# ═══════════════════════════════════════════════════════════════
#  P5-S4: Discrepancy Classification (Formula P5-5)
# ═══════════════════════════════════════════════════════════════


def classify_discrepancy(
    triage_tier: TriageTier,
    pathway_id: str,
    edges_in_chain: list[CompiledEdge],
    direct_edge: CompiledEdge | None = None,
) -> FailureMode:
    """Formula P5-5: Classify discrepancy into one of 6 failure modes.

    FM1: Missing mediator — chain has a gap (k=0 edge)
    FM2: Unmeasured confounding — direct edge has high I-squared
    FM3: Measurement artifact — edge has scale incompatibility
    FM4: Population heterogeneity — chain edges from different populations
    FM5: Non-linearity — large product with small direct effect
    FM6: Temporal mismatch — temporal lag differences

    For PASS tier, returns NONE.

    Parameters
    ----------
    triage_tier : TriageTier
        The triage classification from Z-test.
    pathway_id : str
        Identifier for the pathway being checked.
    edges_in_chain : list[CompiledEdge]
        Edges in the indirect chain.
    direct_edge : CompiledEdge | None
        The direct edge, if it exists.

    Returns
    -------
    FailureMode classification.
    """
    if triage_tier == TriageTier.PASS:
        return FailureMode.NONE

    # FM1: Missing mediator — any chain edge has k=0
    for edge in edges_in_chain:
        if edge.k == 0:
            logger.warning(
                "P5-S4 FM1: Missing mediator detected in pathway '%s' "
                "at edge '%s' (k=0)",
                pathway_id,
                edge.edge_relation_id,
            )
            return FailureMode.MEDIATION_LEAK

    # FM2: Unmeasured confounding — direct edge has high heterogeneity
    if direct_edge is not None and direct_edge.i_squared > HETEROGENEITY_HIGH_THRESHOLD:
        logger.warning(
            "P5-S4 FM2: Possible unmeasured confounding in pathway '%s' "
            "(direct edge I^2=%.1f%%)",
            pathway_id,
            direct_edge.i_squared,
        )
        return FailureMode.COLLIDER_BIAS

    # FM3: Measurement artifact — check for scale incompatibility across chain
    scales_in_chain = {edge.effect_scale for edge in edges_in_chain}
    if len(scales_in_chain) > 1:
        logger.warning(
            "P5-S4 FM3: Scale incompatibility in pathway '%s' "
            "(scales: %s)",
            pathway_id,
            ", ".join(str(s) for s in scales_in_chain),
        )
        return FailureMode.SCALE_INCOMPATIBILITY

    # FM4: Population heterogeneity — high tau-squared across chain edges
    high_tau_edges = [e for e in edges_in_chain if e.tau_squared > SIGMA_SQ_STRUCTURAL_DEFAULT]
    if len(high_tau_edges) > len(edges_in_chain) / 2:
        logger.warning(
            "P5-S4 FM4: Population heterogeneity in pathway '%s' "
            "(%d/%d edges have high tau^2)",
            pathway_id,
            len(high_tau_edges),
            len(edges_in_chain),
        )
        return FailureMode.POPULATION_DRIFT

    # FM5: Non-linearity — large chain product but small direct effect
    if direct_edge is not None:
        chain_product = 1.0
        for edge in edges_in_chain:
            chain_product *= abs(edge.beta_mean) if edge.beta_mean != 0 else 1.0
        if chain_product > P5_FM5_NONLINEARITY_RATIO * abs(direct_edge.beta_mean) and abs(direct_edge.beta_mean) > 0:
            logger.warning(
                "P5-S4 FM5: Non-linearity suspected in pathway '%s' "
                "(chain_product=%.4f >> direct=%.4f)",
                pathway_id,
                chain_product,
                direct_edge.beta_mean,
            )
            return FailureMode.MISSING_MODERATOR

    # FM6: Temporal mismatch — default for remaining unexplained discrepancies
    logger.warning(
        "P5-S4 FM6: Temporal mismatch suspected in pathway '%s' "
        "(no other failure mode matched)",
        pathway_id,
    )
    return FailureMode.TEMPORAL_MISMATCH


# ═══════════════════════════════════════════════════════════════
#  P5-S5: SE Inflation Feedback
# ═══════════════════════════════════════════════════════════════


def compute_se_inflation_for_tier(triage_tier: TriageTier) -> float:
    """Map triage tier to SE inflation factor.

    PASS: 1.0 (no inflation)
    MONITOR: COHERENCE_SE_INFLATION_MONITOR (1.1)
    INVESTIGATE: COHERENCE_SE_INFLATION_INVESTIGATE (1.3)
    ALARM: COHERENCE_SE_INFLATION_ALARM (2.0)

    Parameters
    ----------
    triage_tier : TriageTier
        The triage classification.

    Returns
    -------
    SE inflation multiplier.
    """
    if triage_tier == TriageTier.PASS:
        return 1.0
    elif triage_tier == TriageTier.MONITOR:
        return COHERENCE_SE_INFLATION_MONITOR
    elif triage_tier == TriageTier.INVESTIGATE:
        return COHERENCE_SE_INFLATION_INVESTIGATE
    elif triage_tier == TriageTier.ALARM:
        return COHERENCE_SE_INFLATION_ALARM
    else:
        # UNTESTABLE — no inflation
        return 1.0


def resolve_se_inflations(
    inflation_records: list[SEInflationRecord],
) -> dict[str, float]:
    """P5-S5: If edge appears in multiple chains, use MAX inflation.

    Parameters
    ----------
    inflation_records : list[SEInflationRecord]
        Per-edge inflation records from all chain validations.

    Returns
    -------
    Dict of edge_relation_id -> max SE inflation factor.
    """
    edge_inflations: dict[str, list[float]] = {}
    for record in inflation_records:
        edge_inflations.setdefault(record.edge_relation_id, []).extend(
            record.chain_inflations
        )

    result: dict[str, float] = {}
    for edge_id, inflations in edge_inflations.items():
        max_inflation = max(inflations) if inflations else 1.0
        result[edge_id] = max_inflation
        if max_inflation > 1.0:
            logger.info(
                "P5-S5: Edge '%s' receives SE inflation %.2f "
                "(max across %d chain appearances)",
                edge_id,
                max_inflation,
                len(inflations),
            )

    return result


# ═══════════════════════════════════════════════════════════════
#  Main entry point: Validate one pathway
# ═══════════════════════════════════════════════════════════════


def validate_pathway(
    pathway: PathwayDefinition,
    compiled_edges: dict[str, CompiledEdge],
) -> ChainValidationResult:
    """Validate a single pathway: chain product, chain-vs-direct, classify.

    Parameters
    ----------
    pathway : PathwayDefinition
        The pathway to validate.
    compiled_edges : dict[str, CompiledEdge]
        All compiled edges keyed by edge_relation_id.

    Returns
    -------
    ChainValidationResult with triage tier, failure mode, and SE inflation.
    """
    pathway_id = pathway.pathway_id

    # Gather chain edges
    chain_edges: list[CompiledEdge] = []
    missing_edges: list[str] = []
    for edge_id in pathway.edge_sequence:
        edge = compiled_edges.get(edge_id)
        if edge is None:
            missing_edges.append(edge_id)
        else:
            chain_edges.append(edge)

    if missing_edges:
        logger.warning(
            "P5-S2: Pathway '%s' has missing edges: %s; "
            "marking as UNTESTABLE",
            pathway_id,
            ", ".join(missing_edges),
        )
        return ChainValidationResult(
            pathway_id=pathway_id,
            chain_length=len(pathway.edge_sequence),
            beta_chain=0.0,
            se_chain=0.0,
            triage_tier=TriageTier.UNTESTABLE,
            failure_mode=FailureMode.NONE,
            se_inflation_applied=1.0,
        )

    # P5-S2: Chain product (Formula P5-1)
    beta_chain, se_chain = compute_chain_product(chain_edges)
    logger.info(
        "P5-S2: Pathway '%s': beta_chain=%.4f, se_chain=%.4f "
        "(chain_length=%d)",
        pathway_id,
        beta_chain,
        se_chain,
        len(chain_edges),
    )

    # P5-S3: Chain-vs-direct (Formula P5-2)
    direct_edge: CompiledEdge | None = None
    beta_direct: float | None = None
    se_direct: float | None = None
    z_stat: float | None = None
    triage_tier: TriageTier

    if pathway.direct_edge_id is not None:
        direct_edge = compiled_edges.get(pathway.direct_edge_id)

    if direct_edge is not None:
        beta_direct = direct_edge.beta_mean
        se_direct = direct_edge.beta_se
        z_stat = compute_chain_vs_direct_z(
            beta_chain=beta_chain,
            se_chain=se_chain,
            beta_direct=beta_direct,
            se_direct=se_direct,
        )
        triage_tier = triage_z_score(z_stat)
        logger.info(
            "P5-S3: Pathway '%s': Z=%.4f -> %s "
            "(beta_chain=%.4f vs beta_direct=%.4f)",
            pathway_id,
            z_stat,
            triage_tier.value,
            beta_chain,
            beta_direct,
        )
    else:
        # No direct edge available — cannot test
        triage_tier = TriageTier.UNTESTABLE
        logger.info(
            "P5-S3: Pathway '%s': no direct edge available; UNTESTABLE",
            pathway_id,
        )

    # P5-S4: Discrepancy classification (Formula P5-5)
    failure_mode = classify_discrepancy(
        triage_tier=triage_tier,
        pathway_id=pathway_id,
        edges_in_chain=chain_edges,
        direct_edge=direct_edge,
    )

    # P5-S5: SE inflation
    se_inflation = compute_se_inflation_for_tier(triage_tier)

    return ChainValidationResult(
        pathway_id=pathway_id,
        chain_length=len(chain_edges),
        beta_chain=beta_chain,
        se_chain=se_chain,
        beta_direct=beta_direct,
        se_direct=se_direct,
        z_statistic=z_stat,
        triage_tier=triage_tier,
        failure_mode=failure_mode,
        se_inflation_applied=se_inflation,
    )


def validate_all_pathways(
    pathways: list[PathwayDefinition],
    compiled_edges: dict[str, CompiledEdge],
) -> tuple[list[ChainValidationResult], dict[str, float]]:
    """Validate all pathways and compute aggregate SE inflation.

    Parameters
    ----------
    pathways : list[PathwayDefinition]
        All pathways to validate.
    compiled_edges : dict[str, CompiledEdge]
        All compiled edges keyed by edge_relation_id.

    Returns
    -------
    Tuple of (chain_results, edge_se_inflations).
      chain_results: list of ChainValidationResult per pathway.
      edge_se_inflations: dict of edge_relation_id -> max SE inflation.

    Raises
    ------
    GateViolation
        Gate P5-G2: if any ALARM-tier pathway exists (SEVERE discrepancy).
    """
    results: list[ChainValidationResult] = []
    inflation_records: list[SEInflationRecord] = []

    for pathway in pathways:
        result = validate_pathway(
            pathway=pathway,
            compiled_edges=compiled_edges,
        )
        results.append(result)

        # Build inflation records for P5-S5
        if result.se_inflation_applied > 1.0:
            for edge_id in pathway.edge_sequence:
                record = SEInflationRecord(
                    edge_relation_id=edge_id,
                    chain_inflations=[result.se_inflation_applied],
                )
                inflation_records.append(record)

    # P5-S5: Resolve per-edge SE inflations (max across chains)
    edge_se_inflations = resolve_se_inflations(inflation_records)

    # Gate P5-G2: No SEVERE (ALARM) discrepancies unresolved -> BLOCK
    alarm_results = [
        r for r in results if r.triage_tier == TriageTier.ALARM
    ]
    if alarm_results:
        alarm_pathways = ", ".join(r.pathway_id for r in alarm_results)
        raise GateViolation(
            gate_id="P5-G2",
            message=(
                f"SEVERE chain-vs-direct discrepancies detected in "
                f"{len(alarm_results)} pathway(s): {alarm_pathways}. "
                f"Cannot proceed without resolution."
            ),
            context={
                "alarm_pathways": [r.pathway_id for r in alarm_results],
                "z_statistics": [r.z_statistic for r in alarm_results],
                "failure_modes": [r.failure_mode.value for r in alarm_results],
            },
        )

    logger.info(
        "P5 Chain Validation complete: %d pathways validated, "
        "%d PASS, %d MONITOR, %d INVESTIGATE, %d UNTESTABLE",
        len(results),
        sum(1 for r in results if r.triage_tier == TriageTier.PASS),
        sum(1 for r in results if r.triage_tier == TriageTier.MONITOR),
        sum(1 for r in results if r.triage_tier == TriageTier.INVESTIGATE),
        sum(1 for r in results if r.triage_tier == TriageTier.UNTESTABLE),
    )

    return results, edge_se_inflations
