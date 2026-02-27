# Instrument IDs — Complete Reference

> All instruments in `registries/INSTRUMENT_REGISTRY.csv`, grouped by type.

---

## Patient-Reported Outcomes (PRO)

| Instrument ID | Short | Full Name | Maps To |
|---------------|-------|-----------|---------|
| `INST_AFI` | AFI | Attentional Function Index | NODE_SYM_COG_COMPLAINTS |
| `INST_FACTCOG_PCI` | FACT-Cog PCI | FACT-Cog Perceived Cognitive Impairments | NODE_SYM_COG_COMPLAINTS |
| `INST_PROMIS_COG` | PROMIS-Cog | PROMIS Cognitive Function Short Form 8a | NODE_SYM_COG_COMPLAINTS |
| `INST_FACIT_FATIGUE` | FACIT-F | FACIT-Fatigue Scale | NODE_SYM_FATIGUE |
| `INST_BFI` | BFI | Brief Fatigue Inventory | NODE_SYM_FATIGUE |
| `INST_LFS` | LFS | Lee Fatigue Scale | NODE_SYM_FATIGUE |
| `INST_PHQ9` | PHQ-9 | Patient Health Questionnaire-9 | NODE_SYM_DEPRESSION |
| `INST_CESD` | CES-D | Center for Epidemiological Studies Depression | NODE_SYM_DEPRESSION |
| `INST_PHQ2` | PHQ-2 | Patient Health Questionnaire-2 | NODE_SYM_DEPRESSION |
| `INST_GAD7` | GAD-7 | Generalized Anxiety Disorder-7 | NODE_SYM_ANXIETY |
| `INST_STAI_S` | STAI-S | Spielberger State-Trait Anxiety — State | NODE_SYM_ANXIETY |
| `INST_PSQI` | PSQI | Pittsburgh Sleep Quality Index | NODE_SYM_SLEEP_DISRUPTION |
| `INST_ISI` | ISI | Insomnia Severity Index | NODE_SYM_SLEEP_DISRUPTION |
| `INST_GSDS` | GSDS | General Sleep Disturbance Scale | NODE_SYM_SLEEP_DISRUPTION |
| `INST_BPI` | BPI | Brief Pain Inventory | NODE_SYM_PAIN |
| `INST_PSS` | PSS | Perceived Stress Scale | NODE_BEH_STRESS_MGMT |
| `INST_IES_R` | IES-R | Impact of Event Scale-Revised | NODE_BEH_STRESS_MGMT |
| `INST_LSC_R` | LSC-R | Life Stressor Checklist-Revised | NODE_BEH_STRESS_MGMT |
| `INST_CDRISC` | CD-RISC | Connor-Davidson Resilience Scale | NODE_BEH_STRESS_MGMT |
| `INST_NEO_FFI` | NEO-FFI-N | NEO Five Factor Inventory — Neuroticism | NODE_BEH_STRESS_MGMT |
| `INST_SCQ` | SCQ | Self-Administered Comorbidity Questionnaire | NODE_EXO_COMORBIDITY |
| `INST_IPAQ` | IPAQ | International Physical Activity Questionnaire | NODE_BEH_PHYSICAL_ACTIVITY |
| `INST_GLTEQ` | GLTEQ | Godin Leisure Time Exercise Questionnaire | NODE_BEH_PHYSICAL_ACTIVITY |
| `INST_MED_DIET` | MedDiet | Mediterranean Diet Adherence Score | NODE_BEH_DIET |
| `INST_LSNS` | LSNS-6 | Lubben Social Network Scale | NODE_BEH_SOCIAL_ENGAGE |
| `INST_GSES` | GSES | General Self-Efficacy Scale | NODE_BEH_SELF_EFFICACY |
| `INST_EORTC_C30` | EORTC-C30 | EORTC QLQ-C30 | NODE_SYM_APPETITE |
| `INST_NRS_PAIN` | NRS-Pain | Numeric Rating Scale — Pain | NODE_SYM_PAIN |
| `INST_CAQ` | CAQ | Cognitive Activity Questionnaire | NODE_BEH_COG_ACTIVITY |

## Neuropsychological Tests (Performance-Based)

| Instrument ID | Short | Full Name | Maps To | Direction |
|---------------|-------|-----------|---------|-----------|
| `INST_MOCA` | MoCA | Montreal Cognitive Assessment | NODE_COMP_CRCI | higher=better |
| `INST_TMT_B` | TMT-B | Trail Making Test Part B | NODE_COG_PROC_SPEED | lower=better |
| `INST_HVLTR` | HVLT-R | Hopkins Verbal Learning Test-Revised | NODE_COG_EPISODIC_MEM | higher=better |
| `INST_CPT` | CPT | Continuous Performance Test | NODE_COG_ATTN_SUSTAINED | higher=better |
| `INST_STROOP` | Stroop | Stroop Color-Word Test | NODE_COG_EXEC_INHIBITION | higher=better |
| `INST_DIGIT_SPAN` | Digit Span | WAIS Digit Span | NODE_COG_WORK_MEM | higher=better |
| `INST_COWAT` | FAS/COWAT | Controlled Oral Word Association Test | NODE_COG_VERBAL_FLUENCY | higher=better |
| `INST_TOL` | ToL | Tower of London | NODE_COG_EXEC_PLANNING | higher=better |
| `INST_REY_COPY` | Rey-Copy | Rey Complex Figure Test — Copy | NODE_COG_VISUOSPATIAL | higher=better |
| `INST_BNT` | BNT | Boston Naming Test | NODE_COG_LANGUAGE | higher=better |
| `INST_ISL_DR` | ISL-DR | International Shopping List — Delayed Recall | NODE_COG_EPISODIC_MEM | higher=better |
| `INST_GROTON_MAZE` | GMLT | Groton Maze Learning Task | NODE_COG_EXEC_PLANNING | lower=better |
| `INST_ONEBACK` | One-Back | CogState One-Back Task | NODE_COG_WORK_MEM | higher=better |

## Biomarker Assays

| Instrument ID | Short | Full Name | Maps To |
|---------------|-------|-----------|---------|
| `INST_IL6_PLASMA` | IL-6 | Interleukin-6 Plasma ELISA | NODE_BIO_IL6 |
| `INST_CRP_HS` | hs-CRP | High-Sensitivity C-Reactive Protein | NODE_BIO_CRP |
| `INST_TNF_PLASMA` | TNF-α | TNF Alpha Plasma ELISA | NODE_BIO_TNF |
| `INST_BDNF_PLASMA` | BDNF | BDNF Plasma ELISA | NODE_BIO_BDNF |
| `INST_CORTISOL_SLOPE` | Cortisol-slope | Salivary Cortisol Diurnal Slope | NODE_BIO_CORTISOL |
| `INST_P16_TCELL` | p16 | p16^INK4a T-Cell Expression | NODE_BIO_P16 |
| `INST_GH2AX_LYMPH` | γ-H2AX | Gamma-H2AX Lymphocyte Foci | NODE_BIO_GH2AX |
| `INST_8OHDG` | 8-OHdG | 8-Hydroxy-2'-Deoxyguanosine | NODE_BIO_8OHDG |
| `INST_MDA_PLASMA` | MDA | Malondialdehyde Plasma | NODE_BIO_MDA |
| `INST_GLUCOSE_FASTING` | Glucose | Fasting Glucose | NODE_BIO_GLUCOSE |
| `INST_NFL_PLASMA` | NfL | Neurofilament Light Chain Plasma | NODE_BIO_NFL |
| `INST_SHANNON_16S` | Shannon-H | Gut Microbiome Shannon Diversity Index | NODE_BIO_SHANNON |

## Clinical Records & Other

| Instrument ID | Short | Full Name | Maps To |
|---------------|-------|-----------|---------|
| `INST_CCI` | CCI | Charlson Comorbidity Index | NODE_EXO_COMORBIDITY |
| `INST_KPS` | KPS | Karnofsky Performance Status | NODE_SYM_DECONDITIONING |
| `INST_6MWT` | 6MWT | Six-Minute Walk Test | NODE_SYM_DECONDITIONING |
| `INST_VO2PEAK` | VO2peak | Peak Oxygen Uptake | NODE_SYM_DECONDITIONING |
| `INST_ACCEL` | Actigraphy | Wrist Accelerometry | NODE_BEH_PHYSICAL_ACTIVITY |
| `INST_MAX2` | MAX2 | MAX2 Chemotherapy Toxicity Index | NODE_EXO_CHEMO_REGIMEN |
| `INST_APOE_GENOTYPE` | APOE | APOE Genotype Test | NODE_EXO_APOE |
| `INST_COG_RESERVE_COMP` | CogRes | Cognitive Reserve Composite | NODE_EXO_COG_RESERVE |
| `INST_CLINICAL_AGE` | Age | Age at Diagnosis | NODE_EXO_AGE |
| `INST_CLINICAL_SEX` | Sex | Biological Sex | NODE_EXO_SEX |
| `INST_CLINICAL_CANCER_TYPE` | CancerType | Cancer Type Classification | NODE_EXO_CANCER_TYPE |
| `INST_CLINICAL_RADIATION` | RadRecord | Radiation Exposure Record | NODE_EXO_RADIATION |
| `INST_CLINICAL_TX_PHASE` | TxPhase | Treatment Phase | NODE_EXO_TX_PHASE |

---

**Total: 67+ instruments**

> If a paper uses an instrument not listed above, add it to `registries/INSTRUMENT_REGISTRY.csv` first.  
> Key fields to provide: instrument_id, instrument_name, maps_to_node_id, instrument_type, scoring_direction.
