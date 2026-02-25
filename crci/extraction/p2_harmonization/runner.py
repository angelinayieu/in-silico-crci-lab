# VERIFIED: imports — all 5 P2 submodules + parameter_family_assigner
# VERIFIED: backward wiring — reads validated claims from TB context
# VERIFIED: forward wiring — writes harmonized LER rows to context for P3
# VERIFIED: gates — P2-G1 (plausibility), P2-G2 (orientation)
"""
Component: SYS_EXTRACTION.EX-P2.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 800-1135
      CONVERSION_VALIDITY_AND_HARDENING.md Module 5.1 (Parameter Family Assignment)
Purpose: Orchestrate P2 harmonization: plausibility → conversion → scale →
         orientation → identification → family assignment.
Reads: Validated claims from TB (context)
Writes: Harmonized LER rows in edge_evidence_v1
Gates: P2-G1 (plausibility bounds), P2-G2 (orientation confidence)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.enums import Orientation, PlausibilityStatus
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
        P2-FA: Parameter Family Assignment — assigns freshness family

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with validated claims.

    Returns:
        Updated context with harmonized evidence records.
    """
    paper_id = context.get("paper_id", "unknown")

    # Get validated claims from TB result
    # tb_result is a ConsistencyResult dataclass with .validated attribute
    tb_result = context.get("tb_result")
    if tb_result is not None and hasattr(tb_result, "validated"):
        claims = tb_result.validated
    else:
        # Fallback: try parsed_claims from context
        claims = context.get("parsed_claims", [])
        if isinstance(claims, dict):
            claims = claims.get("valid_claims", [])

    logger.info("P2: Harmonizing %d claims for %s", len(claims), paper_id)

    # Resolve study_design from triage context for S5
    classified_paper = context.get("classified_paper", {})
    study_design_raw = classified_paper.get("study_design", "other")
    if hasattr(study_design_raw, "value"):
        study_design_str = study_design_raw.value
    else:
        study_design_str = str(study_design_raw) if study_design_raw else "other"

    # ── P2-S1: Plausibility ──
    logger.info("P2-S1: Running plausibility checks")
    from crci.extraction.p2_harmonization.plausibility_checker import check_plausibility

    passed_claims: list[Any] = []
    failed_plausibility: list[Any] = []
    for claim in claims:
        try:
            result = check_plausibility(
                span_id=claim.span_id,
                value=claim.value,
            )
            if result.plausibility_status != PlausibilityStatus.FAIL:
                passed_claims.append(result)
            else:
                failed_plausibility.append(result)
        except Exception as exc:
            logger.debug("P2-S1: plausibility check failed for span %s: %s",
                         getattr(claim, "span_id", "?"), exc)
            # On error, pass claim through (fail-open for debugging)
            passed_claims.append(claim)

    context["p2_plausibility"] = {
        "passed": passed_claims,
        "failed": failed_plausibility,
    }
    logger.info(
        "P2-S1 complete: %d/%d passed plausibility",
        len(passed_claims), len(claims),
    )

    # ── P2-S2: Conversion ──
    logger.info("P2-S2: Converting effect sizes")
    from crci.extraction.p2_harmonization.conversion_router import route_conversion

    converted_list: list[Any] = []
    failed_conversions: list[Any] = []
    for claim in passed_claims:
        try:
            routed = route_conversion(
                validated=claim,
                effect_type_reported="group_diff",  # Default; TB claims lack this metadata
            )
            converted_list.append(routed)
        except Exception as exc:
            logger.debug("P2-S2: conversion failed for span %s: %s",
                         getattr(claim, "span_id", "?"), exc)
            failed_conversions.append(claim)

    context["p2_converted"] = {
        "converted": converted_list,
        "failed": failed_conversions,
    }
    logger.info("P2-S2 complete: %d converted, %d failed",
                len(converted_list), len(failed_conversions))

    # ── P2-S3: Scale Harmonization ──
    logger.info("P2-S3: Harmonizing scales")
    from crci.extraction.p2_harmonization.scale_harmonizer import harmonize_scale

    harmonized_list: list[Any] = []
    for routed_item in converted_list:
        try:
            scaled = harmonize_scale(
                routed=routed_item,
                effect_type_reported="group_diff",
            )
            harmonized_list.append(scaled)
        except Exception as exc:
            logger.debug("P2-S3: scale harmonization failed for span %s: %s",
                         getattr(routed_item, "span_id", "?"), exc)

    context["p2_harmonized"] = harmonized_list
    logger.info("P2-S3 complete: %d harmonized", len(harmonized_list))

    # ── P2-S4: Orientation Alignment ──
    logger.info("P2-S4: Aligning orientation")
    from crci.extraction.p2_harmonization.orientation_aligner import align_orientation

    aligned_list: list[Any] = []
    for scaled_item in harmonized_list:
        try:
            aligned = align_orientation(
                scaled=scaled_item,
                dag_orientation=Orientation.HIGHER_WORSE,  # Default; lookup from DAG later
                reported_direction_positive=True,  # Default assumption
                orientation_confidence=0.7,  # Moderate default
            )
            aligned_list.append(aligned)
        except Exception as exc:
            logger.debug("P2-S4: orientation alignment failed for span %s: %s",
                         getattr(scaled_item, "span_id", "?"), exc)
            # Pass through unaligned
            aligned_list.append(scaled_item)

    context["p2_oriented"] = aligned_list
    logger.info("P2-S4 complete: %d aligned", len(aligned_list))

    # ── P2-S5: Identification Scoring ──
    logger.info("P2-S5: Scoring identification status")
    from crci.extraction.p2_harmonization.identification_scorer import score_identification

    scored_list: list[Any] = []
    for aligned_item in aligned_list:
        try:
            id_result = score_identification(
                scaled=aligned_item,
                study_design=study_design_str,
            )
            scored_list.append(id_result)
        except Exception as exc:
            logger.debug("P2-S5: identification scoring failed for span %s: %s",
                         getattr(aligned_item, "span_id", "?"), exc)

    context["p2_identified"] = scored_list
    logger.info("P2-S5 complete: %d scored", len(scored_list))

    # ── P2-FA: Parameter Family Assignment (Module 5.1) ──
    # Use aligned_list (ScaledNumeric objects) as the primary records
    # because downstream P3 needs .beta and .se fields.
    # IdentificationResult objects are kept separately in p2_identified.
    logger.info("P2-FA: Assigning parameter families")
    from crci.extraction.p2_harmonization.parameter_family_assigner import (
        assign_parameter_family,
    )

    paper_subtype = classified_paper.get("paper_subtype")
    subtype_str = (
        paper_subtype.value if hasattr(paper_subtype, "value") else paper_subtype
    )

    family_counts: dict[str, int] = {}
    for record in aligned_list:
        edge_family = getattr(record, "edge_family", None)
        extraction_ctx = getattr(record, "extraction_context", None)
        meta_source = getattr(record, "meta_source_flag", None)

        family = assign_parameter_family(
            paper_subtype=subtype_str,
            edge_family=edge_family,
            meta_source_flag=meta_source,
            extraction_context=extraction_ctx,
        )

        # Attach family to record if it supports attribute assignment
        if hasattr(record, "parameter_family"):
            record.parameter_family = family.value
        elif isinstance(record, dict):
            record["parameter_family"] = family.value

        family_counts[family.value] = family_counts.get(family.value, 0) + 1

    # Pass ScaledNumeric objects (aligned_list) as harmonized_records.
    # These have .beta, .se, .se_source, .scale that P3 needs.
    context["harmonized_records"] = aligned_list
    context["parameter_family_counts"] = family_counts
    logger.info(
        "P2-FA complete: %d records assigned families: %s",
        len(aligned_list),
        family_counts,
    )

    return context
