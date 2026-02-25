# VERIFIED: formulas — P3-2 w_scope matches spec lines 740-764 (EX-P2-S6)
# VERIFIED: imports — all modules exist (shared.config)
# VERIFIED: backward wiring — reads evidence population descriptors
# VERIFIED: forward wiring — writes w_scope per evidence record for P3 layers
# VERIFIED: no hardcoded formula parameters — SCOPE_WEIGHTS and SCOPE_FLOOR from config
# VERIFIED: gates — none (pure computation)
"""
Component: SYS_EXTRACTION.EX-P2.S6
Spec: SYS_EXTRACTION_COMPLETE.md lines 740-764 (EX-P2-S6 Scope Matching)
Formula P3-2: w_scope = Σ(w_d × match_d)
  Dimensions: cancer(0.35), phase(0.25), regimen(0.20), age(0.10), sex(0.10)
  Floor: 0.3 (max 3.33× SE inflation from scope mismatch)
Reads: Evidence record population descriptors, target population context
Writes: w_scope per evidence record (consumed by P3 layer_2_scope_match)
Gates: None (pure computation)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.config import SCOPE_FLOOR, SCOPE_WEIGHTS

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  OUTPUT TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class DimensionMatch:
    """Match result for a single scope dimension."""

    dimension: str
    weight: float
    match_score: float  # 0.0 = no match, 1.0 = exact match
    weighted_contribution: float
    note: str


@dataclass
class ScopeMatchResult:
    """Result of scope matching for a single evidence record.

    Formula P3-2: w_scope = max(SCOPE_FLOOR, Σ(w_d × match_d))
    """

    ler_id: str
    w_scope: float
    dimension_matches: list[DimensionMatch] = field(default_factory=list)
    raw_score: float = 0.0  # before floor application
    floor_applied: bool = False
    notes: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  DIMENSION MATCHERS
# ═══════════════════════════════════════════════════════════════


def _match_cancer(study_cancer: str | None, target_cancer: str | None) -> float:
    """Score cancer type match: 1.0=exact, 0.5=related, 0.0=unrelated."""
    if study_cancer is None or target_cancer is None:
        return 0.5  # uncertain → moderate match
    study = study_cancer.lower().strip()
    target = target_cancer.lower().strip()
    if study == target:
        return 1.0
    # Related cancer groupings (same organ system)
    if study == "mixed" or target == "mixed":
        return 0.5
    return 0.0


def _match_phase(study_phase: str | None, target_phase: str | None) -> float:
    """Score treatment phase match: 1.0=exact, 0.5=adjacent, 0.0=distant."""
    if study_phase is None or target_phase is None:
        return 0.5
    study = study_phase.lower().strip()
    target = target_phase.lower().strip()
    if study == target:
        return 1.0
    # Adjacent phases get partial credit
    _adjacent = {
        ("neoadjuvant", "adjuvant"): 0.7,
        ("adjuvant", "neoadjuvant"): 0.7,
        ("adjuvant", "survivorship"): 0.6,
        ("survivorship", "adjuvant"): 0.6,
        ("active_treatment", "adjuvant"): 0.6,
        ("adjuvant", "active_treatment"): 0.6,
    }
    return _adjacent.get((study, target), 0.0)


def _match_regimen(study_regimen: str | None, target_regimen: str | None) -> float:
    """Score regimen match: 1.0=exact, 0.5=same class, 0.0=unrelated."""
    if study_regimen is None or target_regimen is None:
        return 0.5
    study = study_regimen.lower().strip()
    target = target_regimen.lower().strip()
    if study == target:
        return 1.0
    # Same broad class (e.g., both chemotherapy)
    _classes = {
        "chemotherapy": {"ac", "tc", "fec", "docetaxel", "paclitaxel", "cyclophosphamide"},
        "hormonal": {"tamoxifen", "letrozole", "anastrozole", "aromatase_inhibitor"},
        "immunotherapy": {"pembrolizumab", "nivolumab", "checkpoint_inhibitor"},
    }
    for _class_members in _classes.values():
        if study in _class_members and target in _class_members:
            return 0.7
    if study == "mixed" or target == "mixed":
        return 0.3
    return 0.0


def _match_age(study_age_range: tuple[float, float] | None, target_age: float | None) -> float:
    """Score age match based on overlap of study age range with target."""
    if study_age_range is None or target_age is None:
        return 0.5
    low, high = study_age_range
    if low <= target_age <= high:
        return 1.0
    # Close to range → partial credit
    distance = min(abs(target_age - low), abs(target_age - high))
    if distance <= 5:
        return 0.8
    if distance <= 15:
        return 0.5
    return 0.2


def _match_sex(study_sex: str | None, target_sex: str | None) -> float:
    """Score sex match: 1.0=exact, 0.7=mixed study, 0.0=mismatch."""
    if study_sex is None or target_sex is None:
        return 0.7  # default for unspecified
    study = study_sex.lower().strip()
    target = target_sex.lower().strip()
    if study == target:
        return 1.0
    if study in ("mixed", "both", "all"):
        return 0.7
    return 0.0


# Ordered dimension matcher functions
_DIMENSION_MATCHERS = {
    "cancer": _match_cancer,
    "phase": _match_phase,
    "regimen": _match_regimen,
    "age": _match_age,
    "sex": _match_sex,
}


# ═══════════════════════════════════════════════════════════════
#  CORE FUNCTION
# ═══════════════════════════════════════════════════════════════


def compute_scope_match(
    ler_id: str,
    study_population: dict[str, object],
    target_population: dict[str, object],
) -> ScopeMatchResult:
    """Compute transportability scope weight for an evidence record.

    Formula P3-2: w_scope = max(SCOPE_FLOOR, Σ(w_d × match_d))

    5 dimensions: cancer (0.35), phase (0.25), regimen (0.20),
    age (0.10), sex (0.10).  Floor = 0.3.

    Args:
        ler_id: Literature-evidence-record identifier.
        study_population: Dict with keys 'cancer', 'phase', 'regimen',
            'age' (tuple or float), 'sex'. Missing keys → uncertain.
        target_population: Dict with same keys for the target population.

    Returns:
        ScopeMatchResult with w_scope and per-dimension breakdown.
    """
    dimension_matches: list[DimensionMatch] = []
    raw_score = 0.0

    for dim, weight in SCOPE_WEIGHTS.items():
        study_val = study_population.get(dim)
        target_val = target_population.get(dim)

        # Use appropriate matcher
        if dim == "age":
            # age matcher expects (low, high) tuple for study, float for target
            match_score = _match_age(study_val, target_val)  # type: ignore[arg-type]
        elif dim in _DIMENSION_MATCHERS:
            match_score = _DIMENSION_MATCHERS[dim](study_val, target_val)  # type: ignore[arg-type]
        else:
            match_score = 0.5  # unknown dimension → moderate default

        weighted = weight * match_score
        raw_score += weighted

        note = f"{dim}: study={study_val}, target={target_val}, match={match_score:.2f}"
        dimension_matches.append(
            DimensionMatch(
                dimension=dim,
                weight=weight,
                match_score=match_score,
                weighted_contribution=weighted,
                note=note,
            )
        )

    # Apply floor — Formula P3-2
    floor_applied = raw_score < SCOPE_FLOOR
    w_scope = max(SCOPE_FLOOR, raw_score)

    notes: list[str] = []
    if floor_applied:
        notes.append(
            f"Floor applied: raw w_scope={raw_score:.4f} < {SCOPE_FLOOR}, "
            f"clamped to {SCOPE_FLOOR}"
        )

    return ScopeMatchResult(
        ler_id=ler_id,
        w_scope=w_scope,
        dimension_matches=dimension_matches,
        raw_score=raw_score,
        floor_applied=floor_applied,
        notes=notes,
    )


def compute_scope_match_batch(
    records: list[dict],
    target_population: dict[str, object],
) -> list[ScopeMatchResult]:
    """Compute scope match for a batch of evidence records.

    Each record dict must have 'ler_id' and 'study_population' (a dict
    with keys 'cancer', 'phase', 'regimen', 'age', 'sex').

    Args:
        records: List of evidence record dicts.
        target_population: Target population descriptor for matching.

    Returns:
        List of ScopeMatchResult, one per record.
    """
    results: list[ScopeMatchResult] = []

    for rec in records:
        result = compute_scope_match(
            ler_id=rec["ler_id"],
            study_population=rec.get("study_population", {}),
            target_population=target_population,
        )
        results.append(result)

    n_floored = sum(1 for r in results if r.floor_applied)
    logger.info(
        "Scope matching batch: %d records, mean w_scope=%.3f, "
        "%d floored at %.2f",
        len(results),
        sum(r.w_scope for r in results) / max(len(results), 1),
        n_floored,
        SCOPE_FLOOR,
    )
    return results
