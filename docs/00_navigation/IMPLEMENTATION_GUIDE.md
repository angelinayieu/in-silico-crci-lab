# CRCI System Implementation Guide
*Your Complete Roadmap to Building the CRCI Bayesian Causal Model*

**Version:** 1.0  
**Date:** February 25, 2026  
**Status:** Active Development

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What You're Building](#what-youre-building)
3. [Documentation Map](#documentation-map)
4. [The 7-Phase Build Sequence](#the-7-phase-build-sequence)
5. [How to Implement Each File](#how-to-implement-each-file)
6. [Quality Gates & Verification](#quality-gates--verification)
7. [Troubleshooting & Common Issues](#troubleshooting--common-issues)

---

## 🚀 Quick Start

### First Time Here?

**Read this in order:**
1. **This document** (IMPLEMENTATION_GUIDE.md) — your roadmap
2. **IMPLEMENTATION_BLUEPRINT_v1.1.md** — what v1 needs to do
3. **PROMPT_SEQUENCE.md** — the 42 prompts you'll execute

**Then start with Phase 0, Prompt 0.1** and follow the sequence.

### What's Your Goal?

**Goal:** Build a working CRCI prediction system (v1) that:
- Extracts evidence from ~50-200 papers
- Compiles a Bayesian causal model with 63 nodes and 118 edges
- Predicts patient-specific CRCI risk from questionnaire responses
- Ranks intervention effectiveness for each patient
- Generates scientific visualizations for publication

**Not in v1:** Autonomous retrieval, background workers, production deployment

---

## 🏗️ What You're Building

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CRCI SYSTEM v1                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐        │
│  │ EXTRACTION │───▶│ ALGORITHM  │───▶│PRESENTATION│        │
│  │  (EX)      │    │  (ALG)     │    │  (PRES)    │        │
│  │  Phases 1-4│    │  Phase 5   │    │  Phase 6   │        │
│  └────────────┘    └────────────┘    └────────────┘        │
│                                                              │
│  Phase 0: DATABASE + SHARED (foundation for all above)      │
│  Phase 7: RUNTIME (orchestration + monitoring)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Papers (PDFs)
    ↓
[EX] Extract → Harmonize → Aggregate
    ↓
edge_evidence_v1 (database)
    ↓
[ALG] Compile Graph → Build Priors → Bayesian Update
    ↓
edges_v1 (compiled model with 118 edges)
    ↓
[ALG] Patient Inference → MC Simulation → CRCI Score
    ↓
[PRES] Visualizations + Intervention Cards + Report
```

### Key Outputs

| Output | Description | Where |
|--------|-------------|-------|
| **Compiled Model** | 118 edges with β̂, SE_eff, P_inclusion | `edges_v1` table |
| **Patient State** | Posterior θ̂ over 63 nodes | Per-session computation |
| **Intervention Ranks** | Sorted by expected benefit + CI | Real-time per patient |
| **CRCI Score** | Composite severity score + percentile | Real-time per patient |
| **Visualizations** | DAG, evidence browser, trajectory plots | Generated on demand |

---

## 📚 Documentation Map

### Core Documents (Use Always)

| Document | Lines | Purpose | When to Use |
|----------|-------|---------|-------------|
| **IMPLEMENTATION_GUIDE.md** | ~900 | This file — your roadmap | Always (start here) |
| **IMPLEMENTATION_BLUEPRINT_v1.1.md** | 768 | Architecture, v1 scope | Read first, reference often |
| **PROMPT_SEQUENCE.md** | 1,412 | 42 ordered prompts | Follow sequentially |
| **FILE_CONTEXT_MANIFEST.md** | 885 | Per-file spec lookup | Before each file |
| **CODE_QUALITY_ENFORCEMENT.md** | 445 | 12 rules + verifications | Append to every prompt |

### System Specifications

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **SYS_EXTRACTION_COMPLETE.md** | 2,764 | Extraction chains P0-P6 | Phases 1-4 |
| **SYS_ALGORITHM_COMPLETE.md** | 4,418 | Algorithm chains A-F | Phase 5 |
| **SYS_RUNTIME_COMPLETE.md** | 752 | Runtime orchestration | Phase 7 |
| **SYS_PRESENTATION_COMPLETE.md** | 541 | UI & visualization | Phase 6 |

### Database & Schema

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **05_TABLE_SCHEMAS.md** | 2,334 | All 56 table definitions | Phase 0, any DB work |
| **06_FK_WIRING_MAP.md** | 618 | Foreign key relationships | Phase 0, any DB work |
| **11_CONTROLLED_VOCABULARIES.md** | 344 | All enum values | When defining enums |

### Supporting Documents

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **TABLE_FILL_ORDER.md** | 378 | When tables get populated | When reading/writing tables |
| **INTERFACE_SCHEMA_LOCK.md** | 377 | Intermediate state schemas | When passing data between modules |
| **PARAMETER_PROVENANCE_AND_CURATION.md** | 488 | GREEN/YELLOW/RED parameters | Phase 0, manual curation |
| **SYS_EXTRACTION_ADDENDUM.md** | 635 | Extended agents, compilers | Phases 1-4 (advanced) |
| **AUTOMATED_RETRIEVAL_PLAN.md** | 1,057 | Paper retrieval (v2) | Future reference only |

### Quick Reference Files

Located in workspace root:
- `NODE_REGISTRY.csv` — 63 nodes with IDs, labels, domains
- `EDGE_REGISTRY.csv` — 118 edges with source→target relationships
- `PATHWAY_REGISTRY.csv` — 21 pathway definitions
- `MEASURE_REGISTRY.csv` — Measurement instruments
- `INSTRUMENT_REGISTRY.csv` — Assessment tools

---

## 🔄 The 7-Phase Build Sequence

### Phase Structure

Each phase has:
- **Goal:** What you're building
- **Prompts:** Numbered instructions to execute in order
- **Verification:** Quality gate to run after completion
- **Commit:** Save point after verification passes

### Phase 0: Foundation (Database + Shared)

**Goal:** Build the data layer and shared models

**Duration:** ~6-8 prompts  
**Files Created:** ~15 files  
**Critical:** Everything depends on this phase

#### Prompts
- **0.1** — Database schema: Class A (knowledge tables)
- **0.2** — Database schema: Class B (evidence tables)
- **0.3** — Database schema: Class C (algorithm tables)
- **0.4** — Database schema: Class D (runtime tables)
- **0.5** — Shared models: enums.py
- **0.6** — Shared models: intermediate_states.py
- **0.7** — Shared config.py (all constants)
- **0.8** — Database connection & base setup

#### Key Files
```
crci/
  shared/
    config.py             — ALL formula constants
    models/
      enums.py            — All controlled vocabularies
      intermediate_states.py — TypedNumericValue, HarmonizedClaim, etc.
  database/
    schema/
      001_class_a_knowledge.sql
      002_class_b_evidence.sql
      003_class_c_algorithm.sql
      004_class_d_runtime.sql
    seeds/
      nodes_v1.csv (63 rows)
      edges_v1_skeleton.csv (118 rows)
      instruments_v1.csv (23 rows)
      [... 18 more seed files]
```

#### Verification
Run **V0** from CODE_QUALITY_ENFORCEMENT.md:
- Schema consistency check
- Model imports work
- Enum values match spec
- Config constants complete

#### Before Moving to Phase 1
✅ All schemas created  
✅ All seeds loaded  
✅ Shared models importable  
✅ V0 verification passed  
✅ Git committed

---

### Phase 1: Extraction P0-P1 (Triage + Initial Extraction)

**Goal:** Parse papers and extract raw structured data

**Duration:** ~6-8 prompts  
**Files Created:** ~12 files  
**Depends On:** Phase 0 complete

#### Prompts
- **1.1** — P0: PDF parser
- **1.2** — P0: Section detector
- **1.3** — P0: Study design classifier
- **1.4** — P1: Agent AG11 (full-spectrum extraction)
- **1.5** — P1: Result parsers (tables, text, figures)
- **1.6** — P1: Confidence scoring
- **1.7** — P1: review_tasks writer

#### Key Files
```
crci/
  extraction/
    p0_triage/
      pdf_parser.py
      section_detector.py
      study_classifier.py
    p1_extraction/
      agent_ag11.py       — Main extraction agent
      table_parser.py
      text_extractor.py
      confidence_scorer.py
      review_task_writer.py
```

#### What This Produces
```python
RawExtraction(
    study_id="smith_2023",
    edge_id="E042",  # stress → fatigue
    beta_raw=0.45,
    ci_lower=0.22,
    ci_upper=0.68,
    p_value=0.003,
    sample_size=234,
    study_design="prospective_cohort",
    confidence_extraction=0.85,
    spans=[...],  # Source locations in PDF
)
```

#### Verification
- Extract 3 test papers
- Verify spans match source text
- Check all 40 SpanLabel types used correctly
- Verify review_tasks created for AMBIGUOUS

---

### Phase 2: Extraction P2 (Harmonization)

**Goal:** Convert raw extractions to harmonized claims with validated types

**Duration:** ~5-6 prompts  
**Files Created:** ~8 files  
**Depends On:** Phase 1 complete

#### Prompts
- **2.1** — P2: Type router (effect_size vs RR vs OR vs HR)
- **2.2** — P2: Unit conversion system
- **2.3** — P2: CI/SE calculator
- **2.4** — P2: Harmonization validator
- **2.5** — P2: Gates P2-G1, P2-G2

#### Key Files
```
crci/
  extraction/
    p2_harmonization/
      type_router.py
      converters/
        to_cohens_d.py
        to_log_odds.py
        to_correlation.py
      ci_calculator.py
      harmonizer.py
      gates.py
```

#### What This Produces
```python
HarmonizedClaim(
    beta_harmonized=0.45,  # Cohen's d
    se_raw=0.117,          # Computed from CI
    effect_type="cohens_d",
    conversion_applied="direct",  # or "RR_to_d", etc.
    n_analyzed=234,
)
```

#### Verification
- Test conversions: OR→d, RR→d, r→d
- Verify CI→SE formulas match spec
- Check all gates raise on violation

---

### Phase 3: Extraction P3 (Heterogeneity Layering)

**Goal:** Apply 7-layer heterogeneity adjustments

**Duration:** ~7-9 prompts  
**Files Created:** ~10 files  
**Depends On:** Phase 2 complete

#### Prompts
- **3.1** — P3: Layer L1 (study design)
- **3.2** — P3: Layer L2 (population age)
- **3.3** — P3: Layer L3 (scale mismatch)
- **3.4** — P3: Layer L4 (duration)
- **3.5** — P3: Layer L5 (comorbidity)
- **3.6** — P3: Layer L6 (publication age)
- **3.7** — P3: Layer L7 (scale reliability)
- **3.8** — P3: Layer compositor
- **3.9** — P3: Gates P3-G1, P3-G2

#### Key Files
```
crci/
  extraction/
    p3_heterogeneity/
      layers/
        l1_study_design.py
        l2_population.py
        l3_scale.py
        l4_duration.py
        l5_comorbidity.py
        l6_freshness.py
        l7_reliability.py
      compositor.py
      gates.py
```

#### What This Produces
```python
CalibratedRecord(
    beta_calib=0.45,      # Unchanged (no directional shift in P3)
    se_raw=0.117,
    se_eff=0.156,         # Inflated by Π(M_i)
    multipliers={
        "L1": 1.0,   # RCT
        "L2": 1.1,   # Mixed age
        "L3": 1.0,   # No scale mismatch
        "L4": 1.15,  # 8-week study
        "L5": 1.0,   # No comorbidity
        "L6": 1.05,  # 3 years old
        "L7": 1.12,  # α=0.78
    },
    se_eff_total_multiplier=1.332,
)
```

#### Key Formula
```
SE_eff = SE_raw × M_total
M_total = Π(M_i) for i in L1..L7
```

#### Verification
- Verify SE_eff > SE_raw (P3-G1)
- Test with edge cases (missing data)
- Check multipliers come from config, not hardcoded

---

### Phase 4: Extraction P4 (Aggregation)

**Goal:** Meta-analyze multiple studies per edge

**Duration:** ~6-8 prompts  
**Files Created:** ~8 files  
**Depends On:** Phase 3 complete

#### Prompts
- **4.1** — P4: Double-counting detector
- **4.2** — P4: Overlap resolver
- **4.3** — P4: Meta-analyzer (IVW, DL, RE)
- **4.4** — P4: Publication bias tests (Egger, PET-PEESE)
- **4.5** — P4: Heterogeneity stats (I², τ², Q)
- **4.6** — P4: Prior selector (contextual vs literary)
- **4.7** — P4: Gates P4-G1, P4-G2, P4-G3

#### Key Files
```
crci/
  extraction/
    p4_aggregation/
      double_counting.py
      overlap_resolver.py
      meta_analyzer.py
      publication_bias.py
      heterogeneity_stats.py
      prior_selector.py
    p4b_publication_bias/
      egger_test.py
      pet_peese.py
```

#### What This Produces
```python
PooledEstimate(
    edge_id="E042",
    beta_pooled=0.42,      # Meta-analytic mean
    se_pooled=0.089,       # Pooled standard error
    k=5,                   # 5 studies
    i_squared=0.34,        # Moderate heterogeneity
    tau_squared=0.012,
    method="DerSimonian-Laird",
    egger_p=0.23,          # No publication bias
    prior_type="contextual",
    sigma_sq_structural=0.18,  # Annotation-informed
)
```

#### Key Formulas
```
β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)      [P4-1]
SE_pooled = sqrt(1 / Σ(1/SE²_i))        [P4-2]
τ² = max(0, (Q - (k-1)) / c)            [P4-3b DerSimonian-Laird]
```

#### Verification
- Test IVW with 3 studies (hand-compute expected)
- Verify τ² ≥ 0 always
- Check publication bias thresholds

---

### Phase 5: Algorithm (Bayesian Model + Inference)

**Goal:** Build the causal graph, compile priors, run Bayesian inference

**Duration:** ~12-15 prompts  
**Files Created:** ~20 files  
**Depends On:** Phases 0-4 complete

#### Chains
- **Chain A:** Graph Construction & Validation
- **Chain B:** Prior & Structural Variance
- **Chain C:** Posterior Update
- **Chain D:** Monte Carlo Simulation
- **Chain E:** Temporal Dynamics
- **Chain F:** Composite Scoring

#### Prompts
- **5.1-5.3** — Chain A: Graph assembly, spectral validation, freeze
- **5.4-5.6** — Chain B: Prior compilation, σ²_struct, modifier integration
- **5.7-5.9** — Chain C: Kalman-like Bayesian update (THE CORE ENGINE)
- **5.10-5.12** — Chain D: MC sampling, intervention simulation, SAFE_A/B
- **5.13-5.14** — Chain E: Trajectory prediction, recovery params
- **5.15** — Chain F: CRCI composite score

#### Key Files
```
crci/
  algorithm/
    chain_a_graph/
      assembler.py          — Build 63×63 adjacency
      spectral_validator.py — Check DAG properties
      freezer.py            — Lock model version
    chain_b_evidence/
      prior_compiler.py     — Merge literary + contextual
      structural_variance.py — σ²_struct per edge
      modifier_integrator.py
    chain_c_posterior/
      bayesian_update.py    — ★ THE CORE ★
      observation_weighter.py
      variance_propagator.py
    chain_d_simulation/
      mc_sampler.py         — 10K draws per intervention
      intervention_simulator.py
      safe_scorer.py        — SAFE_A, SAFE_B
    chain_e_temporal/
      trajectory_predictor.py
      recovery_model.py
    chain_f_analytics/
      composite_scorer.py   — CRCI final score
      subdomain_aggregator.py
```

#### What This Produces

**Compiled Model (edges_v1):**
```python
Edge(
    edge_id="E042",
    source_node_id="N12",  # stress
    target_node_id="N45",  # fatigue
    beta=0.42,             # From P4
    se_eff=0.089,
    sigma_sq_structural=0.18,
    p_inclusion=0.95,      # From sufficiency check
    prior_type="contextual",
    k_studies=5,
)
# × 118 edges
```

**Patient Inference:**
```python
def infer_patient_state(
    observations: Dict[str, float],  # {N12: 7.2, N23: 4.5, ...}
    graph: CompiledGraph,
) -> PatientState:
    """
    Formula C1-1 (Kalman-like):
    θ̂_posterior = θ̂_prior + K(y - Hθ̂_prior)
    K = P_prior @ H.T @ inv(HPH.T + R)
    """
    ...
    return PatientState(
        theta_posterior={...},  # 63 node values
        variance_posterior={...},
    )
```

**Intervention Ranking:**
```python
InterventionResult(
    intervention_id="I003",  # CBT-I
    expected_benefit=2.3,    # Points improvement
    ci_lower=1.8,
    ci_upper=2.9,
    safe_a=0.92,             # 92% prob of ANY benefit
    safe_b=0.78,             # 78% prob of MCID
    rank=1,
)
```

#### Verification (CRITICAL)
Run **V5** from CODE_QUALITY_ENFORCEMENT.md:
- Hand-compute Bayesian update for 3 nodes
- Verify MC sampler produces correct distribution
- Check CRCI score formula matches spec
- Test intervention simulator with known inputs

This is the most formula-dense phase. Every computation must match spec exactly.

---

### Phase 6: Presentation (UI + Visualizations)

**Goal:** Generate visualizations and user-facing outputs

**Duration:** ~6-8 prompts  
**Files Created:** ~10 files  
**Depends On:** Phase 5 complete

#### Prompts
- **6.1** — DAG visualizer (networkx → graphviz)
- **6.2** — Evidence browser
- **6.3** — Intervention cards
- **6.4** — Trajectory plots
- **6.5** — Variance decomposition chart
- **6.6** — Report generator

#### Key Files
```
crci/
  presentation/
    dag_visualizer.py
    evidence_browser.py
    intervention_cards.py
    trajectory_plotter.py
    variance_decomposition.py
    report_generator.py
```

#### Verification
- Generate all viz for one test patient
- Verify intervention cards show correct SAFE_A/B
- Check DAG layout is readable

---

### Phase 7: Runtime (Orchestration)

**Goal:** CLI tools and orchestration scripts

**Duration:** ~4-6 prompts  
**Files Created:** ~8 files  
**Depends On:** Phases 0-6 complete

#### Prompts
- **7.1** — Extraction pipeline orchestrator
- **7.2** — Model compilation runner
- **7.3** — Patient inference CLI
- **7.4** — Logging & monitoring
- **7.5** — Error handling & recovery

#### Key Files
```
crci/
  runtime/
    extraction_orchestrator.py
    compilation_runner.py
    inference_cli.py
    logger.py
scripts/
  run_extraction.py
  run_inference.py
  compile_model.py
```

#### Final Verification
Run **V-FINAL** from CODE_QUALITY_ENFORCEMENT.md:
- End-to-end trace: PDF → recommendation
- Verify all 118 edges populated
- Test patient inference on 5 synthetic cases
- Check CRCI scores in expected range

---

## 🛠️ How to Implement Each File

### The 6-Step Cycle

For **every single file** you implement, follow this cycle:

#### 1. READ (Before Writing Any Code)

**Read in this order:**

a. **The file's manifest entry**
   ```
   Open: FILE_CONTEXT_MANIFEST.md
   Find: Your file (e.g., "p3_heterogeneity/layers.py")
   Read: Full entry
   ```

b. **The exact spec lines**
   ```
   The manifest says "SYS_EX lines 853-920"
   Open: SYS_EXTRACTION_COMPLETE.md
   Read: ONLY lines 853-920 (that chain card)
   ```

c. **Upstream dependencies**
   ```
   The manifest lists what produces your inputs
   Read those files' CODE to see output types
   ```

d. **Downstream consumers**
   ```
   The manifest lists what consumes your outputs
   Read those files' manifest entries
   Understand what they'll need from you
   ```

e. **Anchor files** (Phase 1+ only)
   ```
   Re-read these for naming consistency:
   - shared/config.py
   - shared/models/enums.py
   - shared/models/intermediate_states.py
   ```

f. **Enforcement rules**
   ```
   Re-read: CODE_QUALITY_ENFORCEMENT.md Section 1
   All 12 rules
   ```

g. **Table dependencies** (if DB access)
   ```
   Consult: TABLE_FILL_ORDER.md
   Verify table is populated at this stage
   ```

h. **Interface schemas** (if intermediate states)
   ```
   Consult: INTERFACE_SCHEMA_LOCK.md
   Match field definitions exactly
   ```

#### 2. PLAN (Think Before Coding)

**Explicitly state:**

- ✅ **Inputs:** What types? From which file?
- ✅ **Outputs:** What types? For which file?
- ✅ **Formulas:** Which IDs from spec? (e.g., P3-5, P4-1)
- ✅ **Gates:** Which IDs must raise? (e.g., P3-G1, P4-G3)
- ✅ **Config:** Which constants needed?
- ✅ **Decisions:** Anything affecting downstream?

**Example:**
```
FILE: p3_heterogeneity/layers.py
INPUTS: HarmonizedClaim (from p2_harmonization/harmonizer.py)
OUTPUTS: CalibratedRecord (for p4_aggregation/meta_analyzer.py)
FORMULAS: P3-5 (multiplier composition), P3-8 (SE_eff calculation)
GATES: P3-G1 (SE_eff > SE_raw)
CONFIG: LAYER_L2_AGE_THRESHOLD, LAYER_L4_DURATION_REF, etc.
DECISIONS: If study_design missing, use PROSPECTIVE_COHORT default
```

#### 3. IMPLEMENT (Write the Code)

**Follow ALL 12 enforcement rules:**

##### Rule 1: No Hardcoded Formula Parameters
```python
# ❌ WRONG
se_eff = se_raw * 1.15

# ✅ CORRECT
se_eff = se_raw * config.LAYER_L4_MULTIPLIER_MEDIUM
```

##### Rule 2: No Invented Formulas
```python
# ❌ WRONG
result = some_calculation()  # Where's this from?

# ✅ CORRECT
# Formula P3-5: M_total = Π(M_i) for i in 1..7
m_total = np.prod([m1, m2, m3, m4, m5, m6, m7])
```

##### Rule 3: No Stubs
```python
# ❌ WRONG
def compute_egger():
    pass  # TODO

# ✅ CORRECT
def compute_egger(...):
    # Full implementation
    ...
    
# OR if dependency doesn't exist yet:
def compute_egger(...):
    raise NotImplementedError(
        "Requires heterogeneity_stats.py from Phase 4"
    )
```

##### Rule 4: Explicit Imports
```python
# ✅ CORRECT
from shared.models.intermediate_states import HarmonizedClaim
from shared.models.enums import StudyDesign, AggregationMethod
from shared.config import SIGMA_SQ_STRUCTURAL_DEFAULT
```

##### Rule 5: Typed Signatures
```python
# ❌ WRONG
def process(data):
    ...

# ✅ CORRECT
def process(data: HarmonizedClaim) -> CalibratedRecord:
    ...
```

##### Rule 6: Gates Must Raise
```python
# ❌ WRONG
if se_eff < se_raw:
    logger.warning("SE_eff less than SE_raw")
    se_eff = se_raw  # silent fix

# ✅ CORRECT
if se_eff < se_raw:
    raise GateViolation(
        "P3-G1",
        f"SE_eff {se_eff:.4f} < SE_raw {se_raw:.4f} "
        f"for study {study_id}"
    )
```

##### Rule 7: Log Defaults
```python
# ❌ WRONG
sigma_sq = 0.25  # default

# ✅ CORRECT
sigma_sq = config.SIGMA_SQ_STRUCTURAL_DEFAULT
logger.info(
    f"Edge {edge_id}: σ²_struct defaulting to "
    f"{sigma_sq} — no annotations available"
)
```

##### Rule 8: Explicit DB Columns
```python
# ❌ WRONG
query = select(EdgeEvidence)

# ✅ CORRECT
query = select(
    EdgeEvidence.beta,
    EdgeEvidence.se,
    EdgeEvidence.study_design,
    EdgeEvidence.year,
)
```

##### Rule 9: Validate DB Writes
```python
# ✅ CORRECT
assert hasattr(row, 'sigma_sq_structural'), \
    "Missing σ²_struct column"
assert 0 <= row.sigma_sq_structural <= \
    config.SIGMA_SQ_STRUCTURAL_CEILING, \
    f"σ²_struct {row.sigma_sq_structural} out of bounds"
```

##### Rule 10: Seed Randomness
```python
# ❌ WRONG
samples = np.random.normal(mu, sigma, size=10000)

# ✅ CORRECT
def mc_simulate(mu, sigma, n_draws=10000, seed=42):
    rng = np.random.default_rng(seed)
    samples = rng.normal(mu, sigma, size=n_draws)
    ...
```

##### Rule 11: File Docstring
```python
"""
Component: SYS_EXTRACTION.EX-P3.P3-LAYERS
Spec: SYS_EXTRACTION_COMPLETE.md lines 853-920
Formulas: P3-5, P3-8
Reads: HarmonizedClaim (from p2_harmonization/harmonizer.py)
Writes: CalibratedRecord (consumed by p4_aggregation/meta_analyzer.py)
Gates: P3-G1
Dependencies: shared/config.py, shared/models/intermediate_states.py
"""
```

##### Rule 12: Exact Column Names
Already covered in Rule 8

#### 4. VERIFY (Mandatory — Never Skip)

**Run ALL these checks:**

##### a. Formula Accuracy
```
✅ Re-read spec lines
✅ Compare formula character-by-character
✅ Spec equation = code implementation (exact match)
```

##### b. Backward Coherence
```
✅ Read upstream file that produces your input
✅ Verify output type matches your input type
✅ Verify field names match exactly
✅ Verify no data silently dropped at boundary
```

##### c. Forward Coherence
```
✅ Read manifest entry for downstream file
✅ Verify your output type has all needed fields
✅ Verify naming matches downstream expectations
✅ Verify no structural decisions force downstream hacks
```

##### d. Hardcode Scan
```
✅ grep for float literals in your file
✅ If any is a formula parameter, move to config
```

##### e. Gate Enforcement
```
✅ For every gate in manifest, verify code raises
✅ Test with violation conditions
```

##### f. Review Tasks
```
✅ If manifest says file emits review_tasks, verify
✅ Check writes to review_tasks table
```

##### g. Import Validity
```
✅ Every import references existing module
✅ OR documented as future dependency with NotImplementedError
```

#### 5. WRITE TESTS (Formula-Dense Files)

**For these files:**
- `layers.py`
- `meta_analyzer.py`
- `bayesian_update.py`
- `mc_sampler.py`
- `composite_scorer.py`
- Any file marked "formula-dense" in manifest

**Create `tests/test_[module].py` with:**

```python
def test_ivw_meta_analysis_three_studies():
    """Hand-computed expected value for IVW."""
    # Study 1: β=0.40, SE=0.10 → weight=100
    # Study 2: β=0.50, SE=0.15 → weight=44.4
    # Study 3: β=0.35, SE=0.20 → weight=25
    # Expected: β̂_IVW = (0.40×100 + 0.50×44.4 + 0.35×25) / 169.4
    #                  = 0.421
    
    studies = [
        CalibratedRecord(beta_calib=0.40, se_eff=0.10, ...),
        CalibratedRecord(beta_calib=0.50, se_eff=0.15, ...),
        CalibratedRecord(beta_calib=0.35, se_eff=0.20, ...),
    ]
    
    result = compute_ivw(studies)
    
    assert abs(result.beta_pooled - 0.421) < 0.001
    assert abs(result.se_pooled - 0.077) < 0.001  # 1/sqrt(169.4)

def test_gate_p4_g1_raises_on_zero_studies():
    """Gate P4-G1: Must have k ≥ 1."""
    with pytest.raises(GateViolation, match="P4-G1"):
        compute_ivw([])

def test_no_hardcoded_constants():
    """Verify constants come from config."""
    # Parse source file, check for float literals
    ...
```

#### 6. LOG VERIFICATION

**Add verification stamp at top of file:**

```python
# VERIFIED: formulas P3-5, P3-8 match spec lines 853-920
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads HarmonizedClaim from harmonizer.py
# VERIFIED: forward wiring — writes CalibratedRecord for meta_analyzer.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gate P3-G1 raises on failure
# VERIFIED: tests written with hand-computed expected values
```

---

## ✅ Quality Gates & Verification

### Phase Boundary Verification

After completing **ALL prompts** in a phase, run corresponding verification:

| After Phase | Run Verification | What It Checks |
|-------------|------------------|----------------|
| **Phase 0** | **V0** | Schema consistency, model imports, enum values, config complete |
| **Phase 1** | **V1** | Extraction wiring, span validation, review_tasks |
| **Phase 2** | **V2** | Formula audit (conversions, CI→SE) |
| **Phase 3** | **V2** | Formula audit (layers, multipliers) |
| **Phase 4** | **V2** | Formula audit (meta-analysis) |
| **Phase 5** | **V5** | ★ Mathematical correctness (THE BIG ONE) |
| **Phase 6** | **V6** | Presentation wiring, viz generation |
| **Phase 7** | **V-FINAL** | End-to-end trace, all 118 edges, patient inference |

### V5: Mathematical Correctness (Phase 5)

**This is the most critical verification. Run after Phase 5 completes.**

#### What to Check

1. **Bayesian Update**
   ```
   ✅ Hand-compute posterior for 3-node graph
   ✅ Verify Kalman gain formula matches spec
   ✅ Test with missing observations
   ✅ Verify variance propagation
   ```

2. **MC Sampler**
   ```
   ✅ Verify draws from correct distribution
   ✅ Test with known μ, σ → check empirical mean/SD
   ✅ Verify seed reproducibility
   ```

3. **CRCI Score**
   ```
   ✅ Hand-compute for synthetic patient
   ✅ Verify severity weights sum to 1.0
   ✅ Test edge cases (all zeros, all maxes)
   ```

4. **Intervention Simulator**
   ```
   ✅ Verify path effects propagate correctly
   ✅ Test SAFE_A, SAFE_B thresholds
   ✅ Check intervention kernels applied
   ```

#### How to Run
```bash
python scripts/verify_phase5.py
```

**Outputs:**
- ✅ All checks passed → commit and move to Phase 6
- ❌ Any check failed → fix and re-run

### V-FINAL: End-to-End System Test

**Run this after Phase 7 completes.**

#### Test Sequence

1. **Extract 5 test papers**
   ```bash
   python run_extraction.py data/test_papers/*.pdf
   ```
   
   **Verify:**
   - All 5 papers processed without error
   - `edge_evidence_v1` has new rows
   - `review_tasks` created for ambiguous cases

2. **Compile model**
   ```bash
   python compile_model.py
   ```
   
   **Verify:**
   - `edges_v1` has 118 rows (all edges)
   - Each edge has β, SE_eff, σ²_struct, P_inclusion
   - No NULLs in critical columns

3. **Run patient inference**
   ```bash
   python run_inference.py --patient test_cases/patient_01.json
   ```
   
   **Verify:**
   - Posterior computed for all 63 nodes
   - CRCI score in range [0, 100]
   - Top 5 interventions ranked

4. **Generate visualizations**
   ```bash
   python generate_report.py --patient test_cases/patient_01.json
   ```
   
   **Verify:**
   - DAG visualization created
   - Intervention cards generated
   - Trajectory plot rendered

5. **Mathematical spot-checks**
   ```python
   # Pick one edge manually
   edge = edges_v1[42]  # E042: stress → fatigue
   
   # Verify β is mean of studies
   studies = edge_evidence_v1.filter(edge_id="E042")
   expected_beta = compute_ivw_by_hand(studies)
   assert abs(edge.beta - expected_beta) < 0.01
   
   # Verify SE_eff > SE_raw for all studies
   for study in studies:
       assert study.se_eff >= study.se_raw
   ```

**If all pass:** System is v1 complete. Ready for science project. 🎉

---

## 🔧 Troubleshooting & Common Issues

### Issue: "Gate P3-G1 violation: SE_eff < SE_raw"

**Cause:** A layer multiplier is < 1.0, which should never happen.

**Fix:**
1. Check which layer returned M_i < 1.0
2. Verify that layer's formula in spec
3. All P3 multipliers should be ≥ 1.0 (widen uncertainty)

### Issue: "Cannot import shared.models.intermediate_states"

**Cause:** Phase 0 not complete or not on PYTHONPATH.

**Fix:**
```bash
export PYTHONPATH="/workspaces/in-silico-crci-lab:$PYTHONPATH"
# OR
cd /workspaces/in-silico-crci-lab
pip install -e crci/
```

### Issue: "Table edges_v1 is empty after compilation"

**Cause:** No evidence in `edge_evidence_v1`, or sufficiency gate (P5) blocking all edges.

**Fix:**
1. Check `SELECT COUNT(*) FROM edge_evidence_v1` — should be > 0
2. Check `SELECT * FROM edges_v1 WHERE p_inclusion < 0.50` — P5-G1 threshold
3. Lower P_inclusion threshold for testing, or extract more papers

### Issue: "Formula result doesn't match spec"

**Cause:** Most common — hardcoded constant instead of config import.

**Fix:**
1. Run hardcode scan: `grep -n "\b[0-9]*\.[0-9]\+" your_file.py`
2. For each match, verify it's from config or a structural constant
3. Example: Change `0.25` → `config.SIGMA_SQ_STRUCTURAL_DEFAULT`

### Issue: "Bayesian update produces NaN"

**Cause:** Variance matrix not positive definite, or division by zero.

**Fix:**
1. Check observation covariance R — must be > 0
2. Check prior covariance P — must be positive definite
3. Add numerical stability: `R = R + 1e-6 * np.eye(len(R))`

### Issue: "MC sampler runs forever"

**Cause:** Simulation not converging, or n_draws too high.

**Fix:**
1. Start with n_draws=1000 for testing
2. Increase to 10,000 only after verification
3. Check for infinite loops in intervention propagation

### Issue: "Review task not created for ambiguous span"

**Cause:** Condition check for AMBIGUOUS not correct.

**Fix:**
1. Verify confidence threshold: `if confidence < config.AMBIGUOUS_THRESHOLD`
2. Check `review_tasks` table write code
3. Test with known ambiguous case

### Issue: "CRCI score always returns 50"

**Cause:** Severity weights not loading, or subdomain aggregation broken.

**Fix:**
1. Check `instruments_v1` table has severity_weight column
2. Verify weights sum to 1.0 per subdomain
3. Check subdomain_aggregator.py logic

---

## 📞 Need Help?

### Quick Reference

- **What am I building?** → Section 2 (What You're Building)
- **Which file next?** → PROMPT_SEQUENCE.md (follow numbered prompts)
- **How to implement a file?** → Section 5 (How to Implement Each File)
- **What does this formula mean?** → SYS_EXTRACTION_COMPLETE.md or SYS_ALGORITHM_COMPLETE.md (search for formula ID)
- **What columns in this table?** → 05_TABLE_SCHEMAS.md
- **What's this enum value?** → 11_CONTROLLED_VOCABULARIES.md
- **When is this table populated?** → TABLE_FILL_ORDER.md

### Document Quick Links

| Need | Document |
|------|----------|
| High-level architecture | IMPLEMENTATION_BLUEPRINT_v1.1.md |
| Step-by-step prompts | PROMPT_SEQUENCE.md |
| Per-file instructions | FILE_CONTEXT_MANIFEST.md |
| Extraction formulas | SYS_EXTRACTION_COMPLETE.md |
| Algorithm formulas | SYS_ALGORITHM_COMPLETE.md |
| Database schemas | 05_TABLE_SCHEMAS.md |
| Enum definitions | 11_CONTROLLED_VOCABULARIES.md |
| Quality rules | CODE_QUALITY_ENFORCEMENT.md |

---

## 🎯 Success Criteria

**You'll know v1 is complete when:**

✅ All 7 phases complete  
✅ All verification prompts (V0, V1, V2, V5, V6, V-FINAL) pass  
✅ Can extract 50-200 papers end-to-end  
✅ `edges_v1` table has 118 populated rows  
✅ Can run patient inference and get CRCI score  
✅ Can generate intervention rankings  
✅ Can produce all visualizations  
✅ Mathematical spot-checks match hand calculations  
✅ No hardcoded formula constants  
✅ All gates raise on violations  
✅ All formulas have ID comments  

**Then:** You have a working CRCI prediction system ready for scientific publication. 🚀

---

## 📝 Version History

- **v1.0** (2026-02-25) — Initial comprehensive guide

---

**Next Step:** Read [IMPLEMENTATION_BLUEPRINT_v1.1.md](IMPLEMENTATION_BLUEPRINT_v1.1.md), then start [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompt 0.1.
