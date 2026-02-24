# VERIFIED: adapter matches AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 5
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: backward wiring — receives DOIs from fulltext_retriever
# VERIFIED: forward wiring — returns FullTextAvailability + PDF bytes
# VERIFIED: rate limit from config.UNPAYWALL_RPD
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.Unpaywall
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 5 (Unpaywall)
Purpose: Unpaywall adapter for OA route resolution.
         Single DOI lookup → OA status + best OA URL for PDF download.
         Rate limit: 100,000/day with registered email.
Reads: DOIs from fulltext_retriever
Writes: FullTextAvailability + PDF bytes for pipeline
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

_BASE_URL = "https://api.unpaywall.org/v2"
_TIMEOUT_SECONDS = 30


class UnpaywallAdapter(SourceAdapter):
    """Unpaywall adapter for finding legal OA copies of papers.

    Requires an email address (registered at Unpaywall or any valid email).
    Set via UNPAYWALL_EMAIL environment variable.
    """

    def __init__(self) -> None:
        # Unpaywall is per-day, not per-second. Use config throttle for base adapter.
        super().__init__(
            adapter_name="unpaywall",
            requests_per_second=config.UNPAYWALL_RPS_THROTTLE,
        )
        self._email = os.environ.get("UNPAYWALL_EMAIL", "")
        if not self._email:
            logger.warning(
                "UNPAYWALL_EMAIL not set. Unpaywall API requires a valid email."
            )
        logger.info("Unpaywall adapter initialized (daily limit: %d)", config.UNPAYWALL_RPD)

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 100,
    ) -> list[CandidateMetadata]:
        """Unpaywall does not support keyword search. Returns empty list.

        Use PubMed/Crossref/OpenAlex for search, then Unpaywall for OA lookup.
        """
        logger.debug("Unpaywall does not support search queries, skipping.")
        return []

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch OA metadata for a single DOI.

        Args:
            identifier: DOI string.

        Returns:
            PaperMetadata with OA details, or None.
        """
        if not identifier.startswith("10."):
            logger.warning("Unpaywall requires a DOI, got: %s", identifier)
            return None

        data = self._lookup_doi(identifier)
        if not data:
            return None

        title = data.get("title", "")
        year = data.get("year")
        journal = data.get("journal_name")
        is_oa = data.get("is_oa", False)

        oa_status_str = data.get("oa_status", "unknown")
        oa_mapping = {
            "gold": OAStatus.GOLD,
            "green": OAStatus.GREEN,
            "hybrid": OAStatus.HYBRID,
            "bronze": OAStatus.BRONZE,
            "closed": OAStatus.CLOSED,
        }
        oa_status = oa_mapping.get(oa_status_str, OAStatus.UNKNOWN)

        # Authors
        authors: list[str] = []
        for author in data.get("z_authors", []) or []:
            family = author.get("family", "")
            given = author.get("given", "")
            if family:
                authors.append(f"{family} {given}".strip())

        return PaperMetadata(
            doi=identifier,
            title=title or "",
            authors=authors,
            journal=journal,
            year=year,
            is_oa=is_oa,
            oa_status=oa_status,
            sources_checked=["unpaywall"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if a legal OA copy is available.

        Args:
            identifier: DOI string.

        Returns:
            FullTextAvailability with best OA location.
        """
        if not identifier.startswith("10."):
            return FullTextAvailability(available=False, source="unpaywall")

        data = self._lookup_doi(identifier)
        if not data:
            return FullTextAvailability(available=False, source="unpaywall")

        best_location = data.get("best_oa_location")
        if not best_location:
            return FullTextAvailability(
                available=False,
                source="unpaywall",
                oa_status=OAStatus.CLOSED,
            )

        url_for_pdf = best_location.get("url_for_pdf")
        url = best_location.get("url")
        lic = best_location.get("license")

        oa_status_str = data.get("oa_status", "unknown")
        oa_mapping = {
            "gold": OAStatus.GOLD,
            "green": OAStatus.GREEN,
            "hybrid": OAStatus.HYBRID,
            "bronze": OAStatus.BRONZE,
        }
        oa_status = oa_mapping.get(oa_status_str, OAStatus.UNKNOWN)

        return FullTextAvailability(
            available=bool(url_for_pdf or url),
            source="unpaywall",
            url=url_for_pdf or url,
            format="pdf" if url_for_pdf else "html",
            oa_status=oa_status,
            license=lic,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download PDF from best OA location.

        Args:
            identifier: DOI string.

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
                timeout=60,  # PDFs can be large
                headers={"User-Agent": "CRCI-RetrievalBot/1.0"},
                allow_redirects=True,
            )
            resp.raise_for_status()

            # Verify we got a PDF (or at least some content)
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and len(resp.content) < 1000:
                logger.warning(
                    "Unpaywall URL did not return PDF for %s (Content-Type: %s)",
                    identifier,
                    content_type,
                )
                return None

            logger.info(
                "Retrieved full text via Unpaywall for %s (%d bytes)",
                identifier,
                len(resp.content),
            )
            return resp.content

        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "Unpaywall PDF download failed for %s: %s", identifier, exc
            )
            return None

    def _lookup_doi(self, doi: str) -> dict | None:
        """Look up a DOI in Unpaywall API."""
        if not self._email:
            logger.warning("Cannot query Unpaywall without email address")
            return None

        self._rate_limit()
        url = f"{_BASE_URL}/{doi}"
        params = {"email": self._email}

        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT_SECONDS)
            if resp.status_code == 404:
                logger.debug("DOI not found in Unpaywall: %s", doi)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning("Unpaywall lookup failed for %s: %s", doi, exc)
            return None
        except ValueError as exc:
            self._last_error = str(exc)
            logger.warning("Unpaywall JSON parse error for %s: %s", doi, exc)
            return None

    def health(self) -> AdapterStatus:
        """Check Unpaywall adapter health."""
        h = AdapterHealth.HEALTHY
        if not self._email:
            h = AdapterHealth.DEGRADED
            self._last_error = "UNPAYWALL_EMAIL not configured"

        return AdapterStatus(
            adapter_name=self.adapter_name,
            health=h,
            requests_today=self._request_count,
            requests_limit=config.UNPAYWALL_RPD,
            last_error=self._last_error,
        )
