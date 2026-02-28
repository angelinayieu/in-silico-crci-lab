#!/usr/bin/env python3
"""
Batch retrieve and extract PDFs from a list of URLs.

Parses URLs to extract DOIs, PMIDs, PMCIDs, and other identifiers,
then uses the retrieval pipeline to download and stage papers.

Usage:
    python scripts/batch_retrieve_from_urls.py --urls "url1" "url2" "url3"
    python scripts/batch_retrieve_from_urls.py --file urls.txt --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

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

from crci.retrieval.id_resolver import resolve_doi, resolve_pmid, resolve_pmcid
from crci.retrieval.fulltext_retriever import FulltextRetriever

logger = logging.getLogger(__name__)


class URLIdentifierExtractor:
    """Extract DOI, PMID, or PMCID from various URL formats."""

    @staticmethod
    def extract_from_url(url: str) -> dict[str, Optional[str]]:
        """
        Extract identifier(s) from URL.
        
        Returns:
            dict with keys: doi, pmid, pmcid, pii, preprint_id, title_hint
        """
        result = {
            "doi": None,
            "pmid": None,
            "pmcid": None,
            "pii": None,
            "preprint_id": None,
            "title_hint": None,
            "url": url,
        }

        # Remove fragment and normalize
        url = url.split("#")[0].strip()

        # ─ DOI extraction patterns ─
        
        # Pattern 1: DOI in URL path (Wiley, Nature, Elsevier)
        # Examples: 10.1002/hbm.25800, 10.1038/s41598-018-32257-w
        doi_match = re.search(r'10\.\d{4,}/[^\s"\'<>?&]+', url)
        if doi_match:
            result["doi"] = doi_match.group()
            return result

        # Pattern 2: journal.pone style with /e
        # Example: cancer.jmir.org/2019/2/e13150/ → 10.2196/13150
        if "jmir.org" in url.lower() or "cancer.jmir.org" in url.lower():
            match = re.search(r'/e(\d+)/?$', url)
            if match:
                result["doi"] = f"10.2196/{match.group(1)}"
                return result

        # Pattern 3: Nature format URLs
        if "nature.com/articles/" in url:
            match = re.search(r'/articles/(s\d+-\d{3}-[-\d]+)', url)
            if match:
                result["doi"] = f"10.1038/{match.group(1)}"
                return result

        # ─ PMCID extraction ─
        
        # Pattern: PMC style in URLs
        pmcid_match = re.search(r'PMC(\d+)', url)
        if pmcid_match:
            result["pmcid"] = f"PMC{pmcid_match.group(1)}"
            return result

        # ─ PMID extraction ─
        
        # Pattern: PubMed PMID in URL
        pmid_match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/', url)
        if pmid_match:
            result["pmid"] = pmid_match.group(1)
            return result

        # ─ PII extraction ─
        
        # Pattern: ScienceDirect PII
        pii_match = re.search(r'pii/([S0-9A-Z]+)', url, re.IGNORECASE)
        if pii_match:
            result["pii"] = pii_match.group(1)
            return result

        # ─ Preprint ID extraction ─
        
        # Pattern: Preprints.org
        if "preprints.org" in url:
            match = re.search(r'/manuscript/(\d+\.\d+)', url)
            if match:
                result["preprint_id"] = match.group(1)
                return result

        # ─ MDPI format ─
        
        if "mdpi.com" in url:
            # Extract article info for MDPI
            match = re.search(r'mdpi\.com/([^/]+)/(\d+)/(\d+)/(\d+)', url)
            if match:
                journal, vol, issue, article = match.groups()
                result["title_hint"] = f"MDPI {journal} {vol}({issue}):{article}"
                # Try to resolve via DOI if available in supplementary lookup
                return result

        # ─ Other institutional/special repository formats ─
        
        if "semanticscholar.org/paper/" in url:
            match = re.search(r'/paper/([^/]+)/([a-f0-9]+)', url)
            if match:
                title_hint = match.group(1).replace("-", " ")
                result["title_hint"] = title_hint
                return result

        if "uknowledge.uky.edu" in url or "researchgate.net" in url:
            # These require special handling; return what we have
            result["title_hint"] = url
            return result

        return result


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def retrieve_single_paper(
    doi: Optional[str] = None,
    pmid: Optional[str] = None,
    pmcid: Optional[str] = None,
    pii: Optional[str] = None,
    retriever: Optional[FulltextRetriever] = None,
    verbose: bool = False,
) -> tuple[bool, str]:
    """
    Attempt retrieval using priority order: DOI → PMID → PMCID → PII.
    
    Returns:
        (success: bool, message: str)
    """
    if retriever is None:
        retriever = FulltextRetriever()

    if doi:
        logger.info(f"Retrieving by DOI: {doi}")
        try:
            result = retriever.retrieve_by_doi(doi)
            if result:
                return True, f"Retrieved PDF via DOI {doi}: {result.cache_path}"
        except Exception as e:
            logger.warning(f"DOI retrieval failed: {e}")

    if pmid:
        logger.info(f"Retrieving by PMID: {pmid}")
        try:
            result = retriever.retrieve_by_pmid(pmid)
            if result:
                return True, f"Retrieved PDF via PMID {pmid}: {result.cache_path}"
        except Exception as e:
            logger.warning(f"PMID retrieval failed: {e}")

    if pmcid:
        logger.info(f"Retrieving by PMCID: {pmcid}")
        try:
            result = retriever.retrieve_by_pmcid(pmcid)
            if result:
                return True, f"Retrieved PDF via PMCID {pmcid}: {result.cache_path}"
        except Exception as e:
            logger.warning(f"PMCID retrieval failed: {e}")

    if pii:
        logger.info(f"Attempting PII retrieval: {pii}")
        # PII requires cross-reference to DOI via ScienceDirect APIs
        # This is deferred for now
        logger.warning(f"PII resolution not yet implemented: {pii}")
        return False, f"PII {pii} requires special handling"

    return False, "No applicable identifier found"


def main():
    parser = argparse.ArgumentParser(
        description="Batch retrieve papers from URLs",
    )
    parser.add_argument("--urls", nargs="+", help="URLs to retrieve")
    parser.add_argument("--file", help="File with one URL per line")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay between requests (seconds)"
    )
    parser.add_argument(
        "--max-workers", type=int, default=4, help="Max concurrent retrievals"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Gather URLs
    urls = []
    if args.urls:
        urls.extend(args.urls)
    if args.file:
        with open(args.file) as f:
            urls.extend(line.strip() for line in f if line.strip())

    if not urls:
        logger.error("No URLs provided. Use --urls or --file.")
        sys.exit(1)

    logger.info(f"Processing {len(urls)} URLs")

    extractor = URLIdentifierExtractor()
    retriever = FulltextRetriever()

    results = []
    for idx, url in enumerate(urls, 1):
        logger.info(f"\n[{idx}/{len(urls)}] Processing: {url}")
        
        ids = extractor.extract_from_url(url)
        logger.debug(f"Extracted identifiers: {ids}")

        success, msg = retrieve_single_paper(
            doi=ids["doi"],
            pmid=ids["pmid"],
            pmcid=ids["pmcid"],
            pii=ids["pii"],
            retriever=retriever,
            verbose=args.verbose,
        )

        results.append({
            "url": url,
            "identifiers": ids,
            "success": success,
            "message": msg,
        })
        logger.info(f"Status: {msg}")

        if idx < len(urls):
            time.sleep(args.delay)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("RETRIEVAL SUMMARY")
    logger.info("=" * 80)

    success_count = sum(1 for r in results if r["success"])
    logger.info(f"Successfully retrieved: {success_count}/{len(results)}")

    for r in results:
        status = "✓" if r["success"] else "✗"
        logger.info(f"{status} {r['url'][:60]}")
        if not r["success"]:
            logger.info(f"   → {r['message']}")

    # Write report
    report_path = Path(_project_root) / "data" / "retrieval_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nReport saved: {report_path}")

    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
