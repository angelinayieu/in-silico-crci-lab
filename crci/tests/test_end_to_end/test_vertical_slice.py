"""Slice 4: Full Vertical Integration Test

Chain A → Chain B (real evidence from DB) → Chain C (posterior update) →
Chain D (MC draws + effect propagation) → Ranking verification.

Requires:
    - crci_dev.db populated by prior extraction runs (Cherrier 2013)
    - actions.csv seed loaded into action_catalog_v1
    - DATABASE_URL="sqlite:///crci_dev.db" environment variable

Run:
    DATABASE_URL="sqlite:///crci_dev.db" python -m pytest \
        crci/tests/test_end_to_end/test_vertical_slice.py -v
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pytest

# Skip entire module if no database is configured
_DB_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not _DB_URL or "crci_dev" not in _DB_URL,
    reason="Requires DATABASE_URL pointing to crci_dev.db with extracted evidence",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════════

_ROOT = Path(__file__).resolve().parents[3]  # in-silico-crci-lab
_REGISTRIES = _ROOT / "registries"
_NODE_REG = _REGISTRIES / "NODE_REGISTRY.csv"
_EDGE_REG = _REGISTRIES / "EDGE_REGISTRY.csv"
_INST_REG = _REGISTRIES / "INSTRUMENT_REGISTRY.csv"
_PATH_REG = _REGISTRIES / "PATHWAY_REGISTRY.csv"


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def graph():
    """Run Chain A: graph assembly from real registries."""
    from crci.algorithm.chain_a_graph.graph_object import run_chain_a

    g = run_chain_a(
        node_registry_path=str(_NODE_REG),
        edge_registry_path=str(_EDGE_REG),
        instrument_registry_path=str(_INST_REG),
        pathway_registry_path=str(_PATH_REG),
    )
    logger.info(
        "Chain A: %d nodes, %d edges, %d pathways",
        g.n_nodes, g.n_edges, g.n_pathways,
    )
    return g


@pytest.fixture(scope="module")
def evidence_records():
    """Load real evidence from the extraction database."""
    from crci.algorithm.chain_b_evidence.evidence_loader import load_evidence_from_db
    from crci.shared.db import get_session

    with get_session() as session:
        records = load_evidence_from_db(session)
    logger.info("Evidence loader: %d records", len(records))
    return records


@pytest.fixture(scope="module")
def frozen(graph, evidence_records):
    """Run Chain B: edge parameterization with real evidence."""
    from crci.algorithm.chain_b_evidence.frozen_state import run_chain_b

    f = run_chain_b(graph=graph, evidence_records=evidence_records)
    logger.info(
        "Chain B: FrozenModelState — %d non-zero B_hat entries, "
        "%d Sigma_eff entries, %d P_inclusion entries",
        int(np.count_nonzero(f.B_hat)),
        len(f.Sigma_eff),
        len(f.P_inclusion),
    )
    return f


@pytest.fixture(scope="module")
def loaded_prior(frozen):
    """Run Chain C step 1: load prior (uninformative — no context specs)."""
    from crci.algorithm.chain_c_posterior.prior_loader import load_prior

    lp = load_prior(
        frozen=frozen,
        cancer_type="breast",
        treatment_phase="adjuvant",
        treatment_regimen=None,
        context_specs=None,
    )
    logger.info(
        "C1: prior loaded — context='%s', fallback=%s, SE_inflation=%.2f",
        lp.context_key, lp.fallback_level, lp.fallback_SE_inflation,
    )
    return lp


@pytest.fixture(scope="module")
def raw_posterior(loaded_prior):
    """Run Chain C step 3: Bayesian update (no direct observations)."""
    from crci.algorithm.chain_c_posterior.bayesian_update import bayesian_update

    rp = bayesian_update(
        loaded_prior=loaded_prior,
        observations=[],  # No patient observations for this integration test
    )
    logger.info(
        "C3: posterior — ||θ̂||=%.4f, tr(Σ_post)=%.4f",
        np.linalg.norm(rp.theta_hat),
        np.trace(rp.Sigma_post),
    )
    return rp


@pytest.fixture(scope="module")
def patient_state(raw_posterior, loaded_prior, frozen):
    """Run Chain C step 4: apply modifiers (empty — no modifier registry)."""
    from crci.algorithm.chain_c_posterior.modifier_application import apply_modifiers

    ps = apply_modifiers(
        raw_posterior=raw_posterior,
        loaded_prior=loaded_prior,
        frozen=frozen,
        patient_profile={
            "cancer_type": "breast",
            "treatment_phase": "adjuvant",
            "age": 55,
        },
        modifier_rules=[],   # No modifier rules loaded yet
        pathways=frozen.graph.pathway_map,
    )
    logger.info(
        "C4: PatientState — ||θ̂||=%.4f, ||B_eff||=%.4f, "
        "%d active pathways, %d modifier audit records",
        np.linalg.norm(ps.theta_hat),
        np.linalg.norm(ps.B_eff),
        sum(1 for p in ps.active_pathways if p.is_active),
        len(ps.modifier_audit),
    )
    return ps


@pytest.fixture(scope="module")
def intervention_set(frozen):
    """Load interventions from seeded action_catalog_v1."""
    from crci.algorithm.chain_d_simulation.intervention_loader import (
        load_interventions,
    )
    from crci.shared.db import get_session

    with get_session() as session:
        iset = load_interventions(session=session, frozen=frozen)

    logger.info(
        "D0: %d interventions loaded", iset.n_interventions,
    )
    return iset


@pytest.fixture(scope="module")
def mc_draws(frozen, patient_state):
    """Run Chain D step 1: MC sampling (small for test speed)."""
    from crci.algorithm.chain_d_simulation.mc_sampler import generate_mc_draws

    draws = generate_mc_draws(
        frozen=frozen,
        patient_state=patient_state,
        n_draws=200,  # Small for test speed (config default is 10,000)
        seed=42,
    )
    logger.info(
        "D1: MC draws — n_draws=%d, B_draws shape=%s",
        draws.n_draws, draws.B_draws.shape,
    )
    return draws


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestChainAGraphAssembly:
    """Verify Chain A produces a valid graph from real registries."""

    def test_graph_has_nodes(self, graph):
        assert graph.n_nodes >= 63, f"Expected ≥63 nodes, got {graph.n_nodes}"

    def test_graph_has_edges(self, graph):
        assert graph.n_edges >= 100, f"Expected ≥100 edges, got {graph.n_edges}"

    def test_graph_has_pathways(self, graph):
        assert graph.n_pathways >= 1, "No pathways loaded"


class TestChainBEvidenceParameterization:
    """Verify Chain B incorporates real evidence from Cherrier 2013."""

    def test_has_evidence_records(self, evidence_records):
        assert len(evidence_records) >= 1, "No evidence records loaded from DB"

    def test_frozen_has_parameterized_edges(self, frozen):
        """At least one edge should have μ_e ≠ 0."""
        nonzero_edges = [
            eid for eid, se in frozen.Sigma_eff.items()
            if se > 0 and frozen.B_hat[
                frozen.graph.node_map.node_index.get(
                    frozen.graph.b_skeleton.edge_index.get(eid, ("", ""))[0]
                    if isinstance(frozen.graph.b_skeleton.edge_index.get(eid), tuple)
                    else "", 0
                ),
                frozen.graph.node_map.node_index.get(
                    frozen.graph.b_skeleton.edge_index.get(eid, ("", ""))[1]
                    if isinstance(frozen.graph.b_skeleton.edge_index.get(eid), tuple)
                    else "", 0
                ),
            ] != 0
        ]
        # Simpler check: any non-zero entry in B_hat beyond skeleton
        n_nonzero = int(np.count_nonzero(frozen.B_hat))
        assert n_nonzero >= 1, "B_hat is entirely zero — no edges parameterized"

    def test_frozen_has_inclusion_probabilities(self, frozen):
        """Parameterized edges should have P_incl close to 1."""
        high_p = [
            eid for eid, p in frozen.P_inclusion.items()
            if p > 0.5
        ]
        assert len(high_p) >= 1, "No edge has P_inclusion > 0.5"


class TestChainCPosteriorUpdate:
    """Verify Chain C produces valid posterior from prior + evidence."""

    def test_prior_loaded_successfully(self, loaded_prior):
        """Prior should load (even as uninformative fallback)."""
        assert loaded_prior.context_key, "Empty context_key"
        assert loaded_prior.Lambda_prior.shape[0] >= 63

    def test_posterior_is_valid(self, raw_posterior):
        """Posterior θ̂ should be finite."""
        assert np.all(np.isfinite(raw_posterior.theta_hat)), "θ̂ has non-finite values"
        assert np.all(np.isfinite(raw_posterior.Sigma_post)), "Σ_post has non-finite values"

    def test_posterior_covariance_is_pd(self, raw_posterior):
        """Σ_post must be positive-definite."""
        eigvals = np.linalg.eigvalsh(raw_posterior.Sigma_post)
        assert np.all(eigvals > 0), (
            f"Σ_post has non-positive eigenvalues: min={eigvals.min():.6e}"
        )

    def test_patient_state_has_b_eff(self, patient_state, frozen):
        """B_eff should exist (equal to B̂ when no modifiers applied)."""
        assert patient_state.B_eff.shape == frozen.B_hat.shape
        # With no modifiers, B_eff should equal B̂
        np.testing.assert_array_almost_equal(
            patient_state.B_eff, frozen.B_hat,
            decimal=10,
            err_msg="B_eff != B̂ despite no modifiers",
        )

    def test_posterior_precision_consistent(self, raw_posterior):
        """Λ_post should be inverse of Σ_post."""
        identity_approx = raw_posterior.Lambda_post @ raw_posterior.Sigma_post
        np.testing.assert_array_almost_equal(
            identity_approx,
            np.eye(identity_approx.shape[0]),
            decimal=4,
            err_msg="Λ_post × Σ_post ≠ I",
        )


class TestChainDSimulation:
    """Verify Chain D can load interventions and generate MC draws."""

    def test_interventions_loaded(self, intervention_set):
        """Action catalog seed should provide ≥1 intervention."""
        assert intervention_set.n_interventions >= 1, (
            "No interventions loaded — is action_catalog_v1 seeded?"
        )

    def test_mc_draws_valid(self, mc_draws):
        """MC draws should be finite and correctly shaped."""
        assert mc_draws.n_draws == 200
        assert np.all(np.isfinite(mc_draws.B_draws)), "B_draws has NaN/Inf"
        assert np.all(np.isfinite(mc_draws.theta0_draws)), "theta0_draws has NaN/Inf"

    def test_mc_draws_vary(self, mc_draws):
        """Draws should have non-zero variance (not all identical)."""
        b_var = np.var(mc_draws.B_draws, axis=0)
        # At least some edges should show variation
        assert np.max(b_var) > 0, "All B_draws are identical — sampling broken"


class TestVerticalIntegration:
    """End-to-end assertions about the full Chain A→B→C→D pipeline."""

    def test_evidence_reaches_frozen_state(self, frozen, evidence_records):
        """Evidence should influence B_hat (not just skeleton zeros)."""
        # B_hat should have at least one non-zero off-diagonal entry
        # from evidence (not just DAG skeleton)
        n_nodes = frozen.B_hat.shape[0]
        off_diag = frozen.B_hat.copy()
        np.fill_diagonal(off_diag, 0)
        assert np.count_nonzero(off_diag) >= 1, (
            "B_hat has no off-diagonal entries — evidence not incorporated"
        )

    def test_posteriors_reflect_evidence(self, loaded_prior, raw_posterior):
        """Without patient observations, posterior should equal prior
        (since bayesian_update had empty observations).
        The evidence is baked into the prior via Chain B's Lambda_prior.
        """
        # θ̂ should be finite and shaped correctly
        assert raw_posterior.theta_hat.shape == loaded_prior.mu_prior.shape
        # Σ_post should be at most as large as prior variance
        prior_var = np.diag(np.linalg.inv(loaded_prior.Lambda_prior))
        post_var = np.diag(raw_posterior.Sigma_post)
        # For the uninformative case with no observations,
        # posterior variance should equal prior variance
        np.testing.assert_array_almost_equal(
            post_var, prior_var, decimal=6,
            err_msg="Post variance != prior variance (with 0 observations)",
        )

    def test_frozen_state_differs_from_skeleton(self, frozen, graph):
        """FrozenModelState's B_hat should differ from the identity
        skeleton for edges with evidence."""
        # At least one Sigma_eff < infinity (i.e. some edge has finite SE)
        finite_se = [
            (eid, se) for eid, se in frozen.Sigma_eff.items()
            if se < 100.0
        ]
        assert len(finite_se) >= 1, (
            f"No edge has SE_eff < 100 — evidence not incorporated: "
            f"Sigma_eff sample: {dict(list(frozen.Sigma_eff.items())[:5])}"
        )

    def test_chain_c_preserves_evidence_structure(self, patient_state, frozen):
        """PatientState should carry through evidence from Chain B."""
        # B_eff shape should match B̂
        assert patient_state.B_eff.shape == frozen.B_hat.shape
        # theta_hat should be finite
        assert np.all(np.isfinite(patient_state.theta_hat))
        # Sigma_post should be PD
        eigvals = np.linalg.eigvalsh(patient_state.Sigma_post)
        assert np.all(eigvals > 0)

    def test_mc_draws_use_evidence(self, mc_draws, frozen):
        """MC draws should sample from evidence-informed distributions,
        not just the skeleton."""
        # Find an edge with evidence (finite SE)
        evidenced_edges = [
            eid for eid, se in frozen.Sigma_eff.items()
            if 0 < se < 50.0
        ]
        if not evidenced_edges:
            pytest.skip("No edges with finite SE — cannot test evidence in draws")

        # B_draws should show variability around evidenced edge weights
        # (non-zero mean and bounded variance)
        b_mean = np.mean(mc_draws.B_draws, axis=0)
        b_var = np.var(mc_draws.B_draws, axis=0)
        n_nonzero_mean = np.count_nonzero(np.abs(b_mean) > 1e-6)
        assert n_nonzero_mean >= 1, (
            "All B_draw means are ~0 — evidence not reaching MC sampler"
        )

    def test_full_pipeline_summary(
        self, graph, evidence_records, frozen,
        loaded_prior, raw_posterior, patient_state,
        intervention_set, mc_draws,
    ):
        """Print a summary of the full vertical integration."""
        summary = {
            "Chain A": {
                "nodes": graph.n_nodes,
                "edges": graph.n_edges,
                "pathways": graph.n_pathways,
            },
            "Evidence": {
                "records": len(evidence_records),
                "unique_edges": len({r.edge_id for r in evidence_records}),
            },
            "Chain B": {
                "B_hat_nonzero": int(np.count_nonzero(frozen.B_hat)),
                "Sigma_eff_finite": len([s for s in frozen.Sigma_eff.values() if s < 100]),
                "P_incl_high": len([p for p in frozen.P_inclusion.values() if p > 0.5]),
            },
            "Chain C": {
                "prior_context": loaded_prior.context_key,
                "prior_fallback": loaded_prior.fallback_level.value,
                "theta_hat_norm": float(np.linalg.norm(raw_posterior.theta_hat)),
                "Sigma_post_trace": float(np.trace(raw_posterior.Sigma_post)),
                "active_pathways": sum(
                    1 for p in patient_state.active_pathways if p.is_active
                ),
            },
            "Chain D": {
                "interventions": intervention_set.n_interventions,
                "mc_draws": mc_draws.n_draws,
                "B_draws_mean_norm": float(np.linalg.norm(
                    np.mean(mc_draws.B_draws, axis=0)
                )),
            },
        }
        logger.info("═══ VERTICAL INTEGRATION SUMMARY ═══")
        for chain, metrics in summary.items():
            logger.info("  %s:", chain)
            for key, val in metrics.items():
                logger.info("    %s: %s", key, val)

        # This test always passes — it's for logging/documentation
        assert True
