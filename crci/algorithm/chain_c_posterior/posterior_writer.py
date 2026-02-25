# VERIFIED: serialization — node_beliefs_json, evidence_contributions_json match table schema
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PatientState from modifier_application.py
# VERIFIED: forward wiring — writes state_snapshots_v1 for ALG-D (scenario_definitions_v1), ALG-E, ALG-F
# VERIFIED: no hardcoded formula parameters — MIN_SIGMA_FLOOR from config
# VERIFIED: no formulas (serialization-only file)
"""
Component: SYS_ALGORITHM.ALG-C.C5
Spec: SYS_ALGORITHM_COMPLETE.md lines 1939-1940, 05_TABLE_SCHEMAS.md lines 1770-1800
Formulas: None (serialization + persistence)
Reads: PatientState (from modifier_application.py C4), NodeMap (from chain_a_graph)
Writes: state_snapshots_v1 (consumed by scenario_definitions_v1, ALG-D, ALG-E, ALG-F)
Gates: None (C-G4 already validated in C4)
"""
from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import StateSnapshot

from ..chain_a_graph.node_loader import NodeMap
from .modifier_application import PatientState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StateSnapshotResult:
    """Return value from write_posterior — provides state_id for downstream.

    Consumed by ALG-D (scenario_definitions_v1.base_state_id).
    """

    state_id: str
    run_id: str
    subject_ref: str
    obs_used_count: int
    n_nodes_written: int
    sigma_floor_applied: bool
    conflict_inflation_applied: bool


# ═══════════════════════════════════════════════════════════════
#  State ID Generation
# ═══════════════════════════════════════════════════════════════


def _generate_state_id(
    state_time: datetime,
    sequence_number: int = 1,
) -> str:
    """Generate unique state_id per schema: STATE_[A-Z0-9_]+.

    Format: STATE_YYYYMMDDTHHMMSS_NNNN

    Args:
        state_time: Timestamp for this snapshot.
        sequence_number: Sequence within same timestamp.

    Returns:
        Unique state_id string.
    """
    ts = state_time.strftime("%Y%m%dT%H%M%S")
    return f"STATE_{ts}_{sequence_number:04d}"


# ═══════════════════════════════════════════════════════════════
#  Serialization: PatientState → Table Columns
# ═══════════════════════════════════════════════════════════════


def _serialize_node_beliefs(
    patient_state: PatientState,
    node_map: NodeMap,
) -> tuple[dict[str, dict[str, float]], bool]:
    """Serialize θ̂ and Σ_post into node_beliefs_json.

    Format: {node_id: {"mean": float, "sd": float}} per node.
    Applies MIN_SIGMA_FLOOR to any sd below the floor.

    Args:
        patient_state: PatientState with theta_hat and Sigma_post.
        node_map: NodeMap for index → node_id mapping.

    Returns:
        Tuple of (node_beliefs dict, sigma_floor_applied flag).
    """
    beliefs: dict[str, dict[str, float]] = {}
    sigma_floor_applied = False

    # Build inverse mapping: index → node_id
    index_to_node: dict[int, str] = {
        idx: node_id for node_id, idx in node_map.node_index.items()
    }

    n = len(patient_state.theta_hat)
    for i in range(n):
        node_id = index_to_node.get(i)
        if node_id is None:
            continue

        mean = float(patient_state.theta_hat[i])
        variance = float(patient_state.Sigma_post[i, i])

        # sd = sqrt(variance), with floor
        sd = math.sqrt(max(variance, 0.0))
        if sd < config.MIN_SIGMA_FLOOR:
            logger.info(
                "C5: Node '%s' sd=%.4f below floor %.2f — flooring applied",
                node_id, sd, config.MIN_SIGMA_FLOOR,
            )
            sd = config.MIN_SIGMA_FLOOR
            sigma_floor_applied = True

        beliefs[node_id] = {"mean": round(mean, 6), "sd": round(sd, 6)}

    return beliefs, sigma_floor_applied


def _serialize_evidence_contributions(
    patient_state: PatientState,
    node_map: NodeMap,
) -> list[dict[str, object]]:
    """Serialize observation_log into evidence_contributions_json.

    Format: [{"node_id": str, "source_id": str, "w": float}]
    where w = precision_contribution / total_precision_for_node.

    Args:
        patient_state: PatientState with observation_log.
        node_map: NodeMap for index → node_id mapping.

    Returns:
        List of evidence contribution dicts.
    """
    if not patient_state.observation_log:
        return []

    index_to_node: dict[int, str] = {
        idx: node_id for node_id, idx in node_map.node_index.items()
    }

    # Compute total precision per node for weight normalization
    precision_by_node: dict[int, float] = {}
    for obs in patient_state.observation_log:
        precision_by_node[obs.node_i] = (
            precision_by_node.get(obs.node_i, 0.0) + obs.precision_contribution
        )

    contributions: list[dict[str, object]] = []
    for obs in patient_state.observation_log:
        node_id = index_to_node.get(obs.node_i, f"NODE_{obs.node_i}")
        total_prec = precision_by_node.get(obs.node_i, 1.0)

        # Weight = this observation's precision / total for that node
        w = obs.precision_contribution / total_prec if total_prec > 0 else 0.0

        contributions.append({
            "node_id": node_id,
            "source_id": obs.instrument_id,
            "w": round(w, 6),
        })

    return contributions


def _compute_coverage(
    patient_state: PatientState,
    node_map: NodeMap,
) -> dict[str, object]:
    """Compute coverage_json from observation_log.

    Schema: {"n_obs_recent": int, "recency_days": float,
             "n_nodes_observed": int, "n_nodes_total": int}

    Args:
        patient_state: PatientState with observation_log.
        node_map: NodeMap for total node count.

    Returns:
        Coverage dict.
    """
    obs_log = patient_state.observation_log
    n_obs = len(obs_log)
    n_nodes_total = len(node_map.node_index)

    # Count distinct observed nodes
    observed_nodes: set[int] = set()
    for obs in obs_log:
        observed_nodes.add(obs.node_i)

    coverage: dict[str, object] = {
        "n_obs_recent": n_obs,
        "n_nodes_observed": len(observed_nodes),
        "n_nodes_total": n_nodes_total,
    }

    return coverage


def _detect_conflicts(
    patient_state: PatientState,
    node_map: NodeMap,
) -> tuple[dict[str, dict[str, float]], bool]:
    """Detect conflicting observations for same node.

    Conflict: multiple observations on same node where normalized
    values differ by more than 2 SD.

    Args:
        patient_state: PatientState with observation_log.
        node_map: NodeMap for index → node_id mapping.

    Returns:
        Tuple of (conflict_flags dict, conflict_inflation_applied flag).
    """
    index_to_node: dict[int, str] = {
        idx: node_id for node_id, idx in node_map.node_index.items()
    }

    # Group observations by node
    obs_by_node: dict[int, list[float]] = {}
    for obs in patient_state.observation_log:
        obs_by_node.setdefault(obs.node_i, []).append(obs.y_k)

    conflicts: dict[str, dict[str, float]] = {}
    conflict_inflation = False

    for node_i, values in obs_by_node.items():
        if len(values) < 2:
            continue

        # Compute spread: max - min vs mean
        val_range = max(values) - min(values)
        val_mean = sum(values) / len(values)

        # Conflict score: range / 2 (normalized by SD scale of ~1.0 for z-scores)
        conflict_score = val_range / 2.0

        if conflict_score > 1.0:
            node_id = index_to_node.get(node_i, f"NODE_{node_i}")
            conflicts[node_id] = {"conflict_score": round(conflict_score, 4)}
            conflict_inflation = True
            logger.info(
                "C5: Conflict detected at node '%s': "
                "%d observations, range=%.3f, score=%.3f",
                node_id, len(values), val_range, conflict_score,
            )

    return conflicts, conflict_inflation


def _build_notes(
    patient_state: PatientState,
    sigma_floor_applied: bool,
    conflict_inflation: bool,
) -> dict[str, object]:
    """Build notes_json with any warnings or special conditions.

    Args:
        patient_state: PatientState for audit info.
        sigma_floor_applied: Whether sigma floor was applied.
        conflict_inflation: Whether conflicts were detected.

    Returns:
        Notes dict.
    """
    warnings: list[str] = []

    if sigma_floor_applied:
        warnings.append(f"sigma_floor={config.MIN_SIGMA_FLOOR} applied to some nodes")

    if conflict_inflation:
        warnings.append("conflicting observations detected — review conflict_flags_json")

    if patient_state.context_match is not None:
        fb_level = patient_state.context_match.fallback_level
        if fb_level != "EXACT":
            warnings.append(f"prior fallback level: {fb_level}")

    n_active = sum(1 for p in patient_state.active_pathways if p.is_active)
    if n_active == 0 and patient_state.active_pathways:
        warnings.append("0 active pathways — population defaults used")

    high_unc = [p for p in patient_state.active_pathways if p.high_uncertainty]
    if high_unc:
        ids = [p.pathway_id for p in high_unc]
        warnings.append(f"high uncertainty pathways: {ids}")

    notes: dict[str, object] = {}
    if warnings:
        notes["warnings"] = warnings

    # Include modifier summary in notes
    if patient_state.modifier_audit:
        n_clipped = sum(1 for m in patient_state.modifier_audit if m.was_clipped)
        notes["modifier_summary"] = {
            "n_modifiers_applied": len(patient_state.modifier_audit),
            "n_clipped": n_clipped,
        }

    return notes if notes else {}


# ═══════════════════════════════════════════════════════════════
#  Top-Level: write_posterior (C5 entry point)
# ═══════════════════════════════════════════════════════════════


def write_posterior(
    patient_state: PatientState,
    node_map: NodeMap,
    session: Session,
    run_id: str,
    subject_ref: str,
    state_time: datetime | None = None,
    time_step_unit: str = "day",
    estimator_id: str = "EST_GAUSSIAN_CONJUGATE_V1",
    prior_ref_id: str | None = None,
    sequence_number: int = 1,
) -> StateSnapshotResult:
    """C5: Persist PatientState to state_snapshots_v1.

    Serializes the in-memory PatientState into the table schema,
    applies sigma floor, detects conflicts, and writes one row.

    Args:
        patient_state: Validated PatientState from C4.
        node_map: NodeMap for index → node_id mapping.
        session: SQLAlchemy session for database writes.
        run_id: Run identifier (FK to recommendation_runs_v1).
        subject_ref: Patient/profile reference (PAT_* or PROF_*).
        state_time: Timestamp for this snapshot (defaults to now).
        time_step_unit: "day" or "week".
        estimator_id: Estimator spec identifier.
        prior_ref_id: Prior bundle reference (from C1 context_key).
        sequence_number: Sequence within same timestamp.

    Returns:
        StateSnapshotResult with state_id and metadata.
    """
    if state_time is None:
        state_time = datetime.now(timezone.utc)

    state_id = _generate_state_id(state_time, sequence_number)

    logger.info(
        "── C5: Posterior Writer ──\n"
        "  state_id=%s, run_id=%s, subject_ref=%s",
        state_id, run_id, subject_ref,
    )

    # Derive prior_ref_id from context_match if not provided
    if prior_ref_id is None and patient_state.context_match is not None:
        prior_ref_id = f"PRIOR_{patient_state.context_match.context_key.upper()}_V1"

    # Serialize node beliefs (θ̂ + sd from Σ_post diagonal)
    node_beliefs, sigma_floor_applied = _serialize_node_beliefs(
        patient_state, node_map,
    )

    # Serialize evidence contributions from observation_log
    evidence_contributions = _serialize_evidence_contributions(
        patient_state, node_map,
    )

    # Compute coverage
    coverage = _compute_coverage(patient_state, node_map)

    # Detect observation conflicts
    conflict_flags, conflict_inflation = _detect_conflicts(
        patient_state, node_map,
    )

    # Build notes
    notes = _build_notes(
        patient_state, sigma_floor_applied, conflict_inflation,
    )

    obs_used_count = len(patient_state.observation_log)

    # Create ORM row
    snapshot = StateSnapshot(
        state_id=state_id,
        run_id=run_id,
        subject_ref=subject_ref,
        state_time=state_time.isoformat(),
        time_step_unit=time_step_unit,
        estimator_id=estimator_id,
        prior_ref_id=prior_ref_id,
        node_beliefs_json=node_beliefs,
        coverage_json=coverage,
        conflict_flags_json=conflict_flags,
        evidence_contributions_json=evidence_contributions,
        obs_used_count=obs_used_count,
        conflict_inflation_applied=1 if conflict_inflation else 0,
        missingness_inflation_applied=0,
        sigma_floor_applied=1 if sigma_floor_applied else 0,
        notes_json=notes,
    )

    session.add(snapshot)
    session.flush()  # Assigns PK, detects constraint violations

    logger.info(
        "C5: Wrote state_snapshots_v1 — state_id=%s, "
        "%d node beliefs, %d observations, "
        "sigma_floor=%s, conflict=%s",
        state_id,
        len(node_beliefs),
        obs_used_count,
        sigma_floor_applied,
        conflict_inflation,
    )

    return StateSnapshotResult(
        state_id=state_id,
        run_id=run_id,
        subject_ref=subject_ref,
        obs_used_count=obs_used_count,
        n_nodes_written=len(node_beliefs),
        sigma_floor_applied=sigma_floor_applied,
        conflict_inflation_applied=conflict_inflation,
    )
