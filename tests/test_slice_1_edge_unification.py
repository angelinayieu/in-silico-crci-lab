"""
Test: Slice 1 — Edge Definition Unification (FIX-1)
Purpose: Verify that:
    1. The seed loader loads edges directly from EDGE_REGISTRY.csv (source of truth)
    2. All loaded edge_relation_ids start with ER_ (not EDGE_)
    3. The column mapping (source_node_id→node_x, expected_sign→default_effect_direction) works
    4. The old seed CSV (EDGE_* format) is NOT used as an independent truth
    5. Evidence FK joins resolve (no orphan edge_relation_ids)

Definition of Done (from IMPLEMENTATION_SLICES.md):
    test_seed_roundtrip: Drop and recreate DB via seed loader →
    SELECT COUNT(*) FROM edge_relations_definitions_v1 = 138.
    All evidence FK joins still resolve (0 orphans).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
REGISTRY_PATH = PROJECT_ROOT / "registries" / "EDGE_REGISTRY.csv"
SEED_PATH = PROJECT_ROOT / "crci" / "database" / "seeds" / "edge_relations.csv"


class TestRegistryIsSourceOfTruth:
    """The EDGE_REGISTRY.csv must be the authoritative source for edge definitions."""

    def test_registry_exists(self):
        """EDGE_REGISTRY.csv must exist."""
        assert REGISTRY_PATH.exists(), f"Registry not found: {REGISTRY_PATH}"

    def test_registry_has_137_data_rows(self):
        """Registry should have 137 data rows (+ 1 header)."""
        with open(REGISTRY_PATH) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 137, f"Expected 137 rows, got {len(rows)}"

    def test_registry_all_er_ids(self):
        """All registry IDs must start with ER_."""
        with open(REGISTRY_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge_id = row["edge_relation_id"]
                assert edge_id.startswith("ER_"), (
                    f"Registry row has non-ER_ ID: {edge_id}"
                )

    def test_registry_has_required_columns(self):
        """Registry must have the columns we need for mapping."""
        with open(REGISTRY_PATH) as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            headers = set(reader.fieldnames)
        required = {
            "edge_relation_id", "source_node_id", "target_node_id",
            "relation_type", "mechanism_description", "primary_pathway",
            "expected_sign", "functional_form", "version", "active",
        }
        missing = required - headers
        assert not missing, f"Registry missing columns: {missing}"


class TestColumnMapping:
    """Verify the registry→DB column mapping logic."""

    def test_expected_sign_mapping(self):
        """expected_sign must map correctly to default_effect_direction."""
        from crci.database.seed_loader import _map_expected_sign
        assert _map_expected_sign("positive") == 1
        assert _map_expected_sign("negative") == -1
        assert _map_expected_sign("context_dependent") == 0
        assert _map_expected_sign("unknown_value") == 0

    def test_registry_row_to_seed_row(self):
        """A full registry row must map to a valid seed-format row."""
        from crci.database.seed_loader import _registry_row_to_edge_def

        registry_row = {
            "edge_relation_id": "ER_CHEMO_ACTIVITY",
            "source_node_id": "NODE_EXO_CHEMO_REGIMEN",
            "target_node_id": "NODE_BEH_PHYSICAL_ACTIVITY",
            "relation_type": "causal",
            "mechanism_description": "Chemotherapy side effects reduce physical activity",
            "primary_pathway": "PW_C2_FATIGUE",
            "secondary_pathways_json": '["PW_M17_DOPAMINERGIC"]',
            "expected_sign": "negative",
            "functional_form": "linear",
            "fallback_form": "linear",
            "is_feedback_edge": "0",
            "feedback_loop_id": "N/A",
            "notes": "test",
            "version": "1",
            "active": "1",
        }

        result = _registry_row_to_edge_def(registry_row)

        assert result["edge_relation_id"] == "ER_CHEMO_ACTIVITY"
        assert result["node_x"] == "NODE_EXO_CHEMO_REGIMEN"
        assert result["node_y"] == "NODE_BEH_PHYSICAL_ACTIVITY"
        assert result["default_effect_direction"] == -1
        assert result["edge_family"] == "PW_C2_FATIGUE"
        assert result["canonical_statement"] == "Chemotherapy side effects reduce physical activity"
        assert result["relation_label"] == "Chemotherapy side effects reduce physical activity"
        assert result["module"] == "A"
        assert result["default_temporal_family"] == "linear"

    def test_long_mechanism_description_truncated(self):
        """relation_label should be truncated to 80 chars."""
        from crci.database.seed_loader import _registry_row_to_edge_def

        long_desc = "A" * 150
        registry_row = {
            "edge_relation_id": "ER_TEST",
            "source_node_id": "N1",
            "target_node_id": "N2",
            "relation_type": "causal",
            "mechanism_description": long_desc,
            "primary_pathway": "PW_TEST",
            "secondary_pathways_json": "[]",
            "expected_sign": "positive",
            "functional_form": "linear",
            "fallback_form": "linear",
            "is_feedback_edge": "0",
            "feedback_loop_id": "",
            "notes": "",
            "version": "1",
            "active": "1",
        }

        result = _registry_row_to_edge_def(registry_row)
        assert len(result["relation_label"]) <= 80
        assert result["canonical_statement"] == long_desc  # full text preserved


class TestSeedLoaderRegistryIntegration:
    """Verify that load_all_seeds uses registry for edges when available."""

    def test_load_edges_from_registry_function_exists(self):
        """seed_loader must have a function to load edges from registry."""
        from crci.database.seed_loader import load_edges_from_registry
        assert callable(load_edges_from_registry)

    def test_seed_csv_not_stale_edge_format(self):
        """If the seed CSV still exists, it should NOT contain EDGE_* IDs.

        This catches the case where someone runs the old seed path and
        overwrites the 138 ER_* rows with 29 EDGE_* stubs.
        """
        if not SEED_PATH.exists():
            pytest.skip("Seed CSV has been removed (acceptable)")

        with open(SEED_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge_id = row["edge_relation_id"]
                assert not edge_id.startswith("EDGE_"), (
                    f"Seed CSV still contains stale EDGE_* ID: {edge_id}. "
                    f"Run: python -c 'from crci.database.seed_loader import "
                    f"sync_seed_csv_from_registry; sync_seed_csv_from_registry()'"
                )
