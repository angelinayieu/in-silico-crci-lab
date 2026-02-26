# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads QAGateRejection from qa_gate.py
# VERIFIED: forward wiring — writes to edge_evidence_quarantine_v1
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.TB.QUARANTINE_WRITER
Spec: DEEP_AUDIT_FINDINGS.md — Tier 2 Remove Poison Defaults
Formulas: None (persistence only)
Reads: QAGateRejection (from qa_gate.py)
Writes: edge_evidence_quarantine_v1 (for audit/debug, never pooled)
Gates: None (downstream of QA gates)

Purpose: Persist rejected records to a quarantine table so they are
         available for audit but never enter the pooling pipeline.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from crci.extraction.tb_trust_boundary.qa_gate import QAGateRejection
from crci.shared.models.tables import EdgeEvidenceQuarantine

logger = logging.getLogger(__name__)


def write_quarantined_records(
    session: Session,
    rejections: list[QAGateRejection],
    extraction_run_id: str,
    paper_id: str | None = None,
    study_id: str | None = None,
) -> int:
    """Persist QA-rejected records to edge_evidence_quarantine_v1.

    Args:
        session: Active database session.
        rejections: List of QAGateRejection from run_qa_gates().
        extraction_run_id: Current extraction run ID for provenance.
        paper_id: Paper identifier.
        study_id: Study identifier.

    Returns:
        Number of quarantine rows written.
    """
    if not rejections:
        return 0

    written = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for rejection in rejections:
        snap = rejection.record_snapshot
        qid = f"QRN_{uuid.uuid4().hex[:12]}"

        row = EdgeEvidenceQuarantine(
            quarantine_id=qid,
            extraction_run_id=extraction_run_id,
            paper_id=paper_id,
            study_id=study_id or paper_id,
            edge_relation_id=snap.get("edge_relation_id"),
            effect_value=snap.get("value"),
            se=snap.get("se"),
            ci_lower=snap.get("ci_lower"),
            ci_upper=snap.get("ci_upper"),
            p_value=snap.get("p_value"),
            n=snap.get("n"),
            label_type=snap.get("label_type"),
            original_text=snap.get("original_text"),
            grouping_id=snap.get("grouping_id"),
            reject_gate=rejection.gate_id,
            reject_reason=rejection.reject_reason,
            reject_details=rejection.details,
            quarantined_at=now_iso,
        )

        try:
            session.add(row)
            written += 1
        except Exception as exc:
            logger.warning(
                "Failed to quarantine record (gate=%s, reason=%s): %s",
                rejection.gate_id,
                rejection.reject_reason,
                exc,
            )

    if written > 0:
        session.flush()
        logger.info(
            "Quarantine: %d/%d rejected records persisted to "
            "edge_evidence_quarantine_v1 for run %s",
            written,
            len(rejections),
            extraction_run_id,
        )

    return written
