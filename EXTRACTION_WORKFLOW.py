#!/usr/bin/env python3
"""
CRCI Paper Extraction Workflow
Interactive guided extraction for converting papers to CSV templates.

This script helps extract key findings from research papers and 
populate the CRCI database templates.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Paper metadata - update from your extraction_summaries.json
PAPERS_TO_EXTRACT = [
    {
        "pmid": "29759139",
        "doi": "10.1016/j.jneuroim.2018.04.012",
        "title": "Identifying cytokine predictors of cognitive functioning in breast cancer survivors up to 10 years post chemotherapy using machine learning",
        "authors": ["Henneghan, Ashley M.", "Palesh, Oxana", "Harrison, Michelle"],
        "journal": "Journal of Neuroimmunology",
        "year": 2018,
        "doi_slug": "10.1016_j.jneuroim.2018.04.012"
    },
    {
        "pmid": "29187817",
        "doi": "10.3389/fnhum.2017.00555",
        "title": "Predicting Long-Term Cognitive Outcome Following Breast Cancer with Pre-Treatment Resting State fMRI and Random Forest Machine Learning",
        "authors": ["(See summary file)"],
        "journal": "Frontiers in Human Neuroscience",
        "year": 2017,
        "doi_slug": "10.3389_fnhum.2017.00555"
    },
    {
        "pmid": "22698992",
        "doi": "10.1016/j.bbi.2012.05.017",
        "title": "Reduced hippocampal volume and verbal memory performance associated with interleukin-6 and tumor necrosis factor-alpha levels in older adults",
        "authors": ["Kesler, Shelli", "Janelsins, Michelle", "Koovakkattu, Della"],
        "journal": "Brain, Behavior, and Immunity",
        "year": 2012,
        "doi_slug": "10.1016_j.bbi.2012.05.017"
    },
    {
        "pmid": "32482100",
        "doi": "10.1177/0844562120927535",
        "title": "A Cross-Sectional Exploration of Cytokine–Symptom Networks in Breast Cancer Survivors With Cancer-Related Cognitive Impairment",
        "authors": ["Henneghan, Ashley", "Wright, Michelle L.", "Bourne, Garrett"],
        "journal": "Journal of Oncology Practice",
        "year": 2020,
        "doi_slug": "10.1177_0844562120927535"
    },
    {
        "pmid": "30328048",
        "doi": "10.1007/s10549-018-4990-9",
        "title": "Multivariate machine learning models for prediction of pathologic response to neoadjuvant chemotherapy in breast cancer using MR imaging features",
        "authors": ["Cain, Elizabeth Hope", "Saha, Ashirbani", "Harowicz, Michael R."],
        "journal": "Breast Cancer Research and Treatment",
        "year": 2018,
        "doi_slug": "10.1007_s10549-018-4990-9"
    },
    {
        "pmid": "25922060",
        "doi": "10.1093/annonc/mdv206",
        "title": "Association of proinflammatory cytokines and chemotherapy-associated cognitive impairment and depression",
        "authors": ["Cheung, Y T", "Ng, T", "Shwe, M"],
        "journal": "Annals of Oncology",
        "year": 2015,
        "doi_slug": "10.1093_annonc_mdv206"
    },
    {
        "pmid": "23616206",
        "doi": "10.1136/amiajnl-2012-001332",
        "title": "Machine learning for predicting the response of breast cancer to neoadjuvant chemotherapy",
        "authors": ["Mani, Subramani", "Chen, Yukun", "Li, Xia"],
        "journal": "JAMIA",
        "year": 2013,
        "doi_slug": "10.1136_amiajnl-2012-001332"
    },
]

def print_extraction_guide():
    """Print guide for manual extraction."""
    print("""
╔════════════════════════════════════════════════════════════════════════╗
║                    CRCI PAPER EXTRACTION GUIDE                         ║
║                      For 7 Retrieved Papers                            ║
╚════════════════════════════════════════════════════════════════════════╝

WHAT TO EXTRACT FROM EACH PAPER:
─────────────────────────────────

1. STUDY DESIGN
   □ RCT (Randomized Controlled Trial)
   □ Cohort (prospective or retrospective)
   □ Cross-sectional
   □ Case-control
   □ Pre-post design
   Find in: Abstract and Methods section

2. CANCER TYPE
   □ breast
   □ hematological
   □ colorectal
   □ lung
   □ other (specify)
   Find in: Methods → Study Population

3. POPULATION CHARACTERISTICS
   - Sample size (N)
   - Mean age
   - Gender distribution
   - Cancer stage
   - Treatment type (chemotherapy, radiation, surgery, etc.)
   Find in: Methods → Participants or Results

4. COGNITIVE OUTCOMES MEASURED
   Identify each cognitive test and corresponding effect size:
   - Instrument name (e.g., HVLT-R, MMSE, Stroop)
   - Instrument code from registry (INST_*)
   - Timepoints measured
   - Baseline vs. post-treatment comparison
   Find in: Methods → Outcome Measures and Results → Cognitive Outcomes

5. EFFECT SIZES AND STATISTICAL INFO
   For each significant cognitive relationship:
   - Effect type (Cohen's d, mean difference, odds ratio, correlation r)
   - Effect value (numerical)
   - Standard error or confidence interval
   - p-value
   - Sample sizes (treatment/control)
   - Adjustment covariates
   Find in: Results tables and figures

6. KEY RELATIONSHIPS (EDGES)
   Look for:
   - Cytokine/biomarker → Cognitive outcome  (ER_BIOMARKER_COGNITION)
   - Chemotherapy → Cognitive outcome         (ER_CHEMO_COGNITION)
   - Exercise/activity → Cognitive outcome    (ER_ACTIVITY_COGNITION)
   - Sleep → Cognitive outcome                (ER_SLEEP_COGNITION)
   - Other pathways relevant to CRCI

═══════════════════════════════════════════════════════════════════════════

PAPER-BY-PAPER CHECKLIST:
─────────────────────────
""")
    
    for i, paper in enumerate(PAPERS_TO_EXTRACT, 1):
        print(f"""
{i}. PMID {paper['pmid']} — {paper['year']}
   DOI: {paper['doi']}
   Title: {paper['title'][:60]}...
   
   Extraction checklist:
   ☐ Study design identified
   ☐ Sample size and characteristics extracted
   ☐ Cognitive instruments identified
   ☐ Effect sizes with SEs extracted
   ☐ CSV templates created in: data/manual_uploads/structured/{paper['doi_slug']}/
   ☐ Files ready to load: edge_evidence_template.csv + others
   ☐ Meta.json created with DOI and quality markers
""")
    
    print("""
═══════════════════════════════════════════════════════════════════════════

HOW TO FILL THE CSV TEMPLATES:
─────────────────────────────

For EACH finding in a paper, create ONE ROW in edge_evidence_template.csv:

┌─────────────────────────────────────────────────────────────────┐
│ REQUIRED COLUMNS (must fill):                                   │
├─────────────────────────────────────────────────────────────────┤
│ doi                      → Paper DOI (e.g., 10.1016/j.bbi...)  │
│ edge_relation_id         → Causal relationship ID               │
│ effect_value_reported    → Effect size (Cohen's d preferred)    │
│ se_reported              → Standard error                        │
│ effect_type_reported     → How effect was reported              │
│ effect_size_type         → BETWEEN_GROUP / WITHIN_GROUP / etc   │
│ N_effect                 → Analysis sample size                 │
│ study_design             → RCT, cohort, cross_sectional, etc   │
│ cancer_type              → breast, hematological, mixed, etc    │
│ treatment_phase          → active_treatment, early_recovery,... │
│ upstream_instrument_id   → Cognitive test ID (INST_*)          │
└─────────────────────────────────────────────────────────────────┘

OPTIONAL COLUMNS:
  ci_low_reported, ci_high_reported,  p_value
  n_treatment, n_control,  covariates_adjusted
  rob_overall (low/moderate/high),  notes,  extraction_snippet

═══════════════════════════════════════════════════════════════════════════

SPECIAL INSTRUCTIONS:

A) EFFECT SIZE DERIVATION
   If the paper reports means ± SD, calculate Cohen's d:
   
   d = (M_treatment - M_control) / SD_pooled
   
   If the paper reports t-statistic:
   
   d = 2t / √(df)
   
   See: extraction_ref/03_SE_DERIVATION.md for full formulas

B) SIGN CONVENTION
   Always extract the PAPER'S reported sign.
   - Positive effect = improvement in outcome
   - Let the database pipeline handle harmonization
   
C) MISSING DATA
   If p-value not reported but t-test given:
     1. Use SE = effect / t
   If only 95% CI given:
     2. Use SE = (CI_upper - CI_lower) / (2 × 1.96)
   If only N and effect:
     3. Use SE ≈ √(4/N)

═══════════════════════════════════════════════════════════════════════════

NEXT STEPS:

1. Read each paper PDF/XML carefully
2. For EACH finding, fill one row of edge_evidence_template.csv
3. Example row:

   doi | edge_relation_id | effect_value | se_reported | ...
   ────┼──────────────────┼──────────────┼─────────────┼────
   10.1016/j.bbi.2012.05.017 | ER_IL6_MEMORY | -0.48 | 0.15 | ...

4. Save to: data/manual_uploads/structured/<doi-slug>/edge_evidence.csv
5. Create meta.json file in same directory
6. Repeat for all 7 papers
7. Run: python scripts/load_evidence_into_db.py

═══════════════════════════════════════════════════════════════════════════
""")

if __name__ == "__main__":
    print_extraction_guide()
