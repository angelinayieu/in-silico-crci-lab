#!/usr/bin/env python3
"""
Phase A: Get evidence data into the database.

This script performs the critical data-loading steps identified in the
CRITICAL_REVIEW.md:

  A1. Reseed edge_relations_definitions_v1 from authoritative EDGE_REGISTRY.csv
      (replaces the 25 EDGE_* stubs with the full 137 ER_* edges)
  A2. Register all manually extracted studies in study_registry_v1
  A3. Load CSV evidence from data/manual_uploads/structured/ into edge_evidence_v1
      (maps CSV columns to DB columns)
  A4. Verify final state

Usage:
    python scripts/load_evidence_into_db.py
    python scripts/load_evidence_into_db.py --dry-run
    python scripts/load_evidence_into_db.py --verbose
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure DATABASE_URL
db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{PROJECT_ROOT}/crci_dev.db"
os.environ["DATABASE_URL"] = db_url

from sqlalchemy import text

from crci.shared.db import init_db, get_session

logger = logging.getLogger(__name__)


# ============================================================================
#  STUDY DEFINITIONS (manually extracted papers)
# ============================================================================
STUDIES = [
    {
        "study_id": "STUDY_CHERRIER_2013",
        "title": "A randomized trial of cognitive rehabilitation in cancer survivors",
        "authors": "Cherrier MM; Anderson K; David D; Higano CS; Gray H; Church A; Willis SL",
        "journal": "Life Sciences",
        "year": 2013,
        "doi": "10.1016/j.lfs.2013.08.011",
        "study_design": "RCT",
        "notes": "Cancer survivors; cognitive rehab vs wait-list; n=28; 8-week intervention",
    },
    {
        "study_id": "STUDY_CAMPBELL_2017",
        "title": "A randomised controlled trial of exercise to improve cognitive function "
                 "in breast cancer survivors during and after cancer treatment",
        "authors": "Campbell KL; Kam JWY; Neil-Sztramko SE; Liu Ambrose T; Handy TC; Lim HJ; et al",
        "journal": "Psycho-Oncology",
        "year": 2017,
        "doi": "10.1002/pon.4370",
        "study_design": "RCT",
        "notes": "Breast cancer; aerobic exercise vs usual care; n=19; pilot RCT",
    },
]


# ============================================================================
#  CSV → edge_evidence_v1 COLUMN MAPPING
# ============================================================================
# CSV columns → DB columns
# CSV: doi, edge_id, beta_raw, se_raw, effect_type_original, effect_size_type,
#      sample_size, study_design, cancer_type, treatment_phase, instrument_id,
#      confidence_note
#
# DB:  ler_id, edge_relation_id, study_id, edge_family, node_x, node_y,
#      effect_type_reported, effect_value_reported, se_reported,
#      N_effect, notes, effect_size_type, ...

# Map CSV edge_id → study_id (derived from DOI)
DOI_TO_STUDY = {
    "10.1016/j.lfs.2013.08.011": "STUDY_CHERRIER_2013",
    "10.1002/pon.4370": "STUDY_CAMPBELL_2017",
}


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ============================================================================
#  STEP 1: Reseed edge_relations_definitions_v1 from EDGE_REGISTRY.csv
# ============================================================================
def reseed_edge_definitions(engine, dry_run: bool = False) -> int:
    """Replace the 25 EDGE_* stubs with the full 137 ER_* edges from the registry.

    Maps EDGE_REGISTRY.csv columns to edge_relations_definitions_v1 columns:
      edge_relation_id → edge_relation_id
      source_node_id   → node_x
      target_node_id   → node_y
      relation_type    → relation_type
      mechanism_description → canonical_statement
      primary_pathway  → edge_family
      expected_sign    → default_effect_direction (map: positive→1, negative→-1, context_dependent→0)
      functional_form  → default_temporal_family (close enough: stores the canonical form type)
      notes           → notes
      version         → version
      active          → active
    """
    registry_path = PROJECT_ROOT / "registries" / "EDGE_REGISTRY.csv"
    if not registry_path.exists():
        logger.error("EDGE_REGISTRY.csv not found at %s", registry_path)
        return 0

    with open(registry_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Read %d edges from EDGE_REGISTRY.csv", len(rows))

    sign_map = {
        "positive": 1,
        "negative": -1,
        "context_dependent": 0,
    }

    # Derive module from source_node_id pattern
    def derive_module(source_node: str) -> str:
        if source_node.startswith("NODE_EXO_"):
            return "C"  # exogenous treatment/demographics
        elif source_node.startswith("NODE_BEH_"):
            return "B"  # behavioral
        elif source_node.startswith("NODE_BIO_"):
            return "L2"  # biomarker layer
        elif source_node.startswith("NODE_PATH_"):
            return "L3"  # pathway layer
        elif source_node.startswith("NODE_COG_"):
            return "L4"  # cognitive outcomes
        elif source_node.startswith("NODE_SYM_"):
            return "L5"  # symptom outcomes
        return "A"

    # Derive a human-readable relation_label from edge_relation_id
    def derive_label(edge_id: str, desc: str) -> str:
        if desc and len(desc) < 100:
            return desc
        # Fallback: humanize the edge ID → "ER_CHEMO_IL6" → "Chemo → IL6"
        parts = edge_id.replace("ER_", "").split("_")
        return " → ".join(p.capitalize() for p in parts)

    if not dry_run:
        with engine.begin() as conn:
            # Clear existing stubs
            result = conn.execute(text("DELETE FROM edge_relations_definitions_v1"))
            logger.info("Cleared %d existing edge definition rows", result.rowcount)

            insert_sql = text("""
                INSERT INTO edge_relations_definitions_v1 (
                    edge_relation_id, module, edge_family, node_x, node_y,
                    relation_label, canonical_statement, relation_type,
                    default_effect_direction, default_temporal_family,
                    notes, version, active
                ) VALUES (
                    :edge_relation_id, :module, :edge_family, :node_x, :node_y,
                    :relation_label, :canonical_statement, :relation_type,
                    :default_effect_direction, :default_temporal_family,
                    :notes, :version, :active
                )
            """)

            inserted = 0
            for row in rows:
                sign_str = row.get("expected_sign", "").strip()
                sign_val = sign_map.get(sign_str, 0)
                version = row.get("version", "1")
                active = row.get("active", "1")

                params = {
                    "edge_relation_id": row["edge_relation_id"].strip(),
                    "module": derive_module(row.get("source_node_id", "")),
                    "edge_family": row.get("primary_pathway", "").strip(),
                    "node_x": row.get("source_node_id", "").strip(),
                    "node_y": row.get("target_node_id", "").strip(),
                    "relation_label": derive_label(
                        row["edge_relation_id"],
                        row.get("mechanism_description", ""),
                    ),
                    "canonical_statement": row.get("mechanism_description", "").strip(),
                    "relation_type": row.get("relation_type", "").strip(),
                    "default_effect_direction": sign_val,
                    "default_temporal_family": row.get("functional_form", "linear").strip(),
                    "notes": row.get("notes", "").strip(),
                    "version": int(version) if version else 1,
                    "active": int(active) if active else 1,
                }
                conn.execute(insert_sql, params)
                inserted += 1

            logger.info("Inserted %d edge definitions from EDGE_REGISTRY.csv", inserted)
            return inserted
    else:
        logger.info("[DRY RUN] Would insert %d edge definitions", len(rows))
        return len(rows)


# ============================================================================
#  STEP 2: Register studies in study_registry_v1
# ============================================================================
def register_studies(engine, dry_run: bool = False) -> int:
    """Register manually extracted studies, skipping duplicates."""
    registered = 0

    with engine.begin() as conn:
        for study in STUDIES:
            result = conn.execute(
                text("SELECT study_id FROM study_registry_v1 WHERE study_id = :sid"),
                {"sid": study["study_id"]},
            )
            if result.fetchone():
                logger.info("Study %s already exists, skipping", study["study_id"])
                continue

            if dry_run:
                logger.info("[DRY RUN] Would register study %s", study["study_id"])
                registered += 1
                continue

            conn.execute(
                text("""
                    INSERT INTO study_registry_v1 (
                        study_id, title, authors, journal, year, doi,
                        study_design, notes
                    ) VALUES (
                        :study_id, :title, :authors, :journal, :year, :doi,
                        :study_design, :notes
                    )
                """),
                study,
            )
            logger.info("Registered study %s (%s)", study["study_id"], study["doi"])
            registered += 1

    return registered


# ============================================================================
#  STEP 3: Load CSV evidence into edge_evidence_v1
# ============================================================================
def load_csv_evidence(engine, dry_run: bool = False) -> int:
    """Load edge evidence from manual CSV templates into edge_evidence_v1.

    Handles column mapping between CSV template format and DB schema.
    Looks up edge metadata from the (now-reseeded) edge_relations_definitions_v1
    table to populate edge_family, node_x, node_y.
    """
    csv_dir = PROJECT_ROOT / "data" / "manual_uploads" / "structured"
    if not csv_dir.exists():
        logger.warning("No structured CSV directory at %s", csv_dir)
        return 0

    csv_files = sorted(csv_dir.rglob("edge_evidence_template.csv"))
    if not csv_files:
        logger.warning("No edge_evidence_template.csv files found")
        return 0

    # Build edge definition lookup from DB
    edge_defs = {}
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT edge_relation_id, edge_family, node_x, node_y FROM edge_relations_definitions_v1")
        )
        for row in result:
            edge_defs[row[0]] = {
                "edge_family": row[1],
                "node_x": row[2],
                "node_y": row[3],
            }

    logger.info("Loaded %d edge definitions for lookup", len(edge_defs))

    total_loaded = 0
    insert_sql = text("""
        INSERT INTO edge_evidence_v1 (
            ler_id, edge_relation_id, profile_id, study_id,
            edge_family, node_x, node_y,
            effect_type_reported, effect_value_reported, se_reported,
            N_effect, effect_size_type,
            notes, quality_rating, entered_by, entered_at, version, active
        ) VALUES (
            :ler_id, :edge_relation_id, :profile_id, :study_id,
            :edge_family, :node_x, :node_y,
            :effect_type_reported, :effect_value_reported, :se_reported,
            :N_effect, :effect_size_type,
            :notes, :quality_rating, :entered_by, :entered_at, :version, :active
        )
    """)

    with engine.begin() as conn:
        for csv_path in csv_files:
            logger.info("Processing %s", csv_path)

            with open(csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                logger.warning("Empty CSV: %s", csv_path)
                continue

            for row in rows:
                edge_id = row.get("edge_id", "").strip()
                doi = row.get("doi", "").strip()
                study_id = DOI_TO_STUDY.get(doi)

                if not study_id:
                    logger.warning("Unknown DOI %s in %s, skipping row", doi, csv_path)
                    continue

                if not edge_id:
                    logger.warning("Empty edge_id in %s, skipping row", csv_path)
                    continue

                # Look up edge definition
                edge_def = edge_defs.get(edge_id, {})
                if not edge_def:
                    logger.warning(
                        "Edge %s not found in edge_relations_definitions_v1 "
                        "(may not be in EDGE_REGISTRY.csv), proceeding with defaults",
                        edge_id,
                    )

                # Generate unique LER ID
                ler_id = f"LER_{study_id}_{edge_id}_{uuid.uuid4().hex[:8]}"

                # Check if this evidence already exists (avoid duplicates)
                existing = conn.execute(
                    text(
                        "SELECT ler_id FROM edge_evidence_v1 "
                        "WHERE study_id = :sid AND edge_relation_id = :eid"
                    ),
                    {"sid": study_id, "eid": edge_id},
                ).fetchone()

                if existing:
                    logger.info(
                        "Evidence for %s × %s already exists (%s), skipping",
                        study_id, edge_id, existing[0],
                    )
                    continue

                # Map CSV columns to DB columns
                beta_raw = row.get("beta_raw", "").strip()
                se_raw = row.get("se_raw", "").strip()
                sample_size = row.get("sample_size", "").strip()

                params = {
                    "ler_id": ler_id,
                    "edge_relation_id": edge_id,
                    "profile_id": "PROFILE_DEFAULT",
                    "study_id": study_id,
                    "edge_family": edge_def.get("edge_family", "unknown"),
                    "node_x": edge_def.get("node_x", "unknown"),
                    "node_y": edge_def.get("node_y", "unknown"),
                    "effect_type_reported": row.get("effect_type_original", "").strip(),
                    "effect_value_reported": float(beta_raw) if beta_raw else None,
                    "se_reported": float(se_raw) if se_raw else None,
                    "N_effect": int(sample_size) if sample_size else None,
                    "effect_size_type": row.get("effect_size_type", "").strip(),
                    "notes": row.get("confidence_note", "").strip(),
                    "quality_rating": "moderate",  # Default for manually extracted data
                    "entered_by": "manual_csv_import",
                    "entered_at": datetime.utcnow().isoformat(),
                    "version": 1,
                    "active": 1,
                }

                if dry_run:
                    logger.info(
                        "[DRY RUN] Would insert LER %s: %s × %s β=%.3f SE=%.3f n=%s",
                        ler_id, study_id, edge_id,
                        params["effect_value_reported"] or 0,
                        params["se_reported"] or 0,
                        params["N_effect"],
                    )
                else:
                    conn.execute(insert_sql, params)
                    logger.info(
                        "Inserted %s: %s × %s β=%.3f SE=%.3f n=%s",
                        ler_id, study_id, edge_id,
                        params["effect_value_reported"] or 0,
                        params["se_reported"] or 0,
                        params["N_effect"],
                    )

                total_loaded += 1

    return total_loaded


# ============================================================================
#  STEP 4: Clean up old study entries with wrong IDs
# ============================================================================
def cleanup_old_entries(engine, dry_run: bool = False) -> None:
    """Remove the old Cifu 2018 study_registry entry that used inconsistent ID,
    and re-insert with consistent naming."""
    with engine.begin() as conn:
        # Check for old STUDY_CIFU_2018 entry
        result = conn.execute(
            text("SELECT study_id FROM study_registry_v1 WHERE study_id = 'STUDY_CIFU_2018'")
        )
        if result.fetchone():
            if not dry_run:
                conn.execute(
                    text("UPDATE study_registry_v1 SET study_id = 'STUDY_CIFU_2018' WHERE study_id = 'STUDY_CIFU_2018'")
                )
                logger.info("Cifu 2018 entry preserved as STUDY_CIFU_2018")
            else:
                logger.info("[DRY RUN] Would preserve STUDY_CIFU_2018")

        # Also handle old CHERRIER2013 entry if it exists
        result = conn.execute(
            text("SELECT study_id FROM study_registry_v1 WHERE study_id = 'CHERRIER2013'")
        )
        if result.fetchone():
            if not dry_run:
                conn.execute(
                    text("DELETE FROM study_registry_v1 WHERE study_id = 'CHERRIER2013'")
                )
                logger.info("Removed old CHERRIER2013 entry (replaced by STUDY_CHERRIER_2013)")


# ============================================================================
#  STEP 5: Verify final state
# ============================================================================
def verify_state(engine) -> None:
    """Print a summary of the database state after loading."""
    with engine.connect() as conn:
        print()
        print("=" * 70)
        print("  DATABASE STATE AFTER LOADING")
        print("=" * 70)

        # Edge definitions
        result = conn.execute(text("SELECT COUNT(*) FROM edge_relations_definitions_v1"))
        edge_def_count = result.scalar()
        print(f"\n  edge_relations_definitions_v1: {edge_def_count} rows")

        # Study registry
        result = conn.execute(
            text("SELECT study_id, doi, study_design FROM study_registry_v1 ORDER BY study_id")
        )
        studies = result.fetchall()
        print(f"\n  study_registry_v1: {len(studies)} rows")
        for s in studies:
            print(f"    {s[0]:30s} DOI={s[1]} ({s[2]})")

        # Edge evidence
        result = conn.execute(text("SELECT COUNT(*) FROM edge_evidence_v1"))
        evidence_count = result.scalar()
        print(f"\n  edge_evidence_v1: {evidence_count} rows")

        if evidence_count > 0:
            result = conn.execute(
                text("""
                    SELECT ler_id, edge_relation_id, study_id,
                           effect_value_reported, se_reported, N_effect,
                           effect_size_type
                    FROM edge_evidence_v1
                    ORDER BY study_id, edge_relation_id
                """)
            )
            for row in result:
                beta = row[3] if row[3] is not None else 0
                se = row[4] if row[4] is not None else 0
                print(
                    f"    {row[2]:25s} × {row[1]:35s} β={beta:+.3f} SE={se:.3f} n={row[5]} ({row[6]})"
                )

        # Coverage
        result = conn.execute(
            text("""
                SELECT COUNT(DISTINCT edge_relation_id)
                FROM edge_evidence_v1
            """)
        )
        edges_covered = result.scalar()
        print(f"\n  Edge coverage: {edges_covered}/{edge_def_count} edges have evidence")

        # Acquisition queue
        result = conn.execute(text("SELECT COUNT(*) FROM acquisition_queue_v1"))
        queue_count = result.scalar()
        print(f"  Acquisition queue: {queue_count} papers")

        print()
        print("=" * 70)
        if evidence_count > 0:
            print("  ✅ EVIDENCE DATA IS NOW IN THE DATABASE")
        else:
            print("  ❌ NO EVIDENCE LOADED (check errors above)")
        print("=" * 70)


# ============================================================================
#  MAIN
# ============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load manually extracted evidence into the CRCI database",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    print("=" * 70)
    print("  CRCI Phase A: Loading Evidence Into Database")
    print("=" * 70)
    print(f"  Database: {db_url}")
    print(f"  Dry run: {args.dry_run}")
    print()

    engine = init_db()

    # Step 1: Reseed edge definitions
    print("[1/4] Reseeding edge_relations_definitions_v1 from EDGE_REGISTRY.csv...")
    n_edges = reseed_edge_definitions(engine, dry_run=args.dry_run)
    print(f"  → {n_edges} edge definitions loaded")

    # Step 2: Clean up old entries
    print("\n[2/4] Cleaning up old study entries...")
    cleanup_old_entries(engine, dry_run=args.dry_run)

    # Step 3: Register studies
    print("\n[3/4] Registering studies in study_registry_v1...")
    n_studies = register_studies(engine, dry_run=args.dry_run)
    print(f"  → {n_studies} new studies registered")

    # Step 4: Load CSV evidence
    print("\n[4/4] Loading CSV evidence into edge_evidence_v1...")
    n_evidence = load_csv_evidence(engine, dry_run=args.dry_run)
    print(f"  → {n_evidence} evidence rows loaded")

    # Verify
    if not args.dry_run:
        verify_state(engine)

    return 0


if __name__ == "__main__":
    sys.exit(main())
