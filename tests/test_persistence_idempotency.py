"""
Test: Persistence Idempotency (S4)
Purpose: Verify that running extraction twice on the same paper:
    1. Does NOT create duplicate study_registry rows
    2. Does NOT create duplicate edge_evidence rows
    3. Updates existing rows instead of inserting new ones
"""
from __future__ import annotations

import sqlite3
import re
from pathlib import Path

import pytest

from sqlalchemy import create_engine

from crci.shared.study_identity import compute_study_id, normalize_doi


class TestStudyIdentity:
    """Test deterministic study_id computation."""

    def test_doi_normalization(self):
        """DOIs should be normalized consistently."""
        cases = [
            ("https://doi.org/10.1016/j.lfs.2013.08.011", "10.1016/j.lfs.2013.08.011"),
            ("http://dx.doi.org/10.1016/j.lfs.2013.08.011", "10.1016/j.lfs.2013.08.011"),
            ("  10.1016/j.lfs.2013.08.011  ", "10.1016/j.lfs.2013.08.011"),
            ("10.1016/J.LFS.2013.08.011", "10.1016/j.lfs.2013.08.011"),  # lowercase
        ]
        for raw, expected in cases:
            assert normalize_doi(raw) == expected, f"Failed for {raw}"

    def test_doi_none_handling(self):
        """None and empty should return None."""
        assert normalize_doi(None) is None
        assert normalize_doi("") is None
        assert normalize_doi("   ") is None

    def test_study_id_priority_doi_first(self):
        """DOI takes priority over PMID and PMCID."""
        metadata = {
            "doi": "10.1016/j.lfs.2013.08.011",
            "pmid": "24333862",
            "pmcid": "PMC123456",
        }
        study_id, source = compute_study_id(metadata)
        assert source == "doi"
        assert study_id == "doi:10.1016/j.lfs.2013.08.011"

    def test_study_id_fallback_pmid(self):
        """PMID used when DOI missing."""
        metadata = {"pmid": "24333862"}
        study_id, source = compute_study_id(metadata)
        assert source == "pmid"
        assert study_id == "pmid:24333862"

    def test_study_id_fallback_pmcid(self):
        """PMCID used when DOI and PMID missing."""
        metadata = {"pmcid": "PMC123456"}
        study_id, source = compute_study_id(metadata)
        assert source == "pmcid"
        assert study_id == "pmcid:PMC123456"

    def test_study_id_fallback_hash(self):
        """Hash used when no persistent IDs."""
        metadata = {
            "title": "Effects of chemotherapy on cognition",
            "year": 2023,
            "journal": "Cancer Research",
        }
        study_id, source = compute_study_id(metadata)
        assert source == "hash"
        assert study_id.startswith("hash:")
        assert len(study_id) == 21  # "hash:" + 16 chars

    def test_study_id_deterministic(self):
        """Same metadata produces same study_id."""
        metadata = {"doi": "10.1016/j.lfs.2013.08.011"}
        id1, _ = compute_study_id(metadata)
        id2, _ = compute_study_id(metadata)
        assert id1 == id2

    def test_hash_stability(self):
        """Hash should be stable across runs."""
        metadata = {"title": "Test", "year": 2023, "journal": "Journal"}
        id1, _ = compute_study_id(metadata)
        id2, _ = compute_study_id(metadata)
        assert id1 == id2


class TestEvidenceDedup:
    """Test evidence row deduplication."""

    def test_span_hash_deterministic(self):
        """Same inputs produce same span_hash."""
        from crci.extraction.evidence_writer import compute_span_hash

        hash1 = compute_span_hash(
            study_id="doi:10.1016/j.lfs.2013.08.011",
            edge_relation_id="EDGE_001",
            profile_id="PROFILE_001",
            beta=0.5,
            se=0.1,
        )
        hash2 = compute_span_hash(
            study_id="doi:10.1016/j.lfs.2013.08.011",
            edge_relation_id="EDGE_001",
            profile_id="PROFILE_001",
            beta=0.5,
            se=0.1,
        )
        assert hash1 == hash2

    def test_span_hash_differs_on_beta(self):
        """Different beta values produce different hashes."""
        from crci.extraction.evidence_writer import compute_span_hash

        hash1 = compute_span_hash(
            study_id="doi:10.1016/j.lfs.2013.08.011",
            edge_relation_id="EDGE_001",
            profile_id="PROFILE_001",
            beta=0.5,
            se=0.1,
        )
        hash2 = compute_span_hash(
            study_id="doi:10.1016/j.lfs.2013.08.011",
            edge_relation_id="EDGE_001",
            profile_id="PROFILE_001",
            beta=0.6,  # Different
            se=0.1,
        )
        assert hash1 != hash2


class TestDatabaseConstraints:
    """Test that unique indexes exist in the database."""

    @pytest.fixture
    def db_path(self, tmp_path: Path):
        """Create a fresh SQLite DB and apply schema migrations.

        These tests should not depend on a developer's local `crci_dev.db`
        being up-to-date. Instead, we execute the schema SQL files in order
        against a temporary database.
        """
        db_file = tmp_path / "crci_test.db"

        schema_dir = Path(__file__).resolve().parents[1] / "crci" / "database" / "schema"
        if not schema_dir.exists():
            pytest.skip("Schema directory not found")

        # 1) Create tables via ORM (SQLite-safe; schema .sql contains Postgres COMMENT statements)
        from crci.shared.models.tables import Base

        engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(engine)

        # 2) Apply uniqueness indexes from the SQLite-compatible migration file.
        # We intentionally skip ALTER TABLE clauses since the ORM already
        # includes these columns.
        migration_011 = schema_dir / "011_study_identity.sql"
        if not migration_011.exists():
            pytest.skip("Migration 011_study_identity.sql not found")

        migration_sql = migration_011.read_text(encoding="utf-8")
        # Strip '-- ...' line comments to avoid matching words like 'indexes'
        # inside comments.
        migration_sql = re.sub(r"--.*?$", "", migration_sql, flags=re.MULTILINE)

        # Extract CREATE [UNIQUE] INDEX statements (SQLite-compatible subset)
        ddl_statements = re.findall(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\b.*?;",
            migration_sql,
            flags=re.IGNORECASE | re.DOTALL,
        )

        conn = sqlite3.connect(db_file)
        try:
            conn.executescript("\n".join(ddl_statements))
            conn.commit()
        finally:
            conn.close()

        return db_file

    def test_study_registry_unique_indexes_exist(self, db_path):
        """Verify unique indexes on study_registry_v1."""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='study_registry_v1'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_study_doi_normalized_unique" in indexes
        assert "idx_study_pmid_unique" in indexes
        assert "idx_study_pmcid_unique" in indexes

    def test_edge_evidence_unique_index_exists(self, db_path):
        """Verify unique index on edge_evidence_v1."""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='edge_evidence_v1'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_evidence_dedup" in indexes

    def test_new_columns_exist(self, db_path):
        """Verify new columns were added."""
        conn = sqlite3.connect(db_path)

        # Check study_registry_v1 columns
        cursor = conn.execute("PRAGMA table_info(study_registry_v1)")
        sr_cols = {row[1] for row in cursor.fetchall()}
        assert "doi_normalized" in sr_cols
        assert "id_source" in sr_cols

        # Check edge_evidence_v1 columns
        cursor = conn.execute("PRAGMA table_info(edge_evidence_v1)")
        ee_cols = {row[1] for row in cursor.fetchall()}
        assert "span_hash" in ee_cols

        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
