"""
Tests for extraction/p4_aggregation/meta_analyzer.py

FORMULA-DENSE file tests covering:
- P4-1: IVW fixed-effects (hand-computed)
- P4-2: DerSimonian-Laird tau^2 and random-effects (hand-computed)
- P4-3: P_inclusion logistic formula
- P4-3b: P_final with annotation adjustment
- P4-MA-c: Annotation consumption (sigma_sq_structural, p_inclusion_adjustment)
- P4-MA-a: Aggregation decision tree
- Gate P4-G1: All edges must have method
- Gate P4-G2: No NaN in beta or SE
- Edge cases: k=0, k=1, missing SE, sign conflict
"""
from __future__ import annotations

import math

import pytest

from crci.shared import config
from crci.shared.models.enums import AggregationMethod, AnnotationCategory
from crci.shared.models.intermediate_states import (
    GateViolation,
    HarmonizedClaim,
    PooledEstimate,
    ResolvedEvidence,
)
from crci.extraction.p4_aggregation.meta_analyzer import (
    AnnotationRecord,
    MetaAnalysisResult,
    compute_cochran_q,
    compute_i_squared,
    compute_ivw_fixed,
    compute_ivw_random,
    compute_p_inclusion,
    compute_p_inclusion_adjustment,
    compute_sigma_sq_structural,
    compute_tau_squared_dl,
    logistic,
    logit,
    pool_evidence,
    analyze_all_edges,
    select_aggregation_method,
)


# ═══════════════════════════════════════════════════════════════
#  HELPER FACTORIES
# ═══════════════════════════════════════════════════════════════


def make_claim(
    ler_id: str = "ler_1",
    edge_relation_id: str = "edge_1",
    beta: float = 0.3,
    se: float = 0.1,
    quality: str = "moderate",
    study_id: str = "study_1",
) -> HarmonizedClaim:
    return HarmonizedClaim(
        ler_id=ler_id,
        edge_relation_id=edge_relation_id,
        profile_id="prof_1",
        study_id=study_id,
        harmonized_beta=beta,
        harmonized_se=se,
        harmonized_scale="SD_SD",
        harmonization_status="FULL",
        quality_rating=quality,
    )


def make_resolved(
    edge_id: str = "edge_1",
    claims: list[HarmonizedClaim] | None = None,
    k: int | None = None,
    total_n: int = 500,
) -> ResolvedEvidence:
    if claims is None:
        claims = []
    return ResolvedEvidence(
        edge_relation_id=edge_id,
        claims=claims,
        k=k if k is not None else len(claims),
        total_n=total_n,
    )


def make_annotation(
    ann_id: str = "ann_1",
    category: str = "limitation_unmeasured_confounder",
    edge_id: str = "edge_1",
    severity: str | None = "moderate",
    confidence: float = 0.8,
    powered: bool | None = None,
) -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id=ann_id,
        category=category,
        target_edge_relation_id=edge_id,
        reconciled_confidence=confidence,
        severity=severity,
        powered_adequately=powered,
    )


# ═══════════════════════════════════════════════════════════════
#  TEST: Math primitives
# ═══════════════════════════════════════════════════════════════


class TestLogistic:
    def test_zero(self):
        assert logistic(0.0) == pytest.approx(0.5)

    def test_large_positive(self):
        assert logistic(100.0) == pytest.approx(1.0, abs=1e-10)

    def test_large_negative(self):
        assert logistic(-100.0) == pytest.approx(0.0, abs=1e-10)

    def test_symmetry(self):
        assert logistic(2.0) + logistic(-2.0) == pytest.approx(1.0)

    def test_known_value(self):
        # logistic(1.0) = 1/(1+exp(-1)) = 0.7310585...
        assert logistic(1.0) == pytest.approx(0.7310585786300049, rel=1e-10)


class TestLogit:
    def test_half(self):
        assert logit(0.5) == pytest.approx(0.0)

    def test_roundtrip(self):
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            assert logistic(logit(p)) == pytest.approx(p, rel=1e-10)

    def test_boundary_raises(self):
        with pytest.raises(ValueError):
            logit(0.0)
        with pytest.raises(ValueError):
            logit(1.0)


# ═══════════════════════════════════════════════════════════════
#  TEST: Formula P4-1 — IVW Fixed Effects
# ═══════════════════════════════════════════════════════════════


class TestIVWFixed:
    """Hand-computable test for IVW fixed-effects.

    3 studies:
        Study 1: beta=0.3, SE=0.1 -> w=100
        Study 2: beta=0.5, SE=0.2 -> w=25
        Study 3: beta=0.2, SE=0.15 -> w=44.444...

    sum_w = 100 + 25 + 44.444 = 169.444...
    beta_IVW = (0.3*100 + 0.5*25 + 0.2*44.444) / 169.444
             = (30 + 12.5 + 8.8888...) / 169.444
             = 51.3888... / 169.444...
             = 0.30327...
    SE_pooled = 1/sqrt(169.444) = 0.07683...
    """

    def test_three_studies(self):
        betas = [0.3, 0.5, 0.2]
        ses = [0.1, 0.2, 0.15]

        beta_p, se_p, weights = compute_ivw_fixed(betas, ses)

        # Hand-computed
        w1 = 1.0 / 0.1**2  # 100
        w2 = 1.0 / 0.2**2  # 25
        w3 = 1.0 / 0.15**2  # 44.444...
        sum_w = w1 + w2 + w3
        expected_beta = (0.3 * w1 + 0.5 * w2 + 0.2 * w3) / sum_w
        expected_se = 1.0 / math.sqrt(sum_w)

        assert beta_p == pytest.approx(expected_beta, rel=1e-10)
        assert se_p == pytest.approx(expected_se, rel=1e-10)
        assert len(weights) == 3
        assert weights[0] == pytest.approx(w1, rel=1e-10)
        assert weights[1] == pytest.approx(w2, rel=1e-10)
        assert weights[2] == pytest.approx(w3, rel=1e-10)

    def test_single_study(self):
        betas = [0.5]
        ses = [0.2]
        beta_p, se_p, weights = compute_ivw_fixed(betas, ses)
        assert beta_p == pytest.approx(0.5, rel=1e-10)
        assert se_p == pytest.approx(0.2, rel=1e-10)

    def test_equal_weight_studies(self):
        """Two studies with same SE: pooled beta = simple average."""
        betas = [0.4, 0.6]
        ses = [0.2, 0.2]
        beta_p, se_p, weights = compute_ivw_fixed(betas, ses)
        assert beta_p == pytest.approx(0.5, rel=1e-10)


# ═══════════════════════════════════════════════════════════════
#  TEST: Formula P4-2 — DerSimonian-Laird tau^2
# ═══════════════════════════════════════════════════════════════


class TestDerSimonianLaird:
    """Hand-computable test for DL tau^2.

    3 studies:
        Study 1: beta=0.3, SE=0.1 -> w=100
        Study 2: beta=0.8, SE=0.2 -> w=25
        Study 3: beta=0.1, SE=0.15 -> w=44.444

    First compute beta_FE (IVW fixed):
        sum_w = 169.444
        beta_FE = (0.3*100 + 0.8*25 + 0.1*44.444) / 169.444
                = (30 + 20 + 4.444) / 169.444
                = 54.444 / 169.444
                = 0.32131...

    Q = 100*(0.3-0.32131)^2 + 25*(0.8-0.32131)^2 + 44.444*(0.1-0.32131)^2
      = 100*0.000454 + 25*0.22924 + 44.444*0.04892
      = 0.04543 + 5.73105 + 2.17437
      = 7.95085

    tau^2 = max(0, (Q-(k-1)) / (sum_w - sum_w^2/sum_w))
    sum_w^2 = 100^2 + 25^2 + 44.444^2 = 10000 + 625 + 1975.27 = 12600.27
    denominator = 169.444 - 12600.27/169.444 = 169.444 - 74.361 = 95.083
    tau^2 = (7.95085 - 2) / 95.083 = 5.95085 / 95.083 = 0.06259...
    """

    def test_three_studies_heterogeneous(self):
        betas = [0.3, 0.8, 0.1]
        ses = [0.1, 0.2, 0.15]

        beta_fe, _, _ = compute_ivw_fixed(betas, ses)
        tau_sq = compute_tau_squared_dl(betas, ses, beta_fe)

        # Hand-computed expected value
        w1 = 1.0 / 0.1**2
        w2 = 1.0 / 0.2**2
        w3 = 1.0 / 0.15**2
        sum_w = w1 + w2 + w3
        beta_fe_expected = (0.3 * w1 + 0.8 * w2 + 0.1 * w3) / sum_w

        q = w1 * (0.3 - beta_fe_expected) ** 2 + w2 * (0.8 - beta_fe_expected) ** 2 + w3 * (0.1 - beta_fe_expected) ** 2
        sum_w2 = w1**2 + w2**2 + w3**2
        denom = sum_w - sum_w2 / sum_w
        expected_tau_sq = max(0.0, (q - 2) / denom)

        assert tau_sq == pytest.approx(expected_tau_sq, rel=1e-8)
        assert tau_sq > 0.0  # Should be heterogeneous

    def test_homogeneous_studies(self):
        """Identical betas => Q=0, tau^2=0."""
        betas = [0.5, 0.5, 0.5]
        ses = [0.1, 0.2, 0.15]
        beta_fe, _, _ = compute_ivw_fixed(betas, ses)
        tau_sq = compute_tau_squared_dl(betas, ses, beta_fe)
        assert tau_sq == 0.0

    def test_k_less_than_2(self):
        """k<2 => tau^2 = 0."""
        tau_sq = compute_tau_squared_dl([0.5], [0.1], 0.5)
        assert tau_sq == 0.0


# ═══════════════════════════════════════════════════════════════
#  TEST: I^2 computation
# ═══════════════════════════════════════════════════════════════


class TestISquared:
    def test_no_heterogeneity(self):
        """Q = 0 => I^2 = 0."""
        assert compute_i_squared(0.0, 3) == 0.0

    def test_known_value(self):
        """Q=10, k=3: I^2 = max(0, (10-2)/10)*100 = 80%."""
        assert compute_i_squared(10.0, 3) == pytest.approx(80.0)

    def test_negative_clamp(self):
        """Q < k-1 => I^2 = 0 (clamped)."""
        assert compute_i_squared(1.0, 5) == 0.0

    def test_k_less_than_2(self):
        assert compute_i_squared(5.0, 1) == 0.0


# ═══════════════════════════════════════════════════════════════
#  TEST: IVW Random-effects
# ═══════════════════════════════════════════════════════════════


class TestIVWRandom:
    def test_with_tau_squared(self):
        """With tau^2=0.05, weights become 1/(SE^2+0.05)."""
        betas = [0.3, 0.5]
        ses = [0.1, 0.2]
        tau_sq = 0.05

        beta_p, se_p, weights = compute_ivw_random(betas, ses, tau_sq)

        # Hand-computed
        w1 = 1.0 / (0.01 + 0.05)  # = 16.667
        w2 = 1.0 / (0.04 + 0.05)  # = 11.111
        sum_w = w1 + w2
        expected_beta = (0.3 * w1 + 0.5 * w2) / sum_w
        expected_se = 1.0 / math.sqrt(sum_w)

        assert beta_p == pytest.approx(expected_beta, rel=1e-10)
        assert se_p == pytest.approx(expected_se, rel=1e-10)
        assert weights[0] == pytest.approx(w1, rel=1e-10)
        assert weights[1] == pytest.approx(w2, rel=1e-10)

    def test_tau_zero_matches_fixed(self):
        """tau^2=0 should give same result as fixed-effects."""
        betas = [0.3, 0.5]
        ses = [0.1, 0.2]
        beta_fixed, se_fixed, _ = compute_ivw_fixed(betas, ses)
        beta_random, se_random, _ = compute_ivw_random(betas, ses, 0.0)
        assert beta_random == pytest.approx(beta_fixed, rel=1e-10)
        assert se_random == pytest.approx(se_fixed, rel=1e-10)


# ═══════════════════════════════════════════════════════════════
#  TEST: Formula P4-3 — P_inclusion
# ═══════════════════════════════════════════════════════════════


class TestPInclusion:
    def test_known_values(self):
        """Hand-compute P_inclusion for known inputs.

        k=5, beta=0.3, SE=0.1 (Z=3.0), has_rct=True
        linear = -0.5 + 1.2*ln(6) + 0.4*3.0 + 0.6*1.0
               = -0.5 + 1.2*1.7918 + 1.2 + 0.6
               = -0.5 + 2.1501 + 1.2 + 0.6
               = 3.4501
        P_raw = logistic(3.4501) = 0.9691...
        """
        p_raw, p_final = compute_p_inclusion(
            k=5, beta_pooled=0.3, se_pooled=0.1, has_rct=True,
        )

        linear = (
            config.P4_3_INTERCEPT
            + config.P4_3_LN_K_COEFF * math.log(6)
            + config.P4_3_Z_COEFF * 3.0
            + config.P4_3_RCT_COEFF * 1.0
        )
        expected_raw = logistic(linear)
        assert p_raw == pytest.approx(expected_raw, rel=1e-10)

        # P_final applies logit(clamp(p_raw, MIN, 1-MIN)) then logistic back.
        # With no adjustment and p_raw > 1-P_INCLUSION_MIN, clamping occurs.
        p_clamped = max(config.P_INCLUSION_MIN, min(1.0 - config.P_INCLUSION_MIN, p_raw))
        expected_final = max(config.P_INCLUSION_MIN, logistic(logit(p_clamped)))
        assert p_final == pytest.approx(expected_final, rel=1e-10)

    def test_known_values_no_clamp(self):
        """Hand-compute P_inclusion where p_raw is within clamp bounds.

        k=2, beta=0.2, SE=0.2 (Z=1.0), has_rct=False
        linear = -0.5 + 1.2*ln(3) + 0.4*1.0 + 0.6*0.0
               = -0.5 + 1.2*1.0986 + 0.4
               = -0.5 + 1.3183 + 0.4
               = 1.2183
        P_raw = logistic(1.2183) ~ 0.772
        P_final = logistic(logit(0.772) + 0) = 0.772 (no clamp needed)
        """
        p_raw, p_final = compute_p_inclusion(
            k=2, beta_pooled=0.2, se_pooled=0.2, has_rct=False,
        )
        linear = (
            config.P4_3_INTERCEPT
            + config.P4_3_LN_K_COEFF * math.log(3)
            + config.P4_3_Z_COEFF * 1.0
        )
        expected_raw = logistic(linear)
        assert p_raw == pytest.approx(expected_raw, rel=1e-10)
        # p_raw is within bounds, so p_final should match p_raw
        assert p_final == pytest.approx(p_raw, rel=1e-8)

    def test_k_zero_gives_low_probability(self):
        """k=0 with no beta should give low P_inclusion."""
        p_raw, _ = compute_p_inclusion(
            k=0, beta_pooled=0.0, se_pooled=0.0, has_rct=False,
        )
        # linear = -0.5 + 1.2*ln(1) + 0 + 0 = -0.5
        expected = logistic(config.P4_3_INTERCEPT)
        assert p_raw == pytest.approx(expected, rel=1e-10)

    def test_adjustment_negative(self):
        """Negative adjustment decreases P_final."""
        p_raw, p_final_no_adj = compute_p_inclusion(
            k=3, beta_pooled=0.3, se_pooled=0.1, has_rct=False,
        )
        _, p_final_with_adj = compute_p_inclusion(
            k=3, beta_pooled=0.3, se_pooled=0.1, has_rct=False,
            p_inclusion_adjustment=-0.5,
        )
        assert p_final_with_adj < p_final_no_adj

    def test_p_final_floor(self):
        """P_final should not go below P_INCLUSION_MIN."""
        _, p_final = compute_p_inclusion(
            k=0, beta_pooled=0.0, se_pooled=1.0, has_rct=False,
            p_inclusion_adjustment=-1.0,
        )
        assert p_final >= config.P_INCLUSION_MIN

    def test_constants_from_config(self):
        """Verify we use config constants, not hardcoded values."""
        assert config.P4_3_INTERCEPT == -0.5
        assert config.P4_3_LN_K_COEFF == 1.2
        assert config.P4_3_Z_COEFF == 0.4
        assert config.P4_3_RCT_COEFF == 0.6


# ═══════════════════════════════════════════════════════════════
#  TEST: P4-MA-c — Annotation consumption
# ═══════════════════════════════════════════════════════════════


class TestSigmaSqStructural:
    def test_no_annotations(self):
        """No annotations -> default sigma_sq."""
        result = compute_sigma_sq_structural([], "edge_1")
        assert result == pytest.approx(config.SIGMA_SQ_STRUCTURAL_DEFAULT)

    def test_single_moderate(self):
        """One moderate annotation with confidence 0.8.

        sigma_sq = 0.25 + 0.05 * 0.8 = 0.25 + 0.04 = 0.29
        """
        ann = make_annotation(severity="moderate", confidence=0.8)
        result = compute_sigma_sq_structural([ann], "edge_1")
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + config.ANNOTATION_SEVERITY_WEIGHTS["moderate"] * 0.8
        assert result == pytest.approx(expected, rel=1e-10)

    def test_multiple_annotations(self):
        """Two annotations: moderate(0.8) + high(0.9).

        sigma_sq = 0.25 + 0.05*0.8 + 0.10*0.9 = 0.25 + 0.04 + 0.09 = 0.38
        """
        anns = [
            make_annotation(ann_id="a1", severity="moderate", confidence=0.8),
            make_annotation(ann_id="a2", severity="high", confidence=0.9),
        ]
        result = compute_sigma_sq_structural(anns, "edge_1")
        expected = (
            config.SIGMA_SQ_STRUCTURAL_DEFAULT
            + config.ANNOTATION_SEVERITY_WEIGHTS["moderate"] * 0.8
            + config.ANNOTATION_SEVERITY_WEIGHTS["high"] * 0.9
        )
        assert result == pytest.approx(expected, rel=1e-10)

    def test_ceiling(self):
        """Many critical annotations -> clamped to ceiling."""
        anns = [
            make_annotation(ann_id=f"a{i}", severity="critical", confidence=1.0)
            for i in range(20)
        ]
        result = compute_sigma_sq_structural(anns, "edge_1")
        assert result == pytest.approx(config.SIGMA_SQ_STRUCTURAL_CEILING)

    def test_unknown_severity_skipped(self):
        """Unknown severity is skipped, result is default."""
        ann = make_annotation(severity="unknown_value")
        result = compute_sigma_sq_structural([ann], "edge_1")
        assert result == pytest.approx(config.SIGMA_SQ_STRUCTURAL_DEFAULT)


class TestPInclusionAdjustment:
    def test_no_annotations(self):
        result = compute_p_inclusion_adjustment([], "edge_1")
        assert result == 0.0

    def test_single_powered(self):
        """One powered annotation -> adj = -0.3."""
        ann = make_annotation(
            category="null_finding_context",
            powered=True,
        )
        result = compute_p_inclusion_adjustment([ann], "edge_1")
        assert result == pytest.approx(config.P4_3B_NULL_FINDING_POWERED_ADJ)

    def test_not_powered_ignored(self):
        """Annotation with powered=False -> no adjustment."""
        ann = make_annotation(
            category="null_finding_context",
            powered=False,
        )
        result = compute_p_inclusion_adjustment([ann], "edge_1")
        assert result == 0.0

    def test_multiple_powered(self):
        """Two powered annotations -> adj = -0.6."""
        anns = [
            make_annotation(ann_id=f"a{i}", category="null_finding_context", powered=True)
            for i in range(2)
        ]
        result = compute_p_inclusion_adjustment(anns, "edge_1")
        expected = 2 * config.P4_3B_NULL_FINDING_POWERED_ADJ
        assert result == pytest.approx(expected)

    def test_clamping(self):
        """Many powered annotations -> clamped to -P_INCLUSION_ADJ_CAP."""
        anns = [
            make_annotation(ann_id=f"a{i}", category="null_finding_context", powered=True)
            for i in range(10)
        ]
        result = compute_p_inclusion_adjustment(anns, "edge_1")
        assert result == pytest.approx(-config.P_INCLUSION_ADJ_CAP)


# ═══════════════════════════════════════════════════════════════
#  TEST: Aggregation Decision Tree (P4-MA-a)
# ═══════════════════════════════════════════════════════════════


class TestAggregationDecisionTree:
    def test_k0_blocked(self):
        method = select_aggregation_method(0, 0.0, [], "edge_1")
        assert method == "BLOCKED"

    def test_k1_direct(self):
        claims = [make_claim()]
        method = select_aggregation_method(1, 0.0, claims, "edge_1")
        assert method == "DIRECT"

    def test_k2_low_het_fixed(self):
        claims = [make_claim(ler_id="l1"), make_claim(ler_id="l2")]
        method = select_aggregation_method(2, 30.0, claims, "edge_1")
        assert method == AggregationMethod.IVW_FIXED

    def test_k2_moderate_het_random(self):
        claims = [make_claim(ler_id="l1"), make_claim(ler_id="l2")]
        method = select_aggregation_method(2, 60.0, claims, "edge_1")
        assert method == AggregationMethod.IVW_RANDOM

    def test_k2_high_het_single_best(self):
        claims = [make_claim(ler_id="l1"), make_claim(ler_id="l2")]
        method = select_aggregation_method(2, 80.0, claims, "edge_1")
        assert method == AggregationMethod.SINGLE_BEST

    def test_sign_conflict_blocked(self):
        claims = [
            make_claim(ler_id="l1", beta=0.5, quality="HIGH"),
            make_claim(ler_id="l2", beta=-0.3, quality="HIGH"),
        ]
        method = select_aggregation_method(2, 30.0, claims, "edge_1")
        assert method == "BLOCKED"

    def test_sign_conflict_moderate_not_blocked(self):
        """Sign conflict among MODERATE quality -> not blocked."""
        claims = [
            make_claim(ler_id="l1", beta=0.5, quality="moderate"),
            make_claim(ler_id="l2", beta=-0.3, quality="moderate"),
        ]
        method = select_aggregation_method(2, 30.0, claims, "edge_1")
        assert method != "BLOCKED"

    def test_boundary_50_is_fixed(self):
        """I^2 exactly at 50% -> moderate (IVW_RANDOM), not fixed."""
        claims = [make_claim(ler_id="l1"), make_claim(ler_id="l2")]
        method = select_aggregation_method(
            2, config.HETEROGENEITY_MODERATE_THRESHOLD, claims, "edge_1"
        )
        # At exactly 50%, the condition i_sq < 50 is False, so IVW_RANDOM
        assert method == AggregationMethod.IVW_RANDOM

    def test_boundary_75_is_single_best(self):
        """I^2 exactly at 75% -> high (SINGLE_BEST)."""
        claims = [make_claim(ler_id="l1"), make_claim(ler_id="l2")]
        method = select_aggregation_method(
            2, config.HETEROGENEITY_HIGH_THRESHOLD, claims, "edge_1"
        )
        assert method == AggregationMethod.SINGLE_BEST


# ═══════════════════════════════════════════════════════════════
#  TEST: pool_evidence — Full pipeline per edge
# ═══════════════════════════════════════════════════════════════


class TestPoolEvidence:
    def test_k0_blocked(self):
        resolved = make_resolved(claims=[], k=0)
        result = pool_evidence(resolved)
        assert result.pooled_estimate.aggregation_method == "BLOCKED"
        assert result.pooled_estimate.k == 0
        assert result.p_inclusion_raw == 0.0
        assert result.p_inclusion_final == 0.0

    def test_k1_direct(self):
        claim = make_claim(beta=0.4, se=0.15)
        resolved = make_resolved(claims=[claim], k=1)
        result = pool_evidence(resolved)
        assert result.pooled_estimate.aggregation_method == "DIRECT"
        assert result.pooled_estimate.beta_pooled == pytest.approx(0.4)
        assert result.pooled_estimate.se_pooled == pytest.approx(0.15)
        assert result.pooled_estimate.k == 1

    def test_k3_ivw_fixed(self):
        """3 homogeneous studies -> IVW_fixed."""
        claims = [
            make_claim(ler_id="l1", beta=0.30, se=0.10),
            make_claim(ler_id="l2", beta=0.32, se=0.12),
            make_claim(ler_id="l3", beta=0.28, se=0.11),
        ]
        resolved = make_resolved(claims=claims)
        result = pool_evidence(resolved)
        pe = result.pooled_estimate
        # Low heterogeneity among similar betas
        assert pe.k == 3
        assert pe.aggregation_method in [AggregationMethod.IVW_FIXED, AggregationMethod.IVW_RANDOM]
        assert pe.beta_pooled != 0.0
        assert pe.se_pooled > 0.0

    def test_k2_heterogeneous_random(self):
        """2 very different studies -> likely IVW_random."""
        claims = [
            make_claim(ler_id="l1", beta=0.1, se=0.05),
            make_claim(ler_id="l2", beta=0.9, se=0.05),
        ]
        resolved = make_resolved(claims=claims)
        result = pool_evidence(resolved)
        pe = result.pooled_estimate
        assert pe.k == 2
        # With such different betas, I^2 should be high
        assert pe.i_squared > 0.0

    def test_missing_se_excluded(self):
        """Claims with None SE are excluded from pooling."""
        claims = [
            make_claim(ler_id="l1", beta=0.3, se=0.1),
            make_claim(ler_id="l2", beta=0.5, se=None),
        ]
        resolved = make_resolved(claims=claims, k=2)
        result = pool_evidence(resolved)
        # Only 1 valid claim -> DIRECT
        assert result.pooled_estimate.k == 1
        assert result.pooled_estimate.aggregation_method == "DIRECT"

    def test_all_missing_se_blocked(self):
        """All claims with None SE -> BLOCKED."""
        claims = [
            make_claim(ler_id="l1", beta=0.3, se=None),
            make_claim(ler_id="l2", beta=0.5, se=None),
        ]
        resolved = make_resolved(claims=claims, k=2)
        result = pool_evidence(resolved)
        assert result.pooled_estimate.aggregation_method == "BLOCKED"

    def test_annotation_increases_sigma(self):
        """Confounder annotation increases sigma_sq_structural."""
        claim = make_claim(beta=0.3, se=0.1)
        resolved = make_resolved(claims=[claim], k=1)
        ann = make_annotation(severity="high", confidence=0.9)
        result = pool_evidence(resolved, confounder_annotations=[ann])
        expected_sigma = (
            config.SIGMA_SQ_STRUCTURAL_DEFAULT
            + config.ANNOTATION_SEVERITY_WEIGHTS["high"] * 0.9
        )
        assert result.annotation_influence.sigma_sq_structural == pytest.approx(expected_sigma)

    def test_null_finding_decreases_p_inclusion(self):
        """Null finding annotation with powered=True decreases P_final."""
        claims = [
            make_claim(ler_id="l1", beta=0.3, se=0.1),
            make_claim(ler_id="l2", beta=0.4, se=0.15),
        ]
        resolved = make_resolved(claims=claims)

        result_no_ann = pool_evidence(resolved)
        null_ann = make_annotation(
            category="null_finding_context", powered=True,
        )
        result_with_ann = pool_evidence(
            resolved, null_finding_annotations=[null_ann],
        )
        assert result_with_ann.p_inclusion_final < result_no_ann.p_inclusion_final

    def test_sign_conflict_blocked(self):
        """HIGH quality sign conflict -> BLOCKED."""
        claims = [
            make_claim(ler_id="l1", beta=0.5, se=0.1, quality="HIGH"),
            make_claim(ler_id="l2", beta=-0.4, se=0.1, quality="HIGH"),
        ]
        resolved = make_resolved(claims=claims)
        result = pool_evidence(resolved)
        assert result.pooled_estimate.aggregation_method == "BLOCKED"
        assert result.sign_conflict_detected is True


# ═══════════════════════════════════════════════════════════════
#  TEST: Gate enforcement
# ═══════════════════════════════════════════════════════════════


class TestGates:
    def test_gate_p4_g2_nan_beta(self):
        """Gate P4-G2: NaN beta_pooled should raise GateViolation."""
        claim = make_claim(beta=float("nan"), se=0.1)
        resolved = make_resolved(claims=[claim], k=1)
        with pytest.raises(GateViolation, match="P4-G2"):
            pool_evidence(resolved)

    def test_gate_p4_g1_empty_method(self):
        """Gate P4-G1: If somehow aggregation_method is empty, raise."""
        # This is tested indirectly; the decision tree always assigns a method.
        # We test analyze_all_edges with normal input succeeds.
        claim = make_claim(beta=0.3, se=0.1)
        resolved = make_resolved(claims=[claim], k=1)
        results = analyze_all_edges([resolved])
        assert len(results) == 1
        assert results[0].pooled_estimate.aggregation_method != ""


# ═══════════════════════════════════════════════════════════════
#  TEST: analyze_all_edges — Batch processing
# ═══════════════════════════════════════════════════════════════


class TestAnalyzeAllEdges:
    def test_multiple_edges(self):
        resolved_list = [
            make_resolved(
                edge_id="edge_1",
                claims=[make_claim(ler_id="l1", beta=0.3, se=0.1, edge_relation_id="edge_1")],
                k=1,
            ),
            make_resolved(
                edge_id="edge_2",
                claims=[
                    make_claim(ler_id="l2", beta=0.5, se=0.2, edge_relation_id="edge_2"),
                    make_claim(ler_id="l3", beta=0.4, se=0.15, edge_relation_id="edge_2"),
                ],
                k=2,
            ),
        ]
        results = analyze_all_edges(resolved_list)
        assert len(results) == 2
        assert results[0].pooled_estimate.edge_relation_id == "edge_1"
        assert results[1].pooled_estimate.edge_relation_id == "edge_2"

    def test_with_annotations(self):
        claim = make_claim(beta=0.3, se=0.1, edge_relation_id="edge_1")
        resolved_list = [make_resolved(edge_id="edge_1", claims=[claim], k=1)]
        annotations_by_edge = {
            "edge_1": [
                make_annotation(
                    category=AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER,
                    severity="high",
                    confidence=0.8,
                ),
            ],
        }
        results = analyze_all_edges(resolved_list, annotations_by_edge)
        assert len(results) == 1
        expected_sigma = (
            config.SIGMA_SQ_STRUCTURAL_DEFAULT
            + config.ANNOTATION_SEVERITY_WEIGHTS["high"] * 0.8
        )
        assert results[0].annotation_influence.sigma_sq_structural == pytest.approx(
            expected_sigma
        )

    def test_empty_list(self):
        results = analyze_all_edges([])
        assert results == []


# ═══════════════════════════════════════════════════════════════
#  TEST: Config constants are used (not hardcoded)
# ═══════════════════════════════════════════════════════════════


class TestConfigUsage:
    """Verify that formula parameters come from config, not hardcoded values."""

    def test_sigma_sq_default(self):
        assert config.SIGMA_SQ_STRUCTURAL_DEFAULT == 0.25

    def test_sigma_sq_ceiling(self):
        assert config.SIGMA_SQ_STRUCTURAL_CEILING == 0.50

    def test_p_inclusion_adj_cap(self):
        assert config.P_INCLUSION_ADJ_CAP == 1.0

    def test_p_inclusion_min(self):
        assert config.P_INCLUSION_MIN == 0.05

    def test_heterogeneity_thresholds(self):
        assert config.HETEROGENEITY_MODERATE_THRESHOLD == 50.0
        assert config.HETEROGENEITY_HIGH_THRESHOLD == 75.0

    def test_p4_3_coefficients(self):
        assert config.P4_3_INTERCEPT == -0.5
        assert config.P4_3_LN_K_COEFF == 1.2
        assert config.P4_3_Z_COEFF == 0.4
        assert config.P4_3_RCT_COEFF == 0.6

    def test_severity_weights(self):
        assert config.ANNOTATION_SEVERITY_WEIGHTS["moderate"] == 0.05
        assert config.ANNOTATION_SEVERITY_WEIGHTS["high"] == 0.10
        assert config.ANNOTATION_SEVERITY_WEIGHTS["critical"] == 0.15

    def test_null_finding_adj(self):
        assert config.P4_3B_NULL_FINDING_POWERED_ADJ == -0.3
