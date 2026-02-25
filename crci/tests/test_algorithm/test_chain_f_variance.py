"""Tests for ALG-F3 Five-Source Variance Decomposition.

Covers:
    F3a: Literature heterogeneity (τ² weighted by sensitivity)
    F3b: Measurement noise (instrument reliability)
    F3c: Structural model uncertainty (σ²_struct)
    F3d: Proxy imprecision (R²_proxy)
    F3e: Missing observation variance (Formula F-5)
    F3f: Normalization to percentages
    Gate F-G3: 5 components sum ≈ total, all ≥ 0
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_f_analytics.evsi import (
    ReducibleSource,
    VarianceState,
    _compute_literature_variance,
    _compute_measurement_variance,
    _compute_missing_variance,
    _compute_proxy_variance,
    _compute_structural_variance,
    _normalize_and_report,
    _validate_gate_f_g3,
    compute_variance_decomposition,
)


# ═══════════════════════════════════════════════════════════════
#  Test F3a: Literature Heterogeneity
# ═══════════════════════════════════════════════════════════════


class TestLiteratureVariance:
    """Test literature heterogeneity component."""

    def test_basic_tau_squared(self):
        """V_lit = Σ τ²_e (uniform sensitivity)."""
        tau_sq = {"e1": 0.1, "e2": 0.2}
        v, per_edge = _compute_literature_variance(tau_sq)
        assert abs(v - 0.3) < 1e-10
        assert abs(per_edge["e1"] - 0.1) < 1e-10
        assert abs(per_edge["e2"] - 0.2) < 1e-10

    def test_with_sensitivity(self):
        """V_lit = Σ (∂θ/∂β_e)² × τ²_e.

        e1: sensitivity=2, τ²=0.1 → 4 × 0.1 = 0.4
        e2: sensitivity=0.5, τ²=0.2 → 0.25 × 0.2 = 0.05
        Total = 0.45
        """
        tau_sq = {"e1": 0.1, "e2": 0.2}
        sensitivities = {"e1": 2.0, "e2": 0.5}
        v, _ = _compute_literature_variance(tau_sq, sensitivities)
        assert abs(v - 0.45) < 1e-10

    def test_empty(self):
        v, per_edge = _compute_literature_variance({})
        assert v == 0.0
        assert len(per_edge) == 0


# ═══════════════════════════════════════════════════════════════
#  Test F3b: Measurement Noise
# ═══════════════════════════════════════════════════════════════


class TestMeasurementVariance:
    """Test measurement noise component."""

    def test_single_instrument(self):
        """σ²_y = b² × (1−α)/α.

        α=0.8, b=1.0 → σ²_y = 1 × 0.2/0.8 = 0.25
        weight = 1/1 = 1.0
        V_meas = 0.25 × 1.0² = 0.25
        """
        v = _compute_measurement_variance({"inst1": 0.8})
        expected = 1.0 * (1.0 - 0.8) / 0.8 * 1.0 ** 2
        assert abs(v - expected) < 1e-10

    def test_two_instruments(self):
        """Weight = 1/n_instruments = 0.5."""
        v = _compute_measurement_variance({"i1": 0.8, "i2": 0.9})
        # i1: (1-0.8)/0.8 = 0.25, weight=0.5 → 0.25 × 0.25 = 0.0625
        # i2: (1-0.9)/0.9 ≈ 0.111, weight=0.5 → 0.111 × 0.25 ≈ 0.0278
        expected = (0.25 * 0.25 + (1.0 / 9.0) * 0.25)
        assert abs(v - expected) < 1e-6

    def test_empty(self):
        v = _compute_measurement_variance({})
        assert v == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F3c: Structural Uncertainty
# ═══════════════════════════════════════════════════════════════


class TestStructuralVariance:
    """Test structural model uncertainty component."""

    def test_default_value(self):
        v = _compute_structural_variance(n_edges=10)
        assert abs(v - config.SIGMA_SQ_STRUCTURAL_DEFAULT) < 1e-10

    def test_per_edge_values(self):
        v = _compute_structural_variance({"e1": 0.3, "e2": 0.5})
        assert abs(v - 0.4) < 1e-10  # mean(0.3, 0.5) = 0.4

    def test_no_edges(self):
        v = _compute_structural_variance(n_edges=0)
        assert v == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F3d: Proxy Imprecision
# ═══════════════════════════════════════════════════════════════


class TestProxyVariance:
    """Test proxy imprecision component."""

    def test_single_proxy(self):
        """V_proxy = Var(θ) × (1 − R²).

        R²=0.8, Var=1.0 → V = 0.2
        """
        v = _compute_proxy_variance({"n1": 0.8})
        assert abs(v - 0.2) < 1e-10

    def test_multiple_proxies(self):
        """Sum across nodes."""
        v = _compute_proxy_variance({"n1": 0.8, "n2": 0.6})
        # n1: 1.0 × (1-0.8) = 0.2
        # n2: 1.0 × (1-0.6) = 0.4
        assert abs(v - 0.6) < 1e-10

    def test_perfect_proxy(self):
        """R² = 1.0 → V = 0."""
        v = _compute_proxy_variance({"n1": 1.0})
        assert abs(v) < 1e-10

    def test_empty(self):
        v = _compute_proxy_variance({})
        assert v == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F3e: Missing Observation Variance
# ═══════════════════════════════════════════════════════════════


class TestMissingVariance:
    """Test missing observation variance component."""

    def test_formula_f5(self):
        """ΔVar = Σ_unobs Cov(target, i)² / Var(i).

        3×3 covariance matrix, node 2 unobserved, target=[0].
        Cov(0,2)=0.3, Var(2)=0.5
        ΔVar = 0.3²/0.5 = 0.09/0.5 = 0.18
        """
        cov = np.array([
            [1.0, 0.2, 0.3],
            [0.2, 0.8, 0.1],
            [0.3, 0.1, 0.5],
        ])
        observed = np.array([True, True, False])
        v = _compute_missing_variance(cov, observed, target_indices=[0])
        expected = 0.3 ** 2 / 0.5
        assert abs(v - expected) < 1e-10

    def test_all_observed(self):
        """All observed → V_missing = 0."""
        cov = np.eye(3) * 0.5
        observed = np.array([True, True, True])
        v = _compute_missing_variance(cov, observed)
        assert v == 0.0

    def test_none_covariance(self):
        v = _compute_missing_variance(None, None)
        assert v == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F3f: Normalization
# ═══════════════════════════════════════════════════════════════


class TestNormalization:
    """Test normalization to percentages."""

    def test_percentages_sum_to_1(self):
        total, lit, meas, struct, proxy, missing, _ = _normalize_and_report(
            0.3, 0.1, 0.2, 0.15, 0.25,
        )
        assert abs(total - 1.0) < 1e-10
        assert abs(lit + meas + struct + proxy + missing - 1.0) < 1e-10

    def test_top_2_reducible(self):
        """Top 2 from {measurement, proxy, missing}."""
        _, _, _, _, _, _, top = _normalize_and_report(
            0.3, 0.1, 0.2, 0.05, 0.35,  # missing is largest reducible
        )
        assert len(top) == 2
        # Missing (35%) should be first
        assert top[0].source_name == "missing_observations"

    def test_zero_total(self):
        total, _, _, _, _, _, top = _normalize_and_report(0, 0, 0, 0, 0)
        assert total == 0.0
        assert len(top) == 0


# ═══════════════════════════════════════════════════════════════
#  Test Gate F-G3
# ═══════════════════════════════════════════════════════════════


class TestGateFG3:
    """Test Gate F-G3 validation."""

    def _make_result(self, pcts=None):
        if pcts is None:
            pcts = (0.3, 0.15, 0.2, 0.15, 0.2)
        return VarianceState(
            total_variance=1.0,
            literature_pct=pcts[0],
            measurement_pct=pcts[1],
            structural_pct=pcts[2],
            proxy_pct=pcts[3],
            missing_pct=pcts[4],
            literature_variance=pcts[0],
            measurement_variance=pcts[1],
            structural_variance=pcts[2],
            proxy_variance=pcts[3],
            missing_variance=pcts[4],
            top_reducible=[],
            per_edge_variance_contrib={},
        )

    def test_passes_valid(self):
        _validate_gate_f_g3(self._make_result())

    def test_fails_pcts_not_sum_to_1(self):
        result = self._make_result(pcts=(0.3, 0.3, 0.3, 0.3, 0.3))
        with pytest.raises(GateViolation, match="F-G3"):
            _validate_gate_f_g3(result)

    def test_fails_negative_pct(self):
        result = self._make_result(pcts=(0.5, 0.2, 0.2, 0.2, -0.1))
        with pytest.raises(GateViolation, match="F-G3"):
            _validate_gate_f_g3(result)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_variance_decomposition
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full F3 pipeline tests."""

    def test_basic_pipeline(self):
        result = compute_variance_decomposition(
            edge_tau_squared={"e1": 0.1, "e2": 0.15},
            instrument_alphas={"i1": 0.85, "i2": 0.90},
            n_edges=10,
            proxy_r_squared={"n1": 0.7, "n2": 0.8},
        )
        assert result.gate_f_g3_passed
        assert result.total_variance > 0
        pct_sum = (result.literature_pct + result.measurement_pct
                   + result.structural_pct + result.proxy_pct
                   + result.missing_pct)
        assert abs(pct_sum - 1.0) < 0.01

    def test_all_zero_inputs(self):
        """All zeros → total = 0, no gate failure."""
        result = compute_variance_decomposition()
        assert result.gate_f_g3_passed
        assert result.total_variance == 0.0

    def test_with_missing_observations(self):
        cov = np.eye(4) * 0.5
        cov[0, 3] = 0.2
        cov[3, 0] = 0.2
        observed = np.array([True, True, True, False])
        result = compute_variance_decomposition(
            edge_tau_squared={"e1": 0.1},
            instrument_alphas={"i1": 0.85},
            n_edges=5,
            posterior_covariance=cov,
            observed_mask=observed,
            target_indices=[0],
        )
        assert result.gate_f_g3_passed
        assert result.missing_variance > 0


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify F3 constants come from config."""

    def test_proxy_threshold(self):
        assert config.F3_PROXY_R2_LOW_THRESHOLD == 0.3

    def test_sum_tolerance(self):
        assert config.F3_SUM_TOLERANCE == 0.01

    def test_structural_default(self):
        assert config.SIGMA_SQ_STRUCTURAL_DEFAULT == 0.25
