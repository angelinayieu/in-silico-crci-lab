#!/usr/bin/env python3
"""Diagnostic: run AG05 on Campbell 2017 and inspect grouping_ids."""
import sys, os, logging

# Load env vars BEFORE anything else
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from crci.extraction.p0_triage.pdf_ingestion import ingest_pdf
from crci.extraction.p1_extraction.canonical_reader import CanonicalReader
from crci.extraction.p1_extraction.agents.ag05_stats_label import StatsLabelAgent
from crci.llm.client import LLMClient

# Ingest PDF
pdf = ingest_pdf("data/manual_uploads/pdfs/campbell2017.pdf")
print(f"PDF text length: {len(pdf['canonical_text'])}")

# Create LLM client
client = LLMClient()

# Run CanonicalReader to get PaperMap
cr = CanonicalReader(client)
paper_map = cr.read("STUDY_CAMPBELL_2017", pdf["canonical_text"])
print(f"PaperMap: {len(paper_map.sections)} sections, {len(paper_map.candidate_spans)} candidate_spans")
for sec in paper_map.sections:
    print(f"  Section: {sec.section_type:15s} heading={sec.heading!r:40s} chars={len(sec.text)}")

# Run AG05
agent = StatsLabelAgent(client)
output = agent.extract(paper_map)

print(f"\n{'='*80}")
print(f"AG05 produced {len(output.span_labels)} span_labels")
print(f"Metadata: {output.metadata}")
print(f"{'='*80}\n")

for i, sl in enumerate(output.span_labels, 1):
    print(f"  [{i:2d}] type={sl.label_type:20s} value={str(sl.value)[:40]:40s} "
          f"grp_id={str(sl.grouping_id):15s} conf={sl.confidence:.2f} "
          f"arm={sl.arm_assignment} section={sl.source_section}")

# Grouping analysis
from crci.llm.response_schemas import PRIMARY_EFFECT_TYPES, PRECISION_TYPES
n_primary = sum(1 for sl in output.span_labels if sl.label_type in PRIMARY_EFFECT_TYPES)
n_precision = sum(1 for sl in output.span_labels if sl.label_type in PRECISION_TYPES)
n_grouped = sum(1 for sl in output.span_labels if sl.grouping_id)
print(f"\nPrimary effects: {n_primary}, Precision: {n_precision}, Grouped: {n_grouped}")
print(f"Retry fired: {output.metadata.get('grouping_retry', 'N/A')}")
print(f"Complete groups: {output.metadata.get('n_complete_groups', 'N/A')}")
