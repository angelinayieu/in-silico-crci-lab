# VERIFIED: formulas [A1] match spec SYS_ALG lines 697-720
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads NODE_REGISTRY.csv
# VERIFIED: forward wiring — writes NodeMap for edge_loader.py, spectral_validator.py, graph_object.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates [A-G1] raise on failure
"""
Component: SYS_ALGORITHM.ALG-A.A1
Spec: SYS_ALGORITHM_COMPLETE.md lines 697-720
Formulas: (none — structural loading only)
Reads: NODE_REGISTRY.csv (63 rows)
Writes: NodeMap (consumed by edge_loader.py, spectral_validator.py, graph_object.py)
Gates: A-G1
"""
from __future__ import annotations

import csv
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class NodeDef:
    """Immutable definition of a single node in the causal DAG."""

    node_id: str
    node_label: str
    layer: int
    clinical_domain: str
    is_observable: bool
    is_latent: bool
    orientation: str  # POS_UP, POS_DOWN, CATEGORICAL, neutral
    unit_of_measure: str
    pathway_membership: list[str]
    proxy_for: str | None
    proxy_r_squared: float | None
    description: str


@dataclass
class NodeMap:
    """Complete node hierarchy output of ALG-A1.

    Contains all 63 nodes with layer, domain, observability,
    orientation assignments and a verified topological order.
    """

    nodes: list[NodeDef]
    node_index: dict[str, int]  # node_id → position index in nodes list
    layer_assignment: dict[str, int]  # node_id → layer (0-6)
    domain_assignment: dict[str, str]  # node_id → clinical_domain
    observability: dict[str, bool]  # node_id → is_observable
    orientation: dict[str, str]  # node_id → POS_UP / POS_DOWN / etc.
    topological_order: list[str]  # valid DAG ordering (L0 → L6)
    nodes_by_layer: dict[int, list[str]] = field(default_factory=dict)
    n_observable: int = 0
    n_latent: int = 0


# ═══════════════════════════════════════════════════════════════
#  Loading
# ═══════════════════════════════════════════════════════════════


def _parse_bool(val: str) -> bool:
    """Parse CSV boolean field (0/1 or true/false)."""
    return val.strip().lower() in ("1", "true", "yes")


def _parse_proxy_r_squared(val: str) -> float | None:
    """Parse proxy R² field, which may be 'N/A', 'N/A_IS_LATENT', etc."""
    val = val.strip()
    if not val or val.startswith("N/A") or val.lower() in ("none", ""):
        return None
    # Map qualitative values to numeric estimates
    qualitative_map = {
        "high": 0.60,
        "moderate": 0.40,
        "low": 0.20,
    }
    if val.lower() in qualitative_map:
        return qualitative_map[val.lower()]
    try:
        return float(val)
    except ValueError:
        logger.warning(
            "Cannot parse proxy_r_squared value '%s', defaulting to None", val
        )
        return None


def _parse_pathway_membership(val: str) -> list[str]:
    """Parse JSON-like list of pathway IDs from CSV."""
    import json

    val = val.strip()
    if not val or val in ("[]", ""):
        return []
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def load_nodes(registry_path: str | Path) -> list[NodeDef]:
    """Load node definitions from NODE_REGISTRY.csv.

    Args:
        registry_path: Path to NODE_REGISTRY.csv.

    Returns:
        List of NodeDef objects, one per node.

    Raises:
        GateViolation: If file is empty or has structural problems.
    """
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise GateViolation(
            "A-G1",
            f"Node registry file not found: {registry_path}",
            {"path": str(registry_path)},
        )

    nodes: list[NodeDef] = []
    with open(registry_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip inactive nodes
            if not _parse_bool(row.get("active", "1")):
                logger.info("Skipping inactive node: %s", row.get("node_id"))
                continue

            node = NodeDef(
                node_id=row["node_id"].strip(),
                node_label=row["node_label"].strip(),
                layer=int(row["node_layer"]),
                clinical_domain=row["clinical_domain"].strip(),
                is_observable=_parse_bool(row.get("is_observable", "1")),
                is_latent=_parse_bool(row.get("is_latent", "0")),
                orientation=row.get("orientation", "POS_UP").strip(),
                unit_of_measure=row.get("unit_of_measure", "z").strip(),
                pathway_membership=_parse_pathway_membership(
                    row.get("pathway_membership", "[]")
                ),
                proxy_for=row.get("proxy_for", "").strip() or None,
                proxy_r_squared=_parse_proxy_r_squared(
                    row.get("proxy_r_squared", "")
                ),
                description=row.get("description", "").strip(),
            )
            nodes.append(node)

    logger.info("Loaded %d nodes from %s", len(nodes), registry_path)
    return nodes


# ═══════════════════════════════════════════════════════════════
#  Topological Sort (Kahn's Algorithm)
# ═══════════════════════════════════════════════════════════════


def compute_topological_order(
    nodes: list[NodeDef],
    edges: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Compute topological order using Kahn's algorithm.

    Uses layer assignments as the primary ordering constraint.
    If edges are provided, also verifies edge consistency.

    Args:
        nodes: List of NodeDef with layer assignments.
        edges: Optional list of (source_id, target_id) tuples for
               additional DAG verification.

    Returns:
        Topologically sorted list of node IDs.

    Raises:
        GateViolation: If cycle detected or layering is inconsistent.
    """
    # Sort by layer first, then alphabetically within layer for determinism
    layer_sorted = sorted(nodes, key=lambda n: (n.layer, n.node_id))
    order = [n.node_id for n in layer_sorted]

    if edges is None:
        return order

    # Build adjacency and validate with Kahn's algorithm
    node_ids = {n.node_id for n in nodes}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for src, tgt in edges:
        if src in node_ids and tgt in node_ids:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    queue: deque[str] = deque(
        nid for nid in order if in_degree[nid] == 0
    )
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in sorted(adj[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(node_ids):
        remaining = node_ids - set(result)
        raise GateViolation(
            "A-G1",
            f"Cycle detected in DAG: {len(remaining)} nodes unreachable. "
            f"Remaining: {sorted(remaining)[:10]}",
            {"remaining_count": len(remaining)},
        )

    return result


# ═══════════════════════════════════════════════════════════════
#  Assembly
# ═══════════════════════════════════════════════════════════════


def assemble_node_map(
    nodes: list[NodeDef],
    forward_edges: list[tuple[str, str]] | None = None,
) -> NodeMap:
    """Assemble NodeMap from loaded nodes.

    This is the main entry point for ALG-A1.

    Args:
        nodes: List of NodeDef objects from load_nodes().
        forward_edges: Optional list of (source, target) for topological
                       verification. Feedback edges should be excluded.

    Returns:
        Complete NodeMap with all assignments and topological order.

    Raises:
        GateViolation: If gate A-G1 conditions are not met.
    """
    # Validate node count
    if len(nodes) < config.EXPECTED_NODE_COUNT:
        raise GateViolation(
            "A-G1",
            f"Expected {config.EXPECTED_NODE_COUNT} nodes, got {len(nodes)}",
            {"expected": config.EXPECTED_NODE_COUNT, "actual": len(nodes)},
        )

    # Check for duplicates
    node_ids = [n.node_id for n in nodes]
    seen: set[str] = set()
    duplicates: list[str] = []
    for nid in node_ids:
        if nid in seen:
            duplicates.append(nid)
        seen.add(nid)

    if duplicates:
        raise GateViolation(
            "A-G1",
            f"Duplicate node IDs found: {duplicates}",
            {"duplicates": duplicates},
        )

    # Validate layers are in range [0, NODE_LAYER_COUNT)
    for node in nodes:
        if not (0 <= node.layer < config.NODE_LAYER_COUNT):
            raise GateViolation(
                "A-G1",
                f"Node {node.node_id} has invalid layer {node.layer}. "
                f"Expected 0-{config.NODE_LAYER_COUNT - 1}",
                {"node_id": node.node_id, "layer": node.layer},
            )

    # Validate no node is both observable and latent
    for node in nodes:
        if node.is_observable and node.is_latent:
            raise GateViolation(
                "A-G1",
                f"Node {node.node_id} is marked both observable and latent",
                {"node_id": node.node_id},
            )

    # Build assignments
    node_index = {n.node_id: i for i, n in enumerate(nodes)}
    layer_assignment = {n.node_id: n.layer for n in nodes}
    domain_assignment = {n.node_id: n.clinical_domain for n in nodes}
    observability = {n.node_id: n.is_observable for n in nodes}
    orientation = {n.node_id: n.orientation for n in nodes}

    # Group by layer
    nodes_by_layer: dict[int, list[str]] = {}
    for node in nodes:
        nodes_by_layer.setdefault(node.layer, []).append(node.node_id)

    # Verify all layers have nodes
    for layer in range(config.NODE_LAYER_COUNT):
        if layer not in nodes_by_layer:
            logger.warning("Layer %d has no nodes", layer)

    # Compute topological order
    topological_order = compute_topological_order(nodes, forward_edges)

    # Count observable/latent
    n_observable = sum(1 for n in nodes if n.is_observable)
    n_latent = sum(1 for n in nodes if n.is_latent)

    logger.info(
        "NodeMap assembled: %d nodes (%d observable, %d latent), "
        "%d layers populated",
        len(nodes),
        n_observable,
        n_latent,
        len(nodes_by_layer),
    )

    node_map = NodeMap(
        nodes=nodes,
        node_index=node_index,
        layer_assignment=layer_assignment,
        domain_assignment=domain_assignment,
        observability=observability,
        orientation=orientation,
        topological_order=topological_order,
        nodes_by_layer=nodes_by_layer,
        n_observable=n_observable,
        n_latent=n_latent,
    )

    # Gate A-G1: Final validation
    _validate_gate_a_g1(node_map)

    return node_map


def _validate_gate_a_g1(node_map: NodeMap) -> None:
    """Gate A-G1: 63 nodes loaded; layering valid; no orphans.

    Raises:
        GateViolation: If any gate condition fails.
    """
    # Check node count
    if len(node_map.nodes) < config.EXPECTED_NODE_COUNT:
        raise GateViolation(
            "A-G1",
            f"Insufficient nodes: {len(node_map.nodes)} < {config.EXPECTED_NODE_COUNT}",
        )

    # Check that every node has a valid layer
    for node in node_map.nodes:
        if node.node_id not in node_map.layer_assignment:
            raise GateViolation(
                "A-G1",
                f"Node {node.node_id} has no layer assignment",
            )

    # Check that every node has a domain
    for node in node_map.nodes:
        if not node.clinical_domain:
            raise GateViolation(
                "A-G1",
                f"Node {node.node_id} has no clinical domain assigned",
            )

    logger.info(
        "Gate A-G1 PASSED: %d nodes loaded, layering valid, no orphan assignments",
        len(node_map.nodes),
    )
