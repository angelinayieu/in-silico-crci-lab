# Implementation Plan: Clinical CRCI Risk Percentage with Domain Decomposition

> **Objective:** Convert the current z-score / percentile output into a
> model-derived **"X%–Y% probability of clinically significant CRCI"**
> with a transparent per-domain weighting breakdown.
>
> **Status:** Blocked on vertical slice (NB08) producing stable posterior
> domain draws. Do not implement F4 until that precondition is met.

---

## 0. Precondition: Vertical Slice Stability

**This module must NOT be built until the end-to-end slice produces coherent
domain-level z posteriors.** Specifically, F4 requires:

1. **Posterior sampling is stable:** `bayesian_update.py` (C3) produces a
   positive-definite Σ_post and `mc_sampler.py` (D1c) generates draws
   θ^(m) ~ N(θ̂, Σ_post) that pass Gate D-G1 without jitter fallback.

2. **Orientation is verified:** All `NODE_COG_*` nodes are confirmed
   POS_UP (higher = better) in the loaded NodeMap. A hard gate (§4.6)
   must enforce this at runtime — if even one cognitive node has
   inverted orientation, risk thresholds flip silently.

3. **Domain mapping coverage is validated:** Every node_id in
   `CRCI_DOMAIN_NODE_MAP` (§4.1) resolves to a valid index in the
   loaded NodeMap. Missing nodes → the module must refuse to produce
   a risk estimate rather than silently undercount.

4. **At least one extraction round populates cognitive-domain edges**
   so the posterior on `NODE_COG_*` is data-informed rather than purely
   prior-driven. A risk estimate from uninformative priors is
   mathematically valid but clinically meaningless.

If any of these fail, F4 will produce confident-looking but invalid numbers.

---

## 1. Why the Current Output Is Not Enough

The system currently produces:

| Output | Module | What it is |
|--------|--------|------------|
| `crci_composite` (z-score) | `composite_scorer.py` (F1) | IVW-weighted mean of 11 domain z-scores |
| `percentile` | `composite_scorer.py` (F1) | Φ(−z) × 100 — population-normed rank |
| `severity_tier` | `composite_scorer.py` (F1) | 6-level categorical (EXCELLENT → SEVERE) |
| `subdomain_scores` | `composite_scorer.py` (F1) | Per-domain z-scores (dict) |
| `subdomain_weights` | `composite_scorer.py` (F1) | Per-domain IVW weights (1/σ²_d) |

**Problem:** A z-score of −1.3 or a percentile of 90.3 does not answer the clinical
question: *"What is this patient's probability of meeting criteria for clinically
significant cognitive impairment?"*

**What the system should produce:** A posterior predictive event probability —
`P̂(CRCI | patient data, model)` — expressed as a percentage with a simulation
uncertainty interval, decomposed by cognitive domain to show which domains
drive the risk.

**Important caveat:** This is a *model-derived* probability, not a clinically
calibrated incidence rate. See §5.3 (Calibration) for what "clinically calibrated"
would require and why we explicitly label the output as uncalibrated.

---

## 2. Scientific Framework

### 2.1 Defining "Clinically Significant CRCI"

CRCI is operationalized using criteria from the ICCTF (International Cognition
and Cancer Task Force):

> **CRCI positive** if ≥2 test scores ≤ −1.5 SD below age-adjusted norms,
> OR ≥1 test score ≤ −2.0 SD.

Reference: Wefel JS, Vardy J, Ahles T, Schagen SB. International Cognition
and Cancer Task Force recommendations to harmonise studies of cognitive function
in patients with cancer. *Lancet Oncol.* 2011;12(7):703-708.

**Approximation declared:** The ICCTF criteria are defined at the level of
individual *test scores* (e.g., Trail Making B raw time, Hopkins Verbal Learning
Trial 1-3 total). Our implementation applies them at the *domain* level
(posterior z-score per cognitive domain node, each of which may aggregate
multiple test instruments). This is a common simplification in computational
models but is less conservative than test-level classification — domain
averaging can dilute impairment in a single test when other tests in the
same domain are near-normal.

**MVP policy: domain-level with min-aggregation option.** For domains with
multiple underlying node_ids (e.g., if `processing_speed` maps to both
`NODE_COG_PROC_SPEED` and a future sub-node), we will also compute
`min(z_nodes)` within the domain as an alternative criterion (closer to
the test-level ICCTF intent). **This is min over DAG node z-scores within
the domain, NOT min over individual test instruments** — test-level draws
do not exist until the measurement model (§8.9) is implemented. Both the
mean and the min across node_ids will be stored; the primary reporting
metric is configurable.

```python
# In config.py
CRCI_THRESHOLD_MULTI_DOMAIN_Z: float = -1.5    # z ≤ this in ≥2 domains
CRCI_THRESHOLD_MULTI_DOMAIN_COUNT: int = 2      # min domains below threshold
CRCI_THRESHOLD_SINGLE_DOMAIN_Z: float = -2.0    # z ≤ this in ≥1 domain
CRCI_DOMAIN_AGGREGATION: str = "mean"           # "mean" or "min" — per-domain node summary
# NOTE: both modes aggregate over node_ids, NOT individual test scores.
# Test-level classification requires §8.9 measurement model.
```

### 2.2 What We Are Sampling (and What We Are Not)

The system currently produces two distinct sets of draws. It is critical to
use the correct one:

| Draw source | Variable | Meaning | When to use |
|---|---|---|---|
| `mc_sampler.py` D1c | `theta0_draws` | θ^(m) ~ N(θ̂, Σ_post) | **Current cognitive state** conditioned on observations y_{≤t} |
| `intervention_overlay.py` E3 | trajectory draws at t+Δ | θ_{t+Δ} given interventions | **Future cognitive state** (predictive) |

**For "current CRCI probability given observed patient data":**
Use `theta0_draws` from D1c. Despite the misleading name `theta0` (which
suggests "baseline"), these draws sample from the *posterior* distribution
N(θ̂, Σ_post) where θ̂ is the Bayesian-updated patient state after all
observations. This is P(θ_t | y_{≤t}) — the posterior over the patient's
current latent cognitive state.

**For "future CRCI risk under intervention":**
Use Chain E trajectory draws at target timepoints. This is a separate
computation not covered in the MVP (see §8.2).

**For "pre-treatment baseline risk":**
Re-run with prior only (no patient observations). This would require a
separate sampling pass and is not the default mode.

The risk estimator's function signature and docstring must state explicitly
which conditioning set the output refers to.

### 2.3 Computing P̂(CRCI | data, model) via Monte Carlo

**Method — Monte Carlo event-rate estimation over posterior draws:**

For each MC draw $m = 1, \ldots, M$:

1. Extract per-domain z-scores $z_d^{(m)}$ from draw $\theta^{(m)}$
   using the canonical domain → node mapping
2. Apply ICCTF criteria:
   $$\text{CRCI}^{(m)} = \mathbb{1}\left[\sum_d \mathbb{1}(z_d^{(m)} \leq z_{\text{multi}}) \geq k_{\text{multi}}\right] \;\lor\; \mathbb{1}\left[\exists\, d : z_d^{(m)} \leq z_{\text{single}}\right]$$
3. Compute the point estimate:
   $$\hat{P}(\text{CRCI}) = \frac{1}{M} \sum_{m=1}^{M} \text{CRCI}^{(m)}$$

**This is posterior predictive risk estimated by Monte Carlo from the posterior
state distribution.** The MC draws incorporate evidence uncertainty (via edge
weight sampling D1a), structural uncertainty (via inclusion sampling D1b),
and patient-state uncertainty (via Cholesky posterior sampling D1c).

It is **not** "exact Bayesian inference" — the MC draws are an approximation
to the true posterior predictive. The approximation quality depends on:
- The adequacy of the DAG structural assumptions
- The accuracy of the prior specifications (Chain B)
- The number of MC draws (simulation variance)
- The domain-level aggregation approximation (§2.1)

### 2.4 Interval Estimation — Two Options

The naive formula $\hat{P} \pm z_\alpha \sqrt{\hat{P}(1-\hat{P})/M}$ is a
**Monte Carlo standard error interval** — it quantifies simulation noise in
the estimator, not posterior uncertainty over the probability itself. It
answers "how precisely have we estimated this probability given M draws?"
not "what is the credible range of the true probability?"

We provide two intervals, clearly labeled:

#### A. MC Simulation Error Interval (always reported)

$$\text{MC-SE interval}_{90\%} = \hat{P} \pm 1.645 \sqrt{\hat{P}(1-\hat{P})/M}$$

This shrinks with more draws. With M=10,000, it is typically < ±1 pp wide.
Labeled as "simulation precision" in the output.

#### B. Smoothed Posterior Interval (Jeffreys Beta — primary display)

Using a Jeffreys prior on the event rate:

$$P \sim \text{Beta}(S + 0.5, F + 0.5)$$

where $S = \sum_m \text{CRCI}^{(m)}$ and $F = M - S$.

The 90% interval is $[\text{Beta}^{-1}(0.05), \text{Beta}^{-1}(0.95)]$.

This is a **pragmatic smoothing approximation** — it treats the MC event
counts as exchangeable Bernoulli draws and places a weakly informative prior.
It is NOT the model's posterior over a probability parameter (the model has no
such parameter). We use it because:
- It handles edge cases (P̂ = 0 or P̂ = 1) gracefully
- It is well-calibrated for proportion estimation
- It is the standard interval in clinical incidence reporting

Labeled as "Jeffreys interval" in the output, not "credible interval."

```python
CRCI_RISK_INTERVAL_METHOD: str = "jeffreys"   # "jeffreys" or "mc_se"
CRCI_RISK_CI_LEVEL: float = 0.90              # interval width
```

### 2.5 Per-Domain Risk Decomposition

Three complementary views, each answering a different question:

#### A. Marginal Domain Impairment Probability

$$P_d = \frac{1}{M} \sum_{m=1}^{M} \mathbb{1}(z_d^{(m)} \leq z_{\text{multi}})$$

Answers: *"What is the probability that this specific domain is impaired?"*

Reported per domain, directly interpretable. These probabilities do **not**
sum to any particular value — they are marginal, not conditional.

#### B. Trigger-Share Attribution (MVP heuristic)

For each draw where CRCI is positive, identify which domain(s) triggered it
and split credit equally:

$$\phi_d = \frac{1}{M \cdot \hat{P}} \sum_{m : \text{CRCI}^{(m)}=1} \frac{\mathbb{1}(z_d^{(m)} \leq z_{\text{thresh}})}{N_{\text{triggered}}^{(m)}}$$

Where $N_{\text{triggered}}^{(m)}$ is the count of domains below threshold in
draw $m$. $\sum_d \phi_d = 1.0$.

**This is NOT a Shapley value.** It is a trigger-share heuristic that equally
divides a positive event among triggering domains. True Shapley values would
require permutation sampling over domain subsets and computing marginal
contributions — feasible but O(K! × M) and unnecessary for MVP.

Labeled as "trigger-share (equal split among triggering domains)" in the
output. If we later need proper Shapley, the upgrade path is:
permutation-based marginal complementarity analysis over domain coalitions.

#### C. IVW Precision Weight Percentage

$$w_d^{\%} = \frac{w_d}{\sum_{d'} w_{d'}} \times 100$$

where $w_d = 1/\sigma^2_d$ from `CompositeState.subdomain_weights` (F1).

Answers: *"How much does measurement precision in this domain influence the
composite score?"* This is a property of the evidence base and measurement
quality, NOT a risk contribution. Displayed separately under "Precision
Influence" — not mixed with risk attribution.

### 2.6 Missingness Handling

ICCTF criteria assume a complete neuropsychological battery. Our model will
frequently have domains where no tests were directly observed (the posterior
for those nodes is prior-driven via the DAG).

**Policy: Latent-completion with coverage flag.**

1. All 10 cognitive domain nodes have posterior draws from N(θ̂, Σ_post),
   whether or not they were directly observed. Unobserved nodes are
   imputed through the DAG's covariance structure — this is inherent to
   the Bayesian update (C3a adds zero precision for unobserved nodes,
   so they stay at prior + cross-covariance contributions).

2. The risk estimate reports a **coverage fraction**: the proportion of
   the 10 domains that had at least one direct observation (fusion level
   L2 or L3 from C3c).

   **Definition of "directly observed" (reproducible criterion):**
   A domain is "directly observed" if **at least one** of its mapped
   node_ids received a non-zero precision increment during C3a Bayesian
   update — i.e., the C3c `fusion_levels` dict records that node at
   fusion level L2 (direct scalar observation) or L3 (multi-source
   fusion). This covers:
   - **Neuropsychological test scores** (e.g., TMT-B raw time mapped to
     `NODE_COG_PROC_SPEED`) — qualifies as L2/L3
   - **Self-report PROMs** (e.g., FACT-Cog mapped to a cognitive node)
     — qualifies as L2/L3
   - **Biomarker assays** (e.g., BDNF level mapped to `NODE_BIO_BDNF`)
     — qualifies as L2/L3, but note that biomarker nodes are typically
     upstream of cognitive nodes (Layer 3), not cognitive domains
     themselves (Layer 5)

   Observation classes that do NOT count toward domain coverage:
   - L0 (unobserved — node stays at prior)
   - L1 (indirect only — informed via DAG covariance, no direct data)

   **Partial observation policy:** If a domain maps to multiple node_ids
   and only some are directly observed, the domain is marked as
   `is_directly_observed = True` but `n_observations` records how many
   of its constituent nodes had L2+ data. This enables downstream
   consumers to distinguish "fully observed" from "partially observed"
   domains.

3. If coverage < 50% (fewer than 5 of 10 domains directly observed),
   the output is flagged with:
   - `low_coverage_warning: True`
   - Risk tier forced to append "(low coverage)" suffix
   - Presentation shows prominent disclosure

This avoids systematic underestimation (observed-only policy) while being
transparent about when the estimate is predominantly model-driven vs
data-informed.

```python
CRCI_RISK_MIN_COVERAGE: float = 0.50  # flag if < 50% domains observed
```

---

## 3. Architecture — Where This Fits

### 3.1 Data Flow

```
                     EXISTING                               NEW
                    ─────────                              ─────
bayesian_update.py ──→ θ̂, Σ_post ──┐
                                    │
mc_sampler.py ──→ theta0_draws ─────┤
  (posterior samples at time t)     ├──→ risk_estimator.py ──→ CRCIRiskEstimate
                                    │          │
node_loader.py ──→ NodeMap ─────────┘          │
  (orientation + index resolution)             │
                                               ↓
composite_scorer.py ──→ CompositeState ──→ risk_estimator.py (IVW weights only)
                                               │
                                               ↓
                                      output_contracts.py
                                      (ClinicalRiskProfile)
                                               │
                                               ↓
                                      risk_dashboard.py (PRES)
```

### 3.2 New Module: `crci/algorithm/chain_f_analytics/risk_estimator.py`

**Input:**
- `MCDraws.theta0_draws` — (M × n_nodes) posterior draws at time t
- `NodeMap` — for node_id → index resolution and orientation validation
- `CompositeState` — for IVW weights (view C only)
- `FusionLevels` from C3c — for coverage computation

**Output:** `CRCIRiskEstimate` (consumed by report_assembler, presentation)

This module sits after F1 (composite_scorer) and alongside F2/F3 in the
analytics layer. It does NOT replace F1 — it adds a clinical-interpretation
layer using the same MC draws.

### 3.3 Files to Create / Modify

| File | Action | Description |
|------|--------|-------------|
| `crci/algorithm/chain_f_analytics/risk_estimator.py` | **CREATE** | Core risk computation module |
| `crci/shared/config.py` | MODIFY | Add CRCI threshold + policy constants |
| `crci/shared/models/output_contracts.py` | MODIFY | Add `ClinicalRiskProfile` model |
| `crci/runtime/report_assembler.py` | MODIFY | Wire risk_estimator into report assembly |
| `crci/presentation/risk_dashboard.py` | **CREATE** | Render risk % gauge + domain breakdown |
| `tests/test_algorithm/test_risk_estimator.py` | **CREATE** | Unit tests with hand-computable cases |

---

## 4. Detailed Implementation

### 4.1 `config.py` — New Constants

```python
# ═══════════════════════════════════════════════════════════════
#  F4: CLINICAL RISK ESTIMATION (ICCTF-based)
# ═══════════════════════════════════════════════════════════════

# ICCTF criteria: CRCI positive if ≥2 domain scores ≤ -1.5 SD, OR ≥1 ≤ -2.0 SD
# Reference: Wefel et al. (2011), Lancet Oncol 12(7):703-708
# Approximation: applied at domain-level, not individual test-level (§2.1)
CRCI_THRESHOLD_MULTI_DOMAIN_Z: float = -1.5
CRCI_THRESHOLD_MULTI_DOMAIN_COUNT: int = 2
CRCI_THRESHOLD_SINGLE_DOMAIN_Z: float = -2.0

# Domain aggregation method: "mean" (average z across domain nodes) or
# "min" (worst z within domain — closer to ICCTF test-level intent)
CRCI_DOMAIN_AGGREGATION: str = "mean"

# Interval estimation method: "jeffreys" (Beta posterior) or "mc_se" (normal)
CRCI_RISK_INTERVAL_METHOD: str = "jeffreys"
CRCI_RISK_CI_LEVEL: float = 0.90

# Minimum MC draws for stable risk estimate (gate F-G4)
CRCI_RISK_MIN_DRAWS: int = 1000

# Coverage: minimum fraction of domains with direct observations
CRCI_RISK_MIN_COVERAGE: float = 0.50

# Risk communication tiers (communication-only defaults, not evidence-based)
# These are display labels for clinical communication. They are NOT tied
# to epidemiological prevalence or cost-utility thresholds.
CRCI_RISK_TIER_LOW: float = 15.0       # < 15% → LOW
CRCI_RISK_TIER_MODERATE: float = 30.0  # 15-30% → MODERATE
CRCI_RISK_TIER_ELEVATED: float = 50.0  # 30-50% → ELEVATED
CRCI_RISK_TIER_HIGH: float = 70.0      # 50-70% → HIGH
# ≥ 70% → VERY HIGH

# Cognitive domain → node_id mapping (canonical, from NODE_REGISTRY)
# All nodes are POS_UP z-score type — this is validated at runtime by Gate F-G4a
CRCI_DOMAIN_NODE_MAP: dict[str, list[str]] = {
    "processing_speed": ["NODE_COG_PROC_SPEED"],
    "sustained_attention": ["NODE_COG_ATTN_SUSTAINED"],
    "selective_attention": ["NODE_COG_ATTN_SELECTIVE"],
    "working_memory": ["NODE_COG_WORK_MEM"],
    "episodic_memory": ["NODE_COG_EPISODIC_MEM"],
    "verbal_fluency": ["NODE_COG_VERBAL_FLUENCY"],
    "executive_planning": ["NODE_COG_EXEC_PLANNING"],
    "executive_inhibition": ["NODE_COG_EXEC_INHIBITION"],
    "visuospatial": ["NODE_COG_VISUOSPATIAL"],
    "language": ["NODE_COG_LANGUAGE"],
}
# Note: NODE_COMP_CRCI is the composite output — not included as domain input
# Note: mood/fatigue are upstream drivers (symptom_burden), not ICCTF diagnostic domains
```

### 4.2 `risk_estimator.py` — Core Module

```python
"""
Component: SYS_ALGORITHM.ALG-F.F4
Spec: IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md §2–4
Formulas:
    F4-1: CRCI^(m) = 1[Σ_d 1(z_d^(m) ≤ z_multi) ≥ k_multi] ∨ 1[∃d: z_d^(m) ≤ z_single]
    F4-2: P̂(CRCI) = (1/M) Σ_m CRCI^(m)
    F4-3a: MC-SE = √(P̂(1−P̂)/M)  (simulation error)
    F4-3b: P ~ Beta(S+0.5, F+0.5)  (Jeffreys interval)
    F4-4: P_d = (1/M) Σ_m 1(z_d^(m) ≤ z_multi)  (marginal domain impairment)
    F4-5: φ_d = trigger-share heuristic  (NOT Shapley — see §2.5B)
    F4-6: w_d% = w_d / Σw × 100  (IVW precision weight)
Reads: MCDraws.theta0_draws (from D1 — posterior samples at time t),
       NodeMap (from A1 — index + orientation), CompositeState (from F1 — IVW weights),
       fusion_levels (from C3c — coverage)
Writes: CRCIRiskEstimate (consumed by report_assembler.py, risk_dashboard.py)
Gates: F-G4 (orientation check, coverage check, finiteness, consistency)
Approximations declared:
    - Domain-level aggregation in place of individual test scores (§2.1)
    - Trigger-share attribution in place of true Shapley values (§2.5B)
    - Jeffreys Beta smoothing in place of model-structural posterior (§2.4B)
    - No clinical calibration (§5.3) — output is model-derived, not calibrated
"""
```

**Key data structures:**

```python
@dataclass
class DomainRiskProfile:
    """Risk profile for a single cognitive domain."""
    domain_id: str
    domain_label: str
    node_ids: list[str]
    marginal_risk_pct: float          # P_d × 100 — Formula F4-4
    trigger_share_pct: float          # φ_d × 100 — Formula F4-5 (NOT Shapley)
    ivw_weight_pct: float             # w_d% — Formula F4-6 (precision influence)
    mean_z: float                     # E[z_d] across MC draws
    sd_z: float                       # SD[z_d] across MC draws
    z_5th: float                      # 5th percentile of z_d draws
    z_95th: float                     # 95th percentile of z_d draws
    is_directly_observed: bool        # True if node had L2+ fusion level
    n_observations: int               # Number of direct observations on this domain

@dataclass
class CRCIRiskEstimate:
    """Complete clinical risk estimate output.

    risk_pct is a model-derived probability, not a clinically calibrated rate.
    See calibration_status field and §5.3 of the implementation plan.
    """
    # Primary risk estimate
    risk_pct: float                   # P̂(CRCI) × 100 — Formula F4-2
    risk_lower_pct: float             # Interval lower bound
    risk_upper_pct: float             # Interval upper bound
    risk_tier: str                    # LOW / MODERATE / ELEVATED / HIGH / VERY_HIGH
    risk_range_text: str              # "32%–41%"

    # Interval metadata
    interval_method: str              # "jeffreys" or "mc_se"
    interval_level: float             # 0.90
    mc_se: float                      # simulation standard error (always computed)
    n_draws_used: int

    # Coverage
    coverage_fraction: float          # fraction of 10 domains directly observed
    low_coverage_warning: bool        # True if coverage < MIN_COVERAGE

    # Domain decomposition
    domain_profiles: list[DomainRiskProfile]

    # Provenance
    criteria_used: str                # "ICCTF_Wefel2011_domain_level"
    domain_aggregation: str           # "mean" or "min"
    thresholds: dict[str, float]      # for reproducibility
    conditioning: str                 # "posterior_at_t" — what the draws represent
    calibration_status: str           # "uncalibrated_model_derived"

    # Gate
    gate_f_g4_passed: bool = False
```

**Core algorithm:**

```python
def estimate_crci_risk(
    theta_draws: np.ndarray,          # (M, n_nodes) — posterior draws at time t
    node_map: NodeMap,                # for index resolution + orientation gate
    composite_state: CompositeState,  # F1 output for IVW weights
    fusion_levels: dict[int, set[str]], # from C3c for coverage
) -> CRCIRiskEstimate:
    """Estimate P̂(CRCI | y_{≤t}, model) from posterior draws.

    This function computes the posterior predictive event probability for
    clinically significant CRCI as defined by domain-level ICCTF criteria.

    The output is a MODEL-DERIVED probability, not a clinically calibrated rate.
    It inherits all model assumptions: DAG structure, prior specifications,
    evidence quality weights, and the domain-level approximation to ICCTF
    test-level criteria.

    Args:
        theta_draws: Posterior draws (M × n_nodes). These are samples from
            N(θ̂, Σ_post) after Bayesian update on patient observations,
            NOT pre-treatment baselines. Produced by mc_sampler.py D1c.
        node_map: Loaded NodeMap for index lookups and orientation validation.
        composite_state: F1 output — used only for IVW weights (view C).
        fusion_levels: From C3c — identifies which nodes were directly observed.

    Returns:
        CRCIRiskEstimate with risk %, interval, domain profiles, and
        all provenance metadata.

    Raises:
        GateViolation: If F-G4 preconditions fail (orientation, coverage,
                       draw count, finiteness).
    """
```

### 4.3 Domain → Node Mapping Resolution

The current F1 `_extract_subdomain_scores()` uses an *approximate* mapping
(dividing nodes evenly if no map is provided). The risk estimator uses the
**canonical** `CRCI_DOMAIN_NODE_MAP` from config, which maps the 10 cognitive
performance domains to their exact DAG nodes.

**The mapping must be validated at runtime**, not trusted from config:

```python
def _validate_domain_mapping(node_map: NodeMap) -> dict[str, list[int]]:
    """Resolve domain node_ids to indices, validating existence and orientation.

    Gate F-G4a:
    1. Every node_id in CRCI_DOMAIN_NODE_MAP must exist in node_map.
    2. Every mapped node must have orientation == POS_UP.
    3. Every mapped node must have unit_of_measure == 'z-score'.

    Returns:
        domain_id → list[node_index] mapping.

    Raises:
        GateViolation: If any node is missing, mis-oriented, or mis-scaled.
    """
```

**Critical distinction between F1 domains (11) and F4 domains (10):**

| F1 Domains (composite z-score) | F4 Domains (clinical risk) |
|---|---|
| 11 domains including `mood` and `fatigue` | 10 domains — **cognitive only** |
| Used for IVW-weighted composite scoring | Used for ICCTF clinical classification |
| `mood` and `fatigue` are symptom_burden nodes | Excluded: they inform the DAG but are not ICCTF diagnostic criteria |

This is scientifically correct: the ICCTF criteria define CRCI based on
**cognitive test performance**, not on symptom self-report. Fatigue and mood
influence cognition through the DAG (they are upstream drivers), but they are
not diagnostic domains for CRCI itself.

### 4.4 `output_contracts.py` — Extended Report

```python
class DomainRiskBreakdown(BaseModel):
    """Per-domain risk decomposition for clinical display."""
    domain_id: str
    domain_label: str
    marginal_risk_pct: float            # P(this domain impaired)
    trigger_share_pct: float            # trigger-share attribution (NOT Shapley)
    ivw_weight_pct: float               # precision influence (separate from risk)
    mean_z: float
    z_range: tuple[float, float]        # (5th, 95th percentile)
    is_observed: bool                   # whether directly observed (L2+)

class ClinicalRiskProfile(BaseModel):
    """Clinical CRCI risk assessment with domain decomposition.

    This is a model-derived probability, not a clinically calibrated rate.
    """
    risk_pct: float
    risk_lower_pct: float
    risk_upper_pct: float
    risk_range_text: str                # "32%–41%"
    risk_tier: str                      # LOW / MODERATE / ELEVATED / HIGH / VERY_HIGH
    interval_method: str                # "jeffreys" or "mc_se"
    criteria: str                       # "ICCTF_Wefel2011_domain_level"
    calibration_status: str             # "uncalibrated_model_derived"
    coverage_fraction: float
    low_coverage_warning: bool
    domain_breakdown: list[DomainRiskBreakdown]
```

Add to `RecommendationReport`:

```python
class RecommendationReport(BaseModel):
    # ... existing fields ...
    clinical_risk: ClinicalRiskProfile | None = None  # NEW
```

### 4.5 `risk_dashboard.py` — Presentation

Renders two linked views:

**A. Risk Estimate:**
- Large display showing "37% model-derived probability of meeting CRCI criteria"
- Range bar: "32%–41% (Jeffreys 90% interval)"
- Risk tier badge (color-coded, labeled as communication default)
- Criteria disclosure: "Based on ICCTF domain-level criteria (Wefel et al., 2011, *Lancet Oncol*)"
- Calibration disclosure: "Model-derived estimate — not calibrated to clinical incidence"
- Coverage flag: if < 50% domains observed, prominent yellow banner

**B. Domain Breakdown (two sub-panels):**

**B1. Risk Attribution:**
- Horizontal bar chart, each bar = one cognitive domain
  - Bar fill = marginal impairment probability (left axis)
  - Annotation = trigger-share % (labeled "trigger-share," not "Shapley")
  - Color = z-score severity (green → red)
  - Hatching for unobserved domains (imputed from DAG covariance)

**B2. Precision Influence (separate panel):**
- Horizontal bar chart showing IVW weight %
- Labeled as "How much measurement precision in each domain influences the composite"
- Explicitly NOT labeled as "risk contribution"

### 4.6 Gates

**F-G4a: Orientation & Mapping Validity (pre-compute, hard gate)**
1. Every `node_id` in `CRCI_DOMAIN_NODE_MAP` resolves to a valid NodeMap index
2. Every mapped node has `orientation == "POS_UP"`
3. Every mapped node has `unit_of_measure == "z-score"`

If any fail → `raise GateViolation("F-G4a", ...)`. Do NOT proceed with
inverted or mis-scaled nodes.

**F-G4b: Draw Quality (hard gate)**
1. `n_draws ≥ CRCI_RISK_MIN_DRAWS` (default 1000)
2. All domain z-score draws are finite (no NaN/Inf)
3. At least 1 domain has observable variation (SD > 1e-10)

**F-G4c: Output Consistency (hard gate)**
1. `risk_pct ∈ [0, 100]`
2. `risk_lower_pct ≤ risk_pct ≤ risk_upper_pct`
3. `Σ trigger_share_pct = 100% (±0.5% tolerance)` when P̂ > 0
4. `Σ ivw_weight_pct = 100% (±0.1% tolerance)`
5. `coverage_fraction ∈ [0, 1]`

---

## 5. Correctness Concerns & Mitigations

### 5.1 Domain-Level vs. Test-Level Classification

The ICCTF criteria are test-score-level. Using domain-level z-scores (which
average across nodes within a domain) will tend to dilute impairment and
underestimate CRCI prevalence compared to test-level classification.

**Mitigation:**
- Offer `CRCI_DOMAIN_AGGREGATION = "min"` as an alternative that uses the
  worst z-score within each domain (closer to test-level sensitivity)
- Report both rates in the output during validation
- Long-term: when the instrument/measure registry is fully wired, compute
  at individual test-score level using the loaded measurement model

### 5.2 Prior-Dominated Domains

When few or no observations are available for a domain, the posterior draws
for those nodes are dominated by the prior (Chain C). The prior may be
uninformative (N(0, 10²)) or context-matched (from Chain B). In either case:

- Prior-dominated nodes have high variance → draws spread widely
- This inflates risk estimates if the prior mean is near -1.5 SD
- This deflates risk estimates if the prior mean is near 0 SD

**Mitigation:**
- Report coverage fraction prominently
- Flag low-coverage estimates
- The model's covariance structure (off-diagonal Σ_post entries) propagates
  information from observed nodes to unobserved ones — this is the intended
  behavior of the DAG-structured prior

### 5.3 Calibration

A raw posterior predictive probability from a mechanistic causal model is
**not automatically calibrated to clinical incidence rates.** The model may
systematically over- or under-estimate true CRCI prevalence.

**For MVP:** Label output explicitly as "model-derived probability
(not clinically calibrated)." The presentation must not imply clinical
validation.

**For future calibration:**
1. Obtain a held-out cohort with known CRCI outcomes and model predictions
2. Apply Platt scaling (logistic recalibration) or isotonic regression
3. Report calibration slope, intercept, and Brier score
4. Only after external validation can the output be labeled "calibrated"

Placeholder constant for future use:
```python
CRCI_CALIBRATION_SLOPE: float = 1.0   # Platt scaling — 1.0 = no calibration
CRCI_CALIBRATION_INTERCEPT: float = 0.0
```

### 5.4 Risk Tier Cutoffs

The tier boundaries (15/30/50/70%) are **communication-only defaults**.
They are NOT derived from epidemiological data, cost-utility analysis, or
clinical decision thresholds. They exist solely to map a continuous
probability to a categorical label for non-technical communication.

**Justification:** These approximate tercile/quartile splits of the [0, 100]
range, with the LOW tier (<15%) reflecting general-population CRCI prevalence
(~15-25% depending on cancer type and timepoint). The boundaries can be
reconfigured without code changes when formal utility thresholds are
established.

---

## 6. Verification Protocol

### 6.1 Hand-Computable Test Case

**Setup:** 3 domains, 100 draws, deterministic (seeded):
- Domain A: 60 of 100 draws ≤ -1.5; 20 of 100 draws ≤ -2.0
- Domain B: 5 of 100 draws ≤ -1.5; 0 of 100 draws ≤ -2.0
- Domain C: 30 of 100 draws ≤ -1.5; 8 of 100 draws ≤ -2.0

Hand-compute:
1. Draws where ≥2 domains ≤ -1.5 (multi-domain criterion)
2. Draws where ≥1 domain ≤ -2.0 (single severe criterion)
3. Union → CRCI indicator per draw → P̂
4. MC-SE = √(P̂(1-P̂)/100)
5. Jeffreys: Beta(S+0.5, F+0.5) quantiles at 0.05 and 0.95
6. Marginal P_d for each domain
7. Trigger-share φ_d for the positive draws → verify Σ = 1.0

### 6.2 Edge Cases

- All draws below threshold → P̂ = 100%, interval [~98%, 100%], all φ_d ≈ 1/D
- No draws below threshold → P̂ = 0%, Jeffreys interval [~0%, ~2%], φ_d undefined (report 0)
- Only 1 domain observed → coverage flag, estimate still produced from posterior
- n_draws = 0 → Gate F-G4b fires, no estimate produced
- θ̂ = 0 for all nodes with large prior variance → risk depends on prior spread

### 6.5 Non-Negotiable Unit Tests (must exist before F4 is considered complete)

| Test | What it verifies | Expected behavior |
|------|------------------|-------------------|
| **Orientation flip** | One `NODE_COG_*` marked `NEG_UP` in NodeMap | Gate F-G4a raises `GateViolation("F-G4a", ...)` |
| **Mapping completeness** | One `node_id` in `CRCI_DOMAIN_NODE_MAP` absent from NodeMap | Gate F-G4a raises `GateViolation("F-G4a", ...)` — do NOT skip the domain silently |
| **Domain aggregation divergence** | Toy draw set where `mean(z_nodes) > -1.5` but `min(z_nodes) < -1.5` for one domain | `CRCI_DOMAIN_AGGREGATION="mean"` → domain not impaired; `"min"` → domain impaired; outputs must differ |
| **Jeffreys edge S=0** | All 10,000 draws CRCI-negative (S=0, F=M) | `Beta(0.5, M+0.5)` → finite interval `[0%, ~0.03%]`, no NaN/Inf |
| **Jeffreys edge S=M** | All 10,000 draws CRCI-positive (S=M, F=0) | `Beta(M+0.5, 0.5)` → finite interval `[~99.97%, 100%]`, no NaN/Inf |
| **Trigger-share sum** | Any draw set with P̂ > 0 | `Σ_d φ_d = 1.0 (± 0.005)` — verify in test, not just gate |
| **Coverage computation** | 3 of 10 domains at L2+, rest at L0/L1 | `coverage_fraction = 0.3`, `low_coverage_warning = True` |

### 6.3 Backward Coherence

- `theta_draws` shape must be `(n_draws, n_nodes)` from `MCDraws`
- Column indices from `node_map.node_index` match `theta_draws` columns
- `CompositeState.subdomain_weights` keys are a superset of risk domain IDs
- Fusion levels from C3c match `node_map.node_index` keys

### 6.4 Forward Coherence

- `CRCIRiskEstimate` consumed by `report_assembler.py` → `ClinicalRiskProfile`
- `ClinicalRiskProfile` consumed by `risk_dashboard.py` for rendering
- `DomainRiskBreakdown.domain_id` must match `DomainBar.domain_id` in `crci_dashboard.py`
- `calibration_status` must be surfaced in all presentation views

---

## 7. Build Order

| Step | File | Dependencies | Tests | Blocked by |
|------|------|-------------|-------|------------|
| 0 | Vertical slice validation | Chain A–F end-to-end | Posterior draws for COG nodes are non-degenerate | — |
| 1 | `config.py` (add constants) | Step 0 confirmed | — | Step 0 |
| 2 | `output_contracts.py` (add types) | Step 1 | — | Step 1 |
| 3 | `risk_estimator.py` (create) | Steps 1-2, MCDraws (D1), CompositeState (F1), NodeMap (A1), C3c | `test_risk_estimator.py` | Step 2 |
| 4 | `report_assembler.py` (wire in) | Steps 1-3 | Existing tests adapt | Step 3 |
| 5 | `risk_dashboard.py` (create) | Steps 1-4 | `test_risk_dashboard.py` | Step 4 |
| 6 | Integration test | All above | `test_risk_integration.py` | Step 5 |

**Estimated effort:** 3 slices (Steps 1-3 as one, Steps 4-5 as one, Step 6 as one).

**Hard prerequisite:** Step 0 — validate that the vertical slice produces
non-degenerate posterior draws for `NODE_COG_*` nodes. Without this, all
subsequent steps produce meaningless output.

---

> **Cross-Reference: Presentation Audit**
>
> The companion document [`PRESENTATION_AUDIT_AND_IDEAS.md`](PRESENTATION_AUDIT_AND_IDEAS.md)
> addresses *plumbing* concerns — surfacing existing computation to users. This plan
> addresses *algorithm* concerns — new F4/F5 computation. The shared touchpoints are
> `output_contracts.py`, `report_assembler.py`, and `session.py`. Several audit items
> (§5 #11, #12, #13, #14) correspond to sections §8.3–§8.6 below — they are the same
> features viewed from presentation vs. algorithm perspectives. Wiring bugs from audit
> items #1–#3 have been resolved. See audit §7 for details.

---

## 8. Remaining Gaps (Placeholders for Future Elaboration)

### 8.1 Subpopulation Comparative Risk View

#### 8.1.1 Problem Statement

The current pipeline runs one context at a time: a patient is matched to a
single `ContextPriorSpec` (e.g., `breast_adjuvant`) via C1's 4-level fallback,
and Chains C→D→F produce rankings and risk estimates for that context alone.
There is no mechanism to answer: *"Is exercise more effective for breast-cancer
patients than for colorectal patients?"* — a question that requires running the
pipeline under multiple context priors and performing a **paired comparison**
of the outputs.

This gap is non-trivial because naive unpaired comparisons (run context A, run
context B, subtract means) are statistically invalid — MC noise dominates real
differential effects. A correct design must exploit the shared structure in the
sampling pipeline to produce **paired draws** that cancel stochastic variation
and isolate context-driven differences.

#### 8.1.2 Architectural Constraint — Shared Precision Matrix

A critical design constraint discovered in `frozen_state.py` line 228
(`compile_context_priors()`): **all 33 context specs share the same base
precision matrix** Λ = (I − B̂)ᵀ D⁻¹ (I − B̂). Context-specific information
flows exclusively through μ_prior (the prior mean vector in `ContextPriorSpec.
node_prior_means`); the precision structure is identical across contexts.

**Implication:** Subpopulation differences in posterior inference are driven
by *prior mean shifts*, not by structural differences in the covariance. This
means:
- Two contexts with similar μ_prior produce nearly identical posteriors
  → comparison is uninformative
- Differences in downstream rankings arise from (a) different starting-point
  baselines and (b) different intervention-effect magnitudes conditional on
  those baselines
- The comparison must decompose total differential into **baseline
  contribution** (θ̂ difference) and **mechanism contribution** (ΔC difference
  controlling for baseline)

#### 8.1.3 Pipeline Split Point

```
 A ──► B ──► FrozenModelState (SHARED — compute once)
                    │
             ┌──────┼──────┐──────── ... ──────┐
             ▼      ▼      ▼                    ▼
           ctx_1  ctx_2  ctx_3               ctx_N
             │      │      │                    │
            C1: load_prior (context-specific μ_prior, SE_inflation)
             │      │      │                    │
            C3: bayesian_update (+ patient observations, if any)
             │      │      │                    │
            C4: modifier_application (patient-specific modifiers)
             │      │      │                    │
            D1: generate_mc_draws (SAME seed → paired draws)
             │      │      │                    │
            D2→D3→D4-D6: propagation + ranking
             │      │      │                    │
            F4: risk_estimator → P̂(CRCI | context_k)
             │      │      │                    │
             └──────┴──────┴───────────────────┘
                           │
                      F5: compare
```

**What is reused (compute once):**
- Chain A: GraphObject — DAG topology is context-independent
- Chain B: FrozenModelState — B̂, Σ_eff, P_inclusion, AV_scores are
  compiled from the full evidence base irrespective of clinical context

**What is recomputed per context:**
- C1: `load_prior()` — selects context-specific μ_prior, applies fallback-
  level SE inflation
- C3: `bayesian_update()` — if patient observations exist, updates the
  context-specific prior (identical observations, different prior → different
  posterior)
- C4: `apply_modifiers()` — applies patient-specific modifiers (may be
  identical across contexts in the archetype case)
- D1: `generate_mc_draws()` — D1a (edge weights) and D1b (inclusion masks)
  are context-independent (depend only on FrozenModelState), so they produce
  **identical draws** across contexts when given the same seed; D1c (patient
  baselines) uses the same z-draws but transforms through different Cholesky
  factor L and posterior mean θ̂ → **correlated but context-specific**
- D2-D6: all downstream computations differ because θ₀^(m) differs
- F4: risk estimation uses context-specific draws

#### 8.1.4 Paired Comparison via Common Random Numbers

The existing `generate_mc_draws()` (D1 entry point) creates a single
`rng = np.random.default_rng(seed)` and consumes it sequentially:
D1a → D1b → D1c. Since D1a and D1b depend only on `frozen` (not
`patient_state`), they consume identical RNG states across contexts
when called with the same seed. D1c then draws the same z-vectors
from `rng.standard_normal()` but applies context-specific θ̂ + L·z.

This produces **automatically paired MC draws:**

| Component | Same seed, different context      | Effect on pairing       |
|-----------|-----------------------------------|-------------------------|
| D1a β^(m) | Identical — depends on frozen     | Perfectly paired        |
| D1b I^(m) | Identical — depends on frozen     | Perfectly paired        |
| D1c θ₀^(m)| Same z, different L,θ̂             | Correlated via shared z |

The paired structure enables:

$$\Delta_{\text{diff}}^{(m)}(\text{intv}_i, k_1, k_2) = \Delta C_{k_1}^{(m)}(\text{intv}_i) - \Delta C_{k_2}^{(m)}(\text{intv}_i)$$

where the draw-level difference cancels shared stochastic variation (same β,
same I), isolating context-driven effects. The distribution of
Δ_diff^(m) over M=10,000 draws yields a paired CrI that is substantially
tighter than an unpaired comparison (by a factor proportional to the
correlation ρ ≈ 0.6–0.9 depending on how much D1c variance contributes).

#### 8.1.5 Two Use Cases

**Case A — Population Archetype Comparison (no patient observations)**

Purpose: "Which interventions are most effective for breast vs. colorectal
cancer, on average?"

- No patient-specific observations (C3 receives empty observation vector)
- No patient-specific modifiers (C4 is identity: modifier_se_inflation = 1.0)
- Posterior = prior (θ̂ = μ_prior, Σ_post = Σ_prior = Λ⁻¹)
- Clinician selects 2–4 context keys to compare
- D1a+D1b draws computed once and shared across all contexts (optimization)
- D1c differs only through different L and θ̂ from different context priors

This is the **MVP use case** — simpler, requires no patient data, answers the
population-level comparative question directly.

**Case B — Prior Sensitivity Analysis (patient-specific)**

Purpose: "How would MY recommendations change if I had breast vs. colorectal?"

- Patient observations y_{≤t} are applied identically under each context prior
- Different priors + same observations → different posteriors
- C4 modifiers may vary if context affects modifier selection
- Full D1 recomputation per context (modifier_se_inflation may differ)
- This answers: "How sensitive are your personal recommendations to the
  assumed clinical context?"

This is the **extension use case** — requires a patient session, answers the
individual sensitivity question.

#### 8.1.6 Statistical Comparison Methods

**F5-M1: Paired Differential Effects**

For each intervention i and context pair (k₁, k₂):

$$\bar{\Delta}_{\text{diff}} = \frac{1}{M} \sum_{m=1}^{M} \left[ \Delta C_{k_1}^{(m)} - \Delta C_{k_2}^{(m)} \right]$$

$$\text{CrI}_{90\%} = \left[ q_{0.05}\left(\Delta_{\text{diff}}^{(m)}\right),\; q_{0.95}\left(\Delta_{\text{diff}}^{(m)}\right) \right]$$

**Practically different** if the 90% CrI excludes zero.

**F5-M2: Rank Concordance**

Kendall's τ between SAFE_B rankings under context k₁ vs. k₂:

$$\tau(k_1, k_2) = \frac{\text{concordant} - \text{discordant}}{\binom{n}{2}}$$

Interpretation:
- τ > 0.8: Rankings are context-robust — context matters little for ordering
- 0.5 < τ < 0.8: Moderate sensitivity — some reordering
- τ < 0.5: Rankings are context-dependent — clinical context is a first-order
  consideration

**F5-M3: Risk Differential**

$$\hat{P}_{\text{CRCI,diff}}(k_1, k_2) = \hat{P}_{\text{CRCI}}(k_1) - \hat{P}_{\text{CRCI}}(k_2)$$

with interval from paired draw-level differences (same as F5-M1 but applied
to the binary CRCI event counts from F4-2).

**F5-M4: Baseline-vs-Mechanism Decomposition**

Total differential:
$$\Delta_{\text{total}} = \Delta C_{k_1} - \Delta C_{k_2}$$

Decompose into:
- **Baseline contribution:** difference in starting θ̂ → different baseline
  distance from CRCI threshold → different scope for improvement
- **Mechanism contribution:** difference in ΔC controlling for baseline

To isolate mechanism: recompute ΔC under both contexts but starting from a
**common baseline** θ₀* = (θ̂_{k₁} + θ̂_{k₂}) / 2. The mechanism differential
is the residual:

$$\Delta_{\text{mechanism}} = \Delta C_{k_1}^{*} - \Delta C_{k_2}^{*}$$

$$\Delta_{\text{baseline}} = \Delta_{\text{total}} - \Delta_{\text{mechanism}}$$

This prevents the misleading claim "exercise is more effective for breast
cancer" when the actual driver is "breast patients start lower, so there is
more room for improvement."

**F5-M4 implementation constraint — severity weight freeze:**

The D2e composite score uses **baseline-dependent severity weighting**:
`w_d = severity_weight(θ0_d) × (1/σ²_d)` where `severity_weight()` maps
`|z| < 1.0 → 1.0`, `1.0 ≤ |z| < 2.0 → 1.5`, `|z| ≥ 2.0 → 2.0`. This means
the ΔC composite score is a function of the baseline, not just the effect.

If F5-M4 uses the standard D2e scoring with baseline-dependent weights,
then the "mechanism contribution" is contaminated by the scoring policy:
two contexts with identical propagation effects but different baselines
will produce different ΔC* even when evaluated at the common baseline
θ0*, because the severity weight boundaries are discrete (step function)
and may switch classification at the common baseline.

**Policy (Option A — adopted):** For F5-M4 decomposition runs ONLY,
compute ΔC using **baseline-invariant scoring**: fix all severity weights
to 1.0 (the `MILD` constant). This means the decomposition's ΔC* uses
pure inverse-variance weighting without baseline-dependent amplification.
The result isolates the propagation mechanism cleanly.

```python
# In subpopulation_comparator.py, F5-M4 decomposition:
def _compute_mechanism_delta_C(
    delta_theta_draw: np.ndarray,
    common_baseline: np.ndarray,  # θ0* = average of both contexts
    Sigma_post_diag: np.ndarray,
    cognitive_indices: list[int],
) -> float:
    """D2e with frozen severity weights for F5-M4 decomposition.

    All severity weights fixed to 1.0 (baseline-invariant).
    This isolates propagation effects from scoring policy.
    """
    numerator = 0.0
    denominator = 0.0
    for idx in cognitive_indices:
        inv_var = 1.0 / max(Sigma_post_diag[idx], config.MIN_SIGMA_FLOOR ** 2)
        w_d = 1.0 * inv_var  # severity_weight = 1.0 (frozen)
        numerator += w_d * delta_theta_draw[idx]
        denominator += w_d
    return numerator / denominator if denominator > 0 else 0.0
```

The output labels this explicitly:
`decomposition_scoring_policy: "baseline_invariant_severity_frozen"`

#### 8.1.7 Validity Gates

**F5-G0: Deterministic Pairing Invariant (hard gate, run FIRST)**

Before any comparison is computed, verify that the CRN pairing property
actually holds for the completed per-context runs. For each context run,
compute and store fingerprint hashes:

```python
@dataclass
class PairingFingerprint:
    """Cryptographic proof that MC draws are properly paired across contexts."""
    d1a_beta_hash: str       # SHA-256 of beta_draws.tobytes()
    d1b_include_hash: str    # SHA-256 of include_draws.tobytes()
    d3_gamma_hash: str       # SHA-256 of gamma_draws (if injected) or "NOT_CONTROLLED"
    seed_used: int
```

F5-G0 enforcement:
```python
# After all per-context pipelines complete:
fingerprints = {ctx: compute_pairing_fingerprint(ctx_result) for ctx, ctx_result in results.items()}

# D1a must be identical across all contexts
d1a_hashes = {fp.d1a_beta_hash for fp in fingerprints.values()}
if len(d1a_hashes) > 1:
    raise GateViolation("F5-G0", "D1a beta draws differ across contexts — CRN pairing broken")

# D1b must be identical across all contexts
d1b_hashes = {fp.d1b_include_hash for fp in fingerprints.values()}
if len(d1b_hashes) > 1:
    raise GateViolation("F5-G0", "D1b inclusion draws differ across contexts — CRN pairing broken")

# D3 gamma must be identical if injected
d3_hashes = {fp.d3_gamma_hash for fp in fingerprints.values()}
if len(d3_hashes) > 1 and "NOT_CONTROLLED" not in d3_hashes:
    raise GateViolation("F5-G0", "D3 gamma draws differ across contexts — CRN pairing broken")
elif "NOT_CONTROLLED" in d3_hashes:
    # Emit warning: gamma draws were not injected, pairing is partial
    logger.warning("F5-G0: D3 gamma draws not controlled — paired CrI may be wider than optimal")
```

Without F5-G0, the "paired comparison cancels MC noise" claim is not
scientifically reliable. This gate must be the FIRST gate checked.

**F5-G1: Fallback-Level Eligibility**

Only contexts with `fallback_level ∈ {EXACT, CANCER_TYPE}` may be compared.
Contexts resolved at `GENERAL_CANCER` or `UNINFORMATIVE` have SE inflation of
1.5×–2.0× (C1c), which dominates any differential signal. Comparing two
uninformative priors produces noise, not insight.

```python
if any(cr.fallback_level in (FallbackLevel.GENERAL_CANCER,
                              FallbackLevel.UNINFORMATIVE)
       for cr in context_results):
    raise GateViolation(
        "F5-G1",
        f"Contexts {[cr.context_key for cr in context_results
                     if cr.fallback_level not in ('EXACT', 'CANCER_TYPE')]} "
        f"resolved at insufficient specificity for comparative analysis"
    )
```

**F5-G2: Minimum Context Count**

At least 2 eligible context specs must pass F5-G1. A single context produces
no comparison.

**F5-G3: Differential Significance Guard**

For each pairwise comparison, compute the overlap coefficient between the
two marginal CrI distributions. If overlap > 0.80 for ALL interventions in
the comparison, emit a warning (not a hard gate):

> "No meaningfully different intervention effects detected between {k₁} and
> {k₂}. Context-specific priors are too similar for differential analysis."

This prevents over-interpretation when two context specs have nearly identical
μ_prior vectors.

#### 8.1.8 Output Contracts

New types in `crci/algorithm/chain_f_analytics/output_contracts.py`:

```python
@dataclass
class ContextResult:
    """Per-context pipeline output for comparative analysis."""
    context_key: str
    cancer_type: str
    treatment_phase: str
    fallback_level: FallbackLevel
    ranking: RankingResult          # D4-D6 output
    risk_estimate: CRCIRiskEstimate # F4 output
    posterior_mean: np.ndarray      # θ̂ (n_nodes,)
    posterior_sd: np.ndarray        # diag(Σ_post)^½ (n_nodes,)
    # Precision fingerprints for pairing verification (F5-G0) and shared-Λ validation
    prior_precision_fingerprint: str    # SHA-256 of Λ_prior (pre-inflation)
    posterior_precision_fingerprint: str # SHA-256 of Σ_post
    se_inflation_applied: float         # C1c SE inflation factor (1.0/1.2/1.5/2.0)
    pairing_fingerprint: PairingFingerprint  # D1a/D1b/D3 hashes
    # Context provenance (§8.1.12)
    n_context_shifted_nodes: int    # how many nodes have non-default μ_prior
    context_evidence_source: str    # "extracted" | "heuristic" | "default"

@dataclass
class DifferentialEffect:
    """Pairwise intervention effect comparison across two contexts."""
    intervention_id: str
    context_a: str
    context_b: str
    delta_C_diff_mean: float        # Ē[ΔC_a − ΔC_b] over M draws
    delta_C_diff_ci: tuple[float, float]  # 90% CrI of draw-level diffs
    baseline_contribution: float    # portion due to θ̂ difference
    mechanism_contribution: float   # portion due to ΔC|θ₀* difference
    practically_different: bool     # True if CrI excludes zero
    decomposition_scoring_policy: str  # "baseline_invariant_severity_frozen"

@dataclass
class RiskDifferential:
    """Pairwise CRCI risk comparison across two contexts."""
    context_a: str
    context_b: str
    risk_diff_pct: float            # P̂(CRCI|a) − P̂(CRCI|b) × 100
    risk_diff_ci: tuple[float, float]  # 90% CrI
    domain_diffs: dict[str, float]  # per-domain risk differential

@dataclass
class SubpopulationComparisonResult:
    """Complete F5 output: cross-context comparison."""
    context_results: dict[str, ContextResult]
    pairwise_differentials: list[DifferentialEffect]
    rank_concordance: dict[tuple[str, str], float]  # (k₁,k₂) → τ
    risk_differentials: dict[tuple[str, str], RiskDifferential]
    n_contexts_compared: int
    comparison_valid: bool
    validity_notes: list[str]
    seed: int                       # shared seed for reproducibility
    # Pairing verification
    gate_f5_g0_passed: bool = False  # True only if all pairing hashes match
    crn_coverage: str = "full"       # "full" (D1+D3 controlled) or "partial" (D1 only)
```

#### 8.1.9 Module: `subpopulation_comparator.py` (F5)

**Location:** `crci/algorithm/chain_f_analytics/subpopulation_comparator.py`

**Entry point:**
```python
def run_comparative_analysis(
    frozen: FrozenModelState,
    context_keys: list[str],
    observations: ObservationBatch | None = None,  # None → archetype mode
    patient_modifiers: PatientModifiers | None = None,
    n_draws: int = config.MC_DRAWS,
    seed: int = config.MC_DEFAULT_SEED,
) -> SubpopulationComparisonResult:
```

**Internal flow:**

1. **Validate contexts** — resolve each context_key via C1, enforce F5-G1/G2
2. **Pre-compute shared stochastic draws (CRN enforcement):**
   - D1a + D1b: compute once from `frozen` with `seed` → identical across contexts
   - D3 γ draws: pre-compute per-pair gamma draws with `seed + 1_000_000` → identical across contexts
   - Store hashes for F5-G0 verification
3. **Run per-context pipelines:**
   - For each context_key:
     - C1 `load_prior()` → `LoadedPrior`
     - C3 `bayesian_update()` with observations (empty if archetype) → `RawPosterior`
     - C4 `apply_modifiers()` with patient_modifiers (identity if archetype)
       → `PatientState`
     - D1 `generate_mc_draws(frozen, patient_state, seed=seed)` → `MCDraws`
       (same seed ensures pairing via §8.1.4)
     - D2 `propagate_effects()` → `EffectResult`
     - D3 `compute_bundles(..., injected_gamma_draws=shared_gamma_draws)` → `BundleResult`
       (injected γ ensures D3 stochasticity is paired across contexts)
     - D4-D6 `rank_interventions()` → `RankingResult`
     - F4 `estimate_risk()` → `CRCIRiskEstimate`
   - Compute `PairingFingerprint` (SHA-256 of D1a, D1b, D3 γ draws)
   - Compute precision fingerprints (SHA-256 of Λ_prior, Σ_post)
   - Collect into `ContextResult`
4. **Enforce F5-G0** — verify all pairing fingerprints match across contexts
5. **Compute pairwise comparisons:**
   - For each pair (k₁, k₂):
     - F5-M1: paired differential ΔC for each intervention
     - F5-M2: Kendall's τ on SAFE_B rankings
     - F5-M3: risk differential
     - F5-M4: baseline-vs-mechanism decomposition (severity weights frozen to 1.0)
   - Enforce F5-G3 warning if no meaningful differences detected
6. **Assemble** `SubpopulationComparisonResult` with `gate_f5_g0_passed`, `crn_coverage`

**Optimization (archetype mode):** When `observations is None` and
`patient_modifiers is None`, D1a and D1b are context-independent. Pre-compute
them once and inject into each per-context D1c call. This reduces MC cost from
O(N_contexts × M × n_edges) to O(M × n_edges) + O(N_contexts × M × n_nodes).

#### 8.1.10 Presentation

The comparison result feeds into `risk_dashboard.py` (F6) and the session
report:

| View                      | Data Source (F5 output)         | Format               |
|---------------------------|---------------------------------|----------------------|
| Differential forest plot  | `pairwise_differentials`        | Per-intervention bar with CrI, colored by context |
| Rank stability table      | `rank_concordance`              | τ matrix heatmap     |
| Risk comparison bar chart | `risk_differentials`            | Grouped bars with error bars |
| Baseline vs mechanism     | `DifferentialEffect` fields     | Stacked bar: baseline component + mechanism component |
| Domain decomposition diff | `RiskDifferential.domain_diffs` | Radar chart overlay  |

#### 8.1.11 Implementation Sequence

| Step | File                              | Depends On          | Test File                      |
|------|-----------------------------------|---------------------|--------------------------------|
| 1    | `output_contracts.py` — add F5 types | Existing types   | Type-check only                |
| 2    | `subpopulation_comparator.py` (F5)   | C1, C3, C4, D1-D6, F4 | `test_subpopulation.py`    |
| 3    | `risk_dashboard.py` — add comparative view | F5 output   | `test_risk_dashboard.py`       |
| 4    | Integration test — 3-context archetype | Steps 1-3        | `test_subpop_integration.py`   |

**Estimated effort:** 2 slices (Steps 1-2 as one, Steps 3-4 as one).

**Hard prerequisite:** F4 `risk_estimator.py` must be implemented first
(Step 3 of §7). The archetype mode (Case A) has no further prerequisites.
Case B (prior sensitivity) additionally requires a working patient session
with observations (RT-G through RT-I).

#### 8.1.12 Context Spec Provenance

If context priors (μ_prior) are extraction-derived rather than manually
curated, the comparative module must report the provenance of each context's
priors. Without this, you can produce "breast vs. colorectal" comparisons
where both contexts are effectively the same default prior with a different
label — generating apparent differences that are artifacts, not science.

**Required metadata per context (stored in `ContextResult`):**

| Field | Description | Values |
|-------|-------------|--------|
| `n_context_shifted_nodes` | Count of nodes where μ_prior ≠ default (0.0) | 0 → context is just a label, no actual differentiation |
| `context_evidence_source` | How the μ_prior values were determined | `"extracted"` (from literature via extraction pipeline), `"heuristic"` (expert-specified), `"default"` (no context-specific data) |

**Gate extension (F5-G1b):** If BOTH contexts in a comparison have
`n_context_shifted_nodes < 3` (fewer than 3 nodes actually differ from
default), emit warning:

> "Contexts {k₁} and {k₂} have minimal prior differentiation ({n₁} and
> {n₂} shifted nodes respectively). Apparent differences may reflect
> label artifacts rather than evidence-based context distinctions."

This is a warning, not a hard gate — some contexts may legitimately differ
on only 1-2 key nodes (e.g., hormone-receptor status affecting only
`NODE_BIO_ESTROGEN` and `NODE_BIO_PROGESTERONE`).

### 8.2 Future/Predictive Risk Under Intervention

#### 8.2.1 Problem Statement

F4 (§2–§4) produces a **snapshot**: P̂(CRCI | y_≤t, model) — the probability
of clinically significant CRCI right now, given current observations. This is
a static risk assessment.

But the system already computes temporal trajectories:

- **E2** produces `R_draws` (n_draws × T) — per-MC-draw recovery fractions
  at monthly intervals, capturing stochastic variation in natural recovery.
- **E3** overlays intervention effects via `delta_C × K_a(t) + δ_aging(t)`,
  producing `InterventionTrajectory.theta_intervention` (n_nodes × T).
- **E4** computes `ITESummary` and `ClinicalMetrics` (ARR, NNT) at fixed
  horizons [3, 6, 12, 24] months.

However, **none of these apply the F4 ICCTF classification at future
timepoints.** E4's clinical metrics use a simple per-node threshold (is the
mean across nodes below −0.5 SD?), which is NOT the ICCTF multi-domain
criteria. The questions clinicians actually need answered are:

1. *"What is the probability this patient will still meet CRCI criteria at
   6 months, 12 months, 24 months?"*
2. *"How much does Exercise reduce that future probability?"*
3. *"When does CRCI risk peak? When does it resolve?"*
4. *"Which intervention has the best temporal risk reduction profile?"*

These require applying F4's domain-level ICCTF classification to
reconstructed per-draw cognitive state vectors at each future timepoint.

#### 8.2.2 What Exists (Infrastructure Inventory)

| Component | Module | What it provides | Gap |
|-----------|--------|------------------|-----|
| Per-draw recovery | `recovery_trajectory.py` (E2) | `R_draws` (n_draws × T) — stochastic R(t) | ✅ Sufficient |
| Mean natural trajectory | `recovery_trajectory.py` (E2) | `theta_natural` (n_nodes × T) | ✅ Sufficient |
| Intervention kernel | `intervention_overlay.py` (E3) | `K_a(t)` per intervention | ✅ Sufficient |
| Intervention effect | `intervention_overlay.py` (E3) | `delta_C` — **mean** across D2 draws | ⚠ Scalar only |
| Aging term | `intervention_overlay.py` (E3) | `delta_aging(t)` | ✅ Sufficient |
| Per-draw theta reconstruction | `report_assembler.py` | `nadir_i + delta_i × R_draws[m,t]` | ✅ Sufficient |
| ICCTF classification | §4 (`risk_estimator.py`, planned) | F4-1 at time t=0 only | ❌ Not temporal |
| Uncertainty growth | `uncertainty_counterfactual.py` (E4) | `Var(θ(t)) = Var₀ + 0.01t + 0.005t²` | ✅ Available |
| Domain→node mapping | `config.py` (§4.1) | `CRCI_DOMAIN_NODE_MAP` (10 domains) | ✅ Sufficient |
| Prediction horizons | `config.py` | `E_PREDICTION_HORIZONS = [3, 6, 12, 24]` | ✅ Configurable |

**Key observation:** The infrastructure for per-draw temporal theta
reconstruction already exists in `report_assembler.py`'s
`_build_node_trajectory_from_draws()`. The linear mapping from R-space to
θ-space is:

$$\hat{\theta}_i^{(m)}(t) = \text{nadir}_i + \delta_i \cdot R^{(m)}(t)$$

where $\text{nadir}_i$ and $\delta_i$ are solved from:

$$\delta_i = \frac{\theta_{\text{natural},i}(T) - \theta_{\text{natural},i}(0)}{R_{\text{mean}}(T) - R_{\text{mean}}(0)}, \quad \text{nadir}_i = \theta_{\text{natural},i}(0) - \delta_i \cdot R_{\text{mean}}(0)$$

This is **exact** (not an approximation) within the E3 model because
E3d-EQ1 is linear in R(t):
$\theta(t) = \theta_{\text{nadir}} + (\theta_{\text{base}} - \theta_{\text{nadir}}) \cdot R(t)$.

#### 8.2.3 Why E4's Clinical Metrics Are Insufficient

E4 currently computes `ClinicalMetrics` (ARR, RRR, NNT) using:

```python
# "Impaired" = mean across nodes < E4_SEVERITY_THRESHOLD_SD (-0.5)
composite_natural = float(np.mean(theta_natural[:, horizon_idx]))
p_impaired_natural = float(np.sum(theta_natural[:, horizon_idx] < threshold) / n_nodes)
```

This has **three** problems:

1. **Wrong criteria**: Uses a single threshold on per-node values. ICCTF
   requires _multi-domain_ pattern matching (≥2 domains ≤ −1.5 SD OR
   ≥1 domain ≤ −2.0 SD). These are structurally different criteria.

2. **No per-draw stochasticity**: E4 applies criteria to the MEAN
   trajectory `theta_natural[:, t]`, not to per-draw reconstructions.
   This means P(impaired) is either 0 or 1 — no proper probabilistic
   estimation.

3. **Wrong threshold**: Uses `E4_SEVERITY_THRESHOLD_SD = -0.5` (a general
   impairment threshold), not the ICCTF-specific thresholds
   (`CRCI_THRESHOLD_MULTI_DOMAIN_Z = -1.5`,
   `CRCI_THRESHOLD_SINGLE_DOMAIN_Z = -2.0`).

§8.2 corrects all three by applying the F4 ICCTF classification
(Formula F4-1) to per-draw reconstructed theta at each future timepoint.

#### 8.2.4 Core Algorithm — Temporal ICCTF Classification

**Module:** `crci/algorithm/chain_f_analytics/temporal_risk.py`

**Inputs:**
- `RecoveryTrajectory` from E2 — provides `theta_natural` (n_nodes × T),
  `R_draws` (n_draws × T), `R_mean` (T,)
- `OverlayResult` from E3 — provides per-intervention `InterventionTrajectory`
  with `delta_C`, `K_a(t)`, `delta_aging(t)`
- `NodeMap` from A1 — for index resolution and orientation validation
- `CompositeState` from F1 — for IVW weights (View C only)
- `fusion_levels` from C3c — for coverage computation
- Optionally: `Var(θ₀)` from E4 — for epistemic uncertainty inflation

**Step 1: Per-draw theta reconstruction at each timepoint**

For each MC draw $m \in \{1, \ldots, M\}$ and timepoint $t \in \{0, \ldots, T-1\}$:

**Natural (no intervention):**

$$\theta_i^{(m)}(t) = \text{nadir}_i + \delta_i \cdot R^{(m)}(t) + \delta_{\text{aging}}(t) \tag{F4T-1}$$

**With intervention $a$:**

$$\theta_{i,a}^{(m)}(t) = \text{nadir}_i + \delta_i \cdot R^{(m)}(t) + \Delta C_a \cdot K_a(t) + \delta_{\text{aging}}(t) \tag{F4T-2}$$

where $\text{nadir}_i$ and $\delta_i$ are the linear coefficients from the
mean trajectory (identical to report_assembler's reconstruction).

**Critical: Aging appears in BOTH formulas.** The aging term $\delta_{\text{aging}}(t)$
applies universally — it is not intervention-specific. This differs from E3's
current code, which adds aging only to intervention trajectories (a pre-existing
asymmetry in E3; see Note below). F4T corrects this: the natural trajectory
MUST include aging so that ARR isolates the intervention effect cleanly.
Without this, the nonlinear ICCTF thresholding means the aging contribution
does NOT cancel (unlike E4's linear ITE subtraction where it would cancel).

> **Note — E3 implementation divergence:** E3's `compute_intervention_overlay()`
> adds `delta_aging` only inside the per-intervention loop. The `theta_natural`
> from E2 is pure recovery (`θ_nadir + delta × R(t)`) with no aging. This is
> acceptable for E4's linear ITE computation (aging cancels in subtraction),
> but INCORRECT for F4T's nonlinear threshold-based classification. F4T must
> independently compute `delta_aging` and add it to BOTH natural and
> intervention per-draw reconstructions.

**Critical note on stochasticity sources:**

The per-draw variation comes ONLY from $R^{(m)}(t)$ — the recovery trajectory
draws. The intervention effect ($\Delta C_a \cdot K_a(t)$) and aging
($\delta_{\text{aging}}(t)$) are both **deterministic** — identical across
all draws. $\Delta C_a$ is deterministic because E3's current architecture
collapses `delta_C` to `float(np.mean(interv_effects.delta_C))`.

Since both natural and intervention trajectories share the same R_draws AND
the same aging term, the temporal natural↔intervention comparison is
automatically a **paired CRN comparison** — no need for the explicit CRN
seed pairing required in F5 (§8.1.5). MC noise cancels exactly in the
comparison; only the intervention shift $\Delta C_a \cdot K_a(t)$ differs.

**Step 2: Domain aggregation at each draw/timepoint**

For each draw $m$ and timepoint $t$, aggregate node-level theta to
domain-level z-scores using the canonical `CRCI_DOMAIN_NODE_MAP`:

$$z_d^{(m)}(t) = \text{agg}\bigl(\theta_i^{(m)}(t) \text{ for } i \in \text{domain } d\bigr) \tag{F4T-3}$$

where `agg` is `CRCI_DOMAIN_AGGREGATION` (default: `"mean"`).

**Step 3: ICCTF classification at each draw/timepoint**

Apply Formula F4-1 at each draw $m$ and timepoint $t$:

$$\text{CRCI}^{(m)}(t) = \mathbb{1}\!\Bigl[\sum_d \mathbb{1}(z_d^{(m)}(t) \leq z_{\text{multi}}) \geq k_{\text{multi}}\Bigr] \,\lor\, \mathbb{1}\!\bigl[\exists d : z_d^{(m)}(t) \leq z_{\text{single}}\bigr] \tag{F4T-4}$$

This is identical to F4-1 but evaluated at time $t$ rather than time 0.
No modification to the classification formula — only the input changes.

**Step 4: Risk curve aggregation**

$$\hat{P}(t) = \frac{1}{M} \sum_{m=1}^{M} \text{CRCI}^{(m)}(t) \tag{F4T-5}$$

This produces a risk time series: $\hat{P}(0), \hat{P}(1), \ldots, \hat{P}(T-1)$
for each scenario (natural, intervention $a$, intervention $b$, etc.).

**Step 5: Intervals at each timepoint**

Apply the same Jeffreys Beta interval (§2.4B) at each timepoint:

$$P(t) \sim \text{Beta}(S(t) + 0.5, F(t) + 0.5) \tag{F4T-6}$$

where $S(t) = \sum_m \text{CRCI}^{(m)}(t)$, $F(t) = M - S(t)$.

#### 8.2.5 Optional: Epistemic Uncertainty Inflation

E4's Formula E-6 models growing epistemic uncertainty at future timepoints:

$$\text{Var}(\theta(t)) = \text{Var}(\theta_0) + 0.01 \cdot t + 0.005 \cdot t^2$$

The R_draws capture **recovery trajectory uncertainty** (parameter noise in
$r_\infty$ and $\tau_R$). They do NOT capture **epistemic model uncertainty**
— our confidence in the model's predictions decreases over time because we
have less data about distant future outcomes.

To incorporate this, optionally add per-draw noise inflation:

$$\theta_{i,\text{inflated}}^{(m)}(t) = \theta_i^{(m)}(t) + \epsilon_i^{(m)}(t), \quad \epsilon_i^{(m)}(t) \sim \mathcal{N}(0, \sigma^2_{\text{growth}}(t)) \tag{F4T-7}$$

where:

$$\sigma^2_{\text{growth}}(t) = \text{E4\_VAR\_LINEAR\_COEFF} \cdot t + \text{E4\_VAR\_QUADRATIC\_COEFF} \cdot t^2$$

**Trade-off analysis:**

| Mode | What it captures | Cost | When to use |
|------|-----------------|------|-------------|
| Base (no inflation) | Recovery trajectory uncertainty only | O(M × T × K) | When kernels are "fitted" (from evidence) |
| Inflated | Recovery + epistemic growth | O(M × T × K) + noise sampling | When kernels are "default" (unfitted) |

**Policy:** Default to base mode. Enable inflation when `use_default_kernel_scale=True`
(same flag that E4 already uses). This is a configuration constant, not a
runtime heuristic.

```python
# In config.py:
F4T_INFLATION_SEED_OFFSET: int = 777          # Offset from base RNG seed
```

Inflation is controlled by the **same flag** that E4 uses:
`use_default_kernel_scale: bool` — passed as a parameter to
`compute_temporal_risk()`, NOT a separate config constant. This avoids
drift between E4 and F4T's inflation decisions. Both should be toggled
from the same call site in `session.py`.

When inflation is enabled, the additional noise MUST use a separate RNG
stream seeded deterministically from `base_seed + F4T_INFLATION_SEED_OFFSET`
to maintain reproducibility without contaminating the base R_draws.

#### 8.2.6 Temporal Risk Reduction Metrics

For each intervention $a$ at each timepoint $t$:

**Absolute Risk Reduction (temporal):**

$$\text{ARR}_a(t) = \hat{P}_{\text{natural}}(t) - \hat{P}_a(t) \tag{F4T-8}$$

**Relative Risk Reduction (temporal):**

$$\text{RRR}_a(t) = \begin{cases} \text{ARR}_a(t) / \hat{P}_{\text{natural}}(t) & \text{if } \hat{P}_{\text{natural}}(t) > 0 \\ \text{undefined} & \text{otherwise} \end{cases} \tag{F4T-9}$$

**Temporal NNT:**

$$\text{NNT}_a(t) = \begin{cases} 1 / \text{ARR}_a(t) & \text{if } \text{ARR}_a(t) > 0 \\ \text{undefined} & \text{otherwise} \end{cases} \tag{F4T-10}$$

**Clinically interesting derived quantities:**

| Metric | Formula | Clinical meaning |
|--------|---------|-----------------|
| Peak natural risk | $\max_t \hat{P}_{\text{natural}}(t)$ | Worst-case CRCI probability without intervention |
| Peak natural risk month | $\arg\max_t \hat{P}_{\text{natural}}(t)$ | When CRCI risk is highest |
| Peak ARR month | $\arg\max_t \text{ARR}_a(t)$ | When intervention $a$ provides maximum benefit |
| Peak ARR value | $\max_t \text{ARR}_a(t)$ | Maximum CRCI risk reduction from intervention $a$ |
| Risk resolution month | $\min\{t : \hat{P}_{\text{natural}}(t) < p_{\text{LOW}}\}$ | When natural risk drops below LOW tier |
| Accelerated resolution | $\min\{t : \hat{P}_a(t) < p_{\text{LOW}}\}$ | When risk drops below LOW with intervention |
| Months saved | resolution_natural − resolution_intervention | Time acceleration |

Where $p_{\text{LOW}} = \text{CRCI\_RISK\_TIER\_LOW} = 15\%$.

**Warning:** "Risk resolution month" is only meaningful if the natural
trajectory eventually crosses below the LOW threshold. If
$\hat{P}_{\text{natural}}(T-1) \geq p_{\text{LOW}}$, the field should be
`None` with a note: "Risk does not resolve within the {T}-month projection
horizon."

#### 8.2.7 Data Structures

```python
@dataclass(frozen=True)
class TemporalRiskPoint:
    """CRCI risk at a single future timepoint.

    Formula F4T-5: P̂(t) = (1/M) Σ CRCI^(m)(t)
    """
    month: int
    risk_pct: float                    # P̂(t) × 100
    risk_lower_pct: float             # Jeffreys lower × 100
    risk_upper_pct: float             # Jeffreys upper × 100
    mc_se: float                       # √(P̂(1−P̂)/M)
    n_domains_impaired_mean: float    # mean count of impaired domains across draws
    n_draws_crci_positive: int        # S(t) = count of draws meeting CRCI criteria


@dataclass(frozen=True)
class TemporalRiskCurve:
    """CRCI risk over time for one scenario (natural or with intervention).

    Contains the full P̂(t) time series plus summary statistics.
    """
    scenario_id: str                   # "natural" or intervention action_id
    scenario_label: str                # Human-readable label
    points: list[TemporalRiskPoint]   # One per month, 0..T-1
    peak_risk_month: int              # arg max P̂(t)
    peak_risk_pct: float              # max P̂(t) × 100
    risk_at_horizons: dict[int, float]  # {3: 42.3, 6: 38.1, 12: 25.7, 24: 12.0}
    resolution_month: int | None      # First t where P̂(t) < TIER_LOW; None if never


@dataclass(frozen=True)
class TemporalRiskReduction:
    """Risk reduction from one intervention, over time.

    Formulas F4T-8, F4T-9, F4T-10.
    """
    intervention_id: str
    arr_curve: list[float]             # ARR(t) at each month, length T
    rrr_at_horizons: dict[int, float | None]  # RRR at standard horizons
    nnt_at_horizons: dict[int, float | None]  # NNT at standard horizons
    peak_arr_month: int                # When intervention provides max benefit
    peak_arr_pct: float                # Maximum absolute risk reduction
    months_saved: int | None           # resolution_natural − resolution_intervention


@dataclass
class PredictiveRiskEstimate:
    """Complete §8.2 output — temporal risk trajectories with
    ICCTF-based CRCI classification at each future timepoint.

    NOT the same as UncertaintyResult (E4). E4 uses a single-threshold
    impairment definition; this uses the full ICCTF multi-domain criteria
    from F4 (Formula F4-1) applied at each t.

    Consumed by: report_assembler.py → RecommendationReport.predictive_risk
    Rendered by: risk_dashboard.py (temporal curves) or trajectory_plot.py
    """
    # Risk curves
    natural_curve: TemporalRiskCurve
    intervention_curves: dict[str, TemporalRiskCurve]  # intervention_id → curve

    # Risk reduction summaries
    risk_reductions: dict[str, TemporalRiskReduction]   # intervention_id → reduction

    # Best intervention by temporal profile
    best_peak_arr_intervention: str | None     # Intervention with max peak ARR
    best_resolution_intervention: str | None   # Intervention with earliest resolution

    # Metadata
    n_draws: int
    n_timepoints: int
    horizons_months: list[int]
    epistemic_inflation_applied: bool          # Whether F4T-7 was used
    coverage_fraction: float                   # From F4 domain coverage
    domain_aggregation: str                    # "mean" or "min"
    criteria_used: str                         # "ICCTF_Wefel2011_domain_level"
    gate_f4t_g1_passed: bool = False
```

#### 8.2.8 Gate: F4T-G1 (Temporal Risk Validity)

**Preconditions** (must all pass before computation):

1. **R_draws shape consistency**: `R_draws.shape[1] == theta_natural.shape[1]`
   (temporal dimensions match).
2. **Orientation gate**: All nodes in `CRCI_DOMAIN_NODE_MAP` are POS_UP
   (delegated to F4's Gate F-G4a — not duplicated).
3. **Non-degenerate R_draws**: `np.std(R_draws, axis=0)` is > 0 for at
   least `F4T_MIN_VARIABLE_TIMEPOINT_FRAC` (default: 0.50) of timepoints.
   If R_draws has zero variance, the risk curve collapses to a step
   function — technically valid but clinically useless.

```python
# In config.py:
F4T_MIN_VARIABLE_TIMEPOINT_FRAC: float = 0.50  # Gate F4T-G1 precondition #3
```

**Post-conditions** (verified after computation):

4. **Monotonicity NOT required**: Unlike E4's Var(θ(t)), risk curves are
   NOT expected to be monotone. Risk can peak and then decline (recovery)
   or fluctuate (aging vs. recovery competition). A check that asserts
   monotonicity would be scientifically wrong.
5. **Boundedness**: $\hat{P}(t) \in [0, 1]$ for all $t$.
   Jeffreys intervals must also be in [0, 100] after ×100 conversion.
6. **Paired consistency**: For any intervention $a$ at any time $t$,
   $\text{ARR}_a(t) = \hat{P}_{\text{natural}}(t) - \hat{P}_a(t)$
   must hold exactly (floating-point tolerance 1e-10).
7. **Peak coherence**: `peak_risk_month` must be the actual argmax of
   `risk_pct` in the points list. `peak_arr_month` must be the actual
   argF4T-1: theta_draws_node[m, t] = nadir_i + delta_i * R_draws[m, t] + delta_aging[t]
    theta_draws_all[node_idx, :, :] = (
        nadir_i + delta_i * R_draws + delta_aging[np.newaxis, :]  # (n_draws, T)
    
```python
def _validate_gate_f4t_g1(result: PredictiveRiskEstimate) -> None:
    """Gate F4T-G1: Temporal risk estimate validity.

    Raises:
        GateViolation: If any condition fails.
    """
```

#### 8.2.9 Computational Complexity and Optimization

**Naive implementation**: For each draw $m$ and timepoint $t$, reconstruct
$\theta_i^{(m)}(t)$ for all $K=10$ domain nodes, aggregate to domain z,
apply ICCTF.

$$\text{Operations} = M \times T \times K = 10{,}000 \times 37 \times 10 = 3.7 \times 10^6$$

(T = `E_MAX_HORIZON_MONTHS + 1` = 37 timepoints, months 0 through 36 inclusive.)

This is trivially fast (~50 ms on modern hardware). No optimization needed.

**Vectorized implementation** (preferred):

```python
# Reconstruct all draws at all timepoints for cognitive nodes only
# Shape: (n_cognitive_nodes, n_draws, T)
for node_idx, node_id in enumerate(cognitive_node_indices):
    nadir_i, delta_i = _solve_linear_coefficients(
        theta_natural[node_idx, :], R_mean
    )
    # theta_draws_node[m, t] = nadir_i + delta_i * R_draws[m, t]
    theta_draws_all[node_idx, :, :] = nadir_i + delta_i * R_draws  # (n_draws, T)

# Aggregate to domains: (n_domains, n_draws, T)
for d, node_indices in domain_to_node_indices.items():
    z_domain[d, :, :] = np.mean(theta_draws_all[node_indices, :, :], axis=0)

# ICCTF classification: vectorized across draws and timepoints
# Count domains below multi-threshold: (n_draws, T)
n_below_multi = np.sum(z_domain <= z_multi, axis=0)
# Any domain below single-threshold: (n_draws, T)
any_below_single = np.any(z_domain <= z_single, axis=0)
# CRCI positive: (n_draws, T)
crci_positive = (n_below_multi >= k_multi) | any_below_single
# Risk curve: (T,)
risk_curve = np.mean(crci_positive, axis=0)
```

For interventions, add the deterministic shift before classification:

```python
# For intervention a (aging already in theta_draws_all via F4T-1):
theta_draws_interv = theta_draws_all.copy()  # (K, M, T)
for node_idx in range(n_cognitive):
    # Only add intervention shift — aging already baked into base draws
    theta_draws_interv[node_idx, :, :] += delta_C_a * K_a  # NOT + delta_aging
```

Memory: $K \times M \times T \times 8$ bytes = $10 \times 10{,}000 \times 37 \times 8$ ≈ 29 MB per scenario.
Acceptable. No need for chunking.

#### 8.2.10 Relationship to Existing Modules

**F4 `risk_estimator.py` (§4.2) — snapshot risk:**
- §8.2 reuses F4's `CRCI_DOMAIN_NODE_MAP`, `CRCI_THRESHOLD_*` constants,
  and the ICCTF classification logic (Formula F4-1).
- F4 and F4T should share a common `_classify_icctf()` function to avoid
  drift between snapshot and temporal criteria.
- F4 operates on D1c draws `theta0_draws` at time 0. F4T operates on
  reconstructed draws at time $t$.

**E4 `uncertainty_counterfactual.py` — ITE and clinical metrics:**
- E4 and F4T both compute ARR/RRR/NNT, but using different impairment
  definitions. E4 uses a single per-node threshold on MEAN trajectories.
  F4T uses the ICCTF multi-domain criteria on PER-DRAW reconstructions.
- E4's metrics should be understood as a **quick approximation**. F4T's
  metrics are the **rigorous clinical version**.
- Both should be reported, labeled clearly:
  - E4: "Node-level impairment (composite mean < −0.5 SD)"
  - F4T: "ICCTF-criteria CRCI (≥2 domains ≤ −1.5 SD or ≥1 ≤ −2.0 SD)"

**Report assembler `_build_node_trajectory_from_draws()`:**
- F4T uses the same `nadir_i + delta_i × R_draws[m, t]` reconstruction.
- The coefficient-solving logic should be extracted to a shared utility
  rather than duplicated.

#### 8.2.11 Upgrade Path: Per-Draw Intervention Effects

In E3's current implementation, `delta_C` is collapsed to a scalar:

```python
mean_delta_C = float(np.mean(interv_effects.delta_C))  # E3, line ~340
```

This discards the per-draw variation from D2's `EffectResult.delta_C`
(which is an array of shape `(n_draws,)` representing MC uncertainty in
the intervention's effect size).

**MVP**: Use E3's scalar `delta_C`. The temporal natural↔intervention
comparison is automatically paired via shared R_draws. Intervention effect
uncertainty is NOT captured — the intervention shift is the same across all
draws.

**Upgrade**: Thread D2's per-draw `delta_C` through E3 into F4T:

$$\theta_{i,a}^{(m)}(t) = \text{nadir}_i + \delta_i \cdot R^{(m)}(t) + \Delta C_a^{(m)} \cdot K_a(t) + \delta_{\text{aging}}(t) \tag{F4T-2b}$$

This requires:
1. E3 stores `delta_C_draws: np.ndarray` (n_draws,) instead of/in addition
   to the scalar `delta_C`.
2. F4T indexes into `delta_C_draws[m]` per draw.
3. The R_draws count must match 

**Note on key types:** The internal dataclass `TemporalRiskCurve` uses
`dict[int, float]` for `risk_at_horizons`. The Pydantic model uses
`dict[str, float]` (JSON requires string keys). The converter between them
must `str(k)` the keys: `{str(k): v for k, v in curve.risk_at_horizons.items()}`.D2's draw count, or D2 draws must be
   resampled. Currently D2 uses `config.MC_DRAWS` which is the same as E2's
   draw count — alignment is guaranteed IF the config constant is shared.

**Design decision**: Do NOT implement the upgrade in the same slice as
the MVP. The scalar delta_C already captures the mean effect correctly.
Adding per-draw delta_C changes the stochasticity model and requires
re-validation of all downstream interval estimates. Flag in code:

```python
# UPGRADE_PATH: Replace scalar delta_C with per-draw delta_C_draws
# from D2's EffectResult to capture intervention effect uncertainty.
# See IMPLEMENTATION_PLAN §8.2.11 for design.
```

#### 8.2.12 Output Contract Extension

Add to `output_contracts.py`:

```python
class TemporalRiskPointView(BaseModel):
    """One point on the temporal risk curve (for serialization)."""
    month: int
    risk_pct: float
    risk_lower_pct: float
    risk_upper_pct: float

class TemporalRiskCurveView(BaseModel):
    """Temporal risk curve for one scenario."""
    scenario_id: str
    scenario_label: str
    points: list[TemporalRiskPointView]
    peak_risk_month: int
    peak_risk_pct: float
    risk_at_horizons: dict[str, float]  # "3" → 42.3 (string keys for JSON)
    resolution_month: int | None

class TemporalRiskReductionView(BaseModel):
    """Risk reduction summary for one intervention over time."""
    intervention_id: str
    peak_arr_month: int
    peak_arr_pct: float
    arr_at_horizons: dict[str, float]       # "6" → 12.3
    nnt_at_horizons: dict[str, float | None]
    months_saved: int | None

class PredictiveRiskProfile(BaseModel):
    """Complete temporal/predictive risk profile.

    Field on RecommendationReport: predictive_risk
    """
    natural_curve: TemporalRiskCurveView
    intervention_curves: list[TemporalRiskCurveView]
    risk_reductions: list[TemporalRiskReductionView]
    best_peak_arr_intervention: str | None
    best_resolution_intervention: str | None
    epistemic_inflation_applied: bool
    coverage_fraction: float
```

Add to `RecommendationReport`:

```python
predictive_risk: PredictiveRiskProfile | None = None  # §8.2
```

Schema version bump: `OUTPUT_SCHEMA_VERSION = "v1.2.0"` (minor — additive
field on existing contract).

#### 8.2.13 Approximations Declared

This section uses several approximations that must be disclosed in the output:

| # | Approximation | Justification | Impact | Upgrade path |
|---|---------------|---------------|--------|-------------|
| 1 | Domain-level aggregation (same as F4 §2.1) | ICCTF criteria are defined on individual test scores; we apply them to domain-mean z-scores | Overestimates compliance, underestimates CRCI in domains with heterogeneous tests | §8.9 Test-Level ICCTF |
| 2 | Scalar intervention effect (§8.2.11) | E3 collapses `delta_C` to mean | Underestimates uncertainty in intervention-specific risk curves | Thread per-draw `delta_C_draws` (§8.2.11) |
| 3 | Linear R→θ mapping | `theta = nadir + delta × R(t)` is exact within E3's model but assumes nodes recover proportionally | Inaccurate if nodes have differential non-linear recovery patterns | Per-node stretched-exponential parameters |
| 4 | No treatment regiment changes mid-trajectory | K_a(t) is fixed at t=0; no "start exercise at month 3" scenarios | Overestimates early risk if intervention starts later | Time-shifted K_a with configurable start month |
| 5 | Same ICCTF thresholds at all timepoints | Assumes clinical criteria don't change with time since treatment | Potentially conservative at long horizons where practice-effects may inflate raw test scores | Time-varying threshold calibration (speculative) |
| 6 | Epistemic inflation is additive Gaussian (§8.2.5) | Growing uncertainty added as IID noise, not correlated across nodes | Underestimates joint impairment at long horizons | Correlated noise from E4's full Var growth matrix |
| 7 | Uniform node-level intervention shift | E3 applies scalar `delta_C` (composite IVW mean) uniformly across all cognitive nodes. Per-node effects from D2's `delta_theta` (n_draws × n_nodes) are discarded. | Domains that should see large improvement get the same shift as low-impact domains. Domain-level risk decomposition may be inaccurate. | Thread D2's per-node `delta_theta` through E3 into F4T (requires E3 architectural change). |

#### 8.2.14 Implementation Sequence

| Step | Description | Dependencies | Output | Parallelizable with |
|------|-------------|--------------|--------|--------------------|
| 0 | F4 `risk_estimator.py` exists and passes tests | §7 Steps 1-3 | `_classify_icctf()` available | — |
| 1 | Add `F4T_*` constants to `config.py` | Step 0 | Config ready | Steps 2, 3, 5 |
| 2 | Extract `_solve_linear_coefficients()` to `crci/shared/math_utils.py` | `report_assembler.py` exists | Shared function | Steps 1, 3, 5 |
| 3 | Extract `_classify_icctf()` from `risk_estimator.py` to `crci/shared/math_utils.py` | Step 0 | Shared function | Steps 1, 2, 5 |
| 4 | Create `temporal_risk.py` with `compute_temporal_risk()` + `test_temporal_risk.py` (TDD) | Steps 1-3 + E2, E3 outputs | `PredictiveRiskEstimate` + tests | — |
| 5 | Add `PredictiveRiskProfile` to `output_contracts.py` | Spec only (no code dependency) | Contract updated | Steps 1, 2, 3 |
| 6 | Wire into `report_assembler.py` + `session.py` | Steps 4-5 | `predictive_risk` field populated | — |
| 7 | Update `risk_dashboard.py` (or `trajectory_plot.py`) to render temporal risk curves | Step 6 | Visual output | — |

**Optimized critical path** (4 phases instead of 8 sequential steps):
1. **Phase A** (parallel): Steps 1 + 2 + 3 + 5
2. **Phase B** (TDD): Step 4 (core module + tests written together)
3. **Phase C**: Step 6 (wiring)
4. **Phase D**: Step 7 (presentation)

**Hard prerequisite**: Step 0 — F4 must exist. §8.2 reuses F4's ICCTF
classification logic. Building F4T before F4 would require duplicating
that logic, violating DRY.

#### 8.2.15 Test Strategy

**Test 1: Deterministic 3-draw toy case**

Setup:
- 2 domains × 1 node each, 3 timepoints (t=0, 1, 2)
- R_draws = [[0.0, 0.5, 1.0], [0.0, 0.3, 0.7], [0.0, 0.6, 0.9]]
- theta_natural chosen so domain 1 crosses −1.5 at t=1, domain 2 stays above
- Expected: CRCI positive only under single-domain criterion (≤ −2.0)
  at specific draws/timepoints

Hand-compute:
- nadir/delta from theta_natural and R_mean
- theta_draws for each draw at each t
- domain z-scores
- CRCI classification per draw × time
- Expected P̂(t) at each timepoint

**Test 2: Intervention shifts risk curve down**

Same setup, add intervention with delta_C = +0.5, flat kernel K_a = 1.0.
Verify P̂_intervention(t) ≤ P̂_natural(t) at all timepoints.
Verify ARR(t) = P̂_natural(t) − P̂_intervention(t).

**Test 3: Gate violations**

- R_draws with wrong temporal dimension → GateViolation
- Zero-variance R_draws (all draws identical) → warning emitted
- Computed P̂(t) outside [0,1] (impossible in correct code, but test defense)

**Test 4: Epistemic inflation increases uncertainty**

With inflation enabled, verify that Jeffreys intervals widen at later
timepoints compared to base mode (same R_draws, same thresholds).

**Test 5: Resolution month detection**

Construct trajectory where P̂_natural(t) drops below 15% at t=18.
With intervention, drops below 15% at t=12. Verify `months_saved = 6`.

#### 8.2.16 Presentation Guidance

The temporal risk curves should be rendered as:

1. **Primary view**: Line chart with time (months) on x-axis, CRCI
   probability (%) on y-axis. Natural trajectory as solid line, each
   intervention as colored line. Shaded bands for Jeffreys intervals.

2. **Risk tier bands**: Horizontal shading on the chart marking LOW
   (< 15%), MODERATE (15-30%), ELEVATED (30-50%), HIGH (50-70%),
   VERY HIGH (≥ 70%) regions. This gives immediate clinical context
   to the curves.

3. **"Months saved" callout**: If an intervention accelerates crossing
   below LOW threshold, annotate the chart with an arrow showing the
   time savings.

4. **ARR table at horizons**: Tabular display of ARR, RRR, NNT at
   3/6/12/24 months for each intervention, alongside E4's existing
   metrics (labeled with their different criteria).

5. **Peak risk annotation**: Mark the peak of the natural curve with
   month and probability. This is the patient's "worst expected point."

**Critical labeling**: The chart MUST distinguish between:
- "Temporal risk projection (model-derived, uncalibrated)" — what this is
- "Observed CRCI incidence rates" — what this is NOT

The phrase "predicted risk" is acceptable if accompanied by the caveat
that predictions are from the Bayesian model, not from validated clinical
prediction rules.

### 8.3 Adaptive Intensity Ramp Scheduling
<!-- PLACEHOLDER: Temporal gap — dynamic dosage scheduling that adjusts
     intervention intensity over weeks/months based on K(t) temporal
     kernel decay from intervention_overlay.py (E3).
     Currently: static dose × timing schedules from schedule_generator.py.
     Needed: time-phased schedule where intensity ramps down as
     recovery trajectory approaches ceiling.
     TODO: Full design pending. -->

### 8.4 Research Type Heat Map
<!-- PLACEHOLDER: Engine 3 gap — visual heat map of research design types
     (RCT, prospective, cross-sectional, etc.) across edges/domains.
     Data exists in edge_evidence_v1.study_design but no aggregation
     or visualization module generates the heat map view.
     TODO: Full design pending. -->

### 8.5 Cross-Paper Pattern Detection
<!-- PLACEHOLDER: Engine 3 gap — identifying recurring patterns across
     papers (e.g., "3 studies all find exercise → BDNF but use different
     instruments"). Requires cross-edge evidence pattern mining beyond
     what evidence_compiler.py heterogeneity analysis provides.
     TODO: Full design pending. -->

### 8.6 Structured Reasoning Narrative Compiler
<!-- PLACEHOLDER: Result Reasoning gap — synthesizing intervention rankings,
     safety constraints, variance sources, and critical edges into
     clinician-readable justification text. Data exists across
     RankingResult, SafetyResult, VarianceState, StabilityState but
     no module compiles it into structured natural-language reasoning.
     TODO: Full design pending. -->

### 8.7 Extraction → Algorithm Data Bridge

The extraction pipeline (P0→P7) writes to `edge_evidence_v1` via
`evidence_writer.py`. Chain B's `evidence_compiler.py` expects
`EvidenceRecord` objects with 14 required fields. This boundary is the
**#1 scientific risk in the system** — even perfect F4/F5 logic is
meaningless if the evidence records feeding B̂ are malformed.

**Required: Contract validator at the boundary.**

```python
def load_evidence_records(
    session: Session,
    edge_ids: list[str] | None = None,
) -> tuple[list[EvidenceRecord], SchemaValidationReport]:
    """Load evidence records from edge_evidence_v1 ORM rows and validate.

    Asserts all 14 required fields exist and are non-null.
    Returns both the records and a validation report.

    Raises:
        GateViolation: If mandatory fields are missing on > BRIDGE_MAX_MISSING_PCT
                       of records.
    """
```

**Schema validation report structure:**

```python
@dataclass
class SchemaValidationReport:
    """Counts of evidence records with missing/invalid fields."""
    total_records: int
    records_with_missing_se: int
    records_with_missing_n: int
    records_with_missing_scope_weights: int
    records_with_missing_cancer_validation: int
    records_with_missing_identification_status: int
    records_with_missing_alignment: int  # alignment_tag required for P2
    completeness_fraction: float         # records with ALL 14 fields / total
    blocking_gate_triggered: bool        # True if completeness < threshold
```

**Hard gate:** `BRIDGE_MIN_COMPLETENESS = 0.80` — if fewer than 80% of
evidence records have all 14 required fields populated, Chain B compilation
is blocked. This prevents silent garbage-in-garbage-out.

**Implementation sequence:**
1. Add `load_evidence_records()` to `crci/algorithm/chain_b_evidence/evidence_loader.py` (CREATE)
2. Add `SchemaValidationReport` to `crci/shared/models/intermediate_states.py`
3. Wire into `evidence_compiler.py` entry point (replace current direct ORM access)
4. Test: insert 100 records with 20% missing SE → gate fires

**The 14 required fields:** `beta`, `se`, `n_subjects`, `study_design`,
`quality_grade`, `scope_weights`, `cancer_validation_status`,
`identification_status`, `outcome_type`, `instrument_id`, `edge_id`,
`paper_id`, `alignment_tag`, `effect_direction`.

### 8.8 Clinical Calibration Pipeline
<!-- PLACEHOLDER: Calibrating model-derived probabilities against observed
     CRCI incidence in external cohorts. Requires:
     (a) a held-out dataset with P̂(CRCI) predictions and actual outcomes,
     (b) Platt scaling or isotonic regression,
     (c) calibration slope/intercept reporting,
     (d) re-labeling output from "uncalibrated" to "calibrated" only
         after external validation.
     TODO: Full design pending. -->

### 8.9 Test-Level ICCTF Classification
<!-- PLACEHOLDER: Upgrade from domain-level to individual test-score-level
     ICCTF classification. Requires:
     (a) measure-level posterior draws (not just node-level),
     (b) measurement model mapping tests → nodes (from MEASURE_REGISTRY),
     (c) per-test z-score draws incorporating loading_b_k and intercept_a_k,
     (d) criteria applied at test level rather than domain level.
     This would eliminate the domain-aggregation approximation.
     TODO: Full design pending. -->

Extra things to do after finished: 
1. Update all the docs that represent the output of things and understand how this affects the output and create a profesional putput to the relevant documents (for eg. /workspaces/in-silico-crci-lab/docs/00_navigation/VISUAL_ROADMAP.md)

---

## 9. Output Contract Versioning, Schema Locking, and Presentation Wiring

### 9.1 Problem: Schema Drift Between Algorithm and Presentation

The classic failure mode: algorithm outputs evolve (new fields, renamed fields,
restructured nesting), but the presentation layer expects the old schema and
silently renders partial or missing data. This produces incorrect clinical
output without any error signal.

**Policy: The presentation layer is "follower-only."** It may ONLY read from
the locked output contract. It may NOT access algorithm internals directly.
All changes flow through the versioned contract.

### 9.2 Contract Versioning

Add `output_schema_version` to `RecommendationReport`:

```python
class RecommendationReport(BaseModel):
    """Top-level output contract — everything the presentation layer needs.

    This is the single object that flows from Runtime to Presentation.
    SCHEMA VERSION: v1.1.0 — bump on any field addition/removal/rename.
    """
    # Schema version — MUST be bumped on any contract change
    output_schema_version: str = "v1.1.0"

    run_id: str
    subject_ref: str
    output_mode: ReportOutputMode

    # Core outputs
    composite_score: CompositeScore
    primary_schedule: SchedulePlan
    alternative_schedules: list[SchedulePlan] = Field(default_factory=list)

    # Clinical risk (NEW — F4 output)
    clinical_risk: ClinicalRiskProfile | None = None

    # Subpopulation comparison (NEW — F5 output, None when not requested)
    subpopulation_comparison: SubpopulationComparisonSummary | None = None

    # Supporting outputs
    pathway_profile: PathwayProfile | None = None
    trajectories: list[TemporalTrajectory] = Field(default_factory=list)
    variance_decomposition: VarianceDecomposition | None = None
    evidence_gaps: EvidenceGapReport | None = None
    decision_trace: DecisionTrace | None = None

    # Safety & warnings
    safety_flags: list[str] = Field(default_factory=list)
    escalation_triggered: bool = False
    run_warnings: list[str] = Field(default_factory=list)

    # Metadata
    engine_version: str | None = None
    timestamp: str | None = None
```

**Versioning rules:**
- PATCH (v1.1.x → v1.1.y): docstring/description changes, no field changes
- MINOR (v1.1.x → v1.2.0): new OPTIONAL field added (backward compatible)
- MAJOR (v1.x → v2.0.0): field renamed/removed/type changed (breaking)

### 9.3 JSON Schema Emission (Hard Artifact)

Generate JSON Schema from the Pydantic models and commit them:

```
docs/outputs/schemas/
├── recommendation_report_v1.1.schema.json
├── clinical_risk_profile_v1.0.schema.json
└── subpopulation_comparison_v1.0.schema.json
```

**Generation script** (run after any contract change):
```python
# scripts/generate_output_schemas.py
from crci.shared.models.output_contracts import RecommendationReport
import json
from pathlib import Path

schema = RecommendationReport.model_json_schema()
path = Path("docs/outputs/schemas/recommendation_report_v1.1.schema.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(schema, indent=2))
```

The schema file is a **committed artifact** — it goes in version control.
CI can validate that the generated schema matches the committed one (drift
detection).

### 9.4 Golden-File Integration Tests

Run an end-to-end slice, serialize the `RecommendationReport` to JSON,
and commit as a golden file:

```
tests/golden/
├── recommendation_report_v1.1.json    # full report from NB08 slice
├── clinical_risk_profile_v1.0.json    # F4 output from toy case
└── subpopulation_comparison_v1.0.json # F5 output from 2-context archetype
```

**Tests:**
1. **Schema compliance:** Load golden file → validate against JSON Schema →
   all fields present, correct types
2. **Round-trip:** Deserialize → re-serialize → byte-identical (modulo
   timestamp)
3. **Presentation consumption:** Pass golden to each presentation renderer →
   no missing-field errors, no `None` deref, no empty panels without
   disclosure

### 9.5 Presentation Wiring Plan (Minimal, No Drift)

**In `report_assembler.py` (RT-I4):**

```python
# After existing report assembly:
report = RecommendationReport(
    # ... existing fields ...
    clinical_risk=_build_clinical_risk(risk_estimate) if risk_estimate else None,
    subpopulation_comparison=_build_subpop_summary(subpop_result) if subpop_result else None,
)
```

**In the presentation layer, add two panels:**

| Panel | Source field | Required? | Missing behavior |
|-------|-------------|-----------|------------------|
| "Risk Assessment" | `report.clinical_risk` | No (None until F4 built) | Render "Risk assessment not available — F4 module not yet active" |
| "Subpopulation Comparison" | `report.subpopulation_comparison` | No (None unless requested) | Render "Cross-context comparison not requested for this session" |

**Critical rendering rule:** If any panel's source field is `None`, the
presentation MUST render an explicit "not available" block with a reason
string. Silent omission is forbidden — the user must always know what
they are NOT seeing and why.

**Partial rendering disclosure:** If `clinical_risk` exists but
`low_coverage_warning` is True, the Risk panel MUST show a prominent
yellow banner: "Limited data coverage — risk estimate based primarily on
model assumptions rather than patient-specific observations."

If `subpopulation_comparison` exists but `gate_f5_g0_passed` is False,
the Comparison panel MUST show: "Paired comparison integrity could not be
verified — results may have wider uncertainty than reported."

### 9.6 SubpopulationComparisonSummary (Presentation-Ready Contract)

The full `SubpopulationComparisonResult` from F5 contains raw numpy arrays
and internal hashes not suitable for JSON serialization or presentation
consumption. A presentation-ready summary model bridges the gap:

```python
class SubpopulationComparisonSummary(BaseModel):
    """Presentation-ready F5 output (JSON-serializable)."""
    contexts_compared: list[str]      # context_keys
    n_contexts: int
    rank_concordance_matrix: dict[str, dict[str, float]]  # k₁ → k₂ → τ
    risk_differentials: list[RiskDiffSummary]
    differential_effects: list[DiffEffectSummary]
    comparison_valid: bool
    validity_notes: list[str]
    crn_coverage: str                 # "full" or "partial"
    seed_used: int

class RiskDiffSummary(BaseModel):
    context_a: str
    context_b: str
    risk_diff_pct: float
    risk_diff_ci_lower: float
    risk_diff_ci_upper: float
    domain_diffs: dict[str, float]

class DiffEffectSummary(BaseModel):
    intervention_id: str
    context_a: str
    context_b: str
    delta_C_diff_mean: float
    delta_C_diff_ci_lower: float
    delta_C_diff_ci_upper: float
    baseline_contribution: float
    mechanism_contribution: float
    practically_different: bool
    decomposition_scoring_policy: str
```

### 9.7 Build Order for Schema Locking

| Step | Action | Blocked by |
|------|--------|------------|
| 1 | Add `output_schema_version` to `RecommendationReport` | Nothing |
| 2 | Add `ClinicalRiskProfile` and `SubpopulationComparisonSummary` to `output_contracts.py` | Step 1 |
| 3 | Add `clinical_risk` and `subpopulation_comparison` fields to `RecommendationReport` | Step 2 |
| 4 | Create `scripts/generate_output_schemas.py` and generate initial schemas | Step 3 |
| 5 | Commit schema files to `docs/outputs/schemas/` | Step 4 |
| 6 | Wire `report_assembler.py` to populate new fields (None initially) | Step 3 |
| 7 | Add presentation rendering stubs with "not available" blocks | Step 6 |
| 8 | After F4 implemented: generate golden file, add round-trip test | F4 complete |
| 9 | After F5 implemented: generate golden file, add round-trip test | F5 complete |

**Steps 1-7 can be done NOW** (before F4 or F5 exist) — they just add None
fields and "not available" rendering. This locks the schema before any
algorithm modules exist, preventing the drift problem.

---

## 10. References

1. Wefel JS, Vardy J, Ahles T, Schagen SB. International Cognition and Cancer
   Task Force recommendations to harmonise studies of cognitive function in
   patients with cancer. *Lancet Oncol.* 2011;12(7):703-708.

2. Turner RM, et al. Predictive distributions for between-study heterogeneity.
   *Res Synth Methods.* 2012;3(2):111-125. (τ² priors — already used in B5)

Corrections applied after self-audit of §8.2 (2026-02-26, round 3):

| # | Issue | Correction |
|---|-------|------------|
| 24 | F4T-1 (natural trajectory) missing aging term — creates asymmetry where ARR over-attributes benefit to intervention | Added `δ_aging(t)` to F4T-1. Both natural and intervention now include aging. Added E3 divergence note explaining why F4T must compute aging independently. The nonlinear ICCTF thresholding means aging does NOT cancel (unlike E4's linear ITE subtraction). |
| 25 | Missing approximation: uniform node-level intervention shift | Added Approximation #7: E3 applies scalar `delta_C` uniformly to all nodes, discarding per-node `delta_theta` from D2. Domain-level risk decomposition may be inaccurate. Upgrade path: thread D2's per-node effects. |
| 26 | T=36 off-by-one — `E_MAX_HORIZON_MONTHS=36` means T=37 (months 0-36 inclusive) | Fixed complexity from 3.6M → 3.7M, memory from 28→29 MB. |
| 27 | Gate F4T-G1 precondition #3 uses hardcoded 50% threshold | Parameterized to `F4T_MIN_VARIABLE_TIMEPOINT_FRAC` config constant (default 0.50). |
| 28 | `F4T_EPISTEMIC_INFLATION` was a separate bool config — risks drift with E4's `use_default_kernel_scale` | Removed separate config boolean. Inflation now controlled by same `use_default_kernel_scale` parameter that E4 uses, passed into `compute_temporal_risk()`. |
| 29 | Implementation sequence suboptimal — 9 sequential steps, tests last | Reorganized to 4 phases with parallelization table. Steps 1+2+3+5 parallel. Tests co-created with Step 4 (TDD). Extraction target specified as `crci/shared/math_utils.py`. |
| 30 | Vectorized intervention code added `delta_aging` when it's already in base draws | Fixed intervention vectorized code to add only `delta_C_a * K_a` (aging already baked into base via F4T-1). |
| 31 | `risk_at_horizons` key type conversion (int→str) undocumented between dataclass and Pydantic model | Added explicit converter note in §8.2.12. |

3. Brown LD, Cai TT, DasGupta A. Interval estimation for a binomial proportion.
   *Statist Sci.* 2001;16(2):101-133. (Jeffreys interval justification)

---

## 11. Corrections Log

Corrections applied after peer review (2026-02-26):

| # | Issue | Correction |
|---|-------|------------|
| 1 | Sampling wrong object (theta0 = "baseline") | Clarified: theta0_draws are posterior samples N(θ̂, Σ_post) at time t. Added §2.2 table distinguishing current/future/baseline risk. |
| 2 | "Credible interval" was actually MC-SE interval | Replaced with two labeled intervals: MC-SE (simulation precision) and Jeffreys Beta (smoothed proportion). Neither called "credible interval." §2.4 rewritten. |
| 3 | ICCTF citation wrong (J Clin Oncol → Lancet Oncol) | Fixed to Lancet Oncol 12(7):703-708. |
| 4 | ICCTF applied at domain-level, not test-level | Declared as approximation in §2.1. Added min-aggregation option. Added §8.9 placeholder for test-level upgrade. |
| 5 | "Shapley-style" was trigger-share heuristic | Renamed to "trigger-share attribution (MVP heuristic)" throughout. §2.5B explains what true Shapley would require. |
| 6 | No missingness handling | Added §2.6 (latent-completion policy with coverage flag). Added `CRCI_RISK_MIN_COVERAGE` constant and low-coverage warning. |
| 7 | No orientation/scaling invariant check | Added Gate F-G4a: hard gate verifying all mapped nodes are POS_UP z-score. §4.6 specifies gate conditions. |
| 8 | No calibration disclaimer | Added §5.3 (explicit uncalibrated labeling). All output structures carry `calibration_status` field. Presentation must disclose. Added §8.8 placeholder for future calibration pipeline. |
| 9 | Risk tier cutoffs arbitrary | Added §5.4 acknowledging tiers are communication-only defaults, not evidence-based. Labeled in config comment. |
| 10 | Build order not gated on vertical slice | Added §0 preconditions and Step 0 in build order. F4 blocked until posterior draws are stable. |

Corrections applied after second peer review (2026-02-26, round 2):

| # | Issue | Correction |
|---|-------|------------|
| 11 | F4-1: "min(z_tests)" implied test-level draws that don't exist | Clarified in §2.1: min mode is over node_ids within domain, NOT individual test scores. Added explicit NOTE in config comment. |
| 12 | F4-2: "directly observed" not reproducibly defined | Added precise definition in §2.6: L2+ fusion level from C3c, with observation class breakdown (neuropsych, PROM, biomarker) and partial observation policy. |
| 13 | Missing non-negotiable F4 unit tests | Added §6.5: 7 mandatory tests (orientation flip, mapping completeness, aggregation divergence, Jeffreys S=0/S=M, trigger-share sum, coverage computation). |
| 14 | F5 CRN pairing not guaranteed beyond D1 | Added D3 γ stochasticity analysis to §8.1.4. D3 creates independent RNG — pairing breaks silently. Fix: inject pre-computed γ draws from F5 into D3 via `injected_gamma_draws` parameter. Updated §8.1.9 flow. |
| 15 | F5-G0 deterministic pairing invariant missing | Added F5-G0 to §8.1.7: SHA-256 hash verification of D1a, D1b, D3 γ draws. Gate runs FIRST, before any comparison. `PairingFingerprint` dataclass specified. |
| 16 | F5-M4 decomposition contaminated by severity weights | Added severity weight freeze policy to §8.1.6: Option A adopted — all severity weights fixed to 1.0 for F5-M4 decomposition runs only. `_compute_mechanism_delta_C()` specified with baseline-invariant scoring. `decomposition_scoring_policy` field added to `DifferentialEffect`. |
| 17 | Shared Λ assumption unverified after SE inflation | Added `prior_precision_fingerprint` and `posterior_precision_fingerprint` to `ContextResult` (§8.1.8). These enable verification that the shared-Λ assumption holds after C1c inflation. F5-G1 already gates out high-inflation contexts. |
| 18 | Context priors lack provenance | Added §8.1.12: `n_context_shifted_nodes` and `context_evidence_source` fields on `ContextResult`. Gate extension F5-G1b warns when both contexts have < 3 shifted nodes. |
| 19 | No output schema versioning | Added §9: `output_schema_version` field on `RecommendationReport`, JSON Schema emission to committed artifact, golden-file integration tests, presentation "follower-only" policy, `SubpopulationComparisonSummary` Pydantic model. |
| 20 | §8.7 extraction bridge was placeholder | Upgraded to full design: `load_evidence_records()` function, `SchemaValidationReport` dataclass, `BRIDGE_MIN_COMPLETENESS = 0.80` hard gate, 14 required fields enumerated. |
| 21 | Presentation wiring for new outputs unspecified | Added §9.5: `clinical_risk` and `subpopulation_comparison` fields on `RecommendationReport`, rendering rules for None/present/flagged states, mandatory "not available" disclosure blocks. |
| 22 | §8.2 Future/Predictive Risk was placeholder | Upgraded to full design (16 subsections): temporal ICCTF classification via per-draw theta reconstruction from R_draws, Formulas F4T-1 through F4T-10, `PredictiveRiskEstimate` data structure, Gate F4T-G1, optional epistemic inflation (F4T-7), vectorized implementation, upgrade path for per-draw delta_C, 6 declared approximations, 5 tests, presentation guidance. |
| 23 | Cross-reference between impl plan and presentation audit missing | Added cross-reference block before §8 pointing to `PRESENTATION_AUDIT_AND_IDEAS.md` §7. Added §7 to presentation audit with scope distinction, overlap zone, resolution status, build sequencing, and cross-document feature map. |



Origin: 

Now let me dive deeper into the critical modules that map to the diagram engines.


Now let me check the extraction pipeline and the shared config/models to understand the data flow boundaries:

Now let me check the extraction pipeline and the PROGRESS.md for current state:

Now let me check the extraction pipeline's current state more carefully to understand that boundary:

Now I have all the context needed for the critical assessment. Let me write it up.

Critical Assessment: Diagram vs. Current Infrastructure
I've audited all 27+ algorithm modules, 5 runtime modules, 7 presentation modules, and the full extraction pipeline against your diagram. Here's the honest mapping:

ENGINE 1 — Patient Risk Assessment
Diagram says: Patient inputs (background, body check, symptoms, cancer case) → 63-Node DAG → % Range Risk of CRCI

Current infrastructure coverage: ~90%

Diagram Element	Codebase Module	Status
Patient inputs	observation_mapper.py (C2) — maps raw observations to DAG nodes	Implemented
63-Node DAG	node_loader.py (A1) + edge_loader.py (A2) + graph_object.py (A5) — loads and validates full 63-node DAG with 133 edges	Implemented
Chain Validated Edges	evidence_compiler.py (B1-B6) — IVW pooling, heterogeneity, chain-vs-direct validation	Implemented
% Range Risk of CRCI	bayesian_update.py (C3) → composite_scorer.py (F1) — Bayesian posterior → IVW composite with severity tier + percentile	Implemented
Gap: The diagram shows risk as a simple "% Range" — the system actually produces a posterior distribution (θ̂ ± Σ) with a composite z-score, percentile, and 6-tier severity classification. This is more rigorous than what the diagram implies. However, converting that into a clean "X–Y% risk of CRCI" for a patient-facing output is not yet formally surfaced. composite_scorer.py computes the percentile (0–100), but framing it as a clinical "risk percentage range" with credible intervals would need a thin presentation adapter.

ENGINE 2 — Computed Data Analytics + CRCI Insights
Diagram says: Redundancy + Synergism → Aggregated Node Effect Size → Chain vs. Direct Results → Intervention Combinations & Ranking, Subpopulation Stratification, Biopathway count-to-noise ratio

Current infrastructure coverage: ~80%

Diagram Element	Codebase Module	Status
Redundancy + Synergism	synergy_bundle.py (D3) — JPO (Jaccard Pathway Overlap), CCS (Complementary Convergence Score), γ overlap discount	Implemented
Aggregated Node Effect Size	effect_propagation.py (D2) — (I−B)⁻¹ matrix propagation, composite ΔC per intervention	Implemented
Chain vs. Direct Results	evidence_compiler.py (B6) — Z-test for chain-vs-direct discrepancy, Attenuation Validity AV(e)	Implemented
Intervention Combinations & Ranking	ranker.py (D4-D6) — SAFE_A/SAFE_B scoring, bundle ranking, CrI computation	Implemented
Subpopulation Stratification	prior_loader.py (C1) — 4-level fallback by cancer_type × treatment_phase context	Partial
Biopathway count-to-noise ratio	pathway_evidence_scorer.py (B6.5) — Evidence Density ED(P) and Distinction Score DS(P) per pathway	Implemented
Gaps:

Subpopulation stratification — The system does context-matched priors per cancer type × treatment phase (33 context specs), but doesn't yet produce a head-to-head comparison view showing "Intervention X is 40% more effective for breast vs. colorectal." The underlying data (context-specific posteriors) exists, but no module generates the comparative cross-subpopulation analysis the diagram implies. This would be a new analytics module or presentation view.
"Complexity scaling" mentioned in the diagram (Chain vs. Direct Results across complexity scaling) — the system does chain-vs-direct Z-tests but doesn't parameterize these across varying model complexities. It's a single-complexity evaluation based on the full 63-node graph.
SAFETY CONSTRAINTS → Safety-Constrained Intervention Dosage
Diagram says: Safety constraints applied to intervention dosage, each assigned importance level

Current infrastructure coverage: ~95%

Diagram Element	Codebase Module	Status
Safety constraints	safety_checker.py (D3-Safety) — rule engine with CLEAR/WARNING/BLOCKED statuses per intervention	Implemented
Importance levels	ranker.py (D4-D6) — SAFE_A/SAFE_B scoring with burden penalty, dose optimization via Hill/Emax	Implemented
Dosage assignment	ranker.py — Formula D5a-EQ1 (Hill/Emax dose-response), D5c-EQ1 (composite dose)	Implemented
Constraint → dosage integration	schedule_generator.py (RT-G) — expands dose × timing variants, filters by safety, constraint ceiling	Implemented
This is the strongest match between diagram and code. The pipeline is: interventions → safety filter → dose optimization → schedule ranking, which is exactly what the diagram shows.

TEMPORAL TRAJECTORIES → Scheduled Intensity Dosage Changes
Diagram says: Temporal trajectories (w, m, y) → scheduled intensity dosage changes

Current infrastructure coverage: ~85%

Diagram Element	Codebase Module	Status
Temporal trajectories (w, m, y)	recovery_trajectory.py (E2) — stretched exponential R(t) with cancer-specific parameters at week/month/year resolution	Implemented
Nadir estimation	nadir_estimator.py (E1) — DURING_TX / EARLY_POST / LATE_POST scenario routing	Implemented
Intervention overlay on trajectory	intervention_overlay.py (E3) — trapezoidal temporal kernel (onset→build→steady→decay) with aging term	Implemented
Scheduled intensity changes	schedule_generator.py (RT-G) — generates dose × timing variants	Implemented
Gap: The diagram implies the system outputs a time-phased dosage schedule that changes intensity over weeks/months/years. The current system computes temporal trajectories (θ_natural + intervention overlays at arbitrary time points) and generates static schedules with dose/timing combos. But it doesn't yet produce a dynamic schedule where, say, "Exercise: high intensity weeks 1–8, moderate weeks 9–24, maintenance after month 6." That adaptive intensity ramp logic would need a new module bridging intervention_overlay.py → schedule_generator.py, using the K(t) kernel decay to auto-adjust dosage over time.

ENGINE 3 — Uncertainty + Research Insights
Diagram says: Uncertainty % → Uncertainty contributor source breakdown, sources per prediction, heat map of research types, patterns across papers

Current infrastructure coverage: ~75%

Diagram Element	Codebase Module	Status
Uncertainty percentage	variance_pie.py (PRES-PAT4) — mandatory 5-source pie chart	Implemented
Uncertainty contributor source breakdown	evsi.py (F3) — 5-source decomposition (literature, measurement, structural, proxy, missing) with top-2 reducible sources	Implemented
Sources per prediction/statement	provenance_viewer.py (PRES-7) — per-intervention evidence provenance	Partially implemented
Heat map of research types used	Not implemented	Missing
Patterns across papers	Not implemented	Missing
Gaps:

Heat map of research types — The system stores study_design per evidence record (RCT, prospective, cross-sectional, etc.) and outcome_type (subjective, semi_objective, biomarker). Building a heat map view (edge × design type) is straightforward data aggregation but no module generates it yet. This could be a new presentation view pulling from edge_evidence_v1 in the DB.
Patterns across papers — The extraction pipeline stores per-paper metadata, but cross-paper pattern detection (e.g., "3 studies all find exercise affects BDNF but use different measurement instruments") is not yet implemented. The evidence_compiler.py does heterogeneity analysis within an edge, but doesn't produce cross-edge or cross-paper pattern narratives.
Sources per prediction — provenance_viewer.py exists and renders evidence chains, but it's a presentation layer; the runtime doesn't yet annotate each prediction with its full evidence ancestry in a structured way beyond what report_assembler.py already passes through.
RESULT REASONING
Diagram says: Result reasoning connects back from outputs to safety-constrained dosage

Current infrastructure coverage: ~70%

The system writes a RecommendationReport (RT-I) that includes intervention rankings, uncertainty disclosure, and trajectory projections. But explicit reasoning traces — "We recommended Exercise at moderate intensity because SAFE_B = 0.42, driven by 3 RCTs on cognitive outcomes, constrained below high intensity due to fatigue risk" — are not generated as structured natural language. The data to construct such reasoning exists across:

RankingResult.per_intervention_rankings (why ranked)
SafetyResult.per_intervention (what constraints applied)
VarianceState.top_reducible (what's uncertain)
StabilityState.critical_edges (what evidence would change the recommendation)
But no "reasoning compiler" module synthesizes these into patient/clinician-readable justifications.

FUTURE CLINICAL TRIAL / RESEARCH PRIORITIES
Diagram says: Priorities to optimize accuracy & validate novel hypothesized interventions

Current infrastructure coverage: ~80%

Diagram Element	Codebase Module	Status
Evidence gap identification	evidence_gap_compiler.py (S5) — 5-tier gap classification, discovery scores	Implemented
EVSI (value of new research)	evsi.py (F3) — simplified EVSI with heterogeneity boost	Implemented
Ranking critical edges	variance_decomposer.py (F2) — critical edge identification by median-split flip analysis	Implemented
Research priority dashboard	research_dashboard.py (PRES-SCI5) — sortable table with gap counts	Implemented
This is well covered. The system can already answer "which edge should the next clinical trial target?" The gap is in the trial design specifics (sample size calculation, comparator selection) — but that's beyond the scope of the current diagram anyway.

EXTRACTION → ALGORITHM INTEGRATION POINT
Where extraction connects: The extraction pipeline (P0→P1→TB→P2→P3→P4→P4B→P5→P6→P7) produces edge_evidence_v1 rows in the database. Chain B's evidence_compiler.py consumes these as EvidenceRecord objects — this is the critical boundary.

Current state of extraction:

Full pipeline exists (pipeline.py orchestrates 11 stages)
All stage runners implemented (P0 through P6 + TB)
Evidence writer persists harmonized claims to DB
But: The EvidenceRecord dataclass in evidence_compiler.py expects 14 fields (beta, se, study_design, quality_grade, scope_weights, cancer_validation_status, etc.) and the extraction pipeline must produce exactly these. The evidence_writer currently writes to edge_evidence_v1 ORM rows; Chain B loads them via the DB. The schema alignment needs validation.
My recommendation for extraction integration:

Validate that edge_evidence_v1 table columns map 1:1 to EvidenceRecord fields
Build a load_evidence_records() function in Chain B that reads from edge_evidence_v1 via ORM and constructs EvidenceRecord objects — this is the missing glue
The extraction pipeline's P2 (harmonization) output should guarantee all 14 required fields are populated, especially scope_weights, cancer_validation_status, and identification_status which are non-trivial
Summary Scorecard
Diagram Component	Coverage	Critical Gap
Engine 1 (DAG → Risk %)	90%	Need patient-facing "risk range" formatter
Engine 2 (Analytics → CRCI Insights)	80%	Missing subpopulation comparison view
Safety Constraints → Dosage	95%	Essentially complete
Temporal Trajectories → Scheduled Changes	85%	Missing adaptive intensity ramp scheduling
Engine 3 (Uncertainty → Research Insights)	75%	Missing research type heat map + cross-paper patterns
Result Reasoning	70%	Missing structured reasoning narrative compiler
Research Priorities	80%	Solid — mostly presentation polish needed
Extraction → Algorithm boundary	~65%	Need ORM→EvidenceRecord loader + schema validation
Bottom line: The algorithm core (Chains A–F) is remarkably complete — 27 files, zero stubs, all formulas implemented with ID-tagged comments, all gates enforced. The diagram's three "engines" map well to existing chains. The biggest structural gaps are (1) the extraction→algorithm data bridge, (2) a reasoning narrative compiler, and (3) the cross-paper research pattern analysis. These are all addable without restructuring — the architecture supports them cleanly.


MY BIGGEST CONCERNS: 
- How do these map to the current presentation infrastrcuture? 


WHAT I WANT TO OUTPUT ULTIMATELY: (BIG GOAL ACROSS CODE + PAPER): 
- ultimate document stating what the final outptus area, output templates, refrence, essenstially lock in the cschema for output (for presentation + reports)
- ensure the wiring is accurate and connected from start to end 
- ensure this is actually scientfically rigoroous. 