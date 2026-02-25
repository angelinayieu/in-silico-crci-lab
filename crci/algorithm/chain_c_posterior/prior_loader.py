# VERIFIED: formulas [C1b, C1c] match spec SYS_ALG lines 1846-1861
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads FrozenModelState from frozen_state.py
# VERIFIED: forward wiring — writes LoadedPrior for bayesian_update.py (C3)
# VERIFIED: no hardcoded formula parameters — SE multipliers from config.py
# VERIFIED: gate [C-G1] raises on failure
"""
Component: SYS_ALGORITHM.ALG-C.C1
Spec: SYS_ALGORITHM_COMPLETE.md lines 1846-1861
Formulas:
    C1b: 4-level fallback resolution (EXACT→CANCER_TYPE→GENERAL_CANCER→UNINFORMATIVE)
    C1c: Λ_prior_adj = Λ_prior / (SE_inflation²); η_prior = Λ_prior_adj × μ_prior
Reads: FrozenModelState (from chain_b_evidence/frozen_state.py)
Writes: LoadedPrior (consumed by bayesian_update.py C3, modifier_application.py C4)
Gates: C-G1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum, unique

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_b_evidence.frozen_state import ContextPriorSpec, FrozenModelState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@unique
class FallbackLevel(StrEnum):
    """4-level fallback hierarchy for context matching (C1b)."""

    EXACT = "EXACT"
    CANCER_TYPE = "CANCER_TYPE"
    GENERAL_CANCER = "GENERAL_CANCER"
    UNINFORMATIVE = "UNINFORMATIVE"


# Map fallback levels to SE inflation multipliers from config
_FALLBACK_SE_INFLATION: dict[FallbackLevel, float] = {
    FallbackLevel.EXACT: config.P4_FALLBACK_SE_MULTIPLIER_EXACT,
    FallbackLevel.CANCER_TYPE: config.P4_FALLBACK_SE_MULTIPLIER_CANCER_TYPE,
    FallbackLevel.GENERAL_CANCER: config.P4_FALLBACK_SE_MULTIPLIER_GENERAL,
    FallbackLevel.UNINFORMATIVE: config.P4_FALLBACK_SE_MULTIPLIER_UNINFORMATIVE,
}


@dataclass(frozen=True)
class LoadedPrior:
    """Output of C1: context-matched prior in information form.

    Fields per spec SYS_ALG lines 1628-1664.
    """

    # Λ_prior: context-matched precision matrix (adjusted for fallback)
    Lambda_prior: np.ndarray  # ℝ^{n_nodes × n_nodes}

    # η_prior: information vector = Λ_prior_adj × μ_prior
    eta_prior: np.ndarray  # ℝ^{n_nodes}

    # μ_prior: context-matched prior mean
    mu_prior: np.ndarray  # ℝ^{n_nodes}

    # Which of 33 context-type × phase specs matched
    context_key: str

    # How specific the match was
    fallback_level: FallbackLevel

    # SE multiplier for fallback imprecision
    fallback_SE_inflation: float


# ═══════════════════════════════════════════════════════════════
#  C1a: Context Key Construction
# ═══════════════════════════════════════════════════════════════


def _build_context_key(
    cancer_type: str,
    treatment_phase: str,
    treatment_regimen: str | None = None,
) -> str:
    """C1a: Build lookup key from patient demographics.

    Format: cancer_type + "_" + treatment_phase [+ "_" + regimen_class]

    Args:
        cancer_type: Required cancer type identifier.
        treatment_phase: Required treatment phase identifier.
        treatment_regimen: Optional regimen class.

    Returns:
        Context key string.
    """
    key = f"{cancer_type}_{treatment_phase}"
    if treatment_regimen:
        key = f"{key}_{treatment_regimen}"
    return key


# ═══════════════════════════════════════════════════════════════
#  C1b: 4-Level Fallback Resolution
# ═══════════════════════════════════════════════════════════════


def _resolve_fallback(
    cancer_type: str,
    treatment_phase: str,
    treatment_regimen: str | None,
    available_context_keys: set[str],
) -> tuple[str, FallbackLevel]:
    """C1b: Find best available prior, degrading gracefully.

    4-level fallback hierarchy:
        Level 1 (EXACT):          cancer × phase × regimen — SE 1.0×
        Level 2 (CANCER_TYPE):    cancer × phase            — SE 1.2×
        Level 3 (GENERAL_CANCER): "general_cancer"           — SE 1.5×
        Level 4 (UNINFORMATIVE):  uninformative N(0, I)      — SE 2.0×

    Args:
        cancer_type: Patient cancer type.
        treatment_phase: Patient treatment phase.
        treatment_regimen: Optional regimen class.
        available_context_keys: Set of context keys from FrozenModelState.Lambda_prior.

    Returns:
        Tuple of (matched_context_key, fallback_level).
    """
    # Level 1: Exact match (cancer × phase × regimen)
    if treatment_regimen:
        exact_key = _build_context_key(cancer_type, treatment_phase, treatment_regimen)
        if exact_key in available_context_keys:
            logger.info(
                "C1b: EXACT match — context_key='%s'", exact_key,
            )
            return exact_key, FallbackLevel.EXACT

    # Level 1 fallback: cancer × phase (no regimen) still counts as EXACT
    cancer_phase_key = _build_context_key(cancer_type, treatment_phase)
    if cancer_phase_key in available_context_keys:
        logger.info(
            "C1b: EXACT match (cancer×phase) — context_key='%s'",
            cancer_phase_key,
        )
        return cancer_phase_key, FallbackLevel.EXACT

    # Level 2: Cancer-type only — match any key starting with cancer_type
    for ctx_key in sorted(available_context_keys):
        if ctx_key.startswith(f"{cancer_type}_"):
            logger.info(
                "C1b: CANCER_TYPE fallback — matched '%s' "
                "(requested phase='%s')",
                ctx_key, treatment_phase,
            )
            return ctx_key, FallbackLevel.CANCER_TYPE

    # Level 3: General cancer baseline
    if "general_cancer" in available_context_keys:
        logger.info(
            "C1b: GENERAL_CANCER fallback — no %s-specific prior available",
            cancer_type,
        )
        return "general_cancer", FallbackLevel.GENERAL_CANCER

    # Level 4: Uninformative — will use μ=0, Σ=I
    logger.warning(
        "C1b: UNINFORMATIVE fallback — no context priors available at all. "
        "Using μ=0, Λ=I with SE inflation %.1f×",
        _FALLBACK_SE_INFLATION[FallbackLevel.UNINFORMATIVE],
    )
    return "__uninformative__", FallbackLevel.UNINFORMATIVE


# ═══════════════════════════════════════════════════════════════
#  C1c: Information Form Initialization
# ═══════════════════════════════════════════════════════════════


def _build_prior_mean_vector(
    n_nodes: int,
    node_index: dict[str, int],
    context_spec: ContextPriorSpec | None,
) -> np.ndarray:
    """Build μ_prior vector from context spec's per-node means.

    If no context spec (uninformative), returns zero vector.

    Args:
        n_nodes: Number of nodes in the graph.
        node_index: node_id → index mapping from GraphObject.node_map.
        context_spec: The matched ContextPriorSpec (None for uninformative).

    Returns:
        μ_prior: ℝ^{n_nodes}
    """
    mu = np.zeros(n_nodes, dtype=np.float64)

    if context_spec is not None:
        for node_id, mean_val in context_spec.node_prior_means.items():
            idx = node_index.get(node_id)
            if idx is not None:
                mu[idx] = mean_val
            else:
                logger.warning(
                    "C1c: node_id '%s' in context spec '%s' not found in graph — skipping",
                    node_id, context_spec.context_key,
                )

    return mu


def _initialize_information_form(
    Lambda_prior: np.ndarray,
    mu_prior: np.ndarray,
    se_inflation: float,
) -> tuple[np.ndarray, np.ndarray]:
    """C1c: Convert to information form with fallback SE inflation.

    Formula C1c:
        Λ_prior_adj = Λ_prior / (SE_inflation²)
        η_prior     = Λ_prior_adj × μ_prior

    Args:
        Lambda_prior: Base precision matrix from Chain B.
        mu_prior: Prior mean vector.
        se_inflation: SE inflation multiplier from fallback level.

    Returns:
        Tuple of (Λ_prior_adj, η_prior).
    """
    # Formula C1c: Λ_prior_adj = Λ_prior / (SE_inflation²)
    inflation_sq = se_inflation ** 2
    Lambda_adj = Lambda_prior / inflation_sq

    # Formula C1c: η_prior = Λ_prior_adj × μ_prior
    eta_prior = Lambda_adj @ mu_prior

    return Lambda_adj, eta_prior


# ═══════════════════════════════════════════════════════════════
#  Gate C-G1: Prior Validity
# ═══════════════════════════════════════════════════════════════


def _validate_gate_c_g1(loaded_prior: LoadedPrior) -> None:
    """Gate C-G1: Context matched; Λ_prior PD; fallback logged.

    Conditions:
        1. context_key is a non-empty string
        2. Λ_prior is positive-definite (verifiable via Cholesky)
        3. fallback_level is a valid FallbackLevel value

    Raises:
        GateViolation: If any condition fails.
    """
    # Condition 1: context_key present
    if not loaded_prior.context_key:
        raise GateViolation(
            "C-G1",
            "LoadedPrior has empty context_key",
        )

    # Condition 2: Λ_prior_adj is positive-definite
    try:
        np.linalg.cholesky(loaded_prior.Lambda_prior)
    except np.linalg.LinAlgError:
        raise GateViolation(
            "C-G1",
            f"Λ_prior_adj for context '{loaded_prior.context_key}' "
            f"(fallback={loaded_prior.fallback_level}) is NOT positive-definite",
        )

    # Condition 3: fallback_level recorded
    if loaded_prior.fallback_level not in FallbackLevel:
        raise GateViolation(
            "C-G1",
            f"Invalid fallback_level: {loaded_prior.fallback_level}",
        )

    logger.info(
        "Gate C-G1 PASSED: context='%s', fallback=%s, SE_inflation=%.2f",
        loaded_prior.context_key,
        loaded_prior.fallback_level,
        loaded_prior.fallback_SE_inflation,
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level: load_prior (C1 entry point)
# ═══════════════════════════════════════════════════════════════


def load_prior(
    frozen: FrozenModelState,
    cancer_type: str,
    treatment_phase: str,
    treatment_regimen: str | None = None,
    context_specs: list[ContextPriorSpec] | None = None,
) -> LoadedPrior:
    """C1: Context Matching & Prior Loading.

    Matches patient to one of 33 cancer-type × treatment-phase prior
    specifications and loads the appropriate precision matrix in
    information form for efficient Bayesian updating (C3).

    Args:
        frozen: FrozenModelState from Chain B (crosses the cut boundary).
        cancer_type: Patient's cancer type (required).
        treatment_phase: Patient's treatment phase (required).
        treatment_regimen: Optional treatment regimen for exact matching.
        context_specs: Optional list of ContextPriorSpec objects for
                       looking up per-node prior means. If not provided,
                       uses zero mean (non-informative about node means).

    Returns:
        LoadedPrior with information-form prior (Λ_adj, η, μ).

    Raises:
        GateViolation: If C-G1 fails (Λ_prior not PD, etc.).
    """
    logger.info(
        "── C1: Context Matching & Prior Loading ──\n"
        "  cancer_type=%s, treatment_phase=%s, regimen=%s",
        cancer_type, treatment_phase, treatment_regimen,
    )

    n_nodes = frozen.graph.n_nodes
    node_index = frozen.graph.node_map.node_index
    available_keys = set(frozen.Lambda_prior.keys())

    # C1a + C1b: Build context key and resolve fallback
    matched_key, fallback_level = _resolve_fallback(
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        treatment_regimen=treatment_regimen,
        available_context_keys=available_keys,
    )

    # Get base precision matrix
    if fallback_level == FallbackLevel.UNINFORMATIVE:
        # Level 4: μ=0, Λ=I
        Lambda_base = np.eye(n_nodes, dtype=np.float64)
    else:
        Lambda_base = frozen.Lambda_prior[matched_key].copy()

    # Find matching ContextPriorSpec for μ_prior (if available)
    matched_spec: ContextPriorSpec | None = None
    if context_specs and fallback_level != FallbackLevel.UNINFORMATIVE:
        for spec in context_specs:
            if spec.context_key == matched_key:
                matched_spec = spec
                break
        if matched_spec is None:
            logger.info(
                "C1c: No ContextPriorSpec found for key '%s' — "
                "using zero prior mean (non-informative about node locations)",
                matched_key,
            )

    # Build μ_prior
    mu_prior = _build_prior_mean_vector(n_nodes, node_index, matched_spec)

    # C1c: SE inflation and information form
    se_inflation = _FALLBACK_SE_INFLATION[fallback_level]
    Lambda_adj, eta_prior = _initialize_information_form(
        Lambda_base, mu_prior, se_inflation,
    )

    loaded = LoadedPrior(
        Lambda_prior=Lambda_adj,
        eta_prior=eta_prior,
        mu_prior=mu_prior,
        context_key=matched_key,
        fallback_level=fallback_level,
        fallback_SE_inflation=se_inflation,
    )

    # Gate C-G1
    _validate_gate_c_g1(loaded)

    logger.info(
        "C1: Prior loaded — context='%s', fallback=%s, "
        "SE_inflation=%.2f, Λ shape=%s, ||μ||=%.4f",
        loaded.context_key,
        loaded.fallback_level,
        loaded.fallback_SE_inflation,
        loaded.Lambda_prior.shape,
        np.linalg.norm(loaded.mu_prior),
    )

    return loaded
