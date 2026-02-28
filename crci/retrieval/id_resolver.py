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
from crci.retrieval.models import CandidateMetadata, OAStatus, ResolvedIdentifiers

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
                # Normalize key: lowercase DOIs for consistent lookup
                if id_type == "doi":
                    key = key.strip().lower()
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
#  SINGLE-DOI RESOLUTION (OpenAlex primary, NCBI fallback)
# ═══════════════════════════════════════════════════════════════


def resolve_doi(
    doi: str,
    openalex_email: str | None = None,
) -> ResolvedIdentifiers:
    """Resolve a single DOI to all known identifiers.

    Strategy:
      1. OpenAlex /works/doi:{doi} — returns PMID, PMCID, arXiv, OA info
      2. NCBI ID Converter fallback — fills PMID/PMCID gaps
    The OpenAlex call is the primary source because it returns OA status,
    best PDF URL, publisher, and arXiv ID in one request.

    Args:
        doi: Raw DOI string (may include URL prefix).
        openalex_email: Email for OpenAlex polite pool. Falls back to
            OPENALEX_EMAIL env var.

    Returns:
        ResolvedIdentifiers with all discovered cross-references.
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — DOI resolution unavailable")
        return ResolvedIdentifiers(doi=doi, resolution_source="none")

    import os

    norm_doi = _normalize_doi(doi)
    if not norm_doi:
        return ResolvedIdentifiers(doi=doi, resolution_source="none")

    email = openalex_email or os.environ.get("OPENALEX_EMAIL", "")

    # ─── Step 1: OpenAlex ────────────────────────────────────
    resolved = _resolve_via_openalex(norm_doi, email)

    # ─── Step 2: NCBI fallback for PMID/PMCID gaps ──────────
    if not resolved.pmid or not resolved.pmcid:
        ncbi_map = _fetch_ncbi_id_mapping([norm_doi], "doi")
        ncbi = ncbi_map.get(norm_doi, {})
        if ncbi:
            if not resolved.pmid and ncbi.get("pmid"):
                resolved = resolved.model_copy(update={"pmid": ncbi["pmid"]})
            if not resolved.pmcid and ncbi.get("pmcid"):
                resolved = resolved.model_copy(update={"pmcid": ncbi["pmcid"]})
            logger.info(
                "NCBI fallback enriched DOI %s: pmid=%s, pmcid=%s",
                norm_doi,
                resolved.pmid,
                resolved.pmcid,
            )

    return resolved


def _resolve_via_openalex(doi: str, email: str) -> ResolvedIdentifiers:
    """Call OpenAlex /works/doi:{doi} and parse into ResolvedIdentifiers."""
    import requests

    url = f"https://api.openalex.org/works/doi:{doi}"
    params: dict[str, str] = {}
    if email:
        params["mailto"] = email

    try:
        resp = requests.get(
            url,
            params=params,
            timeout=config.ID_RESOLVER_OPENALEX_TIMEOUT_S,
        )
        if resp.status_code == 404:
            logger.debug("DOI not found in OpenAlex: %s", doi)
            return ResolvedIdentifiers(doi=doi, resolution_source="none")
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("OpenAlex DOI lookup failed for %s: %s", doi, exc)
        return ResolvedIdentifiers(doi=doi, resolution_source="none")
    except ValueError as exc:
        logger.warning("OpenAlex JSON parse error for %s: %s", doi, exc)
        return ResolvedIdentifiers(doi=doi, resolution_source="none")

    # Parse IDs
    ids = data.get("ids", {})

    # PMID: "https://pubmed.ncbi.nlm.nih.gov/12345678"
    pmid: str | None = None
    pmid_url = ids.get("pmid")
    if pmid_url and isinstance(pmid_url, str):
        match = re.search(r'(\d+)$', pmid_url)
        if match:
            pmid = match.group(1)

    # PMCID: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567"
    pmcid: str | None = None
    pmcid_val = ids.get("pmcid")
    if pmcid_val and isinstance(pmcid_val, str):
        pmc_match = re.search(r'(PMC\d+)', pmcid_val)
        if pmc_match:
            pmcid = pmc_match.group(1)

    # OpenAlex ID: "https://openalex.org/W1234567890"
    openalex_id: str | None = data.get("id")
    if openalex_id and "/" in openalex_id:
        openalex_id = openalex_id.rsplit("/", 1)[-1]

    # arXiv ID: sometimes in alternate_host_venues or locations
    arxiv_id: str | None = None
    for location in data.get("locations", []):
        landing_url = location.get("landing_page_url") or ""
        if "arxiv.org" in landing_url:
            arxiv_match = re.search(r'arxiv\.org/abs/(\S+)', landing_url)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1).rstrip("/")
                break

    # OA status
    oa_info = data.get("open_access", {})
    oa_status_str = oa_info.get("oa_status", "unknown")
    oa_mapping = {
        "gold": OAStatus.GOLD,
        "green": OAStatus.GREEN,
        "hybrid": OAStatus.HYBRID,
        "bronze": OAStatus.BRONZE,
        "closed": OAStatus.CLOSED,
    }
    oa_status = oa_mapping.get(oa_status_str, OAStatus.UNKNOWN)

    # Best OA PDF URL
    best_oa_pdf_url: str | None = oa_info.get("oa_url")
    best_oa_source: str | None = None

    # Try to get direct PDF URL from best_oa_location
    best_loc = data.get("best_oa_location") or {}
    pdf_url = best_loc.get("pdf_url")
    if pdf_url:
        best_oa_pdf_url = pdf_url
        source_obj = best_loc.get("source") or {}
        best_oa_source = source_obj.get("display_name") or best_loc.get("source_type")

    # Title / journal / year / publisher
    title = data.get("title")
    year = data.get("publication_year")

    primary_location = data.get("primary_location", {}) or {}
    source_obj = primary_location.get("source", {}) or {}
    journal = source_obj.get("display_name")

    # Publisher from host_organization or primary_location
    publisher: str | None = None
    host_org = source_obj.get("host_organization_name")
    if host_org:
        publisher = host_org

    logger.info(
        "OpenAlex resolved DOI %s: pmid=%s pmcid=%s arxiv=%s oa=%s",
        doi, pmid, pmcid, arxiv_id, oa_status.value,
    )

    return ResolvedIdentifiers(
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        arxiv_id=arxiv_id,
        openalex_id=openalex_id,
        oa_status=oa_status,
        best_oa_pdf_url=best_oa_pdf_url,
        best_oa_source=best_oa_source,
        publisher=publisher,
        title=title,
        journal=journal,
        year=year,
        resolution_source="openalex",
    )


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
        r_pmid = str(resolved.get("pmid", "") or "").strip()
        r_pmcid = str(resolved.get("pmcid", "") or "").strip()
        if r_pmid or r_pmcid:
            cand = enriched[idx]
            enriched[idx] = cand.model_copy(update={
                "pmid": r_pmid or cand.pmid,
                "pmcid": r_pmcid or cand.pmcid,
            })
            resolved_count += 1

    for idx, pmid in pmid_only:
        resolved = pmid_map.get(pmid, {})
        r_doi = str(resolved.get("doi", "") or "").strip()
        r_pmcid = str(resolved.get("pmcid", "") or "").strip()
        if r_doi or r_pmcid:
            cand = enriched[idx]
            enriched[idx] = cand.model_copy(update={
                "doi": r_doi or cand.doi,
                "pmcid": r_pmcid or cand.pmcid,
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
