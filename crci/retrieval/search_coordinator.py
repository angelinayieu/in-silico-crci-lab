# VERIFIED: flow matches AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 2
# VERIFIED: imports — adapters, sqlalchemy, retrieval.models
# VERIFIED: backward wiring — reads APSQueryRequest from query_generator
# VERIFIED: forward wiring — writes CandidateMetadata[] for aps_scorer
# VERIFIED: dedup against study_registry_v1 (DOI + PMID match)
"""
Component: SYS_EXTRACTION.EX-ACQ.SearchCoordinator
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 2
Purpose: Orchestrates multi-source search. Dispatches queries to adapters,
         collects CandidateMetadata[], deduplicates against study_registry_v1,
         merges and normalizes candidates.
Reads: APSQueryRequest[] from query_generator
Writes: CandidateMetadata[] (deduplicated) for aps_scorer
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from crci.shared.models.tables import StudyRegistry
from crci.retrieval.models import APSQueryRequest, CandidateMetadata
from crci.retrieval.adapters.base import SourceAdapter
from crci.retrieval.adapters.pubmed import PubMedAdapter
from crci.retrieval.adapters.europe_pmc import EuropePMCAdapter
from crci.retrieval.adapters.crossref import CrossrefAdapter
from crci.retrieval.adapters.openalex import OpenAlexAdapter

logger = logging.getLogger(__name__)


class SearchCoordinator:
    """Orchestrates multi-source bibliographic search.

    For each query:
      a. Search PubMed (primary) → PMID list
      b. Search OpenAlex (expansion) → additional DOIs
      c. Fetch metadata for all candidates via Crossref
      d. Normalize to CandidateMetadata schema
      e. Dedup against study_registry_v1 (DOI + PMID match)
    """

    def __init__(
        self,
        session: Session,
        adapters: dict[str, SourceAdapter] | None = None,
    ) -> None:
        self._session = session
        if adapters is not None:
            self._adapters = adapters
        else:
            self._adapters = {
                "pubmed": PubMedAdapter(),
                "europe_pmc": EuropePMCAdapter(),
                "crossref": CrossrefAdapter(),
                "openalex": OpenAlexAdapter(),
            }
        self._known_dois: set[str] | None = None
        self._known_pmids: set[str] | None = None

    def _load_known_papers(self) -> None:
        """Load DOIs and PMIDs from study_registry_v1 for dedup."""
        if self._known_dois is not None:
            return

        rows = self._session.query(
            StudyRegistry.doi,
            StudyRegistry.pmid,
        ).all()

        self._known_dois = {
            r.doi.strip().lower()
            for r in rows
            if r.doi
        }
        self._known_pmids = {
            r.pmid.strip()
            for r in rows
            if r.pmid
        }

        logger.info(
            "Loaded %d known DOIs and %d known PMIDs for dedup",
            len(self._known_dois),
            len(self._known_pmids),
        )

    def _is_known(self, candidate: CandidateMetadata) -> bool:
        """Check if a candidate already exists in study_registry_v1."""
        self._load_known_papers()

        if candidate.doi and candidate.doi.strip().lower() in self._known_dois:
            return True
        if candidate.pmid and candidate.pmid.strip() in self._known_pmids:
            return True
        return False

    def search(
        self,
        queries: list[APSQueryRequest],
        primary_sources: list[str] | None = None,
    ) -> list[CandidateMetadata]:
        """Execute queries across source adapters and return deduplicated candidates.

        Args:
            queries: APSQueryRequest objects from query_generator.
            primary_sources: Which adapters to use. Default: ["pubmed", "openalex"].

        Returns:
            Deduplicated list of CandidateMetadata.
        """
        if primary_sources is None:
            primary_sources = ["pubmed", "openalex"]

        all_candidates: list[CandidateMetadata] = []
        seen_keys: set[str] = set()

        for query in queries:
            for source_name in primary_sources:
                adapter = self._adapters.get(source_name)
                if adapter is None:
                    continue

                try:
                    results = adapter.search(
                        query.query_string,
                        max_results=query.max_results,
                    )
                except Exception as exc:
                    logger.warning(
                        "Search failed for '%s' on %s: %s",
                        query.query_string[:80],
                        source_name,
                        exc,
                    )
                    continue

                for candidate in results:
                    # Build dedup key
                    key = self._dedup_key(candidate)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    # Check against existing papers
                    if self._is_known(candidate):
                        logger.debug(
                            "Skipping known paper: %s / %s",
                            candidate.doi,
                            candidate.pmid,
                        )
                        continue

                    all_candidates.append(candidate)

        logger.info(
            "Search complete: %d unique candidates from %d queries "
            "(after dedup against %d known papers)",
            len(all_candidates),
            len(queries),
            len(self._known_dois or set()) + len(self._known_pmids or set()),
        )
        return all_candidates

    @staticmethod
    def _dedup_key(candidate: CandidateMetadata) -> str:
        """Generate a dedup key for a candidate."""
        if candidate.doi:
            return f"doi:{candidate.doi.strip().lower()}"
        if candidate.pmid:
            return f"pmid:{candidate.pmid.strip()}"
        if candidate.title:
            # Fallback: normalized title
            return f"title:{candidate.title.strip().lower()[:100]}"
        return f"unknown:{id(candidate)}"
