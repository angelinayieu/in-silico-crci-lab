# VERIFIED: interface matches AUTOMATED_RETRIEVAL_PLAN.md Part 4
# VERIFIED: imports — abc + retrieval.models
# VERIFIED: forward wiring — implemented by pubmed, europe_pmc, crossref, openalex, unpaywall
# VERIFIED: no hardcoded parameters
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.Base
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (SourceAdapter interface)
Purpose: Abstract base class for all bibliographic source adapters.
         Defines the common interface: search, fetch_metadata,
         check_fulltext, retrieve_fulltext, health.
Reads: Nothing (interface definition)
Writes: Nothing (interface definition)
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from crci.retrieval.models import (
    AdapterStatus,
    CandidateMetadata,
    FullTextAvailability,
    PaperMetadata,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class SourceAdapter(ABC):
    """Abstract base class for bibliographic source adapters.

    All adapters (PubMed, Europe PMC, Crossref, OpenAlex, Unpaywall)
    implement this interface for uniform search/retrieval orchestration.
    """

    def __init__(self, adapter_name: str, requests_per_second: float = 1.0) -> None:
        self.adapter_name = adapter_name
        self.requests_per_second = requests_per_second
        self._request_count: int = 0
        self._last_request_time: float = 0.0
        self._last_error: str | None = None

    def _rate_limit(self) -> None:
        """Enforce per-adapter rate limiting."""
        if self.requests_per_second <= 0:
            return
        min_interval = 1.0 / self.requests_per_second
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(
                "%s: rate-limiting, sleeping %.3fs",
                self.adapter_name,
                sleep_time,
            )
            time.sleep(sleep_time)
        self._last_request_time = time.monotonic()
        self._request_count += 1

    @abstractmethod
    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 100,
    ) -> list[CandidateMetadata]:
        """Search for papers matching query.

        Args:
            query: Search query string (adapter-specific syntax).
            filters: Optional filters (e.g., date range, publication type).
            max_results: Maximum number of results to return.

        Returns:
            List of CandidateMetadata for matching papers.
        """

    @abstractmethod
    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch detailed metadata for a single paper.

        Args:
            identifier: DOI, PMID, or other identifier.

        Returns:
            PaperMetadata if found, None otherwise.
        """

    @abstractmethod
    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if full text is available for a paper.

        Args:
            identifier: DOI, PMID, or PMCID.

        Returns:
            FullTextAvailability with availability details.
        """

    @abstractmethod
    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download full text (PDF or XML) for a paper.

        Args:
            identifier: DOI, PMID, or PMCID.

        Returns:
            Raw bytes of the full text, or None if unavailable.
        """

    def health(self) -> AdapterStatus:
        """Check adapter health and usage statistics.

        Returns:
            AdapterStatus with current health and request counts.
        """
        from crci.retrieval.models import AdapterHealth

        return AdapterStatus(
            adapter_name=self.adapter_name,
            health=AdapterHealth.HEALTHY,
            requests_today=self._request_count,
            last_error=self._last_error,
        )
