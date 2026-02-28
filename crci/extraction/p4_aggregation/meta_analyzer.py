# VERIFIED: formulas P4-1, P4-2, P4-3, P4-3b match spec lines 1230-1316
# VERIFIED: imports — all modules exist (shared.config, shared.models.intermediate_states)
# VERIFIED: backward wiring — reads ResolvedEvidence from double_counting.py
# VERIFIED: forward wiring — writes PooledEstimate + MetaAnalysisResult for prior_selector.py / edge_writer.py
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gates P4-G1, P4-G2 raise on failure
"""
Component: SYS_EXTRACTION.EX-P4.P4-MA
File: extraction/p4_aggregation/meta_analyzer.py
Spec: SYS_EXTRACTION_COMPLETE.md lines 1226-1316
Formulas: P4-1, P4-2, P4-3, P4-3b
Reads: ResolvedEvidence (from double_counting.py)
       study_annotations_v1 (category='limitation_unmeasured_confounder')
       study_annotations_v1 (category='null_finding_context')
Writes: PooledEstimate + MetaAnalysisResult (consumed by prior_selector.py, edge_writer.py)
Gates: P4-G1 (all edges have method assigned), P4-G2 (no NaN in beta/SE)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from crci.shared import config
from crci.shared.models.enums import AggregationMethod, AnnotationCategory, MetaSourceFlag
from crci.shared.models.intermediate_states import (
    GateViolation,
    HarmonizedClaim,
    PooledEstimate,
    ResolvedEvidence,
    StudyWeight,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  OUTPUT TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class AnnotationInfluence:
    """Annotation-derived adjustments for a single edge.

    Captures sigma_sq_structural from limitation_unmeasured_confounder
    and p_inclusion_adjustment from null_finding_context.
    """

    sigma_sq_structural: float
    p_inclusion_adjustment: float
    confounder_annotation_count: int = 0
    null_finding_annotation_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class MetaAnalysisResult:
    """Full output of the meta-analyzer for a single edge.

    Bundles PooledEstimate with annotation influence and P_inclusion.
    """

    pooled_estimate: PooledEstimate
    annotation_influence: AnnotationInfluence
    p_inclusion_raw: float
    p_inclusion_final: float
    sign_conflict_detected: bool = False


# ═══════════════════════════════════════════════════════════════
#  ANNOTATION TYPES (for DB interface)
# ═══════════════════════════════════════════════════════════════


@dataclass
class AnnotationRecord:
    """Represents a single annotation row from study_annotations_v1.

    Used as in-memory representation of DB rows.
    """

    annotation_id: str
    category: str
    target_edge_relation_id: str
    reconciled_confidence: float = 0.0
    severity: str | None = None  # moderate, high, critical
    powered_adequately: bool | None = None
    content: str = ""


# ═══════════════════════════════════════════════════════════════
#  MATH PRIMITIVES
# ═══════════════════════════════════════════════════════════════


def logistic(x: float) -> float:
    """Logistic (sigmoid) function: 1 / (1 + exp(-x)).

    Numerically stable implementation.
    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        exp_x = math.exp(x)
        return exp_x / (1.0 + exp_x)


def logit(p: float) -> float:
    """Logit function: ln(p / (1 - p)).

    Raises ValueError if p is not in (0, 1).
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError(f"logit requires p in (0, 1), got {p}")
    return math.log(p / (1.0 - p))


# ═══════════════════════════════════════════════════════════════
#  P4-MA-b: IVW COMPUTATION
# ═══════════════════════════════════════════════════════════════


def compute_ivw_fixed(
    betas: list[float],
    ses: list[float],
) -> tuple[float, float, list[float]]:
    """Fixed-effects IVW meta-analysis.

    Formula P4-1: beta_IVW = sum(beta_i / SE_i^2) / sum(1 / SE_i^2)
                  SE_pooled = 1 / sqrt(sum(1 / SE_i^2))

    Args:
        betas: Effect sizes per study.
        ses: Standard errors per study.

    Returns:
        (beta_pooled, se_pooled, weights)
    """
    # Formula P4-1: beta_IVW = sum(beta_i / SE_i^2) / sum(1 / SE_i^2)
    weights = [1.0 / (se ** 2) for se in ses]
    sum_weights = sum(weights)
    beta_pooled = sum(b / (se ** 2) for b, se in zip(betas, ses)) / sum_weights
    se_pooled = 1.0 / math.sqrt(sum_weights)
    return beta_pooled, se_pooled, weights


def compute_cochran_q(
    betas: list[float],
    ses: list[float],
    beta_fe: float,
) -> float:
    """Cochran's Q statistic for heterogeneity.

    Q = sum(w_i * (beta_i - beta_FE)^2) where w_i = 1/SE_i^2
    """
    q = sum(
        (1.0 / (se ** 2)) * (b - beta_fe) ** 2
        for b, se in zip(betas, ses)
    )
    return q


def compute_i_squared(q: float, k: int) -> float:
    """I-squared heterogeneity statistic.

    I^2 = max(0, (Q - (k-1)) / Q) * 100

    Args:
        q: Cochran's Q statistic.
        k: Number of studies.

    Returns:
        I-squared as percentage (0-100).
    """
    if k < 2 or q == 0.0:
        return 0.0
    # Formula: I^2 = max(0, (Q - (k-1)) / Q) * 100
    i_sq = max(0.0, (q - (k - 1)) / q) * 100.0
    return i_sq


def compute_tau_squared_dl(
    betas: list[float],
    ses: list[float],
    beta_fe: float,
) -> float:
    """DerSimonian-Laird estimator for between-study variance tau^2.

    Formula P4-2:
        Q = sum(w_i * (beta_i - beta_FE)^2)
        tau^2 = max(0, (Q - (k-1)) / (sum_w - sum_w2 / sum_w))

    where w_i = 1/SE_i^2.

    Args:
        betas: Effect sizes per study.
        ses: Standard errors per study.
        beta_fe: Fixed-effects pooled estimate.

    Returns:
        tau_squared (non-negative).
    """
    k = len(betas)
    if k < 2:
        return 0.0

    weights = [1.0 / (se ** 2) for se in ses]
    sum_w = sum(weights)
    sum_w2 = sum(w ** 2 for w in weights)

    # Formula P4-2: Q = sum(w_i * (beta_i - beta_FE)^2)
    q = sum(w * (b - beta_fe) ** 2 for w, b in zip(weights, betas))

    # Formula P4-2: tau^2 = max(0, (Q - (k-1)) / (sum_w - sum_w2 / sum_w))
    denominator = sum_w - sum_w2 / sum_w
    if denominator <= 0.0:
        return 0.0
    tau_sq = max(0.0, (q - (k - 1)) / denominator)
    return tau_sq


def compute_ivw_random(
    betas: list[float],
    ses: list[float],
    tau_squared: float,
) -> tuple[float, float, list[float]]:
    """Random-effects IVW meta-analysis using DerSimonian-Laird tau^2.

    Formula P4-2: beta_RE = sum(beta_i / (SE_i^2 + tau^2)) / sum(1 / (SE_i^2 + tau^2))

    Args:
        betas: Effect sizes per study.
        ses: Standard errors per study.
        tau_squared: Between-study variance from DL estimator.

    Returns:
        (beta_pooled, se_pooled, weights)
    """
    # Formula P4-2: w*_i = 1 / (SE_i^2 + tau^2)
    weights = [1.0 / (se ** 2 + tau_squared) for se in ses]
    sum_weights = sum(weights)
    beta_pooled = sum(
        b / (se ** 2 + tau_squared) for b, se in zip(betas, ses)
    ) / sum_weights
    se_pooled = 1.0 / math.sqrt(sum_weights)
    return beta_pooled, se_pooled, weights


# ═══════════════════════════════════════════════════════════════
#  P4-MA-c: ANNOTATION CONSUMPTION
# ═══════════════════════════════════════════════════════════════


def compute_sigma_sq_structural(
    annotations: list[AnnotationRecord],
    edge_relation_id: str,
) -> float:
    """Compute annotation-informed sigma^2_structural per edge.

    Spec: SYS_EX lines 1241-1248 (P4-MA-c)
    sigma_sq_structural = SIGMA_SQ_STRUCTURAL_DEFAULT + sum(severity_weight * reconciled_confidence)
    CEILING: sigma_sq_structural <= SIGMA_SQ_STRUCTURAL_CEILING

    Args:
        annotations: Annotations with category='limitation_unmeasured_confounder'
                    targeting this edge.
        edge_relation_id: Edge identifier for logging.

    Returns:
        sigma_sq_structural (clamped to ceiling).
    """
    sigma_sq_adj = 0.0

    for ann in annotations:
        severity = ann.severity
        if severity is None:
            logger.warning(
                "Edge %s: annotation %s has no severity, skipping for sigma_sq_adj",
                edge_relation_id,
                ann.annotation_id,
            )
            continue

        severity_lower = severity.lower()
        severity_weight = config.ANNOTATION_SEVERITY_WEIGHTS.get(severity_lower)
        if severity_weight is None:
            logger.warning(
                "Edge %s: annotation %s has unknown severity '%s', skipping",
                edge_relation_id,
                ann.annotation_id,
                severity,
            )
            continue

        # P4-MA-c: sigma_sq_adj += severity_weight * reconciled_confidence
        sigma_sq_adj += severity_weight * ann.reconciled_confidence

    # P4-MA-c: sigma_sq_structural = DEFAULT + sum(adj)
    sigma_sq = config.SIGMA_SQ_STRUCTURAL_DEFAULT + sigma_sq_adj

    # P4-MA-c: CEILING: sigma_sq_structural <= SIGMA_SQ_STRUCTURAL_CEILING
    if sigma_sq > config.SIGMA_SQ_STRUCTURAL_CEILING:
        logger.info(
            "Edge %s: sigma_sq_structural %.4f exceeds ceiling %.4f, clamping",
            edge_relation_id,
            sigma_sq,
            config.SIGMA_SQ_STRUCTURAL_CEILING,
        )
        sigma_sq = config.SIGMA_SQ_STRUCTURAL_CEILING

    if not annotations:
        logger.info(
            "Edge %s: sigma_sq_structural defaulting to %.4f "
            "-- no limitation_unmeasured_confounder annotations",
            edge_relation_id,
            config.SIGMA_SQ_STRUCTURAL_DEFAULT,
        )

    return sigma_sq


def compute_p_inclusion_adjustment(
    annotations: list[AnnotationRecord],
    edge_relation_id: str,
) -> float:
    """Compute logit-scale P_inclusion adjustment from null_finding_context annotations.

    Spec: SYS_EX lines 1250-1254 (P4-MA-c)
    Formula P4-3b:
        For each annotation with powered_adequately=true: adj += P4_3B_NULL_FINDING_POWERED_ADJ
        p_inclusion_adjustment = clamp(sum(adj), -P_INCLUSION_ADJ_CAP, +P_INCLUSION_ADJ_CAP)

    Args:
        annotations: Annotations with category='null_finding_context'
                    targeting this edge.
        edge_relation_id: Edge identifier for logging.

    Returns:
        p_inclusion_adjustment on logit scale, clamped to [-1.0, +1.0].
    """
    adj_total = 0.0

    for ann in annotations:
        # P4-MA-c: IF powered_adequately=true -> adj += -0.3
        if ann.powered_adequately is True:
            adj_total += config.P4_3B_NULL_FINDING_POWERED_ADJ
            logger.debug(
                "Edge %s: null_finding annotation %s (powered_adequately=true) "
                "adds %.2f to p_inclusion_adjustment",
                edge_relation_id,
                ann.annotation_id,
                config.P4_3B_NULL_FINDING_POWERED_ADJ,
            )

    # P4-MA-c: clamp(sum adj, -P_INCLUSION_ADJ_CAP, +P_INCLUSION_ADJ_CAP)
    adjustment = max(
        -config.P_INCLUSION_ADJ_CAP,
        min(config.P_INCLUSION_ADJ_CAP, adj_total),
    )

    if not annotations:
        logger.info(
            "Edge %s: p_inclusion_adjustment = 0.0 "
            "-- no null_finding_context annotations",
            edge_relation_id,
        )

    return adjustment


def compute_annotation_influence(
    confounder_annotations: list[AnnotationRecord],
    null_finding_annotations: list[AnnotationRecord],
    edge_relation_id: str,
) -> AnnotationInfluence:
    """Compute all annotation-derived adjustments for an edge.

    Combines sigma_sq_structural and p_inclusion_adjustment.
    """
    sigma_sq = compute_sigma_sq_structural(confounder_annotations, edge_relation_id)
    p_adj = compute_p_inclusion_adjustment(null_finding_annotations, edge_relation_id)

    notes: list[str] = []
    if confounder_annotations:
        notes.append(
            f"sigma_sq_structural adjusted by {len(confounder_annotations)} "
            f"confounder annotation(s) to {sigma_sq:.4f}"
        )
    if null_finding_annotations:
        notes.append(
            f"p_inclusion_adjustment = {p_adj:.4f} from "
            f"{len(null_finding_annotations)} null_finding annotation(s)"
        )

    return AnnotationInfluence(
        sigma_sq_structural=sigma_sq,
        p_inclusion_adjustment=p_adj,
        confounder_annotation_count=len(confounder_annotations),
        null_finding_annotation_count=len(null_finding_annotations),
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════════
#  P4-3: P_INCLUSION
# ═══════════════════════════════════════════════════════════════


def compute_p_inclusion(
    k: int,
    beta_pooled: float,
    se_pooled: float,
    has_rct: bool,
    p_inclusion_adjustment: float = 0.0,
) -> tuple[float, float]:
    """Compute inclusion probability for an edge.

    Formula P4-3: P_incl = logistic(-0.5 + 1.2*ln(k+1) + 0.4*Z + 0.6*1_RCT)
        where Z = |beta_pooled| / se_pooled

    Formula P4-3b: P_final = logistic(logit(P_formula) + p_inclusion_adjustment)

    Args:
        k: Number of evidence records for this edge.
        beta_pooled: Pooled effect size.
        se_pooled: Pooled standard error.
        has_rct: Whether any contributing study is an RCT.
        p_inclusion_adjustment: Logit-scale adjustment from annotations.

    Returns:
        (p_inclusion_raw, p_inclusion_final)
    """
    # Formula P4-3: Z = |beta_pooled| / se_pooled
    if se_pooled > 0.0:
        z_score = abs(beta_pooled) / se_pooled
    else:
        z_score = 0.0

    rct_indicator = 1.0 if has_rct else 0.0

    # Formula P4-3: P_incl = logistic(-0.5 + 1.2*ln(k+1) + 0.4*Z + 0.6*1_RCT)
    linear_predictor = (
        config.P4_3_INTERCEPT
        + config.P4_3_LN_K_COEFF * math.log(k + 1)
        + config.P4_3_Z_COEFF * z_score
        + config.P4_3_RCT_COEFF * rct_indicator
    )
    p_raw = logistic(linear_predictor)

    # Formula P4-3b: P_final = logistic(logit(P_formula) + p_inclusion_adjustment)
    # Clamp p_raw away from 0 and 1 for logit stability
    p_raw_clamped = max(config.P_INCLUSION_MIN, min(1.0 - config.P_INCLUSION_MIN, p_raw))
    logit_p = logit(p_raw_clamped)
    p_final = logistic(logit_p + p_inclusion_adjustment)

    # Enforce floor from config
    p_final = max(config.P_INCLUSION_MIN, p_final)

    logger.debug(
        "P_inclusion: k=%d, Z=%.3f, RCT=%s, p_raw=%.4f, adj=%.4f, p_final=%.4f",
        k,
        z_score,
        has_rct,
        p_raw,
        p_inclusion_adjustment,
        p_final,
    )

    return p_raw, p_final


# ═══════════════════════════════════════════════════════════════
#  P4-MA-a: AGGREGATION DECISION TREE
# ═══════════════════════════════════════════════════════════════


def _has_sign_conflict_among_high_quality(claims: list[HarmonizedClaim]) -> bool:
    """Check for sign conflict among HIGH-quality claims.

    Spec: P4-MA-a — Sign conflict among HIGH-quality -> BLOCKED.
    """
    high_quality_betas: list[float] = []
    for claim in claims:
        if claim.quality_rating and claim.quality_rating.upper() == "HIGH":
            high_quality_betas.append(claim.harmonized_beta)

    if len(high_quality_betas) < 2:
        return False

    has_positive = any(b > 0.0 for b in high_quality_betas)
    has_negative = any(b < 0.0 for b in high_quality_betas)
    return has_positive and has_negative


def _has_rct_study(claims: list[HarmonizedClaim]) -> bool:
    """Check if any contributing claim is from an RCT design.

    Uses study_id prefix or other indicators. For robustness,
    checks harmonized_claim fields available.
    """
    for claim in claims:
        # In the harmonized pipeline, RCT studies may be identified
        # by design metadata. Check available fields.
        study_id = claim.study_id.lower() if claim.study_id else ""
        if "rct" in study_id:
            return True
    return False


def select_aggregation_method(
    k: int,
    i_squared: float,
    claims: list[HarmonizedClaim],
    edge_relation_id: str,
) -> str:
    """Select aggregation method using the P4-MA-a decision tree.

    Spec: SYS_EX lines 1229-1233 (P4-MA-a)
        k=0 -> BLOCKED
        k=1 -> DIRECT (use single study)
        k>=2:
            I^2 < 50% -> IVW_FIXED
            50-75% -> STRATIFIED or IVW_RANDOM
            >= 75% -> STRATIFIED or SINGLE_BEST
        Sign conflict among HIGH-quality -> BLOCKED

    Args:
        k: Number of independent claims.
        i_squared: I-squared heterogeneity statistic.
        claims: Harmonized claims for this edge.
        edge_relation_id: Edge identifier for logging.

    Returns:
        Aggregation method string matching AggregationMethod enum values.
    """
    # k=0 -> BLOCKED
    if k == 0:
        logger.info("Edge %s: k=0 -> BLOCKED", edge_relation_id)
        return "BLOCKED"

    # Sign conflict among HIGH-quality -> BLOCKED
    if _has_sign_conflict_among_high_quality(claims):
        logger.warning(
            "Edge %s: sign conflict among HIGH-quality claims -> BLOCKED",
            edge_relation_id,
        )
        return "BLOCKED"

    # k=1 -> DIRECT
    if k == 1:
        logger.info("Edge %s: k=1 -> DIRECT", edge_relation_id)
        return "DIRECT"

    # k>=2: decision based on I^2
    if i_squared < config.HETEROGENEITY_MODERATE_THRESHOLD:
        # I^2 < 50% -> IVW_FIXED
        logger.info(
            "Edge %s: k=%d, I^2=%.1f%% < %.1f%% -> IVW_fixed",
            edge_relation_id,
            k,
            i_squared,
            config.HETEROGENEITY_MODERATE_THRESHOLD,
        )
        return AggregationMethod.IVW_FIXED
    elif i_squared < config.HETEROGENEITY_HIGH_THRESHOLD:
        # 50-75% -> IVW_RANDOM (using STRATIFIED would require stratification logic)
        logger.info(
            "Edge %s: k=%d, I^2=%.1f%% (moderate) -> IVW_random",
            edge_relation_id,
            k,
            i_squared,
        )
        return AggregationMethod.IVW_RANDOM
    else:
        # >= 75% -> SINGLE_BEST (stratification not available in v1)
        logger.info(
            "Edge %s: k=%d, I^2=%.1f%% >= %.1f%% -> single_best",
            edge_relation_id,
            k,
            i_squared,
            config.HETEROGENEITY_HIGH_THRESHOLD,
        )
        return AggregationMethod.SINGLE_BEST


def _select_single_best(claims: list[HarmonizedClaim]) -> HarmonizedClaim:
    """Select the single best claim when I^2 >= 75%.

    Selects the claim with the smallest SE (most precise).
    """
    best = min(
        claims,
        key=lambda c: c.harmonized_se if c.harmonized_se is not None else float("inf"),
    )
    return best


# ═══════════════════════════════════════════════════════════════
#  R4.1: PUBLISHED HETEROGENEITY PASSTHROUGH
# ═══════════════════════════════════════════════════════════════


def _use_published_heterogeneity(
    claims: list[HarmonizedClaim],
) -> dict | None:
    """Extract published heterogeneity from MA claim when available.

    When the aggregation pipeline uses an MA pooled estimate (DCR decision),
    we should use the MA's published I²/τ² rather than re-estimating from
    constituent studies. Re-estimation from a mix of MA-pooled and primary
    estimates is methodologically incoherent.

    Args:
        claims: Claims for a single edge (after DCR resolution).

    Returns:
        Heterogeneity dict with I2, tau2, prediction_interval keys,
        or None if no published heterogeneity available.
    """
    for claim in claims:
        if (
            claim.meta_source_flag == MetaSourceFlag.POOLED_ESTIMATE.value
            and claim.heterogeneity_json
            and isinstance(claim.heterogeneity_json, dict)
        ):
            het = claim.heterogeneity_json
            logger.info(
                "R4-HET: Using published heterogeneity from MA %s: "
                "I²=%.2f%%, τ²=%.4f",
                claim.study_id,
                het.get("I2", -1),
                het.get("tau2", -1),
            )
            return het
    return None


# ═══════════════════════════════════════════════════════════════
#  CORE META-ANALYSIS: pool_evidence
# ═══════════════════════════════════════════════════════════════


def pool_evidence(
    resolved: ResolvedEvidence,
    confounder_annotations: list[AnnotationRecord] | None = None,
    null_finding_annotations: list[AnnotationRecord] | None = None,
) -> MetaAnalysisResult:
    """Run full meta-analysis for one edge.

    Implements the complete P4-MA pipeline:
    1. Extract betas/SEs from claims
    2. Compute IVW fixed-effects (P4-1)
    3. Compute DL tau^2 and I^2 (P4-2)
    4. Select aggregation method (P4-MA-a decision tree)
    5. Pool using selected method
    6. Compute annotation influence (P4-MA-c)
    7. Compute P_inclusion (P4-3, P4-3b)

    Args:
        resolved: Evidence after double-counting resolution.
        confounder_annotations: limitation_unmeasured_confounder annotations for this edge.
        null_finding_annotations: null_finding_context annotations for this edge.

    Returns:
        MetaAnalysisResult containing PooledEstimate and annotation influence.

    Raises:
        GateViolation: If P4-G2 (NaN in beta/SE) is violated.
    """
    if confounder_annotations is None:
        confounder_annotations = []
    if null_finding_annotations is None:
        null_finding_annotations = []

    edge_id = resolved.edge_relation_id
    claims = resolved.claims
    k = resolved.k

    # Compute annotation influence (P4-MA-c)
    annotation_influence = compute_annotation_influence(
        confounder_annotations,
        null_finding_annotations,
        edge_id,
    )

    # Handle k=0 case: BLOCKED
    if k == 0 or not claims:
        logger.info("Edge %s: k=0, no claims -> BLOCKED", edge_id)
        pooled = PooledEstimate(
            edge_relation_id=edge_id,
            beta_pooled=0.0,
            se_pooled=0.0,
            tau_squared=0.0,
            i_squared=0.0,
            k=0,
            total_n=resolved.total_n,
            aggregation_method="BLOCKED",
            individual_weights=[],
            study_weights=[],
        )
        return MetaAnalysisResult(
            pooled_estimate=pooled,
            annotation_influence=annotation_influence,
            p_inclusion_raw=0.0,
            p_inclusion_final=0.0,
            sign_conflict_detected=False,
        )

    # Extract betas and SEs from claims, filtering out claims with missing SE
    valid_claims: list[HarmonizedClaim] = []
    betas: list[float] = []
    ses: list[float] = []
    for claim in claims:
        if claim.harmonized_se is not None and claim.harmonized_se > 0.0:
            valid_claims.append(claim)
            betas.append(claim.harmonized_beta)
            ses.append(claim.harmonized_se)
        else:
            logger.warning(
                "Edge %s: claim %s has missing or zero SE (%.4s), excluding from pooling",
                edge_id,
                claim.ler_id,
                claim.harmonized_se,
            )

    effective_k = len(valid_claims)

    # Handle case where all claims had missing SE
    if effective_k == 0:
        logger.warning(
            "Edge %s: all %d claims had missing/zero SE -> BLOCKED",
            edge_id,
            k,
        )
        pooled = PooledEstimate(
            edge_relation_id=edge_id,
            beta_pooled=0.0,
            se_pooled=0.0,
            tau_squared=0.0,
            i_squared=0.0,
            k=0,
            total_n=resolved.total_n,
            aggregation_method="BLOCKED",
            individual_weights=[],
            study_weights=[],
        )
        return MetaAnalysisResult(
            pooled_estimate=pooled,
            annotation_influence=annotation_influence,
            p_inclusion_raw=0.0,
            p_inclusion_final=0.0,
            sign_conflict_detected=False,
        )

    # k=1: DIRECT (use single study)
    if effective_k == 1:
        method = "DIRECT"
        beta_pooled = betas[0]
        se_pooled = ses[0]
        tau_sq = 0.0
        i_sq = 0.0
        weights = [1.0]
        # R1 provenance: single study gets weight 1.0
        _study_weights = [
            StudyWeight(
                ler_id=valid_claims[0].ler_id,
                study_id=valid_claims[0].study_id,
                weight=1.0,
                weight_normalized=1.0,
                beta=betas[0],
                se=ses[0],
            )
        ]
        logger.info(
            "Edge %s: k=1 -> DIRECT, beta=%.4f, SE=%.4f",
            edge_id,
            beta_pooled,
            se_pooled,
        )
    else:
        # R4.1: Check for published heterogeneity from MA claim
        published_het = _use_published_heterogeneity(valid_claims)

        # k>=2: Run IVW fixed-effects first to get beta_FE
        # Formula P4-1: beta_IVW = sum(beta_i / SE_i^2) / sum(1 / SE_i^2)
        beta_fe, se_fe, weights_fe = compute_ivw_fixed(betas, ses)

        # Compute heterogeneity statistics
        q = compute_cochran_q(betas, ses, beta_fe)
        i_sq = compute_i_squared(q, effective_k)

        # Formula P4-2: tau^2 via DerSimonian-Laird
        tau_sq = compute_tau_squared_dl(betas, ses, beta_fe)

        # R4.1: Override with published heterogeneity when available
        if published_het:
            if "I2" in published_het:
                i_sq = float(published_het["I2"])
                logger.info(
                    "R4-HET: Overriding computed I²=%.2f%% with published I²=%.2f%%",
                    compute_i_squared(q, effective_k), i_sq,
                )
            if "tau2" in published_het:
                tau_sq = float(published_het["tau2"])
                logger.info(
                    "R4-HET: Overriding computed τ²=%.4f with published τ²=%.4f",
                    compute_tau_squared_dl(betas, ses, beta_fe), tau_sq,
                )

        # Check for sign conflict among HIGH-quality
        sign_conflict = _has_sign_conflict_among_high_quality(valid_claims)

        # Select aggregation method (P4-MA-a decision tree)
        method = select_aggregation_method(effective_k, i_sq, valid_claims, edge_id)

        if method == "BLOCKED":
            pooled = PooledEstimate(
                edge_relation_id=edge_id,
                beta_pooled=0.0,
                se_pooled=0.0,
                tau_squared=tau_sq,
                i_squared=i_sq,
                k=effective_k,
                total_n=resolved.total_n,
                aggregation_method="BLOCKED",
                individual_weights=[],
                study_weights=[],
            )
            return MetaAnalysisResult(
                pooled_estimate=pooled,
                annotation_influence=annotation_influence,
                p_inclusion_raw=0.0,
                p_inclusion_final=0.0,
                sign_conflict_detected=sign_conflict,
            )

        if method == AggregationMethod.IVW_FIXED:
            beta_pooled = beta_fe
            se_pooled = se_fe
            weights = weights_fe
        elif method == AggregationMethod.IVW_RANDOM:
            # Formula P4-2: random-effects with DL tau^2
            beta_pooled, se_pooled, weights = compute_ivw_random(betas, ses, tau_sq)
        elif method == AggregationMethod.SINGLE_BEST:
            best_claim = _select_single_best(valid_claims)
            beta_pooled = best_claim.harmonized_beta
            se_pooled = (
                best_claim.harmonized_se
                if best_claim.harmonized_se is not None
                else 0.0
            )
            weights = [
                1.0 if c.ler_id == best_claim.ler_id else 0.0
                for c in valid_claims
            ]
        else:
            # Fallback to IVW_random for safety
            logger.warning(
                "Edge %s: unexpected method '%s', falling back to IVW_random",
                edge_id,
                method,
            )
            beta_pooled, se_pooled, weights = compute_ivw_random(betas, ses, tau_sq)
            method = AggregationMethod.IVW_RANDOM

    # ─── Gate P4-G2: No NaN in beta or SE ─────────────────────
    if math.isnan(beta_pooled):
        raise GateViolation(
            "P4-G2",
            f"Edge {edge_id}: beta_pooled is NaN "
            f"(method={method}, k={effective_k})",
            {"edge_relation_id": edge_id, "method": method, "k": effective_k},
        )
    if math.isnan(se_pooled):
        raise GateViolation(
            "P4-G2",
            f"Edge {edge_id}: se_pooled is NaN "
            f"(method={method}, k={effective_k})",
            {"edge_relation_id": edge_id, "method": method, "k": effective_k},
        )

    # Compute P_inclusion (P4-3, P4-3b)
    has_rct = _has_rct_study(valid_claims)
    p_raw, p_final = compute_p_inclusion(
        k=effective_k,
        beta_pooled=beta_pooled,
        se_pooled=se_pooled,
        has_rct=has_rct,
        p_inclusion_adjustment=annotation_influence.p_inclusion_adjustment,
    )

    # R1 provenance: build identified study weights for k>=2 paths
    # (_study_weights already built for k=1 DIRECT path above)
    if effective_k >= 2:
        sum_w = sum(weights) if weights else 1.0
        _study_weights = [
            StudyWeight(
                ler_id=c.ler_id,
                study_id=c.study_id,
                weight=w,
                weight_normalized=w / sum_w if sum_w > 0 else 0.0,
                beta=c.harmonized_beta,
                se=c.harmonized_se if c.harmonized_se is not None else 0.0,
            )
            for c, w in zip(valid_claims, weights)
        ]

    pooled = PooledEstimate(
        edge_relation_id=edge_id,
        beta_pooled=beta_pooled,
        se_pooled=se_pooled,
        tau_squared=tau_sq if effective_k >= 2 else 0.0,
        i_squared=i_sq if effective_k >= 2 else 0.0,
        k=effective_k,
        total_n=resolved.total_n,
        aggregation_method=method,
        individual_weights=weights,
        study_weights=_study_weights,
    )

    sign_conflict = _has_sign_conflict_among_high_quality(valid_claims) if effective_k >= 2 else False

    return MetaAnalysisResult(
        pooled_estimate=pooled,
        annotation_influence=annotation_influence,
        p_inclusion_raw=p_raw,
        p_inclusion_final=p_final,
        sign_conflict_detected=sign_conflict,
    )


# ═══════════════════════════════════════════════════════════════
#  BATCH META-ANALYSIS: analyze_all_edges
# ═══════════════════════════════════════════════════════════════


def analyze_all_edges(
    resolved_evidence_list: list[ResolvedEvidence],
    annotations_by_edge: dict[str, list[AnnotationRecord]] | None = None,
) -> list[MetaAnalysisResult]:
    """Run meta-analysis across all edges.

    Gate P4-G1: All edges must have a method assigned (no None methods).

    Args:
        resolved_evidence_list: Resolved evidence per edge from double_counting.py.
        annotations_by_edge: Annotations keyed by edge_relation_id.
            Expected to contain both limitation_unmeasured_confounder
            and null_finding_context categories.

    Returns:
        List of MetaAnalysisResult, one per edge.

    Raises:
        GateViolation: If P4-G1 (method not assigned for all edges) or
                      P4-G2 (NaN in beta/SE) fails.
    """
    if annotations_by_edge is None:
        annotations_by_edge = {}

    results: list[MetaAnalysisResult] = []

    for resolved in resolved_evidence_list:
        edge_id = resolved.edge_relation_id

        # Partition annotations by category for this edge
        edge_annotations = annotations_by_edge.get(edge_id, [])
        confounder_anns = [
            a
            for a in edge_annotations
            if a.category == AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER
        ]
        null_finding_anns = [
            a
            for a in edge_annotations
            if a.category == AnnotationCategory.NULL_FINDING_CONTEXT
        ]

        result = pool_evidence(
            resolved=resolved,
            confounder_annotations=confounder_anns,
            null_finding_annotations=null_finding_anns,
        )
        results.append(result)

    # ─── Gate P4-G1: All edges have method assigned ───────────
    edges_without_method = [
        r.pooled_estimate.edge_relation_id
        for r in results
        if not r.pooled_estimate.aggregation_method
    ]
    if edges_without_method:
        raise GateViolation(
            "P4-G1",
            f"{len(edges_without_method)} edge(s) have no aggregation method assigned: "
            f"{edges_without_method[:10]}",
            {"edges_without_method": edges_without_method},
        )

    logger.info(
        "Meta-analysis complete: %d edges processed, methods: %s",
        len(results),
        _summarize_methods(results),
    )

    return results


def _summarize_methods(results: list[MetaAnalysisResult]) -> dict[str, int]:
    """Summarize aggregation methods across all edges for logging."""
    method_counts: dict[str, int] = {}
    for r in results:
        method = r.pooled_estimate.aggregation_method
        method_counts[method] = method_counts.get(method, 0) + 1
    return method_counts
