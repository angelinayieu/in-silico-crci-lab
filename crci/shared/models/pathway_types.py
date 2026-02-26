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

Design choices:
    - All sequence fields are tuples (not lists) to guarantee true
      immutability under frozen=True and safe hashability.
    - component_nodes is a computed @property (union of entry + intermediate
      + exit, order-preserved, deduplicated) — cannot drift out of sync.
    - is_complete defaults to None ("not yet computed") rather than True.
    - validate() enforces invariants at load time; the registry loader
      must call it before the PathwayDef enters the pipeline.
    - Use dataclasses.replace() for functional-style updates (frozen).

Reads: Nothing (type definition only)
Writes: Nothing (imported by downstream modules)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ── Constrained types ──────────────────────────────────────────
Tier = Literal[
    "mechanistic_model_implied",
    "mechanistic_emerging",
    "clinical_mediator",
]
Status = Literal["connected", "edgeless"]


@dataclass(frozen=True)
class PathwayDef:
    """Canonical pathway definition — single source of truth.

    Superset of all fields needed by:
    - chain_a (graph assembly: tier, entry/exit/intermediate nodes, edge_ids)
    - chain_b (evidence scoring: se_multiplier, expected_edge_count, status)
    - chain_c (activation detection: activation_threshold, is_sensitive)
    - runtime (profiling: pathway_id, pathway_label, component_nodes, edge_ids)

    Fields populated at different stages:
    - Core fields: from PATHWAY_REGISTRY.csv at load time
    - edge_ids: populated by chain_a from BSkeleton edge membership
    - is_complete: computed by chain_a based on edge presence (None until set)

    All sequence fields are tuples, so hashing and set-membership work safely.
    Use ``dataclasses.replace(pw, edge_ids=(...), is_complete=True)`` for
    functional-style updates.
    """

    # ── Core identity ──
    pathway_id: str
    pathway_label: str
    tier: str  # Tier literal at runtime; str for forward-compat with new tiers

    # ── Topology (from PATHWAY_REGISTRY.csv JSON columns) ──
    entry_node_ids: tuple[str, ...] = ()
    exit_node_ids: tuple[str, ...] = ()
    intermediate_node_ids: tuple[str, ...] = ()

    # ── Edge membership (populated by chain_a from BSkeleton) ──
    edge_ids: tuple[str, ...] = ()
    is_complete: bool | None = None  # None = "not yet computed by chain_a"

    # ── C4d: Pathway activation detection ──
    activation_threshold: float | None = None  # set from registry/config, not hardcoded
    is_sensitive: bool = False  # is_sensitive_pathway flag from registry

    # ── B6.5: Pathway evidence scoring (EXTENSION) ──
    se_multiplier: float = 1.0  # SE inflation from PATHWAY_REGISTRY (1.0 = high evidence)
    expected_edge_count: int = 0  # edge_count column from PATHWAY_REGISTRY.csv
    status: str = "connected"  # Status literal; str for forward-compat

    # ── Computed property ──────────────────────────────────────
    @property
    def component_nodes(self) -> tuple[str, ...]:
        """Union of entry + intermediate + exit nodes (order-preserved, deduplicated).

        This is NOT stored — it is computed on access so it can never
        drift out of sync with the constituent node lists.
        """
        seen: set[str] = set()
        result: list[str] = []
        for nid in self.entry_node_ids + self.intermediate_node_ids + self.exit_node_ids:
            if nid not in seen:
                seen.add(nid)
                result.append(nid)
        return tuple(result)

    # ── Invariant enforcement ──────────────────────────────────
    def validate(self) -> None:
        """Validate invariants. Call from registry loader at load time.

        Raises:
            ValueError: If any invariant is violated.
        """
        # 1. pathway_id must be non-empty
        if not self.pathway_id or not self.pathway_id.strip():
            raise ValueError("PathwayDef: pathway_id must be non-empty")

        # 2. No duplicate nodes within each topology list
        for name, nodes in [
            ("entry_node_ids", self.entry_node_ids),
            ("exit_node_ids", self.exit_node_ids),
            ("intermediate_node_ids", self.intermediate_node_ids),
        ]:
            if len(nodes) != len(set(nodes)):
                raise ValueError(
                    f"PathwayDef {self.pathway_id}: duplicate nodes in {name}: "
                    f"{[n for n in nodes if nodes.count(n) > 1]}"
                )

        # 3. expected_edge_count must be non-negative
        if self.expected_edge_count < 0:
            raise ValueError(
                f"PathwayDef {self.pathway_id}: expected_edge_count "
                f"must be ≥ 0, got {self.expected_edge_count}"
            )

        # 4. se_multiplier must be positive
        if self.se_multiplier <= 0:
            raise ValueError(
                f"PathwayDef {self.pathway_id}: se_multiplier "
                f"must be > 0, got {self.se_multiplier}"
            )

        # 5. activation_threshold, if set, must be in (0, 1]
        if self.activation_threshold is not None:
            if not (0.0 < self.activation_threshold <= 1.0):
                raise ValueError(
                    f"PathwayDef {self.pathway_id}: activation_threshold "
                    f"must be in (0, 1], got {self.activation_threshold}"
                )
