# VERIFIED: formulas — none (temporal extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG08
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG08 TemporalAgent)
Formulas: None
Reads: PaperMap.sections[Methods, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + Annotations for measurement timepoints,
        follow-up duration, temporal patterns
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
from crci.llm.response_schemas import TemporalResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class TemporalAgent(BaseAgent):
    """AG08 -- Extract measurement timepoints, follow-up duration, temporal patterns.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Reads: PaperMap.sections[Methods, Results]
    Outputs: SpanLabel[] + Annotations
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG08"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return TemporalResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag08_temporal.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for temporal agent.

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
        """Convert TemporalResponse to AgentOutput.

        Creates SpanLabel entries for each timepoint extracted,
        and annotations for follow-up duration and temporal patterns.
        """
        temporal_resp: TemporalResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        for tp in temporal_resp.timepoints:
            tp_label = tp.timepoint_label

            # Try to locate timepoint label in paper text
            tp_start = paper_map.full_text.find(tp_label)
            if tp_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08_{uuid.uuid4().hex[:12]}",
                        label_type="TIMEPOINT",
                        value=tp_label,
                        numeric_value=tp.days_from_baseline,
                        char_start=tp_start,
                        char_end=tp_start + len(tp_label),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG08: timepoint '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: timepoint=%s, reason: text not located.",
                    tp_label,
                    tp_label,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08_{uuid.uuid4().hex[:12]}",
                        label_type="TIMEPOINT",
                        value=tp_label,
                        numeric_value=tp.days_from_baseline,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

            # Annotation for timepoint details
            tp_content_parts = [f"Timepoint: {tp_label}"]
            if tp.days_from_baseline is not None:
                tp_content_parts.append(
                    f"Days from baseline: {tp.days_from_baseline}"
                )
            if tp.measurement_type:
                tp_content_parts.append(
                    f"Measurement type: {tp.measurement_type}"
                )

            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag08_ann_{uuid.uuid4().hex[:12]}",
                    category="temporal_onset",
                    content="; ".join(tp_content_parts),
                    evidence_strength="moderate",
                    extraction_snippet=tp_label,
                )
            )

        # SpanLabel for follow-up duration
        if temporal_resp.follow_up_weeks is not None:
            fu_str = str(temporal_resp.follow_up_weeks)
            fu_start = paper_map.full_text.find(fu_str)
            if fu_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08_{uuid.uuid4().hex[:12]}",
                        label_type="FOLLOW_UP_WEEKS",
                        value=fu_str,
                        numeric_value=temporal_resp.follow_up_weeks,
                        char_start=fu_start,
                        char_end=fu_start + len(fu_str),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG08: follow_up_weeks '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: follow_up_weeks=%s, reason: text not located.",
                    fu_str,
                    fu_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08_{uuid.uuid4().hex[:12]}",
                        label_type="FOLLOW_UP_WEEKS",
                        value=fu_str,
                        numeric_value=temporal_resp.follow_up_weeks,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # Annotation for temporal pattern
        if temporal_resp.temporal_pattern:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag08_ann_{uuid.uuid4().hex[:12]}",
                    category="temporal_onset",
                    content=f"Temporal pattern: {temporal_resp.temporal_pattern}",
                    evidence_strength="moderate",
                    extraction_snippet=temporal_resp.temporal_pattern,
                )
            )

        metadata = {
            "n_timepoints": len(temporal_resp.timepoints),
            "follow_up_weeks": temporal_resp.follow_up_weeks,
            "temporal_pattern": temporal_resp.temporal_pattern,
            "timepoints": [
                {
                    "label": tp.timepoint_label,
                    "days_from_baseline": tp.days_from_baseline,
                    "measurement_type": tp.measurement_type,
                }
                for tp in temporal_resp.timepoints
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
