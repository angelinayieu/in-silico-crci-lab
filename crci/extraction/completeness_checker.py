# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads from edge_evidence_v1, population_norms_v1,
#           temporal_evidence_v1, instrument_evidence_v1, subgroup_evidence_v1,
#           study_registry_v1 via ORM queries
# VERIFIED: forward wiring — writes ExtractionCompleteness rows to extraction_completeness_v1
# VERIFIED: no hardcoded formula parameters
# VERIFIED: no stubs — all functions fully implemented
"""
Component: Extraction — Completeness Checker (Slice 7)
Spec: IMPLEMENTATION_SLICES.md Slice 7, Steps 7a-7c
Purpose: Automated verification that a paper's extraction is complete.
         Generates an ExtractionReport with:
         - Expected vs populated families by study design
         - Layer readiness (L1/L4/L5/L7)
         - Effect-size unit consistency check
         - Blocking vs non-blocking issue classification
         - defaults_fired counter (makes silent defaulting visible)

Reads: study_registry_v1, edge_evidence_v1, population_norms_v1,
       temporal_evidence_v1, instrument_evidence_v1, subgroup_evidence_v1
Writes: ExtractionCompleteness rows to extraction_completeness_v1
Gates: None (read-only analysis + reporting)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from crci.shared.models.tables import (
    EdgeEvidence,
    ExtractionCompleteness,
    InstrumentEvidence,
    PopulationNorms,
    StudyRegistry,
    SubgroupEvidence,
    TemporalEvidence,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data structure
# ============================================================================

@dataclass
class ExtractionReport:
    """Complete extraction quality report for a single paper."""

    study_id: str
    study_design: str
    expected_families: list[str]
    populated_families: dict[str, int]  # {"F1": 4, "F2": 6, ...}
    missing_families: list[str]
    edge_evidence_issues: list[str]
    layer_readiness: dict[str, str]  # {"L1": "READY", "L4": "WILL_DEFAULT"}
    completeness_score: float  # 0.0 to 1.0
    blocking_issues: list[str]
    non_blocking_issues: list[str]
    defaults_fired: dict[str, int]  # {"L1": 0, "L4": 2, "L5": 0, "L7": 4}


# ============================================================================
# Family mapping by study design
# ============================================================================

# Family code → (table description, ORM class or label)
_FAMILY_LABELS = {
    "F1": "edge_evidence",
    "F2": "instrument_evidence",
    "F3": "population_norms",
    "F4": "temporal_evidence",
    "F6": "subgroup_evidence",
}


def _expected_families_for_design(study_design: str) -> list[str]:
    """Determine which evidence families should be present for a study design.

    Args:
        study_design: Study design string (e.g. "RCT", "systematic_review").

    Returns:
        List of family codes expected for this design.

    Rules from spec:
        RCT → F1, F2, F3, F4 (and optionally F6)
        SR/MA → F1 only (included_study_ids_json, NOT F3-F6)
        Cross-sectional → F1, F3
        Default → F1 (always need edge evidence)
    """
    design = (study_design or "").strip().lower()

    if design in ("rct", "large_rct", "small_rct_default"):
        return ["F1", "F2", "F3", "F4"]
    elif design in ("systematic_review", "meta_analysis", "sr", "ma"):
        return ["F1"]
    elif design in ("cross_sectional", "cross-sectional"):
        return ["F1", "F3"]
    elif design in ("cohort", "prospective_cohort", "retrospective_cohort"):
        return ["F1", "F3", "F4"]
    else:
        # Default: at minimum expect edge evidence
        return ["F1"]


# ============================================================================
# DB query helpers (mock-friendly)
# ============================================================================

def _query_study_design(session: Session, study_id: str) -> str | None:
    """Look up study_design from study_registry_v1."""
    row = session.query(StudyRegistry).filter(
        StudyRegistry.study_id == study_id
    ).first()
    if row is None:
        return None
    # Treat empty string as None
    return row.study_design if row.study_design else None


def _query_family_counts(session: Session, study_id: str) -> dict[str, int]:
    """Count rows per family table for this study_id."""
    counts = {}

    counts["F1"] = session.query(func.count(EdgeEvidence.ler_id)).filter(
        EdgeEvidence.study_id == study_id
    ).scalar() or 0

    counts["F2"] = session.query(func.count(InstrumentEvidence.id)).filter(
        InstrumentEvidence.study_id == study_id
    ).scalar() or 0

    counts["F3"] = session.query(func.count(PopulationNorms.id)).filter(
        PopulationNorms.study_id == study_id
    ).scalar() or 0

    counts["F4"] = session.query(func.count(TemporalEvidence.id)).filter(
        TemporalEvidence.study_id == study_id
    ).scalar() or 0

    counts["F6"] = session.query(func.count(SubgroupEvidence.id)).filter(
        SubgroupEvidence.study_id == study_id
    ).scalar() or 0

    return counts


def _query_edge_evidence_rows(session: Session, study_id: str) -> list:
    """Get all edge_evidence rows for layer readiness analysis."""
    return session.query(EdgeEvidence).filter(
        EdgeEvidence.study_id == study_id
    ).all()


# ============================================================================
# Layer readiness analysis
# ============================================================================

def _analyze_layer_readiness(
    edge_rows: list,
    has_temporal_evidence: bool = False,
) -> tuple[dict[str, str], dict[str, int], list[str], list[str]]:
    """Analyze L1/L4/L5/L6/L7 readiness across edge evidence rows.

    Returns:
        (layer_readiness, defaults_fired, blocking_issues, edge_evidence_issues)
    """
    n = len(edge_rows)
    if n == 0:
        return (
            {"L1": "NO_DATA", "L4": "NO_DATA", "L5": "NO_DATA", "L6": "NO_DATA", "L7": "NO_DATA"},
            {"L1": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0},
            [],
            [],
        )

    # Count NULL/missing per layer
    l1_null = sum(1 for r in edge_rows if not getattr(r, "study_design", None))
    l4_null = sum(1 for r in edge_rows if not getattr(r, "cancer_validation_status", None))
    l5_null = sum(1 for r in edge_rows if not getattr(r, "rob_overall", None))
    l7_null = sum(1 for r in edge_rows if not getattr(r, "pub_year", None))

    # L6: Temporal data — count rows where days_since_measurement is NULL/0
    # (0.0 is the silent default when no temporal evidence exists)
    l6_defaulting = sum(
        1 for r in edge_rows
        if not getattr(r, "days_since_measurement", None)
        or getattr(r, "days_since_measurement", 0.0) == 0.0
    )
    # If no temporal_evidence rows exist for the study at all, ALL rows are defaulting
    if not has_temporal_evidence:
        l6_defaulting = n

    defaults_fired = {"L1": l1_null, "L4": l4_null, "L5": l5_null, "L6": l6_defaulting, "L7": l7_null}

    # Determine readiness status
    layer_readiness = {}
    blocking = []
    issues = []

    # L1: study_design — NULL is BLOCKING (max SE multiplier 3.0×)
    if l1_null == 0:
        layer_readiness["L1"] = "READY"
    elif l1_null == n:
        layer_readiness["L1"] = "BLOCKED"
        blocking.append(f"study_design NULL for all {n} rows — L1 will apply max SE multiplier 3.0×")
    else:
        layer_readiness["L1"] = "BLOCKED"
        blocking.append(f"study_design NULL for {l1_null}/{n} rows")
    if l1_null > 0:
        issues.append(f"study_design NULL for {l1_null}/{n} rows")

    # L4: cancer_validation_status — NULL is non-blocking (defaults to general_population)
    if l4_null == 0:
        layer_readiness["L4"] = "READY"
    else:
        layer_readiness["L4"] = "WILL_DEFAULT"
        issues.append(f"cancer_validation_status NULL for {l4_null}/{n} rows → will default to general_population")

    # L5: rob_overall — NULL is non-blocking (defaults to MODERATE)
    if l5_null == 0:
        layer_readiness["L5"] = "READY"
    else:
        layer_readiness["L5"] = "WILL_DEFAULT"
        issues.append(f"rob_overall NULL for {l5_null}/{n} rows → will default to MODERATE")

    # L6: temporal data — non-blocking (defaults to days_since_measurement=0, i.e. no SE penalty)
    if l6_defaulting == 0:
        layer_readiness["L6"] = "READY"
    elif l6_defaulting == n:
        layer_readiness["L6"] = "WILL_DEFAULT"
        issues.append(
            f"temporal data absent for all {n} rows → L6 temporal decay defaults to w=1.0 "
            f"(no SE penalty; 'measured today' assumed)"
        )
    else:
        layer_readiness["L6"] = "WILL_DEFAULT"
        issues.append(
            f"temporal data absent for {l6_defaulting}/{n} rows → "
            f"L6 temporal decay will default to w=1.0 for those rows"
        )

    # L7: pub_year — NULL is non-blocking (freshness decay won't fire)
    if l7_null == 0:
        layer_readiness["L7"] = "READY"
    else:
        layer_readiness["L7"] = "WILL_DEFAULT"
        issues.append(f"pub_year NULL for {l7_null}/{n} rows → freshness decay won't fire")

    return layer_readiness, defaults_fired, blocking, issues


# ============================================================================
# Effect-size consistency check
# ============================================================================

def _check_effect_size_consistency(edge_rows: list) -> list[str]:
    """Check that harmonized_scale is consistent across all rows.

    Mixed scales (e.g., cohen_d + log_odds_ratio) within the same study
    is a BLOCKING issue — meta-analysis cannot mix scales.
    """
    if not edge_rows:
        return []

    scales = set()
    for r in edge_rows:
        scale = getattr(r, "harmonized_scale", None)
        if scale:
            scales.add(scale)

    if len(scales) > 1:
        return [
            f"Mixed harmonized_scale values: {sorted(scales)} — "
            f"cannot aggregate across different effect-size metrics"
        ]

    return []


# ============================================================================
# Missing edge_relation_id check
# ============================================================================

def _check_edge_relation_ids(edge_rows: list) -> list[str]:
    """Check for NULL or 'UNASSIGNED' edge_relation_id — blocking."""
    blocking = []
    null_count = sum(
        1 for r in edge_rows
        if not getattr(r, "edge_relation_id", None)
        or getattr(r, "edge_relation_id", "") == "UNASSIGNED"
    )
    if null_count > 0:
        blocking.append(
            f"edge_relation_id NULL/UNASSIGNED for {null_count}/{len(edge_rows)} rows"
        )
    return blocking


# ============================================================================
# Completeness score
# ============================================================================

def _compute_completeness_score(report: ExtractionReport) -> float:
    """Compute a 0.0–1.0 completeness score.

    Scoring:
    - 50% weight: family coverage (populated / expected)
    - 30% weight: layer readiness (READY layers / total layers)
    - 20% weight: absence of blocking issues

    Blocking issues cap score at 0.5.
    """
    # Family coverage: fraction of expected families that have > 0 rows
    n_expected = len(report.expected_families) or 1
    n_populated = sum(
        1 for f in report.expected_families
        if report.populated_families.get(f, 0) > 0
    )
    family_score = n_populated / n_expected

    # Layer readiness: fraction of layers that are READY
    n_layers = len(report.layer_readiness) or 1
    n_ready = sum(1 for v in report.layer_readiness.values() if v == "READY")
    layer_score = n_ready / n_layers

    # Blocking penalty
    blocking_penalty = 0.0 if not report.blocking_issues else 1.0

    score = (0.5 * family_score) + (0.3 * layer_score) + (0.2 * (1.0 - blocking_penalty))

    # Cap at 0.5 if blocking issues exist
    if report.blocking_issues:
        score = min(score, 0.5)

    return round(score, 2)


# ============================================================================
# Main entry point
# ============================================================================

def check_paper_completeness(
    session: Session,
    study_id: str,
) -> ExtractionReport:
    """Check extraction completeness for a paper.

    Args:
        session: SQLAlchemy session.
        study_id: Study identifier (e.g. "STUDY_CAMPBELL_2017").

    Returns:
        ExtractionReport with completeness analysis.

    Raises:
        ValueError: If study_id not found in study_registry_v1.
    """
    # 1. Look up study design
    study_design = _query_study_design(session, study_id)
    if study_design is None:
        # Study exists but study_design column may be NULL or empty.
        # Check if the study_id exists at all before raising.
        row = session.query(StudyRegistry).filter(
            StudyRegistry.study_id == study_id
        ).first()
        if row is None:
            raise ValueError(f"Study '{study_id}' not found in study_registry_v1")
        # Fallback: look up study_design from edge_evidence_v1
        ev_row = session.query(EdgeEvidence.study_design).filter(
            EdgeEvidence.study_id == study_id,
            EdgeEvidence.study_design.isnot(None),
        ).first()
        study_design = ev_row[0] if ev_row else "other"
        logger.info(
            "study_design not set on study_registry_v1 for %s; "
            "using %s from edge_evidence", study_id, study_design,
        )

    # 2. Determine expected families
    expected = _expected_families_for_design(study_design)

    # 3. Count actual family rows
    counts = _query_family_counts(session, study_id)

    # 4. Identify missing families
    missing = [f for f in expected if counts.get(f, 0) == 0]

    # 5. Get edge evidence rows for layer analysis
    edge_rows = _query_edge_evidence_rows(session, study_id)

    # 6. Analyze layer readiness
    has_temporal = counts.get("F4", 0) > 0
    layer_readiness, defaults_fired, layer_blocking, edge_issues = (
        _analyze_layer_readiness(edge_rows, has_temporal_evidence=has_temporal)
    )

    # 7. Check effect-size consistency
    scale_issues = _check_effect_size_consistency(edge_rows)

    # 8. Check edge_relation_id validity
    eid_issues = _check_edge_relation_ids(edge_rows)

    # 9. Classify issues
    blocking_issues: list[str] = []
    non_blocking_issues: list[str] = []

    # Missing F1 (edge evidence) is always blocking
    if "F1" in missing:
        blocking_issues.append(
            f"No edge evidence (F1): 0 rows — cannot proceed to compilation"
        )

    # Other missing families are non-blocking (layers will default)
    for f in missing:
        if f != "F1":
            label = _FAMILY_LABELS.get(f, f)
            non_blocking_issues.append(
                f"{label} ({f}): 0 rows (expected for {study_design})"
            )

    # Layer blocking issues
    blocking_issues.extend(layer_blocking)

    # Scale consistency issues are blocking
    blocking_issues.extend(scale_issues)

    # Edge relation ID issues are blocking
    blocking_issues.extend(eid_issues)

    # Build report
    report = ExtractionReport(
        study_id=study_id,
        study_design=study_design,
        expected_families=expected,
        populated_families=counts,
        missing_families=missing,
        edge_evidence_issues=edge_issues,
        layer_readiness=layer_readiness,
        completeness_score=0.0,  # computed below
        blocking_issues=blocking_issues,
        non_blocking_issues=non_blocking_issues,
        defaults_fired=defaults_fired,
    )

    # Compute score
    report.completeness_score = _compute_completeness_score(report)

    logger.info(
        "Completeness check for %s: score=%.2f, blocking=%d, non_blocking=%d",
        study_id, report.completeness_score,
        len(report.blocking_issues), len(report.non_blocking_issues),
    )

    return report


# ============================================================================
# Write completeness rows to DB
# ============================================================================

def write_completeness_rows(
    session: Session,
    report: ExtractionReport,
) -> int:
    """Write extraction completeness rows to extraction_completeness_v1.

    One row per expected family, recording PRESENT or ABSENT_NOT_EXTRACTED.
    Additional rows for layer readiness issues.

    Args:
        session: SQLAlchemy session.
        report: ExtractionReport from check_paper_completeness().

    Returns:
        Number of rows written.
    """
    now = datetime.now(timezone.utc).isoformat()
    written = 0

    for family_code in report.expected_families:
        count = report.populated_families.get(family_code, 0)
        label = _FAMILY_LABELS.get(family_code, family_code)

        if count > 0:
            code = "PRESENT"
            detail = f"{count} rows extracted"
            action = None
        else:
            code = "ABSENT_NOT_EXTRACTED"
            detail = f"Expected for {report.study_design} but 0 rows found"
            action = "reparse" if family_code == "F1" else "search"

        comp_id = _deterministic_id(
            "COMP_", report.study_id, family_code,
        )

        row = ExtractionCompleteness(
            completeness_id=comp_id,
            study_id=report.study_id,
            component_id=family_code,
            component_label=label,
            missingness_code=code,
            missingness_detail=detail,
            agent_id="completeness_checker",
            corrective_action=action,
            created_at=now,
        )
        session.add(row)
        written += 1

    # Write layer readiness issues as additional rows
    for layer, status in report.layer_readiness.items():
        if status in ("WILL_DEFAULT", "BLOCKED"):
            n_defaults = report.defaults_fired.get(layer, 0)
            comp_id = _deterministic_id(
                "COMP_", report.study_id, f"LAYER_{layer}",
            )
            row = ExtractionCompleteness(
                completeness_id=comp_id,
                study_id=report.study_id,
                component_id=f"LAYER_{layer}",
                component_label=f"Layer {layer} readiness",
                missingness_code="DEFAULTS_WILL_FIRE" if status == "WILL_DEFAULT" else "BLOCKED",
                missingness_detail=f"{n_defaults} rows will use default values",
                agent_id="completeness_checker",
                corrective_action="manual_review",
                created_at=now,
            )
            session.add(row)
            written += 1

    logger.info("Wrote %d completeness rows for %s", written, report.study_id)
    return written


# ============================================================================
# CLI report formatter
# ============================================================================

def print_report(report: ExtractionReport) -> str:
    """Format ExtractionReport as a human-readable CLI string.

    Args:
        report: ExtractionReport to format.

    Returns:
        Formatted string for console output.
    """
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  ExtractionReport for {report.study_id}")
    lines.append(f"  Design: {report.study_design}")
    lines.append(f"  Completeness: {report.completeness_score:.2f}")
    lines.append("=" * 70)

    # Family status
    lines.append("\n  Family Coverage:")
    for f in report.expected_families:
        count = report.populated_families.get(f, 0)
        label = _FAMILY_LABELS.get(f, f)
        status = "OK" if count > 0 else "MISSING"
        icon = "+" if count > 0 else "-"
        lines.append(f"    [{icon}] {f} ({label}): {count} rows [{status}]")

    # Blocking issues
    if report.blocking_issues:
        lines.append(f"\n  BLOCKING issues ({len(report.blocking_issues)}):")
        for issue in report.blocking_issues:
            lines.append(f"    [!] {issue}")
    else:
        lines.append("\n  BLOCKING issues: 0")

    # Non-blocking issues
    if report.non_blocking_issues:
        lines.append(f"\n  NON-BLOCKING issues ({len(report.non_blocking_issues)}):")
        for issue in report.non_blocking_issues:
            lines.append(f"    [~] {issue}")

    # Defaults that will fire
    lines.append("\n  Defaults that WILL fire:")
    layer_names = {"L1": "design", "L4": "cancer", "L5": "GRADE", "L6": "temporal", "L7": "freshness"}
    for layer, count in sorted(report.defaults_fired.items()):
        name = layer_names.get(layer, layer)
        total = sum(report.populated_families.get(f, 0) for f in ["F1"])
        if total > 0:
            status = "all have it" if count == 0 else f"{count}/{total} rows will default"
            icon = "+" if count == 0 else "~"
        else:
            status = "no data"
            icon = "-"
        lines.append(f"    [{icon}] {layer} ({name}): {status}")

    # Layer readiness
    lines.append("\n  Layer Readiness:")
    for layer, status in sorted(report.layer_readiness.items()):
        icon = "+" if status == "READY" else "!" if status == "BLOCKED" else "~"
        lines.append(f"    [{icon}] {layer}: {status}")

    lines.append("=" * 70)
    return "\n".join(lines)


# ============================================================================
# Helpers
# ============================================================================

def _deterministic_id(prefix: str, *components: str) -> str:
    """Generate deterministic ID: PREFIX + sha256[:12]."""
    raw = "|".join(str(c) for c in components)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}{h}"


# ============================================================================
# Aggregate across studies → ExtractionQualitySummary
# ============================================================================

def aggregate_quality_summary(
    reports: list[ExtractionReport],
) -> "ExtractionQualitySummary":
    """Aggregate per-study ExtractionReports into a session-wide summary.

    Consumed by RecommendationReport.extraction_quality for presentation.

    Args:
        reports: List of ExtractionReports (one per study).

    Returns:
        ExtractionQualitySummary (from output_contracts).
    """
    from crci.shared.models.output_contracts import ExtractionQualitySummary

    if not reports:
        return ExtractionQualitySummary()

    n = len(reports)

    # Mean completeness
    overall = sum(r.completeness_score for r in reports) / n

    # Aggregate defaults_fired across studies
    total_defaults: dict[str, int] = {}
    for r in reports:
        for layer, count in r.defaults_fired.items():
            total_defaults[layer] = total_defaults.get(layer, 0) + count

    # Count studies missing each family
    missing_families_summary: dict[str, int] = {}
    for r in reports:
        for f in r.missing_families:
            missing_families_summary[f] = missing_families_summary.get(f, 0) + 1

    # Count blocking issues
    blocking_count = sum(len(r.blocking_issues) for r in reports)

    # Generate human-readable caveats
    caveats: list[str] = []

    # Temporal data caveat
    l6_defaults = total_defaults.get("L6", 0)
    if l6_defaults > 0:
        n_missing_temporal = missing_families_summary.get("F4", 0)
        if n_missing_temporal > 0:
            caveats.append(
                f"{n_missing_temporal}/{n} studies lack temporal evidence — "
                f"temporal SE penalties could not be applied "
                f"(days_since_measurement defaults to 0, assuming 'measured today')"
            )

    # Layer defaults caveats
    for layer, label in [("L4", "cancer validation"), ("L5", "risk-of-bias/GRADE")]:
        count = total_defaults.get(layer, 0)
        if count > 0:
            caveats.append(
                f"{count} evidence row(s) across {n} studies default on {label} ({layer})"
            )

    # Blocking caveats
    if blocking_count > 0:
        caveats.append(
            f"{blocking_count} blocking issue(s) detected across {n} studies"
        )

    return ExtractionQualitySummary(
        study_count=n,
        overall_completeness=round(overall, 3),
        total_defaults_fired=total_defaults,
        missing_families_summary=missing_families_summary,
        blocking_issue_count=blocking_count,
        quality_caveats=caveats,
    )
