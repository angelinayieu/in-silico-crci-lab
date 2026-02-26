"""
Tests for subpopulation_comparator.py (F5 module).

Per §8.1.11: Unit tests for gates, pairwise comparisons, and integration.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation
from crci.algorithm.chain_f_analytics.subpopulation_comparator import (
    _compute_hash,
    _compute_pairing_fingerprint,
    _enforce_f5_g0,
    _enforce_f5_g2,
    _compute_rank_concordance,
    _compute_risk_differential,
    _check_f5_g3,
    PairingFingerprint,
    ContextResult,
    DifferentialEffect,
    SubpopulationComparisonResult,
)


# ══════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_mc_draws():
    """Mock MCDraws for pairing fingerprint tests."""
    draws = MagicMock()
    draws.beta_draws = np.random.rand(10, 5)
    draws.include_draws = np.random.randint(0, 2, (10, 5)).astype(bool)
    return draws


@pytest.fixture
def mock_context_results():
    """Two mock context results with identical pairing fingerprints."""
    fingerprint = PairingFingerprint(
        d1a_beta_hash="abc123",
        d1b_include_hash="def456",
        d3_gamma_hash="NOT_CONTROLLED",
        seed_used=42,
    )

    mock_ranking_a = MagicMock()
    mock_ranking_a.ranked_interventions = [
        MagicMock(action_id="exercise"),
        MagicMock(action_id="cognitive_training"),
        MagicMock(action_id="meditation"),
    ]

    mock_ranking_b = MagicMock()
    mock_ranking_b.ranked_interventions = [
        MagicMock(action_id="cognitive_training"),
        MagicMock(action_id="exercise"),
        MagicMock(action_id="meditation"),
    ]

    mock_risk_a = MagicMock()
    mock_risk_a.risk_pct = 45.0
    mock_risk_a.risk_lower_pct = 38.0
    mock_risk_a.risk_upper_pct = 52.0
    mock_risk_a.domain_profiles = []

    mock_risk_b = MagicMock()
    mock_risk_b.risk_pct = 35.0
    mock_risk_b.risk_lower_pct = 28.0
    mock_risk_b.risk_upper_pct = 42.0
    mock_risk_b.domain_profiles = []

    cr_a = ContextResult(
        context_key="breast_adjuvant",
        cancer_type="breast",
        treatment_phase="adjuvant",
        fallback_level="EXACT",
        ranking=mock_ranking_a,
        risk_estimate=mock_risk_a,
        posterior_mean=np.array([0.0, -0.5, -1.0]),
        posterior_sd=np.array([0.5, 0.5, 0.5]),
        se_inflation_applied=1.0,
        pairing_fingerprint=fingerprint,
        n_context_shifted_nodes=5,
    )

    cr_b = ContextResult(
        context_key="colorectal_adjuvant",
        cancer_type="colorectal",
        treatment_phase="adjuvant",
        fallback_level="EXACT",
        ranking=mock_ranking_b,
        risk_estimate=mock_risk_b,
        posterior_mean=np.array([0.2, -0.3, -0.8]),
        posterior_sd=np.array([0.5, 0.5, 0.5]),
        se_inflation_applied=1.0,
        pairing_fingerprint=fingerprint,
        n_context_shifted_nodes=3,
    )

    return {"breast_adjuvant": cr_a, "colorectal_adjuvant": cr_b}


# ══════════════════════════════════════════════════════════════
#  Unit Tests: Hash Computation
# ══════════════════════════════════════════════════════════════


def test_compute_hash_deterministic():
    """Same array produces same hash."""
    arr = np.array([1.0, 2.0, 3.0])
    h1 = _compute_hash(arr)
    h2 = _compute_hash(arr)
    assert h1 == h2


def test_compute_hash_different_arrays():
    """Different arrays produce different hashes."""
    arr1 = np.array([1.0, 2.0, 3.0])
    arr2 = np.array([1.0, 2.0, 4.0])
    assert _compute_hash(arr1) != _compute_hash(arr2)


def test_compute_pairing_fingerprint(mock_mc_draws):
    """Pairing fingerprint contains expected fields."""
    fp = _compute_pairing_fingerprint(mock_mc_draws, seed=42)

    assert fp.seed_used == 42
    assert len(fp.d1a_beta_hash) == 16
    assert len(fp.d1b_include_hash) == 16
    assert fp.d3_gamma_hash == "NOT_CONTROLLED"


# ══════════════════════════════════════════════════════════════
#  Unit Tests: Gate F5-G0 (CRN Pairing)
# ══════════════════════════════════════════════════════════════


def test_f5_g0_passes_with_identical_fingerprints(mock_context_results):
    """F5-G0 passes when all fingerprints match."""
    passed, coverage = _enforce_f5_g0(mock_context_results)
    assert passed is True
    assert coverage == "partial"  # D3 is NOT_CONTROLLED


def test_f5_g0_fails_with_different_d1a():
    """F5-G0 fails when D1a hashes differ."""
    fp1 = PairingFingerprint("abc", "def", "NOT_CONTROLLED", 42)
    fp2 = PairingFingerprint("xyz", "def", "NOT_CONTROLLED", 42)

    cr_a = MagicMock()
    cr_a.pairing_fingerprint = fp1
    cr_b = MagicMock()
    cr_b.pairing_fingerprint = fp2

    with pytest.raises(GateViolation) as exc_info:
        _enforce_f5_g0({"a": cr_a, "b": cr_b})

    assert "F5-G0" in str(exc_info.value)
    assert "D1a beta draws differ" in str(exc_info.value)


def test_f5_g0_fails_with_different_d1b():
    """F5-G0 fails when D1b hashes differ."""
    fp1 = PairingFingerprint("abc", "def", "NOT_CONTROLLED", 42)
    fp2 = PairingFingerprint("abc", "xyz", "NOT_CONTROLLED", 42)

    cr_a = MagicMock()
    cr_a.pairing_fingerprint = fp1
    cr_b = MagicMock()
    cr_b.pairing_fingerprint = fp2

    with pytest.raises(GateViolation) as exc_info:
        _enforce_f5_g0({"a": cr_a, "b": cr_b})

    assert "F5-G0" in str(exc_info.value)
    assert "D1b inclusion draws differ" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
#  Unit Tests: Gate F5-G2 (Minimum Contexts)
# ══════════════════════════════════════════════════════════════


def test_f5_g2_passes_with_two_contexts(mock_context_results):
    """F5-G2 passes with 2 contexts."""
    assert _enforce_f5_g2(mock_context_results) is True


def test_f5_g2_fails_with_one_context(mock_context_results):
    """F5-G2 fails with less than 2 contexts."""
    single = {"breast_adjuvant": mock_context_results["breast_adjuvant"]}

    with pytest.raises(GateViolation) as exc_info:
        _enforce_f5_g2(single)

    assert "F5-G2" in str(exc_info.value)
    assert "at least 2 contexts" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
#  Unit Tests: F5-M2 (Rank Concordance)
# ══════════════════════════════════════════════════════════════


def test_rank_concordance_identical_rankings():
    """Identical rankings should have τ = 1.0."""
    ranking = MagicMock()
    ranking.ranked_interventions = [
        MagicMock(action_id="a"),
        MagicMock(action_id="b"),
        MagicMock(action_id="c"),
    ]

    cr_a = MagicMock()
    cr_a.ranking = ranking
    cr_b = MagicMock()
    cr_b.ranking = ranking

    tau = _compute_rank_concordance(cr_a, cr_b)
    assert tau == pytest.approx(1.0, abs=0.01)


def test_rank_concordance_reversed_rankings():
    """Reversed rankings should have τ ≈ -1.0."""
    ranking_a = MagicMock()
    ranking_a.ranked_interventions = [
        MagicMock(action_id="a"),
        MagicMock(action_id="b"),
        MagicMock(action_id="c"),
    ]

    ranking_b = MagicMock()
    ranking_b.ranked_interventions = [
        MagicMock(action_id="c"),
        MagicMock(action_id="b"),
        MagicMock(action_id="a"),
    ]

    cr_a = MagicMock()
    cr_a.ranking = ranking_a
    cr_b = MagicMock()
    cr_b.ranking = ranking_b

    tau = _compute_rank_concordance(cr_a, cr_b)
    assert tau == pytest.approx(-1.0, abs=0.01)


def test_rank_concordance_partial_rankings(mock_context_results):
    """Partial overlap in rankings."""
    tau = _compute_rank_concordance(
        mock_context_results["breast_adjuvant"],
        mock_context_results["colorectal_adjuvant"],
    )
    # Rankings have 1 swap (exercise↔cognitive_training), meditation same
    # τ should be between -1 and 1
    assert -1.0 <= tau <= 1.0


# ══════════════════════════════════════════════════════════════
#  Unit Tests: F5-M3 (Risk Differential)
# ══════════════════════════════════════════════════════════════


def test_risk_differential_computation(mock_context_results):
    """Risk differential is P̂(a) − P̂(b)."""
    cr_a = mock_context_results["breast_adjuvant"]
    cr_b = mock_context_results["colorectal_adjuvant"]

    diff = _compute_risk_differential(cr_a, cr_b)

    assert diff.context_a == "breast_adjuvant"
    assert diff.context_b == "colorectal_adjuvant"
    assert diff.risk_diff_pct == pytest.approx(45.0 - 35.0, abs=0.1)
    assert diff.risk_diff_ci_lower < diff.risk_diff_pct < diff.risk_diff_ci_upper


# ══════════════════════════════════════════════════════════════
#  Unit Tests: F5-G3 (Meaningful Differences Warning)
# ══════════════════════════════════════════════════════════════


def test_f5_g3_returns_warning_when_no_meaningful_diffs():
    """F5-G3 returns warning when no differentials are practically different."""
    differentials = [
        DifferentialEffect(
            intervention_id="ex",
            context_a="a",
            context_b="b",
            delta_C_diff_mean=0.01,
            delta_C_diff_ci_lower=-0.1,
            delta_C_diff_ci_upper=0.12,
            baseline_contribution=0.5,
            mechanism_contribution=0.5,
            practically_different=False,  # CrI includes zero
        ),
    ]

    warning = _check_f5_g3(differentials, "a", "b")

    assert warning is not None
    assert "No meaningfully different" in warning


def test_f5_g3_no_warning_when_meaningful_diffs():
    """F5-G3 returns None when at least one differential is practically different."""
    differentials = [
        DifferentialEffect(
            intervention_id="ex",
            context_a="a",
            context_b="b",
            delta_C_diff_mean=0.5,
            delta_C_diff_ci_lower=0.1,
            delta_C_diff_ci_upper=0.9,
            baseline_contribution=0.3,
            mechanism_contribution=0.7,
            practically_different=True,  # CrI excludes zero
        ),
    ]

    warning = _check_f5_g3(differentials, "a", "b")

    assert warning is None


# ══════════════════════════════════════════════════════════════
#  Integration Test Placeholder
# ══════════════════════════════════════════════════════════════


def test_subpopulation_result_dataclass():
    """SubpopulationComparisonResult has expected structure."""
    result = SubpopulationComparisonResult(
        n_contexts_compared=2,
        comparison_valid=True,
        seed=42,
    )

    assert result.n_contexts_compared == 2
    assert result.comparison_valid is True
    assert result.seed == 42
    assert result.gate_f5_g0_passed is False
    assert result.crn_coverage == "partial"
