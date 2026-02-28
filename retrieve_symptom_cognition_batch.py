#!/usr/bin/env python3
"""
Retrieve symptom-cognition papers from user's curated list.
Handles PMC articles, PubMed, Frontiers, BMC, Nature, and other OA sources.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

# Parse PMC IDs from URLs
PMC_PAPERS = [
    ("PMC6640530", "Liou 2019 insomnia→perceived CI breast"),
    ("PMC6122719", "Giffard PROSOM-K 2018 sleep→memory BCA"),
    ("PMC6792503", "Vardy 2022 inflammation→attention BCA"),
    ("PMC12665909", "Onyedibe 2025 depression/fatigue→FACT-Cog"),
    ("PMC12119337", "CRCI search result"),
    ("PMC11642909", "CRCI search result"),
    ("PMC10900040", "CRCI search result"),
    ("PMC4165557", "CRCI search result"),
    ("PMC4455839", "CRCI search result"),
    ("PMC2861143", "CRCI search result"),
    ("PMC7602817", "CRCI search result"),
    ("PMC8170590", "CRCI search result"),
    ("PMC8713760", "Ehrstedt 2021 fatigue→processing speed pediatric"),
    ("PMC9073450", "CRCI search result"),
    # Session 2 - Lung
    ("PMC10914843", "Lung cancer CRCI prevalence meta-analysis"),
    ("PMC12077423", "Lung cancer neuropsych protocol"),
    ("PMC5657249", "Simó lung cancer cognitive + brain"),
    # Session 2 - Hematological
    ("PMC7384931", "CLL cognition disease risk→memory/EF"),
    ("PMC10305842", "CML/TKI cognition symptoms→subjective CI"),
    ("PMC9046282", "Hodgkin lymphoma long-term cognition Hungary"),
    ("PMC8755481", "Lymphoma CRCI longitudinal commentary"),
    ("PMC9385796", "Aggressive lymphoma CRCI feasibility"),
    # Session 2 - Colorectal
    ("PMC4239806", "Vardy 2014 CRC cognition+fatigue baseline"),
    ("PMC5683012", "Vardy 2015 CRC cognition longitudinal 24mo"),
    # Session 2 - Cross-lagged symptoms
    ("PMC4380836", "Ho 2015 fatigue→depression cross-lagged BCA"),
    ("PMC4058321", "Brown 2013 cross-lagged fatigue↔depression NULL"),
    ("PMC3250363", "Liu fatigue↔sleep longitudinal BCA actigraphy"),
    ("PMC12211318", "Hendy 2025 sleep/fatigue/depression→QoL BCA"),
    # Session 2 - Pain mediation
    ("PMC9368026", "Total pain→illness acceptance pelvic SEM"),
    ("PMC12211190", "Cancer pain→QoL SEM biopsychosocial"),
    # Session 2 - Depression/EF
    ("PMC8691137", "EF→depressive symptoms via coping BCA mediation"),
    ("PMC4995149", "Noll 2017 NCF/mood/QoL temporal lobe glioma"),
    ("PMC5980921", "Symptoms/anxiety/depression→QoL path analysis"),
    # Session 2 - Network analyses
    ("PMC12287671", "JMIR 2025 systematic review network analysis"),
    ("PMC9529994", "Xiao 2022 HNC network 4 timepoints"),
    # Session 2 - Gynecological
    ("PMC6377208", "GYN cancer CRCI review"),
    ("PMC5425316", "Ovarian cancer brain structure+cognition"),
    ("PMC9883396", "Mental health disorders ovarian cancer survivors"),
]

# DOI/URL papers (non-PMC sources)
DOI_PAPERS = [
    ("10.1101/2025.01.10.25322159", "Cognitive function LPA chemo 2025 preprint"),  # ResearchSquare → bioRxiv
    ("10.1007/s00520-026-10317-6", "Aggressive lymphoma cognition 2026 Springer"),
    ("10.3389/fonc.2025.1509424", "Hodgkin lymphoma cognition Frontiers"),
    ("10.1186/s12885-025-14732-6", "CRC neuropsych 2025 BMC"),
    ("10.3389/fonc.2024.1380916", "GYN cancer distress trajectory Frontiers"),
    ("10.3389/fmolb.2021.770413", "Long-term CRCI review Frontiers"),
    ("10.3389/fpubh.2023.1079873", "Somatic symptom network Frontiers"),
    ("10.2196/66087", "JMIR network analysis direct link"),
    ("10.1007/s11764-024-01543-0", "Doppenberg-Smit 2024 symptom networks Springer"),
    ("10.1007/s11764-022-01246-4", "EMA temporal network Springer"),
    ("10.1038/s41598-025-09550-6", "Network QoL/mindfulness Nature Sci Rep"),
]

# PMID-only papers (need DOI resolution)
PMID_PAPERS = [
    ("36890861", "Luo 2023 lung cancer symptom cluster→CI"),
    ("29080061", "Dhillon 2018 CRC perceived CI longitudinal"),
    ("15897927", "Beck 2005 pain→sleep→fatigue mediation"),
    ("30679301", "Charalambous 2019 pain→anxiety/fatigue mediation"),
    ("39387227", "CRF network analysis BCA 2024"),
    ("31435892", "Schellekens 2020 fatigue/depression network"),
    ("33404703", "Corallo 2021 GYN cancer CRCI+depression"),
]


def retrieve_pmc_xml(pmcid: str, description: str) -> bool:
    """Retrieve PMC article via direct XML download."""
    print(f"\n{'='*70}")
    print(f"Retrieving: {pmcid}")
    print(f"Description: {description}")
    print(f"{'='*70}")
    
    # Convert PMCID to DOI first via NCBI ID Converter
    import requests
    try:
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": pmcid, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        
        if not records or "doi" not in records[0]:
            print(f"  ⚠️  No DOI found for {pmcid}, trying direct PMC retrieval")
            return False
        
        doi = records[0]["doi"]
        pmid = records[0].get("pmid", "")
        
        print(f"  ✓ Resolved: DOI={doi}, PMID={pmid}")
        
        # Use the main retrieval script
        result = subprocess.run(
            ["python3", "scripts/retrieve_papers.py", "--doi", doi],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0:
            print(f"  ✅ Successfully retrieved via DOI")
            return True
        else:
            print(f"  ❌ Failed to retrieve")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def retrieve_doi(doi: str, description: str) -> bool:
    """Retrieve paper by DOI."""
    print(f"\n{'='*70}")
    print(f"Retrieving: {doi}")
    print(f"Description: {description}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            ["python3", "scripts/retrieve_papers.py", "--doi", doi],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def retrieve_pmid(pmid: str, description: str) -> bool:
    """Resolve PMID to DOI and retrieve."""
    print(f"\n{'='*70}")
    print(f"Retrieving: PMID {pmid}")
    print(f"Description: {description}")
    print(f"{'='*70}")
    
    import requests
    try:
        # Resolve PMID to DOI
        resp = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": pmid, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        
        if not records or "doi" not in records[0]:
            print(f"  ⚠️  No DOI found for PMID {pmid}")
            return False
        
        doi = records[0]["doi"]
        print(f"  ✓ Resolved to DOI: {doi}")
        
        result = subprocess.run(
            ["python3", "scripts/retrieve_papers.py", "--doi", doi],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main batch retrieval."""
    print("="*70)
    print("SYMPTOM-COGNITION PAPER BATCH RETRIEVAL")
    print("="*70)
    
    total_papers = len(PMC_PAPERS) + len(DOI_PAPERS) + len(PMID_PAPERS)
    print(f"Total papers to retrieve: {total_papers}")
    print(f"  - PMC articles: {len(PMC_PAPERS)}")
    print(f"  - DOI papers: {len(DOI_PAPERS)}")
    print(f"  - PMID papers: {len(PMID_PAPERS)}")
    print()
    
    success_count = 0
    failed = []
    
    # Retrieve PMC articles
    print("\n" + "="*70)
    print("SESSION 1: PMC ARTICLES")
    print("="*70)
    for pmcid, desc in PMC_PAPERS:
        if retrieve_pmc_xml(pmcid, desc):
            success_count += 1
        else:
            failed.append((pmcid, desc, "PMC retrieval failed"))
        time.sleep(2)  # Rate limiting
    
    # Retrieve DOI papers
    print("\n" + "="*70)
    print("SESSION 2: DOI-BASED PAPERS")
    print("="*70)
    for doi, desc in DOI_PAPERS:
        if retrieve_doi(doi, desc):
            success_count += 1
        else:
            failed.append((doi, desc, "DOI retrieval failed"))
        time.sleep(2)
    
    # Retrieve PMID papers
    print("\n" + "="*70)
    print("SESSION 3: PMID-BASED PAPERS")
    print("="*70)
    for pmid, desc in PMID_PAPERS:
        if retrieve_pmid(pmid, desc):
            success_count += 1
        else:
            failed.append((pmid, desc, "PMID resolution/retrieval failed"))
        time.sleep(2)
    
    # Final report
    print("\n" + "="*70)
    print("BATCH RETRIEVAL SUMMARY")
    print("="*70)
    print(f"  ✅ Successfully retrieved: {success_count}/{total_papers}")
    print(f"  ❌ Failed: {len(failed)}/{total_papers}")
    
    if failed:
        print(f"\n  Failed papers:")
        for identifier, desc, reason in failed:
            print(f"    - {identifier}: {desc[:50]}...")
            print(f"      Reason: {reason}")
    
    print("="*70)
    
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
