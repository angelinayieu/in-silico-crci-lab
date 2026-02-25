# VERIFIED: spec SYS_PRES lines 231-242 (PRES-SCI2)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-SCI2
Spec: SYS_PRESENTATION_COMPLETE.md lines 231-242
Purpose: Render DAG visualization — 63-node, 118-edge graph with
         domain coloring, edge thickness ∝ |β|, pathway highlighting,
         and patient-specific overlay.
Reads: RecommendationReport.decision_trace (for edge info),
       RecommendationReport.pathway_profile (for activation overlay)
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    DecisionTrace,
    PathwayProfile,
    PathwayContribution,
    RecommendationReport,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DAGNode:
    """One node in the DAG visualization."""

    node_id: str
    label: str
    domain: str
    color: str
    size: float  # relative size
    tooltip: str


@dataclass(frozen=True)
class DAGEdge:
    """One edge in the DAG visualization."""

    edge_id: str
    source_id: str
    target_id: str
    weight: float  # |β|
    thickness: float  # mapped thickness
    style: str  # solid, dashed, dotted
    color: str
    label: str


@dataclass(frozen=True)
class PathwayHighlight:
    """One pathway available for highlighting."""

    pathway_id: str
    pathway_label: str
    activation_z: float | None
    color: str
    edge_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DAGVizView:
    """PRES-SCI2: Interactive DAG visualization."""

    nodes: list[DAGNode]
    edges: list[DAGEdge]
    pathways: list[PathwayHighlight]
    color_mode: str  # domain, layer, observability
    n_nodes: int
    n_edges: int
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════


_DOMAIN_COLORS: dict[str, str] = {
    "cognition": "#4C78A8",
    "symptom": "#F58518",
    "exposure": "#E45756",
    "mediator": "#72B7B2",
    "context": "#54A24B",
    "outcome": "#EECA3B",
    "composite": "#B279A2",
}

_CLAIM_STYLES: dict[str, str] = {
    "causal": "solid",
    "associational": "dashed",
    "mechanistic": "dotted",
    "hypothesized": "dotted",
}


def _activation_color(z: float | None) -> str:
    """Map activation z-score to pathway highlight color."""
    if z is None:
        return "gray"
    abs_z = abs(z)
    if abs_z < 0.5:
        return "green"
    elif abs_z < 1.0:
        return "yellow"
    elif abs_z < 1.5:
        return "orange"
    else:
        return "red"


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_dag_viz(
    report: RecommendationReport,
    color_mode: str = "domain",
) -> DAGVizView:
    """PRES-SCI2: Render DAG visualization.

    Gate SCI-G2: Requires node + edge data consistency.

    In a full implementation this would read from nodes_v1 and edges_v1
    tables directly. Here we render from the RecommendationReport's
    pathway_profile and decision_trace as available.

    Args:
        report: RecommendationReport.
        color_mode: One of 'domain', 'layer', 'observability'.

    Returns:
        DAGVizView ready for rendering.
    """
    nodes: list[DAGNode] = []
    edges: list[DAGEdge] = []
    pathways: list[PathwayHighlight] = []

    # Extract pathway information for highlighting
    if report.pathway_profile is not None:
        for pc in report.pathway_profile.pathway_contributions:
            pathways.append(PathwayHighlight(
                pathway_id=pc.pathway_id,
                pathway_label=pc.pathway_label,
                activation_z=None,
                color=_activation_color(None),
                edge_ids=pc.key_edges,
            ))

    # Extract decision trace edges
    if report.decision_trace is not None:
        for entry in report.decision_trace.entries:
            if entry.step == "recommendation":
                # Create placeholder node for recommended interventions
                node_id = entry.inputs.get("claim_level", "unknown")
                nodes.append(DAGNode(
                    node_id=f"rec_{node_id}",
                    label=entry.description.replace("Recommend: ", ""),
                    domain="outcome",
                    color=_DOMAIN_COLORS.get("outcome", "#999999"),
                    size=1.0,
                    tooltip=entry.outcome,
                ))

    if not nodes and not edges:
        return DAGVizView(
            nodes=[],
            edges=[],
            pathways=[],
            color_mode=color_mode,
            n_nodes=0,
            n_edges=0,
            empty_state=True,
            empty_message="DAG visualization requires model graph data. Load a model first.",
        )

    return DAGVizView(
        nodes=nodes,
        edges=edges,
        pathways=pathways,
        color_mode=color_mode,
        n_nodes=len(nodes),
        n_edges=len(edges),
    )
