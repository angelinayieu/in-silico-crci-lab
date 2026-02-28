# Edge IDs — Complete Reference

> All edges in `registries/EDGE_REGISTRY.csv`, grouped by source layer.

---

## Layer 0 → Layer 1: Exogenous → Behavior (7 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_CHEMO_ACTIVITY` | NODE_EXO_CHEMO_REGIMEN → NODE_BEH_PHYSICAL_ACTIVITY | causal | — |
| `ER_CHEMO_SLEEP` | NODE_EXO_CHEMO_REGIMEN → NODE_BEH_SLEEP_QUALITY | causal | — |
| `ER_CHEMO_DIET` | NODE_EXO_CHEMO_REGIMEN → NODE_BEH_DIET | causal | — |
| `ER_AGE_ACTIVITY` | NODE_EXO_AGE → NODE_BEH_PHYSICAL_ACTIVITY | assoc | negative |
| `ER_COMORBID_ACTIVITY` | NODE_EXO_COMORBIDITY → NODE_BEH_PHYSICAL_ACTIVITY | assoc | — |
| `ER_COGRESERVE_COGACTIVITY` | NODE_EXO_COG_RESERVE → NODE_BEH_COG_ACTIVITY | assoc | — |
| `ER_TX_PHASE_ACTIVITY` | NODE_EXO_TX_PHASE → NODE_BEH_PHYSICAL_ACTIVITY | causal | ctx_dep |

## Layer 0 → Layer 2: Exogenous → Biomarker (14 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_CHEMO_IL6` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_IL6 | causal | — |
| `ER_CHEMO_CRP` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_CRP | causal | positive |
| `ER_CHEMO_TNF` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_TNF | causal | positive |
| `ER_CHEMO_GH2AX` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_GH2AX | causal | positive |
| `ER_RADIATION_GH2AX` | NODE_EXO_RADIATION → NODE_BIO_GH2AX | causal | positive |
| `ER_CHEMO_8OHDG` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_8OHDG | causal | positive |
| `ER_CHEMO_MDA` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_MDA | causal | positive |
| `ER_CHEMO_P16` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_P16 | causal | positive |
| `ER_CHEMO_CORTISOL` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_CORTISOL | causal | — |
| `ER_CHEMO_SHANNON` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_SHANNON | causal | negative |
| `ER_CHEMO_GLUCOSE` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_GLUCOSE | causal | positive |
| `ER_CHEMO_NFL` | NODE_EXO_CHEMO_REGIMEN → NODE_BIO_NFL | mech | positive |
| `ER_RADIATION_NFL` | NODE_EXO_RADIATION → NODE_BIO_NFL | mech | positive |
| `ER_AGE_BDNF` | NODE_EXO_AGE → NODE_BIO_BDNF | assoc | — |

## Layer 0 → Layer 3: Exogenous → Pathway (5 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_CHEMO_MYELIN` | NODE_EXO_CHEMO_REGIMEN → NODE_PATH_MYELIN | causal | negative |
| `ER_CHEMO_EPIGENETIC` | NODE_EXO_CHEMO_REGIMEN → NODE_PATH_EPIGENETIC | mech | positive |
| `ER_CHEMO_DOPAMINE` | NODE_EXO_CHEMO_REGIMEN → NODE_PATH_DOPAMINERGIC | mech | negative |
| `ER_RADIATION_BBB` | NODE_EXO_RADIATION → NODE_PATH_BBB | causal | positive |
| `ER_APOE_OIC` | NODE_EXO_APOE → NODE_PATH_OIC | assoc | positive |
| `ER_SEX_HPA` | NODE_EXO_SEX → NODE_PATH_HPA | assoc | — |

## Layer 1 → Layer 2: Behavior → Biomarker (10 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_ACTIVITY_IL6` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_IL6 | causal | negative |
| `ER_ACTIVITY_CRP` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_CRP | causal | negative |
| `ER_ACTIVITY_BDNF` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_BDNF | causal | positive |
| `ER_ACTIVITY_CORTISOL` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_CORTISOL | causal | negative |
| `ER_ACTIVITY_GLUCOSE` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_GLUCOSE | causal | negative |
| `ER_ACTIVITY_8OHDG` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_BIO_8OHDG | assoc | negative |
| `ER_DIET_IL6` | NODE_BEH_DIET → NODE_BIO_IL6 | assoc | negative |
| `ER_DIET_SHANNON` | NODE_BEH_DIET → NODE_BIO_SHANNON | assoc | — |
| `ER_DIET_GLUCOSE` | NODE_BEH_DIET → NODE_BIO_GLUCOSE | assoc | negative |
| `ER_DIET_MDA` | NODE_BEH_DIET → NODE_BIO_MDA | assoc | negative |
| `ER_STRESS_CORTISOL` | NODE_BEH_STRESS_MGMT → NODE_BIO_CORTISOL | causal | negative |
| `ER_STRESS_IL6` | NODE_BEH_STRESS_MGMT → NODE_BIO_IL6 | assoc | negative |
| `ER_SLEEP_CORTISOL` | NODE_BEH_SLEEP_QUALITY → NODE_BIO_CORTISOL | causal | negative |
| `ER_COGACTIVITY_BDNF` | NODE_BEH_COG_ACTIVITY → NODE_BIO_BDNF | mech | positive |

## Layer 1 → Layer 3: Behavior → Pathway (3 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_SLEEP_GLYMPHATIC` | NODE_BEH_SLEEP_QUALITY → NODE_PATH_GLYMPHATIC | mech | positive |
| `ER_ACTIVITY_NEUROPLAST` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_PATH_NEUROPLASTICITY | causal | positive |
| `ER_COGACTIVITY_SYNAPTIC` | NODE_BEH_COG_ACTIVITY → NODE_PATH_SYNAPTIC | mech | positive |
| `ER_LIGHT_SLEEP` | NODE_BEH_LIGHT_EXPOSURE → NODE_SYM_SLEEP_DISRUPTION | causal | — |

## Layer 2 → Layer 3: Biomarker → Pathway (12 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_IL6_OIC` | NODE_BIO_IL6 → NODE_PATH_OIC | causal | positive |
| `ER_CRP_OIC` | NODE_BIO_CRP → NODE_PATH_OIC | assoc | positive |
| `ER_TNF_OIC` | NODE_BIO_TNF → NODE_PATH_OIC | causal | positive || `ER_IL8_OIC` | NODE_BIO_IL8 → NODE_PATH_OIC | causal | positive |
| `ER_IL10_OIC` | NODE_BIO_IL10 → NODE_PATH_OIC | assoc | negative |
| `ER_MCP1_OIC` | NODE_BIO_MCP1 → NODE_PATH_OIC | causal | positive |
| `ER_STNFR2_OIC` | NODE_BIO_STNFR2 → NODE_PATH_OIC | assoc | positive || `ER_8OHDG_OIC` | NODE_BIO_8OHDG → NODE_PATH_OIC | assoc | positive |
| `ER_MDA_OIC` | NODE_BIO_MDA → NODE_PATH_OIC | assoc | positive |
| `ER_BDNF_NEUROPLAST` | NODE_BIO_BDNF → NODE_PATH_NEUROPLASTICITY | causal | positive |
| `ER_BDNF_NEUROGENESIS` | NODE_BIO_BDNF → NODE_PATH_NEUROGENESIS | causal | positive |
| `ER_CORTISOL_HPA` | NODE_BIO_CORTISOL → NODE_PATH_HPA | causal | positive |
| `ER_P16_SENESCENCE` | NODE_BIO_P16 → NODE_PATH_SENESCENCE | causal | positive |
| `ER_GH2AX_DNA` | NODE_BIO_GH2AX → NODE_PATH_DNA_DAMAGE | causal | positive |
| `ER_SHANNON_GUTBRAIN` | NODE_BIO_SHANNON → NODE_PATH_GUT_BRAIN | assoc | negative |
| `ER_GLUCOSE_METABOLIC` | NODE_BIO_GLUCOSE → NODE_PATH_METABOLIC | causal | positive |
| `ER_NFL_BBB` | NODE_BIO_NFL → NODE_PATH_BBB | assoc | — |
| `ER_NFL_MYELIN` | NODE_BIO_NFL → NODE_PATH_MYELIN | assoc | negative |
## Layer 2 → Layer 2: Biomarker → Biomarker Cross-Edges (6 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_IL6_BDNF_CROSS` | NODE_BIO_IL6 → NODE_BIO_BDNF | assoc | negative |
| `ER_IL4_BDNF_CROSS` | NODE_BIO_IL4 → NODE_BIO_BDNF | assoc | positive |
| `ER_IFNG_BDNF_CROSS` | NODE_BIO_IFNG → NODE_BIO_BDNF | assoc | negative |
| `ER_TNF_BDNF_CROSS` | NODE_BIO_TNF → NODE_BIO_BDNF | assoc | negative |
| `ER_IL10_BDNF_CROSS` | NODE_BIO_IL10 → NODE_BIO_BDNF | assoc | positive |

## Layer 2 → Layer 3: Biomarker → Pathway (18 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_DNA_SENESCENCE` | NODE_PATH_DNA_DAMAGE → NODE_PATH_SENESCENCE | causal | positive |
| `ER_SENESCENCE_OIC` | NODE_PATH_SENESCENCE → NODE_PATH_OIC | causal | positive |
| `ER_GUTBRAIN_OIC` | NODE_PATH_GUT_BRAIN → NODE_PATH_OIC | mech | positive |
| `ER_EPIGENETIC_OIC` | NODE_PATH_EPIGENETIC → NODE_PATH_OIC | mech | positive |
| `ER_EPIGENETIC_NEUROPLAST` | NODE_PATH_EPIGENETIC → NODE_PATH_NEUROPLASTICITY | mech | negative |
| `ER_METABOLIC_OIC` | NODE_PATH_METABOLIC → NODE_PATH_OIC | assoc | positive |

## Layer 3 → Layer 4: Pathway → Symptom (10 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_OIC_FATIGUE` | NODE_PATH_OIC → NODE_SYM_FATIGUE | causal | positive |
| `ER_OIC_DEPRESSION` | NODE_PATH_OIC → NODE_SYM_DEPRESSION | causal | positive |
| `ER_OIC_PAIN` | NODE_PATH_OIC → NODE_SYM_PAIN | causal | positive |
| `ER_HPA_SLEEP` | NODE_PATH_HPA → NODE_SYM_SLEEP_DISRUPTION | causal | positive |
| `ER_HPA_DEPRESSION` | NODE_PATH_HPA → NODE_SYM_DEPRESSION | causal | positive |
| `ER_HPA_ANXIETY` | NODE_PATH_HPA → NODE_SYM_ANXIETY | causal | positive |
| `ER_GLYMPHATIC_SLEEP` | NODE_PATH_GLYMPHATIC → NODE_SYM_SLEEP_DISRUPTION | mech | negative |
| `ER_DOPAMINE_FATIGUE` | NODE_PATH_DOPAMINERGIC → NODE_SYM_FATIGUE | mech | negative |
| `ER_OIC_APPETITE` | NODE_PATH_OIC → NODE_SYM_APPETITE | causal | positive |
| `ER_GUTBRAIN_APPETITE` | NODE_PATH_GUT_BRAIN → NODE_SYM_APPETITE | mech | — |
| `ER_OIC_COGCOMPLAINTS` | NODE_PATH_OIC → NODE_SYM_COG_COMPLAINTS | assoc | positive |
| `ER_METABOLIC_DECONDITIONING` | NODE_PATH_METABOLIC → NODE_SYM_DECONDITIONING | assoc | positive |

## Layer 3 → Layer 5: Pathway → Cognition (16 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_OIC_PROCSPEED` | NODE_PATH_OIC → NODE_COG_PROC_SPEED | causal | negative |
| `ER_OIC_WORKMEM` | NODE_PATH_OIC → NODE_COG_WORK_MEM | causal | negative |
| `ER_OIC_EPISODIC` | NODE_PATH_OIC → NODE_COG_EPISODIC_MEM | causal | negative |
| `ER_OIC_ATTNSUST` | NODE_PATH_OIC → NODE_COG_ATTN_SUSTAINED | causal | negative |
| `ER_OIC_EXECPLAN` | NODE_PATH_OIC → NODE_COG_EXEC_PLANNING | causal | negative |
| `ER_OIC_VERBAL` | NODE_PATH_OIC → NODE_COG_VERBAL_FLUENCY | assoc | negative |
| `ER_OIC_MULTITASK` | NODE_PATH_OIC → NODE_COG_MULTITASKING | causal | negative |
| `ER_NEUROPLAST_EPISODIC` | NODE_PATH_NEUROPLASTICITY → NODE_COG_EPISODIC_MEM | causal | positive |
| `ER_NEUROPLAST_WORKMEM` | NODE_PATH_NEUROPLASTICITY → NODE_COG_WORK_MEM | mech | positive |
| `ER_NEUROPLAST_PROCSPEED` | NODE_PATH_NEUROPLASTICITY → NODE_COG_PROC_SPEED | mech | positive |
| `ER_NEUROPLAST_ATTN` | NODE_PATH_NEUROPLASTICITY → NODE_COG_ATTN_SUSTAINED | mech | positive |
| `ER_NEUROGENESIS_EPISODIC` | NODE_PATH_NEUROGENESIS → NODE_COG_EPISODIC_MEM | mech | positive |
| `ER_SYNAPTIC_PROCSPEED` | NODE_PATH_SYNAPTIC → NODE_COG_PROC_SPEED | mech | positive |
| `ER_SYNAPTIC_WORKMEM` | NODE_PATH_SYNAPTIC → NODE_COG_WORK_MEM | mech | positive |
| `ER_SYNAPTIC_EXEC` | NODE_PATH_SYNAPTIC → NODE_COG_EXEC_PLANNING | mech | positive |
| `ER_MYELIN_PROCSPEED` | NODE_PATH_MYELIN → NODE_COG_PROC_SPEED | causal | positive |
| `ER_MYELIN_VERBAL` | NODE_PATH_MYELIN → NODE_COG_VERBAL_FLUENCY | assoc | positive |
| `ER_MYELIN_LANGUAGE` | NODE_PATH_MYELIN → NODE_COG_LANGUAGE | assoc | positive |
| `ER_DOPAMINE_INHIBITION` | NODE_PATH_DOPAMINERGIC → NODE_COG_EXEC_INHIBITION | mech | positive |
| `ER_HPA_EPISODIC` | NODE_PATH_HPA → NODE_COG_EPISODIC_MEM | causal | negative |
| `ER_HPA_WORKMEM` | NODE_PATH_HPA → NODE_COG_WORK_MEM | assoc | negative |

## Layer 4 → Layer 4: Symptom → Symptom (2 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_PAIN_FATIGUE` | NODE_SYM_PAIN → NODE_SYM_FATIGUE | causal | positive |
| `ER_SLEEP_FATIGUE` | NODE_SYM_SLEEP_DISRUPTION → NODE_SYM_FATIGUE | causal | positive |

## Layer 4 → Layer 1: Symptom → Behavior (Feedback, 6 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_FATIGUE_ACTIVITY` | NODE_SYM_FATIGUE → NODE_BEH_PHYSICAL_ACTIVITY | causal | negative |
| `ER_DEPRESSION_SLEEP` | NODE_SYM_DEPRESSION → NODE_BEH_SLEEP_QUALITY | causal | negative |
| `ER_ANXIETY_SLEEP` | NODE_SYM_ANXIETY → NODE_BEH_SLEEP_QUALITY | causal | — |
| `ER_FATIGUE_SOCIAL` | NODE_SYM_FATIGUE → NODE_BEH_SOCIAL_ENGAGE | causal | negative |
| `ER_DEPRESSION_SOCIAL` | NODE_SYM_DEPRESSION → NODE_BEH_SOCIAL_ENGAGE | causal | — |
| `ER_FATIGUE_SELFEFFICACY` | NODE_SYM_FATIGUE → NODE_BEH_SELF_EFFICACY | causal | negative |

## Layer 4 → Layer 4/5: Symptom → Cognition (10 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_FATIGUE_ATTN` | NODE_SYM_FATIGUE → NODE_COG_ATTN_SUSTAINED | causal | negative |
| `ER_FATIGUE_PROCSPEED` | NODE_SYM_FATIGUE → NODE_COG_PROC_SPEED | causal | negative |
| `ER_SLEEP_ATTN` | NODE_SYM_SLEEP_DISRUPTION → NODE_COG_ATTN_SUSTAINED | causal | negative |
| `ER_SLEEP_WORKMEM` | NODE_SYM_SLEEP_DISRUPTION → NODE_COG_WORK_MEM | causal | negative |
| `ER_SLEEP_EPISODIC` | NODE_SYM_SLEEP_DISRUPTION → NODE_COG_EPISODIC_MEM | causal | negative |
| `ER_DEPRESSION_WORKMEM` | NODE_SYM_DEPRESSION → NODE_COG_WORK_MEM | causal | negative |
| `ER_DEPRESSION_EXEC` | NODE_SYM_DEPRESSION → NODE_COG_EXEC_PLANNING | causal | negative |
| `ER_DEPRESSION_COGCOMPLAINTS` | NODE_SYM_DEPRESSION → NODE_SYM_COG_COMPLAINTS | causal | positive |
| `ER_ANXIETY_SELECTATTN` | NODE_SYM_ANXIETY → NODE_COG_ATTN_SELECTIVE | causal | negative |
| `ER_DECONDITIONING_PROCSPEED` | NODE_SYM_DECONDITIONING → NODE_COG_PROC_SPEED | assoc | negative |
| `ER_COGCOMPLAINTS_EPISODIC` | NODE_SYM_COG_COMPLAINTS → NODE_COG_EPISODIC_MEM | assoc | negative |
| `ER_APPETITE_DECONDITIONING` | NODE_SYM_APPETITE → NODE_SYM_DECONDITIONING | assoc | positive |

## Layer 1 → Layer 4: Behavior → Symptom (Direct, 2 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_ACTIVITY_FATIGUE_DIRECT` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_SYM_FATIGUE | causal | negative |
| `ER_SLEEP_DEPRESSION_FWD` | NODE_BEH_SLEEP_QUALITY → NODE_SYM_DEPRESSION | causal | negative |
| `ER_SOCIAL_DEPRESSION` | NODE_BEH_SOCIAL_ENGAGE → NODE_SYM_DEPRESSION | assoc | negative |

## Layer 1 → Layer 5: Behavior → Cognition (Direct, 8 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_SOCIAL_VERBAL` | NODE_BEH_SOCIAL_ENGAGE → NODE_COG_VERBAL_FLUENCY | assoc | positive |
| `ER_SOCIAL_EXEC` | NODE_BEH_SOCIAL_ENGAGE → NODE_COG_EXEC_PLANNING | assoc | — |
| `ER_COGACTIVITY_WORKMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_WORK_MEM | causal | positive |
| `ER_COGACTIVITY_ATTN` | NODE_BEH_COG_ACTIVITY → NODE_COG_ATTN_SUSTAINED | causal | positive |
| `ER_COGACTIVITY_COGCOMPLAINTS` | NODE_BEH_COG_ACTIVITY → NODE_SYM_COG_COMPLAINTS | causal | negative |
| `ER_COGACTIVITY_EPIMEM` | NODE_BEH_COG_ACTIVITY → NODE_COG_EPISODIC_MEM | causal | positive |
| `ER_ACTIVITY_PROC_SPEED` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_PROC_SPEED | causal | positive |
| `ER_ACTIVITY_VERBAL_FLUENCY` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_VERBAL_FLUENCY | causal | positive |
| `ER_ACTIVITY_EPIMEM` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_EPISODIC_MEM | causal | positive |
| `ER_ACTIVITY_COG_COMPLAINTS` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_SYM_COG_COMPLAINTS | causal | negative |
| `ER_ACTIVITY_WORKMEM` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_WORK_MEM | causal | positive |
| `ER_ACTIVITY_EXEC` | NODE_BEH_PHYSICAL_ACTIVITY → NODE_COG_EXEC_PLANNING | causal | positive |

## Layer 5 → Layer 6: Cognition → Composite (11 edges)

| Edge ID | Source → Target | Type | Sign |
|---------|----------------|------|------|
| `ER_ATTNSUST_CRCI` | NODE_COG_ATTN_SUSTAINED → NODE_COMP_CRCI | causal | positive |
| `ER_ATTNSEL_CRCI` | NODE_COG_ATTN_SELECTIVE → NODE_COMP_CRCI | causal | positive |
| `ER_PROCSPD_CRCI` | NODE_COG_PROC_SPEED → NODE_COMP_CRCI | causal | positive |
| `ER_WORKMEM_CRCI` | NODE_COG_WORK_MEM → NODE_COMP_CRCI | causal | positive |
| `ER_EPIMEM_CRCI` | NODE_COG_EPISODIC_MEM → NODE_COMP_CRCI | causal | positive |
| `ER_VERBAL_CRCI` | NODE_COG_VERBAL_FLUENCY → NODE_COMP_CRCI | causal | positive |
| `ER_EXECPLAN_CRCI` | NODE_COG_EXEC_PLANNING → NODE_COMP_CRCI | causal | positive |
| `ER_EXECINHIB_CRCI` | NODE_COG_EXEC_INHIBITION → NODE_COMP_CRCI | causal | positive |
| `ER_MULTITASK_CRCI` | NODE_COG_MULTITASKING → NODE_COMP_CRCI | causal | positive |
| `ER_VISUOSP_CRCI` | NODE_COG_VISUOSPATIAL → NODE_COMP_CRCI | causal | positive |
| `ER_LANGUAGE_CRCI` | NODE_COG_LANGUAGE → NODE_COMP_CRCI | causal | positive |

---

**Total: ~156 edges across 8 layer-crossing groups**

> If a paper tests a relationship not listed above, add it to `registries/EDGE_REGISTRY.csv` first.
