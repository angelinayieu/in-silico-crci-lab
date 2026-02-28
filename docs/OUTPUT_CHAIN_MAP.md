# CRCI Output Chain Map — How Outputs Stack

> **Purpose**: Shows exactly how each chain's output feeds into the next.
> Verified against a live pipeline run on 2026-02-27.
> For wiring status and presentation coverage, see [OUTPUT_TRACE_AND_STATUS.md](OUTPUT_TRACE_AND_STATUS.md).

---

## The Full Stack (One Picture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER (DB + CSV)                        │
│                                                                     │
│  edge_evidence_v1 (18 rows) ──────────────────────────────► Chain B │
│  NODE_REGISTRY.csv (63 nodes) ────────────────────────────► Chain A │
│  EDGE_REGISTRY.csv (141 edges) ───────────────────────────► Chain A │
│  INSTRUMENT_REGISTRY.csv (67) ────────────────────────────► Chain A │
│  PATHWAY_REGISTRY.csv (22) ───────────────────────────────► Chain A │
│  node_priors_v1 (12 rows) ────────────────────────────────► Chain C │
│  action_catalog_v1 (8 rows) ──────────────────────────────► Chain D │
│  dose_bridges_v1 (10 rows) ───────────────────────────────► Chain D │
│  observation_noise_v1 (13 rows) ──────────────────────────► Chain C │
│  intervention_kernels_v1 (0 rows ❌) ─────────────────────► Chain D │
│  contraindication_rules_v1 (0 rows ❌) ───────────────────► Chain D │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  CHAIN A: Graph Assembly                                             │
│  Output: GraphObject                                                 │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ NodeMap        63 nodes, index, layers 0-6, domains, orient.  │  │
│  │ BSkeleton      n×n edge weight skeleton (unparameterized)     │  │
│  │ InstrumentMap  67 instruments → node mappings                 │  │
│  │ DMatrix        Residual covariance matrix                     │  │
│  │ PathwayMap     22 pathways (node groups)                      │  │
│  │ LatentProxies  Latent-proxy pairs with R², SE multipliers     │  │
│  │ FeedbackLoops  3 feedback loops with gain & stability         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  Live values: 63 nodes, 143 edges, 67 instruments                   │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
┌─────────────────────┐  ┌─────────────────────────────────────────────┐
│  CHAIN B             │  │  (also used by C, D, E, F directly)        │
│  Reads: GraphObject  │  │                                             │
│  + edge_evidence_v1  │  └─────────────────────────────────────────────┘
│  (18 rows, 10 cols)  │
│                      │
│  Steps:              │
│  B1: IVW pooling     │
│  B2: Prior selection  │
│  B3: 7-layer SE      │
│  B4: Coherence check │
│  B5: Inclusion probs │
│  B6: Context priors  │
│  B6.5: Pathway score │
│  B7: Assembly        │
│                      │
│  Output:             │
│  FrozenModelState    │
│  ┌────────────────┐  │
│  │ B_hat    n×n   │──┼──► parameterized edge weights
│  │ Sigma_eff      │──┼──► per-edge effective SE
│  │ Lambda_prior   │──┼──► context→precision matrices
│  │ P_inclusion    │──┼──► per-edge structural inclusion prob
│  │ tau_sq_est     │──┼──► per-edge heterogeneity τ²
│  │ synergy_recs   │──┼──► pairwise interaction data
│  │ pw_ev_scores   │──┼──► per-pathway evidence density
│  │ AV_scores      │──┼──► alignment validity per edge
│  │ sha256_hash    │──┼──► integrity verification
│  └────────────────┘  │
└──────────────────┬───┘
                   │
         ┌─────────┴──────────────────────┐
         ▼                                ▼
┌─────────────────────────┐    ┌────────────────────────────┐
│  CHAIN C                 │    │  CHAIN D (also needs C)     │
│  Reads:                  │    │                              │
│   • FrozenModelState (B) │    │                              │
│   • node_priors_v1 (DB)  │    │                              │
│   • patient observations │    │                              │
│   • modifier_rules.csv   │    │                              │
│   • patient_profile {}   │    │                              │
│                          │    │                              │
│  Steps:                  │    │                              │
│  C1: Context match/prior │    │                              │
│  C2: Observation mapping │    │                              │
│  C3: Bayesian update     │    │                              │
│  C4: Modifier application│    │                              │
│                          │    │                              │
│  Outputs (2 objects):    │    │                              │
│                          │    │                              │
│  RawPosterior            │    │                              │
│  ┌────────────────────┐  │    │                              │
│  │ theta_hat   (n,)   │  │    │                              │
│  │ Sigma_post  (n×n)  │  │    │                              │
│  │ Lambda_post (n×n)  │  │    │                              │
│  │ observation_log    │  │    │                              │
│  │ fusion_levels      │──┼────┼──► used by F4 risk estimator │
│  │ variance_reduction │  │    │                              │
│  └────────────────────┘  │    │                              │
│                          │    │                              │
│  PatientState (final)    │    │                              │
│  ┌────────────────────┐  │    │                              │
│  │ theta_hat   (n,)   │──┼────┼──► D1 MC sampling baseline   │
│  │ Sigma_post  (n×n)  │──┼────┼──► D1 Cholesky decomp       │
│  │ Lambda_post (n×n)  │  │    │                              │
│  │ B_eff       (n×n)  │──┼────┼──► D1 modified edge weights  │
│  │ active_pathways    │──┼────┼──► Runtime pathway profile   │
│  │ modifier_audit     │  │    │                              │
│  │ observation_log    │  │    │                              │
│  │ context_match      │  │    │                              │
│  └────────────────────┘  │    │                              │
│                          │    │                              │
│  LoadedPrior             │    │                              │
│  ┌────────────────────┐  │    │                              │
│  │ mu_prior    (n,)   │  │    │                              │
│  │ Lambda_prior(n×n)  │  │    │                              │
│  │ context_key        │  │    │                              │
│  │ fallback_level     │  │    │                              │
│  └────────────────────┘  │    │                              │
└──────────────────┬───────┘    │                              │
                   │            │                              │
         ┌─────────┴────────────┘                              │
         ▼                                                     │
┌─────────────────────────────────────────────────────────────┐│
│  CHAIN D: Simulation & Ranking                               ││
│  Reads:                                                      ││
│   • FrozenModelState (B) — B_hat, Sigma_eff, P_inclusion    ││
│   • PatientState (C) — theta_hat, Sigma_post, B_eff         ││
│   • action_catalog_v1, dose_bridges_v1 (DB)                 ││
│   • intervention_kernels_v1 (DB — currently 0 rows ❌)      ││
│   • contraindication_rules_v1 (DB — currently 0 rows ❌)    ││
│                                                              ││
│  Steps:                                                      ││
│  D0: Load interventions (InterventionSet)                    ││
│  D1: Monte Carlo draws (10,000)                              ││
│  D2: Effect propagation per intervention                     ││
│  D3: Safety check + synergy bundles                          ││
│  D4-D6: Ranking (SAFE-A, SAFE-B, claim levels)              ││
│                                                              ││
│  Outputs (4 objects):                                        ││
│                                                              ││
│  MCDraws (D1)                                                ││
│  ┌──────────────────────┐                                    ││
│  │ beta_draws  (M×n×n)  │──► F4 risk estimation              ││
│  │ include_draws(M×n×n) │                                    ││
│  │ B_draws     (M×n×n)  │                                    ││
│  │ theta0_draws (M×n)   │──► F4 risk: P̂(CRCI) from MC       ││
│  │ n_draws=10000        │                                    ││
│  └──────────────────────┘                                    ││
│                                                              ││
│  EffectResult (D2)                                           ││
│  ┌──────────────────────┐                                    ││
│  │ intervention_effects │──► E3 intervention overlay          ││
│  │  per action_id:      │                                    ││
│  │   delta_theta (M×n)  │                                    ││
│  │   delta_C (M,)       │                                    ││
│  │   mean_delta_C       │                                    ││
│  └──────────────────────┘                                    ││
│                                                              ││
│  SafetyResult (D3)                                           ││
│  ┌──────────────────────┐                                    ││
│  │ per action: SAFE/    │                                    ││
│  │  BLOCKED/WARNING     │──► D4-D6 ranking filter            ││
│  │ n_clear, n_blocked   │                                    ││
│  └──────────────────────┘                                    ││
│                                                              ││
│  RankingResult (D4-D6)                                       ││
│  ┌──────────────────────┐                                    ││
│  │ intervention_rankings│──► E3, F2, Runtime                  ││
│  │  per action_id:      │                                    ││
│  │   safe_a, safe_b     │                                    ││
│  │   rank, CrI          │                                    ││
│  │   per_draw_safe_a    │──► F2 decision stability            ││
│  │ bundle_rankings      │──► Runtime schedule plans           ││
│  │ sensitivity_indices  │──► Runtime sensitivity report       ││
│  │ dose_recommendations │──► Runtime schedule plans           ││
│  └──────────────────────┘                                    ││
└──────────────────┬──────────────────────────────────────────┘│
                   │                                           │
         ┌─────────┴──────────────────────┐                    │
         ▼                                ▼                    │
┌─────────────────────────┐    ┌───────────────────────────────┤
│  CHAIN E: Temporal       │    │  CHAIN F: Analytics           │
│  Reads:                  │    │  Reads:                       │
│   • PatientState (C)     │    │   • PatientState (C)          │
│   • EffectResult (D2)    │    │   • RankingResult (D4-D6)     │
│   • RankingResult (D4-D6)│    │   • MCDraws (D1)              │
│   • InterventionSet (D0) │    │   • GraphObject (A)           │
│                          │    │   • RecoveryTrajectory (E2)   │
│  Steps:                  │    │   • OverlayResult (E3)        │
│  E1: Nadir estimation    │    │   • RawPosterior.fusion (C)   │
│  E2: Recovery trajectory │    │                               │
│  E3: Intervention overlay│    │  Steps:                       │
│  E4: Uncertainty countf. │    │  F1: CRCI composite score     │
│                          │    │  F2: Decision stability       │
│  Outputs:                │    │  F3: Variance decomposition   │
│                          │    │  F4: Clinical risk P̂(CRCI)   │
│  NadirEstimate (E1)      │    │  F4T: Temporal risk curves    │
│  ┌────────────────────┐  │    │                               │
│  │ theta_nadir  (n,)  │  │    │  Outputs:                     │
│  │ scenario           │  │    │                               │
│  │ confidence         │  │    │  CompositeState (F1)          │
│  │ theta_base   (n,)  │  │    │  ┌──────────────────────┐     │
│  └───────┬────────────┘  │    │  │ crci_composite  0.00 │     │
│          ▼               │    │  │ severity_tier  MILD  │     │
│  RecoveryTrajectory (E2) │    │  │ percentile     50.0  │     │
│  ┌────────────────────┐  │    │  │ subdomain_scores {}  │     │
│  │ theta_natural(n×T) │  │    │  │ cochrans_Q, I²       │     │
│  │ R_draws    (M×T)   │  │    │  └──────────┬───────────┘     │
│  │ R_mean     (T,)    │  │    │             │                 │
│  │ recovery_params    │──┼────┼──► F4T      ▼                 │
│  │ time_months (T,)   │  │    │  StabilityState (F2)          │
│  └───────┬────────────┘  │    │  ┌──────────────────────┐     │
│          ▼               │    │  │ rank_1_probs   {}    │     │
│  OverlayResult (E3)      │    │  │ stability_class      │     │
│  ┌────────────────────┐  │    │  │  STABLE (81% P(r=1)) │     │
│  │ per intervention:  │  │    │  │ decision_crit_edges  │     │
│  │  theta_int (n×T)   │  │    │  └──────────────────────┘     │
│  │  K_a kernel (T,)   │  │    │                               │
│  │  delta_C           │  │    │  VarianceState (F3)           │
│  │ aging_projection   │──┼────┼──► F4T                        │
│  └───────┬────────────┘  │    │  ┌──────────────────────┐     │
│          ▼               │    │  │ structural_pct  100% │     │
│  UncertaintyResult (E4)  │    │  │ literature_pct    0% │     │
│  ┌────────────────────┐  │    │  │ measurement_pct   0% │     │
│  │ var_theta_t  (T,)  │  │    │  │ proxy_pct         0% │     │
│  │ ite_summaries {}   │  │    │  │ missing_pct       0% │     │
│  │ clinical_metrics   │  │    │  │ top_reducible []     │     │
│  │  ARR, RRR, NNT     │  │    │  └──────────────────────┘     │
│  └────────────────────┘  │    │                               │
│                          │    │  CRCIRiskEstimate (F4)        │
│                          │    │  ┌──────────────────────┐     │
│                          │    │  │ risk_pct       (%)   │     │
│                          │    │  │ risk_tier            │     │
│                          │    │  │ domain_profiles []   │     │
│                          │    │  │ calibration_status   │     │
│                          │    │  └──────────────────────┘     │
│                          │    │                               │
│                          │    │  PredictiveRiskEstimate (F4T) │
│                          │    │  ┌──────────────────────┐     │
│                          │    │  │ natural_curve        │     │
│                          │    │  │ intervention_curves  │     │
│                          │    │  │ risk_reductions      │     │
│                          │    │  └──────────────────────┘     │
└──────────────────────────┘    └───────────────┬───────────────┘
                                                │
                   ┌────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  RUNTIME: Session + Report Assembly                                   │
│                                                                       │
│  run_session() accepts ALL chain outputs:                             │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  ranking_result   ← D4-D6    (required — drives schedules)     │  │
│  │  composite        ← F1       (optional — CRCI composite)       │  │
│  │  stability        ← F2       (optional — decision stability)   │  │
│  │  variance         ← F3       (optional — variance decomp)      │  │
│  │  recovery         ← E2       (optional — temporal trajectories)│  │
│  │  overlay          ← E3       (optional — intervention overlay) │  │
│  │  uncertainty      ← E4       (optional — counterfactuals)      │  │
│  │  risk_estimate    ← F4       (optional — clinical risk %)      │  │
│  │  active_pathways  ← C4d      (optional — pathway activations)  │  │
│  │  bundle_result    ← D3       (optional — synergy diagnostics)  │  │
│  │  pw_ev_scores     ← B6.5     (optional — pathway evidence)    │  │
│  │  evidence_gaps    ← compiler (optional — gap analysis)         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Steps:                                                               │
│  RT-G: Schedule generation (ranking → SchedulePlan objects)           │
│  RT-H: Adaptive questioning (optional, unused in current run)         │
│  RT-I: Report assembly (everything → RecommendationReport)            │
│                                                                       │
│  Output: SessionResult                                                │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  .report (RecommendationReport) ◄── THE SINGLE OUTPUT ──►    │    │
│  │    .composite_score      ← F1 composite                      │    │
│  │    .primary_schedule     ← D4-D6 top rank → schedule plan    │    │
│  │    .alternative_schedules← D4-D6 ranks 2-5                   │    │
│  │    .pathway_profile      ← C4d pathway activations           │    │
│  │    .trajectories         ← E2/E3 temporal curves             │    │
│  │    .variance_decomposition← F3 five-source breakdown         │    │
│  │    .evidence_gaps        ← evidence_gap_compiler             │    │
│  │    .clinical_risk        ← F4 risk estimate                  │    │
│  │    .decision_trace       ← audit trail from all chains       │    │
│  │    .sensitivity_report   ← D4c edge sensitivities            │    │
│  │    .safety_flags         ← D3 safety warnings                │    │
│  │    .extraction_quality   ← completeness checker              │    │
│  │    .subpopulation_comparison ← F5 (when available)           │    │
│  │  .ranked_schedules       ← RT-G full schedule list           │    │
│  └───────────────────────────────────────────────────────────────┘    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION: Read-Only Rendering (no computation)                   │
│                                                                       │
│  Input: RecommendationReport (single object)                          │
│                                                                       │
│  Patient-Facing Views:                                                │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ PAT1  crci_dashboard    .composite_score → gauge + domain bars│   │
│  │ PAT2  intervention_cards .primary/alt_schedules → ranked cards│   │
│  │ PAT3  trajectory_plot   .trajectories → time-series charts    │   │
│  │ PAT4  variance_pie      .variance_decomposition → pie chart   │   │
│  │ PAT5  pathway_display   .pathway_profile → pathway diagram    │   │
│  │       risk_dashboard    .clinical_risk → risk gauge + domains │   │
│  │       quality_disclosure.extraction_quality → caveats panel   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Scientist-Facing Views:                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ SCI1  evidence_browser  .evidence_gaps → gap prioritization   │   │
│  │ SCI2  dag_viz           .decision_trace → graph visualization │   │
│  │ SCI3  provenance_viewer .decision_trace → audit sankey/tree   │   │
│  │ SCI4  model_inspection  .decision_trace → assumptions panel   │   │
│  │ SCI5  research_dashboard.evidence_gaps → research priorities  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Final Output: Terminal ASCII / JSON (via render_report.py)           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Matrix (What Reads What)

Each ✓ means the row's output is consumed by the column's chain.

| Output ↓ \ Consumer → | Chain B | Chain C | Chain D | Chain E | Chain F | Runtime |
|------------------------|---------|---------|---------|---------|---------|---------|
| **GraphObject** (A)     | ✓       | ✓ (via B)| ✓ (node map)| —    | ✓ (node map)| ✓ (labels)|
| **FrozenModelState** (B)| —       | ✓       | ✓       | —       | —       | ✓ (pw scores)|
| **PatientState** (C)    | —       | —       | ✓       | ✓ (E1) | ✓ (F1,F3)| —      |
| **RawPosterior** (C)    | —       | —       | —       | —       | ✓ (F4 fusion)| —   |
| **LoadedPrior** (C)     | —       | —       | —       | —       | —       | ✓ (fallback)|
| **MCDraws** (D1)        | —       | —       | D2,D3   | —       | ✓ (F4)  | —      |
| **EffectResult** (D2)   | —       | —       | D3,D4-D6| ✓ (E3) | —       | —      |
| **SafetyResult** (D3)   | —       | —       | D4-D6   | —       | —       | —      |
| **BundleResult** (D3)   | —       | —       | D4-D6   | —       | —       | ✓      |
| **RankingResult** (D4-D6)| —      | —       | —       | ✓ (E3) | ✓ (F2)  | ✓      |
| **NadirEstimate** (E1)  | —       | —       | —       | E2      | —       | —      |
| **RecoveryTrajectory** (E2)| —    | —       | —       | E3,E4   | ✓ (F4T) | ✓      |
| **OverlayResult** (E3)  | —       | —       | —       | E4      | ✓ (F4T) | ✓      |
| **UncertaintyResult** (E4)| —     | —       | —       | —       | —       | ✓      |
| **CompositeState** (F1) | —       | —       | —       | —       | F4,F4T  | ✓      |
| **StabilityState** (F2) | —       | —       | —       | —       | —       | ✓      |
| **VarianceState** (F3)  | —       | —       | —       | —       | —       | ✓      |
| **CRCIRiskEstimate** (F4)| —      | —       | —       | —       | —       | ✓      |

---

## Live Pipeline Values (run 2026-02-27)

Actual values from `run_full_model.py --patient-id PAT_001 --cancer-type breast --treatment-phase active_chemo`:

```
Chain A → 63 nodes, 143 edges, 67 instruments
Chain B → 18 evidence records → FrozenModelState
Chain C → context: breast_active_chemo (fallback=global), 0 obs fused, 0 active pathways
Chain D → 5 interventions ranked, 0 blocked
          10,000 MC draws
          Top: ACT_EXERCISE_AEROBIC + ACT_COGNITIVE_TRAINING bundle (SAFE_B=0.13)
Chain E → Nadir estimated, recovery trajectory, intervention overlay, uncertainty
Chain F → CRCI composite=0.000, percentile=50.0, severity=MILD_IMPAIRMENT
          Stability: STABLE (P(rank=1) = 81%)
          Variance: 100% structural, 0% literature (only 18 evidence rows)
Runtime → 1 primary schedule, 4 alternatives
          All fit into one RecommendationReport object
Presentation → Terminal ASCII report rendered
```

### Why the Values Look Flat

- **Composite = 0.000 / Percentile = 50**: No patient observations provided → no Bayesian update → posterior = prior = population mean → z = 0 for all domains.
- **Variance 100% structural**: With only 18 evidence rows and 0 observations, all uncertainty is from model structure rather than from measured data disagreement.
- **SAFE_B = 0.13 (marginal)**: `intervention_kernels_v1` is empty (0 rows) → Chain D has limited effect magnitudes → small expected benefits.

---

## The Three Key Bottlenecks (Ranked by Impact)

### 1. `intervention_kernels_v1` = 0 rows → Chain D uses mock/limited ranking
**What it blocks**: Real Monte Carlo simulation of intervention effects. Chain D currently produces placeholder rankings.
**What fixes it**: Seed the table with 8 actions × their evidence-based effect magnitudes on cognitive nodes.
**Impact**: Turns SAFE_B scores from near-zero to clinically meaningful values.

### 2. 0 patient observations → Chain C prior-only → all z-scores = 0
**What it blocks**: Personalized cognitive profile. Without observations, every patient looks identical (population mean).
**What fixes it**: Providing even 1-2 instrument observations via `--observations-csv` drives the Bayesian update.
**Impact**: Domain z-scores become non-zero → composite differentiates domains → recommendations become patient-specific.

### 3. Chain B reads 10 of 107 edge_evidence columns → no scope matching
**What it blocks**: Cancer-type-specific evidence weighting. Breast cancer evidence is treated same as prostate.
**What fixes it**: Expanding Chain B's SELECT to include `cancer_type`, `treatment_phase`, and `scope_weights_json`.
**Impact**: Recommendations become cancer-type-aware (requires diverse extracted papers first).

---

## How Outputs Build On Each Other (Plain English)

1. **Chain A builds the map** — 63 cognitive/biological nodes connected by 143 edges. This is the DAG skeleton.

2. **Chain B fills in the edge weights** — reads 18 evidence rows from real papers, pools them via IVW, and produces `B_hat` (the parameterized weight matrix). Also computes inclusion probabilities and prior specifications. This "freezes" the model state.

3. **Chain C asks: where is THIS patient?** — loads context-matched priors for the patient's cancer type + treatment phase, fuses any observations (test scores, biomarkers) via Bayesian update, and applies effect modifiers. Produces a personalized `PatientState` (posterior mean + covariance).

4. **Chain D simulates interventions** — draws 10,000 Monte Carlo samples from the patient's posterior, propagates each intervention's effect through the DAG, checks safety, evaluates synergy between bundles, and ranks everything. The output is `RankingResult` with SAFE scores and credible intervals.

5. **Chain E projects forward in time** — estimates the cognitive nadir, computes a natural recovery trajectory, overlays intervention effects at each time horizon, and generates uncertainty counterfactuals (ARR, NNT).

6. **Chain F computes analytics** — F1 collapses the posterior into a single CRCI composite score with severity tiers. F2 measures decision stability (how robust is the top recommendation). F3 decomposes variance into 5 sources. F4 estimates clinical risk P̂(CRCI). F4T produces temporal risk curves.

7. **Runtime funnels everything into one `RecommendationReport`** — schedule generation (RT-G) converts rankings into actionable plans, report assembly (RT-I) maps all chain outputs into the output contract's fields.

8. **Presentation renders** — each module reads one slice of the report and produces a view model. Terminal output renders the final ASCII report. JSON export available for programmatic consumption.

**The critical insight**: Every chain adds a layer of information, and later chains _cannot_ improve beyond what earlier chains provide. If Chain B has only 18 evidence rows, Chain D's Monte Carlo simulation is sampling from poorly-estimated distributions. If Chain C has 0 observations, Chain F's composite score is just the population prior. **The system is only as good as its data inputs.**
