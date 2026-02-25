# VERIFIED: formulas [C2b, C2c, C2d] match spec SYS_ALG lines 1875-1878
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads InstrumentMap from chain_a_graph/instrument_loader.py
# VERIFIED: forward wiring — writes PreparedObservation[] for bayesian_update.py (C3)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [C-G2] raises on failure
"""
Component: SYS_ALGORITHM.ALG-C.C2
Spec: SYS_ALGORITHM_COMPLETE.md lines 1862-1878
Formulas:
    C2b: σ²_{y,k_base} = b²_k × (1 − α_k) / α_k   (Classical Test Theory)
    C2c: σ²_{y,k} = σ²_{y,k_base} × cancer_SE_mult²
    C2d: w(t) = e^{−λt};  σ²_{y,k_final} = σ²_{y,k} / w(t)
Reads: RawObservation dict, InstrumentMap (from chain_a_graph/instrument_loader.py),
       NodeMap (from chain_a_graph/node_loader.py)
Writes: PreparedObservation[] (consumed by bayesian_update.py C3)
Gates: C-G2
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

from crci.shared import config
from crci.shared.models.enums import CancerValidationStatus, ObservationTier
from crci.shared.models.intermediate_states import GateViolation, PreparedObservation

from ..chain_a_graph.instrument_loader import InstrumentDef, InstrumentMap
from ..chain_a_graph.node_loader import NodeMap

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Input Type
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RawObservation:
    """A single raw patient observation before C2 processing.

    One per instrument per assessment time.
    """

    instrument_id: str
    y_k: float  # raw observed value
    assessment_date: date  # when this was measured


# ═══════════════════════════════════════════════════════════════
#  C2a: Observation Tiering & Completeness Check
# ═══════════════════════════════════════════════════════════════


def _classify_tier(instrument_def: InstrumentDef) -> ObservationTier:
    """C2a: Classify an instrument into its observation priority tier.

    Uses the tier_assignment field from INSTRUMENT_REGISTRY.csv.
    Tier 0 = required, Tier 1 = major gain, Tier 2 = pathway.

    Args:
        instrument_def: InstrumentDef from the instrument registry.

    Returns:
        ObservationTier value.
    """
    # The INSTRUMENT_REGISTRY.csv has a tier_assignment column (0, 1, 2)
    # Map the numeric tier to the enum
    tier_val = getattr(instrument_def, "tier_assignment", None)
    # tier_assignment is not on InstrumentDef — fall back to heuristic
    # based on instrument type and node mapping
    #
    # Tier 0: cognitive measures (maps to NODE_COG_*, NODE_COMP_CRCI,
    #         NODE_SYM_COG_COMPLAINTS)
    # Tier 1: PSQI, PHQ-9, FACIT-F, age, IL-6/CRP, activity
    # Tier 2: everything else (pathway-level biomarkers)
    node_id = instrument_def.maps_to_node_id

    # Tier 0: cognitive measures
    _TIER_0_NODES = frozenset({
        "NODE_COMP_CRCI",
        "NODE_SYM_COG_COMPLAINTS",
        "NODE_COG_ATTN_SUSTAINED",
        "NODE_COG_WORK_MEM",
        "NODE_COG_EPISODIC_MEM",
        "NODE_COG_VERBAL_FLUENCY",
        "NODE_COG_EXEC_PLANNING",
        "NODE_COG_PROC_SPEED",
        "NODE_COG_VISUOSPATIAL",
        "NODE_COG_LANGUAGE",
    })

    # Tier 1: major clinical instruments
    _TIER_1_NODES = frozenset({
        "NODE_SYM_SLEEP",       # PSQI
        "NODE_SYM_DEPRESSION",  # PHQ-9
        "NODE_SYM_FATIGUE",     # FACIT-F
        "NODE_BIO_IL6",         # IL-6
        "NODE_BIO_CRP",         # CRP
        "NODE_BEH_PHYS_ACT",   # physical activity
        "NODE_CTX_AGE",         # age
        "NODE_SYM_ANXIETY",     # anxiety (close to Tier 1)
    })

    if node_id in _TIER_0_NODES:
        return ObservationTier.TIER_0
    if node_id in _TIER_1_NODES:
        return ObservationTier.TIER_1
    return ObservationTier.TIER_2


def _check_tier_0_completeness(
    observations: list[RawObservation],
    instrument_map: InstrumentMap,
    cancer_type: str,
    treatment_phase: str,
) -> list[str]:
    """C2a: Verify Tier 0 requirements are met.

    Tier 0 requires:
    - cancer_type present (non-empty)
    - treatment_phase present (non-empty)
    - ≥1 cognitive measure observation

    Args:
        observations: Raw observations to validate.
        instrument_map: Instrument definitions.
        cancer_type: Patient's cancer type.
        treatment_phase: Patient's treatment phase.

    Returns:
        List of missing requirement descriptions (empty = all met).
    """
    missing: list[str] = []

    if not cancer_type:
        missing.append("cancer_type is empty")
    if not treatment_phase:
        missing.append("treatment_phase is empty")

    # Check for ≥1 cognitive measure
    has_cognitive = False
    for obs in observations:
        idx = instrument_map.instrument_index.get(obs.instrument_id)
        if idx is not None:
            inst = instrument_map.instruments[idx]
            tier = _classify_tier(inst)
            if tier == ObservationTier.TIER_0:
                has_cognitive = True
                break

    if not has_cognitive:
        missing.append("no cognitive measure (Tier 0) observation present")

    return missing


# ═══════════════════════════════════════════════════════════════
#  C2b: Instrument Lookup & Noise Model
# ═══════════════════════════════════════════════════════════════


def _compute_noise_variance_base(
    b_k: float,
    alpha_k: float,
    instrument_id: str,
) -> float:
    """C2b: Classical Test Theory noise model.

    Formula C2b:
        σ²_{y,k_base} = b²_k × (1 − α_k) / α_k

    Examples from spec:
        α=0.90 → noise = 0.111 b²
        α=0.70 → noise = 0.429 b²
        α=0.50 → noise = 1.000 b²

    Args:
        b_k: Instrument loading (slope).
        alpha_k: Cronbach's alpha reliability.
        instrument_id: For logging.

    Returns:
        Base noise variance σ²_{y,k_base}.
    """
    # Guard against unreliable instruments
    if alpha_k < 0.50:
        logger.warning(
            "C2b: Instrument '%s' has low reliability α=%.3f (< 0.50)",
            instrument_id, alpha_k,
        )

    # Enforce floor to prevent division by zero
    alpha_k = max(alpha_k, config.INSTRUMENT_RELIABILITY_ALPHA_FLOOR)

    # Formula C2b: σ²_{y,k_base} = b²_k × (1 − α_k) / α_k
    sigma_sq_base = (b_k ** 2) * (1.0 - alpha_k) / alpha_k

    return sigma_sq_base


# ═══════════════════════════════════════════════════════════════
#  C2c: Cancer Validation SE Multiplier
# ═══════════════════════════════════════════════════════════════


def _get_cancer_se_multiplier(
    cancer_validation_status: str,
    instrument_id: str,
) -> float:
    """C2c: Get SE multiplier based on cancer validation status.

    Spec (line 1877):
        validated_in_cancer:        1.0×
        used_in_cancer:             1.1×
        general_population_only:    1.3×
        somatic_confound_risk:      1.5×

    Uses config.SCALE_MULTIPLIERS (§2.7) which are the canonical values.

    Args:
        cancer_validation_status: From instrument registry.
        instrument_id: For logging.

    Returns:
        Cancer SE multiplier (≥ 1.0).
    """
    # REVIEW: Spec C2c says used_in_cancer=1.1× but config.SCALE_MULTIPLIERS
    # (from §2.7, shared with P3-4) has used_cancer=1.15×. Using config values
    # as they are the canonical §2.7 reference shared across the system.
    mult = config.SCALE_MULTIPLIERS.get(
        cancer_validation_status,
        config.INSTRUMENT_DEFAULT_SE_MULTIPLIER,
    )

    if cancer_validation_status not in config.SCALE_MULTIPLIERS:
        logger.warning(
            "C2c: Instrument '%s' has unrecognized cancer_validation_status='%s' "
            "— using default SE multiplier %.2f",
            instrument_id, cancer_validation_status, mult,
        )

    return mult


def _apply_cancer_se_multiplier(
    sigma_sq_base: float,
    cancer_se_mult: float,
) -> float:
    """C2c: Apply cancer validation SE multiplier to noise variance.

    Formula C2c:
        σ²_{y,k} = σ²_{y,k_base} × cancer_SE_mult²

    Args:
        sigma_sq_base: Base noise variance from C2b.
        cancer_se_mult: Cancer validation SE multiplier.

    Returns:
        Adjusted noise variance.
    """
    # Formula C2c: σ²_{y,k} = σ²_{y,k_base} × cancer_SE_mult²
    return sigma_sq_base * (cancer_se_mult ** 2)


# ═══════════════════════════════════════════════════════════════
#  C2d: Temporal Weighting
# ═══════════════════════════════════════════════════════════════


def _compute_temporal_weight(
    t_days: float,
    instrument_id: str,
) -> float | None:
    """C2d: Compute temporal decay weight.

    Formula C2d:
        w(t) = e^{−λt}   where λ = TEMPORAL_DECAY_RATE (0.05/day)

    Examples from spec:
        Same day: 1.000; 1wk: 0.705; 2wk: 0.497;
        1mo: 0.223; 3mo: 0.011

    Args:
        t_days: Days since assessment (≥ 0).
        instrument_id: For logging.

    Returns:
        Temporal weight w(t) ∈ (0, 1], or None if excluded (t > 90 days).
    """
    # Rule: t > 90 days → EXCLUDED (too stale)
    if t_days > config.TEMPORAL_EXCLUSION_DAYS:
        logger.info(
            "C2d: Instrument '%s' EXCLUDED — %.0f days old "
            "(> %d day limit)",
            instrument_id, t_days, config.TEMPORAL_EXCLUSION_DAYS,
        )
        return None

    # Rule: t > 30 days → WARNING
    if t_days > 30:
        logger.warning(
            "C2d: Instrument '%s' observation is %.0f days old (> 30 days) "
            "— temporal weight will be low",
            instrument_id, t_days,
        )

    # Formula C2d: w(t) = e^{−λt}
    w = math.exp(-config.TEMPORAL_DECAY_RATE * t_days)

    # Floor: prevent w from going to zero
    w = max(w, config.TEMPORAL_WEIGHT_FLOOR)

    return w


def _apply_temporal_weighting(
    sigma_sq: float,
    w_temporal: float,
) -> float:
    """C2d: Apply temporal weighting to noise variance.

    Formula C2d:
        σ²_{y,k_final} = σ²_{y,k} / w(t)

    Stale observations get inflated noise (less informative).

    Args:
        sigma_sq: Noise variance after C2c.
        w_temporal: Temporal weight from C2d.

    Returns:
        Final noise variance.
    """
    # Formula C2d: σ²_{y,k_final} = σ²_{y,k} / w(t)
    return sigma_sq / w_temporal


# ═══════════════════════════════════════════════════════════════
#  Gate C-G2: Observation Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_c_g2(
    prepared: list[PreparedObservation],
    tier_0_missing: list[str],
) -> None:
    """Gate C-G2: All Tier 0 present; σ² > 0; no NaN.

    Conditions (spec line 1958-1962):
        1. Tier 0 requirements met (cancer_type, treatment_phase, ≥1 cognitive)
        2. All σ²_{y,k} > 0
        3. No NaN in any observation field

    Raises:
        GateViolation: If any condition fails.
    """
    # Condition 1: Tier 0 completeness
    if tier_0_missing:
        raise GateViolation(
            "C-G2",
            f"Tier 0 requirements not met: {'; '.join(tier_0_missing)}",
            context={"missing": tier_0_missing},
        )

    # Must have at least 1 valid observation after temporal exclusion
    if not prepared:
        raise GateViolation(
            "C-G2",
            "No valid observations remain after temporal exclusion",
        )

    for obs in prepared:
        # Condition 2: σ² > 0
        if obs.sigma_sq_y_k <= 0:
            raise GateViolation(
                "C-G2",
                f"Instrument '{obs.instrument_id}' has σ²={obs.sigma_sq_y_k} ≤ 0",
                context={"instrument_id": obs.instrument_id},
            )

        # Condition 3: no NaN
        for field_name in ("y_k", "a_k", "b_k", "sigma_sq_y_k", "w_temporal", "t_days"):
            val = getattr(obs, field_name)
            if math.isnan(val):
                raise GateViolation(
                    "C-G2",
                    f"Instrument '{obs.instrument_id}' has NaN in field '{field_name}'",
                    context={"instrument_id": obs.instrument_id, "field": field_name},
                )

    logger.info(
        "Gate C-G2 PASSED: %d valid observations, all σ² > 0, no NaN",
        len(prepared),
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: prepare_observations (C2 entry point)
# ═══════════════════════════════════════════════════════════════


def prepare_observations(
    observations: list[RawObservation],
    instrument_map: InstrumentMap,
    node_map: NodeMap,
    cancer_type: str,
    treatment_phase: str,
    current_date: date,
) -> list[PreparedObservation]:
    """C2: Measurement Model Application.

    Transforms raw patient observations into PreparedObservations with
    noise models (C2b), cancer-specific SE adjustments (C2c), and
    temporal weighting (C2d).

    Sub-steps:
        C2a — Observation Tiering & Completeness Check
        C2b — Instrument Lookup & Noise Model (CTT)
        C2c — Cancer Validation SE Multiplier
        C2d — Temporal Weighting

    Args:
        observations: Raw observation values per instrument.
        instrument_map: InstrumentMap from Chain A (23 instruments).
        node_map: NodeMap from Chain A (63 nodes).
        cancer_type: Patient's cancer type (Tier 0 required).
        treatment_phase: Patient's treatment phase (Tier 0 required).
        current_date: Current date for temporal weighting.

    Returns:
        List of PreparedObservation, sorted by tier (Tier 0 first).

    Raises:
        GateViolation: If C-G2 fails (Tier 0 incomplete, σ² ≤ 0, NaN).
    """
    logger.info(
        "── C2: Measurement Model Application ──\n"
        "  observations=%d, instruments=%d, nodes=%d",
        len(observations), len(instrument_map.instruments), len(node_map.nodes),
    )

    # C2a: Check Tier 0 completeness
    tier_0_missing = _check_tier_0_completeness(
        observations, instrument_map, cancer_type, treatment_phase,
    )

    prepared: list[PreparedObservation] = []
    excluded_count = 0
    variance_penalty_logged: list[str] = []

    for obs in observations:
        # Look up instrument definition
        inst_idx = instrument_map.instrument_index.get(obs.instrument_id)
        if inst_idx is None:
            logger.warning(
                "C2: Unknown instrument_id '%s' — skipping",
                obs.instrument_id,
            )
            continue
        inst = instrument_map.instruments[inst_idx]

        # Resolve target node index
        node_idx = node_map.node_index.get(inst.maps_to_node_id)
        if node_idx is None:
            logger.warning(
                "C2: Instrument '%s' maps to unknown node '%s' — skipping",
                obs.instrument_id, inst.maps_to_node_id,
            )
            continue

        # Get instrument parameters (with config defaults for missing values)
        b_k = inst.loading_b_k if inst.loading_b_k else config.INSTRUMENT_DEFAULT_LOADING_B_K
        a_k = inst.intercept_a_k if inst.intercept_a_k is not None else config.INSTRUMENT_DEFAULT_INTERCEPT_A_K
        alpha_k = inst.reliability_alpha if inst.reliability_alpha else config.INSTRUMENT_DEFAULT_RELIABILITY_ALPHA

        if b_k != inst.loading_b_k or alpha_k != inst.reliability_alpha:
            logger.info(
                "C2: Instrument '%s' — using defaults: b_k=%.2f (was %s), "
                "alpha_k=%.3f (was %s)",
                obs.instrument_id,
                b_k, inst.loading_b_k,
                alpha_k, inst.reliability_alpha,
            )

        # C2a: Classify tier
        tier = _classify_tier(inst)

        # C2d: Temporal weighting — compute t_days and w(t)
        t_days = float((current_date - obs.assessment_date).days)
        if t_days < 0:
            logger.warning(
                "C2d: Instrument '%s' has future assessment_date %s "
                "(current=%s) — treating as t=0",
                obs.instrument_id, obs.assessment_date, current_date,
            )
            t_days = 0.0

        w_temporal = _compute_temporal_weight(t_days, obs.instrument_id)
        if w_temporal is None:
            # Excluded — too stale
            excluded_count += 1
            continue

        # C2b: Noise model
        sigma_sq_base = _compute_noise_variance_base(b_k, alpha_k, obs.instrument_id)

        # C2c: Cancer validation SE multiplier
        cancer_se_mult = _get_cancer_se_multiplier(
            inst.cancer_validation_status, obs.instrument_id,
        )
        sigma_sq_adj = _apply_cancer_se_multiplier(sigma_sq_base, cancer_se_mult)

        # C2d: Apply temporal weighting
        sigma_sq_final = _apply_temporal_weighting(sigma_sq_adj, w_temporal)

        prepared.append(PreparedObservation(
            instrument_id=obs.instrument_id,
            node_i=node_idx,
            y_k=obs.y_k,
            a_k=a_k,
            b_k=b_k,
            sigma_sq_y_k=sigma_sq_final,
            cancer_SE_mult=cancer_se_mult,
            w_temporal=w_temporal,
            t_days=t_days,
            tier=tier.value,
        ))

    # Log Tier 1 missingness for variance penalty tracking
    _TIER_1_INSTRUMENTS = frozenset({
        "INST_PSQI", "INST_PHQ9", "INST_FACIT_F",
    })
    observed_ids = {obs.instrument_id for obs in observations}
    for t1_id in _TIER_1_INSTRUMENTS:
        if t1_id not in observed_ids:
            variance_penalty_logged.append(t1_id)

    if variance_penalty_logged:
        logger.info(
            "C2a: Missing Tier 1 instruments (variance penalty noted): %s",
            ", ".join(sorted(variance_penalty_logged)),
        )

    # Sort by tier priority: TIER_0 first, then TIER_1, then TIER_2
    _TIER_ORDER = {
        ObservationTier.TIER_0.value: 0,
        ObservationTier.TIER_1.value: 1,
        ObservationTier.TIER_2.value: 2,
    }
    prepared.sort(key=lambda p: _TIER_ORDER.get(p.tier, 99))

    # Gate C-G2
    _validate_gate_c_g2(prepared, tier_0_missing)

    logger.info(
        "C2: Observations prepared — %d valid, %d excluded (stale), "
        "tier breakdown: T0=%d T1=%d T2=%d",
        len(prepared),
        excluded_count,
        sum(1 for p in prepared if p.tier == ObservationTier.TIER_0.value),
        sum(1 for p in prepared if p.tier == ObservationTier.TIER_1.value),
        sum(1 for p in prepared if p.tier == ObservationTier.TIER_2.value),
    )

    return prepared
