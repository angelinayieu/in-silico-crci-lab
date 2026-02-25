# VERIFIED: rules E1-E6 match CONVERSION_VALIDITY_AND_HARDENING.md Module 2.1
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads PooledEstimate + edge records from EX-P4
# VERIFIED: forward wiring — writes EscalationResult consumed by edge compiler
# VERIFIED: no hardcoded formula parameters — all from config
"""
Component: SYS_EXTRACTION.EX-P4.ESCALATION
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 2 (Influence-Aware Verification)
Rules:
    E1: w_i > 0.50 (majority IVW weight)
    E2: k < 3 (insufficient pooling protection)
    E3: removing record flips β̂ sign (sign-flip sensitivity)
    E4: only cancer-matched study AND k ≤ 5
    E5: se_derivation_level ≥ L4 AND w_i > 0.30
    E6: meta_source_flag = FOREST_PLOT_ENTRY AND NOT superseded
Reads: PooledEstimate, list of HarmonizedClaim (from EX-P4 IVW)
Writes: EscalationResult (consumed by edge compilation / review queue)
Gates: None (escalation is advisory; SE inflation until verified)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.config import (
    ESCALATION_E1_WEIGHT_THRESHOLD,
    ESCALATION_E2_MIN_K,
    ESCALATION_E4_MAX_K,
    ESCALATION_E5_SE_LEVEL_THRESHOLD,
    ESCALATION_E5_WEIGHT_THRESHOLD,
    ESCALATION_UNVERIFIED_SE_INFLATION,
)
from crci.shared.models.enums import (
    EscalationRule,
    MetaSourceFlag,
    SEDerivationLevel,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

# SE derivation levels that are "soft" (L4a and above)
_SOFT_SE_LEVELS = frozenset({
    SEDerivationLevel.L4A,
    SEDerivationLevel.L4B,
    SEDerivationLevel.L5,
    SEDerivationLevel.L6,
})


@dataclass(frozen=True)
class RecordEscalation:
    """Escalation result for a single evidence record."""

    ler_id: str
    escalated: bool
    rules_triggered: tuple[EscalationRule, ...]
    verification_status: VerificationStatus
    se_inflation: float
    notes: str


@dataclass(frozen=True)
class EscalationResult:
    """Escalation assessment for an entire edge's evidence pool."""

    edge_relation_id: str
    k: int
    records_escalated: int
    record_results: tuple[RecordEscalation, ...]
    any_escalated: bool
    edge_se_inflation: float  # max inflation across all escalated records


@dataclass
class EvidenceRecord:
    """Minimal evidence record interface for escalation checks.

    Callers populate this from HarmonizedClaim + edge metadata.
    """

    ler_id: str
    beta: float
    se: float
    ivw_weight: float = 0.0
    se_derivation_level: str | None = None
    meta_source_flag: str | None = None
    is_cancer_matched: bool = False
    is_superseded: bool = False


def compute_ivw_weights(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Compute IVW weight share for each record.

    Formula: w_i = (1/SE²_i) / Σ(1/SE²_j)
    """
    inv_var_sum = 0.0
    for rec in records:
        if rec.se is not None and rec.se > 0:
            inv_var_sum += 1.0 / (rec.se * rec.se)

    if inv_var_sum <= 0:
        return records

    for rec in records:
        if rec.se is not None and rec.se > 0:
            rec.ivw_weight = (1.0 / (rec.se * rec.se)) / inv_var_sum
        else:
            rec.ivw_weight = 0.0

    return records


def _check_sign_flip(
    records: list[EvidenceRecord],
    record_idx: int,
    beta_pooled: float,
) -> bool:
    """E3: Check if removing this record flips the sign of β̂_pooled.

    Re-computes IVW excluding the target record and checks sign.
    """
    if beta_pooled == 0.0:
        return False

    numer = 0.0
    denom = 0.0
    for i, rec in enumerate(records):
        if i == record_idx:
            continue
        if rec.se is not None and rec.se > 0:
            w = 1.0 / (rec.se * rec.se)
            numer += rec.beta * w
            denom += w

    if denom <= 0:
        return False

    beta_without = numer / denom
    return (beta_pooled > 0 and beta_without < 0) or (beta_pooled < 0 and beta_without > 0)


def evaluate_escalation(
    edge_relation_id: str,
    records: list[EvidenceRecord],
    beta_pooled: float,
) -> EscalationResult:
    """Run E1-E6 escalation checks on all records for an edge.

    Parameters
    ----------
    edge_relation_id : str
        The edge being evaluated.
    records : list[EvidenceRecord]
        Evidence records with IVW weights already computed.
    beta_pooled : float
        The pooled β̂ estimate from IVW.

    Returns
    -------
    EscalationResult
        Assessment with per-record escalation decisions.
    """
    k = len(records)
    n_cancer_matched = sum(1 for r in records if r.is_cancer_matched)

    record_results: list[RecordEscalation] = []

    for i, rec in enumerate(records):
        rules: list[EscalationRule] = []

        # E1: Majority IVW weight
        if rec.ivw_weight > ESCALATION_E1_WEIGHT_THRESHOLD:
            rules.append(EscalationRule.E1_MAJORITY_WEIGHT)

        # E2: Low k (applies to ALL records if k < threshold)
        if k < ESCALATION_E2_MIN_K:
            rules.append(EscalationRule.E2_LOW_K)

        # E3: Sign-flip sensitivity
        if k >= 2 and _check_sign_flip(records, i, beta_pooled):
            rules.append(EscalationRule.E3_SIGN_FLIP)

        # E4: Sole cancer-matched study + low k
        if (
            rec.is_cancer_matched
            and n_cancer_matched == 1
            and k <= ESCALATION_E4_MAX_K
        ):
            rules.append(EscalationRule.E4_SOLE_CANCER_MATCH)

        # E5: Soft SE + substantial weight
        if (
            rec.se_derivation_level is not None
            and rec.se_derivation_level in {lev.value for lev in _SOFT_SE_LEVELS}
            and rec.ivw_weight > ESCALATION_E5_WEIGHT_THRESHOLD
        ):
            rules.append(EscalationRule.E5_SOFT_SE_HIGH_WEIGHT)

        # E6: Forest plot entry (not superseded)
        if (
            rec.meta_source_flag == MetaSourceFlag.FOREST_PLOT_ENTRY
            and not rec.is_superseded
        ):
            rules.append(EscalationRule.E6_FOREST_PLOT)

        escalated = len(rules) > 0
        verification_status = (
            VerificationStatus.ESCALATED_TO_TIER1 if escalated
            else VerificationStatus.UNVERIFIED
        )
        se_inflation = ESCALATION_UNVERIFIED_SE_INFLATION if escalated else 1.0

        notes_parts = []
        if rules:
            rule_strs = [r.value for r in rules]
            notes_parts.append(f"ESCALATED by {', '.join(rule_strs)}")
            notes_parts.append(f"w_i={rec.ivw_weight:.4f}")
            notes_parts.append(f"SE inflation={se_inflation:.2f}×")
            logger.warning(
                "edge=%s, ler_id=%s: ESCALATED to Tier 1 by rules %s (w_i=%.4f)",
                edge_relation_id, rec.ler_id, rule_strs, rec.ivw_weight,
            )

        record_results.append(RecordEscalation(
            ler_id=rec.ler_id,
            escalated=escalated,
            rules_triggered=tuple(rules),
            verification_status=verification_status,
            se_inflation=se_inflation,
            notes="; ".join(notes_parts) if notes_parts else "No escalation",
        ))

    any_escalated = any(r.escalated for r in record_results)
    max_inflation = max(
        (r.se_inflation for r in record_results),
        default=1.0,
    )

    return EscalationResult(
        edge_relation_id=edge_relation_id,
        k=k,
        records_escalated=sum(1 for r in record_results if r.escalated),
        record_results=tuple(record_results),
        any_escalated=any_escalated,
        edge_se_inflation=max_inflation,
    )
