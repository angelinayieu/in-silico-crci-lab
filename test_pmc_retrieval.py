#!/usr/bin/env python3
"""
Test retrieval of just the first 5 PMC articles.
"""
import subprocess
import requests
import time

PMC_TEST = [
    ("PMC6640530", "Liou 2019 insomnia→perceived CI breast"),
    ("PMC6122719", "Giffard PROSOM-K 2018 sleep→memory BCA"),
    ("PMC6792503", "Vardy 2022 inflammation→attention BCA"),
    ("PMC12665909", "Onyedibe 2025 depression/fatigue→FACT-Cog"),
    ("PMC12119337", "CRCI search result"),
]

for pmcid, desc in PMC_TEST:
    print(f"\n{'='*70}")
    print(f"Resolving {pmcid}: {desc}")
    print(f"{'='*70}")
    
    try:
        # Resolve PMC to DOI
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": pmcid, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("records") or "doi" not in data["records"][0]:
            print(f"  ❌ No DOI found for {pmcid}")
            continue
        
        doi = data["records"][0]["doi"]
        pmid = data["records"][0].get("pmid", "")
        
        print(f"  ✓ Resolved: DOI={doi}, PMID={pmid}")
        
        # Retrieve via DOI
        result = subprocess.run(
            ["python3", "scripts/retrieve_papers.py", "--doi", doi],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0:
            print(f"  ✅ Successfully retrieved")
        else:
            print(f"  ❌ Failed to retrieve")
            if result.stdout:
                print(f"  Output: {result.stdout[-200:]}")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    time.sleep(2)

print("\n" + "="*70)
print("Test complete - check data/manual_uploads/pdfs/ for results")
print("="*70)
