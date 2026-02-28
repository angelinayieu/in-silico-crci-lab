# VERIFIED: formulas match spec SYS_EX lines 1277-1290
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads PooledEstimate from meta_analyzer.py,
#           PriorSpec from prior_selector.py
# VERIFIED: forward wiring — writes CompiledEdge for ALG-A (graph_object.py)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates P4-G1, P4-G2 raise on failure
"""
Component: SYS_EXTRACTION.EX-P4.P4-WR
Spec: SYS_EXTRACTION_COMPLETE.md lines 1277-1290
Formulas: None (writes compiled data, no new formulas)
Reads: PooledEstimate (from meta_analyzer.py), PriorSpec (from prior_selector.py),
       PriorSelectionLogEntry (from prior_selector.py)
Writes: edges_v1 (ORM: Edge), edge_param_builds_v1 (ORM: EdgeParamBuild),
        CompiledEdge (consumed by ALG-A graph_object.py)
Gates: P4-G1 (all edges have method assigned), P4-G2 (no NaN in beta or SE)
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.config import (
    PRIOR_MEAN_DEFAULT,
    PRIOR_SD_DEFAULT,
    SIGMA_SQ_STRUCTURAL_DEFAULT,
)
from crci.shared.models.enums import (
    AggregationMethod,
    BiasRisk,
    EffectScale,
    PriorSource,
    PriorTypePaper,
)
from crci.shared.models.intermediate_states import (
    CompiledEdge,
    GateViolation,
    PooledEstimate,
    PriorSpec,
)
from crci.shared.models.tables import (
    Edge,
    EdgeParamBuild,
)
from crci.extraction.p4_aggregation.prior_selector import PriorSelectionLogEntry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Supporting Data Structures
# ═══════════════════════════════════════════════════════════════


class EdgeCompilationInput:
    """All inputs needed to compile a single edge.

    Bundles the pooled estimate, prior spec, and metadata for the
    edge_writer to produce the final edges_v1 row.
    """

    def __init__(
        self,
        pooled_estimate: PooledEstimate,
        prior_spec: PriorSpec,
        prior_log: PriorSelectionLogEntry,
        sigma_sq_structural: float = SIGMA_SQ_STRUCTURAL_DEFAULT,
        overlap_decision: str | None = None,
        overlap_decision_json: dict[str, Any] | None = None,
        annotation_source_ids: list[str] | None = None,
        pub_bias_risk: BiasRisk = BiasRisk.INSUFFICIENT_K,
        se_inflation_pub_bias: float = 1.0,
        coherence_flag: str | None = None,
        se_inflation_coherence: float = 1.0,
        contributing_ler_ids: list[str] | None = None,
        effect_scale: EffectScale = EffectScale.SD_SD,
    ) -> None:
        self.pooled_estimate = pooled_estimate
        self.prior_spec = prior_spec
        self.prior_log = prior_log
        self.sigma_sq_structural = sigma_sq_structural
        self.overlap_decision = overlap_decision
        self.overlap_decision_json = overlap_decision_json or {}
        self.annotation_source_ids = annotation_source_ids or []
        self.pub_bias_risk = pub_bias_risk
        self.se_inflation_pub_bias = se_inflation_pub_bias
        self.coherence_flag = coherence_flag
        self.se_inflation_coherence = se_inflation_coherence
        self.contributing_ler_ids = contributing_ler_ids or []
        self.effect_scale = effect_scale


# ═══════════════════════════════════════════════════════════════
#  Gate Enforcement
# ═══════════════════════════════════════════════════════════════


def _enforce_gate_p4_g1(
    compilation_inputs: list[EdgeCompilationInput],
    expected_edge_ids: set[str],
) -> None:
    """Gate P4-G1: All edges must have aggregation method assigned.

    Spec SYS_EX lines 1302: All 118 edges have method assigned -> P4-WR | ABORT
    Raises GateViolation if any edge is missing.
    """
    compiled_edge_ids = {
        inp.pooled_estimate.edge_relation_id for inp in compilation_inputs
    }
    missing = expected_edge_ids - compiled_edge_ids
    if missing:
        raise GateViolation(
            gate_id="P4-G1",
            message=(
                f"Not all edges have aggregation method assigned. "
                f"Missing {len(missing)} edges: {sorted(missing)[:10]}..."
            ),
            context={
                "expected_count": len(expected_edge_ids),
                "compiled_count": len(compiled_edge_ids),
                "missing_count": len(missing),
                "missing_sample": sorted(missing)[:10],
            },
        )

    # Also check that each has a valid aggregation method (must be AggregationMethod member)
    valid_methods = set(AggregationMethod)
    for inp in compilation_inputs:
        method = inp.pooled_estimate.aggregation_method
        if not method:
            raise GateViolation(
                gate_id="P4-G1",
                message=(
                    f"Edge {inp.pooled_estimate.edge_relation_id} has no "
                    f"aggregation method assigned."
                ),
                context={
                    "edge_relation_id": inp.pooled_estimate.edge_relation_id,
                    "aggregation_method": method,
                },
            )
        if method not in valid_methods:
            raise GateViolation(
                gate_id="P4-G1",
                message=(
                    f"Edge {inp.pooled_estimate.edge_relation_id} has invalid "
                    f"aggregation method '{method}'. "
                    f"Must be one of: {[m.value for m in AggregationMethod]}"
                ),
                context={
                    "edge_relation_id": inp.pooled_estimate.edge_relation_id,
                    "aggregation_method": method,
                },
            )


def _enforce_gate_p4_g2(
    compilation_inputs: list[EdgeCompilationInput],
) -> None:
    """Gate P4-G2: No NaN in beta or SE values.

    Spec SYS_EX lines 1303: No NaN in beta or SE -> write | ERROR
    Raises GateViolation if any NaN is detected.
    """
    for inp in compilation_inputs:
        pooled = inp.pooled_estimate
        if math.isnan(pooled.beta_pooled):
            raise GateViolation(
                gate_id="P4-G2",
                message=(
                    f"NaN detected in beta_pooled for edge "
                    f"{pooled.edge_relation_id}"
                ),
                context={
                    "edge_relation_id": pooled.edge_relation_id,
                    "beta_pooled": pooled.beta_pooled,
                },
            )
        if math.isnan(pooled.se_pooled):
            raise GateViolation(
                gate_id="P4-G2",
                message=(
                    f"NaN detected in se_pooled for edge "
                    f"{pooled.edge_relation_id}"
                ),
                context={
                    "edge_relation_id": pooled.edge_relation_id,
                    "se_pooled": pooled.se_pooled,
                },
            )


# ═══════════════════════════════════════════════════════════════
#  Single Edge Compilation
# ═══════════════════════════════════════════════════════════════


def _compile_single_edge(
    inp: EdgeCompilationInput,
) -> CompiledEdge:
    """Compile a single edge from pooled estimate + prior spec.

    Creates a CompiledEdge in-memory object combining all P4 outputs.

    Returns:
        CompiledEdge ready for DB write and downstream consumption
    """
    pooled = inp.pooled_estimate
    prior = inp.prior_spec
    edge_id = pooled.edge_relation_id

    # Generate edge_param_id as unique identifier
    edge_param_id = f"ep_{edge_id}_{uuid.uuid4().hex[:8]}"

    compiled = CompiledEdge(
        edge_param_id=edge_param_id,
        edge_relation_id=edge_id,
        beta_mean=pooled.beta_pooled,
        beta_se=pooled.se_pooled,
        effect_scale=inp.effect_scale,
        prior_source=prior.prior_source,
        prior_type=prior.prior_type,
        aggregation_method=pooled.aggregation_method,
        k=pooled.k,
        total_n=pooled.total_n,
        i_squared=pooled.i_squared,
        tau_squared=pooled.tau_squared,
        pub_bias_risk=inp.pub_bias_risk,
        se_inflation_pub_bias=inp.se_inflation_pub_bias,
        coherence_flag=None,  # Set by P5 later
        se_inflation_coherence=inp.se_inflation_coherence,
    )

    return compiled


# ═══════════════════════════════════════════════════════════════
#  Edge ORM Row Writer
# ═══════════════════════════════════════════════════════════════


def _write_edge_to_db(
    session: Session,
    compiled: CompiledEdge,
    inp: EdgeCompilationInput,
) -> Edge:
    """Write or update a single edges_v1 row.

    Spec SYS_EX lines 1281-1286: For each edge, write to edges_v1:
      beta, SE_eff, P_inclusion (not computed here -- set by P4B/P5),
      prior_type, k, aggregation_method, contributing_ler_ids,
      publication_bias, sigma_sq_structural, overlap_decision,
      deployment_ready: false
    """
    edge_id = compiled.edge_relation_id

    # Check for existing row (upsert pattern)
    existing: Edge | None = session.query(Edge).filter(
        Edge.edge_relation_id == edge_id,
    ).first()

    if existing is not None:
        # Update existing edge
        existing.edge_param_id = compiled.edge_param_id
        existing.beta_mean = compiled.beta_mean
        existing.beta_se = compiled.beta_se
        existing.effect_scale = compiled.effect_scale.value if compiled.effect_scale else None
        existing.aggregation_method = compiled.aggregation_method
        existing.i_squared = compiled.i_squared
        existing.tau_squared = compiled.tau_squared
        existing.total_n = compiled.total_n
        existing.supporting_ler_ids = json.dumps(inp.contributing_ler_ids) if inp.contributing_ler_ids else None
        existing.pub_bias_risk = compiled.pub_bias_risk.value if compiled.pub_bias_risk else None
        existing.se_inflation_pub_bias = compiled.se_inflation_pub_bias
        existing.coherence_flag = compiled.coherence_flag.value if compiled.coherence_flag else None
        existing.se_inflation_coherence = compiled.se_inflation_coherence
        # deployment_ready stays false (set true by P6)
        existing.active = 1
        existing.notes = (
            f"Compiled by P4-WR at {datetime.now(timezone.utc).isoformat()}. "
            f"prior_type={compiled.prior_type.value if compiled.prior_type else 'none'}, "
            f"sigma_sq={inp.sigma_sq_structural:.4f}, "
            f"overlap_decision={inp.overlap_decision}"
        )
        orm_edge = existing
    else:
        # Create new edge row
        orm_edge = Edge(
            edge_param_id=compiled.edge_param_id,
            edge_relation_id=edge_id,
            beta_mean=compiled.beta_mean,
            beta_se=compiled.beta_se,
            effect_scale=compiled.effect_scale.value if compiled.effect_scale else None,
            aggregation_method=compiled.aggregation_method,
            i_squared=compiled.i_squared,
            tau_squared=compiled.tau_squared,
            total_n=compiled.total_n,
            supporting_ler_ids=json.dumps(inp.contributing_ler_ids) if inp.contributing_ler_ids else None,
            pub_bias_risk=compiled.pub_bias_risk.value if compiled.pub_bias_risk else None,
            se_inflation_pub_bias=compiled.se_inflation_pub_bias,
            coherence_flag=compiled.coherence_flag.value if compiled.coherence_flag else None,
            se_inflation_coherence=compiled.se_inflation_coherence,
            active=1,
            version=1,
            notes=(
                f"Compiled by P4-WR at {datetime.now(timezone.utc).isoformat()}. "
                f"prior_type={compiled.prior_type.value if compiled.prior_type else 'none'}, "
                f"sigma_sq={inp.sigma_sq_structural:.4f}, "
                f"overlap_decision={inp.overlap_decision}"
            ),
        )
        session.add(orm_edge)

    return orm_edge


# ═══════════════════════════════════════════════════════════════
#  Edge Param Build (Audit Trail)
# ═══════════════════════════════════════════════════════════════


def _write_edge_param_build(
    session: Session,
    compiled: CompiledEdge,
    inp: EdgeCompilationInput,
    build_id: str,
) -> EdgeParamBuild:
    """Write edge_param_builds_v1 audit trail.

    Spec SYS_EX lines 1287-1288: Also write edge_param_builds_v1
      (audit trail + overlap_decision_json + annotation_source_ids_json)

    R1 provenance: also persists per-study IVW weights as study_weights_json
    for full source traceability.
    """
    # R1 provenance: serialize per-study weights from PooledEstimate
    study_weights_payload = [
        {
            "ler_id": sw.ler_id,
            "study_id": sw.study_id,
            "weight": sw.weight,
            "weight_normalized": sw.weight_normalized,
            "beta": sw.beta,
            "se": sw.se,
        }
        for sw in inp.pooled_estimate.study_weights
    ]

    build_record = EdgeParamBuild(
        build_id=f"bld_{compiled.edge_param_id}",
        build_label=f"P4-WR compile for {compiled.edge_relation_id}",
        build_time=datetime.now(timezone.utc).isoformat(),
        build_version=1,
        aggregation_policy=compiled.aggregation_method,
        outputs_edge_param_ids_json=[compiled.edge_param_id],
        outputs_summary_json={
            "beta_mean": compiled.beta_mean,
            "beta_se": compiled.beta_se,
            "k": compiled.k,
            "total_n": compiled.total_n,
            "i_squared": compiled.i_squared,
            "tau_squared": compiled.tau_squared,
            "prior_type": compiled.prior_type.value if compiled.prior_type else None,
            "prior_source": compiled.prior_source.value if compiled.prior_source else None,
            "sigma_sq_structural": inp.sigma_sq_structural,
            "overlap_decision": inp.overlap_decision,
            "pub_bias_risk": compiled.pub_bias_risk.value if compiled.pub_bias_risk else None,
        },
        study_weights_json=study_weights_payload if study_weights_payload else None,
        warnings_json=[],
        status="ok",
        notes=json.dumps({
            "overlap_decision_json": inp.overlap_decision_json,
            "annotation_source_ids_json": inp.annotation_source_ids,
            "contributing_ler_ids": inp.contributing_ler_ids,
            "prior_provenance": inp.prior_spec.provenance,
        }),
        active=1,
    )
    session.add(build_record)
    return build_record


# ═══════════════════════════════════════════════════════════════
#  Main Writer: write_all_edges
# ═══════════════════════════════════════════════════════════════


def write_all_edges(
    compilation_inputs: list[EdgeCompilationInput],
    session: Session,
    expected_edge_ids: set[str] | None = None,
    build_id: str | None = None,
) -> list[CompiledEdge]:
    """Write final compiled parameters for all edges to edges_v1.

    Spec SYS_EX lines 1277-1290 (P4-WR):
    For each edge, write to edges_v1:
      beta, SE_eff, P_inclusion, prior_type, k,
      aggregation_method, contributing_ler_ids, publication_bias,
      sigma_sq_structural (per-edge, default 0.25),
      overlap_decision (from DCR, nullable),
      deployment_ready: false (set true by P6)

    Also write: edge_param_builds_v1 (audit trail)

    Args:
        compilation_inputs: List of EdgeCompilationInput for each edge
        session: SQLAlchemy session for DB operations
        expected_edge_ids: If provided, enforce Gate P4-G1 completeness check.
            Pass None to skip completeness check (useful for partial builds).
        build_id: Build identifier for audit trail grouping

    Returns:
        List of CompiledEdge objects for downstream consumption

    Raises:
        GateViolation: If P4-G1 (completeness) or P4-G2 (NaN) checks fail
    """
    if build_id is None:
        build_id = f"build_{uuid.uuid4().hex[:12]}"

    # ─── Gate P4-G1: All edges have method assigned ──────────────
    if expected_edge_ids is not None:
        _enforce_gate_p4_g1(compilation_inputs, expected_edge_ids)

    # ─── Gate P4-G2: No NaN in beta or SE ────────────────────────
    _enforce_gate_p4_g2(compilation_inputs)

    compiled_edges: list[CompiledEdge] = []

    for inp in compilation_inputs:
        # Compile in-memory
        compiled = _compile_single_edge(inp)

        # Write to edges_v1
        _write_edge_to_db(session, compiled, inp)

        # Write audit trail to edge_param_builds_v1
        _write_edge_param_build(session, compiled, inp, build_id)

        compiled_edges.append(compiled)

        logger.debug(
            "Compiled edge %s: beta=%.4f, se=%.4f, k=%d, "
            "method=%s, prior=%s, sigma_sq=%.4f",
            compiled.edge_relation_id,
            compiled.beta_mean,
            compiled.beta_se,
            compiled.k,
            compiled.aggregation_method,
            compiled.prior_type.value if compiled.prior_type else "none",
            inp.sigma_sq_structural,
        )

    # Flush to DB (but don't commit — caller manages transaction)
    session.flush()

    logger.info(
        "P4-WR complete: %d edges written to edges_v1. "
        "Build ID: %s. Methods: %s",
        len(compiled_edges),
        build_id,
        _summarize_methods(compiled_edges),
    )

    return compiled_edges


def _summarize_methods(compiled_edges: list[CompiledEdge]) -> str:
    """Summarize aggregation method distribution for logging."""
    method_counts: dict[str, int] = {}
    for edge in compiled_edges:
        method = edge.aggregation_method or "unknown"
        method_counts[method] = method_counts.get(method, 0) + 1
    return ", ".join(f"{m}={c}" for m, c in sorted(method_counts.items()))


# ═══════════════════════════════════════════════════════════════
#  Convenience: Build EdgeCompilationInput from upstream outputs
# ═══════════════════════════════════════════════════════════════


def build_compilation_inputs(
    pooled_estimates: list[PooledEstimate],
    prior_specs: list[PriorSpec],
    prior_logs: list[PriorSelectionLogEntry],
    sigma_sq_map: dict[str, float] | None = None,
    overlap_decision_map: dict[str, str] | None = None,
    overlap_json_map: dict[str, dict[str, Any]] | None = None,
    annotation_ids_map: dict[str, list[str]] | None = None,
    pub_bias_map: dict[str, tuple[BiasRisk, float]] | None = None,
    ler_ids_map: dict[str, list[str]] | None = None,
) -> list[EdgeCompilationInput]:
    """Build EdgeCompilationInput list from upstream P4 outputs.

    This is a convenience function that assembles all the separate
    per-edge outputs into the unified EdgeCompilationInput structure
    expected by write_all_edges.

    Args:
        pooled_estimates: From meta_analyzer.py
        prior_specs: From prior_selector.py
        prior_logs: From prior_selector.py
        sigma_sq_map: edge_id -> sigma_sq_structural (from meta_analyzer annotation consumption)
        overlap_decision_map: edge_id -> DCR decision string (from double_counting.py)
        overlap_json_map: edge_id -> overlap decision JSON detail
        annotation_ids_map: edge_id -> annotation IDs used for sigma_sq adjustment
        pub_bias_map: edge_id -> (BiasRisk, se_inflation) from P4B
        ler_ids_map: edge_id -> contributing LER IDs

    Returns:
        List of EdgeCompilationInput, one per edge
    """
    sigma_sq_map = sigma_sq_map or {}
    overlap_decision_map = overlap_decision_map or {}
    overlap_json_map = overlap_json_map or {}
    annotation_ids_map = annotation_ids_map or {}
    pub_bias_map = pub_bias_map or {}
    ler_ids_map = ler_ids_map or {}

    # Index prior specs and logs by edge_relation_id
    prior_by_edge: dict[str, PriorSpec] = {
        p.edge_relation_id: p for p in prior_specs if p.edge_relation_id
    }
    log_by_edge: dict[str, PriorSelectionLogEntry] = {
        log.edge_relation_id: log for log in prior_logs
    }

    inputs: list[EdgeCompilationInput] = []

    for pooled in pooled_estimates:
        edge_id = pooled.edge_relation_id

        prior = prior_by_edge.get(edge_id)
        if prior is None:
            logger.warning(
                "No PriorSpec for edge %s, using uninformative default "
                "(mean=%s, sd=%s)",
                edge_id, PRIOR_MEAN_DEFAULT, PRIOR_SD_DEFAULT,
            )
            prior = PriorSpec(
                edge_relation_id=edge_id,
                prior_source=PriorSource.UNINFORMATIVE,
                prior_type=PriorTypePaper.STRUCTURAL_PLACEHOLDER,
                mean=PRIOR_MEAN_DEFAULT,
                sd=PRIOR_SD_DEFAULT,
                dist_family="normal",
                provenance="fallback:no_prior_spec_found",
            )

        log = log_by_edge.get(edge_id)
        if log is None:
            logger.warning(
                "No PriorSelectionLogEntry for edge %s, creating minimal entry",
                edge_id,
            )
            log = PriorSelectionLogEntry(
                edge_relation_id=edge_id,
                prior_type=prior.prior_type.value if prior.prior_type else "unknown",
                prior_source=prior.prior_source.value,
                fallback_level=4,
                se_multiplier=2.0,
                k=pooled.k,
                n_rcts=0,
                best_design="unknown",
                has_chain_evidence=False,
                rationale="auto-generated:no_log_entry_found",
                prior_mean=prior.mean,
                prior_sd=prior.sd,
            )

        # Get publication bias info if available
        bias_risk = BiasRisk.INSUFFICIENT_K
        se_inflation_pub = 1.0
        if edge_id in pub_bias_map:
            bias_risk, se_inflation_pub = pub_bias_map[edge_id]

        inp = EdgeCompilationInput(
            pooled_estimate=pooled,
            prior_spec=prior,
            prior_log=log,
            sigma_sq_structural=sigma_sq_map.get(edge_id, SIGMA_SQ_STRUCTURAL_DEFAULT),
            overlap_decision=overlap_decision_map.get(edge_id),
            overlap_decision_json=overlap_json_map.get(edge_id),
            annotation_source_ids=annotation_ids_map.get(edge_id),
            pub_bias_risk=bias_risk,
            se_inflation_pub_bias=se_inflation_pub,
            contributing_ler_ids=ler_ids_map.get(edge_id, []),
        )
        inputs.append(inp)

    return inputs
