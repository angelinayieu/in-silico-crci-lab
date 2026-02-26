"""
Tests for Slice 7: Completeness Checker (FIX-6)

Definition of Done: check_paper_completeness("STUDY_CAMPBELL_2017") returns
completeness_score > 0.8, 0 blocking issues, defaults_fired["L1"] == 0.

Test strategy:
  - Mock session returns realistic query results for family tables
  - Tests cover: expected families by design, layer readiness,
    effect-size consistency, blocking vs non-blocking classification,
    defaults_fired counting, completeness scoring, report writing,
    and CLI formatting
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session

from crci.extraction.completeness_checker import (
    ExtractionReport,
    check_paper_completeness,
    write_completeness_rows,
    print_report,
    _expected_families_for_design,
    _compute_completeness_score,
)


# ---- Helpers ----

def _make_evidence_row(
    *,
    study_design="RCT",
    cancer_validation_status="cancer_specific",
    rob_overall="moderate",
    pub_year=2017,
    harmonized_scale="cohen_d",
    edge_relation_id="ER_ACTIVITY_PROC_SPEED",
    harmonized_beta=-1.56,
    harmonized_se=0.53,
):
    """Create a mock edge_evidence row (as a namespace object)."""
    row = MagicMock()
    row.study_design = study_design
    row.cancer_validation_status = cancer_validation_status
    row.rob_overall = rob_overall
    row.pub_year = pub_year
    row.harmonized_scale = harmonized_scale
    row.edge_relation_id = edge_relation_id
    row.harmonized_beta = harmonized_beta
    row.harmonized_se = harmonized_se
    return row


def _make_study_row(study_design="RCT"):
    """Create a mock study_registry row."""
    row = MagicMock()
    row.study_design = study_design
    return row


def _make_session_with_data(
    study_design="RCT",
    n_edge=4,
    n_norms=6,
    n_temporal=8,
    n_instrument=6,
    n_subgroup=0,
    edge_rows=None,
):
    """Build a mock session that returns family counts and edge evidence rows.

    The mock uses session.query(...).filter(...).count() pattern for counts
    and session.query(...).filter(...).all() for evidence rows.
    """
    session = MagicMock(spec=Session)

    # Study registry lookup
    study_row = _make_study_row(study_design)
    study_query = MagicMock()
    study_query.filter.return_value.first.return_value = study_row

    # Default edge evidence rows — all fields populated
    if edge_rows is None:
        edge_rows = [_make_evidence_row() for _ in range(n_edge)]

    # Family count queries and evidence row queries use session.execute()
    # We'll mock at a higher level — the checker uses ORM queries
    # Let the implementation decide the query pattern. We'll just verify the report.

    return session, study_row, edge_rows


# ============================================================================
# TestExpectedFamilies
# ============================================================================
class TestExpectedFamilies:
    """Tests for _expected_families_for_design()."""

    def test_rct_expects_f1_f2_f3_f4(self):
        families = _expected_families_for_design("RCT")
        assert "F1" in families  # edge_evidence
        assert "F3" in families  # population_norms
        assert "F4" in families  # temporal_evidence

    def test_sr_expects_f1_only(self):
        """Systematic reviews shouldn't need original data families."""
        families = _expected_families_for_design("systematic_review")
        assert "F1" in families
        assert "F3" not in families
        assert "F4" not in families

    def test_cross_sectional_expects_f1_f3(self):
        families = _expected_families_for_design("cross_sectional")
        assert "F1" in families
        assert "F3" in families
        assert "F4" not in families

    def test_unknown_design_defaults_to_f1(self):
        families = _expected_families_for_design("unknown_design_type")
        assert "F1" in families


# ============================================================================
# TestCompletenessScore
# ============================================================================
class TestCompletenessScore:
    """Tests for _compute_completeness_score()."""

    def test_all_families_present_high_score(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1", "F2", "F3", "F4"],
            populated_families={"F1": 4, "F2": 6, "F3": 6, "F4": 8},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "READY", "L5": "READY", "L7": "READY"},
            completeness_score=0.0,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        score = _compute_completeness_score(report)
        assert score >= 0.9

    def test_missing_families_lower_score(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1", "F2", "F3", "F4"],
            populated_families={"F1": 4, "F2": 0, "F3": 0, "F4": 0},
            missing_families=["F2", "F3", "F4"],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "WILL_DEFAULT", "L5": "WILL_DEFAULT", "L7": "READY"},
            completeness_score=0.0,
            blocking_issues=[],
            non_blocking_issues=["instrument_evidence: 0 rows", "population_norms: 0 rows"],
            defaults_fired={"L1": 0, "L4": 4, "L5": 4, "L7": 0},
        )
        score = _compute_completeness_score(report)
        assert score < 0.9
        assert score > 0.0

    def test_blocking_issues_cap_score(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1"],
            populated_families={"F1": 4},
            missing_families=[],
            edge_evidence_issues=["study_design NULL for 2/4 rows"],
            layer_readiness={"L1": "BLOCKED"},
            completeness_score=0.0,
            blocking_issues=["study_design NULL for 2/4 rows"],
            non_blocking_issues=[],
            defaults_fired={"L1": 2, "L4": 0, "L5": 0, "L7": 0},
        )
        score = _compute_completeness_score(report)
        assert score <= 0.5  # blocking issues should heavily penalize


# ============================================================================
# TestExtractionReport
# ============================================================================
class TestExtractionReport:
    """Tests for ExtractionReport dataclass."""

    def test_report_creation(self):
        report = ExtractionReport(
            study_id="STUDY_CAMPBELL_2017",
            study_design="RCT",
            expected_families=["F1", "F2", "F3", "F4"],
            populated_families={"F1": 4, "F2": 6, "F3": 6, "F4": 8},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY"},
            completeness_score=0.95,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        assert report.study_id == "STUDY_CAMPBELL_2017"
        assert report.completeness_score == 0.95
        assert len(report.blocking_issues) == 0

    def test_defaults_fired_tracks_layers(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1"],
            populated_families={"F1": 4},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "WILL_DEFAULT"},
            completeness_score=0.8,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 2, "L5": 0, "L7": 4},
        )
        assert report.defaults_fired["L1"] == 0
        assert report.defaults_fired["L4"] == 2
        assert report.defaults_fired["L7"] == 4


# ============================================================================
# TestCheckPaperCompleteness
# ============================================================================
class TestCheckPaperCompleteness:
    """Tests for check_paper_completeness() with mocked DB queries."""

    def test_happy_path_rct_all_populated(self):
        """RCT with all families populated → high score, no blocking."""
        session = MagicMock(spec=Session)
        evidence_rows = [_make_evidence_row() for _ in range(4)]

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value="RCT",
        ), patch(
            "crci.extraction.completeness_checker._query_family_counts",
            return_value={"F1": 4, "F2": 6, "F3": 6, "F4": 8, "F6": 0},
        ), patch(
            "crci.extraction.completeness_checker._query_edge_evidence_rows",
            return_value=evidence_rows,
        ):
            report = check_paper_completeness(session, "STUDY_CAMPBELL_2017")

        assert report.study_id == "STUDY_CAMPBELL_2017"
        assert report.study_design == "RCT"
        assert report.completeness_score > 0.8
        assert len(report.blocking_issues) == 0
        assert report.defaults_fired["L1"] == 0

    def test_missing_study_design_is_blocking(self):
        """Rows with NULL study_design → blocking issue."""
        session = MagicMock(spec=Session)
        rows = [
            _make_evidence_row(study_design=None),
            _make_evidence_row(study_design=None),
        ]

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value="RCT",
        ), patch(
            "crci.extraction.completeness_checker._query_family_counts",
            return_value={"F1": 2, "F2": 0, "F3": 0, "F4": 0, "F6": 0},
        ), patch(
            "crci.extraction.completeness_checker._query_edge_evidence_rows",
            return_value=rows,
        ):
            report = check_paper_completeness(session, "STUDY_TEST")

        assert len(report.blocking_issues) > 0
        assert report.defaults_fired["L1"] == 2

    def test_missing_instrument_evidence_is_non_blocking(self):
        """Missing F2 (instrument_evidence) → non-blocking."""
        session = MagicMock(spec=Session)
        rows = [_make_evidence_row() for _ in range(4)]

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value="RCT",
        ), patch(
            "crci.extraction.completeness_checker._query_family_counts",
            return_value={"F1": 4, "F2": 0, "F3": 6, "F4": 8, "F6": 0},
        ), patch(
            "crci.extraction.completeness_checker._query_edge_evidence_rows",
            return_value=rows,
        ):
            report = check_paper_completeness(session, "STUDY_TEST")

        assert len(report.blocking_issues) == 0
        assert len(report.non_blocking_issues) > 0
        assert any("F2" in issue or "instrument" in issue.lower()
                    for issue in report.non_blocking_issues)

    def test_mixed_harmonized_scale_is_blocking(self):
        """Mixed harmonized_scale values → blocking."""
        session = MagicMock(spec=Session)
        rows = [
            _make_evidence_row(harmonized_scale="cohen_d"),
            _make_evidence_row(harmonized_scale="log_odds_ratio"),
        ]

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value="RCT",
        ), patch(
            "crci.extraction.completeness_checker._query_family_counts",
            return_value={"F1": 2, "F2": 0, "F3": 0, "F4": 0, "F6": 0},
        ), patch(
            "crci.extraction.completeness_checker._query_edge_evidence_rows",
            return_value=rows,
        ):
            report = check_paper_completeness(session, "STUDY_TEST")

        assert len(report.blocking_issues) > 0
        assert any("scale" in issue.lower() or "mixed" in issue.lower()
                    for issue in report.blocking_issues)

    def test_no_edge_evidence_is_blocking(self):
        """Zero F1 rows → blocking."""
        session = MagicMock(spec=Session)

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value="RCT",
        ), patch(
            "crci.extraction.completeness_checker._query_family_counts",
            return_value={"F1": 0, "F2": 0, "F3": 0, "F4": 0, "F6": 0},
        ), patch(
            "crci.extraction.completeness_checker._query_edge_evidence_rows",
            return_value=[],
        ):
            report = check_paper_completeness(session, "STUDY_TEST")

        assert len(report.blocking_issues) > 0
        assert report.completeness_score < 0.5

    def test_study_not_found_raises(self):
        """Unknown study → ValueError."""
        session = MagicMock(spec=Session)
        # Make session.query(...).filter(...).first() return None so study is 'not found'
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        session.query.return_value = mock_query

        with patch(
            "crci.extraction.completeness_checker._query_study_design",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="not found"):
                check_paper_completeness(session, "STUDY_NONEXISTENT")


# ============================================================================
# TestPrintReport
# ============================================================================
class TestPrintReport:
    """Tests for print_report()."""

    def test_print_report_contains_study_id(self):
        report = ExtractionReport(
            study_id="STUDY_CAMPBELL_2017",
            study_design="RCT",
            expected_families=["F1", "F2", "F3", "F4"],
            populated_families={"F1": 4, "F2": 6, "F3": 6, "F4": 8},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "READY", "L5": "READY", "L7": "READY"},
            completeness_score=0.95,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        text = print_report(report)
        assert "STUDY_CAMPBELL_2017" in text
        assert "0.95" in text or "95" in text

    def test_print_report_shows_blocking(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1"],
            populated_families={"F1": 0},
            missing_families=["F1"],
            edge_evidence_issues=[],
            layer_readiness={},
            completeness_score=0.0,
            blocking_issues=["No edge evidence (F1): 0 rows"],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        text = print_report(report)
        assert "BLOCKING" in text.upper() or "blocking" in text.lower()

    def test_print_report_shows_defaults_fired(self):
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1"],
            populated_families={"F1": 4},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "WILL_DEFAULT"},
            completeness_score=0.75,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 3, "L5": 0, "L7": 0},
        )
        text = print_report(report)
        assert "L4" in text
        assert "3" in text or "WILL_DEFAULT" in text


# ============================================================================
# TestWriteCompletenessRows
# ============================================================================
class TestWriteCompletenessRows:
    """Tests for write_completeness_rows()."""

    def test_writes_rows_to_session(self):
        session = MagicMock(spec=Session)
        report = ExtractionReport(
            study_id="STUDY_CAMPBELL_2017",
            study_design="RCT",
            expected_families=["F1", "F2", "F3", "F4"],
            populated_families={"F1": 4, "F2": 6, "F3": 6, "F4": 8},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY", "L4": "READY", "L5": "READY", "L7": "READY"},
            completeness_score=0.95,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        write_completeness_rows(session, report)
        # Should have written at least one row per expected family
        assert session.add.call_count >= len(report.expected_families)

    def test_missing_family_gets_absent_code(self):
        session = MagicMock(spec=Session)
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1", "F2"],
            populated_families={"F1": 4, "F2": 0},
            missing_families=["F2"],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY"},
            completeness_score=0.5,
            blocking_issues=[],
            non_blocking_issues=["F2: 0 rows"],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        write_completeness_rows(session, report)
        # Check that at least one row has ABSENT code
        added_objs = [c[0][0] for c in session.add.call_args_list]
        codes = [obj.missingness_code for obj in added_objs]
        assert any("ABSENT" in code for code in codes)

    def test_present_family_gets_present_code(self):
        session = MagicMock(spec=Session)
        report = ExtractionReport(
            study_id="STUDY_TEST",
            study_design="RCT",
            expected_families=["F1"],
            populated_families={"F1": 4},
            missing_families=[],
            edge_evidence_issues=[],
            layer_readiness={"L1": "READY"},
            completeness_score=0.9,
            blocking_issues=[],
            non_blocking_issues=[],
            defaults_fired={"L1": 0, "L4": 0, "L5": 0, "L7": 0},
        )
        write_completeness_rows(session, report)
        added_objs = [c[0][0] for c in session.add.call_args_list]
        codes = [obj.missingness_code for obj in added_objs]
        assert any("PRESENT" in code for code in codes)
