# VERIFIED: imports — pydantic + shared.models.enums + shared.models.intermediate_states
# VERIFIED: downstream — used by agents and llm/client.py for validation
"""
Component: SYS_EXTRACTION.LLM_RESPONSE_SCHEMAS
Spec: SYS_EXTRACTION_COMPLETE.md lines 292-420 (agent architecture)
Formulas: None
Reads: Nothing (schema definitions)
Writes: Nothing (instantiated by LLM client)
Gates: None
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from crci.shared.models.enums import (
    AnnotationCategory,
    ExtractionMode,
    PaperSubtype,
    StudyDesign,
)


# ═══════════════════════════════════════════════════════════════
#  P0: Triage Responses
# ═══════════════════════════════════════════════════════════════


class PaperTypeClassification(BaseModel):
    """Response from paper type classifier (P0-PTC)."""

    paper_subtype: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


# ═══════════════════════════════════════════════════════════════
#  P1: Extraction Agent Responses
# ═══════════════════════════════════════════════════════════════


class MetadataResponse(BaseModel):
    """AG1 response: paper metadata."""

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    journal: str | None = None
    year: int | None = None
    funding_sources: list[str] = Field(default_factory=list)


class DesignResponse(BaseModel):
    """AG2 response: study design classification."""

    study_design: str
    randomization: str | None = None
    blinding: str | None = None
    control_type: str | None = None
    arms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class CohortResponse(BaseModel):
    """AG3 response: cohort details."""

    total_n: int | None = None
    cancer_type: str | None = None
    treatment_phase: str | None = None
    mean_age: float | None = None
    percent_female: float | None = None
    demographics_notes: str | None = None


class OutcomeResponse(BaseModel):
    """AG4 response: outcome measures."""

    class OutcomeMeasure(BaseModel):
        instrument_name: str
        instrument_id: str | None = None
        domain: str | None = None
        timepoints: list[str] = Field(default_factory=list)

    outcomes: list[OutcomeMeasure] = Field(default_factory=list)


class SpanLabelResponse(BaseModel):
    """AG5 response: statistical span labels."""

    class ExtractedSpan(BaseModel):
        span_text: str
        char_start: int
        char_end: int
        label_type: str
        confidence: float = Field(ge=0.0, le=1.0, default=0.5)
        grouping_id: str | None = None
        context: str | None = None
        arm_assignment: str | None = None  # Study arm (e.g., "testosterone", "placebo")

    spans: list[ExtractedSpan] = Field(default_factory=list)


class ExposureResponse(BaseModel):
    """AG6 response: exposure/intervention details."""

    intervention_type: str | None = None
    dose: str | None = None
    dose_unit: str | None = None
    duration_weeks: float | None = None
    frequency: str | None = None
    adherence_rate: float | None = None


class MediatorResponse(BaseModel):
    """AG7 response: mediator/biomarker pathways."""

    class MediatorClaim(BaseModel):
        mediator_name: str
        pathway: str | None = None
        direction: str | None = None
        evidence_strength: str | None = None

    mediators: list[MediatorClaim] = Field(default_factory=list)


class TemporalResponse(BaseModel):
    """AG8 response: temporal patterns."""

    class TimepointExtraction(BaseModel):
        timepoint_label: str
        days_from_baseline: float | None = None
        measurement_type: str | None = None

    timepoints: list[TimepointExtraction] = Field(default_factory=list)
    follow_up_weeks: float | None = None
    temporal_pattern: str | None = None


class AnnotationResponse(BaseModel):
    """AG10 response: strategic annotations."""

    class AnnotationItem(BaseModel):
        category: str
        content: str
        evidence_strength: str | None = None
        extraction_snippet: str | None = None
        target_entity_type: str | None = None
        target_entity_id: str | None = None

    annotations: list[AnnotationItem] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  AG11: Instrument Validation Response
#  Spec: SYS_EXTRACTION_ADDENDUM Part 3 (AG11 InstrumentValidationAgent)
# ═══════════════════════════════════════════════════════════════


class InstrumentValidationResponse(BaseModel):
    """AG11 response: psychometric property extraction.

    Uses the same SpanLabel-style structure as AG05 (SpanLabelResponse)
    but with 12 new label types specific to instrument validation.
    Groups spans by {instrument_name × subscale × population}.
    """

    class ExtractedSpan(BaseModel):
        span_text: str
        char_start: int
        char_end: int
        label_type: str
        confidence: float = Field(ge=0.0, le=1.0, default=0.5)
        grouping_id: str | None = None
        context: str | None = None

    spans: list[ExtractedSpan] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  Agent Extension Response Schemas
#  Spec: SYS_EXTRACTION_ADDENDUM Part 4 (AG03/05/06/08-EXT)
# ═══════════════════════════════════════════════════════════════


class CohortExtendedResponse(BaseModel):
    """AG03-EXT response: cohort + population cognitive norms.

    Extends CohortResponse with per-domain cognitive scores.
    """

    total_n: int | None = None
    cancer_type: str | None = None
    treatment_phase: str | None = None
    mean_age: float | None = None
    percent_female: float | None = None
    demographics_notes: str | None = None

    class CognitiveScore(BaseModel):
        instrument_name: str
        domain: str | None = None
        population_subgroup: str | None = None
        mean: float | None = None
        sd: float | None = None
        n: int | None = None
        percentile: float | None = None

    cognitive_scores: list[CognitiveScore] = Field(default_factory=list)


class ExposureExtendedResponse(BaseModel):
    """AG06-EXT response: exposure + dose-response structured data.

    Extends ExposureResponse with dose × effect pairs.
    """

    intervention_type: str | None = None
    dose: str | None = None
    dose_unit: str | None = None
    duration_weeks: float | None = None
    frequency: str | None = None
    adherence_rate: float | None = None

    class DoseEffectPair(BaseModel):
        dose_level: str
        dose_unit: str | None = None
        effect: float | None = None
        effect_se: float | None = None
        context: str | None = None

    dose_effect_pairs: list[DoseEffectPair] = Field(default_factory=list)
    dose_response_shape: str | None = None
    effective_dose_range: str | None = None
    maximum_tolerated_dose: str | None = None


class TemporalExtendedResponse(BaseModel):
    """AG08-EXT response: temporal + effect × timepoint structured data.

    Extends TemporalResponse with effect at each timepoint.
    """

    class TimepointExtraction(BaseModel):
        timepoint_label: str
        days_from_baseline: float | None = None
        measurement_type: str | None = None

    class EffectAtTimepoint(BaseModel):
        timepoint_weeks: float
        effect: float | None = None
        se: float | None = None
        is_recovery: bool = False
        context: str | None = None

    timepoints: list[TimepointExtraction] = Field(default_factory=list)
    follow_up_weeks: float | None = None
    temporal_pattern: str | None = None
    effect_timepoints: list[EffectAtTimepoint] = Field(default_factory=list)
    onset_observed: str | None = None
    peak_observed: str | None = None
    decay_observed: str | None = None


class StatsLabelExtendedResponse(BaseModel):
    """AG05-EXT response: stats labels + subgroup interaction effects.

    Extends SpanLabelResponse with structured subgroup data.
    """

    class ExtractedSpan(BaseModel):
        span_text: str
        char_start: int
        char_end: int
        label_type: str
        confidence: float = Field(ge=0.0, le=1.0, default=0.5)
        grouping_id: str | None = None
        context: str | None = None

    class SubgroupInteraction(BaseModel):
        subgroup_variable: str
        subgroup_value: str
        interaction_effect: float | None = None
        interaction_se: float | None = None
        interaction_p: float | None = None
        subgroup_effect: float | None = None
        subgroup_n: int | None = None

    spans: list[ExtractedSpan] = Field(default_factory=list)
    subgroup_interactions: list[SubgroupInteraction] = Field(default_factory=list)
