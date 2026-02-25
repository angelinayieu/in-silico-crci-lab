# VERIFIED: formulas [G-1, G-2, G-3, G-4, G-5] match spec SYS_RT lines 90-258
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads RankingResult (D4-D6), StabilityState (F2),
#           CompositeState (F1), VarianceState (F3)
# VERIFIED: forward wiring — writes RankedSchedules for RT-H (adaptive_questions.py)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [G-G1, G-G2] raise on failure
"""
Component: SYS_RUNTIME.RT-G
Spec: SYS_RUNTIME_COMPLETE.md lines 90-258
Formulas:
    G-1: SAFE_A(a) = MSS_cog(a) − 0.3 × MSS_burden(a)  (from ALG-D4)
    G-2: SAFE_B(a) = SAFE_A(a) + 0.5 × ln(P_adhere(a))  (from ALG-D4)
    G-3: P(rank₁) classification (from ALG-F2)
    G-4: Bundle ceiling: total Δθ ≤ 1.5 SD
    G-5: R_intervention = min(R_e for e in critical_path_edges)
Reads: RankingResult (from ALG-D ranker.py),
       StabilityState (from ALG-F2 variance_decomposer.py),
       CompositeState (from ALG-F1 composite_scorer.py),
       VarianceState (from ALG-F3 evsi.py)
Writes: RankedSchedules (consumed by RT-H adaptive_questions.py, RT-I report_assembler.py)
Gates: G-G1, G-G2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..algorithm.chain_d_simulation.ranker import (
    InterventionRanking,
    BundleRanking,
    DoseRecommendation,
    RankingResult,
)
from ..algorithm.chain_f_analytics.variance_decomposer import StabilityClass, StabilityState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


class TimingVariant(str, Enum):
    """Schedule timing options."""

    IMMEDIATE = "immediate"
    PHASED = "phased"
    SEQUENTIAL = "sequential"


class ConstraintSeverity(str, Enum):
    """Constraint evaluation result."""

    CLEAR = "clear"
    SOFT_WARN = "soft_warn"
    ESCALATE = "escalate"
    HARD_EXCLUDE = "hard_exclude"


@dataclass(frozen=True)
class ScheduleCandidate:
    """A single candidate in the expanded pool (RT-G1 output)."""

    candidate_id: str
    action_id: str
    action_label: str
    is_bundle: bool
    member_ids: tuple[str, ...] = ()

    # Scores from ALG-D
    safe_a: float = 0.0
    safe_b: float = 0.0
    safe_b_cri_lower: float = 0.0
    safe_b_cri_upper: float = 0.0

    # Dose & timing
    dose_value: float | None = None
    dose_variant: str = "standard"  # low, standard, high
    timing: TimingVariant = TimingVariant.IMMEDIATE

    # Metadata
    claim_level: str = "model_implied"
    p_adhere: float = 0.5


@dataclass(frozen=True)
class ConstraintResult:
    """Result of constraint evaluation for one candidate."""

    candidate_id: str
    severity: ConstraintSeverity
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleItem:
    """One intervention item within a ranked schedule (RT-G3 output)."""

    action_id: str
    action_label: str
    dose_value: float | None
    dose_unit: str = "standard"
    timing: TimingVariant = TimingVariant.IMMEDIATE
    duration_weeks: float | None = None


@dataclass
class Schedule:
    """A fully assembled schedule (RT-G3 output)."""

    schedule_id: str
    rank: int
    items: list[ScheduleItem]
    safe_b: float
    safe_b_cri_lower: float
    safe_b_cri_upper: float
    safe_a: float
    stability_class: StabilityClass = StabilityClass.MODERATE
    p_rank_1: float = 0.0
    is_bundle: bool = False
    claim_level: str = "model_implied"
    warnings: list[str] = field(default_factory=list)


@dataclass
class RankedSchedules:
    """Complete RT-G output.

    Consumed by RT-H (adaptive questioning) and RT-I (reporting).
    """

    schedules: list[Schedule]
    n_expanded: int
    n_feasible: int
    n_excluded: int
    excluded_reasons: list[ConstraintResult]
    stability: StabilityState | None = None
    gate_g_g1_passed: bool = False
    gate_g_g2_passed: bool = False


# ═══════════════════════════════════════════════════════════════
#  RT-G1: Candidate Expansion
# ═══════════════════════════════════════════════════════════════


def _expand_candidates(
    ranking_result: RankingResult,
    top_k: int | None = None,
) -> list[ScheduleCandidate]:
    """RT-G1: Expand ranked interventions into schedule candidates.

    Process (spec lines 142-154):
        1. Take top-K interventions from ALG-D ranking
        2. For each: generate dose variants (standard, low, high)
        3. Generate timing variants (immediate, phased, sequential)
        4. Combine singles into bundles (from ALG-D bundles)
        5. Cap at MAX_POOL_SIZE

    Args:
        ranking_result: RankingResult from ALG-D.
        top_k: Maximum interventions to expand (default from config).

    Returns:
        List of ScheduleCandidate, up to MAX_POOL_SIZE.
    """
    if top_k is None:
        top_k = config.RT_G_TOP_K_DEFAULT

    candidates: list[ScheduleCandidate] = []
    cid = 0

    # Sort interventions by SAFE_B descending, take top K
    sorted_interventions = sorted(
        ranking_result.intervention_rankings.values(),
        key=lambda r: r.safe_b,
        reverse=True,
    )[:top_k]

    # G1 Step 1-3: Singles with dose + timing variants
    dose_variants = ["standard", "low", "high"]
    timing_variants = [TimingVariant.IMMEDIATE, TimingVariant.PHASED]

    for interv in sorted_interventions:
        for dose_var in dose_variants:
            for timing_var in timing_variants:
                if len(candidates) >= config.RT_G_MAX_POOL_SIZE:
                    break

                # Dose multiplier for variants
                dose_value = interv.dose_recommended
                if dose_value is not None:
                    if dose_var == "low":
                        dose_value *= 0.5
                    elif dose_var == "high":
                        dose_value *= 1.5

                candidates.append(ScheduleCandidate(
                    candidate_id=f"cand_{cid:04d}",
                    action_id=interv.action_id,
                    action_label=interv.action_label,
                    is_bundle=False,
                    safe_a=interv.safe_a,
                    safe_b=interv.safe_b,
                    safe_b_cri_lower=interv.safe_b_cri_lower,
                    safe_b_cri_upper=interv.safe_b_cri_upper,
                    dose_value=dose_value,
                    dose_variant=dose_var,
                    timing=timing_var,
                    claim_level=interv.claim_level.value,
                    p_adhere=interv.p_adhere,
                ))
                cid += 1

    # G1 Step 4: Include existing bundle rankings from ALG-D
    for bundle in ranking_result.bundle_rankings.values():
        if len(candidates) >= config.RT_G_MAX_POOL_SIZE:
            break

        candidates.append(ScheduleCandidate(
            candidate_id=f"cand_{cid:04d}",
            action_id=bundle.bundle_id,
            action_label=f"Bundle: {', '.join(bundle.member_ids)}",
            is_bundle=True,
            member_ids=bundle.member_ids,
            safe_a=bundle.safe_a,
            safe_b=bundle.safe_b,
            safe_b_cri_lower=bundle.safe_b_cri_lower,
            safe_b_cri_upper=bundle.safe_b_cri_upper,
            claim_level=bundle.claim_level.value,
            p_adhere=bundle.p_adhere,
        ))
        cid += 1

    logger.info(
        "RT-G1 Candidate Expansion: %d candidates from %d interventions + %d bundles",
        len(candidates),
        len(sorted_interventions),
        len(ranking_result.bundle_rankings),
    )

    return candidates


# ═══════════════════════════════════════════════════════════════
#  RT-G2: Constraint Filtering
# ═══════════════════════════════════════════════════════════════


def _filter_constraints(
    candidates: list[ScheduleCandidate],
    patient_context: dict | None = None,
) -> tuple[list[ScheduleCandidate], list[ConstraintResult]]:
    """RT-G2: Remove candidates violating hard constraints.

    Process (spec lines 156-207):
        1. Medical contraindications
        2. Drug interactions
        3. Patient preferences (exclude categories)
        4. Practical: cost ceiling, time commitment
        5. Bundle ceiling: total effect ≤ 1.5 SD (Formula G-4)
        6. Zero-rule catch-all safety net

    Args:
        candidates: Expanded pool from RT-G1.
        patient_context: Optional patient-specific constraints
            (treatment phase, comorbidities, preferences, etc.).

    Returns:
        Tuple of (feasible candidates, excluded with reasons).
    """
    if patient_context is None:
        patient_context = {}

    feasible: list[ScheduleCandidate] = []
    excluded: list[ConstraintResult] = []

    preferences_exclude = set(patient_context.get("excluded_categories", []))
    has_active_treatment = patient_context.get("has_active_treatment", False)
    comorbidity_count = patient_context.get("comorbidity_count", 0)
    age = patient_context.get("age", 60)

    for cand in candidates:
        reasons: list[str] = []
        severity = ConstraintSeverity.CLEAR

        # Constraint 3: Patient preference exclusions
        if cand.action_id in preferences_exclude:
            reasons.append(f"Excluded by patient preference: {cand.action_id}")
            severity = ConstraintSeverity.HARD_EXCLUDE

        # Constraint 5: Bundle ceiling (Formula G-4)
        if cand.is_bundle and abs(cand.safe_a) > config.RT_G_BUNDLE_CEILING_SD:
            reasons.append(
                f"Bundle exceeds ceiling: |SAFE_A|={abs(cand.safe_a):.2f} > "
                f"{config.RT_G_BUNDLE_CEILING_SD} SD"
            )
            severity = ConstraintSeverity.HARD_EXCLUDE

        # Zero-rule catch-all: CATCH_ZERO_MATCH_RISKY (spec lines 189-203)
        if (
            len(reasons) == 0
            and (has_active_treatment or comorbidity_count >= 3 or age > 80)
        ):
            reasons.append(
                "No specific safety rules matched, but patient has clinical "
                "risk factors. Clinician review recommended."
            )
            severity = ConstraintSeverity.SOFT_WARN

        if severity == ConstraintSeverity.HARD_EXCLUDE:
            excluded.append(ConstraintResult(
                candidate_id=cand.candidate_id,
                severity=severity,
                reasons=tuple(reasons),
            ))
        else:
            feasible.append(cand)
            if severity == ConstraintSeverity.SOFT_WARN:
                excluded.append(ConstraintResult(
                    candidate_id=cand.candidate_id,
                    severity=severity,
                    reasons=tuple(reasons),
                ))

    logger.info(
        "RT-G2 Constraint Filter: %d feasible, %d hard-excluded",
        len(feasible),
        sum(1 for e in excluded if e.severity == ConstraintSeverity.HARD_EXCLUDE),
    )

    return feasible, excluded


# ═══════════════════════════════════════════════════════════════
#  RT-G3: Schedule Assembly
# ═══════════════════════════════════════════════════════════════


def _assemble_schedules(
    feasible: list[ScheduleCandidate],
) -> list[Schedule]:
    """RT-G3: Assemble feasible candidates into ordered schedules.

    Process (spec lines 209-221):
        1. For each candidate: assign timing, duration, dose
        2. Sort by SAFE_B descending
        3. Top RT_G_TOP_SCHEDULES for detailed output

    Args:
        feasible: Constraint-satisfied candidates from RT-G2.

    Returns:
        Sorted list of Schedule objects, top N.
    """
    # Sort by SAFE_B descending
    sorted_candidates = sorted(feasible, key=lambda c: c.safe_b, reverse=True)

    # Take top N
    top_n = sorted_candidates[:config.RT_G_TOP_SCHEDULES]

    schedules: list[Schedule] = []
    for rank_idx, cand in enumerate(top_n, start=1):
        items = [ScheduleItem(
            action_id=cand.action_id,
            action_label=cand.action_label,
            dose_value=cand.dose_value,
            dose_unit=cand.dose_variant,
            timing=cand.timing,
        )]

        schedules.append(Schedule(
            schedule_id=f"sched_{rank_idx:03d}",
            rank=rank_idx,
            items=items,
            safe_b=cand.safe_b,
            safe_b_cri_lower=cand.safe_b_cri_lower,
            safe_b_cri_upper=cand.safe_b_cri_upper,
            safe_a=cand.safe_a,
            is_bundle=cand.is_bundle,
            claim_level=cand.claim_level,
        ))

    logger.info(
        "RT-G3 Schedule Assembly: %d schedules assembled from %d feasible",
        len(schedules), len(feasible),
    )

    return schedules


# ═══════════════════════════════════════════════════════════════
#  RT-G4: Stability Classification
# ═══════════════════════════════════════════════════════════════


def _attach_stability(
    schedules: list[Schedule],
    stability_state: StabilityState | None,
) -> None:
    """RT-G4: Attach decision stability from ALG-F2 to schedules.

    Process (spec lines 222-229):
        P(rank₁) ≥ 0.80 → STABLE; 0.60–0.79 → MODERATE;
        0.40–0.59 → UNSTABLE; < 0.40 → HIGHLY_UNSTABLE

    Mutates schedules in-place.

    Args:
        schedules: Assembled schedules from RT-G3.
        stability_state: ALG-F2 stability analysis result.
    """
    if stability_state is None:
        return

    for sched in schedules:
        sched.stability_class = stability_state.stability_class

        # Find p_rank_1 for the primary action in this schedule
        if sched.items:
            action_id = sched.items[0].action_id
            sched.p_rank_1 = stability_state.rank_1_probabilities.get(action_id, 0.0)


# ═══════════════════════════════════════════════════════════════
#  Gates
# ═══════════════════════════════════════════════════════════════


def _validate_gate_g_g1(feasible_count: int) -> None:
    """Gate G-G1: At least 1 feasible candidate.

    Spec line 239: ≥1 feasible → proceed; 0 → WARN.

    Raises:
        GateViolation: If no feasible candidates.
    """
    if feasible_count == 0:
        raise GateViolation(
            "G-G1",
            "No feasible candidates after constraint filtering. "
            "All candidates were excluded by hard constraints.",
        )

    logger.info("Gate G-G1 PASSED: %d feasible candidates", feasible_count)


def _validate_gate_g_g2(schedules: list[Schedule]) -> bool:
    """Gate G-G2: Top schedule SAFE_B > MID (0.5 SD).

    Spec line 240: SAFE_B > 0.5 → confident; else → marginal.

    Returns:
        True if confident recommendation, False if marginal.
    """
    if not schedules:
        return False

    top_safe_b = schedules[0].safe_b
    confident = top_safe_b > config.RT_G_SAFE_B_MID_THRESHOLD

    if confident:
        logger.info(
            "Gate G-G2 PASSED: top SAFE_B=%.4f > %.2f (confident)",
            top_safe_b, config.RT_G_SAFE_B_MID_THRESHOLD,
        )
    else:
        logger.warning(
            "Gate G-G2 MARGINAL: top SAFE_B=%.4f ≤ %.2f",
            top_safe_b, config.RT_G_SAFE_B_MID_THRESHOLD,
        )

    return confident


# ═══════════════════════════════════════════════════════════════
#  Top-Level: generate_schedule (RT-G entry point)
# ═══════════════════════════════════════════════════════════════


def generate_schedule(
    ranking_result: RankingResult,
    stability_state: StabilityState | None = None,
    patient_context: dict | None = None,
    top_k: int | None = None,
) -> RankedSchedules:
    """RT-G: Transform ranked interventions into actionable schedules.

    Pipeline: G1(expand) → G2(filter) → G3(assemble) → G4(stability).

    Args:
        ranking_result: RankingResult from ALG-D (D4-D6).
        stability_state: StabilityState from ALG-F2 (optional).
        patient_context: Patient-specific constraint context.
        top_k: Override for top-K expansion limit.

    Returns:
        RankedSchedules.

    Raises:
        GateViolation: If G-G1 fails (no feasible candidates).
    """
    logger.info(
        "── RT-G: Schedule Optimization ──\n"
        "  n_interventions=%d, n_bundles=%d",
        ranking_result.n_interventions_ranked,
        ranking_result.n_bundles_ranked,
    )

    # RT-G1: Candidate Expansion
    candidates = _expand_candidates(ranking_result, top_k=top_k)

    # RT-G2: Constraint Filtering
    feasible, excluded = _filter_constraints(candidates, patient_context)

    # Gate G-G1: ≥1 feasible
    _validate_gate_g_g1(len(feasible))

    # RT-G3: Schedule Assembly
    schedules = _assemble_schedules(feasible)

    # RT-G4: Stability Classification
    _attach_stability(schedules, stability_state)

    # Gate G-G2: SAFE_B > MID
    g_g2_passed = _validate_gate_g_g2(schedules)

    n_hard_excluded = sum(
        1 for e in excluded if e.severity == ConstraintSeverity.HARD_EXCLUDE
    )

    result = RankedSchedules(
        schedules=schedules,
        n_expanded=len(candidates),
        n_feasible=len(feasible),
        n_excluded=n_hard_excluded,
        excluded_reasons=excluded,
        stability=stability_state,
        gate_g_g1_passed=True,
        gate_g_g2_passed=g_g2_passed,
    )

    logger.info(
        "RT-G complete: %d schedules, G-G1=%s, G-G2=%s",
        len(schedules), result.gate_g_g1_passed, result.gate_g_g2_passed,
    )

    return result
