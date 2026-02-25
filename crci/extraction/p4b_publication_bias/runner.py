# VERIFIED: imports — all modules exist (p4b_publication_bias submodules)
# VERIFIED: backward wiring — reads pooled_estimates from context (P4)
# VERIFIED: forward wiring — writes bias_assessments to context (P5)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (assessment only; bias flags → P5 for decision)
"""
Component: SYS_EXTRACTION.EX-P4B.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1394-1534
Purpose: Orchestrate P4B publication bias assessment: Egger regression,
         trim-and-fill, leave-one-out, bias flag aggregation.
Reads: pooled_estimates (from P4 context)
Writes: bias_assessments (to context for P5 sufficiency)
Gates: None (assessment only; bias status used by P5/P6 gates)
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
    """Run the P4B publication bias assessment chain.

    For each pooled estimate with k >= 3 studies, runs Egger regression,
    trim-and-fill, leave-one-out, and aggregates bias flags.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P4 outputs.

    Returns:
        Updated context with bias assessments.
    """
    from crci.extraction.p4b_publication_bias.publication_bias import (
        assess_publication_bias,
    )

    logger.info("P4B publication bias starting for run %s", run.extraction_run_id)

    pooled_list = context.get("pooled_estimates", [])
    if not pooled_list:
        logger.warning("P4B: No pooled estimates found, skipping")
        context["bias_assessments"] = []
        return context

    assessments = []
    skipped = 0

    for pooled in pooled_list:
        pe = pooled.pooled_estimate if hasattr(pooled, "pooled_estimate") else pooled
        k = getattr(pe, "k_studies", 0)

        if k < 3:
            logger.debug(
                "P4B: Skipping %s (k=%d < 3, insufficient for bias tests)",
                getattr(pe, "edge_relation_id", "?"),
                k,
            )
            skipped += 1
            continue

        # Extract per-study betas and SEs for bias testing
        study_betas = getattr(pe, "study_betas", [])
        study_ses = getattr(pe, "study_ses", [])

        if not study_betas or not study_ses:
            logger.debug(
                "P4B: Skipping %s — no per-study data available",
                getattr(pe, "edge_relation_id", "?"),
            )
            skipped += 1
            continue

        try:
            assessment = assess_publication_bias(
                pooled_estimate=pe,
                study_betas=study_betas,
                study_ses=study_ses,
            )
            assessments.append(assessment)
        except Exception as exc:
            logger.warning(
                "P4B assessment failed for %s: %s",
                getattr(pe, "edge_relation_id", "?"),
                exc,
            )

    context["bias_assessments"] = assessments

    logger.info(
        "P4B publication bias complete: %d assessed, %d skipped (k<3 or no data)",
        len(assessments),
        skipped,
    )
    return context
