# VERIFIED: no formulas (keyword-density scoring, not spec-defined formula)
# VERIFIED: imports — stdlib + shared.models.enums + shared.models.intermediate_states
# VERIFIED: backward wiring — reads IngestedPaper dict from pdf_ingestion.py
# VERIFIED: forward wiring — writes ScreenedPaper dict for paper_type_classifier.py, mode_selection.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates P0-G2 raise on failure
"""
Component: SYS_EXTRACTION.EX-P0.P0-S2
Spec: SYS_EXTRACTION_COMPLETE.md lines 233-254
Formulas: None (keyword-density approach, v1 simple)
Reads: IngestedPaper dict (from pdf_ingestion.py)
Writes: ScreenedPaper dict (consumed by paper_type_classifier.py, mode_selection.py)
Gates: P0-G2 (Relevance >= 0.5 or REJECT)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from crci.shared.models.enums import TriageDecision
from crci.shared.models.intermediate_states import GateViolation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  KEYWORD DICTIONARIES FOR INCLUSION CRITERIA
# ═══════════════════════════════════════════════════════════════

# Criterion 1: Cancer population (any type)
_CANCER_KEYWORDS: list[str] = [
    "cancer", "oncology", "tumor", "tumour", "malignancy", "malignant",
    "carcinoma", "lymphoma", "leukemia", "leukaemia", "myeloma",
    "neoplasm", "chemotherapy", "radiation therapy", "radiotherapy",
    "mastectomy", "immunotherapy", "oncologic", "oncological",
    "breast cancer", "lung cancer", "colorectal cancer", "prostate cancer",
    "hematological", "haematological", "sarcoma", "melanoma",
    "cancer survivor", "cancer treatment", "cancer patient",
    "cancer diagnosis", "cancer-related",
]

# Criterion 2: Cognitive outcome OR biological mechanism measure
_COGNITIVE_KEYWORDS: list[str] = [
    "cognitive", "cognition", "memory", "attention", "executive function",
    "processing speed", "concentration", "chemo brain", "chemobrain",
    "cancer-related cognitive", "crci", "cognitive impairment",
    "cognitive decline", "cognitive function", "cognitive deficit",
    "neuropsychological", "neurocognitive", "brain fog",
    "mental fatigue", "cognitive complaint",
    "working memory", "verbal fluency", "reaction time",
    # Biological mechanism measures
    "neuroinflammation", "cytokine", "interleukin", "tnf",
    "cortisol", "bdnf", "brain-derived", "neuroplasticity",
    "hippocampal", "white matter", "gray matter", "grey matter",
    "blood-brain barrier", "neurogenesis", "oxidative stress",
]

# Criterion 3: Original data (not review/commentary)
_ORIGINAL_DATA_KEYWORDS: list[str] = [
    "participants", "subjects", "patients", "sample",
    "recruited", "enrolled", "randomized", "randomised",
    "cohort", "n =", "n=", "sample size",
    "baseline", "follow-up", "follow up",
    "data collected", "data collection",
    "inclusion criteria", "exclusion criteria",
    "informed consent", "ethics", "irb", "institutional review",
    "primary outcome", "secondary outcome",
    "assessed", "measured", "administered",
]

# Criterion 4: Human subjects (or mechanistic animal with translation)
_HUMAN_KEYWORDS: list[str] = [
    "human", "patient", "participant", "subject",
    "men", "women", "adult", "elderly", "older adult",
    "clinical trial", "clinical study",
    "hospital", "clinic", "outpatient", "inpatient",
    "survivor", "caregiver",
]

_ANIMAL_WITH_TRANSLATION_KEYWORDS: list[str] = [
    "translational", "clinical relevance", "human implications",
    "clinical translation", "translatable",
]

# Criterion 5: Published in peer-reviewed venue
_PEER_REVIEW_KEYWORDS: list[str] = [
    "journal", "doi", "published", "peer-reviewed",
    "abstract", "introduction", "methods", "results", "discussion",
    "references", "correspondence",
    "vol.", "volume", "issue", "pp.", "pages",
]

# ═══════════════════════════════════════════════════════════════
#  EXCLUSION CRITERIA PATTERNS
# ═══════════════════════════════════════════════════════════════

# Exclusion 2: Retracted
_RETRACTION_KEYWORDS: list[str] = [
    "retracted", "retraction", "withdrawn", "expression of concern",
    "retraction notice", "editorial retraction",
]

# Sample size pattern for exclusion 3
_SAMPLE_SIZE_PATTERN = re.compile(
    r"(?:n\s*=\s*|sample\s+(?:size\s+(?:of\s+)?)?(?:was\s+)?|"
    r"(?:total\s+of\s+)|(?:enrolled\s+))(\d+)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
#  RELEVANCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# Score >= ACCEPT_THRESHOLD -> ACCEPT
# REVIEW_THRESHOLD <= Score < ACCEPT_THRESHOLD -> REVIEW
# Score < REVIEW_THRESHOLD -> REJECT
ACCEPT_THRESHOLD: float = 0.8
REVIEW_THRESHOLD: float = 0.5


def screen_relevance(
    ingested_paper: dict[str, Any],
    known_dois: set[str] | None = None,
    pubmed_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score CRCI relevance using keyword matching (v1 simple approach).

    P0-S2: Relevance Screening.
    Checks 5 inclusion criteria and 3 exclusion criteria.
    Score = proportion of inclusion criteria met x (1 - any exclusion).

    Args:
        ingested_paper: Output from pdf_ingestion.ingest_pdf().
        known_dois: Set of DOIs already in study_registry_v1 for duplicate check.
        pubmed_metadata: Optional PubMed metadata dict with keys like
            'doi', 'retracted', 'sample_size'.

    Returns:
        ScreenedPaper dict with keys:
            relevance_score: float [0,1]
            decision: TriageDecision (ACCEPT, REJECT, REVIEW)
            inclusion_criteria: dict[str, bool] - 5 criteria checked
            exclusion_criteria: dict[str, bool] - 3 exclusion checks
            rejection_reason: str | None

    Raises:
        GateViolation: P0-G2 if relevance < REVIEW_THRESHOLD (0.5).
    """
    canonical_text = ingested_paper.get("canonical_text", "")
    text_lower = canonical_text.lower()

    if known_dois is None:
        known_dois = set()
    if pubmed_metadata is None:
        pubmed_metadata = {}

    # ─── Check 5 inclusion criteria ───────────────────────────
    inclusion_criteria = _check_inclusion_criteria(
        text_lower=text_lower,
        pubmed_metadata=pubmed_metadata,
    )

    # ─── Check 3 exclusion criteria ───────────────────────────
    exclusion_criteria = _check_exclusion_criteria(
        text_lower=text_lower,
        pubmed_metadata=pubmed_metadata,
        known_dois=known_dois,
    )

    # ─── Gate P0-G3: Not duplicate ─────────────────────────────
    if exclusion_criteria.get("duplicate_doi", False):
        doi = pubmed_metadata.get("doi", "")
        raise GateViolation(
            "P0-G3",
            f"Duplicate DOI detected: {doi}. Paper already processed.",
            {"doi": doi},
        )

    # ─── Compute relevance score ──────────────────────────────
    # Spec: Score = proportion of inclusion met x (1 - any exclusion)
    inclusion_count = sum(1 for v in inclusion_criteria.values() if v)
    inclusion_total = len(inclusion_criteria)
    inclusion_proportion = inclusion_count / inclusion_total if inclusion_total > 0 else 0.0

    any_exclusion = any(exclusion_criteria.values())
    exclusion_factor = 0.0 if any_exclusion else 1.0

    relevance_score = inclusion_proportion * exclusion_factor

    # ─── Determine decision ───────────────────────────────────
    # Spec: Score >= 0.8 -> ACCEPT, 0.5-0.8 -> REVIEW, < 0.5 -> REJECT
    rejection_reason: str | None = None

    if relevance_score >= ACCEPT_THRESHOLD:
        decision = TriageDecision.ACCEPT
    elif relevance_score >= REVIEW_THRESHOLD:
        decision = TriageDecision.REVIEW
    else:
        decision = TriageDecision.REJECT
        rejection_reason = _build_rejection_reason(
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
            relevance_score=relevance_score,
        )

    logger.info(
        "Relevance screening: score=%.3f decision=%s inclusion=%d/%d exclusion=%s",
        relevance_score,
        decision.value,
        inclusion_count,
        inclusion_total,
        any_exclusion,
    )

    # ─── Gate P0-G2: Relevance >= 0.5 or REJECT ──────────────
    if decision == TriageDecision.REJECT:
        raise GateViolation(
            "P0-G2",
            f"Relevance score {relevance_score:.3f} below threshold "
            f"{REVIEW_THRESHOLD}. Reason: {rejection_reason}",
            {
                "relevance_score": relevance_score,
                "inclusion_criteria": inclusion_criteria,
                "exclusion_criteria": exclusion_criteria,
            },
        )

    return {
        "relevance_score": relevance_score,
        "decision": decision,
        "inclusion_criteria": inclusion_criteria,
        "exclusion_criteria": exclusion_criteria,
        "rejection_reason": rejection_reason,
    }


def _check_inclusion_criteria(
    text_lower: str,
    pubmed_metadata: dict[str, Any],
) -> dict[str, bool]:
    """Check the 5 inclusion criteria.

    1. Cancer population (any type)
    2. Cognitive outcome OR biological mechanism measure
    3. Original data (not review/commentary)
    4. Human subjects (or mechanistic animal with translation)
    5. Published in peer-reviewed venue
    """
    # Criterion 1: Cancer population
    cancer_hit = _keyword_density_check(text_lower, _CANCER_KEYWORDS, min_hits=2)

    # Criterion 2: Cognitive outcome or biological mechanism
    cognitive_hit = _keyword_density_check(text_lower, _COGNITIVE_KEYWORDS, min_hits=2)

    # Criterion 3: Original data
    original_data_hit = _keyword_density_check(text_lower, _ORIGINAL_DATA_KEYWORDS, min_hits=3)

    # Criterion 4: Human subjects
    human_hit = _keyword_density_check(text_lower, _HUMAN_KEYWORDS, min_hits=2)
    # Allow animal studies if they explicitly discuss clinical translation
    if not human_hit:
        animal_translation = _keyword_density_check(
            text_lower, _ANIMAL_WITH_TRANSLATION_KEYWORDS, min_hits=1
        )
        if animal_translation and ("animal" in text_lower or "mouse" in text_lower or "rat" in text_lower):
            human_hit = True
            logger.info(
                "Criterion 4 (human subjects): accepted as mechanistic animal "
                "with translation language"
            )

    # Criterion 5: Peer-reviewed venue
    peer_reviewed_hit = _keyword_density_check(text_lower, _PEER_REVIEW_KEYWORDS, min_hits=3)
    # PubMed metadata override: if we have a DOI, it's likely peer-reviewed
    if pubmed_metadata.get("doi"):
        peer_reviewed_hit = True

    return {
        "cancer_population": cancer_hit,
        "cognitive_outcome": cognitive_hit,
        "original_data": original_data_hit,
        "human_subjects": human_hit,
        "peer_reviewed": peer_reviewed_hit,
    }


def _check_exclusion_criteria(
    text_lower: str,
    pubmed_metadata: dict[str, Any],
    known_dois: set[str],
) -> dict[str, bool]:
    """Check the 3 exclusion criteria.

    1. Duplicate (DOI match against known set)
    2. Retracted
    3. Sample size < 10
    """
    # Exclusion 1: Duplicate DOI
    doi = pubmed_metadata.get("doi", "")
    is_duplicate = bool(doi and doi in known_dois)
    if is_duplicate:
        logger.info("Exclusion: duplicate DOI detected: %s", doi)

    # Exclusion 2: Retracted
    is_retracted = pubmed_metadata.get("retracted", False)
    if not is_retracted:
        is_retracted = _keyword_density_check(text_lower, _RETRACTION_KEYWORDS, min_hits=1)
    if is_retracted:
        logger.info("Exclusion: retracted paper detected")

    # Exclusion 3: Sample size < 10
    small_sample = False
    # Try PubMed metadata first
    if pubmed_metadata.get("sample_size") is not None:
        if pubmed_metadata["sample_size"] < 10:
            small_sample = True
            logger.info(
                "Exclusion: sample size %d < 10 (from metadata)",
                pubmed_metadata["sample_size"],
            )
    else:
        # Parse from text
        extracted_n = _extract_sample_size(text_lower)
        if extracted_n is not None and extracted_n < 10:
            small_sample = True
            logger.info(
                "Exclusion: sample size %d < 10 (from text extraction)",
                extracted_n,
            )

    return {
        "duplicate_doi": is_duplicate,
        "retracted": is_retracted,
        "sample_size_below_10": small_sample,
    }


def _keyword_density_check(
    text_lower: str,
    keywords: list[str],
    min_hits: int,
) -> bool:
    """Check if at least min_hits distinct keywords appear in the text."""
    hits = 0
    for kw in keywords:
        if kw.lower() in text_lower:
            hits += 1
            if hits >= min_hits:
                return True
    return False


def _extract_sample_size(text_lower: str) -> int | None:
    """Extract the most likely total sample size from text.

    Returns the largest N found (assumes total sample is the largest reported N),
    or None if no sample size pattern is found.
    """
    matches = _SAMPLE_SIZE_PATTERN.findall(text_lower)
    if not matches:
        return None

    # Convert to integers and return the largest (most likely total N)
    sizes = []
    for m in matches:
        try:
            n = int(m)
            if n > 0:
                sizes.append(n)
        except (ValueError, TypeError):
            continue

    if not sizes:
        return None

    # Return the largest N found, which is the most likely total sample
    return max(sizes)


def _build_rejection_reason(
    inclusion_criteria: dict[str, bool],
    exclusion_criteria: dict[str, bool],
    relevance_score: float,
) -> str:
    """Build a human-readable rejection reason."""
    reasons: list[str] = []

    # Check exclusions first (they zero out the score)
    for criterion, triggered in exclusion_criteria.items():
        if triggered:
            reasons.append(f"Exclusion criterion met: {criterion}")

    # Check missing inclusions
    missing_inclusions = [k for k, v in inclusion_criteria.items() if not v]
    if missing_inclusions:
        reasons.append(
            f"Missing inclusion criteria: {', '.join(missing_inclusions)}"
        )

    if not reasons:
        reasons.append(f"Relevance score {relevance_score:.3f} below threshold")

    return "; ".join(reasons)
