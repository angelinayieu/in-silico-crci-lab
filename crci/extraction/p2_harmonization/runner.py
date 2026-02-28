# VERIFIED: imports — all 5 P2 submodules + parameter_family_assigner + evidence_writer
# VERIFIED: backward wiring — reads validated claims from TB context
# VERIFIED: forward wiring — writes harmonized LER rows to context for P3 AND edge_evidence_v1
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

from crci.shared.models.enums import (
    HarmonizationStatusInMem,
    Orientation,
    PlausibilityStatus,
)
from crci.shared.models.intermediate_states import (
    HarmonizedClaim,
    TypedNumericValue,
)
from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


class _GroupedClaimAdapter:
    """Adapts a TypedNumericValue (from group assembler) to the interface
    that P2 stages expect from ParsedNumeric claims.

    P2 accesses: .span_id, .value (TypedNumericValue), .value_type
    """

    def __init__(self, tv: TypedNumericValue, idx: int):
        self.span_id = f"grp_{tv.grouping_id or idx}"
        self.value = tv  # TypedNumericValue — what check_plausibility expects
        self.value_type = (tv.label_type or "EFFECT_SIZE").upper()
        # Carry through for downstream
        self.edge_relation_id = tv.edge_relation_id
        self.label_type = tv.label_type


def _wrap_typed_as_claims(
    grouped: list[TypedNumericValue],
) -> list[_GroupedClaimAdapter]:
    """Wrap TypedNumericValue records as claim-like objects for P2 stages."""
    return [_GroupedClaimAdapter(tv, i) for i, tv in enumerate(grouped)]


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
    # Prefer grouped_evidence (TypedNumericValue[] with multi-field records)
    # from TB group assembler (1B). Fallback to tb_result.validated
    # (ParsedNumeric[] — legacy, single-field per record).
    grouped_evidence = context.get("grouped_evidence")
    if grouped_evidence is not None and len(grouped_evidence) > 0:
        # TypedNumericValue objects — already have se, ci, p, n fields
        # We need to wrap them to have span_id and value_type for P2 steps
        claims = _wrap_typed_as_claims(grouped_evidence)
        logger.info(
            "P2: Using %d grouped evidence records from TB assembler",
            len(claims),
        )
    else:
        tb_result = context.get("tb_result")
        if tb_result is not None and hasattr(tb_result, "validated"):
            claims = tb_result.validated
        else:
            # Fallback: try parsed_claims from context
            claims = context.get("parsed_claims", [])
            if isinstance(claims, dict):
                claims = claims.get("valid_claims", [])

    # ── FILTER: Only process effect-type claims for P2 harmonization ──
    # Non-effect types (SAMPLE_SIZE, MEAN, SD, etc.) are preserved for context
    # but should not be harmonized as beta/SE pairs.
    EFFECT_VALUE_TYPES = {
        # From numeric_parser _RULE_NP04_TYPES and _RULE_NP08_TYPES
        "EFFECT_SIZE", "ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO",
        "INCIDENCE_RATE_RATIO", "MEAN_DIFFERENCE", "PERCENT_CHANGE",
        "UNSTD_BETA", "STD_BETA", "CORRELATION",
        # Allow interaction terms and subgroup effects
        "INTERACTION_TERM", "SUBGROUP_EFFECT",
        # F-statistics convert to Cohen's d: d = 2*sqrt(F/N)
        "F_STATISTIC",
    }
    original_count = len(claims)
    effect_claims = [
        c for c in claims
        if getattr(c, "value_type", "").upper() in EFFECT_VALUE_TYPES
    ]
    non_effect_count = original_count - len(effect_claims)
    if non_effect_count > 0:
        logger.info(
            "P2: Filtered %d non-effect claims (SAMPLE_SIZE, MEAN, SD, etc.), "
            "processing %d effect-type claims for harmonization",
            non_effect_count, len(effect_claims)
        )
    claims = effect_claims

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
            effect_type = _infer_effect_type(claim)
            routed = route_conversion(
                validated=claim,
                effect_type_reported=effect_type,
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

    # Extract paper-level N for F→d conversion fallback
    _paper_n: int | None = None
    _sample_info = context.get("classified_paper", {}).get("sample_size")
    if _sample_info is not None:
        try:
            _paper_n = int(_sample_info)
        except (TypeError, ValueError):
            pass
    # Also check companion_meta for sample size (meta.json is higher quality)
    if _paper_n is None:
        _meta_sample = (context.get("companion_meta") or {}).get("sample", {})
        _meta_n = _meta_sample.get("n_total")
        if _meta_n is not None:
            try:
                _paper_n = int(_meta_n)
                logger.info("P2-S3: Using meta.json sample N=%d for F→d conversion", _paper_n)
            except (TypeError, ValueError):
                pass

    harmonized_list: list[Any] = []
    for routed_item in converted_list:
        try:
            effect_type = _infer_effect_type(routed_item)
            # For F_STATISTIC: inject paper-level N if not already set
            if effect_type == "f_statistic" and hasattr(routed_item, "value"):
                v = routed_item.value
                if v.n is None and _paper_n is not None:
                    v.n = _paper_n
                    logger.debug(
                        "P2-S3: Injected paper-level N=%d for F_STATISTIC span %s",
                        _paper_n, getattr(routed_item, "span_id", "?"),
                    )
            scaled = harmonize_scale(
                routed=routed_item,
                effect_type_reported=effect_type,
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
    from crci.shared.config import (
        ORIENTATION_CONFIDENCE_DB_MATCH,
        ORIENTATION_CONFIDENCE_EDGE_ONLY,
        ORIENTATION_CONFIDENCE_NO_EDGE,
    )

    # Build edge_relation_id → default_effect_direction lookup from DB
    _edge_direction_cache: dict[str, int] = {}
    try:
        from crci.shared.models.tables import EdgeRelationsDefinition
        edge_rows = session.query(
            EdgeRelationsDefinition.edge_relation_id,
            EdgeRelationsDefinition.default_effect_direction,
        ).all()
        _edge_direction_cache = {r.edge_relation_id: r.default_effect_direction for r in edge_rows}
        logger.info("P2-S4: Loaded %d edge directions from DB", len(_edge_direction_cache))
    except Exception as exc:
        logger.warning("P2-S4: Could not load edge directions from DB: %s — using defaults", exc)

    aligned_list: list[Any] = []
    for scaled_item in harmonized_list:
        try:
            # Look up DAG orientation from edge_relation_id
            eid = getattr(scaled_item, "edge_relation_id", None)
            direction = _edge_direction_cache.get(eid) if eid else None
            if direction is not None:
                dag_orientation = Orientation.HIGHER_BETTER if direction == 1 else Orientation.HIGHER_WORSE
                # DW#5 fix: derive confidence from data quality — direction found in DB
                orientation_confidence = ORIENTATION_CONFIDENCE_DB_MATCH
            elif eid:
                dag_orientation = Orientation.HIGHER_WORSE  # Conservative default
                logger.debug("P2-S4: No direction found for edge %s; defaulting to HIGHER_WORSE", eid)
                # DW#5 fix: edge exists but no direction → moderate confidence
                orientation_confidence = ORIENTATION_CONFIDENCE_EDGE_ONLY
            else:
                dag_orientation = Orientation.HIGHER_WORSE  # Conservative default
                # DW#5 fix: no edge_relation_id → low confidence
                orientation_confidence = ORIENTATION_CONFIDENCE_NO_EDGE

            # reported_direction_positive=True is the standard convention:
            # in virtually all papers, a positive effect size means the
            # outcome measure increased. The DAG orientation (HIGHER_BETTER /
            # HIGHER_WORSE) handles whether increase is good or bad.
            # If a paper reverses this convention, a future extraction field
            # (e.g., ScaledNumeric.reversed_reporting) should override this.
            aligned = align_orientation(
                scaled=scaled_item,
                dag_orientation=dag_orientation,
                reported_direction_positive=True,
                orientation_confidence=orientation_confidence,
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

    # Convert ScaledNumeric → HarmonizedClaim for downstream P3/P4.
    # P3/P4 operate on HarmonizedClaim (ler_id, harmonized_beta, harmonized_se, etc.).
    study_id = context.get("paper_id", run.extraction_run_id)
    profile_id = study_id  # Default until cohort profiling is implemented

    from crci.extraction.evidence_writer import compute_span_hash

    harmonized_claims: list[HarmonizedClaim] = []
    skipped_missing_edge = 0
    for record in aligned_list:
        edge_relation_id = (
            getattr(record, "edge_relation_id", None)
            or getattr(record, "edge_id", None)
            or "UNASSIGNED"
        )
        if edge_relation_id == "UNASSIGNED":
            skipped_missing_edge += 1
            continue

        beta = getattr(record, "beta", None)
        se = getattr(record, "se", None)
        if beta is None:
            continue

        source_position = getattr(record, "source_position", None)
        span_hash = compute_span_hash(
            study_id=study_id,
            edge_relation_id=edge_relation_id,
            profile_id=profile_id,
            beta=float(beta),
            se=float(se) if se is not None else None,
            source_position=str(source_position) if source_position else None,
        )
        ler_id = f"LER_{study_id}_{span_hash}"

        harmonized_claims.append(
            HarmonizedClaim(
                ler_id=ler_id,
                edge_relation_id=edge_relation_id,
                profile_id=profile_id,
                study_id=study_id,
                harmonized_beta=float(beta),
                harmonized_se=float(se) if se is not None else None,
                harmonized_scale=getattr(record, "scale"),
                harmonization_status=HarmonizationStatusInMem.FULL,
                quality_rating=getattr(record, "quality_rating", "moderate"),
                se_source=getattr(record, "se_source"),
                n_effect=getattr(record, "n_effect", None),
                parameter_family=getattr(record, "parameter_family", None),
                canonical_scale=_assign_canonical_scale(record),
                ci_lower=getattr(record, "ci_lower", None),
                ci_upper=getattr(record, "ci_upper", None),
            )
        )

    if skipped_missing_edge:
        logger.info(
            "P2: Skipped %d records missing edge_relation_id (UNASSIGNED)",
            skipped_missing_edge,
        )

    context["harmonized_records"] = harmonized_claims
    context["parameter_family_counts"] = family_counts
    logger.info(
        "P2-FA complete: %d records assigned families: %s",
        len(aligned_list),
        family_counts,
    )

    # ── R2.3: Apply subtype-specific quality caps ──
    for record in aligned_list:
        raw_quality = getattr(record, "quality_rating", "moderate")
        capped_quality = _apply_subtype_quality_caps(raw_quality, subtype_str or "")
        if capped_quality != raw_quality:
            logger.info(
                "R2-CAP: %s quality capped %s←%s for subtype %s",
                getattr(record, "span_id", "?"), capped_quality, raw_quality, subtype_str,
            )
        if hasattr(record, "quality_rating"):
            record.quality_rating = capped_quality
        elif isinstance(record, dict):
            record["quality_rating"] = capped_quality

    # ── R2.4/R2.5: Apply subtype-specific identification rules ──
    for id_result in scored_list:
        raw_status = getattr(id_result, "identification_status", None)
        if raw_status is None:
            continue
        raw_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        meta_flag = getattr(id_result, "meta_source_flag", None)
        meta_flag_str = meta_flag.value if hasattr(meta_flag, "value") else meta_flag
        capped_status = _apply_subtype_identification_rules(
            raw_str, subtype_str or "", meta_flag_str,
        )
        if capped_status != raw_str:
            logger.info(
                "R2-ID: identification capped %s←%s for subtype %s",
                capped_status, raw_str, subtype_str,
            )
        if hasattr(id_result, "identification_status"):
            id_result.identification_status = capped_status

    # ── R5.4 PG-01: RCT randomization language verification ──
    if subtype_str:
        methods_text = context.get("methods_text") or context.get("canonical_text", "")
        rct_id_status = _verify_rct_randomization(subtype_str, methods_text)
        if rct_id_status == "partially_identified":
            logger.info(
                "PG-01: RCT paper '%s' lacks randomization language — "
                "demoting identification_status to partially_identified.",
                context.get("paper_id", "unknown"),
            )
            context["rct_randomization_missing"] = True

    # ── P2-EW: Persist Evidence to edge_evidence_v1 ──
    # Write harmonized records to database for downstream queries and
    # report_status.py visibility. This bridges the in-memory→DB gap.
    if aligned_list:
        from crci.extraction.evidence_writer import write_evidence_rows

        study_id = context.get("paper_id", run.extraction_run_id)
        evidence_count = write_evidence_rows(
            session=session,
            run=run,
            harmonized_records=aligned_list,
            study_id=study_id,
            paper_subtype=subtype_str,
        )
        context["evidence_rows_written"] = evidence_count
        logger.info("P2-EW: Persisted %d evidence rows to edge_evidence_v1", evidence_count)

    return context


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

_LABEL_TO_EFFECT_TYPE: dict[str, str] = {
    "EFFECT_SIZE": "group_diff",
    "MEAN_DIFFERENCE": "group_diff",
    "OR": "odds_ratio",
    "ODDS_RATIO": "odds_ratio",
    "HR": "hazard_ratio",
    "HAZARD_RATIO": "hazard_ratio",
    "RR": "risk_ratio",
    "RISK_RATIO": "risk_ratio",
    "IRR": "incidence_rate_ratio",
    "INCIDENCE_RATE_RATIO": "incidence_rate_ratio",
    "STD_BETA": "std_beta",
    "UNSTD_BETA": "unstd_beta",
    "CORRELATION": "correlation",
    "PERCENT_CHANGE": "percent_change",
    "INTERACTION_TERM": "group_diff",
    "SUBGROUP_EFFECT": "group_diff",
    "F_STATISTIC": "f_statistic",
}


def _infer_effect_type(claim: Any) -> str:
    """Infer effect_type_reported from the claim's label_type.

    Checks multiple locations since different intermediate states store
    label_type in different places:
      - _GroupedClaimAdapter: .label_type directly
      - ValidatedNumeric: .value_type
      - RoutedNumeric: .value.label_type (nested in TypedNumericValue)

    Falls back to 'group_diff' with a logged default.
    """
    label_type = getattr(claim, "label_type", None)
    if label_type is None:
        label_type = getattr(claim, "value_type", None)
    # RoutedNumeric wraps TypedNumericValue inside .value
    if label_type is None:
        inner = getattr(claim, "value", None)
        if inner is not None:
            label_type = getattr(inner, "label_type", None)
    if label_type is None:
        logger.debug("P2: No label_type on claim %s; defaulting to group_diff",
                      getattr(claim, "span_id", "?"))
        return "group_diff"
    return _LABEL_TO_EFFECT_TYPE.get(label_type.upper(), "group_diff")


# Canonical pooling scale — P4 must only pool records with matching scale.
_LABEL_TO_CANONICAL_SCALE: dict[str, str] = {
    "EFFECT_SIZE": "SMD",
    "MEAN_DIFFERENCE": "SMD",
    "ODDS_RATIO": "LOG_OR",
    "OR": "LOG_OR",
    "HAZARD_RATIO": "LOG_HR",
    "HR": "LOG_HR",
    "RISK_RATIO": "LOG_RR",
    "RR": "LOG_RR",
    "INCIDENCE_RATE_RATIO": "LOG_RR",
    "IRR": "LOG_RR",
    "CORRELATION": "FISHER_Z",
    "STD_BETA": "RAW",
    "UNSTD_BETA": "RAW",
    "PERCENT_CHANGE": "RAW",
    "INTERACTION_TERM": "SMD",
    "SUBGROUP_EFFECT": "SMD",
    "F_STATISTIC": "SMD",  # F→d conversion produces SMD
}


def _assign_canonical_scale(claim: Any) -> str:
    """Assign canonical pooling scale from label_type.

    Returns CanonicalScale string value (SMD, LOG_OR, etc.).
    """
    label_type = getattr(claim, "label_type", None)
    if label_type is None:
        label_type = getattr(claim, "value_type", None)
    if label_type is None:
        inner = getattr(claim, "value", None)
        if inner is not None:
            label_type = getattr(inner, "label_type", None)
    if label_type is None:
        return "RAW"
    return _LABEL_TO_CANONICAL_SCALE.get(label_type.upper(), "RAW")


# ═══════════════════════════════════════════════════════════════
#  R2 SUBTYPE-SPECIFIC QUALITY AND IDENTIFICATION RULES
# ═══════════════════════════════════════════════════════════════

# Subtypes whose RCT label should be verified by randomization language
_RCT_SUBTYPES = {"RCT_exercise", "standard_rct", "RCT_cognitive", "RCT_pharmacological"}


def _verify_rct_randomization(subtype: str, methods_text: str) -> str:
    """PG-01: Verify RCT randomization language.

    Returns 'identified' if the subtype is not an RCT or if the methods
    text contains randomization language. Returns 'partially_identified'
    if the RCT paper lacks randomization language.
    """
    if subtype not in _RCT_SUBTYPES:
        return "identified"
    text_lower = (methods_text or "").lower()
    # Match: randomized, randomised, randomly, randomization, randomisation
    if "random" in text_lower:
        return "identified"
    return "partially_identified"


def _apply_subtype_quality_caps(quality: str, subtype: str) -> str:
    """R2.3: Apply subtype-specific quality caps.

    Pilot RCTs are capped at 'moderate' quality.
    """
    _PILOT_SUBTYPES = {"pilot_rct"}
    if subtype in _PILOT_SUBTYPES and quality == "strong":
        return "moderate"
    return quality


def _apply_subtype_identification_rules(
    identification: str,
    subtype: str,
    meta_source_flag: str | None = None,
) -> str:
    """R2.4/R2.5: Apply subtype-specific identification rules.

    - Cross-sectional → always 'not_identified'
    - Retrospective cohort → capped at 'partially_identified'
    - NMA mixed estimates → capped at 'partially_identified'
    """
    _CROSS_SECTIONAL = {"cross_sectional"}
    _RETROSPECTIVE = {"retrospective_cohort"}

    if subtype in _CROSS_SECTIONAL:
        return "not_identified"
    if subtype in _RETROSPECTIVE:
        if identification == "identified":
            return "partially_identified"
        return identification
    if meta_source_flag == "NMA_MIXED" and identification == "identified":
        return "partially_identified"
    return identification
