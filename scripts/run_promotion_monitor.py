#!/usr/bin/env python3
"""Run EX-PROM chain: Annotation Promotion Monitor.

Usage:
    python scripts/run_promotion_monitor.py [--dry-run] [--output PATH]

Scans study_annotations_v1 for annotation clusters that have hit
accumulation thresholds (per SYS_EX L2014-2100). Generates
PromotionCandidate[] proposals for human review.

When --dry-run is specified, candidates are logged but NOT written
to review_tasks or JSONL.

When --output is specified, candidates are written to a JSONL file
in addition to review_tasks.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crci.shared.db import get_session
from crci.extraction.promotion_monitor import run_promotion_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("run_promotion_monitor")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run EX-PROM: Annotation Promotion Monitor",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log candidates without writing to DB or files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to JSONL output file (default: none)",
    )
    args = parser.parse_args()

    with get_session() as session:
        candidates = run_promotion_monitor(
            session=session,
            write_review_tasks=not args.dry_run,
            jsonl_output_path=args.output if not args.dry_run else None,
        )

        if candidates:
            logger.info("=" * 60)
            logger.info("EX-PROM RESULTS: %d promotion candidates", len(candidates))
            logger.info("=" * 60)
            for i, c in enumerate(candidates, 1):
                logger.info(
                    "  [%d] %s on %s (%d independent units, %.1f%% contradiction)",
                    i,
                    c.category,
                    c.target_entity_id,
                    c.independent_evidence_units,
                    c.contradiction_ratio * 100,
                )
                logger.info("       → %s", c.proposed_action)

            if args.dry_run:
                logger.info("DRY RUN: No writes performed.")
            else:
                session.commit()
                logger.info("Candidates written to review_tasks table.")
        else:
            logger.info("No promotion candidates found.")


if __name__ == "__main__":
    main()
