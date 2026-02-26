#!/usr/bin/env python3
"""
Populate harmonized_beta / harmonized_se on existing edge_evidence_v1 rows.

This script converts raw reported effect sizes into the model's standardized
scale (Cohen's d) so the evidence_loader can feed Chain B.

Conversion logic:
    - Cohen's d:      copy directly (already standardized)
    - Mean difference: convert to d via  d = MD / SD_pooled
                       where SD_pooled = SE_MD / √(1/n1 + 1/n2)
                       and   SE_d ≈ √(1/n1 + 1/n2 + d²/(2(n1+n2)))

Usage:
    python scripts/harmonize_evidence.py [--db-path crci_dev.db] [--dry-run]
"""
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from pathlib import Path


def _compute_cohens_d_from_md(
    md: float, se_md: float, n1: int, n2: int
) -> tuple[float, float]:
    """Convert mean difference to Cohen's d with SE.

    Args:
        md: Mean difference (treatment - control)
        se_md: Standard error of the mean difference
        n1: Treatment group size
        n2: Control group size

    Returns:
        (d, se_d) — standardized mean difference and its SE.
    """
    # SD_pooled = SE_MD / √(1/n1 + 1/n2)
    var_factor = 1.0 / n1 + 1.0 / n2
    sd_pooled = se_md / math.sqrt(var_factor)

    if sd_pooled <= 0:
        raise ValueError(f"SD_pooled = {sd_pooled} <= 0")

    # Cohen's d = MD / SD_pooled
    d = md / sd_pooled

    # SE(d) ≈ √(1/n1 + 1/n2 + d²/(2(n1+n2)))
    n_total = n1 + n2
    se_d = math.sqrt(var_factor + d**2 / (2 * n_total))

    return d, se_d


def harmonize_evidence(db_path: str, dry_run: bool = False) -> int:
    """Populate harmonized_beta and harmonized_se for all active evidence rows.

    Returns:
        Number of rows updated.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch all active evidence rows
    c.execute("""
        SELECT ee.ler_id, ee.edge_relation_id, ee.study_id,
               ee.effect_type_reported, ee.effect_value_reported,
               ee.se_reported, ee.N_effect, ee.effect_size_type,
               sr.year, sr.study_design
        FROM edge_evidence_v1 ee
        LEFT JOIN study_registry_v1 sr ON ee.study_id = sr.study_id
        WHERE ee.active = 1
        ORDER BY ee.study_id, ee.edge_relation_id
    """)
    rows = c.fetchall()

    # Study-level sample size overrides (from curated paper data)
    # Used when N_effect is total but we need arm sizes
    _ARM_SIZES: dict[str, tuple[int, int]] = {
        "STUDY_CAMPBELL_2017": (10, 9),     # 10 exercise, 9 control
        "STUDY_CHERRIER_2013": (12, 16),    # 12 treatment, 16 control
        "STUDY_NORTHEY_2018": (6, 5),       # 3-arm: HIIT(6) vs MOD(6) vs CON(5) — use HIIT vs CON
    }

    updated = 0
    for row in rows:
        ler_id = row["ler_id"]
        study_id = row["study_id"]
        effect_type = row["effect_type_reported"] or ""
        beta_raw = row["effect_value_reported"]
        se_raw = row["se_reported"]
        n_total = row["N_effect"]

        if beta_raw is None or se_raw is None:
            print(f"  SKIP {ler_id}: missing beta or SE")
            continue

        # Determine conversion strategy
        is_cohen_d = effect_type.lower() in ("cohen_d", "cohens_d", "smd")
        is_mean_diff = "mean_diff" in effect_type.lower()

        if is_cohen_d:
            # Already standardized — copy directly
            h_beta = beta_raw
            h_se = se_raw
            h_scale = "smd"
            formula = "direct_copy"

        elif is_mean_diff:
            # Convert MD → Cohen's d
            n1, n2 = _ARM_SIZES.get(study_id, (None, None))
            if n1 is None or n2 is None:
                # Fall back: split N_effect evenly
                if n_total and n_total > 1:
                    n1 = n_total // 2
                    n2 = n_total - n1
                else:
                    print(f"  SKIP {ler_id}: mean_diff but no arm sizes")
                    continue

            h_beta, h_se = _compute_cohens_d_from_md(beta_raw, se_raw, n1, n2)
            h_scale = "smd"
            formula = f"md_to_d(n1={n1},n2={n2})"

        else:
            # Unknown effect type — try direct use as standardized
            print(f"  WARN {ler_id}: unknown effect_type '{effect_type}', using raw values")
            h_beta = beta_raw
            h_se = se_raw
            h_scale = "raw"
            formula = "raw_copy"

        print(
            f"  {study_id:30s} | {row['edge_relation_id']:38s} | "
            f"raw={beta_raw:+.4f}±{se_raw:.4f} → "
            f"d={h_beta:+.4f}±{h_se:.4f} [{formula}]"
        )

        if not dry_run:
            c.execute(
                """
                UPDATE edge_evidence_v1
                SET harmonized_beta = ?,
                    harmonized_se = ?,
                    harmonized_scale = ?,
                    harmonization_status = 'harmonized',
                    harmonization_rule_id = ?
                WHERE ler_id = ?
                """,
                (h_beta, h_se, h_scale, formula, ler_id),
            )
            updated += 1

    if not dry_run:
        conn.commit()
        print(f"\n  Updated {updated} rows in edge_evidence_v1")
    else:
        print(f"\n  [DRY RUN] Would update {updated} rows")

    conn.close()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Harmonize evidence in DB")
    parser.add_argument(
        "--db-path", default="crci_dev.db", help="Path to SQLite database"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would change without writing"
    )
    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"Error: database not found: {args.db_path}", file=sys.stderr)
        return 1

    print(f"Harmonizing evidence in {args.db_path}...")
    harmonize_evidence(args.db_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
