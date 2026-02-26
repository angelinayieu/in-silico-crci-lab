"""
Component: Chain C — Patient State Inference Orchestrator
Spec: SYS_ALGORITHM_COMPLETE.md lines 1400-2000
Reads: FrozenModelState (from chain_b_evidence.frozen_state)
Writes: PatientState (consumed by chain_d_simulation), RawPosterior, LoadedPrior
Gates: C-G1, C-G2, C-G3, C-G4

Provides run_chain_c() as the top-level entry point that orchestrates:
    C1 (prior_loader) → C2 (observation_mapper) → C3 (bayesian_update) → C4 (modifier_application)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crci.algorithm.chain_b_evidence.frozen_state import FrozenModelState
    from crci.algorithm.chain_c_posterior.bayesian_update import RawPosterior
    from crci.algorithm.chain_c_posterior.modifier_application import (
        ModifierRule,
        PatientState,
    )
    from crci.algorithm.chain_c_posterior.observation_mapper import RawObservation
    from crci.algorithm.chain_c_posterior.prior_loader import LoadedPrior
    from crci.shared.models.pathway_types import PathwayDef

logger = logging.getLogger(__name__)


def run_chain_c(
    frozen: FrozenModelState,
    observations: list[RawObservation],
    cancer_type: str,
    treatment_phase: str,
    patient_profile: dict[str, object],
    modifier_rules: list[ModifierRule],
    pathways: list[PathwayDef],
    treatment_regimen: str | None = None,
    current_date: date | None = None,
    context_specs: list | None = None,
) -> tuple[PatientState, RawPosterior, LoadedPrior, None]:
    """Run Chain C: Prior Loading → Observation Mapping → Bayesian Update → Modifier Application.

    Orchestrates C1-C4 in sequence, returning the full set of intermediate
    results needed by downstream chains (D, E, F) and the pipeline script.

    Args:
        frozen: FrozenModelState from Chain B.
        observations: Raw patient observations (may be empty for prior-only).
        cancer_type: Patient's cancer type.
        treatment_phase: Patient's treatment phase.
        patient_profile: Dict of patient attributes for modifier matching.
        modifier_rules: List of ModifierRule from registry.
        pathways: List of PathwayDef from PATHWAY_REGISTRY.csv.
        treatment_regimen: Optional treatment regimen for exact context match.
        current_date: Current date for temporal weighting (defaults to today).
        context_specs: Optional context prior specs for C1.

    Returns:
        Tuple of (PatientState, RawPosterior, LoadedPrior, snapshot_result).
        snapshot_result is None (C5 write_posterior requires a DB session
        and is called separately when persistence is needed).
    """
    if current_date is None:
        current_date = date.today()

    logger.info(
        "═══ Chain C: Patient State Inference ═══\n"
        "  cancer_type=%s, treatment_phase=%s, observations=%d",
        cancer_type, treatment_phase, len(observations),
    )

    # ── C1: Context Matching & Prior Loading ──
    from crci.algorithm.chain_c_posterior.prior_loader import load_prior

    loaded_prior = load_prior(
        frozen=frozen,
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        treatment_regimen=treatment_regimen,
        context_specs=context_specs,
    )
    logger.info(
        "C1 complete: context_key=%s, fallback=%s",
        loaded_prior.context_key,
        loaded_prior.fallback_level,
    )

    # ── C2: Measurement Model Application ──
    from crci.algorithm.chain_c_posterior.observation_mapper import prepare_observations

    prepared_observations = prepare_observations(
        observations=observations,
        instrument_map=frozen.graph.instrument_map,
        node_map=frozen.graph.node_map,
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        current_date=current_date,
    )
    logger.info("C2 complete: %d observations prepared", len(prepared_observations))

    # ── C3: Bayesian State Estimation ──
    from crci.algorithm.chain_c_posterior.bayesian_update import bayesian_update

    raw_posterior = bayesian_update(
        loaded_prior=loaded_prior,
        observations=prepared_observations,
    )
    logger.info(
        "C3 complete: ||θ̂||=%.4f, %d observations fused",
        float(sum(raw_posterior.theta_hat**2) ** 0.5),
        len(raw_posterior.observation_log),
    )

    # ── C4: Effect Modifier Application ──
    from crci.algorithm.chain_c_posterior.modifier_application import apply_modifiers

    patient_state = apply_modifiers(
        raw_posterior=raw_posterior,
        loaded_prior=loaded_prior,
        frozen=frozen,
        patient_profile=patient_profile,
        modifier_rules=modifier_rules,
        pathways=pathways,
    )
    logger.info(
        "C4 complete: %d active pathways, %d modifiers applied",
        sum(1 for p in patient_state.active_pathways if p.is_active),
        len(patient_state.modifier_audit),
    )

    # C5 (write_posterior) is NOT called here — it requires a DB session
    # and is the caller's responsibility when persistence is needed.
    snapshot_result = None

    logger.info("═══ Chain C complete ═══")
    return patient_state, raw_posterior, loaded_prior, snapshot_result
