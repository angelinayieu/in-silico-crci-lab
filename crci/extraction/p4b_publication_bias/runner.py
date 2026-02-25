# VERIFIED: imports — publication_bias
# VERIFIED: backward wiring — reads pooled estimates from P4 context
# VERIFIED: forward wiring — writes bias assessment results for P5
"""
Component: SYS_EXTRACTION.EX-P4B.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1500-1600
Purpose: Run publication bias assessment after P4 aggregation.
Reads: Pooled estimates from P4
Writes: Bias assessment results (Egger's test, trim-and-fill)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p4b_publication_bias(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P4B publication bias assessment.

    Steps:
        P4B-EGG: Egger's regression test for funnel asymmetry
        P4B-TF:  Trim-and-fill adjusted estimates

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with pooled estimates from P4.

    Returns:
        Updated context with bias assessment results.
    """
    pooled = context.get("pooled_estimates", [])

    logger.info("P4B: Running publication bias assessment on %d pooled estimates", len(pooled))

    if not pooled:
        logger.info("P4B: No pooled estimates — skipping bias assessment")
        context["bias_results"] = []
        return context

    from crci.extraction.p4b_publication_bias.publication_bias import assess_publication_bias

    bias_results = assess_publication_bias(pooled, session=session)
    context["bias_results"] = bias_results

    logger.info(
        "P4B complete: %d edges assessed for publication bias",
        len(bias_results),
    )

    return context
