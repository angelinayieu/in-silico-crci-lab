#!/usr/bin/env python3
"""
Import data from manual uploads.

Usage:
    python scripts/run_manual_import.py --type pdf
    python scripts/run_manual_import.py --type csv
    python scripts/run_manual_import.py --type override
    python scripts/run_manual_import.py --type csv --validate-only
    python scripts/run_manual_import.py --type all

Reads from:
    data/manual_uploads/pdfs/          -- PDF files + .meta.json companions
    data/manual_uploads/structured/    -- Filled CSV templates
    data/manual_uploads/search_overrides/ -- DOI/PMID lists as JSON
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


def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence pdfminer DEBUG noise (331K+ lines per run, 99.8% of log volume)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)


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
    init_db()

    from crci.retrieval.manual_upload_watcher import (
        scan_pdfs,
        import_structured_csv,
        process_search_overrides,
    )

    logger = logging.getLogger(__name__)

    upload_dir = Path("data/manual_uploads")
    if not upload_dir.exists():
        print(f"Upload directory not found: {upload_dir}")
        print("Create it with: mkdir -p data/manual_uploads/{pdfs,structured,search_overrides}")
        return 1

    print(f"Manual import: type={args.type}, validate_only={args.validate_only}")

    total_imported = 0

    with get_session() as session:
        if args.type in ("pdf", "all"):
            pdf_dir = upload_dir / "pdfs"
            if pdf_dir.exists():
                pdfs_found = list(pdf_dir.glob("*.pdf"))
                print(f"\nFound {len(pdfs_found)} PDF files in {pdf_dir}")
                for pdf in pdfs_found:
                    meta_path = pdf.with_suffix(".meta.json")
                    has_meta = "yes" if meta_path.exists() else "no"
                    print(f"  {pdf.name} (meta: {has_meta})")

                if not args.validate_only and pdfs_found:
                    results = scan_pdfs(session, pdf_dir)
                    print(f"  Registered {len(results)} PDFs for extraction")
                    total_imported += len(results)
            else:
                print(f"\nNo PDF directory: {pdf_dir}")

        if args.type in ("csv", "all"):
            csv_dir = upload_dir / "structured"
            if csv_dir.exists():
                # rglob supports per-paper subfolders: structured/[doi-slug]/*.csv
                csvs_found = list(csv_dir.rglob("*.csv"))
                print(f"\nFound {len(csvs_found)} CSV files in {csv_dir} (recursive)")
                for csv_file in csvs_found:
                    print(f"  {csv_file.relative_to(csv_dir)}")

                if not args.validate_only and csvs_found:
                    for csv_file in csvs_found:
                        results = import_structured_csv(
                            session, csv_file, validate_only=args.validate_only
                        )
                        imported = results.csvs_imported if hasattr(results, "csvs_imported") else 0
                        if results.errors:
                            for err in results.errors:
                                print(f"  ERROR [{csv_file.name}]: {err}")
                        elif results.warnings:
                            for w in results.warnings:
                                print(f"  WARN [{csv_file.name}]: {w}")
                        else:
                            print(f"  OK [{csv_file.name}]: processed {imported} rows")
                        total_imported += imported
            else:
                print(f"\nNo structured directory: {csv_dir}")

        if args.type in ("override", "all"):
            override_dir = upload_dir / "search_overrides"
            if override_dir.exists():
                overrides_found = list(override_dir.glob("*.json"))
                print(f"\nFound {len(overrides_found)} override files in {override_dir}")

                if not args.validate_only and overrides_found:
                    results = process_search_overrides(session, override_dir)
                    print(f"  Queued {len(results)} search overrides")
                    total_imported += len(results)
            else:
                print(f"\nNo overrides directory: {override_dir}")

    if args.validate_only:
        print("\nValidation complete (no data imported).")
    else:
        print(f"\nImport complete. Total items processed: {total_imported}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
