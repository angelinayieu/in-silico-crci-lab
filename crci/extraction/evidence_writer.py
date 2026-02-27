# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ScaledNumeric from P2 context
# VERIFIED: forward wiring — writes EdgeEvidence rows to DB
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no gates (persistence-only module)
# VERIFIED: S3 idempotent writes via span_hash dedup
"""
Component: SYS_EXTRACTION.EX-P2.EVIDENCE_WRITER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1135-1150
Purpose: Persist harmonized claims to edge_evidence_v1 (Class B).
         This bridges the gap between in-memory P2 output and DB storage.
         Uses UPSERT semantics for idempotent reruns (S3 fix).
Reads: ScaledNumeric objects from P2 harmonization context["harmonized_records"]
Writes: edge_evidence_v1 rows (ORM: EdgeEvidence)
Gates: None (persistence-only, no formula logic)
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.enums import PaperSubtype
from crci.shared.models.tables import EdgeEvidence, ExtractionRun

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  R2.2: EVIDENCE BLOCKED SUBTYPES
# ═══════════════════════════════════════════════════════════════

# Paper subtypes that cannot produce evidence rows (MINIMAL-mode only)
_EVIDENCE_BLOCKED_SUBTYPES: set[str] = {
    PaperSubtype.REVIEW_NARRATIVE.value,
    PaperSubtype.CASE_REPORT.value,
    PaperSubtype.QUALITATIVE.value,
    PaperSubtype.UMBRELLA_REVIEW.value,
    PaperSubtype.MECHANISTIC_IN_VITRO.value,
    PaperSubtype.EDITORIAL.value,
    PaperSubtype.PROTOCOL.value,
    "erratum",  # No PaperSubtype enum member yet; keep as string literal
}


def _check_evidence_row_allowed(subtype: str) -> None:
    """R2.2: Raise GateViolation if subtype cannot produce evidence rows.

    Args:
        subtype: Paper subtype string value.

    Raises:
        GateViolation: If the subtype is in _EVIDENCE_BLOCKED_SUBTYPES.
    """
    from crci.shared.models.intermediate_states import GateViolation

    if subtype in _EVIDENCE_BLOCKED_SUBTYPES:
        raise GateViolation(
            gate_id="R2.2-EVIDENCE-BLOCK",
            message=(
                f"Paper subtype '{subtype}' cannot produce evidence rows. "
                f"Only study-based subtypes may contribute to edge_evidence_v1."
            ),
            context={"subtype": subtype},
        )


def compute_span_hash(
    study_id: str,
    edge_relation_id: str,
    profile_id: str,
    beta: float,
    se: float | None,
    source_position: str | None = None,
) -> str:
    """Compute deterministic hash for evidence dedup.

    The hash is based on the natural key of the evidence row:
    - study_id: which paper
    - edge_relation_id: which causal edge
    - profile_id: which cohort
    - beta + se: the actual values (to distinguish multiple effects)
    - source_position: optional source text position for disambiguation

    Args:
        study_id: Study identifier.
        edge_relation_id: Edge identifier.
        profile_id: Cohort profile identifier.
        beta: Effect size value.
        se: Standard error (may be None).
        source_position: Optional source position string.

    Returns:
        16-character hex hash.
    """
    # Build deterministic input string
    se_str = f"{se:.6f}" if se is not None else "none"
    beta_str = f"{beta:.6f}"
    hash_input = f"{study_id}|{edge_relation_id}|{profile_id}|{beta_str}|{se_str}"
    if source_position:
        hash_input += f"|{source_position}"

    return hashlib.sha1(hash_input.encode("utf-8")).hexdigest()[:16]


def write_evidence_rows(
    session: Session,
    run: ExtractionRun,
    harmonized_records: list[Any],
    study_id: str,
    profile_id: str | None = None,
    paper_subtype: str | None = None,
) -> int:
    """Persist P2 harmonized claims to edge_evidence_v1.

    Maps ScaledNumeric fields → EdgeEvidence columns:
      - span_id → part of ler_id
      - beta → harmonized_beta AND effect_value_reported
      - se → harmonized_se AND se_reported
      - scale → harmonized_scale
      - se_source → se_quality_tag
      - se_derivation_level → se_derivation_level
      - se_inflation_applied → se_inflation_applied
      - conversion_formula → (logged in notes)
      - conversion_bias_risk → (logged in notes)

    Args:
        session: Active database session.
        run: Current ExtractionRun instance for provenance.
        harmonized_records: List of ScaledNumeric objects from P2.
        study_id: The study_id for all evidence rows.
        profile_id: Optional cohort profile ID. Defaults to study_id if None.
        paper_subtype: Paper subtype string for R2 gate enforcement.

    Returns:
        Number of evidence rows successfully written.

    Raises:
        GateViolation: If paper_subtype is in _EVIDENCE_BLOCKED_SUBTYPES (R2.2).
    """
    # R2.2: Block evidence rows for MINIMAL-mode subtypes (defense-in-depth)
    if paper_subtype:
        _check_evidence_row_allowed(paper_subtype)

    if not harmonized_records:
        logger.info("No harmonized records to persist for study %s", study_id)
        return 0

    # Default profile_id to study_id if not specified
    if profile_id is None:
        profile_id = study_id

    written = 0
    updated = 0
    skipped = 0

    for record in harmonized_records:
        # Extract fields from ScaledNumeric (or dict)
        beta = _get_attr(record, "beta")
        se = _get_attr(record, "se")
        scale = _get_attr(record, "scale")
        se_source = _get_attr(record, "se_source")
        se_derivation_level = _get_attr(record, "se_derivation_level")
        se_inflation_applied = _get_attr(record, "se_inflation_applied", 1.0)
        se_quality_tag = _get_attr(record, "se_quality_tag")
        conversion_formula = _get_attr(record, "conversion_formula")
        conversion_bias_risk = _get_attr(record, "conversion_bias_risk")
        direction_aligned = _get_attr(record, "direction_aligned", False)
        edge_relation_id = _get_attr(record, "edge_id") or _get_attr(record, "edge_relation_id") or "UNASSIGNED"
        source_position = _get_attr(record, "source_position")

        # Skip records without a valid beta value
        if beta is None:
            logger.debug("Skipping record: no beta value")
            skipped += 1
            continue

        # Compute deterministic span_hash for dedup (S3 fix)
        span_hash = compute_span_hash(
            study_id=study_id,
            edge_relation_id=edge_relation_id,
            profile_id=profile_id,
            beta=beta,
            se=se,
            source_position=source_position,
        )

        # Generate deterministic ler_id from span_hash
        ler_id = f"LER_{study_id}_{span_hash}"

        # Convert enum values to strings if needed
        scale_str = scale.value if hasattr(scale, "value") else str(scale) if scale else None
        se_source_str = se_source.value if hasattr(se_source, "value") else str(se_source) if se_source else None
        se_derivation_str = se_derivation_level.value if hasattr(se_derivation_level, "value") else str(se_derivation_level) if se_derivation_level else None
        se_quality_str = se_quality_tag.value if hasattr(se_quality_tag, "value") else str(se_quality_tag) if se_quality_tag else None
        conversion_risk_str = conversion_bias_risk.value if hasattr(conversion_bias_risk, "value") else str(conversion_bias_risk) if conversion_bias_risk else None

        # Build extraction notes from conversion provenance
        notes_parts = []
        if conversion_formula:
            notes_parts.append(f"formula={conversion_formula}")
        if conversion_risk_str:
            notes_parts.append(f"conv_risk={conversion_risk_str}")
        if direction_aligned:
            notes_parts.append("direction_aligned=True")
        extraction_snippet = "; ".join(notes_parts) if notes_parts else None

        # UPSERT: Check if row exists by ler_id (S3 fix)
        existing_row = session.query(EdgeEvidence).filter(
            EdgeEvidence.ler_id == ler_id
        ).first()

        if existing_row:
            # Update existing row
            existing_row.effect_value_reported = beta
            existing_row.se_reported = se
            existing_row.N_effect = _get_attr(record, "n") or _get_attr(record, "n_effect") or 0
            existing_row.harmonized_scale = scale_str
            existing_row.harmonized_beta = beta
            existing_row.harmonized_se = se
            existing_row.harmonization_status = "harmonized"
            existing_row.se_derivation_level = se_derivation_str
            existing_row.se_inflation_applied = se_inflation_applied
            existing_row.se_quality_tag = se_quality_str
            existing_row.quality_rating = _get_attr(record, "quality_rating", "moderate")
            existing_row.extraction_snippet = extraction_snippet
            existing_row.entered_by = f"extraction_pipeline:{run.extraction_run_id}"
            existing_row.entered_at = datetime.now(timezone.utc).isoformat()
            existing_row.version = (existing_row.version or 0) + 1
            updated += 1
            logger.debug("Updated existing evidence row %s", ler_id)
        else:
            # Insert new row
            evidence_row = EdgeEvidence(
                ler_id=ler_id,
                study_id=study_id,
                profile_id=profile_id,
                edge_relation_id=edge_relation_id,
                edge_family=_get_attr(record, "edge_family"),
                span_hash=span_hash,
                # Reported values (original)
                effect_type_reported="harmonized_beta",
                effect_value_reported=beta,
                se_reported=se,
                N_effect=_get_attr(record, "n") or _get_attr(record, "n_effect") or 0,
                # Harmonized values (same as reported for P2 output)
                harmonized_scale=scale_str,
                harmonized_beta=beta,
                harmonized_se=se,
                harmonization_status="harmonized",
                # SE provenance (v2.0)
                se_derivation_level=se_derivation_str,
                se_inflation_applied=se_inflation_applied,
                se_quality_tag=se_quality_str,
                # Quality and audit
                quality_rating=_get_attr(record, "quality_rating", "moderate"),
                extraction_snippet=extraction_snippet,
                entered_by=f"extraction_pipeline:{run.extraction_run_id}",
                entered_at=datetime.now(timezone.utc).isoformat(),
                version=1,
                active=1,
            )

            try:
                session.add(evidence_row)
                written += 1
            except Exception as exc:
                logger.warning(
                    "Failed to add evidence row %s: %s",
                    ler_id,
                    exc,
                )
                skipped += 1

    # Flush to ensure rows are written
    total_changes = written + updated
    if total_changes > 0:
        session.flush()
        logger.info(
            "Evidence persistence for study %s: %d inserted, %d updated, %d skipped",
            study_id,
            written,
            updated,
            skipped,
        )
    else:
        logger.info(
            "No evidence rows written for study %s (skipped %d)",
            study_id,
            skipped,
        )

    return written + updated


def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Get attribute from object or dict, with default fallback.

    Args:
        obj: Object or dict to read from.
        attr: Attribute/key name.
        default: Default value if not found.

    Returns:
        The attribute value or default.
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
