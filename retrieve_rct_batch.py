#!/usr/bin/env python3
"""
Batch retrieve the 9 RCT papers from the user's list.
Converts PMIDs to DOIs via NCBI, then retrieves PDFs.
"""
import subprocess
import sys
import time
import requests

# Paper metadata from user's request
PAPERS = [
    {"key": "anderson2017_crc_exercise", "pmid": "28943165", "doi": None},
    {"key": "courneya2013_breast_exercise", "pmid": "23129742", "doi": "10.1200/JCO.2012.46.8318"},
    {"key": "jeong2020_breast_cbt_i", "pmid": "33152965", "doi": None},
    {"key": "lee2019_hnc_exercise", "pmid": "30770949", "doi": None},
    {"key": "smith2019_allogeneic_exercise", "pmid": "31267890", "doi": None},
    {"key": "garcia2021_breast_yoga", "pmid": "33712345", "doi": None},
    {"key": "kim2016_crc_cbt_i", "pmid": "27278061", "doi": None},
    {"key": "chiu2018_crc_bright_light", "pmid": "30260894", "doi": None},
    {"key": "adams2019_crc_exercise_rct", "pmid": "30260895", "doi": None},
]


def resolve_pmid_to_doi(pmid: str) -> str | None:
    """Use NCBI ID Converter to resolve PMID to DOI."""
    try:
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={
                "ids": pmid,
                "format": "json",
                "tool": "crci-system",
                "email": "crci@research.example.com",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        if records and "doi" in records[0]:
            return records[0]["doi"]
    except Exception as e:
        print(f"  ⚠️  Failed to resolve PMID {pmid}: {e}")
    return None


def retrieve_paper(doi: str, paper_key: str) -> bool:
    """Call retrieve_papers.py script with DOI."""
    print(f"\n{'='*60}")
    print(f"Retrieving: {paper_key}")
    print(f"DOI: {doi}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            ["python3", "scripts/retrieve_papers.py", "--doi", doi, "--verbose"],
            capture_output=False,
            text=True,
            timeout=120,  # 2 minute timeout per paper
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  ❌ Timeout retrieving {paper_key}")
        return False
    except Exception as e:
        print(f"  ❌ Error retrieving {paper_key}: {e}")
        return False


def main():
    """Main batch retrieval loop."""
    print("="*70)
    print("CRCI RCT BATCH RETRIEVAL")
    print("="*70)
    print(f"Total papers: {len(PAPERS)}")
    print()
    
    # Step 1: Resolve all PMIDs to DOIs
    print("STEP 1: Resolving PMIDs to DOIs...")
    print("-"*70)
    
    for paper in PAPERS:
        if paper["doi"]:
            print(f"✓ {paper['key']}: DOI already known ({paper['doi']})")
        else:
            print(f"→ Resolving PMID {paper['pmid']} ({paper['key']})...")
            doi = resolve_pmid_to_doi(paper["pmid"])
            if doi:
                paper["doi"] = doi
                print(f"  ✓ Found DOI: {doi}")
            else:
                print(f"  ✗ Could not resolve PMID {paper['pmid']}")
            time.sleep(0.5)  # Be polite to NCBI
    
    # Step 2: Retrieve papers with DOIs
    print("\n" + "="*70)
    print("STEP 2: Retrieving PDFs...")
    print("="*70)
    
    success_count = 0
    failed = []
    
    for paper in PAPERS:
        if not paper["doi"]:
            print(f"\n⏭️  Skipping {paper['key']}: No DOI available")
            failed.append((paper["key"], "No DOI"))
            continue
        
        success = retrieve_paper(paper["doi"], paper["key"])
        if success:
            success_count += 1
            print(f"✅ Successfully retrieved {paper['key']}")
        else:
            failed.append((paper["key"], "Retrieval failed"))
            print(f"❌ Failed to retrieve {paper['key']}")
        
        time.sleep(2)  # Be polite, rate limiting
    
    # Final report
    print("\n" + "="*70)
    print("BATCH RETRIEVAL SUMMARY")
    print("="*70)
    print(f"  ✅ Successfully retrieved: {success_count}/{len(PAPERS)}")
    
    if failed:
        print(f"\n  ❌ Failed ({len(failed)}):")
        for key, reason in failed:
            print(f"     - {key}: {reason}")
    
    print("="*70)
    
    return 0 if success_count == len(PAPERS) else 1


if __name__ == "__main__":
    sys.exit(main())
