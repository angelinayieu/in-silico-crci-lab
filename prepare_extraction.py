#!/usr/bin/env python3
"""
Batch extraction coordinator for CRCI papers.

Reads XML/PDF files, extracts basic metadata, and prepares
extraction-ready summaries for manual data entry into CSV templates.
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, List
import xml.etree.ElementTree as ET

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

def parse_xml_abstract(xml_path: Path) -> dict:
    """Extract title, authors, abstract from XML."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Find title
        title = ""
        for elem in root.iter():
            if elem.tag.endswith("title"):
                title = elem.text or ""
                if title:
                    break
        
        # Find abstract
        abstract = ""
        for elem in root.iter():
            if elem.tag.endswith("abstract"):
                abstract = "".join(elem.itertext())
                break
        
        # Find authors
        authors = []
        for elem in root.iter():
            if elem.tag.endswith("contrib"):
                name_elem = elem.find(".//name")
                if name_elem is not None:
                    surname = name_elem.find(".//surname")
                    given_name = name_elem.find(".//given-names")
                    if surname is not None:
                        author_name = surname.text or ""
                        if given_name is not None and given_name.text:
                            author_name += ", " + given_name.text
                        if author_name:
                            authors.append(author_name)
        
        return {
            "title": title,
            "abstract": abstract,
            "authors": authors[:5]  # First 5 authors
        }
    except Exception as e:
        return {"error": str(e)}

def extract_key_from_meta(meta_path: Path) -> dict:
    """Load metadata from JSON file."""
    try:
        with open(meta_path) as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

def prepare_extraction_summary(pmid: str, doi: str, file_path: Path, file_type: str):
    """Create extraction summary for a paper."""
    
    # Load metadata
    meta_path = file_path.parent / f"{file_path.stem}.meta.json"
    meta_data = extract_key_from_meta(meta_path) if meta_path.exists() else {}
    
    # Extract from XML
    summary_data = {"pmid": pmid, "doi": doi, "file_type": file_type}
    
    if file_type == "xml":
        xml_data = parse_xml_abstract(file_path)
        summary_data.update(xml_data)
    
    summary_data.update(meta_data)
    
    return summary_data

def main():
    """Generate extraction summaries for all available papers."""
    
    papers = [
        ("29759139", "10.1016/j.jneuroim.2018.04.012", "10.1016_j.jneuroim.2018.04.012", "xml"),
        ("29187817", "10.3389/fnhum.2017.00555", "10.3389_fnhum.2017.00555", "pdf"),
        ("22698992", "10.1016/j.bbi.2012.05.017", "10.1016_j.bbi.2012.05.017", "xml"),
        ("32482100", "10.1177/0844562120927535", "10.1177_0844562120927535", "xml"),
        ("30328048", "10.1007/s10549-018-4990-9", "10.1007_s10549-018-4990-9", "xml"),
        ("25922060", "10.1093/annonc/mdv206", "10.1093_annonc_mdv206", "xml"),
        ("23616206", "10.1136/amiajnl-2012-001332", "10.1136_amiajnl-2012-001332", "xml"),
    ]
    
    pdfs_dir = Path("/workspaces/in-silico-crci-lab/data/manual_uploads/pdfs")
    
    print("\n" + "=" * 75)
    print("EXTRACTION SUMMARY PREPARATION")
    print("=" * 75 + "\n")
    
    all_summaries = []
    
    for pmid, doi, filename_prefix, file_type in papers:
        print(f"Processing PMID {pmid}...")
        
        file_path = pdfs_dir / f"{filename_prefix}.{file_type}"
        
        if not file_path.exists():
            print(f"  ✗ File not found: {file_path}")
            continue
        
        summary = prepare_extraction_summary(pmid, doi, file_path, file_type)
        all_summaries.append(summary)
        
        if "title" in summary:
            print(f"  ✓ Title: {summary['title'][:70]}...")
        if "authors" in summary and summary["authors"]:
            print(f"  ✓ Authors: {', '.join(summary['authors'][:3])}")
        
        print()
    
    # Save summaries to JSON
    output_file = Path("/tmp/extraction_summaries.json")
    with open(output_file, "w") as f:
        json.dump(all_summaries, f, indent=2, default=str)
    
    print("=" * 75)
    print(f"✓ Extraction summaries saved to: {output_file}")
    print(f"✓ Ready to extract {len(all_summaries)} papers")
    print("\nNext steps:")
    print("1. Review extraction_summaries.json for paper metadata")
    print("2. For each paper, identify:")
    print("   - Study design (RCT, cohort, cross-sectional, etc.)")
    print("   - Cancer type")
    print("   - Cognitive outcomes measured")
    print("   - Effect sizes and standard errors")
    print("3. Fill CSV templates in data/manual_uploads/structured/<doi-slug>/")
    print("4. Run: python scripts/load_evidence_into_db.py")

if __name__ == "__main__":
    main()
