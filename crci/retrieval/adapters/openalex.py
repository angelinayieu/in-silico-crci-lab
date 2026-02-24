# VERIFIED: adapter matches AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 4
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: backward wiring — receives query strings from search_coordinator
# VERIFIED: forward wiring — returns CandidateMetadata for APS scoring
# VERIFIED: rate limit from config.OPENALEX_RPS
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.OpenAlex
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 4 (OpenAlex)
Purpose: OpenAlex adapter for citation graph and related works discovery.
         /works?search=... for discovery, related_works expansion.
         Polite pool with email.
Reads: Query strings from search_coordinator
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

_BASE_URL = "https://api.openalex.org/works"
_TIMEOUT_SECONDS = 30
_DEFAULT_PER_PAGE = 100


class OpenAlexAdapter(SourceAdapter):
    """OpenAlex adapter for citation graph and related works.

    Uses the polite pool by including an email parameter.
    Email is read from OPENALEX_EMAIL environment variable.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="openalex",
            requests_per_second=config.OPENALEX_RPS,
        )
        self._email = os.environ.get("OPENALEX_EMAIL", "")
        logger.info(
            "OpenAlex adapter initialized (%d req/s, polite=%s)",
            config.OPENALEX_RPS,
            bool(self._email),
        )

    def _common_params(self) -> dict[str, str]:
        """Build common request parameters."""
        params: dict[str, str] = {}
        if self._email:
            params["mailto"] = self._email
        return params

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = _DEFAULT_PER_PAGE,
    ) -> list[CandidateMetadata]:
        """Search OpenAlex for papers.

        Args:
            query: Search query string.
            filters: Optional OpenAlex filters (e.g., {"publication_year": ">2020"}).
            max_results: Maximum number of results.

        Returns:
            List of CandidateMetadata.
        """
        results: list[CandidateMetadata] = []
        page = 1
        per_page = min(max_results, _DEFAULT_PER_PAGE)

        while len(results) < max_results:
            self._rate_limit()
            params = self._common_params()
            params["search"] = query
            params["per_page"] = str(per_page)
            params["page"] = str(page)

            if filters:
                filter_parts = []
                for key, value in filters.items():
                    filter_parts.append(f"{key}:{value}")
                params["filter"] = ",".join(filter_parts)

            try:
                resp = requests.get(
                    _BASE_URL, params=params, timeout=_TIMEOUT_SECONDS
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning("OpenAlex search failed: %s", exc)
                break
            except ValueError as exc:
                self._last_error = str(exc)
                logger.warning("OpenAlex JSON parse error: %s", exc)
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
            page += 1

        logger.info(
            "OpenAlex search returned %d results for: %s",
            len(results),
            query[:100],
        )
        return results[:max_results]

    def _parse_work(self, work: dict) -> CandidateMetadata | None:
        """Parse a single OpenAlex work object."""
        # DOI
        doi = work.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]

        title = work.get("title")
        if not title and not doi:
            return None

        # Authors
        authors: list[str] = []
        for authorship in work.get("authorships", []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name")
            if name:
                authors.append(name)

        # Journal / source
        primary_location = work.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        journal = source.get("display_name")

        # Year
        year = work.get("publication_year")

        # Abstract (OpenAlex uses inverted index)
        abstract = None
        abstract_index = work.get("abstract_inverted_index")
        if abstract_index:
            abstract = self._reconstruct_abstract(abstract_index)

        # IDs
        pmid = None
        pmcid = None
        ids = work.get("ids", {})
        pmid_url = ids.get("pmid")
        if pmid_url and "pubmed.ncbi" in pmid_url:
            pmid = pmid_url.rsplit("/", 1)[-1]
        pmcid_val = ids.get("pmcid")
        if pmcid_val:
            pmcid = pmcid_val.replace("https://www.ncbi.nlm.nih.gov/pmc/articles/", "")

        # Citation count
        cited_by_count = work.get("cited_by_count")

        # OA status
        oa_info = work.get("open_access", {})
        is_oa = oa_info.get("is_oa", False)
        oa_status_str = oa_info.get("oa_status", "unknown")
        oa_mapping = {
            "gold": OAStatus.GOLD,
            "green": OAStatus.GREEN,
            "hybrid": OAStatus.HYBRID,
            "bronze": OAStatus.BRONZE,
            "closed": OAStatus.CLOSED,
        }
        oa_status = oa_mapping.get(oa_status_str, OAStatus.UNKNOWN)

        # Publication type
        pub_type = work.get("type", "")
        pub_types = [pub_type] if pub_type else []

        # Concepts as pseudo-MeSH
        mesh_terms: list[str] = []
        for concept in work.get("concepts", []):
            if concept.get("score", 0) > 0.3:
                name = concept.get("display_name")
                if name:
                    mesh_terms.append(name)

        return CandidateMetadata(
            source="openalex",
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

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single paper by DOI.

        Args:
            identifier: DOI or OpenAlex ID.

        Returns:
            PaperMetadata if found, None otherwise.
        """
        self._rate_limit()
        if identifier.startswith("10."):
            url = f"{_BASE_URL}/https://doi.org/{identifier}"
        elif identifier.startswith("W"):
            url = f"{_BASE_URL}/{identifier}"
        else:
            url = f"{_BASE_URL}/{identifier}"

        params = self._common_params()

        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT_SECONDS)
            resp.raise_for_status()
            work = resp.json()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning("OpenAlex lookup failed for %s: %s", identifier, exc)
            return None

        candidate = self._parse_work(work)
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
            mesh_terms=candidate.mesh_terms,
            publication_types=candidate.publication_types,
            is_oa=candidate.is_oa,
            oa_status=candidate.oa_status,
            cited_by_count=candidate.cited_by_count,
            sources_checked=["openalex"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """OpenAlex does not provide full text directly."""
        return FullTextAvailability(available=False, source="openalex")

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """OpenAlex does not provide full text directly."""
        return None

    def health(self) -> AdapterStatus:
        """Check OpenAlex adapter health."""
        try:
            self._rate_limit()
            params = self._common_params()
            params["search"] = "test"
            params["per_page"] = "1"
            resp = requests.get(
                _BASE_URL, params=params, timeout=_TIMEOUT_SECONDS
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
