═══════════════════════════════════════════════════════════════════════════
           SYS_EXTRACTION — COMPLETE SPECIFICATION
           (Tier 1: System Card + Tier 2: Chain Cards + Tier 3: Subsystem Cards)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0 (merged canonical)
Date: 2026-02-24

═══════════════════════════════════════════════════════════════════════════
                    PART 1: TIER 1 — SYSTEM CARD
═══════════════════════════════════════════════════════════════════════════

1. IDENTITY
   System ID:      SYS_EXTRACTION
   Name:           Evidence Extraction System
   Purpose:        Transform published papers into typed, harmonized, quality-graded
                   evidence records that populate the Bayesian causal model
   Scope:          Everything from paper intake to aggregated edge update.
                   Excludes runtime patient inference and UI rendering.
   Timing:         Build-time (per-paper, incremental as new literature arrives)

2. MACRO CHAIN (v2.0 — with Acquisition Loop + Annotation Path)

                    ┌─────────┐        ┌─────────────────┐
  PDF ─────────────▶│ EX-P0   │───────▶│ EX-P1 (v2)      │
  (paper)           │ TRIAGE  │        │ HYBRID MULTI-    │
      ▲             │ + PTC   │        │ AGENT EXTRACTION │
      │             └────┬────┘        └──┬──────────┬────┘
      │                  │                │          │
      │            triage_records    SpanLabels  RawAnnotations
      │                  │                │          │
      │                  │           ┌────┴────┐  ┌──┴──────────┐
      │                  │           │ EX-TB   │  │ EX-P1-REC   │
      │                  │           │ TRUST   │  │ Reconcile + │
      │                  │           │ BOUNDARY│  │ ATB validate│
      │                  │           └────┬────┘  └──┬──────────┘
      │                  │                │          │
      │                  │         TypedNumeric  study_annotations_v1
      │                  │                │          │ (22 categories)
      │             ┌────┴────────────────┴────┐     │
      │             │            EX-P2           │     │
      │             │   HARMONIZATION & GATING   │     │
      │             └────────────┬───────────────┘     │
      │                         │                      │
      │                  HarmonizedClaims               │
      │                         │                      │
      │             ┌───────────┴────────────┐         │
      │             │          EX-P3         │         │
      │             │   SEVEN-LAYER HETERO.  │         │
      │             └───────────┬────────────┘         │
      │                         │                      │
      │                  CalibratedRecords              │
      │                         │                      │
      │   ┌─────────────────────┼─────────────────┐    │
      │   │                     │                  │    │
      │   │  ┌─────────────┐ ┌──┴──────────┐ ┌────┴───┴──┐
      │   │  │  EX-P2E     │ │  EX-P4 (v2) │ │  EX-P4B   │
      │   │  │  EXTENDED   │ │ AGGREGATION  │ │  PUB BIAS │
      │   │  │  EXTRACT    │ │ + DCR + σ²   │ │  ASSESS   │
      │   │  └─────────────┘ └──────┬───────┘ └───────────┘
      │   │                         │
      │   │                  edges_v1 (β̂, SE_eff, P_incl,
      │   │                   sigma_sq_structural, overlap_decision)
      │   │                         │
      │   │             ┌───────────┴───────────┐
      │   │             │       EX-P5           │
      │   │             │ SUFFICIENCY & CHECK    │
      │   │             └───┬───────────────┬───┘
      │   │                 │               │
      │   │          ┌──────┴──────┐  evidence_gaps
      │   │          │    EX-P6    │        │
      │   │          │ DEPLOY VAL  │   ┌────┴──────────┐
      │   │          └─────────────┘   │  EX-ACQ (NEW) │
      │   │                            │ ACQUISITION    │
      │   │                            │ LOOP           │
      │   └────────────────────────────┤ APS scoring    │
      │                                └────────┬───────┘
      └─────────────────────────────────────────┘
                                        (papers fed back to EX-P0)

                              ┌───────────────────┐
      study_annotations_v1───▶│ EX-PROM (NEW)     │───▶ Human review
      (accumulated)           │ PROMOTION MONITOR  │     → Class A table
                              │ Threshold + Indep. │     modifications
                              └───────────────────┘

3. CHAIN INVENTORY (v2.0 — 12 chains)

| Order | Chain ID | Name | Input | Output | Subsystems | Phase | Status |
|-------|----------|------|-------|--------|------------|-------|--------|
| 0 | EX-P0 | Pre-Extraction Triage | PDF + metadata | triage_record + PTC + route | 5 | Build-time | UPDATED (+PTC) |
| 1 | EX-P1 | Hybrid Multi-Agent Extraction | Paper + PaperType | SpanLabel[] + Annotations | 14 | Build-time | REWRITTEN (v2) |
| TB | EX-TB | Trust Boundary | SpanLabels (LLM) | TypedNumericValues (verified) | 2 | Build-time | Unchanged |
| 2 | EX-P2 | Harmonization & Gating | TypedNumericValues | HarmonizedClaims | 7 | Build-time | Unchanged |
| 2E | EX-P2E | Extended Extraction | Conditional papers | Extended evidence | 3 | Build-time | Unchanged |
| 3 | EX-P3 | Seven-Layer Heterogeneity | HarmonizedClaims | CalibratedRecords | 9 | Build-time | Unchanged |
| 4 | EX-P4 | Aggregation + DCR | CalibratedRecords + annotations | Updated edges_v1 | 5 | Build-time | UPDATED (+DCR, +σ²) |
| 4B | EX-P4B | Publication Bias | Evidence pool | Bias-adjusted estimates | 4 | Build-time | Unchanged |
| 5 | EX-P5 | Sufficiency & Coherence | Updated edges_v1 | gaps + coherence flags | 7 | Build-time | Unchanged |
| 6 | EX-P6 | Deployment Validation | Updated model | deployment_decision | 2 | Build-time | Unchanged |
| ACQ | EX-ACQ | Acquisition Loop | Gap queries + annotations | Retrieved papers → EX-P0 | 3 | Scheduled | NEW |
| PROM | EX-PROM | Promotion Monitor | Accumulated annotations | Promotion proposals | 3 | Scheduled | NEW |

4. TABLE INVENTORY (v2.0 — +4 new tables, 1 reclassified)

| Class | Table ID | Row Semantics | Writers | Readers |
|-------|----------|---------------|---------|---------|
| A (Knowledge) | nodes_v1 | 1 node definition | Human | EX-P0, ALG-A |
| B (Evidence) | edge_evidence_v1 | 1 evidence record per study×edge | EX-P2, EX-TB | EX-P3, EX-P4, ALG-B |
| B (Evidence) | study_registry_v1 | 1 study metadata record | EX-P0 | EX-P1, EX-P2, EX-ACQ |
| B (Derived) | study_annotations_raw_v1 (B10) | 1 agent emission per paper | EX-P1-REC | Audit, Calibration | NEW |
| B (Derived) | study_annotations_v1 (B11) | 1 reconciled annotation | EX-P1-ATB | EX-P4, EX-ACQ, EX-PROM | NEW |
| B (Audit) | extraction_runs (B12) | 1 provenance record per run | EX-P1 | All EX chains | NEW |
| B (Derived) | acquisition_queue_v1 (B13) | 1 acquisition candidate | EX-ACQ-RET | EX-ACQ, Scheduler | RECLASSIFIED E→B |
| C (Compiled) | edges_v1 | 1 edge with pooled β̂, SE_eff | EX-P4 | ALG-A, ALG-B |
| E (Audit) | triage_records_v1 | 1 triage decision per paper | EX-P0 | EX-P1 |
| E (Audit) | extraction_audit_v1 | 1 audit record per extraction | EX-P1 | QA |
| E (Audit) | assimilation_log_v1 | 1 record per assimilation decision | EX-P3 | QA |
| E (Audit) | aggregation_log_v1 | 1 record per edge update | EX-P4 | QA |

   SCHEMA UPDATES (v2.0):
     edges_v1: +sigma_sq_structural (float, default 0.25), +overlap_decision (ENUM)
     edge_evidence_v1: +parent_meta_study_id (TEXT FK, nullable)
     edge_param_builds_v1: +annotation_source_ids_json (JSON FK)

5. CROSS-CUTTING CONCERNS
   - Trust Boundary: ALL LLM output must pass through EX-TB before becoming numeric evidence
   - Annotation Trust Boundary: ALL annotations pass through EX-P1-ATB (6 rules) before
     persisting to study_annotations_v1. Annotations NEVER directly modify edges_v1.
   - Quality gates G1-G16: Field validation at commit time
   - S1 (Reproducibility), S2 (Auditability), S2.5 (Composability) gates span chains
   - Evidence freshness: temporal decay applied in EX-P3 (L6)
   - SD_SD scale standardization across all studies
   - State Machines (v2.0): 6 entities with formal lifecycles:
       Paper ingestion (13 states), Extraction run (5), Annotation (4: raw→reviewed→promoted/archived),
       Acquisition queue item (7), Promotion proposal (5), Human review task (6)
   - Observability: correlation IDs span all chains:
       extraction_run_id (root), study_id (paper), source_span_id (span), acquisition_queue_id
   - Soft invalidation: Annotations and evidence rows NEVER deleted; invalidated via active=0
   - Idempotency: Every write has a natural dedup key; partial runs resume from last agent

6. EXTERNAL INTERFACES
   | Direction | External System | Data | Format |
   |-----------|----------------|------|--------|
   | INPUT | PDF repository | Published papers | PDF |
   | INPUT | PubMed/PRISMA/Crossref/OpenAlex | Search results + metadata | API/CSV |
   | OUTPUT | SYS_ALGORITHM | edges_v1 (updated), edge_evidence_v1 | Tables |
   | OUTPUT | Human reviewers | flagged_records, promotion proposals, overlap reviews | Reports |
   | LOOP | EX-ACQ → EX-P0 | Retrieved papers fed back into pipeline | PDF (v2.0) |


═══════════════════════════════════════════════════════════════════════════
                    PART 2: TIER 2 — CHAIN CARDS
═══════════════════════════════════════════════════════════════════════════

TABLE NAME BINDING KEY (EX system):
  triage_records       → triage_records_v1 (Class E)
  study profiles       → study_registry_v1 (Class B)
  edge_evidence (raw)  → edge_evidence_v1 (Class B, 76 columns — +parent_meta_study_id)
  extraction_audit     → extraction_audit_v1 (Class E)
  edges compiled       → edges_v1 (Class C, 118 rows — +sigma_sq_structural, +overlap_decision)
  assimilation_log     → assimilation_log_v1 (Class E)
  aggregation_log      → aggregation_log_v1 (Class E)
  annotations (raw)    → study_annotations_raw_v1 (Class B, 13 cols) NEW
  annotations (canon)  → study_annotations_v1 (Class B, 18 cols) NEW
  extraction_runs      → extraction_runs (Class B, 11 cols) NEW
  acquisition_queue    → acquisition_queue_v1 (Class B — was E, reclassified)

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P0 (Pre-Extraction Triage)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P0
   Name:           Pre-Extraction Triage
   Purpose:        Screen incoming papers for CRCI relevance, extract metadata,
                   assign execution mode, route to appropriate extraction path
   Phase:          Build-time (per-paper)
   Paper §:        §2.5 (implied — intake stage)
   Subsystems:     5 (was 4; +PTC Paper Type Classifier)

2. CHAIN DIAGRAM

 PDF + PubMed metadata
   │
   ▼
 ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
 │  P0-S1    │────▶│  P0-S2    │────▶│  P0-S3    │────▶│  P0-S4    │
 │  PDF      │     │  Relevance│     │  Execution│     │  Route    │
 │  Ingest   │     │  Screening│     │  Mode     │     │  Decision │
 │           │     │           │     │  Selection│     │           │
 └───────────┘     └───────────┘     └───────────┘     └───────────┘
 canonical_text    relevance_score   exec_mode         → EX-P1 or REJECT
                                                       → triage_records_v1

3. INTERMEDIATE STATE SCHEMAS

State: IngestedPaper (after P0-S1)
| Field | Type | Description |
|-------|------|-------------|
| canonical_text | str | Full text extracted from PDF |
| pdf_quality | enum{GOOD,DEGRADED,SCAN} | PDF parsing quality |
| page_count | int | Number of pages |
| has_tables | bool | Statistical tables detected |
| has_figures | bool | Figures detected |

State: ScreenedPaper (after P0-S2)
| Field | Type | Description |
|-------|------|-------------|
| relevance_score | float [0,1] | CRCI relevance probability |
| inclusion_criteria | dict[criterion→bool] | 5 criteria checked |
| exclusion_criteria | dict[criterion→bool] | 3 exclusion checks |

4. SUBSYSTEM DETAIL

## P0-S1 — PDF Ingestion & Text Extraction
   Purpose: Convert PDF to canonical text, assess quality
   Input: PDF file + PubMed metadata
   Output: IngestedPaper (canonical_text, quality flags)
   Logic:
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P0-S1a — PDF Parsing                              │
   │ Purpose: Extract text preserving table structure              │
   │ Logic:   Use PDF parser (pdfplumber/pymupdf)                │
   │          Detect tables via line detection + cell extraction   │
   │          Preserve paragraph structure + section headers       │
   │          Quality assessment: char density, encoding issues    │
   │ Rules:   Scanned PDFs → OCR pipeline (flag DEGRADED)        │
   │          Encrypted PDFs → REJECT                             │
   └─────────────────────────────────────────────────────────────┘

## P0-S2 — Relevance Screening
   Purpose: Determine if paper is relevant to CRCI evidence base
   Input: IngestedPaper + PubMed metadata
   Output: ScreenedPaper (relevance_score, criteria)
   Logic:
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P0-S2a — Inclusion Criteria Check                  │
   │ 5 inclusion criteria (all must be met):                      │
   │   1. Cancer population (any type)                            │
   │   2. Cognitive outcome OR biological mechanism measure        │
   │   3. Original data (not review/commentary)                   │
   │   4. Human subjects (or mechanistic animal with translation) │
   │   5. Published in peer-reviewed venue                        │
   │ 3 exclusion criteria (any triggers REJECT):                  │
   │   1. Duplicate (DOI match against study_registry_v1)         │
   │   2. Retracted (cross-check retraction database)             │
   │   3. Sample size < 10 (underpowered)                         │
   │ Rules:   Score = proportion of inclusion met × (1 − any excl)│
   │          Score ≥ 0.8 → INCLUDE                               │
   │          0.5–0.8 → HUMAN_REVIEW                              │
   │          < 0.5 → EXCLUDE                                     │
   └─────────────────────────────────────────────────────────────┘

## P0-S3 — Execution Mode Selection
   Purpose: Assign SHALLOW/STANDARD/DEEP based on paper characteristics
   Input: ScreenedPaper + metadata
   Output: execution_mode
   Logic:
   ┌─────────────────────────────────────────────────────────────┐
   │ Decision tree:                                               │
   │   RCT + cancer-specific + cognitive primary → DEEP           │
   │   Cohort/observational + cognitive outcome → STANDARD        │
   │   Case report / animal / biomarker-only → SHALLOW            │
   │   Unknown/ambiguous → STANDARD (safe default)                │
   │ DEEP: All 9 agents + ConceptEngine in EX-P1                  │
   │ STANDARD: All 9 agents                                       │
   │ SHALLOW: Agents 1, 2, 5, 9 only                              │
   └─────────────────────────────────────────────────────────────┘

## P0-S4 — Route Decision
   Purpose: Route paper to EX-P1 or reject, write triage record
   Input: All P0 outputs
   Output: route_decision → EX-P1 or REJECT; writes triage_records_v1
   Logic: INCLUDE → EX-P1; HUMAN_REVIEW → queue for human; EXCLUDE → log + stop

5. BOUNDARY TABLES
   READS: study_registry_v1 (duplicate check)
   WRITES: triage_records_v1, study_registry_v1 (new entry)

6. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P0-G1 | PDF parsed successfully | → P0-S2 | REJECT: unparseable |
   | P0-G2 | Relevance ≥ 0.5 | → P0-S3 | EXCLUDE + log |
   | P0-G3 | Not duplicate | → P0-S4 | SKIP: already processed |



═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P1 v2 (Hybrid Multi-Agent Extraction)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P1
   Name:           Hybrid Multi-Agent Extraction
   Purpose:        Extract structured scientific claims AND strategic annotations
                   from paper text using a Canonical Reader + 10 parallel specialist
                   agents + cross-agent reconciliation
   Phase:          Build-time (per-paper)
   Paper §:        §2.5 (Evidence Extraction)
   Subsystems:     14 (was 10: +CR, +AG10, +REC, +ATB)
   Replaces:       Original EX-P1 (9 sequential agents + ConceptEngine)

   KEY ARCHITECTURAL CHANGE (v2): Agents 1-10 execute in PARALLEL on targeted
   PaperMap sections (not sequentially on full paper). Canonical Reader reads
   paper ONCE, produces shared PaperMap. New annotation pathway captures strategic
   intelligence (limitations, mechanism hypotheses, research gaps).

2. CHAIN DIAGRAM

 PDF + canonical_text + TriageDecision + PaperTypeClassification
   │
   ▼
 ┌────────────────┐
 │ EX-P1-CR       │   PaperMap (in-memory, shared)
 │ Canonical      │───────────────────────────────────────────┐
 │ Reader         │                                           │
 │ (reads ONCE)   │   (escape hatch: agents request raw chunks)
 └────────────────┘                                           │
                     ┌────────────────────────────────────────┤
                     │ PaperMap distributed to all specialists │
                     ▼                                        ▼
 ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
 │AG1 │ │AG2 │ │AG3 │ │AG4 │ │AG5 │ │AG6 │ │AG7 │ │AG8 │ │AG9 │ │AG10│
 │Meta│ │Desg│ │Coho│ │Outc│ │Stat│ │Expo│ │Medi│ │Temp│ │Reco│ │Strt│
 │data│ │n   │ │rt  │ │ome │ │Labl│ │sure│ │ator│ │oral│ │nc  │ │Intl│
 └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘
   │      │      │      │      │      │      │      │      │      │
   │ SpanLabel[] + RawAnnotation[]                                │
   └──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
   ┌────────────────┐                         ┌─────────────────┐
   │ EX-P1-AG9      │ ReconcReport            │ EX-P1-REC (NEW) │
   │ SpanLabel      │ (span-level)            │ Annotation       │
   │ Reconciliation │                         │ Reconciliation   │
   │ (7 checks)     │                         │ (dedup, merge,   │
   └────────┬───────┘                         │ conflict detect) │
            │                                 └────────┬────────┘
            ▼                                          ▼
   ┌────────────────┐                         ┌─────────────────┐
   │ EX-P1-CE       │                         │ EX-P1-ATB (NEW) │
   │ ConceptEngine  │                         │ Annotation Trust │
   │ (ontology      │                         │ Boundary         │
   │ grounding)     │                         │ (AT-01—AT-06)    │
   └────────┬───────┘                         └────────┬────────┘
            │                                          │
       SpanLabel[]                           study_annotations_v1
       → EX-TB                               study_annotations_raw_v1

 EXECUTION MODES:
   SHALLOW:   CR + AG1, AG2, AG5, AG9 (quick screen; NO annotations)
   STANDARD:  CR + AG1-AG10, AG9 + CE + REC + ATB (full extraction + annotations)
   DEEP:      CR + AG1-AG10, AG9 + CE + REC + ATB + Tier-2 re-reads

3. INTERMEDIATE STATE SCHEMAS

   ### State: PaperMap (produced by CR, consumed by AG1-AG10)
   | Field | Type | Description |
   |-------|------|-------------|
   | sections | SectionSegment[] | Section type + chunk_id + char offsets |
   | tables | TableRef[] | table_number + caption + location + chunk_id |
   | figures | FigureRef[] | figure_number + caption + location + chunk_id |
   | candidate_spans | CandidateSpan[] | span_id + chunk_id + span_type + confidence |
   | basic_study_object | StudyObject | design, population_n, interventions[], outcomes[] |
   | paper_hash | TEXT | SHA-256 of canonical paper text |
   | paper_map_hash | TEXT | SHA-256 of PaperMap output |

   ### State: RawAnnotationEmission (produced by AG1-AG10, consumed by REC)
   | Field | Type | Description |
   |-------|------|-------------|
   | agent_id | TEXT | Emitting agent (AG1-AG10) |
   | category | ENUM (22 values) | Annotation category |
   | target_entity_type | ENUM | {edge, node, pathway, instrument, intervention, population, global} |
   | target_entity_id | TEXT | Specific entity annotated |
   | content | TEXT | Human-readable summary only |
   | structured_data_json | JSON? | Machine-parseable payload only |
   | evidence_strength | ENUM | {strong, moderate, weak, speculative} |
   | extraction_snippet | TEXT | Section label + page + text fragment |
   | source_span_id | TEXT? | PaperMap span reference |

   ### State: SpanLabel (output to EX-TB — UNCHANGED from v1)
   | Field | Type | Description |
   |-------|------|-------------|
   | span_text | str | Original text from paper |
   | char_start | int | Start offset in canonical text |
   | char_end | int | End offset in canonical text |
   | label_type | SpanLabelEnum (40 values) | What kind of statistic |
   | confidence | float [0-1] | Agent confidence |
   | grouping_id | str | Links related spans |

   ### State: ReconciliationDecision (produced by REC)
   | Field | Type | Description |
   |-------|------|-------------|
   | raw_annotation_ids | UUID[] | Which raw emissions were considered |
   | action | ENUM | {merge, keep_single, flag_conflict, discard_duplicate} |
   | canonical_annotation_id | UUID | Resulting canonical annotation ID |
   | cross_agent_support_n | int | Agents that emitted compatible annotations |
   | reconciled_confidence | float [0-1] | Final confidence |
   | adjudication_status | ENUM | {auto_merged, conflict, unreviewed} |

4. SUBSYSTEM INVENTORY

   | Order | ID | Name | Input | Output | Type | Status |
   |-------|----|------|-------|--------|------|--------|
   | 1 | EX-P1-CR | CanonicalReader | Paper + PaperType | PaperMap | COMPOSITE (4 sub-steps) | NEW |
   | 2 | EX-P1-AG1 | MetadataAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 3 | EX-P1-AG2 | DesignAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 4 | EX-P1-AG3 | CohortAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 5 | EX-P1-AG4 | OutcomeAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 6 | EX-P1-AG5 | StatsLabelAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 7 | EX-P1-AG6 | ExposureAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 8 | EX-P1-AG7 | MediatorAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 9 | EX-P1-AG8 | TemporalAgent | PaperMap | SpanLabel[] + Annotations | ATOMIC (LLM) | Updated |
   | 10 | EX-P1-AG9 | ReconciliationAgent | All SpanLabel[] | ReconcReport | ATOMIC (rule, 7 checks) | Unchanged |
   | 11 | EX-P1-AG10 | StrategicIntelAgent | PaperMap (Discussion) | Annotations only | ATOMIC (LLM) | NEW |
   | 12 | EX-P1-CE | ConceptEngine | All outputs + ontology | Grounded SpanLabels | ATOMIC (hybrid) | Unchanged |
   | 13 | EX-P1-REC | ReconciliationLayer | All RawAnnotations | ReconcDecisions + canonical | COMPOSITE (4 sub-steps) | NEW |
   | 14 | EX-P1-ATB | AnnotationTrustBoundary | ReconcDecisions | Validated annotations | COMPOSITE (6 rules) | NEW |

5. SUBSYSTEM DETAIL

## EX-P1-CR — Canonical Reader (NEW)
   Purpose: Read paper ONCE, produce shared PaperMap for all specialists
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: CR-a — Section Segmenter                          │
   │ Classify paper into structural sections (7+ types)          │
   │ Heading detection + structural heuristics by paper_subtype  │
   │ Output: SectionSegment[] with chunk_id, char_offsets        │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: CR-b — Table/Figure Registry                      │
   │ Enumerate all tables + figures with captions + locations     │
   │ Cross-reference table mentions in text                      │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: CR-c — Candidate Span Identifier                  │
   │ Pre-identify high-signal spans: numeric results (regex),    │
   │ limitation statements, mechanism claims, temporal markers    │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: CR-d — Basic Study Object                         │
   │ Quick parse: design, N, interventions, outcomes, timepoints │
   │ NOT detailed extraction — overview for agent routing        │
   └─────────────────────────────────────────────────────────────┘

## EX-P1-AG1 — MetadataAgent
   ID: EX-P1-AG1 | Type: ATOMIC (LLM) | ALWAYS runs
   Purpose: Extract study title, authors, DOI, journal, year, funding
   Reads: PaperMap.sections[Title, Abstract, Affiliations]
   Outputs: SpanLabel[] (author, year, journal) + RawAnnotation[] (funding_source)

## EX-P1-AG2 — DesignAgent
   ID: EX-P1-AG2 | Type: ATOMIC (LLM) | ALWAYS runs
   Purpose: Classify study design, randomization, blinding, control type
   Reads: PaperMap.sections[Methods, Abstract]
   Outputs: SpanLabel[] (design labels) + RawAnnotation[] (limitation_design)

## EX-P1-AG3 — CohortAgent
   ID: EX-P1-AG3 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract sample size, demographics, cancer type, treatment phase
   Reads: PaperMap.sections[Methods, Results tables]
   Outputs: SpanLabel[] (N, age, demographics) + Annotations (limitation_generalizability)

## EX-P1-AG4 — OutcomeAgent
   ID: EX-P1-AG4 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract outcome measures, instruments, measurement timepoints
   Reads: PaperMap.sections[Methods, Results]
   Outputs: SpanLabel[] (instrument names, timepoints) + Annotations (instrument_observation)

## EX-P1-AG5 — StatsLabelAgent (CRITICAL)
   ID: EX-P1-AG5 | Type: ATOMIC (LLM) | ALWAYS runs | Paper §: §2.5
   Purpose: Produce SpanLabel[] — grounded text spans with char offsets, 40 label types
   Reads: PaperMap.sections[Results, Tables] + PaperMap.candidate_spans
   Outputs: SpanLabel[] {text, char_start, char_end, label_type, confidence}
   Label types: mean, SD, SE, CI_lower, CI_upper, p_value, N, effect_size, OR, HR, RR...
   Validation: ≥1 SpanLabel; char offsets valid; no overlapping spans

## EX-P1-AG6 — ExposureAgent
   ID: EX-P1-AG6 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract exposure/intervention details, dosage, duration, adherence
   Reads: PaperMap.sections[Methods, Results]
   Outputs: SpanLabel[] (dose, duration) + Annotations (adherence_data, dose_response_qualitative)

## EX-P1-AG7 — MediatorAgent
   ID: EX-P1-AG7 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract potential mediators, biomarker pathways, mechanistic claims
   Reads: PaperMap.sections[Intro, Discussion, Biomarker results]
   Outputs: SpanLabel[] (biomarker values) + Annotations (mechanism_hypothesis)

## EX-P1-AG8 — TemporalAgent
   ID: EX-P1-AG8 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract measurement timepoints, follow-up duration, temporal patterns
   Reads: PaperMap.sections[Methods, Results]
   Outputs: SpanLabel[] (timepoints) + Annotations (temporal_onset_decay)

## EX-P1-AG9 — ReconciliationAgent (NO LLM — rule-based)
   ID: EX-P1-AG9 | Type: ATOMIC (rule-based) | ALWAYS runs | Paper §: §2.5
   Purpose: Run 7 span-level consistency checks across all agent SpanLabel outputs
   7 checks: duplicate detection, CI bracketing, p-value/CI consistency,
     N consistency, effect direction, missing groupings, orphan spans
   Decision: Each check → PASS / WARN / FAIL per SpanLabel pair

## EX-P1-AG10 — StrategicIntelAgent (NEW)
   ID: EX-P1-AG10 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract strategic intelligence from Discussion/Limitations/Conclusion
   Reads: PaperMap.sections[Discussion, Limitations, Conclusion]
   Outputs: RawAnnotation[] ONLY (no SpanLabels) — 7 primary categories:
     research_gap, future_research, practical_recommendation, mechanism_hypothesis,
     limitation_unmeasured_confounder, limitation_design, limitation_generalizability
   Decision: paper_subtype IN (case_report, qualitative, methods_paper) → SKIP mechanism_hypothesis

## EX-P1-CE — ConceptEngine (DEEP mode only)
   ID: EX-P1-CE | Type: ATOMIC (hybrid: rule + fuzzy match)
   Purpose: Ground extracted concepts to CRCI ontology (nodes_v1, instruments_v1)
   Inputs: SpanLabel[] from all agents + ontology tables
   Outputs: Grounded SpanLabel[] with resolved node_id, instrument_id, edge_relation_id

## EX-P1-REC — Reconciliation Layer (NEW)
   ID: EX-P1-REC | Type: COMPOSITE (4 sub-steps)
   Purpose: Merge duplicate annotations across agents, detect contradictions,
     assign confidence scores, produce canonical annotations from raw emissions
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: REC-a — Clusterer                                  │
   │ Group raw annotations by (category, entity_type, entity_id) │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: REC-b — DedupChecker                               │
   │ Pairwise Jaccard similarity (content + structured_data_json) │
   │ Threshold: 0.80 → merge candidate                           │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: REC-c — ConflictDetector                           │
   │ Identify contradictions: incompatible structured_data_json   │
   │ Category-specific rules (severity ordinals, directions, etc) │
   │ Assign conflict_severity: LOW / HIGH                        │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: REC-d — MergeDecider + ConfidenceScorer            │
   │ conf = min(1.0, 0.3 + 0.15×support_n + 0.2×mean_agent_conf)│
   │ If unresolved conflict → confidence capped at 0.50          │
   └─────────────────────────────────────────────────────────────┘
   Writes: study_annotations_raw_v1 (ALL raw emissions preserved for audit)

## EX-P1-ATB — Annotation Trust Boundary (NEW)
   ID: EX-P1-ATB | Type: COMPOSITE (6 rules)
   Purpose: Validate canonical annotations before persisting to study_annotations_v1
   ┌─────────────────────────────────────────────────────────────┐
   │ AT-01: Provenance mandatory (extraction_snippet + span_id)  │
   │ AT-02: Explicit vs inferred separation (strong ≠ speculative)│
   │ AT-03: Category-specific required fields:                    │
   │   adverse_event → severity; null_finding → powered_adequately│
   │   limitation_confounder → confounder_name (not generic)     │
   │ AT-04: Contradiction routing (conflict → held from wiring)  │
   │ AT-05: High-impact consumer gate (structural_variance,      │
   │   dag_expansion, safety_rules → require adjudication)       │
   │ AT-06: Speculative ceiling (speculative alone can't promote)│
   └─────────────────────────────────────────────────────────────┘
   Writes: study_annotations_v1 (validated), extraction_audit_v1 (rejected)
   Validation: rejection rate < 20% (if exceeded, agent prompts need tuning)

6. BOUNDARY TABLES
   | Direction | Table | Purpose |
   |-----------|-------|---------|
   | READS | biomarker_node_definitions_v1 | Ontology grounding (CE) |
   | READS | instrument_definitions_v1 | Instrument recognition (AG4, AG5) |
   | READS | edge_relations_definitions_v1 | Edge mapping (AG6, AG7, CE) |
   | WRITES | study_cohort_profiles_v1 | Cohort data from AG3 |
   | WRITES | extraction_audit_v1 | Agent performance metrics |
   | WRITES | study_annotations_raw_v1 | All agent annotation emissions (NEW) |
   | WRITES | study_annotations_v1 | Reconciled canonical annotations (NEW) |
   | WRITES | extraction_runs | Provenance record for this run (NEW) |

7. GATES & CHECKPOINTS
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P1-G1 | PaperMap has ≥3 sections | → Specialists | Fallback: sequential full-paper |
   | P1-G2 | ≥1 extractable effect OR ≥1 annotation | → REC + ATB | Paper yields nothing |
   | P1-G3 | AG9 7 span-level checks pass | Full confidence | Flags for human review |
   | P1-G4 | Contradiction rate < 30% of clusters | → ATB | Flag paper for review |
   | P1-G5 | extraction_mode gate | SHALLOW/STANDARD/DEEP routing | N/A |
   | P1-G6 | Per-batch escape_hatch_rate < 15% | Continue | Flag CR for review (NEW) |

8. ASSUMPTIONS
   | # | Assumption | Impact if Violated |
   |---|-----------|-------------------|
   | 1 | CR section segmentation correct ≥85% | Wrong sections → systematic extraction errors. Mitigated by escape hatch + P1-G6. |
   | 2 | Parallel execution ≈ sequential quality | Mitigated by PaperMap shared context + AG9 cross-checks. |
   | 3 | 22 annotation categories cover strategic content | Uncovered → lost. Monitor "unclassified observation". |
   | 4 | REC can detect semantic duplicates across agents | If dedup fails, annotation counts inflate. Mitigated by cross_agent_support_n tracking. |


═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-TB (Trust Boundary)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-TB
   Name:           Trust Boundary
   Purpose:        Convert LLM-extracted SpanLabels into verified TypedNumericValues
                   using deterministic parsing — NO LLM in this chain
   Phase:          Build-time (per-paper)
   Paper §:        §2.5 (implied — quality gate between LLM and evidence pipeline)
   Subsystems:     2 (NumericParser + ClaimNormalizer)
   Formulas:       11 (NP-01 through NP-11: numeric parsing rules)

2. CHAIN DIAGRAM

 SpanLabel[] (from EX-P1, LLM-produced)
   │
   ▼
 ┌───────────────────┐     ┌───────────────────┐
 │  EX-TB-NP         │────▶│  EX-TB-CN         │
 │  NumericParser     │     │  ClaimNormalizer   │
 │  (DETERMINISTIC)   │     │  (DETERMINISTIC)   │
 │  11 parse rules    │     │  SD_SD + mapping   │
 └───────────────────┘     └───────────────────┘
 TypedNumericValues          → edge_evidence_v1
                             → EX-P2

CRITICAL: This chain is the FIREWALL between LLM outputs and the
evidence database. No LLM-produced value enters edge_evidence_v1
without passing through deterministic numeric parsing.

3. SUBSYSTEM DETAIL

## EX-TB-NP — NumericParser (11 rules)
   Purpose: Parse raw text spans into typed numeric values
   Input: SpanLabel[] (from EX-P1-AG5)
   Output: TypedNumericValues (parsed, validated numeric records)
   ┌─────────────────────────────────────────────────────────────┐
   │ 11 PARSE RULES (NP-01 through NP-11):                      │
   │ NP-01: Mean ± SD extraction (pattern: "X ± Y" or "X (Y)")  │
   │ NP-02: CI extraction (pattern: "[X, Y]" or "X to Y")       │
   │ NP-03: P-value parsing (p<0.05, p=0.001, NS)               │
   │ NP-04: Effect size (Cohen's d, η², r, OR, HR, RR)          │
   │ NP-05: Sample size per group                                │
   │ NP-06: Percentage + proportion conversion                   │
   │ NP-07: Table cell extraction (row×column indexing)          │
   │ NP-08: Regression coefficient (β with SE or CI)             │
   │ NP-09: Correlation coefficient (r, ρ with CI)               │
   │ NP-10: F-statistic / t-statistic / χ² parsing              │
   │ NP-11: Missing data imputation flags (if SE missing)        │
   │                                                             │
   │ Each rule: regex pattern → typed value → validation check   │
   │ Validation: |β| ≤ 5 (plausibility), SE > 0, CI ordered,    │
   │             |r| ≤ 1, N > 0                                  │
   │ Parse failure → REJECT span (logged, not propagated)        │
   └─────────────────────────────────────────────────────────────┘

## EX-TB-CN — ClaimNormalizer
   Purpose: Normalize parsed values to SD_SD scale and map to DAG edges
   Input: TypedNumericValues (from NP)
   Output: Normalized claims → edge_evidence_v1
   ┌─────────────────────────────────────────────────────────────┐
   │ NORMALIZATION PIPELINE:                                     │
   │ 1. Scale identification: raw units → SD_SD / LOGHR / LOGOR │
   │ 2. SD borrowing: if study doesn't report SD, borrow from   │
   │    sd_anchors_v1 with SE inflation per anchor tier          │
   │ 3. Standardized effect: β_SD = raw_effect / SD_pooled      │
   │ 4. SE computation: from CI, p-value, or sample size         │
   │ 5. Edge mapping: source_node → target_node from edge_reg   │
   │ 6. Orientation alignment: ensure sign matches DAG convention│
   │ 7. Write to edge_evidence_v1 with full provenance           │
   │                                                             │
   │ Rules: Multiple claims per paper OK (different edges)       │
   │        Same edge from same paper → keep all, pool later     │
   │        Unmappable claims → flag for human review             │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: sd_anchors_v1 (borrowed SDs), nodes_v1 (edge mapping), edges_v1 (edge definitions)
   WRITES: edge_evidence_v1 (new evidence records)

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | TB-G1 | ≥1 span parsed successfully | → CN | REJECT paper: no parseable stats |
   | TB-G2 | Plausibility: |β|≤5, SE>0 | → edge_evidence_v1 | REJECT claim |
   | TB-G3 | Edge mapping found | → write | HUMAN_REVIEW: unmappable |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P2 (Harmonization & Gating)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P2
   Name:           Harmonization & Gating
   Purpose:        Validate, convert, and harmonize evidence records into
                   pipeline-ready format with quality gates
   Phase:          Build-time
   Paper §:        §2.5
   Subsystems:     7 (S1–S7)

2. CHAIN DIAGRAM

 TypedNumericValues (from EX-TB)
   │
   ▼
 ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
 │ S1  │─▶│ S2  │─▶│ S3  │─▶│ S4  │─▶│ S5  │─▶│ S6  │─▶│ S7  │
 │Plaus│  │Conve│  │Scale│  │Orien│  │Ident│  │Scope│  │Compo│
 │ibil.│  │rsion│  │Harm.│  │tation│  │ific.│  │Match│  │sabil│
 └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
                                                          │
                                                          ▼
                                                   HarmonizedClaims
                                                   → EX-P3

3. SUBSYSTEM DETAIL (7 stages)

## S1 — Plausibility Check (Gate P2-G1)
   |β| ≤ 5, SE > 0, CI properly ordered, |r| ≤ 1, N > 0
   Fail → WARNING (logged) or REJECT (extreme values)

## S2 — Conversion Appropriateness (4 checks: CG1–CG4)
   Check if effect size conversion is valid for this study type
   Fail → sign_only OR magnitude_only OR BLOCKED pathway

## S3 — Scale Harmonization
   Convert all effects to SD_SD scale (or LOGHR/LOGOR where appropriate)
   Apply SD borrowing from sd_anchors_v1 when study SD not reported
   SE inflation: Tier 1 (same population) 1.0×, Tier 2 (similar) 1.15×,
   Tier 3 (general) 1.30×

## S4 — Orientation Alignment
   Ensure effect sign matches DAG convention (POS_UP / POS_DOWN per node)
   Confidence threshold: orientation_confidence ≥ 0.60 for full effect
   Below threshold → magnitude_only (sign stripped)

## S5 — Identification Status Assignment
   Classify causal identification: Identified (1.00) / Partial (0.85) /
   Plausible (0.70) / Unidentified (0.50)
   Based on: study design + adjustment strategy + known confounders
   Maps to attenuation factor applied in ALG-B5

## S6 — Scope Matching
   Compute transportability score: how well does this study population
   match the CRCI target population?
   5 dimensions: cancer_type (0.35), treatment_phase (0.25), regimen (0.20),
   age (0.10), sex (0.10)
   w_scope = weighted match, floor 0.3 (max inflation 3.33×)

## S7 — Composability Check (Gate S2.5: 5 tests)
   Verify record is composable with existing evidence pool for target edge
   Check: correct scale for pool, compatible study design, no duplicate data
   Pass → EX-P3; Fail → record held for human review

4. BOUNDARY TABLES
   READS: edge_evidence_v1 (existing records), sd_anchors_v1, nodes_v1
   WRITES: edge_evidence_v1 (updated with harmonization flags)

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P2-G1 | Plausibility passed | → S2 | WARNING or REJECT |
   | CG1-4 | Conversion appropriate | → S3 | sign_only / magnitude_only / BLOCKED |
   | P2-G2 | Orientation confidence ≥ 0.60 | → S5 | magnitude_only |
   | S2.5 | Composability (5 tests) | → EX-P3 | Record held |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P3 (Seven-Layer Heterogeneity Pipeline)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P3
   Name:           Seven-Layer Heterogeneity Pipeline (SE Calibration)
   Purpose:        Apply 7 sequential adjustment layers to calibrate SE_eff per
                   evidence record — the SAME 7 layers applied in ALG-B2 but
                   here applied per-record before aggregation
   Phase:          Build-time (per-record)
   Paper §:        §2.9 (Seven-Layer Heterogeneity)
   Subsystems:     9 (7 layers + input assembly + output assembly)
   Formulas:       7 (one per layer, plus composite SE_eff)

2. CHAIN DIAGRAM

 HarmonizedClaims (from EX-P2)
   │
   ▼
 ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
 │ IN  │─▶│ L1  │─▶│ L2  │─▶│ L3  │─▶│ L4  │─▶│ L5  │─▶│ L6  │─▶│ L7  │─▶│ OUT │
 │Assem│  │Study│  │Scope│  │Stat │  │Scale│  │GRADE│  │Temprl│  │Fresh│  │Assem│
 │bly  │  │Desgn│  │Match│  │Heter│  │Valid│  │Qual │  │Decay │  │ness │  │bly  │
 └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
   │         │         │         │         │         │         │         │         │
   ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
 Layer    SE×1.0    SE÷w_scope  +τ²?     SE×m_sc   SE×m_G   SE÷w(t)  SE÷w_fr  SE_eff
 Input    –6.0×     (÷0.3)               1.0–1.5  1.0–2.0           ÷0.70    FINAL
 Pkg                max 3.3×                                  >90d
                                                              EXCL

 All 7 layers are MULTIPLICATIVE adjustments to SE.
 Final: SE_eff = √[(SE·m_claim·m_GRADE·m_temporal)² + σ²_struct + τ²·𝟙] / (max(w_scope,0.3)·w_fresh)

3. INTERMEDIATE STATE SCHEMAS (TYPE 2 — in-memory)

   ### State: LayerInputPackage (after IN, per evidence record)
   | Field | Type | Source | Description |
   |-------|------|--------|-------------|
   | ler_id | str | edge_evidence_v1 | Literature evidence record ID |
   | edge_id | str | edge_evidence_v1 | Target edge |
   | β_raw | float | EX-TB | Raw effect estimate (SD_SD scale) |
   | SE_raw | float | EX-TB | Raw standard error |
   | study_design | ENUM | EX-P1-AG2 | RCT/cohort/cross-sectional/animal/expert |
   | sample_size | int | EX-P1-AG3 | Study N |
   | cancer_type | str | EX-P1-AG3 | Cancer type for scope matching |
   | treatment_phase | str | EX-P1-AG3 | Active/post-treatment/survivorship |
   | instrument_id | str | EX-P1-AG4 | Instrument used |
   | instrument_validation | ENUM | instruments_v1 | cancer_validated/used/general/confounded |
   | grade_level | ENUM | EX-P1 | High/Moderate/Low/Very_Low |
   | measurement_date | date | EX-P1-AG8 | When outcome measured |
   | publication_year | int | EX-P1-AG1 | For freshness computation |
   | w_scope | float | EX-P2-S6 | Transportability weight (5 dims) |
   | attenuation_factor | float | EX-P2-S5 | Identification discount |

   ### State: LayerOutputPackage (after OUT, per evidence record)
   | Field | Type | Description |
   |-------|------|-------------|
   | SE_eff | float | Final calibrated SE |
   | m_design | float | L1 multiplier applied |
   | w_scope_applied | float | L2 scope weight used |
   | tau_sq | float | L3 between-study variance (0 if I²<50%) |
   | m_scale | float | L4 multiplier |
   | m_grade | float | L5 multiplier |
   | w_temporal | float | L6 decay weight (0 if >90d → EXCLUDED) |
   | w_fresh | float | L7 freshness weight |
   | excluded | bool | True if record excluded at any layer |
   | exclusion_reason | str? | Which layer excluded and why |

4. SUBSYSTEM INVENTORY
   | Order | ID | Name | Input | Output | Key Formula |
   |-------|----|------|-------|--------|-------------|
   | 0 | P3-IN | Input Assembly | HarmonizedClaims | LayerInputPackage | — |
   | 1 | P3-L1 | Study Design | LayerInputPackage | + m_design | P3-1 |
   | 2 | P3-L2 | Scope Match | + m_design | + w_scope | P3-2 |
   | 3 | P3-L3 | Stat. Heterogeneity | + w_scope | + τ² | P3-3 |
   | 4 | P3-L4 | Scale Validation | + τ² | + m_scale | P3-4 |
   | 5 | P3-L5 | GRADE Quality | + m_scale | + m_grade | P3-5 |
   | 6 | P3-L6 | Temporal Decay | + m_grade | + w_temporal | P3-6 |
   | 7 | P3-L7 | Freshness | + w_temporal | + w_fresh | P3-7 |
   | 8 | P3-OUT | SE_eff Assembly | All multipliers | SE_eff | P3-8 |

5. SUBSYSTEM DETAIL (7 layers)

## L1 — Study Design Adjustment
   Purpose: Apply SE multiplier based on study design quality tier
   Paper §: §2.9 Layer 1
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L1 — Study Design SE Multiplier                │
   │ Input:  LayerInputPackage.study_design, sample_size          │
   │ Output: m_design (float, applied multiplicatively to SE)     │
   │ Logic:                                                       │
   │   MATCH study_design:                                        │
   │     Large RCT (N>200):              m = 1.0                  │
   │     Small RCT (N≤200):              m = 1.0 + 0.5×(200−N)/200│
   │                                     (linear interpolation)   │
   │     Well-adjusted cohort:           m = 1.5                  │
   │     Unadjusted longitudinal:        m = 2.0                  │
   │     Cross-sectional (adjusted):     m = 2.5                  │
   │     Cross-sectional (unadjusted):   m = 3.0                  │
   │     Animal in vivo:                 m = 4.0                  │
   │     In vitro / mechanistic:         m = 5.0                  │
   │     Expert opinion / narrative:     m = 6.0                  │
   │ Calibration source: Anglemyer (2014) ROR=1.08 obs vs RCT;   │
   │   van Zwet, Schwab & Senn (2021) 13% median power           │
   │ Status: AUTHOR-CONSTRUCTED (no standard mapping exists)      │
   │ Rules: If design unclassified → default 3.0× + WARN flag    │
   │        Precision caps also applied here:                     │
   │          Cross-sectional: SE ≥ 30% of best RCT for same edge│
   │          Animal: SE ≥ 10% of best human RCT for same edge   │
   └─────────────────────────────────────────────────────────────┘

## L2 — Transportability/Scope Match
   Purpose: Adjust SE by population transportability (5-dimension weighted match)
   Paper §: §2.9 Layer 2
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L2 — Scope Weight Application                  │
   │ Input:  LayerInputPackage.w_scope (from EX-P2-S6)           │
   │ Output: SE_L2 = SE_L1 / max(w_scope, 0.3)                  │
   │ Logic:                                                       │
   │   w_scope already computed in EX-P2-S6 as:                  │
   │     w_scope = Σ_d (weight_d × match_d)                      │
   │   5 dimensions with weights:                                 │
   │     cancer_type:      0.35 (dominant — breast ≠ glioma)     │
   │     treatment_phase:  0.25 (active ≠ survivorship)          │
   │     regimen:          0.20 (anthracycline ≠ hormonal)       │
   │     age:              0.10 (pediatric ≠ elderly)            │
   │     sex:              0.10 (minor effect on CRCI)           │
   │   match_d scoring (per dimension):                           │
   │     exact match → 1.0; same category → 0.7;                 │
   │     related → 0.4; unrelated → 0.1                          │
   │ Floor: max(w_scope, 0.3)                                    │
   │   Rationale: without floor, w_scope→0 causes SE→∞           │
   │   Max SE inflation from scope: 1/0.3 = 3.33×               │
   │ Example: Breast cancer study applied to colorectal patient:  │
   │   cancer_type: 0.35×0.4=0.14, phase: 0.25×1.0=0.25,       │
   │   regimen: 0.20×0.1=0.02, age: 0.10×0.7=0.07, sex: same   │
   │   w_scope = 0.14+0.25+0.02+0.07+0.10 = 0.58               │
   │   SE_L2 = SE_L1 / 0.58 = 1.72× inflation                  │
   └─────────────────────────────────────────────────────────────┘

## L3 — Statistical Heterogeneity
   Purpose: Add between-study variance (τ²) when evidence is heterogeneous
   Paper §: §2.9 Layer 3
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L3 — Heterogeneity Assessment                  │
   │ Input:  All records for same edge (β_i, SE_i), k count      │
   │ Output: τ² (between-study variance), I² (inconsistency)     │
   │ Logic:                                                       │
   │   IF k < 2: τ² = 0, I² = 0 (cannot estimate)               │
   │   ELSE:                                                      │
   │     Q = Σ w_i(β_i − β̂_IVW)²  (Cochran's Q)               │
   │     τ² = max(0, (Q − (k−1)) / (Σw − Σw²/Σw))  (DL est.)  │
   │     I² = max(0, (Q − (k−1)) / Q) × 100%                   │
   │   Application:                                               │
   │     I² < 50%:  Fixed-effects (no τ² added)                  │
   │     I² ≥ 50%:  Random-effects (τ² added to each SE²_i)     │
   │ Double-counting guard: τ² added ONLY when 𝟙[not_in_base]   │
   │   (some edges already use random-effects from meta-analysis) │
   │ NOTE: This layer operates per-EDGE (not per-record),        │
   │   using all k records for that edge together.                │
   │ Rules: If I² ≥ 75% AND k ≥ 5, also flag for stratification │
   │   (pass to ALG-B1b stratified aggregation branch)            │
   └─────────────────────────────────────────────────────────────┘

## L4 — Scale/Cancer Validation
   Purpose: Adjust SE by instrument validation status in cancer populations
   Paper §: §2.9 Layer 4
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L4 — Scale Compatibility Assessment             │
   │ Input:  LayerInputPackage.instrument_id, instrument_validation│
   │ Output: m_scale (SE multiplier), or EXCLUDE                  │
   │ Logic:                                                       │
   │   MATCH instrument_validation (from instruments_v1):         │
   │     VALIDATED_CANCER:  m = 1.00 (e.g., FACT-Cog)            │
   │     USED_IN_CANCER:    m = 1.15 (used but not revalidated)  │
   │     GENERAL_POP_ONLY:  m = 1.30 (e.g., general MoCA norms) │
   │     CONFOUNDED:        m = 1.50 (known confounders present) │
   │     EXCLUDED:          record REMOVED from pool              │
   │ Scale conversions (when needed):                             │
   │   OR→SMD: d = ln(OR)·√3/π (Chinn 2000)                     │
   │   HR→OR: OR ≈ HR for rare outcomes                          │
   │   r→d: d = 2r/√(1−r²)                                      │
   │   Each conversion adds SE via delta method propagation       │
   │ Rules: Conversion adds 10% SE per step (cumulative)         │
   │ Gate: If instrument_id not in instruments_v1 → WARN + m=1.50│
   └─────────────────────────────────────────────────────────────┘

## L5 — GRADE Quality Assessment
   Purpose: Inflate SE based on evidence quality per GRADE framework
   Paper §: §2.9 Layer 5
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L5 — Quality-Based SE Inflation                 │
   │ Input:  LayerInputPackage.grade_level                        │
   │ Output: m_grade (SE multiplier)                              │
   │ Logic:                                                       │
   │   MATCH grade_level:                                         │
   │     HIGH:      m = 1.00 (confident in estimate)              │
   │     MODERATE:  m = 1.25 (moderate confidence)                │
   │     LOW:       m = 1.50 (limited confidence)                 │
   │     VERY_LOW:  m = 2.00 (very uncertain)                    │
   │ Status: AUTHOR-CONSTRUCTED operationalization                │
   │   The GRADE framework explicitly rejects quantification of   │
   │   uncertainty; these multipliers are NOVEL to this framework │
   │   and represent the author's mapping of qualitative grades   │
   │   to SE inflation factors.                                   │
   │ Determination: grade_level assigned in EX-P1 based on:       │
   │   study design (starting level), risk of bias (−1/−2),      │
   │   inconsistency (−1), indirectness (−1), imprecision (−1),  │
   │   publication bias (−1), large effect (+1/+2),              │
   │   dose-response (+1), confounding direction (+1)             │
   └─────────────────────────────────────────────────────────────┘

## L6 — Temporal Decay
   Purpose: Downweight evidence based on time since measurement
   Paper §: §2.9 Layer 6
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L6 — Measurement Recency Weight                 │
   │ Input:  LayerInputPackage.measurement_date, reference_date   │
   │ Output: w_temporal (weight ∈ [0, 1]), or EXCLUDE             │
   │ Formula: w(t) = e^{−0.05t}   where t = days since measure   │
   │ Pre-computed values:                                         │
   │   Same day:   w = 1.000                                     │
   │   1 week:     w = 0.705                                     │
   │   2 weeks:    w = 0.497                                     │
   │   1 month:    w = 0.223                                     │
   │   2 months:   w = 0.050                                     │
   │   3 months:   w = 0.011                                     │
   │   >90 days:   EXCLUDED (w → 0, record removed from pool)    │
   │ Rationale: Biomarker values change substantially over weeks; │
   │   3-month-old IL-6 measurement has minimal predictive value  │
   │   for current state.                                         │
   │ Application: SE_L6 = SE_L5 / max(w_temporal, 0.01)          │
   │   (0.01 floor prevents division by near-zero)               │
   │ Rules: Chronic trait measures (e.g., education, genetics)    │
   │   exempt — w_temporal = 1.0 always. Flag: is_trait in       │
   │   instruments_v1.                                            │
   │ NOTE: This is MEASUREMENT recency, not publication recency   │
   │   (which is L7). A 2024 paper measuring IL-6 in 2022 gets   │
   │   L6 penalty for 2-year-old measurement + L7 discount for    │
   │   recent publication.                                        │
   └─────────────────────────────────────────────────────────────┘

## L7 — Freshness Decay
   Purpose: Downweight evidence based on publication year (knowledge decay)
   Paper §: §2.9 Layer 7
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-L7 — Publication Freshness Weight               │
   │ Input:  LayerInputPackage.publication_year                   │
   │ Output: w_fresh (weight ∈ [0.70, 1.0])                      │
   │ Formula: w_fresh = max(0.70, 1 − 0.015 × (2025 − pub_year))│
   │ Pre-computed values:                                         │
   │   2025: w = 1.000  2020: w = 0.925  2015: w = 0.850       │
   │   2010: w = 0.775  2005: w = 0.700  ≤2005: w = 0.700      │
   │ Calibration: Poynard et al. (2002) — hepatology review found│
   │   45-year half-life for medical knowledge validity.          │
   │   ln(2)/45 ≈ 1.54%/year ≈ 0.015/year                       │
   │ Floor: 0.70 — older studies still contribute substantially   │
   │   (landmark papers from 1990s remain relevant)               │
   │ Application: SE_L7 = SE_L6 / w_fresh                        │
   │ Rules: No publication date → default w_fresh = 0.85 + WARN  │
   └─────────────────────────────────────────────────────────────┘

## OUT — Final SE_eff Assembly
   Purpose: Compose all 7 layer outputs into final calibrated SE_eff
   Paper §: §2.9
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P3-OUT — SE_eff Composition                        │
   │ Input:  All layer multipliers/weights per record             │
   │ Output: SE_eff (final calibrated standard error)             │
   │ Formula (P3-8):                                              │
   │   SE_eff = √[(SE_pooled · m_claim · m_GRADE · m_temporal)²  │
   │              + σ²_struct + τ² · 𝟙[random_effects]]         │
   │            / (max(w_scope, 0.3) · w_fresh)                  │
   │                                                              │
   │   where: σ²_struct = 0.25 (structural variance, constant)   │
   │          𝟙 = 1 if I²≥50%, 0 otherwise (from L3)            │
   │                                                              │
   │ Validation gate (P3-G1): SE_eff ≥ SE_raw                   │
   │   Calibration ONLY INFLATES uncertainty — never deflates.    │
   │   If SE_eff < SE_raw → ERROR (layer computation bug)        │
   │                                                              │
   │ WORKED EXAMPLE:                                              │
   │ Input: β=0.35, SE=0.12, Large RCT, cancer-validated,       │
   │   GRADE High, measured 10 days ago, published 2023,          │
   │   w_scope=0.80, k=3 for this edge, I²=30%                  │
   │                                                              │
   │   L1: m_design = 1.0 (Large RCT)                            │
   │   L2: SE/0.80 = 0.150  (scope inflation)                   │
   │   L3: I²<50% → τ²=0, no random-effects addition            │
   │   L4: m_scale = 1.0 (cancer-validated)                      │
   │   L5: m_grade = 1.0 (GRADE High)                            │
   │   L6: w(10) = e^{−0.5} = 0.607, SE/0.607 = 0.247          │
   │   L7: w_fresh = 1−0.015×2 = 0.97, SE/0.97 = 0.255         │
   │   Composition:                                               │
   │     numerator² = (0.12×1.0×1.0×1.0)² + 0.25 + 0 = 0.2644  │
   │     SE_eff = √0.2644 / (0.80 × 0.97) = 0.514/0.776 = 0.66│
   │   Result: SE inflated from 0.12 → 0.66 (5.5× total)        │
   │   Dominant contributor: σ²_struct (0.25) dominates the sum   │
   │                                                              │
   │ Write: edge_evidence_v1 updated with:                        │
   │   SE_eff, m_design, w_scope_applied, tau_sq, m_scale,       │
   │   m_grade, w_temporal, w_fresh, excluded, exclusion_reason   │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: edge_evidence_v1 (records to calibrate)
   WRITES: edge_evidence_v1 (SE_eff, layer multipliers per record)

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P3-G1 | SE_eff > SE_raw (calibration only inflates) | → P4 | ERROR: deflation |
   | P3-G2 | No record excluded by all 7 layers | Log exclusion | Exclusion logged |

6. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | P3-1 | m_design: Large RCT 1.0×, Small RCT 1.0-1.5×, Cohort 1.5-2.0×, Cross-sect 3.0×, Animal 4-5×, Expert 6.0× | §2.9 L1 |
   | P3-2 | w_scope = Σ(w_d·match_d); dims: cancer(0.35), phase(0.25), regimen(0.20), age(0.10), sex(0.10); floor 0.3 | §2.9 L2 |
   | P3-3 | I² = (Q−(k−1))/Q; Q = Σ w_i(β_i−β̂)²; if I²>50% add τ² | §2.9 L3 |
   | P3-4 | m_scale: cancer-validated 1.0×, used 1.15×, general 1.30×, confounded 1.50× | §2.9 L4 |
   | P3-5 | m_GRADE: High 1.0×, Moderate 1.25×, Low 1.50×, Very Low 2.00× | §2.9 L5 |
   | P3-6 | w(t) = e^{−0.05t}; half-life 14d; >90d EXCLUDED | §2.9 L6 |
   | P3-7 | w_fresh = max(0.70, 1−0.015×(2025−pub_year)); floor 0.70 | §2.9 L7 |
   | P3-8 | SE_eff = √[(SE·m_claim·m_GRADE·m_temporal)²+σ²_struct+τ²·𝟙]/(max(w_scope,0.3)·w_fresh) | §2.9 |

7. ASSUMPTIONS
   | # | Assumption | Impact | Paper § |
   |---|-----------|--------|---------|
   | P3-A1 | 7 layers multiplicative (order-independent) | High — interaction effects ignored | §2.9 |
   | P3-A2 | σ²_struct = 0.25 constant across all edges | Moderate — may vary by domain | §2.9 |
   | P3-A3 | Temporal decay 0.05/day uniform across biomarker types | Moderate | §2.9 |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P4 (Aggregation & Edge Update)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P4
   Name:           Aggregation / Edge Compilation (v2 — with DCR + Annotation Consumption)
   Purpose:        Pool calibrated evidence records per edge using IVW or random-effects,
                   with dual-metric double-counting resolution (DCR) and annotation-informed
                   structural variance. Write updated β̂, SE_eff, sigma_sq_structural to edges_v1.
   Phase:          Build-time (per-edge, after all papers processed)
   Paper §:        §2.9 (pooling), §2.10 (prior selection), §2.12 (P_inclusion)
   Subsystems:     5 (was 4: +DCR between grouping and meta-analysis)
   Formulas:       6 (IVW, I², P_inclusion, DCR-1 count overlap, DCR-2 N-weighted overlap, σ²_struct)
   Amends:         Original EX-P4 (adds DCR step, annotation consumption)

NOTE: This chain BRIDGES EX and ALG. The output (edges_v1) is the primary
input to ALG-B. The aggregation logic here mirrors ALG-B1/B2/B3/B4 but
operates at the extraction level (per-record pooling before ALG consumes).

2. CHAIN DIAGRAM

 CalibratedRecords (from EX-P3) + study_annotations_v1 (structural_variance, null_finding)
   │
   ▼
 ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
 │  P4-EG    │────▶│  P4-DCR   │────▶│  P4-MA    │────▶│  P4-PS    │────▶│  P4-WR    │
 │  Evidence  │     │  Double-  │     │  Meta-    │     │  Prior    │     │  Compiler │
 │  Grouper   │     │  Counting │     │  Analysis  │     │  Selection│     │  Writer   │
 │            │     │  Resolver │     │  + annot. │     │           │     │           │
 └───────────┘     └───────────┘     └───────────┘     └───────────┘     └───────────┘
  GroupedEvidence    ResolvedEvidence   PooledEstimate    PriorAugmented    CompiledEdge
                     + OverlapDecision  + σ²_struct

3. INTERMEDIATE STATE SCHEMAS

   ### State: GroupedEvidence (after EG, per edge)
   | Field | Type | Description |
   |-------|------|-------------|
   | edge_id | str | Target edge ID |
   | primary_rows | EvidenceRow[] | meta_source_flag = NULL |
   | ma_rows | EvidenceRow[] | meta_source_flag ≠ NULL |
   | k_total | int | Total evidence records |

   ### State: OverlapDecision (NEW — produced by DCR)
   | Field | Type | Description |
   |-------|------|-------------|
   | edge_relation_id | TEXT | Which edge |
   | count_overlap | float [0-1] | |constituents ∩ MA_included| / |S_MA| |
   | n_weighted_overlap | float [0-1] | Σ N_i(overlapping) / Σ N_i(all MA) |
   | decision | ENUM | USE_MA_POOLED / USE_PRIMARIES / USE_MA_EXCLUDE_OVERLAPPING / AMBIGUOUS |
   | excluded_row_ids | TEXT[] | LER IDs set to active=0 |
   | audit_reason | TEXT | Human-readable decision explanation |

   ### State: PooledEstimate (updated — annotation-informed)
   | Field | Type | Description |
   |-------|------|-------------|
   | β̂_pooled | float | IVW or random-effects pooled estimate |
   | SE_pooled | float | Pooled standard error |
   | method | ENUM | IVW_FIXED / IVW_RANDOM / DIRECT / BLOCKED / STRATIFIED / SINGLE_BEST |
   | I² | float | Heterogeneity inconsistency |
   | τ² | float | Between-study variance |
   | sigma_sq_structural | float | Annotation-informed per-edge (default 0.25) (NEW) |
   | p_inclusion_adjustment | float | Logit-scale adjustment from null_finding (NEW) |
   | annotation_source_ids | UUID[] | Which annotations contributed (NEW) |

   ### State: PrioredEdge (after PS, per edge — unchanged)
   | Field | Type | Description |
   |-------|------|-------------|
   | prior_type | ENUM | RobustMAP / Commensurate / Power / MechanisticSynthesis / Placeholder |
   | prior_parameters | dict | μ_0, σ_0, discount (type-specific) |

4. SUBSYSTEM INVENTORY

   | Order | ID | Name | Input | Output | Key Formula | Status |
   |-------|----|------|-------|--------|-------------|--------|
   | 1 | P4-EG | EvidenceGrouper | CalibratedRecords | GroupedEvidence | — | Renamed (was S1a) |
   | 2 | P4-DCR | DoubleCountingResolver | GroupedEvidence + MA lists | ResolvedEvidence + OverlapDecision | DCR-1, DCR-2 | NEW |
   | 3 | P4-MA | MetaAnalyzer | ResolvedEvidence + annotations | PooledEstimate + σ²_struct | P4-1, P4-2 | Updated |
   | 4 | P4-PS | PriorSelector | PooledEstimate | PrioredEdge | Decision tree | Renamed (was S2) |
   | 5 | P4-WR | CompilerWriter | PrioredEdge + OverlapDecision | CompiledEdge → edges_v1 | — | Renamed (was S4) |

5. SUBSYSTEM DETAIL

## P4-EG — Evidence Grouper (renamed from P4-S1a)
   Purpose: Group calibrated records by edge_id, partition primary vs MA
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P4-EG — Group + Partition                          │
   │ Input:  edge_evidence_v1 (calibrated records from P3)        │
   │ Output: GroupedEvidence per edge                              │
   │ Logic:  Filter by target_edge_id, exclude records with       │
   │         excluded=true (from P3 layers)                       │
   │   Partition: primary (meta_source_flag NULL) vs MA rows      │
   │   Apply diminishing returns: w_base × 1/(1+0.3·ln(k))      │
   │   Precision caps: cross-sect ≥30% best RCT, animal ≥10%    │
   └─────────────────────────────────────────────────────────────┘

## P4-DCR — Double-Counting Resolver (NEW)
   Purpose: Prevent double-counting when both MA pooled estimates and their
     constituent primary studies exist in edge_evidence_v1
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P4-DCR — Dual-Metric Overlap Analysis              │
   │ Input:  GroupedEvidence (primary + MA rows)                   │
   │         edge_evidence_v1.included_study_ids (MA constituents) │
   │         study_registry_v1.total_n (for N-weighting)          │
   │ Output: OverlapDecision + ResolvedEvidence                   │
   │                                                              │
   │ Step 1: Compute count_overlap (DCR-1):                       │
   │   count_overlap = |S_registry ∩ S_MA| / |S_MA|              │
   │                                                              │
   │ Step 2: Compute n_weighted_overlap (DCR-2):                  │
   │   n_weighted = Σ N_i(overlapping) / Σ N_i(all MA included)  │
   │                                                              │
   │ Step 3: Decision rule (BOTH metrics must agree):             │
   │   Both < 0.10       → USE_MA_POOLED (minimal overlap)       │
   │   Either > 0.70     → USE_PRIMARIES (exclude MA row)        │
   │   Disagree > 0.30   → AMBIGUOUS (→ human review via P4-G3)  │
   │   Otherwise          → USE_MA_EXCLUDE_OVERLAPPING            │
   │                                                              │
   │ Step 4: Mark excluded rows active=0 with exclusion_reason    │
   │ Edge case: No MA rows present → decision = N/A, pass through │
   └─────────────────────────────────────────────────────────────┘

## P4-MA — MetaAnalyzer (updated — now consumes annotations)
   Purpose: Pool evidence using IVW/random-effects + annotation-informed σ²
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P4-MA-a — Aggregation Decision Tree (UNCHANGED)    │
   │   k=0 → BLOCKED; k=1 → DIRECT; k≥2:                        │
   │     I²<50% → IVW_FIXED; 50-75% → STRATIFIED or IVW_RANDOM  │
   │     ≥75% → STRATIFIED or SINGLE_BEST                        │
   │   Sign conflict among HIGH-quality → BLOCKED                 │
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: P4-MA-b — IVW Computation (UNCHANGED)              │
   │   Fixed: β̂ = Σ(β_i/SE²_i) / Σ(1/SE²_i)     (P4-1)       │
   │   Random: β̂ = Σ(β_i/(SE²_i+τ²)) / Σ(1/(SE²_i+τ²)) (P4-2)│
   ├─────────────────────────────────────────────────────────────┤
   │ SUB-STEP: P4-MA-c — Annotation Consumption (NEW)             │
   │                                                              │
   │ σ²_structural (per-edge, default 0.25):                      │
   │   READ: study_annotations_v1 WHERE category =               │
   │     'limitation_unmeasured_confounder' AND target = this edge│
   │   For each annotation:                                       │
   │     σ²_adj += severity_weight × reconciled_confidence        │
   │     severity_weight: moderate=0.05, high=0.10, critical=0.15│
   │   σ²_structural = 0.25 + Σ σ²_adj                          │
   │   CEILING: σ²_structural ≤ 0.50                             │
   │                                                              │
   │ p_inclusion_adjustment (logit-scale):                        │
   │   READ: study_annotations_v1 WHERE category =               │
   │     'null_finding_context' AND target = this edge            │
   │   For each: IF powered_adequately=true → adj += −0.3        │
   │   p_inclusion_adjustment = clamp(Σ adj, −1.0, +1.0)        │
   │   P_final = logistic(logit(P_formula) + adjustment) (P4-3b) │
   │                                                              │
   │ *** CONFLICT 1 RESOLUTION: σ²_struct is now VARIABLE.       │
   │     ALG-B2 reads edges_v1.sigma_sq_structural.              │
   │     Default 0.25 if NULL → backward compatible.             │
   │ *** CONFLICT 2 RESOLUTION: P_inclusion adjustment is        │
   │     ADDITIVE on logit scale, capped ±1.0.                   │
   └─────────────────────────────────────────────────────────────┘

## P4-PS — Prior Selection (renamed from S2, UNCHANGED logic)
   Purpose: Assign prior distribution type per edge
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P4-PS — Prior Decision Tree                        │
   │   k ≥ 5, ≥2 RCTs → RobustMAP                               │
   │   k = 2–4 → Commensurate (power-discounted)                │
   │   k = 1 → Power                                             │
   │   k = 0 + chain evidence → MechanisticSynthesis             │
   │   k = 0, no chain → Placeholder N(0, 1)                    │
   │ 4-level fallback: exact→cancer-type→general→uninformative   │
   │ Writes: prior_selection_log_v1                               │
   └─────────────────────────────────────────────────────────────┘

## P4-WR — Compiler Writer (renamed from S4, UPDATED output)
   Purpose: Write final compiled parameters for all 118 edges
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P4-WR — Edge Table Update (v2)                     │
   │ For each of 118 edges, write to edges_v1:                    │
   │   β̂, SE_eff, P_inclusion, prior_type, k,                   │
   │   aggregation_method, contributing_ler_ids, publication_bias │
   │   sigma_sq_structural (per-edge, default 0.25)          NEW │
   │   overlap_decision (from P4-DCR, nullable)              NEW │
   │   deployment_ready: false (set true by EX-P6)               │
   │ Also write: edge_param_builds_v1 (audit trail               │
   │   + overlap_decision_json + annotation_source_ids_json) NEW │
   │   aggregation_log_v1 (method, k, I², τ², weights)           │
   └─────────────────────────────────────────────────────────────┘

6. BOUNDARY TABLES
   READS: edge_evidence_v1 (calibrated records), context_matched_priors_v1
   READS: study_annotations_v1 (limitation_unmeasured_confounder, null_finding_context) NEW
   READS: study_registry_v1 (total_n for DCR N-weighting) NEW
   WRITES: edges_v1 (118 rows: +sigma_sq_structural, +overlap_decision)
   WRITES: prior_selection_log_v1, aggregation_log_v1, edge_param_builds_v1

7. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P4-G1 | All 118 edges have method assigned | → P4-WR | ABORT: incomplete |
   | P4-G2 | No NaN in β̂ or SE | → write | ERROR: computation |
   | P4-G3 | DCR decision ≠ AMBIGUOUS | Continue | → human review (NEW) |
   | P4-G4 | Annotation σ² ≤ 0.50 (2× generic) | Accept | → review (NEW) |

8. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | P4-1 | β̂_IVW = Σ w_i·β_i / Σ w_i, w_i = 1/SE²_i | §2.9 |
   | P4-2 | β̂_RE: w*_i = 1/(SE²_i + τ²) (DerSimonian-Laird) | §2.9 |
   | P4-3 | P_incl = logistic(−0.5 + 1.2·ln(k+1) + 0.4Z + 0.6·𝟙_RCT) | §2.12 |
   | P4-3b | P_final = logistic(logit(P_formula) + p_inclusion_adjustment) | §2.12 v2 NEW |
   | DCR-1 | count_overlap = |S_registry ∩ S_MA| / |S_MA| | §2.12.1 NEW |
   | DCR-2 | n_weighted_overlap = Σ N_i(overlap) / Σ N_i(all MA) | §2.12.1 NEW |

9. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | P4-A1 | DL random-effects appropriate for heterogeneous CRCI evidence | High |
   | P4-A2 | Literary priors informative but not dominant | Medium |
   | P4-A3 | Dual-metric overlap correctly identifies double-counting | Medium — P4-G3 AMBIGUOUS → human review | NEW |
   | P4-A4 | Confounder annotations accurately reflect structural bias | Medium — ceiling 0.50 + P4-G4 | NEW |


═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P2E (Extended Extraction — Conditional)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P2E
   Name:           Extended Extraction
   Purpose:        Extract supplementary data types when flagged: cross-method
                   agreement (triangulation), biomarker-pathway loadings, and
                   ontology provenance links
   Phase:          Build-time (CONDITIONAL — only runs when paper flagged by EX-P1)
   Paper §:        §2.13 (triangulation), §2.3 (pathway loadings)
   Subsystems:     3 (TriangulationExtractor, PathwayLoadingExtractor, OntologyLinker)

2. CHAIN DIAGRAM

 Same paper text + prior_outputs from EX-P1
       │
       ├───▶ P2E-S1: TriangulationExtractor ───▶ triangulation_evidence_v1
       │     (when paper reports same edge via multiple methods)
       │
       ├───▶ P2E-S2: PathwayLoadingExtractor ──▶ pathway_biomarkers_v1
       │     (when paper reports biomarker → pathway loading factors)
       │
       └───▶ P2E-S3: OntologyLinker ───────────▶ ontology_links_v1
             (always: map concepts to MeSH/SNOMED/CRCI node IDs)

 Trigger: AG9 reconciliation flags OR DEEP execution mode

3. SUBSYSTEM DETAIL

## P2E-S1 — TriangulationExtractor
   Purpose: Extract cases where same paper measures same relationship via
            multiple methods (e.g., RCT + biomarker mediation + observational cohort)
   Input: prior_outputs (AG5 stats, AG2 design, AG7 mediators)
   Output: triangulation_evidence_v1 records
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic:                                                       │
   │ 1. Identify edges measured by 2+ methods in same paper       │
   │ 2. Record: edge_id, method_1, β_1, SE_1, method_2, β_2, SE_2│
   │ 3. Agreement score: |β_1 − β_2| / √(SE₁² + SE₂²)          │
   │ 4. Agreement < 1.5 → CONCORDANT (strengthens evidence)       │
   │    Agreement 1.5–3.0 → DISCORDANT_MILD                      │
   │    Agreement > 3.0 → DISCORDANT_SEVERE                       │
   │ Rules: Concordant triangulation → 0.8× SE reduction bonus   │
   │        Used in ALG-B chain-vs-direct validation               │
   └─────────────────────────────────────────────────────────────┘

## P2E-S2 — PathwayLoadingExtractor
   Purpose: Extract biomarker-to-pathway loading factors from mechanistic studies
   Input: prior_outputs (AG7 mediators, AG5 stats)
   Output: pathway_biomarkers_v1 (loading factors per biomarker × pathway)
   Logic: Extract factor loadings, mediation proportions, indirect effects
   Rules: Only for papers with formal mediation analysis or factor analysis

## P2E-S3 — OntologyLinker
   Purpose: Map all extracted concepts to standard ontologies + CRCI DAG nodes
   Input: All prior_outputs concepts
   Output: ontology_links_v1 (concept → MeSH/SNOMED/node_id mappings)
   Logic: Fuzzy match + manual review queue for ambiguous mappings

4. BOUNDARY TABLES
   READS: prior_outputs (in-memory from EX-P1)
   WRITES: triangulation_evidence_v1, pathway_biomarkers_v1, ontology_links_v1

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P4B (Publication Bias Assessment)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P4B
   Name:           Publication Bias Assessment
   Purpose:        Detect and quantify publication bias per edge using 4 methods:
                   Egger regression, trim-and-fill, leave-one-out, Copas selection
   Phase:          Build-time (per-edge, requires k ≥ 10 studies)
   Paper §:        §2.12.1
   Subsystems:     4 (Egger, TrimFill, LeaveOneOut, BiasAggregator)
   Formulas:       4

2. CHAIN DIAGRAM

 edges_v1 + edge_evidence_v1 (per edge, k ≥ 10)
       │
       ▼
 ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
 │ P4B-S1    │───▶│ P4B-S2    │───▶│ P4B-S3    │───▶│ P4B-S4    │
 │ Egger     │    │ Trim &    │    │ Leave-One │    │ Bias      │
 │ Regression│    │ Fill      │    │ Out       │    │ Aggregator│
 └───────────┘    └───────────┘    └───────────┘    └───────────┘
  p_egger          n_imputed        LOO_shift        final_bias_verdict

3. INTERMEDIATE STATE SCHEMAS

   ### State: BiasAssessment (accumulated across S1-S3, assembled in S4)
   | Field | Type | Description |
   |-------|------|-------------|
   | edge_id | str | Target edge |
   | k | int | Evidence count (must be ≥10) |
   | p_egger | float | Egger regression p-value |
   | egger_flag | bool | p < 0.10 → asymmetry detected |
   | n_imputed | int | Trim & Fill missing study count |
   | tf_shift | float | |β̂_adjusted − β̂_original| in SD |
   | tf_flag | ENUM(NONE/MODERATE/SEVERE) | shift thresholds |
   | loo_max_influence | float | Max single-study influence |
   | loo_range | float | Max − min of leave-one-out β̂ |
   | loo_flag | bool | influence > 2.0 or range > 0.3 |
   | bias_verdict | ENUM(CLEAN/POSSIBLE/PROBABLE/SEVERE) | Final |
   | se_inflation | float | 1.0/1.1/1.3/1.5 per verdict |

4. SUBSYSTEM INVENTORY
   | Order | ID | Name | Input | Output | Key Formula |
   |-------|----|------|-------|--------|-------------|
   | 1 | P4B-S1 | Egger Regression | {β_i, SE_i} per study | p_egger | P4B-1 |
   | 2 | P4B-S2 | Trim & Fill | {β_i, SE_i} per study | n_imputed, shift | P4B-2 |
   | 3 | P4B-S3 | Leave-One-Out | {β_i, SE_i} per study | influence per study | P4B-3 |
   | 4 | P4B-S4 | Bias Aggregator | All flags | bias_verdict + SE adj | P4B-4 |

5. SUBSYSTEM DETAIL

## P4B-S1 — Egger Regression
   Purpose: Test for funnel plot asymmetry via regression
   Input: β_i, SE_i per study for target edge
   Output: p_egger, intercept_egger
   ┌─────────────────────────────────────────────────────────────┐
   │ Formula: Regress β_i/SE_i on 1/SE_i                         │
   │ Test: H₀: intercept = 0 (no asymmetry)                      │
   │ p < 0.10 → significant asymmetry detected                   │
   │ Limitation: low power when k < 20                            │
   │ Rules: Only run when k ≥ 10; record p-value + confidence     │
   └─────────────────────────────────────────────────────────────┘

## P4B-S2 — Trim & Fill
   Purpose: Estimate number of missing studies and bias-adjusted β̂
   Input: β_i, SE_i per study
   Output: n_imputed (count of hypothetical missing studies), β̂_adjusted
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic: Iteratively:                                          │
   │   1. Compute pooled β̂                                       │
   │   2. Identify asymmetric studies (right-heavy or left-heavy) │
   │   3. "Trim" extreme studies, re-estimate β̂                  │
   │   4. "Fill" mirror studies to restore symmetry               │
   │   5. Report: n_imputed, β̂_original, β̂_adjusted, shift      │
   │ Rules: shift = |β̂_adjusted − β̂_original|                   │
   │   shift > 0.1 SD → MODERATE bias concern                    │
   │   shift > 0.3 SD → SEVERE bias concern                      │
   └─────────────────────────────────────────────────────────────┘

## P4B-S3 — Leave-One-Out Sensitivity
   Purpose: Check if any single study disproportionately drives the pooled estimate
   Input: β_i, SE_i per study
   Output: LOO_results (pooled β̂ with each study removed)
   ┌─────────────────────────────────────────────────────────────┐
   │ Logic: For each study j:                                     │
   │   β̂_{−j} = IVW pooled estimate excluding study j            │
   │   influence(j) = |β̂_{−j} − β̂_all| / SE_all                │
   │ Flag: influence > 2.0 → study j is INFLUENTIAL               │
   │       If influential study is also lowest quality → concern  │
   │ Rules: LOO range (max − min β̂_{−j}) reported                │
   │   LOO range > 0.3 SD → FRAGILE evidence base                │
   └─────────────────────────────────────────────────────────────┘

## P4B-S4 — Bias Aggregator
   Purpose: Synthesize all bias assessments into final verdict per edge
   Input: p_egger, n_imputed, LOO_results
   Output: BiasAssessment (verdict + recommended SE adjustment)
   ┌─────────────────────────────────────────────────────────────┐
   │ Decision matrix:                                             │
   │   All 3 methods → NO_CONCERN:    bias_verdict = CLEAN       │
   │   1 method flags concern:         bias_verdict = POSSIBLE    │
   │     → SE inflated 1.1×                                      │
   │   2 methods flag concern:         bias_verdict = PROBABLE    │
   │     → SE inflated 1.3×                                      │
   │   All 3 methods flag concern:     bias_verdict = SEVERE      │
   │     → SE inflated 1.5× + mandatory disclosure               │
   │                                                              │
   │ Write: publication_bias field in edges_v1                    │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: edges_v1, edge_evidence_v1
   WRITES: edges_v1 (publication_bias field, SE adjustment)

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P4B-G1 | k ≥ 10 for target edge | Run all 4 methods | SKIP: insufficient studies |
   | P4B-G2 | At least 2 methods converge | Apply adjustment | FLAG: methods disagree |

6. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | P4B-1 | Egger: regress β_i/SE_i on 1/SE_i; p<0.10 → asymmetry | §2.12.1 |
   | P4B-2 | Trim & Fill: n_imputed, β̂_adjusted; shift>0.1→MODERATE, >0.3→SEVERE | §2.12.1 |
   | P4B-3 | LOO: influence(j) = |β̂_{−j}−β̂_all|/SE; >2.0 → INFLUENTIAL | §2.12.1 |
   | P4B-4 | Verdict: 0 flags→CLEAN, 1→1.1×SE, 2→1.3×SE, 3→1.5×SE | §2.12.1 |

7. ASSUMPTIONS
   | # | Assumption | Impact | Paper § |
   |---|-----------|--------|---------|
   | P4B-A1 | k≥10 threshold for bias assessment (below → SKIP) | Moderate — biased edges with k<10 undetected | §2.12.1 |
   | P4B-A2 | Egger regression assumes linear relationship between effect and SE | Low — standard assumption | §2.12.1 |
   | P4B-A3 | Trim & Fill assumes funnel plot symmetric under no bias | Low — standard assumption | §2.12.1 |
   | P4B-A4 | Equal weighting of 3 bias methods in aggregator (majority vote) | Moderate — no method is gold standard | §2.12.1 |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P5 (Sufficiency & Coherence Check)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P5
   Name:           Sufficiency & Coherence Check
   Purpose:        (1) Assess evidence coverage across all 118 edges,
                   (2) compute chain-vs-direct pathway coherence,
                   (3) classify discrepancies into 6 failure modes,
                   (4) apply SE inflation feedback, (5) compute E-values,
                   (6) generate acquisition priorities, (7) produce report
   Phase:          Build-time (after all papers processed)
   Paper §:        §2.13 (chain-vs-direct), §2.13.2 (failure modes), §2.22 (gaps)
   Subsystems:     7

2. CHAIN DIAGRAM

 edges_v1 + pathway_map_v1 + edge_evidence_v1
       │
       ▼
 ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
 │ P5-S1 │─▶│ P5-S2 │─▶│ P5-S3 │─▶│ P5-S4 │─▶│ P5-S5 │─▶│ P5-S6 │─▶│ P5-S7 │
 │Coverag│  │Chain  │  │Chain  │  │Discrep│  │SE     │  │E-Value│  │Report │
 │Analyze│  │Product│  │vs Dir.│  │Classif│  │Feedbck│  │Compute│  │Generat│
 └───────┘  └───────┘  └───────┘  └───────┘  └───────┘  └───────┘  └───────┘

3. INTERMEDIATE STATE SCHEMAS

   ### State: CoverageMatrix (after S1)
   | Field | Type | Description |
   |-------|------|-------------|
   | edge_id | str | Each of 118 edges |
   | k | int | Evidence count |
   | SE_eff | float | Current calibrated SE |
   | best_design | ENUM | Best study design contributing |
   | coverage_tier | ENUM(STRONG/MODERATE/WEAK/GAP) | Tier classification |
   | domain | str | Clinical domain (of 11) |

   ### State: CDResults (after S3, per testable chain)
   | Field | Type | Description |
   |-------|------|-------------|
   | pathway_id | str | Pathway from pathway_map_v1 |
   | β_chain | float | Indirect (chain product) effect |
   | SE_chain | float | Propagated SE along chain |
   | β_direct | float | Direct measurement effect |
   | SE_direct | float | Direct measurement SE |
   | Z | float | Discrepancy Z-score |
   | classification | ENUM(PASS/MILD/MODERATE/SEVERE) | Z-tier |
   | failure_modes | list[ENUM] | FM1-FM6 assignments |

   ### State: SufficiencyReport (after S7)
   | Field | Type | Description |
   |-------|------|-------------|
   | coverage_pct | float | % of 118 edges with k≥1 |
   | gap_edges | list[edge_id] | k=0 edges |
   | discrepancy_summary | list[CDResults] | Z≥1.5 chains |
   | e_value_flags | list[{edge_id, E_value}] | Vulnerable edges |
   | top_10_gaps | list[{edge_id, discovery_score}] | Priorities |

4. SUBSYSTEM INVENTORY
   | Order | ID | Name | Input | Output | Key Formula |
   |-------|----|------|-------|--------|-------------|
   | 1 | P5-S1 | Coverage Analyzer | edges_v1 | CoverageMatrix | — |
   | 2 | P5-S2 | Chain Product | edges_v1 + pathway_map_v1 | β_chain | P5-1 |
   | 3 | P5-S3 | Chain-vs-Direct | β_chain + β_direct | CDResults | P5-2, P5-3 |
   | 4 | P5-S4 | Discrepancy Class. | CDResults (Z≥1.5) | + failure_modes | P5-5 |
   | 5 | P5-S5 | SE Inflation | failure_modes | edges_v1 updated | — |
   | 6 | P5-S6 | E-Value Computer | edges_v1 (obs.) | E-value/edge | P5-4 |
   | 7 | P5-S7 | Report Generator | All outputs | SufficiencyReport | — |

5. SUBSYSTEM DETAIL

## P5-S1 — Coverage Analyzer
   Purpose: Build 118-edge coverage matrix showing evidence depth per edge
   Output: CoverageMatrix (edge_id × {k, SE_eff, best_design, coverage_tier})
   ┌─────────────────────────────────────────────────────────────┐
   │ Coverage tiers:                                              │
   │   k ≥ 5, includes RCT → STRONG                              │
   │   k = 2–4 → MODERATE                                        │
   │   k = 1 → WEAK                                              │
   │   k = 0 → GAP (uses structural placeholder)                 │
   │ Current: 8 edgeless nodes (k=0), majority k=1-3             │
   │ Report: per-domain coverage heatmap                          │
   └─────────────────────────────────────────────────────────────┘

## P5-S2 — Chain Product Computer
   Purpose: Compute indirect (chain) β for testable pathways
   Paper §: §2.13
   Input: edges_v1 (β per edge), pathway_map_v1 (20 pathways)
   Output: β_chain per pathway = Π_e β_e (product along path)
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P5-S2 — Chain Effect Computation                   │
   │ For each of 20 pathways in pathway_map_v1:                   │
   │   1. Retrieve constituent edges (ordered)                    │
   │   2. Check: ALL edges must have k ≥ 1 (else SKIP pathway)  │
   │   3. β_chain = Π_{e ∈ path} β_e (product of edge effects)  │
   │   4. SE_chain propagation (delta method):                    │
   │      SE_chain = |β_chain| × √(Σ (SE_e / β_e)²)            │
   │      (relative errors add in quadrature)                     │
   │ Testable pathways: only those with BOTH:                     │
   │   - All constituent edges have k≥1 (chain computable)       │
   │   - A direct measurement exists for the endpoint            │
   │ Result: 10 of 20 pathways are testable (§2.13)              │
   │ Rules: β_e = 0 for any edge → β_chain = 0 (chain broken)   │
   │        Negative β_e handled via sign propagation             │
   └─────────────────────────────────────────────────────────────┘

## P5-S3 — Chain-vs-Direct Comparator
   Purpose: Compare β_chain (indirect) to β_direct (direct measurement) for
            pathways with direct evidence
   Input: β_chain (from S2), direct_effects from edge_evidence_v1
   Output: CDResults (Z-score, classification per pathway)
   ┌─────────────────────────────────────────────────────────────┐
   │ Formula:                                                     │
   │   Z = |β_chain − β_direct| / √(SE²_chain + SE²_direct)     │
   │ Classification (same as ALG-B6):                             │
   │   Z < 1.5 → PASS                                            │
   │   1.5–2.0 → MILD (1.2× SE inflation)                        │
   │   2.0–3.0 → MODERATE (1.5× SE inflation)                    │
   │   Z ≥ 3.0 → SEVERE (exclude or 2.0× SE)                    │
   │ 10 testable chains identified in §2.13                       │
   │                                                              │
   │ WORKED EXAMPLE (Neuroinflammation → Executive Function):     │
   │   Chain: TNF-α→BBB→Neuroinflammation→ExecFunction           │
   │   β_chain = 0.42×0.38×0.55 = 0.088                          │
   │   SE_chain = 0.088 × √((0.10/0.42)²+(0.12/0.38)²+(0.15/0.55)²)│
   │            = 0.088 × √(0.057+0.100+0.074) = 0.088×0.480    │
   │            = 0.042                                           │
   │   β_direct = 0.12 (from direct study of TNF-α→ExecFunc)    │
   │   SE_direct = 0.05                                           │
   │   Z = |0.088−0.12| / √(0.042²+0.05²) = 0.032/0.065 = 0.49│
   │   Classification: Z=0.49 < 1.5 → PASS ✓                   │
   └─────────────────────────────────────────────────────────────┘

## P5-S4 — Discrepancy Classification
   Purpose: Classify MILD+ discrepancies into 6 failure modes
   Input: CDResults where Z ≥ 1.5
   Output: ClassifiedDiscrepancies (failure_mode per discrepancy)
   ┌─────────────────────────────────────────────────────────────┐
   │ 6 failure modes (from §2.13.2):                              │
   │ FM1: Missing mediator (β_chain < β_direct)                  │
   │ FM2: Unmeasured confounding (β_chain > β_direct)            │
   │ FM3: Measurement artifact (instrument validity issue)        │
   │ FM4: Population heterogeneity (different study populations)  │
   │ FM5: Non-linearity (linear model assumption violated)        │
   │ FM6: Temporal mismatch (different follow-up periods)         │
   │                                                              │
   │ Assignment logic: heuristic based on edge characteristics,   │
   │ study design mix, and magnitude/direction of discrepancy     │
   │ Rules: Multiple failure modes can apply to same discrepancy  │
   └─────────────────────────────────────────────────────────────┘

## P5-S5 — SE Inflation Feedback
   Purpose: Apply SE inflation to edges involved in chain-vs-direct discrepancies
   Paper §: §2.13
   Input: ClassifiedDiscrepancies (from S4)
   Output: Updated edges_v1 with inflated SE_eff
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P5-S5 — Discrepancy-Based SE Inflation             │
   │ For each discrepant chain (Z ≥ 1.5):                        │
   │   Identify constituent edges in the chain                    │
   │   Apply inflation to ALL edges in the chain:                 │
   │     MILD (Z 1.5–2.0):     SE_eff *= 1.2                    │
   │     MODERATE (Z 2.0–3.0): SE_eff *= 1.5                    │
   │     SEVERE (Z ≥ 3.0):     SE_eff *= 2.0 OR exclude chain   │
   │       (exclude if failure_mode = FM2 unmeasured confounding) │
   │                                                              │
   │   If edge appears in MULTIPLE discrepant chains:             │
   │     Use the MAXIMUM inflation (don't multiply)               │
   │     Rationale: inflation reflects uncertainty about this     │
   │     edge's value, not cumulative penalty                     │
   │                                                              │
   │ Writes: edges_v1 (SE_eff updated for affected edges)        │
   │ Audit: chain_discrepancy_log_v1 (which edges inflated, by   │
   │   how much, from which chain discrepancy)                    │
   └─────────────────────────────────────────────────────────────┘

## P5-S6 — E-Value Computer
   Purpose: Compute E-values for unmeasured confounding robustness
   Input: edges_v1 (β, SE per edge)
   Output: E-values per edge (minimum confounding strength to nullify)
   ┌─────────────────────────────────────────────────────────────┐
   │ E-value = RR + √(RR × (RR − 1)) where RR = exp(β)         │
   │ Interpretation: E-value > 3.0 → robust to confounding       │
   │                 E-value 2.0–3.0 → moderately robust         │
   │                 E-value < 2.0 → vulnerable to confounding    │
   │ Rules: Only computed for observational/non-randomized edges  │
   │        RCT edges assumed confounding-free (E-value = ∞)      │
   └─────────────────────────────────────────────────────────────┘

## P5-S7 — Report Generator
   Purpose: Produce sufficiency report with acquisition priorities
   Paper §: §2.22
   Output: SufficiencyReport → acquisition_queue_v1
   ┌─────────────────────────────────────────────────────────────┐
   │ SUB-STEP: P5-S7 — Sufficiency Report Assembly                │
   │ Content produced:                                            │
   │                                                              │
   │ 1. Coverage heatmap (11 domains × {STRONG/MOD/WEAK/GAP})   │
   │    Visualization: 118 edges organized by domain, colored    │
   │                                                              │
   │ 2. Top 10 evidence gaps (sorted by discovery_score)          │
   │    discovery_score = |elasticity(e)| × SE_eff(e) (§2.22)   │
   │    High elasticity + high uncertainty → highest research ROI│
   │    Per gap: edge_id, discovery_score, recommended study      │
   │    design, estimated N, primary endpoint                     │
   │                                                              │
   │ 3. Discrepancy summary (from S3/S4)                          │
   │    Per discrepancy: chain, Z, classification, failure modes  │
   │    Highlight unresolved SEVERE cases                         │
   │                                                              │
   │ 4. E-value flag list (from S6)                               │
   │    Edges with E-value < 2.0 flagged as confounding-vulnerable│
   │    Per flag: edge_id, E_value, β, study designs contributing │
   │                                                              │
   │ 5. Recommended next papers to seek                           │
   │    Based on gap analysis: which specific studies would        │
   │    maximally reduce model uncertainty (EVSI-informed)        │
   │    Prioritized by: gap severity × edge importance × EVSI    │
   │                                                              │
   │ Writes: acquisition_queue_v1 (top 20 gaps with priorities)  │
   │         evidence_gaps_v1 (full gap analysis for PRES-SCI5)  │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: edges_v1, edge_evidence_v1, pathway_map_v1
   WRITES: edges_v1 (SE inflation), acquisition_queue_v1

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P5-G1 | Coverage >50% of edges have k≥1 | → P5-S2 | WARN: sparse evidence |
   | P5-G2 | No SEVERE discrepancies unresolved | → EX-P6 | BLOCK: resolve first |

6. FORMULA REGISTRY
   | ID | Equation | Paper § |
   |----|----------|---------|
   | P5-1 | β_chain = Π_e β_e (product along pathway) | §2.13 |
   | P5-2 | Z = |β_chain−β_direct|/√(SE²_chain+SE²_direct) | §2.13 |
   | P5-3 | Z<1.5→PASS, 1.5-2.0→MILD(1.2×SE), 2.0-3.0→MODERATE(1.5×SE), ≥3.0→SEVERE | §2.13 |
   | P5-4 | E-value = RR + √(RR×(RR−1)); RR=exp(β) | §2.22 |
   | P5-5 | 6 failure modes: FM1-FM6 (§2.13.2) | §2.13.2 |

7. ASSUMPTIONS
   | # | Assumption | Impact | Paper § |
   |---|-----------|--------|---------|
   | P5-A1 | Chain product valid for indirect effects (linear composition) | High | §2.13 |
   | P5-A2 | 10 testable chains cover critical pathways | Moderate | §2.13 |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-P6 (Deployment Validation)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-P6
   Name:           Deployment Validation
   Purpose:        Final gate before compiled parameters deploy to SYS_ALGORITHM —
                   runs all validation rules (G1–G16+) across the complete
                   knowledge + evidence + compiled table set
   Phase:          Build-time (after EX-P5, before ALG consumes edges_v1)
   Paper §:        §2.22 (implied — quality assurance)
   Subsystems:     2 (ValidationRunner, DeployGate)

2. CHAIN DIAGRAM

 All Class A + B + C tables
       │
       ▼
 ┌───────────────┐     ┌───────────────┐
 │  EX-P6-VR     │────▶│  EX-P6-DG     │
 │  Validation   │     │  Deploy Gate   │
 │  Runner       │     │               │
 └───────────────┘     └───────────────┘
  ValidationResults     DeploymentDecision → SYS_ALGORITHM

3. SUBSYSTEM DETAIL

## EX-P6-VR — Validation Runner
   Purpose: Execute 16+ validation rules across all tables
   Input: All Class A (knowledge), B (evidence), C (compiled) tables
   Output: ValidationResults
   ┌─────────────────────────────────────────────────────────────┐
   │ VALIDATION RULES (G1–G16 + extensions):                     │
   │ G1:  All FK references resolve (no dangling pointers)       │
   │ G2:  All edges_v1 rows have β̂ and SE_eff (no NaN)          │
   │ G3:  All node_ids in edges_v1 exist in nodes_v1             │
   │ G4:  118 edges present, 63 nodes present                    │
   │ G5:  All P_inclusion ∈ [0.05, 0.99]                         │
   │ G6:  All SE_eff > 0                                         │
   │ G7:  Prior type assigned to every edge                      │
   │ G8:  Aggregation method logged for every edge               │
   │ G9:  study_registry_v1 complete (no missing metadata)       │
   │ G10: edge_evidence_v1 FK → study_registry_v1 resolves       │
   │ G11: Controlled vocabulary compliance (all enums valid)     │
   │ G12: No duplicate rows (unique constraint check)            │
   │ G13: Timestamp consistency (created_at ≤ updated_at)        │
   │ G14: Version consistency (all _v1 suffixes present)         │
   │ G15: Reproducibility (fixed seed → same output)             │
   │ G16: Coverage minimum (≥50% edges have k≥1)                 │
   │                                                             │
   │ EXTENSION RULES (Gap 1 + Gap 2 Fixes):                     │
   │                                                             │
   │ G17: Hill/Emax completeness check                           │
   │   FOR each edge with functional_form = hill in edges_v1:    │
   │     REQUIRE: dose_bridges_v1 has matching complete row       │
   │              (E_max, EC₅₀, h all non-NULL)                  │
   │     OR: edges_v1.fallback_form = linear (explicit downgrade)│
   │     FAIL: "Edge {id} requires Hill params but               │
   │       dose_bridges_v1 has no complete entry and              │
   │       fallback_form is not set. Run COMPILE-INT              │
   │       or set fallback_form = linear."                        │
   │   This ensures ALG-A2 never encounters incomplete Hill       │
   │   params at runtime.                                         │
   │                                                             │
   │ G18: Intervention kernel coverage check                     │
   │   FOR each action in action_catalog_v1:                     │
   │     IF has_temporal_kernel = true:                           │
   │       REQUIRE: intervention_kernels_v1 has matching row     │
   │       FAIL: "Action {id} flagged has_temporal_kernel=true    │
   │         but no kernel entry exists."                         │
   │     IF has_temporal_kernel = false:                          │
   │       WARN: "Action {id} has no temporal kernel.             │
   │         Temporal predictions will use static-only or         │
   │         default conservative kernel."                        │
   │   This ensures ALG-E2 knows what to expect at runtime.      │
   │                                                             │
   │ Per rule: PASS / WARN / FAIL + specific violation details   │
   └─────────────────────────────────────────────────────────────┘

## EX-P6-DG — Deploy Gate
   Purpose: Make final deploy/block/conditional decision
   Input: ValidationResults
   Output: DeploymentDecision
   ┌─────────────────────────────────────────────────────────────┐
   │ Decision logic:                                              │
   │   0 FAILs, 0 WARNs → DEPLOY (clean)                         │
   │   0 FAILs, ≤5 WARNs → DEPLOY_WITH_WARNINGS                 │
   │   0 FAILs, >5 WARNs → CONDITIONAL (human review required)   │
   │   ≥1 FAIL → BLOCK (cannot deploy until resolved)            │
   │                                                              │
   │ On DEPLOY: edges_v1 marked deployment_ready = TRUE           │
   │            Timestamp: deployed_at = now()                    │
   │            SYS_ALGORITHM can begin ALG-A graph assembly      │
   │                                                              │
   │ On BLOCK: Specific violations listed for remediation         │
   │           Pipeline returns to EX-P5 or earlier chain         │
   └─────────────────────────────────────────────────────────────┘

4. BOUNDARY TABLES
   READS: ALL Class A, B, C tables (comprehensive validation)
   WRITES: edges_v1 (deployment_ready flag), deployment_log_v1

5. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | P6-G1 | 0 FAIL rules | DEPLOY or CONDITIONAL | BLOCK |
   | P6-G2 | Coverage ≥ 50% | Proceed | WARN: sparse model |


═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-ACQ (Acquisition Loop — NEW)
═══════════════════════════════════════════════════════════════════════════
Version: 1.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-ACQ
   Name:           Directed Acquisition Loop
   Purpose:        Transform evidence gaps and research_gap annotations into scored
                   acquisition candidates, retrieve papers, and feed them into EX-P0
   Phase:          Scheduled (every N hours) + event-triggered (EX-P5 gap queries)
   Subsystems:     3 (GapGenerator, APSScorer, RetrievalDispatcher)
   Formulas:       1 (APS score: 5-component weighted + author-gap boost)

2. CHAIN DIAGRAM

 EX-P5 SufficiencyReport + research_gap annotations (study_annotations_v1)
       │
       ▼
 ┌───────────┐     ┌───────────┐     ┌───────────┐
 │ EX-ACQ-GAP│────▶│ EX-ACQ-APS│────▶│ EX-ACQ-RET│
 │ Gap       │     │ APS       │     │ Retrieval │
 │ Generator │     │ Scorer    │     │ Dispatcher│
 └───────────┘     └───────────┘     └───────────┘
  APSQueryRequest[]  APSScoredCandidate[]  acquisition_queue_v1 rows

 Loop: EX-ACQ → EX-P0 → EX-P1→P4 → EX-P5 → EX-ACQ (re-evaluate)
 Stop: All edges ≥ Grade C OR no candidates APS ≥ 0.40 OR budget exhausted

3. INTERMEDIATE STATE SCHEMAS

   ### State: APSQueryRequest
   | Field | Type | Description |
   |-------|------|-------------|
   | target_edge_relation_id | TEXT | Edge needing evidence |
   | gap_type | ENUM | insufficient_k / low_grade / missing_population / missing_design / author_identified |
   | required_population | TEXT? | Population constraints |
   | required_design | TEXT? | Minimum study design |
   | search_query | TEXT | Constructed query |
   | source_annotation_ids | UUID[] | research_gap annotations that motivated this |

   ### State: APSScoredCandidate
   | Field | Type | Description |
   |-------|------|-------------|
   | candidate_doi | TEXT | Paper DOI |
   | aps_score | float [0-1] | Acquisition Priority Score |
   | edge_gap_component | float | 0.35 × (1 − grade/5) |
   | design_bonus | float | 0.20 weight |
   | pop_match | float | 0.20 weight |
   | recency | float | 0.15 weight |
   | source_quality | float | 0.10 weight |
   | author_gap_boost | bool | True if author-identified (1.5× multiplier) |

4. SUBSYSTEM INVENTORY
   | Order | ID | Name | Input | Output |
   |-------|----|------|-------|--------|
   | 1 | EX-ACQ-GAP | GapGenerator | SufficiencyReport + research_gap annotations | APSQueryRequest[] |
   | 2 | EX-ACQ-APS | APSScorer | APSQueryRequests + candidate metadata | APSScoredCandidate[] |
   | 3 | EX-ACQ-RET | RetrievalDispatcher | Candidates (APS ≥ 0.40) | acquisition_queue_v1 + papers → EX-P0 |

5. SUBSYSTEM DETAIL

## EX-ACQ-GAP — Gap Generator
   Purpose: Construct acquisition queries from evidence gaps + author annotations
   ┌─────────────────────────────────────────────────────────────┐
   │ Input: edges_v1 (edges below Grade C) + study_annotations_v1│
   │   WHERE category IN ('research_gap', 'future_research')     │
   │ Logic: For each gap, construct search_query from edge node  │
   │   names + gap type keywords. Author-identified gaps carry   │
   │   1.5× boost flag. Constraints from annotation             │
   │   structured_data_json when available.                      │
   └─────────────────────────────────────────────────────────────┘

## EX-ACQ-APS — APS Scorer
   Purpose: Score candidate papers using 5-component APS formula
   ┌─────────────────────────────────────────────────────────────┐
   │ APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch      │
   │       + 0.15·Recency + 0.10·SourceQuality                  │
   │ EdgeGap = 1 − (grade/5)                                    │
   │ If author_gap_boost: APS = min(APS × 1.5, 1.0)            │
   │ Weights: AUTHOR-CONSTRUCTED, require empirical calibration  │
   └─────────────────────────────────────────────────────────────┘

## EX-ACQ-RET — Retrieval Dispatcher
   Purpose: Dispatch scored candidates to retrieval tools, manage queue state
   ┌─────────────────────────────────────────────────────────────┐
   │ Source priority: PMC > Publisher API > Unpaywall > Firecrawl │
   │ Dedup: candidate_doi NOT in study_registry AND NOT in       │
   │   active acquisition_queue                                  │
   │ Rate limiting per source. Max retries: 3 exponential backoff│
   │ Writes: acquisition_queue_v1 (lifecycle: queued → dispatched │
   │   → retrieved → ingested / failed / deferred)               │
   └─────────────────────────────────────────────────────────────┘

6. BOUNDARY TABLES
   READS: edges_v1 (grades), edge_relations_definitions_v1, study_annotations_v1,
          study_registry_v1 (dedup)
   WRITES: acquisition_queue_v1

7. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | ACQ-G1 | APS ≥ 0.40 | Dispatch | Defer (re-evaluate next cycle) |
   | ACQ-G2 | DOI not duplicate | Dispatch | Skip |
   | ACQ-G3 | Loop termination: all edges ≥ Grade C OR no APS ≥ 0.40 OR budget=0 | Stop | Continue |

8. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | ACQ-A1 | APS weights (0.35/0.20/0.20/0.15/0.10) produce useful rankings | Mitigated by monitoring success_rate |
   | ACQ-A2 | Author-identified gaps (1.5× boost) are higher quality | Empirically testable |
   | ACQ-A3 | PubMed + Crossref + OpenAlex cover ≥90% of CRCI literature | Firecrawl fallback |


═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: EX-PROM (Promotion Monitor — NEW)
═══════════════════════════════════════════════════════════════════════════
Version: 1.0
Parent System: SYS_EXTRACTION

1. IDENTITY
   Chain ID:       EX-PROM
   Name:           Annotation Promotion Monitor
   Purpose:        Monitor accumulated annotations for promotion threshold convergence,
                   validate independence, check contradictions, generate human-review
                   proposals for Class A table modifications
   Phase:          Scheduled (daily)
   Subsystems:     3 (ThresholdChecker, IndependenceValidator, ProposalGenerator)

2. CHAIN DIAGRAM

 study_annotations_v1 (all canonical, maturity = 'reviewed')
       │
       ▼
 ┌───────────┐     ┌───────────┐     ┌───────────┐
 │ EX-PROM-  │────▶│ EX-PROM-  │────▶│ EX-PROM-  │
 │ THR       │     │ IND       │     │ PRP       │
 │ Threshold │     │ Independ. │     │ Proposal  │
 │ Checker   │     │ Validator │     │ Generator │
 └───────────┘     └───────────┘     └───────────┘
  ThresholdResult[]  IndependenceResult[]  PromotionCandidate[]
                                            → Human review queue

3. INTERMEDIATE STATE SCHEMAS

   ### State: ThresholdResult
   | Field | Type | Description |
   |-------|------|-------------|
   | category | ENUM | Annotation category |
   | target_entity_id | TEXT | Entity accumulating annotations |
   | raw_count | int | Total annotations in cluster |
   | threshold | int | Required count for this category |
   | threshold_met | bool | raw_count ≥ threshold |

   ### State: PromotionCandidate
   | Field | Type | Description |
   |-------|------|-------------|
   | category | ENUM | Annotation category |
   | target_entity_id | TEXT | Entity |
   | independent_evidence_units | int | Deduplicated trial/dataset count |
   | contradiction_ratio | float | Fraction conflicting |
   | proposed_action | TEXT | What would change |
   | proposed_target_table | TEXT | Which Class A table |

4. SUBSYSTEM INVENTORY
   | Order | ID | Name | Input | Output |
   |-------|----|------|-------|--------|
   | 1 | EX-PROM-THR | ThresholdChecker | study_annotations_v1 (reviewed) | ThresholdResult[] |
   | 2 | EX-PROM-IND | IndependenceValidator | ThresholdResult[] (met) + study_registry_v1 | IndependenceResult[] |
   | 3 | EX-PROM-PRP | ProposalGenerator | IndependenceResult[] (passed) | PromotionCandidate[] |

5. SUBSYSTEM DETAIL

## EX-PROM-THR — Threshold Checker
   Purpose: Count accumulated annotations per (category, target) vs thresholds
   ┌─────────────────────────────────────────────────────────────┐
   │ Thresholds (per category, AUTHOR-CONSTRUCTED):               │
   │   mechanism_hypothesis ≥ 3                                   │
   │   limitation_unmeasured_confounder ≥ 5                      │
   │   instrument_observation ≥ 2                                │
   │   adherence_data ≥ 4                                        │
   │   adverse_event: serious ≥ 1 OR mild ≥ 3                   │
   │   temporal_onset_decay ≥ 3                                  │
   │   dose_response_qualitative ≥ 2                             │
   │ Input: study_annotations_v1 WHERE maturity='reviewed'       │
   │   AND adjudication_status ≠ 'conflict'                      │
   └─────────────────────────────────────────────────────────────┘

## EX-PROM-IND — Independence Validator
   Purpose: Collapse raw counts into independent evidence units
   ┌─────────────────────────────────────────────────────────────┐
   │ Papers sharing dataset_id or trial_id → 1 unit              │
   │ Fallback: title/first-author/year Jaccard > 0.85           │
   │ Contradiction ratio = conflict annotations / total cluster  │
   │ Speculative ceiling: require ≥1 'strong' or 'moderate'     │
   └─────────────────────────────────────────────────────────────┘

## EX-PROM-PRP — Proposal Generator
   Purpose: Generate promotion proposals for human review
   ┌─────────────────────────────────────────────────────────────┐
   │ For each cluster passing THR + IND:                          │
   │   Compose proposed_action (what changes in Class A table)    │
   │   Identify proposed_target_table (which definition table)   │
   │   Package: PromotionCandidate → human review queue          │
   │ NOTE: Proposals are TRANSIENT until human acts on them.     │
   │   No table writes — proposals stored in review queue only.  │
   └─────────────────────────────────────────────────────────────┘

6. BOUNDARY TABLES
   READS: study_annotations_v1, study_registry_v1
   WRITES: None (proposals to human review queue only)

7. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | PROM-G1 | threshold_met = true | → IND | Skip (insufficient) |
   | PROM-G2 | Independent units ≥ threshold AND contradiction < ceiling | → PRP | Skip |
   | PROM-G3 | ≥1 'strong' or 'moderate' in cluster | → PRP | Skip (speculative ceiling) |

8. ASSUMPTIONS
   | # | Assumption | Impact |
   |---|-----------|--------|
   | PROM-A1 | dataset_id/trial_id sufficient for independence detection | Mitigated by fallback clustering |
   | PROM-A2 | Promotion thresholds calibrated for CRCI density | Requires gold benchmark |
   | PROM-A3 | Daily scheduling frequent enough | Acceptable for v2.0 |


═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
                    PART 3: TIER 3 — SUBSYSTEM CARDS
                    (~64 subsystems across 12 chains)
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P0: Pre-Extraction Triage (5 subsystems — +PTC)
───────────────────────────────────────────────────────────────────────────

## EX-P0-S1 — PDF Ingestion & Text Extraction
   ID: EX-P0-S1 | Type: ATOMIC | Phase: Build-time | Paper §: §2.5
   Purpose: Convert PDF to canonical text, assess extraction quality
   Inputs:  PDF file (binary), PubMed metadata (JSON, optional enrichment)
   Outputs: IngestedPaper {canonical_text, pdf_quality(high/medium/low/failed), page_count, has_tables, has_figures}
   Validation: text length > 0; quality ≠ failed; encoding UTF-8
   Connections: → P0-S2; No tables read

## EX-P0-S2 — Relevance Screening
   ID: EX-P0-S2 | Type: ATOMIC (LLM + rule-based) | Phase: Build-time | Paper §: §2.5
   Purpose: Screen paper for CRCI relevance using 5 inclusion + 3 exclusion criteria
   Inputs:  IngestedPaper (from S1), study_registry_v1 (duplicate check)
   Outputs: ScreenedPaper {relevance_score ∈ [0,1], criteria_results dict}
   Decision: ≥ 0.8 → INCLUDE; 0.5–0.8 → HUMAN_REVIEW; < 0.5 → EXCLUDE
   Validation: All 8 criteria evaluated; no duplicate DOI
   Connections: S1→S2; Reads study_registry_v1

## EX-P0-S3 — Execution Mode Selection
   ID: EX-P0-S3 | Type: ATOMIC (rule-based) | Phase: Build-time
   Purpose: Assign SHALLOW/STANDARD/DEEP based on study characteristics
   Inputs:  ScreenedPaper (from S2)
   Outputs: execution_mode ENUM(SHALLOW|STANDARD|DEEP)
   Decision: RCT+cancer+cognitive → DEEP; Cohort+cognitive → STANDARD; else → SHALLOW
   Connections: S2→S3→S4

## EX-P0-S4 — Route Decision
   ID: EX-P0-S4 | Type: ATOMIC (rule-based) | Phase: Build-time
   Purpose: Route to EX-P1 or reject; write triage record
   Inputs:  All P0 outputs
   Outputs: route_decision ENUM(ACCEPT|REJECT)
   Writes: triage_records_v1, study_registry_v1
   Connections: S3→S4→EX-P1

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P1: Hybrid Multi-Agent Extraction (14 subsystems — v2)
───────────────────────────────────────────────────────────────────────────

## EX-P1-AG1 — MetadataAgent
   ID: EX-P1-AG1 | Type: ATOMIC (LLM) | ALWAYS runs
   Purpose: Extract title, authors, journal, year, DOI, publication type
   Inputs: canonical_text | Outputs: prior_outputs.metadata
   Connections: → AG2

## EX-P1-AG2 — DesignAgent
   ID: EX-P1-AG2 | Type: ATOMIC (LLM) | ALWAYS runs
   Purpose: Classify study design, randomization, blinding, control group
   Inputs: canonical_text + metadata | Outputs: prior_outputs.design {study_design ENUM, randomization, blinding}
   Validation: study_design ∈ controlled vocabulary
   Connections: AG1→AG2→AG3; Critical input for EX-P3 L1 SE multiplier

## EX-P1-AG3 — CohortAgent
   ID: EX-P1-AG3 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract sample size, demographics, cancer type, treatment, stage
   Inputs: canonical_text + {metadata, design}
   Outputs: prior_outputs.cohorts (CohortProfile[]: N, age, sex, cancer_type, regimen, stage)
   Validation: N > 0; cancer_type ∈ node ontology
   Connections: AG2→AG3→AG4

## EX-P1-AG4 — OutcomeAgent
   ID: EX-P1-AG4 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract outcome domains, instruments, timepoints
   Inputs: canonical_text + {metadata, design, cohorts}
   Outputs: prior_outputs.outcomes (OutcomeSpec[]: domain, instrument_id, timepoints[])
   Validation: instrument maps to 1 of 23 in instruments_v1
   Connections: AG3→AG4→AG5

## EX-P1-AG5 — StatsLabelAgent (CRITICAL)
   ID: EX-P1-AG5 | Type: ATOMIC (LLM) | ALWAYS runs | Paper §: §2.5
   Purpose: Produce SpanLabel[] — grounded text spans with char offsets, 40 label types
   Inputs: canonical_text + all prior_outputs
   Outputs: SpanLabel[] {text, char_start, char_end, label_type, confidence}
   Label types: mean, SD, SE, CI_lower, CI_upper, p_value, N, effect_size, OR, HR, RR, ...
   Validation: ≥1 SpanLabel; char offsets valid; no overlapping spans
   Connections: AG4→AG5; OUTPUT CROSSES TRUST BOUNDARY → EX-TB-NP

## EX-P1-AG6 — ExposureAgent
   ID: EX-P1-AG6 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract treatment/exposure: drug, dose, duration, route
   Connections: AG5→AG6→AG7

## EX-P1-AG7 — MediatorAgent
   ID: EX-P1-AG7 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract mediating variables, pathway assignments
   Validation: mediator maps to DAG node_id
   Connections: AG6→AG7→AG8

## EX-P1-AG8 — TemporalAgent
   ID: EX-P1-AG8 | Type: ATOMIC (LLM) | STANDARD/DEEP only
   Purpose: Extract timepoints, follow-up duration, washout periods
   Validation: Duration parseable; timepoints ordered
   Connections: AG7→AG8→AG9; Critical for temporal decay in EX-P3 L6

## EX-P1-AG9 — ReconciliationAgent (NO LLM — rule-based)
   ID: EX-P1-AG9 | Type: ATOMIC (rule-based) | ALWAYS runs | Paper §: §2.5
   Purpose: 7 deterministic cross-agent consistency checks
   Inputs: Complete prior_outputs from AG1-AG8
   Outputs: ReconciliationReport {7 checks × PASS|WARN|FAIL}
   7 checks: N-consistency, design-stats coherence, outcome-instrument alignment,
     temporal consistency, exposure-outcome linkage, cohort-stats match, confidence
   Decision: Any FAIL → HUMAN_REVIEW; ≥3 WARNs → HUMAN_REVIEW
   Writes: extraction_audit_v1
   Connections: AG8→AG9→CE (if DEEP) or →EX-TB

## EX-P1-CE — ConceptEngine (DEEP mode only)
   ID: EX-P1-CE | Type: ATOMIC (hybrid: rule + fuzzy match)
   Purpose: Ground concepts to MeSH/SNOMED/CRCI node IDs
   Outputs: Grounded concept mappings (concept → node_id, confidence)
   Connections: AG9→CE; → EX-TB

───────────────────────────────────────────────────────────────────────────
CHAIN EX-TB: Trust Boundary (2 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-TB-NP — NumericParser (DETERMINISTIC — no LLM)
   ID: EX-TB-NP | Type: ATOMIC (rule-based, 11 parse rules) | Paper §: §2.5
   Purpose: Parse SpanLabels into TypedNumericValues via deterministic regex
   Inputs: SpanLabel[] from EX-P1-AG5 (trust boundary input)
   Outputs: TypedNumericValues[] {value, type, unit, parsed_from}
   11 rules: NP-01 Mean±SD, NP-02 CI, NP-03 p-value, NP-04 OR/HR/RR, NP-05 pct,
     NP-06 N, NP-07 effect size, NP-08 correlation, NP-09 F/t stat, NP-10 regression, NP-11 missing
   Validation: |β|≤5, SE>0, CI ordered, |r|≤1, N>0
   Connections: EX-P1→NP→CN

## EX-TB-CN — ClaimNormalizer (DETERMINISTIC — no LLM)
   ID: EX-TB-CN | Type: ATOMIC (rule-based) | Paper §: §2.5
   Purpose: Normalize to SD_SD scale, map to DAG edges, align orientation
   Inputs: TypedNumericValues[] (from NP), sd_anchors_v1, nodes_v1, edges_v1
   Process: Scale ID → SD borrowing (Tier1 1.0×, Tier2 1.15×, Tier3 1.30×) →
     Standardize → SE compute → Edge map → Orientation (confidence ≥ 0.60)
   Writes: edge_evidence_v1 (normalized evidence records)
   Connections: NP→CN; Writes edge_evidence_v1

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P2: Harmonization & Gating (7 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P2-S1 — Plausibility Check
   ID: EX-P2-S1 | Gate P2-G1: |β|≤5, SE>0, CI ordered, |r|≤1
   On fail: REJECT record with reason code | Connections: EX-TB→S1→S2

## EX-P2-S2 — Conversion Appropriateness
   ID: EX-P2-S2 | 4 checks: CG1 scale, CG2 variance, CG3 sample, CG4 direction
   Decision: PROCEED / sign_only / magnitude_only / BLOCKED | Connections: S1→S2→S3

## EX-P2-S3 — Scale Harmonization
   ID: EX-P2-S3 | Convert to SD_SD; SD borrowing: Tier1 1.0×, Tier2 1.15×, Tier3 1.30×
   Reads: sd_anchors_v1 | Connections: S2→S3→S4

## EX-P2-S4 — Orientation Alignment
   ID: EX-P2-S4 | Align sign with DAG convention; confidence ≥0.60 → full, <0.60 → sign_only
   Connections: S3→S4→S5

## EX-P2-S5 — Identification Status
   ID: EX-P2-S5 | Classify: Identified(1.00)/Partial(0.85)/Plausible(0.70)/Unidentified(0.50)
   Output: attenuation factor applied to β | Connections: S4→S5→S6

## EX-P2-S6 — Scope Matching
   ID: EX-P2-S6 | 5-dim transportability: cancer(0.35), phase(0.25), regimen(0.20), age(0.10), sex(0.10)
   Floor 0.3 (max 3.33× SE inflation) | Connections: S5→S6→S7

## EX-P2-S7 — Composability Check
   ID: EX-P2-S7 | 5 composability tests; Gate S2.5 → EX-P3 or HOLD
   Connections: S6→S7→EX-P3

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P2E: Extended Extraction (3 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P2E-S1 — TriangulationExtractor
   ID: EX-P2E-S1 | Agreement Z = |β₁−β₂|/√(SE₁²+SE₂²)
   Z<1.5→CONCORDANT(0.8×SE bonus); >3.0→DISCORDANT_SEVERE
   Writes: triangulation_evidence_v1

## EX-P2E-S2 — PathwayLoadingExtractor
   ID: EX-P2E-S2 | Extract biomarker→pathway loading factors
   Writes: pathway_biomarkers_v1

## EX-P2E-S3 — OntologyLinker
   ID: EX-P2E-S3 | Map concepts to MeSH/SNOMED/CRCI node IDs
   Writes: ontology_links_v1

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P3: Seven-Layer Heterogeneity (9 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P3-IN — Input Assembly
   ID: EX-P3-IN | Assemble per-record metadata for 7 layers
   Inputs: edge_evidence_v1 record + study metadata | Outputs: LayerInputPackage
   Connections: EX-P2→IN→L1

## EX-P3-L1 — Study Design Adjustment
   ID: EX-P3-L1 | Formula P3-1: Large RCT 1.0× → Expert 6.0×
   Connections: IN→L1→L2

## EX-P3-L2 — Transportability/Scope Match
   ID: EX-P3-L2 | Formula P3-2: w_scope 5 dims, floor 0.3; SE_adj = SE/max(w_scope,0.3)
   Connections: L1→L2→L3

## EX-P3-L3 — Statistical Heterogeneity
   ID: EX-P3-L3 | Formula P3-3: I²=(Q−(k−1))/Q; I²>50% → add τ²
   Connections: L2→L3→L4

## EX-P3-L4 — Scale/Cancer Validation
   ID: EX-P3-L4 | Formula P3-4: cancer-validated 1.0× → confounded 1.50×
   Gate: EXCLUDED instruments → record removed | Connections: L3→L4→L5

## EX-P3-L5 — GRADE Quality Assessment
   ID: EX-P3-L5 | Formula P3-5: High 1.0× / Moderate 1.25× / Low 1.50× / Very Low 2.00×
   Connections: L4→L5→L6

## EX-P3-L6 — Temporal Decay
   ID: EX-P3-L6 | Formula P3-6: w(t)=e^{−0.05t}; half-life 14d; >90d EXCLUDED
   Connections: L5→L6→L7

## EX-P3-L7 — Freshness Decay
   ID: EX-P3-L7 | Formula P3-7: w_fresh=max(0.70, 1−0.015×(2025−pub_year))
   Connections: L6→L7→OUT

## EX-P3-OUT — Final SE_eff Assembly
   ID: EX-P3-OUT | Formula P3-8: full SE_eff composition
   Validation: SE_eff > SE_raw (calibration only inflates)
   Writes: edge_evidence_v1 (SE_eff + all layer multipliers per record)
   Connections: L7→OUT→EX-P4

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P4: Aggregation + DCR (5 subsystems — v2)
───────────────────────────────────────────────────────────────────────────

## EX-P4-S1 — Evidence Pooling
   ID: EX-P4-S1 | Formula P4-1/P4-2
   Decision: k=0→BLOCKED, k=1→DIRECT, k≥2 I²<50%→IVW_FIXED, I²≥50%→IVW_RANDOM
   Sign conflict among high-quality → BLOCKED | Connections: EX-P3→S1→S2

## EX-P4-S2 — Prior Selection
   ID: EX-P4-S2 | Decision: k≥5→RobustMAP, k=2-4→Commensurate, k=1→Power,
     k=0+chain→MechanisticSynthesis, k=0→Placeholder
   Writes: prior_selection_log_v1 | Connections: S1→S2→S3

## EX-P4-S3 — Inclusion Probability
   ID: EX-P4-S3 | Formula P4-3: P_incl = logistic(−0.5+1.2·ln(k+1)+0.4Z+0.6·𝟙_RCT)
   Calibration: k=0,Z=0→P≈0.38; k=3+moderate→P≈0.80 | Connections: S2→S3→S4

## EX-P4-S4 — Write edges_v1
   ID: EX-P4-S4 | Update 118 rows: β̂, SE_eff, P_incl, prior_type, k, aggregation_method
   Writes: edges_v1, prior_selection_log_v1, aggregation_log_v1
   Validation: 118 edges complete; no NaN | Connections: S3→S4→SYS_ALGORITHM

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P4B: Publication Bias (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P4B-S1 — Egger Regression
   ID: EX-P4B-S1 | Formula P4B-1; p<0.10 → asymmetry; Gate: k≥10
   Connections: edges_v1→S1→S2

## EX-P4B-S2 — Trim & Fill
   ID: EX-P4B-S2 | Formula P4B-2; shift>0.1→MODERATE, >0.3→SEVERE
   Connections: S1→S2→S3

## EX-P4B-S3 — Leave-One-Out
   ID: EX-P4B-S3 | Formula P4B-3; influence>2.0→INFLUENTIAL; LOO range>0.3→FRAGILE
   Connections: S2→S3→S4

## EX-P4B-S4 — Bias Aggregator
   ID: EX-P4B-S4 | Formula P4B-4; 0→CLEAN, 1→1.1×SE, 2→1.3×SE, 3→1.5×SE
   Writes: edges_v1 (publication_bias, SE adjustment) | Connections: S3→S4→EX-P5

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P5: Sufficiency & Coherence (7 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P5-S1 — Coverage Analyzer
   ID: EX-P5-S1 | 118-edge matrix; k≥5+RCT→STRONG, k=2-4→MODERATE, k=1→WEAK, k=0→GAP
   Connections: edges_v1→S1→S2

## EX-P5-S2 — Chain Product Computer
   ID: EX-P5-S2 | Formula P5-1: β_chain=Π_e β_e for 20 pathways (all edges k≥1)
   Connections: S1→S2→S3

## EX-P5-S3 — Chain-vs-Direct Comparator
   ID: EX-P5-S3 | Formula P5-2/P5-3: Z-score classification; 10 testable chains
   Connections: S2→S3→S4

## EX-P5-S4 — Discrepancy Classification
   ID: EX-P5-S4 | Formula P5-5: 6 failure modes (FM1-FM6); multiple can apply
   Connections: S3→S4→S5

## EX-P5-S5 — SE Inflation Feedback
   ID: EX-P5-S5 | MILD→1.2×SE, MODERATE→1.5×SE, SEVERE→2.0×SE or exclude
   Writes: edges_v1 (inflated SE_eff) | Connections: S4→S5→S6

## EX-P5-S6 — E-Value Computer
   ID: EX-P5-S6 | Formula P5-4: E-value=RR+√(RR×(RR−1)); >3.0 robust, <2.0 vulnerable
   Only observational edges (RCT=∞) | Connections: S5→S6→S7

## EX-P5-S7 — Report Generator
   ID: EX-P5-S7 | Coverage heatmap, top 10 gaps (discovery_score), discrepancy summary
   Writes: acquisition_queue_v1 | Connections: S6→S7→EX-P6

───────────────────────────────────────────────────────────────────────────
CHAIN EX-P6: Deployment Validation (2 subsystems)
───────────────────────────────────────────────────────────────────────────

## EX-P6-VR — Validation Runner
   ID: EX-P6-VR | 17 rules (G1-G17): FK resolution, NaN checks, bounds, coverage,
     version consistency, Hill/Emax completeness [Gap-1]
   Inputs: All Class A/B/C tables | Outputs: ValidationResults {17 × PASS|WARN|FAIL}
   Connections: All tables→VR→DG

## EX-P6-DG — Deploy Gate
   ID: EX-P6-DG | 0 FAILs+0 WARNs→DEPLOY; 0 FAILs+≤5 WARNs→DEPLOY_WITH_WARNINGS;
     ≥1 FAIL→BLOCK (return to remediation)
   Writes: edges_v1 (deployment_ready), deployment_log_v1
   Connections: VR→DG; On DEPLOY → SYS_ALGORITHM begins ALG-A

───────────────────────────────────────────────────────────────────────────
NEW SUBSYSTEMS (v2.0 Enhancement)
───────────────────────────────────────────────────────────────────────────

## EX-P0-PTC — Paper Type Classifier (NEW)
   ID: EX-P0-PTC | Type: ATOMIC (LLM + rule-based) | Chain: EX-P0
   Purpose: Classify papers into 23 subtypes across 6 major categories
   Inputs: Abstract + methods text (from EX-P0-S1)
   Outputs: paper_subtype (23 values), classification_confidence, multi_product_flag
   Decision: confidence < 0.60 → 'unknown' + flag; umbrella_review → SHALLOW;
     case_report/qualitative → edge_evidence BLOCKED
   Connections: P0-S2→PTC→P0-S3; PaperType feeds EX-P1-CR

## EX-P1-CR — Canonical Reader (NEW)
   ID: EX-P1-CR | Type: COMPOSITE (4 sub-steps) | Chain: EX-P1
   Purpose: Read paper ONCE, produce PaperMap shared by all specialists
   Inputs: canonical_text, paper_subtype, extraction_mode
   Outputs: PaperMap (sections, tables, figures, candidate_spans, basic_study_object)
   Sub-steps: Section Segmenter → Table/Figure Registry → Candidate Span ID → Study Object
   Connections: P0-PTC→CR→AG1-AG10 (fan-out); escape hatch enables raw chunk requests

## EX-P1-AG10 — Strategic Intelligence Agent (NEW)
   ID: EX-P1-AG10 | Type: ATOMIC (LLM) | Chain: EX-P1 | STANDARD/DEEP only
   Purpose: Extract strategic annotations from Discussion/Limitations/Conclusion
   Inputs: PaperMap.sections[Discussion, Limitations, Conclusion]
   Outputs: RawAnnotation[] ONLY (no SpanLabels) — 7 primary categories
   Decision: case_report/qualitative → SKIP mechanism_hypothesis
   Connections: CR→AG10→REC (annotation pathway only, no SpanLabel path)

## EX-P1-REC — Reconciliation Layer (NEW)
   ID: EX-P1-REC | Type: COMPOSITE (4 sub-steps) | Chain: EX-P1
   Purpose: Merge duplicate annotations, detect contradictions, score confidence
   Inputs: All RawAnnotationEmission[] from AG1-AG10
   Outputs: ReconciliationDecision[] → EX-P1-ATB; study_annotations_raw_v1 (all preserved)
   Sub-steps: Clusterer → DedupChecker (Jaccard>0.80) → ConflictDetector → MergeDecider
   Formula: conf = min(1.0, 0.3 + 0.15×support_n + 0.2×mean_agent_conf)
   Connections: AG1-AG10→REC→ATB; Writes study_annotations_raw_v1

## EX-P1-ATB — Annotation Trust Boundary (NEW)
   ID: EX-P1-ATB | Type: COMPOSITE (6 rules) | Chain: EX-P1
   Purpose: Validate annotations before persisting to study_annotations_v1
   Inputs: ReconciliationDecision[] from REC
   Outputs: Validated → study_annotations_v1; Rejected → extraction_audit_v1
   Rules: AT-01 provenance, AT-02 explicit/inferred, AT-03 required fields,
     AT-04 contradiction routing, AT-05 high-impact gate, AT-06 speculative ceiling
   Validation: rejection rate < 20% (else agent prompts need tuning)
   Connections: REC→ATB→study_annotations_v1; Rejection → extraction_audit_v1

## EX-P4-DCR — Double-Counting Resolver (NEW)
   ID: EX-P4-DCR | Type: ATOMIC | Chain: EX-P4
   Purpose: Dual-metric overlap analysis for MA vs primary double-counting
   Inputs: GroupedEvidence, included_study_ids (MA), study_registry_v1.total_n
   Outputs: OverlapDecision + ResolvedEvidence
   Formulas: DCR-1 (count_overlap), DCR-2 (n_weighted_overlap)
   Decision: Both<0.10→USE_MA; Either>0.70→USE_PRIMARIES; Disagree>0.30→AMBIGUOUS→P4-G3
   Connections: P4-EG→DCR→P4-MA; AMBIGUOUS → human review queue

───────────────────────────────────────────────────────────────────────────
CHAIN EX-ACQ: Acquisition Loop (3 subsystems — NEW)
───────────────────────────────────────────────────────────────────────────

## EX-ACQ-GAP — Gap Generator
   ID: EX-ACQ-GAP | Type: ATOMIC | Chain: EX-ACQ
   Purpose: Construct acquisition queries from evidence gaps + author annotations
   Reads: edges_v1 (grades), study_annotations_v1 (research_gap, future_research)
   Outputs: APSQueryRequest[] with search_query, gap_type, constraints
   Connections: EX-P5 SufficiencyReport→GAP→APS

## EX-ACQ-APS — APS Scorer
   ID: EX-ACQ-APS | Type: ATOMIC | Chain: EX-ACQ
   Purpose: Score candidates using 5-component APS formula
   Formula: APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch
     + 0.15·Recency + 0.10·SourceQuality; author_gap × 1.5
   Connections: GAP→APS→RET

## EX-ACQ-RET — Retrieval Dispatcher
   ID: EX-ACQ-RET | Type: ATOMIC | Chain: EX-ACQ
   Purpose: Dispatch candidates (APS ≥ 0.40) to retrieval tools, manage queue
   Source priority: PMC > Publisher API > Unpaywall > Firecrawl
   Writes: acquisition_queue_v1 (lifecycle tracking)
   Connections: APS→RET→EX-P0 (papers re-enter pipeline)

───────────────────────────────────────────────────────────────────────────
CHAIN EX-PROM: Promotion Monitor (3 subsystems — NEW)
───────────────────────────────────────────────────────────────────────────

## EX-PROM-THR — Threshold Checker
   ID: EX-PROM-THR | Type: ATOMIC | Chain: EX-PROM
   Purpose: Count accumulated annotations vs category thresholds
   Reads: study_annotations_v1 (maturity='reviewed', no conflicts)
   Thresholds: mechanism≥3, confounder≥5, instrument≥2, adherence≥4, AE serious≥1
   Connections: study_annotations_v1→THR→IND

## EX-PROM-IND — Independence Validator
   ID: EX-PROM-IND | Type: ATOMIC | Chain: EX-PROM
   Purpose: Collapse paper counts to independent evidence units
   Logic: dataset_id/trial_id clustering; fallback title/author Jaccard>0.85
   Checks: contradiction_ratio + speculative ceiling
   Connections: THR→IND→PRP

## EX-PROM-PRP — Proposal Generator
   ID: EX-PROM-PRP | Type: ATOMIC | Chain: EX-PROM
   Purpose: Generate promotion proposals for human review
   Outputs: PromotionCandidate[] → human review queue (no table writes)
   Connections: IND→PRP→human review; on approval → Class A table modification

═══════════════════════════════════════════════════════════════════════════
                    PART 4: NEW TABLE SCHEMAS (v2.0)
═══════════════════════════════════════════════════════════════════════════

### B10. study_annotations_raw_v1
Purpose: Every annotation emitted by every agent before reconciliation.
1 Row = One annotation emission from one agent for one paper.
Written by: EX-P1-REC | Read by: Reconciliation (dedup ref), Audit

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| raw_annotation_id | UUID (PK) | 550e8400-... | Stable UUID |
| extraction_run_id | TEXT (FK) | RUN_20260221_a3f2 | FK → extraction_runs |
| study_id | TEXT (FK) | STUDY_SMITH_2023 | FK → study_registry_v1 |
| entered_by | TEXT | EX-P1-AG10 | Which agent |
| entered_at | TIMESTAMP | 2026-02-21T14:31:05Z | Emission time |
| category | TEXT (22-value CV) | limitation_unmeasured_confounder | Controlled vocab |
| target_entity_type | TEXT | edge | {edge,node,pathway,instrument,intervention,population,global} |
| target_entity_id | TEXT | ER_A_EXERCISE__COGNITION | Specific entity |
| content | TEXT | Authors report inability to control for sleep quality | Human-readable ONLY |
| structured_data_json | JSON? | {"confounder_name":"sleep_quality"} | Machine-parseable ONLY |
| evidence_strength | TEXT | strong | {strong,moderate,weak,speculative} |
| extraction_snippet | TEXT | Discussion, p.12: "A limitation..." | Provenance |
| source_span_id | TEXT? | SPAN_042 | PaperMap reference |

Retention: PERMANENT (append-only, never deleted). Scales: ~15-40 rows/paper.

### B11. study_annotations_v1
Purpose: Reconciled, deduplicated canonical annotations with maturity tracking.
Authoritative annotation table consumed by EX-P4 (variance), EX-ACQ (gaps), EX-PROM.
1 Row = One reconciled canonical annotation.
Written by: EX-P1-ATB | Read by: EX-P4-MA, EX-ACQ-GAP, EX-PROM-THR

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| annotation_id | UUID (PK) | 660e8400-... | Stable UUID |
| study_id | TEXT (FK) | STUDY_SMITH_2023 | FK → study_registry_v1 |
| ler_id | TEXT (FK, nullable) | LER_001234 | FK → edge_evidence_v1 (if linked) |
| category | TEXT (22-value CV) | mechanism_hypothesis | Controlled vocab |
| consumer | TEXT | dag_expansion | Which system component consumes |
| target_entity_type | TEXT | edge | Entity type |
| target_entity_id | TEXT | ER_A_EXERCISE__COGNITION | Entity ID |
| content | TEXT | Exercise may promote BDNF neuroplasticity | Human-readable ONLY |
| structured_data_json | JSON? | {"pathway":"M4_neuroplasticity"} | Machine-parseable ONLY |
| evidence_strength | TEXT | moderate | {strong,moderate,weak,speculative} |
| extraction_snippet | TEXT | Discussion, p.14: "Our findings..." | Best provenance |
| source_span_id | TEXT? | SPAN_067 | PaperMap reference |
| cross_agent_support_n | INT | 2 | Compatible agent count (≥1) |
| adjudication_status | TEXT | auto_merged | {auto_merged,conflict_resolved,human_reviewed,unreviewed} |
| duplicate_of_annotation_id | UUID? | NULL | Self-FK for merged annotations |
| reconciled_confidence | REAL | 0.72 | [0.0-1.0] from REC formula |
| maturity | TEXT | reviewed | {raw,reviewed,promoted,archived} |
| promoted_to | TEXT? | NULL | Table.column ref when promoted |

Retention: PERMANENT (soft delete via maturity='archived'). Scales: ~8-20 rows/paper.

### B12. extraction_runs
Purpose: Per-paper provenance. All versioning metadata here (not duplicated per annotation).
1 Row = One extraction run for one paper.
Written by: EX-P1 (at start + completion) | Read by: All EX chains

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| extraction_run_id | TEXT (PK) | RUN_20260221T143022_a3f2 | Unique run ID |
| study_id | TEXT (FK) | STUDY_SMITH_2023 | FK → study_registry_v1 |
| pipeline_version | TEXT | 2.0.0 | Semver |
| model_id | TEXT | claude-sonnet-4-5-20250929 | LLM model |
| prompt_template_version | TEXT | a1b2c3d4... | SHA-256 hash |
| paper_hash | TEXT | e5f6g7h8... | Content hash of input |
| paper_map_hash | TEXT? | i9j0k1l2... | PaperMap hash (null if sequential) |
| parser_version | TEXT | 1.3.0 | Trust boundary parser version |
| started_at | TIMESTAMP | 2026-02-21T14:30:22Z | Run start |
| completed_at | TIMESTAMP? | 2026-02-21T14:32:15Z | Run end (null if in progress) |
| status | TEXT | completed | {initialized,running,completed,failed,partial} |

Retention: PERMANENT. Scales: 1 row/paper (or more if re-extracted).

### B13. acquisition_queue_v1
Purpose: Operational queue for directed acquisition. Tracks candidates through lifecycle.
1 Row = One candidate paper in acquisition pipeline.
Written by: EX-ACQ-RET | Read by: EX-ACQ (dedup), Scheduler, UI

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| queue_id | TEXT (PK) | ACQ_20260301_b4c5 | Unique queue entry |
| candidate_doi | TEXT | 10.1001/jamaoncol.2024.1234 | Paper DOI |
| candidate_pmid | TEXT? | 39876543 | PubMed ID if available |
| candidate_title | TEXT | Exercise and Cognitive Function... | Paper title |
| target_edge_ids_json | JSON | ["ER_A_EXERCISE__COGNITION"] | FK array → edge_relations |
| aps_score | REAL | 0.78 | [0.0-1.0] APS score |
| aps_components_json | JSON | {"edge_gap":0.35,...} | Component breakdown |
| source_annotation_ids_json | JSON? | ["uuid1","uuid2"] | Motivating annotations |
| retrieval_tool | TEXT? | pubmed | {pubmed,crossref,unpaywall,firecrawl,publisher_api} |
| status | TEXT | dispatched | {queued,scoring,dispatched,retrieved,ingested,failed,deferred} |
| created_at | TIMESTAMP | 2026-03-01T09:15:00Z | Entry creation |
| updated_at | TIMESTAMP | 2026-03-01T09:20:00Z | Last update |

Retention: PERMANENT (status history preserved). Scales: unbounded (budget-controlled).

### FK WIRING (new tables)
study_annotations_raw_v1.extraction_run_id → extraction_runs.extraction_run_id (N:1 STRICT)
study_annotations_raw_v1.study_id → study_registry_v1.study_id (N:1 STRICT)
study_annotations_v1.study_id → study_registry_v1.study_id (N:1 STRICT)
study_annotations_v1.ler_id → edge_evidence_v1.ler_id (N:1 NULLABLE)
study_annotations_v1.duplicate_of_annotation_id → study_annotations_v1.annotation_id (self-ref NULLABLE)
extraction_runs.study_id → study_registry_v1.study_id (N:1 STRICT)
acquisition_queue_v1.target_edge_ids_json → edge_relations_definitions_v1 (N:M JSON-ARRAY FK)

### AMENDED FKs (existing tables)
edge_evidence_v1.parent_meta_study_id → study_registry_v1.study_id (N:1 NULLABLE, NEW)
edge_param_builds_v1.annotation_source_ids_json → study_annotations_v1.annotation_id (N:M JSON, NEW)


                    APPENDIX: CROSS-REFERENCE VALIDATION (v2.0)
═══════════════════════════════════════════════════════════════════════════

A. PAPER SECTION COVERAGE
   §2.5 Evidence Extraction   → EX-P0 (triage+PTC), EX-P1 (agents+CR+REC+ATB), EX-TB
   §2.9 Seven-Layer SE        → EX-P3 (L1–L7), also applied in ALG-B2
   §2.10 Prior Selection      → EX-P4-PS (same logic as ALG-B3)
   §2.12 MC/Inclusion         → EX-P4-MA/P4-3 (P_inclusion), also ALG-B4/D2
   §2.12.1 Publication Bias   → EX-P4B (Egger, trim-fill, LOO)
   §2.12.1 Double-Counting    → EX-P4-DCR (dual-metric overlap)                   NEW
   §2.13 Chain-vs-Direct      → EX-P5-S3 (comparator), also ALG-B6
   §2.13.2 Failure Modes      → EX-P5-S4 (6 failure mode classification)
   §2.22 Evidence Gaps        → EX-P5-S7 (gap report), EX-ACQ (acquisition loop)  NEW

B. TABLE READS/WRITES PER CHAIN
   EX-P0: READS study_registry_v1 | WRITES triage_records_v1, study_registry_v1
   EX-P1: READS triage_records_v1, ontology tables | WRITES extraction_audit_v1,
          study_annotations_raw_v1 (NEW), study_annotations_v1 (NEW), extraction_runs (NEW)
   EX-TB: READS sd_anchors_v1, nodes_v1, edges_v1 | WRITES edge_evidence_v1
   EX-P2: READS edge_evidence_v1, sd_anchors_v1 | WRITES edge_evidence_v1
   EX-P2E: READS prior_outputs | WRITES triangulation_evidence_v1, pathway_biomarkers_v1
   EX-P3: READS edge_evidence_v1 | WRITES edge_evidence_v1 (SE_eff, layer multipliers)
   EX-P4: READS edge_evidence_v1, context_matched_priors_v1, study_annotations_v1 (NEW),
          study_registry_v1 (NEW) | WRITES edges_v1 (+sigma_sq_structural, +overlap_decision),
          prior_selection_log_v1, aggregation_log_v1, edge_param_builds_v1
   EX-P4B: READS edges_v1, edge_evidence_v1 | WRITES edges_v1 (bias adjustment)
   EX-P5: READS edges_v1, pathway_map_v1, edge_evidence_v1 | WRITES edges_v1 (SE inflation)
   EX-P6: READS ALL Class A/B/C tables | WRITES edges_v1 (deployment_ready)
   EX-ACQ: READS edges_v1, study_annotations_v1, study_registry_v1 |               NEW
           WRITES acquisition_queue_v1 | FEEDS papers → EX-P0
   EX-PROM: READS study_annotations_v1, study_registry_v1 |                        NEW
            WRITES none (proposals → human review queue)

C. SUBSYSTEM ID CONSISTENCY
   EX-P0:   P0-S1, P0-S2, P0-PTC, P0-S3, P0-S4                          (5 subsystems)
   EX-P1:   CR, AG1-AG10, AG9, CE, REC, ATB                              (14 subsystems)
   EX-TB:   TB-NP, TB-CN                                                  (2 subsystems)
   EX-P2:   S1, S2, S3, S4, S5, S6, S7                                    (7 subsystems)
   EX-P2E:  S1, S2, S3                                                     (3 subsystems)
   EX-P3:   IN, L1, L2, L3, L4, L5, L6, L7, OUT                           (9 subsystems)
   EX-P4:   EG, DCR, MA, PS, WR                                           (5 subsystems)
   EX-P4B:  S1, S2, S3, S4                                                (4 subsystems)
   EX-P5:   S1, S2, S3, S4, S5, S6, S7                                    (7 subsystems)
   EX-P6:   VR, DG                                                        (2 subsystems)
   EX-ACQ:  GAP, APS, RET                                                 (3 subsystems)
   EX-PROM: THR, IND, PRP                                                 (3 subsystems)
   TOTAL: 64 subsystems ✓

D. DATA FLOW: END-TO-END (v2.0)
   PDF (external)
     → EX-P0 (triage + PTC → route decision)
       → EX-P1 (CR → 10 parallel agents → SpanLabel[] + RawAnnotations)
         ├─→ SpanLabel path: AG9 → CE → EX-TB (→ WRITE edge_evidence_v1)
         └─→ Annotation path: REC → ATB (→ WRITE study_annotations_v1)    NEW
           → EX-P2 (harmonize → gate → composability check)
             → EX-P3 (7-layer SE calibration → SE_eff per record)
               → EX-P4 (EG → DCR → MA + annotations → PS → WR → WRITE edges_v1)
                 → EX-P4B (publication bias → SE adjustment)
                   → EX-P5 (coverage + chain-vs-direct + gap analysis)
                     → EX-P6 (16 validation rules → DEPLOY or BLOCK)
                       → SYS_ALGORITHM (reads edges_v1 in ALG-A/B)
   
   Acquisition feedback loop (NEW):
     EX-P5 gaps + study_annotations_v1 (research_gap)
       → EX-ACQ (score → retrieve → EX-P0)
       Loop until: all edges ≥ Grade C OR budget exhausted
   
   Promotion feedback loop (NEW):
     study_annotations_v1 (accumulated)
       → EX-PROM (threshold → independence → proposal → human review)
       On approval: modify Class A tables → re-trigger extraction

E. CRITICAL BOUNDARY: EX → ALG
   The primary handoff is edges_v1 (118 rows, Class C table):
   - Written by: EX-P4-WR (initial), EX-P4B-S4 (bias adj), EX-P5-S5 (SE inflation)
   - Read by: ALG-A2 (edge matrix), ALG-B1 (evidence pooling), ALG-B2 (variance)
   - Fields: edge_param_id, source_node, target_node, beta, SE_eff, P_inclusion,
     prior_type, k, aggregation_method, publication_bias, deployment_ready,
     sigma_sq_structural (NEW — consumed by ALG-B2),
     overlap_decision (NEW — audit field)
   
   Secondary handoff: edge_evidence_v1 (Class B, scales with papers)
   - Written by: EX-TB-CN (per-paper)
   - Read by: ALG-B1 (per-edge aggregation at runtime)
   - Fields: 76 columns (+parent_meta_study_id NEW)

   Annotation handoff: study_annotations_v1 (Class B, NEW)
   - Written by: EX-P1-ATB (per-paper)
   - Read by: EX-P4-MA (structural_variance), EX-ACQ-GAP (research_gap), EX-PROM-THR
   - NOT read by ALG/RT/PRES (annotations influence edges_v1 indirectly through P4)

═══════════════════════════════════════════════════════════════════════════
END OF SYS_EXTRACTION COMPLETE SPECIFICATION (v2.0)
═══════════════════════════════════════════════════════════════════════════
