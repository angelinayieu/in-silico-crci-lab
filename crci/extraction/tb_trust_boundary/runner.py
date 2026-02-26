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

    # Prefer grounded_spans (GroundedSpan[]) from ConceptEngine (carry edge linkage).
    # Fall back to raw all_span_labels (SpanLabel[]).
    grounded_spans = context.get("grounded_spans", [])
    span_labels = context.get("all_span_labels", [])

    # For parse_spans, we need raw SpanLabel objects
    # (GroundedSpan wraps SpanLabel — extract the inner span for parsing)
    from crci.shared.models.intermediate_states import GroundedSpan as _GS
    if grounded_spans:
        raw_for_parsing = [
            gs.span if isinstance(gs, _GS) else gs for gs in grounded_spans
        ]
        # Keep grounded_spans for group_assembler (carries edge_relation_id)
        assembly_input = grounded_spans
    elif span_labels:
        raw_for_parsing = span_labels
        assembly_input = span_labels
    else:
        raw_for_parsing = []
        assembly_input = []

    # NOTE: PaperMap.candidate_spans are CandidateSpan objects (text, char_start,
    # char_end) — they lack .value and .label_type required by parse_spans().
    # CandidateSpan is a *pre-labelling* detection; SpanLabel is the *post-AG05*
    # labelled version. We cannot meaningfully parse CandidateSpans, so we skip
    # them and let the downstream TB-G1 gate handle the zero-span case.
    paper_map = context.get("paper_map")
    if not raw_for_parsing and paper_map and hasattr(paper_map, "candidate_spans"):
        if paper_map.candidate_spans:
            logger.warning(
                "TB-S1: %d CandidateSpan(s) found on PaperMap but no "
                "SpanLabel(s) available — CandidateSpans lack label_type "
                "and cannot be parsed. Skipping.",
                len(paper_map.candidate_spans),
            )

    parsed_numerics = parse_spans(raw_for_parsing)

    # Separate valid (parsed successfully) from failed
    # ParseStatus enum: CLEAN = successfully parsed, AMBIGUOUS = partial, FAILED = rejected
    valid_claims = [p for p in parsed_numerics if p.parse_status.value == "CLEAN"]
    failed_claims = [p for p in parsed_numerics if p.parse_status.value != "CLEAN"]

    context["parsed_claims"] = valid_claims
    context["failed_claims"] = failed_claims
    context["total_spans"] = len(raw_for_parsing)

    logger.info(
        "TB-S1 complete: %d claims parsed from %d span labels",
        len(valid_claims),
        len(raw_for_parsing),
    )

    # ── TB-S1b: Span Group Assembly ──
    # Reassemble individually-parsed spans sharing a grouping_id into
    # multi-field TypedNumericValue records ({β, SE, CI, p, N}).
    logger.info("TB-S1b: Assembling span groups")
    from crci.extraction.tb_trust_boundary.group_assembler import reassemble_groups

    grouped_evidence, assembly_qa = reassemble_groups(
        span_labels=assembly_input,
        parsed=valid_claims,
    )
    context["grouped_evidence"] = grouped_evidence
    context.setdefault("qa_metrics", {}).update(assembly_qa)

    logger.info(
        "TB-S1b complete: %d grouped evidence records from %d valid claims",
        len(grouped_evidence),
        len(valid_claims),
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


# ═══════════════════════════════════════════════════════════════
#  R5 LLM GUARDRAIL HELPERS
# ═══════════════════════════════════════════════════════════════


def _check_figure_only(span: Any) -> bool:
    """UG-05: Return True if the span is sourced ONLY from a figure.

    A span is figure-only if its source_section contains 'figure'
    (case-insensitive) but does NOT contain 'table'.
    """
    source = getattr(span, "source_section", None) or ""
    source_lower = source.lower()
    if "figure" in source_lower and "table" not in source_lower:
        return True
    return False


def _flag_sensitivity_analysis(span: Any) -> bool:
    """UG-08: Return True if the span is from a sensitivity/robustness analysis.

    Flags spans whose source_section contains sensitivity-related terms.
    """
    source = getattr(span, "source_section", None) or ""
    source_lower = source.lower()
    _SENSITIVITY_TERMS = [
        "sensitivity analysis",
        "sensitivity",
        "robustness check",
        "robustness",
        "leave-one-out",
    ]
    return any(term in source_lower for term in _SENSITIVITY_TERMS)
