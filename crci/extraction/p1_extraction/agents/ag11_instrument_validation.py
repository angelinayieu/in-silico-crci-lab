# VERIFIED: formulas — none (psychometric property extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput with SpanLabel[] for tb_trust_boundary (TB-PSYCH rules)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P1-G2 partial: validates >= 1 SpanLabel produced
"""
Component: SYS_EXTRACTION.EX-P1.AG11
Spec: SYS_EXTRACTION_ADDENDUM Part 3 (AG11 InstrumentValidationAgent)
Formulas: None (LLM extraction)
Reads: PaperMap.sections[Methods, Results, Tables] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] (12 psychometric label types)
        — grouped by {instrument_name × subscale × population}
        (consumed by TB-PSYCH in trust boundary, then psychometric_compiler in P7)
Gates: P1-G2 partial (>= 1 SpanLabel produced, enforced here)
"""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from crci.extraction.p1_extraction.agents.base_agent import (
    AgentOutput,
    BaseAgent,
)
from crci.llm.client import LLMClient
from crci.llm.response_schemas import InstrumentValidationResponse
from crci.shared.models.enums import AnnotationCategory
from crci.shared.models.intermediate_states import (
    GateViolation,
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)

# ─── 12 psychometric label types (SYS_EXTRACTION_ADDENDUM Part 3) ───
AG11_LABEL_TYPES: list[str] = [
    # Reliability Measures (1-4)
    "CRONBACHS_ALPHA",
    "TEST_RETEST_RELIABILITY",
    "INTERNAL_CONSISTENCY_N",
    "SEM_VALUE",
    # Validity and Structure (5-8)
    "FACTOR_LOADING",
    "FACTOR_STRUCTURE",
    "CONVERGENT_VALIDITY",
    "DISCRIMINANT_VALIDITY",
    # Measurement Properties (9-10)
    "MEASUREMENT_INVARIANCE",
    "INSTRUMENT_NAME",
    # Context Labels (11-12)
    "INSTRUMENT_SUBSCALE",
    "POPULATION_DESCRIPTOR",
]

# Common LLM output variants → canonical label types
_LABEL_NORMALIZATION: dict[str, str] = {
    "ALPHA": "CRONBACHS_ALPHA",
    "CRONBACH_ALPHA": "CRONBACHS_ALPHA",
    "RELIABILITY": "CRONBACHS_ALPHA",
    "INTERNAL_CONSISTENCY": "CRONBACHS_ALPHA",
    "TEST_RETEST": "TEST_RETEST_RELIABILITY",
    "RETEST_RELIABILITY": "TEST_RETEST_RELIABILITY",
    "CONSISTENCY_N": "INTERNAL_CONSISTENCY_N",
    "RELIABILITY_N": "INTERNAL_CONSISTENCY_N",
    "SAMPLE_SIZE_RELIABILITY": "INTERNAL_CONSISTENCY_N",
    "SEM": "SEM_VALUE",
    "STANDARD_ERROR_MEASUREMENT": "SEM_VALUE",
    "LOADING": "FACTOR_LOADING",
    "FACTOR_LOADINGS": "FACTOR_LOADING",
    "FACTOR_ANALYSIS": "FACTOR_STRUCTURE",
    "CFA": "FACTOR_STRUCTURE",
    "EFA": "FACTOR_STRUCTURE",
    "MODEL_FIT": "FACTOR_STRUCTURE",
    "CONVERGENT": "CONVERGENT_VALIDITY",
    "DISCRIMINANT": "DISCRIMINANT_VALIDITY",
    "INVARIANCE": "MEASUREMENT_INVARIANCE",
    "DIF": "MEASUREMENT_INVARIANCE",
    "INSTRUMENT": "INSTRUMENT_NAME",
    "SCALE_NAME": "INSTRUMENT_NAME",
    "QUESTIONNAIRE": "INSTRUMENT_NAME",
    "SUBSCALE": "INSTRUMENT_SUBSCALE",
    "POPULATION": "POPULATION_DESCRIPTOR",
    "SAMPLE_DESCRIPTION": "POPULATION_DESCRIPTOR",
}

_AG11_LABEL_SET: set[str] = set(AG11_LABEL_TYPES)


class InstrumentValidationAgent(BaseAgent):
    """AG11 -- Extract instrument psychometric properties from validation studies.

    Activated for PSYCHOMETRIC_VALIDATION papers.

    Reads: PaperMap.sections[Methods, Results, Tables]
    Outputs: SpanLabel[] with 12 psychometric label types, grouped by
             {instrument_name x subscale x population}
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG11"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results", "tables"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return InstrumentValidationResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag11_instrument_validation.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for instrument validation agent.

        Loads the prompt template and fills in the focused text,
        paper_id, table text, and candidate spans.
        """
        template = self._load_prompt_template()
        table_text = self._get_table_text(paper_map)
        candidate_spans = self._get_candidate_spans_text(paper_map)
        return template.format(
            focused_text=focused_text,
            paper_id=paper_map.paper_id,
            table_text=table_text if table_text else "(no tables detected)",
            candidate_spans=(
                candidate_spans if candidate_spans else "(no candidate spans)"
            ),
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert InstrumentValidationResponse to AgentOutput.

        Creates SpanLabel entries for each psychometric property,
        with label type normalization and offset validation.
        """
        iv_resp: InstrumentValidationResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []
        text_len = len(paper_map.full_text)

        for raw_span in iv_resp.spans:
            # ─── Normalize label type ────────────────────────
            label_type = self._normalize_label_type(raw_span.label_type)
            if label_type is None:
                logger.warning(
                    "AG11: unrecognized label_type '%s' for span '%s', skipping",
                    raw_span.label_type,
                    raw_span.span_text[:50],
                )
                continue

            # ─── Validate char offsets ───────────────────────
            char_start = max(0, raw_span.char_start)
            char_end = max(char_start, raw_span.char_end)
            if char_start >= text_len:
                char_start = 0
                char_end = 0
            elif char_end > text_len:
                char_end = text_len

            # ─── Try to extract numeric value ────────────────
            numeric_value = self._try_parse_numeric(raw_span.span_text)

            # ─── Determine source section ────────────────────
            source_section = self._determine_source_section(
                paper_map, char_start
            )
            source_table_id = self._determine_source_table(
                paper_map, char_start, char_end
            )

            span_labels.append(
                SpanLabel(
                    span_id=f"ag11_{uuid.uuid4().hex[:12]}",
                    label_type=label_type,
                    value=raw_span.span_text,
                    numeric_value=numeric_value,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=raw_span.confidence,
                    source_section=source_section,
                    source_table_id=source_table_id,
                )
            )

        # ─── Gate P1-G2: at least 1 SpanLabel ─────────────────
        if not span_labels:
            raise GateViolation(
                "P1-G2",
                f"AG11: no valid SpanLabels produced for paper_id={paper_map.paper_id}. "
                "This may indicate the paper lacks psychometric content "
                "or the LLM failed to extract.",
                {"paper_id": paper_map.paper_id, "agent": "AG11"},
            )

        # ─── Build metadata ─────────────────────────────────
        label_counts = self._count_label_types(span_labels)
        grouping_ids = {
            s.value
            for raw_s in iv_resp.spans
            if (s := type("_", (), {"value": raw_s.grouping_id})())
            and raw_s.grouping_id is not None
        }

        # ─── Create annotation for instrument summary ────────
        instrument_names = [
            s.value
            for s in span_labels
            if s.label_type == "INSTRUMENT_NAME" and s.value
        ]
        if instrument_names:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag11_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.MEASUREMENT_LIMITATION,
                    content=(
                        f"Psychometric properties extracted for: "
                        f"{', '.join(set(instrument_names))}"
                    ),
                    evidence_strength="strong",
                    extraction_snippet=None,
                )
            )

        metadata: dict[str, Any] = {
            "total_extracted": len(span_labels),
            "label_type_distribution": label_counts,
            "n_groupings": len(grouping_ids),
            "instruments_found": list(set(instrument_names)),
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )

    # ─── Private helpers ─────────────────────────────────────

    def _normalize_label_type(self, raw_type: str) -> str | None:
        """Normalize LLM-returned label type to canonical AG11 type.

        Returns None if unrecognizable.
        """
        upper = raw_type.strip().upper()

        # Direct match
        if upper in _AG11_LABEL_SET:
            return upper

        # Normalization table
        if upper in _LABEL_NORMALIZATION:
            return _LABEL_NORMALIZATION[upper]

        # Try removing common prefixes/suffixes
        for suffix in ("_VALUE", "_SCORE", "_COEFFICIENT"):
            stripped = upper.replace(suffix, "")
            if stripped in _AG11_LABEL_SET:
                return stripped

        return None

    @staticmethod
    def _try_parse_numeric(span_text: str) -> float | None:
        """Extract numeric value from span text if possible."""
        cleaned = span_text.strip()
        # Handle common patterns: "0.89", ".82", "-0.3", "= 0.91"
        match = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    @staticmethod
    def _determine_source_section(
        paper_map: PaperMap, char_start: int
    ) -> str | None:
        """Determine which section a character offset falls in."""
        cumulative = 0
        for section in paper_map.sections:
            section_len = len(section.text)
            if cumulative <= char_start < cumulative + section_len:
                return section.section_type
            cumulative += section_len + 2  # account for separator
        return None

    @staticmethod
    def _determine_source_table(
        paper_map: PaperMap, char_start: int, char_end: int
    ) -> str | None:
        """Determine if span falls within a detected table region."""
        if not paper_map.tables:
            return None
        for table in paper_map.tables:
            if (
                hasattr(table, "char_start")
                and hasattr(table, "char_end")
                and table.char_start is not None
                and table.char_end is not None
                and table.char_start <= char_start
                and char_end <= table.char_end
            ):
                return table.table_id
        return None

    @staticmethod
    def _count_label_types(span_labels: list[SpanLabel]) -> dict[str, int]:
        """Count spans per label type."""
        counts: dict[str, int] = {}
        for span in span_labels:
            counts[span.label_type] = counts.get(span.label_type, 0) + 1
        return counts
