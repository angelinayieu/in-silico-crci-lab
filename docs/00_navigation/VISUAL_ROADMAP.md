# CRCI Implementation Visual Roadmap

**Visual diagrams and flowcharts for the CRCI system implementation**

---

## 🗺️ Overall System Map

```
┌───────────────────────────────────────────────────────────────────────┐
│                         CRCI SYSTEM v1.0                              │
│                  Bayesian Causal Model for CRCI                       │
└───────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 0: FOUNDATION                                                   │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │
│ │  Database   │  │   Shared    │  │   Config    │                    │
│ │   Schemas   │  │   Models    │  │  Constants  │                    │
│ └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                    │
│        └─────────────────┴─────────────────┘                          │
│                          │                                             │
│                 ✅ V0: Schema Check                                    │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│ EXTRACTION PIPELINE (Phases 1-4)                                      │
│                                                                        │
│  Phase 1: P0-P1          Phase 2: P2           Phase 3: P3            │
│  ┌──────────────┐       ┌──────────┐         ┌──────────┐            │
│  │   Triage +   │       │ Harmoni- │         │Heterogen-│            │
│  │  Extraction  │──────▶│ zation   │────────▶│  eity    │────┐       │
│  └──────────────┘       └──────────┘         └──────────┘    │       │
│                                                                │       │
│  Phase 4: P4                                                   │       │
│  ┌──────────────┐                                             │       │
│  │ Aggregation  │◀────────────────────────────────────────────┘       │
│  │Meta-Analysis │                                                      │
│  └──────┬───────┘                                                      │
│         │                                                              │
│         ▼                                                              │
│  edge_evidence_v1                                                      │
│                                                                        │
│  ✅ V1, V2: Extraction Verification                                   │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 5: ALGORITHM (THE CORE ENGINE)                                  │
│                                                                        │
│  Chain A          Chain B         Chain C          Chain D            │
│  ┌──────┐       ┌───────┐       ┌────────┐       ┌──────┐            │
│  │Graph │──────▶│Prior  │──────▶│Bayesian│──────▶│  MC  │──┐         │
│  │Build │       │Compile│       │ Update │       │ Sim  │  │         │
│  └──────┘       └───────┘       └────────┘       └──────┘  │         │
│                                                              │         │
│  Chain E          Chain F                                   │         │
│  ┌──────────┐   ┌──────────┐                                │         │
│  │Temporal  │   │   CRCI   │◀───────────────────────────────┘         │
│  │Dynamics  │   │  Score   │                                          │
│  └──────────┘   └──────────┘                                          │
│                                                                        │
│  ✅ V5: Mathematical Correctness (CRITICAL)                           │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 6: PRESENTATION                                                 │
│  ┌───────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐              │
│  │  DAG  │  │Evidence  │  │Intervention│  │Trajectory│              │
│  │  Viz  │  │ Browser  │  │   Cards    │  │  Plots   │              │
│  └───────┘  └──────────┘  └────────────┘  └──────────┘              │
│                                                                        │
│  ✅ V6: Presentation Verification                                     │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 7: RUNTIME                                                      │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐                     │
│  │ Orchestration│  │   Logging   │  │   CLI    │                     │
│  └──────────────┘  └─────────────┘  └──────────┘                     │
│                                                                        │
│  ✅ V-FINAL: End-to-End System Test                                   │
└───────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                   🎉 v1 COMPLETE 🎉
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT: Research Papers                        │
│                         (PDFs, ~50-200)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │  P0: TRIAGE                           │
         │  • Parse PDF                          │
         │  • Detect sections                    │
         │  • Classify study design              │
         └───────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────────┐
         │  P1: EXTRACTION                       │
         │  • Agent AG11 (LLM)                   │
         │  • Parse tables, text, figures        │
         │  • Extract β, CI, n, design           │
         │  Output: RawExtraction                │
         └───────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────────┐
         │  P2: HARMONIZATION                    │
         │  • Convert OR/RR → Cohen's d          │
         │  • Compute SE from CI                 │
         │  • Validate conversions               │
         │  Output: HarmonizedClaim              │
         └───────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────────┐
         │  P3: HETEROGENEITY                    │
         │  • Apply 7 layers (L1-L7)             │
         │  • SE_eff = SE_raw × Π(M_i)           │
         │  • Widen uncertainty                  │
         │  Output: CalibratedRecord             │
         └───────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────────┐
         │  P4: AGGREGATION                      │
         │  • Meta-analysis (IVW, DL)            │
         │  • Publication bias tests             │
         │  • Select prior type                  │
         │  Output: PooledEstimate               │
         └───────────────┬───────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    DATABASE: edge_evidence_v1                      │
│                    (All extracted evidence)                        │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │  CHAIN A: GRAPH BUILD                 │
         │  • Assemble 63×63 adjacency           │
         │  • Spectral validation                │
         │  • Freeze model                       │
         └───────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────────┐
         │  CHAIN B: PRIOR COMPILATION           │
         │  • Merge literary + contextual        │
         │  • Compute σ²_structural              │
         │  • Integrate modifiers                │
         └───────────────┬───────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    DATABASE: edges_v1                              │
│              (Compiled model: 118 edges with priors)               │
└────────────────────────────┬───────────────────────────────────────┘
                             │
         ┌───────────────────┴────────────────────┐
         │                                        │
         ▼                                        ▼
┌─────────────────────┐                 ┌─────────────────────┐
│  INPUT: Patient     │                 │  INPUT: Patient     │
│  Questionnaire      │                 │  State (posterior)  │
└──────────┬──────────┘                 └──────────┬──────────┘
           │                                       │
           ▼                                       ▼
  ┌────────────────────┐                ┌────────────────────┐
  │  CHAIN C:          │                │  CHAIN D:          │
  │  BAYESIAN UPDATE   │                │  MC SIMULATION     │
  │  • Kalman-like     │                │  • 10K draws       │
  │  • Posterior θ̂     │                │  • Intervention    │
  │  Output: 63 nodes  │                │    effects         │
  └────────┬───────────┘                │  • SAFE_A, SAFE_B  │
           │                            └────────┬───────────┘
           │                                     │
           ▼                                     ▼
  ┌────────────────────┐                ┌────────────────────┐
  │  CHAIN F:          │                │  OUTPUT:           │
  │  CRCI SCORE        │                │  Intervention      │
  │  • Composite       │                │  Rankings          │
  │  • Percentile      │                │  • Sorted by Δθ    │
  └────────┬───────────┘                └────────┬───────────┘
           │                                     │
           └──────────────┬──────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────────────┐
          │  CHAIN E: TEMPORAL DYNAMICS           │
          │  • Trajectory prediction              │
          │  • Recovery modeling                  │
          └───────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                                 │
│  • DAG visualization                                                 │
│  • Evidence browser                                                  │
│  • Intervention cards                                                │
│  • Trajectory plots                                                  │
│  • Report generation                                                 │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
                  📄 Scientific Report
                  📊 Patient Dashboard
                  📈 Clinical Recommendations
```

---

## 🔄 File Implementation Flow

```
FOR EACH FILE:

┌─────────────────────────────────────────────────────────┐
│ STEP 1: READ                                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ • Manifest entry (FILE_CONTEXT_MANIFEST.md)         │ │
│ │ • Spec lines (SYS_*.md)                             │ │
│ │ • Upstream code (what produces your input)          │ │
│ │ • Downstream manifest (what consumes your output)   │ │
│ │ • Anchor files (config, enums, models)              │ │
│ │ • Enforcement rules (12 rules)                      │ │
│ │ • Table fill order (if DB access)                   │ │
│ │ • Interface schemas (if intermediate states)        │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2: PLAN                                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Explicitly state:                                    │ │
│ │ ✓ Inputs (types + which file)                       │ │
│ │ ✓ Outputs (types + which file)                      │ │
│ │ ✓ Formulas (IDs from spec)                          │ │
│ │ ✓ Gates (IDs from spec)                             │ │
│ │ ✓ Config constants                                  │ │
│ │ ✓ Decisions affecting downstream                    │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3: IMPLEMENT                                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Follow ALL 12 enforcement rules:                    │ │
│ │ 1. No hardcoded numbers                             │ │
│ │ 2. No invented formulas                             │ │
│ │ 3. No stubs/TODO                                    │ │
│ │ 4. Explicit imports                                 │ │
│ │ 5. Typed signatures                                 │ │
│ │ 6. Gates raise on failure                           │ │
│ │ 7. Log all defaults                                 │ │
│ │ 8. Specify DB columns                               │ │
│ │ 9. Validate DB writes                               │ │
│ │ 10. Seed randomness                                 │ │
│ │ 11. File docstring                                  │ │
│ │ 12. Exact column names                              │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4: VERIFY                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Run ALL checks:                                      │ │
│ │ a. Formula accuracy (char-by-char)                  │ │
│ │ b. Backward coherence (upstream wiring)             │ │
│ │ c. Forward coherence (downstream wiring)            │ │
│ │ d. Hardcode scan (no float literals)                │ │
│ │ e. Gate enforcement (all raise)                     │ │
│ │ f. Review tasks (if applicable)                     │ │
│ │ g. Import validity (all modules exist)              │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5: TEST (if formula-dense)                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ • Hand-computable expected values                   │ │
│ │ • Edge cases (k=0, missing data, boundaries)        │ │
│ │ • Gate violation tests (assert raises)              │ │
│ │ • Config constant usage (no hardcodes)              │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 6: LOG VERIFICATION STAMP                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Add to top of file:                                  │ │
│ │ # VERIFIED: formulas [IDs] match spec lines [X-Y]   │ │
│ │ # VERIFIED: imports — all modules exist             │ │
│ │ # VERIFIED: backward wiring — reads [Type] from [F] │ │
│ │ # VERIFIED: forward wiring — writes [Type] for [F]  │ │
│ │ # VERIFIED: no hardcoded formula parameters         │ │
│ │ # VERIFIED: gates [IDs] raise on failure            │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
                  ✅ FILE COMPLETE
                  (Commit and move to next file)
```

---

## 🎯 Phase Completion Flow

```
START PHASE N
     │
     ▼
┌─────────────────────────────────────┐
│  Execute Prompt N.1                 │
│  (Follow 6-step cycle per file)     │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Execute Prompt N.2                 │
│  (Follow 6-step cycle per file)     │
└─────────────┬───────────────────────┘
              │
              ▼
             ...
              │
              ▼
┌─────────────────────────────────────┐
│  Execute Prompt N.last              │
│  (Follow 6-step cycle per file)     │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Run Phase N Verification           │
│  (V0, V1, V2, V5, V6, or V-FINAL)   │
└─────────────┬───────────────────────┘
              │
              ▼
         All checks pass?
              │
        ┌─────┴─────┐
        │           │
       YES          NO
        │           │
        │           ▼
        │     ┌──────────────────┐
        │     │  Debug & Fix     │
        │     │  Re-run verify   │
        │     └────────┬─────────┘
        │              │
        │              └───────────┐
        │                          │
        ▼                          ▼
┌─────────────────────────────────────┐
│  Git commit                         │
│  "Phase N complete, verification    │
│   passed"                           │
└─────────────┬───────────────────────┘
              │
              ▼
        Next phase or DONE
```

---

## 🧩 Module Dependency Graph

```
                    ┌───────────────┐
                    │ shared/config │
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
   ┌────────────────────┐      ┌────────────────────┐
   │ shared/models/     │      │  database/schema/  │
   │  enums.py          │◀─────│  *.sql             │
   └─────────┬──────────┘      └──────────┬─────────┘
             │                            │
             ▼                            │
   ┌────────────────────┐                │
   │ shared/models/     │                │
   │  intermediate_     │                │
   │  states.py         │                │
   └─────────┬──────────┘                │
             │                            │
             └──────────┬─────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌─────────────────────┐
│  extraction/      │         │  llm/               │
│  p0_triage/       │         │  client.py          │
│  p1_extraction/   │         └─────────┬───────────┘
└────────┬──────────┘                   │
         │                              │
         └──────────────┬───────────────┘
                        │
                        ▼
         ┌──────────────────────────┐
         │ extraction/              │
         │  p2_harmonization/       │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ extraction/              │
         │  p3_heterogeneity/       │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ extraction/              │
         │  p4_aggregation/         │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ DATABASE:                │
         │  edge_evidence_v1        │
         └──────────┬───────────────┘
                    │
        ┌───────────┴───────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐     ┌─────────────────────┐
│ algorithm/        │     │ algorithm/          │
│  chain_a_graph/   │     │  chain_b_evidence/  │
└────────┬──────────┘     └──────────┬──────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     ▼
         ┌──────────────────────────┐
         │ DATABASE: edges_v1       │
         └──────────┬───────────────┘
                    │
        ┌───────────┴───────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐     ┌─────────────────────┐
│ algorithm/        │     │ algorithm/          │
│  chain_c_         │     │  chain_d_           │
│  posterior/       │     │  simulation/        │
└────────┬──────────┘     └──────────┬──────────┘
         │                           │
         └───────────┬───────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────────┐   ┌─────────────────────┐
│ algorithm/        │   │ algorithm/          │
│  chain_e_         │   │  chain_f_           │
│  temporal/        │   │  analytics/         │
└────────┬──────────┘   └──────────┬──────────┘
         │                         │
         └──────────┬──────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ presentation/            │
         │  (all modules)           │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ runtime/                 │
         │  (orchestration)         │
         └──────────────────────────┘
```

---

## 📈 Progress Tracking

```
YOUR PROGRESS:

Phase 0: Foundation               [▱▱▱▱▱▱▱▱] 0/8 prompts
  └─ V0 Verification              [ ] Not run

Phase 1: Triage + Extraction      [▱▱▱▱▱▱▱▱] 0/8 prompts
  └─ V1 Verification              [ ] Not run

Phase 2: Harmonization            [▱▱▱▱▱▱] 0/6 prompts
  └─ V2 Verification              [ ] Not run

Phase 3: Heterogeneity            [▱▱▱▱▱▱▱▱▱] 0/9 prompts
  └─ V2 Verification              [ ] Not run

Phase 4: Aggregation              [▱▱▱▱▱▱▱▱] 0/8 prompts
  └─ V2 Verification              [ ] Not run

Phase 5: Algorithm (CORE)         [▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱] 0/15 prompts
  └─ V5 Verification (CRITICAL)   [ ] Not run

Phase 6: Presentation             [▱▱▱▱▱▱▱▱] 0/8 prompts
  └─ V6 Verification              [ ] Not run

Phase 7: Runtime                  [▱▱▱▱▱▱] 0/6 prompts
  └─ V-FINAL Verification         [ ] Not run

─────────────────────────────────────────────────────
TOTAL: [▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱] 0/68
─────────────────────────────────────────────────────

Update this as you complete prompts!
Use █ for completed, ▰ for in-progress, ▱ for not started.
```

---

## 🎓 Key Concepts Map

```
┌───────────────────────────────────────────────────────────────┐
│                    EXTRACTION CONCEPTS                        │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  RawExtraction → HarmonizedClaim → CalibratedRecord →        │
│                                     PooledEstimate            │
│                                                               │
│  Transformations:                                             │
│  • P1: PDF → structured data                                  │
│  • P2: Various effect sizes → Cohen's d                       │
│  • P3: SE_raw → SE_eff (widen uncertainty)                    │
│  • P4: k studies → 1 pooled estimate                          │
│                                                               │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    ALGORITHM CONCEPTS                         │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Compiled Model (edges_v1):                                   │
│  • β: Effect size (mean of posterior from literature)         │
│  • SE_eff: Effective standard error (uncertainty)             │
│  • σ²_struct: Structural variance (model uncertainty)         │
│  • P_inclusion: Probability edge is real                      │
│                                                               │
│  Patient Inference:                                           │
│  • Observations: Questionnaire responses                      │
│  • Prior: Compiled model (edges_v1)                           │
│  • Posterior: Bayesian update (Kalman-like)                   │
│  • Output: Patient-specific node values (θ̂)                  │
│                                                               │
│  Intervention Simulation:                                     │
│  • θ̂_pre: Current patient state                               │
│  • Intervention: Modify specific nodes                        │
│  • Propagation: Effects flow through DAG                      │
│  • θ̂_post: Simulated future state                             │
│  • SAFE_A/B: Probability of benefit                           │
│                                                               │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     QUALITY CONCEPTS                          │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Gates: Hard stops that raise exceptions                      │
│  • Example: P3-G1 requires SE_eff ≥ SE_raw                    │
│  • Never log-and-continue; always raise                       │
│                                                               │
│  Formulas: Every computation has a spec ID                    │
│  • Example: P4-1 is β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)        │
│  • Code must cite formula ID in comment                       │
│                                                               │
│  Config: All numbers from shared/config.py                    │
│  • Never hardcode 0.25; use config.SIGMA_DEFAULT              │
│  • Searchable, changeable, traceable                          │
│                                                               │
│  Verification: Multi-level checks                             │
│  • Per-file: 6-step cycle                                     │
│  • Per-phase: V0-V6, V-FINAL                                  │
│  • Per-formula: Hand-computed tests                           │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 🏁 Completion Checklist

```
PHASE 0: FOUNDATION
├─ [ ] Database schemas created (001-004.sql)
├─ [ ] Seed files loaded (21 knowledge tables)
├─ [ ] shared/config.py with ALL constants
├─ [ ] shared/models/enums.py with ALL enums
├─ [ ] shared/models/intermediate_states.py
├─ [ ] Database connection working
└─ [ ] V0 verification passed

PHASE 1: TRIAGE + EXTRACTION
├─ [ ] PDF parser implemented
├─ [ ] Section detector implemented
├─ [ ] Study classifier implemented
├─ [ ] Agent AG11 (LLM extraction)
├─ [ ] Result parsers (table/text/figure)
├─ [ ] Confidence scorer
├─ [ ] Review task writer
└─ [ ] V1 verification passed

PHASE 2: HARMONIZATION
├─ [ ] Type router (OR/RR/HR/r/d)
├─ [ ] Unit converters (to Cohen's d)
├─ [ ] CI/SE calculator
├─ [ ] Harmonization validator
├─ [ ] Gates P2-G1, P2-G2
└─ [ ] V2 verification passed

PHASE 3: HETEROGENEITY
├─ [ ] Layer L1 (study design)
├─ [ ] Layer L2 (population age)
├─ [ ] Layer L3 (scale mismatch)
├─ [ ] Layer L4 (duration)
├─ [ ] Layer L5 (comorbidity)
├─ [ ] Layer L6 (publication age)
├─ [ ] Layer L7 (scale reliability)
├─ [ ] Layer compositor
├─ [ ] Gates P3-G1, P3-G2
└─ [ ] V2 verification passed

PHASE 4: AGGREGATION
├─ [ ] Double-counting detector
├─ [ ] Overlap resolver
├─ [ ] Meta-analyzer (IVW, DL, RE)
├─ [ ] Publication bias (Egger, PET-PEESE)
├─ [ ] Heterogeneity stats (I², τ²)
├─ [ ] Prior selector
├─ [ ] Gates P4-G1, P4-G2, P4-G3
└─ [ ] V2 verification passed

PHASE 5: ALGORITHM
├─ [ ] Chain A: Graph assembly
├─ [ ] Chain A: Spectral validation
├─ [ ] Chain A: Model freeze
├─ [ ] Chain B: Prior compilation
├─ [ ] Chain B: σ²_structural
├─ [ ] Chain B: Modifier integration
├─ [ ] Chain C: Bayesian update (CORE)
├─ [ ] Chain C: Observation weighting
├─ [ ] Chain C: Variance propagation
├─ [ ] Chain D: MC sampler
├─ [ ] Chain D: Intervention simulator
├─ [ ] Chain D: SAFE scorer
├─ [ ] Chain E: Trajectory prediction
├─ [ ] Chain E: Recovery model
├─ [ ] Chain F: CRCI composite score
└─ [ ] V5 verification passed (CRITICAL)

PHASE 6: PRESENTATION
├─ [ ] DAG visualizer
├─ [ ] Evidence browser
├─ [ ] Intervention cards
├─ [ ] Trajectory plotter
├─ [ ] Variance decomposition
├─ [ ] Report generator
└─ [ ] V6 verification passed

PHASE 7: RUNTIME
├─ [ ] Extraction orchestrator
├─ [ ] Compilation runner
├─ [ ] Patient inference CLI
├─ [ ] Logging & monitoring
├─ [ ] Error handling
└─ [ ] V-FINAL verification passed

────────────────────────────────────────
v1 COMPLETE: ALL BOXES CHECKED
Ready for science project! 🎉
────────────────────────────────────────
```

---

**Last Updated:** 2026-02-25  
**For:** CRCI System v1 Implementation

**Next:** Start with [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md), then [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompt 0.1
