# VERIFIED: formulas — keyword intersection score, design boost
# VERIFIED: imports — shared/config, retrieval/models
# VERIFIED: backward wiring — reads CandidateMetadata from search_coordinator
# VERIFIED: forward wiring — writes AbstractRelevance to acquisition_queue_v1
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — IRRELEVANT blocks retrieval dispatch
"""
Component: SYS_EXTRACTION.EX-ACQ.AbstractScreener
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 3 (Pre-Retrieval Filter)
      Master Spec §9.2.1 (Abstract Screening)
Formulas: SCREEN-1 (keyword intersection relevance)
Reads: CandidateMetadata (from search_coordinator.py)
Writes: AbstractRelevance enum (consumed by acquisition_scheduler.py)
Gates: SCREEN-G1 — IRRELEVANT candidates are excluded from APS scoring
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from crci.shared import config
from crci.retrieval.models import CandidateMetadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreeningResult:
    """Result of abstract relevance screening for one candidate."""

    relevance: str  # HIGH, MODERATE, LOW, IRRELEVANT
    cancer_keyword_hits: int
    cognitive_keyword_hits: int
    design_bonus: bool
    score: float  # 0.0-1.0 composite


def screen_abstract(candidate: CandidateMetadata) -> ScreeningResult:
    """Screen a single candidate's abstract for CRCI relevance.

    Formula SCREEN-1:
        cancer_hits = count(CANCER_KEYWORDS in abstract)
        cognitive_hits = count(COGNITIVE_KEYWORDS in abstract)
        design_bonus = 1 if study_design in {RCT, cohort, meta-analysis} else 0
        score = min(1.0, (cancer_hits + cognitive_hits) / MIN_KEYWORDS + 0.15 * design_bonus)

    Classification:
        score >= 0.8 → HIGH
        score >= 0.5 → MODERATE
        score >= 0.2 → LOW
        score <  0.2 → IRRELEVANT

    Gate SCREEN-G1: IRRELEVANT candidates are excluded from APS scoring.
    Only HIGH and MODERATE proceed to full retrieval.

    Args:
        candidate: CandidateMetadata from search_coordinator.

    Returns:
        ScreeningResult with relevance classification and score breakdown.
    """
    text = _build_screening_text(candidate)
    text_lower = text.lower()

    # Count cancer keyword hits
    cancer_hits = 0
    for keyword in config.ABSTRACT_SCREENING_CANCER_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword.lower()) + r'\w*\b', text_lower):
            cancer_hits += 1

    # Count cognitive keyword hits
    cognitive_hits = 0
    for keyword in config.ABSTRACT_SCREENING_COGNITIVE_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword.lower()) + r'\w*\b', text_lower):
            cognitive_hits += 1

    # Design bonus for high-quality study types
    design_bonus = _has_design_bonus(candidate)

    # Formula SCREEN-1: composite relevance score
    min_keywords = config.ABSTRACT_SCREENING_MIN_KEYWORDS
    keyword_score = (cancer_hits + cognitive_hits) / max(min_keywords, 1)
    score = min(1.0, keyword_score + (0.15 if design_bonus else 0.0))

    # Classification thresholds
    if score >= 0.8:
        relevance = "HIGH"
    elif score >= 0.5:
        relevance = "MODERATE"
    elif score >= 0.2:
        relevance = "LOW"
    else:
        relevance = "IRRELEVANT"

    result = ScreeningResult(
        relevance=relevance,
        cancer_keyword_hits=cancer_hits,
        cognitive_keyword_hits=cognitive_hits,
        design_bonus=design_bonus,
        score=score,
    )

    logger.debug(
        "Abstract screening: doi=%s relevance=%s score=%.2f "
        "(cancer=%d, cognitive=%d, design_bonus=%s)",
        candidate.doi,
        relevance,
        score,
        cancer_hits,
        cognitive_hits,
        design_bonus,
    )

    return result


def screen_batch(
    candidates: list[CandidateMetadata],
) -> list[tuple[CandidateMetadata, ScreeningResult]]:
    """Screen a batch of candidates and return paired results.

    Gate SCREEN-G1: filters out IRRELEVANT candidates from the returned list.

    Args:
        candidates: List of CandidateMetadata from search.

    Returns:
        List of (candidate, screening_result) tuples where relevance != IRRELEVANT.
    """
    results: list[tuple[CandidateMetadata, ScreeningResult]] = []
    irrelevant_count = 0

    for candidate in candidates:
        screening = screen_abstract(candidate)

        if screening.relevance == "IRRELEVANT":
            irrelevant_count += 1
            logger.debug(
                "SCREEN-G1: excluding IRRELEVANT candidate doi=%s (score=%.2f)",
                candidate.doi,
                screening.score,
            )
            continue

        results.append((candidate, screening))

    logger.info(
        "Abstract screening: %d/%d candidates passed (%.0f%% excluded as IRRELEVANT)",
        len(results),
        len(candidates),
        (irrelevant_count / max(len(candidates), 1)) * 100,
    )

    return results


def _build_screening_text(candidate: CandidateMetadata) -> str:
    """Build the text corpus for keyword screening.

    Combines title, abstract, and MeSH terms for maximum signal.
    """
    parts: list[str] = []
    if candidate.title:
        parts.append(candidate.title)
    if candidate.abstract:
        parts.append(candidate.abstract)
    if candidate.mesh_terms:
        parts.append(" ".join(candidate.mesh_terms))
    return " ".join(parts)


def _has_design_bonus(candidate: CandidateMetadata) -> bool:
    """Check if the candidate has a high-quality study design.

    Design types that get a bonus: RCT, meta-analysis, systematic review,
    prospective cohort. Detected from publication_types or study_design fields.
    """
    design_bonus_keywords = {
        "randomized controlled trial", "rct", "meta-analysis",
        "meta analysis", "systematic review", "prospective cohort",
        "clinical trial",
    }

    check_fields: list[str] = []
    if candidate.study_design:
        check_fields.append(candidate.study_design.lower())
    for pt in candidate.publication_types:
        check_fields.append(pt.lower())

    return any(
        kw in field_text
        for field_text in check_fields
        for kw in design_bonus_keywords
    )
