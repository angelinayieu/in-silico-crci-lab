# AI Retrieval Session Guide — Systematic Literature Search

> **Purpose:** Ready-to-paste prompts and session instructions for using AI deep research
> tools (ChatGPT Deep Research, Perplexity Pro, Gemini Deep Research, Claude) to
> systematically find papers that feed into the CRCI triage pipeline (Stage 0).
>
> **Companion docs:**
> - `DEEP_RESEARCH_STRATEGY.md` — Full search keyword batteries (reference, not session-ready)
> - `docs/05_data_management/AUTOMATED_RETRIEVAL_PLAN.md` Part 14 — Pipeline stages
> - `extraction_ref/02_CHATBOX_CONTEXT.md` — For extraction sessions (Stage 2), NOT this doc

---

## Quick Start

1. Pick a **session type** from the table below
2. Copy the **system prompt** (Section 1) into your AI chatbox
3. Copy the **session-specific prompt** (Section 3) into the same session
4. Collect the AI's output DOI/PMID list
5. Paste results into `data/retrieval_candidates/` as a `.jsonl` file (format in Section 4)
6. Run Stage 0: `python scripts/run_triage_sweep.py --stage 0 --input <file>`

---

## Session Planning Matrix

Run sessions in this order. Each session is independent (new chatbox window).

### Phase A: Vertical Slice First (DO THIS FIRST)

| Session | Target | Est. Papers | Priority |
|---------|--------|-------------|----------|
| A1 | Neuroinflammation pathway (M1) — meta-analyses + RCTs | 30-50 | CRITICAL |
| A2 | HPA axis pathway (M3) — cortisol → cognition | 20-40 | CRITICAL |
| A3 | BDNF / Neuroplasticity pathway (M4) — exercise → BDNF → cognition | 25-45 | CRITICAL |
| A4 | Sleep pathway (C1) — sleep → cognition in cancer | 20-35 | CRITICAL |
| A5 | Fatigue pathway (C2) — fatigue ↔ activity ↔ cognition | 20-35 | CRITICAL |
| A6 | Cross-pathway multi-domain studies (covers ≥3 pathways) | 15-25 | HIGH |
| A7 | Biomarker-cognition correlations (IL-6, CRP, BDNF, cortisol) | 20-40 | HIGH |

### Phase B: Instrument & Norms (after Phase A)

| Session | Target | Est. Papers | Priority |
|---------|--------|-------------|----------|
| B1 | Neuropsych test norms in cancer (TMT, HVLT-R, Digit Span, etc.) | 15-25 | HIGH |
| B2 | PRO instrument validation in cancer (FACIT-F, PHQ-9, PSQI, etc.) | 15-25 | HIGH |
| B3 | Biomarker reference ranges in cancer populations | 10-15 | MODERATE |

### Phase C: Remaining Pathways (after Phase B)

| Session | Target | Est. Papers | Priority |
|---------|--------|-------------|----------|
| C1 | Oxidative stress (M2) + DNA damage (M7) + Senescence (M9) | 15-30 | MODERATE |
| C2 | Myelin/white matter (M16) + Synaptic (M15) | 15-25 | MODERATE |
| C3 | Mood/affect (C3) — depression/anxiety → cognition | 15-25 | MODERATE |
| C4 | Metabolic (M13) + Vascular (C4) | 10-20 | MODERATE |
| C5 | Emerging pathways: Gut-brain (M8), Glymphatic (M10), BBB (M14), Epigenetic (M12), Dopaminergic (M17) | 10-20 | LOW |

### Phase D: Dose-Response & Temporal (after Phase C)

| Session | Target | Est. Papers | Priority |
|---------|--------|-------------|----------|
| D1 | Exercise dose-response for biomarkers + cognition | 10-20 | HIGH |
| D2 | Temporal recovery curves (pre → during → post chemo → survivorship) | 10-20 | HIGH |
| D3 | Effect modifiers (APOE, age, sex, cognitive reserve) | 10-15 | MODERATE |

---

## Section 1: System Prompt (Paste First in Every Session)

Copy this EXACTLY into the AI chatbox at session start. It's the "pinned context"
that tells the AI what output format you need.

```
You are a systematic literature search assistant for a Bayesian causal model
of Chemotherapy-Related Cognitive Impairment (CRCI).

YOUR TASK: Find published research papers that provide QUANTITATIVE evidence
for specific causal/associational relationships in cancer patients. I need
papers with extractable statistics (effect sizes, confidence intervals,
regression coefficients, correlations) — not narrative reviews.

OUTPUT FORMAT — For EVERY paper you find, output this exact structure:

PAPER: [sequential number]
TITLE: [full title]
AUTHORS: [first author et al., year]
JOURNAL: [journal name]
YEAR: [publication year]
DOI: [doi if available, or "NOT_FOUND"]
PMID: [PubMed ID if available, or "NOT_FOUND"]
DESIGN: [RCT | cohort | cross-sectional | meta-analysis | systematic_review | case-control | longitudinal]
CANCER_TYPE: [breast | colorectal | lung | mixed | other: specify]
SAMPLE_SIZE: [N, or "UNKNOWN"]
EDGE_IDS: [comma-separated list of CRCI edge IDs this paper likely covers — see my edge list below]
INSTRUMENTS: [comma-separated list of assessment instruments used]
EXTRACTABILITY: [HIGH: has tables with β/SE/CI | MODERATE: has some stats | LOW: mainly narrative]
KEY_FINDING: [1-2 sentence summary of the quantitative result]
ACCESS: [OA: open access | PAYWALLED | PREPRINT | UNKNOWN]

RULES:
1. Prefer papers with TABLES containing regression coefficients, odds ratios,
   hazard ratios, correlations, or standardized mean differences WITH confidence
   intervals or standard errors.
2. Prefer cancer-specific populations. If not available, well-established general
   population evidence is acceptable — flag it as "NON_CANCER_POP".
3. For each pathway, find papers in this priority order:
   meta-analyses → RCTs → prospective cohort → cross-sectional → animal/preclinical
4. Include NULL results too — a study finding no significant relationship is
   equally valuable for Bayesian priors.
5. DO NOT fabricate citations. If you're unsure about a DOI or PMID, put "UNVERIFIED".
6. Aim for 20-40 papers per session unless I specify otherwise.
7. For each paper, guess which EDGE_IDs from my model it covers by matching
   the source/target constructs (I'll provide the edge list with my query).
```

---

## Section 2: Edge ID Reference (Paste After System Prompt)

Paste this condensed edge reference so the AI can map papers to edges.
This is the same content as `extraction_ref/09_EDGE_IDS.md` but condensed
for chatbox context windows.

```
CRCI MODEL EDGE REFERENCE (143 edges)
Use these IDs in the EDGE_IDS field of your output.

--- LAYER 0→1: Treatment → Behavior ---
ER_CHEMO_ACTIVITY: chemotherapy → physical activity (negative)
ER_CHEMO_SLEEP: chemotherapy → sleep disruption (negative)
ER_CHEMO_DIET: chemotherapy → dietary quality (negative)
ER_TX_PHASE_ACTIVITY: treatment phase → activity level

--- LAYER 0→2: Treatment → Biomarkers ---
ER_CHEMO_IL6: chemotherapy → IL-6 elevation (positive)
ER_CHEMO_CRP: chemotherapy → CRP elevation (positive)
ER_CHEMO_TNF: chemotherapy → TNF-α elevation (positive)
ER_CHEMO_CORTISOL: chemotherapy → cortisol dysregulation
ER_CHEMO_BDNF: chemotherapy → BDNF reduction (negative)
ER_CHEMO_8OHDG: chemotherapy → oxidative DNA damage
ER_CHEMO_MDA: chemotherapy → lipid peroxidation
ER_CHEMO_GH2AX: chemotherapy → DNA double-strand breaks
ER_CHEMO_P16: chemotherapy → cellular senescence (p16)
ER_CHEMO_SHANNON: chemotherapy → gut microbiome diversity
ER_CHEMO_GLUCOSE: chemotherapy → glucose dysregulation
ER_CHEMO_NFL: chemotherapy → neurofilament light chain
ER_RADIATION_GH2AX: radiation → DNA double-strand breaks
ER_RADIATION_NFL: radiation → neurofilament light chain

--- LAYER 1→2: Behavior → Biomarkers ---
ER_ACTIVITY_IL6: physical activity → IL-6 (negative/reduces)
ER_ACTIVITY_CRP: physical activity → CRP (negative/reduces)
ER_ACTIVITY_BDNF: physical activity → BDNF (positive/increases)
ER_ACTIVITY_CORTISOL: physical activity → cortisol normalization
ER_ACTIVITY_GLUCOSE: physical activity → glucose regulation
ER_ACTIVITY_8OHDG: physical activity → oxidative damage reduction
ER_DIET_IL6: diet quality → IL-6 (anti-inflammatory)
ER_DIET_SHANNON: diet quality → gut microbiome diversity
ER_DIET_GLUCOSE: diet quality → glucose regulation
ER_DIET_MDA: diet quality → lipid peroxidation (reduction)
ER_STRESS_CORTISOL: stress management → cortisol normalization
ER_STRESS_IL6: stress management → IL-6 reduction
ER_SLEEP_CORTISOL: sleep quality → cortisol rhythm
ER_COGACTIVITY_BDNF: cognitive activity → BDNF

--- LAYER 2→3: Biomarkers → Pathways ---
ER_IL6_OIC: IL-6 → neuroinflammation pathway
ER_CRP_OIC: CRP → neuroinflammation pathway
ER_TNF_OIC: TNF-α → neuroinflammation pathway
ER_8OHDG_OIC: oxidative DNA damage → OIC pathway
ER_MDA_OIC: lipid peroxidation → OIC pathway
ER_BDNF_NEUROPLAST: BDNF → neuroplasticity pathway
ER_BDNF_NEUROGENESIS: BDNF → neurogenesis pathway
ER_CORTISOL_HPA: cortisol → HPA axis pathway
ER_P16_SENESCENCE: p16INK4a → cellular senescence pathway
ER_GH2AX_DNA: γ-H2AX → DNA damage pathway
ER_SHANNON_GUTBRAIN: gut diversity → gut-brain axis
ER_GLUCOSE_METABOLIC: glucose → metabolic pathway
ER_NFL_BBB: NfL → BBB disruption pathway
ER_NFL_MYELIN: NfL → myelin damage pathway

--- LAYER 3→4: Pathways → Symptoms ---
ER_OIC_FATIGUE: neuroinflammation → fatigue
ER_OIC_DEPRESSION: neuroinflammation → depression
ER_OIC_PAIN: neuroinflammation → pain
ER_HPA_SLEEP: HPA dysregulation → sleep disruption
ER_HPA_DEPRESSION: HPA dysregulation → depression
ER_HPA_ANXIETY: HPA dysregulation → anxiety
ER_DOPAMINE_FATIGUE: dopaminergic dysfunction → fatigue

--- LAYER 3→5: Pathways → Cognition ---
ER_OIC_PROCSPEED: neuroinflammation → processing speed
ER_OIC_WORKMEM: neuroinflammation → working memory
ER_OIC_EPISODIC: neuroinflammation → episodic memory
ER_OIC_ATTNSUST: neuroinflammation → sustained attention
ER_HPA_EPISODIC: HPA axis → episodic memory
ER_HPA_WORKMEM: HPA axis → working memory
ER_NEUROPLAST_EPISODIC: neuroplasticity → episodic memory
ER_NEUROPLAST_WORKMEM: neuroplasticity → working memory
ER_NEUROGENESIS_EPISODIC: neurogenesis → episodic memory
ER_SYNAPTIC_PROCSPEED: synaptic function → processing speed
ER_SYNAPTIC_WORKMEM: synaptic function → working memory
ER_SYNAPTIC_EXEC: synaptic function → executive function
ER_MYELIN_PROCSPEED: myelin integrity → processing speed
ER_MYELIN_VERBAL: myelin integrity → verbal fluency
ER_MYELIN_LANGUAGE: myelin integrity → language
ER_DOPAMINE_INHIBITION: dopaminergic → inhibition/exec function
ER_METABOLIC_PROCSPEED: metabolic → processing speed

--- LAYER 4→5: Symptoms → Cognition ---
ER_FATIGUE_ATTN: fatigue → sustained attention
ER_FATIGUE_PROCSPEED: fatigue → processing speed
ER_SLEEP_ATTN: sleep disruption → attention
ER_SLEEP_WORKMEM: sleep disruption → working memory
ER_SLEEP_EPISODIC: sleep disruption → episodic memory
ER_DEPRESSION_WORKMEM: depression → working memory
ER_DEPRESSION_EXEC: depression → executive function
ER_ANXIETY_SELECTATTN: anxiety → selective attention
ER_DECONDITIONING_PROCSPEED: deconditioning → processing speed

--- FEEDBACK EDGES ---
ER_FATIGUE_ACTIVITY: fatigue → physical activity (feedback, negative)
ER_ACTIVITY_FATIGUE_DIRECT: physical activity → fatigue (direct, negative)
ER_DEPRESSION_SLEEP: depression ↔ sleep (bidirectional)
ER_ANXIETY_SLEEP: anxiety ↔ sleep (bidirectional)

--- CROSS-PATHWAY EDGES ---
ER_IL6_BDNF_CROSS: IL-6 → BDNF suppression (cross-pathway)
ER_AGE_BDNF: age → BDNF decline (modifier)
ER_AGE_PROCSPEED: age → processing speed decline (modifier)
ER_COGRES_COMPOSITE: cognitive reserve → composite cognition (modifier)
```

---

## Section 3: Session-Specific Prompts

### Session A1: Neuroinflammation Pathway (M1)

**Paste after the system prompt + edge reference:**

```
SEARCH TASK: Find papers providing quantitative evidence for the
NEUROINFLAMMATION pathway in chemotherapy-related cognitive impairment.

TARGET EDGES (prioritize papers covering these):
- ER_CHEMO_IL6, ER_CHEMO_CRP, ER_CHEMO_TNF (chemo → inflammatory markers)
- ER_IL6_OIC, ER_CRP_OIC, ER_TNF_OIC (biomarkers → neuroinflammation)
- ER_OIC_PROCSPEED, ER_OIC_WORKMEM, ER_OIC_EPISODIC, ER_OIC_ATTNSUST (pathway → cognition)
- ER_OIC_FATIGUE, ER_OIC_DEPRESSION, ER_OIC_PAIN (pathway → symptoms)

SEARCH STRATEGY:
1. FIRST find meta-analyses/systematic reviews of inflammation and cognition in cancer
   (these are highest value — one paper covers many edges)
2. THEN find RCTs where inflammatory biomarkers (IL-6, CRP, TNF-α) were measured
   alongside cognitive outcomes in cancer patients
3. THEN find prospective cohort studies tracking cytokine trajectories during/after
   chemotherapy with cognitive assessments
4. THEN find cross-sectional studies correlating inflammation markers with specific
   cognitive domains (processing speed, memory, executive function) in cancer survivors

SPECIFIC SEARCH TERMS TO USE:
PubMed: ("interleukin-6" OR "IL-6" OR "C-reactive protein" OR "CRP" OR "TNF-alpha"
OR "tumor necrosis factor" OR "cytokines" OR "neuroinflammation")
AND ("cognitive" OR "cognition" OR "neuropsychological" OR "CRCI" OR "chemobrain"
OR "processing speed" OR "memory" OR "executive function")
AND ("cancer" OR "chemotherapy" OR "breast cancer" OR "cancer survivors")

KEY INSTRUMENTS to look for: TMT-A, TMT-B (processing speed); HVLT-R, RAVLT
(episodic memory); Digit Span (working memory); Stroop (executive function);
FACT-Cog (subjective cognition); FACIT-F (fatigue)

KNOWN KEY PAPERS (find these + everything that cites them):
- Felger et al., 2020, Mol Psychiatry
- Bower, 2014, Brain Behav Immun
- Ganz et al., 2013 (cytokine profiles + cognitive trajectories)
- Pomykala et al., 2013 (IL-6 + brain structure in breast cancer)
- Janelsins et al., 2012 (cytokines + cognition in breast cancer)

TARGET: 30-50 papers. Include null results.
```

---

### Session A2: HPA Axis Pathway (M3)

```
SEARCH TASK: Find papers providing quantitative evidence for the
HPA AXIS DYSREGULATION pathway in cancer-related cognitive impairment.

TARGET EDGES:
- ER_CHEMO_CORTISOL (chemo → cortisol dysregulation)
- ER_STRESS_CORTISOL (stress management → cortisol normalization)
- ER_CORTISOL_HPA (cortisol → HPA pathway activation)
- ER_HPA_SLEEP, ER_HPA_DEPRESSION, ER_HPA_ANXIETY (HPA → symptoms)
- ER_HPA_EPISODIC, ER_HPA_WORKMEM (HPA → cognition)
- ER_SLEEP_CORTISOL (sleep → cortisol rhythm, feedback)

SEARCH STRATEGY:
1. Meta-analyses of cortisol and cognition (cancer or stress populations)
2. Studies measuring diurnal cortisol slope (DCS) + cognitive outcomes in cancer
3. MBSR/mindfulness RCTs measuring both cortisol AND cognition in cancer
4. Studies of cortisol-hippocampal-memory axis in cancer patients
5. Studies of DHEA-S neuroprotection in cancer or aging

SEARCH TERMS:
("cortisol" OR "diurnal cortisol slope" OR "cortisol awakening response" OR "CAR"
OR "HPA axis" OR "hypothalamic-pituitary-adrenal" OR "cortisol AUC"
OR "DHEA" OR "DHEA-S")
AND ("cognitive" OR "memory" OR "hippocampal" OR "neuropsychological"
OR "processing speed" OR "executive function")
AND ("cancer" OR "breast cancer" OR "chemotherapy" OR "cancer survivors")

ALSO SEARCH:
("mindfulness" OR "MBSR" OR "stress reduction" OR "meditation")
AND ("cortisol") AND ("cancer") AND ("randomized" OR "trial")

KEY INSTRUMENTS: Salivary cortisol assays, HVLT-R, RAVLT (episodic memory),
PHQ-9 (depression), GAD-7 (anxiety), PSQI (sleep)

KNOWN KEY PAPERS:
- Bower et al., 2005 — cortisol and fatigue in cancer
- Sephton et al., 2013 — diurnal cortisol and survival
- Tell et al., 2014 — cortisol and cognition in cancer
- Adam et al., 2017 — DCS meta-analysis
- Lengacher et al., 2019 — MBSR + cortisol in breast cancer

TARGET: 20-40 papers. Include null results.
```

---

### Session A3: BDNF / Neuroplasticity Pathway (M4)

```
SEARCH TASK: Find papers providing quantitative evidence for the
NEUROPLASTICITY / BDNF pathway linking exercise to cognition in cancer.

TARGET EDGES:
- ER_ACTIVITY_BDNF (physical activity → BDNF increase)
- ER_COGACTIVITY_BDNF (cognitive activity → BDNF)
- ER_BDNF_NEUROPLAST, ER_BDNF_NEUROGENESIS (BDNF → pathway activation)
- ER_NEUROPLAST_EPISODIC, ER_NEUROPLAST_WORKMEM (neuroplasticity → cognition)
- ER_NEUROGENESIS_EPISODIC (neurogenesis → episodic memory)
- ER_IL6_BDNF_CROSS (IL-6 suppresses BDNF — cross-pathway)
- ER_AGE_BDNF (age moderates BDNF response)

SEARCH STRATEGY:
1. Meta-analyses of exercise → BDNF (cancer and general population)
2. RCTs measuring BDNF + cognitive outcomes in cancer patients
3. Mediation studies: exercise → BDNF → cognition (full chain)
4. Studies of plasma/serum BDNF and cognitive domains in cancer
5. APOE × BDNF × exercise interaction studies

CRITICAL DISTINCTION: Plasma BDNF vs Serum BDNF measurements are not
interchangeable. Note which was used in each paper.

SEARCH TERMS:
("brain-derived neurotrophic factor" OR "BDNF" OR "plasma BDNF" OR "serum BDNF")
AND ("exercise" OR "physical activity" OR "aerobic" OR "resistance training"
OR "cognitive training")
AND ("cognitive" OR "memory" OR "hippocampal" OR "neuroplasticity"
OR "neuropsychological")

For cancer-specific:
ADD: AND ("cancer" OR "chemotherapy" OR "breast cancer" OR "cancer survivors")

For full chain mediation:
("exercise" OR "physical activity") AND ("BDNF")
AND ("cognitive" OR "memory") AND ("mediation" OR "mediator" OR "mechanism")

KEY INSTRUMENTS: HVLT-R, RAVLT (episodic memory), Digit Span (working memory),
BDNF ELISA (specify plasma vs serum)

KNOWN KEY PAPERS:
- Szuhany et al., 2015, J Psychiatr Res (exercise → BDNF meta-analysis)
- Erickson et al., 2011, PNAS (exercise, hippocampal volume, BDNF)
- Northey et al., 2019 (exercise + cognition)
- Zimmer et al., 2016 (BDNF + exercise meta-analysis)

TARGET: 25-45 papers. Include general-population exercise → BDNF studies
if cancer-specific evidence is sparse — flag as NON_CANCER_POP.
```

---

### Session A4: Sleep Pathway (C1)

```
SEARCH TASK: Find papers providing quantitative evidence for the
SLEEP DISRUPTION pathway affecting cognition in cancer patients.

TARGET EDGES:
- ER_CHEMO_SLEEP (chemotherapy → sleep disruption)
- ER_HPA_SLEEP (HPA axis → sleep disruption)
- ER_DEPRESSION_SLEEP, ER_ANXIETY_SLEEP (mood → sleep, bidirectional)
- ER_SLEEP_CORTISOL (sleep → cortisol rhythm)
- ER_SLEEP_ATTN, ER_SLEEP_WORKMEM, ER_SLEEP_EPISODIC (sleep → cognition)
- ER_SLEEP_FATIGUE (sleep → fatigue)

SEARCH STRATEGY:
1. Meta-analyses of sleep and cognition in cancer survivors
2. CBT-I RCTs measuring cognitive outcomes in cancer patients
3. Bright light therapy studies in cancer (circadian + cognition)
4. Studies correlating PSQI/ISI scores with neuropsych performance in cancer
5. Mechanistic studies: sleep → glymphatic → neuroinflammation → cognition

SEARCH TERMS:
("sleep" OR "insomnia" OR "sleep quality" OR "sleep disturbance" OR "circadian"
OR "PSQI" OR "Pittsburgh Sleep Quality" OR "ISI" OR "Insomnia Severity Index")
AND ("cognitive" OR "cognition" OR "neuropsychological" OR "attention"
OR "memory" OR "processing speed" OR "executive function")
AND ("cancer" OR "breast cancer" OR "cancer survivors" OR "chemotherapy")

For interventions:
("CBT-I" OR "cognitive behavioral therapy for insomnia" OR "sleep hygiene"
OR "bright light therapy" OR "light exposure" OR "melatonin")
AND ("cancer") AND ("cognitive" OR "sleep")

KEY INSTRUMENTS: PSQI, ISI (sleep); Actigraphy; TMT, HVLT-R, Digit Span (cognition)

KNOWN KEY PAPERS:
- Savard & Morin, 2001 — insomnia in cancer
- Garland et al., 2014 — CBT-I in cancer survivors
- Irwin, 2015 — sleep and inflammation
- Xie et al., 2013, Science — glymphatic clearance during sleep

TARGET: 20-35 papers.
```

---

### Session A5: Cancer-Related Fatigue Pathway (C2)

```
SEARCH TASK: Find papers providing quantitative evidence for the
CANCER-RELATED FATIGUE pathway and its bidirectional relationship with
physical activity and cognition.

TARGET EDGES:
- ER_OIC_FATIGUE (neuroinflammation → fatigue)
- ER_PAIN_FATIGUE (pain → fatigue)
- ER_SLEEP_FATIGUE (sleep disruption → fatigue)
- ER_FATIGUE_ACTIVITY (fatigue → reduced activity — feedback loop)
- ER_ACTIVITY_FATIGUE_DIRECT (exercise → fatigue reduction — intervention)
- ER_FATIGUE_ATTN, ER_FATIGUE_PROCSPEED (fatigue → cognition)
- ER_DECONDITIONING_PROCSPEED (deconditioning → processing speed)

SEARCH STRATEGY:
1. Meta-analyses of exercise interventions for cancer-related fatigue
2. Studies measuring fatigue + cognitive domains simultaneously in cancer
3. Mediation studies: inflammation → fatigue → cognition chain
4. Dose-response: exercise dose (MET-min/week) vs fatigue reduction
5. Fatigue ↔ activity feedback loop studies (bidirectional)

SEARCH TERMS:
("cancer-related fatigue" OR "CRF" OR "cancer fatigue" OR "FACIT-Fatigue"
OR "fatigue" AND "cancer")
AND ("cognitive" OR "attention" OR "processing speed" OR "concentration"
OR "neuropsychological")

For exercise interventions:
("exercise" OR "physical activity" OR "aerobic" OR "resistance training")
AND ("fatigue" OR "cancer-related fatigue")
AND ("cancer" OR "breast cancer" OR "cancer survivors")
AND ("randomized" OR "trial" OR "meta-analysis")

For mediation:
("mediation" OR "mediator" OR "indirect effect" OR "path analysis")
AND ("fatigue") AND ("inflammation" OR "IL-6" OR "cytokines")
AND ("cognitive")

KEY INSTRUMENTS: FACIT-F, BFI (fatigue); Actigraphy, IPAQ (activity);
TMT-A/B (processing speed); CPT (sustained attention)

KNOWN KEY PAPERS:
- Mustian et al., 2017 — exercise for CRF (large meta-analysis)
- Bower, 2014 — CRF biological mechanisms
- Berger et al., 2015 — CRF clinical practice guidelines

TARGET: 20-35 papers.
```

---

### Session A6: Multi-Domain / Multi-Pathway Studies

```
SEARCH TASK: Find studies that measure MULTIPLE domains simultaneously
(biomarkers + cognitive tests + symptoms + behavior) in cancer patients.
These are the highest-value papers because they provide evidence for
many edges at once and enable path analysis.

WHAT MAKES A PAPER HIGH VALUE HERE:
- Measures ≥3 of: inflammatory biomarker, cognitive test battery, sleep/fatigue,
  physical activity, depression/anxiety, cortisol, BDNF
- Performs mediation analysis or path analysis or SEM
- Has large enough sample for multivariate models

SEARCH TERMS:
("path analysis" OR "structural equation" OR "SEM" OR "mediation analysis"
OR "multiple mediators")
AND ("cognitive" OR "neuropsychological" OR "CRCI" OR "chemobrain")
AND ("cancer" OR "breast cancer" OR "cancer survivors")

Also:
("multi-domain" OR "comprehensive assessment" OR "battery")
AND ("biomarkers" OR "cytokines" OR "cortisol" OR "BDNF")
AND ("neuropsychological" OR "cognitive")
AND ("cancer" OR "chemotherapy")

And:
("Oppegaard" OR "Janelsins" OR "Ahles" OR "Wefel" OR "Kesler" OR "Mandelblatt"
OR "ICCTF" OR "International Cognition and Cancer Task Force")
AND ("cognitive" OR "CRCI") AND ("longitudinal" OR "prospective" OR "trajectory")

For each paper, identify ALL edge_ids it covers — these papers often cover
5-15 edges if they have both biomarkers and cognitive domains.

TARGET: 15-25 papers. Quality over quantity here.
```

---

### Session A7: Biomarker → Cognition Direct Correlations

```
SEARCH TASK: Find studies reporting DIRECT QUANTITATIVE correlations between
peripheral blood biomarkers and specific cognitive domain test scores in
cancer patients/survivors.

I need r, β, or d values (with CIs or p-values) for these specific pairs:

HIGH PRIORITY:
1. Plasma IL-6 → Processing Speed (TMT-A, TMT-B, DSST)
2. Plasma IL-6 → Working Memory (Digit Span Backward)
3. Plasma IL-6 → Episodic Memory (HVLT-R, RAVLT)
4. hs-CRP → Processing Speed (any test)
5. TNF-α → Processing Speed (any test)
6. Plasma BDNF → Episodic Memory (HVLT-R, hippocampal)
7. Plasma BDNF → Working Memory (Digit Span)
8. Cortisol diurnal slope → Episodic Memory (any test)
9. Cortisol diurnal slope → Fatigue (FACIT-F, BFI)

MODERATE PRIORITY:
10. p16INK4a → Fatigue or Processing Speed
11. 8-OHdG → Processing Speed or general cognition
12. Fasting glucose / HOMA-IR → Processing Speed
13. NfL → Processing Speed or Global Cognition
14. Shannon diversity (gut) → Any cognitive outcome

For each study, report:
- Exact correlation coefficient (r or β) and CI
- Which specific test was used (TMT-A vs TMT-B matters)
- Plasma vs serum (for BDNF especially)
- Whether the analysis controlled for age/education/depression

Include NULL results (r ≈ 0, p > 0.05) — they are equally important.

SEARCH TERMS:
For each pair, search:
("[biomarker name]") AND ("[cognitive test name]" OR "[cognitive domain]")
AND ("cancer" OR "chemotherapy" OR "breast cancer")
AND ("correlation" OR "association" OR "regression" OR "predictor")

TARGET: 20-40 papers. Prioritize studies that report multiple biomarker-cognition
pairs from the same sample (efficient extraction).
```

---

### Session B1: Neuropsych Test Norms in Cancer

```
SEARCH TASK: Find normative data and psychometric validation studies for
neuropsychological tests used in cancer populations.

INSTRUMENTS TO COVER (priority order):
1. TMT-A, TMT-B (Trail Making Test) — processing speed, executive function
2. HVLT-R (Hopkins Verbal Learning Test-Revised) — episodic memory
3. DSST / Digit Symbol (Wechsler) — processing speed
4. Digit Span Forward/Backward — attention/working memory
5. Stroop Color-Word Test — executive function / inhibition
6. RAVLT (Rey Auditory Verbal Learning) — verbal memory
7. CPT (Continuous Performance Test) — sustained attention
8. COWAT / FAS (Controlled Oral Word Association) — verbal fluency
9. FACT-Cog (Functional Assessment: Cognition) — subjective cognition
10. MoCA (Montreal Cognitive Assessment) — screening

FOR EACH INSTRUMENT FIND:
- Normative means and SDs in cancer populations (by cancer type, age group)
- Normative means and SDs in healthy controls (age-matched)
- Test-retest reliability (ICC or r)
- Internal consistency (Cronbach's α)
- Sensitivity/specificity for detecting CRCI
- Minimally clinically important difference (MCID) if reported
- Whether cancer-specific norms exist vs using general population norms

SEARCH TERMS:
("[instrument name]") AND ("normative" OR "norms" OR "psychometric"
OR "reliability" OR "validation" OR "reference values" OR "Cronbach")
AND ("cancer" OR "oncology" OR "cancer survivors" OR "chemotherapy")

Fallback (if no cancer norms):
("[instrument name]") AND ("normative" OR "norms") AND ("adult" OR "aging")

TARGET: 15-25 papers. Focus on cancer-specific validation studies.
```

---

### Session B2: PRO Instrument Validation in Cancer

```
SEARCH TASK: Find psychometric validation studies for patient-reported
outcome (PRO) instruments in cancer populations.

INSTRUMENTS TO COVER:
1. FACIT-Fatigue / BFI (Brief Fatigue Inventory) — fatigue
2. PHQ-9 — depression
3. GAD-7 — anxiety
4. PSQI (Pittsburgh Sleep Quality Index) — sleep quality
5. ISI (Insomnia Severity Index) — insomnia
6. FACT-Cog PCI subscale — perceived cognitive impairment
7. EORTC QLQ-C30 cognitive subscale — QoL cognition
8. BPI (Brief Pain Inventory) — pain
9. IPAQ / Godin (physical activity questionnaires)
10. PSS (Perceived Stress Scale) — stress

FOR EACH INSTRUMENT FIND:
- Cronbach's α in cancer populations
- Factor structure in cancer (same as general population?)
- Test-retest reliability
- Convergent/discriminant validity with objective measures
- Known floor/ceiling effects
- Cancer-specific clinical cutoffs (vs general population cutoffs)

SEARCH TERMS:
("[instrument name]") AND ("validation" OR "psychometric" OR "reliability"
OR "factor analysis" OR "Cronbach" OR "measurement invariance")
AND ("cancer" OR "oncology" OR "breast cancer" OR "cancer survivors")

TARGET: 15-25 papers.
```

---

### Session C1: Oxidative Stress + DNA Damage + Senescence (M2 + M7 + M9)

```
SEARCH TASK: Find papers linking the OXIDATIVE STRESS → DNA DAMAGE →
CELLULAR SENESCENCE cascade to cognitive outcomes, primarily in cancer/chemo.

TARGET EDGES:
- ER_CHEMO_8OHDG, ER_CHEMO_MDA (chemo → oxidative biomarkers)
- ER_8OHDG_OIC, ER_MDA_OIC (oxidative damage → neuroinflammation)
- ER_CHEMO_GH2AX, ER_RADIATION_GH2AX (treatment → DNA damage)
- ER_GH2AX_DNA (γ-H2AX → DNA damage pathway)
- ER_CHEMO_P16 (chemo → senescence)
- ER_P16_SENESCENCE (p16 → senescence pathway)

SEARCH TERMS:
("oxidative stress" OR "8-OHdG" OR "MDA" OR "malondialdehyde"
OR "reactive oxygen species" OR "F2-isoprostanes")
AND ("chemotherapy" OR "cancer treatment")
AND ("cognitive" OR "neurotoxicity" OR "brain")

("gamma-H2AX" OR "γ-H2AX" OR "DNA double-strand break" OR "DNA damage")
AND ("chemotherapy" OR "cancer") AND ("cognitive" OR "aging" OR "senescence")

("p16INK4a" OR "p16" OR "cellular senescence" OR "SASP"
OR "senescence-associated secretory phenotype")
AND ("chemotherapy" OR "cancer") AND ("cognitive" OR "aging" OR "inflammation")

TARGET: 15-30 papers. Animal model evidence acceptable for M7/M9 — flag as PRECLINICAL.
```

---

### Session D1: Exercise Dose-Response

```
SEARCH TASK: Find dose-response data for exercise interventions on biomarkers
and cognition in cancer patients.

I need data to fit dose-response curves (EC50, Emax) for:

1. AEROBIC EXERCISE → IL-6 reduction
   What MET-min/week or minutes/week produces effect?
   Is there a threshold? A plateau?

2. AEROBIC EXERCISE → BDNF increase
   EC50 in MET-min/week?
   HIIT vs moderate continuous — does intensity matter?

3. AEROBIC EXERCISE → Fatigue reduction (FACIT-F)
   Minimum effective dose?
   Is there a dose ceiling?

4. AEROBIC EXERCISE → Processing speed improvement
   Sessions/week, duration, intensity — what predicts effect?

5. RESISTANCE TRAINING → Any biomarker or cognitive outcome
   Separate from aerobic — different dose parameters

SEARCH TERMS:
("dose-response" OR "dose response" OR "MET-minutes" OR "exercise intensity"
OR "exercise volume" OR "exercise prescription" OR "minimum dose"
OR "threshold" OR "plateau")
AND ("cancer" OR "breast cancer" OR "cancer survivors")
AND ("cognitive" OR "fatigue" OR "IL-6" OR "BDNF" OR "cortisol")

Also:
("exercise" OR "physical activity") AND ("cancer")
AND ("randomized") AND ("dose" OR "intensity" OR "frequency" OR "duration")
AND ("cognitive" OR "biomarker" OR "inflammation")

TARGET: 10-20 papers. Studies with multiple dose arms are highest value.
```

---

### Session D2: Temporal Recovery Curves

```
SEARCH TASK: Find longitudinal studies tracking cognitive and biomarker
trajectories before, during, and after chemotherapy treatment.

I need timepoint-specific data for modeling recovery curves:

1. COGNITIVE TRAJECTORY:
   - Pre-chemo baseline → during chemo → end of chemo → 6mo → 12mo → 2yr → 5yr+
   - By cognitive domain (processing speed recovers differently than memory)
   - What percentage of patients show persistent deficits at each timepoint?

2. BIOMARKER TRAJECTORY:
   - IL-6, CRP, TNF-α: peak during chemo → recovery timeline
   - Cortisol: when does DCS normalize after chemo?
   - BDNF: nadir → recovery
   - p16INK4a: is the increase permanent?

3. ACCELERATED AGING:
   - Evidence for permanent "biological age offset" from chemotherapy
   - Epigenetic clock studies in cancer survivors

SEARCH TERMS:
("trajectory" OR "longitudinal" OR "prospective" OR "follow-up"
OR "recovery" OR "time course" OR "temporal")
AND ("cognitive" OR "neuropsychological" OR "CRCI" OR "chemobrain")
AND ("chemotherapy" OR "cancer" OR "breast cancer")
AND ("months" OR "years" OR "timepoint")

("accelerated aging" OR "biological age" OR "epigenetic clock"
OR "methylation age" OR "telomere")
AND ("chemotherapy" OR "cancer treatment")

KEY: Studies with ≥3 timepoints are critical. Studies with only pre/post
are lower value (can't fit curves).

TARGET: 10-20 papers.
```

---

## Section 4: Output Processing

### How to Process AI Results

After each session, the AI will output papers in the structured format.
Convert to JSONL for pipeline input:

**File location:** `data/retrieval_candidates/<session_id>.jsonl`

**Naming convention:** `A1_neuroinflammation_2026-02-27.jsonl`

**Format (one JSON object per line):**

```json
{"doi": "10.1038/s41380-020-0698-6", "pmid": "32066837", "title": "Neuroinflammation and cognition...", "year": 2020, "authors": "Felger et al.", "journal": "Mol Psychiatry", "design": "meta_analysis", "cancer_type": "mixed", "sample_size": 1250, "edge_ids": ["ER_IL6_OIC", "ER_OIC_PROCSPEED", "ER_OIC_WORKMEM"], "instruments": ["TMT-A", "TMT-B", "HVLT-R"], "extractability": "HIGH", "access": "PAYWALLED", "key_finding": "IL-6 negatively correlated with processing speed (r=-0.23, p<0.01)", "session": "A1", "source": "chatgpt_deep_research"}
```

### Verification Step (IMPORTANT)

AI chatboxes sometimes fabricate citations. After collecting results:

1. **Spot-check 20%** of DOIs by pasting into https://doi.org/[DOI]
2. **Verify PMIDs** by checking https://pubmed.ncbi.nlm.nih.gov/[PMID]
3. Mark unverifiable papers as `"verified": false` in the JSONL
4. Papers marked false still enter Stage 0 but get a verification flag

### Feeding Results to Pipeline

```bash
# After collecting JSONL files from sessions:
python scripts/run_triage_sweep.py \
  --stage 0 \
  --input data/retrieval_candidates/A1_neuroinflammation_2026-02-27.jsonl \
  --slice PW_M01_NEUROINFLAMMATION

# Or batch all Phase A sessions:
python scripts/run_triage_sweep.py \
  --stage 0 \
  --input data/retrieval_candidates/A*.jsonl \
  --slice default
```

---

## Section 5: Session Workflow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ 1. OPEN new AI chatbox session (ChatGPT/Perplexity/Claude)   │
│ 2. PASTE System Prompt (Section 1)                           │
│ 3. PASTE Edge Reference (Section 2)                          │
│ 4. PASTE Session Prompt (Section 3, matching your session)   │
│ 5. WAIT for AI to complete search                            │
│ 6. REVIEW output for obvious hallucinations (wrong years,    │
│    non-existent journals, implausible sample sizes)          │
│ 7. COPY results → convert to JSONL → save to                │
│    data/retrieval_candidates/<session_id>.jsonl              │
│ 8. SPOT-CHECK 20% of DOIs                                   │
│ 9. RUN: python scripts/run_triage_sweep.py --stage 0 --input│
│ 10. PROCEED to next session                                  │
└──────────────────────────────────────────────────────────────┘

Time per session: ~10-15 minutes (AI search) + ~5-10 minutes (review)
Total for Phase A (7 sessions): ~2-3 hours
Total for all phases (17 sessions): ~1-2 days
Expected total yield: ~300-500 unique candidate papers
```

---

## Section 6: Tips for Different AI Platforms

### ChatGPT Deep Research (Recommended for Phase A)
- Best at finding specific papers with DOIs
- Can search PubMed directly
- Tends to provide more citations per session
- Weakness: sometimes includes retracted or preprint papers without flagging

### Perplexity Pro (Recommended for Phase B)
- Best at finding normative/reference data
- Provides source links you can verify immediately
- Weakness: sometimes gives fewer results per query

### Claude (Recommended for Phase C/D)
- Best at synthesizing complex pathway relationships
- Good at identifying null results
- Weakness: knowledge cutoff may miss very recent papers
- Workaround: provide recent review papers as context

### Google Gemini Deep Research
- Good breadth, accesses Google Scholar directly
- Best for finding gray literature and dissertations
- Weakness: DOIs less consistently provided

### General Tips
- If a session returns <10 papers, broaden the search terms
- If it returns >60, narrow by adding "AND cancer" if not already present
- If the AI says "I couldn't find papers on this topic," that IS data —
  record it as evidence that the pathway has poor human evidence
- Run the same session on 2 different platforms and deduplicate — catches
  platform-specific blind spots

---

## Section 7: Checklist

### Per-Session Checklist
- [ ] System prompt pasted
- [ ] Edge reference pasted
- [ ] Session-specific prompt pasted
- [ ] Results reviewed for hallucinations
- [ ] JSONL file created in `data/retrieval_candidates/`
- [ ] 20% DOI spot-check complete
- [ ] Pipeline Stage 0 run on results

### Phase Completion Checklist
- [ ] All Phase A sessions complete (A1-A7)
- [ ] Stage 0 triage run on all Phase A results
- [ ] Stage 1 abstract pre-extraction run on PASSED candidates
- [ ] Review: which edges in the vertical slice now have candidates?
- [ ] Phase B sessions complete (B1-B3) if needed
- [ ] Phase C sessions complete (C1-C5) if needed
- [ ] Phase D sessions complete (D1-D3) if needed
- [ ] Full pipeline through Stage 2 on top-priority batch

---

*Document: extraction_ref/13_RETRIEVAL_SESSIONS.md*
*Version: 1.0*
*Created: 2026-02-27*
*Companion: DEEP_RESEARCH_STRATEGY.md (keyword batteries), AUTOMATED_RETRIEVAL_PLAN.md Part 14 (pipeline)*
