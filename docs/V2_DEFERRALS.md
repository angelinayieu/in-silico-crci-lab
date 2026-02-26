# CRCI — Consolidated Deferral Tracker

> **Purpose:** Single source of truth for all features, modules, and improvements
> deferred beyond the current v1 code-complete scope. Prevents items from falling
> through the cracks across scattered docs.
>
> **Last updated:** 2026-02-26
>
> **How to use:** Before starting new work, check this list. When deferring
> something new, add it here with a source reference.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| DEFERRED | Explicitly deferred — documented design exists, not yet built |
| PLACEHOLDER | Design stub exists in a doc — no implementation attempted |
| GAP | Functional gap identified during audit — no design yet |
| BLOCKED | Cannot proceed until a prerequisite is met |

---

## 1. Algorithm Extensions

### 1.1 MC Sampler Pathway Mask
- **Status:** DEFERRED
- **Source:** [gapmap.md](gapmap.md) Slice 6 (lines 255–280)
- **What:** Filter edges in `mc_sampler.py` `_build_edge_map()` using
  `FrozenModelState.active_pathway_ids` so edges belonging to inactive
  pathways (low evidence density) are excluded from MC simulation draws.
- **Why deferred:** Edgeless pathways (M11, M14) already have B̂=0. Low-evidence
  pathways (M08, M12, M17) use structural placeholder priors with μ_e ≈ 0.
  Filtering has near-zero practical impact today.
- **Trigger:** Implement when extraction populates ≥50 edges with real betas
  AND at least one pathway has ED > 0.15 but poor DS.
- **Skeleton:** Commented-out code in [gapmap.md lines 269–271](gapmap.md).
- **Depends on:** Sufficient evidence extraction (§6.1)

### 1.2 Clinical Risk Estimator (F4)
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §4
- **What:** Module `risk_estimator.py` in `chain_f_analytics/` that computes
  P(CRCI | data) via MC integration over posterior draws, using ICCTF criteria.
  Produces risk percentage with credible interval and per-domain decomposition.
- **Why deferred:** Requires non-degenerate posterior draws for `NODE_COG_*` nodes
  (Step 0 prerequisite in §6). Current extraction density insufficient.
- **Depends on:** Sufficient evidence in cognitive domain edges, stable posterior draws

### 1.3 Subpopulation Comparative Risk View
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.1
- **What:** Cross-subpopulation comparison showing how risk percentages differ
  across cancer types / treatment phases. Runs `risk_estimator.py` across
  multiple context specifications.
- **Depends on:** §1.2 (risk estimator)

### 1.4 Future/Predictive Risk Under Intervention
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.2
- **What:** Compute P̂(CRCI at t+Δ | intervention) using Chain E trajectory
  draws. Extends F4 from "current state risk" to "predicted future risk."
- **Depends on:** §1.2 (risk estimator), Chain E per-draw trajectory output

### 1.5 Adaptive Intensity Ramp Scheduling
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.3
- **What:** Dynamic dosage scheduling that adjusts intervention intensity over
  weeks/months based on K(t) temporal kernel decay. Currently static schedules.
- **Depends on:** Chain E intervention overlay integration

### 1.6 Clinical Calibration Pipeline
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.8
- **What:** Calibrate model-derived probabilities against observed CRCI incidence
  in external cohorts (Platt scaling or isotonic regression). Output carries
  `calibration_status` field — currently always "uncalibrated."
- **Depends on:** §1.2 (risk estimator), held-out validation dataset

### 1.7 Test-Level ICCTF Classification
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.9
- **What:** Upgrade from domain-level to individual test-score-level ICCTF
  classification. Requires measure-level posterior draws and measurement model
  mapping from MEASURE_REGISTRY.
- **Depends on:** §1.2 (risk estimator), measure-level draws

### 1.8 Stepwise Complexity Optimization
- **Status:** DEFERRED
- **Source:** [gapmap.md](gapmap.md) Slice 6 notes
- **What:** Full stepwise pathway inclusion/exclusion loop using DS (distinction
  scores) and information criteria to find optimal pathway subset.
- **Trigger:** Extraction populates ≥50 edges with real betas.
- **Depends on:** §1.1, sufficient evidence extraction

### 1.9 v2.0 Active β Learning
- **Status:** DEFERRED
- **Source:** [SYS_ALGORITHM_COMPLETE.md](02_system_specs/SYS_ALGORITHM_COMPLETE.md) line 164
- **What:** Hierarchical random slopes for learning edge weights from individual
  patient outcomes (currently edges are fixed at build time).
- **Depends on:** Patient outcome data collection infrastructure

---

## 2. Extraction Pipeline

### 2.1 Extraction → Algorithm Data Bridge
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.7
- **What:** `load_evidence_records()` function to bridge ORM rows in
  `edge_evidence_v1` → `EvidenceRecord` dataclass (14 fields) for Chain B
  consumption. Schema validation ensuring all fields are populated.
- **Depends on:** Evidence in database

### 2.2 OCR for Scanned PDFs
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) line 624
- **What:** Add `ocrmypdf` integration for scanned PDF processing. Currently
  scanned PDFs produce SCAN quality and are not processed.
- **Depends on:** Nothing — can be added independently

### 2.3 Failed Paper Retry Logic
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) line 558
- **What:** `--retry-failed` CLI flag for re-processing papers that failed
  extraction. Currently failed papers are skipped permanently.
- **Depends on:** Nothing — can be added independently

### 2.4 Additional Template Importers
- **Status:** GAP
- **Source:** [manual_upload_watcher.py](../crci/retrieval/manual_upload_watcher.py) line 181
- **What:** Only `edge_evidence_template` CSV import is implemented. Five other
  template types exist in `data/templates/` but have no importer:
  - `context_priors_template.csv`
  - `correlation_template.csv`
  - `instrument_evidence_template.csv`
  - `population_norms_template.csv`
  - `temporal_evidence_template.csv`
- **Depends on:** Nothing — can be added independently

### 2.5 SR/MA Extraction Path Fixes
- **Status:** GAP
- **Source:** [PIPELINE_AUDIT.md](../PIPELINE_AUDIT.md) lines 296–310
- **What:** Systematic review papers currently produce NO persisted data (study
  registry row destroyed by rollback on P6 GateViolation). Needs: partial commit
  for study_registry, hop_discoverer integration, MA-specific P3/P4 path.
- **Depends on:** Pipeline architecture decision on partial commits

### 2.6 EX-P1 v2 Parallel Agent Architecture
- **Status:** DEFERRED
- **Source:** [SYS_EXTRACTION_COMPLETE.md](02_system_specs/SYS_EXTRACTION_COMPLETE.md) lines 292–380
- **What:** Canonical Reader builds immutable PaperMap; agents run in parallel on
  targeted sections. Current v1 runs agents sequentially on full text.
- **Depends on:** Performance need (v1 sequential is fine for <200 papers)

### 2.7 AG09 Reconciliation Agent
- **Status:** GAP
- **Source:** [PIPELINE_AUDIT.md](../PIPELINE_AUDIT.md) BUG-009 (line 149)
- **What:** AG09 (ReconciliationAgent) is missing from the agent list. P1 skips
  from AG08 (TemporalAgent) to AG10 (StrategicIntelAgent). Reconciliation of
  conflicting agent outputs is not performed.
- **Depends on:** Nothing — can be added independently

### 2.8 Annotation-Informed σ²_structural
- **Status:** DEFERRED
- **Source:** [SYS_ALGORITHM_COMPLETE.md](02_system_specs/SYS_ALGORITHM_COMPLETE.md) line 1149
- **What:** Per-edge σ²_structural informed by study annotations about unmeasured
  confounders (from `study_annotations_v1`). Currently uses static default 0.25.
- **Depends on:** AG10 strategic annotation extraction populating annotations table

---

## 3. Presentation & Reporting

### 3.1 Risk Dashboard
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §4.5
- **What:** `risk_dashboard.py` rendering risk % gauge + domain breakdown chart.
- **Depends on:** §1.2 (risk estimator)

### 3.2 Research Type Heat Map
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.4
- **What:** Visual heat map of research design types (RCT, prospective, etc.)
  across edges/domains. Data exists in `edge_evidence_v1.study_design`.
- **Depends on:** Evidence in database

### 3.3 Cross-Paper Pattern Detection
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.5
- **What:** Identify recurring patterns across papers (e.g., "3 studies all find
  exercise → BDNF but use different instruments"). Cross-edge evidence mining.
- **Depends on:** Sufficient extraction volume

### 3.4 Structured Reasoning Narrative Compiler
- **Status:** PLACEHOLDER
- **Source:** [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) §8.6
- **What:** Synthesize intervention rankings, safety constraints, variance sources
  into clinician-readable justification text. Data exists across RankingResult,
  SafetyResult, VarianceState, StabilityState.
- **Depends on:** Full pipeline producing valid results

### 3.5 Monitoring Dashboard (FastAPI)
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) Workstream 3 (lines 588–620)
- **What:** Web dashboard with pages for queue status, extraction detail, evidence
  coverage heatmap, cost tracking. FastAPI + Jinja2 + SSE for live logs.
- **Depends on:** Extraction pipeline producing data at scale

### 3.6 RecommendationReport Unpopulated Fields
- **Status:** GAP
- **Source:** [PROGRESS.md](../PROGRESS.md) "Known Limitations" section
- **What:** Three `RecommendationReport` fields are defined but not populated:
  - `trajectories` — needs Chain E integration
  - `evidence_gaps` — needs extraction evidence gap compilation
  - `pathway_profile` — needs pathway activation computation
- **Note:** All presentation modules handle empty state gracefully.
- **Depends on:** Full pipeline end-to-end integration

---

## 4. Infrastructure & Operations

### 4.1 Multi-Provider LLM Gateway
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_BLUEPRINT_v1.1.md](02_system_specs/IMPLEMENTATION_BLUEPRINT_v1.1.md) lines 466–479
- **What:** Multi-provider routing, queue broker, worker pools, scheduler, budget
  controller, DLQ, circuit breakers, capacity caps.
- **Note:** v1 uses direct Claude calls, sequential processing, passive cost tracking.
- **Depends on:** Scale need

### 4.2 Production Deployment Infrastructure
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_BLUEPRINT_v1.1.md](02_system_specs/IMPLEMENTATION_BLUEPRINT_v1.1.md) lines 466–479
- **What:** Kubernetes, Docker orchestration, Terraform, deployment stages,
  observability dashboards, review SLA management.
- **Note:** v1 runs locally on SQLite.
- **Depends on:** Production deployment need

### 4.3 PostgreSQL Migration
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) line 624
- **What:** SQLite → PostgreSQL for concurrent access. Sequential processing
  works for ≤100 papers (~5 hours).
- **Depends on:** Concurrency need

### 4.4 RankingResult JSON Serialization
- **Status:** GAP
- **Source:** [run_session.py](../scripts/run_session.py) line 168
- **What:** `run_session.py` raises `NotImplementedError` when loading
  `--ranking-json` file. JSON deserialization of `RankingResult` not implemented.
  Workaround: use Python API directly.
- **Depends on:** Nothing — can be added independently

### 4.5 Autonomous Retrieval Pipeline
- **Status:** DEFERRED
- **Source:** [IMPLEMENTATION_GUIDE.md](00_navigation/IMPLEMENTATION_GUIDE.md) line 134,
  [INDEX.md](00_navigation/INDEX.md) line 90
- **What:** Full automated paper retrieval with background workers, autonomous
  cycling, saturation detection. Config constants exist (§v2.0 in config.py
  lines 1160–1186) but pipeline is manual.
- **Depends on:** Evidence density need

### 4.6 Extraction Audit Trail
- **Status:** GAP
- **Source:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) line 610 note
- **What:** `extraction_audit_v1` table exists in schema but pipeline doesn't
  write to it. Need `session.add(ExtractionAudit(...))` at end of each runner.
- **Depends on:** Nothing — can be added independently

---

## 5. Data & Evidence

### 5.1 Evidence Extraction at Scale
- **Status:** BLOCKED
- **Source:** [CRITICAL_REVIEW.md](CRITICAL_REVIEW.md)
- **What:** ~129/137 edges still need evidence. 8 manually extracted edges exist
  but edge ID naming mismatches prevent DB loading. The system cannot produce
  scientifically valid recommendations without substantially more evidence.
- **Blocks:** §1.1, §1.2, §1.8, §3.2, §3.3
- **Depends on:** Manual extraction effort + pipeline bug fixes (§2.5)

### 5.2 Edgeless Pathway Population (M11, M14)
- **Status:** DEFERRED
- **Source:** [NODE_REGISTRY.csv](../registries/NODE_REGISTRY.csv),
  [PATHWAY_REGISTRY.csv](../registries/PATHWAY_REGISTRY.csv)
- **What:** Pathways M11 (Cerebrovascular) and M14 (BBB Disruption) have zero
  edges in the skeleton. Need literature review + edge definition + evidence
  extraction.
- **Depends on:** Domain expertise + literature search

---

## 6. Documents Not Yet Created

Referenced in code/docs but not yet written:

| Document | Referenced In | Purpose |
|----------|--------------|---------|
| `INTERFACE_SCHEMA_LOCK.md` | [CLAUDE.md](../CLAUDE.md) line 151 | Field-level definitions for intermediate states |
| ~~`TABLE_FILL_ORDER.md`~~ | ~~CLAUDE.md~~ | ~~Table population order~~ (NOW EXISTS: `docs/03_database/TABLE_FILL_ORDER.md`) |

---

## Priority Tiers

### Tier 1 — Needed for first valid end-to-end result
- §5.1 Evidence extraction at scale
- §2.1 Extraction → Algorithm data bridge
- §2.5 SR/MA extraction path fixes
- §3.6 RecommendationReport field population

### Tier 2 — High scientific value
- §1.2 Clinical risk estimator (F4)
- §1.1 MC sampler pathway mask
- §3.4 Structured reasoning narrative compiler
- §2.8 Annotation-informed σ²_structural

### Tier 3 — Quality of life / efficiency
- §2.2 OCR for scanned PDFs
- §2.3 Failed paper retry logic
- §2.4 Additional template importers
- §2.7 AG09 reconciliation agent
- §4.4 RankingResult JSON serialization
- §4.6 Extraction audit trail

### Tier 4 — Scale / production
- §4.1 Multi-provider LLM gateway
- §4.2 Production deployment
- §4.3 PostgreSQL migration
- §4.5 Autonomous retrieval pipeline
- §3.5 Monitoring dashboard

### Tier 5 — Future research features
- §1.3 Subpopulation comparative risk
- §1.4 Predictive risk under intervention
- §1.5 Adaptive intensity ramp scheduling
- §1.6 Clinical calibration pipeline
- §1.7 Test-level ICCTF classification
- §1.8 Stepwise complexity optimization
- §1.9 Active β learning
- §3.2 Research type heat map
- §3.3 Cross-paper pattern detection
- §5.2 Edgeless pathway population
