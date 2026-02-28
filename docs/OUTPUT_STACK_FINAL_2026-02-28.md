# CRCI Final Output Stack (Planned vs Current)

**Date:** 2026-02-28  
**Purpose:** One clear source of truth for:
1) what outputs are planned vs currently implemented,  
2) which outputs are generated from other outputs, and  
3) how outputs are grouped in runtime reports (patient/scientist/audit/admin).

---

## 1) Executive Snapshot

| Group | Planned Total | Live (end-to-end) | Wired (upstream needed / no view yet) | Partial | Planned-only |
|---|---:|---:|---:|---:|---:|
| Patient Clinical Outputs | 8 | 6 | 2 | 0 | 0 |
| Paper / Evidence Analytics | 8 | 5 | 2 | 1 | 0 |
| Evidence Auditing | 2 | 1 | 0 | 0 | 1 |
| System / Admin | 4 | 0 | 0 | 0 | 4 |
| **Total** | **22** | **12** | **4** | **1** | **5** |

**Interpretation:**
- **Live** = algorithm + report assembly + view/report surface are all working.
- **Wired** = report field is implemented, but depends on upstream data not always passed or a dedicated view not built.
- **Partial** = visible but incomplete behavior.
- **Planned-only** = documented/spec’d but not implemented.

---

## 2) Final Output Inventory (Planned vs Current)

### A. Patient Clinical Outputs (for patient-facing reporting)

| ID | Output | Generated From | Report Field | Report Grouping | Status |
|---|---|---|---|---|---|
| PC1 | Composite Score | C3 posterior + F1 composite | `composite_score` | `score` | **LIVE** |
| PC2 | Primary Schedule | D4-D6 ranking + RT-G | `primary_schedule` | `interventions` | **LIVE** |
| PC3 | Alternative Schedules | D4-D6 ranking + RT-G | `alternative_schedules` | `interventions` | **LIVE** |
| PC4 | Temporal Trajectories | E2/E3 temporal outputs | `trajectories` | `interventions`/trajectory modules | **LIVE** |
| PC5 | Uncertainty Decomposition | F2 stability + F3 variance | `variance_decomposition` | `uncertainty` | **LIVE** |
| PC6 | Pathway Profile | C4d pathway activations (+ B6.5 enrichment) | `pathway_profile` | `pathways` | **WIRED** |
| PC7 | Clinical Risk Profile | F4 risk estimator (from D1 draws + C state) | `clinical_risk` | `risk` | **WIRED** |
| PC8 | Extraction Quality Disclosure | Completeness checker | `extraction_quality` | `quality` | **LIVE** |

### B. Paper / Evidence Analytics Outputs (for scientist-facing reporting)

| ID | Output | Generated From | Report Field / Source | Report Grouping | Status |
|---|---|---|---|---|---|
| EA1 | Evidence Gaps / EVSI | F3 EVSI | `evidence_gaps` | `evidence` | **WIRED** |
| EA2 | Edge Evidence Browser | B1-B5 compiled evidence in DB | DB (`edge_evidence_v1`) + report context | `evidence` | **LIVE** |
| EA3 | Decision Trace / Provenance Chain | Runtime assembly over chain outputs | `decision_trace` | `uncertainty` + scientist trace views | **LIVE** |
| EA4 | DAG Visualization | A graph + report trace/pathway data | view-side synthesis | `pathways` / scientist DAG view | **PARTIAL** |
| EA5 | Model Inspection | B2-B4 priors/calibration assumptions | mostly via `decision_trace` + metadata | scientist inspection | **LIVE** |
| EA6 | Provenance Viewer | R2/R3 mapping (edge→study, sensitivity) | `decision_trace` + influence maps | scientist provenance | **LIVE** |
| EA7 | Sensitivity Report | D4-D6 sensitivity indices | `sensitivity_report` | scientist research dashboard | **WIRED** |
| EA8 | Subpopulation Comparison | F5 subpopulation comparator | `subpopulation_comparison` | no dedicated section/view yet | **WIRED** |

### C. Evidence Auditing Outputs

| ID | Output | Generated From | Stored/Surfaced In | Status |
|---|---|---|---|---|
| AUD1 | Edge Coherence Flags (chain-vs-direct checks) | B4 coherence checker | DB + partial inspection surfaces | **LIVE (partial surfacing)** |
| AUD2 | Research-Type Heat Map | Planned mining over study design distribution | Not implemented | **PLANNED** |

### D. System / Admin Outputs

| ID | Output | Status |
|---|---|---|
| ADM1 | System Health Dashboard | **PLANNED** |
| ADM2 | Audit Log Viewer | **PLANNED** |
| ADM3 | Configuration Manager | **PLANNED** |
| ADM4 | Population Analytics | **PLANNED** |

---

## 3) Output Dependency Stack (what is generated from what)

## Layer 0 — Evidence + Registries (inputs)
- `edge_evidence_v1`, priors, action catalog, dose bridges, registries.

## Layer 1 — Algorithm Boundary Outputs (internal)
- **B output:** `FrozenModelState`
- **C output:** posterior state + pathway activations
- **D outputs:** `MCDraws`, ranking, bundle/synergy details
- **E outputs:** recovery + intervention trajectories
- **F outputs:** composite, variance/stability, EVSI gaps, risk, subpopulation comparison

## Layer 2 — Runtime Assembled Contract (single sink)
- `RecommendationReport` is the canonical final object.
- Key derived mappings:
  - `composite_score` ← C3 + F1
  - `primary_schedule`/`alternative_schedules` ← D ranking + RT-G
  - `variance_decomposition` ← F3 (+ F2 context)
  - `pathway_profile` ← C4d (+ optional B6.5 pathway evidence)
  - `clinical_risk` ← F4
  - `evidence_gaps` ← F3 EVSI
  - `sensitivity_report` ← D4-D6 sensitivity
  - `subpopulation_comparison` ← F5
  - `decision_trace` ← cross-chain provenance assembly

## Layer 3 — Reporting Surfaces
- Terminal/JSON report sections (`score`, `interventions`, `pathways`, `uncertainty`, `risk`, `evidence`, `quality`)
- Module-level view models (dashboard/cards/pathway/risk/evidence/provenance/etc.)

---

## 4) How outputs are grouped during report output

### Runtime section grouping (from `render_report.py`)

**Patient branch (`--branch patient`):**
- `score`
- `interventions`
- `pathways`
- `uncertainty`
- `quality`

**Scientist branch (`--branch scientist`):**
- `score`
- `interventions`
- `pathways`
- `uncertainty`
- `risk`
- `evidence`
- `quality`

**All branch (`--branch all` or RESEARCH mode default):**
- all seven sections above.

### Functional grouping for your working sessions

1. **Paper Data Analytics group**
   - EA1, EA2, EA3, EA4, EA5, EA6, EA7, EA8
   - Main sections: `evidence`, `risk`, `uncertainty`, scientist modules

2. **Evidence Auditing group**
   - AUD1, AUD2 (+ quality disclosure cross-cut)
   - Main sections: `quality`, scientist inspection/provenance

3. **Clinical Recommendation group**
   - PC1–PC8
   - Main sections: `score`, `interventions`, `pathways`, `uncertainty`, `quality` (+ `risk` when enabled)

4. **System/Admin group**
   - ADM1–ADM4
   - Not yet in runtime report output

---

## 5) “Have right now” (operational baseline)

### Operational now
- Core patient outputs: score, schedules, trajectories, uncertainty, quality.
- Core scientist outputs: evidence browsing, provenance/decision trace, model inspection.
- Assembled contract fields for risk/pathways/evidence-gaps/sensitivity/subpopulation exist and are wired.

### Main remaining gaps
- DAG view edge rendering remains partial.
- Subpopulation comparison has no dedicated presentation section/view.
- Research-type heat map and all admin dashboards remain planned.

---

## 6) Canonical files for maintenance

- `docs/OUTPUT_STACK_CONSOLIDATED.md`
- `docs/OUTPUT_TRACE_AND_STATUS.md`
- `docs/OUTPUT_CHAIN_MAP.md`
- `crci/shared/models/output_contracts.py`
- `crci/runtime/report_assembler.py`
- `crci/presentation/render_report.py`
