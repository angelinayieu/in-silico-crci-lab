#!/usr/bin/env python3
"""
Show papers that need manual retrieval (paywalled / failed download).

Provides researchers with:
  - Which papers the system needs but couldn't download
  - DOI, title, why each paper is needed (target edges)
  - Instructions for manual acquisition
  - Status of all papers in the acquisition queue

Usage:
    python scripts/show_paywalled.py                  # Show papers needing manual action
    python scripts/show_paywalled.py --all             # Show entire acquisition queue
    python scripts/show_paywalled.py --mark-retrieved DOI  # Mark a manually downloaded paper
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{PROJECT_ROOT}/crci_dev.db"
os.environ["DATABASE_URL"] = db_url

from sqlalchemy import text

from crci.shared.db import init_db


_STATUS_ICONS = {
    "retrieved": "✅",
    "dispatched": "📤",
    "queued": "⏳",
    "failed": "❌",
}


def show_queue(engine, show_all: bool = False) -> None:
    """Display the acquisition queue with researcher-friendly formatting."""
    with engine.connect() as conn:
        if show_all:
            query = text(
                "SELECT queue_id, candidate_doi, candidate_pmid, candidate_title, "
                "aps_score, status, retrieval_tool, hop_source_study_id, "
                "paywall_flagged, target_edge_ids_json "
                "FROM acquisition_queue_v1 ORDER BY aps_score DESC"
            )
        else:
            query = text(
                "SELECT queue_id, candidate_doi, candidate_pmid, candidate_title, "
                "aps_score, status, retrieval_tool, hop_source_study_id, "
                "paywall_flagged, target_edge_ids_json "
                "FROM acquisition_queue_v1 "
                "WHERE status IN ('dispatched', 'queued', 'failed') "
                "ORDER BY aps_score DESC"
            )

        rows = conn.execute(query).fetchall()

        if not rows:
            print("\n  No papers need manual retrieval. Queue is clean.\n")
            return

        # Group by status
        by_status: dict[str, list] = {}
        for row in rows:
            status = row[5]
            by_status.setdefault(status, []).append(row)

        # Summary
        print()
        print("=" * 78)
        print("  ACQUISITION QUEUE — Papers Needing Attention")
        print("=" * 78)
        total = len(rows)
        for status in ["dispatched", "failed", "queued", "retrieved"]:
            count = len(by_status.get(status, []))
            if count > 0:
                icon = _STATUS_ICONS.get(status, "?")
                print(f"  {icon} {status.upper():12s} {count} papers")
        print(f"  {'─' * 40}")
        print(f"  Total: {total} papers")
        print()

        # Detail for actionable papers
        for status in ["dispatched", "failed", "queued"]:
            papers = by_status.get(status, [])
            if not papers:
                continue

            icon = _STATUS_ICONS.get(status, "?")
            print(f"  {icon} {status.upper()} ({len(papers)} papers)")
            print(f"  {'─' * 70}")

            for row in papers:
                doi = row[1] or "no-doi"
                pmid = row[2] or "—"
                title = row[3] or "Unknown"
                aps = row[4] or 0
                tool = row[6] or "—"
                hop_source = row[7] or "—"
                paywall = row[8]
                target_edges = row[9]

                # Truncate title
                if len(title) > 65:
                    title = title[:62] + "..."

                print(f"\n    DOI:    {doi}")
                print(f"    PMID:   {pmid}")
                print(f"    Title:  {title}")
                print(f"    APS:    {aps:.3f}  |  Source: {hop_source}  |  Tool: {tool}")

                if target_edges:
                    try:
                        edges = json.loads(target_edges) if isinstance(target_edges, str) else target_edges
                        if edges:
                            print(f"    Needed for edges: {', '.join(edges)}")
                    except (json.JSONDecodeError, TypeError):
                        pass

                if paywall:
                    print("    ⚠️  PAYWALL DETECTED")

            print()

        # Show retrieved papers if --all
        if show_all:
            retrieved = by_status.get("retrieved", [])
            if retrieved:
                print(f"  ✅ RETRIEVED ({len(retrieved)} papers)")
                print(f"  {'─' * 70}")
                for row in retrieved:
                    doi = row[1] or "no-doi"
                    title = row[3] or "Unknown"
                    if len(title) > 65:
                        title = title[:62] + "..."
                    print(f"    {doi:45s} {title}")
                print()

        # Instructions
        print("=" * 78)
        print("  HOW TO MANUALLY RETRIEVE A PAPER")
        print("=" * 78)
        print("""
  1. Use your institutional access to download the PDF:
     - PubMed: https://pubmed.ncbi.nlm.nih.gov/<PMID>
     - DOI:    https://doi.org/<DOI>
     - Or use your library's interlibrary loan (ILL) service

  2. Save the PDF to:
     data/manual_uploads/pdfs/<short_name>.pdf
     Example: data/manual_uploads/pdfs/johns2016.pdf

  3. Create a companion metadata file:
     data/manual_uploads/pdfs/<short_name>.meta.json
     Contents:
     {
       "doi": "<DOI>",
       "pmid": "<PMID>",
       "title": "<paper title>",
       "target_edges": ["ER_EDGE_ID_1", "ER_EDGE_ID_2"],
       "priority": "high"
     }

  4. Mark it as retrieved:
     python scripts/show_paywalled.py --mark-retrieved <DOI>

  5. Import and extract:
     python scripts/run_manual_import.py --type pdf
""")


def mark_retrieved(engine, doi: str) -> None:
    """Mark a paper as manually retrieved in the acquisition queue."""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE acquisition_queue_v1 "
                "SET status = 'retrieved', retrieval_tool = 'manual' "
                "WHERE candidate_doi = :doi"
            ),
            {"doi": doi},
        )
        if result.rowcount > 0:
            print(f"\n  ✅ Marked {doi} as retrieved ({result.rowcount} row(s) updated)")
        else:
            print(f"\n  ❌ DOI {doi} not found in acquisition queue")
            print("     Check the DOI and try again, or add it manually first.")


def show_edge_coverage(engine) -> None:
    """Show which edges have evidence and which need papers."""
    with engine.connect() as conn:
        # Get all edge definitions
        edges = conn.execute(
            text(
                "SELECT edge_relation_id, node_x, node_y, edge_family "
                "FROM edge_relations_definitions_v1 "
                "WHERE active = 1 ORDER BY edge_family, edge_relation_id"
            )
        ).fetchall()

        # Get edges that have evidence
        covered = set()
        result = conn.execute(
            text("SELECT DISTINCT edge_relation_id FROM edge_evidence_v1")
        )
        for row in result:
            covered.add(row[0])

        print()
        print("=" * 78)
        print("  EDGE COVERAGE REPORT")
        print("=" * 78)
        print(f"  {len(covered)}/{len(edges)} edges have at least one evidence row")
        print()

        current_family = ""
        for edge in edges:
            eid, nx, ny, family = edge
            if family != current_family:
                current_family = family
                print(f"\n  [{family}]")

            icon = "✅" if eid in covered else "❌"
            print(f"    {icon} {eid:45s} {nx} → {ny}")

        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show papers needing manual retrieval",
    )
    parser.add_argument("--all", action="store_true", help="Show all papers including retrieved")
    parser.add_argument("--mark-retrieved", type=str, help="Mark a DOI as manually retrieved")
    parser.add_argument("--coverage", action="store_true", help="Show edge evidence coverage")
    args = parser.parse_args()

    engine = init_db()

    if args.mark_retrieved:
        mark_retrieved(engine, args.mark_retrieved)
        return 0

    if args.coverage:
        show_edge_coverage(engine)
        return 0

    show_queue(engine, show_all=args.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
