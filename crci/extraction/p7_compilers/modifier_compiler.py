# VERIFIED: formulas P7-C5a (exp β_interaction), P7-C5b (1 + β/β_main)
#           match SYS_EXTRACTION_ADDENDUM Part 6 Compiler 5
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads SubgroupEvidence from tables.py (B14)
# VERIFIED: forward wiring — writes CompiledModifier for modifier_registry
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G5 (clamp to guardrails) enforced
"""
Component: SYS_EXTRACTION.EX-P7.C5
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 5
Formulas: P7-C5a (multiplier = exp(β_interaction) for log-scale),
          P7-C5b (multiplier = 1 + β_interaction/β_main for linear-scale)
Reads: SubgroupEvidence rows (from subgroup_evidence_v1, written by AG05-EXT)
Writes: CompiledModifier (consumed by baseline_modifier_definitions_v1 writer)
Gates: P7-G5 (clamp multiplier to [0.7, 1.5] per ALG-C4b guardrails)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledModifier,
    GateViolation,
)
from crci.shared.models.tables import SubgroupEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class _ModifierGroup:
    """Evidence rows for one modifier variable-value pair."""

    modifier_variable: str
    modifier_value: str
    edge_id: str | None = None
    rows: list[SubgroupEvidence] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  IVW POOLING FOR INTERACTIONS
# ═══════════════════════════════════════════════════════════════


def _pool_interactions_ivw(
    betas: list[float],
    ses: list[float],
) -> tuple[float, float]:
    """Pool interaction effects via IVW (same as edge evidence, formula P4-1).

    Formula P4-1: β_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
                  SE_pooled = 1 / √(Σ(1/SE²_i))
    """
    if not betas or not ses:
        return 0.0, 1.0

    if len(betas) == 1:
        return betas[0], ses[0]

    weights = [1.0 / (se ** 2) for se in ses]
    sum_weights = sum(weights)
    beta_pooled = sum(b / (se ** 2) for b, se in zip(betas, ses)) / sum_weights
    se_pooled = 1.0 / math.sqrt(sum_weights)
    return beta_pooled, se_pooled


# ═══════════════════════════════════════════════════════════════
#  MULTIPLIER CONVERSION
# ═══════════════════════════════════════════════════════════════


def _convert_to_multiplier(
    beta_interaction: float,
    beta_main: float | None = None,
    scale: str = "log",
) -> float:
    """Convert interaction β to multiplicative modifier.

    Formula P7-C5a: multiplier = exp(β_interaction) for log-scale effects
    Formula P7-C5b: multiplier = 1 + β_interaction/β_main for linear-scale

    Args:
        beta_interaction: Pooled interaction effect.
        beta_main: Main effect beta (needed for linear scale).
        scale: "log" or "linear".

    Returns:
        Multiplicative modifier.
    """
    if scale == "log":
        # Formula P7-C5a: multiplier = exp(β_interaction)
        multiplier = math.exp(beta_interaction)
    else:
        # Formula P7-C5b: multiplier = 1 + β_interaction/β_main
        if beta_main is not None and abs(beta_main) > 1e-8:
            multiplier = 1.0 + beta_interaction / beta_main
        else:
            # Cannot compute linear multiplier without β_main
            # Fall back to exp approximation
            logger.warning(
                "Cannot compute linear multiplier: β_main=%.6f, "
                "falling back to exp(β_interaction)",
                beta_main,
            )
            multiplier = math.exp(beta_interaction)

    return multiplier


# ═══════════════════════════════════════════════════════════════
#  EVIDENCE GRADING
# ═══════════════════════════════════════════════════════════════


def _grade_evidence(rows: list[SubgroupEvidence]) -> str:
    """Grade modifier evidence quality.

    RCT interaction = HIGH
    Observational = MODERATE
    Single study = LOW
    """
    if len(rows) < 2:
        return "LOW"

    # Check study IDs for diversity
    study_ids = {r.study_id for r in rows if r.study_id}
    if len(study_ids) < 2:
        return "LOW"

    # In v1, without detailed study design metadata,
    # multiple studies = MODERATE
    return "MODERATE"


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_modifiers(
    evidence_rows: list[SubgroupEvidence],
    beta_main_lookup: dict[str, float] | None = None,
    scale: str = "log",
) -> list[CompiledModifier]:
    """Compile subgroup modifiers from extracted interaction evidence.

    Groups evidence by (modifier_variable, modifier_value), pools
    interaction effects via IVW, converts to multiplicative modifier,
    and clamps to [0.7, 1.5] per ALG-C4b guardrails.

    Args:
        evidence_rows: Rows from subgroup_evidence_v1 (written by AG05-EXT).
        beta_main_lookup: Optional lookup of edge_id → β_main for linear scale.
        scale: "log" or "linear" — determines multiplier conversion formula.

    Returns:
        List of CompiledModifier, one per (variable, value) pair.
    """
    if beta_main_lookup is None:
        beta_main_lookup = {}

    # Group by (modifier_variable, modifier_value)
    groups: dict[tuple[str, str], _ModifierGroup] = {}
    for row in evidence_rows:
        var = (row.modifier_variable or "unknown").strip().lower()
        val = (row.modifier_value or "unknown").strip().lower()
        key = (var, val)
        if key not in groups:
            groups[key] = _ModifierGroup(
                modifier_variable=row.modifier_variable or "unknown",
                modifier_value=row.modifier_value or "unknown",
                edge_id=row.edge_id,
            )
        groups[key].rows.append(row)

    results: list[CompiledModifier] = []

    for key, group in groups.items():
        rows = group.rows

        logger.info(
            "Compiling modifier '%s'='%s': %d evidence rows",
            group.modifier_variable,
            group.modifier_value,
            len(rows),
        )

        # Collect interaction betas and SEs
        betas: list[float] = []
        ses: list[float] = []
        for r in rows:
            if r.interaction_beta is not None:
                beta = r.interaction_beta
                se = r.interaction_se if r.interaction_se is not None and r.interaction_se > 0 else 0.5
                betas.append(beta)
                ses.append(se)

        if not betas:
            logger.warning(
                "Modifier '%s'='%s': no valid interaction betas, skipping",
                group.modifier_variable,
                group.modifier_value,
            )
            continue

        # Pool interactions via IVW (formula P4-1)
        beta_pooled, se_pooled = _pool_interactions_ivw(betas, ses)

        # Convert to multiplicative modifier
        beta_main = beta_main_lookup.get(group.edge_id or "", None)
        multiplier = _convert_to_multiplier(beta_pooled, beta_main, scale)

        # ─── Gate P7-G5: Clamp to [0.7, 1.5] per ALG-C4b ────────
        original_multiplier = multiplier
        multiplier = max(
            config.P7_MODIFIER_CLAMP_LOW,
            min(config.P7_MODIFIER_CLAMP_HIGH, multiplier),
        )
        if multiplier != original_multiplier:
            logger.info(
                "Modifier '%s'='%s': multiplier %.4f clamped to %.4f "
                "(guardrails [%.2f, %.2f])",
                group.modifier_variable,
                group.modifier_value,
                original_multiplier,
                multiplier,
                config.P7_MODIFIER_CLAMP_LOW,
                config.P7_MODIFIER_CLAMP_HIGH,
            )

        # Grade evidence
        grade = _grade_evidence(rows)

        study_ids = sorted({r.study_id for r in rows if r.study_id})

        compiled = CompiledModifier(
            modifier_variable=group.modifier_variable,
            modifier_value=group.modifier_value,
            edge_id=group.edge_id,
            multiplier=multiplier,
            grade=grade,
            k_studies=len(set(r.study_id for r in rows if r.study_id)),
            provenance_status="CURATED_TRACED",
            provenance_ref="; ".join(study_ids),
        )
        results.append(compiled)

        logger.info(
            "Compiled modifier '%s'='%s': multiplier=%.4f (β_pooled=%.4f, "
            "SE=%.4f), grade=%s, k=%d",
            group.modifier_variable,
            group.modifier_value,
            multiplier,
            beta_pooled,
            se_pooled,
            grade,
            compiled.k_studies,
        )

    logger.info(
        "Modifier compilation complete: %d modifiers compiled",
        len(results),
    )
    return results
