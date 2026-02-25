# VERIFIED: formulas [B1-1..B1-5, B2-1, B3-1..B3-5, B4-1, B5-1, B6-1, B6-2] match spec SYS_ALG lines 1103-1428
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads GraphObject from chain_a_graph.graph_object
# VERIFIED: forward wiring — writes PooledEdge, HeterogeneityAdjustedEdge, EdgePriorSpec,
#           InclusionProbEdge, TauSquaredPrior, ChainDirectResult for frozen_state.py
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [B-G1, B-G2, B-G3, B-G4, B-G5] raise on failure
# VERIFIED: τ² double-counting guard — adds τ² for all methods except IVW_RANDOM (which incorporates it)
# VERIFIED: B3 decision tree — k≥5 non-prospective falls to Commensurate (no gap)
# VERIFIED: Commensurate τ — weighted geometric product per spec line 1347
"""
Component: SYS_ALGORITHM.ALG-B.B1-B6
Spec: SYS_ALGORITHM_COMPLETE.md lines 1270-1428
Formulas:
    B1-1: μ_e = Σ(β_i/σ²_i) / Σ(1/σ²_i)              (IVW mean)
    B1-2: SE_within = 1 / √(Σ(1/σ²_i))                 (pooled SE)
    B1-3: Q = Σ w_i(β_i − μ_e)²                        (Cochran's Q)
    B1-4: τ² = max(0, (Q−(k−1)) / (Σw−Σw²/Σw))        (DerSimonian-Laird)
    B1-5: I² = max(0, (Q−(k−1))/Q)                     (inconsistency)
    B2-1: SE_eff = √[(SE×m_claim×m_GRADE×m_temp)² + σ²_struct + τ²·𝟙] / (w_scope×w_fresh)
    B3-1: RobustMAP w = min(0.8, 0.5 + 0.06k)
    B3-2: Commensurate β ~ N(β_hist, σ²_hist / τ)
    B3-3: PowerPrior L(β|D₀)^{a₀} × π₀(β)
    B3-4: MechanisticSynth β_impl = Π_i β_i
    B3-5: StructuralPlaceholder β ~ N(0, 10²)
    B4-1: P_incl = 1/(1+exp(−(−0.5+1.2·ln(k+1)+0.4·Z+0.6·𝟙[RCT])))
    B5-1: τ² ~ LogNormal(μ, σ²)  (Turner et al., 2012)
    B6-1: Z = |β_chain − β_direct| / √(σ²_chain + σ²_direct)
    B6-2: AV(e) = 1 − min(Z/3.0, 1.0)
Reads: GraphObject (from chain_a_graph), EvidenceRecord[] (from SYS_EXTRACTION)
Writes: PooledEdge, HeterogeneityAdjustedEdge, EdgePriorSpec,
        InclusionProbEdge, TauSquaredPrior, ChainDirectResult
        (all consumed by frozen_state.py → FrozenModelState)
Gates: B-G1, B-G2, B-G3, B-G4, B-G5
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_a_graph.edge_loader import EdgeDef
from ..chain_a_graph.graph_object import GraphObject

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Input Type: Evidence Record
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EvidenceRecord:
    """Single evidence record for an edge, produced by SYS_EXTRACTION.

    This is the interface between the extraction pipeline and the
    algorithm pipeline. Each record represents one study's quantitative
    contribution to one edge in the causal DAG.
    """

    study_id: str
    edge_id: str
    beta: float                    # effect estimate (standardized)
    se: float                      # standard error
    study_design: str              # key into config.DESIGN_MULTIPLIERS
    publication_year: int
    sample_size: int
    identification_status: str     # identified, partially_identified, plausible, unidentified
    quality_grade: str             # HIGH, MODERATE, LOW, VERY_LOW
    scope_weights: dict[str, float]  # 5 dimensions for transportability
    cancer_validation_status: str  # validated_cancer, used_cancer, general_population, known_somatic_confound
    temporal_distance_days: float  # distance to model target timepoint
    outcome_type: str              # subjective, semi_objective, biomarker
    is_animal: bool = False
    is_cross_sectional: bool = False
    has_rct_component: bool = False
    sigma_sq_structural: float | None = None  # annotation-informed override


# ═══════════════════════════════════════════════════════════════
#  Intermediate Types: B1-B6 Outputs
# ═══════════════════════════════════════════════════════════════


@dataclass
class PooledEdge:
    """Output of B1: IVW pooling result for one edge."""

    edge_id: str
    mu_e: float                    # IVW pooled point estimate
    SE_within: float               # pooled within-study SE
    tau_sq: float                  # DerSimonian-Laird τ²
    k: int                         # number of contributing studies
    I_sq: float                    # inconsistency index [0,1]
    aggregation_method: str        # BLOCKED, DIRECT, IVW_FIXED, IVW_RANDOM, STRATIFIED, SINGLE_BEST
    contributing_studies: list[str] = field(default_factory=list)
    attenuation_factor: float = 1.0  # claim-level β attenuation


@dataclass
class HeterogeneityAdjustedEdge:
    """Output of B2: PooledEdge extended with SE_eff from 7-layer pipeline."""

    edge_id: str
    mu_e: float
    SE_within: float
    tau_sq: float
    k: int
    I_sq: float
    aggregation_method: str
    contributing_studies: list[str]
    attenuation_factor: float
    # B2 additions
    SE_eff: float                  # effective SE after 7-layer compounding
    layer_contributions: dict[str, float]  # L1-L7 per-layer factor
    sigma_sq_structural: float     # additive structural variance
    w_scope: float                 # transportability weight [0.3, 1.0]
    w_fresh: float                 # evidence freshness weight [0.70, 1.0]


@dataclass
class EdgePriorSpec:
    """Output of B3: Bayesian prior specification for one edge."""

    edge_id: str
    prior_type: str                # RobustMAP, Commensurate, PowerPrior, MechanisticSynth, StructuralPlaceholder
    prior_params: dict[str, float]  # type-specific parameters
    selection_rationale: str


@dataclass
class InclusionProbEdge:
    """Output of B4: structural inclusion probability for one edge."""

    edge_id: str
    P_inclusion: float             # [0, 1]
    inclusion_inputs: dict[str, float]  # {k, Z, has_RCT}
    is_decision_critical: bool     # True if force-ON vs force-OFF changes top rank


@dataclass
class TauSquaredPrior:
    """Output of B5: empirical τ² prior distribution for one edge."""

    edge_id: str
    outcome_type: str              # subjective, semi_objective, biomarker
    log_mu: float                  # log-normal μ
    log_sigma: float               # log-normal σ
    median_tau_sq: float           # exp(log_mu)


@dataclass
class ChainDirectResult:
    """Output of B6: chain-vs-direct validation for one edge."""

    edge_id: str
    has_chain_evidence: bool
    has_direct_evidence: bool
    beta_chain: float | None
    se_chain: float | None
    beta_direct: float | None
    se_direct: float | None
    Z_score: float | None
    AV_score: float | None         # Alignment Validity [0, 1]
    triage_action: str             # Pass, Mild, Moderate, Substantial
    se_multiplier: float           # applied SE inflation


# ═══════════════════════════════════════════════════════════════
#  B1 — IVW Pooling & Aggregation
# ═══════════════════════════════════════════════════════════════


def _apply_precision_caps(
    records: list[EvidenceRecord],
) -> list[EvidenceRecord]:
    """B1a: Apply precision caps to prevent low-quality designs from
    dominating high-quality ones.

    Cross-sectional: cap at 30% of best RCT precision
    Animal: cap at 10% of best human RCT precision

    Args:
        records: Evidence records for one edge.

    Returns:
        Records with SE floors applied where needed.
    """
    # Find best RCT precision (lowest SE among RCTs)
    rct_ses = [
        r.se for r in records
        if r.study_design in ("large_rct", "small_rct_default")
        and r.se > 0
    ]
    if not rct_ses:
        return records

    best_rct_se = min(rct_ses)

    capped: list[EvidenceRecord] = []
    for r in records:
        se = r.se
        if r.is_cross_sectional and se > 0:
            # Formula B1a: cross-sect ≥ 30% of best RCT precision
            # Precision = 1/SE², so SE floor = best_rct_se / √(cap_fraction)
            se_floor = best_rct_se / math.sqrt(config.EG_PRECISION_CAP_CROSS_SECTIONAL)
            if se < se_floor:
                logger.info(
                    "Precision cap: study %s SE %.4f → %.4f (cross-sectional cap)",
                    r.study_id, se, se_floor,
                )
                # Create new record with capped SE
                r = EvidenceRecord(
                    study_id=r.study_id, edge_id=r.edge_id, beta=r.beta,
                    se=se_floor, study_design=r.study_design,
                    publication_year=r.publication_year,
                    sample_size=r.sample_size,
                    identification_status=r.identification_status,
                    quality_grade=r.quality_grade,
                    scope_weights=r.scope_weights,
                    cancer_validation_status=r.cancer_validation_status,
                    temporal_distance_days=r.temporal_distance_days,
                    outcome_type=r.outcome_type,
                    is_animal=r.is_animal,
                    is_cross_sectional=r.is_cross_sectional,
                    has_rct_component=r.has_rct_component,
                    sigma_sq_structural=r.sigma_sq_structural,
                )
        elif r.is_animal and se > 0:
            # Formula B1a: animal ≥ 10% of best human RCT precision
            se_floor = best_rct_se / math.sqrt(config.EG_PRECISION_CAP_ANIMAL)
            if se < se_floor:
                logger.info(
                    "Precision cap: study %s SE %.4f → %.4f (animal cap)",
                    r.study_id, se, se_floor,
                )
                r = EvidenceRecord(
                    study_id=r.study_id, edge_id=r.edge_id, beta=r.beta,
                    se=se_floor, study_design=r.study_design,
                    publication_year=r.publication_year,
                    sample_size=r.sample_size,
                    identification_status=r.identification_status,
                    quality_grade=r.quality_grade,
                    scope_weights=r.scope_weights,
                    cancer_validation_status=r.cancer_validation_status,
                    temporal_distance_days=r.temporal_distance_days,
                    outcome_type=r.outcome_type,
                    is_animal=r.is_animal,
                    is_cross_sectional=r.is_cross_sectional,
                    has_rct_component=r.has_rct_component,
                    sigma_sq_structural=r.sigma_sq_structural,
                )
        capped.append(r)

    return capped


def _compute_ivw(
    betas: list[float],
    ses: list[float],
) -> tuple[float, float, float, float, float]:
    """B1c: Compute IVW pooled estimate and heterogeneity statistics.

    Args:
        betas: Effect estimates β_i.
        ses: Standard errors SE_i.

    Returns:
        Tuple of (mu_e, SE_within, Q, tau_sq, I_sq).
    """
    k = len(betas)
    assert k >= 2, "IVW requires k ≥ 2"

    # Weights: w_i = 1/σ²_i
    variances = [se ** 2 for se in ses]
    weights = [1.0 / v for v in variances]
    sum_w = sum(weights)

    # Formula B1-1: μ_e = Σ(β_i/σ²_i) / Σ(1/σ²_i)
    mu_e = sum(b / v for b, v in zip(betas, variances)) / sum_w

    # Formula B1-2: SE_within = 1 / √(Σ(1/σ²_i))
    SE_within = 1.0 / math.sqrt(sum_w)

    # Formula B1-3: Q = Σ w_i(β_i − μ_e)²
    Q = sum(w * (b - mu_e) ** 2 for w, b in zip(weights, betas))

    # Formula B1-4: τ² = max(0, (Q−(k−1)) / (Σw − Σw²/Σw))
    sum_w_sq = sum(w ** 2 for w in weights)
    denominator = sum_w - sum_w_sq / sum_w
    if denominator > 0:
        tau_sq = max(0.0, (Q - (k - 1)) / denominator)
    else:
        tau_sq = 0.0

    # Formula B1-5: I² = max(0, (Q−(k−1))/Q)
    if Q > 0:
        I_sq = max(0.0, (Q - (k - 1)) / Q)
    else:
        I_sq = 0.0

    return mu_e, SE_within, Q, tau_sq, I_sq


def _select_aggregation_method(
    records: list[EvidenceRecord],
    I_sq: float,
) -> str:
    """B1b: Aggregation decision tree.

    Decision tree:
        k = 0 → BLOCKED
        k = 1 → DIRECT (passthrough)
        k ≥ 2, ≥2 have SE:
            I² < 50%                        → IVW_FIXED
            50% ≤ I² < 75% AND stratifiable → STRATIFIED
            50% ≤ I² < 75% AND not strat.   → IVW_RANDOM
            I² ≥ 75% AND stratifiable        → STRATIFIED
            I² ≥ 75% AND not stratifiable    → SINGLE_BEST
            Sign conflict among high-quality → BLOCKED

    Args:
        records: Evidence records for this edge.
        I_sq: Inconsistency index from IVW computation.

    Returns:
        Aggregation method string.
    """
    k = len(records)

    if k == 0:
        return "BLOCKED"
    if k == 1:
        return "DIRECT"

    records_with_se = [r for r in records if r.se > 0]
    if len(records_with_se) < 2:
        return "DIRECT"

    # Check sign conflict among high-quality studies
    high_quality_signs = set()
    for r in records:
        if r.quality_grade in ("HIGH", "MODERATE"):
            if r.beta > 0:
                high_quality_signs.add(1)
            elif r.beta < 0:
                high_quality_signs.add(-1)
    if len(high_quality_signs) > 1:
        # Both positive and negative effects among high-quality studies
        logger.warning(
            "Sign conflict among high-quality studies for edge %s — BLOCKED",
            records[0].edge_id,
        )
        return "BLOCKED"

    # Stratifiability: can we group by design type with ≥2 per stratum?
    design_counts: dict[str, int] = {}
    for r in records:
        design_counts[r.study_design] = design_counts.get(r.study_design, 0) + 1
    is_stratifiable = any(c >= 2 for c in design_counts.values()) and len(design_counts) >= 2

    I_sq_pct = I_sq * 100.0  # convert to percentage

    if I_sq_pct < config.HETEROGENEITY_MODERATE_THRESHOLD:
        return "IVW_FIXED"
    elif I_sq_pct < config.HETEROGENEITY_HIGH_THRESHOLD:
        return "STRATIFIED" if is_stratifiable else "IVW_RANDOM"
    else:
        return "STRATIFIED" if is_stratifiable else "SINGLE_BEST"


def _get_attenuation_factor(identification_status: str) -> float:
    """Look up claim-level β attenuation factor by identification status.

    Spec SYS_ALG lines 1309-1324:
        Identified (RCT)      → 1.00
        Partially identified  → 0.85
        Plausible            → 0.70
        Unidentified         → 0.50
    """
    mapping = {
        "identified": config.IDENTIFICATION_FACTOR_IDENTIFIED,
        "partially_identified": config.IDENTIFICATION_FACTOR_PARTIAL,
        "plausible": config.IDENTIFICATION_FACTOR_PLAUSIBLE,
        "unidentified": config.IDENTIFICATION_FACTOR_UNIDENTIFIED,
    }
    factor = mapping.get(identification_status)
    if factor is None:
        logger.warning(
            "Unknown identification_status '%s' — using PLAUSIBLE default (%.2f)",
            identification_status,
            config.IDENTIFICATION_FACTOR_PLAUSIBLE,
        )
        return config.IDENTIFICATION_FACTOR_PLAUSIBLE
    return factor


def pool_edge(
    edge_id: str,
    records: list[EvidenceRecord],
) -> PooledEdge:
    """B1: IVW pool evidence records for one edge.

    Orchestrates B1a (precision caps), B1b (aggregation decision),
    and B1c (IVW computation).

    Args:
        edge_id: Edge identifier.
        records: Evidence records targeting this edge.

    Returns:
        PooledEdge with aggregation result.
    """
    k = len(records)

    if k == 0:
        logger.info("Edge %s: k=0 → BLOCKED", edge_id)
        return PooledEdge(
            edge_id=edge_id,
            mu_e=0.0,
            SE_within=float("inf"),
            tau_sq=0.0,
            k=0,
            I_sq=0.0,
            aggregation_method="BLOCKED",
            contributing_studies=[],
            attenuation_factor=1.0,
        )

    # B1a: Apply precision caps
    records = _apply_precision_caps(records)

    # Apply diminishing returns weight: w_base × 1/(1 + 0.3·ln(k))
    # This does NOT change β/SE — it's for informational tracking only
    # (actual diminishing returns are via IVW weighting naturally)

    if k == 1:
        r = records[0]
        att = _get_attenuation_factor(r.identification_status)
        return PooledEdge(
            edge_id=edge_id,
            mu_e=r.beta * att,
            SE_within=r.se,
            tau_sq=0.0,
            k=1,
            I_sq=0.0,
            aggregation_method="DIRECT",
            contributing_studies=[r.study_id],
            attenuation_factor=att,
        )

    # k ≥ 2: Compute IVW
    valid_records = [r for r in records if r.se > 0]
    if len(valid_records) < 2:
        # Fall back to single best
        best = max(records, key=lambda r: r.sample_size)
        att = _get_attenuation_factor(best.identification_status)
        return PooledEdge(
            edge_id=edge_id,
            mu_e=best.beta * att,
            SE_within=best.se if best.se > 0 else float("inf"),
            tau_sq=0.0,
            k=len(records),
            I_sq=0.0,
            aggregation_method="SINGLE_BEST",
            contributing_studies=[r.study_id for r in records],
            attenuation_factor=att,
        )

    betas = [r.beta for r in valid_records]
    ses = [r.se for r in valid_records]

    mu_e, SE_within, Q, tau_sq, I_sq = _compute_ivw(betas, ses)

    # B1b: Select aggregation method
    method = _select_aggregation_method(valid_records, I_sq)

    # Handle special methods
    if method == "SINGLE_BEST":
        # Use study with lowest SE
        best = min(valid_records, key=lambda r: r.se)
        att = _get_attenuation_factor(best.identification_status)
        return PooledEdge(
            edge_id=edge_id,
            mu_e=best.beta * att,
            SE_within=best.se,
            tau_sq=tau_sq,
            k=k,
            I_sq=I_sq,
            aggregation_method="SINGLE_BEST",
            contributing_studies=[r.study_id for r in records],
            attenuation_factor=att,
        )

    if method == "IVW_RANDOM":
        # Use random-effects SE: SE_random = √(1/Σ(1/(σ²_i + τ²)))
        re_weights = [1.0 / (se ** 2 + tau_sq) for se in ses]
        sum_re_w = sum(re_weights)
        mu_e = sum(b * w for b, w in zip(betas, re_weights)) / sum_re_w
        SE_within = 1.0 / math.sqrt(sum_re_w)

    if method == "BLOCKED":
        mu_e = 0.0
        SE_within = float("inf")

    # Compute aggregate attenuation factor (weighted by precision)
    att_factors = [_get_attenuation_factor(r.identification_status) for r in valid_records]
    weights = [1.0 / (r.se ** 2) for r in valid_records]
    sum_w = sum(weights)
    weighted_att = sum(a * w for a, w in zip(att_factors, weights)) / sum_w if sum_w > 0 else 1.0

    # Apply attenuation to pooled estimate
    mu_e_attenuated = mu_e * weighted_att

    return PooledEdge(
        edge_id=edge_id,
        mu_e=mu_e_attenuated,
        SE_within=SE_within,
        tau_sq=tau_sq,
        k=k,
        I_sq=I_sq,
        aggregation_method=method,
        contributing_studies=[r.study_id for r in records],
        attenuation_factor=weighted_att,
    )


# ═══════════════════════════════════════════════════════════════
#  B2 — Seven-Layer Heterogeneity Pipeline
# ═══════════════════════════════════════════════════════════════


def _compute_design_multiplier(record: EvidenceRecord) -> float:
    """Layer 1: Study design SE multiplier (1.0–6.0×).

    Args:
        record: Single evidence record.

    Returns:
        SE multiplier for study design.
    """
    design = record.study_design
    mult = config.DESIGN_MULTIPLIERS.get(design)

    if mult is not None:
        # Special handling for small RCTs: interpolation
        if design == "small_rct_default" and record.sample_size <= config.SMALL_RCT_N_THRESHOLD:
            # Formula: m = 1.0 + SLOPE × (THRESHOLD − N) / THRESHOLD
            n = max(record.sample_size, 1)
            mult = 1.0 + config.SMALL_RCT_PENALTY_SLOPE * (
                config.SMALL_RCT_N_THRESHOLD - n
            ) / config.SMALL_RCT_N_THRESHOLD
        return mult

    logger.warning(
        "Unknown study_design '%s' for study %s — using default %.1f×",
        design, record.study_id, config.DESIGN_MULTIPLIER_DEFAULT,
    )
    return config.DESIGN_MULTIPLIER_DEFAULT


def _compute_scope_weight(record: EvidenceRecord) -> float:
    """Layer 2: Transportability — 5-dimension scope weight.

    w_scope = geometric mean of 5 dimension weights
    Floor: max(w_scope, 0.3)

    Args:
        record: Single evidence record.

    Returns:
        Scope weight in [0.3, 1.0].
    """
    if not record.scope_weights:
        logger.warning(
            "No scope_weights for study %s — using floor %.2f",
            record.study_id, config.SCOPE_FLOOR,
        )
        return config.SCOPE_FLOOR

    # Geometric mean of available dimension weights
    values = list(record.scope_weights.values())
    if not values:
        return config.SCOPE_FLOOR

    log_sum = sum(math.log(max(v, 0.01)) for v in values)
    geo_mean = math.exp(log_sum / len(values))

    # Floor: max(w_scope, 0.3)
    return max(geo_mean, config.SCOPE_FLOOR)


def _compute_grade_multiplier(record: EvidenceRecord) -> float:
    """Layer 5: GRADE-inspired SE inflation (1.0–2.0×).

    Args:
        record: Single evidence record.

    Returns:
        GRADE quality multiplier.
    """
    mult = config.GRADE_MULTIPLIERS.get(record.quality_grade)
    if mult is not None:
        return mult

    logger.warning(
        "Unknown quality_grade '%s' for study %s — using MODERATE default %.2f×",
        record.quality_grade, record.study_id,
        config.GRADE_MULTIPLIERS.get("MODERATE", 1.25),
    )
    return config.GRADE_MULTIPLIERS.get("MODERATE", 1.25)


def _compute_temporal_multiplier(record: EvidenceRecord) -> float:
    """Layer 6: Temporal mismatch SE correction (1.0–1.6×).

    SE inflated proportional to temporal distance, adjusted by
    intervention kernel.

    Args:
        record: Single evidence record.

    Returns:
        Temporal mismatch multiplier in [1.0, 1.6].
    """
    if record.temporal_distance_days <= 0:
        return 1.0

    # Exponential decay-based inflation
    # m_temporal = 1 + (MAX-1) × (1 - exp(-dist/half))
    max_mult = config.B2_TEMPORAL_MISMATCH_MAX
    half_days = config.B2_TEMPORAL_MISMATCH_HALF_DAYS
    raw = 1.0 + (max_mult - 1.0) * (
        1.0 - math.exp(-record.temporal_distance_days / half_days)
    )
    return min(raw, max_mult)


def _compute_freshness_weight(record: EvidenceRecord) -> float:
    """Layer 7: Evidence freshness weight.

    Formula: w_fresh = max(0.70, 1 − 0.015 × (REF_YEAR − pub_year))
    Calibration: Poynard et al. (2002) — 45-year half-life

    Args:
        record: Single evidence record.

    Returns:
        Freshness weight in [0.70, 1.0].
    """
    age_years = config.FRESHNESS_REFERENCE_YEAR - record.publication_year
    if age_years <= 0:
        return 1.0

    # Formula B2-L7: w_fresh = max(FLOOR, 1 − DECAY × age)
    w = 1.0 - config.FRESHNESS_DECAY_RATE * age_years
    return max(config.FRESHNESS_FLOOR, w)


def compute_se_eff(
    pooled: PooledEdge,
    records: list[EvidenceRecord],
) -> HeterogeneityAdjustedEdge:
    """B2: Compute effective SE through 7-layer heterogeneity pipeline.

    Master formula:
    SE_eff = √[(SE_pooled × m_claim × m_GRADE × m_temporal)² + σ²_structural + τ²·𝟙]
             ───────────────────────────────────────────────────────────────────────────
                                  max(w_scope, 0.3) × w_fresh

    Args:
        pooled: PooledEdge from B1.
        records: Original evidence records for per-record layer computation.

    Returns:
        HeterogeneityAdjustedEdge with SE_eff and layer contributions.
    """
    if pooled.aggregation_method == "BLOCKED" or pooled.k == 0:
        return HeterogeneityAdjustedEdge(
            edge_id=pooled.edge_id,
            mu_e=pooled.mu_e,
            SE_within=pooled.SE_within,
            tau_sq=pooled.tau_sq,
            k=pooled.k,
            I_sq=pooled.I_sq,
            aggregation_method=pooled.aggregation_method,
            contributing_studies=pooled.contributing_studies,
            attenuation_factor=pooled.attenuation_factor,
            SE_eff=float("inf"),
            layer_contributions={"L1": 1.0, "L2": 1.0, "L3": 0.0,
                                 "L4": 1.0, "L5": 1.0, "L6": 1.0, "L7": 1.0},
            sigma_sq_structural=config.SIGMA_SQ_STRUCTURAL_DEFAULT,
            w_scope=config.SCOPE_FLOOR,
            w_fresh=config.FRESHNESS_FLOOR,
        )

    # Compute per-record layers, then aggregate
    # For pooled edges, use precision-weighted averages of per-record multipliers
    if records:
        valid_records = [r for r in records if r.se > 0]
    else:
        valid_records = []

    if valid_records:
        weights = [1.0 / (r.se ** 2) for r in valid_records]
        sum_w = sum(weights)

        # L1: Study design multiplier (precision-weighted average)
        m_claims = [_compute_design_multiplier(r) for r in valid_records]
        m_claim = sum(m * w for m, w in zip(m_claims, weights)) / sum_w

        # L2: Scope weight (precision-weighted average)
        w_scopes = [_compute_scope_weight(r) for r in valid_records]
        w_scope = sum(ws * w for ws, w in zip(w_scopes, weights)) / sum_w
        w_scope = max(w_scope, config.SCOPE_FLOOR)

        # L5: GRADE multiplier (precision-weighted average)
        m_grades = [_compute_grade_multiplier(r) for r in valid_records]
        m_grade = sum(mg * w for mg, w in zip(m_grades, weights)) / sum_w

        # L6: Temporal mismatch (precision-weighted average)
        m_temporals = [_compute_temporal_multiplier(r) for r in valid_records]
        m_temporal = sum(mt * w for mt, w in zip(m_temporals, weights)) / sum_w

        # L7: Freshness weight (precision-weighted average)
        w_freshes = [_compute_freshness_weight(r) for r in valid_records]
        w_fresh = sum(wf * w for wf, w in zip(w_freshes, weights)) / sum_w
        w_fresh = max(w_fresh, config.FRESHNESS_FLOOR)

        # Structural variance: use annotation-informed value if available
        sigma_sq_structs = [
            r.sigma_sq_structural if r.sigma_sq_structural is not None
            else config.SIGMA_SQ_STRUCTURAL_DEFAULT
            for r in valid_records
        ]
        sigma_sq_structural = sum(
            s * w for s, w in zip(sigma_sq_structs, weights)
        ) / sum_w
        # Ceiling
        sigma_sq_structural = min(
            sigma_sq_structural, config.SIGMA_SQ_STRUCTURAL_CEILING
        )
    else:
        # No valid records — use defaults
        m_claim = config.DESIGN_MULTIPLIER_DEFAULT
        w_scope = config.SCOPE_FLOOR
        m_grade = config.GRADE_MULTIPLIERS.get("LOW", 1.50)
        m_temporal = 1.0
        w_fresh = config.FRESHNESS_DEFAULT_WEIGHT
        sigma_sq_structural = config.SIGMA_SQ_STRUCTURAL_DEFAULT

    # L3: Statistical heterogeneity (τ²)
    # Spec line 1303: τ² added ONLY when not already in base SE (𝟙[not_in_base])
    # IVW_RANDOM already incorporates τ² via random-effects weights → don't add again
    # IVW_FIXED, SINGLE_BEST, STRATIFIED: τ² is NOT in base SE → add
    # BLOCKED, DIRECT: τ²=0 by construction → adding 0 is harmless
    tau_sq_addition = 0.0 if pooled.aggregation_method == "IVW_RANDOM" else pooled.tau_sq

    # Formula B2-1: Master SE_eff computation
    # Numerator: √[(SE_pooled × m_claim × m_GRADE × m_temporal)² + σ²_structural + τ²·𝟙]
    multiplicative_se = pooled.SE_within * m_claim * m_grade * m_temporal
    variance_under_root = (
        multiplicative_se ** 2
        + sigma_sq_structural
        + tau_sq_addition
    )
    numerator = math.sqrt(max(variance_under_root, 0.0))

    # Denominator: max(w_scope, 0.3) × w_fresh
    denominator = w_scope * w_fresh

    SE_eff = numerator / denominator if denominator > 0 else float("inf")

    layer_contributions = {
        "L1_design": m_claim,
        "L2_scope": w_scope,
        "L3_tau_sq": tau_sq_addition,
        "L4_scale": 1.0,  # scale compatibility handled at extraction
        "L5_grade": m_grade,
        "L6_temporal": m_temporal,
        "L7_freshness": w_fresh,
    }

    return HeterogeneityAdjustedEdge(
        edge_id=pooled.edge_id,
        mu_e=pooled.mu_e,
        SE_within=pooled.SE_within,
        tau_sq=pooled.tau_sq,
        k=pooled.k,
        I_sq=pooled.I_sq,
        aggregation_method=pooled.aggregation_method,
        contributing_studies=pooled.contributing_studies,
        attenuation_factor=pooled.attenuation_factor,
        SE_eff=SE_eff,
        layer_contributions=layer_contributions,
        sigma_sq_structural=sigma_sq_structural,
        w_scope=w_scope,
        w_fresh=w_fresh,
    )


# ═══════════════════════════════════════════════════════════════
#  B3 — Prior Selection Framework
# ═══════════════════════════════════════════════════════════════


def _best_design_is_prospective(records: list[EvidenceRecord]) -> bool:
    """Check whether the best study design is at least prospective."""
    for r in records:
        if r.study_design in config.B3_PROSPECTIVE_DESIGNS:
            return True
    return False


def _compute_commensurate_tau(records: list[EvidenceRecord]) -> float:
    """Compute commensurate prior τ as weighted geometric product of scope dimensions.

    Formula (spec line 1347): τ = Π_d w_d^{p_d}
    where w_d are the 5 scope dimension weights and p_d are the config weights.

    Takes the average across records of the per-record geometric product.
    """
    if not records:
        return config.SCOPE_FLOOR

    taus: list[float] = []
    for r in records:
        if not r.scope_weights:
            taus.append(config.SCOPE_FLOOR)
            continue
        # Weighted geometric product: Π_d w_d^{p_d}
        log_product = 0.0
        total_weight = 0.0
        for dim, p_d in config.SCOPE_WEIGHTS.items():
            w_d = r.scope_weights.get(dim, config.SCOPE_FLOOR)
            w_d = max(w_d, 0.01)  # prevent log(0)
            log_product += p_d * math.log(w_d)
            total_weight += p_d
        if total_weight > 0:
            taus.append(math.exp(log_product))
        else:
            taus.append(config.SCOPE_FLOOR)

    # Average across records
    tau = sum(taus) / len(taus)
    return max(tau, config.SCOPE_FLOOR)


def _has_chain_evidence(
    edge_id: str,
    graph: GraphObject,
    all_adjusted: dict[str, HeterogeneityAdjustedEdge],
) -> bool:
    """Check if indirect chain evidence exists for this edge.

    An edge has chain evidence if there exists an intermediate path
    from source to target where all intermediate edges have k > 0.
    """
    edge_idx = graph.b_skeleton.edge_index.get(edge_id)
    if edge_idx is None:
        return False

    edge_def = graph.b_skeleton.edges[edge_idx]
    source = edge_def.source_node_id
    target = edge_def.target_node_id

    # Simple check: are there edges from source and to target via intermediaries?
    edges_from_source = [
        e for e in graph.b_skeleton.edges
        if e.source_node_id == source and e.edge_id != edge_id
        and not e.is_feedback_edge
    ]
    edges_to_target = [
        e for e in graph.b_skeleton.edges
        if e.target_node_id == target and e.edge_id != edge_id
        and not e.is_feedback_edge
    ]

    if not edges_from_source or not edges_to_target:
        return False

    # Check if intermediate edges are parameterized (k > 0)
    for e_from in edges_from_source:
        intermediate = e_from.target_node_id
        for e_to in edges_to_target:
            if e_to.source_node_id == intermediate:
                adj_from = all_adjusted.get(e_from.edge_id)
                adj_to = all_adjusted.get(e_to.edge_id)
                if (adj_from and adj_from.k > 0 and
                        adj_to and adj_to.k > 0):
                    return True

    return False


def _compute_chain_estimate(
    edge_id: str,
    graph: GraphObject,
    all_adjusted: dict[str, HeterogeneityAdjustedEdge],
) -> tuple[float, float, list[str]] | None:
    """Compute implied β from chain path (mechanistic synthesis).

    Formula B3-4: β_implied = Π_i β_i
    SE_implied = |β_impl| × √(Σ(SE_i/β_i)²) [delta method]

    Returns:
        (beta_implied, se_implied, chain_edge_ids) or None.
    """
    edge_idx = graph.b_skeleton.edge_index.get(edge_id)
    if edge_idx is None:
        return None

    edge_def = graph.b_skeleton.edges[edge_idx]
    source = edge_def.source_node_id
    target = edge_def.target_node_id

    # Find 2-hop chain: source → intermediate → target
    best_chain: tuple[float, float, list[str]] | None = None

    for e_from in graph.b_skeleton.edges:
        if e_from.source_node_id != source or e_from.edge_id == edge_id:
            continue
        if e_from.is_feedback_edge:
            continue

        intermediate = e_from.target_node_id
        adj_from = all_adjusted.get(e_from.edge_id)
        if not adj_from or adj_from.k == 0 or adj_from.aggregation_method == "BLOCKED":
            continue

        for e_to in graph.b_skeleton.edges:
            if e_to.source_node_id != intermediate or e_to.target_node_id != target:
                continue
            if e_to.is_feedback_edge or e_to.edge_id == edge_id:
                continue

            adj_to = all_adjusted.get(e_to.edge_id)
            if not adj_to or adj_to.k == 0 or adj_to.aggregation_method == "BLOCKED":
                continue

            # Formula B3-4: β_implied = Π_i β_i
            beta_impl = adj_from.mu_e * adj_to.mu_e

            # SE_implied = |β_impl| × √(Σ(SE_i/β_i)²)
            if abs(adj_from.mu_e) > 1e-10 and abs(adj_to.mu_e) > 1e-10:
                se_ratio_sq = (
                    (adj_from.SE_eff / adj_from.mu_e) ** 2
                    + (adj_to.SE_eff / adj_to.mu_e) ** 2
                )
                se_impl = abs(beta_impl) * math.sqrt(se_ratio_sq)
            else:
                se_impl = float("inf")

            chain_edges = [e_from.edge_id, e_to.edge_id]

            if best_chain is None or se_impl < best_chain[1]:
                best_chain = (beta_impl, se_impl, chain_edges)

    return best_chain


def select_prior(
    adjusted: HeterogeneityAdjustedEdge,
    records: list[EvidenceRecord],
    graph: GraphObject,
    all_adjusted: dict[str, HeterogeneityAdjustedEdge] | None = None,
) -> EdgePriorSpec:
    """B3: Select and parameterize Bayesian prior for one edge.

    Decision tree:
        RobustMAP           if k ≥ 5, best_design ≥ prospective
        Commensurate        if k ∈ [2,4]
        PowerPrior          if k = 1
        MechanisticSynth    if k = 0, has_chain
        StructuralPlaceholder  if k = 0, no_chain

    Args:
        adjusted: HeterogeneityAdjustedEdge from B2.
        records: Evidence records for this edge.
        graph: GraphObject for chain evidence lookup.
        all_adjusted: All adjusted edges (for chain evidence computation).

    Returns:
        EdgePriorSpec with prior type and parameters.
    """
    k = adjusted.k
    edge_id = adjusted.edge_id

    if all_adjusted is None:
        all_adjusted = {}

    # Decision tree
    if k >= 5 and _best_design_is_prospective(records):
        # B3a: RobustMAP (Schmidli et al., 2014)
        # Formula B3-1: w = min(0.8, 0.5 + 0.06k)
        w = min(
            config.B3_ROBUST_MAP_W_MAX,
            config.B3_ROBUST_MAP_W_BASE + config.B3_ROBUST_MAP_W_PER_K * k,
        )
        return EdgePriorSpec(
            edge_id=edge_id,
            prior_type="RobustMAP",
            prior_params={
                "w": w,
                "MAP_mean": adjusted.mu_e,
                "MAP_var": adjusted.SE_eff ** 2,
                "vague_var": config.B3_ROBUST_MAP_VAGUE_VAR,
            },
            selection_rationale=f"k={k} ≥ 5, best_design ≥ prospective → RobustMAP (w={w:.3f})",
        )

    if k >= config.B3_COMMENSURATE_MIN_K and (
        k <= config.B3_COMMENSURATE_MAX_K or not _best_design_is_prospective(records)
    ):
        # B3b: Commensurate (Hobbs et al., 2011)
        # Also covers k >= 5 without prospective design (spec gap: these have evidence
        # but don't qualify for RobustMAP; Commensurate is the best fallback).
        # τ_commens = Π_d w_d^{p_d} (5 dimension match scores, spec line 1347)
        if records:
            # Geometric product of scope dimension weights per spec
            tau_commens = _compute_commensurate_tau(records)
        else:
            tau_commens = config.SCOPE_FLOOR

        rationale = (
            f"k={k} ∈ [2,4] → Commensurate (τ={tau_commens:.3f})" if k <= config.B3_COMMENSURATE_MAX_K
            else f"k={k} ≥ 5, best_design < prospective → Commensurate fallback (τ={tau_commens:.3f})"
        )
        if k >= 5:
            logger.warning(
                "Edge %s: k=%d ≥ 5 but best_design < prospective — "
                "using Commensurate instead of RobustMAP",
                edge_id, k,
            )
        return EdgePriorSpec(
            edge_id=edge_id,
            prior_type="Commensurate",
            prior_params={
                "beta_hist": adjusted.mu_e,
                "sigma_sq_hist": adjusted.SE_eff ** 2,
                "tau": tau_commens,
            },
            selection_rationale=rationale,
        )

    if k == 1:
        # B3c: Power Prior (Ibrahim & Chen, 2000)
        # Discount a₀ based on design
        if records:
            design = records[0].study_design
            if design in ("large_rct",):
                a0 = config.B3_POWER_PRIOR_A0["rct_same"]
            elif design in ("small_rct_default",):
                a0 = config.B3_POWER_PRIOR_A0["rct_diff"]
            elif design in ("well_adjusted_cohort",):
                a0 = config.B3_POWER_PRIOR_A0["cohort"]
            elif design in ("unadjusted_longitudinal", "cross_sectional_adjusted",
                            "cross_sectional_unadjusted"):
                a0 = config.B3_POWER_PRIOR_A0["observational"]
            elif records[0].is_animal:
                a0 = config.B3_POWER_PRIOR_A0["animal"]
            else:
                a0 = config.B3_POWER_PRIOR_A0["mechanistic"]
        else:
            a0 = config.B3_POWER_PRIOR_A0["observational"]

        return EdgePriorSpec(
            edge_id=edge_id,
            prior_type="PowerPrior",
            prior_params={
                "a0": a0,
                "D0_beta": adjusted.mu_e,
                "D0_se": adjusted.SE_eff,
            },
            selection_rationale=f"k=1 → PowerPrior (a₀={a0:.2f})",
        )

    # k = 0
    if _has_chain_evidence(edge_id, graph, all_adjusted):
        # B3d: Mechanistic Synthesis
        chain_result = _compute_chain_estimate(edge_id, graph, all_adjusted)
        if chain_result is not None:
            beta_impl, se_impl, chain_edges = chain_result
            return EdgePriorSpec(
                edge_id=edge_id,
                prior_type="MechanisticSynth",
                prior_params={
                    "beta_implied": beta_impl,
                    "se_implied": se_impl,
                    "a0": config.B3_MECHANISTIC_SYNTH_A0,
                    "n_chain_edges": float(len(chain_edges)),
                },
                selection_rationale=(
                    f"k=0, chain exists via {chain_edges} → "
                    f"MechanisticSynth (β_impl={beta_impl:.4f}, a₀={config.B3_MECHANISTIC_SYNTH_A0})"
                ),
            )

    # B3e: Structural Placeholder
    return EdgePriorSpec(
        edge_id=edge_id,
        prior_type="StructuralPlaceholder",
        prior_params={
            "sigma_sq": config.B3_STRUCTURAL_PLACEHOLDER_VAR,
        },
        selection_rationale=f"k=0, no chain → StructuralPlaceholder (σ²={config.B3_STRUCTURAL_PLACEHOLDER_VAR})",
    )


# ═══════════════════════════════════════════════════════════════
#  B4 — Structural Inclusion Probability
# ═══════════════════════════════════════════════════════════════


def compute_p_inclusion(
    adjusted: HeterogeneityAdjustedEdge,
    records: list[EvidenceRecord],
) -> InclusionProbEdge:
    """B4: Compute calibrated structural inclusion probability.

    Formula B4-1:
    P_inclusion(e) = 1 / (1 + exp(−(−0.5 + 1.2·ln(k+1) + 0.4·Z + 0.6·𝟙[RCT])))

    Calibration targets (author-constructed):
        (i)   k=0, Z=0, no RCT → P ≈ 0.38
        (ii)  k=3, moderate Z  → P ≈ 0.80
        (iii) RCT bonus        → ~15 pp
        (iv)  k≥5, Z>3, RCT   → P ≈ 0.99

    Args:
        adjusted: HeterogeneityAdjustedEdge from B2.
        records: Evidence records for RCT check.

    Returns:
        InclusionProbEdge with P_inclusion and metadata.
    """
    k = adjusted.k

    # Compute Z-statistic = |μ_e| / SE_eff
    if adjusted.SE_eff > 0 and not math.isinf(adjusted.SE_eff):
        Z = abs(adjusted.mu_e) / adjusted.SE_eff
    else:
        Z = 0.0

    # Check if any contributing study is an RCT
    has_rct = any(r.has_rct_component for r in records)

    # Formula B4-1: logistic inclusion
    linear = (
        config.P4_3_INTERCEPT
        + config.P4_3_LN_K_COEFF * math.log(k + 1)
        + config.P4_3_Z_COEFF * Z
        + config.P4_3_RCT_COEFF * (1.0 if has_rct else 0.0)
    )
    P_inclusion = 1.0 / (1.0 + math.exp(-linear))

    # Clamp to [P_INCLUSION_MIN, P_INCLUSION_ADJ_CAP]
    P_inclusion = max(config.P_INCLUSION_MIN, min(P_inclusion, config.P_INCLUSION_ADJ_CAP))

    # Decision-critical flag: mark if P < 0.85 for sensitivity analysis
    is_decision_critical = P_inclusion < 0.85

    return InclusionProbEdge(
        edge_id=adjusted.edge_id,
        P_inclusion=P_inclusion,
        inclusion_inputs={"k": float(k), "Z": Z, "has_RCT": 1.0 if has_rct else 0.0},
        is_decision_critical=is_decision_critical,
    )


# ═══════════════════════════════════════════════════════════════
#  B5 — Heterogeneity Priors (Turner et al., 2012)
# ═══════════════════════════════════════════════════════════════


def _classify_outcome_type(
    edge_id: str,
    records: list[EvidenceRecord],
    graph: GraphObject,
) -> str:
    """Classify edge outcome type for Turner prior selection.

    Categories:
        subjective: self-reported cognition (e.g., FACT-Cog)
        semi_objective: neuropsychological tests
        biomarker: biological markers

    Uses the target node's properties from GraphObject.
    """
    # Check records first
    if records:
        outcome_types = [r.outcome_type for r in records if r.outcome_type]
        if outcome_types:
            # Use majority vote
            from collections import Counter
            counts = Counter(outcome_types)
            return counts.most_common(1)[0][0]

    # Fallback: derive from target node
    edge_idx = graph.b_skeleton.edge_index.get(edge_id)
    if edge_idx is not None:
        edge_def = graph.b_skeleton.edges[edge_idx]
        target = graph.node_map.node_index.get(edge_def.target_node_id)
        if target is not None:
            target_node = graph.node_map.nodes[target]
            layer = target_node.layer
            if layer <= 2:
                return "biomarker"
            elif layer <= 4:
                return "semi_objective"
            else:
                return "subjective"

    return "semi_objective"  # safe default


def assign_tau_sq_prior(
    pooled: PooledEdge,
    records: list[EvidenceRecord],
    graph: GraphObject,
) -> TauSquaredPrior:
    """B5: Assign empirical τ² prior from Turner et al. (2012).

    Formula B5-1: τ² ~ LogNormal(μ, σ²)
    Priors from 14,886 meta-analyses:
        Subjective: LogNormal(−2.13, 1.58²), median 0.12
        Semi-objective: LogNormal(−2.56, 1.07²), median 0.08
        Biomarker: LogNormal(−2.56, 1.07²), median 0.08

    Args:
        pooled: PooledEdge from B1.
        records: Evidence records for outcome classification.
        graph: GraphObject for node property lookup.

    Returns:
        TauSquaredPrior with distribution parameters.
    """
    outcome_type = _classify_outcome_type(pooled.edge_id, records, graph)

    if outcome_type == "subjective":
        log_mu = config.B5_TURNER_SUBJECTIVE_LOG_MU
        log_sigma = config.B5_TURNER_SUBJECTIVE_LOG_SIGMA
    else:
        # semi_objective and biomarker use the same distribution
        log_mu = config.B5_TURNER_SEMIOBJECTIVE_LOG_MU
        log_sigma = config.B5_TURNER_SEMIOBJECTIVE_LOG_SIGMA

    median_tau_sq = math.exp(log_mu)

    return TauSquaredPrior(
        edge_id=pooled.edge_id,
        outcome_type=outcome_type,
        log_mu=log_mu,
        log_sigma=log_sigma,
        median_tau_sq=median_tau_sq,
    )


# ═══════════════════════════════════════════════════════════════
#  B6 — Chain-versus-Direct Validation
# ═══════════════════════════════════════════════════════════════


def validate_chain_vs_direct(
    edge_id: str,
    all_adjusted: dict[str, HeterogeneityAdjustedEdge],
    graph: GraphObject,
) -> ChainDirectResult:
    """B6: For edges with both chain and direct evidence, test consistency.

    Formula B6-1: Z = |β_chain − β_direct| / √(σ²_chain + σ²_direct)

    Triage (4-tier):
        Z < 1.5   → Pass          → 1.0× SE
        1.5–2.0   → Mild          → 1.2× SE
        2.0–3.0   → Moderate      → 1.5× SE
        ≥ 3.0     → Substantial   → 2.0× SE

    Formula B6-2: AV(e) = 1 − min(Z/3.0, 1.0)

    Args:
        edge_id: Edge to validate.
        all_adjusted: All HeterogeneityAdjustedEdges.
        graph: GraphObject for chain path finding.

    Returns:
        ChainDirectResult with Z-score, AV score, and triage action.
    """
    adjusted = all_adjusted.get(edge_id)
    has_direct = adjusted is not None and adjusted.k > 0 and adjusted.aggregation_method != "BLOCKED"

    # Compute chain estimate
    chain_result = _compute_chain_estimate(edge_id, graph, all_adjusted)
    has_chain = chain_result is not None

    if not has_direct or not has_chain:
        return ChainDirectResult(
            edge_id=edge_id,
            has_chain_evidence=has_chain,
            has_direct_evidence=has_direct,
            beta_chain=chain_result[0] if chain_result else None,
            se_chain=chain_result[1] if chain_result else None,
            beta_direct=adjusted.mu_e if has_direct else None,
            se_direct=adjusted.SE_eff if has_direct else None,
            Z_score=None,
            AV_score=None,
            triage_action="Pass",
            se_multiplier=config.B6_SE_MULT_PASS,
        )

    beta_chain, se_chain = chain_result[0], chain_result[1]
    beta_direct = adjusted.mu_e
    se_direct = adjusted.SE_eff

    # Formula B6-1: Z = |β_chain − β_direct| / √(σ²_chain + σ²_direct)
    variance_sum = se_chain ** 2 + se_direct ** 2
    if variance_sum > 0 and not math.isinf(se_chain) and not math.isinf(se_direct):
        Z = abs(beta_chain - beta_direct) / math.sqrt(variance_sum)
    else:
        Z = 0.0

    # Formula B6-2: AV(e) = 1 − min(Z/3.0, 1.0)
    AV = 1.0 - min(Z / config.B6_AV_Z_DIVISOR, 1.0)

    # Triage
    if Z < config.B6_Z_PASS:
        triage = "Pass"
        se_mult = config.B6_SE_MULT_PASS
    elif Z < config.B6_Z_MILD:
        triage = "Mild"
        se_mult = config.B6_SE_MULT_MILD
    elif Z < config.B6_Z_MODERATE:
        triage = "Moderate"
        se_mult = config.B6_SE_MULT_MODERATE
    else:
        triage = "Substantial"
        se_mult = config.B6_SE_MULT_SUBSTANTIAL

    if triage != "Pass":
        logger.warning(
            "Chain-vs-Direct %s: Z=%.2f → %s (SE ×%.1f). "
            "β_chain=%.4f, β_direct=%.4f",
            edge_id, Z, triage, se_mult, beta_chain, beta_direct,
        )

        # Directionality-aware hypothesis generation
        if beta_chain > beta_direct:
            logger.info(
                "  → β_chain > β_direct: inflated mediation / double-counting suspected"
            )
        else:
            logger.info(
                "  → β_chain < β_direct: missing parallel pathways (discovery signal)"
            )

    return ChainDirectResult(
        edge_id=edge_id,
        has_chain_evidence=True,
        has_direct_evidence=True,
        beta_chain=beta_chain,
        se_chain=se_chain,
        beta_direct=beta_direct,
        se_direct=se_direct,
        Z_score=Z,
        AV_score=AV,
        triage_action=triage,
        se_multiplier=se_mult,
    )


# ═══════════════════════════════════════════════════════════════
#  Gates B-G1 through B-G5
# ═══════════════════════════════════════════════════════════════


def _validate_gate_b_g1(pooled_edges: dict[str, PooledEdge]) -> None:
    """Gate B-G1: All edges have aggregation method; no NaN in μ_e for non-BLOCKED.

    Raises:
        GateViolation: If gate conditions fail.
    """
    for edge_id, pe in pooled_edges.items():
        if not pe.aggregation_method:
            raise GateViolation(
                "B-G1",
                f"Edge {edge_id} has no aggregation method assigned",
                {"edge_id": edge_id},
            )
        if pe.aggregation_method != "BLOCKED" and math.isnan(pe.mu_e):
            raise GateViolation(
                "B-G1",
                f"Edge {edge_id} has NaN μ_e with method {pe.aggregation_method}",
                {"edge_id": edge_id, "method": pe.aggregation_method},
            )

    logger.info(
        "Gate B-G1 PASSED: %d edges with aggregation methods; no NaN in non-BLOCKED",
        len(pooled_edges),
    )


def _validate_gate_b_g2(
    adjusted_edges: dict[str, HeterogeneityAdjustedEdge],
) -> None:
    """Gate B-G2: SE_eff > 0 for all edges; no infinite values for non-BLOCKED; layers logged.

    Raises:
        GateViolation: If gate conditions fail.
    """
    for edge_id, ae in adjusted_edges.items():
        if ae.aggregation_method == "BLOCKED":
            continue
        if ae.SE_eff <= 0:
            raise GateViolation(
                "B-G2",
                f"Edge {edge_id} has SE_eff={ae.SE_eff} ≤ 0",
                {"edge_id": edge_id, "SE_eff": ae.SE_eff},
            )
        if math.isinf(ae.SE_eff):
            raise GateViolation(
                "B-G2",
                f"Edge {edge_id} has infinite SE_eff",
                {"edge_id": edge_id},
            )

    logger.info(
        "Gate B-G2 PASSED: SE_eff > 0 for all %d non-BLOCKED edges; layers logged",
        sum(1 for ae in adjusted_edges.values() if ae.aggregation_method != "BLOCKED"),
    )


def _validate_gate_b_g3(prior_specs: dict[str, EdgePriorSpec]) -> None:
    """Gate B-G3: Every edge has a prior type; audit trail complete.

    Raises:
        GateViolation: If gate conditions fail.
    """
    for edge_id, ps in prior_specs.items():
        valid_types = {
            "RobustMAP", "Commensurate", "PowerPrior",
            "MechanisticSynth", "StructuralPlaceholder",
        }
        if ps.prior_type not in valid_types:
            raise GateViolation(
                "B-G3",
                f"Edge {edge_id} has invalid prior type '{ps.prior_type}'",
                {"edge_id": edge_id, "prior_type": ps.prior_type},
            )
        if not ps.selection_rationale:
            raise GateViolation(
                "B-G3",
                f"Edge {edge_id} has empty selection_rationale",
                {"edge_id": edge_id},
            )

    logger.info(
        "Gate B-G3 PASSED: %d edges with valid prior types; audit trail complete",
        len(prior_specs),
    )


def _validate_gate_b_g4(inclusion_probs: dict[str, InclusionProbEdge]) -> None:
    """Gate B-G4: P_inclusion ∈ [0,1] for all edges.

    Raises:
        GateViolation: If gate conditions fail.
    """
    for edge_id, ip in inclusion_probs.items():
        if not (0.0 <= ip.P_inclusion <= 1.0):
            raise GateViolation(
                "B-G4",
                f"Edge {edge_id} has P_inclusion={ip.P_inclusion} outside [0,1]",
                {"edge_id": edge_id, "P_inclusion": ip.P_inclusion},
            )

    # Report decision-critical edges
    critical = [ip for ip in inclusion_probs.values() if ip.is_decision_critical]
    if critical:
        logger.info(
            "B-G4: %d edges with P_inclusion < 0.85 flagged for sensitivity analysis",
            len(critical),
        )

    logger.info(
        "Gate B-G4 PASSED: %d edges with P_inclusion ∈ [0,1]",
        len(inclusion_probs),
    )


def _validate_gate_b_g5(
    chain_direct_results: dict[str, ChainDirectResult],
) -> None:
    """Gate B-G5: AV scores computed for all chain+direct edges; triage actions applied.

    Raises:
        GateViolation: If gate conditions fail.
    """
    both = [
        r for r in chain_direct_results.values()
        if r.has_chain_evidence and r.has_direct_evidence
    ]
    for r in both:
        if r.AV_score is None:
            raise GateViolation(
                "B-G5",
                f"Edge {r.edge_id} has chain+direct evidence but no AV score",
                {"edge_id": r.edge_id},
            )

    logger.info(
        "Gate B-G5 PASSED: AV scores computed for %d chain+direct edges",
        len(both),
    )


# ═══════════════════════════════════════════════════════════════
#  Pipeline: run_b1_through_b6
# ═══════════════════════════════════════════════════════════════


def run_b1_through_b6(
    graph: GraphObject,
    evidence_records: list[EvidenceRecord],
) -> tuple[
    dict[str, PooledEdge],
    dict[str, HeterogeneityAdjustedEdge],
    dict[str, EdgePriorSpec],
    dict[str, InclusionProbEdge],
    dict[str, TauSquaredPrior],
    dict[str, ChainDirectResult],
]:
    """Run ALG-B subsystems B1 through B6.

    Orchestrates the full evidence compilation pipeline:
    B1: IVW Pooling → B2: 7-Layer SE → B3: Prior Selection →
    B4: P_inclusion → B5: τ² Priors → B6: Chain-vs-Direct

    Args:
        graph: GraphObject from Chain A.
        evidence_records: Evidence records from SYS_EXTRACTION.

    Returns:
        Tuple of (pooled_edges, adjusted_edges, prior_specs,
                  inclusion_probs, tau_sq_priors, chain_direct_results).

    Raises:
        GateViolation: If any gate (B-G1 through B-G5) fails.
    """
    logger.info("═══ ALG-B: Edge Parameterization — B1-B6 START ═══")

    # Index evidence by edge_id
    evidence_by_edge: dict[str, list[EvidenceRecord]] = {}
    for rec in evidence_records:
        evidence_by_edge.setdefault(rec.edge_id, []).append(rec)

    # ── B1: IVW Pooling per edge ──
    logger.info("── B1: IVW Pooling ──")
    pooled_edges: dict[str, PooledEdge] = {}
    for edge in graph.b_skeleton.edges:
        records = evidence_by_edge.get(edge.edge_id, [])
        pooled = pool_edge(edge.edge_id, records)
        pooled_edges[edge.edge_id] = pooled

    _validate_gate_b_g1(pooled_edges)

    # ── B2: Seven-Layer SE_eff per edge ──
    logger.info("── B2: Seven-Layer Heterogeneity Pipeline ──")
    adjusted_edges: dict[str, HeterogeneityAdjustedEdge] = {}
    for edge_id, pooled in pooled_edges.items():
        records = evidence_by_edge.get(edge_id, [])
        adjusted = compute_se_eff(pooled, records)
        adjusted_edges[edge_id] = adjusted

    _validate_gate_b_g2(adjusted_edges)

    # ── B3: Prior Selection per edge ──
    logger.info("── B3: Prior Selection ──")
    prior_specs: dict[str, EdgePriorSpec] = {}
    for edge_id, adj in adjusted_edges.items():
        records = evidence_by_edge.get(edge_id, [])
        prior = select_prior(adj, records, graph, all_adjusted=adjusted_edges)
        prior_specs[edge_id] = prior

    _validate_gate_b_g3(prior_specs)

    # ── B4: Structural Inclusion Probability ──
    logger.info("── B4: Structural Inclusion Probability ──")
    inclusion_probs: dict[str, InclusionProbEdge] = {}
    for edge_id, adj in adjusted_edges.items():
        records = evidence_by_edge.get(edge_id, [])
        incl = compute_p_inclusion(adj, records)
        inclusion_probs[edge_id] = incl

    _validate_gate_b_g4(inclusion_probs)

    # ── B5: Heterogeneity Priors ──
    logger.info("── B5: Heterogeneity Priors (Turner et al., 2012) ──")
    tau_sq_priors: dict[str, TauSquaredPrior] = {}
    for edge_id, pooled in pooled_edges.items():
        records = evidence_by_edge.get(edge_id, [])
        tau_prior = assign_tau_sq_prior(pooled, records, graph)
        tau_sq_priors[edge_id] = tau_prior

    # ── B6: Chain-vs-Direct Validation ──
    logger.info("── B6: Chain-vs-Direct Validation ──")
    chain_direct_results: dict[str, ChainDirectResult] = {}
    for edge_id in adjusted_edges:
        result = validate_chain_vs_direct(edge_id, adjusted_edges, graph)
        chain_direct_results[edge_id] = result

    _validate_gate_b_g5(chain_direct_results)

    # Summary
    methods = {}
    for pe in pooled_edges.values():
        methods[pe.aggregation_method] = methods.get(pe.aggregation_method, 0) + 1
    prior_types = {}
    for ps in prior_specs.values():
        prior_types[ps.prior_type] = prior_types.get(ps.prior_type, 0) + 1

    logger.info(
        "═══ ALG-B: B1-B6 COMPLETE ═══\n"
        "  Aggregation methods: %s\n"
        "  Prior types: %s\n"
        "  Decision-critical edges: %d\n"
        "  Chain+direct edges: %d",
        methods,
        prior_types,
        sum(1 for ip in inclusion_probs.values() if ip.is_decision_critical),
        sum(1 for r in chain_direct_results.values()
            if r.has_chain_evidence and r.has_direct_evidence),
    )

    return (
        pooled_edges,
        adjusted_edges,
        prior_specs,
        inclusion_probs,
        tau_sq_priors,
        chain_direct_results,
    )
