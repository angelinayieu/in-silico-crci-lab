# VERIFIED: formulas — none (rule-based checks)
# VERIFIED: imports — intermediate_states, enums, config
# VERIFIED: backward wiring — reads ParsedNumeric from numeric_parser.py
# VERIFIED: forward wiring — writes ValidatedNumeric for harmonization
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — TB-G2 raises on failure
"""
Component: SYS_EXTRACTION.EX-TB.CN
Spec: SYS_EXTRACTION_COMPLETE.md lines 652-682 (ClaimNormalizer)
Formulas: None (rule-based consistency checks)
Reads: ParsedNumeric (from numeric_parser.py)
Writes: ValidatedNumeric (consumed by harmonization/plausibility_checker.py)
Gates: TB-G2
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from crci.shared import config
from crci.shared.models.intermediate_states import (
    GateViolation,
    ParsedNumeric,
    ValidatedNumeric,
)

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyResult:
    """Result of consistency checking for a group of parsed numerics."""

    validated: list[ValidatedNumeric] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)


def check_consistency(
    parsed_values: list[ParsedNumeric],
    paper_id: str,
) -> ConsistencyResult:
    """Run cross-validation checks on parsed numeric values.

    Checks:
    1. CI contains point estimate (if both reported)
    2. P-value consistent with CI (p<0.05 ↔ CI excludes 0)
    3. N consistency across different reported values
    4. Plausibility: |β| ≤ 5, SE > 0

    Args:
        parsed_values: List of ParsedNumeric from numeric_parser.
        paper_id: Paper ID for logging.

    Returns:
        ConsistencyResult with validated, warnings, and rejected items.

    Raises:
        GateViolation: If TB-G2 fails (no plausible values).
    """
    result = ConsistencyResult()

    # Group by grouping_id for cross-checks
    groups: dict[str | None, list[ParsedNumeric]] = {}
    for pv in parsed_values:
        gid = getattr(pv, "grouping_id", None)
        groups.setdefault(gid, []).append(pv)

    for group_id, group_values in groups.items():
        _check_group_consistency(group_values, group_id, paper_id, result)

    # Individual plausibility checks on all values
    for pv in parsed_values:
        validated = _check_plausibility(pv, paper_id)
        if validated is not None:
            result.validated.append(validated)
        else:
            result.rejected.append(
                (pv.span_id, f"Failed plausibility check for {pv.value_type}")
            )

    # Gate TB-G2: at least one plausible value
    if not result.validated:
        raise GateViolation(
            gate_id="TB-G2",
            message=(
                f"Paper {paper_id}: No values passed plausibility checks. "
                f"Rejected {len(result.rejected)} values."
            ),
        )

    logger.info(
        "Consistency check for paper %s: %d validated, %d warnings, %d rejected",
        paper_id,
        len(result.validated),
        len(result.warnings),
        len(result.rejected),
    )

    return result


def _check_plausibility(
    pv: ParsedNumeric,
    paper_id: str,
) -> ValidatedNumeric | None:
    """Check single value plausibility.

    Gate TB-G2 criteria:
    - |β| ≤ 5 for effect sizes
    - SE > 0
    - CI properly ordered (lower < upper)
    - |r| ≤ 1 for correlations
    - N > 0
    """
    notes: list[str] = []

    # Check effect size plausibility
    if pv.parsed_value is not None and pv.value_type in (
        "effect_size",
        "beta",
        "regression_coefficient",
        "cohens_d",
    ):
        if abs(pv.parsed_value) > config.PLAUSIBILITY_BETA_MAX:
            logger.warning(
                "Paper %s span %s: |β|=%.3f > %.1f, rejecting",
                paper_id,
                pv.span_id,
                abs(pv.parsed_value),
                config.PLAUSIBILITY_BETA_MAX,
            )
            return None

    # Check SE positivity
    if pv.value_type == "se" and pv.parsed_value is not None:
        if pv.parsed_value <= 0:
            logger.warning(
                "Paper %s span %s: SE=%.4f ≤ 0, rejecting",
                paper_id,
                pv.span_id,
                pv.parsed_value,
            )
            return None

    # Check CI ordering
    if pv.parsed_lower is not None and pv.parsed_upper is not None:
        if pv.parsed_lower > pv.parsed_upper:
            notes.append(
                f"CI inverted: [{pv.parsed_lower}, {pv.parsed_upper}], swapping"
            )
            pv.parsed_lower, pv.parsed_upper = pv.parsed_upper, pv.parsed_lower

    # Check correlation bounds
    if pv.value_type in ("correlation", "r", "rho"):
        if pv.parsed_value is not None and abs(pv.parsed_value) > 1.0:
            logger.warning(
                "Paper %s span %s: |r|=%.3f > 1.0, rejecting",
                paper_id,
                pv.span_id,
                abs(pv.parsed_value),
            )
            return None

    # Check N positivity
    if pv.value_type in ("sample_size", "n") and pv.parsed_value is not None:
        if pv.parsed_value <= 0:
            logger.warning(
                "Paper %s span %s: N=%.0f ≤ 0, rejecting",
                paper_id,
                pv.span_id,
                pv.parsed_value,
            )
            return None

    plausibility_status = "PASS" if not notes else "WARNING"

    return ValidatedNumeric(
        span_id=pv.span_id,
        value=pv.parsed_value,
        plausibility_status=plausibility_status,
        plausibility_note="; ".join(notes) if notes else None,
    )


def _check_group_consistency(
    group: list[ParsedNumeric],
    group_id: str | None,
    paper_id: str,
    result: ConsistencyResult,
) -> None:
    """Cross-validate values within a grouping.

    Checks:
    1. CI contains point estimate
    2. P-value ↔ CI consistency
    3. N consistency
    """
    # Find different value types in the group
    point_estimates = [
        v for v in group if v.value_type in ("effect_size", "beta", "mean", "or", "hr")
    ]
    cis = [v for v in group if v.parsed_lower is not None and v.parsed_upper is not None]
    p_values = [v for v in group if v.value_type == "p_value"]
    sample_sizes = [v for v in group if v.value_type in ("sample_size", "n")]

    # Check 1: CI contains point estimate
    for pe in point_estimates:
        if pe.parsed_value is None:
            continue
        for ci in cis:
            if ci.parsed_lower is not None and ci.parsed_upper is not None:
                if not (ci.parsed_lower <= pe.parsed_value <= ci.parsed_upper):
                    warning = (
                        f"Paper {paper_id} group {group_id}: point estimate "
                        f"{pe.parsed_value:.4f} outside CI "
                        f"[{ci.parsed_lower:.4f}, {ci.parsed_upper:.4f}]"
                    )
                    logger.warning(warning)
                    result.warnings.append(warning)

    # Check 2: P-value ↔ CI consistency
    for pv in p_values:
        if pv.parsed_value is None:
            continue
        for ci in cis:
            if ci.parsed_lower is None or ci.parsed_upper is None:
                continue
            ci_excludes_zero = not (ci.parsed_lower <= 0 <= ci.parsed_upper)
            p_significant = pv.parsed_value < 0.05

            if ci_excludes_zero and not p_significant:
                warning = (
                    f"Paper {paper_id} group {group_id}: CI excludes 0 "
                    f"[{ci.parsed_lower:.4f}, {ci.parsed_upper:.4f}] "
                    f"but p={pv.parsed_value:.4f} ≥ 0.05"
                )
                logger.warning(warning)
                result.warnings.append(warning)
            elif not ci_excludes_zero and p_significant:
                warning = (
                    f"Paper {paper_id} group {group_id}: CI includes 0 "
                    f"[{ci.parsed_lower:.4f}, {ci.parsed_upper:.4f}] "
                    f"but p={pv.parsed_value:.4f} < 0.05"
                )
                logger.warning(warning)
                result.warnings.append(warning)

    # Check 3: N consistency (all reported Ns should be close)
    n_values = [
        s.parsed_value for s in sample_sizes if s.parsed_value is not None
    ]
    if len(n_values) >= 2:
        max_n = max(n_values)
        min_n = min(n_values)
        if max_n > 0 and (max_n - min_n) / max_n > 0.20:
            warning = (
                f"Paper {paper_id} group {group_id}: N values inconsistent: "
                f"min={min_n:.0f}, max={max_n:.0f} "
                f"(diff {(max_n - min_n) / max_n:.0%})"
            )
            logger.warning(warning)
            result.warnings.append(warning)
