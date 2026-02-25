#!/usr/bin/env python3
"""
Run automated paper acquisition cycle.

Usage:
    python scripts/run_acquisition.py --workstream all --max-papers 50
    python scripts/run_acquisition.py --workstream instruments --max-papers 10 --dry-run
    python scripts/run_acquisition.py --manual
    python scripts/run_acquisition.py --continuous --max-papers 20

Options:
    --workstream: {edge|instruments|norms|priors|recovery|kernels|correlations|all}
    --max-papers: Maximum papers to retrieve per cycle (default: 50)
    --dry-run: Show queries and candidates without fetching
    --manual: Process manual_uploads/ instead of automated search
    --continuous: Run in continuous mode (loop every N hours)
    --max-cycles: Max number of cycles in continuous mode
    --verbose: Enable debug-level logging
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

from crci.shared.db import get_session, init_db


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
    init_db()

    # Determine workstreams
    workstream = _WORKSTREAM_MAP.get(args.workstream)
    workstreams = [workstream] if workstream else None

    if args.manual:
        from crci.retrieval.manual_upload_watcher import (
            scan_pdfs,
            import_structured_csv,
            process_search_overrides,
        )

        logger = logging.getLogger(__name__)
        logger.info("Running manual import via acquisition script...")

        with get_session() as session:
            pdfs = scan_pdfs(session)
            logger.info("Scanned %d PDFs for import", len(pdfs))
            csvs = import_structured_csv(session)
            logger.info("Imported %d structured CSVs", len(csvs))
            overrides = process_search_overrides(session)
            logger.info("Processed %d search overrides", len(overrides))

        return 0

    # Automated acquisition mode
    from crci.retrieval.acquisition_scheduler import (
        run_acquisition_cycle,
        run_continuous,
    )

    print(f"Starting acquisition: workstream={args.workstream}, "
          f"max_papers={args.max_papers}, dry_run={args.dry_run}")

    with get_session() as session:
        if args.continuous:
            reports = run_continuous(
                session,
                workstreams=workstreams,
                max_papers_per_cycle=args.max_papers,
                max_cycles=args.max_cycles,
            )
            for i, report in enumerate(reports, 1):
                print(f"\n--- Cycle {i} ---")
                _print_report(report)
        else:
            report = run_acquisition_cycle(
                session,
                workstreams=workstreams,
                max_papers=args.max_papers,
                dry_run=args.dry_run,
            )
            _print_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
