#!/usr/bin/env python3
"""
Process queued hop candidates from acquisition_queue_v1.

This script bridges the gap between hop_discoverer (which queues constituent
studies) and the extraction pipeline (which processes PDFs). It:

1. Reads queued candidates from acquisition_queue_v1 (status='queued')
2. Resolves PMIDs → DOI + PMCID via NCBI ID converter
3. Attempts PDF retrieval via the full 8-source FulltextRetriever chain:
   OpenAlex → Europe PMC → PMC XML → Unpaywall → arXiv → CORE →
   Semantic Scholar → manual
4. For retrieved PDFs: runs the full extraction pipeline
5. Updates queue status: 'retrieved'/'extracted'/'failed'

Usage:
    python scripts/process_hop_queue.py --max-papers 5 --verbose
    python scripts/process_hop_queue.py --resolve-only   # Just resolve IDs, don't retrieve
    python scripts/process_hop_queue.py --dry-run         # Show plan without executing

Requires:
    - ANTHROPIC_API_KEY in .env (for extraction)
    - Network access (for NCBI, Europe PMC, Unpaywall, etc.)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
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
from crci.shared.models.tables import AcquisitionQueue
from crci.retrieval.fulltext_retriever import FulltextRetriever
from crci.retrieval.models import RetrievalStatus

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  NCBI E-UTILITIES HELPERS
# ═══════════════════════════════════════════════════════════════

_NCBI_IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
_NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_NCBI_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EUROPE_PMC_FT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
_UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}"
_RATE_LIMIT_SLEEP = 0.4  # NCBI requests max ~3/sec without API key


def resolve_pmid_to_ids(pmid: str) -> dict[str, str]:
    """Resolve PMID → DOI + PMCID via PubMed E-utilities + NCBI ID Converter.

    Uses two approaches:
    1. PubMed esummary → articleids (most reliable for DOIs)
    2. NCBI ID Converter (for PMCIDs)

    Returns:
        Dict with keys: pmid, doi, pmcid (may be empty strings).
    """
    import requests

    result = {"pmid": pmid, "doi": "", "pmcid": ""}

    # Source 1: PubMed esummary articleids (best for DOI resolution)
    try:
        time.sleep(_RATE_LIMIT_SLEEP)
        resp = requests.get(
            _NCBI_ESUMMARY_URL,
            params={
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
                "tool": "crci-hop-processor",
                "email": "crci@research.example.com",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        doc = data.get("result", {}).get(pmid, {})
        for aid in doc.get("articleids", []):
            if aid.get("idtype") == "doi" and not result["doi"]:
                result["doi"] = aid.get("value", "")
            if aid.get("idtype") == "pmc" and not result["pmcid"]:
                result["pmcid"] = aid.get("value", "")

    except Exception as exc:
        logger.warning("PubMed esummary failed for PMID %s: %s", pmid, exc)

    # Source 2: NCBI ID Converter (backup, good for PMCIDs)
    if not result["pmcid"]:
        try:
            time.sleep(_RATE_LIMIT_SLEEP)
            resp = requests.get(
                _NCBI_IDCONV_URL,
                params={
                    "ids": pmid,
                    "format": "json",
                    "tool": "crci-hop-processor",
                    "email": "crci@research.example.com",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for record in data.get("records", []):
                if record.get("pmid") == pmid:
                    if not result["doi"]:
                        result["doi"] = record.get("doi", "")
                    if not result["pmcid"]:
                        result["pmcid"] = record.get("pmcid", "")
                    break

        except Exception as exc:
            logger.warning("NCBI ID conversion failed for PMID %s: %s", pmid, exc)

    return result


def fetch_pubmed_metadata(pmid: str) -> dict[str, str]:
    """Fetch title + abstract from PubMed via E-utilities.

    Returns:
        Dict with keys: title, abstract, journal, year.
    """
    import requests

    result = {"title": "", "abstract": "", "journal": "", "year": ""}

    try:
        time.sleep(_RATE_LIMIT_SLEEP)
        resp = requests.get(
            _NCBI_ESUMMARY_URL,
            params={
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
                "tool": "crci-hop-processor",
                "email": "crci@research.example.com",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        doc = data.get("result", {}).get(pmid, {})
        result["title"] = doc.get("title", "")
        result["journal"] = doc.get("fulljournalname", doc.get("source", ""))

        # Extract year from pubdate or sortpubdate
        pubdate = doc.get("pubdate", "")
        if pubdate:
            result["year"] = pubdate[:4]

    except Exception as exc:
        logger.warning("PubMed metadata fetch failed for PMID %s: %s", pmid, exc)

    return result


def try_retrieve_pdf(
    pmid: str,
    doi: str,
    pmcid: str,
    output_dir: Path,
) -> Path | None:
    """Attempt PDF retrieval via Europe PMC → Unpaywall.

    Args:
        pmid: PubMed ID.
        doi: DOI (may be empty).
        pmcid: PMC ID (may be empty).
        output_dir: Directory to save PDF.

    Returns:
        Path to downloaded PDF, or None if not available.
    """
    import requests

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"pmid_{pmid}.pdf"

    # Already downloaded?
    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        logger.info("PDF already cached: %s", pdf_path)
        return pdf_path

    # Source 1: Europe PMC full-text XML → we'd need XML, but pipeline expects PDF
    # Let's try the Europe PMC PDF endpoint instead
    if pmcid:
        try:
            time.sleep(_RATE_LIMIT_SLEEP)
            # Europe PMC OA subset can provide PDFs
            # Try the OA web service
            pmc_pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
            resp = requests.get(pmc_pdf_url, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 5000:
                # Validate it looks like a PDF
                if resp.content[:5] == b"%PDF-":
                    pdf_path.write_bytes(resp.content)
                    logger.info(
                        "Retrieved PDF via Europe PMC (%s): %d bytes → %s",
                        pmcid, len(resp.content), pdf_path,
                    )
                    return pdf_path
                else:
                    logger.debug("Europe PMC response not a PDF for %s", pmcid)
            else:
                logger.debug(
                    "Europe PMC PDF not available for %s (status=%d, size=%d)",
                    pmcid, resp.status_code, len(resp.content),
                )
        except Exception as exc:
            logger.debug("Europe PMC PDF retrieval failed for %s: %s", pmcid, exc)

    # Source 2: Unpaywall
    if doi:
        try:
            time.sleep(_RATE_LIMIT_SLEEP)
            resp = requests.get(
                _UNPAYWALL_URL.format(doi=doi),
                params={"email": "crci@research.example.com"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Find best OA location with PDF
                best_url = data.get("best_oa_location", {})
                pdf_url = best_url.get("url_for_pdf") or best_url.get("url")

                if pdf_url:
                    time.sleep(_RATE_LIMIT_SLEEP)
                    pdf_resp = requests.get(
                        pdf_url,
                        timeout=60,
                        allow_redirects=True,
                        headers={"User-Agent": "CRCI-System/1.0 (research; crci@research.example.com)"},
                    )
                    if pdf_resp.status_code == 200 and len(pdf_resp.content) > 5000:
                        if pdf_resp.content[:5] == b"%PDF-":
                            pdf_path.write_bytes(pdf_resp.content)
                            logger.info(
                                "Retrieved PDF via Unpaywall (%s): %d bytes → %s",
                                doi, len(pdf_resp.content), pdf_path,
                            )
                            return pdf_path
                        else:
                            logger.debug("Unpaywall response not a PDF for %s", doi)
                else:
                    logger.debug("No PDF URL in Unpaywall response for %s", doi)
        except Exception as exc:
            logger.debug("Unpaywall retrieval failed for %s: %s", doi, exc)

    # Source 3: PubMed Central direct (for free PMC articles)
    if pmcid:
        try:
            time.sleep(_RATE_LIMIT_SLEEP)
            pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
            resp = requests.get(
                pmc_url,
                timeout=30,
                allow_redirects=True,
                headers={"User-Agent": "CRCI-System/1.0 (research; crci@research.example.com)"},
            )
            if resp.status_code == 200 and len(resp.content) > 5000:
                if resp.content[:5] == b"%PDF-":
                    pdf_path.write_bytes(resp.content)
                    logger.info(
                        "Retrieved PDF via PMC direct (%s): %d bytes → %s",
                        pmcid, len(resp.content), pdf_path,
                    )
                    return pdf_path
        except Exception as exc:
            logger.debug("PMC direct retrieval failed for %s: %s", pmcid, exc)

    logger.warning(
        "No PDF available for PMID %s (doi=%s, pmcid=%s)",
        pmid, doi or "none", pmcid or "none",
    )
    return None


# ═══════════════════════════════════════════════════════════════
#  QUEUE PROCESSING
# ═══════════════════════════════════════════════════════════════


def process_hop_queue(
    max_papers: int = 9,
    resolve_only: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Process queued hop candidates end-to-end.

    Args:
        max_papers: Maximum candidates to process.
        resolve_only: If True, only resolve IDs (don't retrieve/extract).
        dry_run: If True, show plan without executing.
        verbose: Enable debug logging.

    Returns:
        Summary report dict.
    """
    report = {
        "queued": 0,
        "resolved": 0,
        "retrieved": 0,
        "extracted": 0,
        "failed": 0,
        "skipped_no_pmid": 0,
        "details": [],
    }

    init_db()

    with get_session() as session:
        # Fetch queued candidates
        candidates = (
            session.query(AcquisitionQueue)
            .filter(AcquisitionQueue.status == "queued")
            .limit(max_papers)
            .all()
        )
        report["queued"] = len(candidates)

        if not candidates:
            logger.info("No queued hop candidates found.")
            print("No queued hop candidates to process.")
            return report

        print(f"\n{'='*70}")
        print(f"HOP QUEUE PROCESSOR — {len(candidates)} candidates")
        print(f"{'='*70}\n")

        pdf_dir = Path("data/retrieval_cache/hop_pdfs")

        for i, cand in enumerate(candidates, 1):
            pmid = cand.candidate_pmid or ""
            title = cand.candidate_title or ""
            queue_id = cand.queue_id

            detail = {
                "queue_id": queue_id,
                "pmid": pmid,
                "title": title,
                "status": "pending",
            }

            print(f"[{i}/{len(candidates)}] {queue_id}")
            print(f"  PMID: {pmid or '(none)'}")
            print(f"  Title: {title or '(unknown)'}")

            # Skip candidates without PMID
            if not pmid:
                print(f"  ⚠ No PMID — cannot resolve. Skipping.")
                detail["status"] = "skipped_no_pmid"
                report["skipped_no_pmid"] += 1
                report["details"].append(detail)
                continue

            if dry_run:
                print(f"  [DRY RUN] Would resolve PMID {pmid}")
                detail["status"] = "dry_run"
                report["details"].append(detail)
                continue

            # Step 1: Resolve PMID → DOI + PMCID
            print(f"  Resolving PMID {pmid}...", end=" ", flush=True)
            ids = resolve_pmid_to_ids(pmid)
            doi = ids.get("doi", "")
            pmcid = ids.get("pmcid", "")
            print(f"DOI={doi or '(none)'}, PMCID={pmcid or '(none)'}")

            detail["doi"] = doi
            detail["pmcid"] = pmcid

            # Update queue row with resolved IDs
            if doi and not cand.candidate_doi:
                cand.candidate_doi = doi
            cand.updated_at = datetime.now(timezone.utc)

            # Step 1b: Get metadata if title is missing
            if not title:
                print(f"  Fetching metadata...", end=" ", flush=True)
                meta = fetch_pubmed_metadata(pmid)
                title = meta.get("title", "")
                if title:
                    cand.candidate_title = title
                    detail["title"] = title
                    print(f"'{title[:60]}...'")
                else:
                    print("(no title found)")

            report["resolved"] += 1

            if resolve_only:
                cand.retrieval_status = "ids_resolved"
                detail["status"] = "resolved"
                print(f"  ✓ IDs resolved (resolve-only mode)")
                report["details"].append(detail)
                continue

            # Step 2: Retrieve PDF via full 8-source chain
            print(f"  Retrieving via 8-source chain...", end=" ", flush=True)
            retriever = FulltextRetriever(session)
            if doi:
                ret_result = retriever.retrieve_by_doi(doi, title=title, stage=True)
            elif pmid:
                ret_result = retriever.retrieve_by_pmid(pmid, title=title, stage=True, output_dir=pdf_dir)
            else:
                ret_result = None

            if ret_result and ret_result.status == RetrievalStatus.RETRIEVED:
                pdf_path = Path(ret_result.cache_path) if ret_result.cache_path else None
                # Also copy to hop_pdfs dir with standard name
                if pdf_path and pdf_path.exists():
                    hop_copy = pdf_dir / f"pmid_{pmid}.pdf"
                    if not hop_copy.exists():
                        import shutil
                        pdf_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(pdf_path, hop_copy)
                    pdf_path = hop_copy

                source_used = ret_result.source_used or "unknown"
                size = ret_result.file_size_bytes or 0
                print(f"✓ via {source_used} ({size:,} bytes)")
                cand.retrieval_status = "retrieved"
                cand.retrieval_tool = source_used
                cand.status = "retrieved"
                detail["pdf_path"] = str(pdf_path) if pdf_path else ""
                detail["source"] = source_used
                detail["status"] = "retrieved"
                report["retrieved"] += 1

                # Step 3: Run extraction pipeline
                if pdf_path and pdf_path.exists():
                    print(f"  Running extraction pipeline...")
                    success = _run_extraction(pdf_path, pmid, doi, title=title, verbose=verbose)
                    if success:
                        cand.status = "extracted"
                        detail["status"] = "extracted"
                        report["extracted"] += 1
                        print(f"  ✓ Extraction complete")
                    else:
                        detail["status"] = "extraction_failed"
                        report["failed"] += 1
                        print(f"  ✗ Extraction failed")
            else:
                error = ""
                if ret_result:
                    error = ret_result.error_message or f"status={ret_result.status.value}"
                print(f"✗ Not available ({error or 'all sources exhausted'})")
                cand.retrieval_status = "no_fulltext"
                cand.paywall_flagged = True
                detail["status"] = "no_pdf"
                detail["error"] = error
                report["failed"] += 1

            cand.updated_at = datetime.now(timezone.utc)
            report["details"].append(detail)

            # Commit after each candidate so progress isn't lost
            try:
                session.commit()
            except Exception as exc:
                logger.warning("Failed to commit queue update: %s", exc)
                session.rollback()

            print()

    return report


def _create_meta_json(pdf_path: Path, pmid: str, doi: str, title: str = "") -> Path:
    """Create a meta.json for the PDF so the extraction pipeline has context.

    Provides target_edges hints based on the paper title and hop context.
    Since these are constituent studies from a cortisol/HPA meta-analysis,
    we provide cortisol-related target edges to help concept grounding.

    Args:
        pdf_path: Path to the PDF file.
        pmid: PubMed ID.
        doi: DOI (may be empty).
        title: Paper title (for target_edges inference).

    Returns:
        Path to the created meta.json file.
    """
    meta_path = pdf_path.with_suffix(".meta.json")

    # Infer target_edges from title keywords
    target_edges = _infer_target_edges(title)

    meta = {
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "source": "hop_discovery",
        "hop_depth": 1,
        "target_edges": target_edges,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    logger.info(
        "Created meta.json for PMID %s with target_edges=%s",
        pmid, target_edges,
    )
    return meta_path


# Keyword → edge mapping for cortisol/HPA constituent studies
_EDGE_KEYWORD_MAP = {
    "depression": "EDGE_CORTISOL_DEPRESSION",
    "depressive": "EDGE_CORTISOL_DEPRESSION",
    "anxiety": "EDGE_CORTISOL_ANXIETY",
    "fatigue": "EDGE_CORTISOL_FATIGUE",
    "sleep": "EDGE_CORTISOL_SLEEP",
    "cogniti": "EDGE_CORTISOL_COGNITION",
    "memory": "EDGE_CORTISOL_COGNITION",
    "inflamma": "EDGE_CORTISOL_IL6",
    "immune": "EDGE_CORTISOL_IL6",
    "il-6": "EDGE_CORTISOL_IL6",
    "cytokine": "EDGE_CORTISOL_IL6",
}


def _infer_target_edges(title: str) -> list[str]:
    """Infer target_edges from paper title keywords.

    For hop candidates from cortisol/HPA meta-analyses, we can
    narrow down which edges the paper likely provides evidence for.

    Args:
        title: Paper title.

    Returns:
        List of edge_relation_ids (may be empty).
    """
    if not title:
        return []

    title_lower = title.lower()
    edges: set[str] = set()

    for keyword, edge_id in _EDGE_KEYWORD_MAP.items():
        if keyword in title_lower:
            edges.add(edge_id)

    # If cortisol paper but no specific outcome matched, use broad set
    if not edges and ("cortisol" in title_lower or "diurnal" in title_lower):
        edges = {
            "EDGE_CORTISOL_COGNITION",
            "EDGE_CORTISOL_FATIGUE",
            "EDGE_CORTISOL_DEPRESSION",
        }

    return sorted(edges)


def _run_extraction(
    pdf_path: Path,
    pmid: str,
    doi: str,
    title: str = "",
    verbose: bool = False,
) -> bool:
    """Run the extraction pipeline on a retrieved PDF.

    Calls scripts/run_extraction.py as a subprocess so each extraction
    gets a clean state.

    Args:
        pdf_path: Path to the PDF file.
        pmid: PubMed ID (for logging).
        doi: DOI (may be empty).
        verbose: Enable verbose logging.

    Returns:
        True if extraction succeeded.
    """
    # Create meta.json alongside the PDF
    _create_meta_json(pdf_path, pmid, doi, title=title)

    cmd = [
        sys.executable,
        str(_project_root / "scripts" / "run_extraction.py"),
        str(pdf_path),
        "--skip-idempotency",
    ]
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per paper
            cwd=str(_project_root),
        )

        if result.returncode == 0:
            logger.info("Extraction succeeded for PMID %s", pmid)
            return True
        else:
            logger.warning(
                "Extraction failed for PMID %s (exit=%d): %s",
                pmid,
                result.returncode,
                result.stderr[-500:] if result.stderr else "no stderr",
            )
            # Print last few lines of output for debugging
            if result.stdout:
                lines = result.stdout.strip().split("\n")
                for line in lines[-5:]:
                    print(f"    | {line}")
            if result.stderr:
                lines = result.stderr.strip().split("\n")
                for line in lines[-3:]:
                    print(f"    ! {line}")
            return False

    except subprocess.TimeoutExpired:
        logger.warning("Extraction timed out for PMID %s (>300s)", pmid)
        print(f"    ! Timed out after 300 seconds")
        return False
    except Exception as exc:
        logger.warning("Extraction error for PMID %s: %s", pmid, exc)
        return False


def _print_report(report: dict) -> None:
    """Print summary report."""
    print(f"\n{'='*70}")
    print("HOP QUEUE PROCESSING REPORT")
    print(f"{'='*70}")
    print(f"  Queued candidates:     {report['queued']}")
    print(f"  IDs resolved:          {report['resolved']}")
    print(f"  PDFs retrieved:        {report['retrieved']}")
    print(f"  Successfully extracted: {report['extracted']}")
    print(f"  Failed:                {report['failed']}")
    print(f"  Skipped (no PMID):     {report['skipped_no_pmid']}")

    if report["details"]:
        print(f"\n  Per-candidate details:")
        for d in report["details"]:
            pmid = d.get("pmid", "?")
            title = d.get("title", "")[:50]
            status = d.get("status", "?")
            icon = {"extracted": "✓", "retrieved": "→", "resolved": "◎",
                    "no_pdf": "✗", "skipped_no_pmid": "⚠", "dry_run": "…",
                    "extraction_failed": "✗"}.get(status, "?")
            print(f"    {icon} PMID {pmid:>10s} [{status:>18s}] {title}")
    print(f"{'='*70}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process queued hop candidates: resolve → retrieve → extract",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=9,
        help="Maximum candidates to process (default: 9)",
    )
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Only resolve PMIDs to DOIs/PMCIDs, don't retrieve PDFs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show plan without executing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    report = process_hop_queue(
        max_papers=args.max_papers,
        resolve_only=args.resolve_only,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    _print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
