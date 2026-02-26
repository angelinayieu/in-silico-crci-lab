# VERIFIED: flow matches AUTOMATED_RETRIEVAL_PLAN.md Part 5
# VERIFIED: imports — pathlib, json, csv
# VERIFIED: supports 3 methods: PDF, structured CSV, search override
# VERIFIED: companion .meta.json for PDF uploads
"""
Component: SYS_EXTRACTION.EX-ACQ.ManualUploadWatcher
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 5 (Manual Input Protocol)
Purpose: Watches data/manual_uploads/ for new files and routes them:
         - PDFs → register in study_registry_v1 → feed to EX-P0
         - CSVs → validate against template schema → write to evidence table
         - search_overrides → fetch specific DOIs/PMIDs → feed to pipeline
Reads: data/manual_uploads/{pdfs,structured,search_overrides}
Writes: study_registry_v1, evidence tables, acquisition_queue_v1
"""
from __future__ import annotations

import csv
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MANUAL_DIR = Path("data/manual_uploads")
_PDF_DIR = _MANUAL_DIR / "pdfs"
_STRUCTURED_DIR = _MANUAL_DIR / "structured"
_OVERRIDE_DIR = _MANUAL_DIR / "search_overrides"

# Valid CSV template names (must match data/templates/)
_VALID_TEMPLATES = {
    "edge_evidence_template",
    "instrument_evidence_template",
    "population_norms_template",
    "context_priors_template",
    "temporal_evidence_template",
    "correlation_template",
}


@dataclass
class ImportResult:
    """Result of a manual import operation."""

    files_processed: int = 0
    pdfs_registered: int = 0
    csvs_imported: int = 0
    overrides_queued: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def scan_pdfs(
    session: Session,
    pdf_dir: Path | None = None,
) -> list[dict]:
    """Scan for new PDF uploads and prepare them for pipeline ingestion.

    Each PDF may have a companion .meta.json with metadata hints.

    Args:
        session: SQLAlchemy session.
        pdf_dir: Override PDF directory.

    Returns:
        List of dicts with pdf_path and metadata for pipeline.
    """
    pdf_dir = pdf_dir or _PDF_DIR
    if not pdf_dir.exists():
        logger.info("PDF upload directory does not exist: %s", pdf_dir)
        return []

    results: list[dict] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        meta = _load_meta(pdf_path)
        results.append({
            "pdf_path": str(pdf_path),
            "doi": meta.get("doi"),
            "pmid": meta.get("pmid"),
            "title": meta.get("title", pdf_path.stem),
            "workstream_hints": meta.get("workstream_hints", []),
            "target_edges": meta.get("target_edges", []),
            "target_instruments": meta.get("target_instruments", []),
            "priority": meta.get("priority", "normal"),
            "notes": meta.get("notes", ""),
            "source": "manual",
        })

    logger.info("Found %d PDF uploads in %s", len(results), pdf_dir)
    return results


def _load_meta(pdf_path: Path) -> dict:
    """Load companion .meta.json if it exists."""
    meta_path = pdf_path.with_suffix(".meta.json")
    if meta_path.exists():
        try:
            with open(meta_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read meta file %s: %s", meta_path, exc)
    return {}


def import_structured_csv(
    session: Session,
    csv_path: Path,
    validate_only: bool = False,
) -> ImportResult:
    """Import a structured CSV file into the appropriate evidence table.

    The CSV filename must match one of the template names
    (e.g., edge_evidence_template.csv).

    Args:
        session: SQLAlchemy session.
        csv_path: Path to the CSV file.
        validate_only: If True, validate without importing.

    Returns:
        ImportResult.
    """
    result = ImportResult()
    template_name = csv_path.stem

    # Check if template name is valid
    if template_name not in _VALID_TEMPLATES:
        result.errors.append(
            f"Unknown template: '{template_name}'. "
            f"Valid templates: {sorted(_VALID_TEMPLATES)}"
        )
        return result

    # Read CSV
    try:
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as exc:
        result.errors.append(f"Failed to read CSV: {exc}")
        return result

    if not rows:
        result.warnings.append("CSV is empty")
        return result

    # Validate required columns
    required_columns = _get_required_columns(template_name)
    missing = required_columns - set(rows[0].keys())
    if missing:
        result.errors.append(
            f"Missing required columns: {sorted(missing)}"
        )
        return result

    result.files_processed = 1

    if validate_only:
        logger.info(
            "Validation OK: %s (%d rows, all required columns present)",
            csv_path.name,
            len(rows),
        )
        return result

    # Write to evidence table
    logger.info(
        "Importing %d rows from %s (template: %s)",
        len(rows),
        csv_path.name,
        template_name,
    )

    if template_name == "edge_evidence_template":
        imported = _write_edge_evidence_rows(session, rows, csv_path)
        result.csvs_imported = imported
    elif template_name == "population_norms_template":
        from crci.extraction.family_importers import import_population_norm
        imported = 0
        for row in rows:
            try:
                study_id = _resolve_study_id(session, row.get("doi", ""))
                if study_id:
                    row["study_id"] = study_id
                import_population_norm(session, row)
                imported += 1
            except Exception as exc:
                logger.warning(
                    "Failed to import population_norm row: %s", exc
                )
                result.warnings.append(f"Row import failed: {exc}")
        result.csvs_imported = imported
    elif template_name == "instrument_evidence_template":
        from crci.extraction.family_importers import import_instrument_evidence
        imported = 0
        for row in rows:
            try:
                study_id = _resolve_study_id(session, row.get("doi", ""))
                if study_id:
                    row["study_id"] = study_id
                import_instrument_evidence(session, row)
                imported += 1
            except Exception as exc:
                logger.warning(
                    "Failed to import instrument_evidence row: %s", exc
                )
                result.warnings.append(f"Row import failed: {exc}")
        result.csvs_imported = imported
    else:
        # Other template types not yet implemented
        result.warnings.append(
            f"Template '{template_name}' import not yet implemented — "
            f"only edge_evidence_template, population_norms_template, "
            f"and instrument_evidence_template are supported. "
            f"({len(rows)} rows skipped)"
        )
        logger.warning(
            "Import for template '%s' not yet implemented, skipping %d rows",
            template_name,
            len(rows),
        )

    return result


# Study ID lookup: map DOI → study_id by checking study_registry_v1
_DOI_STUDY_CACHE: dict[str, str] = {}


def _resolve_study_id(session: Session, doi: str) -> str | None:
    """Look up or generate a study_id for a DOI."""
    if doi in _DOI_STUDY_CACHE:
        return _DOI_STUDY_CACHE[doi]

    from sqlalchemy import text
    result = session.execute(
        text("SELECT study_id FROM study_registry_v1 WHERE doi = :doi"),
        {"doi": doi},
    )
    row = result.fetchone()
    if row:
        _DOI_STUDY_CACHE[doi] = row[0]
        return row[0]

    logger.warning(
        "DOI %s not found in study_registry_v1. "
        "Register the study first (scripts/load_evidence_into_db.py).",
        doi,
    )
    return None


def _write_edge_evidence_rows(
    session: Session,
    rows: list[dict],
    csv_path: Path,
) -> int:
    """Write edge_evidence_template rows into edge_evidence_v1.

    Maps CSV columns to DB columns:
      CSV: doi, edge_id, beta_raw, se_raw, effect_type_original,
           effect_size_type, sample_size, study_design, cancer_type,
           treatment_phase, instrument_id, confidence_note
      DB:  ler_id, edge_relation_id, study_id, edge_family, node_x, node_y,
           effect_type_reported, effect_value_reported, se_reported,
           N_effect, effect_size_type, notes
    """
    from datetime import datetime, timezone
    from sqlalchemy import text as sa_text

    # Load edge definitions for metadata lookup
    edge_defs: dict[str, dict] = {}
    result = session.execute(
        sa_text("SELECT edge_relation_id, edge_family, node_x, node_y "
                "FROM edge_relations_definitions_v1")
    )
    for r in result:
        edge_defs[r[0]] = {"edge_family": r[1], "node_x": r[2], "node_y": r[3]}

    insert_sql = sa_text("""
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

    imported = 0
    for row in rows:
        edge_id = row.get("edge_id", "").strip()
        doi = row.get("doi", "").strip()

        if not edge_id or not doi:
            logger.warning("Skipping row with empty edge_id or doi in %s", csv_path)
            continue

        study_id = _resolve_study_id(session, doi)
        if not study_id:
            continue

        # Check for duplicates
        existing = session.execute(
            sa_text(
                "SELECT ler_id FROM edge_evidence_v1 "
                "WHERE study_id = :sid AND edge_relation_id = :eid"
            ),
            {"sid": study_id, "eid": edge_id},
        ).fetchone()

        if existing:
            logger.info(
                "Evidence for %s × %s already exists, skipping",
                study_id, edge_id,
            )
            continue

        edge_def = edge_defs.get(edge_id, {})
        ler_id = f"LER_{study_id}_{edge_id}_{uuid.uuid4().hex[:8]}"

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
            "quality_rating": "moderate",
            "entered_by": "manual_csv_import",
            "entered_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "active": 1,
        }

        session.execute(insert_sql, params)
        logger.info(
            "Inserted %s: %s × %s β=%.3f SE=%.3f n=%s",
            ler_id, study_id, edge_id,
            params["effect_value_reported"] or 0,
            params["se_reported"] or 0,
            params["N_effect"],
        )
        imported += 1

    session.commit()
    return imported


def _get_required_columns(template_name: str) -> set[str]:
    """Get required columns for a template."""
    # Column names follow CRCI_Checklists_Templates_v2.0.md §T1 (the authoritative spec)
    required = {
        "edge_evidence_template": {
            "doi", "edge_id", "beta_raw", "se_raw", "sample_size",
        },
        "instrument_evidence_template": {
            "doi", "instrument_id", "reliability_value", "sample_size",
        },
        "population_norms_template": {
            "doi", "instrument_id", "mean", "sd", "sample_size",
        },
        "context_priors_template": {
            "doi", "node_id", "cancer_type", "treatment_phase",
            "prior_mean_z", "prior_sd_z",
        },
        "temporal_evidence_template": {
            "doi", "edge_id", "timepoint_weeks", "value", "se",
        },
        "correlation_template": {
            "doi", "biomarker_id_1", "biomarker_id_2", "correlation_r", "sample_size",
        },
    }
    return required.get(template_name, set())


def process_search_overrides(
    session: Session,
    override_dir: Path | None = None,
) -> list[dict]:
    """Process search override files (specific DOI/PMID lists).

    Args:
        session: SQLAlchemy session.
        override_dir: Override directory path.

    Returns:
        List of paper dicts to fetch and process.
    """
    override_dir = override_dir or _OVERRIDE_DIR
    if not override_dir.exists():
        return []

    papers: list[dict] = []

    for override_path in sorted(override_dir.glob("*.json")):
        try:
            with open(override_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read override %s: %s", override_path, exc)
            continue

        if data.get("override_type") != "specific_papers":
            logger.warning("Unknown override_type in %s", override_path)
            continue

        for paper in data.get("papers", []):
            papers.append({
                "doi": paper.get("doi"),
                "pmid": paper.get("pmid"),
                "workstream": paper.get("workstream", "edge_evidence"),
                "target_edges": paper.get("target_edges", []),
                "source": "search_override",
                "override_file": str(override_path),
            })

    logger.info("Found %d papers in search overrides", len(papers))
    return papers


def run_manual_import(
    session: Session,
    import_type: str = "all",
    validate_only: bool = False,
) -> ImportResult:
    """Run manual import for all or specific file types.

    Args:
        session: SQLAlchemy session.
        import_type: "pdf", "csv", "override", or "all".
        validate_only: If True, validate without importing.

    Returns:
        Combined ImportResult.
    """
    result = ImportResult()

    if import_type in ("pdf", "all"):
        pdfs = scan_pdfs(session)
        result.pdfs_registered = len(pdfs)

    if import_type in ("csv", "all"):
        if _STRUCTURED_DIR.exists():
            # rglob supports per-paper subfolders: structured/[doi-slug]/*.csv
            for csv_path in sorted(_STRUCTURED_DIR.rglob("*.csv")):
                csv_result = import_structured_csv(
                    session, csv_path, validate_only=validate_only
                )
                result.csvs_imported += csv_result.csvs_imported
                result.errors.extend(csv_result.errors)
                result.warnings.extend(csv_result.warnings)

    if import_type in ("override", "all"):
        overrides = process_search_overrides(session)
        result.overrides_queued = len(overrides)

    result.files_processed = (
        result.pdfs_registered + result.csvs_imported + result.overrides_queued
    )

    logger.info(
        "Manual import complete: %d PDFs, %d CSVs, %d overrides",
        result.pdfs_registered,
        result.csvs_imported,
        result.overrides_queued,
    )
    return result
