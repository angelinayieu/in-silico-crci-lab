# VERIFIED: imports — layers, se_eff_assembly
# VERIFIED: backward wiring — reads harmonized records from P2 context
# VERIFIED: forward wiring — writes calibrated records for P4
# VERIFIED: gates — P3-G1 (layer validity)
"""
Component: SYS_EXTRACTION.EX-P3.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1135-1230
Purpose: Orchestrate P3 seven-layer heterogeneity calibration.
         Applies design, GRADE, temporal, scope, freshness, structural,
         and between-study layers to SE_eff.
Reads: Harmonized records from P2
Writes: Calibrated records with SE_eff for P4 aggregation
Gates: P3-G1 (layer validity — all 7 layers must be applied)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.enums import MissingnessCode
from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p3_heterogeneity(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run P3 seven-layer heterogeneity calibration.

    Steps:
        P3-L1 through P3-L7: Apply all 7 calibration layers
        P3-ASM: Assemble SE_eff from calibrated components

    Args:
        session: Active database session.
        run: Current ExtractionRun instance.
        context: Pipeline context with harmonized records.

    Returns:
        Updated context with calibrated records.
    """
    paper_id = context.get("paper_id", "unknown")
    harmonized_records = context.get("harmonized_records", [])

    logger.info(
        "P3: Calibrating %d records for %s through 7 layers",
        len(harmonized_records), paper_id,
    )

    if not harmonized_records:
        logger.warning("P3: No harmonized records to calibrate")
        context["calibrated_records"] = []
        return context

    # Resolve study design from P0 classification as fallback
    # when AG02 (DesignAgent) fails and records default to "unclassified"
    classified_paper = context.get("classified_paper", {})
    p0_study_design = classified_paper.get("study_design", "other")
    if hasattr(p0_study_design, "value"):
        p0_study_design = p0_study_design.value
    p0_study_design = str(p0_study_design) if p0_study_design else "other"

    # Debug: log what fields the harmonized records actually have
    if harmonized_records:
        sample = harmonized_records[0]
        logger.info(
            "P3: Record type=%s, fields=%s",
            type(sample).__name__,
            [f for f in dir(sample) if not f.startswith("_")],
        )
        # Log SE/beta availability across all records
        has_se = sum(1 for r in harmonized_records if getattr(r, "se", None) is not None)
        has_beta = sum(1 for r in harmonized_records if getattr(r, "beta", None) is not None)
        logger.info(
            "P3: Data availability: %d/%d have SE, %d/%d have beta",
            has_se, len(harmonized_records), has_beta, len(harmonized_records),
        )

    # ── P3-L1 through P3-L7: Apply all 7 layers ──
    from crci.extraction.p3_heterogeneity.layers import apply_all_layers

    layered_records = apply_all_layers(harmonized_records, session=session)
    logger.info("P3 layers complete: %d records calibrated", len(layered_records))

    # ── P3-ASM: Assemble SE_eff from layered components ──
    from crci.extraction.p3_heterogeneity.se_eff_assembly import (
        SEEffInput,
        compute_se_eff,
    )

    # DW#6 fix: Load annotation-derived σ²_structural per edge
    # Uses shared_annotation_features → annotation_lifecycle → study_annotations_v1
    _sigma_sq_cache: dict[str, float] = {}
    try:
        from crci.extraction.shared_annotation_features import get_structural_variance
        # Collect all unique edge_relation_ids from the layered records
        _edge_ids = {
            getattr(lr.record, "edge_relation_id", None)
            for lr in layered_records
        } - {None}
        for eid in _edge_ids:
            ann_features = get_structural_variance(session, eid)
            _sigma_sq_cache[eid] = ann_features.sigma_sq_structural
            if ann_features.annotation_ids:
                logger.info(
                    "P3: σ²_structural for edge %s = %.4f "
                    "(from %d annotation(s): %s)",
                    eid, ann_features.sigma_sq_structural,
                    len(ann_features.annotation_ids),
                    ann_features.annotation_ids[:3],
                )
        if _sigma_sq_cache:
            logger.info(
                "P3: Loaded annotation-derived σ²_structural for %d edges",
                len(_sigma_sq_cache),
            )
    except Exception as exc:
        logger.warning(
            "P3: Could not load annotation-derived σ²_structural: %s "
            "— using config default for all edges",
            exc,
        )

    calibrated_records = []
    p3_gate_failures = []

    for layered in layered_records:
        rec = layered.record
        se_raw = getattr(rec, "se", None) or getattr(rec, "harmonized_se", None)

        # ── CI→SE defense-in-depth fallback ──
        # If SE is missing but CI bounds exist, derive SE via NP-11.
        # TB's numeric_parser already does this, but the derived SE may
        # not propagate through P2 to this point.  This ensures P3 doesn't
        # drop records that have CI data.
        if se_raw is None:
            ci_lo = (
                getattr(rec, "ci_lower", None)
                or getattr(rec, "harmonized_ci_lower", None)
            )
            ci_hi = (
                getattr(rec, "ci_upper", None)
                or getattr(rec, "harmonized_ci_upper", None)
            )
            if ci_lo is not None and ci_hi is not None and ci_hi > ci_lo:
                # NP-11: SE = (upper - lower) / (2 × z)
                se_raw = (ci_hi - ci_lo) / (
                    2 * config.SE_FROM_CI_Z_MULTIPLIER
                )
                logger.info(
                    "P3: Derived SE=%.4f from CI [%.4f, %.4f] for %s "
                    "(defense-in-depth fallback)",
                    se_raw, ci_lo, ci_hi,
                    getattr(rec, "ler_id", "?"),
                )

        try:
            if se_raw is None:
                se_source = getattr(rec, "se_source", "UNKNOWN")
                raise GateViolation(
                    "P3-G-SE",
                    f"Record {getattr(rec, 'ler_id', '?')} has no SE "
                    f"(se_source={se_source})",
                    context={
                        "ler_id": getattr(rec, "ler_id", ""),
                        "has_ci": getattr(rec, "ci_lower", None) is not None
                               or getattr(rec, "harmonized_ci_lower", None) is not None,
                        "has_p": getattr(rec, "p_value", None) is not None,
                        "has_n": getattr(rec, "n_total", None) is not None
                               or getattr(rec, "n_effect", None) is not None,
                        "missingness_code": MissingnessCode.PARSE_FAILURE.value,
                    },
                )

            # Use P0's study_design as fallback when AG02 fails
            record_design = getattr(rec, "study_design", "unclassified")
            if record_design == "unclassified" and p0_study_design != "other":
                record_design = p0_study_design
                logger.debug(
                    "P3-ASM: using P0 study_design '%s' as fallback for "
                    "record %s (AG02 returned 'unclassified')",
                    p0_study_design,
                    getattr(rec, "ler_id", "?"),
                )

            # DW#6 fix: look up annotation-derived σ²_structural for this edge
            _rec_eid = getattr(rec, "edge_relation_id", None)
            _ann_sigma = _sigma_sq_cache.get(_rec_eid) if _rec_eid else None

            inp = SEEffInput(
                ler_id=getattr(rec, "ler_id", ""),
                se_raw=se_raw,
                study_design=record_design,
                n_total=(
                    getattr(rec, "n_total", None)
                    or getattr(rec, "n_effect", None)
                ),
                w_scope=layered.w_scope,
                betas=getattr(rec, "group_betas", None) or [],
                ses=getattr(rec, "group_ses", None) or [],
                validation_status=getattr(rec, "cancer_validation_status", "general_population"),
                grade_level=getattr(rec, "grade_level", "MODERATE"),
                days_since_measurement=getattr(rec, "days_since_measurement", 0.0),
                is_trait=getattr(rec, "is_trait", False),
                sigma_sq_structural=_ann_sigma,
                edge_relation_id=_rec_eid,
            )
            se_eff_result = compute_se_eff(inp)
            # Attach SE_eff to the record in the field that downstream
            # aggregation actually consumes.
            if hasattr(rec, "harmonized_se"):
                if hasattr(rec, "model_copy"):
                    rec = rec.model_copy(
                        update={"harmonized_se": se_eff_result.se_effective}
                    )
                else:
                    try:
                        rec.harmonized_se = se_eff_result.se_effective
                    except Exception:
                        pass
            elif hasattr(rec, "se"):
                # Fallback for legacy record shapes
                try:
                    rec.se = se_eff_result.se_effective
                except Exception:
                    pass
            calibrated_records.append(rec)

        except GateViolation as gv:
            logger.info("P3-ASM gate failure: %s", gv)
            p3_gate_failures.append({
                "ler_id": gv.context.get("ler_id", ""),
                "gate_id": gv.gate_id,
                "reason": str(gv),
                "missingness_code": gv.context.get(
                    "missingness_code", MissingnessCode.PARSE_FAILURE.value
                ),
                "has_ci": gv.context.get("has_ci", False),
                "has_p": gv.context.get("has_p", False),
                "has_n": gv.context.get("has_n", False),
            })
            continue
        except ValueError as exc:
            # Temporal exclusion (>90 days) — record removed by design
            logger.info("P3-ASM: record excluded: %s", exc)
        except Exception as exc:
            logger.warning("P3-ASM: SE_eff computation failed: %s", exc)

    # Persist gate failure tracking for missingness provenance
    context["p3_gate_failures"] = p3_gate_failures
    context["p3_survival_rate"] = (
        len(calibrated_records) / len(layered_records)
        if layered_records
        else 0.0
    )
    context["calibrated_records"] = calibrated_records

    logger.info(
        "P3 complete: %d/%d records survived (%.0f%% survival rate), "
        "%d gate failures",
        len(calibrated_records),
        len(layered_records),
        context["p3_survival_rate"] * 100,
        len(p3_gate_failures),
    )
    if p3_gate_failures:
        # Log missingness breakdown
        from collections import Counter
        miss_codes = Counter(
            f.get("missingness_code", "UNKNOWN") for f in p3_gate_failures
        )
        logger.info(
            "P3 missingness breakdown: %s",
            dict(miss_codes),
        )

    # ── Slice-level hard stop: prevent P4-P7 from running on empty ──
    # If records entered P3 but none survived, this is a data flow failure
    # that should halt the pipeline rather than producing a false "completed".
    if context["p3_survival_rate"] == 0.0 and len(layered_records) > 0:
        raise GateViolation(
            "P3-SLICE-HALT",
            f"Zero records survived P3 ({len(p3_gate_failures)} gate "
            f"failures out of {len(layered_records)} input records). "
            f"Pipeline cannot produce evidence. Halting.",
            context={
                "n_in": len(layered_records),
                "n_failed": len(p3_gate_failures),
            },
        )

    return context
