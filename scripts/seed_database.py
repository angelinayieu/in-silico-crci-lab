#!/usr/bin/env python3
"""
Seed the CRCI database with Class A knowledge tables from CSV files.

Usage:
    python scripts/seed_database.py                    # Load all seeds
    python scripts/seed_database.py --validate         # Load + validate FK integrity
    python scripts/seed_database.py --upsert           # Update existing rows
    python scripts/seed_database.py --seeds-dir PATH   # Custom seeds directory

Wrapper for crci.database.seed_loader.load_all_seeds().
For full database setup (create tables + seed), use setup_database.py instead.
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


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Seed CRCI Class A knowledge tables from CSV files",
    )
    parser.add_argument(
        "--seeds-dir",
        type=Path,
        default=_project_root / "crci" / "database" / "seeds",
        help="Path to seeds directory (default: crci/database/seeds/)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Run Class A validation after loading (default: True)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation after loading",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Update existing rows on conflict (default: insert only)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    seeds_dir = args.seeds_dir
    if not seeds_dir.is_dir():
        print(f"Error: Seeds directory not found: {seeds_dir}", file=sys.stderr)
        print("Create seed CSVs in crci/database/seeds/ first.", file=sys.stderr)
        return 1

    csv_files = list(seeds_dir.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {seeds_dir}", file=sys.stderr)
        return 1

    print(f"\n>>> Seeding database from {seeds_dir}")
    print(f"    CSV files found: {len(csv_files)}")
    print(f"    Validate: {not args.no_validate}")
    print(f"    Upsert:   {args.upsert}")

    from crci.shared.db import get_session, init_db
    from crci.database.seed_loader import load_all_seeds

    init_db()

    try:
        with get_session() as session:
            results = load_all_seeds(
                seeds_dir=seeds_dir,
                session=session,
                validate=not args.no_validate,
                upsert=args.upsert,
            )
    except Exception as exc:
        logging.getLogger(__name__).exception("Seed loading failed: %s", exc)
        return 1

    print("\n" + "=" * 70)
    print("SEED LOADING RESULTS")
    print("=" * 70)
    total = 0
    for csv_name, count in results.items():
        status = f"{count:>5d} rows" if count > 0 else "    0  (skipped)"
        print(f"  {csv_name:40s} {status}")
        total += count
    print(f"\n  Total rows loaded: {total}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
