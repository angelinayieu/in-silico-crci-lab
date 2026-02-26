"""
Component: SYS_EXTRACTION.EX-P1.ISL
Spec: SYS_EXTRACTION_COMPLETE.md (MA-8 included study list)
      PAPER_TYPE_ROUTING_AND_ACQUISITION.md §2
Purpose: Extract DOIs/PMIDs of included/constituent studies from SR/MA papers
         using LLM, for hop discovery via hop_discoverer.py.
Reads: Canonical text from P1 (via LLM call)
Writes: List of identifier dicts [{doi, pmid, title, first_author, year}]
        (consumed by P1 runner → study_registry_v1.included_study_ids_json)
Gates: None
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from crci.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Max chars to send to LLM for study list extraction
_MAX_TEXT_CHARS = 12000


class _IncludedStudyEntry(BaseModel):
    """Single included study from SR/MA."""
    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    first_author: str | None = None
    year: int | None = None


class _IncludedStudiesResponse(BaseModel):
    """LLM response schema for included study extraction."""
    studies: list[_IncludedStudyEntry] = Field(default_factory=list)


def extract_included_studies(
    llm_client: LLMClient,
    canonical_text: str,
    paper_id: str,
    title: str | None = None,
) -> list[dict[str, Any]]:
    """Extract included study identifiers from an SR/MA paper.

    Uses the LLM to scan the references/results section for DOIs, PMIDs,
    and bibliographic metadata of studies included in the review.

    Args:
        llm_client: Configured LLM client.
        canonical_text: Full text of the paper.
        paper_id: Paper identifier for logging.
        title: Optional paper title for context.

    Returns:
        List of dicts with keys: doi, pmid, title, first_author, year.
        Empty list if extraction fails or no studies found.
    """
    if not canonical_text:
        logger.warning("P1-ISL: No canonical text for %s", paper_id)
        return []

    # Focus on references and results sections (last portion of text
    # typically has references, but also check for "included studies" tables)
    text_to_send = _focus_text(canonical_text)

    prompt = _build_prompt(text_to_send, title)

    try:
        response = llm_client.call(
            prompt=prompt,
            response_schema=_IncludedStudiesResponse,
            system_prompt=(
                "You are a systematic review analysis assistant. "
                "Extract bibliographic identifiers of studies included in "
                "this systematic review or meta-analysis. Return valid JSON."
            ),
        )

        included_ids = [
            {
                "doi": s.doi,
                "pmid": str(s.pmid) if s.pmid else None,
                "title": s.title,
                "first_author": s.first_author,
                "year": s.year,
            }
            for s in response.studies
            if s.doi or s.pmid or (s.first_author and s.year) or s.title
        ]
        logger.info(
            "P1-ISL: Extracted %d included studies for %s",
            len(included_ids), paper_id,
        )
        return included_ids

    except Exception as exc:
        logger.error("P1-ISL: LLM call failed for %s: %s", paper_id, exc)
        return []


def _focus_text(canonical_text: str) -> str:
    """Extract the most relevant portions of text for study list extraction.

    Prioritizes: references section, tables of included studies, results section.
    """
    text = canonical_text

    # Try to find a references section
    ref_patterns = [
        r"(?i)\n\s*references\s*\n",
        r"(?i)\n\s*bibliography\s*\n",
        r"(?i)\n\s*works cited\s*\n",
    ]
    ref_start = None
    for pattern in ref_patterns:
        match = re.search(pattern, text)
        if match:
            ref_start = match.start()
            break

    # Try to find "included studies" or "characteristics of included studies"
    table_patterns = [
        r"(?i)characteristics?\s+of\s+included\s+stud",
        r"(?i)table\s+\d+[.:]\s*included\s+stud",
        r"(?i)included\s+studies",
        r"(?i)eligible\s+studies",
    ]
    table_start = None
    for pattern in table_patterns:
        match = re.search(pattern, text)
        if match:
            table_start = max(0, match.start() - 200)
            break

    # Build focused text: table of included studies + references
    parts = []
    if table_start is not None:
        parts.append(text[table_start:table_start + 5000])
    if ref_start is not None:
        parts.append(text[ref_start:ref_start + 6000])

    if parts:
        focused = "\n\n---\n\n".join(parts)
    else:
        # Fallback: use last portion of text (likely contains references)
        focused = text[-_MAX_TEXT_CHARS:]

    return focused[:_MAX_TEXT_CHARS]


def _build_prompt(text: str, title: str | None) -> str:
    """Build the LLM prompt for included study extraction."""
    title_ctx = f"Paper title: {title}\n\n" if title else ""

    return f"""{title_ctx}Below is text from a systematic review or meta-analysis paper. \
Extract ALL studies that were included in this review/meta-analysis.

For each included study, provide:
- "doi": the DOI if mentioned (null if not found)
- "pmid": the PubMed ID if mentioned (null if not found)
- "title": the study title if identifiable (null if not found)
- "first_author": the first author's last name (null if not found)
- "year": publication year as integer (null if not found)

Return a JSON object with a "studies" key containing an array of objects. Example:
{{"studies": [
  {{"doi": "10.1234/example", "pmid": "12345678", "title": "Study of X", "first_author": "Smith", "year": 2020}},
  {{"doi": null, "pmid": null, "title": null, "first_author": "Jones", "year": 2019}}
]}}

If you cannot identify any included studies, return: {{"studies": []}}

IMPORTANT:
- Only include studies that were INCLUDED in the review (not excluded or just cited)
- Look for study flow diagrams (PRISMA), tables of included studies, and reference lists
- Extract as many identifiers as possible for each study

Text:
{text}
"""


def _parse_response(raw_text: str) -> list[dict[str, Any]]:
    """Parse LLM response into list of study identifier dicts."""
    # Try to extract JSON array from the response
    # Handle markdown code blocks
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```", 1)[0]

    text = text.strip()

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return _validate_entries(parsed)
        elif isinstance(parsed, dict) and "studies" in parsed:
            return _validate_entries(parsed["studies"])
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in text
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return _validate_entries(parsed)
        except json.JSONDecodeError:
            pass

    logger.warning("P1-ISL: Could not parse LLM response as JSON array")
    return []


def _validate_entries(entries: list) -> list[dict[str, Any]]:
    """Validate and normalize study identifier entries."""
    valid = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        # Must have at least one identifier (doi, pmid, first_author+year)
        has_doi = bool(entry.get("doi"))
        has_pmid = bool(entry.get("pmid"))
        has_author_year = bool(entry.get("first_author")) and entry.get("year")
        has_title = bool(entry.get("title"))

        if has_doi or has_pmid or has_author_year or has_title:
            normalized = {
                "doi": entry.get("doi"),
                "pmid": str(entry["pmid"]) if entry.get("pmid") else None,
                "title": entry.get("title"),
                "first_author": entry.get("first_author"),
                "year": int(entry["year"]) if entry.get("year") else None,
            }
            valid.append(normalized)

    return valid
