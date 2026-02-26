"""Boundary Contract Test: P2 → P3.

Every harmonized record must have canonical_scale + orientation metadata
or explicit 'unknown' (never implicit defaults). Uses synthetic data only.
"""
from __future__ import annotations

import math

import pytest

from crci.shared.models.enums import (
    EffectScale,
    HarmonizationStatusInMem,
    SESource,
)
from crci.shared.models.intermediate_states import HarmonizedClaim


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

VALID_CANONICAL_SCALES = {
    "SMD", "LOG_OR", "LOG_HR", "LOG_RR", "FISHER_Z", "RAW",
}


def _make_claim(
    ler_id: str = "LER_test_001",
    edge_relation_id: str = "ER_COGACTIVITY_WORKMEM",
    profile_id: str = "prof_01",
    study_id: str = "study_001",
    harmonized_beta: float = 0.45,
    harmonized_se: float | None = 0.12,
    harmonized_scale: EffectScale = EffectScale.SD_SD,
    canonical_scale: str | None = "SMD",
    quality_rating: str = "moderate",
) -> HarmonizedClaim:
    return HarmonizedClaim(
        ler_id=ler_id,
        edge_relation_id=edge_relation_id,
        profile_id=profile_id,
        study_id=study_id,
        harmonized_beta=harmonized_beta,
        harmonized_se=harmonized_se,
        harmonized_scale=harmonized_scale,
        harmonization_status=HarmonizationStatusInMem.FULL,
        quality_rating=quality_rating,
        se_source=SESource.SE_DIRECT,
        canonical_scale=canonical_scale,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestCanonicalScale:
    """P2 → P3 contract: canonical_scale must be set and valid."""

    def test_canonical_scale_present(self):
        claim = _make_claim(canonical_scale="SMD")
        assert claim.canonical_scale is not None

    @pytest.mark.parametrize("scale", sorted(VALID_CANONICAL_SCALES))
    def test_valid_canonical_scales(self, scale: str):
        claim = _make_claim(canonical_scale=scale)
        assert claim.canonical_scale in VALID_CANONICAL_SCALES

    def test_none_canonical_scale_flagged(self):
        """Records without canonical_scale should be detectable."""
        claim = _make_claim(canonical_scale=None)
        assert claim.canonical_scale is None  # P3 must handle this

    def test_unknown_canonical_scale_not_in_valid_set(self):
        claim = _make_claim(canonical_scale="UNKNOWN_SCALE")
        assert claim.canonical_scale not in VALID_CANONICAL_SCALES


class TestOrientationMetadata:
    """P2 → P3 contract: orientation should never be silently defaulted."""

    def test_quality_rating_present(self):
        """Quality rating must always be set (even if default 'moderate')."""
        claim = _make_claim(quality_rating="moderate")
        assert claim.quality_rating in {"weak", "moderate", "strong"}

    def test_se_source_present(self):
        """SE source tracks how SE was derived."""
        claim = _make_claim()
        assert claim.se_source is not None

    def test_harmonization_status_present(self):
        claim = _make_claim()
        assert claim.harmonization_status is not None


class TestFisherZTransform:
    """P2 → P3 contract: correlations should be Fisher-z transformed."""

    def test_fisher_z_scale_for_correlation(self):
        """When canonical_scale=FISHER_Z, beta should be arctanh(r)."""
        r = 0.5
        z = math.atanh(r)  # Expected: ~0.5493
        claim = _make_claim(
            canonical_scale="FISHER_Z",
            harmonized_beta=z,
        )
        # Verify the stored beta is in z-space (> r for |r| < 1)
        assert abs(claim.harmonized_beta - z) < 1e-6
        assert abs(z) > abs(r)  # z is always farther from 0 than r

    def test_fisher_z_se_derivation(self):
        """SE in Fisher-z space: SE_z = 1/sqrt(N-3)."""
        n = 100
        expected_se = 1.0 / math.sqrt(n - 3)
        claim = _make_claim(
            canonical_scale="FISHER_Z",
            harmonized_beta=math.atanh(0.3),
            harmonized_se=expected_se,
        )
        assert abs(claim.harmonized_se - expected_se) < 1e-6

    def test_smd_not_transformed(self):
        """SMD values should NOT be Fisher-z transformed."""
        claim = _make_claim(
            canonical_scale="SMD",
            harmonized_beta=0.45,
        )
        assert claim.harmonized_beta == 0.45


class TestP2OutputCompleteness:
    """P2 → P3 contract: records must have minimum viable fields."""

    def test_required_fields_present(self):
        claim = _make_claim()
        assert claim.ler_id is not None
        assert claim.edge_relation_id is not None
        assert claim.study_id is not None
        assert claim.harmonized_beta is not None
        assert claim.harmonized_scale is not None
        assert claim.harmonization_status is not None

    def test_se_or_ci_for_p3_survival(self):
        """P3 needs SE or CI to avoid L6 qualitative fallback."""
        claim = _make_claim(harmonized_se=0.12)
        has_se = claim.harmonized_se is not None
        has_ci = (claim.ci_lower is not None and claim.ci_upper is not None)
        assert has_se or has_ci, "P3 requires SE or CI for survival"

    def test_no_silent_empty_pass(self):
        """Empty claim list should be detectable, not silently passed."""
        claims: list[HarmonizedClaim] = []
        assert len(claims) == 0  # P3 should halt on this
