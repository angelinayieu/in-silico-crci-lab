#!/usr/bin/env python3
"""
CRCI System Status Report.

Shows database population state, evidence coverage, acquisition progress,
and workstream-level fill rates.

Usage:
    python scripts/report_status.py              # Full report
    python scripts/report_status.py --json       # Machine-readable JSON output
    python scripts/report_status.py --workstream # Workstream detail only
    python scripts/report_status.py --gaps       # Show gaps and next actions

Sections:
    1. Class A Knowledge Base — seed data completeness
    2. Class B Evidence — papers processed, evidence rows
    3. Workstream Fill Rates — per-workstream parameter coverage
    4. Extraction Activity — recent runs, success/failure counts
    5. Acquisition Queue — pending, dispatched, completed
    6. Gap Analysis — what's missing, what to search next
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from sqlalchemy import text

from crci.shared.db import get_session, init_db

logger = logging.getLogger(__name__)


def _count(session, table_name: str) -> int:
    """Count rows in a table, return 0 if table doesn't exist."""
    try:
        result = session.execute(text(f"SELECT count(*) FROM {table_name}"))
        return result.scalar() or 0
    except Exception:
        return -1


def _section_header(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def report_class_a(session) -> dict:
    """Section 1: Class A Knowledge Base completeness."""
    _section_header("CLASS A — KNOWLEDGE BASE")

    tables = [
        ("biomarker_node_definitions_v1", "Biomarker Nodes", "63 target"),
        ("edge_relations_definitions_v1", "Edge Relations", "~129 target"),
        ("instrument_definitions_v1", "Instruments", "~23 target"),
        ("measure_definitions_v1", "Measures", "~15 target"),
        ("pathways_v1", "Pathways", "~8 target"),
        ("node_search_terms_v1", "Search Terms", "~200 target"),
        ("observation_noise_v1", "Observation Noise", "1 per instrument/measure"),
        ("feedback_loops_v1", "Feedback Loops", "~5 target"),
        ("action_catalog_v1", "Actions (interventions)", "~10 target"),
        ("normalization_refs_v1", "Normalization Refs", "1 per instrument"),
        ("harmonization_rules_v1", "Harmonization Rules", "design-dependent"),
        ("recovery_trajectories_v1", "Recovery Trajectories", "~10 target"),
        ("intervention_kernels_v1", "Intervention Kernels", "1 per action"),
        ("biomarker_correlations_v1", "Biomarker Correlations", "~30 target"),
        ("literary_mechanistic_priors_v1", "Literary Priors", "1 per edge"),
    ]

    counts = {}
    for table_name, label, target in tables:
        count = _count(session, table_name)
        counts[table_name] = count
        status = f"{count:>5d}" if count > 0 else "    0  <-- NEEDS DATA"
        print(f"  {label:35s} {status:>20s}   ({target})")

    return counts


def report_class_b(session) -> dict:
    """Section 2: Class B Evidence — populated by extraction."""
    _section_header("CLASS B — EVIDENCE (from extraction)")

    tables = [
        ("study_registry_v1", "Studies Registered"),
        ("edge_evidence_v1", "Edge Evidence Rows"),
        ("instrument_evidence_v1", "Instrument Evidence Rows"),
        ("population_norms_v1", "Population Norms"),
        ("temporal_evidence_v1", "Temporal Evidence"),
        ("dose_evidence_v1", "Dose Evidence"),
        ("subgroup_evidence_v1", "Subgroup Evidence"),
        ("extraction_runs", "Extraction Runs"),
    ]

    counts = {}
    for table_name, label in tables:
        count = _count(session, table_name)
        counts[table_name] = count
        print(f"  {label:35s} {count:>5d}")

    # Extraction run status breakdown
    try:
        result = session.execute(text(
            "SELECT status, count(*) FROM extraction_runs "
            "GROUP BY status ORDER BY count(*) DESC"
        ))
        statuses = {row[0]: row[1] for row in result}
        if statuses:
            print(f"\n  Extraction run breakdown:")
            for status, cnt in statuses.items():
                print(f"    {status:20s} {cnt:>5d}")
    except Exception:
        pass

    return counts


def report_workstreams(session) -> dict:
    """Section 3: Per-workstream parameter fill rates."""
    _section_header("WORKSTREAM FILL RATES")

    report = {}

    # Workstream 1: Edge Evidence
    # How many of the defined edges have at least 1 evidence row?
    total_edges = _count(session, "edge_relations_definitions_v1")
    try:
        result = session.execute(text(
            "SELECT count(DISTINCT edge_relation_id) FROM edge_evidence_v1"
        ))
        edges_with_evidence = result.scalar() or 0
    except Exception:
        edges_with_evidence = 0

    # Edges with k >= 2 (minimum for meta-analysis)
    try:
        result = session.execute(text(
            "SELECT count(*) FROM ("
            "  SELECT edge_relation_id, count(*) as k "
            "  FROM edge_evidence_v1 GROUP BY edge_relation_id HAVING count(*) >= 2"
            ") sub"
        ))
        edges_k2_plus = result.scalar() or 0
    except Exception:
        edges_k2_plus = 0

    pct_e = (edges_with_evidence / total_edges * 100) if total_edges > 0 else 0
    print(f"  WS1 Edge Evidence:")
    print(f"    Edges defined:          {total_edges:>5d}")
    print(f"    Edges with k>=1:        {edges_with_evidence:>5d}  ({pct_e:.0f}%)")
    print(f"    Edges with k>=2 (MA):   {edges_k2_plus:>5d}")
    report["edge_evidence"] = {
        "total": total_edges,
        "k1_plus": edges_with_evidence,
        "k2_plus": edges_k2_plus,
    }

    # Workstream 2: Instrument Psychometrics
    total_instruments = _count(session, "instrument_definitions_v1")
    try:
        result = session.execute(text(
            "SELECT count(DISTINCT instrument_id) FROM instrument_evidence_v1"
        ))
        instruments_with_evidence = result.scalar() or 0
    except Exception:
        instruments_with_evidence = 0

    # Instruments with observation_noise entry (i.e., we have alpha)
    try:
        result = session.execute(text(
            "SELECT count(*) FROM observation_noise_v1 "
            "WHERE target_entity_type = 'instrument' AND reliability_alpha IS NOT NULL"
        ))
        instruments_with_alpha = result.scalar() or 0
    except Exception:
        instruments_with_alpha = 0

    pct_i = (instruments_with_evidence / total_instruments * 100) if total_instruments > 0 else 0
    pct_a = (instruments_with_alpha / total_instruments * 100) if total_instruments > 0 else 0
    print(f"\n  WS2 Instrument Psychometrics:")
    print(f"    Instruments defined:    {total_instruments:>5d}")
    print(f"    With evidence rows:     {instruments_with_evidence:>5d}  ({pct_i:.0f}%)")
    print(f"    With alpha (noise):     {instruments_with_alpha:>5d}  ({pct_a:.0f}%)")
    report["instrument_psychometrics"] = {
        "total": total_instruments,
        "with_evidence": instruments_with_evidence,
        "with_alpha": instruments_with_alpha,
    }

    # Workstream 3: Population Norms
    norms_count = _count(session, "population_norms_v1")
    print(f"\n  WS3 Population Norms:")
    print(f"    Norm entries:           {norms_count:>5d}")
    report["population_norms"] = {"total": norms_count}

    # Workstream 4: Context Priors
    priors_count = _count(session, "literary_mechanistic_priors_v1")
    print(f"\n  WS4 Context Priors:")
    print(f"    Literary priors:        {priors_count:>5d}")
    report["context_priors"] = {"total": priors_count}

    # Workstream 5: Recovery Parameters
    recovery_count = _count(session, "recovery_trajectories_v1")
    print(f"\n  WS5 Recovery Parameters:")
    print(f"    Recovery trajectories:  {recovery_count:>5d}")
    report["recovery_parameters"] = {"total": recovery_count}

    # Workstream 6: Intervention Kernels
    kernels_count = _count(session, "intervention_kernels_v1")
    print(f"\n  WS6 Intervention Kernels:")
    print(f"    Kernels defined:        {kernels_count:>5d}")
    report["intervention_kernels"] = {"total": kernels_count}

    # Workstream 7: Correlations
    correlations_count = _count(session, "biomarker_correlations_v1")
    print(f"\n  WS7 Correlations:")
    print(f"    Correlation entries:    {correlations_count:>5d}")
    report["correlations"] = {"total": correlations_count}

    return report


def report_acquisition(session) -> dict:
    """Section 5: Acquisition queue status."""
    _section_header("ACQUISITION QUEUE")

    total = _count(session, "acquisition_queue_v1")
    print(f"  Total queue entries:      {total:>5d}")

    report = {"total": total}

    if total > 0:
        try:
            result = session.execute(text(
                "SELECT status, count(*) FROM acquisition_queue_v1 "
                "GROUP BY status ORDER BY count(*) DESC"
            ))
            for row in result:
                print(f"    {row[0]:20s} {row[1]:>5d}")
                report[row[0]] = row[1]
        except Exception:
            pass

    return report


def report_gaps(session) -> list[str]:
    """Section 6: Gap analysis — what's missing."""
    _section_header("GAP ANALYSIS — NEXT ACTIONS")

    gaps = []

    # Check Tier 1 prerequisites
    nodes = _count(session, "biomarker_node_definitions_v1")
    edges = _count(session, "edge_relations_definitions_v1")
    instruments = _count(session, "instrument_definitions_v1")
    search_terms = _count(session, "node_search_terms_v1")

    if nodes < 63:
        gap = f"Nodes: {nodes}/63 defined. Add remaining nodes to seeds/nodes.csv"
        gaps.append(gap)
        print(f"  [!] {gap}")

    if edges < 50:
        gap = f"Edges: {edges} defined. Target ~129 for full DAG coverage"
        gaps.append(gap)
        print(f"  [!] {gap}")

    if instruments < 20:
        gap = f"Instruments: {instruments} defined. Target ~23 for clinical coverage"
        gaps.append(gap)
        print(f"  [!] {gap}")

    if search_terms < 100:
        gap = f"Search terms: {search_terms}. Need terms for all nodes to drive acquisition"
        gaps.append(gap)
        print(f"  [!] {gap}")

    # Check evidence gaps
    total_edges = edges
    try:
        result = session.execute(text(
            "SELECT count(DISTINCT edge_relation_id) FROM edge_evidence_v1"
        ))
        covered_edges = result.scalar() or 0
    except Exception:
        covered_edges = 0

    uncovered = total_edges - covered_edges
    if uncovered > 0:
        gap = f"Edge evidence: {uncovered}/{total_edges} edges have ZERO evidence rows"
        gaps.append(gap)
        print(f"  [!] {gap}")

    # Check Class A tables that should exist but are empty
    empty_tables = []
    optional_tables = [
        ("action_catalog_v1", "Actions"),
        ("normalization_refs_v1", "Normalization refs"),
        ("harmonization_rules_v1", "Harmonization rules"),
    ]
    for table, label in optional_tables:
        if _count(session, table) == 0:
            empty_tables.append(label)

    if empty_tables:
        gap = f"Empty Class A tables (Tier 2): {', '.join(empty_tables)}"
        gaps.append(gap)
        print(f"  [i] {gap}")

    # Recommended next action
    print(f"\n  --- RECOMMENDED NEXT ACTIONS ---")
    if _count(session, "extraction_runs") == 0:
        print(f"  1. Run manual smoke test: python scripts/run_extraction.py <pdf_path>")
        print(f"     (Validates end-to-end pipeline before automated acquisition)")
    elif covered_edges == 0:
        print(f"  1. Start acquisition: python scripts/run_acquisition.py --workstream instruments --max-papers 10 --dry-run")
        print(f"     (Instruments first — no pooling protection needed)")
    else:
        print(f"  1. Continue acquisition for gaps above")
        print(f"  2. Check workstream fill rates for next priority")

    if not gaps:
        print(f"  No critical gaps detected.")

    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description="CRCI system status report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--workstream", action="store_true", help="Workstream detail only")
    parser.add_argument("--gaps", action="store_true", help="Gap analysis only")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level)

    init_db()

    with get_session() as session:
        full_report = {}

        if args.json:
            # Silent mode — collect all data
            full_report["class_a"] = {}
            tables_a = [
                "biomarker_node_definitions_v1", "edge_relations_definitions_v1",
                "instrument_definitions_v1", "measure_definitions_v1",
                "pathways_v1", "node_search_terms_v1", "observation_noise_v1",
                "feedback_loops_v1",
            ]
            for t in tables_a:
                full_report["class_a"][t] = _count(session, t)

            full_report["class_b"] = {}
            tables_b = [
                "study_registry_v1", "edge_evidence_v1",
                "instrument_evidence_v1", "population_norms_v1",
                "extraction_runs",
            ]
            for t in tables_b:
                full_report["class_b"][t] = _count(session, t)

            print(json.dumps(full_report, indent=2))
            return 0

        print(f"\n{'#' * 70}")
        print(f"  CRCI SYSTEM STATUS REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'#' * 70}")

        if args.workstream:
            report_workstreams(session)
        elif args.gaps:
            report_gaps(session)
        else:
            report_class_a(session)
            report_class_b(session)
            report_workstreams(session)
            report_acquisition(session)
            report_gaps(session)

        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
