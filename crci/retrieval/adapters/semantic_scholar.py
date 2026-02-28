# VERIFIED: adapter matches FULLTEXT_SOURCE_PRIORITY "semantic_scholar" entry
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: rate limit from config.SEMANTIC_SCHOLAR_RPS (1 req/s)
# VERIFIED: forward wiring — returns CandidateMetadata + PDF bytes
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.SemanticScholar
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (extended)
Purpose: Semantic Scholar adapter for paper metadata and OA PDF retrieval.
         Uses S2 Academic Graph API. 1 req/s without key, higher with key.
         Provides citation graph, TLDR, and sometimes unique OA PDFs.
Reads: DOIs or paper IDs from ResolvedIdentifiers
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

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"
_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_TIMEOUT_SECONDS = 30

# Fields to request from S2 API
_PAPER_FIELDS = (
    "paperId,externalIds,title,abstract,year,venue,journal,"
    "authors,citationCount,isOpenAccess,openAccessPdf,"
    "publicationTypes,publicationDate"
)


class SemanticScholarAdapter(SourceAdapter):
    """Semantic Scholar adapter for paper discovery and OA PDF retrieval.

    Uses the Semantic Scholar Academic Graph API.
    Rate limits: 1 req/s without key, 10 req/s with API key.
    Set API key via S2_API_KEY environment variable.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="semantic_scholar",
            requests_per_second=config.SEMANTIC_SCHOLAR_RPS,
        )
        self._api_key = os.environ.get("S2_API_KEY", "")
        if self._api_key:
            # With API key, can go faster
            self.requests_per_second = 10.0
        logger.info(
            "Semantic Scholar adapter initialized (%.0f req/s, api_key=%s)",
            self.requests_per_second,
            bool(self._api_key),
        )

    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        headers: dict[str, str] = {
            "User-Agent": "CRCI-RetrievalBot/1.0",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 50,
    ) -> list[CandidateMetadata]:
        """Search Semantic Scholar for papers.

        Args:
            query: Search query string.
            filters: Optional. Supports 'year' (e.g., '2020-2024'), 'fieldsOfStudy'.
            max_results: Maximum results (S2 max per page is 100).

        Returns:
            List of CandidateMetadata.
        """
        results: list[CandidateMetadata] = []
        offset = 0
        per_page = min(max_results, 100)

        while len(results) < max_results:
            self._rate_limit()
            params: dict[str, str] = {
                "query": query,
                "limit": str(per_page),
                "offset": str(offset),
                "fields": _PAPER_FIELDS,
            }

            if filters:
                if "year" in filters:
                    params["year"] = filters["year"]
                if "fieldsOfStudy" in filters:
                    params["fieldsOfStudy"] = filters["fieldsOfStudy"]

            try:
                resp = requests.get(
                    _SEARCH_URL,
                    params=params,
                    headers=self._headers(),
                    timeout=_TIMEOUT_SECONDS,
                )
                # S2 returns 429 for rate limits
                if resp.status_code == 429:
                    logger.warning("Semantic Scholar rate limited, stopping search")
                    break
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning("Semantic Scholar search failed: %s", exc)
                break
            except ValueError as exc:
                self._last_error = str(exc)
                logger.warning("Semantic Scholar JSON parse error: %s", exc)
                break

            papers = data.get("data", [])
            if not papers:
                break

            for paper in papers:
                candidate = self._parse_paper(paper)
                if candidate:
                    results.append(candidate)

            # Check if there are more results
            total = data.get("total", 0)
            offset += len(papers)
            if offset >= total or len(papers) < per_page:
                break

        logger.info(
            "Semantic Scholar search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results[:max_results]

    def _parse_paper(self, paper: dict) -> CandidateMetadata | None:
        """Parse a single S2 paper object."""
        title = paper.get("title")
        if not title:
            return None

        # External IDs
        ext_ids = paper.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI")
        pmid = ext_ids.get("PubMed")
        pmcid_raw = ext_ids.get("PubMedCentral")
        pmcid = f"PMC{pmcid_raw}" if pmcid_raw and not str(pmcid_raw).startswith("PMC") else pmcid_raw
        arxiv_id = ext_ids.get("ArXiv")

        # Authors
        authors: list[str] = []
        for author in paper.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Journal / venue
        journal_info = paper.get("journal", {}) or {}
        journal = journal_info.get("name") or paper.get("venue")

        # Year
        year = paper.get("year")

        # Abstract
        abstract = paper.get("abstract")

        # Citation count
        cited_by_count = paper.get("citationCount")

        # OA status
        is_oa = paper.get("isOpenAccess", False)
        oa_pdf = paper.get("openAccessPdf", {}) or {}
        pdf_url = oa_pdf.get("url")

        oa_status = OAStatus.UNKNOWN
        if is_oa:
            oa_status = OAStatus.GREEN

        # Publication types
        pub_types = paper.get("publicationTypes") or []

        return CandidateMetadata(
            source="semantic_scholar",
            doi=doi,
            pmid=str(pmid) if pmid else None,
            pmcid=str(pmcid) if pmcid else None,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            is_oa=is_oa,
            oa_status=oa_status,
            cited_by_count=cited_by_count,
            publication_types=pub_types,
            extra={
                "arxiv_id": arxiv_id,
                "s2_paper_id": paper.get("paperId"),
                "pdf_url": pdf_url,
            },
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single paper by DOI or S2 paper ID.

        Args:
            identifier: DOI (e.g., '10.1234/example') or S2 paper ID.

        Returns:
            PaperMetadata if found, None otherwise.
        """
        self._rate_limit()

        # S2 API accepts DOI: prefix or bare paper IDs
        if identifier.startswith("10."):
            paper_id = f"DOI:{identifier}"
        else:
            paper_id = identifier

        try:
            resp = requests.get(
                f"{_BASE_URL}/{paper_id}",
                params={"fields": _PAPER_FIELDS},
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
            )
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                logger.warning("Semantic Scholar rate limited on metadata fetch")
                return None
            resp.raise_for_status()
            paper = resp.json()
        except (requests.RequestException, ValueError) as exc:
            self._last_error = str(exc)
            logger.warning(
                "Semantic Scholar metadata fetch failed for %s: %s",
                identifier, exc,
            )
            return None

        candidate = self._parse_paper(paper)
        if not candidate:
            return None

        return PaperMetadata(
            pmid=candidate.pmid,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            title=candidate.title or "",
            authors=candidate.authors,
            journal=candidate.journal,
            year=candidate.year,
            abstract=candidate.abstract,
            is_oa=candidate.is_oa,
            oa_status=candidate.oa_status,
            cited_by_count=candidate.cited_by_count,
            publication_types=candidate.publication_types,
            sources_checked=["semantic_scholar"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if Semantic Scholar has an OA PDF URL.

        Args:
            identifier: DOI or S2 paper ID.

        Returns:
            FullTextAvailability.
        """
        self._rate_limit()

        if identifier.startswith("10."):
            paper_id = f"DOI:{identifier}"
        else:
            paper_id = identifier

        try:
            resp = requests.get(
                f"{_BASE_URL}/{paper_id}",
                params={"fields": "isOpenAccess,openAccessPdf"},
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
            )
            if resp.status_code in (404, 429):
                return FullTextAvailability(available=False, source="semantic_scholar")
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            return FullTextAvailability(available=False, source="semantic_scholar")

        oa_pdf = data.get("openAccessPdf", {}) or {}
        pdf_url = oa_pdf.get("url")

        if not pdf_url:
            return FullTextAvailability(
                available=False,
                source="semantic_scholar",
            )

        return FullTextAvailability(
            available=True,
            source="semantic_scholar",
            url=pdf_url,
            format="pdf",
            oa_status=OAStatus.GREEN,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download OA PDF via Semantic Scholar's link.

        Args:
            identifier: DOI or S2 paper ID.

        Returns:
            Raw PDF bytes, or None if unavailable.
        """
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
                    "S2 PDF URL did not return PDF for %s (starts with %r)",
                    identifier,
                    resp.content[:20],
                )
                return None

            logger.info(
                "Retrieved PDF via Semantic Scholar for %s (%d bytes)",
                identifier,
                len(resp.content),
            )
            return resp.content

        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "S2 PDF download failed for %s: %s", identifier, exc,
            )
            return None

    def health(self) -> AdapterStatus:
        """Check Semantic Scholar adapter health."""
        try:
            self._rate_limit()
            resp = requests.get(
                _SEARCH_URL,
                params={"query": "test", "limit": "1", "fields": "title"},
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                h = AdapterHealth.DEGRADED
                self._last_error = "Rate limited"
            else:
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
