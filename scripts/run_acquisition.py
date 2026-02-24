#!/usr/bin/env python3
"""
Run automated paper acquisition cycle.

Usage:
    python scripts/run_acquisition.py --workstream all --max-papers 50
    python scripts/run_acquisition.py --workstream instruments --max-papers 10 --dry-run
    python scripts/run_acquisition.py --manual
    python scripts/run_acquisition.py --cycle --max-papers 20

Options:
    --workstream: {edge|instruments|norms|priors|recovery|kernels|correlations|all}
    --max-papers: Maximum papers to retrieve per cycle (default: 50)
    --dry-run: Show queries and candidates without fetching
    --manual: Process manual_uploads/ instead of automated search
    --cycle: Run full cycle (search + retrieve + extract + compile)
    --continuous: Run in continuous mode (loop every N hours)
    --verbose: Enable debug-level logging
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


_WORKSTREAM_MAP = {
    "edge": "edge_evidence",
    "instruments": "instrument_psychometrics",
    "norms": "population_norms",
    "priors": "context_priors",
    "recovery": "recovery_parameters",
    "kernels": "intervention_kernels",
    "correlations": "correlations",
    "all": None,
}


def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_report(report) -> None:
    """Print acquisition report."""
    print("\n" + "=" * 70)
    print("ACQUISITION REPORT")
    print("=" * 70)
    print(f"Queries generated:      {report.queries_generated}")
    print(f"Candidates found:       {report.candidates_found}")
    print(f"Candidates dispatched:  {report.candidates_dispatched}")
    print(f"Candidates deferred:    {report.candidates_deferred}")
    print(f"Full-text retrieved:    {report.fulltext_retrieved}")
    print(f"Abstract-only:          {report.abstract_only}")
    print(f"Retrieval failed:       {report.retrieval_failed}")
    print(f"Workstreams searched:   {', '.join(report.workstreams_searched)}")
    if report.errors:
        print(f"\nErrors ({len(report.errors)}):")
        for err in report.errors:
            print(f"  - {err}")
    print("=" * 70)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CRCI automated paper acquisition",
    )
    parser.add_argument(
        "--workstream",
        choices=list(_WORKSTREAM_MAP.keys()),
        default="all",
        help="Which workstream to search (default: all)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=50,
        help="Maximum papers to retrieve per cycle (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show queries and candidates without fetching",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Process manual_uploads/ instead of automated search",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run in continuous mode (loop)",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Maximum number of cycles in continuous mode",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    # Determine workstreams
    workstream = _WORKSTREAM_MAP.get(args.workstream)
    workstreams = [workstream] if workstream else None

    if args.manual:
        # Manual import mode
        from crci.retrieval.manual_upload_watcher import run_manual_import

        logger = logging.getLogger(__name__)
        logger.info("Running manual import...")

        # For manual import, we need a DB session
        # NOTE: In production, this would use the actual DB engine
        print("Manual import mode: scanning data/manual_uploads/")
        print("NOTE: Database session required for actual import.")
        print("Use run_manual_import.py for full manual import functionality.")
        return 0

    # Automated acquisition mode
    from crci.retrieval.acquisition_scheduler import (
        run_acquisition_cycle,
        run_continuous,
    )

    print(f"Starting acquisition: workstream={args.workstream}, "
          f"max_papers={args.max_papers}, dry_run={args.dry_run}")
    print("NOTE: Database session required. Configure DB connection first.")
    print("Acquisition scheduler ready for integration with database engine.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
