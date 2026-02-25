#!/usr/bin/env python3
"""
Run the CRCI model build pipeline: ALG-A (Graph Assembly) + ALG-B (Evidence Compilation).

Usage:
    python scripts/run_build.py [--evidence-csv PATH] [--verbose]
    python scripts/run_build.py --node-registry PATH --edge-registry PATH --instrument-registry PATH

Runs ALG-A: loads node/edge/instrument registries, builds GraphObject.
Runs ALG-B: compiles evidence records into FrozenModelState.
Reports: graph stats, spectral radius, number of parameterized edges.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load .env if present
_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _default_registry_path(name: str) -> Path:
    """Return default path for a registry CSV in the project root."""
    return _project_root / name


def _print_graph_report(graph) -> None:
    """Print ALG-A graph assembly results."""
    print("\n" + "=" * 70)
    print("ALG-A: GRAPH ASSEMBLY RESULTS")
    print("=" * 70)
    print(f"  Nodes:           {graph.n_nodes}")
    print(f"    Observable:    {graph.node_map.n_observable}")
    print(f"    Latent:        {graph.node_map.n_latent}")
    print(f"  Edges:           {graph.n_edges}")
    print(f"  Pathways:        {graph.n_pathways}")
    print(f"  Feedback loops:  {graph.n_feedback_loops}")
    print(f"  Edgeless nodes:  {len(graph.edgeless_nodes)}")
    print(f"  Spectral radius: {graph.lambda_structure.spectral_radius_B:.6f}")
    print(f"  Condition κ(Λ):  {graph.lambda_structure.condition_number:.2e}")
    print("=" * 70)


def _print_frozen_report(frozen) -> None:
    """Print ALG-B frozen model state results."""
    print("\n" + "=" * 70)
    print("ALG-B: FROZEN MODEL STATE RESULTS")
    print("=" * 70)
    print(f"  Edges parameterized: {frozen.n_edges_parameterized}")
    print(f"  Edges blocked:       {frozen.n_edges_blocked}")
    print(f"  Context priors:      {frozen.n_contexts}")
    print(f"  Synergy records:     {len(frozen.synergy_records)}")
    print(f"  Integrity hash:      {frozen.sha256_hash[:16]}...")
    print(f"  Non-zero B̂ entries:  {int((frozen.B_hat != 0).sum())}")
    print(f"  Edges with SE_eff:   {len(frozen.Sigma_eff)}")
    print(f"  Edges with P_incl:   {len(frozen.P_inclusion)}")
    print("=" * 70)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CRCI model build pipeline (ALG-A + ALG-B)",
    )
    parser.add_argument(
        "--node-registry",
        type=Path,
        default=_default_registry_path("NODE_REGISTRY.csv"),
        help="Path to NODE_REGISTRY.csv (default: project root)",
    )
    parser.add_argument(
        "--edge-registry",
        type=Path,
        default=_default_registry_path("EDGE_REGISTRY.csv"),
        help="Path to EDGE_REGISTRY.csv (default: project root)",
    )
    parser.add_argument(
        "--instrument-registry",
        type=Path,
        default=_default_registry_path("INSTRUMENT_REGISTRY.csv"),
        help="Path to INSTRUMENT_REGISTRY.csv (default: project root)",
    )
    parser.add_argument(
        "--pathway-registry",
        type=Path,
        default=_default_registry_path("PATHWAY_REGISTRY.csv"),
        help="Path to PATHWAY_REGISTRY.csv (default: project root)",
    )
    parser.add_argument(
        "--evidence-csv",
        type=Path,
        default=None,
        help="Path to evidence CSV (optional — if absent, builds graph only)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Validate registry paths
    for name, path in [
        ("Node registry", args.node_registry),
        ("Edge registry", args.edge_registry),
        ("Instrument registry", args.instrument_registry),
    ]:
        if not path.exists():
            print(f"Error: {name} not found: {path}", file=sys.stderr)
            return 1

    pathway_path = args.pathway_registry if args.pathway_registry.exists() else None

    # ── ALG-A: Graph Assembly ──
    print("\n>>> ALG-A: Graph Assembly")
    t0 = time.monotonic()

    try:
        from crci.algorithm.chain_a_graph.graph_object import run_chain_a

        graph = run_chain_a(
            node_registry_path=args.node_registry,
            edge_registry_path=args.edge_registry,
            instrument_registry_path=args.instrument_registry,
            pathway_registry_path=pathway_path,
        )
        dt_a = time.monotonic() - t0
        _print_graph_report(graph)
        print(f"  (completed in {dt_a:.2f}s)")

    except Exception as exc:
        logger.exception("ALG-A failed: %s", exc)
        return 1

    # ── ALG-B: Evidence Compilation + Frozen State ──
    if args.evidence_csv is not None:
        if not args.evidence_csv.exists():
            print(f"Error: Evidence CSV not found: {args.evidence_csv}", file=sys.stderr)
            return 1

        print("\n>>> ALG-B: Evidence Compilation → Frozen Model State")
        t1 = time.monotonic()

        try:
            import csv as csv_mod
            from crci.algorithm.chain_b_evidence.evidence_compiler import (
                EvidenceRecord,
                run_b1_through_b6,
            )
            from crci.algorithm.chain_b_evidence.frozen_state import (
                assemble_frozen_state,
                load_synergy_registry,
            )

            # Load evidence records from CSV
            records: list[EvidenceRecord] = []
            with open(args.evidence_csv, newline="", encoding="utf-8") as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    rec = EvidenceRecord(
                        study_id=row["study_id"],
                        edge_id=row["edge_id"],
                        beta=float(row["beta"]),
                        se=float(row["se"]),
                        study_design=row.get("study_design", "observational"),
                        publication_year=int(row.get("publication_year", 2020)),
                        sample_size=int(row.get("sample_size", 100)),
                        identification_status=row.get("identification_status", "identified"),
                        quality_grade=row.get("quality_grade", "MODERATE"),
                        scope_weights={
                            dim: float(row.get(f"scope_{dim}", 1.0))
                            for dim in [
                                "population", "intervention", "comparator",
                                "outcome", "setting",
                            ]
                        },
                        cancer_validation_status=row.get(
                            "cancer_validation_status", "general_population"
                        ),
                        temporal_distance_days=float(
                            row.get("temporal_distance_days", 0.0)
                        ),
                        outcome_type=row.get("outcome_type", "subjective"),
                    )
                    records.append(rec)

            logger.info("Loaded %d evidence records from %s", len(records), args.evidence_csv)

            # Run B1-B6
            (pooled, adjusted, priors, inclusions,
             tau_sq, chain_direct) = run_b1_through_b6(graph, records)

            # Load synergy registry (optional)
            synergy = load_synergy_registry()

            # Assemble frozen state
            frozen = assemble_frozen_state(
                graph=graph,
                pooled_edges=pooled,
                adjusted_edges=adjusted,
                prior_specs=priors,
                inclusion_probs=inclusions,
                tau_sq_priors=tau_sq,
                chain_direct_results=chain_direct,
                synergy_records=synergy,
            )

            dt_b = time.monotonic() - t1
            _print_frozen_report(frozen)
            print(f"  (completed in {dt_b:.2f}s)")

        except Exception as exc:
            logger.exception("ALG-B failed: %s", exc)
            return 1
    else:
        print("\n>>> ALG-B: Skipped (no --evidence-csv provided)")
        print("  To compile evidence, provide --evidence-csv PATH")

    print("\nBuild pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
