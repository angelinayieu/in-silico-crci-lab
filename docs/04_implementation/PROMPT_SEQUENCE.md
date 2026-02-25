═══════════════════════════════════════════════════════════════════════════
 CRCI — COMPLETE PROMPT SEQUENCE & CONTEXT MAP
 Every prompt. In order. With exact context attachments.
═══════════════════════════════════════════════════════════════════════════

YOUR DOCUMENT INVENTORY (6 core + 3 supporting)
────────────────────────────────────────────────

CORE (use constantly):
  A. SYS_EXTRACTION_COMPLETE.md        2,764 lines  — extraction spec
  B. SYS_ALGORITHM_COMPLETE.md         4,418 lines  — algorithm spec
  C. SYS_RUNTIME_COMPLETE.md             752 lines  — runtime spec
  D. SYS_PRESENTATION_COMPLETE.md        541 lines  — presentation spec
  E. IMPLEMENTATION_BLUEPRINT_v1.1.md    768 lines  — architecture + phases
  F. FILE_CONTEXT_MANIFEST.md            885 lines  — per-file lookup

SUPPORTING (use when referenced):
  G. 05_TABLE_SCHEMAS.md               2,334 lines  — full column definitions
  H. 06_FK_WIRING_MAP.md                 618 lines  — FK relationships
  I. 11_CONTROLLED_VOCABULARIES.md       344 lines  — enum values
  J. CONFLICT_ANALYSIS.md                337 lines  — v2 merge resolutions
  K. TABLE_FILL_ORDER.md                 378 lines  — when each table gets populated
  L. INTERFACE_SCHEMA_LOCK.md            377 lines  — field definitions for ALL intermediate states

EXTRACTION EXTENSIONS (use for Phases 1-4):
  M. SYS_EXTRACTION_ADDENDUM.md          598 lines  — AG11, extended agents, compilers
  N. AUTOMATED_RETRIEVAL_PLAN.md       1,001 lines  — source adapters, query gen, acquisition
  O. PAPER_TYPE_ROUTING_AND_ACQUISITION  ~600 lines  — 27 subtypes, MA multi-product, double-counting, guardrails
  P. PAPER_INTELLIGENCE_MAXIMIZATION     ~500 lines  — 22 content dims, study_annotations_v1, annotation lifecycle
  Q. HETEROGENEOUS_PAPER_TREATMENT     1,241 lines  — component inventory, precision cascade, completeness tracking
  R. CONVERSION_VALIDITY_AND_HARDENING   786 lines  — conversion matrix, verification escalation, shared-control, freshness


CONTEXT RULES
─────────────
Rule 1: ALWAYS attach E (Blueprint) with every prompt. It's the map.

Rule 2: ALWAYS attach F (Manifest) with every prompt. It tells the LLM
        which spec lines to read for the specific file being built.

Rule 3: Attach the RELEVANT system spec (A, B, C, or D) based on which
        layer you're building. Never all 4 at once unless doing integration.

Rule 4: For database/shared work, attach G (Table Schemas) + H (FK Map).

Rule 5: For enum-heavy files, attach I (Controlled Vocabularies).

Rule 6: The LLM should read the manifest entry FIRST, then the spec
        lines referenced, then write code. Not the reverse.

Rule 7: If the LLM's context window can't fit everything, prioritize:
        F (Manifest) > relevant spec lines > E (Blueprint) > G/H/I

Rule 8: ALWAYS append the 12 enforcement rules from
        CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt.

Rule 9: After EVERY prompt, the LLM must self-verify per the
        CLAUDE_CODE_ORCHESTRATION.md Step D checklist.

Rule 10: After EVERY phase, run the corresponding verification prompt
         from CODE_QUALITY_ENFORCEMENT.md Section 2.

Rule 11: Before implementing any file from Phase 1 onward, the LLM
         must re-read the 3 anchor files: shared/config.py,
         shared/models/enums.py, shared/models/intermediate_states.py.

Rule 12: For formula-dense files (P3 layers, P4 meta-analyzer,
         Bayesian update, MC sampler), also write test files with
         hand-computable expected values.


═══════════════════════════════════════════════════════════════════════════
 PHASE 0: FOUNDATION (database + shared)
 Attach: E (Blueprint) + F (Manifest) + G (Table Schemas) + H (FK Map)
         + K (TABLE_FILL_ORDER.md) + PARAMETER_PROVENANCE_AND_CURATION.md
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 After phase: Run VERIFICATION PROMPT V0, commit if passes
 NOTE: Phase 0 builds code + seeds GREEN/YELLOW values + APPROXIMATE
       defaults for RED values. Phase 0B (manual curation of RED values
       using templates in PARAMETER_PROVENANCE_AND_CURATION.md Part 6)
       runs IN PARALLEL with code Phases 1-5. Curation Tier 1
       (instruments_v1 psychometrics) MUST finish before Phase 5 testing.
       All Class A tables include provenance_status + provenance_ref columns.
═══════════════════════════════════════════════════════════════════════════

PROMPT 0.1 — Database Schema: Class A Knowledge Tables
───────────────────────────────────────────────────────
Context: E + F + G (05_TABLE_SCHEMAS.md) + H (06_FK_WIRING_MAP.md)
Spec lines to paste: SYS_ALG lines 383-407 (table inventory)

Prompt:
  You are implementing the CRCI system database.
  [paste manifest entry for database/schema/001_class_a_knowledge.sql]
  [paste 05_TABLE_SCHEMAS.md sections for all Class A tables]
  [paste 06_FK_WIRING_MAP.md]

  Create the SQL file database/schema/001_class_a_knowledge.sql with
  CREATE TABLE statements for all 21 Class A (human-authored) tables.
  Use PostgreSQL syntax. Include all columns from the table schemas doc.
  Include CHECK constraints for enums where appropriate.
  Include comments noting the row count and purpose of each table.

  CRITICAL: Every Class A table must include these 2 additional columns:
    provenance_status ENUM('DESIGN_CHOICE', 'CURATED_TRACED',
      'APPROXIMATE_PENDING', 'SENSITIVITY_REQUIRED')
      DEFAULT 'APPROXIMATE_PENDING'
    provenance_ref TEXT DEFAULT NULL
  See PARAMETER_PROVENANCE_AND_CURATION.md Part 4 for definitions.
  These track whether each value has real evidence or is using defaults.

Output: 001_class_a_knowledge.sql


PROMPT 0.2 — Database Schema: Class B Evidence Tables
─────────────────────────────────────────────────────
Context: E + F + G + H + A (SYS_EX lines 2559-2700 for B10-B13)
        + Routing Protocol §6 (schema amendments)
        + R Module 4 (shared-control + cohort lineage schema additions)

Prompt:
  [paste manifest entry for database/schema/002_class_b_evidence.sql]
  [paste SYS_EX lines 2559-2700 (Part 4: New Table Schemas)]
  [paste relevant sections from 05_TABLE_SCHEMAS.md]
  [paste Routing Protocol §6 (schema amendments)]
  [paste R Module 6.1 (schema additions table)]

  Create 002_class_b_evidence.sql with CREATE TABLE for:
  - edge_evidence_v1 (83 columns — include:
      parent_meta_study_id TEXT FK → study_registry_v1 nullable,
      meta_source_flag TEXT nullable — controlled vocab:
        {POOLED_ESTIMATE, SUBGROUP_ESTIMATE, NMA_MIXED, NMA_DIRECT,
         FOREST_PLOT_ENTRY, DOSE_RESPONSE_POINT},
      heterogeneity_json TEXT nullable — structured JSON for I²/τ²/Q,
      shared_control_flag BOOLEAN default FALSE,
      shared_control_study_id TEXT FK nullable,
      endpoint_vs_change TEXT nullable — {ENDPOINT, CHANGE, UNCLEAR},
      se_derivation_level TEXT nullable — {L1..L6},
      se_inflation_applied REAL default 1.0,
      conversion_formula TEXT nullable,
      conversion_bias_risk TEXT nullable — {NONE,LOW,MODERATE,HIGH,BLOCKED})
  - study_registry_v1 (include:
      study_subtype TEXT nullable — 27-value controlled vocab per
        Routing Protocol §1.1,
      cohort_lineage_id TEXT nullable — groups same-cohort papers,
      lineage_role TEXT nullable — {PRIMARY, SUPPLEMENTARY, FOLLOW_UP})
  - study_annotations_raw_v1 (B10, 13 cols)
  - study_annotations_v1 (B11, 18 cols — full schema per
      Intelligence Maximization Protocol §3.2, 22 annotation
      categories per §3.3)
  - extraction_runs (B12, 11 cols)
  - acquisition_queue_v1 (B13, 12 cols)
  - study_cohort_profiles_v1

Output: 002_class_b_evidence.sql


PROMPT 0.3 — Database Schema: Class C, D, E + Ops Tables + FKs
──────────────────────────────────────────────────────────────
Context: E + F + G + H

Prompt:
  Create the remaining schema files:
  - 003_class_c_compiled.sql (edges_v1 with sigma_sq_structural,
    overlap_decision columns)
  - 004_class_d_reference.sql (question_bank_v1, description_templates_v1)
  - 005_class_e_output.sql (recommendation_runs_v1, schedule_plans_v1,
    schedule_items_v1, state_snapshots_v1, decision_trace_v1,
    temporal_trajectories_v1, intervention_rankings_v1,
    variance_decomposition_v1, evidence_gaps_v1, question_sequence_v1,
    question_selection_trace_v1, prior_selection_log_v1,
    edge_param_builds_v1)
  - 006_fk_constraints.sql (ALL FK relationships from FK wiring doc,
    including 9 new FKs from v2 + self-referential FK on
    study_annotations_v1.duplicate_of_annotation_id)
  - 007_ops_tables.sql (review_tasks + policy_snapshots — see Blueprint
    Part 4 items 5 and 8)

Output: 5 SQL files


PROMPT 0.4 — Seed Loader + CSV Validation
─────────────────────────────────────────
Context: E + F + G

Prompt:
  Create database/seed_loader.py that:
  1. Reads all CSV files from database/seeds/
  2. Loads them into the corresponding PostgreSQL tables
  3. Validates FK integrity after loading (no orphan references)
  4. Reports: row counts per table, any validation failures
  5. Is idempotent: can be re-run safely (UPSERT or truncate+load)

  Also create empty CSV templates for the top-priority seeds:
  - nodes.csv (63 rows needed — columns from 001 schema)
  - edges.csv (118 rows — skeleton with placeholders)
  - instruments.csv (23 rows)

Output: seed_loader.py + 3 CSV templates


PROMPT 0.5 — Shared Models: Enums
─────────────────────────────────
Context: E + F + I (11_CONTROLLED_VOCABULARIES.md)
Spec lines: SYS_EX lines 312-330, 430-445, 1155-1170, 1190-1230
            SYS_ALG lines 285-310, 1170-1190

Prompt:
  [paste manifest entry for shared/models/enums.py]
  [paste 11_CONTROLLED_VOCABULARIES.md]

  Create shared/models/enums.py with Python enums for ALL controlled
  vocabularies. Use enum.Enum base class. Include docstrings noting
  which spec section defines each enum.

Output: enums.py


PROMPT 0.6 — Shared Models: Config Constants
────────────────────────────────────────────
Context: E + F
Spec lines: see manifest entry for shared/config.py (formula registries)

Prompt:
  [paste manifest entry for shared/config.py]

  Create shared/config.py with ALL numeric constants from the specs.
  Group by system (EX, ALG, RT). Include comment with formula ID for
  each constant. Use dataclass or module-level constants.

Output: config.py


PROMPT 0.7 — Shared Models: Intermediate States + Output Contracts
──────────────────────────────────────────────────────────────────
Context: E + F + L (INTERFACE_SCHEMA_LOCK.md — THIS IS THE PRIMARY SOURCE)
         + A (SYS_EX lines 330-370, 460-490, 1135-1180)
         + B (SYS_ALG lines 1075-1200, 1630-1680, 2100-2160)

Prompt:
  [paste INTERFACE_SCHEMA_LOCK.md in full — it defines every type]
  [paste manifest entries for intermediate_states.py and output_contracts.py]

  Create shared/models/intermediate_states.py with Pydantic BaseModel
  or dataclass for EVERY intermediate pipeline state defined in
  INTERFACE_SCHEMA_LOCK.md. This includes:

  - PaperMap + sub-types (SectionSegment, TableRef, FigureRef,
    CandidateSpan, StudyObject)
  - SpanLabel, RawAnnotationEmission, ReconciliationDecision
  - TypedNumericValue (TB → P2)
  - HarmonizedClaim (P2 → P3, inherits TypedNumericValue)
  - CalibratedRecord (P3 → P4, inherits HarmonizedClaim)
  - GroupedEvidence, OverlapDecision
  - PooledEdge, HeterogeneityAdjustedEdge, PriorSpec, InclusionProbEdge
  - FrozenModelState
  - PreparedObservation
  - MCDraw, PerDrawEffect, BundleEffect
  - SimulationResults + sub-types (RankedIntervention, BundleRec,
    DoseRec, ClaimLevel)

  Use inheritance: CalibratedRecord extends HarmonizedClaim extends
  TypedNumericValue. This mirrors the pipeline — each stage adds fields.

  EVERY field from INTERFACE_SCHEMA_LOCK.md must be present.
  Do not invent additional fields. Do not omit fields.

  Create shared/models/output_contracts.py with typed schemas for all
  final system outputs (CompositeScore, SchedulePlan, etc. — see
  Blueprint Part 6).

Output: intermediate_states.py + output_contracts.py


PROMPT 0.8 — Shared: DB Connection + Table ORM
──────────────────────────────────────────────
Context: E + F + the SQL schemas from 0.1-0.3

Prompt:
  Create:
  - shared/db.py: PostgreSQL connection via SQLAlchemy or psycopg2,
    session management, connection pooling
  - shared/models/tables.py: SQLAlchemy ORM models for all 56 tables
    (can generate from the SQL schemas)
  - shared/validators.py: Cross-table FK validation utilities

Output: db.py + tables.py + validators.py


═══════════════════════════════════════════════════════════════════════════
 PHASE 1: LLM CLIENT + EXTRACTION SKELETON
 Attach: E + F + A (SYS_EXTRACTION, relevant lines only)
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 Anchor: Re-read shared/config.py + enums.py + intermediate_states.py first
 After phase: Run VERIFICATION PROMPT V1, commit if passes
═══════════════════════════════════════════════════════════════════════════

PROMPT 1.1 — LLM Client (Claude Wrapper)
────────────────────────────────────────
Context: E + F
Spec lines: SYS_EX lines 292-310 (agent architecture overview)

Prompt:
  [paste manifest entry for llm/client.py]

  Create llm/client.py — a Claude API wrapper that:
  1. Takes a prompt string + expected response schema
  2. Calls Anthropic API with pinned model ID
  3. Retries 3× on HTTP 429/502/timeout with exponential backoff
  4. Parses JSON response and validates against schema
  5. Counts tokens (prompt + completion)
  6. Logs: model_id, prompt_hash, tokens, cost_estimate, latency
  7. Returns validated response or raises typed exception

  Also create:
  - llm/response_schemas.py (placeholder schemas per agent)
  - llm/cost_tracker.py (simple table/CSV logger)

Output: client.py + response_schemas.py + cost_tracker.py


PROMPT 1.2 — Extraction Pipeline Orchestrator
─────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 1-167)

Prompt:
  [paste manifest entry for extraction/pipeline.py]
  [paste SYS_EX lines 1-167 (system overview, chain list)]

  Create extraction/pipeline.py that:
  1. Accepts a PDF file path
  2. Creates extraction_runs row (B12 schema) with status=STARTED
  3. Snapshots current policy/config version (v1 ops #5)
  4. Checks idempotency: skip if same paper hash + version exists
  5. Calls P0 → P1 → TB → P2 → P3 → P4 → P4B → P5 → P6 in sequence
  6. Checkpoints after each chain completes (v1 ops #6)
  7. On failure: marks extraction_run as FAILED with error details
  8. On success: marks as COMPLETED

  For now, each chain call can be a stub that logs "chain X not yet
  implemented." We'll fill them in with subsequent prompts.

Output: pipeline.py


PROMPT 1.3 — P0 Triage: PDF Ingestion + Relevance + Classification
──────────────────────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 169-291)
        + Routing Protocol §1 (27 study_subtypes) + §9.1 (decision tree)
        + Treatment Protocol Part 2 (component inventory)

Prompt:
  [paste manifest entries for all p0_triage/ files]
  [paste SYS_EX lines 169-291 (EX-P0 chain card)]
  [paste Routing Protocol §1.1 study_subtype taxonomy table]
  [paste Treatment Protocol Part 2 Stage 2 (component inventory)]

  Create the 5 files in extraction/p0_triage/:
  - pdf_ingestion.py: PDF → text via pdfplumber. No LLM.
  - relevance_screening.py: keyword match for cancer+cognition+CRCI.
    Simple v1: score based on keyword density. No LLM needed.
  - paper_type_classifier.py: TWO-LEVEL classification via Claude:
    Level 1: study_subtype (27 values per Routing Protocol §1.1).
    Level 2: PaperSubtype enum (backward compat).
    Prompt in llm/prompts/ptc_prompt.txt.
    Decision tree per Routing Protocol §9.1.
  - mode_selection.py: study_subtype → ExtractionMode mapping.
    RCT/meta-analysis → DEEP. Cohort → STANDARD. Case report → MINIMAL.
    Umbrella reviews: SHALLOW + BLOCK numeric extraction.
  - component_inventory.py: Detect ALL information types present.
    Scans PaperMap sections/tables for 9 parameter-yielding components
    + 9 intelligence-yielding components (Treatment Protocol Part 2).
    Returns ComponentInventory dict: {component: bool, confidence: float}.
    This drives agent activation in P1 (which extensions fire).

Output: 5 Python files + 1 prompt template


PROMPT 1.4 — P1 Agent Framework + First 3 Agents
────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 292-420)

Prompt:
  [paste manifest entries for base_agent.py, ag01, ag02, ag05]
  [paste SYS_EX lines 292-420 (EX-P1 overview + agent cards)]

  Create:
  - extraction/p1_extraction/canonical_reader.py
    Reads paper once, creates PaperMap. 4 sub-steps from spec.
  - extraction/p1_extraction/agents/base_agent.py
    Abstract base: receive PaperMap → call LLM → validate → return
  - agents/ag01_metadata.py (title, authors, DOI, journal)
  - agents/ag02_design.py (study design classification)
  - agents/ag05_stats_label.py (*** CRITICAL: SpanLabel[] production)

  Also create prompt templates:
  - llm/prompts/ag01_metadata.txt
  - llm/prompts/ag02_design.txt
  - llm/prompts/ag05_stats_label.txt

  AG05 is the highest-impact agent. Its prompt must explicitly list
  all 40 SpanLabel types and require char offsets + confidence scores.

Output: 5 Python files + 3 prompt templates


PROMPT 1.5 — Remaining Agents (AG03-04, AG06-AG10)
──────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 380-470)

Prompt:
  [paste SYS_EX lines 380-470 (remaining agent cards)]

  Create agents ag03 through ag10, following the same pattern as
  ag01/ag02. Each agent:
  - Extends base_agent.py
  - Reads specific PaperMap sections
  - Has its own prompt template in llm/prompts/
  - Returns typed output per response_schemas.py

  AG09 (reconciliation support) is rule-based, NO LLM.
  AG10 (strategic intel) extracts 7 annotation categories from
  Discussion section — outputs RawAnnotationEmission[].

Output: 7 Python files + 6 prompt templates


PROMPT 1.6 — Reconciliation + Annotation Trust Boundary
──────────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 470-592)

Prompt:
  [paste manifest entries for reconciliation.py and
   annotation_trust_boundary.py]
  [paste SYS_EX lines 470-592 (REC + ATB subsystems)]

  Create:
  - extraction/p1_extraction/reconciliation.py
    Formula: conf = min(1.0, 0.3 + 0.15×n + 0.2×mean_confidence)
    4 sub-steps: cluster, dedup, conflict detect, confidence score
    On conflict: emit review_tasks row

  - extraction/p1_extraction/annotation_trust_boundary.py
    6 rules (AT-01 through AT-06)
    Writes: study_annotations_raw_v1 (B10), study_annotations_v1 (B11)
    On rejection: emit review_tasks row

Output: 2 Python files


═══════════════════════════════════════════════════════════════════════════
 PHASE 2: TRUST BOUNDARY + HARMONIZATION + CALIBRATION
 Attach: E + F + A (SYS_EXTRACTION, relevant lines)
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 Anchor: Re-read shared/config.py + enums.py + intermediate_states.py first
 Tests: For Prompt 2.3 (layers.py), also write test with hand-computed SE_eff
 After phase: Run VERIFICATION PROMPT V2 (formula audit), commit if passes
═══════════════════════════════════════════════════════════════════════════

PROMPT 2.1 — Numeric Trust Boundary
───────────────────────────────────
Context: E + F + A (SYS_EX lines 593-683)
        + Treatment Protocol Part 4 Stage 4 (precision cascade + conversions)
        + R (Conversion Validity Matrix — Module 1: executable conversion gates)
        + Routing Protocol §5.1 (universal guardrails UG-01 through UG-08)

Prompt:
  [paste manifest entries for numeric_parser.py and consistency_checker.py]
  [paste SYS_EX lines 593-683 (EX-TB chain card)]
  [paste Treatment Protocol Part 4 Stage 4: precision cascade (6 levels)
   and non-edge conversion pathways (psychometric, temporal, normative)]
  [paste R Module 1 conversion validity matrix (ALL tables: 1.1, 1.2, 1.3, 1.4)]
  [paste Routing Protocol §5.1 (universal guardrails)]

  Create:
  - extraction/tb_trust_boundary/numeric_parser.py
    SpanLabel[] → TypedNumericValue[]. Pure deterministic parsing.
    Handle: negative values, OR→logOR, HR→logHR, "NS"→NULL,
    derive SE from CI: SE = (upper-lower)/(2×1.96)

    PRECISION CASCADE (6 levels with inflation):
    Level 1: SE reported directly → quality=DIRECT, inflation=1.00×
    Level 2: From CI → quality=DERIVED_EXACT, inflation=1.00×
    Level 3: From p-value → quality=DERIVED_APPROXIMATE, inflation=1.05×
    Level 4: From N only → quality=ESTIMATED_FROM_N, inflation=1.15×
    Level 5: Borrowed SD → quality=SD_BORROWED, inflation=1.15-1.50×
    Level 6: Direction only → quality=QUALITATIVE (no SE, no pooling)
    Record precision_derivation_level on each TypedNumericValue.

    NON-EDGE CONVERSIONS (extend for all parameter types):
    Psychometric: split-half→α via Spearman-Brown, validate α∈(0,1)
    Factor loadings: flag unstandardized, validate λ∈(0,1)
    Temporal: normalize to weeks (months×4.33, days/7, cycles×cycle_wks)
    Normative: median/IQR→mean/SD, validate z-score < 4 vs general pop

  - extraction/tb_trust_boundary/consistency_checker.py
    Cross-field checks: CI contains β, SE~CI width, p~CI, N>0
    Enforce UG-01 through UG-08 from Routing Protocol §5.1.
    Writes edge_evidence_v1 rows (+ meta_source_flag if MA-derived).

  NO LLM CALLS in either file. This is the trust boundary.

Output: 2 Python files


PROMPT 2.2 — Harmonization Pipeline
───────────────────────────────────
Context: E + F + A (SYS_EX lines 684-764)

Prompt:
  [paste manifest entries for all p2_harmonization/ files]
  [paste SYS_EX lines 684-764 (EX-P2 chain card)]

  Create all files in extraction/p2_harmonization/:
  - sd_standardization.py (anchor-based, reads sd_anchors_v1)
  - direction_alignment.py (canonicalize effect direction)
  - claim_level.py (Identified/Associational/Mechanistic)
  - scope_matching.py (Formula P3-2: 5-dimension weighted match)
  - gating.py (quality gates)

Output: 5 Python files


PROMPT 2.3 — Seven-Layer Heterogeneity (SE_eff)
───────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 765-1101) + shared/config.py

Prompt:
  [paste manifest entry for layers.py — the FORMULA-DENSE one]
  [paste SYS_EX lines 765-1101 (entire EX-P3 chain card)]

  Create extraction/p3_heterogeneity/layers.py implementing ALL 7
  layers as composable functions:

  L1: m_design (P3-1) — multiplier table from config
  L2: w_scope (P3-2) — 5-dim match, floor 0.3
  L3: I², τ² (P3-3) — Cochran's Q, DerSimonian-Laird
  L4: m_scale (P3-4) — cancer validation multiplier
  L5: m_GRADE (P3-5) — GRADE quality multiplier
  L6: w_temporal (P3-6) — e^{-0.05t}, >90d EXCLUDED
  L7: w_fresh (P3-7) — 1.5%/yr decay, floor 0.70

  Create extraction/p3_heterogeneity/se_eff_assembly.py:
  Formula P3-8:
    SE_eff = √[(SE·m_claim·m_GRADE·m_temporal)²+σ²_struct+τ²·𝟙]
             / (max(w_scope,0.3)·w_fresh)

  Gate P3-G1: SE_eff ≥ SE_raw (never deflates). Assert this.

  Import ALL constants from shared/config.py.

Output: 2 Python files


═══════════════════════════════════════════════════════════════════════════
 PHASE 3: AGGREGATION + COMPILATION
 Attach: E + F + A (SYS_EX lines 1102-1898)
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 Anchor: Re-read config.py + enums.py + intermediate_states.py first
 Tests: For Prompt 3.2 (meta_analyzer.py), write test with hand-computed IVW
 After phase: Included in V2 verification (run V2 after Phases 2+3 combined)
═══════════════════════════════════════════════════════════════════════════

PROMPT 3.1 — Evidence Grouper + Double-Counting Resolver
───────────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 1102-1230)
        + Routing Protocol §3 (double-counting prevention — full rules)
        + Routing Protocol §7.1 (aggregation pipeline step 2.5)
        + R Module 4 (shared-control + cohort lineage + change-vs-endpoint)

Prompt:
  [paste manifest entries for evidence_grouper.py and double_counting.py]
  [paste SYS_EX lines 1102-1230 (P4-EG + P4-DCR)]
  [paste Routing Protocol §3 (full double-counting rules)]
  [paste R Module 4 (all three subsections: 4.1, 4.2, 4.3)]

  Create:
  - extraction/p4_aggregation/evidence_grouper.py
  - extraction/p4_aggregation/double_counting.py
    DCR-1: count_overlap = |S_registry ∩ S_MA| / |S_MA|
    DCR-2: n_weighted = Σ N_i(overlap) / Σ N_i(all)
    Decision matrix:
      overlap < 0.70 → USE_MA_POOLED, exclude overlapping primaries
      overlap ≥ 0.70 → USE_CONSTITUENTS, exclude MA pooled
    Forest plot entries: always superseded when full paper extracted
    Subgroup estimates from same MA: correlated, do NOT IVW-pool
    NMA triple-overlap: NMA > pairwise MA if more recent + inclusive
    Record decisions in edge_param_builds_v1 as structured JSON.
    AMBIGUOUS → review_tasks row

    SHARED CONTROL (Module 4.1):
    - Detect shared_control_flag on evidence records
    - Split N_control evenly: N_per_comparison = N_control / k_comparisons
    - Recompute SE with reduced control N

    COHORT LINEAGE (Module 4.2):
    - Group records by cohort_lineage_id
    - Select PRIMARY paper per lineage (longest follow-up > largest N > most recent)
    - Set non-primary to lineage_role = SUPPLEMENTARY (retains annotations, temporal)

    CHANGE vs ENDPOINT (Module 4.3):
    - Partition records by endpoint_vs_change
    - If ≥2/3 same type: convert minority to match
    - If mixed: pool separately, take larger-k pool

Output: 2 Python files


PROMPT 3.2 — Meta-Analyzer (IVW/RE + Annotations)
──────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 1230-1320)
        + R Module 2 (influence-aware verification escalation)
        + R Module 5 (family-specific freshness decay policies)

Prompt:
  [paste manifest entry for meta_analyzer.py — the 6-formula one]
  [paste SYS_EX lines 1230-1320 (P4-MA + formula registry)]
  [paste R Module 2 (escalation rules E1-E6)]
  [paste R Module 5 (freshness decay table)]

  Create extraction/p4_aggregation/meta_analyzer.py implementing:
  - P4-1: β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
  - P4-2: β̂_RE with DerSimonian-Laird τ²
  - P4-3: P_incl logistic formula
  - P4-3b: P_final with annotation adjustment (±1.0 cap)
  - 6-branch aggregation decision tree
  - σ²_structural computation from study_annotations_v1

  FRESHNESS (Module 5): Replace universal 1.5%/yr with:
    - Psychometrics: 0.0%/yr (supersession-only decay)
    - Population norms: 0.5%/yr, floor 0.90
    - Biological correlations: 0.5%/yr, floor 0.90
    - Edge evidence (intervention): 1.5%/yr, floor 0.70
    - Edge evidence (mechanism): 1.0%/yr, floor 0.80
    - Temporal kernels: 2.0%/yr, floor 0.70
    - Context priors: 1.0%/yr, floor 0.80
    Config: FRESHNESS_POLICIES dict in config.py.

  ESCALATION (Module 2): After IVW pooling, check each record:
    E1: w_i > 0.50 → escalate to Tier 1
    E2: k < 3 for edge → escalate all records
    E3: removing record flips sign → escalate
    E4: only cancer-matched study + k ≤ 5 → escalate
    E5: SE derivation ≥ L4 + w_i > 0.30 → escalate
    E6: forest plot entry not superseded → escalate
    Escalated records get unverified_inflation = 1.20×.

  Import SIGMA_SQ_DEFAULT, SIGMA_SQ_CEILING, P_INCLUSION_ADJ_CAP,
  FRESHNESS_POLICIES from config.py.

Output: 1 Python file (the most formula-dense extraction file)


PROMPT 3.3 — Prior Selector + Edge Writer
─────────────────────────────────────────
Context: E + F + A (SYS_EX lines 1280-1326)

Prompt:
  [paste manifest entries for prior_selector.py and edge_writer.py]
  [paste SYS_EX lines 1280-1326]

  Create:
  - extraction/p4_aggregation/prior_selector.py
    5-branch decision tree + 4-level fallback
  - extraction/p4_aggregation/edge_writer.py
    Write all 118 rows to edges_v1
    Gate P4-G1: all 118 edges have method assigned

Output: 2 Python files


PROMPT 3.4 — Publication Bias + Sufficiency + Deployment Validation
──────────────────────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 1394-1898)

Prompt:
  [paste manifest entries for p4b, p5, p6 files]
  [paste SYS_EX lines 1394-1534 (P4B)]
  [paste SYS_EX lines 1535-1786 (P5)]
  [paste SYS_EX lines 1787-1898 (P6)]

  Create:
  - extraction/p4b_publication_bias/egger.py
  - extraction/p4b_publication_bias/trim_fill.py
  - extraction/p4b_publication_bias/bias_aggregator.py
  - extraction/p5_sufficiency/coverage.py
  - extraction/p5_sufficiency/chain_vs_direct.py (§2.13)
  - extraction/p5_sufficiency/gap_analysis.py
    (discovery_score = |elasticity| × SE_eff)
  - extraction/p6_deployment/validation.py (16 rules)
    BLOCK → review_tasks row

Output: 7 Python files


PROMPT 3.5 — AG11 (InstrumentValidationAgent) + Extended Agent Prompts
─────────────────────────────────────────────────────────────────────
Context: E + F + A (SYS_EX lines 408-430) + M (SYS_EXTRACTION_ADDENDUM Parts 3-4)
        + P (Intelligence Maximization §4 — annotation emission rules per agent)
        + O (Routing Protocol §5 — LLM guardrails by paper type)

Prompt:
  [paste SYS_EXTRACTION_ADDENDUM.md Parts 3 and 4 (new agent + extensions)]
  [paste base_agent.py for reference]

  Create:
  - extraction/p1_extraction/agents/ag11_instrument_validation.py
    New agent following base_agent pattern. Extracts: CRONBACHS_ALPHA,
    FACTOR_LOADING, TEST_RETEST_RELIABILITY, INSTRUMENT_NAME, etc.
    (12 new SpanLabel types from addendum Part 3)
  - llm/prompts/ag11_instrument_validation.txt

  Update existing prompt templates to add extended SpanLabel types:
  - llm/prompts/ag03_cohort.txt (add POPULATION_COGNITIVE_MEAN/SD/etc.)
  - llm/prompts/ag05_stats_label.txt (add SUBGROUP_*/INTERACTION_*)
  - llm/prompts/ag06_exposure.txt (add DOSE_LEVEL/EFFECT_AT_DOSE/etc.)
  - llm/prompts/ag08_temporal.txt (add EFFECT_AT_TIMEPOINT/RECOVERY_*)

  Update shared/models/enums.py: Add all new SpanLabel types to
  SpanLabelEnum (~25 new values).

  Update P0 paper_type_classifier.py: Add 4 new paper subtypes
  (PSYCHOMETRIC_VALIDATION, NORMATIVE_COHORT, DOSE_RESPONSE_STUDY,
  LONGITUDINAL_FOLLOWUP).

  Update P0 mode_selection.py: Route new subtypes to appropriate
  agent configurations.

Output: 1 new agent + 1 new prompt + 4 updated prompts + enum updates
        + P0 routing updates


PROMPT 3.6 — Trust Boundary Extensions
──────────────────────────────────────
Context: E + F + SYS_EXTRACTION_ADDENDUM.md Part 5

Prompt:
  [paste SYS_EXTRACTION_ADDENDUM.md Part 5 (TB extensions)]
  [paste existing numeric_parser.py and consistency_checker.py]

  Extend:
  - extraction/tb_trust_boundary/numeric_parser.py
    Add parsing rules for psychometric values (α ∈ (0,1)),
    factor loadings, population norms, dose-response pairs,
    temporal curve points, subgroup interactions.
  - extraction/tb_trust_boundary/consistency_checker.py
    Add TB-PSYCH, TB-NORMS, TB-DOSE, TB-TEMPORAL, TB-SUBGROUP
    cross-validation rule sets per addendum.

Output: 2 updated Python files


PROMPT 3.7 — New Intermediate Evidence Tables
─────────────────────────────────────────────
Context: E + F + G + SYS_EXTRACTION_ADDENDUM.md Part 7

Prompt:
  [paste SYS_EXTRACTION_ADDENDUM.md Part 7]

  Add to database/schema/002_class_b_evidence.sql:
  - instrument_evidence_v1 (psychometric extractions per study)
  - population_norms_v1 (population cognitive scores per study)
  - temporal_evidence_v1 (timepoint × effect data per study)
  - dose_evidence_v1 (dose × effect data per study)
  - subgroup_evidence_v1 (subgroup interaction data per study)

  All 5 share base columns: id, study_id (FK), extraction_run_id (FK),
  created_at, provenance_status, provenance_ref.
  Plus type-specific columns per addendum Part 7.

  Update shared/models/tables.py with ORM models for new tables.

Output: Updated SQL schema + updated ORM models


PROMPT 3.8 — Compilers 1-3 (Psychometric, Prior, Temporal)
──────────────────────────────────────────────────────────
Context: E + F + SYS_EXTRACTION_ADDENDUM.md Part 6 (Compilers 1-3)
         + B (SYS_ALG lines for instruments_v1, context_matched_priors,
              intervention_kernels, recovery_params schemas)

Prompt:
  [paste SYS_EXTRACTION_ADDENDUM.md Part 6, Compilers 1-3]

  Create:
  - extraction/p7_compilers/psychometric_compiler.py
    Reads instrument_evidence_v1 → weighted mean of α by N →
    derives b_k → writes instruments_v1 {a_k, b_k, alpha_k}
    Gate P7-G1: each α must be based on N≥20 study.

  - extraction/p7_compilers/prior_compiler.py
    Reads population_norms_v1 → z-scores → weighted mean per node →
    builds Σ_prior → Λ_prior via Cholesky → writes context_matched_priors_v1
    Gate P7-G2: Λ_prior must be positive definite.

  - extraction/p7_compilers/temporal_compiler.py
    Reads temporal_evidence_v1 → fits trapezoidal kernel via IVW-weighted
    timepoints → fits stretched exponential for recovery →
    writes intervention_kernels_v1 + recovery_params_v1
    Gate P7-G3: onset < peak; r_∞ ∈ (0,1]; τ_R > 0.

  Import ALL constants from config.py. Use scipy for curve fitting.

Output: 3 Python files (highest-impact compilers)


PROMPT 3.9 — Compilers 4-6 (Dose-Response, Modifier, Synergy)
─────────────────────────────────────────────────────────────
Context: E + F + SYS_EXTRACTION_ADDENDUM.md Part 6 (Compilers 4-6)

Prompt:
  [paste SYS_EXTRACTION_ADDENDUM.md Part 6, Compilers 4-6]

  Create:
  - extraction/p7_compilers/dose_response_compiler.py
    Reads dose_evidence_v1 → fits Hill/Emax via NLLS →
    writes dose_response_params_v1 {E0, Emax, ED50, hill}
    Gate P7-G4: Emax same sign as effect direction; ED50 > 0.

  - extraction/p7_compilers/modifier_compiler.py
    Reads subgroup_evidence_v1 → pools interactions via IVW →
    converts to multiplicative modifier → writes modifier_registry_v1
    Clamp to [0.7, 1.5] per ALG-C4b guardrails.

  - extraction/p7_compilers/synergy_compiler.py
    Reads factorial trial data → computes γ coefficient →
    writes synergy_registry_v1
    Gate P7-G6: γ ∈ (-1, 1).

Output: 3 Python files


PROMPT 3.10 — Pipeline Extension for Full-Spectrum Extraction
────────────────────────────────────────────────────────────
Context: E + F + M (SYS_EXTRACTION_ADDENDUM Part 8) + pipeline.py
        + Q (Treatment Protocol Part 2-3 — component inventory → agent activation)
        + O (Routing Protocol §2 — meta-analysis multi-product routing)

Prompt:
  [paste pipeline.py (existing)]
  [paste SYS_EXTRACTION_ADDENDUM.md Part 8]
  [paste Treatment Protocol Part 2 Stage 2 (component inventory → activation)]
  [paste Routing Protocol §2.1-2.5 (MA product routing)]
  [paste Routing Protocol §9.2 (MA product extraction decision tree)]

  Update extraction/pipeline.py to:
  1. After P0 classification, run component_inventory.py to detect
     ALL information types (9 parameter + 9 intelligence components).
     Component inventory drives which agent extensions activate.
  2. Route papers through AG11 when paper_subtype is
     PSYCHOMETRIC_VALIDATION or component INSTRUMENT_PSYCHOMETRICS detected.
  3. Activate AG03-EXT, AG06-EXT, AG08-EXT, AG05-EXT based on
     component inventory (not just paper subtype).
  4. For meta-analyses: extract ALL products (1-6) per Routing Protocol §2.
     Route Product 3 (included studies) → acquisition_queue_v1.
     Set meta_source_flag on all MA-derived edge_evidence_v1 rows.
  5. For umbrella reviews: BLOCK numeric extraction (Routing Protocol §2.5).
  6. After P6 validation passes, run P7 compilers.
  7. Report: compilation results per compiler (rows updated,
     gates passed/failed, provenance_status counts)
     Run all 6 compilers. Each reads from its intermediate evidence
     table and writes to the corresponding Class A table.
  4. Report: compilation results per compiler (rows updated,
     gates passed/failed, provenance_status counts)

  Update scripts/run_extraction.py to report full-spectrum results:
  edge evidence rows + instrument compilations + prior compilations +
  kernel compilations + dose compilations + modifier updates.

Output: 2 updated Python files


PROMPT 3.11 — Source Adapter Base + PubMed + Europe PMC
───────────────────────────────────────────────────────
Context: E + F + SYS_EX lines 1983-2010 (EX-ACQ-RET)
         + AUTOMATED_RETRIEVAL_PLAN.md Part 4

Prompt:
  [paste AUTOMATED_RETRIEVAL_PLAN.md Part 4 (adapter specs)]

  Create retrieval/adapters/base.py — abstract SourceAdapter with:
    search(query, filters, max_results) → CandidateMetadata[]
    fetch_metadata(identifier) → PaperMetadata
    check_fulltext(doi_or_pmid) → FullTextAvailability
    retrieve_fulltext(identifier) → bytes | None
    health() → AdapterStatus

  Create retrieval/adapters/pubmed.py:
    Uses NCBI E-utilities (esearch.fcgi, efetch.fcgi)
    API key from env NCBI_API_KEY (optional, affects rate limit)
    Rate limit: 3 req/s without key, 10 req/s with key
    Parses XML responses into CandidateMetadata
    Supports PubMed Boolean query syntax
    Handles pagination (retstart, retmax)

  Create retrieval/adapters/europe_pmc.py:
    Search endpoint + fullTextXML/{pmcid} for OA articles
    Returns structured full text when available
    Converts XML to clean text sections for Canonical Reader

  Create retrieval/models.py with Pydantic models:
    CandidateMetadata, PaperMetadata, FullTextAvailability,
    RetrievalResult, AdapterStatus

Output: 4 Python files


PROMPT 3.12 — Crossref + OpenAlex + Unpaywall Adapters
──────────────────────────────────────────────────────
Context: E + F + AUTOMATED_RETRIEVAL_PLAN.md Part 4

Prompt:
  Create retrieval/adapters/crossref.py:
    /works?query=... for search, /works/{doi} for lookup
    Polite pool: include mailto in User-Agent
    Normalize to CandidateMetadata schema

  Create retrieval/adapters/openalex.py:
    /works?search=... for discovery
    Related works expansion for citation graph
    Polite pool with email

  Create retrieval/adapters/unpaywall.py:
    /v2/{doi}?email=... for OA route resolution
    Returns best_oa_location URL for PDF download

Output: 3 Python files


PROMPT 3.13 — Query Generator + node_search_terms_v1
────────────────────────────────────────────────────
Context: E + F + G (table schemas) + AUTOMATED_RETRIEVAL_PLAN.md Part 3

Prompt:
  Add node_search_terms_v1 to database/schema/001_class_a_knowledge.sql:
    node_id (FK), term (TEXT), term_type (ENUM: primary, synonym,
    abbreviation, mesh_heading), active (BOOL)

  Create retrieval/query_generator.py:
    Reads: edge_relations_definitions_v1, biomarker_node_definitions_v1,
           instrument_definitions_v1, action_catalog_v1,
           correlation_registry_v1, node_search_terms_v1

    For each of the 7 workstreams, generates APSQueryRequest[] using
    the template patterns in AUTOMATED_RETRIEVAL_PLAN.md Part 3.

    Key methods:
      generate_edge_queries(edge_ids=None) → APSQueryRequest[]
      generate_instrument_queries(inst_ids=None) → APSQueryRequest[]
      generate_norms_queries() → APSQueryRequest[]
      generate_prior_queries(contexts) → APSQueryRequest[]
      generate_recovery_queries() → APSQueryRequest[]
      generate_kernel_queries() → APSQueryRequest[]
      generate_correlation_queries() → APSQueryRequest[]
      generate_all() → APSQueryRequest[]

    Uses node_search_terms_v1 for synonym expansion in queries.
    All constants from shared/config.py.

Output: 1 SQL addition + 1 Python file


PROMPT 3.14 — Search Coordinator + APS Scorer + Full-Text Retriever
───────────────────────────────────────────────────────────────────
Context: E + F + SYS_EX lines 1899-2013 (full EX-ACQ chain card)
         + AUTOMATED_RETRIEVAL_PLAN.md Parts 4-6

Prompt:
  Create retrieval/search_coordinator.py:
    Takes APSQueryRequest[], dispatches to source adapters,
    collects CandidateMetadata[], deduplicates against
    study_registry_v1 (DOI + PMID match), returns unique candidates.

  Create retrieval/aps_scorer.py:
    Implements EX-ACQ-APS formula:
    APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch
          + 0.15·Recency + 0.10·SourceQuality
    Author-gap boost: APS × 1.5 (capped at 1.0)
    Gate: APS ≥ 0.40 → DISPATCH, < 0.40 → DEFER
    All constants from shared/config.py

  Create retrieval/fulltext_retriever.py:
    Source priority: Europe PMC → Unpaywall → abstract_only
    Downloads PDF to data/retrieval_cache/{hash}.pdf
    Writes/updates acquisition_queue_v1 rows
    Respects rate limits per adapter

  Create retrieval/config.py:
    API keys (from env), rate limits, budget caps,
    source priority, cache paths, max papers/day

Output: 4 Python files


PROMPT 3.15 — Acquisition Scheduler + Manual Upload + CLI Scripts
────────────────────────────────────────────────────────────────
Context: E + F + AUTOMATED_RETRIEVAL_PLAN.md Parts 5, 7, 9

Prompt:
  Create retrieval/acquisition_scheduler.py:
    Full acquisition cycle:
    1. query_generator.generate_all()
    2. search_coordinator.search(queries)
    3. aps_scorer.score(candidates)
    4. fulltext_retriever.retrieve(scored, budget)
    5. Feed retrieved PDFs to extraction pipeline
    6. Report results summary
    Modes: single_run, continuous, dry_run
    Budget-aware: stops when daily cap reached

  Create retrieval/manual_upload_watcher.py:
    Watches data/manual_uploads/ for new files
    PDFs → register + feed to EX-P0
    CSVs → validate against template → write to evidence table
    search_overrides → fetch specific DOIs → feed to pipeline

  Create scripts/run_acquisition.py:
    --workstream {edge|instruments|norms|priors|recovery|kernels|
                  correlations|all}
    --max-papers N (default: 50)
    --dry-run (show queries, don't fetch)
    --manual (process manual_uploads/)
    --cycle (full: search + retrieve + extract + compile)

  Create scripts/run_manual_import.py:
    --type {pdf|csv|override}
    --validate-only

  Create CSV templates in data/templates/ (6 templates per
  AUTOMATED_RETRIEVAL_PLAN.md Part 5)

Output: 4 Python files + 6 CSV templates


═══════════════════════════════════════════════════════════════════════════
 PHASE 4: AUTOMATED + MANUAL EXTRACTION
 The system finds papers AND you can drop your own in.
 START THIS WHILE BUILDING PHASE 5 (algorithm) IN PARALLEL.
 Run validate_deployment_readiness.py (G0) to check coverage.
═══════════════════════════════════════════════════════════════════════════

Phase 4 is RUNNING the system, not building code. Two parallel tracks:

TRACK A — AUTOMATED (system finds papers):
  python scripts/run_acquisition.py --workstream instruments --max-papers 10 --cycle
  python scripts/run_acquisition.py --workstream edge --max-papers 20 --cycle
  python scripts/run_acquisition.py --workstream all --max-papers 50 --cycle

TRACK B — MANUAL (you supplement):
  Drop PDFs into data/manual_uploads/pdfs/
  Fill CSV templates in data/manual_uploads/structured/
  python scripts/run_manual_import.py --type pdf

TRACK C — ALGORITHM (parallel with extraction):
  Build Phase 5 (ALG-A→F) while extraction populates evidence tables.
  Re-run algorithm with real parameters when extraction delivers.

ITERATION:
  1. Run automated acquisition
  2. Review extraction quality, tune prompts
  3. Supplement with manual uploads for paywalled papers
  4. Run G0: python scripts/validate_deployment_readiness.py
  5. If NOT_READY → run more cycles. If READY → validate algorithm.

PROMPT 4.DEBUG — Fix Extraction Issue
  Context: E + F + A (relevant chain lines) + the error output
  Prompt: "The extraction pipeline failed at [chain/subsystem] with
  [error]. Here is the relevant spec section [paste]. Here is the
  current code [paste]. Fix the issue while maintaining spec fidelity."


═══════════════════════════════════════════════════════════════════════════
 PHASE 5: ALGORITHM (the actual science)
 Attach: E + F + B (SYS_ALGORITHM, relevant lines)
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 Anchor: Re-read config.py + enums.py + intermediate_states.py first
 Tests: MANDATORY for Prompts 5.3 (Bayesian update) and 5.4 (MC sampler)
        Include hand-computed expected values in test cases
 After phase: Run VERIFICATION PROMPT V5, MANUALLY REVIEW bayesian_update.py
              and mc_sampler.py before committing
 *** THIS IS THE HIGHEST-RISK PHASE. DO NOT SKIP MANUAL REVIEW. ***
═══════════════════════════════════════════════════════════════════════════

PROMPT 5.1 — Graph Assembly (ALG-A)
──────────────────────────────────
Context: E + F + B (SYS_ALG lines 410-1000)

Prompt:
  [paste manifest entry for graph_object.py]
  [paste SYS_ALG lines 410-1000 (entire ALG-A chain card)]

  Create all files in algorithm/chain_a_graph/:
  - node_loader.py (63 nodes → hierarchy)
  - edge_loader.py (118 edges → B̂ matrix, sparse)
  - instrument_loader.py (23 instruments → H matrix, Σ_ε)
  - spectral_validator.py (compute ρ(B). If ≥ 1 → ABORT)
  - graph_object.py (assemble GraphObject dataclass)

  Use numpy/scipy for matrix operations.
  The spectral radius check is NON-NEGOTIABLE. If ρ(B) ≥ 1, the
  system is mathematically unstable and cannot produce valid inference.

Output: 5 Python files


PROMPT 5.2 — Evidence Compilation + Model Freeze (ALG-B)
───────────────────────────────────────────────────────
Context: E + F + B (SYS_ALG lines 1004-1545)

Prompt:
  [paste manifest entry for evidence_compiler.py]
  [paste SYS_ALG lines 1004-1545 (entire ALG-B chain card)]

  Create algorithm/chain_b_evidence/ files:
  - evidence_compiler.py (B1-B6: IVW, 7-layer SE, priors, P_incl,
    constraints, chain validation — mirrors EX-P3/P4 but is the
    AUTHORITATIVE compilation)
  - frozen_state.py (B7: freeze model → FrozenModelState with
    frozen_model_version_id. Pin at session start per v1 ops #7)

Output: 2 Python files


PROMPT 5.3 — Bayesian Update (ALG-C) *** THE CORE ***
─────────────────────────────────────────────────────
Context: E + F + B (SYS_ALG lines 1547-2012)

Prompt:
  [paste manifest entry for bayesian_update.py — flagged as MOST
   IMPORTANT FILE]
  [paste SYS_ALG lines 1547-2012 (entire ALG-C chain card)]

  Create all files in algorithm/chain_c_posterior/:

  - prior_loader.py (C1: 4-level fallback from context_matched_priors)
  - observation_mapper.py (C2: questionnaire → node observations,
    instrument noise model, cancer validation multiplier,
    temporal weighting with 90-day exclusion)
  - bayesian_update.py (C3: THE BAYESIAN ENGINE)
    C3a: Information-form rank-1 updates (commutative, O(1) per obs)
      Λ_post ← Λ_post + (b²_k/σ²_{y,k}) · eᵢeᵢᵀ
      η_post ← η_post + (b_k(y_k−a_k)/σ²_{y,k}) · eᵢ
    C3b: Posterior recovery via Cholesky
      θ̂ = Λ_post⁻¹ · η_post
    C3c: Three-level fusion accounting (L1/L2/L3 per node)
    C3d: Variance reduction for next-best observation
  - modifier_application.py (C4: 109 modifier rules,
    individual [0.7,1.5], cumulative [0.5,2.0] guardrails)
  - posterior_writer.py (C5: → state_snapshots_v1)

  Use numpy/scipy. Cholesky for matrix inversion. This must be
  MATHEMATICALLY EXACT — test against hand calculations.

Output: 5 Python files


PROMPT 5.4 — Monte Carlo Simulation (ALG-D)
───────────────────────────────────────────
Context: E + F + B (SYS_ALG lines 2015-2540)

Prompt:
  [paste manifest entry for mc_sampler.py — MOST COMPUTE-INTENSIVE]
  [paste SYS_ALG lines 2015-2540 (entire ALG-D chain card)]

  Create all files in algorithm/chain_d_simulation/:

  - intervention_loader.py (load kernels, synergies, dose-response)
  - mc_sampler.py (D1-D2: 10K MC draws)
    Per draw: sample β ~ N(β̂, SE²), sample include ~ Bern(P_incl),
    sample θ₀ ~ N(θ̂, Σ_post), apply intervention (do-operator),
    propagate through DAG: Δθ = (I-B)⁻¹ × intervention,
    compute ΔC (composite effect)
    SAFE_A = mean(ΔC), SAFE_B = normed, CrI_95 = quantiles
    MUST: accept random seed parameter for reproducibility
  - safety_checker.py (D3: contraindication_rules_v1 evaluation)
  - ranker.py (D4-D6: rank by E[SAFE_B], stability, CrI)
    Write: intervention_rankings_v1, decision_trace_v1

  Use numpy vectorization for performance. 63×63 × 10K draws.

Output: 4 Python files


PROMPT 5.5 — Temporal Prediction (ALG-E)
───────────────────────────────────────
Context: E + F + B (SYS_ALG lines 2543-2974)

Prompt:
  [paste manifest entry for trajectory_simulator.py]
  [paste SYS_ALG lines 2543-2974 (ALG-E chain card)]

  Create:
  - algorithm/chain_e_temporal/trajectory_simulator.py
    Timepoints: 0, 4, 8, 12, 26, 52 weeks
    Apply intervention kernels (onset, peak, decay)
  - algorithm/chain_e_temporal/recovery_model.py
    Post-cessation recovery curves from recovery_params_v1
  Write: temporal_trajectories_v1

Output: 2 Python files


PROMPT 5.6 — Analytics: Composite + Variance + EVSI (ALG-F)
──────────────────────────────────────────────────────────
Context: E + F + B (SYS_ALG lines 2977-3580)

Prompt:
  [paste manifest entries for composite_scorer.py,
   variance_decomposer.py, evsi.py]
  [paste SYS_ALG lines 2977-3580 (ALG-F chain card)]

  Create all files in algorithm/chain_f_analytics/:
  - composite_scorer.py (CRCI = severity-weighted mean, 11 subdomains,
    population-normed percentile)
  - population_norming.py (percentile vs normative distribution)
  - variance_decomposer.py (5-source: literature, measurement,
    structural, patient, stochastic)
  - evsi.py (Expected Value of Sample Information, nested MC 500×1000,
    discovery_score = |elasticity| × SE_eff)

Output: 4 Python files


═══════════════════════════════════════════════════════════════════════════
 PHASE 6: RUNTIME + PRESENTATION
 Attach: E + F + C (SYS_RUNTIME) or D (SYS_PRESENTATION)
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1 to every prompt
 Anchor: Re-read config.py + enums.py + intermediate_states.py + output_contracts.py
 After phase: Run VERIFICATION PROMPT V6, commit if passes
═══════════════════════════════════════════════════════════════════════════

PROMPT 6.1 — Runtime Session + Schedule + Questions + Report
───────────────────────────────────────────────────────────
Context: E + F + C (SYS_RT lines 1-752, entire spec — it's only 752 lines)

Prompt:
  [paste manifest entries for all runtime/ files]
  [paste SYS_RUNTIME_COMPLETE.md in full — it fits easily]

  Create all files in runtime/:
  - session.py (lifecycle, pin frozen_model_version_id at start,
    orchestrate C→D→E→F→G→H→I, write recommendation_runs_v1)
  - schedule_generator.py (RT-G: generate intervention combos,
    evaluate via ALG-D, apply constraints, write schedule_plans_v1)
  - adaptive_questions.py (RT-H: IG-based question selection,
    ΔVar(Y|X) = Cov²/Var, stop when IG < threshold)
  - report_assembler.py (RT-I: package all outputs into
    RecommendationReport, link provenance to paper-level evidence)

Output: 4 Python files


PROMPT 6.2 — Presentation: All Visualization Components
───────────────────────────────────────────────────────
Context: E + F + D (SYS_PRES lines 1-541, entire spec)

Prompt:
  [paste manifest entries for all presentation/ files]
  [paste SYS_PRESENTATION_COMPLETE.md in full — it fits easily]

  Create all files in presentation/:
  - crci_dashboard.py (PAT1: score gauge + radar chart, 11 subdomains)
  - intervention_cards.py (PAT2: ranked cards with dose, CrI, safety)
  - trajectory_plot.py (PAT3/PAT6: time-series with CrI bands)
  - variance_pie.py (PAT4: 5-slice decomposition)
  - dag_viz.py (SCI2: full 63-node graph with edge weights)
  - evidence_browser.py (SCI1: 118 edges with study drill-down)
  - provenance_viewer.py (SCI3: claim → edge → study → paper)

  Use matplotlib/plotly for charts. Keep it functional — these
  render to files or notebook output for the science submission.

Output: 7 Python files


═══════════════════════════════════════════════════════════════════════════
 PHASE 7: INTEGRATION + CLI SCRIPTS
 Attach: E + F + relevant specs as needed
 Enforcement: Append CODE_QUALITY_ENFORCEMENT.md Section 1
 After phase: Run V-FINAL (end-to-end wiring audit from
              CODE_QUALITY_ENFORCEMENT.md Section 2)
 *** V-FINAL IS THE LAST GATE BEFORE THE SYSTEM IS COMPLETE ***
═══════════════════════════════════════════════════════════════════════════

PROMPT 7.1 — CLI Scripts
────────────────────────
Context: E + F

Prompt:
  Create the CLI entry points in scripts/:
  - run_extraction.py: accepts PDF paths (glob-able), runs pipeline.py
    for each, reports results summary
  - run_build.py: runs ALG-A + ALG-B, freezes model, reports stats
  - run_session.py: accepts --patient-id, runs runtime session,
    outputs RecommendationReport
  - seed_database.py: wrapper for database/seed_loader.py
  - validate_model.py: runs spectral check + P6 validation
  - validate_deployment_readiness.py: implements G0 gate from
    PARAMETER_PROVENANCE_AND_CURATION.md Part 5. Checks:
    G0-1 (measurement model completeness),
    G0-2 (minimum 30 edges parameterized),
    G0-3 (≥3 curated priors),
    G0-4 (spectral radius with real weights),
    G0-5 (no APPROXIMATE in patient's critical path).
    Output: READY or NOT_READY with specific failing checks.

Output: 5 Python files


PROMPT 7.2 — End-to-End Test
───────────────────────────
Context: E + F + A + B + C

Prompt:
  Create tests/test_end_to_end/test_full_pipeline.py that:
  1. Seeds test database with minimal Class A data (3 nodes, 3 edges)
  2. Feeds 1 test paper through extraction → evidence row
  3. Compiles edges_v1 (3 edges)
  4. Runs patient session with mock questionnaire
  5. Asserts: CompositeScore exists, SchedulePlan exists,
     TemporalTrajectory has 6 timepoints,
     all outputs have valid provenance
  6. Asserts: changing 1 edge parameter → different recommendation

Output: 1 test file


═══════════════════════════════════════════════════════════════════════════
 TOTAL PROMPT COUNT
═══════════════════════════════════════════════════════════════════════════

Phase 0: 8 prompts (foundation)
Phase 1: 6 prompts (LLM client + extraction skeleton)
Phase 2: 3 prompts (trust boundary + harmonization + calibration)
Phase 3: 15 prompts (aggregation + compilers + full-spectrum + retrieval)
Phase 4: 0 prompts (running the automated pipeline + manual supplements)
Phase 5: 6 prompts (algorithm — the science)
Phase 6: 2 prompts (runtime + presentation)
Phase 7: 2 prompts (integration + CLI)
────────────────────────────────────────
TOTAL: 42 prompts to build the entire v1 system

+ Debug prompts as needed during Phase 4 iteration


═══════════════════════════════════════════════════════════════════════════
 CONTEXT ATTACHMENT CHEAT SHEET
═══════════════════════════════════════════════════════════════════════════

ALWAYS attach (every prompt):
  ✓ IMPLEMENTATION_BLUEPRINT_v1.1.md (E)
  ✓ FILE_CONTEXT_MANIFEST.md (F)
  ✓ CODE_QUALITY_ENFORCEMENT.md Section 1 (enforcement rules)

From Phase 1 onward, always re-read before implementing:
  ✓ shared/config.py (anchor — naming conventions + constants)
  ✓ shared/models/enums.py (anchor — vocabulary)
  ✓ shared/models/intermediate_states.py (anchor — types)

Phase 0 (database/shared) — also attach:
  ✓ 05_TABLE_SCHEMAS.md (G)
  ✓ 06_FK_WIRING_MAP.md (H)
  ✓ 11_CONTROLLED_VOCABULARIES.md (I) — for enums prompt only

Phase 1-4 (extraction) — also attach:
  ✓ SYS_EXTRACTION_COMPLETE.md (A) — relevant lines per manifest

Phase 5 (algorithm) — also attach:
  ✓ SYS_ALGORITHM_COMPLETE.md (B) — relevant lines per manifest

Phase 6 (runtime) — also attach:
  ✓ SYS_RUNTIME_COMPLETE.md (C) — entire doc fits easily
  ✓ SYS_PRESENTATION_COMPLETE.md (D) — entire doc fits easily

Integration / debugging — also attach:
  ✓ Whichever system spec is relevant
  ✓ The actual code file that has the bug
  ✓ CONFLICT_ANALYSIS.md (J) — if hitting σ²_struct / P_inclusion /
    acquisition_queue issues specifically


IF CONTEXT WINDOW IS TOO SMALL:
  Priority order: F (Manifest) → relevant spec lines only (not full
  spec) → E (Blueprint) → code of upstream/downstream files
  
  The manifest tells you exactly which 50-100 spec lines matter.
  Paste THOSE LINES, not the entire 2,764-line spec.


═══════════════════════════════════════════════════════════════════════════
 EXPECTED OUTPUT FILE COUNT PER PHASE
═══════════════════════════════════════════════════════════════════════════

Phase 0: ~12 files (5 SQL + seed_loader + enums + config +
         intermediate_states + output_contracts + db + tables +
         validators)
Phase 1: ~18 files (client + cost_tracker + schemas + pipeline +
         4 triage + canonical_reader + base_agent + 10 agents +
         reconciliation + ATB) + ~12 prompt templates
Phase 2:  9 files (2 trust boundary + 5 harmonization + 2 P3)
Phase 3: 11 files (2 P4-EG/DCR + 1 meta_analyzer + 2 prior/writer +
         3 P4B + 3 P5 + 1 P6)
Phase 5: 15 files (5 ALG-A + 2 ALG-B + 5 ALG-C + 4 ALG-D +
         2 ALG-E + 4 ALG-F) — wait some of these overlap, actual ~20
Phase 6:  11 files (4 runtime + 7 presentation)
Phase 7:  6 files (5 scripts + 1 test)
──────────────────────────
TOTAL: ~70 code files + ~12 prompt templates + 5 SQL schemas
       (matches Blueprint estimate)

═══════════════════════════════════════════════════════════════════════════
END
═══════════════════════════════════════════════════════════════════════════
