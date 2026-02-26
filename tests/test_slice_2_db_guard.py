"""
Test: Slice 2 — DB Persistence Protection (FIX-2)
Purpose: Verify that:
    1. db_guard detects evidence rows and blocks destructive operations
    2. --force flag allows proceeding (in dev environment)
    3. CRCI_ENV guard blocks non-dev destructive operations
    4. backup_db creates a timestamped backup file data

Definition of Done (from IMPLEMENTATION_SLICES.md):
    test_guard_blocks: With evidence rows in DB, setup_database.py --reset
    (without --force) exits non-zero. With --force AND CRCI_ENV=dev, succeeds
    and creates backup file.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCheckEvidenceExists:
    """db_guard.check_evidence_exists must detect evidence rows."""

    def test_function_exists(self):
        from scripts.db_guard import check_evidence_exists
        assert callable(check_evidence_exists)

    def test_returns_dict_of_counts(self, tmp_path):
        """Should return a dict mapping table names to row counts."""
        from scripts.db_guard import check_evidence_exists

        # Create a temp SQLite DB with some evidence
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE edge_evidence_v1 (ler_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO edge_evidence_v1 VALUES ('ler_001')")
        conn.execute("INSERT INTO edge_evidence_v1 VALUES ('ler_002')")
        conn.execute("CREATE TABLE study_registry_v1 (study_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO study_registry_v1 VALUES ('STUDY_TEST')")
        conn.commit()
        conn.close()

        counts = check_evidence_exists(str(db_path))
        assert isinstance(counts, dict)
        assert counts.get("edge_evidence_v1") == 2
        assert counts.get("study_registry_v1") == 1

    def test_empty_db(self, tmp_path):
        """Should return 0 counts for empty/missing tables."""
        from scripts.db_guard import check_evidence_exists

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE edge_evidence_v1 (ler_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        counts = check_evidence_exists(str(db_path))
        assert counts.get("edge_evidence_v1") == 0

    def test_missing_tables(self, tmp_path):
        """Should handle missing tables gracefully (return 0)."""
        from scripts.db_guard import check_evidence_exists

        db_path = tmp_path / "bare.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE some_other_table (id TEXT)")
        conn.commit()
        conn.close()

        counts = check_evidence_exists(str(db_path))
        assert counts.get("edge_evidence_v1") == 0


class TestGuardBeforeReset:
    """guard_before_reset must block if evidence exists and --force not set."""

    def test_blocks_when_evidence_exists(self, tmp_path, capsys):
        """With evidence rows, should return False (blocked)."""
        from scripts.db_guard import guard_before_reset

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE edge_evidence_v1 (ler_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO edge_evidence_v1 VALUES ('ler_001')")
        conn.commit()
        conn.close()

        result = guard_before_reset(str(db_path), force=False)
        assert result is False

    def test_allows_when_no_evidence(self, tmp_path):
        """With no evidence rows, should return True (proceed)."""
        from scripts.db_guard import guard_before_reset

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE edge_evidence_v1 (ler_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        result = guard_before_reset(str(db_path), force=False)
        assert result is True

    def test_force_overrides_block(self, tmp_path):
        """With --force, should return True even with evidence."""
        from scripts.db_guard import guard_before_reset

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE edge_evidence_v1 (ler_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO edge_evidence_v1 VALUES ('ler_001')")
        conn.commit()
        conn.close()

        result = guard_before_reset(str(db_path), force=True)
        assert result is True


class TestBackupDb:
    """backup_db must create a timestamped copy of the database file."""

    def test_creates_backup(self, tmp_path):
        """Should create a backup file with .bak. in its name."""
        from scripts.db_guard import backup_db

        db_path = tmp_path / "test.db"
        db_path.write_text("fake db content")

        backup_path = backup_db(str(db_path))
        assert backup_path.exists()
        assert ".bak." in backup_path.name
        assert backup_path.read_text() == "fake db content"

    def test_backup_path_is_returned(self, tmp_path):
        """Should return a Path object pointing to the backup."""
        from scripts.db_guard import backup_db

        db_path = tmp_path / "test.db"
        db_path.write_text("data")

        backup_path = backup_db(str(db_path))
        assert isinstance(backup_path, Path)


class TestRequireDevEnvironment:
    """require_dev_environment must block non-dev destructive operations."""

    def test_dev_env_passes(self):
        """CRCI_ENV=dev should not raise."""
        from scripts.db_guard import require_dev_environment

        with patch.dict(os.environ, {"CRCI_ENV": "dev"}):
            # Should not raise
            require_dev_environment(force=False)

    def test_missing_env_blocks(self):
        """Missing CRCI_ENV should raise SystemExit."""
        from scripts.db_guard import require_dev_environment

        env = os.environ.copy()
        env.pop("CRCI_ENV", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                require_dev_environment(force=False)

    def test_prod_env_blocks(self):
        """CRCI_ENV=prod should raise SystemExit."""
        from scripts.db_guard import require_dev_environment

        with patch.dict(os.environ, {"CRCI_ENV": "prod"}):
            with pytest.raises(SystemExit):
                require_dev_environment(force=False)

    def test_force_overrides_prod(self):
        """--force should warn but not block even in non-dev env."""
        from scripts.db_guard import require_dev_environment

        with patch.dict(os.environ, {"CRCI_ENV": "prod"}):
            # Should not raise with force=True
            require_dev_environment(force=True)
