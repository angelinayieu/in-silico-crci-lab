"""
Test: Slice 4 — Fix Existing Paper Data (FIX-7 + FIX-8)
Purpose: Verify that:
    1. Edge evidence CSVs are v2 format (32 columns) with required fields populated
    2. Instrument evidence CSVs exist with reliability data
    3. Key curated values match spec expectations
    4. All edge_ids and instrument_ids reference valid registry entries

Definition of Done (from IMPLEMENTATION_SLICES.md):
    - instrument_evidence_v1 rows exist for both papers
    - Edge CSVs have cancer_validated, pub_year, n_treatment, n_control,
      se_derivation_method, outcome_directionality, beta_sign_convention populated
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
STRUCTURED = PROJECT_ROOT / "data" / "manual_uploads" / "structured"
TEMPLATE_V2 = PROJECT_ROOT / "data" / "templates" / "edge_evidence_template_v2.csv"

CAMPBELL_DIR = STRUCTURED / "10.1002_pon.4370"
CHERRIER_DIR = STRUCTURED / "10.1016_j.lfs.2013.08.011"

EDGE_REGISTRY = PROJECT_ROOT / "registries" / "EDGE_REGISTRY.csv"
INSTRUMENT_REGISTRY = PROJECT_ROOT / "registries" / "INSTRUMENT_REGISTRY.csv"


# ── Helpers ──────────────────────────────────────────────────────────

def _read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def _read_csv_columns(path: Path) -> list[str]:
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or [])


def _load_registry_ids(path: Path, col: str) -> set[str]:
    """Load a set of IDs from column `col` of a registry CSV."""
    with open(path) as f:
        reader = csv.DictReader(f)
        if col not in (reader.fieldnames or []):
            # Handle column name mismatches (e.g. edge_id vs edge_relation_id)
            return set()
        return {row[col] for row in reader if row.get(col)}


@pytest.fixture(scope="module")
def v2_columns() -> list[str]:
    return _read_csv_columns(TEMPLATE_V2)


@pytest.fixture(scope="module")
def campbell_edge() -> list[dict]:
    return _read_csv(CAMPBELL_DIR / "edge_evidence_template.csv")


@pytest.fixture(scope="module")
def cherrier_edge() -> list[dict]:
    return _read_csv(CHERRIER_DIR / "edge_evidence_template.csv")


@pytest.fixture(scope="module")
def campbell_instr() -> list[dict]:
    return _read_csv(CAMPBELL_DIR / "instrument_evidence_template.csv")


@pytest.fixture(scope="module")
def cherrier_instr() -> list[dict]:
    return _read_csv(CHERRIER_DIR / "instrument_evidence_template.csv")


@pytest.fixture(scope="module")
def valid_edge_ids() -> set[str]:
    return _load_registry_ids(EDGE_REGISTRY, "edge_relation_id")


@pytest.fixture(scope="module")
def valid_instrument_ids() -> set[str]:
    return _load_registry_ids(INSTRUMENT_REGISTRY, "instrument_id")


# ── 1. Edge CSVs are v2 format ──────────────────────────────────────

class TestEdgeCSVFormat:
    """Both edge CSVs must have all v2 template columns."""

    def test_campbell_has_v2_columns(self, campbell_edge, v2_columns):
        actual = set(campbell_edge[0].keys()) if campbell_edge else set()
        expected = set(v2_columns)
        missing = expected - actual
        assert not missing, f"Campbell edge CSV missing v2 columns: {missing}"

    def test_cherrier_has_v2_columns(self, cherrier_edge, v2_columns):
        actual = set(cherrier_edge[0].keys()) if cherrier_edge else set()
        expected = set(v2_columns)
        missing = expected - actual
        assert not missing, f"Cherrier edge CSV missing v2 columns: {missing}"

    def test_campbell_row_count(self, campbell_edge):
        assert len(campbell_edge) == 4, f"Expected 4 rows, got {len(campbell_edge)}"

    def test_cherrier_row_count(self, cherrier_edge):
        assert len(cherrier_edge) == 4, f"Expected 4 rows, got {len(cherrier_edge)}"


# ── 2. Required values populated ────────────────────────────────────

class TestCampbellValues:
    """Campbell 2017 edge CSV must have correct curated values."""

    REQUIRED_FIELDS = [
        "cancer_validated", "pub_year", "n_treatment", "n_control",
        "se_derivation_method", "outcome_directionality", "beta_sign_convention",
        "rob_overall", "endpoint_vs_change", "comparison_arm_label",
        "timepoint_weeks", "effect_size_context", "outcome_node_id",
    ]

    def test_required_fields_populated(self, campbell_edge):
        for i, row in enumerate(campbell_edge):
            for field in self.REQUIRED_FIELDS:
                val = row.get(field, "")
                assert val.strip(), (
                    f"Row {i} ({row.get('edge_id')}) has empty '{field}'"
                )

    def test_pub_year(self, campbell_edge):
        for row in campbell_edge:
            assert row["pub_year"] == "2017"

    def test_n_treatment(self, campbell_edge):
        for row in campbell_edge:
            assert row["n_treatment"] == "10"

    def test_n_control(self, campbell_edge):
        for row in campbell_edge:
            assert row["n_control"] == "9"

    def test_cancer_validated(self, campbell_edge):
        for row in campbell_edge:
            assert row["cancer_validated"] == "yes"

    def test_se_derivation_method(self, campbell_edge):
        for row in campbell_edge:
            assert row["se_derivation_method"] == "from_mean_diff_sd"

    def test_comparison_arm(self, campbell_edge):
        for row in campbell_edge:
            assert row["comparison_arm_label"] == "usual_care"

    def test_rob_overall(self, campbell_edge):
        for row in campbell_edge:
            assert row["rob_overall"] in {"low", "moderate", "high", "critical"}

    def test_endpoint_vs_change(self, campbell_edge):
        for row in campbell_edge:
            assert row["endpoint_vs_change"] in {"endpoint", "change_score"}

    def test_shared_control_flag(self, campbell_edge):
        for row in campbell_edge:
            assert row["shared_control_flag"] == "0"

    def test_outcome_directionality_valid(self, campbell_edge):
        for row in campbell_edge:
            assert row["outcome_directionality"] in {
                "higher_is_better", "higher_is_worse"
            }

    def test_beta_sign_convention_valid(self, campbell_edge):
        for row in campbell_edge:
            assert row["beta_sign_convention"] in {
                "positive_is_benefit", "positive_is_harm"
            }

    def test_tmt_b_is_higher_is_worse(self, campbell_edge):
        """TMT-B: lower time = better → higher_is_worse."""
        tmt_rows = [r for r in campbell_edge if r["instrument_id"] == "INST_TMT_B"]
        assert len(tmt_rows) == 1
        assert tmt_rows[0]["outcome_directionality"] == "higher_is_worse"
        assert tmt_rows[0]["beta_sign_convention"] == "positive_is_harm"

    def test_timepoint_weeks(self, campbell_edge):
        for row in campbell_edge:
            assert row["timepoint_weeks"] == "12"


class TestCherrierValues:
    """Cherrier 2013 edge CSV must have correct curated values."""

    REQUIRED_FIELDS = [
        "cancer_validated", "pub_year", "n_treatment", "n_control",
        "se_derivation_method", "outcome_directionality", "beta_sign_convention",
        "rob_overall", "endpoint_vs_change", "comparison_arm_label",
        "timepoint_weeks", "effect_size_context", "outcome_node_id",
    ]

    def test_required_fields_populated(self, cherrier_edge):
        for i, row in enumerate(cherrier_edge):
            for field in self.REQUIRED_FIELDS:
                val = row.get(field, "")
                assert val.strip(), (
                    f"Row {i} ({row.get('edge_id')}) has empty '{field}'"
                )

    def test_pub_year(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["pub_year"] == "2013"

    def test_n_treatment(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["n_treatment"] == "12"

    def test_n_control(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["n_control"] == "16"

    def test_cancer_validated(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["cancer_validated"] == "yes"

    def test_se_derivation_method(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["se_derivation_method"] == "direct"

    def test_comparison_arm(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["comparison_arm_label"] == "waitlist"

    def test_timepoint_weeks(self, cherrier_edge):
        for row in cherrier_edge:
            assert row["timepoint_weeks"] == "8"

    def test_cogcomplaints_sign_convention(self, cherrier_edge):
        """FACT-Cog PCI row: higher PCI = better, but d was sign-flipped."""
        cog = [r for r in cherrier_edge
               if r["edge_id"] == "ER_COGACTIVITY_COGCOMPLAINTS"]
        assert len(cog) == 1
        assert cog[0]["outcome_directionality"] == "higher_is_better"
        assert cog[0]["beta_sign_convention"] == "positive_is_harm"


# ── 3. Instrument evidence CSVs ─────────────────────────────────────

class TestInstrumentEvidence:
    """Instrument evidence CSVs must exist with reliability data."""

    def test_campbell_instrument_exists(self):
        p = CAMPBELL_DIR / "instrument_evidence_template.csv"
        assert p.exists(), f"Missing: {p}"

    def test_cherrier_instrument_exists(self):
        p = CHERRIER_DIR / "instrument_evidence_template.csv"
        assert p.exists(), f"Missing: {p}"

    def test_campbell_has_rows(self, campbell_instr):
        assert len(campbell_instr) >= 4, (
            f"Expected ≥4 instrument rows for Campbell, got {len(campbell_instr)}"
        )

    def test_cherrier_has_rows(self, cherrier_instr):
        assert len(cherrier_instr) >= 3, (
            f"Expected ≥3 instrument rows for Cherrier, got {len(cherrier_instr)}"
        )

    def test_campbell_reliability_populated(self, campbell_instr):
        for row in campbell_instr:
            val = float(row["reliability_value"])
            assert 0.0 < val <= 1.0, (
                f"{row['instrument_id']} reliability {val} out of range"
            )

    def test_cherrier_reliability_populated(self, cherrier_instr):
        for row in cherrier_instr:
            val = float(row["reliability_value"])
            assert 0.0 < val <= 1.0, (
                f"{row['instrument_id']} reliability {val} out of range"
            )


# ── 4. Registry referential integrity ───────────────────────────────

class TestRegistryIntegrity:
    """All IDs in paper CSVs must exist in registries."""

    def test_campbell_edge_ids_valid(self, campbell_edge, valid_edge_ids):
        for row in campbell_edge:
            eid = row["edge_id"]
            assert eid in valid_edge_ids, (
                f"Campbell edge_id '{eid}' not in EDGE_REGISTRY"
            )

    def test_cherrier_edge_ids_valid(self, cherrier_edge, valid_edge_ids):
        for row in cherrier_edge:
            eid = row["edge_id"]
            assert eid in valid_edge_ids, (
                f"Cherrier edge_id '{eid}' not in EDGE_REGISTRY"
            )

    def test_campbell_instrument_ids_valid(self, campbell_edge, valid_instrument_ids):
        for row in campbell_edge:
            iid = row.get("instrument_id", "")
            if iid:
                assert iid in valid_instrument_ids, (
                    f"Campbell instrument_id '{iid}' not in INSTRUMENT_REGISTRY"
                )

    def test_cherrier_instrument_ids_valid(self, cherrier_edge, valid_instrument_ids):
        for row in cherrier_edge:
            iid = row.get("instrument_id", "")
            if iid:
                assert iid in valid_instrument_ids, (
                    f"Cherrier instrument_id '{iid}' not in INSTRUMENT_REGISTRY"
                )

    def test_campbell_instr_csv_ids_valid(self, campbell_instr, valid_instrument_ids):
        for row in campbell_instr:
            iid = row["instrument_id"]
            assert iid in valid_instrument_ids, (
                f"Campbell instrument CSV instrument_id '{iid}' not in registry"
            )

    def test_cherrier_instr_csv_ids_valid(self, cherrier_instr, valid_instrument_ids):
        for row in cherrier_instr:
            iid = row["instrument_id"]
            assert iid in valid_instrument_ids, (
                f"Cherrier instrument CSV instrument_id '{iid}' not in registry"
            )


# ── 5. Outcome node ID matches edge registry target ─────────────────

class TestOutcomeNodeConsistency:
    """outcome_node_id must match the edge's target node in EDGE_REGISTRY."""

    @pytest.fixture(scope="class")
    def edge_target_map(self) -> dict[str, str]:
        """Map edge_relation_id → target_node_id from EDGE_REGISTRY."""
        result = {}
        with open(EDGE_REGISTRY) as f:
            for row in csv.DictReader(f):
                result[row["edge_relation_id"]] = row["target_node_id"]
        return result

    def test_campbell_outcome_nodes(self, campbell_edge, edge_target_map):
        for row in campbell_edge:
            eid = row["edge_id"]
            expected = edge_target_map.get(eid)
            assert row["outcome_node_id"] == expected, (
                f"{eid}: outcome_node_id={row['outcome_node_id']} "
                f"but EDGE_REGISTRY target={expected}"
            )

    def test_cherrier_outcome_nodes(self, cherrier_edge, edge_target_map):
        for row in cherrier_edge:
            eid = row["edge_id"]
            expected = edge_target_map.get(eid)
            assert row["outcome_node_id"] == expected, (
                f"{eid}: outcome_node_id={row['outcome_node_id']} "
                f"but EDGE_REGISTRY target={expected}"
            )
