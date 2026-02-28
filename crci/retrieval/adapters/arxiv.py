# VERIFIED: adapter matches FULLTEXT_SOURCE_PRIORITY "arxiv" entry
# VERIFIED: imports — requests, xml.etree, base.SourceAdapter
# VERIFIED: rate limit from config.ARXIV_DELAY_SEC (3s between requests)
# VERIFIED: forward wiring — returns CandidateMetadata + PDF bytes
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.Arxiv
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (extended)
Purpose: arXiv adapter for preprint search and PDF retrieval.
         Uses arXiv Atom API for search and export.arxiv.org for PDF.
         Always-free PDFs (no paywall). Rate limit: 3s between requests.
Reads: arXiv IDs from ResolvedIdentifiers or search queries
Writes: CandidateMetadata[] + PDF bytes for pipeline
"""
from __future__ import annotations

import logging
import re
import time
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

_SEARCH_URL = "http://export.arxiv.org/api/query"
_PDF_URL_TEMPLATE = "https://arxiv.org/pdf/{arxiv_id}.pdf"
_ABS_URL_TEMPLATE = "https://arxiv.org/abs/{arxiv_id}"
_TIMEOUT_SECONDS = 30

# arXiv Atom namespace
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivAdapter(SourceAdapter):
    """arXiv adapter for preprint search and PDF download.

    arXiv enforces a strict 3-second interval between requests.
    PDFs are always freely available.
    """

    def __init__(self) -> None:
        # arXiv uses delay-based throttling, not RPS
        super().__init__(
            adapter_name="arxiv",
            requests_per_second=1.0 / config.ARXIV_DELAY_SEC,
        )
        logger.info(
            "arXiv adapter initialized (%.1fs delay between requests)",
            config.ARXIV_DELAY_SEC,
        )

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 50,
    ) -> list[CandidateMetadata]:
        """Search arXiv using Atom API.

        Args:
            query: arXiv search query (e.g., 'all:chemobrain AND cat:q-bio').
            filters: Optional. Supports 'start' (offset) key.
            max_results: Maximum results to return (arXiv caps at 30000).

        Returns:
            List of CandidateMetadata for matching preprints.
        """
        results: list[CandidateMetadata] = []
        start = int((filters or {}).get("start", "0"))
        per_page = min(max_results, 100)  # arXiv max per page

        while len(results) < max_results:
            self._rate_limit()
            params = {
                "search_query": query,
                "start": str(start),
                "max_results": str(per_page),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            try:
                resp = requests.get(
                    _SEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning("arXiv search failed: %s", exc)
                break

            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as exc:
                self._last_error = str(exc)
                logger.warning("arXiv XML parse error: %s", exc)
                break

            entries = root.findall("atom:entry", _NS)
            if not entries:
                break

            for entry in entries:
                candidate = self._parse_entry(entry)
                if candidate:
                    results.append(candidate)

            if len(entries) < per_page:
                break
            start += len(entries)

        logger.info(
            "arXiv search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results[:max_results]

    def _parse_entry(self, entry: ET.Element) -> CandidateMetadata | None:
        """Parse a single arXiv Atom entry."""
        # arXiv ID from <id> element: "http://arxiv.org/abs/2301.12345v1"
        id_elem = entry.find("atom:id", _NS)
        if id_elem is None or id_elem.text is None:
            return None

        arxiv_url = id_elem.text.strip()
        arxiv_match = re.search(r'arxiv\.org/abs/(.+)', arxiv_url)
        if not arxiv_match:
            return None

        arxiv_id = arxiv_match.group(1)
        # Strip version suffix for canonical ID
        arxiv_id_base = re.sub(r'v\d+$', '', arxiv_id)

        title_elem = entry.find("atom:title", _NS)
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else None

        summary_elem = entry.find("atom:summary", _NS)
        abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else None

        # Authors
        authors: list[str] = []
        for author_elem in entry.findall("atom:author", _NS):
            name_elem = author_elem.find("atom:name", _NS)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())

        # Published date → year
        published_elem = entry.find("atom:published", _NS)
        year: int | None = None
        if published_elem is not None and published_elem.text:
            year_match = re.match(r'(\d{4})', published_elem.text)
            if year_match:
                year = int(year_match.group(1))

        # DOI (sometimes present in <arxiv:doi>)
        doi: str | None = None
        doi_elem = entry.find("arxiv:doi", _NS)
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()

        # Categories
        categories: list[str] = []
        for cat_elem in entry.findall("atom:category", _NS):
            term = cat_elem.get("term")
            if term:
                categories.append(term)

        # Journal ref (if published)
        journal: str | None = None
        journal_elem = entry.find("arxiv:journal_ref", _NS)
        if journal_elem is not None and journal_elem.text:
            journal = journal_elem.text.strip()

        return CandidateMetadata(
            source="arxiv",
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            is_oa=True,
            oa_status=OAStatus.GREEN,
            publication_types=["preprint"],
            mesh_terms=categories,
            extra={"arxiv_id": arxiv_id_base},
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single arXiv paper.

        Args:
            identifier: arXiv ID (e.g., '2301.12345' or '2301.12345v2').

        Returns:
            PaperMetadata if found, None otherwise.
        """
        self._rate_limit()
        params = {"id_list": identifier, "max_results": "1"}

        try:
            resp = requests.get(
                _SEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            self._last_error = str(exc)
            logger.warning("arXiv metadata fetch failed for %s: %s", identifier, exc)
            return None

        entries = root.findall("atom:entry", _NS)
        if not entries:
            return None

        candidate = self._parse_entry(entries[0])
        if not candidate:
            return None

        return PaperMetadata(
            doi=candidate.doi,
            title=candidate.title or "",
            authors=candidate.authors,
            journal=candidate.journal,
            year=candidate.year,
            abstract=candidate.abstract,
            is_oa=True,
            oa_status=OAStatus.GREEN,
            publication_types=candidate.publication_types,
            sources_checked=["arxiv"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if arXiv PDF is available. Always True for valid IDs.

        Args:
            identifier: arXiv ID.

        Returns:
            FullTextAvailability (always available for arXiv).
        """
        if not identifier:
            return FullTextAvailability(available=False, source="arxiv")

        # Strip version suffix for URL construction
        arxiv_id = re.sub(r'v\d+$', '', identifier.strip())

        return FullTextAvailability(
            available=True,
            source="arxiv",
            url=_PDF_URL_TEMPLATE.format(arxiv_id=arxiv_id),
            format="pdf",
            oa_status=OAStatus.GREEN,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download PDF from arXiv.

        Args:
            identifier: arXiv ID.

        Returns:
            Raw PDF bytes, or None if download fails.
        """
        if not identifier:
            return None

        arxiv_id = re.sub(r'v\d+$', '', identifier.strip())
        pdf_url = _PDF_URL_TEMPLATE.format(arxiv_id=arxiv_id)

        self._rate_limit()
        try:
            resp = requests.get(
                pdf_url,
                timeout=config.RETRIEVAL_PDF_DOWNLOAD_TIMEOUT_SEC,
                headers={"User-Agent": "CRCI-RetrievalBot/1.0"},
                allow_redirects=True,
            )
            resp.raise_for_status()

            # Verify PDF magic bytes
            if not resp.content[:5] == b"%PDF-":
                logger.warning(
                    "arXiv URL did not return PDF for %s (starts with %r)",
                    identifier,
                    resp.content[:20],
                )
                return None

            logger.info(
                "Retrieved PDF from arXiv for %s (%d bytes)",
                identifier,
                len(resp.content),
            )
            return resp.content

        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "arXiv PDF download failed for %s: %s", identifier, exc,
            )
            return None

    def health(self) -> AdapterStatus:
        """Check arXiv adapter health."""
        try:
            self._rate_limit()
            resp = requests.get(
                _SEARCH_URL,
                params={"search_query": "test", "max_results": "1"},
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
