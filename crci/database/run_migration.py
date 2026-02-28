"""
Utility: Run SQLite migrations that use ALTER TABLE ADD COLUMN.

SQLite does not support ALTER TABLE ADD COLUMN IF NOT EXISTS.
This runner executes each statement individually, catching
"duplicate column name" errors and reporting them as skips.

Usage:
    python -m crci.database.run_migration crci/database/schema/014_edge_evidence_p2p7_columns.sql
    python -m crci.database.run_migration --db crci_dev.db crci/database/schema/014_*.sql
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path


def run_migration(db_path: str, sql_path: str, *, verbose: bool = True) -> dict:
    """Execute a migration SQL file statement-by-statement.
    
    Returns dict with counts: {added, skipped, failed, total}.
    """
    sql_text = Path(sql_path).read_text()
    
    # Split on semicolons, skip empty/comment-only fragments
    raw_stmts = sql_text.split(";")
    stmts = []
    for raw in raw_stmts:
        stripped = raw.strip()
        # Remove pure comment lines for emptiness check
        lines = [l for l in stripped.splitlines() if not l.strip().startswith("--")]
        if any(l.strip() for l in lines):
            stmts.append(stripped + ";")
    
    conn = sqlite3.connect(db_path)
    counts = {"added": 0, "skipped": 0, "failed": 0, "total": len(stmts)}
    
    for stmt in stmts:
        # Extract column name for reporting
        col_match = re.search(r"ADD\s+COLUMN\s+(\w+)", stmt, re.IGNORECASE)
        col_name = col_match.group(1) if col_match else "?"
        
        try:
            conn.execute(stmt)
            conn.commit()
            counts["added"] += 1
            if verbose:
                print(f"  ✅ {col_name}")
        except sqlite3.OperationalError as e:
            err = str(e).lower()
            if "duplicate column" in err:
                counts["skipped"] += 1
                if verbose:
                    print(f"  ⏭️  {col_name} (already exists)")
            else:
                counts["failed"] += 1
                if verbose:
                    print(f"  ❌ {col_name}: {e}")
    
    conn.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description="Run SQLite migration(s)")
    parser.add_argument("sql_files", nargs="+", help="SQL migration file(s)")
    parser.add_argument("--db", default="crci_dev.db", help="SQLite database path")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress per-column output")
    args = parser.parse_args()
    
    for sql_file in args.sql_files:
        print(f"\n{'═'*60}")
        print(f"  Migration: {sql_file}")
        print(f"  Database:  {args.db}")
        print(f"{'═'*60}")
        
        counts = run_migration(args.db, sql_file, verbose=not args.quiet)
        
        print(f"\n  Summary: {counts['added']} added, "
              f"{counts['skipped']} skipped, "
              f"{counts['failed']} failed "
              f"(of {counts['total']} statements)")
        
        if counts["failed"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
