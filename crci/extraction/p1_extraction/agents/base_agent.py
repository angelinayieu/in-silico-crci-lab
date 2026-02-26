# VERIFIED: formulas — none (framework only)
# VERIFIED: imports — all modules exist (llm.client, shared.models.intermediate_states)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for downstream reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P1-G2 enforced at orchestration level, not per-agent
"""
Component: SYS_EXTRACTION.EX-P1.BASE_AGENT
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-420 (agent architecture, parallel exec)
      FILE_CONTEXT_MANIFEST — base_agent.py entry
Formulas: None (framework only)
Reads: PaperMap (from canonical_reader.py)
Writes: AgentOutput (consumed by reconciliation.py, trust boundary)
Gates: None (per-agent; P1-G2 enforced at orchestration level)
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from crci.llm.client import LLMClient, LLMResponseValidationError
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SectionSegment,
    SpanLabel,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentOutput(BaseModel):
    """Standard output from any extraction agent.

    Contains both SpanLabel[] (for numeric trust boundary)
    and RawAnnotationEmission[] (for annotation trust boundary).
    """

    agent_id: str
    paper_id: str
    span_labels: list[SpanLabel] = Field(default_factory=list)
    annotations: list[RawAnnotationEmission] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    completion_status: str = "success"
    elapsed_ms: float = 0.0


class BaseAgent(ABC):
    """Abstract base for all 10 extraction agents.

    Each agent:
      1. Receives PaperMap + list of target section types
      2. Builds section-focused text from PaperMap
      3. Loads agent-specific prompt template
      4. Calls LLM via llm/client.py with agent-specific prompt
      5. Validates response against agent-specific schema
      6. Converts to typed AgentOutput (SpanLabel[] + annotations)
      7. Logs completion checkpoint

    Subclasses must implement:
      - agent_id: str property
      - target_sections: list[str] property
      - response_schema: type[BaseModel] property
      - prompt_template_path: Path property
      - _build_prompt(focused_text, paper_map) -> str
      - _parse_response(response, paper_map) -> AgentOutput
    """

    # Max parse-failure retries before giving up
    PARSE_RETRY_LIMIT = 2

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._prompt_template: str | None = None

    # ─── Abstract properties ────────────────────────────────────

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique agent identifier (e.g., 'AG01', 'AG05')."""

    @property
    @abstractmethod
    def target_sections(self) -> list[str]:
        """Section types this agent reads from PaperMap."""

    @property
    @abstractmethod
    def response_schema(self) -> type[BaseModel]:
        """Pydantic schema class for LLM response validation."""

    @property
    @abstractmethod
    def prompt_template_path(self) -> Path:
        """Path to the agent's prompt template file."""

    # ─── Abstract methods ───────────────────────────────────────

    @abstractmethod
    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build the full LLM prompt from template + focused text.

        Args:
            focused_text: Concatenated text from target sections.
            paper_map: Full PaperMap for additional context.

        Returns:
            Complete prompt string for LLM.
        """

    @abstractmethod
    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert LLM response to typed AgentOutput.

        Args:
            response: Validated LLM response object.
            paper_map: Full PaperMap for context/offsets.

        Returns:
            AgentOutput with span_labels and/or annotations.
        """

    # ─── Public API ────────────────────────────────────────────

    def extract(
        self, paper_map: PaperMap, sections: list[str] | None = None
    ) -> AgentOutput:
        """Execute extraction on paper_map.

        This is the main entry point called by the orchestrator.

        Args:
            paper_map: PaperMap produced by CanonicalReader.
            sections: Optional override of target section types.
                      Defaults to self.target_sections.

        Returns:
            AgentOutput with extracted span_labels and annotations.
        """
        start_time = time.monotonic()
        target = sections if sections is not None else self.target_sections

        logger.info(
            "%s: starting extraction for paper_id=%s, "
            "target_sections=%s",
            self.agent_id,
            paper_map.paper_id,
            target,
        )

        # Build focused text from target sections
        focused_text = self._extract_focused_text(paper_map, target)

        if not focused_text.strip():
            logger.warning(
                "%s: no text found in target sections %s for paper_id=%s, "
                "using full text as fallback.",
                self.agent_id,
                target,
                paper_map.paper_id,
            )
            focused_text = paper_map.full_text

        # Build prompt
        prompt = self._build_prompt(focused_text, paper_map)

        # Call LLM with retry on parse failure
        last_exc: Exception | None = None
        response = None
        for attempt in range(1, self.PARSE_RETRY_LIMIT + 1):
            try:
                response = self._llm_client.call(
                    prompt=prompt,
                    response_schema=self.response_schema,
                    system_prompt=self._get_system_prompt(),
                )
                break  # Success
            except LLMResponseValidationError as exc:
                last_exc = exc
                logger.warning(
                    "%s: LLM parse/validation failure on attempt %d/%d "
                    "for paper_id=%s: %s",
                    self.agent_id,
                    attempt,
                    self.PARSE_RETRY_LIMIT,
                    paper_map.paper_id,
                    str(exc)[:200],
                )
                if attempt < self.PARSE_RETRY_LIMIT:
                    logger.info(
                        "%s: retrying LLM call (attempt %d)...",
                        self.agent_id,
                        attempt + 1,
                    )

        if response is None:
            # All retries exhausted — return empty output with error status
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "%s: all %d parse attempts failed for paper_id=%s. "
                "Last error: %s",
                self.agent_id,
                self.PARSE_RETRY_LIMIT,
                paper_map.paper_id,
                str(last_exc)[:300] if last_exc else "unknown",
            )
            return AgentOutput(
                agent_id=self.agent_id,
                paper_id=paper_map.paper_id,
                completion_status="error_parse_failure",
                elapsed_ms=elapsed_ms,
                metadata={"error": str(last_exc)[:500] if last_exc else "unknown"},
            )

        # Parse to AgentOutput
        output = self._parse_response(response, paper_map)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        output.elapsed_ms = elapsed_ms

        # Checkpoint logging
        logger.info(
            "%s: completed paper_id=%s — "
            "span_labels=%d, annotations=%d, elapsed_ms=%.0f, "
            "status=%s",
            self.agent_id,
            paper_map.paper_id,
            len(output.span_labels),
            len(output.annotations),
            elapsed_ms,
            output.completion_status,
        )

        return output

    # ─── Protected helpers ──────────────────────────────────────

    def _extract_focused_text(
        self, paper_map: PaperMap, target_sections: list[str]
    ) -> str:
        """Extract concatenated text from target sections of PaperMap.

        Args:
            paper_map: The PaperMap to extract from.
            target_sections: List of section types to include.

        Returns:
            Concatenated text from matching sections.
        """
        parts: list[str] = []
        for section in paper_map.sections:
            if section.section_type in target_sections:
                header = (
                    f"[{section.section_type.upper()}]"
                    if section.heading is None
                    else f"[{section.section_type.upper()}: {section.heading}]"
                )
                parts.append(f"{header}\n{section.text}")
        return "\n\n".join(parts)

    def _load_prompt_template(self) -> str:
        """Load the prompt template from disk. Cached after first load."""
        if self._prompt_template is None:
            template_path = self.prompt_template_path
            if not template_path.exists():
                raise FileNotFoundError(
                    f"Prompt template not found: {template_path}"
                )
            self._prompt_template = template_path.read_text(encoding="utf-8")
        return self._prompt_template

    def _get_system_prompt(self) -> str:
        """Default system prompt for extraction agents."""
        return (
            "You are a precise scientific paper extraction agent. "
            "Extract exactly what is asked for from the paper text. "
            "Return valid JSON conforming to the specified schema. "
            "Do not hallucinate or invent data not present in the text. "
            "If a field cannot be determined, use null."
        )

    def _get_table_text(self, paper_map: PaperMap) -> str:
        """Get concatenated table text from PaperMap."""
        if not paper_map.tables:
            return ""
        parts = []
        for table in paper_map.tables:
            parts.append(
                f"[{table.table_id}] {table.caption or ''}\n{table.raw_text}"
            )
        return "\n\n".join(parts)

    def _get_candidate_spans_text(self, paper_map: PaperMap) -> str:
        """Get candidate spans formatted as text."""
        if not paper_map.candidate_spans:
            return ""
        parts = []
        for span in paper_map.candidate_spans:
            parts.append(
                f"[{span.span_id}] offset={span.char_start}-{span.char_end} "
                f"section={span.section_type}: {span.text}"
            )
        return "\n".join(parts)
