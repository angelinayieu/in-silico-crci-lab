#!/usr/bin/env python3
"""
Phase A: Get evidence data into the database.

This is the CANONICAL manual-import entry point. When you extract a paper
from PDF into CSVs under data/manual_uploads/structured/<doi-slug>/, run
this script to load everything into the DB and compile edges_v1.

Steps performed:
  A1. Reseed edge_relations_definitions_v1 from authoritative EDGE_REGISTRY.csv
  A2. Clean up legacy study entries
  A3. Register studies in study_registry_v1  (auto-discovers from DOI→study map)
  A4. Load CSV evidence → edge_evidence_v1   (populates BOTH raw AND harmonized columns)
  A4b. Load auxiliary family CSVs → node_priors_v1, instrument_evidence_v1,
       population_norms_v1, temporal_evidence_v1
  A4c. Harmonize scales: mean_diff_raw → cohens_d (SD borrowing)
  A4d. Apply 7-layer SE_eff calibration (Formula P3-8, Gate P3-G1)
  A5. Seed action_catalog_v1                  (from seeds/actions.csv)
  A6. Compile evidence → edges_v1             (IVW aggregation per edge)
  A7. Verify final state

Supports two CSV formats:
  - 12-column minimal: doi,edge_id,beta_raw,se_raw,...,confidence_note
  - 32-column extended: adds ci_low,ci_high,p_value,...,outcome_node_id

Usage:
    python scripts/load_evidence_into_db.py
    python scripts/load_evidence_into_db.py --dry-run
    python scripts/load_evidence_into_db.py --verbose
    python scripts/load_evidence_into_db.py --reset   # wipe evidence + edges first
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure DATABASE_URL
db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{PROJECT_ROOT}/crci_dev.db"
os.environ["DATABASE_URL"] = db_url

from sqlalchemy import text

from crci.shared.db import init_db, get_session
from crci.extraction.family_importers import (
    import_context_prior,
    import_correlation,
    import_dose_evidence,
    import_instrument_evidence,
    import_ontology_link,
    import_population_norm,
    import_profile_data_stream,
    import_stream_timepoint,
    import_study_cohort_profile,
    import_subgroup_evidence,
    import_temporal_evidence,
)

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
    {
        "study_id": "STUDY_NORTHEY_2018",
        "title": "Cognition in breast cancer survivors: A pilot study of interval and continuous exercise",
        "authors": "Northey JM; Pumpa KL; Quinlan C; Ikin A; Toohey K; Smee DJ; Rattray B",
        "journal": "Journal of Science and Medicine in Sport",
        "year": 2018,
        "doi": "10.1016/j.jsams.2018.11.026",
        "study_design": "RCT",
        "notes": "Breast cancer survivors; 3-arm pilot RCT: HIIT vs MOD vs CON; n=17; 12-week cycle ergometer; CogState battery",
    },
    {
        "study_id": "STUDY_ADAM_2017",
        "title": "Diurnal Cortisol Slopes and Mental and Physical Health Outcomes: "
                 "A Systematic Review and Meta-analysis",
        "authors": "Adam EK; Quinn ME; Tavernier R; McQuillan MT; Dahlke KA; Gilbert KE",
        "journal": "Psychoneuroendocrinology",
        "year": 2017,
        "doi": "10.1016/j.psyneuen.2017.05.018",
        "study_design": "systematic_review",
        "notes": "Meta-analysis of 80 studies (k=179, N=36823). DCS↔health outcomes. "
                 "Subgroups: inflammation r=.288, depression r=.106, fatigue r=.167, anxiety r=-.084 (NS). "
                 "Overall r=.147. Cross-sectional=91.1%. I²=83.23%.",
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
    "10.1016/j.jsams.2018.11.026": "STUDY_NORTHEY_2018",
    "10.1016/j.psyneuen.2017.05.018": "STUDY_ADAM_2017",
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
#  STEP 1b: Reseed biomarker_node_definitions_v1 and instrument_definitions_v1
#           from authoritative registries
# ============================================================================
def reseed_node_and_instrument_definitions(engine, dry_run: bool = False) -> tuple[int, int]:
    """Reseed biomarker_node_definitions_v1 from NODE_REGISTRY.csv and
    instrument_definitions_v1 from INSTRUMENT_REGISTRY.csv.

    The registries are the authoritative source with fine-grained IDs
    (e.g., NODE_COG_PROC_SPEED, INST_TMT_B) that match the manual CSV data.
    The coarse seed data (nodes.csv, instruments.csv) uses different IDs.

    Returns:
        Tuple of (nodes_loaded, instruments_loaded).
    """
    node_registry = PROJECT_ROOT / "registries" / "NODE_REGISTRY.csv"
    inst_registry = PROJECT_ROOT / "registries" / "INSTRUMENT_REGISTRY.csv"

    nodes_loaded = 0
    instruments_loaded = 0

    # ---- Reseed nodes ----
    if node_registry.exists():
        with open(node_registry, "r") as f:
            reader = csv.DictReader(f)
            node_rows = list(reader)

        logger.info("Read %d nodes from NODE_REGISTRY.csv", len(node_rows))

        # Map NODE_REGISTRY.csv columns → biomarker_node_definitions_v1 columns
        # node_layer → orientation mapping
        layer_to_role = {
            "0": "exogenous",
            "1": "behavioral",
            "2": "biomarker",
            "3": "pathway",
            "4": "cognitive_outcome",
            "5": "symptom_outcome",
        }

        if not dry_run:
            with engine.begin() as conn:
                # Clear existing nodes
                result = conn.execute(text("DELETE FROM biomarker_node_definitions_v1"))
                logger.info("Cleared %d existing node rows", result.rowcount)

                insert_sql = text("""
                    INSERT OR IGNORE INTO biomarker_node_definitions_v1 (
                        node_id, node_label, node_role, orientation,
                        node_domain, default_state_space, state_update_scale,
                        allowed_source_types_json,
                        is_actionable_input_node, active, version,
                        description
                    ) VALUES (
                        :node_id, :node_label, :node_role, :orientation,
                        :node_domain, :default_state_space, :state_update_scale,
                        :allowed_source_types_json,
                        :is_actionable_input_node, :active, :version,
                        :description
                    )
                """)

                for row in node_rows:
                    node_id = row.get("node_id", "").strip()
                    if not node_id:
                        continue

                    layer = row.get("node_layer", "").strip()
                    is_actionable = 1 if layer in ("0", "1") else 0

                    params = {
                        "node_id": node_id,
                        "node_label": row.get("node_label", "").strip() or node_id,
                        "node_role": layer_to_role.get(layer, "unknown"),
                        "orientation": row.get("orientation", "").strip() or "HIGHER_BETTER",
                        "node_domain": row.get("clinical_domain", "").strip() or "general",
                        "default_state_space": row.get("unit_of_measure", "z").strip() or "z",
                        "state_update_scale": "z",
                        "allowed_source_types_json": '["instrument", "measure"]',
                        "is_actionable_input_node": is_actionable,
                        "active": int(row.get("active", 1)),
                        "version": int(row.get("version", 1)),
                        "description": row.get("description", "").strip() or node_id,
                    }
                    conn.execute(insert_sql, params)
                    nodes_loaded += 1

                logger.info("Inserted %d node definitions from NODE_REGISTRY.csv", nodes_loaded)
        else:
            nodes_loaded = len(node_rows)
            logger.info("[DRY RUN] Would insert %d node definitions", nodes_loaded)
    else:
        logger.warning("NODE_REGISTRY.csv not found at %s", node_registry)

    # ---- Reseed instruments ----
    if inst_registry.exists():
        with open(inst_registry, "r") as f:
            reader = csv.DictReader(f)
            inst_rows = list(reader)

        logger.info("Read %d instruments from INSTRUMENT_REGISTRY.csv", len(inst_rows))

        if not dry_run:
            with engine.begin() as conn:
                # Clear existing instruments
                result = conn.execute(text("DELETE FROM instrument_definitions_v1"))
                logger.info("Cleared %d existing instrument rows", result.rowcount)

                insert_sql = text("""
                    INSERT OR IGNORE INTO instrument_definitions_v1 (
                        instrument_id, instrument_label, maps_to_node_id,
                        instrument_kind, instrument_method,
                        time_aggregation, raw_scale_spec,
                        raw_unit, higher_means_pre_alignment,
                        direction_rule_id, directionality_after_alignment,
                        adapter_output_kind, required_fields_json,
                        active, version, description
                    ) VALUES (
                        :instrument_id, :instrument_label, :maps_to_node_id,
                        :instrument_kind, :instrument_method,
                        :time_aggregation, :raw_scale_spec,
                        :raw_unit, :higher_means_pre_alignment,
                        :direction_rule_id, :directionality_after_alignment,
                        :adapter_output_kind, :required_fields_json,
                        :active, :version, :description
                    )
                """)

                for row in inst_rows:
                    inst_id = row.get("instrument_id", "").strip()
                    if not inst_id:
                        continue

                    scoring_dir = row.get("scoring_direction", "").strip() or "higher_better"
                    inst_type = row.get("instrument_type", "").strip() or "unknown"
                    admin_mode = row.get("administration_mode", "").strip() or "unknown"

                    # Build raw_scale_spec from min/max if available
                    scale_min = row.get("total_score_range_min", "").strip() or "0"
                    scale_max = row.get("total_score_range_max", "").strip() or "100"
                    raw_scale_spec = f"{scale_min}-{scale_max}"

                    # Direction rule from scoring_direction
                    if scoring_dir == "higher_better":
                        dir_rule = "DIR_POSITIVE"
                        dir_post = "higher_better"
                    elif scoring_dir == "lower_better":
                        dir_rule = "DIR_REVERSE"
                        dir_post = "higher_worse"
                    else:
                        dir_rule = "DIR_POSITIVE"
                        dir_post = "higher_better"

                    params = {
                        "instrument_id": inst_id,
                        "instrument_label": row.get("instrument_name", "").strip() or inst_id,
                        "maps_to_node_id": row.get("maps_to_node_id", "").strip() or "NODE_COMP_CRCI",
                        "instrument_kind": inst_type,
                        "instrument_method": admin_mode,
                        "time_aggregation": row.get("time_window_days", "").strip() or "study_window",
                        "raw_scale_spec": raw_scale_spec,
                        "raw_unit": row.get("response_type", "").strip() or "score",
                        "higher_means_pre_alignment": scoring_dir,
                        "direction_rule_id": dir_rule,
                        "directionality_after_alignment": dir_post,
                        "adapter_output_kind": "z",
                        "required_fields_json": row.get("required_fields_json", "").strip() or '{"total_score": "required"}',
                        "active": int(row.get("active", 1)),
                        "version": 1,
                        "description": row.get("notes", "").strip() or inst_id,
                    }
                    conn.execute(insert_sql, params)
                    instruments_loaded += 1

                logger.info("Inserted %d instrument definitions from INSTRUMENT_REGISTRY.csv", instruments_loaded)
        else:
            instruments_loaded = len(inst_rows)
            logger.info("[DRY RUN] Would insert %d instrument definitions", instruments_loaded)
    else:
        logger.warning("INSTRUMENT_REGISTRY.csv not found at %s", inst_registry)

    return nodes_loaded, instruments_loaded


# ============================================================================
#  STEP 1c: Reseed measure_definitions_v1 and pathways_v1
#           from authoritative registries
# ============================================================================
def reseed_measure_and_pathway_definitions(engine, dry_run: bool = False) -> tuple[int, int]:
    """Reseed measure_definitions_v1 from MEASURE_REGISTRY.csv and
    pathways_v1 from PATHWAY_REGISTRY.csv.

    The registries contain fine-grained columns (cancer_validation_status,
    se_multiplier, mcid, etc.) that the seed CSVs lack.  Column mapping
    adapts registry names → DB schema names.

    Returns:
        Tuple of (measures_loaded, pathways_loaded).
    """
    measure_registry = PROJECT_ROOT / "registries" / "MEASURE_REGISTRY.csv"
    pathway_registry = PROJECT_ROOT / "registries" / "PATHWAY_REGISTRY.csv"

    measures_loaded = 0
    pathways_loaded = 0

    # ---- Reseed measures ----
    if measure_registry.exists():
        with open(measure_registry, "r") as f:
            reader = csv.DictReader(f)
            measure_rows = list(reader)

        logger.info("Read %d measures from MEASURE_REGISTRY.csv", len(measure_rows))

        if not dry_run:
            with engine.begin() as conn:
                result = conn.execute(text("DELETE FROM measure_definitions_v1"))
                logger.info("Cleared %d existing measure rows", result.rowcount)

                insert_sql = text("""
                    INSERT OR IGNORE INTO measure_definitions_v1 (
                        measure_id, measure_label, maps_to_node_id,
                        measure_kind, analyte, specimen_or_device,
                        biospecimen, device_type, proxy_type,
                        time_aggregation, raw_unit, value_transform_spec,
                        direction_rule_id, directionality_after_alignment,
                        measure_family_id, compatibility_group_id,
                        effective_window_days, min_required_samples,
                        required_fields_json,
                        preferred_norm_ref_id, preferred_noise_id,
                        active, version, description, notes
                    ) VALUES (
                        :measure_id, :measure_label, :maps_to_node_id,
                        :measure_kind, :analyte, :specimen_or_device,
                        :biospecimen, :device_type, :proxy_type,
                        :time_aggregation, :raw_unit, :value_transform_spec,
                        :direction_rule_id, :directionality_after_alignment,
                        :measure_family_id, :compatibility_group_id,
                        :effective_window_days, :min_required_samples,
                        :required_fields_json,
                        :preferred_norm_ref_id, :preferred_noise_id,
                        :active, :version, :description, :notes
                    )
                """)

                for row in measure_rows:
                    mid = row.get("measure_id", "").strip()
                    if not mid:
                        continue

                    scoring_dir = row.get("scoring_direction", "").strip() or "higher_better"
                    if scoring_dir == "higher_better":
                        dir_rule = "DIR_POSITIVE"
                        dir_post = "higher_better"
                    elif scoring_dir == "lower_better":
                        dir_rule = "DIR_REVERSE"
                        dir_post = "higher_worse"
                    else:
                        dir_rule = "DIR_POSITIVE"
                        dir_post = "higher_better"

                    mtype = row.get("measure_type", "").strip() or "total_score"
                    assay = row.get("assay_method", "").strip() or ""
                    sample = row.get("sample_type", "").strip() or ""

                    # Derive measure_kind from measure_type
                    kind_map = {
                        "total_score": "total_score",
                        "subscale": "subscale",
                        "single_item": "single_item",
                        "biomarker": "biomarker",
                        "composite": "composite",
                        "performance": "performance_metric",
                    }
                    measure_kind = kind_map.get(mtype, mtype)

                    # Derive specimen/device from assay_method + sample_type
                    if assay and assay != "N/A":
                        specimen_or_device = assay
                    elif sample and sample != "N/A":
                        specimen_or_device = sample
                    else:
                        specimen_or_device = "questionnaire"

                    # Build required_fields_json
                    req_fields = row.get("alternative_measure_ids_json", "").strip()
                    if not req_fields or req_fields == "N/A":
                        req_fields = '{"total_score": "required"}'

                    time_res = row.get("time_resolution_days", "").strip() or "30"
                    try:
                        eff_window = int(float(time_res))
                    except (ValueError, TypeError):
                        eff_window = 30

                    params = {
                        "measure_id": mid,
                        "measure_label": row.get("measure_name", "").strip() or mid,
                        "maps_to_node_id": row.get("maps_to_node_id", "").strip() or "NODE_COMP_CRCI",
                        "measure_kind": measure_kind,
                        "analyte": assay if assay != "N/A" else "",
                        "specimen_or_device": specimen_or_device,
                        "biospecimen": sample if sample != "N/A" else "",
                        "device_type": "",
                        "proxy_type": "direct",
                        "time_aggregation": row.get("aggregation_method", "").strip() or "mean",
                        "raw_unit": row.get("unit_of_measure", "").strip() or "score",
                        "value_transform_spec": "",
                        "direction_rule_id": dir_rule,
                        "directionality_after_alignment": dir_post,
                        "measure_family_id": row.get("parent_instrument_id", "").strip() or mid,
                        "compatibility_group_id": row.get("tier_assignment", "").strip() or "0",
                        "effective_window_days": eff_window,
                        "min_required_samples": 1,
                        "required_fields_json": req_fields,
                        "preferred_norm_ref_id": row.get("norm_id", "").strip() or None,
                        "preferred_noise_id": row.get("noise_id", "").strip() or None,
                        "active": int(row.get("active", 1)),
                        "version": 1,
                        "description": row.get("measure_short", "").strip() or mid,
                        "notes": row.get("notes", "").strip() or "",
                    }
                    conn.execute(insert_sql, params)
                    measures_loaded += 1

                logger.info("Inserted %d measure definitions from MEASURE_REGISTRY.csv", measures_loaded)
        else:
            measures_loaded = len(measure_rows)
            logger.info("[DRY RUN] Would insert %d measure definitions", measures_loaded)
    else:
        logger.warning("MEASURE_REGISTRY.csv not found at %s", measure_registry)

    # ---- Reseed pathways ----
    if pathway_registry.exists():
        with open(pathway_registry, "r") as f:
            reader = csv.DictReader(f)
            pathway_rows = list(reader)

        logger.info("Read %d pathways from PATHWAY_REGISTRY.csv", len(pathway_rows))

        if not dry_run:
            with engine.begin() as conn:
                result = conn.execute(text("DELETE FROM pathways_v1"))
                logger.info("Cleared %d existing pathway rows", result.rowcount)

                insert_sql = text("""
                    INSERT OR IGNORE INTO pathways_v1 (
                        pathway_id, pathway_label, tier,
                        entry_node_ids_json, exit_node_ids_json,
                        intermediate_node_ids_json, edge_relation_ids_json,
                        cognitive_domain_specificity_json,
                        best_proxy_biomarker, proxy_r_squared,
                        causal_evidence_level, key_citation,
                        version, active, notes
                    ) VALUES (
                        :pathway_id, :pathway_label, :tier,
                        :entry_node_ids_json, :exit_node_ids_json,
                        :intermediate_node_ids_json, :edge_relation_ids_json,
                        :cognitive_domain_specificity_json,
                        :best_proxy_biomarker, :proxy_r_squared,
                        :causal_evidence_level, :key_citation,
                        :version, :active, :notes
                    )
                """)

                for row in pathway_rows:
                    pid = row.get("pathway_id", "").strip()
                    if not pid:
                        continue

                    # proxy_r_squared: convert qualitative → numeric
                    proxy_qual = row.get("proxy_r_squared_qualitative", "").strip().lower()
                    proxy_map = {"high": 0.7, "moderate": 0.4, "low": 0.15, "very_low": 0.05}
                    proxy_r2 = proxy_map.get(proxy_qual, 0.3)

                    # Build edge_relation_ids_json from component_nodes if available
                    # (the registry has component_nodes_json but not edge_relation_ids_json)
                    edge_rel_json = "[]"

                    params = {
                        "pathway_id": pid,
                        "pathway_label": row.get("pathway_label", "").strip() or pid,
                        "tier": row.get("tier", "").strip() or "unknown",
                        "entry_node_ids_json": row.get("entry_node_ids_json", "").strip() or "[]",
                        "exit_node_ids_json": row.get("exit_node_ids_json", "").strip() or "[]",
                        "intermediate_node_ids_json": row.get("intermediate_node_ids_json", "").strip() or "[]",
                        "edge_relation_ids_json": edge_rel_json,
                        "cognitive_domain_specificity_json": row.get("cognitive_domain_specificity_json", "").strip() or "{}",
                        "best_proxy_biomarker": row.get("best_proxy_biomarker", "").strip() or None,
                        "proxy_r_squared": proxy_r2,
                        "causal_evidence_level": row.get("causal_evidence_level", "").strip() or "unknown",
                        "key_citation": row.get("key_citation", "").strip() or "pending",
                        "version": int(row.get("version", 1)),
                        "active": int(row.get("active", 1)),
                        "notes": row.get("notes", "").strip() or "",
                    }
                    conn.execute(insert_sql, params)
                    pathways_loaded += 1

                logger.info("Inserted %d pathway definitions from PATHWAY_REGISTRY.csv", pathways_loaded)
        else:
            pathways_loaded = len(pathway_rows)
            logger.info("[DRY RUN] Would insert %d pathway definitions", pathways_loaded)
    else:
        logger.warning("PATHWAY_REGISTRY.csv not found at %s", pathway_registry)

    return measures_loaded, pathways_loaded


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

def _compute_span_hash(study_id: str, edge_id: str, beta: float, se: float | None, n: int | None) -> str:
    """Deterministic hash for dedup — same data = same hash."""
    se_str = f"{se:.6f}" if se is not None else "none"
    n_str = str(n) if n is not None else "0"
    h = hashlib.sha1(f"{study_id}|{edge_id}|{beta:.6f}|{se_str}|{n_str}".encode()).hexdigest()[:16]
    return h


def _safe_float(val: str | None) -> float | None:
    """Parse float from CSV value, returning None for empty/invalid."""
    if val is None:
        return None
    val = val.strip()
    if not val or val.lower() in ("", "na", "nan", "none"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _safe_int(val: str | None) -> int | None:
    """Parse int from CSV value, returning None for empty/invalid."""
    if val is None:
        return None
    val = val.strip()
    if not val or val.lower() in ("", "na", "nan", "none"):
        return None
    try:
        return int(float(val))  # handles "19.0"
    except ValueError:
        return None


def _csv_str(row: dict, key: str) -> str | None:
    """Get a CSV field as cleaned string, or None if absent/empty."""
    val = row.get(key)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def load_csv_evidence(engine, dry_run: bool = False) -> int:
    """Load edge evidence from manual CSV templates into edge_evidence_v1.

    CRITICAL: This populates BOTH the raw columns (effect_value_reported,
    se_reported) AND the harmonized columns (harmonized_beta, harmonized_se,
    harmonization_status, harmonized_scale). For manual CSV extractions,
    the raw values ARE the harmonized values — they are already clean
    effect sizes in standard units.

    Handles both 12-column minimal CSVs and 32-column extended CSVs.
    Deduplicates by span_hash (study + edge + beta + se + n).
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

    # Collect existing span_hashes to avoid duplicates
    existing_hashes: set[str] = set()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT span_hash FROM edge_evidence_v1 WHERE span_hash IS NOT NULL"))
        for row in result:
            existing_hashes.add(row[0])

    total_loaded = 0

    # Full INSERT statement covering raw + harmonized + extended columns
    insert_sql = text("""
        INSERT INTO edge_evidence_v1 (
            ler_id, edge_param_id, edge_relation_id, profile_id, study_id,
            edge_family, node_x, node_y,
            upstream_instrument_id,
            effect_type_reported, effect_value_reported, se_reported,
            ci_low_reported, ci_high_reported, p_value,
            N_effect, effect_size_type,
            harmonized_beta, harmonized_se, harmonization_status, harmonized_scale,
            se_derivation_level, se_quality_tag,
            rob_overall, identification_status,
            quality_rating, notes, extraction_snippet,
            shared_control_flag, endpoint_vs_change, comparison_arm_label,
            study_design, cancer_type, treatment_phase, pub_year,
            covariates_adjusted, sd_x, sd_y, cancer_validation_status,
            entered_by, entered_at, version, active,
            span_hash
        ) VALUES (
            :ler_id, :edge_param_id, :edge_relation_id, :profile_id, :study_id,
            :edge_family, :node_x, :node_y,
            :upstream_instrument_id,
            :effect_type_reported, :effect_value_reported, :se_reported,
            :ci_low_reported, :ci_high_reported, :p_value,
            :N_effect, :effect_size_type,
            :harmonized_beta, :harmonized_se, :harmonization_status, :harmonized_scale,
            :se_derivation_level, :se_quality_tag,
            :rob_overall, :identification_status,
            :quality_rating, :notes, :extraction_snippet,
            :shared_control_flag, :endpoint_vs_change, :comparison_arm_label,
            :study_design, :cancer_type, :treatment_phase, :pub_year,
            :covariates_adjusted, :sd_x, :sd_y, :cancer_validation_status,
            :entered_by, :entered_at, :version, :active,
            :span_hash
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
                edge_id = _csv_str(row, "edge_id")
                doi = _csv_str(row, "doi")
                study_id = DOI_TO_STUDY.get(doi) if doi else None

                if not study_id:
                    logger.warning("Unknown DOI '%s' in %s, skipping row", doi, csv_path)
                    continue

                if not edge_id:
                    logger.warning("Empty edge_id in %s, skipping row", csv_path)
                    continue

                beta_raw = _safe_float(row.get("beta_raw"))
                se_raw = _safe_float(row.get("se_raw"))
                sample_size = _safe_int(row.get("sample_size"))

                if beta_raw is None:
                    logger.warning("Missing beta_raw for %s × %s, skipping", study_id, edge_id)
                    continue

                if se_raw is None or se_raw <= 0:
                    logger.warning(
                        "Missing or invalid se_raw (%.4f) for %s × %s, skipping",
                        se_raw or 0, study_id, edge_id,
                    )
                    continue

                # Dedup by content hash
                span_hash = _compute_span_hash(study_id, edge_id, beta_raw, se_raw, sample_size)
                if span_hash in existing_hashes:
                    logger.info(
                        "Evidence %s × %s (hash=%s) already exists, skipping",
                        study_id, edge_id, span_hash,
                    )
                    continue

                # Look up edge definition for node_x/node_y
                edge_def = edge_defs.get(edge_id, {})
                if not edge_def:
                    logger.warning(
                        "Edge %s not in edge_relations_definitions_v1, using defaults",
                        edge_id,
                    )

                # Build deterministic ler_id
                ler_id = f"LER_{study_id}_{edge_id}_{span_hash}"

                # Determine harmonized_scale from effect_size_type
                effect_size_type = _csv_str(row, "effect_size_type") or "BETWEEN_GROUP"
                effect_type_original = _csv_str(row, "effect_type_original") or ""

                # Map effect type to a harmonized scale label
                if "cohen" in effect_type_original.lower() or "cohens_d" in effect_type_original.lower():
                    harmonized_scale = "cohens_d"
                elif "mean_diff" in effect_type_original.lower():
                    harmonized_scale = "mean_diff_raw"
                elif "odds_ratio" in effect_type_original.lower() or "log_or" in effect_type_original.lower():
                    harmonized_scale = "log_odds_ratio"
                elif "hazard" in effect_type_original.lower():
                    harmonized_scale = "log_hazard_ratio"
                else:
                    harmonized_scale = "cohens_d"  # safe default for CRCI

                # Determine quality from rob_overall or default
                rob_overall = _csv_str(row, "rob_overall")
                quality_rating = rob_overall or "moderate"

                # SE derivation level from CSV (extended format)
                se_derivation = _csv_str(row, "se_derivation_method") or "direct"

                # Identification status: manually extracted → at least "plausible"
                identification_status = "plausible"

                # Build extraction snippet from context
                snippet_parts = []
                if _csv_str(row, "effect_size_context"):
                    snippet_parts.append(_csv_str(row, "effect_size_context"))
                if _csv_str(row, "beta_sign_convention"):
                    snippet_parts.append(f"sign_convention={_csv_str(row, 'beta_sign_convention')}")
                if _csv_str(row, "outcome_directionality"):
                    snippet_parts.append(f"directionality={_csv_str(row, 'outcome_directionality')}")
                extraction_snippet = "; ".join(snippet_parts) if snippet_parts else None

                params = {
                    "ler_id": ler_id,
                    "edge_param_id": f"EP_{edge_id}_{span_hash[:8]}",
                    "edge_relation_id": edge_id,
                    "profile_id": "PROFILE_DEFAULT",
                    "study_id": study_id,
                    "edge_family": edge_def.get("edge_family", "unknown"),
                    "node_x": edge_def.get("node_x", "unknown"),
                    "node_y": edge_def.get("node_y", "unknown"),
                    "upstream_instrument_id": _csv_str(row, "instrument_id"),
                    # Raw columns
                    "effect_type_reported": effect_type_original,
                    "effect_value_reported": beta_raw,
                    "se_reported": se_raw,
                    "ci_low_reported": _safe_float(row.get("ci_low")),
                    "ci_high_reported": _safe_float(row.get("ci_high")),
                    "p_value": _safe_float(row.get("p_value")),
                    "N_effect": sample_size,
                    "effect_size_type": effect_size_type,
                    # HARMONIZED columns — CRITICAL for evidence_loader
                    "harmonized_beta": beta_raw,
                    "harmonized_se": se_raw,
                    "harmonization_status": "harmonized",
                    "harmonized_scale": harmonized_scale,
                    # SE provenance
                    "se_derivation_level": se_derivation,
                    "se_quality_tag": "manual_extraction",
                    # Quality & identification
                    "rob_overall": rob_overall,
                    "identification_status": identification_status,
                    "quality_rating": quality_rating,
                    "notes": _csv_str(row, "confidence_note") or "",
                    "extraction_snippet": extraction_snippet,
                    # Extended columns
                    "shared_control_flag": 1 if _csv_str(row, "shared_control_flag") == "1" else 0,
                    "endpoint_vs_change": _csv_str(row, "endpoint_vs_change"),
                    "comparison_arm_label": _csv_str(row, "comparison_arm_label"),
                    # Study-level metadata columns (from CSV)
                    "study_design": _csv_str(row, "study_design"),
                    "cancer_type": _csv_str(row, "cancer_type"),
                    "treatment_phase": _csv_str(row, "treatment_phase"),
                    "pub_year": _safe_int(row.get("pub_year")),
                    "covariates_adjusted": _csv_str(row, "covariates_adjusted"),
                    "sd_x": _safe_float(row.get("sd_treatment")),
                    "sd_y": _safe_float(row.get("sd_control")),
                    "cancer_validation_status": _csv_str(row, "cancer_validated"),
                    # Audit
                    "entered_by": "manual_csv_import",
                    "entered_at": datetime.now(timezone.utc).isoformat(),
                    "version": 1,
                    "active": 1,
                    "span_hash": span_hash,
                }

                if dry_run:
                    logger.info(
                        "[DRY RUN] Would insert %s: %s × %s β=%.3f SE=%.3f n=%s",
                        ler_id, study_id, edge_id, beta_raw, se_raw, sample_size,
                    )
                else:
                    conn.execute(insert_sql, params)
                    logger.info(
                        "Inserted %s: %s × %s β=%.3f SE=%.3f n=%s scale=%s",
                        ler_id, study_id, edge_id, beta_raw, se_raw,
                        sample_size, harmonized_scale,
                    )

                existing_hashes.add(span_hash)
                total_loaded += 1

    return total_loaded


# ============================================================================
#  STEP 4b: Load auxiliary family CSVs (context_priors, instrument_evidence,
#           population_norms, temporal_evidence)
# ============================================================================

# Map CSV template filename stem → (importer function, target table)
_FAMILY_IMPORTERS = {
    "context_priors_template": ("context_prior", import_context_prior),
    "correlation_template": ("correlation", import_correlation),
    "instrument_evidence_template": ("instrument_evidence", import_instrument_evidence),
    "population_norms_template": ("population_norm", import_population_norm),
    "temporal_evidence_template": ("temporal_evidence", import_temporal_evidence),
    # B2-B5 study metadata families
    "study_cohort_profile_template": ("study_cohort_profile", import_study_cohort_profile),
    "profile_data_stream_template": ("profile_data_stream", import_profile_data_stream),
    "stream_timepoint_template": ("stream_timepoint", import_stream_timepoint),
    "ontology_link_template": ("ontology_link", import_ontology_link),
    # Dose + subgroup evidence
    "dose_evidence_template": ("dose_evidence", import_dose_evidence),
    "subgroup_evidence_template": ("subgroup_evidence", import_subgroup_evidence),
}


def load_family_csvs(engine, dry_run: bool = False) -> dict[str, int]:
    """Load auxiliary evidence families from manual CSV templates.

    Scans data/manual_uploads/structured/<doi-slug>/ for each template type
    and imports rows via the validated family_importers module.

    Returns:
        Dict mapping family name → number of rows imported.
    """
    from sqlalchemy.orm import Session as SASession

    csv_dir = PROJECT_ROOT / "data" / "manual_uploads" / "structured"
    if not csv_dir.exists():
        logger.warning("No structured CSV directory at %s", csv_dir)
        return {}

    results: dict[str, int] = {}

    for template_stem, (family_name, importer_fn) in _FAMILY_IMPORTERS.items():
        csv_files = sorted(csv_dir.rglob(f"{template_stem}.csv"))
        if not csv_files:
            logger.info("No %s.csv files found", template_stem)
            results[family_name] = 0
            continue

        family_count = 0

        for csv_path in csv_files:
            # Derive DOI from parent directory name (e.g., "10.1002_pon.4370")
            doi_slug = csv_path.parent.name
            doi = doi_slug.replace("_", "/")
            study_id = DOI_TO_STUDY.get(doi)

            if not study_id:
                logger.warning(
                    "Unknown DOI '%s' (from dir %s) for %s, skipping",
                    doi, doi_slug, csv_path.name,
                )
                continue

            with open(csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                logger.warning("Empty CSV: %s", csv_path)
                continue

            logger.info(
                "Loading %d %s rows from %s (study=%s)",
                len(rows), family_name, csv_path.name, study_id,
            )

            if dry_run:
                logger.info("[DRY RUN] Would import %d %s rows", len(rows), family_name)
                family_count += len(rows)
                continue

            # Use ORM session for family importers (they use session.add())
            with get_session() as session:
                for row_dict in rows:
                    # Inject doi for provenance
                    row_dict["doi"] = doi
                    try:
                        importer_fn(session, row_dict, study_id)
                        family_count += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to import %s row (study=%s): %s",
                            family_name, study_id, exc,
                        )
                # Session auto-commits on exit from context manager
                logger.info(
                    "Committed %s rows from %s", family_name, csv_path.name,
                )

        results[family_name] = family_count
        logger.info("Total %s rows imported: %d", family_name, family_count)

    return results


# ============================================================================
#  STEP 4 (legacy): Clean up old study entries with wrong IDs
# ============================================================================
def cleanup_old_entries(engine, dry_run: bool = False) -> None:
    """Remove legacy study entries with inconsistent IDs."""
    legacy_ids = ["CHERRIER2013", "STUDY_c5c88ae841b4", "STUDY_UNIT_TEST"]
    with engine.begin() as conn:
        for old_id in legacy_ids:
            result = conn.execute(
                text("SELECT study_id FROM study_registry_v1 WHERE study_id = :sid"),
                {"sid": old_id},
            )
            if result.fetchone():
                if not dry_run:
                    conn.execute(
                        text("DELETE FROM study_registry_v1 WHERE study_id = :sid"),
                        {"sid": old_id},
                    )
                    logger.info("Removed legacy study entry: %s", old_id)
                else:
                    logger.info("[DRY RUN] Would remove legacy study entry: %s", old_id)


# ============================================================================
#  STEP 5: Seed action_catalog_v1
# ============================================================================
def seed_action_catalog(engine, dry_run: bool = False) -> int:
    """Seed action_catalog_v1 from crci/database/seeds/actions.csv."""
    csv_path = PROJECT_ROOT / "crci" / "database" / "seeds" / "actions.csv"
    if not csv_path.exists():
        logger.warning("actions.csv not found at %s", csv_path)
        return 0

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Read %d actions from %s", len(rows), csv_path)

    loaded = 0
    with engine.begin() as conn:
        for row in rows:
            action_id = row.get("action_id", "").strip()
            if not action_id:
                continue

            # Check if exists
            existing = conn.execute(
                text("SELECT action_id FROM action_catalog_v1 WHERE action_id = :aid"),
                {"aid": action_id},
            ).fetchone()
            if existing:
                logger.debug("Action %s already exists, skipping", action_id)
                continue

            if dry_run:
                logger.info("[DRY RUN] Would insert action %s", action_id)
                loaded += 1
                continue

            conn.execute(
                text("""
                    INSERT INTO action_catalog_v1 (
                        action_id, action_label, action_class, dose_type, dose_unit,
                        dose_semantics, dose_min, dose_max, dose_recommended_start,
                        dose_step, time_cost_min_default, cognitive_load_default,
                        logistics_load_default, overall_burden_default,
                        adherence_rate_default, evidence_basis, evidence_strength,
                        notes, version, active
                    ) VALUES (
                        :action_id, :action_label, :action_class, :dose_type, :dose_unit,
                        :dose_semantics, :dose_min, :dose_max, :dose_recommended_start,
                        :dose_step, :time_cost_min_default, :cognitive_load_default,
                        :logistics_load_default, :overall_burden_default,
                        :adherence_rate_default, :evidence_basis, :evidence_strength,
                        :notes, :version, :active
                    )
                """),
                {
                    "action_id": action_id,
                    "action_label": row.get("action_label", "").strip(),
                    "action_class": row.get("action_class", "").strip(),
                    "dose_type": row.get("dose_type", "").strip(),
                    "dose_unit": row.get("dose_unit", "").strip() or None,
                    "dose_semantics": row.get("dose_semantics", "").strip() or None,
                    "dose_min": _safe_float(row.get("dose_min")),
                    "dose_max": _safe_float(row.get("dose_max")),
                    "dose_recommended_start": _safe_float(row.get("dose_recommended_start")),
                    "dose_step": _safe_float(row.get("dose_step")),
                    "time_cost_min_default": _safe_float(row.get("time_cost_min_default")),
                    "cognitive_load_default": _safe_float(row.get("cognitive_load_default")),
                    "logistics_load_default": _safe_float(row.get("logistics_load_default")),
                    "overall_burden_default": _safe_float(row.get("overall_burden_default")),
                    "adherence_rate_default": _safe_float(row.get("adherence_rate_default")),
                    "evidence_basis": row.get("evidence_basis", "").strip() or None,
                    "evidence_strength": row.get("evidence_strength", "").strip() or None,
                    "notes": row.get("notes", "").strip() or None,
                    "version": _safe_int(row.get("version")) or 1,
                    "active": _safe_int(row.get("active")) or 1,
                },
            )
            loaded += 1
            logger.info("Inserted action %s", action_id)

    return loaded


# ============================================================================
#  STEP 5b: Seed dose_bridges_v1 from crci/database/seeds/dose_bridges.csv
# ============================================================================
def seed_dose_bridges(engine, dry_run: bool = False) -> int:
    """Seed dose_bridges_v1 from crci/database/seeds/dose_bridges.csv."""
    csv_path = PROJECT_ROOT / "crci" / "database" / "seeds" / "dose_bridges.csv"
    if not csv_path.exists():
        logger.warning("dose_bridges.csv not found at %s", csv_path)
        return 0

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Read %d dose bridges from %s", len(rows), csv_path)

    loaded = 0
    with engine.begin() as conn:
        for row in rows:
            bridge_id = row.get("bridge_id", "").strip()
            if not bridge_id:
                continue

            # Check if exists
            existing = conn.execute(
                text("SELECT bridge_id FROM dose_bridges_v1 WHERE bridge_id = :bid"),
                {"bid": bridge_id},
            ).fetchone()
            if existing:
                logger.debug("Dose bridge %s already exists, skipping", bridge_id)
                continue

            if dry_run:
                logger.info("[DRY RUN] Would insert dose bridge %s", bridge_id)
                loaded += 1
                continue

            conn.execute(
                text("""
                    INSERT INTO dose_bridges_v1 (
                        bridge_id, action_id, output_mode, output_feature_id,
                        output_node_id, maps_to_node_id, dose_type, dose_unit,
                        dose_min, dose_max, dose_step, dose_reference,
                        dose_response_family, dose_response_params_json,
                        bridge_effect_sign, bridge_gain, bridge_noise_sd,
                        time_step_unit, temporal_family, lag_steps, half_life_steps,
                        scope_json, provenance, version, active
                    ) VALUES (
                        :bridge_id, :action_id, :output_mode, :output_feature_id,
                        :output_node_id, :maps_to_node_id, :dose_type, :dose_unit,
                        :dose_min, :dose_max, :dose_step, :dose_reference,
                        :dose_response_family, :dose_response_params_json,
                        :bridge_effect_sign, :bridge_gain, :bridge_noise_sd,
                        :time_step_unit, :temporal_family, :lag_steps, :half_life_steps,
                        :scope_json, :provenance, :version, :active
                    )
                """),
                {
                    "bridge_id": bridge_id,
                    "action_id": row.get("action_id", "").strip(),
                    "output_mode": row.get("output_mode", "node").strip(),
                    "output_feature_id": row.get("output_feature_id", "").strip() or None,
                    "output_node_id": row.get("output_node_id", "").strip() or None,
                    "maps_to_node_id": row.get("maps_to_node_id", "").strip() or None,
                    "dose_type": row.get("dose_type", "").strip() or None,
                    "dose_unit": row.get("dose_unit", "").strip() or None,
                    "dose_min": _safe_float(row.get("dose_min")),
                    "dose_max": _safe_float(row.get("dose_max")),
                    "dose_step": _safe_float(row.get("dose_step")),
                    "dose_reference": _safe_float(row.get("dose_reference")) or 1.0,
                    "dose_response_family": row.get("dose_response_family", "linear").strip(),
                    "dose_response_params_json": row.get("dose_response_params_json", "{}").strip(),
                    "bridge_effect_sign": _safe_int(row.get("bridge_effect_sign")) or 1,
                    "bridge_gain": _safe_float(row.get("bridge_gain")) or 1.0,
                    "bridge_noise_sd": _safe_float(row.get("bridge_noise_sd")),
                    "time_step_unit": row.get("time_step_unit", "day").strip(),
                    "temporal_family": row.get("temporal_family", "delta").strip(),
                    "lag_steps": _safe_int(row.get("lag_steps")) or 0,
                    "half_life_steps": _safe_float(row.get("half_life_steps")),
                    "scope_json": row.get("scope_json", "{}").strip(),
                    "provenance": row.get("provenance", "CATEGORY_A_CURATED").strip(),
                    "version": _safe_int(row.get("version")) or 1,
                    "active": _safe_int(row.get("active")) or 1,
                },
            )
            loaded += 1
            logger.info("Inserted dose bridge %s → %s",
                        bridge_id, row.get("output_node_id", "").strip())

    return loaded


# ============================================================================
#  STEP 4c: Harmonize scales to Cohen's d
# ============================================================================
def harmonize_scales_to_cohens_d(engine, dry_run: bool = False) -> int:
    """Convert mean_diff_raw evidence rows to cohens_d using population norm SD.

    For each evidence row with harmonized_scale='mean_diff_raw':
    1. Look up the outcome node (node_y) in population_norms_v1
    2. Borrow the pooled SD from the closest matching norm
    3. Convert: d = mean_diff / SD_pooled,  SE_d = SE_raw / SD_pooled
    4. Apply Tier-based SE inflation per SYS_EXTRACTION S3 SD borrowing spec
    5. Update the row to harmonized_scale='cohens_d'

    This ensures all evidence rows fed to IVW compilation are on a
    common standardized scale, preventing nonsensical pooling of raw
    score differences with Cohen's d values.

    Returns:
        Number of rows converted.
    """
    from crci.shared.config import (
        SD_BORROW_TIER1_INFLATION,
        SD_BORROW_TIER2_INFLATION,
        SD_BORROW_TIER3_INFLATION,
    )

    converted = 0
    skipped = 0

    with engine.begin() as conn:
        # Get all mean_diff_raw rows
        rows = conn.execute(text("""
            SELECT ler_id, edge_relation_id, harmonized_beta, harmonized_se,
                   N_effect, node_y, study_id
            FROM edge_evidence_v1
            WHERE harmonized_scale = 'mean_diff_raw' AND active = 1
        """)).fetchall()

        if not rows:
            logger.info("No mean_diff_raw rows to harmonize")
            return 0

        logger.info(
            "Found %d mean_diff_raw evidence rows to harmonize to cohens_d",
            len(rows),
        )

        for row in rows:
            ler_id, edge_id, beta_raw, se_raw, n_eff, node_y, study_id = row

            if not node_y:
                logger.warning(
                    "Harmonization skipped for %s: no node_y set", ler_id,
                )
                skipped += 1
                continue

            # Priority 1: SD from same study + same node (Tier 1)
            sd_row = conn.execute(text("""
                SELECT sd_raw, instrument_id, study_id
                FROM population_norms_v1
                WHERE node_id = :nid AND sd_raw > 0 AND study_id = :sid
                ORDER BY sd_raw DESC
                LIMIT 1
            """), {"nid": node_y, "sid": study_id}).fetchone()

            if sd_row:
                sd_pooled = sd_row[0]
                sd_source_inst = sd_row[1]
                sd_source_study = sd_row[2]
                se_inflation = SD_BORROW_TIER1_INFLATION  # 1.0 — same study
                borrow_tier = 1
            else:
                # Priority 2: SD from any study for this node (Tier 2)
                sd_row = conn.execute(text("""
                    SELECT sd_raw, instrument_id, study_id
                    FROM population_norms_v1
                    WHERE node_id = :nid AND sd_raw > 0
                    ORDER BY sd_raw DESC
                    LIMIT 1
                """), {"nid": node_y}).fetchone()

                if sd_row:
                    sd_pooled = sd_row[0]
                    sd_source_inst = sd_row[1]
                    sd_source_study = sd_row[2]
                    se_inflation = SD_BORROW_TIER2_INFLATION  # 1.15
                    borrow_tier = 2
                else:
                    logger.warning(
                        "Harmonization skipped for %s (%s): no population norm "
                        "SD found for node_y=%s",
                        ler_id, edge_id, node_y,
                    )
                    skipped += 1
                    continue

            if sd_pooled <= 0:
                logger.warning(
                    "Harmonization skipped for %s: SD_pooled=%.4f <= 0",
                    ler_id, sd_pooled,
                )
                skipped += 1
                continue

            # Formula: d = mean_diff / SD_pooled
            d = beta_raw / sd_pooled
            # SE transforms linearly: SE_d = SE_raw / SD_pooled
            se_d = se_raw / sd_pooled
            # Apply tier-based SE inflation for borrowed SD uncertainty
            se_d_inflated = se_d * se_inflation

            provenance_note = (
                f"; HARMONIZED mean_diff→cohens_d: d={d:.4f} "
                f"(beta_raw={beta_raw:.4f} / SD_pooled={sd_pooled:.4f}); "
                f"SE_d={se_d_inflated:.4f} (inflation={se_inflation:.2f}, "
                f"tier={borrow_tier}); SD from {sd_source_inst} "
                f"(study={sd_source_study})"
            )

            if dry_run:
                logger.info(
                    "[DRY RUN] Would harmonize %s: β=%.3f → d=%.4f, "
                    "SE=%.3f → %.4f (SD_pooled=%.2f, tier=%d)",
                    ler_id, beta_raw, d, se_raw, se_d_inflated,
                    sd_pooled, borrow_tier,
                )
            else:
                conn.execute(text("""
                    UPDATE edge_evidence_v1
                    SET harmonized_beta = :d,
                        harmonized_se = :se_d,
                        harmonized_scale = 'cohens_d',
                        harmonization_status = 'harmonized_scale_converted',
                        notes = notes || :provenance
                    WHERE ler_id = :ler_id
                """), {
                    "d": round(d, 6),
                    "se_d": round(se_d_inflated, 6),
                    "provenance": provenance_note,
                    "ler_id": ler_id,
                })
                logger.info(
                    "Harmonized %s (%s): β=%.3f → d=%.4f, SE=%.3f → %.4f "
                    "(SD_pooled=%.2f from %s, tier=%d)",
                    ler_id, edge_id, beta_raw, d, se_raw, se_d_inflated,
                    sd_pooled, sd_source_inst, borrow_tier,
                )

            converted += 1

    if skipped:
        logger.warning(
            "Scale harmonization: %d rows converted, %d skipped (no SD available)",
            converted, skipped,
        )
    else:
        logger.info("Scale harmonization: %d rows converted to cohens_d", converted)

    return converted


# ============================================================================
#  STEP 4d: Apply 7-layer SE_eff calibration (Formula P3-8)
#
#  Implements the full P3 heterogeneity pipeline for CSV-imported data.
#  For each evidence row, applies:
#    L1: Study design penalty (small RCT interpolation from N)
#    L2: Scope match (1.0 for manual extraction = well-scoped)
#    L3: Statistical heterogeneity (τ²/I² from grouped edge data)
#    L4: Cancer validation multiplier (from CSV cancer_validated column)
#    L5: GRADE quality (from quality_rating → HIGH/MODERATE/LOW)
#    L6: Temporal decay (conservative default: 14 days when absent)
#    L7: Freshness (from pub_year, decay 1.5%/yr)
#
#  Formula P3-8:
#    SE_eff = √[(SE · m_design · m_scale · m_GRADE)² + σ²_struct + τ²·𝟙[I²≥50%]]
#             / (max(w_scope, 0.3) · w_fresh)
#
#  Gate P3-G1: SE_eff ≥ SE_raw (calibration only inflates, never deflates)
# ============================================================================


def _build_cancer_validation_lookup() -> dict[tuple[str, str], str]:
    """Read CSV files to build (doi_slug, edge_id) → validation_status map.

    Maps CSV ``cancer_validated`` column values to config.SCALE_MULTIPLIERS keys:
      - "yes" → "validated_cancer"  (m=1.0)
      - "no"  → "general_population" (m=1.30)
      - missing column → "general_population" (m=1.30)

    Returns:
        Dict mapping (doi_slug, edge_relation_id) → validation_status string.
    """
    structured_dir = PROJECT_ROOT / "data" / "manual_uploads" / "structured"
    lookup: dict[tuple[str, str], str] = {}

    if not structured_dir.exists():
        logger.warning("Structured dir %s not found; cancer validation will default", structured_dir)
        return lookup

    for doi_dir in sorted(structured_dir.iterdir()):
        if not doi_dir.is_dir():
            continue
        csv_path = doi_dir / "edge_evidence_template.csv"
        if not csv_path.exists():
            continue

        doi_slug = doi_dir.name
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge_id = row.get("edge_id", "").strip()
                cancer_val = row.get("cancer_validated", "").strip().lower()
                if cancer_val == "yes":
                    status = "validated_cancer"
                elif cancer_val == "no":
                    status = "general_population"
                else:
                    # Column missing or empty → default
                    status = "general_population"
                key = (doi_slug, edge_id)
                # For duplicate edge_ids (e.g. multiple comparison arms),
                # prefer the most informative (non-default) value
                existing = lookup.get(key)
                if existing is None or (
                    existing == "general_population"
                    and status != "general_population"
                ):
                    lookup[key] = status

    logger.info(
        "Cancer validation lookup: %d entries from %s",
        len(lookup), structured_dir,
    )
    return lookup


def _doi_to_slug(doi: str) -> str:
    """Convert a DOI like '10.1002/pon.4370' to directory slug '10.1002_pon.4370'."""
    return doi.replace("/", "_")


def apply_se_eff_calibration(engine, dry_run: bool = False) -> int:
    """Step 4d: Apply 7-layer SE_eff calibration to all evidence rows.

    Replaces the P3 heterogeneity pipeline that was bypassed for
    CSV-imported data. Updates harmonized_se in-place with the
    calibrated SE_eff value. Records se_inflation_applied and
    cancer_validation_status for audit trail.

    Formula P3-8 implementation via crci.extraction.p3_heterogeneity.

    Returns:
        Number of rows calibrated.
    """
    from crci.extraction.p3_heterogeneity.se_eff_assembly import (
        SEEffInput,
        compute_se_eff,
    )

    calibrated = 0
    failed = 0

    # Build cancer validation lookup from source CSVs
    cancer_lookup = _build_cancer_validation_lookup()

    with engine.begin() as conn:
        # Fetch all active evidence with harmonized values
        rows = conn.execute(text("""
            SELECT
                ee.ler_id,
                ee.edge_relation_id,
                ee.study_id,
                ee.harmonized_beta,
                ee.harmonized_se,
                ee.N_effect,
                ee.quality_rating,
                ee.study_design,
                ee.pub_year,
                ee.cancer_validation_status,
                ee.parameter_family,
                ee.freshness_superseded,
                ee.notes
            FROM edge_evidence_v1 ee
            WHERE ee.active = 1
              AND ee.harmonized_beta IS NOT NULL
              AND ee.harmonized_se IS NOT NULL
              AND ee.harmonized_se > 0
        """)).fetchall()

        if not rows:
            logger.warning("SE_eff calibration: no active evidence rows found")
            return 0

        # Group by edge_relation_id for L3 heterogeneity computation
        edge_groups: dict[str, list] = {}
        for row in rows:
            eid = row[1]  # edge_relation_id
            if eid not in edge_groups:
                edge_groups[eid] = []
            edge_groups[eid].append(row)

        # Per-edge grouped betas/SEs for L3 (DerSimonian-Laird τ²/I²)
        edge_betas: dict[str, list[float]] = {}
        edge_ses: dict[str, list[float]] = {}
        for eid, group in edge_groups.items():
            edge_betas[eid] = [r[3] for r in group]  # harmonized_beta
            edge_ses[eid] = [r[4] for r in group]     # harmonized_se

        # Look up DOI for each study_id (for cancer validation CSV lookup)
        study_doi_map: dict[str, str] = {}
        doi_rows = conn.execute(text(
            "SELECT study_id, doi FROM study_registry_v1"
        )).fetchall()
        for sr in doi_rows:
            study_doi_map[sr[0]] = sr[1]

        logger.info(
            "SE_eff calibration: %d rows across %d edges",
            len(rows), len(edge_groups),
        )

        for row in rows:
            ler_id = row[0]
            edge_id = row[1]
            study_id = row[2]
            se_raw = row[4]
            n_total = row[5]
            quality_rating = row[6]
            study_design_raw = row[7]
            pub_year = row[8]
            existing_cancer_val = row[9]
            param_family = row[10]
            freshness_superseded = row[11]

            # ── L1: Map study_design for layer function ──
            sd = (study_design_raw or "RCT").strip().upper()
            if sd == "RCT":
                if n_total and n_total > 200:
                    study_design_key = "large_rct"
                else:
                    study_design_key = "small_rct"
            elif sd in ("COHORT", "WELL_ADJUSTED_COHORT"):
                study_design_key = "well_adjusted_cohort"
            elif sd in ("CROSS_SECTIONAL", "CROSS-SECTIONAL"):
                study_design_key = "cross_sectional_adjusted"
            else:
                study_design_key = sd.lower()

            # ── L4: Cancer validation status ──
            # Priority: existing DB value > CSV lookup > default
            if existing_cancer_val and existing_cancer_val in (
                "validated_cancer", "used_cancer",
                "general_population", "known_somatic_confound",
            ):
                validation_status = existing_cancer_val
            else:
                # Look up from CSV via DOI slug
                doi = study_doi_map.get(study_id, "")
                doi_slug = _doi_to_slug(doi) if doi else ""
                csv_val = cancer_lookup.get((doi_slug, edge_id))
                validation_status = csv_val or "general_population"

            # ── L5: GRADE quality ──
            qr = (quality_rating or "moderate").strip().upper()
            grade_level = qr if qr in ("HIGH", "MODERATE", "LOW", "VERY_LOW") else "MODERATE"

            # ── Build SEEffInput ──
            try:
                inp = SEEffInput(
                    ler_id=ler_id,
                    se_raw=se_raw,
                    study_design=study_design_key,
                    n_total=n_total,
                    w_scope=1.0,  # Manual extraction = well-scoped studies
                    betas=edge_betas[edge_id],
                    ses=edge_ses[edge_id],
                    validation_status=validation_status,
                    grade_level=grade_level,
                    days_since_measurement=0.0,
                    temporal_data_available=False,  # → conservative 14d default
                    is_trait=False,
                    pub_year=pub_year,
                    parameter_family=param_family,
                    superseded_by_newer=bool(freshness_superseded),
                    sigma_sq_structural=None,  # → config.SIGMA_SQ_STRUCTURAL_DEFAULT
                    edge_relation_id=edge_id,
                )

                result = compute_se_eff(inp)
                se_eff = result.se_effective

            except Exception as exc:
                logger.error(
                    "SE_eff failed for %s: %s", ler_id, exc,
                )
                failed += 1
                continue

            # ── Update DB ──
            inflation = se_eff / se_raw if se_raw > 0 else 1.0
            note_suffix = (
                f"\n[SE_eff P3-8] SE calibrated: {se_raw:.4f} → {se_eff:.4f} "
                f"(×{inflation:.2f}). design={study_design_key}(N={n_total}), "
                f"validation={validation_status}, grade={grade_level}, "
                f"pub={pub_year}, k={len(edge_betas[edge_id])}"
            )

            if not dry_run:
                conn.execute(text("""
                    UPDATE edge_evidence_v1
                    SET harmonized_se = :se_eff,
                        cancer_validation_status = :validation_status,
                        se_inflation_applied = :inflation,
                        notes = COALESCE(notes, '') || :note
                    WHERE ler_id = :ler_id
                """), {
                    "se_eff": round(se_eff, 6),
                    "validation_status": validation_status,
                    "inflation": round(inflation, 4),
                    "note": note_suffix,
                    "ler_id": ler_id,
                })

            logger.info(
                "SE_eff %s (%s): SE %.4f → %.4f (×%.2f) "
                "[L1=%s(N=%s), L4=%s, L5=%s, L7=pub%s, k=%d]",
                ler_id, edge_id, se_raw, se_eff, inflation,
                study_design_key, n_total, validation_status,
                grade_level, pub_year, len(edge_betas[edge_id]),
            )
            calibrated += 1

    if failed:
        logger.warning(
            "SE_eff calibration: %d calibrated, %d failed", calibrated, failed,
        )
    else:
        logger.info("SE_eff calibration: all %d rows calibrated", calibrated)

    return calibrated


# ============================================================================
#  STEP 6: Compile evidence → edges_v1 (lightweight IVW aggregation)
# ============================================================================
def compile_edges(engine, dry_run: bool = False) -> int:
    """Compile edge_evidence_v1 → edges_v1 using IVW pooling.

    For each distinct edge_relation_id with harmonized evidence:
    1. Collect all active rows with valid harmonized_beta + harmonized_se
    2. If k=1: single-study estimate (beta = that study's beta, SE = that SE)
    3. If k>=2: IVW pooling: β̂ = Σ(βᵢ/SEᵢ²) / Σ(1/SEᵢ²); SE = 1/√(Σ(1/SEᵢ²))
    4. Write/update edges_v1 row with compiled parameters

    This replaces the full P4 pipeline for manual imports while
    preserving the same output contract.
    """
    compiled = 0

    with engine.begin() as conn:
        # Clear existing edges_v1 (will rebuild from evidence)
        if not dry_run:
            conn.execute(text("DELETE FROM edges_v1"))
            logger.info("Cleared edges_v1 for recompilation")

        # Get all distinct edges with evidence
        result = conn.execute(text("""
            SELECT edge_relation_id,
                   harmonized_beta, harmonized_se, N_effect, harmonized_scale,
                   study_id, quality_rating, rob_overall,
                   ci_low_reported, ci_high_reported
            FROM edge_evidence_v1
            WHERE active = 1
              AND harmonized_beta IS NOT NULL
              AND harmonized_se IS NOT NULL
              AND harmonized_se > 0
              AND edge_relation_id != 'UNASSIGNED'
            ORDER BY edge_relation_id
        """))
        all_rows = result.fetchall()

        # Group by edge_relation_id
        from itertools import groupby
        from operator import itemgetter

        groups = {}
        for row in all_rows:
            eid = row[0]
            if eid not in groups:
                groups[eid] = []
            groups[eid].append(row)

        # Also look up edge definitions for metadata
        edge_defs = {}
        result = conn.execute(text(
            "SELECT edge_relation_id, node_x, node_y, default_effect_direction "
            "FROM edge_relations_definitions_v1"
        ))
        for row in result:
            edge_defs[row[0]] = {
                "node_x": row[1], "node_y": row[2],
                "direction": row[3],
            }

        logger.info("Compiling %d edges from %d evidence rows", len(groups), len(all_rows))

        insert_edge_sql = text("""
            INSERT INTO edges_v1 (
                edge_param_id, edge_relation_id,
                effect_scale, effect_direction,
                beta_mean, beta_se, beta_dist_family,
                ci_low, ci_high,
                aggregation_method, evidence_level,
                total_n, i_squared, tau_squared,
                supporting_ler_ids,
                notes, active, version
            ) VALUES (
                :edge_param_id, :edge_relation_id,
                :effect_scale, :effect_direction,
                :beta_mean, :beta_se, :beta_dist_family,
                :ci_low, :ci_high,
                :aggregation_method, :evidence_level,
                :total_n, :i_squared, :tau_squared,
                :supporting_ler_ids,
                :notes, :active, :version
            )
        """)

        for edge_id, evidence_rows in groups.items():
            k = len(evidence_rows)
            betas = [r[1] for r in evidence_rows]
            ses = [r[2] for r in evidence_rows]
            ns = [r[3] or 0 for r in evidence_rows]
            scale = evidence_rows[0][4] or "cohens_d"
            study_ids = [r[5] for r in evidence_rows]

            total_n = sum(ns)

            if k == 1:
                # Single study — pass through
                beta_pooled = betas[0]
                se_pooled = ses[0]
                aggregation_method = "SINGLE_STUDY"
                i_squared = 0.0
                tau_squared = 0.0
            else:
                # IVW pooling: Formula P4-1
                # β̂_IVW = Σ(βᵢ/SEᵢ²) / Σ(1/SEᵢ²)
                # SE_IVW = 1 / √(Σ(1/SEᵢ²))
                weights = [1.0 / (se ** 2) for se in ses]
                sum_weights = sum(weights)
                beta_pooled = sum(b * w for b, w in zip(betas, weights)) / sum_weights
                se_pooled = 1.0 / math.sqrt(sum_weights)
                aggregation_method = "IVW_FIXED"

                # Cochran's Q and I²
                q_stat = sum(w * (b - beta_pooled) ** 2 for b, w in zip(betas, weights))
                df = k - 1
                i_squared = max(0.0, (q_stat - df) / q_stat) if q_stat > 0 else 0.0
                # DerSimonian-Laird τ²
                c = sum_weights - sum(w ** 2 for w in weights) / sum_weights
                tau_squared = max(0.0, (q_stat - df) / c) if c > 0 else 0.0

            # CI from compiled estimate
            ci_low = beta_pooled - 1.96 * se_pooled
            ci_high = beta_pooled + 1.96 * se_pooled

            # Determine effect direction from edge definition
            edge_def = edge_defs.get(edge_id, {})
            direction = edge_def.get("direction", 0)
            if direction is None:
                direction = 0
            effect_direction = "positive" if direction >= 0 else "negative"

            # Determine evidence level
            if k >= 3:
                evidence_level = "DEPLOY"
            elif k >= 1:
                evidence_level = "DEPLOY_WITH_WARNINGS"
            else:
                evidence_level = "BLOCKED"

            edge_param_id = f"EP_{edge_id}_compiled"
            ler_list = json.dumps([f"LER_{sid}_{edge_id}" for sid in study_ids])

            params = {
                "edge_param_id": edge_param_id,
                "edge_relation_id": edge_id,
                "effect_scale": scale,
                "effect_direction": effect_direction,
                "beta_mean": round(beta_pooled, 6),
                "beta_se": round(se_pooled, 6),
                "beta_dist_family": "normal",
                "ci_low": round(ci_low, 6),
                "ci_high": round(ci_high, 6),
                "aggregation_method": aggregation_method,
                "evidence_level": evidence_level,
                "total_n": total_n,
                "i_squared": round(i_squared, 4),
                "tau_squared": round(tau_squared, 6),
                "supporting_ler_ids": ler_list,
                "notes": f"Manual import: k={k} studies, IVW compiled",
                "active": 1,
                "version": 1,
            }

            if dry_run:
                logger.info(
                    "[DRY RUN] Would compile edge %s: β=%.4f SE=%.4f k=%d method=%s",
                    edge_id, beta_pooled, se_pooled, k, aggregation_method,
                )
            else:
                conn.execute(insert_edge_sql, params)
                logger.info(
                    "Compiled %s: β=%.4f SE=%.4f k=%d n=%d method=%s level=%s",
                    edge_id, beta_pooled, se_pooled, k, total_n,
                    aggregation_method, evidence_level,
                )

            compiled += 1

    return compiled


# ============================================================================
#  STEP 7: Reset (optional — wipe evidence/edges before reload)
# ============================================================================
def reset_evidence(engine) -> None:
    """Wipe edge_evidence_v1, edges_v1, and related tables for clean reload."""
    with engine.begin() as conn:
        for table in ["edges_v1", "edge_evidence_v1", "edge_param_builds_v1",
                       "study_annotations_v1", "study_annotations_raw_v1",
                       "review_tasks", "extraction_runs",
                       "instrument_evidence_v1", "population_norms_v1",
                       "temporal_evidence_v1", "node_priors_v1"]:
            try:
                result = conn.execute(text(f'DELETE FROM "{table}"'))
                logger.info("Cleared %s: %d rows removed", table, result.rowcount)
            except Exception as exc:
                logger.debug("Could not clear %s: %s", table, exc)


# ============================================================================
#  STEP 8: Verify final state
# ============================================================================
def verify_state(engine) -> None:
    """Print a comprehensive summary of the database state after loading."""
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
            text("SELECT study_id, doi, study_design, year FROM study_registry_v1 ORDER BY study_id")
        )
        studies = result.fetchall()
        print(f"\n  study_registry_v1: {len(studies)} rows")
        for s in studies:
            print(f"    {s[0]:30s} DOI={s[1]} ({s[2]}, {s[3]})")

        # Edge evidence with harmonized columns
        result = conn.execute(text("SELECT COUNT(*) FROM edge_evidence_v1"))
        evidence_count = result.scalar()
        result2 = conn.execute(text(
            "SELECT COUNT(*) FROM edge_evidence_v1 "
            "WHERE harmonized_beta IS NOT NULL AND harmonized_se IS NOT NULL"
        ))
        harmonized_count = result2.scalar()
        print(f"\n  edge_evidence_v1: {evidence_count} rows ({harmonized_count} harmonized)")

        if harmonized_count > 0:
            result = conn.execute(
                text("""
                    SELECT edge_relation_id, study_id,
                           harmonized_beta, harmonized_se, harmonized_scale,
                           N_effect, harmonization_status
                    FROM edge_evidence_v1
                    WHERE harmonized_beta IS NOT NULL
                    ORDER BY edge_relation_id, study_id
                """)
            )
            for row in result:
                print(
                    f"    {row[1]:25s} × {row[0]:40s} β={row[2]:+.4f} SE={row[3]:.4f} "
                    f"scale={row[4]} n={row[5]} status={row[6]}"
                )

        # Compiled edges
        result = conn.execute(text("SELECT COUNT(*) FROM edges_v1"))
        edges_count = result.scalar()
        print(f"\n  edges_v1 (compiled): {edges_count} rows")

        if edges_count > 0:
            result = conn.execute(
                text("""
                    SELECT edge_relation_id, beta_mean, beta_se,
                           aggregation_method, evidence_level, total_n
                    FROM edges_v1
                    WHERE active = 1
                    ORDER BY edge_relation_id
                """)
            )
            for row in result:
                print(
                    f"    {row[0]:40s} β={row[1]:+.4f} SE={row[2]:.4f} "
                    f"method={row[3]} level={row[4]} n={row[5]}"
                )

        # Action catalog
        result = conn.execute(text("SELECT COUNT(*) FROM action_catalog_v1"))
        action_count = result.scalar()
        print(f"\n  action_catalog_v1: {action_count} rows")

        # Auxiliary family tables
        print("\n  --- Auxiliary Evidence Families ---")
        for aux_table, label in [
            ("instrument_evidence_v1", "Instrument Evidence"),
            ("population_norms_v1", "Population Norms"),
            ("temporal_evidence_v1", "Temporal Evidence"),
            ("node_priors_v1", "Context Priors"),
        ]:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{aux_table}"'))
                cnt = result.scalar()
                print(f"  {label:30s} ({aux_table}): {cnt} rows")
            except Exception:
                print(f"  {label:30s} ({aux_table}): TABLE MISSING")

        # Coverage summary
        result = conn.execute(text(
            "SELECT COUNT(DISTINCT edge_relation_id) FROM edge_evidence_v1 "
            "WHERE harmonized_beta IS NOT NULL"
        ))
        edges_covered = result.scalar()
        print(f"\n  Evidence coverage: {edges_covered}/{edge_def_count} edges have evidence")
        print(f"  Compiled edges:    {edges_count}/{edges_covered} evidence edges compiled")

        print()
        print("=" * 70)
        ok = harmonized_count > 0 and edges_count > 0 and action_count > 0
        if ok:
            print("  ✅ PIPELINE READY: evidence → edges → actions all populated")
        else:
            problems = []
            if harmonized_count == 0:
                problems.append("NO HARMONIZED EVIDENCE")
            if edges_count == 0:
                problems.append("NO COMPILED EDGES")
            if action_count == 0:
                problems.append("NO ACTIONS")
            print(f"  ❌ ISSUES: {', '.join(problems)}")
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
    parser.add_argument("--reset", action="store_true", help="Wipe evidence/edges before reload")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    print("=" * 70)
    print("  CRCI: Loading Evidence Into Database")
    print("=" * 70)
    print(f"  Database: {db_url}")
    print(f"  Dry run:  {args.dry_run}")
    print(f"  Reset:    {args.reset}")
    print()

    engine = init_db()

    # Optional reset
    if args.reset and not args.dry_run:
        print("[0/10] Resetting evidence and edge tables...")
        reset_evidence(engine)
        print("  → Tables cleared\n")

    # Step 1: Reseed edge definitions
    print("[1/10] Reseeding edge_relations_definitions_v1 from EDGE_REGISTRY.csv...")
    n_edges = reseed_edge_definitions(engine, dry_run=args.dry_run)
    print(f"  → {n_edges} edge definitions loaded")

    # Step 1b: Reseed node + instrument definitions from authoritative registries
    print("\n[1b/10] Reseeding node + instrument definitions from registries...")
    n_nodes, n_insts = reseed_node_and_instrument_definitions(engine, dry_run=args.dry_run)
    print(f"  → {n_nodes} node definitions, {n_insts} instrument definitions loaded")

    # Step 1c: Reseed measure + pathway definitions from authoritative registries
    print("\n[1c/10] Reseeding measure + pathway definitions from registries...")
    n_measures, n_pathways = reseed_measure_and_pathway_definitions(engine, dry_run=args.dry_run)
    print(f"  → {n_measures} measure definitions, {n_pathways} pathway definitions loaded")

    # Step 2: Clean up old entries
    print("\n[2/10] Cleaning up legacy study entries...")
    cleanup_old_entries(engine, dry_run=args.dry_run)

    # Step 3: Register studies
    print("\n[3/10] Registering studies in study_registry_v1...")
    n_studies = register_studies(engine, dry_run=args.dry_run)
    print(f"  → {n_studies} new studies registered")

    # Step 4: Load CSV evidence
    print("\n[4/10] Loading CSV evidence into edge_evidence_v1...")
    n_evidence = load_csv_evidence(engine, dry_run=args.dry_run)
    print(f"  → {n_evidence} evidence rows loaded")

    # Step 4b: Load auxiliary family CSVs
    print("\n[4b/10] Loading auxiliary family CSVs (context_priors, instrument, norms, temporal)...")
    family_results = load_family_csvs(engine, dry_run=args.dry_run)
    for fam, count in family_results.items():
        print(f"  → {fam}: {count} rows loaded")

    # Step 4c: Harmonize scales to Cohen's d
    print("\n[4c/10] Harmonizing mean_diff_raw → cohens_d (SD borrowing from population_norms)...")
    n_harmonized = harmonize_scales_to_cohens_d(engine, dry_run=args.dry_run)
    print(f"  → {n_harmonized} rows converted to cohens_d")

    # Step 4d: Apply 7-layer SE_eff calibration (P3-8)
    print("\n[4d/10] Applying 7-layer SE_eff calibration (Formula P3-8)...")
    n_calibrated = apply_se_eff_calibration(engine, dry_run=args.dry_run)
    print(f"  → {n_calibrated} rows SE-calibrated")

    # Step 5: Seed action catalog
    print("\n[5/10] Seeding action_catalog_v1...")
    n_actions = seed_action_catalog(engine, dry_run=args.dry_run)
    print(f"  → {n_actions} actions loaded")

    # Step 5b: Seed dose bridges
    print("\n[5b/10] Seeding dose_bridges_v1...")
    n_bridges = seed_dose_bridges(engine, dry_run=args.dry_run)
    print(f"  → {n_bridges} dose bridges loaded")

    # Step 6: Compile edges
    print("\n[6/10] Compiling evidence → edges_v1 (IVW aggregation)...")
    n_compiled = compile_edges(engine, dry_run=args.dry_run)
    print(f"  → {n_compiled} edges compiled")

    # Step 7: Verify
    if not args.dry_run:
        print("\n[7/10] Verifying...")
        verify_state(engine)

    return 0


if __name__ == "__main__":
    sys.exit(main())
