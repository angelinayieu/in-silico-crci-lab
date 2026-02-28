# VERIFIED: adapter matches FULLTEXT_SOURCE_PRIORITY "core" entry
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: rate limit from config.CORE_API_RPS (0.5 req/s free tier)
# VERIFIED: forward wiring — returns CandidateMetadata + PDF bytes
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.CoreApi
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (extended)
Purpose: CORE API adapter for institutional repository paper retrieval.
         CORE indexes 200M+ papers from 10K+ data providers.
         Free tier: ~5 req/10sec. Higher with API key.
         Uses CORE API v3 (https://api.core.ac.uk/v3/).
Reads: DOIs or search queries
Writes: CandidateMetadata[] + PDF bytes for pipeline
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

_BASE_URL = "https://api.core.ac.uk/v3"
_TIMEOUT_SECONDS = 30


class CoreApiAdapter(SourceAdapter):
    """CORE API adapter for discovering OA papers from institutional repos.

    CORE aggregates open access research papers from thousands of data
    providers (institutional repositories, preprint servers, journals).
    Requires an API key for reliable access (free registration).

    Set API key via CORE_API_KEY environment variable.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="core",
            requests_per_second=config.CORE_API_RPS,
        )
        self._api_key = os.environ.get("CORE_API_KEY", "")
        if not self._api_key:
            logger.warning(
                "CORE_API_KEY not set. CORE API requires an API key for "
                "reliable access. Register free at https://core.ac.uk/services/api"
            )
        logger.info(
            "CORE API adapter initialized (%.1f req/s, api_key=%s)",
            config.CORE_API_RPS,
            bool(self._api_key),
        )

    def _headers(self) -> dict[str, str]:
        """Build request headers with API key."""
        headers: dict[str, str] = {
            "User-Agent": "CRCI-RetrievalBot/1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 50,
    ) -> list[CandidateMetadata]:
        """Search CORE for papers.

        Args:
            query: Search query string.
            filters: Optional. Supports 'year_from', 'year_to' keys.
            max_results: Maximum results.

        Returns:
            List of CandidateMetadata.
        """
        if not self._api_key:
            logger.debug("CORE API key not configured, skipping search")
            return []

        results: list[CandidateMetadata] = []
        offset = 0
        per_page = min(max_results, 100)

        while len(results) < max_results:
            self._rate_limit()
            params: dict[str, str] = {
                "q": query,
                "limit": str(per_page),
                "offset": str(offset),
            }

            try:
                resp = requests.get(
                    f"{_BASE_URL}/search/works",
                    params=params,
                    headers=self._headers(),
                    timeout=_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning("CORE search failed: %s", exc)
                break
            except ValueError as exc:
                self._last_error = str(exc)
                logger.warning("CORE JSON parse error: %s", exc)
                break

            works = data.get("results", [])
            if not works:
                break

            for work in works:
                candidate = self._parse_work(work)
                if candidate:
                    results.append(candidate)

            if len(works) < per_page:
                break
            offset += len(works)

        logger.info(
            "CORE search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results[:max_results]

    def _parse_work(self, work: dict) -> CandidateMetadata | None:
        """Parse a single CORE work object."""
        title = work.get("title")
        doi = work.get("doi")

        if not title and not doi:
            return None

        # Clean DOI
        if doi:
            for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
                if doi.startswith(prefix):
                    doi = doi[len(prefix):]

        # Authors
        authors: list[str] = []
        for author in work.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Year
        year: int | None = work.get("yearPublished")

        # Abstract
        abstract = work.get("abstract")

        # Journal
        journals = work.get("journals", [])
        journal: str | None = None
        if journals and isinstance(journals, list):
            first_journal = journals[0] if journals else {}
            if isinstance(first_journal, dict):
                journal = first_journal.get("title")

        # Download URL
        download_url = work.get("downloadUrl")

        # OA status — CORE only indexes OA
        is_oa = True
        oa_status = OAStatus.GREEN

        return CandidateMetadata(
            source="core",
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            is_oa=is_oa,
            oa_status=oa_status,
            extra={"download_url": download_url} if download_url else {},
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a paper by DOI.

        Args:
            identifier: DOI string.

        Returns:
            PaperMetadata if found, None otherwise.
        """
        if not self._api_key:
            return None

        self._rate_limit()

        # CORE v3 supports DOI lookup via /works?doi=...
        try:
            resp = requests.get(
                f"{_BASE_URL}/search/works",
                params={"q": f'doi:"{identifier}"', "limit": "1"},
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            self._last_error = str(exc)
            logger.warning("CORE metadata fetch failed for %s: %s", identifier, exc)
            return None

        works = data.get("results", [])
        if not works:
            return None

        candidate = self._parse_work(works[0])
        if not candidate:
            return None

        return PaperMetadata(
            doi=candidate.doi,
            title=candidate.title or "",
            authors=candidate.authors,
            journal=candidate.journal,
            year=candidate.year,
            abstract=candidate.abstract,
            is_oa=candidate.is_oa,
            oa_status=candidate.oa_status,
            sources_checked=["core"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if CORE has a downloadable full text for a DOI.

        Args:
            identifier: DOI string.

        Returns:
            FullTextAvailability.
        """
        if not self._api_key or not identifier:
            return FullTextAvailability(available=False, source="core")

        metadata = self.fetch_metadata(identifier)
        if not metadata:
            return FullTextAvailability(available=False, source="core")

        # Re-search to get download URL (not stored in PaperMetadata)
        self._rate_limit()
        try:
            resp = requests.get(
                f"{_BASE_URL}/search/works",
                params={"q": f'doi:"{identifier}"', "limit": "1"},
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            return FullTextAvailability(available=False, source="core")

        works = data.get("results", [])
        if not works:
            return FullTextAvailability(available=False, source="core")

        download_url = works[0].get("downloadUrl")
        if not download_url:
            return FullTextAvailability(available=False, source="core")

        return FullTextAvailability(
            available=True,
            source="core",
            url=download_url,
            format="pdf",
            oa_status=OAStatus.GREEN,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download PDF via CORE's download URL.

        Args:
            identifier: DOI string.

        Returns:
            Raw PDF bytes, or None if unavailable.
        """
        if not self._api_key:
            return None

        availability = self.check_fulltext(identifier)
        if not availability.available or not availability.url:
            return None

        self._rate_limit()
        try:
            resp = requests.get(
                availability.url,
                timeout=config.RETRIEVAL_PDF_DOWNLOAD_TIMEOUT_SEC,
                headers={"User-Agent": "CRCI-RetrievalBot/1.0"},
                allow_redirects=True,
            )
            resp.raise_for_status()

            # Verify PDF magic bytes
            if not resp.content[:5] == b"%PDF-":
                logger.warning(
                    "CORE download URL did not return PDF for %s "
                    "(starts with %r, %d bytes)",
                    identifier,
                    resp.content[:20],
                    len(resp.content),
                )
                return None

            logger.info(
                "Retrieved PDF via CORE for %s (%d bytes)",
                identifier,
                len(resp.content),
            )
            return resp.content

        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "CORE PDF download failed for %s: %s", identifier, exc,
            )
            return None

    def health(self) -> AdapterStatus:
        """Check CORE API adapter health."""
        if not self._api_key:
            return AdapterStatus(
                adapter_name=self.adapter_name,
                health=AdapterHealth.DEGRADED,
                requests_today=self._request_count,
                last_error="CORE_API_KEY not configured",
            )

        try:
            self._rate_limit()
            resp = requests.get(
                f"{_BASE_URL}/search/works",
                params={"q": "test", "limit": "1"},
                headers=self._headers(),
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
