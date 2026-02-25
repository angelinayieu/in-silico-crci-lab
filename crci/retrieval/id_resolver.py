# VERIFIED: formulas — none (lookup / resolution logic)
# VERIFIED: imports — shared/config, retrieval/adapters
# VERIFIED: backward wiring — reads CandidateMetadata from search_coordinator
# VERIFIED: forward wiring — enriched CandidateMetadata for dedup accuracy
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-ACQ.IDResolver
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 5 (Deduplication)
      Master Spec §9.3 (Identifier Cross-Resolution)
Purpose: Cross-resolve DOI ↔ PMID ↔ PMCID to improve dedup accuracy.
         A paper found via Crossref (DOI only) may be the same as one
         found via PubMed (PMID only). This module resolves the mapping.
Reads: CandidateMetadata (from search_coordinator.py)
Writes: Enriched CandidateMetadata (consumed by search_coordinator dedup)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from crci.shared import config
from crci.retrieval.models import CandidateMetadata

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  ID RESOLUTION VIA NCBI ID CONVERTER API
# ═══════════════════════════════════════════════════════════════


def _fetch_ncbi_id_mapping(
    identifiers: list[str],
    id_type: str,
) -> dict[str, dict[str, str]]:
    """Query NCBI ID Converter API to map between DOI/PMID/PMCID.

    Uses the NCBI ID Converter (https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/)
    which maps between PMID, PMCID, and DOI.

    Args:
        identifiers: List of identifiers to resolve.
        id_type: Type of identifiers provided ('doi', 'pmid', 'pmcid').

    Returns:
        Dict mapping input identifier to resolved IDs:
        {"10.1234/example": {"pmid": "12345", "pmcid": "PMC67890", "doi": "10.1234/example"}}
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — ID resolution unavailable")
        return {}

    if not identifiers:
        return {}

    # NCBI ID Converter accepts up to 200 IDs per request
    batch_size = 200
    results: dict[str, dict[str, str]] = {}

    for i in range(0, len(identifiers), batch_size):
        batch = identifiers[i:i + batch_size]
        ids_param = ",".join(batch)

        try:
            resp = requests.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                params={
                    "ids": ids_param,
                    "format": "json",
                    "tool": "crci-system",
                    "email": "crci@research.example.com",
                },
                timeout=config.ID_RESOLVER_PUBMED_TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(
                "NCBI ID Converter failed for batch %d-%d: %s",
                i, i + len(batch), exc,
            )
            continue

        for record in data.get("records", []):
            key = record.get(id_type, record.get("doi", ""))
            if not key:
                # Use first available ID as key
                key = record.get("pmid", record.get("pmcid", ""))
            if key:
                results[key] = {
                    "doi": record.get("doi", ""),
                    "pmid": record.get("pmid", ""),
                    "pmcid": record.get("pmcid", ""),
                }

    logger.info(
        "NCBI ID resolution: resolved %d/%d identifiers",
        len(results), len(identifiers),
    )
    return results


def _normalize_doi(doi: str) -> str:
    """Normalize DOI to lowercase, stripped of URL prefix."""
    doi = doi.strip().lower()
    # Remove common URL prefixes
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def _normalize_pmid(pmid: str) -> str:
    """Normalize PMID — extract numeric portion only."""
    match = re.search(r'\d+', pmid)
    return match.group(0) if match else pmid.strip()


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════


def resolve_candidate_ids(
    candidates: list[CandidateMetadata],
) -> list[CandidateMetadata]:
    """Cross-resolve DOI/PMID/PMCID for a batch of candidates.

    For candidates with only DOI, resolves PMID+PMCID.
    For candidates with only PMID, resolves DOI+PMCID.
    This dramatically improves dedup accuracy in search_coordinator.

    Args:
        candidates: List of CandidateMetadata (may have partial IDs).

    Returns:
        List of CandidateMetadata with enriched identifier fields.
    """
    # Partition candidates by what they're missing
    doi_only: list[tuple[int, str]] = []
    pmid_only: list[tuple[int, str]] = []

    for idx, cand in enumerate(candidates):
        has_doi = bool(cand.doi)
        has_pmid = bool(cand.pmid)
        has_pmcid = bool(cand.pmcid)

        if has_doi and not has_pmid:
            doi_only.append((idx, _normalize_doi(cand.doi)))
        elif has_pmid and not has_doi:
            pmid_only.append((idx, _normalize_pmid(cand.pmid)))

    if not doi_only and not pmid_only:
        logger.debug("All candidates already have both DOI and PMID — no resolution needed")
        return candidates

    # Resolve DOI → PMID/PMCID
    doi_map: dict[str, dict[str, str]] = {}
    if doi_only:
        dois = [d for _, d in doi_only]
        doi_map = _fetch_ncbi_id_mapping(dois, "doi")

    # Resolve PMID → DOI/PMCID
    pmid_map: dict[str, dict[str, str]] = {}
    if pmid_only:
        pmids = [p for _, p in pmid_only]
        pmid_map = _fetch_ncbi_id_mapping(pmids, "pmid")

    # Enrich candidates
    enriched = list(candidates)  # shallow copy
    resolved_count = 0

    for idx, doi in doi_only:
        resolved = doi_map.get(doi, {})
        if resolved.get("pmid") or resolved.get("pmcid"):
            cand = enriched[idx]
            enriched[idx] = cand.model_copy(update={
                "pmid": resolved.get("pmid") or cand.pmid,
                "pmcid": resolved.get("pmcid") or cand.pmcid,
            })
            resolved_count += 1

    for idx, pmid in pmid_only:
        resolved = pmid_map.get(pmid, {})
        if resolved.get("doi") or resolved.get("pmcid"):
            cand = enriched[idx]
            enriched[idx] = cand.model_copy(update={
                "doi": resolved.get("doi") or cand.doi,
                "pmcid": resolved.get("pmcid") or cand.pmcid,
            })
            resolved_count += 1

    logger.info(
        "ID resolution: enriched %d candidates (%d DOI→PMID, %d PMID→DOI)",
        resolved_count,
        len(doi_only),
        len(pmid_only),
    )

    return enriched


def build_dedup_key(candidate: CandidateMetadata) -> str:
    """Build a canonical dedup key for a candidate.

    Resolution priority: DOI (most unique) > PMID > title-based hash.
    After ID resolution, candidates that are the same paper will
    produce the same dedup key regardless of which adapter found them.

    Args:
        candidate: CandidateMetadata with (possibly enriched) IDs.

    Returns:
        A normalized dedup key string.
    """
    if candidate.doi:
        return f"doi:{_normalize_doi(candidate.doi)}"
    if candidate.pmid:
        return f"pmid:{_normalize_pmid(candidate.pmid)}"
    if candidate.pmcid:
        return f"pmcid:{candidate.pmcid.strip().upper()}"
    # Fallback: normalized title
    if candidate.title:
        title_key = re.sub(r'[^a-z0-9]', '', candidate.title.lower())
        return f"title:{title_key[:120]}"
    return f"unknown:{id(candidate)}"
