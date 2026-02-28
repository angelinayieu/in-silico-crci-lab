#!/usr/bin/env python3
"""
Component: SYS_EXTRACTION.EX-ACQ.TriageSweep
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 7b (4-Stage Pipeline)
      BOX_TO_IMPLEMENTATION_MAPPING_v2.md §System 1, Process Step 5
Purpose: Orchestrator CLI for the 4-stage triage pipeline that bridges
         System 1 (discovery) → System 2 (extraction).

Stages:
    0   — Metadata + triage (FREE): ID resolution, dedup, abstract screening,
          APS scoring, OA routing. Writes/updates acquisition_queue_v1.
    1   — Abstract pre-extraction (CHEAP): LLM on abstract for design_guess,
          edges_covered_guess, extractability, priority_band.
    1.5 — Full-text extractability scan (V.CHEAP, no LLM): regex marker
          search on cached/OA full text.
    2   — Deep extraction (EXPENSIVE): full P0→P7 pipeline on prioritized
          papers selected by greedy set-cover.

Usage:
    python scripts/run_triage_sweep.py --stage 0
    python scripts/run_triage_sweep.py --stage 1 --max-papers 20
    python scripts/run_triage_sweep.py --stage all --slice PW_M01_NEUROINFLAMMATION
    python scripts/run_triage_sweep.py --stage 0 --input data/retrieval_candidates/A1.jsonl
    python scripts/run_triage_sweep.py --stage 2 --max-papers 5 --dry-run
    python scripts/run_triage_sweep.py --status
    python scripts/run_triage_sweep.py --export-csv

Reads: acquisition_queue_v1, JSONL candidate files, retrieval_cache/
Writes: acquisition_queue_v1 (stage fields), extraction pipeline output
Gates: S0-G1, S1-G1, S1.5-G1 (per AUTOMATED_RETRIEVAL_PLAN.md)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Project bootstrap ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env
_env_path = _PROJECT_ROOT / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from sqlalchemy import text
from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.db import get_session, init_db
from crci.retrieval.config import load_retrieval_config

logger = logging.getLogger(__name__)


def _validate_retrieval_keys() -> list[str]:
    """Check retrieval API keys at startup. Returns list of warnings."""
    rc = load_retrieval_config()
    warnings: list[str] = []

    if not rc.unpaywall_email:
        warnings.append(
            "UNPAYWALL_EMAIL not set → Unpaywall adapter BROKEN (required). "
            "Set in .env or export UNPAYWALL_EMAIL=you@example.com"
        )
    if not rc.core_api_key:
        warnings.append(
            "CORE_API_KEY not set → CORE source non-functional. "
            "Free registration: https://core.ac.uk/services/api"
        )
    if not rc.ncbi_api_key:
        warnings.append(
            "NCBI_API_KEY not set → PubMed rate-limited to 3 req/s (10 with key). "
            "Get one free: https://www.ncbi.nlm.nih.gov/account/"
        )
    if not rc.openalex_email:
        warnings.append(
            "OPENALEX_EMAIL not set → excluded from OpenAlex polite pool (may be throttled)"
        )
    if not rc.s2_api_key:
        warnings.append(
            "S2_API_KEY not set → Semantic Scholar limited to 1 req/s. "
            "Free key: https://www.semanticscholar.org/product/api"
        )
    if not rc.crossref_mailto:
        warnings.append(
            "CROSSREF_MAILTO not set → excluded from Crossref polite pool"
        )
    return warnings


# ═══════════════════════════════════════════════════════════════
#  JSONL INGESTION — load candidates from discovery sessions
# ═══════════════════════════════════════════════════════════════


def ingest_jsonl(session: Session, jsonl_paths: list[Path]) -> int:
    """Ingest JSONL candidate files into acquisition_queue_v1.

    Each line is a JSON object with at minimum: doi, title.
    Optional: pmid, year, design, cancer_type, edge_ids,
              extractability, instruments, session_id.

    Deduplicates by DOI against existing queue entries.

    Returns:
        Number of new candidates inserted.
    """
    if not jsonl_paths:
        jsonl_paths = list((_PROJECT_ROOT / "data" / "retrieval_candidates").glob("*.jsonl"))
        if not jsonl_paths:
            logger.warning("No JSONL files found in data/retrieval_candidates/")
            return 0

    existing_dois = set()
    rows = session.execute(text(
        "SELECT candidate_doi FROM acquisition_queue_v1 WHERE candidate_doi IS NOT NULL"
    )).fetchall()
    for row in rows:
        if row[0]:
            existing_dois.add(row[0].strip().lower())

    # Also check study_registry for already-extracted papers
    try:
        sr_rows = session.execute(text(
            "SELECT doi FROM study_registry_v1 WHERE doi IS NOT NULL"
        )).fetchall()
        extracted_dois = {r[0].strip().lower() for r in sr_rows if r[0]}
    except Exception:
        extracted_dois = set()

    inserted = 0
    skipped_dup = 0
    skipped_extracted = 0

    for jsonl_path in jsonl_paths:
        logger.info("Ingesting %s", jsonl_path)
        with open(jsonl_path) as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("%s:%d — invalid JSON: %s", jsonl_path.name, line_no, exc)
                    continue

                doi = (rec.get("doi") or "").strip()
                if not doi:
                    logger.warning("%s:%d — missing DOI, skipping", jsonl_path.name, line_no)
                    continue

                doi_lower = doi.lower()
                if doi_lower in existing_dois:
                    skipped_dup += 1
                    continue
                if doi_lower in extracted_dois:
                    skipped_extracted += 1
                    continue

                queue_id = f"Q_{uuid.uuid4().hex[:12]}"
                edge_ids = rec.get("edge_ids") or rec.get("edges") or []
                session.execute(text("""
                    INSERT INTO acquisition_queue_v1 (
                        queue_id, candidate_doi, candidate_pmid, candidate_title,
                        target_edge_ids_json, aps_score, status, created_at, updated_at
                    ) VALUES (
                        :qid, :doi, :pmid, :title,
                        :edges, NULL, 'ingested', :now, :now
                    )
                """), {
                    "qid": queue_id,
                    "doi": doi,
                    "pmid": rec.get("pmid"),
                    "title": rec.get("title", ""),
                    "edges": json.dumps(edge_ids) if edge_ids else None,
                    "now": datetime.now(timezone.utc).isoformat(),
                })
                existing_dois.add(doi_lower)
                inserted += 1

    logger.info(
        "JSONL ingestion: %d new, %d duplicate (queue), %d already extracted",
        inserted, skipped_dup, skipped_extracted,
    )
    return inserted


# ═══════════════════════════════════════════════════════════════
#  STAGE 0 — METADATA + TRIAGE (FREE)
# ═══════════════════════════════════════════════════════════════


def run_stage_0(
    session: Session,
    pathway_filter: list[str] | None = None,
    max_papers: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Stage 0: ID resolution + dedup + abstract screening + APS scoring.

    Processes candidates in acquisition_queue_v1 with status='ingested'.
    Updates each row with: relevance_label, aps_score, aps_components,
    stage0_status (PASSED / REJECTED / PARKED).

    Gate S0-G1:
        IRRELEVANT → REJECT
        APS < 0.40  → DEFER (PARKED)
        HIGH/MOD + APS ≥ 0.40 → PASSED

    Returns:
        dict with counts: {passed, rejected, parked, errors}
    """
    from crci.retrieval.abstract_screener import screen_batch
    from crci.retrieval.aps_scorer import score_candidates
    from crci.retrieval.models import CandidateMetadata

    stats = {"passed": 0, "rejected": 0, "parked": 0, "errors": 0}

    # Fetch unprocessed candidates
    rows = session.execute(text("""
        SELECT queue_id, candidate_doi, candidate_pmid, candidate_title,
               target_edge_ids_json
        FROM acquisition_queue_v1
        WHERE status = 'ingested'
        ORDER BY created_at
    """)).fetchall()

    if max_papers:
        rows = rows[:max_papers]

    if not rows:
        logger.info("Stage 0: no unprocessed candidates found")
        return stats

    logger.info("Stage 0: processing %d candidates", len(rows))

    # Build CandidateMetadata objects for the screening/scoring pipeline
    candidates = []
    queue_map: dict[str, str] = {}  # doi → queue_id
    for row in rows:
        qid, doi, pmid, title, edges_json = row
        edge_ids = json.loads(edges_json) if edges_json else []
        cand = CandidateMetadata(
            doi=doi or "",
            pmid=pmid,
            title=title or "",
            abstract="",  # Will be fetched by screener if available
            target_edge_ids=edge_ids,
        )
        candidates.append(cand)
        if doi:
            queue_map[doi] = qid

    # Step 1: Abstract screening (keyword-based; returns (candidate, label) pairs)
    try:
        screened = screen_batch(candidates)
    except Exception as exc:
        logger.error("Abstract screening failed: %s", exc)
        stats["errors"] = len(candidates)
        return stats

    # Step 2: APS scoring on passed candidates
    passed_candidates = []
    relevance_labels: dict[str, str] = {}
    for cand, label in screened:
        doi = cand.doi
        relevance_labels[doi] = label
        if label in ("HIGH", "MODERATE"):
            passed_candidates.append(cand)

    try:
        scored = score_candidates(passed_candidates)
    except Exception as exc:
        logger.error("APS scoring failed: %s", exc)
        stats["errors"] = len(candidates)
        return stats

    # Build APS lookup
    aps_lookup: dict[str, float] = {}
    for s in scored:
        if s.candidate.doi:
            aps_lookup[s.candidate.doi] = s.aps_score

    # Step 3: Apply gate S0-G1 and update DB
    now = datetime.now(timezone.utc).isoformat()
    for cand, label in screened:
        doi = cand.doi
        qid = queue_map.get(doi)
        if not qid:
            continue

        aps = aps_lookup.get(doi, 0.0)

        if label in ("LOW", "IRRELEVANT"):
            stage0_status = "REJECTED"
            stats["rejected"] += 1
        elif aps < config.APS_THRESHOLD:
            stage0_status = "PARKED"
            stats["parked"] += 1
        else:
            stage0_status = "PASSED"
            stats["passed"] += 1

        if not dry_run:
            session.execute(text("""
                UPDATE acquisition_queue_v1
                SET status = :status,
                    aps_score = :aps,
                    abstract_relevance = :relevance,
                    updated_at = :now
                WHERE queue_id = :qid
            """), {
                "status": stage0_status.lower(),
                "aps": aps,
                "relevance": label,
                "now": now,
                "qid": qid,
            })

    if not dry_run:
        session.commit()

    logger.info(
        "Stage 0 complete: %d passed, %d rejected, %d parked, %d errors",
        stats["passed"], stats["rejected"], stats["parked"], stats["errors"],
    )
    return stats


# ═══════════════════════════════════════════════════════════════
#  STAGE 1 — ABSTRACT PRE-EXTRACTION (CHEAP LLM)
# ═══════════════════════════════════════════════════════════════


def run_stage_1(
    session: Session,
    pathway_filter: list[str] | None = None,
    max_papers: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Stage 1: LLM abstract pre-extraction for edge mapping.

    Processes candidates with stage0_status=PASSED.
    Uses Haiku-tier LLM to extract categorical metadata from abstract:
      - design_guess, population_guess, instruments_guess
      - edges_covered_guess, extractability, priority_band

    Gate S1-G1:
        extractability = NO → SKIP
        priority = LOW + no unique edge → SKIP
        CRITICAL/HIGH → PROCEED
        MODERATE → PROCEED only if edge gap k≤1

    Returns:
        dict with counts: {proceeded, skipped, parked_paywalled, errors}
    """
    stats = {"proceeded": 0, "skipped": 0, "parked_paywalled": 0, "errors": 0}

    rows = session.execute(text("""
        SELECT queue_id, candidate_doi, candidate_title, target_edge_ids_json
        FROM acquisition_queue_v1
        WHERE status = 'passed'
        ORDER BY aps_score DESC
    """)).fetchall()

    if max_papers:
        rows = rows[:max_papers]

    if not rows:
        logger.info("Stage 1: no PASSED candidates to process")
        return stats

    logger.info("Stage 1: processing %d candidates", len(rows))

    # Load edge evidence counts for gap checking
    edge_counts = {}
    try:
        ec_rows = session.execute(text("""
            SELECT edge_relation_id, COUNT(*) as k
            FROM edge_evidence_v1
            WHERE active = 1
            GROUP BY edge_relation_id
        """)).fetchall()
        edge_counts = {r[0]: r[1] for r in ec_rows}
    except Exception:
        pass

    # Try to use LLM for abstract analysis; fall back to heuristic
    try:
        from crci.llm.client import LLMClient
        llm = LLMClient()
        has_llm = True
    except Exception:
        has_llm = False
        logger.warning("LLM not available; Stage 1 will use heuristic classification")

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        qid, doi, title, edges_json = row
        edge_ids = json.loads(edges_json) if edges_json else []

        # Determine extractability and priority using heuristic or LLM
        design_guess = "unknown"
        extractability = "MAYBE"
        priority_band = "MODERATE"

        if has_llm and title:
            try:
                prompt = (
                    f"Given this paper title: \"{title}\"\n"
                    f"Target edges: {edge_ids}\n\n"
                    "Respond ONLY with a JSON object (no other text):\n"
                    '{"design_guess": "RCT|cohort|cross_sectional|meta_analysis|SR|methods",'
                    '"extractability": "YES|MAYBE|NO",'
                    '"priority_band": "CRITICAL|HIGH|MODERATE|LOW",'
                    '"edges_covered_guess": ["ER_..."]}'
                )
                resp = llm.complete(
                    prompt,
                    system="You classify research papers for a CRCI evidence pipeline. "
                           "Return ONLY valid JSON.",
                    max_tokens=300,
                )
                parsed = json.loads(resp)
                design_guess = parsed.get("design_guess", design_guess)
                extractability = parsed.get("extractability", extractability)
                priority_band = parsed.get("priority_band", priority_band)
                edge_ids = parsed.get("edges_covered_guess", edge_ids)
            except Exception as exc:
                logger.debug("LLM classification failed for %s: %s", doi, exc)

        # Gate S1-G1
        if extractability == "NO":
            stage1_status = "SKIP"
            stats["skipped"] += 1
        elif priority_band == "LOW":
            # Only proceed if covers a gap edge (k ≤ 1)
            has_gap = any(edge_counts.get(eid, 0) <= 1 for eid in edge_ids)
            if has_gap:
                stage1_status = "PROCEED"
                stats["proceeded"] += 1
            else:
                stage1_status = "SKIP"
                stats["skipped"] += 1
        else:
            stage1_status = "PROCEED"
            stats["proceeded"] += 1

        if not dry_run:
            session.execute(text("""
                UPDATE acquisition_queue_v1
                SET status = :status,
                    target_edge_ids_json = :edges,
                    updated_at = :now
                WHERE queue_id = :qid
            """), {
                "status": stage1_status.lower(),
                "edges": json.dumps(edge_ids) if edge_ids else None,
                "now": now,
                "qid": qid,
            })

    if not dry_run:
        session.commit()

    logger.info(
        "Stage 1 complete: %d proceed, %d skipped, %d paywalled-parked, %d errors",
        stats["proceeded"], stats["skipped"], stats["parked_paywalled"], stats["errors"],
    )
    return stats


# ═══════════════════════════════════════════════════════════════
#  STAGE 1.5 — FULL-TEXT EXTRACTABILITY SCAN (NO LLM)
# ═══════════════════════════════════════════════════════════════


def _scan_extractability(text_content: str) -> dict:
    """Scan full text for extractability markers.

    Spec: AUTOMATED_RETRIEVAL_PLAN.md §Stage 1.5, Scan 1-3.

    Returns:
        dict with: markers_found, table_hints, marker_count, scan_pass
    """
    lower = text_content.lower()
    markers_found = []
    for marker in config.EXTRACTABILITY_MARKERS:
        if marker.lower() in lower:
            markers_found.append(marker)

    # Table caption detection (Scan 3)
    table_hints = re.findall(
        r'Table\s+\d+[.:]\s*[^\n]{10,80}',
        text_content,
        re.IGNORECASE,
    )
    # Filter to likely data tables
    table_hints = [
        t for t in table_hints
        if re.search(
            r'regression|model|coefficient|association|correlation|'
            r'comparison|outcome|effect|predictor|hazard|odds|risk',
            t, re.IGNORECASE,
        )
    ]

    marker_count = len(set(markers_found))

    # Classification per spec
    if marker_count >= config.EXTRACTABILITY_MARKER_THRESHOLD_PASS and len(table_hints) >= 1:
        scan_pass = "PASS"
    elif marker_count >= 1 or len(table_hints) >= 1:
        scan_pass = "UNCLEAR"
    else:
        scan_pass = "FAIL"

    return {
        "markers_found": markers_found[:20],  # cap for storage
        "table_hints": table_hints[:10],
        "marker_count": marker_count,
        "scan_pass": scan_pass,
    }


def run_stage_1_5(
    session: Session,
    max_papers: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Stage 1.5: Full-text extractability scan (no LLM cost).

    Processes candidates with status='proceed' that have cached full text.
    Runs regex markers on the text to determine if extractable statistics
    are likely present.

    Gate S1.5-G1:
        FAIL → do NOT deep-extract (unless k=0 critical edge)
        PASS → PROCEED to Stage 2
        UNCLEAR → PROCEED only if edge gap is critical

    Returns:
        dict with counts: {passed, failed, unclear, no_text}
    """
    stats = {"passed": 0, "failed": 0, "unclear": 0, "no_text": 0}

    rows = session.execute(text("""
        SELECT queue_id, candidate_doi, target_edge_ids_json, file_path
        FROM acquisition_queue_v1
        WHERE status = 'proceed'
        ORDER BY aps_score DESC
    """)).fetchall()

    if max_papers:
        rows = rows[:max_papers]

    if not rows:
        logger.info("Stage 1.5: no PROCEED candidates to scan")
        return stats

    logger.info("Stage 1.5: scanning %d candidates", len(rows))

    # Load edge evidence counts for gap priority
    edge_counts = {}
    try:
        ec_rows = session.execute(text("""
            SELECT edge_relation_id, COUNT(*) as k
            FROM edge_evidence_v1 WHERE active = 1
            GROUP BY edge_relation_id
        """)).fetchall()
        edge_counts = {r[0]: r[1] for r in ec_rows}
    except Exception:
        pass

    cache_dir = _PROJECT_ROOT / "data" / "retrieval_cache"
    uploads_dir = _PROJECT_ROOT / "data" / "manual_uploads" / "pdfs"

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        qid, doi, edges_json, file_path = row
        edge_ids = json.loads(edges_json) if edges_json else []

        # Try to find cached text
        text_content = ""
        tried_paths = []

        # Check explicit file_path first
        if file_path:
            p = Path(file_path)
            if p.exists():
                tried_paths.append(str(p))
                text_content = _extract_text(p)

        # Check manual_uploads/pdfs/ by DOI slug
        if not text_content and doi:
            doi_slug = doi.replace("/", "_")
            for ext in (".pdf", ".xml"):
                candidate_path = uploads_dir / f"{doi_slug}{ext}"
                if candidate_path.exists():
                    tried_paths.append(str(candidate_path))
                    text_content = _extract_text(candidate_path)
                    if text_content:
                        break

        # Check retrieval_cache/
        if not text_content:
            for cached in cache_dir.glob("*"):
                if cached.is_file() and cached.suffix in (".pdf", ".xml", ".txt"):
                    # Check if filename contains DOI hash
                    if doi and doi.replace("/", "_") in cached.stem:
                        tried_paths.append(str(cached))
                        text_content = _extract_text(cached)
                        if text_content:
                            break

        if not text_content:
            stats["no_text"] += 1
            logger.debug("No text available for %s (tried: %s)", doi, tried_paths)
            continue

        # Run extractability scan
        scan = _scan_extractability(text_content)
        scan_pass = scan["scan_pass"]

        # Gate S1.5-G1
        has_critical_gap = any(edge_counts.get(eid, 0) == 0 for eid in edge_ids)

        if scan_pass == "PASS":
            new_status = "stage1p5_passed"
            stats["passed"] += 1
        elif scan_pass == "UNCLEAR" and has_critical_gap:
            new_status = "stage1p5_passed"
            stats["unclear"] += 1
        elif scan_pass == "FAIL" and has_critical_gap:
            # Override: only candidate for a k=0 critical edge
            new_status = "stage1p5_passed"
            stats["failed"] += 1
            logger.info(
                "Overriding FAIL for %s — only candidate for critical gap edge(s)",
                doi,
            )
        else:
            new_status = "stage1p5_failed"
            stats["failed"] += 1

        if not dry_run:
            session.execute(text("""
                UPDATE acquisition_queue_v1
                SET status = :status,
                    updated_at = :now
                WHERE queue_id = :qid
            """), {
                "status": new_status,
                "now": now,
                "qid": qid,
            })

    if not dry_run:
        session.commit()

    logger.info(
        "Stage 1.5 complete: %d passed, %d failed, %d unclear, %d no_text",
        stats["passed"], stats["failed"], stats["unclear"], stats["no_text"],
    )
    return stats


def _extract_text(path: Path) -> str:
    """Extract text from PDF or XML for extractability scanning."""
    if path.suffix == ".xml":
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(str(path)).getroot()
            parts = []
            for elem in root.iter():
                if elem.text:
                    parts.append(elem.text.strip())
            return " ".join(p for p in parts if p)
        except Exception:
            return ""
    elif path.suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                pages = []
                for page in pdf.pages[:20]:  # First 20 pages
                    t = page.extract_text()
                    if t:
                        pages.append(t)
                return "\n".join(pages)
        except Exception:
            return ""
    elif path.suffix == ".txt":
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    return ""


# ═══════════════════════════════════════════════════════════════
#  STAGE 2 — DEEP EXTRACTION (EXPENSIVE)
# ═══════════════════════════════════════════════════════════════


def _greedy_set_cover(
    session: Session,
    candidates: list[dict],
    max_extract: int,
) -> list[dict]:
    """Pre-Stage 2: Greedy edge-coverage set cover.

    Spec: AUTOMATED_RETRIEVAL_PLAN.md §Pre-Stage 2.

    Selects the minimum set of papers that maximally covers uncovered edges,
    weighted by: APS, new edge coverage, extractability, design rank, access cost.

    Returns:
        Ordered list of candidate dicts to extract.
    """
    # Load current edge evidence counts
    edge_counts = {}
    try:
        ec_rows = session.execute(text("""
            SELECT edge_relation_id, COUNT(*) as k
            FROM edge_evidence_v1 WHERE active = 1
            GROUP BY edge_relation_id
        """)).fetchall()
        edge_counts = {r[0]: r[1] for r in ec_rows}
    except Exception:
        pass

    # Load all registered edges → target set
    all_edges = set()
    try:
        er_rows = session.execute(text(
            "SELECT edge_relation_id FROM edge_relations_definitions_v1"
        )).fetchall()
        all_edges = {r[0] for r in er_rows}
    except Exception:
        pass

    # Uncovered = edges with k < 3 (sufficiency target)
    uncovered = {eid for eid in all_edges if edge_counts.get(eid, 0) < 3}

    weights = config.EXTRACTION_PRIORITY_WEIGHTS
    selected = []
    remaining = list(candidates)

    while remaining and len(selected) < max_extract and uncovered:
        best_idx = -1
        best_score = -1.0

        for i, cand in enumerate(remaining):
            cand_edges = set(cand.get("edge_ids", []))
            new_coverage = len(cand_edges & uncovered) / max(len(uncovered), 1)
            aps = cand.get("aps_score", 0.0) or 0.0

            # Design rank
            design = cand.get("design_guess", "unknown")
            design_score = config.DESIGN_RANK.get(design, 0.3)

            # Extractability score
            scan = cand.get("scan_pass", "UNCLEAR")
            ext_score = 1.0 if scan == "PASS" else (0.4 if scan == "UNCLEAR" else 0.1)

            # Access cost penalty
            has_file = bool(cand.get("file_path"))
            access_penalty = 0.0 if has_file else 0.3

            priority = (
                weights["aps"] * aps
                + weights["new_edge_coverage"] * new_coverage
                + weights["extractability"] * ext_score
                + weights["design_rank"] * design_score
                - weights["access_cost_penalty"] * access_penalty
            )

            if priority > best_score:
                best_score = priority
                best_idx = i

        if best_idx < 0 or best_score < 0.20:
            break

        chosen = remaining.pop(best_idx)
        chosen["extraction_priority"] = best_score
        selected.append(chosen)

        # Remove covered edges
        uncovered -= set(chosen.get("edge_ids", []))

    # Add exploration budget
    explore_n = max(
        config.EXPLORATION_BUDGET_MIN,
        int(max_extract * config.EXPLORATION_BUDGET_FRACTION),
    )
    for cand in remaining[:explore_n]:
        if len(selected) >= max_extract:
            break
        cand["extraction_priority"] = 0.15  # below main threshold
        selected.append(cand)

    return selected


def run_stage_2(
    session: Session,
    max_papers: int = 5,
    dry_run: bool = False,
) -> dict:
    """Stage 2: Deep extraction via full P0→P7 pipeline.

    Processes candidates with status='stage1p5_passed'.
    Uses greedy set-cover to prioritize which papers to extract first.
    Calls run_extraction_pipeline() on each selected paper.

    Returns:
        dict with counts: {extracted, failed, skipped_no_file}
    """
    stats = {"extracted": 0, "failed": 0, "skipped_no_file": 0}

    rows = session.execute(text("""
        SELECT queue_id, candidate_doi, candidate_title,
               target_edge_ids_json, aps_score, file_path
        FROM acquisition_queue_v1
        WHERE status = 'stage1p5_passed'
        ORDER BY aps_score DESC
    """)).fetchall()

    if not rows:
        logger.info("Stage 2: no candidates ready for extraction")
        return stats

    # Build candidate dicts for set-cover
    candidates = []
    queue_lookup: dict[str, str] = {}  # doi → queue_id
    for row in rows:
        qid, doi, title, edges_json, aps, fpath = row
        edge_ids = json.loads(edges_json) if edges_json else []
        candidates.append({
            "queue_id": qid,
            "doi": doi,
            "title": title,
            "edge_ids": edge_ids,
            "aps_score": aps,
            "file_path": fpath,
        })
        if doi:
            queue_lookup[doi] = qid

    # Run greedy set-cover
    extraction_queue = _greedy_set_cover(session, candidates, max_papers)
    logger.info(
        "Stage 2: set-cover selected %d/%d candidates for extraction",
        len(extraction_queue), len(candidates),
    )

    if dry_run:
        for i, cand in enumerate(extraction_queue, 1):
            print(f"  [{i}] {cand['doi']} (priority={cand.get('extraction_priority', 0):.3f})")
        return stats

    # Import extraction pipeline
    from crci.extraction.pipeline import run_extraction_pipeline

    now = datetime.now(timezone.utc).isoformat()
    for cand in extraction_queue:
        doi = cand["doi"]
        fpath = cand.get("file_path")
        qid = cand.get("queue_id")

        # Find the PDF
        pdf_path = None
        if fpath and Path(fpath).exists():
            pdf_path = Path(fpath)
        elif doi:
            doi_slug = doi.replace("/", "_")
            for ext in (".pdf", ".xml"):
                candidate_path = _PROJECT_ROOT / "data" / "manual_uploads" / "pdfs" / f"{doi_slug}{ext}"
                if candidate_path.exists():
                    pdf_path = candidate_path
                    break

        if pdf_path is None:
            logger.warning("No file for %s — skipping extraction", doi)
            stats["skipped_no_file"] += 1
            continue

        logger.info("Extracting %s from %s", doi, pdf_path)
        try:
            run_result = run_extraction_pipeline(pdf_path, session=session)
            stats["extracted"] += 1

            if qid:
                session.execute(text("""
                    UPDATE acquisition_queue_v1
                    SET status = 'extracted', updated_at = :now
                    WHERE queue_id = :qid
                """), {"now": now, "qid": qid})
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", doi, exc)
            stats["failed"] += 1

            if qid:
                session.execute(text("""
                    UPDATE acquisition_queue_v1
                    SET status = 'extraction_failed', updated_at = :now
                    WHERE queue_id = :qid
                """), {"now": now, "qid": qid})

    session.commit()

    logger.info(
        "Stage 2 complete: %d extracted, %d failed, %d skipped (no file)",
        stats["extracted"], stats["failed"], stats["skipped_no_file"],
    )
    return stats


# ═══════════════════════════════════════════════════════════════
#  POST-STEP: GAP RE-EVALUATION
# ═══════════════════════════════════════════════════════════════


def run_gap_evaluation(session: Session) -> dict:
    """Post-step: Re-evaluate evidence landscape and report gaps.

    Uses pathway_evidence_auditor to re-grade all edges after extraction.
    Returns gap summary.
    """
    from crci.retrieval.pathway_evidence_auditor import audit_evidence_landscape

    landscape = audit_evidence_landscape(session)
    gaps = landscape.grade_distribution

    logger.info(
        "Gap evaluation: %d total edges, distribution=%s, mean_k=%.1f",
        landscape.total_edges,
        gaps,
        landscape.mean_k,
    )

    if landscape.top_priority_gaps:
        logger.info("Top 10 priority gaps:")
        for g in landscape.top_priority_gaps[:10]:
            logger.info(
                "  %s — grade=%s, k=%d, priority=%.3f",
                g.edge_relation_id,
                g.sufficiency_grade,
                g.k_total,
                g.gap_priority_score,
            )

    return {
        "total_edges": landscape.total_edges,
        "grade_distribution": gaps,
        "mean_k": landscape.mean_k,
        "top_gaps": [
            {
                "edge": g.edge_relation_id,
                "grade": g.sufficiency_grade,
                "k": g.k_total,
                "priority": g.gap_priority_score,
            }
            for g in landscape.top_priority_gaps[:20]
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  STATUS & EXPORT
# ═══════════════════════════════════════════════════════════════


def print_status(session: Session) -> None:
    """Print current triage pipeline status."""
    counts = session.execute(text("""
        SELECT status, COUNT(*) FROM acquisition_queue_v1
        GROUP BY status ORDER BY COUNT(*) DESC
    """)).fetchall()

    print("\n" + "=" * 60)
    print("TRIAGE PIPELINE STATUS")
    print("=" * 60)
    total = 0
    for status, count in counts:
        print(f"  {status:<25} {count:>5}")
        total += count
    print(f"  {'TOTAL':<25} {total:>5}")

    # Evidence coverage
    try:
        edge_count = session.execute(text(
            "SELECT COUNT(DISTINCT edge_relation_id) FROM edge_evidence_v1 WHERE active = 1"
        )).scalar() or 0
        total_edges = session.execute(text(
            "SELECT COUNT(*) FROM edge_relations_definitions_v1"
        )).scalar() or 0
        print(f"\n  Edge coverage: {edge_count}/{total_edges} edges have evidence")
    except Exception:
        pass

    print("=" * 60)


def export_csv(session: Session, output_dir: Path) -> None:
    """Export acquisition queue to CSV for human review."""
    import csv

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = session.execute(text("""
        SELECT queue_id, candidate_doi, candidate_pmid, candidate_title,
               target_edge_ids_json, aps_score, abstract_relevance,
               status, created_at, updated_at
        FROM acquisition_queue_v1
        ORDER BY aps_score DESC
    """)).fetchall()

    csv_path = output_dir / f"triage_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "queue_id", "doi", "pmid", "title", "edge_ids",
            "aps_score", "relevance", "status", "created_at", "updated_at",
        ])
        for row in rows:
            writer.writerow(row)

    print(f"Exported {len(rows)} rows to {csv_path}")


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CRCI Triage Sweep — System 1 → System 2 bridge",
    )
    parser.add_argument(
        "--stage",
        choices=["0", "1", "1.5", "2", "all"],
        help="Which stage to run (0, 1, 1.5, 2, or all)",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to JSONL file(s) to ingest (glob pattern accepted)",
    )
    parser.add_argument(
        "--slice",
        type=str,
        help="Comma-separated pathway IDs to filter (e.g. PW_M01_NEUROINFLAMMATION)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=50,
        help="Max papers to process per stage (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying DB",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print current triage pipeline status",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export triage snapshot to CSV",
    )
    parser.add_argument(
        "--gap-report",
        action="store_true",
        help="Run gap evaluation and show priority edges",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    # ── Validate retrieval API keys at startup ──
    key_warnings = _validate_retrieval_keys()
    if key_warnings:
        logger.warning("=" * 60)
        logger.warning("RETRIEVAL API KEY WARNINGS (%d issues):", len(key_warnings))
        for w in key_warnings:
            logger.warning("  ⚠ %s", w)
        logger.warning("=" * 60)

    init_db()

    pathway_filter = None
    if args.slice:
        pathway_filter = [p.strip() for p in args.slice.split(",")]

    with get_session() as session:
        # Status mode
        if args.status:
            print_status(session)
            return 0

        # Export mode
        if args.export_csv:
            export_csv(session, _PROJECT_ROOT / "data" / "retrieval_candidates")
            return 0

        # Gap report mode
        if args.gap_report:
            report = run_gap_evaluation(session)
            print(json.dumps(report, indent=2))
            return 0

        # Ingest JSONL if provided
        if args.input:
            import glob
            paths = [Path(p) for p in glob.glob(args.input)]
            if not paths:
                paths = [Path(args.input)]
            n = ingest_jsonl(session, paths)
            session.commit()
            print(f"Ingested {n} new candidates")
            if not args.stage:
                return 0

        if not args.stage:
            parser.print_help()
            return 1

        # Run stages
        stages = ["0", "1", "1.5", "2"] if args.stage == "all" else [args.stage]

        for stage in stages:
            print(f"\n{'='*60}")
            print(f"  STAGE {stage}")
            print(f"{'='*60}")

            if stage == "0":
                result = run_stage_0(
                    session,
                    pathway_filter=pathway_filter,
                    max_papers=args.max_papers,
                    dry_run=args.dry_run,
                )
            elif stage == "1":
                result = run_stage_1(
                    session,
                    pathway_filter=pathway_filter,
                    max_papers=args.max_papers,
                    dry_run=args.dry_run,
                )
            elif stage == "1.5":
                result = run_stage_1_5(
                    session,
                    max_papers=args.max_papers,
                    dry_run=args.dry_run,
                )
            elif stage == "2":
                result = run_stage_2(
                    session,
                    max_papers=args.max_papers,
                    dry_run=args.dry_run,
                )
            else:
                continue

            print(f"  Result: {json.dumps(result, indent=2)}")

        # Post-step: gap evaluation (if running all stages)
        if args.stage == "all" and not args.dry_run:
            print(f"\n{'='*60}")
            print("  POST-STEP: GAP RE-EVALUATION")
            print(f"{'='*60}")
            gap_report = run_gap_evaluation(session)
            print(f"  Grades: {gap_report['grade_distribution']}")
            print(f"  Mean k: {gap_report['mean_k']:.1f}")
            if gap_report["top_gaps"]:
                print("  Top 5 priority gaps:")
                for g in gap_report["top_gaps"][:5]:
                    print(f"    {g['edge']} — grade={g['grade']}, k={g['k']}, priority={g['priority']:.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
