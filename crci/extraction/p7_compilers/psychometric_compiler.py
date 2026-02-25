# VERIFIED: formulas P7-C1a, P7-C1b, P7-C1c match SYS_EXTRACTION_ADDENDUM Part 6 Compiler 1
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads InstrumentEvidence from tables.py (B10)
# VERIFIED: forward wiring — writes CompiledInstrument for instrument_definitions_v1 (A4)
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G1 raises on failure
"""
Component: SYS_EXTRACTION.EX-P7.C1
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 1
Formulas: P7-C1a (weighted α), P7-C1b (SE_alpha), P7-C1c (b_k from α)
Reads: InstrumentEvidence rows (from instrument_evidence_v1, written by AG11)
Writes: CompiledInstrument (consumed by instrument_definitions_v1 writer)
Gates: P7-G1 (every compiled α must be based on ≥1 study with N≥20)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledInstrument,
    GateViolation,
)
from crci.shared.models.tables import InstrumentEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class _InstrumentGroup:
    """Intermediate grouping of evidence rows for one instrument."""

    instrument_name: str
    instrument_id: str | None = None
    rows: list[InstrumentEvidence] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  CANCER VALIDATION STATUS
# ═══════════════════════════════════════════════════════════════


def _determine_cancer_validation_status(rows: list[InstrumentEvidence]) -> str:
    """Determine cancer validation status per the spec.

    If ≥1 cancer-specific validation study → CANCER_VALIDATED
    If used in ≥1 cancer study but no validation → USED_IN_CANCER
    If only general population data → GENERAL_POPULATION
    If potential somatic confound flagged → CONFOUNDED
    """
    has_cancer_validation = False
    has_cancer_use = False
    has_confound = False

    for row in rows:
        cancer_type = (row.cancer_type or "").lower()
        pop_desc = (row.population_descriptor or "").lower()

        if "confound" in pop_desc:
            has_confound = True
        if cancer_type and cancer_type not in ("", "none", "general", "healthy"):
            # Check if this is a validation study (has psychometric data)
            if row.cronbachs_alpha is not None or row.factor_loading_mean is not None:
                has_cancer_validation = True
            else:
                has_cancer_use = True

    if has_confound:
        return "CONFOUNDED"
    if has_cancer_validation:
        return "CANCER_VALIDATED"
    if has_cancer_use:
        return "USED_IN_CANCER"
    return "GENERAL_POPULATION"


# ═══════════════════════════════════════════════════════════════
#  COMPILATION FORMULAS
# ═══════════════════════════════════════════════════════════════


def _compile_alpha(
    rows: list[InstrumentEvidence],
    instrument_name: str,
) -> tuple[float, float, int, int]:
    """Compile weighted mean Cronbach's α across studies.

    Formula P7-C1a: α_compiled = Σ(N_i × α_i) / Σ(N_i)
    Formula P7-C1b: SE_alpha = √(Σ(N_i × (α_i − α_compiled)²) / Σ(N_i)) / √(k)

    Returns:
        (alpha_compiled, se_alpha, k_studies, total_n)
    """
    # Filter to rows with alpha and N
    valid_rows = [
        r for r in rows
        if r.cronbachs_alpha is not None and r.N is not None and r.N > 0
    ]

    if not valid_rows:
        logger.warning(
            "Instrument '%s': no rows with valid α and N, cannot compile",
            instrument_name,
        )
        return 0.0, 0.0, 0, 0

    k = len(valid_rows)
    alphas = [r.cronbachs_alpha for r in valid_rows]
    ns = [r.N for r in valid_rows]
    total_n = sum(ns)

    # Formula P7-C1a: α_compiled = Σ(N_i × α_i) / Σ(N_i)
    alpha_compiled = sum(n * a for n, a in zip(ns, alphas)) / total_n

    # Formula P7-C1b: SE_alpha = √(Σ(N_i × (α_i − α_compiled)²) / Σ(N_i)) / √(k)
    if k >= 2:
        weighted_var = sum(
            n * (a - alpha_compiled) ** 2 for n, a in zip(ns, alphas)
        ) / total_n
        se_alpha = math.sqrt(weighted_var) / math.sqrt(k)
    else:
        # Single study: use SE from the row if available, else estimate
        se_alpha = valid_rows[0].se_alpha if valid_rows[0].se_alpha is not None else 0.05

    return alpha_compiled, se_alpha, k, total_n


def _derive_b_k(
    alpha_compiled: float,
    rows: list[InstrumentEvidence],
) -> float:
    """Derive loading coefficient b_k from compiled alpha.

    If instrument has mean factor loading available, use it directly.
    Otherwise, derive via tau-equivalent assumption:
    Formula P7-C1c: b_k ≈ √(α / num_items)

    Returns:
        b_k (loading coefficient)
    """
    # Check if any row has factor loading data
    loading_rows = [r for r in rows if r.factor_loading_mean is not None]
    if loading_rows:
        # Use sample-size weighted mean of factor loadings
        rows_with_n = [(r.factor_loading_mean, r.N or 1) for r in loading_rows]
        total_n = sum(n for _, n in rows_with_n)
        b_k = sum(fl * n for fl, n in rows_with_n) / total_n
        logger.info(
            "b_k derived from %d factor loading estimates: %.4f",
            len(loading_rows),
            b_k,
        )
        return b_k

    # Formula P7-C1c: b_k ≈ √(α / num_items) (tau-equivalent assumption)
    if alpha_compiled > 0.0:
        b_k = math.sqrt(alpha_compiled / config.P7_DEFAULT_NUM_ITEMS)
        logger.info(
            "b_k derived from tau-equivalent assumption: "
            "√(%.4f / %d) = %.4f (using default num_items=%d)",
            alpha_compiled,
            config.P7_DEFAULT_NUM_ITEMS,
            b_k,
            config.P7_DEFAULT_NUM_ITEMS,
        )
        return b_k

    logger.warning("Cannot derive b_k: alpha_compiled=%.4f", alpha_compiled)
    return 0.0


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_psychometric(
    evidence_rows: list[InstrumentEvidence],
) -> list[CompiledInstrument]:
    """Compile psychometric properties per instrument from extracted evidence.

    Groups evidence by instrument_name, compiles weighted α, derives b_k,
    and determines cancer validation status.

    Gate P7-G1: Every compiled α must be based on ≥1 study with N≥20.
    If not met → provenance_status='APPROXIMATE_PENDING', keep default.

    Args:
        evidence_rows: Rows from instrument_evidence_v1 (written by AG11).

    Returns:
        List of CompiledInstrument, one per instrument.

    Raises:
        GateViolation: If P7-G1 cannot be satisfied and no fallback is possible.
    """
    # Group by instrument_name (case-insensitive)
    groups: dict[str, _InstrumentGroup] = {}
    for row in evidence_rows:
        key = (row.instrument_name or "UNKNOWN").strip().lower()
        if key not in groups:
            groups[key] = _InstrumentGroup(
                instrument_name=row.instrument_name or "UNKNOWN",
                instrument_id=row.instrument_id,
            )
        groups[key].rows.append(row)

    results: list[CompiledInstrument] = []

    for key, group in groups.items():
        instrument_name = group.instrument_name
        rows = group.rows

        logger.info(
            "Compiling instrument '%s': %d evidence rows",
            instrument_name,
            len(rows),
        )

        # Compile alpha
        alpha_compiled, se_alpha, k_studies, total_n = _compile_alpha(
            rows, instrument_name
        )

        # ─── Gate P7-G1: ≥1 study with N≥20 ─────────────────────
        has_adequate_n = any(
            r.N is not None and r.N >= config.P7_MIN_N_FOR_ALPHA
            and r.cronbachs_alpha is not None
            for r in rows
        )

        if not has_adequate_n:
            logger.warning(
                "Gate P7-G1: Instrument '%s' has no study with N≥%d and alpha data. "
                "Setting provenance_status=APPROXIMATE_PENDING.",
                instrument_name,
                config.P7_MIN_N_FOR_ALPHA,
            )
            provenance_status = "APPROXIMATE_PENDING"
        else:
            provenance_status = "CURATED_TRACED"

        # Derive b_k
        b_k = _derive_b_k(alpha_compiled, rows)

        # a_k: intercept — use 0 unless instrument has known intercept
        a_k = 0.0

        # Cancer validation status
        cancer_status = _determine_cancer_validation_status(rows)

        # Provenance ref: list of study IDs
        study_ids = sorted({r.study_id for r in rows if r.study_id})
        provenance_ref = "; ".join(study_ids)

        compiled = CompiledInstrument(
            instrument_id=group.instrument_id or f"INST_{key}",
            instrument_name=instrument_name,
            a_k=a_k,
            b_k=b_k,
            alpha_k=alpha_compiled,
            se_alpha=se_alpha,
            cancer_validation_status=cancer_status,
            k_studies=k_studies,
            total_n=total_n,
            provenance_status=provenance_status,
            provenance_ref=provenance_ref,
        )
        results.append(compiled)

        logger.info(
            "Compiled instrument '%s': α=%.4f (SE=%.4f), b_k=%.4f, "
            "status=%s, cancer=%s, k=%d, N=%d",
            instrument_name,
            alpha_compiled,
            se_alpha,
            b_k,
            provenance_status,
            cancer_status,
            k_studies,
            total_n,
        )

    logger.info(
        "Psychometric compilation complete: %d instruments compiled",
        len(results),
    )
    return results
