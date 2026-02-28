# VERIFIED: config matches AUTOMATED_RETRIEVAL_PLAN.md Part 9
# VERIFIED: API keys from environment variables
# VERIFIED: all constants imported from shared/config.py
"""
Component: SYS_EXTRACTION.EX-ACQ.Config
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 9 (Budget and Rate-Limit Controls)
Purpose: Retrieval-specific configuration. API keys from environment,
         rate limits and budget caps from shared/config.py,
         cache paths, source priority.
Reads: Environment variables, shared/config.py
Writes: Nothing (configuration only)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from crci.shared import config


@dataclass(frozen=True)
class RetrievalConfig:
    """Retrieval subsystem configuration.

    API keys from environment variables:
      - NCBI_API_KEY: PubMed E-utilities API key
      - CROSSREF_MAILTO: Email for Crossref polite pool
      - OPENALEX_EMAIL: Email for OpenAlex polite pool
      - UNPAYWALL_EMAIL: Email for Unpaywall API
    """

    # API keys (from environment)
    ncbi_api_key: str | None = None
    crossref_mailto: str | None = None
    openalex_email: str | None = None
    unpaywall_email: str | None = None
    core_api_key: str | None = None
    s2_api_key: str | None = None

    # Daily budget caps (from shared/config.py)
    max_queries_per_day: int = config.RETRIEVAL_MAX_QUERIES_PER_DAY
    max_candidates_scored_per_day: int = config.RETRIEVAL_MAX_CANDIDATES_SCORED_PER_DAY
    max_fulltext_per_day: int = config.RETRIEVAL_MAX_FULLTEXT_PER_DAY
    max_extractions_per_day: int = config.RETRIEVAL_MAX_EXTRACTIONS_PER_DAY
    max_llm_cost_usd_per_day: float = config.RETRIEVAL_MAX_LLM_COST_USD_PER_DAY

    # Rate limits (from shared/config.py)
    pubmed_rps: int = config.PUBMED_RPS
    crossref_rps: int = config.CROSSREF_RPS
    openalex_rps: int = config.OPENALEX_RPS
    europe_pmc_rps: int = config.EUROPE_PMC_RPS
    unpaywall_rpd: int = config.UNPAYWALL_RPD
    arxiv_delay_sec: float = config.ARXIV_DELAY_SEC
    core_api_rps: float = config.CORE_API_RPS
    s2_rps: float = config.SEMANTIC_SCHOLAR_RPS
    pmc_efetch_rps: float = config.PMC_EFETCH_RPS

    # Content validation thresholds
    min_text_length: int = config.RETRIEVAL_MIN_TEXT_LENGTH
    min_title_match_score: int = config.RETRIEVAL_MIN_TITLE_MATCH_SCORE
    min_pdf_size_bytes: int = config.RETRIEVAL_MIN_PDF_SIZE_BYTES
    http_timeout_sec: float = config.RETRIEVAL_HTTP_TIMEOUT_SEC
    pdf_download_timeout_sec: float = config.RETRIEVAL_PDF_DOWNLOAD_TIMEOUT_SEC

    # Source priority (from shared/config.py)
    fulltext_source_priority: list[str] | None = None

    # Paths
    cache_dir: Path = Path("data/retrieval_cache")
    manual_upload_dir: Path = Path("data/manual_uploads")
    templates_dir: Path = Path("data/templates")

    # APS
    aps_threshold: float = config.APS_THRESHOLD
    author_gap_boost: float = config.AUTHOR_GAP_BOOST_MULTIPLIER

    # Acquisition loop
    loop_hours: int = config.ACQUISITION_LOOP_HOURS

    def __post_init__(self) -> None:
        if self.fulltext_source_priority is None:
            object.__setattr__(
                self,
                "fulltext_source_priority",
                list(config.FULLTEXT_SOURCE_PRIORITY),
            )


def load_retrieval_config() -> RetrievalConfig:
    """Load retrieval configuration from environment and shared config."""
    return RetrievalConfig(
        ncbi_api_key=os.environ.get("NCBI_API_KEY"),
        crossref_mailto=os.environ.get("CROSSREF_MAILTO"),
        openalex_email=os.environ.get("OPENALEX_EMAIL"),
        unpaywall_email=os.environ.get("UNPAYWALL_EMAIL"),
        core_api_key=os.environ.get("CORE_API_KEY"),
        s2_api_key=os.environ.get("S2_API_KEY"),
    )
