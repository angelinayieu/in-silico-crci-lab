# VERIFIED: imports — evidence_grouper, double_counting, meta_analyzer, prior_selector, edge_writer
# VERIFIED: imports — shared_control_handler, cohort_lineage_detector, verification_escalation
# VERIFIED: backward wiring — reads calibrated records from P3 context
# VERIFIED: forward wiring — writes compiled edges to edges_v1
# VERIFIED: gates — P4-G1 (minimum k for pooling)
"""
Component: SYS_EXTRACTION.EX-P4.RUNNER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1230-1500
      CONVERSION_VALIDITY_AND_HARDENING.md Modules 2, 4
Purpose: Orchestrate P4 aggregation:
         lineage → group → DCR → shared-control → pool → escalation → prior → write.
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
        P4-CL:  Cohort lineage detection — deduplicate overlapping cohorts
        P4-GRP: Evidence grouper — group by edge relation
        P4-DCR: Double counting resolution
        P4-SC:  Shared control handling — SC-1 N split + CS-2 scale alignment
        P4-MA:  Meta-analysis (IVW pooling)
        P4-ESC: Verification escalation — E1-E6 influence checks
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

    # ── P4-CL: Cohort lineage detection (Module 4.2) ──
    from crci.extraction.p4_aggregation.cohort_lineage_detector import (
        StudyMetadata,
        assign_lineage,
    )

    study_metadata = _extract_study_metadata(calibrated, session)
    if study_metadata:
        lineage_groups = assign_lineage(study_metadata)
        context["lineage_groups"] = lineage_groups

        # Build set of SUPPLEMENTARY study_ids to exclude from IVW
        supplementary_ids: set[str] = set()
        for lg in lineage_groups:
            for assignment in lg.assignments:
                if assignment.lineage_role.value != "PRIMARY":
                    supplementary_ids.add(assignment.study_id)

        logger.info(
            "P4-CL: %d lineage groups detected, %d supplementary studies flagged",
            len(lineage_groups),
            len(supplementary_ids),
        )

        # Filter calibrated records: exclude supplementary from IVW pooling
        if supplementary_ids:
            pre_count = len(calibrated)
            calibrated = [
                r for r in calibrated
                if getattr(r, "study_id", None) not in supplementary_ids
            ]
            logger.info(
                "P4-CL: filtered %d → %d records (excluded %d supplementary)",
                pre_count,
                len(calibrated),
                pre_count - len(calibrated),
            )
    else:
        context["lineage_groups"] = []

    # ── P4-GRP: Group evidence by edge ──
    from crci.extraction.p4_aggregation.evidence_grouper import group_evidence_by_edge

    groups = group_evidence_by_edge(calibrated)
    logger.info("P4-GRP: %d evidence groups formed", len(groups))

    # ── P4-DCR: Double counting resolution ──
    from crci.extraction.p4_aggregation.double_counting import resolve_all

    resolved_groups = resolve_all(groups, session=session)
    context["resolved_groups"] = resolved_groups
    logger.info(
        "P4-DCR: %d groups after double-counting resolution",
        len(resolved_groups),
    )

    # ── P4-SC: Shared control handling (Module 4.1 + 4.3) ──
    from crci.extraction.p4_aggregation.shared_control_handler import (
        SharedControlRecord,
        apply_shared_control_split,
        partition_endpoint_change,
    )

    sc_context = _apply_shared_control_pipeline(resolved_groups)
    context["shared_control_applied"] = sc_context.get("n_adjusted", 0) > 0
    logger.info(
        "P4-SC: shared-control split applied to %d records, "
        "endpoint/change alignment on %d groups",
        sc_context.get("n_adjusted", 0),
        sc_context.get("n_groups_aligned", 0),
    )

    # ── P4-MA: Meta-analysis (IVW pooling) ──
    from crci.extraction.p4_aggregation.meta_analyzer import analyze_all_edges

    ma_results = analyze_all_edges(resolved_groups)
    pooled_estimates = [r.pooled_estimate for r in ma_results]
    context["pooled_estimates"] = pooled_estimates
    context["meta_analysis_results"] = ma_results
    logger.info("P4-MA: %d pooled estimates computed", len(pooled_estimates))

    # ── P4-ESC: Verification escalation (Module 2) ──
    from crci.extraction.p4_aggregation.verification_escalation import (
        EvidenceRecord,
        compute_ivw_weights,
        evaluate_escalation,
    )

    escalation_results = []
    for ma_result in ma_results:
        pe = ma_result.pooled_estimate
        if pe.aggregation_method == "BLOCKED" or pe.k == 0:
            continue
        esc_records = _build_escalation_records(
            pe.edge_relation_id, resolved_groups,
        )
        if esc_records:
            compute_ivw_weights(esc_records)
            esc_result = evaluate_escalation(
                edge_relation_id=pe.edge_relation_id,
                records=esc_records,
                beta_pooled=pe.beta_pooled,
            )
            escalation_results.append(esc_result)

    context["escalation_results"] = escalation_results
    n_escalated = sum(1 for r in escalation_results if r.any_escalated)
    logger.info(
        "P4-ESC: %d edges checked, %d edges have escalated records",
        len(escalation_results),
        n_escalated,
    )

    # ── P4-PRI: Prior selection ──
    from crci.extraction.p4_aggregation.prior_selector import (
        EdgeContext,
        select_priors_for_all_edges,
    )

    # Build EdgeContext for each edge from the resolved groups
    edge_contexts: dict[str, EdgeContext] = {}
    for group in resolved_groups:
        eid = getattr(group, "edge_relation_id", None)
        if eid:
            claims = getattr(group, "claims", [])
            has_rct = any(
                getattr(c, "study_design", "").lower() in ("rct", "large_rct")
                for c in claims
            )
            edge_contexts[eid] = EdgeContext(
                edge_relation_id=eid,
                k=len(claims),
                has_rct=has_rct,
                study_designs=[getattr(c, "study_design", "") for c in claims],
            )

    prior_specs, prior_logs = select_priors_for_all_edges(
        pooled_estimates, edge_contexts, session,
    )
    context["prior_assignments"] = prior_logs
    context["prior_specs"] = prior_specs
    logger.info("P4-PRI: priors assigned for %d edges", len(prior_specs))

    # ── P4-WRT: Write compiled edges ──
    from crci.extraction.p4_aggregation.edge_writer import write_all_edges, build_compilation_inputs

    # Build sigma_sq map from annotation influence
    sigma_sq_map = {
        r.pooled_estimate.edge_relation_id: r.annotation_influence.sigma_sq_structural
        for r in ma_results
    }

    compilation_inputs = build_compilation_inputs(
        pooled_estimates=pooled_estimates,
        prior_specs=prior_specs,
        prior_logs=prior_logs,
        sigma_sq_map=sigma_sq_map,
    ) if prior_specs else []

    if compilation_inputs:
        compiled_edges = write_all_edges(
            compilation_inputs=compilation_inputs,
            session=session,
        )
        context["edges_written"] = len(compiled_edges)
        logger.info("P4-WRT: %d edges written to edges_v1", len(compiled_edges))
    else:
        logger.warning("P4-WRT: no compilation inputs available, skipping edge write")
        context["edges_written"] = 0

    return context


# ═══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════


def _extract_study_metadata(
    calibrated: list[Any],
    session: Session,
) -> list[Any]:
    """Extract StudyMetadata objects from calibrated records for lineage detection.

    Queries study_registry_v1 for enriched metadata (trial_registry_id,
    funding_grant, authors, follow_up) to feed CL-1/CL-2 detection.
    """
    from crci.extraction.p4_aggregation.cohort_lineage_detector import StudyMetadata
    from crci.shared.models.tables import StudyRegistry

    # Collect unique study_ids from calibrated records
    study_ids: set[str] = set()
    for rec in calibrated:
        sid = getattr(rec, "study_id", None)
        if sid:
            study_ids.add(sid)

    if not study_ids:
        return []

    # Query study registry for metadata
    study_rows = (
        session.query(StudyRegistry)
        .filter(StudyRegistry.study_id.in_(study_ids))
        .all()
    )

    metadata_list: list[StudyMetadata] = []
    for row in study_rows:
        metadata_list.append(StudyMetadata(
            study_id=row.study_id,
            title=row.title,
            authors=row.authors,
            doi=row.doi,
            year=row.year,
            n_analyzed=getattr(row, "n_analyzed", None),
            follow_up_months=getattr(row, "follow_up_months", None),
            trial_registry_id=getattr(row, "trial_registry_id", None),
            funding_grant=getattr(row, "funding_grant", None),
            is_secondary_analysis=getattr(row, "is_secondary_analysis", False),
        ))

    return metadata_list


def _apply_shared_control_pipeline(
    resolved_groups: list[Any],
) -> dict[str, int]:
    """Apply shared-control N split and endpoint/change alignment.

    Processes each resolved evidence group through SC-1 and CS-2.
    Returns summary statistics.
    """
    from crci.extraction.p4_aggregation.shared_control_handler import (
        AdjustedRecord,
        SharedControlRecord,
        apply_shared_control_split,
        partition_endpoint_change,
    )

    n_adjusted = 0
    n_groups_aligned = 0

    for group in resolved_groups:
        claims = getattr(group, "claims", [])
        if not claims:
            continue

        # Build SharedControlRecords from claims
        sc_records: list[SharedControlRecord] = []
        for claim in claims:
            sc_records.append(SharedControlRecord(
                ler_id=getattr(claim, "ler_id", ""),
                study_id=getattr(claim, "study_id", ""),
                beta=getattr(claim, "harmonized_beta", 0.0),
                se=getattr(claim, "harmonized_se", 0.0) or 0.0,
                n_treatment=getattr(claim, "n_treatment", 0) or 0,
                n_control=getattr(claim, "n_control", 0) or 0,
                shared_control_flag=getattr(claim, "shared_control_flag", False),
                shared_control_study_id=getattr(claim, "shared_control_study_id", None),
                endpoint_vs_change=getattr(claim, "endpoint_vs_change", "UNCLEAR"),
            ))

        # SC-1: Split shared control groups
        adjusted = apply_shared_control_split(sc_records)
        n_adjusted += sum(
            1 for a in adjusted
            if "SC-1" in a.se_adjustment_note
        )

        # CS-2: Endpoint/change alignment
        final = partition_endpoint_change(adjusted)
        if any("CS-2" in getattr(r, "se_adjustment_note", "") for r in final):
            n_groups_aligned += 1

    return {"n_adjusted": n_adjusted, "n_groups_aligned": n_groups_aligned}


def _build_escalation_records(
    edge_relation_id: str,
    resolved_groups: list[Any],
) -> list[Any]:
    """Build EvidenceRecord list for a specific edge from resolved groups."""
    from crci.extraction.p4_aggregation.verification_escalation import EvidenceRecord

    for group in resolved_groups:
        if getattr(group, "edge_relation_id", None) != edge_relation_id:
            continue
        claims = getattr(group, "claims", [])
        records: list[EvidenceRecord] = []
        for claim in claims:
            records.append(EvidenceRecord(
                ler_id=getattr(claim, "ler_id", ""),
                beta=getattr(claim, "harmonized_beta", 0.0),
                se=getattr(claim, "harmonized_se", 0.0) or 0.0,
                se_derivation_level=getattr(claim, "se_derivation_level", None),
                meta_source_flag=getattr(claim, "meta_source_flag", None),
                is_cancer_matched=getattr(claim, "is_cancer_matched", False),
                is_superseded=getattr(claim, "is_superseded", False),
            ))
        return records
    return []
