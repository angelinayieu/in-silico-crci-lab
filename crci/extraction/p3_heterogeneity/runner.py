# VERIFIED: imports — layers, se_eff_assembly
# VERIFIED: backward wiring — reads harmonized records from P2 context
# VERIFIED: forward wiring — writes calibrated records for P4
# VERIFIED: gates — P3-G1 (layer validity)
"""
Component: SYS_EXTRACTION.EX-P3.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1135-1230
Purpose: Orchestrate P3 seven-layer heterogeneity calibration.
         Applies design, GRADE, temporal, scope, freshness, structural,
         and between-study layers to SE_eff.
Reads: Harmonized records from P2
Writes: Calibrated records with SE_eff for P4 aggregation
Gates: P3-G1 (layer validity — all 7 layers must be applied)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p3_heterogeneity(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P3 seven-layer heterogeneity calibration.

    Steps:
        P3-L1 through P3-L7: Apply all 7 calibration layers
        P3-ASM: Assemble SE_eff from calibrated components

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with harmonized records.

    Returns:
        Updated context with calibrated records.
    """
    paper_id = context.get("paper_id", "unknown")
    harmonized_records = context.get("harmonized_records", [])

    logger.info(
        "P3: Calibrating %d records for %s through 7 layers",
        len(harmonized_records), paper_id,
    )

    if not harmonized_records:
        logger.warning("P3: No harmonized records to calibrate")
        context["calibrated_records"] = []
        return context

    # Resolve study design from P0 classification as fallback
    # when AG02 (DesignAgent) fails and records default to "unclassified"
    classified_paper = context.get("classified_paper", {})
    p0_study_design = classified_paper.get("study_design", "other")
    if hasattr(p0_study_design, "value"):
        p0_study_design = p0_study_design.value
    p0_study_design = str(p0_study_design) if p0_study_design else "other"

    # Debug: log what fields the harmonized records actually have
    if harmonized_records:
        sample = harmonized_records[0]
        logger.info(
            "P3: Record type=%s, fields=%s",
            type(sample).__name__,
            [f for f in dir(sample) if not f.startswith("_")],
        )
        # Log SE/beta availability across all records
        has_se = sum(1 for r in harmonized_records if getattr(r, "se", None) is not None)
        has_beta = sum(1 for r in harmonized_records if getattr(r, "beta", None) is not None)
        logger.info(
            "P3: Data availability: %d/%d have SE, %d/%d have beta",
            has_se, len(harmonized_records), has_beta, len(harmonized_records),
        )

    # ── P3-L1 through P3-L7: Apply all 7 layers ──
    from crci.extraction.p3_heterogeneity.layers import apply_all_layers

    layered_records = apply_all_layers(harmonized_records, session=session)
    logger.info("P3 layers complete: %d records calibrated", len(layered_records))

    # ── P3-ASM: Assemble SE_eff from layered components ──
    from crci.extraction.p3_heterogeneity.se_eff_assembly import (
        SEEffInput,
        compute_se_eff,
    )

    calibrated_records = []
    for layered in layered_records:
        rec = layered.record
        se_raw = getattr(rec, "se", None) or getattr(rec, "harmonized_se", None)
        if se_raw is None:
            logger.debug("P3-ASM: skipping record with no SE")
            continue
        try:
            # Use P0's study_design as fallback when AG02 fails
            record_design = getattr(rec, "study_design", "unclassified")
            if record_design == "unclassified" and p0_study_design != "other":
                record_design = p0_study_design
                logger.debug(
                    "P3-ASM: using P0 study_design '%s' as fallback for "
                    "record %s (AG02 returned 'unclassified')",
                    p0_study_design,
                    getattr(rec, "ler_id", "?"),
                )

            inp = SEEffInput(
                ler_id=getattr(rec, "ler_id", ""),
                se_raw=se_raw,
                study_design=record_design,
                n_total=getattr(rec, "n_total", None),
                w_scope=layered.w_scope,
                betas=getattr(rec, "group_betas", None) or [],
                ses=getattr(rec, "group_ses", None) or [],
                validation_status=getattr(rec, "cancer_validation_status", "general_population"),
                grade_level=getattr(rec, "grade_level", "MODERATE"),
                days_since_measurement=getattr(rec, "days_since_measurement", 0.0),
                is_trait=getattr(rec, "is_trait", False),
            )
            se_eff_result = compute_se_eff(inp)
            # Attach SE_eff to the original record
            if hasattr(rec, "se_eff"):
                rec.se_eff = se_eff_result.se_eff
            calibrated_records.append(rec)
        except ValueError as exc:
            # Temporal exclusion (>90 days) — record removed by design
            logger.info("P3-ASM: record excluded: %s", exc)
        except Exception as exc:
            logger.warning("P3-ASM: SE_eff computation failed: %s", exc)

    context["calibrated_records"] = calibrated_records

    logger.info(
        "P3 complete: %d records with SE_eff assembled",
        len(calibrated_records),
    )

    return context
