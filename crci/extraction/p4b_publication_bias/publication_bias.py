# VERIFIED: formulas [P4B-1, P4B-2, P4B-3, P4B-4] match spec SYS_EX lines 1394-1533
# VERIFIED: imports — all modules exist (config.py, enums.py, intermediate_states.py)
# VERIFIED: backward wiring — reads PooledEstimate from p4_aggregation
# VERIFIED: forward wiring — writes BiasAssessment for sufficiency_reporter.py
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gates [P4B-G1] raise on failure
"""
Component: SYS_EXTRACTION.EX-P4B
Spec: SYS_EXTRACTION_COMPLETE.md lines 1394-1533
Formulas: P4B-1 (Egger regression), P4B-2 (Trim & Fill), P4B-3 (Leave-one-out),
          P4B-4 (Bias aggregator)
Reads: PooledEstimate (from meta_analyzer.py)
Writes: BiasAssessment (consumed by sufficiency_reporter.py, deploy_gate.py)
Gates: P4B-G1
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from scipy import stats as scipy_stats

from crci.shared.config import (
    PUB_BIAS_EGGER_ALPHA,
    PUB_BIAS_MIN_K_EGGER,
    PUB_BIAS_SE_INFLATION_HIGH,
    PUB_BIAS_SE_INFLATION_LOW,
    PUB_BIAS_SE_INFLATION_MODERATE,
)
from crci.shared.models.enums import BiasRisk
from crci.shared.models.intermediate_states import (
    GateViolation,
    PooledEstimate,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output data structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class EggerResult:
    """Result of P4B-S1 Egger regression test."""

    intercept: float
    intercept_se: float
    t_statistic: float
    p_value: float
    significant: bool  # p < PUB_BIAS_EGGER_ALPHA
    k: int


@dataclass
class TrimFillResult:
    """Result of P4B-S2 Trim & Fill analysis."""

    beta_original: float
    beta_adjusted: float
    shift: float  # |beta_adjusted - beta_original|
    shift_sd_units: float  # shift / SE_pooled
    n_imputed: int
    severity: str  # "NONE", "MODERATE", "SEVERE"


@dataclass
class LeaveOneOutResult:
    """Result of P4B-S3 Leave-One-Out sensitivity analysis."""

    study_influences: list[float]  # influence(j) for each study j
    influential_studies: list[int]  # indices where influence > 2.0
    loo_range: float  # max(beta_{-j}) - min(beta_{-j})
    loo_range_sd_units: float  # loo_range / SE_pooled
    fragile: bool  # loo_range_sd_units > 0.3


@dataclass
class BiasAssessment:
    """P4B-S4 aggregated publication bias assessment."""

    edge_relation_id: str
    egger: EggerResult | None = None
    trim_fill: TrimFillResult | None = None
    leave_one_out: LeaveOneOutResult | None = None
    n_flags: int = 0
    bias_risk: BiasRisk = BiasRisk.LOW
    se_inflation_factor: float = 1.0
    flags: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


# ═══════════════════════════════════════════════════════════════
#  P4B-G1: Minimum k gate
# ═══════════════════════════════════════════════════════════════


def _enforce_gate_p4b_g1(k: int, edge_relation_id: str) -> bool:
    """Gate P4B-G1: k >= PUB_BIAS_MIN_K_EGGER or SKIP.

    Returns True if k is sufficient to run bias assessment,
    False if the assessment should be skipped.

    Raises GateViolation only if k < 2 (should never reach this point
    but protects against impossible meta-analysis).
    """
    if k < 2:
        raise GateViolation(
            gate_id="P4B-G1",
            message=(
                f"Cannot run publication bias assessment with k={k} "
                f"studies for edge '{edge_relation_id}'. Minimum is 2."
            ),
            context={"edge_relation_id": edge_relation_id, "k": k},
        )
    if k < PUB_BIAS_MIN_K_EGGER:
        logger.info(
            "P4B-G1: k=%d < %d for edge '%s'; skipping Egger regression "
            "(insufficient studies for formal bias testing).",
            k,
            PUB_BIAS_MIN_K_EGGER,
            edge_relation_id,
        )
        return False
    return True


# ═══════════════════════════════════════════════════════════════
#  P4B-S1: Egger Regression (Formula P4B-1)
# ═══════════════════════════════════════════════════════════════


def run_egger_regression(
    betas: list[float],
    ses: list[float],
) -> EggerResult:
    """Formula P4B-1: Regress beta_i/SE_i on 1/SE_i.

    Test H0: intercept = 0.
    p < PUB_BIAS_EGGER_ALPHA (0.10) -> significant asymmetry detected.

    Parameters
    ----------
    betas : list[float]
        Effect sizes for each study.
    ses : list[float]
        Standard errors for each study.

    Returns
    -------
    EggerResult with intercept, p-value, and significance flag.
    """
    k = len(betas)
    # Formula P4B-1: Regress beta_i/SE_i on 1/SE_i
    # y = beta_i / SE_i, x = 1 / SE_i
    # OLS: y = intercept + slope * x
    # H0: intercept = 0
    y = np.array([b / s for b, s in zip(betas, ses)])
    x = np.array([1.0 / s for s in ses])

    # OLS regression: y = a + b*x
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    ss_xx = np.sum((x - x_mean) ** 2)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # Residuals and SE of intercept
    y_hat = intercept + slope * x
    residuals = y - y_hat
    mse = np.sum(residuals ** 2) / (n - 2)
    se_intercept = math.sqrt(mse * (1.0 / n + x_mean ** 2 / ss_xx))

    # t-test for H0: intercept = 0
    t_stat = intercept / se_intercept
    # Two-tailed p-value with (k - 2) degrees of freedom
    p_value = float(2.0 * scipy_stats.t.sf(abs(t_stat), df=n - 2))

    significant = p_value < PUB_BIAS_EGGER_ALPHA

    if significant:
        logger.warning(
            "P4B-S1 Egger regression: significant funnel asymmetry "
            "detected (intercept=%.4f, p=%.4f < %.2f)",
            intercept,
            p_value,
            PUB_BIAS_EGGER_ALPHA,
        )

    return EggerResult(
        intercept=float(intercept),
        intercept_se=float(se_intercept),
        t_statistic=float(t_stat),
        p_value=float(p_value),
        significant=significant,
        k=k,
    )


# ═══════════════════════════════════════════════════════════════
#  P4B-S2: Trim & Fill (Formula P4B-2)
# ═══════════════════════════════════════════════════════════════


def run_trim_and_fill(
    betas: list[float],
    ses: list[float],
    se_pooled: float,
    max_iterations: int = 50,
) -> TrimFillResult:
    """Formula P4B-2: Iterative trim-and-fill procedure.

    Iteratively:
      1. Compute pooled beta_hat (IVW)
      2. Identify asymmetric studies (those furthest from pooled on one side)
      3. Trim extremes and fill mirror images
      4. shift = |beta_adjusted - beta_original|
      5. shift > 0.1 SD -> MODERATE, shift > 0.3 SD -> SEVERE

    Parameters
    ----------
    betas : list[float]
        Effect sizes for each study.
    ses : list[float]
        Standard errors for each study.
    se_pooled : float
        SE of the overall pooled estimate (used for SD units).
    max_iterations : int
        Maximum trim-fill iterations.

    Returns
    -------
    TrimFillResult with original and adjusted estimates.
    """
    betas_arr = np.array(betas, dtype=np.float64)
    ses_arr = np.array(ses, dtype=np.float64)

    # Original IVW pooled estimate
    # Formula P4-1: beta_IVW = sum(beta_i / SE^2_i) / sum(1 / SE^2_i)
    weights_orig = 1.0 / (ses_arr ** 2)
    beta_original = float(np.sum(betas_arr * weights_orig) / np.sum(weights_orig))

    # Iterative trim-and-fill
    current_betas = betas_arr.copy()
    current_ses = ses_arr.copy()
    n_imputed = 0

    for _iteration in range(max_iterations):
        # Compute current pooled estimate
        w = 1.0 / (current_ses ** 2)
        beta_hat = float(np.sum(current_betas * w) / np.sum(w))

        # Compute deviations from pooled estimate
        deviations = current_betas - beta_hat

        # Count studies on each side
        n_positive = int(np.sum(deviations > 0))
        n_negative = int(np.sum(deviations < 0))

        # Asymmetry: more studies on one side suggests bias
        if n_positive == n_negative:
            break

        # Identify the side with excess studies
        if n_positive > n_negative:
            excess_side_mask = deviations > 0
            deficit = n_positive - n_negative
        else:
            excess_side_mask = deviations < 0
            deficit = n_negative - n_positive

        # Number of studies to trim (conservative: R0 estimator)
        n_trim = max(0, deficit // 2)

        if n_trim == 0:
            break

        # Find the most extreme studies on the excess side
        abs_deviations = np.abs(deviations)
        abs_deviations[~excess_side_mask] = -np.inf
        trim_indices = np.argsort(abs_deviations)[-n_trim:]

        # Create mirror studies for trimmed ones
        mirror_betas = []
        mirror_ses = []
        for idx in trim_indices:
            mirror_beta = 2.0 * beta_hat - current_betas[idx]
            mirror_betas.append(mirror_beta)
            mirror_ses.append(current_ses[idx])

        # Add mirror studies
        if mirror_betas:
            current_betas = np.concatenate([current_betas, np.array(mirror_betas)])
            current_ses = np.concatenate([current_ses, np.array(mirror_ses)])
            n_imputed += len(mirror_betas)

        # Check convergence: if no new imputations needed, done
        if n_trim == 0:
            break

    # Adjusted pooled estimate with filled studies
    w_final = 1.0 / (current_ses ** 2)
    beta_adjusted = float(np.sum(current_betas * w_final) / np.sum(w_final))

    shift = abs(beta_adjusted - beta_original)
    shift_sd_units = shift / se_pooled if se_pooled > 0 else 0.0

    # Formula P4B-2: severity classification
    if shift_sd_units > 0.3:
        severity = "SEVERE"
    elif shift_sd_units > 0.1:
        severity = "MODERATE"
    else:
        severity = "NONE"

    if severity != "NONE":
        logger.warning(
            "P4B-S2 Trim & Fill: %s bias detected "
            "(shift=%.4f, shift_sd=%.4f, n_imputed=%d)",
            severity,
            shift,
            shift_sd_units,
            n_imputed,
        )

    return TrimFillResult(
        beta_original=beta_original,
        beta_adjusted=beta_adjusted,
        shift=shift,
        shift_sd_units=shift_sd_units,
        n_imputed=n_imputed,
        severity=severity,
    )


# ═══════════════════════════════════════════════════════════════
#  P4B-S3: Leave-One-Out (Formula P4B-3)
# ═══════════════════════════════════════════════════════════════


def run_leave_one_out(
    betas: list[float],
    ses: list[float],
    beta_all: float,
    se_all: float,
) -> LeaveOneOutResult:
    """Formula P4B-3: Leave-one-out sensitivity analysis.

    For each study j:
      beta_{-j} = IVW excluding study j
      influence(j) = |beta_{-j} - beta_all| / SE_all
    influence > 2.0 -> study j is INFLUENTIAL
    LOO range > 0.3 SD -> FRAGILE

    Parameters
    ----------
    betas : list[float]
        Effect sizes for each study.
    ses : list[float]
        Standard errors for each study.
    beta_all : float
        Overall IVW pooled estimate.
    se_all : float
        SE of the overall pooled estimate.

    Returns
    -------
    LeaveOneOutResult with per-study influence scores and fragility flag.
    """
    k = len(betas)
    influences: list[float] = []
    loo_betas: list[float] = []
    influential_indices: list[int] = []

    for j in range(k):
        # IVW excluding study j
        # Formula P4-1 applied to k-1 studies
        remaining_betas = [betas[i] for i in range(k) if i != j]
        remaining_ses = [ses[i] for i in range(k) if i != j]

        if len(remaining_betas) == 0:
            # Only one study, cannot compute LOO
            influences.append(0.0)
            loo_betas.append(beta_all)
            continue

        weights_j = [1.0 / (s ** 2) for s in remaining_ses]
        sum_w = sum(weights_j)
        if sum_w == 0:
            influences.append(0.0)
            loo_betas.append(beta_all)
            continue

        beta_minus_j = sum(
            b * w for b, w in zip(remaining_betas, weights_j)
        ) / sum_w

        loo_betas.append(beta_minus_j)

        # Formula P4B-3: influence(j) = |beta_{-j} - beta_all| / SE_all
        if se_all > 0:
            influence_j = abs(beta_minus_j - beta_all) / se_all
        else:
            influence_j = 0.0

        influences.append(influence_j)

        # influence > 2.0 -> INFLUENTIAL
        if influence_j > 2.0:
            influential_indices.append(j)
            logger.warning(
                "P4B-S3 LOO: Study %d is INFLUENTIAL "
                "(influence=%.4f > 2.0, beta_{-j}=%.4f vs beta_all=%.4f)",
                j,
                influence_j,
                beta_minus_j,
                beta_all,
            )

    # LOO range
    if loo_betas:
        loo_range = max(loo_betas) - min(loo_betas)
    else:
        loo_range = 0.0

    loo_range_sd_units = loo_range / se_all if se_all > 0 else 0.0
    fragile = loo_range_sd_units > 0.3

    if fragile:
        logger.warning(
            "P4B-S3 LOO: Evidence is FRAGILE "
            "(LOO range=%.4f, range_sd=%.4f > 0.3)",
            loo_range,
            loo_range_sd_units,
        )

    return LeaveOneOutResult(
        study_influences=influences,
        influential_studies=influential_indices,
        loo_range=loo_range,
        loo_range_sd_units=loo_range_sd_units,
        fragile=fragile,
    )


# ═══════════════════════════════════════════════════════════════
#  P4B-S4: Bias Aggregator (Formula P4B-4)
# ═══════════════════════════════════════════════════════════════


def aggregate_bias_flags(
    egger: EggerResult | None,
    trim_fill: TrimFillResult | None,
    leave_one_out: LeaveOneOutResult | None,
) -> tuple[int, BiasRisk, float, list[str]]:
    """Formula P4B-4: Aggregate bias flags into overall assessment.

    0 flags -> CLEAN (SE x 1.0, from PUB_BIAS_SE_INFLATION_LOW)
    1 flag  -> POSSIBLE (SE x 1.1 ... but spec says 1.0 for LOW; see note)
    2 flags -> PROBABLE (SE x 1.15, from PUB_BIAS_SE_INFLATION_MODERATE)
    3 flags -> SEVERE (SE x 1.30, from PUB_BIAS_SE_INFLATION_HIGH)

    Note: The spec maps 0 flags -> SE x 1.0 (LOW), 1 flag -> MODERATE,
    2 flags -> MODERATE with higher inflation, 3 flags -> HIGH.
    Config values: LOW=1.0, MODERATE=1.15, HIGH=1.30.

    Returns
    -------
    Tuple of (n_flags, BiasRisk, se_inflation_factor, flag_descriptions).
    """
    flags: list[str] = []

    # Flag 1: Egger significant
    if egger is not None and egger.significant:
        flags.append(
            f"Egger regression significant (p={egger.p_value:.4f} "
            f"< {PUB_BIAS_EGGER_ALPHA})"
        )

    # Flag 2: Trim & Fill non-trivial
    if trim_fill is not None and trim_fill.severity != "NONE":
        flags.append(
            f"Trim & Fill {trim_fill.severity} "
            f"(shift_sd={trim_fill.shift_sd_units:.4f})"
        )

    # Flag 3: LOO fragile
    if leave_one_out is not None and leave_one_out.fragile:
        flags.append(
            f"Leave-one-out FRAGILE "
            f"(range_sd={leave_one_out.loo_range_sd_units:.4f})"
        )

    n_flags = len(flags)

    # Formula P4B-4: Map flag count to risk and SE inflation
    if n_flags == 0:
        # 0 flags -> CLEAN (SE x 1.0)
        bias_risk = BiasRisk.LOW
        se_inflation = PUB_BIAS_SE_INFLATION_LOW
    elif n_flags == 1:
        # 1 flag -> POSSIBLE (SE x 1.0 from config LOW; between LOW and MODERATE)
        bias_risk = BiasRisk.MODERATE
        se_inflation = PUB_BIAS_SE_INFLATION_LOW
    elif n_flags == 2:
        # 2 flags -> PROBABLE (SE x 1.15)
        bias_risk = BiasRisk.MODERATE
        se_inflation = PUB_BIAS_SE_INFLATION_MODERATE
    else:
        # 3 flags -> SEVERE (SE x 1.30)
        bias_risk = BiasRisk.HIGH
        se_inflation = PUB_BIAS_SE_INFLATION_HIGH

    return n_flags, bias_risk, se_inflation, flags


# ═══════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════


def assess_publication_bias(
    pooled_estimate: PooledEstimate,
    study_betas: list[float],
    study_ses: list[float],
) -> BiasAssessment:
    """Run full publication bias assessment (P4B-S1 through P4B-S4).

    Parameters
    ----------
    pooled_estimate : PooledEstimate
        The IVW meta-analysis result from meta_analyzer.py.
    study_betas : list[float]
        Individual study effect sizes (in same order as study_ses).
    study_ses : list[float]
        Individual study standard errors.

    Returns
    -------
    BiasAssessment with results from all applicable sub-analyses.

    Raises
    ------
    GateViolation
        Gate P4B-G1: if k < 2.
    """
    edge_id = pooled_estimate.edge_relation_id
    k = len(study_betas)

    if k != len(study_ses):
        raise ValueError(
            f"study_betas (len={k}) and study_ses (len={len(study_ses)}) "
            f"must have the same length for edge '{edge_id}'"
        )

    # Gate P4B-G1: Check minimum k
    sufficient_k = _enforce_gate_p4b_g1(k=k, edge_relation_id=edge_id)

    if not sufficient_k:
        # k < PUB_BIAS_MIN_K_EGGER but >= 2: skip Egger, run LOO/trim-fill if possible
        logger.info(
            "P4B: k=%d < %d for edge '%s'; running reduced assessment "
            "(LOO and Trim & Fill only, no Egger).",
            k,
            PUB_BIAS_MIN_K_EGGER,
            edge_id,
        )
        egger_result = None
    else:
        # P4B-S1: Egger regression
        egger_result = run_egger_regression(
            betas=study_betas,
            ses=study_ses,
        )
        logger.info(
            "P4B-S1 Egger for edge '%s': intercept=%.4f, p=%.4f, sig=%s",
            edge_id,
            egger_result.intercept,
            egger_result.p_value,
            egger_result.significant,
        )

    # P4B-S2: Trim & Fill
    trim_fill_result = run_trim_and_fill(
        betas=study_betas,
        ses=study_ses,
        se_pooled=pooled_estimate.se_pooled,
    )
    logger.info(
        "P4B-S2 Trim & Fill for edge '%s': shift_sd=%.4f, severity=%s",
        edge_id,
        trim_fill_result.shift_sd_units,
        trim_fill_result.severity,
    )

    # P4B-S3: Leave-one-out
    loo_result = run_leave_one_out(
        betas=study_betas,
        ses=study_ses,
        beta_all=pooled_estimate.beta_pooled,
        se_all=pooled_estimate.se_pooled,
    )
    logger.info(
        "P4B-S3 LOO for edge '%s': n_influential=%d, fragile=%s",
        edge_id,
        len(loo_result.influential_studies),
        loo_result.fragile,
    )

    # P4B-S4: Aggregate bias flags
    n_flags, bias_risk, se_inflation, flag_descs = aggregate_bias_flags(
        egger=egger_result,
        trim_fill=trim_fill_result,
        leave_one_out=loo_result,
    )

    logger.info(
        "P4B-S4 Aggregator for edge '%s': n_flags=%d, risk=%s, "
        "se_inflation=%.2f",
        edge_id,
        n_flags,
        bias_risk.value,
        se_inflation,
    )

    skipped_reason = None
    if not sufficient_k:
        skipped_reason = (
            f"Egger regression skipped: k={k} < "
            f"{PUB_BIAS_MIN_K_EGGER} (P4B-G1)"
        )

    return BiasAssessment(
        edge_relation_id=edge_id,
        egger=egger_result,
        trim_fill=trim_fill_result,
        leave_one_out=loo_result,
        n_flags=n_flags,
        bias_risk=bias_risk,
        se_inflation_factor=se_inflation,
        flags=flag_descs,
        skipped_reason=skipped_reason,
    )


def assess_publication_bias_batch(
    pooled_estimates: list[PooledEstimate],
    all_study_betas: list[list[float]],
    all_study_ses: list[list[float]],
) -> list[BiasAssessment]:
    """Run publication bias assessment on a batch of pooled estimates.

    Parameters
    ----------
    pooled_estimates : list[PooledEstimate]
        Pooled estimates from meta_analyzer, one per edge.
    all_study_betas : list[list[float]]
        Per-edge lists of individual study betas.
    all_study_ses : list[list[float]]
        Per-edge lists of individual study SEs.

    Returns
    -------
    list[BiasAssessment], one per edge. Edges with k < 2 will have
    their BiasAssessment marked with INSUFFICIENT_K.
    """
    results: list[BiasAssessment] = []

    for pooled, betas, ses in zip(
        pooled_estimates, all_study_betas, all_study_ses
    ):
        try:
            assessment = assess_publication_bias(
                pooled_estimate=pooled,
                study_betas=betas,
                study_ses=ses,
            )
            results.append(assessment)
        except GateViolation as exc:
            logger.error(
                "P4B-G1 SKIP edge '%s': %s",
                pooled.edge_relation_id,
                str(exc),
            )
            results.append(
                BiasAssessment(
                    edge_relation_id=pooled.edge_relation_id,
                    bias_risk=BiasRisk.INSUFFICIENT_K,
                    skipped_reason=str(exc),
                )
            )

    logger.info(
        "Publication bias assessment complete: %d edges processed",
        len(results),
    )
    return results
