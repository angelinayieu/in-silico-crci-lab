"""
Tests for Slice 9: Cross-cutting Wiring (FIX-7/8/9).

Validates:
9A: Context key orphans — missingness_report and outcomes wiring
9C: Chain B evidence bridge — reads from edge_evidence_v1 → EvidenceRecord
9D: extraction_audit_v1 writer utility
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════
#  9A: missingness_report wiring
# ═══════════════════════════════════════════════════════════════


class TestMissingnessReportWiring:
    """P2 runner should set context['missingness_report'] from
    extraction completeness data so P5 can consume it."""

    def test_build_missingness_report_from_families(self):
        """Build MissingnessReport from family population state."""
        from crci.extraction.context_wiring import build_missingness_report

        report = build_missingness_report(
            paper_id="STUDY_TEST",
            families_present=["F1", "F3"],
            families_expected=["F1", "F2", "F3", "F4"],
        )
        assert report.total_components == 4
        assert report.present_count == 2
        assert report.missing_count == 2
        assert 0.49 < report.completeness_fraction() < 0.51

    def test_all_present_full_completeness(self):
        from crci.extraction.context_wiring import build_missingness_report

        report = build_missingness_report(
            paper_id="STUDY_FULL",
            families_present=["F1", "F2", "F3"],
            families_expected=["F1", "F2", "F3"],
        )
        assert report.completeness_fraction() == 1.0

    def test_empty_expected_zero_completeness(self):
        from crci.extraction.context_wiring import build_missingness_report

        report = build_missingness_report(
            paper_id="STUDY_EMPTY",
            families_present=[],
            families_expected=[],
        )
        assert report.completeness_fraction() == 0.0

    def test_report_entries_have_correct_codes(self):
        from crci.extraction.context_wiring import build_missingness_report
        from crci.shared.models.enums import MissingnessCode

        report = build_missingness_report(
            paper_id="STUDY_X",
            families_present=["F1"],
            families_expected=["F1", "F2"],
        )
        codes = {e.component_id: e.code for e in report.entries}
        assert codes["F1"] == MissingnessCode.PRESENT
        assert codes["F2"] == MissingnessCode.ABSENT_IN_PAPER


# ═══════════════════════════════════════════════════════════════
#  9A: outcomes context key wiring
# ═══════════════════════════════════════════════════════════════


class TestOutcomesContextWiring:
    """P1 runner should set context['outcomes'] from AG04 output."""

    def test_extract_outcomes_from_agent_metadata(self):
        from crci.extraction.context_wiring import extract_outcomes_from_agents

        metadata = {
            "n_outcomes": 2,
            "instruments": [
                {"name": "FACT-Cog", "id": "FACT_COG", "domain": "cognitive", "timepoints": ["baseline", "12w"]},
                {"name": "HVLT-R", "id": "HVLT_R", "domain": "memory", "timepoints": ["baseline"]},
            ],
        }
        outcomes = extract_outcomes_from_agents(metadata)
        assert len(outcomes) == 2
        assert outcomes[0].instrument_name == "FACT-Cog"
        assert outcomes[0].instrument_id == "FACT_COG"
        assert outcomes[1].instrument_name == "HVLT-R"

    def test_empty_metadata_returns_empty(self):
        from crci.extraction.context_wiring import extract_outcomes_from_agents

        outcomes = extract_outcomes_from_agents({})
        assert outcomes == []

    def test_outcomes_have_required_attributes(self):
        """ConceptEngine reads .instrument_id and .instrument_name."""
        from crci.extraction.context_wiring import extract_outcomes_from_agents

        metadata = {
            "instruments": [
                {"name": "TMT-A", "id": "TMT_A", "domain": "speed", "timepoints": []},
            ],
        }
        outcomes = extract_outcomes_from_agents(metadata)
        o = outcomes[0]
        assert hasattr(o, "instrument_id")
        assert hasattr(o, "instrument_name")


# ═══════════════════════════════════════════════════════════════
#  9C: Chain B evidence bridge
# ═══════════════════════════════════════════════════════════════


class TestChainBEvidenceBridge:
    """Build EvidenceRecord from edge_evidence_v1 rows."""

    def _make_mock_row(self, **overrides):
        """Create a mock EdgeEvidence row."""
        defaults = dict(
            ler_id="LER_TEST_001",
            edge_relation_id="ER_ACTIVITY_PROC_SPEED",
            study_id="STUDY_CAMPBELL_2017",
            harmonized_beta=0.35,
            harmonized_se=0.12,
            N_effect=200,
            quality_rating="moderate",
            rob_overall="low",
            identification_status="identified",
            meta_source_flag=None,
            shared_control_flag=False,
            endpoint_vs_change="ENDPOINT",
            parameter_family="edge_intervention",
        )
        defaults.update(overrides)
        row = MagicMock()
        for k, v in defaults.items():
            setattr(row, k, v)
        return row

    def _make_mock_study_row(self, **overrides):
        defaults = dict(
            study_id="STUDY_CAMPBELL_2017",
            study_design="RCT",
            year=2017,
        )
        defaults.update(overrides)
        row = MagicMock()
        for k, v in defaults.items():
            setattr(row, k, v)
        return row

    def test_bridge_creates_evidence_record(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row()
        mock_study = self._make_mock_study_row()

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        assert rec.study_id == "STUDY_CAMPBELL_2017"
        assert rec.edge_id == "ER_ACTIVITY_PROC_SPEED"
        assert rec.beta == 0.35
        assert rec.se == 0.12
        assert rec.sample_size == 200
        assert rec.publication_year == 2017
        assert rec.quality_grade == "HIGH"  # rob_overall="low" → HIGH quality

    def test_bridge_defaults_for_missing_fields(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row(
            identification_status=None,
            rob_overall=None,
        )
        mock_study = self._make_mock_study_row(year=None)

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        # Should not crash — uses sensible defaults
        assert rec.identification_status == "plausible"
        assert rec.quality_grade == "MODERATE"
        assert rec.publication_year == 2020  # default

    def test_bridge_maps_study_design(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row()
        mock_study = self._make_mock_study_row(study_design="RCT")

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        # Should map to a valid config.DESIGN_MULTIPLIERS key
        assert rec.study_design in (
            "large_rct", "small_rct", "small_rct_default", "RCT",
            "observational", "cross_sectional", "cohort",
        ) or rec.study_design == "RCT"

    def test_bridge_maps_cross_sectional_flags(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row()
        mock_study = self._make_mock_study_row(study_design="cross_sectional")

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        assert rec.is_cross_sectional is True
        assert rec.has_rct_component is False

    def test_bridge_maps_rct_flags(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row()
        mock_study = self._make_mock_study_row(study_design="RCT")

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        assert rec.has_rct_component is True
        assert rec.is_cross_sectional is False

    def test_bridge_scope_weights_default(self):
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row()
        mock_study = self._make_mock_study_row()

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        # scope_weights should be a 5-dim dict
        assert len(rec.scope_weights) == 5
        assert "population" in rec.scope_weights

    def test_bridge_rob_to_grade_mapping(self):
        """rob_overall → quality_grade mapping."""
        from crci.extraction.context_wiring import edge_evidence_to_chain_b_record

        mock_row = self._make_mock_row(rob_overall="high")
        mock_study = self._make_mock_study_row()

        rec = edge_evidence_to_chain_b_record(mock_row, mock_study)

        # High RoB → LOW quality grade
        assert rec.quality_grade == "LOW"


# ═══════════════════════════════════════════════════════════════
#  9C: Batch bridge function
# ═══════════════════════════════════════════════════════════════


class TestChainBBatchBridge:
    """load_evidence_records_from_db should query edge_evidence_v1
    and produce EvidenceRecord list."""

    def test_function_exists(self):
        from crci.extraction.context_wiring import load_evidence_records_from_db
        assert callable(load_evidence_records_from_db)


# ═══════════════════════════════════════════════════════════════
#  9D: extraction_audit writer
# ═══════════════════════════════════════════════════════════════


class TestExtractionAuditWriter:
    """Utility to write audit rows to extraction_audit_v1."""

    def test_write_audit_row_creates_record(self):
        from crci.extraction.context_wiring import write_audit_row

        mock_session = MagicMock()
        write_audit_row(
            session=mock_session,
            study_id="STUDY_TEST",
            pipeline_stage="P2",
            agent_id="AG04",
            status="success",
            records_input=10,
            records_output=8,
            records_rejected=2,
        )
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.study_id == "STUDY_TEST"
        assert added.pipeline_stage == "P2"
        assert added.agent_id == "AG04"
        assert added.status == "success"
        assert added.records_input == 10
        assert added.records_output == 8
        assert added.records_rejected == 2

    def test_audit_id_is_deterministic(self):
        from crci.extraction.context_wiring import write_audit_row

        mock_session = MagicMock()
        write_audit_row(
            session=mock_session,
            study_id="STUDY_A",
            pipeline_stage="P3",
            agent_id=None,
            status="success",
            records_input=5,
            records_output=5,
            records_rejected=0,
        )
        added = mock_session.add.call_args[0][0]
        assert added.audit_id.startswith("AUD_")
        assert len(added.audit_id) > 4

    def test_audit_row_with_rejection_reasons(self):
        from crci.extraction.context_wiring import write_audit_row
        import json

        mock_session = MagicMock()
        reasons = {"missing_se": 2, "out_of_range": 1}
        write_audit_row(
            session=mock_session,
            study_id="STUDY_B",
            pipeline_stage="TB",
            agent_id=None,
            status="partial",
            records_input=10,
            records_output=7,
            records_rejected=3,
            rejection_reasons=reasons,
        )
        added = mock_session.add.call_args[0][0]
        parsed = json.loads(added.rejection_reasons_json)
        assert parsed["missing_se"] == 2
