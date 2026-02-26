#!/usr/bin/env python3
"""
Full Extraction Pipeline Test — Uses Actual System Components

Tests the complete extraction pipeline on a paper URL:
1. Fetch page HTML + download PDF (using curl-cffi for TLS fingerprinting)
2. Run P0 Triage: pdf_ingestion → relevance_screening → paper_type_classifier
3. Run P1 Extraction: canonical_reader → multi-agent extraction
4. Match against registries (EDGE, INSTRUMENT, NODE)
5. Output structured holding data for LLM decision-making
6. Generate next steps per EXTRACTION_PLAYBOOK.md protocols

Usage:
    ANTHROPIC_API_KEY=... python scripts/test_full_extraction.py URL
    
    # Without API key (dry-run mode):
    python scripts/test_full_extraction.py URL --dry-run
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Auto-load .env file so ANTHROPIC_API_KEY is available
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extraction_test")

# ═══════════════════════════════════════════════════════════════
#  WEB FETCHING — Uses curl-cffi for TLS fingerprinting
# ═══════════════════════════════════════════════════════════════

try:
    from curl_cffi import requests as cffi_requests
    USING_CURL_CFFI = True
except ImportError:
    import requests as cffi_requests  # type: ignore
    USING_CURL_CFFI = False
    logger.warning("curl-cffi not installed — may get 403 on some sites. pip install curl-cffi")

from bs4 import BeautifulSoup

TIMEOUT = 60


def fetch_html(url: str) -> tuple[BeautifulSoup | None, str | None, str]:
    """Fetch HTML page, returning soup, error, and final URL after redirects."""
    try:
        if USING_CURL_CFFI:
            response = cffi_requests.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
        else:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
            response = cffi_requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}", url
        
        final_url = str(response.url) if hasattr(response, 'url') else url
        return BeautifulSoup(response.text, "html.parser"), None, final_url
    except Exception as e:
        return None, str(e), url


def download_pdf(url: str, save_path: Path, max_retries: int = 3) -> bool:
    """Download PDF to disk. Returns True on success."""
    
    # Generate alternate URLs to try
    urls_to_try = [url]
    
    # For PMC URLs, try the direct PDF path variants
    if "pmc.ncbi.nlm.nih.gov" in url or "ncbi.nlm.nih.gov/pmc" in url:
        # Extract PMC ID
        pmc_match = re.search(r'PMC(\d+)', url)
        if pmc_match:
            pmc_id = pmc_match.group(0)  # e.g., PMC5568897
            # Add alternate PDF URL patterns
            urls_to_try.extend([
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/",
                f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf",
            ])
    
    for attempt_url in urls_to_try:
        for retry in range(max_retries):
            try:
                logger.info("Downloading PDF (attempt %d): %s", retry + 1, attempt_url[:80])
                
                if USING_CURL_CFFI:
                    response = cffi_requests.get(
                        attempt_url, 
                        impersonate="chrome", 
                        timeout=TIMEOUT,
                        allow_redirects=True,
                    )
                else:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
                        "Accept": "application/pdf,*/*",
                        "Referer": "https://pmc.ncbi.nlm.nih.gov/",
                    }
                    response = cffi_requests.get(attempt_url, headers=headers, timeout=TIMEOUT)
                
                if response.status_code != 200:
                    logger.warning("HTTP %d for %s", response.status_code, attempt_url[:50])
                    continue
                
                content = response.content
                
                # Verify it's actually a PDF (starts with %PDF)
                if content[:5].startswith(b"%PDF"):
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(content)
                    logger.info("PDF saved: %s (%d bytes)", save_path.name, len(content))
                    return True
                else:
                    logger.warning("Response is not PDF (got: %s...)", content[:30])
                    
            except Exception as e:
                logger.warning("Download attempt failed: %s", e)
                continue
    
    logger.error("PDF download failed after all attempts")
    return False


def extract_metadata_from_html(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    """Extract paper metadata from HTML meta tags."""
    meta = {}
    
    # DOI
    for attr in ["citation_doi", "DC.identifier"]:
        elem = soup.find("meta", attrs={"name": attr})
        if elem and elem.get("content"):
            doi = elem["content"]
            if doi.startswith("doi:"):
                doi = doi[4:]
            if doi.startswith("10."):
                meta["doi"] = doi
                break
    
    if "doi" not in meta:
        match = re.search(r'10\.\d{4,}/[^\s"<>]+', url)
        if match:
            meta["doi"] = match.group(0).rstrip(".,;")
    
    # Title
    for attr in ["citation_title", "DC.title", "og:title"]:
        elem = soup.find("meta", attrs={"name": attr}) or soup.find("meta", attrs={"property": attr})
        if elem and elem.get("content"):
            meta["title"] = elem["content"].strip()
            break
    
    # Authors
    authors = []
    for elem in soup.find_all("meta", attrs={"name": "citation_author"}):
        if elem.get("content"):
            authors.append(elem["content"].strip())
    meta["authors"] = authors
    
    # Journal
    elem = soup.find("meta", attrs={"name": "citation_journal_title"})
    if elem and elem.get("content"):
        meta["journal"] = elem["content"].strip()
    
    # Year
    for attr in ["citation_publication_date", "citation_date"]:
        elem = soup.find("meta", attrs={"name": attr})
        if elem and elem.get("content"):
            match = re.search(r"(19|20)\d{2}", elem["content"])
            if match:
                meta["year"] = int(match.group(0))
                break
    
    # PDF URL
    elem = soup.find("meta", attrs={"name": "citation_pdf_url"})
    if elem and elem.get("content"):
        meta["pdf_url"] = elem["content"]
    else:
        # Search for PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                if href.startswith("/"):
                    parsed = urlparse(url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                meta["pdf_url"] = href
                break
    
    # Abstract
    for attr in ["citation_abstract", "DC.description", "description"]:
        elem = soup.find("meta", attrs={"name": attr})
        if elem and elem.get("content") and len(elem["content"]) > 100:
            meta["abstract"] = elem["content"].strip()[:5000]
            break
    
    if "abstract" not in meta:
        for elem in soup.find_all(attrs={"class": re.compile(r"abstract", re.I)}):
            text = elem.get_text(strip=True)
            if len(text) > 100:
                meta["abstract"] = text[:5000]
                break
    
    return meta


# ═══════════════════════════════════════════════════════════════
#  P0 TRIAGE — Uses actual system components
# ═══════════════════════════════════════════════════════════════

def run_p0_ingestion(pdf_path: Path) -> dict[str, Any]:
    """Run P0-S1: PDF Ingestion using actual system component."""
    from crci.extraction.p0_triage.pdf_ingestion import ingest_pdf
    return ingest_pdf(pdf_path)


def run_p0_relevance_screening(ingested: dict[str, Any]) -> dict[str, Any]:
    """Run P0-S2: Relevance Screening using actual system component."""
    from crci.extraction.p0_triage.relevance_screening import screen_relevance
    return screen_relevance(ingested)


def run_p0_paper_type_classification(ingested: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Run P0-PTC: Paper Type Classification using actual system component."""
    if dry_run:
        # Use heuristic classification in dry-run mode
        text = ingested.get("canonical_text", "").lower()
        
        # Heuristic paper type detection
        if "meta-analysis" in text or "meta analysis" in text:
            return {"paper_subtype": "meta_analysis", "confidence": 0.8}
        elif "systematic review" in text:
            return {"paper_subtype": "systematic_review", "confidence": 0.8}
        elif "randomized" in text and "controlled" in text:
            return {"paper_subtype": "randomized_controlled_trial", "confidence": 0.7}
        elif "cohort" in text and "prospective" in text:
            return {"paper_subtype": "prospective_cohort", "confidence": 0.6}
        elif "cross-sectional" in text or "cross sectional" in text:
            return {"paper_subtype": "cross_sectional", "confidence": 0.6}
        elif "case report" in text or "case series" in text:
            return {"paper_subtype": "case_report", "confidence": 0.6}
        elif "review" in text:
            return {"paper_subtype": "narrative_review", "confidence": 0.5}
        else:
            return {"paper_subtype": "observational", "confidence": 0.4}
    
    from crci.extraction.p0_triage.paper_type_classifier import classify_paper_type
    return classify_paper_type(ingested)


def run_p0_mode_selection(paper_id: str, classified: dict[str, Any], screened: dict[str, Any], dry_run: bool = False) -> str:
    """Run P0-S3: Mode Selection using actual system component."""
    if dry_run:
        # Heuristic mode selection in dry-run
        subtype = classified.get("paper_subtype", "").lower()
        if subtype in ["meta_analysis", "systematic_review", "randomized_controlled_trial"]:
            return "DEEP"
        elif subtype in ["case_report", "case_series", "animal", "review"]:
            return "SHALLOW"
        else:
            return "STANDARD"
    
    from crci.extraction.p0_triage.mode_selection import select_extraction_mode
    from crci.shared.models.enums import PaperSubtype
    
    # Convert string subtype to enum
    subtype_str = classified.get("paper_subtype", "observational")
    try:
        paper_subtype = PaperSubtype(subtype_str)
    except ValueError:
        paper_subtype = PaperSubtype.OBSERVATIONAL
    
    result = select_extraction_mode(paper_id, paper_subtype, screened)
    return result.extraction_mode.value if hasattr(result.extraction_mode, 'value') else str(result.extraction_mode)


# ═══════════════════════════════════════════════════════════════
#  P1 EXTRACTION — Uses actual system components
# ═══════════════════════════════════════════════════════════════

def run_p1_canonical_read(
    paper_id: str, 
    canonical_text: str,
    dry_run: bool = False,
) -> Any:
    """Run P1-CR: Canonical Reader using actual system component."""
    from crci.extraction.p1_extraction.canonical_reader import CanonicalReader
    
    if dry_run:
        # Return a mock PaperMap for dry-run mode
        from crci.shared.models.intermediate_states import PaperMap
        return PaperMap(
            paper_id=paper_id,
            full_text=canonical_text,
            sections=(),
            tables=(),
            figures=(),
            candidate_spans=(),
            study_design=None,
            n_total=None,
            arms=(),
        )
    
    from crci.llm.client import LLMClient
    llm_client = LLMClient()
    reader = CanonicalReader(llm_client)
    return reader.read(paper_id=paper_id, canonical_text=canonical_text)


def run_p1_agents(
    paper_id: str,
    paper_map: Any,
    extraction_mode: str,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Run P1-AG: Multi-Agent Extraction using ALL system agents."""
    if dry_run:
        return [
            {"agent_id": f"AG{i:02d}", "status": "skipped", "reason": "dry-run mode"}
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 10, 11]
        ]

    from crci.llm.client import LLMClient
    from crci.extraction.p1_extraction.agents.ag01_metadata import MetadataAgent
    from crci.extraction.p1_extraction.agents.ag02_design import DesignAgent
    from crci.extraction.p1_extraction.agents.ag03_cohort import CohortAgent
    from crci.extraction.p1_extraction.agents.ag04_outcome import OutcomeAgent
    from crci.extraction.p1_extraction.agents.ag05_stats_label import StatsLabelAgent
    from crci.extraction.p1_extraction.agents.ag06_exposure import ExposureAgent
    from crci.extraction.p1_extraction.agents.ag07_mediator import MediatorAgent
    from crci.extraction.p1_extraction.agents.ag08_temporal import TemporalAgent
    from crci.extraction.p1_extraction.agents.ag10_strategic_intel import StrategicIntelAgent
    from crci.extraction.p1_extraction.agents.ag11_instrument_validation import InstrumentValidationAgent

    llm_client = LLMClient(max_tokens=8192)  # 8192 to avoid AG05 truncation on large papers

    # Run ALL 10 extraction agents — same set as runner.py
    agents = [
        MetadataAgent(llm_client),
        DesignAgent(llm_client),
        CohortAgent(llm_client),
        OutcomeAgent(llm_client),
        StatsLabelAgent(llm_client),       # *** CRITICAL — 40 SpanLabel types ***
        ExposureAgent(llm_client),
        MediatorAgent(llm_client),
        TemporalAgent(llm_client),
        StrategicIntelAgent(llm_client),
        InstrumentValidationAgent(llm_client),
    ]

    results = []
    all_span_labels = []
    all_annotations = []
    for agent in agents:
        try:
            logger.info("Running agent: %s", agent.agent_id)
            # Correct method: .extract() not .run()
            output = agent.extract(paper_map)
            span_labels_detail = []
            for sl in output.span_labels:
                sl_dict = {"label_type": sl.label_type, "value": sl.value}
                if hasattr(sl, "unit") and sl.unit:
                    sl_dict["unit"] = sl.unit
                if hasattr(sl, "context") and sl.context:
                    sl_dict["context"] = sl.context[:80]
                span_labels_detail.append(sl_dict)
            all_span_labels.extend(output.span_labels)
            all_annotations.extend(output.annotations)
            results.append({
                "agent_id": agent.agent_id,
                "status": "success",
                "span_labels_count": len(output.span_labels),
                "annotations_count": len(output.annotations),
                "span_labels_detail": span_labels_detail[:20],  # first 20
                "metadata": output.metadata,
                "elapsed_ms": output.elapsed_ms,
            })
        except Exception as e:
            logger.error("Agent %s failed: %s", agent.agent_id, e, exc_info=True)
            results.append({
                "agent_id": agent.agent_id,
                "status": "error",
                "error": str(e),
            })

    # Summary of all extractions
    results.append({
        "agent_id": "TOTAL",
        "status": "summary",
        "total_span_labels": len(all_span_labels),
        "total_annotations": len(all_annotations),
        "label_type_counts": _count_label_types(all_span_labels),
    })
    return results


def _count_label_types(span_labels: list) -> dict[str, int]:
    """Count occurrences of each SpanLabel type."""
    counts: dict[str, int] = {}
    for sl in span_labels:
        lt = sl.label_type if hasattr(sl, "label_type") else str(sl)
        counts[lt] = counts.get(lt, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ═══════════════════════════════════════════════════════════════
#  REGISTRY MATCHING
# ═══════════════════════════════════════════════════════════════

def load_registry(name: str) -> list[dict[str, str]]:
    """Load a registry CSV."""
    path = PROJECT_ROOT / "registries" / f"{name}_REGISTRY.csv"
    if not path.exists():
        logger.warning("Registry not found: %s", path)
        return []
    
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def find_instrument_matches(text: str, instruments: list[dict]) -> list[dict]:
    """Find instruments mentioned in text."""
    matches = []
    text_lower = text.lower()
    
    for inst in instruments:
        inst_id = inst.get("instrument_id", "")
        full_name = inst.get("instrument_name", "")
        short_name = inst.get("instrument_short", "")
        
        # Require minimum length to avoid false positives
        matched_on = None
        if full_name and len(full_name) >= 8 and full_name.lower() in text_lower:
            matched_on = full_name
        elif short_name and len(short_name) >= 4 and short_name.lower() in text_lower:
            # For short names, require word boundary
            pattern = r'\b' + re.escape(short_name) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                matched_on = short_name
        
        if matched_on:
            matches.append({
                "instrument_id": inst_id,
                "instrument_name": full_name,
                "matched_text": matched_on,
                "maps_to_node": inst.get("maps_to_node_id", ""),
            })
    
    return matches


def find_edge_candidates(
    text: str, 
    design_info: dict,
    instrument_ids: list[str],
    edges: list[dict],
) -> list[dict]:
    """Identify candidate edges based on content analysis."""
    candidates = []
    text_lower = text.lower()
    
    # Keyword detection
    keywords = {
        "exercise": ["exercise", "physical activity", "aerobic", "resistance training", "walking"],
        "sleep": ["sleep", "insomnia", "circadian", "psqi", "actigraphy"],
        "stress": ["stress", "mindfulness", "mbsr", "meditation", "cortisol"],
        "cognitive": ["cognitive", "memory", "attention", "executive function", "processing speed", "chemo brain"],
        "cancer": ["cancer", "oncology", "chemotherapy", "tumor", "breast cancer", "survivor"],
        "inflammation": ["il-6", "interleukin", "crp", "c-reactive", "tnf", "cytokine", "inflammation"],
        "fatigue": ["fatigue", "tiredness", "energy"],
        "depression": ["depression", "depressive", "mood", "phq"],
        "anxiety": ["anxiety", "anxious", "gad", "worry"],
        "bdnf": ["bdnf", "brain-derived", "neurotrophic factor"],
    }
    
    detected = {}
    for category, terms in keywords.items():
        detected[category] = any(term in text_lower for term in terms)
    
    # Match edges based on detected content
    for edge in edges:
        edge_id = edge.get("edge_relation_id", "")
        source = edge.get("source_node_id", "").upper()
        target = edge.get("target_node_id", "").upper()
        mechanism = edge.get("mechanism_description", "").lower()
        
        reasons = []
        
        # Exercise interventions
        if detected["exercise"] and "ACTIVITY" in source:
            if detected["inflammation"] and any(x in target for x in ["IL6", "CRP", "TNF"]):
                reasons.append("Exercise intervention + inflammation outcome")
            if detected["bdnf"] and "BDNF" in target:
                reasons.append("Exercise intervention + BDNF outcome")
            if detected["cognitive"] and "COG" in target:
                reasons.append("Exercise intervention + cognitive outcome")
            if detected["fatigue"] and "FATIGUE" in target:
                reasons.append("Exercise intervention + fatigue outcome")
        
        # Sleep interventions
        if detected["sleep"] and "SLEEP" in source:
            if detected["cognitive"] and "COG" in target:
                reasons.append("Sleep intervention + cognitive outcome")
            if "CORTISOL" in target:
                reasons.append("Sleep + HPA axis")
        
        # Stress/mindfulness interventions
        if detected["stress"] and "STRESS" in source:
            if "CORTISOL" in target:
                reasons.append("Stress management + cortisol")
            if detected["inflammation"] and any(x in target for x in ["IL6", "CRP"]):
                reasons.append("Stress management + inflammation")
        
        # Chemotherapy exposure
        if detected["cancer"] and "CHEMO" in source:
            if detected["cognitive"] and "COG" in target:
                reasons.append("Chemotherapy -> cognitive impairment")
            if detected["inflammation"] and any(x in target for x in ["IL6", "CRP", "TNF"]):
                reasons.append("Chemotherapy -> inflammation")
            if detected["fatigue"] and "FATIGUE" in target:
                reasons.append("Chemotherapy -> fatigue")
        
        if reasons:
            candidates.append({
                "edge_id": edge_id,
                "source_node": source,
                "target_node": target,
                "reasons": reasons,
            })
    
    # Deduplicate by edge_id
    seen = set()
    unique = []
    for c in candidates:
        if c["edge_id"] not in seen:
            seen.add(c["edge_id"])
            unique.append(c)
    
    return unique[:15]


# ═══════════════════════════════════════════════════════════════
#  HOLDING DATA STRUCTURE — For LLM Decision Making
# ═══════════════════════════════════════════════════════════════

@dataclass
class HoldingData:
    """Structured holding data for LLM to make extraction decisions.
    
    This is the intermediate state between web fetch and full extraction.
    The LLM uses this to decide next steps per EXTRACTION_PLAYBOOK.md.
    """
    # Source info
    url: str
    doi: str | None = None
    pdf_path: str | None = None
    
    # Paper metadata (from HTML + P0)
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    abstract: str | None = None
    
    # P0 Triage results
    pdf_quality: str | None = None
    page_count: int = 0
    relevance_score: float = 0.0
    relevance_decision: str | None = None
    paper_subtype: str | None = None
    paper_subtype_confidence: float = 0.0
    extraction_mode: str = "STANDARD"
    
    # P1 Canonical Read results
    sections_found: list[str] = field(default_factory=list)
    tables_found: int = 0
    figures_found: int = 0
    candidate_spans_found: int = 0
    
    # Full text (for LLM processing)
    canonical_text: str = ""
    canonical_text_length: int = 0
    
    # Registry matches
    instruments_matched: list[dict] = field(default_factory=list)
    edges_candidate: list[dict] = field(default_factory=list)
    
    # Agent outputs (if LLM was called)
    agent_outputs: list[dict] = field(default_factory=list)
    
    # Status
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "url": self.url,
            "doi": self.doi,
            "pdf_path": self.pdf_path,
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "abstract": self.abstract[:500] + "..." if self.abstract and len(self.abstract) > 500 else self.abstract,
            "pdf_quality": self.pdf_quality,
            "page_count": self.page_count,
            "relevance_score": self.relevance_score,
            "relevance_decision": self.relevance_decision,
            "paper_subtype": self.paper_subtype,
            "paper_subtype_confidence": self.paper_subtype_confidence,
            "extraction_mode": self.extraction_mode,
            "sections_found": self.sections_found,
            "tables_found": self.tables_found,
            "figures_found": self.figures_found,
            "candidate_spans_found": self.candidate_spans_found,
            "canonical_text_length": self.canonical_text_length,
            "instruments_matched": self.instruments_matched,
            "edges_candidate": self.edges_candidate,
            "agent_outputs": self.agent_outputs,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ═══════════════════════════════════════════════════════════════
#  NEXT STEPS GENERATOR — Per EXTRACTION_PLAYBOOK.md protocols
# ═══════════════════════════════════════════════════════════════

def generate_next_steps(holding: HoldingData) -> list[str]:
    """Generate next steps per EXTRACTION_PLAYBOOK.md protocols."""
    steps = []
    doi_slug = (holding.doi or "unknown_doi").replace("/", "_")
    
    # -----------------------------------------------------------
    # Step 0: Mode is already determined by P0
    # -----------------------------------------------------------
    steps.append(f"## Step 0 — Mode: {holding.extraction_mode}")
    steps.append(f"   Paper subtype: {holding.paper_subtype} (confidence: {holding.paper_subtype_confidence:.2f})")
    steps.append(f"   Relevance: {holding.relevance_decision} (score: {holding.relevance_score:.2f})")
    steps.append("")
    
    # -----------------------------------------------------------
    # Step 1: Check/Add to EDGE_REGISTRY
    # -----------------------------------------------------------
    steps.append("## Step 1 — Check/Add to EDGE_REGISTRY")
    if holding.edges_candidate:
        steps.append(f"   {len(holding.edges_candidate)} candidate edges detected:")
        for ec in holding.edges_candidate[:5]:
            steps.append(f"   - {ec['edge_id']}: {', '.join(ec.get('reasons', []))[:60]}")
        steps.append("   ACTION: Verify these edges exist in registries/EDGE_REGISTRY.csv")
        steps.append("   ACTION: Add new rows if paper tests edges NOT already in registry")
    else:
        steps.append("   No candidate edges detected from keyword analysis")
        steps.append("   ACTION: Manual review of paper to identify edges tested")
    steps.append("")
    
    # -----------------------------------------------------------
    # Step 2: Create Paper Subfolder
    # -----------------------------------------------------------
    steps.append("## Step 2 — Create Paper Subfolder")
    steps.append(f"   mkdir -p data/manual_uploads/structured/{doi_slug}")
    steps.append(f"   Copy templates from data/templates/ to this folder")
    steps.append("")
    
    # -----------------------------------------------------------
    # Step 3: Fill edge_evidence_template.csv (REQUIRED)
    # -----------------------------------------------------------
    steps.append("## Step 3 — Fill edge_evidence_template.csv (REQUIRED)")
    steps.append(f"   Location: data/manual_uploads/structured/{doi_slug}/edge_evidence_template.csv")
    steps.append("   Required fields:")
    steps.append(f"   - doi: {holding.doi}")
    steps.append("   - edge_id: [from Step 1]")
    steps.append("   - beta_raw: [Cohen's d, OR, or reported effect size]")
    steps.append("   - se_raw: [Standard error of effect size]")
    steps.append("   - effect_type_original: [cohen_d, mean_diff, odds_ratio, etc.]")
    steps.append("   - effect_size_type: [BETWEEN_GROUP, WITHIN_GROUP, PRE_POST_CHANGE]")
    steps.append("   - sample_size: [Total N in analysis]")
    steps.append(f"   - study_design: {holding.paper_subtype or '[from paper]'}")
    steps.append("   - cancer_type: [breast, colorectal, lung, etc.]")
    steps.append("   - treatment_phase: [active_treatment, early_recovery, etc.]")
    if holding.instruments_matched:
        inst_ids = [m["instrument_id"] for m in holding.instruments_matched[:3]]
        steps.append(f"   - instrument_id: {', '.join(inst_ids)}")
    else:
        steps.append("   - instrument_id: [from INSTRUMENT_REGISTRY.csv]")
    steps.append("")
    
    # -----------------------------------------------------------
    # Step 4+: Mode-dependent templates
    # -----------------------------------------------------------
    if holding.extraction_mode == "DEEP":
        steps.append("## Step 4 — Fill population_norms_template.csv (REQUIRED for DEEP)")
        steps.append(f"   Location: data/manual_uploads/structured/{doi_slug}/population_norms_template.csv")
        steps.append("   Required: node_id, instrument_id, mean, sd, sample_size, cancer_type")
        steps.append("")
        
        steps.append("## Step 5 — Fill context_priors_template.csv")
        steps.append("   Convert raw scores to z-scores: z = (observed - population_mean) / population_SD")
        steps.append("")
        
        steps.append("## Step 6 — Optional Templates (if data available)")
        steps.append("   - temporal_evidence_template.csv: if ≥2 longitudinal timepoints")
        steps.append("   - instrument_evidence_template.csv: if Cronbach's α, test-retest ICC reported")
        steps.append("   - correlation_template.csv: if inter-domain correlations reported")
        steps.append("")
        
        steps.append("## Step 7 — Create meta.json")
        
    elif holding.extraction_mode == "STANDARD":
        steps.append("## Step 4 — Fill population_norms_template.csv (RECOMMENDED)")
        steps.append(f"   Location: data/manual_uploads/structured/{doi_slug}/population_norms_template.csv")
        steps.append("")
        
        steps.append("## Step 5 — Create meta.json")
        
    else:  # SHALLOW
        steps.append("## Step 4 — Create meta.json (minimal extraction)")
    
    # Meta.json template
    steps.append(f"   Location: data/manual_uploads/pdfs/{doi_slug}.meta.json")
    steps.append("   Content:")
    steps.append("   {")
    steps.append(f'     "doi": "{holding.doi}",')
    steps.append(f'     "title": "{holding.title or ""}",')
    steps.append(f'     "authors": {json.dumps(holding.authors[:5])},')
    steps.append(f'     "year": {holding.year or "null"},')
    steps.append(f'     "journal": "{holding.journal or ""}",')
    steps.append(f'     "extraction_mode": "{holding.extraction_mode}"')
    steps.append("   }")
    
    return steps


# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATION
# ═══════════════════════════════════════════════════════════════

def run_full_extraction_test(
    url: str, 
    dry_run: bool = False,
    keep_pdf: bool = False,
) -> HoldingData:
    """Run full extraction test on a URL.
    
    Args:
        url: Paper URL (PubMed, PMC, journal site, etc.)
        dry_run: If True, skip LLM calls
        keep_pdf: If True, keep downloaded PDF in data/retrieval_cache/
        
    Returns:
        HoldingData with all extracted information
    """
    holding = HoldingData(url=url)
    
    print(f"\n{'='*70}")
    print(f"FULL EXTRACTION TEST")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'FULL (with LLM calls)'}")
    print(f"{'='*70}\n")
    
    # ───────────────────────────────────────────────────────────
    # Phase 1: Fetch HTML and extract metadata
    # ───────────────────────────────────────────────────────────
    print("=" * 50)
    print("PHASE 1: WEB FETCH")
    print("=" * 50)
    
    soup, error, final_url = fetch_html(url)
    if error:
        print(f"✗ Failed to fetch HTML: {error}")
        holding.errors.append(f"HTML fetch failed: {error}")
        return holding
    
    print(f"✓ HTML fetched ({final_url})")
    
    # Extract metadata from HTML
    meta = extract_metadata_from_html(soup, final_url)
    holding.doi = meta.get("doi")
    holding.title = meta.get("title")
    holding.authors = meta.get("authors", [])
    holding.journal = meta.get("journal")
    holding.year = meta.get("year")
    holding.abstract = meta.get("abstract")
    
    print(f"  DOI: {holding.doi}")
    print(f"  Title: {holding.title[:60]}..." if holding.title and len(holding.title) > 60 else f"  Title: {holding.title}")
    print(f"  Authors: {len(holding.authors)} found")
    print(f"  Journal: {holding.journal}")
    print(f"  Year: {holding.year}")
    
    # ───────────────────────────────────────────────────────────
    # Phase 2: Download PDF
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 2: PDF DOWNLOAD")
    print("=" * 50)
    
    pdf_url = meta.get("pdf_url")
    if not pdf_url:
        print("✗ No PDF URL found in HTML")
        holding.warnings.append("No PDF URL found — extraction will be limited")
    else:
        # Create temp directory or use cache
        if keep_pdf:
            cache_dir = PROJECT_ROOT / "data" / "retrieval_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            doi_slug = (holding.doi or str(uuid.uuid4())[:8]).replace("/", "_")
            pdf_path = cache_dir / f"{doi_slug}.pdf"
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix="crci_extraction_"))
            pdf_path = temp_dir / "paper.pdf"
        
        # Use cached PDF if available
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            holding.pdf_path = str(pdf_path)
            print(f"✓ PDF cached: {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)")
        elif download_pdf(pdf_url, pdf_path):
            holding.pdf_path = str(pdf_path)
            print(f"✓ PDF downloaded: {pdf_path.name}")
        else:
            holding.warnings.append("PDF download failed")
    
    # ───────────────────────────────────────────────────────────
    # Phase 3: P0 Triage (using actual system components)
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 3: P0 TRIAGE")
    print("=" * 50)
    
    if holding.pdf_path:
        try:
            # P0-S1: PDF Ingestion
            print("\nP0-S1: PDF Ingestion...")
            ingested = run_p0_ingestion(Path(holding.pdf_path))
            
            holding.pdf_quality = ingested.get("pdf_quality", "UNKNOWN")
            holding.page_count = ingested.get("page_count", 0)
            holding.canonical_text = ingested.get("canonical_text", "")
            holding.canonical_text_length = len(holding.canonical_text)
            
            # Store sections found
            sections = ingested.get("sections", [])
            holding.sections_found = [s.get("section_type", "unknown") for s in sections]
            
            print(f"  ✓ Quality: {holding.pdf_quality}")
            print(f"  ✓ Pages: {holding.page_count}")
            print(f"  ✓ Text: {holding.canonical_text_length:,} chars")
            print(f"  ✓ Sections: {holding.sections_found}")
            
            # P0-S2: Relevance Screening
            print("\nP0-S2: Relevance Screening...")
            screened = run_p0_relevance_screening(ingested)
            
            holding.relevance_score = screened.get("relevance_score", 0.0)
            holding.relevance_decision = screened.get("decision", "REVIEW")
            
            print(f"  ✓ Score: {holding.relevance_score:.2f}")
            print(f"  ✓ Decision: {holding.relevance_decision}")
            
            # P0-PTC: Paper Type Classification
            print("\nP0-PTC: Paper Type Classification...")
            classified = run_p0_paper_type_classification(ingested, dry_run=dry_run)
            
            holding.paper_subtype = str(classified.get("paper_subtype", "unknown"))
            holding.paper_subtype_confidence = classified.get("confidence", 0.0)
            
            print(f"  ✓ Subtype: {holding.paper_subtype}")
            print(f"  ✓ Confidence: {holding.paper_subtype_confidence:.2f}")
            
            # P0-S3: Mode Selection
            print("\nP0-S3: Mode Selection...")
            paper_id = holding.doi or str(uuid.uuid4())[:8]
            holding.extraction_mode = run_p0_mode_selection(paper_id, classified, screened, dry_run=dry_run)
            print(f"  ✓ Mode: {holding.extraction_mode}")
            
        except Exception as e:
            logger.error("P0 Triage failed: %s", e)
            holding.errors.append(f"P0 Triage failed: {e}")
            # Fall back to heuristic mode
            holding.extraction_mode = "STANDARD"
    else:
        print("⚠ No PDF available — skipping P0 triage")
        holding.warnings.append("P0 triage skipped (no PDF)")
        holding.extraction_mode = "STANDARD"
        # Use abstract as canonical text
        holding.canonical_text = holding.abstract or ""
        holding.canonical_text_length = len(holding.canonical_text)
    
    # ───────────────────────────────────────────────────────────
    # Phase 4: P1 Canonical Read (using actual system components)
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 4: P1 CANONICAL READ")
    print("=" * 50)
    
    if holding.canonical_text:
        try:
            paper_id = holding.doi or str(uuid.uuid4())[:8]
            print(f"\nBuilding PaperMap for {paper_id}...")
            
            paper_map = run_p1_canonical_read(
                paper_id=paper_id,
                canonical_text=holding.canonical_text,
                dry_run=dry_run,
            )
            
            holding.sections_found = [s.section_type for s in paper_map.sections]
            holding.tables_found = len(paper_map.tables)
            holding.figures_found = len(paper_map.figures)
            holding.candidate_spans_found = len(paper_map.candidate_spans)
            
            print(f"  ✓ Sections: {len(holding.sections_found)}")
            print(f"  ✓ Tables: {holding.tables_found}")
            print(f"  ✓ Figures: {holding.figures_found}")
            print(f"  ✓ Candidate spans: {holding.candidate_spans_found}")
            
        except Exception as e:
            logger.error("P1 Canonical Read failed: %s", e)
            holding.warnings.append(f"P1 Canonical Read failed: {e}")
    
    # ───────────────────────────────────────────────────────────
    # Phase 5: Registry Matching
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 5: REGISTRY MATCHING")
    print("=" * 50)
    
    # Load registries
    instruments = load_registry("INSTRUMENT")
    edges = load_registry("EDGE")
    nodes = load_registry("NODE")
    
    print(f"Loaded: {len(instruments)} instruments, {len(edges)} edges, {len(nodes)} nodes")
    
    # Search text: combine abstract + canonical text
    search_text = (holding.abstract or "") + "\n\n" + holding.canonical_text
    
    # Find instrument matches
    holding.instruments_matched = find_instrument_matches(search_text, instruments)
    print(f"\nInstruments matched: {len(holding.instruments_matched)}")
    for m in holding.instruments_matched[:5]:
        print(f"  - {m['instrument_id']}: {m['instrument_name'][:40]}")
    
    # Find edge candidates
    design_info = {"study_design": holding.paper_subtype}
    inst_ids = [m["instrument_id"] for m in holding.instruments_matched]
    holding.edges_candidate = find_edge_candidates(search_text, design_info, inst_ids, edges)
    print(f"\nEdge candidates: {len(holding.edges_candidate)}")
    for ec in holding.edges_candidate[:5]:
        print(f"  - {ec['edge_id']}: {ec['reasons'][0][:50]}")
    
    # ───────────────────────────────────────────────────────────
    # Phase 6: Multi-Agent Extraction (ALL 10 agents)
    # ───────────────────────────────────────────────────────────
    if not dry_run and holding.canonical_text:
        print("\n" + "=" * 50)
        print("PHASE 6: MULTI-AGENT EXTRACTION (ALL 10 AGENTS)")
        print("=" * 50)

        try:
            paper_map = run_p1_canonical_read(
                paper_id=holding.doi or "unknown",
                canonical_text=holding.canonical_text,
                dry_run=False,
            )

            print(f"\nPaperMap built: {len(paper_map.sections)} sections, "
                  f"{len(paper_map.tables)} tables, "
                  f"{len(paper_map.candidate_spans)} candidate spans")
            if paper_map.study_design:
                print(f"  Study design: {paper_map.study_design}")
            if paper_map.n_total:
                print(f"  N total: {paper_map.n_total}")

            print("\nRunning all 10 extraction agents...")
            holding.agent_outputs = run_p1_agents(
                paper_id=holding.doi or "unknown",
                paper_map=paper_map,
                extraction_mode=holding.extraction_mode,
                dry_run=False,
            )

            for output in holding.agent_outputs:
                agent_id = output.get("agent_id", "?")
                status_icon = "✓" if output.get("status") == "success" else ("Σ" if output.get("status") == "summary" else "✗")
                if output.get("status") == "success":
                    sl_count = output.get("span_labels_count", 0)
                    an_count = output.get("annotations_count", 0)
                    elapsed = output.get("elapsed_ms", 0)
                    print(f"  {status_icon} {agent_id}: {sl_count} span_labels, "
                          f"{an_count} annotations ({elapsed:.0f}ms)")
                    # Show first few span labels for detail
                    for sl in output.get("span_labels_detail", [])[:5]:
                        print(f"      → {sl.get('label_type')}: {sl.get('value')} "
                              f"{sl.get('context', '')[:50]}")
                elif output.get("status") == "summary":
                    print(f"\n  TOTAL: {output.get('total_span_labels', 0)} span_labels, "
                          f"{output.get('total_annotations', 0)} annotations")
                    label_counts = output.get("label_type_counts", {})
                    if label_counts:
                        print("  Label type distribution:")
                        for lt, cnt in list(label_counts.items())[:15]:
                            print(f"      {lt}: {cnt}")
                else:
                    print(f"  {status_icon} {agent_id}: {output.get('status')} - {output.get('error', '')}")

        except Exception as e:
            logger.error("Multi-agent extraction failed: %s", e, exc_info=True)
            holding.errors.append(f"Multi-agent extraction failed: {e}")
    else:
        print("\n⚠ Skipping multi-agent extraction (dry-run mode)")
    
    # ───────────────────────────────────────────────────────────
    # Generate Next Steps
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("NEXT STEPS (per EXTRACTION_PLAYBOOK.md)")
    print("=" * 70 + "\n")
    
    next_steps = generate_next_steps(holding)
    for step in next_steps:
        print(step)
    
    # ───────────────────────────────────────────────────────────
    # Summary
    # ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("HOLDING DATA SUMMARY")
    print("=" * 70)
    
    if holding.errors:
        print("\n⚠ ERRORS:")
        for e in holding.errors:
            print(f"   - {e}")
    
    if holding.warnings:
        print("\n⚠ WARNINGS:")
        for w in holding.warnings:
            print(f"   - {w}")
    
    print(f"\nExtraction Mode: {holding.extraction_mode}")
    print(f"PDF Quality: {holding.pdf_quality}")
    print(f"Canonical Text: {holding.canonical_text_length:,} chars")
    print(f"Instruments Matched: {len(holding.instruments_matched)}")
    print(f"Edge Candidates: {len(holding.edges_candidate)}")
    
    # Cleanup temp PDF if not keeping
    if holding.pdf_path and not keep_pdf:
        temp_dir = Path(holding.pdf_path).parent
        if temp_dir.name.startswith("crci_extraction_"):
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    return holding


def main():
    parser = argparse.ArgumentParser(
        description="Full extraction pipeline test using actual system components"
    )
    parser.add_argument("url", help="Paper URL to test")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Skip LLM calls (faster, no API key needed)"
    )
    parser.add_argument(
        "--keep-pdf",
        action="store_true",
        help="Keep downloaded PDF in data/retrieval_cache/"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output holding data as JSON"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check for API key unless dry-run
    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ ANTHROPIC_API_KEY not set. Running in dry-run mode.")
        print("  Set the key or use --dry-run explicitly.\n")
        args.dry_run = True
    
    holding = run_full_extraction_test(
        url=args.url,
        dry_run=args.dry_run,
        keep_pdf=args.keep_pdf,
    )
    
    if args.json:
        print("\n" + "=" * 70)
        print("HOLDING DATA (JSON)")
        print("=" * 70)
        print(json.dumps(holding.to_dict(), indent=2))


if __name__ == "__main__":
    main()
