# VERIFIED: formulas — none (mediator extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG07
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG07 MediatorAgent)
Formulas: None
Reads: PaperMap.sections[Introduction, Discussion, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + Annotations for mediators,
        biomarker pathways, mechanistic claims
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
from crci.llm.response_schemas import MediatorResponse
from crci.shared.models.enums import AnnotationCategory
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class MediatorAgent(BaseAgent):
    """AG07 -- Extract mediators, biomarker pathways, mechanistic claims.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Reads: PaperMap.sections[Introduction, Discussion, Results]
    Outputs: SpanLabel[] + Annotations
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG07"

    @property
    def target_sections(self) -> list[str]:
        return ["introduction", "discussion", "results"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return MediatorResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag07_mediator.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for mediator agent.

        Loads the prompt template and fills in the focused text,
        paper_id, and table text.
        """
        template = self._load_prompt_template()
        table_text = self._get_table_text(paper_map)
        return template.format(
            focused_text=focused_text,
            paper_id=paper_map.paper_id,
            table_text=table_text if table_text else "(no tables detected)",
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert MediatorResponse to AgentOutput.

        Creates SpanLabel entries for each mediator name found in the text,
        and annotations for pathway and mechanistic claim details.
        """
        mediator_resp: MediatorResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        for claim in mediator_resp.mediators:
            mediator_name = claim.mediator_name

            # Try to locate mediator name in paper text
            med_start = paper_map.full_text.find(mediator_name)
            if med_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag07_{uuid.uuid4().hex[:12]}",
                        label_type="MEDIATOR",
                        value=mediator_name,
                        numeric_value=None,
                        char_start=med_start,
                        char_end=med_start + len(mediator_name),
                        confidence=0.8,
                        source_section="discussion",
                    )
                )
            else:
                logger.info(
                    "AG07: mediator '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: mediator=%s, reason: text not located.",
                    mediator_name,
                    mediator_name,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag07_{uuid.uuid4().hex[:12]}",
                        label_type="MEDIATOR",
                        value=mediator_name,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.6,
                        source_section="discussion",
                    )
                )

            # Annotation for mechanism hypothesis
            content_parts = [f"Mediator: {mediator_name}"]
            if claim.pathway:
                content_parts.append(f"Pathway: {claim.pathway}")
            if claim.direction:
                content_parts.append(f"Direction: {claim.direction}")

            # Determine annotation category based on content
            category = AnnotationCategory.MECHANISM_HYPOTHESIS
            if claim.pathway and any(
                kw in claim.pathway.lower()
                for kw in ["biomarker", "cytokine", "inflammatory", "cortisol"]
            ):
                category = AnnotationCategory.BIOLOGICAL_PLAUSIBILITY

            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag07_ann_{uuid.uuid4().hex[:12]}",
                    category=category,
                    content="; ".join(content_parts),
                    evidence_strength=claim.evidence_strength or "weak",
                    extraction_snippet=mediator_name,
                )
            )

        metadata = {
            "n_mediators": len(mediator_resp.mediators),
            "mediators": [
                {
                    "name": m.mediator_name,
                    "pathway": m.pathway,
                    "direction": m.direction,
                    "evidence_strength": m.evidence_strength,
                }
                for m in mediator_resp.mediators
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
