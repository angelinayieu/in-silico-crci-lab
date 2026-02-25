# VERIFIED: imports — numeric_parser, consistency_checker
# VERIFIED: backward wiring — reads raw LER claims from P1 context
# VERIFIED: forward wiring — writes validated LER rows to context for P2
# VERIFIED: gates — TB-G1 (plausibility), TB-G2 (consistency)
"""
Component: SYS_EXTRACTION.EX-TB.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 600-800
Purpose: Orchestrate Trust Boundary: numeric parse → plausibility → consistency.
         Filters raw extracted claims before harmonization.
Reads: Agent outputs (from P1 context) — raw numeric claims
Writes: Validated LER claims (consumed by P2 harmonization)
Gates: TB-G1 (implausible values blocked), TB-G2 (inconsistency flagged)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_tb_trust_boundary(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run Trust Boundary validation on extracted numeric claims.

    Steps:
        TB-S1: Numeric Parser — parse and type-check raw claims
        TB-S2: Consistency Checker — cross-validate related claims

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with raw agent outputs.

    Returns:
        Updated context with validated claims.
    """
    paper_id = context.get("paper_id", "unknown")

    # ── TB-S1: Numeric Parser ──
    logger.info("TB-S1: Parsing numeric claims for %s", paper_id)
    from crci.extraction.tb_trust_boundary.numeric_parser import parse_numeric_claims

    raw_claims = context.get("raw_annotations", [])
    parsed = parse_numeric_claims(raw_claims)
    context["parsed_claims"] = parsed

    logger.info(
        "TB-S1 complete: %d claims parsed from %d raw annotations",
        len(parsed.get("valid_claims", [])),
        len(raw_claims),
    )

    # ── TB-S2: Consistency Checker ──
    logger.info("TB-S2: Running consistency checks")
    from crci.extraction.tb_trust_boundary.consistency_checker import check_consistency

    consistency_result = check_consistency(
        parsed_claims=parsed,
        paper_id=paper_id,
        session=session,
    )
    context["tb_result"] = consistency_result

    logger.info(
        "TB-S2 complete: %d passed, %d flagged, %d blocked",
        consistency_result.get("passed", 0),
        consistency_result.get("flagged", 0),
        consistency_result.get("blocked", 0),
    )

    return context
