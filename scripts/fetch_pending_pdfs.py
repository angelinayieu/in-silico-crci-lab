"""
PDF Fetcher for Pending Downloads

Scans data/manual_uploads/pdfs/*.meta.json for papers with
pdf_status == "PENDING_DOWNLOAD", then attempts to fetch PDFs
from open-access sources (Europe PMC, Unpaywall, PubMed Central).

Usage:
    python scripts/fetch_pending_pdfs.py [--email your@email.com]

The --email flag is required for Unpaywall API (their terms of service).
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "manual_uploads" / "pdfs"

# Source priority (per AUTOMATED_RETRIEVAL_PLAN.md):
# 1. Europe PMC (structured XML/PDF)
# 2. Unpaywall (legal open-access PDFs)
# 3. PubMed Central direct


def doi_to_slug(doi: str) -> str:
    """Convert DOI to filesystem-safe slug: 10.1200/JCO.2014.59.0290 -> 10.1200_JCO.2014.59.0290"""
    return doi.replace("/", "_")


def fetch_url(url: str, timeout: int = 30) -> bytes | None:
    """Fetch URL with retries and exponential backoff."""
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CRCI-System/1.0"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read()
        except Exception as e:
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"  Retry {attempt+1}/3 in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  Failed after 4 attempts: {e}")
                return None


def try_europe_pmc(pmid: str | None) -> bytes | None:
    """Try Europe PMC for free full-text PDF."""
    if not pmid:
        return None
    print(f"  Trying Europe PMC (PMID {pmid})...")
    # First get PMCID from PMID
    api_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:{pmid}&format=json"
    data = fetch_url(api_url)
    if not data:
        return None
    try:
        result = json.loads(data)
        hits = result.get("resultList", {}).get("result", [])
        if not hits:
            return None
        pmcid = hits[0].get("pmcid")
        if not pmcid:
            print(f"  No PMCID found for PMID {pmid}")
            return None
        print(f"  Found PMCID: {pmcid}")
        pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
        return fetch_url(pdf_url)
    except (json.JSONDecodeError, KeyError):
        return None


def try_unpaywall(doi: str, email: str) -> bytes | None:
    """Try Unpaywall for open-access PDF."""
    print(f"  Trying Unpaywall...")
    api_url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    data = fetch_url(api_url)
    if not data:
        return None
    try:
        result = json.loads(data)
        best_oa = result.get("best_oa_location")
        if not best_oa:
            print("  No open-access location found")
            return None
        pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")
        if not pdf_url:
            print("  No PDF URL in OA location")
            return None
        print(f"  Found OA PDF: {pdf_url}")
        return fetch_url(pdf_url, timeout=60)
    except (json.JSONDecodeError, KeyError):
        return None


def try_pmc_direct(pmid: str | None) -> bytes | None:
    """Try PubMed Central direct PDF link."""
    if not pmid:
        return None
    print(f"  Trying PMC direct...")
    # Convert PMID to PMCID via NCBI
    api_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
    data = fetch_url(api_url)
    if not data:
        return None
    try:
        result = json.loads(data)
        records = result.get("records", [])
        if not records:
            return None
        pmcid = records[0].get("pmcid")
        if not pmcid:
            print(f"  No PMCID for PMID {pmid}")
            return None
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
        return fetch_url(pdf_url, timeout=60)
    except (json.JSONDecodeError, KeyError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Fetch pending PDFs for CRCI system")
    parser.add_argument("--email", default="crci-system@example.com",
                        help="Email for Unpaywall API (required by their TOS)")
    args = parser.parse_args()

    meta_files = sorted(PDF_DIR.glob("*.meta.json"))
    pending = []

    for mf in meta_files:
        with open(mf) as f:
            meta = json.load(f)
        if meta.get("pdf_status") == "PENDING_DOWNLOAD":
            pending.append((mf, meta))

    if not pending:
        print("No pending PDF downloads found.")
        return

    print(f"Found {len(pending)} papers with PENDING_DOWNLOAD status:\n")

    results = {"downloaded": [], "failed": []}

    for mf, meta in pending:
        doi = meta["doi"]
        pmid = meta.get("pmid")
        slug = doi_to_slug(doi)
        pdf_path = PDF_DIR / f"{slug}.pdf"
        title = meta.get("title", "Unknown")

        print(f"--- {doi} ---")
        print(f"  Title: {title}")
        print(f"  PMID: {pmid or 'N/A'}")

        if pdf_path.exists():
            print(f"  PDF already exists: {pdf_path}")
            results["downloaded"].append(doi)
            continue

        # Try sources in priority order
        pdf_data = None
        pdf_data = try_europe_pmc(pmid)
        if not pdf_data:
            pdf_data = try_unpaywall(doi, args.email)
        if not pdf_data:
            pdf_data = try_pmc_direct(pmid)

        if pdf_data and len(pdf_data) > 1000:  # Sanity check: real PDFs > 1KB
            with open(pdf_path, "wb") as f:
                f.write(pdf_data)
            print(f"  SUCCESS: Saved {len(pdf_data)} bytes -> {pdf_path}")

            # Update meta.json status
            meta["pdf_status"] = "DOWNLOADED"
            with open(mf, "w") as f:
                json.dump(meta, f, indent=2)
            results["downloaded"].append(doi)
        else:
            print(f"  FAILED: Could not retrieve PDF (may be paywalled)")
            print(f"  Manual download links:")
            print(f"    PubMed: https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            print(f"    DOI:    https://doi.org/{doi}")
            if pmid:
                print(f"    Sci-Hub: https://sci-hub.se/{doi}")
            results["failed"].append(doi)

        print()
        time.sleep(1)  # Rate limiting between papers

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print(f"  Downloaded: {len(results['downloaded'])}")
    print(f"  Failed:     {len(results['failed'])}")
    if results["failed"]:
        print("\nFailed DOIs (require manual download):")
        for doi in results["failed"]:
            print(f"  - {doi}")
        print(f"\nPlace PDFs in: {PDF_DIR}/")
        print("Naming: {doi_slug}.pdf (replace / with _)")


if __name__ == "__main__":
    main()
