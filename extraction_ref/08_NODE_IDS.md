# Node IDs — Complete Reference

> All 70 nodes in `registries/NODE_REGISTRY.csv`, grouped by layer.

---

## Layer 0 — Exogenous / Treatment (9 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_EXO_CHEMO_REGIMEN` | Chemotherapy Regimen Class |
| `NODE_EXO_RADIATION` | Radiation Exposure |
| `NODE_EXO_TX_PHASE` | Treatment Phase |
| `NODE_EXO_CANCER_TYPE` | Cancer Type |
| `NODE_EXO_AGE` | Age at Diagnosis |
| `NODE_EXO_SEX` | Biological Sex |
| `NODE_EXO_APOE` | APOE Genotype Status |
| `NODE_EXO_COG_RESERVE` | Premorbid Cognitive Reserve |
| `NODE_EXO_COMORBIDITY` | Comorbidity Burden |

## Layer 1 — Behavioral Interventions (8 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_BEH_PHYSICAL_ACTIVITY` | Physical Activity Level |
| `NODE_BEH_SLEEP_QUALITY` | Sleep Quality/Hygiene |
| `NODE_BEH_DIET` | Dietary Pattern |
| `NODE_BEH_STRESS_MGMT` | Stress Management Practice |
| `NODE_BEH_SOCIAL_ENGAGE` | Social Engagement Level |
| `NODE_BEH_LIGHT_EXPOSURE` | Light Exposure Pattern |
| `NODE_BEH_COG_ACTIVITY` | Cognitive Activity Level |
| `NODE_BEH_SELF_EFFICACY` | Self-Efficacy / Adherence Motivation |

## Layer 2 — Biomarkers (18 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_BIO_IL6` | Interleukin-6 |
| `NODE_BIO_CRP` | C-Reactive Protein |
| `NODE_BIO_TNF` | Tumor Necrosis Factor Alpha |
| `NODE_BIO_BDNF` | Brain-Derived Neurotrophic Factor |
| `NODE_BIO_IL8` | Interleukin-8 (CXCL8) |
| `NODE_BIO_IL10` | Interleukin-10 |
| `NODE_BIO_IL4` | Interleukin-4 |
| `NODE_BIO_IFNG` | Interferon-Gamma |
| `NODE_BIO_MCP1` | Monocyte Chemoattractant Protein-1 (CCL2) |
| `NODE_BIO_STNFR2` | Soluble TNF Receptor II (sTNF-RII) |
| `NODE_BIO_CORTISOL` | Cortisol Diurnal Slope |
| `NODE_BIO_P16` | p16^INK4a Expression |
| `NODE_BIO_GH2AX` | Gamma-H2AX Foci |
| `NODE_BIO_8OHDG` | 8-Hydroxy-2'-Deoxyguanosine |
| `NODE_BIO_MDA` | Malondialdehyde |
| `NODE_BIO_GLUCOSE` | Fasting Glucose |
| `NODE_BIO_NFL` | Neurofilament Light Chain |
| `NODE_BIO_SHANNON` | Gut Microbiome Shannon Diversity |

## Layer 3 — Biological Pathways (14 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_PATH_OIC` | Oxidative-Inflammatory Cascade |
| `NODE_PATH_HPA` | HPA Axis Dysregulation |
| `NODE_PATH_NEUROPLASTICITY` | Neuroplasticity / BDNF Signaling |
| `NODE_PATH_NEUROGENESIS` | Adult Neurogenesis |
| `NODE_PATH_DNA_DAMAGE` | DNA Damage Response |
| `NODE_PATH_GUT_BRAIN` | Gut-Brain Axis Signaling |
| `NODE_PATH_SENESCENCE` | Cellular Senescence |
| `NODE_PATH_GLYMPHATIC` | Glymphatic Clearance |
| `NODE_PATH_CEREBROVASCULAR` | Cerebrovascular Function |
| `NODE_PATH_EPIGENETIC` | Epigenetic Modification |
| `NODE_PATH_METABOLIC` | Metabolic Dysregulation |
| `NODE_PATH_BBB` | Blood-Brain Barrier Disruption |
| `NODE_PATH_SYNAPTIC` | Synaptic Function |
| `NODE_PATH_MYELIN` | Myelin / Oligodendrocyte Integrity |
| `NODE_PATH_DOPAMINERGIC` | Dopaminergic Signaling |

## Layer 4 — Symptom Clusters (8 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_SYM_FATIGUE` | Cancer-Related Fatigue |
| `NODE_SYM_DEPRESSION` | Depression |
| `NODE_SYM_ANXIETY` | Anxiety |
| `NODE_SYM_SLEEP_DISRUPTION` | Sleep Disruption |
| `NODE_SYM_PAIN` | Pain |
| `NODE_SYM_COG_COMPLAINTS` | Subjective Cognitive Complaints |
| `NODE_SYM_DECONDITIONING` | Physical Deconditioning |
| `NODE_SYM_APPETITE` | Appetite / Nausea Disruption |

## Layer 5 — Cognitive Domains (11 nodes)

| Node ID | Label |
|---------|-------|
| `NODE_COG_ATTN_SUSTAINED` | Sustained Attention |
| `NODE_COG_ATTN_SELECTIVE` | Selective Attention |
| `NODE_COG_PROC_SPEED` | Processing Speed |
| `NODE_COG_WORK_MEM` | Working Memory |
| `NODE_COG_EPISODIC_MEM` | Episodic Memory |
| `NODE_COG_VERBAL_FLUENCY` | Verbal Fluency |
| `NODE_COG_EXEC_PLANNING` | Executive Function — Planning |
| `NODE_COG_EXEC_INHIBITION` | Executive Function — Inhibition |
| `NODE_COG_MULTITASKING` | Multitasking / Cognitive Flexibility |
| `NODE_COG_VISUOSPATIAL` | Visuospatial Function |
| `NODE_COG_LANGUAGE` | Language Comprehension |

## Layer 6 — Composite (1 node)

| Node ID | Label |
|---------|-------|
| `NODE_COMP_CRCI` | CRCI Composite Score |

---

## Quick Lookup by Domain

**Physical activity edges:** source = `NODE_BEH_PHYSICAL_ACTIVITY`  
**Cognitive rehabilitation edges:** source = `NODE_BEH_COG_ACTIVITY`  
**Inflammation pathways:** `NODE_BIO_IL6`, `NODE_BIO_CRP`, `NODE_BIO_TNF`, `NODE_BIO_IL8`, `NODE_BIO_IL10`, `NODE_BIO_IL4`, `NODE_BIO_IFNG`, `NODE_BIO_MCP1`, `NODE_BIO_STNFR2` → `NODE_PATH_OIC`  
**Subjective cognition:** `NODE_SYM_COG_COMPLAINTS` (PROs like FACT-Cog)  
**Objective cognition:** `NODE_COG_*` (neuropsych tests)  
**Multitasking/flexibility:** `NODE_COG_MULTITASKING` (CANTAB MTT, WCST, TMT-B switching)  
