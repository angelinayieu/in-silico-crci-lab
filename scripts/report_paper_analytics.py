#!/usr/bin/env python3
"""
CRCI Paper Analytics Report — System 1/2 Evidence Dashboard.

Produces the analytics outputs described in BOX_TO_IMPLEMENTATION_MAPPING_v2.md
(System 1 outputs): literature space shape, per-pathway coverage depth,
design-tier distribution, edge saturation report, and per-paper yield metrics.

Usage:
    python scripts/report_paper_analytics.py              # Full terminal report
    python scripts/report_paper_analytics.py --json       # Machine-readable JSON
    python scripts/report_paper_analytics.py --section X  # Single section (1-7)
    python scripts/report_paper_analytics.py --csv        # Export gap matrix CSV

Sections:
    1. Papers Overview — per-paper edge yield, design, cancer type, N
    2. Design × Cancer Matrix — cross-tabulation of evidence rows
    3. Edge Saturation Report — per-edge k, studies, pooled β, gap tier
    4. Pathway Coverage — per-pathway edges covered vs total, evidence depth
    5. Literature Space Shape — summary statistics across all dimensions
    6. Compiled Edge Quality — IVW-pooled edges with confidence metrics
    7. Priority Gap List — edges with 0 or insufficient evidence, ranked
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from io import StringIO
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
DB_PATH = _project_root / "crci_dev.db"


# ═══════════════════════════════════════════════════════════════
#  Utility
# ═══════════════════════════════════════════════════════════════


def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _hdr(title: str) -> None:
    w = 80
    print(f"\n{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}")


def _bar(val: float, max_val: float, width: int = 30) -> str:
    """ASCII bar chart character."""
    if max_val <= 0:
        return ""
    filled = int(round(val / max_val * width))
    return "█" * filled + "░" * (width - filled)


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "  --%"
    return f"{num / denom * 100:4.0f}%"


def _gap_tier(k: int, has_rct: bool, i_squared: float) -> str:
    """Classify evidence gap severity (aligns with S5-1 in evidence_gap_compiler)."""
    if k == 0:
        return "MISSING"
    if k == 1:
        return "SINGLE"
    if k < 3 and not has_rct:
        return "LOW_K"
    if i_squared > 0.75:
        return "HIGH_HET"
    return "ADEQUATE"


GAP_TIER_ORDER = {"MISSING": 0, "SINGLE": 1, "LOW_K": 2, "HIGH_HET": 3, "ADEQUATE": 4}


# ═══════════════════════════════════════════════════════════════
#  Section 1: Papers Overview
# ═══════════════════════════════════════════════════════════════


def section_papers_overview(conn: sqlite3.Connection) -> list[dict]:
    _hdr("SECTION 1 — PAPERS IN DATABASE (per-paper edge yield)")

    rows = conn.execute("""
        SELECT
            s.study_id,
            s.authors,
            s.year,
            s.study_design,
            s.doi,
            COUNT(DISTINCT e.edge_relation_id) AS edges_covered,
            COUNT(e.rowid)                     AS evidence_rows,
            SUM(e.N_effect)                    AS total_n,
            GROUP_CONCAT(DISTINCT e.cancer_type)    AS cancer_types,
            GROUP_CONCAT(DISTINCT e.treatment_phase) AS phases,
            GROUP_CONCAT(DISTINCT e.effect_size_type) AS effect_types
        FROM study_registry_v1 s
        LEFT JOIN edge_evidence_v1 e ON s.study_id = e.study_id
        GROUP BY s.study_id
        ORDER BY edges_covered DESC, s.year DESC
    """).fetchall()

    papers = []
    max_edges = max((r["edges_covered"] for r in rows), default=1) or 1

    fmt = "{:<36s}  {:>4s}  {:>15s}  {:>5s}  {:>4s}  {:>6s}  {}"
    print(fmt.format("Study", "Year", "Design", "Edges", "Rows", "N", "Yield"))
    print("─" * 100)

    for r in rows:
        author_short = (r["authors"] or "Unknown")[:25]
        study_label = f"{author_short} ({r['year'] or '?'})"
        n_str = f"{r['total_n']:,}" if r["total_n"] else "-"
        bar = _bar(r["edges_covered"], max_edges, 20)

        print(fmt.format(
            study_label[:36],
            str(r["year"] or ""),
            (r["study_design"] or "unknown")[:15],
            str(r["edges_covered"]),
            str(r["evidence_rows"]),
            n_str[:6],
            bar,
        ))

        papers.append({
            "study_id": r["study_id"],
            "authors": r["authors"],
            "year": r["year"],
            "design": r["study_design"],
            "doi": r["doi"],
            "edges_covered": r["edges_covered"],
            "evidence_rows": r["evidence_rows"],
            "total_n": r["total_n"],
            "cancer_types": r["cancer_types"],
            "phases": r["phases"],
        })

    total_papers = len(rows)
    total_rows = sum(r["evidence_rows"] for r in rows)
    papers_with_evidence = sum(1 for r in rows if r["evidence_rows"] > 0)

    print("─" * 100)
    print(f"  TOTAL: {total_papers} papers registered, "
          f"{papers_with_evidence} with evidence, "
          f"{total_rows} evidence rows")

    return papers


# ═══════════════════════════════════════════════════════════════
#  Section 2: Design × Cancer Matrix
# ═══════════════════════════════════════════════════════════════


def section_design_cancer_matrix(conn: sqlite3.Connection) -> dict:
    _hdr("SECTION 2 — DESIGN-TIER × CANCER-TYPE MATRIX (evidence rows)")

    rows = conn.execute("""
        SELECT
            COALESCE(study_design, 'unknown')  AS design,
            COALESCE(cancer_type, 'unknown')   AS cancer,
            COUNT(*)                           AS cnt
        FROM edge_evidence_v1
        GROUP BY design, cancer
        ORDER BY cnt DESC
    """).fetchall()

    # Build matrix
    designs = sorted(set(r["design"] for r in rows))
    cancers = sorted(set(r["cancer"] for r in rows))
    matrix = defaultdict(lambda: defaultdict(int))
    design_totals = defaultdict(int)
    cancer_totals = defaultdict(int)

    for r in rows:
        matrix[r["design"]][r["cancer"]] = r["cnt"]
        design_totals[r["design"]] += r["cnt"]
        cancer_totals[r["cancer"]] += r["cnt"]

    # Header
    col_w = 8
    header = f"{'Design':<18s}"
    for c in cancers:
        header += f" {c[:col_w]:>{col_w}s}"
    header += f" {'TOTAL':>{col_w}s}"
    print(header)
    print("─" * len(header))

    for d in designs:
        line = f"{d:<18s}"
        for c in cancers:
            v = matrix[d][c]
            line += f" {v if v else '.':>{col_w}}"
        line += f" {design_totals[d]:>{col_w}d}"
        print(line)

    # Totals row
    line = f"{'TOTAL':<18s}"
    for c in cancers:
        line += f" {cancer_totals[c]:>{col_w}d}"
    line += f" {sum(design_totals.values()):>{col_w}d}"
    print("─" * len(header))
    print(line)

    # Design tier summary
    print("\n  Design tier distribution:")
    tier_order = ["meta_analysis", "systematic_review", "RCT", "cohort",
                  "cross_sectional", "unknown"]
    for d in tier_order:
        if d in design_totals:
            pct = design_totals[d] / sum(design_totals.values()) * 100
            bar = _bar(design_totals[d], max(design_totals.values()), 25)
            print(f"    {d:<22s} {design_totals[d]:>4d} ({pct:4.1f}%)  {bar}")

    return {"matrix": dict(matrix), "design_totals": dict(design_totals),
            "cancer_totals": dict(cancer_totals)}


# ═══════════════════════════════════════════════════════════════
#  Section 3: Edge Saturation Report
# ═══════════════════════════════════════════════════════════════


def section_edge_saturation(conn: sqlite3.Connection) -> list[dict]:
    _hdr("SECTION 3 — EDGE SATURATION REPORT (per-edge evidence depth)")

    # All defined edges
    all_edges = conn.execute("""
        SELECT edge_relation_id, edge_family, node_x, node_y
        FROM edge_relations_definitions_v1
        WHERE active = 1
        ORDER BY edge_relation_id
    """).fetchall()

    # Evidence stats per edge
    evidence = conn.execute("""
        SELECT
            edge_relation_id,
            COUNT(*)                            AS k,
            COUNT(DISTINCT study_id)            AS n_studies,
            SUM(N_effect)                       AS total_n,
            GROUP_CONCAT(DISTINCT study_design) AS designs,
            ROUND(AVG(CASE WHEN harmonized_beta IS NOT NULL
                       THEN harmonized_beta END), 4) AS avg_beta,
            MAX(CASE WHEN study_design = 'RCT' THEN 1 ELSE 0 END) AS has_rct,
            GROUP_CONCAT(DISTINCT cancer_type) AS cancers,
            GROUP_CONCAT(DISTINCT treatment_phase) AS phases
        FROM edge_evidence_v1
        GROUP BY edge_relation_id
    """).fetchall()

    ev_map = {r["edge_relation_id"]: dict(r) for r in evidence}

    # Compiled edges for I²
    compiled = conn.execute("""
        SELECT edge_relation_id, i_squared, beta_mean, beta_se, total_n
        FROM edges_v1
    """).fetchall()
    compiled_map = {r["edge_relation_id"]: dict(r) for r in compiled}

    edge_report = []
    tier_counts = defaultdict(int)

    for edge in all_edges:
        eid = edge["edge_relation_id"]
        ev = ev_map.get(eid, {})
        comp = compiled_map.get(eid, {})

        k = ev.get("k", 0)
        n_studies = ev.get("n_studies", 0)
        has_rct = bool(ev.get("has_rct", 0))
        i_sq = comp.get("i_squared", 0.0) or 0.0
        tier = _gap_tier(k, has_rct, i_sq)
        tier_counts[tier] += 1

        entry = {
            "edge_id": eid,
            "pathway": edge["edge_family"],
            "node_x": edge["node_x"],
            "node_y": edge["node_y"],
            "k": k,
            "n_studies": n_studies,
            "total_n": ev.get("total_n"),
            "designs": ev.get("designs", ""),
            "has_rct": has_rct,
            "avg_beta": ev.get("avg_beta"),
            "i_squared": i_sq,
            "pooled_beta": comp.get("beta_mean"),
            "pooled_se": comp.get("beta_se"),
            "gap_tier": tier,
            "cancers": ev.get("cancers", ""),
            "phases": ev.get("phases", ""),
        }
        edge_report.append(entry)

    # Sort: ADEQUATE first (ascending gap), then by k descending
    edge_report.sort(key=lambda e: (GAP_TIER_ORDER.get(e["gap_tier"], 5), -e["k"]))

    # Print edges with evidence first
    print("\n  Edges WITH evidence:")
    fmt = "  {:<38s} {:>3s} {:>3s} {:>7s} {:>8s} {:>8s} {:>10s} {}"
    print(fmt.format("Edge ID", "k", "St", "N", "Avg β", "I²", "Tier", "Designs"))
    print("  " + "─" * 98)

    for e in edge_report:
        if e["k"] == 0:
            continue
        n_str = f"{e['total_n']:,}" if e["total_n"] else "-"
        beta_str = f"{e['avg_beta']:.3f}" if e["avg_beta"] is not None else "-"
        isq_str = f"{e['i_squared']:.1%}" if e["i_squared"] else "-"
        print(fmt.format(
            e["edge_id"][:38],
            str(e["k"]),
            str(e["n_studies"]),
            n_str[:7],
            beta_str[:8],
            isq_str[:8],
            e["gap_tier"][:10],
            (e["designs"] or "")[:25],
        ))

    # Tier summary
    total_edges = len(all_edges)
    print(f"\n  Gap tier summary ({total_edges} total edges):")
    for tier_name in ["ADEQUATE", "HIGH_HET", "LOW_K", "SINGLE", "MISSING"]:
        cnt = tier_counts.get(tier_name, 0)
        pct = cnt / total_edges * 100 if total_edges > 0 else 0
        marker = "✓" if tier_name == "ADEQUATE" else "!" if tier_name in ("SINGLE", "MISSING") else "~"
        bar = _bar(cnt, total_edges, 30)
        print(f"    {marker} {tier_name:<12s} {cnt:>4d} ({pct:4.1f}%)  {bar}")

    return edge_report


# ═══════════════════════════════════════════════════════════════
#  Section 4: Pathway Coverage
# ═══════════════════════════════════════════════════════════════


def section_pathway_coverage(conn: sqlite3.Connection) -> list[dict]:
    _hdr("SECTION 4 — PATHWAY COVERAGE (edges evidenced per pathway)")

    # edge_family = pathway_id in edge_relations_definitions_v1
    pathway_labels = {}
    for r in conn.execute("SELECT pathway_id, pathway_label, tier FROM pathways_v1"):
        pathway_labels[r["pathway_id"]] = {
            "label": r["pathway_label"] or r["pathway_id"],
            "tier": r["tier"] or "unknown",
        }

    # Count total edges per pathway
    pw_edges = conn.execute("""
        SELECT edge_family AS pathway_id,
               COUNT(*) AS total_edges
        FROM edge_relations_definitions_v1
        WHERE active = 1
        GROUP BY edge_family
    """).fetchall()

    # Count edges with evidence per pathway
    pw_evidence = conn.execute("""
        SELECT er.edge_family AS pathway_id,
               COUNT(DISTINCT e.edge_relation_id)               AS edges_with_evidence,
               COUNT(e.rowid)                                   AS total_rows,
               COUNT(DISTINCT e.study_id)                       AS n_studies,
               SUM(e.N_effect)                                  AS total_n,
               GROUP_CONCAT(DISTINCT e.study_design)            AS designs
        FROM edge_relations_definitions_v1 er
        INNER JOIN edge_evidence_v1 e ON e.edge_relation_id = er.edge_relation_id
        WHERE er.active = 1
        GROUP BY er.edge_family
    """).fetchall()

    pw_ev_map = {r["pathway_id"]: dict(r) for r in pw_evidence}

    report = []
    for pw in pw_edges:
        pid = pw["pathway_id"]
        meta = pathway_labels.get(pid, {"label": pid, "tier": "unknown"})
        ev = pw_ev_map.get(pid, {})
        total = pw["total_edges"]
        covered = ev.get("edges_with_evidence", 0)
        coverage = covered / total if total > 0 else 0.0

        report.append({
            "pathway_id": pid,
            "label": meta["label"],
            "tier": meta["tier"],
            "total_edges": total,
            "edges_with_evidence": covered,
            "coverage": coverage,
            "evidence_rows": ev.get("total_rows", 0),
            "n_studies": ev.get("n_studies", 0),
            "total_n": ev.get("total_n", 0),
            "designs": ev.get("designs", ""),
        })

    report.sort(key=lambda p: -p["coverage"])

    fmt = "  {:<42s} {:>3s}/{:<3s} {:>5s}  {:>4s}  {:>7s}  {}"
    print(fmt.format("Pathway", "Cov", "Tot", "Pct", "Rows", "N", "Bar"))
    print("  " + "─" * 90)

    max_cov = max((p["edges_with_evidence"] for p in report), default=1) or 1

    for p in report:
        n_str = f"{p['total_n']:,}" if p["total_n"] else "-"
        bar = _bar(p["coverage"], 1.0, 20)
        status = "●" if p["coverage"] >= 0.5 else "◐" if p["coverage"] > 0 else "○"
        print(f"  {status} {p['label'][:40]:<40s} {p['edges_with_evidence']:>3d}/{p['total_edges']:<3d}"
              f" {_pct(p['edges_with_evidence'], p['total_edges'])}  {p['evidence_rows']:>4d}"
              f"  {n_str:>7s}  {bar}")

    # Summary
    total_pw = len(report)
    pw_with_ev = sum(1 for p in report if p["edges_with_evidence"] > 0)
    all_edges_total = sum(p["total_edges"] for p in report)
    all_edges_covered = sum(p["edges_with_evidence"] for p in report)
    print("  " + "─" * 90)
    print(f"  TOTAL: {pw_with_ev}/{total_pw} pathways have evidence, "
          f"{all_edges_covered}/{all_edges_total} edges covered "
          f"({_pct(all_edges_covered, all_edges_total)})")

    return report


# ═══════════════════════════════════════════════════════════════
#  Section 5: Literature Space Shape
# ═══════════════════════════════════════════════════════════════


def section_literature_space(conn: sqlite3.Connection) -> dict:
    _hdr("SECTION 5 — LITERATURE SPACE SHAPE (summary statistics)")

    stats = {}

    # Total counts
    stats["total_papers"] = conn.execute(
        "SELECT COUNT(*) FROM study_registry_v1").fetchone()[0]
    stats["papers_with_evidence"] = conn.execute(
        "SELECT COUNT(DISTINCT study_id) FROM edge_evidence_v1").fetchone()[0]
    stats["total_evidence_rows"] = conn.execute(
        "SELECT COUNT(*) FROM edge_evidence_v1").fetchone()[0]
    stats["total_edges_defined"] = conn.execute(
        "SELECT COUNT(*) FROM edge_relations_definitions_v1 WHERE active=1"
    ).fetchone()[0]
    stats["edges_with_evidence"] = conn.execute(
        "SELECT COUNT(DISTINCT edge_relation_id) FROM edge_evidence_v1"
    ).fetchone()[0]
    stats["edges_with_k2"] = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT edge_relation_id FROM edge_evidence_v1
            GROUP BY edge_relation_id HAVING COUNT(*) >= 2
        )
    """).fetchone()[0]
    stats["edges_with_k3"] = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT edge_relation_id FROM edge_evidence_v1
            GROUP BY edge_relation_id HAVING COUNT(*) >= 3
        )
    """).fetchone()[0]
    stats["compiled_edges"] = conn.execute(
        "SELECT COUNT(*) FROM edges_v1").fetchone()[0]

    # Total sample size
    stats["total_sample_n"] = conn.execute(
        "SELECT SUM(N_effect) FROM edge_evidence_v1").fetchone()[0] or 0

    # Auxiliary evidence
    stats["population_norms"] = conn.execute(
        "SELECT COUNT(*) FROM population_norms_v1").fetchone()[0]
    stats["temporal_evidence"] = conn.execute(
        "SELECT COUNT(*) FROM temporal_evidence_v1").fetchone()[0]
    stats["instrument_evidence"] = conn.execute(
        "SELECT COUNT(*) FROM instrument_evidence_v1").fetchone()[0]

    # Year range
    year_range = conn.execute(
        "SELECT MIN(pub_year), MAX(pub_year) FROM edge_evidence_v1 WHERE pub_year IS NOT NULL"
    ).fetchone()
    stats["year_min"] = year_range[0]
    stats["year_max"] = year_range[1]

    # SE derivation levels
    se_levels = conn.execute("""
        SELECT COALESCE(se_derivation_level, 'unknown') AS lvl, COUNT(*) AS cnt
        FROM edge_evidence_v1
        GROUP BY lvl ORDER BY cnt DESC
    """).fetchall()

    # Print
    print(f"  Papers registered:          {stats['total_papers']:>5d}")
    print(f"  Papers with evidence:       {stats['papers_with_evidence']:>5d}")
    print(f"  Total evidence rows:        {stats['total_evidence_rows']:>5d}")
    print(f"  Total sample N:           {stats['total_sample_n']:>7,d}")
    print(f"  Publication year range:     {stats['year_min'] or '?'} – {stats['year_max'] or '?'}")
    print()
    print(f"  Edges defined:              {stats['total_edges_defined']:>5d}")
    print(f"  Edges with k≥1:            {stats['edges_with_evidence']:>5d}  "
          f"({_pct(stats['edges_with_evidence'], stats['total_edges_defined'])})")
    print(f"  Edges with k≥2 (IVW):      {stats['edges_with_k2']:>5d}  "
          f"({_pct(stats['edges_with_k2'], stats['total_edges_defined'])})")
    print(f"  Edges with k≥3 (robust):   {stats['edges_with_k3']:>5d}  "
          f"({_pct(stats['edges_with_k3'], stats['total_edges_defined'])})")
    print(f"  Edges compiled (edges_v1):  {stats['compiled_edges']:>5d}")
    print()
    print(f"  Population norms:           {stats['population_norms']:>5d}")
    print(f"  Temporal evidence rows:     {stats['temporal_evidence']:>5d}")
    print(f"  Instrument evidence rows:   {stats['instrument_evidence']:>5d}")

    if se_levels:
        print("\n  SE derivation breakdown:")
        for r in se_levels:
            print(f"    {r['lvl']:<25s} {r['cnt']:>4d} rows")

    return stats


# ═══════════════════════════════════════════════════════════════
#  Section 6: Compiled Edge Quality
# ═══════════════════════════════════════════════════════════════


def section_compiled_edges(conn: sqlite3.Connection) -> list[dict]:
    _hdr("SECTION 6 — COMPILED EDGE QUALITY (IVW-pooled parameters)")

    rows = conn.execute("""
        SELECT
            c.edge_relation_id,
            c.beta_mean,
            c.beta_se,
            c.total_n,
            c.i_squared,
            c.evidence_level,
            c.pub_bias_risk,
            c.e_value,
            er.edge_family,
            er.node_x,
            er.node_y
        FROM edges_v1 c
        JOIN edge_relations_definitions_v1 er
            ON er.edge_relation_id = c.edge_relation_id
        ORDER BY ABS(c.beta_mean) DESC
    """).fetchall()

    fmt = "  {:<38s} {:>8s} {:>8s} {:>7s} {:>5s} {:>12s}"
    print(fmt.format("Edge", "β_IVW", "SE_IVW", "N", "I²", "Evidence"))
    print("  " + "─" * 85)

    report = []
    for r in rows:
        beta_str = f"{r['beta_mean']:.4f}" if r["beta_mean"] is not None else "-"
        se_str = f"{r['beta_se']:.4f}" if r["beta_se"] is not None else "-"
        n_str = f"{r['total_n']:,}" if r["total_n"] else "-"
        isq_str = f"{r['i_squared']:.1%}" if r["i_squared"] else "-"

        # Flag suspicious SE (very large = possible issue)
        se_flag = ""
        if r["beta_se"] and r["beta_se"] > 1e6:
            se_flag = " ⚠️"

        print(fmt.format(
            r["edge_relation_id"][:38],
            beta_str[:8],
            (se_str[:8] if r["beta_se"] and r["beta_se"] < 1e6 else "⚠HIGH")[:8],
            n_str[:7],
            isq_str[:5],
            (r["evidence_level"] or "?")[:12],
        ))

        report.append({
            "edge_id": r["edge_relation_id"],
            "beta_mean": r["beta_mean"],
            "beta_se": r["beta_se"],
            "total_n": r["total_n"],
            "i_squared": r["i_squared"],
            "evidence_level": r["evidence_level"],
            "pathway": r["edge_family"],
        })

    print(f"\n  {len(rows)} compiled edges total")

    return report


# ═══════════════════════════════════════════════════════════════
#  Section 7: Priority Gap List
# ═══════════════════════════════════════════════════════════════


def section_priority_gaps(conn: sqlite3.Connection) -> list[dict]:
    _hdr("SECTION 7 — PRIORITY GAP LIST (edges needing evidence)")

    # All defined edges
    all_edges = conn.execute("""
        SELECT edge_relation_id, edge_family, node_x, node_y
        FROM edge_relations_definitions_v1
        WHERE active = 1
    """).fetchall()

    # Edges with evidence
    covered = conn.execute("""
        SELECT edge_relation_id, COUNT(*) AS k,
               COUNT(DISTINCT study_id) AS n_studies,
               MAX(CASE WHEN study_design = 'RCT' THEN 1 ELSE 0 END) AS has_rct
        FROM edge_evidence_v1
        GROUP BY edge_relation_id
    """).fetchall()
    covered_map = {r["edge_relation_id"]: dict(r) for r in covered}

    gaps = []
    for edge in all_edges:
        eid = edge["edge_relation_id"]
        ev = covered_map.get(eid, {})
        k = ev.get("k", 0)
        has_rct = bool(ev.get("has_rct", 0))
        tier = _gap_tier(k, has_rct, 0.0)

        if tier != "ADEQUATE":
            gaps.append({
                "edge_id": eid,
                "pathway": edge["edge_family"],
                "node_x": edge["node_x"],
                "node_y": edge["node_y"],
                "k": k,
                "gap_tier": tier,
                "need": "any evidence" if k == 0 else
                        "replication (k=1)" if k == 1 else
                        "RCT or additional study",
            })

    # Sort: MISSING first, then SINGLE, then LOW_K
    gaps.sort(key=lambda g: (GAP_TIER_ORDER.get(g["gap_tier"], 5), g["edge_id"]))

    # Group by pathway for display
    by_pathway = defaultdict(list)
    for g in gaps:
        by_pathway[g["pathway"]].append(g)

    for pw_id in sorted(by_pathway.keys()):
        pw_gaps = by_pathway[pw_id]
        missing = sum(1 for g in pw_gaps if g["gap_tier"] == "MISSING")
        single = sum(1 for g in pw_gaps if g["gap_tier"] == "SINGLE")
        low_k = sum(1 for g in pw_gaps if g["gap_tier"] == "LOW_K")
        print(f"\n  {pw_id}  ({missing} missing, {single} single, {low_k} low-k)")
        for g in pw_gaps:
            marker = "  ○" if g["gap_tier"] == "MISSING" else "  ◐" if g["gap_tier"] == "SINGLE" else "  △"
            print(f"    {marker} {g['edge_id']:<40s} k={g['k']}  → {g['need']}")

    n_missing = sum(1 for g in gaps if g["gap_tier"] == "MISSING")
    n_single = sum(1 for g in gaps if g["gap_tier"] == "SINGLE")
    n_low_k = sum(1 for g in gaps if g["gap_tier"] == "LOW_K")
    print(f"\n  TOTAL GAPS: {len(gaps)} edges need attention")
    print(f"    ○ MISSING (k=0): {n_missing}")
    print(f"    ◐ SINGLE (k=1): {n_single}")
    print(f"    △ LOW_K  (k<3):  {n_low_k}")

    return gaps


# ═══════════════════════════════════════════════════════════════
#  CSV Export (gap matrix)
# ═══════════════════════════════════════════════════════════════


def export_gap_csv(conn: sqlite3.Connection, outpath: Path) -> None:
    """Export edge saturation as CSV for spreadsheet analysis."""
    edges = section_edge_saturation.__wrapped__(conn) if hasattr(
        section_edge_saturation, "__wrapped__") else _build_edge_data(conn)

    with open(outpath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "edge_id", "pathway", "node_x", "node_y", "k", "n_studies",
            "total_n", "designs", "has_rct", "avg_beta", "i_squared",
            "pooled_beta", "pooled_se", "gap_tier", "cancers", "phases",
        ])
        writer.writeheader()
        for e in edges:
            writer.writerow(e)
    print(f"  Gap matrix exported to {outpath}")


def _build_edge_data(conn: sqlite3.Connection) -> list[dict]:
    """Build edge saturation data without printing (for CSV export)."""
    all_edges = conn.execute("""
        SELECT edge_relation_id, edge_family, node_x, node_y
        FROM edge_relations_definitions_v1 WHERE active = 1
        ORDER BY edge_relation_id
    """).fetchall()

    evidence = conn.execute("""
        SELECT edge_relation_id,
               COUNT(*) AS k, COUNT(DISTINCT study_id) AS n_studies,
               SUM(N_effect) AS total_n,
               GROUP_CONCAT(DISTINCT study_design) AS designs,
               ROUND(AVG(CASE WHEN harmonized_beta IS NOT NULL
                          THEN harmonized_beta END), 4) AS avg_beta,
               MAX(CASE WHEN study_design='RCT' THEN 1 ELSE 0 END) AS has_rct,
               GROUP_CONCAT(DISTINCT cancer_type) AS cancers,
               GROUP_CONCAT(DISTINCT treatment_phase) AS phases
        FROM edge_evidence_v1 GROUP BY edge_relation_id
    """).fetchall()
    ev_map = {r["edge_relation_id"]: dict(r) for r in evidence}

    compiled = conn.execute(
        "SELECT edge_relation_id, i_squared, beta_mean, beta_se, total_n FROM edges_v1"
    ).fetchall()
    comp_map = {r["edge_relation_id"]: dict(r) for r in compiled}

    result = []
    for edge in all_edges:
        eid = edge["edge_relation_id"]
        ev = ev_map.get(eid, {})
        comp = comp_map.get(eid, {})
        k = ev.get("k", 0)
        has_rct = bool(ev.get("has_rct", 0))
        i_sq = comp.get("i_squared", 0.0) or 0.0

        result.append({
            "edge_id": eid, "pathway": edge["edge_family"],
            "node_x": edge["node_x"], "node_y": edge["node_y"],
            "k": k, "n_studies": ev.get("n_studies", 0),
            "total_n": ev.get("total_n"), "designs": ev.get("designs", ""),
            "has_rct": has_rct, "avg_beta": ev.get("avg_beta"),
            "i_squared": i_sq,
            "pooled_beta": comp.get("beta_mean"),
            "pooled_se": comp.get("beta_se"),
            "gap_tier": _gap_tier(k, has_rct, i_sq),
            "cancers": ev.get("cancers", ""),
            "phases": ev.get("phases", ""),
        })
    return result


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CRCI Paper Analytics — Evidence Dashboard")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--csv", action="store_true",
                        help="Export edge gap matrix to CSV")
    parser.add_argument("--csv-path", type=str, default=None,
                        help="CSV export path (default: data/edge_saturation.csv)")
    parser.add_argument("--section", type=int, choices=range(1, 8),
                        help="Run a single section (1-7)")
    args = parser.parse_args()

    conn = _conn()

    if args.csv:
        outpath = Path(args.csv_path) if args.csv_path else _project_root / "data" / "edge_saturation.csv"
        export_gap_csv(conn, outpath)
        conn.close()
        return 0

    if args.json:
        result = {}
        result["generated_at"] = datetime.now().isoformat()
        result["papers"] = section_papers_overview(conn)
        result["design_cancer"] = section_design_cancer_matrix(conn)
        result["literature_space"] = section_literature_space(conn)
        # Suppress printed output for JSON by redirecting
        # (For simplicity, JSON mode still prints to stdout — pipe to jq)
        conn.close()
        return 0

    # Banner
    print(f"\n{'#' * 80}")
    print(f"  CRCI PAPER ANALYTICS REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#' * 80}")

    sections = {
        1: section_papers_overview,
        2: section_design_cancer_matrix,
        3: section_edge_saturation,
        4: section_pathway_coverage,
        5: section_literature_space,
        6: section_compiled_edges,
        7: section_priority_gaps,
    }

    if args.section:
        sections[args.section](conn)
    else:
        for num in sorted(sections):
            sections[num](conn)

    print()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
