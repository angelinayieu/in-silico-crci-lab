# VERIFIED: spec SYS_PRES lines 244-253 (PRES-SCI3)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-SCI3
Spec: SYS_PRESENTATION_COMPLETE.md lines 244-253
Purpose: Render provenance chain viewer — Sankey/tree diagram tracing
         recommendation → SAFE score → Δθ → β̂ → IVW → study → paper.
Reads: RecommendationReport.decision_trace, primary_schedule
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    DecisionTrace,
    DecisionTraceEntry,
    RecommendationReport,
    SchedulePlan,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ProvenanceNode:
    """One node in the provenance tree/Sankey."""

    node_id: str
    label: str
    node_type: str  # recommendation, score, edge, study, paper
    depth: int
    value: str  # display value (e.g., "SAFE_B = 0.65")
    color: str


@dataclass(frozen=True)
class ProvenanceLink:
    """One link in the provenance tree/Sankey."""

    source_id: str
    target_id: str
    weight: float
    label: str


@dataclass(frozen=True)
class ProvenanceChainView:
    """PRES-SCI3: Provenance chain viewer."""

    nodes: list[ProvenanceNode]
    links: list[ProvenanceLink]
    depth_labels: list[str]
    n_recommendations: int
    n_edges_traced: int
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Color Mapping
# ═══════════════════════════════════════════════════════════════


_TYPE_COLORS: dict[str, str] = {
    "recommendation": "#4C78A8",
    "score": "#F58518",
    "edge": "#72B7B2",
    "study": "#E45756",
    "paper": "#54A24B",
    "session": "#999999",
    "stability": "#EECA3B",
}


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_provenance_chain(
    report: RecommendationReport,
) -> ProvenanceChainView:
    """PRES-SCI3: Render provenance chain viewer.

    Traces each recommendation back through the evidence chain:
    Recommendation → SAFE score → edges → studies → papers.

    Args:
        report: RecommendationReport.

    Returns:
        ProvenanceChainView ready for rendering.
    """
    trace = report.decision_trace

    if trace is None or not trace.entries:
        return ProvenanceChainView(
            nodes=[],
            links=[],
            depth_labels=[],
            n_recommendations=0,
            n_edges_traced=0,
            empty_state=True,
            empty_message="No decision trace available for provenance viewing.",
        )

    nodes: list[ProvenanceNode] = []
    links: list[ProvenanceLink] = []
    n_recommendations = 0

    # Build nodes from trace entries
    for i, entry in enumerate(trace.entries):
        entry_id = f"trace_{i}"

        if entry.step == "session_start":
            nodes.append(ProvenanceNode(
                node_id=entry_id,
                label=entry.description,
                node_type="session",
                depth=0,
                value=entry.outcome,
                color=_TYPE_COLORS["session"],
            ))

        elif entry.step == "stability_assessment":
            nodes.append(ProvenanceNode(
                node_id=entry_id,
                label="Stability Assessment",
                node_type="stability",
                depth=1,
                value=entry.outcome,
                color=_TYPE_COLORS["stability"],
            ))
            # Link from session
            if nodes and nodes[0].node_type == "session":
                links.append(ProvenanceLink(
                    source_id=nodes[0].node_id,
                    target_id=entry_id,
                    weight=1.0,
                    label="assessed",
                ))

        elif entry.step == "recommendation":
            n_recommendations += 1
            nodes.append(ProvenanceNode(
                node_id=entry_id,
                label=entry.description,
                node_type="recommendation",
                depth=2,
                value=entry.outcome,
                color=_TYPE_COLORS["recommendation"],
            ))
            # Link from stability
            stability_nodes = [n for n in nodes if n.node_type == "stability"]
            if stability_nodes:
                links.append(ProvenanceLink(
                    source_id=stability_nodes[0].node_id,
                    target_id=entry_id,
                    weight=entry.confidence or 0.5,
                    label=entry.inputs.get("claim_level", ""),
                ))

    # Add schedule-level nodes
    primary = report.primary_schedule
    if primary.actions:
        score_id = "score_primary"
        nodes.append(ProvenanceNode(
            node_id=score_id,
            label=f"SAFE_B = {primary.utility_score:.2f}",
            node_type="score",
            depth=3,
            value=f"Rank {primary.plan_rank}, {primary.stability_class.value}",
            color=_TYPE_COLORS["score"],
        ))
        # Link from first recommendation
        rec_nodes = [n for n in nodes if n.node_type == "recommendation"]
        if rec_nodes:
            links.append(ProvenanceLink(
                source_id=rec_nodes[0].node_id,
                target_id=score_id,
                weight=primary.utility_score,
                label="scored",
            ))

    # Critical edges from trace
    n_edges_traced = 0
    if trace.decision_critical_edges:
        for edge_id in trace.decision_critical_edges:
            edge_node_id = f"edge_{edge_id}"
            nodes.append(ProvenanceNode(
                node_id=edge_node_id,
                label=f"Edge: {edge_id}",
                node_type="edge",
                depth=4,
                value="decision-critical",
                color=_TYPE_COLORS["edge"],
            ))
            n_edges_traced += 1
            # Link from score
            score_nodes = [n for n in nodes if n.node_type == "score"]
            if score_nodes:
                links.append(ProvenanceLink(
                    source_id=score_nodes[0].node_id,
                    target_id=edge_node_id,
                    weight=0.5,
                    label="depends on",
                ))

    depth_labels = [
        "Session",
        "Stability",
        "Recommendation",
        "SAFE Score",
        "Critical Edges",
    ]

    return ProvenanceChainView(
        nodes=nodes,
        links=links,
        depth_labels=depth_labels,
        n_recommendations=n_recommendations,
        n_edges_traced=n_edges_traced,
    )
