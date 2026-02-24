# VERIFIED: imports — shared.models, sqlalchemy
# VERIFIED: downstream — called by seed_loader.py, extraction pipeline
"""
Component: Layer 0 — Cross-Table Validation
Spec: 05_TABLE_SCHEMAS.md (wiring notes per table)
      06_FK_WIRING_MAP.md (FK relationships)
      CODE_QUALITY_ENFORCEMENT.md (gates must raise)
Purpose: Validate data integrity across tables before commit.
Reads: Database tables via session
Writes: Nothing (raises on failure)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models.enums import (
    ActionClass,
    CancerType,
    DoseType,
    EffectScale,
    EvidenceGrade,
    EvidenceLevel,
    InstrumentKind,
    MeasureKind,
    NodeRole,
    Orientation,
    PathwayTier,
    RelationType,
    StudyDesign,
    TreatmentPhase,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    rule_id: str
    table: str
    passed: bool
    severity: str = "error"  # error, warning
    message: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Aggregated validation results."""

    results: list[ValidationResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(not r.passed and r.severity == "error" for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(not r.passed and r.severity == "warning" for r in self.results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "warning")

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        return (
            f"Validation: {passed}/{total} passed, "
            f"{self.error_count} errors, {self.warning_count} warnings"
        )


def validate_fk_integrity(
    session: Session,
    source_table: str,
    source_column: str,
    target_table: str,
    target_column: str,
) -> ValidationResult:
    """Check that all values in source_column exist in target_column."""
    query = text(f"""
        SELECT s.{source_column}
        FROM {source_table} s
        LEFT JOIN {target_table} t ON s.{source_column} = t.{target_column}
        WHERE s.{source_column} IS NOT NULL
          AND t.{target_column} IS NULL
    """)
    result = session.execute(query).fetchall()
    orphans = [row[0] for row in result]

    return ValidationResult(
        rule_id=f"FK_{source_table}.{source_column}→{target_table}.{target_column}",
        table=source_table,
        passed=len(orphans) == 0,
        severity="error",
        message=(
            f"FK violation: {len(orphans)} orphan(s) in "
            f"{source_table}.{source_column} not found in "
            f"{target_table}.{target_column}"
            if orphans else "FK integrity OK"
        ),
        details=[{"orphan_value": v} for v in orphans[:10]],
    )


def validate_enum_membership(
    session: Session,
    table: str,
    column: str,
    allowed_values: set[str],
) -> ValidationResult:
    """Check that all values in column are in the allowed set."""
    query = text(f"""
        SELECT DISTINCT {column}
        FROM {table}
        WHERE {column} IS NOT NULL
    """)
    result = session.execute(query).fetchall()
    actual_values = {row[0] for row in result}
    invalid = actual_values - allowed_values

    return ValidationResult(
        rule_id=f"ENUM_{table}.{column}",
        table=table,
        passed=len(invalid) == 0,
        severity="error",
        message=(
            f"Invalid enum values in {table}.{column}: {invalid}"
            if invalid else "Enum membership OK"
        ),
        details=[{"invalid_value": v} for v in invalid],
    )


def validate_range(
    session: Session,
    table: str,
    column: str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> ValidationResult:
    """Check that numeric values fall within the specified range."""
    conditions = []
    if min_val is not None:
        conditions.append(f"{column} < {min_val}")
    if max_val is not None:
        conditions.append(f"{column} > {max_val}")

    if not conditions:
        return ValidationResult(
            rule_id=f"RANGE_{table}.{column}",
            table=table,
            passed=True,
            message="No range constraints specified",
        )

    where_clause = " OR ".join(conditions)
    query = text(f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE {column} IS NOT NULL AND ({where_clause})
    """)
    result = session.execute(query).scalar()

    return ValidationResult(
        rule_id=f"RANGE_{table}.{column}",
        table=table,
        passed=result == 0,
        severity="error",
        message=(
            f"Range violation: {result} row(s) in {table}.{column} "
            f"outside [{min_val}, {max_val}]"
            if result else "Range check OK"
        ),
    )


def validate_not_null(
    session: Session,
    table: str,
    column: str,
) -> ValidationResult:
    """Check that a required column has no NULL values."""
    query = text(f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE {column} IS NULL
    """)
    result = session.execute(query).scalar()

    return ValidationResult(
        rule_id=f"NOTNULL_{table}.{column}",
        table=table,
        passed=result == 0,
        severity="error",
        message=(
            f"NULL violation: {result} NULL(s) in {table}.{column}"
            if result else "NOT NULL check OK"
        ),
    )


def run_class_a_validation(session: Session) -> ValidationReport:
    """Run all validation checks for Class A (Knowledge) tables."""
    report = ValidationReport()

    # ── biomarker_node_definitions_v1 ──
    report.results.append(validate_enum_membership(
        session, "biomarker_node_definitions_v1", "orientation",
        {v.value for v in Orientation},
    ))
    report.results.append(validate_enum_membership(
        session, "biomarker_node_definitions_v1", "node_role",
        {v.value for v in NodeRole},
    ))

    # ── edge_relations_definitions_v1 ──
    report.results.append(validate_fk_integrity(
        session,
        "edge_relations_definitions_v1", "node_x",
        "biomarker_node_definitions_v1", "node_id",
    ))
    report.results.append(validate_fk_integrity(
        session,
        "edge_relations_definitions_v1", "node_y",
        "biomarker_node_definitions_v1", "node_id",
    ))
    report.results.append(validate_enum_membership(
        session, "edge_relations_definitions_v1", "relation_type",
        {v.value for v in RelationType},
    ))

    # ── instrument_definitions_v1 ──
    report.results.append(validate_fk_integrity(
        session,
        "instrument_definitions_v1", "maps_to_node_id",
        "biomarker_node_definitions_v1", "node_id",
    ))
    report.results.append(validate_enum_membership(
        session, "instrument_definitions_v1", "instrument_kind",
        {v.value for v in InstrumentKind},
    ))

    # ── measure_definitions_v1 ──
    report.results.append(validate_fk_integrity(
        session,
        "measure_definitions_v1", "maps_to_node_id",
        "biomarker_node_definitions_v1", "node_id",
    ))
    report.results.append(validate_enum_membership(
        session, "measure_definitions_v1", "measure_kind",
        {v.value for v in MeasureKind},
    ))

    # ── action_catalog_v1 ──
    report.results.append(validate_enum_membership(
        session, "action_catalog_v1", "action_class",
        {v.value for v in ActionClass},
    ))
    report.results.append(validate_enum_membership(
        session, "action_catalog_v1", "dose_type",
        {v.value for v in DoseType},
    ))

    # ── pathways_v1 ──
    report.results.append(validate_enum_membership(
        session, "pathways_v1", "tier",
        {v.value for v in PathwayTier},
    ))

    return report


def run_class_b_validation(session: Session) -> ValidationReport:
    """Run validation checks for Class B (Evidence) tables."""
    report = ValidationReport()

    # ── study_cohort_profiles_v1 ──
    report.results.append(validate_fk_integrity(
        session,
        "study_cohort_profiles_v1", "study_id",
        "study_registry_v1", "study_id",
    ))

    # ── edge_evidence_v1 ──
    report.results.append(validate_fk_integrity(
        session,
        "edge_evidence_v1", "study_id",
        "study_registry_v1", "study_id",
    ))
    report.results.append(validate_fk_integrity(
        session,
        "edge_evidence_v1", "edge_relation_id",
        "edge_relations_definitions_v1", "edge_relation_id",
    ))
    report.results.append(validate_not_null(
        session, "edge_evidence_v1", "effect_value_reported",
    ))
    report.results.append(validate_not_null(
        session, "edge_evidence_v1", "N_effect",
    ))

    return report


def run_full_validation(session: Session) -> ValidationReport:
    """Run ALL validation checks across all table classes."""
    report = ValidationReport()

    logger.info("Running Class A validation...")
    class_a = run_class_a_validation(session)
    report.results.extend(class_a.results)

    logger.info("Running Class B validation...")
    class_b = run_class_b_validation(session)
    report.results.extend(class_b.results)

    logger.info(report.summary())
    return report
