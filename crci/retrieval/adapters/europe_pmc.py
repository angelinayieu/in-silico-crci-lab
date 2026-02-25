# VERIFIED: adapter matches AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 2
# VERIFIED: imports — requests, xml.etree, base.SourceAdapter
# VERIFIED: backward wiring — receives query strings from search_coordinator
# VERIFIED: forward wiring — returns CandidateMetadata + full text bytes
# VERIFIED: rate limit from config.EUROPE_PMC_RPS
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.EuropePMC
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 2 (Europe PMC)
Purpose: Europe PMC adapter for search and OA full-text retrieval.
         Search endpoint + fullTextXML/{pmcid} for OA articles.
         Primary full-text source in FULLTEXT_SOURCE_PRIORITY.
Reads: Query strings from search_coordinator
Writes: CandidateMetadata[] + full text bytes for pipeline
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

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

_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
_TIMEOUT_SECONDS = 30
_DEFAULT_PAGE_SIZE = 100


class EuropePMCAdapter(SourceAdapter):
    """Europe PMC adapter for search and OA full-text retrieval.

    Provides both search (via REST API) and full-text XML retrieval
    for open-access articles with PMC IDs.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="europe_pmc",
            requests_per_second=config.EUROPE_PMC_RPS,
        )
        logger.info(
            "Europe PMC adapter initialized (%d req/s)", config.EUROPE_PMC_RPS
        )

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = _DEFAULT_PAGE_SIZE,
    ) -> list[CandidateMetadata]:
        """Search Europe PMC.

        Args:
            query: Search query string.
            filters: Optional filters (e.g., {"fromDate": "2020-01-01"}).
            max_results: Maximum number of results.

        Returns:
            List of CandidateMetadata.
        """
        results: list[CandidateMetadata] = []
        cursor_mark = "*"
        fetched = 0

        while fetched < max_results:
            page_size = min(_DEFAULT_PAGE_SIZE, max_results - fetched)
            self._rate_limit()

            params: dict[str, str] = {
                "query": query,
                "format": "json",
                "pageSize": str(page_size),
                "cursorMark": cursor_mark,
                "resultType": "core",
            }

            try:
                resp = requests.get(
                    _SEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning("Europe PMC search failed: %s", exc)
                break
            except ValueError as exc:
                self._last_error = str(exc)
                logger.warning("Europe PMC JSON parse error: %s", exc)
                break

            result_list = data.get("resultList", {}).get("result", [])
            if not result_list:
                break

            for item in result_list:
                candidate = self._parse_result(item)
                if candidate:
                    results.append(candidate)

            fetched += len(result_list)
            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

        logger.info(
            "Europe PMC search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results

    def _parse_result(self, item: dict) -> CandidateMetadata | None:
        """Parse a single Europe PMC search result."""
        pmid = item.get("pmid")
        pmcid = item.get("pmcid")
        doi = item.get("doi")

        if not any([pmid, pmcid, doi]):
            return None

        title = item.get("title")
        abstract = item.get("abstractText")

        # Authors
        authors: list[str] = []
        author_string = item.get("authorString", "")
        if author_string:
            authors = [a.strip() for a in author_string.split(",")]

        journal = item.get("journalTitle")

        # Year
        year = None
        pub_year = item.get("pubYear")
        if pub_year:
            try:
                year = int(pub_year)
            except ValueError:
                pass

        # Cited by
        cited_by = item.get("citedByCount")
        cited_by_count = int(cited_by) if cited_by else None

        # OA status
        is_oa = item.get("isOpenAccess", "N") == "Y"
        oa_status = OAStatus.UNKNOWN
        if is_oa:
            oa_status = OAStatus.GOLD if pmcid else OAStatus.GREEN

        # Publication types
        pub_types: list[str] = []
        pub_type = item.get("pubType")
        if pub_type:
            if isinstance(pub_type, list):
                pub_types = pub_type
            else:
                pub_types = [pub_type]

        # MeSH terms
        mesh_terms: list[str] = []
        mesh_list = item.get("meshHeadingList", {}).get("meshHeading", [])
        for mesh in mesh_list:
            desc = mesh.get("descriptorName")
            if desc:
                mesh_terms.append(desc)

        return CandidateMetadata(
            source="europe_pmc",
            pmid=pmid,
            pmcid=pmcid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            mesh_terms=mesh_terms,
            publication_types=pub_types,
            is_oa=is_oa,
            oa_status=oa_status,
            cited_by_count=cited_by_count,
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single paper.

        Args:
            identifier: PMID, DOI, or PMCID.

        Returns:
            PaperMetadata if found, None otherwise.
        """
        # Determine query based on identifier format
        if identifier.startswith("PMC"):
            query = f"PMCID:{identifier}"
        elif identifier.startswith("10."):
            query = f"DOI:{identifier}"
        else:
            query = f"EXT_ID:{identifier} AND SRC:MED"

        candidates = self.search(query, max_results=1)
        if not candidates:
            return None

        c = candidates[0]
        return PaperMetadata(
            pmid=c.pmid,
            pmcid=c.pmcid,
            doi=c.doi,
            title=c.title or "",
            authors=c.authors,
            journal=c.journal,
            year=c.year,
            abstract=c.abstract,
            mesh_terms=c.mesh_terms,
            publication_types=c.publication_types,
            is_oa=c.is_oa,
            oa_status=c.oa_status,
            sources_checked=["europe_pmc"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if full-text XML is available for a paper.

        Args:
            identifier: PMCID (e.g., "PMC1234567").

        Returns:
            FullTextAvailability.
        """
        if not identifier.startswith("PMC"):
            return FullTextAvailability(available=False, source="europe_pmc")

        self._rate_limit()
        url = _FULLTEXT_URL.format(pmcid=identifier)

        try:
            resp = requests.head(url, timeout=_TIMEOUT_SECONDS)
            available = resp.status_code == 200
        except requests.RequestException:
            available = False

        return FullTextAvailability(
            available=available,
            source="europe_pmc",
            url=url if available else None,
            format="xml",
            oa_status=OAStatus.GOLD if available else OAStatus.UNKNOWN,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download full-text XML for an OA article.

        Args:
            identifier: PMCID (e.g., "PMC1234567").

        Returns:
            Raw XML bytes, or None if unavailable.
        """
        if not identifier.startswith("PMC"):
            logger.warning(
                "Europe PMC full text requires PMCID, got: %s", identifier
            )
            return None

        self._rate_limit()
        url = _FULLTEXT_URL.format(pmcid=identifier)

        try:
            resp = requests.get(url, timeout=_TIMEOUT_SECONDS)
            resp.raise_for_status()
            logger.info(
                "Retrieved full text from Europe PMC: %s (%d bytes)",
                identifier,
                len(resp.content),
            )
            return resp.content
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "Europe PMC full text retrieval failed for %s: %s",
                identifier,
                exc,
            )
            return None

    def health(self) -> AdapterStatus:
        """Check Europe PMC adapter health."""
        try:
            self._rate_limit()
            resp = requests.get(
                _SEARCH_URL,
                params={"query": "test", "format": "json", "pageSize": "1"},
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
