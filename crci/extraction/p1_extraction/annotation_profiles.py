# VERIFIED: profiles match PIMP §5.1-5.3 paper-type expectations
# VERIFIED: imports — enums (AnnotationCategory, PaperSubtype)
# VERIFIED: backward wiring — called after agents produce annotations
# VERIFIED: forward wiring — returns warnings for logging (no hard gate)
"""
Component: SYS_EXTRACTION.EX-P1.PROFILES
Spec: PAPER_INTELLIGENCE_MAXIMIZATION.md §5.1-5.3 (Paper-Type Profiles)
Purpose: Define expected annotation yield per paper type. Used to:
         (a) post-extraction validation (warn if a meta-analysis produces
             0 research_gap annotations),
         (b) modulate agent prompt emphasis (future enhancement).
Reads: Raw annotations from P1 agents
Writes: Returns warnings list (consumed by P1 runner for logging)
Gates: None (warnings only — annotations are additive, not mandatory)
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from crci.shared.models.enums import AnnotationCategory, PaperSubtype

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategoryProfile:
    """Expected yield for one annotation category from one paper type.

    Attributes:
        category: The annotation category.
        expected_yield: "HIGH", "MODERATE", "LOW", or "NONE".
        priority: 1-3 stars (3 = highest priority for this paper type).
        notes: Human-readable context.
    """

    category: AnnotationCategory
    expected_yield: str
    priority: int
    notes: str = ""


@dataclass(frozen=True)
class PaperAnnotationProfile:
    """Complete annotation profile for a paper type.

    Attributes:
        paper_subtype: The paper subtype this profile applies to.
        profiles: Expected yields per category.
    """

    paper_subtype: PaperSubtype
    profiles: tuple[CategoryProfile, ...]


# ═══════════════════════════════════════════════════════════════
#  §5.1 Meta-Analysis Profile
# ═══════════════════════════════════════════════════════════════

META_ANALYSIS_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.META_ANALYSIS,
    profiles=(
        CategoryProfile(
            AnnotationCategory.RESEARCH_GAP, "HIGH", 3,
            "MAs routinely identify gaps in Discussion; 2-5 expected",
        ),
        CategoryProfile(
            AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER, "MODERATE", 3,
            "MA limitations often name unmeasured confounders",
        ),
        CategoryProfile(
            AnnotationCategory.DOSE_RESPONSE_EVIDENCE, "MODERATE", 3,
            "MAs with dose subgroups may report dose-response patterns",
        ),
        CategoryProfile(
            AnnotationCategory.NULL_FINDING_CONTEXT, "MODERATE", 2,
            "MAs report null subgroups or non-significant secondary outcomes",
        ),
        CategoryProfile(
            AnnotationCategory.MEASUREMENT_LIMITATION, "MODERATE", 2,
            "MAs note heterogeneity in outcome measures",
        ),
        CategoryProfile(
            AnnotationCategory.GENERALIZABILITY_CONCERN, "MODERATE", 2,
            "MAs note population scope limitations",
        ),
        CategoryProfile(
            AnnotationCategory.MECHANISM_HYPOTHESIS, "LOW", 1,
            "MAs occasionally propose new mechanism hypotheses",
        ),
    ),
)

# ═══════════════════════════════════════════════════════════════
#  §5.2 RCT Profile
# ═══════════════════════════════════════════════════════════════

RCT_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.RCT_EXERCISE,
    profiles=(
        CategoryProfile(
            AnnotationCategory.TEMPORAL_ONSET, "HIGH", 3,
            "RCTs report intervention timing (onset, duration, follow-up)",
        ),
        CategoryProfile(
            AnnotationCategory.MEASUREMENT_LIMITATION, "HIGH", 3,
            "RCTs discuss instrument limitations and sensitivity",
        ),
        CategoryProfile(
            AnnotationCategory.ADHERENCE_DATA, "HIGH", 3,
            "RCTs report compliance/adherence rates",
        ),
        CategoryProfile(
            AnnotationCategory.MECHANISM_HYPOTHESIS, "MODERATE", 2,
            "RCTs may propose mechanisms in Discussion",
        ),
        CategoryProfile(
            AnnotationCategory.POPULATION_SPECIFICITY, "MODERATE", 2,
            "RCT inclusion/exclusion criteria define population scope",
        ),
        CategoryProfile(
            AnnotationCategory.NULL_FINDING_CONTEXT, "MODERATE", 2,
            "RCTs report non-significant secondary outcomes",
        ),
        CategoryProfile(
            AnnotationCategory.ADVERSE_EVENT, "LOW", 2,
            "RCTs report safety data (if collected)",
        ),
        CategoryProfile(
            AnnotationCategory.TEMPORAL_DECAY, "LOW", 1,
            "Only RCTs with follow-up report detraining/decay",
        ),
    ),
)

# ═══════════════════════════════════════════════════════════════
#  §5.3 Mechanistic / Preclinical Profile
# ═══════════════════════════════════════════════════════════════

MECHANISTIC_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.MECHANISTIC_HUMAN,
    profiles=(
        CategoryProfile(
            AnnotationCategory.MECHANISM_HYPOTHESIS, "HIGH", 3,
            "Mechanistic papers are primary sources of mechanism hypotheses",
        ),
        CategoryProfile(
            AnnotationCategory.BIOLOGICAL_PLAUSIBILITY, "HIGH", 3,
            "Mechanistic papers provide direct biological plausibility evidence",
        ),
        CategoryProfile(
            AnnotationCategory.MECHANISM_INTERACTION, "MODERATE", 2,
            "Mechanistic papers may identify pathway interactions",
        ),
        CategoryProfile(
            AnnotationCategory.TEMPORAL_ONSET, "MODERATE", 2,
            "Biomarker kinetics provide temporal onset data",
        ),
        CategoryProfile(
            AnnotationCategory.MODEL_DIAGNOSTIC, "LOW", 1,
            "Mechanistic papers occasionally discuss model assumptions",
        ),
    ),
)

# ═══════════════════════════════════════════════════════════════
#  Observational Profile
# ═══════════════════════════════════════════════════════════════

OBSERVATIONAL_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.LONGITUDINAL_COHORT,
    profiles=(
        CategoryProfile(
            AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER, "HIGH", 3,
            "Observational studies have unmeasured confounding by definition",
        ),
        CategoryProfile(
            AnnotationCategory.POPULATION_SPECIFICITY, "HIGH", 3,
            "Cohort studies define specific populations",
        ),
        CategoryProfile(
            AnnotationCategory.TEMPORAL_ONSET, "MODERATE", 2,
            "Longitudinal studies track change over time",
        ),
        CategoryProfile(
            AnnotationCategory.TEMPORAL_TRAJECTORY, "MODERATE", 2,
            "Longitudinal data reveals trajectory classes",
        ),
        CategoryProfile(
            AnnotationCategory.SELECTION_BIAS, "MODERATE", 2,
            "Cohort studies are susceptible to selection bias",
        ),
        CategoryProfile(
            AnnotationCategory.GENERALIZABILITY_CONCERN, "LOW", 1,
            "Single-site cohorts may have limited generalizability",
        ),
    ),
)

# Psychometric Validation Profile (PIMP WP-6 addition)
PSYCHOMETRIC_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.PSYCHOMETRIC_VALIDATION,
    profiles=(
        CategoryProfile(
            AnnotationCategory.MEASUREMENT_LIMITATION, "HIGH", 3,
            "Direct output: instrument properties, DIF, ceiling/floor effects",
        ),
        CategoryProfile(
            AnnotationCategory.POPULATION_SPECIFICITY, "HIGH", 3,
            "Normative sample characteristics",
        ),
        CategoryProfile(
            AnnotationCategory.CROSS_VALIDATION, "HIGH", 3,
            "Cross-validation with other instruments",
        ),
        CategoryProfile(
            AnnotationCategory.METHODOLOGICAL_INNOVATION, "MODERATE", 2,
            "Novel measurement or scoring approaches",
        ),
        CategoryProfile(
            AnnotationCategory.REPLICATION_STATUS, "MODERATE", 2,
            "Comparison with prior validation studies",
        ),
        CategoryProfile(
            AnnotationCategory.RESEARCH_GAP, "LOW", 1,
        ),
    ),
)


# ═══════════════════════════════════════════════════════════════
#  LOOKUP TABLE
# ═══════════════════════════════════════════════════════════════

ANNOTATION_PROFILES: dict[PaperSubtype, PaperAnnotationProfile] = {
    # Meta-analyses (all subtypes)
    PaperSubtype.META_ANALYSIS: META_ANALYSIS_PROFILE,
    PaperSubtype.PAIRWISE_MA: META_ANALYSIS_PROFILE,
    PaperSubtype.NMA: META_ANALYSIS_PROFILE,
    PaperSubtype.IPDMA: META_ANALYSIS_PROFILE,
    PaperSubtype.DOSE_RESPONSE_MA: META_ANALYSIS_PROFILE,
    PaperSubtype.UMBRELLA_REVIEW: META_ANALYSIS_PROFILE,
    PaperSubtype.SYSTEMATIC_REVIEW: META_ANALYSIS_PROFILE,
    PaperSubtype.SCOPING_REVIEW: META_ANALYSIS_PROFILE,
    PaperSubtype.MEGA_ANALYSIS: META_ANALYSIS_PROFILE,
    # RCTs (all subtypes)
    PaperSubtype.RCT_EXERCISE: RCT_PROFILE,
    PaperSubtype.RCT_COGNITIVE: RCT_PROFILE,
    PaperSubtype.RCT_PHARMACOLOGICAL: RCT_PROFILE,
    PaperSubtype.RCT_MULTIMODAL: RCT_PROFILE,
    PaperSubtype.STANDARD_RCT: RCT_PROFILE,
    PaperSubtype.FACTORIAL_RCT: RCT_PROFILE,
    PaperSubtype.PILOT_RCT: RCT_PROFILE,
    PaperSubtype.CROSSOVER_RCT: RCT_PROFILE,
    # Mechanistic
    PaperSubtype.MECHANISTIC_HUMAN: MECHANISTIC_PROFILE,
    PaperSubtype.MECHANISTIC_ANIMAL: MECHANISTIC_PROFILE,
    PaperSubtype.MECHANISTIC_IN_VITRO: MECHANISTIC_PROFILE,
    PaperSubtype.BIOMARKER_DISCOVERY: MECHANISTIC_PROFILE,
    # Observational
    PaperSubtype.LONGITUDINAL_COHORT: OBSERVATIONAL_PROFILE,
    PaperSubtype.CROSS_SECTIONAL: OBSERVATIONAL_PROFILE,
    PaperSubtype.PROSPECTIVE_COHORT: OBSERVATIONAL_PROFILE,
    PaperSubtype.RETROSPECTIVE_COHORT: OBSERVATIONAL_PROFILE,
    PaperSubtype.INTENSIVE_LONGITUDINAL: OBSERVATIONAL_PROFILE,
    PaperSubtype.LONGITUDINAL_FOLLOWUP: OBSERVATIONAL_PROFILE,
    PaperSubtype.NORMATIVE_COHORT: OBSERVATIONAL_PROFILE,
    # Psychometric
    PaperSubtype.PSYCHOMETRIC_VALIDATION: PSYCHOMETRIC_PROFILE,
}


def validate_annotation_yield(
    paper_subtype: str | PaperSubtype,
    annotations: list[Any],
) -> list[str]:
    """Check extracted annotations against paper-type profile expectations.

    Compares the categories of extracted annotations to the expected yield
    defined in the paper-type profile. Generates warnings for HIGH-priority
    categories that yielded 0 annotations.

    Parameters
    ----------
    paper_subtype : str | PaperSubtype
        The paper subtype (from P0 triage).
    annotations : list
        Raw annotation emissions from P1 agents. Each must have a
        `category` attribute (str or AnnotationCategory).

    Returns
    -------
    list[str]
        Warning messages for missing HIGH-priority categories.
    """
    # Resolve subtype
    if isinstance(paper_subtype, str):
        try:
            subtype = PaperSubtype(paper_subtype)
        except ValueError:
            logger.debug(
                "PROFILE: no profile for paper_subtype=%s (not in PaperSubtype enum)",
                paper_subtype,
            )
            return []
    else:
        subtype = paper_subtype

    profile = ANNOTATION_PROFILES.get(subtype)
    if profile is None:
        logger.debug("PROFILE: no profile defined for %s", subtype.value)
        return []

    # Count categories in extracted annotations
    category_counts: Counter[str] = Counter()
    for ann in annotations:
        cat = getattr(ann, "category", None)
        if cat is not None:
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            category_counts[cat_val] += 1

    warnings: list[str] = []
    for cp in profile.profiles:
        cat_val = cp.category.value
        count = category_counts.get(cat_val, 0)

        if cp.expected_yield == "HIGH" and count == 0:
            msg = (
                f"Expected HIGH yield for {cat_val} from "
                f"{subtype.value} but got 0"
            )
            warnings.append(msg)
            logger.warning("PROFILE MISS: %s", msg)
        elif cp.expected_yield == "MODERATE" and count == 0 and cp.priority >= 3:
            msg = (
                f"Expected MODERATE yield (priority {cp.priority}) for "
                f"{cat_val} from {subtype.value} but got 0"
            )
            warnings.append(msg)
            logger.info("PROFILE NOTE: %s", msg)

    if not warnings:
        logger.info(
            "PROFILE: annotation yield for %s meets expectations (%d categories found)",
            subtype.value,
            len(category_counts),
        )

    return warnings
