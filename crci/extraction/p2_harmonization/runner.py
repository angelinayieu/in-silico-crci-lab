# VERIFIED: imports — all 5 P2 submodules
# VERIFIED: backward wiring — reads validated claims from TB context
# VERIFIED: forward wiring — writes harmonized LER rows to context for P3
# VERIFIED: gates — P2-G1 (plausibility), P2-G2 (orientation)
"""
Component: SYS_EXTRACTION.EX-P2.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 800-1135
Purpose: Orchestrate P2 harmonization: plausibility → conversion → scale →
         orientation → identification. Produces harmonized edge evidence.
Reads: Validated claims from TB (context)
Writes: Harmonized LER rows in edge_evidence_v1
Gates: P2-G1 (plausibility bounds), P2-G2 (orientation confidence)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p2_harmonization(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P2 harmonization chain on validated claims.

    Steps:
        P2-S1: Plausibility Checker — bounds check (Gate P2-G1)
        P2-S2: Conversion Router — effect size conversion
        P2-S3: Scale Harmonizer — SMD/log-scale alignment
        P2-S4: Orientation Aligner — direction standardization (Gate P2-G2)
        P2-S5: Identification Scorer — causal identification scoring

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with validated claims.

    Returns:
        Updated context with harmonized evidence records.
    """
    paper_id = context.get("paper_id", "unknown")
    claims = context.get("tb_result", {}).get("valid_claims", [])

    if not claims:
        claims = context.get("parsed_claims", {}).get("valid_claims", [])

    logger.info("P2: Harmonizing %d claims for %s", len(claims), paper_id)

    # ── P2-S1: Plausibility ──
    logger.info("P2-S1: Running plausibility checks")
    from crci.extraction.p2_harmonization.plausibility_checker import check_plausibility

    plausibility_results = check_plausibility(claims, session=session)
    context["p2_plausibility"] = plausibility_results

    passed_claims = plausibility_results.get("passed", claims)
    logger.info(
        "P2-S1 complete: %d/%d passed plausibility",
        len(passed_claims), len(claims),
    )

    # ── P2-S2: Conversion ──
    logger.info("P2-S2: Converting effect sizes")
    from crci.extraction.p2_harmonization.conversion_router import convert_effects

    converted = convert_effects(passed_claims, session=session)
    context["p2_converted"] = converted
    logger.info("P2-S2 complete: %d converted", len(converted.get("converted", [])))

    # ── P2-S3: Scale Harmonization ──
    logger.info("P2-S3: Harmonizing scales")
    from crci.extraction.p2_harmonization.scale_harmonizer import harmonize_scales

    harmonized = harmonize_scales(converted.get("converted", []), session=session)
    context["p2_harmonized"] = harmonized
    logger.info("P2-S3 complete: %d harmonized", len(harmonized.get("harmonized", [])))

    # ── P2-S4: Orientation Alignment ──
    logger.info("P2-S4: Aligning orientation")
    from crci.extraction.p2_harmonization.orientation_aligner import align_orientation

    oriented = align_orientation(harmonized.get("harmonized", []), session=session)
    context["p2_oriented"] = oriented
    logger.info("P2-S4 complete: %d aligned", len(oriented.get("aligned", [])))

    # ── P2-S5: Identification Scoring ──
    logger.info("P2-S5: Scoring identification status")
    from crci.extraction.p2_harmonization.identification_scorer import score_identification

    identified = score_identification(oriented.get("aligned", []), session=session)
    context["p2_identified"] = identified
    context["harmonized_records"] = identified.get("scored", [])
    logger.info("P2-S5 complete: %d scored", len(identified.get("scored", [])))

    return context
