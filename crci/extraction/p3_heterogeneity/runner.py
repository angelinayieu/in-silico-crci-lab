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

    # ── P3-L1 through P3-L7: Apply layers ──
    from crci.extraction.p3_heterogeneity.layers import apply_all_layers

    layered_records = apply_all_layers(harmonized_records, session=session)
    logger.info("P3 layers complete: %d records calibrated", len(layered_records))

    # ── P3-ASM: Assemble SE_eff ──
    from crci.extraction.p3_heterogeneity.se_eff_assembly import assemble_se_eff

    calibrated_records = assemble_se_eff(layered_records)
    context["calibrated_records"] = calibrated_records

    logger.info(
        "P3 complete: %d records with SE_eff assembled",
        len(calibrated_records),
    )

    return context
