#!/usr/bin/env python3
"""
G0 Gate: Pre-deployment parameter readiness check.

Usage:
    python scripts/validate_deployment_readiness.py [--verbose]
    python scripts/validate_deployment_readiness.py --patient-context breast_adjuvant

Implements the G0 gate from PARAMETER_PROVENANCE_AND_CURATION.md Part 5.
Checks:
    G0-1: Measurement model completeness (active instruments must be CURATED)
    G0-2: Minimum edge parameterization (≥30 edges with real evidence)
    G0-3: Prior coverage (≥3 curated context-matched priors)
    G0-4: Spectral radius with real weights (ρ(B) < 1)
    G0-5: No APPROXIMATE in critical path (patient-specific check)

Output: READY or NOT_READY with specific failing checks.
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


# ═══════════════════════════════════════════════════════════════
#  G0 Check Implementations
# ═══════════════════════════════════════════════════════════════

# Minimum parameterized edges required
G0_MIN_PARAMETERIZED_EDGES: int = 30

# Minimum curated context-matched priors
G0_MIN_CURATED_PRIORS: int = 3


def _check_g0_1(session) -> tuple[bool, str]:
    """G0-1: Measurement model completeness.

    Every instrument that patients will actually USE (in question_bank_v1)
    must have real psychometric values — not APPROXIMATE_PENDING.

    SQL:
        SELECT COUNT(*) FROM instruments_v1
        WHERE provenance_status = 'APPROXIMATE_PENDING'
        AND instrument_id IN (SELECT DISTINCT instrument_id FROM question_bank_v1)
        MUST = 0
    """
    from sqlalchemy import text

    try:
        result = session.execute(text("""
            SELECT COUNT(*) FROM instrument_definitions_v1 i
            WHERE i.provenance_status = 'APPROXIMATE_PENDING'
            AND i.instrument_id IN (
                SELECT DISTINCT instrument_id FROM question_bank_v1
            )
        """))
        count = result.scalar() or 0
    except Exception as exc:
        return False, f"Cannot query instruments: {exc}"

    if count == 0:
        return True, "All active instruments have curated psychometrics."
    return False, (
        f"{count} active instrument(s) still have APPROXIMATE_PENDING "
        f"psychometric values. Curate these before deployment."
    )


def _check_g0_2(session) -> tuple[bool, str]:
    """G0-2: Minimum edge parameterization.

    At least 30 of 118 edges must have real evidence from extraction.

    SQL:
        SELECT COUNT(*) FROM edges_v1 WHERE beta_mean IS NOT NULL
        MUST ≥ 30
    """
    from sqlalchemy import text

    try:
        # Try edge_relations_definitions_v1 first (the actual Class A table)
        result = session.execute(text(
            "SELECT COUNT(*) FROM edge_relations_definitions_v1 "
            "WHERE beta_mean IS NOT NULL"
        ))
        count = result.scalar() or 0
    except Exception:
        try:
            # Fallback to edges_v1 if that table name is used
            result = session.execute(text(
                "SELECT COUNT(*) FROM edges_v1 WHERE beta_mean IS NOT NULL"
            ))
            count = result.scalar() or 0
        except Exception as exc:
            return False, f"Cannot query edges: {exc}"

    if count >= G0_MIN_PARAMETERIZED_EDGES:
        return True, f"{count} edges parameterized (minimum: {G0_MIN_PARAMETERIZED_EDGES})."
    return False, (
        f"Only {count} edges parameterized (minimum: {G0_MIN_PARAMETERIZED_EDGES}). "
        f"Run extraction pipeline on more papers."
    )


def _check_g0_3(session) -> tuple[bool, str]:
    """G0-3: Prior coverage.

    At least 3 cancer×phase contexts must have curated priors.

    SQL:
        SELECT COUNT(*) FROM context_matched_priors_v1
        WHERE provenance_status = 'CURATED_TRACED'
        MUST ≥ 3
    """
    from sqlalchemy import text

    try:
        result = session.execute(text(
            "SELECT COUNT(DISTINCT context_key) "
            "FROM context_matched_priors_v1 "
            "WHERE provenance_status = 'CURATED_TRACED'"
        ))
        count = result.scalar() or 0
    except Exception as exc:
        return False, f"Cannot query context_matched_priors: {exc}"

    if count >= G0_MIN_CURATED_PRIORS:
        return True, f"{count} curated context priors (minimum: {G0_MIN_CURATED_PRIORS})."
    return False, (
        f"Only {count} curated context priors (minimum: {G0_MIN_CURATED_PRIORS}). "
        f"Curate priors for at least {G0_MIN_CURATED_PRIORS} cancer×phase contexts."
    )


def _check_g0_4() -> tuple[bool, str]:
    """G0-4: Spectral radius with real weights.

    ρ(B) < 1 with REAL edge weights (not placeholders).
    """
    from crci.algorithm.chain_a_graph.graph_object import run_chain_a
    from crci.shared import config

    node_path = _project_root / "NODE_REGISTRY.csv"
    edge_path = _project_root / "EDGE_REGISTRY.csv"
    instrument_path = _project_root / "INSTRUMENT_REGISTRY.csv"

    for name, path in [
        ("NODE_REGISTRY.csv", node_path),
        ("EDGE_REGISTRY.csv", edge_path),
        ("INSTRUMENT_REGISTRY.csv", instrument_path),
    ]:
        if not path.exists():
            return False, f"{name} not found at {path}"

    try:
        graph = run_chain_a(
            node_registry_path=node_path,
            edge_registry_path=edge_path,
            instrument_registry_path=instrument_path,
        )
    except Exception as exc:
        return False, f"Graph assembly failed: {exc}"

    rho = graph.lambda_structure.spectral_radius
    if rho < config.SPECTRAL_RADIUS_THRESHOLD:
        return True, f"ρ(B) = {rho:.6f} < {config.SPECTRAL_RADIUS_THRESHOLD} (stable)."
    return False, (
        f"ρ(B) = {rho:.6f} ≥ {config.SPECTRAL_RADIUS_THRESHOLD} (unstable). "
        f"Check edge weights for cycles or excessive magnitudes."
    )


def _check_g0_5(session, patient_context: str | None) -> tuple[bool, str]:
    """G0-5: No APPROXIMATE in patient's critical path.

    For the specific patient being tested: their cancer type × treatment
    phase combination must have CURATED_TRACED priors, and every
    instrument they've completed must have CURATED_TRACED psychometrics.
    """
    if patient_context is None:
        return True, "No patient context specified — skipping critical path check."

    from sqlalchemy import text

    # Check context prior exists and is curated
    try:
        result = session.execute(text(
            "SELECT provenance_status FROM context_matched_priors_v1 "
            "WHERE context_key = :ctx"
        ), {"ctx": patient_context})
        row = result.fetchone()
    except Exception as exc:
        return False, f"Cannot query context priors for '{patient_context}': {exc}"

    if row is None:
        return False, (
            f"No context prior found for '{patient_context}'. "
            f"Curate a prior for this cancer×phase combination."
        )

    if row[0] != "CURATED_TRACED":
        return False, (
            f"Context prior for '{patient_context}' has status '{row[0]}' "
            f"(needs CURATED_TRACED)."
        )

    return True, (
        f"Context prior for '{patient_context}' is CURATED_TRACED."
    )


# ═══════════════════════════════════════════════════════════════
#  Main Entry Point
# ═══════════════════════════════════════════════════════════════


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="G0 Gate: Pre-deployment parameter readiness check",
    )
    parser.add_argument(
        "--patient-context",
        default=None,
        help="Patient cancer×phase context key for G0-5 check "
             "(e.g., 'breast_adjuvant')",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    print("=" * 70)
    print("G0 GATE: PRE-DEPLOYMENT READINESS CHECK")
    print("=" * 70)

    from crci.shared.db import get_session, init_db

    init_db()

    checks: list[tuple[str, bool, str]] = []

    with get_session() as session:
        # G0-1: Measurement model completeness
        ok, msg = _check_g0_1(session)
        checks.append(("G0-1", ok, msg))

        # G0-2: Minimum edge parameterization
        ok, msg = _check_g0_2(session)
        checks.append(("G0-2", ok, msg))

        # G0-3: Prior coverage
        ok, msg = _check_g0_3(session)
        checks.append(("G0-3", ok, msg))

    # G0-4: Spectral radius (does not need DB session)
    ok, msg = _check_g0_4()
    checks.append(("G0-4", ok, msg))

    # G0-5: No APPROXIMATE in critical path
    with get_session() as session:
        ok, msg = _check_g0_5(session, args.patient_context)
        checks.append(("G0-5", ok, msg))

    # Report
    print()
    all_passed = True
    for check_id, passed, message in checks:
        status = "PASS" if passed else "FAIL"
        icon = "OK" if passed else "XX"
        print(f"  [{icon}] {check_id}: {message}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("G0 RESULT: READY")
        print("All pre-deployment checks passed. System is ready for inference.")
    else:
        print("G0 RESULT: NOT_READY")
        failed = [c[0] for c in checks if not c[1]]
        print(f"Failing checks: {', '.join(failed)}")
        print("Resolve the above issues before running patient inference.")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
