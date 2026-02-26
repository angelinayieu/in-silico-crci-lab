# VERIFIED: imports — csv, json, pathlib (stdlib); chain_validator (local)
# VERIFIED: backward wiring — reads PATHWAY_REGISTRY.csv, EDGE_REGISTRY.csv
# VERIFIED: forward wiring — writes list[PathwayDefinition] for chain_validator
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P5.PATHWAY_LOADER
Spec: SYS_EXTRACTION_COMPLETE.md (P5 chain validation setup)
Purpose: Load PathwayDefinition objects from PATHWAY_REGISTRY.csv and
         EDGE_REGISTRY.csv so that P5 chain validation actually runs.
         Previously, pathways were always an empty list (DW#4 dead wire).
Reads: registries/PATHWAY_REGISTRY.csv, registries/EDGE_REGISTRY.csv
Writes: list[PathwayDefinition] (consumed by chain_validator.validate_all_pathways)
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from crci.extraction.p5_sufficiency.chain_validator import PathwayDefinition

logger = logging.getLogger(__name__)

# Default registry location (project root / registries/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PATHWAY_CSV = _PROJECT_ROOT / "registries" / "PATHWAY_REGISTRY.csv"
_DEFAULT_EDGE_CSV = _PROJECT_ROOT / "registries" / "EDGE_REGISTRY.csv"

# Safety limit: max simple paths to enumerate per pathway to prevent
# combinatorial explosion in densely-connected pathways.
_MAX_PATHS_PER_PATHWAY = 50


def load_pathway_definitions(
    pathway_csv: Path | None = None,
    edge_csv: Path | None = None,
) -> list[PathwayDefinition]:
    """Load PathwayDefinition objects from registry CSVs.

    For each *connected* pathway in PATHWAY_REGISTRY.csv:
      1. Collect edges from EDGE_REGISTRY.csv whose ``primary_pathway``
         matches the pathway_id.
      2. Build a directed graph from those edges.
      3. Enumerate simple paths from each entry node to each exit node.
      4. Create one PathwayDefinition per distinct path, with
         ``edge_sequence`` being the ordered edge_relation_ids along the
         path and ``direct_edge_id`` set when a single-edge shortcut
         from entry→exit exists.

    Parameters
    ----------
    pathway_csv : Path | None
        Override path to PATHWAY_REGISTRY.csv. Uses default if None.
    edge_csv : Path | None
        Override path to EDGE_REGISTRY.csv. Uses default if None.

    Returns
    -------
    list[PathwayDefinition]
        One definition per entry→exit simple path, across all pathways.
    """
    pathway_csv = pathway_csv or _DEFAULT_PATHWAY_CSV
    edge_csv = edge_csv or _DEFAULT_EDGE_CSV

    if not pathway_csv.exists():
        logger.warning(
            "PATHWAY_REGISTRY.csv not found at %s; returning empty list",
            pathway_csv,
        )
        return []
    if not edge_csv.exists():
        logger.warning(
            "EDGE_REGISTRY.csv not found at %s; returning empty list",
            edge_csv,
        )
        return []

    # ── Load edge registry ──
    edges_by_pathway: dict[str, list[dict[str, str]]] = {}
    all_edges: dict[str, dict[str, str]] = {}
    with open(edge_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row["edge_relation_id"]
            all_edges[eid] = row
            pw = row.get("primary_pathway", "")
            if pw:
                edges_by_pathway.setdefault(pw, []).append(row)

    # ── Load pathway registry ──
    pathways_raw: list[dict[str, Any]] = []
    with open(pathway_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pathways_raw.append(row)

    definitions: list[PathwayDefinition] = []

    for pw_row in pathways_raw:
        pw_id = pw_row["pathway_id"]
        status = pw_row.get("status", "")
        active = pw_row.get("active", "1")

        # Skip edgeless or inactive pathways
        if status == "edgeless" or active == "0":
            logger.debug(
                "Skipping pathway %s (status=%s, active=%s)",
                pw_id, status, active,
            )
            continue

        # Parse node lists
        try:
            entry_nodes = set(json.loads(pw_row.get("entry_node_ids_json", "[]")))
            exit_nodes = set(json.loads(pw_row.get("exit_node_ids_json", "[]")))
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Pathway %s: malformed node JSON; skipping", pw_id,
            )
            continue

        if not entry_nodes or not exit_nodes:
            logger.debug("Pathway %s: no entry or exit nodes; skipping", pw_id)
            continue

        # Get edges belonging to this pathway
        pw_edges = edges_by_pathway.get(pw_id, [])
        if not pw_edges:
            logger.debug("Pathway %s: no edges in registry; skipping", pw_id)
            continue

        # Build adjacency list: source_node -> [(target_node, edge_id), ...]
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge_row in pw_edges:
            src = edge_row["source_node_id"]
            tgt = edge_row["target_node_id"]
            eid = edge_row["edge_relation_id"]
            adjacency.setdefault(src, []).append((tgt, eid))

        # Find direct edges (entry→exit in one hop)
        direct_edge_ids: dict[tuple[str, str], str] = {}
        for edge_row in pw_edges:
            src = edge_row["source_node_id"]
            tgt = edge_row["target_node_id"]
            if src in entry_nodes and tgt in exit_nodes:
                direct_edge_ids[(src, tgt)] = edge_row["edge_relation_id"]

        # Enumerate simple paths from each entry → each exit via DFS
        path_count = 0
        for entry in entry_nodes:
            if entry not in adjacency:
                continue
            for exit_node in exit_nodes:
                paths = _find_simple_paths(
                    adjacency, entry, exit_node, _MAX_PATHS_PER_PATHWAY - path_count,
                )
                for edge_path in paths:
                    if path_count >= _MAX_PATHS_PER_PATHWAY:
                        logger.warning(
                            "Pathway %s: hit max path limit (%d); truncating",
                            pw_id, _MAX_PATHS_PER_PATHWAY,
                        )
                        break

                    # Find matching direct edge for this entry→exit pair
                    direct_eid = direct_edge_ids.get((entry, exit_node))

                    # Build pathway_id suffix for multi-path pathways
                    suffix = f"__path_{path_count}" if path_count > 0 or len(entry_nodes) > 1 or len(exit_nodes) > 1 else ""
                    definitions.append(PathwayDefinition(
                        pathway_id=f"{pw_id}{suffix}",
                        edge_sequence=edge_path,
                        direct_edge_id=direct_eid,
                    ))
                    path_count += 1

                if path_count >= _MAX_PATHS_PER_PATHWAY:
                    break
            if path_count >= _MAX_PATHS_PER_PATHWAY:
                break

        if path_count == 0:
            logger.debug(
                "Pathway %s: no entry→exit paths found among %d edges",
                pw_id, len(pw_edges),
            )

    logger.info(
        "Loaded %d PathwayDefinition(s) from %d registry pathways",
        len(definitions), len(pathways_raw),
    )
    return definitions


def _find_simple_paths(
    adjacency: dict[str, list[tuple[str, str]]],
    start: str,
    end: str,
    max_paths: int,
) -> list[list[str]]:
    """DFS enumeration of simple paths from *start* to *end*.

    Returns a list of edge-id lists, each representing a simple path.
    Stops after *max_paths* paths are found.

    Parameters
    ----------
    adjacency : dict
        source_node -> [(target_node, edge_id), ...]
    start : str
        Start node.
    end : str
        End node.
    max_paths : int
        Maximum number of paths to enumerate.

    Returns
    -------
    list[list[str]]
        Each inner list is an ordered sequence of edge_relation_ids.
    """
    if max_paths <= 0:
        return []

    results: list[list[str]] = []
    # stack: (current_node, visited_nodes, edge_path)
    stack: list[tuple[str, set[str], list[str]]] = [
        (start, {start}, []),
    ]

    while stack and len(results) < max_paths:
        node, visited, path = stack.pop()

        if node == end and path:
            # We reached the target with at least one edge
            results.append(list(path))
            continue

        for neighbor, edge_id in adjacency.get(node, []):
            if neighbor not in visited:
                stack.append((
                    neighbor,
                    visited | {neighbor},
                    path + [edge_id],
                ))

    return results
