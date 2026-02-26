# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads SpanLabel[] from P1, edge_relations from DB
# VERIFIED: forward wiring — writes GroundedSpan[] for TB group_assembler
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P1-CE.CONCEPT_ENGINE
Spec: Master Spec v2.0 §5.7, SYS_EXTRACTION_COMPLETE.md §515-520 (EX-P1-CE)
Purpose: Map extracted concepts to ontology IDs (edge_relation_id, node_id).
         This bridges AG05's statistical spans to the causal DAG.

Reads: SpanLabel[] (from P1 agents via context)
       edge_relations_definitions_v1, biomarker_node_definitions_v1,
       instrument_definitions_v1 (from DB)
       meta.json target_edges (from context, when available)
Writes: GroundedSpan[] (consumed by TB group_assembler)
Gates: None (grounding is best-effort; UNRESOLVED spans pass through)

Resolution modes (per spec §5.7):
  Mode 1 — Section Context + meta.json hints (deterministic)
  Mode 2 — Instrument→Node→Edge resolution (alias matching)
  Mode 3 — LLM-assisted (DEEP mode only, not implemented in v1)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from crci.shared.models.intermediate_states import GroundedSpan, SpanLabel

logger = logging.getLogger(__name__)


class ConceptEngine:
    """Ontology grounding engine for extracted spans.

    Maps SpanLabel objects to edge_relation_ids from the causal DAG.
    """

    def __init__(self, session: Session):
        self._session = session
        self._edges: list[dict[str, Any]] = []
        self._node_labels: dict[str, str] = {}  # node_id → node_label
        self._instrument_node_map: dict[str, str] = {}  # instrument_id → node_id
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load ontology data from DB."""
        if self._loaded:
            return

        # Load edge definitions
        rows = self._session.execute(
            text(
                "SELECT edge_relation_id, node_x, node_y, relation_label, "
                "canonical_statement, default_effect_direction "
                "FROM edge_relations_definitions_v1 WHERE active = 1"
            )
        ).fetchall()
        self._edges = [
            {
                "edge_relation_id": r[0],
                "source_node": r[1],
                "target_node": r[2],
                "relation_label": r[3] or "",
                "canonical_statement": r[4] or "",
                "direction": r[5],
            }
            for r in rows
        ]

        # Load node labels for keyword matching
        node_rows = self._session.execute(
            text(
                "SELECT node_id, node_label FROM biomarker_node_definitions_v1 "
                "WHERE active = 1"
            )
        ).fetchall()
        self._node_labels = {r[0]: r[1] for r in node_rows}

        # Load instrument → node mapping
        inst_rows = self._session.execute(
            text(
                "SELECT instrument_id, maps_to_node_id "
                "FROM instrument_definitions_v1 WHERE active = 1"
            )
        ).fetchall()
        self._instrument_node_map = {r[0]: r[1] for r in inst_rows}

        self._loaded = True
        logger.info(
            "ConceptEngine loaded: %d edges, %d nodes, %d instruments",
            len(self._edges),
            len(self._node_labels),
            len(self._instrument_node_map),
        )

    def ground_spans(
        self,
        span_labels: list[SpanLabel],
        context: dict[str, Any],
    ) -> list[GroundedSpan]:
        """Ground SpanLabel objects to causal DAG edge_relation_ids.

        Resolution strategy:
        1. Use meta.json target_edges if available (highest confidence)
        2. Use AG04 outcome instruments to resolve target node
        3. Use source_section keywords to match edge descriptions
        4. Fall through as UNRESOLVED

        Args:
            span_labels: SpanLabel list from AG05.
            context: Pipeline context with agent outputs.

        Returns:
            List of GroundedSpan objects.
        """
        self._ensure_loaded()

        # Gather hints from context
        target_edges = self._get_target_edges(context)
        outcome_nodes = self._get_outcome_nodes(context)

        grounded: list[GroundedSpan] = []
        n_resolved = 0

        for span in span_labels:
            gs = self._ground_single_span(span, target_edges, outcome_nodes)
            grounded.append(gs)
            if gs.edge_relation_id is not None:
                n_resolved += 1

        total = len(span_labels)
        logger.info(
            "ConceptEngine: %d/%d spans grounded (%.0f%% resolved)",
            n_resolved,
            total,
            (n_resolved / total * 100) if total > 0 else 0,
        )

        return grounded

    def _ground_single_span(
        self,
        span: SpanLabel,
        target_edges: list[str],
        outcome_nodes: set[str],
    ) -> GroundedSpan:
        """Ground a single SpanLabel.

        Priority:
        1. meta.json target_edges (deterministic, highest confidence)
        2. Instrument → node → edge resolution
        3. Source section keyword matching
        """
        # Mode 1: meta.json target edges
        if target_edges:
            edge_id = self._match_from_target_edges(span, target_edges)
            if edge_id is not None:
                return GroundedSpan(
                    span=span,
                    edge_relation_id=edge_id,
                    grounding_confidence=0.9,
                    grounding_mode="meta_hint",
                )

        # Mode 2: outcome node → edge resolution
        if outcome_nodes:
            edge_id = self._match_from_outcome_nodes(span, outcome_nodes)
            if edge_id is not None:
                return GroundedSpan(
                    span=span,
                    edge_relation_id=edge_id,
                    grounding_confidence=0.8,
                    grounding_mode="instrument_resolution",
                )

        # Mode 3: keyword matching on section/text
        edge_id = self._match_from_keywords(span)
        if edge_id is not None:
            return GroundedSpan(
                span=span,
                edge_relation_id=edge_id,
                grounding_confidence=0.6,
                grounding_mode="keyword",
            )

        # Unresolved
        return GroundedSpan(
            span=span,
            edge_relation_id=None,
            grounding_confidence=0.0,
            grounding_mode="unresolved",
        )

    def _get_target_edges(self, context: dict[str, Any]) -> list[str]:
        """Extract target edge IDs from meta.json, validated against DB.

        Validates each ID exists in edge_relations_definitions_v1.
        Auto-corrects EDGE_* → ER_* prefix mismatch.
        """
        meta = context.get("companion_meta") or {}
        target_edges = meta.get("target_edges")
        if not target_edges:
            target_edges = meta.get("targeted_edges")
        if not isinstance(target_edges, list):
            return []

        valid_ids = {e["edge_relation_id"] for e in self._edges}
        validated: list[str] = []
        for eid in target_edges:
            if not isinstance(eid, str):
                continue
            if eid in valid_ids:
                validated.append(eid)
            else:
                # Try EDGE_ → ER_ auto-correction
                fuzzy = eid.replace("EDGE_", "ER_")
                if fuzzy in valid_ids:
                    logger.warning(
                        "ConceptEngine: meta.json target_edge '%s' not found, "
                        "auto-corrected to '%s'",
                        eid,
                        fuzzy,
                    )
                    validated.append(fuzzy)
                else:
                    logger.error(
                        "ConceptEngine: meta.json target_edge '%s' does NOT "
                        "exist in edge_relations_definitions_v1 — SKIPPING",
                        eid,
                    )

        if not validated and target_edges:
            logger.error(
                "ConceptEngine: ALL %d target_edges from meta.json were "
                "invalid: %s",
                len(target_edges),
                target_edges,
            )

        return validated

    def _get_outcome_nodes(self, context: dict[str, Any]) -> set[str]:
        """Extract outcome nodes from AG04 instrument data."""
        nodes: set[str] = set()

        # From AG04 outcomes
        outcomes = context.get("outcomes", [])
        for outcome in outcomes:
            inst_id = getattr(outcome, "instrument_id", None)
            if inst_id and inst_id in self._instrument_node_map:
                nodes.add(self._instrument_node_map[inst_id])
            # Also check instrument_name for fuzzy matching
            inst_name = getattr(outcome, "instrument_name", "")
            if inst_name:
                for iid, nid in self._instrument_node_map.items():
                    if iid.lower() in inst_name.lower() or inst_name.lower() in iid.lower():
                        nodes.add(nid)

        return nodes

    def _match_from_target_edges(
        self, span: SpanLabel, target_edges: list[str]
    ) -> str | None:
        """Try to match span to a target edge using section context.

        When only one target edge exists, all spans map to it.
        When multiple exist, use source_section keywords to disambiguate.
        """
        if len(target_edges) == 0:
            return None

        if len(target_edges) == 1:
            return target_edges[0]

        # Multiple target edges — try to disambiguate
        section = (span.source_section or "").lower()
        span_text = (span.value or "").lower()

        # Build edge → keyword mapping from canonical statements
        edge_info = {
            e["edge_relation_id"]: (
                e["relation_label"].lower() + " " + e["canonical_statement"].lower()
            )
            for e in self._edges
            if e["edge_relation_id"] in target_edges
        }

        best_edge: str | None = None
        best_score = 0

        for eid, description in edge_info.items():
            score = 0
            # Check section keywords
            for keyword in _extract_keywords(description):
                if keyword in section or keyword in span_text:
                    score += 1
            if score > best_score:
                best_score = score
                best_edge = eid

        # If no disambiguation possible, use the first target edge
        # (still better than UNRESOLVED)
        if best_edge is None and target_edges:
            return target_edges[0]

        return best_edge

    def _match_from_outcome_nodes(
        self, span: SpanLabel, outcome_nodes: set[str]
    ) -> str | None:
        """Match span to an edge that targets one of the outcome nodes."""
        candidates = [
            e for e in self._edges
            if e["target_node"] in outcome_nodes
        ]
        if len(candidates) == 1:
            return candidates[0]["edge_relation_id"]
        if len(candidates) > 1:
            # Use section keywords to pick
            section = (span.source_section or "").lower()
            for c in candidates:
                desc = c["canonical_statement"].lower()
                for kw in _extract_keywords(desc):
                    if kw in section:
                        return c["edge_relation_id"]
            # Default to first candidate
            return candidates[0]["edge_relation_id"]
        return None

    def _match_from_keywords(self, span: SpanLabel) -> str | None:
        """Last-resort: keyword match using edge descriptions AND node labels.

        Enhanced to also match against:
        - context field from AG05 (e.g., "Cohen's d for working memory")
        - node labels (NODE_COG_WORKING_MEM → "working memory")
        """
        section = (span.source_section or "").lower()
        span_text = (span.value or "").lower()
        context_text = (getattr(span, "context", "") or "").lower()
        combined = section + " " + span_text + " " + context_text

        if not combined.strip():
            return None

        combined_keywords = set(_extract_keywords(combined))
        if not combined_keywords:
            return None

        best_edge: str | None = None
        best_score = 0

        for e in self._edges:
            score = 0
            # Match against edge canonical_statement + relation_label
            desc = (e["relation_label"] + " " + e["canonical_statement"]).lower()
            desc_keywords = set(_extract_keywords(desc))
            score += len(combined_keywords & desc_keywords)

            # Match against source and target NODE LABELS
            src_label = self._node_labels.get(e["source_node"], "").lower()
            tgt_label = self._node_labels.get(e["target_node"], "").lower()
            node_keywords = set(_extract_keywords(src_label + " " + tgt_label))
            score += len(combined_keywords & node_keywords)

            if score > best_score and score >= 2:
                best_score = score
                best_edge = e["edge_relation_id"]

        return best_edge


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text for matching."""
    # Remove common words
    stopwords = {
        "the", "a", "an", "and", "or", "in", "of", "to", "for", "is",
        "are", "was", "were", "be", "been", "has", "have", "had",
        "with", "from", "by", "at", "on", "not", "no", "but", "that",
        "this", "it", "its", "may", "can", "will", "via", "between",
        "than", "more", "less", "through", "also", "into",
    }
    words = text.lower().split()
    return [w for w in words if len(w) > 2 and w not in stopwords]
