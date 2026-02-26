# ASSUMPTIONS: DOIs follow ISO 26324 (case-insensitive, prefix-stripped).
#              PMIDs are numeric strings with no leading zeros that matter.
# TEST COVERAGE: tests/test_identifier_utils.py
# REVIEW: Normalization covers known real-world variations but not all edge cases
#         (e.g., Unicode DOIs, DOIs with parentheses). Extend as issues are found.
"""
Component: SYS_EXTRACTION.EX-ACQ.IdentifierUtils
Purpose: Robust normalization and dedup key generation for paper identifiers.
         Used by hop_discoverer, aps_scorer, search_coordinator, id_resolver
         to ensure consistent matching across DOI/PMID format variants.
Reads: Nothing (pure functions)
Writes: Nothing (returns normalized strings/hashes)
"""
from __future__ import annotations

import hashlib
import re

# Regex for prefix stripping: https://doi.org/, http://dx.doi.org/, doi:, etc.
_DOI_PREFIX_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
    re.IGNORECASE,
)

# Trailing punctuation that is never part of a DOI
_DOI_TRAILING_RE = re.compile(r"[.\s,;]+$")


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI to a canonical lowercase form.

    Strips common URL prefixes (https://doi.org/, http://dx.doi.org/, doi:),
    removes trailing punctuation and whitespace, and lowercases.

    Args:
        doi: Raw DOI string, or None.

    Returns:
        Normalized DOI string, or None if input is empty/None.

    Examples:
        >>> normalize_doi("https://doi.org/10.1016/j.psyneuen.2017.05.018")
        '10.1016/j.psyneuen.2017.05.018'
        >>> normalize_doi("DOI: 10.1016/J.PSYNEUEN.2017.05.018.")
        '10.1016/j.psyneuen.2017.05.018'
        >>> normalize_doi(None)
        None
    """
    if not doi:
        return None
    cleaned = doi.strip()
    cleaned = _DOI_PREFIX_RE.sub("", cleaned)
    cleaned = _DOI_TRAILING_RE.sub("", cleaned)
    cleaned = cleaned.strip().lower()
    return cleaned if cleaned else None


def normalize_pmid(pmid: str | int | None) -> str | None:
    """Normalize a PMID to a canonical string form.

    Strips whitespace, "PMID:" prefix, and converts int to str.

    Args:
        pmid: Raw PMID (string or int), or None.

    Returns:
        Normalized PMID string (digits only), or None if invalid.

    Examples:
        >>> normalize_pmid("PMID: 28778509")
        '28778509'
        >>> normalize_pmid(28778509)
        '28778509'
        >>> normalize_pmid("  28778509  ")
        '28778509'
    """
    if pmid is None:
        return None
    s = str(pmid).strip()
    # Strip "PMID:" or "pmid:" prefix
    s = re.sub(r"^pmid:\s*", "", s, flags=re.IGNORECASE)
    s = s.strip()
    # Validate: should be digits only
    if not s or not s.isdigit():
        return None
    return s


def candidate_dedup_key(
    doi: str | None = None,
    pmid: str | int | None = None,
    title: str | None = None,
    first_author: str | None = None,
    year: int | str | None = None,
) -> str:
    """Generate a dedup key for a candidate paper.

    Priority: normalized DOI > normalized PMID > hash(title|author|year).

    For candidates without DOI/PMID, produces a SHA-1 hash of the
    normalized title + first_author + year so that identical candidates
    across reruns are caught.

    Args:
        doi: DOI string.
        pmid: PMID string or int.
        title: Paper title.
        first_author: First author name.
        year: Publication year.

    Returns:
        Canonical dedup key string.
    """
    ndoi = normalize_doi(doi)
    if ndoi:
        return f"doi:{ndoi}"

    npmid = normalize_pmid(pmid)
    if npmid:
        return f"pmid:{npmid}"

    # Fallback: hash of available metadata
    parts = [
        (title or "").strip().lower()[:200],
        (first_author or "").strip().lower(),
        str(year or ""),
    ]
    combined = "|".join(parts)
    h = hashlib.sha1(combined.encode("utf-8")).hexdigest()[:16]
    return f"meta:{h}"
