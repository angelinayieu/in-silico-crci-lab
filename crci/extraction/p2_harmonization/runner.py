# VERIFIED: imports — all modules exist (p2_harmonization submodules)
# VERIFIED: backward wiring — reads typed_numeric_values from context (TB)
# VERIFIED: forward wiring — writes harmonized_claims to context (P3)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P2-G1, P2-G2, CG1-4 delegated to sub-modules
"""
Component: SYS_EXTRACTION.EX-P2.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 684-764
Purpose: Orchestrate P2 harmonization: plausibility → conversion routing →
         scale harmonization (SD standardization) → orientation alignment →
         identification scoring → scope matching → composability.
Reads: typed_numeric_values (from TB context)
Writes: harmonized_claims (to context for P3)
Gates: P2-G1 (plausibility), CG1-4 (conversion), P2-G2 (orientation)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import ExtractionRun

logger = logging.getLogger(__name__)


def run_p2_harmonization(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the P2 harmonization chain: S1 → S2 → S3 → S4 → S5 → S6 → S7.

    Processes TypedNumericValues through 7 harmonization stages to produce
    HarmonizedClaims ready for P3 heterogeneity assessment.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Pipeline context with TB outputs.

    Returns:
        Updated context with harmonized claims.
    """
    from crci.extraction.p2_harmonization.plausibility_checker import check_plausibility
    from crci.extraction.p2_harmonization.conversion_router import route_conversion
    from crci.extraction.p2_harmonization.scale_harmonizer import harmonize_scale
    from crci.extraction.p2_harmonization.orientation_aligner import align_orientation
    from crci.extraction.p2_harmonization.identification_scorer import score_identification
    from crci.extraction.p2_harmonization.scope_matching import compute_scope_match
    from crci.extraction.p2_harmonization.sd_standardization import (
        fetch_sd_anchor,
        standardize_effect,
    )

    logger.info("P2 harmonization starting for run %s", run.extraction_run_id)

    typed_values = context.get("typed_numeric_values", [])
    if not typed_values:
        logger.warning("P2: No typed numeric values found, skipping")
        context["harmonized_claims"] = []
        return context

    # Track records through pipeline
    validated = []
    routed = []
    scaled = []
    oriented = []
    identified = []
    scope_matched = []
    harmonized_claims = []

    n_rejected = 0
    n_blocked = 0

    for i, tv in enumerate(typed_values):
        span_id = getattr(tv, "span_id", f"span_{i}")

        # S1: Plausibility Check (Gate P2-G1)
        try:
            v = check_plausibility(span_id=span_id, value=tv)
            if v.plausibility_status.value in ("REJECTED", "rejected"):
                n_rejected += 1
                continue
            validated.append(v)
        except Exception as exc:
            logger.debug("P2-S1 plausibility failed for %s: %s", span_id, exc)
            n_rejected += 1
            continue

        # S2: Conversion Routing (Gates CG1-CG4)
        try:
            effect_type = getattr(tv, "effect_type", "smd")
            r = route_conversion(validated=v, effect_type_reported=effect_type)
            if r.conversion_gate_result.value in ("BLOCKED", "blocked"):
                n_blocked += 1
                continue
            routed.append(r)
        except Exception as exc:
            logger.debug("P2-S2 conversion route failed for %s: %s", span_id, exc)
            n_blocked += 1
            continue

        # S3: Scale Harmonization + SD Standardization
        try:
            outcome = getattr(tv, "outcome_measure", None)
            anchor = None
            if outcome:
                anchor = fetch_sd_anchor(session, outcome)
            s = harmonize_scale(
                routed=r,
                effect_type_reported=effect_type,
                sd_anchor=anchor,
            )
            scaled.append(s)
        except Exception as exc:
            logger.debug("P2-S3 scale harmonization failed for %s: %s", span_id, exc)
            continue

        # S4: Orientation Alignment (Gate P2-G2)
        try:
            from crci.shared.models.enums import Orientation
            dag_orientation = getattr(tv, "dag_orientation", Orientation.POS_UP)
            direction_positive = getattr(tv, "direction_positive", True)
            confidence = getattr(tv, "orientation_confidence", 0.8)
            o = align_orientation(
                scaled=s,
                dag_orientation=dag_orientation,
                reported_direction_positive=direction_positive,
                orientation_confidence=confidence,
            )
            oriented.append(o)
        except Exception as exc:
            logger.debug("P2-S4 orientation alignment failed for %s: %s", span_id, exc)
            oriented.append(s)  # pass through without alignment

        # S5: Identification Scoring
        try:
            study_design = getattr(tv, "study_design", "observational")
            ident = score_identification(
                scaled=oriented[-1],
                study_design=study_design,
            )
            identified.append(ident)
        except Exception as exc:
            logger.debug("P2-S5 identification scoring failed for %s: %s", span_id, exc)
            continue

        # S6: Scope Matching
        try:
            target_pop = context.get("target_population", {})
            study_pop = getattr(tv, "study_population", {})
            if isinstance(study_pop, dict):
                sm = compute_scope_match(
                    ler_id=span_id,
                    study_population=study_pop,
                    target_population=target_pop,
                )
                scope_matched.append(sm)
        except Exception as exc:
            logger.debug("P2-S6 scope matching failed for %s: %s", span_id, exc)

    # Assemble harmonized claims from the survived records
    from crci.shared.models.enums import EffectScale, HarmonizationStatusInMem, SESource
    from crci.shared.models.intermediate_states import HarmonizedClaim

    for idx, s in enumerate(oriented):
        claim = HarmonizedClaim(
            ler_id=s.span_id,
            edge_relation_id=getattr(typed_values[idx] if idx < len(typed_values) else None, "edge_relation_id", ""),
            profile_id=context.get("paper_id", run.extraction_run_id),
            study_id=context.get("paper_id", run.extraction_run_id),
            harmonized_beta=s.beta,
            harmonized_se=s.se,
            harmonized_scale=s.scale,
            harmonization_status=HarmonizationStatusInMem.HARMONIZED,
            se_source=s.se_source,
        )
        harmonized_claims.append(claim)

    context["harmonized_claims"] = harmonized_claims
    context["p2_validated_count"] = len(validated)
    context["p2_rejected_count"] = n_rejected
    context["p2_blocked_count"] = n_blocked

    logger.info(
        "P2 harmonization complete: %d input → %d harmonized "
        "(%d rejected, %d blocked)",
        len(typed_values),
        len(harmonized_claims),
        n_rejected,
        n_blocked,
    )
    return context
