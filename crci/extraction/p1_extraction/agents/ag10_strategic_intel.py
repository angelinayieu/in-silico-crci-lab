# VERIFIED: formulas — none (annotation extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas, enums)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput (annotations ONLY) for trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG10
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG10 StrategicIntelAgent)
      SYS_EXTRACTION_COMPLETE.md lines 506-513 (7 primary annotation categories)
Formulas: None
Reads: PaperMap.sections[Discussion, Limitations, Conclusion] (from canonical_reader.py)
Writes: AgentOutput with RawAnnotationEmission[] ONLY (no SpanLabels)
        (consumed by annotation trust boundary)
Gates: None (STANDARD/DEEP mode gate enforced at orchestration level)

7 primary annotation categories (from spec lines 506-513):
  1. limitation_unmeasured_confounder
  2. research_gap
  3. mechanism_hypothesis
  4. null_finding_context
  5. generalizability_concern
  6. clinical_significance
  7. effect_modification
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
from crci.llm.response_schemas import AnnotationResponse
from crci.shared.models.enums import AnnotationCategory
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
)

logger = logging.getLogger(__name__)

# The 7 primary categories AG10 targets, per spec lines 506-513
_PRIMARY_CATEGORIES: set[str] = {
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
    AnnotationCategory.RESEARCH_GAP,
    AnnotationCategory.MECHANISM_HYPOTHESIS,
    AnnotationCategory.NULL_FINDING_CONTEXT,
    AnnotationCategory.GENERALIZABILITY_CONCERN,
    AnnotationCategory.CLINICAL_SIGNIFICANCE,
    AnnotationCategory.EFFECT_MODIFICATION,
}

# All valid AnnotationCategory values for fallback matching
_ALL_CATEGORIES: set[str] = {cat.value for cat in AnnotationCategory}


class StrategicIntelAgent(BaseAgent):
    """AG10 -- Extract strategic intelligence from Discussion/Limitations.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Produces annotations ONLY (no SpanLabels). This agent extracts
    higher-level scientific insights that inform downstream model
    interpretation and uncertainty estimation.

    Reads: PaperMap.sections[Discussion, Limitations, Conclusion]
    Outputs: RawAnnotationEmission[] ONLY
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG10"

    @property
    def target_sections(self) -> list[str]:
        return ["discussion", "limitations", "conclusion"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return AnnotationResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag10_strategic_intel.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for strategic intelligence agent.

        Loads the prompt template and fills in the focused text,
        paper_id, and title.
        """
        template = self._load_prompt_template()
        return template.format(
            focused_text=focused_text,
            paper_id=paper_map.paper_id,
            title=paper_map.title or "(unknown)",
            study_design=paper_map.study_design or "(unknown)",
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert AnnotationResponse to AgentOutput.

        AG10 produces annotations ONLY -- no SpanLabels.
        Each annotation item is validated against the AnnotationCategory enum,
        with priority given to the 7 primary categories.
        """
        ann_resp: AnnotationResponse = response  # type: ignore[assignment]

        annotations: list[RawAnnotationEmission] = []

        for item in ann_resp.annotations:
            # Validate and normalize category
            category = self._resolve_category(item.category)
            if category is None:
                logger.warning(
                    "AG10: skipping annotation with unrecognized category '%s' "
                    "for paper_id=%s. Content: '%s'",
                    item.category,
                    paper_map.paper_id,
                    item.content[:100],
                )
                continue

            # Validate evidence strength
            evidence_strength = item.evidence_strength
            if evidence_strength not in ("strong", "moderate", "weak", None):
                logger.info(
                    "AG10: normalizing evidence_strength '%s' to 'moderate' "
                    "for paper_id=%s, annotation category=%s. "
                    "Entity: evidence_strength=%s, "
                    "reason: not in allowed set {strong, moderate, weak}.",
                    evidence_strength,
                    paper_map.paper_id,
                    category,
                    evidence_strength,
                )
                evidence_strength = "moderate"

            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag10_ann_{uuid.uuid4().hex[:12]}",
                    category=category,
                    content=item.content,
                    evidence_strength=evidence_strength,
                    extraction_snippet=item.extraction_snippet,
                    source_span_id=None,  # AG10 does not produce SpanLabels
                )
            )

        # Count how many annotations fall in the 7 primary categories
        primary_count = sum(
            1 for a in annotations if a.category in _PRIMARY_CATEGORIES
        )
        secondary_count = len(annotations) - primary_count

        metadata = {
            "n_annotations": len(annotations),
            "n_primary_categories": primary_count,
            "n_secondary_categories": secondary_count,
            "categories_found": list(set(a.category for a in annotations)),
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=[],  # AG10 produces NO SpanLabels
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )

    @staticmethod
    def _resolve_category(raw_category: str) -> str | None:
        """Resolve a raw category string to a valid AnnotationCategory value.

        Attempts exact match first, then case-insensitive match,
        then common alias resolution.

        Returns:
            The valid AnnotationCategory value string, or None if unresolvable.
        """
        # Exact match
        if raw_category in _ALL_CATEGORIES:
            return raw_category

        # Case-insensitive match
        lower = raw_category.lower().strip()
        for cat in _ALL_CATEGORIES:
            if cat.lower() == lower:
                return cat

        # Common alias resolution
        alias_map: dict[str, str] = {
            "unmeasured_confounder": AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
            "confounder": AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
            "confounders": AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
            "limitation_confounder": AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
            "gap": AnnotationCategory.RESEARCH_GAP,
            "research_gaps": AnnotationCategory.RESEARCH_GAP,
            "future_research": AnnotationCategory.RESEARCH_GAP,
            "mechanism": AnnotationCategory.MECHANISM_HYPOTHESIS,
            "mechanistic": AnnotationCategory.MECHANISM_HYPOTHESIS,
            "mechanistic_hypothesis": AnnotationCategory.MECHANISM_HYPOTHESIS,
            "null_finding": AnnotationCategory.NULL_FINDING_CONTEXT,
            "null_result": AnnotationCategory.NULL_FINDING_CONTEXT,
            "negative_finding": AnnotationCategory.NULL_FINDING_CONTEXT,
            "generalizability": AnnotationCategory.GENERALIZABILITY_CONCERN,
            "external_validity": AnnotationCategory.GENERALIZABILITY_CONCERN,
            "clinical_relevance": AnnotationCategory.CLINICAL_SIGNIFICANCE,
            "clinical_importance": AnnotationCategory.CLINICAL_SIGNIFICANCE,
            "clinical": AnnotationCategory.CLINICAL_SIGNIFICANCE,
            "effect_modifier": AnnotationCategory.EFFECT_MODIFICATION,
            "moderator": AnnotationCategory.EFFECT_MODIFICATION,
            "subgroup": AnnotationCategory.EFFECT_MODIFICATION,
            "subgroup_effect": AnnotationCategory.EFFECT_MODIFICATION,
            "adherence": AnnotationCategory.ADHERENCE_DATA,
            "adverse_events": AnnotationCategory.ADVERSE_EVENT,
            "safety": AnnotationCategory.ADVERSE_EVENT,
            "temporal": AnnotationCategory.TEMPORAL_ONSET,
            "dose_response": AnnotationCategory.DOSE_RESPONSE_EVIDENCE,
            "measurement": AnnotationCategory.MEASUREMENT_LIMITATION,
            "measurement_error": AnnotationCategory.MEASUREMENT_LIMITATION,
            "population": AnnotationCategory.POPULATION_SPECIFICITY,
            "sample": AnnotationCategory.POPULATION_SPECIFICITY,
            "biological": AnnotationCategory.BIOLOGICAL_PLAUSIBILITY,
            "plausibility": AnnotationCategory.BIOLOGICAL_PLAUSIBILITY,
            "replication": AnnotationCategory.REPLICATION_STATUS,
            "replicated": AnnotationCategory.REPLICATION_STATUS,
            "selection": AnnotationCategory.SELECTION_BIAS,
            "attrition": AnnotationCategory.ATTRITION_BIAS,
            "dropout": AnnotationCategory.ATTRITION_BIAS,
            "detection": AnnotationCategory.DETECTION_BIAS,
            "reporting": AnnotationCategory.REPORTING_BIAS,
            "theory": AnnotationCategory.THEORY_SUPPORT,
            "cross_validation": AnnotationCategory.CROSS_VALIDATION,
        }

        resolved = alias_map.get(lower)
        if resolved is not None:
            return resolved

        # Try partial match on underscore-separated tokens
        for alias, cat_val in alias_map.items():
            if alias in lower or lower in alias:
                return cat_val

        return None
