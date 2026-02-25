#!/usr/bin/env python3
"""
Generate derivable seed data from the core Class A tables.

This script reads the already-loaded core seeds (nodes, instruments, measures,
edges) and generates:
  1. node_search_terms — search synonyms per node for automated retrieval
  2. observation_noise — default noise parameters per instrument/measure
  3. feedback_loops — feedback cycles detected from edge definitions

Usage:
    python scripts/generate_derived_seeds.py [--verbose]

Prerequisite: Core seeds (nodes, instruments, measures, edges) must be loaded first.
Run: python scripts/setup_database.py --seed
"""
from __future__ import annotations

import logging
import os
import sys
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


# ═══════════════════════════════════════════════════════════════
#  NODE SEARCH TERMS — synonyms, abbreviations, MeSH headings
# ═══════════════════════════════════════════════════════════════

# Hand-curated search terms per node. The query generator uses these
# to build PubMed/Semantic Scholar queries.
NODE_SEARCH_TERMS: dict[str, list[tuple[str, str]]] = {
    # (term, term_type)
    "NODE_SLEEP_QUALITY": [
        ("sleep quality", "primary"),
        ("sleep disturbance", "synonym"),
        ("insomnia", "synonym"),
        ("sleep disruption", "synonym"),
        ("PSQI", "abbreviation"),
        ("Pittsburgh Sleep Quality Index", "synonym"),
        ("sleep disorders", "mesh_heading"),
        ("sleep wake disorders", "mesh_heading"),
    ],
    "NODE_FATIGUE": [
        ("cancer-related fatigue", "primary"),
        ("cancer fatigue", "synonym"),
        ("CRF", "abbreviation"),
        ("FACIT-F", "abbreviation"),
        ("FACIT Fatigue", "synonym"),
        ("Brief Fatigue Inventory", "synonym"),
        ("BFI", "abbreviation"),
        ("fatigue", "mesh_heading"),
    ],
    "NODE_COGNITION": [
        ("cognitive function", "primary"),
        ("cognitive impairment", "synonym"),
        ("chemobrain", "synonym"),
        ("chemo brain", "synonym"),
        ("CRCI", "abbreviation"),
        ("cancer-related cognitive impairment", "synonym"),
        ("chemotherapy-related cognitive dysfunction", "synonym"),
        ("FACT-Cog", "abbreviation"),
        ("cognition disorders", "mesh_heading"),
        ("cognitive dysfunction", "mesh_heading"),
    ],
    "NODE_IL6": [
        ("interleukin-6", "primary"),
        ("IL-6", "abbreviation"),
        ("IL6", "abbreviation"),
        ("serum IL-6", "synonym"),
        ("plasma IL-6", "synonym"),
        ("interleukin 6", "synonym"),
        ("interleukins", "mesh_heading"),
    ],
    "NODE_CRP": [
        ("C-reactive protein", "primary"),
        ("CRP", "abbreviation"),
        ("hs-CRP", "abbreviation"),
        ("high-sensitivity CRP", "synonym"),
        ("C reactive protein", "mesh_heading"),
    ],
    "NODE_TNF_ALPHA": [
        ("tumor necrosis factor alpha", "primary"),
        ("TNF-alpha", "abbreviation"),
        ("TNF-α", "abbreviation"),
        ("TNFa", "abbreviation"),
        ("tumor necrosis factor-alpha", "mesh_heading"),
    ],
    "NODE_CORTISOL": [
        ("cortisol", "primary"),
        ("salivary cortisol", "synonym"),
        ("diurnal cortisol", "synonym"),
        ("cortisol slope", "synonym"),
        ("cortisol awakening response", "synonym"),
        ("CAR", "abbreviation"),
        ("HPA axis", "synonym"),
        ("hydrocortisone", "mesh_heading"),
    ],
    "NODE_BDNF": [
        ("brain-derived neurotrophic factor", "primary"),
        ("BDNF", "abbreviation"),
        ("serum BDNF", "synonym"),
        ("plasma BDNF", "synonym"),
        ("brain derived neurotrophic factor", "mesh_heading"),
    ],
    "NODE_EXERCISE": [
        ("physical activity", "primary"),
        ("exercise", "synonym"),
        ("aerobic exercise", "synonym"),
        ("resistance training", "synonym"),
        ("IPAQ", "abbreviation"),
        ("accelerometry", "synonym"),
        ("exercise", "mesh_heading"),
        ("motor activity", "mesh_heading"),
    ],
    "NODE_HRV": [
        ("heart rate variability", "primary"),
        ("HRV", "abbreviation"),
        ("RMSSD", "abbreviation"),
        ("vagal tone", "synonym"),
        ("autonomic function", "synonym"),
        ("heart rate determination", "mesh_heading"),
    ],
    "NODE_DEPRESSION": [
        ("depression", "primary"),
        ("depressive symptoms", "synonym"),
        ("PHQ-9", "abbreviation"),
        ("CES-D", "abbreviation"),
        ("major depressive disorder", "synonym"),
        ("depressive disorder", "mesh_heading"),
    ],
    "NODE_ATTENTION": [
        ("attention", "primary"),
        ("concentration", "synonym"),
        ("sustained attention", "synonym"),
        ("selective attention", "synonym"),
        ("attentional function", "synonym"),
        ("attention deficit", "synonym"),
    ],
    "NODE_MEMORY": [
        ("memory", "primary"),
        ("verbal memory", "synonym"),
        ("episodic memory", "synonym"),
        ("working memory", "synonym"),
        ("HVLT-R", "abbreviation"),
        ("Hopkins Verbal Learning Test", "synonym"),
        ("memory disorders", "mesh_heading"),
    ],
    "NODE_EXEC_FUNCTION": [
        ("executive function", "primary"),
        ("executive functioning", "synonym"),
        ("cognitive flexibility", "synonym"),
        ("Trail Making Test", "synonym"),
        ("TMT-B", "abbreviation"),
        ("set shifting", "synonym"),
        ("executive function", "mesh_heading"),
    ],
    "NODE_PROCESSING_SPEED": [
        ("processing speed", "primary"),
        ("information processing speed", "synonym"),
        ("DSST", "abbreviation"),
        ("Digit Symbol Substitution", "synonym"),
        ("reaction time", "synonym"),
        ("psychomotor speed", "synonym"),
    ],
    "NODE_ANXIETY": [
        ("anxiety", "primary"),
        ("anxiety symptoms", "synonym"),
        ("GAD-7", "abbreviation"),
        ("generalized anxiety", "synonym"),
        ("cancer anxiety", "synonym"),
        ("anxiety disorders", "mesh_heading"),
    ],
    "NODE_PAIN": [
        ("pain", "primary"),
        ("cancer pain", "synonym"),
        ("BPI", "abbreviation"),
        ("Brief Pain Inventory", "synonym"),
        ("pain severity", "synonym"),
        ("cancer pain", "mesh_heading"),
    ],
    "NODE_CHEMO_EXPOSURE": [
        ("chemotherapy", "primary"),
        ("cytotoxic chemotherapy", "synonym"),
        ("anthracycline", "synonym"),
        ("taxane", "synonym"),
        ("antineoplastic agents", "mesh_heading"),
    ],
    "NODE_AGE": [
        ("age", "primary"),
        ("chronological age", "synonym"),
    ],
    "NODE_MENOPAUSAL_STATUS": [
        ("menopause", "primary"),
        ("menopausal status", "synonym"),
        ("postmenopausal", "synonym"),
        ("premature menopause", "synonym"),
        ("menopause", "mesh_heading"),
    ],
}


# ═══════════════════════════════════════════════════════════════
#  OBSERVATION NOISE — default σ² per instrument/measure
# ═══════════════════════════════════════════════════════════════

# Derived from published psychometric properties.
# noise_variance = 1 - reliability_alpha (for questionnaires)
# or estimated from test-retest ICC.
OBSERVATION_NOISE_DEFAULTS: list[dict] = [
    {
        "noise_id": "NOISE_PSQI",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_PSQI",
        "reliability_alpha": 0.83,
        "noise_variance": 0.17,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Buysse et al. 1989; Carpenter & Andrykowski 1998",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_FACIT_F",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_FACIT_F",
        "reliability_alpha": 0.95,
        "noise_variance": 0.05,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Yellen et al. 1997; Cella et al. 2002",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_BFI",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_BFI",
        "reliability_alpha": 0.96,
        "noise_variance": 0.04,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Mendoza et al. 1999",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_FACT_COG",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_FACT_COG",
        "reliability_alpha": 0.92,
        "noise_variance": 0.08,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Wagner et al. 2009",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_TRAIL_B",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_TRAIL_B",
        "reliability_alpha": 0.89,
        "noise_variance": 0.11,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Strauss et al. 2006",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.15 for general_population validation",
    },
    {
        "noise_id": "NOISE_HVLT_R",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_HVLT_R",
        "reliability_alpha": 0.74,
        "noise_variance": 0.26,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Brandt & Benedict 2001",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.15 for general_population; alternate forms available",
    },
    {
        "noise_id": "NOISE_PHQ9",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_PHQ9",
        "reliability_alpha": 0.89,
        "noise_variance": 0.11,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Kroenke et al. 2001",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_GAD7",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_GAD7",
        "reliability_alpha": 0.92,
        "noise_variance": 0.08,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Spitzer et al. 2006",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_DSST",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_DSST",
        "reliability_alpha": 0.82,
        "noise_variance": 0.18,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Wechsler 2008 (WAIS-IV manual)",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_IL6_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_IL6_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.30,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "Estimated from assay CV and biological variability",
        "condition_dependent": 1,
        "condition_description": "High intra-individual variability; single timepoint unreliable",
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.3 for estimated noise source",
    },
    {
        "noise_id": "NOISE_CRP_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_CRP_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.25,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "Estimated from assay CV and biological variability",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_CORTISOL_SALIVA",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_CORTISOL_SALIVA",
        "reliability_alpha": None,
        "noise_variance": 0.35,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "High diurnal and day-to-day variability; Adam & Kumari 2009",
        "condition_dependent": 1,
        "condition_description": "Requires multiple daily samples over multiple days",
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_BDNF_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_BDNF_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.35,
        "noise_source": "estimated",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.3,
        "source_citation": "High platelet-bound fraction; Lommatzsch et al. 2005",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "Serum BDNF strongly affected by platelet count and handling",
    },
]


# ═══════════════════════════════════════════════════════════════
#  FEEDBACK LOOPS — cycles in the edge graph
# ═══════════════════════════════════════════════════════════════

FEEDBACK_LOOPS: list[dict] = [
    {
        "loop_id": "LOOP_SLEEP_IL6",
        "loop_label": "Sleep-Inflammation Bidirectional Loop",
        "edge_relation_ids_json": '["EDGE_SLEEP_IL6", "EDGE_IL6_SLEEP"]',
        "node_ids_json": '["NODE_SLEEP_QUALITY", "NODE_IL6"]',
        "loop_gain": 0.3,
        "characteristic_period_weeks": "2-4",
        "forward_dynamics": "Poor sleep activates NF-kB, elevating IL-6 within days",
        "reverse_dynamics": "Elevated IL-6 fragments sleep via prostaglandin-mediated mechanisms",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.15,
        "version": 1,
        "notes": "Well-established bidirectional relationship; Irwin 2015",
    },
    {
        "loop_id": "LOOP_FATIGUE_SLEEP",
        "loop_label": "Fatigue-Sleep Disruption Loop",
        "edge_relation_ids_json": '["EDGE_SLEEP_FATIGUE", "EDGE_FATIGUE_COGNITION"]',
        "node_ids_json": '["NODE_SLEEP_QUALITY", "NODE_FATIGUE", "NODE_COGNITION"]',
        "loop_gain": 0.25,
        "characteristic_period_weeks": "1-2",
        "forward_dynamics": "Poor sleep causes daytime fatigue and cognitive impairment",
        "reverse_dynamics": "Fatigue leads to daytime napping disrupting nighttime sleep",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.10,
        "version": 1,
        "notes": "Clinical cycle commonly observed in cancer survivors",
    },
    {
        "loop_id": "LOOP_DEPRESSION_FATIGUE",
        "loop_label": "Depression-Fatigue Bidirectional Loop",
        "edge_relation_ids_json": '["EDGE_DEPRESSION_FATIGUE"]',
        "node_ids_json": '["NODE_DEPRESSION", "NODE_FATIGUE"]',
        "loop_gain": 0.35,
        "characteristic_period_weeks": "4-8",
        "forward_dynamics": "Depressive symptoms amplify fatigue perception and reduce motivation",
        "reverse_dynamics": "Persistent fatigue triggers hopelessness and anhedonia",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.12,
        "version": 1,
        "notes": "Shared serotonergic and inflammatory mechanisms; Brown & Kroenke 2009",
    },
]


def generate_search_terms(session) -> int:
    """Insert node_search_terms rows from the curated dictionary."""
    count = 0
    for node_id, terms in NODE_SEARCH_TERMS.items():
        for term_text, term_type in terms:
            # Check if exists
            existing = session.execute(
                text(
                    "SELECT 1 FROM node_search_terms_v1 "
                    "WHERE node_id = :nid AND term = :t"
                ),
                {"nid": node_id, "t": term_text},
            ).first()
            if existing:
                continue
            session.execute(
                text(
                    "INSERT INTO node_search_terms_v1 (node_id, term, term_type, active) "
                    "VALUES (:nid, :t, :tt, 1)"
                ),
                {"nid": node_id, "t": term_text, "tt": term_type},
            )
            count += 1
    return count


def generate_observation_noise(session) -> int:
    """Insert observation_noise rows from psychometric defaults."""
    count = 0
    for noise in OBSERVATION_NOISE_DEFAULTS:
        existing = session.execute(
            text("SELECT 1 FROM observation_noise_v1 WHERE noise_id = :nid"),
            {"nid": noise["noise_id"]},
        ).first()
        if existing:
            continue

        cols = [k for k in noise.keys() if noise[k] is not None]
        placeholders = [f":{k}" for k in cols]
        session.execute(
            text(
                f"INSERT INTO observation_noise_v1({', '.join(cols)}) "
                f"VALUES ({', '.join(placeholders)})"
            ),
            {k: noise[k] for k in cols},
        )
        count += 1
    return count


def generate_feedback_loops(session) -> int:
    """Insert feedback_loop rows from edge analysis."""
    count = 0
    for loop in FEEDBACK_LOOPS:
        existing = session.execute(
            text("SELECT 1 FROM feedback_loops_v1 WHERE loop_id = :lid"),
            {"lid": loop["loop_id"]},
        ).first()
        if existing:
            continue

        cols = [k for k in loop.keys() if loop[k] is not None]
        placeholders = [f":{k}" for k in cols]
        session.execute(
            text(
                f"INSERT INTO feedback_loops_v1({', '.join(cols)}) "
                f"VALUES ({', '.join(placeholders)})"
            ),
            {k: loop[k] for k in cols},
        )
        count += 1
    return count


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate derived seed data from core Class A tables",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    init_db()

    print("\n--- Generating derived seed data ---\n")

    with get_session() as session:
        # 1. Node search terms
        terms_count = generate_search_terms(session)
        print(f"  Node search terms:    {terms_count} rows inserted")

        # 2. Observation noise
        noise_count = generate_observation_noise(session)
        print(f"  Observation noise:    {noise_count} rows inserted")

        # 3. Feedback loops
        loops_count = generate_feedback_loops(session)
        print(f"  Feedback loops:       {loops_count} rows inserted")

    total = terms_count + noise_count + loops_count
    print(f"\nTotal derived rows: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
