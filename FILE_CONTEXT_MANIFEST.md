═══════════════════════════════════════════════════════════════════════════
 CRCI — FILE CONTEXT MANIFEST
 Purpose: For each code file, the EXACT spec sections, formulas,
          tables, gates, and dependencies an LLM needs to implement it.
 Usage: When implementing any file, paste its manifest entry into the
        Master Prompt Template along with the referenced spec lines.
═══════════════════════════════════════════════════════════════════════════

HOW TO USE THIS DOCUMENT:

  1. Find the file you're implementing below
  2. Copy its manifest entry
  3. Open the referenced spec document
  4. Extract the specified line range
  5. Paste both into the Master Prompt Template
  6. The LLM now has full context for that file

  The spec line ranges point to the EXACT chain card or subsystem card
  that governs that file. No searching required.


═══════════════════════════════════════════════════════════════════════════
 LAYER 0: DATABASE + SHARED
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: database/schema/001_class_a_knowledge.sql                      │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALGORITHM lines 383-407 (Table Inventory)                  │
│       SYS_EXTRACTION lines 148-167 (Table Mapping)                   │
│ Purpose: CREATE TABLE for all 21 human-authored knowledge tables     │
│ Tables: nodes_v1 (63), edges_v1 skeleton (118),                      │
│   instruments_v1 (23), pathway_map_v1 (21), feedback_loops_v1 (5),   │
│   correlation_registry_v1 (12), modifier_registry_v1 (109),          │
│   recovery_params_v1 (7), context_matched_priors_v1 (33),            │
│   intervention_kernels_v1, sd_anchors_v1,                            │
│   literary_mechanistic_priors_v1, literary_constraints_v1,           │
│   contraindication_rules_v1, action_catalog_v1,                      │
│   dose_response_params_v1, synergy_registry_v1, objective_specs_v1,  │
│   outcome_anchors_v1, edge_relations_definitions_v1,                 │
│   biomarker_node_definitions_v1                                      │
│ Column sources: seed CSV headers define columns; nodes_v1 columns    │
│   listed at ALG lines 475-510; edges_v1 at ALG lines 512-548        │
│ Downstream: Everything. These are the scientific foundation.         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: database/schema/002_class_b_evidence.sql                       │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EXTRACTION lines 2559-2700 (Part 4: New Table Schemas)     │
│       SYS_EXTRACTION lines 148-158 (Table Mapping — column counts)   │
│ Purpose: CREATE TABLE for pipeline-written evidence tables            │
│ Tables:                                                              │
│   edge_evidence_v1 (76 cols) — THE main evidence store               │
│   study_registry_v1 — paper-level metadata                           │
│   study_annotations_raw_v1 (B10, 13 cols) — lines 2565-2596         │
│   study_annotations_v1 (B11, 18 cols) — lines 2597-2632             │
│   extraction_runs (B12, 11 cols) — lines 2633-2647                   │
│   acquisition_queue_v1 (B13, 12 cols) — lines 2648-2656             │
│   study_cohort_profiles_v1                                           │
│ CRITICAL: edge_evidence_v1 must include parent_meta_study_id (FK)    │
│ FK wiring: SYS_EXTRACTION lines 2657-2700 (9 relationships)         │
│ Downstream: Extraction writes here; Algorithm reads from here        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: shared/models/enums.py                                         │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: Scattered across all 4 specs. Key locations:                   │
│   SYS_EX lines 312-330 (SpanLabel 40 types)                         │
│   SYS_EX lines 430-445 (Annotation 22 categories)                   │
│   SYS_EX lines 1155-1170 (AggregationMethod 6 values)               │
│   SYS_EX lines 1190-1230 (OverlapDecision 4 values)                 │
│   SYS_ALG lines 1170-1190 (PriorType 5 values)                      │
│   SYS_ALG lines 285-310 (GradeLevel 4 values, StudyDesign 6 values) │
│ Purpose: All controlled vocabularies as Python enums                 │
│ Enums to define: SpanLabelType(40), AnnotationCategory(22),          │
│   StudyDesign(6), AggregationMethod(6), PriorType(5),                │
│   GradeLevel(4), EvidenceStrength(4), AnnotationMaturity(4),         │
│   AdjudicationStatus(4), OverlapDecision(4), SeverityTier(4),        │
│   StabilityFlag(3), PublicationBias(4), ExtractionMode(3),           │
│   PaperSubtype(23), ContraindicationStatus(3)                        │
│ Downstream: Used by virtually every other module                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: shared/config.py                                               │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: Formula registries across all chain cards. Key locations:      │
│   SYS_EX lines 853-870 (P3 layer multipliers)                       │
│   SYS_EX lines 1310-1320 (P4 formula constants)                     │
│   SYS_ALG lines 1298-1320 (σ²_struct, B2 constants)                 │
│   SYS_ALG lines 3301-3310 (worked example constants)                │
│ Purpose: ALL numeric constants from specs, centralized               │
│ Key constants:                                                       │
│   SIGMA_SQ_STRUCTURAL_DEFAULT = 0.25                                 │
│   SIGMA_SQ_STRUCTURAL_CEILING = 0.50                                 │
│   P_INCLUSION_ADJ_CAP = 1.0                                         │
│   FRESHNESS_DECAY_RATE = 0.015, FRESHNESS_FLOOR = 0.70              │
│   TEMPORAL_DECAY_RATE = 0.05, TEMPORAL_EXCLUSION_DAYS = 90           │
│   MC_DRAWS = 10000                                                   │
│   SCOPE_WEIGHTS = {cancer:0.35, phase:0.25, regimen:0.20,           │
│                    age:0.10, sex:0.10}, SCOPE_FLOOR = 0.3            │
│   DESIGN_MULTIPLIERS = {large_rct:1.0, small_rct:1.25,              │
│     cohort:1.75, cross_sectional:3.0, animal:4.5, expert:6.0}       │
│   GRADE_MULTIPLIERS = {HIGH:1.0, MODERATE:1.25, LOW:1.50,           │
│     VERY_LOW:2.00}                                                   │
│   SCALE_MULTIPLIERS = {validated:1.0, used:1.15, general:1.30,      │
│     confounded:1.50}                                                 │
│   APS_WEIGHTS = {edge_gap:0.35, design:0.20, pop:0.20,              │
│     recency:0.15, source:0.10}, APS_THRESHOLD = 0.40                │
│ Downstream: Imported by every formula-implementing module             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: shared/models/intermediate_states.py                           │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: Intermediate state tables in each chain card:                  │
│   SYS_EX lines 330-370 (PaperMap, SectionSegment, SpanLabel, etc.)  │
│   SYS_EX lines 460-490 (RawAnnotationEmission, ReconciliationDec.)  │
│   SYS_EX lines 1135-1180 (GroupedEvidence, ResolvedEvidence, etc.)  │
│   SYS_ALG lines 1075-1200 (PooledEdge, PriorSpec, etc.)             │
│   SYS_ALG lines 1630-1680 (PreparedObservation, ModifiedState)       │
│   SYS_ALG lines 2100-2160 (MCDraw, PerDrawEffect, SimResults)       │
│ Purpose: Pydantic/dataclass for ALL intermediate pipeline states     │
│ Key types: PaperMap, SpanLabel, TypedNumericValue, GroupedEvidence,   │
│   ResolvedEvidence, PooledEstimate, CalibratedRecord, MCDraw,        │
│   PerDrawEffect, SimulationResults, RecommendationReport             │
│ Downstream: Passed between subsystems within chains                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: shared/models/output_contracts.py                              │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_RUNTIME lines 61-66 (output tables)                       │
│       SYS_PRESENTATION lines 87-200 (PRES-PAT reads)                │
│       IMPLEMENTATION_BLUEPRINT Part 6 (output schemas)               │
│ Purpose: Typed schemas for final system outputs                      │
│ Types: CompositeScore, SchedulePlan, PathwayProfile,                 │
│   TemporalTrajectory, VarianceDecomposition, EvidenceGap,            │
│   DecisionTrace, RecommendationReport                                │
│ Downstream: Written by ALG-F/RT-I; Read by PRES                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: llm/client.py                                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 292-310 (agent architecture overview)             │
│       IMPLEMENTATION_BLUEPRINT Part 4 item 1 (LLM wrapper needs)     │
│ Purpose: Single-provider Claude API wrapper                          │
│ Must implement:                                                      │
│   - call(prompt, response_schema) → validated JSON                   │
│   - Retry: 3 attempts on HTTP 429/502/timeout, exponential backoff   │
│   - Schema validation: parse JSON, check against response_schemas.py │
│   - Token counting: prompt_tokens, completion_tokens                 │
│   - Cost logging: to extraction_runs or cost_tracker table           │
│   - Model ID: pinned, stored in extraction_runs.model_id             │
│ Does NOT need: multi-provider, routing, failover (that's v2)         │
│ Downstream: Called by all agents in extraction/p1_extraction/agents/  │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 LAYER 1: SYS_EXTRACTION
 Master spec: SYS_EXTRACTION_COMPLETE.md (2,764 lines)
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/pipeline.py                                         │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1-167 (System Card — overview, chain list,       │
│       table mapping, cross-cutting concerns, interfaces)             │
│ Purpose: Master orchestrator that calls P0→P6 in sequence            │
│ Must implement:                                                      │
│   - Create extraction_runs row at start (B12 schema, lines 2633-47) │
│   - Snapshot policy/config version (v1 ops #5)                       │
│   - Checkpoint per-agent and per-chain completion (v1 ops #6)        │
│   - Idempotency check: skip if same paper+version already done (#2)  │
│   - Call P0→P1→TB→P2→P3→P4→P4B→P5→P6 in sequence                   │
│   - Update extraction_runs status on completion/failure              │
│ Reads: PDF file path (from CLI)                                      │
│ Writes: extraction_runs (B12), orchestrates all downstream writes    │
│ Downstream: Every extraction chain                                   │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P0: TRIAGE ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p0_triage/pdf_ingestion.py                          │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 169-210 (EX-P0, subsystems S1-S2)                │
│ Purpose: PDF → canonical text, basic metadata extraction             │
│ Reads: PDF file on disk                                              │
│ Writes: In-memory canonical text + metadata dict                     │
│ Libraries: pypdf2 or pdfplumber                                      │
│ No formulas. No LLM calls. Pure parsing.                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p0_triage/relevance_screening.py                    │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 210-240 (EX-P0-S2)                               │
│ Purpose: Score CRCI relevance (cancer + cognition + intervention)    │
│ Reads: Canonical text from pdf_ingestion                             │
│ Writes: Relevance score + ACCEPT/REJECT decision                     │
│ May use: LLM (via llm/client.py) or keyword matching (simpler v1)   │
│ Gate: Relevance < threshold → REJECT (skip extraction)               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p0_triage/paper_type_classifier.py                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 240-265 (EX-P0-PTC, 23 subtypes)                │
│ Purpose: Classify paper into 1 of 23 subtypes                       │
│ Uses LLM: Yes (via llm/client.py)                                    │
│ Output: PaperSubtype enum value                                      │
│ Downstream: Affects extraction mode and agent checklist              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p0_triage/mode_selection.py                         │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 265-291 (EX-P0-S3, S4)                          │
│ Purpose: Select SHALLOW/STANDARD/DEEP based on paper type + EIG     │
│ Reads: Paper subtype, relevance score                                │
│ Writes: ExtractionMode enum + route decision                         │
│ Logic: RCTs/meta-analyses → STANDARD or DEEP;                       │
│        Case reports/editorials → SHALLOW or REJECT                   │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P1: EXTRACTION ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/canonical_reader.py                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 292-380 (EX-P1 v2 overview + CR subsystem)       │
│       SYS_EX lines 330-370 (PaperMap schema, 4 sub-steps)           │
│ Purpose: Read paper ONCE, create PaperMap shared by all agents       │
│ Uses LLM: Yes — section segmentation + table/figure detection        │
│ Output: PaperMap{sections[], tables[], figures[], candidate_spans[]} │
│ Sub-steps:                                                           │
│   CR-1: Section segmentation (abstract, methods, results, etc.)      │
│   CR-2: Table + figure registry with captions                        │
│   CR-3: Candidate span detection (numeric claims, stat results)      │
│   CR-4: Basic study object (N, design, arms)                         │
│ Downstream: ALL agents read from PaperMap (not raw text)             │
│ This is the key v2 efficiency improvement — one read, many agents    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/agents/base_agent.py                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 380-420 (agent architecture, parallel exec)      │
│ Purpose: Abstract base for all 10 extraction agents                  │
│ Must implement:                                                      │
│   - receive(paper_map: PaperMap, sections: list[str]) → AgentOutput  │
│   - Call llm/client.py with agent-specific prompt                    │
│   - Validate response against agent-specific schema                  │
│   - Return typed output (per response_schemas.py)                    │
│   - Checkpoint: log completion status per agent (v1 ops #6)          │
│ Does NOT contain any formulas. Just the framework.                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/agents/ag05_stats_label.py            │
│ *** CRITICAL — highest-impact extraction agent ***                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 400-420 (AG5 subsystem card)                     │
│       SYS_EX lines 312-330 (SpanLabel schema, 40 label types)        │
│ Purpose: Extract numeric statistical claims as SpanLabel[]           │
│ Uses LLM: Yes — reads Results section + tables from PaperMap         │
│ Output: SpanLabel[]{label_type, value, char_start, char_end,         │
│   confidence, source_section, source_table_id}                       │
│ Label types include: EFFECT_SIZE, CI_LOWER, CI_UPPER, P_VALUE,       │
│   SAMPLE_SIZE, MEAN, SD, ODDS_RATIO, HAZARD_RATIO, etc. (40 total)  │
│ CRITICAL: These labels become the RAW INPUT to the trust boundary.   │
│   If AG5 misses a β or misparses a CI, that evidence is LOST.        │
│ Prompt: llm/prompts/ag05_stats_label.txt (must be very precise)      │
│ Downstream: → tb_trust_boundary/numeric_parser.py                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/agents/ag10_strategic_intel.py        │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 420-470 (AG10 subsystem card, 7 categories)      │
│ Purpose: Extract annotations from Discussion/Limitations sections    │
│ Uses LLM: Yes — reads Discussion section from PaperMap               │
│ Output: RawAnnotationEmission[]{category, content, evidence_strength,│
│   extraction_snippet, source_span_id}                                │
│ 7 priority categories:                                               │
│   limitation_unmeasured_confounder, research_gap, adherence_data,    │
│   adverse_event, mechanism_hypothesis, null_finding_context,         │
│   temporal_onset                                                     │
│ Downstream: → reconciliation.py → annotation_trust_boundary.py       │
│   → study_annotations_v1 → P4-MA σ²_structural consumption          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/reconciliation.py                     │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 470-530 (EX-P1-REC, 4 sub-steps)                │
│ Purpose: Deduplicate + merge annotations from multiple agents        │
│ Formula: conf = min(1.0, 0.3 + 0.15×n + 0.2×mean_confidence)       │
│   where n = cross_agent_support_count                                │
│ Sub-steps:                                                           │
│   REC-1: Semantic clustering (same annotation from 2+ agents)        │
│   REC-2: Duplicate detection + merge                                 │
│   REC-3: Conflict detection + routing                                │
│   REC-4: Confidence scoring (formula above)                          │
│ Reads: RawAnnotationEmission[] from AG10 (and other agents)          │
│ Writes: Reconciled annotations → annotation_trust_boundary           │
│ If conflict: emit review_tasks row (v1 ops #8)                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p1_extraction/annotation_trust_boundary.py          │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 530-592 (EX-P1-ATB, 6 rules)                    │
│ Purpose: Validate annotations before writing to canonical table      │
│ Rules:                                                               │
│   AT-01: Provenance (must have extraction_snippet + source_span_id)  │
│   AT-02: Explicit vs inferred flag required                          │
│   AT-03: Category-specific required fields                           │
│     (e.g., confounder_name required for unmeasured_confounder)       │
│   AT-04: Contradiction check vs existing annotations                 │
│   AT-05: High-impact gate (categories that affect σ² need ≥moderate) │
│   AT-06: Speculative ceiling (speculative evidence ≤ 0.50 conf)      │
│ Reads: Reconciled annotations + existing study_annotations_v1        │
│ Writes: study_annotations_raw_v1 (B10), study_annotations_v1 (B11)  │
│ On rejection: emit review_tasks row (v1 ops #8)                      │
│ CRITICAL: This is the TRUST BOUNDARY for annotation data.            │
│   Annotations that fail ATB NEVER enter study_annotations_v1.        │
└─────────────────────────────────────────────────────────────────────┘

─── EX-TB: NUMERIC TRUST BOUNDARY ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/tb_trust_boundary/numeric_parser.py                 │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 593-660 (EX-TB-NP subsystem)                     │
│ Purpose: Convert SpanLabel[] → TypedNumericValue[]                   │
│ THIS IS THE TRUST BOUNDARY FOR NUMERIC EVIDENCE.                     │
│ Logic: Each SpanLabel has type + raw text value                      │
│   Parser must handle: "0.35 (95% CI: 0.12-0.58, p=0.003)"          │
│   → β=0.35, CI_lower=0.12, CI_upper=0.58, p=0.003                  │
│ Must handle edge cases:                                              │
│   - Negative values, scientific notation                             │
│   - Odds ratios (log-transform to β)                                 │
│   - Hazard ratios (log-transform to β)                               │
│   - "NS" or "p>0.05" → p_value = NULL, not 0                        │
│   - Missing SE → derive from CI: SE = (upper-lower)/(2×1.96)        │
│ NO LLM CALLS. Pure deterministic parsing.                            │
│ Reads: SpanLabel[] from AG05                                         │
│ Writes: TypedNumericValue[] → consistency_checker                    │
│ If ambiguous: flag for human review (v1 ops #8)                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/tb_trust_boundary/consistency_checker.py             │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 660-683 (EX-TB-CN subsystem)                     │
│ Purpose: Cross-field validation before writing evidence              │
│ Checks:                                                              │
│   - CI contains point estimate (lower < β < upper)                   │
│   - SE consistent with CI width                                      │
│   - p-value consistent with CI (CI excludes 0 ↔ p < 0.05)           │
│   - Sample size > 0 and plausible for design type                    │
│   - Effect direction consistent across related spans                 │
│ Reads: TypedNumericValue[] from numeric_parser                       │
│ Writes: edge_evidence_v1 rows (the actual evidence records)          │
│ CRITICAL: This is where LLM-extracted text BECOMES numeric evidence. │
│   After this point, the data is trusted for computation.             │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P2: HARMONIZATION ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p2_harmonization/sd_standardization.py               │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 684-710 (EX-P2-S1)                               │
│ Purpose: Standardize effect sizes to common SD using anchors         │
│ Reads: edge_evidence_v1 (raw β, SE), sd_anchors_v1                  │
│ Writes: edge_evidence_v1 (standardized β, SE)                        │
│ No LLM. Deterministic math.                                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p2_harmonization/scope_matching.py                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 740-764 (EX-P2-S6, 5-dimension scope)            │
│ Formula P3-2: w_scope = Σ(w_d × match_d)                            │
│   Dimensions: cancer(0.35), phase(0.25), regimen(0.20),              │
│               age(0.10), sex(0.10)                                   │
│   Floor: 0.3 (max 3.33× SE inflation from scope mismatch)           │
│ Reads: edge_evidence_v1 (study population), patient context          │
│ Writes: w_scope per evidence record                                  │
│ Constants: SCOPE_WEIGHTS, SCOPE_FLOOR from config.py                 │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P3: SEVEN-LAYER HETEROGENEITY ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p3_heterogeneity/layers.py                          │
│ *** FORMULA-DENSE — 8 formulas ***                                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 765-1101 (entire EX-P3 chain card)               │
│ Purpose: Apply 7 sequential SE adjustment layers per evidence record │
│ Formulas (implement ALL):                                            │
│   P3-1: m_design (L1) — multiplier table (lines 810-825)            │
│     Large RCT 1.0×, Small RCT 1.0-1.5×, Cohort 1.5-2.0×,           │
│     Cross-sectional 3.0×, Animal 4.0-5.0×, Expert 6.0×              │
│   P3-2: w_scope (L2) — 5-dim weighted match, floor 0.3              │
│   P3-3: I², τ² (L3) — if k≥2 and I²>50%, add τ² to SE²            │
│     Q = Σ w_i(β_i−β̂)²; I² = (Q−(k−1))/Q                          │
│   P3-4: m_scale (L4) — cancer validation multiplier (lines 848-855) │
│   P3-5: m_GRADE (L5) — High 1.0×, Moderate 1.25×, Low 1.50×,       │
│     Very Low 2.00×                                                   │
│   P3-6: w_temporal (L6) — w(t) = e^{−0.05t}, >90d EXCLUDED         │
│   P3-7: w_fresh (L7) — max(0.70, 1−0.015×(2025−pub_year))          │
│   P3-8: SE_eff = √[(SE·m_claim·m_GRADE·m_temporal)²+σ²_struct      │
│     +τ²·𝟙] / (max(w_scope,0.3)·w_fresh)                            │
│ Gate P3-G1: SE_eff > SE_raw (calibration only inflates, never       │
│   deflates) — if violated, ERROR                                     │
│ Reads: edge_evidence_v1 (per-record), config.py constants            │
│ Writes: edge_evidence_v1 (SE_eff, layer multipliers per record)      │
│ Constants: All multiplier tables from config.py                      │
│ Test: Known study (RCT, cancer-validated, GRADE High, 2020,          │
│   same-day) → SE_eff should equal √(SE²+0.25) with no inflation    │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P4: AGGREGATION ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4_aggregation/evidence_grouper.py                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1102-1160 (EX-P4 overview + P4-EG)               │
│ Purpose: Group evidence records by target edge, partition MA/primary │
│ Reads: edge_evidence_v1 (all records, calibrated)                    │
│ Writes: GroupedEvidence{edge_id, primary_records[], ma_records[]}    │
│ Logic: For each of 118 edges, collect all evidence records           │
│   Separate meta-analyses from primary studies                        │
│ Downstream: → double_counting.py                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4_aggregation/double_counting.py                   │
│ *** NEW in v2 — dual-metric overlap resolution ***                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1185-1230 (P4-DCR subsystem, full detail)        │
│ Formulas:                                                            │
│   DCR-1: count_overlap = |S_registry ∩ S_MA| / |S_MA|               │
│     S_registry = study IDs in our edge_evidence_v1                   │
│     S_MA = study IDs claimed by the meta-analysis                    │
│   DCR-2: n_weighted = Σ N_i(overlap) / Σ N_i(all MA studies)        │
│ Decision matrix:                                                     │
│   count<0.3 AND n_weighted<0.3 → USE_MA_POOLED                      │
│   count>0.7 AND n_weighted>0.7 → USE_PRIMARIES                      │
│   count>0.7 AND n_weighted<0.7 → USE_MA_EXCLUDE_OVERLAPPING         │
│   else → AMBIGUOUS → review_tasks row (v1 ops #8, P4-G3)            │
│ Reads: GroupedEvidence (MA + primary lists with included_study_ids)   │
│ Writes: ResolvedEvidence + OverlapDecision per edge                  │
│ CRITICAL: This prevents double-counting when a meta-analysis         │
│   includes studies that are also individually in your evidence base.  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4_aggregation/meta_analyzer.py                     │
│ *** FORMULA-DENSE — 6 formulas + annotation consumption ***          │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1230-1300 (P4-MA subsystem, full detail)         │
│ Formulas:                                                            │
│   P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i) [fixed-effects]        │
│   P4-2: β̂_RE with w*_i = 1/(SE²_i + τ²) [DerSimonian-Laird]       │
│   P4-3: P_incl = logistic(−0.5+1.2·ln(k+1)+0.4Z+0.6·𝟙_RCT)       │
│     where Z = (|β̂|/SE) and k = evidence count                      │
│   P4-3b: P_final = logistic(logit(P_formula) + adjustment)          │
│     adjustment from null_finding_context annotations, ±1.0 cap       │
│ Annotation consumption (P4-MA-c):                                    │
│   Read study_annotations_v1 where category =                         │
│     'limitation_unmeasured_confounder'                                │
│   σ²_adj = base(0.25) + Σ(severity_weight × confidence)             │
│   Ceiling: 0.50                                                      │
│   Write to edges_v1.sigma_sq_structural                              │
│ 6-branch aggregation decision tree (mirrors ALG-B1b):                │
│   k=0→BLOCKED, k=1→DIRECT, k≥2→IVW_FIXED/IVW_RANDOM/              │
│   STRATIFIED/SINGLE_BEST based on I² and stratifiability             │
│ Reads: ResolvedEvidence, study_annotations_v1                        │
│ Writes: PooledEstimate per edge (β̂, SE, method, I², k)              │
│ Constants: SIGMA_SQ_DEFAULT, SIGMA_SQ_CEILING, P_INCLUSION_ADJ_CAP  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4_aggregation/prior_selector.py                    │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1280-1310 (P4-PS subsystem, 5-branch tree)       │
│       SYS_ALG lines 1170-1200 (ALG-B3, same tree with more detail)  │
│ Purpose: Select prior type per edge from 5-branch decision tree      │
│ Decision tree:                                                       │
│   k≥5 + low heterogeneity → RobustMAP                               │
│   k≥3 + moderate quality → Commensurate                              │
│   k≥2 + some evidence → Power                                       │
│   k=0 but mechanistic pathway → MechanisticSynthesis                 │
│   else → Placeholder (uninformative)                                 │
│ 4-level fallback resolution:                                         │
│   Level 1: Exact match (cancer × phase × regimen) → SE 1.0×         │
│   Level 2: Cancer-type only → SE 1.2×                                │
│   Level 3: General cancer → SE 1.5×                                  │
│   Level 4: Uninformative (μ=0, Σ=I) → SE 2.0×                       │
│ Reads: PooledEstimate, context_matched_priors_v1 (33 rows)           │
│ Writes: PriorType + fallback_level per edge                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4_aggregation/edge_writer.py                       │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1310-1326 (P4-WR subsystem)                      │
│ Purpose: Write compiled edges_v1 (all 118 rows)                      │
│ Writes per edge: β̂, SE_eff, P_inclusion, prior_type, prior_params,  │
│   k, method, I², sigma_sq_structural, overlap_decision               │
│ Gate P4-G1: All 118 edges have method assigned (else ABORT)          │
│ Downstream: ALG-A reads edges_v1 for graph assembly                  │
└─────────────────────────────────────────────────────────────────────┘

─── EX-P4B, P5, P6 (supporting chains) ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p4b_publication_bias/egger.py + trim_fill.py        │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1394-1534 (EX-P4B chain card, full detail)       │
│ Formulas: Egger regression, Duval & Tweedie trim-and-fill           │
│ Output: BiasAssessment{CLEAN/POSSIBLE/PROBABLE/SEVERE} per edge     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p5_sufficiency/coverage.py + gap_analysis.py        │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1535-1786 (EX-P5 chain card, 7 subsystems)       │
│ Key formula: discovery_score = |elasticity| × SE_eff (§2.22)        │
│ Output: Per-edge sufficiency grade + evidence gap priorities         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: extraction/p6_deployment/validation.py                         │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_EX lines 1787-1898 (EX-P6, 16 validation rules)           │
│ Output: DEPLOY / DEPLOY_WITH_WARNINGS / BLOCK                       │
│ If BLOCK: emit review_tasks row (v1 ops #8)                         │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 LAYER 2: SYS_ALGORITHM
 Master spec: SYS_ALGORITHM_COMPLETE.md (4,418 lines)
═══════════════════════════════════════════════════════════════════════════

─── ALG-A: GRAPH ASSEMBLY (build-time) ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_a_graph/graph_object.py                        │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 410-1000 (entire ALG-A chain card)              │
│       Key sub-steps: A1-A5 (lines 475-1000)                         │
│ Purpose: Assemble complete GraphObject from all Class A/C tables     │
│ Sub-steps:                                                           │
│   A1: Load 63 nodes → hierarchy (lines 475-510)                     │
│   A2: Load 118 edges → B̂ matrix (lines 512-600)                    │
│   A3: Load 23 instruments → H matrix (measurement model)            │
│   A4: Spectral validation — ρ(B) < 1 CRITICAL (lines 700-750)      │
│     If ρ(B) ≥ 1 → system unstable → ABORT                           │
│   A5a: Pathway map (20 pathways from edges) (lines 780-820)         │
│   A5b: Correlation registry (12 pairs) (lines 820-840)              │
│   A5c: Feedback loop verification (5 loops, gain<1) (lines 840-870) │
│ Output: GraphObject{B_hat, nodes, H, Sigma_eps, pathway_map,        │
│   feedback_loops, correlation_registry}                               │
│ Reads: nodes_v1, edges_v1, instruments_v1, pathway_map_v1,          │
│   feedback_loops_v1, correlation_registry_v1                         │
│ Writes: In-memory GraphObject → ALG-B                                │
│ Gate: ρ(B) < 1 (spectral radius). THIS IS NON-NEGOTIABLE.           │
└─────────────────────────────────────────────────────────────────────┘

─── ALG-B: EVIDENCE COMPILATION (build-time) ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_b_evidence/evidence_compiler.py                │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 1004-1545 (entire ALG-B chain card)             │
│       Key sub-steps: B1-B7 (lines 1080-1540)                        │
│ Purpose: For each of 118 edges, compile final parameters             │
│ Sub-steps:                                                           │
│   B1: IVW pooling + aggregation decision tree (lines 1080-1150)     │
│     Same 6-branch tree as EX-P4. Mirrors/validates EX output.       │
│   B2: 7-layer SE_eff (lines 1150-1310) — same as EX-P3              │
│     σ²_struct reads edges_v1.sigma_sq_structural (default 0.25)      │
│   B3: Prior assignment (lines 1170-1200) — same as EX-P4-PS         │
│   B4: Inclusion probability (lines 1200-1240)                        │
│     P4-3 + P4-3b formulas                                           │
│   B5: Literary constraint enforcement                                │
│   B6: Chain-vs-direct validation (§2.13)                             │
│   B7: Freeze model state                                             │
│ Reads: edge_evidence_v1, context_matched_priors_v1, edges_v1         │
│ Writes: FrozenModelState (frozen_model_version_id, all edge params)   │
│ NOTE: In v1, B1-B6 may partially duplicate EX-P3/P4 work.           │
│   That's OK — ALG-B is the AUTHORITATIVE compilation.                │
│   EX produces edges_v1 as input; ALG-B validates and freezes.        │
└─────────────────────────────────────────────────────────────────────┘

─── ALG-C: POSTERIOR COMPUTATION (runtime) ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_c_posterior/bayesian_update.py                  │
│ *** THE MOST IMPORTANT FILE IN THE ENTIRE SYSTEM ***                 │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 1547-2012 (entire ALG-C chain card)             │
│       Key: C3 Bayesian State Estimation (lines 1879-1895)            │
│ Purpose: Update prior beliefs with patient observations              │
│ Core equations (C3a — Information-Form Rank-1 Updates):              │
│   Initialize: Λ_post = Λ_prior; η_post = η_prior                    │
│   Per observation y_k at instrument k → node i:                      │
│     Λ_post ← Λ_post + (b²_k/σ²_{y,k}) · eᵢeᵢᵀ                   │
│     η_post ← η_post + (b_k(y_k−a_k)/σ²_{y,k}) · eᵢ               │
│   Properties: commutative, O(1) per observation                      │
│ Recovery (C3b):                                                      │
│   θ̂ = Λ_post⁻¹ · η_post                                           │
│   Σ_post = Λ_post⁻¹ (via Cholesky)                                  │
│ Upstream dependencies:                                               │
│   C1: Prior loading with 4-level fallback (lines 1846-1862)         │
│     context_matched_priors_v1 (33 rows)                              │
│     Fallback: exact→cancer-type→general→uninformative                │
│   C2: Observation mapping (lines 1875-1878)                          │
│     questionnaire → instrument → node → {y_k, a_k, b_k, σ²_{y,k}}  │
│     Cancer validation multiplier on σ² (lines 1877)                  │
│     Temporal weighting: w(t)=e^{−0.05t}, >90d EXCLUDED (line 1878)  │
│ Downstream:                                                          │
│   C4: Modifier application — 109 rules (lines 1896-1920)            │
│     Individual modifier: m_k ∈ [0.7, 1.5]                           │
│     Cumulative: Π m_k ∈ [0.5, 2.0] (guardrails)                     │
│   C5: Write state_snapshots_v1                                       │
│ Reads: FrozenModelState, instruments_v1, patient observations        │
│ Writes: state_snapshots_v1 (posterior θ̂, Σ_post)                     │
│ Test: Known prior (μ=0, Σ=I) + known observation → verify           │
│   posterior matches hand calculation. THIS MUST BE EXACT.            │
└─────────────────────────────────────────────────────────────────────┘

─── ALG-D: MONTE CARLO SIMULATION (runtime) ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_d_simulation/mc_sampler.py                     │
│ *** MOST COMPUTE-INTENSIVE FILE ***                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 2015-2540 (entire ALG-D chain card)             │
│       D1 MC setup: lines 2030-2160                                   │
│       D2 per-draw: lines 2160-2310                                   │
│ Purpose: 10,000 MC draws per intervention, propagate uncertainty     │
│ Per draw (D1):                                                       │
│   D1a: Sample β_draw ~ Normal(β̂_edge, SE²_edge) for each edge      │
│   D1b: Sample include_draw ~ Bernoulli(P_inclusion) per edge        │
│   D1c: Sample θ₀_draw ~ Normal(θ̂_post, Σ_post)                     │
│   B_draw = β_draw × include_draw (masked effective B matrix)         │
│ Per draw per intervention (D2):                                      │
│   D2a: Apply do-operator (set intervention node to dose level)       │
│   D2b: Propagate through DAG: Δθ = (I−B_draw)⁻¹ × intervention     │
│     Methods: DIRECT_RCT, MATRIX_INVERSE, PATH_ENUMERATION            │
│   D2c: Apply synergy adjustments from synergy_registry_v1            │
│   D2d: Apply dose-response (Emax model) from dose_response_params    │
│   D2e: Compute ΔC (composite cognitive effect for this draw)         │
│ SAFE computation (D4):                                               │
│   SAFE_A = mean(ΔC across draws) (expected effect)                   │
│   SAFE_B = population-normed SAFE_A [0-10 scale]                     │
│   CrI_95 = [quantile_0.025, quantile_0.975] of ΔC distribution      │
│   stability = std(rank across bootstrap resamples)                   │
│ Safety (D3): contraindication_rules_v1 evaluation                    │
│   CLEAR / WARNING / BLOCKED per intervention                         │
│ Reads: FrozenModelState, state_snapshots_v1, intervention_kernels_v1,│
│   synergy_registry_v1, dose_response_params_v1, contraind_rules_v1   │
│ Writes: intervention_rankings_v1, decision_trace_v1                  │
│ Constants: MC_DRAWS=10000 from config.py                             │
│ MUST: Set random seed for reproducibility                            │
│ Performance: 63×63 matrix × 10K draws. Use numpy vectorization.      │
└─────────────────────────────────────────────────────────────────────┘

─── ALG-E: TEMPORAL PREDICTION ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_e_temporal/trajectory_simulator.py              │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 2543-2974 (entire ALG-E chain card)             │
│ Purpose: Forward simulation at 0,4,8,12,26,52 weeks                 │
│ Per timepoint: apply intervention kernel (onset, peak, decay)        │
│ Recovery model: post-cessation curve from recovery_params_v1         │
│ Reads: intervention_rankings (top), intervention_kernels_v1,         │
│   recovery_params_v1                                                 │
│ Writes: temporal_trajectories_v1                                     │
└─────────────────────────────────────────────────────────────────────┘

─── ALG-F: ANALYTICS ───

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_f_analytics/composite_scorer.py                │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 2977-3200 (ALG-F chain card, F1 subsystem)     │
│ Purpose: CRCI composite = severity-weighted mean across 11 subdomains│
│ Reads: state_snapshots_v1 (posterior), outcome_anchors_v1 (weights)  │
│ Output: CRCI_score [0-10], severity_tier, percentile, subdomains[]  │
│ Downstream: recommendation_runs_v1 (composite field)                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_f_analytics/variance_decomposer.py             │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 3200-3300 (F3 subsystem)                        │
│ Purpose: Decompose total uncertainty into 5 sources                  │
│ Sources: literature, measurement, structural, patient, stochastic    │
│ Writes: variance_decomposition_v1                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: algorithm/chain_f_analytics/evsi.py                            │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_ALG lines 3300-3500 (F5 subsystem)                        │
│ Purpose: Expected Value of Sample Information per edge               │
│ Formula: discovery_score = |elasticity| × SE_eff                     │
│ Nested MC: 500 outer × 1000 inner draws                             │
│ Writes: evidence_gaps_v1                                             │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 LAYER 3: SYS_RUNTIME
 Master spec: SYS_RUNTIME_COMPLETE.md (752 lines)
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: runtime/session.py                                             │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_RT lines 1-89 (system card + chain inventory)              │
│ Purpose: Session lifecycle — pin frozen model, run C→D→E→F→G→H→I    │
│ Must: Record frozen_model_version_id at session start (v1 ops #7)    │
│ Writes: recommendation_runs_v1 (session anchor)                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: runtime/schedule_generator.py                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_RT lines 90-259 (RT-G chain card, 4 subsystems)           │
│ Purpose: Generate + evaluate intervention combinations               │
│ Reads: intervention_rankings_v1, contraindication_rules_v1           │
│ Writes: schedule_plans_v1 (top 5), schedule_items_v1                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: runtime/adaptive_questions.py                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_RT lines 260-389 (RT-H chain card, 3 subsystems)          │
│       SYS_RT lines 603-640 (RT-H Tier 3 subsystem cards)            │
│ Purpose: Select next question maximizing information gain            │
│ Formula: IG(q) = expected reduction in posterior variance             │
│   from C3d: ΔVar(Y|X) = Cov(Y,X)²/Var(X)                           │
│ Reads: state_snapshots_v1, question_bank_v1                          │
│ Writes: question_sequence_v1, question_selection_trace_v1            │
│ Stop when: IG < threshold or max questions reached                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: runtime/report_assembler.py                                    │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_RT lines 390-512 (RT-I chain card, 4 subsystems)          │
│ Purpose: Package all outputs into RecommendationReport               │
│ Bundles: composite, schedules, pathways, trajectories, variance,     │
│   audit trail (decision_trace, prior_selection_log)                  │
│ Reads: ALL Class E output tables for this session                    │
│ Writes: recommendation_runs_v1 (final payload)                       │
│ Downstream: SYS_PRESENTATION reads this                              │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 LAYER 4: SYS_PRESENTATION
 Master spec: SYS_PRESENTATION_COMPLETE.md (541 lines)
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/crci_dashboard.py                                 │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 87-116 (PRES-PAT1)                             │
│ Reads: recommendation_runs_v1.composite                              │
│ Renders: Score gauge + severity tier + 11-subdomain radar chart      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/intervention_cards.py                             │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 117-146 (PRES-PAT2)                            │
│ Reads: schedule_plans_v1 (top 5), intervention_rankings_v1           │
│ Renders: Ranked cards with dose, CrI, stability, safety status       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/dag_viz.py                                        │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 231-255 (PRES-SCI2)                            │
│ Reads: nodes_v1, edges_v1 (full 63-node graph)                      │
│ Renders: Interactive DAG with edge weights, pathway highlighting     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/evidence_browser.py                               │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 218-230 (PRES-SCI1) + lines 429-470           │
│ Reads: edges_v1, edge_evidence_v1, study_registry_v1,               │
│   study_annotations_v1 (for evidence panel enrichment)               │
│ Renders: All 118 edges with drill-down to study-level evidence       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/trajectory_plot.py                                │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 132-160 (PRES-PAT3, PAT6)                      │
│ Reads: temporal_trajectories_v1, historical recommendation_runs      │
│ Renders: Time-series chart (0-52 weeks) with CrI bands              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/variance_pie.py                                   │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 147-170 (PRES-PAT4)                            │
│ Reads: variance_decomposition_v1                                     │
│ Renders: 5-slice pie (literature, measurement, structural,           │
│   patient, stochastic) with plain-language descriptions              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ FILE: presentation/provenance_viewer.py                              │
├─────────────────────────────────────────────────────────────────────┤
│ Spec: SYS_PRES lines 244-268 (PRES-SCI3)                            │
│ Reads: decision_trace_v1, edge_evidence_v1, study_registry_v1       │
│ Renders: Claim → edge → evidence records → study → paper chain       │
│ Purpose: Full scientific provenance for any recommendation           │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 USAGE EXAMPLE
═══════════════════════════════════════════════════════════════════════════

You want to implement extraction/p4_aggregation/meta_analyzer.py.

Step 1: Copy the manifest entry above for meta_analyzer.py
Step 2: Open SYS_EXTRACTION_COMPLETE.md
Step 3: Extract lines 1230-1300 (the P4-MA subsystem detail)
Step 4: Also grab lines 1310-1320 (the P4 formula registry)
Step 5: Paste into the Master Prompt Template:

  ## CURRENT TASK
  Component: SYS_EXTRACTION.EX-P4.P4-MA
  File: extraction/p4_aggregation/meta_analyzer.py

  ## SPECIFICATION EXCERPT
  [paste lines 1230-1320 from SYS_EXTRACTION_COMPLETE.md]

  ## UPSTREAM DEPENDENCIES
  Reads: ResolvedEvidence from double_counting.py
  Reads: study_annotations_v1 (category='limitation_unmeasured_confounder')

  ## DOWNSTREAM CONSUMERS
  Writes: PooledEstimate → prior_selector.py → edge_writer.py

  ## FORMULAS TO IMPLEMENT
  P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
  P4-2: β̂_RE with w*_i = 1/(SE²_i + τ²)
  P4-3: P_incl = logistic(−0.5+1.2·ln(k+1)+0.4Z+0.6·𝟙_RCT)
  P4-3b: P_final = logistic(logit(P_formula) + adjustment)

  ## VALIDATION GATES
  P4-G1: All 118 edges have method assigned
  P4-G3: DCR AMBIGUOUS → review_tasks (already handled upstream)

  ## CONSTANTS
  SIGMA_SQ_DEFAULT=0.25, SIGMA_SQ_CEILING=0.50,
  P_INCLUSION_ADJ_CAP=1.0

The LLM now has COMPLETE context. No searching. No guessing.

═══════════════════════════════════════════════════════════════════════════
END OF FILE CONTEXT MANIFEST
═══════════════════════════════════════════════════════════════════════════
