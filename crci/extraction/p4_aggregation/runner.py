# VERIFIED: imports — evidence_grouper, double_counting, meta_analyzer, prior_selector, edge_writer
# VERIFIED: backward wiring — reads calibrated records from P3 context
# VERIFIED: forward wiring — writes compiled edges to edges_v1
# VERIFIED: gates — P4-G1 (minimum k for pooling)
"""
Component: SYS_EXTRACTION.EX-P4.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1230-1500
Purpose: Orchestrate P4 aggregation: group → DCR → pool → prior → write edges.
Reads: Calibrated records from P3
Writes: Compiled edge parameters in edges_v1 (Class C)
Gates: P4-G1 (k >= 1 for pooling)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p4_aggregation(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P4 aggregation chain.

    Steps:
        P4-GRP: Evidence grouper — group by edge relation
        P4-DCR: Double counting resolution
        P4-MA:  Meta-analysis (IVW pooling)
        P4-PRI: Prior selector — match priors to edges
        P4-WRT: Edge writer — persist to edges_v1

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with calibrated records.

    Returns:
        Updated context with pooled estimates and edge writes.
    """
    paper_id = context.get("paper_id", "unknown")
    calibrated = context.get("calibrated_records", [])

    logger.info("P4: Aggregating %d calibrated records for %s", len(calibrated), paper_id)

    if not calibrated:
        logger.warning("P4: No calibrated records to aggregate")
        context["pooled_estimates"] = []
        context["edges_written"] = 0
        return context

    # ── P4-GRP: Group evidence by edge ──
    from crci.extraction.p4_aggregation.evidence_grouper import group_evidence

    groups = group_evidence(calibrated, session=session)
    logger.info("P4-GRP: %d evidence groups formed", len(groups))

    # ── P4-DCR: Double counting resolution ──
    from crci.extraction.p4_aggregation.double_counting import resolve_double_counting

    resolved_groups = resolve_double_counting(groups, session=session)
    logger.info(
        "P4-DCR: %d groups after double-counting resolution",
        len(resolved_groups),
    )

    # ── P4-MA: Meta-analysis (IVW pooling) ──
    from crci.extraction.p4_aggregation.meta_analyzer import pool_evidence

    pooled_estimates = pool_evidence(resolved_groups)
    context["pooled_estimates"] = pooled_estimates
    logger.info("P4-MA: %d pooled estimates computed", len(pooled_estimates))

    # ── P4-PRI: Prior selection ──
    from crci.extraction.p4_aggregation.prior_selector import select_priors

    prior_assignments = select_priors(pooled_estimates, session=session)
    context["prior_assignments"] = prior_assignments
    logger.info("P4-PRI: priors assigned for %d edges", len(prior_assignments))

    # ── P4-WRT: Write compiled edges ──
    from crci.extraction.p4_aggregation.edge_writer import write_edges

    edges_written = write_edges(
        pooled_estimates=pooled_estimates,
        prior_assignments=prior_assignments,
        extraction_run_id=context.get("extraction_run_id"),
        session=session,
    )
    context["edges_written"] = edges_written
    logger.info("P4-WRT: %d edges written to edges_v1", edges_written)

    return context
