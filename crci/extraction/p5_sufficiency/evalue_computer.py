# VERIFIED: formulas [P5-4] match spec SYS_EX lines 1720-1750
# VERIFIED: imports — all modules exist (config.py, intermediate_states.py)
# VERIFIED: backward wiring — reads CompiledEdge from p4_aggregation
# VERIFIED: forward wiring — writes EValueResult for sufficiency_reporter.py
# VERIFIED: no hardcoded formula parameters — EVALUE_RR_CONVERSION_FACTOR from config
# VERIFIED: gates — no gate for this subsystem
"""
Component: SYS_EXTRACTION.EX-P5.S6
Spec: SYS_EXTRACTION_COMPLETE.md lines 1720-1750
Formulas: P5-4 (E-value computation)
Reads: CompiledEdge (from p4_aggregation)
Writes: EValueResult (consumed by sufficiency_reporter.py)
Gates: None
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from crci.shared.config import EVALUE_RR_CONVERSION_FACTOR
from crci.shared.models.intermediate_states import CompiledEdge

logger = logging.getLogger(__name__)


@dataclass
class EValueResult:
    """Result of E-value computation for an edge."""

    edge_relation_id: str
    beta: float
    rr: float  # RR = exp(EVALUE_RR_CONVERSION_FACTOR * |beta|)
    e_value: float  # E = RR + sqrt(RR * (RR - 1))
    interpretation: str  # human-readable strength assessment


def compute_evalue(
    beta: float,
) -> tuple[float, float]:
    """Formula P5-4: Compute E-value for unmeasured confounding sensitivity.

    RR = exp(EVALUE_RR_CONVERSION_FACTOR * |beta|)
    E-value = RR + sqrt(RR * (RR - 1))

    The E-value represents the minimum strength of association (on the
    risk ratio scale) that an unmeasured confounder would need with both
    the treatment and outcome to fully explain away the observed effect.

    Parameters
    ----------
    beta : float
        Standardized effect size.

    Returns
    -------
    Tuple of (rr, e_value).
    """
    # Formula P5-4: RR = exp(0.91 * |beta|)
    abs_beta = abs(beta)
    rr = math.exp(EVALUE_RR_CONVERSION_FACTOR * abs_beta)

    # Formula P5-4: E-value = RR + sqrt(RR * (RR - 1))
    if rr < 1.0:
        # RR < 1 should not happen with exp(positive), but guard against
        # numerical issues
        e_value = 1.0
    else:
        e_value = rr + math.sqrt(rr * (rr - 1.0))

    return rr, e_value


def interpret_evalue(e_value: float) -> str:
    """Provide human-readable interpretation of E-value strength.

    Parameters
    ----------
    e_value : float
        The computed E-value.

    Returns
    -------
    Interpretation string.
    """
    if e_value >= 3.0:
        return "ROBUST: Large E-value; substantial unmeasured confounding needed to explain away"
    elif e_value >= 2.0:
        return "MODERATE: Moderate E-value; meaningful confounding could explain away"
    elif e_value >= 1.5:
        return "WEAK: Small E-value; modest confounding could explain away"
    else:
        return "FRAGILE: Very small E-value; trivial confounding could explain away"


def compute_evalue_for_edge(
    edge: CompiledEdge,
) -> EValueResult:
    """Compute E-value for a single compiled edge.

    Parameters
    ----------
    edge : CompiledEdge
        A fully compiled edge from the aggregation phase.

    Returns
    -------
    EValueResult with RR, E-value, and interpretation.
    """
    rr, e_value = compute_evalue(beta=edge.beta_mean)
    interpretation = interpret_evalue(e_value)

    logger.info(
        "P5-S6 E-value for edge '%s': beta=%.4f, RR=%.4f, "
        "E-value=%.4f (%s)",
        edge.edge_relation_id,
        edge.beta_mean,
        rr,
        e_value,
        interpretation.split(":")[0],
    )

    return EValueResult(
        edge_relation_id=edge.edge_relation_id,
        beta=edge.beta_mean,
        rr=rr,
        e_value=e_value,
        interpretation=interpretation,
    )


def compute_evalues_batch(
    edges: list[CompiledEdge],
) -> list[EValueResult]:
    """Compute E-values for a batch of compiled edges.

    Parameters
    ----------
    edges : list[CompiledEdge]
        All compiled edges.

    Returns
    -------
    List of EValueResult, one per edge.
    """
    results: list[EValueResult] = []

    for edge in edges:
        result = compute_evalue_for_edge(edge)
        results.append(result)

    # Summary statistics
    if results:
        avg_evalue = sum(r.e_value for r in results) / len(results)
        min_evalue = min(r.e_value for r in results)
        fragile_count = sum(
            1 for r in results if r.e_value < 1.5
        )
        logger.info(
            "P5-S6 E-value batch: %d edges, avg=%.4f, min=%.4f, "
            "%d fragile (E < 1.5)",
            len(results),
            avg_evalue,
            min_evalue,
            fragile_count,
        )

    return results
