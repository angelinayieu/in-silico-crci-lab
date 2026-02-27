. Methods
2.0 Theoretical Framework: Biological-Cognitive Causation
2.0.1 Overview
This framework operationalizes a specific theory of how biological perturbations produce cognitive dysfunction. Before describing the computational machinery, we articulate the theoretical architecture that justifies and constrains the model. This architecture draws from four converging traditions: modular neuropsychology, network neuroscience, biological psychiatry and psychoneuroimmunology, and allostatic load theory.
2.0.2 The Multi-Level Causation Principle
Chemotherapy-induced cognitive impairment emerges through a cascade spanning seven levels of biological organization. The framework explicitly models this cascade rather than treating the chemotherapy→cognition relationship as a black box.
Level
Description
CRCI Examples
Measurement Access
L1: Molecular
Chemical/biochemical events
DNA adduct formation, ROS generation, cytokine transcription
Research assays only
L2: Cellular
Single-cell dysfunction
Neuronal apoptosis, microglial activation, oligodendrocyte damage
Peripheral proxies (γ-H2AX, p16INK4a)
L3: Circuit
Local network disruption
Hippocampal LTP impairment, prefrontal hypoactivation
fMRI, EEG (research)
L4: System
Distributed network dysfunction
Default mode desynchronization, frontoparietal decoupling
Functional connectivity (research)
L5: Cognitive
Information processing deficits
Encoding failures, retrieval interference, attentional lapses
Neuropsychological tests
L6: Behavioral
Observable performance decrements
Test scores, task completion, error rates
Clinical assessment
L7: Experiential
Subjective complaints and distress
“Foggy thinking,” frustration, reduced confidence
Self-report instruments


Each level is partially reducible to the level below, but emergent properties at each level require level-specific measurement and modeling. The DAG architecture respects this multi-level structure by including nodes at L2 (biomarkers), L3 (pathway activations, latent), L4 (symptom clusters), L5 (cognitive domains), and L7 (subjective complaints). Direct edges between non-adjacent levels are avoided unless supported by evidence of level-skipping mechanisms.
2.0.3 The Pathway-to-Cognition Mapping Hypothesis
The central theoretical claim is:
Mechanistic Mapping Hypothesis: Specific biological pathways affect cognition through identifiable mechanisms with predictable domain-specificity, time-course, and individual-difference moderation. These pathway-cognition relationships are sufficiently stable across individuals to support causal modeling and intervention targeting, while varying in magnitude according to measurable patient characteristics.
This hypothesis is intermediate between strong reductionism (cognition fully determined by biology — rejected because cognitive reserve, strategy, and context modulate biological effects) and dualism (cognition independent of biology — rejected because robust biological-cognitive correlations and intervention effects demonstrate causal linkage).
Biological pathways affect cognition through three distinct mechanisms with different implications for assessment, reversibility, and intervention:
Mechanism
Definition
Examples
Reversibility
Structural Damage
Loss or degradation of neural tissue
Senescent neuronal loss, white matter lesions, hippocampal atrophy
Low to Moderate (plasticity-dependent)
Functional Disruption
Altered signaling without structural loss
Synaptic dysfunction from neuroinflammation, neurotransmitter imbalance
Moderate to High (resolves with pathway normalization)
Compensatory Exhaustion
Increased cognitive effort for equivalent output
Fatigue-driven resource depletion, reserve exhaustion under multiple pathway burden
High (rest-dependent) but recurs with demand

Mechanism type assignment. Each of the 16 mechanistic  pathways (§2.3.1) is classified by its primary mechanism of cognitive impact, enabling mechanism-aware intervention targeting:
Pathway
Primary Mechanism
Rationale
M1: Neuroinflammation
Functional Disruption (acute); Structural Damage (chronic)
Acute microglial activation disrupts synaptic signaling; chronic activation causes neuronal loss
M2: Oxidative stress
Structural Damage
ROS-mediated lipid peroxidation and DNA damage cause irreversible cellular injury
M3: HPA dysregulation
Functional Disruption
Cortisol excess impairs hippocampal signaling without necessarily causing structural loss
M4: Neuroplasticity impairment
Functional Disruption
Reduced BDNF/TrkB signaling impairs LTP; reversible with pathway normalization
M5: Neurogenesis impairment
Structural Damage
Loss of hippocampal progenitor cells reduces neural tissue
M6: Mitochondrial dysfunction
Functional Disruption; Compensatory Exhaustion
ATP depletion impairs synaptic function; compensatory metabolic strain causes fatigue
M7: DNA damage
Structural Damage
Genomic instability in post-mitotic neurons is largely irreversible
M8: Gut-brain axis
Functional Disruption
Dysbiosis alters vagal and immune signaling; potentially reversible
M9: Cellular senescence
Structural Damage
Senescent cells accumulate; SASP drives chronic inflammation
M10: Glymphatic impairment
Functional Disruption
Impaired waste clearance is sleep-dependent and potentially reversible
M11: Cerebrovascular dysfunction
Structural Damage
White matter lesions and perfusion deficits cause permanent tissue loss
M12: Epigenetic changes
Functional Disruption
Methylation changes are potentially reversible with appropriate interventions
M13: Metabolic dysregulation
Functional Disruption
Brain insulin resistance impairs glucose utilization; modifiable
M14: BBB disruption
Functional Disruption; Structural Damage
Endothelial dysfunction permits neurotoxic infiltration
M15: Synaptic dysfunction
Functional Disruption
PSD-95 loss and spine retraction impair transmission; partially reversible
M16: Myelin/Oligodendrocyte dysfunction
Structural Damage; Functional Disruption
OPC depletion causes structural myelin loss (low reversibility); disrupted myelination signaling impairs conduction velocity (partially reversible with OPC regeneration)


Pathways classified as primarily Functional Disruption (M3, M4, M8, M10, M12, M13) are expected to show higher reversibility and stronger intervention response than those classified as Structural Damage (M2, M5, M7, M9, M11), informing both the temporal recovery model (§2.18.1, where r∞ should be higher for functional pathways) and intervention prioritization (targeting functional pathways yields faster, more complete recovery). Pathways with dual classification (M1, M6, M14, M15) have time-dependent mechanism transitions — acute intervention prevents the shift from reversible functional disruption to irreversible structural damage, providing a mechanistic rationale for early intervention. These classifications are recorded in Supplementary Table S1 as an additional column per pathway node.
2.0.4 The Subjective-Objective Dissociation
A robust finding in CRCI research is that subjective cognitive complaints correlate only modestly with objective neuropsychological test performance. Pullens et al. (2010) systematically reviewed 27 studies and concluded that subjective and objective cognitive dysfunction were largely unrelated, with subjective complaints instead associated with psychological distress, fatigue, and health status. Across the broader literature, the correlation between self-reported and objectively measured cognitive function generally ranges from r ≈ 0.20 to 0.30, explaining only 4–9% of shared variance (Gehring et al., 2015; Hutchinson et al., 2012). The framework models subjective cognition as influenced by four predictors with the following standardized path coefficients, estimated from the relative magnitudes of published associations in cancer populations: objective cognitive performance (β ≈ 0.22), fatigue (β ≈ 0.31), mood disturbance (β ≈ 0.27), and metacognitive accuracy (β ≈ 0.18), where coefficients are normalized to sum to approximately 1.0. The relative ordering — fatigue > mood > objective performance > metacognitive accuracy — is consistent with multivariate analyses showing that emotional and somatic factors dominate subjective cognitive complaints in cancer patients (Pullens et al., 2010; Hutchinson et al., 2012), though the specific coefficients are author-constructed estimates from the pattern of published correlations rather than values drawn from a single regression model. This has a direct clinical implication: interventions targeting fatigue and mood may improve subjective cognition even without changing objective performance — a valid and clinically meaningful outcome.
2.0.5 Seven Generalization Axioms
The CRCI framework instantiates general principles applicable to any condition involving biological-cognitive interactions:
Axiom 1 — Multi-Causality: Any cognitive outcome has multiple biological pathways capable of producing it, and any biological pathway can affect multiple cognitive outcomes. Models must be multivariate.
The necessity of multivariate modeling is highlighted by the risk of “partial adjustment”. Steiner & Kim (2016) demonstrated that adjusting for some confounders while omitting others can amplify bias rather than reduce it. Therefore we should avoid purely accounting for well-studied pathways (neuroinflammation) while omitting poorly-studied ones (gut-brain axis, mitochondrial dysfunction) to avoid producing worse pathway estimates because it creates a false condition that distorts estimates. The framework addresses this through structural inclusion probabilities (§2.10) and structural placeholder pathways for mechanisms with insufficient evidence, ensuring that acknowledged uncertainty is formally propagated to prevent hidden omitted variable bias from contaminating results. 
Axiom 2 — Convergence: Distinct upstream causes may converge on common intermediate nodes/pathways, producing similar downstream effects (towards outcome) despite different origins. This structure equifinality suggesazts that therapeutic interventions can be optimized by targeting these convergence points, thereby mitigating adverse downstream outcomes – including both the probability (CRCI risk) and the severity of clinical symptoms – regardless of the initiating upstream cause (e.g., chemotherapy, surgery, or systemic inflammation). 
Axiom 3 — Divergence: Single pathways may diverge to affect multiple cognitive outcomes through distinct downstream mechanisms. Pathway-targeted interventions upon a shared upstream driver may have broad cognitive benefits.
Axiom 4 — Temporal Dynamics: Effects have onset latency, peak timing, and decay characteristics that vary by mechanism and must be explicitly modeled. Time-to-effect and effect duration are as important as effect magnitude for clinical decision-making.
Axiom 5 — Individual Differences: The same biological state produces different cognitive outcomes across individuals based on reserve, genetics, context, and compensatory capacity. Personalization requires modeling effect modifiers, not just main effects.
Axiom 6 — Bidirectionality: Cognitive and behavioral states can influence biological pathways, creating feedback loops that may amplify (e.g. poor sleep causes deep depression and chronic inflammation) or attenuate (eg. CBT-I targets poor sleep to break bidirectional amplification of depression and sleep quality) initial perturbations . Stability requires that all loop gains remain below unity (1.0). 
Axiom 7 — Measurement Gap: Observable biomarkers are proxies for latent biological states; cognitive tests are proxies for latent cognitive capacity. The fidelity of these proxies varies substantially and must be quantified and propagated as uncertainty. Klein et al. (2011) reported R² = 0.44 (rats) and R² = 0.41 (pigs) for peripheral-to-central BDNF in healthy animals. However, these correlations likely attenuate under neuroinflammatory conditions: pro-inflammatory cytokines suppress central BDNF expression while peripheral BDNF sources (platelets, immune cells) are independently regulated, and Elfving et al. (2010) demonstrated an inverse correlation between hippocampal and blood BDNF in a genetic depression model — meaning peripheral BDNF can become actively misleading when central inflammation is present. No study has directly quantified the peripheral-central BDNF R² under inflammatory conditions; the framework conservatively estimates this at R² ≈ 0.10–0.15 (author estimate reflecting ~60–75% attenuation from baseline R² ≈ 0.40), and applies a 1.5× SE multiplier for the BDNF proxy when neuroinflammation is elevated (§2.17.1).
2.1 Directed Acyclic Graph Formulation
To represent the multi-variate relationships, a directed acyclic graph G = (V, E, Θ) is used, where V is a set of 63 canonical random variables (nodes), E is a set of 118 directed edges encoding conditional dependencies, and Θ is the full parameter set comprising edge weights β_ij, temporal kernels κ_ij(t), dose-response functions f_k(d), and effect modifier rules m_k. Each node is standardized to z-score units (μ = 0, σ = 1) via population-level reference distributions (general healthy population) to reflect an optimal wellness standard and to prevent normalization of deviancy, enabling commensurable effect sizes across heterogeneous measurement scales. The graph has edge density 0.030, with 55 connected nodes (87.3%) and 8 edgeless structural placeholders (12.7%) representing pathways with insufficient evidence for parameterization.
Property
Value
Canonical nodes
64
Directed edges
118
Connected / edgeless nodes
60 (93.8%) / 4 (6.3%)
Clinical domains
11
Hierarchical layers
7 (exogenous → composite)
Pathway latent variables
16
Observable / latent
48 (76.2%) / 15 (23.8%)
Evidence records
446 studies
Model registries
10 CSV files

2.1.1 Complete Node Registry
The 63 canonical nodes are exhaustively enumerated below, organized by hierarchical layer. Each node is specified with its variable identifier, clinical domain assignment, observability status, orientation convention, primary measurement instrument (where applicable), parameterization status, and biological organization level (mapping to the seven-level cascade in §2.0.2). This registry is the authoritative reference; Supplementary Table S1 provides additional fields (population means, prior specifications, loading factors).
Layer 0 — Exogenous Inputs (n = 9)
ID
Node
Domain
Observable
Orientation
Instrument / Source
Bio Level
Status
N01
chemo_regimen
Treatment
Yes
Categorical
Medical record
L1: Molecular
Connected
N02
radiation_therapy
Treatment
Yes
Higher = more dose
Medical record (Gy)
L1: Molecular
Connected
N03
endocrine_therapy
Treatment
Yes
Categorical
Medical record
L1: Molecular
Connected
N04
age
Demographic
Yes
Higher = older
Self-report / record
—
Connected
N05
sex
Demographic
Yes
Binary (0=F, 1=M)
Self-report / record
—
Connected
N06
education_years
Demographic
Yes
Higher = more
Self-report
—
Connected
N07
apoe_genotype
Demographic
Yes
Categorical (ε4±)
Genotyping assay
L1: Molecular
Connected
N08
cancer_type
Treatment
Yes
Categorical
Medical record
—
Connected
N09
treatment_phase
Treatment
Yes
Ordinal (active→surv.)
Medical record
—
Connected

Layer 1 — Modifiable Behaviors (n = 8)
ID
Node
Domain
Observable
Orientation
Instrument / Source
Bio Level
Status
N10
physical_activity
Lifestyle
Yes
Higher = more active
Actigraphy / IPAQ (MET-min/wk)
L6: Behavioral
Connected
N11
sleep_quality
Sleep/Circadian
Yes
Higher = worse
PSQI global score
L6: Behavioral
Connected
N12
sleep_duration
Sleep/Circadian
Yes
Hours/night
Actigraphy / self-report
L6: Behavioral
Connected
N13
dietary_pattern
Lifestyle
Yes
Higher = better adherence
Mediterranean Diet Score
L6: Behavioral
Connected
N14
social_engagement
Lifestyle
Yes
Higher = more
Composite (LSNS-6)
L7: Experiential
Connected
N15
stress_management
Lifestyle
Yes
Higher = more practice
Practice hours/wk (MBSR)
L6: Behavioral
Connected
N16
cognitive_engagement
Lifestyle
Yes
Higher = more
Training hours/wk
L6: Behavioral
Connected
N17
light_exposure
Lifestyle
Yes
Higher = more
Lux·hours/day
L6: Behavioral
Connected

Layer 2 — Biological Mediators (n = 12)
ID
Node
Domain
Observable
Orientation
Instrument / Source
Bio Level
Status
N18
il6
Inflammatory
Yes
Higher = worse
Plasma ELISA (pg/mL)
L1: Molecular
Connected
N19
crp
Inflammatory
Yes
Higher = worse
hs-CRP assay (mg/L)
L1: Molecular
Connected
N20
tnf_alpha
Inflammatory
Yes
Higher = worse
Plasma ELISA (pg/mL)
L1: Molecular
Connected
N21
bdnf_plasma
Neuroprotective
Yes
Higher = better
Plasma ELISA (ng/mL); NOT serum
L1: Molecular
Connected
N22
cortisol_slope
Neuroendocrine
Yes
Flatter = worse
Salivary diurnal slope (≥2 days)
L1: Molecular
Connected
N23
dhea_s
Neuroendocrine
Yes
Lower = worse
Serum assay (μg/dL)
L1: Molecular
Connected
N24
mda
Inflammatory
Yes
Higher = worse
Plasma TBARS (nmol/mL)
L1: Molecular
Connected
N25
ohd_8ohdg
Inflammatory
Yes
Higher = worse
Urinary 8-OHdG (ng/mg Cr)
L1: Molecular
Connected
N26
p16ink4a
Metabolic
Yes
Higher = worse
T-lymphocyte qRT-PCR
L2: Cellular
Connected
N27
fasting_glucose
Metabolic
Yes
Higher = worse
Serum assay (mg/dL)
L1: Molecular
Connected
N28
nfl
Neuroprotective
Yes
Higher = worse
Serum Simoa (pg/mL)
L1: Molecular
Connected
N29
shannon_diversity
Metabolic
Yes
Lower = worse
16S rRNA sequencing
L2: Cellular
Connected




Layer 3 — Mechanistic Pathways (n = 16; all latent)
ID
Node
Domain
Proxy Indicators (Layer 2)
Bio Level
Tier
Status
N30
neuroinflammation
Inflammatory
N18 (IL-6), N19 (CRP), N20 (TNF-α)
L2–L3: Cellular→Circuit
Model-implied
Connected
N31
oxidative_stress
Inflammatory
N24 (MDA), N25 (8-OHdG)
L1–L2: Molecular→Cellular
Model-implied
Connected
N32
hpa_dysregulation
Neuroendocrine
N22 (cortisol slope), N23 (DHEA-S)
L1–L3: Molecular→Circuit
Model-implied
Connected
N33
neuroplasticity_impairment
Neuroprotective
N21 (BDNF plasma)
L2–L3: Cellular→Circuit
Model-implied
Connected
N34
neurogenesis_impairment
Neuroprotective
None (no validated human biomarker)
L2: Cellular
Model-implied
Connected
N35
mitochondrial_dysfunction
Metabolic
None (Seahorse XF research only)
L2: Cellular
Model-implied
Connected
N36
dna_damage
Metabolic
None (γ-H2AX research only)
L1–L2: Molecular→Cellular
Model-implied
Connected
N37
gut_brain_disruption
Metabolic
N29 (Shannon diversity)
L2: Cellular
Emerging
Connected
N38
cellular_senescence
Metabolic
N26 (p16INK4a)
L2: Cellular
Emerging
Connected
N39
glymphatic_impairment
Sleep/Circadian
N11 (sleep quality; indirect)
L3–L4: Circuit→System
Emerging
Connected
N40
cerebrovascular_dysfunction
Neuroprotective
None (DTI/FDG-PET research only)
L3–L4: Circuit→System
Emerging
Edgeless†
N41
epigenetic_changes
Metabolic
None (methylation arrays research)
L1: Molecular
Emerging
Connected
N42
metabolic_dysregulation
Metabolic
N27 (fasting glucose)
L1–L2: Molecular→Cellular
Emerging
Connected
N43
bbb_disruption
Neuroprotective
N28 (NfL; CNS/PNS confound)
L2–L3: Cellular→Circuit
Placeholder
Edgeless†
N44
synaptic_dysfunction
Neuroprotective
None (no peripheral biomarker; convergent hub)
L3: Circuit
Model-implied
Connected
N65
myelin_dysfunction
Neuroprotective
Fractional anisotropy (DTI, research); NfL (shared with BBB — confound)
L2–L3: Cellular→Circuit
Model-implied
Connected
N66
dopaminergic_dysfunction
Neuroprotective
None (SPECT/PET research only)
L2–L3: Cellular→Circuit
Emerging
Connected


†Edgeless nodes have k = 0 direct evidence records and receive StructuralPlaceholder priors (§2.10). They are retained in the DAG to (a) acknowledge known biology, (b) enable mechanistic synthesis priors when chain evidence becomes available, and (c) prevent the partial adjustment paradox (§2.0.5, Axiom 1).
Composite node clarification. Three composite latent nodes — OIC (Oxidative-Inflammatory Cascade, encoding N30 + N31 + N35), NIC (Neuroendocrine-Immune Coupling, encoding N32 + N30), and CAL (Cognitive-Affective Loop, encoding subjective cognition + N46/N47) — are defined in §2.4.2. These do not add new nodes to the DAG; they replace the internal independence assumption among their constituent nodes with a multivariate covariance structure while preserving the same node identifiers and external edge connections. The composite nodes formalize feedback dynamics that the acyclic DAG cannot represent as directed cycles: within each composite, bidirectional coupling is encoded as off-diagonal entries in a 2×2 or 3×3 covariance matrix, while between composites the condensed DAG remains acyclic and amenable to standard belief propagation. The total node count (64) refers to individual nodes; the 3 composites are structural annotations grouping subsets of these nodes, not additional entities.

Layer 4 — Symptom Clusters (n = 8)
ID
Node
Domain
Observable
Orientation
Instrument / Source
Bio Level
Status
N45
fatigue
Psychological
Yes
Higher = worse
FACIT-Fatigue / BFI
L7: Experiential
Connected
N46
depression
Psychological
Yes
Higher = worse
PHQ-9 (PHQ-2 during tx)
L7: Experiential
Connected
N47
anxiety
Psychological
Yes
Higher = worse
GAD-7
L7: Experiential
Connected
N48
pain
Psychological
Yes
Higher = worse
BPI / NRS
L7: Experiential
Connected
N49
sleep_disturbance
Sleep/Circadian
Yes
Higher = worse
ISI
L7: Experiential
Connected
N50
appetite_changes
Psychological
Yes
Higher = worse
Single-item / ESAS
L7: Experiential
Edgeless†
N51
weight_changes
Metabolic
Yes


Δ
= worse
BMI / self-report
N52
self_efficacy
Psychological
Yes
Higher = better
GSE / cancer-specific
L7: Experiential
Connected

Layer 5 — Cognitive Domains (n = 10)
ID
Node
Domain
Observable
Orientation
Instrument / Source
Bio Level
Status
N53
attention_sustained
Cognitive
Yes
Higher = better
CPT-II, d’
L5: Cognitive
Connected
N54
attention_selective
Cognitive
Yes
Higher = better
Stroop interference
L5: Cognitive
Connected
N55
attention_shifting
Cognitive
Yes
Higher = better
TMT-B (time, reversed)
L5: Cognitive
Connected
N56
memory_working
Cognitive
Yes
Higher = better
Digit Span Backward
L5: Cognitive
Connected
N57
memory_episodic
Cognitive
Yes
Higher = better
HVLT-R Total Recall
L5: Cognitive
Connected
N58
executive_inhibition
Cognitive
Yes
Higher = better
Stroop Color-Word
L5: Cognitive
Connected
N59
executive_flexibility
Cognitive
Yes
Higher = better
WCST / TMT-B:A ratio
L5: Cognitive
Connected
N60
processing_speed
Cognitive
Yes
Higher = better
DSST / TMT-A
L5: Cognitive
Connected
N61
verbal_fluency
Cognitive
Yes
Higher = better
COWAT (FAS + Animals)
L5: Cognitive
Connected
N62
memory_consolidation
Cognitive
Yes
Higher = better
HVLT-R Delayed Recall
L5: Cognitive
Connected


Layer 6 — Composite Outcome (n = 1)
ID
Node
Domain
Observable
Orientation
Derivation
Status
N63
crci_composite
Composite
Derived
Higher = better
IVW aggregate of N53–N62 (§2.20)
Connected


Registry verification. Total nodes: 9 + 8 + 12 + 16 + 8 + 10 + 1 = 64 .  Observable: 48 (75.0%) — all Layer 0–2, all Layer 4–6. Latent: 16 (25.0%) — all Layer 3. Connected: 60 (93.8%). Edgeless: 4 (6.3%) — N40 (cerebrovascular), N43 (BBB), N50 (appetite), N51 (weight). Cross-level coverage spans all seven biological organization levels defined in §2.0.2, with strongest representation at L1 (Molecular: 14 nodes), L7 (Experiential: 8 nodes), and L5 (Cognitive: 10 nodes); weakest at L3 (Circuit) and L4 (System), which are accessible only through research imaging modalities and are modeled as latent pathway nodes.

2.1.2 Pathway-Edge Architecture
The 118 directed edges are organized into five functional classes, mapping to the pathway architecture defined in §2.3. Each edge class serves a distinct inferential role:
Edge Class
Count
Definition
Example
Treatment → Mediator
22
Chemotherapy exposure activates biological pathway
N01 (chemo) → N18 (IL-6)
Mediator → Pathway
18
Observable biomarker loads onto latent pathway
N18 (IL-6) → N30 (neuroinflammation)
Pathway → Symptom/Cognition
31
Mechanistic pathway produces downstream effects
N30 (neuroinflammation) → N60 (processing speed)
Intervention → Mediator/Pathway
24
Behavioral intervention modifies biological state
N10 (exercise) → N18 (IL-6)
Cross-layer lateral
23
Within-layer or feedback connections
N45 (fatigue) ↔ N10 (physical activity)

Pathway-edge decomposition. Each of the 21 pathways (16 mechanistic  + 5 clinical mediator) engages a specific subset of edges. The table below maps each pathway to its constituent edge chain(s), the biological levels traversed, and the number of edges contributing:
#
Pathway
Edge Chain (representative)
Levels Traversed
k Edges
Evidence Grade
M1
Neuroinflammation
N01→N18→N30→{N53,N57,N60}
L1→L1→L2/L3→L5
11
A (causal demo)
M2
Oxidative stress
N01→N24→N31→{N53,N60}
L1→L1→L1/L2→L5
7
B
M3
HPA dysregulation
N01→N22→N32→{N57,N53}
L1→L1→L1/L3→L5
8
B
M4
Neuroplasticity
N01→N21→N33→{N57,N56}
L1→L1→L2/L3→L5
9
B (cancer-null BDNF)
M5
Neurogenesis
N01→N34; N30→N34; N33→N34; N34→N57
L1→L2→L5
5
B (preclinical strong)
M6
Mitochondrial
N01→N35→N45→{N56,N60}
L1→L2→L7→L5
6
B
M7
DNA damage
N01→N36; N31→N36; N36→N38→N45
L1→L1/L2→L2→L7
5
B (human neuropath.)
M8
Gut-brain axis
N01→N29→N37→N30
L1→L2→L2→L2/L3
5
C
M9
Cellular senescence
N01→N26→N38→N45
L1→L2→L2→L7
5
B (causal demo, animal)
M10
Glymphatic
N11→N39→N30→{N57,N60}
L6→L3/L4→L2/L3→L5
6
C
M11
Cerebrovascular
N01→N40→{N53,N60}
L1→L3/L4→L5
3
C (edgeless)
M12
Epigenetic
N01→N41; N31→N41; N41→N33
L1→L1→L2/L3
4
C (growilng preclinical)
M13
Metabolic
N01→N27→N42→{N56,N60}
L1→L1→L1/L2→L5
5
C
M14
BBB disruption
N01→N28→N43→N30
L1→L1→L2/L3→L2/L3
4
D (edgeless)
M15
Synaptic (convergent hub)
{N30,N31,N33,N32,N01}→N44→{N56,N57,N60}
L1–L3→L3→L5
8
B (convergent)
M16
Myelin/Oligodendrocyte
N01→N65→{N53,N55,N60}
L1→L2/L3→L5
5
B
M17
Dopaminergic
N01→N66→{N58,N59,N60}
L1→L2/L3→L5
4
C
C1
Sleep disruption
N11→N49→{N39,N32,N33}→cognition
L6→L7→L3→L5
8
A (RCT mediation)
C2
Fatigue
N45→N10→{N30,N33}→cognition
L7→L6→L2/L3→L5
7
A
C3
Mood/affect
N46/N47→{N33,N53–N62}
L7→L2/L3→L5
6
B
C4
Vascular/metabolic
N27→N42→{N56,N60}
L1→L1/L2→L5
4
B
C5
Social isolation
N14→N52→cognition
L7→L7→L5
3
C


Edge total verification: Σ pathway edges = 120 (minor overcounting due to shared edges between pathways, e.g., N30→N60 serves both M1 and M8). Net unique edges after deduplication: 118. Shared edges between pathways are precisely the convergence nodes described in Axiom 2 (§2.0.5), and their shared variance is handled by the block-diagonal D matrix (§2.17.2).
no
Cross-level coverage matrix. The following table verifies that the DAG provides edge coverage across all transitions between adjacent biological levels:
Transition
Example Edge
k Edges
Gap?
L1 (Molecular) → L2 (Cellular)
N18 (IL-6) → N30 (neuroinflammation)
18
No
L2 (Cellular) → L3 (Circuit)
N33 (neuroplasticity) → circuit effects (latent)
8
Partial — circuit-level effects are latent within pathway nodes
L3 (Circuit) → L4 (System)
N39 (glymphatic) → system-level effects
4
Partial — L3/L4 boundary is modeled within single pathway nodes
L4 (System) → L5 (Cognitive)
Pathway → cognitive domain edges
31
No
L5 (Cognitive) → L6 (Behavioral)
N53–N62 → N63 (composite)
10
No
L6 (Behavioral) → L7 (Experiential)
N10 (activity) → N45 (fatigue)
5
No
L7 (Experiential) → L6 (feedback)
N45 (fatigue) → N10 (activity)
5
No

Identified coverage gaps. The L2→L3 and L3→L4 transitions (cellular→circuit→system) are the weakest links in the cascade. These transitions occur within the 15 latent pathway nodes rather than being explicitly modeled as separate edges, because the intervening steps (e.g., microglial activation → synaptic stripping → network disruption → system-level desynchronization) are not independently measurable with current clinical biomarkers. This compression of multiple biological steps into a single latent node is the primary source of structural model uncertainty (σ² = 0.01, §2.9) and represents the most important target for expansion as neuroimaging biomarkers (functional connectivity, DTI) become clinically accessible.
Collider bias acknowledgment. A DAG with ~128 edges among 65 nodes creates the potential for collider bias: conditioning on intermediate variables that serve simultaneously as mediators on some paths and colliders on others can open previously blocked backdoor paths. The v1.1 framework does not algorithmically compute minimally sufficient adjustment sets for each intervention query (e.g., via the dagitty algorithm of Textor et al., 2016). Instead, the cut-model architecture and Mode A associational shift provide a conservative approach: by not conditioning on intermediate pathway nodes during intervention simulation (effects propagate forward through the full graph), collider bias from intermediate conditioning is avoided. However, this comes at the cost of not being able to make strictly causal claims (§2.14). Algorithmic identification of valid adjustment sets for each intervention-outcome pair is a v2.0 priority.


FIGURE 2. 
INTERACTIVE LINK FOR A SELECTABLE FOCUS VIEWS: https://angelinayieu.github.io/CRCI-in-silico/  
Complete 63-Node DAG. Hierarchical layout with L0 (top) → L6 (bottom). Node color = clinical domain (11 colors), shape = observable (circle) vs latent (diamond), border = connected (solid) vs edgeless (dashed). Edge thickness = |β|, color = claim level (green/yellow/gray), style = P_inclusion (solid >0.85, dashed <0.85). 20 pathway groupings overlaid as colored regions. Can create now — use §2.1.1 node registry and §2.1.2 edge architecture as data source.

Cognitive domain intercorrelation pairs, sourced from neuropsychological normative data:
Pair
ρ
Source
Block
Processing speed (N60) ↔ Sustained attention (N53)
0.60
Neuropsychological normative data
Cognitive
Episodic memory (N57) ↔ Executive function (N58)
0.40
Neuropsychological normative data
Cognitive
Sustained attention (N53) ↔ Processing speed (N60)
0.55
Neuropsychological normative data
Cognitive
Working memory (N56) ↔ Executive flexibility (N59)
0.45
Neuropsychological normative data
Cognitive


2.2 Seven-Layer Node Hierarchy
Nodes are organized into seven layers reflecting causal role in the biological cascade from treatment exposure to cognitive outcome:
Layer 0 — Exogenous inputs (n = 9): Treatment exposures (chemotherapy regimen, radiation, endocrine therapy), demographic factors (age, sex, education), and intervention assignments. These nodes have no parents in the DAG; their values are observed or specified.
Layer 1 — Modifiable behaviors (n = 8): Sleep quality and duration, physical activity level, dietary patterns, social engagement, stress management practices. These represent the primary intervention targets.
Layer 2 — Biological mediators (n = 12): Measurable biomarkers and hormones including inflammatory markers (IL-6, CRP, TNF-α), neurotrophic factors (BDNF), stress hormones (cortisol slope, DHEA-S), oxidative stress markers (MDA, 8-OHdG), senescence markers (p16INK4a), and metabolic indicators (fasting glucose).
Layer 3 — Mechanistic pathways (n = 16): Latent neuropathological processes — neuroinflammation, oxidative stress, HPA dysregulation, neuroplasticity impairment, neurogenesis impairment, mitochondrial dysfunction, DNA damage, gut-brain axis disruption, cellular senescence, glymphatic impairment, cerebrovascular dysfunction, epigenetic changes, metabolic dysregulation, BBB disruption, and synaptic dysfunction. These are partially observed through Layer 2 proxies.
Layer 4 — Symptom cluster (n = 8): Affective and somatic manifestations including fatigue, depression, anxiety, pain, sleep disturbance severity, and appetite/weight changes.
Layer 5 — Cognitive domains (n = 10): Neurocognitive performance across attention (sustained, selective, shifting), memory (working, episodic encoding, consolidation, retrieval), executive function (inhibition, flexibility, planning), processing speed (perceptual, motor, decision), and verbal fluency.
Layer 6 — Composite outcome (n = 1): Integrated CRCI severity score aggregating domain-specific performance via inverse-variance weighting with severity-dependent domain weights.
Orthogonally, each node belongs to one of 11 clinical domains: treatment exposure, demographic, lifestyle, inflammatory, neuroendocrine, metabolic, neuroprotective, sleep/circadian, psychological, cognitive, and composite. The full node classification with domain assignments, measurement instruments, and orientation conventions is provided in Supplementary Table S1.
Table. Node domain distribution.
Domain
Count
Measurable
Description
pathway_latent
9 (3 composite + 6 standard)
No
Latent mechanistic constructs representing biological processes not directly measurable in clinical settings. Includes 3 composite nodes (OIC, NIC, CAL) encoding feedback dynamics. Distinct from biomarkers: a pathway represents the biological process; a biomarker is an imperfect peripheral measurement of that process (see proxy fidelity, §2.0.5).
biomarker
11
Yes
Serum, salivary, and urinary assays serving as proxies for latent pathway states. Each biomarker–pathway link carries an explicit proxy fidelity estimate (R² range) acknowledging measurement imperfection.
cognitive
10
Yes
Neuropsychological test outcomes (objective) and patient-reported cognitive function (subjective).
treatment
7
Yes
Chemotherapy agents and regimen parameters extracted from medical records.
genetic
4
Yes (genotyping)
Genetic polymorphisms functioning as time-invariant effect modifiers: APOE ε4 carrier status, COMT Val158Met, BDNF Val66Met, and a composite pharmacogenomic risk score (MDR1/GST variants affecting drug metabolism and CNS exposure). These are not causal parents in the DAG but modify edge coefficients through the effect modifier system (§2.7).
behavior
4
Yes
Self-report and actigraphy-derived behavioral measures (exercise, sleep, diet, substance use).
symptom
4
Yes
Patient-reported outcome measures (fatigue, pain, nausea, subjective cognitive complaints).
psychological
4
Yes
Coping, resilience, anxiety, and depression measures.
intervention
3
Yes
Intervention implementation parameters (type, dose, duration, adherence).
demographic
2
Yes
Age and BMI. Hormonal status (menopausal state, endocrine therapy) reclassified to treatment domain.
physical
1
Yes
Cardiorespiratory fitness (VO₂max or proxy).


Note on domain separation. The pathway_latent and biomarker domains are deliberately kept separate despite their close relationship. This separation encodes a fundamental epistemological distinction: pathway nodes represent theoretical biological processes (e.g., “the degree of neuroinflammation in the central nervous system”), while biomarker nodes represent measurable peripheral quantities (e.g., “plasma IL-6 concentration”). The relationship between them is a measurement model with quantified imprecision — Klein et al. (2011) reported R² = 0.41–0.44 for peripheral-to-central BDNF in healthy animals, but this correlation likely attenuates substantially under neuroinflammatory conditions (§2.0.5, Axiom 7). Merging the two domains would conflate the thing measured with the measurement, obscuring a source of uncertainty that the framework explicitly propagates.
Rationale for the genetic domain. The addition of a genetic/genomic domain reflects the growing literature on polymorphism-based effect modification in CRCI. APOE ε4 carrier status modifies exercise → cognition relationships (Smith et al., 2013) and endocrine therapy → cognitive decline trajectories (Buskbjerg et al., 2019). COMT Val158Met affects dopaminergic function and has been associated with differential CRCI vulnerability (Small et al., 2011). BDNF Val66Met influences activity-dependent BDNF secretion and may moderate the neuroplasticity pathway’s responsiveness to intervention (Egan et al., 2003). MDR1 and GST polymorphisms affect drug metabolism and thereby CNS chemotherapy exposure, providing a mechanistic basis for inter-individual variation in neurotoxicity (Ahles & Saykin, 2007). These genetic variables function as time-invariant modifiers of edge coefficients rather than as causal parents or children in the DAG, and are implemented through the effect modifier system (§2.7) rather than as standard DAG edges.

2.3 Two-Tier Pathway Architecture
The model encodes 21 causal pathways in two tiers reflecting evidence maturity and mechanistic directness.
2.3.1 Tier 1: Mechanistic Pathways (n = 16)
Model-implied pathways (n = 7) have strong preclinical foundations with emerging or established human validation:
1. Neuroinflammation — The single best-supported CRCI mechanism. Chemotherapy agents generate peripheral cytokines (IL-6, TNF-α, IL-1β) that cross the blood-brain barrier via receptor-mediated transport, activating microglia and triggering NF-κB cascades. Cheung et al. (2015) demonstrated that higher plasma IL-1β predicted slower response speed in 99 breast cancer patients. Kesler et al. (2013) found reduced hippocampal volume associated with elevated IL-6 and TNF-α. The CANTO-Cog study established that baseline IL-6 before treatment predicted CRCI at 2 years, indicating cancer itself drives neuroinflammation independent of chemotherapy. Critically, Acharya et al. (2016) demonstrated causality for the neuroinflammation pathway: microglial depletion via PLX5622 completely reversed radiation-induced cognitive deficits in mice. The same group subsequently showed that PLX5622 also reversed doxorubicin-induced cognitive deficits (Allen et al., 2019), extending the causal evidence from cranial irradiation to systemic chemotherapy — the most direct causal demonstration that microglial activation mediates chemotherapy-induced cognitive impairment.
The exercise-neuroinflammation relationship involves a paradoxical mechanism with important implications for dose-response modeling. Acute exercise transiently elevates IL-6 (up to 100-fold during prolonged activity; Pedersen & Febbraio, 2008), but this muscle-derived IL-6 acts as a myokine rather than a classical inflammatory cytokine, triggering downstream anti-inflammatory cascades (IL-1ra, IL-10) that produce net anti-inflammatory effects over chronic training. Meta-analytic evidence confirms this net benefit: Khosravi et al. (2019) found exercise training in cancer survivors reduced circulating inflammatory cytokines (pooled SMD = −0.20, 95% CI: −0.38 to −0.01), and Meneses-Echávez et al. (2016) reported exercise-induced IL-6 reduction in breast cancer survivors (WMD = −0.55 pg/mL, 95% CI: −0.89 to −0.22). The 2025 Supportive Care in Cancer meta-analysis identified a threshold of approximately 2,000 MET-min/week above which anti-inflammatory benefits plateau, informing the dose-response ceiling in §2.6. The myokine paradox means that the exercise → neuroinflammation edge in the DAG represents the net chronic effect (anti-inflammatory) rather than the acute transient response (pro-inflammatory), with the pathway operating through peripheral-to-CNS mechanisms: muscle-derived anti-inflammatory myokines reduce systemic inflammation, decreasing BBB permeability to pro-inflammatory cytokines and reducing microglial activation.
2. Oxidative stress — Forms a bidirectional feed-forward loop with neuroinflammation: reactive oxygen species activate NF-κB → cytokine release, while TNF-α generates further ROS. Torre et al. (2021) provided the first human neuropathological evidence via autopsy, demonstrating elevated nitrotyrosine, 4-hydroxynonenal, and γ-H2AX in frontal cortex neurons of chemotherapy-treated patients. Zhao et al. (2025, Blood 146(Suppl 1):3619, ASH abstract) reported that malondialdehyde (MDA) levels were associated with focused attention decline (measured by TMT-A — a measure of psychomotor speed and simple attention rather than complex executive function) in Hodgkin lymphoma patients receiving chemotherapy. Over 50% of FDA-approved anticancer drugs generate ROS through established mechanisms.
3. HPA dysregulation — A systematic review of 17 studies found 16 showing altered HPA function in cancer patients versus controls. Flatter diurnal cortisol slopes associate with poorer health outcomes (Adam et al., 2017 meta-analysis: r = 0.147 across 80 studies). Toh et al. (2022) showed pre-chemotherapy DHEA-S levels predicted CRCI, providing the strongest cancer-specific evidence for the cortisol-to-cognition link.
4. Neuroplasticity impairment — Doxorubicin reduces BDNF/TrkB expression and impairs long-term potentiation; cisplatin reduces BDNF mRNA at concentrations as low as 0.1 μM. Ng et al. (2023) found cancer patients had significantly lower baseline BDNF (10.7 vs. 21.6 ng/mL, P < 0.001), with lower BDNF predicting worse attention, memory, and self-perceived cognition. The peripheral-to-central BDNF correlation is moderate: animal studies in healthy, unstressed specimens report R² ≈ 0.40–0.44 (Klein et al., 2011: r² = 0.44 in rats, r² = 0.41 in pigs), though no large human validation study exists, and these correlations were established under non-inflammatory conditions that may not hold in cancer populations with active neuroinflammation.
 This correlation may further decouple under neuroinflammatory conditions — a critical caveat for proxy validity that is reflected in the SE multiplier (1.0× baseline, 1.3× if neuroinflammation is elevated).
The exercise → BDNF mechanism is well-characterized in general populations. Wrann et al. (2013) demonstrated the molecular cascade: exercise induces PGC-1α in muscle → activates FNDC5/irisin → crosses BBB → upregulates hippocampal BDNF expression. El Hayek et al. (2019) further showed that lactate mediates exercise effects on learning and memory through SIRT1-dependent activation of hippocampal BDNF. General-population meta-analyses confirm robust effects: Szuhany, Bugatti & Otto (2015) reported acute exercise Hedges’ g = 0.46 (k = 29) for blood BDNF increase, and Dinoff et al. (2017) found chronic aerobic exercise SMD = 0.59 for resting BDNF (k = 14) and SMD = 0.66 for post-exercise BDNF. However, cancer-specific BDNF evidence represents a critical gap. Two well-powered cancer-specific RCTs found null exercise-BDNF effects: Irwin et al. (2021, N = 144 ovarian cancer survivors, 6-month home-based exercise) and Hartman et al. (2019, N = 87 breast cancer survivors, 12-week technology-based intervention). Notably, Hartman’s exercise group showed improved processing speed despite no BDNF change — a dissociation suggesting either alternative mediating pathways (myokines, vascular effects, neuroinflammation reduction) or that chemotherapy-damaged BDNF signaling does not respond to exercise stimulation as in healthy populations. This gap between robust general-population effects and null cancer-specific results is the most critical per-pathway uncertainty in the model. The v1.1 specification addresses this through wider priors for the exercise → BDNF edge in cancer populations (§2.10), but the fundamental question — whether exercise improves cancer-survivor cognition through BDNF at all — remains open and constitutes the highest-priority evidence gap for the neuroplasticity pathway.
5. Neurogenesis impairment — The most robustly replicated preclinical finding. Christie et al. (2012) showed 80–90% reduction in hippocampal neurogenesis after doxorubicin or cyclophosphamide in rats. Sekeres et al. (2021) catalogued ≥14 independent rodent studies confirming neurogenesis suppression across BCNU, methotrexate, 5-FU, cyclophosphamide, doxorubicin, temozolomide, and cisplatin. No validated human biomarker exists for in vivo neurogenesis measurement.
6. Mitochondrial dysfunction — Cisplatin inhibits electron transport chain complexes I–IV, causing substantial reductions in ATP production in cancer cells (Chiu et al., 2017, Cancer Research 77(3):742–752). Boukelmoune et al. (2018) demonstrated that mesenchymal stem cell-to-neural stem cell mitochondrial transfer protects against cisplatin neurotoxicity in vitro — providing evidence that mitochondrial function in neural progenitor cells is a critical vulnerability in chemotherapy-induced cognitive impairment. Alexander et al. (2021) showed that nasal administration of exogenous mitochondria reversed cisplatin-induced cognitive deficits in vivo, providing direct causal evidence linking mitochondrial dysfunction to chemotherapy-induced cognitive impairment. Park et al. (2018) demonstrated that exercise prevents doxorubicin-induced cognitive impairment via enhancement of hippocampal mitochondrial function in mice — a preclinical link between the exercise intervention and this specific pathway. PBMC ATP production via Seahorse XF Analyzer correlates with cancer-related fatigue (Feng et al., 2020).
7. DNA damage — Carroll et al. (2019) demonstrated that higher leukocyte DNA damage was associated with worse executive function (β = −0.23, P < 0.05) and lower telomerase activity predicted worse attention and motor speed in breast cancer survivors 3–6 years post-treatment.
Emerging-evidence pathways (n = 6) have accumulating support requiring further validation:
8. Gut-brain axis disruption — The Intelligut study (Pyter et al., 2024) demonstrated chemotherapy-induced microbiome disruption directly related to objective cognitive decline in 77 breast cancer patients, independent of systemic inflammation, with unique taxonomic shifts (decreased Faecalibacterium, altered Bacteroides) in cognitively impaired patients. The critical mediators are metabolite-level rather than community-level: butyrate produced by Faecalibacterium and Roseburia spp. directly modulates microglial activation and HDAC activity, while tryptophan metabolites feed into the kynurenine pathway linking gut dysbiosis to neuroinflammation. Shannon diversity alone cannot distinguish metabolically distinct communities, and v2.0 should incorporate taxa-specific or metabolite-level proxies.

9. Cellular senescence — Sanoff et al. (2014) showed chemotherapy increased T-lymphocyte p16INK4a expression (a senescence biomarker, mechanistically distinct from epigenetic aging clocks) by an amount comparable to 10–15 years of chronological aging; anthracycline-based regimens accelerated senescence biomarker expression by 23–26 years versus approximately 9–11 years for TC regimens (Shachar et al., 2020), though the TC acceleration did not reach statistical significance (P ≤ 0.15). Demaria et al. (2017) demonstrated genetic elimination of senescent cells restored voluntary running activity — from ~10% to ~40% of waking time — in chemotherapy-treated mice, demonstrating causality for the senescence → functional impairment pathway. Other chemotherapy side effects (bone marrow suppression, cardiac dysfunction) were also reduced, though less completely.

10. Glymphatic impairment — The most novel pathway with evidence emerging 2022–2025. Zhou et al. (2025, Human Brain Mapping 46(13):e70334) provided the first longitudinal MRI evidence showing chemotherapy-induced choroid plexus enlargement precedes perivascular space volume reduction, correlating with gray matter atrophy and cognitive decline during neoadjuvant chemotherapy. The cross-lagged panel analysis demonstrated a temporal sequence: choroid plexus volume change → perivascular space alteration → gray matter atrophy → FACT-Cog decline — providing the first in vivo human evidence for a chemo-glymphatic impairment cascade. This builds on the foundational finding of Xie et al. (2013) that sleep increases interstitial space volume by ~60%, enabling convective clearance of metabolic waste including amyloid-β — mechanistically linking glymphatic function to sleep quality (the primary measurable proxy for this pathway) and explaining why sleep disruption may compound chemotherapy-induced neurotoxicity through impaired waste clearance.
11. Cerebrovascular dysfunction — DTI studies show decreased fractional anisotropy in frontal/temporal white matter tracts correlating with impaired attention and processing speed (Deprez et al., 2011). FDG-PET reveals decreased cerebral glucose metabolism persisting 5–10 years post-treatment (Silverman et al., 2007).
12. Epigenetic changes — Doxorubicin + cyclophosphamide alters DNA methylation patterns and HDAC activity in rat prefrontal cortex (Chakrabarti et al., 2025, Scientific Reports 15:20681). Yao et al. (2019) found 4.2% of CpG sites changed post-chemotherapy in breast cancer patients, with one site (VMP1/MIR21) associated with cognitive decline.
13. Metabolic dysregulation — FDG-PET studies consistently demonstrate decreased cerebral glucose metabolism in frontal, temporal, and cerebellar regions post-chemotherapy across breast cancer, lymphoma, lung cancer, and leukemia. The brain insulin resistance model (de la Monte, 2012) provides the mechanistic bridge.
Structural placeholder pathways (n = 2) have preclinical support awaiting human validation:
14. Blood-brain barrier disruption — Ungvari/Csiszar group (2025) demonstrated persistent BBB disruption 2 months post-cisplatin treatment via two-photon microscopy, mediated by endothelial senescence. Schroyen et al. (2021) reported elevated neurofilament light chain (NfL) in chemotherapy-treated breast cancer patients (n = 19); published chemotherapy-NfL studies generally report 2- to 10-fold elevations depending on drug class and neuropathy severity [NOTE: the magnitude reported in the original Schroyen et al. small-sample study should be verified against larger cohorts]. NfL cannot distinguish CNS from peripheral nervous system damage — a critical limitation when taxane/platinum-induced peripheral neuropathy is common.
15. Synaptic dysfunction (convergent hub) — The evidence overwhelmingly establishes synaptic dysfunction as a downstream convergent hub rather than an independent parallel pathway. It receives inputs from multiple upstream mechanisms: neuroinflammation drives CR3-mediated complement synaptic pruning by microglia (Gibson & Monje, 2021), oxidative stress causes mitochondrial calcium dysregulation at synapses, BDNF depletion removes trophic maintenance of dendritic spines, HPA dysregulation impairs long-term potentiation through glucocorticoid-mediated mechanisms, and direct chemotherapy damage includes taxane-mediated microtubule disruption and cisplatin-induced rapid spine loss at concentrations achievable in the CNS (Andres et al., 2014). Doxorubicin reduces PSD-95 expression and causes dendritic spine loss.
The convergent hub architecture has a critical clinical implication: upstream-targeted interventions (anti-inflammatory, neurotrophic, cortisol-normalizing) improve synaptic integrity without directly targeting synapses, because synaptic dysfunction is a downstream consequence rather than an independent initiating mechanism. Treating synaptic dysfunction as a parallel pathway double-counts its contribution to CRCI and obscures that the most effective intervention strategy addresses the upstream drivers converging on this node.
Additionally, cisplatin induces hippocampal tau clustering in wild-type mice (Chiang et al., 2019, Brain, Behavior, and Immunity), and HDAC6 inhibition reverses both tau pathology and associated cognitive deficits (Cherrier et al., 2018, Acta Neuropathologica Communications), linking chemotherapy-induced tauopathy to the synaptic dysfunction convergent hub. This tau pathology mechanism is subsumed under N44 and does not require a separate node.
Inbound edges: OIC composite (neuroinflammation/oxidative stress/mitochondrial dysfunction) → N44, neuroplasticity/BDNF pathway (N33) → N44, treatment nodes (direct chemotherapy neurotoxicity) → N44, HPA dysregulation (N32) → N44. Outbound edges: → working memory (N56), → episodic memory (N57), → processing speed (N60). Evidence grade: B (strong preclinical with multiple independent demonstrations of each inbound mechanism; no human synaptic protein measurements in CRCI patients; no validated peripheral biomarker). No direct human studies have measured synaptic proteins in CRCI patients.
16. Myelin/Oligodendrocyte dysfunction — Gibson et al. (2019, Cell) demonstrated that methotrexate causes persistent oligodendrocyte precursor cell (OPC) depletion, disrupted differentiation, and reduced myelin thickness in a mouse model, with human postmortem validation showing analogous oligodendroglial lineage disruption in methotrexate-treated patients. Critically, this study identified a tri-glial mechanism: methotrexate activates microglia, which induce neurotoxic astrocyte polarization (A1 phenotype), which in turn fails to support — and actively impairs — oligodendrocyte maturation and survival. Geraghty et al. (2019, Neuron) showed that methotrexate blocks activity-regulated myelination through disruption of BDNF-TrkB signaling in oligodendrocyte precursors, providing a molecular link between the neuroplasticity pathway (M4) and myelination. This is arguably the most important CRCI mechanism discovery of the past decade, establishing that chemotherapy-induced white matter damage — the most consistently documented neuroimaging finding in CRCI, typically measured as reduced fractional anisotropy on DTI (Deprez et al., 2011) — is primarily myelin-driven rather than vascular in origin.
Inbound edges: chemotherapy → OPC depletion (direct cytotoxicity), neuroinflammation (OIC) → neurotoxic astrocyte activation → oligodendrocyte failure (the tri-glial cascade from Gibson et al., 2019), BDNF/neuroplasticity → myelination support (Geraghty et al., 2019). Outbound edges: → processing speed (strongest — myelination directly determines axonal conduction velocity), → attention, → executive function. Evidence grade: B (strong preclinical + human postmortem + DTI correlation; no interventional human data). Proxy indicator: fractional anisotropy from DTI (research only), or NfL (shared with BBB disruption — note the confound, §2.17.1).
17. Dopaminergic dysfunction — COMT Val158Met is modeled as a genetic modifier (§2.2). Vitor et al. (2019, Annals of Nuclear Medicine) showed dopamine transporter reduction in breast cancer survivors via SPECT imaging, providing direct human neuroimaging evidence of chemotherapy-induced dopaminergic dysfunction. Kaplan et al. (2016, ACS Chemical Neuroscience) demonstrated that carboplatin impairs dopamine release using in vivo voltammetry. Dopaminergic dysfunction directly underlies the frontal executive deficits and processing speed reductions prominent in CRCI — the two cognitive domains most consistently impaired — via prefrontal dopamine-dependent attentional control and striatal-dependent processing efficiency. Edge structure: chemotherapy → dopamine transporter/release impairment → executive function + processing speed. Evidence grade: C (human neuroimaging + preclinical voltammetry; limited intervention data).
2.3.2 Tier 2: Clinical Mediator Pathways (n = 5)
1. Sleep disruption — The strongest mediation evidence in CRCI, including a landmark RCT showing CBT-I improved perceived cognitive impairment with change fully mediated by insomnia improvement (Garland et al., 2024). Sleep disturbances affect 30–60% of cancer patients and provide the primary measurable proxy for glymphatic function. Boyd et al. (2025, Sleep 48(7):zsaf073) demonstrated that methotrexate causes enduring disruption of NREM sleep architecture in a mouse model, independent of tumor presence — providing preclinical evidence that chemotherapy directly damages sleep regulatory circuits rather than merely causing sleep disruption through symptom burden. Human validation of this direct neurotoxic mechanism remains a priority gap. The sleep-cognition relationship in CRCI operates through multiple mechanisms: Giese et al. (2014) demonstrated a biphasic relationship between sleep disturbance and BDNF — both insomnia and hypersomnia are associated with reduced BDNF, suggesting a U-shaped dose-response where moderate, well-structured sleep optimizes neurotrophic signaling. Tell, Mathews & Janusek (2014) demonstrated that disrupted sleep architecture predicted flattened diurnal cortisol slopes in breast cancer patients, linking sleep disruption to HPA dysregulation and providing a concrete mechanism through which sleep interventions may improve cognition via cortisol normalization.
2. Cancer-related fatigue — Co-occurs with CRCI at rates of approximately 75% during chemotherapy, sharing inflammatory (IL-6, TNF-α), HPA, and mitochondrial mechanisms. A shared inflammation polygenic risk score predicted both CRF and CRCI (Janelsins et al., 2025), providing genetic evidence for mechanistic overlap.
3. Mood/affect — Depression affects approximately 27% and anxiety approximately 30% of cancer patients globally. Inflammatory cytokines mediate 24–26% of the distress-cognition relationship in breast cancer survivors.
4. Vascular/metabolic risk — In the TLC study (Mandelblatt et al., 2014), cardiovascular disease and diabetes showed OR = 8.77 (95% CI: 2.06–37.4) for pretreatment cognitive impairment in cancer patients while showing no association in controls, demonstrating cancer-specific vulnerability to vascular risk.
5. Social isolation — Grounded in cognitive reserve theory. A cross-national study (N = 101,581) demonstrated social isolation accelerates cognitive aging.
2.3.3 Pathway-Domain Specificity
Not all pathways affect all cognitive domains equally. The pathway-domain specificity matrix (Supplementary Table S-Cognitive Architecture) encodes these differential effects as edge weights, with stronger weights for high-specificity relationships. For example, neuroinflammation shows strongest effects on processing speed and memory (via hippocampal microglial pruning), while HPA dysregulation preferentially affects memory and attention (via hippocampal glucocorticoid receptors and arousal system modulation). This specificity matrix is a core component of personalization: a patient with elevated neuroinflammation benefits most from anti-inflammatory pathways affecting processing speed, while a patient with HPA dysregulation benefits most from cortisol-normalizing interventions affecting memory.
2.3.3 Pathway Evidence Confidence Tiers
The following table maps each pathway to an evidence confidence tier with corresponding SE multiplier and basis. These tiers synthesize the evidence grade from §2.1.2 with the detailed pathway descriptions above, providing a unified reference for the uncertainty architecture.
Pathway
Evidence Tier
SE Mult.
Basis
Neuroinflammation (M1)
High
1.0×
Causal demo (animal), human biomarker, multiple RCTs
Oxidative stress (M2)
Moderate-High
1.15×
Human autopsy, animal causal; limited human intervention
HPA dysregulation (M3)
Moderate
1.25×
Associational in cancer; mechanistic extrapolation
Neuroplasticity/BDNF (M4)
Moderate-High*
1.15× (*1.5× cancer-specific)
Animal strong; cancer-specific BDNF null
Neurogenesis (M5)
Moderate
1.25×
Strong animal; not measurable in humans
Mitochondrial (M6)
Moderate
1.25×
Animal causal; peripheral proxy only
DNA damage (M7)
Moderate-High
1.15×
Human autopsy confirmation
Gut-brain axis (M8)
Low-Moderate
1.75×
Emerging; single cancer-specific study
Cellular senescence (M9)
Moderate
1.25×
Animal causal; human biomarker
Glymphatic (M10)
Low-Moderate
1.75×
Emerging; 4–5 studies; largest N=126
Cerebrovascular (M11)
Moderate
1.25×
DTI + FDG-PET human; no intervention data
Epigenetic (M12)
Low-Moderate
1.75×
Growing preclinical; minimal human brain data
Metabolic (M13)
Moderate
1.25×
FDG-PET human; insulin resistance model
BBB disruption (M14)
Low-Moderate
1.75×
Preclinical; NfL confound
Synaptic (M15, convergent)
Moderate
1.25×
Strong preclinical; convergent hub architecture
Myelin/oligo (M16, NEW)
Moderate-High
1.15×
Cell paper; human postmortem; DTI correlation
Dopaminergic (M17, NEW)
Low-Moderate
1.75×
Human SPECT; preclinical voltammetry


Notebook delegation: Detailed pathway-domain specificity derivation, pathway interaction dynamics, and cognitive architecture modeling → NB00 (Setup).
 
Microscopic Pathway Vertical Slice: Exercise → Cognition. Two parallel chains (Chain A: anti-inflammatory via IL-6/TNF-α → neuroinflammation → processing speed; Chain B: neurotrophic via AMPK → BDNF → neuroplasticity → memory) traced across all 7 biological levels. Each transition annotated with β, SE, k, evidence grade. AMPK cascade shown as sub-edge molecular inset within Chain B. L2→L3 coverage gap highlighted with dashed region. Right panel: temporal kernel shape. Bottom panel: chain product computation with Z-score comparison to direct RCT evidence. Cancer-null BDNF divergence flagged. Can create now — β values from §2.3.1 text. See 03_pathway_visualizations.md for full spec.





FIGURE 4 . Macroscopic Pathway Interaction Map. 21 pathways as network nodes (size = edge count, color = evidence grade). Three gravitational clusters: inflammatory hub (M1–M2–M8–M9), neurotrophic hub (M4–M5–M6), regulatory hub (M3–C1–C2–M10). Edges = shared mediators (solid), convergent cognitive targets (double), feedback loops (bidirectional). Convergence zone at bottom showing cognitive domain targeting density (processing speed: 16/21 pathways). Edgeless pathways as faded/dashed nodes. Inset: block-diagonal D correlation heatmap + top synergy CCS scores. Can create now — pathway descriptions in §2.3 provide all connection data.
2.4 Modular Bayesian Inference (Cut-Model Architecture)
The inference engine implements modular Bayesian inference (Liu, Bayarri & Berger, 2009; Plummer, 2015), factorizing the generative model into two independent modules connected by a one-directional information flow constraint — the “cut.”
Stage 1 (Literature Module — Build-Time): Edge parameters β are estimated from systematic meta-analysis of published studies. Each edge posterior is:
pe∣literaturee=Ne,within2+e2
where μ_e is the inverse-variance-weighted pooled estimate and τ²_e is the REML-estimated between-study heterogeneity variance (with DerSimonian–Laird as sensitivity analysis). These parameters are fixed at build time and never updated by individual patient data.
Stage 2 (Patient Module — Runtime): Patient states θ are inferred conditional on the fixed edge estimates:
p∣y,py∣p∣
where p(θ | β̂) is the graph-informed prior derived from the SEM precision matrix Λ = (I−B)ᵀD⁻¹(I−B), and p(y | θ) is the measurement likelihood from observed instruments.
The Cut Constraint: Edge parameters inform the patient state prior through off-diagonal entries in Λ_prior, but patient observations never update edge beliefs. The full posterior factorizes as:
p,∣y,lit=p∣y,eEpe∣lite
This prevents feedback contamination where noisy individual data could corrupt population-level estimates. The architecture also provides a clean separation of concerns: the literature module can be updated (by incorporating new studies) independently of the patient inference module, and the patient module can process new observations without re-running meta-analysis. Implementation caveat: Plummer (2015) warns that naive cut implementations in BUGS/JAGS may not converge to a well-defined distribution because the cut posterior is not a true Bayesian posterior. The v1.1 framework avoids this issue by implementing Stage 1 and Stage 2 as separate computational steps rather than as a single MCMC sampler with cut feedback — β values are point-estimated (posterior mean ± SE) from meta-analysis and passed as fixed constants to the Stage 2 sampler, eliminating the within-sampler cut that causes convergence pathology. This “hard cut” implementation sacrifices the ability to propagate full β posterior uncertainty into θ estimation (only mean and variance are transmitted, not the full distribution shape), a limitation addressed in §2.21 (Assumption 5).
Clarification on “feedback-informed” terminology. The five feedback loops identified in §2.11 update latent state variables θ over time (e.g., fatigue ↔ physical activity), propagating through the fixed precision matrix Λ during patient state estimation. This is permitted under the cut constraint because θ is a Stage 2 (runtime) quantity. Edge weights β remain fixed below the cut and are never updated by individual patient data in v1.1. The term “feedback-informed” in this framework refers exclusively to temporal θ dynamics, not to β learning. Active β learning from patient trajectories — enabling the model to detect that a specific patient responds more strongly to exercise than the population average — is a v2.0 feature requiring hierarchical random slopes (§2.21, Assumption 1).
2.4.1 Scale Justification and Parameter Identifiability
The DAG comprises 64 nodes and 103 directed edges — substantially larger than typical clinical Bayesian networks, which commonly employ 6–20 nodes. This scale requires explicit justification.
Reason behind DAG size: The empirical case for simultaneous multi-pathway modeling in CRCI is unambiguous. Henneghan et al. (2018) demonstrated that single-cytokine linear models found zero significant associations with cognitive function in 66 breast cancer survivors, while 13-cytokine random forest models on the same data achieved adjusted R² = 0.71–0.77 — the difference between concluding inflammation is unrelated to CRCI and explaining three-quarters of cognitive variance. Oh & Oh (2019) found that individual pathway squared betas summed to approximately 24% of CRCI variance, while their simultaneous SEM explained 47.7% — indicating that nearly half the explained variance arises from indirect and synergistic effects invisible to single-pathway analysis. These findings, predicted by formal results in causal mediation theory (VanderWeele & Vansteelandt, 2014; Fritz, Kenny & MacKinnon, 2016; Coenen, 2022), establish multi-pathway estimation as a methodological requirement rather than a design preference. The question is not whether the model needs this many nodes, but whether 59 is sufficient to avoid the omitted variable bias that demonstrably distorts simpler CRCI models.
Identifiability regime. A critical distinction separates this framework from data-driven Bayesian network learning. In standard BN parameter estimation, all edge weights are learned simultaneously from a single dataset, creating a classical identifiability requirement of approximately 5–10 observations per free parameter (Koller & Friedman, 2009). With ~103 edge coefficients, ~59 residual variances, and Hill equation parameters for nonlinear edges, such an approach would require 1,500–5,000 observations — far exceeding typical CRCI cohorts of 100–500 participants.
This framework operates in a fundamentally different regime. Edge coefficients are not estimated from patient data; they are derived individually from published meta-analyses, each with its own sample size, study design, and uncertainty estimate. The model is a literature-synthesized simulation with informative priors, analogous to infectious disease transmission models (e.g., Bilcke et al., 2011; Kim et al., 2007) and pharmacokinetic models that routinely parameterize 50–200+ parameters from heterogeneous published sources without requiring a single dataset of equivalent size. In the Bayesian framework, informative priors derived from meta-analytic evidence formally resolve non-identifiability by constraining the parameter space to regions consistent with the published literature (Semochkina et al., 2025; Neath & Samaniego, 1997). Each edge coefficient β ± SE extracted from a meta-analysis functions as a Gaussian informative prior N(β, SE²), and the model's joint posterior is determined by the product of these priors and any individual-patient likelihood updates.
The identifiability concern therefore shifts from total sample size to per-edge evidence quality. Some edges rest on large meta-analyses (e.g., exercise → BDNF: k = 29 studies, N > 1,100; Szuhany et al., 2015), while others rest on single studies with modest samples. The framework addresses this heterogeneity through three mechanisms: (1) GRADE-informed SE inflation (§2.6), which widens uncertainty for lower-quality evidence; (2) structural uncertainty penalties (§2.9), which add variance for edges with thin evidence; and (3) explicit flagging of edges where evidence derives from fewer than 3 independent studies or N < 200 total participants.
When patient-level identifiability matters. The framework does perform patient-specific Bayesian updating via Kalman-style information-form updates (§2.3). In this mode, only the observed nodes contribute likelihood information; unobserved latent pathway nodes are updated solely through propagated effects from observed measurements. Identifiability in this mode is constrained by the observation pattern — which nodes have measurements — rather than by the total number of model parameters. The minimum viable observation set for meaningful patient-specific updating is: at least one biomarker per mechanistic pathway of interest (to anchor the latent state), plus the cognitive outcome measures. With 11 measurable biomarker nodes and 10 cognitive outcome nodes, a clinical assessment providing 5–10 measurements enables informative updating of the most clinically relevant model components while appropriately preserving prior uncertainty for unobserved pathways.
Limitations of scale. Model scale carries three genuine costs that must be acknowledged. First, uncertainty compounds across layers: a 5-layer path from treatment to cognition multiplies the SEs of each constituent edge, and with 3–5 edges per path, the cumulative credible interval at the outcome layer is substantially wider than for any individual edge. This is a feature, not a bug — it honestly represents the state of knowledge — but it does limit the precision of long-chain predictions. Second, structural sensitivity increases with scale: with 103 specified edges out of 1,711 possible directed connections among 64 nodes, the model asserts 1,608 conditional independence relationships, each untested. Missing a single confounding edge can bias all downstream estimates. The framework partially addresses this through chain-versus-direct validation (§2.5) and node suppression analysis, but cannot fully protect against unknown confounders. Third, computational cost scales with node count: Monte Carlo propagation with N = 10,000 samples across 64 nodess remains tractable (< 2 seconds on standard hardware), but Bayesian model averaging over DAG structures — the principled approach to structural uncertainty — is computationally prohibitive at this scale and is deferred to future work.
2.4.2 Handling Biological Feedback Loops Within an Acyclic Framework
The DAG formalism requires acyclicity: directed cycles are forbidden, and the joint distribution factorizes as a product of conditional distributions ordered by the DAG topology. This is both the source of the model's computational tractability and its most biologically unjustified constraint.
Biological cycles the DAG severs. At least five well-documented feedback loops relevant to CRCI cannot be represented as directed edges in a static DAG:
Neuroinflammation ↔ oxidative stress ↔ mitochondrial dysfunction. This is the most tightly coupled triad. Reactive oxygen species activate NF-κB, driving pro-inflammatory cytokine production; cytokines damage mitochondrial electron transport chains, increasing ROS generation; and mitochondrial dysfunction produces further oxidative stress — a self-amplifying cascade documented extensively in both neurodegeneration (Guo et al., 2013) and chemotherapy neurotoxicity (Gibson & Monje, 2021). Treating these as three independent parallel pathways, as the current DAG does, underestimates the amplification dynamics that make this triad disproportionately damaging.
HPA axis dysregulation ↔ neuroinflammation. Chronic cortisol elevation suppresses anti-inflammatory pathways while glucocorticoid resistance in immune cells permits sustained cytokine production (McEwen, 2008). Conversely, pro-inflammatory cytokines activate the HPA axis. In the allostatic overload model, this bidirectional coupling creates a stable maladaptive state that resists single-target intervention.
Cognitive impairment ↔ psychological distress. Perceived cognitive decline increases anxiety and depression, which further impair attention and executive function (Pullens et al., 2010; Hutchinson et al., 2012). The paper's subjective-objective dissociation model (§2.0.4) implicitly acknowledges this loop through the mood → subjective cognition edge, but the reverse path (subjective cognitive complaints → mood deterioration) is absent from the DAG.
Sleep disruption ↔ neuroinflammation. Sleep deprivation elevates IL-6 and TNF-α; elevated cytokines fragment sleep architecture (Irwin, 2019). Both are prevalent in cancer survivors and mutually reinforcing.
Oxidative stress → DNA damage → cellular senescence → SASP → neuroinflammation → oxidative stress. This is a slower-timescale amplification loop operating over weeks to months, relevant to the chronic/persistent phase of CRCI.
Resolution via composite latent nodes. Rather than adopting dynamic Bayesian networks (which require time-series data per patient — rare in CRCI, where most studies are cross-sectional) or abandoning the DAG formalism (which would sacrifice the computational tractability of belief propagation), the framework implements the condensed graph approach of Wiecek et al. (2019). Tightly coupled cycles are collapsed into multivariate composite nodes that preserve the internal covariance structure while maintaining acyclicity in the condensed DAG.
Specifically, three composite nodes replace the current independent pathway structure:
Composite Node
Component Pathways
Internal Structure
Oxidative-inflammatory cascade (OIC)
Neuroinflammation, Oxidative stress, Mitochondrial dysfunction
3×3 covariance matrix; amplification factor α estimated from paired cytokine-ROS studies
Neuroendocrine-immune coupling (NIC)
HPA axis dysregulation, Neuroinflammation (shared)
2×2 covariance matrix; bidirectional β from cortisol-cytokine studies
Cognitive-affective loop (CAL)
Subjective cognition, Mood/psychological distress
2×2 covariance matrix; bidirectional β from longitudinal CRCI cohorts

Within each composite node, the covariance matrix encodes the bidirectional coupling strength. Between composite nodes, the condensed DAG remains acyclic and amenable to standard belief propagation. This approach has three advantages: (1) it captures the amplification dynamics within tightly coupled subsystems, (2) it maintains the computational tractability of directed graphical models, and (3) it makes the cycle-handling explicit and auditable rather than hidden.
What is lost. The composite node approach approximates feedback dynamics as instantaneous equilibrium covariance rather than as time-evolving oscillatory or divergent behavior. This is appropriate for the chronic/stable phase of CRCI (months to years post-treatment), where the amplification loops have largely reached steady state. It is less appropriate for the acute phase (during and immediately after chemotherapy), where the inflammatory cascade is actively amplifying and has not equilibrated. The temporal kernels (§2.2) partially compensate by modeling onset, peak, and decay dynamics for intervention effects, but cannot capture the dynamic instability of the acute phase. Future extensions using time-sliced DBN representations (Dagum, 1992; Murphy, 2002) are planned for acute-phase modeling, contingent on the availability of longitudinal CRCI biomarker datasets with sufficient temporal resolution (≥ monthly sampling over 12+ months).
Remaining acyclic pathways. The five remaining mechanistic pathways — neuroplasticity impairment, neurogenesis impairment, glymphatic impairment, cerebrovascular dysfunction, and epigenetic changes — operate primarily as feedforward cascades from treatment to cognition, without strong evidence for bidirectional coupling at the pathway level. These retain standard single-node representation in the DAG. The slower-timescale senescence loop (oxidative stress → DNA damage → senescence → SASP → inflammation) is modeled as a unidirectional chain with time-lagged temporal kernels rather than as a cycle, on the grounds that the cycle time (weeks to months) substantially exceeds the model's intervention simulation timescale, and the self-amplification is adequately captured by the OIC composite node's amplification factor.
Parameterized feedforward pathways. The remaining mechanistic pathways — neuroplasticity impairment, neurogenesis impairment, glymphatic impairment, cerebrovascular dysfunction, and epigenetic modification — operate primarily as feedforward cascades from treatment to cognition without the strong bidirectional coupling that characterizes the three composite nodes above. However, unlike earlier iterations of this framework, none are modeled as edgeless. A node with zero parameterized edges asserts, via the Markov property, conditional independence from all other variables — a claim that is empirically untenable for any mechanism with published evidence linking it to treatment or cognition. Three nodes previously carried zero edges (neurogenesis, DNA damage, epigenetic changes) despite substantial published evidence for their connections. This has been corrected as follows.
Neurogenesis impairment receives inbound edges from chemotherapy exposure (multiple agents reduce hippocampal neural progenitor cell viability by 55–70% at clinically relevant concentrations), neuroinflammation (microglial activation suppresses progenitor cell proliferation and differentiation), and BDNF levels (promotes progenitor survival and integration). The outbound edge to hippocampal-dependent cognition is supported by extensive preclinical evidence linking reduced neurogenesis to impaired spatial memory and pattern separation. Evidence grade: Moderate-to-High (>15 independent preclinical studies, mechanistic certainty, consistent effect direction; limited to animal models for the neurogenesis → cognition link since hippocampal neurogenesis is not directly measurable in living humans).
DNA damage receives inbound edges from chemotherapy exposure (platinum-DNA adduct formation is the therapeutic mechanism of action for cisplatin, oxaliplatin, and carboplatin, with confirmed neuronal DNA damage in human autopsy tissue) and oxidative stress (ROS-induced 8-oxodG accumulation in frontal cortex neurons). The outbound edge connects through neuronal atrophy (platinum-induced transcriptional arrest causes cell body shrinkage) and feeds into the senescence-SASP chain captured by the OIC amplification factor. Evidence grade: High for treatment → DNA damage (human neuropathological confirmation); Moderate for DNA damage → cognitive outcomes.
Epigenetic modification receives inbound edges from chemotherapy exposure (AC chemotherapy alters DNA methylation patterns and histone deacetylase activity in prefrontal cortex) and oxidative stress (ROS disrupts methylation-maintaining enzymes). The outbound edge to cognition operates through altered expression of neuroplasticity and neurogenesis-regulating genes, including BDNF. This pathway is particularly relevant to persistent CRCI: epigenetic marks are self-perpetuating and may explain why cognitive impairment persists months to years after the initial neurotoxic insult has resolved. Evidence grade: Moderate (strong and growing preclinical evidence from multiple independent laboratories; limited human brain tissue data; direct epigenetic-to-cognitive-domain mapping remains correlational).
All three nodes carry GRADE-informed SE inflation (§2.6) reflecting their evidence quality, with structural uncertainty penalties (§2.9) applied to edges supported by fewer than three independent studies. Per-edge evidence sources and quality ratings are provided in Supplementary Table S1.

2.5 Evidence Extraction System
The evidence extraction system transforms published literature into parameterized model inputs through a six-phase pipeline with strict provenance tracking. The system architecture implements a trust boundary separating LLM-assisted content labeling from deterministic numeric parsing, ensuring that no floating-point value enters the Bayesian model without passing through a deterministic parser with validated output.
2.5.1 Design Principles
Seven principles govern the extraction system: (1) no record enters the model without explicit typing, gating, and provenance; (2) paper type determines what a record is allowed to update — a cross-sectional study cannot update a causal edge parameter regardless of sample size; (3) uncertainty is always propagated, never discarded — when uncertainty information is missing, the record is flagged PARTIAL, never silently completed; (4) LLMs label, deterministic parsers extract — the trust boundary between LLM-generated spans and numeric values that enter the model is absolute; (5) the system generates its own acquisition priorities via evidence gap analysis; (6) precision caps prevent low-quality mass from overwhelming high-quality signal; (7) raw extraction and curated evidence are stored separately with independent audit trails.
2.5.2 Pre-Extraction Triage (Phase 0)
Every paper is classified along five orthogonal axes before extraction: design class (16 study designs from RCT to qualitative), estimand type (12 types: ATE, ATT, CACE, per-protocol, adjusted/unadjusted association, mediation, dose-response, hazard, diagnostic, temporal trajectory), population match (8 levels with SE inflation from 1.0× for exact match to 3.3× for in vitro), outcome alignment (8 levels with SE inflation from 1.0× for same instrument to 1.8× for surrogate biomarker), and completeness (9 levels from full effect + CI + adjustment set to qualitative only).
An expected information gain (EIG) score routes papers to extraction depth:
EIGpaper=etarget_edgesHe∣current−He∣current+expectedPextractable
Papers with EIG < 0.01 are aborted; 0.01–0.10 receive shallow extraction (3 agents); 0.10–0.50 receive standard extraction (all 9 agents); >0.50 receive deep extraction with extended table processing.
2.5.3 Structured Extraction (Phase 1)
A nine-agent pipeline processes each paper sequentially: MetadataAgent (DOI, authors, funding), DesignAgent (study design, blinding, randomization), CohortAgent (sample size, demographics, eligibility), OutcomeAgent (instruments, timepoints, domains), StatsLabelAgent (statistical values as labeled spans with character offsets — never parsed numbers), MechanismAgent (causal language, pathway assignments), BiasQualityAgent (risk of bias across 6 dimensions, identification status), CombinationAgent (multi-arm designs, synergy data), and ReconciliationAgent (7 rule-based consistency checks across all agents, operating with no LLM).
2.5.4 Trust Boundary
The trust boundary is the architectural wall between LLM-generated content and numeric data entering the Bayesian model. Agents produce SpanLabel objects (character offsets, categorical labels, confidence scores) but never output parsed floating-point numbers. Eleven specialized deterministic parsers (NumericParser) extract numbers from labeled text spans: N_parser, p_parser, CI_parser, effect_parser, corr_parser, beta_parser, ratio_parser, test_parser, mean_sd_parser, range_parser, and percent_parser. Ambiguous parses (confidence < 0.80, SE/SD indistinguishable, multiple interpretations) are flagged AMBIGUOUS, never guessed.
The trust boundary architecture is validated by emerging evidence on AI-assisted extraction accuracy. The RAISE framework (2025), developed jointly by Cochrane, Campbell, JBI, and the Collaboration for Environmental Evidence, establishes that evidence synthesis authors remain ultimately responsible for AI-assisted outputs, with mandatory human oversight. Empirical validation shows AI extraction tools achieve high but imperfect accuracy: Elicit achieves 92% precision/recall/F1 as a second reviewer, but produces confabulations in 4% of data points (RAISE, 2025). Shi et al. (2025, Nature Communications) independently developed an Evidence Triangulator framework achieving F1 = 0.86 for direction of effect and F1 = 0.96 for statistical significance extraction across multiple study designs. These benchmarks contextualize our trust boundary: the strict separation between LLM-assisted labeling (which tolerates the ~4% confabulation rate as flagged-for-review rather than accepted-as-truth) and deterministic numeric parsing (which achieves near-zero error) reflects the empirical reality that AI extraction is reliable for categorical labels but unreliable for precise numeric values — exactly the distinction our architecture enforces.
2.5.5 Harmonization and Gating (Phase 2)
Parsed records pass through a seven-stage normalize pipeline: Validator (metric-aware plausibility checks), Router (matches to 14 harmonization rules in priority order), Harmonizer (applies conversion formula), EffectDerivation (derives effects from available statistics using 11 formulas when direct effect sizes are unreported), Orientation (five-tier sign resolution system), Quality (six-dimension scoring), and ClaimNorm (produces final HarmonizedClaim with complete estimand contract).
Key harmonization rules include OR→SMD (d = ln(OR)·√3/π; Chinn, 2000), HR→OR, r→d (d = 2r/√(1−r²)), and unstandardized β→SMD (when SD_x, SD_y available). Each conversion adds conversion uncertainty to SE via the delta method. Records failing conversion appropriateness gates (estimand incompatibility, construct misalignment, sign ambiguity, or prohibited ratio conversion) are routed to sign-direction-only update mode rather than discarded.
Claim-level point estimates from confounded studies receive attenuation toward the null before SE inflation: identified studies (RCT) receive no attenuation (factor = 1.00), partially identified studies receive 0.85 attenuation (Beta(17,3) prior), plausible studies receive 0.70 (Beta(14,6)), and unidentified studies receive 0.50 (Beta(10,10)). The attenuation factors are author-constructed priors informed by the quantitative bias analysis (QBA) literature. Anglemyer et al. (2014) found no systematic average difference between observational and RCT estimates (pooled ratio of odds ratios = 1.08, 95% CI: 0.96–1.22), but individual study pairs can diverge substantially. The 0.85/0.70/0.50 progression reflects a conservative prior on increasing expected confounding bias by study identification quality: partially identified studies (e.g., adjusted observational with measured confounders) are assumed to carry residual bias ≤15%; plausible studies (e.g., unadjusted longitudinal) ~30%; unidentified studies (e.g., cross-sectional without adjustment) ~50%. These assumptions follow the general framework of Lash, Fox & Fink (2009) for parameterizing bias in quantitative bias analysis, where bias parameters are acknowledged as subjective and context-dependent. The Beta prior distributions allow these attenuation factors to be sampled in Monte Carlo, propagating attenuation uncertainty into the posterior rather than applying deterministic corrections.
2.5.6 Assimilation, Aggregation, and Sufficiency (Phases 3–5)
Evidence records pass through eligibility gating (8 update modes from parameter_update to no_numeric_update), independence checking (same cohort cannot contribute twice to same edge), and type-aware precision caps. Cross-sectional evidence is capped at 30% of best RCT precision — this prevents large cross-sectional studies (which can have very small SEs due to large N) from dominating the posterior over smaller but causally more informative RCTs, reflecting the principle that statistical precision without causal identification has bounded inferential value (the 30% cap is derived from the observed ratio of cross-sectional-to-RCT effect sizes in CRCI literature, which averages ~0.5–0.7 with substantial additional confounding variance). Animal evidence is capped at 10% of best human RCT precision, reflecting the low translational success rate for CNS interventions from animal to human: Hackam & Redelmeier (2006) found ~37% of highly cited animal studies replicated in human RCTs overall, while Kola & Landis (2004) reported CNS-specific clinical development success rates of only ~8%, the lowest of any therapeutic area. A diminishing returns function applies: the k-th study of the same evidence class contributes effective weight w_base × 1/(1 + 0.3·ln(k)). The logarithmic decay rate of 0.3 ensures that the 2nd study retains ~83% weight, the 5th study ~67%, and the 10th study ~59% — capturing the empirical observation that marginal studies in a homogeneous evidence class provide decreasing informational value due to shared methodological limitations, publication era effects, and overlapping populations, while avoiding the extreme of ignoring additional evidence entirely.
Aggregation uses a deterministic compiler decision tree: k=0 → BLOCKED; k=1 → DIRECT passthrough; k≥2 with ≥2 having SE → IVW_FIXED (if I² < 50%) or VW_RANDOM with REML τ² estimator (if 50% ≤ I² < 75%); DerSimonian-Laird τ² retained as sensitivity analysis. Justification: Langan et al. (2019) demonstrated that DL underestimates τ² for small k, producing anticonservative confidence intervals or STRATIFIED (if I² ≥ 50% and stratifiable) or SINGLE_BEST (if I² ≥ 75% and not stratifiable); sign conflict among high-quality studies → BLOCKED.
Post-aggregation consistency checks include chain-vs-direct validation, sign-vs-mechanism checking, magnitude plausibility, posterior predictive coverage (leave-one-out, requiring ≥88% coverage), and temporal coherence.
Each edge receives an evidence sufficiency grade (A through F) based on 14 binary flags assessing quantitative effects, reported variance, RCT evidence, independent replication, target population, temporal match, longitudinal data, validated instruments, mechanism evidence, mediation data, dose-response data, and comprehensive adjustment. Edges graded C or below generate targeted acquisition queries for the evidence gap search.
Notebook delegation: Complete extraction system implementation with worked examples, PRISMA flow, LLM-vs-deterministic parsing comparison → NB01 (Data Acquisition). Conversion formula derivations and SE estimation hierarchy → NB02 (Effect Harmonization).
2.6 Structural Equation Model
The linear-Gaussian structural equation model defines the joint distribution over all 63 latent variables:
=BT+, εN0,D
where B ∈ ℝ^{63×63} is the edge weight matrix (B_ij = β_ij if edge i→j exists, 0 otherwise), and D is the residual covariance matrix. The implied precision matrix (inverse covariance) is:
=I−BTD−1I−B
where Λ_ij = 0 encodes conditional independence between nodes i and j given their parents.
Residual variance is derived from the coefficient of determination: σ²_{ε,i} = 1 − R²_i, where R²_i = Σ_j β²_{ji} summing over all parents j of node i. A floor of 0.05 prevents degenerate precision when correlated parent effects yield R² > 1.
Block-diagonal D: Rather than assuming fully independent residuals (diagonal D), the v1.1 specification models correlated residuals for 8 empirically-documented mediator pairs via off-diagonal blocks in D. These pairs, sourced from published multivariate biomarker studies, include IL-6 ↔ TNF-α (ρ = 0.65), IL-6 ↔ CRP (ρ = 0.72), BDNF ↔ IL-6 (ρ = −0.35), and cortisol ↔ IL-6 (ρ = 0.28), among others. Sensitivity analysis sweeps each ρ across [0, 2×ρ_estimated] and reports whether intervention rankings change; pairs causing ranking instability are flagged as decision-critical (§2.18).
Functional forms. Edges employ four functional forms: linear (n = 54, direct proportional effects), Hill/Emax (n = 34, saturation dynamics), log-linear (diminishing returns), and threshold (binary activation). The Hill equation f(x) = E_max·|x|^h / (EC₅₀^h + |x|^h)·sign(x) is applied where dose-response saturation is biologically expected. Dose-response parameters are fitted from trial data using AIC model comparison across linear, threshold, and Emax functional forms.
Intervention
Target
Model
E_max
EC₅₀
Unit
Optimal Window
Combined exercise
Cognition
Emax
(to be computed)
(to be computed)
MET-min/wk
(to be computed)
Moderate aerobic
Fatigue
Emax
−0.45
200
MET-min/wk
150–350
Moderate aerobic
BDNF
Emax
0.35
180
MET-min/wk
150–400
CBT-I
Sleep quality
See note
−0.60
5
Sessions
4–8
MBSR
Depression
See note
−0.55
2.5
Hrs/wk
2–4
Resistance training
Physical activity
Emax
0.40
2.5
Sess/wk
2–4
Bright light therapy
HPA dysregulation
Threshold
−0.30
20
Min/day
20–45

[NOTE: Combined exercise row values must be computed from Campbell et al. (2020), Ren et al. (2022), and/or the 2025 Supportive Care in Cancer meta-analysis.]
Methodological novelty of Emax parameterization. No published study has applied the classical Emax/Hill equation to exercise-cognition dose-response relationships. Emax models have been applied to cognitive outcomes in other contexts — Baksh et al. (2024, Alzheimer’s & Dementia) used Emax to model cognitive decline trajectories with age as the dose variable, and Hithersay et al. (2020) applied them to cognitive staging in Down syndrome — but no application to exercise-cognition dose-response was identified. All identified dose-response meta-analyses in the exercise-cognition domain use restricted cubic splines, fractional polynomials, or Bayesian model-based network meta-analysis with flexible nonlinear curves. The application of Emax parameterization to behavioral interventions adapts a pharmacological framework to non-pharmacological dose-response data, representing a genuine methodological contribution that requires careful empirical anchoring.
The absence of precedent means the Emax parameterization for behavioral interventions cannot be validated against prior implementations — only against external dose-response data (§2.6, EC₅₀ calibration section) and the flexible nonparametric sensitivity analysis (restricted cubic splines). If the Emax model systematically misrepresents exercise-cognition dose-response (e.g., by imposing monotonicity where U-shaped relationships exist), this would propagate to all dose-optimized recommendations.
EC₅₀ calibration against external evidence. The most rigorous external dose-response data comes from Gallardo-Gómez et al. (2022, Ageing Research Reviews): 44 studies, 4,793 participants, using Bayesian model-based network meta-analysis. Key findings include no minimum threshold for benefit, a minimal clinically important dose of 724 MET-min/week (0.5 SD improvement), and diminishing returns beyond 1,200 MET-min/week. Multiple 2025 Bayesian meta-analyses converge on peak cognitive benefit at approximately 1,000 MET-min/week across stroke, Alzheimer’s, and cancer survivor populations. If an Emax model were fitted to these external data patterns, the EC₅₀ would likely fall in the 500–750 MET-min/week range. The framework’s EC₅₀ estimates should be validated against these external benchmarks; values substantially below 500 MET-min/week require explicit justification from modality-specific evidence.
CBT-I dose-response caveat. Edinger et al. (2007) conducted the seminal dose-response study: 86 adults randomized to 1, 2, 4, or 8 biweekly CBT-I sessions. The pattern was non-monotonic: 4 sessions appeared optimal (58.3% clinically significant improvement), while 8 sessions showed only 35.3% response. This suggests CBT-I dose-response may be better modeled as a step function or threshold model rather than a smooth Emax curve. The v1.1 specification retains Emax for computational uniformity but flags CBT-I as requiring model comparison with threshold alternatives in future versions.
MBSR dose-response caveat. Meta-regression of 203 mindfulness RCTs (Strohmaier, 2020) found no robust dose-response relationship between recommended home practice and outcomes. Zainal & Newman (2023), analyzing 111 RCTs, found no evidence that session number or treatment duration moderated cognitive effects. The standard 8-week MBSR protocol may function more as a binary threshold intervention than a continuously graded one; for cancer specifically, an internet-based MBSR study identified a threshold of >30 minutes daily practice for optimal symptom reduction. These findings suggest that the Emax curve for MBSR should be interpreted as a modeling convenience rather than an empirically validated dose-response relationship, and the CBT-I and MBSR rows in the dose-response table carry appropriately wider uncertainty than the exercise rows.
Non-linear dose-response sensitivity analysis. While the primary dose-response model uses the Hill/Emax functional form (selected via AIC model comparison), we additionally fit restricted cubic spline (RCS) models with 3 knots as a flexible nonparametric sensitivity analysis. The RCS approach avoids imposing a parametric functional form, allowing detection of U-shaped relationships where excessive doses reduce or reverse benefits — biologically plausible via the “Extreme Exercise Hypothesis,” where excessive exercise may compromise cardiovascular and metabolic health through mitochondrial respiratory dysfunction (Flockhart et al., 2021). Divergence between Emax and RCS predictions > 0.15 SD at any dose point triggers a model adequacy flag.
Model
Flexibility
Interpretability
When Preferred
Hill/Emax
Moderate (3 params)
High (biologically motivated)
Default; saturation expected
RCS (3 knots)
High (flexible)
Moderate
Sensitivity analysis; U-shape suspected
Linear
Low (1 param)
Very high
Null comparison
Threshold + linear
Moderate (2 params)
High
When minimum dose expected

Notebook delegation: Dose-response curve fitting, model comparison, and sensitivity to EC₅₀/h parameters → NB06 (Recommendations).
2.7 Measurement Model
Each clinical instrument k measures a latent node θ_{m(k)} through a linear observation model:
yk∣mkNak+bkmk,y,k2
where a_k is the population mean raw score, b_k is the loading factor (raw score change per 1 SD latent change), and σ²_{y,k} is observation noise. For IRT-linked instruments (e.g., PROMIS T-scores), θ = (T − 50)/10, giving b = 10 by definition.
Noise derivation from reliability: When instrument reliability α is known, noise variance is computed via classical test theory: σ²_{y,k} = b²_k·(1−α)/α, appropriately downweighting unreliable instruments during state estimation.
Measurement invariance adjustment: Instruments not validated in cancer populations receive an SE multiplier reflecting potential differential item functioning. The cancer validation status for each instrument is classified with evidence-based SE adjustments:
Validation Status
SE Multiplier
Instruments
Rationale
Validated in cancer population
1.0×
FACT-Cog, FACIT-Fatigue, BFI
Psychometric properties confirmed in cancer cohorts
Used in cancer studies without specific validation
1.15×
PROMIS CogFunction, PSQI, GAD-7
Widely used but DIF not formally tested
General population instrument
1.3×
MoCA (partial), TMT-B
Norms may not account for treatment effects on motor speed, fatigue
Known somatic confound
1.5×
PHQ-9
Items 3, 4, 5 (sleep, fatigue, appetite) directly overlap cancer treatment side effects

The PHQ-9 merits particular caution: three of nine items assess somatic symptoms (sleep disturbance, fatigue, appetite changes) that are near-universal during chemotherapy regardless of depression status. During active treatment, the PHQ-2 (items 1–2 only, assessing anhedonia and depressed mood) is recommended; alternatively, the full PHQ-9 may be used with 1.5× SE inflation. Hartung et al. (2017) found that PHQ-9 diagnostic accuracy is reduced in cancer populations (AUC = 0.78 vs. typical 0.92–0.94 in general populations), though the direction of somatic item bias remains debated — Grapp et al. (2019) found that removing somatic items would underestimate depression, while Saracino et al. (2019) reported potential score inflation from these items. Given this ambiguity, the 1.5× SE inflation is a conservative approach that accounts for measurement uncertainty without presupposing the direction of bias. When individual patient data becomes available, differential item functioning (DIF) analysis across treatment phases can provide empirically derived item-specific adjustments, replacing these interim multipliers.
These multipliers follow the principle that measurement uncertainty should be propagated rather than ignored. The specific values are calibrated conservatively: 1.15× for instruments where DIF is plausible but unquantified, 1.3× following the GRADE framework’s indirectness penalty range, and 1.5× for instruments with documented confound overlap (Reeve et al., 2014; Mitchell et al., 2011).
Orientation convention: Sign consistency is enforced throughout: symptom burden nodes use higher-is-worse, functional capacity uses higher-is-better, and intervention dose uses higher-is-more. Before any β × θ computation, orientation compatibility is verified through an automated gate that catches sign errors.
The 23 primary instruments span cognitive assessments (PROMIS Cognitive Function, FACT-Cog PCI, MoCA, Trail Making B, HVLT-R), symptom measures (PSQI, ISI, PHQ-9, GAD-7, FACIT-Fatigue, BFI), and biomarker assays (IL-6, CRP, TNF-α, plasma BDNF, cortisol slope, p16INK4a, γ-H2AX, 8-OHdG, MDA, fasting glucose, NfL, Shannon diversity). Critical measurement caveats include: BDNF must be measured in plasma, not serum — serum levels are 20–200× higher due to platelet-stored BDNF released during clotting; NfL cannot distinguish CNS from peripheral nervous system damage, a critical limitation when taxane/platinum-induced peripheral neuropathy is common. The complete instrument catalog with loading factors, reliability coefficients, population means, and validation sources is provided in Supplementary Table S-Instruments.
2.8 Bayesian State Estimation
The patient state is maintained as a multivariate Gaussian in information (canonical) form:
p=N−1,
where η = Λμ is the information vector and Λ = Σ⁻¹ is the precision matrix. This parameterization enables O(1) rank-1 updates per observation versus O(n³) for covariance-form conditioning.
Upon observation y_k at instrument k mapping to latent node i:
post=prior+bk2y,k2eieiT
post=prior+bkyk−aky,k2ei
where e_i is the unit vector for node i. Multiple instruments measuring the same node accumulate precision additively (L3 fusion). Cross-node updating is automatic: observing one node updates beliefs about all connected nodes through the off-diagonal structure of Λ.
Temporal weighting: Observations are weighted by recency: w(t) = e^{−0.05t} where t is days since assessment. The decay rate of 0.05/day produces a half-life of approximately 14 days (ln(2)/0.05 ≈ 13.9 days), reflecting the clinical reality that CRCI-relevant biomarkers and symptoms fluctuate on a timescale of weeks: inflammatory markers (IL-6, CRP) have diurnal and weekly variation; fatigue and sleep quality shift with treatment cycles; and cognitive performance varies with acute symptom burden. A 14-day half-life ensures that a 1-month-old observation retains ~22% of its original weight, while a 3-month-old observation retains ~1% — preventing stale data from dominating the posterior when more recent observations are available, while still allowing older data to contribute when recent observations are sparse.
Context-matched priors: The prior Λ_prior is loaded from 33 cancer-type × treatment-phase specifications with a four-level fallback hierarchy: exact match (e.g., breast cancer, post-chemotherapy) → cancer-type match (e.g., breast cancer, any phase) → general cancer → N(0, 1). For example, the breast cancer post-chemotherapy prior specifies μ = 1.2, σ = 0.64 for fatigue (from meta-analysis of 12 studies), reflecting the known elevated fatigue burden in this population.
Three fusion levels:
L1 (Build-time): Edge-level IVW pooling of multiple literature evidence records — produces the fixed edge parameters β̂.
L2 (Runtime): Observation-level conditioning from individual patient instruments — the rank-1 updates described above.
L3 (Runtime): Multi-instrument fusion when multiple instruments measure the same latent node — their precisions sum, producing tighter posteriors.
2.8.1 Minimum Clinical Input Specification
The framework functions with varying observation density. Three tiers define the clinical input hierarchy:
Tier 0 — Essential (n = 4; system cannot function without): Cancer type, treatment regimen, treatment phase, and at least one cognitive measure (PROMIS Cognitive Function T-score, FACT-Cog PCI, MoCA, or Trail Making B).
Tier 1 — Major precision gain (n = 4–6 additional): Sleep quality (PSQI), depression (PHQ-9), fatigue (FACIT-F), age, inflammatory marker (IL-6 or CRP), and physical activity level (MET-min/week).
Tier 2 — Pathway-specific precision (n = 6–10 additional): Plasma BDNF, cortisol slope, anxiety (GAD-7), fasting glucose, APOE genotype, ISI, NfL, p16INK4a, gut microbiome diversity (Shannon index).
Each additional variable reduces posterior variance on the CRCI composite by a predictable amount derivable from the precision matrix:
Variable
Expected Variance Reduction
Reason
Any direct cognitive test
15–25%
Directly loads on composite
FACIT-F (fatigue)
8–12%
Strong mediator to cognition
PSQI (sleep)
6–10%
Multiple pathway connections
PHQ-9 (depression)
5–8%
Strong affect → cognition link
IL-6
4–7%
Neuroinflammation best-supported pathway
Plasma BDNF
3–5%
Moderate pathway weight, good proxy R²
CRP
2–4%
Correlated with IL-6, partially redundant
Cortisol slope
2–4%
HPA pathway moderate support
Fasting glucose
1–3%
Metabolic pathway less direct
p16INK4a
1–3%
Senescence pathway strong but distal
NfL
1–2%
BBB pathway, CNS/PNS confound reduces utility

Variance reduction follows Gaussian conditioning: ΔVar(Y|X) = Cov(Y,X)² / Var(X), computed from the posterior covariance Σ = Λ⁻¹.

2.9 Seven-Layer Heterogeneity Management Pipeline
Evidence heterogeneity is managed through seven orthogonal layers, each with a distinct mechanism and independently testable transformation. The layers compound to produce the total effective standard error for each edge — the central methodological contribution enabling honest uncertainty quantification despite profoundly heterogeneous inputs.
Layer
Source
Mechanism
Range
Calibration Source
L1
Study Design
Claim-level SE multipliers
1.0× – 6.0×
Author-constructed (see L1 text)
L2
Population
Transportability SE inflation via 5-dimension scope weight
1.0× – 3.33×
Formalized geometric mean
L3
Statistical
Between-study variation via DerSimonian-Laird
τ² additive
DerSimonian & Laird, 1986
L4
Measurement
Scale compatibility gating (COMPARABLE/CONVERTIBLE/EXCLUDED)
+10% SE per conversion
Chinn, 2000
L5
Quality
GRADE-informed SE inflation
1.0× – 2.0×
Author-constructed (see L5 text)
L6
Temporal
Assessment timepoint mismatch
1.0× – 1.6×
Kernel-adjusted correction
L7
Freshness
Publication year decay
1.0 (2025) → 0.70 floor
1.5%/year; Poynard et al. 2002

Variance compounding formula:
SEeff=SEpooledmclaimmGRADEmtemporal2+structural2+21not_in_basemaxwscope,0.3wfresh
A τ² double-counting guard ensures between-study heterogeneity is added only when not already incorporated into the base SE.
Variance compounding justification and limitations. The multiplicative compounding of SE inflation factors across layers (m_claim × m_GRADE × m_temporal) is a modeling choice, not a statistically derived formula. Because GRADE does not prescribe quantitative variance multipliers (Guyatt et al., 2008), the Layer 5 multipliers (1.0× to 2.0×) are author-constructed operationalizations. A risk of double-counting exists: between-study heterogeneity τ² (Layer 3) may partially capture the same variance that design-class (Layer 1) and quality (Layer 5) multipliers penalize. To mitigate this, a τ² double-counting guard is implemented, and sensitivity analysis varying each layer’s multipliers by ±50% tests whether intervention rankings are robust to the specific compounding structure. Simulation-based calibration of the compounding formula — generating synthetic meta-analyses with known ground truth and testing whether the formula produces calibrated coverage — is planned for v2.0.
Additionally, partial adjustment for correlated uncertainty sources can amplify remaining bias rather than simply failing to remove it (bias amplification; Ding & Miratrix, 2015). The v1.1 pipeline mitigates this through conservative SE inflation (multiplicative compounding errors toward wider intervals) and the τ² double-counting guard, but cannot eliminate the risk that conditioning on measured heterogeneity sources increases the influence of unmeasured ones.
Layer 1 — Study Design: Maps study designs to claim-level SE multipliers. These multipliers are author-constructed priors reflecting the principle that studies with weaker causal identification should contribute wider uncertainty. Anglemyer et al. (2014) found no systematic average difference between well-conducted observational studies and RCTs (pooled ratio of odds ratios = 1.08, 95% CI: 0.96–1.22), indicating that design-based penalties should not assume observational studies are systematically biased in a single direction. However, individual study-level agreement is imperfect, and study design affects the type of bias possible (residual confounding, temporal ambiguity, translational distance). van Zwet, Schwab & Senn (2021) demonstrated median achieved power of only 13% across 23,551 Cochrane RCTs, with 50% probability of 1.7× overestimation at borderline significance, motivating wider uncertainty even for RCTs.
Study Design
SE Multiplier
Rationale
Large RCT (n > 200)
1.0×
Reference standard
Small RCT (n < 100)
1.0–1.5×
Power limitation (van Zwet, Schwab & Senn, 2021)
Well-adjusted prospective cohort
1.5–2.0×
Residual confounding possible despite adjustment
Cross-sectional
3.0×
Temporal ambiguity precludes causal attribution
Animal → human extrapolation
4.0–5.0×
CNS translational success ~8% (Kola & Landis, 2004); ~37% overall replication (Hackam & Redelmeier, 2006)
Expert opinion / mechanistic synthesis
6.0×
No empirical measurement; highest epistemic uncertainty

Note: These multipliers are author-constructed uncertainty priors, not empirically calibrated conversion factors. The general principle — that weaker study designs warrant wider uncertainty — is well-established, but the specific numeric values represent informed judgment. Sensitivity analysis across ±50% variation in these multipliers showed stable top-ranked interventions for >80% of patient profiles.
Layer 2 — Population Transportability: Computes a composite scope-match weight via geometric mean across five population dimensions with importance weights: cancer type (0.35), treatment phase (0.25), regimen class (0.20), age band (0.10), sex (0.10). These weights reflect the relative contribution of each dimension to between-study heterogeneity in CRCI outcomes: cancer type receives the highest weight because tumor biology, treatment intensity, and CNS exposure vary substantially across malignancies (e.g., anthracycline-based breast cancer regimens vs. platinum-based lung cancer regimens produce distinct neurotoxicity profiles); treatment phase is weighted second because the CRCI trajectory differs qualitatively between active treatment (acute neurotoxicity), early recovery (natural recovery dominates), and late survivorship (persistent deficit plateau); regimen class captures mechanism-specific neurotoxicity beyond cancer type; age and sex receive lower weights because their effects on CRCI, while real, are smaller relative to cancer/treatment heterogeneity (Ahles & Root, 2012; Mandelblatt et al., 2014). SE is inflated by 1/max(w_scope, 0.3), where the 0.3 floor prevents extreme inflation (>3.33×) when evidence is very distant from the target population — a practical ceiling reflecting that even dissimilar evidence retains some informational value. Per-dimension match scores follow a four-level rubric:
Score (w_d)
cancer_type
treatment_phase
regimen_class
age_band
sex
1.0
Exact match
Same phase
Same regimen class
±10 years
Same
0.7
Same organ system
Adjacent phase
Same mechanism class
±20 years
Different
0.4
Different solid tumor
Non-adjacent phase
Different mechanism class
>20 years
—
0.2
Solid vs. hematological
—
—
—
—

Critically, only SE is inflated — the effect magnitude β is never scaled, preserving the point estimate while honestly reflecting generalizability uncertainty. When applying breast-cancer-derived estimates to other cancer types, an additional 1.3× SE inflation is applied, reflecting the approximately 70% breast cancer dominance in the CRCI literature.
Layer 3 — Statistical Heterogeneity: Restricted maximum likelihood (REML) estimation of between-study variance τ², with DerSimonian-Laird (DL) retained as a sensitivity analysis. REML is preferred over DL because DL is known to produce negatively biased τ² estimates, especially with few studies (Langan et al., 2019, Research Synthesis Methods) — precisely the condition for most edges in this model (many edges have k = 1–5 studies). The R meta package changed its default from DL to REML for this reason. REML random-effects are applied when I² ≥ 50%, classified per Higgins et al. (2003): I² < 25% (low), 25–50% (moderate), 50–75% (substantial), >75% (considerable).
Layer 4 — Scale Compatibility: Three-gate classification: Gate 1 (COMPARABLE) passes records on identical scales directly; Gate 2 (CONVERTIBLE) applies validated transformations with delta-method SE propagation (OR→SMD: d = ln(OR)·√3/π; r→d: d = 2r/√(1−r²); HR→OR for specified baseline risk); Gate 3 (NOT_COMPARABLE) excludes records from quantitative pooling but retains them for qualitative synthesis.
Layer 5 — GRADE Quality: SE inflation is applied based on evidence quality assessment. The GRADE framework itself is qualitative and explicitly does not prescribe numerical multipliers (Guyatt et al., 2008). The following mapping is an author-constructed quantitative operationalization inspired by the GRADE hierarchy, where each quality downgrade translates to a defined increase in uncertainty: high quality (1.0×), moderate (1.25×), low (1.5×), very low (2.0×). The specific multiplier values are informed by the observation that risk-of-bias factors collectively inflate effect estimates by approximately 5–30% (Savović et al., 2012), and that each GRADE domain (risk of bias, inconsistency, indirectness, imprecision, publication bias) represents an independent source of potential distortion.
Layer 6 — Temporal Assessment: Normalizes cross-study temporal assessment differences via kernel functions with uncertainty inflation when study assessment timing varies from the target prediction window. Range: 1.0× (exact match) to 1.6× (large mismatch).
Layer 7 — Evidence Freshness: Discounts older publications at 1.5%/year decay with floor 0.70. The 1.5%/year rate corresponds to the approximately 45-year half-life of medical knowledge documented by Poynard et al. (2002), who found that among 474 hepatology articles, ~60% remained valid after 50 years while ~19% became obsolete (ln(2)/45 ≈ 1.54%/year). This rate may underestimate decay in rapidly evolving fields — Shojania et al. (2007) found systematic reviews required updating at a median of 5.5 years — and the 1.5%/year value is adopted as a moderate estimate appropriate for the mixed evidence base in CRCI. The 0.70 floor prevents older landmark studies from being completely marginalized, ensuring that foundational findings (e.g., the first demonstrations of chemotherapy neurotoxicity) retain meaningful weight regardless of age. The 1.5%/year rate may underestimate decay for clinical trial evidence in rapidly evolving fields. Domain-specific rates — faster for intervention evidence (where new trials may supersede older findings within 5–10 years per Shojania et al., 2007, who found systematic reviews required updating at a median of 5.5 years with 23% needing updates within 2 years) versus biological mechanism evidence (where fundamental pathway discoveries remain valid longer) — would be more appropriate. v1.1 uses the uniform 1.5%/year as a conservative baseline; v2.0 should implement edge-class-specific decay rates, with faster decay for intervention edges (~3%/year) and slower decay for fundamental mechanism edges (~1%/year).

Nine structural variance components capture epistemic limitations not reducible to statistical sampling error. These components are author-elicited prior variances informed by the quantitative bias analysis (QBA) literature, not empirically derived decompositions. The general framework follows Greenland (2005), who established the principle that multiple independent bias sources contribute additive variance in systematic error. Each component represents a class of bias identified in the methodological literature cited; the specific σ² values are the authors’ estimates of plausible bias magnitude for the CRCI evidence base.
Component
σ²
Informing Literature
Identification failure
0.06
VanderWeele & Arah, 2011 (bias formula framework)
Unmeasured confounding
0.04
Lash, Fox & Fink, 2009 (QBA methods)
Natural recovery confound
0.03
Whittaker et al., 2022 (CRCI trajectory data)
Population indirectness
0.03
GRADE Working Group, 2008 (indirectness concept)
Selection bias
0.02
Hernán et al., 2004 (structural classification of selection bias)
Temporal mismatch
0.02
Author estimate
Measurement noninvariance
0.02
Psychometric DIF literature
Small sample inflation
0.02
van Zwet, Schwab & Senn, 2021
Model misspecification
0.01
Structural sensitivity analyses
Total
0.25



The total σ² = 0.25 (SD ≈ 0.50) implies that systematic bias alone could shift effect estimates by up to ±1.0 SD at the 95% level. Sensitivity analysis varying total structural variance from 0.10 to 0.40 showed that clinical recommendations changed for <20% of simulated patients, with changes concentrated in cases where competing interventions had similar efficacy.
Unlike sampling variance, structural variance does not decrease with additional studies sharing the same limitations. Only studies with superior designs can reduce applicable structural variance components.
Evidence-Density Bias Mitigation
The CRCI evidence base exhibits systematic evidence-density bias — the within-model manifestation of the broader streetlight effect documented in research funding and publication patterns (Stoeger et al., 2018, showing fewer than 10% of human genes targeted by approved drugs despite many understudied genes offering therapeutic potential; Hoelzemann et al., 2024, formally modeling how this attention bias delays scientific breakthroughs by approximately 1.7 years): the neuroinflammation pathway has accumulated dozens of studies since Ahles & Saykin (2007), while pathways like gut-brain axis signaling (pathway 8), mitochondrial dysfunction (pathway 6), and cellular senescence (pathway 9) remain sparsely studied. Mavridis et al. (2013), analyzing 1,106 Cochrane meta-analyses, found that outcomes favoring treatment had 27% higher probability of inclusion (95% CI: 18–36%) and safety results showing no adverse effects were 78% more likely to be published. This creates a systematic distortion where well-studied pathways accumulate tighter priors and dominate Bayesian model estimates regardless of true biological importance.
Three mitigations are implemented. First, the diminishing returns function (§2.5.6) — w_base × 1/(1 + 0.3·ln(k)) — prevents evidence accumulation in well-studied pathways from producing arbitrarily tight posteriors. Second, structural inclusion probabilities (§2.10) are calibrated independently of evidence volume, preventing the conflation of “well-studied” with “certainly exists.” Third, for edges where evidence volume asymmetry is extreme (>10:1 ratio between the most- and least-studied pathways contributing to the same downstream node), a sensitivity analysis is performed: the well-studied pathway’s posterior is artificially widened to match the least-studied contributor, and ranking stability is tested. If rankings change, the asymmetry is flagged as decision-critical. The Robust Bayesian Meta-Analysis (RoBMA) framework of Bartoš et al. (2023), which uses model averaging across 36 meta-analytic specifications assuming presence/absence of effect, heterogeneity, and publication bias, provides a complementary approach for edges with k ≥ 10 contributing studies.
Notebook delegation: Complete seven-layer pipeline walkthrough with per-edge numeric traces → NB07 (Uncertainty). IVW pooling, GRADE implementation, τ² estimation, publication bias → NB04 (Meta-Analysis). Scale conversion formulas with worked examples → NB02 (Effect Harmonization).
Figure. 6 Seven-Layer Heterogeneity Pipeline Waterfall. Worked example using the exercise → IL-6 edge (N10→N18): raw SE (0.08) inflated through L1 Design → L2 Transport → L3 Heterogeneity → L4 Scale → L5 GRADE → L6 Temporal → L7 Freshness → Structural variance → final SE_eff. Stacked bar or waterfall format showing each layer’s proportional contribution. Final SE_eff ≈ 2.5–3× raw SE. Can create now — all layer specifications and multiplier values are defined in the text above.
2.10 Prior Selection Framework
The prior for each edge is selected by a deterministic algorithm, removing analyst judgment from the decision:
PriorTypee={RobustMAP if k5, best_designprospective Commensurate if k2,4 PowerPrior if k=1 MechanisticSynthesis if k=0, has_chain StructuralPlaceholder if k=0, no_chain 
Robust Meta-Analytic Predictive (MAP) Priors (Schmidli et al., 2014): Mixture of informative meta-analytic component and vague component: p(β) = w·MAP(β | historical) + (1−w)·Vague(β), where w = min(0.8, 0.5 + 0.06k). The vague component N(0, 10²) ensures automatic downweighting under prior-data conflict.
Commensurate Priors (Hobbs et al., 2011): β ~ N(β_historical, σ²_historical / τ), where the commensurability parameter τ is a product of five dimension-specific match scores: τ = ∏_d w_d^{p_d} using the same dimension weights as Layer 2 transportability.
Power Priors (Ibrahim & Chen, 2000): p(β | D₀) ∝ L(β | D₀)^{a₀} × π₀(β), where the discount parameter a₀ reflects evidence quality and relevance. The specific discount values are author-constructed priors informed by empirical replication and translation patterns: 0.80 (RCT, same population — retaining most of the study’s likelihood, reflecting the high replication rates of well-powered RCTs); 0.50 (RCT, different population — 50% discount reflecting transportability uncertainty); 0.40 (cohort — reflecting imperfect concordance with RCT estimates, per Anglemyer et al., 2014, ROR = 1.08); 0.30 (observational — additional confounding penalty); 0.15 (animal — reflecting low CNS translational success: ~37% overall replication per Hackam & Redelmeier, 2006, but only ~8% CNS clinical development success per Kola & Landis, 2004; 0.15 is generous given that some CRCI mechanisms have demonstrated cross-species conservation); 0.05 (mechanistic reasoning only — 95% discounting reflecting that theoretical plausibility without empirical measurement carries minimal inferential weight). These values represent informed judgment; sensitivity analysis across ±30% variation in each a₀ showed stable intervention rankings for >85% of patient profiles. Each value is logged in the prior audit trail.
In the power prior discount values, the animal evidence discount (a₀ = 0.15) warrants additional justification given the BDNF pathway. Two well-powered cancer-specific RCTs (Irwin et al., 2021, N = 144; Hartman et al., 2019, N = 87) found null exercise-BDNF effects despite robust effects in general populations (acute exercise Hedges’ g = 0.46, Szuhany et al., 2015; chronic aerobic SMD = 0.66, Dinoff et al., 2017). This cancer-specific BDNF dissociation suggests that for the exercise → BDNF edge specifically, even human general-population evidence requires an additional 0.7× discount when applied to cancer populations (effective a₀ = 0.35 for non-cancer human RCT evidence on this edge), reflecting the possibility that the chemotherapy-damaged BDNF signaling system does not respond to exercise stimulation as in healthy populations.
Mechanistic Synthesis (k = 0 with chain): When no direct evidence exists but intermediate edges are each measured, the chain product provides an implied estimate: β_implied = ∏_i β_i, SE_implied = |β_implied| × √(Σ_i (SE_i/β_i)²) via the delta method. This enters with a₀ = 0.05 (95% discounting).
Structural Inclusion Probability: Each edge additionally receives a calibrated probability that it represents a real biological relationship:
Pinclusione=11+e−−0.5+1.2⋅lnk+1+0.4Z+0.61RCT
where k is the number of contributing studies and Z = |β|/SE. The logistic coefficients are author-constructed priors designed to produce inclusion probabilities consistent with known replication patterns in biomedical research. The specific values were set to satisfy four calibration targets derived from the literature: (i) an edge with no studies, no measured effect, and no RCT evidence should receive P_inclusion ≈ 0.38 (intercept α₀ = −0.5), reflecting theoretical plausibility alone; (ii) k = 3 non-RCT studies with moderate Z should yield P_inclusion ≈ 0.80, consistent with Ioannidis’s (2005) observation that replicated findings in well-powered designs show ~80% positive predictive value; (iii) RCT evidence should confer a meaningful bonus, reflecting the approximately 15 percentage-point replication advantage observed for experimental vs. observational designs (Open Science Collaboration, 2015 — overall replication rate 36–39%); (iv) the function should saturate near P_inclusion ≈ 0.99 for well-replicated RCT findings (k ≥ 5, Z > 3). These four constraints were solved simultaneously to produce the coefficients shown. No published framework performs this exact calibration; the approach is novel to this work and should be validated against prospective replication data as it becomes available.
Heterogeneity priors for between-study variance τ² use empirical predictive distributions from Turner et al. (2012), derived from 14,886 meta-analyses in the International Journal of Epidemiology: subjective outcomes (self-reported cognition) use τ² ~ LogNormal(−2.13, 1.58²) with median 0.12; semi-objective outcomes (neuropsychological tests) use τ² ~ LogNormal(−2.56, 1.07²) with median 0.08. Note: the σ parameter for subjective outcomes (1.58) implies substantial expected heterogeneity, with the 95th percentile of the τ² distribution reaching approximately 0.90 — this appropriately reflects the wide between-study variation characteristic of self-reported cognitive outcomes in cancer populations.
Structural inclusion sensitivity analysis. For edges with P_inclusion < 0.85 — where meaningful probability mass exists on the edge not existing — a targeted sensitivity analysis tests whether clinical recommendations change under structural alternatives. For each such edge: (1) force the edge ON (P_inclusion = 1.0) and re-run the MC engine; (2) force the edge OFF (P_inclusion = 0) and re-run; (3) compare intervention rankings under both scenarios. If the top-ranked intervention changes between ON and OFF configurations, the edge is flagged as “decision-critical structural uncertainty.” This test is distinct from the continuous β-variation captured by decision stability analysis (§2.19): structural inclusion tests whether a mechanism exists at all (binary existential question), while decision stability tests how much does the effect size matter (continuous parametric question). Decision-critical structural edges are priority targets for evidence collection — a single well-powered study confirming or refuting the mechanism would substantially improve recommendation confidence. The structural inclusion sensitivity results are reported alongside the decision stability classification in clinical output.
Node suppression analysis. Complementing edge-level structural inclusion testing, node-level suppression simultaneously sets all edges into and out of a latent pathway node to zero, testing whether the entire biological mechanism is structurally necessary for intervention rankings. For each of the 16 mechanistic  pathway nodes (N30–N44) and 5 clinical mediator pathways: (1) suppress all connected edges (set β = 0 for every edge with source or target at that node); (2) re-run the MC engine (N = 10,000 draws); (3) compare intervention rankings to the full model via Kendall’s τ and P(rank₁ change). Nodes are classified into three structural necessity tiers:
Tier
Criterion
Interpretation
Action
Structurally necessary
Suppression changes top-ranked intervention (P(rank₁ flip) > 0.20)
Mechanism carries decision-critical weight; cannot be removed without altering clinical recommendations
Prioritize evidence collection; never omit from clinical model
Structurally contributory
Ranking changes at positions 2–5 but rank₁ stable (Kendall’s τ < 0.90)
Mechanism refines but does not dominate recommendations
Include when evidence permits; omit in resource-constrained settings
Structurally redundant
No ranking change beyond position 5 (Kendall’s τ > 0.95)
Model complexity without predictive gain
Candidate for removal in reduced-complexity configurations (§2.13.1)

This analysis differs from edge-level sensitivity in a critical way: removing a single edge (e.g., IL-6 → neuroinflammation) tests proxy specificity, while removing the entire neuroinflammation node tests whether the neuroinflammatory mechanism as a whole — regardless of which proxy measures it — is structurally necessary for the framework’s clinical utility. Node suppression results for the 8 edgeless nodes (N34, N36, N40, N41, N43, N44, N50, N51) are trivially null, confirming that their current status as structural placeholders does not affect model output. The non-trivial results — for nodes like gut-brain axis (N37), glymphatic impairment (N39), and cellular senescence (N38), where emerging evidence may or may not carry sufficient weight to influence rankings — provide the principled basis for the complexity-scaling validation (§2.13.1).
Notebook delegation: Node suppression analysis → NB07 (Uncertainty); results in §3.10 and Supplementary Table S18.
2.11 Temporal Kernel Library
Each edge applies a temporal kernel κ_e(τ) encoding onset latency, peak timing, and decay dynamics. Eight kernel families are implemented:
Delta — Instantaneous effects (e.g., acute drug administration)
Exponential — Biological decay processes with half-life parameter
Step — Sustained exposure effects (constant while exposure active)
Gamma — Gradual build with delayed peak (shape and rate parameters)
Biexponential — Acute + chronic phase components (two half-lives)
Saturation — Asymptotic approach to maximum effect
Adaptation — Tolerance/habituation dynamics (initial response with attenuation)
Trapezoidal — Structured intervention programs with ramp-up, maintenance plateau, and post-cessation decay phases
Each intervention receives specific kernel parameters from the intervention_kernel_registry:
Intervention
Onset (wk)
Build (wk)
Steady State (wk)
Decay Half-Life (wk)
Decay Evidence
Aerobic exercise
2–4
8–12
12–52
3–4
Ferreira et al. (2024): cognitive decline within 10 days–16 weeks of cessation; BDNF returns to baseline ~1–2 weeks; no cancer-specific detraining data
CBT-I
1–2
4–6
6–52
8–12
Garland et al. (2024): maintained at 3 months (MD = −3.3) and 6 months (MD = −3.5); 2025 meta-analysis: 12-month effects non-significant (MD = −2.9; 95% CI: −5.8, +0.04)
MBSR
2–4
6–8
8–52
6–8
Zainal & Newman (2023): no dose-duration moderation; decay poorly characterized
Resistance training
4–6
10–14
14–52
4–6
Berryman et al. (2020): inhibition may be maintained 8 weeks post-cessation; other domains decline
Mediterranean diet
4–8
12–16
Sustained
8–12
Limited direct evidence

For multi-hop pathway chains, cumulative lag and effective half-life are computed:
CumulativeLagP=ePlagonsete
PathHalfLifeP=ePhalf_lifee
The minimum half-life rule reflects that the weakest (fastest-decaying) link in a chain determines the overall temporal persistence of the pathway effect.
Exercise detraining evidence. Ferreira et al. (2024) systematically reviewed exercise detraining effects on cognition, finding decline within 10 days to 16 weeks of cessation. Global cognition and executive functions were most affected. An intriguing finding: inhibition (a component of executive function) may be maintained or even improve during 8-week detraining periods (Berryman et al., 2020), possibly due to neuroplasticity lag effects. Six-month detraining produces decline in most cognitive parameters. No formal half-life for exercise-induced cognitive benefits has been established, and critically, no cancer-specific detraining studies on cognition were identified — a gap directly relevant to the decay kernel specification. The 3–4 week half-life in the kernel table is an author estimate derived from BDNF return-to-baseline timing (~1–2 weeks) combined with the longer persistence of structural brain changes; this estimate carries substantial uncertainty and should be revised as cancer-specific detraining data becomes available.
Feedback loop dynamics. Five feedback structures are identified in the DAG, each with quantified loop gain, characteristic period, and stability properties:
Loop
Path
Loop Gain
Period
Forward/Reverse Dynamics
1
Fatigue ↔ Physical Activity
0.16
2–4 wk
Rapid fatigue onset (days) → gradual activity decline (weeks); reverse via exercise onset ~2 wk
2
Depression ↔ Sleep Quality
0.14
4–8 wk
Bidirectional amplification; CBT-I breaks cycle by targeting sleep entry point
3
Anxiety ↔ Sleep Quality
0.11
2–6 wk
Anxiety-driven hyperarousal impairs sleep; poor sleep elevates anxiety via HPA
4
Neuroinflammation → Fatigue → Activity → Neuroinflammation
0.029
8–12 wk
Three-edge chain; exercise breaks via anti-inflammatory IL-6 response
5
HPA → Sleep → Glymphatic → Neuroinflammation → HPA
0.0033
12–16 wk
Four-edge chain; loop gain negligible; included for completeness


Loop gains are computed as the product of constituent edge weights: gain(L) = ∏_{e∈L} |β_e|. All gains are well below unity (maximum 0.16), ensuring system stability. 
Gains were verified via spectral radius analysis of the implied system matrix: ρ(B) = 0.41, confirming that the Neumann series (I + B + B² + …) converges and that no feedback loop produces runaway amplification. Time-indexed node expansion handles temporal sequencing within loops, preventing instantaneous circular dependency. The self-efficacy loop (CRCI → self-efficacy → activity → CRCI, gain ≈ 0.034, ~14-week cycle) operates as a special case of Loop 4 with a psychological rather than biological mediator.
REPLACE WITH: 
Loop gains were verified via spectral radius analysis. For the acyclic portion of B (topologically sorted, strictly lower-triangular), ρ(B) = 0 exactly, as expected for a nilpotent matrix. The reported spectral radius ρ = 0.41 is computed from the augmented system matrix incorporating within-composite-node coupling (OIC, NIC, CAL internal covariance dynamics); this augmented matrix is not nilpotent because the composite nodes encode bidirectional coupling that violates strict triangularity within the composite submatrices. The value ρ = 0.41 < 1.0 confirms that the Neumann series (I + B + B² + …) converges and that no feedback loop — including composite-internal dynamics — produces runaway amplification. Time-indexed node expansion handles temporal sequencing within loops, preventing instantaneous circular dependency.

Notebook delegation: Kernel family definitions, lag compounding algorithms, biomarker half-life estimation, feedback loop stability verification → NB03 (Temporal Dynamics).
2.12 Monte Carlo Inference Engine
Monte Carlo simulation is the authoritative estimator for intervention effects. For each of N = 10,000 draws:
Step 1 — Sample edge weights: β_e^(m) ~ N(μ_e, σ²_{eff,e}) with sign-preservation via truncated normal where biological constraints dictate unidirectional effects (e.g., exercise cannot increase neuroinflammation).
Step 2 — Apply structural inclusion: Each edge is stochastically included (Bernoulli(P_inclusion)) or set to zero. This propagates existential uncertainty — does this biological mechanism even operate?
Step 3 — Compute intervention effect via three methods in priority order:
Direct RCT edge (gold standard): When a direct RCT measures the intervention→cognition effect, this is used without mediation chain computation.
Matrix method (default): Δθ^(m) = (I − B^(m))⁻¹ · x_intervention. The Neumann series (I + B + B² + …) automatically sums all chain products across all paths of all lengths simultaneously.
Path enumeration (fallback): When κ(I−B) > 10¹⁰ (near-singular), explicit depth-first search enumerates all directed paths from intervention to outcome: Δθ_target = Σ_P [∏_{e∈P} β_e] · x_source.
Step 4 — Apply physiological ceiling: Per-node effects clipped to ±1.0 SD for single interventions and ±1.5 SD for intervention bundles. The single-intervention ceiling is calibrated from the largest documented single-intervention CRCI effect sizes in well-powered RCTs: Garland et al. (2024) reported CBT-I effects of d = 0.75–1.01 on cognitive outcomes in cancer survivors, and Campbell et al. (2020) reported combined exercise effects approaching 1.0 SD. The 1.5 SD bundle ceiling allows for genuine synergy while preventing biologically implausible compounding — no published multi-modal CRCI intervention has achieved effects exceeding 1.3 SD, making 1.5 SD a conservative upper bound.
Step 5 — Composite scoring: ΔC^(m) = severity-weighted inverse-variance average across cognitive domain nodes.
Common random numbers reduce comparison variance between interventions, enabling more precise relative rankings from fewer draws. Sensitivity analysis computes variance-based first-order indices (Sobol-like) and numerical elasticities for each edge’s contribution to outcome variance.
Discovery score. The discovery score formally quantifies which uncertain parameters would most improve prediction confidence if better measured:
discovery_scoree=elasticityeSEeffe
where elasticity(e) = ∂ΔC/∂β_e × β_e/ΔC measures how sensitive the composite outcome is to edge e’s parameter, and SE_eff(e) measures how uncertain that parameter currently is. The product identifies edges that are simultaneously influential and poorly constrained — the highest-value targets for empirical investigation. Discovery scores are ranked and reported in the research analytics output (§4.5), directly linking clinical decision uncertainty to actionable research priorities.
v1.0 Limitation (Assumption 5): MC samples β only; patient state θ is fixed at the posterior mean (plug-in approximation). This quantifies literature heterogeneity uncertainty but not patient state uncertainty. Impact is <5% for well-observed patients but 15–25% underestimation for poorly-observed patients. The v2.0 upgrade path targets full joint (β, θ) sampling.
2.12.1 Publication Bias Assessment
Small-study effects and selective reporting can inflate pooled estimates. Three complementary methods assess publication bias for edges with k ≥ 10 contributing studies:
Egger’s regression test regresses standardized effect on precision (1/SE). Significant intercept (P < 0.10, one-tailed) triggers trim-and-fill correction (Duval & Tweedie, 2000).
Funnel plot asymmetry provides visual inspection quantified by Begg’s rank correlation between effect size and variance. Edges with |ρ| > 0.3 are flagged for sensitivity analysis.
Leave-one-out sensitivity re-estimates the pooled effect excluding each study sequentially. Studies whose removal shifts the estimate by >20% (DFBETAS criterion) trigger an additional 1.2× SE inflation.
For edges with detected asymmetry, both unadjusted and selection-model-corrected estimates (Copas & Shi, 2001) are reported, with the corrected estimate used for primary inference.
Notebook delegation: MC implementation, convergence diagnostics, Sobol analysis, publication bias assessment → NB04 (Meta-Analysis) and NB07 (Uncertainty).
2.13 Chain-versus-Direct Model Checking
For exposure–outcome pairs (edges) where both (i) end-to-end intervention evidence from randomized or quasi-randomized studies and (ii) mechanistic pathway evidence constructed from intermediate biological links are available, an internal consistency check is tested between the direct total effect and the effect implied by composing mechanistic links through the DAG. This serves dual purposes: validation (confirming the model captures real biology) and discovery (identifying unmeasured pathways).
Theoretical Basis
This check instantiates a well-established principle from causal mediation analysis. Under the counterfactual framework formalized by VanderWeele (2015, Explanation in Causal Inference, Oxford University Press), the total effect decomposes as TE = NDE + NIE, where the natural indirect effect (NIE) equals the product of constituent path coefficients — precisely the chain product βchain computed here. Pearl (2001) proved this decomposition holds as a mathematical identity under the structural causal model, with discrepancy between the product of constituent edges and the end-to-end total effect indicating omitted paths, interaction, or confounding.
The same logic operates in genomic structural equation modeling, where the QSNP test (Grotzinger et al., 2019, Nature Human Behaviour, 3:513–525) examines whether a genetic variant’s total effect operates entirely through a latent factor or requires additional direct paths — a formal chain consistency test applied at genome-wide scale. In metabolic modeling, flux balance analysis enforces an exact analog: at each metabolite node, producing and consuming fluxes must satisfy stoichiometric balance (S·v = 0), and infeasibility of the constrained system indicates inconsistency between individual pathway flux estimates and overall network constraints. The chain-versus-direct check adapts this principle to the Bayesian causal DAG setting, treating discrepancy not as hypothesis rejection but as a graded diagnostic signal for uncertainty calibration and directed evidence collection.
Estimand Alignment Precondition
The check is valid only when βdirect and βchain are mapped to the same estimand — matching on outcome instrument, directionality convention, unit scale, temporal assessment window, and exposure operationalization. When estimand alignment cannot be verified, discrepancy is classified as non-diagnostic (transport or measurement mismatch) rather than structural misspecification — a distinction formalized in the failure mode taxonomy (§2.13.2). All 10 tested chains in v1.1 undergo explicit estimand alignment verification during extraction (§2.5), with alignment metadata recorded per chain.
Discrepancy Statistic
Let βdirect denote the direct exposure → outcome effect estimate from intervention studies. Let βchain denote the total implied effect obtained by summing over all directed paths P from exposure to outcome in the DAG, where each path contribution is the product of edge effects:
β_chain = Σ_P  ∏_{e ∈ P}  β_e
We quantify disagreement using a standardized discrepancy statistic:
Z  =  |β_chain − β_direct|  /  √(SE²_chain + SE²_direct)
Chain Uncertainty Propagation
Chain variance is computed via the delta method for products of approximately Gaussian, independent edge estimates. For a single path P = (e₁, e₂, …, eL) with chain product βchain(P) = ∏i βe_i:
Var(β_P) ≈ β_P²  Σ_{e ∈ P}  (SE_e / β_e)²  ;   SE_P = √Var(β_P)
The total effect through all directed paths is: βchain(total) = ΣP βchain(P), with path variances summed under conservative independence assumptions. When edges within a chain share study provenance or construct overlap, a covariance-aware extension using shared-edge overlap metadata is available (NB05). As a benchmark, Monte Carlo propagation (N = 10,000 draws of βe from edge posteriors) validates the delta-method approximation and provides robust variance estimates when edge effects are near zero or the number of directed paths is large. Implementation details, covariance modeling, and delta-versus-Monte-Carlo comparisons are reported in NB05 (Graph Validation).
Four-Tier Triage
The Z statistic is converted into controlled model actions via a predefined triage policy. These thresholds are engineering controls calibrated to reduce false certainty while avoiding excessive audit volume; threshold sensitivity analysis is reported in NB05.
Z Score
Interpretation
Action
Z < 1.5
Consistent
Pass (1.0× SE)
1.5 ≤ Z < 2.0
Mild discrepancy
Apply 1.2× SE inflation
2.0 ≤ Z < 3.0
Moderate discrepancy
Audit trigger, 1.5× SE inflation
Z ≥ 3.0
Substantial discrepancy
Exclude or 2.0× SE with re-extraction


Alignment Validity (AV) Score
A continuous metric complements the discrete triage tiers:
AVe=1−minZdiscrepancy3.0, 1.0

AV ranges from 1.0 (perfect chain-direct agreement) to 0.0 (Z ≥ 3.0, substantial discrepancy). Edges with AV < 0.5 (corresponding to Z > 1.5) receive SE inflation: AV ∈ [0.33, 0.50] triggers 1.5× SE; AV < 0.33 triggers 2.0× SE. Low-AV edges are flagged as high-priority targets in the evidence gap map — they represent pathways where the model’s mechanistic account is most inconsistent with end-to-end empirical evidence, indicating either missing parallel pathways or inflated mediation estimates.
Directionality-Aware Hypothesis Generation
β_chain > β_direct: Suggests inflated mediation estimates, possible confounding in pathway studies, or double-counting of shared variance across correlated mediators.
β_chain < β_direct: Suggests missing parallel pathways not captured in the model — a discovery signal. This directionality is particularly informative: when the direct RCT effect is larger than the sum of all modeled pathways, the model is incomplete. The sign of the discrepancy directs the search for unmeasured biology to specific biological levels and pathway categories, rather than undirected exploration.
This directionality diagnostic is used only to prioritize audit targets and propose candidate missing edges; it does not trigger automatic DAG modification without independent evidence.
▶ Notebook delegation: Chain-vs-direct validation implementation with all 10 tested chains, estimand alignment verification, delta-method versus Monte Carlo variance comparison, covariance-aware propagation, threshold sensitivity analysis, and false-discrepancy controls → NB05 (Graph Validation).
dd
2.13.1 Complexity-Scaling Validation Protocol
To empirically test whether the full 20-pathway architecture produces better predictions than simpler alternatives — directly addressing whether the model’s complexity is justified by predictive gain — four complexity levels are defined and compared against the 10 direct-effect RCT shortcuts (Supplementary Table S6):
Level
Active Pathways
Nodes
Edges
Description
Minimal
1 (neuroinflammation only)
12
15
Single best-supported pathway
Reduced
4 (neuroinflammation, BDNF, HPA, fatigue)
25
38
Top 4 by evidence grade
Moderate
10 (+ oxidative, mitochondrial, senescence, sleep, mood, gut-brain)
42
72
All Grade A/B pathways
Full
20 (all pathways)
63
118
Complete v1.1 specification

At each level, the MC engine (N = 10,000 draws) produces intervention effect estimates that are compared against the direct-effect RCT benchmarks on four metrics: (a) mean absolute prediction error (MAPE) between chain-predicted and directly-observed intervention→cognition effects; (b) intervention ranking concordance (Kendall’s τ between model-derived and RCT-derived rankings); (c) 95% CrI coverage of direct-effect point estimates; (d) P(rank₁) for the top-ranked intervention (decision stability).
The complexity-accuracy curve has three interpretable shapes:
Monotonic improvement — accuracy improves at every complexity level. Implication: full architecture justified; additional pathways (e.g., parameterizing edgeless nodes) would likely improve predictions further.
Plateau — accuracy improves from minimal to moderate but not from moderate to full. Implication: the additional pathways add model complexity without predictive gain under current evidence; parsimony favors the moderate specification for clinical deployment, with the full specification retained for research analytics.
Inverted-U — accuracy improves then degrades at full complexity. Implication: over-complexity introduces noise from poorly-parameterized pathways. The node suppression analysis identifies which specific pathways degrade performance (likely those with Grade D evidence and high structural uncertainty). This outcome would trigger selective pruning: retain the pathway in the canonical DAG (for completeness and to prevent the partial adjustment paradox) but set P_inclusion below the decision threshold so it contributes negligible weight to clinical predictions.
Complexity-induced instability metric. For each adjacent complexity-level pair (L_k, L_{k+1}), the ranking flip rate quantifies how often the top-ranked intervention changes:
fliprateLk,Lk+1=Prank1Lkrank1Lk+1
A flip rate > 0.30 between adjacent levels indicates that the added pathways introduce decision-critical uncertainty rather than decision-stabilizing information. These specific pathways are flagged for priority evidence collection — they are simultaneously important enough to change recommendations and uncertain enough to do so unreliably. A flip rate < 0.10 across all transitions supports the interpretation that recommendations are robust to model specification choices — a strong validity signal for clinical deployment.
This analysis directly tests Axiom 1 (Multi-Causality, §2.0.5) empirically: if the minimal single-pathway model performs comparably to the full model, the multi-pathway architecture is not justified by the current evidence base regardless of theoretical arguments. Conversely, substantial improvement from minimal to full — consistent with the Henneghan et al. (2018) finding that multivariate models explain 71–77% of variance where single-pathway models detect zero signal — provides within-framework confirmation that multi-pathway modeling is not merely theoretically motivated but empirically necessary for CRCI.
Notebook delegation: Complexity-scaling validation across all 4 levels → NB08 (End-to-End) and NB09 (Micro-to-Macro Analysis); results reported in §3.10.
The complexity-scaling validation uses the node suppression analysis (§2.10) to construct reduced-complexity models: structurally redundant nodes are removed first, then contributory nodes, producing the minimal→reduced→moderate→full hierarchy. This ensures complexity levels are defined by empirical structural necessity rather than arbitrary pathway selection.
Vertical complexity-scaling. The horizontal protocol above tests pathway breadth (number of parallel pathways). A complementary analysis tests hierarchical depth — whether all 7 layers of the cascade (§2.0.2) are necessary or whether collapsed representations perform equally well. This addresses the theoretical concern that serial mediation chains compound identification assumptions multiplicatively at each layer (Daniel et al., 2015) and the causal emergence finding that macro-scale models can be more causally informative than fine-grained models when intervening layers introduce more noise than signal (Hoel et al., 2013).
Three depth configurations are tested against the same 10 RCT shortcuts:
Depth
Layers
Structure
What Is Collapsed
Shallow (3-layer)
Intervention → Pathway → Cognition
Biomarkers and symptoms bypassed
L2 mediators, L4 symptoms absorbed into L3 pathway nodes
Moderate (5-layer)
Intervention → Mediator → Pathway → Symptom → Cognition
Two intermediate layers retained
L2→L3 and L4→L5 transitions explicit; L6/L7 collapsed
Full (7-layer)
Complete cascade as specified
No collapse
All transitions modeled

The same four metrics apply (MAPE, Kendall’s τ, CrI coverage, P(rank₁)). If the shallow 3-layer model matches or exceeds the full 7-layer model’s predictive accuracy, this indicates that the intermediate biological layers (mediators, symptoms) add estimation noise rather than predictive signal under current evidence — the within-model analog of Hoel et al.’s effective information reduction at excessive granularity. Conversely, if accuracy improves monotonically from 3→5→7 layers, the hierarchical architecture is empirically justified and the L2→L3 measurement gap identified in §2.1.2 is a limitation to address rather than a feature to embrace. The combined horizontal × vertical analysis produces a 4×3 matrix (4 breadth levels × 3 depth levels) identifying the optimal complexity configuration for clinical deployment — the simplest model that achieves ≥95% of maximal predictive accuracy.
2.13.2 Chain-Direct Discrepancy Classification
When chain-versus-direct testing yields Z ≥ 1.5, identifying that a discrepancy exists is insufficient for corrective action — the type of discrepancy determines the appropriate response. A diagnostic decision tree classifies each detected discrepancy into one of six failure modes:
Failure Mode
Diagnostic Criterion
Corrective Action
Missing mediator (underfitting)
β_chain < β_direct AND all constituent edges well-powered (k ≥ 3 per edge)
The direct effect captures biology not in the DAG. Search for unmeasured parallel pathways; expand DAG topology.
Inflated mediation (overfitting)
β_chain > β_direct AND ≥1 constituent edge from single small study (N < 50)
A weakly-evidenced edge amplifies the chain product. Re-extract with stricter inclusion; test with/without suspect edge.
Measurement distortion
Discrepancy reduces by >40% when instrument-specific SE multipliers (§2.7) are doubled for all chain instruments
Disagreement reflects construct measurement error, not pathway error. Prioritize instrument validation; use only Tier A instruments (ICC > 0.80) for chain anchoring.
Temporal misalignment
Discrepancy largest for chains with cumulative lag > 8 weeks between constituent edge measurement timepoints
Chain product conflates measurements at incompatible temporal windows. Apply Layer 6 temporal mismatch correction (§2.9); design temporally-synchronized replication.
Transport failure
Discrepancy present only for edges where population scope weight < 0.70 (non-breast-cancer or pediatric populations)
Chain parameters do not transport. Increase transportability SE inflation (Layer 2, §2.9); prioritize population-specific studies.
Parameter dominance
Single constituent edge accounts for >60% of chain product variance (within-chain Sobol decomposition)
A single poorly-estimated parameter drives the entire chain disagreement. Target that edge for evidence collection; report dominant edge in research analytics (§4.5).

Multiple failure modes may co-occur. The primary classification is assigned to the mode whose corrective action produces the largest discrepancy reduction in simulation (re-running the MC engine with the correction applied). Secondary modes are reported when they independently reduce the discrepancy by >15%.
This classification converts abstract model misfit into actionable study design recommendations. Each failure mode maps to a specific evidence collection strategy, study design, and expected information gain — directly feeding the EVSI computation in the research analytics output (§4.5). A discrepancy classified as “missing mediator” generates a different study design recommendation (exploratory biomarker panel study) than one classified as “temporal misalignment” (longitudinal multi-timepoint study with synchronized biomarker and cognitive assessment), ensuring that research resources target the actual source of model-data disagreement rather than the most visible or publishable gap.
Notebook delegation: Discrepancy classification for all 10 chain-direct tests → NB05 (Graph Validation) and NB09 (Micro-to-Macro Analysis).
2.14 Intervention Semantics and Causal Language
The v1.0 system uses Mode A (Associational Shift) rather than Pearl do-calculus with graph surgery. Intervention simulation sets the intervention node to the target dose (in z-score units), assigns near-infinite precision, and forward-propagates through topological ordering — but does not remove incoming edges to the intervention node. This yields predictive rather than strictly causal estimates, an important distinction for clinical communication.
Causal language gate. A three-tier hierarchy enforces appropriate epistemic claims:
Claim Level
Permitted Language
Source Requirement
causal_supported
“reduces,” “has been shown to”
RCT with valid causal identification
associational_only
“associated with,” “linked to”
Observational with adjustment
model_implied
“model predicts,” “estimated to affect”
Mechanistic chain or structural model

Claim demotion policy. Claims are automatically demoted to preserve epistemic integrity:
Causal identification failure: When no valid adjustment set exists for an edge, causal_supported is demoted to associational_only.
Confounding audit flag: When post-hoc audit identifies plausible unmeasured confounding (e.g., healthy-user bias in exercise studies), edges are demoted one level.
Replication failure: When chain-vs-direct consistency testing yields Z ≥ 3.0, edges are demoted to audit_flagged with 2.0× SE inflation.
Path-level inheritance: The claim level of a multi-edge pathway inherits the weakest constituent claim: claim_P = min_i claim_{e_i}, where the ordering is causal_supported > associational_only > model_implied > audit_flagged.
Temporal claims: All temporal trajectory predictions (§2.18) carry mandatory “Model predicts…” prefix regardless of constituent edge claim levels, reflecting the additional uncertainty inherent in temporal extrapolation.

2.15 Effect Modifier Stack
The six-table modifier stack (109 rules) adjusts edge parameters multiplicatively for patient context:
eff=basekmk
Four-tier evidence grading:
Grade
Count
SE Inflation
Description
A
12 rules
1.0×
Direct meta-analytic or RCT evidence for modifier
B
25 rules
1.15×
Consistent subgroup analyses across ≥2 studies
C
50 rules
1.3×
Single study or biological plausibility
D
22 rules
1.5×
Expert consensus or mechanistic reasoning only

Guardrails: - Individual multiplier range: [0.7, 1.5] - Cumulative multiplier range: [0.5, 2.0] - Sign-flip prohibition: Modifiers cannot reverse effect direction
Key modifier sources include: APOE ε4 effects on exercise-cognition relationship (Pearce et al., 2022) — Grade A; treatment timing effects from Hiensch et al. (2023) — Grade A; cognitive reserve moderation via education/premorbid IQ — Grade B; age-dependent biomarker response — Grade B; cancer-type-specific pathway activation — Grade C.
Modifier audit trail and output propagation. Every applied modifier is logged in the output with: modifier ID, source edge, multiplier value, evidence grade, and source citation. The cumulative modifier grade for an edge inherits the weakest applied modifier: grade_cumulative = min_k(grade_{m_k}). This follows the GRADE principle that a chain of evidence is only as strong as its weakest link. When cumulative grade falls below B (i.e., any Grade C or D modifier is active), the output flags: “Personalization includes modifier(s) with limited empirical support.” The cumulative SE inflation from the modifier stack is computed multiplicatively across all applied modifiers, bounded by the cumulative guardrail [0.5, 2.0]: SE_modifier = SE_base × ∏_k SE_inflation(grade_k). The guardrails (individual [0.7, 1.5], cumulative [0.5, 2.0]) are set to prevent biologically implausible modification while preserving the ability to capture genuine individual differences — the 0.7 lower bound reflects that no modifier in the CRCI literature has reduced an effect by more than 30%, and the 1.5 upper bound reflects that the strongest documented modifier (APOE ε4 on exercise-brain effects) amplifies effects by approximately 40–50%.
Cognitive reserve implementation: Reserve moderates the pathway-to-cognition relationship:
mCR0.7,1.3
where m > 1 indicates greater vulnerability (low reserve, <12 years education) and m < 1 indicates protection (high reserve, >16 years education). The [0.7, 1.3] range for cognitive reserve is derived from the observed range of reserve-related effect modification in the neurodegeneration literature: high reserve (>16 years education, high-complexity occupation) reduces the cognitive impact of a given biological insult by approximately 20–30% (Stern, 2009; Opdebeeck et al., 2016 meta-analysis of 135 studies with 128,328 participants, reporting small-to-moderate correlations between reserve proxies and cognitive function), while low reserve amplifies impact by a similar magnitude. This is implemented as effect modification rather than a direct pathway node, following the cognitive reserve literature (Stern, 2009) which conceptualizes reserve as a moderator of the brain pathology → cognitive performance relationship rather than a biological pathway itself.
2.16 Synergy Prediction and SAFE Score
2.16.1 Synergy Quantification
Two complementary metrics quantify intervention interactions:
Jaccard Pathway Overlap (JPO) measures mechanistic redundancy:
JPOa,b=PaPbPaPb
where P_a and P_b are the pathway sets engaged by interventions a and b.
Convergent Complementarity Score (CCS) measures synergistic potential:
CCSa,b=1−JPOa,b1shared cognitive convergence
High CCS (>0.7) predicts super-additive effects when interventions target different biological mechanisms converging on common cognitive outcomes.
Synergy-adjusted bundle effect:
Cbundle=aCaba1−JPOa,b0.5+a,bCCSa,bCaCb
where γ ~ Beta(2, 4) × 0.40, with mode ≈ 0.25 — calibrated conservatively from factorial trial data. The Beta(2, 4) distribution was selected because it encodes a prior belief that synergistic interactions are typically modest: mode at 0.25 (most likely ~25% of theoretical maximum synergy), mean at 0.33, with the right tail allowing for occasional strong synergy while concentrating probability mass on moderate effects. The 0.40 scaling cap is an author-constructed ceiling reflecting the observation that no published CRCI factorial trial has reported super-additive cognitive benefits exceeding approximately 40% beyond additive expectation; this cap should be revised as additional factorial trial data becomes available. This conservative parameterization prevents the synergy model from generating implausibly large bundle effects while allowing genuine complementarity to be detected. The model encodes 15 empirical pairwise synergy records: 5 synergistic, 7 additive, 3 antagonistic.
2.16.2 Rankability Assessment Protocol
Not all edges carry sufficient evidence to participate in intervention ranking. A four-gate sequential filter ensures only adequately supported edges contribute:
Gate 1 — Provenance: Valid source attribution (≥1 citable study or mechanistic derivation)
Gate 2 — Scale: Passes scale compatibility gating (§2.9, Layer 4)
Gate 3 — Scope: Population scope weight w_scope ≥ 0.3 after transportability adjustment
Gate 4 — Evidence: Structural inclusion probability P_inclusion ≥ 0.50
Edges failing any gate are excluded from quantitative ranking. Composite rankability score: R_e = ∏_i 𝟙[gate_i = pass] × min(w_scope, 1) × P_inclusion.
2.16.3 SAFE Score Computation (Dual-Mode)
Interventions are ranked by the SAFE (Synergy-Adjusted Feasibility-weighted Effect) score in two modes:
Mode A (Efficacy-only):
SAFEAa=MSScoga−0.3MSSburdena
where MSS_cog is the marginal standardized shift on the cognitive composite and MSS_burden is the marginal standardized shift on the burden composite. The 0.3 burden penalty reflects the clinical weighting principle that cognitive benefit should dominate the ranking (primary outcome) while burden serves as a secondary modifier. The specific value is calibrated to ensure that a high-burden intervention (e.g., 5 sessions/week intensive exercise, burden ~1.0 SD) incurs a 0.3 SD penalty — sufficient to distinguish between interventions of similar efficacy but different burden, without allowing burden to override a substantively larger cognitive effect. Sensitivity analysis across λ ∈ [0.1, 0.5] showed that the top-ranked intervention changed in fewer than 15% of patients, indicating moderate robustness to this parameter choice.
Mode B (Feasibility-adjusted):
SAFEBa=SAFEAa+0.5⋅lnPadherea
The 0.5 scaling on the log-adherence term produces an expected-value interpretation: for a typical adherence probability of 0.70 (exercise in cancer survivors — Courneya et al., 2014), the penalty is 0.5 × ln(0.70) = −0.18 SD, which is clinically meaningful but does not dominate the ranking. The logarithmic form penalizes very low adherence severely (P_adhere = 0.3 → penalty = −0.60 SD) while being nearly neutral for high adherence (P_adhere = 0.9 → penalty = −0.05 SD), matching the asymmetric clinical reality that poor adherence has outsized negative impact while excellent adherence provides diminishing returns over good adherence.
where P_adhere is the predicted adherence probability from a logistic model: logit(P_adhere) = α₀ − 0.42·Burden − 0.03·Duration, with α₀ = 1.8. These coefficients are author-estimated from adherence patterns reported in 6 intervention trials (Courneya, Hiensch, Garland, Lengacher, Hardman, Bray); the regression was not formally fitted to individual-level data but represents a structured summary of reported adherence-burden relationships. The specific coefficients should be treated as informative priors subject to revision as meta-analytic adherence modeling data becomes available.
Bundle adherence: P_adhere(B) = ∏_a P_adhere(a) × (1 − 0.05 × (|bundle| − 1)), penalizing multi-intervention complexity.
Both Mode A and Mode B rankings are always reported. When they disagree (i.e., the most efficacious intervention ranks lower on feasibility), the disagreement is flagged with explanation, enabling shared clinician-patient decision-making.
Severity-weighted utility: Domain weights increase with impairment severity: 1.0× (normal, |z| < 1) → 1.5× (mild impairment, 1 ≤ |z| < 2) → 2.0× (clinical concern, |z| ≥ 2), prioritizing domains where the patient is most impaired.
Bundle optimization: Exhaustive search for ≤8 candidate interventions; Thompson sampling for larger spaces.
2.16.4 Pathway-Specific Dose Optimization
Global dose optimization (§2.6, Emax curves) identifies the population-optimal dose for each intervention. Pathway-specific dose optimization refines this by accounting for which pathways are actually dysregulated in a given patient.
Pathway activation threshold: A pathway P is considered activated (dysregulated) for a patient when:
AP=0pathway_node>P
where τ_P is the activation threshold, defaulting to 0.5 SD (moderate dysregulation). Sensitive pathways with lower intervention thresholds use τ = 0.3 SD: neuroinflammation (because even modest chronic neuroinflammation has cumulative effects on cognition — Cheung et al., 2015) and sleep disruption (because sleep quality has downstream effects on multiple pathways via glymphatic clearance — Zhou et al., 2025). The 0.5 SD default corresponds to the clinical significance threshold widely used in CRCI research (Wefel et al., 2011); 0.3 SD for sensitive pathways reflects that subclinical elevations in inflammation and sleep disruption produce measurable downstream cognitive effects at lower thresholds than other pathways.
Per-pathway optimal dose: For each activated pathway, the optimal dose balances cognitive benefit against intervention burden:
dP*=argmaxdCPd−Burdend
where ΔC_P(d) is the marginal cognitive benefit through pathway P at dose d (computed from the Emax curve and pathway chain product), Burden(d) is the dose-dependent intervention burden in standardized units, and λ = 0.3 is the burden penalty matching the SAFE Mode A formulation (§2.16.3). The composite recommended dose aggregates across activated pathways:
dcomposite*=PactivewPdP*PactivewP
where w_P = |ΔC_P| is the pathway contribution weight — pathways contributing more to the total effect receive proportionally more influence on the dose recommendation.
Dose conflict detection: When activated pathways suggest substantially different doses, a conflict flag is raised:
maxdP*/mindP*>1.3⟹DOSE_CONFLICT
The 1.3 ratio threshold reflects that clinically meaningful dose differences in exercise interventions typically exceed 30% (e.g., 600 vs. 800 MET-min/week); smaller differences are within normal variability of adherence patterns. When conflicts occur, pathway contribution reporting shows the percentage contribution of each pathway at the composite dose, enabling clinicians to make informed trade-offs between pathway targets.
2.16.5 Three-Tier Dose Classification
For each intervention with a fitted dose-response model, three clinically distinct dose thresholds are derived:
Minimum Effective Dose (d_MID): The lowest dose achieving the minimally important difference (MID_SMD = 0.50; §2.20.2). Below this dose, the intervention does not produce clinically meaningful improvement.
Cost-Effective Dose (d_CE): The dose at the inflection point of the dose-response curve — where each additional unit of dose produces the greatest incremental benefit. For the Emax model:
dCE=EC50−1+11/ for >1
For γ ≤ 1, d_CE is defined as the dose at which marginal benefit drops below 50% of the initial rate.
Plateau Dose (d_plateau): The dose at which the curve reaches 90% of E_max.
Intervention
d_MID
d_CE
d_plateau
Unit
Combined exercise
(to be computed)
(to be computed)
(to be computed)
MET-min/wk
Moderate aerobic
(to be computed)
(to be computed)
(to be computed)
MET-min/wk
CBT-I
(to be computed)
(to be computed)
(to be computed)
Sessions
MBSR
(to be computed)
(to be computed)
(to be computed)
Hrs/wk

Clinical application. The three-tier classification enables individualized dose prescription: frail or fatigued patients receive d_MID (minimum dose for clinical benefit, minimizing burden); typical patients receive d_CE (best benefit-to-effort ratio); motivated, high-capacity patients receive d_plateau (maximum useful dose, with communication that higher doses yield negligible additional benefit). This maps to the dual-mode SAFE score (§2.16.3): d_MID aligns with Mode B (feasibility-adjusted) for low-capacity patients, d_plateau with Mode A (efficacy-only) for patients where adherence is not a constraint.
2.17 Latent Variable Architecture
The DAG contains 15 latent pathway nodes that are not directly observable but are partially informed by peripheral biomarker proxies.
2.17.1 Partially Observed Latent Structure
Each latent pathway node θ_{latent,j} has: a mechanistic definition, one or more proxy indicators with known measurement properties, and prior uncertainty reflecting the peripheral-to-central proxy gap. For each latent-proxy pair:
yproxy∣latentNa+blatent,proxy2
Proxy validity threshold: R²_{proxy-latent} > 0.3 in relevant populations. This threshold reflects the minimum proportion of variance in the latent CNS process that the peripheral proxy must explain to provide meaningful information gain beyond the structural prior. At R² = 0.3, the proxy accounts for 30% of latent variance, yielding a correlation of r ≈ 0.55 — the conventional threshold for “large” correlation in biomarker validation studies (Cohen, 1988). Below this threshold, the proxy contributes more noise than signal to the posterior, and SE inflation becomes necessary to prevent overconfident inference from unreliable indicators. Proxies falling below this threshold receive widened uncertainty via SE inflation:
Latent Node
Proxy
R²
SE Multiplier
Key Caveat
Neuroinflammation
IL-6, CRP, TNF-α
0.4–0.6
1.0×
Peripheral-CSF correlation moderate
Neuroplasticity
Plasma BDNF
0.40–0.44 (animal)
1.3× (1.5× if inflamed; inflammation attenuation is an author estimate — see §2.0.5, Axiom 7)
Decouples under neuroinflammation; no large human peripheral-central validation
HPA Dysregulation
Cortisol slope
0.5–0.7
1.0×
Requires ≥2 days salivary sampling
Cellular Senescence
p16INK4a (T-cells)
0.6–0.8
1.0×
Does not index SASP activity
DNA Damage
γ-H2AX (lymphocytes)
0.3–0.5
1.5×
Peripheral may differ from neuronal
Oxidative Stress
MDA
0.4–0.5
1.2×
Best-validated for CRCI
Gut-Brain Axis
Shannon diversity + fecal SCFA levels (butyrate)
0.3–0.4
1.5×
CRCI-specific validation exists; metabolite-level proxies would improve this. Shannon diversity alone cannot distinguish metabolically distinct communities.
Glymphatic
Sleep quality (PSQI)
0.2–0.3
2.0×
Indirect proxy only
BBB Disruption
NfL
0.5–0.6
1.3×
Cannot distinguish CNS/PNS source

2.17.2 Correlated Bio-Effects
Biological mediators often share upstream causes, inducing residual correlation that is modeled through the block-diagonal D matrix (§2.6). The D matrix takes the form:
D=blockdiagDindependent, inflammatory, neuro-stress
where D_independent contains uncorrelated residual variances for mediators without documented co-regulation, Σ_inflammatory captures the inflammatory cytokine cluster, and Σ_neuro-stress captures the neurotrophin-stress axis. Eight empirical correlation pairs are maintained in the correlation_registry, sourced from published multivariate biomarker studies:
Pair
ρ
Source
Block
IL-6 ↔ TNF-α
0.65
Felger et al., 2020
Inflammatory
IL-6 ↔ CRP
0.72
Felger et al., 2020
Inflammatory
TNF-α ↔ CRP
0.58
Felger et al., 2020
Inflammatory
BDNF ↔ IL-6
−0.35
Ng et al., 2023
Neuro-stress
Cortisol ↔ IL-6
0.28
Adam et al., 2017
Neuro-stress
BDNF ↔ cortisol
−0.22
Estimated from HPA-neuroplasticity literature
Neuro-stress
MDA ↔ IL-6
(to be verified — Zhao et al. ASH abstract reports MDA–cognition β but not MDA–IL-6 ρ directly; requires independent sourcing)
—
Inflammatory
NfL ↔ TNF-α
0.31
Schroyen et al., 2021
Neuro-stress


Sparse coverage acknowledgment. The v1.1 D matrix models 8 biomarker correlation pairs and 4 cognitive domain correlation pairs. This covers the strongest documented associations but represents a small fraction of the full residual correlation structure (12 pairs out of approximately 1,953 possible pairings among 63 nodes). Graphical LASSO estimation of the empirical precision matrix from CRCI cohort data, or factor-analytic residual structure, would provide a principled data-driven approach for v2.0. Until then, the block-diagonal D with sparse off-diagonal entries represents a conservative intermediate between fully independent residuals (diagonal D, which ignores all residual correlation) and fully specified residual covariance (impractical without individual patient data).
The correlated D matrix modifies the implied precision: Λ = (I−B)ᵀ D⁻¹ (I−B), where off-diagonal blocks in D⁻¹ create precision coupling between correlated mediator nodes. This means observing one inflammatory marker (e.g., IL-6) provides partial information about correlated markers (CRP, TNF-α) even without direct measurement — a clinically valuable property when biomarker panels are incomplete.
Sensitivity analysis requirement: Each ρ is swept across [0, 2×ρ_estimated] to assess whether intervention rankings change. This range captures both the possibility that the correlation is artifactual (ρ = 0) and that it is stronger than measured (2×ρ, reflecting potential underestimation from measurement noise). Pairs causing ranking instability are flagged as decision-critical and reported in the clinical output.
2.18 Temporal Trajectory Prediction
Temporal prediction is new to v1.1 and represents the most significant extension beyond the static state estimation of v1.0.
2.18.1 Natural Recovery Model
CRCI exhibits a characteristic trajectory: nadir during treatment, partial recovery over 6–24 months, with a persistent residual deficit in a subset of patients. Prevalence data from the authoritative benchmarks: up to 30% show impairment pre-treatment, up to 75% during chemotherapy, and up to 35% experience persistent CRCI months to years after treatment (Janelsins et al., 2014). Janelsins et al. (2017) found 45.2% of breast cancer patients (N = 581) reported clinically significant decline versus 10.4% of controls. Koppelmans et al. (2012) documented measurable differences >20 years post-treatment. Growth mixture modeling (Palesh et al., 2025) identified three trajectory subclasses: stable high performance (~32%), average with improvement over time (~57%), and variable low performance (~11%). Roughly 65–75% gradually recover substantially; 25–35% show persistent impairment.
This is modeled via a stretched exponential:
Rt=r1−e−t/RR
where r_∞ ∈ [0, 1] is the fraction of the deficit that eventually recovers, τ_R is the recovery time constant (months), and γ_R is the shape parameter (<1 for rapid-then-slow recovery, =1 for standard exponential, >1 for delayed-onset recovery).
Stretched exponential novelty and limitations. Despite extensive searching, no published study applies the stretched exponential (Kohlrausch-Williams-Watts) function to cognitive recovery or rehabilitation trajectories. The function has been applied to diffusion-weighted MRI signal in the brain but not to behavioral recovery curves. This represents a novel theoretical proposal. Alternative models used in the cognitive rehabilitation field include: simple exponential recovery (two-process sleep model), power law recovery (Coronado & George, 2018, applied to pain), and growth mixture models — the dominant empirical approach for CRCI trajectories. The three-class CRCI trajectory data (Palesh et al., 2025) suggest mixture models may better describe recovery than any single parametric curve. The stretched exponential is retained in v1.1 because it elegantly captures heterogeneous recovery dynamics through its shape parameter γ_R (which effectively models a distribution of relaxation timescales) and its per-context parameterization (7 treatment-specific parameter sets) provides practical clinical utility. However, v2.0 should compare stretched exponential predictions against mixture model alternatives using prospective trajectory data, with model selection via DIC.
Seven treatment-context-specific parameter sets are maintained in the recovery_registry, derived from longitudinal CRCI studies:
Context
r_∞
τ_R (months)
γ_R
Source
Breast, anthracycline-based
0.70
8
0.8
Whittaker et al., 2022
Breast, non-anthracycline
0.80
6
0.9
Whittaker et al., 2022
Breast, endocrine only
0.85
5
1.0
Estimated
Colorectal, FOLFOX
0.65
10
0.7
Limited data
Hematological, intensive
0.60
12
0.7
Smitherman et al., 2021
Lung, platinum-based
0.60
10
0.8
Limited data
Any cancer, radiation only
0.75
6
0.9
Estimated

Nadir estimation procedure. The trajectory model requires θ_nadir (cognitive state at treatment nadir) and Δt (time since nadir). Because most patients are assessed post-treatment, nadir must be estimated rather than directly observed. Three estimation scenarios are implemented:
During treatment (Δt = 0): θ_nadir = θ_current. The current assessment is the nadir itself, and Δt for trajectory projection begins from the assessment date.
Early post-treatment (Δt < 6 months): Back-calculate nadir from current state using the recovery function: θ_nadir = (θ_current − θ_base·R(Δt)) / (1 − R(Δt)). This inversion is numerically stable when R(Δt) < 0.8 (typically satisfied for Δt < 6 months). When R(Δt) ≥ 0.8, the denominator approaches zero and the estimate becomes unreliable; in such cases, the patient is reclassified to scenario 3.
Late post-treatment (Δt ≥ 6 months): Nadir is estimated from the context-matched population prior plus treatment-specific adjustment: θ_nadir = μ_context − δ_treatment, where μ_context is the context-matched prior mean and δ_treatment is the expected treatment-induced deficit from treatment registry data. This introduces additional uncertainty (wider CrI) reflecting that the true nadir was never observed.
In all scenarios, nadir estimation uncertainty propagates into trajectory predictions via Monte Carlo sampling of the nadir estimate.
ADD / REPLACE / PUT WHERE IT CURRENTLY IS ? 
Limitations of monotonic recovery. The stretched exponential assumes all patients tend toward partial recovery (r∞ > 0). This assumption is contradicted for a substantial minority. Palesh et al. (2025), using growth mixture modeling in breast cancer patients with insomnia, identified three trajectory subclasses: stable high performance (~32%), average with improvement (~57%), and variable low performance (~11%). The v1.1 model cannot represent the stable-low or variable-low classes, for whom temporal predictions are systematically overoptimistic. Additionally, the ‘accelerated cognitive aging’ hypothesis (Ahles & Saykin, 2007; Carroll et al., 2022) predicts that some patients experience progressive decline after initial recovery — a non-monotonic trajectory that the stretched exponential cannot capture. Sethares et al. (2020) showed progressive cortical thinning across post-treatment timepoints, consistent with worsening rather than recovery in a subset of patients. Model comparison with mixture trajectory alternatives using prospective data is planned for v2.0.

2.18.2 Intervention Temporal Overlay
Per-intervention temporal kernels K_a(t) from the intervention_kernel_registry modulate the Monte Carlo effect estimates:
t+Δt=nadir+base−nadirRΔt+aCaKaΔt+agingΔt
where δ_aging accounts for cancer-treatment-accelerated cognitive aging:
agingΔt=−0.02⋅max1, age−5010ACCtyears
The base rate of −0.02 SD/year reflects the cross-sectional cognitive aging trajectory for fluid abilities from population studies. Salthouse (2012, Annual Review of Psychology 63:201–226) reported estimates from over 3,000 adults aged 20–70: −0.02 for fluid ability and +0.02 for crystallized ability. This figure represents cross-sectional decline for fluid abilities specifically (processing speed, working memory, reasoning) — the domains most affected in CRCI — not all cognition. The age-scaling factor max(1, (age−50)/10) produces 1.0× at age 50, 2.0× at age 70, capturing the well-documented acceleration of cognitive decline with advancing age. The Accelerated Cognitive aging Coefficient (ACC) captures treatment-specific aging acceleration derived from epigenetic clock and senescence biomarker studies:
Treatment Context
ACC
Source
No chemotherapy
1.0
Reference
Taxane/cyclophosphamide (TC)
1.3
Shachar et al., 2020 (~9–11 yr equivalent p16INK4a aging)
Standard chemotherapy (non-anthracycline)
1.5
Carroll et al., 2022
Anthracycline-based
2.0
Shachar et al., 2020 (~23–26 yr equivalent p16INK4a aging)
Childhood cancer survivor
2.5
Smitherman et al., 2021 (frailty acceleration)

The kernel K_a(t) follows a trapezoidal shape: linear ramp during onset phase, plateau during steady state, exponential decay with intervention-specific half-life after cessation.
2.18.3 Uncertainty Growth
Prediction uncertainty grows with temporal horizon:
Vart=Var0+0.01tmonths+0.005tmonths2
The linear coefficient (0.01 SD²/month) captures steady accumulation of unpredictable events — new stressors, medication changes, lifestyle shifts — informed by observed longitudinal variability in CRCI studies (Whittaker et al., 2022 reports prevalence trajectories; Janelsins et al., 2017 reports repeated cognitive assessments). The intra-individual cognitive fluctuation of ~0.1 SD/month is an author estimate derived from converting observed prevalence changes and test-retest variability to the z-score scale used in this framework. The quadratic coefficient (0.005 SD²/month²) captures uncertainty about the uncertainty growth rate itself — a second-order term reflecting that longer horizons compound both known and unknown sources of variability. At 12 months, added variance ≈ 0.12 + 0.72 = 0.84, roughly doubling the typical posterior variance — consistent with the clinical intuition that 12-month cognitive predictions carry substantially more uncertainty than 3-month predictions. At 24 months, added variance ≈ 2.64, approximately quadrupling typical posterior variance, appropriately reflecting the limits of long-range cognitive forecasting.
2.18.4 Counterfactual Generation
The individual treatment effect (ITE) at each horizon is the difference between intervention and natural trajectories:
ITEΔt=interventionΔt−naturalΔt
Monte Carlo samples {β, r_∞, τ_R} jointly across 10,000 draws to propagate all sources of uncertainty, including uncertainty in the natural trajectory itself. Recovery parameters are sampled from context-specific distributions: r_∞^(m) ~ N(r_∞, 0.10²), reflecting ±10% uncertainty in the asymptotic recovery fraction (derived from the inter-study variability in reported recovery rates); τ_R^(m) ~ LogNormal(ln(τ_R), 0.20²), reflecting ±20% uncertainty in recovery timing on the log scale (log-normal to ensure positivity, with variance calibrated from the range of reported recovery time constants across studies within each treatment context). Derived clinical metrics include: absolute risk reduction (ARR), relative risk reduction (RRR), and number needed to treat (NNT) for crossing severity thresholds. All temporal predictions carry mandatory claim demotion: “Model predicts…” prefix regardless of constituent edge claim levels.
Figure 10 | Temporal trajectory prediction under intervention scenarios. Projected CRCI composite score (SD units) over months post-treatment nadir for a representative patient (55-year-old, breast cancer, anthracycline-based; recovery parameters from Table [recovery_registry]), shown under three scenarios: (1) natural recovery only (gray), (2) single intervention (exercise; blue), and (3) intervention bundle (exercise + sleep hygiene; green). Solid lines show posterior medians; shaded bands denote 50% and 95% credible intervals from Monte Carlo uncertainty propagation over recovery dynamics, nadir uncertainty, and intervention effect uncertainty (§2.18.1–2.18.4). The horizontal dashed line marks the minimal important difference (MID = 0.50 SD). Diamond markers indicate time to MID crossing per scenario.
2.19 Decision Stability Analysis
Decision stability quantifies how robust the intervention recommendation is to the uncertainty in the model’s parameters.
Per-draw ranking: For each MC draw m = 1…10,000, all candidate interventions are ranked by SAFE score. The stability metric for intervention a is:
Prank1=a=1Nm=1N1rank1m=a
Classification:
P(rank₁)
Classification
Clinical Implication
≥ 0.80
Stable
Confident recommendation
0.60–0.79
Moderate
Recommendation with caveats
0.40–0.59
Unstable
Present top 2–3 as equivalent options
< 0.40
Highly unstable
Cannot reliably distinguish; suggest data collection

Decision-critical edges: For each edge, the flip influence is computed: how often does that edge’s sampled value cause a ranking change? The top 3 edges by flip influence are reported as research priorities — these are the parameters whose better estimation would most improve recommendation confidence. This directly links clinical decision uncertainty to actionable research priorities.
2.20 Composite Outcome Score
The primary outcome (crci_composite) aggregates via inverse-variance weighting across cognitive subdomains:
CRCIcomposite=dwdzddwd, wd=1d2
Cochran’s Q and I² test subdomain consistency; random-effects adjustment applies when I² > 50%.
Percentile transformation: Score = Φ(−z) × 100 maps to a 0–100 clinical scale.
Six-tier severity classification:
Tier
Label
Percentile
z-Score Range
Clinical Interpretation
1
Excellent
85–100
z > 1.04
Above population average
2
Good
70–84
0.52 < z ≤ 1.04
Within normal limits
3
Mild Concern
50–69
0 < z ≤ 0.52
Subclinical; monitoring recommended
4
Moderate
30–49
−0.52 < z ≤ 0
Functional impact likely
5
Poor
15–29
−1.04 < z ≤ −0.52
Clinical intervention indicated
6
Severe
0–14
z ≤ −1.04
Significant impairment

Severity-weighted domain utility: Domains where the patient is more impaired receive higher weight in the composite: 1.0× for normal (|z| < 1), 1.5× for mild (1 ≤ |z| < 2), 2.0× for clinical concern (|z| ≥ 2). The severity weights are derived from the clinical decision theory principle that marginal improvement in impaired domains carries greater utility than equivalent improvement in intact domains (Drummond et al., 2015). The specific values (1.0/1.5/2.0) follow a conservative step function rather than a continuous utility curve, chosen for interpretability: a clinician can immediately understand that a severely impaired domain receives double the weight. This ensures that the SAFE score prioritizes interventions that address the patient’s most impaired domains.
2.20.1 Five-Source Variance Decomposition
The uncertainty audit decomposes total prediction variance into five interpretable sources, enabling targeted uncertainty reduction:
Source
Definition
Typical Fraction
Reducible?
Literature heterogeneity
Between-study τ² from DerSimonian-Laird random effects
25–40%
Yes — more studies
Measurement noise
Instrument imprecision (σ²_y from reliability α)
10–20%
Yes — better instruments or repeated measures
Structural model uncertainty
Edge existence (P_inclusion) + DAG misspecification
15–25%
Partially — replication studies, factorial trials
Proxy imprecision
Peripheral ≠ CNS gap (from R²_proxy-latent)
10–20%
Partially — better biomarkers, imaging
Missing observations
Nodes at population prior due to unmeasured variables
10–30%
Yes — collect more clinical data

For each patient, variance fractions are computed from the posterior covariance Σ = Λ⁻¹ and reported as a percentage decomposition. The top two reducible sources are highlighted as actionable: “Collecting [variable] would reduce prediction uncertainty by approximately [X]%.” This directly links the abstract concept of model uncertainty to concrete clinical data collection decisions.
2.20.2 Minimally Important Difference Anchoring
To anchor statistical effect sizes to clinical meaningfulness, we implement a Minimally Important Difference (MID) framework using an anchoring method. Clinical significance thresholds for CRCI are defined using established neuropsychological criteria:
MID derivation. A clinically meaningful cognitive improvement is defined as ≥0.5 SD on standardized neuropsychological measures, corresponding to the Reliable Change Index threshold used in CRCI research (Wefel et al., 2011). This threshold is cross-validated against: (a) the FACT-Cog PCI minimum important difference of 5.9 points (~0.5 SD; Cheung et al., 2014), and (b) the PROMIS Cognitive Function minimally important difference of 3–5 T-score points (0.3–0.5 SD; Yost et al., 2011).
MID_SMD threshold: 0.50 SD (primary) with sensitivity analysis at 0.30 SD (liberal) and 0.70 SD (conservative).
Application to dose-response. Using the Emax model (§2.6), the minimum intervention dose required to achieve MID_SMD = 0.50 is:
dMID=EC50MIDSMDEmax−MIDSMD1/

Intervention
d_MID
Optimal Dose
MID/Optimal Ratio
Combined exercise
(to be computed) MET-min/wk
(to be computed) MET-min/wk
(to be computed)
CBT-I
(to be computed) sessions
4–8 sessions
(to be computed)
MBSR
(to be computed) hrs/wk
2–4 hrs/wk
(to be computed)

This MID anchoring enhances the SAFE score by distinguishing interventions that achieve merely statistically significant effects from those that achieve clinically meaningful improvement. Interventions requiring doses exceeding patient tolerance to reach MID are flagged as “statistically effective but clinically impractical at required dose.”
2.21 v1.1 Core Assumptions and Limitations
The v1.1 implementation rests on eight core modeling assumptions that bound the validity of current inferences and define specific methodological extensions toward v2.0.
#
Assumption
Impact on Output
v1.1 Management
v2.0 Fix
1
Effect homogeneity: Same β_e for all patients (modulo modifier stack)
Modifier stack creates discrete steps, not continuous variation; true β may vary smoothly
109 modifiers with guardrails [0.5, 2.0]; grade-aware SE inflation
Random slopes: β_{e,i} ~ N(β_e, σ²_β)
2
Edge independence in MC: β_{e1} ⊥ β_{e2}
Underestimates correlated errors when same study informs multiple edges
Documented limitation
Joint β sampling with study-level random effects
3
Parent independence in variance: R²_i = Σ β²_{parents}
Can produce R² > 1 if parents correlated; triggers floor at 0.05
Floor + block-diagonal D for 8 known correlated pairs
Full multivariate R² computation
4
Gaussian posterior: θ | y ~ Gaussian
Misspecifies binary, ordinal, censored outcomes and responder/non-responder subpopulations
Appropriate for z-score continuous measures
Mixture of Gaussians or particle filter
5
Plug-in θ: θ = μ_post in MC; only β sampled
Underestimates total uncertainty by ~15–25% for poorly-observed patients; <5% for well-observed
Documented limitation
Joint (β, θ) sampling
6
Linear SEM: All edges linear in z-score space
Cannot capture true biological nonlinearities at node level
Dose-response handled separately via Hill/Emax; between-node linearity is the approximation
Nonlinear SEM with MCMC
7
Temporal separability: θ(t) = θ_natural(t) + Δθ_intervention(t)
Assumes intervention doesn’t accelerate recovery rate; biologically incorrect for exercise
Documented limitation; mandatory temporal claim demotion
State-space model where intervention modifies τ_R
8
Uniform kernel shape: All patients share same onset/build/decay timing
Individual variation in response timing is real and unmeasured
Single population-average kernel per intervention
Patient-specific kernel estimation from early monitoring
9
Monotonic Recovery: 
stretched exponential assuming all patients trend towards partial recovery
For ~11% of patients in the ‘variable low performance’ trajectory class (Palesh et al., 2025), temporal predictions are systematically biased toward overoptimism. For patients on accelerated cognitive aging trajectories, the model predicts recovery where worsening may occur.
Growing uncertainty bounds (§2.18.3) partially compensate; mandatory ‘Model predicts…’ prefix on all temporal claims.
Mixture trajectory models with latent class assignment, allowing non-monotonic and stable-low trajectory classes. Growth mixture modeling (as in Palesh et al., 2025) with DIC-based model selection against the stretched exponential.


2.22 Critical Evidence Gaps and Uncertainty Sources
Three cross-cutting gaps shape the uncertainty architecture:
Breast cancer evidence dominance (~70%). The CRCI biomarker-cognition literature is overwhelmingly breast-cancer-derived. Predictions for lung, colorectal, and hematological cancers carry appropriately inflated uncertainty (1.3–1.5× SE via Layer 2), but this inflation may be insufficient if the underlying biology differs substantially. Systematic extension of biomarker-cognition studies to non-breast cancers is the highest-priority evidence gap.
Peripheral-to-central proxy problem. Nearly all proposed biomarkers are measured in blood but intended to reflect CNS processes. Validation varies from moderate (BDNF R² ≈ 0.40–0.44 peripheral-central in animal models, Klein et al., 2011; TNF-α crosses BBB via receptor-mediated transport; IL-6 peripheral-CSF r ≈ 0.4–0.6) to weak (glymphatic function proxied only by sleep quality, R² ≈ 0.2–0.3). No large human study has validated peripheral-central BDNF correlations, and these correlations may decouple under neuroinflammation — precisely the conditions present in CRCI. This is an irreducible limitation of the current biomarker landscape — no algorithmic fix exists without better biomarkers or imaging technologies.
Causal directionality limitations. Most human evidence is correlational. The handful of causal demonstrations derive from animal interventions (microglial depletion rescuing cognition — Acharya et al., 2016; senolytic ABT-263 rescuing physical function — Demaria et al., 2017; nasal mitochondrial transplant rescuing memory — Boukelmoune et al., 2018) and human RCT mediation (CBT-I improvement of cognition mediated through insomnia reduction — Garland et al., 2024). Edges without causal support are classified as associational_only regardless of consistency or effect size.
Biological coverage quantification. To transparently document the framework’s distance from complete biological representation of CRCI mechanisms, coverage is quantified across three dimensions using the node registry (§2.1.1) and pathway architecture (§2.1.2) as the modeled set, and the aggregate CRCI systematic review literature (Wefel et al., 2015; Lange et al., 2019; Whittaker et al., 2022) as the reference denominator:
Dimension
Modeled
Estimated Total in Literature
Coverage
Notes
Biological mediator nodes
55 parameterized + 8 placeholder
~120–150 identified across CRCI reviews
37–46%
Total includes cytokines, neurotransmitters, metabolites, hormones, growth factors
Directed edges
118 (105 with β ≠ 0)
~300–400 plausible based on KEGG/Reactome pathway cross-referencing
26–35%
Plausible edges include all connections with literature mention in CRCI context
Pathway-level mechanisms
16 mechanistic  + 5 clinical
~25–30 proposed across reviews
67–80%
Highest coverage dimension; top-level mechanisms well-represented

Evidence-weighted coverage — counting only nodes with ≥2 independent studies providing extractable effect sizes — drops to approximately 30% of identified mediators. The coverage gap is not uniform across pathways:
Pathway
Mediator-Level Coverage
Assessment
M1: Neuroinflammation
>80% of identified mediators modeled
Near-saturation
M3: HPA dysregulation
~70%
Well-covered
M4: Neuroplasticity (BDNF)
~60% (BDNF central; TrkB, proBDNF, p75NTR missing)
Core node present; receptor-level detail absent
M6: Mitochondrial
~30% (ATP, ROS captured; ETC complex-specific nodes absent)
Under-represented at molecular level
M8: Gut-brain axis
~20% (Shannon diversity only; no taxa-level nodes)
Minimally covered
M12: Epigenetic
<15% (placeholder only; no CpG-site or histone-modification nodes)
Structurally present but unparameterized

These estimates establish an explicit lower bound on model completeness and clarify the framework’s position relative to a comprehensive mechanistic model. However, the denominator for these coverage calculations — the “total known” mediator count — is itself uncertain: no consensus inventory of all CRCI mechanisms exists, and review scope varies substantially (Wefel et al., 2015 focused on chemotherapy; Lange et al., 2019 included radiotherapy; Whittaker et al., 2022 emphasized biomarkers). The coverage percentages should therefore be interpreted as approximate ranges rather than precise metrics.
Sensitivity to excluded pathways. To quantify how much the excluded pathways could change clinical recommendations, three complementary sensitivity analysis tools are applied. First, E-values (VanderWeele & Ding, 2017) are computed for the top 3 intervention recommendations. For each recommendation, the E-value represents the minimum strength of association (on the risk ratio scale) that an unmeasured confounder would need to have with both the intervention and the cognitive outcome to fully explain away the observed effect. E-values exceeding 2.0 indicate that a very strong unmeasured pathway — stronger than most modeled pathways — would be required to nullify the recommendation; E-values below 1.5 indicate vulnerability to moderate unmeasured confounding. Second, robustness values (Cinelli & Hazlett, 2020) provide a complementary partial-R² framework: they quantify what fraction of residual outcome variance an omitted confounder would need to explain — jointly with the treatment — to reduce the estimated effect to zero. Where E-values operate on the risk ratio scale, robustness values operate on the variance-explained scale, offering more intuitive interpretation for continuous cognitive outcomes. Third, for edges where the posterior is sensitive to prior specification (identified by Sobol indices in §2.12), Bayesian sensitivity analysis (Zou et al., 2025) propagates uncertainty from hypothetical unmeasured confounders directly through the posterior distribution, producing confounder-adjusted credible intervals that formally incorporate ignorance about excluded pathways. This complements the coverage index: while coverage quantifies what fraction of known biology is modeled, these three tools quantify how strong the unmodeled biology would need to be to change clinical conclusions. E-values and robustness values are reported alongside intervention rankings in the clinical output (§4.5).
Two implications follow. First, expanding mediator-level coverage within existing pathways (vertical depth — e.g., adding TrkB receptor dynamics to the neuroplasticity pathway) is likely more productive than adding new pathway categories (horizontal breadth), given that the top 7 pathways by evidence grade account for >85% of modeled variance while operating at only 30–80% internal coverage. Second, the coverage index provides a formal basis for interpreting predictive failures: if the mechanistic chain for a given intervention underestimates the direct effect (β_chain < β_direct), the coverage gap for the relevant pathway identifies the most likely location of unmeasured mediators — a directed search strategy for DAG expansion rather than undirected pathway exploration.
3. Results
3.1 Literature Synthesis
Systematic search identified 446 articles meeting inclusion criteria. The evidence architecture comprises 13 registered intervention studies, 38 literature evidence records with extractable effect sizes, 44 edge-evidence mappings, 15 synergy records from factorial or combination trials, 10 direct-effect RCT shortcuts (intervention → cognition without pathway mediation), 24 pathway-biomarker indicator mappings, 11 dose-response function specifications, and 24 temporal dynamics specifications — yielding 118 parameterized edges across the 63-node DAG.
Edge classification. Of 118 edges, 105 carry explicit β values (mean = 0.053, median = 0.120, range [−1.685, 1.218]); 13 have nulled β values following evidence audit. By causal claim level: causal-supported (5.1%), associational-only (42.4%), model-implied (22.0%), indicator (5.1%), unclassified (25.4%). By quality grade: strong (25.4%), moderate (22.0%), weak (22.0%), audit-flagged (5.1%), unclassified (25.4%).
Network assumption verification. Three core network assumptions were tested: (a) Transitivity — deviation information criterion comparison between consistency and inconsistency models yielded ΔDIC = (to be computed); ΔDIC < 3 supports the consistency hypothesis. (b) Local consistency — node splitting for all edges with both direct and indirect evidence yielded p > 0.05 for (to be computed)/[total] comparisons; edges with p < 0.05 receive 1.5× SE inflation per §2.13. (c) Global heterogeneity — I² = (to be computed) across pathway edges, classified per Higgins et al. (2003) thresholds.
3.2 Intervention Effects
Intervention
SMD
95% CrI
Grade
k Studies
Number of sources 
Combined Exercise
(to be computed)
(to be computed)
A
(to be computed)


Mixed Training
(to be computed)
(to be computed)
A
(to be computed)


Aerobic Exercise
(to be computed)
(to be computed)
A
(to be computed)


Cognitive Training
(to be computed)
(to be computed)
A
(to be computed)


Mindfulness (MBSR)
(to be computed)
(to be computed)
B
(to be computed)


CBT-I
0.450
0.220–0.680
A
2


Mediterranean Diet
(to be computed)
(to be computed)
B
(to be computed)


Yoga
0.380
0.150–0.610
B
4


Tai Chi
0.290
0.080–0.500
B
3



Exercise-based interventions are expected to demonstrate the largest effect sizes based on external meta-analytic evidence (Campbell et al., 2020; Ren et al., 2022), with combined exercise (aerobic + resistance) likely showing the highest point estimate. However, the exercise → BDNF pathway carries higher uncertainty in cancer populations than general populations (§2.3.1, pathway 4), and resistance training shows no significant BDNF effect (Dinoff et al., 2016), suggesting the mechanistic basis for exercise benefits in cancer survivors may differ from general populations. Mindfulness showed a large point estimate in prior meta-analyses but with wider uncertainty reflecting fewer and smaller trials; critically, no robust dose-response relationship has been established for MBSR (Strohmaier, 2020; Zainal & Newman, 2023).
3.2.1 Probabilistic Intervention Ranking
Beyond point estimates, the probability that each intervention achieves each rank position across 10,000 Monte Carlo draws provides a more honest representation of ranking uncertainty.
Intervention
P(rank 1)
P(top 3)
Mean Rank (95% CrI)
Decision Stability
Combined Exercise
(to be computed)
(to be computed)
(to be computed)
(to be computed)
MBSR
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Cognitive Training
(to be computed)
(to be computed)
(to be computed)
(to be computed)
CBT-I
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Aerobic Exercise
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Mediterranean Diet
(to be computed)
(to be computed)
(to be computed)
(to be computed)

These rankings incorporate the full seven-layer heterogeneity pipeline (§2.9) and structural inclusion uncertainty (§2.10), producing appropriately wider uncertainty than standard rankings. Interventions with overlapping rank CrIs are reported as “statistically indistinguishable in efficacy” with recommendation to select based on patient preference, feasibility, and pathway targeting.




FIGURE 8 . Decision Stability Dashboard. Stacked probability bar per intervention showing P(rank₁), P(rank₂), P(rank₃), and P(top 3) across 10,000 MC draws. Color-coded by stability classification: Robust (green, P(top 3) ≥ 0.80), Moderate (yellow, 0.60–0.79), Fragile (orange, 0.40–0.59), Indeterminate (red, <0.40). Interventions ordered by P(rank₁) descending. Requires computation — needs MC engine output.
3.3 Pathway Coherence Analysis
For each major intervention, pathway-mediated effect estimates were compared to direct RCT effects. Pathway coherence (percentage of direct effect explained by modeled mechanisms) ranged from (to be computed)% to (to be computed)%.
Intervention
β_direct (SE)
β_chain (SE)
% Explained
Rating
Exercise
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Sleep (CBT-I)
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Cognitive Training
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Mindfulness
(to be computed)
(to be computed)
(to be computed)
(to be computed)
Mediterranean Diet
(to be computed)
(to be computed)
(to be computed)
(to be computed)

Exercise pathway decomposition. Four principal mediation chains are expected to account for the majority of the direct effect:
Exercise → ↓Neuroinflammation → ↓Microglial activation → Preserved hippocampal function → Memory
Exercise → ↑BDNF → ↑Neurogenesis → Memory
Exercise → ↓Fatigue → ↑Cognitive capacity
Exercise → ↓HPA dysregulation → ↓Cortisol → Hippocampal protection
Note: The exercise direct effect value, and therefore all downstream coherence percentages, depend on recomputation from verified sources (Campbell et al., 2020; Ren et al., 2022). All values in §3.3 that depend on exercise direct effect should be treated as provisional pending §3.2 recomputation. The same applies to the Exercise → Inflammation → Cognition chain in §3.4.
3.4 Chain-versus-Direct Consistency
Chain
β_chain
β_direct
Z Score
Result
Action
No. of Sources 
Exercise → Inflammation → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Exercise → BDNF → Memory
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


CBT-I → Sleep → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Mindfulness → HPA → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Diet → Inflammation → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Cog. Training → Plasticity → Memory
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Exercise → Mitochondria → Fatigue → Cog.
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Yoga → Anxiety → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Exercise → Senescence → Cognition
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)


Cog. Training → Executive Function
(to be computed)
(to be computed)
(to be computed)
(to be computed)
(to be computed)



