#!/usr/bin/env python3
"""Deduplicate edge_evidence_v1 rows.

For each (study_id, edge_relation_id), keep only ONE active row:
1. Prefer rows with non-None SE (better precision).
2. Prefer earlier entered_at (manual imports over pipeline).
3. Prefer lower se_derivation_level (L1_EXACT > L2_CI > L4B_N_DERIVED > L6).

All other rows are deactivated (active=0).

Usage:
    python scripts/dedup_evidence.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from crci.shared.db import get_session, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# SE derivation quality ranking (lower = better)
_SE_LEVEL_RANK = {
    "L1_EXACT": 1,
    "DIRECT": 1,
    "L2_CI": 2,
    "L3_P_VALUE": 3,
    "L4B_N_DERIVED": 4,
    "L5_PROXY": 5,
    "L6_QUALITATIVE": 6,
}


def _rank_row(row: dict) -> tuple:
    """Return a sort key for choosing the best row (lower = better)."""
    has_se = 0 if row.get("se_reported") is not None else 1
    se_rank = _SE_LEVEL_RANK.get(row.get("se_derivation_level") or "", 99)
    entered = row.get("entered_at") or "9999"
    return (has_se, se_rank, entered)


def dedup_evidence(dry_run: bool = True) -> dict:
    """Deduplicate edge_evidence_v1 rows.

    Returns:
        Dict with total_groups, total_dupes, deactivated counts.
    """
    db_url = os.environ.get("DATABASE_URL", "sqlite:///crci_dev.db")
    init_db(db_url)

    stats = {"total_groups": 0, "total_dupes": 0, "deactivated": 0}

    with get_session() as session:
        # Find all (study_id, edge_relation_id) groups with >1 active row
        dupes = session.execute(text(
            "SELECT study_id, edge_relation_id, COUNT(*) as cnt "
            "FROM edge_evidence_v1 "
            "WHERE active = 1 "
            "GROUP BY study_id, edge_relation_id "
            "HAVING cnt > 1"
        )).fetchall()

        stats["total_groups"] = len(dupes)

        for study_id, edge_relation_id, cnt in dupes:
            stats["total_dupes"] += cnt - 1  # extras beyond the 1 we keep

            # Get all active rows for this group
            rows = session.execute(text(
                "SELECT ler_id, se_reported, se_derivation_level, entered_at "
                "FROM edge_evidence_v1 "
                "WHERE study_id = :sid AND edge_relation_id = :eid AND active = 1 "
                "ORDER BY entered_at"
            ), {"sid": study_id, "eid": edge_relation_id}).fetchall()

            row_dicts = [
                {
                    "ler_id": r[0],
                    "se_reported": r[1],
                    "se_derivation_level": r[2],
                    "entered_at": r[3],
                }
                for r in rows
            ]

            # Sort by quality rank, keep first
            row_dicts.sort(key=_rank_row)
            keep_id = row_dicts[0]["ler_id"]
            deactivate_ids = [r["ler_id"] for r in row_dicts[1:]]

            logger.info(
                "Dedup %s/%s: keeping %s, deactivating %d others",
                study_id, edge_relation_id, keep_id, len(deactivate_ids),
            )

            if not dry_run:
                for lid in deactivate_ids:
                    session.execute(text(
                        "UPDATE edge_evidence_v1 SET active = 0 "
                        "WHERE ler_id = :lid"
                    ), {"lid": lid})
                    stats["deactivated"] += 1

    action = "Would deactivate" if dry_run else "Deactivated"
    logger.info(
        "%s: %d groups with duplicates, %d excess rows %s",
        "DRY RUN" if dry_run else "APPLIED",
        stats["total_groups"],
        stats["total_dupes"],
        action.lower(),
    )
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate edge_evidence_v1 rows")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Show what would be deactivated without making changes")
    args = parser.parse_args()
    dedup_evidence(dry_run=args.dry_run)
