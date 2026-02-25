# VERIFIED: no formulas (decision-tree routing)
# VERIFIED: imports — logging + shared.models.enums + shared.models.intermediate_states
# VERIFIED: backward wiring — reads PaperSubtype from paper_type_classifier.py, ScreenedPaper from relevance_screening.py
# VERIFIED: forward wiring — writes TriageResult for extraction/pipeline.py -> EX-P1
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no formula-specific gates (routing logic only)
"""
Component: SYS_EXTRACTION.EX-P0.P0-S3/S4
Spec: SYS_EXTRACTION_COMPLETE.md lines 256-277
Formulas: None (decision tree routing)
Reads: PaperSubtype (from paper_type_classifier.py),
       ScreenedPaper dict (from relevance_screening.py)
Writes: TriageResult (consumed by extraction/pipeline.py -> EX-P1)
Gates: None (mode_selection routes; gating already done by P0-G2)
"""
from __future__ import annotations

import logging
from typing import Any

from crci.shared.config import P0_MODE_SELECTION_REJECT_THRESHOLD
from crci.shared.models.enums import (
    ExtractionMode,
    PaperSubtype,
    TriageDecision,
)
from crci.shared.models.intermediate_states import TriageResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  SUBTYPE -> EXTRACTION MODE MAPPING
#  Spec lines 260-270:
#    RCT + cancer-specific + cognitive primary -> DEEP
#    Cohort/observational + cognitive outcome -> STANDARD
#    Case report / animal / biomarker-only -> SHALLOW
#    Unknown/ambiguous -> STANDARD (safe default)
# ═══════════════════════════════════════════════════════════════

_SUBTYPE_TO_MODE: dict[PaperSubtype, ExtractionMode] = {
    # DEEP: RCTs with direct cognitive intervention relevance
    PaperSubtype.RCT_EXERCISE: ExtractionMode.DEEP,
    PaperSubtype.RCT_COGNITIVE: ExtractionMode.DEEP,
    PaperSubtype.RCT_PHARMACOLOGICAL: ExtractionMode.DEEP,
    PaperSubtype.RCT_MULTIMODAL: ExtractionMode.DEEP,

    # DEEP: Meta-analyses (high evidence value, need thorough extraction)
    PaperSubtype.META_ANALYSIS: ExtractionMode.DEEP,

    # DEEP: Dose-response and longitudinal follow-up
    # (SYS_EXTRACTION_ADDENDUM Part 2: need thorough multi-dose/multi-timepoint extraction)
    PaperSubtype.DOSE_RESPONSE_STUDY: ExtractionMode.DEEP,
    PaperSubtype.LONGITUDINAL_FOLLOWUP: ExtractionMode.DEEP,

    # STANDARD: Systematic reviews and observational designs with cognitive outcomes
    PaperSubtype.SYSTEMATIC_REVIEW: ExtractionMode.STANDARD,
    PaperSubtype.LONGITUDINAL_COHORT: ExtractionMode.STANDARD,
    PaperSubtype.CROSS_SECTIONAL: ExtractionMode.STANDARD,
    PaperSubtype.INTENSIVE_LONGITUDINAL: ExtractionMode.STANDARD,
    PaperSubtype.MECHANISTIC_HUMAN: ExtractionMode.STANDARD,
    PaperSubtype.IMAGING_STRUCTURAL: ExtractionMode.STANDARD,
    PaperSubtype.IMAGING_FUNCTIONAL: ExtractionMode.STANDARD,
    PaperSubtype.DOSE_RESPONSE: ExtractionMode.STANDARD,

    # STANDARD: Psychometric validation and normative cohorts
    # (SYS_EXTRACTION_ADDENDUM Part 2: activate AG11 / AG03-EXT respectively)
    PaperSubtype.PSYCHOMETRIC_VALIDATION: ExtractionMode.STANDARD,
    PaperSubtype.NORMATIVE_COHORT: ExtractionMode.STANDARD,

    # SHALLOW: Lower evidence value or less extractable content
    PaperSubtype.MECHANISTIC_ANIMAL: ExtractionMode.SHALLOW,
    PaperSubtype.BIOMARKER_DISCOVERY: ExtractionMode.SHALLOW,
    PaperSubtype.SAFETY_REPORT: ExtractionMode.SHALLOW,
    PaperSubtype.CASE_REPORT: ExtractionMode.SHALLOW,
    PaperSubtype.GUIDELINE: ExtractionMode.SHALLOW,
    PaperSubtype.REVIEW_NARRATIVE: ExtractionMode.SHALLOW,
    PaperSubtype.QUALITATIVE: ExtractionMode.SHALLOW,

    # SHALLOW or REJECT candidates (minimal extractable evidence)
    PaperSubtype.EDITORIAL: ExtractionMode.SHALLOW,
    PaperSubtype.PROTOCOL: ExtractionMode.SHALLOW,

    # Unknown/other -> STANDARD (safe default per spec)
    PaperSubtype.OTHER: ExtractionMode.STANDARD,
}


# Subtypes that should be considered for REJECT instead of extraction
# (editorials and protocols have very little extractable evidence)
_REJECT_CANDIDATES: set[PaperSubtype] = {
    PaperSubtype.EDITORIAL,
    PaperSubtype.PROTOCOL,
}


def select_extraction_mode(
    paper_id: str,
    paper_subtype: PaperSubtype,
    screened_paper: dict[str, Any],
) -> TriageResult:
    """Select SHALLOW/STANDARD/DEEP extraction mode based on paper type.

    P0-S3: Execution Mode Selection.
    P0-S4: Route Decision.

    Decision tree (from spec lines 260-270):
        RCT + cancer-specific + cognitive primary -> DEEP
        Cohort/observational + cognitive outcome -> STANDARD
        Case report / animal / biomarker-only -> SHALLOW
        Unknown/ambiguous -> STANDARD (safe default)

    Args:
        paper_id: Unique identifier for the paper.
        paper_subtype: Classified paper subtype from paper_type_classifier.
        screened_paper: Output from relevance_screening.screen_relevance().

    Returns:
        TriageResult with decision, extraction_mode, and all metadata.
    """
    relevance_score: float = screened_paper.get("relevance_score", 0.0)
    decision: TriageDecision = screened_paper.get("decision", TriageDecision.REVIEW)
    rejection_reason: str | None = screened_paper.get("rejection_reason")

    # ─── Determine extraction mode from subtype ──────────────
    extraction_mode = _SUBTYPE_TO_MODE.get(paper_subtype, ExtractionMode.STANDARD)

    # Log default usage when subtype is not in the explicit mapping
    if paper_subtype not in _SUBTYPE_TO_MODE:
        logger.info(
            "Mode selection: paper_subtype=%s not in explicit mapping, "
            "defaulting to STANDARD (safe default per spec)",
            paper_subtype.value,
        )

    # ─── REJECT candidate check ──────────────────────────────
    # Editorials and protocols with low relevance should be rejected
    if paper_subtype in _REJECT_CANDIDATES and relevance_score < P0_MODE_SELECTION_REJECT_THRESHOLD:
        decision = TriageDecision.REJECT
        rejection_reason = (
            f"Paper subtype '{paper_subtype.value}' has minimal extractable "
            f"evidence and relevance score {relevance_score:.3f} < {P0_MODE_SELECTION_REJECT_THRESHOLD}"
        )
        extraction_mode = None
        logger.info(
            "Mode selection: REJECT for paper_subtype=%s with relevance=%.3f",
            paper_subtype.value,
            relevance_score,
        )

    # ─── For REVIEW decisions, keep extraction mode but flag ──
    if decision == TriageDecision.REVIEW:
        logger.info(
            "Mode selection: paper %s routed to REVIEW with mode=%s "
            "(queued for human review per P0-S4)",
            paper_id,
            extraction_mode.value if extraction_mode else "None",
        )

    # ─── Build TriageResult ───────────────────────────────────
    result = TriageResult(
        paper_id=paper_id,
        decision=decision,
        relevance_score=relevance_score,
        extraction_mode=extraction_mode,
        paper_subtype=paper_subtype.value,
        rejection_reason=rejection_reason,
    )

    logger.info(
        "Triage complete: paper_id=%s decision=%s mode=%s subtype=%s score=%.3f",
        paper_id,
        result.decision.value,
        result.extraction_mode.value if result.extraction_mode else "None",
        result.paper_subtype,
        result.relevance_score,
    )

    return result
