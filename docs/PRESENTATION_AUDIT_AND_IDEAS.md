# Presentation Layer: Current State, Wiring Gaps & Improvement Ideas

> **Purpose**: Comprehensive audit of what the presentation layer currently renders,
> what pipeline data is lost before it reaches the user, and prioritized ideas
> for improvement.
>
> **Generated**: 2025-01-XX — based on full codebase audit of `crci/presentation/`,
> `output_contracts.py`, `report_assembler.py`, and upstream algorithm chains.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Current Presentation Modules](#2-current-presentation-modules)
3. [Data Lost at Boundaries](#3-data-lost-at-boundaries)
4. [Report Fields Never Surfaced](#4-report-fields-never-surfaced)
5. [Improvement Ideas — Ranked](#5-improvement-ideas--ranked)
6. [Implementation Effort Matrix](#6-implementation-effort-matrix)

---

## 1. Architecture Overview

The data flow is:

```
Algorithm Chains (A→F) ──► report_assembler.py ──► RecommendationReport ──► Presentation Modules
                                    ▲                       │
                           RankedSchedules (RT-G)           │
                           CompositeState (F1)              ├── crci_dashboard.py   (PAT1)
                           StabilityState (F2)              ├── intervention_cards.py (PAT2)
                           VarianceState (F3)               ├── trajectory_plot.py   (PAT3)
                           RecoveryTrajectory (E2)          ├── variance_pie.py      (PAT4)
                           OverlayResult (E3)               ├── pathway_display.py   (PAT5)
                           UncertaintyResult (E4)           ├── evidence_browser.py  (SCI1)
                                                            ├── dag_viz.py           (SCI2)
                                                            ├── provenance_viewer.py (SCI3)
                                                            ├── model_inspection.py  (SCI4)
                                                            └── research_dashboard.py(SCI5)
```

**Single chokepoint**: Everything flows through `RecommendationReport`. If data isn't in that contract, no presentation module can render it.

---

## 2. Current Presentation Modules

### 2.1 Patient-Facing Views

#### PAT1 — CRCI Dashboard (`crci_dashboard.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-PAT1 (SYS_PRESENTATION lines 103–116) |
| **Consumes** | `report.composite_score` (CompositeScore) |
| **Renders** | `ScoreDashboardView` — gauge/dial with severity tier, percentile, 11-domain bar chart, delta from previous session |

**Fields actually used from CompositeScore**:
- `composite_z`, `composite_percentile`, `overall_severity`, `domain_scores` (only `domain_id`, `domain_label`, `z_score`)

**Fields available but NOT surfaced**:
- Per-domain `severity_tier`, `percentile`, `contributing_nodes`, `confidence_sd`
- `population_norm_used`, `calibration_mode`

**Upstream data lost before reaching this view**:
- `CompositeState.cochrans_Q`, `I_squared`, `random_effects_applied` — heterogeneity statistics from F1 never enter `CompositeScore`

---

#### PAT2 — Intervention Cards (`intervention_cards.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-PAT2 (SYS_PRESENTATION lines 117–131) |
| **Consumes** | `report.primary_schedule`, `report.alternative_schedules` |
| **Renders** | `InterventionCardsView` — ranked cards with SAFE-B, evidence badges, stability indicator, dose, duration |

**Fields actually used from SchedulePlan**:
- `actions[].action_label`, `dose_value`, `dose_unit`, `duration_days`
- `cri_95_lower`, `cri_95_upper`, `plan_rank`, `utility_score`, `plan_type`, `stability_class`
- Bundle detection: `len(actions) > 1` → `is_bundle`, `bundle_members`

**Fields available but NOT surfaced**:
- `p_rank_1`, `expected_outcomes`, `risk_summary`, `rationale`, `constraints_applied`, `warnings`
- Per-action: `action_class`, `timing_summary`, `frequency`, `expected_benefit_z`, `rationale`

**Upstream data lost**:
- All synergy diagnostics (JPO, CCS, γ, interaction completeness) — die at `ranker.py` boundary
- `BundleRanking` carries only `delta_C_bundle` and `member_ids`
- `RankingResult.sensitivity_indices`, `dose_recommendations`, `per_draw_safe_a`, `SafetyStatus`

---

#### PAT3 — Trajectory Plot (`trajectory_plot.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-PAT3 (lines 132–145) + PRES-PAT6 (lines 171–180) |
| **Consumes** | `report.trajectories` (list[TemporalTrajectory]) |
| **Renders** | `TrajectoryPlotView` — time-series with mean + P10/P90 bands; `ProgressTrackerView` (PAT6) — historical session comparison |

**Fields actually used**:
- `scenario_id`, `scenario_label`, `horizon_days`
- Per-node: `node_id`, `points[].day`, `z_mean`, `z_p10`, `z_p90`

**Fields NOT surfaced**:
- `time_step_unit`, `NodeTrajectory.node_label`, `final_delta_z`, `TrajectoryPoint.z_sd`

**Status**: Well-wired. PAT6 requires external session history (not from report).

---

#### PAT4 — Variance Pie / Uncertainty Panel (`variance_pie.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-PAT4 (lines 147–159) |
| **Consumes** | `report.variance_decomposition`, `report.decision_trace`, `report.safety_flags` |
| **Renders** | `UncertaintyPanelView` — 5-source pie chart, confidence statement, UNSTABLE warning banner |

**Fields actually used**:
- `VarianceDecomposition.components[].source`, `.fraction`, `.dominant_source`
- `DecisionTrace.entries` — scans for `stability_assessment` step → P(rank1) and stability class
- `safety_flags` — checks for "HIGHLY_UNSTABLE_WARNING"

**Fields NOT surfaced**:
- `total_variance`, per-component `description`

**Critical gaps**:
- No 6th slice for "interaction uncertainty" (synergy variance inflation exists upstream but is lost)
- `per_edge_variance_contrib` from `VarianceState` is lost at `report_assembler` — would show which specific edges drive uncertainty

---

#### PAT5 — Pathway Display (`pathway_display.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-PAT5 (lines 161–169) |
| **Consumes** | `report.pathway_profile` (PathwayProfile) |
| **Renders** | `PathwayDisplayView` — heatmap with direction-aware colors, dysregulation flags, tooltips |

**Fields actually used**:
- `pathway_contributions[].pathway_id`, `.pathway_label`, `.activation_z`, `dominant_pathway_id`

**Fields NOT surfaced**:
- `contribution_fraction`, `key_edges`, `evidence_quality`, `coverage_fraction`

**CRITICAL**: `pathway_profile` is **never populated** by `assemble_report()` — this view always hits its empty-state code path. Dead code in production.

---

### 2.2 Scientist-Facing Views

#### SCI1 — Evidence Browser (`evidence_browser.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-SCI1 (lines 218–229) |
| **Consumes** | `report.evidence_gaps` (EvidenceGapReport) |
| **Renders** | `EvidenceBrowserView` — sortable/filterable table with gap highlighting, EVSI ranking |

**Status**: Well-implemented; surfaces all `EvidenceGapItem` fields.

**CRITICAL**: `evidence_gaps` is **never populated** by `assemble_report()` — always `None`. Dead code in production.

---

#### SCI2 — DAG Visualization (`dag_viz.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-SCI2 (lines 231–242) |
| **Consumes** | `report.pathway_profile`, `report.decision_trace` |
| **Renders** | `DAGVizView` — 63-node graph with domain coloring and pathway highlights |

**PARTIAL IMPLEMENTATION**:
- `DAGEdge` is defined in the view model but **no edges are ever created**
- Only creates nodes from decision trace recommendation entries
- Spec calls for 63-node, 118-edge graph with edge thickness ∝ |β| — not implemented
- `pathway_profile` is never populated (see PAT5), so pathway highlights are always empty
- `PathwayContribution.activation_z`, `contribution_fraction`, `evidence_quality` all unsurfaced

---

#### SCI3 — Provenance Viewer (`provenance_viewer.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-SCI3 (lines 244–253) |
| **Consumes** | `report.decision_trace`, `report.primary_schedule` |
| **Renders** | `ProvenanceChainView` — Sankey/tree tracing recommendation → score → edges |

**Fields actually used**:
- `DecisionTrace.entries` — switched by step type (session_start, stability_assessment, recommendation)
- `DecisionTrace.decision_critical_edges`
- `primary_schedule.utility_score`, `plan_rank`, `stability_class`

**Fields NOT surfaced**:
- `p_rank_1`, `expected_outcomes`, `risk_summary`, `rationale`, `cri_95_lower/upper`
- `DecisionTraceEntry.inputs`, `.confidence` (partially)

---

#### SCI4 — Model Inspection (`model_inspection.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-SCI4 (lines 255–266) |
| **Consumes** | `report.decision_trace`, `report.engine_version`, `report.timestamp` |
| **Renders** | `ModelInspectionView` — prior selection log, SE calibration, assumptions, decision steps |

**External data required (NOT from report)**:
- `prior_log: list[PriorSelectionRow]` — must be assembled externally
- `se_calibration: list[SECalibrationRow]` — must be assembled externally

**Gap**: No upstream code produces `PriorSelectionRow` or `SECalibrationRow` lists. The rendering logic is complete, but the data pipeline is absent.

---

#### SCI5 — Research Dashboard (`research_dashboard.py`)
| Attribute | Value |
|---|---|
| **Spec** | PRES-SCI5 (lines 268–278) |
| **Consumes** | `report.evidence_gaps` (EvidenceGapReport) |
| **Renders** | `ResearchDashboardView` — sortable gap table with EVSI, recommended study designs |

**CRITICAL**: Same issue as SCI1 — `evidence_gaps` is never populated. Dead code.

---

## 3. Data Lost at Boundaries

### 3.1 Lost at `report_assembler.py` (Algorithm → RecommendationReport)

| Upstream State | Fields Lost | Scientific Value |
|---|---|---|
| **CompositeState** (F1) | `cochrans_Q`, `I_squared`, `random_effects_applied`, `severity_weighted_z`, `n_domains`, `subdomain_weights` | Heterogeneity of evidence across domains – required for paper reporting (PRISMA) |
| **StabilityState** (F2) | `pairwise_dominance`, `flip_counts`, `n_draws`, `n_interventions` | How often interventions swap ranks across MC draws – decision robustness |
| **VarianceState** (F3) | `per_edge_variance_contrib`, raw `literature/measurement/structural/proxy/missing_variance` (only percentages flow) | Which specific edges are the biggest uncertainty drivers |
| **RankingResult** (D4–D6) | `sensitivity_indices`, `top_discovery_edges`, `dose_recommendations` (full detail), `per_draw_safe_a`, `SafetyStatus` per intervention | Dose-response detail, safety flags per intervention, sensitivity analysis |
| **BundleEffects** (D3) | `pairwise_metrics` (JPO, CCS, γ, jpo_sd, ccs_sd, gamma_empirical), `joint_propagation_used`, `interaction_completeness`, `k_way_variance_inflation` | All synergy diagnostics — completely invisible to user |
| **PathwayProfile** | Correctly passed through | — |
| **EvidenceGapReport** | **Never populated** (field exists but `assemble_report()` never sets it) | Evidence quality assessment unavailable despite schema existing |

### 3.2 Lost at `ranker.py` (D3 → D4–D6)

| D3 Data | What Survives | What Dies |
|---|---|---|
| `BundleEffects.delta_C_bundle` | ✅ → `BundleRanking.delta_C_bundle` | — |
| `BundleEffects.member_ids` | ✅ → `BundleRanking.member_ids` | — |
| `BundleEffects.pairwise_metrics` | ❌ | JPO, CCS, γ values + uncertainty (SD) |
| `BundleEffects.joint_propagation_used` | ❌ | Whether superposition fix was active |
| `BundleEffects.interaction_completeness` | ❌ | Fraction of k≥3 interactions covered |
| `BundleEffects.k_way_variance_inflation` | ❌ | Variance inflation from unmeasured interactions |

### 3.3 Never Populated Despite Schema Existing

| Report Field | Schema Location | Wiring Status |
|---|---|---|
| `evidence_gaps` | `EvidenceGapReport` in `output_contracts.py` | ❌ Never set by `assemble_report()` |
| `pathway_profile` | `PathwayProfile` in `output_contracts.py` | ❌ Never set by `assemble_report()` |

---

## 4. Report Fields Never Surfaced by ANY View

| `RecommendationReport` Field | Current Consumer |
|---|---|
| `run_id` | **NONE** — no view displays it |
| `subject_ref` | **NONE** |
| `output_mode` | **NONE** — should gate patient-vs-scientist view selection |
| `escalation_triggered` | **NONE** — safety-critical field with no UI |
| `run_warnings` | **NONE** |

---

## 5. Improvement Ideas — Ranked

### Ranking Criteria

Each idea is scored 1–5 on three axes:

| Axis | Description |
|---|---|
| **Scientific Rigor** | How much this improves defensibility of the system in a peer-reviewed paper |
| **User Impact** | How much this improves the actionability / transparency of outputs |
| **Effort** | Implementation complexity (5 = trivial, 1 = major architectural change) |

**Priority Score** = (Scientific Rigor × 2) + (User Impact × 1.5) + (Effort × 0.5)

---

### Tier 1 — Must Do

#### 1. Wire `evidence_gaps` into `assemble_report()` 🔴
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 5 |
| Effort | 4 |
| **Priority Score** | **19.5** |

**What**: The `EvidenceGapReport` schema exists, `evidence_browser.py` (SCI1) and `research_dashboard.py` (SCI5) are fully implemented, but `assemble_report()` never populates the field. Two complete presentation modules are dead code.

**Why must-do**: Any peer reviewer will ask "how do you disclose evidence gaps?" The code exists — it just isn't connected. This is a wiring bug, not a design gap.

**How**: In `assemble_report()`, accept `evidence_gap_report: EvidenceGapReport | None` as a parameter, set `evidence_gaps=evidence_gap_report` on the RecommendationReport. Upstream, the F3 EVSI module + gap compiler should produce this. If the gap compiler doesn't exist yet, raise `NotImplementedError` but fix the wiring.

---

#### 2. Wire `pathway_profile` into `assemble_report()` 🔴
| Axis | Score |
|---|---|
| Scientific Rigor | 4 |
| User Impact | 5 |
| Effort | 4 |
| **Priority Score** | **17.5** |

**What**: `PathwayProfile` schema exists, `pathway_display.py` (PAT5) is fully implemented, but `assemble_report()` never sets it. PAT5 and SCI2 pathway highlights are dead.

**Why must-do**: Pathway profiles are a core differentiator of the CRCI system (biological mechanism transparency). Having the schema + renderer but no wiring is confusing and wastes implemented work.

**How**: The Chain A graph should produce pathway assignments. In `assemble_report()`, accept and forward `PathwayProfile`. If chain_a doesn't produce it yet, document the gap.

---

#### 3. Surface `escalation_triggered` + `run_warnings` + `output_mode` 🔴
| Axis | Score |
|---|---|
| Scientific Rigor | 4 |
| User Impact | 5 |
| Effort | 5 |
| **Priority Score** | **18.0** |

**What**: Three safety/routing fields in `RecommendationReport` are never consumed by any presentation module:
- `escalation_triggered` — a boolean that should trigger a prominent safety warning
- `run_warnings` — marginal recommendation warnings
- `output_mode` — should gate which views are shown (patient vs. scientist)

**Why must-do**: `escalation_triggered` is safety-critical. If the system flags escalation but no UI displays it, the patient gets unsafe silence. `output_mode` routing is core to the two-audience design.

**How**:
- Add an `EscalationBanner` to PAT1 (crci_dashboard) or a standalone safety module
- Render `run_warnings` as a dismissible notice bar
- Use `output_mode` via a `view_router.py` to select patient-only or patient+scientist views

---

#### 4. Surface Synergy/Interaction Diagnostics on Bundle Cards 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 4 |
| Effort | 3 |
| **Priority Score** | **17.0** |

**What**: Synergy metadata (JPO, CCS, γ, interaction completeness) dies at the ranker boundary. Bundle intervention cards show `is_bundle` and `bundle_members` but zero information about *how* the bundle components interact.

**Why must-do**: Our pairwise interaction fixes (joint propagation, cascade JPO, antagonistic γ, completeness scoring) produce scientifically valuable diagnostics that the user never sees. In a paper, you can't claim "we model synergies" if no output discloses the synergy values.

**How**:
1. Add `synergy_summary: dict | None` to `BundleRanking` in `ranker.py` (carry through JPO mean±SD, CCS mean±SD, γ, completeness)
2. Add `synergy_summary: dict | None` to `SchedulePlan` in `output_contracts.py`
3. Forward through `report_assembler.py`
4. Render in `intervention_cards.py` as a collapsible "Interaction Details" panel

---

#### 5. Add 6th Variance Slice: "Interaction Uncertainty" 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 4 |
| Effort | 3 |
| **Priority Score** | **17.0** |

**What**: The variance pie shows 5 sources (literature, measurement, structural, proxy, missing). Synergy/interaction uncertainty from `k_way_variance_inflation` and JPO/CCS SDs is computed upstream but never reaches the variance decomposition.

**Why must-do**: The 5-source pie claims to be a complete uncertainty breakdown, but it omits interaction uncertainty entirely. This is a silent model assumption that reviewers will catch.

**How**:
1. Add `"interaction"` as a 6th source in `VarianceComponent`
2. In `variance_decomposer.py`, compute interaction variance fraction from `BundleEffects.k_way_variance_inflation`
3. Renormalize the 5 existing fractions to make room for the 6th
4. Update `variance_pie.py` color map and description lookup

---

### Tier 2 — Strongly Recommended

#### 6. Complete DAG Visualization (SCI2) with Actual Edges 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 4 |
| User Impact | 4 |
| Effort | 3 |
| **Priority Score** | **15.5** |

**What**: `dag_viz.py` defines `DAGEdge` in its view model but **never creates any edges**. It only creates nodes from decision trace recommendations. The spec calls for a 63-node, 118-edge graph with edge thickness ∝ |β|.

**Why**: A "DAG visualization" without edges is misleading. This is the primary tool for causal model transparency. The graph topology exists in Chain A — it just needs to be forwarded.

**How**: Add a `graph_topology: list[tuple[str,str,float]] | None` field to `RecommendationReport` (or pass via a separate channel). Populate edges from the frozen B̂ matrix.

---

#### 7. Surface Per-Edge Variance Contributions 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 3 |
| Effort | 3 |
| **Priority Score** | **15.0** |

**What**: `VarianceState.per_edge_variance_contrib` exists upstream but only aggregate percentages flow into `VarianceDecomposition`. Scientists can't see *which* edges drive uncertainty.

**Why**: This is one of the most actionable pieces of information for researchers — "collect more data on edge X to reduce overall uncertainty by Y%." The information exists, it just isn't forwarded.

**How**: Add `edge_contributions: list[dict] | None` to `VarianceDecomposition`. Forward from `VarianceState.per_edge_variance_contrib`. Render as a sortable table in `variance_pie.py` or a new dedicated view.

---

#### 8. Populate Model Inspection Data Pipeline (SCI4) 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 4 |
| User Impact | 3 |
| Effort | 2 |
| **Priority Score** | **13.0** |

**What**: `model_inspection.py` requires `PriorSelectionRow` and `SECalibrationRow` lists that no upstream code produces. The renderer is complete; the data feed is empty.

**Why**: Prior selection transparency is core to Bayesian credibility. Showing "we used prior X because study Y with k evidence" is essential for reproducibility.

**How**: During Chain B (evidence → prior), log `PriorSelectionRow` entries. During extraction, log `SECalibrationRow` entries. Forward via `DecisionTrace` or a new report field.

---

#### 9. Disclose D Matrix Correlations in Outputs 🟡
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 2 |
| Effort | 4 |
| **Priority Score** | **14.5** |

**What**: The D matrix has 8 residual correlation pairs (IL-6↔TNF-α ρ=0.65, etc.) that affect MC sampling. These correlations are fixed constants in `config.py` with no disclosure in any output.

**Why**: Residual correlations are a structural assumption of the model. Any sensitivity analysis should vary them, and any transparency report should disclose them. Currently invisible.

**How**: Add a `model_assumptions` section to `RecommendationReport` or include in `model_inspection.py`. Render as a correlation heatmap.

---

#### 10. Surface Cochran's Q and I² Statistics
| Axis | Score |
|---|---|
| Scientific Rigor | 5 |
| User Impact | 2 |
| Effort | 5 |
| **Priority Score** | **15.0** |

**What**: `CompositeState` computes Cochran's Q and I² (heterogeneity measures) but these are lost at the `report_assembler` boundary.

**Why**: Q and I² are standard meta-analysis reporting requirements (PRISMA). Any paper reporting pooled effects should disclose heterogeneity.

**How**: Add `heterogeneity_Q: float | None` and `I_squared: float | None` to `CompositeScore`. Forward from `CompositeState`. Render in PAT1 dashboard or SCI4 model inspection.

---

### Tier 3 — Nice to Have

#### 11. Structured Reasoning Narrative Compiler
| Axis | Score |
|---|---|
| Scientific Rigor | 3 |
| User Impact | 4 |
| Effort | 2 |
| **Priority Score** | **12.0** |

**What**: Generate a natural-language paragraph explaining *why* intervention X is ranked #1 — tracing from biological mechanism through evidence strength to expected benefit.

**Why**: Clinicians and patients don't read bar charts — they read sentences. A "recommendation rationale" paragraph would be the most-read output.

**How**: Template-based NLG using decision trace entries, top contributing edges, stability class. Could leverage LLM module for polishing.

---

#### 12. Research Type Heat Map (Edge × Study Design)
| Axis | Score |
|---|---|
| Scientific Rigor | 4 |
| User Impact | 2 |
| Effort | 2 |
| **Priority Score** | **12.0** |

**What**: A matrix showing, for each edge in the DAG, which study designs support it (RCT, observational, case-control, etc.) and how many studies.

**Why**: Identifies where evidence is thin or relies on weak designs. Useful for research prioritization.

**How**: Query extraction metadata (study design tags per edge). Render as a heatmap in SCI5 or a new view.

---

#### 13. Cross-Paper Pattern Detection Report
| Axis | Score |
|---|---|
| Scientific Rigor | 3 |
| User Impact | 2 |
| Effort | 1 |
| **Priority Score** | **9.0** |

**What**: Identify when multiple papers report conflicting effect directions for the same edge, or when dose-response patterns emerge across studies.

**Why**: Conflict patterns indicate either measurement heterogeneity or true biological complexity. Disclosure improves model credibility.

**How**: Requires cross-study comparison logic in extraction/evidence layer. Moderate implementation effort.

---

#### 14. Adaptive Intensity Ramp Scheduling Visualization
| Axis | Score |
|---|---|
| Scientific Rigor | 2 |
| User Impact | 3 |
| Effort | 2 |
| **Priority Score** | **8.5** |

**What**: Show how intervention doses ramp up/down over the schedule timeline. Currently, dose is flat for each action.

**Why**: Dose timing affects adherence and safety. Visual ramp charts help patients understand their schedule.

**How**: Extend `ScheduleAction` with `dose_schedule: list[tuple[int, float]]` (day, dose). Render as a stepped line chart.

---

#### 15. Schedule Timing Variant Explorer
| Axis | Score |
|---|---|
| Scientific Rigor | 2 |
| User Impact | 3 |
| Effort | 2 |
| **Priority Score** | **8.5** |

**What**: Allow comparing different timing variants of the same intervention (morning vs. evening, 3x vs. 5x/week).

**Why**: Timing can significantly affect efficacy (e.g., exercise timing relative to chemotherapy cycles).

**How**: Extend schedule generator to produce timing variants. Render as swipeable cards or tabs.

---

## 6. Implementation Effort Matrix

| # | Idea | Files to Modify | Estimated LOC | Dependencies |
|---|---|---|---|---|
| 1 | Wire evidence_gaps | `report_assembler.py` | ~15 | F3/EVSI gap compiler upstream |
| 2 | Wire pathway_profile | `report_assembler.py` | ~10 | Chain A pathway assignment upstream |
| 3 | Surface escalation/warnings/mode | `crci_dashboard.py`, new `view_router.py` | ~80 | None |
| 4 | Synergy diagnostics on cards | `ranker.py`, `output_contracts.py`, `report_assembler.py`, `intervention_cards.py` | ~120 | D3 synergy data (exists) |
| 5 | 6th variance slice | `output_contracts.py`, `variance_decomposer.py`, `report_assembler.py`, `variance_pie.py` | ~80 | D3 k_way_variance_inflation (exists) |
| 6 | Complete DAG edges | `dag_viz.py`, `report_assembler.py` or new channel | ~100 | Frozen B̂ matrix access |
| 7 | Per-edge variance | `output_contracts.py`, `report_assembler.py`, `variance_pie.py` or new view | ~60 | VarianceState (exists) |
| 8 | Model inspection pipeline | Chain B logging, extraction logging, `report_assembler.py` | ~200 | Prior selection + SE calibration logs |
| 9 | D matrix disclosure | `model_inspection.py` or new view, `output_contracts.py` | ~50 | config.py constants (exist) |
| 10 | Cochran's Q / I² | `output_contracts.py`, `report_assembler.py`, `crci_dashboard.py` | ~30 | CompositeState (exists) |
| 11 | Reasoning narrative | New `narrative_compiler.py` | ~200 | DecisionTrace + edge metadata |
| 12 | Research type heat map | New view + extraction query | ~150 | Study design metadata |
| 13 | Cross-paper patterns | New analysis module + view | ~300+ | Cross-study comparison logic |
| 14 | Dose ramp visualization | `output_contracts.py`, new view | ~100 | Schedule generator extension |
| 15 | Timing variant explorer | Schedule generator, new view | ~200 | Timing variant logic |

---

## Summary: Priority Order

| Priority | # | Idea | Status |
|---|---|---|---|
| **19.5** | 1 | Wire `evidence_gaps` | Wiring bug — schema + renderer exist, just disconnected |
| **18.0** | 3 | Surface escalation/warnings/mode | Safety-critical gap |
| **17.5** | 2 | Wire `pathway_profile` | Wiring bug — schema + renderer exist, just disconnected |
| **17.0** | 4 | Synergy diagnostics on bundle cards | New data flow needed through ranker |
| **17.0** | 5 | 6th variance slice (interaction) | New variance source computation |
| **15.5** | 6 | Complete DAG with edges | Partial implementation completion |
| **15.0** | 7 | Per-edge variance contributions | Forward existing upstream data |
| **15.0** | 10 | Cochran's Q / I² | Forward existing upstream data |
| **14.5** | 9 | D matrix correlation disclosure | Config data to output |
| **13.0** | 8 | Model inspection data pipeline | New logging infrastructure |
| **12.0** | 11 | Reasoning narrative | NLG module |
| **12.0** | 12 | Research type heat map | Extraction metadata query |
| **9.0** | 13 | Cross-paper patterns | New analysis module |
| **8.5** | 14 | Dose ramp visualization | Schedule extension |
| **8.5** | 15 | Timing variant explorer | Schedule extension |

**Bottom line**: Ideas 1–3 are pure wiring fixes (existing schema + existing renderer, just not connected) and should be done immediately. Ideas 4–5 are the most scientifically impactful new features — they surface the synergy diagnostics we already compute. Everything else adds value but has diminishing returns relative to effort.

---

## 7. Cross-Reference: Implementation Plan for Risk Percentage

> **Companion document:**
> [`IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md`](IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md)

### 7.1 Scope Distinction

These two documents address **orthogonal concerns** with a small overlap zone:

| Dimension | This Document (Presentation Audit) | Implementation Plan (Risk %) |
|-----------|-------------------------------------|------------------------------|
| **Focus** | Plumbing — surfacing *existing* computation to users | Algorithm — *new* computation (F4/F5) |
| **Core question** | "What computed data never reaches the presentation layer?" | "How do we convert z-scores to clinical risk percentages?" |
| **New code** | Wiring fixes, new renderers, contract extensions | New algorithm modules (`risk_estimator.py`, subpopulation comparator) |
| **Upstream** | Zero changes to Chains A–F | New chain F modules (F4, F5) |
| **Downstream** | Presentation modules + RecommendationReport contract | RecommendationReport contract + new presentation views |
| **Shared touchpoint** | `output_contracts.py`, `report_assembler.py`, `session.py` | Same |

### 7.2 Overlap Zone

Both documents modify the same three files — **these are the coordination points**:

1. **`crci/shared/models/output_contracts.py`** — This audit identified missing fields on `RecommendationReport`. The implementation plan adds `ClinicalRiskProfile`, `SubpopulationComparisonSummary`, and schema versioning. Both sets of changes are additive (no conflicts) because they touch different fields.

2. **`crci/runtime/report_assembler.py`** — This audit found that `assemble_report()` never received `evidence_gap_report` or `pathway_profile` (wiring bugs). The implementation plan adds `risk_estimate` and `subpop_result` parameters. All changes are additive parameters on the same function.

3. **`crci/runtime/session.py`** — Both require `run_session()` to forward additional chain outputs to the assembler. Already extended with all 8 new params.

### 7.3 Resolution Status

Items from the §5 priority list that have been resolved:

| # | Idea | Status | Resolution |
|---|------|--------|------------|
| 1 | Wire `evidence_gaps` | **RESOLVED** | `evidence_gap_report` param added to `assemble_report()` and `run_session()`. Wired into `RecommendationReport.evidence_gaps`. |
| 2 | Wire `pathway_profile` | **RESOLVED** | `pathway_profile` param added to `assemble_report()` and `run_session()`. Wired into `RecommendationReport.pathway_profile`. |
| 3 | Surface escalation/warnings/mode | **RESOLVED** | `EscalationBanner` and `WarningNotice` dataclasses added to `crci_dashboard.py`. `render_score_dashboard()` now populates `ScoreDashboardView.escalation`, `.warnings`, `.output_mode`. |

Items 4–15 remain as **unresolved backlog** and are independent of the implementation plan's scope.

### 7.4 Build Sequencing

The implementation plan's Build Order (§7) should be completed **before** tackling audit items 4–15. Rationale:

- Items 4–5 (synergy diagnostics, 6th variance slice) require data flow changes in `ranker.py` and `variance_decomposer.py`. The implementation plan's F4/F5 modules sit alongside these in Chain F — building them first avoids merge conflicts in `output_contracts.py`.
- The implementation plan locks the output schema version (`OUTPUT_SCHEMA_VERSION = "v1.1.0"`) and establishes `generate_output_schemas.py`. All subsequent contract changes should bump this version.
- Items 11 (reasoning narrative) and 12 (research type heat map) correspond to implementation plan §8.6 and §8.4 respectively — they are *the same features* viewed from algorithm (plan) vs. presentation (audit) perspectives.

### 7.5 Cross-Document Feature Map

| Audit Item | Implementation Plan Section | Relationship |
|---|---|---|
| #11 Reasoning narrative | §8.6 Structured Reasoning Narrative Compiler | **Same feature** — audit describes presentation, plan would describe algorithm |
| #12 Research type heat map | §8.4 Research Type Heat Map | **Same feature** — audit describes view, plan would describe aggregation logic |
| #13 Cross-paper patterns | §8.5 Cross-Paper Pattern Detection | **Same feature** — audit describes view, plan would describe pattern mining |
| #14 Dose ramp visualization | §8.3 Adaptive Intensity Ramp Scheduling | **Related** — audit is just the chart, plan is the scheduling algorithm behind it |
| #4 Synergy diagnostics | Not in plan — pure plumbing | Plan's F4/F5 don't overlap with D3 synergy surfacing |
| #5 6th variance slice | Not in plan — pure plumbing | Plan's F4/F5 don't overlap with variance decomposition |
