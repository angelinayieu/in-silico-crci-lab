# VERIFIED: spec SYS_RT lines 1-88 (system card, macro chain)
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads ALG chain outputs (D4-D6, F1, F2, F3)
# VERIFIED: forward wiring — writes RecommendationReport for SYS_PRESENTATION
"""
Component: SYS_RUNTIME.SESSION
Spec: SYS_RUNTIME_COMPLETE.md lines 1-88 (System Card)
Purpose: Top-level session orchestrator. Ties together:
    RT-G (schedule optimization) →
    RT-H (adaptive questioning, optional) →
    RT-I (report assembly) →
    RecommendationReport
Reads: RankingResult (ALG-D), CompositeState (ALG-F1),
       StabilityState (ALG-F2), VarianceState (ALG-F3)
Writes: RecommendationReport (consumed by SYS_PRESENTATION)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from crci.shared.models.enums import ReportOutputMode
from crci.shared.models.output_contracts import RecommendationReport

from ..algorithm.chain_d_simulation.ranker import RankingResult
from ..algorithm.chain_f_analytics.composite_scorer import CompositeState
from ..algorithm.chain_f_analytics.evsi import VarianceState
from ..algorithm.chain_f_analytics.variance_decomposer import StabilityState

from .adaptive_questions import QuestioningState
from .report_assembler import assemble_report
from .schedule_generator import RankedSchedules, generate_schedule

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class SessionConfig:
    """Per-session configuration."""

    subject_ref: str
    output_mode: ReportOutputMode = ReportOutputMode.CLINICAL
    enable_adaptive_questioning: bool = False
    patient_context: dict | None = None
    top_k: int | None = None


@dataclass
class SessionResult:
    """Complete session result, wrapping RecommendationReport + metadata."""

    run_id: str
    report: RecommendationReport
    ranked_schedules: RankedSchedules
    questioning_state: QuestioningState | None = None
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  Session Orchestration
# ═══════════════════════════════════════════════════════════════


def run_session(
    session_config: SessionConfig,
    ranking_result: RankingResult,
    composite: CompositeState | None = None,
    stability: StabilityState | None = None,
    variance: VarianceState | None = None,
    questioning: QuestioningState | None = None,
) -> SessionResult:
    """Execute a complete runtime session.

    Pipeline: RT-G → (RT-H optional) → RT-I.

    This is the top-level entry point for the runtime system.
    It orchestrates the three runtime chains and produces a
    RecommendationReport for SYS_PRESENTATION.

    Args:
        session_config: Session-level parameters.
        ranking_result: From ALG-D (D4-D6) — ranked interventions.
        composite: From ALG-F1 — composite cognitive score.
        stability: From ALG-F2 — decision stability analysis.
        variance: From ALG-F3 — variance decomposition.
        questioning: From RT-H — adaptive questioning state (if pre-run).

    Returns:
        SessionResult containing the RecommendationReport.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    start_time = datetime.now(timezone.utc).isoformat()

    logger.info(
        "═══ SYS_RUNTIME Session Start ═══\n"
        "  run_id=%s, subject=%s, mode=%s\n"
        "  n_interventions=%d, n_bundles=%d",
        run_id, session_config.subject_ref,
        session_config.output_mode.value,
        ranking_result.n_interventions_ranked,
        ranking_result.n_bundles_ranked,
    )

    # ── RT-G: Schedule Optimization ──
    ranked_schedules = generate_schedule(
        ranking_result=ranking_result,
        stability_state=stability,
        patient_context=session_config.patient_context,
        top_k=session_config.top_k,
    )

    logger.info(
        "RT-G complete: %d schedules, G-G1=%s, G-G2=%s",
        len(ranked_schedules.schedules),
        ranked_schedules.gate_g_g1_passed,
        ranked_schedules.gate_g_g2_passed,
    )

    # ── RT-H: Adaptive Questioning (optional) ──
    # In a full implementation, this would be an interactive loop.
    # Here we accept a pre-computed QuestioningState.
    if questioning is not None:
        logger.info(
            "RT-H: Using pre-computed questioning state (%d questions)",
            questioning.n_questions,
        )

    # ── RT-I: Report Assembly ──
    report = assemble_report(
        run_id=run_id,
        subject_ref=session_config.subject_ref,
        ranked_schedules=ranked_schedules,
        composite=composite,
        stability=stability,
        variance=variance,
        questioning=questioning,
        output_mode=session_config.output_mode,
    )

    end_time = datetime.now(timezone.utc).isoformat()

    result = SessionResult(
        run_id=run_id,
        report=report,
        ranked_schedules=ranked_schedules,
        questioning_state=questioning,
        start_time=start_time,
        end_time=end_time,
    )

    logger.info(
        "═══ SYS_RUNTIME Session Complete ═══\n"
        "  run_id=%s, n_schedules=%d, severity=%s",
        run_id,
        len(ranked_schedules.schedules),
        report.composite_score.overall_severity.value,
    )

    return result
