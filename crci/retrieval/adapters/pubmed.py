# VERIFIED: adapter matches AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 1
# VERIFIED: imports — requests, xml.etree, base.SourceAdapter
# VERIFIED: backward wiring — receives query strings from search_coordinator
# VERIFIED: forward wiring — returns CandidateMetadata for APS scoring
# VERIFIED: rate limit from config.PUBMED_RPS
"""
Component: SYS_EXTRACTION.EX-ACQ.Adapters.PubMed
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 4, Adapter 1 (NCBI E-utilities)
Purpose: PubMed adapter using NCBI E-utilities API.
         Endpoints: esearch.fcgi (search), efetch.fcgi (fetch metadata).
         Rate limit: 3 req/s without API key, 10 req/s with key.
Reads: Query strings from search_coordinator
Writes: CandidateMetadata[] for APS scoring
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from typing import Any

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

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ESEARCH_URL = f"{_EUTILS_BASE}/esearch.fcgi"
_EFETCH_URL = f"{_EUTILS_BASE}/efetch.fcgi"
_DEFAULT_RETMAX = 100
_TIMEOUT_SECONDS = 30


class PubMedAdapter(SourceAdapter):
    """PubMed adapter using NCBI E-utilities (esearch, efetch).

    API key is read from environment variable NCBI_API_KEY.
    Rate limit adjusts based on whether an API key is available.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("NCBI_API_KEY")
        rps = 10 if self._api_key else config.PUBMED_RPS
        super().__init__(adapter_name="pubmed", requests_per_second=rps)
        if self._api_key:
            logger.info("PubMed adapter initialized with API key (10 req/s)")
        else:
            logger.info(
                "PubMed adapter initialized without API key (%d req/s)",
                config.PUBMED_RPS,
            )

    def _build_params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Build common E-utilities parameters."""
        params: dict[str, str] = {"retmode": "xml"}
        if self._api_key:
            params["api_key"] = self._api_key
        if extra:
            params.update(extra)
        return params

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        max_results: int = _DEFAULT_RETMAX,
    ) -> list[CandidateMetadata]:
        """Search PubMed using esearch + efetch.

        Args:
            query: PubMed Boolean query string.
            filters: Optional filters (e.g., {"mindate": "2020", "maxdate": "2024"}).
            max_results: Maximum number of results.

        Returns:
            List of CandidateMetadata.
        """
        pmids = self._esearch(query, filters=filters, retmax=max_results)
        if not pmids:
            logger.info("PubMed search returned 0 results for: %s", query[:100])
            return []

        logger.info(
            "PubMed search returned %d PMIDs for: %s", len(pmids), query[:100]
        )
        return self._efetch_batch(pmids)

    def _esearch(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        retmax: int = _DEFAULT_RETMAX,
        retstart: int = 0,
    ) -> list[str]:
        """Run esearch and return PMID list."""
        self._rate_limit()
        params = self._build_params({
            "db": "pubmed",
            "term": query,
            "retmax": str(retmax),
            "retstart": str(retstart),
            "usehistory": "n",
        })
        if filters:
            params.update(filters)

        try:
            resp = requests.get(
                _ESEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            logger.warning("PubMed esearch failed: %s", exc)
            return []

        root = ET.fromstring(resp.text)
        id_list = root.find("IdList")
        if id_list is None:
            return []
        return [el.text for el in id_list.findall("Id") if el.text]

    def _efetch_batch(
        self,
        pmids: list[str],
        batch_size: int = 200,
    ) -> list[CandidateMetadata]:
        """Fetch metadata for a list of PMIDs using efetch."""
        results: list[CandidateMetadata] = []

        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            self._rate_limit()
            params = self._build_params({
                "db": "pubmed",
                "id": ",".join(batch),
                "rettype": "xml",
            })

            try:
                resp = requests.get(
                    _EFETCH_URL, params=params, timeout=_TIMEOUT_SECONDS
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                self._last_error = str(exc)
                logger.warning(
                    "PubMed efetch failed for batch %d-%d: %s",
                    i,
                    i + len(batch),
                    exc,
                )
                continue

            results.extend(self._parse_efetch_xml(resp.text))

        return results

    def _parse_efetch_xml(self, xml_text: str) -> list[CandidateMetadata]:
        """Parse efetch XML response into CandidateMetadata list."""
        results: list[CandidateMetadata] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("PubMed XML parse error: %s", exc)
            return results

        for article in root.findall(".//PubmedArticle"):
            try:
                candidate = self._parse_article(article)
                if candidate:
                    results.append(candidate)
            except Exception as exc:
                logger.debug("Failed to parse PubMed article: %s", exc)

        return results

    def _parse_article(self, article: ET.Element) -> CandidateMetadata | None:
        """Parse a single PubmedArticle XML element."""
        medline = article.find("MedlineCitation")
        if medline is None:
            return None

        # PMID
        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else None
        if not pmid:
            return None

        art = medline.find("Article")
        if art is None:
            return None

        # Title
        title_el = art.find("ArticleTitle")
        title = title_el.text if title_el is not None else None

        # Abstract
        abstract_parts: list[str] = []
        abstract_el = art.find("Abstract")
        if abstract_el is not None:
            for text_el in abstract_el.findall("AbstractText"):
                label = text_el.get("Label", "")
                text = "".join(text_el.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
        abstract = " ".join(abstract_parts) if abstract_parts else None

        # Authors
        authors: list[str] = []
        author_list = art.find("AuthorList")
        if author_list is not None:
            for author_el in author_list.findall("Author"):
                last = author_el.find("LastName")
                first = author_el.find("ForeName")
                if last is not None and last.text:
                    name = last.text
                    if first is not None and first.text:
                        name += f" {first.text}"
                    authors.append(name)

        # Journal
        journal_el = art.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else None

        # Year
        year = None
        pub_date = art.find(".//Journal/JournalIssue/PubDate/Year")
        if pub_date is not None and pub_date.text:
            try:
                year = int(pub_date.text)
            except ValueError:
                pass

        # DOI
        doi = None
        article_ids = article.find("PubmedData/ArticleIdList")
        if article_ids is not None:
            for aid in article_ids.findall("ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text
                elif aid.get("IdType") == "pmc" and aid.text:
                    pass  # pmcid captured below

        # PMC ID
        pmcid = None
        if article_ids is not None:
            for aid in article_ids.findall("ArticleId"):
                if aid.get("IdType") == "pmc" and aid.text:
                    pmcid = aid.text

        # MeSH terms
        mesh_terms: list[str] = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for heading in mesh_list.findall("MeshHeading"):
                desc = heading.find("DescriptorName")
                if desc is not None and desc.text:
                    mesh_terms.append(desc.text)

        # Publication types
        pub_types: list[str] = []
        pub_type_list = art.find("PublicationTypeList")
        if pub_type_list is not None:
            for pt in pub_type_list.findall("PublicationType"):
                if pt.text:
                    pub_types.append(pt.text)

        is_oa = pmcid is not None

        return CandidateMetadata(
            source="pubmed",
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
            oa_status=OAStatus.GREEN if is_oa else OAStatus.UNKNOWN,
        )

    def fetch_metadata(self, identifier: str) -> PaperMetadata | None:
        """Fetch metadata for a single PMID.

        Args:
            identifier: A PubMed ID (PMID).

        Returns:
            PaperMetadata if found, None otherwise.
        """
        candidates = self._efetch_batch([identifier])
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
            sources_checked=["pubmed"],
        )

    def check_fulltext(self, identifier: str) -> FullTextAvailability:
        """PubMed does not provide full text. Always returns unavailable.

        Args:
            identifier: PMID.

        Returns:
            FullTextAvailability with available=False.
        """
        return FullTextAvailability(
            available=False,
            source="pubmed",
        )

    def retrieve_fulltext(self, identifier: str) -> bytes | None:
        """PubMed does not provide full text. Always returns None."""
        return None

    def health(self) -> AdapterStatus:
        """Check PubMed adapter health."""
        try:
            self._rate_limit()
            params = self._build_params({
                "db": "pubmed",
                "term": "test",
                "retmax": "1",
            })
            resp = requests.get(
                _ESEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS
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
            requests_limit=None,
            last_error=self._last_error,
        )
