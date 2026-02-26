"""
Component: Shared — Canonical Pathway Definition
Purpose: Single source of truth for PathwayDef used across:
    - ALG-A (graph_object.py — graph assembly, pathway map)
    - ALG-B (pathway_evidence_scorer.py — evidence density scoring)
    - ALG-C (modifier_application.py — pathway activation detection)
    - Runtime (pathway_profiler.py — pathway z-score profiling)

Previously, three independent PathwayDef types existed in graph_object.py,
modifier_application.py, and pathway_profiler.py. This module consolidates
them into a single canonical type with a superset of all required fields.

Reads: Nothing (type definition only)
Writes: Nothing (imported by downstream modules)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PathwayDef:
    """Canonical pathway definition — single source of truth.

    Superset of all fields needed by:
    - chain_a (graph assembly: tier, entry/exit/intermediate nodes, edge_ids)
    - chain_b (evidence scoring: se_multiplier, edge_count_registry, status)
    - chain_c (activation detection: activation_threshold, is_sensitive)
    - runtime (profiling: pathway_id, pathway_label, component_nodes, edge_ids)

    Fields populated at different stages:
    - Core fields: from PATHWAY_REGISTRY.csv at load time
    - edge_ids: populated by chain_a from BSkeleton edge membership
    - is_complete: computed by chain_a based on edge presence
    """

    # ── Core identity ──
    pathway_id: str
    pathway_label: str
    tier: str  # mechanistic_model_implied, mechanistic_emerging, clinical_mediator, etc.

    # ── Topology (from PATHWAY_REGISTRY.csv JSON columns) ──
    entry_node_ids: list[str] = field(default_factory=list)
    exit_node_ids: list[str] = field(default_factory=list)
    intermediate_node_ids: list[str] = field(default_factory=list)
    component_nodes: list[str] = field(default_factory=list)

    # ── Edge membership (populated by chain_a from BSkeleton) ──
    edge_ids: list[str] = field(default_factory=list)
    is_complete: bool = True  # False if no constituent edges found in skeleton

    # ── C4d: Pathway activation detection ──
    activation_threshold: float = 0.5  # A(P) > τ_P for activation
    is_sensitive: bool = False  # is_sensitive_pathway flag from registry

    # ── B6.5: Pathway evidence scoring (EXTENSION) ──
    se_multiplier: float = 1.0  # SE inflation from PATHWAY_REGISTRY (1.0 = high evidence)
    edge_count_registry: int = 0  # edge_count column from PATHWAY_REGISTRY.csv
    status: str = "connected"  # connected, edgeless — from PATHWAY_REGISTRY.csv
