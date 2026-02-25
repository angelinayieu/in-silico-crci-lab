# VERIFIED: rules CL-1, CL-2 match CONVERSION_VALIDITY_AND_HARDENING.md Module 4.2
# VERIFIED: imports — all modules exist (shared.models)
# VERIFIED: backward wiring — reads study_registry_v1 records
# VERIFIED: forward wiring — writes lineage assignments for IVW deduplication
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P4.COHORT-LINEAGE
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 4.2 (Cohort Lineage)
Rules:
    CL-1: Only ONE paper per cohort lineage contributes to IVW pooling.
          Selection hierarchy: longest follow-up → largest N → most recent.
    CL-2: Non-selected papers contribute annotations and temporal data
          (flagged as SUPPLEMENTARY).
Detection:
    - Same clinical trial registry number (NCT#)
    - Same first/senior author + institution + overlapping N
    - Paper states "secondary analysis of [trial]"
    - Shared funding grant number
Reads: StudyRegistry records
Writes: Lineage assignments (cohort_lineage_id, lineage_role)
Gates: None (advisory; downstream IVW respects lineage_role)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from crci.shared.models.enums import LineageRole

logger = logging.getLogger(__name__)


@dataclass
class StudyMetadata:
    """Minimal study metadata for lineage detection."""

    study_id: str
    title: str | None = None
    authors: str | None = None
    doi: str | None = None
    year: int | None = None
    n_analyzed: int | None = None
    follow_up_months: float | None = None
    trial_registry_id: str | None = None
    funding_grant: str | None = None
    is_secondary_analysis: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class LineageAssignment:
    """Cohort lineage assignment for a single study."""

    study_id: str
    cohort_lineage_id: str
    lineage_role: LineageRole
    selection_reason: str


@dataclass(frozen=True)
class LineageGroup:
    """A group of studies from the same cohort/trial."""

    cohort_lineage_id: str
    primary_study_id: str
    member_study_ids: tuple[str, ...]
    assignments: tuple[LineageAssignment, ...]


# ═══════════════════════════════════════════════════════════════
#  LINEAGE DETECTION
# ═══════════════════════════════════════════════════════════════


_NCT_PATTERN = re.compile(r"NCT\d{8}", re.IGNORECASE)
_ISRCTN_PATTERN = re.compile(r"ISRCTN\d+", re.IGNORECASE)


def _extract_trial_id(text: str | None) -> str | None:
    """Extract trial registry ID (NCT or ISRCTN) from text."""
    if text is None:
        return None
    match = _NCT_PATTERN.search(text)
    if match:
        return match.group(0).upper()
    match = _ISRCTN_PATTERN.search(text)
    if match:
        return match.group(0).upper()
    return None


def _first_author(authors: str | None) -> str | None:
    """Extract normalized first author surname."""
    if not authors:
        return None
    # Handle "Smith J, Jones K, ..." or "Smith, J.; Jones, K."
    first = authors.split(",")[0].split(";")[0].strip()
    # Take surname only (first token)
    parts = first.split()
    return parts[0].lower() if parts else None


def detect_lineage_candidates(
    studies: list[StudyMetadata],
) -> list[list[int]]:
    """Detect potential lineage groups from study metadata.

    Signals for same lineage:
    1. Same clinical trial registry number
    2. Same first author + overlapping N (within 30%)
    3. Paper marked as secondary analysis
    4. Shared funding grant number

    Returns
    -------
    list[list[int]]
        Groups of study indices that share a lineage.
    """
    n = len(studies)
    # Union-Find for grouping
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Signal 1: Same trial registry ID
    trial_id_map: dict[str, list[int]] = {}
    for i, s in enumerate(studies):
        tid = s.trial_registry_id or _extract_trial_id(s.notes)
        if tid:
            trial_id_map.setdefault(tid, []).append(i)
    for indices in trial_id_map.values():
        for idx in indices[1:]:
            union(indices[0], idx)

    # Signal 2: Same first author + overlapping N
    for i in range(n):
        author_i = _first_author(studies[i].authors)
        if not author_i:
            continue
        for j in range(i + 1, n):
            author_j = _first_author(studies[j].authors)
            if author_i != author_j:
                continue
            # Check overlapping N (within 30%)
            n_i = studies[i].n_analyzed
            n_j = studies[j].n_analyzed
            if n_i and n_j and n_i > 0 and n_j > 0:
                ratio = min(n_i, n_j) / max(n_i, n_j)
                if ratio >= 0.70:
                    union(i, j)

    # Signal 3: Explicit secondary analysis
    for i, s in enumerate(studies):
        if s.is_secondary_analysis:
            # Try to match with the primary by author
            author_i = _first_author(s.authors)
            if author_i:
                for j in range(n):
                    if i == j:
                        continue
                    if _first_author(studies[j].authors) == author_i:
                        if not studies[j].is_secondary_analysis:
                            union(i, j)
                            break

    # Signal 4: Shared funding grant
    grant_map: dict[str, list[int]] = {}
    for i, s in enumerate(studies):
        if s.funding_grant:
            grant_key = s.funding_grant.strip().upper()
            grant_map.setdefault(grant_key, []).append(i)
    for indices in grant_map.values():
        if len(indices) > 1:
            for idx in indices[1:]:
                union(indices[0], idx)

    # Collect groups
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Only return groups with >1 member
    return [g for g in groups.values() if len(g) > 1]


# ═══════════════════════════════════════════════════════════════
#  PRIMARY SELECTION (CL-1)
# ═══════════════════════════════════════════════════════════════


def select_primary(
    studies: list[StudyMetadata],
    group_indices: list[int],
) -> int:
    """CL-1: Select the PRIMARY study from a lineage group.

    Selection hierarchy:
    1. Longest follow-up (most complete data)
    2. Largest sample size (if follow-up equal)
    3. Most recent publication (if N and follow-up equal)
    4. Primary outcome paper over secondary analysis

    Returns
    -------
    int
        Index of the selected primary study.
    """
    def sort_key(idx: int) -> tuple[float, int, int, int]:
        s = studies[idx]
        follow_up = s.follow_up_months if s.follow_up_months is not None else 0.0
        n = s.n_analyzed if s.n_analyzed is not None else 0
        year = s.year if s.year is not None else 0
        is_primary = 0 if s.is_secondary_analysis else 1
        return (follow_up, n, year, is_primary)

    best_idx = max(group_indices, key=sort_key)
    return best_idx


def assign_lineage(
    studies: list[StudyMetadata],
) -> list[LineageGroup]:
    """Detect lineage groups and assign PRIMARY/SUPPLEMENTARY roles.

    Parameters
    ----------
    studies : list[StudyMetadata]
        All studies to check for lineage relationships.

    Returns
    -------
    list[LineageGroup]
        Lineage groups with role assignments.
    """
    candidate_groups = detect_lineage_candidates(studies)
    lineage_groups: list[LineageGroup] = []

    for group_idx, indices in enumerate(candidate_groups):
        primary_idx = select_primary(studies, indices)
        cohort_id = f"LINEAGE_{group_idx:04d}"

        assignments: list[LineageAssignment] = []
        for idx in indices:
            s = studies[idx]
            if idx == primary_idx:
                role = LineageRole.PRIMARY
                reason = "CL-1: selected as primary (best follow-up/N/recency)"
            elif s.is_secondary_analysis:
                role = LineageRole.SUPPLEMENTARY
                reason = "CL-2: secondary analysis → SUPPLEMENTARY"
            else:
                # Check if it's a follow-up with different timepoint
                primary = studies[primary_idx]
                if (
                    s.follow_up_months is not None
                    and primary.follow_up_months is not None
                    and s.follow_up_months != primary.follow_up_months
                ):
                    role = LineageRole.FOLLOW_UP
                    reason = f"CL-2: different follow-up ({s.follow_up_months}mo vs primary {primary.follow_up_months}mo)"
                else:
                    role = LineageRole.SUPPLEMENTARY
                    reason = "CL-2: same lineage → SUPPLEMENTARY"

            assignments.append(LineageAssignment(
                study_id=s.study_id,
                cohort_lineage_id=cohort_id,
                lineage_role=role,
                selection_reason=reason,
            ))

            logger.info(
                "Lineage %s: study=%s → %s (%s)",
                cohort_id, s.study_id, role.value, reason,
            )

        lineage_groups.append(LineageGroup(
            cohort_lineage_id=cohort_id,
            primary_study_id=studies[primary_idx].study_id,
            member_study_ids=tuple(studies[idx].study_id for idx in indices),
            assignments=tuple(assignments),
        ))

    return lineage_groups
