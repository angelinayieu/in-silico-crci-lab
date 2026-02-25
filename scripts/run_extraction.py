#!/usr/bin/env python3
"""
Run full-spectrum extraction pipeline on a single paper.

Usage:
    python scripts/run_extraction.py <pdf_path> [--skip-idempotency] [--verbose]

Reports:
    - Edge evidence rows
    - Instrument compilations (Compiler 1)
    - Prior compilations (Compiler 2)
    - Kernel + recovery compilations (Compiler 3)
    - Dose-response compilations (Compiler 4)
    - Modifier updates (Compiler 5)
    - Synergy compilations (Compiler 6)
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

from crci.shared.db import init_db
from crci.extraction.pipeline import run_extraction_pipeline


def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_report(run) -> None:
    """Print extraction results summary."""
    print("\n" + "=" * 70)
    print("EXTRACTION RESULTS")
    print("=" * 70)
    print(f"Run ID:    {run.extraction_run_id}")
    print(f"Status:    {run.status}")
    print(f"PDF:       {run.pdf_path}")

    if run.stages_completed_json:
        print(f"\nStages completed: {len(run.stages_completed_json)}")
        for stage in run.stages_completed_json:
            status_icon = "OK" if stage.get("status") == "success" else "!!"
            print(f"  [{status_icon}] {stage.get('stage', '?')}")

    if run.error_message:
        print(f"\nError: {run.error_message[:200]}")

    print("=" * 70)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CRCI full-spectrum extraction pipeline",
    )
    parser.add_argument("pdf_path", help="Path to the PDF file to extract")
    parser.add_argument(
        "--skip-idempotency",
        action="store_true",
        help="Force re-extraction even if paper was already processed",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)
    init_db()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        return 1

    try:
        run = run_extraction_pipeline(
            pdf_path=pdf_path,
            skip_idempotency=args.skip_idempotency,
        )
        _print_report(run)
        return 0 if run.status == "completed" else 1

    except Exception as exc:
        logging.getLogger(__name__).exception("Pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
