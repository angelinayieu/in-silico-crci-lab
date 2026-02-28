# CRCI System — Consolidated Output Stack

> **Purpose**: Single consolidated view of all system outputs organized by **dependency stack** (what flows from what), **purpose category** (clinical outputs vs. analytics vs. auditing), and **implementation status**.
>
> **Last Updated**: 2026-02-28

---

## Quick Status Summary

| Category | Total | Fully Built | Wired | Partial | Planned |
|----------|-------|------------|-------|---------|---------|
| **Patient Clinical Outputs** | 8 | 7 | 1 | 0 | 0 |
| **Evidence/Paper Analytics** | 8 | 3 | 3 | 1 | 1 |
| **Evidence Auditing** | 2 | 1 | 0 | 0 | 1 |
| **System/Admin** | 4 | 0 | 0 | 0 | 4 |
| **Intermediate** (internal use) | 8 | 7 | 1 | 0 | 0 |
| **TOTAL** | 30 | 18 | 5 | 2 | 6 |

---

## Table of Contents

1. [Output Dependency Stack](#1-output-dependency-stack) — what flows from what
2. [Outputs by Purpose Category](#2-outputs-by-purpose-category)
3. [Complete Output Inventory & Implementation Matrix](#3-complete-output-inventory--implementation-matrix)
4. [What's Built vs. Planned](#4-whats-built-vs-planned)
5. [Evidence Auditing & Paper Analytics Workflow](#5-evidence-auditing--paper-analytics-workflow)

---

## 1. Output Dependency Stack

### The Flow: Algorithm Chains → Intermediate States → RecommendationReport → Presentation Views

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALGORITHM CHAINS (A–F)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Chain A1: NodeMap (63 nodes)                                    │
│      ↓                                                            │
│  Chain A3: Edge weights (from studies)                           │
│      ↓                                                            │
│  Chain B1-B6: Evidence compilation → FrozenModelState            │
│      ├─ Prior selection (B2)                                     │
│      ├─ Analysis layer (B4): β̂, SE per edge                     │
│      ├─ Heterogeneity: Cochran's Q, I²                          │
│      └─ Pathway evidence scores (B6.5): ED, DS                   │
│      ↓                                                            │
│  Chain C1-C4d: Bayesian fusion                                   │
│      ├─ C1: Prior loader (context-stratified)                   │
│      ├─ C2: Likelihood from proxies                             │
│      ├─ C3: Posterior (θ̂, Σ_post, z-scores)                    │
│      └─ C4d: Pathway activation → PathwayActivation list        │
│      ↓                                                            │
│  Chain D0-D6: Intervention ranking                               │
│      ├─ D0-D3: Synergy + toxicity effects (BundleEffects/CCS)   │
│      ├─ D1: MC sampler (10,000 draws)                           │
│      ├─ D4-D6: Ranking (Sobol sensitivity, P(net_benefit))      │
│      └─ RT-G: Dose/schedule selection                            │
│      ↓                                                            │
│  Chain E: Temporal projections → TemporalTrajectory[]            │
│      ↓                                                            │
│  Chain F1-F6: Analytics                                          │
│      ├─ F1: Composite scoring                                   │
│      ├─ F2: Stability analysis                                  │
│      ├─ F3: EVSI (evidence gaps, discovery priorities)          │
│      ├─ F4: Clinical risk P̂(CRCI) → CRCIRiskEstimate           │
│      ├─ F5: Subpopulation comparison → SubpopulationComparison  │
│      └─ F6: VarianceDecomposition (per-edge, per-source)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│         INTERMEDIATE OUTPUTS (Algorithm boundaries)              │
├─────────────────────────────────────────────────────────────────┤
│  FrozenModelState (β̂, SE, Λ_prior, P_inclusion, Q, I²)          │
│  PosteriorState (θ̂, Σ_post + per-domain z-scores)              │
│  PathwayActivation[] (per-pathway signed activation)             │
│  MCDraws (10,000 × [θ, edge_weights, inclusion])               │
│  BundleEffects (JPO, CCS, γ)                                    │
│  CRCIRiskEstimate (MC-derived risk + domain breakdown)          │
│  SubpopulationComparisonResult (differential effects)           │
│  VarianceState (per-source, per-edge contributions)             │
│  RankingResult (Sobol indices, decision stability)              │
│  PathwayEvidenceScores (ED, DS per pathway)                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│          REPORT ASSEMBLER (report_assembler.py)                  │
│  Converts: Intermediate states → RecommendationReport fields    │
├─────────────────────────────────────────────────────────────────┤
│  FrozenModelState + PosteriorState                              │
│      → CompositeScore (z, percentile, severity_tier, domains)   │
│                                                                  │
│  BundleEffects + RankingResult                                  │
│      → SchedulePlan[] (primary + alternatives)                  │
│      → SchedulePlan.synergy_metrics (JPO, CCS, γ)              │
│      → SchedulePlan.safety (SAFE_A CrI, P_net_benefit)         │
│      → SensitivityReport (Sobol indices, top edges)             │
│                                                                  │
│  PathwayActivation[] + PathwayEvidenceScores                     │
│      → PathwayProfile (dominant pathway, contributions)         │
│      → PathwayContribution[] (z, ED, DS, key_edges)            │
│                                                                  │
│  CRCIRiskEstimate                                                │
│      → ClinicalRiskProfile (risk %, CrI, domain breakdown)      │
│                                                                  │
│  SubpopulationComparisonResult                                   │
│      → SubpopulationComparisonSummary (diff effects)            │
│                                                                  │
│  VarianceState + RankingResult                                  │
│      → VarianceDecomposition (per-edge, per-source, per-domain) │
│                                                                  │
│  DecisionTrace (extracted from all previous + decision_log)     │
│  EvidenceGapReport (from F3, passed through)                    │
│  ExtractionQualitySummary (if provided)                         │
│                                                                  │
│  ➜ All consolidated into: RecommendationReport                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│      PRESENTATION VIEWS (render_report.py dispatcher)            │
│  Consumes: RecommendationReport + presentation registry         │
├─────────────────────────────────────────────────────────────────┤
│  PATIENT-FACING (output_mode=CLINICAL)                          │
│    PAT1: crci_dashboard (composite_score) → ScoreDashboardView  │
│    PAT2: intervention_cards (schedules) → InterventionCards     │
│    PAT3: trajectory_plot (trajectories) → TrajectoryChart       │
│    PAT4: variance_pie (variance_decomposition) → Uncertainty    │
│    PAT5: pathway_display (pathway_profile) → PathwayDisplay     │
│    PAT6: trajectory_plot (history) → ProgressTracker            │
│    QUA:  quality_disclosure → QualityDisclosure                 │
│    RISK: risk_dashboard (clinical_risk) → RiskDashboard        │
│                                                                  │
│  SCIENTIST-FACING (output_mode=RESEARCH)                        │
│    SCI1: evidence_browser (evidence_gaps) → EvidenceBrowser    │
│    SCI2: dag_viz (decision_trace + pathway_profile)            │
│    SCI3: provenance_viewer (decision_trace) → Provenance       │
│    SCI4: model_inspection (decision_trace) → ModelInspection   │
│    SCI5: research_dashboard (evidence_gaps) → ResearchDash     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Outputs by Purpose Category

### A. Patient Clinical Outputs (in RecommendationReport)

These outputs are generated during a **patient analysis session** and
drive clinical recommendations.

| # | Output | Purpose | Data Source | Implementation | View(s) |
|---|--------|---------|-------------|---------------|----|
| **PC1** | **Composite Score** | Patient posterior dysregulation (z, %, severity tier, domain breakdown) | C3 + F1 | ✅ FULLY BUILT | PAT1 |
| **PC2** | **Primary Schedule** | Top-ranked intervention (drug, dose, duration, safety) | D0-D6 | ✅ FULLY BUILT | PAT2 |
| **PC3** | **Alternative Schedules** | 4 alternatives for patient choice | D0-D6 | ✅ FULLY BUILT | PAT2 |
| **PC4** | **Temporal Trajectories** | Time-series recovery predictions (mean + P10/P90 bands) | E1-E4 | ✅ FULLY BUILT | PAT3 |
| **PC5** | **Uncertainty Panel** | Variance decomposition (5 sources + stability class) | F2, F6 | ✅ FULLY BUILT | PAT4 |
| **PC6** | **Pathway Profile** | Which pathways drive impairment + dominant pathway | C4d | ✅ WIRED (needs C4d upstream) | PAT5 |
| **PC7** | **Clinical Risk Profile** | P̂(CRCI) with CrI, per-domain breakdown | F4 | ✅ WIRED (needs F4 upstream) | risk_dashboard |
| **PC8** | **Quality Disclosure** | Extraction completeness, defaults fired, caveats | extraction_quality param | ✅ FULLY BUILT (conditional) | quality_disclosure |

### B. Evidence & Paper Analytics Outputs

These outputs support **research landscape analysis** and **model inspection**
— used by scientists to understand what evidence drives recommendations.

| # | Output | Purpose | Data Source | Implementation | View(s) |
|---|--------|---------|-------------|---------------|----|
| **EA1** | **Evidence Gaps Report** | Discovery priorities (study designs needed per edge) with EVSI scoring | F3 | ✅ WIRED (flows via param) | SCI1, SCI5 |
| **EA2** | **Edge-Level Evidence Browser** | 118 edges with β̂, SE, k, claim_level, degree, claim_type | B1-B5 (stored in DB) | ✅ FULLY BUILT (DB) | SCI1 |
| **EA3** | **Decision Trace** | Chain of reasoning: recommendation → scores → edges → studies with degrees | All chains | ✅ FULLY BUILT | PAT4, SCI2, SCI3, SCI4 |
| **EA4** | **DAG Visualization** | 63-node mechanistic graph with edge weights from posterior | A1, A3, C3 | ⚠️ PARTIAL (nodes built, edges missing) | SCI2 |
| **EA5** | **Model Inspection** | Prior selection (type, source), SE calibration, assumptions, inclusion flags | B2-B4 | ✅ FULLY BUILT | SCI4 |
| **EA6** | **Provenance Viewer** | Sankey/tree: per-edge forest plot + study metadata + DOI | edge_evidence_v1 | ✅ FULLY BUILT | SCI3 |
| **EA7** | **Sensitivity Report** | Sobol indices (D4c), top 5 discovery edges, decision stability | D4-D6 | ✅ FULLY BUILT (wired) | SCI5 |
| **EA8** | **Subpopulation Comparison** | Differential effects across cancer types / treatment phases | F5 | ✅ WIRED (contract + assembler; no view yet) | — |

### C. Evidence Auditing & Quality Assurance

These outputs support **data validation** and **extraction quality assurance**
— used by curators to verify evidence integrity.

| # | Output | Purpose | Data Source | Implementation | Status |
|---|--------|---------|-------------|---------------|----|
| **AUD1** | **Edge Coherence Flags** | Chain-vs-direct validation; indirect → direct discrepancies → missing mechanisms | B4 | ✅ FULLY BUILT (computed in DB) | ✅ Flags stored; view partial |
| **AUD2** | **Research Type Heat Map** | Study design distribution per edge (RCT %, observational %, etc.) | edge_evidence_v1 | 🔮 PLANNED (spec §8.4) | Not yet built |

### D. System / Admin Outputs (not yet built)

| # | Output | Purpose | Implementation |
|---|--------|---------|-----------------|
| **ADM1** | System Health Dashboard | Algorithm uptime, error tracking, quality metrics | 🔮 NOT BUILT |
| **ADM2** | Audit Log Viewer | Extract change history, user actions, data lineage | 🔮 NOT BUILT |
| **ADM3** | Configuration Manager | Prior overrides, context rules, sensitivity thresholds | 🔮 NOT BUILT |
| **ADM4** | Population Analytics | Cluster profiles, treatment phase archetypes (GMM) | 🔮 SCHEMA ONLY |

---

## 3. Complete Output Inventory & Implementation Matrix

### 3.1 Clinical Outputs — RecommendationReport Fields

The `RecommendationReport` object is the **single sink** for all outputs. One
field per output type.

| Field | Type | Populated | Algorithm Source | Assembler | View(s) | Status |
|-------|------|-----------|--------------|-----------|--------|--------|
| `composite_score` | `CompositeScore` | Always | C3 + F1 | ✅ Direct | PAT1 | ✅ LIVE |
| `primary_schedule` | `SchedulePlan` | Always | D0-D6 + RT-G | ✅ Direct + synergy | PAT2 | ✅ LIVE |
| `alternative_schedules` | `list[SchedulePlan]` | Always | D0-D6 + RT-G | ✅ Direct + synergy | PAT2 | ✅ LIVE |
| `trajectories` | `list[TemporalTrajectory]` | When E data provided | E1-E4 | ✅ Direct | PAT3 | ✅ LIVE |
| `variance_decomposition` | `VarianceDecomposition` | When ranking provided | F2, F6 | ✅ Added per-edge contrib | PAT4, SCI5 | ✅ LIVE |
| `pathway_profile` | `PathwayProfile \| None` | When C4d provided | C4d | ✅ Added 2026-02-27 | PAT5, SCI2 | ✅ WIRED |
| `clinical_risk` | `ClinicalRiskProfile \| None` | When F4 provided | F4 | ✅ Added 2026-02-27 | risk_dashboard | ✅ WIRED |
| `extraction_quality` | `ExtractionQualitySummary \| None` | If provided | param | ✅ Direct | quality_disclosure | ✅ LIVE |
| `evidence_gaps` | `EvidenceGapReport \| None` | When F3 provided | F3 | ✅ Passthrough param | SCI1, SCI5 | ✅ WIRED |
| `decision_trace` | `DecisionTrace \| None` | Always | All chains | ✅ Direct | SCI2, SCI3, SCI4 | ✅ LIVE |
| `safety_flags` | `list[str]` | Always | D0-D3, D6 | ✅ Direct | PAT4 banner | ✅ LIVE |
| `subpopulation_comparison` | `SubpopulationComparisonSummary \| None` | When F5 provided | F5 | ✅ Added 2026-02-27 | — | ✅ WIRED |
| `sensitivity_report` | `SensitivityReport \| None` | When ranking provided | D4-D6 | ✅ Added 2026-02-28 | SCI5 | ✅ WIRED |

### 3.2 Intermediate Outputs (Internal Algorithm Boundaries)

These are produced by algorithm chains **before** hitting the report assembler.
They are **not** in RecommendationReport but are referenced by it.

| Output | Produced By | Type | Size | Wired To | Status |
|--------|------------|------|------|----------|--------|
| **FrozenModelState** | B1-B6 | β̂, SE, Λ, P_incl, Q, I² per edge | 118 edges × 6 numbers | C3, assembler | ✅ LIVE |
| **PosteriorState** | C3 Bayesian | θ̂, Σ_post, z-scores, percentiles | 11 domains + full covariance | D0-D6, assembler | ✅ LIVE |
| **PathwayActivation[]** | C4d | Signed z-scores per pathway | 20 pathways | assembler | ✅ LIVE |
| **MCDraws** | D1 | 10,000 × [θ, edge_weights, include] | ~100 KB | D3, D4-D6 | ✅ LIVE |
| **BundleEffects** | D3 synergy | JPO, CCS, γ, completeness | Per intervention | assembler | ✅ WIRED (added 2026-02-28) |
| **CRCIRiskEstimate** | F4 | MC-derived risk %, CrI, domain breakdown | Calibrated  | assembler → `clinical_risk` | ✅ WIRED |
| **SubpopulationComparisonResult** | F5 | Differential effects per subpop | Per cancer_type × phase | assembler → `subpop_comparison` | ✅ WIRED |
| **VarianceState** | F6 | Per-source, per-edge, per-domain | Full decomposition | assembler → `variance_decomposition` | ✅ WIRED (added 2026-02-28) |
| **RankingResult** | D4-D6 | Sobol indices, P_net_benefit, safety_a | Per intervention | assembler → `sensitivity_report` | ✅ WIRED (added 2026-02-28) |
| **PathwayEvidenceScores** | B6.5 | ED, DS (per pathway), key_edges | Per pathway | assembler → `pathway_profile` | ✅ WIRED (enriched) |

---

## 4. What's Built vs. Planned

### 4.1 Fully Built & Live (Data flows end-to-end; view exists)

| # | Output | Algorithm | Assembler | View | Test |
|---|--------|-----------|-----------|------|------|
| PC1 | Composite Score | ✅ | ✅ | PAT1 ✅ | ✅ |
| PC2 | Primary Schedule | ✅ | ✅ | PAT2 ✅ | ✅ |
| PC3 | Alternative Schedules | ✅ | ✅ | PAT2 ✅ | ✅ |
| PC4 | Trajectories | ✅ | ✅ | PAT3 ✅ | ✅ |
| PC5 | Uncertainty Panel | ✅ | ✅ | PAT4 ✅ | ✅ |
| PC8 | Quality Disclosure | ✅ | ✅ | quality_disclosure ✅ | ✅ |
| EA2 | Edge Browser | ✅ DB | — | SCI1 ✅ | ✅ |
| EA3 | Decision Trace | ✅ | ✅ | SCI3, SCI4 ✅ | ✅ |
| EA5 | Model Inspection | ✅ | ✅ | SCI4 ✅ | ✅ |
| EA6 | Provenance Viewer | ✅ | ✅ | SCI3 ✅ | ✅ |
| AUD1 | Edge Coherence | ✅ | — | SCI4 (partial) ⚠️ | ✅ |
| SCI3 | Provenance View | ✅ | ✅ | ✅ | ✅ |
| SCI4 | Model Inspection | ✅ | ✅ | ✅ | ✅ |

**Count: 13 fully operational**

### 4.2 Wired (Contracts exist, assembler populates, algorithm built, but needs upstream data or view TBD)

| # | Output | Algorithm | Contract | Assembler | View | Status |
|---|--------|-----------|----------|-----------|------|--------|
| PC6 | Pathway Profile | ✅ (C4d) | ✅ | ✅ 2026-02-27 | PAT5 🔮 (needs C4d in session) | ✅ WIRED |
| PC7 | Clinical Risk | ✅ (F4) | ✅ | ✅ 2026-02-27 | risk_dashboard 🔮 (needs F4 in session) | ✅ WIRED |
| EA1 | Evidence Gaps | ✅ (F3) | ✅ | ✅ param 2026-02-27 | SCI1, SCI5 ✅ | ✅ WIRED |
| EA7 | Sensitivity Report | ✅ (D4-D6) | ✅ | ✅ 2026-02-28 | SCI5 ✅ | ✅ WIRED |
| EA8 | Subpop Comparison | ✅ (F5) | ✅ | ✅ 2026-02-27 | — (view TBD) | ✅ WIRED |

**Count: 5 wired (all core infrastructure in place)**

### 4.3 Partial (Algorithm exists, view partial, or data flow incomplete)

| # | Output | Issue | What's Missing |
|---|--------|-------|-----------------|
| EA4 | DAG Visualization | Nodes built, edges never created | Edge rendering in SCI2 dag_viz.py |
| AUD1 | Edge Coherence | Flags computed + partially shown | Dedicated validation view; full display in SCI4 |

**Count: 2 partial**

### 4.4 Planned (Spec only, not built)

| # | Output | Where Spec'd | Est. Lines | Status |
|---|--------|-------------|-----------|--------|
| AUD2 | Research Type Heat Map | IMPL_PLAN §8.4 | ~150 | 🔮 PLANNED |
| Pattern Detection | Cross-paper patterns | IMPL_PLAN §8.5 | ~200 | 🔮 PLANNED |
| Reasoning Narrative | Narrative text synthesis | IMPL_PLAN §8.6 | ~300 | 🔮 PLANNED |
| Test-Level ICCTF | Measure-level classification | IMPL_PLAN §8.9 | ~100 | 🔮 PLANNED |
| Clinical Calibration | Platt scaling pipeline | IMPL_PLAN §8.8 | ~200 | 🔮 PLANNED |
| Temporal Risk Curves | Risk under intervention | IMPL_PLAN §8.2 | ~150 | 🔮 PLANNED |
| ADM1-ADM4 | Admin dashboards | SYS_PRESENTATION spec | ~1000 | 🔮 PLANNED |

**Count: 7 planned (future)**

---

## 5. Evidence Auditing & Paper Analytics Workflow

### 5.1 Evidence Auditing Objectives

When a paper is **extracted**, the system:
1. Loads structured claims + study metadata
2. Computes **per-edge evidence quality** (B1-B6):
   - Evidence density (number of studies, k)
   - Study designs (balance of RCTs vs. observational)
   - SE calibration (heterogeneity: Q, I²)
   - Prior credibility
3. Checks **chain coherence** (B4):
   - Do indirect chains (A→B→C) match direct (A→C) effects?
   - Flags discrepancies for curation
4. Generates **discovery priorities** (F3 EVSI):
   - Which edges need more evidence?
   - What study designs would reduce posterior variance most?

### 5.2 Current Auditing Outputs

| Auditing Task | Output | Where Built | Where Stored | Where Viewed |
|---------------|--------|------------|--------------|-------------|
| Extraction completeness | `ExtractionQualitySummary` | completeness_checker | RecommendationReport | quality_disclosure |
| Per-edge evidence density | `edge_evidence_v1` table | B1-B5 | Database | SCI1 (edge_browser) |
| Heterogeneity (Q, I²) | `CompositeScore.heterogeneity_*` | B5, C3 | Database | PAT5 (implicit) |
| Prior credibility | `edge_analysis_v1.prior_*` | B2-B4 | Database | SCI4 (model_inspection) |
| Coherence flags | `edge_analysis_v1.coherence_*` | B4 | Database | SCI4 (partial) |
| Discovery priorities | `EvidenceGapReport` | F3 EVSI | RecommendationReport | SCI1, SCI5 |

### 5.3 Paper Analytics Workflow (High-Level)

```
NEW PAPER EXTRACTION
       ↓
  01_PROCEDURE.md (Steps 0-10)
       ↓
  Extract claims: edges, study metadata, effect sizes
       ↓
  Load into: edge_evidence_v1, edge_analysis_v1 tables
       ↓
  Trigger B-chain jobs:
    ├─ B1: Count studies per edge
    ├─ B2: Select prior
    ├─ B3: Estimate SE (calibration)
    ├─ B4: Flag coherence issues
    ├─ B5: Pool evidence (meta-analysis if k>1)
    └─ B6.5: Pathway evidence scoring (ED, DS)
       ↓
  Store: FrozenModelState (per session)
       ↓
  On next patient analysis:
    1. Load FrozenModelState
    2. Run C3 Bayesian fusion
    3. Assemble report
    4. Display Evidence Browser (SCI1) showing:
       - All 118 edges with β̂, SE, k, claim_level
       - Coherence flags (chain-vs-direct)
       - Prior assumptions
       - Study design breakdown
    5. Display Research Dashboard (SCI5) showing:
       - EVSI discovery priorities
       - Which edges have highest variance?
       - What study designs needed?
```

### 5.4 Evidence Auditing Checklist (per-paper)

When curating a **new paper**, verify:

- [ ] **Extraction completeness**: All edges claimed in paper are extracted
- [ ] **Study metadata**: k, design (RCT/observational/case report), year, sample size
- [ ] **Effect sizes**: β̂, SE (or 95% CI for conversion), direction
- [ ] **Prior selection**: Justified based on claim type (mechanism vs. empirical)
- [ ] **Coherence**: Chains consistent (A→B + B→C consistent with A→C)
- [ ] **Evidence density**: Tracked (for future EVSI optimization)
- [ ] **Defaults flagged**: Any missing data filled in? Logged.

View results in:
- `quality_disclosure` → extraction completeness
- `SCI4 (model_inspection)` → prior assumptions + coherence flags
- `SCI1 (evidence_browser)` → edge-level evidence + study designs
- `SCI5 (research_dashboard)` → discovery priorities (F3)

---

## Summary: Outputs at a Glance

### What Flows to the Patient
✅ **Composite Score** (dysregulation z-score + domain breakdown)
✅ **Ranked Schedules** (5 interventions with dose/duration/safety)
✅ **Trajectories** (recovery time-series with bands)
✅ **Uncertainty breakdown** (which factors drive uncertainty)
✅ **Pathway profile** (which biological mechanisms involved)
✅ **Clinical risk** (P̂(CRCI) with confidence)
✅ **Quality disclosure** (data gaps + caveats)

### What Flows to the Scientist
✅ **Evidence gaps** (discovery priorities + EVSI scoring)
✅ **Edge browser** (all 118 edges with evidence quality)
✅ **Decision trace** (sankey: recommendation → scores → edges → studies)
✅ **DAG visualization** (mechanistic graph)
✅ **Model inspection** (priors, assumptions, coherence flags)
✅ **Provenance** (per-edge forest plots + DOI)
✅ **Sensitivity analysis** (which edges drive top decisions)
✅ **Subpopulation comparison** (diff effects by cancer type)

### What's Planned for Future
🔮 Research heat map (study design distribution per edge)
🔮 Cross-paper patterns (recurring findings)
🔮 Clinical narrative (text synthesis)
🔮 Admin dashboards (health, audit, config, population analytics)
🔮 Temporal risk curves (risk under intervention over time)

---

## Key Files Reference

| Purpose | File |
|---------|------|
| Output contract (Pydantic) | [crci/shared/models/output_contracts.py](../crci/shared/models/output_contracts.py) |
| Report assembly | [crci/runtime/report_assembler.py](../crci/runtime/report_assembler.py) |
| Presentation dispatch | [crci/presentation/render_report.py](../crci/presentation/render_report.py) |
| All patient views | [crci/presentation/](../crci/presentation/) (PAT1-6, QUA, RISK) |
| All scientist views | [crci/presentation/](../crci/presentation/) (SCI1-5) |
| Session orchestrator | [crci/runtime/session.py](../crci/runtime/session.py) |
| Risk estimator (F4) | [crci/algorithm/chain_f_analytics/risk_estimator.py](../crci/algorithm/chain_f_analytics/risk_estimator.py) |
| EVSI (F3) | [crci/algorithm/chain_f_analytics/evsi.py](../crci/algorithm/chain_f_analytics/evsi.py) |
| Subpop comparator (F5) | [crci/algorithm/chain_f_analytics/subpopulation_comparator.py](../crci/algorithm/chain_f_analytics/subpopulation_comparator.py) |
