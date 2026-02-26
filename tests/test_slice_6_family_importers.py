"""
Tests for Slice 6: Family Importers (FIX-5)

Definition of Done: After importing all CSVs for Campbell, all 4 family
tables have > 0 rows. FK constraints all satisfied.

Test strategy:
  - Each importer gets unit tests for validation + happy-path insert
  - Watcher dispatch gets tests for routing to correct importer
  - Integration test verifies all families import for a paper
"""
from __future__ import annotations

import hashlib
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session

from crci.extraction.family_importers import (
    import_population_norm,
    import_context_prior,
    import_temporal_evidence,
    import_instrument_evidence,
)
from crci.shared.models.tables import (
    BiomarkerNodeDefinition,
    EdgeRelationsDefinition,
    InstrumentDefinition,
    PopulationNorms,
    NodePrior,
    TemporalEvidence,
    InstrumentEvidence,
)


# ---- Helpers ----

def _make_session_mock():
    """Session mock that returns truthy for FK lookups, None for dedup.

    FK checks use session.get(ModelClass, pk) — we return a truthy MagicMock
    for node/edge/instrument definitions, but None for the family tables
    (allowing dedup checks to see no duplicate).
    """
    session = MagicMock(spec=Session)

    # Tables that are "family" output tables — return None (no existing row)
    dedup_tables = {PopulationNorms, NodePrior, TemporalEvidence, InstrumentEvidence}

    def _get_side_effect(model_class, pk):
        if model_class in dedup_tables:
            return None
        return MagicMock()  # FK exists

    session.get.side_effect = _get_side_effect
    return session


def _pop_norm_row():
    return {
        "doi": "10.1002/pon.4370",
        "node_id": "NODE_COG_PROC_SPEED",
        "instrument_id": "INST_TMT_B",
        "mean": "33.8",
        "sd": "9.1",
        "sample_size": "9",
        "cancer_type": "breast",
        "treatment_phase": "early_recovery",
        "age_range": "40-65",
    }


def _context_prior_row():
    return {
        "doi": "10.1002/pon.4370",
        "node_id": "NODE_SYM_COG_COMPLAINTS",
        "cancer_type": "breast",
        "treatment_phase": "early_recovery",
        "prior_mean_z": "-2.18",
        "prior_sd_z": "1.0",
        "source_type": "published_norm_comparison",
        "n_contributing": "9",
        "notes": "FACT-Cog PCI baseline comparison",
    }


def _temporal_row():
    return {
        "doi": "10.1002/pon.4370",
        "edge_id": "ER_ACTIVITY_PROC_SPEED",
        "timepoint_weeks": "24",
        "value": "-1.56",
        "se": "0.53",
        "is_recovery": "0",
        "sample_size": "19",
        "provenance_ref": "post_intervention_cohen_d",
    }


def _instrument_row():
    return {
        "doi": "10.1002/pon.4370",
        "instrument_id": "INST_TMT_B",
        "reliability_value": "0.79",
        "reliability_type": "test_retest",
        "factor_loading_mean": "",
        "test_retest_icc": "0.79",
        "sample_size": "",
        "cancer_type": "breast",
        "cancer_validated": "no",
        "provenance_ref": "Lezak et al. 2004 Neuropsychological Assessment",
    }


# ============================================================================
# TestPopulationNormImporter
# ============================================================================
class TestPopulationNormImporter:
    """Tests for import_population_norm()."""

    def test_happy_path_returns_id(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        result = import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")
        assert result.startswith("NORM_")
        assert len(result) > len("NORM_")  # has a hash suffix
        session.add.assert_called_once()

    def test_orm_object_populated_correctly(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert isinstance(orm_obj, PopulationNorms)
        assert orm_obj.mean_raw == 33.8
        assert orm_obj.sd_raw == 9.1
        assert orm_obj.N == 9
        assert orm_obj.node_id == "NODE_COG_PROC_SPEED"
        assert orm_obj.instrument_id == "INST_TMT_B"
        assert orm_obj.cancer_type == "breast"
        assert orm_obj.treatment_phase == "early_recovery"
        assert orm_obj.study_id == "STUDY_CAMPBELL_2017"

    def test_rejects_missing_node_id(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        row["node_id"] = ""
        with pytest.raises(ValueError, match="node_id"):
            import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_negative_sd(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        row["sd"] = "-1.0"
        with pytest.raises(ValueError, match="sd"):
            import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_zero_sample_size(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        row["sample_size"] = "0"
        with pytest.raises(ValueError, match="sample_size"):
            import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_missing_mean(self):
        session = _make_session_mock()
        row = _pop_norm_row()
        row["mean"] = ""
        with pytest.raises(ValueError, match="mean"):
            import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_fk_node_id_checked(self):
        """If node_id doesn't exist in DB, raise ValueError."""
        session = _make_session_mock()
        # Override: node FK returns None
        original_side_effect = session.get.side_effect

        def _reject_node(model_class, pk):
            if model_class is BiomarkerNodeDefinition:
                return None
            return original_side_effect(model_class, pk)

        session.get.side_effect = _reject_node
        row = _pop_norm_row()
        with pytest.raises(ValueError, match="node_id.*not found"):
            import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_deterministic_id(self):
        """Same study+node+cancer_type → same id."""
        session = _make_session_mock()
        row = _pop_norm_row()
        id1 = import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")
        session.reset_mock()
        session.get.side_effect = _make_session_mock().get.side_effect
        id2 = import_population_norm(session, row, study_id="STUDY_CAMPBELL_2017")
        assert id1 == id2


# ============================================================================
# TestContextPriorImporter
# ============================================================================
class TestContextPriorImporter:
    """Tests for import_context_prior()."""

    def test_happy_path(self):
        session = _make_session_mock()
        row = _context_prior_row()
        result = import_context_prior(session, row, study_id="STUDY_CAMPBELL_2017")
        assert result.startswith("PRIOR_")
        session.add.assert_called_once()

    def test_orm_object_populated(self):
        session = _make_session_mock()
        row = _context_prior_row()
        import_context_prior(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert isinstance(orm_obj, NodePrior)
        assert orm_obj.mean == -2.18
        assert orm_obj.sd == 1.0
        assert orm_obj.dist_family == "normal"
        assert orm_obj.prior_space == "z"
        assert orm_obj.node_id == "NODE_SYM_COG_COMPLAINTS"

    def test_rejects_negative_sd(self):
        session = _make_session_mock()
        row = _context_prior_row()
        row["prior_sd_z"] = "-0.5"
        with pytest.raises(ValueError, match="prior_sd_z"):
            import_context_prior(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_missing_node_id(self):
        session = _make_session_mock()
        row = _context_prior_row()
        row["node_id"] = ""
        with pytest.raises(ValueError, match="node_id"):
            import_context_prior(session, row, study_id="STUDY_CAMPBELL_2017")


# ============================================================================
# TestTemporalEvidenceImporter
# ============================================================================
class TestTemporalEvidenceImporter:
    """Tests for import_temporal_evidence()."""

    def test_happy_path(self):
        session = _make_session_mock()
        row = _temporal_row()
        result = import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        assert result.startswith("TEMP_")
        session.add.assert_called_once()

    def test_orm_object_populated(self):
        session = _make_session_mock()
        row = _temporal_row()
        import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert isinstance(orm_obj, TemporalEvidence)
        assert orm_obj.timepoint_weeks == 24.0
        assert orm_obj.effect == -1.56
        assert orm_obj.se == 0.53
        assert orm_obj.is_recovery == 0
        assert orm_obj.N == 19
        assert orm_obj.action_id == "ER_ACTIVITY_PROC_SPEED"

    def test_rejects_negative_timepoint(self):
        session = _make_session_mock()
        row = _temporal_row()
        row["timepoint_weeks"] = "-1"
        with pytest.raises(ValueError, match="timepoint_weeks"):
            import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_missing_edge_id(self):
        session = _make_session_mock()
        row = _temporal_row()
        row["edge_id"] = ""
        with pytest.raises(ValueError, match="edge_id"):
            import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_zero_sample_size(self):
        session = _make_session_mock()
        row = _temporal_row()
        row["sample_size"] = "0"
        with pytest.raises(ValueError, match="sample_size"):
            import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_fk_edge_id_checked(self):
        """If edge_id doesn't exist in edge_relations_definitions_v1, raise."""
        session = _make_session_mock()
        original = session.get.side_effect

        def _reject_edge(model_class, pk):
            if model_class is EdgeRelationsDefinition:
                return None
            return original(model_class, pk)

        session.get.side_effect = _reject_edge
        row = _temporal_row()
        with pytest.raises(ValueError, match="edge_id.*not found"):
            import_temporal_evidence(session, row, study_id="STUDY_CAMPBELL_2017")


# ============================================================================
# TestInstrumentEvidenceImporter
# ============================================================================
class TestInstrumentEvidenceImporter:
    """Tests for import_instrument_evidence()."""

    def test_happy_path(self):
        session = _make_session_mock()
        row = _instrument_row()
        result = import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        assert result.startswith("INST_EV_")
        session.add.assert_called_once()

    def test_orm_object_populated_test_retest(self):
        session = _make_session_mock()
        row = _instrument_row()
        import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert isinstance(orm_obj, InstrumentEvidence)
        assert orm_obj.test_retest_reliability == 0.79
        assert orm_obj.cronbachs_alpha is None  # reliability_type=test_retest
        assert orm_obj.instrument_id == "INST_TMT_B"

    def test_orm_object_populated_cronbachs_alpha(self):
        session = _make_session_mock()
        row = _instrument_row()
        row["reliability_type"] = "cronbachs_alpha"
        row["reliability_value"] = "0.92"
        row["test_retest_icc"] = ""
        import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert orm_obj.cronbachs_alpha == 0.92
        assert orm_obj.test_retest_reliability is None

    def test_rejects_reliability_out_of_range(self):
        session = _make_session_mock()
        row = _instrument_row()
        row["reliability_value"] = "1.5"
        with pytest.raises(ValueError, match="reliability_value"):
            import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_negative_reliability(self):
        session = _make_session_mock()
        row = _instrument_row()
        row["reliability_value"] = "-0.1"
        with pytest.raises(ValueError, match="reliability_value"):
            import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_missing_provenance(self):
        """Spec: without reliability_source_citation, reject the row."""
        session = _make_session_mock()
        row = _instrument_row()
        row["provenance_ref"] = ""
        with pytest.raises(ValueError, match="provenance_ref"):
            import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_rejects_missing_instrument_id(self):
        session = _make_session_mock()
        row = _instrument_row()
        row["instrument_id"] = ""
        with pytest.raises(ValueError, match="instrument_id"):
            import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_fk_instrument_id_checked(self):
        """If instrument_id doesn't exist in instrument_definitions_v1, raise."""
        session = _make_session_mock()
        original = session.get.side_effect

        def _reject_inst(model_class, pk):
            if model_class is InstrumentDefinition:
                return None
            return original(model_class, pk)

        session.get.side_effect = _reject_inst
        row = _instrument_row()
        with pytest.raises(ValueError, match="instrument_id.*not found"):
            import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")

    def test_test_retest_icc_overrides(self):
        """Dedicated test_retest_icc column should populate trt even when type=cronbachs."""
        session = _make_session_mock()
        row = _instrument_row()
        row["reliability_type"] = "cronbachs_alpha"
        row["reliability_value"] = "0.85"
        row["test_retest_icc"] = "0.79"
        import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        orm_obj = session.add.call_args[0][0]
        assert orm_obj.cronbachs_alpha == 0.85
        assert orm_obj.test_retest_reliability == 0.79

    def test_deterministic_id(self):
        """Same study+instrument → same id."""
        session = _make_session_mock()
        row = _instrument_row()
        id1 = import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        session.reset_mock()
        session.get.side_effect = _make_session_mock().get.side_effect
        id2 = import_instrument_evidence(session, row, study_id="STUDY_CAMPBELL_2017")
        assert id1 == id2


# ============================================================================
# TestWatcherDispatch
# ============================================================================
class TestWatcherDispatch:
    """Tests for watcher routing to family importers."""

    def test_watcher_dispatches_population_norms(self):
        """import_structured_csv with population_norms_template calls importer."""
        from crci.retrieval.manual_upload_watcher import import_structured_csv
        from pathlib import Path
        import tempfile
        import csv

        # Create a temp CSV with 1 valid row
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="population_norms_template",
            delete=False,
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(_pop_norm_row().keys()))
            writer.writeheader()
            writer.writerow(_pop_norm_row())
            tmp_path = Path(f.name)

        # Rename to match template name
        target = tmp_path.parent / "population_norms_template.csv"
        tmp_path.rename(target)

        try:
            session = _make_session_mock()
            with patch(
                "crci.retrieval.manual_upload_watcher._resolve_study_id",
                return_value="STUDY_CAMPBELL_2017",
            ):
                result = import_structured_csv(session, target)
            # Should have processed without "not yet implemented" warning
            not_impl_warnings = [
                w for w in result.warnings if "not yet implemented" in w
            ]
            assert len(not_impl_warnings) == 0, f"Got stale stub warning: {result.warnings}"
            assert result.csvs_imported >= 1 or result.files_processed >= 1
        finally:
            target.unlink(missing_ok=True)

    def test_watcher_dispatches_instrument_evidence(self):
        """import_structured_csv with instrument_evidence_template calls importer."""
        from crci.retrieval.manual_upload_watcher import import_structured_csv
        from pathlib import Path
        import tempfile
        import csv

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="instrument_evidence_template",
            delete=False,
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(_instrument_row().keys()))
            writer.writeheader()
            writer.writerow(_instrument_row())
            tmp_path = Path(f.name)

        target = tmp_path.parent / "instrument_evidence_template.csv"
        tmp_path.rename(target)

        try:
            session = _make_session_mock()
            with patch(
                "crci.retrieval.manual_upload_watcher._resolve_study_id",
                return_value="STUDY_CAMPBELL_2017",
            ):
                result = import_structured_csv(session, target)
            not_impl_warnings = [
                w for w in result.warnings if "not yet implemented" in w
            ]
            assert len(not_impl_warnings) == 0
        finally:
            target.unlink(missing_ok=True)
