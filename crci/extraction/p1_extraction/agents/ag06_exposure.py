# VERIFIED: formulas — none (exposure extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG06
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG06 ExposureAgent)
Formulas: None
Reads: PaperMap.sections[Methods, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + Annotations for exposure/intervention
        details, dosage, duration, adherence
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
from crci.llm.response_schemas import ExposureResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class ExposureAgent(BaseAgent):
    """AG06 -- Extract exposure/intervention details, dosage, duration, adherence.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Reads: PaperMap.sections[Methods, Results]
    Outputs: SpanLabel[] + Annotations
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG06"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return ExposureResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag06_exposure.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for exposure agent.

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
            study_design=paper_map.study_design or "(unknown)",
            arms=", ".join(paper_map.arms) if paper_map.arms else "(not specified)",
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert ExposureResponse to AgentOutput.

        Creates SpanLabel entries for intervention type, dose, duration,
        and annotations for adherence and detailed intervention metadata.
        """
        exposure_resp: ExposureResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        # SpanLabel for intervention type
        if exposure_resp.intervention_type is not None:
            interv_text = exposure_resp.intervention_type
            interv_start = paper_map.full_text.find(interv_text)
            if interv_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="INTERVENTION_TYPE",
                        value=interv_text,
                        numeric_value=None,
                        char_start=interv_start,
                        char_end=interv_start + len(interv_text),
                        confidence=0.9,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG06: intervention_type '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: intervention_type=%s, reason: text not located.",
                    interv_text,
                    interv_text,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="INTERVENTION_TYPE",
                        value=interv_text,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="methods",
                    )
                )

        # SpanLabel for dose
        if exposure_resp.dose is not None:
            dose_text = exposure_resp.dose
            dose_unit = exposure_resp.dose_unit or ""
            dose_full = f"{dose_text} {dose_unit}".strip()
            dose_start = paper_map.full_text.find(dose_text)
            if dose_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="DOSE",
                        value=dose_full,
                        numeric_value=None,
                        char_start=dose_start,
                        char_end=dose_start + len(dose_text),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG06: dose '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: dose=%s, reason: text not located.",
                    dose_text,
                    dose_text,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="DOSE",
                        value=dose_full,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # SpanLabel for duration
        if exposure_resp.duration_weeks is not None:
            dur_str = str(exposure_resp.duration_weeks)
            dur_start = paper_map.full_text.find(dur_str)
            if dur_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="DURATION_WEEKS",
                        value=dur_str,
                        numeric_value=exposure_resp.duration_weeks,
                        char_start=dur_start,
                        char_end=dur_start + len(dur_str),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG06: duration_weeks '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: duration_weeks=%s, reason: text not located.",
                    dur_str,
                    dur_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="DURATION_WEEKS",
                        value=dur_str,
                        numeric_value=exposure_resp.duration_weeks,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # SpanLabel for frequency
        if exposure_resp.frequency is not None:
            freq_text = exposure_resp.frequency
            freq_start = paper_map.full_text.find(freq_text)
            if freq_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="FREQUENCY",
                        value=freq_text,
                        numeric_value=None,
                        char_start=freq_start,
                        char_end=freq_start + len(freq_text),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG06: frequency '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: frequency=%s, reason: text not located.",
                    freq_text,
                    freq_text,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag06_{uuid.uuid4().hex[:12]}",
                        label_type="FREQUENCY",
                        value=freq_text,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # Annotation for adherence rate
        if exposure_resp.adherence_rate is not None:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag06_ann_{uuid.uuid4().hex[:12]}",
                    category="adherence_data",
                    content=f"Adherence rate: {exposure_resp.adherence_rate}%",
                    evidence_strength="moderate",
                    extraction_snippet=None,
                )
            )

        # Annotation for full exposure details
        detail_parts: list[str] = []
        if exposure_resp.intervention_type:
            detail_parts.append(f"Intervention: {exposure_resp.intervention_type}")
        if exposure_resp.dose:
            dose_desc = exposure_resp.dose
            if exposure_resp.dose_unit:
                dose_desc += f" {exposure_resp.dose_unit}"
            detail_parts.append(f"Dose: {dose_desc}")
        if exposure_resp.duration_weeks is not None:
            detail_parts.append(f"Duration: {exposure_resp.duration_weeks} weeks")
        if exposure_resp.frequency:
            detail_parts.append(f"Frequency: {exposure_resp.frequency}")

        if detail_parts:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag06_ann_{uuid.uuid4().hex[:12]}",
                    category="dose_response_evidence",
                    content="; ".join(detail_parts),
                    evidence_strength="moderate",
                    extraction_snippet=None,
                )
            )

        metadata = {
            "intervention_type": exposure_resp.intervention_type,
            "dose": exposure_resp.dose,
            "dose_unit": exposure_resp.dose_unit,
            "duration_weeks": exposure_resp.duration_weeks,
            "frequency": exposure_resp.frequency,
            "adherence_rate": exposure_resp.adherence_rate,
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )
