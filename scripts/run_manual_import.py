#!/usr/bin/env python3
"""
Import data from manual uploads.

Usage:
    python scripts/run_manual_import.py --type pdf
    python scripts/run_manual_import.py --type csv
    python scripts/run_manual_import.py --type override
    python scripts/run_manual_import.py --type csv --validate-only

Reads from:
    data/manual_uploads/pdfs/          — PDF files + .meta.json companions
    data/manual_uploads/structured/    — Filled CSV templates
    data/manual_uploads/search_overrides/ — DOI/PMID lists as JSON
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
        description="Import data from CRCI manual uploads",
    )
    parser.add_argument(
        "--type",
        choices=["pdf", "csv", "override", "all"],
        default="all",
        help="Type of files to import (default: all)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate file format without importing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    from crci.retrieval.manual_upload_watcher import (
        scan_pdfs,
        import_structured_csv,
        process_search_overrides,
    )

    print(f"Manual import: type={args.type}, validate_only={args.validate_only}")

    upload_dir = Path("data/manual_uploads")
    if not upload_dir.exists():
        print(f"Upload directory not found: {upload_dir}")
        print("Create it with: mkdir -p data/manual_uploads/{pdfs,structured,search_overrides}")
        return 1

    if args.type in ("pdf", "all"):
        pdf_dir = upload_dir / "pdfs"
        if pdf_dir.exists():
            pdfs = list(pdf_dir.glob("*.pdf"))
            print(f"Found {len(pdfs)} PDF files in {pdf_dir}")
            for pdf in pdfs:
                meta_path = pdf.with_suffix(".meta.json")
                has_meta = "yes" if meta_path.exists() else "no"
                print(f"  {pdf.name} (meta: {has_meta})")
        else:
            print(f"No PDF directory: {pdf_dir}")

    if args.type in ("csv", "all"):
        csv_dir = upload_dir / "structured"
        if csv_dir.exists():
            csvs = list(csv_dir.glob("*.csv"))
            print(f"Found {len(csvs)} CSV files in {csv_dir}")
            for csv_file in csvs:
                print(f"  {csv_file.name}")
        else:
            print(f"No structured directory: {csv_dir}")

    if args.type in ("override", "all"):
        override_dir = upload_dir / "search_overrides"
        if override_dir.exists():
            overrides = list(override_dir.glob("*.json"))
            print(f"Found {len(overrides)} override files in {override_dir}")
        else:
            print(f"No overrides directory: {override_dir}")

    print("\nNOTE: Actual database import requires a configured DB session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
