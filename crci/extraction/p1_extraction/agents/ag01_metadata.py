# VERIFIED: formulas — none (metadata extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (ALWAYS runs agent)
"""
Component: SYS_EXTRACTION.EX-P1.AG01
Spec: SYS_EXTRACTION_COMPLETE.md lines 449-453 (AG1 MetadataAgent)
      SYS_EXTRACTION_COMPLETE.md lines 412 (AG1 subsystem inventory)
Formulas: None
Reads: PaperMap.sections[title, abstract, affiliations] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + metadata (consumed by reconciliation.py)
Gates: None (ALWAYS runs)
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from pydantic import BaseModel

from crci.extraction.p1_extraction.agents.base_agent import (
    AgentOutput,
    BaseAgent,
)
from crci.llm.client import LLMClient
from crci.llm.response_schemas import MetadataResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    SpanLabel,
)

logger = logging.getLogger(__name__)

# Path to prompt template relative to this package
_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / ".." / "llm" / "prompts" / "ag01_metadata.txt"
_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "llm" / "prompts" / "ag01_metadata.txt"


class MetadataAgent(BaseAgent):
    """AG01 — Extract study title, authors, DOI, journal, year, funding.

    ALWAYS runs (all extraction modes: SHALLOW, STANDARD, DEEP).

    Reads: PaperMap.sections[title, abstract, affiliations]
    Outputs: SpanLabel[] (author, year, journal) + metadata dict
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG01"

    @property
    def target_sections(self) -> list[str]:
        return ["title", "abstract", "affiliations", "acknowledgements"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return MetadataResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag01_metadata.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for metadata agent.

        Loads the prompt template and fills in the focused text.
        """
        template = self._load_prompt_template()
        return template.format(
            focused_text=focused_text,
            paper_id=paper_map.paper_id,
            title=paper_map.title or "(unknown)",
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert MetadataResponse to AgentOutput.

        Creates SpanLabel entries for extractable metadata fields
        and stores structured metadata in the metadata dict.
        """
        meta_resp: MetadataResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []

        # Create SpanLabel for title if found
        if meta_resp.title:
            title_start = paper_map.full_text.find(meta_resp.title)
            if title_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="TITLE",
                        value=meta_resp.title,
                        numeric_value=None,
                        char_start=title_start,
                        char_end=title_start + len(meta_resp.title),
                        confidence=0.95,
                        source_section="title",
                    )
                )
            else:
                logger.info(
                    "AG01: title text not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: title=%r, reason: text not located.",
                    meta_resp.title,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="TITLE",
                        value=meta_resp.title,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="title",
                    )
                )

        # Create SpanLabel for year if found
        if meta_resp.year is not None:
            year_str = str(meta_resp.year)
            year_start = paper_map.full_text.find(year_str)
            if year_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="PUBLICATION_YEAR",
                        value=year_str,
                        numeric_value=float(meta_resp.year),
                        char_start=year_start,
                        char_end=year_start + len(year_str),
                        confidence=0.9,
                        source_section="title",
                    )
                )
            else:
                logger.info(
                    "AG01: year '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: year=%s, reason: text not located.",
                    year_str,
                    year_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="PUBLICATION_YEAR",
                        value=year_str,
                        numeric_value=float(meta_resp.year),
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="title",
                    )
                )

        # Create SpanLabel for journal if found
        if meta_resp.journal:
            journal_start = paper_map.full_text.find(meta_resp.journal)
            if journal_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="JOURNAL",
                        value=meta_resp.journal,
                        numeric_value=None,
                        char_start=journal_start,
                        char_end=journal_start + len(meta_resp.journal),
                        confidence=0.9,
                        source_section="title",
                    )
                )
            else:
                logger.info(
                    "AG01: journal '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: journal=%s, reason: text not located.",
                    meta_resp.journal,
                    meta_resp.journal,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag01_{uuid.uuid4().hex[:12]}",
                        label_type="JOURNAL",
                        value=meta_resp.journal,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="title",
                    )
                )

        # Build metadata dict with all extracted fields
        metadata = {
            "title": meta_resp.title,
            "authors": meta_resp.authors,
            "doi": meta_resp.doi,
            "journal": meta_resp.journal,
            "year": meta_resp.year,
            "funding_sources": meta_resp.funding_sources,
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=[],
            metadata=metadata,
            completion_status="success",
        )
