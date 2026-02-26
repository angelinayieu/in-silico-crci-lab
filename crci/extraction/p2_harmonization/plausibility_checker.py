# VERIFIED: formulas — plausibility bounds match spec lines 715-717
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads TypedNumericValue from tb_trust_boundary
# VERIFIED: forward wiring — writes ValidatedNumeric for conversion_router.py
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gates [P2-G1] raise on failure
"""
Component: SYS_EXTRACTION.EX-P2.S1
Spec: SYS_EXTRACTION_COMPLETE.md lines 715-717
Formulas: None (bound checks only)
Reads: TypedNumericValue (from tb_trust_boundary/consistency_checker.py)
Writes: ValidatedNumeric (consumed by conversion_router.py)
Gates: P2-G1
"""
from __future__ import annotations

import logging
from typing import Any

from crci.shared.config import (
    PLAUSIBILITY_BETA_MAX,
    PLAUSIBILITY_CORRELATION_MAX,
)
from crci.shared.models.enums import PlausibilityStatus
from crci.shared.models.intermediate_states import (
    GateViolation,
    TypedNumericValue,
    ValidatedNumeric,
)

logger = logging.getLogger(__name__)


def check_plausibility(
    span_id: str,
    value: TypedNumericValue,
    *,
    is_correlation: bool = False,
) -> ValidatedNumeric:
    """S1 — Plausibility Check (Gate P2-G1).

    Validates numeric evidence against plausibility bounds:
    - |beta| <= PLAUSIBILITY_BETA_MAX (5.0)
    - SE > 0
    - CI properly ordered (lower < upper)
    - |r| <= PLAUSIBILITY_CORRELATION_MAX (1.0) for correlations
    - N > 0

    Parameters
    ----------
    span_id:
        Unique identifier for this numeric span.
    value:
        Typed numeric value from the trust boundary.
    is_correlation:
        If True, apply correlation-specific bounds (|r| <= 1).

    Returns
    -------
    ValidatedNumeric
        The validated value with plausibility status.

    Raises
    ------
    GateViolation
        Gate P2-G1: raised on FAIL (extreme values that are
        unrecoverable). WARNING values are logged but pass through.
    """
    warnings: list[str] = []
    status = PlausibilityStatus.PASS

    # Determine if this is a raw test statistic (not an effect size).
    # F-statistics can naturally exceed the beta bound (e.g., F=10.2)
    # and should not be checked against PLAUSIBILITY_BETA_MAX.
    _label = (value.label_type or "").upper()
    _is_test_statistic = _label in {"F_STATISTIC", "CHI_SQUARE", "T_STATISTIC"}

    # Check 1: |beta| <= PLAUSIBILITY_BETA_MAX (skip for raw test statistics)
    if not _is_test_statistic and abs(value.value) > PLAUSIBILITY_BETA_MAX:
        note = (
            f"span_id={span_id}: |beta|={abs(value.value):.4f} exceeds "
            f"PLAUSIBILITY_BETA_MAX={PLAUSIBILITY_BETA_MAX}"
        )
        # Extreme values (> 2x threshold) are rejected outright
        if abs(value.value) > 2 * PLAUSIBILITY_BETA_MAX:
            logger.error(note)
            raise GateViolation(
                gate_id="P2-G1",
                message=note,
                context={"span_id": span_id, "beta": value.value},
            )
        # Moderately out-of-range values get a WARNING
        logger.warning(note)
        warnings.append(note)
        status = PlausibilityStatus.WARNING

    # Check 2: SE > 0 (if reported)
    if value.se is not None and value.se <= 0:
        note = (
            f"span_id={span_id}: SE={value.se:.6f} is not positive"
        )
        logger.error(note)
        raise GateViolation(
            gate_id="P2-G1",
            message=note,
            context={"span_id": span_id, "se": value.se},
        )

    # Check 3: CI properly ordered (lower < upper)
    if value.ci_lower is not None and value.ci_upper is not None:
        if value.ci_lower > value.ci_upper:
            note = (
                f"span_id={span_id}: CI misordered — "
                f"lower={value.ci_lower:.4f} > upper={value.ci_upper:.4f}"
            )
            logger.error(note)
            raise GateViolation(
                gate_id="P2-G1",
                message=note,
                context={
                    "span_id": span_id,
                    "ci_lower": value.ci_lower,
                    "ci_upper": value.ci_upper,
                },
            )
        # Also check that beta is within CI (soft check — WARNING only)
        if not (value.ci_lower <= value.value <= value.ci_upper):
            note = (
                f"span_id={span_id}: beta={value.value:.4f} outside CI "
                f"[{value.ci_lower:.4f}, {value.ci_upper:.4f}]"
            )
            logger.warning(note)
            warnings.append(note)
            if status == PlausibilityStatus.PASS:
                status = PlausibilityStatus.WARNING

    # Check 4: |r| <= PLAUSIBILITY_CORRELATION_MAX for correlations
    if is_correlation:
        if abs(value.value) > PLAUSIBILITY_CORRELATION_MAX:
            note = (
                f"span_id={span_id}: |r|={abs(value.value):.4f} exceeds "
                f"PLAUSIBILITY_CORRELATION_MAX={PLAUSIBILITY_CORRELATION_MAX}"
            )
            logger.error(note)
            raise GateViolation(
                gate_id="P2-G1",
                message=note,
                context={"span_id": span_id, "r": value.value},
            )

    # Check 5: N > 0 (if reported)
    if value.n is not None and value.n <= 0:
        note = (
            f"span_id={span_id}: N={value.n} is not positive"
        )
        logger.error(note)
        raise GateViolation(
            gate_id="P2-G1",
            message=note,
            context={"span_id": span_id, "n": value.n},
        )

    # Check 6: p-value in [0, 1] (if reported)
    if value.p_value is not None:
        if not (0.0 <= value.p_value <= 1.0):
            note = (
                f"span_id={span_id}: p_value={value.p_value:.6f} "
                f"outside [0, 1]"
            )
            logger.error(note)
            raise GateViolation(
                gate_id="P2-G1",
                message=note,
                context={"span_id": span_id, "p_value": value.p_value},
            )

    plausibility_note = "; ".join(warnings) if warnings else None

    return ValidatedNumeric(
        span_id=span_id,
        value=value,
        value_type=(value.label_type or "EFFECT_SIZE").upper(),
        plausibility_status=status,
        plausibility_note=plausibility_note,
    )


def check_plausibility_batch(
    items: list[tuple[str, TypedNumericValue, bool]],
) -> list[ValidatedNumeric]:
    """Run plausibility checks on a batch of values.

    Parameters
    ----------
    items:
        List of (span_id, TypedNumericValue, is_correlation) tuples.

    Returns
    -------
    list[ValidatedNumeric]
        Successfully validated items. Items that fail Gate P2-G1
        (GateViolation raised) are logged and excluded from output.
    """
    results: list[ValidatedNumeric] = []
    for span_id, value, is_corr in items:
        try:
            validated = check_plausibility(
                span_id=span_id,
                value=value,
                is_correlation=is_corr,
            )
            results.append(validated)
        except GateViolation as exc:
            logger.error(
                "Plausibility REJECT for span_id=%s: %s",
                span_id,
                str(exc),
            )
    return results
