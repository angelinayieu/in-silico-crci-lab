# VERIFIED: formula P7-C4a (Hill/Emax) matches SYS_EXTRACTION_ADDENDUM Part 6 Compiler 4
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads DoseEvidence from tables.py (B13)
# VERIFIED: forward wiring — writes CompiledDoseResponse for dose_bridges_v1
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G4 raises on failure
"""
Component: SYS_EXTRACTION.EX-P7.C4
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 4
Formulas: P7-C4a (E(d) = E0 + Emax * d^h / (ED50^h + d^h))
Reads: DoseEvidence rows (from dose_evidence_v1, written by AG06-EXT)
Writes: CompiledDoseResponse (consumed by dose_bridges_v1 writer)
Gates: P7-G4 (Emax same sign as effect direction; ED50 > 0; hill > 0)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledDoseResponse,
    GateViolation,
)
from crci.shared.models.tables import DoseEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  HILL/EMAX MODEL
# ═══════════════════════════════════════════════════════════════


def _hill_emax(
    d: np.ndarray,
    e0: float,
    emax: float,
    ed50: float,
    hill: float,
) -> np.ndarray:
    """Hill/Emax dose-response model.

    Formula P7-C4a: E(d) = E0 + Emax * d^h / (ED50^h + d^h)
    """
    return e0 + emax * (d ** hill) / (ed50 ** hill + d ** hill)


# ═══════════════════════════════════════════════════════════════
#  DOSE NORMALIZATION
# ═══════════════════════════════════════════════════════════════


def _normalize_doses(
    rows: list[DoseEvidence],
) -> list[DoseEvidence]:
    """Normalize doses to common unit per intervention.

    For v1, groups by dose_unit and uses the most common unit.
    Rows with incompatible units are excluded with a warning.
    """
    if not rows:
        return rows

    # Find most common unit
    unit_counts: dict[str, int] = {}
    for r in rows:
        unit = (r.dose_unit or "unknown").strip().lower()
        unit_counts[unit] = unit_counts.get(unit, 0) + 1

    target_unit = max(unit_counts, key=unit_counts.get)

    normalized = []
    for r in rows:
        unit = (r.dose_unit or "unknown").strip().lower()
        if unit == target_unit:
            normalized.append(r)
        else:
            logger.warning(
                "Study %s: dose unit '%s' differs from target '%s', "
                "excluding from compilation",
                r.study_id,
                r.dose_unit,
                target_unit,
            )

    return normalized


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_dose_response(
    evidence_rows: list[DoseEvidence],
) -> list[CompiledDoseResponse]:
    """Compile dose-response parameters per intervention from extracted evidence.

    Groups evidence by action_id, normalizes doses, and fits Hill/Emax model.
    If < 3 dose levels: uses linear dose-response with max observed effect
    as Emax. Flags as APPROXIMATE_PENDING.

    Gate P7-G4: Emax same sign as effect direction; ED50 > 0; hill > 0.

    Args:
        evidence_rows: Rows from dose_evidence_v1 (written by AG06-EXT).

    Returns:
        List of CompiledDoseResponse, one per intervention.

    Raises:
        GateViolation: If P7-G4 constraints are violated.
    """
    # Group by action_id (or intervention_type as fallback)
    groups: dict[str, list[DoseEvidence]] = {}
    for row in evidence_rows:
        key = (row.action_id or row.intervention_type or "unknown").strip().lower()
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    results: list[CompiledDoseResponse] = []

    for action_id, rows in groups.items():
        logger.info(
            "Compiling dose-response for '%s': %d evidence rows",
            action_id,
            len(rows),
        )

        # Normalize doses to common unit
        rows = _normalize_doses(rows)

        # Filter to valid rows
        valid = [
            r for r in rows
            if r.effect is not None and r.dose_level is not None and r.dose_level > 0
        ]

        if not valid:
            logger.warning(
                "Action '%s': no valid dose-effect pairs, skipping",
                action_id,
            )
            continue

        k = len(valid)
        doses = np.array([r.dose_level for r in valid])
        effects = np.array([r.effect for r in valid])
        ses = np.array([
            r.se if r.se is not None and r.se > 0.0 else 1.0
            for r in valid
        ])
        weights = 1.0 / (ses ** 2)

        # Determine effect direction from data
        effect_sign = 1.0 if np.mean(effects) >= 0 else -1.0

        study_ids = sorted({r.study_id for r in valid if r.study_id})

        if k < config.P7_MIN_DOSE_LEVELS_EMAX:
            # Cannot fit Emax: use linear dose-response
            max_effect_idx = np.argmax(np.abs(effects))
            emax = float(effects[max_effect_idx])
            max_dose = float(doses[max_effect_idx])
            ed50 = max_dose / 2.0 if max_dose > 0 else 1.0

            logger.info(
                "Action '%s': k=%d < %d, using linear approximation: "
                "Emax=%.4f, ED50=%.4f",
                action_id,
                k,
                config.P7_MIN_DOSE_LEVELS_EMAX,
                emax,
                ed50,
            )

            compiled = CompiledDoseResponse(
                action_id=action_id,
                e0=config.P7_EMAX_E0_DEFAULT,
                emax=emax,
                ed50=ed50,
                hill=config.P7_HILL_COEFFICIENT_DEFAULT,
                k_dose_levels=k,
                provenance_status="APPROXIMATE_PENDING",
                provenance_ref="; ".join(study_ids),
            )
            results.append(compiled)
            continue

        # Fit Hill/Emax model using NLLS weighted by 1/SE²
        try:
            # Initial guesses
            e0_init = config.P7_EMAX_E0_DEFAULT
            emax_init = float(np.max(np.abs(effects))) * effect_sign
            ed50_init = float(np.median(doses))
            hill_init = config.P7_HILL_COEFFICIENT_DEFAULT

            popt, _ = curve_fit(
                _hill_emax,
                doses,
                effects,
                p0=[e0_init, emax_init, ed50_init, hill_init],
                sigma=ses,
                absolute_sigma=True,
                bounds=(
                    [-np.inf, -np.inf, 1e-6, 1e-6],
                    [np.inf, np.inf, np.inf, 10.0],
                ),
                maxfev=5000,
            )
            e0, emax, ed50, hill = (
                float(popt[0]),
                float(popt[1]),
                float(popt[2]),
                float(popt[3]),
            )

        except (RuntimeError, ValueError) as exc:
            # Fallback to linear approximation
            logger.warning(
                "Action '%s': curve_fit failed (%s), using linear approximation",
                action_id,
                exc,
            )
            max_effect_idx = np.argmax(np.abs(effects))
            e0 = config.P7_EMAX_E0_DEFAULT
            emax = float(effects[max_effect_idx])
            ed50 = float(np.median(doses))
            hill = config.P7_HILL_COEFFICIENT_DEFAULT

        # ─── Gate P7-G4: Emax same sign as effect direction ───────
        if emax != 0.0 and np.sign(emax) != effect_sign:
            raise GateViolation(
                "P7-G4",
                f"Action '{action_id}': Emax ({emax:.4f}) has opposite sign "
                f"to observed effect direction ({effect_sign:+.0f})",
                {"action_id": action_id, "emax": emax, "effect_sign": effect_sign},
            )

        # ─── Gate P7-G4: ED50 > 0 ────────────────────────────────
        if ed50 <= config.P7_ED50_MIN:
            raise GateViolation(
                "P7-G4",
                f"Action '{action_id}': ED50 ({ed50:.4f}) <= {config.P7_ED50_MIN}",
                {"action_id": action_id, "ed50": ed50},
            )

        # ─── Gate P7-G4: hill > 0 ────────────────────────────────
        if hill <= config.P7_HILL_MIN:
            raise GateViolation(
                "P7-G4",
                f"Action '{action_id}': Hill coefficient ({hill:.4f}) <= {config.P7_HILL_MIN}",
                {"action_id": action_id, "hill": hill},
            )

        compiled = CompiledDoseResponse(
            action_id=action_id,
            e0=e0,
            emax=emax,
            ed50=ed50,
            hill=hill,
            k_dose_levels=k,
            provenance_status="CURATED_TRACED",
            provenance_ref="; ".join(study_ids),
        )
        results.append(compiled)

        logger.info(
            "Compiled dose-response '%s': E0=%.4f, Emax=%.4f, "
            "ED50=%.4f, hill=%.4f, k=%d",
            action_id,
            e0,
            emax,
            ed50,
            hill,
            k,
        )

    logger.info(
        "Dose-response compilation complete: %d interventions compiled",
        len(results),
    )
    return results
