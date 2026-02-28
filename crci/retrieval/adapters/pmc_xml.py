# VERIFIED: adapter matches FULLTEXT_SOURCE_PRIORITY "pmc_xml" entry
# VERIFIED: imports — requests, base.SourceAdapter
# VERIFIED: rate limit from config.PMC_EFETCH_RPS (3/sec without key)
# VERIFIED: forward wiring — returns JATS XML bytes for xml_ingestion.py
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.PmcXml
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4 (extended)
Purpose: PMC E-fetch adapter for retrieving JATS XML from NCBI PMC.
         Uses NCBI E-utilities efetch endpoint to download structured
         JATS/NLM XML. Requires PMCID. Rate: 3/sec (10 with API key).
Reads: PMCIDs from ResolvedIdentifiers
Writes: JATS XML bytes for pipeline (consumed by xml_ingestion.py)
"""
from __future__ import annotations

import logging
import os
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

_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_TIMEOUT_SECONDS = 30


class PmcXmlAdapter(SourceAdapter):
    """PMC JATS XML adapter via NCBI E-utilities efetch.

    Downloads structured JATS XML from PMC, which contains full text
    with proper section markup (abstract, methods, results, references).
    JATS XML is preferable to PDF for extraction accuracy.

    Requires PMCID as input. Use id_resolver.resolve_doi() to get PMCID first.
    """

    def __init__(self) -> None:
        super().__init__(
            adapter_name="pmc_xml",
            requests_per_second=config.PMC_EFETCH_RPS,
        )
        self._api_key = os.environ.get("NCBI_API_KEY", "")
        effective_rps = 10 if self._api_key else config.PMC_EFETCH_RPS
        logger.info(
            "PMC XML adapter initialized (%.0f req/s, api_key=%s)",
            effective_rps,
            bool(self._api_key),
        )

    def _common_params(self) -> dict[str, str]:
        """Build common NCBI request parameters."""
        params: dict[str, str] = {
            "tool": "crci-system",
            "email": "crci@research.example.com",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = 100,
    ) -> list[CandidateMetadata]:
        """Search PMC via NCBI esearch. Limited — prefer Europe PMC for search.

        Args:
            query: PubMed-style query for PMC database.
            filters: Not used.
            max_results: Maximum results.

        Returns:
            List of CandidateMetadata with PMCIDs.
        """
        self._rate_limit()
        params = self._common_params()
        params.update({
            "db": "pmc",
            "term": query,
            "retmax": str(min(max_results, 500)),
            "retmode": "json",
        })

        try:
            resp = requests.get(
                _ESEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            self._last_error = str(exc)
            logger.warning("PMC esearch failed: %s", exc)
            return []

        id_list = data.get("esearchresult", {}).get("idlist", [])
        results: list[CandidateMetadata] = []
        for pmc_id_num in id_list:
            results.append(CandidateMetadata(
                source="pmc_xml",
                pmcid=f"PMC{pmc_id_num}" if not pmc_id_num.startswith("PMC") else pmc_id_num,
                is_oa=True,
                oa_status=OAStatus.GOLD,
            ))

        logger.info("PMC esearch returned %d IDs for: %s", len(results), query[:100])
        return results

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata by downloading and parsing JATS XML headers.

        Args:
            identifier: PMCID (e.g., 'PMC1234567').

        Returns:
            PaperMetadata extracted from JATS front-matter, or None.
        """
        xml_bytes = self.retrieve_fulltext(identifier)
        if not xml_bytes:
            return None

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            logger.warning("Failed to parse JATS XML for %s: %s", identifier, exc)
            return None

        # JATS front-matter
        front = root.find(".//front")
        if front is None:
            return PaperMetadata(
                pmcid=identifier,
                title="",
                sources_checked=["pmc_xml"],
            )

        # Title
        title_elem = front.find(".//article-title")
        title = self._element_text(title_elem) if title_elem is not None else ""

        # Authors
        authors: list[str] = []
        for contrib in front.findall(".//contrib[@contrib-type='author']"):
            surname = contrib.findtext("name/surname", "")
            given = contrib.findtext("name/given-names", "")
            if surname:
                authors.append(f"{surname} {given}".strip())

        # Journal
        journal_elem = front.find(".//journal-title")
        journal = self._element_text(journal_elem) if journal_elem is not None else None

        # Year
        year: int | None = None
        year_elem = front.find(".//pub-date/year")
        if year_elem is not None and year_elem.text:
            try:
                year = int(year_elem.text)
            except ValueError:
                pass

        # Abstract
        abstract_elem = front.find(".//abstract")
        abstract = self._element_text(abstract_elem) if abstract_elem is not None else None

        # DOI
        doi: str | None = None
        for article_id in front.findall(".//article-id"):
            if article_id.get("pub-id-type") == "doi" and article_id.text:
                doi = article_id.text.strip()

        # PMID
        pmid: str | None = None
        for article_id in front.findall(".//article-id"):
            if article_id.get("pub-id-type") == "pmid" and article_id.text:
                pmid = article_id.text.strip()

        return PaperMetadata(
            pmid=pmid,
            pmcid=identifier,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            is_oa=True,
            oa_status=OAStatus.GOLD,
            sources_checked=["pmc_xml"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """Check if JATS XML is available in PMC.

        Args:
            identifier: PMCID (e.g., 'PMC1234567').

        Returns:
            FullTextAvailability.
        """
        if not identifier or not identifier.upper().startswith("PMC"):
            return FullTextAvailability(available=False, source="pmc_xml")

        # Quick HEAD request to check availability
        pmc_num = identifier.upper().replace("PMC", "")
        self._rate_limit()
        params = self._common_params()
        params.update({
            "db": "pmc",
            "id": pmc_num,
            "rettype": "xml",
        })

        try:
            resp = requests.head(
                _EFETCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
            )
            available = resp.status_code == 200
        except requests.RequestException:
            available = False

        return FullTextAvailability(
            available=available,
            source="pmc_xml",
            format="xml",
            oa_status=OAStatus.GOLD if available else OAStatus.UNKNOWN,
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """Download JATS XML from NCBI efetch.

        Args:
            identifier: PMCID (e.g., 'PMC1234567').

        Returns:
            Raw JATS XML bytes, or None if unavailable.
        """
        if not identifier or not identifier.upper().startswith("PMC"):
            logger.warning("PMC XML adapter requires PMCID, got: %s", identifier)
            return None

        pmc_num = identifier.upper().replace("PMC", "")

        self._rate_limit()
        params = self._common_params()
        params.update({
            "db": "pmc",
            "id": pmc_num,
            "rettype": "xml",
        })

        try:
            resp = requests.get(
                _EFETCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()

            # Verify we got XML, not an error page
            content = resp.content
            if not content or b"<" not in content[:100]:
                logger.warning(
                    "PMC efetch returned non-XML for %s (%d bytes, starts: %r)",
                    identifier,
                    len(content),
                    content[:40],
                )
                return None

            # Check for PMC error responses
            if b"<ERROR>" in content[:500] or b"<error>" in content[:500]:
                logger.warning(
                    "PMC efetch returned error for %s: %s",
                    identifier,
                    content[:200].decode("utf-8", errors="replace"),
                )
                return None

            logger.info(
                "Retrieved JATS XML from PMC for %s (%d bytes)",
                identifier,
                len(content),
            )
            return content

        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning(
                "PMC efetch failed for %s: %s", identifier, exc,
            )
            return None

    @staticmethod
    def _element_text(elem: ET.Element) -> str:
        """Extract all text content from an XML element, including children."""
        parts: list[str] = []
        for text in elem.itertext():
            parts.append(text.strip())
        return " ".join(p for p in parts if p)

    def health(self) -> AdapterStatus:
        """Check PMC XML adapter health."""
        try:
            self._rate_limit()
            params = self._common_params()
            params.update({
                "db": "pmc",
                "term": "test",
                "retmax": "1",
                "retmode": "json",
            })
            resp = requests.get(
                _ESEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS,
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
            avg_latency_ms=None,
        )
