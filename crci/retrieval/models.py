# VERIFIED: models match AUTOMATED_RETRIEVAL_PLAN.md Part 4 interface
# VERIFIED: imports — pydantic only
# VERIFIED: forward wiring — consumed by all adapters, aps_scorer, search_coordinator
# VERIFIED: no hardcoded parameters
"""
Component: SYS_EXTRACTION.EX-ACQ.Models
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (adapter interface), Part 6 (flow)
Purpose: Pydantic models for the retrieval subsystem:
         CandidateMetadata, PaperMetadata, FullTextAvailability,
         RetrievalResult, AdapterStatus, APSQueryRequest, APSScoredCandidate.
Reads: Nothing (data structure definitions)
Writes: Nothing (instantiated by retrieval modules)
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════


class RetrievalStatus(str, Enum):
    """Status of a full-text retrieval attempt."""

    PENDING = "pending"
    RETRIEVED = "retrieved"
    ABSTRACT_ONLY = "abstract_only"
    FAILED = "failed"
    DEFERRED = "deferred"


class AdapterHealth(str, Enum):
    """Health status of a source adapter."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class TermType(str, Enum):
    """Type of search term in node_search_terms_v1."""

    PRIMARY = "primary"
    SYNONYM = "synonym"
    ABBREVIATION = "abbreviation"
    MESH_HEADING = "mesh_heading"


class OAStatus(str, Enum):
    """Open access status of a paper."""

    GOLD = "gold"
    GREEN = "green"
    HYBRID = "hybrid"
    BRONZE = "bronze"
    CLOSED = "closed"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
#  CANDIDATE & PAPER METADATA
# ═══════════════════════════════════════════════════════════════


class CandidateMetadata(BaseModel):
    """Metadata for a candidate paper returned by a source adapter.

    This is the normalized output of any adapter's search() method.
    All adapters produce CandidateMetadata regardless of source API.
    """

    source: str  # pubmed, europe_pmc, crossref, openalex
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    abstract: str | None = None
    mesh_terms: list[str] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list)
    is_oa: bool = False
    oa_status: OAStatus = OAStatus.UNKNOWN
    cited_by_count: int | None = None
    sample_size: int | None = None  # extracted from abstract if available
    study_design: str | None = None  # extracted from publication type
    extra: dict[str, Any] = Field(default_factory=dict)


class PaperMetadata(BaseModel):
    """Enriched metadata for a paper (after cross-referencing multiple sources)."""

    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    abstract: str | None = None
    mesh_terms: list[str] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list)
    is_oa: bool = False
    oa_status: OAStatus = OAStatus.UNKNOWN
    cited_by_count: int | None = None
    sources_checked: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  FULL-TEXT AVAILABILITY
# ═══════════════════════════════════════════════════════════════


class FullTextAvailability(BaseModel):
    """Result of checking full-text availability for a paper."""

    available: bool = False
    source: str | None = None  # europe_pmc, unpaywall, manual
    url: str | None = None
    format: str | None = None  # pdf, xml, html
    oa_status: OAStatus = OAStatus.UNKNOWN
    license: str | None = None


# ═══════════════════════════════════════════════════════════════
#  RETRIEVAL RESULT
# ═══════════════════════════════════════════════════════════════


class RetrievalResult(BaseModel):
    """Result of a full-text retrieval attempt."""

    doi: str | None = None
    pmid: str | None = None
    status: RetrievalStatus
    cache_path: str | None = None  # path to cached PDF/XML
    source_used: str | None = None  # which adapter provided the full text
    file_size_bytes: int | None = None
    error_message: str | None = None


# ═══════════════════════════════════════════════════════════════
#  ADAPTER STATUS
# ═══════════════════════════════════════════════════════════════


class AdapterStatus(BaseModel):
    """Health status of a source adapter."""

    adapter_name: str
    health: AdapterHealth
    requests_today: int = 0
    requests_limit: int | None = None
    last_error: str | None = None
    avg_latency_ms: float | None = None


# ═══════════════════════════════════════════════════════════════
#  QUERY REQUEST & SCORED CANDIDATE
# ═══════════════════════════════════════════════════════════════


class APSQueryRequest(BaseModel):
    """A search query to be dispatched to source adapters.

    Produced by query_generator.py, consumed by search_coordinator.py.
    """

    query_id: str
    workstream: str  # edge_evidence, instrument_psychometrics, etc.
    query_string: str  # PubMed-style Boolean query
    target_entity_id: str | None = None  # edge_id, instrument_id, etc.
    target_entity_type: str | None = None  # edge, instrument, node, action
    max_results: int = 100
    design_filter: str | None = None  # e.g., "randomized" OR "cohort"
    priority: int = 0  # higher = searched first


class APSScoredCandidate(BaseModel):
    """A candidate paper with its APS score.

    Produced by aps_scorer.py, consumed by fulltext_retriever.py.
    """

    candidate: CandidateMetadata
    aps_score: float = Field(ge=0.0, le=1.0)
    aps_components: dict[str, float] = Field(default_factory=dict)
    author_gap_boosted: bool = False
    workstream: str | None = None
    target_entity_id: str | None = None
    decision: str = "DISPATCH"  # DISPATCH or DEFER
