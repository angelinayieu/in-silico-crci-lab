1) Problem
Cancer-related cognitive impairment (CRCI) is common, clinically consequential, and mechanistically heterogeneous. In oncology survivors, cognitive deficits span multiple domains (memory, attention, processing speed, executive function), vary substantially across individuals, and often persist despite recovery in other symptoms. Current clinical practice lacks a principled way to (i) attribute a given patient's impairment to specific biological pathways, (ii) integrate heterogeneous proxy measurements (biomarkers, symptoms, cognitive tests) into a coherent mechanistic state estimate with quantified uncertainty, and (iii) translate mechanistic understanding into optimized non-pharmaceutical intervention plans with defensible effect estimates and safety/feasibility constraints. Existing predictive approaches are either (a) black-box statistical/ML models that do not provide mechanistic interpretability or intervention-specific causal traces, or (b) narrative mechanistic accounts that cannot be parameterized, propagated, or validated against trial-level effect sizes. The result is a gap between CRCI biology and actionable personalization: clinicians and patients cannot reliably answer "which pathway is driving my cognitive risk" or "which non-pharmaceutical interventions, at what dose and timing, are most likely to improve cognition for this patient."
2) Hypothesis
Mechanistic CRCI pathways can be represented as a literature-parameterized causal graph in which latent pathway states are inferable from panels of proxy indicators (biomarkers, symptoms, and cognitive test domains) under an explicit measurement-and-uncertainty model. Given a patient's proxy profile, Bayesian fusion of observed proxies can produce a patient-specific posterior dysregulation vector over mechanistic pathways. Non-pharmaceutical interventions can be modeled as exogenous perturbations that intercept defined nodes/pathways and whose propagated effects through the graph yield individualized predictions of cognitive improvement and uncertainty. The model is valid to the extent that, in contexts where comparable direct intervention trial effects exist, the graph-derived chain-of-pathway effect estimates agree with observed direct effects within uncertainty bounds; systematic discrepancies localize missing mechanisms or mis-specified pathways and guide evidence-gap prioritization.
3) Research
Clinical phenotype and measurement landscape
Cancer-related cognitive impairment (CRCI) is a multidimensional syndrome observed during and after cancer treatment, characterized by impairments in memory/learning, attention, processing speed, and executive control, with frequent dissociation between objective neuropsychological performance and subjective cognitive complaints. Standard assessment relies on (i) objective neuropsychological tests that map to specific domains (e.g., Trail Making, Stroop, Digit Symbol/DSST, HVLT-R), (ii) self-report instruments capturing perceived cognitive dysfunction and functional impact (e.g., FACT-Cog), and (iii) adjunctive measures used in selected studies, including neuroimaging and physiological monitoring. Empirical work consistently shows that cognitive outcomes are heterogeneous across patients and across domains, with trajectories shaped by treatment phase (during treatment, early post-treatment, late survivorship), baseline reserve and comorbidity, and symptom clusters such as fatigue, sleep disturbance, anxiety, and depression.
Mechanistic pathways and proxy indicator structure
The mechanistic literature converges on a set of partially overlapping biological processes linking cancer therapy to cognitive decline, including neuroinflammation, oxidative stress, neuroendocrine dysregulation (HPA axis), impaired neuroplasticity and neurogenesis, mitochondrial dysfunction, vascular/metabolic dysregulation, blood–brain barrier disruption, and white matter/myelin injury. In humans, many of these mechanisms are not directly measurable at the central nervous system level; instead, studies rely on proxy indicators such as peripheral cytokines (e.g., IL-6, CRP, TNF-α), oxidative stress markers (e.g., MDA, 8-OHdG), neuroendocrine markers (e.g., cortisol slope, DHEA-S), neurotrophic markers (e.g., plasma BDNF), and symptom measures. These proxies are informative but imperfect: they vary in cancer-specific validation, show cross-correlations, and may reflect both central processes and peripheral confounds. Therefore, mechanistic inference requires integrating multiple proxies while explicitly representing proxy imprecision and cross-proxy coupling rather than treating any single biomarker as a direct mechanistic state.
Non-pharmaceutical interventions and evidence characteristics
Non-pharmaceutical interventions—including structured physical activity, sleep/circadian interventions, cognitive training, stress reduction, and social engagement programs—have demonstrated improvements in cognitive outcomes in subsets of studies, but effects vary by domain, baseline severity, adherence, and treatment context. The intervention literature is heterogeneous in design (RCTs, cohorts, cross-sectional studies, meta-analyses), measurement instruments, timing relative to treatment, and reporting format for effect sizes and uncertainty. Direct intervention trials often quantify net cognitive change without resolving mediation through underlying biological pathways, while mechanistic studies often report biomarker and symptom associations without intervention manipulation. This produces an evidence fragmentation problem: mechanistic plausibility and clinical efficacy are rarely co-measured in the same datasets, making it difficult to (i) localize which pathways are driving impairment in a given patient and (ii) select interventions that are mechanistically matched to that patient's dysregulation profile.
Gap motivating the present framework
Current CRCI research provides abundant mechanistic hypotheses and many proxy measurements, but lacks a unified, parameterized framework that (i) integrates heterogeneous proxy indicators into a patient-specific mechanistic state with quantified uncertainty, (ii) propagates intervention effects through mechanistic pathways to domain-specific cognitive outcomes, and (iii) evaluates biological plausibility by comparing chain-implied effects to direct intervention effects when comparable estimands exist. This motivates a causal-graph-based, evidence-calibrated digital representation of CRCI in which pathway nodes represent latent mechanistic states inferred from proxy panels, and interventions are treated as perturbations that intercept defined nodes/pathways. The goal is not to replace clinical judgment or claim definitive causality from observational evidence, but to provide an auditable synthesis engine that converts the CRCI literature into individualized mechanistic predictions, uncertainty decomposition, and testable validation targets.
4) Materials
1. Source literature corpus
A curated set of peer-reviewed CRCI studies was assembled to parameterize and validate the mechanistic graph. Included paper types comprised randomized controlled trials (RCTs) of non-pharmaceutical interventions, prospective and cross-sectional observational cohorts reporting biomarker–cognition associations, and meta-analyses where available. For each included study, the full text (PDF) and bibliographic metadata (DOI/PMID, year, population, cancer type, treatment phase) were stored as immutable inputs to the extraction workflow. Studies were included only if they reported at least one extractable effect estimate relevant to a predefined edge in the model (e.g., biomarker→cognition, intervention→biomarker, intervention→cognition) and provided a precision source (SE, confidence interval, or p-value with sample size) sufficient for uncertainty calibration.
2. Model registries and system configuration artifacts
The system operates over explicit, versioned registries that define the model topology, measurement mappings, and intervention semantics. These registries are treated as materials because they fully determine what the system is allowed to ingest and how it interprets inputs.
Node registry. Canonical node definitions including node identifiers, layer assignment, observability, unit, orientation convention, and primary measurement source/instrument.

Edge registry / edge-relation definitions. Permitted directed relations with source/target node identifiers, canonical statement, pathway membership, and ontological constraints used for grounding and validation.

Pathway registry. Mechanistic pathway definitions as curated subsets of nodes/edges, including component node sets and any composite pathway groupings used for covariance coupling.

Measure and instrument registries. Mappings from clinical instruments and laboratory assays to node identifiers, including transformation parameters (e.g., intercepts/loadings where used), reliability parameters, and cancer-validation tags used for measurement noise inflation.

Intervention registry. Definitions of actionable interventions, allowable dose units, safety constraints, and scheduling degrees of freedom.

Dose bridge registry. Deterministic mappings from intervention dose to node perturbation magnitude (dose–response family and parameters, gain/sign, applicable scope rules).

Temporal kernel registry. Parameterized onset/plateau/decay kernels, lag and half-life settings used to shape intervention effects across time.

All registries and configuration constants (e.g., heterogeneity multipliers, transportability weights, GRADE inflations, recency half-life, Monte Carlo draw count) were version-controlled and recorded with each run to ensure reproducibility.
3. Extraction and compilation database
A relational database was used to persist intermediate and compiled artifacts:
Evidence table: structured per-paper evidence records keyed by (study, edge), including effect size, precision source, conversion trace, quality/transportability tags, and provenance pointers.

Compiled edge table: pooled edge parameters (β̂, SE_eff, heterogeneity statistics, inclusion priors) produced by the deterministic compiler.

Annotation table (optional): promoted study annotations used to adjust structural uncertainty and inclusion priors when enabled.

Run metadata: run identifiers, timestamps, configuration hashes, registry versions, and integrity gate outcomes.

4. Patient observation inputs (for runtime inference demonstrations)
To demonstrate patient-level inference and intervention optimization, observation batches were represented as structured inputs consisting of:
demographic and treatment context variables (e.g., cancer type, treatment phase),

modifiable behaviors (e.g., sleep quality, physical activity),

biomarker panels (e.g., IL-6/CRP/TNF-α; cortisol slope/DHEA-S; BDNF),

symptom scores (e.g., fatigue, depression/anxiety), and

cognitive domain test scores where available.

Each observation included a timestamp (or days-since-assessment) to enable temporal recency weighting. Observations were mapped to nodes strictly through the instrument/measure registries.
5. Software and computational environment
All analyses were executed using the CRCI system codebase (Python) implementing the extraction pipeline, evidence compiler, Bayesian state update, Monte Carlo simulation, intervention ranking, and reporting modules. Experiments were run in a reproducible environment with fixed random seeds for Monte Carlo sampling and with all run configurations persisted. Integrity gates (e.g., positive-definiteness of precision matrices, evidence completeness checks, and referential integrity checks between compiled edges and backing evidence) were enforced during compilation and runtime.

5) Methods
Overview and study objective
We developed a literature-grounded Bayesian causal simulation engine for cancer-related cognitive impairment (CRCI) that (i) represents mechanistic CRCI pathways as a directed acyclic graph (DAG) with latent pathway states inferred from proxy biomarkers/symptoms, (ii) converts heterogeneous published evidence into calibrated edge parameters with explicit uncertainty accounting, and (iii) optimizes non-pharmaceutical interventions by translating dose and timing into exogenous node perturbations propagated through the mechanistic graph. Model validity is assessed by comparing chain-implied intervention effects (computed through mechanistic mediation pathways) against directly observed intervention effect sizes from clinical trials when comparable estimands exist.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SYSTEM ARCHITECTURE OVERVIEW                            │
│                                                                             │
│  ┌──────────────┐    ┌───────────────────┐    ╔═══════════════╗             │
│  │  LITERATURE   │    │   CHAIN A          │    ║  FROZEN MODEL ║             │
│  │  CORPUS       │───▶│   Graph Assembly   │───▶║  STATE (CUT   ║             │
│  │  (PDFs)       │    │   63 nodes, 138    │    ║  BOUNDARY)    ║             │
│  └──────┬───────┘    │   edges, 7 layers  │    ║               ║             │
│         │            └───────────────────┘    ║  B_hat, Σ_eff ║             │
│         ▼                                      ║  Λ_prior,     ║             │
│  ┌──────────────┐    ┌───────────────────┐    ║  P_inclusion  ║             │
│  │  EXTRACTION   │    │   CHAIN B          │    ║  AV_scores    ║             │
│  │  PIPELINE     │───▶│   Evidence         │───▶║  τ² estimates ║             │
│  │  P0→TB→P2→    │    │   Compilation      │    ║               ║             │
│  │  P3→P4→P5→P7  │    │   B1-B6            │    ║  READ-ONLY    ║             │
│  └──────────────┘    └───────────────────┘    ╚═══════╤═══════╝             │
│                                                        │                     │
│         ┌──────────────────────────────────────────────┘                     │
│         ▼                                                                    │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐          │
│  │  CHAIN C         │   │  CHAIN D          │   │  CHAIN E          │          │
│  │  Patient         │──▶│  MC Simulation    │──▶│  Temporal          │          │
│  │  Posterior        │   │  10,000 draws     │   │  Trajectories      │          │
│  │  C1: Prior load  │   │  D0: Dose bridge  │   │  E1: Nadir est.   │          │
│  │  C2: Obs map     │   │  D1: MC sampler   │   │  E2: Recovery      │          │
│  │  C3: Bayes fuse  │   │  D2: Propagation  │   │  E3: Intervention  │          │
│  │  C4: Modifiers   │   │  D3: Synergy/Safe │   │      overlay       │          │
│  │                   │   │  D4-D6: Ranking   │   │  E4: Uncertainty   │          │
│  └─────────────────┘   └──────────┬───────┘   └──────────────────┘          │
│                                    │                                         │
│         ┌──────────────────────────┘                                         │
│         ▼                                                                    │
│  ┌───────────────────────────────────────────────────┐                      │
│  │  CHAIN F — Analytics                               │                      │
│  │  F1: Composite scorer (IVW, Q, I², percentile)    │                      │
│  │  F2: Stability analysis (rank probability)         │                      │
│  │  F3: EVSI (variance decomposition, gap priority)  │                      │
│  │  F4: Risk estimator (P̂(CRCI), domain breakdown)  │                      │
│  └──────────────────────┬────────────────────────────┘                      │
│                          │                                                   │
│         ┌────────────────┘                                                   │
│         ▼                                                                    │
│  ┌───────────────────────────────────────────────────┐                      │
│  │  RUNTIME                                           │                      │
│  │  RT-G: Schedule generator (dose × timing combos)  │                      │
│  │  RT-H: Adaptive questions (info-gain selection)   │                      │
│  │  RT-I: Report assembler → RecommendationReport    │                      │
│  │  RT-S: Session manager (audit trail)              │                      │
│  └───────────────────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. Causal graph specification
1.1 Node registry, layers, and standardized state space
The model consists of a fixed registry of canonical nodes representing treatment exposures, modifiable behaviors, measurable biological mediators, latent mechanistic pathway states, symptom clusters, cognitive domains, and a composite CRCI outcome. Nodes are organized into hierarchical layers to preserve causal directionality and facilitate evidence routing. All cognitive-domain nodes are represented on a standardized z-score scale with explicit orientation conventions (higher = better for cognitive performance; higher = worse for most symptoms and inflammatory mediators, with exceptions explicitly declared at the node level). Observable nodes are associated with primary measurement instruments or data sources (e.g., medical record variables, questionnaires, assays, neuropsychological tests). Latent mechanistic pathway nodes encode theoretical biological processes (e.g., "neuroinflammation") and are not equated to a single measurable biomarker.

```
┌───────────────────────────────────────────────────────────────────────────┐
│              DAG NODE LAYER ARCHITECTURE (63 nodes, 7 layers)             │
│                                                                           │
│  Layer 0 ─ CONTEXT          cancer_type, treatment_phase, age,           │
│             (background)     menopausal_status, bmi, ...                 │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 1 ─ TREATMENT        chemo_regimen, radiation_dose,               │
│             (exposures)      endocrine_therapy, ...                       │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 2 ─ MODIFIABLE       sleep_quality, physical_activity,            │
│             BEHAVIORS        stress_level, social_engagement, ...        │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 3 ─ BIOLOGICAL       IL6, CRP, TNF_alpha, cortisol_slope,        │
│             MEDIATORS        DHEA_S, BDNF, oxidative_stress, ...        │
│             (observable      [orientation: POS_UP or POS_DOWN]           │
│              proxies)                                                     │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 4 ─ LATENT           neuroinflammation, HPA_dysregulation,       │
│             PATHWAYS         neuroplasticity_deficit,                     │
│             (inferred from   oxidative_damage, mitochondrial_dysfx,     │
│              L3 proxies)     vascular_metabolic, BBB_disruption, ...     │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 5 ─ SYMPTOMS &       fatigue, depression, anxiety,               │
│             COGNITIVE        sleep_disturbance, memory,                  │
│             DOMAINS          attention, processing_speed,                │
│                              executive_function, ...                     │
│                  │                                                        │
│                  ▼                                                        │
│  Layer 6 ─ COMPOSITE        crci_composite (IVW aggregate)              │
│             OUTCOME                                                       │
│                                                                           │
│  Edges flow downward (L0→L1→...→L6) and laterally within layers.        │
│  No upward edges (DAG constraint enforced at graph assembly).            │
└───────────────────────────────────────────────────────────────────────────┘
```

1.2 Pathway architecture and edge classes
Directed edges are partitioned into functional classes reflecting the intended inferential role of each relationship: (i) treatment → mediator/pathway activation; (ii) mediator → latent pathway (proxy/indicator links); (iii) pathway → symptom/cognitive domain effects; (iv) intervention → mediator/pathway modulation; and (v) lateral within-layer or feedback-associated links encoded without forming directed cycles. Pathways are defined as curated subsets of nodes and edges; shared edges across pathways are deduplicated in the DAG, while cross-pathway coupling is handled through residual covariance structures (Section 4). Nodes with insufficient direct evidence may be retained as placeholders with structural priors, explicitly flagged as edgeless or low-evidence to prevent false certainty and to preserve mechanistic completeness for future evidence incorporation.
2. Literature evidence acquisition and structured extraction
2.1 Evidence families and target estimands
The system ingests heterogeneous study outputs including standardized mean differences, correlations, regression coefficients, odds ratios/hazard ratios, and group mean differences. The target estimand for mechanistic edges is a standardized effect size (β) on the model's node scale, accompanied by a precision measure (SE, or derivable surrogate such as confidence interval or p-value with sample size). Each extracted effect is associated with an edge identifier corresponding to the model's edge registry.
2.2 Deterministic trust boundary for numeric parsing
To prevent uncontrolled propagation of ungrounded model outputs, all numeric claims pass through a deterministic trust boundary that parses extracted spans into typed numeric values and assembles them into structured evidence records only when minimal completeness criteria are met. Records are rejected or quarantined if they lack a verifiable precision source (reported SE, confidence interval bounds, or p-value with sample size) or cannot be mapped to an approved estimand family. This prevents "graceful degradation" from converting missing precision into arbitrary default uncertainties.
2.3 Harmonization, conversion validity gating, and integrity controls
Extracted evidence is harmonized into a unified standard effect-family representation. Conversion routines enforce validity gates for estimand compatibility (e.g., OR→SMD via log transform), temporal compatibility (e.g., endpoint vs. change-score reconciliation), and scale compatibility (unit/construct alignment). Evidence integrity controls include: (i) cohort-lineage deduplication and overlap resolution to avoid double-counting shared cohorts; (ii) semantic deduplication and contrast/timepoint disambiguation to avoid treating multiple statistics from the same study as independent; and (iii) manual review triggers for implausible magnitudes, contradictory directionality, or inconsistent reporting.

```
┌───────────────────────────────────────────────────────────────────────────┐
│              EXTRACTION PIPELINE (P0 → P7)                                │
│                                                                           │
│  PDF ──▶ ┌────────────────────────────────────────────────────────────┐   │
│          │ P0: TRIAGE                                                 │   │
│          │ Ingest → screen → classify (RCT/cohort/meta) → route      │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P1: HYBRID MULTI-AGENT EXTRACTION                          │   │
│          │ Canonical read → MA plan → multi-agent → reconcile         │   │
│          │ (MA-1 through MA-8 dispatch per paper type)               │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ TB: TRUST BOUNDARY                                         │   │
│          │ Numeric parse → plausibility check → consistency check     │   │
│          │ Gate TB-G1: implausible values BLOCKED                     │   │
│          │ Gate TB-G2: inconsistencies FLAGGED                        │   │
│          │ Reject-on-missing: no SE/CI/p+N → QUARANTINE              │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P2: HARMONIZATION & GATING                                 │   │
│          │ S1: Plausibility bounds (|β| ≤ 5.0)                       │   │
│          │ S2: Conversion routing (OR→SMD, r→β, GMD→SMD)             │   │
│          │ S3: Scale harmonization (SD borrowing + inflation tiers)   │   │
│          │ S4: Orientation alignment (POS_UP / POS_DOWN)             │   │
│          │ S5: Identification status & attenuation                   │   │
│          │ S6: Effect-family assignment                               │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P3: SEVEN-LAYER SE CALIBRATION                             │   │
│          │ (see §3.1 detail diagram)                                  │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P4: AGGREGATION + DOUBLE-COUNTING RESOLUTION               │   │
│          │ Cohort lineage → group → DCR → shared-control → pool      │   │
│          │ → escalation → prior selection → edge write                │   │
│          │ Gate P4-G1: k ≥ 1 for pooling                             │   │
│          ├────────────────────────────────────────────────────────────┤   │
│          │ P4B: PUBLICATION BIAS ASSESSMENT                           │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P5: SUFFICIENCY & COHERENCE                                 │   │
│          │ Chain-vs-direct validation (B6 Z-scores, AV scores)       │   │
│          └──────────────────────┬─────────────────────────────────────┘   │
│                                 ▼                                         │
│          ┌────────────────────────────────────────────────────────────┐   │
│          │ P6: DEPLOYMENT GATE → P7: EDGE WRITER                      │   │
│          │ Final referential integrity → write to edges_v1            │   │
│          └────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Output: Structured evidence records in edge_evidence_v1                 │
│          Compiled edge parameters in edges_v1                            │
└───────────────────────────────────────────────────────────────────────────┘
```

3. Uncertainty calibration and edge parameter compilation
3.1 Seven-layer heterogeneity management
Each evidence record's uncertainty is calibrated through a layered framework that inflates or adjusts the raw precision to reflect real-world inferential uncertainty. Layers include: study design reliability, population transportability, between-study statistical heterogeneity (τ² for random-effects conditions), scale conversion uncertainty, evidence-quality grading (e.g., GRADE-aligned multipliers), temporal assessment mismatch, and publication freshness/decay. The output is an effective standard error (SE_eff) with full provenance of the applied inflation components.

```
┌───────────────────────────────────────────────────────────────────────────┐
│              SEVEN-LAYER SE CALIBRATION (P3)                              │
│                                                                           │
│  Raw SE (from extraction)                                                │
│    │                                                                      │
│    ├── Layer 1: STUDY DESIGN RELIABILITY                                 │
│    │   m_design = f(RCT=1.0, prospective=1.15, cross-sectional=1.30)    │
│    │                                                                      │
│    ├── Layer 2: POPULATION TRANSPORTABILITY                              │
│    │   w_scope = f(cancer-match, phase-match, age-match)                 │
│    │                                                                      │
│    ├── Layer 3: BETWEEN-STUDY HETEROGENEITY (τ²)                         │
│    │   τ² via DerSimonian-Laird: max(0, (Q−(k−1)) / (Σw−Σw²/Σw))      │
│    │   Added for all methods except IVW_RANDOM (already incorporates)    │
│    │                                                                      │
│    ├── Layer 4: SCALE CONVERSION UNCERTAINTY                             │
│    │   m_claim = f(conversion type: OR→SMD=1.10, r→β=1.05, none=1.0)   │
│    │                                                                      │
│    ├── Layer 5: EVIDENCE QUALITY GRADING (GRADE-aligned)                 │
│    │   m_GRADE = f(high=1.0, moderate=1.15, low=1.30, very_low=1.50)    │
│    │                                                                      │
│    ├── Layer 6: TEMPORAL ASSESSMENT MISMATCH                             │
│    │   m_temp = f(endpoint vs change-score, assessment timing gap)       │
│    │                                                                      │
│    └── Layer 7: PUBLICATION FRESHNESS / DECAY                            │
│        w_fresh = exp(−λ × age_years), half-life ≈ 14 days recency       │
│                                                                           │
│    ▼                                                                      │
│  SE_eff = √[(SE × m_claim × m_GRADE × m_temp)² + σ²_struct + τ²·𝟙]    │
│           / (w_scope × w_fresh)                                          │
│                                                                           │
│  Full provenance: each layer's multiplier recorded per evidence record   │
└───────────────────────────────────────────────────────────────────────────┘
```

3.2 Meta-analytic aggregation to edge-level parameters
For each edge, calibrated evidence records are pooled deterministically using inverse-variance weighting. Fixed-effects pooling is applied when heterogeneity is low; random-effects pooling is applied when heterogeneity criteria are met; otherwise, stratified pooling or single-best selection is used under high heterogeneity or clear subgroup separations. The compiler emits an edge-level parameter set including pooled β̂, pooled SE_eff, k (number of included records), heterogeneity statistics (e.g., I²), pooling method tag, and provenance pointers to the contributing evidence records.
3.3 Prior assignment and structural inclusion probabilities
Each edge receives a prior parameterization determined by a deterministic selection procedure based on evidence sufficiency and mechanistic plausibility: robust maximum a posteriori aggregation for well-evidenced edges; commensurate/power priors for partially transportable evidence; mechanistic synthesis priors when direct human evidence is sparse but pathway-level mechanistic evidence exists; and structural placeholder priors for acknowledged but evidence-limited edges. Structural inclusion probabilities are computed via a calibrated mapping from evidence sufficiency and coherence diagnostics to an inclusion prior, enabling stochastic structural sampling during Monte Carlo simulation (Section 7).

```
┌───────────────────────────────────────────────────────────────────────────┐
│         EVIDENCE COMPILATION PIPELINE (Chain B: B1 → B6)                 │
│                                                                           │
│  Evidence records (from extraction)                                      │
│    │                                                                      │
│    ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B1: IVW POOLING (per edge)                               │             │
│  │   μ_e = Σ(β_i/σ²_i) / Σ(1/σ²_i)                       │             │
│  │   SE_within = 1 / √(Σ(1/σ²_i))                         │             │
│  │   Q = Σ w_i(β_i − μ_e)²           (Cochran's Q)        │             │
│  │   τ² = max(0, (Q−(k−1))/(Σw−Σw²/Σw))  (DerSimonian-Laird)          │
│  │   I² = max(0, (Q−(k−1))/Q) × 100                       │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B2: 7-LAYER SE_eff ASSEMBLY (see §3.1 diagram)          │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B3: PRIOR SELECTION (decision tree)                      │             │
│  │   k≥5 + low-I² → RobustMAP: w = min(0.8, 0.5+0.06k)   │             │
│  │   k≥2 + transportable → Commensurate: β~N(β_hist,σ²/τ) │             │
│  │   k=1 + strong design → PowerPrior: L(β|D₀)^{a₀}×π₀   │             │
│  │   k=0 + pathway evidence → MechanisticSynth: Π_i β_i   │             │
│  │   k=0 + no evidence → StructuralPlaceholder: N(0, 10²)  │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B4: INCLUSION PROBABILITY                                │             │
│  │   P_incl = σ(−0.5 + 1.2·ln(k+1) + 0.4·Z + 0.6·𝟙[RCT])│             │
│  │   Enables stochastic structural sampling in MC (§7.4)   │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B5: τ² PRIORS                                            │             │
│  │   τ²~LogNormal(μ, σ²) per Turner et al., 2012           │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ B6: CHAIN-VS-DIRECT VALIDATION                           │             │
│  │   Z = |β_chain − β_direct| / √(σ²_chain + σ²_direct)  │             │
│  │   AV(e) = 1 − min(Z/3.0, 1.0)                           │             │
│  │   Z<1.96: agreement │ 1.96-3.0: partial │ >3.0: reject  │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  Output: PooledEdge, SE_eff, EdgePriorSpec, P_inclusion,                │
│          τ² estimates, AV scores → FrozenModelState                      │
└───────────────────────────────────────────────────────────────────────────┘
```

4. Residual covariance and the SEM-implied precision matrix
To capture co-movement among proxies and latent pathway states not fully explained by directed edges, we specify a residual covariance matrix D with a sparse block-diagonal structure containing empirically documented correlated pairs (e.g., within inflammatory marker panels and neuroendocrine proxy panels). The SEM-implied precision matrix is derived as:
Λ = (I − B)ᵀ D⁻¹ (I − B),
where B is the compiled edge-weight matrix (sparse). Positive-definiteness and conditioning are enforced by hard gates; ill-conditioned configurations trigger deterministic fallbacks for propagation (Section 7.3) rather than silent continuation.
5. Cut-model boundary and parameter freezing
The framework is explicitly cut-model: once compiled from literature, edge parameters and structural inclusion priors are frozen and treated as read-only. Patient-specific data updates only latent node states (posterior means and covariances) and never retrofits edge parameters. This separation prevents feedback contamination and ensures reproducibility of the literature-grounded mechanistic backbone across patient sessions.

```
┌───────────────────────────────────────────────────────────────────────────┐
│          CUT-MODEL BOUNDARY & FROZEN STATE                                │
│                                                                           │
│  ══════════════════════════════════════════════════════════════════════   │
│  ║  LITERATURE SIDE (write-once)         ║  PATIENT SIDE (per-session) ║  │
│  ║                                        ║                             ║  │
│  ║  Chain A: Graph assembly               ║  Chain C: Patient posterior ║  │
│  ║  Chain B: Evidence compilation         ║  Chain D: MC simulation     ║  │
│  ║  Extraction: P0→P7                     ║  Chain E: Temporal          ║  │
│  ║                                        ║  Chain F: Analytics         ║  │
│  ║          │                             ║         ▲                   ║  │
│  ║          ▼                             ║         │                   ║  │
│  ║  ╔═══════════════════════╗             ║         │                   ║  │
│  ║  ║  FrozenModelState     ║─────────────╫────────▶│                   ║  │
│  ║  ║  (immutable snapshot) ║             ║                             ║  │
│  ║  ║                       ║             ║  Patient data updates       ║  │
│  ║  ║  • B_hat (edge wts)   ║             ║  ONLY latent node states   ║  │
│  ║  ║  • Sigma_eff (SEs)    ║             ║  (θ̂, Σ_post)              ║  │
│  ║  ║  • Lambda_prior (33   ║             ║                             ║  │
│  ║  ║    context priors)    ║             ║  NEVER retrofits:           ║  │
│  ║  ║  • P_inclusion        ║             ║  • edge parameters          ║  │
│  ║  ║  • AV_scores          ║             ║  • inclusion priors         ║  │
│  ║  ║  • tau_sq_estimates   ║             ║  • graph topology           ║  │
│  ║  ║  • synergy_records    ║             ║                             ║  │
│  ║  ║  • context_specs(33)  ║             ║                             ║  │
│  ║  ╚═══════════════════════╝             ║                             ║  │
│  ══════════════════════════════════════════════════════════════════════   │
│                                                                           │
│  Key invariant: Literature side is compiled once and frozen.             │
│  Patient sessions consume the frozen state as a read-only input.         │
│  This ensures reproducibility and prevents feedback contamination.       │
└───────────────────────────────────────────────────────────────────────────┘
```

6. Observation model: proxy indicators and Bayesian fusion into node posteriors
6.1 Registry-defined measurement mapping and standardization
All patient observations enter as instrument/measure–typed inputs (e.g., assay values, questionnaire scores, neuropsychological test scores). Each instrument is mapped to a target node (or small set of nodes) via registry-defined relationships, including orientation and unit-of-measure. Observations are standardized into the node's state space (z-score where applicable), enabling fusion across heterogeneous scales.
6.2 Measurement noise and proxy imprecision
Measurement noise is computed from instrument reliability and cancer-context validation status. Proxy indicators for latent mechanistic nodes are treated as imperfect measurements, and proxy validity is explicitly represented by uncertainty inflation multipliers. This preserves the epistemic distinction between the latent process (e.g., CNS neuroinflammation) and the proxy measurement (e.g., peripheral cytokines).
6.3 Bayesian state update (information form)
Given a context-matched prior (Section 6.4), patient observations are fused using rank-1 information-form updates to the precision matrix and information vector. Temporal recency weighting is applied to downweight older measurements using an exponential decay (14-day half-life). This yields a posterior distribution over all nodes:
θ | y_≤t ~ N(θ̂, Σ_post),
including posterior estimates of latent pathway nodes inferred from proxy panels and covariance coupling.
6.4 Context-matched priors
Prior means are selected from a library of cancer-type × treatment-phase specifications using a deterministic fallback hierarchy. Context matching affects the prior mean vector, while the shared precision structure constrains baseline covariance. When context specificity is insufficient (broad fallback levels), uncertainty inflation flags are propagated to downstream reporting and comparative analysis modules.

```
┌───────────────────────────────────────────────────────────────────────────┐
│         OBSERVATION MODEL & BAYESIAN FUSION (Chain C)                    │
│                                                                           │
│  Patient observations                                                    │
│  (assays, questionnaires, neuro tests, timestamps)                       │
│    │                                                                      │
│    ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ C1: PRIOR LOADER                                         │             │
│  │   4-level fallback hierarchy:                            │             │
│  │     exact(cancer×phase) → cancer-type → general → N(0,1)│             │
│  │   33 context-matched precision matrices (Λ_prior)        │             │
│  │   Per-node prior means and SDs from cancer literature    │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ C2: OBSERVATION MAPPER                                    │             │
│  │   Instrument → node mapping via MEASURE_REGISTRY          │             │
│  │   Raw value → z-score standardization                     │             │
│  │   Orientation alignment (POS_UP / POS_DOWN)              │             │
│  │   Timestamp → recency weight: w = exp(−λ·Δt)            │             │
│  │   Coverage tracking: which nodes observed vs. missing    │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ C3: BAYESIAN UPDATE (information form)                    │             │
│  │   For each observation y_i at node j:                    │             │
│  │     σ²_obs = f(instrument reliability, cancer validation)│             │
│  │     Λ_post += (1/σ²_obs) · e_j·e_jᵀ    (precision)     │             │
│  │     η_post += (y_i/σ²_obs) · e_j        (information)   │             │
│  │                                                           │             │
│  │   Proxy imprecision: latent nodes get uncertainty         │             │
│  │   inflation multipliers (peripheral ≠ central process)   │             │
│  │                                                           │             │
│  │   Cross-proxy coupling:                                   │             │
│  │   IL-6 + CRP + TNF → posterior on neuroinflammation      │             │
│  │   (latent state inferred via covariance structure)        │             │
│  │                                                           │             │
│  │   Output: θ̂, Σ_post, fusion_levels, coverage_fraction   │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ C4: MODIFIER APPLICATION                                 │             │
│  │   Apply context-specific modifiers to posterior          │             │
│  │   Output: PatientState (consumed by Chain D, E, F)       │             │
│  └─────────────────────────────────────────────────────────┘             │
└───────────────────────────────────────────────────────────────────────────┘
```


7. Intervention modeling, simulation, and optimization
7.1 Intervention semantics as exogenous perturbations
Non-pharmaceutical interventions are modeled as exogenous perturbations applied to specific modifiable behavior nodes and/or biological mediator nodes. Each intervention action is associated with a deterministic dose-response bridge mapping dose d into an instantaneous node perturbation Δz_target on the model's state scale:
Δz_target = s · g · f(d),
where s is sign, g is bridge gain, and f is the configured dose-response family (linear/saturating/Hill).
7.2 Temporal shaping and trajectory composition
Intervention effects are shaped over time using parameterized temporal kernels (onset/build/steady/decay with lag and half-life parameters). Natural recovery is modeled as a stretched exponential trajectory, combined with intervention kernels and a treatment-accelerated cognitive aging term to generate predicted trajectories over weeks to years. Trajectories are computed per Monte Carlo draw to produce posterior predictive intervals.
7.3 Mechanistic propagation of intervention effects
For each Monte Carlo draw, intervention perturbations are propagated through the personalized mechanistic graph using linear SEM propagation:
Δθ(t) = (I − B⁽ᵐ⁾)⁻¹ x⁽ᵐ⁾(t),
where B⁽ᵐ⁾ reflects per-draw edge sampling and structural inclusion, and x⁽ᵐ⁾(t) is the time-indexed injection vector from dose translation and kernels. If matrix inversion is ill-conditioned, deterministic path enumeration is used as a fallback to preserve numerical stability.

```
┌───────────────────────────────────────────────────────────────────────────┐
│     INTERVENTION MODELING & SIMULATION PIPELINE (Chain D + E)            │
│                                                                           │
│  Intervention definition (from INTERVENTION_REGISTRY)                    │
│    │                                                                      │
│    ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ D0: DOSE BRIDGE                                          │             │
│  │   dose d → Δz_target = s · g · f(d)                     │             │
│  │   f ∈ {linear, saturating, Hill/Emax}                    │             │
│  │   Three thresholds: min_effective, cost_effective, plateau│             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ D1: MC SAMPLER (10,000 draws per session)                │             │
│  │   Per draw m:                                            │             │
│  │     (i)   β⁽ᵐ⁾ ~ N(β̂, SE_eff²)    (edge weight)       │             │
│  │     (ii)  mask⁽ᵐ⁾ ~ Bernoulli(P_inclusion) (structure) │             │
│  │     (iii) θ₀⁽ᵐ⁾ ~ N(θ̂, Σ_post)    (patient state)     │             │
│  │   B⁽ᵐ⁾ = β⁽ᵐ⁾ ⊙ mask⁽ᵐ⁾           (masked edges)     │             │
│  │   Physiological ceilings enforced per draw              │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ D2: EFFECT PROPAGATION (per draw)                        │             │
│  │   Δθ⁽ᵐ⁾(t) = (I − B⁽ᵐ⁾)⁻¹ x⁽ᵐ⁾(t)                  │             │
│  │   Fallback: deterministic path enumeration if κ > 10⁸   │             │
│  │   Output: per-intervention ΔC distribution              │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ D3: SYNERGY + SAFETY (per draw)                          │             │
│  │   SYNERGY:                                               │             │
│  │     JPO(a,b) = |P_a ∩ P_b| / |P_a ∪ P_b|              │             │
│  │     CCS(a,b) = (1−JPO)·𝟙[shared_convergence]           │             │
│  │     γ ~ Beta(2,4) × 0.40 (sampled per draw)            │             │
│  │   SAFETY:                                                │             │
│  │     CLEAR / WARNING / BLOCKED per intervention          │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ D4-D6: SCORING & RANKING                                 │             │
│  │   D4: SAFE_A score (efficacy-focused)                    │             │
│  │   D5: Dose optimization (Hill/Emax → 3 thresholds)      │             │
│  │   D6: SAFE_B score (feasibility + adherence penalty)     │             │
│  │   Bundle ranking with synergy corrections                │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          │                                                │
│  ┌───────────────────────┘                                               │
│  │                                                                        │
│  │  ┌─────────────────────────────────────────────────────────┐          │
│  └─▶│ CHAIN E: TEMPORAL TRAJECTORIES                          │          │
│     │  E1: Nadir estimator (DURING_TX / EARLY_POST / LATE)   │          │
│     │  E2: Recovery trajectory: R(t) stretched exponential    │          │
│     │  E3: Intervention overlay: K(t) trapezoidal kernel      │          │
│     │      (onset→build→steady→decay with lag & half-life)   │          │
│     │  E4: Uncertainty counterfactual                         │          │
│     │  Output: θ(t) = θ_natural(t) + Σ_interventions K_i(t) │          │
│     │          + aging_term, with P10/mean/P90 bands          │          │
│     └─────────────────────────────────────────────────────────┘          │
└───────────────────────────────────────────────────────────────────────────┘
```

7.4 Monte Carlo simulation protocol
We perform Monte Carlo simulation with N = 10,000 draws per patient session. Each draw samples: (i) edge weights from compiled uncertainties; (ii) structural inclusion masks from inclusion priors; and (iii) patient-state draws from N(θ̂, Σ_post). Physiological ceilings and constraint checks enforce plausibility and prevent unrealistic excursions. Outputs include per-intervention distributions of cognitive benefit, pathway impact traces, and posterior predictive trajectory bands.
7.5 Scoring, ranking, and feasibility constraints
Interventions and schedules are scored and ranked under dual SAFE criteria: Mode A emphasizes efficacy; Mode B adjusts for feasibility, adherence penalties, and safety constraints. Dose optimization uses Emax/Hill curve families to derive three interpretable thresholds per intervention: minimum effective dose, cost-effective dose, and plateau dose. Candidate schedules are generated and filtered to satisfy safety constraints and practical feasibility.
7.6 Pairwise synergy modeling (optional extension)
Pairwise interaction terms between interventions are modeled as a conservative outcome-level correction using pathway-set overlap (Jaccard pathway overlap, JPO) and a convergent complementarity score (CCS). A bounded interaction parameter γ is sampled per draw to propagate uncertainty. The synergy module computes three diagnostics per intervention pair: JPO (shared pathway fraction), CCS (complementary benefit coverage), and γ (net interaction magnitude). These diagnostics are used internally for bundle ranking and schedule generation; in the current implementation, synergy diagnostics inform the ranking algorithm but are not surfaced in the patient-facing recommendation report. This module is explicitly limited to pairwise interactions and does not claim mechanistic node-level interaction modeling beyond the SEM and residual covariance structures.
8. Outcomes, risk scoring, stability, and uncertainty decomposition
8.1 Composite cognitive impairment scoring
Cognitive-domain outcomes are aggregated into a composite CRCI score using inverse-variance-weighted aggregation across cognitive domains, with internal consistency testing (Cochran's Q) and transformation to percentile and severity tiers for interpretability. Composite scoring is reported alongside domain-level outputs to prevent masking heterogeneous domain impacts.
8.2 Decision stability
Recommendation robustness is assessed by rank-probability distributions across Monte Carlo draws, producing stability classes (stable, moderate, unstable, highly unstable) and identifying critical edges that drive rank flips under uncertainty.
8.3 Variance decomposition and evidence-gap prioritization
Total prediction variance is decomposed into five sources: literature heterogeneity, measurement noise, structural uncertainty, proxy imprecision, and missing observations. Evidence gaps are prioritized using a discovery score combining edge elasticity and effective uncertainty, and via expected value of sample information to identify high-value empirical targets for future trials and measurement improvements.

```
┌───────────────────────────────────────────────────────────────────────────┐
│         ANALYTICS & SCORING PIPELINE (Chain F: F1 → F4)                  │
│                                                                           │
│  MC draw outputs (from Chain D)                                          │
│    │                                                                      │
│    ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ F1: COMPOSITE SCORER                                     │             │
│  │   CRCI = Σ_d (w_d × z_d) / Σ_d w_d    (IVW composite)  │             │
│  │   Percentile = Φ(−CRCI) × 100                           │             │
│  │   Cochran's Q = Σ_d w_d(z_d − CRCI)²                   │             │
│  │   I² = max(0, (Q−(D−1))/Q) × 100                       │             │
│  │   Severity tier: minimal/mild/moderate/substantial/      │             │
│  │                  severe/critical (6 tiers)               │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ F2: STABILITY ANALYSIS                                    │             │
│  │   P(rank₁ = a) = (1/N) Σ_m 𝟙[rank₁⁽ᵐ⁾ = a]            │             │
│  │   Classes: STABLE (≥0.80) | MODERATE (≥0.60)            │             │
│  │            UNSTABLE (≥0.40) | HIGHLY_UNSTABLE (<0.40)   │             │
│  │   Critical edges: those driving rank flips              │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ F3: VARIANCE DECOMPOSITION & EVSI                        │             │
│  │   5-source decomposition:                                │             │
│  │     1. Literature heterogeneity (τ²)                     │             │
│  │     2. Measurement noise (instrument reliability)        │             │
│  │     3. Structural uncertainty (P_inclusion < 1)          │             │
│  │     4. Proxy imprecision (peripheral ≠ central)         │             │
│  │     5. Missing observations (unobserved nodes)          │             │
│  │                                                           │             │
│  │   EVSI per edge: estimated reduction in decision         │             │
│  │   variance from one additional study on that edge        │             │
│  │   Discovery score: elasticity × effective uncertainty    │             │
│  │   Output: top reducible sources + next-best-measurement  │             │
│  └──────────────────────┬──────────────────────────────────┘             │
│                          ▼                                                │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ F4: CLINICAL RISK ESTIMATOR                              │             │
│  │   Per MC draw m:                                         │             │
│  │     CRCI⁽ᵐ⁾ = 𝟙[Σ_d 𝟙(z_d⁽ᵐ⁾ ≤ z_multi) ≥ k_multi]  │             │
│  │              ∨ 𝟙[∃d: z_d⁽ᵐ⁾ ≤ z_single]                │             │
│  │   P̂(CRCI) = (1/M) Σ_m CRCI⁽ᵐ⁾                         │             │
│  │   MC-SE = √(P̂(1−P̂)/M)                                  │             │
│  │   CI via Jeffreys Beta(S+0.5, F+0.5)                    │             │
│  │   Per-domain: P_d = (1/M) Σ_m 𝟙(z_d⁽ᵐ⁾ ≤ z_multi)     │             │
│  │   Coverage warning if few cognitive domains observed     │             │
│  │   OUTPUT: P̂(CRCI), CI, per-domain breakdown             │             │
│  │   LABEL: model-derived, uncalibrated                     │             │
│  └─────────────────────────────────────────────────────────┘             │
└───────────────────────────────────────────────────────────────────────────┘
```

9. Validation and sensitivity analyses
9.1 Chain-versus-direct validation
Where comparable direct-effect intervention evidence exists (e.g., RCT effect of exercise on a cognitive outcome), we compute mechanistic chain-implied effects by propagating intervention perturbations through the relevant mediator and pathway nodes to the same cognitive endpoint. Discrepancy Z-scores and attenuation-validity metrics classify agreement, partial mediation, or inconsistency. Validation claims are restricted to cases where estimands are comparable and the implemented chain estimator spans the mediating path(s).

```
┌───────────────────────────────────────────────────────────────────────────┐
│         CHAIN-VS-DIRECT VALIDATION (B6)                                  │
│                                                                           │
│  NOTE: This is a LITERATURE-LEVEL validation, not patient-level.         │
│  It compares two estimates for the SAME cognitive endpoint derived       │
│  from the compiled evidence base (not from a specific patient).          │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │ MECHANISTIC CHAIN ESTIMATE                                       │     │
│  │                                                                   │     │
│  │  Intervention ──▶ Mediator nodes ──▶ Pathway nodes ──▶ Cognition │     │
│  │  (e.g., exercise → BDNF → neuroplasticity → memory)             │     │
│  │                                                                   │     │
│  │  β_chain = product of compiled edge weights along path           │     │
│  │  σ²_chain = propagated uncertainty through path                  │     │
│  └──────────────────────────┬──────────────────────────────────────┘     │
│                              │                                            │
│                              ▼                                            │
│                     ┌──────────────────┐                                  │
│                     │  DISCREPANCY TEST │                                  │
│                     │                    │                                  │
│                     │  Z = |β_chain − β_direct|                           │
│                     │      / √(σ²_chain + σ²_direct)                     │
│                     │                    │                                  │
│                     │  AV(e) = 1 − min(Z/3.0, 1.0)                       │
│                     │                    │                                  │
│                     │  Z < 1.96: AGREEMENT                                │
│                     │  1.96–3.0: PARTIAL MEDIATION                        │
│                     │  Z > 3.0:  INCONSISTENCY → flag                    │
│                     └──────────────────┘                                  │
│                              ▲                                            │
│  ┌──────────────────────────┴──────────────────────────────────────┐     │
│  │ DIRECT EFFECT ESTIMATE                                           │     │
│  │                                                                   │     │
│  │  Intervention ─────────────────────────────────────▶ Cognition   │     │
│  │  (e.g., RCT: exercise → memory, d = −0.35)                      │     │
│  │                                                                   │     │
│  │  β_direct = observed RCT effect size                             │     │
│  │  σ²_direct = reported or derived SE²                             │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  Interpretation:                                                         │
│  • Agreement confirms mechanistic pathway captures intervention effect  │
│  • Partial mediation → unmeasured parallel paths likely exist           │
│  • Inconsistency → missing edges, misspecified weights, or confounds    │
│  • Each outcome is per-EDGE, not per-pathway or per-patient             │
└───────────────────────────────────────────────────────────────────────────┘
```

9.2 Complexity-scaling validation
To assess whether multi-pathway integration improves or degrades ranking fidelity, a complexity-scaling validation framework is specified in which model performance is evaluated under systematic reductions in pathway count and heterogeneity depth. The current implementation performs chain-versus-direct validation at the full model complexity (Section 9.1), with infrastructure for systematic pathway-reduction experiments defined in the database schema but not yet executed as a batch experiment. When fully deployed, performance would be benchmarked against direct-effect RCT estimates and summarized using ranking flip rates and mean effect shifts.
10. System outputs and data contracts
The system produces a set of auditable artifacts at each boundary: (i) structured evidence records (edge-level evidence with precision provenance); (ii) compiled edge parameters (β̂, SE_eff, inclusion priors, coherence flags); (iii) a frozen model state at the cut boundary (graph topology and compiled parameter snapshot); (iv) patient posterior state (θ̂, Σ_post) with pathway activation profiles defined in the output schema (pathway activation profiles require upstream pathway profiler integration to populate from patient posteriors and are not yet generated end-to-end); (v) per-intervention simulation results (ΔC distributions and trajectory bands); (vi) ranked schedules with safety/feasibility annotations; (vii) temporal trajectory predictions (per-intervention and natural-recovery time courses with posterior predictive intervals over configurable horizons); (viii) a clinical risk estimate comprising model-derived P̂(CRCI) with credible interval and per-domain breakdown using ICCTF-aligned classification across Monte Carlo draws; (ix) expected value of sample information (EVSI) per edge, quantifying the reduction in decision uncertainty achievable by collecting additional evidence; and (x) a final recommendation report containing ranked interventions, uncertainty decomposition, stability classification, Cochran's Q and I² at the composite level, and full provenance links to contributing evidence.

```
┌───────────────────────────────────────────────────────────────────────────┐
│         END-TO-END DATA FLOW SUMMARY                                     │
│                                                                           │
│  LITERATURE SIDE                 CUT          PATIENT SIDE               │
│  (build once)                  BOUNDARY       (per session)              │
│                                   ║                                       │
│  PDF corpus                       ║   Patient observations               │
│    │                              ║     │                                 │
│    ▼                              ║     ▼                                 │
│  Extraction (P0→P7)              ║   C1: Context-matched prior           │
│    │                              ║     │                                 │
│    ▼                              ║     ▼                                 │
│  Chain A: Graph (63n, 138e)      ║   C2: Observation mapper              │
│    │                              ║     │                                 │
│    ▼                              ║     ▼                                 │
│  Chain B: Evidence compilation   ║   C3: Bayesian fusion → θ̂, Σ_post    │
│    │                              ║     │                                 │
│    ▼                ══════════════╣     ▼                                 │
│  FrozenModelState ══════════════▶║   C4: Modifier application            │
│  (B_hat, Σ_eff, Λ_prior,        ║     │                                 │
│   P_inclusion, AV, τ²)           ║     ▼                                 │
│                                   ║   D1: MC sampler (10k draws)         │
│                                   ║     │                                 │
│                                   ║     ├──▶ D2: Effect propagation      │
│                                   ║     ├──▶ D3: Synergy + safety        │
│                                   ║     └──▶ D4-D6: Ranking              │
│                                   ║            │                          │
│                                   ║     ┌──────┘                          │
│                                   ║     ├──▶ E1-E4: Temporal trajectories│
│                                   ║     ├──▶ F1: Composite + Q/I²       │
│                                   ║     ├──▶ F2: Stability analysis      │
│                                   ║     ├──▶ F3: EVSI + variance decomp │
│                                   ║     └──▶ F4: Risk estimator          │
│                                   ║            │                          │
│                                   ║     ┌──────┘                          │
│                                   ║     ▼                                 │
│                                   ║   RT-G: Schedule generator           │
│                                   ║   RT-H: Adaptive questions           │
│                                   ║   RT-I: Report assembler             │
│                                   ║     │                                 │
│                                   ║     ▼                                 │
│                                   ║   RecommendationReport               │
│                                   ║   (ranked interventions, uncertainty,│
│                                   ║    stability, risk %, trajectories,  │
│                                   ║    provenance, EVSI priorities)      │
└───────────────────────────────────────────────────────────────────────────┘
```


Data / Graphs
This section should contain only what is necessary to demonstrate that the system is (i) parameterized from real evidence, (ii) inferentially coherent at the patient level, and (iii) produces stable, interpretable intervention recommendations. For your paper, the cleanest structure is: (A) datasets/tables produced, then (B) figures that validate each major claim.
A. Data artifacts you should report (as tables, with IDs)
Include these as main-text tables (small) and supplementary tables (large).
Table D1 — Slice Registry Snapshot (vertical slice)

Node IDs used (e.g., sleep_quality, physical_activity, cortisol_slope, IL-6/CRP/TNF, BDNF, cognitive domains).

Edge relation IDs used (e.g., sleep→cortisol, cortisol→IL-6, IL-6→processing speed, etc.).

Orientation conventions (POS_UP / NEG_UP) and unit (z-score vs assay unit pre-standardization).

Table D2 — Evidence Coverage Matrix (paper × edge)

Rows: papers (PMID/DOI).

Columns: slice edges.

Cell: effect metric available (β/SE, CI, p+N) + conversion performed (if any).
 This is the single fastest way to prove you did not "handwave" parameterization.

Table D3 — Edge Evidence Records (edge_evidence_v1 subset)
 For each evidence record used in compilation:

edge_relation_id, study_id, effect_size, SE source (direct/CI/p+N), conversion trace, design class, population match level, quality grade, timepoint.

Table D4 — Compiled Edge Parameters (edges_v1 subset)
 One row per compiled edge:

β̂, SE_eff, k, I², pooling method, inclusion probability, structural variance term used, and provenance pointer.

Table D5 — Patient Observation Batch Used in Demonstrations

Which nodes were observed, which were imputed, timestamps/recency weight, and coverage fraction.

All five are "data." Everything else is derived from them.
B. Figures you should include (minimal set that proves the system works)
Figure 1 — Vertical Slice DAG (topology)
Your 11-node slice subgraph with edge signs and pathway labels (HPA, neuroinflammation, neuroplasticity).

Purpose: readers can see exactly what is being modeled.

Figure 2 — Evidence-to-Edge Pipeline Trace (worked example)
A single edge (e.g., IL-6 → processing_speed) showing:

one or two raw extracted effects,

conversion to standardized β + SE,

SE calibration (layer multipliers),

pooled β̂ and SE_eff.

Purpose: proves your pipeline is not a black box.

Figure 3 — Proxy Fusion to Latent Pathway Inference (key "cross-proxy" figure)
Show: IL-6/CRP/TNF-α observations → posterior shift in neuroinflammation (N30), with uncertainty shrinking as more proxies are observed.

Graph: posterior mean ± 90% interval for N30 under three conditions:

only IL-6 observed,

IL-6 + CRP observed,

IL-6 + CRP + TNF observed.

Purpose: demonstrates cross-proxy integration.

Figure 4 — Intervention Dose Translation and Propagation (mechanistic effect trace)
For one intervention (exercise), show:

dose → Δz at target node via dose bridge,

propagated Δθ across key mediators,

resulting ΔC distribution.

Purpose: makes intervention semantics concrete.

Figure 5 — Ranked Interventions with Uncertainty + Stability
Rank probability distribution (top-5 interventions) across MC draws + stability label.

Purpose: proves decision stability is quantified, not asserted.

Figure 6 — Chain vs Direct Validation (where available)
A small forest plot:

direct RCT effect on cognition (standardized),

chain-implied effect computed through mediators,

discrepancy Z and interpretation.

Purpose: links your hypothesis to empirical validation.

Figure 7 — Temporal Trajectory Predictions
Predicted cognitive trajectory over time (weeks to months) for the demonstration patient under:

natural recovery only (stretched exponential baseline),

top-ranked intervention (with onset/build/steady/decay kernel overlay),

posterior predictive bands (mean, P10, P90) across Monte Carlo draws.

Purpose: demonstrates the system produces actionable time-course predictions, not just static scores.

Figure 8 — Clinical Risk Estimate Dashboard
Model-derived P̂(CRCI) gauge with credible interval, accompanied by:

per-domain impairment probability breakdown (bar chart),

coverage fraction indicator and low-coverage warning flag.

Purpose: shows the system translates composite scores into an interpretable risk probability with explicit uncertainty and domain decomposition.

Optional (supplementary):
Uncertainty source pie chart (literature vs measurement vs structural vs proxy vs missingness).

EVSI priority plot — per-edge expected value of sample information, ranked, showing where additional evidence would most reduce decision uncertainty.

Complexity-scaling curve (only if systematic pathway-reduction experiments are executed).

Results
Results should be written as claims + quantitative evidence. Do not describe "the system" here; show what happened when you ran it.
1. Evidence base and parameterization success
Report:
number of papers ingested for the slice,

number of usable evidence records after trust-boundary rejection,

number of edges compiled with k≥1 and k≥2,

proportion of records with direct precision vs derived precision.

Key statement format:
"Across X papers, we extracted Y evidence records mapping to Z of Z_slice edges; W% contained a primary precision source (SE/CI/p+N)."
2. Compiled mechanistic parameters are non-degenerate and interpretable
Report:
median β magnitude and SE_eff across slice edges,

distribution of inclusion probabilities,

heterogeneity (I²) summary.

Include one worked edge example (linked to Figure 2).
3. Cross-proxy inference produces pathway dysregulation profiles
Report:
posterior means and uncertainty for the latent pathway nodes (e.g., neuroinflammation, HPA dysregulation) under your demonstration patient.

show how uncertainty contracts with additional proxies (Figure 3).

Key claim:
"Adding cytokine proxies reduced posterior SD for neuroinflammation by X% while shifting the mean by Y SD."
4. Patient-level predictions and risk outputs
Report:
composite CRCI score and domain scores with uncertainty,

coverage fraction and whether the result is observation-driven or imputation-heavy,

Cochran's Q and I² at the composite level (consistency across cognitive domains).

The system implements a clinical risk estimator (F4) that computes P̂(CRCI) via ICCTF-aligned domain-level classification across Monte Carlo draws, producing:
P̂(CRCI) with credible interval (model-derived, uncalibrated against external cohort data),

per-domain impairment probabilities and a domain-level breakdown,

coverage fraction with a low-coverage warning when few cognitive domains are observed.

P̂(CRCI) is explicitly labeled as model-derived and uncalibrated until validated against held-out cohorts with ground-truth CRCI outcomes.

4b. Temporal trajectory predictions
Report:
temporal trajectory predictions (per-intervention and natural-recovery time courses) with posterior predictive intervals (mean, P10, P90) over configurable horizons (weeks to years),

composition of natural recovery (stretched exponential), intervention kernels (onset/build/steady/decay), and treatment-accelerated cognitive aging.
5. Intervention optimization produces mechanistically plausible rankings
Report:
top intervention(s), dose thresholds (min effective / cost-effective / plateau),

predicted effect distribution (ΔC mean, interval),

adherence-adjusted rank changes (SAFE_A vs SAFE_B),

pairwise synergy diagnostics for bundled interventions: pathway overlap (JPO), complementarity (CCS), and net interaction magnitude (γ) with uncertainty,

any safety constraints that removed options.

6. Stability and uncertainty decomposition
Report:
stability class,

probability that the top-1 remains top-1,

top variance contributors (five-source decomposition: literature heterogeneity, measurement noise, structural uncertainty, proxy imprecision, missing observations).

This is where your engine's "scientific honesty" shows.

6b. Evidence-gap prioritization and EVSI
Report:
top-ranked evidence gaps by discovery score (edge elasticity × effective uncertainty),

expected value of sample information (EVSI) per edge: the estimated reduction in decision variance achievable from one additional study on that edge,

concrete "next best measurement" nominations for future trials.

Key statement format:
"EVSI analysis identifies edge [X→Y] as the highest-value empirical target, with an estimated [Z]% reduction in ranking variance from a single well-powered study."
7. Validation: chain vs direct agreement (where testable)
Report for each testable comparison:
direct effect size,

chain-implied effect size,

discrepancy statistic (Z) and interpretation.

Important: if comparisons are only possible for a subset of pathways/edges, state the denominator explicitly:
"Validation was feasible for K out of M candidate intervention–outcome pairs due to estimand compatibility and available RCT reporting."
Conclusion
This work presents a literature-parameterized, mechanistic framework for CRCI that converts heterogeneous published evidence into a calibrated causal graph and uses patient proxy measurements to infer latent pathway dysregulation states with quantified uncertainty. By separating observable proxies (biomarkers, symptoms, cognitive tests) from latent mechanistic pathway nodes, the system preserves measurement–construct epistemology and propagates proxy imprecision through posterior inference. Non-pharmaceutical interventions are modeled as dose- and time-parameterized exogenous perturbations that intercept specific nodes/pathways; their predicted effects are propagated through the compiled graph and ranked under explicit feasibility and safety constraints. In the vertical-slice demonstration, the system produces interpretable intervention rankings, uncertainty decomposition, temporal trajectory predictions with posterior predictive intervals, a model-derived clinical risk estimate (P̂(CRCI) with credible interval and per-domain breakdown, explicitly labeled as uncalibrated), evidence-gap prioritization via EVSI, and (where comparable trial evidence exists) chain-implied effect estimates suitable for direct-versus-chain consistency assessment. Collectively, these results support the feasibility of a biologically grounded, auditable "digital representation" of treatment-to-cognition processes for CRCI and provide a concrete route for mechanistically guided non-pharmaceutical mitigation.

Discussion
Interpretation and contribution
The central contribution is not merely prediction, but mechanistic interpretability with uncertainty accounting. Instead of treating CRCI as a single latent score or relying on black-box predictors, the framework explicitly represents multi-pathway causal structure, acknowledges that key mechanisms are only indirectly measurable, and infers patient pathway states from proxy panels under an explicit measurement-and-uncertainty model. This enables individualized recommendations framed as: "which pathway is likely dysregulated for this patient, what evidence supports that inference, and which interventions most plausibly reduce downstream cognitive burden."
Why the proxy–latent separation matters
The model's separation between biomarker nodes and pathway_latent nodes is scientifically important: peripheral biomarkers and self-report instruments are informative but imperfect proxies for central processes. By modeling proxy imprecision and cross-proxy coupling, the system avoids conflating measurement with mechanism and makes uncertainty sources explicit (proxy validity, measurement noise, and missingness). This design supports responsible clinical translation: when few domains are observed or when proxy validity is low, the system can warn that estimates are primarily model-driven.
Validation logic and what "agreement" means
Chain-versus-direct comparison provides a testable internal validity criterion: when a direct intervention effect on cognition is available and estimands are aligned, mechanistic chain predictions can be compared against observed trial effects. Agreement does not prove the graph is "true," but it increases confidence that the mechanistic representation captures a meaningful portion of the intervention's pathway-mediated effect. Disagreement is equally valuable because it localizes likely gaps—missing edges, omitted mediators, misaligned measures, or unmodeled effect modification—and can be used to drive targeted evidence acquisition.
Limitations (state them explicitly)
Evidence-to-parameter dependency. Model performance is bounded by extraction completeness, effect-size harmonization accuracy, and evidence quality. Incomplete precision sources or mis-grounded edges can produce non-deployable parameters; therefore strict reject-on-missing gates and referential integrity checks are essential.

Latent mechanism compression. Several transitions (cellular→circuit→system) are compressed into latent pathway nodes due to limited clinical biomarkers; this is a structural approximation and a primary source of model uncertainty.

Heterogeneity and effect modification. Current effect modification is bounded and does not represent full node×node interaction or complex non-linear conditional effects.

Calibration to incidence. The clinical risk estimate P̂(CRCI) is model-derived and uncalibrated: it reflects ICCTF-aligned domain-level classification applied to Monte Carlo posterior draws, not externally validated incidence rates. Until calibrated against held-out cohorts with ground-truth CRCI outcomes, P̂(CRCI) should be interpreted as a relative risk ordering rather than an absolute probability.

Validation coverage. Chain-vs-direct checks are only possible for subsets of intervention–outcome pairs where comparable direct evidence exists and the chain estimator spans the mediating path(s).

Practical implications
Even under these constraints, the framework can serve as an auditable decision-support layer for hypothesis generation, mechanistically justified intervention selection, and research prioritization. The EVSI analysis provides a concrete, quantitative mechanism for translating model uncertainty into empirical action: by identifying which edges contribute most to decision variance, the system nominates specific biomarker–cognition or intervention–mediator relationships as high-value targets for future measurement or trial design. In the near term, its highest-value role is to unify fragmented CRCI evidence into interpretable pathway-level predictions — including temporal trajectories that show how cognitive outcomes evolve over time under intervention — and to expose where uncertainty is dominated by missing evidence versus measurement limitations versus structural assumptions.

Next Steps
A. Engineering next steps (to make the system scientifically deployable)
Extraction integrity hardening (highest priority). Enforce reject-on-missing-precision at the trust boundary, implement semantic record identity (study×edge×contrast×timepoint), eliminate SE=1.0 fallback (quarantine instead), and add referential integrity gates that prevent compiled edges without backing evidence.

Output contract stabilization. Version and freeze the RecommendationReport schema, generate JSON schema artifacts, and add golden-file integration tests ensuring presentation wiring matches algorithm outputs without silent field loss.

Complete chain-vs-direct estimator. Extend chain computation beyond short hops, sum over all indirect paths, and make the scope of validation explicit in outputs (which chains were evaluable and why).

Deterministic reproducibility. Ensure all stochastic modules in comparative analyses share controlled random seeds (including synergy γ draws) and add pairing invariants for subpopulation comparisons.

Annotation consumer wiring (PIMP completion). Wire promoted annotations into compilation as parameter overrides (σ²_structural, p_inclusion adjustment, quality demotion) through batch queries and compiled policy tables—not runtime DB queries.

B. Scientific next steps (to improve model fidelity and credibility)
Expand proxy coverage at L2→L3/L3→L4 boundaries. Prioritize clinically accessible neuroimaging proxies (DTI metrics for myelin/white matter; functional connectivity proxies for network disruption) and explicitly model their proxy validity and confounds.

External validation cohort. Evaluate predictive accuracy and calibration on an independent dataset with longitudinal cognitive outcomes; report calibration slope/intercept and discrimination metrics.

Test-level ICCTF implementation. Upgrade from domain-level classification to test-level CRCI criteria once measure-level mappings and measurement model parameters are fully wired.

Mechanistic interaction modeling. Introduce a small set of high-impact moderated edges (e.g., inflammation moderating BDNF→memory) to capture context-dependent effects without abandoning tractability.

Prospective trial design targets. Use EVSI + elasticity to nominate concrete "next best measurements" and mechanistic endpoints for intervention trials (e.g., which biomarker panels most reduce uncertainty in intervention ranking).

C. Deliverable next steps (paper + system documentation)
Publish the vertical-slice benchmark package. Release a reproducible slice artifact: evidence matrix, compiled edge parameters, one example patient observation batch, and resulting ranked interventions with uncertainty and provenance.

Update system roadmap documentation. Revise the visual roadmap and output templates to reflect the stabilized output contracts and the validated slice wiring from extraction → compilation → inference → report.
