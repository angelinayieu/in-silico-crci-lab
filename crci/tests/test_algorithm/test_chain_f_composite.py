"""Tests for ALG-F1 Composite Outcome Scoring.

Covers:
    F1a: Subdomain extraction from posterior
    F1b: Severity weighting (1.0/1.5/2.0× based on |z|)
    F1c: IVW composite + Cochran's Q + I² + random effects
    F-2: Percentile = Φ(−z) × 100
    Gate F-G1: composite in [-5,5], percentile in [0,100]
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_f_analytics.composite_scorer import (
    CompositeState,
    SeverityTier,
    _apply_severity_weights,
    _classify_severity_tier,
    _compute_ivw_composite,
    _extract_subdomain_scores,
    _validate_gate_f_g1,
    compute_composite_score,
)


# ═══════════════════════════════════════════════════════════════
#  Test F1a: Subdomain Extraction
# ═══════════════════════════════════════════════════════════════


class TestSubdomainExtraction:
    """Test subdomain score extraction."""

    def test_explicit_domain_map(self):
        means = np.array([0.5, -0.3, 0.1, -0.2])
        variances = np.array([0.1, 0.2, 0.15, 0.25])
        domain_map = {
            "processing_speed": [0, 1],
            "attention": [2, 3],
        }
        scores, vars_ = _extract_subdomain_scores(means, variances, domain_map)
        # processing_speed: mean([0.5, -0.3]) = 0.1
        assert abs(scores["processing_speed"] - 0.1) < 1e-10
        # attention: mean([0.1, -0.2]) = -0.05
        assert abs(scores["attention"] - (-0.05)) < 1e-10

    def test_single_node_domain(self):
        means = np.array([0.5])
        variances = np.array([0.1])
        domain_map = {"processing_speed": [0]}
        scores, _ = _extract_subdomain_scores(means, variances, domain_map)
        assert abs(scores["processing_speed"] - 0.5) < 1e-10

    def test_empty_domain_skipped(self):
        means = np.array([0.5])
        variances = np.array([0.1])
        domain_map = {"processing_speed": [0], "attention": []}
        scores, _ = _extract_subdomain_scores(means, variances, domain_map)
        assert "processing_speed" in scores
        assert "attention" not in scores

    def test_default_domain_map(self):
        """Without explicit map, nodes distributed across domains."""
        means = np.zeros(22)
        variances = np.ones(22) * 0.1
        scores, _ = _extract_subdomain_scores(means, variances)
        assert len(scores) > 0


# ═══════════════════════════════════════════════════════════════
#  Test F1b: Severity Weighting
# ═══════════════════════════════════════════════════════════════


class TestSeverityWeighting:
    """Test severity weight application."""

    def test_mild_weight(self):
        """|z| < 1.0 → weight = 1.0."""
        scores = {"d1": 0.5}
        result = _apply_severity_weights(scores)
        assert abs(result["d1"] - 0.5 * config.F1_SEVERITY_WEIGHT_MILD) < 1e-10

    def test_moderate_weight(self):
        """1.0 ≤ |z| < 2.0 → weight = 1.5."""
        scores = {"d1": -1.5}
        result = _apply_severity_weights(scores)
        expected = -1.5 * config.F1_SEVERITY_WEIGHT_MODERATE
        assert abs(result["d1"] - expected) < 1e-10

    def test_severe_weight(self):
        """|z| ≥ 2.0 → weight = 2.0."""
        scores = {"d1": -2.5}
        result = _apply_severity_weights(scores)
        expected = -2.5 * config.F1_SEVERITY_WEIGHT_SEVERE
        assert abs(result["d1"] - expected) < 1e-10

    def test_boundary_at_1(self):
        """|z| = 1.0 → moderate weight (1.5×)."""
        scores = {"d1": 1.0}
        result = _apply_severity_weights(scores)
        assert abs(result["d1"] - 1.0 * config.F1_SEVERITY_WEIGHT_MODERATE) < 1e-10

    def test_boundary_at_2(self):
        """|z| = 2.0 → severe weight (2.0×)."""
        scores = {"d1": -2.0}
        result = _apply_severity_weights(scores)
        assert abs(result["d1"] - (-2.0) * config.F1_SEVERITY_WEIGHT_SEVERE) < 1e-10

    def test_zero_z(self):
        """z = 0 → weight = 1.0, result = 0."""
        scores = {"d1": 0.0}
        result = _apply_severity_weights(scores)
        assert result["d1"] == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F1c: IVW Composite
# ═══════════════════════════════════════════════════════════════


class TestIVWComposite:
    """Test IVW composite computation."""

    def test_equal_variance_is_simple_mean(self):
        """If all σ²_d equal, composite = simple mean (spec line 3186)."""
        z = {"d1": 1.0, "d2": -0.5, "d3": 0.0}
        var = {"d1": 0.1, "d2": 0.1, "d3": 0.1}
        crci, _, _, _, _ = _compute_ivw_composite(z, var)
        expected = (1.0 + (-0.5) + 0.0) / 3.0
        assert abs(crci - expected) < 1e-10

    def test_ivw_formula_hand_computed(self):
        """Hand-computed IVW (no RE trigger).

        d1: z=0.5, σ²=0.25 → w=4.0
        d2: z=0.3, σ²=0.5 → w=2.0
        d3: z=0.4, σ²=0.25 → w=4.0
        CRCI = (4×0.5 + 2×0.3 + 4×0.4) / (4+2+4) = 4.2/10 = 0.42
        (Low heterogeneity → no RE)
        """
        z = {"d1": 0.5, "d2": 0.3, "d3": 0.4}
        var = {"d1": 0.25, "d2": 0.5, "d3": 0.25}
        crci, weights, _, _, re = _compute_ivw_composite(z, var)
        expected = (4.0 * 0.5 + 2.0 * 0.3 + 4.0 * 0.4) / 10.0
        assert not re  # no random effects
        assert abs(crci - expected) < 1e-10
        assert abs(weights["d1"] - 4.0) < 1e-10
        assert abs(weights["d2"] - 2.0) < 1e-10

    def test_single_domain(self):
        """1 domain → composite = that z (spec line 3187)."""
        z = {"d1": -0.8}
        var = {"d1": 0.1}
        crci, _, Q, I_sq, _ = _compute_ivw_composite(z, var)
        assert abs(crci - (-0.8)) < 1e-10
        assert Q == 0.0
        assert I_sq == 0.0

    def test_cochrans_q_formula(self):
        """Hand-computed Cochran's Q.

        d1: z=1.0, w=10.0; d2: z=-1.0, w=10.0
        CRCI = (10×1 + 10×(-1)) / 20 = 0
        Q = 10×(1-0)² + 10×(-1-0)² = 10 + 10 = 20
        """
        z = {"d1": 1.0, "d2": -1.0}
        var = {"d1": 0.1, "d2": 0.1}
        _, _, Q, _, _ = _compute_ivw_composite(z, var)
        assert abs(Q - 20.0) < 1e-10

    def test_i_squared_formula(self):
        """I² = max(0, (Q − (D−1)) / Q) × 100.

        Q=20, D=2 → I² = max(0, (20-1)/20) × 100 = 95%
        """
        z = {"d1": 1.0, "d2": -1.0}
        var = {"d1": 0.1, "d2": 0.1}
        _, _, Q, I_sq, _ = _compute_ivw_composite(z, var)
        expected = max(0.0, (Q - 1.0) / Q) * 100.0
        assert abs(I_sq - expected) < 1e-10
        assert I_sq > 50.0  # should trigger RE

    def test_random_effects_applied_when_i2_high(self):
        """I² > 50% → random effects applied."""
        z = {"d1": 2.0, "d2": -2.0}
        var = {"d1": 0.1, "d2": 0.1}
        _, _, _, I_sq, re_applied = _compute_ivw_composite(z, var)
        assert I_sq > config.F1_I_SQUARED_RE_THRESHOLD
        assert re_applied is True

    def test_no_random_effects_when_i2_low(self):
        """I² ≤ 50% → no random effects."""
        # Very similar z-scores → low heterogeneity
        z = {"d1": 0.5, "d2": 0.5, "d3": 0.5}
        var = {"d1": 0.1, "d2": 0.1, "d3": 0.1}
        _, _, _, I_sq, re_applied = _compute_ivw_composite(z, var)
        assert I_sq <= config.F1_I_SQUARED_RE_THRESHOLD
        assert re_applied is False

    def test_empty_domains(self):
        crci, _, _, _, _ = _compute_ivw_composite({}, {})
        assert crci == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test F-2: Percentile
# ═══════════════════════════════════════════════════════════════


class TestPercentile:
    """Test percentile computation."""

    def test_percentile_at_zero(self):
        """z=0 → percentile = 50."""
        pct = float(stats.norm.cdf(0) * 100.0)
        assert abs(pct - 50.0) < 1e-10

    def test_percentile_negative_z(self):
        """Negative z (impaired) → percentile > 50."""
        # Φ(−(−1)) = Φ(1) ≈ 84.13%
        pct = float(stats.norm.cdf(1.0) * 100.0)
        assert abs(pct - 84.13) < 0.1

    def test_percentile_positive_z(self):
        """Positive z (above average) → percentile < 50."""
        # Φ(−1) ≈ 15.87%
        pct = float(stats.norm.cdf(-1.0) * 100.0)
        assert abs(pct - 15.87) < 0.1


# ═══════════════════════════════════════════════════════════════
#  Test Severity Tier Classification
# ═══════════════════════════════════════════════════════════════


class TestSeverityTierClassification:
    """Test severity tier from percentile."""

    def test_excellent(self):
        assert _classify_severity_tier(90.0) == SeverityTier.EXCELLENT

    def test_good(self):
        assert _classify_severity_tier(75.0) == SeverityTier.GOOD

    def test_mild(self):
        assert _classify_severity_tier(55.0) == SeverityTier.MILD_IMPAIRMENT

    def test_moderate(self):
        assert _classify_severity_tier(35.0) == SeverityTier.MODERATE_IMPAIRMENT

    def test_poor(self):
        assert _classify_severity_tier(20.0) == SeverityTier.POOR

    def test_severe(self):
        assert _classify_severity_tier(10.0) == SeverityTier.SEVERE_IMPAIRMENT

    def test_boundary_85(self):
        assert _classify_severity_tier(85.0) == SeverityTier.EXCELLENT


# ═══════════════════════════════════════════════════════════════
#  Test Gate F-G1
# ═══════════════════════════════════════════════════════════════


class TestGateFG1:
    """Test Gate F-G1 validation."""

    def _make_result(self, crci=0.0, percentile=50.0, weights=None):
        if weights is None:
            weights = {"d1": 1.0}
        return CompositeState(
            crci_composite=crci,
            severity_tier=SeverityTier.MILD_IMPAIRMENT,
            percentile=percentile,
            subdomain_scores={"d1": 0.0},
            subdomain_weights=weights,
            cochrans_Q=0.0,
            I_squared=0.0,
            random_effects_applied=False,
            severity_weighted_z={"d1": 0.0},
            n_domains=1,
        )

    def test_passes_valid(self):
        result = self._make_result()
        _validate_gate_f_g1(result)

    def test_fails_z_too_high(self):
        result = self._make_result(crci=6.0)
        with pytest.raises(GateViolation, match="F-G1"):
            _validate_gate_f_g1(result)

    def test_fails_z_too_low(self):
        result = self._make_result(crci=-6.0)
        with pytest.raises(GateViolation, match="F-G1"):
            _validate_gate_f_g1(result)

    def test_fails_percentile_over_100(self):
        result = self._make_result(percentile=101.0)
        with pytest.raises(GateViolation, match="F-G1"):
            _validate_gate_f_g1(result)

    def test_fails_zero_weight(self):
        result = self._make_result(weights={"d1": 0.0})
        with pytest.raises(GateViolation, match="F-G1"):
            _validate_gate_f_g1(result)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_composite_score
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full F1 pipeline tests."""

    def test_basic_pipeline(self):
        means = np.zeros(22)
        variances = np.ones(22) * 0.1
        result = compute_composite_score(means, variances)
        assert result.gate_f_g1_passed
        assert -5.0 <= result.crci_composite <= 5.0
        assert 0.0 <= result.percentile <= 100.0

    def test_impaired_patient(self):
        """All negative z-scores → low percentile."""
        means = np.ones(11) * -1.5
        variances = np.ones(11) * 0.1
        domain_map = {d: [i] for i, d in enumerate(config.F1_COGNITIVE_DOMAINS)}
        result = compute_composite_score(means, variances, domain_map)
        assert result.crci_composite < 0
        assert result.percentile > 50  # Φ(−negative) > 0.5

    def test_healthy_patient(self):
        """All positive z-scores → high percentile of cognitive function."""
        means = np.ones(11) * 0.5
        variances = np.ones(11) * 0.1
        domain_map = {d: [i] for i, d in enumerate(config.F1_COGNITIVE_DOMAINS)}
        result = compute_composite_score(means, variances, domain_map)
        assert result.crci_composite > 0
        assert result.percentile < 50  # Φ(−positive) < 0.5

    def test_with_domain_map(self):
        means = np.array([0.5, -0.5, 0.0, 0.1])
        variances = np.ones(4) * 0.1
        domain_map = {
            "processing_speed": [0, 1],
            "attention": [2, 3],
        }
        result = compute_composite_score(means, variances, domain_map)
        assert result.gate_f_g1_passed
        assert result.n_domains == 2


# ═══════════════════════════════════════════════════════════════
#  Config Constants Check
# ═══════════════════════════════════════════════════════════════


class TestConfigConstants:
    """Verify F1 constants come from config."""

    def test_severity_weights(self):
        assert config.F1_SEVERITY_WEIGHT_MILD == 1.0
        assert config.F1_SEVERITY_WEIGHT_MODERATE == 1.5
        assert config.F1_SEVERITY_WEIGHT_SEVERE == 2.0

    def test_severity_thresholds(self):
        assert config.F1_SEVERITY_THRESHOLD_MODERATE == 1.0
        assert config.F1_SEVERITY_THRESHOLD_SEVERE == 2.0

    def test_i_squared_threshold(self):
        assert config.F1_I_SQUARED_RE_THRESHOLD == 50.0

    def test_tier_boundaries(self):
        assert config.F1_TIER_EXCELLENT_MIN == 85.0
        assert config.F1_TIER_GOOD_MIN == 70.0
        assert config.F1_TIER_MILD_MIN == 50.0
        assert config.F1_TIER_MODERATE_MIN == 30.0
        assert config.F1_TIER_POOR_MIN == 15.0

    def test_composite_bounds(self):
        assert config.F1_COMPOSITE_Z_MIN == -5.0
        assert config.F1_COMPOSITE_Z_MAX == 5.0

    def test_domain_list(self):
        assert len(config.F1_COGNITIVE_DOMAINS) == 11
        assert "processing_speed" in config.F1_COGNITIVE_DOMAINS
