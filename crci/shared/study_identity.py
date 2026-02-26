"""
Component: Shared — Study Identity Generation
Purpose: Deterministic study_id computation for idempotent extraction.

Problem: Previously, study_id was `STUDY_{uuid.uuid4().hex[:12]}` which generated
a new ID every run, causing duplicate rows on re-extraction.

Solution: Use deterministic IDs based on persistent identifiers:
    1. DOI (normalized) if available
    2. PMID if available
    3. PMCID if available
    4. SHA-1 hash of (normalized_title + year + journal) as fallback

Reads: Paper metadata dict
Writes: Nothing (pure function)
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_doi(doi: str | None) -> str | None:
    """Normalize DOI to canonical form.

    - Lowercase
    - Strip whitespace
    - Remove leading https://doi.org/ or http://dx.doi.org/ prefixes
    - Remove leading 'doi:' prefix

    Args:
        doi: Raw DOI string or None.

    Returns:
        Normalized DOI or None if invalid/empty.
    """
    if not doi:
        return None

    doi = doi.strip().lower()

    # Remove common URL prefixes
    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi.org/",
        "dx.doi.org/",
        "doi:",
    ]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break

    doi = doi.strip()
    return doi if doi else None


def normalize_title(title: str | None) -> str:
    """Normalize title for hashing.

    - Lowercase
    - Collapse whitespace
    - Remove common punctuation
    - Strip

    Args:
        title: Raw title string or None.

    Returns:
        Normalized title (empty string if None).
    """
    if not title:
        return ""

    title = title.lower()
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title)
    # Remove punctuation except alphanumeric and space
    title = re.sub(r"[^\w\s]", "", title)
    return title.strip()


def compute_study_id(metadata: dict[str, Any]) -> tuple[str, str]:
    """Compute deterministic study_id from metadata.

    Priority order:
    1. DOI: study_id = "doi:<normalized_doi>"
    2. PMID: study_id = "pmid:<pmid>"
    3. PMCID: study_id = "pmcid:<pmcid>"
    4. Hash: study_id = "hash:<sha1(title|year|journal)[:16]>"

    Args:
        metadata: Dict with optional keys: doi, pmid, pmcid, title, year, journal.

    Returns:
        Tuple of (study_id, id_source) where id_source is one of:
        'doi', 'pmid', 'pmcid', 'hash'.
    """
    # 1. Try DOI
    doi = normalize_doi(metadata.get("doi"))
    if doi:
        return f"doi:{doi}", "doi"

    # 2. Try PMID
    pmid = metadata.get("pmid")
    if pmid:
        pmid = str(pmid).strip()
        if pmid:
            return f"pmid:{pmid}", "pmid"

    # 3. Try PMCID
    pmcid = metadata.get("pmcid")
    if pmcid:
        pmcid = str(pmcid).strip()
        if pmcid:
            return f"pmcid:{pmcid}", "pmcid"

    # 4. Fallback: hash of title + year + journal
    title = normalize_title(metadata.get("title"))
    year = str(metadata.get("year", "")).strip()
    journal = normalize_title(metadata.get("journal"))

    hash_input = f"{title}|{year}|{journal}"
    hash_digest = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()[:16]

    return f"hash:{hash_digest}", "hash"


def check_duplicate_study(
    session,
    doi: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
) -> str | None:
    """Check if a study with the given identifiers already exists.

    Args:
        session: SQLAlchemy session.
        doi: DOI to check (will be normalized).
        pmid: PMID to check.
        pmcid: PMCID to check.

    Returns:
        Existing study_id if found, None otherwise.
    """
    from sqlalchemy import text

    # Check by normalized DOI
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        result = session.execute(
            text("SELECT study_id FROM study_registry_v1 WHERE doi_normalized = :doi"),
            {"doi": normalized_doi},
        ).fetchone()
        if result:
            return result[0]

    # Check by PMID
    if pmid:
        result = session.execute(
            text("SELECT study_id FROM study_registry_v1 WHERE pmid = :pmid"),
            {"pmid": str(pmid).strip()},
        ).fetchone()
        if result:
            return result[0]

    # Check by PMCID
    if pmcid:
        result = session.execute(
            text("SELECT study_id FROM study_registry_v1 WHERE pmcid = :pmcid"),
            {"pmcid": str(pmcid).strip()},
        ).fetchone()
        if result:
            return result[0]

    return None


# ═══════════════════════════════════════════════════════════════
#  Filesystem-Safe Naming Conversion
#  Master Spec §9.3: files named {study_id}.pdf, {study_id}.txt, etc.
#  Problem: study_id contains : and / which are invalid in filenames.
# ═══════════════════════════════════════════════════════════════


def study_id_to_filename(study_id: str) -> str:
    """Convert study_id to filesystem-safe string.

    Handles the : and / characters that appear in DOI-based study_ids.
    Uses reversible encoding: : → --, / → __

    Args:
        study_id: Database study_id (e.g., "doi:10.1016/j.lfs.2013.08.011").

    Returns:
        Filesystem-safe string (e.g., "doi--10.1016__j.lfs.2013.08.011").

    Example:
        >>> study_id_to_filename("doi:10.1016/j.lfs.2013.08.011")
        'doi--10.1016__j.lfs.2013.08.011'
        >>> study_id_to_filename("pmid:24333862")
        'pmid--24333862'
        >>> study_id_to_filename("hash:1a19634d5552fb63")
        'hash--1a19634d5552fb63'
    """
    return study_id.replace(":", "--").replace("/", "__")


def filename_to_study_id(filename: str) -> str:
    """Convert filesystem-safe string back to study_id.

    Reverse of study_id_to_filename().

    Args:
        filename: Filesystem-safe string (without extension).

    Returns:
        Database study_id.

    Example:
        >>> filename_to_study_id("doi--10.1016__j.lfs.2013.08.011")
        'doi:10.1016/j.lfs.2013.08.011'
    """
    return filename.replace("--", ":").replace("__", "/")


def get_study_file_path(study_id: str, extension: str, base_dir: str | None = None) -> str:
    """Get the canonical file path for a study artifact.

    Follows Master Spec §9.3 naming convention:
    - {study_id}.pdf → Downloaded PDF
    - {study_id}.json → Paperscraper metadata sidecar
    - {study_id}.txt → EX-INGEST canonical text
    - {study_id}_papermap.json → EX-P1 PaperMap

    Args:
        study_id: Database study_id.
        extension: File extension (e.g., "pdf", "txt", "json").
        base_dir: Optional base directory. Defaults to data/papers/.

    Returns:
        Full file path as string.
    """
    from pathlib import Path

    if base_dir is None:
        base_dir = "data/papers"

    safe_name = study_id_to_filename(study_id)
    return str(Path(base_dir) / f"{safe_name}.{extension}")


# ═══════════════════════════════════════════════════════════════
#  Evidence Row Identity (Dedup Key)
#  IMPLEMENTATION_SLICES.md Slice 0, Gap 3
#
#  An evidence row is uniquely identified by 8 fields. Two rows with
#  the same identity are the same observation; two with different
#  identities are distinct even if they share study_id + edge_id.
# ═══════════════════════════════════════════════════════════════

# The fields that compose the identity hash (order matters — do not reorder)
EVIDENCE_IDENTITY_FIELDS: tuple[str, ...] = (
    "study_id",
    "edge_relation_id",
    "instrument_id",
    "timepoint_weeks",
    "comparison_arm_label",
    "effect_size_context",
    "endpoint_vs_change",
    "outcome_node_id",
)


def compute_evidence_identity(row: dict[str, Any]) -> str:
    """Compute deterministic identity hash for an evidence row.

    Two rows with the same identity are considered the same observation.
    Two rows with different identities are distinct observations even
    if they share study_id and edge_relation_id.

    The hash is computed over 8 distinguishing dimensions:
    - study_id: which study
    - edge_relation_id: which causal edge
    - instrument_id: different instruments = different rows
    - timepoint_weeks: different timepoints = different rows
    - comparison_arm_label: different comparators = different rows
    - effect_size_context: between vs within = different rows
    - endpoint_vs_change: endpoint vs change score = different rows
    - outcome_node_id: different outcome domains = different rows

    Args:
        row: Dict-like object with evidence row fields.

    Returns:
        Deterministic ler_id string with "ler_" prefix + 16-char hex hash.

    Examples:
        >>> row1 = {"study_id": "doi:10.1234/x", "edge_relation_id": "E001",
        ...         "instrument_id": "HVLT", "timepoint_weeks": "12",
        ...         "comparison_arm_label": "", "effect_size_context": "BETWEEN_GROUP",
        ...         "endpoint_vs_change": "endpoint", "outcome_node_id": "N_COG"}
        >>> row2 = dict(row1, instrument_id="COWAT")
        >>> compute_evidence_identity(row1) != compute_evidence_identity(row2)
        True
        >>> compute_evidence_identity(row1) == compute_evidence_identity(row1)
        True
    """
    identity_parts = [
        str(row.get(field, "")) for field in EVIDENCE_IDENTITY_FIELDS
    ]
    identity_str = "|".join(identity_parts)
    return "ler_" + hashlib.sha256(identity_str.encode("utf-8")).hexdigest()[:16]
