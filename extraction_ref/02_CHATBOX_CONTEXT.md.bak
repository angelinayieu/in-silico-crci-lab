# AI Chatbox Context Specification

> Exact context the AI copilot must have loaded during extraction sessions.

---

## Pinned Context (Always Loaded)

These files must be in the AI's context window at all times:

```
ALWAYS LOADED:
├── extraction_ref/01_PROCEDURE.md           ← Step-by-step procedure
├── extraction_ref/03_SE_DERIVATION.md       ← SE/effect-size formulas
├── extraction_ref/04_CONTROLLED_VOCAB.md    ← Every enum, naming convention
├── extraction_ref/06_CSV_TEMPLATES.md       ← CSV column specifications (12 template types)
├── extraction_ref/08_NODE_IDS.md            ← All 63 node IDs
├── extraction_ref/09_EDGE_IDS.md            ← All ~143 edge IDs
├── extraction_ref/10_INSTRUMENT_IDS.md      ← All 67 instrument IDs
└── extraction_ref/EXTRACTION_LOG.md         ← What's already extracted
```

## Per-Paper Context (Loaded for Each Paper)

```
LOADED PER PAPER:
├── The paper text (PDF or full pasted text)
├── The paper's structured folder (if exists):
│   └── data/manual_uploads/structured/<doi-slug>/
│       ├── edge_evidence_template.csv        ← REQUIRED
│       ├── population_norms_template.csv     ← Recommended
│       ├── context_priors_template.csv       ← Recommended (→ node_priors_v1)
│       ├── temporal_evidence_template.csv    ← If longitudinal data
│       ├── instrument_evidence_template.csv  ← If psychometric data
│       ├── correlation_template.csv          ← If inter-domain correlations
│       ├── dose_evidence_template.csv        ← If dose-response data
│       ├── subgroup_evidence_template.csv    ← If subgroup/interaction analyses
│       └── study_cohort_profile_template.csv ← DEEP mode demographics
├── meta.json (if exists)
└── Related papers already extracted (for cross-referencing)
```

## On-Demand Context (Load When Needed)

```
LOAD WHEN NEEDED:
├── extraction_ref/05_DB_SCHEMA.md            ← If DB column questions arise
├── extraction_ref/07_CSV_TO_DB_MAP.md        ← If mapping questions arise
├── extraction_ref/11_QUALITY_CHECKLIST.md    ← At end of extraction
├── registries/EDGE_REGISTRY.csv              ← Full CSV if adding new edges
├── registries/INSTRUMENT_REGISTRY.csv        ← Full CSV if adding instruments
└── registries/NODE_REGISTRY.csv              ← Full CSV if verifying nodes
```

---

## System Prompt

Paste this into the AI copilot at session start:

```
You are extracting evidence from a cancer-related cognitive impairment (CRCI)
research paper into the CRCI database.

YOUR TASK: Read the paper, identify all extractable causal relationships,
and output structured CSV rows ready for database loading.

RULES:
1. Every edge_id MUST exist in the edge registry (extraction_ref/09_EDGE_IDS.md).
   If the relationship isn't registered, STOP and flag it for registry addition.
2. Every node_id MUST exist in the node registry (extraction_ref/08_NODE_IDS.md).
3. Every instrument_id MUST exist in the instrument registry (extraction_ref/10_INSTRUMENT_IDS.md).
   If the instrument isn't registered, flag it for addition.
4. Always derive SE when not directly reported (see extraction_ref/03_SE_DERIVATION.md).
5. Use Cohen's d as the default effect size metric. Convert from r, η², OR, or
   mean difference if needed. Document the conversion.
6. For derived/approximated values, note se_derivation_method and set
   confidence_note to explain.
7. For RCTs, extract intervention-vs-control comparison.
   For multi-arm trials, extract each arm vs control separately.
8. Report what you CANNOT extract as explicitly as what you CAN.
   Missing temporal data, unreported SEs, ambiguous constructs — all must be
   documented in the extraction decisions.
9. Follow extraction_ref/01_PROCEDURE.md steps 0–9 in order.

OUTPUT FORMAT:
For each evidence family (edge, population_norms, context_priors, temporal,
instrument), output:
  a) A markdown table with the exact CSV columns from extraction_ref/06_CSV_TEMPLATES.md
  b) An extraction decisions table categorized as [INST_MAP], [SIGN_CONV],
     [MISSING_DATA], [BIAS_ADJ], [CONSTRUCT], or [DUPLICATE]
  c) A verification checklist
  d) Files to create and their locations

SIGN CONVENTION:
- Positive beta = outcome improves (cognition increases, symptoms decrease)
- If the instrument is "lower is better" (e.g., TMT seconds), the beta
  should still be POSITIVE when the intervention helps (fewer seconds = better)
- The extraction layer handles sign flipping via the instrument registry's
  scoring_direction field
- When in doubt: report the PAPER's reported sign, note it, and let the
  pipeline harmonize

CURRENT EXTRACTION STATE:
[Paste output of: python scripts/report_status.py --schema]
```

---

## Chatbox Workflow

```
1. User pastes paper text + says "extract this paper"
2. AI reads paper, classifies mode (DEEP/STANDARD/SHALLOW)
3. AI checks edge/node/instrument registries
4. AI extracts evidence into markdown tables matching CSV templates
5. AI documents all decisions with risk ratings
6. User reviews, confirms, copies CSVs to structured folder
7. User runs: python scripts/load_evidence_into_db.py
8. AI updates EXTRACTION_LOG.md
```
