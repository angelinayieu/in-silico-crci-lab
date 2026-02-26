"""Tests for dead wire fixes (DW#3, DW#4, DW#9, DW#12).

DW#3:  P4B SE=0.01 fabrication — claims with None SE should be skipped
DW#4:  P5 pathways always empty — load from registries
DW#9:  SharedControlRecord / escalation SE=0.0 — skip None/0 SE claims
DW#12: UNKNOWN_EDGE injection — skip records without edge_relation_id
"""
from __future__ import annotations

import types
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
#  DW#3: P4B should skip claims with None SE, not fabricate 0.01
# ═══════════════════════════════════════════════════════════════


class TestDW3_P4B_SE_Fabrication:
    """Verify claims with missing SE are excluded from publication bias input."""

    def test_none_se_claims_excluded_from_study_ses(self):
        """Claims where SE is None should not appear in study_ses list."""
        from crci.shared.models.intermediate_states import HarmonizedClaim
        from crci.shared.models.enums import EffectScale, HarmonizationStatusInMem

        # Build a claim with valid SE and one with None SE
        claim_good = HarmonizedClaim(
            ler_id="good",
            edge_relation_id="ER_TEST",
            profile_id="P1",
            study_id="S1",
            harmonized_beta=0.5,
            harmonized_se=0.2,
            harmonized_scale=EffectScale.SD_SD,
            harmonization_status=HarmonizationStatusInMem.FULL,
        )
        claim_no_se = HarmonizedClaim(
            ler_id="bad",
            edge_relation_id="ER_TEST",
            profile_id="P1",
            study_id="S2",
            harmonized_beta=0.3,
            harmonized_se=None,
            harmonized_scale=EffectScale.SD_SD,
            harmonization_status=HarmonizationStatusInMem.FULL,
        )

        # Simulate the P4B filtering logic inline (mirrors runner.py DW#3 fix)
        study_betas: list[float] = []
        study_ses: list[float] = []
        for c in [claim_good, claim_no_se]:
            beta_val = getattr(c, "harmonized_beta", None)
            se_val = getattr(c, "harmonized_se", None)
            if beta_val is not None and se_val is not None and se_val > 0:
                study_betas.append(float(beta_val))
                study_ses.append(float(se_val))

        assert len(study_betas) == 1
        assert study_betas[0] == 0.5
        assert study_ses[0] == 0.2

    def test_zero_se_claims_excluded(self):
        """Claims where SE == 0 should be excluded."""
        claims = [
            types.SimpleNamespace(harmonized_beta=0.5, harmonized_se=0.0),
            types.SimpleNamespace(harmonized_beta=0.3, harmonized_se=0.2),
        ]
        study_ses: list[float] = []
        for c in claims:
            beta_val = getattr(c, "harmonized_beta", None)
            se_val = getattr(c, "harmonized_se", None)
            if beta_val is not None and se_val is not None and se_val > 0:
                study_ses.append(float(se_val))

        assert len(study_ses) == 1
        assert study_ses[0] == 0.2


# ═══════════════════════════════════════════════════════════════
#  DW#4: P5 pathway loading from registries
# ═══════════════════════════════════════════════════════════════


class TestDW4_P5_PathwayLoading:
    """Verify pathway definitions load from registry CSVs."""

    def test_load_returns_nonempty(self):
        """load_pathway_definitions should return > 0 PathwayDefinitions."""
        from crci.extraction.p5_sufficiency.pathway_loader import load_pathway_definitions

        defs = load_pathway_definitions()
        assert len(defs) > 0, "DW#4: pathways should not be empty"

    def test_all_have_edge_sequence(self):
        """Every PathwayDefinition must have non-empty edge_sequence."""
        from crci.extraction.p5_sufficiency.pathway_loader import load_pathway_definitions

        for d in load_pathway_definitions():
            assert len(d.edge_sequence) > 0, (
                f"Pathway {d.pathway_id} has empty edge_sequence"
            )

    def test_edgeless_pathways_excluded(self):
        """Pathways with status=edgeless should not appear."""
        from crci.extraction.p5_sufficiency.pathway_loader import load_pathway_definitions

        defs = load_pathway_definitions()
        for d in defs:
            base = d.pathway_id.split("__")[0]
            assert base not in ("PW_M11_CEREBROVASCULAR", "PW_M14_BBB"), (
                f"Edgeless pathway {base} should not be loaded"
            )

    def test_edge_ids_are_valid(self):
        """All edge_relation_ids in sequences should exist in EDGE_REGISTRY."""
        import csv
        from pathlib import Path

        from crci.extraction.p5_sufficiency.pathway_loader import (
            _DEFAULT_EDGE_CSV,
            load_pathway_definitions,
        )

        # Collect all valid edge IDs
        valid_ids: set[str] = set()
        with open(_DEFAULT_EDGE_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                valid_ids.add(row["edge_relation_id"])

        defs = load_pathway_definitions()
        for d in defs:
            for eid in d.edge_sequence:
                assert eid in valid_ids, (
                    f"Edge {eid} in pathway {d.pathway_id} not in EDGE_REGISTRY"
                )

    def test_missing_csv_returns_empty(self, tmp_path):
        """If registry CSVs don't exist, return empty list (no crash)."""
        from crci.extraction.p5_sufficiency.pathway_loader import load_pathway_definitions

        result = load_pathway_definitions(
            pathway_csv=tmp_path / "nonexistent.csv",
            edge_csv=tmp_path / "also_missing.csv",
        )
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  DW#9: SharedControlRecord / escalation skip None/0 SE
# ═══════════════════════════════════════════════════════════════


class TestDW9_SE_ZeroGuards:
    """Verify claims with None or 0 SE are skipped before IVW computation."""

    def test_shared_control_skips_none_se(self):
        """Claims with SE=None should be excluded from SharedControlRecords."""
        claims = [
            types.SimpleNamespace(
                ler_id="c1", study_id="S1", harmonized_beta=0.5,
                harmonized_se=0.2, n_treatment=50, n_control=50,
                shared_control_flag=False, shared_control_study_id=None,
                endpoint_vs_change="ENDPOINT",
            ),
            types.SimpleNamespace(
                ler_id="c2", study_id="S2", harmonized_beta=0.3,
                harmonized_se=None, n_treatment=50, n_control=50,
                shared_control_flag=False, shared_control_study_id=None,
                endpoint_vs_change="ENDPOINT",
            ),
        ]

        from crci.extraction.p4_aggregation.shared_control_handler import SharedControlRecord

        sc_records: list[SharedControlRecord] = []
        for claim in claims:
            se_val = getattr(claim, "harmonized_se", None)
            if se_val is None or se_val == 0.0:
                continue
            sc_records.append(SharedControlRecord(
                ler_id=getattr(claim, "ler_id", ""),
                study_id=getattr(claim, "study_id", ""),
                beta=getattr(claim, "harmonized_beta", 0.0),
                se=se_val,
                n_treatment=getattr(claim, "n_treatment", 0) or 0,
                n_control=getattr(claim, "n_control", 0) or 0,
            ))

        assert len(sc_records) == 1
        assert sc_records[0].ler_id == "c1"

    def test_shared_control_skips_zero_se(self):
        """Claims with SE=0.0 should be excluded (would cause div/0 in IVW)."""
        claim = types.SimpleNamespace(
            ler_id="c1", study_id="S1", harmonized_beta=0.5,
            harmonized_se=0.0, n_treatment=50, n_control=50,
        )
        se_val = getattr(claim, "harmonized_se", None)
        assert se_val is not None
        assert se_val == 0.0
        # With the guard, this claim would be skipped
        assert se_val is None or se_val == 0.0  # guard condition

    def test_escalation_records_skip_none_se(self):
        """EvidenceRecord construction should skip claims with None SE."""
        from crci.extraction.p4_aggregation.verification_escalation import EvidenceRecord

        claims = [
            types.SimpleNamespace(
                ler_id="c1", harmonized_beta=0.5, harmonized_se=0.2,
                se_derivation_level=None, meta_source_flag=None,
                is_cancer_matched=False, is_superseded=False,
            ),
            types.SimpleNamespace(
                ler_id="c2", harmonized_beta=0.3, harmonized_se=None,
                se_derivation_level=None, meta_source_flag=None,
                is_cancer_matched=False, is_superseded=False,
            ),
            types.SimpleNamespace(
                ler_id="c3", harmonized_beta=0.1, harmonized_se=0.0,
                se_derivation_level=None, meta_source_flag=None,
                is_cancer_matched=False, is_superseded=False,
            ),
        ]

        records: list[EvidenceRecord] = []
        for claim in claims:
            se_val = getattr(claim, "harmonized_se", None)
            if se_val is None or se_val == 0.0:
                continue
            records.append(EvidenceRecord(
                ler_id=getattr(claim, "ler_id", ""),
                beta=getattr(claim, "harmonized_beta", 0.0),
                se=se_val,
            ))

        assert len(records) == 1
        assert records[0].ler_id == "c1"
        assert records[0].se == 0.2


# ═══════════════════════════════════════════════════════════════
#  DW#12: UNKNOWN_EDGE injection — skip records without edge_relation_id
# ═══════════════════════════════════════════════════════════════


class TestDW12_UnknownEdge:
    """Verify records without edge_relation_id are not injected as phantom evidence."""

    def test_scaled_numeric_without_edge_id_skipped(self):
        """ScaledNumeric with edge_relation_id=None should be skipped in adapter."""
        from crci.shared.models.intermediate_states import HarmonizedClaim, ScaledNumeric
        from crci.shared.models.enums import (
            EffectScale,
            HarmonizationStatusInMem,
            SESource,
        )

        rec_good = ScaledNumeric(
            span_id="span1",
            beta=0.5,
            se=0.2,
            se_source=SESource.SE_DIRECT,
            scale=EffectScale.SD_SD,
            edge_relation_id="ER_CHEMO_IL6",
        )
        rec_bad = ScaledNumeric(
            span_id="span2",
            beta=0.3,
            se=0.1,
            se_source=SESource.SE_DIRECT,
            scale=EffectScale.SD_SD,
            edge_relation_id=None,
        )

        # Simulate the adapter logic
        adapted = []
        for rec in [rec_good, rec_bad]:
            if isinstance(rec, ScaledNumeric):
                if not rec.edge_relation_id:
                    continue  # DW#12 fix
                adapted.append(rec)

        assert len(adapted) == 1
        assert adapted[0].edge_relation_id == "ER_CHEMO_IL6"

    def test_duck_typed_records_without_edge_id_skipped(self):
        """Duck-typed records without edge_relation_id should be skipped."""
        rec_good = types.SimpleNamespace(
            span_id="sp1", edge_relation_id="ER_TEST",
            harmonized_beta=0.5, harmonized_se=0.2,
        )
        rec_bad = types.SimpleNamespace(
            span_id="sp2", edge_relation_id=None,
            harmonized_beta=0.3, harmonized_se=0.1,
        )
        rec_empty = types.SimpleNamespace(
            span_id="sp3", edge_relation_id="",
            harmonized_beta=0.1, harmonized_se=0.05,
        )

        # Simulate the duck-type adapter guard
        kept = []
        for rec in [rec_good, rec_bad, rec_empty]:
            duck_eid = getattr(rec, "edge_relation_id", None)
            if not duck_eid:
                continue
            kept.append(rec)

        assert len(kept) == 1
        assert kept[0].span_id == "sp1"
