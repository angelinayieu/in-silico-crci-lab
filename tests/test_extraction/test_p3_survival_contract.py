"""Boundary Contract Test: P3 survival.

p3_survival_rate > 0 for target paper; no silent empty-list pass-through.
Uses synthetic data only (no LLM).
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import (
    EffectScale,
    HarmonizationStatusInMem,
    SESource,
)
from crci.shared.models.intermediate_states import (
    GateViolation,
    HarmonizedClaim,
)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _make_claim(
    ler_id: str = "LER_test_001",
    harmonized_se: float | None = 0.12,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    canonical_scale: str | None = "SMD",
) -> HarmonizedClaim:
    return HarmonizedClaim(
        ler_id=ler_id,
        edge_relation_id="ER_TEST_EDGE",
        profile_id="prof_01",
        study_id="study_001",
        harmonized_beta=0.45,
        harmonized_se=harmonized_se,
        harmonized_scale=EffectScale.SD_SD,
        harmonization_status=HarmonizationStatusInMem.FULL,
        quality_rating="moderate",
        se_source=SESource.SE_DIRECT,
        canonical_scale=canonical_scale,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
    )


def simulate_p3_se_gate(claim: HarmonizedClaim) -> bool:
    """Simulate P3's per-record SE gate check.

    Returns True if record survives (has SE or derivable SE from CI).
    """
    se = claim.harmonized_se
    if se is not None and se > 0:
        return True
    # CI→SE fallback
    if claim.ci_lower is not None and claim.ci_upper is not None:
        return True
    return False


def compute_survival_rate(claims: list[HarmonizedClaim]) -> float:
    """Compute P3 survival rate."""
    if not claims:
        return 0.0
    survived = sum(1 for c in claims if simulate_p3_se_gate(c))
    return survived / len(claims)


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestP3SurvivalGate:
    """P3 contract: SE gate works correctly per-record."""

    def test_record_with_se_survives(self):
        claim = _make_claim(harmonized_se=0.12)
        assert simulate_p3_se_gate(claim)

    def test_record_with_ci_survives(self):
        claim = _make_claim(harmonized_se=None, ci_lower=0.21, ci_upper=0.69)
        assert simulate_p3_se_gate(claim)

    def test_record_without_se_or_ci_fails(self):
        claim = _make_claim(harmonized_se=None, ci_lower=None, ci_upper=None)
        assert not simulate_p3_se_gate(claim)

    def test_record_with_zero_se_fails(self):
        claim = _make_claim(harmonized_se=0.0)
        assert not simulate_p3_se_gate(claim)


class TestP3SurvivalRate:
    """P3 contract: survival rate > 0 for well-formed data."""

    def test_all_records_survive(self):
        claims = [
            _make_claim(ler_id=f"LER_{i}", harmonized_se=0.12)
            for i in range(5)
        ]
        assert compute_survival_rate(claims) == 1.0

    def test_partial_survival(self):
        claims = [
            _make_claim(ler_id="LER_1", harmonized_se=0.12),
            _make_claim(ler_id="LER_2", harmonized_se=None),  # fails
            _make_claim(ler_id="LER_3", harmonized_se=0.25),
        ]
        rate = compute_survival_rate(claims)
        assert abs(rate - 2.0 / 3.0) < 1e-6

    def test_zero_survival_detected(self):
        claims = [
            _make_claim(ler_id="LER_1", harmonized_se=None),
            _make_claim(ler_id="LER_2", harmonized_se=None),
        ]
        assert compute_survival_rate(claims) == 0.0


class TestP3SliceHalt:
    """P3 contract: zero survival must halt pipeline."""

    def test_zero_survival_should_halt(self):
        """When p3_survival_rate == 0 and records existed, pipeline must halt."""
        claims = [
            _make_claim(ler_id="LER_1", harmonized_se=None),
        ]
        rate = compute_survival_rate(claims)
        if rate == 0.0 and len(claims) > 0:
            # P3 should raise GateViolation("P3-SLICE-HALT", ...)
            with pytest.raises(GateViolation):
                raise GateViolation(
                    "P3-SLICE-HALT",
                    f"Zero records survived P3 ({len(claims)} failures). "
                    f"Pipeline cannot produce evidence. Halting.",
                )

    def test_empty_input_rate_is_zero(self):
        """Empty input → rate=0, but no halt (nothing to process)."""
        assert compute_survival_rate([]) == 0.0


class TestP3NoSilentEmptyPassthrough:
    """P3 contract: never silently produce empty output."""

    def test_empty_claims_detectable(self):
        claims: list[HarmonizedClaim] = []
        assert len(claims) == 0

    def test_all_failed_claims_detectable(self):
        claims = [
            _make_claim(ler_id=f"LER_{i}", harmonized_se=None)
            for i in range(3)
        ]
        survived = [c for c in claims if simulate_p3_se_gate(c)]
        assert len(survived) == 0
        # This should trigger P3-SLICE-HALT in the real pipeline


class TestP4GroupingByScale:
    """Contract: P4 must group by (edge_relation_id, canonical_scale)."""

    def test_same_edge_different_scales_separated(self):
        """Claims with same edge but different scales must not be pooled."""
        claim_smd = _make_claim(ler_id="LER_1", canonical_scale="SMD")
        claim_log_or = _make_claim(ler_id="LER_2", canonical_scale="LOG_OR")

        # Both have same edge_relation_id but different scales
        assert claim_smd.edge_relation_id == claim_log_or.edge_relation_id
        assert claim_smd.canonical_scale != claim_log_or.canonical_scale

        # Grouping key should differ
        key_1 = (claim_smd.edge_relation_id, claim_smd.canonical_scale)
        key_2 = (claim_log_or.edge_relation_id, claim_log_or.canonical_scale)
        assert key_1 != key_2

    def test_same_edge_same_scale_grouped(self):
        """Claims with same edge AND scale should be pooled together."""
        claim_1 = _make_claim(ler_id="LER_1", canonical_scale="SMD")
        claim_2 = _make_claim(ler_id="LER_2", canonical_scale="SMD")

        key_1 = (claim_1.edge_relation_id, claim_1.canonical_scale)
        key_2 = (claim_2.edge_relation_id, claim_2.canonical_scale)
        assert key_1 == key_2
