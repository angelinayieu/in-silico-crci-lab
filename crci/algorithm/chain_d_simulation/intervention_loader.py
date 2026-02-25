# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ActionCatalog, InterventionKernel, DoseBridge,
#           ContraindicationRule ORM tables; SynergyRecord from frozen_state.py
# VERIFIED: forward wiring — writes InterventionDef, DoseResponseSpec, ContraindicationDef,
#           InterventionSet for mc_sampler.py (D1), ranker.py (D4/D5), safety_checker.py (D3)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no formulas (data-loading file)
"""
Component: SYS_ALGORITHM.ALG-D.D0 (Data Loading)
Spec: SYS_ALGORITHM_COMPLETE.md lines 2015-2540 (ALG-D chain card)
      Boundary tables: lines 2500-2508
Formulas: None (data loading + type construction)
Reads: action_catalog_v1 (ORM), intervention_kernels_v1 (ORM),
       dose_bridges_v1 (ORM), contraindication_rules_v1 (ORM),
       SynergyRecord (from FrozenModelState.synergy_records)
Writes: InterventionSet (consumed by mc_sampler.py D1, ranker.py D4/D5,
        safety_checker.py D3)
Gates: None (validation gates are in downstream files)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from crci.shared.models.tables import (
    ActionCatalog,
    ContraindicationRule,
    DoseBridge,
    InterventionKernel,
)

from ..chain_b_evidence.frozen_state import FrozenModelState, SynergyRecord

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Typed Data Structures for ALG-D
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TemporalKernel:
    """Temporal onset/peak/decay profile for one intervention.

    From intervention_kernels_v1 (A32).
    Used by Chain E for trajectory prediction.
    """

    kernel_id: str
    action_id: str
    kernel_family: str  # e.g., "exponential_rise_decay", "step", "linear"
    onset_weeks_min: float
    onset_weeks_max: float
    build_weeks: float
    steady_state_weeks_min: float
    steady_state_weeks_max: float
    decay_half_life_weeks: float
    pathway_specific_onset: dict[str, float]  # pathway_id → onset_weeks override
    source_citation: str


@dataclass(frozen=True)
class DoseResponseSpec:
    """Dose-response bridge for one action → one node.

    From dose_bridges_v1 (C2).
    Used by D5 (dose optimization) and D2 (effect propagation).
    """

    bridge_id: str
    action_id: str
    output_node_id: str | None  # target node in the graph
    maps_to_node_id: str | None  # alternative mapping
    dose_type: str | None
    dose_unit: str | None
    dose_min: float
    dose_max: float | None
    dose_step: float | None
    dose_reference: float  # reference dose for unit-effect
    dose_response_family: str  # "hill", "emax", "linear", "log_linear"
    dose_response_params: dict[str, float]  # E_max, EC50, h for Hill/Emax
    bridge_effect_sign: int  # +1 or -1
    bridge_gain: float  # scaling factor
    bridge_noise_sd: float | None


@dataclass(frozen=True)
class ContraindicationDef:
    """Safety contraindication rule.

    From contraindication_rules_v1 (A10).
    Used by D3 (safety_checker.py).
    """

    rule_id: str
    rule_label: str
    applies_to_type: str  # "action", "action_class", "bundle"
    applies_to_ref: str | None  # specific action_id or class
    severity: str  # "BLOCK", "WARNING", "CAUTION"
    condition_expression: str  # evaluable condition string
    required_inputs: list[str]  # patient attributes needed
    unknown_input_policy: str  # "assume_safe", "assume_unsafe", "skip"
    penalty_spec: dict[str, float] | None  # optional penalty details
    escalation_id: str | None
    rationale: str


@dataclass(frozen=True)
class InterventionDef:
    """Complete intervention definition for simulation.

    Combines action catalog, dose-response, temporal kernel, and contraindications
    into a single object consumed by D1-D6.
    """

    action_id: str
    action_label: str
    action_class: str  # "exercise", "pharmacological", "behavioral", etc.

    # Dose parameters
    dose_type: str
    dose_unit: str | None
    dose_min: float
    dose_max: float
    dose_recommended_start: float
    dose_step: float | None

    # Burden (for SAFE scoring, D4)
    time_cost_min: float
    cognitive_load: float
    logistics_load: float
    overall_burden: float | None
    adherence_rate_default: float | None

    # Evidence
    evidence_basis: str
    evidence_strength: str

    # Linked data (populated during loading)
    dose_bridges: list[DoseResponseSpec] = field(default_factory=list)
    temporal_kernel: TemporalKernel | None = None
    contraindications: list[ContraindicationDef] = field(default_factory=list)


@dataclass
class InterventionSet:
    """Complete loaded intervention data for ALG-D.

    This is the top-level output of intervention_loader.
    Consumed by mc_sampler.py, safety_checker.py, ranker.py.
    """

    interventions: list[InterventionDef]
    intervention_index: dict[str, int]  # action_id → position in list
    synergy_records: list[SynergyRecord]  # from FrozenModelState
    synergy_lookup: dict[tuple[str, str], SynergyRecord]  # (a_id, b_id) → record
    all_contraindications: list[ContraindicationDef]

    @property
    def n_interventions(self) -> int:
        return len(self.interventions)


# ═══════════════════════════════════════════════════════════════
#  Loading Functions
# ═══════════════════════════════════════════════════════════════


def _load_actions(session: Session) -> list[dict[str, object]]:
    """Load active interventions from action_catalog_v1.

    Args:
        session: SQLAlchemy session.

    Returns:
        List of action rows as dicts.
    """
    rows = (
        session.query(
            ActionCatalog.action_id,
            ActionCatalog.action_label,
            ActionCatalog.action_class,
            ActionCatalog.dose_type,
            ActionCatalog.dose_unit,
            ActionCatalog.dose_semantics,
            ActionCatalog.dose_min,
            ActionCatalog.dose_max,
            ActionCatalog.dose_recommended_start,
            ActionCatalog.dose_step,
            ActionCatalog.time_cost_min_default,
            ActionCatalog.cognitive_load_default,
            ActionCatalog.logistics_load_default,
            ActionCatalog.overall_burden_default,
            ActionCatalog.adherence_rate_default,
            ActionCatalog.evidence_basis,
            ActionCatalog.evidence_strength,
        )
        .filter(ActionCatalog.active == 1)
        .all()
    )

    actions = []
    for r in rows:
        actions.append({
            "action_id": r.action_id,
            "action_label": r.action_label,
            "action_class": r.action_class,
            "dose_type": r.dose_type,
            "dose_unit": r.dose_unit,
            "dose_min": r.dose_min,
            "dose_max": r.dose_max,
            "dose_recommended_start": r.dose_recommended_start,
            "dose_step": r.dose_step,
            "time_cost_min": r.time_cost_min_default,
            "cognitive_load": r.cognitive_load_default,
            "logistics_load": r.logistics_load_default,
            "overall_burden": r.overall_burden_default,
            "adherence_rate_default": r.adherence_rate_default,
            "evidence_basis": r.evidence_basis,
            "evidence_strength": r.evidence_strength,
        })

    logger.info("D0: Loaded %d active actions from action_catalog_v1", len(actions))
    return actions


def _load_temporal_kernels(session: Session) -> dict[str, TemporalKernel]:
    """Load temporal kernels from intervention_kernels_v1.

    Args:
        session: SQLAlchemy session.

    Returns:
        Dict: action_id → TemporalKernel.
    """
    rows = (
        session.query(InterventionKernel)
        .filter(InterventionKernel.active == 1)
        .all()
    )

    kernels: dict[str, TemporalKernel] = {}
    for r in rows:
        pathway_onset = {}
        if r.pathway_specific_onset_json:
            try:
                pathway_onset = (
                    json.loads(r.pathway_specific_onset_json)
                    if isinstance(r.pathway_specific_onset_json, str)
                    else r.pathway_specific_onset_json
                )
            except (json.JSONDecodeError, TypeError):
                pass

        kernel = TemporalKernel(
            kernel_id=r.kernel_id,
            action_id=r.action_id,
            kernel_family=r.kernel_family,
            onset_weeks_min=r.onset_weeks_min,
            onset_weeks_max=r.onset_weeks_max,
            build_weeks=r.build_weeks,
            steady_state_weeks_min=r.steady_state_weeks_min,
            steady_state_weeks_max=r.steady_state_weeks_max,
            decay_half_life_weeks=r.decay_half_life_weeks,
            pathway_specific_onset=pathway_onset,
            source_citation=r.source_citation,
        )
        kernels[r.action_id] = kernel

    logger.info(
        "D0: Loaded %d temporal kernels from intervention_kernels_v1",
        len(kernels),
    )
    return kernels


def _load_dose_bridges(session: Session) -> dict[str, list[DoseResponseSpec]]:
    """Load dose-response bridges from dose_bridges_v1.

    Args:
        session: SQLAlchemy session.

    Returns:
        Dict: action_id → list of DoseResponseSpec.
    """
    rows = (
        session.query(DoseBridge)
        .filter(DoseBridge.active == 1)
        .all()
    )

    bridges: dict[str, list[DoseResponseSpec]] = {}
    for r in rows:
        params = {}
        if r.dose_response_params_json:
            try:
                params = (
                    json.loads(r.dose_response_params_json)
                    if isinstance(r.dose_response_params_json, str)
                    else r.dose_response_params_json
                )
            except (json.JSONDecodeError, TypeError):
                pass

        spec = DoseResponseSpec(
            bridge_id=r.bridge_id,
            action_id=r.action_id,
            output_node_id=r.output_node_id,
            maps_to_node_id=r.maps_to_node_id,
            dose_type=r.dose_type,
            dose_unit=r.dose_unit,
            dose_min=r.dose_min or 0.0,
            dose_max=r.dose_max,
            dose_step=r.dose_step,
            dose_reference=r.dose_reference,
            dose_response_family=r.dose_response_family,
            dose_response_params=params,
            bridge_effect_sign=r.bridge_effect_sign,
            bridge_gain=r.bridge_gain,
            bridge_noise_sd=r.bridge_noise_sd,
        )
        bridges.setdefault(r.action_id, []).append(spec)

    total = sum(len(v) for v in bridges.values())
    logger.info(
        "D0: Loaded %d dose bridges for %d actions from dose_bridges_v1",
        total, len(bridges),
    )
    return bridges


def _load_contraindications(session: Session) -> list[ContraindicationDef]:
    """Load contraindication rules from contraindication_rules_v1.

    Args:
        session: SQLAlchemy session.

    Returns:
        List of ContraindicationDef.
    """
    rows = (
        session.query(ContraindicationRule)
        .filter(ContraindicationRule.active == 1)
        .all()
    )

    contras: list[ContraindicationDef] = []
    for r in rows:
        required_inputs: list[str] = []
        if r.required_inputs_json:
            try:
                required_inputs = (
                    json.loads(r.required_inputs_json)
                    if isinstance(r.required_inputs_json, str)
                    else r.required_inputs_json
                )
            except (json.JSONDecodeError, TypeError):
                pass

        penalty_spec: dict[str, float] | None = None
        if r.penalty_spec_json:
            try:
                penalty_spec = (
                    json.loads(r.penalty_spec_json)
                    if isinstance(r.penalty_spec_json, str)
                    else r.penalty_spec_json
                )
            except (json.JSONDecodeError, TypeError):
                pass

        contras.append(ContraindicationDef(
            rule_id=r.rule_id,
            rule_label=r.rule_label,
            applies_to_type=r.applies_to_type,
            applies_to_ref=r.applies_to_ref,
            severity=r.severity,
            condition_expression=r.condition_expression,
            required_inputs=required_inputs,
            unknown_input_policy=r.unknown_input_policy,
            penalty_spec=penalty_spec,
            escalation_id=r.escalation_id,
            rationale=r.rationale,
        ))

    logger.info(
        "D0: Loaded %d contraindication rules from contraindication_rules_v1",
        len(contras),
    )
    return contras


def _build_synergy_lookup(
    synergy_records: list[SynergyRecord],
) -> dict[tuple[str, str], SynergyRecord]:
    """Build bidirectional synergy lookup from FrozenModelState records.

    Args:
        synergy_records: SynergyRecord list from FrozenModelState.

    Returns:
        Dict: (action_a_id, action_b_id) → SynergyRecord (both directions).
    """
    lookup: dict[tuple[str, str], SynergyRecord] = {}
    for sr in synergy_records:
        lookup[(sr.action_a_id, sr.action_b_id)] = sr
        lookup[(sr.action_b_id, sr.action_a_id)] = sr

    logger.info(
        "D0: Built synergy lookup — %d records, %d lookup entries",
        len(synergy_records), len(lookup),
    )
    return lookup


# ═══════════════════════════════════════════════════════════════
#  Top-Level: load_interventions (D0 entry point)
# ═══════════════════════════════════════════════════════════════


def load_interventions(
    session: Session,
    frozen: FrozenModelState,
) -> InterventionSet:
    """D0: Load all intervention data for ALG-D simulation.

    Reads from 4 database tables and assembles typed data structures:
    - action_catalog_v1 → InterventionDef (core attributes + burden)
    - intervention_kernels_v1 → TemporalKernel (onset/peak/decay)
    - dose_bridges_v1 → DoseResponseSpec (Hill/Emax params)
    - contraindication_rules_v1 → ContraindicationDef (safety rules)

    Synergy data comes from FrozenModelState.synergy_records (Chain B).

    Args:
        session: SQLAlchemy session for database reads.
        frozen: FrozenModelState containing synergy_records.

    Returns:
        InterventionSet with all loaded data for D1-D6.
    """
    logger.info("── D0: Intervention Loading ──")

    # Load from database tables
    action_rows = _load_actions(session)
    kernels = _load_temporal_kernels(session)
    dose_bridges = _load_dose_bridges(session)
    all_contras = _load_contraindications(session)

    # Build action_id → contraindication mapping
    contra_by_action: dict[str, list[ContraindicationDef]] = {}
    for c in all_contras:
        if c.applies_to_ref:
            contra_by_action.setdefault(c.applies_to_ref, []).append(c)

    # Assemble InterventionDef objects
    interventions: list[InterventionDef] = []
    intervention_index: dict[str, int] = {}

    for i, row in enumerate(action_rows):
        action_id = row["action_id"]

        intervention = InterventionDef(
            action_id=action_id,
            action_label=row["action_label"],
            action_class=row["action_class"],
            dose_type=row["dose_type"],
            dose_unit=row["dose_unit"],
            dose_min=row["dose_min"],
            dose_max=row["dose_max"],
            dose_recommended_start=row["dose_recommended_start"],
            dose_step=row["dose_step"],
            time_cost_min=row["time_cost_min"],
            cognitive_load=row["cognitive_load"],
            logistics_load=row["logistics_load"],
            overall_burden=row["overall_burden"],
            adherence_rate_default=row["adherence_rate_default"],
            evidence_basis=row["evidence_basis"],
            evidence_strength=row["evidence_strength"],
            dose_bridges=dose_bridges.get(action_id, []),
            temporal_kernel=kernels.get(action_id),
            contraindications=contra_by_action.get(action_id, []),
        )

        interventions.append(intervention)
        intervention_index[action_id] = i

    # Build synergy lookup from FrozenModelState
    synergy_lookup = _build_synergy_lookup(frozen.synergy_records)

    result = InterventionSet(
        interventions=interventions,
        intervention_index=intervention_index,
        synergy_records=frozen.synergy_records,
        synergy_lookup=synergy_lookup,
        all_contraindications=all_contras,
    )

    logger.info(
        "D0: Intervention loading complete — "
        "%d interventions, %d dose bridges, %d kernels, "
        "%d contraindication rules, %d synergy pairs",
        result.n_interventions,
        sum(len(iv.dose_bridges) for iv in interventions),
        sum(1 for iv in interventions if iv.temporal_kernel is not None),
        len(all_contras),
        len(frozen.synergy_records),
    )

    return result
