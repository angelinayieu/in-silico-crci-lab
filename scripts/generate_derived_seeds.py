#!/usr/bin/env python3
"""
Generate derivable seed data from the core Class A tables.

This script reads the already-loaded core seeds (nodes, instruments, measures,
edges) and generates:
  1. node_search_terms — search synonyms per node for automated retrieval
  2. observation_noise — default noise parameters per instrument/measure
  3. feedback_loops — feedback cycles detected from edge definitions
  4. instrument-derived search terms — auto-generated from instrument_definitions_v1

Usage:
    python scripts/generate_derived_seeds.py [--verbose]

Prerequisite: Core seeds (nodes, instruments, measures, edges) must be loaded first.
Run: python scripts/setup_database.py --seed
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from sqlalchemy import text

from crci.shared.db import get_session, init_db

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  NODE SEARCH TERMS — synonyms, abbreviations, MeSH headings,
#  instrument names, and exclude terms.
#
#  term_type values:
#    primary       — canonical search label for this node
#    synonym       — alternate name / phrasing
#    abbreviation  — short form (IL-6, CRF, PSQI, etc.)
#    mesh_heading  — MeSH term for PubMed queries
#    instrument    — assessment tool name (auto-generated from DB too)
#    exclude       — term to EXCLUDE from search (prevents false positives)
#
#  Node IDs MUST match biomarker_node_definitions_v1.node_id exactly.
# ═══════════════════════════════════════════════════════════════

NODE_SEARCH_TERMS: dict[str, list[tuple[str, str]]] = {
    # ───────────────────────────────────────────────────────────
    # LAYER 0 — Exogenous / Context Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_EXO_CHEMO_REGIMEN": [
        ("chemotherapy", "primary"),
        ("chemotherapy regimen", "synonym"),
        ("cytotoxic chemotherapy", "synonym"),
        ("anthracycline", "synonym"),
        ("taxane", "synonym"),
        ("cyclophosphamide", "synonym"),
        ("doxorubicin", "synonym"),
        ("antineoplastic agents", "mesh_heading"),
        ("antineoplastic combined chemotherapy protocols", "mesh_heading"),
    ],
    "NODE_EXO_AGE": [
        ("age", "primary"),
        ("chronological age", "synonym"),
        ("age at diagnosis", "synonym"),
        ("older adults", "synonym"),
        ("age factors", "mesh_heading"),
    ],
    "NODE_EXO_SEX": [
        ("sex", "primary"),
        ("biological sex", "synonym"),
        ("female", "synonym"),
        ("male", "synonym"),
        ("sex factors", "mesh_heading"),
    ],
    "NODE_EXO_APOE": [
        ("APOE", "primary"),
        ("apolipoprotein E", "synonym"),
        ("APOE4", "abbreviation"),
        ("APOE ε4", "synonym"),
        ("ApoE genotype", "synonym"),
        ("apolipoproteins E", "mesh_heading"),
    ],
    "NODE_EXO_CANCER_TYPE": [
        ("cancer type", "primary"),
        ("breast cancer", "synonym"),
        ("colorectal cancer", "synonym"),
        ("lung cancer", "synonym"),
        ("hematological malignancy", "synonym"),
        ("neoplasms", "mesh_heading"),
    ],
    "NODE_EXO_RADIATION": [
        ("radiation therapy", "primary"),
        ("radiotherapy", "synonym"),
        ("cranial radiation", "synonym"),
        ("whole brain radiotherapy", "synonym"),
        ("WBRT", "abbreviation"),
        ("radiotherapy", "mesh_heading"),
    ],
    "NODE_EXO_TX_PHASE": [
        ("treatment phase", "primary"),
        ("active treatment", "synonym"),
        ("post-treatment", "synonym"),
        ("survivorship", "synonym"),
        ("during chemotherapy", "synonym"),
    ],
    "NODE_EXO_COMORBIDITY": [
        ("comorbidity", "primary"),
        ("comorbid conditions", "synonym"),
        ("medical comorbidity", "synonym"),
        ("comorbidity", "mesh_heading"),
    ],
    "NODE_EXO_COG_RESERVE": [
        ("cognitive reserve", "primary"),
        ("education level", "synonym"),
        ("premorbid intelligence", "synonym"),
        ("years of education", "synonym"),
        ("cognitive reserve", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # LAYER 1 — Behavioral Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_BEH_SLEEP_QUALITY": [
        ("sleep quality", "primary"),
        ("sleep hygiene", "synonym"),
        ("sleep habits", "synonym"),
        ("sleep behavior", "synonym"),
        ("sleep", "mesh_heading"),
        ("sleep hygiene", "mesh_heading"),
        # exclude
        ("sleep apnea", "exclude"),
    ],
    "NODE_BEH_PHYSICAL_ACTIVITY": [
        ("physical activity", "primary"),
        ("exercise", "synonym"),
        ("aerobic exercise", "synonym"),
        ("resistance training", "synonym"),
        ("MVPA", "abbreviation"),
        ("MET-minutes", "synonym"),
        ("step count", "synonym"),
        ("cardiorespiratory fitness", "synonym"),
        ("VO2", "abbreviation"),
        ("exercise", "mesh_heading"),
        ("motor activity", "mesh_heading"),
        # exclude
        ("physical therapy", "exclude"),
        ("rehabilitation", "exclude"),
    ],
    "NODE_BEH_DIET": [
        ("diet", "primary"),
        ("dietary pattern", "synonym"),
        ("Mediterranean diet", "synonym"),
        ("nutrition", "synonym"),
        ("dietary intake", "synonym"),
        ("anti-inflammatory diet", "synonym"),
        ("diet", "mesh_heading"),
        ("nutritional status", "mesh_heading"),
    ],
    "NODE_BEH_STRESS_MGMT": [
        ("stress management", "primary"),
        ("mindfulness", "synonym"),
        ("MBSR", "abbreviation"),
        ("meditation", "synonym"),
        ("relaxation training", "synonym"),
        ("yoga", "synonym"),
        ("cognitive behavioral stress management", "synonym"),
        ("stress reduction", "synonym"),
        ("mindfulness", "mesh_heading"),
        ("relaxation therapy", "mesh_heading"),
    ],
    "NODE_BEH_COG_ACTIVITY": [
        ("cognitive activity", "primary"),
        ("cognitive training", "synonym"),
        ("brain training", "synonym"),
        ("cognitive stimulation", "synonym"),
        ("cognitive engagement", "synonym"),
        ("cognitive remediation", "synonym"),
        ("cognitive training", "mesh_heading"),
    ],
    "NODE_BEH_LIGHT_EXPOSURE": [
        ("light exposure", "primary"),
        ("bright light therapy", "synonym"),
        ("phototherapy", "synonym"),
        ("circadian light", "synonym"),
        ("light therapy", "mesh_heading"),
        ("phototherapy", "mesh_heading"),
    ],
    "NODE_BEH_SOCIAL_ENGAGE": [
        ("social engagement", "primary"),
        ("social support", "synonym"),
        ("social isolation", "synonym"),
        ("social participation", "synonym"),
        ("social network", "synonym"),
        ("social support", "mesh_heading"),
    ],
    "NODE_BEH_SELF_EFFICACY": [
        ("self-efficacy", "primary"),
        ("self efficacy", "synonym"),
        ("perceived self-efficacy", "synonym"),
        ("self confidence", "synonym"),
        ("self efficacy", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # LAYER 2 — Biomarker Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_BIO_IL6": [
        ("interleukin-6", "primary"),
        ("IL-6", "abbreviation"),
        ("IL6", "abbreviation"),
        ("plasma IL-6", "synonym"),
        ("serum IL-6", "synonym"),
        ("interleukin 6", "synonym"),
        ("interleukins", "mesh_heading"),
        ("interleukin-6", "mesh_heading"),
        # exclude — pharmacological IL-6 targeting
        ("tocilizumab", "exclude"),
        ("IL-6 receptor antagonist", "exclude"),
        # exclude — pharmacological/therapeutic IL-6 targeting
        ("tocilizumab", "exclude"),
        ("IL-6 receptor antagonist", "exclude"),
    ],
    "NODE_BIO_CRP": [
        ("C-reactive protein", "primary"),
        ("CRP", "abbreviation"),
        ("hs-CRP", "abbreviation"),
        ("high-sensitivity CRP", "synonym"),
        ("high-sensitivity C-reactive protein", "synonym"),
        ("C reactive protein", "mesh_heading"),
    ],
    "NODE_BIO_TNF": [
        ("tumor necrosis factor alpha", "primary"),
        ("TNF-alpha", "abbreviation"),
        ("TNF-α", "abbreviation"),
        ("TNFα", "abbreviation"),
        ("TNF", "abbreviation"),
        ("plasma TNF", "synonym"),
        ("tumor necrosis factor-alpha", "mesh_heading"),
        # exclude — anti-TNF therapies (measuring drug effect, not endogenous)
        ("infliximab", "exclude"),
        ("etanercept", "exclude"),
        ("anti-TNF therapy", "exclude"),
    ],
    "NODE_BIO_CORTISOL": [
        ("cortisol", "primary"),
        ("salivary cortisol", "synonym"),
        ("diurnal cortisol", "synonym"),
        ("cortisol slope", "synonym"),
        ("diurnal cortisol slope", "synonym"),
        ("cortisol awakening response", "synonym"),
        ("CAR", "abbreviation"),
        ("evening cortisol", "synonym"),
        ("cortisol AUCg", "synonym"),
        ("cortisol AUCi", "synonym"),
        ("cortisol rhythm", "synonym"),
        ("HPA axis", "synonym"),
        ("hydrocortisone", "mesh_heading"),
        # exclude
        ("cortisol injection", "exclude"),
        ("hydrocortisone therapy", "exclude"),
    ],
    "NODE_BIO_BDNF": [
        ("brain-derived neurotrophic factor", "primary"),
        ("BDNF", "abbreviation"),
        ("plasma BDNF", "synonym"),
        ("serum BDNF", "synonym"),
        ("brain derived neurotrophic factor", "mesh_heading"),
        # exclude — gene therapy / knockout / purely preclinical
        ("BDNF gene therapy", "exclude"),
        ("BDNF knockout", "exclude"),
    ],
    "NODE_BIO_8OHDG": [
        ("8-hydroxydeoxyguanosine", "primary"),
        ("8-OHdG", "abbreviation"),
        ("8-oxo-dG", "abbreviation"),
        ("oxidative DNA damage marker", "synonym"),
        ("8-hydroxy-2'-deoxyguanosine", "synonym"),
    ],
    "NODE_BIO_MDA": [
        ("malondialdehyde", "primary"),
        ("MDA", "abbreviation"),
        ("lipid peroxidation", "synonym"),
        ("TBARS", "abbreviation"),
        ("malondialdehyde", "mesh_heading"),
    ],
    "NODE_BIO_NFL": [
        ("neurofilament light chain", "primary"),
        ("NfL", "abbreviation"),
        ("plasma NfL", "synonym"),
        ("serum NfL", "synonym"),
        ("neurofilament light", "synonym"),
        ("neurofilament proteins", "mesh_heading"),
    ],
    "NODE_BIO_P16": [
        ("p16INK4a", "primary"),
        ("p16", "abbreviation"),
        ("CDKN2A", "abbreviation"),
        ("cellular senescence marker", "synonym"),
        ("T-cell p16", "synonym"),
        ("cyclin-dependent kinase inhibitor 2A", "mesh_heading"),
    ],
    "NODE_BIO_GH2AX": [
        ("gamma-H2AX", "primary"),
        ("γ-H2AX", "abbreviation"),
        ("phospho-H2AX", "synonym"),
        ("DNA double-strand break marker", "synonym"),
        ("H2AX phosphorylation", "synonym"),
    ],
    "NODE_BIO_GLUCOSE": [
        ("fasting glucose", "primary"),
        ("blood glucose", "synonym"),
        ("insulin resistance", "synonym"),
        ("HbA1c", "abbreviation"),
        ("HOMA-IR", "abbreviation"),
        ("blood glucose", "mesh_heading"),
    ],
    "NODE_BIO_SHANNON": [
        ("gut microbiome diversity", "primary"),
        ("Shannon diversity index", "synonym"),
        ("alpha diversity", "synonym"),
        ("microbiome composition", "synonym"),
        ("16S rRNA sequencing", "synonym"),
        ("gastrointestinal microbiome", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # LAYER 3 — Pathway / Latent Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_PATH_HPA": [
        ("HPA axis", "primary"),
        ("hypothalamic-pituitary-adrenal axis", "synonym"),
        ("HPA axis dysregulation", "synonym"),
        ("adrenal function", "synonym"),
        ("neuroendocrine stress response", "synonym"),
        ("hypothalamo-hypophyseal system", "mesh_heading"),
        # exclude — pathological HPA conditions
        ("Cushing syndrome", "exclude"),
        ("Addison disease", "exclude"),
    ],
    "NODE_PATH_NEUROPLASTICITY": [
        ("neuroplasticity", "primary"),
        ("neural plasticity", "synonym"),
        ("synaptic plasticity", "synonym"),
        ("brain plasticity", "synonym"),
        ("neuronal plasticity", "synonym"),
        ("neuronal plasticity", "mesh_heading"),
    ],
    "NODE_PATH_OIC": [
        ("neuroinflammation", "primary"),
        ("oxidative inflammatory cascade", "synonym"),
        ("central inflammation", "synonym"),
        ("neuroinflammatory response", "synonym"),
        ("brain inflammation", "synonym"),
        ("oxidative stress brain", "synonym"),
        ("neuroinflammatory diseases", "mesh_heading"),
        # exclude — different neuroinflammatory conditions
        ("traumatic brain injury", "exclude"),
        ("multiple sclerosis", "exclude"),
    ],
    "NODE_PATH_NEUROGENESIS": [
        ("neurogenesis", "primary"),
        ("adult neurogenesis", "synonym"),
        ("hippocampal neurogenesis", "synonym"),
        ("neural stem cells", "synonym"),
        ("neural progenitor cells", "synonym"),
        ("neurogenesis", "mesh_heading"),
    ],
    "NODE_PATH_EPIGENETIC": [
        ("epigenetic changes", "primary"),
        ("DNA methylation", "synonym"),
        ("epigenetic aging", "synonym"),
        ("epigenetic clock", "synonym"),
        ("histone modification", "synonym"),
        ("epigenomics", "mesh_heading"),
    ],
    "NODE_PATH_SENESCENCE": [
        ("cellular senescence", "primary"),
        ("senescence-associated secretory phenotype", "synonym"),
        ("SASP", "abbreviation"),
        ("telomere shortening", "synonym"),
        ("biological aging", "synonym"),
        ("cellular senescence", "mesh_heading"),
    ],
    "NODE_PATH_GUT_BRAIN": [
        ("gut-brain axis", "primary"),
        ("microbiota-gut-brain axis", "synonym"),
        ("enteric nervous system", "synonym"),
        ("gut microbiome brain", "synonym"),
        ("brain-gut axis", "mesh_heading"),
    ],
    "NODE_PATH_METABOLIC": [
        ("metabolic dysfunction", "primary"),
        ("metabolic syndrome", "synonym"),
        ("insulin resistance brain", "synonym"),
        ("cancer metabolism", "synonym"),
        ("cerebral glucose metabolism", "synonym"),
        ("metabolic syndrome", "mesh_heading"),
    ],
    "NODE_PATH_BBB": [
        ("blood-brain barrier", "primary"),
        ("BBB", "abbreviation"),
        ("BBB permeability", "synonym"),
        ("BBB disruption", "synonym"),
        ("BBB integrity", "synonym"),
        ("blood-brain barrier", "mesh_heading"),
    ],
    "NODE_PATH_CEREBROVASCULAR": [
        ("cerebrovascular function", "primary"),
        ("cerebral blood flow", "synonym"),
        ("cerebrovascular health", "synonym"),
        ("white matter hyperintensities", "synonym"),
        ("cerebrovascular circulation", "mesh_heading"),
    ],
    "NODE_PATH_DOPAMINERGIC": [
        ("dopaminergic system", "primary"),
        ("dopamine", "synonym"),
        ("dopamine signaling", "synonym"),
        ("dopaminergic function", "synonym"),
        ("dopaminergic neurotransmission", "synonym"),
        ("dopamine", "mesh_heading"),
    ],
    "NODE_PATH_SYNAPTIC": [
        ("synaptic function", "primary"),
        ("synaptic transmission", "synonym"),
        ("synaptic integrity", "synonym"),
        ("neurotransmission", "synonym"),
        ("synaptic plasticity", "synonym"),
        ("synaptic transmission", "mesh_heading"),
    ],
    "NODE_PATH_MYELIN": [
        ("myelin integrity", "primary"),
        ("myelination", "synonym"),
        ("demyelination", "synonym"),
        ("white matter integrity", "synonym"),
        ("myelin sheath", "mesh_heading"),
    ],
    "NODE_PATH_GLYMPHATIC": [
        ("glymphatic system", "primary"),
        ("glymphatic clearance", "synonym"),
        ("brain waste clearance", "synonym"),
        ("CSF flow", "synonym"),
        ("perivascular drainage", "synonym"),
        ("glymphatic system", "mesh_heading"),
    ],
    "NODE_PATH_DNA_DAMAGE": [
        ("DNA damage response", "primary"),
        ("DNA repair", "synonym"),
        ("genotoxic stress", "synonym"),
        ("DNA damage", "synonym"),
        ("DNA strand breaks", "synonym"),
        ("DNA repair", "mesh_heading"),
        ("DNA damage", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # LAYER 4 — Cognitive Domain Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_COG_PROC_SPEED": [
        ("processing speed", "primary"),
        ("information processing speed", "synonym"),
        ("psychomotor speed", "synonym"),
        ("reaction time", "synonym"),
        ("simple RT", "synonym"),
        ("coding task", "synonym"),
        ("mental processing", "mesh_heading"),
    ],
    "NODE_COG_WORK_MEM": [
        ("working memory", "primary"),
        ("short-term memory", "synonym"),
        ("n-back", "synonym"),
        ("letter-number sequencing", "synonym"),
        ("spatial working memory", "synonym"),
        ("memory, short-term", "mesh_heading"),
    ],
    "NODE_COG_EPISODIC_MEM": [
        ("episodic memory", "primary"),
        ("verbal memory", "synonym"),
        ("word list recall", "synonym"),
        ("delayed recall", "synonym"),
        ("recognition memory", "synonym"),
        ("verbal learning", "synonym"),
        ("memory, episodic", "mesh_heading"),
        # exclude — neurodegenerative memory loss (different etiology)
        ("Alzheimer disease", "exclude"),
        ("dementia", "exclude"),
    ],
    "NODE_COG_ATTN_SUSTAINED": [
        ("sustained attention", "primary"),
        ("vigilance", "synonym"),
        ("concentration", "synonym"),
        ("continuous performance", "synonym"),
        ("attentional function", "synonym"),
        ("attention", "mesh_heading"),
    ],
    "NODE_COG_ATTN_SELECTIVE": [
        ("selective attention", "primary"),
        ("attentional selection", "synonym"),
        ("focused attention", "synonym"),
        ("distraction filtering", "synonym"),
        ("attention", "mesh_heading"),
    ],
    "NODE_COG_EXEC_PLANNING": [
        ("executive planning", "primary"),
        ("executive function", "synonym"),
        ("planning", "synonym"),
        ("cognitive flexibility", "synonym"),
        ("set shifting", "synonym"),
        ("task switching", "synonym"),
        ("executive function", "mesh_heading"),
    ],
    "NODE_COG_EXEC_INHIBITION": [
        ("inhibitory control", "primary"),
        ("response inhibition", "synonym"),
        ("Stroop interference", "synonym"),
        ("go/no-go", "synonym"),
        ("cognitive control", "synonym"),
        ("inhibition, psychological", "mesh_heading"),
    ],
    "NODE_COG_VERBAL_FLUENCY": [
        ("verbal fluency", "primary"),
        ("phonemic fluency", "synonym"),
        ("semantic fluency", "synonym"),
        ("word generation", "synonym"),
        ("category fluency", "synonym"),
    ],
    "NODE_COG_VISUOSPATIAL": [
        ("visuospatial function", "primary"),
        ("visuospatial ability", "synonym"),
        ("spatial processing", "synonym"),
        ("visual construction", "synonym"),
        ("spatial navigation", "mesh_heading"),
    ],
    "NODE_COG_LANGUAGE": [
        ("language function", "primary"),
        ("naming", "synonym"),
        ("word finding", "synonym"),
        ("anomia", "synonym"),
        ("language", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # LAYER 5 — Symptom Nodes
    # ───────────────────────────────────────────────────────────
    "NODE_SYM_FATIGUE": [
        ("cancer-related fatigue", "primary"),
        ("cancer fatigue", "synonym"),
        ("CRF", "abbreviation"),
        ("fatigue", "synonym"),
        ("persistent fatigue", "synonym"),
        ("fatigue", "mesh_heading"),
        # exclude — different conditions with similar presentation
        ("chronic fatigue syndrome", "exclude"),
        ("myalgic encephalomyelitis", "exclude"),
    ],
    "NODE_SYM_DEPRESSION": [
        ("depression", "primary"),
        ("depressive symptoms", "synonym"),
        ("major depressive disorder", "synonym"),
        ("depressed mood", "synonym"),
        ("depressive disorder", "mesh_heading"),
        # exclude — different psychiatric conditions
        ("bipolar disorder", "exclude"),
        ("schizophrenia", "exclude"),
    ],
    "NODE_SYM_ANXIETY": [
        ("anxiety", "primary"),
        ("anxiety symptoms", "synonym"),
        ("generalized anxiety", "synonym"),
        ("cancer anxiety", "synonym"),
        ("anxiety disorders", "mesh_heading"),
    ],
    "NODE_SYM_SLEEP_DISRUPTION": [
        ("sleep disruption", "primary"),
        ("insomnia", "synonym"),
        ("sleep disturbance", "synonym"),
        ("sleep fragmentation", "synonym"),
        ("sleep efficiency", "synonym"),
        ("sleep initiation and maintenance disorders", "mesh_heading"),
        # exclude
        ("sleep apnea", "exclude"),
    ],
    "NODE_SYM_PAIN": [
        ("cancer pain", "primary"),
        ("pain", "synonym"),
        ("pain severity", "synonym"),
        ("chronic pain", "synonym"),
        ("nociceptive pain", "synonym"),
        ("cancer pain", "mesh_heading"),
    ],
    "NODE_SYM_COG_COMPLAINTS": [
        ("cognitive complaints", "primary"),
        ("perceived cognitive impairment", "synonym"),
        ("subjective cognitive decline", "synonym"),
        ("self-reported cognitive difficulties", "synonym"),
        ("cognitive failure", "synonym"),
        ("cognitive dysfunction", "mesh_heading"),
    ],
    "NODE_SYM_APPETITE": [
        ("appetite", "primary"),
        ("appetite loss", "synonym"),
        ("anorexia", "synonym"),
        ("taste changes", "synonym"),
        ("cancer anorexia", "synonym"),
        ("anorexia", "mesh_heading"),
    ],
    "NODE_SYM_DECONDITIONING": [
        ("physical deconditioning", "primary"),
        ("functional decline", "synonym"),
        ("physical function decline", "synonym"),
        ("performance status", "synonym"),
        ("frailty", "synonym"),
        ("physical fitness", "mesh_heading"),
    ],
    # ───────────────────────────────────────────────────────────
    # Composite Node
    # ───────────────────────────────────────────────────────────
    "NODE_COMP_CRCI": [
        ("cancer-related cognitive impairment", "primary"),
        ("CRCI", "abbreviation"),
        ("chemobrain", "synonym"),
        ("chemo brain", "synonym"),
        ("chemotherapy-related cognitive dysfunction", "synonym"),
        ("cognitive function cancer", "synonym"),
        ("cognition disorders", "mesh_heading"),
        ("cognitive dysfunction", "mesh_heading"),
    ],
}


# ═══════════════════════════════════════════════════════════════
#  NODE SEARCH CAVEATS — per-node instructions for human operators
#  These are NOT stored in the DB; they are emitted into prompts
#  and retrieval session sheets to guide evidence interpretation.
# ═══════════════════════════════════════════════════════════════

NODE_SEARCH_CAVEATS: dict[str, str] = {
    "NODE_BIO_BDNF": (
        "MUST distinguish plasma vs serum. Serum BDNF reflects platelet "
        "degranulation, not central levels. Our model uses PLASMA only. "
        "Serum BDNF papers may be entered but get flagged and SE-inflated."
    ),
    "NODE_BIO_CORTISOL": (
        "Slope vs CAR vs AUC are DIFFERENT constructs — always note which. "
        "Diurnal cortisol slope = primary measure. CAR and AUC are secondary. "
        "Require multiple daily samples over multiple days for reliable slope."
    ),
    "NODE_BIO_IL6": (
        "High-sensitivity assay preferred (hs-IL-6). Standard ELISA may "
        "miss low-grade inflammation values. High intra-individual variability; "
        "single timepoint unreliable. Note assay type when extracting."
    ),
    "NODE_BIO_CRP": (
        "hs-CRP preferred. Standard CRP may miss low-grade inflammation. "
        "Acute infections can spike CRP 100x — note if study excluded acute illness."
    ),
    "NODE_BIO_TNF": (
        "TNF-α has very short half-life (~20 min). Soluble TNF receptors "
        "(sTNFR1, sTNFR2) may be more reliable markers. Note measurement method."
    ),
    "NODE_BIO_NFL": (
        "Plasma NfL is a neuroaxonal damage marker. Elevated in many "
        "neurodegenerative conditions — not specific to chemotherapy. "
        "Must be chemotherapy-induced elevation, not pre-existing."
    ),
    "NODE_BIO_SHANNON": (
        "Diversity metrics vary: Shannon-H, Simpson, observed OTUs, Chao1. "
        "Note which metric. 16S vs shotgun sequencing matters for resolution."
    ),
    "NODE_BIO_GH2AX": (
        "γ-H2AX foci counts vary by methodology (flow cytometry vs IF). "
        "Timing critical — peaks 30min-2hr post-exposure, clears within 24hr."
    ),
    "NODE_BIO_GLUCOSE": (
        "Fasting glucose vs HbA1c vs HOMA-IR measure different aspects of "
        "metabolic function. HOMA-IR preferred for insulin resistance assessment."
    ),
}


# ═══════════════════════════════════════════════════════════════
#  OBSERVATION NOISE — default σ² per instrument/measure
# ═══════════════════════════════════════════════════════════════

# Derived from published psychometric properties.
# noise_variance = 1 - reliability_alpha (for questionnaires)
# or estimated from test-retest ICC.
OBSERVATION_NOISE_DEFAULTS: list[dict] = [
    {
        "noise_id": "NOISE_PSQI",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_PSQI",
        "reliability_alpha": 0.83,
        "noise_variance": 0.17,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Buysse et al. 1989; Carpenter & Andrykowski 1998",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_FACIT_F",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_FACIT_F",
        "reliability_alpha": 0.95,
        "noise_variance": 0.05,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Yellen et al. 1997; Cella et al. 2002",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_BFI",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_BFI",
        "reliability_alpha": 0.96,
        "noise_variance": 0.04,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Mendoza et al. 1999",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_FACT_COG",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_FACT_COG",
        "reliability_alpha": 0.92,
        "noise_variance": 0.08,
        "noise_source": "psychometric",
        "cancer_validation_status": "validated_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Wagner et al. 2009",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_TRAIL_B",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_TRAIL_B",
        "reliability_alpha": 0.89,
        "noise_variance": 0.11,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Strauss et al. 2006",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.15 for general_population validation",
    },
    {
        "noise_id": "NOISE_HVLT_R",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_HVLT_R",
        "reliability_alpha": 0.74,
        "noise_variance": 0.26,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Brandt & Benedict 2001",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.15 for general_population; alternate forms available",
    },
    {
        "noise_id": "NOISE_PHQ9",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_PHQ9",
        "reliability_alpha": 0.89,
        "noise_variance": 0.11,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Kroenke et al. 2001",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_GAD7",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_GAD7",
        "reliability_alpha": 0.92,
        "noise_variance": 0.08,
        "noise_source": "psychometric",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.0,
        "source_citation": "Spitzer et al. 2006",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_DSST",
        "target_entity_type": "instrument",
        "target_entity_id": "INST_DSST",
        "reliability_alpha": 0.82,
        "noise_variance": 0.18,
        "noise_source": "test_retest",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.15,
        "source_citation": "Wechsler 2008 (WAIS-IV manual)",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_IL6_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_IL6_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.30,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "Estimated from assay CV and biological variability",
        "condition_dependent": 1,
        "condition_description": "High intra-individual variability; single timepoint unreliable",
        "version": 1,
        "active": 1,
        "notes": "SE multiplier 1.3 for estimated noise source",
    },
    {
        "noise_id": "NOISE_CRP_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_CRP_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.25,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "Estimated from assay CV and biological variability",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_CORTISOL_SALIVA",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_CORTISOL_SALIVA",
        "reliability_alpha": None,
        "noise_variance": 0.35,
        "noise_source": "estimated",
        "cancer_validation_status": "used_cancer",
        "se_multiplier": 1.3,
        "source_citation": "High diurnal and day-to-day variability; Adam & Kumari 2009",
        "condition_dependent": 1,
        "condition_description": "Requires multiple daily samples over multiple days",
        "version": 1,
        "active": 1,
    },
    {
        "noise_id": "NOISE_BDNF_SERUM",
        "target_entity_type": "measure",
        "target_entity_id": "MEAS_BDNF_SERUM",
        "reliability_alpha": None,
        "noise_variance": 0.35,
        "noise_source": "estimated",
        "cancer_validation_status": "general_population",
        "se_multiplier": 1.3,
        "source_citation": "High platelet-bound fraction; Lommatzsch et al. 2005",
        "condition_dependent": 0,
        "version": 1,
        "active": 1,
        "notes": "Serum BDNF strongly affected by platelet count and handling",
    },
]


# ═══════════════════════════════════════════════════════════════
#  FEEDBACK LOOPS — cycles in the edge graph
# ═══════════════════════════════════════════════════════════════

FEEDBACK_LOOPS: list[dict] = [
    {
        "loop_id": "LOOP_SLEEP_IL6",
        "loop_label": "Sleep-Inflammation Bidirectional Loop",
        "edge_relation_ids_json": '["EDGE_SLEEP_IL6", "EDGE_IL6_SLEEP"]',
        "node_ids_json": '["NODE_SLEEP_QUALITY", "NODE_IL6"]',
        "loop_gain": 0.3,
        "characteristic_period_weeks": "2-4",
        "forward_dynamics": "Poor sleep activates NF-kB, elevating IL-6 within days",
        "reverse_dynamics": "Elevated IL-6 fragments sleep via prostaglandin-mediated mechanisms",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.15,
        "version": 1,
        "notes": "Well-established bidirectional relationship; Irwin 2015",
    },
    {
        "loop_id": "LOOP_FATIGUE_SLEEP",
        "loop_label": "Fatigue-Sleep Disruption Loop",
        "edge_relation_ids_json": '["EDGE_SLEEP_FATIGUE", "EDGE_FATIGUE_COGNITION"]',
        "node_ids_json": '["NODE_SLEEP_QUALITY", "NODE_FATIGUE", "NODE_COGNITION"]',
        "loop_gain": 0.25,
        "characteristic_period_weeks": "1-2",
        "forward_dynamics": "Poor sleep causes daytime fatigue and cognitive impairment",
        "reverse_dynamics": "Fatigue leads to daytime napping disrupting nighttime sleep",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.10,
        "version": 1,
        "notes": "Clinical cycle commonly observed in cancer survivors",
    },
    {
        "loop_id": "LOOP_DEPRESSION_FATIGUE",
        "loop_label": "Depression-Fatigue Bidirectional Loop",
        "edge_relation_ids_json": '["EDGE_DEPRESSION_FATIGUE"]',
        "node_ids_json": '["NODE_DEPRESSION", "NODE_FATIGUE"]',
        "loop_gain": 0.35,
        "characteristic_period_weeks": "4-8",
        "forward_dynamics": "Depressive symptoms amplify fatigue perception and reduce motivation",
        "reverse_dynamics": "Persistent fatigue triggers hopelessness and anhedonia",
        "breaking_intervention": None,
        "spectral_radius_contribution": 0.12,
        "version": 1,
        "notes": "Shared serotonergic and inflammatory mechanisms; Brown & Kroenke 2009",
    },
]


def _upsert_search_term(session, node_id: str, term_text: str, term_type: str) -> bool:
    """Insert a single search term if it doesn't already exist. Returns True if inserted."""
    existing = session.execute(
        text(
            "SELECT 1 FROM node_search_terms_v1 "
            "WHERE node_id = :nid AND term = :t"
        ),
        {"nid": node_id, "t": term_text},
    ).first()
    if existing:
        return False
    session.execute(
        text(
            "INSERT INTO node_search_terms_v1 (node_id, term, term_type, active) "
            "VALUES (:nid, :t, :tt, 1)"
        ),
        {"nid": node_id, "t": term_text, "tt": term_type},
    )
    return True


def generate_search_terms(session) -> int:
    """Insert node_search_terms rows from the curated dictionary."""
    count = 0
    for node_id, terms in NODE_SEARCH_TERMS.items():
        for term_text, term_type in terms:
            if _upsert_search_term(session, node_id, term_text, term_type):
                count += 1
    return count


def generate_instrument_search_terms(session) -> int:
    """Auto-generate search terms from instrument_definitions_v1.

    For each instrument, adds its instrument_label and instrument_id short form
    as term_type='instrument' under the instrument's maps_to_node_id.
    This ensures every node with instruments gets searchable instrument names.
    """
    rows = session.execute(
        text(
            "SELECT instrument_id, instrument_label, maps_to_node_id "
            "FROM instrument_definitions_v1 "
            "WHERE active = 1 AND maps_to_node_id IS NOT NULL"
        )
    ).fetchall()

    count = 0
    for row in rows:
        inst_id, inst_label, node_id = row[0], row[1], row[2]

        # Skip clinical/administrative instruments that aren't useful search terms
        if inst_id.startswith("INST_CLINICAL_"):
            continue

        # Add full instrument name as term_type='instrument'
        if inst_label and _upsert_search_term(session, node_id, inst_label, "instrument"):
            count += 1

        # Add abbreviation from instrument_id (e.g., INST_PSQI -> PSQI)
        short_name = inst_id.replace("INST_", "").replace("_", "-")
        # Only add if it's a recognizable short name (not too long)
        if len(short_name) <= 12 and _upsert_search_term(session, node_id, short_name, "instrument"):
            count += 1

    logger.info("Auto-generated %d instrument search terms from instrument_definitions_v1", count)
    return count


def generate_observation_noise(session) -> int:
    """Insert observation_noise rows from psychometric defaults."""
    count = 0
    for noise in OBSERVATION_NOISE_DEFAULTS:
        existing = session.execute(
            text("SELECT 1 FROM observation_noise_v1 WHERE noise_id = :nid"),
            {"nid": noise["noise_id"]},
        ).first()
        if existing:
            continue

        cols = [k for k in noise.keys() if noise[k] is not None]
        placeholders = [f":{k}" for k in cols]
        session.execute(
            text(
                f"INSERT INTO observation_noise_v1({', '.join(cols)}) "
                f"VALUES ({', '.join(placeholders)})"
            ),
            {k: noise[k] for k in cols},
        )
        count += 1
    return count


def generate_feedback_loops(session) -> int:
    """Insert feedback_loop rows from edge analysis."""
    count = 0
    for loop in FEEDBACK_LOOPS:
        existing = session.execute(
            text("SELECT 1 FROM feedback_loops_v1 WHERE loop_id = :lid"),
            {"lid": loop["loop_id"]},
        ).first()
        if existing:
            continue

        cols = [k for k in loop.keys() if loop[k] is not None]
        placeholders = [f":{k}" for k in cols]
        session.execute(
            text(
                f"INSERT INTO feedback_loops_v1({', '.join(cols)}) "
                f"VALUES ({', '.join(placeholders)})"
            ),
            {k: loop[k] for k in cols},
        )
        count += 1
    return count


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate derived seed data from core Class A tables",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    init_db()

    print("\n--- Generating derived seed data ---\n")

    with get_session() as session:
        # 1. Node search terms (hand-curated)
        terms_count = generate_search_terms(session)
        print(f"  Node search terms:    {terms_count} rows inserted (hand-curated)")

        # 2. Instrument-derived search terms (auto-generated from DB)
        inst_count = generate_instrument_search_terms(session)
        print(f"  Instrument terms:     {inst_count} rows inserted (auto-generated)")

        # 3. Observation noise
        noise_count = generate_observation_noise(session)
        print(f"  Observation noise:    {noise_count} rows inserted")

        # 4. Feedback loops
        loops_count = generate_feedback_loops(session)
        print(f"  Feedback loops:       {loops_count} rows inserted")

    total = terms_count + inst_count + noise_count + loops_count
    print(f"\nTotal derived rows: {total}")

    # Print coverage summary
    print("\n--- Search Term Coverage Summary ---")
    with get_session() as session:
        total_terms = session.execute(
            text("SELECT count(*) FROM node_search_terms_v1 WHERE active = 1")
        ).scalar()
        nodes_covered = session.execute(
            text("SELECT count(DISTINCT node_id) FROM node_search_terms_v1 WHERE active = 1")
        ).scalar()
        total_nodes = session.execute(
            text("SELECT count(*) FROM biomarker_node_definitions_v1")
        ).scalar()
        by_type = session.execute(
            text(
                "SELECT term_type, count(*) FROM node_search_terms_v1 "
                "WHERE active = 1 GROUP BY term_type ORDER BY count(*) DESC"
            )
        ).fetchall()
        exclude_count = session.execute(
            text(
                "SELECT count(*) FROM node_search_terms_v1 "
                "WHERE term_type = 'exclude' AND active = 1"
            )
        ).scalar()

    print(f"  Total terms:     {total_terms}")
    print(f"  Nodes covered:   {nodes_covered}/{total_nodes}")
    print(f"  Exclude terms:   {exclude_count}")
    print(f"  By type:")
    for tt, cnt in by_type:
        print(f"    {tt:20s} {cnt}")
    print(f"  Caveats defined: {len(NODE_SEARCH_CAVEATS)} nodes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
