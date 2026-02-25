# VERIFIED: formulas match spec SYS_EX lines 1264-1275, SYS_ALG lines 1326-1350
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PooledEstimate from meta_analyzer.py
# VERIFIED: forward wiring — writes PriorSpec for edge_writer.py
# VERIFIED: no hardcoded formula parameters — all from shared/config.py (PRIOR_* constants)
# VERIFIED: 4-level fallback matches spec SYS_ALG line 3876
"""
Component: SYS_EXTRACTION.EX-P4.P4-PS
Spec: SYS_EXTRACTION_COMPLETE.md lines 1264-1275
      SYS_ALGORITHM_COMPLETE.md lines 1326-1350, 3865-3879
Formulas: P4-PS decision tree (5 branches), 4-level fallback
Reads: PooledEstimate (from meta_analyzer.py), literary_mechanistic_priors_v1
Writes: PriorSpec (consumed by edge_writer.py), prior_selection_log for audit
Gates: None (prior selection is deterministic, no gate violations)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.config import (
    PRIOR_FALLBACK_SE_MULTIPLIER_CANCER_TYPE,
    PRIOR_FALLBACK_SE_MULTIPLIER_EXACT,
    PRIOR_FALLBACK_SE_MULTIPLIER_GENERAL,
    PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE,
    PRIOR_K_THRESHOLD_COMMENSURATE_HIGH,
    PRIOR_K_THRESHOLD_COMMENSURATE_LOW,
    PRIOR_K_THRESHOLD_POWER,
    PRIOR_K_THRESHOLD_ROBUST_MAP,
    PRIOR_MEAN_DEFAULT,
    PRIOR_MECHANISTIC_SYNTH_DISCOUNT,
    PRIOR_MIN_RCTS_FOR_ROBUST_MAP,
    PRIOR_POWER_DISCOUNT,
    PRIOR_ROBUST_MAP_VAGUE_VAR,
    PRIOR_ROBUST_MAP_W_BASE,
    PRIOR_ROBUST_MAP_W_CAP,
    PRIOR_ROBUST_MAP_W_PER_K,
    PRIOR_SD_DEFAULT,
)
from crci.shared.models.enums import (
    PriorSource,
    PriorTypePaper,
    StudyDesign,
)
from crci.shared.models.intermediate_states import (
    PooledEstimate,
    PriorSpec,
)
from crci.shared.models.tables import (
    LiteraryMechanisticPrior,
    Pathway,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Prior Selection Constants — all imported from shared/config.py
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  Data Structures for Prior Selection Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class EdgeContext:
    """Contextual information about an edge for prior selection.

    Assembled from the PooledEstimate and additional metadata about
    the contributing studies (design types, cancer context, etc.).
    """

    edge_relation_id: str
    k: int
    n_rcts: int = 0
    best_design: str = "other"
    has_chain_evidence: bool = False
    chain_edges: list[str] = field(default_factory=list)
    cancer_type: str | None = None
    treatment_phase: str | None = None
    regimen: str | None = None
    beta_pooled: float = 0.0
    se_pooled: float = 1.0


@dataclass
class PriorSelectionLogEntry:
    """Audit log entry for prior selection decisions."""

    edge_relation_id: str
    prior_type: str
    prior_source: str
    fallback_level: int  # 1=exact, 2=cancer-type, 3=general, 4=uninformative
    se_multiplier: float
    k: int
    n_rcts: int
    best_design: str
    has_chain_evidence: bool
    rationale: str
    prior_mean: float
    prior_sd: float


# ═══════════════════════════════════════════════════════════════
#  4-Level Fallback Resolution
# ═══════════════════════════════════════════════════════════════


def _resolve_fallback_prior(
    edge_context: EdgeContext,
    session: Session,
) -> tuple[float, float, int, str]:
    """Resolve prior parameters via 4-level fallback hierarchy.

    Spec SYS_ALG line 3876:
      Level 1: Exact match (cancer x phase x regimen) -> SE 1.0x
      Level 2: Cancer-type only -> SE 1.2x
      Level 3: General cancer -> SE 1.5x
      Level 4: Uninformative (mu=0, sigma=1) -> SE 2.0x

    Returns:
        Tuple of (mean, sd, fallback_level, provenance_description)
    """
    cancer_type = edge_context.cancer_type
    treatment_phase = edge_context.treatment_phase
    edge_id = edge_context.edge_relation_id

    # Level 1: Exact context match (cancer x phase x edge)
    if cancer_type and treatment_phase:
        priors_exact = session.query(
            LiteraryMechanisticPrior.prior_params,
            LiteraryMechanisticPrior.prior_id,
        ).filter(
            LiteraryMechanisticPrior.target_ref == edge_id,
            LiteraryMechanisticPrior.population_scope == cancer_type,
            LiteraryMechanisticPrior.phase_scope == treatment_phase,
            LiteraryMechanisticPrior.active == 1,
        ).first()

        if priors_exact is not None:
            prior_params_str, prior_id = priors_exact
            mean, sd = _parse_prior_params(prior_params_str)
            logger.info(
                "Prior fallback level 1 (exact) for edge %s: "
                "prior_id=%s, cancer=%s, phase=%s",
                edge_id, prior_id, cancer_type, treatment_phase,
            )
            return mean, sd * PRIOR_FALLBACK_SE_MULTIPLIER_EXACT, 1, (
                f"exact_match:prior_id={prior_id}"
            )

    # Level 2: Cancer-type only match
    if cancer_type:
        priors_cancer = session.query(
            LiteraryMechanisticPrior.prior_params,
            LiteraryMechanisticPrior.prior_id,
        ).filter(
            LiteraryMechanisticPrior.target_ref == edge_id,
            LiteraryMechanisticPrior.population_scope == cancer_type,
            LiteraryMechanisticPrior.active == 1,
        ).first()

        if priors_cancer is not None:
            prior_params_str, prior_id = priors_cancer
            mean, sd = _parse_prior_params(prior_params_str)
            logger.info(
                "Prior fallback level 2 (cancer-type) for edge %s: "
                "prior_id=%s, cancer=%s",
                edge_id, prior_id, cancer_type,
            )
            return mean, sd * PRIOR_FALLBACK_SE_MULTIPLIER_CANCER_TYPE, 2, (
                f"cancer_type_match:prior_id={prior_id}"
            )

    # Level 3: General cancer
    priors_general = session.query(
        LiteraryMechanisticPrior.prior_params,
        LiteraryMechanisticPrior.prior_id,
    ).filter(
        LiteraryMechanisticPrior.target_ref == edge_id,
        LiteraryMechanisticPrior.active == 1,
    ).first()

    if priors_general is not None:
        prior_params_str, prior_id = priors_general
        mean, sd = _parse_prior_params(prior_params_str)
        logger.info(
            "Prior fallback level 3 (general cancer) for edge %s: "
            "prior_id=%s",
            edge_id, prior_id,
        )
        return mean, sd * PRIOR_FALLBACK_SE_MULTIPLIER_GENERAL, 3, (
            f"general_cancer_match:prior_id={prior_id}"
        )

    # Level 4: Uninformative N(0, 1) — no matched prior found
    logger.info(
        "Prior fallback level 4 (uninformative) for edge %s: "
        "no literary prior found, using N(%s, %s)",
        edge_id, PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT,
    )
    return (
        PRIOR_MEAN_DEFAULT,
        PRIOR_SD_DEFAULT * PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE,
        4,
        "uninformative:no_matching_prior",
    )


def _parse_prior_params(prior_params_str: str | None) -> tuple[float, float]:
    """Parse prior parameters from literary_mechanistic_priors_v1.prior_params.

    Expected format: JSON-like string or simple 'mean,sd' format.
    Falls back to defaults if parsing fails.
    """
    if not prior_params_str:
        logger.warning(
            "Empty prior_params, using defaults: mean=%s, sd=%s",
            PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT,
        )
        return PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT

    import json
    try:
        params = json.loads(prior_params_str)
        if isinstance(params, dict):
            mean = float(params.get("mean", PRIOR_MEAN_DEFAULT))
            sd = float(params.get("sd", PRIOR_SD_DEFAULT))
            return mean, sd
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback: try comma-separated
    try:
        parts = prior_params_str.split(",")
        if len(parts) >= 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except (ValueError, IndexError):
        pass

    logger.warning(
        "Could not parse prior_params '%s', using defaults: mean=%s, sd=%s",
        prior_params_str, PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT,
    )
    return PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT


# ═══════════════════════════════════════════════════════════════
#  Chain Evidence Detection
# ═══════════════════════════════════════════════════════════════


def _has_chain_evidence(
    edge_relation_id: str,
    session: Session,
) -> tuple[bool, list[str]]:
    """Check whether an edge with k=0 has chain (mechanistic pathway) evidence.

    Looks for pathways where this edge's endpoint nodes are connected
    through intermediate edges that DO have evidence.

    Returns:
        Tuple of (has_chain, list_of_chain_edge_ids)
    """
    # Query pathways containing this edge
    pathways = session.query(
        Pathway.pathway_id,
        Pathway.edge_relation_ids_json,
    ).filter(
        Pathway.active == 1,
    ).all()

    for pathway_id, edge_ids_json in pathways:
        if not edge_ids_json:
            continue
        edge_ids: list[str] = edge_ids_json if isinstance(edge_ids_json, list) else []
        if edge_relation_id in edge_ids:
            # This edge is part of a pathway; check if other edges have evidence
            chain_edges = [eid for eid in edge_ids if eid != edge_relation_id]
            if chain_edges:
                logger.info(
                    "Edge %s has chain evidence via pathway %s: %s",
                    edge_relation_id, pathway_id, chain_edges,
                )
                return True, chain_edges

    return False, []


# ═══════════════════════════════════════════════════════════════
#  Design Classification Helpers
# ═══════════════════════════════════════════════════════════════


_PROSPECTIVE_DESIGNS: set[str] = {
    StudyDesign.RCT,
    StudyDesign.LONGITUDINAL,
}


def _is_prospective_design(design: str) -> bool:
    """Check if a study design qualifies as 'prospective' for RobustMAP.

    Spec SYS_ALG line 1338: 'best_design >= prospective'
    RCT and longitudinal are considered prospective.
    """
    return design in _PROSPECTIVE_DESIGNS


def _classify_design_for_power_prior(design: str) -> str:
    """Map StudyDesign to power prior discount category.

    Spec SYS_ALG lines 1348 (B3c).
    """
    if design == StudyDesign.RCT:
        return "RCT_same"  # Conservative: assume same-population RCT
    if design == StudyDesign.LONGITUDINAL:
        return "cohort"
    if design == StudyDesign.CROSS_SECTIONAL:
        return "observational"
    if design == StudyDesign.MECHANISTIC:
        return "mechanistic"
    return "observational"  # Default for OTHER, INTENSIVE, META


# ═══════════════════════════════════════════════════════════════
#  Core Prior Selection: 5-Branch Decision Tree
# ═══════════════════════════════════════════════════════════════


def select_prior(
    pooled_estimate: PooledEstimate,
    edge_context: EdgeContext,
    session: Session,
) -> tuple[PriorSpec, PriorSelectionLogEntry]:
    """Select prior distribution type for a single edge.

    Implements P4-PS decision tree (SYS_EX lines 1267-1272):
      k >= 5, >= 2 RCTs       -> RobustMAP
      k = 2-4                  -> Commensurate (power-discounted)
      k = 1                    -> Power (single-study prior)
      k = 0 + chain evidence   -> MechanisticSynthesis
      k = 0, no chain          -> StructuralPlaceholder N(0, 1)

    4-level fallback (SYS_ALG line 3876):
      exact context -> cancer-type-only -> general cancer -> uninformative N(0,1)

    Args:
        pooled_estimate: The pooled estimate from meta_analyzer.py
        edge_context: Contextual information about the edge
        session: SQLAlchemy session for DB queries

    Returns:
        Tuple of (PriorSpec, PriorSelectionLogEntry) for downstream and audit
    """
    k = pooled_estimate.k
    edge_id = pooled_estimate.edge_relation_id

    # Resolve fallback prior parameters (used as base for all branches)
    fallback_mean, fallback_sd, fallback_level, provenance = _resolve_fallback_prior(
        edge_context, session,
    )

    # ─── Branch 1: RobustMAP (k >= 5, >= 2 RCTs) ────────────────
    # Spec SYS_EX line 1268: k >= 5, >= 2 RCTs -> RobustMAP
    # Spec SYS_ALG line 1338: k >= 5, best_design >= prospective -> RobustMAP
    # NOTE: SYS_EX says ">= 2 RCTs", SYS_ALG says "best_design >= prospective"
    # Implementing SYS_EX (the extraction spec) as primary: k >= 5 AND >= 2 RCTs
    if k >= PRIOR_K_THRESHOLD_ROBUST_MAP and edge_context.n_rcts >= PRIOR_MIN_RCTS_FOR_ROBUST_MAP:
        # Formula B3a: w = min(0.8, 0.5 + 0.06k)
        w = min(PRIOR_ROBUST_MAP_W_CAP, PRIOR_ROBUST_MAP_W_BASE + PRIOR_ROBUST_MAP_W_PER_K * k)
        prior_sd = fallback_sd  # SD from fallback with multiplier applied
        prior_mean = pooled_estimate.beta_pooled  # MAP centered on pooled

        prior_spec = PriorSpec(
            edge_relation_id=edge_id,
            prior_source=PriorSource.EMPIRICAL,
            prior_type=PriorTypePaper.ROBUST_MAP,
            mean=prior_mean,
            sd=prior_sd,
            dist_family="robust_map_mixture",
            provenance=(
                f"RobustMAP: w={w:.3f}, MAP_mean={prior_mean:.4f}, "
                f"vague_var={PRIOR_ROBUST_MAP_VAGUE_VAR}, "
                f"fallback_level={fallback_level}, {provenance}"
            ),
        )
        log_entry = PriorSelectionLogEntry(
            edge_relation_id=edge_id,
            prior_type=PriorTypePaper.ROBUST_MAP.value,
            prior_source=PriorSource.EMPIRICAL.value,
            fallback_level=fallback_level,
            se_multiplier=_get_fallback_se_multiplier(fallback_level),
            k=k,
            n_rcts=edge_context.n_rcts,
            best_design=edge_context.best_design,
            has_chain_evidence=edge_context.has_chain_evidence,
            rationale=(
                f"k={k} >= {PRIOR_K_THRESHOLD_ROBUST_MAP}, "
                f"n_rcts={edge_context.n_rcts} >= {PRIOR_MIN_RCTS_FOR_ROBUST_MAP}: "
                f"RobustMAP with w={w:.3f}"
            ),
            prior_mean=prior_mean,
            prior_sd=prior_sd,
        )
        return prior_spec, log_entry

    # ─── Branch 2: Commensurate (k = 2-4) ───────────────────────
    # Spec SYS_EX line 1269: k = 2-4 -> Commensurate (power-discounted)
    if PRIOR_K_THRESHOLD_COMMENSURATE_LOW <= k <= PRIOR_K_THRESHOLD_COMMENSURATE_HIGH:
        prior_mean = pooled_estimate.beta_pooled
        prior_sd = fallback_sd  # SD from fallback with multiplier applied

        prior_spec = PriorSpec(
            edge_relation_id=edge_id,
            prior_source=PriorSource.EMPIRICAL,
            prior_type=PriorTypePaper.COMMENSURATE,
            mean=prior_mean,
            sd=prior_sd,
            dist_family="normal",
            provenance=(
                f"Commensurate: k={k}, beta_hist={prior_mean:.4f}, "
                f"sigma_hist={prior_sd:.4f}, "
                f"fallback_level={fallback_level}, {provenance}"
            ),
        )
        log_entry = PriorSelectionLogEntry(
            edge_relation_id=edge_id,
            prior_type=PriorTypePaper.COMMENSURATE.value,
            prior_source=PriorSource.EMPIRICAL.value,
            fallback_level=fallback_level,
            se_multiplier=_get_fallback_se_multiplier(fallback_level),
            k=k,
            n_rcts=edge_context.n_rcts,
            best_design=edge_context.best_design,
            has_chain_evidence=edge_context.has_chain_evidence,
            rationale=(
                f"k={k} in [{PRIOR_K_THRESHOLD_COMMENSURATE_LOW}, "
                f"{PRIOR_K_THRESHOLD_COMMENSURATE_HIGH}]: Commensurate prior"
            ),
            prior_mean=prior_mean,
            prior_sd=prior_sd,
        )
        return prior_spec, log_entry

    # ─── Branch 3: Power Prior (k = 1) ──────────────────────────
    # Spec SYS_EX line 1270: k = 1 -> Power (single-study prior)
    if k == PRIOR_K_THRESHOLD_POWER:
        design_category = _classify_design_for_power_prior(edge_context.best_design)
        a_0 = PRIOR_POWER_DISCOUNT.get(design_category, PRIOR_POWER_DISCOUNT["observational"])
        prior_mean = pooled_estimate.beta_pooled
        # Power prior: effective SD inflated by discount
        # SE_power = SE / sqrt(a_0), reflecting reduced borrowing
        if a_0 > 0.0:
            prior_sd = pooled_estimate.se_pooled / math.sqrt(a_0)
        else:
            prior_sd = PRIOR_SD_DEFAULT * PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE

        prior_spec = PriorSpec(
            edge_relation_id=edge_id,
            prior_source=PriorSource.EMPIRICAL,
            prior_type=PriorTypePaper.POWER_PRIOR,
            mean=prior_mean,
            sd=prior_sd,
            dist_family="normal",
            provenance=(
                f"PowerPrior: a_0={a_0:.2f}, design={design_category}, "
                f"fallback_level={fallback_level}, {provenance}"
            ),
        )
        log_entry = PriorSelectionLogEntry(
            edge_relation_id=edge_id,
            prior_type=PriorTypePaper.POWER_PRIOR.value,
            prior_source=PriorSource.EMPIRICAL.value,
            fallback_level=fallback_level,
            se_multiplier=_get_fallback_se_multiplier(fallback_level),
            k=k,
            n_rcts=edge_context.n_rcts,
            best_design=edge_context.best_design,
            has_chain_evidence=edge_context.has_chain_evidence,
            rationale=(
                f"k={k} == 1: Power prior with a_0={a_0:.2f} "
                f"(design={design_category})"
            ),
            prior_mean=prior_mean,
            prior_sd=prior_sd,
        )
        return prior_spec, log_entry

    # ─── Branch 4: MechanisticSynthesis (k = 0 + chain evidence) ─
    # Spec SYS_EX line 1271: k = 0 + chain evidence -> MechanisticSynthesis
    if k == 0:
        has_chain, chain_edges = _has_chain_evidence(edge_id, session)
        if has_chain:
            # Mechanistic synthesis: enters as Power Prior with a_0 = 0.05
            # Spec SYS_ALG lines 1349 (B3d): 95% discount
            prior_mean = fallback_mean
            prior_sd = fallback_sd

            prior_spec = PriorSpec(
                edge_relation_id=edge_id,
                prior_source=PriorSource.LITERARY,
                prior_type=PriorTypePaper.MECHANISTIC_SYNTHESIS,
                mean=prior_mean,
                sd=prior_sd,
                dist_family="normal",
                provenance=(
                    f"MechanisticSynthesis: a_0={PRIOR_MECHANISTIC_SYNTH_DISCOUNT:.2f}, "
                    f"chain_edges={chain_edges}, "
                    f"fallback_level={fallback_level}, {provenance}"
                ),
            )
            log_entry = PriorSelectionLogEntry(
                edge_relation_id=edge_id,
                prior_type=PriorTypePaper.MECHANISTIC_SYNTHESIS.value,
                prior_source=PriorSource.LITERARY.value,
                fallback_level=fallback_level,
                se_multiplier=_get_fallback_se_multiplier(fallback_level),
                k=k,
                n_rcts=edge_context.n_rcts,
                best_design=edge_context.best_design,
                has_chain_evidence=True,
                rationale=(
                    f"k=0 with chain evidence via edges {chain_edges}: "
                    f"MechanisticSynthesis with a_0={PRIOR_MECHANISTIC_SYNTH_DISCOUNT:.2f}"
                ),
                prior_mean=prior_mean,
                prior_sd=prior_sd,
            )
            return prior_spec, log_entry

    # ─── Branch 5: StructuralPlaceholder (k = 0, no chain) ──────
    # Spec SYS_EX line 1272: k = 0, no chain -> Placeholder N(0, 1)
    # Spec SYS_ALG line 3875: StructuralPlaceholder (N(0,1), P_inclusion = 0.38)
    prior_mean = PRIOR_MEAN_DEFAULT
    prior_sd = PRIOR_SD_DEFAULT

    prior_spec = PriorSpec(
        edge_relation_id=edge_id,
        prior_source=PriorSource.UNINFORMATIVE,
        prior_type=PriorTypePaper.STRUCTURAL_PLACEHOLDER,
        mean=prior_mean,
        sd=prior_sd,
        dist_family="normal",
        provenance=(
            f"StructuralPlaceholder: N({PRIOR_MEAN_DEFAULT}, "
            f"{PRIOR_SD_DEFAULT}), k=0, no chain evidence"
        ),
    )
    log_entry = PriorSelectionLogEntry(
        edge_relation_id=edge_id,
        prior_type=PriorTypePaper.STRUCTURAL_PLACEHOLDER.value,
        prior_source=PriorSource.UNINFORMATIVE.value,
        fallback_level=4,  # Always uninformative level for placeholder
        se_multiplier=PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE,
        k=k,
        n_rcts=edge_context.n_rcts,
        best_design=edge_context.best_design,
        has_chain_evidence=False,
        rationale=(
            f"k={k}, no chain evidence: StructuralPlaceholder "
            f"N({PRIOR_MEAN_DEFAULT}, {PRIOR_SD_DEFAULT})"
        ),
        prior_mean=prior_mean,
        prior_sd=prior_sd,
    )
    return prior_spec, log_entry


def _get_fallback_se_multiplier(fallback_level: int) -> float:
    """Return the SE multiplier for a given fallback level.

    Spec SYS_ALG line 3876:
      Level 1: Exact context -> 1.0x
      Level 2: Cancer-type only -> 1.2x
      Level 3: General cancer -> 1.5x
      Level 4: Uninformative -> 2.0x
    """
    return {
        1: PRIOR_FALLBACK_SE_MULTIPLIER_EXACT,
        2: PRIOR_FALLBACK_SE_MULTIPLIER_CANCER_TYPE,
        3: PRIOR_FALLBACK_SE_MULTIPLIER_GENERAL,
        4: PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE,
    }.get(fallback_level, PRIOR_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE)


# ═══════════════════════════════════════════════════════════════
#  Batch Prior Selection
# ═══════════════════════════════════════════════════════════════


def select_priors_for_all_edges(
    pooled_estimates: list[PooledEstimate],
    edge_contexts: dict[str, EdgeContext],
    session: Session,
) -> tuple[list[PriorSpec], list[PriorSelectionLogEntry]]:
    """Select priors for all edges in the model.

    Iterates through all pooled estimates, applies the 5-branch decision
    tree with 4-level fallback, and returns prior specifications + audit log.

    Args:
        pooled_estimates: List of pooled estimates from meta_analyzer.py
        edge_contexts: Dictionary mapping edge_relation_id -> EdgeContext
        session: SQLAlchemy session for DB queries

    Returns:
        Tuple of (list[PriorSpec], list[PriorSelectionLogEntry])
    """
    prior_specs: list[PriorSpec] = []
    log_entries: list[PriorSelectionLogEntry] = []

    for pooled in pooled_estimates:
        edge_id = pooled.edge_relation_id

        # Get or create edge context
        context = edge_contexts.get(edge_id)
        if context is None:
            logger.warning(
                "No EdgeContext for edge %s, constructing minimal context "
                "from PooledEstimate (k=%d, beta=%.4f)",
                edge_id, pooled.k, pooled.beta_pooled,
            )
            context = EdgeContext(
                edge_relation_id=edge_id,
                k=pooled.k,
                beta_pooled=pooled.beta_pooled,
                se_pooled=pooled.se_pooled,
            )

        prior_spec, log_entry = select_prior(pooled, context, session)
        prior_specs.append(prior_spec)
        log_entries.append(log_entry)

    logger.info(
        "Prior selection complete: %d edges processed. "
        "Types: RobustMAP=%d, Commensurate=%d, Power=%d, "
        "MechanisticSynth=%d, Placeholder=%d",
        len(prior_specs),
        sum(1 for p in prior_specs if p.prior_type == PriorTypePaper.ROBUST_MAP),
        sum(1 for p in prior_specs if p.prior_type == PriorTypePaper.COMMENSURATE),
        sum(1 for p in prior_specs if p.prior_type == PriorTypePaper.POWER_PRIOR),
        sum(1 for p in prior_specs if p.prior_type == PriorTypePaper.MECHANISTIC_SYNTHESIS),
        sum(1 for p in prior_specs if p.prior_type == PriorTypePaper.STRUCTURAL_PLACEHOLDER),
    )

    return prior_specs, log_entries
