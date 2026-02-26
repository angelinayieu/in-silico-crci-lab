"""
Tests for R1-R4 Routing Slices.

Covers:
- R1: PaperSubtype completeness + ExtractionMode MINIMAL
- R2: Evidence block gates + quality caps + identification rules
- R3: Forest plot supersede + subgroup correlation detection
- R4: Heterogeneity passthrough + NMA overlap + dose-response wiring
"""
from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════
#  R1: ENUM + ROUTING TABLE COMPLETENESS
# ═══════════════════════════════════════════════════════════════


def test_extraction_mode_has_minimal():
    """R1.1: ExtractionMode includes MINIMAL."""
    from crci.shared.models.enums import ExtractionMode

    assert "MINIMAL" in ExtractionMode.__members__
    assert ExtractionMode.MINIMAL.value == "MINIMAL"


def test_paper_subtype_count():
    """R1.2: PaperSubtype has at least 43 members."""
    from crci.shared.models.enums import PaperSubtype

    members = list(PaperSubtype)
    assert len(members) >= 43, f"Expected >=43 subtypes, got {len(members)}"


def test_all_subtypes_routed():
    """R1.3: Every PaperSubtype has an entry in _SUBTYPE_TO_MODE."""
    from crci.shared.models.enums import PaperSubtype
    from crci.extraction.p0_triage.mode_selection import _SUBTYPE_TO_MODE

    missing = []
    for member in PaperSubtype:
        if member.value not in _SUBTYPE_TO_MODE:
            missing.append(member.value)
    assert not missing, f"Unrouted subtypes: {missing}"


def test_new_subtypes_present():
    """R1.2: Key new fine-grained subtypes exist."""
    from crci.shared.models.enums import PaperSubtype

    expected_new = {
        "PAIRWISE_MA", "NMA", "IPDMA", "DOSE_RESPONSE_MA",
        "UMBRELLA_REVIEW", "MEGA_ANALYSIS", "SCOPING_REVIEW",
        "STANDARD_RCT", "FACTORIAL_RCT", "PILOT_RCT", "CROSSOVER_RCT",
        "PROSPECTIVE_COHORT", "RETROSPECTIVE_COHORT",
        "MECHANISTIC_IN_VITRO", "COMPUTATIONAL_MODEL", "METHODS_PAPER",
    }
    actual = set(PaperSubtype.__members__.keys())
    missing = expected_new - actual
    assert not missing, f"Missing new subtypes: {missing}"


# ═══════════════════════════════════════════════════════════════
#  R2: ENFORCEMENT GATES
# ═══════════════════════════════════════════════════════════════


def test_minimal_mode_subtypes_blocked():
    """R2.2: MINIMAL-mode subtypes cannot produce evidence rows."""
    from crci.extraction.evidence_writer import _EVIDENCE_BLOCKED_SUBTYPES
    from crci.shared.models.enums import PaperSubtype

    expected_blocked = {
        PaperSubtype.REVIEW_NARRATIVE.value,
        PaperSubtype.CASE_REPORT.value,
        PaperSubtype.QUALITATIVE.value,
        PaperSubtype.UMBRELLA_REVIEW.value,
        PaperSubtype.MECHANISTIC_IN_VITRO.value,
    }
    assert expected_blocked.issubset(_EVIDENCE_BLOCKED_SUBTYPES)


def test_evidence_block_gate_raises():
    """R2.2: _check_evidence_row_allowed raises GateViolation for blocked subtypes."""
    from crci.extraction.evidence_writer import _check_evidence_row_allowed
    from crci.shared.models.intermediate_states import GateViolation
    from crci.shared.models.enums import PaperSubtype

    with pytest.raises(GateViolation):
        _check_evidence_row_allowed(PaperSubtype.UMBRELLA_REVIEW.value)


def test_evidence_block_gate_allows_rct():
    """R2.2: _check_evidence_row_allowed passes for RCT subtypes."""
    from crci.extraction.evidence_writer import _check_evidence_row_allowed

    from crci.shared.models.enums import PaperSubtype
    # Should not raise
    _check_evidence_row_allowed(PaperSubtype.RCT_EXERCISE.value)


def test_pilot_rct_quality_cap():
    """R2.3: Pilot RCT 'strong' quality is capped to 'moderate'."""
    from crci.extraction.p2_harmonization.runner import _apply_subtype_quality_caps

    from crci.shared.models.enums import PaperSubtype
    assert _apply_subtype_quality_caps("strong", PaperSubtype.PILOT_RCT.value) == "moderate"
    assert _apply_subtype_quality_caps("moderate", PaperSubtype.PILOT_RCT.value) == "moderate"
    assert _apply_subtype_quality_caps("strong", PaperSubtype.RCT_EXERCISE.value) == "strong"


def test_cross_sectional_identification_demotion():
    """R2.4: Cross-sectional always NOT_IDENTIFIED."""
    from crci.extraction.p2_harmonization.runner import _apply_subtype_identification_rules

    from crci.shared.models.enums import PaperSubtype
    result = _apply_subtype_identification_rules("identified", PaperSubtype.CROSS_SECTIONAL.value)
    assert result == "not_identified"


def test_retrospective_identification_cap():
    """R2.4: Retrospective cohort capped at PARTIALLY_IDENTIFIED."""
    from crci.extraction.p2_harmonization.runner import _apply_subtype_identification_rules

    from crci.shared.models.enums import PaperSubtype
    result = _apply_subtype_identification_rules("identified", PaperSubtype.RETROSPECTIVE_COHORT.value)
    assert result == "partially_identified"

    # partially_identified should stay as-is
    result2 = _apply_subtype_identification_rules("partially_identified", PaperSubtype.RETROSPECTIVE_COHORT.value)
    assert result2 == "partially_identified"


def test_nma_mixed_identification_cap():
    """R2.5: NMA mixed estimates capped at PARTIALLY_IDENTIFIED."""
    from crci.extraction.p2_harmonization.runner import _apply_subtype_identification_rules
    from crci.shared.models.enums import MetaSourceFlag, PaperSubtype

    result = _apply_subtype_identification_rules(
        "identified", PaperSubtype.META_ANALYSIS.value, MetaSourceFlag.NMA_MIXED.value
    )
    assert result == "partially_identified"


# ═══════════════════════════════════════════════════════════════
#  R4: ALGORITHM ADAPTATIONS
# ═══════════════════════════════════════════════════════════════


def test_nma_pairwise_overlap_detection_warns():
    """R4.2: detect_nma_pairwise_overlap warns when both NMA and pairwise claims exist."""
    from crci.extraction.p4_aggregation.double_counting import detect_nma_pairwise_overlap
    from crci.shared.models.enums import MetaSourceFlag
    from unittest.mock import MagicMock

    # Create mock claims with meta_source_flag
    nma_claim = MagicMock()
    nma_claim.meta_source_flag = MetaSourceFlag.NMA_MIXED.value
    nma_claim.parent_meta_study_id = "ma_001"

    pw_claim = MagicMock()
    pw_claim.meta_source_flag = MetaSourceFlag.POOLED_ESTIMATE.value
    pw_claim.parent_meta_study_id = "ma_002"

    primary = MagicMock()
    primary.meta_source_flag = None
    primary.parent_meta_study_id = None

    warnings = detect_nma_pairwise_overlap(
        [nma_claim, pw_claim, primary], "edge_001"
    )
    assert len(warnings) == 1
    assert "R4-NMA3" in warnings[0]


def test_nma_pairwise_overlap_no_warning_without_both():
    """R4.2: No warning if only NMA or only pairwise MA present."""
    from crci.extraction.p4_aggregation.double_counting import detect_nma_pairwise_overlap
    from crci.shared.models.enums import MetaSourceFlag
    from unittest.mock import MagicMock

    # Only NMA
    nma_claim = MagicMock()
    nma_claim.meta_source_flag = MetaSourceFlag.NMA_MIXED.value
    nma_claim.parent_meta_study_id = "ma_001"

    warnings = detect_nma_pairwise_overlap([nma_claim], "edge_001")
    assert len(warnings) == 0


def test_extraction_mode_values():
    """R1.1: All 4 extraction modes exist with correct values."""
    from crci.shared.models.enums import ExtractionMode

    expected = {"MINIMAL", "SHALLOW", "STANDARD", "DEEP"}
    actual = {m.value for m in ExtractionMode}
    assert actual == expected


# ═══════════════════════════════════════════════════════════════
#  R1.4: MA MULTI-PRODUCT PLAN
# ═══════════════════════════════════════════════════════════════


def test_umbrella_review_produces_study_list_only():
    """R1.4: Umbrella review yields only INCLUDED_STUDY_LIST."""
    from crci.extraction.p1_extraction.ma_multi_product import build_ma_extraction_plan
    from crci.shared.models.enums import PaperSubtype

    plan = build_ma_extraction_plan(
        paper_id="test_umbrella",
        paper_subtype=PaperSubtype.UMBRELLA_REVIEW.value,
        paper_text="An umbrella review of meta-analyses",
    )
    product_types = {p.product_type.value for p in plan.products}
    assert "included_study_list" in product_types
    assert "pooled_estimate" not in product_types


def test_ipdma_includes_ipd_interaction_product():
    """R1.4: IPDMA papers include IPD_INTERACTION product."""
    from crci.extraction.p1_extraction.ma_multi_product import build_ma_extraction_plan
    from crci.shared.models.enums import PaperSubtype

    plan = build_ma_extraction_plan(
        paper_id="test_ipdma",
        paper_subtype=PaperSubtype.IPDMA.value,
        paper_text="Individual patient data meta-analysis",
    )
    product_types = {p.product_type.value for p in plan.products}
    assert "ipd_interaction" in product_types
