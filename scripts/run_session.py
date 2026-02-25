#!/usr/bin/env python3
"""
Run a CRCI patient session: runtime pipeline producing a RecommendationReport.

Usage:
    python scripts/run_session.py --patient-id PATIENT_001 [--mode clinical|research] [--verbose]

Requires: A FrozenModelState from run_build.py (or mock data for testing).
Runs: RT-G (schedule) → RT-H (questions, optional) → RT-I (report).
Outputs: RecommendationReport summary to stdout.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load .env if present
_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _setup_logging(verbose: bool) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_report(result) -> None:
    """Print session results summary."""
    report = result.report

    print("\n" + "=" * 70)
    print("SESSION RESULTS")
    print("=" * 70)
    print(f"  Run ID:          {result.run_id}")
    print(f"  Patient:         {report.subject_ref}")
    print(f"  Output mode:     {report.output_mode.value}")
    print(f"  Start:           {result.start_time}")
    print(f"  End:             {result.end_time}")

    # Composite score
    cs = report.composite_score
    print(f"\n  Composite Score:")
    print(f"    z-score:       {cs.composite_z:.3f}")
    print(f"    Severity:      {cs.overall_severity.value}")
    if cs.domain_scores:
        print(f"    Domain scores:")
        for ds in cs.domain_scores:
            print(f"      {ds.domain_label:30s} z = {ds.z_score:.3f}")

    # Primary schedule
    ps = report.primary_schedule
    print(f"\n  Primary Schedule:")
    print(f"    ID:            {ps.schedule_id}")
    print(f"    Rank:          {ps.plan_rank}")
    print(f"    Type:          {ps.plan_type}")
    if ps.actions:
        print(f"    Actions ({len(ps.actions)}):")
        for a in ps.actions:
            print(f"      - {a.action_label} ({a.action_class})")

    # Alternative schedules
    if report.alternative_schedules:
        print(f"\n  Alternatives:    {len(report.alternative_schedules)}")
        for alt in report.alternative_schedules:
            print(f"    - {alt.schedule_id} (rank {alt.plan_rank})")

    # Safety flags
    if report.safety_flags:
        print(f"\n  Safety flags:    {', '.join(report.safety_flags)}")

    # Trajectories
    if report.trajectories:
        print(f"\n  Trajectories:    {len(report.trajectories)}")
        for t in report.trajectories:
            print(f"    - {t.scenario_label}: {t.horizon_days}d horizon")

    # Variance decomposition
    if report.variance_decomposition:
        vd = report.variance_decomposition
        print(f"\n  Variance decomposition:")
        print(f"    Stability:     {vd.stability_class}")
        if vd.components:
            for comp in vd.components:
                print(f"    - {comp.source:15s} {comp.fraction:.1%}")

    print("=" * 70)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CRCI patient session → RecommendationReport",
    )
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Patient identifier (subject_ref)",
    )
    parser.add_argument(
        "--mode",
        choices=["clinical", "research"],
        default="clinical",
        help="Output mode (default: clinical)",
    )
    parser.add_argument(
        "--ranking-json",
        type=Path,
        default=None,
        help="Path to RankingResult JSON (from ALG-D). "
             "If absent, creates minimal mock data for testing.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Limit number of schedules to top K",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    from crci.shared.models.enums import ReportOutputMode
    from crci.runtime.session import SessionConfig, run_session

    output_mode = (
        ReportOutputMode.CLINICAL if args.mode == "clinical"
        else ReportOutputMode.RESEARCH
    )

    session_config = SessionConfig(
        subject_ref=args.patient_id,
        output_mode=output_mode,
        top_k=args.top_k,
    )

    # Load or create RankingResult
    if args.ranking_json is not None:
        if not args.ranking_json.exists():
            print(f"Error: Ranking JSON not found: {args.ranking_json}", file=sys.stderr)
            return 1
        print(f"Loading ranking result from {args.ranking_json}...")
        raise NotImplementedError(
            "JSON deserialization of RankingResult requires Phase 7 serialization support. "
            "Use the Python API directly for now."
        )
    else:
        # Create minimal mock RankingResult for testing
        print("No --ranking-json provided. Creating minimal mock data for demo...")
        import numpy as np
        from crci.algorithm.chain_d_simulation.ranker import (
            ClaimLevel,
            InterventionRanking,
            BundleRanking,
            RankingResult,
        )
        from crci.algorithm.chain_d_simulation.safety_checker import SafetyStatus

        n_draws = 100
        mock_draws_1 = np.random.default_rng(42).normal(0.35, 0.12, n_draws)
        mock_draws_2 = np.random.default_rng(43).normal(0.25, 0.15, n_draws)

        mock_ranking = RankingResult(
            intervention_rankings={
                "ACT_exercise_aerobic": InterventionRanking(
                    action_id="ACT_exercise_aerobic",
                    action_label="Aerobic Exercise",
                    safety_status=SafetyStatus.CLEAR,
                    mss_cog=0.35,
                    mss_burden=0.2,
                    safe_a=0.29,
                    safe_a_cri_lower=0.15,
                    safe_a_cri_upper=0.45,
                    rank_a=1,
                    p_adhere=0.75,
                    safe_b=0.15,
                    safe_b_cri_lower=0.02,
                    safe_b_cri_upper=0.30,
                    rank_b=1,
                    adherence_warning=False,
                    dose_recommended=150.0,
                    dose_conflict=False,
                    dose_conflict_ratio=None,
                    claim_level=ClaimLevel.CAUSAL_SUPPORTED,
                    per_draw_safe_a=mock_draws_1,
                ),
                "ACT_cognitive_training": InterventionRanking(
                    action_id="ACT_cognitive_training",
                    action_label="Cognitive Training",
                    safety_status=SafetyStatus.CLEAR,
                    mss_cog=0.25,
                    mss_burden=0.15,
                    safe_a=0.205,
                    safe_a_cri_lower=0.08,
                    safe_a_cri_upper=0.35,
                    rank_a=2,
                    p_adhere=0.70,
                    safe_b=0.03,
                    safe_b_cri_lower=-0.10,
                    safe_b_cri_upper=0.18,
                    rank_b=2,
                    adherence_warning=False,
                    dose_recommended=None,
                    dose_conflict=False,
                    dose_conflict_ratio=None,
                    claim_level=ClaimLevel.ASSOCIATIONAL_ONLY,
                    per_draw_safe_a=mock_draws_2,
                ),
            },
            bundle_rankings={
                "BUNDLE_exercise_cognitive": BundleRanking(
                    bundle_id="BUNDLE_exercise_cognitive",
                    member_ids=("ACT_exercise_aerobic", "ACT_cognitive_training"),
                    safe_a=0.42,
                    safe_a_cri_lower=0.25,
                    safe_a_cri_upper=0.60,
                    rank_a=1,
                    p_adhere=0.60,
                    safe_b=0.17,
                    safe_b_cri_lower=0.01,
                    safe_b_cri_upper=0.35,
                    rank_b=1,
                    adherence_warning=False,
                    claim_level=ClaimLevel.ASSOCIATIONAL_ONLY,
                    per_draw_safe_a=mock_draws_1 + mock_draws_2,
                ),
            },
            sensitivity_indices=[],
            top_discovery_edges=[],
            dose_recommendations={},
            n_interventions_ranked=2,
            n_bundles_ranked=1,
            n_blocked=0,
            gate_d_g4_passed=True,
            gate_d_g5_passed=True,
            gate_d_g6_passed=True,
        )

    # Run session
    print(f"\n>>> Running session for patient {args.patient_id}...")
    t0 = time.monotonic()

    try:
        result = run_session(
            session_config=session_config,
            ranking_result=mock_ranking,
        )
        dt = time.monotonic() - t0
        _print_report(result)
        print(f"\n  (completed in {dt:.2f}s)")

    except Exception as exc:
        logger.exception("Session failed: %s", exc)
        return 1

    print("\nSession complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
