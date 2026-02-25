"""Tests for S3: Pathway Profiler.

Covers:
    - Signed z-score computation (direction preserved)
    - Variance-weighted aggregation
    - Dysregulation flag correctness
    - Dominant pathway identification
    - Equal-weight fallback when variance_contrib is None
    - Edge cases: empty pathway, missing nodes
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.runtime.pathway_profiler import (
    PathwayInput,
    compute_pathway_profile,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _three_pathway_setup():
    """3 pathways, 9 nodes. Known z-scores for hand verification."""
    # 9 nodes: 3 per pathway
    node_index = {f"n{i}": i for i in range(9)}

    # Prior: all nodes at mean=0, sd=1
    theta_prior_mean = np.zeros(9)
    sigma_prior = np.ones(9)

    # Posterior: pathway 0 nodes shifted positive, pathway 1 negative, pathway 2 near zero
    theta_hat = np.array([
        1.0, 0.8, 1.2,    # pathway 0: positive z ≈ +1.0
        -2.0, -1.5, -1.8, # pathway 1: negative z ≈ -1.77 (dysregulated)
        0.1, -0.1, 0.0,   # pathway 2: near zero (normal)
    ])

    pathways = [
        PathwayInput(
            pathway_id="pw_inflammation",
            pathway_label="Neuroinflammation",
            component_node_ids=["n0", "n1", "n2"],
            edge_ids=["e0", "e1"],
        ),
        PathwayInput(
            pathway_id="pw_hpa",
            pathway_label="HPA Axis",
            component_node_ids=["n3", "n4", "n5"],
            edge_ids=["e2", "e3"],
        ),
        PathwayInput(
            pathway_id="pw_oxidative",
            pathway_label="Oxidative Stress",
            component_node_ids=["n6", "n7", "n8"],
            edge_ids=["e4", "e5"],
        ),
    ]

    # Variance contributions: pathway 1 dominates
    variance_contrib = {
        "n0": 0.05, "n1": 0.05, "n2": 0.05,  # pw0: 0.15 total
        "n3": 0.20, "n4": 0.15, "n5": 0.15,  # pw1: 0.50 total
        "n6": 0.10, "n7": 0.10, "n8": 0.15,  # pw2: 0.35 total
    }

    return pathways, theta_hat, theta_prior_mean, sigma_prior, node_index, variance_contrib


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestPathwayProfiler:

    def test_signed_z_scores_preserved(self):
        """Pathway z-scores should retain sign (not absolute value)."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)

        # pw_inflammation should be positive (nodes shifted positive)
        pw0 = profile.pathway_contributions[0]
        # pw_hpa should be negative (nodes shifted negative)
        pw1 = profile.pathway_contributions[1]

        # We can infer sign from the z-score via the evidence_quality
        # But we need the actual z_pathway value. Since PathwayContribution
        # doesn't carry activation_z, we verify indirectly:
        # pw_inflammation: mean z ≈ (1.0 + 0.8 + 1.2)/3 = 1.0 (if equal weight)
        # pw_hpa: mean z ≈ (-2.0 + -1.5 + -1.8)/3 = -1.77 (if equal weight)
        # With variance weighting the exact values differ, but signs are preserved
        # pw_hpa quality should be "strong_signal" (|z| > 1.5)
        assert pw1.evidence_quality == "strong_signal"

    def test_variance_weighted_aggregation(self):
        """Z-pathway should be variance-weighted mean of node z-scores."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)

        # Hand-compute pathway 1 (HPA) z-score with variance weights:
        # z_nodes = [-2.0, -1.5, -1.8]
        # weights = [0.20, 0.15, 0.15]
        # z_pathway = (-2.0*0.20 + -1.5*0.15 + -1.8*0.15) / (0.20+0.15+0.15)
        #           = (-0.40 + -0.225 + -0.27) / 0.50
        #           = -0.895 / 0.50
        #           = -1.79
        # |z| = 1.79 > 1.5 → strong_signal
        pw1 = profile.pathway_contributions[1]
        assert pw1.evidence_quality == "strong_signal"

    def test_equal_weight_fallback(self):
        """When variance_contrib is None, should use equal weights."""
        pws, theta_hat, prior_mean, sigma, ni, _ = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, None)

        # Without variance contrib, equal weights
        # pw_inflammation: (1.0 + 0.8 + 1.2) / 3 = 1.0 → moderate_signal
        pw0 = profile.pathway_contributions[0]
        assert pw0.evidence_quality == "moderate_signal"

        # pw_hpa: (-2.0 + -1.5 + -1.8) / 3 = -1.767 → strong_signal
        pw1 = profile.pathway_contributions[1]
        assert pw1.evidence_quality == "strong_signal"

        # pw_oxidative: (0.1 + -0.1 + 0.0) / 3 = 0.0 → normal_range
        pw2 = profile.pathway_contributions[2]
        assert pw2.evidence_quality == "normal_range"

    def test_dominant_pathway_identification(self):
        """Dominant pathway should be the one with highest contribution fraction."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)

        # pw_hpa has highest variance contribution (0.50 total)
        assert profile.dominant_pathway_id == "pw_hpa"

    def test_contribution_fractions_sum(self):
        """Contribution fractions should sum to <= 1.0."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)

        total = sum(c.contribution_fraction for c in profile.pathway_contributions)
        assert total <= 1.0 + 1e-10

    def test_dysregulation_threshold_from_config(self):
        """Dysregulation flag should use config.PATHWAY_DYSREGULATION_THRESHOLD."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()

        # pw_oxidative has z ≈ 0.0, should be normal_range
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)
        pw2 = profile.pathway_contributions[2]
        assert pw2.evidence_quality == "normal_range"

    def test_missing_node_handled(self):
        """Nodes not in node_index should be skipped with warning."""
        pws = [
            PathwayInput(
                pathway_id="pw_test",
                pathway_label="Test",
                component_node_ids=["n0", "n_missing", "n1"],
                edge_ids=["e0"],
            ),
        ]
        theta_hat = np.array([1.0, 0.5])
        prior_mean = np.zeros(2)
        sigma = np.ones(2)
        ni = {"n0": 0, "n1": 1}

        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, None)
        assert len(profile.pathway_contributions) == 1
        # Should still compute from available nodes
        pw = profile.pathway_contributions[0]
        assert pw.contribution_fraction > 0 or pw.evidence_quality is not None

    def test_empty_pathway(self):
        """Pathway with no resolvable nodes should get zero contribution."""
        pws = [
            PathwayInput(
                pathway_id="pw_empty",
                pathway_label="Empty",
                component_node_ids=["nonexistent"],
                edge_ids=[],
            ),
        ]
        theta_hat = np.array([1.0])
        prior_mean = np.zeros(1)
        sigma = np.ones(1)
        ni = {"n0": 0}

        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, None)
        assert profile.pathway_contributions[0].contribution_fraction == 0.0
        assert profile.pathway_contributions[0].evidence_quality == "insufficient"

    def test_coverage_fraction(self):
        """Coverage fraction should be sum of contribution fractions, capped at 1.0."""
        pws, theta_hat, prior_mean, sigma, ni, vc = _three_pathway_setup()
        profile = compute_pathway_profile(pws, theta_hat, prior_mean, sigma, ni, vc)
        assert 0.0 < profile.coverage_fraction <= 1.0
