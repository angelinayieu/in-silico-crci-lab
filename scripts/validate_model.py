#!/usr/bin/env python3
"""
Validate the CRCI model: spectral radius check + P6 extraction validation.

Usage:
    python scripts/validate_model.py [--verbose]
    python scripts/validate_model.py --spectral-only
    python scripts/validate_model.py --p6-only

Checks:
    1. Spectral radius ρ(B) < 1 (DAG stability)
    2. Condition number κ(Λ) within bounds
    3. P6 validation rules G1-G18 (extraction quality)
    4. P6 deployment gate decision
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
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


def run_spectral_check() -> bool:
    """Run ALG-A spectral validation on the DAG.

    Returns True if all checks pass.
    """
    from crci.algorithm.chain_a_graph.graph_object import run_chain_a
    from crci.shared import config

    print("\n>>> Spectral Validation (ALG-A)")
    print("-" * 50)

    node_path = _project_root / "NODE_REGISTRY.csv"
    edge_path = _project_root / "EDGE_REGISTRY.csv"
    instrument_path = _project_root / "INSTRUMENT_REGISTRY.csv"
    pathway_path = _project_root / "PATHWAY_REGISTRY.csv"

    for name, path in [
        ("NODE_REGISTRY.csv", node_path),
        ("EDGE_REGISTRY.csv", edge_path),
        ("INSTRUMENT_REGISTRY.csv", instrument_path),
    ]:
        if not path.exists():
            print(f"  SKIP: {name} not found at {path}")
            return False

    try:
        graph = run_chain_a(
            node_registry_path=node_path,
            edge_registry_path=edge_path,
            instrument_registry_path=instrument_path,
            pathway_registry_path=pathway_path if pathway_path.exists() else None,
        )
    except Exception as exc:
        print(f"  FAIL: ALG-A graph assembly failed: {exc}")
        return False

    ls = graph.lambda_structure
    passed = True

    # Check 1: Spectral radius ρ(B) < 1
    rho = ls.spectral_radius
    rho_ok = rho < config.SPECTRAL_RADIUS_THRESHOLD
    status = "PASS" if rho_ok else "FAIL"
    print(f"  [{status}] ρ(B) = {rho:.6f} (threshold: < {config.SPECTRAL_RADIUS_THRESHOLD})")
    if not rho_ok:
        passed = False

    # Check 2: Condition number κ(Λ) within bounds
    kappa = ls.condition_number
    kappa_ok = kappa < config.CONDITION_NUMBER_WARN
    status = "PASS" if kappa_ok else "WARN"
    print(f"  [{status}] κ(Λ) = {kappa:.2e} (threshold: < {config.CONDITION_NUMBER_WARN:.0e})")

    # Check 3: Positive definiteness of Λ
    pd_ok = ls.is_positive_definite
    status = "PASS" if pd_ok else "FAIL"
    print(f"  [{status}] Λ positive definite: {pd_ok}")
    if not pd_ok:
        passed = False

    # Summary stats
    print(f"\n  Graph: {graph.n_nodes} nodes, {graph.n_edges} edges")
    print(f"  Feedback loops: {graph.n_feedback_loops} (all stable: "
          f"{all(fl.is_stable for fl in graph.feedback_loops)})")

    return passed


def run_p6_validation() -> bool:
    """Run P6 extraction validation rules.

    Returns True if deployment is not BLOCKED.
    """
    from crci.shared.db import get_session, init_db
    from crci.shared.models.intermediate_states import CompiledEdge, GateViolation

    print("\n>>> P6 Extraction Validation (G1-G18)")
    print("-" * 50)

    init_db()

    # Load compiled edges from database
    from sqlalchemy import text

    compiled_edges: list[CompiledEdge] = []
    try:
        with get_session() as session:
            result = session.execute(text(
                "SELECT edge_id, beta_mean, se_eff, k_studies, "
                "aggregation_method, prior_type, total_n, i_squared "
                "FROM edges_v1 WHERE beta_mean IS NOT NULL"
            ))
            for row in result:
                edge = CompiledEdge(
                    edge_id=row[0],
                    beta_mean=float(row[1]) if row[1] is not None else 0.0,
                    se_eff=float(row[2]) if row[2] is not None else 1.0,
                    k_studies=int(row[3]) if row[3] is not None else 0,
                    aggregation_method=str(row[4]) if row[4] else "NONE",
                    prior_type=str(row[5]) if row[5] else "StructuralPlaceholder",
                    total_n=int(row[6]) if row[6] is not None else 0,
                    i_squared=float(row[7]) if row[7] is not None else 0.0,
                )
                compiled_edges.append(edge)
    except Exception as exc:
        print(f"  SKIP: Cannot read edges_v1 — {exc}")
        print("  (Database may not be initialized. Run setup_database.py --init first.)")
        return False

    if not compiled_edges:
        print("  SKIP: No parameterized edges found in edges_v1.")
        print("  (Run extraction pipeline first to populate evidence.)")
        return False

    print(f"  Loaded {len(compiled_edges)} compiled edges from database.")

    from crci.extraction.p6_deployment.validation_runner import run_validation
    from crci.extraction.p6_deployment.deploy_gate import evaluate_deploy_gate

    validation_result = run_validation(compiled_edges)

    print(f"\n  Validation Results:")
    print(f"    PASS: {validation_result.n_pass}")
    print(f"    WARN: {validation_result.n_warn}")
    print(f"    FAIL: {validation_result.n_fail}")
    print(f"    Total rules: {validation_result.total_rules}")

    for rr in validation_result.rule_results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[rr.status]
        print(f"    [{icon}] {rr.rule_id:4s} {rr.rule_name}: {rr.message[:60]}")

    # Evaluate deploy gate
    try:
        decision = evaluate_deploy_gate(validation_result)
        print(f"\n  Deployment decision: {decision.decision}")
        for note in decision.review_notes:
            print(f"    {note}")
        return decision.decision != "BLOCK"
    except GateViolation as gv:
        print(f"\n  GATE VIOLATION: {gv.gate_id} — {gv.message}")
        return False


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate CRCI model (spectral + P6)",
    )
    parser.add_argument(
        "--spectral-only",
        action="store_true",
        help="Run only spectral validation (ALG-A)",
    )
    parser.add_argument(
        "--p6-only",
        action="store_true",
        help="Run only P6 extraction validation",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    print("=" * 70)
    print("CRCI MODEL VALIDATION")
    print("=" * 70)

    all_passed = True

    if not args.p6_only:
        if not run_spectral_check():
            all_passed = False

    if not args.spectral_only:
        if not run_p6_validation():
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: SOME CHECKS FAILED — see details above")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
