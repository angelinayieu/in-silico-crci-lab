"""
Component: Shared — Canonical Controlled Vocabularies
Spec: IMPLEMENTATION_SLICES.md Slice 0, Gap 1
Formulas: None (mapping layer, no formulas)
Reads: Nothing (pure definitions)
Writes: Nothing (consumed by validated_evidence_writer, P3 layers)
Gates: None

Canonical controlled vocabularies + human-friendly → internal key mappings.

Every constrained field that crosses a system boundary (CSV → DB → P3/P4)
must have its mapping defined here. The validated_evidence_writer accepts
human-friendly inputs and persists canonical keys only.

Design decision: Internal keys map to themselves (idempotent) so that
values already in canonical form pass through unchanged.

VERIFIED: DESIGN_MULTIPLIERS keys match config.py lines 111-123
VERIFIED: GRADE_MULTIPLIERS keys match config.py lines 131-136
VERIFIED: SCALE_MULTIPLIERS keys match config.py lines 139-144
VERIFIED: no hardcoded formula parameters
"""
from __future__ import annotations

from crci.shared.config import SMALL_RCT_N_THRESHOLD

# ═══════════════════════════════════════════════════════════════
#  study_design: human-friendly → P3 L1 internal key
# ═══════════════════════════════════════════════════════════════

# Keys on the right MUST be exact matches for config.DESIGN_MULTIPLIERS keys.
STUDY_DESIGN_MAP: dict[str, str] = {
    # Human-friendly CSV inputs (left) → config.DESIGN_MULTIPLIERS keys (right)
    "RCT":                        "large_rct",    # reclassified by N in resolve_study_design()
    "rct":                        "large_rct",
    "randomized_controlled":      "large_rct",
    "randomized_controlled_trial": "large_rct",
    "quasi_experimental":         "well_adjusted_cohort",
    "cohort":                     "well_adjusted_cohort",
    "cohort_adjusted":            "well_adjusted_cohort",
    "prospective_cohort":         "well_adjusted_cohort",
    "longitudinal":               "unadjusted_longitudinal",
    "longitudinal_unadjusted":    "unadjusted_longitudinal",
    "cross_sectional":            "cross_sectional_unadjusted",
    "cross_sectional_adjusted":   "cross_sectional_adjusted",
    "cross_sectional_unadjusted": "cross_sectional_unadjusted",
    "animal":                     "animal_in_vivo",
    "animal_in_vivo":             "animal_in_vivo",
    "in_vitro":                   "in_vitro_mechanistic",
    "mechanistic":                "in_vitro_mechanistic",
    "in_vitro_mechanistic":       "in_vitro_mechanistic",
    "expert_opinion":             "expert_opinion",
    "narrative_review":           "expert_opinion",
    # Internal keys map to themselves (idempotent)
    "large_rct":                  "large_rct",
    "small_rct_default":          "small_rct_default",
    "well_adjusted_cohort":       "well_adjusted_cohort",
    "unadjusted_longitudinal":    "unadjusted_longitudinal",
}

# ═══════════════════════════════════════════════════════════════
#  rob_overall: human-friendly → config.GRADE_MULTIPLIERS key
# ═══════════════════════════════════════════════════════════════

# Cochrane risk-of-bias levels → GRADE quality levels.
# Low risk-of-bias = HIGH quality (inverse relationship).
ROB_TO_GRADE_MAP: dict[str, str] = {
    "low":       "HIGH",       # low risk-of-bias = HIGH quality
    "moderate":  "MODERATE",
    "some_concerns": "MODERATE",
    "high":      "LOW",        # high risk-of-bias = LOW quality
    "critical":  "VERY_LOW",
    "serious":   "LOW",
    # Internal keys map to themselves (idempotent)
    "HIGH":      "HIGH",
    "MODERATE":  "MODERATE",
    "LOW":       "LOW",
    "VERY_LOW":  "VERY_LOW",
}

# ═══════════════════════════════════════════════════════════════
#  cancer_validated: human-friendly → config.SCALE_MULTIPLIERS key
# ═══════════════════════════════════════════════════════════════

CANCER_VALIDATION_MAP: dict[str, str] = {
    "yes":      "validated_cancer",
    "true":     "validated_cancer",
    "no":       "general_population",
    "false":    "general_population",
    "unknown":  "used_cancer",
    "partial":  "used_cancer",
    # Internal keys map to themselves (idempotent)
    "validated_cancer":       "validated_cancer",
    "used_cancer":            "used_cancer",
    "general_population":     "general_population",
    "known_somatic_confound": "known_somatic_confound",
}

# ═══════════════════════════════════════════════════════════════
#  effect_type_original: allowed values (closed vocabulary)
# ═══════════════════════════════════════════════════════════════

EFFECT_TYPE_VOCAB: set[str] = {
    "cohen_d",
    "cohen_d_from_eta_sq",
    "log_or",
    "odds_ratio",
    "hazard_ratio",
    "r_correlation",
    "mean_diff",
    "partial_eta_sq",
    "hedges_g",
}

# ═══════════════════════════════════════════════════════════════
#  effect_size_context: allowed values
# ═══════════════════════════════════════════════════════════════

EFFECT_SIZE_CONTEXT_VOCAB: set[str] = {
    "BETWEEN_GROUP",
    "WITHIN_GROUP",
    "PRE_POST_CHANGE",
}

# ═══════════════════════════════════════════════════════════════
#  treatment_phase: allowed values
# ═══════════════════════════════════════════════════════════════

TREATMENT_PHASE_VOCAB: set[str] = {
    "active_treatment",
    "early_recovery",
    "late_recovery",
    "maintenance",
    "survivorship",
    "mixed",
    "not_specified",
}

# ═══════════════════════════════════════════════════════════════
#  cancer_type: allowed values
# ═══════════════════════════════════════════════════════════════

CANCER_TYPE_VOCAB: set[str] = {
    "breast",
    "prostate",
    "colorectal",
    "lung",
    "hematologic",
    "head_neck",
    "gynecologic",
    "brain",
    "mixed",
    "any_solid",
    "not_specified",
}


# ═══════════════════════════════════════════════════════════════
#  Mapping Functions
# ═══════════════════════════════════════════════════════════════

def resolve_study_design(raw: str, n_total: int | None = None) -> str:
    """Map human-friendly study_design to P3 L1 internal key.

    If raw is an RCT variant and n_total <= SMALL_RCT_N_THRESHOLD (200),
    returns 'small_rct_default' so L1 can apply the interpolation formula.

    Args:
        raw: Human-friendly or canonical study design string.
        n_total: Sample size. Used for RCT reclassification.

    Returns:
        Canonical key that exists in config.DESIGN_MULTIPLIERS.

    Raises:
        ValueError: If raw is not in STUDY_DESIGN_MAP.
    """
    canonical = STUDY_DESIGN_MAP.get(raw.strip())
    if canonical is None:
        raise ValueError(
            f"Unknown study_design '{raw}'. "
            f"Valid inputs: {sorted(STUDY_DESIGN_MAP.keys())}"
        )
    # RCT reclassification by sample size
    if canonical == "large_rct" and n_total is not None and n_total <= SMALL_RCT_N_THRESHOLD:
        return "small_rct_default"
    return canonical


def resolve_rob_to_grade(raw: str) -> str:
    """Map risk-of-bias level to GRADE quality key.

    Args:
        raw: Human-friendly or canonical RoB string.

    Returns:
        Canonical key that exists in config.GRADE_MULTIPLIERS.

    Raises:
        ValueError: If raw is not in ROB_TO_GRADE_MAP.
    """
    canonical = ROB_TO_GRADE_MAP.get(raw.strip())
    if canonical is None:
        raise ValueError(
            f"Unknown rob_overall '{raw}'. "
            f"Valid inputs: {sorted(ROB_TO_GRADE_MAP.keys())}"
        )
    return canonical


def resolve_cancer_validation(raw: str) -> str:
    """Map cancer validation status to SCALE_MULTIPLIERS key.

    Args:
        raw: Human-friendly or canonical cancer validation string.

    Returns:
        Canonical key that exists in config.SCALE_MULTIPLIERS.

    Raises:
        ValueError: If raw is not in CANCER_VALIDATION_MAP.
    """
    canonical = CANCER_VALIDATION_MAP.get(raw.strip().lower())
    if canonical is None:
        raise ValueError(
            f"Unknown cancer_validated '{raw}'. "
            f"Valid inputs: {sorted(CANCER_VALIDATION_MAP.keys())}"
        )
    return canonical


def validate_effect_type(raw: str) -> str:
    """Validate that effect_type_original is in the closed vocabulary.

    Args:
        raw: Effect type string.

    Returns:
        The validated effect type (stripped).

    Raises:
        ValueError: If raw is not in EFFECT_TYPE_VOCAB.
    """
    cleaned = raw.strip()
    if cleaned not in EFFECT_TYPE_VOCAB:
        raise ValueError(
            f"Unknown effect_type '{cleaned}'. "
            f"Valid: {sorted(EFFECT_TYPE_VOCAB)}"
        )
    return cleaned


def validate_effect_size_context(raw: str) -> str:
    """Validate that effect_size_context is in the closed vocabulary.

    Args:
        raw: Effect size context string.

    Returns:
        The validated context (stripped).

    Raises:
        ValueError: If raw is not in EFFECT_SIZE_CONTEXT_VOCAB.
    """
    cleaned = raw.strip()
    if cleaned not in EFFECT_SIZE_CONTEXT_VOCAB:
        raise ValueError(
            f"Unknown effect_size_context '{cleaned}'. "
            f"Valid: {sorted(EFFECT_SIZE_CONTEXT_VOCAB)}"
        )
    return cleaned


def validate_treatment_phase(raw: str) -> str:
    """Validate that treatment_phase is in the closed vocabulary.

    Args:
        raw: Treatment phase string.

    Returns:
        The validated phase (stripped).

    Raises:
        ValueError: If raw is not in TREATMENT_PHASE_VOCAB.
    """
    cleaned = raw.strip()
    if cleaned not in TREATMENT_PHASE_VOCAB:
        raise ValueError(
            f"Unknown treatment_phase '{cleaned}'. "
            f"Valid: {sorted(TREATMENT_PHASE_VOCAB)}"
        )
    return cleaned


def validate_cancer_type(raw: str) -> str:
    """Validate that cancer_type is in the closed vocabulary.

    Args:
        raw: Cancer type string.

    Returns:
        The validated type (stripped).

    Raises:
        ValueError: If raw is not in CANCER_TYPE_VOCAB.
    """
    cleaned = raw.strip().lower()
    if cleaned not in CANCER_TYPE_VOCAB:
        raise ValueError(
            f"Unknown cancer_type '{cleaned}'. "
            f"Valid: {sorted(CANCER_TYPE_VOCAB)}"
        )
    return cleaned
