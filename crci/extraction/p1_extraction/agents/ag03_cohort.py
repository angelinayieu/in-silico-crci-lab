# VERIFIED: formulas — none (cohort extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG03 + AG03-EXT
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG03 CohortAgent)
      SYS_EXTRACTION_ADDENDUM Part 4 (AG03-EXT population cognitive norms)
Formulas: None
Reads: PaperMap.sections[Methods, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] (N, age, demographics + population cognitive scores)
        + Annotations (consumed by reconciliation.py, trust boundary, prior_compiler)
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
from crci.llm.response_schemas import CohortExtendedResponse, CohortResponse
from crci.shared.models.enums import AnnotationCategory
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class CohortAgent(BaseAgent):
    """AG03 -- Extract sample size, demographics, cancer type, treatment phase.

    STANDARD/DEEP only (mode gate enforced at orchestration level).

    Reads: PaperMap.sections[Methods, Results]
    Outputs: SpanLabel[] (N, age, demographics) + Annotations
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG03"

    @property
    def target_sections(self) -> list[str]:
        return ["methods", "results"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return CohortExtendedResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag03_cohort.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for cohort agent.

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
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert CohortExtendedResponse to AgentOutput.

        Creates SpanLabel entries for sample size, age, demographics,
        population cognitive scores (AG03-EXT), and annotations for
        cancer type and treatment phase.
        """
        cohort_resp: CohortExtendedResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []
        annotations: list[RawAnnotationEmission] = []

        # SpanLabel for total N
        if cohort_resp.total_n is not None:
            n_str = str(cohort_resp.total_n)
            n_start = paper_map.full_text.find(n_str)
            if n_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="SAMPLE_SIZE",
                        value=n_str,
                        numeric_value=float(cohort_resp.total_n),
                        char_start=n_start,
                        char_end=n_start + len(n_str),
                        confidence=0.9,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG03: total_n '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: total_n=%s, reason: text not located.",
                    n_str,
                    n_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="SAMPLE_SIZE",
                        value=n_str,
                        numeric_value=float(cohort_resp.total_n),
                        char_start=0,
                        char_end=0,
                        confidence=0.7,
                        source_section="methods",
                    )
                )

        # SpanLabel for mean age
        if cohort_resp.mean_age is not None:
            age_str = str(cohort_resp.mean_age)
            age_start = paper_map.full_text.find(age_str)
            if age_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="MEAN_AGE",
                        value=age_str,
                        numeric_value=cohort_resp.mean_age,
                        char_start=age_start,
                        char_end=age_start + len(age_str),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG03: mean_age '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: mean_age=%s, reason: text not located.",
                    age_str,
                    age_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="MEAN_AGE",
                        value=age_str,
                        numeric_value=cohort_resp.mean_age,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # SpanLabel for percent female
        if cohort_resp.percent_female is not None:
            pf_str = str(cohort_resp.percent_female)
            pf_start = paper_map.full_text.find(pf_str)
            if pf_start >= 0:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="PERCENT_FEMALE",
                        value=pf_str,
                        numeric_value=cohort_resp.percent_female,
                        char_start=pf_start,
                        char_end=pf_start + len(pf_str),
                        confidence=0.85,
                        source_section="methods",
                    )
                )
            else:
                logger.info(
                    "AG03: percent_female '%s' not found in canonical text, "
                    "creating SpanLabel with offset 0. "
                    "Entity: percent_female=%s, reason: text not located.",
                    pf_str,
                    pf_str,
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03_{uuid.uuid4().hex[:12]}",
                        label_type="PERCENT_FEMALE",
                        value=pf_str,
                        numeric_value=cohort_resp.percent_female,
                        char_start=0,
                        char_end=0,
                        confidence=0.65,
                        source_section="methods",
                    )
                )

        # Annotation for cancer type
        if cohort_resp.cancer_type is not None:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag03_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.POPULATION_SPECIFICITY,
                    content=f"Cancer type: {cohort_resp.cancer_type}",
                    evidence_strength="moderate",
                    extraction_snippet=cohort_resp.demographics_notes,
                )
            )

        # Annotation for treatment phase
        if cohort_resp.treatment_phase is not None:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag03_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.POPULATION_SPECIFICITY,
                    content=f"Treatment phase: {cohort_resp.treatment_phase}",
                    evidence_strength="moderate",
                    extraction_snippet=cohort_resp.demographics_notes,
                )
            )

        # Annotation for demographics notes
        if cohort_resp.demographics_notes:
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag03_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.POPULATION_SPECIFICITY,
                    content=cohort_resp.demographics_notes,
                    evidence_strength="weak",
                    extraction_snippet=cohort_resp.demographics_notes,
                )
            )

        # ─── AG03-EXT: Population cognitive scores ─────────────
        for cog in cohort_resp.cognitive_scores:
            grp_id = f"cog_{uuid.uuid4().hex[:8]}"

            # SpanLabel for instrument name
            if cog.instrument_name:
                inst_start = paper_map.full_text.find(cog.instrument_name)
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03ext_{uuid.uuid4().hex[:12]}",
                        label_type="POPULATION_COGNITIVE_INSTRUMENT",
                        value=cog.instrument_name,
                        numeric_value=None,
                        char_start=max(0, inst_start),
                        char_end=(
                            inst_start + len(cog.instrument_name)
                            if inst_start >= 0
                            else 0
                        ),
                        confidence=0.85 if inst_start >= 0 else 0.65,
                        source_section="results",
                    )
                )

            # SpanLabel for cognitive domain
            if cog.domain:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03ext_{uuid.uuid4().hex[:12]}",
                        label_type="POPULATION_COGNITIVE_DOMAIN",
                        value=cog.domain,
                        numeric_value=None,
                        char_start=0,
                        char_end=0,
                        confidence=0.80,
                        source_section="results",
                    )
                )

            # SpanLabel for mean
            if cog.mean is not None:
                mean_str = str(cog.mean)
                mean_start = paper_map.full_text.find(mean_str)
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03ext_{uuid.uuid4().hex[:12]}",
                        label_type="POPULATION_COGNITIVE_MEAN",
                        value=mean_str,
                        numeric_value=cog.mean,
                        char_start=max(0, mean_start),
                        char_end=(
                            mean_start + len(mean_str) if mean_start >= 0 else 0
                        ),
                        confidence=0.85 if mean_start >= 0 else 0.65,
                        source_section="results",
                    )
                )

            # SpanLabel for SD
            if cog.sd is not None:
                sd_str = str(cog.sd)
                sd_start = paper_map.full_text.find(sd_str)
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03ext_{uuid.uuid4().hex[:12]}",
                        label_type="POPULATION_COGNITIVE_SD",
                        value=sd_str,
                        numeric_value=cog.sd,
                        char_start=max(0, sd_start),
                        char_end=(
                            sd_start + len(sd_str) if sd_start >= 0 else 0
                        ),
                        confidence=0.85 if sd_start >= 0 else 0.65,
                        source_section="results",
                    )
                )

            # SpanLabel for percentile
            if cog.percentile is not None:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag03ext_{uuid.uuid4().hex[:12]}",
                        label_type="POPULATION_PERCENTILE",
                        value=str(cog.percentile),
                        numeric_value=cog.percentile,
                        char_start=0,
                        char_end=0,
                        confidence=0.70,
                        source_section="results",
                    )
                )

            # Annotation for population cognitive data
            pop_desc = cog.population_subgroup or cohort_resp.cancer_type or "all"
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag03ext_ann_{uuid.uuid4().hex[:12]}",
                    category=AnnotationCategory.POPULATION_SPECIFICITY,
                    content=(
                        f"Cognitive score: {cog.instrument_name} "
                        f"domain={cog.domain or 'overall'} "
                        f"mean={cog.mean} SD={cog.sd} N={cog.n} "
                        f"population={pop_desc}"
                    ),
                    evidence_strength="moderate",
                    extraction_snippet=None,
                )
            )

        metadata = {
            "total_n": cohort_resp.total_n,
            "cancer_type": cohort_resp.cancer_type,
            "treatment_phase": cohort_resp.treatment_phase,
            "mean_age": cohort_resp.mean_age,
            "percent_female": cohort_resp.percent_female,
            "demographics_notes": cohort_resp.demographics_notes,
            "n_cognitive_scores": len(cohort_resp.cognitive_scores),
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )
