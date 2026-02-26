# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads enriched dict from standardization.py
# VERIFIED: forward wiring — writes EdgeEvidence to DB, quarantine on failure
# VERIFIED: uses compute_evidence_identity from study_identity.py (Slice 0)
# VERIFIED: no hardcoded formula parameters
"""
Component: Extraction — Evidence Persistence (Dedup + Insert/Update + Quarantine)
Spec: IMPLEMENTATION_SLICES.md Slice 5, Step 5c
Formulas: None (persistence logic)
Reads: Enriched dict from standardization.py
Writes: EdgeEvidence row to edge_evidence_v1, or
        EvidenceValidationQuarantine row to evidence_validation_quarantine_v1
Gates: None (persistence-only)

Uses compute_evidence_identity() from Slice 0 for deterministic dedup.
UPSERT semantics: if ler_id exists → update non-identity fields; else INSERT.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from crci.shared.models.tables import EdgeEvidence, EvidenceValidationQuarantine
from crci.shared.study_identity import compute_evidence_identity

logger = logging.getLogger(__name__)


def _get(row: dict, key: str) -> str:
    """Get a stripped string value from row, or empty string."""
    val = row.get(key)
    if val is None:
        return ""
    return str(val).strip()


def _get_float(row: dict, key: str) -> float | None:
    """Get a float value from row, or None."""
    val = _get(row, key)
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_int(row: dict, key: str) -> int | None:
    """Get an int value from row, or None."""
    val = _get(row, key)
    if not val:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def compute_writer_identity(row: dict[str, Any]) -> str:
    """Compute deterministic identity hash for dedup.

    Delegates to compute_evidence_identity() from study_identity.py (Slice 0).
    Maps CSV column names to identity field names if needed.

    Args:
        row: Dict with evidence row fields.

    Returns:
        ler_id string ("ler_" + 16-char hex hash).
    """
    # Map edge_id → edge_relation_id for the identity function
    identity_row = dict(row)
    if "edge_relation_id" not in identity_row and "edge_id" in identity_row:
        identity_row["edge_relation_id"] = identity_row["edge_id"]

    # Ensure study_id is present (derive from doi if needed)
    if not identity_row.get("study_id"):
        doi = identity_row.get("doi", "")
        if doi:
            identity_row["study_id"] = f"doi:{doi}"

    return compute_evidence_identity(identity_row)


def write_validated_row(
    session: Any,
    row: dict[str, Any],
) -> str:
    """Write a validated + standardized evidence row to edge_evidence_v1.

    UPSERT semantics: if an existing row with the same ler_id exists,
    update non-identity columns. Otherwise, INSERT a new row.

    Args:
        session: SQLAlchemy session (caller manages transaction).
        row: Fully validated and standardized dict.

    Returns:
        ler_id of the written row.
    """
    ler_id = compute_writer_identity(row)

    # Check for existing row (UPSERT)
    existing = session.get(EdgeEvidence, ler_id)

    if existing is not None:
        # UPDATE non-identity fields
        _update_evidence_row(existing, row)
        logger.info("UPSERT update: ler_id=%s (existing row updated)", ler_id)
        return ler_id

    # INSERT new row
    edge_id = _get(row, "edge_relation_id") or _get(row, "edge_id")
    study_id = _get(row, "study_id") or f"doi:{_get(row, 'doi')}"

    evidence = EdgeEvidence(
        ler_id=ler_id,
        edge_relation_id=edge_id,
        profile_id=_get(row, "profile_id") or "default",
        study_id=study_id,

        # Effect size fields
        effect_type_reported=_get(row, "effect_type_reported") or _get(row, "effect_type_original"),
        effect_value_reported=_get_float(row, "beta_raw") or 0.0,
        se_reported=_get_float(row, "se_raw"),
        ci_low_reported=_get_float(row, "ci_low"),
        ci_high_reported=_get_float(row, "ci_high"),
        p_value=_get_float(row, "p_value"),
        N_effect=_get_int(row, "sample_size") or 0,

        # Harmonized values (from standardization)
        harmonized_beta=row.get("harmonized_beta"),
        harmonized_se=row.get("harmonized_se"),
        harmonized_scale="cohen_d",

        # SE derivation provenance
        se_derivation_level=_get(row, "se_derivation_level"),
        conversion_formula=_get(row, "conversion_formula"),

        # Layer inputs (from compute_layer_inputs)
        quality_rating=_get(row, "rob_grade_canonical") or _get(row, "rob_overall") or "moderate",
        rob_overall=_get(row, "rob_overall"),

        # Shared control & dedup fields
        shared_control_flag=_get(row, "shared_control_flag") == "1",
        endpoint_vs_change=_get(row, "endpoint_vs_change"),
        comparison_arm_label=_get(row, "comparison_arm_label"),

        # Metadata
        effect_size_type=_get(row, "effect_size_context") or _get(row, "effect_size_type"),
        covariates_adjusted=_get(row, "covariates_adjusted"),
        notes=_get(row, "confidence_note"),
        entered_by=_get(row, "source") or "validated_writer",
        entered_at=datetime.now(timezone.utc).isoformat(),
        version=1,
        active=1,

        # Span hash for backward compat with evidence_writer.py dedup
        span_hash=ler_id,
    )

    session.add(evidence)
    logger.info(
        "INSERT: ler_id=%s study=%s edge=%s d=%.4f SE=%s",
        ler_id, study_id, edge_id,
        row.get("harmonized_beta", 0.0) or 0.0,
        row.get("harmonized_se"),
    )
    return ler_id


def _update_evidence_row(existing: EdgeEvidence, row: dict[str, Any]) -> None:
    """Update non-identity columns on an existing EdgeEvidence row."""
    # Only update if new values are present (don't overwrite with None)
    if row.get("harmonized_beta") is not None:
        existing.harmonized_beta = row["harmonized_beta"]
    if row.get("harmonized_se") is not None:
        existing.harmonized_se = row["harmonized_se"]
    if row.get("se_derivation_level"):
        existing.se_derivation_level = row["se_derivation_level"]
    if row.get("conversion_formula"):
        existing.conversion_formula = row["conversion_formula"]
    if row.get("rob_overall"):
        existing.rob_overall = row["rob_overall"]
    if row.get("quality_rating") or row.get("rob_grade_canonical"):
        existing.quality_rating = row.get("rob_grade_canonical") or row.get("quality_rating")
    existing.entered_at = datetime.now(timezone.utc).isoformat()
    existing.version = (existing.version or 0) + 1


def quarantine_row(
    session: Any,
    row: dict[str, Any],
    errors: list[str],
    source: str = "unknown",
) -> str:
    """Write an invalid evidence row to the quarantine table.

    Args:
        session: SQLAlchemy session.
        row: The raw (unvalidated) dict.
        errors: List of validation error strings.
        source: Write path identifier ('llm', 'manual_csv', 'bulk_loader', 'test').

    Returns:
        quarantine_id string.
    """
    study_id = _get(row, "study_id") or f"doi:{_get(row, 'doi')}"
    edge_id = _get(row, "edge_relation_id") or _get(row, "edge_id")

    # Deterministic quarantine ID for idempotent reruns
    quar_input = f"{study_id}|{edge_id}|{source}|{json.dumps(errors, sort_keys=True)}"
    quarantine_id = "quar_" + hashlib.sha256(quar_input.encode()).hexdigest()[:16]

    q_row = EvidenceValidationQuarantine(
        quarantine_id=quarantine_id,
        study_id=study_id,
        edge_relation_id=edge_id,
        source_path=source,
        raw_payload_json=json.dumps(row, default=str),
        validation_errors=json.dumps(errors),
        quarantine_reason="validation_failure",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    session.add(q_row)
    logger.warning(
        "QUARANTINED %s×%s from %s: %s",
        study_id, edge_id, source, "; ".join(errors),
    )
    return quarantine_id
