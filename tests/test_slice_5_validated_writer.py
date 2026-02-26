"""
Test: Slice 5 — Unified Evidence Writer with Validation (FIX-4)
Purpose: Verify that:
    1. validation.py rejects bad rows and accepts good ones
    2. standardization.py converts effect sizes correctly
    3. standardization.py flips signs per outcome_directionality
    4. standardization.py derives SE via cascade
    5. persistence.py computes identity hashes and writes rows
    6. __init__.py write_evidence_row() orchestrates the pipeline
    7. Invalid rows are quarantined, not silently dropped

Definition of Done (from IMPLEMENTATION_SLICES.md):
    - All evidence writes go through validated_evidence_writer
    - Bad rows quarantined with reasons
    - Effect sizes standardized to Cohen's d
    - SE derived via cascade
    - Layer inputs computed from vocab.py
"""
from __future__ import annotations

import json
import math
from unittest.mock import MagicMock, patch

import pytest

# ── Test helpers ─────────────────────────────────────────────────────

def _good_row() -> dict:
    """A fully valid evidence row with all required fields."""
    return {
        "doi": "10.1002/pon.4370",
        "study_id": "doi:10.1002/pon.4370",
        "edge_id": "ER_ACTIVITY_PROC_SPEED",
        "edge_relation_id": "ER_ACTIVITY_PROC_SPEED",
        "beta_raw": "-1.56",
        "se_raw": "0.53",
        "effect_type_original": "cohen_d",
        "effect_size_type": "BETWEEN_GROUP",
        "effect_size_context": "BETWEEN_GROUP",
        "sample_size": "19",
        "study_design": "RCT",
        "cancer_type": "breast",
        "treatment_phase": "early_recovery",
        "instrument_id": "INST_TMT_B",
        "confidence_note": "test conversion",
        "n_treatment": "10",
        "n_control": "9",
        "cancer_validated": "yes",
        "rob_overall": "moderate",
        "pub_year": "2017",
        "endpoint_vs_change": "change_score",
        "comparison_arm_label": "usual_care",
        "se_derivation_method": "from_mean_diff_sd",
        "shared_control_flag": "0",
        "outcome_directionality": "higher_is_worse",
        "beta_sign_convention": "positive_is_harm",
        "timepoint_weeks": "12",
        "outcome_node_id": "NODE_COG_PROC_SPEED",
    }


# ═══════════════════════════════════════════════════════════════
#  1. Validation Module Tests
# ═══════════════════════════════════════════════════════════════

class TestValidation:
    """Tests for crci.extraction.validated_writer.validation."""

    def test_good_row_passes(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        is_valid, errors = validate_evidence_row(row, session=None)
        assert is_valid, f"Good row should pass validation but got errors: {errors}"
        assert errors == []

    def test_missing_study_design_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["study_design"]
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("study_design" in e for e in errors)

    def test_bad_study_design_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["study_design"] = "telepathy_trial"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("study_design" in e for e in errors)

    def test_missing_effect_type_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["effect_type_original"]
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("effect_type" in e for e in errors)

    def test_bad_effect_type_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["effect_type_original"] = "psychic_distance"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_zero_sample_size_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["sample_size"] = "0"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("sample_size" in e for e in errors)

    def test_negative_sample_size_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["sample_size"] = "-5"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_no_se_no_ci_no_p_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["se_raw"]
        # No CI or p-value either
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("SE" in e or "se" in e.lower() or "precision" in e.lower() for e in errors)

    def test_se_raw_present_passes_precision_check(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        # se_raw is present → should pass
        is_valid, errors = validate_evidence_row(row, session=None)
        assert is_valid

    def test_ci_instead_of_se_passes(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["se_raw"]
        row["ci_low"] = "-2.5"
        row["ci_high"] = "-0.5"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert is_valid, f"CI should satisfy precision requirement: {errors}"

    def test_p_value_instead_of_se_passes(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["se_raw"]
        row["p_value"] = "0.05"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert is_valid, f"p-value should satisfy precision requirement: {errors}"

    def test_bad_pub_year_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["pub_year"] = "1850"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_missing_cancer_type_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["cancer_type"]
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_bad_cancer_type_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["cancer_type"] = "unicorn_cancer"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_missing_treatment_phase_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        del row["treatment_phase"]
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_bad_rob_overall_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["rob_overall"] = "fantastic"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid

    def test_mean_diff_without_sds_fails(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["effect_type_original"] = "mean_diff"
        # Deliberately no sd_treatment / sd_control
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert any("sd" in e.lower() for e in errors)

    def test_mean_diff_with_sds_passes(self):
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["effect_type_original"] = "mean_diff"
        row["sd_treatment"] = "1.5"
        row["sd_control"] = "1.8"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert is_valid, f"mean_diff with SDs should pass: {errors}"

    def test_collects_multiple_errors(self):
        """Validation should collect ALL errors, not just the first."""
        from crci.extraction.validated_writer.validation import validate_evidence_row
        row = _good_row()
        row["study_design"] = "bad_design"
        row["cancer_type"] = "bad_cancer"
        row["sample_size"] = "0"
        is_valid, errors = validate_evidence_row(row, session=None)
        assert not is_valid
        assert len(errors) >= 3, f"Should collect multiple errors, got {len(errors)}: {errors}"


# ═══════════════════════════════════════════════════════════════
#  2. Standardization Module Tests
# ═══════════════════════════════════════════════════════════════

class TestEffectSizeConversion:
    """Tests for standardize_effect_size()."""

    def test_cohen_d_passthrough(self):
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        result = standardize_effect_size(row)
        assert float(result["harmonized_beta"]) == pytest.approx(-1.56)
        assert result["conversion_formula"] == "passthrough"

    def test_mean_diff_to_cohen_d(self):
        """d = mean_diff / SD_pooled. SD_pooled = sqrt((sd1² + sd2²)/2)."""
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        row["effect_type_original"] = "mean_diff"
        row["beta_raw"] = "3.0"  # mean difference
        row["sd_treatment"] = "4.0"
        row["sd_control"] = "4.0"
        row["se_raw"] = "0.5"
        result = standardize_effect_size(row)
        # SD_pooled = sqrt((16+16)/2) = 4.0
        # d = 3.0/4.0 = 0.75
        assert float(result["harmonized_beta"]) == pytest.approx(0.75)
        assert result["conversion_formula"] == "mean_diff_to_cohen_d"

    def test_partial_eta_sq_to_cohen_d(self):
        """d = 2 * sqrt(η²/(1-η²))."""
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        row["effect_type_original"] = "partial_eta_sq"
        row["beta_raw"] = "0.35"
        row["se_raw"] = "0.1"
        result = standardize_effect_size(row)
        # d = 2 * sqrt(0.35/0.65) = 2 * sqrt(0.5385) = 2 * 0.7338 = 1.4677
        expected_d = 2.0 * math.sqrt(0.35 / (1.0 - 0.35))
        assert float(result["harmonized_beta"]) == pytest.approx(expected_d, rel=1e-3)
        assert result["conversion_formula"] == "partial_eta_sq_to_cohen_d"

    def test_odds_ratio_to_cohen_d(self):
        """d = ln(OR) * sqrt(3) / π."""
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        row["effect_type_original"] = "odds_ratio"
        row["beta_raw"] = "2.5"
        row["se_raw"] = "0.3"
        result = standardize_effect_size(row)
        expected_d = math.log(2.5) * math.sqrt(3) / math.pi
        assert float(result["harmonized_beta"]) == pytest.approx(expected_d, rel=1e-3)
        assert result["conversion_formula"] == "odds_ratio_to_cohen_d"

    def test_r_correlation_to_cohen_d(self):
        """d = 2r / sqrt(1-r²)."""
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        row["effect_type_original"] = "r_correlation"
        row["beta_raw"] = "0.5"
        row["se_raw"] = "0.1"
        result = standardize_effect_size(row)
        expected_d = 2 * 0.5 / math.sqrt(1 - 0.25)
        assert float(result["harmonized_beta"]) == pytest.approx(expected_d, rel=1e-3)
        assert result["conversion_formula"] == "r_to_cohen_d"


class TestHedgesG:
    """Hedges' g small-sample correction must be computed."""

    def test_hedges_g_computed(self):
        from crci.extraction.validated_writer.standardization import standardize_effect_size
        row = _good_row()
        row["n_treatment"] = "10"
        row["n_control"] = "9"
        result = standardize_effect_size(row)
        n1, n2 = 10, 9
        d = -1.56
        # g = d * (1 - 3/(4*(n1+n2) - 9))
        correction = 1 - 3 / (4 * (n1 + n2) - 9)
        expected_g = d * correction
        assert float(result["hedges_g"]) == pytest.approx(expected_g, rel=1e-3)


class TestSignHarmonization:
    """Tests for harmonize_sign()."""

    def test_higher_is_worse_flips_positive(self):
        """TMT-B: higher = worse. Positive raw d (worse) → negative harmonized (harm)."""
        from crci.extraction.validated_writer.standardization import harmonize_sign
        row = {
            "harmonized_beta": 1.5,
            "harmonized_se": 0.5,
            "outcome_directionality": "higher_is_worse",
            "beta_sign_convention": "positive_is_harm",
        }
        result = harmonize_sign(row)
        assert result["harmonized_beta"] == pytest.approx(-1.5)
        assert result["sign_flipped"] is True

    def test_higher_is_better_no_flip(self):
        """HVLT-R: higher = better. Positive d = benefit → no flip."""
        from crci.extraction.validated_writer.standardization import harmonize_sign
        row = {
            "harmonized_beta": 0.7,
            "harmonized_se": 0.4,
            "outcome_directionality": "higher_is_better",
            "beta_sign_convention": "positive_is_benefit",
        }
        result = harmonize_sign(row)
        assert result["harmonized_beta"] == pytest.approx(0.7)
        assert result["sign_flipped"] is False


class TestSEDerivation:
    """Tests for derive_se()."""

    def test_direct_se_level_1(self):
        from crci.extraction.validated_writer.standardization import derive_se
        row = _good_row()
        result = derive_se(row)
        assert float(result["harmonized_se"]) == pytest.approx(0.53)
        assert result["se_derivation_level"] == "L1_DIRECT"

    def test_se_from_ci_level_2(self):
        """SE = (CI_high - CI_low) / (2 × 1.96)."""
        from crci.extraction.validated_writer.standardization import derive_se
        row = _good_row()
        del row["se_raw"]
        row["ci_low"] = "-2.6"
        row["ci_high"] = "-0.5"
        result = derive_se(row)
        expected_se = ((-0.5) - (-2.6)) / (2 * 1.96)
        assert float(result["harmonized_se"]) == pytest.approx(expected_se, rel=1e-3)
        assert result["se_derivation_level"] == "L2_FROM_CI"

    def test_se_from_p_value_level_3(self):
        """SE = |beta| / z_from_p."""
        from crci.extraction.validated_writer.standardization import derive_se
        row = _good_row()
        del row["se_raw"]
        row["p_value"] = "0.05"
        result = derive_se(row)
        assert result["se_derivation_level"] == "L3_FROM_P"
        assert float(result["harmonized_se"]) > 0


class TestLayerInputs:
    """Tests for compute_layer_inputs()."""

    def test_study_design_mapped(self):
        """RCT with N=19 → small_rct_default."""
        from crci.extraction.validated_writer.standardization import compute_layer_inputs
        row = _good_row()
        result = compute_layer_inputs(row)
        assert result["study_design_canonical"] == "small_rct_default"

    def test_cancer_validation_mapped(self):
        """cancer_validated=yes → validated_cancer."""
        from crci.extraction.validated_writer.standardization import compute_layer_inputs
        row = _good_row()
        result = compute_layer_inputs(row)
        assert result["cancer_validation_canonical"] == "validated_cancer"

    def test_rob_mapped(self):
        """rob_overall=moderate → MODERATE."""
        from crci.extraction.validated_writer.standardization import compute_layer_inputs
        row = _good_row()
        result = compute_layer_inputs(row)
        assert result["rob_grade_canonical"] == "MODERATE"


# ═══════════════════════════════════════════════════════════════
#  3. Persistence Module Tests
# ═══════════════════════════════════════════════════════════════

class TestPersistence:
    """Tests for crci.extraction.validated_writer.persistence."""

    def test_identity_hash_deterministic(self):
        from crci.extraction.validated_writer.persistence import compute_writer_identity
        row = _good_row()
        h1 = compute_writer_identity(row)
        h2 = compute_writer_identity(row)
        assert h1 == h2
        assert h1.startswith("ler_")

    def test_identity_hash_differs_on_instrument(self):
        from crci.extraction.validated_writer.persistence import compute_writer_identity
        row1 = _good_row()
        row2 = _good_row()
        row2["instrument_id"] = "INST_COWAT"
        assert compute_writer_identity(row1) != compute_writer_identity(row2)

    def test_identity_hash_differs_on_timepoint(self):
        from crci.extraction.validated_writer.persistence import compute_writer_identity
        row1 = _good_row()
        row2 = _good_row()
        row2["timepoint_weeks"] = "24"
        assert compute_writer_identity(row1) != compute_writer_identity(row2)

    def test_quarantine_stores_errors(self):
        from crci.extraction.validated_writer.persistence import quarantine_row
        mock_session = MagicMock()
        row = _good_row()
        errors = ["bad study_design", "missing SE"]
        qid = quarantine_row(mock_session, row, errors, source="test")
        assert qid.startswith("quar_")
        # Should have called session.add
        mock_session.add.assert_called_once()
        # Check the object added
        obj = mock_session.add.call_args[0][0]
        assert obj.quarantine_reason == "validation_failure"
        parsed = json.loads(obj.validation_errors)
        assert len(parsed) == 2


# ═══════════════════════════════════════════════════════════════
#  4. Integration: write_evidence_row()
# ═══════════════════════════════════════════════════════════════

class TestWriteEvidenceRow:
    """Integration tests for the top-level entry point."""

    def _make_session_mock(self):
        """Create a mock session that handles FK checks correctly.

        Returns None for EdgeEvidence lookups (no existing row → INSERT),
        but returns a truthy MagicMock for FK checks (EdgeRelationsDefinition,
        InstrumentDefinition) so validation passes.
        """
        from crci.shared.models.tables import EdgeEvidence

        mock_session = MagicMock()

        def get_side_effect(model_class, pk):
            if model_class is EdgeEvidence:
                return None  # no existing row → INSERT
            return MagicMock()  # FK checks → "found"

        mock_session.get.side_effect = get_side_effect
        return mock_session

    def test_valid_row_returns_ler_id(self):
        from crci.extraction.validated_writer import write_evidence_row
        mock_session = self._make_session_mock()
        row = _good_row()
        result = write_evidence_row(mock_session, row, source="test")
        assert result is not None
        assert result.startswith("ler_")

    def test_invalid_row_returns_none_and_quarantines(self):
        from crci.extraction.validated_writer import write_evidence_row
        mock_session = MagicMock()
        row = _good_row()
        row["study_design"] = "telepathy_trial"
        result = write_evidence_row(mock_session, row, source="test")
        assert result is None
        # Should have called session.add for quarantine
        mock_session.add.assert_called()

    def test_pipeline_order(self):
        """Verify validate → standardize → sign → SE → layer_inputs → persist."""
        from crci.extraction.validated_writer import write_evidence_row
        from crci.shared.models.tables import EdgeEvidence
        mock_session = self._make_session_mock()
        row = _good_row()
        row["effect_type_original"] = "cohen_d"
        result = write_evidence_row(mock_session, row, source="test")
        assert result is not None
        # Find the EdgeEvidence add call (not the quarantine)
        add_calls = mock_session.add.call_args_list
        evidence_adds = [
            c for c in add_calls
            if isinstance(c[0][0], EdgeEvidence)
        ]
        assert len(evidence_adds) == 1
        added_obj = evidence_adds[0][0][0]
        assert added_obj.harmonized_beta is not None
        assert added_obj.harmonized_se is not None
        assert added_obj.se_derivation_level is not None
