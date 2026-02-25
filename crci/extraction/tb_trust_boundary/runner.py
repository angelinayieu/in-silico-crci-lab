# VERIFIED: imports — all modules exist (tb_trust_boundary submodules)
# VERIFIED: backward wiring — reads atb_result from context (P1)
# VERIFIED: forward wiring — writes typed_numeric_values to context (P2)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — TB-G1 consistency delegated to consistency_checker.py
"""
Component: SYS_EXTRACTION.EX-TB.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 593-683
Purpose: Orchestrate Trust Boundary: parse numeric spans → consistency check.
         Converts LLM annotations into deterministic TypedNumericValues.
Reads: atb_result, raw_annotations (from P1 context)
Writes: typed_numeric_values, consistency_result (to context for P2)
Gates: TB-G1 (consistency) delegated to consistency_checker.py
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
    """Run the Trust Boundary chain: parse spans → consistency check.

    Called by pipeline.py after P1 extraction completes.
    This is the critical LLM-to-deterministic boundary.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with P1 outputs.

    Returns:
        Updated context with typed numeric values.
    """
    from crci.extraction.tb_trust_boundary.numeric_parser import parse_spans_to_typed
    from crci.extraction.tb_trust_boundary.consistency_checker import check_consistency

    logger.info("TB trust boundary starting for run %s", run.extraction_run_id)

    # Collect span labels from ATB result or raw annotations
    atb_result = context.get("atb_result")
    span_labels = []
    if atb_result and hasattr(atb_result, "accepted"):
        span_labels = atb_result.accepted
    elif atb_result and hasattr(atb_result, "span_labels"):
        span_labels = atb_result.span_labels
    else:
        span_labels = context.get("span_labels", [])

    if not span_labels:
        logger.warning("TB: No span labels found in context, skipping")
        context["typed_numeric_values"] = []
        context["consistency_result"] = None
        return context

    # S1: Numeric Parsing — convert spans to TypedNumericValue
    typed_values = parse_spans_to_typed(span_labels)
    context["typed_numeric_values"] = typed_values
    logger.info("TB-S1: Parsed %d spans into %d typed values", len(span_labels), len(typed_values))

    # S2: Consistency Check — cross-validate parsed values
    paper_id = context.get("paper_id", run.extraction_run_id)
    from crci.extraction.tb_trust_boundary.numeric_parser import ParsedNumeric
    parsed_numerics = []
    for tv in typed_values:
        parsed_numerics.append(
            ParsedNumeric(
                span_id=getattr(tv, "span_id", ""),
                value=tv.value,
                se=tv.se,
                ci_lower=tv.ci_lower,
                ci_upper=tv.ci_upper,
                p_value=tv.p_value,
                n=tv.n,
            ) if hasattr(tv, "span_id") else tv
        )

    consistency_result = check_consistency(
        parsed_values=parsed_numerics,
        paper_id=paper_id,
    )
    context["consistency_result"] = consistency_result
    logger.info("TB-S2: Consistency check complete")

    logger.info(
        "TB trust boundary complete: %d typed values produced",
        len(typed_values),
    )
    return context
