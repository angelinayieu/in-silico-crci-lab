# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads B10-B14 intermediate evidence tables
# VERIFIED: forward wiring — produces compiled parameters for Class A tables
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates delegated to individual compilers (P7-G1 through P7-G6)
"""
Component: SYS_EXTRACTION.EX-P7.RUNNER
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6 + Part 8
Purpose: Orchestrate all 6 P7 compilers after P6 validation.
         Each compiler reads from its intermediate evidence table and
         produces compiled parameters.
Reads: B10-B14 intermediate evidence tables, pipeline context
Writes: Compiled parameter results in context (consumed by DB writers)
Gates: Delegates to individual compilers (P7-G1 through P7-G6)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crci.shared.models.intermediate_states import GateViolation
from crci.shared.models.tables import (
    DoseEvidence,
    ExtractionRun,
    InstrumentEvidence,
    PopulationNorms,
    SubgroupEvidence,
    TemporalEvidence,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  COMPILATION REPORT
# ═══════════════════════════════════════════════════════════════


@dataclass
class CompilerReport:
    """Report for a single compiler's execution."""

    compiler_name: str
    rows_input: int = 0
    rows_compiled: int = 0
    gates_passed: int = 0
    gates_failed: int = 0
    provenance_curated: int = 0
    provenance_approximate: int = 0
    error_message: str | None = None


@dataclass
class P7CompilationReport:
    """Aggregated report across all 6 compilers."""

    compiler_reports: list[CompilerReport] = field(default_factory=list)
    total_rows_compiled: int = 0
    total_gates_passed: int = 0
    total_gates_failed: int = 0


# ═══════════════════════════════════════════════════════════════
#  DB QUERY HELPERS
# ═══════════════════════════════════════════════════════════════


def _fetch_instrument_evidence(
    session: Session,
    extraction_run_id: str | None = None,
) -> list[InstrumentEvidence]:
    """Fetch instrument evidence rows for compilation."""
    stmt = select(InstrumentEvidence)
    if extraction_run_id:
        stmt = stmt.where(InstrumentEvidence.extraction_run_id == extraction_run_id)
    return list(session.execute(stmt).scalars().all())


def _fetch_population_norms(
    session: Session,
    extraction_run_id: str | None = None,
) -> list[PopulationNorms]:
    """Fetch population norms rows for compilation."""
    stmt = select(PopulationNorms)
    if extraction_run_id:
        stmt = stmt.where(PopulationNorms.extraction_run_id == extraction_run_id)
    return list(session.execute(stmt).scalars().all())


def _fetch_temporal_evidence(
    session: Session,
    extraction_run_id: str | None = None,
) -> list[TemporalEvidence]:
    """Fetch temporal evidence rows for compilation."""
    stmt = select(TemporalEvidence)
    if extraction_run_id:
        stmt = stmt.where(TemporalEvidence.extraction_run_id == extraction_run_id)
    return list(session.execute(stmt).scalars().all())


def _fetch_dose_evidence(
    session: Session,
    extraction_run_id: str | None = None,
) -> list[DoseEvidence]:
    """Fetch dose evidence rows for compilation."""
    stmt = select(DoseEvidence)
    if extraction_run_id:
        stmt = stmt.where(DoseEvidence.extraction_run_id == extraction_run_id)
    return list(session.execute(stmt).scalars().all())


def _fetch_subgroup_evidence(
    session: Session,
    extraction_run_id: str | None = None,
) -> list[SubgroupEvidence]:
    """Fetch subgroup evidence rows for compilation."""
    stmt = select(SubgroupEvidence)
    if extraction_run_id:
        stmt = stmt.where(SubgroupEvidence.extraction_run_id == extraction_run_id)
    return list(session.execute(stmt).scalars().all())


# ═══════════════════════════════════════════════════════════════
#  INDIVIDUAL COMPILER RUNNERS
# ═══════════════════════════════════════════════════════════════


def _run_psychometric_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 1: Psychometric → instruments."""
    from crci.extraction.p7_compilers.psychometric_compiler import compile_psychometric

    report = CompilerReport(compiler_name="psychometric")
    rows = _fetch_instrument_evidence(session, extraction_run_id)
    report.rows_input = len(rows)

    if not rows:
        logger.info("Psychometric compiler: no instrument evidence rows, skipping")
        return report

    try:
        results = compile_psychometric(rows)
        report.rows_compiled = len(results)
        report.gates_passed = len(results)
        report.provenance_curated = sum(
            1 for r in results if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in results if r.provenance_status == "APPROXIMATE_PENDING"
        )
        context["compiled_instruments"] = results
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Psychometric compiler gate failure: %s", exc)

    return report


def _run_prior_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 2: Population Norms → priors."""
    from crci.extraction.p7_compilers.prior_compiler import compile_priors

    report = CompilerReport(compiler_name="prior")
    rows = _fetch_population_norms(session, extraction_run_id)
    report.rows_input = len(rows)

    if not rows:
        logger.info("Prior compiler: no population norms rows, skipping")
        return report

    try:
        results = compile_priors(rows)
        report.rows_compiled = len(results)
        report.gates_passed = len(results)
        report.provenance_curated = sum(
            1 for r in results if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in results if r.provenance_status == "APPROXIMATE_PENDING"
        )
        context["compiled_priors"] = results
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Prior compiler gate failure: %s", exc)

    return report


def _run_temporal_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 3: Temporal → kernels + recovery."""
    from crci.extraction.p7_compilers.temporal_compiler import compile_temporal

    report = CompilerReport(compiler_name="temporal")
    rows = _fetch_temporal_evidence(session, extraction_run_id)
    report.rows_input = len(rows)

    if not rows:
        logger.info("Temporal compiler: no temporal evidence rows, skipping")
        return report

    try:
        kernels, recoveries = compile_temporal(rows)
        report.rows_compiled = len(kernels) + len(recoveries)
        report.gates_passed = len(kernels) + len(recoveries)
        report.provenance_curated = sum(
            1 for r in kernels if r.provenance_status == "CURATED_TRACED"
        ) + sum(
            1 for r in recoveries if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in kernels if r.provenance_status == "APPROXIMATE_PENDING"
        ) + sum(
            1 for r in recoveries if r.provenance_status == "APPROXIMATE_PENDING"
        )
        context["compiled_kernels"] = kernels
        context["compiled_recoveries"] = recoveries
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Temporal compiler gate failure: %s", exc)

    return report


def _run_dose_response_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 4: Dose-Response → dose params."""
    from crci.extraction.p7_compilers.dose_response_compiler import compile_dose_response

    report = CompilerReport(compiler_name="dose_response")
    rows = _fetch_dose_evidence(session, extraction_run_id)
    report.rows_input = len(rows)

    if not rows:
        logger.info("Dose-response compiler: no dose evidence rows, skipping")
        return report

    try:
        results = compile_dose_response(rows)
        report.rows_compiled = len(results)
        report.gates_passed = len(results)
        report.provenance_curated = sum(
            1 for r in results if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in results if r.provenance_status == "APPROXIMATE_PENDING"
        )
        context["compiled_dose_response"] = results
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Dose-response compiler gate failure: %s", exc)

    return report


def _run_modifier_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 5: Subgroup → modifiers."""
    from crci.extraction.p7_compilers.modifier_compiler import compile_modifiers

    report = CompilerReport(compiler_name="modifier")
    rows = _fetch_subgroup_evidence(session, extraction_run_id)
    report.rows_input = len(rows)

    if not rows:
        logger.info("Modifier compiler: no subgroup evidence rows, skipping")
        return report

    try:
        results = compile_modifiers(rows)
        report.rows_compiled = len(results)
        report.gates_passed = len(results)
        report.provenance_curated = sum(
            1 for r in results if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in results if r.provenance_status == "APPROXIMATE_PENDING"
        )
        context["compiled_modifiers"] = results
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Modifier compiler gate failure: %s", exc)

    return report


def _run_synergy_compiler(
    session: Session,
    extraction_run_id: str | None,
    context: dict[str, Any],
) -> CompilerReport:
    """Run Compiler 6: Synergy → synergy registry.

    Note: This compiler expects SynergyTrialData input, which is not
    directly stored in a B-class table. In v1, synergy data must be
    constructed from factorial trial edge evidence.
    """
    report = CompilerReport(compiler_name="synergy")

    # Synergy data requires factorial trial design — very rare.
    # In v1, this compiler typically has 0 input rows.
    synergy_data = context.get("synergy_trial_data", [])
    report.rows_input = len(synergy_data)

    if not synergy_data:
        logger.info(
            "Synergy compiler: no factorial trial data available, skipping "
            "(expected — factorial designs rare in cancer cognition)"
        )
        return report

    from crci.extraction.p7_compilers.synergy_compiler import compile_synergy

    try:
        results = compile_synergy(synergy_data)
        report.rows_compiled = len(results)
        report.gates_passed = len(results)
        report.provenance_curated = sum(
            1 for r in results if r.provenance_status == "CURATED_TRACED"
        )
        report.provenance_approximate = sum(
            1 for r in results if r.provenance_status == "SENSITIVITY_REQUIRED"
        )
        context["compiled_synergy"] = results
    except GateViolation as exc:
        report.gates_failed = 1
        report.error_message = str(exc)
        logger.error("Synergy compiler gate failure: %s", exc)

    return report


# ═══════════════════════════════════════════════════════════════
#  MAIN RUNNER (called by pipeline.py)
# ═══════════════════════════════════════════════════════════════


def run_p7_compilation(
    session: Session,
    run: ExtractionRun,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run all 6 P7 compilers in sequence.

    Called by pipeline.py after P6 validation passes.
    Each compiler reads from its intermediate evidence table (B10-B14)
    and produces compiled parameters stored in the context.

    Args:
        session: Active database session.
        run: The current ExtractionRun instance.
        context: Accumulated pipeline context from prior chains.

    Returns:
        Updated context dict with compiled parameters and report.
    """
    extraction_run_id = context.get("extraction_run_id")

    logger.info(
        "Starting P7 compilation for run %s",
        run.extraction_run_id,
    )

    compilation_report = P7CompilationReport()

    # Run all 6 compilers in order
    compilers = [
        _run_psychometric_compiler,
        _run_prior_compiler,
        _run_temporal_compiler,
        _run_dose_response_compiler,
        _run_modifier_compiler,
        _run_synergy_compiler,
    ]

    for compiler_fn in compilers:
        report = compiler_fn(session, extraction_run_id, context)
        compilation_report.compiler_reports.append(report)
        compilation_report.total_rows_compiled += report.rows_compiled
        compilation_report.total_gates_passed += report.gates_passed
        compilation_report.total_gates_failed += report.gates_failed

    # Store report in context
    context["p7_compilation_report"] = compilation_report

    # Log summary
    logger.info(
        "P7 compilation complete: %d total rows compiled, "
        "%d gates passed, %d gates failed",
        compilation_report.total_rows_compiled,
        compilation_report.total_gates_passed,
        compilation_report.total_gates_failed,
    )
    for cr in compilation_report.compiler_reports:
        if cr.rows_input > 0 or cr.rows_compiled > 0:
            logger.info(
                "  %s: %d input → %d compiled "
                "(curated=%d, approximate=%d%s)",
                cr.compiler_name,
                cr.rows_input,
                cr.rows_compiled,
                cr.provenance_curated,
                cr.provenance_approximate,
                f", ERROR: {cr.error_message}" if cr.error_message else "",
            )

    return context
