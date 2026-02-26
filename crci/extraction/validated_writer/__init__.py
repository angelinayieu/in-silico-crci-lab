# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads dict row from any write path
# VERIFIED: forward wiring — writes EdgeEvidence to DB via persistence.py
# VERIFIED: no hardcoded formula parameters
"""
Component: Extraction — Validated Evidence Writer (Package Entry Point)
Spec: IMPLEMENTATION_SLICES.md Slice 5
Purpose: Single chokepoint for ALL evidence writes into edge_evidence_v1.
         All three write paths (LLM pipeline, manual CSV, bulk loader) must
         route through write_evidence_row() to ensure consistent validation,
         standardization, and persistence.

Pipeline:
    1. validate_evidence_row()    → reject bad rows
    2. standardize_effect_size()  → convert to Cohen's d
    3. harmonize_sign()           → canonical sign convention
    4. derive_se()                → SE cascade (L1-L6)
    5. compute_layer_inputs()     → map to P3-layer canonical keys
    6. write_validated_row()      → UPSERT to edge_evidence_v1

Reads: dict row from CSV/LLM/bulk paths
Writes: EdgeEvidence row to DB, or quarantine on failure
"""
from __future__ import annotations

import logging
from typing import Any

from crci.extraction.validated_writer.persistence import (
    compute_writer_identity,
    quarantine_row,
    write_validated_row,
)
from crci.extraction.validated_writer.standardization import (
    compute_layer_inputs,
    derive_se,
    harmonize_sign,
    standardize_effect_size,
)
from crci.extraction.validated_writer.validation import validate_evidence_row

logger = logging.getLogger(__name__)

# Re-export key symbols for external consumers
__all__ = [
    "write_evidence_row",
    "validate_evidence_row",
    "standardize_effect_size",
    "harmonize_sign",
    "derive_se",
    "compute_layer_inputs",
    "compute_writer_identity",
    "quarantine_row",
    "write_validated_row",
]


def write_evidence_row(
    session: Any,
    row: dict[str, Any],
    source: str = "unknown",
) -> str | None:
    """Single entry point for all evidence writes.

    Orchestrates the full validation → standardization → persistence pipeline.
    Valid rows are written to edge_evidence_v1. Invalid rows are quarantined
    in evidence_validation_quarantine_v1 with full error details.

    Args:
        session: SQLAlchemy session (caller manages transaction).
        row: Dict with evidence row fields (from any write path).
        source: Write path identifier for audit trail
                ('llm', 'manual_csv', 'bulk_loader').

    Returns:
        ler_id if row was written successfully, None if quarantined.
    """
    # Store source for persistence
    row = dict(row)  # shallow copy
    row["source"] = source

    # 1. Validate
    is_valid, errors = validate_evidence_row(row, session)
    if not is_valid:
        quarantine_row(session, row, errors, source)
        return None

    # 2. Standardize effect size → Cohen's d
    row = standardize_effect_size(row)

    # 3. Harmonize sign → positive = benefit
    row = harmonize_sign(row)

    # 4. Derive SE via cascade
    row = derive_se(row)

    # 5. Compute layer inputs (study_design → L1, cancer_validated → L4, etc.)
    row = compute_layer_inputs(row)

    # 6. Persist (UPSERT)
    ler_id = write_validated_row(session, row)

    logger.info(
        "WRITE_EVIDENCE_ROW: %s → ler_id=%s (source=%s, d=%.4f, SE=%s, sign_flipped=%s)",
        row.get("study_id") or row.get("doi"),
        ler_id,
        source,
        row.get("harmonized_beta", 0.0) or 0.0,
        row.get("harmonized_se"),
        row.get("sign_flipped"),
    )

    return ler_id
