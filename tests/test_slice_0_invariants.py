"""
Test: Slice 0 Pre-Implementation Invariants
Purpose: Verify the three invariants from IMPLEMENTATION_SLICES.md Slice 0
    are locked before any other slice proceeds:
    1. Vocab mapping — study_design, rob, cancer_validation all resolve correctly
    2. Quarantine — ORM model exists and can be instantiated
    3. Dedup identity — same study+edge with different instruments → different ler_ids
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from crci.shared.vocab import (
    CANCER_TYPE_VOCAB,
    CANCER_VALIDATION_MAP,
    EFFECT_SIZE_CONTEXT_VOCAB,
    EFFECT_TYPE_VOCAB,
    ROB_TO_GRADE_MAP,
    STUDY_DESIGN_MAP,
    TREATMENT_PHASE_VOCAB,
    resolve_cancer_validation,
    resolve_rob_to_grade,
    resolve_study_design,
    validate_cancer_type,
    validate_effect_size_context,
    validate_effect_type,
    validate_treatment_phase,
)
from crci.shared.config import (
    DESIGN_MULTIPLIERS,
    GRADE_MULTIPLIERS,
    SCALE_MULTIPLIERS,
    SMALL_RCT_N_THRESHOLD,
)
from crci.shared.study_identity import (
    EVIDENCE_IDENTITY_FIELDS,
    compute_evidence_identity,
)


# ═══════════════════════════════════════════════════════════════
#  Gap 1 Tests: Canonical Controlled Vocabulary
# ═══════════════════════════════════════════════════════════════


class TestStudyDesignMapping:
    """Every value in STUDY_DESIGN_MAP must map to a valid DESIGN_MULTIPLIERS key."""

    def test_all_mapped_values_exist_in_config(self):
        """Every canonical output of STUDY_DESIGN_MAP must be a key in DESIGN_MULTIPLIERS."""
        canonical_values = set(STUDY_DESIGN_MAP.values())
        for value in canonical_values:
            assert value in DESIGN_MULTIPLIERS, (
                f"STUDY_DESIGN_MAP produces '{value}' which is not in DESIGN_MULTIPLIERS. "
                f"Valid keys: {sorted(DESIGN_MULTIPLIERS.keys())}"
            )

    def test_rct_large_sample(self):
        """RCT with N > 200 → large_rct."""
        assert resolve_study_design("RCT", n_total=500) == "large_rct"

    def test_rct_small_sample(self):
        """RCT with N ≤ 200 → small_rct_default."""
        assert resolve_study_design("RCT", n_total=19) == "small_rct_default"

    def test_rct_boundary(self):
        """RCT with N == 200 (boundary) → small_rct_default."""
        assert resolve_study_design("RCT", n_total=SMALL_RCT_N_THRESHOLD) == "small_rct_default"

    def test_rct_boundary_plus_one(self):
        """RCT with N == 201 → large_rct."""
        assert resolve_study_design("RCT", n_total=SMALL_RCT_N_THRESHOLD + 1) == "large_rct"

    def test_rct_no_sample_size(self):
        """RCT with no N → large_rct (conservative — no reclassification)."""
        assert resolve_study_design("RCT") == "large_rct"

    def test_cohort(self):
        """cohort → well_adjusted_cohort."""
        assert resolve_study_design("cohort") == "well_adjusted_cohort"

    def test_cross_sectional_defaults_unadjusted(self):
        """Plain 'cross_sectional' → cross_sectional_unadjusted."""
        assert resolve_study_design("cross_sectional") == "cross_sectional_unadjusted"

    def test_cross_sectional_adjusted(self):
        """cross_sectional_adjusted → cross_sectional_adjusted."""
        assert resolve_study_design("cross_sectional_adjusted") == "cross_sectional_adjusted"

    def test_animal(self):
        """animal → animal_in_vivo."""
        assert resolve_study_design("animal") == "animal_in_vivo"

    def test_unknown_design_raises(self):
        """Unknown study_design must raise ValueError, not silently default."""
        with pytest.raises(ValueError, match="Unknown study_design"):
            resolve_study_design("bogus_design")

    def test_idempotent_canonical_keys(self):
        """Internal keys must map to themselves."""
        for key in DESIGN_MULTIPLIERS:
            if key in STUDY_DESIGN_MAP:
                assert resolve_study_design(key) == key, (
                    f"Canonical key '{key}' should map to itself"
                )

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        assert resolve_study_design("  RCT  ", n_total=500) == "large_rct"


class TestRobToGradeMapping:
    """Every value in ROB_TO_GRADE_MAP must map to a valid GRADE_MULTIPLIERS key."""

    def test_all_mapped_values_exist_in_config(self):
        """Every canonical output must be a key in GRADE_MULTIPLIERS."""
        canonical_values = set(ROB_TO_GRADE_MAP.values())
        for value in canonical_values:
            assert value in GRADE_MULTIPLIERS, (
                f"ROB_TO_GRADE_MAP produces '{value}' which is not in GRADE_MULTIPLIERS. "
                f"Valid keys: {sorted(GRADE_MULTIPLIERS.keys())}"
            )

    def test_low_rob_is_high_grade(self):
        """Low risk-of-bias = HIGH quality."""
        assert resolve_rob_to_grade("low") == "HIGH"

    def test_high_rob_is_low_grade(self):
        """High risk-of-bias = LOW quality."""
        assert resolve_rob_to_grade("high") == "LOW"

    def test_critical_is_very_low(self):
        """Critical risk-of-bias = VERY_LOW quality."""
        assert resolve_rob_to_grade("critical") == "VERY_LOW"

    def test_unknown_rob_raises(self):
        """Unknown rob level must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown rob_overall"):
            resolve_rob_to_grade("excellent")

    def test_idempotent_grade_keys(self):
        """Internal GRADE keys must map to themselves."""
        for key in GRADE_MULTIPLIERS:
            assert resolve_rob_to_grade(key) == key


class TestCancerValidationMapping:
    """Every value in CANCER_VALIDATION_MAP must map to a valid SCALE_MULTIPLIERS key."""

    def test_all_mapped_values_exist_in_config(self):
        """Every canonical output must be a key in SCALE_MULTIPLIERS."""
        canonical_values = set(CANCER_VALIDATION_MAP.values())
        for value in canonical_values:
            assert value in SCALE_MULTIPLIERS, (
                f"CANCER_VALIDATION_MAP produces '{value}' which is not in SCALE_MULTIPLIERS."
            )

    def test_yes_is_validated(self):
        assert resolve_cancer_validation("yes") == "validated_cancer"

    def test_no_is_general(self):
        assert resolve_cancer_validation("no") == "general_population"

    def test_unknown_is_used(self):
        assert resolve_cancer_validation("unknown") == "used_cancer"

    def test_case_insensitive(self):
        assert resolve_cancer_validation("YES") == "validated_cancer"
        assert resolve_cancer_validation("True") == "validated_cancer"

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError, match="Unknown cancer_validated"):
            resolve_cancer_validation("maybe")


class TestClosedVocabularies:
    """Closed vocabulary sets must reject invalid values."""

    def test_valid_effect_type(self):
        assert validate_effect_type("cohen_d") == "cohen_d"

    def test_invalid_effect_type(self):
        with pytest.raises(ValueError, match="Unknown effect_type"):
            validate_effect_type("pearson_r")

    def test_valid_effect_size_context(self):
        assert validate_effect_size_context("BETWEEN_GROUP") == "BETWEEN_GROUP"

    def test_invalid_effect_size_context(self):
        with pytest.raises(ValueError, match="Unknown effect_size_context"):
            validate_effect_size_context("COMBINED")

    def test_valid_treatment_phase(self):
        assert validate_treatment_phase("active_treatment") == "active_treatment"

    def test_invalid_treatment_phase(self):
        with pytest.raises(ValueError, match="Unknown treatment_phase"):
            validate_treatment_phase("pre_treatment")

    def test_valid_cancer_type(self):
        assert validate_cancer_type("breast") == "breast"

    def test_cancer_type_case_insensitive(self):
        assert validate_cancer_type("BREAST") == "breast"

    def test_invalid_cancer_type(self):
        with pytest.raises(ValueError, match="Unknown cancer_type"):
            validate_cancer_type("liver")


# ═══════════════════════════════════════════════════════════════
#  Gap 2 Tests: Evidence Quarantine ORM Model
# ═══════════════════════════════════════════════════════════════


class TestQuarantineModel:
    """Verify the quarantine ORM model can be instantiated."""

    def test_model_import(self):
        """EvidenceValidationQuarantine should be importable."""
        from crci.shared.models.tables import EvidenceValidationQuarantine
        assert EvidenceValidationQuarantine.__tablename__ == "evidence_validation_quarantine_v1"

    def test_model_instantiation(self):
        """Should be able to create an instance with required fields."""
        from crci.shared.models.tables import EvidenceValidationQuarantine

        row = EvidenceValidationQuarantine(
            quarantine_id=f"q_{uuid.uuid4().hex[:12]}",
            study_id="doi:10.1234/test",
            edge_relation_id="E001",
            source_path="manual_csv",
            raw_payload_json=json.dumps({"study_design": None, "effect_value": 0.5}),
            validation_errors=json.dumps(["missing_study_design"]),
            quarantine_reason="missing_study_design",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert row.quarantine_reason == "missing_study_design"
        assert row.resolved_at is None

    def test_model_has_required_columns(self):
        """Model must have all columns defined in Slice 0 spec."""
        from crci.shared.models.tables import EvidenceValidationQuarantine

        required_columns = {
            "quarantine_id", "study_id", "edge_relation_id",
            "source_path", "raw_payload_json", "validation_errors",
            "quarantine_reason", "created_at", "resolved_at", "resolved_by",
        }
        model_columns = {c.name for c in EvidenceValidationQuarantine.__table__.columns}
        missing = required_columns - model_columns
        assert not missing, f"Missing columns: {missing}"


# ═══════════════════════════════════════════════════════════════
#  Gap 3 Tests: Evidence Row Dedup Identity
# ═══════════════════════════════════════════════════════════════


class TestEvidenceIdentity:
    """Verify deterministic identity hashing for evidence rows."""

    BASE_ROW = {
        "study_id": "doi:10.1234/test",
        "edge_relation_id": "E001",
        "instrument_id": "HVLT",
        "timepoint_weeks": "12",
        "comparison_arm_label": "usual_care",
        "effect_size_context": "BETWEEN_GROUP",
        "endpoint_vs_change": "endpoint",
        "outcome_node_id": "N_COG",
    }

    def test_deterministic(self):
        """Same row must produce the same ler_id every time."""
        id1 = compute_evidence_identity(self.BASE_ROW)
        id2 = compute_evidence_identity(self.BASE_ROW)
        assert id1 == id2

    def test_prefix(self):
        """ler_id must start with 'ler_' prefix."""
        ler_id = compute_evidence_identity(self.BASE_ROW)
        assert ler_id.startswith("ler_")

    def test_length(self):
        """ler_id must be 'ler_' + 16 hex chars = 20 chars total."""
        ler_id = compute_evidence_identity(self.BASE_ROW)
        assert len(ler_id) == 20  # "ler_" (4) + 16 hex chars

    def test_different_instrument_different_id(self):
        """Same study+edge, different instrument → different ler_id."""
        row_hvlt = dict(self.BASE_ROW, instrument_id="HVLT")
        row_cowat = dict(self.BASE_ROW, instrument_id="COWAT")
        assert compute_evidence_identity(row_hvlt) != compute_evidence_identity(row_cowat)

    def test_different_timepoint_different_id(self):
        """Same study+edge+instrument, different timepoint → different ler_id."""
        row_4w = dict(self.BASE_ROW, timepoint_weeks="4")
        row_12w = dict(self.BASE_ROW, timepoint_weeks="12")
        assert compute_evidence_identity(row_4w) != compute_evidence_identity(row_12w)

    def test_different_comparison_arm_different_id(self):
        """Different comparison arms → different ler_id."""
        row_uc = dict(self.BASE_ROW, comparison_arm_label="usual_care")
        row_ac = dict(self.BASE_ROW, comparison_arm_label="active_control")
        assert compute_evidence_identity(row_uc) != compute_evidence_identity(row_ac)

    def test_different_context_different_id(self):
        """BETWEEN_GROUP vs WITHIN_GROUP → different ler_id."""
        row_bg = dict(self.BASE_ROW, effect_size_context="BETWEEN_GROUP")
        row_wg = dict(self.BASE_ROW, effect_size_context="WITHIN_GROUP")
        assert compute_evidence_identity(row_bg) != compute_evidence_identity(row_wg)

    def test_same_row_reimport_same_id(self):
        """Re-importing the same row with an updated SE should keep the same ler_id.

        Non-identity fields (like se, effect_value) do NOT affect the hash.
        """
        row_v1 = dict(self.BASE_ROW, effect_value=0.5, se=0.1)
        row_v2 = dict(self.BASE_ROW, effect_value=0.5, se=0.15)  # updated SE
        assert compute_evidence_identity(row_v1) == compute_evidence_identity(row_v2)

    def test_missing_fields_use_empty_string(self):
        """Missing identity fields default to empty string, not None."""
        sparse_row = {"study_id": "doi:10.1234/test", "edge_relation_id": "E001"}
        ler_id = compute_evidence_identity(sparse_row)
        assert ler_id.startswith("ler_")
        assert len(ler_id) == 20

    def test_identity_fields_tuple_defined(self):
        """EVIDENCE_IDENTITY_FIELDS should list exactly 8 fields."""
        assert len(EVIDENCE_IDENTITY_FIELDS) == 8

    def test_all_identity_fields_present_in_base_row(self):
        """BASE_ROW must contain all 8 identity fields for test validity."""
        for field in EVIDENCE_IDENTITY_FIELDS:
            assert field in self.BASE_ROW, f"Test BASE_ROW missing identity field: {field}"
