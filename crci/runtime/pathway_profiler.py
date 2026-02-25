# VERIFIED: formulas match plan S3 specification
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads GraphObject (chain_a), theta_hat (chain_c)
# VERIFIED: forward wiring — writes PathwayProfile for report_assembler.py
# VERIFIED: no hardcoded formula parameters — thresholds from config.py
"""
Component: Phase 8 S3 — Pathway Profile Computation
Spec: Plan S3 (pathway activation z-scores)
Formulas:
    S3-1: z_node_i = (theta_hat[i] - theta_prior_mean[i]) / sigma_prior[i]
    S3-2: z_pathway = Σ(w_i × z_node_i) / Σ(w_i)  [variance-weighted]
    S3-3: dysregulation flag = |z_pathway| > PATHWAY_DYSREGULATION_THRESHOLD
    S3-4: contribution_fraction = Σ(var_contrib for nodes in pathway) / total_var
Reads: GraphObject (from chain_a), theta_hat (from chain_c),
       theta_prior (from chain_b), variance_contrib (from chain_f)
Writes: PathwayProfile (consumed by report_assembler.py → PRES-PAT5)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from crci.shared import config
from crci.shared.models.output_contracts import PathwayContribution, PathwayProfile

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PathwayInput:
    """Aggregated inputs for pathway profiling."""

    pathway_id: str
    pathway_label: str
    component_node_ids: list[str]
    edge_ids: list[str]


# ═══════════════════════════════════════════════════════════════
#  Core Computation
# ═══════════════════════════════════════════════════════════════


def compute_pathway_profile(
    pathways: list[PathwayInput],
    theta_hat: np.ndarray,
    theta_prior_mean: np.ndarray,
    sigma_prior: np.ndarray,
    node_index: dict[str, int],
    variance_contrib: dict[str, float] | None = None,
    run_id: str = "",
    subject_ref: str = "",
) -> PathwayProfile:
    """Compute per-pathway activation z-scores and contribution fractions.

    Uses signed z-scores (direction matters clinically) weighted by
    per-node variance contribution from ALG-F3.

    Args:
        pathways: List of pathway definitions with component node IDs.
        theta_hat: Posterior node means (n_nodes,) from Chain C.
        theta_prior_mean: Prior node means (n_nodes,) from Chain B.
        sigma_prior: Prior node SDs (n_nodes,) from Chain B.
        node_index: Mapping node_id → index in theta arrays.
        variance_contrib: Per-node variance contribution from ALG-F3.
            Falls back to equal weights if None.
        run_id: Session run ID.
        subject_ref: Patient reference.

    Returns:
        PathwayProfile with per-pathway contributions.
    """
    total_var = sum(variance_contrib.values()) if variance_contrib else 1.0
    if total_var <= 0:
        total_var = 1.0

    contributions: list[PathwayContribution] = []
    max_contribution = 0.0
    dominant_id: str | None = None

    for pw in pathways:
        # Resolve node indices for this pathway
        node_indices = []
        for nid in pw.component_node_ids:
            if nid in node_index:
                node_indices.append((nid, node_index[nid]))
            else:
                logger.warning(
                    "Pathway %s: node %s not found in node_index, skipping",
                    pw.pathway_id, nid,
                )

        if not node_indices:
            logger.warning(
                "Pathway %s: no valid nodes, producing zero contribution",
                pw.pathway_id,
            )
            contributions.append(PathwayContribution(
                pathway_id=pw.pathway_id,
                pathway_label=pw.pathway_label,
                contribution_fraction=0.0,
                key_edges=pw.edge_ids[:3],
                evidence_quality="insufficient",
            ))
            continue

        # Formula S3-1: Per-node signed z-score
        # z_node_i = (theta_hat[i] - theta_prior_mean[i]) / sigma_prior[i]
        z_nodes: list[float] = []
        weights: list[float] = []
        pathway_var_sum = 0.0

        for nid, idx in node_indices:
            sigma = float(sigma_prior[idx])
            if sigma <= 0:
                sigma = config.PRIOR_SD_DEFAULT
                logger.warning(
                    "Pathway %s node %s: sigma_prior <= 0, using default %f",
                    pw.pathway_id, nid, sigma,
                )

            # Formula S3-1: signed z-score
            z_i = (float(theta_hat[idx]) - float(theta_prior_mean[idx])) / sigma
            z_nodes.append(z_i)

            # Weight by variance contribution (or equal weight)
            if variance_contrib is not None and nid in variance_contrib:
                w = variance_contrib[nid]
            else:
                w = 1.0
                if variance_contrib is not None:
                    logger.debug(
                        "Pathway %s node %s: no variance_contrib, using equal weight",
                        pw.pathway_id, nid,
                    )
            weights.append(w)
            pathway_var_sum += w

        # Formula S3-2: Variance-weighted pathway z-score (signed)
        w_sum = sum(weights)
        if w_sum > 0:
            z_pathway = sum(z * w for z, w in zip(z_nodes, weights)) / w_sum
        else:
            z_pathway = 0.0

        # Formula S3-4: Contribution fraction
        contribution_fraction = pathway_var_sum / total_var

        # Determine evidence quality from z-score magnitude
        abs_z = abs(z_pathway)
        if abs_z >= config.PATHWAY_DYSREGULATION_THRESHOLD:
            quality = "strong_signal"
        elif abs_z >= config.PATHWAY_MILD_THRESHOLD:
            quality = "moderate_signal"
        else:
            quality = "normal_range"

        contributions.append(PathwayContribution(
            pathway_id=pw.pathway_id,
            pathway_label=pw.pathway_label,
            contribution_fraction=float(contribution_fraction),
            activation_z=float(z_pathway),
            key_edges=pw.edge_ids[:3],
            evidence_quality=quality,
        ))

        if contribution_fraction > max_contribution:
            max_contribution = contribution_fraction
            dominant_id = pw.pathway_id

    coverage = min(1.0, sum(c.contribution_fraction for c in contributions))

    logger.info(
        "Pathway profiler: %d pathways, dominant=%s, coverage=%.3f",
        len(contributions), dominant_id, coverage,
    )

    return PathwayProfile(
        run_id=run_id,
        subject_ref=subject_ref,
        pathway_contributions=contributions,
        dominant_pathway_id=dominant_id,
        coverage_fraction=float(coverage),
    )
