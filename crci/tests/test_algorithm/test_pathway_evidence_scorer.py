"""
Component: Test — Pathway Evidence Scorer (ALG-B6.5 EXTENSION)
Purpose: Verify ED-1, DS-1 formulas and Gate B-G6.5 with hand-computable values.

Tests:
    - ED computation with known quality grades and edge counts
    - Study deduplication per (study_id, edge_id)
    - Grade normalization (strip/upper)
    - DS computation with overlapping / non-overlapping pathways
    - DS eligibility alignment (ED + coverage) and no-comparator guard
    - Edge cases: empty pathways, no evidence, single pathway
    - Gate B-G6.5 warning behavior
    - Config constant usage (no hardcoded values)
    - Debug hook fields in output
"""
from __future__ import annotations

import logging
import math

import pytest

from crci.algorithm.chain_b_evidence.evidence_compiler import EvidenceRecord
from crci.algorithm.chain_b_evidence.pathway_evidence_scorer import (
    PathwayEvidenceScore,
    _build_evidence_vector,
    _compute_distinction_scores,
    _compute_edge_k_quality,
    _compute_evidence_density,
    _cosine_similarity,
    _precompute_k_quality_by_edge,
    score_pathway_evidence,
)
from crci.shared import config
from crci.shared.models.pathway_types import PathwayDef


# ═══════════════════════════════════════════════════════════════
#  Test Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_evidence(
    edge_id: str,
    study_id: str,
    quality_grade: str = "MODERATE",
) -> EvidenceRecord:
    """Create a minimal EvidenceRecord for testing."""
    return EvidenceRecord(
        study_id=study_id,
        edge_id=edge_id,
        beta=0.3,
        se=0.1,
        study_design="large_rct",
        publication_year=2020,
        sample_size=200,
        identification_status="identified",
        quality_grade=quality_grade,
        scope_weights={"cancer": 1.0, "phase": 1.0, "regimen": 1.0, "age": 1.0, "sex": 1.0},
        cancer_validation_status="validated_cancer",
        temporal_distance_days=0.0,
        outcome_type="subjective",
    )


def _make_pathway(
    pathway_id: str,
    edge_ids: list[str] | tuple[str, ...],
) -> PathwayDef:
    """Create a minimal PathwayDef for testing."""
    return PathwayDef(
        pathway_id=pathway_id,
        pathway_label=f"Test {pathway_id}",
        tier="mechanistic_model_implied",
        edge_ids=tuple(edge_ids),
    )


# ═══════════════════════════════════════════════════════════════
#  Test: Quality-Weighted Count (ED inner sum)
# ═══════════════════════════════════════════════════════════════


class TestQualityWeightedCount:
    """Test _compute_edge_k_quality (ED-1 inner sum) with study dedup."""

    def test_single_high_study(self) -> None:
        """One HIGH study → weight = 1.0."""
        records = [_make_evidence("e1", "s1", "HIGH")]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)

    def test_two_moderate_studies(self) -> None:
        """Two MODERATE studies (different study_ids) → 2 × 0.75 = 1.5."""
        records = [
            _make_evidence("e1", "s1", "MODERATE"),
            _make_evidence("e1", "s2", "MODERATE"),
        ]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(2 * config.ED_QUALITY_WEIGHT_MODERATE)

    def test_mixed_grades(self) -> None:
        """HIGH + LOW → 1.0 + 0.5 = 1.5."""
        records = [
            _make_evidence("e1", "s1", "HIGH"),
            _make_evidence("e1", "s2", "LOW"),
        ]
        result = _compute_edge_k_quality("e1", records)
        expected = config.ED_QUALITY_WEIGHT_HIGH + config.ED_QUALITY_WEIGHT_LOW
        assert result == pytest.approx(expected)

    def test_no_evidence(self) -> None:
        """No evidence for edge → 0.0."""
        result = _compute_edge_k_quality("e_missing", [])
        assert result == 0.0

    def test_unknown_grade_defaults_to_very_low(self) -> None:
        """Unknown quality_grade → VERY_LOW weight + warning."""
        records = [_make_evidence("e1", "s1", "UNKNOWN_GRADE")]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_VERY_LOW)

    def test_dedup_same_study_same_edge(self) -> None:
        """Same study_id twice for same edge (multi-outcome) → counted ONCE.

        Study s1 appears twice with MODERATE and HIGH grades.
        Max weight = HIGH = 1.0.  Not 1.0 + 0.75 = 1.75.
        """
        records = [
            _make_evidence("e1", "s1", "MODERATE"),
            _make_evidence("e1", "s1", "HIGH"),
        ]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)

    def test_dedup_three_records_same_study(self) -> None:
        """Same study_id three times → only max weight counts.

        s1 appears with LOW, MODERATE, HIGH → max = HIGH = 1.0.
        """
        records = [
            _make_evidence("e1", "s1", "LOW"),
            _make_evidence("e1", "s1", "MODERATE"),
            _make_evidence("e1", "s1", "HIGH"),
        ]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)

    def test_dedup_different_studies_not_affected(self) -> None:
        """Different study_ids are summed normally.

        s1 × 2 (HIGH, LOW) → max = HIGH = 1.0
        s2 × 1 (MODERATE) → 0.75
        Total = 1.0 + 0.75 = 1.75
        """
        records = [
            _make_evidence("e1", "s1", "HIGH"),
            _make_evidence("e1", "s1", "LOW"),
            _make_evidence("e1", "s2", "MODERATE"),
        ]
        result = _compute_edge_k_quality("e1", records)
        expected = config.ED_QUALITY_WEIGHT_HIGH + config.ED_QUALITY_WEIGHT_MODERATE
        assert result == pytest.approx(expected)

    def test_grade_normalization_whitespace(self) -> None:
        """Quality grade with whitespace should be normalized."""
        records = [_make_evidence("e1", "s1", "  HIGH  ")]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)

    def test_grade_normalization_case(self) -> None:
        """Quality grade with mixed case should be normalized."""
        records = [_make_evidence("e1", "s1", "moderate")]
        result = _compute_edge_k_quality("e1", records)
        assert result == pytest.approx(config.ED_QUALITY_WEIGHT_MODERATE)


# ═══════════════════════════════════════════════════════════════
#  Test: Evidence Density (ED-1)
# ═══════════════════════════════════════════════════════════════


class TestEvidenceDensity:
    """Test _compute_evidence_density (ED-1 formula)."""

    def test_hand_computed_ed(self) -> None:
        """Pathway with 2 edges, each with 1 HIGH study.

        ED = (1.0 + 1.0) / 2 = 1.0
        """
        pw = _make_pathway("P1", ["e1", "e2"])
        k_quality = {"e1": config.ED_QUALITY_WEIGHT_HIGH,
                      "e2": config.ED_QUALITY_WEIGHT_HIGH}
        ed, n_total, n_with = _compute_evidence_density(pw, k_quality)
        assert ed == pytest.approx(1.0)
        assert n_total == 2
        assert n_with == 2

    def test_partial_coverage(self) -> None:
        """Pathway with 3 edges, only 1 has evidence.

        edge e1: k_quality = 1.0
        edge e2: k_quality = 0 (missing from dict)
        edge e3: k_quality = 0 (missing from dict)
        ED = (1.0 + 0.0 + 0.0) / 3 = 0.333...
        """
        pw = _make_pathway("P1", ["e1", "e2", "e3"])
        k_quality = {"e1": config.ED_QUALITY_WEIGHT_HIGH}
        ed, n_total, n_with = _compute_evidence_density(pw, k_quality)
        assert ed == pytest.approx(1.0 / 3.0)
        assert n_total == 3
        assert n_with == 1

    def test_zero_edges(self) -> None:
        """Pathway with no edges → ED = 0.0."""
        pw = _make_pathway("P1", [])
        ed, n_total, n_with = _compute_evidence_density(pw, {})
        assert ed == 0.0
        assert n_total == 0
        assert n_with == 0

    def test_multi_study_single_edge(self) -> None:
        """3 unique studies on 1 edge: HIGH + MODERATE + LOW.

        k_quality = 1.0 + 0.75 + 0.5 = 2.25
        ED = 2.25 / 1 = 2.25
        """
        pw = _make_pathway("P1", ["e1"])
        expected = (
            config.ED_QUALITY_WEIGHT_HIGH
            + config.ED_QUALITY_WEIGHT_MODERATE
            + config.ED_QUALITY_WEIGHT_LOW
        )
        k_quality = {"e1": expected}
        ed, n_total, n_with = _compute_evidence_density(pw, k_quality)
        assert ed == pytest.approx(expected)
        assert n_total == 1
        assert n_with == 1


# ═══════════════════════════════════════════════════════════════
#  Test: Cosine Similarity
# ═══════════════════════════════════════════════════════════════


class TestCosineSimilarity:
    """Test _cosine_similarity."""

    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_both_zero(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_anti_parallel(self) -> None:
        """Opposite direction → cosine = -1.0."""
        sim = _cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert sim == pytest.approx(-1.0)

    def test_hand_computed(self) -> None:
        """a = [3, 4], b = [4, 3].
        dot = 12+12 = 24; |a| = 5, |b| = 5
        cos = 24/25 = 0.96
        """
        sim = _cosine_similarity([3.0, 4.0], [4.0, 3.0])
        assert sim == pytest.approx(24.0 / 25.0)


# ═══════════════════════════════════════════════════════════════
#  Test: Distinction Score (DS-1)
# ═══════════════════════════════════════════════════════════════


class TestDistinctionScore:
    """Test _compute_distinction_scores (DS-1 formula)."""

    def test_two_non_overlapping_pathways(self) -> None:
        """Two pathways with completely different edges → DS ≈ 1.0.

        P1 has edges e1, e2 with evidence.
        P2 has edges e3, e4 with evidence.
        Cosine similarity of non-overlapping vectors = 0.0.
        DS(P1) = 1 - 0 = 1.0, DS(P2) = 1 - 0 = 1.0.
        """
        pw1 = _make_pathway("P1", ["e1", "e2"])
        pw2 = _make_pathway("P2", ["e3", "e4"])
        k_quality = {
            "e1": config.ED_QUALITY_WEIGHT_HIGH,
            "e2": config.ED_QUALITY_WEIGHT_HIGH,
            "e3": config.ED_QUALITY_WEIGHT_HIGH,
            "e4": config.ED_QUALITY_WEIGHT_HIGH,
        }
        evidence_densities = {"P1": 1.0, "P2": 1.0}  # both adequate
        edge_coverages = {"P1": 1.0, "P2": 1.0}

        ds_vals, ds_elig, ds_comp = _compute_distinction_scores(
            [pw1, pw2], k_quality, evidence_densities, edge_coverages,
        )
        assert ds_vals["P1"] == pytest.approx(1.0)
        assert ds_vals["P2"] == pytest.approx(1.0)
        assert ds_elig["P1"] is True
        assert ds_elig["P2"] is True
        assert ds_comp["P1"] == 1
        assert ds_comp["P2"] == 1

    def test_identical_evidence_pattern(self) -> None:
        """Two pathways with identical edge sets → DS = 0.0.

        Same edges, same evidence → cosine similarity = 1.0.
        DS(P) = 1 - 1 = 0.0.
        """
        pw1 = _make_pathway("P1", ["e1", "e2"])
        pw2 = _make_pathway("P2", ["e1", "e2"])
        k_quality = {
            "e1": config.ED_QUALITY_WEIGHT_HIGH,
            "e2": config.ED_QUALITY_WEIGHT_HIGH,
        }
        evidence_densities = {"P1": 1.0, "P2": 1.0}
        edge_coverages = {"P1": 1.0, "P2": 1.0}

        ds_vals, ds_elig, ds_comp = _compute_distinction_scores(
            [pw1, pw2], k_quality, evidence_densities, edge_coverages,
        )
        assert ds_vals["P1"] == pytest.approx(0.0)
        assert ds_vals["P2"] == pytest.approx(0.0)

    def test_insufficient_active_pathways(self) -> None:
        """Only 1 adequate pathway (need ≥ 2) → all DS = 0.0."""
        pw1 = _make_pathway("P1", ["e1"])
        pw2 = _make_pathway("P2", ["e2"])
        k_quality = {"e1": config.ED_QUALITY_WEIGHT_HIGH}
        evidence_densities = {"P1": 1.0, "P2": 0.0}
        edge_coverages = {"P1": 1.0, "P2": 0.0}

        ds_vals, ds_elig, ds_comp = _compute_distinction_scores(
            [pw1, pw2], k_quality, evidence_densities, edge_coverages,
        )
        assert ds_vals["P1"] == 0.0
        assert ds_vals["P2"] == 0.0

    def test_low_edge_coverage_gets_zero_ds(self) -> None:
        """Pathway with edge coverage below MIN_EDGE_COVERAGE_FOR_DS → DS = 0.0."""
        # P1: 10 edges, only 1 with evidence → coverage = 0.1 < 0.3
        pw1 = _make_pathway("P1", [f"e{i}" for i in range(10)])
        pw2 = _make_pathway("P2", ["e20", "e21"])
        k_quality = {
            "e0": config.ED_QUALITY_WEIGHT_HIGH,
            "e20": config.ED_QUALITY_WEIGHT_HIGH,
            "e21": config.ED_QUALITY_WEIGHT_HIGH,
        }
        # P1 ED = 1.0/10 = 0.1, P2 ED = 2.0/2 = 1.0
        # P1 fails ED threshold → only 1 eligible → all DS = 0.0
        evidence_densities = {"P1": 0.1, "P2": 1.0}
        edge_coverages = {"P1": 0.1, "P2": 1.0}

        ds_vals, ds_elig, ds_comp = _compute_distinction_scores(
            [pw1, pw2], k_quality, evidence_densities, edge_coverages,
        )
        assert ds_vals["P1"] == 0.0
        assert ds_vals["P2"] == 0.0  # only 1 eligible globally, so all DS = 0.0

    def test_no_comparator_guard(self) -> None:
        """Pathway meets eligibility but only comparator doesn't → DS = 0.0.

        P1: ED=1.0, coverage=1.0 → eligible
        P2: ED=1.0, coverage=0.1 → NOT eligible (coverage too low)
        P1 has no eligible comparator → DS = 0.0 (not "highly distinct").
        """
        pw1 = _make_pathway("P1", ["e1", "e2"])
        pw2 = _make_pathway("P2", ["e3", "e4", "e5", "e6", "e7",
                                   "e8", "e9", "e10", "e11", "e12"])
        k_quality = {
            "e1": 1.0, "e2": 1.0,
            "e3": 1.0,  # only 1/10 edges → coverage = 0.1
        }
        # Force: P1 eligible, P2 fails coverage
        evidence_densities = {"P1": 1.0, "P2": 1.0}
        edge_coverages = {"P1": 1.0, "P2": 0.1}

        ds_vals, ds_elig, ds_comp = _compute_distinction_scores(
            [pw1, pw2], k_quality, evidence_densities, edge_coverages,
        )
        # P2 is ineligible (coverage < 0.3), so only 1 eligible globally
        # → falls below MIN_ACTIVE_PATHWAYS_FOR_DS (2) → all DS = 0.0
        assert ds_vals["P1"] == 0.0
        assert ds_elig["P1"] is True  # P1 is individually eligible
        assert ds_comp["P1"] == 0  # but no comparators available


# ═══════════════════════════════════════════════════════════════
#  Test: End-to-End score_pathway_evidence
# ═══════════════════════════════════════════════════════════════


class TestScorePathwayEvidence:
    """Test the top-level score_pathway_evidence orchestrator."""

    def test_basic_two_pathways(self) -> None:
        """Two pathways with non-overlapping evidence.

        P1: edges [e1, e2], each with 1 HIGH study → ED = 1.0
        P2: edges [e3, e4], each with 1 MODERATE study → ED = 0.75
        Both adequate (ED > 0.5).
        Non-overlapping → DS = 1.0 for both (orthogonal evidence).
        """
        pw1 = _make_pathway("P1", ["e1", "e2"])
        pw2 = _make_pathway("P2", ["e3", "e4"])
        records = [
            _make_evidence("e1", "s1", "HIGH"),
            _make_evidence("e2", "s2", "HIGH"),
            _make_evidence("e3", "s3", "MODERATE"),
            _make_evidence("e4", "s4", "MODERATE"),
        ]

        scores = score_pathway_evidence([pw1, pw2], records)

        assert len(scores) == 2

        # P1 checks
        s1 = scores["P1"]
        assert s1.evidence_density == pytest.approx(1.0)
        assert s1.n_edges_total == 2
        assert s1.n_edges_with_evidence == 2
        assert s1.edge_coverage == pytest.approx(1.0)
        assert s1.is_adequate is True
        assert s1.distinction_score == pytest.approx(1.0)
        assert s1.ds_eligible is True
        assert s1.ds_comparators == 1

        # P2 checks
        s2 = scores["P2"]
        assert s2.evidence_density == pytest.approx(config.ED_QUALITY_WEIGHT_MODERATE)
        assert s2.is_adequate is True
        assert s2.distinction_score == pytest.approx(1.0)
        assert s2.ds_eligible is True

    def test_empty_pathways(self) -> None:
        """Pathway with no edges → all zeros."""
        pw = _make_pathway("P_empty", [])
        scores = score_pathway_evidence([pw], [])
        s = scores["P_empty"]
        assert s.evidence_density == 0.0
        assert s.distinction_score == 0.0
        assert s.n_edges_total == 0
        assert s.is_adequate is False
        assert s.ds_eligible is False

    def test_no_evidence_records(self) -> None:
        """Pathways exist but no evidence → all ED = 0, DS = 0."""
        pw1 = _make_pathway("P1", ["e1", "e2"])
        pw2 = _make_pathway("P2", ["e3"])
        scores = score_pathway_evidence([pw1, pw2], [])

        assert scores["P1"].evidence_density == 0.0
        assert scores["P1"].distinction_score == 0.0
        assert scores["P1"].is_adequate is False
        assert scores["P2"].evidence_density == 0.0

    def test_single_pathway(self) -> None:
        """Single pathway → DS = 0.0 (no other to compare against,
        and MIN_ACTIVE_PATHWAYS_FOR_DS requires ≥ 2)."""
        pw = _make_pathway("P1", ["e1"])
        records = [_make_evidence("e1", "s1", "HIGH")]
        scores = score_pathway_evidence([pw], records)

        assert scores["P1"].evidence_density == pytest.approx(1.0)
        assert scores["P1"].distinction_score == 0.0
        assert scores["P1"].is_adequate is True
        assert scores["P1"].ds_eligible is True
        assert scores["P1"].ds_comparators == 0  # no comparators available

    def test_all_pathways_returned(self) -> None:
        """Every input pathway must appear in output."""
        pathways = [_make_pathway(f"P{i}", [f"e{i}"]) for i in range(5)]
        scores = score_pathway_evidence(pathways, [])
        assert set(scores.keys()) == {f"P{i}" for i in range(5)}

    def test_dedup_in_end_to_end(self) -> None:
        """Same study appearing twice for same edge → counted once.

        P1: edge e1 with study s1 (HIGH + MODERATE records)
        Dedup: s1 counted once with max weight = HIGH = 1.0.
        ED = 1.0 / 1 = 1.0 (not 1.75).
        """
        pw = _make_pathway("P1", ["e1"])
        records = [
            _make_evidence("e1", "s1", "HIGH"),
            _make_evidence("e1", "s1", "MODERATE"),  # duplicate study
        ]
        scores = score_pathway_evidence([pw], records)
        assert scores["P1"].evidence_density == pytest.approx(
            config.ED_QUALITY_WEIGHT_HIGH,  # not HIGH + MODERATE
        )

    def test_debug_hooks_populated(self) -> None:
        """Verify tier, status, expected_edge_count from PathwayDef."""
        pw = PathwayDef(
            pathway_id="PW_TEST",
            pathway_label="Test Pathway",
            tier="mechanistic_model_implied",
            edge_ids=("e1",),
            status="connected",
            expected_edge_count=5,
        )
        records = [_make_evidence("e1", "s1", "HIGH")]
        scores = score_pathway_evidence([pw], records)

        s = scores["PW_TEST"]
        assert s.tier == "mechanistic_model_implied"
        assert s.status == "connected"
        assert s.expected_edge_count == 5


# ═══════════════════════════════════════════════════════════════
#  Test: Precompute Cache
# ═══════════════════════════════════════════════════════════════


class TestPrecomputeKQuality:
    """Test _precompute_k_quality_by_edge (caching + dedup layer)."""

    def test_basic_precompute(self) -> None:
        """Precompute returns correct k_quality for each edge."""
        evidence_by_edge = {
            "e1": [_make_evidence("e1", "s1", "HIGH")],
            "e2": [_make_evidence("e2", "s2", "MODERATE"),
                   _make_evidence("e2", "s3", "LOW")],
        }
        result = _precompute_k_quality_by_edge(evidence_by_edge)
        assert result["e1"] == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)
        assert result["e2"] == pytest.approx(
            config.ED_QUALITY_WEIGHT_MODERATE + config.ED_QUALITY_WEIGHT_LOW,
        )

    def test_precompute_dedup(self) -> None:
        """Same study_id across edges gets deduped per edge."""
        evidence_by_edge = {
            "e1": [_make_evidence("e1", "s1", "HIGH"),
                   _make_evidence("e1", "s1", "LOW")],
        }
        result = _precompute_k_quality_by_edge(evidence_by_edge)
        # Only max weight for s1: HIGH = 1.0
        assert result["e1"] == pytest.approx(config.ED_QUALITY_WEIGHT_HIGH)

    def test_precompute_empty(self) -> None:
        """Empty evidence → empty dict."""
        result = _precompute_k_quality_by_edge({})
        assert result == {}

    def test_dedup_warning_not_spammed(self, caplog) -> None:
        """Same study with unknown grade should only warn once per edge."""
        evidence_by_edge = {
            "e1": [
                _make_evidence("e1", "s1", "BOGUS_GRADE"),
                _make_evidence("e1", "s1", "BOGUS_GRADE"),
                _make_evidence("e1", "s1", "BOGUS_GRADE"),
            ],
        }
        with caplog.at_level(logging.WARNING):
            _precompute_k_quality_by_edge(evidence_by_edge)

        # Should have exactly 1 warning for s1, not 3
        warning_count = sum(
            1 for r in caplog.records
            if "unknown quality_grade" in r.message and "s1" in r.message
        )
        assert warning_count == 1


# ═══════════════════════════════════════════════════════════════
#  Test: Gate B-G6.5
# ═══════════════════════════════════════════════════════════════


class TestGateBG65:
    """Test Gate B-G6.5 (soft gate — warning only)."""

    def test_gate_warns_on_insufficient_pathways(self, caplog) -> None:
        """All pathways with ED=0 → warning logged."""
        pw = _make_pathway("P1", ["e1"])
        with caplog.at_level(logging.WARNING):
            scores = score_pathway_evidence([pw], [])
        assert any("B-G6.5 WARNING" in r.message for r in caplog.records)

    def test_gate_passes_with_adequate(self, caplog) -> None:
        """At least GATE_B65_MIN_ADEQUATE_PATHWAYS adequate → info, no warning."""
        pw = _make_pathway("P1", ["e1"])
        records = [_make_evidence("e1", "s1", "HIGH")]
        with caplog.at_level(logging.INFO):
            scores = score_pathway_evidence([pw], records)
        assert not any("B-G6.5 WARNING" in r.message for r in caplog.records)
        assert any("B-G6.5 PASSED" in r.message for r in caplog.records)


# ═══════════════════════════════════════════════════════════════
#  Test: Config Constants (no hardcoded values)
# ═══════════════════════════════════════════════════════════════


class TestConfigUsage:
    """Verify the scorer uses config constants, not hardcoded values."""

    def test_adequacy_threshold_from_config(self) -> None:
        """is_adequate should match comparison against config constant."""
        pw = _make_pathway("P1", ["e1", "e2"])
        # Create evidence that gives ED exactly at the threshold boundary
        # 1 MODERATE study across 2 edges → ED = 0.75/2 = 0.375
        # With MIN_PATHWAY_EVIDENCE_DENSITY = 0.5, this is NOT adequate
        records = [_make_evidence("e1", "s1", "MODERATE")]
        scores = score_pathway_evidence([pw], records)

        ed = scores["P1"].evidence_density
        expected_adequate = ed >= config.MIN_PATHWAY_EVIDENCE_DENSITY
        assert scores["P1"].is_adequate == expected_adequate

    def test_quality_weights_match_config(self) -> None:
        """ED computation must use config quality weights."""
        pw = _make_pathway("P1", ["e1"])
        # 1 VERY_LOW study → k_quality = 0.25 → ED = 0.25/1 = 0.25
        records = [_make_evidence("e1", "s1", "VERY_LOW")]
        scores = score_pathway_evidence([pw], records)
        assert scores["P1"].evidence_density == pytest.approx(
            config.ED_QUALITY_WEIGHT_VERY_LOW,
        )
