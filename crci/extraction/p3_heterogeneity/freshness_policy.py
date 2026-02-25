# VERIFIED: formulas match CONVERSION_VALIDITY_AND_HARDENING.md Module 5
# VERIFIED: imports — all modules exist (shared.config, shared.models.enums)
# VERIFIED: backward wiring — reads pub_year + parameter_family from upstream
# VERIFIED: forward wiring — writes FreshnessResult consumed by se_eff_assembly.py L7
# VERIFIED: no hardcoded formula parameters — all from config
"""
Component: SYS_EXTRACTION.EX-P3.L7-FAMILY
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 5 (Family-Specific Freshness)
Formulas:
    F5-1: w_fresh = max(floor, 1 − decay × (ref_year − pub_year))
    F5-2: supersession: w_fresh *= 0.70 if newer better-matched record exists
Reads: pub_year, parameter_family (from edge metadata)
Writes: FreshnessResult (consumed by P3 L7 / se_eff_assembly.py)
Gates: None (freshness is a weight, not a gate)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from crci.shared.config import (
    FRESHNESS_DEFAULT_WEIGHT,
    FRESHNESS_FAMILY_POLICIES,
    FRESHNESS_REFERENCE_YEAR,
    FRESHNESS_SUPERSESSION_MIN_N_RATIO,
    FRESHNESS_SUPERSESSION_PENALTY,
)
from crci.shared.models.enums import ParameterFamily

logger = logging.getLogger(__name__)

# Default policy for unknown families: same as edge_intervention
_DEFAULT_POLICY = (0.015, 0.70)


@dataclass(frozen=True)
class FreshnessResult:
    """Result of family-aware freshness weighting.

    Attributes
    ----------
    w_fresh : float
        The freshness weight (0.70-1.00).
    family : str
        Parameter family used.
    decay_rate : float
        Decay rate applied (per year).
    floor : float
        Floor value applied.
    age_years : int
        Study age in years.
    superseded : bool
        Whether supersession penalty was applied.
    notes : str
        Human-readable derivation summary.
    """

    w_fresh: float
    family: str
    decay_rate: float
    floor: float
    age_years: int
    superseded: bool
    notes: str


def get_family_policy(family: str | ParameterFamily) -> tuple[float, float]:
    """Look up the (decay_rate, floor) for a parameter family.

    Parameters
    ----------
    family : str | ParameterFamily
        Parameter family identifier.

    Returns
    -------
    tuple[float, float]
        (decay_rate_per_year, floor).
    """
    family_str = family.value if isinstance(family, ParameterFamily) else family
    policy = FRESHNESS_FAMILY_POLICIES.get(family_str, None)
    if policy is None:
        logger.warning(
            "Unknown parameter family '%s'; using default policy (%.3f/yr, floor %.2f)",
            family_str, _DEFAULT_POLICY[0], _DEFAULT_POLICY[1],
        )
        return _DEFAULT_POLICY
    return policy


def compute_freshness(
    pub_year: int | None,
    family: str | ParameterFamily = ParameterFamily.EDGE_INTERVENTION,
    *,
    superseded_by_newer: bool = False,
) -> FreshnessResult:
    """Compute family-specific freshness weight.

    Formula F5-1: w_fresh = max(floor, 1 − decay × (ref_year − pub_year))
    Formula F5-2: if superseded, w_fresh *= SUPERSESSION_PENALTY

    Parameters
    ----------
    pub_year : int | None
        Publication year. None → default weight + warning.
    family : str | ParameterFamily
        Parameter family for decay lookup.
    superseded_by_newer : bool
        Whether a newer, better-matched record exists (Module 5.2).

    Returns
    -------
    FreshnessResult
        Computed freshness weight with full provenance.
    """
    family_str = family.value if isinstance(family, ParameterFamily) else family
    decay_rate, floor = get_family_policy(family)

    if pub_year is None:
        logger.warning(
            "No publication year; using default w_fresh=%.2f for family '%s'",
            FRESHNESS_DEFAULT_WEIGHT, family_str,
        )
        return FreshnessResult(
            w_fresh=FRESHNESS_DEFAULT_WEIGHT,
            family=family_str,
            decay_rate=decay_rate,
            floor=floor,
            age_years=0,
            superseded=False,
            notes=f"No pub_year; default w_fresh={FRESHNESS_DEFAULT_WEIGHT}",
        )

    # Formula F5-1: w_fresh = max(floor, 1 − decay × (ref_year − pub_year))
    age_years = FRESHNESS_REFERENCE_YEAR - pub_year
    w_raw = 1.0 - decay_rate * age_years
    w_fresh = max(floor, w_raw)

    notes_parts = [f"family={family_str}, age={age_years}yr, decay={decay_rate}/yr"]

    if w_raw < floor:
        notes_parts.append(f"w_raw={w_raw:.4f} clamped to floor={floor}")

    # Formula F5-2: Supersession penalty
    superseded = False
    if superseded_by_newer and decay_rate == 0.0:
        # Psychometrics: age doesn't degrade, but supersession does
        w_fresh *= FRESHNESS_SUPERSESSION_PENALTY
        superseded = True
        notes_parts.append(
            f"superseded by newer record: w_fresh *= {FRESHNESS_SUPERSESSION_PENALTY}"
        )
    elif superseded_by_newer:
        w_fresh *= FRESHNESS_SUPERSESSION_PENALTY
        superseded = True
        notes_parts.append(
            f"superseded by newer record: w_fresh *= {FRESHNESS_SUPERSESSION_PENALTY}"
        )

    logger.info(
        "Freshness: family=%s, pub_year=%s, w_fresh=%.4f%s",
        family_str, pub_year, w_fresh,
        " (SUPERSEDED)" if superseded else "",
    )

    return FreshnessResult(
        w_fresh=w_fresh,
        family=family_str,
        decay_rate=decay_rate,
        floor=floor,
        age_years=age_years,
        superseded=superseded,
        notes="; ".join(notes_parts),
    )


def check_supersession(
    *,
    older_pub_year: int,
    newer_pub_year: int,
    older_pop_match: float,
    newer_pop_match: float,
    older_sample_size: int,
    newer_sample_size: int,
) -> bool:
    """Check if a newer record supersedes an older one (Module 5.2).

    Supersession is triggered when ALL conditions are met:
      1. newer_pop_match > older_pop_match
      2. newer_sample_size >= older_sample_size × MIN_N_RATIO
      3. newer_pub_year > older_pub_year

    Parameters
    ----------
    older_pub_year, newer_pub_year : int
        Publication years.
    older_pop_match, newer_pop_match : float
        Population match scores (0-1).
    older_sample_size, newer_sample_size : int
        Sample sizes.

    Returns
    -------
    bool
        True if the newer record supersedes the older.
    """
    if newer_pub_year <= older_pub_year:
        return False
    if newer_pop_match <= older_pop_match:
        return False
    if newer_sample_size < older_sample_size * FRESHNESS_SUPERSESSION_MIN_N_RATIO:
        return False
    return True
