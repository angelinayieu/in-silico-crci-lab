"""
Tests for R4: Per-Study Variance Decomposition.

Verifies that the F3 literature variance is decomposed into per-study
shares using weight-proportional allocation, and that the pipeline
threads per_study_variance_contrib through to the output contract.
"""
from __future__ import annotations

import math

import pytest

from crci.algorithm.chain_f_analytics.evsi import (
    VarianceState,
    _compute_literature_variance,
    compute_variance_decomposition,
)
from crci.runtime.report_assembler import _build_variance_decomposition
from crci.shared.models.output_contracts import VarianceDecomposition


# ═══════════════════════════════════════════════════════════════
#  _compute_literature_variance — per-study decomposition
# ═══════════════════════════════════════════════════════════════


class TestComputeLiteratureVariancePerStudy:
    """R4: per-study decomposition inside _compute_literature_variance."""

    def test_no_study_weights_returns_empty(self):
        """Without edge_study_weights, per_study dict is empty."""
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.04}, None, None,
        )
        assert per_study == {}
        assert per_edge == {"E001": 0.04}
        assert v == pytest.approx(0.04)

    def test_single_edge_single_study(self):
        """One study with weight 1.0 gets 100% of edge variance."""
        weights = {
            "E001": [{"ler_id": "LER-001", "weight_normalized": 1.0}],
        }
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.09}, None, weights,
        )
        assert per_study["E001"]["LER-001"] == pytest.approx(0.09)

    def test_two_studies_equal_weight(self):
        """Two equal-weight studies each get 50% of edge variance."""
        weights = {
            "E001": [
                {"ler_id": "LER-001", "weight_normalized": 0.5},
                {"ler_id": "LER-002", "weight_normalized": 0.5},
            ],
        }
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.10}, None, weights,
        )
        assert per_study["E001"]["LER-001"] == pytest.approx(0.05)
        assert per_study["E001"]["LER-002"] == pytest.approx(0.05)

    def test_three_studies_unequal_weights(self):
        """Hand-computable: 3 studies with weights 0.5, 0.3, 0.2.

        Edge τ² = 0.20, sensitivity = 1.0
        Edge contrib = 1.0² × 0.20 = 0.20
        Study shares: 0.5×0.20=0.10, 0.3×0.20=0.06, 0.2×0.20=0.04
        Sum = 0.20 ✓
        """
        weights = {
            "E001": [
                {"ler_id": "LER-A", "weight_normalized": 0.5},
                {"ler_id": "LER-B", "weight_normalized": 0.3},
                {"ler_id": "LER-C", "weight_normalized": 0.2},
            ],
        }
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.20}, None, weights,
        )
        shares = per_study["E001"]
        assert shares["LER-A"] == pytest.approx(0.10)
        assert shares["LER-B"] == pytest.approx(0.06)
        assert shares["LER-C"] == pytest.approx(0.04)
        # Sum of per-study shares equals edge contribution
        assert sum(shares.values()) == pytest.approx(per_edge["E001"])

    def test_sensitivity_scales_per_study(self):
        """With sensitivity = 2.0, edge contrib = 4 × τ²; per-study scales too.

        τ² = 0.05, sensitivity = 2.0 → edge contrib = 4 × 0.05 = 0.20
        Two studies w=[0.7, 0.3] → shares = [0.14, 0.06]
        """
        weights = {
            "E001": [
                {"ler_id": "LER-X", "weight_normalized": 0.7},
                {"ler_id": "LER-Y", "weight_normalized": 0.3},
            ],
        }
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.05}, {"E001": 2.0}, weights,
        )
        assert per_edge["E001"] == pytest.approx(0.20)
        assert per_study["E001"]["LER-X"] == pytest.approx(0.14)
        assert per_study["E001"]["LER-Y"] == pytest.approx(0.06)

    def test_multi_edge_per_study(self):
        """Per-study decomposition across multiple edges."""
        tau_sq = {"E001": 0.10, "E002": 0.04}
        weights = {
            "E001": [
                {"ler_id": "LER-1", "weight_normalized": 0.6},
                {"ler_id": "LER-2", "weight_normalized": 0.4},
            ],
            "E002": [
                {"ler_id": "LER-3", "weight_normalized": 1.0},
            ],
        }
        v, per_edge, per_study = _compute_literature_variance(
            tau_sq, None, weights,
        )
        # E001: 0.10 → LER-1=0.06, LER-2=0.04
        assert per_study["E001"]["LER-1"] == pytest.approx(0.06)
        assert per_study["E001"]["LER-2"] == pytest.approx(0.04)
        # E002: 0.04 → LER-3=0.04
        assert per_study["E002"]["LER-3"] == pytest.approx(0.04)
        # Total per-study sums equal total lit variance
        all_study_sum = sum(
            s for edge_studies in per_study.values() for s in edge_studies.values()
        )
        assert all_study_sum == pytest.approx(v)

    def test_edge_without_study_weights_excluded(self):
        """If an edge has no study weights entry, it's not in per_study."""
        weights = {
            "E001": [{"ler_id": "LER-1", "weight_normalized": 1.0}],
            # E002 not in weights
        }
        v, per_edge, per_study = _compute_literature_variance(
            {"E001": 0.10, "E002": 0.05}, None, weights,
        )
        assert "E001" in per_study
        assert "E002" not in per_study


# ═══════════════════════════════════════════════════════════════
#  VarianceState — per_study_variance_contrib field
# ═══════════════════════════════════════════════════════════════


class TestVarianceStatePerStudy:
    """VarianceState carries per_study_variance_contrib."""

    def test_default_empty(self):
        """Default per_study_variance_contrib is empty dict."""
        vs = VarianceState(
            total_variance=1.0,
            literature_pct=0.5, measurement_pct=0.2,
            structural_pct=0.1, proxy_pct=0.1, missing_pct=0.1,
            literature_variance=0.5, measurement_variance=0.2,
            structural_variance=0.1, proxy_variance=0.1, missing_variance=0.1,
            top_reducible=[], per_edge_variance_contrib={},
        )
        assert vs.per_study_variance_contrib == {}

    def test_populated(self):
        """per_study_variance_contrib can be populated."""
        per_study = {"E001": {"LER-1": 0.06, "LER-2": 0.04}}
        vs = VarianceState(
            total_variance=1.0,
            literature_pct=0.5, measurement_pct=0.2,
            structural_pct=0.1, proxy_pct=0.1, missing_pct=0.1,
            literature_variance=0.5, measurement_variance=0.2,
            structural_variance=0.1, proxy_variance=0.1, missing_variance=0.1,
            top_reducible=[], per_edge_variance_contrib={"E001": 0.10},
            per_study_variance_contrib=per_study,
        )
        assert vs.per_study_variance_contrib["E001"]["LER-1"] == 0.06


# ═══════════════════════════════════════════════════════════════
#  compute_variance_decomposition — end-to-end with study weights
# ═══════════════════════════════════════════════════════════════


class TestComputeVarianceDecompositionPerStudy:
    """E2E: compute_variance_decomposition threads study weights."""

    def test_without_study_weights(self):
        """Without study weights, per_study_variance_contrib is empty."""
        result = compute_variance_decomposition(
            edge_tau_squared={"E001": 0.10},
        )
        assert result.per_study_variance_contrib == {}

    def test_with_study_weights(self):
        """With study weights, per_study_variance_contrib is populated."""
        weights = {
            "E001": [
                {"ler_id": "LER-A", "weight_normalized": 0.6},
                {"ler_id": "LER-B", "weight_normalized": 0.4},
            ],
        }
        result = compute_variance_decomposition(
            edge_tau_squared={"E001": 0.10},
            edge_study_weights=weights,
        )
        ps = result.per_study_variance_contrib
        assert "E001" in ps
        assert ps["E001"]["LER-A"] == pytest.approx(0.06)
        assert ps["E001"]["LER-B"] == pytest.approx(0.04)


# ═══════════════════════════════════════════════════════════════
#  _build_variance_decomposition — threads to output contract
# ═══════════════════════════════════════════════════════════════


class TestBuildVarianceDecompositionPerStudy:
    """R4: report_assembler threads per_study to VarianceDecomposition."""

    def _make_variance_state(self, per_study=None) -> VarianceState:
        return VarianceState(
            total_variance=1.0,
            literature_pct=0.4, measurement_pct=0.2,
            structural_pct=0.15, proxy_pct=0.15, missing_pct=0.1,
            literature_variance=0.4, measurement_variance=0.2,
            structural_variance=0.15, proxy_variance=0.15, missing_variance=0.1,
            top_reducible=[], per_edge_variance_contrib={"E001": 0.4},
            per_study_variance_contrib=per_study or {},
        )

    def test_none_variance_returns_none(self):
        result = _build_variance_decomposition(None, "run-1")
        assert result is None

    def test_empty_per_study(self):
        vs = self._make_variance_state()
        result = _build_variance_decomposition(vs, "run-1")
        assert isinstance(result, VarianceDecomposition)
        assert result.per_study_contributions == {}

    def test_per_study_threaded(self):
        per_study = {"E001": {"LER-1": 0.24, "LER-2": 0.16}}
        vs = self._make_variance_state(per_study)
        result = _build_variance_decomposition(vs, "run-1")
        assert result.per_study_contributions == per_study

    def test_per_study_sums_match_per_edge(self):
        """Per-study shares within each edge sum to that edge's contribution."""
        per_study = {"E001": {"LER-1": 0.24, "LER-2": 0.16}}
        vs = self._make_variance_state(per_study)
        result = _build_variance_decomposition(vs, "run-1")
        for edge_id, study_shares in result.per_study_contributions.items():
            assert sum(study_shares.values()) == pytest.approx(
                result.per_edge_contributions[edge_id],
            )


# ═══════════════════════════════════════════════════════════════
#  VarianceDecomposition output contract — field exists
# ═══════════════════════════════════════════════════════════════


class TestVarianceDecompositionOutputContract:
    """R4: VarianceDecomposition has per_study_contributions field."""

    def test_default_empty(self):
        vd = VarianceDecomposition(run_id="r1")
        assert vd.per_study_contributions == {}

    def test_populated(self):
        vd = VarianceDecomposition(
            run_id="r1",
            per_study_contributions={"E001": {"LER-1": 0.05}},
        )
        assert vd.per_study_contributions["E001"]["LER-1"] == 0.05
