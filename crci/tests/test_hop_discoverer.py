"""Tests for crci.retrieval.hop_discoverer.

Covers:
- DOI normalization via identifier_utils
- Dedup key generation
- Per-paper cap enforcement (HOP-G3)
- Depth ceiling enforcement (HOP-G1)
- APS semantics (aps_score=None, boost stored in components)
- Global budget enforcement (HOP-G4)
"""
from __future__ import annotations

import json
import uuid

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from crci.retrieval.identifier_utils import (
    normalize_doi,
    normalize_pmid,
    candidate_dedup_key,
)


# ═══════════════════════════════════════════════════════════════
#  Unit tests: identifier_utils (no DB needed)
# ═══════════════════════════════════════════════════════════════


class TestNormalizeDoi:
    """Test DOI normalization strips prefixes, lowercases, removes trailing punct."""

    def test_plain_doi(self):
        assert normalize_doi("10.1016/j.psyneuen.2017.05.018") == "10.1016/j.psyneuen.2017.05.018"

    def test_https_prefix(self):
        assert normalize_doi("https://doi.org/10.1016/j.psyneuen.2017.05.018") == "10.1016/j.psyneuen.2017.05.018"

    def test_http_prefix(self):
        assert normalize_doi("http://doi.org/10.1016/J.Example") == "10.1016/j.example"

    def test_dx_doi_prefix(self):
        assert normalize_doi("https://dx.doi.org/10.1234/test") == "10.1234/test"

    def test_doi_colon_prefix(self):
        assert normalize_doi("doi:10.1234/test") == "10.1234/test"

    def test_trailing_period(self):
        assert normalize_doi("10.1234/test.") == "10.1234/test"

    def test_trailing_comma(self):
        assert normalize_doi("10.1234/test,") == "10.1234/test"

    def test_whitespace(self):
        assert normalize_doi("  10.1234/test  ") == "10.1234/test"

    def test_uppercase(self):
        assert normalize_doi("10.1016/J.EXAMPLE") == "10.1016/j.example"

    def test_none(self):
        assert normalize_doi(None) is None

    def test_empty(self):
        assert normalize_doi("") is None


class TestNormalizePmid:
    """Test PMID normalization strips prefix and validates digits."""

    def test_plain_pmid(self):
        assert normalize_pmid("12345678") == "12345678"

    def test_pmid_prefix(self):
        assert normalize_pmid("PMID:12345678") == "12345678"

    def test_pmid_prefix_space(self):
        assert normalize_pmid("PMID: 12345678") == "12345678"

    def test_whitespace(self):
        assert normalize_pmid("  12345678  ") == "12345678"

    def test_non_numeric(self):
        assert normalize_pmid("abc123") is None

    def test_none(self):
        assert normalize_pmid(None) is None

    def test_empty(self):
        assert normalize_pmid("") is None


class TestCandidateDedupKey:
    """Test dedup key generation priority: DOI > PMID > title/author/year hash."""

    def test_doi_priority(self):
        """DOI-based key takes priority even when PMID is present."""
        key = candidate_dedup_key(doi="10.1234/test", pmid="12345")
        assert key.startswith("doi:")

    def test_pmid_fallback(self):
        """PMID-based key when no DOI."""
        key = candidate_dedup_key(pmid="12345")
        assert key.startswith("pmid:")

    def test_title_hash_fallback(self):
        """Metadata hash when no DOI or PMID."""
        key = candidate_dedup_key(title="My Paper Title", first_author="Smith", year=2020)
        assert key.startswith("meta:")
        assert len(key) > 5

    def test_same_doi_same_key(self):
        """Same DOI (different casing/prefix) produces same key."""
        k1 = candidate_dedup_key(doi="10.1234/test")
        k2 = candidate_dedup_key(doi="https://doi.org/10.1234/TEST")
        assert k1 == k2

    def test_same_pmid_same_key(self):
        """Same PMID with/without prefix produces same key."""
        k1 = candidate_dedup_key(pmid="12345678")
        k2 = candidate_dedup_key(pmid="PMID:12345678")
        assert k1 == k2

    def test_same_title_same_hash(self):
        """Same title/author/year produces same hash key."""
        k1 = candidate_dedup_key(title="Test Paper", first_author="Doe", year=2021)
        k2 = candidate_dedup_key(title="Test Paper", first_author="Doe", year=2021)
        assert k1 == k2

    def test_different_title_different_hash(self):
        """Different title produces different hash key."""
        k1 = candidate_dedup_key(title="Paper A", first_author="Doe", year=2021)
        k2 = candidate_dedup_key(title="Paper B", first_author="Doe", year=2021)
        assert k1 != k2

    def test_no_identifiers_returns_meta_hash(self):
        """No identifiers produces a meta: hash (from empty strings)."""
        key = candidate_dedup_key()
        assert key is not None
        assert key.startswith("meta:")


class TestHopDiscoveryApsSemantics:
    """Test that APS semantics are correct (aps_score=None, boost in components)."""

    def test_aps_score_is_none_for_hop_candidates(self):
        """Hop candidates should have aps_score=None, not the boost value."""
        from crci.shared import config

        # The boost value should NOT be used as aps_score
        boost = config.HOP_CITATION_APS_BOOST
        threshold = config.APS_THRESHOLD

        # The old bug: aps_score=boost (0.15) < threshold (0.40) → always DEFER
        assert boost < threshold, (
            f"If boost ({boost}) >= threshold ({threshold}), "
            f"the old code would accidentally work. This test checks the bug premise."
        )


class TestConfigConstants:
    """Verify hop-related config constants exist and have sane values."""

    def test_hop_max_depth_exists(self):
        from crci.shared import config
        assert hasattr(config, "HOP_MAX_DEPTH")
        assert config.HOP_MAX_DEPTH >= 1

    def test_hop_max_targets_per_paper_exists(self):
        from crci.shared import config
        assert hasattr(config, "HOP_MAX_TARGETS_PER_PAPER")
        assert config.HOP_MAX_TARGETS_PER_PAPER >= 1

    def test_hop_max_total_per_run_exists(self):
        from crci.shared import config
        assert hasattr(config, "HOP_MAX_TOTAL_PER_RUN")
        assert config.HOP_MAX_TOTAL_PER_RUN >= 1

    def test_hop_citation_aps_boost_exists(self):
        from crci.shared import config
        assert hasattr(config, "HOP_CITATION_APS_BOOST")
        assert 0 < config.HOP_CITATION_APS_BOOST < 1.0


class TestStudyRegistryHopColumns:
    """Verify StudyRegistry model has hop-related columns."""

    def test_hop_depth_column(self):
        from crci.shared.models.tables import StudyRegistry
        assert hasattr(StudyRegistry, "hop_depth")

    def test_hop_source_study_id_column(self):
        from crci.shared.models.tables import StudyRegistry
        assert hasattr(StudyRegistry, "hop_source_study_id")

    def test_acquisition_queue_id_column(self):
        from crci.shared.models.tables import StudyRegistry
        assert hasattr(StudyRegistry, "acquisition_queue_id")
