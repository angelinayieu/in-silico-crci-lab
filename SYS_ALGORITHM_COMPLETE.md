# SYS_ALGORITHM_COMPLETE

## Part 1: System Card (SYS_ALGORITHM)

**Version:** 1.1-CORRECTED (post-citation-audit)
**Source:** CRCI_v1.1_CORRECTED.md (§2.0–§2.22, §3, §4.5)
**Date:** 2026-02-22

### 1. Identity

| Field | Value |
| --- | --- |
| System ID | SYS_ALGORITHM |
| Name | CRCI Bayesian Causal Simulation Engine |
| Purpose | Transform literature-derived causal graph parameters and patient-specific clinical observations into ranked, personalized intervention recommendations with calibrated uncertainty, temporal trajectory predictions, and research priority identification |
| Scope | Everything from populated registries (output of SYS_EXTRACTION) through clinical/research output. Excludes evidence extraction, PDF processing, UI rendering. |

What this system IS: A computational engine that takes a frozen parameterized causal graph + live patient data and produces actionable clinical predictions.
What this system is NOT: It does not extract evidence from papers (that's SYS_EXTRACTION), it does not learn edge weights from individual patients (v2.0 feature), and it does not render visualizations (that's SYS_RUNTIME).

---

### 2. Macro Chain
The end-to-end transformation, showing all 6 chains with boundary tables between them.

```text
FROM SYS_EXTRACTION                                              TO SYS_RUNTIME
═══════════════════                                              ═══════════════

 10 CSV Registries     ┌───────────┐                             Clinical Output
 (evidence_registry,   │  CHAIN A  │   Parameterized             Package
   node_registry,       │  GRAPH    │   Graph Object              (rankings,
   edge_registry,  ────▶│  ASSEMBLY │──────────────┐              trajectories,
   instrument_reg,      │           │              │              stability,
   modifier_reg,        │ BUILD-TIME│              │              research
   synergy_reg,         └───────────┘              │              priorities)
   recovery_reg,                                   ▼                    ▲
   correlation_reg,               ┌───────────────────────┐            │
   feedback_reg,                  │       CHAIN B          │            │
   kernel_reg)                    │  EDGE PARAMETERIZATION │            │
                                                 │                        │            │
                                                 │      BUILD-TIME        │            │
                                                 └───────────┬────────────┘            │
                                                                   │                         │
                                                    Frozen Model State                  │
                                                    {B̂, Σ_eff, Λ_prior,               │
                                                      P_inclusion, priors}               │
                                                                   │                         │
                               Patient  ┌──────────────▼──────────┐              │
                               Observations            │                         │
                               (y_k)   │       CHAIN C            │              │
                            ─────────▶│  PATIENT STATE           │              │
                                           │  INFERENCE               │              │
                                           │       RUNTIME            │              │
                                           └──────────────┬───────────┘              │
                                                                  │                          │
                                                   Posterior θ̂, Σ_post,                │
                                                   Active Pathway Map                   │
                                                                  │                          │
                                             ┌─────────────▼───────────┐              │
                                             │        CHAIN D           │              │
                                             │  INTERVENTION            │              │
                                             │  SIMULATION              │              │
                                             │        RUNTIME           │              │
                                             └─────────────┬────────────┘              │
                                                                  │                          │
                                                   Ranked Interventions,                │
                                                   Bundle Effects,                      │
                                                   Dose Recommendations                 │
                                                                  │                          │
                                             ┌─────────────▼───────────┐              │
                                             │        CHAIN E           │              │
                                             │  TEMPORAL                │              │
                                             │  PREDICTION              │              │
                                             │        RUNTIME           │              │
                                             └─────────────┬────────────┘              │
                                                                  │                          │
                                                   Trajectory Curves,                   │
                                                   ITE at horizons,                     │
                                                   ARR/RRR/NNT                          │
                                                                  │                          │
                                             ┌─────────────▼───────────┐              │
                                             │        CHAIN F           │              │
                                             │  OUTPUT &                │──────────────┘
                                             │  ANALYTICS               │
                                             │        RUNTIME           │
                                             └─────────────────────────┘
```

Critical architectural boundary: THE CUT Chains A+B are BUILD-TIME. Chains C–F are RUNTIME. The cut-model constraint (Liu, Bayarri & Berger, 2009) ensures:
- Edge parameters β flow DOWN from build-time → runtime (via Λ_prior)
- Patient observations y flow ONLY within runtime
- Patient data NEVER updates edge beliefs (prevents feedback contamination)

```text
══════════════════════════════════════════
║          THE CUT BOUNDARY             ║
║  β fixed below │ θ inferred above     ║
║  BUILD-TIME     │ RUNTIME              ║
══════════════════════════════════════════
```

---

### 3. Chain Inventory

| Order | Chain ID | Name | Phase | Timing | Input State | Output State | Subsystem Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | ALG-A | Graph Assembly | PHASE_A | Build-time (one-time) | 10 CSV registries | Graph skeleton (V, E, B_skeleton, D, Λ_structure) | 5 |
| B | ALG-B | Edge Parameterization | PHASE_B | Build-time (per-update) | Graph skeleton + evidence_registry | Frozen model state (B̂, Σ_eff, Λ_prior, P_inclusion) | 7 |
| C | ALG-C | Patient State Inference | PHASE_C | Runtime (per-patient) | Frozen model + patient observations y_k | Posterior θ̂, Σ_post, active pathway map | 4 |
| D | ALG-D | Intervention Simulation | PHASE_D | Runtime (per-patient) | Posterior θ̂ + frozen model + intervention registry | Ranked interventions, bundles, doses | 6 |
| E | ALG-E | Temporal Prediction | PHASE_E | Runtime (per-patient) | Chain D outputs + recovery_registry + kernel_registry | Trajectory curves, ITE, clinical metrics | 4 |
| F | ALG-F | Output & Analytics | PHASE_F | Runtime (per-patient) | All Chain C–E outputs | Clinical/Research/Population output packages | 5 |

Total subsystems: ~31

> NOTE: Chain overviews (sections 4-9 of the original system card) are SUPERSEDED by the canonical Tier 2 Chain Cards below. The overviews were summary-depth (~50 lines each). The chain cards below are canonical-depth (400-600 lines each) with full sub-step boxes, intermediate state schemas, and specific parameter values.

---

### 10. Table Inventory
All tables owned by SYS_ALGORITHM, grouped by role.

#### Source Registries (human-curated, fixed at build-time)
| Table | Rows | Role | Read By Chains | Mutability |
| --- | --- | --- | --- | --- |
| node_registry.csv | 63 | Structural scaffold | A, C | Fixed |
| edge_registry.csv | 118 | Derived edge parameters | A, B | Computed — NEVER manually edit |
| evidence_registry.csv | 446+ | Raw study extractions | B | Human-edited only |
| instrument_registry.csv | 23 | Measurement specs | A, C | Fixed |
| modifier_registry.csv | 109 | Effect modifier rules | C | Fixed |
| synergy_registry.csv | 15 | Pairwise interactions | D | Fixed |
| recovery_registry.csv | 7 | Natural trajectory params | E | Fixed |
| correlation_registry.csv | 8 | Correlated mediator pairs | A | Fixed |
| feedback_loop_registry.csv | 5 | Loop members + gains | A | Fixed |
| intervention_kernel_registry.csv | 9 | Onset/build/steady/decay | E | Fixed |

#### Derived / Intermediate (computed by pipeline)
| Table | Produced By | Consumed By | Content |
| --- | --- | --- | --- |
| prior_audit_trail | B3 | F5 | Prior type + parameters per edge |
| chain_direct_validation | B6 | F5 | Z-scores, AV scores, discrepancy flags |
| patient_posterior_log | C3 | D1, E1, F1 | Per-patient θ̂, Σ_post snapshots |
| simulation_results_log | D1-D6 | E3, F1-F5 | Per-draw outcomes for audit |
| trajectory_predictions | E1-E4 | F1 | Monthly trajectory + CrI per scenario |

#### Configuration / Policy (editable but not evidence)
| Table | Rows | Content | Read By |
| --- | --- | --- | --- |
| context_matched_priors | 33 | Cancer-type × treatment-phase → μ, σ per node | C1 |
| claim_attenuation_policy | 4 | Identification status → attenuation factor | B2 |
| evidence_freshness_policy | — | Year → w_fresh | B2 |
| dose_response_registry | 9 | Per-intervention Emax, EC₅₀, h | D2 |
| ACC_table | 5 | Treatment context → aging acceleration coefficient | E3 |
| severity_thresholds | 6 | Six-tier severity classification boundaries | F1 |

───────────────────────────────────────────────────────────────────────────
11. CROSS-CUTTING CONCERNS
The Cut Constraint (spans A/B ↔ C/D/E/F boundary)
Build-time chains (A, B) produce frozen β — never modified by runtime
Runtime chains (C–F) infer θ conditional on frozen β̂
Full posterior: p(θ,β|y,lit) = p(θ|y,β̂) × Π_e p(β_e|lit_e)
v2.0 upgrade path: hierarchical random slopes for active β learning
Causal Language Gate (spans D → F)
Three-tier epistemology: causal_supported / associational_only / model_implied
Path-level inheritance: weakest link in chain
Demotion policy: confounding audit, replication failure, Z≥3.0
Temporal predictions: mandatory "Model predicts..." prefix
Sign Convention (spans all chains)
Symptom burden: higher-is-worse
Functional capacity: higher-is-better
Intervention dose: higher-is-more
Automated orientation gate before any β × θ computation
Physiological Ceilings (spans D, E)
Single intervention: ±1.0 SD per node
Bundle: ±1.5 SD per node
Calibrated from largest documented CRCI effects
Binding Assumptions (8 constraints on all chains)
Linear-Gaussian SEM (no non-linear node interactions beyond Emax edges)
Cut-model (no β learning from individual patients)
Mode A interventions (associational shift, not do-calculus)
Static β (no temporal drift in population parameters)
Independent β posteriors (no multivariate edge correlation)
Gaussian states (no mixture models for non-Gaussian nodes)
Point-estimate modifiers (no full posterior on modifier values)
Single-trajectory recovery (no multi-phase recovery patterns)
───────────────────────────────────────────────────────────────────────────
12. EXTERNAL INTERFACES
Direction
External System
Data
Format
IN
SYS_EXTRACTION
Populated 10 CSV registries (post-extraction, harmonized, aggregated)
CSV with SHA-256 hashes
IN
SYS_RUNTIME (clinical)
Patient observations y_k (instruments, biomarkers, demographics)
Typed observation records
IN
Human curators
Modifier rules, recovery parameters, context-matched priors
CSV edits to config tables
OUT
SYS_RUNTIME (clinical)
ClinicalOutputPackage per patient
Typed output records
OUT
SYS_RUNTIME (research)
ResearchOutputPackage (evidence gaps, EVSI, study designs)
Typed output records
OUT
SYS_RUNTIME (population)
PopulationOutputPackage (archetypes, stratified defaults)
Typed output records

───────────────────────────────────────────────────────────────────────────
13. IMPLEMENTATION SEQUENCING
Build order respecting dependency chain:
PHASE 0:  Data Infrastructure
          → Define all 10 CSV schemas + validation contracts
          → Build SHA-256 provenance layer
          → Implement context-matched prior loading (33 specs)

PHASE 1:  Chain A — Static Graph (one-time)
          → Node hierarchy, B skeleton, D matrix, Λ computation
          → Feedback loop stability verification
          → Test: Λ positive-definite, κ(Λ) < 10¹⁰

PHASE 2:  Chain B — Evidence Pipeline (per-update)
          → IVW pooling + DL heterogeneity
          → 7-layer SE_eff computation
          → Prior selection tree + P_inclusion
          → Chain-vs-direct validation
          → Test: prior audit trail complete, all edges parameterized

PHASE 3:  Chain C — Patient Inference (per-patient)
          → Measurement model + information-form updates
          → Effect modifier stack (109 rules)
          → Test: posterior recovery matches known patient profiles

PHASE 4:  Chain D — Intervention Simulation (per-patient)
          → MC engine (10K draws) + structural inclusion
          → Matrix inversion + path enumeration fallback
          → Synergy + SAFE scoring + dose optimization
          → Test: common random numbers reduce comparison variance

PHASE 5:  Chain E — Temporal Prediction (per-patient)
          → Natural recovery + intervention overlay + aging
          → Uncertainty growth + counterfactuals
          → Test: trajectory CrI covers observed longitudinal data

PHASE 6:  Chain F — Output & Analytics
          → Composite scoring + decision stability
          → Variance decomposition + research analytics
          → Population archetype discovery
          → Test: end-to-end reproducibility with fixed seed

Performance target (not yet specified in paper): 63×63 matrix × 10,000 draws — latency requirement TBD. Matrix inversion is O(n³) = O(250,000) per draw × 10K = 2.5×10⁹ ops. With path enumeration fallback, worst case is DFS over 118 edges.
───────────────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════════════
                    PART 2: TIER 2 — CHAIN CARDS
                    (Canonical depth: 400-600 lines each)
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
TABLE NAME BINDING KEY (applies to all chain cards below):
  node_registry.csv       → nodes_v1 (Class A, 63 rows)
  edge_registry.csv       → edges_v1 (Class C, 118 rows) 
  instrument_registry.csv → instruments_v1 (Class A, 23 rows)
  correlation_registry.csv → correlation_registry_v1 (Class A, 12 rows)
  feedback_loop_registry.csv → feedback_loops_v1 (Class A, 5 rows)
  evidence records        → edge_evidence_v1 (Class B, scales with papers)
  modifier_registry       → modifier_registry_v1 (Class A, 109 rows)
  recovery_params         → recovery_params_v1 (Class A, 7 rows)
  context_matched_priors  → context_matched_priors_v1 (Class A, 33 rows)
  action_catalog          → action_catalog_v1 (Class A)
  synergy_registry        → synergy_registry_v1 (Class B, 15 rows)
  intervention_kernels    → intervention_kernels_v1 (Class A)
  dose_response_params    → dose_response_params_v1 (Class C)
  pathway_map             → pathway_map_v1 (Class A, 21 rows)
  state_snapshots         → state_snapshots_v1 (Class E, per-session)
  prior_selection_log     → prior_selection_log_v1 (Class E, audit)
  intervention_rankings   → intervention_rankings_v1 (Class E)
───────────────────────────────────────────────────────────────────────────

## CHAIN CARD: ALG-A

═══════════════════════════════════════════════════════════════════════════ CHAIN CARD: ALG-A (Graph Assembly) ═══════════════════════════════════════════════════════════════════════════ Version: 1.1-CORRECTED Parent System: SYS_ALGORITHM
1. IDENTITY
Field
Value
Chain ID
ALG-A
System
SYS_ALGORITHM
Name
Graph Assembly
Purpose
Assemble the 63-node, 118-edge causal DAG into computational objects: B matrix skeleton, block-diagonal D, precision matrix Λ, pathway maps, latent variable structure, and feedback loop stability verification
Phase
PHASE_A — Build-time, one-time (re-run only when DAG topology changes)

───────────────────────────────────────────────────────────────────────────
2. CHAIN DIAGRAM
FROM SYS_EXTRACTION                                           TO CHAIN ALG-B
═══════════════════                                           ═════════════════

 node_registry.csv ─┐
 edge_registry.csv ─┤    ┌──────────┐   NodeMap    ┌──────────┐   B_skeleton
 instrument_reg ────┤───▶│  A1      │─────────────▶│  A2      │──────────┐
 correlation_reg ───┤    │  Node    │              │  Edge    │          │
 feedback_reg ──────┘    │  Hierarchy│              │  Matrix  │          │
                         │  Assembly │              │  Build   │          │
                         └──────────┘              └──────────┘          │
                                                                         │
                          B_skeleton + correlation_reg                    │
                                       │                                 │
                                       ▼                                 │
                              ┌──────────────┐   D_matrix    ┌──────────▼─────┐
                              │  A3          │──────────────▶│  A4            │
                              │  Residual    │              │  Precision     │
                              │  Covariance  │              │  Matrix        │
                              │  Assembly    │              │  Assembly      │
                              └──────────────┘              └──────────┬─────┘
                                                                       │
                                                            Λ_structure │
                                                                       │
                              ┌─────────────────────────────────────────▼─────┐
                              │  A5                                           │
                              │  Pathway & Latent Structure Registration      │
                              │  (reads: node_reg, edge_reg, instrument_reg,  │
                              │   feedback_reg, Λ_structure)                  │
                              └──────────────────────┬────────────────────────┘
                                                     │
                                                     ▼
                                              GraphObject
                                        (complete output state)
                                                     │
                                              TO CHAIN ALG-B

Data flow type: All intermediate states are IN-MEMORY typed objects. No tables are written by this chain; it only READS source registries.
───────────────────────────────────────────────────────────────────────────
3. INTERMEDIATE STATE SCHEMAS
State: NodeMap (after A1)
Field
Type
Description
Produced By
Consumed By
nodes
list[NodeDef] (63 entries)
Complete node definitions
A1
A2, A3, A5
layer_assignment
dict[node_id → int 0-6]
Hierarchical layer
A1
A2, A5
domain_assignment
dict[node_id → enum(11)]
Clinical domain
A1
A5
observability
dict[node_id → bool]
Observable (48) vs latent (15)
A1
A5
orientation
dict[node_id → enum{POS_UP, POS_DOWN}]
Sign convention
A1
A2, A5
topological_order
list[node_id]
Valid DAG ordering (L0→L6)
A1
A2

State: B_skeleton (after A2)
Field
Type
Description
Produced By
Consumed By
B_struct
ℝ^{63×63} sparse
Non-zero pattern with functional form flags
A2
A3, A4
functional_forms
dict[edge_id → enum{linear, hill, loglinear, threshold}]
Per-edge form
A2
A5
hill_params
dict[edge_id → {E_max, EC₅₀, h}]
For 34 Hill/Emax edges
A2
A5
edge_claim_levels
dict[edge_id → enum{causal, associational, model_implied}]
Initial claim level
A2
A5
edge_count
int
Should be 118
A2
validation
acyclicity_verified
bool
DAG constraint satisfied
A2
validation

State: D_matrix (after A3)
Field
Type
Description
Produced By
Consumed By
D
ℝ^{63×63} block-diagonal
Residual covariance matrix
A3
A4
D_blocks
{D_independent, Σ_inflammatory, Σ_neuro_stress}
Named blocks
A3
A5
residual_variances
ℝ^{63} vector
σ²_{ε,i} = 1 − R²_i (floored at 0.05)
A3
A4, A5
correlation_pairs
8 × {node_i, node_j, ρ, source}
Empirical ρ entries
A3
A5
R_squared_per_node
ℝ^{63}
R²_i = Σ_j β²_{ji}
A3
A5

State: Λ_structure (after A4)
Field
Type
Description
Produced By
Consumed By
Λ
ℝ^{63×63}
Precision matrix (structural form)
A4
A5
is_positive_definite
bool
Must be True
A4
validation
condition_number
float
κ(Λ); flag if > 10⁸
A4
validation, A5
sparsity_pattern
set[(i,j)]
Non-zero entries in Λ
A4
A5
spectral_radius_B
float
ρ(B); must be < 1 for convergence
A4
A5, validation

State: GraphObject (final output)
Field
Type
Description
Produced By
Consumed By
(all B_skeleton fields)




A2
ALG-B
(all D_matrix fields)




A3
ALG-B
(all Λ_structure fields)




A4
ALG-B, ALG-C
node_hierarchy
NodeMap
Complete 63-node metadata
A1
all chains
pathway_map
20 × PathwayDef
Pathway definitions
A5
ALG-C, ALG-D
proxy_table
15 × ProxyDef
Latent-proxy mappings
A5
ALG-C
feedback_loops
5 × LoopDef
Loop specs with computed gains
A5
ALG-E
edgeless_nodes
8 × node_id
Nodes without edges
A5
ALG-F (research)

───────────────────────────────────────────────────────────────────────────
4. SUBSYSTEM INVENTORY
Order
Subsystem ID
Name
Input State
Output State
Type
1
ALG-A1
Node Hierarchy Assembly
node_registry CSV
NodeMap
ATOMIC
2
ALG-A2
Edge Matrix Construction
NodeMap + edge_registry CSV
B_skeleton
ATOMIC
3
ALG-A3
Residual Covariance Assembly
B_skeleton + correlation_registry CSV
D_matrix
ATOMIC
4
ALG-A4
Precision Matrix Assembly
B_skeleton + D_matrix
Λ_structure
ATOMIC
5
ALG-A5
Pathway & Latent Registration
All prior states + instrument_reg + feedback_reg
GraphObject
COMPOSITE

───────────────────────────────────────────────────────────────────────────
5. SUBSYSTEM DETAIL
A1 — Node Hierarchy Assembly
Field
Value
ID
ALG-A1
Type
ATOMIC
Purpose
Parse 63-node registry into typed computational objects with layer, domain, observability, and orientation assignments
Phase
PHASE_A
Research Phase
RESEARCH_TOPOLOGY (structure must be confirmed)

Steps:
Load node_registry.csv (63 rows)
Validate: all 63 nodes present, no duplicates, all required fields non-null
Assign each node to layer (0-6) — verify DAG layering: no node in layer L has a parent in layer L' ≥ L
Assign each node to one of 11 clinical domains
Classify: 48 observable / 15 latent
Compute topological order via Kahn's algorithm (verify acyclicity)
Map orientation convention per node: symptom = POS_DOWN, function = POS_UP
Validation gate: 63 nodes loaded; layering consistent with DAG; no orphan assignments.
A2 — Edge Matrix Construction
Field
Value
ID
ALG-A2
Type
ATOMIC
Purpose
Initialize the B ∈ ℝ^{63×63} sparse matrix skeleton with 118 non-zero entries, each tagged with functional form
Phase
PHASE_A
Research Phase
RESEARCH_TOPOLOGY

Steps:
Load edge_registry.csv (118 rows)
For each edge (source, target):
Verify source and target exist in NodeMap
Verify source_layer < target_layer (DAG constraint) OR edge is in a registered feedback loop
Set B[source, target] = placeholder (actual weight assigned in ALG-B)
Record functional form: linear (54), Hill/Emax (34), log-linear, threshold
For Hill/Emax edges, load dose-response parameters {E_max, EC₅₀, h}
Record initial claim level per edge from registry
Verify: acyclicity (ignoring temporal feedback edges handled via time-indexed expansion)
Compute edge density: 118 / (63×62) = 0.030
Key formulas:
ID
Equation
Notes
A2-1
`f(x) = E_max·
x
A2-2
`density =
E

Validation gate: 118 edges; acyclicity confirmed; all source/target valid; 55 connected + 8 edgeless = 63.
A3 — Residual Covariance Assembly
Field
Value
ID
ALG-A3
Type
ATOMIC
Purpose
Build the block-diagonal residual covariance matrix D with 8 empirical off-diagonal correlation pairs
Phase
PHASE_A
Research Phase
RESEARCH_PARAMETERS (ρ values from literature)

Steps:
For each node i, compute R²_i = Σ_j β²_{ji} (sum over parents j)
Note: β values are placeholders at this stage — use initial estimates from edge_registry
Final R²_i recomputed in ALG-B after parameterization
Derive residual variance: σ²_{ε,i} = 1 − R²_i
Floor at 0.05: σ²_{ε,i} = max(1 − R²_i, 0.05)
Floor prevents degenerate precision when correlated parent effects yield R² > 1
Initialize D as diagonal with σ²_{ε,i} entries
Load correlation_registry.csv (8 pairs)
Insert off-diagonal blocks:
Pair
ρ
Block
Source
IL-6 ↔ TNF-α
0.65
Inflammatory
Felger et al., 2020
IL-6 ↔ CRP
0.72
Inflammatory
Felger et al., 2020
TNF-α ↔ CRP
0.58
Inflammatory
Felger et al., 2020
BDNF ↔ IL-6
−0.35
Neuro-stress
Ng et al., 2023
Cortisol ↔ IL-6
0.28
Neuro-stress
Adam et al., 2017
BDNF ↔ cortisol
−0.22
Neuro-stress
Estimated
MDA ↔ IL-6
0.38
Inflammatory
Zhao et al., 2025 [VERIFY]
NfL ↔ TNF-α
0.31
Neuro-stress
Schroyen et al., 2021

Assemble: D = blockdiag(D_independent, Σ_inflammatory, Σ_neuro_stress)
Verify D is positive-definite
Key formulas:
ID
Equation
Notes
A3-1
R²_i = Σ_j β²_{ji}
Variance explained by parents (§2.6)
A3-2
σ²_{ε,i} = max(1 − R²_i, 0.05)
Floored residual (§2.6)
A3-3
D = blockdiag(D_ind, Σ_inflam, Σ_neuro)
Block structure (§2.17.2)

Research dependencies:
Dependency
Status
Priority
Zhao et al. 2025 (MDA ↔ IL-6, ρ=0.38)
UNVERIFIED — possible phantom ref
HIGH
BDNF ↔ cortisol (ρ=−0.22)
Author-estimated, no direct source
MEDIUM

Validation gate: D positive-definite; 8 off-diagonal pairs inserted; all ρ ∈ (−1, 1).
A4 — Precision Matrix Assembly
Field
Value
ID
ALG-A4
Type
ATOMIC
Purpose
Compute the implied precision matrix Λ from B and D, verify positive-definiteness and numerical stability
Phase
PHASE_A
Research Phase
RESEARCH_NONE (pure computation)

Steps:
Compute: Λ = (I − B)ᵀ D⁻¹ (I − B)
Verify Λ is symmetric positive-definite (Cholesky factorization test)
Compute condition number: κ(Λ) = λ_max / λ_min
Flag WARNING if κ > 10⁸
Flag CRITICAL if κ > 10¹⁰ (matrix inversion unstable → force path enumeration in ALG-D)
Compute spectral radius: ρ(B) = max eigenvalue magnitude of B
Must satisfy ρ(B) < 1 for Neumann series convergence
Current: ρ(B) = 0.41 (well within bounds)
Record sparsity pattern: Λ_ij = 0 encodes conditional independence
Key formulas:
ID
Equation
Notes
A4-1
Λ = (I − B)ᵀ D⁻¹ (I − B)
Precision from SEM (§2.6)
A4-2
κ(Λ) = λ_max / λ_min
Condition number for stability
A4-3
`ρ(B) = max
eigenvalue(B)

Validation gate: Λ positive-definite; ρ(B) < 1; κ(Λ) < 10¹⁰.
A5 — Pathway & Latent Structure Registration
Field
Value
ID
ALG-A5
Type
COMPOSITE
Purpose
Register 20 pathways, 15 latent-proxy pairs, feedback loops, and edgeless nodes into the complete GraphObject
Phase
PHASE_A
Research Phase
RESEARCH_TOPOLOGY + RESEARCH_PARAMETERS

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: A5a — Pathway Map Construction │ │ Purpose: Map 20 pathways (15 Tier 1 + 5 Tier 2) from edge │ │ graph to named pathway objects │ │ Input: B_skeleton (edge list), node_hierarchy │ │ Output: pathway_map: 20 × {id, name, tier, edges, nodes} │ │ Logic: For each pathway definition in the spec: │ │ - Extract constituent edges from B_skeleton │ │ - Verify all edges exist and form a connected path │ │ - Record pathway tier (1=mechanistic, 2=clinical) │ │ - Compute chain product β_chain = Π β_e (placeholder)│ │ Rules: Pathway with any missing edge → flagged INCOMPLETE │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: A5b — Latent-Proxy Registration │ │ Purpose: Register 15 latent nodes with their proxy │ │ instruments and R²_proxy-latent thresholds │ │ Input: node_hierarchy (latent nodes), instrument_reg │ │ Output: proxy_table: 15 × {latent_node, proxy, R², SE_mult}│ │ Logic: For each latent node: │ │ - Match to proxy instrument(s) from instrument_reg │ │ - Load R²_proxy-latent value │ │ - Assign SE multiplier per R² validity: │ │ R² ≥ 0.5 → 1.0×; 0.3-0.5 → 1.2-1.3×; │ │ 0.2-0.3 → 1.5×; <0.2 → 2.0× │ │ Rules: R²_proxy < 0.3 → node flagged LOW_PROXY_VALIDITY │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: A5c — Feedback Loop Verification │ │ Purpose: Load 5 feedback loops, compute gains, verify │ │ stability via spectral analysis │ │ Input: feedback_loop_registry, B_skeleton, Λ_structure │ │ Output: feedback_loops: 5 × {edges, gain, period, stable} │ │ Logic: For each loop L: │ │ - gain(L) = Π_{e∈L} |β_e| │ │ - Verify gain < 1 (necessary for stability) │ │ - Record characteristic period │ │ - Cross-check with ρ(B) from A4 │ │ Rules: gain ≥ 1 → CRITICAL: system unstable │ │ gain > 0.5 → WARNING: slow convergence possible │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: A5d — Edgeless Node Identification │ │ Purpose: Identify 8 nodes without edges (structural │ │ placeholders) for research prioritization │ │ Input: B_skeleton, node_hierarchy │ │ Output: edgeless_nodes: 8 × {node_id, gap_rationale} │ │ Logic: Nodes with no incoming or outgoing edges in B │ │ Rules: Edgeless nodes excluded from MC simulation │ │ Flagged as HIGH PRIORITY evidence gaps │ └─────────────────────────────────────────────────────────────┘
Validation gate: 20 pathways registered; 15 latent-proxy pairs mapped; all 5 loop gains < 1; 8 edgeless nodes identified; GraphObject complete.
───────────────────────────────────────────────────────────────────────────
6. BOUNDARY TABLES
Direction
Table
Columns Used
Purpose
READS
node_registry.csv
id, layer, domain, orientation, observable
Node scaffold
READS
edge_registry.csv
source, target, functional_form, claim_level, E_max, EC₅₀, h
Edge scaffold
READS
instrument_registry.csv
instrument_id, target_node, loading, reliability
Proxy mapping
READS
correlation_registry.csv
node_i, node_j, rho, source_citation
Off-diagonal D
READS
feedback_loop_registry.csv
loop_id, member_edges, characteristic_period
Stability check
WRITES
(none — all output is in-memory GraphObject)





───────────────────────────────────────────────────────────────────────────
7. GATES & CHECKPOINTS
Gate ID
Position
Condition
Pass
Fail
A-G1
After A1
63 nodes loaded; layering valid; no orphans
→ A2
ABORT: registry corrupt
A-G2
After A2
118 edges; acyclicity (modulo feedback); all endpoints valid
→ A3
ABORT: DAG invalid
A-G3
After A3
D positive-definite; all ρ ∈ (−1, 1)
→ A4
ABORT: covariance invalid
A-G4
After A4
Λ positive-definite; ρ(B) < 1; κ(Λ) < 10¹⁰
→ A5
CRITICAL: matrix unstable
A-G5
After A5
All pathways, proxies, loops registered; GraphObject complete
→ ALG-B
ABORT: graph incomplete

───────────────────────────────────────────────────────────────────────────
8. CHAIN-LEVEL ASSUMPTIONS
#
Assumption
Impact if Violated
Binding Assumption #
1
Node hierarchy (7 layers) correctly represents causal ordering
Wrong topological order → wrong propagation direction
— (structural)
2
118 edges capture all relevant biological relationships
Missing edges = missing pathways; 8 edgeless nodes known
— (§2.22)
3
Block-diagonal D (8 pairs) captures all important residual correlations
Missing correlations → under-estimated cross-node uncertainty
Assumption 3 (parent independence)
4
Feedback loop gains computed from static β are valid
If β changes substantially, gains change → stability could shift
Assumption 4 (static β)
5
Linear-Gaussian SEM appropriate for z-score-transformed nodes
Non-Gaussian nodes (binary, ordinal) misspecified
Assumption 6 (linear SEM)

═══════════════════════════════════════════════════════════════════════════


## CHAIN CARD: ALG-B

═══════════════════════════════════════════════════════════════════════════ CHAIN CARD: ALG-B (Edge Parameterization) ═══════════════════════════════════════════════════════════════════════════ Version: 1.1-CORRECTED Parent System: SYS_ALGORITHM
1. IDENTITY
Field
Value
Chain ID
ALG-B
System
SYS_ALGORITHM
Name
Edge Parameterization
Purpose
Transform raw evidence records into parameterized edge weights with calibrated effective standard errors, prior distributions, structural inclusion probabilities, and chain-vs-direct validation — producing the frozen model state that crosses the cut boundary
Phase
PHASE_B — Build-time, per-evidence-update (re-run when SYS_EXTRACTION delivers new evidence)

This is the most methodologically complex chain in the system. It contains the central contribution (7-layer SE_eff) and the most author-constructed parameters.
───────────────────────────────────────────────────────────────────────────
2. CHAIN DIAGRAM
FROM CHAIN ALG-A                    FROM SYS_EXTRACTION
══════════════                      ═══════════════════

 GraphObject ─────┐  evidence_registry ──┐  synergy_registry ──┐
                  │  (446+ rows)         │  (15 rows)          │
                  ▼                      ▼                     │
          ┌──────────────┐                                     │
          │  B1           │                                    │
          │  IVW Pooling  │◀── per edge: k evidence records    │
          │  (per-edge)   │    DerSimonian-Laird τ²            │
          └──────┬───────┘                                     │
                 │                                             │
           PooledEdge[]                                        │
           {μ_e, SE_within,                                    │
            τ²_e, k, I²,                                      │
            aggregation_method}                                │
                 │                                             │
                 ▼                                             │
          ┌──────────────┐                                     │
          │  B2           │                                    │
          │  Seven-Layer  │                                    │
          │  Heterogeneity│                                    │
          │  Pipeline     │                                    │
          │  (per-record) │                                    │
          └──────┬───────┘                                     │
                 │                                             │
           SE_eff per edge                                     │
           (post-7-layer)                                      │
                 │                                             │
          ┌──────▼───────┐                                     │
          │  B3           │                                    │
          │  Prior        │                                    │
          │  Selection    │                                    │
          │  (per-edge)   │                                    │
          └──────┬───────┘                                     │
                 │                                             │
           PriorSpec per edge                                  │
           {type, params, w}                                   │
                 │                                             │
          ┌──────▼───────┐                                     │
          │  B4           │                                    │
          │  Structural   │                                    │
          │  Inclusion    │                                    │
          │  P_inclusion  │                                    │
          └──────┬───────┘                                     │
                 │                                             │
           P_inclusion per edge                                │
                 │                                             │
          ┌──────▼───────┐                                     │
          │  B5           │                                    │
          │  Heterogeneity│                                    │
          │  Priors       │                                    │
          │  (Turner 2012)│                                    │
          └──────┬───────┘                                     │
                 │                                             │
           τ² priors per edge                                  │
                 │                                             │
          ┌──────▼───────┐                                     │
          │  B6           │                                    │
          │  Chain-vs-    │                                    │
          │  Direct       │                                    │
          │  Validation   │                                    │
          └──────┬───────┘                                     │
                 │                                             │
           AV scores, Z-tests                                  │
                 │                                             │
          ┌──────▼───────┐◀────────────────────────────────────┘
          │  B7           │
          │  Context-     │
          │  Matched Prior│
          │  Assembly     │
          └──────┬───────┘
                 │
                 ▼
          FrozenModelState
          (complete output)
                 │
          TO CHAINS ALG-C, ALG-D, ALG-E

───────────────────────────────────────────────────────────────────────────
3. INTERMEDIATE STATE SCHEMAS
State: PooledEdge (after B1, one per edge)
Field
Type
Description
edge_id
str
Unique edge identifier
μ_e
float
IVW pooled point estimate
SE_within
float
Pooled within-study variance (1/Σ(1/σ²_i))
τ²_e
float
DerSimonian-Laird between-study heterogeneity
k
int
Number of contributing studies
I²
float [0,1]
Inconsistency index
aggregation_method
enum{BLOCKED, DIRECT, IVW_FIXED, IVW_RANDOM, STRATIFIED, SINGLE_BEST}
Decision tree outcome
contributing_studies
list[study_id]
For audit trail

State: HeterogeneityAdjustedEdge (after B2, one per edge)
Field
Type
Description
(all PooledEdge fields)




SE_eff
float
Effective SE after 7-layer compounding
layer_contributions
dict[L1-L7 → float]
Per-layer SE inflation factor
σ²_structural
float
Additive structural variance
w_scope
float [0.3, 1.0]
Transportability weight
w_fresh
float [0.70, 1.0]
Evidence freshness weight
attenuation_factor
float
Claim-level β attenuation

State: PriorSpec (after B3, one per edge)
Field
Type
Description
prior_type
enum{RobustMAP, Commensurate, PowerPrior, MechanisticSynth, StructuralPlaceholder}
Selected type
prior_params
dict
Type-specific: {w, MAP, vague} or {β_hist, σ²_hist, τ} or {a₀, D₀} or ...
selection_rationale
str
Why this type was selected (k, best_design)

State: InclusionProbEdge (after B4, one per edge)
Field
Type
Description
P_inclusion
float [0, 1]
Structural inclusion probability
inclusion_inputs
{k, Z, has_RCT}
Inputs to logistic
is_decision_critical
bool
True if force-ON vs force-OFF changes top rank

State: FrozenModelState (final output)
Field
Type
Description
B̂
ℝ^{63×63}
Parameterized edge weight matrix
Σ_eff
ℝ^{118}
Vector of effective SEs (post-7-layer)
Λ_prior
dict[context → ℝ^{63×63}]
33 context-matched precision matrices
P_inclusion
ℝ^{118}
Structural inclusion probabilities
prior_audit_trail
118 × PriorSpec
Complete prior documentation
AV_scores
dict[edge_id → float]
Alignment validity (chain+direct edges only)
τ²_estimates
ℝ^{118}
Per-edge heterogeneity variance
synergy_records
15 × SynergyRecord
Pairwise interaction data

───────────────────────────────────────────────────────────────────────────
4. SUBSYSTEM INVENTORY
Order
Subsystem ID
Name
Input State
Output State
Type
1
ALG-B1
IVW Pooling & Aggregation
GraphObject + evidence_registry
PooledEdge[]
COMPOSITE
2
ALG-B2
Seven-Layer Heterogeneity Pipeline
PooledEdge[] + evidence records
HeterogeneityAdjustedEdge[]
COMPOSITE (7 layers)
3
ALG-B3
Prior Selection Framework
HeterogeneityAdjustedEdge[]
PriorSpec[]
COMPOSITE (5 prior types)
4
ALG-B4
Structural Inclusion Probability
HeterogeneityAdjustedEdge[]
InclusionProbEdge[]
ATOMIC
5
ALG-B5
Heterogeneity Priors
PooledEdge[] (outcome type)
τ² prior distributions
ATOMIC
6
ALG-B6
Chain-vs-Direct Validation
All parameterized edges
AV_scores, Z-tests
ATOMIC
7
ALG-B7
Context-Matched Prior Assembly
All B1-B6 outputs + synergy_registry
FrozenModelState
COMPOSITE

───────────────────────────────────────────────────────────────────────────
5. SUBSYSTEM DETAIL
B1 — IVW Pooling & Aggregation
Field
Value
ID
ALG-B1
Type
COMPOSITE
Purpose
For each edge, pool contributing evidence records via inverse-variance weighting with DerSimonian-Laird heterogeneity estimation

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: B1a — Evidence Retrieval (per-edge) │ │ Purpose: Pull all evidence records targeting this edge │ │ Input: edge_id + evidence_registry │ │ Output: k records × {β_i, SE_i, design, year, scope...} │ │ Logic: Filter evidence_registry by target_edge_id │ │ Apply diminishing returns: w_base × 1/(1+0.3·ln(k))│ │ Apply precision caps: │ │ Cross-sectional: cap at 30% of best RCT precision│ │ Animal: cap at 10% of best human RCT precision │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: B1b — Aggregation Decision Tree │ │ Purpose: Select aggregation method based on evidence count │ │ and heterogeneity │ │ Decision tree: │ │ k = 0 → BLOCKED │ │ k = 1 → DIRECT (passthrough) │ │ k ≥ 2, ≥2 have SE: │ │ I² < 50% → IVW_FIXED │ │ 50% ≤ I² < 75% AND stratifiable → STRATIFIED │ │ 50% ≤ I² < 75% AND not strat. → IVW_RANDOM │ │ I² ≥ 75% AND stratifiable → STRATIFIED │ │ I² ≥ 75% AND not stratifiable → SINGLE_BEST │ │ Sign conflict among high-quality → BLOCKED │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: B1c — IVW Computation │ │ Purpose: Compute pooled estimate and heterogeneity │ │ Formulas: │ │ μ_e = Σ(β_i/σ²_i) / Σ(1/σ²_i) (IVW mean) │ │ SE_within = 1 / √(Σ(1/σ²_i)) (pooled SE) │ │ Q = Σ w_i(β_i − μ_e)² (Cochran's Q) │ │ τ² = max(0, (Q−(k−1)) / (Σw−Σw²/Σw)) (DL estimator) │ │ I² = max(0, (Q−(k−1))/Q) (inconsistency) │ │ SE_random = √(1/Σ(1/(σ²_i + τ²))) (random-effects)│ └─────────────────────────────────────────────────────────────┘
B2 — Seven-Layer Heterogeneity Pipeline
Field
Value
ID
ALG-B2
Type
COMPOSITE (7 sequential layers)
Purpose
Compound 7 orthogonal uncertainty sources into SE_eff per edge

This is the central methodological contribution of the framework.
Master formula:
SE_eff = √[(SE_pooled × m_claim × m_GRADE × m_temporal)² + σ²_structural + τ²·𝟙[not_in_base]]
         ─────────────────────────────────────────────────────────────────────────────────────
                                      max(w_scope, 0.3) × w_fresh

Seven layers (each a sub-step):
┌─────────────────────────────────────────────────────────────┐ │ LAYER L1 — Study Design (per-record) │ │ Mechanism: Claim-level SE multipliers │ │ Range: 1.0× – 6.0× │ │ Values: │ │ Large RCT (n>200): 1.0× │ │ Small RCT (n<100): 1.0–1.5× │ │ Well-adjusted cohort: 1.5–2.0× │ │ Unadjusted longitudinal: 2.0–2.5× │ │ Cross-sectional adjusted: 2.5–3.0× │ │ Cross-sectional unadjusted: 3.0–4.0× │ │ Animal in vivo: 3.0–5.0× │ │ In vitro / mechanistic: 5.0–6.0× │ │ Status: AUTHOR-CONSTRUCTED priors │ │ Calibration: Anglemyer (2014) ROR=1.08; van Zwet, │ │ Schwab & Senn (2021) 13% median power │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L2 — Transportability (per-record) │ │ Mechanism: 5-dimension scope weight, SE ÷ max(w_scope, 0.3) │ │ Five dimensions: │ │ (1) Population match (8 levels, 1.0× → 3.3×) │ │ (2) Design match │ │ (3) Outcome alignment (8 levels, 1.0× → 1.8×) │ │ (4) Cancer type match │ │ (5) Measurement compatibility │ │ w_scope = geometric mean of 5 dimension weights │ │ Floor: max(w_scope, 0.3) prevents infinite inflation │ │ Range: 1.0× – 3.33× (= 1/0.3) │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L3 — Statistical Heterogeneity (per-edge) │ │ Mechanism: τ² additive (DerSimonian-Laird) │ │ Double-counting guard: τ² added ONLY when not already │ │ in base SE (𝟙[not_in_base]) │ │ Standard methodology; not author-constructed │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L4 — Scale Compatibility (per-record) │ │ Mechanism: Compatibility gate + conversion SE │ │ Three categories: │ │ COMPARABLE: same scale → no penalty │ │ CONVERTIBLE: different scale, formula exists → +10% SE/conv│ │ EXCLUDED: incompatible scale → record excluded │ │ Key conversions: │ │ OR→SMD: d = ln(OR)·√3/π (Chinn, 2000) │ │ HR→OR, r→d: d = 2r/√(1−r²) │ │ Unstd β→SMD: when SD_x, SD_y available │ │ Each conversion adds SE via delta method │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L5 — Evidence Quality (per-record) │ │ Mechanism: GRADE-inspired SE inflation │ │ Range: 1.0× – 2.0× │ │ Status: AUTHOR-CONSTRUCTED operationalization │ │ (GRADE framework rejects quantification; │ │ these multipliers are novel to this framework) │ │ Grades: │ │ GRADE High: 1.0× GRADE Moderate: 1.15× │ │ GRADE Low: 1.3× GRADE Very Low: 2.0× │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L6 — Temporal Mismatch (per-record) │ │ Mechanism: Kernel-adjusted SE correction │ │ Range: 1.0× – 1.6× │ │ When study assessed at timepoint t_study but model targets │ │ timepoint t_model, SE inflated proportional to temporal │ │ distance adjusted by the relevant intervention kernel │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ LAYER L7 — Evidence Freshness (per-record) │ │ Mechanism: 1.5%/year decay from publication year │ │ Floor: 0.70 (oldest studies retain ≥70% weight) │ │ Formula: w_fresh = max(0.70, 1 − 0.015 × (2025 − pub_year))│ │ Calibration: Poynard et al. (2002) — 45-year half-life of │ │ medical truth → ln(2)/45 ≈ 1.54%/yr │ └─────────────────────────────────────────────────────────────┘
Structural variance (additive, per-edge): σ²_structural composed of up to 9 components: unmeasured confounding, measurement error, selection bias, model misspecification, treatment heterogeneity, temporal instability, construct validity, population bias, publication bias. Author-elicited; informed by QBA literature (Greenland 2005; VanderWeele & Arah 2011; Lash, Fox & Fink 2009). Does NOT decrease with more studies of the same quality. In v2.0, σ²_structural is ANNOTATION-INFORMED per-edge: EX-P4-MA reads limitation_unmeasured_confounder annotations from study_annotations_v1 and adjusts upward from the 0.25 base (ceiling 0.50). ALG-B2 reads edges_v1.sigma_sq_structural (default 0.25 if NULL).
Claim-level attenuation (before SE inflation):
Identification Status
Attenuation Factor
Beta Prior
Identified (RCT)
1.00
—
Partially identified
0.85
Beta(17,3)
Plausible
0.70
Beta(14,6)
Unidentified
0.50
Beta(10,10)

B3 — Prior Selection Framework
Field
Value
ID
ALG-B3
Type
COMPOSITE (5 prior types)
Purpose
Select and parameterize the Bayesian prior for each edge via deterministic decision tree

Decision tree:
PriorType(e) = {
  RobustMAP           if k ≥ 5, best_design ≥ prospective
  Commensurate        if k ∈ [2,4]
  PowerPrior          if k = 1
  MechanisticSynth    if k = 0, has_chain
  StructuralPlaceholder  if k = 0, no_chain
}

Sub-steps (one per prior type):
┌─────────────────────────────────────────────────────────────┐ │ B3a — Robust MAP (Schmidli et al., 2014) │ │ Condition: k ≥ 5, best_design ≥ prospective │ │ Formula: p(β) = w·MAP(β|hist) + (1−w)·N(0, 10²) │ │ w = min(0.8, 0.5 + 0.06k) │ │ The vague component N(0,10²) ensures automatic downweighting│ │ under prior-data conflict │ │ Output: {type=RobustMAP, w, MAP_mean, MAP_var, vague_var} │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B3b — Commensurate (Hobbs et al., 2011) │ │ Condition: k ∈ [2,4] │ │ Formula: β ~ N(β_hist, σ²_hist / τ) │ │ τ = Π_d w_d^{p_d} (5 dimension match scores, │ │ same as L2 transportability) │ │ Output: {type=Commensurate, β_hist, σ²_hist, τ, dims} │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B3c — Power Prior (Ibrahim & Chen, 2000) │ │ Condition: k = 1 │ │ Formula: p(β|D₀) ∝ L(β|D₀)^{a₀} × π₀(β) │ │ Discount a₀ (AUTHOR-CONSTRUCTED): │ │ 0.80 RCT-same │ 0.50 RCT-diff │ 0.40 cohort │ │ 0.30 observ. │ 0.15 animal │ 0.05 mechanistic │ │ Calibration: Hackam & Redelmeier 2006 (~37% overall); │ │ Kola & Landis 2004 (CNS ~8%) │ │ Output: {type=PowerPrior, a₀, D₀, π₀} │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B3d — Mechanistic Synthesis (k=0 with chain) │ │ Condition: k = 0, intermediate edges all measured │ │ Formula: β_implied = Π_i β_i │ │ SE_implied = |β_impl| × √(Σ(SE_i/β_i)²) [delta] │ │ Enters as Power Prior with a₀ = 0.05 (95% discount) │ │ Output: {type=MechanisticSynth, β_impl, SE_impl, chain_edges}│ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B3e — Structural Placeholder (k=0, no chain) │ │ Condition: k = 0, no intermediate chain available │ │ Formula: β ~ N(0, σ²_placeholder) │ │ σ²_placeholder set wide (e.g., 10²) to express ignorance │ │ These edges contribute near-zero information │ │ Output: {type=StructuralPlaceholder, σ²} │ └─────────────────────────────────────────────────────────────┘
B4 — Structural Inclusion Probability
Field
Value
ID
ALG-B4
Type
ATOMIC
Purpose
Compute calibrated probability each edge represents a real biological mechanism

Formula: P_inclusion(e) = 1 / (1 + exp(−(−0.5 + 1.2·ln(k+1) + 0.4·Z + 0.6·𝟙[RCT])))
Calibration targets (AUTHOR-CONSTRUCTED): (i) k=0, Z=0, no RCT → P ≈ 0.38 (ii) k=3, moderate Z → P ≈ 0.80 (iii) RCT bonus → ~15 pp (iv) k≥5, Z>3, RCT → P ≈ 0.99
Sensitivity analysis (for P < 0.85):
Force ON (P=1.0): re-run MC, check top rank
Force OFF (P=0): re-run MC, check top rank
If top rank changes: flag decision-critical structural uncertainty
B5 — Heterogeneity Priors
Field
Value
ID
ALG-B5
Type
ATOMIC
Purpose
Assign empirical τ² prior distributions from Turner et al. (2012)

Priors (from 14,886 meta-analyses):
Subjective outcomes (self-reported cognition): τ² ~ LogNormal(−2.13, 1.58²), median 0.12 [NOTE: σ CORRECTED from 1.18 to 1.58 per audit]
Semi-objective outcomes (neuropsychological tests): τ² ~ LogNormal(−2.56, 1.07²), median 0.08
Biomarker outcomes: τ² ~ LogNormal(−2.56, 1.07²), median 0.08 (same as semi-objective)
B6 — Chain-versus-Direct Validation
Field
Value
ID
ALG-B6
Type
ATOMIC
Purpose
For edges with both pathway-mediated (chain) and direct (RCT) evidence, test internal consistency

Test statistic: Z = |β_chain − β_direct| / √(σ²_chain + σ²_direct)
Chain variance (delta method): SE_chain = |β_chain| × √(Σ_i (SE_{e_i}/β_{e_i})²)
Triage (4-tier):
Z
Action
SE multiplier
< 1.5
Pass
1.0×
1.5–2.0
Mild discrepancy
1.2×
2.0–3.0
Moderate; audit trigger
1.5×
≥ 3.0
Substantial; exclude or 2.0×
2.0×

Alignment Validity: AV(e) = 1 − min(Z/3.0, 1.0)
Directionality-aware hypothesis generation:
β_chain > β_direct → inflated mediation / double-counting
β_chain < β_direct → missing parallel pathways (discovery signal)
B7 — Context-Matched Prior Assembly
Field
Value
ID
ALG-B7
Type
COMPOSITE
Purpose
Compile all B1-B6 outputs into the FrozenModelState with 33 context-matched precision matrices

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ B7a — Populate B̂ matrix │ │ Fill B̂[source, target] = μ_e for each parameterized edge │ │ Non-linear edges: store Hill params alongside B̂ entry │ │ Edges with aggregation_method = BLOCKED: set to 0 │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B7b — Context-matched prior compilation │ │ 33 cancer-type × treatment-phase specifications │ │ 4-level fallback: │ │ exact match → cancer-type → general cancer → N(0,1) │ │ For each context: Λ_prior = (I − B̂)ᵀ D⁻¹ (I − B̂) │ │ with context-specific μ_prior per node │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B7c — Package synergy records │ │ Load synergy_registry (15 pairwise records) │ │ Pass through to FrozenModelState for ALG-D consumption │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ B7d — Assemble FrozenModelState │ │ Combine: B̂ + Σ_eff + Λ_prior(×33) + P_inclusion + │ │ prior_audit + AV_scores + τ² + synergy │ │ This object crosses THE CUT BOUNDARY │ │ It is FROZEN: never modified by runtime patient data │ └─────────────────────────────────────────────────────────────┘
───────────────────────────────────────────────────────────────────────────
6. BOUNDARY TABLES
Direction
Table
Columns Used
Purpose
READS
evidence_registry.csv (446+)
edge_id, β, SE, design, year, scope, quality...
Raw evidence
READS
synergy_registry.csv (15)
pair, JPO, CCS, source_trial
Interaction records
READS
claim_attenuation_policy (4)
identification_status → factor, Beta_params
β attenuation
READS
evidence_freshness_policy
pub_year → w_fresh
L7 decay weights
READS
context_matched_priors (33)
cancer_type, phase → per-node μ, σ
Prior loading
WRITES
prior_audit_trail
edge_id, prior_type, params, rationale
Documentation
WRITES
chain_direct_validation
edge_id, Z, AV, triage_action
Validation log

───────────────────────────────────────────────────────────────────────────
7. GATES & CHECKPOINTS
Gate ID
Position
Condition
Pass
Fail
B-G1
After B1
All edges have aggregation method assigned; no NaN in μ_e for non-BLOCKED edges
→ B2
Review evidence records
B-G2
After B2
SE_eff > 0 for all edges; no infinite values; L1-L7 contributions logged
→ B3
Debug layer computation
B-G3
After B3
Every edge has a prior type assigned; audit trail complete
→ B4
Review prior selection tree
B-G4
After B4
P_inclusion ∈ [0,1] for all edges; sensitivity analysis run for P < 0.85
→ B5
Calibration error
B-G5
After B6
AV scores computed for all chain+direct edges; triage actions applied
→ B7
Chain-direct mismatch
B-G6
After B7
FrozenModelState complete; all 33 Λ_prior positive-definite; SHA-256 hash
→ ALG-C
Assembly failure

───────────────────────────────────────────────────────────────────────────
8. CHAIN-LEVEL ASSUMPTIONS
#
Assumption
Impact if Violated
Binding #
1
IVW weighting is appropriate (assumes common effect or random effects)
If effect heterogeneity is systematic (not random), IVW gives wrong pooled estimate
—
2
7 layers are orthogonal (multiplicative compounding valid)
If layers correlate, SE_eff is over- or under-estimated
—
3
Structural variance components are correctly elicited
Wrong σ²_structural → wrong SE_eff → wrong uncertainty bands
— (author-constructed)
4
Attenuation factors correctly discount confounded estimates
Too aggressive → real effects suppressed; too lenient → bias persists
— (author-constructed)
5
Logistic P_inclusion correctly calibrated
Wrong inclusion probs → over/under-counting edge existence
— (novel, needs validation)
6
Turner et al. (2012) priors appropriate for CRCI literature
If CRCI heterogeneity differs from general medical, τ² priors are miscalibrated
—
7
Context-matched priors from 33 specifications cover clinical practice
Missing contexts fall back to general cancer, which may be too vague
—
8
Claim-level attenuation factors (0.85/0.70/0.50) are reasonable
These are author-constructed; sensitivity analysis shows stable rankings for >85% of patients
Assumption 1 (effect homogeneity)

═══════════════════════════════════════════════════════════════════════════



## CHAIN CARD: ALG-C

═══════════════════════════════════════════════════════════════════════════ CHAIN CARD: ALG-C (Patient State Inference) ═══════════════════════════════════════════════════════════════════════════ Version: 1.1-CORRECTED Parent System: SYS_ALGORITHM
1. IDENTITY
Field
Value
Chain ID
ALG-C
System
SYS_ALGORITHM
Name
Patient State Inference
Purpose
Fuse partial clinical observations with the graph-informed prior to produce a posterior estimate of the patient's full 63-node latent state with calibrated uncertainty, applying effect modifiers and identifying dysregulated pathways
Phase
PHASE_C — Runtime, per-patient

This is the most clinically critical chain. It is the first runtime chain to touch patient data and produces the posterior state vector that all downstream chains (D, E, F) consume.
The Cut Boundary: This chain operates BELOW the cut. It receives frozen edge parameters β̂ from Chain B but NEVER modifies them. Patient observations update θ (node states) only.
───────────────────────────────────────────────────────────────────────────
2. CHAIN DIAGRAM
FROM CHAIN ALG-B                         FROM SYS_RUNTIME (clinical interface)
══════════════                           ══════════════════════════════════════

 FrozenModelState ──┐   Patient observations ──┐
 {Λ_prior, B̂,      │   {y_k: instrument k     │
  context_priors,   │    measured at time t}    │
  proxy_table}      │                          │
                    ▼                          │
           ┌───────────────┐                   │
           │  C1            │                  │
           │  Context       │                  │
           │  Matching &    │                  │
           │  Prior Loading │                  │
           └───────┬───────┘                   │
                   │                           │
            LoadedPrior                        │
            {Λ_prior, η_prior,                 │
             context_level,                    │
             fallback_used}                    │
                   │                           │
                   ▼                           │
           ┌───────────────┐◀──────────────────┘
           │  C2            │
           │  Measurement   │
           │  Model         │
           │  Application   │
           └───────┬───────┘
                   │
            PreparedObservations[]
            {y_k, node_i, b_k, a_k,
             σ²_{y,k}, w_temporal,
             cancer_SE_mult}
                   │
                   ▼
           ┌───────────────┐
           │  C3            │
           │  Bayesian      │
           │  State         │
           │  Estimation    │
           └───────┬───────┘
                   │
            RawPosterior
            {θ̂, Σ_post, Λ_post,
             observation_log,
             variance_reduction}
                   │
                   ▼
           ┌───────────────┐
           │  C4            │
           │  Effect        │
           │  Modifier      │
           │  Application   │
           └───────┬───────┘
                   │
                   ▼
            PatientState
            (complete output)
                   │
            TO CHAINS ALG-D, ALG-E, ALG-F

───────────────────────────────────────────────────────────────────────────
3. INTERMEDIATE STATE SCHEMAS
State: LoadedPrior (after C1)
Field
Type
Description
Produced By
Consumed By
Λ_prior
ℝ^{63×63}
Context-matched precision matrix
C1
C3
η_prior
ℝ^{63}
Information vector: Λ_prior × μ_prior
C1
C3
μ_prior
ℝ^{63}
Context-matched prior mean
C1
C4, F1
context_key
str
Which of 33 cancer-type × phase specs matched
C1
F1 (audit)
fallback_level
enum{EXACT, CANCER_TYPE, GENERAL_CANCER, UNINFORMATIVE}
How specific the match was
C1
C4, F1
fallback_SE_inflation
float [1.0, 2.0]
SE multiplier for fallback imprecision
C1
C3

State: PreparedObservation (after C2, one per instrument)
Field
Type
Description
Produced By
Consumed By
instrument_id
str
Instrument identifier
C2
C3
node_i
int [0, 62]
Target latent node index
C2
C3
y_k
float
Observed measurement value
C2
C3
a_k
float
Instrument intercept (offset)
C2
C3
b_k
float
Instrument loading (slope)
C2
C3
σ²_y_k
float
Total observation noise variance (after all adjustments)
C2
C3
cancer_SE_mult
float [1.0, 1.5]
Cancer validation SE multiplier applied
C2
audit
w_temporal
float (0, 1]
Temporal decay weight: e^{−0.05t}
C2
audit
t_days
float
Days since assessment
C2
audit
tier
enum{TIER_0, TIER_1, TIER_2}
Observation priority tier
C2
C3 (ordering)

State: RawPosterior (after C3)
Field
Type
Description
Produced By
Consumed By
θ̂
ℝ^{63}
Posterior mean (pre-modifier)
C3
C4
Σ_post
ℝ^{63×63}
Posterior covariance
C3
C4, D, E, F
Λ_post
ℝ^{63×63}
Posterior precision
C3
C4
observation_log
list[ObservationRecord]
Which instruments contributed, weights
C3
F1
fusion_levels
dict[node_id → {L1, L2, L3}]
Which fusion level applied per node
C3
audit
variance_reduction
ℝ^{63}
Per-variable expected ΔVar from next obs
C3
F3

State: PatientState (final output)
Field
Type
Description
Produced By
Consumed By
θ̂
ℝ^{63}
Posterior mean (post-modifier)
C4
D, E, F
Σ_post
ℝ^{63×63}
Posterior covariance (from C3, unmodified)
C3
D, E, F
Λ_post
ℝ^{63×63}
Posterior precision
C3
D
active_pathways
list[PathwayActivation]
Dysregulated pathways with magnitudes
C4
D, F
modifier_audit
list[ModifierRecord]
Per-edge modifiers + grades + clip events
C4
F
observation_log
list[ObservationRecord]
Complete observation provenance
C3
F
context_match
ContextMatchRecord
Prior loading audit
C1
F
variance_reduction
ℝ^{63}
Per-variable expected variance reduction
C3
F
B_eff
ℝ^{63×63}
Modified edge weight matrix (β_eff per edge)
C4
D

───────────────────────────────────────────────────────────────────────────
4. SUBSYSTEM INVENTORY
Order
Subsystem ID
Name
Input State
Output State
Type
1
ALG-C1
Context Matching & Prior Loading
FrozenModelState + patient demographics
LoadedPrior
COMPOSITE
2
ALG-C2
Measurement Model Application
instrument_registry + patient observations
PreparedObservation[]
COMPOSITE
3
ALG-C3
Bayesian State Estimation
LoadedPrior + PreparedObservation[]
RawPosterior
COMPOSITE
4
ALG-C4
Effect Modifier Application
RawPosterior + modifier_registry + B̂
PatientState
COMPOSITE

───────────────────────────────────────────────────────────────────────────
5. SUBSYSTEM DETAIL
C1 — Context Matching & Prior Loading
Field
Value
ID
ALG-C1
Type
COMPOSITE
Purpose
Match patient to one of 33 cancer-type × treatment-phase prior specifications and load the appropriate precision matrix
Research Phase
RESEARCH_PARAMETERS

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C1a — Context Key Construction │ │ Purpose: Build lookup key from patient demographics │ │ Input: cancer_type (required), treatment_phase (required), │ │ treatment_regimen (optional) │ │ Output: context_key: str │ │ Logic: Concatenate cancer_type + treatment_phase │ │ + regimen_class (if available) │ │ Rules: Unknown cancer_type → fallback triggered │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C1b — 4-Level Fallback Resolution │ │ Purpose: Find best available prior, degrading gracefully │ │ Input: context_key + context_matched_priors (33 rows) │ │ Output: matched_prior + fallback_level │ │ Logic: Level 1 — Exact: cancer × phase × regimen (1.0×) │ │ Level 2 — Cancer-type only (SE 1.2×) │ │ Level 3 — General cancer (SE 1.5×) │ │ Level 4 — Uninformative: μ=0, Σ=I (SE 2.0×) │ │ Rules: Always use most specific; log fallback_level │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C1c — Information Form Initialization │ │ Purpose: Convert to information form for efficient updating │ │ Input: matched_prior: {μ_prior, Λ_prior} │ │ Output: η_prior = Λ_prior × μ_prior │ │ Logic: Apply fallback SE inflation: │ │ Λ_prior_adj = Λ_prior / (SE_inflation²) │ │ η_prior_adj = Λ_prior_adj × μ_prior │ │ Rules: Verify Λ_prior_adj remains positive-definite │ └─────────────────────────────────────────────────────────────┘
C2 — Measurement Model Application
Field
Value
ID
ALG-C2
Type
COMPOSITE
Purpose
Transform raw patient observations into PreparedObservations with noise models, temporal weighting, and cancer-specific SE adjustments
Research Phase
RESEARCH_PARAMETERS

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C2a — Observation Tiering & Completeness Check │ │ Purpose: Classify by priority tier; verify minimum data │ │ Input: Raw patient observations (variable set) │ │ Output: Tiered observation list + completeness flags │ │ Logic: Tier 0 (REQUIRED — abort if missing): │ │ cancer_type, treatment_regimen, treatment_phase, │ │ ≥1 cognitive measure │ │ Tier 1 (MAJOR GAIN): │ │ PSQI, PHQ-9, FACIT-F, age, IL-6/CRP, activity │ │ Tier 2 (PATHWAY): │ │ BDNF, cortisol, GAD-7, glucose, APOE, ISI, NfL, │ │ p16^INK4a, Shannon diversity │ │ Rules: Tier 0 incomplete → ABORT │ │ Missing Tier 1 → variance_penalty logged │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C2b — Instrument Lookup & Noise Model │ │ Purpose: Compute observation noise from psychometric params │ │ Input: Observation y_k + instrument_registry (23 rows) │ │ Output: {a_k, b_k, σ²_{y,k_base}} │ │ Logic: Classical test theory: │ │ σ²_{y,k_base} = b²_k × (1 − α_k) / α_k │ │ α=0.90 → noise = 0.111 b² │ │ α=0.70 → noise = 0.429 b² │ │ α=0.50 → noise = 1.000 b² │ │ Rules: α_k < 0.50 → WARNING; missing α → default 0.70 │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C2c — Cancer Validation SE Multiplier │ │ Purpose: Inflate noise for instruments not cancer-validated │ │ Input: instrument_id + cancer validation status │ │ Output: cancer_SE_mult per observation │ │ Logic: validated_in_cancer: 1.0× │ │ used_in_cancer: 1.1× │ │ general_population_only: 1.3× │ │ somatic_confound_risk: 1.5× │ │ σ²_{y,k} = σ²_{y,k_base} × cancer_SE_mult² │ │ Rules: somatic_confound: e.g., PHQ-9 somatic items │ │ overlap with chemo side effects │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C2d — Temporal Weighting │ │ Purpose: Downweight stale observations │ │ Input: Assessment date + current date per observation │ │ Output: w_temporal; adjusted σ² │ │ Logic: w(t) = e^{−0.05t} (t = days since assessment) │ │ Same day: 1.000; 1wk: 0.705; 2wk: 0.497; │ │ 1mo: 0.223; 3mo: 0.011 │ │ σ²_{y,k_final} = σ²_{y,k} / w(t) │ │ Rules: t > 90 days → EXCLUDED (too stale) │ │ t > 30 days → WARNING │ │ Decay 0.05/day AUTHOR-CONSTRUCTED (~2wk half-life) │ └─────────────────────────────────────────────────────────────┘
C3 — Bayesian State Estimation
Field
Value
ID
ALG-C3
Type
COMPOSITE
Purpose
Perform information-form Bayesian updating to produce full 63-node posterior
Research Phase
RESEARCH_NONE (canonical Bayesian computation)

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C3a — Information-Form Rank-1 Updates │ │ Purpose: Sequentially incorporate each observation │ │ Input: {Λ_prior, η_prior} + PreparedObservation[] │ │ Output: {Λ_post, η_post} │ │ Logic: Initialize: Λ_post = Λ_prior; η_post = η_prior │ │ Per observation y_k at instrument k → node i: │ │ Λ_post ← Λ_post + (b²_k/σ²_{y,k}) · eᵢeᵢᵀ │ │ η_post ← η_post + (b_k(y_k−a_k)/σ²_{y,k}) · eᵢ │ │ Properties: │ │ - Updates are COMMUTATIVE (order doesn't matter) │ │ - Multiple instruments on same node: precisions sum (L3) │ │ - Each update costs O(1) on the sparse precision matrix │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C3b — Posterior Recovery │ │ Purpose: Convert information form to moment form │ │ Input: {Λ_post, η_post} │ │ Output: {θ̂ = Λ_post⁻¹ · η_post, Σ_post = Λ_post⁻¹} │ │ Logic: Cholesky: Λ_post = LLᵀ │ │ Forward+backward substitution for μ_post │ │ Diagonal of Σ_post via selective inversion │ │ Rules: Cholesky failure → ABORT (should never happen) │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C3c — Three-Level Fusion Accounting │ │ Purpose: Record which fusion level applied per node │ │ Input: Observation log + update records │ │ Output: Per-node: L1 (build-time IVW via prior), L2 │ │ (per-obs rank-1), L3 (multi-instrument same-node) │ │ Logic: L1: all nodes (via Λ_prior from Chain B) │ │ L2: nodes with direct observations │ │ L3: nodes with ≥2 instruments │ │ Rules: Record for variance decomposition in Chain F │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C3d — Variance Reduction Computation │ │ Purpose: Compute expected ΔVar from each potential next obs │ │ Input: Σ_post │ │ Output: Per-unobserved-variable: ΔVar(Y|X) = Cov²/Var │ │ Logic: Gaussian conditioning: ΔVar(Y|X) = Cov(Y,X)²/Var(X)│ │ Compute for top 10 unobserved by marginal variance │ │ Rules: Report top 2 "most informative next observations" │ └─────────────────────────────────────────────────────────────┘
C4 — Effect Modifier Application
Field
Value
ID
ALG-C4
Type
COMPOSITE
Purpose
Apply 109 modifier rules to adjust edge weights, then identify dysregulated pathways
Research Phase
RESEARCH_PARAMETERS + RESEARCH_CALIBRATION

Sub-steps:
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C4a — Modifier Rule Matching │ │ Purpose: Identify which of 109 rules apply to this patient │ │ Input: Patient profile + modifier_registry (109 rows) │ │ Output: Per-edge list of applicable modifiers │ │ Logic: For each rule: check condition (age>65, APOE4+, │ │ education<12yr, BMI>30, diabetes, etc.) │ │ If met → add to edge's modifier stack │ │ Rules: Evaluate in dependency order for conditional mods │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C4b — Modifier Stacking with Guardrails │ │ Purpose: Multiply modifiers per edge with safety bounds │ │ Input: Per-edge modifier lists + B̂ │ │ Output: B_eff: β_eff = β_base × Π_k m_k │ │ Logic: Individual: m_k ∈ [0.7, 1.5] │ │ Cumulative: Π_k m_k ∈ [0.5, 2.0] │ │ Sign-flip prohibition: direction preserved │ │ Cognitive reserve: m_CR ∈ [0.7, 1.3] │ │ >16yr ed → 0.7; <12yr ed → 1.3 (Stern 2009) │ │ Rules: Log clipping events; grade = min_k(grade_{m_k}) │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C4c — Modifier SE Inflation │ │ Purpose: Inflate edge SE per cumulative evidence grade │ │ Input: Cumulative grade per edge from C4b │ │ Output: SE_modifier_adj per edge │ │ Logic: Grade A: 1.00× | B: 1.15× | C: 1.30× | D: 1.50× │ │ Rules: Applied in Chain D's MC sampling (B̂ stays frozen) │ └─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐ │ SUB-STEP: C4d — Pathway Activation Detection │ │ Purpose: Identify which of 20 pathways are dysregulated │ │ Input: θ̂ + pathway_map (20 pathways) │ │ Output: active_pathways with magnitudes │ │ Logic: A(P) = mean(|θ̂[nodes_in_P]|) │ │ Default threshold: τ_P = 0.5 SD │ │ Sensitive mode: τ_P = 0.3 SD │ │ Rules: Active pathways drive intervention targeting in D │ │ High activation + high uncertainty → flag │ │ No active pathways → population defaults │ └─────────────────────────────────────────────────────────────┘
───────────────────────────────────────────────────────────────────────────
6. BOUNDARY TABLES
Direction
Table
Columns Used
Purpose
READS
FrozenModelState (Chain B)
Λ_prior, B̂, proxy_table
Prior + frozen edges
READS
context_matched_priors (33)
cancer_type, phase → μ, σ per node
Prior loading
READS
instrument_registry.csv (23)
instrument_id, target_node, a_k, b_k, α_k
Measurement model
READS
modifier_registry.csv (109)
condition, target_edge, multiplier, grade
Effect modifiers
READS
node_registry.csv (63)
orientation, domain
Sign convention
WRITES
(none — all output is in-memory PatientState)





───────────────────────────────────────────────────────────────────────────
7. GATES & CHECKPOINTS
Gate ID
Position
Condition
Pass
Fail
C-G1
After C1
Context matched; Λ_prior PD; fallback logged
→ C2
ABORT: prior invalid
C-G2
After C2
All Tier 0 present; σ² > 0; no NaN
→ C3
ABORT: insufficient data
C-G3
After C3
θ̂ finite; Σ_post PD; variance reduced for observed nodes
→ C4
ABORT: numerical failure
C-G4
After C4
Modifiers in guardrails; no sign flips; ≥1 pathway evaluated
→ ALG-D
WARNING if 0 active pathways

───────────────────────────────────────────────────────────────────────────
8. CHAIN-LEVEL ASSUMPTIONS
#
Assumption
Impact if Violated
Binding #
1
Gaussian measurement model
Non-Gaussian instruments misspecified
Assumption 6
2
Classical test theory σ² = b²(1−α)/α
α varies by population → noise model wrong
—
3
Temporal decay e^{−0.05t} appropriate
Stale data over/under-weighted
— (author)
4
33 context-matched priors cover practice
Missing contexts → wider uncertainty
—
5
Modifiers multiplicative and independent
Interactions (age × APOE) → product form wrong
Assumption 7
6
Pathway threshold τ=0.5 SD appropriate
Too high → misses dysregulation; too low → false positives
— (author)
7
109 rules capture relevant modification
Missing rules → less personalized
—

═══════════════════════════════════════════════════════════════════════════


## CHAIN CARD: ALG-D

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: ALG-D  (Intervention Simulation)
═══════════════════════════════════════════════════════════════════════════
Version: 1.1-CORRECTED
Parent System: SYS_ALGORITHM

# 1. IDENTITY

| Field | Value |
|-------|-------|
| Chain ID | `ALG-D` |
| System | `SYS_ALGORITHM` |
| Name | Intervention Simulation |
| Purpose | Simulate expected cognitive effects of each candidate intervention and optimal bundles via Monte Carlo, incorporating structural uncertainty, synergy, dose optimization, and adherence — producing ranked personalized recommendations |
| Phase | `PHASE_D` — Runtime, per-patient |

**This chain is the computational core of the recommendation engine.** It consumes the patient's posterior state (Chain C) and the frozen model (Chain B), and runs 10,000 Monte Carlo draws to propagate all forms of uncertainty into the final intervention rankings.

───────────────────────────────────────────────────────────────────────────

# 2. CHAIN DIAGRAM

```
FROM CHAIN ALG-B              FROM CHAIN ALG-C
══════════════                ════════════════

 FrozenModelState ──┐    PatientState ──┐
 {B̂, Σ_eff,        │    {θ̂, Σ_post,   │
  P_inclusion,      │     active_paths,  │
  synergy_reg}      │     B_eff}        │
                    ▼                   │
           ┌───────────────┐            │
           │  D1            │◀──────────┘
           │  Monte Carlo   │
           │  Sampling      │
           │  (N=10,000)    │
           └───────┬───────┘
                   │
            MCDraws[10000]
            {β^(m), Include^(m),
             θ₀^(m)}
                   │
                   ▼
           ┌───────────────┐
           │  D2            │
           │  Effect        │
           │  Propagation   │
           │  (per-draw,    │
           │   per-interv.) │
           └───────┬───────┘
                   │
            PerDrawEffects[10000 × n_interventions]
            {Δθ^(m), ΔC^(m)}
                   │
                   ▼
           ┌───────────────┐
           │  D3            │
           │  Synergy &     │
           │  Bundle        │
           │  Computation   │
           └───────┬───────┘
                   │
            BundleEffects[]
            {ΔC_bundle, synergy_breakdown}
                   │
                   ▼
           ┌───────────────┐
           │  D4            │
           │  SAFE Score    │
           │  Ranking       │
           └───────┬───────┘
                   │
            Rankings_A, Rankings_B
            {SAFE, CrI, P_rank1}
                   │
                   ▼
           ┌───────────────┐
           │  D5            │
           │  Pathway-Dose  │
           │  Optimization  │
           └───────┬───────┘
                   │
            DoseRecommendations[]
            {d*, conflict_flag}
                   │
                   ▼
           ┌───────────────┐
           │  D6            │
           │  Causal        │
           │  Language       │
           │  Assignment    │
           └───────┬───────┘
                   │
                   ▼
            SimulationResults
            (complete output)
                   │
            TO CHAINS ALG-E, ALG-F
```

───────────────────────────────────────────────────────────────────────────

# 3. INTERMEDIATE STATE SCHEMAS

### State: MCDraw (after D1, 10,000 instances)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| draw_id | int [0, 9999] | Draw index | D1 | D2, D3, D4 |
| β_draw | ℝ^{63×63} sparse | Sampled edge weights | D1a | D2 |
| include_draw | bool^{118} | Structural inclusion mask | D1b | D2 |
| θ₀_draw | ℝ^{63} | Sampled patient baseline | D1c | D2 |
| B_draw | ℝ^{63×63} | β_draw × include_draw (effective B for this draw) | D1 | D2 |

### State: PerDrawEffect (after D2, per-draw per-intervention)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| draw_id | int | Which MC draw | D2 | D3, D4 |
| intervention_id | str | Which intervention | D2 | D3, D4 |
| Δθ_draw | ℝ^{63} | Full-graph effect vector | D2a/b/c | D3 |
| ΔC_draw | float | Composite cognitive effect | D2e | D3, D4 |
| propagation_method | enum{DIRECT_RCT, MATRIX, PATH_ENUM} | Which method used | D2 | audit |
| ceiling_clipped | bool | Whether physiological ceiling was applied | D2d | audit |

### State: BundleEffect (after D3, per candidate bundle)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| bundle_id | str | Identifier (sorted intervention combo) | D3 | D4 |
| ΔC_bundle | ℝ^{10000} | Bundle cognitive effect across draws | D3c | D4 |
| synergy_breakdown | dict[pair → {JPO, CCS, γ}] | Pairwise synergy terms | D3b | F |
| member_interventions | list[str] | Bundle members | D3 | D4 |

### State: SimulationResults (final output)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| ranked_interventions_A | list[RankedIntervention] | By SAFE_A (efficacy) | D4 | E, F |
| ranked_interventions_B | list[RankedIntervention] | By SAFE_B (feasibility) | D4 | E, F |
| bundle_recommendations | list[BundleRec] | Top bundles + synergy | D3+D4 | E, F |
| dose_recommendations | dict[intervention → DoseRec] | Per-intervention d* | D5 | F |
| causal_claims | dict[intervention → ClaimLevel] | Causal language | D6 | F |
| sensitivity_indices | dict[edge → {elasticity, discovery_score}] | Research priority | D4 | F |
| common_random_numbers | seed | For reproducible comparison | D1 | audit |

───────────────────────────────────────────────────────────────────────────

# 4. SUBSYSTEM INVENTORY

| Order | Subsystem ID | Name | Input State | Output State | Type |
|-------|-------------|------|-------------|-------------|------|
| 1 | ALG-D1 | Monte Carlo Sampling | FrozenModelState + PatientState | MCDraw[10000] | COMPOSITE |
| 2 | ALG-D2 | Effect Propagation | MCDraw[] + intervention defs | PerDrawEffect[][] | COMPOSITE |
| 3 | ALG-D3 | Synergy & Bundle Computation | PerDrawEffect[][] + synergy_reg | BundleEffect[] | COMPOSITE |
| 4 | ALG-D4 | SAFE Score Ranking | PerDrawEffect[][] + BundleEffect[] | Rankings | COMPOSITE |
| 5 | ALG-D5 | Pathway-Specific Dose Optimization | PatientState + dose_response_registry | DoseRecommendations | COMPOSITE |
| 6 | ALG-D6 | Causal Language Assignment | All D1-D5 outputs + edge metadata | CausalClaims | ATOMIC |

───────────────────────────────────────────────────────────────────────────

# 5. SUBSYSTEM DETAIL

## D1 — Monte Carlo Sampling

| Field | Value |
|-------|-------|
| ID | `ALG-D1` |
| Type | COMPOSITE |
| Purpose | Generate 10,000 joint samples of {edge weights, structural inclusion, patient baseline} using common random numbers |
| Research Phase | `RESEARCH_NONE` (sampling infrastructure) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D1a — Edge Weight Sampling (per-draw, per-edge)   │
│ Purpose:  Sample edge weights from posterior distributions    │
│ Input:    B̂ (μ_e per edge), Σ_eff (SE per edge), B_eff      │
│ Output:   β_e^(m) per edge per draw                          │
│ Logic:    β_e^(m) ~ N(μ_e, σ²_{eff,e})                      │
│           For edges with modifier SE inflation from C4c:      │
│             σ²_{sampling} = σ²_{eff,e} × SE_modifier_adj²   │
│           Sign preservation (where biological constraint):    │
│             Use truncated normal (reject draws that flip sign)│
│           Non-linear (Hill/Emax) edges:                       │
│             Sample E_max, EC₅₀ from their posteriors         │
│             h (Hill coefficient) fixed (insufficient data     │
│             for posterior estimation)                         │
│ Rules:    Common random numbers: fix seed at draw level       │
│           → enables precise pairwise comparison               │
│           Same seed, different intervention → only the        │
│           intervention differs, not the model realization     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D1b — Structural Inclusion Sampling (per-draw)    │
│ Purpose:  Sample which edges exist in this model realization │
│ Input:    P_inclusion per edge (from Chain B4)                │
│ Output:   Include_e^(m) ∈ {0, 1} per edge per draw          │
│ Logic:    Include_e^(m) ~ Bernoulli(P_inclusion(e))          │
│           If excluded: β_e^(m) = 0 (edge absent)            │
│ Key effect: An edge with P_inclusion = 0.60 is absent in     │
│   ~4,000 of 10,000 draws → dramatic uncertainty inflation    │
│   for pathways that depend on uncertain edges                │
│ Rules:    Edges with P ≥ 0.99 treated as always-present      │
│           Edges with P ≤ 0.05 treated as always-absent       │
│           (optimization: reduces sampling overhead)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D1c — Patient Baseline Sampling (per-draw)        │
│ Purpose:  Sample patient's true state from posterior          │
│ Input:    θ̂, Σ_post from Chain C3                            │
│ Output:   θ₀^(m) per draw                                    │
│ Logic:    θ₀^(m) ~ N(θ̂, Σ_post)                             │
│           Cholesky of Σ_post: Σ = LLᵀ                       │
│           θ₀^(m) = θ̂ + L · z^(m), z ~ N(0, I)              │
│ Rules:    Pre-compute L once, reuse for all 10,000 draws     │
│           Clip θ₀^(m) to ±4 SD if extreme (numerical guard) │
└─────────────────────────────────────────────────────────────┘

## D2 — Effect Propagation

| Field | Value |
|-------|-------|
| ID | `ALG-D2` |
| Type | COMPOSITE |
| Purpose | For each draw × intervention, propagate the intervention effect through the causal graph to compute cognitive impact |
| Research Phase | `RESEARCH_NONE` (computation) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D2a — Direct RCT Edge (priority 1)               │
│ Purpose:  Use direct RCT evidence when available             │
│ Input:    Intervention definition + edge metadata             │
│ Output:   ΔC_direct if RCT edge exists for this intervention │
│ Logic:    If edge "intervention → cognition" has claim_level  │
│           = causal_supported AND has direct RCT evidence:     │
│             Use β_direct^(m) as the effect estimate           │
│             Skip matrix propagation (gold standard path)      │
│ Rules:    Only for interventions with direct cognitive RCTs   │
│           Still subject to structural inclusion sampling       │
│           (the RCT edge itself has P_inclusion ≈ 0.95+)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D2b — Matrix Method (priority 2, default)         │
│ Purpose:  Propagate effect through full causal graph via      │
│           matrix inversion                                    │
│ Input:    B_draw^(m) (this draw's edge matrix), x_interv      │
│ Output:   Δθ^(m) = (I − B^(m))⁻¹ · x_intervention           │
│ Logic:    x_intervention: ℝ^{63} vector, 1.0 at intervention │
│           node, 0 elsewhere (for unit-dose effect)            │
│           (I − B^(m))⁻¹ propagates through ALL paths          │
│           simultaneously via Neumann series                   │
│ Complexity: O(n³) = O(250,000) per draw                      │
│ Optimization: Pre-factor (I − B̂)⁻¹ at mean, use             │
│   Woodbury updates for per-draw perturbations                │
│ Rules:    Check κ(I − B^(m)); if > 10¹⁰ → fall back to D2c │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D2c — Path Enumeration (fallback)                 │
│ Purpose:  When matrix inversion is numerically unstable,      │
│           enumerate all directed paths explicitly              │
│ Input:    B_draw^(m) (sparse), source node, target node       │
│ Output:   Δθ_target = Σ_P [Π_{e∈P} β_e] · x_source          │
│ Logic:    Depth-first search from intervention node            │
│           For each path P reaching a cognitive target:         │
│             path_effect = Π_{e∈P} β_e^(m)                    │
│             (multiply edge weights along the path)            │
│           Sum over all paths: Δθ = Σ_P path_effect           │
│ Complexity: O(|paths|×|path_length|), worst case DFS on 118  │
│ Rules:    Max path depth = 7 (number of layers)              │
│           Paths through excluded edges (Include=0) → skip    │
│           Produces identical result to matrix method when      │
│           numerically stable (consistency check)              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D2d — Physiological Ceiling Application           │
│ Purpose:  Clip effects to biologically plausible bounds       │
│ Input:    Δθ^(m) per node                                     │
│ Output:   Δθ^(m)_clipped                                      │
│ Logic:    Single intervention: ±1.0 SD per node              │
│           Bundle (multi-intervention): ±1.5 SD per node      │
│           Calibration: largest documented CRCI effect is       │
│             combined exercise at 0.94 SD (Northey 2018)      │
│ Rules:    Log all clipping events                             │
│           Clipping frequency > 20% → WARNING (model may be   │
│           over-estimating effects or ceilings too tight)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D2e — Composite Scoring                           │
│ Purpose:  Combine multi-domain effects into single cognitive  │
│           composite score                                     │
│ Input:    Δθ^(m) across cognitive domain nodes                 │
│ Output:   ΔC^(m) = severity-weighted inverse-variance average │
│ Logic:    ΔC^(m) = Σ_d w_d · Δθ_d^(m) / Σ_d w_d             │
│           Severity weights:                                   │
│             |z_d| < 1.0 SD: w = 1.0 (mild)                  │
│             1.0 ≤ |z_d| < 2.0: w = 1.5 (moderate)           │
│             |z_d| ≥ 2.0: w = 2.0 (severe)                   │
│           Inverse-variance: w_d also × 1/σ²_d                │
│ Rules:    Severity from patient baseline θ₀^(m), not mean    │
│           → personalized: sicker patients weight more         │
└─────────────────────────────────────────────────────────────┘

## D3 — Synergy & Bundle Computation

| Field | Value |
|-------|-------|
| ID | `ALG-D3` |
| Type | COMPOSITE |
| Purpose | Compute pairwise synergy metrics, then bundle effects accounting for pathway overlap and complementarity |
| Research Phase | `RESEARCH_PARAMETERS` (synergy registry from trials) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D3a — Pairwise Pathway Overlap                    │
│ Purpose:  Compute Jaccard Pathway Overlap for each pair      │
│ Input:    Intervention → pathway mappings + active_pathways   │
│ Output:   JPO(a,b) per pair                                   │
│ Logic:    JPO(a,b) = |P_a ∩ P_b| / |P_a ∪ P_b|             │
│           P_a = set of pathways intervention a acts on        │
│           High JPO → redundant (diminishing returns)         │
│           Low JPO → complementary (additive benefits)        │
│ Rules:    JPO = 1.0 → identical mechanism → no bundle benefit │
│           JPO = 0.0 → completely complementary                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D3b — Complementary Convergence Score             │
│ Purpose:  Identify pairs that act on different pathways but   │
│           converge on the same cognitive domain               │
│ Input:    Pathway→domain mappings + ΔC per intervention       │
│ Output:   CCS(a,b) per pair                                   │
│ Logic:    CCS(a,b) = (1 − JPO(a,b)) × 𝟙[shared_convergence]│
│           shared_convergence: both interventions improve       │
│           the same cognitive domain via different pathways     │
│           High CCS → synergistic (different paths, same goal) │
│ Rules:    CCS ∈ [0, 1]; only positive when convergence exists │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D3c — Bundle Effect Computation (per-draw)        │
│ Purpose:  Compute combined effect of multi-intervention       │
│           bundles accounting for overlap and synergy           │
│ Input:    ΔC_a per intervention per draw, JPO, CCS, γ prior  │
│ Output:   ΔC_bundle^(m) per draw per candidate bundle         │
│ Logic:    ΔC_bundle = Σ_a ΔC_a · Π_{b≠a}(1 − JPO(a,b)·0.5) │
│                     + Σ_{(a,b)} γ · CCS(a,b) · √|ΔC_a·ΔC_b| │
│           Term 1: Discounted additive (overlap penalty)       │
│           Term 2: Synergy bonus (complementary convergence)   │
│           γ ~ Beta(2,4) × 0.40 (mode ≈ 0.25, sampled/draw)  │
│ Rules:    Bundle size ≤ 4 (clinical feasibility)             │
│           Search: exhaustive for ≤8 candidates;               │
│             Thompson sampling for larger candidate sets       │
│           γ prior AUTHOR-CONSTRUCTED; needs clinical calibr.  │
└─────────────────────────────────────────────────────────────┘

## D4 — SAFE Score Ranking

| Field | Value |
|-------|-------|
| ID | `ALG-D4` |
| Type | COMPOSITE |
| Purpose | Rank interventions and bundles using dual-mode SAFE scores with adherence weighting |
| Research Phase | `RESEARCH_CALIBRATION` (adherence model coefficients) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D4a — Mode A: Efficacy-Only Ranking               │
│ Purpose:  Rank by pure expected cognitive benefit minus burden│
│ Input:    ΔC^(m) per intervention per draw                    │
│ Output:   SAFE_A per intervention                             │
│ Logic:    SAFE_A(a) = MSS_cog(a) − 0.3 × MSS_burden(a)      │
│           MSS_cog: mean of ΔC across draws (Monte Carlo mean) │
│           MSS_burden: standardized intervention burden score   │
│           0.3 = burden penalty weight (AUTHOR-CONSTRUCTED)    │
│ Rules:    95% CrI from 2.5th and 97.5th percentiles of draws │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D4b — Mode B: Feasibility-Adjusted Ranking        │
│ Purpose:  Adjust for adherence probability                    │
│ Input:    SAFE_A + P_adhere per intervention                  │
│ Output:   SAFE_B per intervention                             │
│ Logic:    SAFE_B(a) = SAFE_A(a) + 0.5 × ln(P_adhere(a))    │
│           P_adhere: logistic model                            │
│             logit(P_adhere) = 1.8 − 0.42·Burden − 0.03·Dur  │
│           Bundle adherence:                                   │
│             P_adhere(B) = Π_a P_adhere(a) × (1−0.05(|B|−1)) │
│           AUTHOR-ESTIMATED from 6 trials; not formally fitted │
│ Rules:    Low P_adhere → large negative ln → rank drops       │
│           P_adhere < 0.30 → WARNING flag                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D4c — Sensitivity & Discovery Indices             │
│ Purpose:  Identify which edges most influence rankings        │
│ Input:    Full MC draw set + per-edge β values                │
│ Output:   Per-edge elasticity + discovery_score               │
│ Logic:    Elasticity: partial derivative of top rank w.r.t. β │
│             = Corr(β_e^(m), ΔC_top^(m)) across draws        │
│           Discovery score:                                    │
│             discovery_score = |elasticity| × SE_eff          │
│             High: influential edge with high uncertainty      │
│             → research priority                              │
│ Rules:    Top 5 by discovery_score → reported in Chain F      │
└─────────────────────────────────────────────────────────────┘

## D5 — Pathway-Specific Dose Optimization

| Field | Value |
|-------|-------|
| ID | `ALG-D5` |
| Type | COMPOSITE |
| Purpose | Find optimal dose per activated pathway, detect dose conflicts, composite across pathways |
| Research Phase | `RESEARCH_PARAMETERS` (dose-response parameters from trials) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D5a — Per-Pathway Dose Optimization               │
│ Purpose:  For each active pathway, find dose maximizing net   │
│           benefit (cognitive gain minus burden)                │
│ Input:    Active pathways from C4d + dose_response_registry   │
│ Output:   d*_P per pathway                                    │
│ Logic:    d*_P = argmax_d [ΔC_P(d) − 0.3 · Burden(d)]       │
│           ΔC_P(d): dose-response via Hill/Emax:               │
│             ΔC_P(d) = E_max · d^h / (EC₅₀^h + d^h)          │
│           Burden(d): typically linear in dose                 │
│           Optimization: grid search over clinically relevant  │
│             dose range (e.g., exercise: 75-300 min/week)      │
│ Rules:    Respect clinical dose limits                         │
│           d* outside clinical range → clip to range boundary  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D5b — Dose Conflict Detection                     │
│ Purpose:  Flag when different pathways demand different doses │
│ Input:    d*_P per pathway for same intervention              │
│ Output:   conflict_flag + conflict_ratio                      │
│ Logic:    conflict_ratio = max(d*_P) / min(d*_P)             │
│           ratio > 1.3 → DOSE_CONFLICT flag                   │
│ Rules:    DOSE_CONFLICT → report to clinician with pathway    │
│           rationale; default to composite dose                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: D5c — Composite Dose Assembly                     │
│ Purpose:  Weight across pathways to produce single dose rec  │
│ Input:    d*_P per pathway + pathway effect magnitudes        │
│ Output:   d*_composite per intervention                       │
│ Logic:    d*_composite = Σ_{P∈active} w_P · d*_P / Σ w_P    │
│           w_P = |ΔC_P| (weight by pathway's cognitive impact) │
│ Rules:    If only 1 active pathway → d* = d*_P directly      │
└─────────────────────────────────────────────────────────────┘

## D6 — Causal Language Assignment

| Field | Value |
|-------|-------|
| ID | `ALG-D6` |
| Type | ATOMIC |
| Purpose | Assign epistemic claim level to each intervention recommendation |
| Research Phase | `RESEARCH_NONE` (rule application) |

**Steps:**
1. Per edge in the path from intervention to cognition:
   - Classify: causal_supported / associational_only / model_implied
   - causal_supported: RCT with adequate adjustment (backdoor criterion met)
   - associational_only: observational evidence without causal identification
   - model_implied: no direct evidence; inferred from chain synthesis
2. Path-level inheritance: claim_P = min_i(claim_{edge_i})
   - Weakest link in chain determines path claim
3. Intervention-level claim = min across contributing paths
4. Claim demotion triggers:
   - Confounding audit failure → demote to associational
   - Replication failure in Chain B6 → demote
   - Chain-vs-direct Z ≥ 3.0 → demote to model_implied
5. All temporal predictions (Chain E) carry mandatory "Model predicts..." prefix

───────────────────────────────────────────────────────────────────────────

# 6. BOUNDARY TABLES

| Direction | Table | Columns Used | Purpose |
|-----------|-------|-------------|---------|
| READS | FrozenModelState (Chain B) | B̂, Σ_eff, P_inclusion | Edge sampling |
| READS | PatientState (Chain C) | θ̂, Σ_post, active_pathways, B_eff | Patient baseline |
| READS | synergy_registry.csv (15) | pair, JPO, CCS, source_trial | Pairwise interactions |
| READS | dose_response_registry (9) | intervention, E_max, EC₅₀, h | Dose optimization |
| WRITES | (none — all output is in-memory SimulationResults) | | |

───────────────────────────────────────────────────────────────────────────

# 7. GATES & CHECKPOINTS

| Gate ID | Position | Condition | Pass | Fail |
|---------|---------|-----------|------|------|
| D-G1 | After D1 | 10,000 draws generated; no NaN in β; all Include ∈ {0,1} | → D2 | ABORT: sampling failure |
| D-G2 | After D2 | ΔC finite for all draws × interventions; ceiling clips < 20% | → D3 | WARNING if clips > 20% |
| D-G3 | After D3 | Bundle effects computed; γ samples in valid range | → D4 | Review synergy params |
| D-G4 | After D4 | Rankings consistent between modes; CrI finite | → D5 | Numerical error |
| D-G5 | After D5 | Dose recs within clinical ranges; conflicts flagged | → D6 | Review dose limits |
| D-G6 | After D6 | All interventions have claim level assigned | → ALG-E | Claim assignment error |

───────────────────────────────────────────────────────────────────────────

# 8. CHAIN-LEVEL ASSUMPTIONS

| # | Assumption | Impact if Violated | Binding # |
|---|-----------|-------------------|-----------|
| 1 | 10,000 MC draws sufficient for convergence | Rankings may be unstable; top-2 swap probability underestimated | — |
| 2 | Gaussian sampling of β appropriate | Heavy-tailed edge posteriors → under-sample extreme effects | Assumption 5 |
| 3 | Matrix inversion numerically stable (κ < 10¹⁰) | Fallback to path enumeration; may miss some paths | — |
| 4 | Physiological ceilings (±1.0/±1.5 SD) correctly calibrated | Too tight → truncates real effects; too loose → impossible predictions | — (author) |
| 5 | Synergy γ ~ Beta(2,4)×0.40 reasonable | Mis-calibrated → over/under-estimates bundle benefits | — (author) |
| 6 | Adherence model correctly specified | Wrong P_adhere → Mode B rankings misleading | — (author, 6 trials) |
| 7 | Common random numbers yield valid comparisons | If CRN implementation wrong → pairwise comparisons noisy | — (standard method) |

═══════════════════════════════════════════════════════════════════════════


## CHAIN CARD: ALG-E

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: ALG-E  (Temporal Prediction)
═══════════════════════════════════════════════════════════════════════════
Version: 1.1-CORRECTED
Parent System: SYS_ALGORITHM

# 1. IDENTITY

| Field | Value |
|-------|-------|
| Chain ID | `ALG-E` |
| System | `SYS_ALGORITHM` |
| Name | Temporal Prediction |
| Purpose | Project cognitive trajectory over time under natural recovery and intervention scenarios, with growing uncertainty bounds and counterfactual generation for ITE, ARR, RRR, NNT computation |
| Phase | `PHASE_E` — Runtime, per-patient |

**This chain adds the time dimension.** While Chain D answers "how much benefit?", Chain E answers "when does benefit appear, peak, and decay?" — with mandatory epistemic demotion on all temporal claims.

───────────────────────────────────────────────────────────────────────────

# 2. CHAIN DIAGRAM

```
FROM CHAIN ALG-C           FROM CHAIN ALG-D           FROM CHAIN ALG-B
════════════════           ════════════════           ════════════════

 PatientState ──┐    SimulationResults ──┐    FrozenModelState ──┐
 {θ̂, context}   │    {ΔC per interv.}   │    {kernel params}    │
                ▼                       │                       │
       ┌───────────────┐               │                       │
       │  E1            │               │                       │
       │  Nadir         │               │                       │
       │  Estimation    │               │                       │
       └───────┬───────┘               │                       │
               │                        │                       │
        NadirEstimate                   │                       │
        {θ_nadir, scenario,             │                       │
         confidence}                    │                       │
               │                        │                       │
               ▼                        │                       │
       ┌───────────────┐               │                       │
       │  E2            │               │                       │
       │  Natural       │◀──────────────┘                       │
       │  Recovery      │                                       │
       │  Trajectory    │                                       │
       └───────┬───────┘                                       │
               │                                                │
        RecoveryTrajectory                                      │
        {θ(t) natural,                                          │
         R(t) per draw}                                         │
               │                                                │
               ▼                                                │
       ┌───────────────┐◀──────────────────────────────────────┘
       │  E3            │
       │  Intervention  │
       │  Temporal      │
       │  Overlay +     │
       │  Aging         │
       └───────┬───────┘
               │
        InterventionTrajectories[]
        {θ(t) per intervention,
         K_a(t), δ_aging(t)}
               │
               ▼
       ┌───────────────┐
       │  E4            │
       │  Uncertainty   │
       │  Growth +      │
       │  Counterfactuals│
       └───────┬───────┘
               │
               ▼
        TemporalPredictions
        (complete output)
               │
        TO CHAIN ALG-F
```

───────────────────────────────────────────────────────────────────────────

# 3. INTERMEDIATE STATE SCHEMAS

### State: NadirEstimate (after E1)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| θ_nadir | ℝ^{63} | Estimated worst cognitive state | E1 | E2 |
| estimation_scenario | enum{DURING_TX, EARLY_POST, LATE_POST} | Which method used | E1 | E2, F |
| confidence | float [0, 1] | Confidence in nadir estimate | E1 | F |
| Δt_since_treatment | float | Months since treatment end | E1 | E2 |
| θ_base | ℝ^{63} | Pre-treatment baseline (if available) | E1 | E2 |

### State: RecoveryTrajectory (after E2)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| θ_natural | ℝ^{63 × T} | Natural trajectory at monthly intervals | E2 | E3, E4 |
| R_draws | ℝ^{10000 × T} | Recovery fraction R(t) per MC draw | E2 | E4 |
| recovery_params | {r_∞, τ_R, γ_R} | Context-specific recovery parameters | E2 | F |
| T_horizons | list[int] | Prediction horizons in months | E2 | E3, E4 |

### State: InterventionTrajectory (after E3, one per intervention)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| intervention_id | str | Which intervention | E3 | E4 |
| θ_intervention | ℝ^{63 × T} | Trajectory under intervention | E3 | E4 |
| K_a | ℝ^{T} | Temporal kernel values at each horizon | E3a | E4, F |
| δ_aging | ℝ^{T} | Aging contribution at each horizon | E3b | E4, F |
| path_lags | dict[path → {cumulative_lag, half_life}] | Multi-hop delays | E3c | F |

### State: TemporalPredictions (final output)
| Field | Type | Description | Produced By | Consumed By |
|-------|------|-------------|-------------|-------------|
| natural_trajectory | ℝ^{63 × T} with 95% CrI | Monthly intervals | E2+E4 | F |
| per_intervention_trajectory | dict[intervention → trajectory + CrI] | Under each intervention | E3+E4 | F |
| ITE_at_horizons | dict[intervention × horizon → {mean, CrI}] | Individual treatment effect | E4 | F |
| clinical_metrics | dict[intervention × horizon → {ARR, RRR, NNT}] | Derived clinical metrics | E4 | F |
| nadir_estimate | NadirEstimate | From E1 | E1 | F |
| aging_projection | ℝ^{T} | δ_aging at each horizon | E3 | F |
| uncertainty_growth | ℝ^{T} | Var(θ(t)) decomposition | E4 | F |

───────────────────────────────────────────────────────────────────────────

# 4. SUBSYSTEM INVENTORY

| Order | Subsystem ID | Name | Input State | Output State | Type |
|-------|-------------|------|-------------|-------------|------|
| 1 | ALG-E1 | Nadir Estimation | PatientState + treatment timeline | NadirEstimate | COMPOSITE |
| 2 | ALG-E2 | Natural Recovery Trajectory | NadirEstimate + recovery_registry | RecoveryTrajectory | COMPOSITE |
| 3 | ALG-E3 | Intervention Temporal Overlay + Aging | RecoveryTrajectory + Chain D outputs + kernel_registry | InterventionTrajectory[] | COMPOSITE |
| 4 | ALG-E4 | Uncertainty Growth + Counterfactuals | All E1-E3 + Σ_post | TemporalPredictions | COMPOSITE |

───────────────────────────────────────────────────────────────────────────

# 5. SUBSYSTEM DETAIL

## E1 — Nadir Estimation

| Field | Value |
|-------|-------|
| ID | `ALG-E1` |
| Type | COMPOSITE |
| Purpose | Estimate the patient's cognitive nadir (worst point) based on treatment timing — determines recovery trajectory baseline |
| Research Phase | `RESEARCH_PARAMETERS` (treatment-specific nadir depth estimates) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E1a — Treatment Timeline Classification           │
│ Purpose:  Determine which nadir scenario applies             │
│ Input:    treatment_phase, treatment_end_date, current_date   │
│ Output:   estimation_scenario + Δt_since_treatment            │
│ Logic:    (a) DURING_TX: patient currently in treatment       │
│             Δt = 0; θ_nadir = θ_current                      │
│           (b) EARLY_POST: Δt < 6 months post-treatment       │
│             Recovery has begun but nadir is recent enough      │
│             to back-estimate from current observations         │
│           (c) LATE_POST: Δt ≥ 6 months post-treatment        │
│             Nadir was long ago; must estimate from context     │
│ Rules:    Treatment end unknown → assume DURING_TX            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E1b — Nadir Back-Estimation (Scenario b)          │
│ Purpose:  Estimate nadir from current state + recovery model │
│ Input:    θ_current, θ_base (if available), Δt, R(Δt)       │
│ Output:   θ_nadir                                             │
│ Logic:    θ_nadir = (θ_current − θ_base · R(Δt)) / (1−R(Δt))│
│           Where R(Δt) is recovery fraction at time Δt         │
│           (loaded from recovery_registry, evaluated at Δt)    │
│ Rules:    Stable only when R(Δt) < 0.8                       │
│           If R(Δt) ≥ 0.8 → switch to Scenario (c)           │
│           θ_base unknown → use μ_prior as proxy               │
│           Wider CrI when θ_base unavailable                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E1c — Context-Based Nadir (Scenario c)            │
│ Purpose:  Estimate nadir from population-level treatment data │
│ Input:    context_match from C1, μ_context, δ_treatment       │
│ Output:   θ_nadir = μ_context − δ_treatment                  │
│ Logic:    δ_treatment: expected treatment-induced decrement    │
│           from context_matched_priors (per cancer × regimen)  │
│ Rules:    Widest CrI (nadir was never directly observed)      │
│           Confidence lowest for this scenario                 │
└─────────────────────────────────────────────────────────────┘

## E2 — Natural Recovery Trajectory

| Field | Value |
|-------|-------|
| ID | `ALG-E2` |
| Type | COMPOSITE |
| Purpose | Project cognitive state over time under natural recovery (no intervention) using stretched exponential model |
| Research Phase | `RESEARCH_PARAMETERS` (7 context-specific recovery parameter sets) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E2a — Recovery Parameter Loading                  │
│ Purpose:  Load context-specific {r_∞, τ_R, γ_R} parameters  │
│ Input:    context_match from C1 + recovery_registry (7 rows) │
│ Output:   {r_∞, τ_R, γ_R} for this patient's context         │
│ Logic:    7 contexts in recovery_registry:                    │
│           (e.g., breast_chemo, colorectal_chemo,              │
│            lymphoma_chemo, etc.)                              │
│           Match by cancer_type + treatment_type               │
│           Fallback: general_cancer_chemo defaults             │
│ Rules:    If no match → use general parameters + wider CrI   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E2b — Stretched Exponential Recovery Curve        │
│ Purpose:  Compute R(t) at monthly intervals                  │
│ Input:    {r_∞, τ_R, γ_R}                                    │
│ Output:   R(t) = r_∞ · (1 − e^{−(t/τ_R)^{γ_R}}) at t=1..36│
│ Logic:    r_∞ ∈ [0,1]: fraction that eventually recovers     │
│           τ_R: recovery time constant (months)               │
│           γ_R: shape parameter                               │
│             γ < 1: rapid early recovery, slow tail           │
│             γ = 1: standard exponential                      │
│             γ > 1: delayed onset then rapid recovery         │
│ Rules:    R(0) = 0 (no recovery at nadir)                    │
│           R(∞) → r_∞ (asymptotic limit)                      │
│           Most CRCI: γ ≈ 0.7-0.9 (rapid early, slow tail)   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E2c — MC Recovery Trajectory Sampling             │
│ Purpose:  Sample recovery parameters to generate trajectory  │
│           uncertainty bands                                   │
│ Input:    {r_∞, τ_R, γ_R} + θ_nadir + θ_base                │
│ Output:   θ_natural(t)^(m) for m=1..10000, t=1..36 months   │
│ Logic:    Per draw m:                                         │
│           r_∞^(m) ~ N(r_∞, 0.10²)  [clipped to (0,1)]      │
│           τ_R^(m) ~ LogNormal(ln(τ_R), 0.20²)               │
│           γ_R: fixed (insufficient data for posterior)        │
│           θ_natural(t)^(m) = θ_nadir + (θ_base−θ_nadir)·R(t)│
│ Rules:    Use same random number stream as Chain D draws      │
│           (enables correlated comparison)                     │
└─────────────────────────────────────────────────────────────┘

## E3 — Intervention Temporal Overlay + Aging

| Field | Value |
|-------|-------|
| ID | `ALG-E3` |
| Type | COMPOSITE |
| Purpose | Overlay intervention effects onto natural recovery using temporal kernels, add aging contribution |
| Research Phase | `RESEARCH_PARAMETERS` (kernel params from trials, ACC from epidemiology) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E3a — Intervention Kernel Application             │
│ Purpose:  Model temporal shape of each intervention's effect  │
│ Input:    intervention_kernel_registry (9 rows) +             │
│           ΔC per intervention from Chain D                    │
│ Output:   K_a(t) per intervention at each time horizon        │
│ Logic:    Trapezoidal kernel per intervention:                │
│           Phase 1 — Onset: linear ramp (0 → 1) over onset_wk │
│           Phase 2 — Build: linear ramp (1 → peak) over build │
│           Phase 3 — Steady: plateau at peak for steady_wk    │
│           Phase 4 — Decay: exponential with half-life         │
│             K(t) = peak × e^{−0.693(t−t_steady)/half_life}   │
│                                                               │
│           9 intervention kernels:                             │
│           (exercise, CBT-I, mindfulness, omega-3, etc.)      │
│           Each has: {onset_wk, build_wk, steady_wk,          │
│                      decay_half_life_wk}                      │
│                                                               │
│           Effective ΔC at time t:                             │
│             ΔC_a(t) = ΔC_a × K_a(t)                          │
│ Rules:    K_a(t) ∈ [0, 1] always                             │
│           Intervention discontinued → decay begins            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E3b — Accelerated Cognitive Aging                 │
│ Purpose:  Model treatment-induced acceleration of normal      │
│           cognitive aging                                     │
│ Input:    age, treatment_type, ACC_table (5 rows)             │
│ Output:   δ_aging(Δt) at each time horizon                    │
│ Logic:    δ_aging(Δt) = −0.02 × max(1, (age−50)/10) × ACC   │
│                        × Δt_years                             │
│           ACC (Accelerated Cognitive aging Coefficient):      │
│             No chemotherapy:   ACC = 1.0                     │
│             TC (docetaxel):    ACC = 1.3                     │
│             Standard chemo:    ACC = 1.5                     │
│             Anthracycline:     ACC = 2.0                     │
│             Childhood cancer:  ACC = 2.5                     │
│           Base aging rate: 0.02 SD/year (normal decline)      │
│           Age adjustment: max(1, (age−50)/10)                │
│             Age 50: 1.0×; Age 60: 1.0×; Age 70: 2.0×        │
│ Rules:    δ_aging always negative (decline)                   │
│           Small at short horizons, meaningful at >12 months   │
│           ACC values AUTHOR-CONSTRUCTED from epidem. estimates│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E3c — Multi-Hop Path Lag Computation              │
│ Purpose:  Model delay in mechanistic pathways (indirect       │
│           effects take time to manifest)                      │
│ Input:    Pathway definitions + per-edge lag parameters        │
│ Output:   CumulativeLag(P) + PathHalfLife(P) per pathway      │
│ Logic:    CumulativeLag(P) = Σ_{e∈P} lag_onset(e)            │
│           PathHalfLife(P) = min_{e∈P} half_life(e)           │
│           (bottleneck: slowest-decaying edge in the path)     │
│                                                               │
│           Effect: indirect pathways activate later and         │
│           decay faster than direct pathways                   │
│ Rules:    Shift intervention kernel by CumulativeLag          │
│           Apply PathHalfLife as additional decay               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E3d — Full Trajectory Assembly                    │
│ Purpose:  Combine recovery + intervention + aging into full   │
│           trajectory equation                                 │
│ Input:    All E2 + E3a-c outputs                              │
│ Output:   θ(t+Δt) per intervention per draw                   │
│ Logic:    θ(t+Δt) = [θ_nadir + (θ_base − θ_nadir) · R(Δt)]  │
│                    + Σ_a ΔC_a · K_a(Δt)                      │
│                    + δ_aging(Δt)                               │
│           Term 1: Natural recovery (stretched exponential)     │
│           Term 2: Intervention effects (kernel-modulated)     │
│           Term 3: Aging (always negative)                     │
│ Rules:    All three terms additive                             │
│           Compute at t = 0, 1, 2, ..., 36 months              │
│           Standard horizons for reporting: 3, 6, 12, 24 mo   │
└─────────────────────────────────────────────────────────────┘

## E4 — Uncertainty Growth + Counterfactuals

| Field | Value |
|-------|-------|
| ID | `ALG-E4` |
| Type | COMPOSITE |
| Purpose | Model growing prediction uncertainty over time, generate counterfactual comparisons (ITE), derive clinical metrics |
| Research Phase | `RESEARCH_CALIBRATION` (uncertainty growth rates author-estimated) |

**Sub-steps:**

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E4a — Uncertainty Growth Model                    │
│ Purpose:  Predictions become less certain over time           │
│ Input:    Var(θ₀) from Σ_post                                 │
│ Output:   Var(θ(t)) at each horizon                           │
│ Logic:    Var(θ(t)) = Var(θ₀) + 0.01·t + 0.005·t²           │
│           Term 1: Baseline uncertainty (from posterior)        │
│           Term 2: Linear growth (~0.1 SD/month)              │
│             Author-estimated from CRCI longitudinal variability│
│           Term 3: Quadratic (uncertainty about uncertainty)   │
│             Second-order term; small at short horizons,        │
│             dominant at long horizons                         │
│ Rules:    At 3mo: +0.075 variance; at 12mo: +0.84;           │
│           at 24mo: +3.12. CrI widens substantially.          │
│           AUTHOR-CONSTRUCTED; needs longitudinal calibration  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E4b — Individual Treatment Effect (ITE)           │
│ Purpose:  Compute per-draw counterfactual comparison          │
│ Input:    θ_intervention(t)^(m) and θ_natural(t)^(m)         │
│ Output:   ITE(Δt)^(m) = θ_intervention − θ_natural           │
│ Logic:    For each draw m, at each horizon t:                 │
│             ITE^(m)(t) = θ_intervention^(m)(t) − θ_natural^(m)(t)│
│           Summary: mean, 2.5th, 97.5th percentiles across m  │
│ Rules:    ITE > 0 → intervention helps (higher is better     │
│           for functional capacity nodes)                      │
│           Common random numbers ensure valid comparison       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: E4c — Clinical Metric Derivation                  │
│ Purpose:  Compute ARR, RRR, NNT for crossing severity bounds │
│ Input:    ITE distributions + severity thresholds              │
│ Output:   Per intervention × horizon: {ARR, RRR, NNT}        │
│ Logic:    Define "impaired" as crossing severity threshold     │
│           (e.g., composite score < 50th percentile)           │
│           P_impaired_natural = fraction of draws where        │
│             θ_natural(t) crosses threshold                    │
│           P_impaired_intervention = fraction where             │
│             θ_intervention(t) crosses threshold               │
│           ARR = P_natural − P_intervention                    │
│           RRR = ARR / P_natural (when P_natural > 0)         │
│           NNT = 1 / ARR (when ARR > 0)                       │
│ Rules:    NNT < 3 → strong recommendation                    │
│           NNT 3-10 → moderate                                 │
│           NNT > 10 → weak                                     │
│           Report with CrI (percentiles of per-draw NNT)      │
│           Mandatory: "Model predicts..." prefix on all output│
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────

# 6. BOUNDARY TABLES

| Direction | Table | Columns Used | Purpose |
|-----------|-------|-------------|---------|
| READS | PatientState (Chain C) | θ̂, Σ_post, context_match | Baseline + context |
| READS | SimulationResults (Chain D) | ΔC per intervention | Effect magnitudes |
| READS | recovery_registry.csv (7) | context, r_∞, τ_R, γ_R | Natural recovery params |
| READS | intervention_kernel_registry (9) | onset_wk, build_wk, steady_wk, decay_hl | Temporal shapes |
| READS | ACC_table (5) | treatment_context → ACC coefficient | Aging acceleration |
| WRITES | (none — all output is in-memory TemporalPredictions) | | |

───────────────────────────────────────────────────────────────────────────

# 7. GATES & CHECKPOINTS

| Gate ID | Position | Condition | Pass | Fail |
|---------|---------|-----------|------|------|
| E-G1 | After E1 | θ_nadir finite; scenario classified; confidence > 0 | → E2 | ABORT: nadir estimation failed |
| E-G2 | After E2 | R(t) ∈ [0, r_∞] for all t; trajectory monotonically improving | → E3 | Recovery params invalid |
| E-G3 | After E3 | K_a(t) ∈ [0,1]; δ_aging ≤ 0; full trajectory finite | → E4 | Kernel or aging error |
| E-G4 | After E4 | Var(θ(t)) monotonically increasing; ITE finite; NNT > 0 | → ALG-F | Uncertainty model error |

───────────────────────────────────────────────────────────────────────────

# 8. CHAIN-LEVEL ASSUMPTIONS

| # | Assumption | Impact if Violated | Binding # |
|---|-----------|-------------------|-----------|
| 1 | Stretched exponential recovery model appropriate | Wrong trajectory shape → prediction errors at all horizons | — |
| 2 | Recovery params from 7 contexts generalize | Unrepresented contexts → wrong recovery speed | — |
| 3 | Intervention kernels (trapezoidal) are accurate | Wrong onset/plateau/decay timing → misleading "when" predictions | — |
| 4 | Aging is linear in time at each horizon | If aging accelerates non-linearly, long-horizon predictions biased | — |
| 5 | Uncertainty growth (linear+quadratic) calibrated | Too aggressive → unnecessarily wide CrI; too conservative → overconfident | — (author) |
| 6 | Recovery and intervention effects additive | If interaction (recovery × intervention), simple addition wrong | Assumption 8 |
| 7 | ACC coefficients correctly distinguish regimens | Wrong ACC → over/under-estimates of long-term cognitive trajectory | — (author) |

═══════════════════════════════════════════════════════════════════════════
## CHAIN CARD: ALG-F

═══════════════════════════════════════════════════════════════════════════
CHAIN CARD: ALG-F (Output & Analytics)
═══════════════════════════════════════════════════════════════════════════
Version: 1.0
Parent System: SYS_ALGORITHM

1. IDENTITY
Field                Value
Chain ID             ALG-F
System               SYS_ALGORITHM
Name                 Output & Analytics
Purpose              Synthesize all upstream outputs into three consumer-specific
                     packages: clinical (per-patient recommendations), population
                     (archetype discovery), and research (evidence gap prioritization)
Phase                PHASE_F — Runtime, per-patient (Clinical + Population + Research modes)
Paper §              §2.19 (Decision Stability), §2.20 (Composite Outcome),
                     §2.22 (Evidence Gaps), §4.5 (Output Architecture)
Subsystems           5 (F1–F5)
Formulas             10 (F-1 through F-10)

───────────────────────────────────────────────────────────────────────────
2. CHAIN DIAGRAM

FROM ALG-C/D/E (all outputs)                                   TO SYS_RUNTIME
════════════════════════════                                   ═══════════════

 PatientState ──────────────┐
 SimulationResults ─────────┤
 TemporalPredictions ───────┤
                            │
                     ┌──────▼──────┐
                     │     F1      │
                     │  Composite  │◀── nodes_v1 (severity weights)
                     │  Outcome    │
                     │  Scoring    │
                     └──────┬──────┘
                            │ CompositeState
                            ▼
                     ┌─────────────┐
                     │     F2      │
                     │  Decision   │◀── SimulationResults.per_draw_rankings
                     │  Stability  │
                     │  Analysis   │
                     └──────┬──────┘
                            │ StabilityState
                            ▼
                     ┌─────────────┐
                     │     F3      │
                     │  Variance   │◀── edges_v1 (SE_eff per edge)
                     │  Decomp.    │    instruments_v1 (α reliability)
                     │             │    PatientState (missing obs mask)
                     └──────┬──────┘
                            │ VarianceState
                            ▼
                     ┌─────────────┐
                     │     F4      │
                     │  Population │◀── pathway_activation profiles (from ALG-D)
                     │  Analytics  │    population_archetypes_v1 (if exists)
                     │  (GMM)      │
                     └──────┬──────┘
                            │ PopulationState
                            ▼
                     ┌─────────────┐
                     │     F5      │
                     │  Research   │◀── edges_v1 (evidence counts, SE_eff)
                     │  Analytics  │    chain_direct_validation (from VAL-01)
                     │  (EVSI)     │
                     └──────┬──────┘
                            │
                            ▼
                     3 Output Packages
                     → SYS_RUNTIME

Data flow type: All intermediate states are IN-MEMORY. Final packages are
written to Class E output tables (intervention_rankings_v1, session outputs).

───────────────────────────────────────────────────────────────────────────
3. INTERMEDIATE STATE SCHEMAS

State: CompositeState (after F1, 1 per patient)
Field                       Type              Description                    Source
crci_composite              float             IVW composite z-score          F1
severity_tier               enum(6)           Excellent/Good/Mild/Moderate/  F1
                                              Poor/Severe
percentile                  float [0,100]     Φ(−z) × 100                   F1
subdomain_scores            dict[domain→z]    Per-domain z-scores (11)       F1
subdomain_weights           dict[domain→w]    1/σ²_d per domain              F1
cochrans_Q                  float             Subdomain heterogeneity stat   F1
I_squared                   float [0,1]       % variance due to real diffs   F1
random_effects_applied      bool              True if I² > 50%               F1
severity_weighted_z         dict[domain→wz]   z × severity_weight per domain F1

State: StabilityState (after F2, 1 per patient)
Field                       Type              Description                    Source
rank_1_probabilities        dict[action→P]    P(rank₁ = a) per action        F2
stability_class             enum(4)           Stable/Moderate/Unstable/      F2
                                              Highly_unstable
decision_critical_edges     list[3×EdgeID]    Edges with highest flip        F2
                                              influence on rankings
flip_counts                 dict[edge→int]    Per-edge count of rank changes F2
pairwise_dominance          dict[(a,b)→P]     P(SAFE_a > SAFE_b) per pair    F2

State: VarianceState (after F3, 1 per patient)
Field                       Type              Description                    Source
total_variance              float             Var(CRCI_composite)            F3
literature_pct              float [0,1]       τ² share                       F3
measurement_pct             float [0,1]       σ²_y share                     F3
structural_pct              float [0,1]       P_inclusion share              F3
proxy_pct                   float [0,1]       R²_proxy share                 F3
missing_pct                 float [0,1]       Missing obs share              F3
top_reducible               list[2×{source,   Top 2 sources where new data   F3
                            reduction_pct}]   would help most
per_edge_variance_contrib   dict[edge→float]  Variance contribution per edge F3

State: PopulationState (after F4, 1 per analysis run)
Field                       Type              Description                    Source
K_clusters                  int               Optimal cluster count (BIC)    F4
archetypes                  list[K×Archetype] Cluster profiles               F4
patient_assignment          int               Which archetype this patient   F4
mahalanobis_distance        float             Distance to assigned centroid  F4
escalation_flag             bool              True if distance > 2.5         F4

State: OutputPackages (final output)
Field                       Type              Description                    Source
clinical_package            ClinicalOutputPkg Full clinical report           F1-F3
population_package          PopulationOutPkg  Archetype assignment           F4
research_package            ResearchOutPkg    Evidence gaps + EVSI           F5

───────────────────────────────────────────────────────────────────────────
4. SUBSYSTEM INVENTORY

Order  Subsystem ID  Name                      Input State              Output State       Type
1      ALG-F1        Composite Outcome Score   PatientState + SimRes    CompositeState     COMPOSITE
2      ALG-F2        Decision Stability        SimRes draws + ranks     StabilityState     COMPOSITE
3      ALG-F3        Variance Decomposition    PatientState + edges_v1  VarianceState      COMPOSITE
4      ALG-F4        Population Analytics      Pathway profiles (D)     PopulationState    COMPOSITE
5      ALG-F5        Research Analytics        edges_v1 + VAL results   ResearchOutPkg     COMPOSITE

───────────────────────────────────────────────────────────────────────────
5. SUBSYSTEM DETAIL

## F1 — Composite Outcome Scoring
Field        Value
ID           ALG-F1
Type         COMPOSITE
Purpose      Compute a single CRCI composite score from all cognitive subdomain
             z-scores using inverse-variance weighting, with severity adjustment
Phase        PHASE_F
Paper §      §2.20

Input:  PatientState.posterior_means (63-vector), posterior_variances (63-vector)
Output: CompositeState → F2

Sub-steps:
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F1a — Subdomain Extraction                        │
│ Purpose: Extract cognitive subdomain z-scores from the      │
│          63-node posterior                                   │
│ Input:   PatientState.posterior_means                        │
│ Output:  subdomain_scores: dict[domain → z]                 │
│ Logic:   For each of 11 clinical domains:                   │
│   - Select nodes belonging to domain (from node_hierarchy)  │
│   - If domain has multiple nodes: z_d = mean(z_nodes)       │
│   - If domain has 1 node: z_d = z_node                      │
│   - Record σ²_d from posterior variance (propagated)        │
│ Rules:   Skip domains with zero observable nodes             │
│          Domains: Processing Speed, Attention, Executive,    │
│          Memory (verbal), Memory (visual), Working Memory,   │
│          Language, Visuospatial, Motor, Mood, Fatigue        │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F1b — Severity Weighting                          │
│ Purpose: Apply non-linear severity weights to subdomain     │
│          scores before compositing                          │
│ Input:   subdomain_scores from F1a                          │
│ Output:  severity_weighted_z per domain                     │
│ Logic:   For each domain d:                                 │
│   - |z_d| < 1.0 SD → weight = 1.0×                         │
│   - 1.0 ≤ |z_d| < 2.0 SD → weight = 1.5×                  │
│   - |z_d| ≥ 2.0 SD → weight = 2.0×                         │
│   - severity_weighted_z_d = z_d × severity_weight           │
│ Rules:   Severity weighting amplifies clinically            │
│          significant deficits in the composite              │
│          Paper §2.20: MID = 0.50 SD (primary threshold)     │
│          Liberal: 0.30 SD; Conservative: 0.70 SD            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F1c — IVW Composite                               │
│ Purpose: Compute inverse-variance weighted composite score  │
│ Input:   severity_weighted_z, σ²_d per domain               │
│ Output:  crci_composite, percentile, severity_tier          │
│ Logic:                                                      │
│   w_d = 1 / σ²_d                        [Formula F-1]      │
│   CRCI_composite = Σ_d (w_d × z_d) / Σ_d w_d              │
│   Percentile = Φ(−CRCI_composite) × 100 [Formula F-2]      │
│                                                             │
│   Cochran's Q = Σ_d w_d(z_d − CRCI)²   [Formula F-3]      │
│   I² = max(0, (Q − (D−1))/Q) × 100%                       │
│   If I² > 50%: apply random-effects adjustment              │
│     → add τ² = max(0, (Q−(D−1))/(Σw − Σw²/Σw))           │
│     → w*_d = 1/(σ²_d + τ²)                                │
│     → recompute composite with w*_d                         │
│                                                             │
│   Severity tier:                                            │
│     Percentile 85-100 → Excellent                           │
│     Percentile 70-84  → Good                                │
│     Percentile 50-69  → Mild impairment                     │
│     Percentile 30-49  → Moderate impairment                 │
│     Percentile 15-29  → Poor                                │
│     Percentile 0-14   → Severe impairment                   │
│ Rules: If all σ²_d are equal, composite = simple mean       │
│        If only 1 domain observed, composite = that z-score  │
└─────────────────────────────────────────────────────────────┘

Validation gate: crci_composite ∈ [−5, 5] SD; percentile ∈ [0, 100];
Σ weights > 0; severity tier assigned.

## F2 — Decision Stability Analysis
Field        Value
ID           ALG-F2
Type         COMPOSITE
Purpose      Assess how stable the intervention ranking is across Monte Carlo
             draws — determines clinical confidence in recommendations
Phase        PHASE_F
Paper §      §2.19

Input:  SimulationResults.per_draw_safe_scores (10,000 × A matrix, A = candidate actions)
Output: StabilityState → F3

Sub-steps:
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F2a — Per-Draw Ranking                            │
│ Purpose: Rank all candidate interventions within each MC    │
│          draw                                               │
│ Input:   per_draw_safe_scores: 10,000 × A matrix           │
│ Output:  per_draw_rankings: 10,000 × A matrix of ranks     │
│ Logic:   For each draw m ∈ {1, ..., 10,000}:               │
│   - Sort candidates by SAFE_B(a)^(m) descending            │
│   - Assign rank 1 to highest, rank A to lowest             │
│   - Ties broken by SAFE_A (efficacy-only)                  │
│ Rules:   Use SAFE_B (feasibility-adjusted) as primary       │
│          ranking criterion per paper §2.19                  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F2b — Rank Probability Computation                │
│ Purpose: Compute probability each intervention is rank 1    │
│ Input:   per_draw_rankings                                  │
│ Output:  rank_1_probabilities, stability_class              │
│ Logic:                                                      │
│   P(rank₁ = a) = (1/N) Σ_m 𝟙[rank₁^(m) = a]  [F-4]      │
│                                                             │
│   Stability classification:                                 │
│     P(rank₁) ≥ 0.80 → STABLE                               │
│     0.60 ≤ P(rank₁) < 0.80 → MODERATE                      │
│     0.40 ≤ P(rank₁) < 0.60 → UNSTABLE                      │
│     P(rank₁) < 0.40 → HIGHLY_UNSTABLE                      │
│                                                             │
│   Also compute pairwise dominance:                          │
│   P(a > b) = (1/N) Σ_m 𝟙[SAFE_B(a)^(m) > SAFE_B(b)^(m)] │
│ Rules:   HIGHLY_UNSTABLE triggers mandatory uncertainty     │
│          disclosure in clinical output                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F2c — Decision-Critical Edge Identification       │
│ Purpose: Find top 3 edges whose uncertainty most affects    │
│          the ranking                                        │
│ Input:   per_draw_rankings, SimulationResults.per_draw_β    │
│ Output:  decision_critical_edges (top 3), flip_counts       │
│ Logic:   For each edge e in edges_v1:                       │
│   - Partition draws by: β_e > median vs β_e ≤ median       │
│   - Count rank flips between top-2 actions across partition │
│   - flip_influence(e) = |rank₁_above − rank₁_below| / N   │
│   - Select top 3 edges by flip_influence                    │
│ Rules:   Decision-critical edges are flagged for research   │
│          prioritization in F5                               │
│          Edge must have ≥100 draws in each partition        │
└─────────────────────────────────────────────────────────────┘

Validation gate: Σ_a P(rank₁ = a) = 1.0 (within ε=0.001);
stability_class assigned; exactly 3 critical edges identified.

## F3 — Five-Source Variance Decomposition
Field        Value
ID           ALG-F3
Type         COMPOSITE
Purpose      Decompose total prediction variance into 5 actionable sources
             to guide clinical uncertainty communication and research priorities
Phase        PHASE_F
Paper §      §2.21 (Assumptions), implied by §2.9, §2.7, §2.8

Input:  PatientState (posterior Λ), edges_v1 (SE_eff), instruments_v1 (α)
Output: VarianceState → F4

Sub-steps:
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3a — Literature Heterogeneity Component          │
│ Purpose: Compute variance share from inter-study τ²         │
│ Input:   edges_v1.tau_squared per edge                      │
│ Output:  literature_variance (scalar)                       │
│ Logic:   Sum τ² across all edges weighted by path           │
│          sensitivity (∂θ_target/∂β_e)²:                     │
│          V_lit = Σ_e (∂θ/∂β_e)² × τ²_e                    │
│ Rules:   Edges with k=0 or k=1 have τ²=0 (no pooling)     │
│          These edges contribute through structural var      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3b — Measurement Noise Component                 │
│ Purpose: Compute variance from instrument reliability       │
│ Input:   instruments_v1.alpha_k, PatientState observations  │
│ Output:  measurement_variance (scalar)                      │
│ Logic:   For each observed node i with instrument k:        │
│          σ²_{y,k} = b²_k × (1−α_k)/α_k    [from ALG-C]   │
│          V_meas = Σ_k σ²_{y,k} × (weight_k)²              │
│          where weight_k = information gain from obs k       │
│ Rules:   Unobserved nodes contribute 0 measurement noise   │
│          (they contribute through missing_obs instead)      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3c — Structural Model Uncertainty Component      │
│ Purpose: Compute variance from stochastic edge inclusion    │
│ Input:   edges_v1.P_inclusion, MC draw results              │
│ Output:  structural_variance (scalar)                       │
│ Logic:   V_struct = Var_draws[θ | β_included vs excluded]   │
│          Estimated from MC: compare draws where edge e is   │
│          included vs excluded, compute conditional variance │
│          Total structural: σ²_struct per edge (9 components):│
│            identification 0.06, confounding 0.04,           │
│            selection 0.03, measurement 0.04,                │
│            transportability 0.03, model form 0.02,          │
│            temporal 0.015, missing moderator 0.015,         │
│            publication bias 0.01                            │
│ Base:    σ²_struct = 0.25 (sum of 9 components above)      │
│ v2.0:    σ²_struct = edges_v1.sigma_sq_structural per-edge  │
│          Default 0.25 if NULL (no annotations available)    │
│          Annotation-informed: EX-P4-MA adjusts upward from  │
│          0.25 based on limitation_unmeasured_confounder      │
│          annotations (ceiling 0.50). See EX-P4-MA-c.       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3d — Proxy Imprecision Component                 │
│ Purpose: Compute variance from latent-proxy gaps            │
│ Input:   proxy_table (from ALG-A GraphObject), R²_proxy     │
│ Output:  proxy_variance (scalar)                            │
│ Logic:   For each latent node with proxy:                   │
│          V_proxy_i = Var(θ_latent) × (1 − R²_proxy)        │
│          V_proxy = Σ_i V_proxy_i × (path_weight_i)²        │
│ Rules:   R²_proxy < 0.3 → LOW_PROXY_VALIDITY warning       │
│          15 latent nodes contribute; 48 observable do not   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3e — Missing Observation Component               │
│ Purpose: Compute variance from unobserved nodes             │
│ Input:   PatientState.observed_mask, posterior Λ            │
│ Output:  missing_variance (scalar)                          │
│ Logic:   V_missing = Var(θ_target | observed) −             │
│                      Var(θ_target | fully observed)         │
│          Computed via: ΔVar = Σ_{unobs} Cov(target,i)² /   │
│                        Var(i)    [Formula F-5]              │
│          This is the variance REDUCTION that would occur    │
│          if the missing observations were collected         │
│ Rules:   Patient-specific — depends on which tests were     │
│          administered. Maximum when many nodes unobserved.  │
│          Top 2 reducible sources reported to clinician      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F3f — Normalization and Reporting                 │
│ Purpose: Express each source as % of total variance         │
│ Input:   V_lit, V_meas, V_struct, V_proxy, V_missing       │
│ Output:  VarianceState with percentages + top 2 reducible   │
│ Logic:   V_total = V_lit + V_meas + V_struct + V_proxy     │
│                    + V_missing                              │
│          pct_x = V_x / V_total × 100 for each source       │
│          Typical ranges (from paper):                       │
│            Literature: 25–40%                               │
│            Measurement: 10–20%                              │
│            Structural: 15–25%                               │
│            Proxy: 10–20%                                    │
│            Missing: 10–30%                                  │
│          Top 2 reducible = largest of {meas, proxy, missing}│
│          (Literature and structural are NOT easily reducible│
│           per-patient; they require new studies)            │
│ Rules:   Sum of percentages = 100%                          │
│          Actionable message: "Collecting [top test] would   │
│          reduce your uncertainty by ~[X]%"                  │
└─────────────────────────────────────────────────────────────┘

Validation gate: 5 components sum to total (within ε=0.01);
all percentages ∈ [0, 100]; top 2 reducible identified.

## F4 — Population Analytics (Archetype Discovery)
Field        Value
ID           ALG-F4
Type         COMPOSITE
Purpose      Cluster patients into archetypes based on pathway activation
             profiles for population-level pattern discovery
Phase        PHASE_F
Paper §      §4.5 (implied)

Input:  Pathway activation profiles (from ALG-D), historical profiles if available
Output: PopulationState → F5

Sub-steps:
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F4a — Profile Extraction                          │
│ Purpose: Build patient pathway activation vector            │
│ Input:   SimulationResults.pathway_activations              │
│          (20 pathways × activation z-score)                 │
│ Output:  activation_vector: ℝ^20                            │
│ Logic:   For each of 20 pathways (15 Tier1 + 5 Tier2):     │
│   - Extract mean activation from posterior                  │
│   - Normalize to z-score scale                              │
│   - Binary dysregulation flag: |z| > τ_P (0.5 SD default)  │
│ Rules:   Profile is patient-specific + pathway-specific     │
│          Captures WHICH biological pathways are active      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F4b — Gaussian Mixture Model Clustering           │
│ Purpose: Discover K natural patient archetypes              │
│ Input:   activation_vectors (current + historical pool)     │
│ Output:  K clusters, centroids, assignments                 │
│ Logic:   Fit GMM with K ∈ {2, ..., 8}                       │
│          Select K by BIC = −2 ln(L) + K·ln(n)              │
│          Minimum cluster size: 5% of pool                   │
│          If pool < 20 patients: skip clustering,            │
│            assign to nearest pre-defined archetype          │
│ Rules:   GMM preferred over K-means for non-spherical       │
│          clusters. Archetypes are DESCRIPTIVE, not           │
│          prescriptive — they guide defaults, not mandates   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F4c — Escalation Check                            │
│ Purpose: Flag patients who don't fit any archetype well     │
│ Input:   patient assignment, Mahalanobis distance           │
│ Output:  escalation_flag, mahalanobis_distance              │
│ Logic:   d_M = √((x − μ_k)ᵀ Σ_k⁻¹ (x − μ_k))            │
│          If d_M > 2.5: escalation_flag = True               │
│          Meaning: patient is an outlier from all archetypes │
│          → fully personalized assessment required           │
│ Rules:   Escalation threshold 2.5 corresponds to ~99th      │
│          percentile in multivariate normal                  │
│          Escalated patients get extended uncertainty report  │
└─────────────────────────────────────────────────────────────┘

Validation gate: K ≥ 2; all patients assigned; Mahalanobis computed;
escalation_flag set for outliers.

## F5 — Research Analytics (Evidence Gap Prioritization)
Field        Value
ID           ALG-F5
Type         COMPOSITE
Purpose      Identify highest-priority evidence gaps, generate study designs,
             and compute Expected Value of Sample Information (EVSI) to guide
             future research investment
Phase        PHASE_F
Paper §      §2.22 (Evidence Gaps), §2.13 (Chain-vs-Direct)

Input:  edges_v1 (evidence counts, SE_eff), chain_direct_validation (from VAL-01)
Output: ResearchOutputPackage → SYS_RUNTIME

Sub-steps:
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F5a — Discovery Score Computation                 │
│ Purpose: Rank edges by research value = impact × uncertainty│
│ Input:   edges_v1 (β, SE_eff), PatientState (elasticities) │
│ Output:  discovery_scores: dict[edge → score]               │
│ Logic:                                                      │
│   discovery_score(e) = |elasticity(e)| × SE_eff(e) [F-6]   │
│                                                             │
│   where elasticity(e) = ∂θ_target/∂β_e × (β_e/θ_target)   │
│                                                             │
│   Interpretation: high elasticity = edge matters to outcome │
│                   high SE_eff = edge is uncertain            │
│   Product = "would learning about this edge change things?" │
│                                                             │
│ Rules:   Sort descending. Top 10 edges form evidence gap map│
│          Edges with k=0 automatically get HIGH priority     │
│          (8 edgeless nodes from ALG-A5d)                    │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F5b — Chain-vs-Direct Discrepancy Flagging        │
│ Purpose: Identify pathways where indirect ≠ direct effects  │
│          suggesting missing mediators or confounders         │
│ Input:   chain_direct_validation results (from VAL-01)      │
│ Output:  missing_pathway_hypotheses                         │
│ Logic:   For each of 10 tested chains (from §2.13):         │
│   Z = |β_chain − β_direct| / √(SE²_chain + SE²_direct)    │
│   If Z > 1.5: flag as discrepancy                           │
│   Classification:                                           │
│     Z < 1.5 → PASS (no issue)                              │
│     1.5–2.0 → MILD (1.2× SE inflation)                     │
│     2.0–3.0 → MODERATE (1.5× SE inflation)                 │
│     Z ≥ 3.0 → SEVERE (exclude or 2.0× SE)                  │
│   Discrepancies suggest: missing edge, unmodeled mediator,  │
│   or confounding bias                                       │
│ Rules:   Severe discrepancies → mandatory disclosure in     │
│          clinical output + research gap flag                 │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F5c — Study Design Generator                      │
│ Purpose: For top evidence gaps, generate recommended study  │
│          designs                                            │
│ Input:   Top 10 edges from F5a                              │
│ Output:  study_designs: list[{edge, N, design, endpoint}]   │
│ Logic:   For each gap edge:                                 │
│   - Required N = (z_α/2 + z_β)² × (2σ²) / δ²              │
│     where δ = MID × elasticity (clinically meaningful Δ)    │
│     α = 0.05, β = 0.20 (80% power)                         │
│   - Optimal design hierarchy:                               │
│     RCT (if ethical) > Cohort > Cross-sectional             │
│   - Primary endpoint = node most sensitive to edge          │
│   - Recommended instrument from instruments_v1              │
│ Rules:   N capped at 500 (practical feasibility)            │
│          If N > 500: suggest collaborative multi-site       │
│          Cancer-specific population preferred                │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SUB-STEP: F5d — EVSI Computation                            │
│ Purpose: Estimate how much a proposed study would improve   │
│          clinical decision-making                           │
│ Input:   study_designs from F5c, current MC simulation      │
│ Output:  EVSI per study: expected SAFE improvement          │
│ Logic:   Nested Monte Carlo:                                │
│   Outer loop (M=500): simulate study outcome d_j            │
│     - Draw β_e | study_j from posterior predictive          │
│     Inner loop (N=1000): re-run MC with updated β_e        │
│       - Compute max_a SAFE(a | d_j)                         │
│     EVSI(j) = E_d[max_a SAFE(a|d_j)] −                     │
│               max_a SAFE(a|current)    [Formula F-7]         │
│                                                             │
│   Interpretation: EVSI > 0.1 SD → study is "worth doing"   │
│                   EVSI > 0.3 SD → high-value study          │
│                   EVSI < 0.05 SD → marginal value           │
│ Rules:   Computationally expensive (500 × 1000 MC draws)    │
│          Run asynchronously; cache results                   │
│          Report as "expected improvement in best SAFE score" │
└─────────────────────────────────────────────────────────────┘

Validation gate: Discovery scores computed for all edges; study designs
for top 10; EVSI for top 5; chain-vs-direct flags applied.

───────────────────────────────────────────────────────────────────────────
6. BOUNDARY TABLES

### Tables Read (Entry)
Table ID                  Columns Used                              Purpose
nodes_v1                  node_id, domain, layer, observable        Subdomain extraction, severity
edges_v1                  edge_param_id, beta, SE_eff, k,          Elasticity, discovery score
                          P_inclusion, tau_squared
instruments_v1            instrument_id, alpha_k, b_k, target_node Measurement variance
modifier_registry_v1      (none directly — effects pre-applied)     (context only)
synergy_registry_v1       (none directly — synergies pre-computed)  (context only)
population_archetypes_v1  archetype_id, centroid, covariance        Prior archetypes (if exists)

### Tables Written (Exit)
Table ID                    Columns Written                         Write Condition
intervention_rankings_v1    action_id, SAFE_A, SAFE_B, rank,       Per recommendation_run
                            P_rank1, stability_class, CrI
variance_decomposition_v1   run_id, literature_pct, measurement_pct Per recommendation_run
                            structural_pct, proxy_pct, missing_pct
evidence_gaps_v1            edge_id, discovery_score, EVSI,         Per recommendation_run
                            study_design, recommended_N             (research mode only)
population_archetypes_v1    archetype_id, centroid, covariance,     Updated when new patient
                            archetype_size, default_ranking          added to pool

───────────────────────────────────────────────────────────────────────────
7. GATES & CHECKPOINTS

Gate ID  Position    Condition                                    Pass        Fail            Severity
F-G1     After F1    crci_composite ∈ [−5,5]; percentile valid   → F2        WARN: clamp     LOW
F-G2     After F2    Σ P(rank₁) = 1.0; stability classified     → F3        ABORT: MC fail  HIGH
F-G3     After F3    5 components sum ≈ total; all ≥ 0           → F4        WARN: recompute MEDIUM
F-G4     After F4    K ≥ 2; all assigned; Mahalanobis computed   → F5        WARN: skip pop  LOW
F-G5     After F5    Discovery scores computed; ≥1 study design  → output    WARN: skip res  LOW

───────────────────────────────────────────────────────────────────────────
8. CHAIN-LEVEL ASSUMPTIONS

#  Assumption                                        Impact if Violated              Paper §
1  IVW compositing of subdomains is appropriate      Wrong composite if domains      §2.20
   (domains are reasonably independent)              strongly correlated
2  10,000 MC draws sufficient for rank stability     False stability classification  §2.19
                                                     if draws insufficient
3  GMM captures population structure                 Archetypes meaningless if       §4.5
                                                     data non-Gaussian mixtures
4  EVSI nested MC (500×1000) gives adequate          EVSI estimates noisy with       §2.22
   precision for study prioritization                small outer sample
5  σ²_struct was static 0.25 in v1.0; now per-edge   RESOLVED in v2.0: EX-P4-MA     §2.21
   annotation-informed (0.25 base, ceiling 0.50)     computes from annotations.
                                                     Default 0.25 if no annotations.
6  Severity weights (1.0/1.5/2.0) are clinically    Composite biased if weights     §2.20
   appropriate step-function approximations          are wrong

───────────────────────────────────────────────────────────────────────────
9. FORMULA REGISTRY

ID    Equation                                          Variables                   Paper §  Status
F-1   CRCI = Σ_d (w_d·z_d) / Σ_d w_d                  w_d=1/σ²_d, z_d=subdomain   §2.20    Canonical
F-2   Score = Φ(−z) × 100                              z=composite, Φ=normal CDF   §2.20    Canonical
F-3   Q = Σ_d w_d(z_d − CRCI)²                         Cochran's Q heterogeneity   §2.20    Canonical
F-4   P(rank₁=a) = (1/N)Σ_m 𝟙[rank₁^(m)=a]           N=10,000 draws              §2.19    Canonical
F-5   ΔVar = Σ_{unobs} Cov(Y,X_i)²/Var(X_i)           Variance reduction formula   §2.8     Canonical
F-6   discovery = |elasticity(e)| × SE_eff(e)          Impact × uncertainty         §2.22    Canonical
F-7   EVSI = E_d[max SAFE(a|d)] − max SAFE(a|curr)    Nested MC estimate           §2.22    Canonical
F-8   N = (z_α/2+z_β)²×2σ²/δ²                         Power calculation            §2.22    Canonical
F-9   d_M = √((x−μ)ᵀΣ⁻¹(x−μ))                        Mahalanobis distance         §4.5     Canonical
F-10  BIC = −2ln(L) + K·ln(n)                          Model selection for GMM      §4.5     Canonical

═══════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════
                    PART 3: TIER 3 — SUBSYSTEM CARDS
                    (31 subsystems across 6 chains)
═══════════════════════════════════════════════════════════════════════════

Each subsystem card below is derived from the canonical chain card detail
above. The chain cards contain the FULL sub-step boxes; the subsystem cards
here provide the structured interface contracts, validation gates, and
cross-chain connection maps needed for implementation.

───────────────────────────────────────────────────────────────────────────
CHAIN ALG-A: Graph Assembly (5 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-A1 — Node Hierarchy Assembly
1. IDENTITY
   Subsystem ID:   ALG-A1
   Chain:          ALG-A
   System:         SYS_ALGORITHM
   Name:           Node Hierarchy Assembly
   Purpose:        Load 63 nodes from registry, assign layers/domains/observability, compute topological order
   Type:           ATOMIC
   Phase:          PHASE_A (Build-time)
   Data Flow Role: ROLE_TRANSFORMER
   Consumer:       FOR_FRAMEWORK
   Research Phase: RESEARCH_TOPOLOGY
   Paper §:        §2.1, §2.2

2. INTERFACE CONTRACT
   Inputs:
   | Source | Field | Type | Required | Notes |
   |--------|-------|------|----------|-------|
   | nodes_v1 | id, layer, domain, orientation, observable | CSV/63 rows | YES | Full node registry |

   Outputs:
   | Field | Type | Destination | Notes |
   |-------|------|-------------|-------|
   | NodeMap.nodes | list[NodeDef] (63) | A2, A3, A5 | Complete node definitions |
   | NodeMap.layer_assignment | dict[node_id→int 0-6] | A2, A5 | 7 hierarchical layers |
   | NodeMap.domain_assignment | dict[node_id→enum(11)] | A5 | 11 clinical domains |
   | NodeMap.observability | dict[node_id→bool] | A5 | 48 observable, 15 latent |
   | NodeMap.topological_order | list[node_id] | A2 | Kahn's algorithm output |

3. PROCESS
   Steps: Load → Validate 63 nodes → Assign layers (verify DAG) → Assign domains → Classify observable/latent → Compute topological order (Kahn's) → Map orientation
   Key Formula: Kahn's algorithm for topological sort (standard)
   Decision Logic: node in layer L must have all parents in layer L' < L

4. VALIDATION GATE
   | Check | Condition | On Fail |
   |-------|-----------|---------|
   | Node count | == 63 | ABORT |
   | Layer consistency | All parents in lower layer | ABORT |
   | No orphans | All nodes assigned domain + layer | ABORT |
   | Acyclicity | Kahn's completes without remainder | ABORT |

5. CONNECTIONS
   Within-Chain: → A2 (via NodeMap), → A3 (via NodeMap), → A5 (via NodeMap)
   Cross-Chain: Reads nodes_v1 (Class A, human-curated)

## ALG-A2 — Edge Matrix Construction
1. IDENTITY
   Subsystem ID:   ALG-A2
   Chain:          ALG-A
   System:         SYS_ALGORITHM
   Name:           Edge Matrix Construction
   Purpose:        Initialize B ∈ ℝ^{63×63} sparse matrix with 118 entries, tag functional forms
   Type:           ATOMIC
   Phase:          PHASE_A
   Data Flow Role: ROLE_TRANSFORMER
   Consumer:       FOR_FRAMEWORK
   Research Phase: RESEARCH_TOPOLOGY
   Paper §:        §2.1, §2.3, §2.6

2. INTERFACE CONTRACT
   Inputs:
   | Source | Field | Type | Required |
   |--------|-------|------|----------|
   | NodeMap | topological_order, layer_assignment | from A1 | YES |
   | edges_v1 | source, target, functional_form, claim_level, E_max, EC₅₀, h | 118 rows | YES |

   Outputs:
   | Field | Type | Destination |
   |-------|------|-------------|
   | B_struct | ℝ^{63×63} sparse | A3, A4 |
   | functional_forms | dict[edge_id→enum] | A5 |
   | hill_params | dict[edge_id→{E_max,EC₅₀,h}] | A5 |
   | edge_claim_levels | dict[edge_id→enum] | A5 |
   | acyclicity_verified | bool | validation |

3. PROCESS
   Steps: Load 118 edges → Verify endpoints exist → Verify DAG constraint (source_layer < target_layer except feedback) → Set B[source,target] = placeholder → Record functional forms (54 linear, 34 Hill/Emax) → Load Hill params (with fallback) → Verify acyclicity
   Key Formulas:
   | ID | Equation | Paper § |
   |----|----------|---------|
   | A2-1 | f(x) = E_max·|x|^h/(EC₅₀^h+|x|^h)·sign(x) | §2.6 |
   | A2-2 | density = |E|/(|V|·(|V|−1)) = 118/3906 = 0.030 | §2.1 |

   ┌─────────────────────────────────────────────────────────────┐
   │ DECISION LOGIC: Hill/Emax Parameter Loading (Gap 1 Fix)     │
   │                                                             │
   │ FOR each edge e with functional_form = hill:                │
   │   IF hill_params(e) = {E_max, EC₅₀, h} all non-NULL:      │
   │     → Load normally. Standard path.                         │
   │                                                             │
   │   ELIF edges_v1(e).fallback_form = linear:                  │
   │     → DOWNGRADE to linear.                                  │
   │       Set functional_form(e) = linear                       │
   │       Use β_mean as constant slope                          │
   │       Log to edge_param_builds_v1:                          │
   │         compilation_method = "hill_to_linear_downgrade"     │
   │       Log WARNING: "Edge {id}: Hill→linear downgrade,       │
   │         saturation effects not modeled"                     │
   │       RATIONALE: Linear = tangent at low doses, a           │
   │         conservative first-order approximation.             │
   │         54/118 edges are already linear — one more is       │
   │         architecturally consistent.                         │
   │                                                             │
   │   ELIF external calibration bounds exist                    │
   │        (e.g., EC₅₀ range from cited source):               │
   │     → Use midpoint of calibration range with wide SE.       │
   │       Example: §2.6 exercise EC₅₀ = 625 MET-min/wk        │
   │         (midpoint of 500-750 from Gallardo-Gómez 2022)     │
   │       Set SE(EC₅₀) = range_width / 4                       │
   │       Log: compilation_method = "external_calibration"      │
   │                                                             │
   │   ELSE (fallback_form = NULL, no calibration):              │
   │     → ABORT: "Edge {id} requires Hill params but            │
   │       dose_bridges_v1 has no complete entry and no          │
   │       fallback_form is specified. Run COMPILE-INT           │
   │       or set fallback_form = linear."                       │
   │                                                             │
   │ SCHEMA ADDITION: edges_v1.fallback_form                     │
   │   Type: ENUM {linear, NULL}                                 │
   │   Nullable: YES                                             │
   │   Purpose: "If Hill parameters unavailable, is linear       │
   │     approximation acceptable?"                              │
   │   Default: NULL (require explicit opt-in to fallback)       │
   └─────────────────────────────────────────────────────────────┘

4. VALIDATION GATE
   | Check | Condition | On Fail |
   |-------|-----------|---------|
   | Edge count | == 118 | ABORT |
   | Acyclicity | Verified (modulo feedback) | ABORT |
   | All endpoints | Valid node_ids in NodeMap | ABORT |
   | Connected + edgeless | 55 + 8 = 63 | WARN |
   | Hill params | All hill edges: params complete OR fallback_form set | ABORT (see decision logic above) |

5. CONNECTIONS
   Within-Chain: A1→A2 (NodeMap), A2→A3 (B_skeleton), A2→A4 (B_skeleton)
   Cross-Chain: Reads edges_v1 (Class C, compiled from extraction), edge_param_builds_v1 (audit writes)

## ALG-A3 — Residual Covariance Assembly
1. IDENTITY
   Subsystem ID:   ALG-A3
   Chain:          ALG-A
   System:         SYS_ALGORITHM
   Name:           Residual Covariance Assembly
   Purpose:        Build block-diagonal D matrix with 8 empirical off-diagonal correlation pairs
   Type:           ATOMIC
   Phase:          PHASE_A
   Paper §:        §2.6, §2.17.2

2. INTERFACE CONTRACT
   Inputs:
   | Source | Field | Type | Required |
   |--------|-------|------|----------|
   | B_skeleton | B_struct | ℝ^{63×63} | YES |
   | correlation_registry_v1 | node_i, node_j, rho, source | 8 rows | YES |

   Outputs:
   | Field | Type | Destination |
   |-------|------|-------------|
   | D | ℝ^{63×63} block-diagonal | A4 |
   | residual_variances | ℝ^{63} | A4, A5 |
   | correlation_pairs | 8×{i,j,ρ,source} | A5 |

3. PROCESS
   Key Formulas:
   | ID | Equation | Paper § |
   |----|----------|---------|
   | A3-1 | R²_i = Σ_j β²_{ji} | §2.6 |
   | A3-2 | σ²_{ε,i} = max(1 − R²_i, 0.05) | §2.6 |
   | A3-3 | D = blockdiag(D_ind, Σ_inflam, Σ_neuro) | §2.17.2 |

   8 correlation pairs: IL-6↔TNF-α(0.65), IL-6↔CRP(0.72), TNF-α↔CRP(0.58),
   BDNF↔IL-6(−0.35), Cortisol↔IL-6(0.28), BDNF↔Cortisol(−0.22),
   MDA↔IL-6(0.38)[VERIFY], NfL↔TNF-α(0.31)

4. VALIDATION GATE: D positive-definite; all ρ ∈ (−1,1); 8 pairs inserted
5. RESEARCH DEPENDENCIES: Zhao 2025 MDA↔IL-6 UNVERIFIED; BDNF↔cortisol ESTIMATED
6. CONNECTIONS: A2→A3 (B_skeleton), A3→A4 (D_matrix); Reads correlation_registry_v1

## ALG-A4 — Precision Matrix Assembly
1. IDENTITY
   Subsystem ID:   ALG-A4
   Chain:          ALG-A
   System:         SYS_ALGORITHM
   Name:           Precision Matrix Assembly
   Purpose:        Compute Λ = (I−B)ᵀD⁻¹(I−B), verify positive-definiteness and stability
   Type:           ATOMIC
   Phase:          PHASE_A
   Paper §:        §2.6

2. INTERFACE CONTRACT
   Inputs: B_skeleton (from A2), D_matrix (from A3)
   Outputs: Λ_structure (ℝ^{63×63}), condition_number, spectral_radius_B → A5

3. PROCESS
   Key Formulas:
   | ID | Equation | Paper § |
   |----|----------|---------|
   | A4-1 | Λ = (I−B)ᵀ D⁻¹ (I−B) | §2.6 |
   | A4-2 | κ(Λ) = λ_max/λ_min | stability |
   | A4-3 | ρ(B) = max|eigenvalue(B)| = 0.41 | §2.6 |

4. VALIDATION GATE: Λ positive-definite (Cholesky); ρ(B) < 1; κ(Λ) < 10¹⁰
5. CONNECTIONS: A2→A4, A3→A4, A4→A5; Pure computation, no table reads

## ALG-A5 — Pathway & Latent Structure Registration
1. IDENTITY
   Subsystem ID:   ALG-A5
   Chain:          ALG-A
   System:         SYS_ALGORITHM
   Name:           Pathway & Latent Structure Registration
   Purpose:        Register 20 pathways, 15 latent-proxy pairs, 5 feedback loops, 8 edgeless nodes
   Type:           COMPOSITE (4 sub-steps: A5a-A5d)
   Phase:          PHASE_A
   Paper §:        §2.3, §2.17

2. INTERFACE CONTRACT
   Inputs: All prior states + instruments_v1 + feedback_loops_v1
   Outputs: GraphObject (complete) → ALG-B

3. PROCESS — see chain card §5 sub-step boxes A5a through A5d:
   - A5a: Pathway Map (20 pathways: 15 Tier1 + 5 Tier2)
   - A5b: Latent-Proxy Registration (15 nodes, R² validity tiers)
   - A5c: Feedback Loop Verification (5 loops, gain < 1)
   - A5d: Edgeless Node Identification (8 nodes, research gaps)

4. VALIDATION GATE: 20 pathways; 15 proxies; 5 loops stable; GraphObject complete
5. CONNECTIONS: All A1-A4→A5; A5→ALG-B (GraphObject); Reads instruments_v1, feedback_loops_v1, pathway_map_v1


───────────────────────────────────────────────────────────────────────────
CHAIN ALG-B: Edge Parameterization (7 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-B1 — Evidence Pooling & Aggregation
   ID: ALG-B1 | Type: COMPOSITE | Phase: PHASE_B | Paper §: §2.9
   Purpose: Pool evidence per edge using IVW/random-effects, select aggregation method
   Inputs: GraphObject (from ALG-A), edge_evidence_v1 (Class B)
   Outputs: AggregatedEstimates (β̂_pooled, SE_pooled, method per edge)
   Sub-steps: B1a (Evidence Loading), B1b (Aggregation Decision Tree: k=0→BLOCKED,
     k=1→DIRECT, k≥2 w/ I²<50%→IVW_FIXED, I²50-75%→STRATIFIED or IVW_RANDOM,
     I²≥75%→SINGLE_BEST), B1c (Precision Caps: cross-sect 30% best RCT, animal 10%)
   Formulas: B-1 (IVW: β̂=Σw_i·β_i/Σw_i, w_i=1/SE²_i), B-2 (I²=(Q−(k−1))/Q)
   Validation: Every edge has method assigned; no infinite weights
   Connections: ALG-A→B1 (GraphObject); Reads edge_evidence_v1

## ALG-B2 — Seven-Layer SE Calibration
   ID: ALG-B2 | Type: COMPOSITE | Phase: PHASE_B | Paper §: §2.9
   Purpose: Apply 7 heterogeneity adjustments to calibrate SE_eff per edge
   Inputs: AggregatedEstimates (from B1)
   Outputs: CalibratedSE (SE_eff per edge)
   7 Layers (sequential multiplication):
     L1: Study design (Large RCT 1.0× → Expert 6.0×)
     L2: Transportability/scope (w_scope = weighted match, floor 0.3)
     L3: Statistical heterogeneity (I², τ² if random-effects)
     L4: Scale compatibility (cancer-specific validation: 1.0×–1.5×)
     L5: Quality/GRADE (High 1.0×, Moderate 1.25×, Low 1.5×, Very Low 2.0×)
     L6: Temporal decay (w(t) = e^{−0.05t}, >90 days excluded)
     L7: Freshness (1.5%/yr decay, floor 0.70)
   Formula: B-3 (SE_eff = √[(SE_pooled·m_claim·m_GRADE·m_temporal)² + σ²_struct + τ²·𝟙] / (max(w_scope,0.3)·w_fresh))
   σ²_struct source: edges_v1.sigma_sq_structural (per-edge, default 0.25 if NULL; annotation-informed in v2.0)
   Validation: SE_eff > SE_pooled for every edge (calibration only inflates)
   Connections: B1→B2; Reads edge_evidence_v1 (study metadata)

## ALG-B3 — Prior Selection
   ID: ALG-B3 | Type: COMPOSITE | Phase: PHASE_B | Paper §: §2.10
   Purpose: Select prior type per edge based on evidence count and source quality
   Inputs: CalibratedSE (from B2), edge_evidence_v1
   Outputs: PriorAssignments (prior_type, prior_params per edge)
   Decision tree:
     k ≥ 5, consistent → RobustMAP (shrunk MLE with outlier downweight)
     k = 2–4 → Commensurate (adaptive borrowing from external data)
     k = 1 → Power prior (discount: RCT-same 0.80, RCT-diff 0.50, Cohort 0.40, Obs 0.30, Animal 0.15, Mech 0.05)
     k = 0 + mechanistic chain → MechanisticSynthesis (product of constituent edges)
     k = 0, no chain → StructuralPlaceholder (N(0,1), P_inclusion = 0.38)
   4-level fallback: Exact context(1.0×) → Cancer-type(1.2×) → General cancer(1.5×) → Uninformative(2.0×)
   Formulas: B-4 (Power prior), B-5 (Commensurate prior)
   Validation: Every edge has prior; audit log written to prior_selection_log_v1
   Connections: B2→B3; Reads context_matched_priors_v1; Writes prior_selection_log_v1

## ALG-B4 — Structural Inclusion Probability
   ID: ALG-B4 | Type: ATOMIC | Phase: PHASE_B | Paper §: §2.12
   Purpose: Compute P_inclusion per edge for stochastic edge inclusion in MC
   Inputs: PriorAssignments (from B3), edge metadata
   Outputs: InclusionProbabilities (P_inclusion per edge)
   Formula: B-6 (P_incl = logistic(−0.5 + 1.2·ln(k+1) + 0.4Z + 0.6·𝟙_RCT))
   Calibration targets: k=0,Z=0 → P≈0.38; k=3+moderate → P≈0.80
   Validation: All P ∈ [0.05, 0.99]; mean P ∈ [0.4, 0.8]
   Connections: B3→B4

## ALG-B5 — Diminishing Returns & Attenuation
   ID: ALG-B5 | Type: ATOMIC | Phase: PHASE_B | Paper §: §2.9
   Purpose: Apply diminishing returns for large k and causal attenuation
   Inputs: CalibratedSE + InclusionProb (from B2, B4)
   Outputs: AttenuatedEstimates
   Formulas: B-7 (DR: w_base × 1/(1+0.3·ln(k))), B-8 (Attenuation: Identified 1.00, Partial 0.85, Plausible 0.70, Unidentified 0.50)
   Validation: All β attenuated ≤ original; all weights ≤ w_base
   Connections: B2→B5, B4→B5

## ALG-B6 — Chain-vs-Direct Validation
   ID: ALG-B6 | Type: COMPOSITE | Phase: PHASE_B | Paper §: §2.13
   Purpose: Compare indirect (chain) vs direct edge estimates for 10 tested chains
   Inputs: B_parameterized (all edges with β̂, SE_eff)
   Outputs: ValidationResults (Z-scores, SE inflation factors)
   Logic: Z = |β_chain − β_direct|/√(SE²_chain + SE²_direct)
   Classification: Z<1.5→PASS, 1.5-2.0→MILD(1.2×SE), 2.0-3.0→MODERATE(1.5×SE), ≥3.0→SEVERE(exclude/2.0×SE)
   Formula: B-9 (Z-test for chain-vs-direct)
   Validation: All 10 chains tested; inflated SEs applied where needed
   Connections: Uses all B1-B5 outputs; Results → ALG-F5 (research analytics)

## ALG-B7 — Final Edge Parameter Assembly
   ID: ALG-B7 | Type: ATOMIC | Phase: PHASE_B | Paper §: §2.9, §2.10
   Purpose: Assemble final β̂, SE_eff, P_inclusion, prior_type per edge into edges_v1
   Inputs: All B1-B6 outputs
   Outputs: Writes to edges_v1 (118 rows updated with final parameters)
   Formula: B-10 (Final assembly: edges_v1.beta = β̂_attenuated, edges_v1.SE_eff = SE_calibrated)
   Validation: 118 edges written; no NaN values; all SEs > 0
   Connections: All B1-B6→B7; Writes edges_v1 (Class C); Output → ALG-C (reads edges_v1)


───────────────────────────────────────────────────────────────────────────
CHAIN ALG-C: Patient State Inference (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-C1 — Observation Loading & Instrument Mapping
   ID: ALG-C1 | Type: COMPOSITE | Phase: PHASE_C (Runtime) | Paper §: §2.7
   Purpose: Load patient test scores, map to instruments, compute noise model per observation
   Inputs: Patient observations (from SYS_RUNTIME), instruments_v1 (23 instruments)
   Outputs: MappedObservations (y_k, a_k, b_k, σ²_{y,k}, node_i per observation)
   Logic: For each test score y_k:
     - Look up instrument k in instruments_v1 → get a_k (intercept), b_k (loading), α_k (reliability)
     - Compute noise: σ²_{y,k} = b²_k × (1−α_k)/α_k [Formula C-1]
     - Map to target node_i
     - Verify instrument validated for cancer population (SE multiplier from A5b)
   Validation: All observations mapped; no unknown instruments; α_k > 0 for all
   Connections: SYS_RUNTIME→C1; Reads instruments_v1; C1→C2

## ALG-C2 — Information-Form Bayesian Update
   ID: ALG-C2 | Type: COMPOSITE | Phase: PHASE_C | Paper §: §2.8
   Purpose: Update 63-node posterior via information-form sequential updates
   Inputs: MappedObservations (from C1), GraphObject.Λ_structure (from ALG-A), edges_v1 (β values from ALG-B)
   Outputs: PatientState (posterior_means μ_post, posterior_precisions Λ_post)
   Logic: Three fusion levels:
     L1 (Build-time): Λ_prior = (I−B)ᵀ D⁻¹ (I−B) with β from edges_v1
     L2 (Per-observation): Λ_post += (b²_k/σ²_{y,k})·e_i·e_iᵀ ; η_post += (b_k(y_k−a_k)/σ²_{y,k})·e_i [C-2, C-3]
     L3 (Multi-instrument same node): Aggregate information from multiple tests targeting same node
   Formulas:
   | ID | Equation | Paper § |
   |----|----------|---------|
   | C-2 | Λ_post = Λ_prior + Σ_k (b²_k/σ²_{y,k})·e_i·e_iᵀ | §2.8 |
   | C-3 | η_post = η_prior + Σ_k (b_k(y_k−a_k)/σ²_{y,k})·e_i | §2.8 |
   | C-4 | μ_post = Λ_post⁻¹ · η_post | §2.8 |
   Validation: Λ_post positive-definite; μ_post ∈ [−5, 5] per node; information gain > 0
   Connections: C1→C2; Reads edges_v1 (β from ALG-B), GraphObject.Λ_structure (from ALG-A)

## ALG-C3 — Effect Modifier Application
   ID: ALG-C3 | Type: COMPOSITE | Phase: PHASE_C | Paper §: §2.15
   Purpose: Apply 109 patient-specific effect modifiers to edge weights
   Inputs: PatientState (from C2), modifier_registry_v1 (109 rules), patient demographics
   Outputs: ModifiedPatientState (adjusted posterior with modifier effects)
   Logic: For each applicable modifier rule:
     - Evaluate condition (e.g., age > 65, education < 12yr, cancer_type = breast)
     - Compute multiplier m ∈ [0.7, 1.5] (individual guardrail)
     - Apply: β_modified = β × Π(applicable modifiers)
     - Cumulative product guardrail: [0.5, 2.0]
     - Key modifier: cognitive reserve m_CR ∈ [0.7, 1.3] (>16yr ed → 0.7; <12yr → 1.3)
   Validation: All multipliers within guardrails; cumulative within [0.5, 2.0]
   Connections: C2→C3; Reads modifier_registry_v1; C3→C4

## ALG-C4 — Pathway Activation Analysis
   ID: ALG-C4 | Type: ATOMIC | Phase: PHASE_C | Paper §: §2.3
   Purpose: Compute per-pathway activation z-scores and dysregulation flags
   Inputs: ModifiedPatientState (from C3), pathway_map_v1 (20 pathways)
   Outputs: PathwayProfile (20 pathways × activation z-score + dysregulation flag)
   Logic: For each pathway p:
     - Collect constituent node z-scores from posterior
     - pathway_activation(p) = mean(z_nodes_in_p) weighted by edge strengths
     - dysregulation flag: |activation| > τ_P (default 0.5 SD, sensitive 0.3 SD)
   Validation: All 20 pathways scored; dysregulation flags consistent with node z-scores
   Connections: C3→C4; Reads pathway_map_v1; C4→ALG-D (pathway profiles for simulation)

───────────────────────────────────────────────────────────────────────────
CHAIN ALG-D: Intervention Simulation (6 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-D1 — Intervention Candidate Selection
   ID: ALG-D1 | Type: COMPOSITE | Phase: PHASE_D (Runtime) | Paper §: §2.14
   Purpose: Select candidate interventions based on patient profile, safety filtering,
            causal language gate, and rankability pre-filter
   Inputs: PatientState (from ALG-C), action_catalog_v1, PathwayProfile,
           contraindication_rules_v1, contraindication_escalation_policy_v1
   Outputs: CandidateSet (safety-filtered, rankability-scored interventions)

   Logic: For each intervention in action_catalog_v1:
     Step 1: Check eligibility (cancer_type compatibility)
     Step 2: Safety filtering (contraindications — see below)
     Step 3: Assign causal language level: causal_supported > associational_only > model_implied
     Step 4: Path-level claim = weakest constituent edge claim
     Step 5: Rankability pre-filter (see below)
     Step 6: Filter: exclude model_implied unless user opts in

   ┌─────────────────────────────────────────────────────────────┐
   │ SAFETY FILTERING: Contraindication Evaluation (Gap 3 Fix)   │
   │                                                             │
   │ FOR each (action, patient) pair:                            │
   │   eval_results = evaluate_all_matching_rules(                │
   │     action, patient, contraindication_rules_v1)             │
   │                                                             │
   │   Apply severity per contraindication_escalation_policy_v1: │
   │     block    → EXCLUDE action entirely                      │
   │     escalate → Flag for mandatory clinician review           │
   │     soft_warn → Include with advisory note                  │
   │                                                             │
   │ POST-EVALUATION META-CHECK (the catch-all safety net):      │
   │                                                             │
   │   IF len(eval_results) == 0                                 │
   │      AND patient.has_risk_factors():                        │
   │     → Evaluate CATCH_ZERO_MATCH_RISKY rule:                 │
   │       condition: "eval_count = 0 AND (has_active_treatment  │
   │         OR comorbidity_count ≥ 3 OR age > 80)"             │
   │       severity: soft_warn                                   │
   │       rationale: "No specific safety rules evaluated for    │
   │         this action-patient combination, but patient has     │
   │         clinical risk factors suggesting caution."          │
   │                                                             │
   │   ADDITIONAL CATCH-ALL RULES (3 rows in contraindication_   │
   │   rules_v1):                                                │
   │                                                             │
   │   CATCH_ACTIVE_TREATMENT:                                   │
   │     condition: treatment_phase IN ('active_chemo',          │
   │       'active_radiation', 'active_immunotherapy')           │
   │       AND toxicity_grade_max ≥ 2                            │
   │     applies_to: ALL actions with intensity > 'light'        │
   │     severity: escalate (→ clinician review)                 │
   │     rationale: "Patient on active treatment with Grade 2+   │
   │       toxicity. Rule base may not cover all interactions."  │
   │                                                             │
   │   CATCH_RARE_CANCER:                                        │
   │     condition: cancer_type NOT IN ('breast', 'colorectal',  │
   │       'lung', 'prostate', 'hematological')                  │
   │       AND action.intensity > 'light'                        │
   │     severity: soft_warn                                     │
   │     rationale: "Cancer type has limited representation in   │
   │       evidence base. Safety rules may be incomplete."       │
   │                                                             │
   │   CATCH_ZERO_MATCH_RISKY:                                   │
   │     condition: eval_count = 0 AND (has_active_treatment     │
   │       OR comorbidity_count ≥ 3 OR age > 80)                │
   │     severity: soft_warn                                     │
   │     rationale: "No specific safety rules evaluated.         │
   │       Patient risk factors suggest clinician should review."│
   │                                                             │
   │ SCHEMA: No changes needed.                                  │
   │   contraindication_rules_v1 already has condition_expression│
   │   (18-col spec), severity ENUM (block/escalate/soft_warn),  │
   │   escalation_id FK. Just 3 new rows.                        │
   │                                                             │
   │ Write all eval results to contraindication_eval_trace_v1.   │
   └─────────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────────┐
   │ RANKABILITY PRE-FILTER: 4-Gate Sequential (Gap 4 Fix)       │
   │ (Paper §2.16.2)                                             │
   │                                                             │
   │ FOR each candidate intervention a:                          │
   │   critical_path_edges = get_primary_pathway_edges(a)        │
   │                                                             │
   │   Compute per-edge rankability:                             │
   │   R_e = 𝟙[provenance_exists]                               │
   │       × 𝟙[scale_compatible]  (from EX-P3-L4)              │
   │       × min(w_scope, 1.0)    (from EX-P3-L2)              │
   │       × P_inclusion           (from ALG-B4)                │
   │                                                             │
   │   Intervention-level rankability:                           │
   │   R_intervention = min(R_e for e in critical_path_edges)    │
   │                                                             │
   │   Classification:                                           │
   │     R ≥ 0.50 → INCLUDE normally                             │
   │       rankability_status = "full"                           │
   │     0.25 ≤ R < 0.50 → INCLUDE with caveat                  │
   │       rankability_status = "limited"                        │
   │       Output: "Limited evidence base for this intervention" │
   │     R < 0.25 → EXCLUDE from ranking                         │
   │       rankability_status = "excluded"                       │
   │       Output: "Insufficient evidence to rank. Key gap:      │
   │         edge {weakest_edge_id}"                             │
   │                                                             │
   │ OUTPUT: decision_trace_v1 gets:                             │
   │   rankability_score: REAL [0,1]                             │
   │   rankability_status: ENUM {full, limited, excluded}        │
   │                                                             │
   │ CLINICAL EXAMPLE:                                           │
   │   Cognitive training: all pathway edges have P_incl > 0.6,  │
   │   w_scope > 0.8, scale_compatible = true → R ≈ 0.65 → full │
   │                                                             │
   │   Acupuncture: primary edge has P_incl = 0.15, w_scope =   │
   │   0.4, no RCT → R ≈ 0.06 → excluded, with message:        │
   │   "Excluded from ranking: insufficient evidence for         │
   │   acupuncture→attention pathway"                            │
   └─────────────────────────────────────────────────────────────┘

   Validation: ≥1 candidate selected; claim levels assigned; all safety evals logged;
               rankability computed for all candidates
   Connections: ALG-C→D1; Reads action_catalog_v1, contraindication_rules_v1,
                contraindication_escalation_policy_v1, edges_v1;
                Writes contraindication_eval_trace_v1, decision_trace_v1; D1→D2

## ALG-D2 — Monte Carlo Sampling Engine
   ID: ALG-D2 | Type: COMPOSITE | Phase: PHASE_D | Paper §: §2.12
   Purpose: Generate N=10,000 MC draws with stochastic edge inclusion and parameter sampling
   Inputs: CandidateSet (from D1), edges_v1 (β, SE_eff, P_inclusion)
   Outputs: MCDraws (10,000 × {β_vector, included_edges})
   Logic: For each draw m = 1..10,000:
     - For each edge e: include with P_inclusion(e) (Bernoulli draw)
     - For included edges: β^(m)_e ~ N(β̂_e, SE_eff²_e)
     - Assemble B^(m) matrix
   Validation: 10,000 draws generated; mean β across draws ≈ β̂ (within 2 SE)
   Connections: D1→D2; Reads edges_v1; D2→D3

## ALG-D3 — Causal Effect Propagation
   ID: ALG-D3 | Type: COMPOSITE | Phase: PHASE_D | Paper §: §2.12
   Purpose: Propagate intervention effects through the DAG for each MC draw
   Inputs: MCDraws (from D2), CandidateSet (target edges per intervention)
   Outputs: EffectEstimates (Δθ per intervention per draw)
   Logic: For each draw m, for each candidate intervention a:
     - Construct x_intervention vector (intervention magnitudes on target edges)
     - For non-linear edges: apply f(x) = E_max·|x|^h/(EC₅₀^h+|x|^h)·sign(x)
     - Compute: Δθ^(m) = (I − B^(m))⁻¹ · x_intervention [Formula D-1]
     - Apply physiological ceiling: |Δθ_i| ≤ 1.0 SD (single), ≤ 1.5 SD (bundle)
   Formulas: D-1 (Δθ = (I−B)⁻¹·x), D-2 (Emax dose-response)
   Validation: |Δθ| ≤ ceiling for all draws; (I−B) invertible for all draws
   Connections: D2→D3; D3→D4

## ALG-D4 — SAFE Score Computation
   ID: ALG-D4 | Type: COMPOSITE | Phase: PHASE_D | Paper §: §2.16
   Purpose: Compute dual-mode SAFE scores (efficacy + feasibility-adjusted) per intervention
   Inputs: EffectEstimates (from D3), patient burden estimates
   Outputs: SAFEScores (SAFE_A, SAFE_B, CrI per intervention per draw)
   Logic:
     MSS_cog(a) = mean Δθ across cognitive nodes
     MSS_burden(a) = burden estimate (time, cost, side effects)
     SAFE_A(a) = MSS_cog(a) − 0.3 · MSS_burden(a) [Formula D-3]
     SAFE_B(a) = SAFE_A(a) + 0.5 · ln(P_adhere(a)) [Formula D-4]
     where P_adhere from: logit(P) = 1.8 − 0.42·Burden − 0.03·Duration [D-5]
     95% CrI from 2.5th/97.5th percentile across 10,000 draws
   Validation: Both modes computed; CrI width > 0; SAFE_A ≥ SAFE_B (adherence ≤ 1)
   Connections: D3→D4; D4→D5

## ALG-D5 — Bundle & Synergy Analysis
   ID: ALG-D5 | Type: COMPOSITE | Phase: PHASE_D | Paper §: §2.16
   Purpose: Evaluate multi-intervention bundles with synergy/overlap correction
   Inputs: SAFEScores (from D4), synergy_registry_v1 (15 pairwise records)
   Outputs: BundleResults (top bundles with overlap-corrected effects)
   Logic:
     JPO(a,b) = |P_a ∩ P_b| / |P_a ∪ P_b| [pathway overlap]
     CCS(a,b) = (1−JPO)·(1 + shared_cognitive_convergence)
     ΔC_bundle = Σ_a ΔC_a − Σ_{a≠b}(1−JPO)^0.5 + Σ CCS·γ·√(ΔC_a·ΔC_b) [Formula D-6]
     γ from synergy_registry_v1 (empirical interaction term)
     Bundle ceiling: ≤ 1.5 SD total effect
   Validation: Bundle effects ≤ ceiling; all pairwise synergies looked up
   Connections: D4→D5; Reads synergy_registry_v1, pathway_map_v1; D5→D6

## ALG-D6 — Ranked Output Assembly
   ID: ALG-D6 | Type: ATOMIC | Phase: PHASE_D | Paper §: §2.16
   Purpose: Assemble final ranked intervention list (singles + bundles) for output
   Inputs: SAFEScores (from D4), BundleResults (from D5)
   Outputs: SimulationResults → ALG-E, ALG-F
   Logic: Merge single and bundle rankings → Sort by SAFE_B descending → Attach CrI, claim levels, pathway attribution → Package per_draw_safe_scores for F2 stability analysis
   Validation: Rankings consistent between Mode A and Mode B; all candidates included
   Connections: D4→D6, D5→D6; D6→ALG-E (trajectories), D6→ALG-F (output analytics)

───────────────────────────────────────────────────────────────────────────
CHAIN ALG-E: Temporal Prediction (4 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-E1 — Natural Recovery Trajectory
   ID: ALG-E1 | Type: COMPOSITE | Phase: PHASE_E (Runtime) | Paper §: §2.18
   Purpose: Model natural cognitive recovery trajectory (no intervention)
   Inputs: PatientState (from ALG-C), recovery_params_v1 (7 treatment-context sets)
   Outputs: NaturalTrajectory (θ(t) at 3/6/12/24 months, no intervention)
   Logic:
     R(t) = r∞ · (1 − e^{−(t/τ_R)^γ_R}) [Formula E-1: stretched exponential]
     θ_natural(t) = θ_nadir + (θ_baseline − θ_nadir) · R(t) + δ_aging(t)
     δ_aging = −0.02 · max(1, (age−50)/10) · ACC · t_years [Formula E-2]
     ACC values: No chemo 1.0, TC 1.3, Standard 1.5, Anthracycline 2.0, Childhood 2.5
     7 recovery contexts: e.g., breast-anthracycline (r∞=0.70, τ=8, γ=0.8)
   Validation: R(t) monotonically increasing; θ_natural bounded
   Connections: ALG-C→E1; Reads recovery_params_v1; E1→E3

## ALG-E2 — Intervention Kernel Application
   ID: ALG-E2 | Type: COMPOSITE | Phase: PHASE_E | Paper §: §2.11
   Purpose: Apply temporal kernel to each intervention's effect
   Inputs: SimulationResults.ranked_interventions (from ALG-D), intervention_kernels_v1
   Outputs: InterventionTrajectories (Δθ_a(t) at each time point per intervention)
   Logic: For each intervention a:
     K_a(t) = onset_function(t) × maintenance_function(t) × decay_function(t)
     ΔC_a(t) = ΔC_a(0) × K_a(t) [Formula E-3]
     Kernel types: step, ramp, exponential_onset, pulse, maintenance_dependent
     From intervention_kernels_v1: onset_delay, peak_time, half_life, maintenance_required

   ┌─────────────────────────────────────────────────────────────┐
   │ DECISION LOGIC: Missing Kernel Fallback (Gap 2 Fix)         │
   │                                                             │
   │ FOR each intervention a in scenario:                        │
   │                                                             │
   │   IF a.action_id IN intervention_kernels_v1:                │
   │     → Load fitted kernel. Normal path.                      │
   │     → Set temporal_profile_source = "fitted"                │
   │                                                             │
   │   ELIF a.has_temporal_kernel = false                        │
   │        (action_catalog_v1 flag):                            │
   │     → STATIC-ONLY mode.                                     │
   │       Set K_a(t) = 1.0 for all t (constant effect)         │
   │       No trajectory curve generated.                        │
   │       Output shows: "Effect estimate: X SD improvement.     │
   │         Temporal dynamics not characterized."               │
   │     → Set temporal_profile_source = "static_only"           │
   │     → This is the HONEST path — we know it helps            │
   │       but don't know when/how the effect unfolds.           │
   │                                                             │
   │   ELSE (kernel expected but missing):                       │
   │     → Load DEFAULT_CONSERVATIVE kernel:                     │
   │       {onset_wk: 4 (±2), build_wk: 12 (±4),               │
   │        steady_wk: 12-52, decay_half_life_wk: 4 (±2)}      │
   │       Conservative because: slow onset (no quick promises), │
   │       fast decay (no lasting promises). Both biases err     │
   │       toward underestimating the intervention.              │
   │     → Set temporal_profile_source = "default_conservative"  │
   │     → Log WARNING: "Using generic temporal profile for      │
   │       {action_id}. Results are approximate."                │
   │                                                             │
   │ SCHEMA ADDITIONS:                                           │
   │   action_catalog_v1.has_temporal_kernel: BOOLEAN            │
   │     Purpose: Flag indicating whether fitted kernel exists   │
   │     Default: false (safe default)                           │
   │                                                             │
   │   intervention_kernels_v1 row: action_id = DEFAULT_CONSERV  │
   │     onset_wk=4, build_wk=12, steady_wk=26,                 │
   │     decay_half_life_wk=4, source="system_default"           │
   │                                                             │
   │ CLINICAL PRESENTATION:                                      │
   │   Fitted kernel: "Exercise is expected to show initial      │
   │     effects at 2-4 weeks, peak benefit at 12 weeks,         │
   │     with effects declining ~3-4 weeks after stopping."      │
   │   Static-only: "This intervention is estimated to improve   │
   │     cognitive function by X SD. Temporal dynamics are not    │
   │     well characterized; effects may take weeks to manifest."│
   │   Default kernel: "Based on generic behavioral intervention │
   │     profiles, effects may begin within 4 weeks. Temporal    │
   │     estimates carry additional uncertainty."                │
   └─────────────────────────────────────────────────────────────┘

   Validation: K_a(t) ∈ [0, 1] for all t; onset_delay ≥ 0; temporal_profile_source set for all
   Connections: ALG-D→E2; Reads intervention_kernels_v1, action_catalog_v1; E2→E3

## ALG-E3 — Composite Trajectory Assembly
   ID: ALG-E3 | Type: COMPOSITE | Phase: PHASE_E | Paper §: §2.18
   Purpose: Combine natural recovery + intervention effects + aging into full trajectory
   Inputs: NaturalTrajectory (from E1), InterventionTrajectories (from E2)
   Outputs: CompositeTrajectory (θ(t) with and without intervention at all time points)
   Logic:
     θ(t+Δt) = θ_nadir + (θ_base − θ_nadir)·R(Δt) + Σ_a ΔC_a·K_a(Δt) + δ_aging(Δt) [E-4]
     ITE(Δt) = θ_intervention(Δt) − θ_natural(Δt) [Formula E-5]
     Uncertainty: Var(t) = Var(0) + 0.01t + 0.005t² [Formula E-6: growing uncertainty]
     Time points: 0, 1, 3, 6, 12, 18, 24 months
   Validation: ITE sign consistent with SAFE direction; Var(t) monotonically increasing
   Connections: E1→E3, E2→E3; E3→E4

## ALG-E4 — Trajectory Output Packaging
   ID: ALG-E4 | Type: ATOMIC | Phase: PHASE_E | Paper §: §2.18
   Purpose: Package trajectories with uncertainty bands for clinical visualization
   Inputs: CompositeTrajectory (from E3)
   Outputs: TemporalPredictions → ALG-F, writes temporal_trajectories_v1
   Logic: For each time point:
     - Mean trajectory ± 95% CrI from MC draws
     - MID crossing time: when does |z| cross 0.50 SD threshold?
     - Recovery probability: P(|z| < 0.50 at t=24mo)

   ┌─────────────────────────────────────────────────────────────┐
   │ UNCERTAINTY SCALING BY KERNEL SOURCE (Gap 2 Fix cont.)      │
   │                                                             │
   │ When temporal_profile_source ≠ "fitted", uncertainty growth │
   │ coefficients are scaled to reflect the unknown dynamics:     │
   │                                                             │
   │ IF temporal_profile_source = "fitted":                      │
   │   Var(t) = Var(0) + 0.01t + 0.005t²  (standard)            │
   │                                                             │
   │ IF temporal_profile_source = "default_conservative":        │
   │   Var(t) = Var(0) + 0.015t + 0.0075t² (1.5× coefficients) │
   │   → Wider CrI bands signal "temporal shape is approximate"  │
   │                                                             │
   │ IF temporal_profile_source = "static_only":                 │
   │   No trajectory curve generated. Output:                    │
   │     temporal_trajectories_v1.has_trajectory = false          │
   │     Only static effect Δθ reported (no time-series)         │
   │                                                             │
   │ OUTPUT FLAG per intervention in temporal_trajectories_v1:    │
   │   temporal_profile_source: ENUM {fitted, default, static}   │
   │   Mandatory prefix for static_only or default:              │
   │     "Model predicts..." (per ALG-E4 temporal claim prefix)  │
   └─────────────────────────────────────────────────────────────┘

   Validation: All time points have mean + CrI; MID crossing computed; temporal_profile_source logged
   Connections: E3→E4; Writes temporal_trajectories_v1 (Class E); E4→ALG-F

───────────────────────────────────────────────────────────────────────────
CHAIN ALG-F: Output & Analytics (5 subsystems)
───────────────────────────────────────────────────────────────────────────

## ALG-F1 — Composite Outcome Scoring
   ID: ALG-F1 | Type: COMPOSITE | Phase: PHASE_F (Runtime) | Paper §: §2.20
   Purpose: Compute IVW composite CRCI score with severity weighting
   Inputs: PatientState posterior (from ALG-C)
   Outputs: CompositeState (crci_composite, severity_tier, percentile)
   Sub-steps: F1a (subdomain extraction), F1b (severity weighting: 1.0/1.5/2.0×),
     F1c (IVW composite + Cochran's Q + random-effects if I²>50%)
   Formulas: F-1 (CRCI=Σw_d·z_d/Σw_d), F-2 (Score=Φ(−z)×100), F-3 (Q=Σw_d(z_d−CRCI)²)
   Validation: crci ∈ [−5,5]; percentile ∈ [0,100]; severity assigned
   Connections: ALG-C→F1; Reads nodes_v1 (domain assignments); F1→F2

## ALG-F2 — Decision Stability Analysis
   ID: ALG-F2 | Type: COMPOSITE | Phase: PHASE_F | Paper §: §2.19
   Purpose: Assess ranking stability across 10,000 MC draws
   Inputs: SimulationResults.per_draw_safe_scores (from ALG-D)
   Outputs: StabilityState (P(rank₁), stability_class, critical edges)
   Sub-steps: F2a (per-draw ranking), F2b (rank probability: ≥0.80 Stable, 0.60-0.79 Moderate,
     0.40-0.59 Unstable, <0.40 Highly_unstable), F2c (decision-critical edge identification)
   Formula: F-4 (P(rank₁=a) = (1/N)Σ𝟙[rank₁^(m)=a])
   Validation: Σ P(rank₁) = 1.0; stability classified; 3 critical edges
   Connections: ALG-D→F2; F2→F3

## ALG-F3 — Five-Source Variance Decomposition
   ID: ALG-F3 | Type: COMPOSITE | Phase: PHASE_F | Paper §: §2.21
   Purpose: Decompose prediction variance into 5 actionable sources
   Inputs: PatientState, edges_v1, instruments_v1
   Outputs: VarianceState (5 percentages + top 2 reducible sources)
   5 Sources: Literature heterogeneity (25-40%), Measurement noise (10-20%),
     Structural uncertainty (15-25%, fixed σ²=0.25), Proxy imprecision (10-20%),
     Missing observations (10-30%)
   Formula: F-5 (ΔVar = Σ Cov(Y,X_i)²/Var(X_i))
   Validation: 5 components sum to 100%; all ≥ 0
   Connections: Reads edges_v1, instruments_v1; F3→F4

## ALG-F4 — Population Analytics
   ID: ALG-F4 | Type: COMPOSITE | Phase: PHASE_F | Paper §: §4.5
   Purpose: Cluster patients into archetypes via GMM on pathway activation profiles
   Inputs: PathwayProfile (from ALG-C/D), historical profiles
   Outputs: PopulationState (K archetypes, assignment, escalation flag)
   Logic: GMM with K selected by BIC; min cluster 5%; Mahalanobis > 2.5 → escalation
   Formulas: F-9 (Mahalanobis), F-10 (BIC)
   Validation: K ≥ 2; all patients assigned
   Connections: ALG-C/D→F4; Writes population_archetypes_v1; F4→F5

## ALG-F5 — Research Analytics (EVSI)
   ID: ALG-F5 | Type: COMPOSITE | Phase: PHASE_F | Paper §: §2.22
   Purpose: Rank evidence gaps by discovery score, generate study designs, compute EVSI
   Inputs: edges_v1, chain-vs-direct validation results (from B6/VAL-01)
   Outputs: ResearchOutputPackage (gap map, study designs, EVSI)
   Sub-steps: F5a (discovery_score = |elasticity| × SE_eff), F5b (chain-vs-direct flagging),
     F5c (study design generator: N, design type, endpoint), F5d (EVSI: nested MC 500×1000)
   Formulas: F-6 (discovery score), F-7 (EVSI), F-8 (power calc)
   Validation: Top 10 edges ranked; top 5 EVSI computed; study designs generated
   Connections: Reads edges_v1; ALG-B6→F5; Writes evidence_gaps_v1


═══════════════════════════════════════════════════════════════════════════
                    APPENDIX: CROSS-REFERENCE VALIDATION
═══════════════════════════════════════════════════════════════════════════

A. FORMULA COVERAGE (Paper → Chain Card)
   §2.1 DAG formulation    → ALG-A (A2-1, A2-2)
   §2.6 SEM + Precision    → ALG-A (A3-1, A3-2, A3-3, A4-1, A4-2, A4-3)
   §2.7 Noise model        → ALG-C (C-1)
   §2.8 Bayesian update    → ALG-C (C-2, C-3, C-4)
   §2.9 Seven-layer SE     → ALG-B (B-1, B-2, B-3, B-7, B-8)
   §2.10 Prior selection   → ALG-B (B-4, B-5)
   §2.11 Temporal kernels  → ALG-E (E-3)
   §2.12 MC engine         → ALG-B (B-6), ALG-D (D-1)
   §2.13 Chain-vs-direct   → ALG-B (B-9)
   §2.14 Intervention sem. → ALG-D (D1 causal language gate)
   §2.15 Effect modifiers  → ALG-C (C3 modifier application)
   §2.16 Synergy + SAFE    → ALG-D (D-3, D-4, D-5, D-6)
   §2.17 Latent variables  → ALG-A (A5b proxy table)
   §2.18 Temporal traj.    → ALG-E (E-1, E-2, E-4, E-5, E-6)
   §2.19 Decision stability→ ALG-F (F-4)
   §2.20 Composite outcome → ALG-F (F-1, F-2, F-3)
   §2.22 Evidence gaps     → ALG-F (F-6, F-7, F-8)

B. TABLE READS/WRITES PER CHAIN
   ALG-A: READS nodes_v1, edges_v1, instruments_v1, correlation_registry_v1, feedback_loops_v1, pathway_map_v1 | WRITES none (in-memory GraphObject)
   ALG-B: READS edge_evidence_v1, context_matched_priors_v1 | WRITES edges_v1 (β, SE_eff, P_incl), prior_selection_log_v1
   ALG-C: READS edges_v1, instruments_v1, modifier_registry_v1, pathway_map_v1 | WRITES state_snapshots_v1
   ALG-D: READS action_catalog_v1, synergy_registry_v1, pathway_map_v1, dose_response_params_v1 | WRITES intervention_rankings_v1
   ALG-E: READS recovery_params_v1, intervention_kernels_v1 | WRITES temporal_trajectories_v1
   ALG-F: READS nodes_v1, edges_v1, instruments_v1, population_archetypes_v1 | WRITES intervention_rankings_v1, variance_decomposition_v1, evidence_gaps_v1, population_archetypes_v1

C. SUBSYSTEM ID CONSISTENCY
   ALG-A: A1, A2, A3, A4, A5 (5 subsystems — matches chain card §4)
   ALG-B: B1, B2, B3, B4, B5, B6, B7 (7 subsystems — matches chain card §4)
   ALG-C: C1, C2, C3, C4 (4 subsystems — matches chain card §4)
   ALG-D: D1, D2, D3, D4, D5, D6 (6 subsystems — matches chain card §4)
   ALG-E: E1, E2, E3, E4 (4 subsystems — matches chain card §4)
   ALG-F: F1, F2, F3, F4, F5 (5 subsystems — matches chain card §4)
   TOTAL: 31 subsystems ✓

D. DATA FLOW: END-TO-END
   nodes_v1/edges_v1 (registries)
     → ALG-A (assemble GraphObject)
       → ALG-B (parameterize: β̂, SE_eff, P_incl → write edges_v1)
         → ALG-C (patient observations → PatientState → write state_snapshots_v1)
           → ALG-D (interventions → SAFE scores → write intervention_rankings_v1)
             → ALG-E (temporal predictions → write temporal_trajectories_v1)
               → ALG-F (composite + stability + gaps → write output tables)
                 → SYS_RUNTIME (receives 3 output packages)

═══════════════════════════════════════════════════════════════════════════
END OF SYS_ALGORITHM COMPLETE SPECIFICATION
═══════════════════════════════════════════════════════════════════════════
