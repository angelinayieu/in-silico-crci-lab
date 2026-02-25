# VERIFIED: no formulas (pure parsing module)
# VERIFIED: imports — pdfplumber + stdlib
# VERIFIED: backward wiring — reads PDF file from disk
# VERIFIED: forward wiring — writes IngestedPaper dict for relevance_screening.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates P0-G1 raise on failure
"""
Component: SYS_EXTRACTION.EX-P0.P0-S1
Spec: SYS_EXTRACTION_COMPLETE.md lines 169-232
Formulas: None (pure parsing)
Reads: PDF file on disk
Writes: IngestedPaper dict (consumed by relevance_screening.py, paper_type_classifier.py)
Gates: P0-G1 (PDF parsed successfully)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  PDF QUALITY ENUM (local to this module, not persisted)
# ═══════════════════════════════════════════════════════════════

PDF_QUALITY_GOOD = "GOOD"
PDF_QUALITY_DEGRADED = "DEGRADED"
PDF_QUALITY_SCAN = "SCAN"


# ═══════════════════════════════════════════════════════════════
#  SECTION HEADER PATTERNS
# ═══════════════════════════════════════════════════════════════

_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("abstract", re.compile(r"^\s*abstract\s*$", re.IGNORECASE)),
    ("introduction", re.compile(r"^\s*(introduction|background)\s*$", re.IGNORECASE)),
    ("methods", re.compile(r"^\s*(methods?|materials?\s+(and|&)\s+methods?|study\s+design)\s*$", re.IGNORECASE)),
    ("results", re.compile(r"^\s*results?\s*$", re.IGNORECASE)),
    ("discussion", re.compile(r"^\s*(discussion|conclusions?)\s*$", re.IGNORECASE)),
    ("references", re.compile(r"^\s*(references?|bibliography)\s*$", re.IGNORECASE)),
    ("acknowledgments", re.compile(r"^\s*(acknowledgm?ents?|funding)\s*$", re.IGNORECASE)),
    ("supplementary", re.compile(r"^\s*(supplementary|supporting|appendix)\s*", re.IGNORECASE)),
]

# Patterns for detecting table and figure captions
_TABLE_CAPTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(Table\s+\d+[.:]\s*.+?)(?:\n|$)", re.IGNORECASE
)
_FIGURE_CAPTION_PATTERN = re.compile(
    r"(?:^|\n)\s*((?:Figure|Fig\.?)\s+\d+[.:]\s*.+?)(?:\n|$)", re.IGNORECASE
)


def ingest_pdf(pdf_path: str | Path) -> dict[str, Any]:
    """Convert PDF to canonical text with quality assessment.

    P0-S1: PDF Ingestion & Text Extraction.
    Uses pdfplumber for text extraction, table detection, and
    structural analysis. No LLM calls -- pure parsing.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        IngestedPaper-like dict with keys:
            canonical_text: str - Full extracted text
            pdf_quality: str - One of GOOD, DEGRADED, SCAN
            page_count: int - Number of pages
            has_tables: bool - Whether statistical tables were detected
            has_figures: bool - Whether figures were detected
            sections: list[dict] - Detected section headers with offsets
            metadata: dict - Basic PDF metadata if available

    Raises:
        GateViolation: P0-G1 if PDF cannot be parsed.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise GateViolation(
            "P0-G1",
            f"PDF file does not exist: {pdf_path}",
            {"pdf_path": str(pdf_path)},
        )

    if not pdf_path.suffix.lower() == ".pdf":
        raise GateViolation(
            "P0-G1",
            f"File is not a PDF: {pdf_path.suffix}",
            {"pdf_path": str(pdf_path), "suffix": pdf_path.suffix},
        )

    try:
        import pdfplumber
    except ImportError as exc:
        raise GateViolation(
            "P0-G1",
            "pdfplumber package not installed. Install with: pip install pdfplumber",
            {"pdf_path": str(pdf_path)},
        ) from exc

    # Attempt to open and parse the PDF
    try:
        pdf = pdfplumber.open(str(pdf_path))
    except Exception as exc:
        raise GateViolation(
            "P0-G1",
            f"PDF could not be opened (possibly encrypted or corrupted): {exc}",
            {"pdf_path": str(pdf_path), "error": str(exc)},
        ) from exc

    try:
        page_count = len(pdf.pages)

        if page_count == 0:
            raise GateViolation(
                "P0-G1",
                "PDF has zero pages",
                {"pdf_path": str(pdf_path)},
            )

        # Extract text from all pages
        page_texts: list[str] = []
        tables_detected: list[dict[str, Any]] = []
        total_chars = 0
        non_empty_pages = 0

        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            page_texts.append(page_text)

            if page_text.strip():
                non_empty_pages += 1
                total_chars += len(page_text)

            # Detect tables on each page using pdfplumber's table detection
            try:
                page_tables = page.extract_tables()
                if page_tables:
                    for tbl_idx, tbl in enumerate(page_tables):
                        tables_detected.append({
                            "page": page_idx + 1,
                            "table_index": tbl_idx,
                            "rows": len(tbl) if tbl else 0,
                            "cols": len(tbl[0]) if tbl and tbl[0] else 0,
                        })
            except Exception as table_exc:
                logger.warning(
                    "Table detection failed on page %d of %s: %s",
                    page_idx + 1,
                    pdf_path,
                    table_exc,
                )

        canonical_text = "\n\n".join(page_texts)

        # Gate P0-G1: PDF must have parseable text
        if not canonical_text.strip():
            raise GateViolation(
                "P0-G1",
                "PDF contains no extractable text (possibly a scanned image-only PDF)",
                {"pdf_path": str(pdf_path), "page_count": page_count},
            )

        # Quality assessment
        pdf_quality = _assess_quality(
            canonical_text=canonical_text,
            page_count=page_count,
            non_empty_pages=non_empty_pages,
            total_chars=total_chars,
        )

        # Detect section headers
        sections = _detect_sections(canonical_text)

        # Detect figures from caption patterns in text
        has_figures = bool(_FIGURE_CAPTION_PATTERN.search(canonical_text))

        # Detect tables from pdfplumber detection OR caption patterns
        has_tables = bool(tables_detected) or bool(
            _TABLE_CAPTION_PATTERN.search(canonical_text)
        )

        # Extract basic PDF metadata
        metadata = _extract_metadata(pdf)

        logger.info(
            "PDF ingested: path=%s pages=%d quality=%s has_tables=%s has_figures=%s sections=%d",
            pdf_path,
            page_count,
            pdf_quality,
            has_tables,
            has_figures,
            len(sections),
        )

        return {
            "canonical_text": canonical_text,
            "pdf_quality": pdf_quality,
            "page_count": page_count,
            "has_tables": has_tables,
            "has_figures": has_figures,
            "sections": sections,
            "metadata": metadata,
            "tables_detected": tables_detected,
        }

    finally:
        pdf.close()


def _assess_quality(
    canonical_text: str,
    page_count: int,
    non_empty_pages: int,
    total_chars: int,
) -> str:
    """Assess PDF parsing quality based on character density and encoding issues.

    Returns one of: GOOD, DEGRADED, SCAN.
    """
    if page_count == 0:
        return PDF_QUALITY_SCAN

    # Character density per page (average for non-empty pages)
    if non_empty_pages == 0:
        return PDF_QUALITY_SCAN

    chars_per_page = total_chars / non_empty_pages

    # Check for encoding issues: excessive replacement characters, control chars
    replacement_chars = canonical_text.count("\ufffd")
    control_char_count = sum(
        1 for c in canonical_text
        if ord(c) < 32 and c not in ("\n", "\r", "\t")
    )
    encoding_issue_ratio = (replacement_chars + control_char_count) / max(total_chars, 1)

    # Empty page ratio
    empty_page_ratio = 1.0 - (non_empty_pages / page_count)

    # Heuristic quality assessment
    # A typical academic paper has 2000-4000 chars per page
    if chars_per_page < 100:
        # Very low char density suggests scanned PDF
        logger.info(
            "PDF quality SCAN: chars_per_page=%.0f (below 100 threshold)",
            chars_per_page,
        )
        return PDF_QUALITY_SCAN

    if (
        chars_per_page < 500
        or encoding_issue_ratio > 0.05
        or empty_page_ratio > 0.5
    ):
        logger.info(
            "PDF quality DEGRADED: chars_per_page=%.0f encoding_issues=%.3f empty_pages=%.2f",
            chars_per_page,
            encoding_issue_ratio,
            empty_page_ratio,
        )
        return PDF_QUALITY_DEGRADED

    return PDF_QUALITY_GOOD


def _detect_sections(canonical_text: str) -> list[dict[str, Any]]:
    """Detect section headers in the canonical text.

    Returns a list of dicts with keys:
        section_type: str - e.g., 'abstract', 'methods', 'results'
        heading: str - The actual heading text
        char_start: int - Character offset of the heading
    """
    sections: list[dict[str, Any]] = []

    for line_match in re.finditer(r"^(.+)$", canonical_text, re.MULTILINE):
        line_text = line_match.group(1).strip()
        # Skip very long lines (unlikely to be section headers)
        if len(line_text) > 100:
            continue

        for section_type, pattern in _SECTION_PATTERNS:
            if pattern.match(line_text):
                sections.append({
                    "section_type": section_type,
                    "heading": line_text,
                    "char_start": line_match.start(),
                })
                break

    return sections


def _extract_metadata(pdf: Any) -> dict[str, Any]:
    """Extract basic PDF metadata (title, author, creation date) if available."""
    metadata: dict[str, Any] = {}

    try:
        pdf_metadata = pdf.metadata or {}
        if pdf_metadata.get("Title"):
            metadata["title"] = pdf_metadata["Title"]
        if pdf_metadata.get("Author"):
            metadata["author"] = pdf_metadata["Author"]
        if pdf_metadata.get("CreationDate"):
            metadata["creation_date"] = pdf_metadata["CreationDate"]
        if pdf_metadata.get("Creator"):
            metadata["creator"] = pdf_metadata["Creator"]
    except Exception as exc:
        logger.warning("Could not extract PDF metadata: %s", exc)

    return metadata
