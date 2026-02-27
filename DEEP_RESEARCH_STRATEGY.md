# CRCI Deep Literature Research Strategy

**Purpose:** Systematic search strategy to maximize evidence yield for all 64 nodes,
143 edges, and 21 pathways in the CRCI Bayesian Causal Model. Organized by
pathway, with exact search queries, database targets, and prioritization logic.

**How to use this document:**
1. Work through **Tier 1 (Critical)** searches first — these fill the highest-evidence edges
2. Then **Tier 2 (Important)** — these fill moderate-evidence and emerging pathways
3. Then **Tier 3 (Emerging)** — placeholder/edgeless pathways needing any evidence at all
4. Each section has **PubMed**, **Google Scholar**, **Scopus/Web of Science**, and **Deep Research AI** queries
5. Within each pathway, searches are ordered: **meta-analyses → RCTs → prospective cohort → cross-sectional**

---

## Table of Contents

- [Part 1: Master Search Principles](#part-1-master-search-principles)
- [Part 2: Per-Pathway Search Batteries](#part-2-per-pathway-search-batteries)
  - [Tier 1 — High Evidence Pathways](#tier-1--high-evidence-pathways)
  - [Tier 2 — Moderate Evidence Pathways](#tier-2--moderate-evidence-pathways)
  - [Tier 3 — Emerging / Placeholder Pathways](#tier-3--emerging--placeholder-pathways)
- [Part 3: Cross-Cutting Searches](#part-3-cross-cutting-searches)
- [Part 4: Instrument & Norms Searches](#part-4-instrument--norms-searches)
- [Part 5: Dose-Response & Temporal Kernel Searches](#part-5-dose-response--temporal-kernel-searches)
- [Part 6: Effect Modifier Searches](#part-6-effect-modifier-searches)
- [Part 7: AI Deep Research Prompts](#part-7-ai-deep-research-prompts)
- [Part 8: Search Execution Checklist](#part-8-search-execution-checklist)

---

## Part 1: Master Search Principles

### 1.1 What We Need Per Edge

For each of the 143 edges in the EDGE_REGISTRY, we ideally need:

| Data Type | What to Extract | Priority |
|-----------|-----------------|----------|
| **β (effect size)** | Standardized mean difference, correlation, OR, HR | CRITICAL |
| **SE (standard error)** | CI bounds, p-value, sample sizes to derive SE | CRITICAL |
| **n (sample size)** | Per-arm or total | HIGH |
| **Population** | Cancer type, treatment phase, demographics | HIGH |
| **Design** | RCT > prospective > cross-sectional > preclinical | HIGH |
| **Dose-response** | EC50, Hill coefficient, threshold, Emax | MODERATE |
| **Temporal kernel** | Onset latency, peak, decay half-life | MODERATE |
| **Effect modifiers** | Age × effect, APOE × effect, sex × effect | MODERATE |
| **Instrument used** | Exact neuropsych test, biomarker assay | FOR NORMALIZATION |

### 1.2 Database Strategy

| Database | Best For | Access Method |
|----------|----------|---------------|
| **PubMed / MEDLINE** | Biomedical literature, MeSH-based precision | E-utilities API, web |
| **Google Scholar** | Broad coverage, citation mining, gray lit | Web search |
| **Scopus** | Citation networks, conference proceedings | API or web |
| **Web of Science** | Impact metrics, field-specific clustering | Web |
| **Cochrane Library** | Systematic reviews, RCTs | Web |
| **ClinicalTrials.gov** | Active/completed trial data | API |
| **bioRxiv / medRxiv** | Preprints (especially emerging pathways) | API |
| **OpenAlex** | Open-access metadata, citation links | API |
| **Semantic Scholar** | AI-ranked relevance, citation context | API |

### 1.3 Population Filters (Apply Everywhere)

```
PubMed: ("cancer survivors"[MeSH] OR "neoplasms"[MeSH] OR "cancer patients" OR 
         "breast cancer survivors" OR "chemotherapy-related" OR "cancer treatment")

Google Scholar: "cancer survivors" OR "cancer patients" OR "breast cancer" OR 
                "chemotherapy" OR "cancer treatment"
```

### 1.4 Design Hierarchy Filters

For maximum extraction value, append these filters to find highest-quality designs first:

```
TIER A (append first): AND (meta-analysis[pt] OR systematic review[pt] OR "systematic review" OR "meta-analysis")
TIER B (if < 5 results): AND (randomized controlled trial[pt] OR "randomized" OR "RCT")  
TIER C (if < 3 results): AND ("prospective" OR "longitudinal" OR "cohort study")
TIER D (last resort):    AND ("cross-sectional" OR "observational" OR "correlational")
```

### 1.5 Date Range Strategy

- **Primary sweep:** 2010–2026 (bulk of CRCI-specific literature)
- **Classic sweep:** 2000–2009 (foundational papers, normative data)
- **Emerging sweep:** 2022–2026 (newest evidence for placeholder pathways)

---

## Part 2: Per-Pathway Search Batteries

### Tier 1 — High Evidence Pathways

These pathways have SE multiplier 1.0 (highest confidence). Search to find
additional confirming evidence, dose-response parameters, and subgroup analyses.

---

#### PW_M01: Neuroinflammation (11 edges, SE×1.0, Grade A)

**Target edges:**
- ER_CHEMO_IL6, ER_CHEMO_CRP, ER_CHEMO_TNF (chemo → inflammation)
- ER_IL6_OIC, ER_CRP_OIC, ER_TNF_OIC (biomarker → pathway)
- ER_OIC_PROCSPEED, ER_OIC_WORKMEM, ER_OIC_EPISODIC, ER_OIC_ATTNSUST (pathway → cognition)
- ER_OIC_FATIGUE, ER_OIC_DEPRESSION, ER_OIC_PAIN (pathway → symptoms)

**PubMed queries:**

```sql
-- META: Inflammation → Cognition in Cancer
("neuroinflammation" OR "inflammatory markers" OR "cytokines" OR "interleukin-6" 
OR "C-reactive protein" OR "tumor necrosis factor") 
AND ("cognitive impairment" OR "cognitive dysfunction" OR "chemobrain" OR "chemo brain" 
OR "CRCI" OR "cancer-related cognitive") 
AND (meta-analysis[pt] OR systematic review[pt])

-- RCT: IL-6 change → cognitive change
("interleukin-6" OR "IL-6" OR "CRP" OR "C-reactive protein" OR "TNF-alpha") 
AND ("cognitive function" OR "neuropsychological" OR "processing speed" OR "memory" 
OR "executive function") 
AND ("chemotherapy" OR "cancer treatment") 
AND (randomized controlled trial[pt] OR "randomized")

-- DOSE-RESPONSE: IL-6 levels and cognitive performance
("interleukin-6" OR "IL-6") AND ("dose-response" OR "concentration" OR "threshold") 
AND ("cognitive" OR "neuropsychological") AND ("cancer" OR "chemotherapy")

-- MECHANISTIC: Chemotherapy → cytokine elevation magnitude
("chemotherapy" OR "anthracycline" OR "taxane" OR "cyclophosphamide") 
AND ("interleukin-6" OR "IL-6" OR "CRP" OR "TNF") 
AND ("increase" OR "elevation" OR "change" OR "trajectory") 
AND ("cancer patients" OR "breast cancer")
```

**Google Scholar queries:**
```
"chemotherapy-related cognitive impairment" "interleukin-6" meta-analysis
"neuroinflammation" "processing speed" "cancer survivors" effect size
"IL-6" "cognitive decline" "chemotherapy" longitudinal
"cytokines" "working memory" "cancer treatment" correlation
"CRP" "cognitive function" "breast cancer survivors" trajectory
```

**Specific papers to find (cited in model):**
- Felger et al., 2020, Mol Psychiatry — inflammation → cognition
- Bower, 2014, Brain Behav Immun — inflammation in cancer survivors
- Ganz et al., 2013 — cytokine profiles and cognitive trajectories
- Pomykala et al., 2013 — IL-6 and brain structure in breast cancer

---

#### PW_C1: Sleep Disruption (8 edges, SE×1.0, Grade A)

**Target edges:**
- ER_LIGHT_SLEEP, ER_SLEEP_CORTISOL, ER_SLEEP_GLYMPHATIC
- ER_HPA_SLEEP, ER_SLEEP_FATIGUE, ER_SLEEP_ATTN, ER_SLEEP_WORKMEM, ER_SLEEP_EPISODIC

**PubMed queries:**

```sql
-- META: Sleep → Cognition in Cancer  
("sleep" OR "insomnia" OR "sleep quality" OR "sleep disturbance") 
AND ("cognitive" OR "neuropsychological" OR "attention" OR "memory") 
AND ("cancer" OR "cancer survivors" OR "breast cancer") 
AND (meta-analysis[pt] OR systematic review[pt])

-- RCT: CBT-I → Cognitive Improvement in Cancer 
("CBT-I" OR "cognitive behavioral therapy for insomnia" OR "sleep hygiene" 
OR "sleep intervention") 
AND ("cognitive function" OR "neuropsychological" OR "attention") 
AND ("cancer" OR "oncology") 
AND (randomized controlled trial[pt])

-- MECHANISM: Sleep → Glymphatic → Cognition
("glymphatic" OR "glymphatic system" OR "waste clearance") 
AND ("sleep" OR "slow wave sleep") 
AND ("cognitive" OR "neurodegeneration" OR "amyloid" OR "tau")

-- BRIGHT LIGHT: Light therapy → sleep in cancer
("bright light therapy" OR "light exposure" OR "phototherapy") 
AND ("sleep" OR "circadian") 
AND ("cancer" OR "chemotherapy") 
AND ("cognitive" OR "fatigue")
```

**Google Scholar queries:**
```
"sleep disturbance" "cognitive impairment" "cancer survivors" meta-analysis
"insomnia" "processing speed" "memory" "breast cancer" 
"CBT-I" "cancer" "cognitive outcomes" RCT
"bright light therapy" "circadian" "cancer" "sleep quality"
"glymphatic clearance" "sleep deprivation" "cognitive decline"
"Pittsburgh Sleep Quality Index" "cognitive function" "cancer"
```

**Specific papers:**
- Savard & Morin, 2001 — insomnia in cancer (foundational)
- Garland et al., 2014 — CBT-I in cancer survivors
- Irwin, 2015 — sleep and inflammation connection
- Xie et al., 2013, Science — glymphatic clearance during sleep

---

#### PW_C2: Cancer-Related Fatigue (7 edges, SE×1.0, Grade A)

**Target edges:**
- ER_OIC_FATIGUE, ER_PAIN_FATIGUE, ER_SLEEP_FATIGUE (→ fatigue)
- ER_FATIGUE_ACTIVITY (feedback), ER_ACTIVITY_FATIGUE_DIRECT (intervention)
- ER_FATIGUE_ATTN, ER_FATIGUE_PROCSPEED (fatigue → cognition)

**PubMed queries:**

```sql
-- META: Fatigue → Cognition in Cancer 
("cancer-related fatigue" OR "cancer fatigue" OR "CRF") 
AND ("cognitive" OR "attention" OR "processing speed" OR "concentration") 
AND (meta-analysis[pt] OR systematic review[pt])

-- RCT: Exercise → Fatigue Reduction in Cancer  
("exercise" OR "physical activity" OR "aerobic exercise" OR "resistance training") 
AND ("fatigue" OR "cancer-related fatigue") 
AND ("cancer" OR "breast cancer" OR "cancer survivors") 
AND (randomized controlled trial[pt])

-- MEDIATION: Fatigue mediating inflammation → cognition
("mediation" OR "mediator" OR "indirect effect") 
AND ("fatigue" OR "cancer-related fatigue") 
AND ("inflammation" OR "IL-6" OR "cytokines") 
AND ("cognitive" OR "neuropsychological")

-- DOSE-RESPONSE: Exercise dose → fatigue reduction
("dose-response" OR "dose response" OR "MET-minutes" OR "exercise intensity") 
AND ("fatigue" OR "cancer-related fatigue") 
AND ("cancer" OR "breast cancer")
```

**Google Scholar queries:**
```
"cancer-related fatigue" "cognitive impairment" meta-analysis effect size
"exercise" "cancer fatigue" "randomized" dose-response
"FACIT-Fatigue" "cognitive function" "cancer survivors" correlation
"deconditioning" "cognitive decline" "cancer" cerebral blood flow
fatigue activity feedback loop "cancer survivors"
```

**Specific papers:**
- Bower, 2014 — CRF biological mechanisms
- Berger et al., 2015 — CRF clinical practice guidelines
- Mustian et al., 2017 — exercise for CRF (large meta-analysis)

---

#### PW_M04: Neuroplasticity / BDNF (9 edges, SE×1.15, Grade B+)

**Target edges:**
- ER_ACTIVITY_BDNF, ER_COGACTIVITY_BDNF (interventions → BDNF)
- ER_BDNF_NEUROPLAST, ER_BDNF_NEUROGENESIS (BDNF → pathways)
- ER_NEUROPLAST_EPISODIC, ER_NEUROPLAST_WORKMEM (pathway → cognition)
- ER_AGE_BDNF, ER_IL6_BDNF_CROSS (modifiers/cross-links)

**PubMed queries:**

```sql
-- META: Exercise → BDNF  
("brain-derived neurotrophic factor" OR "BDNF") 
AND ("exercise" OR "physical activity" OR "aerobic") 
AND (meta-analysis[pt] OR systematic review[pt])

-- CANCER-SPECIFIC: BDNF in cancer patients
("BDNF" OR "brain-derived neurotrophic factor") 
AND ("cancer" OR "chemotherapy" OR "breast cancer" OR "cancer survivors") 
AND ("cognitive" OR "neuropsychological" OR "memory" OR "neuroplasticity")

-- PLASMA vs SERUM: Critical distinction
("BDNF" AND "plasma") AND ("cognitive" OR "memory") 
AND NOT ("serum BDNF" NOT "plasma")

-- EXERCISE → BDNF → COGNITION: Full chain
("exercise" OR "physical activity") AND ("BDNF") 
AND ("cognitive" OR "memory" OR "hippocampal") 
AND ("mediation" OR "mediator" OR "mechanism")
```

**Google Scholar queries:**
```
"BDNF" "exercise" "cognition" meta-analysis effect size
"plasma BDNF" "cancer survivors" "cognitive function"  
"BDNF" "neuroplasticity" "chemotherapy" "hippocampal"
"exercise" "BDNF" "cancer" "randomized controlled trial"
"BDNF" "age" "moderator" "exercise response"
"APOE" "BDNF" "exercise" "cognitive" interaction
```

**Specific papers:**
- Szuhany et al., 2015, J Psychiatr Res — exercise → BDNF meta-analysis
- Northey et al., 2019 — exercise and cognition
- Erickson et al., 2011, PNAS — exercise, hippocampal volume, BDNF

---

### Tier 2 — Moderate Evidence Pathways

These pathways have SE multiplier 1.15–1.25. Search to strengthen existing
evidence and reduce uncertainty.

---

#### PW_M02: Oxidative Stress (7 edges, SE×1.15)

**PubMed queries:**

```sql
-- META: Oxidative stress markers in cancer patients
("oxidative stress" OR "reactive oxygen species" OR "malondialdehyde" OR "MDA" 
OR "8-OHdG" OR "8-hydroxy-2'-deoxyguanosine" OR "lipid peroxidation") 
AND ("chemotherapy" OR "cancer treatment") 
AND (meta-analysis[pt] OR systematic review[pt])

-- Oxidative stress → cognitive outcomes
("oxidative stress" OR "MDA" OR "8-OHdG" OR "F2-isoprostanes") 
AND ("cognitive" OR "neuropsychological" OR "memory" OR "processing speed") 
AND ("cancer" OR "aging" OR "neurodegeneration")

-- Antioxidant interventions → cognition
("antioxidant" OR "vitamin E" OR "vitamin C" OR "N-acetylcysteine" OR "NAC") 
AND ("cognitive" OR "neuroprotective") 
AND ("chemotherapy" OR "cancer")
```

**Google Scholar queries:**
```
"oxidative stress" "cognitive impairment" "chemotherapy" biomarkers
"malondialdehyde" OR "8-OHdG" "cancer" "cognitive decline" 
"reactive oxygen species" "neuronal damage" "chemotherapy" "brain"
"oxidative stress" "processing speed" correlation
"Mediterranean diet" "oxidative stress" "cancer" biomarkers
```

---

#### PW_M03: HPA Dysregulation (8 edges, SE×1.25)

**PubMed queries:**

```sql
-- META: Cortisol and cognition in cancer  
("cortisol" OR "diurnal cortisol slope" OR "HPA axis" OR "hypothalamic-pituitary-adrenal") 
AND ("cognitive" OR "memory" OR "attention") 
AND ("cancer" OR "breast cancer") 
AND (meta-analysis[pt] OR systematic review[pt])

-- Cortisol slope → specific cognitive domains
("cortisol slope" OR "diurnal cortisol" OR "cortisol rhythm") 
AND ("hippocampal" OR "episodic memory" OR "working memory" OR "executive function") 
AND ("cancer" OR "survivors" OR "stress")

-- DHEA-S → neuroprotection
("DHEA" OR "DHEA-S" OR "dehydroepiandrosterone") 
AND ("cognitive" OR "neuroprotective") 
AND ("cancer" OR "aging")

-- HPA → depression → cognition chain
("cortisol" OR "HPA") AND ("depression" OR "depressive") 
AND ("cognitive" OR "neuropsychological") 
AND ("cancer" OR "breast cancer")

-- MBSR → cortisol in cancer
("mindfulness" OR "MBSR" OR "meditation" OR "stress reduction") 
AND ("cortisol" OR "HPA") 
AND ("cancer") 
AND (randomized controlled trial[pt])
```

**Google Scholar queries:**
```
"diurnal cortisol slope" "cognitive function" "cancer survivors" 
"HPA axis" "chemotherapy" "cognitive impairment" hippocampus
"cortisol" "episodic memory" "cancer" effect size
"MBSR" "cortisol" "cancer" randomized trial
"DHEA-S" "cognitive reserve" "cancer" "neuroprotection"
```

**Specific papers:**
- Bower et al., 2005 — cortisol and fatigue in cancer
- Sephton et al., 2013 — diurnal cortisol and survival
- Tell et al., 2014 — cortisol and cognition in cancer
- Adam et al., 2017 — meta-analysis of DCS and health

---

#### PW_M07: DNA Damage (5 edges, SE×1.15)

**PubMed queries:**

```sql
-- γ-H2AX and chemotherapy  
("gamma-H2AX" OR "γ-H2AX" OR "H2AX" OR "DNA double-strand breaks") 
AND ("chemotherapy" OR "anthracycline" OR "cisplatin" OR "radiation") 
AND ("cognitive" OR "neurotoxicity" OR "brain")

-- DNA damage → senescence → cognitive aging
("DNA damage" OR "genomic instability") 
AND ("cellular senescence" OR "senescence") 
AND ("cognitive" OR "neurodegeneration" OR "brain aging")

-- Radiation-induced DNA damage and neurocognition
("radiation" OR "cranial irradiation" OR "radiotherapy") 
AND ("DNA damage" OR "γ-H2AX") 
AND ("cognitive" OR "neurocognitive" OR "brain")
```

---

#### PW_M09: Cellular Senescence (5 edges, SE×1.25)

**PubMed queries:**

```sql
-- p16INK4a and chemotherapy  
("p16INK4a" OR "p16" OR "CDKN2A" OR "cellular senescence" OR "senescence") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("cognitive" OR "aging" OR "accelerated aging")

-- SASP and neuroinflammation
("senescence-associated secretory phenotype" OR "SASP") 
AND ("neuroinflammation" OR "cognitive" OR "brain aging")

-- Senolytics for cognition
("senolytic" OR "dasatinib" OR "quercetin" OR "fisetin") 
AND ("cognitive" OR "brain" OR "neurodegeneration")
```

**Google Scholar queries:**
```
"p16INK4a" "chemotherapy" "cognitive aging" "cancer survivors"
"cellular senescence" "SASP" "neuroinflammation" "cognitive decline"
Sanoff 2014 p16 chemotherapy accelerated aging
"senescence" "biomarker aging" "cancer treatment" cognitive outcomes
```

---

#### PW_M15: Synaptic Function (8 edges, SE×1.25, Convergent Hub)

**PubMed queries:**

```sql
-- Synaptic dysfunction and chemotherapy (mostly preclinical)  
("synaptic" OR "synaptic plasticity" OR "LTP" OR "long-term potentiation" 
OR "PSD-95" OR "dendritic spine") 
AND ("chemotherapy" OR "doxorubicin" OR "cisplatin" OR "methotrexate") 
AND ("cognitive" OR "memory" OR "learning")

-- Synaptic convergence: multiple pathways → synaptic function 
("synaptic dysfunction" OR "synaptic loss") 
AND ("neuroinflammation" OR "oxidative stress" OR "BDNF") 
AND ("cognitive impairment" OR "neurodegeneration")

-- Translational: animal model → human inference
("chemobrain" OR "chemo brain" OR "chemotherapy-induced cognitive") 
AND ("synaptic" OR "hippocampal" OR "neuronal") 
AND ("animal model" OR "mouse" OR "rat" OR "preclinical")
```

---

#### PW_M16: Myelin / Oligodendrocyte (5 edges, SE×1.15)

**PubMed queries:**

```sql
-- Chemotherapy → white matter damage  
("white matter" OR "myelin" OR "oligodendrocyte" OR "demyelination" 
OR "fractional anisotropy" OR "DTI") 
AND ("chemotherapy" OR "cancer treatment" OR "methotrexate" OR "5-fluorouracil") 
AND ("cognitive" OR "processing speed" OR "neuropsychological")

-- DTI studies in cancer survivors
("diffusion tensor imaging" OR "DTI" OR "fractional anisotropy" OR "white matter integrity") 
AND ("cancer survivors" OR "breast cancer" OR "chemotherapy") 
AND ("cognitive" OR "processing speed")
```

**Google Scholar queries:**
```
"white matter damage" "chemotherapy" "processing speed" DTI
"oligodendrocyte" "chemotherapy toxicity" "demyelination" cognition
Deprez 2012 DTI chemotherapy white matter 
Dietrich 2006 chemotherapy oligodendrocyte
Han 2008 chemotherapy white matter cognitive
```

---

#### PW_C3: Mood / Affect (6 edges, SE×1.15)

**PubMed queries:**

```sql
-- META: Depression/anxiety → cognition in cancer  
("depression" OR "depressive" OR "anxiety" OR "mood disturbance" OR "psychological distress") 
AND ("cognitive" OR "neuropsychological" OR "executive function" OR "memory") 
AND ("cancer" OR "cancer survivors") 
AND (meta-analysis[pt] OR systematic review[pt])

-- Subjective vs objective cognition dissociation  
("subjective cognitive" OR "perceived cognitive" OR "cognitive complaints") 
AND ("objective" OR "neuropsychological test") 
AND ("cancer" OR "breast cancer" OR "chemotherapy") 
AND ("correlation" OR "dissociation" OR "discrepancy")

-- Depression → cognitive complaints (CAL)
("depression" OR "mood") AND ("subjective cognitive" OR "FACT-Cog" OR "perceived cognitive") 
AND ("cancer" OR "breast cancer") AND ("reporting bias" OR "correlation")
```

**Google Scholar queries:**
```
"depression" "cognitive function" "cancer survivors" meta-analysis
"anxiety" "attention" "working memory" "cancer" effect size
"subjective cognitive complaints" "objective performance" "cancer" dissociation
"mood disturbance" "processing speed" "breast cancer" 
Pullens 2010 subjective objective cognitive cancer
Hutchinson 2012 cognitive complaints cancer
```

---

#### PW_M05: Neurogenesis (5 edges, SE×1.25)

**PubMed queries:**

```sql
-- Exercise → hippocampal neurogenesis (translational)  
("neurogenesis" OR "hippocampal neurogenesis" OR "adult neurogenesis") 
AND ("exercise" OR "physical activity" OR "running") 
AND ("cognitive" OR "memory" OR "spatial learning")

-- Chemotherapy → neurogenesis suppression
("neurogenesis" OR "neural progenitor" OR "stem cell") 
AND ("chemotherapy" OR "doxorubicin" OR "cisplatin" OR "cyclophosphamide") 
AND ("hippocampus" OR "dentate gyrus" OR "subgranular zone")

-- Human hippocampal volume as neurogenesis proxy
("hippocampal volume" OR "hippocampal atrophy") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("cognitive" OR "memory")
```

---

#### PW_M06: Mitochondrial Dysfunction (6 edges, SE×1.25)

**PubMed queries:**

```sql
-- Mitochondrial dysfunction in cancer treatment  
("mitochondrial dysfunction" OR "mitochondrial" OR "bioenergetics" OR "ATP" 
OR "electron transport chain" OR "oxidative phosphorylation") 
AND ("chemotherapy" OR "doxorubicin" OR "cisplatin") 
AND ("cognitive" OR "brain" OR "neurotoxicity" OR "fatigue")

-- Mitochondrial → fatigue connection
("mitochondrial" OR "bioenergetics" OR "ATP depletion") 
AND ("fatigue" OR "cancer-related fatigue") 
AND ("cancer" OR "cancer survivors")
```

---

### Tier 3 — Emerging / Placeholder Pathways

These have SE multiplier 1.75 or are edgeless. ANY evidence helps.

---

#### PW_M08: Gut-Brain Axis (5 edges, SE×1.75, Emerging)

**PubMed queries:**

```sql
-- Gut-brain axis and chemotherapy  
("gut-brain axis" OR "microbiome-gut-brain" OR "gut microbiota" OR "microbiome" 
OR "dysbiosis") 
AND ("chemotherapy" OR "cancer" OR "cancer treatment") 
AND ("cognitive" OR "neuroinflammation" OR "brain" OR "behavior")

-- Microbiome diversity and cognition
("microbiome diversity" OR "Shannon diversity" OR "gut microbiota") 
AND ("cognitive" OR "memory" OR "brain function") 
AND ("cancer" OR "aging" OR "neurodegeneration")

-- Chemotherapy → gut damage → systemic inflammation
("chemotherapy-induced mucositis" OR "intestinal permeability" OR "leaky gut") 
AND ("inflammation" OR "IL-6" OR "LPS" OR "endotoxin") 
AND ("brain" OR "neuroinflammation" OR "cognitive")

-- Probiotic interventions
("probiotic" OR "prebiotic" OR "synbiotic" OR "fecal transplant") 
AND ("cognitive" OR "brain" OR "mood") 
AND ("cancer" OR "chemotherapy")
```

**Google Scholar queries:**
```
"gut-brain axis" "chemotherapy" "cognitive impairment" 
"microbiome" "cancer survivors" "cognitive function" "Shannon diversity"
"chemotherapy" "dysbiosis" "neuroinflammation" mechanism
"probiotics" "cancer" "cognitive" randomized trial
Jordan 2018 chemotherapy microbiome brain
Cryan Dinan 2012 gut-brain axis
```

---

#### PW_M10: Glymphatic Clearance (6 edges, SE×1.75, Emerging)

**PubMed queries:**

```sql
-- Glymphatic system and cognition  
("glymphatic" OR "glymphatic system" OR "paravascular clearance" 
OR "interstitial fluid" OR "aquaporin-4") 
AND ("cognitive" OR "neurodegeneration" OR "Alzheimer" OR "dementia")

-- Sleep → glymphatic → waste clearance
("glymphatic" OR "brain waste clearance") 
AND ("sleep" OR "slow wave sleep" OR "sleep deprivation") 
AND ("amyloid" OR "tau" OR "neuroinflammation" OR "metabolite")

-- Cancer-specific glymphatic (very sparse — broaden)
("glymphatic" OR "perivascular clearance") 
AND ("cancer" OR "chemotherapy" OR "radiation")
```

---

#### PW_M11: Cerebrovascular (EDGELESS — 3 nominal edges, SE×1.25)

**PubMed queries:**

```sql
-- Cerebrovascular function and chemotherapy  
("cerebral blood flow" OR "cerebrovascular" OR "brain perfusion" 
OR "cerebral hemodynamics" OR "vascular function") 
AND ("chemotherapy" OR "cancer treatment" OR "cancer survivors") 
AND ("cognitive" OR "processing speed" OR "neuropsychological")

-- fMRI/MRI perfusion in cancer survivors
("fMRI" OR "functional MRI" OR "ASL" OR "arterial spin labeling" 
OR "cerebral perfusion") 
AND ("cancer survivors" OR "breast cancer" OR "chemotherapy") 
AND ("cognitive")

-- Exercise → cerebrovascular → cognition
("exercise" OR "physical activity") AND ("cerebral blood flow" OR "brain perfusion") 
AND ("cognitive" OR "processing speed") AND ("cancer" OR "aging")
```

---

#### PW_M12: Epigenetic Changes (4 edges, SE×1.75, Emerging)

**PubMed queries:**

```sql
-- Epigenetic changes from chemotherapy  
("epigenetic" OR "DNA methylation" OR "histone modification" OR "epigenome") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("cognitive" OR "brain" OR "neuronal" OR "gene expression")

-- BDNF promoter methylation
("BDNF methylation" OR "BDNF promoter" OR "BDNF epigenetic") 
AND ("cognitive" OR "depression" OR "neuroplasticity")

-- Mindfulness/exercise → epigenetic changes
("mindfulness" OR "exercise" OR "physical activity") 
AND ("epigenetic" OR "methylation" OR "telomere") 
AND ("cancer" OR "inflammation")
```

---

#### PW_M13: Metabolic Dysregulation (5 edges, SE×1.25, Emerging)

**PubMed queries:**

```sql
-- Insulin resistance and cognition in cancer  
("insulin resistance" OR "metabolic syndrome" OR "glucose" OR "HbA1c" 
OR "diabetes" OR "metabolic dysregulation") 
AND ("cognitive" OR "dementia" OR "memory" OR "processing speed") 
AND ("cancer" OR "chemotherapy" OR "dexamethasone")

-- Brain insulin resistance
("brain insulin resistance" OR "cerebral glucose metabolism" OR "FDG-PET") 
AND ("cognitive" OR "neurodegeneration") 
AND ("cancer" OR "chemo" OR "treatment")
```

---

#### PW_M14: BBB Disruption (EDGELESS — 4 nominal edges, SE×1.75)

**PubMed queries:**

```sql
-- Blood-brain barrier and chemotherapy  
("blood-brain barrier" OR "BBB" OR "BBB disruption" OR "BBB permeability" 
OR "tight junction") 
AND ("chemotherapy" OR "cancer treatment" OR "doxorubicin" OR "methotrexate") 
AND ("cognitive" OR "neurotoxicity" OR "neuroinflammation")

-- NfL as BBB marker
("neurofilament light" OR "NfL" OR "neurofilament") 
AND ("chemotherapy" OR "cancer") 
AND ("cognitive" OR "neurotoxicity" OR "blood-brain barrier")

-- BBB imaging studies  
("dynamic contrast-enhanced MRI" OR "DCE-MRI" OR "BBB permeability" 
OR "albumin quotient" OR "S100B") 
AND ("cancer" OR "chemotherapy" OR "radiation")
```

---

#### PW_M17: Dopaminergic (4 edges, SE×1.75, Emerging)

**PubMed queries:**

```sql
-- Dopamine and cancer-related fatigue/motivation  
("dopamine" OR "dopaminergic" OR "mesolimbic" OR "striatal") 
AND ("fatigue" OR "motivation" OR "amotivation" OR "anhedonia") 
AND ("cancer" OR "chemotherapy" OR "inflammation")

-- Inflammation → dopamine disruption
("inflammation" OR "cytokine" OR "interferon") 
AND ("dopamine" OR "dopaminergic" OR "reward" OR "motivation") 
AND ("cognitive" OR "executive function" OR "inhibitory control")
```

**Specific papers:**
- Saligan et al., 2015 — fatigue and dopaminergic function
- Capuron et al., 2012 — inflammation and dopamine

---

#### PW_C4: Vascular / Metabolic (4 edges, SE×1.15)

**PubMed queries:**

```sql
-- Metabolic comorbidities → cognition in cancer  
("metabolic syndrome" OR "diabetes" OR "obesity" OR "cardiovascular risk") 
AND ("cognitive" OR "dementia" OR "processing speed") 
AND ("cancer survivors" OR "breast cancer")

-- Comorbidity burden and cognitive outcomes
("comorbidity" OR "Charlson" OR "comorbid conditions") 
AND ("cognitive" OR "neuropsychological") 
AND ("cancer" OR "cancer survivors")
```

---

#### PW_C5: Social Isolation (3 edges, SE×1.75)

**PubMed queries:**

```sql
-- Social isolation → cognition in cancer  
("social isolation" OR "loneliness" OR "social engagement" OR "social network" 
OR "social participation") 
AND ("cognitive" OR "verbal fluency" OR "executive function") 
AND ("cancer" OR "cancer survivors")

-- Social interventions for cancer patients
("social support" OR "support group" OR "peer support") 
AND ("cognitive" OR "quality of life") 
AND ("cancer" OR "cancer survivors") 
AND (randomized controlled trial[pt])
```

---

## Part 3: Cross-Cutting Searches

These searches span multiple pathways to find papers addressing model-wide questions.

### 3.1 Feedback Loops

```sql
-- PubMed: Fatigue ↔ Activity feedback in cancer
("fatigue" AND "physical activity" AND "bidirectional" OR "reciprocal" OR "feedback") 
AND ("cancer" OR "cancer survivors")

-- PubMed: Depression ↔ Sleep feedback
("depression" AND "insomnia" OR "sleep" AND "bidirectional" OR "reciprocal") 
AND ("cancer" OR "cancer survivors")

-- Google Scholar
"fatigue" "physical activity" "bidirectional" "cancer survivors" 
"depression" "sleep" "reciprocal relationship" "cancer"
"feedback loop" "symptom cluster" "cancer" cognitive
```

### 3.2 Multi-Pathway / Multi-Mechanism Papers

```sql
-- PubMed: Comprehensive CRCI mechanism reviews
("chemotherapy-related cognitive impairment" OR "chemobrain" OR "CRCI" 
OR "cancer-related cognitive impairment" OR "chemo brain") 
AND ("mechanism" OR "pathophysiology" OR "biological mechanism" OR "pathway") 
AND (review[pt] OR meta-analysis[pt])

-- Google Scholar
"chemobrain" mechanisms "biological pathways" review 2020..2026
"CRCI" "multiple mechanisms" "neuroinflammation" "oxidative stress" "BDNF"  
"chemotherapy-induced cognitive" "comprehensive review" mechanisms  
```

### 3.3 Symptom Cluster Co-Occurrence

```sql
-- PubMed: Symptom clusters in cancer (fatigue + sleep + depression + cognitive)
("symptom cluster" OR "co-occurring symptoms" OR "symptom burden") 
AND ("fatigue" AND "sleep" AND "depression" OR "cognitive") 
AND ("cancer" OR "cancer survivors")

-- Google Scholar
"symptom cluster" "fatigue" "sleep" "depression" "cognitive" "cancer"
"network analysis" "symptoms" "cancer survivors" cognitive
```

### 3.4 Exercise Interventions (Cross-Pathway)

```sql
-- META: Exercise → ALL outcome types in cancer
("exercise" OR "physical activity" OR "aerobic exercise" OR "HIIT" OR "resistance training") 
AND ("cancer" OR "breast cancer" OR "cancer survivors") 
AND ("cognitive" OR "fatigue" OR "depression" OR "sleep" OR "inflammation" OR "BDNF") 
AND (meta-analysis[pt] OR systematic review[pt])

-- Google Scholar (years 2020-2026 for recency)
exercise "cancer survivors" cognitive outcomes meta-analysis 2020..2026
"high intensity interval training" "cancer" cognitive biomarkers
exercise "cancer-related cognitive impairment" mediation mechanisms
```

### 3.5 Cognitive Rehabilitation / Training (Cross-Pathway)

```sql
-- META: Cognitive rehabilitation in cancer  
("cognitive rehabilitation" OR "cognitive training" OR "cognitive remediation" 
OR "compensatory strategy" OR "neuropsychological rehabilitation") 
AND ("cancer" OR "cancer survivors" OR "chemotherapy" OR "CRCI") 
AND (meta-analysis[pt] OR systematic review[pt] OR randomized controlled trial[pt])

-- Google Scholar
"cognitive rehabilitation" "cancer survivors" RCT meta-analysis
"cognitive training" "chemobrain" "working memory" "processing speed"
"memory strategy training" "cancer" randomized
```

---

## Part 4: Instrument & Norms Searches

For every instrument in the INSTRUMENT_REGISTRY, we need normative data
(mean, SD) specific to cancer populations.

### 4.1 Neuropsychological Test Norms

```sql
-- PubMed: Cancer-specific neuropsych norms  
("normative data" OR "reference values" OR "norms") 
AND ("cancer" OR "cancer survivors" OR "breast cancer") 
AND ("neuropsychological" OR "Trail Making" OR "HVLT" OR "Digit Span" 
OR "Stroop" OR "COWAT" OR "CPT")

-- Specific instruments
("Trail Making Test" OR "TMT-A" OR "TMT-B") AND ("cancer" OR "breast cancer") AND ("normative" OR "baseline" OR "mean" OR "standard deviation")
("Hopkins Verbal Learning" OR "HVLT-R") AND ("cancer") AND ("normative" OR "mean" OR "SD")
("Digit Span" OR "WAIS") AND ("cancer survivors") AND ("normative" OR "baseline")
("Stroop" OR "Color-Word") AND ("cancer") AND ("normative" OR "baseline")
("COWAT" OR "verbal fluency" OR "FAS") AND ("cancer") AND ("normative" OR "baseline")
("Continuous Performance Test" OR "CPT") AND ("cancer") AND ("normative" OR "mean")
```

### 4.2 PRO / Symptom Instrument Norms

```sql
-- Fatigue norms
("FACIT-Fatigue" OR "Brief Fatigue Inventory" OR "BFI") AND ("cancer") AND ("mean" OR "normative" OR "cutoff")

-- Depression / anxiety norms  
("PHQ-9" OR "GAD-7" OR "CES-D") AND ("cancer patients" OR "cancer survivors") AND ("mean" OR "prevalence" OR "cutoff")

-- Sleep norms
("PSQI" OR "Pittsburgh Sleep Quality" OR "ISI" OR "Insomnia Severity") AND ("cancer") AND ("mean" OR "normative")

-- Cognitive complaints norms
("FACT-Cog" OR "PROMIS Cognitive" OR "Attentional Function Index") AND ("cancer") AND ("mean" OR "normative" OR "cutoff")
```

### 4.3 Biomarker Reference Ranges

```sql
-- Cancer-specific biomarker norms
("IL-6" OR "interleukin-6") AND ("reference range" OR "normal values" OR "healthy controls") AND ("cancer" OR "breast cancer")
("C-reactive protein" OR "hs-CRP") AND ("reference range" OR "normative") AND ("cancer patients")
("BDNF" AND "plasma") AND ("reference range" OR "normal" OR "healthy" OR "mean" AND "SD")
("cortisol" AND "diurnal slope") AND ("normative" OR "reference" OR "healthy") 
("p16INK4a" OR "p16") AND ("age-adjusted" OR "reference" OR "normative")
("neurofilament light" OR "NfL") AND ("normative" OR "reference range" OR "age-adjusted")
("8-OHdG") AND ("reference" OR "normal values") AND ("healthy")
("malondialdehyde" OR "MDA") AND ("reference range" OR "normal values")
```

---

## Part 5: Dose-Response & Temporal Kernel Searches

### 5.1 Dose-Response Functions

The model uses Hill/Emax functions for exercise edges. We need EC50 and hill coefficient data.

```sql
-- Exercise dose-response for specific outcomes
("dose-response" OR "dose response") AND ("exercise" OR "physical activity") 
AND ("IL-6" OR "BDNF" OR "cortisol" OR "fatigue" OR "cognitive") 
AND ("cancer" OR "breast cancer")

-- MET-minutes threshold for benefit
("MET-minutes" OR "MET-min" OR "moderate-vigorous" OR "exercise threshold") 
AND ("cancer" OR "oncology") 
AND ("benefit" OR "response" OR "improvement")

-- Meditation dose-response
("dose-response" OR "dose response") AND ("mindfulness" OR "meditation" OR "MBSR") 
AND ("cortisol" OR "stress" OR "inflammation")
```

**Google Scholar:**
```
"dose-response" "exercise" "IL-6" "cancer survivors" 
"MET-minutes per week" "cognitive benefit" threshold
"exercise intensity" "BDNF response" "Emax" OR "EC50"
"minimum effective dose" exercise cognition cancer
```

### 5.2 Temporal Dynamics / Trajectories

```sql
-- Cognitive trajectory after chemotherapy  
("trajectory" OR "longitudinal" OR "time course" OR "recovery") 
AND ("cognitive" OR "neuropsychological" OR "chemobrain") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("months" OR "years" OR "follow-up")

-- Biomarker trajectories during/after cancer treatment
("trajectory" OR "longitudinal" OR "time course") 
AND ("IL-6" OR "BDNF" OR "cortisol" OR "CRP") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("pre-treatment" OR "during treatment" OR "post-treatment" OR "recovery")

-- Onset latency and peak timing  
("onset" OR "latency" OR "peak" OR "half-life" OR "decay") 
AND ("exercise" OR "intervention") 
AND ("BDNF" OR "IL-6" OR "cortisol" OR "cognitive" OR "fatigue") 
AND ("weeks" OR "months")
```

**Google Scholar:**
```
"cognitive trajectory" "chemotherapy" "recovery" longitudinal months years
"IL-6" "trajectory" "chemotherapy" pre post treatment
"BDNF" "exercise" "time course" "weeks" "peak response"
"cancer-related cognitive impairment" "natural history" "recovery curve"
"accelerated aging" "chemotherapy" trajectory cognitive
```

---

## Part 6: Effect Modifier Searches

### 6.1 APOE Genotype (Grade A Modifier)

```sql
-- APOE and CRCI  
("APOE" OR "apolipoprotein E" OR "APOE4" OR "epsilon 4") 
AND ("cognitive" OR "chemotherapy" OR "cancer" OR "CRCI") 
AND ("risk" OR "moderator" OR "interaction" OR "carrier")

-- APOE × exercise interaction  
("APOE" OR "apolipoprotein E") 
AND ("exercise" OR "physical activity") 
AND ("cognitive" OR "BDNF" OR "neuroplasticity") 
AND ("interaction" OR "moderator" OR "genotype")
```

**Specific papers:**
- Pearce et al., 2022 — APOE moderation of exercise-cognition

### 6.2 Age as Modifier

```sql
-- Age × chemotherapy cognitive effects  
("age" OR "older adults" OR "elderly") 
AND ("chemotherapy" OR "cancer treatment") 
AND ("cognitive" OR "neuropsychological") 
AND ("risk factor" OR "moderator" OR "vulnerability" OR "interaction")

-- Cognitive reserve  
("cognitive reserve" OR "education" OR "premorbid IQ") 
AND ("chemotherapy" OR "cancer") 
AND ("cognitive decline" OR "resilience" OR "moderator")
```

### 6.3 Sex / Hormonal Modifiers

```sql
-- Sex differences in CRCI  
("sex differences" OR "gender differences" OR "biological sex") 
AND ("cognitive" OR "CRCI" OR "chemobrain") 
AND ("cancer" OR "chemotherapy")

-- Endocrine therapy and cognition  
("tamoxifen" OR "aromatase inhibitor" OR "letrozole" OR "anastrozole" 
OR "endocrine therapy" OR "hormonal therapy") 
AND ("cognitive" OR "memory" OR "processing speed" OR "neuropsychological")
```

### 6.4 Treatment Phase Modifier

```sql
-- Cognitive changes across treatment phases
("pre-treatment" OR "active treatment" OR "post-treatment" OR "survivorship") 
AND ("cognitive" OR "neuropsychological") 
AND ("cancer" OR "chemotherapy") 
AND ("change" OR "trajectory" OR "comparison")
```

---

## Part 7: AI Deep Research Prompts

Use these with ChatGPT Deep Research, Perplexity Pro, Google Gemini Deep Research,
or Claude Research mode to find comprehensive literature reviews.

### 7.1 Master Overview Prompt

```
I am building a Bayesian causal model of Chemotherapy-Related Cognitive Impairment (CRCI) 
with 64 nodes, 143 edges, and 21 biological/clinical pathways. I need a comprehensive 
literature review covering all mechanistic pathways from chemotherapy to cognitive outcomes.

The 17 mechanistic pathways are:
M1: Neuroinflammation (IL-6, CRP, TNF-α → processing speed, memory, fatigue)
M2: Oxidative stress (MDA, 8-OHdG → neuronal damage → cognition)
M3: HPA axis dysregulation (cortisol slope → memory, sleep, depression)
M4: Neuroplasticity/BDNF (exercise → BDNF → hippocampal function → memory)
M5: Adult neurogenesis (hippocampal progenitor cells → memory)
M6: Mitochondrial dysfunction (ATP depletion → fatigue → processing speed)
M7: DNA damage (γ-H2AX → cellular senescence → inflammation)
M8: Gut-brain axis (dysbiosis → intestinal permeability → neuroinflammation)
M9: Cellular senescence (p16INK4a → SASP → chronic inflammation)
M10: Glymphatic clearance (sleep → brain waste clearance)
M11: Cerebrovascular dysfunction (perfusion deficits → processing speed)
M12: Epigenetic changes (methylation → gene expression → neuroplasticity)
M13: Metabolic dysregulation (insulin resistance → cerebral glucose metabolism)
M14: BBB disruption (endothelial damage → neurotoxin infiltration)
M15: Synaptic dysfunction (convergent hub from multiple pathways → cognition)
M16: Myelin/oligodendrocyte damage (demyelination → processing speed)
M17: Dopaminergic dysfunction (reduced motivation → executive function)

Plus 5 clinical mediator pathways:
C1: Sleep disruption, C2: Cancer-related fatigue, C3: Mood/affect, C4: Vascular/metabolic, C5: Social isolation

For EACH pathway, I need:
1. The strongest meta-analyses or systematic reviews (with effect sizes)
2. Key RCTs providing β and SE values 
3. Dose-response parameters where available
4. Whether the evidence is from human cancer patients, healthy humans, or animal models
5. Any known effect modifiers (age, sex, APOE genotype, cancer type)

Please provide specific paper citations with DOIs, sample sizes, and effect sizes where available.
```

### 7.2 Specific Pathway Deep Dives

**For weak pathways (M8, M10, M11, M12, M14, M17):**

```
I need a deep literature review on [PATHWAY NAME] specifically in the context of 
chemotherapy-related cognitive impairment (CRCI). This is an EMERGING pathway in my 
Bayesian causal model with limited human evidence.

Specifically I need:
1. ALL published human studies linking [PATHWAY] to cognitive outcomes in cancer patients
2. The strongest animal model evidence for this pathway in chemo-induced neurotoxicity
3. Any indirect human evidence (e.g., this pathway in Alzheimer's/aging applied to cancer patients)
4. Quantitative effect sizes (correlations, standardized mean differences, hazard ratios)
5. Whether any interventions target this pathway in cancer patients

For context, in my model this pathway connects:
- Entry nodes: [LIST FROM PATHWAY_REGISTRY]  
- Exit nodes: [LIST FROM PATHWAY_REGISTRY]
- Proxy biomarker: [FROM PATHWAY_REGISTRY]

Please be as specific as possible with citations (first author, year, journal, DOI, n, effect size).
```

### 7.3 Edge-Specific Evidence Queries

**Template for any edge in EDGE_REGISTRY:**

```
I need quantitative evidence for the causal/associational relationship between 
[SOURCE NODE] and [TARGET NODE] in cancer patients or cancer survivors.

Specifically: [MECHANISM_DESCRIPTION from edge registry]

What I need:
1. Effect size (standardized mean difference, correlation r, regression β, odds ratio)
2. Standard error or confidence interval
3. Sample size
4. Study design (RCT, prospective cohort, cross-sectional)
5. Population (cancer type, treatment phase, demographics)
6. Instrument used to measure [SOURCE] and [TARGET]

Priority: meta-analyses > RCTs > prospective studies > cross-sectional
Cancer-specific evidence preferred, but well-established general population 
evidence is acceptable when cancer-specific data is sparse.
```

### 7.4 Biomarker-to-Cognition Evidence

```
I need quantitative evidence linking peripheral blood biomarkers to cognitive 
performance in cancer patients/survivors. For each biomarker-cognition pair below, 
please find the best available effect sizes (r, β, d, or OR) with CIs:

1. Plasma IL-6 → Processing Speed (TMT-A, TMT-B, DSST)
2. Plasma IL-6 → Working Memory (Digit Span Backward) 
3. Plasma IL-6 → Episodic Memory (HVLT-R, RAVLT)
4. hs-CRP → Processing Speed
5. TNF-α → Processing Speed
6. Plasma BDNF → Episodic Memory (HVLT-R, hippocampal)
7. Plasma BDNF → Working Memory
8. Cortisol diurnal slope → Episodic Memory
9. Cortisol diurnal slope → Fatigue (FACIT-F)
10. p16INK4a → Fatigue or Processing Speed
11. 8-OHdG → Processing Speed
12. Fasting glucose / HOMA-IR → Processing Speed
13. NfL → Processing Speed or Global Cognition
14. Shannon diversity (gut) → Any cognitive outcome

Include "null" results too — knowing that a study found no significant relationship 
is equally valuable for Bayesian priors.
```

### 7.5 Intervention Dose-Response

```
For the following lifestyle interventions in cancer patients/survivors, I need 
dose-response parameters to fit Hill/Emax functions:

1. AEROBIC EXERCISE → IL-6 reduction
   - What MET-min/week produces 50% of maximum IL-6 reduction (EC50)?
   - What is the maximum IL-6 reduction achievable (Emax)?
   
2. AEROBIC EXERCISE → BDNF increase
   - EC50 in MET-min/week?
   - Does intensity (HIIT vs moderate) matter more than volume?
   
3. AEROBIC EXERCISE → Fatigue reduction (FACIT-F)
   - Is there a minimum dose threshold?
   - Does the relationship plateau?
   
4. MBSR/MINDFULNESS → Cortisol slope normalization 
   - What practice hours/week needed for measurable effect?
   
5. CBT-I → Sleep quality improvement (PSQI)
   - What is the typical effect magnitude vs waitlist?
   - Is there a dose (number of sessions) threshold?

6. BRIGHT LIGHT THERAPY → Circadian rhythm improvement
   - Minimum lux and duration for effect?
   - Morning vs evening exposure difference?
   
7. COGNITIVE TRAINING → Working memory improvement
   - Hours per week needed?
   - Does the effect transfer to untrained tasks?
   
8. MEDITERRANEAN DIET → IL-6 reduction
   - Adherence score threshold for anti-inflammatory effect?
```

### 7.6 Temporal Recovery Curves

```
For chemotherapy-related cognitive impairment, I need evidence about temporal 
dynamics and recovery curves:

1. ONSET: When do cognitive deficits first appear relative to chemo start?
   - During treatment? Immediately after? Delayed onset?
   
2. NADIR: When is the worst point for each cognitive domain?
   - Processing speed, memory, executive function — same or different timing?
   
3. RECOVERY: What proportion of patients recover to baseline by:
   - 6 months post-treatment?
   - 12 months?
   - 2 years?
   - 5+ years (long-term survivors)?
   
4. BIOMARKER DYNAMICS: For IL-6, cortisol, BDNF, p16INK4a:
   - Peak elevation timing during/after chemotherapy
   - Return to baseline timing
   - Are some biomarkers permanently altered?
   
5. ACCELERATED AGING: Is there evidence that chemotherapy creates a permanent 
   "biological age offset" (e.g., 10 years of biological aging from treatment)?
   
Provide specific longitudinal study data with timepoints and effect sizes.
```

### 7.7 Comprehensive Oppegaard / Multi-Symptom Search

```
I need papers that measure MULTIPLE nodes from my CRCI model simultaneously 
(at minimum 3+ of: cognitive test, biomarkers, sleep, fatigue, depression/anxiety, 
physical activity) in cancer patients, enabling path analysis or structural 
equation modeling.

Search for studies like Oppegaard et al. 2023 that collect broad multi-domain 
batteries in cancer patients. I need:
- Studies with both objective neuropsych testing AND patient-reported outcomes  
- Studies with both biomarkers AND cognitive outcomes
- Studies that perform mediation analysis through biological pathways
- Path analysis or SEM studies in cancer cognitive research

These multi-domain studies are especially valuable because they can provide 
evidence for multiple edges simultaneously and test pathway structures.
```

---

## Part 8: Search Execution Checklist

### Phase 1: Meta-Analyses & Systematic Reviews (Highest Yield)
Run these queries first — each paper may provide evidence for 5-20 edges.

- [ ] CRCI comprehensive mechanism reviews (2020-2026)
- [ ] Exercise → cognition in cancer meta-analyses
- [ ] Exercise → biomarkers (IL-6, BDNF, cortisol) in cancer meta-analyses  
- [ ] Sleep → cognition in cancer systematic reviews
- [ ] Fatigue → cognition in cancer meta-analyses
- [ ] Depression/anxiety → cognition in cancer meta-analyses
- [ ] Neuroinflammation → cognition meta-analyses (general + cancer)
- [ ] CBT-I → sleep in cancer meta-analyses
- [ ] MBSR → stress/cortisol in cancer meta-analyses
- [ ] Cognitive rehabilitation in cancer meta-analyses

### Phase 2: Cancer-Specific RCTs (β, SE, n)
Run these for each major intervention type.

- [ ] Exercise RCTs with cognitive outcomes in cancer
- [ ] CBT-I RCTs with cognitive outcomes in cancer
- [ ] MBSR RCTs with biomarker + cognitive outcomes
- [ ] Cognitive training RCTs in cancer
- [ ] Diet interventions with biomarker outcomes in cancer
- [ ] Bright light therapy in cancer

### Phase 3: Biomarker-Cognition Correlation Studies
Run these for each biomarker node (Layer 2).

- [ ] IL-6 ↔ cognitive domains in cancer
- [ ] CRP ↔ cognitive domains in cancer  
- [ ] TNF-α ↔ cognitive domains in cancer
- [ ] BDNF ↔ cognitive domains in cancer
- [ ] Cortisol ↔ cognitive domains in cancer
- [ ] p16INK4a ↔ aging/cognition in cancer
- [ ] γ-H2AX ↔ outcomes in cancer
- [ ] 8-OHdG ↔ outcomes in cancer
- [ ] MDA ↔ outcomes
- [ ] Fasting glucose ↔ cognition in cancer
- [ ] NfL ↔ neurotoxicity in cancer
- [ ] Shannon diversity ↔ any outcomes in cancer

### Phase 4: Emerging Pathway Evidence
Fill edgeless and placeholder pathways.

- [ ] Gut-brain axis + chemotherapy (ANY human evidence)
- [ ] Glymphatic + cancer/chemo (ANY evidence)
- [ ] Cerebrovascular + chemotherapy (fMRI/perfusion studies)
- [ ] Epigenetic + chemotherapy + cognition
- [ ] BBB disruption + chemotherapy (ANY human evidence)
- [ ] Dopaminergic + cancer fatigue/motivation
- [ ] Myelin/DTI + chemotherapy

### Phase 5: Norms & Reference Data

- [ ] Cancer-specific neuropsych norms (TMT, HVLT-R, Stroop, Digit Span, etc.)
- [ ] Cancer-specific PRO norms (FACIT-F, PHQ-9, GAD-7, PSQI, ISI, FACT-Cog)
- [ ] Biomarker reference ranges in cancer populations
- [ ] Age-stratified norms for all instruments
- [ ] Healthy control comparison data

### Phase 6: Effect Modifiers & Subgroups

- [ ] APOE × chemotherapy × cognition
- [ ] APOE × exercise × BDNF/cognition
- [ ] Age × treatment × cognitive outcomes
- [ ] Sex × HPA × cognitive outcomes
- [ ] Cognitive reserve × CRCI vulnerability
- [ ] Cancer type differences in CRCI severity
- [ ] Treatment phase differences

### Phase 7: Dose-Response & Temporal

- [ ] Exercise dose-response (MET-min/wk) for each biomarker
- [ ] MBSR dose-response for cortisol
- [ ] Cognitive trajectory studies (pre → during → post → survivorship)
- [ ] Biomarker trajectory studies during treatment
- [ ] Recovery curves by cognitive domain
- [ ] Accelerated aging evidence in cancer

---

## Appendix A: High-Priority Citation Targets

Papers **already cited** in the model that need full extraction:

| Citation | Pathway | What to Extract |
|----------|---------|-----------------|
| Felger et al., 2020, Mol Psychiatry | M1 | β for inflammation → cognition |
| Bower, 2014, Brain Behav Immun | M1, C2 | Effect sizes for IL-6 paths |
| Szuhany et al., 2015, J Psychiatr Res | M4 | Exercise → BDNF meta-analytic effect |
| Erickson et al., 2011, PNAS | M4, M5 | Exercise → hippocampus → memory |
| Joshi et al., 2010, Free Radic Biol Med | M2 | Oxidative stress effect sizes |
| Xie et al., 2013, Science | M10 | Glymphatic clearance parameters |
| Sanoff et al., 2014 | M9 | p16INK4a post-chemo increase |
| Demaria et al., 2017 | M9 | Senescence → SASP → inflammation |
| Cryan & Dinan, 2012 | M8 | Gut-brain axis framework |
| Jordan et al., 2018 | M8 | Chemo + microbiome |
| Dietrich et al., 2006 | M16 | Chemo → oligodendrocyte toxicity |
| Han et al., 2008 | M16 | White matter damage post-chemo |
| Deprez et al., 2012 | M16 | DTI evidence in chemo patients |
| Wardill et al., 2016 | M14 | BBB disruption from chemo |
| Schroyen et al., 2021 | M14 | NfL in chemo patients |
| Saligan et al., 2015 | M17 | Fatigue and dopaminergic function |
| Capuron et al., 2012 | M17 | Inflammation → dopamine |
| Adam et al., 2017 | M3 | DCS meta-analysis (flatter slope → inflammation/health) |
| Pullens et al., 2010 | C3 | Subjective-objective dissociation |
| Stern, 2009 | Modifier | Cognitive reserve theory |
| Pearce et al., 2022 | Modifier | APOE × exercise (Grade A) |
| Kesler et al., 2017 | M11 | fMRI evidence in cancer |
| Bhatt et al., 2020 | M15 | Synaptic mechanisms in chemo brain |
| Gibson & Bhatt, 2018 | M15 | Synaptic dysfunction review |

---

## Appendix B: Edge Coverage Gap Analysis

### Edges with ZERO extracted evidence (high priority):

Based on EDGE_REGISTRY, these edges lack any extracted studies and need filling:

**Layer 0→1 (Treatment → Behavior):**
- ER_CHEMO_ACTIVITY, ER_CHEMO_SLEEP, ER_CHEMO_DIET, ER_TX_PHASE_ACTIVITY

**Layer 0→2 (Treatment → Biomarker):**
- ER_CHEMO_IL6, ER_CHEMO_CRP, ER_CHEMO_TNF, ER_CHEMO_GH2AX, ER_RADIATION_GH2AX
- ER_CHEMO_8OHDG, ER_CHEMO_MDA, ER_CHEMO_P16, ER_CHEMO_CORTISOL
- ER_CHEMO_SHANNON, ER_CHEMO_GLUCOSE, ER_CHEMO_NFL, ER_RADIATION_NFL

**Layer 1→2 (Behavior → Biomarker):**
- ER_ACTIVITY_IL6, ER_ACTIVITY_CRP, ER_ACTIVITY_BDNF, ER_ACTIVITY_CORTISOL
- ER_ACTIVITY_GLUCOSE, ER_ACTIVITY_8OHDG, ER_DIET_IL6, ER_DIET_SHANNON
- ER_DIET_GLUCOSE, ER_DIET_MDA, ER_STRESS_CORTISOL, ER_STRESS_IL6
- ER_SLEEP_CORTISOL, ER_COGACTIVITY_BDNF

**Layer 2→3 (Biomarker → Pathway):**
- ER_IL6_OIC, ER_CRP_OIC, ER_TNF_OIC, ER_8OHDG_OIC, ER_MDA_OIC
- ER_BDNF_NEUROPLAST, ER_BDNF_NEUROGENESIS, ER_CORTISOL_HPA
- ER_P16_SENESCENCE, ER_GH2AX_DNA, ER_SHANNON_GUTBRAIN
- ER_GLUCOSE_METABOLIC, ER_NFL_BBB, ER_NFL_MYELIN

**Layer 3→4/5 (Pathway → Symptoms/Cognition):**
- ER_OIC_PROCSPEED, ER_OIC_WORKMEM, ER_OIC_EPISODIC, ER_OIC_ATTNSUST
- ER_OIC_FATIGUE, ER_OIC_DEPRESSION, ER_OIC_PAIN
- ER_HPA_SLEEP, ER_HPA_DEPRESSION, ER_HPA_ANXIETY, ER_HPA_EPISODIC, ER_HPA_WORKMEM
- ER_NEUROPLAST_EPISODIC, ER_NEUROPLAST_WORKMEM, ER_NEUROGENESIS_EPISODIC
- ER_SYNAPTIC_PROCSPEED, ER_SYNAPTIC_WORKMEM, ER_SYNAPTIC_EXEC
- ER_MYELIN_PROCSPEED, ER_MYELIN_VERBAL, ER_MYELIN_LANGUAGE
- ER_DOPAMINE_INHIBITION, ER_DOPAMINE_FATIGUE

**Layer 4→5 (Symptom → Cognition):**
- ER_FATIGUE_ATTN, ER_FATIGUE_PROCSPEED, ER_SLEEP_ATTN, ER_SLEEP_WORKMEM
- ER_SLEEP_EPISODIC, ER_DEPRESSION_WORKMEM, ER_DEPRESSION_EXEC
- ER_ANXIETY_SELECTATTN, ER_DECONDITIONING_PROCSPEED

---

## Appendix C: Search Query Templates by Database

### PubMed E-Utilities API Call Template

```python
# Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
# Parameters:
#   db=pubmed
#   retmax=100
#   sort=relevance
#   term={QUERY}

import requests

def pubmed_search(query, max_results=100):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "term": query
    }
    response = requests.get(base, params=params)
    return response.json()
```

### OpenAlex API Call Template

```python
# Search: https://api.openalex.org/works?search={QUERY}&filter=from_publication_date:2010-01-01
# Filter by concepts for cancer + cognitive

def openalex_search(query, from_year=2010):
    base = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": f"from_publication_date:{from_year}-01-01",
        "sort": "relevance_score:desc",
        "per_page": 50
    }
    response = requests.get(base, params=params)
    return response.json()
```

### Semantic Scholar API Template

```python
# Search: https://api.semanticscholar.org/graph/v1/paper/search?query={QUERY}

def semantic_scholar_search(query, limit=50):
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,citationCount,externalIds"
    }
    response = requests.get(base, params=params)
    return response.json()
```

---

## Appendix D: Quality Filters for Extraction Priority

When results come back, prioritize papers for full extraction in this order:

1. **Meta-analyses with forest plots** — one paper provides multiple β/SE values
2. **RCTs in breast cancer with neuropsych outcomes** — closest match to model population
3. **RCTs in any cancer with biological + cognitive outcomes** — multi-edge evidence
4. **Prospective cohort with ≥3 timepoints** — temporal kernel data
5. **Large cross-sectional (n>200) with biomarker + cognitive data** — correlations
6. **Animal model studies with dose-response curves** — for emerging pathways
7. **Narrative reviews citing 50+ studies** — bibliography mining for additional papers

### Exclusion Criteria (Skip These)

- Case reports / case series (n < 5)
- Studies without any quantitative outcomes
- Studies in pediatric populations only (different mechanisms)
- Studies measuring only global cognition without domain breakdown
- Studies using only screening tools (MMSE) without comprehensive neuropsych

---

---

## Part 9: Manual Chatbox Retrieval Protocol

> **This is the primary operational workflow until the automated retrieval
> pipeline is proven end-to-end.** The automated modules (Stage 0–2) exist
> as code but have never run against live APIs. Use this manual protocol
> to collect PDFs via any AI chatbox, then hand them to Claude for
> CSV-based extraction via `EXTRACTION_PLAYBOOK.md`.

### 9.1 Integration Audit: What the Strategy Assumes vs What Exists

This strategy document (Parts 1–8) was designed as a search-query reference.
The research acquisition strategy (user's message, 2026-02-27) proposes a
rigorous end-to-end pipeline layered on top of it. Here is the alignment
status with the actual codebase:

| Strategy Concept | System Equivalent | Status |
|---|---|---|
| **Query Registry** (one row per edge) | `node_search_terms_v1` table + `query_generator.py` 7-workstream pattern | **Table populated: 504 terms across 63 nodes (230 synonyms, 119 instruments, 23 excludes)**. Query generator can now use real terms. |
| **Controlled Vocabulary** (Step 0) | `node_search_terms_v1.term` + `term_type` (PRIMARY, SYNONYM, ABBREVIATION, MESH_HEADING, INSTRUMENT, EXCLUDE) | **LOCKED — all 63 nodes have ≥5 terms. Canonical source: `generate_derived_seeds.py`** |
| **APS Scoring** | `aps_scorer.py` — `APS = 0.35·EdgeGap + 0.20·DesignBonus + 0.20·PopMatch + 0.15·Recency + 0.10·SourceQuality` | Built and coded |
| **Gap Auditing / Coverage Matrix** | `pathway_evidence_auditor.py` → `LandscapeReport` with per-edge sufficiency grades (A/B/C/D/F) | Built and coded |
| **Template B (EDGE_PACKET)** | Mixes static ontology (`edge_ontology_v1`) + search config (no DB home). Search parts → `node_search_terms_v1` + `APSQueryRequest` | **Don't create parallel format** — populate existing tables |
| **Template C (PAPER_PACKET)** | `edge_evidence_template.csv` (32 cols) + `meta.json` → loads into 71-col `edge_evidence_v1` | **Already operational** — 18 rows from 4 papers |
| **Template A (Protocol Header)** | Methods-section document — belongs in `docs/`, not a DB table | Write as markdown when needed for publication |
| **Template D (Chain Assembly)** | Algorithm chain compilation in `crci/algorithm/` already handles sign/time/instrument alignment | **Don't duplicate** — ensure input data is clean |
| **Extractability Screener (Pack B)** | `abstract_pre_extractor.py` (Stage 1) + `fulltext_extractability_scanner.py` (Stage 1.5) | **NOT BUILT** — highest-leverage missing code |
| **Paywall Classification** | `unpaywall.py` adapter + `OAStatus` enum exist; not wired as automatic post-step | Partially built |
| **Proxy Validity (R2 searches)** | No workstream in `query_generator.py` — `correlations` workstream searches biomarker intercorrelations, not proxy-to-latent R² | **Missing workstream** |
| **Extractability Triggers** in queries | `query_generator.py` does NOT append statistical terms (`β`, `95% CI`, `SE`, etc.) to PubMed queries | **Quick fix when automated pipeline is activated** |
| **Spine Papers** approach | = the existing `data/manual_uploads/` pathway with a prioritized queue | Already working |

### 9.2 The Manual Workflow (What You Actually Do)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE A: DISCOVER (Chatbox Session — any LLM)                  │
│                                                                 │
│  Load context:                                                  │
│    • This doc Parts 1-8 (search queries + keyword batteries)    │
│    • registries/EDGE_REGISTRY.csv (know what edges exist)       │
│    • Appendix B gap list (know what's missing)                  │
│    • EXTRACTION_LOG.md (know what's already extracted)           │
│                                                                 │
│  Ask the chatbox to run queries from Parts 2-7, prioritized:    │
│    1. Vertical slice edges first (§9.3 below)                   │
│    2. Meta-analyses and multi-edge papers first                 │
│    3. Append extractability triggers to queries:                │
│       AND ("95% CI" OR "standard error" OR "β" OR "effect size" │
│        OR "odds ratio" OR "regression" OR "mixed-effects")      │
│                                                                 │
│  Output: list of DOIs/PMIDs/titles with edge-mapping guesses    │
│                                                                 │
│  STOP RULE: stop when each vertical-slice edge has ≥2 candidates│
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE B: SCREEN (same or new Chatbox Session)                  │
│                                                                 │
│  For each candidate, ask the chatbox:                           │
│    "Does the abstract mention β, SE, CI, OR/HR with CI,         │
│     r with p, group means/SD, or mixed-model estimates?          │
│     Identify the exact phrases that imply extractability."       │
│                                                                 │
│  Kill papers that have NO numeric extractability cues.           │
│  Keep papers that mention:                                      │
│    • Effect sizes with uncertainty (β + CI, OR + CI)            │
│    • Regression tables, correlation matrices                    │
│    • Group means ± SD/SE by arm                                 │
│    • Mixed-effects model coefficients                           │
│                                                                 │
│  Output: filtered candidate list (~40-60% kill rate typical)    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE C: ACQUIRE (manual — browser)                            │
│                                                                 │
│  For each surviving candidate:                                  │
│    1. Check DOI → Unpaywall (https://unpaywall.org/) or         │
│       Semantic Scholar → "Open Access PDF" button                │
│    2. PMC: https://www.ncbi.nlm.nih.gov/pmc/articles/PMCID/    │
│    3. Google Scholar → "PDF" link on right side                 │
│    4. Author preprint repositories (ResearchGate, institutional)│
│    5. Sci-Hub as last resort for paywalled papers               │
│                                                                 │
│  Download PDF to: data/manual_uploads/pdfs/[doi-slug].pdf      │
│                                                                 │
│  Classification (deterministic, not guesswork):                 │
│    • Open:       PMC full text OR publisher OA license          │
│    • Likely OA:  Institutional repo / accepted manuscript       │
│    • Paywalled:  Everything else                                │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE D: EXTRACT (Claude — this repo's extraction workflow)    │
│                                                                 │
│  Follow EXTRACTION_PLAYBOOK.md Steps 0-9 exactly.              │
│  The playbook is the authoritative extraction reference.        │
│                                                                 │
│  Per paper, Claude needs:                                       │
│    • The PDF (attached or pasted as text)                       │
│    • extraction_ref/02_CHATBOX_CONTEXT.md (pinned)              │
│    • registries/EDGE_REGISTRY.csv (validate edges)              │
│    • registries/INSTRUMENT_REGISTRY.csv (validate instruments)  │
│    • registries/NODE_REGISTRY.csv (validate nodes)              │
│    • EXTRACTION_LOG.md (avoid duplicates)                       │
│                                                                 │
│  Output:                                                        │
│    • data/manual_uploads/structured/[doi-slug]/*.csv            │
│    • data/manual_uploads/pdfs/[doi-slug].meta.json              │
│    • EXTRACTION_LOG.md entry (append at top)                    │
│                                                                 │
│  Then run: python scripts/load_evidence_into_db.py --verbose    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE E: AUDIT (Claude — gap review)                           │
│                                                                 │
│  After extracting a batch (5-10 papers):                        │
│    1. Run: python scripts/load_evidence_into_db.py --verbose    │
│    2. Check edge coverage: SELECT edge_relation_id,             │
│       COUNT(*) FROM edge_evidence_v1 GROUP BY 1                 │
│    3. Compare to Appendix B gap list                            │
│    4. Identify still-empty edges in the vertical slice          │
│    5. Return to Phase A with updated gap priorities              │
│                                                                 │
│  STOP when vertical slice has ≥1 evidence row per edge          │
│  and ≥1 higher-grade record (RCT/longitudinal) per              │
│  decision-critical edge.                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Vertical Slice Paper Targets (Start Here)

The vertical slice covers **Sleep/Activity → HPA → Neuroplasticity + OIC → Cognition**.
These are the concrete edges to fill, with recommended spine papers.

#### Spine Papers (OA or likely obtainable — extract these first)

| Paper | Year | Edges Covered | Access |
|-------|------|---------------|--------|
| Tell et al. — breast cancer; diary sleep + salivary cortisol | 2014 | ER_SLEEP_CORTISOL, sleep↔HPA | Likely OA |
| Cheung et al. — multicenter cohort; cytokines + FACT-Cog + objective domains | 2015 | ER_CHEMO_IL6, ER_CHEMO_CRP, ER_OIC_*, inflammation↔cognition | Likely OA |
| Henneghan et al. — cytokine multivariate + cognition | 2018 | ER_IL6_OIC, ER_OIC_PROCSPEED, covariance structure | Likely OA |
| Kesler et al. — inflammation ↔ hippocampal volume ↔ memory | 2013 | ER_OIC_EPISODIC, mechanistic bridge | Likely OA |
| Ng et al. — plasma BDNF longitudinal + FACT-Cog in AYA cancer | 2023 | ER_BDNF_NEUROPLAST, BDNF↔cognition | OA (Sci Rep) |
| Hartman et al. — PA intervention + biomarkers (BDNF, CRP) | 2019 | ER_ACTIVITY_BDNF, ER_ACTIVITY_CRP | OA (JMIR) |
| Garland et al. — CBT-I RCT + CRCI + insomnia mediation | 2024 | ER_SLEEP_*, sleep→cognition | JCO |
| Adam et al. — diurnal cortisol slope meta-analysis | 2017 | ER_CORTISOL_HPA, cortisol metric anchoring | Likely paywalled |
| Szuhany et al. — exercise → BDNF meta-analysis | 2015 | ER_ACTIVITY_BDNF, direct-effect benchmark | Check OA |
| Klein et al. — peripheral ↔ central BDNF validity | 2011 | Proxy validity: BDNF R² | Check OA |

#### Vertical Slice Edges and Coverage Targets

| Edge ID | Source → Target | Evidence Status | Priority |
|---------|----------------|-----------------|----------|
| ER_SLEEP_CORTISOL | Sleep → Cortisol | k=0 | **CRITICAL** |
| ER_ACTIVITY_BDNF | Activity → BDNF | k=0 | **CRITICAL** |
| ER_ACTIVITY_IL6 | Activity → IL-6 | k=0 | **CRITICAL** |
| ER_ACTIVITY_CRP | Activity → CRP | k=0 | **CRITICAL** |
| ER_ACTIVITY_CORTISOL | Activity → Cortisol | k=0 | **CRITICAL** |
| ER_CHEMO_IL6 | Chemo → IL-6 | k=0 | **CRITICAL** |
| ER_CHEMO_CRP | Chemo → CRP | k=0 | **CRITICAL** |
| ER_IL6_OIC | IL-6 → OIC pathway | k=0 | HIGH |
| ER_CRP_OIC | CRP → OIC pathway | k=0 | HIGH |
| ER_BDNF_NEUROPLAST | BDNF → Neuroplasticity | k=0 | HIGH |
| ER_CORTISOL_HPA | Cortisol → HPA pathway | k=0 | HIGH |
| ER_OIC_PROCSPEED | OIC → Processing Speed | k=0 | HIGH |
| ER_OIC_WORKMEM | OIC → Working Memory | k=0 | HIGH |
| ER_OIC_EPISODIC | OIC → Episodic Memory | k=0 | HIGH |
| ER_NEUROPLAST_EPISODIC | Neuroplast → Episodic Memory | k=0 | HIGH |
| ER_NEUROPLAST_WORKMEM | Neuroplast → Working Memory | k=0 | HIGH |
| ER_HPA_EPISODIC | HPA → Episodic Memory | k=0 | MODERATE |
| ER_HPA_WORKMEM | HPA → Working Memory | k=0 | MODERATE |
| ER_HPA_SLEEP | HPA → Sleep (feedback) | k=0 | MODERATE |
| ER_OIC_FATIGUE | OIC → Fatigue | k=0 | MODERATE |

### 9.4 Chatbox Prompt Templates (Copy-Paste Ready)

#### Prompt A — Edge Discovery (use per edge or per cluster of related edges)

```
I'm building a Bayesian causal model of chemotherapy-related cognitive impairment (CRCI).
I need to find papers with EXTRACTABLE quantitative effects (β + SE or CI, correlation
+ p-value, group means ± SD/SE) for a specific causal edge.

EDGE: [SOURCE_NODE] → [TARGET_NODE]
Example: Physical activity level → Plasma BDNF concentration

SEARCH TERMS for source: [paste synonym bundle]
SEARCH TERMS for target: [paste synonym bundle]

POPULATION: Cancer patients or survivors (any cancer type; breast cancer preferred)
DESIGN PRIORITY: Meta-analysis > RCT > longitudinal cohort > cross-sectional
DATE RANGE: 2010-2026 preferred, 2000-2009 for foundational papers

EXTRACTABILITY REQUIREMENT: Paper must report at least one of:
  - β coefficient with SE or 95% CI
  - Correlation (r) with p-value and N
  - Group means ± SD by arm (allows Cohen's d computation)
  - Odds ratio or hazard ratio with 95% CI
  - Mixed-effects model coefficients with standard errors

For each paper found, provide:
  1. Full citation (authors, year, journal, DOI if available)
  2. Study design and sample size
  3. Which of the above extractable statistics it likely contains
  4. Open access status (PMC, publisher OA, or paywalled)

Find 5-10 candidates. Prioritize papers that cover MULTIPLE edges
(multi-biomarker panels, multi-domain cognitive batteries).
```

#### Prompt B — Extractability Screen (use on abstract/results snippet)

```
Given this abstract, does the paper report any of the following extractable
statistics? Identify the EXACT phrases that indicate extractability:

  - β, B, or regression coefficient with SE or CI
  - Odds ratio (OR) or hazard ratio (HR) with 95% CI
  - Correlation coefficient (r) with p-value
  - Group means ± SD or SE by treatment arm
  - Cohen's d, Hedges' g, or other standardized effect size
  - Mixed-effects model estimates
  - ANOVA/ANCOVA F-statistics with effect sizes (η²)
  - Mediation path coefficients

Also note:
  - What cognitive tests or biomarker assays are mentioned?
  - What is the sample size?
  - Is this cancer-specific or general population?

If NONE of the above are detectable in the abstract, mark as
"LIKELY NOT EXTRACTABLE — narrative/mechanistic only."

ABSTRACT:
[paste abstract here]
```

#### Prompt C — Cortisol Metric Disambiguation

```
For studying HPA axis dysregulation in cancer patients, which cortisol metric
has the strongest evidence for predicting cognitive outcomes?

Compare these metrics:
  - Diurnal cortisol slope (DCS): rate of decline across day
  - Cortisol awakening response (CAR): spike 30-45min post-waking
  - Area under curve (AUCg, AUCi): total vs. reactive cortisol
  - Evening/bedtime cortisol: single-point measure

For EACH metric, provide:
  1. Number of studies in cancer populations using it
  2. Typical sampling protocol required (days, samples/day)
  3. Strength of association with cognitive/fatigue/sleep outcomes
  4. Which cancer populations it's been studied in

I need to decide which to use as the primary operationalization for
NODE_BIO_CORTISOL in our model. The current default is diurnal slope.
```

#### Prompt D — Proxy Validity Search (BDNF-specific)

```
Find studies quantifying the correlation between peripheral blood BDNF
(specifically PLASMA, not serum) and central nervous system BDNF or
hippocampal measures.

Report for each study:
  - Correlation coefficient (r) or R²
  - Sample matrix: plasma vs serum vs CSF vs brain tissue
  - Species: human, rat, pig
  - Condition: healthy, cancer, inflammatory, neurological
  - Assay type: ELISA, other

Key anchors I'm aware of:
  - Klein et al. 2011: R² = 0.44 (rats), R² = 0.41 (pigs) in healthy animals
  - Elfving et al. 2010: INVERSE correlation in genetic depression model

I specifically need evidence about whether plasma-central BDNF correlation
ATTENUATES under neuroinflammatory conditions (e.g., during chemotherapy),
because our model applies a 1.5× SE multiplier for BDNF proxy when
neuroinflammation is elevated.
```

#### Prompt E — Multi-Edge Paper Discovery

```
Find breast cancer survivor studies that measured MULTIPLE biomarkers AND
multiple cognitive domains simultaneously. I need multi-edge papers.

IDEAL PAPER PROFILE:
  - Population: breast cancer patients/survivors
  - Measures at least 2 of: IL-6, CRP, TNF-α, BDNF (plasma), cortisol
  - AND measures at least 2 of: processing speed, working memory,
    episodic memory, executive function, attention
  - Reports correlation matrix or multivariate regression
  - N ≥ 50

These papers are extremely high value because one paper can fill 5-20
edge_evidence rows simultaneously.

Find 5-10 candidates from 2015-2026.
```

### 9.5 Controlled Vocabulary — Locked Reference

> **Status: LOCKED** — 504 terms across 63 nodes loaded in `node_search_terms_v1`.
> Canonical source: `scripts/generate_derived_seeds.py` → DB table.

#### How to query for any node's terms

```sql
SELECT term, term_type FROM node_search_terms_v1
WHERE node_id = 'NODE_BIO_CORTISOL' AND active = 1
ORDER BY term_type, term;
```

#### Term types

| Type | Count | Purpose |
|------|------:|---------|
| `synonym` | 230 | Search expansion (MeSH variants, lay terms) |
| `instrument` | 119 | Auto-generated from `instrument_definitions_v1` |
| `primary` | 63 | One per node, canonical label |
| `mesh_heading` | 40 | NLM MeSH terms |
| `abbreviation` | 29 | Standard abbreviations (BDNF, CRP, etc.) |
| `exclude` | 23 | False-positive filters (drug names, unrelated conditions) |

#### Measurement caveats (9 biomarker nodes)

Stored in `NODE_SEARCH_CAVEATS` dict in `generate_derived_seeds.py`. Key caveats:

- **BDNF**: Plasma vs serum — serum reflects platelet degranulation, not central levels
- **Cortisol**: Slope vs CAR vs AUC are different constructs — record which
- **IL-6**: High-sensitivity assay (hs-IL-6) preferred
- **CRP**: hs-CRP preferred; standard CRP misses low-grade inflammation
- **TNF**: Short half-life — timing matters; plasma preferred over serum

#### Vertical-slice node bundles (quick copy-paste for chatbox)

```yaml
# ── Behavioral nodes ──
NODE_BEH_SLEEP_QUALITY:
  primary: "sleep quality"
  synonyms: "sleep behavior", "sleep habits", "sleep hygiene"
  mesh: "sleep"
  exclude: "sleep apnea"

NODE_BEH_PHYSICAL_ACTIVITY:
  primary: "physical activity"
  synonyms: "exercise", "aerobic exercise", "resistance training",
            "cardiorespiratory fitness", "step count", "MET-minutes"
  abbreviations: "MVPA", "VO2"
  instruments: "IPAQ", "GLTEQ", "ACCEL" (+ full names in DB)
  exclude: "physical therapy", "rehabilitation"

NODE_BEH_STRESS_MGMT:
  primary: "stress management"
  synonyms: "mindfulness", "meditation", "yoga", "CBSM",
            "relaxation training", "stress reduction"
  abbreviations: "MBSR"
  instruments: "PSS", "CDRISC", "IES-R", "LSC-R", "NEO-FFI"

NODE_BEH_COG_ACTIVITY:
  primary: "cognitive activity"
  synonyms: "brain training", "cognitive training", "cognitive stimulation",
            "cognitive engagement", "cognitive remediation"
  instruments: "CAQ"

NODE_BEH_DIET:
  primary: "diet"
  synonyms: "Mediterranean diet", "anti-inflammatory diet", "dietary intake",
            "dietary pattern", "nutrition"
  instruments: "MED-DIET"

# ── Biomarker nodes ──
NODE_BIO_CORTISOL:
  primary: "cortisol"
  synonyms: "salivary cortisol", "diurnal cortisol", "cortisol slope",
            "cortisol awakening response", "evening cortisol", "HPA axis",
            "cortisol AUCg", "cortisol AUCi", "cortisol rhythm"
  abbreviations: "CAR"
  mesh: "hydrocortisone"
  exclude: "cortisol injection", "hydrocortisone therapy"

NODE_BIO_BDNF:
  primary: "brain-derived neurotrophic factor"
  synonyms: "plasma BDNF", "serum BDNF"
  abbreviations: "BDNF"
  instruments: "BDNF-PLASMA"
  exclude: "BDNF gene therapy", "BDNF knockout"

NODE_BIO_IL6:
  primary: "interleukin-6"
  synonyms: "interleukin 6", "plasma IL-6", "serum IL-6"
  abbreviations: "IL-6", "IL6"
  instruments: "IL6-PLASMA"
  exclude: "tocilizumab", "IL-6 receptor antagonist"

NODE_BIO_CRP:
  primary: "C-reactive protein"
  synonyms: "high-sensitivity CRP", "high-sensitivity C-reactive protein"
  abbreviations: "CRP", "hs-CRP"
  instruments: "CRP-HS"

NODE_BIO_TNF:
  primary: "tumor necrosis factor alpha"
  synonyms: "plasma TNF"
  abbreviations: "TNF", "TNF-alpha", "TNF-α", "TNFα"
  instruments: "TNF-PLASMA"
  exclude: "infliximab", "etanercept", "anti-TNF therapy"

# ── Pathway nodes ──
NODE_PATH_HPA:
  primary: "HPA axis"
  synonyms: "hypothalamic-pituitary-adrenal axis", "HPA axis dysregulation",
            "neuroendocrine stress response", "adrenal function"
  exclude: "Cushing syndrome", "Addison disease"

NODE_PATH_NEUROPLASTICITY:
  primary: "neuroplasticity"
  synonyms: "neural plasticity", "brain plasticity", "neuronal plasticity",
            "synaptic plasticity"

NODE_PATH_OIC:
  primary: "neuroinflammation"
  synonyms: "oxidative inflammatory cascade", "brain inflammation",
            "central inflammation", "neuroinflammatory response",
            "oxidative stress brain"
  exclude: "traumatic brain injury", "multiple sclerosis"

NODE_PATH_NEUROGENESIS:
  primary: "neurogenesis"
  synonyms: "adult neurogenesis", "hippocampal neurogenesis",
            "neural stem cells", "neural progenitor cells"

# ── Cognitive domain nodes ──
NODE_COG_PROC_SPEED:
  primary: "processing speed"
  synonyms: "information processing speed", "psychomotor speed",
            "reaction time", "simple RT", "coding task"
  instruments: "TMT-B" (+ full names in DB)

NODE_COG_WORK_MEM:
  primary: "working memory"
  synonyms: "n-back", "letter-number sequencing",
            "short-term memory", "spatial working memory"
  instruments: "DIGIT-SPAN", "ONEBACK"

NODE_COG_EPISODIC_MEM:
  primary: "episodic memory"
  synonyms: "verbal memory", "verbal learning", "delayed recall",
            "recognition memory", "word list recall"
  instruments: "HVLTR", "ISL-DR"
  exclude: "Alzheimer disease", "dementia"

NODE_COG_ATTN_SUSTAINED:
  primary: "sustained attention"
  synonyms: "concentration", "vigilance", "continuous performance",
            "attentional function"
  instruments: "CPT"

# ── Symptom nodes ──
NODE_SYM_FATIGUE:
  primary: "cancer-related fatigue"
  synonyms: "fatigue", "cancer fatigue", "persistent fatigue"
  abbreviations: "CRF"
  instruments: "BFI", "FACIT-Fatigue", "LFS"
  exclude: "chronic fatigue syndrome", "myalgic encephalomyelitis"

NODE_SYM_DEPRESSION:
  primary: "depression"
  synonyms: "depressed mood", "depressive symptoms", "major depressive disorder"
  instruments: "PHQ9", "PHQ2", "CESD"
  exclude: "bipolar disorder", "schizophrenia"

NODE_SYM_ANXIETY:
  primary: "anxiety"
  synonyms: "anxiety symptoms", "cancer anxiety", "generalized anxiety"
  instruments: "GAD7", "STAI-S"

NODE_SYM_SLEEP_DISRUPTION:
  primary: "sleep disruption"
  synonyms: "insomnia", "sleep disturbance", "sleep efficiency",
            "sleep fragmentation"
  instruments: "PSQI", "ISI", "GSDS"
  exclude: "sleep apnea"
```

### 9.6 Evidence Relationship Classes (Search Organization)

When running searches, organize by relationship type across the DAG layers.
This prevents random searching and ensures mechanistic chains are complete.

| Class | What You're Looking For | Layer | Design Priority |
|-------|------------------------|-------|-----------------|
| **R0** | Treatment → biomarkers/behaviors | 0→1, 0→2 | Prospective cohorts (pre→during→post-tx) |
| **R1** | Behaviors → biomarkers (intervention levers) | 1→2 | RCTs of CBT-I/exercise/diet/MBSR with biomarker outcomes |
| **R2** | Biomarker → latent pathway validity | 2→3 | Multi-marker studies; correlation matrices; proxy R² |
| **R3** | Pathways → cognition/symptoms | 3→4, 3→5 | Biomarker-predicting-cognition longitudinal; mediation models |
| **R4** | Subjective ↔ objective dissociation | 4↔5 | Multivariable models with both + fatigue/mood |
| **R5** | Feedback / bidirectional coupling | Various | Cross-lagged panels; longitudinal bidirectional associations |
| **R-proxy** | Peripheral-to-central biomarker validity | 2↔latent | Multi-matrix studies; translational animal-to-human |

**R-proxy is a gap in the current system.** No workstream in `query_generator.py`
targets proxy validity evidence. When the automated pipeline is activated, add
Workstream 8 for this. For now, use Prompt D (§9.4) manually.

### 9.7 Per-Session Checklist (Print This)

Before starting a chatbox discovery session:
- [ ] Read `EXTRACTION_LOG.md` — know what's already in the system
- [ ] Read Appendix B of this doc — know which edges have zero evidence
- [ ] Pick 3-5 target edges for this session
- [ ] Query `node_search_terms_v1` for those nodes (or copy from §9.5 bundles)
- [ ] Decide: cancer-specific pass first, then general-population if sparse

During the session:
- [ ] Use Prompt A (§9.4) for each edge cluster
- [ ] Use Prompt B (§9.4) to screen each candidate's abstract
- [ ] Record DOI, title, year, likely edges, OA status for each keeper
- [ ] Note which edges each paper covers (build coverage matrix mentally)
- [ ] Stop when each target edge has ≥2 candidates with extractability cues

After discovery, before extraction:
- [ ] Collect all PDFs (Phase C of §9.2)
- [ ] For each PDF, create `data/manual_uploads/pdfs/[doi-slug].pdf`
- [ ] Start a new Claude session for extraction
- [ ] Follow `EXTRACTION_PLAYBOOK.md` Steps 0-9 per paper
- [ ] Update `EXTRACTION_LOG.md` after each paper

After a batch (5-10 papers):
- [ ] Run `python scripts/load_evidence_into_db.py --verbose`
- [ ] Query edge coverage
- [ ] Compare to gap list — update priorities for next session

---

*Document version: 2.1*  
*Updated: 2026-02-28*  
*Covers: 63 nodes, 142 edges, 21 pathways, 67 instruments*  
*Vocabulary: LOCKED — 504 terms in node_search_terms_v1 (23 excludes, 9 caveats)*  
*Part 9 updated: §9.5 now reflects locked DB vocabulary*  
*Estimated total search queries: ~200 (across all databases)*  
*Expected yield: 300-500 unique papers for extraction*
