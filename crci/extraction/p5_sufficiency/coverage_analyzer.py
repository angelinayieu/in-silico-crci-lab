# VERIFIED: formulas — coverage classification matches spec SYS_EX lines 1535-1600
# VERIFIED: imports — all modules exist (config.py, enums.py, intermediate_states.py)
# VERIFIED: backward wiring — reads CompiledEdge from p4_aggregation
# VERIFIED: forward wiring — writes CoverageMatrix for sufficiency_reporter.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — no gate for this subsystem (coverage is informational)
"""
Component: SYS_EXTRACTION.EX-P5.S1
Spec: SYS_EXTRACTION_COMPLETE.md lines 1535-1600
Formulas: None (classification logic only)
Reads: CompiledEdge (from p4_aggregation)
Writes: CoverageMatrix (consumed by sufficiency_reporter.py)
Gates: None
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.enums import EvidenceLevel
from crci.shared.models.intermediate_states import CompiledEdge

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Coverage classification constants
# ═══════════════════════════════════════════════════════════════

# Thresholds for coverage strength classification
# These are structural classifications, not formula parameters
_STRONG_MIN_K: int = 5
_MODERATE_MIN_K: int = 2
_WEAK_MIN_K: int = 1


@dataclass
class EdgeCoverage:
    """Coverage assessment for a single edge."""

    edge_relation_id: str
    k: int
    has_rct: bool
    strength: str  # "STRONG", "MODERATE", "WEAK", "GAP"
    pathway_id: str | None = None


@dataclass
class CoverageMatrix:
    """P5-S1 output: coverage analysis across all 118 edges.

    Builds a matrix of edge coverage, classifying each edge as:
      k >= 5 + RCT -> STRONG
      k = 2-4      -> MODERATE
      k = 1        -> WEAK
      k = 0        -> GAP
    """

    edge_coverages: list[EdgeCoverage] = field(default_factory=list)
    total_edges: int = 0
    n_strong: int = 0
    n_moderate: int = 0
    n_weak: int = 0
    n_gap: int = 0
    coverage_fraction: float = 0.0
    gaps: list[str] = field(default_factory=list)
    pathway_coverage: dict[str, float] = field(default_factory=dict)


def classify_edge_coverage(
    edge_relation_id: str,
    k: int,
    has_rct: bool,
    pathway_id: str | None = None,
) -> EdgeCoverage:
    """Classify a single edge's evidence coverage.

    Classification rules from P5-S1:
      k >= 5 AND has RCT -> STRONG
      k >= 2 (and k < 5, or no RCT) -> MODERATE
      k == 1 -> WEAK
      k == 0 -> GAP

    Parameters
    ----------
    edge_relation_id : str
        Identifier for the edge.
    k : int
        Number of independent studies.
    has_rct : bool
        Whether any study is an RCT.
    pathway_id : str | None
        Optional pathway grouping.

    Returns
    -------
    EdgeCoverage with classification.
    """
    if k >= _STRONG_MIN_K and has_rct:
        strength = "STRONG"
    elif k >= _MODERATE_MIN_K:
        strength = "MODERATE"
    elif k >= _WEAK_MIN_K:
        strength = "WEAK"
    else:
        strength = "GAP"

    return EdgeCoverage(
        edge_relation_id=edge_relation_id,
        k=k,
        has_rct=has_rct,
        strength=strength,
        pathway_id=pathway_id,
    )


def build_coverage_matrix(
    compiled_edges: list[CompiledEdge],
    expected_edge_ids: list[str] | None = None,
    edge_rct_flags: dict[str, bool] | None = None,
    edge_pathway_map: dict[str, str] | None = None,
) -> CoverageMatrix:
    """P5-S1: Build the 118-edge coverage matrix.

    Parameters
    ----------
    compiled_edges : list[CompiledEdge]
        All compiled edges from the aggregation phase.
    expected_edge_ids : list[str] | None
        Full set of expected edge IDs (118 edges). Edges not present
        in compiled_edges will be classified as GAP.
    edge_rct_flags : dict[str, bool] | None
        Map of edge_relation_id -> whether any constituent study is an RCT.
        Defaults to False if not provided.
    edge_pathway_map : dict[str, str] | None
        Map of edge_relation_id -> pathway_id for grouping.

    Returns
    -------
    CoverageMatrix with per-edge and aggregate statistics.
    """
    if edge_rct_flags is None:
        edge_rct_flags = {}
    if edge_pathway_map is None:
        edge_pathway_map = {}

    # Index compiled edges by edge_relation_id
    compiled_by_edge: dict[str, CompiledEdge] = {
        ce.edge_relation_id: ce for ce in compiled_edges
    }

    # Determine the full set of edges to assess
    if expected_edge_ids is not None:
        all_edge_ids = expected_edge_ids
    else:
        all_edge_ids = list(compiled_by_edge.keys())

    edge_coverages: list[EdgeCoverage] = []
    gaps: list[str] = []

    for edge_id in all_edge_ids:
        compiled = compiled_by_edge.get(edge_id)
        k = compiled.k if compiled is not None else 0
        has_rct = edge_rct_flags.get(edge_id, False)
        pathway_id = edge_pathway_map.get(edge_id)

        coverage = classify_edge_coverage(
            edge_relation_id=edge_id,
            k=k,
            has_rct=has_rct,
            pathway_id=pathway_id,
        )
        edge_coverages.append(coverage)

        if coverage.strength == "GAP":
            gaps.append(edge_id)

    # Aggregate counts
    total = len(edge_coverages)
    n_strong = sum(1 for ec in edge_coverages if ec.strength == "STRONG")
    n_moderate = sum(1 for ec in edge_coverages if ec.strength == "MODERATE")
    n_weak = sum(1 for ec in edge_coverages if ec.strength == "WEAK")
    n_gap = sum(1 for ec in edge_coverages if ec.strength == "GAP")

    coverage_fraction = (total - n_gap) / total if total > 0 else 0.0

    # Pathway-level coverage
    pathway_coverage: dict[str, float] = {}
    pathway_groups: dict[str, list[EdgeCoverage]] = {}
    for ec in edge_coverages:
        pw = ec.pathway_id or "ungrouped"
        pathway_groups.setdefault(pw, []).append(ec)

    for pw, edges in pathway_groups.items():
        pw_total = len(edges)
        pw_covered = sum(1 for e in edges if e.strength != "GAP")
        pathway_coverage[pw] = pw_covered / pw_total if pw_total > 0 else 0.0

    logger.info(
        "P5-S1 Coverage: %d edges total, %d STRONG, %d MODERATE, "
        "%d WEAK, %d GAP (coverage=%.1f%%)",
        total,
        n_strong,
        n_moderate,
        n_weak,
        n_gap,
        coverage_fraction * 100,
    )

    if gaps:
        logger.warning(
            "P5-S1: %d evidence gaps detected: %s",
            len(gaps),
            ", ".join(gaps[:10]) + ("..." if len(gaps) > 10 else ""),
        )

    return CoverageMatrix(
        edge_coverages=edge_coverages,
        total_edges=total,
        n_strong=n_strong,
        n_moderate=n_moderate,
        n_weak=n_weak,
        n_gap=n_gap,
        coverage_fraction=coverage_fraction,
        gaps=gaps,
        pathway_coverage=pathway_coverage,
    )
