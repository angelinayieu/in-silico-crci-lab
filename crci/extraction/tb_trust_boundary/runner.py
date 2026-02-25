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
    from crci.extraction.tb_trust_boundary.numeric_parser import parse_spans

    # Extract SpanLabel objects from P1 agent outputs (passed via context)
    span_labels = context.get("all_span_labels", [])

    # Also check PaperMap candidate_spans as fallback
    paper_map = context.get("paper_map")
    if not span_labels and paper_map and hasattr(paper_map, "candidate_spans"):
        span_labels = paper_map.candidate_spans

    parsed_numerics = parse_spans(span_labels)

    # Separate valid (parsed successfully) from failed
    # ParseStatus enum: CLEAN = successfully parsed, AMBIGUOUS = partial, FAILED = rejected
    valid_claims = [p for p in parsed_numerics if p.parse_status.value == "CLEAN"]
    failed_claims = [p for p in parsed_numerics if p.parse_status.value != "CLEAN"]

    context["parsed_claims"] = valid_claims
    context["failed_claims"] = failed_claims
    context["total_spans"] = len(span_labels)

    logger.info(
        "TB-S1 complete: %d claims parsed from %d span labels",
        len(valid_claims),
        len(span_labels),
    )

    # ── TB-S2: Consistency Checker ──
    logger.info("TB-S2: Running consistency checks")
    from crci.extraction.tb_trust_boundary.consistency_checker import check_consistency

    consistency_result = check_consistency(
        parsed_values=valid_claims,
        paper_id=paper_id,
    )
    context["tb_result"] = consistency_result

    logger.info(
        "TB-S2 complete: %d validated, %d warnings, %d rejected",
        len(consistency_result.validated),
        len(consistency_result.warnings),
        len(consistency_result.rejected),
    )

    return context
