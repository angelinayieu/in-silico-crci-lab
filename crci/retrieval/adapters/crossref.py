# VERIFIED: adapter matches AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 3
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: backward wiring — receives query strings from search_coordinator
# VERIFIED: forward wiring — returns CandidateMetadata for APS scoring
# VERIFIED: rate limit from config.CROSSREF_RPS
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.Crossref
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 3 (Crossref)
Purpose: Crossref adapter for DOI resolution and metadata enrichment.
         /works?query=... for search, /works/{doi} for lookup.
         Polite pool: include mailto in User-Agent header.
Reads: Query strings and DOIs from search_coordinator
Writes: CandidateMetadata[] for APS scoring
"""
from __future__ import annotations

import logging
import os

import requests

from crci.shared import config
from crci.retrieval.models import (
    AdapterHealth,
    AdapterStatus,
    CandidateMetadata,
    FullTextAvailability,
    OAStatus,
    PaperMetadata,
)
from crci.retrieval.adapters.base import SourceAdapter

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_TIMEOUT_SECONDS = 30
_DEFAULT_ROWS = 100


class CrossrefAdapter(SourceAdapter):
    """Crossref adapter for DOI resolution and metadata.

    Uses the polite pool by including a mailto: in the User-Agent header.
    Email is read from CROSSREF_MAILTO environment variable.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="crossref",
            requests_per_second=config.CROSSREF_RPS,
        )
        self._email = os.environ.get("CROSSREF_MAILTO", "")
        self._headers = {
            "User-Agent": f"CRCI-RetrievalBot/1.0 (mailto:{self._email})"
            if self._email
            else "CRCI-RetrievalBot/1.0",
        }
        logger.info(
            "Crossref adapter initialized (%d req/s, polite=%s)",
            config.CROSSREF_RPS,
            bool(self._email),
        )

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = _DEFAULT_ROWS,
    ) -> list[CandidateMetadata]:
        """Search Crossref by keywords.

        Args:
            query: Search query string.
            filters: Optional filters (e.g., {"from-pub-date": "2020"}).
            max_results: Maximum number of results.

        Returns:
            List of CandidateMetadata.
        """
        self._rate_limit()
        params: dict[str, str] = {
            "query": query,
            "rows": str(min(max_results, 1000)),
        }
        if filters:
            for key, value in filters.items():
                params[f"filter"] = f"{key}:{value}"

        try:
            resp = requests.get(
                _BASE_URL,
                params=params,
                headers=self._headers,
                timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning("Crossref search failed: %s", exc)
            return []
        except ValueError as exc:
            self._last_error = str(exc)
            logger.warning("Crossref JSON parse error: %s", exc)
            return []

        items = data.get("message", {}).get("items", [])
        results = []
        for item in items:
            candidate = self._parse_item(item)
            if candidate:
                results.append(candidate)

        logger.info(
            "Crossref search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results

    def _parse_item(self, item: dict) -> CandidateMetadata | None:
        """Parse a single Crossref work item."""
        doi = item.get("DOI")
        if not doi:
            return None

        # Title
        title_list = item.get("title", [])
        title = title_list[0] if title_list else None

        # Authors
        authors: list[str] = []
        for author in item.get("author", []):
            family = author.get("family", "")
            given = author.get("given", "")
            if family:
                name = f"{family} {given}".strip() if given else family
                authors.append(name)

        # Journal
        container = item.get("container-title", [])
        journal = container[0] if container else None

        # Year
        year = None
        published = item.get("published-print") or item.get("published-online")
        if published:
            date_parts = published.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                try:
                    year = int(date_parts[0][0])
                except (ValueError, IndexError):
                    pass

        # Abstract
        abstract = item.get("abstract")
        if abstract:
            # Crossref abstracts often contain XML/HTML tags
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        # Citation count
        cited_by = item.get("is-referenced-by-count")
        cited_by_count = int(cited_by) if cited_by is not None else None

        # Publication type
        pub_types = [item.get("type", "")]

        # OA status
        license_list = item.get("license", [])
        is_oa = False
        oa_status = OAStatus.CLOSED
        for lic in license_list:
            url = lic.get("URL", "")
            if "creativecommons" in url.lower():
                is_oa = True
                oa_status = OAStatus.GOLD
                break

        return CandidateMetadata(
            source="crossref",
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            publication_types=pub_types,
            is_oa=is_oa,
            oa_status=oa_status,
            cited_by_count=cited_by_count,
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single DOI.

        Args:
            identifier: DOI string.

        Returns:
            PaperMetadata if found, None otherwise.
        """
        self._rate_limit()
        url = f"{_BASE_URL}/{identifier}"

        try:
            resp = requests.get(
                url, headers=self._headers, timeout=_TIMEOUT_SECONDS
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning("Crossref DOI lookup failed for %s: %s", identifier, exc)
            return None

        item = data.get("message", {})
        candidate = self._parse_item(item)
        if not candidate:
            return None

        return PaperMetadata(
            doi=candidate.doi,
            title=candidate.title or "",
            authors=candidate.authors,
            journal=candidate.journal,
            year=candidate.year,
            abstract=candidate.abstract,
            publication_types=candidate.publication_types,
            is_oa=candidate.is_oa,
            oa_status=candidate.oa_status,
            cited_by_count=candidate.cited_by_count,
            sources_checked=["crossref"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Crossref does not provide full text directly."""
        return FullTextAvailability(available=False, source="crossref")

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Crossref does not provide full text directly."""
        return None

    def health(self) -> AdapterStatus:
        """Check Crossref adapter health."""
        try:
            self._rate_limit()
            resp = requests.get(
                _BASE_URL,
                params={"query": "test", "rows": "1"},
                headers=self._headers,
                timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            h = AdapterHealth.HEALTHY
        except Exception as exc:
            self._last_error = str(exc)
            h = AdapterHealth.UNAVAILABLE

        return AdapterStatus(
            adapter_name=self.adapter_name,
            health=h,
            requests_today=self._request_count,
            last_error=self._last_error,
        )
