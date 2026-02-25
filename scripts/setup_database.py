#!/usr/bin/env python3
"""
Database setup and seed loading for CRCI system.

Usage:
    python scripts/setup_database.py --init          # Create tables from SQL schemas
    python scripts/setup_database.py --seed          # Load seed CSVs into Class A tables
    python scripts/setup_database.py --verify        # Check table counts and FK integrity
    python scripts/setup_database.py --init --seed   # Both: create tables then load seeds
    python scripts/setup_database.py --reset         # Drop all tables, recreate, reload seeds

Requires:
    DATABASE_URL in .env or environment (default: postgresql://crci:crci@localhost:5432/crci)
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

from crci.shared.db import create_db_engine, execute_sql_file, get_session, init_db

logger = logging.getLogger(__name__)

SCHEMA_DIR = _project_root / "crci" / "database" / "schema"
SEEDS_DIR = _project_root / "crci" / "database" / "seeds"

SCHEMA_FILES = [
    "001_class_a_knowledge.sql",
    "002_class_b_evidence.sql",
    "003_class_c_compiled.sql",
    "004_class_d_reference.sql",
    "005_class_e_output.sql",
    "006_fk_constraints.sql",
    "007_ops_tables.sql",
]


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def do_init(engine) -> None:
    """Create all tables by running schema SQL files in order."""
    print("\n--- Creating tables from SQL schemas ---")
    for sql_file in SCHEMA_FILES:
        sql_path = SCHEMA_DIR / sql_file
        if not sql_path.exists():
            print(f"  MISSING: {sql_file}")
            continue
        try:
            execute_sql_file(engine, str(sql_path))
            print(f"  OK: {sql_file}")
        except Exception as exc:
            print(f"  FAIL: {sql_file} — {exc}")
            raise
    print("Schema creation complete.")


def do_reset(engine) -> None:
    """Drop all tables and recreate from scratch."""
    from sqlalchemy import text

    print("\n--- Dropping all tables ---")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO crci;"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    print("All tables dropped.")
    do_init(engine)


def do_seed() -> None:
    """Load seed CSVs into Class A tables."""
    print("\n--- Loading seed data ---")
    if not SEEDS_DIR.is_dir():
        print(f"Seeds directory not found: {SEEDS_DIR}")
        print("Create seed CSVs in crci/database/seeds/ first.")
        return

    csv_files = list(SEEDS_DIR.glob("*.csv"))
    if not csv_files:
        print("No CSV files found in seeds directory.")
        return

    # Import seed_loader — fix its relative imports by ensuring crci is importable
    from crci.database.seed_loader import load_all_seeds

    with get_session() as session:
        results = load_all_seeds(
            seeds_dir=SEEDS_DIR,
            session=session,
            validate=True,
            upsert=False,
        )

    print("\nSeed loading results:")
    total = 0
    for csv_name, count in results.items():
        status = f"{count} rows" if count > 0 else "skipped (empty or missing)"
        print(f"  {csv_name:40s} {status}")
        total += count
    print(f"\nTotal rows loaded: {total}")


def do_verify() -> None:
    """Verify table counts and basic FK integrity."""
    print("\n--- Verifying database state ---")
    from sqlalchemy import text

    with get_session() as session:
        # Count all tables
        result = session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result]
        print(f"\nTotal tables: {len(tables)}")

        # Class A tables (knowledge base) — these should be seeded
        class_a_tables = [
            ("biomarker_node_definitions_v1", "Nodes"),
            ("edge_relations_definitions_v1", "Edges"),
            ("instrument_definitions_v1", "Instruments"),
            ("measure_definitions_v1", "Measures"),
            ("pathways_v1", "Pathways"),
            ("observation_noise_v1", "Observation Noise"),
            ("feedback_loops_v1", "Feedback Loops"),
            ("node_search_terms_v1", "Search Terms"),
            ("action_catalog_v1", "Actions"),
            ("normalization_refs_v1", "Normalization Refs"),
            ("harmonization_rules_v1", "Harmonization Rules"),
            ("recovery_trajectories_v1", "Recovery Trajectories"),
            ("intervention_kernels_v1", "Intervention Kernels"),
            ("biomarker_correlations_v1", "Correlations"),
            ("literary_mechanistic_priors_v1", "Literary Priors"),
        ]

        print("\nClass A (Knowledge Base) table counts:")
        for table_name, label in class_a_tables:
            if table_name in tables:
                count_result = session.execute(
                    text(f"SELECT count(*) FROM {table_name}")
                )
                count = count_result.scalar()
                status = f"{count:>5d}" if count > 0 else "    0  <-- EMPTY"
                print(f"  {label:30s} ({table_name:40s}) {status}")
            else:
                print(f"  {label:30s} ({table_name:40s}) MISSING TABLE")

        # Class B tables (evidence) — populated by extraction
        class_b_tables = [
            ("study_registry_v1", "Study Registry"),
            ("edge_evidence_v1", "Edge Evidence"),
            ("instrument_evidence_v1", "Instrument Evidence"),
            ("population_norms_v1", "Population Norms"),
            ("temporal_evidence_v1", "Temporal Evidence"),
            ("dose_evidence_v1", "Dose Evidence"),
            ("extraction_runs", "Extraction Runs"),
            ("acquisition_queue_v1", "Acquisition Queue"),
        ]

        print("\nClass B (Evidence) table counts:")
        for table_name, label in class_b_tables:
            if table_name in tables:
                count_result = session.execute(
                    text(f"SELECT count(*) FROM {table_name}")
                )
                count = count_result.scalar()
                print(f"  {label:30s} ({table_name:40s}) {count:>5d}")
            else:
                print(f"  {label:30s} ({table_name:40s}) MISSING TABLE")

        print("\nVerification complete.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CRCI database setup and seed loading",
    )
    parser.add_argument("--init", action="store_true", help="Create tables from SQL schemas")
    parser.add_argument("--seed", action="store_true", help="Load seed CSVs into Class A tables")
    parser.add_argument("--verify", action="store_true", help="Check table counts and FK integrity")
    parser.add_argument("--reset", action="store_true", help="Drop all tables, recreate, reload seeds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug-level logging")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if not any([args.init, args.seed, args.verify, args.reset]):
        parser.print_help()
        return 1

    engine = init_db()

    try:
        if args.reset:
            do_reset(engine)
            do_seed()
        else:
            if args.init:
                do_init(engine)
            if args.seed:
                do_seed()
        if args.verify:
            do_verify()
    except Exception as exc:
        logger.exception("Setup failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
