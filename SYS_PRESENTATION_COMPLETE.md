═══════════════════════════════════════════════════════════════════════════
           SYS_PRESENTATION — COMPLETE SPECIFICATION
           (Tier 1: System Card + Tier 2: Chain Cards + Tier 3: Subsystem Cards)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0 (merged canonical)
Date: 2026-02-24

═══════════════════════════════════════════════════════════════════════════
                    PART 1: TIER 1 — SYSTEM CARD
═══════════════════════════════════════════════════════════════════════════

1. IDENTITY
   System ID:      SYS_PRESENTATION
   Name:           Patient-Facing UI & Reports
   Purpose:        Render RecommendationReport into patient-facing UI, clinician
                   dashboards, and evidence browsers
   Scope:          UI RENDERING ONLY [COR-2]. Reads output tables. Performs NO
                   computation, inference, or data transformation.
   Timing:         Runtime (after SYS_RUNTIME produces RecommendationReport)
   Chain Count:    3 branches (Patient, Science, Admin)
   Input:          RecommendationReport (TYPE 3 interface from RT-I4)

2. MACRO CHAIN

 RecommendationReport (from RT-I4)
   │
   ├────────────▶ PRES-PAT: Patient Interface
   │              (schedule, progress, education)
   │
   ├────────────▶ PRES-SCI: Science Interface
   │              (evidence browser, provenance, model inspection)
   │
   └────────────▶ PRES-ADM: Admin Interface
                  (monitoring, audit, configuration)

 CRITICAL: All 3 branches are READ-ONLY. No tables written.
 All computation is done upstream in SYS_ALGORITHM + SYS_RUNTIME.

3. BRANCH INVENTORY

| Branch | Chain ID | Name | Audience | Components |
|--------|----------|------|----------|------------|
| Patient | PRES-PAT | Patient Interface | Patients + caregivers | 6 |
| Science | PRES-SCI | Science Interface | Researchers + clinicians | 5 |
| Admin | PRES-ADM | Admin Interface | System administrators | 4 |

4. TABLE INVENTORY (READ-ONLY)

| Table ID | Class | Source System | Content |
|----------|-------|---------------|---------|
| recommendation_runs_v1 | E | RT-I | Session anchor + report payload |
| schedule_plans_v1 | E | RT-G | Ranked schedules |
| schedule_items_v1 | E | RT-G | Items per schedule |
| decision_trace_v1 | E | RT-G/I | Audit trail |
| question_sequence_v1 | E | RT-H | Questions asked |
| state_snapshots_v1 | E | ALG-C/RT-H | Posterior states over time |
| intervention_rankings_v1 | E | ALG-D/F | Ranked interventions |
| temporal_trajectories_v1 | E | ALG-E | Predicted trajectories |
| variance_decomposition_v1 | E | ALG-F | 5-source decomposition |
| evidence_gaps_v1 | E | ALG-F | Research priorities |
| description_templates_v1 | A | Humans | Text generation templates |
| outcome_anchors_v1 | C | Compilation | Severity calibration |
| action_catalog_v1 | A | Humans | Intervention display names |
| question_bank_v1 | D | Humans | Question presentation text |
| nodes_v1 | A | Humans | Node display names + domains |
| edges_v1 | C | EX/ALG | Edge parameters for evidence display |
| edge_evidence_v1 | B | EX | Study-level evidence for provenance |
| study_annotations_v1 | B | EX | Annotation context for evidence panels (v2.0) |

Tables Written: NONE. SYS_PRESENTATION is strictly read-only.
NOTE (v2.0): edges_v1 now includes sigma_sq_structural and overlap_decision columns.
  study_annotations_v1 available for enriching evidence panels with annotation context.

5. EXTERNAL INTERFACES
   | Direction | System | Data |
   |-----------|--------|------|
   | INPUT | SYS_RUNTIME (RT-I4) | RecommendationReport (JSON) |
   | INPUT | All Class A/B/C/D/E tables | Read-only rendering data |
   | OUTPUT | Browser/mobile client | Rendered HTML/PDF/API |
   | OUTPUT | Printer/export | PDF clinical report |

═══════════════════════════════════════════════════════════════════════════
                    PART 2: TIER 2 — CHAIN CARDS (BRANCHES)
═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: PRES-PAT (Patient Interface)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_PRESENTATION

1. IDENTITY
   Chain ID:       PRES-PAT
   Name:           Patient Interface
   Purpose:        Render clinical recommendations, trajectories, and educational
                   content for patients and caregivers in accessible format
   Phase:          Runtime (after RT-I4 report assembly)
   Paper §:        §4.5 (Clinical Output Mode)
   Subsystems:     6 (PAT1–PAT6)

2. SUBSYSTEM DETAIL

## PRES-PAT1 — CRCI Score Dashboard
   Purpose: Display composite CRCI score, severity tier, and percentile
   ┌─────────────────────────────────────────────────────────────┐
   │ Renders:                                                     │
   │ 1. Composite score as gauge/dial visualization               │
   │ 2. Severity tier with color coding:                          │
   │    Excellent(green) / Good(light-green) / Mild(yellow)       │
   │    Moderate(orange) / Poor(red-orange) / Severe(red)         │
   │ 3. Percentile ranking ("Your score is in the Xth percentile")│
   │ 4. Subdomain breakdown (11 domains, bar chart)              │
   │ 5. Change from previous session (if available)               │
   │ Reads: recommendation_runs_v1.composite                      │
   └─────────────────────────────────────────────────────────────┘

## PRES-PAT2 — Recommendation Cards
   Purpose: Display ranked interventions as actionable cards
   ┌─────────────────────────────────────────────────────────────┐
   │ Per intervention card:                                       │
   │ 1. Intervention name (from action_catalog_v1)               │
   │ 2. Expected benefit (SAFE_B score + 95% CrI)               │
   │ 3. Evidence strength badge (claim level color)               │
   │ 4. Stability indicator (Stable/Moderate/Unstable)            │
   │ 5. Schedule details (duration, frequency, dose)              │
   │ 6. "Why this?" expandable provenance summary                 │
   │ Display order: SAFE_B descending; top 5 shown by default    │
   │ Bundle cards: show component interventions + synergy bonus   │
   │ Reads: schedule_plans_v1, intervention_rankings_v1           │
   └─────────────────────────────────────────────────────────────┘

## PRES-PAT3 — Trajectory Visualization
   Purpose: Show predicted cognitive trajectory with and without intervention
   ┌─────────────────────────────────────────────────────────────┐
   │ Chart type: Line graph with confidence bands                 │
   │ X-axis: Time (0, 3, 6, 12, 18, 24 months)                  │
   │ Y-axis: Cognitive score (z-score or percentile)              │
   │ Lines:                                                       │
   │   1. Natural recovery (no intervention) — gray              │
   │   2. With top intervention — blue                            │
   │   3. 95% CrI bands — shaded                                 │
   │   4. MID threshold line (0.5 SD) — dashed                   │
   │ Annotations: MID crossing point, recovery probability        │
   │ Reads: temporal_trajectories_v1                              │
   └─────────────────────────────────────────────────────────────┘

## PRES-PAT4 — Uncertainty Disclosure Panel
   Purpose: Display mandatory uncertainty information in patient-accessible language
   ┌─────────────────────────────────────────────────────────────┐
   │ Content (ALWAYS shown — cannot be suppressed):               │
   │ 1. Confidence level: "We are [stability_class] confident     │
   │    in this recommendation"                                   │
   │ 2. Simplified variance pie chart (5 sources)                 │
   │ 3. Actionable message: "Collecting [test] would reduce       │
   │    uncertainty by ~[X]%"                                     │
   │ 4. If HIGHLY_UNSTABLE: prominent warning banner              │
   │ Language: Plain English (grade 8 reading level)              │
   │ Reads: variance_decomposition_v1, decision_trace_v1          │
   └─────────────────────────────────────────────────────────────┘

## PRES-PAT5 — Pathway Profile Display
   Purpose: Show which biological pathways are active/dysregulated
   ┌─────────────────────────────────────────────────────────────┐
   │ Visualization: Heatmap or radar chart of 20 pathways         │
   │ Color: Green (normal) → Yellow (mild) → Red (dysregulated)  │
   │ Per pathway: activation z-score + dysregulation flag         │
   │ Educational tooltip: plain-language pathway description       │
   │ Reads: recommendation_runs_v1.pathway_profile                │
   └─────────────────────────────────────────────────────────────┘

## PRES-PAT6 — Progress Tracker
   Purpose: Show longitudinal progress across sessions
   ┌─────────────────────────────────────────────────────────────┐
   │ Content:                                                     │
   │ 1. Score timeline (sessions over months)                     │
   │ 2. Intervention adherence tracking                           │
   │ 3. Next assessment due date                                  │
   │ 4. Milestone markers (MID crossing, recovery targets)        │
   │ Reads: historical recommendation_runs_v1 for same patient    │
   └─────────────────────────────────────────────────────────────┘

3. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | PAT-G1 | RecommendationReport exists | Render all | Show "Assessment in progress" |
   | PAT-G2 | Uncertainty disclosure present | Display | ERROR: cannot render without disclosure |

4. BOUNDARY TABLES (READ-ONLY)
   | Table ID | Columns Used | Component |
   |----------|-------------|-----------|
   | recommendation_runs_v1 | composite.CRCI_score, severity_tier, percentile, subdomains | PAT1 |
   | schedule_plans_v1 | intervention, SAFE_A, SAFE_B, CrI, stability | PAT2 |
   | intervention_rankings_v1 | ranked interventions, claim levels | PAT2 |
   | action_catalog_v1 | display_name, category, description | PAT2 |
   | temporal_trajectories_v1 | timepoints, mean, CrI_lower, CrI_upper | PAT3 |
   | variance_decomposition_v1 | 5-source breakdown | PAT4 |
   | decision_trace_v1 | stability_class, P_rank1, critical_edges | PAT4 |
   | recommendation_runs_v1 | pathway_profile[{pathway, activation_z, dysreg_flag}] | PAT5 |
   | recommendation_runs_v1 | historical sessions (same patient_id) | PAT6 |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: PRES-SCI (Science Interface)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_PRESENTATION

1. IDENTITY
   Chain ID:       PRES-SCI
   Name:           Science Interface
   Purpose:        Provide researchers and clinicians with full evidence
                   transparency, model inspection, and provenance visualization
   Phase:          Runtime (available after RT-I4)
   Paper §:        §4.5 (Research Output Mode)
   Subsystems:     5 (SCI1–SCI5)

2. SUBSYSTEM DETAIL

## PRES-SCI1 — Evidence Browser
   Purpose: Interactive table of all 118 edges with evidence depth
   ┌─────────────────────────────────────────────────────────────┐
   │ Features:                                                    │
   │ 1. Sortable/filterable table: edge_id, source→target, β̂,   │
   │    SE_eff, k, P_inclusion, claim_level, prior_type           │
   │ 2. Click-through to study-level evidence (edge_evidence_v1)  │
   │ 3. Forest plot per edge (β_i ± SE_i for each study)         │
   │ 4. Funnel plot for edges with k ≥ 10                        │
   │ 5. Evidence gap highlighting (k=0 edges in red)              │
   │ Reads: edges_v1, edge_evidence_v1                            │
   └─────────────────────────────────────────────────────────────┘

## PRES-SCI2 — DAG Visualization
   Purpose: Interactive directed acyclic graph with pathway highlighting
   ┌─────────────────────────────────────────────────────────────┐
   │ Features:                                                    │
   │ 1. 63-node, 118-edge interactive graph (force-directed)      │
   │ 2. Color by: domain (11), layer (7), observability (2)       │
   │ 3. Edge thickness ∝ |β|; edge style ∝ claim_level           │
   │ 4. Click pathway: highlight constituent edges                │
   │ 5. Click node: show posterior mean + variance for patient    │
   │ 6. Overlay: patient-specific pathway activation heatmap      │
   │ Reads: nodes_v1, edges_v1, pathway_map_v1, state_snapshots_v1│
   └─────────────────────────────────────────────────────────────┘

## PRES-SCI3 — Provenance Chain Viewer
   Purpose: Trace any recommendation back to source studies
   ┌─────────────────────────────────────────────────────────────┐
   │ For each intervention:                                       │
   │   Recommendation → SAFE score → Δθ computation               │
   │   → β̂ per edge → IVW pooling → study-level β_i              │
   │   → original paper (DOI link)                                │
   │ Visual: Sankey diagram or tree from recommendation to papers │
   │ Reads: decision_trace_v1, edges_v1, edge_evidence_v1         │
   └─────────────────────────────────────────────────────────────┘

## PRES-SCI4 — Model Inspection Panel
   Purpose: Show all model parameters and assumptions
   ┌─────────────────────────────────────────────────────────────┐
   │ Content:                                                     │
   │ 1. Prior selection log: per-edge prior type + rationale       │
   │ 2. SE calibration: 7-layer multipliers per edge              │
   │ 3. Effect modifier application log                           │
   │ 4. Chain-vs-direct validation results                        │
   │ 5. Assumptions table with impact assessment                  │
   │ 6. Model version + deployment timestamp                      │
   │ Reads: prior_selection_log_v1, decision_trace_v1, edges_v1   │
   └─────────────────────────────────────────────────────────────┘

## PRES-SCI5 — Research Priority Dashboard
   Purpose: Display evidence gaps and research investment guidance
   ┌─────────────────────────────────────────────────────────────┐
   │ Content:                                                     │
   │ 1. Evidence gap map (sorted by discovery_score)              │
   │ 2. EVSI per proposed study ("expected improvement in SAFE")  │
   │ 3. Recommended study designs (N, type, endpoint)             │
   │ 4. Chain-vs-direct discrepancy flags                         │
   │ 5. Missing pathway hypotheses                                │
   │ Reads: evidence_gaps_v1                                      │
   └─────────────────────────────────────────────────────────────┘

3. BOUNDARY TABLES (READ-ONLY)
   | Table ID | Columns Used | Component |
   |----------|-------------|-----------|
   | edges_v1 | all 118 rows: β, SE_eff, k, P_incl, claim_level, prior_type | SCI1 |
   | edge_evidence_v1 | per-study records: β_i, SE_i, design, cohort | SCI1, SCI3 |
   | nodes_v1 | 63 nodes: name, domain, layer, observability | SCI2 |
   | pathway_map_v1 | 20 pathways with node memberships | SCI2 |
   | state_snapshots_v1 | posterior mean + variance per node for patient | SCI2 |
   | decision_trace_v1 | all decision steps with rationale | SCI3, SCI4 |
   | prior_selection_log_v1 | per-edge prior type + rationale | SCI4 |
   | evidence_gaps_v1 | gaps sorted by discovery_score + EVSI | SCI5 |

4. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | SCI-G1 | edges_v1 loaded (≥1 row) | Render evidence browser | Show "No model loaded" |
   | SCI-G2 | nodes_v1 + edges_v1 consistent | Render DAG | Show "Graph validation error" |

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: PRES-ADM (Admin Interface)
═══════════════════════════════════════════════════════════════════════════
Version: 2.0
Parent System: SYS_PRESENTATION

1. IDENTITY
   Chain ID:       PRES-ADM
   Name:           Admin Interface
   Purpose:        System monitoring, audit access, and configuration management
   Phase:          Always available (admin-only access)
   Subsystems:     4 (ADM1–ADM4)

2. SUBSYSTEM DETAIL

## PRES-ADM1 — System Health Dashboard
   Purpose: Show pipeline status, error rates, performance metrics
   Content: Processing queue depth, last deployment timestamp, error log,
   validation rule pass rates, model version history

## PRES-ADM2 — Audit Log Viewer
   Purpose: Searchable audit trail across all Class E tables
   Content: Session logs, extraction audit, aggregation log, deployment log
   Reads: All Class E audit tables

## PRES-ADM3 — Configuration Manager
   Purpose: UI for editing Class D policy tables (human-curated)
   Content: Edit contraindication rules, objective specs, question bank
   NOTE: This is the ONLY place SYS_PRESENTATION writes — and only to Class D
   policy tables, which are human-curated configuration, not computed data.

## PRES-ADM4 — Population Analytics Dashboard
   Purpose: Display archetype discovery results across patient pool
   Content: Cluster visualization, archetype profiles, escalation rates
   Reads: population_archetypes_v1

3. BOUNDARY TABLES
   | Table ID | Access | Component |
   |----------|--------|-----------|
   | All Class E audit tables | READ | ADM2 |
   | contraindication_rules_v1 (Class D) | READ+WRITE (admin only) | ADM3 |
   | objective_specs_v1 (Class D) | READ+WRITE (admin only) | ADM3 |
   | question_bank_v1 (Class D) | READ+WRITE (admin only) | ADM3 |
   | population_archetypes_v1 | READ | ADM4 |

4. GATES
   | Gate | Condition | Pass | Fail |
   |------|-----------|------|------|
   | ADM-G1 | Admin authentication verified | Render all | Block access |
   | ADM-G2 | Class D edit → validation pass | Save changes | Show validation errors |

═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
                    PART 3: TIER 3 — SUBSYSTEM CARDS
                    (15 subsystems across 3 branches)
═══════════════════════════════════════════════════════════════════════════

Note: SYS_PRESENTATION is a read-only rendering layer. Subsystem cards
here specify rendering behavior, data requirements, and empty-state handling
rather than mathematical processes or formulas (which are N/A for rendering).

───────────────────────────────────────────────────────────────────────────
CHAIN PRES-PAT: Patient Interface (6 subsystems)
───────────────────────────────────────────────────────────────────────────

## PRES-PAT1 — CRCI Score Dashboard
   ID: PRES-PAT1 | Type: RENDER | Phase: Runtime
   Purpose: Display composite CRCI score, severity tier, percentile, subdomain breakdown
   Reads: recommendation_runs_v1.composite {CRCI_score, severity_tier, percentile, subdomains[11]}
   Renders: Gauge/dial (score), color-coded severity tier, percentile text, 11-domain bar chart,
     delta from previous session (if available)
   Empty State: "Assessment not yet complete. Please answer the questions to receive your score."
   Connections: Reads recommendation_runs_v1; Rendered first in patient view

## PRES-PAT2 — Recommendation Cards
   ID: PRES-PAT2 | Type: RENDER | Phase: Runtime
   Purpose: Display ranked interventions as actionable cards with evidence badges
   Reads: schedule_plans_v1 (top 5), intervention_rankings_v1, action_catalog_v1 (display names)
   Renders: Per card: name, expected benefit (SAFE_B + 95% CrI), evidence strength badge
     (claim_level color), stability indicator, schedule details, expandable provenance summary.
     Bundle cards show component interventions + synergy bonus.
   Display Order: SAFE_B descending; top 5 shown; "Show more" expands
   Empty State: "No interventions could be ranked. This may indicate insufficient data."
   Connections: Reads schedule_plans_v1, intervention_rankings_v1, action_catalog_v1

## PRES-PAT3 — Trajectory Visualization
   ID: PRES-PAT3 | Type: RENDER | Phase: Runtime
   Purpose: Show predicted cognitive trajectory ± intervention
   Reads: temporal_trajectories_v1 {timepoints, mean, CrI_lower, CrI_upper, temporal_source}
   Renders: Line chart — X: time (0,3,6,12,18,24 months), Y: cognitive z-score/percentile.
     Lines: natural recovery (gray), top intervention (blue), 95% CrI bands (shaded),
     MID threshold (0.5 SD, dashed). Annotations: MID crossing point, recovery probability.
     If temporal_source = "static_only" [Gap-2]: show point estimate only, no trajectory curve.
     If temporal_source = "default_conservative": show with wider bands + caveat text.
   Empty State: "Trajectory prediction requires additional assessment data."
   Connections: Reads temporal_trajectories_v1

## PRES-PAT4 — Uncertainty Disclosure Panel (MANDATORY)
   ID: PRES-PAT4 | Type: RENDER | Phase: Runtime
   Purpose: Display mandatory uncertainty information in accessible language (grade 8 reading level)
   Reads: variance_decomposition_v1, decision_trace_v1 {stability_class, P_rank1, critical_edges}
   Renders: (1) Confidence statement: "We are [stability_class] confident..."
     (2) Simplified variance pie chart (5 sources), (3) Actionable: "Collecting [test]
     would reduce uncertainty by ~[X]%", (4) HIGHLY_UNSTABLE → prominent warning banner
   CRITICAL: This panel CANNOT BE SUPPRESSED — always rendered when report exists
   Empty State: N/A — if report exists, uncertainty exists
   Connections: Reads variance_decomposition_v1, decision_trace_v1

## PRES-PAT5 — Pathway Profile Display
   ID: PRES-PAT5 | Type: RENDER | Phase: Runtime
   Purpose: Show which biological pathways are active/dysregulated
   Reads: recommendation_runs_v1.pathway_profile [{pathway, activation_z, dysregulation_flag}]
   Renders: Heatmap or radar chart of 20 pathways. Color: green(normal)→yellow(mild)→red(dysreg).
     Educational tooltip per pathway (plain-language description from description_templates_v1).
   Empty State: "Pathway analysis requires additional biomarker data."
   Connections: Reads recommendation_runs_v1, description_templates_v1

## PRES-PAT6 — Progress Tracker
   ID: PRES-PAT6 | Type: RENDER | Phase: Runtime
   Purpose: Show longitudinal progress across sessions
   Reads: Historical recommendation_runs_v1 (same patient_id, multiple sessions)
   Renders: Score timeline (sessions over months), intervention adherence tracking,
     next assessment due date, milestone markers (MID crossing, recovery targets)
   Empty State: "This is your first assessment. Progress tracking will begin after your next session."
   Connections: Reads historical recommendation_runs_v1

───────────────────────────────────────────────────────────────────────────
CHAIN PRES-SCI: Science Interface (5 subsystems)
───────────────────────────────────────────────────────────────────────────

## PRES-SCI1 — Evidence Browser
   ID: PRES-SCI1 | Type: RENDER | Phase: Runtime
   Purpose: Interactive sortable/filterable table of all 118 edges with evidence depth
   Reads: edges_v1 (all columns), edge_evidence_v1 (per-study records)
   Renders: Table: edge_id, source→target, β̂, SE_eff, k, P_incl, claim_level, prior_type.
     Click-through to study-level evidence. Forest plot per edge. Funnel plot for k≥10.
     Evidence gap highlighting (k=0 in red).
   Empty State: "Model not loaded. Deploy evidence to view."
   Connections: Reads edges_v1, edge_evidence_v1

## PRES-SCI2 — DAG Visualization
   ID: PRES-SCI2 | Type: RENDER | Phase: Runtime
   Purpose: Interactive 63-node, 118-edge DAG with pathway highlighting
   Reads: nodes_v1, edges_v1, pathway_map_v1, state_snapshots_v1
   Renders: Force-directed graph. Color by: domain(11)/layer(7)/observability(2).
     Edge thickness ∝ |β|; edge style ∝ claim_level. Click pathway → highlight edges.
     Click node → show posterior mean + variance. Overlay: patient-specific heatmap.
   Empty State: "Graph requires deployed model. Run extraction pipeline first."
   Connections: Reads nodes_v1, edges_v1, pathway_map_v1, state_snapshots_v1

## PRES-SCI3 — Provenance Chain Viewer
   ID: PRES-SCI3 | Type: RENDER | Phase: Runtime
   Purpose: Trace any recommendation back to source studies
   Reads: decision_trace_v1, edges_v1, edge_evidence_v1
   Renders: Sankey diagram or tree: Recommendation → SAFE score → Δθ → β̂ per edge
     → IVW pooling → study-level β_i → DOI link.
   Empty State: "Select an intervention to trace its evidence chain."
   Connections: Reads decision_trace_v1, edges_v1, edge_evidence_v1

## PRES-SCI4 — Model Inspection Panel
   ID: PRES-SCI4 | Type: RENDER | Phase: Runtime
   Purpose: Show all model parameters and assumptions for full transparency
   Reads: prior_selection_log_v1, decision_trace_v1, edges_v1
   Renders: Prior selection log (per-edge), SE calibration (7-layer multipliers),
     effect modifier application log, chain-vs-direct results,
     assumptions table with impact assessment, model version + deploy timestamp
   Empty State: "Model inspection available after deployment."
   Connections: Reads prior_selection_log_v1, decision_trace_v1, edges_v1

## PRES-SCI5 — Research Priority Dashboard
   ID: PRES-SCI5 | Type: RENDER | Phase: Runtime
   Purpose: Display evidence gaps and research investment guidance
   Reads: evidence_gaps_v1 {edge_id, discovery_score, EVSI, recommended_design, N, endpoint}
   Renders: Gap map sorted by discovery_score, EVSI per proposed study,
     recommended study designs, chain-vs-direct discrepancy flags, missing pathway hypotheses
   Empty State: "Evidence gap analysis available after sufficiency check (EX-P5)."
   Connections: Reads evidence_gaps_v1

───────────────────────────────────────────────────────────────────────────
CHAIN PRES-ADM: Admin Interface (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## PRES-ADM1 — System Health Dashboard
   ID: PRES-ADM1 | Type: RENDER | Phase: Always
   Purpose: Show pipeline status, error rates, performance metrics
   Reads: System metrics, error logs, deployment_log_v1
   Renders: Processing queue depth, last deployment timestamp, error rate trends,
     validation rule pass rates (G1-G17), model version history
   Empty State: "System metrics unavailable."

## PRES-ADM2 — Audit Log Viewer
   ID: PRES-ADM2 | Type: RENDER | Phase: Always
   Purpose: Searchable audit trail across all Class E tables
   Reads: All Class E audit tables (extraction_audit_v1, decision_trace_v1,
     aggregation_log_v1, deployment_log_v1, prior_selection_log_v1)
   Renders: Searchable/filterable log viewer with timestamps, session IDs, actions
   Empty State: "No audit records found."

## PRES-ADM3 — Configuration Manager
   ID: PRES-ADM3 | Type: RENDER+WRITE | Phase: Always (admin-only)
   Purpose: UI for editing Class D policy tables
   Reads+Writes: contraindication_rules_v1, objective_specs_v1, question_bank_v1
   Renders: Editable table views with validation. Save triggers validation check (ADM-G2).
   NOTE: ONLY place SYS_PRESENTATION writes. Only Class D policy tables (human-curated).
   Empty State: N/A — tables always exist with defaults

## PRES-ADM4 — Population Analytics Dashboard
   ID: PRES-ADM4 | Type: RENDER | Phase: Runtime
   Purpose: Display archetype discovery results across patient pool
   Reads: population_archetypes_v1 {cluster_id, profile, n_patients, escalation_rate}
   Renders: Cluster visualization, archetype profiles, escalation rates, Mahalanobis outliers
   Empty State: "Population analytics require ≥50 patient sessions."

                    APPENDIX: CROSS-REFERENCE VALIDATION
═══════════════════════════════════════════════════════════════════════════

A. RT → PRES INTERFACE CONTRACT
   The primary handoff is RecommendationReport (JSON from RT-I4):
   - header: session_id, timestamp, model_version, patient_id
   - composite: CRCI_score, severity_tier, percentile
   - recommendations: [{intervention, SAFE_A, SAFE_B, CrI, schedule, provenance}]
   - trajectories: [{timepoint, mean, CrI_lower, CrI_upper}]
   - uncertainty: {stability, variance_decomp, critical_edges}
   - pathway_profile: [{pathway, activation, dysregulation}]
   - session: {questions_asked, state_updates, total_time}
   - audit: {decision_trace, prior_selection_log}

B. SUBSYSTEM CONSISTENCY
   PRES-PAT: PAT1–PAT6                (6 subsystems)
   PRES-SCI: SCI1–SCI5                (5 subsystems)
   PRES-ADM: ADM1–ADM4                (4 subsystems)
   TOTAL: 15 subsystems ✓ (matches "~15 visualization components" from architecture doc)

C. READ-ONLY ENFORCEMENT
   SYS_PRESENTATION reads from 17 tables across Class A/B/C/D/E.
   SYS_PRESENTATION writes to ZERO tables.
   Exception: PRES-ADM3 (Configuration Manager) edits Class D policy tables,
   which are human-curated configuration — not computed system output.
   This is a deliberate design choice: no computation in the rendering layer.

═══════════════════════════════════════════════════════════════════════════
END OF SYS_PRESENTATION COMPLETE SPECIFICATION
═══════════════════════════════════════════════════════════════════════════
