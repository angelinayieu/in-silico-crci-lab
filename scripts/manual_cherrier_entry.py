#!/usr/bin/env python3
"""
Manual data entry script for Cherrier 2013 paper.
Populates CRCI SQLite tables with extracted evidence.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
sys.path.insert(0, str(PROJECT_ROOT))

# Prefer explicit env var, fallback to local SQLite db.
db_url = os.environ.get("DATABASE_URL") or "sqlite:////workspaces/in-silico-crci-lab/crci_dev.db"
os.environ["DATABASE_URL"] = db_url
print(f"Using database: {db_url}")

from crci.shared.db import init_db
from sqlalchemy import text

STUDY_ID = "CHERRIER2013"

print("=" * 70)
print("  CRCI Manual Data Entry: Cherrier 2013")
print("=" * 70)
print()

# Initialize database
engine = init_db()
print("✓ Database connected")
print()

# ============================================================================
#  STEP 1: Insert Study Registry Entry
# ============================================================================
print("[1/3] Creating study registry entry...")

study_data = {
    "study_id": STUDY_ID,
    "title": "A randomized trial of cognitive rehabilitation in cancer survivors",
    "authors": "Cherrier MM; Anderson K; David D; Higano CS; Gray H; Church A; Willis SL",
    "journal": "Life Sciences",
    "year": 2013,
    "doi": "10.1016/j.lfs.2013.08.011",
    "study_design": "RCT",
    "notes": "Cancer survivors; wait-list control; n=28; primary outcome Digit Span",
}

with engine.begin() as conn:
    result = conn.execute(
        text("SELECT study_id FROM study_registry_v1 WHERE study_id = :sid"),
        {"sid": study_data["study_id"]},
    )
    exists = result.fetchone()

    if not exists:
        conn.execute(
            text(
                """
                INSERT INTO study_registry_v1 (
                    study_id, title, authors, journal, year, doi, study_design, notes
                ) VALUES (
                    :study_id, :title, :authors, :journal, :year, :doi, :study_design, :notes
                )
                """
            ),
            study_data,
        )
        print(f"  ✓ Study {study_data['study_id']} registered")
    else:
        print(f"  ⊙ Study {study_data['study_id']} already exists")

# ============================================================================
#  STEP 2: Insert Edge Evidence
# ============================================================================
print()
print("[2/3] Creating edge evidence...")

edges = [
    {
        "ler_id": "LER_CHERRIER2013_ATTENTION",
        "edge_relation_id": "ER_COGREHAB_ATTENTION",
        "profile_id": "PROFILE_DEFAULT",
        "study_id": STUDY_ID,
        "edge_family": "intervention_to_cognition",
        "node_x": "CognitiveRehabilitation",
        "node_y": "Attention",
        "effect_type_reported": "cohens_d",
        "effect_value_reported": 0.59,
        "se_reported": 0.25,
        "ci_low_reported": 0.10,
        "ci_high_reported": 1.08,
        "p_value": 0.01,
        "N_effect": 28,
        "notes": "Digit Span total; net change 2.3 points; MANOVA-adjusted p<0.01",
        "quality_rating": "moderate",
        "rob_overall": "moderate",
    },
    {
        "ler_id": "LER_CHERRIER2013_WORKING_MEMORY",
        "edge_relation_id": "ER_COGREHAB_WORKING_MEMORY",
        "profile_id": "PROFILE_DEFAULT",
        "study_id": STUDY_ID,
        "edge_family": "intervention_to_cognition",
        "node_x": "CognitiveRehabilitation",
        "node_y": "WorkingMemory",
        "effect_type_reported": "cohens_d",
        "effect_value_reported": 0.52,
        "se_reported": 0.26,
        "ci_low_reported": 0.01,
        "ci_high_reported": 1.03,
        "p_value": 0.01,
        "N_effect": 28,
        "notes": "Digit Span backward; working memory component",
        "quality_rating": "moderate",
        "rob_overall": "moderate",
    },
    {
        "ler_id": "LER_CHERRIER2013_COG_QOL",
        "edge_relation_id": "ER_COGREHAB_COG_QOL",
        "profile_id": "PROFILE_DEFAULT",
        "study_id": STUDY_ID,
        "edge_family": "intervention_to_cognition",
        "node_x": "CognitiveRehabilitation",
        "node_y": "CognitiveQualityOfLife",
        "effect_type_reported": "cohens_d",
        "effect_value_reported": 0.75,
        "se_reported": 0.28,
        "ci_low_reported": 0.20,
        "ci_high_reported": 1.30,
        "p_value": 0.01,
        "N_effect": 28,
        "notes": "FACT-Cog PCI; subjective measure; wait-list expectancy risk",
        "quality_rating": "moderate",
        "rob_overall": "moderate",
    },
]

insert_edge_sql = text(
    """
    INSERT INTO edge_evidence_v1 (
        ler_id, edge_relation_id, profile_id, study_id, edge_family, node_x, node_y,
        effect_type_reported, effect_value_reported, se_reported, ci_low_reported,
        ci_high_reported, p_value, N_effect, notes, quality_rating, rob_overall
    ) VALUES (
        :ler_id, :edge_relation_id, :profile_id, :study_id, :edge_family, :node_x, :node_y,
        :effect_type_reported, :effect_value_reported, :se_reported, :ci_low_reported,
        :ci_high_reported, :p_value, :N_effect, :notes, :quality_rating, :rob_overall
    )
    """
)

with engine.begin() as conn:
    for edge in edges:
        result = conn.execute(
            text("SELECT ler_id FROM edge_evidence_v1 WHERE ler_id = :ler_id"),
            {"ler_id": edge["ler_id"]},
        )
        exists = result.fetchone()

        if not exists:
            conn.execute(insert_edge_sql, edge)
            print(f"  ✓ Edge {edge['ler_id']} created")
        else:
            print(f"  ⊙ Edge {edge['ler_id']} already exists")

# ============================================================================
#  STEP 3: Verify Data Entry
# ============================================================================
print()
print("[3/3] Verifying data entry...")

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT COUNT(*) FROM study_registry_v1 WHERE study_id = :sid"),
        {"sid": STUDY_ID},
    )
    study_count = result.scalar()

    result = conn.execute(
        text("SELECT COUNT(*) FROM edge_evidence_v1 WHERE study_id = :sid"),
        {"sid": STUDY_ID},
    )
    edge_count = result.scalar()

    print(f"  ✓ Studies registered: {study_count}")
    print(f"  ✓ Edges created: {edge_count}")

print()
print("=" * 70)
print("✅ DATA ENTRY COMPLETE")
print()
print("Your Cherrier 2013 extraction is now in the database!")
print()
print("Next steps:")
print("  1. View data: sqlite3 crci_dev.db 'SELECT * FROM edge_evidence_v1;' ")
print("  2. Add more papers using this same template")
print("  3. Once you have 5-10 papers, run meta-analysis")
print("  4. Build the full Bayesian causal model")
print("=" * 70)
