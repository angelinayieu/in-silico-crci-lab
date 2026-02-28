# VERIFIED: no formulas (pure parsing module)
# VERIFIED: imports — xml.etree + stdlib
# VERIFIED: backward wiring — reads JATS/NLM XML file from disk
# VERIFIED: forward wiring — writes IngestedPaper dict same as pdf_ingestion.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates P0-G1 raise on failure
"""
Component: SYS_EXTRACTION.EX-P0.P0-S1-XML
Spec: SYS_EXTRACTION_COMPLETE.md lines 169-232 (adapted for XML)
Formulas: None (pure parsing)
Reads: JATS/NLM XML file on disk (from PMC efetch or Europe PMC)
Writes: IngestedPaper dict (consumed by relevance_screening.py, paper_type_classifier.py)
Gates: P0-G1 (XML parsed successfully)

Purpose: Convert JATS/NLM XML to the same IngestedPaper dict format
         as pdf_ingestion.py. JATS XML has proper section markup so
         extraction is more reliable than PDF. No pdfplumber needed.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


def ingest_xml(xml_path: str | Path) -> dict[str, Any]:
    """Convert JATS/NLM XML to canonical text with quality assessment.

    P0-S1 (XML variant): XML Ingestion & Text Extraction.
    Parses JATS XML structure for front-matter, body, and back-matter.
    Produces the same dict structure as ingest_pdf() so downstream
    modules (relevance_screening, paper_type_classifier) work unchanged.

    Args:
        xml_path: Path to the JATS/NLM XML file on disk.

    Returns:
        IngestedPaper-like dict with keys:
            canonical_text: str - Full extracted text
            pdf_quality: str - Always "GOOD" for XML (structured)
            page_count: int - Estimated from text length
            has_tables: bool - Whether <table-wrap> elements exist
            has_figures: bool - Whether <fig> elements exist
            sections: list[dict] - Detected sections with offsets
            metadata: dict - Extracted from JATS front-matter

    Raises:
        GateViolation: P0-G1 if XML cannot be parsed.
    """
    xml_path = Path(xml_path)

    if not xml_path.exists():
        raise GateViolation(
            "P0-G1",
            f"XML file does not exist: {xml_path}",
            {"xml_path": str(xml_path)},
        )

    if xml_path.suffix.lower() not in (".xml", ".nxml"):
        raise GateViolation(
            "P0-G1",
            f"File is not XML: {xml_path.suffix}",
            {"xml_path": str(xml_path), "suffix": xml_path.suffix},
        )

    # Read raw XML
    try:
        raw = xml_path.read_bytes()
    except OSError as exc:
        raise GateViolation(
            "P0-G1",
            f"Cannot read XML file: {exc}",
            {"xml_path": str(xml_path)},
        ) from exc

    if not raw.strip():
        raise GateViolation(
            "P0-G1",
            "XML file is empty",
            {"xml_path": str(xml_path)},
        )

    # Parse XML
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GateViolation(
            "P0-G1",
            f"XML parse error: {exc}",
            {"xml_path": str(xml_path), "error": str(exc)},
        ) from exc

    # ── Extract front-matter (metadata) ──
    metadata = _extract_front_matter(root)

    # ── Extract body text with sections ──
    body_text, sections = _extract_body(root)

    # ── Extract abstract (may be in front or body) ──
    abstract_text = _extract_abstract(root)

    # ── Extract back-matter (references, acknowledgments) ──
    back_text = _extract_back_matter(root)

    # Build canonical text: abstract + body + back
    parts: list[str] = []
    if abstract_text:
        parts.append(f"ABSTRACT\n{abstract_text}")
    if body_text:
        parts.append(body_text)
    if back_text:
        parts.append(back_text)

    canonical_text = "\n\n".join(parts)

    if not canonical_text.strip():
        raise GateViolation(
            "P0-G1",
            "XML contains no extractable text",
            {"xml_path": str(xml_path)},
        )

    # ── Detect tables and figures ──
    has_tables = len(root.findall(".//table-wrap")) > 0 or len(root.findall(".//table")) > 0
    has_figures = len(root.findall(".//fig")) > 0

    # Estimate page count (~3000 chars per page for academic papers)
    page_count = max(1, len(canonical_text) // 3000)

    # Update sections with abstract if present
    if abstract_text:
        sections.insert(0, {
            "name": "abstract",
            "offset": 0,
            "length": len(abstract_text),
        })

    logger.info(
        "XML ingested: path=%s quality=GOOD est_pages=%d has_tables=%s "
        "has_figures=%s sections=%d chars=%d",
        xml_path,
        page_count,
        has_tables,
        has_figures,
        len(sections),
        len(canonical_text),
    )

    return {
        "canonical_text": canonical_text,
        "pdf_quality": "GOOD",  # XML is always well-structured
        "page_count": page_count,
        "has_tables": has_tables,
        "has_figures": has_figures,
        "sections": sections,
        "metadata": metadata,
        "source_format": "jats_xml",
    }


# ═══════════════════════════════════════════════════════════════
#  JATS FRONT-MATTER PARSING
# ═══════════════════════════════════════════════════════════════


def _extract_front_matter(root: ET.Element) -> dict[str, Any]:
    """Extract metadata from JATS <front> element."""
    metadata: dict[str, Any] = {}
    front = root.find(".//front")
    if front is None:
        return metadata

    # Title
    title_elem = front.find(".//article-title")
    if title_elem is not None:
        metadata["title"] = _element_text(title_elem)

    # Authors
    authors: list[str] = []
    for contrib in front.findall(".//contrib[@contrib-type='author']"):
        surname = contrib.findtext("name/surname", "")
        given = contrib.findtext("name/given-names", "")
        if surname:
            authors.append(f"{surname}, {given}".strip().rstrip(","))
    if authors:
        metadata["author"] = "; ".join(authors)
        metadata["authors"] = authors

    # Journal
    journal_elem = front.find(".//journal-title")
    if journal_elem is not None:
        metadata["journal"] = _element_text(journal_elem)

    # Year
    for pub_date in front.findall(".//pub-date"):
        year_elem = pub_date.find("year")
        if year_elem is not None and year_elem.text:
            try:
                metadata["year"] = int(year_elem.text.strip())
                break
            except ValueError:
                pass

    # DOI
    for article_id in front.findall(".//article-id"):
        if article_id.get("pub-id-type") == "doi" and article_id.text:
            metadata["doi"] = article_id.text.strip()
        elif article_id.get("pub-id-type") == "pmid" and article_id.text:
            metadata["pmid"] = article_id.text.strip()
        elif article_id.get("pub-id-type") == "pmc" and article_id.text:
            pmc_id = article_id.text.strip()
            if not pmc_id.startswith("PMC"):
                pmc_id = f"PMC{pmc_id}"
            metadata["pmcid"] = pmc_id

    # Volume, issue, pages
    volume = front.findtext(".//volume")
    if volume:
        metadata["volume"] = volume.strip()
    issue = front.findtext(".//issue")
    if issue:
        metadata["issue"] = issue.strip()
    fpage = front.findtext(".//fpage")
    lpage = front.findtext(".//lpage")
    if fpage:
        metadata["pages"] = f"{fpage.strip()}-{lpage.strip()}" if lpage else fpage.strip()

    return metadata


# ═══════════════════════════════════════════════════════════════
#  JATS ABSTRACT PARSING
# ═══════════════════════════════════════════════════════════════


def _extract_abstract(root: ET.Element) -> str:
    """Extract abstract text from JATS <abstract> element(s)."""
    abstracts = root.findall(".//abstract")
    if not abstracts:
        return ""

    parts: list[str] = []
    for abstract in abstracts:
        # Skip graphical abstracts
        abstract_type = abstract.get("abstract-type", "")
        if "graphical" in abstract_type.lower():
            continue

        # Structured abstracts have <sec> children
        sec_children = abstract.findall("sec")
        if sec_children:
            for sec in sec_children:
                sec_title = sec.findtext("title", "")
                sec_text = _element_text_recursive(sec, skip_tags={"title"})
                if sec_title:
                    parts.append(f"{sec_title}: {sec_text}")
                elif sec_text:
                    parts.append(sec_text)
        else:
            parts.append(_element_text(abstract))

    return "\n".join(p for p in parts if p.strip())


# ═══════════════════════════════════════════════════════════════
#  JATS BODY PARSING
# ═══════════════════════════════════════════════════════════════


def _extract_body(root: ET.Element) -> tuple[str, list[dict[str, Any]]]:
    """Extract body text and section structure from JATS <body>."""
    body = root.find(".//body")
    if body is None:
        return "", []

    text_parts: list[str] = []
    sections: list[dict[str, Any]] = []
    current_offset = 0

    # JATS body uses <sec> elements with <title> children
    sec_elements = body.findall("sec")
    if sec_elements:
        for sec in sec_elements:
            section_text, sub_sections = _extract_section(sec, current_offset)
            if section_text:
                text_parts.append(section_text)
                sections.extend(sub_sections)
                current_offset += len(section_text) + 2  # +2 for \n\n
    else:
        # Flat body text (no sections)
        body_text = _element_text_recursive(body)
        if body_text:
            text_parts.append(body_text)

    return "\n\n".join(text_parts), sections


def _extract_section(
    sec: ET.Element,
    offset: int,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract text and title from a <sec> element."""
    title: str = ""
    title_elem = sec.find("title")
    if title_elem is not None:
        title = _element_text(title_elem)

    # Get direct text (excluding nested <sec>)
    paragraphs: list[str] = []
    for child in sec:
        if child.tag == "title":
            continue
        if child.tag == "sec":
            continue  # Handle recursively below
        if child.tag == "p":
            p_text = _element_text(child)
            if p_text:
                paragraphs.append(p_text)
        elif child.tag in ("list", "def-list"):
            list_text = _element_text_recursive(child)
            if list_text:
                paragraphs.append(list_text)

    section_text = ""
    sections: list[dict[str, Any]] = []

    if title:
        section_text = f"{title.upper()}\n" + "\n".join(paragraphs)
        # Normalize section name
        sec_name = _normalize_section_name(title)
        sections.append({
            "name": sec_name,
            "offset": offset,
            "length": len(section_text),
        })
    else:
        section_text = "\n".join(paragraphs)

    # Recurse into nested <sec> elements
    nested_offset = offset + len(section_text) + 2
    for child_sec in sec.findall("sec"):
        child_text, child_sections = _extract_section(child_sec, nested_offset)
        if child_text:
            section_text += "\n\n" + child_text
            sections.extend(child_sections)
            nested_offset += len(child_text) + 2

    return section_text, sections


# ═══════════════════════════════════════════════════════════════
#  JATS BACK-MATTER PARSING
# ═══════════════════════════════════════════════════════════════


def _extract_back_matter(root: ET.Element) -> str:
    """Extract back-matter text (references, acknowledgments)."""
    back = root.find(".//back")
    if back is None:
        return ""

    parts: list[str] = []

    # Acknowledgments
    ack = back.find("ack")
    if ack is not None:
        ack_text = _element_text_recursive(ack)
        if ack_text:
            parts.append(f"ACKNOWLEDGMENTS\n{ack_text}")

    # References
    ref_list = back.find("ref-list")
    if ref_list is not None:
        ref_parts: list[str] = []
        for ref in ref_list.findall("ref"):
            ref_text = _element_text_recursive(ref)
            if ref_text:
                ref_parts.append(ref_text)
        if ref_parts:
            parts.append("REFERENCES\n" + "\n".join(ref_parts))

    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
#  TEXT EXTRACTION UTILITIES
# ═══════════════════════════════════════════════════════════════


def _element_text(elem: ET.Element) -> str:
    """Extract all text from an element, including children inline."""
    parts: list[str] = []
    for text in elem.itertext():
        stripped = text.strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


def _element_text_recursive(
    elem: ET.Element,
    skip_tags: set[str] | None = None,
) -> str:
    """Extract text recursively, optionally skipping certain tag children."""
    skip_tags = skip_tags or set()
    parts: list[str] = []

    if elem.text:
        parts.append(elem.text.strip())

    for child in elem:
        if child.tag in skip_tags:
            if child.tail:
                parts.append(child.tail.strip())
            continue
        child_text = _element_text(child)
        if child_text:
            parts.append(child_text)
        if child.tail:
            parts.append(child.tail.strip())

    return " ".join(p for p in parts if p)


_SECTION_NAME_MAP: dict[str, str] = {
    "introduction": "introduction",
    "background": "introduction",
    "methods": "methods",
    "materials and methods": "methods",
    "study design": "methods",
    "participants": "methods",
    "procedure": "methods",
    "results": "results",
    "findings": "results",
    "discussion": "discussion",
    "conclusion": "discussion",
    "conclusions": "discussion",
    "limitations": "discussion",
    "references": "references",
    "bibliography": "references",
    "acknowledgments": "acknowledgments",
    "acknowledgements": "acknowledgments",
    "funding": "acknowledgments",
    "supplementary": "supplementary",
    "supplementary materials": "supplementary",
    "appendix": "supplementary",
}


def _normalize_section_name(title: str) -> str:
    """Normalize a section title to canonical name."""
    lower = title.strip().lower()
    # Try exact match first
    if lower in _SECTION_NAME_MAP:
        return _SECTION_NAME_MAP[lower]
    # Try prefix match
    for key, canonical in _SECTION_NAME_MAP.items():
        if lower.startswith(key):
            return canonical
    return lower
