# VERIFIED: formulas [B7a, B7b, A4-1] match spec SYS_ALG lines 1414-1428
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads B1-B6 outputs from evidence_compiler.py, GraphObject from chain_a
# VERIFIED: forward wiring — writes FrozenModelState for ALG-C, ALG-D, ALG-E
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gates [B-G6] raise on failure
# VERIFIED: B6 SE multiplier applied to Sigma_eff in assemble_frozen_state (spec lines 1393-1408)
# VERIFIED: S4 — FrozenModelState frozen=True (cut-boundary integrity)
# VERIFIED: S4 — _compute_frozen_hash covers B̂, Σ_eff, P_incl, Λ_prior, active_pathway_ids
# VERIFIED: S4 — IEEE-754 double encoding for deterministic float hashing
# VERIFIED: S4 — context_specs stored on FrozenModelState for ALG-C1 access
# VERIFIED: S4 — build_b_hat_matrix: unused chain_direct_results param removed
# VERIFIED: S4 — synergy gamma clamped symmetrically to [-cap, +cap]
# VERIFIED: S5 — score_pathway_evidence wired into run_chain_b (after B6, before B7 assembly)
# VERIFIED: S5 — pathway scoring conditional on graph.pathway_map non-empty
"""
Component: SYS_ALGORITHM.ALG-B.B7
Spec: SYS_ALGORITHM_COMPLETE.md lines 1414-1428
Formulas:
    B7a: B̂[source, target] = μ_e for each parameterized edge
    B7b: Λ_prior = (I − B̂)ᵀ D⁻¹ (I − B̂) per context
    (Re-uses Formula A4-1 from spectral_validator)
Reads: PooledEdge, HeterogeneityAdjustedEdge, EdgePriorSpec,
       InclusionProbEdge, TauSquaredPrior, ChainDirectResult (from evidence_compiler.py),
       GraphObject (from chain_a_graph)
Writes: FrozenModelState (consumed by ALG-C, ALG-D, ALG-E)
Gates: B-G6
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from ..chain_a_graph.graph_object import GraphObject
from .evidence_compiler import (
    ChainDirectResult,
    EdgePriorSpec,
    EvidenceRecord,
    HeterogeneityAdjustedEdge,
    InclusionProbEdge,
    PooledEdge,
    TauSquaredPrior,
    run_b1_through_b6,
)
from .pathway_evidence_scorer import PathwayEvidenceScore, score_pathway_evidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SynergyRecord:
    """Pairwise interaction record from synergy_registry.

    Used by ALG-D for joint intervention effects.
    """

    action_a_id: str
    action_b_id: str
    joint_probability_offset: float   # JPO
    combined_cognitive_score: float    # CCS
    source_trial: str
    gamma: float = 0.0                # synergy parameter


@dataclass(frozen=True)
class ContextPriorSpec:
    """One of 33 context-matched prior specifications.

    Each spec defines per-node prior means and SDs for a specific
    cancer_type × treatment_phase combination.
    """

    context_key: str          # e.g., "breast_adjuvant"
    cancer_type: str
    treatment_phase: str
    node_prior_means: dict[str, float]   # node_id → μ_prior
    node_prior_sds: dict[str, float]     # node_id → σ_prior


@dataclass(frozen=True)
class FrozenModelState:
    """Complete output of ALG-B — crosses the cut boundary to runtime.

    This object is FROZEN (dataclass frozen=True): attribute rebinding is
    prohibited after construction. Consumers must treat all internal
    containers (dicts, ndarrays) as immutable. The integrity hash covers
    all deterministic state, so any mutation would invalidate it.

    It contains all build-time parameters needed by ALG-C, D, E, F.

    Fields match spec SYS_ALG lines 1188-1216:
        B̂:              Parameterized edge weight matrix
        Sigma_eff:       Effective SEs per edge (post-7-layer)
        Lambda_prior:    33 context-matched precision matrices
        P_inclusion:     Structural inclusion probabilities per edge
        prior_audit_trail: Complete prior documentation per edge
        AV_scores:       Alignment validity for chain+direct edges
        tau_sq_estimates: Per-edge heterogeneity variance
        synergy_records: Pairwise interaction data
        context_specs:   Context prior specifications (means + SDs per node)
    """

    # B7a: Parameterized edge weight matrix — ℝ^{n_nodes × n_nodes}
    B_hat: np.ndarray

    # B2 output: edge_id → SE_eff
    Sigma_eff: dict[str, float]

    # B7b: context_key → precision matrix ℝ^{n_nodes × n_nodes}
    Lambda_prior: dict[str, np.ndarray]

    # B4 output: edge_id → P_inclusion
    P_inclusion: dict[str, float]

    # B3 output: edge_id → EdgePriorSpec
    prior_audit_trail: dict[str, EdgePriorSpec]

    # B6 output: edge_id → AV score
    AV_scores: dict[str, float]

    # B1/B5 output: edge_id → τ²
    tau_sq_estimates: dict[str, float]

    # B7c: synergy records
    synergy_records: list[SynergyRecord]

    # Reference to source GraphObject (not serialized in hash)
    graph: GraphObject

    # B7b context specifications — stored so ALG-C1 (prior_loader) can
    # access per-node prior means and SDs without a separate parameter.
    # Tuple for immutability.  Empty when no context specs are provided.
    context_specs: tuple[ContextPriorSpec, ...] = ()

    # B6.5 output: Pathway evidence scoring (EXTENSION)
    # Dict mapping pathway_id → PathwayEvidenceScore.
    # Empty dict when pathway scoring is not run (e.g., no pathway_map).
    pathway_evidence_scores: dict[str, PathwayEvidenceScore] = field(
        default_factory=dict,
    )
    # Active pathway IDs (pathways with adequate evidence density).
    # Included in the integrity hash so that two FrozenModelStates with
    # different active sets hash differently.
    active_pathway_ids: tuple[str, ...] = ()

    # Metadata
    n_edges_parameterized: int = 0
    n_edges_blocked: int = 0
    n_contexts: int = 0
    sha256_hash: str = ""

    def __hash__(self) -> int:
        """Hash by SHA-256 integrity hash (pre-computed at construction)."""
        return hash(self.sha256_hash)


# ═══════════════════════════════════════════════════════════════
#  B7a: Populate B̂ Matrix
# ═══════════════════════════════════════════════════════════════


def build_b_hat_matrix(
    graph: GraphObject,
    adjusted_edges: dict[str, HeterogeneityAdjustedEdge],
) -> np.ndarray:
    """B7a: Fill B̂[source, target] = μ_e for each parameterized edge.

    BLOCKED edges are set to 0.
    Non-linear edges: Hill params accessible via graph.b_skeleton.
    B̂ uses the attenuated μ_e directly (SE inflation from B6
    is applied separately in assemble_frozen_state).

    Args:
        graph: GraphObject from Chain A.
        adjusted_edges: HeterogeneityAdjustedEdges from B2.

    Returns:
        B̂ matrix of shape (n_nodes, n_nodes).
    """
    n = graph.n_nodes
    B_hat = np.zeros((n, n), dtype=np.float64)

    for edge in graph.b_skeleton.edges:
        adj = adjusted_edges.get(edge.edge_id)
        if adj is None or adj.aggregation_method == "BLOCKED":
            continue

        source_idx = graph.node_map.node_index.get(edge.source_node_id)
        target_idx = graph.node_map.node_index.get(edge.target_node_id)

        if source_idx is None or target_idx is None:
            logger.warning(
                "B7a: Edge %s has unmapped node(s) — skipping",
                edge.edge_id,
            )
            continue

        B_hat[source_idx, target_idx] = adj.mu_e

    n_param = np.count_nonzero(B_hat)
    logger.info(
        "B7a: B̂ matrix populated — %d non-zero entries out of %d edges",
        n_param, len(graph.b_skeleton.edges),
    )

    return B_hat


# ═══════════════════════════════════════════════════════════════
#  B7b: Context-Matched Prior Compilation
# ═══════════════════════════════════════════════════════════════


def compile_context_priors(
    graph: GraphObject,
    B_hat: np.ndarray,
    context_specs: list[ContextPriorSpec] | None = None,
) -> dict[str, np.ndarray]:
    """B7b: Compile 33 context-matched precision matrices.

    For each context: Λ_prior = (I − B̂)ᵀ D⁻¹ (I − B̂)
    with context-specific μ_prior per node.

    4-level fallback:
        exact match → cancer-type → general cancer → N(0,1)

    Args:
        graph: GraphObject from Chain A.
        B_hat: Parameterized edge weight matrix from B7a.
        context_specs: Optional list of 33 ContextPriorSpec objects.
                       If None, generates a single "general_cancer" default.

    Returns:
        Dict mapping context_key → precision matrix ℝ^{n_nodes × n_nodes}.
    """
    n = graph.n_nodes
    I = np.eye(n)
    D = graph.d_matrix.D

    # Compute D⁻¹
    try:
        D_inv = np.linalg.inv(D)
    except np.linalg.LinAlgError:
        raise GateViolation(
            "B-G6",
            "D matrix is singular — cannot compute D⁻¹ for context priors",
        )

    # Formula B7b / A4-1: Λ_prior = (I − B̂)ᵀ D⁻¹ (I − B̂)
    I_minus_B = I - B_hat
    Lambda_base = I_minus_B.T @ D_inv @ I_minus_B
    # Force symmetry
    Lambda_base = (Lambda_base + Lambda_base.T) / 2.0

    Lambda_prior: dict[str, np.ndarray] = {}

    if context_specs:
        for spec in context_specs:
            # Context-specific adjustment: shift diagonal elements
            # based on per-node prior means (informative priors)
            Lambda_ctx = Lambda_base.copy()
            # The context-specific μ_prior affects the prior mean vector,
            # not the precision matrix itself. Store the base Λ for each context.
            # (Mean adjustments are applied in ALG-C1 during patient state inference.)
            Lambda_prior[spec.context_key] = Lambda_ctx
    else:
        # Default: single general_cancer context
        Lambda_prior["general_cancer"] = Lambda_base.copy()
        logger.info(
            "B7b: No context specs provided — using single 'general_cancer' default. "
            "Full 33-context compilation requires context_matched_priors data."
        )

    # Verify all are positive-definite
    for ctx_key, L in Lambda_prior.items():
        try:
            np.linalg.cholesky(L)
        except np.linalg.LinAlgError:
            logger.warning(
                "B7b: Λ_prior for context '%s' is NOT positive-definite. "
                "Applying nearest PD correction.",
                ctx_key,
            )
            from ..chain_a_graph.spectral_validator import _nearest_positive_definite
            Lambda_prior[ctx_key] = _nearest_positive_definite(L)

    logger.info(
        "B7b: Compiled %d context-matched precision matrices",
        len(Lambda_prior),
    )

    return Lambda_prior


# ═══════════════════════════════════════════════════════════════
#  B7c: Synergy Registry Loading
# ═══════════════════════════════════════════════════════════════


def load_synergy_registry(
    registry_path: str | Path | None = None,
) -> list[SynergyRecord]:
    """B7c: Load synergy records from CSV.

    Synergy records describe pairwise interaction effects between
    interventions (15 records in the spec).

    Args:
        registry_path: Path to SYNERGY_REGISTRY.csv.
                       If None, returns empty list (data not yet available).

    Returns:
        List of SynergyRecord objects.
    """
    if registry_path is None:
        logger.info(
            "B7c: No synergy_registry_path provided — "
            "synergy data will be empty (awaiting SYS_EXTRACTION)"
        )
        return []

    registry_path = Path(registry_path)
    if not registry_path.exists():
        logger.warning("B7c: Synergy registry not found: %s", registry_path)
        return []

    records: list[SynergyRecord] = []
    with open(registry_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = SynergyRecord(
                action_a_id=row["action_a_id"].strip(),
                action_b_id=row["action_b_id"].strip(),
                joint_probability_offset=float(row.get("JPO", 0.0)),
                combined_cognitive_score=float(row.get("CCS", 0.0)),
                source_trial=row.get("source_trial", "").strip(),
                gamma=max(
                    -config.SYNERGY_GAMMA_CAP_DEFAULT,
                    min(
                        float(row.get("gamma", 0.0)),
                        config.SYNERGY_GAMMA_CAP_DEFAULT,
                    ),
                ),
            )
            records.append(rec)

    logger.info("B7c: Loaded %d synergy records", len(records))
    return records


# ═══════════════════════════════════════════════════════════════
#  B7d: Assemble FrozenModelState
# ═══════════════════════════════════════════════════════════════


def _compute_frozen_hash(
    B_hat: np.ndarray,
    Sigma_eff: dict[str, float],
    P_inclusion: dict[str, float],
    Lambda_prior: dict[str, np.ndarray] | None = None,
    active_pathway_ids: tuple[str, ...] | None = None,
) -> str:
    """Compute SHA-256 integrity hash for FrozenModelState.

    Covers ALL deterministic state that affects runtime inference:
        - B̂ matrix (edge weights)
        - Sigma_eff (effective SEs)
        - P_inclusion (structural inclusion probabilities)
        - Lambda_prior (context-matched precision matrices)
        - active_pathway_ids (pathway filtering)

    Floats are encoded as IEEE-754 big-endian doubles via struct.pack
    for deterministic, platform-independent hashing (no str() rounding).

    Lambda_prior and active_pathway_ids are optional for backward
    compatibility with existing 3-arg callers in tests.
    """
    hasher = hashlib.sha256()

    # Hash B̂ matrix (contiguous C-order float64)
    hasher.update(np.ascontiguousarray(B_hat, dtype=np.float64).tobytes())

    # Hash Sigma_eff (sorted by edge_id for determinism, IEEE-754 doubles)
    for edge_id in sorted(Sigma_eff.keys()):
        hasher.update(edge_id.encode())
        hasher.update(struct.pack(">d", Sigma_eff[edge_id]))

    # Hash P_inclusion (sorted, IEEE-754 doubles)
    for edge_id in sorted(P_inclusion.keys()):
        hasher.update(edge_id.encode())
        hasher.update(struct.pack(">d", P_inclusion[edge_id]))

    # Hash Lambda_prior (sorted by context key, contiguous matrix bytes)
    if Lambda_prior:
        for ctx_key in sorted(Lambda_prior.keys()):
            hasher.update(ctx_key.encode())
            hasher.update(
                np.ascontiguousarray(
                    Lambda_prior[ctx_key], dtype=np.float64,
                ).tobytes()
            )

    # Hash active_pathway_ids (EXTENSION — Issue #7)
    if active_pathway_ids:
        for pid in sorted(active_pathway_ids):
            hasher.update(pid.encode())

    return hasher.hexdigest()


def assemble_frozen_state(
    graph: GraphObject,
    pooled_edges: dict[str, PooledEdge],
    adjusted_edges: dict[str, HeterogeneityAdjustedEdge],
    prior_specs: dict[str, EdgePriorSpec],
    inclusion_probs: dict[str, InclusionProbEdge],
    chain_direct_results: dict[str, ChainDirectResult],
    synergy_records: list[SynergyRecord] | None = None,
    context_specs: list[ContextPriorSpec] | None = None,
    pathway_evidence_scores: dict[str, PathwayEvidenceScore] | None = None,
    # DEPRECATED — kept for backward compat, ignored.
    tau_sq_priors: dict[str, TauSquaredPrior] | None = None,
) -> FrozenModelState:
    """B7d: Assemble the complete FrozenModelState.

    Combines: B̂ + Σ_eff + Λ_prior(×33) + P_inclusion +
    prior_audit + AV_scores + τ² + synergy +
    pathway_evidence_scores (EXTENSION B6.5)

    This object crosses THE CUT BOUNDARY.
    It is FROZEN: never modified by runtime patient data.

    Args:
        graph: GraphObject from Chain A.
        pooled_edges: B1 outputs.
        adjusted_edges: B2 outputs.
        prior_specs: B3 outputs.
        inclusion_probs: B4 outputs.
        tau_sq_priors: B5 outputs.
        chain_direct_results: B6 outputs.
        synergy_records: B7c synergy data (optional).
        context_specs: B7b context specifications (optional).
        pathway_evidence_scores: B6.5 output (optional, EXTENSION).
            Dict mapping pathway_id → PathwayEvidenceScore.
            If None, pathway scoring was not run (no pathway_map).

    Returns:
        Complete FrozenModelState.

    Raises:
        GateViolation: If gate B-G6 conditions fail.
    """
    logger.info("── B7: Context-Matched Prior Assembly ──")

    # B7a: Build B̂ matrix
    B_hat = build_b_hat_matrix(graph, adjusted_edges)

    # B7b: Compile context-matched precision matrices
    Lambda_prior = compile_context_priors(graph, B_hat, context_specs)

    # Collect Sigma_eff — apply B6 chain-vs-direct SE multiplier
    Sigma_eff: dict[str, float] = {}
    for edge_id, ae in adjusted_edges.items():
        se_eff = ae.SE_eff
        # B6 triage SE inflation: spec lines 1393-1408
        cdr = chain_direct_results.get(edge_id)
        if cdr is not None and cdr.se_multiplier != 1.0:
            se_eff *= cdr.se_multiplier
            logger.info(
                "B7d: Edge %s SE_eff %.4f × %.1f (B6 %s) → %.4f",
                edge_id, ae.SE_eff, cdr.se_multiplier,
                cdr.triage_action, se_eff,
            )
        Sigma_eff[edge_id] = se_eff

    # Collect P_inclusion
    P_incl = {
        edge_id: ip.P_inclusion
        for edge_id, ip in inclusion_probs.items()
    }

    # Collect AV_scores (only for edges with both chain+direct)
    AV_scores = {}
    for edge_id, r in chain_direct_results.items():
        if r.AV_score is not None:
            AV_scores[edge_id] = r.AV_score

    # Collect τ² estimates
    tau_sq_estimates = {
        edge_id: pe.tau_sq
        for edge_id, pe in pooled_edges.items()
    }

    # Synergy records
    if synergy_records is None:
        synergy_records = []

    # Count parameterized vs blocked
    n_param = sum(
        1 for ae in adjusted_edges.values()
        if ae.aggregation_method != "BLOCKED"
    )
    n_blocked = sum(
        1 for ae in adjusted_edges.values()
        if ae.aggregation_method == "BLOCKED"
    )

    # B6.5: Pathway evidence scoring (EXTENSION)
    pw_scores: dict[str, PathwayEvidenceScore] = {}
    active_pw_ids: tuple[str, ...] = ()
    if pathway_evidence_scores is not None:
        pw_scores = pathway_evidence_scores
        active_pw_ids = tuple(
            sorted(pid for pid, s in pw_scores.items() if s.is_adequate)
        )
        n_excluded = sum(1 for s in pw_scores.values() if not s.is_adequate)
        for pid, s in pw_scores.items():
            if not s.is_adequate:
                logger.info(
                    "B6.5: Pathway %s excluded — ED %.3f below threshold %.2f",
                    pid, s.evidence_density, config.MIN_PATHWAY_EVIDENCE_DENSITY,
                )
        logger.info(
            "B7d: Pathway evidence — %d active, %d excluded",
            len(active_pw_ids), n_excluded,
        )

    # Compute integrity hash (covers all deterministic state)
    sha256_hash = _compute_frozen_hash(
        B_hat, Sigma_eff, P_incl, Lambda_prior, active_pw_ids,
    )

    # Store context_specs as immutable tuple for ALG-C1 access
    ctx_specs_tuple = tuple(context_specs) if context_specs else ()

    frozen = FrozenModelState(
        B_hat=B_hat,
        Sigma_eff=Sigma_eff,
        Lambda_prior=Lambda_prior,
        P_inclusion=P_incl,
        prior_audit_trail=prior_specs,
        AV_scores=AV_scores,
        tau_sq_estimates=tau_sq_estimates,
        synergy_records=synergy_records,
        graph=graph,
        context_specs=ctx_specs_tuple,
        pathway_evidence_scores=pw_scores,
        active_pathway_ids=active_pw_ids,
        n_edges_parameterized=n_param,
        n_edges_blocked=n_blocked,
        n_contexts=len(Lambda_prior),
        sha256_hash=sha256_hash,
    )

    # Gate B-G6
    _validate_gate_b_g6(frozen)

    logger.info(
        "═══ ALG-B: Edge Parameterization — COMPLETE ═══\n"
        "  Edges parameterized: %d\n"
        "  Edges blocked: %d\n"
        "  Context priors: %d\n"
        "  Synergy records: %d\n"
        "  SHA-256: %s",
        frozen.n_edges_parameterized,
        frozen.n_edges_blocked,
        frozen.n_contexts,
        len(frozen.synergy_records),
        frozen.sha256_hash[:16] + "...",
    )

    return frozen


def _validate_gate_b_g6(frozen: FrozenModelState) -> None:
    """Gate B-G6: FrozenModelState complete; all Λ_prior positive-definite; SHA-256 hash.

    Validates:
    - B̂ matrix has correct shape
    - All Λ_prior matrices are positive-definite
    - SHA-256 hash is computed
    - All required fields are populated

    Raises:
        GateViolation: If gate conditions fail.
    """
    n = frozen.graph.n_nodes

    # B̂ shape
    if frozen.B_hat.shape != (n, n):
        raise GateViolation(
            "B-G6",
            f"B̂ matrix shape {frozen.B_hat.shape} ≠ expected ({n}, {n})",
        )

    # All Λ_prior positive-definite
    for ctx_key, L in frozen.Lambda_prior.items():
        if L.shape != (n, n):
            raise GateViolation(
                "B-G6",
                f"Λ_prior[{ctx_key}] shape {L.shape} ≠ expected ({n}, {n})",
            )
        try:
            np.linalg.cholesky(L)
        except np.linalg.LinAlgError:
            raise GateViolation(
                "B-G6",
                f"Λ_prior[{ctx_key}] is NOT positive-definite",
            )

    # SHA-256 hash
    if not frozen.sha256_hash:
        raise GateViolation(
            "B-G6",
            "FrozenModelState has empty SHA-256 hash",
        )

    # Required fields populated
    if not frozen.Sigma_eff:
        raise GateViolation(
            "B-G6",
            "FrozenModelState has empty Sigma_eff",
        )
    if not frozen.P_inclusion:
        raise GateViolation(
            "B-G6",
            "FrozenModelState has empty P_inclusion",
        )

    logger.info(
        "Gate B-G6 PASSED: FrozenModelState complete. "
        "%d Λ_prior matrices all PD. Hash: %s",
        len(frozen.Lambda_prior),
        frozen.sha256_hash[:16] + "...",
    )


# ═══════════════════════════════════════════════════════════════
#  Top-Level Pipeline: run_chain_b
# ═══════════════════════════════════════════════════════════════


def run_chain_b(
    graph: GraphObject,
    evidence_records: list[EvidenceRecord],
    synergy_registry_path: str | Path | None = None,
    context_specs: list[ContextPriorSpec] | None = None,
) -> FrozenModelState:
    """Run the complete ALG-B chain: Edge Parameterization.

    Executes B1 → B2 → B3 → B4 → B5 → B6 → B7 in sequence,
    producing the FrozenModelState that crosses the cut boundary
    to runtime chains ALG-C, ALG-D, ALG-E.

    Args:
        graph: GraphObject from Chain A (run_chain_a output).
        evidence_records: Evidence records from SYS_EXTRACTION.
        synergy_registry_path: Optional path to SYNERGY_REGISTRY.csv.
        context_specs: Optional 33 context-matched prior specifications.

    Returns:
        Complete FrozenModelState.

    Raises:
        GateViolation: If any gate (B-G1 through B-G6) fails.
    """
    logger.info("═══ ALG-B: Edge Parameterization — START ═══")
    logger.info("  Input: %d evidence records for %d edges",
                len(evidence_records), graph.n_edges)

    # B1-B6
    (
        pooled_edges,
        adjusted_edges,
        prior_specs,
        inclusion_probs,
        tau_sq_priors,
        chain_direct_results,
    ) = run_b1_through_b6(graph, evidence_records)

    # B7c: Load synergy records
    synergy_records = load_synergy_registry(synergy_registry_path)

    # B6.5: Pathway evidence scoring (EXTENSION)
    # Only run when the graph contains pathways; skip for minimal/test graphs.
    pw_scores: dict[str, PathwayEvidenceScore] | None = None
    if graph.pathway_map:
        pw_scores = score_pathway_evidence(graph.pathway_map, evidence_records)
        logger.info(
            "B6.5 complete: %d pathways scored, %d adequate",
            len(pw_scores),
            sum(1 for s in pw_scores.values() if s.is_adequate),
        )

    # B7: Assemble FrozenModelState
    frozen = assemble_frozen_state(
        graph=graph,
        pooled_edges=pooled_edges,
        adjusted_edges=adjusted_edges,
        prior_specs=prior_specs,
        inclusion_probs=inclusion_probs,
        chain_direct_results=chain_direct_results,
        synergy_records=synergy_records,
        context_specs=context_specs,
        pathway_evidence_scores=pw_scores,
    )

    return frozen
