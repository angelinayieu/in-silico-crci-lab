#!/usr/bin/env python3
"""
Load seed CSVs into the SQLite database.
Creates any missing definition tables first, then imports CSVs.
"""
import csv
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
sys.path.insert(0, str(PROJECT_ROOT))

db_url = os.environ.get("DATABASE_URL") or "sqlite:////workspaces/in-silico-crci-lab/crci_dev.db"
os.environ["DATABASE_URL"] = db_url

from crci.shared.db import init_db
from sqlalchemy import text

engine = init_db()

print("=" * 70)
print("  CRCI Seed Loader — SQLite")
print("=" * 70)
print()

SEEDS_DIR = PROJECT_ROOT / "crci" / "database" / "seeds"

# ── Step 0: Create missing tables ─────────────────────────────────────────

MISSING_TABLES_DDL = [
    (
        "instrument_definitions_v1",
        """
        CREATE TABLE IF NOT EXISTS instrument_definitions_v1 (
            instrument_id                   TEXT        NOT NULL,
            instrument_label                TEXT        NOT NULL,
            maps_to_node_id                 TEXT        NOT NULL,
            instrument_kind                 TEXT        NOT NULL,
            instrument_method               TEXT        NOT NULL,
            recall_window_days              INTEGER,
            time_aggregation                TEXT        NOT NULL,
            raw_scale_spec                  TEXT        NOT NULL,
            raw_unit                        TEXT        NOT NULL,
            higher_means_pre_alignment      TEXT        NOT NULL,
            direction_rule_id               TEXT        NOT NULL,
            directionality_after_alignment  TEXT        NOT NULL,
            adapter_output_kind             TEXT        NOT NULL,
            adapter_spec_id                 TEXT,
            required_fields_json            TEXT        NOT NULL,
            thresholds_json                 TEXT,
            preferred_norm_ref_id           TEXT,
            preferred_noise_id              TEXT,
            compatibility_group_id          TEXT,
            active                          INTEGER     NOT NULL,
            version                         INTEGER     NOT NULL,
            description                     TEXT        NOT NULL,
            notes                           TEXT,
            PRIMARY KEY (instrument_id)
        )
        """,
    ),
    (
        "measure_definitions_v1",
        """
        CREATE TABLE IF NOT EXISTS measure_definitions_v1 (
            measure_id                      TEXT        NOT NULL,
            measure_label                   TEXT        NOT NULL,
            maps_to_node_id                 TEXT        NOT NULL,
            measure_kind                    TEXT        NOT NULL,
            analyte                         TEXT,
            specimen_or_device              TEXT        NOT NULL,
            biospecimen                     TEXT,
            device_type                     TEXT,
            proxy_type                      TEXT        NOT NULL,
            time_aggregation                TEXT        NOT NULL,
            raw_unit                        TEXT        NOT NULL,
            value_transform_spec            TEXT,
            direction_rule_id               TEXT        NOT NULL,
            directionality_after_alignment  TEXT        NOT NULL,
            measure_family_id               TEXT        NOT NULL,
            compatibility_group_id          TEXT        NOT NULL,
            effective_window_days           INTEGER,
            min_required_samples            INTEGER,
            required_fields_json            TEXT        NOT NULL,
            preferred_norm_ref_id           TEXT,
            preferred_noise_id              TEXT,
            active                          INTEGER     NOT NULL,
            version                         INTEGER     NOT NULL,
            description                     TEXT        NOT NULL,
            notes                           TEXT,
            PRIMARY KEY (measure_id)
        )
        """,
    ),
    (
        "pathways_v1",
        """
        CREATE TABLE IF NOT EXISTS pathways_v1 (
            pathway_id                          TEXT        NOT NULL,
            pathway_label                       TEXT        NOT NULL,
            tier                                TEXT        NOT NULL,
            entry_node_ids_json                 TEXT        NOT NULL,
            exit_node_ids_json                  TEXT        NOT NULL,
            intermediate_node_ids_json          TEXT        NOT NULL,
            edge_relation_ids_json              TEXT        NOT NULL,
            cognitive_domain_specificity_json   TEXT        NOT NULL,
            best_proxy_biomarker                TEXT,
            proxy_r_squared                     REAL,
            causal_evidence_level               TEXT        NOT NULL,
            key_citation                        TEXT        NOT NULL,
            version                             INTEGER     NOT NULL,
            active                              INTEGER     NOT NULL,
            notes                               TEXT,
            PRIMARY KEY (pathway_id)
        )
        """,
    ),
]

print("[0/5] Creating missing tables...")
with engine.begin() as conn:
    for tname, ddl in MISSING_TABLES_DDL:
        conn.execute(text(ddl))
        print(f"  ✓ {tname}")
print()

# ── Mapping: CSV file → (table_name, pk_column) ──────────────────────────

SEED_MAP = [
    ("nodes.csv",          "biomarker_node_definitions_v1", "node_id"),
    ("edge_relations.csv", "edge_relations_definitions_v1", "edge_relation_id"),
    ("instruments.csv",    "instrument_definitions_v1",     "instrument_id"),
    ("measures.csv",       "measure_definitions_v1",        "measure_id"),
    ("pathways.csv",       "pathways_v1",                   "pathway_id"),
]


def load_csv_into_table(csv_path: Path, table_name: str, pk_col: str) -> int:
    """Load a CSV into a SQLite table, skipping duplicates. Returns rows inserted."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return 0

    # Get actual table columns from DB
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        db_cols = {r[1] for r in result.fetchall()}

    # Only use CSV columns that exist in the DB table
    csv_cols = list(rows[0].keys())
    valid_cols = [c for c in csv_cols if c in db_cols]
    skipped_cols = [c for c in csv_cols if c not in db_cols]
    if skipped_cols:
        print(f"    ⚠ Skipping CSV columns not in DB: {skipped_cols}")

    col_list = ", ".join(valid_cols)
    param_list = ", ".join(f":{c}" for c in valid_cols)
    insert_sql = text(f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list})")

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            # Check if PK already exists
            result = conn.execute(
                text(f"SELECT 1 FROM {table_name} WHERE {pk_col} = :pk"),
                {"pk": row[pk_col]},
            )
            if result.fetchone():
                continue

            # Filter to valid columns, convert empty strings to None
            params = {}
            for c in valid_cols:
                val = row.get(c, "")
                params[c] = val if val != "" else None
            conn.execute(insert_sql, params)
            inserted += 1

    return inserted


# ── Step 1-5: Load each CSV ──────────────────────────────────────────────

for idx, (csv_name, table_name, pk_col) in enumerate(SEED_MAP, 1):
    csv_path = SEEDS_DIR / csv_name
    print(f"[{idx}/5] Loading {csv_name} → {table_name}...")
    if not csv_path.exists():
        print(f"  ✗ File not found: {csv_path}")
        continue
    count = load_csv_into_table(csv_path, table_name, pk_col)
    print(f"  ✓ {count} rows inserted")
print()

# ── Verify ───────────────────────────────────────────────────────────────

print("Verification:")
with engine.connect() as conn:
    for _, table_name, _ in SEED_MAP:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        n = result.scalar()
        print(f"  {table_name}: {n} rows")

    # Also show study + edge counts
    result = conn.execute(text("SELECT COUNT(*) FROM study_registry_v1"))
    print(f"  study_registry_v1: {result.scalar()} rows")
    result = conn.execute(text("SELECT COUNT(*) FROM edge_evidence_v1"))
    print(f"  edge_evidence_v1: {result.scalar()} rows")

print()
print("=" * 70)
print("✅ ALL SEEDS LOADED")
print("=" * 70)
