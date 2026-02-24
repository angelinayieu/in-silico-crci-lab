# VERIFIED: formulas — validation rules G1-G18 match spec SYS_EX lines 1787-1860
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads CompiledEdge, SufficiencyReport, BiasAssessment
# VERIFIED: forward wiring — writes ValidationResult for deploy_gate.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — no gate (deploy_gate enforces P6-G1)
"""
Component: SYS_EXTRACTION.EX-P6.VR
Spec: SYS_EXTRACTION_COMPLETE.md lines 1787-1860
Formulas: None (validation rule checks)
Reads: CompiledEdge (from p4_aggregation),
       SufficiencyReport (from sufficiency_reporter.py),
       BiasAssessment (from publication_bias.py)
Writes: ValidationResult (consumed by deploy_gate.py)
Gates: None (P6-G1 enforced in deploy_gate.py)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crci.shared.models.enums import (
    BiasRisk,
    SufficiencyRecommendation,
)
from crci.shared.models.intermediate_states import (
    CompiledEdge,
    SufficiencyReport,
)

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """Result of a single validation rule execution."""

    rule_id: str
    rule_name: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Aggregated result of all validation rules."""

    rule_results: list[RuleResult] = field(default_factory=list)
    n_pass: int = 0
    n_warn: int = 0
    n_fail: int = 0
    total_rules: int = 0


# ═══════════════════════════════════════════════════════════════
#  Validation Rules G1 through G18
# ═══════════════════════════════════════════════════════════════


def _rule_g1_minimum_edges(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G1: At least 1 compiled edge must exist."""
    if len(compiled_edges) == 0:
        return RuleResult(
            rule_id="G1",
            rule_name="minimum_edges",
            status="FAIL",
            message="No compiled edges found. Pipeline produced no usable evidence.",
            details={"n_edges": 0},
        )
    return RuleResult(
        rule_id="G1",
        rule_name="minimum_edges",
        status="PASS",
        message=f"{len(compiled_edges)} compiled edges present.",
        details={"n_edges": len(compiled_edges)},
    )


def _rule_g2_all_edges_have_se(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G2: Every compiled edge must have SE > 0."""
    bad_edges = [
        e.edge_relation_id
        for e in compiled_edges
        if e.beta_se <= 0
    ]
    if bad_edges:
        return RuleResult(
            rule_id="G2",
            rule_name="positive_se",
            status="FAIL",
            message=f"{len(bad_edges)} edge(s) have SE <= 0: {bad_edges[:5]}",
            details={"bad_edges": bad_edges},
        )
    return RuleResult(
        rule_id="G2",
        rule_name="positive_se",
        status="PASS",
        message="All edges have positive SE.",
    )


def _rule_g3_all_edges_have_k(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G3: Every compiled edge must have k >= 1."""
    bad_edges = [
        e.edge_relation_id
        for e in compiled_edges
        if e.k < 1
    ]
    if bad_edges:
        return RuleResult(
            rule_id="G3",
            rule_name="positive_k",
            status="WARN",
            message=f"{len(bad_edges)} edge(s) have k < 1: {bad_edges[:5]}",
            details={"bad_edges": bad_edges},
        )
    return RuleResult(
        rule_id="G3",
        rule_name="positive_k",
        status="PASS",
        message="All edges have k >= 1.",
    )


def _rule_g4_plausible_betas(
    compiled_edges: list[CompiledEdge],
    beta_max: float = 5.0,
) -> RuleResult:
    """G4: All |beta| values within plausible range."""
    extreme_edges = [
        (e.edge_relation_id, e.beta_mean)
        for e in compiled_edges
        if abs(e.beta_mean) > beta_max
    ]
    if extreme_edges:
        return RuleResult(
            rule_id="G4",
            rule_name="plausible_betas",
            status="WARN",
            message=f"{len(extreme_edges)} edge(s) have |beta| > {beta_max}.",
            details={"extreme_edges": extreme_edges[:5]},
        )
    return RuleResult(
        rule_id="G4",
        rule_name="plausible_betas",
        status="PASS",
        message=f"All edges have |beta| <= {beta_max}.",
    )


def _rule_g5_se_not_excessive(
    compiled_edges: list[CompiledEdge],
    se_max: float = 10.0,
) -> RuleResult:
    """G5: SE values not excessively large."""
    bad_edges = [
        (e.edge_relation_id, e.beta_se)
        for e in compiled_edges
        if e.beta_se > se_max
    ]
    if bad_edges:
        return RuleResult(
            rule_id="G5",
            rule_name="se_not_excessive",
            status="WARN",
            message=f"{len(bad_edges)} edge(s) have SE > {se_max}.",
            details={"bad_edges": bad_edges[:5]},
        )
    return RuleResult(
        rule_id="G5",
        rule_name="se_not_excessive",
        status="PASS",
        message=f"All edges have SE <= {se_max}.",
    )


def _rule_g6_consistent_effect_scales(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G6: Effect scales should be consistent (all same or documented mix)."""
    scales = {e.effect_scale for e in compiled_edges}
    if len(scales) > 2:
        return RuleResult(
            rule_id="G6",
            rule_name="consistent_scales",
            status="WARN",
            message=f"Multiple effect scales detected: {[s.value for s in scales]}",
            details={"scales": [s.value for s in scales]},
        )
    return RuleResult(
        rule_id="G6",
        rule_name="consistent_scales",
        status="PASS",
        message=f"Effect scales: {[s.value for s in scales]}",
    )


def _rule_g7_no_duplicate_edges(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G7: No duplicate edge_relation_ids."""
    edge_ids = [e.edge_relation_id for e in compiled_edges]
    duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
    unique_duplicates = list(set(duplicates))
    if unique_duplicates:
        return RuleResult(
            rule_id="G7",
            rule_name="no_duplicate_edges",
            status="FAIL",
            message=f"Duplicate edge_relation_ids: {unique_duplicates[:5]}",
            details={"duplicates": unique_duplicates},
        )
    return RuleResult(
        rule_id="G7",
        rule_name="no_duplicate_edges",
        status="PASS",
        message="No duplicate edge_relation_ids.",
    )


def _rule_g8_sufficiency_not_insufficient(
    sufficiency_report: SufficiencyReport | None,
) -> RuleResult:
    """G8: Overall sufficiency should not be INSUFFICIENT."""
    if sufficiency_report is None:
        return RuleResult(
            rule_id="G8",
            rule_name="sufficiency_check",
            status="WARN",
            message="No sufficiency report available.",
        )
    if sufficiency_report.recommendation == SufficiencyRecommendation.INSUFFICIENT:
        return RuleResult(
            rule_id="G8",
            rule_name="sufficiency_check",
            status="FAIL",
            message=(
                f"Evidence base is INSUFFICIENT: "
                f"{sufficiency_report.edges_insufficient} insufficient edges, "
                f"{len(sufficiency_report.gaps)} gaps."
            ),
            details={
                "recommendation": sufficiency_report.recommendation.value,
                "gaps": sufficiency_report.gaps[:10],
            },
        )
    return RuleResult(
        rule_id="G8",
        rule_name="sufficiency_check",
        status="PASS",
        message=f"Sufficiency: {sufficiency_report.recommendation.value}",
    )


def _rule_g9_no_severe_bias(
    bias_assessments: list | None,
) -> RuleResult:
    """G9: No edges with HIGH publication bias risk."""
    if bias_assessments is None or len(bias_assessments) == 0:
        return RuleResult(
            rule_id="G9",
            rule_name="no_severe_bias",
            status="PASS",
            message="No bias assessments to check (or none provided).",
        )
    high_bias = [
        ba.edge_relation_id
        for ba in bias_assessments
        if ba.bias_risk == BiasRisk.HIGH
    ]
    if high_bias:
        return RuleResult(
            rule_id="G9",
            rule_name="no_severe_bias",
            status="WARN",
            message=f"{len(high_bias)} edge(s) have HIGH publication bias: {high_bias[:5]}",
            details={"high_bias_edges": high_bias},
        )
    return RuleResult(
        rule_id="G9",
        rule_name="no_severe_bias",
        status="PASS",
        message="No edges with HIGH publication bias.",
    )


def _rule_g10_coverage_minimum(
    sufficiency_report: SufficiencyReport | None,
    min_coverage: float = 0.5,
) -> RuleResult:
    """G10: At least 50% of expected edges covered."""
    if sufficiency_report is None:
        return RuleResult(
            rule_id="G10",
            rule_name="coverage_minimum",
            status="WARN",
            message="No sufficiency report available for coverage check.",
        )
    total = sufficiency_report.total_edges_compiled
    covered = (
        sufficiency_report.edges_sufficient
        + sufficiency_report.edges_marginal
    )
    fraction = covered / total if total > 0 else 0.0
    if fraction < min_coverage:
        return RuleResult(
            rule_id="G10",
            rule_name="coverage_minimum",
            status="WARN",
            message=(
                f"Coverage {fraction:.1%} < {min_coverage:.0%} minimum. "
                f"{covered}/{total} edges covered."
            ),
            details={"coverage_fraction": fraction, "min_coverage": min_coverage},
        )
    return RuleResult(
        rule_id="G10",
        rule_name="coverage_minimum",
        status="PASS",
        message=f"Coverage {fraction:.1%} >= {min_coverage:.0%}.",
    )


def _rule_g11_edge_param_ids_present(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G11: All compiled edges have non-empty edge_param_id."""
    missing = [
        e.edge_relation_id
        for e in compiled_edges
        if not e.edge_param_id
    ]
    if missing:
        return RuleResult(
            rule_id="G11",
            rule_name="edge_param_ids",
            status="FAIL",
            message=f"{len(missing)} edge(s) missing edge_param_id.",
            details={"missing": missing[:5]},
        )
    return RuleResult(
        rule_id="G11",
        rule_name="edge_param_ids",
        status="PASS",
        message="All edges have edge_param_id.",
    )


def _rule_g12_heterogeneity_warnings(
    compiled_edges: list[CompiledEdge],
    i_squared_high: float = 75.0,
) -> RuleResult:
    """G12: Flag edges with very high heterogeneity (I^2 > 75%)."""
    high_het = [
        (e.edge_relation_id, e.i_squared)
        for e in compiled_edges
        if e.i_squared > i_squared_high
    ]
    if high_het:
        return RuleResult(
            rule_id="G12",
            rule_name="heterogeneity",
            status="WARN",
            message=f"{len(high_het)} edge(s) have I^2 > {i_squared_high}%.",
            details={"high_heterogeneity": high_het[:5]},
        )
    return RuleResult(
        rule_id="G12",
        rule_name="heterogeneity",
        status="PASS",
        message=f"No edges exceed I^2 > {i_squared_high}%.",
    )


def _rule_g13_prior_source_documented(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G13: All edges have documented prior source."""
    missing = [
        e.edge_relation_id
        for e in compiled_edges
        if not e.prior_source
    ]
    if missing:
        return RuleResult(
            rule_id="G13",
            rule_name="prior_documented",
            status="WARN",
            message=f"{len(missing)} edge(s) missing prior_source.",
            details={"missing": missing[:5]},
        )
    return RuleResult(
        rule_id="G13",
        rule_name="prior_documented",
        status="PASS",
        message="All edges have documented prior_source.",
    )


def _rule_g14_aggregation_method_documented(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G14: All edges have documented aggregation method."""
    missing = [
        e.edge_relation_id
        for e in compiled_edges
        if not e.aggregation_method
    ]
    if missing:
        return RuleResult(
            rule_id="G14",
            rule_name="aggregation_documented",
            status="WARN",
            message=f"{len(missing)} edge(s) missing aggregation_method.",
            details={"missing": missing[:5]},
        )
    return RuleResult(
        rule_id="G14",
        rule_name="aggregation_documented",
        status="PASS",
        message="All edges have documented aggregation_method.",
    )


def _rule_g15_se_inflation_coherence(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G15: SE inflation from coherence is documented and reasonable."""
    high_inflation = [
        (e.edge_relation_id, e.se_inflation_coherence)
        for e in compiled_edges
        if e.se_inflation_coherence > 2.0
    ]
    if high_inflation:
        return RuleResult(
            rule_id="G15",
            rule_name="se_inflation_coherence",
            status="WARN",
            message=(
                f"{len(high_inflation)} edge(s) have coherence SE inflation > 2.0."
            ),
            details={"high_inflation": high_inflation[:5]},
        )
    return RuleResult(
        rule_id="G15",
        rule_name="se_inflation_coherence",
        status="PASS",
        message="All coherence SE inflations <= 2.0.",
    )


def _rule_g16_se_inflation_pub_bias(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G16: SE inflation from publication bias is documented and reasonable."""
    high_inflation = [
        (e.edge_relation_id, e.se_inflation_pub_bias)
        for e in compiled_edges
        if e.se_inflation_pub_bias > 1.5
    ]
    if high_inflation:
        return RuleResult(
            rule_id="G16",
            rule_name="se_inflation_pub_bias",
            status="WARN",
            message=(
                f"{len(high_inflation)} edge(s) have pub bias SE inflation > 1.5."
            ),
            details={"high_inflation": high_inflation[:5]},
        )
    return RuleResult(
        rule_id="G16",
        rule_name="se_inflation_pub_bias",
        status="PASS",
        message="All pub bias SE inflations <= 1.5.",
    )


def _rule_g17_total_n_positive(
    compiled_edges: list[CompiledEdge],
) -> RuleResult:
    """G17: All edges should have total_n > 0."""
    bad = [
        e.edge_relation_id
        for e in compiled_edges
        if e.total_n <= 0
    ]
    if bad:
        return RuleResult(
            rule_id="G17",
            rule_name="total_n_positive",
            status="WARN",
            message=f"{len(bad)} edge(s) have total_n <= 0.",
            details={"bad_edges": bad[:5]},
        )
    return RuleResult(
        rule_id="G17",
        rule_name="total_n_positive",
        status="PASS",
        message="All edges have total_n > 0.",
    )


def _rule_g18_no_gaps_in_critical_paths(
    sufficiency_report: SufficiencyReport | None,
) -> RuleResult:
    """G18: No evidence gaps in critical DAG pathways."""
    if sufficiency_report is None:
        return RuleResult(
            rule_id="G18",
            rule_name="no_critical_gaps",
            status="WARN",
            message="No sufficiency report available.",
        )
    if sufficiency_report.gaps:
        return RuleResult(
            rule_id="G18",
            rule_name="no_critical_gaps",
            status="WARN",
            message=(
                f"{len(sufficiency_report.gaps)} gap(s) in evidence base: "
                f"{sufficiency_report.gaps[:5]}"
            ),
            details={"gaps": sufficiency_report.gaps[:10]},
        )
    return RuleResult(
        rule_id="G18",
        rule_name="no_critical_gaps",
        status="PASS",
        message="No evidence gaps detected.",
    )


# ═══════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════


def run_validation(
    compiled_edges: list[CompiledEdge],
    sufficiency_report: SufficiencyReport | None = None,
    bias_assessments: list | None = None,
) -> ValidationResult:
    """P6-VR: Execute all G1-G18 validation rules.

    Parameters
    ----------
    compiled_edges : list[CompiledEdge]
        All compiled edges from the extraction pipeline.
    sufficiency_report : SufficiencyReport | None
        From sufficiency_reporter.py.
    bias_assessments : list | None
        From publication_bias.py (list of BiasAssessment).

    Returns
    -------
    ValidationResult with per-rule outcomes and aggregate counts.
    """
    rule_results: list[RuleResult] = []

    # Execute all 18 rules
    rule_results.append(_rule_g1_minimum_edges(compiled_edges))
    rule_results.append(_rule_g2_all_edges_have_se(compiled_edges))
    rule_results.append(_rule_g3_all_edges_have_k(compiled_edges))
    rule_results.append(_rule_g4_plausible_betas(compiled_edges))
    rule_results.append(_rule_g5_se_not_excessive(compiled_edges))
    rule_results.append(_rule_g6_consistent_effect_scales(compiled_edges))
    rule_results.append(_rule_g7_no_duplicate_edges(compiled_edges))
    rule_results.append(_rule_g8_sufficiency_not_insufficient(sufficiency_report))
    rule_results.append(_rule_g9_no_severe_bias(bias_assessments))
    rule_results.append(_rule_g10_coverage_minimum(sufficiency_report))
    rule_results.append(_rule_g11_edge_param_ids_present(compiled_edges))
    rule_results.append(_rule_g12_heterogeneity_warnings(compiled_edges))
    rule_results.append(_rule_g13_prior_source_documented(compiled_edges))
    rule_results.append(_rule_g14_aggregation_method_documented(compiled_edges))
    rule_results.append(_rule_g15_se_inflation_coherence(compiled_edges))
    rule_results.append(_rule_g16_se_inflation_pub_bias(compiled_edges))
    rule_results.append(_rule_g17_total_n_positive(compiled_edges))
    rule_results.append(_rule_g18_no_gaps_in_critical_paths(sufficiency_report))

    # Aggregate counts
    n_pass = sum(1 for r in rule_results if r.status == "PASS")
    n_warn = sum(1 for r in rule_results if r.status == "WARN")
    n_fail = sum(1 for r in rule_results if r.status == "FAIL")

    for result in rule_results:
        if result.status == "FAIL":
            logger.error(
                "P6-VR Rule %s (%s): FAIL — %s",
                result.rule_id,
                result.rule_name,
                result.message,
            )
        elif result.status == "WARN":
            logger.warning(
                "P6-VR Rule %s (%s): WARN — %s",
                result.rule_id,
                result.rule_name,
                result.message,
            )
        else:
            logger.info(
                "P6-VR Rule %s (%s): PASS",
                result.rule_id,
                result.rule_name,
            )

    logger.info(
        "P6-VR Validation complete: %d PASS, %d WARN, %d FAIL "
        "(total %d rules)",
        n_pass,
        n_warn,
        n_fail,
        len(rule_results),
    )

    return ValidationResult(
        rule_results=rule_results,
        n_pass=n_pass,
        n_warn=n_warn,
        n_fail=n_fail,
        total_rules=len(rule_results),
    )
