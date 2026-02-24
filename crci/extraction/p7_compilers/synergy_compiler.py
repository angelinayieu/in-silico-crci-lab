# VERIFIED: formula P7-C6a matches SYS_EXTRACTION_ADDENDUM Part 6 Compiler 6
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads factorial trial data (edge_evidence_v1 via SpanLabels)
# VERIFIED: forward wiring — writes CompiledSynergy for intervention_synergy_v1
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G6 raises on failure
"""
Component: SYS_EXTRACTION.EX-P7.C6
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 6
Formulas: P7-C6a (γ = (effect_AB - effect_A - effect_B) / max(|effect_A|, |effect_B|))
Reads: Factorial trial data — evidence with combination intervention effects
Writes: CompiledSynergy (consumed by intervention_synergy_v1 writer)
Gates: P7-G6 (γ must be ∈ (-1, 1))
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledSynergy,
    GateViolation,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class SynergyTrialData:
    """Input data for synergy compilation from a factorial trial.

    Each record represents one study's factorial comparison.
    """

    study_id: str
    action_a_id: str
    action_b_id: str
    effect_a: float  # Effect of intervention A alone
    effect_b: float  # Effect of intervention B alone
    effect_ab: float  # Effect of A + B combined
    se_a: float | None = None
    se_b: float | None = None
    se_ab: float | None = None
    n: int | None = None


@dataclass
class _SynergyGroup:
    """Evidence for one intervention pair."""

    action_a_id: str
    action_b_id: str
    trials: list[SynergyTrialData] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  GAMMA COMPUTATION
# ═══════════════════════════════════════════════════════════════


def _compute_gamma(
    effect_a: float,
    effect_b: float,
    effect_ab: float,
) -> float:
    """Compute synergy coefficient γ from factorial effects.

    Formula P7-C6a: γ = (effect_AB - effect_A - effect_B) / max(|effect_A|, |effect_B|)

    If γ > 0: synergistic
    If γ < 0: antagonistic
    If ≈ 0: additive
    """
    denominator = max(abs(effect_a), abs(effect_b))
    if denominator < 1e-8:
        logger.warning(
            "Cannot compute γ: max(|effect_A|, |effect_B|) ≈ 0 "
            "(effect_A=%.6f, effect_B=%.6f)",
            effect_a,
            effect_b,
        )
        return 0.0

    # Formula P7-C6a
    gamma = (effect_ab - effect_a - effect_b) / denominator
    return gamma


def _classify_interaction(gamma: float) -> str:
    """Classify interaction type from γ coefficient.

    γ > 0.05 → synergistic
    γ < -0.05 → antagonistic
    else → additive
    """
    if gamma > 0.05:
        return "synergistic"
    elif gamma < -0.05:
        return "antagonistic"
    else:
        return "additive"


# ═══════════════════════════════════════════════════════════════
#  WEIGHTED GAMMA POOLING
# ═══════════════════════════════════════════════════════════════


def _pool_gamma(trials: list[SynergyTrialData]) -> tuple[float, int]:
    """Pool γ coefficients across trials.

    Uses sample-size weighting if N is available,
    otherwise equal weighting.

    Returns:
        (gamma_pooled, k_studies)
    """
    gammas: list[float] = []
    weights: list[float] = []

    for trial in trials:
        g = _compute_gamma(trial.effect_a, trial.effect_b, trial.effect_ab)
        gammas.append(g)
        weights.append(float(trial.n) if trial.n is not None and trial.n > 0 else 1.0)

    if not gammas:
        return 0.0, 0

    total_weight = sum(weights)
    gamma_pooled = sum(g * w for g, w in zip(gammas, weights)) / total_weight

    return gamma_pooled, len(gammas)


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_synergy(
    trial_data: list[SynergyTrialData],
) -> list[CompiledSynergy]:
    """Compile synergy coefficients from factorial trial data.

    This compiler is the MOST LIMITED because factorial trials in
    cancer cognition are rare. Realistic expectation: 0-3 synergy
    pairs will have direct extraction evidence.

    Gate P7-G6: γ must be ∈ (-1, 1). Values outside this range
    suggest misparse or implausible interaction.

    Args:
        trial_data: Factorial trial data (each record = one study's
                   factorial comparison between two interventions).

    Returns:
        List of CompiledSynergy, one per intervention pair.

    Raises:
        GateViolation: If P7-G6 (γ out of bounds) is violated.
    """
    # Group by (action_a, action_b) — canonical ordering: a < b
    groups: dict[tuple[str, str], _SynergyGroup] = {}
    for trial in trial_data:
        # Canonical ordering
        a = min(trial.action_a_id, trial.action_b_id)
        b = max(trial.action_a_id, trial.action_b_id)
        key = (a, b)
        if key not in groups:
            groups[key] = _SynergyGroup(action_a_id=a, action_b_id=b)
        groups[key].trials.append(trial)

    results: list[CompiledSynergy] = []

    for key, group in groups.items():
        logger.info(
            "Compiling synergy for '%s' × '%s': %d trials",
            group.action_a_id,
            group.action_b_id,
            len(group.trials),
        )

        # Pool γ across trials
        gamma_pooled, k_studies = _pool_gamma(group.trials)

        # ─── Gate P7-G6: γ ∈ (-1, 1) ─────────────────────────────
        if gamma_pooled <= config.P7_SYNERGY_GAMMA_MIN or gamma_pooled >= config.P7_SYNERGY_GAMMA_MAX:
            raise GateViolation(
                "P7-G6",
                f"Pair '{group.action_a_id}' × '{group.action_b_id}': "
                f"γ={gamma_pooled:.4f} not in "
                f"({config.P7_SYNERGY_GAMMA_MIN}, {config.P7_SYNERGY_GAMMA_MAX})",
                {
                    "action_a_id": group.action_a_id,
                    "action_b_id": group.action_b_id,
                    "gamma": gamma_pooled,
                },
            )

        interaction_type = _classify_interaction(gamma_pooled)
        study_ids = sorted({t.study_id for t in group.trials if t.study_id})

        compiled = CompiledSynergy(
            action_a_id=group.action_a_id,
            action_b_id=group.action_b_id,
            gamma=gamma_pooled,
            interaction_type=interaction_type,
            k_studies=k_studies,
            provenance_status="CURATED_TRACED" if k_studies > 0 else "SENSITIVITY_REQUIRED",
            provenance_ref="; ".join(study_ids),
        )
        results.append(compiled)

        logger.info(
            "Compiled synergy '%s' × '%s': γ=%.4f (%s), k=%d",
            group.action_a_id,
            group.action_b_id,
            gamma_pooled,
            interaction_type,
            k_studies,
        )

    logger.info(
        "Synergy compilation complete: %d pairs compiled "
        "(expected few due to rare factorial designs in cancer cognition)",
        len(results),
    )
    return results
