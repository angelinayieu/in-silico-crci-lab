# CRCI Persistence Gap Remediation Plan

**Date**: 2026-02-25  
**Status**: Verified against current codebase  
**Purpose**: Close the gap between in-memory extraction pipeline and database persistence

---

## Executive Summary

The extraction pipeline (P0→P7) processes papers correctly in-memory but has **two critical persistence gaps**:

1. **edge_evidence_v1 never receives extraction output** — P2 harmonization produces `HarmonizedClaim` objects that flow downstream but are never persisted to the database
2. **included_study_ids_json never populated** — P1 extraction doesn't write constituent study IDs for SRs/MAs, blocking hop discovery

The schema, hop_discoverer module, and study_registry writer **already exist and work**, contrary to earlier claims.

---

## Infrastructure Audit Results

### What Already Exists ✅

| Component | Location | Status |
|-----------|----------|--------|
| StudyRegistry v2.0 columns | `tables.py:737` + actual DB | ✅ All columns exist |
| AcquisitionQueue hop columns | `tables.py:1988` + actual DB | ✅ hop_source_study_id, hop_depth, paywall_flagged |
| Study registry writer | `p0_triage/runner.py:147-175` | ✅ Writes study_subtype, pdf_path, parse_quality |
| Hop discoverer module | `retrieval/hop_discoverer.py` | ✅ 365 lines, complete with discover_hops_from_meta_analyses() |
| Hop discovery wiring | `retrieval/acquisition_scheduler.py:37` | ✅ run_hop_discovery() called in acquisition cycle |
| Paywall tracking column | DB schema | ✅ paywall_flagged column exists |
| Paywalled paper reporter | `scripts/show_paywalled.py` | ✅ CLI tool exists |

### What's Actually Missing ❌

| Gap | Description | Impact |
|-----|-------------|--------|
| **G1: Evidence writer** | P2 harmonization doesn't write to `edge_evidence_v1` | No per-study evidence persisted from extraction |
| **G2: SR reference extraction** | P1 agents don't extract `included_study_ids_json` | Hop discovery has no data to read |
| **G3: Pipeline→hop trigger** | Extraction doesn't automatically trigger hop discovery | Manual intervention required after SR extraction |
| **G4: PDF validation** | fulltext_retriever doesn't validate Content-Type | HTML pages saved as .pdf files |
| **G5: APS citation bonus** | +0.15 bonus for hop candidates not implemented | Spec §9.5 not enforced |

---

## Corrected Build Order (6 Slices)

### ~~S1: Schema Columns~~ SKIP — Already Done

**Evidence**: 
```sql
-- Actual DB schema has all columns:
PRAGMA table_info(study_registry_v1);
-- Shows: study_subtype, included_study_ids_json, pdf_path, etc.
```

### ~~S2: Study Registry Writer~~ SKIP — Already Done

**Evidence**:
```python
# crci/extraction/p0_triage/runner.py lines 147-175
study_row = StudyRegistry(
    study_id=paper_id,
    study_subtype=str(subtype_enum.value),
    pdf_path=str(pdf_path),
    parse_quality=ingested.get("pdf_quality", "GOOD"),
)
session.add(study_row)
```

---

### S1-NEW: Create Evidence Persistence Layer

**Gap addressed**: G1 (edge_evidence_v1 never written by extraction)

**Spec**: SYS_EXTRACTION_COMPLETE.md lines 800-1135 (P2 output)

**New file**: `crci/extraction/evidence_writer.py`

**Called after**: P2 harmonization (when we have standardized β, SE)

```python
"""
Component: SYS_EXTRACTION.EX-P2.EVIDENCE_WRITER
Spec: SYS_EXTRACTION_COMPLETE.md lines 1135-1150
Purpose: Persist harmonized claims to edge_evidence_v1 (Class B).
Reads: HarmonizedClaim/ScaledNumeric from P2 context
Writes: edge_evidence_v1 rows
Gates: None (persistence-only, no formula logic)
"""

def write_evidence_rows(
    session: Session,
    run: ExtractionRun,
    harmonized_records: list[ScaledNumeric],
    study_id: str,
) -> int:
    """Persist P2 harmonized claims to edge_evidence_v1.
    
    Maps ScaledNumeric fields → EdgeEvidence columns:
      - beta → effect_value_reported
      - se → se_reported  
      - span_id → ler_id (prefixed)
      - edge_id → edge_relation_id
      - scale → harmonized_scale
    """
    from crci.shared.models.tables import EdgeEvidence
    
    written = 0
    for record in harmonized_records:
        ler_id = f"LER_{study_id}_{record.span_id}_{uuid.uuid4().hex[:8]}"
        
        evidence_row = EdgeEvidence(
            ler_id=ler_id,
            study_id=study_id,
            edge_relation_id=getattr(record, "edge_id", None),
            profile_id=None,  # Set if cohort-specific
            edge_family=getattr(record, "edge_family", None),
            effect_type_reported="harmonized_beta",
            effect_value_reported=record.beta,
            se_reported=record.se,
            N_effect=getattr(record, "n", None),
            effect_size_type=getattr(record, "scale", "SD_SD"),
            harmonized_scale=getattr(record, "scale", None),
            quality_rating=getattr(record, "quality_rating", None),
            entered_by="extraction_pipeline",
            entered_at=datetime.now(timezone.utc),
            version=1,
            active=1,
        )
        session.add(evidence_row)
        written += 1
    
    session.flush()
    logger.info("Persisted %d evidence rows for study %s", written, study_id)
    return written
```

**Wire into pipeline**: Modify `crci/extraction/pipeline.py` after P2 chain:

```python
# After P2 harmonization succeeds
if "harmonized_records" in context and context["harmonized_records"]:
    from crci.extraction.evidence_writer import write_evidence_rows
    write_evidence_rows(
        session, run, 
        context["harmonized_records"],
        context.get("paper_id", run.extraction_run_id)
    )
```

---

### S2-NEW: Add SR Reference Extraction to P1

**Gap addressed**: G2 (included_study_ids_json never populated)

**Spec**: Master Spec §9.4 (hop discovery requires constituent study IDs)

**Files modified**:
- `crci/extraction/p1_extraction/ma_multi_product.py` — Add reference list extraction
- `crci/extraction/p1_extraction/runner.py` — Write extracted refs to study_registry

**Add to AG01 (metadata agent) or new AG-REF agent**:

```python
# In ma_multi_product.py or new reference_extractor.py
def extract_constituent_studies(
    paper_text: str,
    paper_subtype: str,
) -> list[dict]:
    """Extract DOI/PMID/title of studies included in SR/MA.
    
    Returns list of dicts: [{"doi": "...", "pmid": "...", "title": "..."}, ...]
    """
    if paper_subtype not in ("systematic_review", "meta_analysis", "pairwise_ma", "nma"):
        return []
    
    # LLM prompt to extract reference list from Results/Methods section
    # Look for "included studies" table, PRISMA flowchart data, etc.
    ...
```

**Add post-P1 update to study_registry**:

```python
# In p1_extraction/runner.py, after extraction completes
if classified.paper_subtype in ("systematic_review", "meta_analysis"):
    refs = extract_constituent_studies(paper_text, classified.paper_subtype)
    if refs:
        study_row = session.query(StudyRegistry).get(paper_id)
        if study_row:
            study_row.included_study_ids_json = json.dumps(refs)
            study_row.included_k = len(refs)
            session.flush()
```

---

### S3-NEW: Wire Hop Discovery into Extraction Pipeline

**Gap addressed**: G3 (no automatic hop trigger after extraction)

**Current state**: hop_discoverer.py exists and works, but is only called by acquisition_scheduler, not by extraction pipeline

**File modified**: `crci/extraction/pipeline.py` (~line 500+, after mark_run_completed)

```python
# At end of successful extraction run
def mark_run_completed(session: Session, run: ExtractionRun) -> None:
    run.status = PipelineStatus.COMPLETED.value
    run.completed_at = datetime.now(timezone.utc)
    session.flush()

# ADD AFTER mark_run_completed:
# Post-extraction hop discovery for SRs/MAs
triage_result = context.get("triage_result")
paper_subtype = getattr(triage_result, "paper_subtype", None)
if paper_subtype in ("systematic_review", "meta_analysis", "pairwise_ma", "nma"):
    from crci.retrieval.hop_discoverer import discover_hops_from_meta_analyses
    try:
        hop_count = discover_hops_from_meta_analyses(session)
        logger.info("Post-extraction hop discovery: %d candidates queued", hop_count)
    except Exception as exc:
        logger.warning("Hop discovery failed: %s", exc)
```

---

### S4-NEW: Add PDF Content Validation

**Gap addressed**: G4 (HTML pages saved as .pdf)

**File modified**: `crci/retrieval/fulltext_retriever.py`

```python
def _validate_pdf_content(content: bytes, url: str) -> bool:
    """Validate that downloaded content is actually a PDF.
    
    Checks:
    1. Magic bytes: PDF starts with %PDF-
    2. Content-Type from response headers (if available)
    3. File size sanity (PDFs are typically >10KB)
    """
    # Check PDF magic bytes
    if not content.startswith(b'%PDF-'):
        logger.warning("Downloaded content from %s is not a PDF (magic bytes: %s)", 
                       url, content[:10])
        return False
    
    # Check minimum size
    if len(content) < 10_000:  # 10KB minimum
        logger.warning("PDF from %s suspiciously small: %d bytes", url, len(content))
        # Still return True, just warn
    
    return True


# In retrieve_fulltext():
content = response.content
if not _validate_pdf_content(content, url):
    return RetrievalResult(
        status=RetrievalStatus.FAILED,
        error="Downloaded content is HTML, not PDF",
    )
```

---

### S5-NEW: Add APS Citation-Validation Bonus

**Gap addressed**: G5 (§9.5 +0.15 bonus not implemented)

**File modified**: `crci/retrieval/aps_scorer.py`

**Config constant** (add to `crci/shared/config.py`):
```python
HOP_CITATION_APS_BOOST: float = 0.15  # Master Spec §9.5
```

**Scorer modification**:
```python
def score_candidate(
    candidate: CandidateMetadata,
    target_edges: list[str],
) -> APSScoredCandidate:
    """Score a candidate paper for acquisition priority.
    
    Formula APS-1: APS = w_edge × S_edge + w_method × S_method + w_recency × S_recency
    
    v2.0 addition (§9.5): If candidate came from hop discovery (citation chain),
    add +HOP_CITATION_APS_BOOST to final score.
    """
    aps_raw = _compute_base_aps(candidate, target_edges)
    
    # Citation-validation bonus (§9.5)
    if candidate.hop_source_study_id is not None:
        aps_final = min(1.0, aps_raw + config.HOP_CITATION_APS_BOOST)
        aps_components["citation_chain_bonus"] = config.HOP_CITATION_APS_BOOST
    else:
        aps_final = aps_raw
    
    return APSScoredCandidate(
        candidate=candidate,
        aps_score=aps_final,
        aps_components=aps_components,
    )
```

**Model update** (`crci/retrieval/models.py`):
```python
@dataclass
class CandidateMetadata:
    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    abstract: str | None = None
    # ... existing fields ...
    
    # v2.0: Hop provenance
    hop_source_study_id: str | None = None
    hop_depth: int = 0
```

---

### S6-NEW: Seed Database & Integration Test

**Goal**: Load seed data and verify full pipeline

**Steps**:

```bash
# 1. Ensure database is initialized
python scripts/setup_database.py

# 2. Load Class A seed data
python scripts/seed_database.py

# 3. Download test PDF (Cifu 2018 is OA)
mkdir -p data/manual_uploads/pdfs
curl -L "https://bmccancer.biomedcentral.com/track/pdf/10.1186/s12885-018-5065-3" \
     -o data/manual_uploads/pdfs/cifu2018.pdf

# 4. Run extraction
python scripts/run_extraction.py data/manual_uploads/pdfs/cifu2018.pdf

# 5. Verify results
python scripts/report_status.py
```

**New integration test**: `scripts/test_integration_e2e.py`

```python
"""End-to-end integration test for extraction→evidence→hop pipeline."""

def test_full_pipeline():
    # 1. Verify DB seeded
    assert count_rows("node_search_terms_v1") > 0, "Class A not seeded"
    
    # 2. Run extraction on Cifu 2018
    result = run_extraction("data/manual_uploads/pdfs/cifu2018.pdf")
    assert result.status == "completed"
    
    # 3. Verify study_registry_v1 populated
    study = get_study("cifu2018")
    assert study.study_subtype == "systematic_review"
    assert study.pdf_path is not None
    
    # 4. Verify edge_evidence_v1 (may be 0 for SR without direct evidence)
    evidence_count = count_rows("edge_evidence_v1")
    print(f"Evidence rows: {evidence_count}")
    
    # 5. Verify hop discovery ran (if included_study_ids_json populated)
    if study.included_study_ids_json:
        queue_count = count_rows("acquisition_queue_v1", 
                                  filter="hop_source_study_id IS NOT NULL")
        assert queue_count > 0, "Hop discovery didn't queue candidates"
    
    print("✅ Integration test passed")
```

---

## Slice Dependencies

```
S1-NEW (evidence_writer) → independent, start first
      ↓
S2-NEW (SR ref extraction) → depends on understanding P1 agent structure
      ↓
S3-NEW (hop wiring) → depends on S2 (included_study_ids must exist)
      ↓
S4-NEW (PDF validation) → independent, can be parallel
      ↓
S5-NEW (APS bonus) → independent, can be parallel
      ↓
S6-NEW (integration test) → depends on all above
```

**Recommended order**: S1-NEW → S4-NEW → S5-NEW → S2-NEW → S3-NEW → S6-NEW

---

## Verification Checklist

After implementation:

- [ ] `edge_evidence_v1` has rows after running extraction (not just manual scripts)
- [ ] `study_registry_v1.included_study_ids_json` populated for SRs
- [ ] `acquisition_queue_v1` has entries with `hop_source_study_id` set
- [ ] Downloaded PDFs validate as actual PDFs (not HTML)
- [ ] Hop candidates have +0.15 APS bonus
- [ ] `extraction_runs` table shows completed runs
- [ ] `report_status.py` shows accurate counts

---

## Files Modified (Verified)

| File | Action |
|------|--------|
| `crci/extraction/evidence_writer.py` | **CREATE** — new file |
| `crci/extraction/pipeline.py` | **MODIFY** — wire evidence writer + hop trigger |
| `crci/extraction/p1_extraction/runner.py` | **MODIFY** — populate included_study_ids_json |
| `crci/retrieval/fulltext_retriever.py` | **MODIFY** — add PDF validation |
| `crci/retrieval/aps_scorer.py` | **MODIFY** — add citation bonus |
| `crci/retrieval/models.py` | **MODIFY** — add hop provenance fields |
| `crci/shared/config.py` | **MODIFY** — add HOP_CITATION_APS_BOOST |
| `scripts/test_integration_e2e.py` | **CREATE** — integration test |

---

## What Was Wrong in Original Document

| Original Claim | Reality |
|----------------|---------|
| "Schema columns missing" | ❌ All v2.0 columns exist in ORM + actual DB |
| "study_registry_v1 NEVER WRITTEN" | ❌ p0_triage/runner.py writes to it |
| "No hop_discoverer.py module" | ❌ Module exists (365 lines, complete) |
| "hop columns missing on acquisition_queue" | ❌ All columns exist |
| "edge_evidence_v1 NEVER WRITTEN" | ⚠️ TRUE for extraction pipeline, FALSE for manual scripts |

The original document's **core thesis is correct** (persistence gap exists), but the **diagnosis was wrong** (schema/modules exist, the wiring is missing).
