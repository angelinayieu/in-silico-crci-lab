# VERIFIED: spec SYS_PRES lines 255-266 (PRES-SCI4)
# VERIFIED: read-only — no computation, no DB writes
"""
Component: SYS_PRESENTATION.PRES-SCI4
Spec: SYS_PRESENTATION_COMPLETE.md lines 255-266
Purpose: Render model transparency and auditability panel —
         prior selection log, SE calibration, assumptions,
         chain-vs-direct results.
Reads: RecommendationReport.decision_trace, variance_decomposition
Writes: Nothing (render-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crci.shared.models.output_contracts import (
    DecisionTrace,
    DecisionTraceEntry,
    RecommendationReport,
    VarianceDecomposition,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  View Models
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PriorSelectionRow:
    """One edge's prior selection for the transparency log."""

    edge_id: str
    prior_type: str
    rationale: str
    k: int | None = None
    has_rct: bool = False


@dataclass(frozen=True)
class SECalibrationRow:
    """SE calibration layers applied to one edge."""

    edge_id: str
    layers_applied: list[str]
    final_se_eff: float
    inflation_factor: float


@dataclass(frozen=True)
class AssumptionRow:
    """One model assumption for the assumptions tab."""

    assumption_id: str
    description: str
    impact: str  # "HIGH", "MEDIUM", "LOW"
    sensitivity: str  # what happens if wrong


@dataclass(frozen=True)
class ModelInspectionView:
    """PRES-SCI4: Model transparency and auditability panel.

    Supports transparency and auditability — enables peer reviewers
    to inspect every modeling choice. Reproducibility is handled
    separately by seeded randomness in algorithm chains.
    """

    prior_log: list[PriorSelectionRow]
    se_calibration: list[SECalibrationRow]
    assumptions: list[AssumptionRow]
    model_version: str | None
    deploy_timestamp: str | None
    n_edges: int
    n_nodes: int
    decision_steps: list[str]
    empty_state: bool = False
    empty_message: str = ""


# ═══════════════════════════════════════════════════════════════
#  Default Assumptions
# ═══════════════════════════════════════════════════════════════


_DEFAULT_ASSUMPTIONS: list[AssumptionRow] = [
    AssumptionRow(
        assumption_id="A1",
        description="DAG structure is acyclic (no unmeasured confounders between nodes)",
        impact="HIGH",
        sensitivity="If violated, causal effect estimates may be biased. "
                    "Chain-vs-direct validation partially detects this.",
    ),
    AssumptionRow(
        assumption_id="A2",
        description="Linear edge effects (β parameters represent linear associations)",
        impact="MEDIUM",
        sensitivity="Nonlinear dose-response captured by Emax model where available. "
                    "For uncaptured nonlinearity, SE inflation provides partial robustness.",
    ),
    AssumptionRow(
        assumption_id="A3",
        description="Prior distributions are informative but not dominating",
        impact="MEDIUM",
        sensitivity="RobustMAP and power priors discount historical data. "
                    "k≥5 edges have strong empirical signal. k<5 edges rely more on prior.",
    ),
    AssumptionRow(
        assumption_id="A4",
        description="Exchangeability of study populations (random effects model)",
        impact="MEDIUM",
        sensitivity="If population heterogeneity is extreme, τ² will be large "
                    "and I² will flag the edge as high-heterogeneity.",
    ),
    AssumptionRow(
        assumption_id="A5",
        description="Patient baseline is representative of study populations",
        impact="LOW",
        sensitivity="Effect modifiers (age, cancer type) adjust for major "
                    "population differences. Residual mismatch inflates SE.",
    ),
]


# ═══════════════════════════════════════════════════════════════
#  Rendering
# ═══════════════════════════════════════════════════════════════


def render_model_inspection(
    report: RecommendationReport,
    prior_log: list[PriorSelectionRow] | None = None,
    se_calibration: list[SECalibrationRow] | None = None,
    n_nodes: int = 63,
    n_edges: int = 118,
) -> ModelInspectionView:
    """PRES-SCI4: Render model transparency panel.

    Tabbed panels for expert review:
    1. Prior Selection Log — which prior was chosen per edge
    2. SE Calibration — 7-layer inflation per edge
    3. Assumptions — model assumptions with impact assessment
    4. Decision Steps — from decision trace

    Args:
        report: RecommendationReport.
        prior_log: Pre-built prior selection rows (from algorithm outputs).
        se_calibration: Pre-built SE calibration rows (from algorithm outputs).
        n_nodes: Number of nodes in the model.
        n_edges: Number of edges in the model.

    Returns:
        ModelInspectionView ready for rendering.
    """
    if report.decision_trace is None and prior_log is None:
        return ModelInspectionView(
            prior_log=[],
            se_calibration=[],
            assumptions=_DEFAULT_ASSUMPTIONS,
            model_version=report.engine_version,
            deploy_timestamp=report.timestamp,
            n_edges=n_edges,
            n_nodes=n_nodes,
            decision_steps=[],
            empty_state=True,
            empty_message="No model inspection data available for this session.",
        )

    # Decision steps from trace
    steps: list[str] = []
    if report.decision_trace is not None:
        for entry in report.decision_trace.entries:
            steps.append(f"[{entry.step}] {entry.description} → {entry.outcome}")

    return ModelInspectionView(
        prior_log=prior_log or [],
        se_calibration=se_calibration or [],
        assumptions=_DEFAULT_ASSUMPTIONS,
        model_version=report.engine_version,
        deploy_timestamp=report.timestamp,
        n_edges=n_edges,
        n_nodes=n_nodes,
        decision_steps=steps,
    )
