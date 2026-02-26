"""Tests for ALG-D3 Synergy & Bundle Computation.

Covers:
    D3a: JPO (Jaccard Pathway Overlap) with hand-computed examples
    D3b: CCS (Complementary Convergence Score)
    D3c: Bundle effect computation with overlap penalty + synergy bonus
    D-G3: Gate validation
    Full integration: compute_bundles end-to-end
"""
from __future__ import annotations

import numpy as np
import pytest

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from crci.algorithm.chain_d_simulation.synergy_bundle import (
    BundleEffects,
    BundleResult,
    PairwiseMetrics,
    _compute_bundle_effect_per_draw,
    _generate_candidate_bundles,
    _validate_gate_d_g3,
    compute_bundles,
    compute_ccs,
    compute_jpo,
)
from crci.algorithm.chain_d_simulation.effect_propagation import (
    EffectResult,
    InterventionEffects,
    PropagationMethod,
)
from crci.algorithm.chain_d_simulation.intervention_loader import (
    ContraindicationDef,
    DoseResponseSpec,
    InterventionDef,
    InterventionSet,
)
from crci.algorithm.chain_d_simulation.safety_checker import (
    InterventionSafety,
    SafetyResult,
    SafetyStatus,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_intervention(action_id, action_class="exercise", bridges=None):
    return InterventionDef(
        action_id=action_id,
        action_label=f"Test {action_id}",
        action_class=action_class,
        dose_type="min/wk",
        dose_unit="min/wk",
        dose_min=0.0,
        dose_max=300.0,
        dose_recommended_start=150.0,
        dose_step=30.0,
        time_cost_min=150.0,
        cognitive_load=0.2,
        logistics_load=0.3,
        overall_burden=0.4,
        adherence_rate_default=0.7,
        evidence_basis="rct",
        evidence_strength="HIGH",
        dose_bridges=bridges or [],
    )


def _make_dose_bridge(output_node_id, maps_to_node_id=None):
    return DoseResponseSpec(
        bridge_id="BR_01",
        action_id="ACT_01",
        output_node_id=output_node_id,
        maps_to_node_id=maps_to_node_id,
        dose_type="continuous",
        dose_unit="min/wk",
        dose_min=0.0,
        dose_max=300.0,
        dose_step=30.0,
        dose_reference=150.0,
        dose_response_family="emax",
        dose_response_params={},
        bridge_effect_sign=1.0,
        bridge_gain=1.0,
        bridge_noise_sd=0.1,
    )


def _make_intervention_set(interventions):
    return InterventionSet(
        interventions=interventions,
        intervention_index={i.action_id: idx for idx, i in enumerate(interventions)},
        synergy_records=[],
        synergy_lookup={},
        all_contraindications=[],
    )


def _make_safety_result(interventions, blocked_ids=None):
    blocked_ids = blocked_ids or []
    safety = {}
    n_clear = 0
    n_warning = 0
    n_blocked = 0
    for i in interventions:
        if i.action_id in blocked_ids:
            status = SafetyStatus.BLOCKED
            n_blocked += 1
        else:
            status = SafetyStatus.CLEAR
            n_clear += 1
        safety[i.action_id] = InterventionSafety(
            action_id=i.action_id,
            action_label=i.action_label,
            status=status,
            evaluations=[],
            n_triggered=0,
            n_blocked=1 if status == SafetyStatus.BLOCKED else 0,
            n_warnings=0,
            blocking_rules=[],
            warning_rules=[],
        )
    return SafetyResult(
        intervention_safety=safety,
        n_total=len(interventions),
        n_clear=n_clear,
        n_warning=n_warning,
        n_blocked=n_blocked,
        blocked_action_ids=blocked_ids,
    )


def _make_effect_result(intervention_effects, cognitive_indices=None):
    cog_idx = cognitive_indices or [0]
    n_draws = list(intervention_effects.values())[0].delta_C.shape[0] if intervention_effects else 0
    n_nodes = list(intervention_effects.values())[0].delta_theta.shape[1] if intervention_effects else 0
    return EffectResult(
        intervention_effects=intervention_effects,
        n_draws=n_draws,
        n_nodes=n_nodes,
        cognitive_node_indices=cog_idx,
        cognitive_node_ids=[f"N_COG_{i}" for i in cog_idx],
        gate_d_g2_passed=True,
    )


def _make_interv_effects(action_id, delta_C_values, n_nodes=4):
    n_draws = len(delta_C_values)
    return InterventionEffects(
        intervention_id=action_id,
        delta_theta=np.zeros((n_draws, n_nodes)),
        delta_C=np.array(delta_C_values),
        propagation_methods=[PropagationMethod.MATRIX] * n_draws,
        ceiling_clipped=np.zeros(n_draws, dtype=bool),
    )


# ═══════════════════════════════════════════════════════════════
#  Test D3a: JPO (Jaccard Pathway Overlap)
# ═══════════════════════════════════════════════════════════════


class TestJPO:
    """D3a: JPO = |P_a ∩ P_b| / |P_a ∪ P_b|."""

    def test_identical_pathways(self):
        """Same pathways → JPO = 1.0."""
        assert compute_jpo({"M1", "M2"}, {"M1", "M2"}) == 1.0

    def test_disjoint_pathways(self):
        """No overlap → JPO = 0.0."""
        assert compute_jpo({"M1", "M2"}, {"M3", "M4"}) == 0.0

    def test_partial_overlap(self):
        """Partial overlap → JPO between 0 and 1.

        {M1, M2} ∩ {M2, M3} = {M2} → |1| / |{M1,M2,M3}| = 1/3
        """
        result = compute_jpo({"M1", "M2"}, {"M2", "M3"})
        assert abs(result - 1.0 / 3.0) < 1e-10

    def test_empty_sets(self):
        """Both empty → JPO = 0.0."""
        assert compute_jpo(set(), set()) == 0.0

    def test_one_empty(self):
        """One empty → JPO = 0.0."""
        assert compute_jpo({"M1"}, set()) == 0.0

    def test_subset(self):
        """{M1} ⊂ {M1, M2} → JPO = 1/2."""
        result = compute_jpo({"M1"}, {"M1", "M2"})
        assert abs(result - 0.5) < 1e-10


# ═══════════════════════════════════════════════════════════════
#  Test D3b: CCS (Complementary Convergence Score)
# ═══════════════════════════════════════════════════════════════


class TestCCS:
    """D3b: CCS = (1 − JPO) × 𝟙[shared_convergence]."""

    def test_complementary_with_convergence(self):
        """Disjoint pathways + both improve cognitive → CCS = 1.0."""
        jpo = 0.0
        effect_a = np.array([0.5, 0.3])  # positive at cognitive node 0
        effect_b = np.array([0.2, 0.4])  # positive at cognitive node 0
        result = compute_ccs(jpo, effect_a, effect_b, [0])
        assert abs(result - 1.0) < 1e-10

    def test_identical_pathways_no_ccs(self):
        """JPO = 1.0 → CCS = 0.0 (even with convergence)."""
        jpo = 1.0
        effect_a = np.array([0.5])
        effect_b = np.array([0.3])
        result = compute_ccs(jpo, effect_a, effect_b, [0])
        assert abs(result - 0.0) < 1e-10

    def test_no_convergence(self):
        """One intervention worsens cognitive → no shared_convergence → CCS = 0."""
        jpo = 0.0
        effect_a = np.array([0.5])   # improves
        effect_b = np.array([-0.3])  # worsens
        result = compute_ccs(jpo, effect_a, effect_b, [0])
        assert result == 0.0

    def test_partial_overlap_with_convergence(self):
        """JPO = 0.5 + convergence → CCS = 0.5."""
        jpo = 0.5
        effect_a = np.array([0.3, 0.1])
        effect_b = np.array([0.2, 0.1])
        result = compute_ccs(jpo, effect_a, effect_b, [0])
        assert abs(result - 0.5) < 1e-10

    def test_no_cognitive_indices(self):
        """No cognitive nodes → CCS = 0."""
        result = compute_ccs(0.0, np.array([0.5]), np.array([0.3]), [])
        assert result == 0.0


# ═══════════════════════════════════════════════════════════════
#  Test D3c: Bundle Effect Computation
# ═══════════════════════════════════════════════════════════════


class TestBundleEffectComputation:
    """D3c: ΔC_bundle with overlap penalty and synergy bonus."""

    def test_no_overlap_no_synergy(self):
        """Two interventions, JPO=0, CCS=0 → ΔC_bundle = ΔC_a + ΔC_b."""
        n_draws = 5
        delta_C = {
            "A": np.full(n_draws, 0.5),
            "B": np.full(n_draws, 0.3),
        }
        pairwise = {
            ("A", "B"): PairwiseMetrics("A", "B", jpo=0.0, ccs=0.0),
        }
        gamma = np.full(n_draws, 0.1)

        result = _compute_bundle_effect_per_draw(
            ("A", "B"), delta_C, pairwise, gamma, n_draws,
        )

        # No overlap → discount = 1.0 for both → ΔC_bundle = 0.5 + 0.3 = 0.8
        np.testing.assert_allclose(result, 0.8, atol=1e-10)

    def test_full_overlap_penalty(self):
        """JPO=1.0 → discount = 1 - 1.0 × 0.5 = 0.5 for each."""
        n_draws = 5
        delta_C = {
            "A": np.full(n_draws, 1.0),
            "B": np.full(n_draws, 1.0),
        }
        pairwise = {
            ("A", "B"): PairwiseMetrics("A", "B", jpo=1.0, ccs=0.0),
        }
        gamma = np.zeros(n_draws)

        result = _compute_bundle_effect_per_draw(
            ("A", "B"), delta_C, pairwise, gamma, n_draws,
        )

        # Each intervention gets discount = 1 - 1.0 × 0.5 = 0.5
        # ΔC_bundle = 1.0 × 0.5 + 1.0 × 0.5 = 1.0
        np.testing.assert_allclose(result, 1.0, atol=1e-10)

    def test_synergy_bonus(self):
        """CCS > 0 adds synergy bonus term."""
        n_draws = 5
        delta_C = {
            "A": np.full(n_draws, 0.4),
            "B": np.full(n_draws, 0.4),
        }
        pairwise = {
            ("A", "B"): PairwiseMetrics("A", "B", jpo=0.0, ccs=1.0),
        }
        gamma = {("A", "B"): np.full(n_draws, 0.2)}

        result = _compute_bundle_effect_per_draw(
            ("A", "B"), delta_C, pairwise, gamma, n_draws,
        )

        # Term 1: 0.4 + 0.4 = 0.8 (no overlap)
        # Term 2: 0.2 × 1.0 × √|0.4 × 0.4| = 0.2 × 0.4 = 0.08
        # Total: 0.88
        np.testing.assert_allclose(result, 0.88, atol=1e-10)

    def test_three_member_bundle(self):
        """Three-intervention bundle with pairwise interactions."""
        n_draws = 3
        delta_C = {
            "A": np.full(n_draws, 0.5),
            "B": np.full(n_draws, 0.3),
            "C": np.full(n_draws, 0.2),
        }
        pairwise = {
            ("A", "B"): PairwiseMetrics("A", "B", jpo=0.0, ccs=0.0),
            ("A", "C"): PairwiseMetrics("A", "C", jpo=0.0, ccs=0.0),
            ("B", "C"): PairwiseMetrics("B", "C", jpo=0.0, ccs=0.0),
        }
        gamma = {
            ("A", "B"): np.zeros(n_draws),
            ("A", "C"): np.zeros(n_draws),
            ("B", "C"): np.zeros(n_draws),
        }

        result = _compute_bundle_effect_per_draw(
            ("A", "B", "C"), delta_C, pairwise, gamma, n_draws,
        )

        # No overlap → simple sum: 0.5 + 0.3 + 0.2 = 1.0
        np.testing.assert_allclose(result, 1.0, atol=1e-10)


# ═══════════════════════════════════════════════════════════════
#  Test Candidate Bundle Generation
# ═══════════════════════════════════════════════════════════════


class TestCandidateGeneration:
    """Bundle candidate generation."""

    def test_small_set_exhaustive(self):
        """3 candidates → all combos of size 2-4."""
        candidates = _generate_candidate_bundles(["A", "B", "C"], max_size=4)
        # Size 2: C(3,2) = 3, Size 3: C(3,3) = 1 → total 4
        assert len(candidates) == 4

    def test_max_size_respected(self):
        """Max size limits combinations."""
        candidates = _generate_candidate_bundles(["A", "B", "C", "D"], max_size=2)
        # Only size 2: C(4,2) = 6
        assert len(candidates) == 6

    def test_single_intervention_no_bundles(self):
        """1 intervention → no bundles possible."""
        candidates = _generate_candidate_bundles(["A"], max_size=4)
        assert len(candidates) == 0


# ═══════════════════════════════════════════════════════════════
#  Test Gate D-G3
# ═══════════════════════════════════════════════════════════════


class TestGateDG3:
    """Gate D-G3: finite ΔC, γ in valid range."""

    def test_passes_valid(self):
        result = BundleResult(
            pairwise_metrics={},
            bundle_effects={
                "A+B": BundleEffects("A+B", ("A", "B"), np.zeros(5), 0.0, 0.0, 5),
            },
            n_bundles_evaluated=1,
            n_candidates_filtered=0,
        )
        gamma = {("A", "B"): np.full(5, 0.1)}
        _validate_gate_d_g3(result, gamma)  # should not raise

    def test_fails_nan_bundle(self):
        dc = np.array([0.1, np.nan, 0.3])
        result = BundleResult(
            pairwise_metrics={},
            bundle_effects={
                "A+B": BundleEffects("A+B", ("A", "B"), dc, 0.0, 0.0, 3),
            },
            n_bundles_evaluated=1,
            n_candidates_filtered=0,
        )
        gamma = {("A", "B"): np.full(3, 0.1)}
        with pytest.raises(GateViolation, match="D-G3"):
            _validate_gate_d_g3(result, gamma)

    def test_fails_negative_gamma(self):
        result = BundleResult(
            pairwise_metrics={},
            bundle_effects={},
            n_bundles_evaluated=0,
            n_candidates_filtered=0,
        )
        # γ exceeds -γ_cap (0.40) — should fail
        gamma = {("A", "B"): np.array([-0.5, 0.2, 0.3])}
        with pytest.raises(GateViolation, match="D-G3"):
            _validate_gate_d_g3(result, gamma)


# ═══════════════════════════════════════════════════════════════
#  Integration: Full compute_bundles
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Full D3-synergy pipeline."""

    def test_two_interventions_bundle(self):
        """Two eligible interventions produce one bundle."""
        n_draws = 100
        interventions = [
            _make_intervention("ACT_A", bridges=[_make_dose_bridge("N_M1")]),
            _make_intervention("ACT_B", bridges=[_make_dose_bridge("N_M3")]),
        ]
        intervention_set = _make_intervention_set(interventions)
        safety = _make_safety_result(interventions)

        # Create effects: set cognitive node improvement
        effects_a = _make_interv_effects("ACT_A", [0.5] * n_draws, n_nodes=4)
        effects_a_theta = np.zeros((n_draws, 4))
        effects_a_theta[:, 0] = 0.3  # cognitive node improvement
        effects_a = InterventionEffects(
            intervention_id="ACT_A",
            delta_theta=effects_a_theta,
            delta_C=np.full(n_draws, 0.5),
            propagation_methods=[PropagationMethod.MATRIX] * n_draws,
            ceiling_clipped=np.zeros(n_draws, dtype=bool),
        )
        effects_b = InterventionEffects(
            intervention_id="ACT_B",
            delta_theta=np.zeros((n_draws, 4)),
            delta_C=np.full(n_draws, 0.3),
            propagation_methods=[PropagationMethod.MATRIX] * n_draws,
            ceiling_clipped=np.zeros(n_draws, dtype=bool),
        )

        effect_result = _make_effect_result(
            {"ACT_A": effects_a, "ACT_B": effects_b},
            cognitive_indices=[0],
        )

        result = compute_bundles(
            effect_result, intervention_set, safety,
            n_draws=n_draws, seed=42,
        )

        assert result.gate_d_g3_passed
        assert result.n_bundles_evaluated == 1
        assert "ACT_A+ACT_B" in result.bundle_effects

        bundle = result.bundle_effects["ACT_A+ACT_B"]
        assert bundle.n_draws == n_draws
        # Bundle mean should be >= sum of individuals minus overlap
        assert bundle.mean_delta_C > 0

    def test_blocked_interventions_excluded(self):
        """Blocked interventions are excluded from bundles."""
        n_draws = 10
        interventions = [
            _make_intervention("ACT_A"),
            _make_intervention("ACT_B"),
            _make_intervention("ACT_C"),
        ]
        intervention_set = _make_intervention_set(interventions)
        safety = _make_safety_result(interventions, blocked_ids=["ACT_B"])

        effects = {}
        for aid in ["ACT_A", "ACT_B", "ACT_C"]:
            effects[aid] = _make_interv_effects(aid, [0.3] * n_draws)
        effect_result = _make_effect_result(effects)

        result = compute_bundles(
            effect_result, intervention_set, safety,
            n_draws=n_draws, seed=42,
        )

        # Only ACT_A + ACT_C bundle (ACT_B blocked)
        assert result.n_bundles_evaluated == 1
        assert result.n_candidates_filtered == 1
        bundle_ids = list(result.bundle_effects.keys())
        assert "ACT_A+ACT_C" in bundle_ids

    def test_gamma_sampling_reproducible(self):
        """Same seed → same γ → same bundle effects."""
        n_draws = 50
        interventions = [
            _make_intervention("ACT_A"),
            _make_intervention("ACT_B"),
        ]
        intervention_set = _make_intervention_set(interventions)
        safety = _make_safety_result(interventions)

        effects = {
            "ACT_A": _make_interv_effects("ACT_A", [0.5] * n_draws),
            "ACT_B": _make_interv_effects("ACT_B", [0.3] * n_draws),
        }
        effect_result = _make_effect_result(effects)

        r1 = compute_bundles(effect_result, intervention_set, safety, seed=123)
        r2 = compute_bundles(effect_result, intervention_set, safety, seed=123)

        np.testing.assert_array_equal(
            r1.bundle_effects["ACT_A+ACT_B"].delta_C_bundle,
            r2.bundle_effects["ACT_A+ACT_B"].delta_C_bundle,
        )

    def test_uses_config_constants(self):
        """Verify config constants are set correctly."""
        assert config.D3_GAMMA_BETA_ALPHA == 2.0
        assert config.D3_GAMMA_BETA_BETA == 4.0
        assert config.SYNERGY_GAMMA_CAP_DEFAULT == 0.40
        assert config.D3_JPO_OVERLAP_PENALTY_FACTOR == 0.5
        assert config.D3_MAX_BUNDLE_SIZE == 4
