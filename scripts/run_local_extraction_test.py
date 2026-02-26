#!/usr/bin/env python3
"""
Run the extraction pipeline checkpoint-by-checkpoint on a LOCAL PDF.

Uses the same functions as test_full_extraction.py but skips the web fetch
and uses the local PDF directly.

Usage:
    python scripts/run_local_extraction_test.py <pdf_path> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silence pdfminer DEBUG noise (331K+ lines per run, 99.8% of log volume)
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logger = logging.getLogger("local_extraction_test")

# Import the test_full_extraction functions
from test_full_extraction import (
    HoldingData,
    run_p0_ingestion,
    run_p0_relevance_screening,
    run_p0_paper_type_classification,
    run_p0_mode_selection,
    run_p1_canonical_read,
    run_p1_agents,
    load_registry,
    find_instrument_matches,
    find_edge_candidates,
    generate_next_steps,
    _count_label_types,
)


def run_on_local_pdf(pdf_path: Path, dry_run: bool = False) -> HoldingData:
    """Run full extraction test on a local PDF, checkpoint by checkpoint."""
    holding = HoldingData(url=f"file://{pdf_path}")
    holding.pdf_path = str(pdf_path)

    # Print model info
    from crci.shared import config
    from crci.llm.model_router import ModelTier
    
    print(f"\n{'='*70}")
    print(f"LOCAL PDF EXTRACTION TEST")
    print(f"{'='*70}")
    print(f"PDF: {pdf_path}")
    print(f"Size: {pdf_path.stat().st_size:,} bytes")
    print(f"Mode: {'DRY-RUN (no LLM)' if dry_run else 'FULL (with LLM calls)'}")
    print(f"\nLLM Configuration:")
    print(f"  Default model:  {config.LLM_DEFAULT_MODEL}")
    print(f"  Max tokens:     {config.LLM_DEFAULT_MAX_TOKENS}")
    print(f"  Max retries:    {config.LLM_MAX_RETRIES}")
    print(f"  Haiku model:    {ModelTier.HAIKU.value}")
    print(f"  Sonnet model:   {ModelTier.SONNET.value}")
    print(f"  Opus model:     {ModelTier.OPUS.value}")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"  API key loaded: {'YES' if api_key else 'NO'} (length: {len(api_key)})")
    print(f"{'='*70}\n")

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 1: P0-S1 — PDF Ingestion
    # ═══════════════════════════════════════════════════════════
    print("=" * 60)
    print("CHECKPOINT 1: P0-S1 — PDF Ingestion")
    print("=" * 60)
    try:
        ingested = run_p0_ingestion(pdf_path)
        holding.pdf_quality = ingested.get("pdf_quality", "UNKNOWN")
        holding.page_count = ingested.get("page_count", 0)
        holding.canonical_text = ingested.get("canonical_text", "")
        holding.canonical_text_length = len(holding.canonical_text)
        sections = ingested.get("sections", [])
        holding.sections_found = [s.get("section_type", "unknown") for s in sections]

        print(f"  ✓ PDF Quality:    {holding.pdf_quality}")
        print(f"  ✓ Pages:          {holding.page_count}")
        print(f"  ✓ Text extracted: {holding.canonical_text_length:,} chars")
        print(f"  ✓ Sections:       {holding.sections_found}")
        print(f"  ✓ First 200 chars: {holding.canonical_text[:200]}...")
        
        # Extract metadata from ingested
        metadata = ingested.get("metadata", {})
        holding.doi = metadata.get("doi")
        holding.title = metadata.get("title")
        holding.year = metadata.get("year")
        if holding.title:
            print(f"  ✓ Title:          {holding.title[:80]}")
        if holding.doi:
            print(f"  ✓ DOI:            {holding.doi}")
        
        print("\n  CHECKPOINT 1: PASSED ✓")
    except Exception as e:
        print(f"  ✗ CHECKPOINT 1 FAILED: {e}")
        holding.errors.append(f"P0-S1 failed: {e}")
        import traceback; traceback.print_exc()
        return holding

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 2: P0-S2 — Relevance Screening
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 2: P0-S2 — Relevance Screening")
    print("=" * 60)
    try:
        screened = run_p0_relevance_screening(ingested)
        holding.relevance_score = screened.get("relevance_score", 0.0)
        holding.relevance_decision = screened.get("decision", "REVIEW")

        print(f"  ✓ Relevance score: {holding.relevance_score:.2f}")
        print(f"  ✓ Decision:        {holding.relevance_decision}")
        print(f"  ✓ Reason:          {screened.get('reason', 'N/A')}")

        if holding.relevance_decision == "REJECT":
            print(f"\n  ⚠ Paper REJECTED — Gate P0-G2 would fire")
            print(f"    Score {holding.relevance_score:.2f} below threshold")
        
        print("\n  CHECKPOINT 2: PASSED ✓")
    except Exception as e:
        print(f"  ✗ CHECKPOINT 2 FAILED: {e}")
        holding.errors.append(f"P0-S2 failed: {e}")
        import traceback; traceback.print_exc()

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 3: P0-PTC — Paper Type Classification (LLM)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 3: P0-PTC — Paper Type Classification")
    print(f"  {'[DRY-RUN: Heuristic]' if dry_run else '[LLM CALL → Claude API]'}")
    print("=" * 60)
    try:
        classified = run_p0_paper_type_classification(ingested, dry_run=dry_run)
        holding.paper_subtype = str(classified.get("paper_subtype", "unknown"))
        holding.paper_subtype_confidence = classified.get("confidence", 0.0)

        print(f"  ✓ Paper subtype:  {holding.paper_subtype}")
        print(f"  ✓ Confidence:     {holding.paper_subtype_confidence:.2f}")
        if not dry_run:
            print(f"  ✓ Model used:     {config.LLM_DEFAULT_MODEL}")
            # Show classification details if available
            for k, v in classified.items():
                if k not in ("paper_subtype", "confidence"):
                    print(f"  ✓ {k}: {v}")
        
        print("\n  CHECKPOINT 3: PASSED ✓")
    except Exception as e:
        print(f"  ✗ CHECKPOINT 3 FAILED: {e}")
        holding.errors.append(f"P0-PTC failed: {e}")
        import traceback; traceback.print_exc()
        holding.paper_subtype = "unknown"
        holding.paper_subtype_confidence = 0.0

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 4: P0-S3 — Mode Selection (Deterministic)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 4: P0-S3 — Mode Selection (Deterministic)")
    print("=" * 60)
    try:
        paper_id = holding.doi or f"LOCAL_{uuid.uuid4().hex[:8]}"
        holding.extraction_mode = run_p0_mode_selection(
            paper_id, 
            {"paper_subtype": holding.paper_subtype, "confidence": holding.paper_subtype_confidence},
            {"relevance_score": holding.relevance_score, "decision": holding.relevance_decision},
            dry_run=dry_run,
        )
        print(f"  ✓ Paper ID:        {paper_id}")
        print(f"  ✓ Extraction mode: {holding.extraction_mode}")
        print(f"  ✓ Input subtype:   {holding.paper_subtype}")
        
        # Explain the routing
        mode_map = {
            "DEEP": "Full extraction: all 10 agents, MA multi-product, hop discovery",
            "STANDARD": "Standard extraction: all 10 agents",
            "SHALLOW": "Minimal extraction: AG01+AG02+AG05 only",
        }
        print(f"  ✓ Routing:         {mode_map.get(holding.extraction_mode, 'Unknown')}")
        
        print("\n  CHECKPOINT 4: PASSED ✓")
    except Exception as e:
        print(f"  ✗ CHECKPOINT 4 FAILED: {e}")
        holding.errors.append(f"P0-S3 failed: {e}")
        import traceback; traceback.print_exc()
        holding.extraction_mode = "STANDARD"

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 5: Registry Matching (Deterministic)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 5: Registry Matching (Deterministic)")
    print("=" * 60)
    instruments = load_registry("INSTRUMENT")
    edges = load_registry("EDGE")
    nodes = load_registry("NODE")
    print(f"  Loaded: {len(instruments)} instruments, {len(edges)} edges, {len(nodes)} nodes")

    search_text = holding.canonical_text
    holding.instruments_matched = find_instrument_matches(search_text, instruments)
    print(f"\n  Instruments matched: {len(holding.instruments_matched)}")
    for m in holding.instruments_matched[:10]:
        print(f"    - {m['instrument_id']}: {m['instrument_name'][:50]} → {m['maps_to_node']}")

    design_info = {"study_design": holding.paper_subtype}
    inst_ids = [m["instrument_id"] for m in holding.instruments_matched]
    holding.edges_candidate = find_edge_candidates(search_text, design_info, inst_ids, edges)
    print(f"\n  Edge candidates: {len(holding.edges_candidate)}")
    for ec in holding.edges_candidate[:10]:
        print(f"    - {ec['edge_id']}: {', '.join(ec.get('reasons', []))[:70]}")

    print("\n  CHECKPOINT 5: PASSED ✓")

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 6: P1-CR — Canonical Read (LLM)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 6: P1-CR — Canonical Read")
    print(f"  {'[DRY-RUN: Mock PaperMap]' if dry_run else '[LLM CALL → Claude API]'}")
    print("=" * 60)
    paper_map = None
    try:
        paper_map = run_p1_canonical_read(
            paper_id=paper_id,
            canonical_text=holding.canonical_text,
            dry_run=dry_run,
        )
        holding.sections_found = [s.section_type for s in paper_map.sections]
        holding.tables_found = len(paper_map.tables)
        holding.figures_found = len(paper_map.figures)
        holding.candidate_spans_found = len(paper_map.candidate_spans)

        print(f"  ✓ Sections:         {len(paper_map.sections)}")
        for s in paper_map.sections:
            print(f"      {s.section_type}: chars {s.char_start}-{s.char_end}")
        print(f"  ✓ Tables:           {holding.tables_found}")
        print(f"  ✓ Figures:          {holding.figures_found}")
        print(f"  ✓ Candidate spans:  {holding.candidate_spans_found}")
        if paper_map.study_design:
            print(f"  ✓ Study design:     {paper_map.study_design}")
        if paper_map.n_total:
            print(f"  ✓ N total:          {paper_map.n_total}")

        print("\n  CHECKPOINT 6: PASSED ✓")
    except Exception as e:
        print(f"  ✗ CHECKPOINT 6 FAILED: {e}")
        holding.errors.append(f"P1-CR failed: {e}")
        import traceback; traceback.print_exc()

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 7: P1-AG — Multi-Agent Extraction (LLM × 10)
    # ═══════════════════════════════════════════════════════════
    if not dry_run and paper_map is not None:
        print("\n" + "=" * 60)
        print("CHECKPOINT 7: P1-AG — Multi-Agent Extraction (10 agents)")
        print("[LLM CALLS → Claude API × 10 agents]")
        print("=" * 60)
        try:
            holding.agent_outputs = run_p1_agents(
                paper_id=paper_id,
                paper_map=paper_map,
                extraction_mode=holding.extraction_mode,
                dry_run=False,
            )

            for output in holding.agent_outputs:
                agent_id = output.get("agent_id", "?")
                status = output.get("status", "unknown")
                if status == "success":
                    sl_count = output.get("span_labels_count", 0)
                    an_count = output.get("annotations_count", 0)
                    elapsed = output.get("elapsed_ms", 0)
                    print(f"  ✓ {agent_id}: {sl_count} span_labels, "
                          f"{an_count} annotations ({elapsed:.0f}ms)")
                    for sl in output.get("span_labels_detail", [])[:8]:
                        val_str = str(sl.get("value", ""))[:30]
                        ctx = sl.get("context", "")[:40]
                        print(f"      → {sl.get('label_type')}: {val_str} | {ctx}")
                elif status == "summary":
                    print(f"\n  ═══ TOTALS ═══")
                    print(f"  Total span_labels:  {output.get('total_span_labels', 0)}")
                    print(f"  Total annotations:  {output.get('total_annotations', 0)}")
                    label_counts = output.get("label_type_counts", {})
                    if label_counts:
                        print("  Label type distribution:")
                        for lt, cnt in list(label_counts.items())[:20]:
                            print(f"      {lt}: {cnt}")
                else:
                    print(f"  ✗ {agent_id}: {status} — {output.get('error', '')[:100]}")

            print("\n  CHECKPOINT 7: PASSED ✓")
        except Exception as e:
            print(f"  ✗ CHECKPOINT 7 FAILED: {e}")
            holding.errors.append(f"P1-AG failed: {e}")
            import traceback; traceback.print_exc()
    elif dry_run:
        print("\n  ⚠ CHECKPOINT 7: SKIPPED (dry-run mode)")
    else:
        print("\n  ⚠ CHECKPOINT 7: SKIPPED (no PaperMap from Checkpoint 6)")

    # ═══════════════════════════════════════════════════════════
    #  CHECKPOINT 8: Next Steps (per EXTRACTION_PLAYBOOK.md)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("CHECKPOINT 8: Next Steps (per EXTRACTION_PLAYBOOK.md)")
    print("=" * 60)
    next_steps = generate_next_steps(holding)
    for step in next_steps:
        print(f"  {step}")

    # ═══════════════════════════════════════════════════════════
    #  FINAL SUMMARY
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  PDF:               {pdf_path.name}")
    print(f"  Quality:           {holding.pdf_quality}")
    print(f"  Pages:             {holding.page_count}")
    print(f"  Text:              {holding.canonical_text_length:,} chars")
    print(f"  Relevance:         {holding.relevance_decision} ({holding.relevance_score:.2f})")
    print(f"  Paper subtype:     {holding.paper_subtype} ({holding.paper_subtype_confidence:.2f})")
    print(f"  Extraction mode:   {holding.extraction_mode}")
    print(f"  Instruments:       {len(holding.instruments_matched)}")
    print(f"  Edge candidates:   {len(holding.edges_candidate)}")
    if holding.agent_outputs:
        summary = next((o for o in holding.agent_outputs if o.get("status") == "summary"), None)
        if summary:
            print(f"  Total span_labels: {summary.get('total_span_labels', 0)}")
            print(f"  Total annotations: {summary.get('total_annotations', 0)}")
    print(f"  Errors:            {len(holding.errors)}")
    print(f"  Warnings:          {len(holding.warnings)}")
    
    if holding.errors:
        print(f"\n  ERRORS:")
        for e in holding.errors:
            print(f"    - {e}")
    if holding.warnings:
        print(f"\n  WARNINGS:")
        for w in holding.warnings:
            print(f"    - {w}")

    return holding


def main():
    parser = argparse.ArgumentParser(description="Run extraction on a local PDF")
    parser.add_argument("pdf_path", help="Path to the local PDF file")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls")
    parser.add_argument("--json", action="store_true", help="Output JSON holding data")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ ANTHROPIC_API_KEY not set. Running in dry-run mode.")
        args.dry_run = True

    holding = run_on_local_pdf(pdf_path, dry_run=args.dry_run)

    if args.json:
        print("\n" + json.dumps(holding.to_dict(), indent=2))

    return 0 if not holding.errors else 1


if __name__ == "__main__":
    sys.exit(main())
