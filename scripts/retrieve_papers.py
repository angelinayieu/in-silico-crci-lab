#!/usr/bin/env python3
"""
Retrieve full-text papers by DOI using the 8-source retrieval chain.

Resolves DOI → PMID / PMCID / arXiv / OpenAlex IDs, downloads PDF/XML
from the best available open-access source, validates content quality,
and stages retrieved files for the P0 triage pipeline.

Usage:
    # Retrieve a single paper by DOI
    python scripts/retrieve_papers.py --doi "10.1371/journal.pone.0185059"

    # Resolve identifiers only (no download)
    python scripts/retrieve_papers.py --doi "10.1002/pon.4370" --resolve-only

    # Process queued papers from acquisition_queue_v1
    python scripts/retrieve_papers.py --batch --limit 10

    # Retry previously failed papers
    python scripts/retrieve_papers.py --retry-failed --limit 5

    # Show queue status summary
    python scripts/retrieve_papers.py --status

    # Dry run (resolve + show plan, no download)
    python scripts/retrieve_papers.py --doi "10.1002/pon.4370" --dry-run

    # Verbose logging
    python scripts/retrieve_papers.py --doi "10.1002/pon.4370" --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
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

from sqlalchemy import text

from crci.shared.db import get_session, init_db
from crci.retrieval.fulltext_retriever import FulltextRetriever
from crci.retrieval.id_resolver import resolve_doi
from crci.retrieval.models import RetrievalStatus

logger = logging.getLogger(__name__)


# ── Logging ──────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy loggers
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# ── Status display ───────────────────────────────────────────

_STATUS_ICONS = {
    "retrieved": "✅",
    "dispatched": "📤",
    "queued": "⏳",
    "failed": "❌",
    "extracted": "🔬",
}


def _cmd_status(engine) -> int:
    """Show summary of acquisition queue status."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT status, COUNT(*) as cnt "
            "FROM acquisition_queue_v1 "
            "GROUP BY status ORDER BY cnt DESC"
        )).fetchall()

    if not rows:
        print("Acquisition queue is empty.")
        return 0

    print("\n" + "=" * 50)
    print("ACQUISITION QUEUE STATUS")
    print("=" * 50)
    total = 0
    for status, cnt in rows:
        icon = _STATUS_ICONS.get(status, "❓")
        print(f"  {icon} {status:<15} {cnt:>5}")
        total += cnt
    print(f"  {'':>2} {'TOTAL':<15} {total:>5}")
    print("=" * 50)
    return 0


# ── Resolve-only ─────────────────────────────────────────────

def _cmd_resolve(doi: str) -> int:
    """Resolve DOI to cross-referenced IDs without downloading."""
    print(f"\nResolving identifiers for: {doi}")
    print("-" * 50)

    resolved = resolve_doi(doi)

    print(f"  DOI:        {resolved.doi}")
    print(f"  PMID:       {resolved.pmid or '—'}")
    print(f"  PMCID:      {resolved.pmcid or '—'}")
    print(f"  arXiv ID:   {resolved.arxiv_id or '—'}")
    print(f"  OpenAlex:   {resolved.openalex_id or '—'}")
    print(f"  OA status:  {resolved.oa_status.value}")
    print(f"  Best OA URL:{resolved.best_oa_pdf_url or '—'}")
    print(f"  Publisher:  {resolved.publisher or '—'}")
    print(f"  Title:      {resolved.title or '—'}")
    print(f"  Journal:    {resolved.journal or '—'}")
    print(f"  Year:       {resolved.year or '—'}")
    return 0


# ── Single DOI retrieval ─────────────────────────────────────

def _cmd_retrieve_doi(doi: str, dry_run: bool = False, title: str | None = None) -> int:
    """Retrieve a single paper by DOI."""
    if dry_run:
        print(f"\n[DRY RUN] Would retrieve: {doi}")
        resolved = resolve_doi(doi)
        print(f"  Resolved PMCID: {resolved.pmcid or '—'}")
        print(f"  Resolved arXiv: {resolved.arxiv_id or '—'}")
        print(f"  OA status:      {resolved.oa_status.value}")
        print(f"  Best URL:       {resolved.best_oa_pdf_url or '—'}")
        print(f"  Title:          {resolved.title or '—'}")
        print("\n  Sources that would be tried (in order):")
        from crci.shared import config
        for i, src in enumerate(config.FULLTEXT_SOURCE_PRIORITY, 1):
            print(f"    {i}. {src}")
        return 0

    db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{_project_root}/crci_dev.db"
    os.environ.setdefault("DATABASE_URL", db_url)
    engine = init_db(db_url)

    with get_session() as session:
        retriever = FulltextRetriever(session)
        start = time.monotonic()
        result = retriever.retrieve_by_doi(doi, title=title, stage=True)
        elapsed = time.monotonic() - start

    _print_result(doi, result, elapsed)
    return 0 if result.status == RetrievalStatus.RETRIEVED else 1


def _print_result(doi: str, result, elapsed: float) -> None:
    """Pretty-print retrieval result."""
    icon = {
        RetrievalStatus.RETRIEVED: "✅",
        RetrievalStatus.ABSTRACT_ONLY: "📄",
        RetrievalStatus.FAILED: "❌",
    }.get(result.status, "❓")

    print(f"\n{'=' * 60}")
    print(f"{icon} RETRIEVAL RESULT: {doi}")
    print(f"{'=' * 60}")
    print(f"  Status:      {result.status.value}")
    print(f"  Source:      {result.source_used or '—'}")
    print(f"  Format:      {result.retrieval_format or '—'}")
    print(f"  Cache path:  {result.cache_path or '—'}")
    print(f"  Preprint:    {'yes' if result.is_preprint else 'no'}")
    print(f"  Elapsed:     {elapsed:.1f}s")

    if result.attempts:
        print(f"\n  Attempts ({len(result.attempts)}):")
        for a in result.attempts:
            status_icon = "✓" if a.status == "success" else "✗"
            dur = f"{a.duration_ms}ms" if a.duration_ms else "—"
            err = f" — {a.error}" if a.error else ""
            print(f"    [{status_icon}] {a.source:<20} {dur:>8}{err}")

    if result.validation:
        v = result.validation
        valid_icon = "✓" if v.valid else "✗"
        print(f"\n  Content validation [{valid_icon}]:")
        print(f"    Text length:  {v.text_length:,} chars")
        print(f"    Title match:  {v.title_match_score:.0f}%")
        print(f"    Has abstract: {'yes' if v.has_abstract else 'no'}")
        print(f"    Has refs:     {'yes' if v.has_references else 'no'}")
        print(f"    Pages:        {v.page_count or '—'}")
        if v.issues:
            for issue in v.issues:
                print(f"    ⚠ {issue}")

    print(f"{'=' * 60}")


# ── Batch retrieval from queue ───────────────────────────────

def _cmd_batch(limit: int, retry_failed: bool = False) -> int:
    """Process queued papers from acquisition_queue_v1."""
    db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{_project_root}/crci_dev.db"
    os.environ.setdefault("DATABASE_URL", db_url)
    engine = init_db(db_url)

    # Query papers to process
    if retry_failed:
        where = "WHERE status = 'failed'"
        label = "failed"
    else:
        where = "WHERE status = 'queued'"
        label = "queued"

    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT candidate_doi, candidate_title "
            f"FROM acquisition_queue_v1 "
            f"{where} "
            f"ORDER BY aps_score DESC NULLS LAST "
            f"LIMIT :limit"
        ), {"limit": limit}).fetchall()

    if not rows:
        print(f"No {label} papers in queue.")
        return 0

    print(f"\nProcessing {len(rows)} {label} paper(s)...")
    print("-" * 60)

    succeeded = 0
    failed = 0

    with get_session() as session:
        retriever = FulltextRetriever(session)
        for i, (doi, title) in enumerate(rows, 1):
            if not doi:
                logger.warning("Skipping queue row with no DOI")
                continue

            print(f"\n[{i}/{len(rows)}] {doi}")
            if title:
                print(f"         {title[:70]}...")

            start = time.monotonic()
            try:
                result = retriever.retrieve_by_doi(doi, title=title, stage=True)
                elapsed = time.monotonic() - start

                if result.status == RetrievalStatus.RETRIEVED:
                    print(f"  ✅ Retrieved via {result.source_used} ({elapsed:.1f}s)")
                    succeeded += 1
                elif result.status == RetrievalStatus.ABSTRACT_ONLY:
                    print(f"  📄 Abstract only ({elapsed:.1f}s)")
                    failed += 1
                else:
                    print(f"  ❌ Failed ({elapsed:.1f}s)")
                    failed += 1
            except Exception as exc:
                elapsed = time.monotonic() - start
                print(f"  ❌ Error ({elapsed:.1f}s): {exc}")
                failed += 1

    print(f"\n{'=' * 60}")
    print(f"BATCH COMPLETE: {succeeded} retrieved, {failed} failed of {len(rows)} total")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


# ── CLI entry point ──────────────────────────────────────────

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Retrieve full-text papers via 8-source chain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--doi",
        type=str,
        help="DOI to retrieve (e.g. '10.1371/journal.pone.0185059')",
    )
    group.add_argument(
        "--batch",
        action="store_true",
        help="Process queued papers from acquisition_queue_v1",
    )
    group.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed papers",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Show acquisition queue status summary",
    )

    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Expected title (for content validation, used with --doi)",
    )
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Only resolve identifiers, don't download (used with --doi)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without downloading",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max papers to process in batch mode (default: 10)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    # Route to subcommand
    if args.status:
        db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{_project_root}/crci_dev.db"
        os.environ.setdefault("DATABASE_URL", db_url)
        engine = init_db(db_url)
        return _cmd_status(engine)

    if args.doi and args.resolve_only:
        return _cmd_resolve(args.doi)

    if args.doi:
        return _cmd_retrieve_doi(args.doi, dry_run=args.dry_run, title=args.title)

    if args.batch or args.retry_failed:
        return _cmd_batch(args.limit, retry_failed=args.retry_failed)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
