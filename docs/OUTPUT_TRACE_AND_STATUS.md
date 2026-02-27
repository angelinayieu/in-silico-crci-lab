# CRCI System — Output Trace & Status Assessment

> **Purpose**: Single document tracing every system output from research objective
> → algorithm chain → output contract → presentation module → rendered view.
> Identifies what's live, what's dead-wired, and what's planned-but-unbuilt.
>
> **Generated**: 2026-02-27  
> **Updated**: 2026-02-28 — Priority 1–4 fixes applied (wiring, boundary data, CLI, remaining losses)

---

## Table of Contents

1. [Research Objectives → Output Mapping](#1-research-objectives--output-mapping)
2. [Complete Output Inventory](#2-complete-output-inventory)
3. [Presentation Layer Status (Code vs Spec)](#3-presentation-layer-status)
4. [Wiring Gaps & Dead Code](#4-wiring-gaps--dead-code)
5. [Documentation Coverage](#5-documentation-coverage)
6. [What We Have Right Now](#6-what-we-have-right-now)
7. [What Remains To Wire / Build](#7-what-remains-to-wire--build)

---

## 1. Research Objectives → Output Mapping

The research paper ([research paper.md](../research%20paper.md)) defines 4 high-level objective
categories. Below is how each maps to system outputs and their current status.

### Category A: Personalization (Patient-Specific Mechanistic Inference)

| Objective | System Output | Algorithm Chain | Contract Field | Presentation | Status |
|-----------|--------------|-----------------|----------------|--------------|--------|
| **O1** Attribute impairment to biological pathways | Pathway activation profile | C4d → pathway scoring | `report.pathway_profile` (PathwayProfile) | PAT5 pathway_display | ✅ **WIRED** — `_build_pathway_profile()` maps C4d PathwayActivation list |
| **O2** Integrate heterogeneous proxies into mechanistic state with uncertainty | Patient posterior θ̂, Σ_post | C1→C2→C3 (Bayesian fusion) | `report.composite_score` (CompositeScore) | PAT1 crci_dashboard | ✅ **LIVE** |
| **O3** Optimized intervention plans with safety/feasibility | Ranked schedules + dose + safety | D0→D3→D4-D6 → RT-G | `report.primary_schedule`, `report.alternative_schedules` | PAT2 intervention_cards | ✅ **LIVE** |
| **O5** Patient-specific posterior dysregulation vector | Per-domain z-scores + percentiles | C3 → F1 composite | `report.composite_score.domain_scores[]` | PAT1 subdomain bars | ✅ **LIVE** |
| **O6** Individualized trajectory predictions | Temporal curves with CrI bands | E1→E2→E3→E4 | `report.trajectories[]` (TemporalTrajectory) | PAT3 trajectory_plot | ✅ **LIVE** |
| **O9** Clinical risk P̂(CRCI) with CrI + domain breakdown | Risk percentage from MC draws | F4 risk_estimator | `report.clinical_risk` (ClinicalRiskProfile) | risk_dashboard | ✅ **WIRED** — `_build_clinical_risk()` maps CRCIRiskEstimate → ClinicalRiskProfile |
| **O11** Decision stability / rank robustness | Stability class + P(rank1) | F2 stability analysis | `report.variance_decomposition`, `report.decision_trace` | PAT4 variance_pie | ✅ **LIVE** |

### Category B: Paper Analysis / Research Landscape Analysis

| Objective | System Output | Algorithm Chain | Contract Field | Presentation | Status |
|-----------|--------------|-----------------|----------------|--------------|--------|
| **O7** Chain-vs-direct validation (discrepancies → missing mechanisms) | Coherence flags per edge | B4 coherence checker | `edges_v1.coherence_*` columns | SCI4 model_inspection (partial) | ⚠️ **PARTIAL** — flags computed but no dedicated validation view |
| **O10** Evidence-gap prioritization via EVSI | Discovery scores + study designs | F3 EVSI computation | `report.evidence_gaps` (EvidenceGapReport) | SCI1 evidence_browser, SCI5 research_dashboard | ✅ **WIRED** — `evidence_gaps` passed through to assembler |
| Study-level evidence provenance | Per-edge forest plots + DOI links | Extraction → edge_evidence_v1 | `report.decision_trace` | SCI3 provenance_viewer | ✅ **LIVE** |
| Model parameter transparency | Prior types, SE calibration, assumptions | B2→B4 prior selection | `report.decision_trace` | SCI4 model_inspection | ✅ **LIVE** |
| Edge-level evidence browser | 118 edges with β̂, SE, k, claim_level | B1→B5 compilation | `report.evidence_gaps` / DB direct | SCI1 evidence_browser | ✅ **WIRED** (evidence_gaps flows through) |
| DAG visualization (63 nodes, 118 edges) | Interactive graph with edge weights | A1→A3 graph assembly | `report.decision_trace` + `report.pathway_profile` | SCI2 dag_viz | ⚠️ **PARTIAL** — nodes from trace, edges never created, pathway overlay dead |
| Research type heat map (spec §8.4) | Study design counts per edge | Cross-edge mining | NOT IN CONTRACT | NOT BUILT | 🔮 **PLANNED** |
| Cross-paper pattern detection (spec §8.5) | Recurring findings across papers | Pattern mining | NOT IN CONTRACT | NOT BUILT | 🔮 **PLANNED** |

### Category C: Biopathway Analysis Insights

| Objective | System Output | Algorithm Chain | Contract Field | Presentation | Status |
|-----------|--------------|-----------------|----------------|--------------|--------|
| **O1/O4** Mechanistic pathway representation | 63-node DAG with 20 pathways | A1 graph assembly | NodeMap, edges_v1 | SCI2 dag_viz | ⚠️ **PARTIAL** |
| Pathway activation z-scores | Per-pathway signed activation | C4d → pathway scoring | `report.pathway_profile.pathway_contributions[]` | PAT5 pathway_display | ✅ **WIRED** |
| Pathway dysregulation flags | Binary flags per pathway | Threshold on activation_z | `PathwayContribution.activation_z` | PAT5 pathway_display | ✅ **WIRED** |
| Pathway evidence density/distinction | ED(P) and DS(P) per pathway | B6.5 pathway_evidence_scorer | `PathwayContribution.evidence_density/distinction_score` | PAT5 pathway_display | ✅ **WIRED** — enriched via assembler when B6.5 scores provided |
| Dominant pathway identification | Which pathway drives most impairment | C4d → max activation | `PathwayProfile.dominant_pathway_id` | PAT5 pathway_display | ✅ **WIRED** |
| Key edges per pathway | Which edges contribute most to pathway | B6.5 | `PathwayContribution.key_edges[]` | PAT5 pathway_display | ⚠️ Needs B6.5 data |

### Category D: Subpopulation Stratification / Accessibility

| Objective | System Output | Algorithm Chain | Contract Field | Presentation | Status |
|-----------|--------------|-----------------|----------------|--------------|--------|
| Subpopulation comparison (F5) | Differential effects across cancer types / treatment phases | F5 subpopulation_comparator | `report.subpopulation_comparison` (SubpopulationComparisonSummary) | NOT BUILT (view) | ✅ **WIRED** — contract type added, `_build_subpopulation_summary()` maps F5 result |
| Population archetypes | Cluster profiles from patient pool | GMM clustering (planned) | `population_archetypes_v1` table | ADM4 population_analytics | 🔮 **SCHEMA ONLY** — ORM model exists, no clustering module |
| Context-stratified priors | cancer_type × treatment_phase fallback | C1 prior loader (4-level) | Internal to algorithm | Not a presentation output | ✅ **LIVE** (internal) |
| Structured reasoning narrative | Clinician-readable text synthesis | Planned (§8.6) | NOT IN CONTRACT | NOT BUILT | 🔮 **PLANNED** |
| Extraction quality disclosure | Completeness scores, defaults, caveats | completeness_checker | `report.extraction_quality` (ExtractionQualitySummary) | quality_disclosure | ✅ **LIVE** (conditional) |

---

## 2. Complete Output Inventory

### 2.1 The `RecommendationReport` — Single Output Contract

Everything flows through one object: `RecommendationReport` (defined in
[crci/shared/models/output_contracts.py](../crci/shared/models/output_contracts.py)).

| Field | Type | Populated? | Consumer(s) |
|-------|------|------------|-------------|
| `run_id` | `str` | ✅ | **NONE** — no view displays it |
| `subject_ref` | `str` | ✅ | **NONE** |
| `output_mode` | `ReportOutputMode` | ✅ | **NONE** — should gate patient-vs-scientist |
| `composite_score` | `CompositeScore` | ✅ | PAT1 |
| `primary_schedule` | `SchedulePlan` | ✅ | PAT2, SCI3 |
| `alternative_schedules` | `list[SchedulePlan]` | ✅ | PAT2 |
| `pathway_profile` | `PathwayProfile \| None` | ✅ When C4d provided | PAT5, SCI2 |
| `trajectories` | `list[TemporalTrajectory]` | ✅ | PAT3 |
| `variance_decomposition` | `VarianceDecomposition \| None` | ✅ | PAT4, SCI4 |
| `evidence_gaps` | `EvidenceGapReport \| None` | ✅ When provided | SCI1, SCI5 |
| `decision_trace` | `DecisionTrace \| None` | ✅ | PAT4, SCI2, SCI3, SCI4 |
| `clinical_risk` | `ClinicalRiskProfile \| None` | ✅ When F4 provided | risk_dashboard |
| `extraction_quality` | `ExtractionQualitySummary \| None` | ✅ (if provided) | quality_disclosure |
| `sensitivity_report` | `SensitivityReport \| None` | ✅ When ranking provided | SCI5 |
| `safety_flags` | `list[str]` | ✅ | PAT4 (warning banner) |
| `escalation_triggered` | `bool` | ✅ | **NONE** |
| `run_warnings` | `list[str]` | ✅ | **NONE** |
| `engine_version` | `str \| None` | ✅ | SCI4 |
| `timestamp` | `str \| None` | ✅ | SCI4 |

### 2.2 Intermediate Outputs (Not in Report but Available Upstream)

| Output | Produced By | Available At | Why Not in Report |
|--------|------------|--------------|-------------------|
| `FrozenModelState` (β̂, Σ_eff, Λ_prior, P_inclusion) | Chain B compilation | Cut boundary | Too large / internal |
| `PosteriorState` (θ̂, Σ_post) | C3 Bayesian update | After fusion | Summarized via composite_score |
| `MCDraws` (theta0_draws, edge weights, inclusion) | D1 MC sampler | 10,000 × n_nodes | Too large / internal |
| `BundleEffects` (JPO, CCS, γ, interaction completeness) | D3 synergy | After synergy calc | ✅ Wired via SynergyMetrics in SchedulePlan |
| `CRCIRiskEstimate` | F4 risk_estimator | After F4 | ✅ Wired via `_build_clinical_risk()` |
| `SubpopulationComparisonResult` | F5 comparator | After F5 | ✅ Wired via `_build_subpopulation_summary()` |
| `PathwayEvidenceScores` (ED, DS per pathway) | B6.5 | After compilation | ✅ Wired into PathwayContribution (evidence_density, distinction_score) |
| Per-edge variance contributions | F3 variance decomposer | After F3 | ✅ Wired into VarianceDecomposition.per_edge_contributions |
| Sensitivity indices (Sobol) | D4-D6 ranking | After ranking | ✅ Wired via SensitivityReport in RecommendationReport |

---

## 3. Presentation Layer Status

### 3.1 Patient-Facing Views (PRES-PAT)

| ID | Module | File | View Model | Status |
|----|--------|------|-----------|--------|
| PAT1 | CRCI Dashboard | [crci_dashboard.py](../crci/presentation/crci_dashboard.py) | `ScoreDashboardView` | ✅ **LIVE** |
| PAT2 | Intervention Cards | [intervention_cards.py](../crci/presentation/intervention_cards.py) | `InterventionCardsPanel` | ✅ **LIVE** |
| PAT3 | Trajectory Plot | [trajectory_plot.py](../crci/presentation/trajectory_plot.py) | `TrajectoryChartView` | ✅ **LIVE** |
| PAT4 | Uncertainty Panel | [variance_pie.py](../crci/presentation/variance_pie.py) | `UncertaintyPanelView` | ✅ **LIVE** |
| PAT5 | Pathway Display | [pathway_display.py](../crci/presentation/pathway_display.py) | `PathwayDisplayView` | ⚠️ **WIRED** (assembler populates; view needs C4d data upstream) |
| PAT6 | Progress Tracker | [trajectory_plot.py](../crci/presentation/trajectory_plot.py) | `ProgressTrackerView` | ✅ **LIVE** (needs session history) |
| — | Risk Dashboard | [risk_dashboard.py](../crci/presentation/risk_dashboard.py) | `RiskDashboardView` | ⚠️ **WIRED** (assembler populates; view needs F4 data upstream) |
| — | Quality Disclosure | [quality_disclosure.py](../crci/presentation/quality_disclosure.py) | `QualityDisclosureView` | ✅ **LIVE** (conditional) |

### 3.2 Scientist-Facing Views (PRES-SCI)

| ID | Module | File | View Model | Status |
|----|--------|------|-----------|--------|
| SCI1 | Evidence Browser | [evidence_browser.py](../crci/presentation/evidence_browser.py) | `EvidenceBrowserView` | ⚠️ **WIRED** (assembler passes through; view needs evidence_gaps upstream) |
| SCI2 | DAG Visualization | [dag_viz.py](../crci/presentation/dag_viz.py) | `DAGVizView` | ⚠️ **PARTIAL** |
| SCI3 | Provenance Viewer | [provenance_viewer.py](../crci/presentation/provenance_viewer.py) | `ProvenanceChainView` | ✅ **LIVE** |
| SCI4 | Model Inspection | [model_inspection.py](../crci/presentation/model_inspection.py) | `ModelInspectionView` | ✅ **LIVE** |
| SCI5 | Research Dashboard | [research_dashboard.py](../crci/presentation/research_dashboard.py) | `ResearchDashboardView` | ⚠️ **WIRED** (assembler passes through; view needs evidence_gaps upstream) |

### 3.3 Admin Views (PRES-ADM) — Not Implemented

| ID | Module | Status |
|----|--------|--------|
| ADM1 | System Health Dashboard | 🔮 **NOT BUILT** |
| ADM2 | Audit Log Viewer | 🔮 **NOT BUILT** |
| ADM3 | Configuration Manager | 🔮 **NOT BUILT** |
| ADM4 | Population Analytics | 🔮 **NOT BUILT** |

---

## 4. Wiring Gaps & Dead Code

### 4.1 Critical Wiring Bugs — ✅ ALL RESOLVED (2026-02-27)

| # | Gap | Resolution |
|---|-----|------------|
| W1 | `pathway_profile` never populated | ✅ `_build_pathway_profile()` added — maps C4d `PathwayActivation` list → `PathwayProfile` |
| W2 | `evidence_gaps` never populated | ✅ Passthrough param added to `assemble_report()` — `EvidenceGapReport` flows directly |
| W3 | `clinical_risk` never populated | ✅ `_build_clinical_risk()` added — maps F4 `CRCIRiskEstimate` → `ClinicalRiskProfile` with domain breakdown |
| W4 | `SubpopulationComparisonSummary` not in contract | ✅ Added to `output_contracts.py` + `_build_subpopulation_summary()` maps F5 result via duck typing |

### 4.2 Data Lost at Boundaries — ✅ ALL RESOLVED (2026-02-28)

| Lost Data | Where It Dies | Scientific Value | Status |
|-----------|--------------|------------------|--------|
| Cochran's Q, I², random_effects_applied | CompositeState → report_assembler | Heterogeneity reporting (PRISMA) | ✅ **FIXED** — now flows to CompositeScore |
| Synergy diagnostics (JPO, CCS, γ) | BundleEffects → ranker.py | Intervention interaction transparency | ✅ **FIXED** — BundleResult accepted by assembler, SynergyMetrics in SchedulePlan |
| Per-edge variance contributions | VarianceState → report_assembler | Which edges drive uncertainty | ✅ **FIXED** — now in VarianceDecomposition.per_edge_contributions |
| Sensitivity indices (Sobol) | RankingResult → report_assembler | Decision sensitivity analysis | ✅ **FIXED** — SensitivityReport with all D4c indices + top discovery edges |
| Per-domain severity_tier, percentile | CompositeState → CompositeScore | Domain-level clinical grading | ✅ **FIXED** — Φ(-z)×100 percentile, severity tier, confidence_sd per domain |
| `per_draw_safe_a`, `SafetyStatus` | RankingResult → report_assembler | Per-intervention safety detail | ✅ **FIXED** — SAFE_A CrI, P(net_benefit), safety_status on SchedulePlan |

### 4.3 Broken Scripts — ✅ FIXED (2026-02-27)

| Script | Issue | Resolution |
|--------|-------|------------|
| [scripts/generate_output_schemas.py](../scripts/generate_output_schemas.py) | Crashed — imported missing type + bad config ref | ✅ Fixed imports + version; generates 3 schemas |

### 4.4 Production Orchestrator — ✅ BUILT (2026-02-27)

[crci/presentation/render_report.py](../crci/presentation/render_report.py) provides:
- CLI: `python -m crci.presentation --input report.json [--format terminal|json|all] [--branch patient|scientist]`
- `render_report()` API function for programmatic use
- `export_view_models()` runs all 11 presentation modules and exports view-model dicts
- `output_mode` gating: CLINICAL → patient sections, RESEARCH → all sections
- Section filtering via `--sections` or `--branch` flags

---

## 5. Documentation Coverage

### 5.1 Where Outputs Are Documented

| Document | What It Covers | Gaps |
|----------|---------------|------|
| [SYS_PRESENTATION_COMPLETE.md](02_system_specs/SYS_PRESENTATION_COMPLETE.md) | Full spec for 15 subsystems across 3 branches | ✅ Comprehensive |
| [PRESENTATION_AUDIT_AND_IDEAS.md](PRESENTATION_AUDIT_AND_IDEAS.md) | Audit of current code vs spec, data lost at boundaries, improvement ideas | ✅ Detailed |
| [IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) | F4 risk estimator, F5 subpop, future extensions §8.1–8.9 | ✅ Very detailed |
| [output_contracts.py](../crci/shared/models/output_contracts.py) | Pydantic models for all output types | ✅ Complete (SubpopulationComparisonSummary added) |
| [research paper.md §10](../research%20paper.md) | Lists 10 output artifact types | ✅ Covers all |
| [MASTER_PLAN.md](../MASTER_PLAN.md) | System state, pipeline gaps, slice plan | ✅ Current |

### 5.2 What's MISSING (No Single Trace Document Until Now)

Before this document, **no single file** mapped:
- Research objective → algorithm output → contract field → presentation module → rendered view

The closest pieces were scattered across 6+ documents. This document is that
consolidated trace.

---

## 6. What We Have Right Now

### 6.1 End-to-End Working Outputs (data flows from algorithm through to presentation view-model)

| # | Output | What You Get | Condition |
|---|--------|-------------|-----------|
| 1 | **CRCI Composite Score** | z-score, percentile, severity tier, 11-domain bar chart | Always (even on priors-only) |
| 2 | **Ranked Intervention Cards** | Top 5 interventions with SAFE-B score, CrI, stability, dose, duration | Always |
| 3 | **Temporal Trajectory Plot** | Time-series with mean + P10/P90 bands, natural recovery vs intervention | When E-chain data provided |
| 4 | **Uncertainty Panel** | 5-source variance pie, stability class, P(rank1), warning banners | Always |
| 5 | **Provenance Chain** | Sankey/tree: recommendation → score → edges → studies | Always |
| 6 | **Model Inspection** | Prior selection log, SE calibration, assumptions, decision steps | Always |
| 7 | **Progress Tracker** | Session-over-session comparison | When history available |
| 8 | **Quality Disclosure** | Extraction completeness, defaults fired, caveats | When extraction_quality provided |

### 6.2 Fully Implemented But Not Wired (Algorithm code exists, presentation code exists, assembly missing)

| # | Output | Algorithm Module | Presentation Module | Missing Link |
|---|--------|-----------------|--------------------|----|
| 9 | **Clinical Risk P̂(CRCI)** | F4 `risk_estimator.py` (846 lines) | `risk_dashboard.py` (259 lines) | ✅ WIRED — `_build_clinical_risk()` in assembler |
| 10 | **Evidence Gap / EVSI** | F3 `evsi.py` | `evidence_browser.py` (145 lines), `research_dashboard.py` (148 lines) | ✅ WIRED — passthrough param in assembler |
| 11 | **Pathway Profile** | C4d PathwayActivation available | `pathway_display.py` (171 lines) | ✅ WIRED — `_build_pathway_profile()` in assembler |

### 6.3 Algorithm Exists, No Presentation

| # | Output | Algorithm Module | Presentation | Status |
|---|--------|-----------------|-------------|--------|
| 12 | **Subpopulation Comparison** | F5 `subpopulation_comparator.py` | None built (view) | ✅ Contract + assembler wired; presentation view TBD |
| 13 | **Pathway Evidence Scores** | B6.5 `pathway_evidence_scorer.py` | None | ✅ Surfaced via PathwayContribution (evidence_density, distinction_score, edge_coverage) |
| 14 | **Per-Edge Variance Contributions** | F3 (internal) | None | ✅ Wired into VarianceDecomposition.per_edge_contributions |

### 6.4 Planned / Spec'd, Not Built

| # | Output | Spec Reference | Status |
|---|--------|---------------|--------|
| 15 | Predictive risk under intervention (temporal risk curves) | IMPL_PLAN §8.2 | 🔮 Placeholder |
| 16 | Population archetypes / clustering | ADM4 spec, ORM model exists | 🔮 Schema only |
| 17 | Research type heat map | IMPL_PLAN §8.4 | 🔮 Planned |
| 18 | Cross-paper pattern detection | IMPL_PLAN §8.5 | 🔮 Planned |
| 19 | Structured reasoning narrative | IMPL_PLAN §8.6 | 🔮 Planned |
| 20 | Adaptive evidence acquisition scheduler | IMPL_PLAN §8.3 | 🔮 Planned |
| 21 | Test-level ICCTF classification (measure-level) | IMPL_PLAN §8.9 | 🔮 Planned |
| 22 | Clinical calibration pipeline (Platt scaling) | IMPL_PLAN §8.8 | 🔮 Planned |
| 23 | Admin dashboard (ADM1–ADM4) | SYS_PRESENTATION spec | 🔮 Not built |

---

## 7. What Remains To Wire / Build

### Priority 1 — ✅ COMPLETED (2026-02-27)

All four wiring tasks have been implemented and tested (1056 tests pass):

| Task | Status | Files Changed |
|------|--------|---------------|
| Wire F4 `CRCIRiskEstimate` → `clinical_risk` | ✅ Done | `report_assembler.py`, `session.py` |
| Wire F3 EVSI → `evidence_gaps` passthrough | ✅ Done | `report_assembler.py`, `session.py` |
| Add `SubpopulationComparisonSummary` to contracts | ✅ Done | `output_contracts.py`, `report_assembler.py`, `session.py` |
| Wire C4d `PathwayActivation` → `pathway_profile` | ✅ Done | `report_assembler.py`, `session.py` |
| Fix `generate_output_schemas.py` | ✅ Done | `generate_output_schemas.py` |

### Priority 2 — ✅ COMPLETED (2026-02-28)

Boundary data loss fixes:

| Task | Status | Files Changed |
|------|--------|---------------|
| Pass Cochran's Q, I², random_effects to CompositeScore | ✅ Done | `output_contracts.py`, `report_assembler.py` |
| Pass per-edge variance contributions through | ✅ Done | `output_contracts.py`, `report_assembler.py` |
| Pass synergy diagnostics (JPO, CCS, γ) through | ✅ Done | `output_contracts.py`, `report_assembler.py`, `session.py` |
| Wire sensitivity indices (D4c) → SensitivityReport | ✅ Done | `output_contracts.py`, `report_assembler.py`, `session.py` |
| Wire per-domain severity_tier, percentile, confidence_sd | ✅ Done | `report_assembler.py` (uses Φ(-z)×100 + config thresholds) |
| Wire per_draw_safe_a → P(net_benefit), safety_status | ✅ Done | `output_contracts.py`, `report_assembler.py`, `session.py` |
| Surface B6.5 pathway evidence (ED, DS) in PathwayContribution | ✅ Done | `output_contracts.py`, `report_assembler.py`, `session.py` |

### Priority 3 — ✅ COMPLETED (2026-02-27)

| Task | Status | Files Changed |
|------|--------|---------------|
| Build production orchestrator (CLI + API) | ✅ Done | `crci/presentation/render_report.py` (new, 240 lines) |
| Add JSON serialization for all view models | ✅ Done | `export_view_models()` in render_report.py |
| Wire `output_mode` to gate patient vs scientist views | ✅ Done | `_resolve_sections()` in render_report.py |

### Priority 4 — Future Build (spec'd, not started)

Temporal risk curves (§8.2), population archetypes (ADM4), research heat map (§8.4),
cross-paper patterns (§8.5), reasoning narrative (§8.6), clinical calibration (§8.8),
admin dashboard (ADM1-4).

---

## Appendix: Key Files Reference

| Purpose | File |
|---------|------|
| Output contract (Pydantic models) | [crci/shared/models/output_contracts.py](../crci/shared/models/output_contracts.py) |
| Report assembly (Algorithm → Report) | [crci/runtime/report_assembler.py](../crci/runtime/report_assembler.py) |
| Presentation spec | [docs/02_system_specs/SYS_PRESENTATION_COMPLETE.md](02_system_specs/SYS_PRESENTATION_COMPLETE.md) |
| Presentation audit | [docs/PRESENTATION_AUDIT_AND_IDEAS.md](PRESENTATION_AUDIT_AND_IDEAS.md) |
| Risk estimator implementation plan | [docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md) |
| Risk estimator code | [crci/algorithm/chain_f_analytics/risk_estimator.py](../crci/algorithm/chain_f_analytics/risk_estimator.py) |
| Subpopulation comparator code | [crci/algorithm/chain_f_analytics/subpopulation_comparator.py](../crci/algorithm/chain_f_analytics/subpopulation_comparator.py) |
| EVSI code | [crci/algorithm/chain_f_analytics/evsi.py](../crci/algorithm/chain_f_analytics/evsi.py) |
| All presentation modules | [crci/presentation/](../crci/presentation/) |
