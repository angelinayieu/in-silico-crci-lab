"""Tests for Slice R3: MA Product Lifecycle & Forest Plot Superseding.

R3.1: Forest plot auto-supersede
R3.2: Subgroup correlation warning
R3.3: IPD-MA product skeleton (covered in test_routing_gates.py)
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from crci.shared.models.enums import EffectScale, MetaSourceFlag, SESource
from crci.shared.models.intermediate_states import HarmonizedClaim

# Use valid EffectScale member
_EFFECT_SCALE = EffectScale.SD_SD
# Valid harmonization status
_HARM_STATUS = "FULL"
from crci.shared.models.intermediate_states import HarmonizedClaim


# ═══════════════════════════════════════════════════════════════
#  R3.1: FOREST PLOT AUTO-SUPERSEDE
# ═══════════════════════════════════════════════════════════════


class TestForestPlotSupersede:
    """R3.1: Forest plot entries deactivated on primary extraction."""

    def test_supersede_deactivates_forest_plot_entries(self):
        """Insert forest plot entry, then insert primary → forest plot active=0."""
        from crci.extraction.evidence_writer import _supersede_forest_plot_entries
        from crci.shared.models.tables import EdgeEvidence

        # Mock session with an UPDATE that affects 1 row
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_session.execute.return_value = mock_result

        count = _supersede_forest_plot_entries(
            session=mock_session,
            study_id="STUDY_001",
            edge_relation_id="ER_EXERCISE_FATIGUE",
        )

        assert count == 2
        mock_session.execute.assert_called_once()

    def test_supersede_noop_when_no_forest_plot(self):
        """Insert primary row with no existing forest plot → no-op."""
        from crci.extraction.evidence_writer import _supersede_forest_plot_entries

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        count = _supersede_forest_plot_entries(
            session=mock_session,
            study_id="STUDY_002",
            edge_relation_id="ER_EXERCISE_FATIGUE",
        )

        assert count == 0

    def test_supersede_called_for_primary_rows(self):
        """write_evidence_rows calls supersede for primary (non-MA) rows."""
        from crci.extraction.evidence_writer import write_evidence_rows

        # Build a minimal harmonized record (dict style) with no meta_source_flag
        record = {
            "beta": 0.35,
            "se": 0.10,
            "scale": _EFFECT_SCALE,
            "se_source": SESource.SE_DIRECT,
            "se_derivation_level": None,
            "se_inflation_applied": 1.0,
            "se_quality_tag": None,
            "conversion_formula": None,
            "conversion_bias_risk": None,
            "direction_aligned": False,
            "edge_id": "ER_EXERCISE_FATIGUE",
            "source_position": None,
            "n": 50,
            "quality_rating": "moderate",
            "meta_source_flag": None,  # Primary row
        }

        mock_session = MagicMock()
        mock_run = MagicMock()
        mock_run.extraction_run_id = "RUN_001"

        # Mock the session.query for UPSERT check (no existing row)
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Mock the supersede UPDATE
        mock_supersede_result = MagicMock()
        mock_supersede_result.rowcount = 0
        mock_session.execute.return_value = mock_supersede_result

        written = write_evidence_rows(
            session=mock_session,
            run=mock_run,
            harmonized_records=[record],
            study_id="STUDY_003",
        )

        assert written == 1
        # Verify supersede was called (session.execute with UPDATE)
        mock_session.execute.assert_called_once()


# ═══════════════════════════════════════════════════════════════
#  R3.2: SUBGROUP CORRELATION WARNING
# ═══════════════════════════════════════════════════════════════


def _make_claim(
    ler_id: str,
    edge_id: str = "ER_EXERCISE_FATIGUE",
    meta_flag: str | None = None,
    parent_ma: str | None = None,
    beta: float = 0.3,
    se: float = 0.1,
) -> HarmonizedClaim:
    """Helper to build a HarmonizedClaim for testing."""
    return HarmonizedClaim(
        ler_id=ler_id,
        edge_relation_id=edge_id,
        profile_id="PROF_01",
        study_id=parent_ma or "STUDY_PRIMARY",
        harmonized_beta=beta,
        harmonized_se=se,
        harmonized_scale=_EFFECT_SCALE,
        harmonization_status=_HARM_STATUS,
        quality_rating="moderate",
        meta_source_flag=meta_flag,
        parent_meta_study_id=parent_ma,
    )


class TestSubgroupCorrelationWarning:
    """R3.2: Correlated subgroup estimates from same MA → warning."""

    def test_two_subgroups_same_ma_triggers_warning(self):
        """Two subgroup estimates from same MA → warning emitted."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            _check_subgroup_correlation,
        )

        claims = [
            _make_claim(
                "LER_001",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
            _make_claim(
                "LER_002",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
        ]
        warnings = _check_subgroup_correlation(claims)
        assert len(warnings) == 1
        assert "R3-CORR" in warnings[0]
        assert "2 subgroup estimates" in warnings[0]
        assert "MA_CIFU_2018" in warnings[0]

    def test_subgroups_different_mas_no_warning(self):
        """Subgroup estimates from different MAs → no warning."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            _check_subgroup_correlation,
        )

        claims = [
            _make_claim(
                "LER_001",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
            _make_claim(
                "LER_002",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_NORTHEY_2018",
            ),
        ]
        warnings = _check_subgroup_correlation(claims)
        assert len(warnings) == 0

    def test_single_subgroup_no_warning(self):
        """Single subgroup estimate from an MA → no warning (need ≥2)."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            _check_subgroup_correlation,
        )

        claims = [
            _make_claim(
                "LER_001",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
            _make_claim("LER_002"),  # Primary study, not subgroup
        ]
        warnings = _check_subgroup_correlation(claims)
        assert len(warnings) == 0

    def test_primary_claims_no_warning(self):
        """All primary claims → no subgroup correlation warning."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            _check_subgroup_correlation,
        )

        claims = [
            _make_claim("LER_001"),
            _make_claim("LER_002"),
            _make_claim("LER_003"),
        ]
        warnings = _check_subgroup_correlation(claims)
        assert len(warnings) == 0

    def test_subgroup_without_parent_id_no_warning(self):
        """Subgroup flag but no parent_meta_study_id → safely ignored."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            _check_subgroup_correlation,
        )

        claims = [
            _make_claim(
                "LER_001",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma=None,  # Missing parent ID
            ),
            _make_claim(
                "LER_002",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma=None,
            ),
        ]
        warnings = _check_subgroup_correlation(claims)
        assert len(warnings) == 0

    def test_grouper_emits_subgroup_warning(self, caplog):
        """Integration: group_evidence_by_edge logs R3-CORR for correlated subgroups."""
        from crci.extraction.p4_aggregation.evidence_grouper import (
            group_evidence_by_edge,
        )

        claims = [
            _make_claim(
                "LER_001",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
            _make_claim(
                "LER_002",
                meta_flag=MetaSourceFlag.SUBGROUP_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
            ),
        ]

        with caplog.at_level(logging.WARNING):
            results = group_evidence_by_edge(claims)

        assert len(results) == 1  # One edge group
        assert any("R3-CORR" in record.message for record in caplog.records)


# ═══════════════════════════════════════════════════════════════
#  R3.3: IPD-MA PRODUCT SKELETON
# ═══════════════════════════════════════════════════════════════


class TestIPDMAProduct:
    """R3.3: IPDMA plan includes IPD_INTERACTION product."""

    def test_ipdma_plan_has_ipd_interaction(self):
        """IPDMA extraction plan includes IPD_INTERACTION product type."""
        from crci.extraction.p1_extraction.ma_multi_product import (
            MAProductType,
            build_ma_extraction_plan,
        )
        from crci.shared.models.enums import PaperSubtype

        plan = build_ma_extraction_plan(
            paper_id="test_ipdma",
            paper_subtype=PaperSubtype.IPDMA.value,
            paper_text="Individual patient data meta-analysis of exercise",
        )
        product_types = {p.product_type for p in plan.products}
        assert MAProductType.IPD_INTERACTION in product_types

    def test_standard_ma_no_ipd_interaction(self):
        """Standard MA plan does NOT include IPD_INTERACTION product."""
        from crci.extraction.p1_extraction.ma_multi_product import (
            MAProductType,
            build_ma_extraction_plan,
        )
        from crci.shared.models.enums import PaperSubtype

        plan = build_ma_extraction_plan(
            paper_id="test_standard_ma",
            paper_subtype=PaperSubtype.PAIRWISE_MA.value,
            paper_text="Meta-analysis of exercise interventions",
        )
        product_types = {p.product_type for p in plan.products}
        assert MAProductType.IPD_INTERACTION not in product_types
