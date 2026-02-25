# VERIFIED: imports — all modules exist (p3_heterogeneity submodules)
# VERIFIED: backward wiring — reads harmonized_claims from context (P2)
# VERIFIED: forward wiring — writes calibrated_evidence to context (P4)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P3-G1 (SE_eff >= SE_raw) delegated to se_eff_assembly.py
"""
Component: SYS_EXTRACTION.EX-P3.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 765-1102
Purpose: Orchestrate P3 seven-layer heterogeneity assessment.
         Applies 7 SE inflation layers to each harmonized claim,
         producing calibrated evidence with SE_eff.
Reads: harmonized_claims (from P2 context)
Writes: calibrated_evidence (to context for P4)
Gates: P3-G1 (SE_eff >= SE_raw) delegated to se_eff_assembly.py
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
    """Run the P3 seven-layer heterogeneity chain.

    Applies all 7 SE inflation layers (P3-1 through P3-7) to each
    harmonized claim, assembling SE_eff via Formula P3-8.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P2 outputs.

    Returns:
        Updated context with calibrated evidence.
    """
    from crci.extraction.p3_heterogeneity.se_eff_assembly import (
        SEEffInput,
        compute_se_eff,
    )
    from crci.shared import config

    logger.info("P3 heterogeneity starting for run %s", run.extraction_run_id)

    harmonized_claims = context.get("harmonized_claims", [])
    if not harmonized_claims:
        logger.warning("P3: No harmonized claims found, skipping")
        context["calibrated_evidence"] = []
        return context

    calibrated: list = []
    errors = 0

    for claim in harmonized_claims:
        try:
            se_base = claim.harmonized_se if claim.harmonized_se else config.SE_DERIVATION_FALLBACK
            inp = SEEffInput(
                ler_id=claim.ler_id,
                se_base=se_base,
                study_design=getattr(claim, "study_design", "observational"),
                n_total=getattr(claim, "n_effect", None),
                quality_grade=getattr(claim, "quality_rating", "MODERATE").upper(),
                publication_year=getattr(claim, "publication_year", 2020),
                cancer_validation_status=getattr(
                    claim, "cancer_validation_status", "general_population"
                ),
            )
            result = compute_se_eff(inp)
            calibrated.append({
                "claim": claim,
                "se_eff_result": result,
                "se_effective": result.se_effective,
            })
        except Exception as exc:
            logger.warning(
                "P3 SE_eff computation failed for %s: %s",
                claim.ler_id,
                exc,
            )
            errors += 1

    context["calibrated_evidence"] = calibrated

    logger.info(
        "P3 heterogeneity complete: %d claims → %d calibrated (%d errors)",
        len(harmonized_claims),
        len(calibrated),
        errors,
    )
    return context
