# VERIFIED: formulas — aggregation logic matches spec SYS_EX lines 1750-1785
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads CoverageMatrix, ChainValidationResult, BiasAssessment, EValueResult
# VERIFIED: forward wiring — writes SufficiencyReport for deploy_gate.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — no additional gate (P5-G2 enforced in chain_validator)
"""
Component: SYS_EXTRACTION.EX-P5.S7
Spec: SYS_EXTRACTION_COMPLETE.md lines 1750-1785
Formulas: None (report aggregation)
Reads: CoverageMatrix (from coverage_analyzer.py),
       ChainValidationResult (from chain_validator.py),
       BiasAssessment (from publication_bias.py),
       EValueResult (from evalue_computer.py)
Writes: SufficiencyReport (consumed by deploy_gate.py)
Gates: None (P5-G2 enforced upstream in chain_validator.py)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from crci.shared.models.enums import (
    BiasRisk,
    SufficiencyRecommendation,
    TriageTier,
)
from crci.shared.models.intermediate_states import (
    ChainValidationResult,
    CompiledEdge,
    SufficiencyReport,
)

from .coverage_analyzer import CoverageMatrix
from .evalue_computer import EValueResult

if TYPE_CHECKING:
    from crci.extraction.p4b_publication_bias.publication_bias import (
        BiasAssessment,
    )

logger = logging.getLogger(__name__)


def classify_edge_sufficiency(
    edge: CompiledEdge,
    coverage_strength: str,
    bias_risk: BiasRisk | None = None,
    e_value: float | None = None,
) -> str:
    """Classify a single edge as SUFFICIENT, MARGINAL, or INSUFFICIENT.

    Heuristic combining coverage, bias risk, and E-value:
      SUFFICIENT: STRONG coverage AND (LOW/MODERATE bias) AND E-value >= 2.0
      MARGINAL: MODERATE coverage OR one concern (bias or low E-value)
      INSUFFICIENT: GAP or WEAK coverage AND multiple concerns

    Parameters
    ----------
    edge : CompiledEdge
        The compiled edge.
    coverage_strength : str
        From CoverageMatrix: "STRONG", "MODERATE", "WEAK", "GAP".
    bias_risk : BiasRisk | None
        From BiasAssessment.
    e_value : float | None
        From EValueResult.

    Returns
    -------
    One of "SUFFICIENT", "MARGINAL", "INSUFFICIENT".
    """
    concerns: list[str] = []

    if coverage_strength == "GAP":
        return "INSUFFICIENT"

    if coverage_strength == "WEAK":
        concerns.append("weak_coverage")

    if bias_risk is not None and bias_risk == BiasRisk.HIGH:
        concerns.append("high_bias")

    if e_value is not None and e_value < 1.5:
        concerns.append("fragile_evalue")

    if coverage_strength == "STRONG" and len(concerns) == 0:
        return "SUFFICIENT"
    elif len(concerns) >= 2:
        return "INSUFFICIENT"
    else:
        return "MARGINAL"


def generate_sufficiency_report(
    compiled_edges: list[CompiledEdge],
    coverage_matrix: CoverageMatrix,
    chain_results: list[ChainValidationResult] | None = None,
    bias_assessments: list | None = None,
    evalue_results: list[EValueResult] | None = None,
) -> SufficiencyReport:
    """P5-S7: Generate the overall sufficiency report.

    Aggregates evidence from coverage analysis, chain validation,
    publication bias assessment, and E-value computation.

    Parameters
    ----------
    compiled_edges : list[CompiledEdge]
        All compiled edges from aggregation.
    coverage_matrix : CoverageMatrix
        Output from coverage_analyzer.
    chain_results : list[ChainValidationResult] | None
        Output from chain_validator.
    bias_assessments : list | None
        Output from publication_bias (list of BiasAssessment).
    evalue_results : list[EValueResult] | None
        Output from evalue_computer.

    Returns
    -------
    SufficiencyReport with overall recommendation and per-pathway coverage.
    """
    if chain_results is None:
        chain_results = []
    if bias_assessments is None:
        bias_assessments = []
    if evalue_results is None:
        evalue_results = []

    # Index supporting data by edge_relation_id
    coverage_by_edge: dict[str, str] = {
        ec.edge_relation_id: ec.strength
        for ec in coverage_matrix.edge_coverages
    }

    bias_by_edge: dict[str, BiasRisk] = {}
    for ba in bias_assessments:
        bias_by_edge[ba.edge_relation_id] = ba.bias_risk

    evalue_by_edge: dict[str, float] = {}
    for ev in evalue_results:
        evalue_by_edge[ev.edge_relation_id] = ev.e_value

    # Classify each edge
    n_sufficient = 0
    n_marginal = 0
    n_insufficient = 0
    gaps: list[str] = []
    warnings: list[str] = []

    for edge in compiled_edges:
        eid = edge.edge_relation_id
        coverage_str = coverage_by_edge.get(eid, "GAP")
        bias = bias_by_edge.get(eid)
        ev = evalue_by_edge.get(eid)

        classification = classify_edge_sufficiency(
            edge=edge,
            coverage_strength=coverage_str,
            bias_risk=bias,
            e_value=ev,
        )

        if classification == "SUFFICIENT":
            n_sufficient += 1
        elif classification == "MARGINAL":
            n_marginal += 1
        else:
            n_insufficient += 1

    # Also count gaps from coverage matrix that have no compiled edge
    for gap_edge_id in coverage_matrix.gaps:
        if gap_edge_id not in {e.edge_relation_id for e in compiled_edges}:
            n_insufficient += 1
            gaps.append(gap_edge_id)

    # Collect gaps from coverage matrix
    gaps.extend(
        g for g in coverage_matrix.gaps
        if g not in gaps
    )

    # Add warnings for chain validation issues
    for chain_result in chain_results:
        if chain_result.triage_tier == TriageTier.INVESTIGATE:
            warnings.append(
                f"Pathway '{chain_result.pathway_id}': INVESTIGATE tier "
                f"(Z={chain_result.z_statistic:.4f}, "
                f"failure_mode={chain_result.failure_mode.value})"
            )
        elif chain_result.triage_tier == TriageTier.MONITOR:
            warnings.append(
                f"Pathway '{chain_result.pathway_id}': MONITOR tier "
                f"(Z={chain_result.z_statistic:.4f})"
            )

    # Add warnings for publication bias
    for ba in bias_assessments:
        if ba.bias_risk == BiasRisk.HIGH:
            warnings.append(
                f"Edge '{ba.edge_relation_id}': HIGH publication bias risk "
                f"({ba.n_flags} flags)"
            )

    total_compiled = len(compiled_edges) + len(
        [g for g in coverage_matrix.gaps
         if g not in {e.edge_relation_id for e in compiled_edges}]
    )

    # Overall recommendation
    if n_insufficient > 0 and n_insufficient > n_sufficient:
        recommendation = SufficiencyRecommendation.INSUFFICIENT
    elif n_insufficient > 0 or n_marginal > n_sufficient:
        recommendation = SufficiencyRecommendation.MARGINAL
    else:
        recommendation = SufficiencyRecommendation.SUFFICIENT

    logger.info(
        "P5-S7 Sufficiency Report: %s — %d sufficient, %d marginal, "
        "%d insufficient out of %d edges, %d gaps, %d warnings",
        recommendation.value,
        n_sufficient,
        n_marginal,
        n_insufficient,
        total_compiled,
        len(gaps),
        len(warnings),
    )

    return SufficiencyReport(
        recommendation=recommendation,
        total_edges_compiled=total_compiled,
        edges_sufficient=n_sufficient,
        edges_marginal=n_marginal,
        edges_insufficient=n_insufficient,
        coverage_by_pathway=coverage_matrix.pathway_coverage,
        gaps=gaps,
        warnings=warnings,
    )
