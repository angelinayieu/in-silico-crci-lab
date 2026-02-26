# VERIFIED: formulas [ED-1, DS-1] — EXTENSION (not in original spec)
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PathwayDef (from shared/models),
#           EvidenceRecord (from evidence_compiler.py)
# VERIFIED: forward wiring — writes PathwayEvidenceScore
#           (consumed by frozen_state.py → FrozenModelState in S4)
# VERIFIED: no hardcoded formula parameters — all from config.py
# VERIFIED: gate [B-G6.5] logs WARNING (soft gate, not hard block)
# VERIFIED: study deduplication per (study_id, edge_id) — max weight
# VERIFIED: quality_grade normalized (strip+upper) before lookup
# VERIFIED: k_quality precomputed once — no redundant computation
# VERIFIED: DS eligibility aligned (ED + coverage) with no-comparator guard
"""
Component: SYS_ALGORITHM.ALG-B.B6.5 (EXTENSION)
Spec: Not in original spec — EXTENSION for pathway-level evidence metrics.
Formulas:
    ED-1: ED(P) = Σ_{e ∈ P} k_quality(e) / |edges_in_P|
           where k_quality(e) = Σ_{unique s ∈ evidence(e)} w_quality(grade(s))
           Deduplicated by study_id per edge — each study contributes at most
           once, with weight = max quality weight across duplicate records.
           quality_grade is normalized via strip().upper() before lookup.
    DS-1: DS(P) = 1 − max_{Q ≠ P} cosine_sim(ev_vec(P), ev_vec(Q))
           where ev_vec(P) is per-edge quality-weighted study counts.
           NOTE: DS measures edge-evidence orthogonality. Because pathways
           have mostly disjoint edge sets by design, DS will often saturate
           near 1.0 for well-evidenced pathways. Interpret as "how non-
           overlapping are the evidence supports," not "how distinguishable
           the evidence patterns are."
           DS is only computed for pathways meeting BOTH the ED adequacy
           threshold AND the edge coverage threshold, with at least one
           valid comparator pathway. Otherwise DS = 0.0.
Reads: PathwayDef (from shared/models/pathway_types.py),
       EvidenceRecord (from evidence_compiler.py)
Writes: PathwayEvidenceScore (consumed by frozen_state.py in S4)
Gates: B-G6.5 (soft — WARNING only)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from crci.shared import config
from crci.shared.models.pathway_types import PathwayDef

from .evidence_compiler import EvidenceRecord

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output Type
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PathwayEvidenceScore:
    """Evidence density and distinction score for one pathway.

    Produced by score_pathway_evidence(), consumed by frozen_state.py
    when assembling FrozenModelState (Slice 4).
    """

    pathway_id: str
    evidence_density: float        # ED(P): quality-weighted unique studies per edge
    distinction_score: float       # DS(P): 1 − max cosine similarity (edge-evidence orthogonality)
    n_edges_total: int             # |edges_in_P| — denominator of ED
    n_edges_with_evidence: int     # edges that have ≥1 unique study
    edge_coverage: float           # n_edges_with_evidence / n_edges_total
    is_adequate: bool              # ED ≥ MIN_PATHWAY_EVIDENCE_DENSITY
    # Debug hooks for downstream diagnosis (FrozenModelState, reporting)
    tier: str = ""                 # from PathwayDef / registry
    status: str = "connected"      # from PathwayDef / registry
    ds_eligible: bool = False      # True if this pathway met DS computation criteria
    ds_comparators: int = 0        # number of valid comparator pathways used for DS
    expected_edge_count: int = 0   # from PATHWAY_REGISTRY.csv — spot skeleton mismatches


# ═══════════════════════════════════════════════════════════════
#  ED-1: Evidence Density per Pathway
# ═══════════════════════════════════════════════════════════════


def _compute_edge_k_quality(
    edge_id: str,
    records: list[EvidenceRecord],
) -> float:
    """Compute k_quality(e) for one edge with study deduplication.

    # EXTENSION ED-1 (inner sum):
    #   k_quality(e) = Σ_{unique s ∈ evidence(e)} w_quality(grade(s))

    Each study contributes at most once per edge. If a study has multiple
    records for the same edge (multi-outcome, multi-arm, reconciliation),
    the highest quality weight is used.

    quality_grade is normalized via strip().upper() before lookup to
    guard against upstream case/whitespace drift.

    Args:
        edge_id: The edge to score (for logging context).
        records: Evidence records for this edge.

    Returns:
        Quality-weighted unique study count (float ≥ 0).
    """
    if not records:
        return 0.0

    # Deduplicate: each study_id contributes max weight across its records
    study_best_weight: dict[str, float] = {}
    warned_studies: set[str] = set()

    for rec in records:
        grade = rec.quality_grade.strip().upper() if rec.quality_grade else ""
        weight = config.ED_QUALITY_WEIGHTS.get(grade)
        if weight is None:
            weight = config.ED_QUALITY_WEIGHT_VERY_LOW
            if rec.study_id not in warned_studies:
                warned_studies.add(rec.study_id)
                logger.warning(
                    "ED-1: Edge %s, study %s has unknown quality_grade '%s' — "
                    "defaulting to VERY_LOW weight %.2f",
                    edge_id, rec.study_id, rec.quality_grade, weight,
                )
        current_best = study_best_weight.get(rec.study_id, -1.0)
        if weight > current_best:
            study_best_weight[rec.study_id] = weight

    return sum(study_best_weight.values())


def _precompute_k_quality_by_edge(
    evidence_by_edge: dict[str, list[EvidenceRecord]],
) -> dict[str, float]:
    """Precompute k_quality(e) for all edges — called ONCE per scoring run.

    This is the single point of truth for per-edge quality-weighted study
    counts. Both ED and DS computations read from this cache. This
    eliminates redundant computation and duplicate log warnings.

    Args:
        evidence_by_edge: Pre-indexed evidence records by edge_id.

    Returns:
        Dict mapping edge_id → k_quality(e).
    """
    result: dict[str, float] = {}
    for edge_id, records in evidence_by_edge.items():
        result[edge_id] = _compute_edge_k_quality(edge_id, records)
    return result


def _compute_evidence_density(
    pathway: PathwayDef,
    k_quality_by_edge: dict[str, float],
) -> tuple[float, int, int]:
    """Compute ED(P) for one pathway.

    # EXTENSION ED-1:
    #   ED(P) = Σ_{e ∈ P} k_quality(e) / |edges_in_P|

    Uses precomputed k_quality values (study-deduplicated, grade-normalized).

    Args:
        pathway: PathwayDef with edge_ids populated by chain_a.
        k_quality_by_edge: Precomputed quality-weighted counts per edge.

    Returns:
        Tuple of (evidence_density, n_edges_total, n_edges_with_evidence).
        If the pathway has no edges, returns (0.0, 0, 0).
    """
    edge_ids = pathway.edge_ids
    n_edges_total = len(edge_ids)

    if n_edges_total == 0:
        logger.info(
            "ED-1: Pathway %s has 0 edges (status=%s) — ED=0.0",
            pathway.pathway_id, pathway.status,
        )
        return 0.0, 0, 0

    quality_sum = 0.0
    n_with_evidence = 0

    for edge_id in edge_ids:
        k_quality = k_quality_by_edge.get(edge_id, 0.0)
        quality_sum += k_quality
        if k_quality > 0.0:
            n_with_evidence += 1

    # EXTENSION ED-1: ED(P) = Σ k_quality(e) / |edges_in_P|
    evidence_density = quality_sum / n_edges_total

    return evidence_density, n_edges_total, n_with_evidence


# ═══════════════════════════════════════════════════════════════
#  DS-1: Distinction Score (Cosine Dissimilarity)
# ═══════════════════════════════════════════════════════════════


def _build_evidence_vector(
    pathway: PathwayDef,
    all_edge_ids: list[str],
    edge_id_to_index: dict[str, int],
    k_quality_by_edge: dict[str, float],
) -> list[float]:
    """Build an evidence vector for one pathway over a shared edge index.

    The vector has one entry per edge in the global edge set.
    Entries for edges NOT in this pathway are 0.0.
    Entries for edges IN this pathway are k_quality(e) from precomputed cache.

    Args:
        pathway: PathwayDef with edge_ids.
        all_edge_ids: Global ordered list of all edge IDs across all pathways.
        edge_id_to_index: Reverse lookup for all_edge_ids.
        k_quality_by_edge: Precomputed quality-weighted counts per edge.

    Returns:
        Evidence vector of length len(all_edge_ids).
    """
    vec = [0.0] * len(all_edge_ids)
    for edge_id in pathway.edge_ids:
        idx = edge_id_to_index.get(edge_id)
        if idx is not None:
            vec[idx] = k_quality_by_edge.get(edge_id, 0.0)
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 if either vector has zero magnitude (no evidence).
    """
    dot = sum(ai * bi for ai, bi in zip(a, b))
    mag_a = math.sqrt(sum(ai * ai for ai in a))
    mag_b = math.sqrt(sum(bi * bi for bi in b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


def _compute_distinction_scores(
    pathways: list[PathwayDef],
    k_quality_by_edge: dict[str, float],
    evidence_densities: dict[str, float],
    edge_coverages: dict[str, float],
) -> tuple[dict[str, float], dict[str, bool], dict[str, int]]:
    """Compute DS(P) for all pathways.

    # EXTENSION DS-1:
    #   DS(P) = 1 − max_{Q ≠ P} cosine_sim(ev_vec(P), ev_vec(Q))
    #
    #   NOTE: DS measures edge-evidence orthogonality. Pathways with
    #   disjoint edge sets will have high DS regardless of evidence
    #   quality. This is by design — interpret as "how non-overlapping
    #   are the evidence supports."

    Eligibility (aligned criteria):
    - A pathway is eligible for DS iff:
        (a) ED ≥ MIN_PATHWAY_EVIDENCE_DENSITY, AND
        (b) edge_coverage ≥ MIN_EDGE_COVERAGE_FOR_DS
    - At least MIN_ACTIVE_PATHWAYS_FOR_DS eligible pathways must exist
      globally for any DS computation to proceed.
    - For each pathway P, at least one other eligible comparator Q must
      exist; otherwise DS(P) = 0.0 (not comparable, not "highly distinct").

    Args:
        pathways: All PathwayDef objects.
        k_quality_by_edge: Precomputed quality-weighted counts per edge.
        evidence_densities: Pre-computed ED(P) per pathway_id.
        edge_coverages: Pre-computed edge_coverage per pathway_id.

    Returns:
        Tuple of three dicts, all keyed by pathway_id:
        - ds_values: distinction score (float, 0.0 if ineligible)
        - ds_eligible: whether this pathway met DS computation criteria
        - ds_comparators: number of comparator pathways used for DS
    """
    ds_values: dict[str, float] = {}
    ds_eligible_map: dict[str, bool] = {}
    ds_comparators_map: dict[str, int] = {}

    # Aligned eligibility: ED ≥ threshold AND coverage ≥ threshold
    eligible_ids: set[str] = set()
    for pw in pathways:
        pid = pw.pathway_id
        ed_ok = evidence_densities.get(pid, 0.0) >= config.MIN_PATHWAY_EVIDENCE_DENSITY
        cov_ok = edge_coverages.get(pid, 0.0) >= config.MIN_EDGE_COVERAGE_FOR_DS
        if ed_ok and cov_ok:
            eligible_ids.add(pid)

    # Global precondition: need enough eligible pathways
    if len(eligible_ids) < config.MIN_ACTIVE_PATHWAYS_FOR_DS:
        logger.info(
            "DS-1: Only %d eligible pathways (need %d) — all DS set to 0.0. "
            "Eligibility requires ED ≥ %.2f AND coverage ≥ %.2f.",
            len(eligible_ids), config.MIN_ACTIVE_PATHWAYS_FOR_DS,
            config.MIN_PATHWAY_EVIDENCE_DENSITY, config.MIN_EDGE_COVERAGE_FOR_DS,
        )
        for pw in pathways:
            ds_values[pw.pathway_id] = 0.0
            ds_eligible_map[pw.pathway_id] = pw.pathway_id in eligible_ids
            ds_comparators_map[pw.pathway_id] = 0
        return ds_values, ds_eligible_map, ds_comparators_map

    # Build shared edge index from union of all pathway edges
    all_edge_id_set: set[str] = set()
    for pw in pathways:
        all_edge_id_set.update(pw.edge_ids)
    all_edge_ids = sorted(all_edge_id_set)  # deterministic order
    edge_id_to_index = {eid: i for i, eid in enumerate(all_edge_ids)}

    # Build evidence vectors for all pathways
    vectors: dict[str, list[float]] = {}
    for pw in pathways:
        vectors[pw.pathway_id] = _build_evidence_vector(
            pw, all_edge_ids, edge_id_to_index, k_quality_by_edge,
        )

    # Compute DS(P) = 1 − max_{Q ≠ P} cosine_sim(ev_vec(P), ev_vec(Q))
    for pw in pathways:
        pid = pw.pathway_id

        if pid not in eligible_ids:
            ds_values[pid] = 0.0
            ds_eligible_map[pid] = False
            ds_comparators_map[pid] = 0
            logger.debug(
                "DS-1: Pathway %s ineligible (ED=%.3f, coverage=%.3f)",
                pid,
                evidence_densities.get(pid, 0.0),
                edge_coverages.get(pid, 0.0),
            )
            continue

        # Find valid comparators: other pathways that are ALSO eligible
        comparators = [
            other_pw for other_pw in pathways
            if other_pw.pathway_id != pid
            and other_pw.pathway_id in eligible_ids
        ]

        if not comparators:
            # No valid comparators — DS is not meaningful
            ds_values[pid] = 0.0
            ds_eligible_map[pid] = True
            ds_comparators_map[pid] = 0
            logger.debug(
                "DS-1: Pathway %s eligible but has 0 valid comparators — "
                "DS=0.0 (not comparable, not 'highly distinct')",
                pid,
            )
            continue

        vec_p = vectors[pid]
        max_sim = 0.0
        for comp in comparators:
            sim = _cosine_similarity(vec_p, vectors[comp.pathway_id])
            if sim > max_sim:
                max_sim = sim

        # EXTENSION DS-1: DS(P) = 1 − max similarity
        ds_values[pid] = 1.0 - max_sim
        ds_eligible_map[pid] = True
        ds_comparators_map[pid] = len(comparators)

    return ds_values, ds_eligible_map, ds_comparators_map


# ═══════════════════════════════════════════════════════════════
#  Gate B-G6.5: Pathway Evidence Sufficiency (Soft Gate)
# ═══════════════════════════════════════════════════════════════


def _check_gate_b_g65(
    scores: dict[str, PathwayEvidenceScore],
) -> None:
    """Gate B-G6.5: Check pathway evidence sufficiency.

    This is a SOFT gate — it logs a WARNING, not a hard block.
    Early-stage data will often have sparse pathway evidence.

    EXTENSION B-G6.5: Warns if count of adequate pathways
    < GATE_B65_MIN_ADEQUATE_PATHWAYS.
    """
    n_adequate = sum(1 for s in scores.values() if s.is_adequate)

    if n_adequate < config.GATE_B65_MIN_ADEQUATE_PATHWAYS:
        logger.warning(
            "Gate B-G6.5 WARNING: Only %d pathways have adequate evidence "
            "(ED ≥ %.2f). Minimum recommended: %d. "
            "Pathway-level scoring will be unreliable.",
            n_adequate,
            config.MIN_PATHWAY_EVIDENCE_DENSITY,
            config.GATE_B65_MIN_ADEQUATE_PATHWAYS,
        )
    else:
        logger.info(
            "Gate B-G6.5 PASSED: %d pathways with adequate evidence "
            "(ED ≥ %.2f)",
            n_adequate, config.MIN_PATHWAY_EVIDENCE_DENSITY,
        )


# ═══════════════════════════════════════════════════════════════
#  Top-Level Entry Point
# ═══════════════════════════════════════════════════════════════


def score_pathway_evidence(
    pathways: list[PathwayDef],
    evidence_records: list[EvidenceRecord],
) -> dict[str, PathwayEvidenceScore]:
    """Score all pathways for evidence density and distinction.

    Computes ED(P) and DS(P) for every pathway, then fires the
    soft gate B-G6.5.

    This function is called from run_chain_b (wired in Slice 5)
    after B1-B6 complete and before FrozenModelState assembly.

    k_quality(e) is precomputed ONCE for all edges, with study
    deduplication per (study_id, edge_id) and grade normalization.
    Both ED and DS read from this cache — no redundant computation.

    Args:
        pathways: PathwayDef list from GraphObject.pathway_map.
                  Must have edge_ids populated by chain_a.
        evidence_records: Raw evidence records (same input as B1).
                          Needed for quality_grade per study.

    Returns:
        Dict mapping pathway_id → PathwayEvidenceScore.
        Includes all pathways, even those with no evidence (ED=0).
    """
    logger.info("── B6.5: Pathway Evidence Scoring (EXTENSION) ──")
    logger.info("  Input: %d pathways, %d evidence records",
                len(pathways), len(evidence_records))

    # Pre-index evidence by edge_id (O(n) scan, O(1) lookups)
    evidence_by_edge: dict[str, list[EvidenceRecord]] = {}
    for rec in evidence_records:
        evidence_by_edge.setdefault(rec.edge_id, []).append(rec)

    # Precompute k_quality ONCE — study-deduplicated, grade-normalized
    k_quality_by_edge = _precompute_k_quality_by_edge(evidence_by_edge)

    # Phase 1: Compute ED(P) for all pathways
    evidence_densities: dict[str, float] = {}
    edge_coverages: dict[str, float] = {}
    ed_details: dict[str, tuple[int, int]] = {}  # pathway_id → (n_total, n_with)

    for pw in pathways:
        ed, n_total, n_with = _compute_evidence_density(pw, k_quality_by_edge)
        evidence_densities[pw.pathway_id] = ed
        coverage = n_with / n_total if n_total > 0 else 0.0
        edge_coverages[pw.pathway_id] = coverage
        ed_details[pw.pathway_id] = (n_total, n_with)

    # Phase 2: Compute DS(P) for all pathways (uses precomputed k_quality)
    distinction_scores, ds_eligible_map, ds_comparators_map = (
        _compute_distinction_scores(
            pathways, k_quality_by_edge, evidence_densities, edge_coverages,
        )
    )

    # Phase 3: Assemble output with debug hooks
    scores: dict[str, PathwayEvidenceScore] = {}
    for pw in pathways:
        pid = pw.pathway_id
        n_total, n_with = ed_details[pid]
        ed = evidence_densities[pid]
        ds = distinction_scores[pid]
        coverage = edge_coverages[pid]
        is_adequate = ed >= config.MIN_PATHWAY_EVIDENCE_DENSITY

        scores[pid] = PathwayEvidenceScore(
            pathway_id=pid,
            evidence_density=ed,
            distinction_score=ds,
            n_edges_total=n_total,
            n_edges_with_evidence=n_with,
            edge_coverage=coverage,
            is_adequate=is_adequate,
            # Debug hooks from PathwayDef and DS computation
            tier=pw.tier,
            status=pw.status,
            ds_eligible=ds_eligible_map.get(pid, False),
            ds_comparators=ds_comparators_map.get(pid, 0),
            expected_edge_count=pw.expected_edge_count,
        )

    # Phase 4: Soft gate check
    _check_gate_b_g65(scores)

    # Summary
    n_adequate = sum(1 for s in scores.values() if s.is_adequate)
    n_ds_eligible = sum(1 for s in scores.values() if s.ds_eligible)
    ed_values = [s.evidence_density for s in scores.values()]
    mean_ed = sum(ed_values) / len(ed_values) if ed_values else 0.0
    ds_eligible_values = [s.distinction_score for s in scores.values() if s.ds_eligible]
    mean_ds = (
        sum(ds_eligible_values) / len(ds_eligible_values)
        if ds_eligible_values else 0.0
    )

    logger.info(
        "── B6.5: COMPLETE ──\n"
        "  Pathways scored: %d\n"
        "  Adequate (ED ≥ %.2f): %d\n"
        "  DS-eligible: %d\n"
        "  Mean ED: %.3f\n"
        "  Mean DS (eligible only): %.3f",
        len(scores), config.MIN_PATHWAY_EVIDENCE_DENSITY,
        n_adequate, n_ds_eligible, mean_ed, mean_ds,
    )

    return scores
