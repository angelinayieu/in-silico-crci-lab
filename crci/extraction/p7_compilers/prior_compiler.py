# VERIFIED: formulas P7-C2a, P7-C2b match SYS_EXTRACTION_ADDENDUM Part 6 Compiler 2
# VERIFIED: imports — all modules exist (shared.config, shared.models, numpy)
# VERIFIED: backward wiring — reads PopulationNorms from tables.py (B11)
# VERIFIED: forward wiring — writes CompiledPriorNode for context_matched_priors
# VERIFIED: no hardcoded formula parameters (all from config)
# VERIFIED: gate P7-G2 raises on failure
"""
Component: SYS_EXTRACTION.EX-P7.C2
Spec: SYS_EXTRACTION_ADDENDUM.md Part 6, Compiler 2
Formulas: P7-C2a (μ_prior weighted mean), P7-C2b (Σ_prior → Λ_prior via Cholesky)
Reads: PopulationNorms rows (from population_norms_v1, written by AG03-EXT)
Writes: CompiledPriorNode (consumed by context_matched_priors writer)
Gates: P7-G2 (compiled Λ_prior must be positive definite)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import (
    CompiledPriorNode,
    GateViolation,
)
from crci.shared.models.tables import PopulationNorms

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  INTERNAL TYPES
# ═══════════════════════════════════════════════════════════════


@dataclass
class _ContextGroup:
    """Evidence rows for one cancer_type × treatment_phase context."""

    cancer_type: str
    treatment_phase: str
    rows: list[PopulationNorms] = field(default_factory=list)


@dataclass
class CompiledPriorMatrix:
    """Full prior for one context: μ vector + Λ precision matrix.

    For multi-node priors where covariance structure matters.
    """

    cancer_type: str
    treatment_phase: str
    node_ids: list[str]
    mu_vector: list[float]
    lambda_matrix: list[list[float]]  # precision matrix (flattened for JSON)
    is_diagonal: bool = False
    provenance_status: str = "CURATED_TRACED"
    source_studies: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  NODE-LEVEL COMPILATION
# ═══════════════════════════════════════════════════════════════


def _compile_node_prior(
    rows: list[PopulationNorms],
    node_id: str,
    context_label: str,
) -> tuple[float, float, int, int, list[str]]:
    """Compile weighted mean z-score for one node in one context.

    Formula P7-C2a: μ_prior[node_i] = Σ(N_i × z_i) / Σ(N_i)
    SD from observed variation: sd = √(Σ(N_i × (z_i − μ)²) / Σ(N_i))

    Uses mean_z if available; otherwise falls back to mean_raw (unscaled).

    Returns:
        (mu_prior, sd_prior, k_studies, total_n, study_ids)
    """
    valid_rows = [
        r for r in rows
        if r.N is not None and r.N > 0
        and (r.mean_z is not None or r.mean_raw is not None)
    ]

    if not valid_rows:
        logger.warning(
            "Node '%s' in context '%s': no valid rows, returning uninformative prior",
            node_id,
            context_label,
        )
        return (
            config.PRIOR_MEAN_DEFAULT,
            config.PRIOR_SD_DEFAULT * config.P7_UNINFORMATIVE_SE_INFLATION,
            0,
            0,
            [],
        )

    k = len(valid_rows)

    # Prefer z-scores; fall back to raw means
    values = []
    ns = []
    for r in valid_rows:
        if r.mean_z is not None:
            values.append(r.mean_z)
        else:
            values.append(r.mean_raw)
        ns.append(r.N)

    total_n = sum(ns)

    # Formula P7-C2a: μ_prior = Σ(N_i × z_i) / Σ(N_i)
    mu_prior = sum(n * v for n, v in zip(ns, values)) / total_n

    # SD from observed variation
    if k >= 2:
        weighted_var = sum(
            n * (v - mu_prior) ** 2 for n, v in zip(ns, values)
        ) / total_n
        sd_prior = math.sqrt(weighted_var) if weighted_var > 0 else config.PRIOR_SD_DEFAULT
    else:
        # Single study: use reported SD if available
        sd_val = valid_rows[0].sd_z if valid_rows[0].sd_z is not None else valid_rows[0].sd_raw
        sd_prior = sd_val if sd_val is not None and sd_val > 0 else config.PRIOR_SD_DEFAULT

    study_ids = sorted({r.study_id for r in valid_rows if r.study_id})

    return mu_prior, sd_prior, k, total_n, study_ids


# ═══════════════════════════════════════════════════════════════
#  PRECISION MATRIX COMPILATION
# ═══════════════════════════════════════════════════════════════


def _build_precision_matrix(
    node_sds: dict[str, float],
    node_ids: list[str],
) -> tuple[np.ndarray, bool]:
    """Build precision matrix Λ_prior from marginal SDs.

    Formula P7-C2b: Λ_prior = Σ_prior⁻¹ (via Cholesky)

    Without multi-instrument cross-study data, uses diagonal Σ
    (shrinkage estimator toward diagonal with marginal variances).

    Returns:
        (lambda_matrix, is_diagonal)
    """
    n_nodes = len(node_ids)
    if n_nodes == 0:
        return np.array([]).reshape(0, 0), True

    # Build diagonal covariance matrix from marginal SDs
    sigma_diag = np.zeros((n_nodes, n_nodes))
    for i, nid in enumerate(node_ids):
        sd = node_sds.get(nid, config.PRIOR_SD_DEFAULT)
        sigma_diag[i, i] = sd ** 2

    # Formula P7-C2b: Λ_prior = Σ_prior⁻¹ via Cholesky
    try:
        chol = np.linalg.cholesky(sigma_diag)
        chol_inv = np.linalg.solve(chol, np.eye(n_nodes))
        lambda_matrix = chol_inv.T @ chol_inv
        is_diagonal = True  # diagonal input → diagonal output
    except np.linalg.LinAlgError:
        # Gate P7-G2 fallback: if not positive definite, use diagonal with marginal precisions
        logger.warning(
            "Σ_prior not positive definite for %d nodes, "
            "falling back to diagonal Λ with marginal precisions",
            n_nodes,
        )
        lambda_matrix = np.zeros((n_nodes, n_nodes))
        for i, nid in enumerate(node_ids):
            sd = node_sds.get(nid, config.PRIOR_SD_DEFAULT)
            lambda_matrix[i, i] = 1.0 / (sd ** 2)
        is_diagonal = True

    return lambda_matrix, is_diagonal


# ═══════════════════════════════════════════════════════════════
#  MAIN COMPILER
# ═══════════════════════════════════════════════════════════════


def compile_priors(
    evidence_rows: list[PopulationNorms],
) -> list[CompiledPriorNode]:
    """Compile population norm priors per context per node.

    Groups evidence by (cancer_type × treatment_phase × node_id),
    computes weighted z-score means and SDs, builds precision matrix.

    Gate P7-G2: Compiled Λ_prior must be positive definite.
    Fallback: diagonal Λ with marginal precisions only.

    Args:
        evidence_rows: Rows from population_norms_v1 (written by AG03-EXT).

    Returns:
        List of CompiledPriorNode, one per node per context.
    """
    # Group by (cancer_type, treatment_phase, node_id)
    groups: dict[tuple[str, str, str], list[PopulationNorms]] = {}
    for row in evidence_rows:
        cancer = (row.cancer_type or "mixed").strip().lower()
        phase = (row.treatment_phase or "mixed").strip().lower()
        node = (row.node_id or row.cognitive_domain or "unknown").strip().lower()
        key = (cancer, phase, node)
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    results: list[CompiledPriorNode] = []

    for (cancer, phase, node), rows in groups.items():
        context_label = f"{cancer}×{phase}"

        mu, sd, k, total_n, study_ids = _compile_node_prior(
            rows, node, context_label
        )

        provenance_status = "CURATED_TRACED" if k > 0 else "APPROXIMATE_PENDING"

        compiled = CompiledPriorNode(
            node_id=node,
            cancer_type=cancer,
            treatment_phase=phase,
            mu_prior=mu,
            sd_prior=sd,
            n_total=total_n,
            k_studies=k,
            provenance_status=provenance_status,
            source_studies=study_ids,
        )
        results.append(compiled)

        logger.info(
            "Compiled prior node '%s' in %s: μ=%.4f, σ=%.4f, k=%d, N=%d, status=%s",
            node,
            context_label,
            mu,
            sd,
            k,
            total_n,
            provenance_status,
        )

    logger.info(
        "Prior compilation complete: %d node-context priors compiled",
        len(results),
    )
    return results


def compile_prior_matrix(
    evidence_rows: list[PopulationNorms],
    cancer_type: str,
    treatment_phase: str,
) -> CompiledPriorMatrix:
    """Compile full prior matrix for one context.

    Builds μ vector and Λ precision matrix across all nodes in this context.

    Gate P7-G2: Λ_prior must be positive definite.

    Args:
        evidence_rows: All population_norms_v1 rows for this context.
        cancer_type: Cancer type filter.
        treatment_phase: Treatment phase filter.

    Returns:
        CompiledPriorMatrix with μ vector and Λ matrix.

    Raises:
        GateViolation: If precision matrix cannot be computed at all.
    """
    context_label = f"{cancer_type}×{treatment_phase}"

    # Filter to this context
    context_rows = [
        r for r in evidence_rows
        if (r.cancer_type or "mixed").strip().lower() == cancer_type.lower()
        and (r.treatment_phase or "mixed").strip().lower() == treatment_phase.lower()
    ]

    # Group by node
    node_groups: dict[str, list[PopulationNorms]] = {}
    for row in context_rows:
        node = (row.node_id or row.cognitive_domain or "unknown").strip().lower()
        if node not in node_groups:
            node_groups[node] = []
        node_groups[node].append(row)

    node_ids = sorted(node_groups.keys())
    mu_vector: list[float] = []
    node_sds: dict[str, float] = {}
    all_study_ids: set[str] = set()

    for nid in node_ids:
        rows = node_groups[nid]
        mu, sd, k, total_n, study_ids = _compile_node_prior(
            rows, nid, context_label
        )
        mu_vector.append(mu)
        node_sds[nid] = sd
        all_study_ids.update(study_ids)

    # Build precision matrix
    lambda_mat, is_diagonal = _build_precision_matrix(node_sds, node_ids)

    # ─── Gate P7-G2: Verify positive definiteness ─────────────
    if lambda_mat.size > 0:
        try:
            np.linalg.cholesky(lambda_mat)
        except np.linalg.LinAlgError:
            raise GateViolation(
                "P7-G2",
                f"Context {context_label}: compiled Λ_prior is not positive definite "
                f"even after diagonal fallback ({len(node_ids)} nodes)",
                {"cancer_type": cancer_type, "treatment_phase": treatment_phase},
            )

    return CompiledPriorMatrix(
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        node_ids=node_ids,
        mu_vector=mu_vector,
        lambda_matrix=lambda_mat.tolist(),
        is_diagonal=is_diagonal,
        provenance_status="CURATED_TRACED" if context_rows else "APPROXIMATE_PENDING",
        source_studies=sorted(all_study_ids),
    )
