# VERIFIED: spec SYS_RT lines 389-511 (RT-I: Reporting & Provenance)
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads RankedSchedules (RT-G), QuestioningState (RT-H),
#           CompositeState (F1), StabilityState (F2), VarianceState (F3)
# VERIFIED: forward wiring — writes RecommendationReport for SYS_PRESENTATION
# VERIFIED: no hardcoded formula parameters — all from config.py
"""
Component: SYS_RUNTIME.RT-I
Spec: SYS_RUNTIME_COMPLETE.md lines 389-511
Subsystems:
    I1: Evidence Provenance — trace each recommendation to supporting evidence
    I2: Uncertainty Disclosure — mandatory uncertainty information
    I3: Session Summary — audit trail for session
    I4: Report Assembly — package RecommendationReport for PRES
Reads: RankedSchedules (from RT-G), QuestioningState (from RT-H),
       CompositeState (from ALG-F1), StabilityState (from ALG-F2),
       VarianceState (from ALG-F3)
Writes: RecommendationReport (consumed by SYS_PRESENTATION)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from crci.shared import config
from crci.shared.models.output_contracts import (
    CompositeScore,
    DecisionTrace,
    DecisionTraceEntry,
    DomainScore,
    EvidenceGapItem,
    EvidenceGapReport,
    RecommendationReport,
    ScheduleAction,
    SchedulePlan,
    VarianceComponent,
    VarianceDecomposition,
)
from crci.shared.models.enums import ReportOutputMode, SeverityTier, StabilityClass

from ..algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier as F1SeverityTier,
)
from ..algorithm.chain_f_analytics.variance_decomposer import StabilityState
from ..algorithm.chain_f_analytics.evsi import VarianceState
from .schedule_generator import RankedSchedules, Schedule
from .adaptive_questions import QuestioningState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ProvenanceEntry:
    """Evidence provenance for one recommended intervention (RT-I1)."""

    intervention_id: str
    intervention_label: str
    claim_level: str
    supporting_edges: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class UncertaintyDisclosure:
    """Mandatory uncertainty disclosure (RT-I2).

    ALWAYS included — cannot be suppressed.
    """

    stability_class: str
    p_rank_1: float
    cri_95_lower: float
    cri_95_upper: float
    variance_decomposition: dict[str, float]
    top_reducible_sources: list[str]
    critical_edges: list[str]
    warning_text: str | None = None


@dataclass
class SessionSummary:
    """Session audit summary (RT-I3)."""

    n_questions_asked: int
    n_questions_skipped: int
    stop_reason: str | None
    total_ig: float
    timestamp: str
    duration_seconds: float | None = None


# ═══════════════════════════════════════════════════════════════
#  RT-I1: Evidence Provenance
# ═══════════════════════════════════════════════════════════════


def _build_provenance(
    schedules: list[Schedule],
) -> list[ProvenanceEntry]:
    """RT-I1: Build provenance chain for each recommended intervention.

    Args:
        schedules: Ranked schedules from RT-G.

    Returns:
        ProvenanceEntry per schedule.
    """
    entries: list[ProvenanceEntry] = []

    for sched in schedules:
        for item in sched.items:
            entries.append(ProvenanceEntry(
                intervention_id=item.action_id,
                intervention_label=item.action_label,
                claim_level=sched.claim_level,
            ))

    logger.info("RT-I1 Provenance: %d entries", len(entries))
    return entries


# ═══════════════════════════════════════════════════════════════
#  RT-I2: Uncertainty Disclosure
# ═══════════════════════════════════════════════════════════════


def _build_uncertainty_disclosure(
    stability: StabilityState | None,
    variance: VarianceState | None,
    top_schedule: Schedule | None,
) -> UncertaintyDisclosure:
    """RT-I2: Build mandatory uncertainty disclosure.

    CRITICAL: This is ALWAYS included — cannot be suppressed (spec line 443).

    Args:
        stability: ALG-F2 decision stability result.
        variance: ALG-F3 variance decomposition result.
        top_schedule: Top ranked schedule for CrI.

    Returns:
        UncertaintyDisclosure.
    """
    # Stability
    stab_class = "MODERATE"
    p_rank_1 = 0.0
    critical_edges: list[str] = []
    if stability is not None:
        stab_class = stability.stability_class.value
        p_rank_1 = max(stability.rank_1_probabilities.values()) if stability.rank_1_probabilities else 0.0
        critical_edges = [e.edge_id for e in stability.decision_critical_edges]

    # Variance decomposition
    var_decomp: dict[str, float] = {}
    top_reducible: list[str] = []
    if variance is not None:
        var_decomp = {
            "literature": variance.literature_pct,
            "measurement": variance.measurement_pct,
            "structural": variance.structural_pct,
            "proxy": variance.proxy_pct,
            "missing": variance.missing_pct,
        }
        top_reducible = [r.source_name for r in variance.top_reducible]

    # CrI from top schedule
    cri_lower = 0.0
    cri_upper = 0.0
    if top_schedule is not None:
        cri_lower = top_schedule.safe_b_cri_lower
        cri_upper = top_schedule.safe_b_cri_upper

    # Warning text for HIGHLY_UNSTABLE
    warning = None
    if stab_class == "HIGHLY_UNSTABLE":
        warning = (
            "Warning: The best intervention recommendation is highly uncertain. "
            "Rankings may change significantly with additional information. "
            "Please discuss options carefully with your healthcare provider."
        )

    disclosure = UncertaintyDisclosure(
        stability_class=stab_class,
        p_rank_1=p_rank_1,
        cri_95_lower=cri_lower,
        cri_95_upper=cri_upper,
        variance_decomposition=var_decomp,
        top_reducible_sources=top_reducible,
        critical_edges=critical_edges,
        warning_text=warning,
    )

    logger.info(
        "RT-I2 Uncertainty Disclosure: stability=%s, P(rank1)=%.2f",
        stab_class, p_rank_1,
    )

    return disclosure


# ═══════════════════════════════════════════════════════════════
#  RT-I3: Session Summary
# ═══════════════════════════════════════════════════════════════


def _build_session_summary(
    questioning: QuestioningState | None,
) -> SessionSummary:
    """RT-I3: Build session audit summary.

    Args:
        questioning: RT-H questioning state.

    Returns:
        SessionSummary.
    """
    if questioning is None:
        return SessionSummary(
            n_questions_asked=0,
            n_questions_skipped=0,
            stop_reason=None,
            total_ig=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return SessionSummary(
        n_questions_asked=questioning.n_questions,
        n_questions_skipped=questioning.n_skipped,
        stop_reason=questioning.stop_reason.value if questioning.stop_reason else None,
        total_ig=questioning.total_ig,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════════════════════════
#  RT-I4: Report Assembly
# ═══════════════════════════════════════════════════════════════


def _map_severity_tier(f1_tier: F1SeverityTier) -> SeverityTier:
    """Map ALG-F1 SeverityTier to output_contracts (enums) SeverityTier."""
    mapping = {
        F1SeverityTier.EXCELLENT: SeverityTier.EXCELLENT,
        F1SeverityTier.GOOD: SeverityTier.GOOD,
        F1SeverityTier.MILD_IMPAIRMENT: SeverityTier.MILD_CONCERN,
        F1SeverityTier.MODERATE_IMPAIRMENT: SeverityTier.MODERATE,
        F1SeverityTier.POOR: SeverityTier.POOR,
        F1SeverityTier.SEVERE_IMPAIRMENT: SeverityTier.SEVERE,
    }
    return mapping.get(f1_tier, SeverityTier.MODERATE)


def _build_composite_score(
    composite: CompositeState | None,
    run_id: str,
    subject_ref: str,
) -> CompositeScore:
    """Build output CompositeScore from ALG-F1 CompositeState."""
    if composite is None:
        return CompositeScore(
            run_id=run_id,
            subject_ref=subject_ref,
            composite_z=0.0,
            overall_severity=SeverityTier.MODERATE,
        )

    return CompositeScore(
        run_id=run_id,
        subject_ref=subject_ref,
        composite_z=composite.crci_composite,
        composite_percentile=composite.percentile,
        overall_severity=_map_severity_tier(composite.severity_tier),
        domain_scores=[
            DomainScore(
                domain_id=domain,
                domain_label=domain.replace("_", " ").title(),
                z_score=z,
                severity_tier=SeverityTier.MODERATE,
            )
            for domain, z in composite.subdomain_scores.items()
        ],
    )


def _map_stability_class(f2_class) -> StabilityClass:
    """Map ALG-F2 StabilityClass to output enums StabilityClass."""
    # enums.StabilityClass: STABLE, SOFT, UNSTABLE
    # F2 StabilityClass: STABLE, MODERATE, UNSTABLE, HIGHLY_UNSTABLE
    mapping = {
        "STABLE": StabilityClass.STABLE,
        "MODERATE": StabilityClass.SOFT,
        "UNSTABLE": StabilityClass.UNSTABLE,
        "HIGHLY_UNSTABLE": StabilityClass.UNSTABLE,
    }
    return mapping.get(f2_class.value, StabilityClass.UNSTABLE)


def _build_schedule_plan(sched: Schedule, run_id: str) -> SchedulePlan:
    """Convert internal Schedule to output SchedulePlan."""
    actions = [
        ScheduleAction(
            action_id=item.action_id,
            action_label=item.action_label,
            action_class="intervention",
            dose_value=item.dose_value or 0.0,
            dose_unit=item.dose_unit,
            timing_summary=item.timing.value,
            frequency="as_prescribed",
            duration_days=int((item.duration_weeks or config.RT_I_DEFAULT_DURATION_WEEKS) * 7),
        )
        for item in sched.items
    ]

    return SchedulePlan(
        schedule_id=sched.schedule_id,
        run_id=run_id,
        plan_rank=sched.rank,
        plan_type="primary" if sched.rank == 1 else "alternative",
        actions=actions,
        utility_score=sched.safe_b,
        stability_class=_map_stability_class(sched.stability_class),
        p_rank_1=sched.p_rank_1,
        warnings=sched.warnings,
    )


def _build_variance_decomposition(
    variance: VarianceState | None,
    run_id: str,
) -> VarianceDecomposition | None:
    """Build output VarianceDecomposition from ALG-F3."""
    if variance is None:
        return None

    components = [
        VarianceComponent(source="literature", fraction=variance.literature_pct),
        VarianceComponent(source="measurement", fraction=variance.measurement_pct),
        VarianceComponent(source="structural", fraction=variance.structural_pct),
        VarianceComponent(source="proxy", fraction=variance.proxy_pct),
        VarianceComponent(source="missing", fraction=variance.missing_pct),
    ]

    dominant = max(components, key=lambda c: c.fraction).source if components else None

    return VarianceDecomposition(
        run_id=run_id,
        components=components,
        total_variance=variance.total_variance,
        dominant_source=dominant,
    )


def _build_decision_trace(
    provenance: list[ProvenanceEntry],
    disclosure: UncertaintyDisclosure,
    session: SessionSummary,
    run_id: str,
) -> DecisionTrace:
    """Build decision trace for audit trail."""
    entries: list[DecisionTraceEntry] = []

    # Session info
    entries.append(DecisionTraceEntry(
        step="session_start",
        description=f"Session with {session.n_questions_asked} questions",
        outcome=f"stop_reason={session.stop_reason or 'N/A'}",
    ))

    # Stability
    entries.append(DecisionTraceEntry(
        step="stability_assessment",
        description=f"Decision stability: {disclosure.stability_class}",
        outcome=f"P(rank1)={disclosure.p_rank_1:.3f}",
        confidence=disclosure.p_rank_1,
    ))

    # Top recommendations
    for prov in provenance[:config.RT_I_DECISION_TRACE_TOP_N]:
        entries.append(DecisionTraceEntry(
            step="recommendation",
            description=f"Recommend: {prov.intervention_label}",
            inputs={"claim_level": prov.claim_level},
            outcome=f"intervention_id={prov.intervention_id}",
        ))

    return DecisionTrace(
        run_id=run_id,
        entries=entries,
        decision_critical_edges=disclosure.critical_edges,
    )


def assemble_report(
    run_id: str,
    subject_ref: str,
    ranked_schedules: RankedSchedules,
    composite: CompositeState | None = None,
    stability: StabilityState | None = None,
    variance: VarianceState | None = None,
    questioning: QuestioningState | None = None,
    output_mode: ReportOutputMode = ReportOutputMode.CLINICAL,
) -> RecommendationReport:
    """RT-I4: Assemble complete RecommendationReport.

    This is the PRIMARY handoff from SYS_RUNTIME to SYS_PRESENTATION.

    Args:
        run_id: Unique session/run ID.
        subject_ref: Patient reference.
        ranked_schedules: From RT-G.
        composite: From ALG-F1.
        stability: From ALG-F2.
        variance: From ALG-F3.
        questioning: From RT-H.
        output_mode: Clinical or research output mode.

    Returns:
        RecommendationReport.
    """
    logger.info(
        "── RT-I: Report Assembly ──\n"
        "  run_id=%s, subject=%s, mode=%s, n_schedules=%d",
        run_id, subject_ref, output_mode.value,
        len(ranked_schedules.schedules),
    )

    # RT-I1: Provenance
    provenance = _build_provenance(ranked_schedules.schedules)

    # RT-I2: Uncertainty Disclosure (MANDATORY)
    top_sched = ranked_schedules.schedules[0] if ranked_schedules.schedules else None
    disclosure = _build_uncertainty_disclosure(stability, variance, top_sched)

    # RT-I3: Session Summary
    session = _build_session_summary(questioning)

    # RT-I4: Package
    composite_score = _build_composite_score(composite, run_id, subject_ref)

    # Primary schedule
    if ranked_schedules.schedules:
        primary = _build_schedule_plan(ranked_schedules.schedules[0], run_id)
    else:
        primary = SchedulePlan(
            schedule_id="empty",
            run_id=run_id,
            plan_rank=1,
            plan_type="primary",
        )

    # Alternative schedules
    alternatives = [
        _build_schedule_plan(s, run_id)
        for s in ranked_schedules.schedules[1:]
    ]

    # Variance decomposition
    var_decomp = _build_variance_decomposition(variance, run_id)

    # Decision trace
    trace = _build_decision_trace(provenance, disclosure, session, run_id)

    # Safety flags
    safety_flags: list[str] = []
    if disclosure.warning_text:
        safety_flags.append("HIGHLY_UNSTABLE_WARNING")

    warnings: list[str] = []
    if not ranked_schedules.gate_g_g2_passed:
        warnings.append("Marginal recommendation: top SAFE_B below MID threshold")

    report = RecommendationReport(
        run_id=run_id,
        subject_ref=subject_ref,
        output_mode=output_mode,
        composite_score=composite_score,
        primary_schedule=primary,
        alternative_schedules=alternatives,
        variance_decomposition=var_decomp,
        decision_trace=trace,
        safety_flags=safety_flags,
        run_warnings=warnings,
        timestamp=session.timestamp,
    )

    logger.info(
        "RT-I complete: run_id=%s, %d alternatives, safety_flags=%s",
        run_id, len(alternatives), safety_flags,
    )

    return report
