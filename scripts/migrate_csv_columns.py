#!/usr/bin/env python3
"""Migrate existing extracted CSV files from legacy column names to DB-aligned names.

This script renames column headers in all extracted CSV files under
data/manual_uploads/structured/ to match the DB table columns exactly.

Run once after the template alignment refactor. Creates .bak backup of each file.
"""
import csv
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STRUCTURED_DIR = PROJECT_ROOT / "data" / "manual_uploads" / "structured"

# ── Column rename maps per template type ──────────────────────────────────

EDGE_EVIDENCE_RENAMES = {
    "edge_id": "edge_relation_id",
    "beta_raw": "effect_value_reported",
    "se_raw": "se_reported",
    "effect_type_original": "effect_type_reported",
    "sample_size": "N_effect",
    "instrument_id": "upstream_instrument_id",
    "confidence_note": "notes",
    "ci_low": "ci_low_reported",
    "ci_high": "ci_high_reported",
    "sd_treatment": "sd_x",
    "sd_control": "sd_y",
    "cancer_validated": "cancer_validation_status",
    "se_derivation_method": "se_derivation_level",
}

# Columns to fold into extraction_snippet
EDGE_SNIPPET_SOURCES = ["outcome_directionality", "beta_sign_convention", "effect_size_context"]
# Columns to drop entirely (data goes elsewhere or is auto-derived)
EDGE_DROP = ["timepoint_weeks", "outcome_node_id"]

POPULATION_NORMS_RENAMES = {
    "mean": "mean_raw",
    "sd": "sd_raw",
    "sample_size": "N",
}

CONTEXT_PRIORS_RENAMES = {
    "prior_mean_z": "mean",
    "prior_sd_z": "sd",
}

TEMPORAL_EVIDENCE_RENAMES = {
    "edge_id": "edge_relation_id",
    "value": "effect",
    "sample_size": "N",
}

CORRELATION_RENAMES = {
    "biomarker_id_1": "node_a_id",
    "biomarker_id_2": "node_b_id",
    "correlation_r": "rho",
    "sample_size": "N",
}


def migrate_csv(csv_path: Path, renames: dict, drop_cols: list | None = None,
                snippet_sources: list | None = None) -> bool:
    """Rename columns in a CSV file in-place, creating a .bak backup.

    Returns True if changes were made.
    """
    drop_cols = drop_cols or []
    snippet_sources = snippet_sources or []

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        old_fieldnames = reader.fieldnames
        if not old_fieldnames:
            print(f"  SKIP (empty): {csv_path}")
            return False

        rows = list(reader)

    # Check if any renames apply
    applicable = {old: new for old, new in renames.items() if old in old_fieldnames}
    applicable_drops = [c for c in drop_cols if c in old_fieldnames]
    applicable_snippets = [c for c in snippet_sources if c in old_fieldnames]

    if not applicable and not applicable_drops and not applicable_snippets:
        print(f"  SKIP (already migrated): {csv_path.name}")
        return False

    # Build new fieldnames
    new_fieldnames = []
    for col in old_fieldnames:
        if col in applicable:
            new_fieldnames.append(applicable[col])
        elif col in applicable_drops or col in applicable_snippets:
            continue  # drop these columns
        else:
            new_fieldnames.append(col)

    # Add extraction_snippet if we're folding snippet sources AND it's not already there
    if applicable_snippets and "extraction_snippet" not in new_fieldnames:
        new_fieldnames.append("extraction_snippet")

    # Transform rows
    new_rows = []
    for row in rows:
        new_row = {}
        for col in old_fieldnames:
            val = row.get(col, "")
            if col in applicable:
                new_row[applicable[col]] = val
            elif col in applicable_drops:
                pass  # drop
            elif col in applicable_snippets:
                pass  # handled below
            else:
                new_row[col] = val

        # Fold snippet sources into extraction_snippet
        if applicable_snippets:
            existing_snippet = new_row.get("extraction_snippet", "")
            parts = [existing_snippet] if existing_snippet else []
            for src_col in applicable_snippets:
                v = row.get(src_col, "").strip()
                if v:
                    if src_col == "effect_size_context":
                        parts.append(v)
                    else:
                        parts.append(f"{src_col}={v}")
            new_row["extraction_snippet"] = "; ".join(parts) if parts else ""

        new_rows.append(new_row)

    # Backup original
    bak_path = csv_path.with_suffix(".csv.bak")
    shutil.copy2(csv_path, bak_path)

    # Write migrated file
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    changes = list(applicable.items())
    print(f"  MIGRATED: {csv_path.name} — {len(changes)} renames, "
          f"{len(applicable_drops)} drops, {len(applicable_snippets)} snippet folds")
    for old, new in changes:
        print(f"    {old} → {new}")
    return True


def migrate_instrument_evidence(csv_path: Path) -> bool:
    """Special handler: reliability_value + reliability_type → separate DB columns."""
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        old_fieldnames = reader.fieldnames
        if not old_fieldnames:
            return False
        rows = list(reader)

    # Check if already migrated
    if "cronbachs_alpha" in old_fieldnames:
        print(f"  SKIP (already migrated): {csv_path.name}")
        return False

    # New columns: doi, instrument_id, instrument_name, instrument_subscale,
    #   cronbachs_alpha, se_alpha, test_retest_reliability, factor_loading_mean,
    #   sem_value, N, cancer_type, treatment_phase, cancer_validated, provenance_ref, notes
    new_fieldnames = [
        "doi", "instrument_id", "instrument_name", "instrument_subscale",
        "cronbachs_alpha", "se_alpha", "test_retest_reliability",
        "factor_loading_mean", "sem_value", "N",
        "cancer_type", "treatment_phase", "cancer_validated",
        "provenance_ref", "notes",
    ]

    new_rows = []
    for row in rows:
        new_row = {col: "" for col in new_fieldnames}
        new_row["doi"] = row.get("doi", "")
        new_row["instrument_id"] = row.get("instrument_id", "")
        new_row["instrument_name"] = ""
        new_row["instrument_subscale"] = ""

        # Map reliability_value based on reliability_type
        rel_type = row.get("reliability_type", "").strip().lower()
        rel_val = row.get("reliability_value", "").strip()

        if rel_type in ("cronbachs_alpha", "cronbach", "alpha"):
            new_row["cronbachs_alpha"] = rel_val
        elif rel_type in ("test_retest", "test-retest", "icc", "test_retest_icc"):
            new_row["test_retest_reliability"] = rel_val
        elif rel_val:
            # Default: put in cronbachs_alpha
            new_row["cronbachs_alpha"] = rel_val

        new_row["se_alpha"] = ""
        # test_retest_icc column from old format
        icc_val = row.get("test_retest_icc", "").strip()
        if icc_val and not new_row["test_retest_reliability"]:
            new_row["test_retest_reliability"] = icc_val

        new_row["factor_loading_mean"] = row.get("factor_loading_mean", "")
        new_row["sem_value"] = ""
        new_row["N"] = row.get("sample_size", "")
        new_row["cancer_type"] = row.get("cancer_type", "")
        new_row["treatment_phase"] = ""
        new_row["cancer_validated"] = row.get("cancer_validated", "")
        new_row["provenance_ref"] = row.get("provenance_ref", "")
        new_row["notes"] = ""

        new_rows.append(new_row)

    # Backup and write
    shutil.copy2(csv_path, csv_path.with_suffix(".csv.bak"))
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"  MIGRATED: {csv_path.name} — restructured reliability columns")
    return True


def main():
    if not STRUCTURED_DIR.exists():
        print(f"No structured directory at {STRUCTURED_DIR}")
        sys.exit(1)

    paper_dirs = sorted(d for d in STRUCTURED_DIR.iterdir() if d.is_dir())
    print(f"Found {len(paper_dirs)} paper directories\n")

    total_migrated = 0

    for paper_dir in paper_dirs:
        print(f"\n── {paper_dir.name} ──")

        # Edge evidence
        edge_csv = paper_dir / "edge_evidence_template.csv"
        if edge_csv.exists():
            if migrate_csv(edge_csv, EDGE_EVIDENCE_RENAMES,
                          drop_cols=EDGE_DROP, snippet_sources=EDGE_SNIPPET_SOURCES):
                total_migrated += 1

        # Population norms
        norms_csv = paper_dir / "population_norms_template.csv"
        if norms_csv.exists():
            if migrate_csv(norms_csv, POPULATION_NORMS_RENAMES):
                total_migrated += 1

        # Context priors
        priors_csv = paper_dir / "context_priors_template.csv"
        if priors_csv.exists():
            if migrate_csv(priors_csv, CONTEXT_PRIORS_RENAMES):
                total_migrated += 1

        # Temporal evidence
        temporal_csv = paper_dir / "temporal_evidence_template.csv"
        if temporal_csv.exists():
            if migrate_csv(temporal_csv, TEMPORAL_EVIDENCE_RENAMES):
                total_migrated += 1

        # Instrument evidence (special handler)
        instrument_csv = paper_dir / "instrument_evidence_template.csv"
        if instrument_csv.exists():
            if migrate_instrument_evidence(instrument_csv):
                total_migrated += 1

        # Correlation (no existing files yet, but support it)
        corr_csv = paper_dir / "correlation_template.csv"
        if corr_csv.exists():
            if migrate_csv(corr_csv, CORRELATION_RENAMES):
                total_migrated += 1

    print(f"\n{'='*60}")
    print(f"Total files migrated: {total_migrated}")
    print("Backup files saved as .csv.bak")


if __name__ == "__main__":
    main()
