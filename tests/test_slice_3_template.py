"""
Test: Slice 3 — Expand the CSV Template (FIX-3)
Purpose: Verify that:
    1. edge_evidence_template_v2.csv exists with all required columns
    2. All 7-layer fields are present (study_design, cancer_validated, rob_overall, pub_year, etc.)
    3. Sign convention fields are present (outcome_directionality, beta_sign_convention)
    4. Dedup identity fields are present (comparison_arm_label, endpoint_vs_change, etc.)
    5. SE derivation fields are present (ci_low, ci_high, p_value, sd_treatment, sd_control)

Definition of Done (from IMPLEMENTATION_SLICES.md):
    test_template_columns: Template v2 CSV header has all required columns
    including outcome_directionality and beta_sign_convention.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
TEMPLATE_V1 = PROJECT_ROOT / "data" / "templates" / "edge_evidence_template.csv"
TEMPLATE_V2 = PROJECT_ROOT / "data" / "templates" / "edge_evidence_template_v2.csv"


class TestTemplateV2Exists:
    """The v2 template must exist."""

    def test_file_exists(self):
        assert TEMPLATE_V2.exists(), f"Missing: {TEMPLATE_V2}"

    def test_is_valid_csv(self):
        """Should be parseable as CSV."""
        with open(TEMPLATE_V2) as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            assert len(reader.fieldnames) > 0


class TestTemplateV2Columns:
    """The v2 template must have all required columns."""

    @pytest.fixture
    def columns(self) -> set[str]:
        with open(TEMPLATE_V2) as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            return set(reader.fieldnames)

    # --- Original 12 columns preserved ---
    @pytest.mark.parametrize("col", [
        "doi", "edge_id", "beta_raw", "se_raw", "effect_type_original",
        "effect_size_type", "sample_size", "study_design", "cancer_type",
        "treatment_phase", "instrument_id", "confidence_note",
    ])
    def test_original_columns_preserved(self, columns, col):
        """All original v1 columns must still be present."""
        assert col in columns, f"Original column '{col}' missing from v2 template"

    # --- 7-Layer SE system fields ---
    def test_has_cancer_validated(self, columns):
        """L4 needs cancer_validated."""
        assert "cancer_validated" in columns

    def test_has_rob_overall(self, columns):
        """L5 needs rob_overall."""
        assert "rob_overall" in columns

    def test_has_pub_year(self, columns):
        """L7 needs pub_year."""
        assert "pub_year" in columns

    # --- SE derivation fields ---
    def test_has_ci_bounds(self, columns):
        assert "ci_low" in columns
        assert "ci_high" in columns

    def test_has_p_value(self, columns):
        assert "p_value" in columns

    def test_has_per_arm_n(self, columns):
        assert "n_treatment" in columns
        assert "n_control" in columns

    def test_has_per_arm_sd(self, columns):
        assert "sd_treatment" in columns
        assert "sd_control" in columns

    def test_has_se_derivation_method(self, columns):
        assert "se_derivation_method" in columns

    # --- Sign convention fields (new in review) ---
    def test_has_outcome_directionality(self, columns):
        """Required to flip signs for instruments where lower = better."""
        assert "outcome_directionality" in columns

    def test_has_beta_sign_convention(self, columns):
        """Required to establish canonical sign: positive = benefit."""
        assert "beta_sign_convention" in columns

    # --- Audit and dedup fields ---
    def test_has_comparison_arm_label(self, columns):
        assert "comparison_arm_label" in columns

    def test_has_endpoint_vs_change(self, columns):
        assert "endpoint_vs_change" in columns

    def test_has_shared_control_flag(self, columns):
        assert "shared_control_flag" in columns

    def test_has_covariates_adjusted(self, columns):
        assert "covariates_adjusted" in columns

    # --- Dedup identity fields (from Slice 0, Gap 3) ---
    def test_has_timepoint_weeks(self, columns):
        """Identity hash uses timepoint_weeks."""
        assert "timepoint_weeks" in columns

    def test_has_effect_size_context(self, columns):
        """Identity hash uses effect_size_context (BETWEEN_GROUP / WITHIN_GROUP)."""
        assert "effect_size_context" in columns

    def test_has_outcome_node_id(self, columns):
        """Identity hash uses outcome_node_id."""
        assert "outcome_node_id" in columns


class TestTemplateV2BackwardCompatibility:
    """V2 must be a strict superset of v1 columns."""

    def test_v2_superset_of_v1(self):
        """Every column in v1 must also appear in v2."""
        if not TEMPLATE_V1.exists():
            pytest.skip("v1 template not found (already archived?)")

        with open(TEMPLATE_V1) as f:
            v1_cols = set(csv.DictReader(f).fieldnames or [])
        with open(TEMPLATE_V2) as f:
            v2_cols = set(csv.DictReader(f).fieldnames or [])

        missing = v1_cols - v2_cols
        assert not missing, f"v2 is missing v1 columns: {missing}"
