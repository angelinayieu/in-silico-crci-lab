# VERIFIED: formulas — none (design classification, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (ALWAYS runs agent)
"""
Component: SYS_EXTRACTION.EX-P1.AG02
Spec: SYS_EXTRACTION_COMPLETE.md lines 455-459 (AG2 DesignAgent)
      SYS_EXTRACTION_COMPLETE.md lines 413 (AG2 subsystem inventory)
Formulas: None
Reads: PaperMap.sections[methods, abstract] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + design annotations (consumed by reconciliation.py)
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
from crci.llm.response_schemas import DesignResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)
from crci.shared.models.enums import AnnotationCategory

logger = logging.getLogger(__name__)


class DesignAgent(BaseAgent):
    """AG02 -- Classify study design, randomization, blinding, control type.

    ALWAYS runs (all extraction modes: SHALLOW, STANDARD, DEEP).

    Reads: PaperMap.sections[methods, abstract]
    Outputs: SpanLabel[] (design labels) + RawAnnotation[] (limitation_design)
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG02"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "abstract"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return DesignResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag02_design.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for design classification agent.

        Loads the prompt template and fills in the focused text.
        """
        template = self._load_prompt_template()

        # Include basic study object info if available from CR-d
        study_design_hint = paper_map.study_design or "(unknown)"
        n_total_hint = str(paper_map.n_total) if paper_map.n_total else "(unknown)"
        arms_hint = ", ".join(paper_map.arms) if paper_map.arms else "(unknown)"

        return template.format(
            focused_text=focused_text,
            paper_id=paper_map.paper_id,
            study_design_hint=study_design_hint,
            n_total_hint=n_total_hint,
            arms_hint=arms_hint,
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert DesignResponse to AgentOutput.

        Creates SpanLabel entries for design classification fields
        and annotations for design limitations.
        """
        design_resp: DesignResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        # Create SpanLabel for study design
        if design_resp.study_design:
            design_start = self._find_text_offset(
                paper_map.full_text, design_resp.study_design
            )
            span_labels.append(
                SpanLabel(
                    span_id=f"ag02_{uuid.uuid4().hex[:12]}",
                    label_type="STUDY_DESIGN",
                    value=design_resp.study_design,
                    numeric_value=None,
                    char_start=design_start,
                    char_end=design_start + len(design_resp.study_design)
                    if design_start > 0
                    else 0,
                    confidence=design_resp.confidence,
                    source_section="methods",
                )
            )

        # Create SpanLabel for randomization
        if design_resp.randomization:
            rand_start = self._find_text_offset(
                paper_map.full_text, design_resp.randomization
            )
            span_labels.append(
                SpanLabel(
                    span_id=f"ag02_{uuid.uuid4().hex[:12]}",
                    label_type="RANDOMIZATION",
                    value=design_resp.randomization,
                    numeric_value=None,
                    char_start=rand_start,
                    char_end=rand_start + len(design_resp.randomization)
                    if rand_start > 0
                    else 0,
                    confidence=design_resp.confidence,
                    source_section="methods",
                )
            )

        # Create SpanLabel for blinding
        if design_resp.blinding:
            blind_start = self._find_text_offset(
                paper_map.full_text, design_resp.blinding
            )
            span_labels.append(
                SpanLabel(
                    span_id=f"ag02_{uuid.uuid4().hex[:12]}",
                    label_type="BLINDING",
                    value=design_resp.blinding,
                    numeric_value=None,
                    char_start=blind_start,
                    char_end=blind_start + len(design_resp.blinding)
                    if blind_start > 0
                    else 0,
                    confidence=design_resp.confidence,
                    source_section="methods",
                )
            )

        # Create SpanLabel for control type
        if design_resp.control_type:
            ctrl_start = self._find_text_offset(
                paper_map.full_text, design_resp.control_type
            )
            span_labels.append(
                SpanLabel(
                    span_id=f"ag02_{uuid.uuid4().hex[:12]}",
                    label_type="CONTROL_TYPE",
                    value=design_resp.control_type,
                    numeric_value=None,
                    char_start=ctrl_start,
                    char_end=ctrl_start + len(design_resp.control_type)
                    if ctrl_start > 0
                    else 0,
                    confidence=design_resp.confidence,
                    source_section="methods",
                )
            )

        # Create SpanLabels for study arms
        for arm in design_resp.arms:
            arm_start = self._find_text_offset(paper_map.full_text, arm)
            span_labels.append(
                SpanLabel(
                    span_id=f"ag02_{uuid.uuid4().hex[:12]}",
                    label_type="STUDY_ARM",
                    value=arm,
                    numeric_value=None,
                    char_start=arm_start,
                    char_end=arm_start + len(arm) if arm_start > 0 else 0,
                    confidence=design_resp.confidence,
                    source_section="methods",
                )
            )

        # Emit design limitation annotation if applicable
        # Detect common design limitations from the response
        design_type = design_resp.study_design.lower() if design_resp.study_design else ""
        if design_type in (
            "cross_sectional",
            "cross-sectional",
            "observational",
            "retrospective",
        ):
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag02_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.SELECTION_BIAS,
                    content=(
                        f"Study uses {design_resp.study_design} design, "
                        f"which limits causal inference. "
                        f"Blinding: {design_resp.blinding or 'not reported'}. "
                        f"Control: {design_resp.control_type or 'not reported'}."
                    ),
                    evidence_strength="moderate",
                    extraction_snippet=f"Design: {design_resp.study_design}",
                )
            )

        if design_resp.blinding and "open" in design_resp.blinding.lower():
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag02_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.DETECTION_BIAS,
                    content=(
                        f"Open-label design ({design_resp.blinding}) "
                        f"may introduce detection bias."
                    ),
                    evidence_strength="moderate",
                    extraction_snippet=f"Blinding: {design_resp.blinding}",
                )
            )

        # Build metadata dict
        metadata = {
            "study_design": design_resp.study_design,
            "randomization": design_resp.randomization,
            "blinding": design_resp.blinding,
            "control_type": design_resp.control_type,
            "arms": design_resp.arms,
            "confidence": design_resp.confidence,
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )

    @staticmethod
    def _find_text_offset(full_text: str, search_text: str) -> int:
        """Find the first occurrence of search_text in full_text.

        Returns the character offset, or 0 if not found (with logging).
        """
        idx = full_text.find(search_text)
        if idx < 0:
            # Try case-insensitive search
            idx = full_text.lower().find(search_text.lower())
        if idx < 0:
            logger.info(
                "AG02: text '%s' not found in canonical text, "
                "using offset 0 as fallback. "
                "Entity: search_text=%r, reason: text not located.",
                search_text[:50],
                search_text[:50],
            )
            return 0
        return idx
