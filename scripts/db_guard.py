#!/usr/bin/env python3
"""
Database safety guard.  Run before any destructive operation (schema reset,
full re-extraction, etc.) to prevent accidental data loss.

Functions:
    check_evidence_exists(db_path) -> dict[str, int]
    backup_db(db_path) -> Path
    guard_before_reset(db_path) -> bool   # False == blocked

Usage:
    python scripts/db_guard.py                  # print DB summary
    python scripts/db_guard.py --backup         # create timestamped backup
    python scripts/db_guard.py --guard-reset    # interactive guard for reset
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Tables with irreplaceable manual data
CRITICAL_TABLES = [
    "edge_evidence_v1",
    "temporal_evidence_v1",
    "instrument_evidence_v1",
    "node_priors_v1",
    "study_annotations_v1",
    "study_registry_v1",
]


def check_evidence_exists(db_path: str) -> dict[str, int]:
    """Return row counts for critical tables.

    Returns:
        Mapping of table_name -> row_count.
    """
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    counts: dict[str, int] = {}
    for table in CRITICAL_TABLES:
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM [{table}]")  # noqa: S608
            counts[table] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = 0  # table doesn't exist
    conn.close()
    return counts


def require_dev_environment(force: bool = False) -> None:
    """Block destructive operations outside dev environment.

    Checks CRCI_ENV environment variable. If not set or not 'dev',
    raises SystemExit unless --force is specified.

    Args:
        force: If True, warn but allow non-dev operations.

    Raises:
        SystemExit: If CRCI_ENV is not 'dev' and force is False.
    """
    env = os.environ.get("CRCI_ENV", "unknown")
    if env == "dev":
        return

    if not force:
        print(
            f"ERROR: CRCI_ENV='{env}'. Destructive operations require CRCI_ENV=dev."
        )
        print("Set CRCI_ENV=dev or use --force to override.")
        sys.exit(1)
    else:
        print(
            f"WARNING: CRCI_ENV='{env}' but --force specified. Proceeding."
        )


def check_wal_safety(db_path: str) -> list[str]:
    """Check for WAL safety issues.

    Returns:
        List of warning messages.  Empty list == all clear.
    """
    warnings: list[str] = []
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"

    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
        if wal_size > 0:
            warnings.append(
                f"WAL file exists with {wal_size:,} bytes of uncommitted data: "
                f"{wal_path}. Do NOT delete this file — it contains data that "
                f"has not been checkpointed to the main DB file."
            )
    if os.path.exists(shm_path):
        warnings.append(
            f"SHM file exists: {shm_path}. This is normal during active use "
            f"but should not be deleted while the DB is accessed."
        )

    return warnings


def backup_db(db_path: str) -> Path:
    """Create a timestamped backup of the database (and WAL/SHM if present).

    Returns:
        Path to the backup file.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"{db_path}.bak.{ts}")
    shutil.copy2(db_path, backup_path)
    logger.info("Backed up %s → %s", db_path, backup_path)

    # Also copy WAL and SHM if they exist
    for ext in ("-wal", "-shm"):
        src = db_path + ext
        if os.path.exists(src):
            dst = str(backup_path) + ext
            shutil.copy2(src, dst)
            logger.info("Backed up %s → %s", src, dst)

    return backup_path


def guard_before_reset(db_path: str, *, force: bool = False, interactive: bool = False) -> bool:
    """Guard that blocks destructive operations when data exists.

    Args:
        db_path: Path to the SQLite database file.
        force: If True, bypass the guard and allow the operation.
        interactive: If True, prompt the user for confirmation.
            If False (default), just return False when blocked.

    Returns:
        True if the operation should proceed, False if blocked.
    """
    counts = check_evidence_exists(db_path)
    if not counts:
        # No DB file or no tables — safe to proceed
        return True

    total_rows = sum(v for v in counts.values() if v > 0)
    manual_evidence = 0
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT COUNT(*) FROM edge_evidence_v1 "
            "WHERE entered_by LIKE 'manual_%'"
        )
        manual_evidence = cur.fetchone()[0]
        conn.close()
    except sqlite3.OperationalError:
        pass

    if total_rows == 0:
        return True

    print("\n========================================")
    print("  ⚠  DATABASE GUARD — DATA EXISTS")
    print("========================================")
    print(f"\nDatabase: {db_path}")
    print(f"Total rows in critical tables: {total_rows:,}")
    if manual_evidence > 0:
        print(f"  ** {manual_evidence} MANUALLY ENTERED evidence rows **")
    print("\nTable breakdown:")
    for table, count in counts.items():
        if count > 0:
            print(f"  {table}: {count:,} rows")

    wal_warnings = check_wal_safety(db_path)
    if wal_warnings:
        print("\nWAL warnings:")
        for w in wal_warnings:
            print(f"  {w}")

    if force:
        print("\n--force flag supplied, proceeding without backup prompt.")
        return True

    if not interactive:
        print("\nBlocked. Use --force to override, or run interactively.")
        return False

    print("\nThis operation will DESTROY all existing data.")
    print("Options:")
    print("  [b] Create backup first, then proceed")
    print("  [a] Abort (recommended)")
    print("  [f] Force proceed WITHOUT backup (DANGER)")

    choice = input("\nChoice [b/a/f]: ").strip().lower()
    if choice == "b":
        backup_path = backup_db(db_path)
        print(f"\nBackup created: {backup_path}")
        return True
    elif choice == "f":
        confirm = input("Type 'DELETE ALL DATA' to confirm: ").strip()
        if confirm == "DELETE ALL DATA":
            return True
        else:
            print("Aborted.")
            return False
    else:
        print("Aborted. No data was changed.")
        return False


def print_summary(db_path: str) -> None:
    """Print a human-readable summary of the database state."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return

    counts = check_evidence_exists(db_path)
    total = sum(v for v in counts.values() if v > 0)

    print(f"\nDatabase: {db_path}")
    print(f"File size: {os.path.getsize(db_path):,} bytes")
    print(f"Total rows in critical tables: {total:,}")
    print()

    for table, count in counts.items():
        status = "EMPTY" if count == 0 else (
            "MISSING" if count < 0 else f"{count:,} rows"
        )
        print(f"  {table}: {status}")

    wal_warnings = check_wal_safety(db_path)
    if wal_warnings:
        print("\nWAL Safety Warnings:")
        for w in wal_warnings:
            print(f"  WARNING: {w}")
    else:
        print("\nWAL: clean (no uncommitted data)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Database safety guard")
    parser.add_argument(
        "--db", default="crci_dev.db",
        help="Path to the SQLite database file (default: crci_dev.db)",
    )
    parser.add_argument("--backup", action="store_true", help="Create a backup")
    parser.add_argument(
        "--guard-reset", action="store_true",
        help="Interactive guard before a destructive operation",
    )
    parser.add_argument("--force", action="store_true", help="Skip interactive prompts")

    args = parser.parse_args()

    if args.backup:
        try:
            path = backup_db(args.db)
            print(f"Backup created: {path}")
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
    elif args.guard_reset:
        allowed = guard_before_reset(args.db, force=args.force)
        if not allowed:
            sys.exit(1)
    else:
        print_summary(args.db)


if __name__ == "__main__":
    main()
