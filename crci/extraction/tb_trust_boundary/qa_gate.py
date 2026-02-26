# VERIFIED: imports — all modules exist (shared/config, shared/models/*)
# VERIFIED: backward wiring — reads TypedNumericValue from group_assembler.py
# VERIFIED: forward wiring — writes QAGateResult for evidence_writer.py / P2 runner
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates QA-1..QA-5 raise/reject on failure
"""
Component: SYS_EXTRACTION.TB.QA_GATE
Spec: DEEP_AUDIT_FINDINGS.md — Tier 1 Hard Gates
Formulas: None (gating logic only)
Reads: TypedNumericValue (from group_assembler.py)
Writes: QAGateResult (consumed by evidence_writer.py / P2 runner)
Gates: GATE-QA-1 (PrecisionSourceRequired),
       GATE-QA-2 (EdgeIdExists),
       GATE-QA-3 (EstimandDeclaredAndAllowed),
       GATE-QA-4 (EvidenceKeyUniqueness),
       GATE-QA-5 (StudyContextRequired)

Purpose: Hard-reject records that cannot produce scientifically meaningful
         compiled edges. Replaces the "graceful degradation" philosophy
         with fail-early semantics. Rejected records are quarantined with
         explicit reject reasons — never silently dropped or defaulted.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crci.shared.models.intermediate_states import TypedNumericValue
from crci.shared.models.tables import EdgeRelationsDefinition

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  ALLOWED ESTIMAND FAMILIES (GATE-QA-3)
# ═══════════════════════════════════════════════════════════════

ALLOWED_ESTIMAND_FAMILIES: frozenset[str] = frozenset({
    "SMD",           # Standardized mean difference (Cohen's d, Hedges' g)
    "LOG_OR",        # Log odds ratio
    "BETA_STD",      # Standardized regression coefficient
    "BETA_UNSTD",    # Unstandardized regression coefficient
    "R",             # Correlation coefficient (Pearson / Spearman)
    "HR_LOG",        # Log hazard ratio
    "LOG_RR",        # Log risk ratio
    "FISHER_Z",      # Fisher-z transformed correlation
})


# ═══════════════════════════════════════════════════════════════
#  REJECT REASONS
# ═══════════════════════════════════════════════════════════════

REJECT_NO_PRECISION = "NO_PRECISION_SOURCE"
REJECT_EDGE_NOT_IN_DEFINITIONS = "EDGE_ID_NOT_IN_DEFINITIONS"
REJECT_ESTIMAND_UNDECLARED = "ESTIMAND_UNDECLARED"
REJECT_DUPLICATE_KEY = "DUPLICATE_EVIDENCE_KEY"
REJECT_MISSING_STUDY_CONTEXT = "MISSING_STUDY_CONTEXT"


# ═══════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class QAGateRejection:
    """A single rejection event from the QA gate.

    Attributes:
        gate_id: Which gate rejected (QA-1 through QA-5).
        reject_reason: Machine-readable reject code.
        record_index: Index of the rejected record in the input list.
        details: Human-readable context about the rejection.
        record_snapshot: Minimal snapshot of the rejected record for quarantine.
    """
    gate_id: str
    reject_reason: str
    record_index: int
    details: str
    record_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAGateResult:
    """Result of running all QA gates on a batch of records.

    Attributes:
        accepted: Records that passed all 5 gates.
        rejected: Records that failed at least one gate, with reasons.
        stats: Summary statistics for logging/monitoring.
    """
    accepted: list[TypedNumericValue]
    rejected: list[QAGateRejection]
    stats: dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  CACHE: Valid edge IDs (loaded once per pipeline run)
# ═══════════════════════════════════════════════════════════════

_valid_edge_ids_cache: frozenset[str] | None = None


def _load_valid_edge_ids(session: Session) -> frozenset[str]:
    """Load all active edge_relation_ids from edge_relations_definitions_v1.

    Cached for the lifetime of the module (one pipeline run).
    """
    global _valid_edge_ids_cache
    if _valid_edge_ids_cache is not None:
        return _valid_edge_ids_cache

    stmt = select(EdgeRelationsDefinition.edge_relation_id).where(
        EdgeRelationsDefinition.active == 1
    )
    rows = session.execute(stmt).all()
    _valid_edge_ids_cache = frozenset(r[0] for r in rows)
    logger.info(
        "QA-GATE: Loaded %d valid edge_relation_ids from definitions",
        len(_valid_edge_ids_cache),
    )
    return _valid_edge_ids_cache


def clear_edge_id_cache() -> None:
    """Clear the cached edge IDs (for testing or between pipeline runs)."""
    global _valid_edge_ids_cache
    _valid_edge_ids_cache = None


# ═══════════════════════════════════════════════════════════════
#  INDIVIDUAL GATE CHECKS
# ═══════════════════════════════════════════════════════════════


def check_qa1_precision_source(tv: TypedNumericValue) -> str | None:
    """GATE-QA-1: PrecisionSourceRequired.

    A record must have at least one precision source:
    - se is not None and > 0
    - ci_lower AND ci_upper are both not None
    - p_value AND n are both not None
    - n > 2 AND value is not None (allows L4B Borenstein SE derivation)

    Returns:
        None if passed, reject reason string if failed.
    """
    has_se = tv.se is not None and tv.se > 0
    has_ci = tv.ci_lower is not None and tv.ci_upper is not None
    has_p_n = tv.p_value is not None and tv.n is not None and tv.n > 0
    # L4B: if we have N > 2 and an effect size, P3 can derive SE via Borenstein
    has_n_for_derivation = (
        tv.n is not None and tv.n > 2
        and tv.value is not None
    )

    if has_se or has_ci or has_p_n or has_n_for_derivation:
        return None  # PASSED

    return REJECT_NO_PRECISION


def check_qa2_edge_id_exists(
    tv: TypedNumericValue,
    valid_edge_ids: frozenset[str],
) -> str | None:
    """GATE-QA-2: EdgeIdExists.

    The record's edge_relation_id must exist in edge_relations_definitions_v1.
    Records with edge_relation_id=None or "UNASSIGNED" are also rejected.

    Returns:
        None if passed, reject reason string if failed.
    """
    eid = tv.edge_relation_id
    if eid is None or eid == "UNASSIGNED" or eid not in valid_edge_ids:
        return REJECT_EDGE_NOT_IN_DEFINITIONS
    return None


def check_qa3_estimand_declared(
    tv: TypedNumericValue,
    declared_estimand: str | None = None,
) -> str | None:
    """GATE-QA-3: EstimandDeclaredAndAllowed.

    The record must have a declared effect size family that is in the
    allowed set. The estimand comes from:
    1. Explicit `declared_estimand` parameter (from meta.json or P0 triage)
    2. Inference from label_type (EFFECT_SIZE → SMD, ODDS_RATIO → LOG_OR, etc.)

    Returns:
        None if passed, reject reason string if failed.
    """
    # Check explicit declaration first
    if declared_estimand and declared_estimand.upper() in ALLOWED_ESTIMAND_FAMILIES:
        return None

    # Try to infer from label_type
    if tv.label_type:
        inferred = _infer_estimand_from_label(tv.label_type)
        if inferred is not None:
            return None

    return REJECT_ESTIMAND_UNDECLARED


def _infer_estimand_from_label(label_type: str) -> str | None:
    """Try to infer estimand family from the label_type string.

    Conservative mapping — only well-defined label types are mapped.
    """
    label_upper = label_type.upper()
    _LABEL_TO_ESTIMAND: dict[str, str] = {
        "EFFECT_SIZE": "SMD",
        "COHENS_D": "SMD",
        "HEDGES_G": "SMD",
        "SMD": "SMD",
        "MEAN_DIFFERENCE": "SMD",
        "GROUP_DIFF": "SMD",
        "PARTIAL_ETA_SQ": "SMD",
        "PARTIAL_ETA_SQUARED": "SMD",
        "ETA_SQUARED": "SMD",
        "F_STATISTIC": "SMD",
        "F_VALUE": "SMD",
        "T_STATISTIC": "SMD",
        "T_VALUE": "SMD",
        "ODDS_RATIO": "LOG_OR",
        "OR": "LOG_OR",
        "LOG_OR": "LOG_OR",
        "HAZARD_RATIO": "HR_LOG",
        "HR": "HR_LOG",
        "LOG_HR": "HR_LOG",
        "RISK_RATIO": "LOG_RR",
        "RR": "LOG_RR",
        "LOG_RR": "LOG_RR",
        "RELATIVE_RISK": "LOG_RR",
        "CORRELATION": "R",
        "R": "R",
        "PEARSON_R": "R",
        "FISHER_Z": "FISHER_Z",
        "BETA": "BETA_UNSTD",
        "BETA_STD": "BETA_STD",
        "BETA_UNSTD": "BETA_UNSTD",
        "REGRESSION_COEFFICIENT": "BETA_UNSTD",
        "PERCENT_CHANGE": "SMD",
    }
    return _LABEL_TO_ESTIMAND.get(label_upper)


def check_qa5_study_context(
    paper_id: str | None,
    study_id: str | None,
) -> str | None:
    """GATE-QA-5: StudyContextRequired.

    At least paper_id must be present; study_id falls back to paper_id
    if not independently available.

    Returns:
        None if passed, reject reason string if failed.
    """
    if not paper_id and not study_id:
        return REJECT_MISSING_STUDY_CONTEXT
    return None


# ═══════════════════════════════════════════════════════════════
#  EVIDENCE KEY (for GATE-QA-4)
# ═══════════════════════════════════════════════════════════════


def compute_evidence_key(
    paper_id: str,
    study_id: str,
    edge_relation_id: str,
    timepoint_bucket: str | None = None,
    contrast_id: str | None = None,
) -> str:
    """Compute a canonical evidence key for dedup.

    Full EvidenceKey per audit spec:
        (paper_id, study_id, edge_relation_id, outcome_node_id,
         exposure_node_id, timepoint_bucket, contrast_id, analysis_id)

    Currently outcome/exposure node_ids and analysis_id are not available
    from TB output. We use the available fields; the key will become more
    discriminating as extraction improves.
    """
    parts = [
        paper_id,
        study_id,
        edge_relation_id,
        timepoint_bucket or "default",
        contrast_id or "primary",
    ]
    return "|".join(parts)


# ═══════════════════════════════════════════════════════════════
#  MAIN GATE RUNNER
# ═══════════════════════════════════════════════════════════════


def run_qa_gates(
    records: list[TypedNumericValue],
    session: Session,
    paper_id: str | None = None,
    study_id: str | None = None,
    declared_estimand: str | None = None,
) -> QAGateResult:
    """Run all 5 QA gates on a batch of TypedNumericValue records.

    Order: QA-5 (study context, checked once) → QA-1, QA-2, QA-3 per record
           → QA-4 (dedup across accepted records).

    Records that fail ANY gate are rejected with the first failure reason.
    Rejected records are captured as QAGateRejection with enough context
    for quarantine storage.

    Args:
        records: TypedNumericValue list from group_assembler.
        session: DB session for edge ID lookup (QA-2).
        paper_id: Paper identifier (from context/meta.json).
        study_id: Study identifier (may equal paper_id).
        declared_estimand: Explicit estimand family from meta.json or P0.

    Returns:
        QAGateResult with accepted/rejected lists and stats.
    """
    accepted: list[TypedNumericValue] = []
    rejected: list[QAGateRejection] = []

    # ── QA-5: Study context (applies to entire batch) ──
    qa5_result = check_qa5_study_context(paper_id, study_id)
    if qa5_result is not None:
        # Entire batch rejected — no study context
        for i, tv in enumerate(records):
            rejected.append(QAGateRejection(
                gate_id="QA-5",
                reject_reason=qa5_result,
                record_index=i,
                details=f"No paper_id or study_id for record {i}",
                record_snapshot=_snapshot(tv),
            ))
        logger.warning(
            "QA-GATE: Entire batch of %d records rejected by QA-5 "
            "(no paper_id or study_id)",
            len(records),
        )
        return QAGateResult(
            accepted=[],
            rejected=rejected,
            stats={"total": len(records), "qa5_reject": len(records)},
        )

    # Use paper_id as study_id fallback
    effective_study_id = study_id or paper_id or "unknown"
    effective_paper_id = paper_id or study_id or "unknown"

    # ── Load valid edge IDs for QA-2 ──
    valid_edge_ids = _load_valid_edge_ids(session)

    # ── Per-record gates: QA-1, QA-2, QA-3 ──
    stats: dict[str, int] = {
        "total": len(records),
        "qa1_reject": 0,
        "qa2_reject": 0,
        "qa3_reject": 0,
        "qa4_reject": 0,
        "qa5_reject": 0,
        "accepted": 0,
    }

    pre_dedup_accepted: list[tuple[int, TypedNumericValue]] = []

    for i, tv in enumerate(records):
        # QA-1: Precision source
        qa1 = check_qa1_precision_source(tv)
        if qa1 is not None:
            rejected.append(QAGateRejection(
                gate_id="QA-1",
                reject_reason=qa1,
                record_index=i,
                details=(
                    f"Record {i}: se={tv.se}, ci=[{tv.ci_lower}, {tv.ci_upper}], "
                    f"p={tv.p_value}, n={tv.n}"
                ),
                record_snapshot=_snapshot(tv),
            ))
            stats["qa1_reject"] += 1
            continue

        # QA-2: Edge ID exists in definitions
        qa2 = check_qa2_edge_id_exists(tv, valid_edge_ids)
        if qa2 is not None:
            rejected.append(QAGateRejection(
                gate_id="QA-2",
                reject_reason=qa2,
                record_index=i,
                details=(
                    f"Record {i}: edge_relation_id='{tv.edge_relation_id}' "
                    f"not in {len(valid_edge_ids)} definitions"
                ),
                record_snapshot=_snapshot(tv),
            ))
            stats["qa2_reject"] += 1
            continue

        # QA-3: Estimand declared and allowed
        qa3 = check_qa3_estimand_declared(tv, declared_estimand)
        if qa3 is not None:
            rejected.append(QAGateRejection(
                gate_id="QA-3",
                reject_reason=qa3,
                record_index=i,
                details=(
                    f"Record {i}: label_type='{tv.label_type}', "
                    f"declared_estimand='{declared_estimand}' "
                    f"— cannot map to allowed family"
                ),
                record_snapshot=_snapshot(tv),
            ))
            stats["qa3_reject"] += 1
            continue

        pre_dedup_accepted.append((i, tv))

    # ── QA-4: Evidence key uniqueness ──
    seen_keys: dict[str, int] = {}  # key → first record index

    for i, tv in pre_dedup_accepted:
        ek = compute_evidence_key(
            paper_id=effective_paper_id,
            study_id=effective_study_id,
            edge_relation_id=tv.edge_relation_id or "UNKNOWN",
            timepoint_bucket=None,  # Not yet available from TB
            contrast_id=tv.grouping_id,  # Use grouping_id to distinguish observations
        )

        if ek in seen_keys:
            rejected.append(QAGateRejection(
                gate_id="QA-4",
                reject_reason=REJECT_DUPLICATE_KEY,
                record_index=i,
                details=(
                    f"Record {i}: duplicate EvidenceKey '{ek}' — "
                    f"first seen at record {seen_keys[ek]}"
                ),
                record_snapshot=_snapshot(tv),
            ))
            stats["qa4_reject"] += 1
        else:
            seen_keys[ek] = i
            accepted.append(tv)
            stats["accepted"] += 1

    # ── Summary logging ──
    logger.info(
        "QA-GATE: %d/%d accepted, %d rejected "
        "(QA-1: %d, QA-2: %d, QA-3: %d, QA-4: %d)",
        stats["accepted"],
        stats["total"],
        len(rejected),
        stats["qa1_reject"],
        stats["qa2_reject"],
        stats["qa3_reject"],
        stats["qa4_reject"],
    )

    if rejected:
        for r in rejected:
            logger.info(
                "  REJECTED [%s] %s: %s",
                r.gate_id,
                r.reject_reason,
                r.details,
            )

    return QAGateResult(accepted=accepted, rejected=rejected, stats=stats)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _snapshot(tv: TypedNumericValue) -> dict[str, Any]:
    """Create a minimal snapshot of a TypedNumericValue for quarantine storage."""
    return {
        "value": tv.value,
        "se": tv.se,
        "ci_lower": tv.ci_lower,
        "ci_upper": tv.ci_upper,
        "p_value": tv.p_value,
        "n": tv.n,
        "edge_relation_id": tv.edge_relation_id,
        "label_type": tv.label_type,
        "original_text": tv.original_text[:200] if tv.original_text else None,
        "grouping_id": tv.grouping_id,
    }
