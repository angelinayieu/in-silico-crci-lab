#!/usr/bin/env python3
"""
Sync registries/*.csv → crci/database/seeds/*.csv

The human-authored registries use a *domain-expert* column vocabulary.
The seed CSVs use an *engineering/ORM* column vocabulary matching the DB schema.
This script bridges the gap by mapping registry columns → seed columns with
sensible defaults for any seed columns that have no registry equivalent.

Existing seed rows are **preserved**; new rows from the registry are **appended**.
If a registry row already exists in the seed (same PK), the seed row wins —
hand-tuned seed values are never overwritten.

Usage:
    python scripts/sync_registries_to_seeds.py              # Dry-run (show what would change)
    python scripts/sync_registries_to_seeds.py --apply       # Write updated seed CSVs
    python scripts/sync_registries_to_seeds.py --apply --force  # Overwrite existing seed rows too

After running with --apply, follow up with:
    python scripts/load_seeds_sqlite.py      # Load updated seeds into DB
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRIES_DIR = PROJECT_ROOT / "registries"
SEEDS_DIR = PROJECT_ROOT / "crci" / "database" / "seeds"


# ═══════════════════════════════════════════════════════════════════════════
#  NODES: NODE_REGISTRY.csv → nodes.csv
# ═══════════════════════════════════════════════════════════════════════════

def _derive_node_role(row: dict) -> str:
    """Map node_layer + clinical_domain → node_role."""
    layer = str(row.get("node_layer", "")).strip()
    domain = str(row.get("clinical_domain", "")).strip().lower()
    is_obs = str(row.get("is_observable", "")).strip()

    # Layer 0 = exogenous inputs
    if layer == "0":
        return "exogenous"
    # Observable symptoms/behaviors
    if is_obs == "1" and domain in ("symptom", "behavioral", "behaviour", "behavior"):
        return "symptom"
    if domain in ("cognitive", "cognitive_outcomes"):
        return "outcome"
    if domain in ("biomarker", "biomarkers"):
        return "biomarker"
    if domain in ("behavioral", "behaviour", "behavior"):
        return "behavior"
    if domain in ("pathway", "pathways"):
        return "pathway"
    if domain in ("treatment_exposure", "treatment"):
        return "exogenous"
    if domain in ("symptom", "symptoms"):
        return "symptom"
    if domain in ("context", "demographic"):
        return "context"
    # Fallback
    return "latent" if str(row.get("is_latent", "")).strip() == "1" else "observable"


def _derive_node_subtype(row: dict) -> str:
    """Map is_observable/is_latent → node_subtype."""
    is_lat = str(row.get("is_latent", "0")).strip()
    if is_lat == "1":
        return "latent_construct"
    domain = str(row.get("clinical_domain", "")).strip().lower()
    if domain in ("biomarker", "biomarkers"):
        return "biomarker"
    if domain in ("behavioral", "behaviour", "behavior"):
        return "behavioral"
    if domain in ("cognitive", "cognitive_outcomes"):
        return "cognitive"
    return "observable"


def _derive_node_symbol(node_id: str) -> str:
    """Generate a short LaTeX-style symbol from the node_id."""
    # NODE_BIO_IL6 → IL6, NODE_COG_EXEC_PLANNING → EXEC_PLAN
    parts = node_id.replace("NODE_", "").split("_")
    # Drop category prefixes like BIO, COG, SYM, BEH, EXO, PATH
    skip = {"BIO", "COG", "SYM", "BEH", "EXO", "PATH"}
    meaningful = [p for p in parts if p not in skip]
    if not meaningful:
        meaningful = parts[-1:]
    return "_".join(meaningful[:3]).lower()


def _derive_state_space(row: dict) -> str:
    """Map orientation + unit → default_state_space."""
    orient = str(row.get("orientation", "")).strip().upper()
    unit = str(row.get("unit_of_measure", "")).strip().lower()
    if orient == "CATEGORICAL" or unit == "categorical":
        return "categorical"
    return "z"


def _derive_state_update_scale(row: dict) -> str:
    """Map clinical_domain → default temporal update scale."""
    domain = str(row.get("clinical_domain", "")).strip().lower()
    layer = str(row.get("node_layer", "")).strip()
    if layer == "0":
        return "treatment_cycle"
    if domain in ("biomarker", "biomarkers"):
        return "daily"
    if domain in ("behavioral", "behaviour", "behavior"):
        return "weekly"
    if domain in ("symptom", "symptoms"):
        return "weekly"
    if domain in ("cognitive", "cognitive_outcomes"):
        return "study_window"
    if domain in ("pathway", "pathways"):
        return "weekly"
    return "weekly"


def _derive_window_days(row: dict) -> int:
    """Map clinical_domain → default observation window."""
    domain = str(row.get("clinical_domain", "")).strip().lower()
    layer = str(row.get("node_layer", "")).strip()
    if layer == "0":
        return 1
    if domain in ("biomarker", "biomarkers"):
        return 1
    if domain in ("behavioral", "behaviour", "behavior"):
        return 7
    if domain in ("symptom", "symptoms"):
        return 7
    if domain in ("cognitive", "cognitive_outcomes"):
        return 30
    if domain in ("pathway", "pathways"):
        return 14
    return 7


def _derive_min_obs_window(row: dict) -> int:
    """Minimum observation window — typically half of default."""
    return max(1, _derive_window_days(row) // 2)


def _derive_allowed_source_types(row: dict) -> str:
    """Map is_observable + domain → allowed source types JSON."""
    domain = str(row.get("clinical_domain", "")).strip().lower()
    is_obs = str(row.get("is_observable", "")).strip()
    layer = str(row.get("node_layer", "")).strip()
    if layer == "0":
        return '["clinical_record"]'
    if domain in ("biomarker", "biomarkers"):
        return '["measure"]'
    if is_obs == "1":
        return '["instrument"]'
    if domain in ("cognitive", "cognitive_outcomes"):
        return '["instrument", "measure"]'
    return '["instrument"]'


def _derive_is_actionable(row: dict) -> int:
    """Behavioral nodes are typically actionable inputs."""
    domain = str(row.get("clinical_domain", "")).strip().lower()
    if domain in ("behavioral", "behaviour", "behavior"):
        return 1
    return 0


def _node_domain_from_clinical(row: dict) -> str:
    """Map clinical_domain → node_domain."""
    domain = str(row.get("clinical_domain", "")).strip().lower()
    mapping = {
        "treatment_exposure": "treatment",
        "behavioral": "behavior",
        "behaviour": "behavior",
        "behavior": "behavior",
        "biomarker": "biomarker",
        "biomarkers": "biomarker",
        "symptom": "symptom",
        "symptoms": "symptom",
        "cognitive": "cognition",
        "cognitive_outcomes": "cognition",
        "pathway": "pathway",
        "pathways": "pathway",
        "context": "context",
        "demographic": "context",
    }
    return mapping.get(domain, domain or "unknown")


def convert_node(reg: dict) -> dict:
    """Convert a NODE_REGISTRY row → nodes.csv seed row."""
    orient_raw = str(reg.get("orientation", "")).strip()
    # Normalize orientation
    orient = orient_raw.lower().replace(" ", "_") if orient_raw else "higher_worse"

    return {
        "node_id": reg["node_id"],
        "node_label": reg.get("node_label", ""),
        "node_symbol": _derive_node_symbol(reg["node_id"]),
        "node_role": _derive_node_role(reg),
        "orientation": orient,
        "node_domain": _node_domain_from_clinical(reg),
        "node_subtype": _derive_node_subtype(reg),
        "default_state_space": _derive_state_space(reg),
        "state_update_scale": _derive_state_update_scale(reg),
        "default_window_days": _derive_window_days(reg),
        "min_observation_window_days": _derive_min_obs_window(reg),
        "allowed_source_types_json": _derive_allowed_source_types(reg),
        "is_actionable_input_node": _derive_is_actionable(reg),
        "active": reg.get("active", 1),
        "version": reg.get("version", 1),
        "description": reg.get("description", ""),
        "notes": reg.get("notes", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  EDGES: EDGE_REGISTRY.csv → edge_relations.csv
# ═══════════════════════════════════════════════════════════════════════════

def _derive_module(edge_id: str) -> str:
    """Derive module letter from edge_relation_id convention."""
    # ER_CHEMO_ACTIVITY → A (exogenous), etc.
    # Convention: edges starting with NODE_EXO → module A
    # Otherwise use first letter after ER_ if pattern matches ER_[A-D]_
    m = re.match(r"^ER_([A-Z])_", edge_id)
    if m:
        return m.group(1)
    return "A"


def _sign_to_direction(sign: str) -> int:
    """Map expected_sign → default_effect_direction."""
    s = str(sign).strip().lower()
    if s in ("negative", "-1", "neg"):
        return -1
    if s in ("positive", "1", "+1", "pos"):
        return 1
    return 0


def convert_edge(reg: dict) -> dict:
    """Convert an EDGE_REGISTRY row → edge_relations.csv seed row."""
    mechanism = reg.get("mechanism_description", "") or ""
    label = mechanism[:80] if mechanism else reg.get("edge_relation_id", "")

    return {
        "edge_relation_id": reg["edge_relation_id"],
        "module": _derive_module(reg["edge_relation_id"]),
        "edge_family": reg.get("primary_pathway", ""),
        "node_x": reg.get("source_node_id", ""),
        "node_y": reg.get("target_node_id", ""),
        "relation_label": label,
        "canonical_statement": mechanism,
        "relation_type": reg.get("relation_type", "causal"),
        "default_effect_direction": _sign_to_direction(reg.get("expected_sign", "")),
        "allowed_measure_ids_json": "",
        "allowed_upstream_instruments_json": "",
        "default_temporal_family": reg.get("functional_form", "linear"),
        "notes": reg.get("notes", "N/A"),
        "version": reg.get("version", 1),
        "active": reg.get("active", 1),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  INSTRUMENTS: INSTRUMENT_REGISTRY.csv → instruments.csv
# ═══════════════════════════════════════════════════════════════════════════

def _scoring_to_higher_means(scoring: str) -> str:
    """Map scoring_direction → higher_means_pre_alignment."""
    s = str(scoring).strip().lower()
    if s in ("higher_better", "higher better"):
        return "better"
    if s in ("higher_worse", "higher worse"):
        return "worse"
    return "worse"


def _scoring_to_directionality(scoring: str) -> str:
    """Map scoring_direction → directionality_after_alignment."""
    s = str(scoring).strip().lower()
    if "better" in s:
        return "higher_better"
    return "higher_worse"


def _derive_direction_rule_id(inst_id: str, scoring: str) -> str:
    """Generate direction rule ID."""
    s = str(scoring).strip().lower()
    if "better" in s:
        return f"DIR_REVERSE"
    return f"DIR_HIGHER_WORSE"


def _derive_instrument_kind(inst_type: str) -> str:
    """Map instrument_type → instrument_kind."""
    t = str(inst_type).strip().lower()
    kind_map = {
        "pro": "questionnaire",
        "questionnaire": "questionnaire",
        "self-report": "questionnaire",
        "self_report": "questionnaire",
        "clinician_rated": "clinician_rating",
        "clinician-rated": "clinician_rating",
        "neuropsychological": "neuropsych_test",
        "neuropsych_test": "neuropsych_test",
        "neuropsych": "neuropsych_test",
        "performance": "neuropsych_test",
        "performance_test": "neuropsych_test",
        "composite": "composite",
        "wearable": "device",
        "device": "device",
        "biomarker_assay": "lab_assay",
        "lab": "lab_assay",
    }
    return kind_map.get(t, "questionnaire")


def _derive_instrument_method(inst_type: str) -> str:
    """Map instrument_type → instrument_method."""
    t = str(inst_type).strip().lower()
    if t in ("pro", "questionnaire", "self-report", "self_report"):
        return "self_report"
    if t in ("clinician_rated", "clinician-rated"):
        return "clinician_rated"
    if t in ("neuropsychological", "neuropsych_test", "neuropsych", "performance",
             "performance_test"):
        return "performance_test"
    if t in ("wearable", "device"):
        return "device_measured"
    if t in ("biomarker_assay", "lab"):
        return "lab_assay"
    return "self_report"


def _derive_time_aggregation(window_days: str) -> str:
    """Map time_window_days → time_aggregation."""
    try:
        d = int(float(str(window_days).strip()))
    except (ValueError, TypeError):
        return "point_in_time"
    if d <= 1:
        return "point_in_time"
    if d <= 7:
        return "weekly"
    if d <= 14:
        return "biweekly"
    if d <= 31:
        return "monthly"
    return "cumulative"


def _derive_raw_scale_spec(row: dict) -> str:
    """Build raw scale spec from range columns."""
    lo = row.get("total_score_range_min", "")
    hi = row.get("total_score_range_max", "")
    if lo and hi:
        return f"{lo}-{hi}"
    return "unbounded"


def _derive_raw_unit(row: dict) -> str:
    """Derive raw_unit from instrument characteristics."""
    resp = str(row.get("response_type", "")).strip().lower()
    if resp in ("likert",):
        return "likert_score"
    if resp in ("nrs", "vas"):
        return "mean_score"
    if resp in ("binary", "dichotomous"):
        return "binary"
    return "total_score"


def _derive_thresholds_json(row: dict) -> str:
    """Build thresholds from cutoff info."""
    cutoff = row.get("clinical_cutoff_value", "")
    direction = row.get("clinical_cutoff_direction", "")
    if cutoff and cutoff != "N/A" and direction and direction != "N/A":
        return json.dumps({"clinical_cutoff": cutoff})
    return ""


def convert_instrument(reg: dict) -> dict:
    """Convert an INSTRUMENT_REGISTRY row → instruments.csv seed row."""
    scoring = reg.get("scoring_direction", "higher_worse")
    inst_type = reg.get("instrument_type", "PRO")

    # Use maps_to_node_id (single) — may need updating if node IDs differ
    maps_to = reg.get("maps_to_node_id", "")

    return {
        "instrument_id": reg["instrument_id"],
        "instrument_label": reg.get("instrument_name", ""),
        "maps_to_node_id": maps_to,
        "instrument_kind": _derive_instrument_kind(inst_type),
        "instrument_method": _derive_instrument_method(inst_type),
        "recall_window_days": reg.get("time_window_days", "7"),
        "time_aggregation": _derive_time_aggregation(reg.get("time_window_days", "")),
        "raw_scale_spec": _derive_raw_scale_spec(reg),
        "raw_unit": _derive_raw_unit(reg),
        "higher_means_pre_alignment": _scoring_to_higher_means(scoring),
        "direction_rule_id": _derive_direction_rule_id(reg["instrument_id"], scoring),
        "directionality_after_alignment": _scoring_to_directionality(scoring),
        "adapter_output_kind": "z",
        "adapter_spec_id": "",
        "required_fields_json": '{"total_score": "required"}',
        "thresholds_json": _derive_thresholds_json(reg),
        "preferred_norm_ref_id": reg.get("norm_id", ""),
        "preferred_noise_id": reg.get("noise_id", ""),
        "compatibility_group_id": "",
        "active": reg.get("active", 1),
        "version": reg.get("version", 1),
        "description": (
            f"{reg.get('instrument_name', '')} — "
            f"{reg.get('item_count', '?')}-item {inst_type}"
        ),
        "notes": reg.get("notes", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  MEASURES: MEASURE_REGISTRY.csv → measures.csv
# ═══════════════════════════════════════════════════════════════════════════

def _derive_measure_kind(measure_type: str) -> str:
    """Map measure_type → measure_kind."""
    t = str(measure_type).strip().lower()
    kind_map = {
        "total_score": "score",
        "subscale": "subscale",
        "biomarker": "analyte",
        "direct_measure": "direct",
        "device_metric": "device",
        "composite": "composite",
        "derived": "derived",
        "ratio": "ratio",
        "change_score": "change",
    }
    return kind_map.get(t, "score")


def _derive_analyte(row: dict) -> str:
    """Derive analyte from measure_id or assay_method."""
    mid = str(row.get("measure_id", "")).upper()
    if "CORTISOL" in mid:
        return "cortisol"
    if "IL6" in mid or "IL_6" in mid:
        return "IL-6"
    if "TNF" in mid:
        return "TNF-alpha"
    if "CRP" in mid:
        return "CRP"
    if "BDNF" in mid:
        return "BDNF"
    if "8OHDG" in mid:
        return "8-OHdG"
    if "MDA" in mid:
        return "MDA"
    return ""


def _derive_specimen(row: dict) -> str:
    """Derive specimen_or_device from sample_type or measure_type."""
    sample = str(row.get("sample_type", "")).strip().lower()
    mtype = str(row.get("measure_type", "")).strip().lower()
    if sample in ("blood", "serum", "plasma"):
        return "blood_sample"
    if sample in ("saliva",):
        return "saliva_sample"
    if sample in ("urine",):
        return "urine_sample"
    if sample in ("csf",):
        return "csf_sample"
    if mtype in ("biomarker",):
        return "blood_sample"
    if mtype == "device_metric":
        return "wearable_device"
    return "questionnaire"


def _derive_biospecimen(row: dict) -> str:
    """Derive biospecimen from sample_type."""
    sample = str(row.get("sample_type", "")).strip().lower()
    if sample in ("blood", "serum", "plasma", "saliva", "urine", "csf"):
        return sample
    return ""


def _derive_proxy_type(row: dict) -> str:
    """Derive proxy_type from measure characteristics."""
    mtype = str(row.get("measure_type", "")).strip().lower()
    if mtype in ("biomarker", "direct_measure"):
        return "direct"
    if mtype == "subscale":
        return "subscale"
    return "self_report"


def _derive_measure_direction_rule(scoring: str) -> str:
    """Map scoring_direction → direction_rule_id for measures."""
    s = str(scoring).strip().lower()
    if "better" in s:
        return "DIR_REVERSE"
    if "categorical" in s:
        return "DIR_NONE"
    return "DIR_HIGHER_WORSE"


def _derive_measure_family(row: dict) -> str:
    """Derive measure_family_id from parent instrument or measure_id."""
    parent = row.get("parent_instrument_id", "")
    if parent and parent != "N/A":
        return f"FAM_{parent.replace('INST_', '')}"
    # Use first part of measure_id
    mid = str(row.get("measure_id", ""))
    parts = mid.replace("MEAS_", "").split("_")
    return f"FAM_{parts[0]}" if parts else "FAM_UNKNOWN"


def _derive_compatibility_group(row: dict) -> str:
    """Derive compatibility_group_id from measure characteristics.

    Groups measures that are interchangeable (e.g., MEAS_IL6_SERUM and
    MEAS_IL6_PLASMA both → COMPAT_IL6).
    """
    mid = str(row.get("measure_id", "")).upper()
    # Known biomarker patterns
    for marker in ["IL6", "CRP", "TNF", "BDNF", "CORTISOL", "8OHDG", "MDA",
                    "GH2AX", "NFL", "P16", "TELOMERE", "GLUCOSE", "HBA1C",
                    "INSULIN", "SHANNON", "HRV", "VO2", "GRIP", "6MWT"]:
        if marker in mid:
            return f"COMPAT_{marker}"
    # Fall back to first meaningful segment
    parts = mid.replace("MEAS_", "").split("_")
    return f"COMPAT_{parts[0]}" if parts else "COMPAT_UNKNOWN"


def convert_measure(reg: dict) -> dict:
    """Convert a MEASURE_REGISTRY row → measures.csv seed row."""
    scoring = reg.get("scoring_direction", "higher_worse")

    return {
        "measure_id": reg["measure_id"],
        "measure_label": reg.get("measure_name", ""),
        "maps_to_node_id": reg.get("maps_to_node_id", ""),
        "measure_kind": _derive_measure_kind(reg.get("measure_type", "")),
        "analyte": _derive_analyte(reg),
        "specimen_or_device": _derive_specimen(reg),
        "biospecimen": _derive_biospecimen(reg),
        "device_type": "",
        "proxy_type": _derive_proxy_type(reg),
        "time_aggregation": _derive_time_aggregation(reg.get("time_resolution_days", "")),
        "raw_unit": reg.get("unit_of_measure", "score"),
        "value_transform_spec": "",
        "direction_rule_id": _derive_measure_direction_rule(scoring),
        "directionality_after_alignment": _scoring_to_directionality(scoring),
        "measure_family_id": _derive_measure_family(reg),
        "compatibility_group_id": _derive_compatibility_group(reg),
        "effective_window_days": reg.get("time_resolution_days", "7"),
        "min_required_samples": 1,
        "required_fields_json": '{"value": "required"}',
        "preferred_norm_ref_id": reg.get("norm_id", ""),
        "preferred_noise_id": reg.get("noise_id", ""),
        "active": reg.get("active", 1),
        "version": reg.get("version", 1),
        "description": reg.get("measure_name", ""),
        "notes": reg.get("notes", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PATHWAYS: PATHWAY_REGISTRY.csv → pathways.csv
# ═══════════════════════════════════════════════════════════════════════════

def _proxy_qual_to_numeric(qual: str) -> float:
    """Map proxy_r_squared_qualitative → numeric proxy_r_squared."""
    q = str(qual).strip().lower()
    mapping = {
        "high": 0.45,
        "moderate-high": 0.35,
        "moderate": 0.25,
        "moderate-low": 0.18,
        "low-moderate": 0.18,
        "low": 0.12,
        "very_low": 0.05,
    }
    return mapping.get(q, 0.20)


def _derive_edge_relation_ids(pathway_id: str, edge_registry: list[dict]) -> str:
    """Find all edges whose primary_pathway matches this pathway_id."""
    matching = [
        e["edge_relation_id"] for e in edge_registry
        if e.get("primary_pathway", "").strip() == pathway_id
    ]
    return json.dumps(matching) if matching else "[]"


def convert_pathway(reg: dict, edge_registry: list[dict]) -> dict:
    """Convert a PATHWAY_REGISTRY row → pathways.csv seed row."""
    return {
        "pathway_id": reg["pathway_id"],
        "pathway_label": reg.get("pathway_label", ""),
        "tier": reg.get("tier", ""),
        "entry_node_ids_json": reg.get("entry_node_ids_json", "[]"),
        "exit_node_ids_json": reg.get("exit_node_ids_json", "[]"),
        "intermediate_node_ids_json": reg.get("intermediate_node_ids_json", "[]"),
        "edge_relation_ids_json": _derive_edge_relation_ids(
            reg["pathway_id"], edge_registry
        ),
        "cognitive_domain_specificity_json": reg.get(
            "cognitive_domain_specificity_json", "{}"
        ),
        "best_proxy_biomarker": reg.get("best_proxy_biomarker", ""),
        "proxy_r_squared": _proxy_qual_to_numeric(
            reg.get("proxy_r_squared_qualitative", "")
        ),
        "causal_evidence_level": reg.get("causal_evidence_level", ""),
        "key_citation": reg.get("key_citation", ""),
        "version": reg.get("version", 1),
        "active": reg.get("active", 1),
        "notes": reg.get("notes", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  GENERIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def read_csv(path: Path) -> list[dict]:
    """Read CSV into list of dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Write list of dicts to CSV with given field order."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_rows(
    existing: list[dict],
    new: list[dict],
    pk: str,
    *,
    force: bool = False,
) -> tuple[list[dict], int, int]:
    """Merge new rows into existing, keyed by pk.

    Returns (merged_rows, added_count, updated_count).
    """
    by_pk = {row[pk]: row for row in existing}
    added = 0
    updated = 0

    for row in new:
        key = row[pk]
        if key not in by_pk:
            by_pk[key] = row
            added += 1
        elif force:
            by_pk[key] = row
            updated += 1
        # else: skip — existing seed row wins

    merged = list(by_pk.values())
    return merged, added, updated


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

SYNC_SPECS = [
    {
        "label": "Nodes",
        "registry": REGISTRIES_DIR / "NODE_REGISTRY.csv",
        "seed": SEEDS_DIR / "nodes.csv",
        "pk": "node_id",
        "convert": lambda reg, **kw: convert_node(reg),
        # Replace mode: the old 20-row seed uses stale NODE_CRP-style IDs
        # while the registry (and DB) uses NODE_BIO_CRP-style IDs.
        # Zero PK overlap → merge would create 83 duplicates.
        # Replace with registry data only (DB already has the 63 registry nodes).
        "replace": True,
        "fieldnames": [
            "node_id", "node_label", "node_symbol", "node_role", "orientation",
            "node_domain", "node_subtype", "default_state_space",
            "state_update_scale", "default_window_days",
            "min_observation_window_days", "allowed_source_types_json",
            "is_actionable_input_node", "active", "version", "description", "notes",
        ],
    },
    {
        "label": "Edges",
        "registry": REGISTRIES_DIR / "EDGE_REGISTRY.csv",
        "seed": SEEDS_DIR / "edge_relations.csv",
        "pk": "edge_relation_id",
        "convert": lambda reg, **kw: convert_edge(reg),
        "fieldnames": [
            "edge_relation_id", "module", "edge_family", "node_x", "node_y",
            "relation_label", "canonical_statement", "relation_type",
            "default_effect_direction", "allowed_measure_ids_json",
            "allowed_upstream_instruments_json", "default_temporal_family",
            "notes", "version", "active",
        ],
    },
    {
        "label": "Instruments",
        "registry": REGISTRIES_DIR / "INSTRUMENT_REGISTRY.csv",
        "seed": SEEDS_DIR / "instruments.csv",
        "pk": "instrument_id",
        "convert": lambda reg, **kw: convert_instrument(reg),
        "fieldnames": [
            "instrument_id", "instrument_label", "maps_to_node_id",
            "instrument_kind", "instrument_method", "recall_window_days",
            "time_aggregation", "raw_scale_spec", "raw_unit",
            "higher_means_pre_alignment", "direction_rule_id",
            "directionality_after_alignment", "adapter_output_kind",
            "adapter_spec_id", "required_fields_json", "thresholds_json",
            "preferred_norm_ref_id", "preferred_noise_id",
            "compatibility_group_id", "active", "version", "description", "notes",
        ],
    },
    {
        "label": "Measures",
        "registry": REGISTRIES_DIR / "MEASURE_REGISTRY.csv",
        "seed": SEEDS_DIR / "measures.csv",
        "pk": "measure_id",
        "convert": lambda reg, **kw: convert_measure(reg),
        "fieldnames": [
            "measure_id", "measure_label", "maps_to_node_id", "measure_kind",
            "analyte", "specimen_or_device", "biospecimen", "device_type",
            "proxy_type", "time_aggregation", "raw_unit", "value_transform_spec",
            "direction_rule_id", "directionality_after_alignment",
            "measure_family_id", "compatibility_group_id", "effective_window_days",
            "min_required_samples", "required_fields_json",
            "preferred_norm_ref_id", "preferred_noise_id", "active", "version",
            "description", "notes",
        ],
    },
    {
        "label": "Pathways",
        "registry": REGISTRIES_DIR / "PATHWAY_REGISTRY.csv",
        "seed": SEEDS_DIR / "pathways.csv",
        "pk": "pathway_id",
        "convert": None,  # special: needs edge_registry
        "fieldnames": [
            "pathway_id", "pathway_label", "tier", "entry_node_ids_json",
            "exit_node_ids_json", "intermediate_node_ids_json",
            "edge_relation_ids_json", "cognitive_domain_specificity_json",
            "best_proxy_biomarker", "proxy_r_squared", "causal_evidence_level",
            "key_citation", "version", "active", "notes",
        ],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync registries/*.csv → crci/database/seeds/*.csv"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write updated seed CSVs (default: dry-run)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing seed rows (default: preserve hand-tuned seeds)",
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n{'=' * 70}")
    print(f"  REGISTRY → SEED SYNC  [{mode}]")
    print(f"{'=' * 70}\n")

    # Pre-load edge registry for pathway conversion
    edge_registry = read_csv(REGISTRIES_DIR / "EDGE_REGISTRY.csv")

    total_added = 0
    total_updated = 0

    for spec in SYNC_SPECS:
        label = spec["label"]
        reg_path = spec["registry"]
        seed_path = spec["seed"]
        pk = spec["pk"]
        fieldnames = spec["fieldnames"]

        print(f"─── {label} ───")
        print(f"  Registry: {reg_path.name}")
        print(f"  Seed:     {seed_path.name}")

        # Read registry
        registry_rows = read_csv(reg_path)
        print(f"  Registry rows: {len(registry_rows)}")

        # Read existing seed (unless replace mode)
        replace_mode = spec.get("replace", False)
        if replace_mode:
            existing_rows = []
            print(f"  Existing seed rows: (replace mode — ignoring stale seed)")
        elif seed_path.exists():
            existing_rows = read_csv(seed_path)
            print(f"  Existing seed rows: {len(existing_rows)}")
        else:
            existing_rows = []
            print(f"  Existing seed rows: 0 (file not found)")

        # Convert
        if label == "Pathways":
            converted = [convert_pathway(r, edge_registry) for r in registry_rows]
        else:
            convert_fn = spec["convert"]
            converted = [convert_fn(r) for r in registry_rows]

        # Merge
        merged, added, updated = merge_rows(
            existing_rows, converted, pk, force=args.force,
        )
        total_added += added
        total_updated += updated

        print(f"  → {added} new rows to add", end="")
        if args.force:
            print(f", {updated} existing rows updated", end="")
        print(f" (total: {len(merged)})")

        if added == 0 and updated == 0:
            print(f"  ✓ Already in sync\n")
            continue

        if args.apply:
            # Sort by PK for stable ordering
            merged.sort(key=lambda r: r.get(pk, ""))
            write_csv(seed_path, merged, fieldnames)
            print(f"  ✓ Written to {seed_path.name}\n")
        else:
            # Show sample of new rows
            if added > 0 and converted:
                first_new = [r for r in converted if r[pk] not in
                             {e[pk] for e in existing_rows}]
                if first_new:
                    sample = first_new[0]
                    print(f"  Sample new row:")
                    print(f"    {pk}={sample[pk]}")
                    for k, v in list(sample.items())[:5]:
                        if k != pk:
                            print(f"    {k}={v}")
                    print(f"    ...")
            print()

    print(f"{'=' * 70}")
    print(f"  TOTAL: {total_added} rows to add, {total_updated} rows to update")
    print(f"{'=' * 70}")

    if not args.apply and total_added > 0:
        print(f"\n  ⚠ Dry-run only. Add --apply to write changes.")
        print(f"  After applying, run: python scripts/load_seeds_sqlite.py\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
