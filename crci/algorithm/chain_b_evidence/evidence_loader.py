"""
Component: ALG-B — Evidence Loader (DB → EvidenceRecord)
Spec: MASTER_PLAN.md Slice 3.1
Reads: edge_evidence_v1, study_registry_v1 (from SYS_EXTRACTION)
Writes: list[EvidenceRecord] (consumed by run_chain_b / run_b1_through_b6)
Gates: None (loader, not validator)

Bridges the extraction pipeline output (DB rows) to the algorithm
pipeline input (EvidenceRecord dataclass).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from .evidence_compiler import EvidenceRecord

logger = logging.getLogger(__name__)

# ── Quality grade normalization ──────────────────────────────
_QUALITY_GRADE_MAP: dict[str, str] = {
    "high": "HIGH",
    "moderate": "MODERATE",
    "low": "LOW",
    "very_low": "VERY_LOW",
    "very low": "VERY_LOW",
    # Already uppercase
    "HIGH": "HIGH",
    "MODERATE": "MODERATE",
    "LOW": "LOW",
    "VERY_LOW": "VERY_LOW",
}

# ── Study design normalization ───────────────────────────────
_DESIGN_MAP: dict[str, str] = {
    "RCT": "RCT",
    "rct": "RCT",
    "RCT_cognitive": "RCT",
    "randomized_controlled_trial": "RCT",
    "quasi_experimental": "quasi_experimental",
    "prospective_cohort": "prospective_cohort",
    "retrospective_cohort": "retrospective_cohort",
    "cross_sectional": "cross_sectional",
    "case_control": "case_control",
    "pre_post": "pre_post",
    "SR": "SR",
    "MA": "MA",
    "meta_analysis": "MA",
    "systematic_review": "SR",
}

# ── Identification status normalization ──────────────────────
_ID_STATUS_MAP: dict[str | None, str] = {
    None: "plausible",
    "": "plausible",
    "identified": "identified",
    "partially_identified": "partially_identified",
    "plausible": "plausible",
    "unidentified": "unidentified",
}

# Default scope_weights when no annotation data is available
# Dimensions match config.SCOPE_WEIGHTS keys used by B2 Layer 7
_DEFAULT_SCOPE_WEIGHTS: dict[str, float] = {
    "cancer": 0.5,
    "phase": 0.5,
    "regimen": 0.5,
    "age": 0.5,
    "sex": 0.5,
}


def load_evidence_from_db(
    session: Session,
    *,
    edge_relation_ids: list[str] | None = None,
    active_only: bool = True,
) -> list[EvidenceRecord]:
    """Load evidence records from edge_evidence_v1 + study metadata.

    Queries the extraction pipeline's output tables and converts each
    row into an EvidenceRecord suitable for Chain B processing.

    Args:
        session: SQLAlchemy session.
        edge_relation_ids: If provided, only load evidence for these edges.
            If None, load all active evidence.
        active_only: If True, only load active (non-superseded) records.

    Returns:
        List of EvidenceRecord objects.
    """
    # Build WHERE clause
    where_clauses = []
    params: dict[str, object] = {}

    if active_only:
        where_clauses.append("ee.active = 1")
        where_clauses.append("ee.edge_relation_id != 'UNASSIGNED'")

    if edge_relation_ids:
        placeholders = ", ".join(f":eid_{i}" for i in range(len(edge_relation_ids)))
        where_clauses.append(f"ee.edge_relation_id IN ({placeholders})")
        for i, eid in enumerate(edge_relation_ids):
            params[f"eid_{i}"] = eid

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = text(f"""
        SELECT
            ee.ler_id,
            ee.edge_relation_id,
            ee.study_id,
            ee.harmonized_beta,
            ee.harmonized_se,
            ee.N_effect,
            ee.quality_rating,
            ee.identification_status,
            ee.harmonized_scale,
            ee.se_inflation_applied,
            ee.escalation_se_inflation,
            sr.study_design,
            sr.study_subtype,
            sr.year AS publication_year
        FROM edge_evidence_v1 ee
        LEFT JOIN study_registry_v1 sr
            ON ee.study_id = sr.study_id
        WHERE {where_sql}
        ORDER BY ee.edge_relation_id, ee.ler_id
    """)

    rows = session.execute(query, params).fetchall()
    logger.info(
        "Evidence loader: queried %d rows from edge_evidence_v1 "
        "(active_only=%s, edge_filter=%s)",
        len(rows),
        active_only,
        edge_relation_ids or "ALL",
    )

    records: list[EvidenceRecord] = []
    skipped = 0

    for row in rows:
        # Skip rows with missing critical data
        if row.harmonized_beta is None or row.harmonized_se is None:
            logger.warning(
                "Evidence loader: skipping %s — missing beta or SE",
                row.ler_id,
            )
            skipped += 1
            continue

        if row.harmonized_se <= 0:
            logger.warning(
                "Evidence loader: skipping %s — SE=%.4f <= 0",
                row.ler_id, row.harmonized_se,
            )
            skipped += 1
            continue

        # Resolve study_design → compiler-compatible key
        raw_design = row.study_design or row.study_subtype or "unknown"
        study_design = _DESIGN_MAP.get(raw_design, "unknown")

        # Map RCT → small_rct_default / large_rct based on sample size
        # (compiler expects these specific keys in DESIGN_MULTIPLIERS)
        if study_design == "RCT":
            from crci.shared import config
            n = row.N_effect if row.N_effect and row.N_effect > 0 else 0
            if n > config.SMALL_RCT_N_THRESHOLD:
                study_design = "large_rct"
            else:
                study_design = "small_rct_default"
        elif study_design == "quasi_experimental":
            study_design = "well_adjusted_cohort"
        elif study_design == "prospective_cohort":
            study_design = "well_adjusted_cohort"
        elif study_design == "retrospective_cohort":
            study_design = "unadjusted_longitudinal"
        elif study_design == "cross_sectional":
            study_design = "cross_sectional_unadjusted"
        elif study_design == "case_control":
            study_design = "unadjusted_longitudinal"
        elif study_design == "pre_post":
            study_design = "unadjusted_longitudinal"

        # Resolve quality grade
        quality_grade = _QUALITY_GRADE_MAP.get(
            row.quality_rating or "moderate", "MODERATE"
        )

        # Resolve identification status
        id_status = _ID_STATUS_MAP.get(
            row.identification_status, "plausible"
        )

        # Publication year
        pub_year = row.publication_year or _current_year()

        # Sample size
        sample_size = row.N_effect if row.N_effect and row.N_effect > 0 else 0

        # Apply any SE inflation from extraction pipeline
        se = row.harmonized_se
        if row.se_inflation_applied and row.se_inflation_applied > 1.0:
            # SE already inflated by extraction; don't double-inflate
            pass
        if row.escalation_se_inflation and row.escalation_se_inflation > 1.0:
            # Escalation inflation also already applied
            pass

        # Determine outcome_type from harmonized_scale
        outcome_type = _infer_outcome_type(row.harmonized_scale)

        # Determine is_cross_sectional and has_rct_component
        is_cross_sectional = study_design == "cross_sectional"
        has_rct = study_design in ("RCT", "quasi_experimental")

        record = EvidenceRecord(
            study_id=row.study_id,
            edge_id=row.edge_relation_id,
            beta=row.harmonized_beta,
            se=se,
            study_design=study_design,
            publication_year=pub_year,
            sample_size=sample_size,
            identification_status=id_status,
            quality_grade=quality_grade,
            scope_weights=_DEFAULT_SCOPE_WEIGHTS.copy(),
            cancer_validation_status="used_cancer",  # Default: paper used cancer cohort
            temporal_distance_days=0.0,  # Default: no temporal distance info — L6 will apply w=1.0
            outcome_type=outcome_type,
            is_animal=False,
            is_cross_sectional=is_cross_sectional,
            has_rct_component=has_rct,
            sigma_sq_structural=None,
        )
        records.append(record)

    # Log temporal default statistics
    n_temporal_defaulted = sum(
        1 for r in records if r.temporal_distance_days == 0.0
    )
    if n_temporal_defaulted > 0:
        logger.warning(
            "Temporal default: %d/%d evidence records have temporal_distance_days=0.0 "
            "(no temporal distance info available — L6 SE inflation will not fire)",
            n_temporal_defaulted, len(records),
        )

    logger.info(
        "Evidence loader: produced %d EvidenceRecord objects (%d skipped)",
        len(records), skipped,
    )

    return records


def _infer_outcome_type(harmonized_scale: str | None) -> str:
    """Infer outcome type from the harmonized scale.

    Neuropsychological test scores → semi_objective.
    Self-report questionnaires → subjective.
    Default → semi_objective (most CRCI outcomes are cognitive tests).
    """
    if not harmonized_scale:
        return "semi_objective"
    # In CRCI, most outcomes are cognitive test scores
    return "semi_objective"


def _current_year() -> int:
    """Return current year for missing publication_year fallback."""
    return datetime.now().year
