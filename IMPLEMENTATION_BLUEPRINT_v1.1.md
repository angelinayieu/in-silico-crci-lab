═══════════════════════════════════════════════════════════════════════════
 CRCI SYSTEM — IMPLEMENTATION BLUEPRINT v1.1
 Date: 2026-02-24
 Focus: SCIENCE PROJECT FIRST, production automation later
═══════════════════════════════════════════════════════════════════════════

PRIORITY STATEMENT

  This system exists to produce scientifically rigorous CRCI predictions.
  Extraction is the means, not the end. The model, the inference, and the
  recommendations are what get submitted and published.

  v1 = Working prediction system with operator-driven extraction.
       You feed papers. It extracts. It compiles. It predicts. You publish.

  v2 = Autonomous continuous research engine with background operation.
       Scheduled acquisition, budget controllers, worker pools, queues,
       observability dashboards, review SLAs, cloud deployment.

  Do NOT build v2 infrastructure before v1 predictions work.


REFERENCE DOCUMENTS:
  SYS_EXTRACTION_COMPLETE.md   (2,764 lines — 12 chains, ~64 subsystems)
  SYS_ALGORITHM_COMPLETE.md    (4,418 lines — 6 chains, ~31 subsystems)
  SYS_RUNTIME_COMPLETE.md      (752 lines — 4 chains, ~11 subsystems)
  SYS_PRESENTATION_COMPLETE.md (541 lines — 3 branches, ~15 subsystems)

SOURCE PAPERS:
  Primary: CRCI Bayesian Causal Model paper (§2.1-§2.22, §4, §6)
  Supporting: Greenland 2005, VanderWeele & Arah 2011, Lash Fox Fink 2009,
    DerSimonian & Laird 1986, Poynard 2002, GRADE (Guyatt 2008)


═══════════════════════════════════════════════════════════════════════════
 PART 1: WHAT V1 ACTUALLY NEEDS TO DO
═══════════════════════════════════════════════════════════════════════════

V1 must produce these outputs for the science project:

  1. COMPILED EVIDENCE BASE (edges_v1, 118 rows)
     Populated from ~50-200 extracted papers
     Each edge has: β̂, SE_eff, P_inclusion, prior_type, k, method
     + σ²_structural (annotation-informed where available)

  2. PATIENT INFERENCE (per session)
     Input: questionnaire responses
     Output: posterior θ̂ over 63 nodes
     Via: Bayesian update (Kalman-like, the core engine)

  3. INTERVENTION RANKINGS (per patient)
     MC simulation (10K draws) → SAFE_A, SAFE_B per intervention
     Ranked by expected benefit with credible intervals

  4. CRCI COMPOSITE SCORE
     Severity-weighted mean across 11 subdomains
     Population-normed percentile

  5. VISUALIZATIONS for the science submission
     DAG visualization, evidence browser, intervention cards,
     trajectory plots, variance decomposition

V1 does NOT need:
  - Autonomous paper discovery/retrieval (you find papers manually)
  - Background scheduled jobs (you trigger extraction manually)
  - Queue broker, worker pools, or service topology
  - Budget controllers or capacity caps
  - Source adapter abstractions for 8 APIs
  - Observability dashboards or SLO monitoring
  - Kubernetes, Terraform, or multi-environment deployment
  - Human review SLA management
  - Model publish locks or frozen model versioning protocol

Those are all real needs — for v2.


═══════════════════════════════════════════════════════════════════════════
 PART 2: V1 END-TO-END DATA FLOW
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│  YOU (operator)                                                      │
│  ├── Collect ~50-200 papers from PubMed/Google Scholar manually      │
│  ├── Download PDFs to a local folder                                 │
│  └── Run: python run_extraction.py papers/*.pdf                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  EXTRACTION (EX-P0→P6)  │  Runs locally, paper by paper
              │  Claude API for agents  │  ~2-5 min per paper
              │  Deterministic parsing  │  Results to local Postgres
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  COMPILATION (ALG-A,B)  │  Runs once after extraction
              │  Graph assembly         │  Build edges_v1 (118 rows)
              │  Evidence compilation   │  Spectral validation
              │  Model freeze           │  ~1 min total
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  INFERENCE (ALG-C→F)    │  Runs per patient/session
              │  Bayesian update        │  Input: questionnaire
              │  MC simulation (10K)    │  Output: recommendations
              │  Composite scoring      │  ~30-60 seconds
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  PRESENTATION           │  Renders outputs
              │  DAG viz, charts,       │  For paper/submission
              │  intervention cards     │
              └─────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 PART 3: V1 ARCHITECTURE — DIRECTORY TREE (simplified)
═══════════════════════════════════════════════════════════════════════════

crci/
├── README.md
├── pyproject.toml
├── .env                                    # Claude API key, DB connection
│
├── docs/
│   ├── SYS_EXTRACTION_COMPLETE.md          # ALWAYS reference during EX impl
│   ├── SYS_ALGORITHM_COMPLETE.md           # ALWAYS reference during ALG impl
│   ├── SYS_RUNTIME_COMPLETE.md             # ALWAYS reference during RT impl
│   ├── SYS_PRESENTATION_COMPLETE.md        # ALWAYS reference during PRES impl
│   └── papers/                             # Source papers
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ DATABASE + SHARED (build first)
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── database/
│   ├── schema/
│   │   ├── 001_class_a_knowledge.sql       # 21 tables (nodes, edges, etc.)
│   │   ├── 002_class_b_evidence.sql        # 7 tables (evidence, annotations)
│   │   ├── 003_class_c_compiled.sql        # edges_v1 (118 rows)
│   │   ├── 004_class_d_reference.sql       # question_bank, templates
│   │   ├── 005_class_e_output.sql          # recommendation_runs, schedules, etc.
│   │   ├── 006_fk_constraints.sql          # All FK relationships
│   │   └── 007_ops_tables.sql              # review_tasks (simple HITL queue),
│   │                                       # policy_snapshots (config per run)
│   │
│   ├── seeds/                              # CSV files for ALL Class A tables
│   │   ├── nodes.csv                       # 63 nodes
│   │   ├── edges.csv                       # 118 edges (skeleton)
│   │   ├── instruments.csv                 # 23 instruments
│   │   ├── pathway_map.csv                 # 21 pathways
│   │   ├── modifier_registry.csv           # 109 modifiers
│   │   ├── context_matched_priors.csv      # 33 priors
│   │   └── ... (all other Class A seeds)
│   │
│   └── seed_loader.py                      # CSV → database, validate FKs
│
├── shared/
│   ├── models/
│   │   ├── tables.py                       # ORM for all 56 tables
│   │   ├── intermediate_states.py          # All intermediate state dataclasses
│   │   ├── output_contracts.py             # CompositeScore, SchedulePlan, etc.
│   │   └── enums.py                        # All controlled vocabularies
│   ├── config.py                           # ALL constants from specs
│   ├── db.py                               # Postgres connection
│   └── validators.py                       # Cross-table validation
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ LLM LAYER (from ops doc — v1 minimal version)
│ Essential because extraction agents need Claude to work reliably.
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── llm/
│   ├── __init__.py
│   ├── client.py                           # Single provider client (Claude)
│   │                                       # Wraps: API call, retry on timeout,
│   │                                       # structured JSON response parsing,
│   │                                       # token counting, cost logging
│   │                                       # NOT a multi-provider gateway yet
│   │                                       # Just: call Claude, parse response,
│   │                                       # retry if transient failure, log cost
│   ├── prompts/                            # Prompt templates per agent
│   │   ├── ag01_metadata.txt
│   │   ├── ag02_design.txt
│   │   ├── ... (one per agent)
│   │   └── ag10_strategic.txt
│   ├── response_schemas.py                 # Expected JSON schemas for validation
│   └── cost_tracker.py                     # Simple: log tokens + estimated $
│                                           # Just a CSV/DB table, not a budget
│                                           # controller. Know what you're spending.
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ EXTRACTION (operator-driven, not autonomous)
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── extraction/
│   ├── __init__.py
│   ├── pipeline.py                         # Main orchestrator: P0 → P6
│   │                                       # Called by run_extraction.py
│   │                                       # Processes one paper at a time
│   │                                       # Checkpoint/resume per agent + chain
│   │                                       # Logs extraction_run + policy snapshot
│   │
│   ├── p0_triage/
│   │   ├── __init__.py
│   │   ├── pdf_ingestion.py                # PDF → text (pypdf2/pdfplumber)
│   │   ├── relevance_screening.py          # Is this CRCI-relevant?
│   │   ├── paper_type_classifier.py        # 23 subtypes (via Claude)
│   │   └── mode_selection.py               # SHALLOW/STANDARD/DEEP
│   │
│   ├── p1_extraction/
│   │   ├── __init__.py
│   │   ├── canonical_reader.py             # PaperMap: read once, share
│   │   ├── agents/
│   │   │   ├── base_agent.py               # Common: call llm/client.py,
│   │   │   │                               # receive PaperMap section,
│   │   │   │                               # return typed output
│   │   │   ├── ag01_metadata.py
│   │   │   ├── ag02_design.py
│   │   │   ├── ag03_cohort.py
│   │   │   ├── ag04_outcome.py
│   │   │   ├── ag05_stats_label.py         # CRITICAL: numeric extraction
│   │   │   ├── ag06_exposure.py
│   │   │   ├── ag07_mediator.py
│   │   │   ├── ag08_temporal.py
│   │   │   ├── ag09_reconciliation.py      # Rule-based, no LLM
│   │   │   └── ag10_strategic_intel.py     # Annotations from Discussion
│   │   ├── reconciliation.py               # Dedup, conflict, merge annotations
│   │   └── annotation_trust_boundary.py    # 6 ATB rules → write annotations
│   │                                       # High-impact rejections → review_tasks
│   │
│   ├── tb_trust_boundary/
│   │   ├── numeric_parser.py               # SpanLabel → TypedNumericValue
│   │   └── consistency_checker.py          # Cross-field validation
│   │                                       # Writes edge_evidence_v1
│   │
│   ├── p2_harmonization/
│   │   ├── sd_standardization.py           # SD_SD anchors
│   │   ├── direction_alignment.py          # Canonicalize effect direction
│   │   ├── claim_level.py                  # Identified/Associational/Mechanistic
│   │   ├── scope_matching.py               # 5-dim w_scope (P3-2)
│   │   └── gating.py                       # Quality gates
│   │
│   ├── p3_heterogeneity/
│   │   ├── __init__.py
│   │   ├── layers.py                       # All 7 layers in one file (v1)
│   │   │                                   # L1-L7 as functions, composed
│   │   │                                   # Formulas P3-1 through P3-8
│   │   └── se_eff_assembly.py              # Final SE_eff computation
│   │
│   ├── p4_aggregation/
│   │   ├── evidence_grouper.py             # Group by edge, partition MA/primary
│   │   ├── double_counting.py              # DCR: DCR-1, DCR-2 formulas
│   │   │                                   # AMBIGUOUS → review_tasks row (v1 ops #8)
│   │   ├── meta_analyzer.py               # IVW/RE + annotation σ² + P_incl adj
│   │   ├── prior_selector.py              # 5-branch decision tree
│   │   └── edge_writer.py                 # Write edges_v1 (118 rows)
│   │
│   ├── p4b_publication_bias/
│   │   ├── egger.py
│   │   ├── trim_fill.py
│   │   └── bias_aggregator.py
│   │
│   ├── p5_sufficiency/
│   │   ├── coverage.py                     # Per-edge grading
│   │   ├── chain_vs_direct.py             # §2.13 comparator
│   │   └── gap_analysis.py                # Evidence gaps (for v1: report only)
│   │
│   └── p6_deployment/
│       └── validation.py                   # 16 rules, DEPLOY/BLOCK decision
│                                           # BLOCK → review_tasks row (v1 ops #8)
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ ALGORITHM (the actual science — THIS IS THE CORE)
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── algorithm/
│   ├── __init__.py
│   │
│   ├── chain_a_graph/
│   │   ├── node_loader.py                  # 63 nodes → hierarchy
│   │   ├── edge_loader.py                  # 118 edges → B̂ matrix
│   │   ├── instrument_loader.py            # 23 instruments → H matrix
│   │   ├── spectral_validator.py           # ρ(B) < 1 CRITICAL check
│   │   └── graph_object.py                 # Assemble complete GraphObject
│   │
│   ├── chain_b_evidence/
│   │   ├── evidence_compiler.py            # Read edge_evidence_v1 per edge
│   │   ├── variance_computation.py         # 7-layer SE_eff (mirrors EX-P3)
│   │   │                                   # σ²_struct from edges_v1
│   │   ├── prior_assignment.py             # Same 5-branch tree as EX-P4-PS
│   │   ├── inclusion_probability.py        # P4-3 + P4-3b
│   │   ├── constraint_enforcement.py       # Literary bounds
│   │   └── frozen_state.py                 # Freeze → FrozenModelState
│   │                                       # Assigns frozen_model_version_id
│   │                                       # Pinned at session start (v1 ops #7)
│   │
│   ├── chain_c_posterior/                  # *** THE BAYESIAN ENGINE ***
│   │   ├── prior_loader.py                # 4-level fallback resolution
│   │   ├── observation_mapper.py          # Questionnaire → node observations
│   │   ├── bayesian_update.py             # θ̂ = θ_prior + K(y - H·θ_prior)
│   │   │                                   # K = Σ_prior·H'·(H·Σ_prior·H'+Σ_ε)⁻¹
│   │   │                                   # THIS IS THE MOST IMPORTANT FILE
│   │   ├── modifier_application.py        # Apply 109 patient modifiers
│   │   └── posterior_writer.py            # → state_snapshots_v1
│   │
│   ├── chain_d_simulation/
│   │   ├── intervention_loader.py         # Kernels, synergies, doses
│   │   ├── mc_sampler.py                  # 10K MC draws per intervention
│   │   │                                   # Per draw: sample edges, sample β,
│   │   │                                   # apply intervention, compute SAFE
│   │   ├── safety_checker.py              # Contraindication evaluation
│   │   └── ranker.py                      # Rank by E[SAFE_B], CrI, stability
│   │
│   ├── chain_e_temporal/
│   │   ├── trajectory_simulator.py        # 0,4,8,12,26,52 weeks forward sim
│   │   └── recovery_model.py             # Post-cessation curves
│   │
│   └── chain_f_analytics/
│       ├── composite_scorer.py            # CRCI score: weighted 11 subdomains
│       ├── population_norming.py          # Percentile vs normative
│       ├── variance_decomposer.py         # 5-source decomposition
│       └── evsi.py                        # Expected Value of Sample Info
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ RUNTIME (session orchestration — simple for v1)
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── runtime/
│   ├── session.py                          # Session lifecycle (simple)
│   ├── schedule_generator.py               # Generate intervention combinations
│   ├── adaptive_questions.py               # IG-based question selection
│   └── report_assembler.py                # Package all outputs
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ PRESENTATION (for the science submission)
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── presentation/
│   ├── dag_viz.py                          # Full 63-node DAG rendering
│   ├── evidence_browser.py                 # Edge drill-down with study-level
│   ├── intervention_cards.py               # Ranked intervention display
│   ├── trajectory_plot.py                  # Temporal prediction charts
│   ├── variance_pie.py                     # 5-source decomposition visual
│   ├── crci_dashboard.py                   # Composite score + radar
│   └── provenance_viewer.py               # Claim → paper trace
│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│ TESTS + SCRIPTS
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│
├── tests/
│   ├── test_database/                      # Schema + FK + seed validation
│   ├── test_extraction/                    # Per-chain, per-layer tests
│   ├── test_algorithm/                     # Bayesian update, MC, composite
│   ├── test_runtime/                       # Session flow
│   └── test_end_to_end/                    # Paper → recommendation
│
└── scripts/
    ├── run_extraction.py                   # CLI: extract one or many papers
    ├── run_build.py                        # CLI: compile edges_v1 from evidence
    ├── run_session.py                      # CLI: patient session → recommendations
    ├── seed_database.py                    # Load all CSVs
    └── validate_model.py                   # Full compiled model checks


═══════════════════════════════════════════════════════════════════════════
 PART 4: WHAT I PULLED FROM THE OPS DOC INTO V1
═══════════════════════════════════════════════════════════════════════════

These are the specific elements from the production ops blueprint that v1
NEEDS to work. Everything else stays in v2.

INTEGRATED INTO V1 (8 items — the minimum ops floor):
──────────────────────────────────────────────────────
1. LLM ABSTRACTION (minimal)
   From ops doc Part 9. NOT the full multi-provider gateway.
   Just: llm/client.py that wraps Claude API calls with:
     - Retry on HTTP 429/502/timeout (3 attempts, exponential backoff)
     - Structured JSON response parsing + schema validation
     - Token counting and cost logging (know what you spend)
     - Model ID pinned in extraction_runs table
     - Prompt templates stored as files (hashable for reproducibility)
   WHY: Without this, extraction agents will silently fail or produce
   garbage when Claude has a hiccup. This is ~200 lines of code that
   saves you days of debugging.

2. BASIC IDEMPOTENCY
   From ops doc Part 6. NOT the full replay/DLQ framework.
   Just: before extracting a paper, check if study_id already exists
   in extraction_runs with status=completed and same version_bundle.
   If yes, skip (log "already extracted"). If partial, resume.
   WHY: When you're extracting 200 papers, you WILL re-run the script
   after a crash. Without idempotency, you get duplicate evidence rows.

3. EXTRACTION RUN PROVENANCE
   From ops doc Part 9.3. Already in your spec (extraction_runs table).
   Log: model_id, prompt_template_hash, pipeline_version, paper_hash.
   WHY: Required for scientific reproducibility. Reviewers will ask
   "which model extracted this?" and you need to answer precisely.

4. COST TRACKING (passive, not controlling)
   From ops doc Part 9.7. NOT a budget controller.
   Just: log every Claude call with prompt_tokens, completion_tokens,
   estimated_cost_usd to a simple table or CSV.
   WHY: You need to know what 200 papers costs before you scale to 500.
   If deep extraction costs $2/paper and you have 200, that's $400.
   You should know this before it's on your credit card.

5. PAPER TYPE ROUTING (affects extraction quality)
   From ops doc recommendations. Your spec already has PTC.
   Implement the 23-subtype classifier and use it to:
     - Skip case reports / qualitative studies (save LLM cost)
     - Route umbrella reviews to SHALLOW (they summarize, not report)
     - Route RCTs to STANDARD or DEEP (high-value evidence)
   WHY: Without this, you waste LLM budget extracting papers that
   contribute nothing to edges_v1.

5. VERSIONED POLICY/CONFIG SNAPSHOT PER RUN
   From ops doc principle of version_bundle tracking.
   When you run extraction or compilation, snapshot which config was
   active: SE calibration constants, gate thresholds, GRADE multipliers,
   scope weights, σ² ceiling, ATB rules version, etc.
   Store as a JSON blob in extraction_runs or a separate policy_snapshots table.
   WHY: If you change GRADE_MULTIPLIERS from {LOW: 1.50} to {LOW: 1.40}
   and re-extract 20 papers, you MUST know which edges used which policy.
   Without this, your sensitivity analyses become impossible to interpret.

6. CHECKPOINT/RESUME FOR EXTRACTION PIPELINE
   From ops doc Part 6 (partial recovery). NOT the full workflow engine.
   Just: after each agent completes for a paper, write its output to DB
   with status per-agent. If pipeline crashes at AG07, resume from AG07
   on next run (don't re-run AG01-AG06). Same for chain-level: if P3
   completes but P4 crashes, resume at P4.
   WHY: Deep extraction takes 2-5 min per paper. If you're running 200
   papers overnight and it crashes at paper #147, you don't want to
   re-extract papers 1-146. This is ~50 lines of checkpoint logic.

7. FROZEN MODEL VERSION PINNING FOR RUNTIME TESTS
   From ops doc Part 17 (OR-OPS-08). NOT the full publish lock protocol.
   Just: when you run a test session, record which frozen_model_version_id
   was used. If you re-compile edges_v1 (because you extracted more
   papers), old test results are tagged with their model version.
   New tests use the new version. You can compare across versions.
   WHY: You WILL re-compile the model multiple times during development.
   If your test patient gets different recommendations on Tuesday vs
   Thursday and you can't tell whether it's because you changed code
   or because the evidence base changed, you'll lose days debugging.

8. ONE SIMPLE REVIEW QUEUE (DB table, not a service)
   From ops doc Part 4 (review queues). NOT the full HITL service.
   Just: a review_tasks table with columns:
     task_id, task_type, entity_type, entity_id, reason, status,
     created_at, resolved_at, resolution, notes
   task_type values: DCR_AMBIGUOUS, ATB_REJECTION, HIGH_IMPACT_CONFLICT,
     P6_VALIDATION_FAILURE, MANUAL_FLAG
   Status: OPEN, RESOLVED, DEFERRED, IGNORED
   When P4-DCR hits AMBIGUOUS, write a row. When ATB rejects a
   high-impact annotation, write a row. When P6 blocks deployment,
   write a row. You review them manually (SELECT * WHERE status='OPEN').
   WHY: Without this, AMBIGUOUS overlap decisions and trust boundary
   failures disappear into log files. The spec REQUIRES human review
   for P4-G3 (AMBIGUOUS) — this is the minimum viable implementation
   of that requirement. It's one CREATE TABLE and a few INSERT calls.

DEFERRED TO V2:
─────────────────
- Multi-provider gateway (just use Claude directly)
- Queue broker (just call functions in sequence)
- Worker pools (single process is fine for 200 papers)
- Scheduler (you decide when to run extraction)
- Budget controller (passive tracking is enough for v1)
- Source adapters (you download PDFs manually)
- Capacity caps (you control volume by choosing papers)
- Observability dashboards (Python logging is fine)
- Review SLA management (you are the reviewer)
- Deployment stages (local Postgres, that's it)
- Kubernetes, Docker orchestration, Terraform
- DLQ, circuit breakers, backpressure
- All 30 named queues from the ops doc


═══════════════════════════════════════════════════════════════════════════
 PART 5: V1 IMPLEMENTATION ORDER
═══════════════════════════════════════════════════════════════════════════

PHASE 0: FOUNDATION (Week 1-2)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: database/schema/*.sql + shared/models/ + shared/config.py │
  │ Seed: ALL Class A tables from CSVs                               │
  │ Test: 56 tables exist, all FKs enforced, seeds loaded            │
  │ Gate: Can query nodes_v1 (63), edges_v1 (118), instruments (23) │
  └──────────────────────────────────────────────────────────────────┘
  This is SCIENTIFIC WORK:
    Define the 63 nodes from the paper's DAG
    Define the 118 edges from the paper's causal structure
    Define the 23 instruments from the measurement model
    Define the 109 modifier rules from patient modifiers
    Define the 33 priors from the literature
  This is where domain expertise matters most.
  If these are wrong, nothing downstream can be right.

PHASE 1: LLM CLIENT + EXTRACTION SKELETON (Week 2-3)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: llm/client.py (Claude wrapper with retry + schema parse)  │
  │ Build: extraction/pipeline.py (orchestrator skeleton)            │
  │ Build: extraction/p0_triage/ (PDF intake + relevance + classify) │
  │ Build: extraction/p1_extraction/base_agent.py (agent framework)  │
  │ Test: Feed 1 paper → triage → classify → agents produce output  │
  │ Gate: Can extract metadata from 1 known paper correctly          │
  └──────────────────────────────────────────────────────────────────┘
  Start with AG01 (metadata) + AG02 (design) + AG05 (stats).
  These three agents produce the minimum viable evidence row.
  Add remaining agents incrementally.

PHASE 2: TRUST BOUNDARY + EVIDENCE WRITING (Week 3-4)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: extraction/tb_trust_boundary/ (SpanLabel → numbers)       │
  │ Build: extraction/p2_harmonization/ (standardize, gate, scope)   │
  │ Test: SpanLabel with β=0.35, CI=[0.12,0.58] → correct parse     │
  │ Test: Edge_evidence_v1 row written with all required columns     │
  │ Gate: 5 known papers produce correct edge_evidence_v1 rows       │
  └──────────────────────────────────────────────────────────────────┘
  THIS IS THE CRITICAL BOUNDARY. If the trust boundary is wrong,
  every downstream computation is contaminated.
  Test this extensively with known papers and known effect sizes.

PHASE 3: CALIBRATION + AGGREGATION (Week 4-5)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: extraction/p3_heterogeneity/ (7 layers, SE_eff)           │
  │ Build: extraction/p4_aggregation/ (IVW, RE, DCR, priors)        │
  │ Build: extraction/p4b_publication_bias/ (Egger, trim-fill)       │
  │ Build: extraction/p5_sufficiency/ (coverage, gaps)               │
  │ Build: extraction/p6_deployment/ (16 validation rules)           │
  │ Test: Known evidence set → expected β̂, SE_eff, method choice    │
  │ Gate: edges_v1 fully populated (118 rows, no NaNs, all methods)  │
  └──────────────────────────────────────────────────────────────────┘
  Formula-dense phase. Implement P3-1 through P3-8, P4-1/P4-2,
  P4-3/P4-3b, DCR-1/DCR-2 exactly as specified.
  Test with hand-computed examples.

PHASE 4: BATCH EXTRACTION (Week 5-7)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Run: Extract 50-200 papers through full pipeline                 │
  │ Review: Check edge_evidence_v1 for obvious errors                │
  │ Review: Check edges_v1 compilation for reasonable values          │
  │ Fix: Iterate on prompts, parsing, harmonization as needed        │
  │ Gate: edges_v1 passes P6 deployment validation                   │
  └──────────────────────────────────────────────────────────────────┘
  This is where you'll spend the most time iterating.
  The prompts will need tuning. The parser will miss edge cases.
  Budget ~$200-600 for Claude API during this phase depending on
  paper count and extraction depth.

  OPTIONAL (v1.5): Add AG10 strategic annotations for the papers
  that discuss limitations and future research. This populates
  study_annotations_v1 and enables σ²_structural adjustment.
  Nice for the science project but not blocking.

PHASE 5: ALGORITHM — THE ACTUAL SCIENCE (Week 7-9)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: algorithm/chain_a_graph/ (GraphObject from compiled data) │
  │ Build: algorithm/chain_b_evidence/ (freeze model state)          │
  │ Test: ρ(B) < 1, all 118 edges in graph, spectral OK             │
  │                                                                  │
  │ Build: algorithm/chain_c_posterior/ (*** BAYESIAN UPDATE ***)     │
  │ Build: algorithm/chain_d_simulation/ (MC sampler)                │
  │ Build: algorithm/chain_e_temporal/ (trajectory prediction)       │
  │ Build: algorithm/chain_f_analytics/ (composite, variance, EVSI)  │
  │ Test: Known patient → expected posterior → expected ranking       │
  │ Gate: Full inference produces valid CompositeScore + rankings     │
  └──────────────────────────────────────────────────────────────────┘
  THIS IS THE CORE OF THE SCIENCE PROJECT.
  chain_c_posterior/bayesian_update.py is the single most important
  file in the entire system. It implements the Kalman-like update
  that IS the Bayesian causal model. Get this right.

PHASE 6: RUNTIME + PRESENTATION (Week 9-11)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Build: runtime/ (session flow, question selection)               │
  │ Build: presentation/ (visualizations for submission)             │
  │ Test: Full session: questionnaire → inference → report           │
  │ Gate: Can produce all outputs listed in Part 1                   │
  └──────────────────────────────────────────────────────────────────┘

PHASE 7: END-TO-END VALIDATION (Week 11-12)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Test: Paper PDF → extraction → compilation → session → output    │
  │ Test: Multiple patient profiles → different recommendations      │
  │ Test: Sensitivity: change 1 edge → output changes appropriately  │
  │ Gate: System produces scientifically defensible results           │
  └──────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 PART 6: OUTPUT CONTRACTS (what the science project shows)
═══════════════════════════════════════════════════════════════════════════

A. COMPOSITE CRCI SCORE
   {CRCI_score: float [0-10], severity_tier: NONE/MILD/MODERATE/SEVERE,
    percentile: float [0-100], subdomains: [{domain_id, score, z_score}×11],
    confidence_interval: [low, high], stability_flag: STABLE/DRIFTING/UNSTABLE}

B. INTERVENTION SCHEDULE (top 5)
   [{rank, interventions: [{action_id, display_name, dose, frequency}],
     SAFE_A: float, SAFE_B: float [0-10], CrI_95: [low, high],
     stability: HIGH/MEDIUM/LOW, contraindication_status: CLEAR/WARNING}]

C. PATHWAY PROFILE
   [{pathway_id, pathway_name, activation_z, dysregulation_flag,
     targeted_by: [action_id]}]

D. TEMPORAL TRAJECTORIES
   [{timepoint_weeks, predicted_score, CrI_95: [low, high],
     intervention_active: bool}]

E. VARIANCE DECOMPOSITION
   {literature_pct, measurement_pct, structural_pct, patient_pct,
    stochastic_pct}

F. EVIDENCE GAPS
   [{edge_id, discovery_score, recommended_study, EVSI}]

G. DECISION AUDIT TRAIL
   Full provenance: edge → evidence records → papers


═══════════════════════════════════════════════════════════════════════════
 PART 7: MASTER PROMPT TEMPLATE (unchanged — use for every task)
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│                    MASTER IMPLEMENTATION PROMPT                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ## SYSTEM CONTEXT                                                   │
│  You are implementing the CRCI Bayesian Causal Model system.         │
│  This is a scientifically rigorous evidence-to-recommendation        │
│  pipeline with 56 database tables, 25 processing chains,             │
│  ~121 subsystems, and ~80 mathematical formulas.                     │
│                                                                     │
│  ## CURRENT TASK                                                     │
│  Component: [SYSTEM].[CHAIN].[SUBSYSTEM]                             │
│  File: [exact file path]                                             │
│  Purpose: [1-sentence from spec]                                     │
│                                                                     │
│  ## SPECIFICATION EXCERPT                                            │
│  [Paste EXACT relevant section from system spec. Include:            │
│   subsystem card, formulas, gates, intermediate states, boundary     │
│   tables, assumptions.]                                              │
│                                                                     │
│  ## UPSTREAM DEPENDENCIES                                            │
│  Reads from: [table/state] produced by [upstream subsystem]          │
│                                                                     │
│  ## DOWNSTREAM CONSUMERS                                             │
│  Writes to: [table/state] consumed by [downstream subsystem]         │
│                                                                     │
│  ## FORMULAS TO IMPLEMENT                                            │
│  [Every formula ID with full equation and parameter sources]         │
│                                                                     │
│  ## VALIDATION GATES                                                 │
│  [Every gate with pass/fail conditions]                              │
│                                                                     │
│  ## CONSTANTS (from shared/config.py)                                │
│  [All constants this component uses]                                 │
│                                                                     │
│  ## SCIENTIFIC RIGOR REQUIREMENTS                                    │
│  - Every numeric output traceable to a formula ID                    │
│  - All intermediate values logged for audit                          │
│  - No silent fallbacks: log every default with reason                │
│  - Random seeds settable for reproducibility                         │
│                                                                     │
│  ## WHAT NOT TO DO                                                   │
│  - Do NOT invent formulas not in the spec                            │
│  - Do NOT skip validation gates                                      │
│  - Do NOT hardcode values that should come from config               │
│  - Do NOT silently drop data                                         │
│  - Do NOT change table schemas                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 PART 8: END-TO-END WIRING TRACES
═══════════════════════════════════════════════════════════════════════════

TRACE 1: Paper → Recommendation (the main pipeline)
  You download paper.pdf
    → extraction/pipeline.py processes it
      → p0: classify paper type, select mode
        → p1: CR reads once → AG1-AG10 extract → TB parses → evidence row
          → p2: harmonize → standardize → scope match
            → p3: 7-layer SE calibration → SE_eff
              → p4: group → DCR → IVW/RE → prior → write edges_v1
    → algorithm/chain_a: assemble GraphObject from edges_v1
      → chain_b: freeze model state
        → chain_c: patient answers questions → Bayesian update → θ̂
          → chain_d: MC simulation → SAFE per intervention → rank
            → chain_f: CRCI score, variance decomposition, EVSI
              → presentation: dashboard, cards, trajectory, DAG

TRACE 2: Annotation → Wider Uncertainty (σ² pathway)
  AG10 finds "unmeasured confounder" in Discussion
    → reconciliation dedup → ATB validates (AT-03: confounder_name)
      → study_annotations_v1 row
        → P4-MA reads annotation → σ²_structural = 0.25 + adjustment
          → edges_v1.sigma_sq_structural for this edge
            → ALG-B2 reads it → SE_eff wider → MC: wider CrI

TRACE 3: Questionnaire → Personalized Score
  Patient answers FACT-Cog
    → observation_mapper: instrument → node → observation vector y
      → bayesian_update: θ̂ = θ_prior + K(y - H·θ_prior)
        → modifier_application: age>65, APOE4+, diabetes → adjust
          → mc_sampler: 10K draws with personalized posterior
            → composite_scorer: CRCI score → severity tier → percentile


═══════════════════════════════════════════════════════════════════════════
 PART 9: SCIENTIFIC RIGOR CHECKLIST (run every session)
═══════════════════════════════════════════════════════════════════════════

□ Formula fidelity: Code implements EXACT formula from spec
□ Audit trail: Every decision logged with reason
□ Reproducibility: Random seeds settable, extraction_runs logged
□ Provenance: Every edge → LER IDs → study → paper
□ Trust boundaries: LLM output → deterministic parse → evidence
□ Graceful degradation: Missing data → logged defaults, not errors
□ Gate enforcement: All validation gates implemented and tested


═══════════════════════════════════════════════════════════════════════════
 PART 10: V2 ROADMAP (after science project, not before)
═══════════════════════════════════════════════════════════════════════════

When the science project is submitted and the prediction system works,
THEN build the production automation layer:

V2 PHASE O1: Queue + job primitives (from ops doc Parts 4-6)
V2 PHASE O2: Source adapters (PubMed, Europe PMC, Unpaywall first)
V2 PHASE O3: LLM gateway (multi-provider, routing, failover)
V2 PHASE O4: Scheduler + budget controller
V2 PHASE O5: Observability + alerts
V2 PHASE O6: Single-node continuous pilot
V2 PHASE O7: Cloud deployment

Reference document: CRCI_PRODUCTION_ORCHESTRATION_AND_OPS_BLUEPRINT.md
(the ops companion spec you already wrote — it becomes the v2 plan)


═══════════════════════════════════════════════════════════════════════════
 SUMMARY
═══════════════════════════════════════════════════════════════════════════

Total v1 code files: ~70 (down from ~120)
Total database tables: 56 (unchanged — schema is the foundation)
Total formulas to implement: ~80 (unchanged — the science is the science)
Total validation gates: ~30 (unchanged — rigor is non-negotiable)

v1 timeline: ~12 weeks for a working prediction system
v2 timeline: ~6-8 weeks additional for production automation

Priority: The Bayesian engine (chain_c/bayesian_update.py) and the
compiled evidence (edges_v1 from extraction) are the two things that
make or break the science project. Everything else serves them.

═══════════════════════════════════════════════════════════════════════════
END OF IMPLEMENTATION BLUEPRINT v1.1
═══════════════════════════════════════════════════════════════════════════
