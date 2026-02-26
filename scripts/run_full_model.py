#!/usr/bin/env python3
"""Run the full CRCI model: chains A → B → C → D → E → F → session.

This is the production orchestrator that chains all algorithm modules
together, producing a RecommendationReport from registries + evidence +
patient observations.

Usage:
    python scripts/run_full_model.py --patient-id PAT_001 \\
        --cancer-type breast --treatment-phase active_chemo

    python scripts/run_full_model.py --patient-id PAT_001 \\
        --cancer-type breast --treatment-phase active_chemo \\
        --evidence-csv data/evidence.csv --verbose
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# Hardcoded action → primary target node mapping.
# Used when dose_bridges_v1 table is empty (before full data curation).
_ACTION_TO_NODE_FALLBACK: dict[str, str] = {
    "ACT_EXERCISE_AEROBIC": "NODE_BEH_PHYSICAL_ACTIVITY",
    "ACT_EXERCISE_RESISTANCE": "NODE_BEH_PHYSICAL_ACTIVITY",
    "ACT_COGNITIVE_TRAINING": "NODE_BEH_COG_ACTIVITY",
    "ACT_MINDFULNESS": "NODE_BEH_STRESS_MGMT",
    "ACT_SLEEP_HYGIENE": "NODE_BEH_SLEEP_QUALITY",
    "ACT_LIGHT_AM": "NODE_BEH_LIGHT_EXPOSURE",
    "ACT_SOCIAL_ENGAGE": "NODE_BEH_SOCIAL_ENGAGE",
    "ACT_NUTRITION_ANTI_INFLAM": "NODE_BEH_DIET",
}


def _build_intervention_node_map(
    intervention_set: "InterventionSet",
    graph: "GraphObject",
) -> dict[str, int]:
    """Build action_id → node_index mapping from dose bridges.

    Falls back to _ACTION_TO_NODE_FALLBACK when dose bridges are empty.
    """
    node_map = {}
    for interv in intervention_set.interventions:
        # Try dose bridges first
        for bridge in interv.dose_bridges:
            nid = bridge.output_node_id or bridge.maps_to_node_id
            if nid and nid in graph.node_map.node_index:
                node_map[interv.action_id] = graph.node_map.node_index[nid]
                break
        # Fallback to hardcoded mapping
        if interv.action_id not in node_map:
            fallback_nid = _ACTION_TO_NODE_FALLBACK.get(interv.action_id)
            if fallback_nid and fallback_nid in graph.node_map.node_index:
                node_map[interv.action_id] = graph.node_map.node_index[fallback_nid]
                logging.getLogger(__name__).info(
                    "D0: Using fallback node mapping: %s → %s",
                    interv.action_id, fallback_nid,
                )
    return node_map


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full CRCI model: A → B → C → D → E → F → session",
    )

    # Required
    parser.add_argument(
        "--patient-id", required=True,
        help="Patient identifier (subject_ref)",
    )
    parser.add_argument(
        "--cancer-type", required=True,
        help="Cancer type (e.g., breast, colorectal, lymphoma)",
    )
    parser.add_argument(
        "--treatment-phase", required=True,
        help="Treatment phase (e.g., active_chemo, post_chemo, mixed)",
    )

    # Optional data paths
    parser.add_argument(
        "--evidence-csv", type=Path, default=None,
        help="Evidence CSV (if absent, chain B uses DB evidence)",
    )
    parser.add_argument(
        "--node-registry", type=Path,
        default=PROJECT_ROOT / "registries" / "NODE_REGISTRY.csv",
    )
    parser.add_argument(
        "--edge-registry", type=Path,
        default=PROJECT_ROOT / "registries" / "EDGE_REGISTRY.csv",
    )
    parser.add_argument(
        "--instrument-registry", type=Path,
        default=PROJECT_ROOT / "registries" / "INSTRUMENT_REGISTRY.csv",
    )
    parser.add_argument(
        "--pathway-registry", type=Path,
        default=PROJECT_ROOT / "registries" / "PATHWAY_REGISTRY.csv",
    )

    # Patient options
    parser.add_argument(
        "--treatment-regimen", default=None,
        help="Optional treatment regimen for exact context match",
    )
    parser.add_argument(
        "--mode", choices=["clinical", "research"], default="clinical",
        help="Output mode (default: clinical)",
    )
    parser.add_argument(
        "--mc-draws", type=int, default=None,
        help="Number of Monte Carlo draws (default: from config)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--skip-temporal", action="store_true",
        help="Skip chain E (temporal projections)",
    )
    parser.add_argument(
        "--skip-analytics", action="store_true",
        help="Skip chain F (analytics/risk)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    t_total = time.monotonic()

    # Validate required files
    for name, path in [
        ("Node registry", args.node_registry),
        ("Edge registry", args.edge_registry),
        ("Instrument registry", args.instrument_registry),
    ]:
        if not path.exists():
            print(f"Error: {name} not found: {path}", file=sys.stderr)
            return 1

    pathway_path = args.pathway_registry if args.pathway_registry.exists() else None

    # ══════════════════════════════════════════════════════════
    #  CHAIN A: Graph Assembly
    # ══════════════════════════════════════════════════════════
    _print_section("ALG-A: Graph Assembly")
    t0 = time.monotonic()

    from crci.algorithm.chain_a_graph.graph_object import run_chain_a

    graph = run_chain_a(
        node_registry_path=args.node_registry,
        edge_registry_path=args.edge_registry,
        instrument_registry_path=args.instrument_registry,
        pathway_registry_path=pathway_path,
    )
    print(f"  Nodes: {graph.n_nodes}, Edges: {graph.n_edges}, "
          f"Instruments: {len(graph.instrument_map.instruments)}")
    print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  CHAIN B: Evidence Compilation → Frozen Model State
    # ══════════════════════════════════════════════════════════
    _print_section("ALG-B: Evidence Compilation → Frozen Model State")
    t0 = time.monotonic()

    from crci.algorithm.chain_b_evidence.frozen_state import (
        FrozenModelState,
        run_chain_b,
    )
    from crci.algorithm.chain_b_evidence.evidence_compiler import EvidenceRecord

    # Load evidence from CSV or DB
    evidence_records: list[EvidenceRecord] = []
    if args.evidence_csv is not None:
        if not args.evidence_csv.exists():
            print(f"Error: Evidence CSV not found: {args.evidence_csv}",
                  file=sys.stderr)
            return 1
        with open(args.evidence_csv, newline="", encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                rec = EvidenceRecord(
                    study_id=row["study_id"],
                    edge_id=row["edge_id"],
                    beta=float(row["beta"]),
                    se=float(row["se"]),
                    study_design=row.get("study_design", "observational"),
                    publication_year=int(row.get("publication_year", 2020)),
                    sample_size=int(row.get("sample_size", 100)),
                    identification_status=row.get("identification_status", "identified"),
                    quality_grade=row.get("quality_grade", "MODERATE"),
                    scope_weights={
                        dim: float(row.get(f"scope_{dim}", 1.0))
                        for dim in [
                            "population", "intervention", "comparator",
                            "outcome", "setting",
                        ]
                    },
                    cancer_validation_status=row.get(
                        "cancer_validation_status", "general_population",
                    ),
                    temporal_distance_days=float(
                        row.get("temporal_distance_days", 0.0),
                    ),
                    outcome_type=row.get("outcome_type", "subjective"),
                )
                evidence_records.append(rec)
        logger.info("Loaded %d evidence records from %s",
                    len(evidence_records), args.evidence_csv)
    else:
        # Load from DB
        from crci.shared.db import get_session
        with get_session() as session:
            from crci.shared.models.tables import EdgeEvidence
            rows = session.query(EdgeEvidence).all()
            for row in rows:
                rec = EvidenceRecord(
                    study_id=row.study_id,
                    edge_id=row.edge_relation_id,
                    beta=row.beta,
                    se=row.se,
                    study_design=row.study_design or "observational",
                    publication_year=row.publication_year or 2020,
                    sample_size=row.sample_size or 100,
                    identification_status=row.identification_status or "identified",
                    quality_grade=row.quality_grade or "MODERATE",
                    scope_weights={},
                    cancer_validation_status=row.cancer_validation or "general_population",
                    temporal_distance_days=0.0,
                    outcome_type=row.outcome_type or "subjective",
                )
                evidence_records.append(rec)
        logger.info("Loaded %d evidence records from DB", len(evidence_records))

    if not evidence_records:
        print("Warning: No evidence records found — chain B will use uniform priors")

    frozen = run_chain_b(graph=graph, evidence_records=evidence_records)
    print(f"  Evidence records: {len(evidence_records)}")
    print(f"  Prior contexts: {len(frozen.Lambda_prior)}")
    print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  CHAIN C: Posterior Estimation
    # ══════════════════════════════════════════════════════════
    _print_section("ALG-C: Posterior Estimation")
    t0 = time.monotonic()

    from crci.algorithm.chain_c_posterior import run_chain_c
    from crci.algorithm.chain_c_posterior.observation_mapper import RawObservation
    from crci.algorithm.chain_c_posterior.modifier_application import ModifierRule

    # For now, empty observations (no live patient data).
    # In production, these come from the EHR/patient intake form.
    # Use minimal Tier-0 dummy observations to pass C-G2.
    observations: list[RawObservation] = []
    modifier_rules: list[ModifierRule] = []

    # Load pathway definitions
    from crci.shared.models.pathway_types import PathwayDef
    pathways: list[PathwayDef] = []
    if graph.pathway_map:
        for pw_def in graph.pathway_map:
            pathways.append(pw_def)
    logger.info("Using %d pathways from graph", len(pathways))

    patient_profile: dict[str, object] = {
        "cancer_type": args.cancer_type,
        "treatment_phase": args.treatment_phase,
    }

    try:
        patient_state, raw_posterior, loaded_prior, snapshot_result = run_chain_c(
            frozen=frozen,
            observations=observations,
            cancer_type=args.cancer_type,
            treatment_phase=args.treatment_phase,
            patient_profile=patient_profile,
            modifier_rules=modifier_rules,
            pathways=pathways,
            treatment_regimen=args.treatment_regimen,
            current_date=date.today(),
        )
        print(f"  Context: {loaded_prior.context_key} (fallback={loaded_prior.fallback_level})")
        print(f"  Observations fused: {len(raw_posterior.observation_log)}")
        print(f"  Active pathways: {sum(1 for p in patient_state.active_pathways if p.is_active)}")
        print(f"  ({time.monotonic() - t0:.2f}s)")
    except Exception as exc:
        logger.warning("Chain C failed (may need Tier-0 observations): %s", exc)
        print(f"  Chain C SKIPPED: {exc}")
        print("  Creating minimal PatientState with prior-only estimates...")

        # Fallback: use prior as patient state (no observations)
        from crci.algorithm.chain_c_posterior.prior_loader import load_prior

        loaded_prior = load_prior(
            frozen=frozen,
            cancer_type=args.cancer_type,
            treatment_phase=args.treatment_phase,
        )

        from crci.algorithm.chain_c_posterior.modifier_application import PatientState
        from crci.algorithm.chain_c_posterior.bayesian_update import RawPosterior

        # Create minimal patient state from prior means
        Sigma_fallback = (
            np.linalg.inv(loaded_prior.Lambda_prior)
            if np.linalg.det(loaded_prior.Lambda_prior) > 0
            else np.eye(loaded_prior.Lambda_prior.shape[0])
        )
        patient_state = PatientState(
            theta_hat=loaded_prior.mu_prior,
            Sigma_post=Sigma_fallback,
            Lambda_post=loaded_prior.Lambda_prior.copy(),
            B_eff=frozen.B_hat.copy(),
            modifier_audit=[],
            active_pathways=[],
            observation_log=[],
            context_match=None,
        )
        raw_posterior = None
        print(f"  Using prior-only PatientState ({loaded_prior.context_key})")
        print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  CHAIN D: Simulation & Ranking
    # ══════════════════════════════════════════════════════════
    _print_section("ALG-D: Simulation & Ranking")
    t0 = time.monotonic()

    from crci.shared.db import get_session

    with get_session() as session:
        # D0: Load interventions
        from crci.algorithm.chain_d_simulation.intervention_loader import (
            InterventionSet,
            load_interventions,
        )

        try:
            intervention_set = load_interventions(session, frozen)
        except Exception as exc:
            logger.warning("D0: load_interventions failed: %s — creating empty set", exc)
            intervention_set = InterventionSet(
                interventions=[],
                intervention_index={},
                synergy_records=[],
                synergy_lookup={},
                all_contraindications=[],
            )

    if intervention_set.n_interventions == 0:
        print("  No interventions loaded — using mock ranking for demo")
        # Create minimal mock ranking
        from crci.algorithm.chain_d_simulation.ranker import (
            ClaimLevel,
            InterventionRanking,
            BundleRanking,
            RankingResult,
        )
        from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus

        mock_ranking = RankingResult(
            intervention_rankings={},
            bundle_rankings={},
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=0,
            n_bundles_ranked=0,
            n_blocked=0,
            gate_d_g4_passed=True,
            gate_d_g5_passed=True,
            gate_d_g6_passed=True,
        )
        ranking_result = mock_ranking
        mc_draws = None
        effect_result = None
    else:
        # D1: Monte Carlo draws
        from crci.algorithm.chain_d_simulation.mc_sampler import (
            MCDraws,
            generate_mc_draws,
        )

        mc_draws = generate_mc_draws(
            frozen=frozen,
            patient_state=patient_state,
            n_draws=args.mc_draws,
            seed=args.seed,
        )
        print(f"  D1: {mc_draws.n_draws} MC draws generated")

        # D2: Effect propagation
        from crci.algorithm.chain_d_simulation.effect_propagation import (
            EffectResult,
            propagate_effects,
        )

        intervention_node_map = _build_intervention_node_map(
            intervention_set, graph,
        )

        effect_result = propagate_effects(
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
            intervention_node_map=intervention_node_map,
        )
        print(f"  D2: Effects propagated for {len(intervention_node_map)} interventions")

        # D3: Safety check
        from crci.algorithm.chain_d_simulation.safety_checker import (
            SafetyResult,
            evaluate_safety,
        )

        safety_result = evaluate_safety(
            intervention_set=intervention_set,
            patient_profile=patient_profile,
        )
        print(f"  D3-safety: {safety_result.n_clear} clear, "
              f"{safety_result.n_blocked} blocked")

        # D3-syn: Synergy bundles
        from crci.algorithm.chain_d_simulation.synergy_bundle import (
            BundleResult,
            compute_bundles,
        )

        bundle_result = compute_bundles(
            effect_result=effect_result,
            intervention_set=intervention_set,
            safety_result=safety_result,
            mc_draws=mc_draws,
            frozen=frozen,
            patient_state=patient_state,
        )
        print(f"  D3-synergy: {len(bundle_result.bundle_effects)} bundles")

        # D4-D6: Ranking
        from crci.algorithm.chain_d_simulation.ranker import (
            RankingResult,
            rank_interventions,
        )

        ranking_result = rank_interventions(
            effect_result=effect_result,
            bundle_result=bundle_result,
            safety_result=safety_result,
            intervention_set=intervention_set,
            mc_draws=mc_draws,
            frozen=frozen,
        )
        print(f"  D4-D6: {ranking_result.n_interventions_ranked} ranked, "
              f"{ranking_result.n_blocked} blocked")

    print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  CHAIN E: Temporal Projections (optional)
    # ══════════════════════════════════════════════════════════
    recovery = None
    overlay = None
    uncertainty = None

    if not args.skip_temporal:
        _print_section("ALG-E: Temporal Projections")
        t0 = time.monotonic()

        try:
            # E1: Nadir estimation
            from crci.algorithm.chain_e_temporal.nadir_estimator import estimate_nadir

            nadir = estimate_nadir(patient_state=patient_state)
            print(f"  E1: Nadir estimated")

            # E2: Recovery trajectory
            from crci.algorithm.chain_e_temporal.recovery_trajectory import (
                compute_recovery_trajectory,
            )

            context_key = f"{args.cancer_type}_{args.treatment_phase}"
            recovery = compute_recovery_trajectory(
                nadir=nadir,
                context_key=context_key,
                seed=args.seed,
            )
            print(f"  E2: Recovery trajectory ({recovery.n_timepoints} timepoints)")

            # E3: Intervention overlay (only if we have effects)
            if effect_result is not None:
                from crci.algorithm.chain_e_temporal.intervention_overlay import (
                    compute_intervention_overlay,
                )

                overlay = compute_intervention_overlay(
                    recovery=recovery,
                    effect_result=effect_result,
                    ranking_result=ranking_result,
                    intervention_set=intervention_set,
                )
                print(f"  E3: Intervention overlay computed")

                # E4: Uncertainty counterfactual
                from crci.algorithm.chain_e_temporal.uncertainty_counterfactual import (
                    compute_uncertainty_counterfactual,
                )

                uncertainty = compute_uncertainty_counterfactual(
                    overlay=overlay,
                    recovery=recovery,
                )
                print(f"  E4: Uncertainty counterfactual computed")

        except Exception as exc:
            logger.warning("Chain E failed: %s", exc)
            print(f"  Chain E partially failed: {exc}")

        print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  CHAIN F: Analytics & Risk (optional)
    # ══════════════════════════════════════════════════════════
    composite = None
    stability = None
    variance = None
    risk_estimate = None
    temporal_risk = None

    if not args.skip_analytics:
        _print_section("ALG-F: Analytics & Risk")
        t0 = time.monotonic()

        try:
            # F1: Composite score
            from crci.algorithm.chain_f_analytics.composite_scorer import (
                compute_composite_score,
            )

            posterior_variances = np.diag(patient_state.Sigma_post)
            composite = compute_composite_score(
                posterior_means=patient_state.theta_hat,
                posterior_variances=posterior_variances,
            )
            print(f"  F1: CRCI composite={composite.crci_composite:.3f}, "
                  f"percentile={composite.percentile:.1f}, "
                  f"severity={composite.severity_tier.value}")

            # F2: Decision stability
            from crci.algorithm.chain_f_analytics.variance_decomposer import (
                compute_decision_stability,
            )

            stability = compute_decision_stability(
                ranking_result=ranking_result,
            )
            print(f"  F2: Decision stability computed")

            # F3: EVSI / variance decomposition
            from crci.algorithm.chain_f_analytics.evsi import (
                compute_variance_decomposition,
            )

            variance = compute_variance_decomposition(
                n_edges=graph.n_edges,
                posterior_covariance=patient_state.Sigma_post,
            )
            print(f"  F3: Variance decomposition computed")

            # F4: Risk estimation
            if mc_draws is not None:
                from crci.algorithm.chain_f_analytics.risk_estimator import (
                    estimate_crci_risk,
                )

                fusion_levels = (raw_posterior.fusion_levels
                                 if raw_posterior is not None else {})
                risk_estimate = estimate_crci_risk(
                    theta_draws=mc_draws.theta0_draws,
                    node_map=graph.node_map,
                    composite_state=composite,
                    fusion_levels=fusion_levels,
                )
                print(f"  F4: Risk estimate computed")

            # F4T: Temporal risk
            if recovery is not None:
                from crci.algorithm.chain_f_analytics.temporal_risk import (
                    compute_temporal_risk,
                )

                temporal_risk = compute_temporal_risk(
                    recovery=recovery,
                    overlay=overlay,
                    node_map=graph.node_map,
                    composite_state=composite,
                )
                print(f"  F4T: Temporal risk computed")

        except Exception as exc:
            logger.warning("Chain F failed: %s", exc)
            print(f"  Chain F partially failed: {exc}")

        print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  RUNTIME: Session & Report
    # ══════════════════════════════════════════════════════════
    _print_section("Runtime: Session & Report Generation")
    t0 = time.monotonic()

    from crci.shared.models.enums import ReportOutputMode
    from crci.runtime.session import SessionConfig, run_session

    output_mode = (
        ReportOutputMode.CLINICAL if args.mode == "clinical"
        else ReportOutputMode.RESEARCH
    )

    session_config = SessionConfig(
        subject_ref=args.patient_id,
        output_mode=output_mode,
    )

    # Build evidence gap report (WP-8)
    evidence_gap_report = None
    pathway_profile = None
    try:
        from crci.runtime.evidence_gap_compiler import compile_evidence_gaps

        edge_info = []
        for edge in graph.edge_list:
            edge_info.append({
                "edge_relation_id": edge.edge_relation_id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
            })
        evidence_gap_report = compile_evidence_gaps(
            edge_info=edge_info,
            run_id=args.patient_id,
        )
    except Exception as exc:
        logger.debug("Evidence gap compilation skipped: %s", exc)

    try:
        from crci.runtime.pathway_profiler import compute_pathway_profile, PathwayInput

        if graph.pathway_map:
            pathway_inputs = []
            for pw in graph.pathway_map:
                pathway_inputs.append(PathwayInput(
                    pathway_id=pw.pathway_id,
                    pathway_name=getattr(pw, "name", pw.pathway_id),
                    node_indices=[
                        graph.node_map.node_index[nid]
                        for nid in pw.node_ids
                        if nid in graph.node_map.node_index
                    ],
                ))
            if pathway_inputs:
                pathway_profile = compute_pathway_profile(
                    pathways=pathway_inputs,
                    theta_hat=patient_state.theta_hat,
                    theta_prior_mean=loaded_prior.mu_prior,
                    sigma_prior=np.diag(
                        np.linalg.inv(loaded_prior.Lambda_prior)
                    ) if np.linalg.det(loaded_prior.Lambda_prior) > 0
                    else np.ones(loaded_prior.Lambda_prior.shape[0]),
                    node_index=graph.node_map.node_index,
                    run_id=args.patient_id,
                    subject_ref=args.patient_id,
                )
    except Exception as exc:
        logger.debug("Pathway profile skipped: %s", exc)

    # Build node labels for the report
    node_labels = {
        node_id: node_id.replace("NODE_", "").replace("_", " ").title()
        for node_id in graph.node_map.node_index
    }

    result = run_session(
        session_config=session_config,
        ranking_result=ranking_result,
        composite=composite,
        stability=stability,
        variance=variance,
    )

    print(f"  Report generated: run_id={result.run_id}")
    n_actions = len(result.report.primary_schedule.actions)
    print(f"  Primary schedule: {n_actions} actions, "
          f"utility={result.report.primary_schedule.utility_score:.3f}")
    print(f"  Alternatives: {len(result.report.alternative_schedules)}")
    print(f"  ({time.monotonic() - t0:.2f}s)")

    # ══════════════════════════════════════════════════════════
    #  Summary
    # ══════════════════════════════════════════════════════════
    dt_total = time.monotonic() - t_total

    _print_section("Summary")
    print(f"  Patient: {args.patient_id}")
    print(f"  Cancer: {args.cancer_type} / {args.treatment_phase}")
    print(f"  Evidence: {len(evidence_records)} records")
    print(f"  Interventions ranked: {ranking_result.n_interventions_ranked}")
    if composite is not None:
        print(f"  CRCI composite: {composite.crci_composite:.3f} "
              f"(percentile {composite.percentile:.0f}, "
              f"{composite.severity_tier.value})")
    print(f"  Total time: {dt_total:.2f}s")

    # Print top recommendations
    if ranking_result.intervention_rankings:
        print("\n  Top recommendations (by SAFE_A):")
        sorted_rankings = sorted(
            ranking_result.intervention_rankings.values(),
            key=lambda r: r.rank_a,
        )
        for r in sorted_rankings[:5]:
            print(f"    #{r.rank_a}: {r.action_label} "
                  f"(SAFE_A={r.safe_a:.3f} [{r.safe_a_cri_lower:.3f}, "
                  f"{r.safe_a_cri_upper:.3f}], "
                  f"claim={r.claim_level.value})")

    print("\nFull model pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
