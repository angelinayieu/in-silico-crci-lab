# VERIFIED: formulas — none (outcome extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG04
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG04 OutcomeAgent)
Formulas: None
Reads: PaperMap.sections[Methods, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + Annotations for outcome measures,
        instruments, measurement timepoints
        (consumed by reconciliation.py, trust boundary)
Gates: None (STANDARD/DEEP mode gate enforced at orchestration level)
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
from crci.llm.response_schemas import OutcomeResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class OutcomeAgent(BaseAgent):
    """AG04 -- Extract outcome measures, instruments, measurement timepoints.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Reads: PaperMap.sections[Methods, Results]
    Outputs: SpanLabel[] + Annotations
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG04"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return OutcomeResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag04_outcome.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for outcome agent.

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
            candidate_spans=candidate_spans if candidate_spans else "(no candidate spans)",
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert OutcomeResponse to AgentOutput.

        Creates SpanLabel entries for each outcome instrument name found
        in the text, and annotations for detailed instrument metadata.
        """
        outcome_resp: OutcomeResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        for measure in outcome_resp.outcomes:
            # Try to locate instrument name in paper text
            instrument_name = measure.instrument_name
            instr_start = paper_map.full_text.find(instrument_name)

            if instr_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag04_{uuid.uuid4().hex[:12]}",
                        label_type="OUTCOME_INSTRUMENT",
                        value=instrument_name,
                        numeric_value=None,
                        char_start=instr_start,
                        char_end=instr_start + len(instrument_name),
                        confidence=0.9,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG04: instrument '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: instrument=%s, reason: text not located.",
                    instrument_name,
                    instrument_name,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag04_{uuid.uuid4().hex[:12]}",
                        label_type="OUTCOME_INSTRUMENT",
                        value=instrument_name,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="methods",
                    )
                )

            # Create SpanLabels for each timepoint mentioned
            for tp in measure.timepoints:
                tp_start = paper_map.full_text.find(tp)
                if tp_start >= 0:
                    span_labels.append(
                        SpanLabel(
                            span_id=f"ag04_{uuid.uuid4().hex[:12]}",
                            label_type="MEASUREMENT_TIMEPOINT",
                            value=tp,
                            numeric_value=None,
                            char_start=tp_start,
                            char_end=tp_start + len(tp),
                            confidence=0.8,
                            source_section="methods",
                        )
                    )
                else:
                    logger.info(
                        "AG04: timepoint '%s' not found in canonical text, "
                        "creating SpanLabel with offset 0. "
                        "Entity: timepoint=%s for instrument=%s, "
                        "reason: text not located.",
                        tp,
                        tp,
                        instrument_name,
                    )
                    span_labels.append(
                        SpanLabel(
                            span_id=f"ag04_{uuid.uuid4().hex[:12]}",
                            label_type="MEASUREMENT_TIMEPOINT",
                            value=tp,
                            numeric_value=None,
                            char_start=0,
                            char_end=0,
                            confidence=0.6,
                            source_section="methods",
                        )
                    )

            # Annotation for instrument details
            content_parts = [f"Instrument: {instrument_name}"]
            if measure.instrument_id:
                content_parts.append(f"ID: {measure.instrument_id}")
            if measure.domain:
                content_parts.append(f"Domain: {measure.domain}")
            if measure.timepoints:
                content_parts.append(f"Timepoints: {', '.join(measure.timepoints)}")

            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag04_ann_{uuid.uuid4().hex[:12]}",
                    category="measurement_limitation",
                    content="; ".join(content_parts),
                    evidence_strength="moderate",
                    extraction_snippet=instrument_name,
                )
            )

        metadata = {
            "n_outcomes": len(outcome_resp.outcomes),
            "instruments": [
                {
                    "name": m.instrument_name,
                    "id": m.instrument_id,
                    "domain": m.domain,
                    "timepoints": m.timepoints,
                }
                for m in outcome_resp.outcomes
            ],
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )
