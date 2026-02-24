# VERIFIED: no formulas (LLM classification)
# VERIFIED: imports — pathlib + logging + shared.models.enums + llm.client + llm.response_schemas
# VERIFIED: backward wiring — reads IngestedPaper dict from pdf_ingestion.py
# VERIFIED: forward wiring — writes PaperSubtype for mode_selection.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no gates (classification does not gate)
"""
Component: SYS_EXTRACTION.EX-P0.P0-PTC
Spec: SYS_EXTRACTION_COMPLETE.md lines 240-265 (implied from chain card)
Formulas: None (LLM classification)
Reads: IngestedPaper dict (from pdf_ingestion.py), canonical_text
Writes: PaperSubtype enum (consumed by mode_selection.py)
Gates: None (classification feeds into mode_selection which routes)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crci.llm.client import LLMClient, LLMClientError
from crci.llm.response_schemas import PaperTypeClassification
from crci.shared.models.enums import PaperSubtype

logger = logging.getLogger(__name__)

# Path to the prompt template
_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "ptc_prompt.txt"

# Maximum text length to send to LLM (avoid token limits)
_MAX_TEXT_LENGTH = 15_000

# Valid PaperSubtype values for validation
_VALID_SUBTYPES: set[str] = {member.value for member in PaperSubtype}


def classify_paper_type(
    ingested_paper: dict[str, Any],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Classify paper into one of 23 PaperSubtype values using Claude.

    P0-PTC: Paper Type Classifier.
    Uses the LLM to classify the paper based on its canonical text.
    Falls back to PaperSubtype.OTHER on LLM failure.

    Args:
        ingested_paper: Output from pdf_ingestion.ingest_pdf().
        llm_client: LLMClient instance. If None, creates a default one.

    Returns:
        Dict with keys:
            paper_subtype: PaperSubtype enum value
            confidence: float [0,1]
            reasoning: str | None
    """
    canonical_text = ingested_paper.get("canonical_text", "")

    if not canonical_text.strip():
        logger.warning(
            "Paper type classification: empty canonical text, "
            "defaulting to PaperSubtype.OTHER"
        )
        return {
            "paper_subtype": PaperSubtype.OTHER,
            "confidence": 0.0,
            "reasoning": "Empty canonical text; cannot classify.",
        }

    # Truncate text if needed to stay within token limits
    paper_text = canonical_text[:_MAX_TEXT_LENGTH]
    if len(canonical_text) > _MAX_TEXT_LENGTH:
        logger.info(
            "Paper type classification: truncated text from %d to %d chars",
            len(canonical_text),
            _MAX_TEXT_LENGTH,
        )

    # Load prompt template
    prompt = _load_and_fill_prompt(paper_text)

    # Initialize LLM client if not provided
    if llm_client is None:
        llm_client = LLMClient()

    # Call LLM
    try:
        result: PaperTypeClassification = llm_client.call(
            prompt=prompt,
            response_schema=PaperTypeClassification,
        )
    except LLMClientError as exc:
        logger.error(
            "Paper type classification LLM call failed: %s. "
            "Defaulting to PaperSubtype.OTHER",
            exc,
        )
        return {
            "paper_subtype": PaperSubtype.OTHER,
            "confidence": 0.0,
            "reasoning": f"LLM classification failed: {exc}",
        }

    # Validate the returned subtype against the enum
    paper_subtype = _validate_subtype(result.paper_subtype)

    logger.info(
        "Paper type classified: subtype=%s confidence=%.2f reasoning=%s",
        paper_subtype.value,
        result.confidence,
        result.reasoning,
    )

    return {
        "paper_subtype": paper_subtype,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
    }


def _load_and_fill_prompt(paper_text: str) -> str:
    """Load the PTC prompt template and fill in the paper text.

    Args:
        paper_text: The (potentially truncated) paper text.

    Returns:
        Filled prompt string ready for LLM call.
    """
    try:
        template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(
            "PTC prompt template not found at %s. Using inline fallback.",
            _PROMPT_TEMPLATE_PATH,
        )
        # Inline fallback prompt (minimal)
        template = (
            "Classify the following paper into one of the 23 CRCI paper subtypes. "
            "Valid subtypes: RCT_exercise, RCT_cognitive, RCT_pharmacological, "
            "RCT_multimodal, meta_analysis, systematic_review, longitudinal_cohort, "
            "cross_sectional, intensive_longitudinal, mechanistic_animal, "
            "mechanistic_human, imaging_structural, imaging_functional, "
            "biomarker_discovery, dose_response, safety_report, guideline, "
            "case_report, editorial, review_narrative, protocol, qualitative, other.\n\n"
            "Paper text:\n---\n{paper_text}\n---\n\n"
            "Respond with JSON: "
            '{{\"paper_subtype\": \"<subtype>\", \"confidence\": <float>, '
            '\"reasoning\": \"<reason>\"}}'
        )

    return template.replace("{paper_text}", paper_text)


def _validate_subtype(raw_subtype: str) -> PaperSubtype:
    """Validate and convert the LLM-returned subtype string to PaperSubtype enum.

    Falls back to PaperSubtype.OTHER if the value is invalid.
    """
    # Direct match
    if raw_subtype in _VALID_SUBTYPES:
        return PaperSubtype(raw_subtype)

    # Case-insensitive match
    raw_lower = raw_subtype.lower().strip()
    for member in PaperSubtype:
        if member.value.lower() == raw_lower:
            return member

    # Partial matching for common LLM variations
    # e.g., "RCT_Exercise" -> "RCT_exercise"
    for member in PaperSubtype:
        if raw_lower.replace("-", "_").replace(" ", "_") == member.value.lower():
            return member

    logger.warning(
        "Paper type classification returned invalid subtype '%s'. "
        "Defaulting to PaperSubtype.OTHER",
        raw_subtype,
    )
    return PaperSubtype.OTHER
