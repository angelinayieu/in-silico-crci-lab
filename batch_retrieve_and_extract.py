#!/usr/bin/env python3
"""
Batch retrieve papers by PMID and prepare for extraction.

PMIDs are provided via command line or directly in the script.
Fetches metadata from PubMed, retrieves DOIs, and downloads PDFs.

Usage:
    python batch_retrieve_and_extract.py 29759139 34875674 29187817 22698992 ...
"""
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import requests
from urllib.parse import urljoin

def fetch_pubmed_metadata(pmid: str) -> Optional[dict]:
    """Fetch metadata for a PMID from PubMed."""
    try:
        # Use NCBI eutils to fetch metadata
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "rettype": "json",
            "retmode": "json",
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("result") and data["result"].get(pmid):
            return data["result"][pmid]
        return None
    except Exception as e:
        print(f"⚠️  Error fetching metadata for PMID {pmid}: {e}")
        return None


def extract_doi_from_metadata(metadata: dict) -> Optional[str]:
    """Extract DOI from PubMed metadata."""
    if not metadata:
        return None
    
    # Try various fields where DOI might be stored
    article = metadata.get("article", {})
    
    # Check ArticleIdList
    article_ids = article.get("articlepublicationdate", {}).get("articleids") or article.get("articleids", [])
    for aid in article_ids:
        if aid.get("idtype") == "doi":
            return aid.get("value")
    
    # Check journal_info or other fields
    for key in ["journal", "doi_id"]:
        if key in metadata and metadata[key]:
            return metadata[key]
    
    return None


def main():
    """Main batch retrieval function."""
    # PMIDs from user input or command line
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
    
    # Allow command line override
    if len(sys.argv) > 1:
        pmids = sys.argv[1:]
    
    print(f"📥 Retrieving {len(pmids)} papers...")
    print(f"PMIDs: {', '.join(pmids)}\n")
    
    retrieval_results = []
    
    for pmid in pmids:
        print(f"🔍 Processing PMID {pmid}...")
        
        # Fetch metadata
        metadata = fetch_pubmed_metadata(pmid)
        if not metadata:
            print(f"   ⚠️  Could not fetch metadata")
            continue
        
        # Try to extract DOI
        doi = extract_doi_from_metadata(metadata)
        if not doi:
            print(f"   ⚠️  No DOI found in metadata, will attempt retrieval by PMID")
        else:
            print(f"   ✓ Found DOI: {doi}")
        
        # Store for retrieval
        retrieval_results.append({
            "pmid": pmid,
            "doi": doi,
            "metadata_available": True
        })
    
    # Now use the retrieve_papers.py script for each DOI
    print("\n" + "="*60)
    print("Now retrieving papers...\n")
    
    for result in retrieval_results:
        pmid = result["pmid"]
        doi = result["doi"]
        
        if doi:
            print(f"Retrieving PMID {pmid} (DOI: {doi})...")
            try:
                # Call retrieve_papers.py with the DOI
                cmd = [
                    sys.executable,
                    "scripts/retrieve_papers.py",
                    "--doi", doi,
                    "--verbose"
                ]
                subprocess.run(cmd, check=True, timeout=60)
                print(f"✓ Retrieved PMID {pmid}\n")
            except subprocess.CalledProcessError:
                print(f"⚠️  Failed to retrieve PMID {pmid}\n")
            except Exception as e:
                print(f"⚠️  Error retrieving PMID {pmid}: {e}\n")
        else:
            print(f"⚠️  Skipping PMID {pmid} (no DOI available)\n")
    
    print("\n" + "="*60)
    print("Batch retrieval complete!")
    print("\nNext steps:")
    print("1. Check data/manual_uploads/pdfs/ for retrieved papers")
    print("2. Run extraction: python scripts/extract_papers.py")


if __name__ == "__main__":
    main()
