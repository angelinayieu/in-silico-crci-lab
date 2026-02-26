# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ScaledNumeric from P2 context
# VERIFIED: forward wiring — writes EdgeEvidence rows to DB
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no gates (persistence-only module)
"""
Component: SYS_EXTRACTION.EX-P2.EVIDENCE_WRITER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1135-1150
Purpose: Persist harmonized claims to edge_evidence_v1 (Class B).
         This bridges the gap between in-memory P2 output and DB storage.
Reads: ScaledNumeric objects from P2 harmonization context["harmonized_records"]
Writes: edge_evidence_v1 rows (ORM: EdgeEvidence)
Gates: None (persistence-only, no formula logic)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import EdgeEvidence, ExtractionRun

logger = logging.getLogger(__name__)


def write_evidence_rows(
    session: Session,
    run: ExtractionRun,
    harmonized_records: list[Any],
    study_id: str,
    profile_id: str | None = None,
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

    Returns:
        Number of evidence rows successfully written.
    """
    if not harmonized_records:
        logger.info("No harmonized records to persist for study %s", study_id)
        return 0

    # Default profile_id to study_id if not specified
    if profile_id is None:
        profile_id = study_id

    written = 0
    skipped = 0

    for record in harmonized_records:
        # Extract fields from ScaledNumeric (or dict)
        span_id = _get_attr(record, "span_id", f"span_{uuid.uuid4().hex[:8]}")
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

        # Skip records without a valid beta value
        if beta is None:
            logger.debug(
                "Skipping record %s: no beta value",
                span_id,
            )
            skipped += 1
            continue

        # Generate unique LER ID
        ler_id = f"LER_{study_id}_{span_id}_{uuid.uuid4().hex[:8]}"

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

        # Create EdgeEvidence row
        evidence_row = EdgeEvidence(
            ler_id=ler_id,
            study_id=study_id,
            profile_id=profile_id,
            edge_relation_id=_get_attr(record, "edge_id") or _get_attr(record, "edge_relation_id") or "UNASSIGNED",
            edge_family=_get_attr(record, "edge_family"),
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
    if written > 0:
        session.flush()
        logger.info(
            "Persisted %d evidence rows for study %s (skipped %d)",
            written,
            study_id,
            skipped,
        )
    else:
        logger.info(
            "No evidence rows written for study %s (skipped %d)",
            study_id,
            skipped,
        )

    return written


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
