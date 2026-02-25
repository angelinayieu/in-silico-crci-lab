# VERIFIED: formulas — none (temporal extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput for reconciliation/trust boundary
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (STANDARD/DEEP only, mode gate enforced at orchestration level)
"""
Component: SYS_EXTRACTION.EX-P1.AG08 + AG08-EXT
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG08 TemporalAgent)
      SYS_EXTRACTION_ADDENDUM Part 4 (AG08-EXT effect x timepoint data)
Formulas: None
Reads: PaperMap.sections[Methods, Results] (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] + Annotations for measurement timepoints,
        follow-up duration, temporal patterns, effect at each timepoint,
        recovery curves (consumed by reconciliation.py, trust boundary,
        temporal_compiler)
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
from crci.llm.response_schemas import TemporalExtendedResponse
from crci.shared.models.intermediate_states import (
    PaperMap,
    RawAnnotationEmission,
    SpanLabel,
)

logger = logging.getLogger(__name__)


class TemporalAgent(BaseAgent):
    """AG08 -- Extract measurement timepoints, follow-up duration, temporal patterns.

    AG08-EXT: Also extracts effect x timepoint structured data and
    post-cessation recovery measurements.

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
        return TemporalExtendedResponse

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
        """Convert TemporalExtendedResponse to AgentOutput.

        Creates SpanLabel entries for each timepoint extracted,
        effect at each timepoint (AG08-EXT), and annotations for
        follow-up duration, temporal patterns, and onset/peak/decay.
        """
        temporal_resp: TemporalExtendedResponse = response  # type: ignore[assignment]

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

        # ─── AG08-EXT: Effect at each timepoint ────────────────
        for etp in temporal_resp.effect_timepoints:
            grp_id = f"etp_{uuid.uuid4().hex[:8]}"

            # SpanLabel for timepoint in weeks
            tp_str = str(etp.timepoint_weeks)
            tp_start = paper_map.full_text.find(tp_str)
            span_labels.append(
                SpanLabel(
                    span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                    label_type="TIMEPOINT_WEEKS",
                    value=tp_str,
                    numeric_value=etp.timepoint_weeks,
                    char_start=max(0, tp_start),
                    char_end=(
                        tp_start + len(tp_str) if tp_start >= 0 else 0
                    ),
                    confidence=0.85 if tp_start >= 0 else 0.65,
                    source_section="results",
                )
            )

            # SpanLabel for effect at this timepoint
            if etp.effect is not None:
                eff_str = str(etp.effect)
                eff_start = paper_map.full_text.find(eff_str)
                label = (
                    "RECOVERY_POSTCESSATION" if etp.is_recovery
                    else "EFFECT_AT_TIMEPOINT"
                )
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                        label_type=label,
                        value=eff_str,
                        numeric_value=etp.effect,
                        char_start=max(0, eff_start),
                        char_end=(
                            eff_start + len(eff_str) if eff_start >= 0 else 0
                        ),
                        confidence=0.85 if eff_start >= 0 else 0.65,
                        source_section="results",
                    )
                )

            # SpanLabel for SE at this timepoint
            if etp.se is not None:
                se_str = str(etp.se)
                se_start = paper_map.full_text.find(se_str)
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                        label_type="SE_AT_TIMEPOINT",
                        value=se_str,
                        numeric_value=etp.se,
                        char_start=max(0, se_start),
                        char_end=(
                            se_start + len(se_str) if se_start >= 0 else 0
                        ),
                        confidence=0.80 if se_start >= 0 else 0.60,
                        source_section="results",
                    )
                )

            # Recovery timepoint label
            if etp.is_recovery:
                span_labels.append(
                    SpanLabel(
                        span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                        label_type="RECOVERY_TIMEPOINT",
                        value=tp_str,
                        numeric_value=etp.timepoint_weeks,
                        char_start=0,
                        char_end=0,
                        confidence=0.80,
                        source_section="results",
                    )
                )

        # SpanLabels for onset/peak/decay observations
        if temporal_resp.onset_observed:
            span_labels.append(
                SpanLabel(
                    span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                    label_type="ONSET_OBSERVED",
                    value=temporal_resp.onset_observed,
                    numeric_value=None,
                    char_start=0,
                    char_end=0,
                    confidence=0.75,
                    source_section="results",
                )
            )

        if temporal_resp.peak_observed:
            span_labels.append(
                SpanLabel(
                    span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                    label_type="PEAK_OBSERVED",
                    value=temporal_resp.peak_observed,
                    numeric_value=None,
                    char_start=0,
                    char_end=0,
                    confidence=0.75,
                    source_section="results",
                )
            )

        if temporal_resp.decay_observed:
            span_labels.append(
                SpanLabel(
                    span_id=f"ag08ext_{uuid.uuid4().hex[:12]}",
                    label_type="DECAY_OBSERVED",
                    value=temporal_resp.decay_observed,
                    numeric_value=None,
                    char_start=0,
                    char_end=0,
                    confidence=0.75,
                    source_section="results",
                )
            )

        # Annotation for effect trajectory data
        if temporal_resp.effect_timepoints:
            n_recovery = sum(
                1 for etp in temporal_resp.effect_timepoints if etp.is_recovery
            )
            annotations.append(
                RawAnnotationEmission(
                    annotation_id=f"ag08ext_ann_{uuid.uuid4().hex[:12]}",
                    category="temporal_onset",
                    content=(
                        f"Effect trajectory: {len(temporal_resp.effect_timepoints)} "
                        f"timepoints ({n_recovery} recovery); "
                        f"onset={temporal_resp.onset_observed or 'not observed'}, "
                        f"peak={temporal_resp.peak_observed or 'not observed'}"
                    ),
                    evidence_strength="moderate",
                    extraction_snippet=None,
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
            "n_effect_timepoints": len(temporal_resp.effect_timepoints),
            "onset_observed": temporal_resp.onset_observed,
            "peak_observed": temporal_resp.peak_observed,
            "decay_observed": temporal_resp.decay_observed,
        }

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=annotations,
            metadata=metadata,
            completion_status="success",
        )
