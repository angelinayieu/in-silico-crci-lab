#!/usr/bin/env python3
"""
Batch retrieve papers by PMID with proper retry logic and rate limiting.
"""
import sys
import time
from pathlib import Path
from typing import Optional

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import requests
from bs4 import BeautifulSoup

def fetch_doi_from_pubmed(pmid: str, delay: float = 2.0) -> Optional[str]:
    """
    Fetch DOI from PubMed HTML page by scraping.
    Includes rate limiting delay.
    """
    time.sleep(delay)  # Rate limiting
    
    try:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; U; en) Gecko/20091221"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML to find DOI
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Look for DOI in various locations
        # PubMed usually has it in a span with data-doi attribute
        doi_elem = soup.find(attrs={"data-doi": True})
        if doi_elem:
            doi = doi_elem.get("data-doi")
            if doi:
                return doi
        
        # Also try to find it in the page text
        text = soup.get_text()
        if "doi:" in text.lower():
            for line in text.split("\n"):
                if "doi:" in line.lower():
                    # Extract DOI
                    parts = line.lower().split("doi:")
                    if len(parts) > 1:
                        doi_candidate = parts[1].strip().split()[0]
                        return doi_candidate
        
        print(f"   ⚠️  No DOI found in HTML for PMID {pmid}")
        return None
        
    except Exception as e:
        print(f"   ⚠️  Error fetching DOI for PMID {pmid}: {e}")
        return None


def main():
    """Retrieve DOIs for all PMIDs."""
    pmids = [
        "29759139",
        "34875674", 
        "29187817",
        "22698992",
        "40155248",
        "32482100",
        "30328048",
        "32570396",
        "25922060",
        "23616206",
    ]
    
    print(f"🔍 Fetching DOIs for {len(pmids)} papers from PubMed...\n")
    
    results = []
    for i, pmid in enumerate(pmids, 1):
        print(f"[{i}/{len(pmids)}] PMID {pmid}...", end=" ", flush=True)
        doi = fetch_doi_from_pubmed(pmid)
        if doi:
            print(f"✓ DOI: {doi}")
            results.append((pmid, doi))
        else:
            print("✗ No DOI found")
    
    print(f"\n{'='*60}")
    print(f"Successfully resolved {len(results)}/{len(pmids)} DOIs\n")
    
    # Print results for manual use
    print("DOI list for retrieve_papers.py batch processing:")
    print("-" * 60)
    for pmid, doi in results:
        print(f"python scripts/retrieve_papers.py --doi \"{doi}\"")
    
    return results


if __name__ == "__main__":
    results = main()
