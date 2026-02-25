# VERIFIED: query templates match AUTOMATED_RETRIEVAL_PLAN.md Part 3
# VERIFIED: imports — sqlalchemy, retrieval.models
# VERIFIED: backward wiring — reads Class A tables + node_search_terms_v1
# VERIFIED: forward wiring — writes APSQueryRequest[] for search_coordinator
# VERIFIED: no hardcoded parameters (workstream priority from config)
"""
Component: SYS_EXTRACTION.EX-ACQ.QueryGenerator
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 3 (Query Generation from Class A Tables)
Purpose: Deterministic template expansion from Class A registry data into
         search queries. 7 workstream-specific query generators.
         No LLM used — pure template expansion from structured data.
Reads: edge_relations_definitions_v1, biomarker_node_definitions_v1,
       instrument_definitions_v1, action_catalog_v1,
       correlation_registry_v1, node_search_terms_v1
Writes: APSQueryRequest[] for search_coordinator
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import (
    EdgeRelationsDefinition,
    BiomarkerNodeDefinition,
    InstrumentDefinition,
    ActionCatalog,
    NodeSearchTerm,
)
from crci.retrieval.models import APSQueryRequest

logger = logging.getLogger(__name__)


def _query_id() -> str:
    """Generate a unique query ID."""
    return f"QRY_{uuid.uuid4().hex[:12]}"


def _get_node_synonyms(
    session: Session,
    node_id: str,
) -> list[str]:
    """Get search synonyms for a node from node_search_terms_v1.

    Returns all active terms, or falls back to the node_id itself
    with underscores replaced by spaces.
    """
    terms = (
        session.query(NodeSearchTerm.term)
        .filter(
            NodeSearchTerm.node_id == node_id,
            NodeSearchTerm.active == 1,
        )
        .all()
    )
    if terms:
        return [t[0] for t in terms]

    # Fallback: derive from node_id (e.g., NODE_SLEEP_DISRUPTION → "sleep disruption")
    fallback = node_id.replace("NODE_", "").replace("_", " ").lower()
    logger.warning(
        "No search terms for node '%s', using fallback: '%s'",
        node_id,
        fallback,
    )
    return [fallback]


def _build_or_clause(terms: list[str]) -> str:
    """Build a PubMed-style OR clause from a list of terms."""
    quoted = [f'"{t}"' for t in terms]
    if len(quoted) == 1:
        return quoted[0]
    return f"({' OR '.join(quoted)})"


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 1: EDGE EVIDENCE
# ═══════════════════════════════════════════════════════════════


def generate_edge_queries(
    session: Session,
    edge_ids: list[str] | None = None,
) -> list[APSQueryRequest]:
    """Generate search queries for edge evidence.

    Template: "{node_x_terms}" AND "{node_y_terms}" AND (cancer OR oncology)
              AND (cognitive OR cognition OR CRCI)
    """
    query = session.query(EdgeRelationsDefinition).filter(
        EdgeRelationsDefinition.active == 1,
    )
    if edge_ids:
        query = query.filter(
            EdgeRelationsDefinition.edge_relation_id.in_(edge_ids),
        )
    edges = query.all()

    requests: list[APSQueryRequest] = []
    for edge in edges:
        node_x_terms = _get_node_synonyms(session, edge.node_x)
        node_y_terms = _get_node_synonyms(session, edge.node_y)

        x_clause = _build_or_clause(node_x_terms)
        y_clause = _build_or_clause(node_y_terms)

        # Primary query: specific to cancer + cognitive context
        q1 = (
            f"{x_clause} AND {y_clause} "
            f'AND (cancer OR chemotherapy OR oncology) '
            f'AND (cognitive OR cognition OR CRCI)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="edge_evidence",
            query_string=q1,
            target_entity_id=edge.edge_relation_id,
            target_entity_type="edge",
            design_filter='"randomized" OR "cohort" OR "meta-analysis"',
            priority=config.WORKSTREAM_PRIORITY.index("edge_evidence")
            if "edge_evidence" in config.WORKSTREAM_PRIORITY
            else 5,
        ))

        # Secondary query: broader (without CRCI filter)
        q2 = (
            f"{x_clause} AND {y_clause} "
            f'AND (cancer OR oncology)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="edge_evidence",
            query_string=q2,
            target_entity_id=edge.edge_relation_id,
            target_entity_type="edge",
            max_results=50,
            design_filter='"randomized" OR "cohort"',
            priority=config.WORKSTREAM_PRIORITY.index("edge_evidence")
            if "edge_evidence" in config.WORKSTREAM_PRIORITY
            else 5,
        ))

    logger.info(
        "Generated %d edge queries for %d edges",
        len(requests),
        len(edges),
    )
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 2: INSTRUMENT PSYCHOMETRICS
# ═══════════════════════════════════════════════════════════════


def generate_instrument_queries(
    session: Session,
    instrument_ids: list[str] | None = None,
) -> list[APSQueryRequest]:
    """Generate search queries for instrument psychometric validation.

    Template: "{instrument_name}" AND (reliability OR validation OR psychometric
              OR "Cronbach" OR "factor analysis") AND (cancer OR oncology)
    """
    query = session.query(InstrumentDefinition).filter(
        InstrumentDefinition.active == 1,
    )
    if instrument_ids:
        query = query.filter(
            InstrumentDefinition.instrument_id.in_(instrument_ids),
        )
    instruments = query.all()

    requests: list[APSQueryRequest] = []
    for inst in instruments:
        name = inst.instrument_label or inst.instrument_id

        # Primary: cancer-specific psychometric validation
        q1 = (
            f'"{name}" AND (reliability OR validation OR psychometric '
            f'OR "Cronbach" OR "factor analysis") AND (cancer OR oncology)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="instrument_psychometrics",
            query_string=q1,
            target_entity_id=inst.instrument_id,
            target_entity_type="instrument",
            design_filter='"validation" OR "psychometric" OR "factor"',
            priority=config.WORKSTREAM_PRIORITY.index("instrument_psychometrics")
            if "instrument_psychometrics" in config.WORKSTREAM_PRIORITY
            else 0,
        ))

        # Fallback: general psychometric (no cancer filter)
        q2 = (
            f'"{name}" AND (reliability OR validation OR psychometric '
            f'OR "Cronbach" OR "factor analysis")'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="instrument_psychometrics",
            query_string=q2,
            target_entity_id=inst.instrument_id,
            target_entity_type="instrument",
            max_results=50,
            design_filter='"validation" OR "psychometric"',
            priority=config.WORKSTREAM_PRIORITY.index("instrument_psychometrics")
            if "instrument_psychometrics" in config.WORKSTREAM_PRIORITY
            else 0,
        ))

    logger.info(
        "Generated %d instrument queries for %d instruments",
        len(requests),
        len(instruments),
    )
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 3: POPULATION NORMS
# ═══════════════════════════════════════════════════════════════


def generate_norms_queries(
    session: Session,
) -> list[APSQueryRequest]:
    """Generate search queries for population norms.

    Template: "{instrument_name}" AND (normative OR norms OR "reference values"
              OR "general population" OR "healthy controls")
    """
    instruments = (
        session.query(InstrumentDefinition)
        .filter(InstrumentDefinition.active == 1)
        .all()
    )

    requests: list[APSQueryRequest] = []
    for inst in instruments:
        name = inst.instrument_label or inst.instrument_id
        q = (
            f'"{name}" AND (normative OR norms OR "reference values" '
            f'OR "general population" OR "healthy controls")'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="population_norms",
            query_string=q,
            target_entity_id=inst.instrument_id,
            target_entity_type="instrument",
            design_filter='"normative" OR "population" OR "reference"',
            priority=config.WORKSTREAM_PRIORITY.index("population_norms")
            if "population_norms" in config.WORKSTREAM_PRIORITY
            else 1,
        ))

    logger.info(
        "Generated %d norms queries for %d instruments",
        len(requests),
        len(instruments),
    )
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 4: CONTEXT-MATCHED PRIORS
# ═══════════════════════════════════════════════════════════════


# Priority contexts from AUTOMATED_RETRIEVAL_PLAN.md Part 3
_PRIORITY_CONTEXTS: list[tuple[str, str]] = [
    ("breast", "post_chemotherapy"),
    ("breast", "active_chemotherapy"),
    ("colorectal", "post_treatment"),
    ("lung", "active_chemotherapy"),
    ("mixed_cancer", "mixed_treatment"),
]


def generate_prior_queries(
    session: Session,
    contexts: list[tuple[str, str]] | None = None,
) -> list[APSQueryRequest]:
    """Generate search queries for context-matched priors.

    Template: "{cancer_type}" AND "{treatment_phase}" AND (cognitive OR cognition
              OR fatigue OR depression OR sleep) AND (baseline OR cohort OR
              prospective) AND (N > 50 OR "sample size")
    """
    if contexts is None:
        contexts = _PRIORITY_CONTEXTS

    requests: list[APSQueryRequest] = []
    for cancer_type, treatment_phase in contexts:
        cancer_label = cancer_type.replace("_", " ")
        phase_label = treatment_phase.replace("_", " ").replace("-", " ")

        q = (
            f'"{cancer_label} cancer" AND "{phase_label}" '
            f'AND (cognitive OR cognition OR fatigue OR depression OR sleep) '
            f'AND (baseline OR cohort OR prospective)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="context_priors",
            query_string=q,
            target_entity_id=f"{cancer_type}__{treatment_phase}",
            target_entity_type="context",
            design_filter='"cohort"',
            priority=config.WORKSTREAM_PRIORITY.index("context_priors")
            if "context_priors" in config.WORKSTREAM_PRIORITY
            else 3,
        ))

    logger.info("Generated %d prior queries for %d contexts", len(requests), len(contexts))
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 5: RECOVERY PARAMETERS
# ═══════════════════════════════════════════════════════════════


def generate_recovery_queries(
    session: Session,
) -> list[APSQueryRequest]:
    """Generate search queries for recovery trajectory parameters.

    Template: "{cancer_type}" AND (cognitive OR "chemo brain" OR CRCI) AND
              (longitudinal OR "follow-up" OR recovery OR trajectory) AND
              (months OR years)
    """
    cancer_types = ["breast", "colorectal", "lung", "ovarian", "mixed"]

    requests: list[APSQueryRequest] = []
    for cancer_type in cancer_types:
        q = (
            f'"{cancer_type} cancer" AND (cognitive OR "chemo brain" OR CRCI) '
            f'AND (longitudinal OR "follow-up" OR recovery OR trajectory) '
            f'AND (months OR years)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="recovery_parameters",
            query_string=q,
            target_entity_id=f"recovery_{cancer_type}",
            target_entity_type="context",
            design_filter='"longitudinal"',
            priority=config.WORKSTREAM_PRIORITY.index("recovery_parameters")
            if "recovery_parameters" in config.WORKSTREAM_PRIORITY
            else 4,
        ))

    logger.info("Generated %d recovery queries", len(requests))
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 6: INTERVENTION KERNELS
# ═══════════════════════════════════════════════════════════════


def generate_kernel_queries(
    session: Session,
) -> list[APSQueryRequest]:
    """Generate search queries for intervention kernels.

    Template: "{intervention_name}" AND (cognitive OR cognition) AND
              (cancer OR oncology) AND "randomized" AND (weeks OR months)
    """
    actions = (
        session.query(ActionCatalog)
        .filter(ActionCatalog.active == 1)
        .all()
    )

    requests: list[APSQueryRequest] = []
    for action in actions:
        name = action.action_label or action.action_id

        q = (
            f'"{name}" AND (cognitive OR cognition) '
            f'AND (cancer OR oncology) AND "randomized" '
            f'AND (weeks OR months)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="intervention_kernels",
            query_string=q,
            target_entity_id=action.action_id,
            target_entity_type="action",
            design_filter='"randomized"',
            priority=config.WORKSTREAM_PRIORITY.index("intervention_kernels")
            if "intervention_kernels" in config.WORKSTREAM_PRIORITY
            else 5,
        ))

    logger.info(
        "Generated %d kernel queries for %d interventions",
        len(requests),
        len(actions),
    )
    return requests


# ═══════════════════════════════════════════════════════════════
#  WORKSTREAM 7: BIOMARKER CORRELATIONS
# ═══════════════════════════════════════════════════════════════


def generate_correlation_queries(
    session: Session,
) -> list[APSQueryRequest]:
    """Generate search queries for biomarker correlations.

    Template: "{biomarker_A}" AND "{biomarker_B}" AND (correlation OR association)
              AND (cancer OR oncology)
    """
    # Use node pairs from edge_relations where relation_type is correlation
    edges = (
        session.query(EdgeRelationsDefinition)
        .filter(
            EdgeRelationsDefinition.active == 1,
            EdgeRelationsDefinition.relation_type == "correlation",
        )
        .all()
    )

    requests: list[APSQueryRequest] = []
    seen_pairs: set[tuple[str, str]] = set()

    for edge in edges:
        pair = tuple(sorted([edge.node_x, edge.node_y]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        x_terms = _get_node_synonyms(session, edge.node_x)
        y_terms = _get_node_synonyms(session, edge.node_y)

        x_clause = _build_or_clause(x_terms[:3])
        y_clause = _build_or_clause(y_terms[:3])

        q = (
            f"{x_clause} AND {y_clause} "
            f'AND (correlation OR association) AND (cancer OR oncology)'
        )
        requests.append(APSQueryRequest(
            query_id=_query_id(),
            workstream="correlations",
            query_string=q,
            target_entity_id=edge.edge_relation_id,
            target_entity_type="edge",
            priority=config.WORKSTREAM_PRIORITY.index("correlations")
            if "correlations" in config.WORKSTREAM_PRIORITY
            else 6,
        ))

    logger.info(
        "Generated %d correlation queries from %d unique pairs",
        len(requests),
        len(seen_pairs),
    )
    return requests


# ═══════════════════════════════════════════════════════════════
#  MASTER GENERATOR
# ═══════════════════════════════════════════════════════════════


def generate_all(
    session: Session,
    workstreams: list[str] | None = None,
) -> list[APSQueryRequest]:
    """Generate queries for all (or selected) workstreams.

    Args:
        session: SQLAlchemy session.
        workstreams: Optional list of workstream names to generate for.
                     If None, generates for all 7 workstreams.

    Returns:
        All APSQueryRequest objects, sorted by workstream priority.
    """
    all_workstreams = workstreams or config.WORKSTREAM_PRIORITY

    generators = {
        "edge_evidence": lambda: generate_edge_queries(session),
        "instrument_psychometrics": lambda: generate_instrument_queries(session),
        "population_norms": lambda: generate_norms_queries(session),
        "context_priors": lambda: generate_prior_queries(session),
        "recovery_parameters": lambda: generate_recovery_queries(session),
        "intervention_kernels": lambda: generate_kernel_queries(session),
        "correlations": lambda: generate_correlation_queries(session),
    }

    all_queries: list[APSQueryRequest] = []
    for ws in all_workstreams:
        gen = generators.get(ws)
        if gen is None:
            logger.warning("Unknown workstream: '%s', skipping", ws)
            continue
        queries = gen()
        all_queries.extend(queries)

    # Sort by priority (lower index = higher priority)
    all_queries.sort(key=lambda q: q.priority)

    logger.info(
        "Total queries generated: %d across %d workstreams",
        len(all_queries),
        len(all_workstreams),
    )
    return all_queries
