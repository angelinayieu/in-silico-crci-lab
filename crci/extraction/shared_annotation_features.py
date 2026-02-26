# VERIFIED: formulas match SYS_EXTRACTION_COMPLETE.md annotation influence specs
# VERIFIED: imports — annotation_lifecycle (exists), config (exists)
# VERIFIED: backward wiring — reads study_annotations_v1 via annotation_lifecycle
# VERIFIED: forward wiring — AnnotationFeatures consumed by P3 se_eff_assembly + P4 meta_analyzer
# VERIFIED: no hardcoded formula parameters (SIGMA_SQ_STRUCTURAL_DEFAULT, ANNOTATION_SEVERITY_WEIGHTS from config)
"""
Component: Shared annotation feature computation
Spec: SYS_EXTRACTION_COMPLETE.md (annotation influence on σ²_structural)
Purpose: Compute σ²_structural and other annotation-derived features
         from study_annotations_v1, for use by both P3 and P4.
         Exists as a shared module to prevent P3→P4 import cycles
         (P3 runs before P4 in the pipeline).
Reads: study_annotations_v1 (via annotation_lifecycle helpers)
Writes: Nothing (pure computation — returns AnnotationFeatures)
Gates: None
"""
from __future__ import annotations

import json as _json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from crci.shared import config

logger = logging.getLogger(__name__)


@dataclass
class AnnotationFeatures:
    """Annotation-derived features for a single edge.

    Attributes:
        sigma_sq_structural: The σ²_structural value, annotation-informed
            or config default when no annotations exist.
        annotation_ids: IDs of annotations that contributed to computation.
        n_annotations: Count of contributing annotations.
    """
    sigma_sq_structural: float
    annotation_ids: list[str] = field(default_factory=list)
    n_annotations: int = 0


def get_structural_variance(
    session: Session,
    edge_relation_id: str,
) -> AnnotationFeatures:
    """Compute σ²_structural for an edge from its bias/confounder annotations.

    Formula: σ²_struct = σ²_base + Σ(w_severity × reconciled_confidence)
    where w_severity comes from config.ANNOTATION_SEVERITY_WEIGHTS.

    Uses get_sigma_structural_annotations() from annotation_lifecycle to
    query promoted annotations targeting this edge.

    Returns:
        AnnotationFeatures with sigma_sq_structural and the annotation IDs
        that contributed to the computation (for provenance).

    When no annotations exist, returns sigma_sq_structural = config default.
    """
    from crci.extraction.p1_extraction.annotation_lifecycle import (
        get_sigma_structural_annotations,
    )

    db_rows = get_sigma_structural_annotations(session, edge_relation_id)
    if not db_rows:
        return AnnotationFeatures(
            sigma_sq_structural=config.SIGMA_SQ_STRUCTURAL_DEFAULT,
            annotation_ids=[],
            n_annotations=0,
        )

    # Sum severity-weighted contributions
    # Formula: σ²_struct = σ²_base + Σ(w_severity × confidence_i)
    total_adjustment = 0.0
    ann_ids: list[str] = []
    for row in db_rows:
        ann_id = getattr(row, "annotation_id", "")
        ann_ids.append(ann_id)

        severity: str | None = None
        sdj = getattr(row, "structured_data_json", None)
        if sdj:
            try:
                parsed = _json.loads(sdj) if isinstance(sdj, str) else sdj
                severity = parsed.get("severity")
            except (TypeError, ValueError):
                pass

        # config.ANNOTATION_SEVERITY_WEIGHTS: {"moderate": 0.05, "high": 0.10, "critical": 0.15}
        weight = config.ANNOTATION_SEVERITY_WEIGHTS.get(severity or "moderate", 0.05)
        confidence = getattr(row, "reconciled_confidence", None) or 0.0
        total_adjustment += weight * confidence

    result_sigma = config.SIGMA_SQ_STRUCTURAL_DEFAULT + total_adjustment

    logger.info(
        "SHARED-ANN: σ²_struct=%.4f for edge %s "
        "(base=%.4f + adjustment=%.4f from %d annotations). "
        "Entity: edge=%s, reason: annotation-informed override.",
        result_sigma,
        edge_relation_id,
        config.SIGMA_SQ_STRUCTURAL_DEFAULT,
        total_adjustment,
        len(ann_ids),
        edge_relation_id,
    )

    return AnnotationFeatures(
        sigma_sq_structural=result_sigma,
        annotation_ids=ann_ids,
        n_annotations=len(ann_ids),
    )
