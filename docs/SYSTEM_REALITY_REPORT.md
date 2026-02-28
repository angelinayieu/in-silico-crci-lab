# CRCI System Reality Report

> Generated 2026-02-27 from ground-truth code + DB audit.
> This is the authoritative "what actually exists and works" document.

---

## 1. THE SYSTEM IN ONE PAGE

The CRCI system has **two independent pipelines** connected by a single table:

```
PIPELINE 1: EXTRACTION (manual CSV → DB)
  You fill 12 CSV templates per paper
      → python scripts/load_evidence_into_db.py
          → Writes to 11 DB tables
          → Auto-harmonizes scales (Cohen's d)
          → Auto-compiles IVW edges → edges_v1

PIPELINE 2: ALGORITHM (DB → recommendations)  
  python scripts/run_full_model.py --patient-id PAT_001 --cancer-type breast ...
      → Chain A: reads registries/*.csv → builds DAG
      → Chain B: reads edge_evidence_v1 (10 cols) → evidence weights
      → Chain C: reads node_priors_v1 → Bayesian posteriors
      → Chain D: reads action_catalog_v1 + dose_bridges_v1 → MC simulation → ranking
      → Chain E: in-memory → temporal trajectories
      → Chain F: in-memory → composite scores + analytics
      → Runtime: session + report assembly → terminal output
```

**The bridge between them is `edge_evidence_v1`** — 18 rows today, 107 columns in
schema, 45 columns populated, Chain B reads only 10 of them.

---

## 2. TABLES THAT ACTUALLY MATTER (22 with data)

### TIER 1: CRITICAL PATH (data flows through these)

| Table | Rows | Written By | Read By | Status |
|-------|------|-----------|---------|--------|
| `edge_evidence_v1` | 18 | load_evidence_into_db.py | Chain B, IVW compiler | **CORE** — sole extraction→algorithm bridge |
| `edges_v1` | 17 | load_evidence IVW step | Chain A (graph weights) | **CORE** — compiled edge parameters |
| `study_registry_v1` | 4 | load_evidence | Chain B (study lookup) | **CORE** — DOI→study_id map |
| `edge_relations_definitions_v1` | 141 | load_evidence (reseeds from EDGE_REGISTRY.csv) | load_evidence (edge metadata lookup) | Registry mirror |
| `biomarker_node_definitions_v1` | 63 | load_evidence (reseeds from NODE_REGISTRY.csv) | — | Registry mirror |
| `instrument_definitions_v1` | 67 | load_evidence (reseeds from INSTRUMENT_REGISTRY.csv) | — | Registry mirror |
| `measure_definitions_v1` | 82 | load_evidence (reseeds from MEASURE_REGISTRY.csv) | — | Registry mirror |
| `pathways_v1` | 22 | load_evidence (reseeds from PATHWAY_REGISTRY.csv) | — | Registry mirror |
| `action_catalog_v1` | 8 | load_evidence (seeds) | Chain D (intervention_loader) | **ACTIVE** — interventions |
| `dose_bridges_v1` | 10 | load_evidence (seeds) | Chain D (intervention_loader) | **ACTIVE** — dose-response curves |
| `node_priors_v1` | 12 | load_evidence (from context_priors CSVs) | Chain C (prior_loader) | **ACTIVE** — Bayesian priors |
| `population_norms_v1` | 14 | load_evidence (from population_norms CSVs) | P7 prior_compiler, SD borrowing | **ACTIVE** — baseline norms |
| `temporal_evidence_v1` | 16 | load_evidence (from temporal CSVs) | P7 temporal_compiler | **ACTIVE** — trajectories |
| `instrument_evidence_v1` | 9 | load_evidence (from instrument CSVs) | P7 psychometric_compiler | **ACTIVE** — reliability data |
| `observation_noise_v1` | 13 | seed_loader | Chain B (planned) | Seeded, referenced |

### TIER 2: SEEDED BUT NOT ON CRITICAL PATH

| Table | Rows | Notes |
|-------|------|-------|
| `acquisition_queue_v1` | 15 | Paper retrieval queue — ops tracking |
| `baseline_modifier_definitions_v1` | 15 | Modifier seeds — not yet consumed |
| `node_search_terms_v1` | 504 | Search terms — retrieval aid |
| `feedback_loops_v1` | 3 | DAG feedback edges — not consumed by algorithm |
| `predictor_alignment_rules_v1` | 7 | Template alignment — not consumed |
| `action_contraindication_links_v1` | 6 | Contraindication links — Chain D reads contraindication_rules_v1 but it's EMPTY |
| `variable_to_input_map_v1` | 12 | Variable mapping — not consumed |

### TIER 3: EMPTY (0 rows, exist in schema only)

61 tables are empty. Notable ones:
- `contraindication_rules_v1` — Chain D tries to load this, falls back to empty set
- `intervention_kernels_v1` — Chain D tries to load this, falls back to empty set
- `biomarker_correlations_v1` — Would feed Chain C cross-domain correlations
- `dose_evidence_v1` — Template exists, no papers have filled it yet
- `subgroup_evidence_v1` — Template exists, no papers have filled it yet
- `harmonization_rules_v1` — NEVER READ BY ANY CODE (see §3)

---

## 3. HARMONIZATION RULES: THE VERDICT

**Q: Does the pipeline need `harmonization_rules_v1`?**

**A: NO. Harmonization logic is 100% hardcoded in Python.**

Here's exactly where it lives:

| What | Where | How |
|------|-------|-----|
| Valid conversion paths (effect_type → target_scale) | `crci/extraction/p2_harmonization/conversion_router.py` lines 37-67 | `_VALID_CONVERSIONS` dict — 8 effect types × their valid targets |
| Target scale selection | `conversion_router.py` lines 175-195 | `_determine_target_scale()` — if-elif chain |
| Gate checks (CG1-CG4) | `conversion_router.py` lines 202-281 | `route_conversion()` — 4 gate checks |
| Actual math (OR→d, HR→log, r→d, etc.) | `conversion_executor.py` (881 lines) | 15 conversion functions with exact formulas |
| SE derivation cascade | `se_derivation_cascade.py` (336 lines) | `derive_se()` — CI→SE, p→SE, SD→SE |
| Scale harmonization (legacy path) | `scale_harmonizer.py` (549 lines) | OR→SMD, HR→logOR, r→d conversions |
| SD standardization | `sd_standardization.py` (283 lines) | Borrows SD from `sd_anchors_v1` (but that table doesn't exist either) |
| Load_evidence inline harmonization | `load_evidence_into_db.py` lines 910-924 | Simple string matching for harmonized_scale |

The `harmonization_rules_v1` table:
- Has an ORM model in `tables.py:162`
- Has a seed_loader entry for `harmonization_rules.csv` (file doesn't exist)
- Is listed in `report_status.py` and `setup_database.py`
- **Is NEVER queried by any pipeline code, any extraction stage, or any algorithm chain**

**Bottom line:** The conversion rules ARE the harmonization rules, just expressed as Python code rather than a database table. This is fine for now — the code works. A table-driven approach would be a future refactor for auditability.

---

## 4. WHAT YOU NEED TO FILL TO EXTRACT PAPERS

### The Extraction Workflow (System 2) — CONFIRMED WORKING

You have 5 papers extracted. The workflow is:

```
1. Create folder: data/manual_uploads/structured/<doi-slug>/
2. Fill CSV templates (using data/templates/*.csv as headers)
3. Create meta.json in data/manual_uploads/pdfs/<doi-slug>.meta.json
4. Run: python scripts/load_evidence_into_db.py [--verbose]
5. Verify: python scripts/report_status.py --evidence
```

### The 12 CSV Templates — Which Actually Matter

| # | Template | → DB Table | Algorithm Consumer | PRIORITY |
|---|----------|-----------|-------------------|----------|
| 1 | **edge_evidence_template.csv** | `edge_evidence_v1` | Chain B (10 cols) → IVW → `edges_v1` → Chain A | **MUST FILL** — sole evidence bridge |
| 2 | **population_norms_template.csv** | `population_norms_v1` | SD borrowing (IVW step), P7 prior_compiler | **SHOULD FILL** — enables mean_diff→d conversion |
| 3 | **context_priors_template.csv** | `node_priors_v1` | Chain C prior_loader | **SHOULD FILL** — Bayesian priors |
| 4 | **temporal_evidence_template.csv** | `temporal_evidence_v1` | P7 temporal_compiler (→ Chain E planned) | NICE TO HAVE — trajectories |
| 5 | **instrument_evidence_template.csv** | `instrument_evidence_v1` | P7 psychometric_compiler | NICE TO HAVE — reliability data |
| 6 | correlation_template.csv | `biomarker_correlations_v1` | Not consumed yet | LOW — future Chain C enhancement |
| 7 | dose_evidence_template.csv | `dose_evidence_v1` | P7 dose_response_compiler (reads table, produces in-memory) | LOW — future Chain D enhancement |
| 8 | subgroup_evidence_template.csv | `subgroup_evidence_v1` | P7 modifier_compiler (reads table, produces in-memory) | LOW — future |
| 9-12 | study_cohort_profile, profile_data_stream, stream_timepoint, ontology_link | respective tables | Not consumed by any chain | DEEP MODE ONLY |

### The 28-Column Edge Evidence Template — Column Status

Every column in the template IS wired into `load_evidence_into_db.py` **EXCEPT**:

| Column | Template? | Inserted to DB? | Read by Chain B? | Gap? |
|--------|-----------|-----------------|-----------------|------|
| `doi` | YES | Remapped → `study_id` | YES (as study_id) | ✅ OK |
| `n_treatment` | YES | **NO** | NO | ⚠️ Minor — column exists in DB but INSERT skips it |
| `n_control` | YES | **NO** | NO | ⚠️ Minor — column exists in DB but INSERT skips it |

**All other 25 template columns → INSERT → DB correctly.**

The 18 auto-generated columns (ler_id, edge_param_id, harmonized_beta, etc.) are computed by `load_evidence_into_db.py` — you don't fill these.

### What Chain B Actually Reads (the 10-column bottleneck)

```sql
SELECT study_id, edge_relation_id, harmonized_beta, harmonized_se,
       study_design, pub_year, N_effect, identification_status,
       quality_rating, cancer_validation_status
FROM edge_evidence_v1 WHERE active = 1
```

Of these 10:
- `study_id` — auto-generated from DOI
- `harmonized_beta` / `harmonized_se` — auto-computed from your reported values
- `identification_status` — auto-assigned ("plausible" for manual extractions)
- `quality_rating` — derived from rob_overall or defaults to "moderate"
- **You directly control: `edge_relation_id`, `study_design`, `pub_year`, `N_effect`, `cancer_validation_status`**

**Current data quality issue:** `pub_year` is only 44% populated (8/18 rows). This is because the Northey 2018 paper (5 rows) was extracted with the older 12-column template that didn't have pub_year.

---

## 5. CRITICAL ASSESSMENT: WHAT'S ACTUALLY GOING ON

### The Good
1. **The pipeline works end-to-end.** `load_evidence_into_db.py` correctly: loads CSVs, registers studies, auto-generates IDs, harmonizes scales, compiles IVW edges.
2. **The algorithm chains work.** `run_full_model.py` runs A→B→C→D→E→F→session→presentation. Chain D gracefully falls back when tables are empty.
3. **The 28-column template is well-designed.** It captures everything needed for the extraction→DB→algorithm path.
4. **The 12 template types cover the right evidence families.** Core (3) + Conditional (3) + Extended (6) is a sensible hierarchy.

### The Concerning
1. **Chain B only reads 10 of 107 columns.** The rich extraction data (treatment_phase, cancer_type, instrument_id, covariates, etc.) is stored but never used by the algorithm. This means the model treats all evidence equally regardless of cancer type, treatment phase, etc.
2. **No scope matching in the algorithm.** The P2 scope_matching module exists in the extraction pipeline but its output (`scope_weights_json`) is never consumed by Chain B or the IVW compiler.
3. **No SE calibration in the algorithm.** The 7-layer SE inflation exists in code but `se_eff` column is empty for all 18 rows. The IVW compiler uses `harmonized_se` directly.
4. **Chain D has 2 empty critical tables.** `contraindication_rules_v1` (0 rows) and `intervention_kernels_v1` (0 rows) — Chain D creates mock rankings instead of real ones.
5. **P7 compilers read from DB but write nowhere.** They produce in-memory objects that would feed the chains but the wiring doesn't persist results.

### The Not-a-Problem (despite looking scary)
1. **61 empty tables** — These are correctly designed schema for future phases. The system works without them because every chain has fallback logic.
2. **harmonization_rules_v1 is empty** — Rules are in Python code. Works fine.
3. **47 tables with zero code references** — Aspirational schema. No harm.
4. **sd_anchors_v1 doesn't exist** — The SD standardization code references it but `load_evidence_into_db.py` borrows SD from `population_norms_v1` instead. Works.

---

## 6. PRIORITIZED ACTION PLAN

### PHASE 0: IMMEDIATE (do this now, then start extracting)

#### 0A. Fix n_treatment/n_control INSERT gap (15 min)
The template has these columns, the DB has them, but `load_evidence_into_db.py` doesn't INSERT them. Quick fix: add them to the INSERT statement.

**Why now:** You're already filling these in your CSVs (Campbell 2017 has n_treatment=10, n_control=9). They should be in the DB.

#### 0B. Backfill pub_year on Northey 2018 rows (5 min)
```sql
UPDATE edge_evidence_v1 SET pub_year = 2018 WHERE study_id = 'STUDY_NORTHEY_2018';
```

**Why now:** Chain B reads pub_year. 44% population rate is suboptimal.

#### 0C. Verify you can run the full pipeline (10 min)
```bash
python scripts/load_evidence_into_db.py --verbose
python scripts/run_full_model.py --patient-id PAT_001 --cancer-type breast --treatment-phase active_chemo
```

**Why now:** Confirms everything works before you invest extraction time.

### THEN: START EXTRACTING PAPERS
You have everything you need. The 28-column edge_evidence_template + 4 auxiliary templates (population_norms, context_priors, temporal, instrument) are correctly wired. Extract papers using the existing workflow in `extraction_ref/01_PROCEDURE.md`.

**Per paper, fill:**
1. `edge_evidence_template.csv` (ALWAYS — 28 columns)
2. `population_norms_template.csv` (if baseline stats available)
3. `context_priors_template.csv` (if you can compute z-scores)
4. `temporal_evidence_template.csv` (if ≥2 timepoints)
5. `instrument_evidence_template.csv` (if psychometric data)

Then run `python scripts/load_evidence_into_db.py --verbose`.

---

### PHASE 1: BACKGROUND IMPROVEMENTS (do while extracting)

#### 1A. Make Chain B use more columns (2 hrs)
Chain B currently ignores cancer_type, treatment_phase, and scope_weights. Adding these to the SELECT + evidence weighting would make the model cancer-type-aware.

#### 1B. Wire se_eff into IVW compiler (1 hr)  
The IVW compiler uses `harmonized_se` but should use `calibrated_se_eff` (7-layer inflated SE) for honest uncertainty. Requires: (a) `load_evidence_into_db.py` to compute se_eff during insert, (b) IVW compiler to prefer se_eff over harmonized_se.

#### 1C. Seed contraindication_rules_v1 (30 min)
Chain D reads this table. Currently falls back to "no contraindications." Seeding with basic rules (e.g., high-intensity exercise contraindicated during active chemo with low platelets) would make Chain D's safety checker functional.

#### 1D. Seed intervention_kernels_v1 (1 hr)
Chain D reads this table. Currently produces mock rankings. Seeding with the 8 actions from action_catalog_v1 × their effect magnitudes would enable real Monte Carlo simulation.

### PHASE 2: ACCURACY REFINEMENTS (after 10+ papers extracted)

#### 2A. Implement scope matching in IVW (2 hrs)
Use scope_weights_json to weight evidence by relevance to the patient's cancer_type/treatment_phase.

#### 2B. Wire P7 compiler outputs into chains (3 hrs)
Currently P7 compilers (temporal, psychometric, dose, modifier) produce in-memory objects that vanish. Persisting them or passing them directly to the chains would enrich the model.

#### 2C. Activate the full extraction pipeline P0→P7 (4 hrs)
Currently extraction uses `load_evidence_into_db.py` (a standalone script). The full pipeline in `crci/extraction/pipeline.py` (P0→P7) is implemented but not used for manual imports. Activating it would add automated harmonization, heterogeneity detection, publication bias checks, and sufficiency gates.

---

## 7. EXTRACTION REFERENCE DOCS — ALIGNMENT CHECK

| Document | Purpose | Aligned with Reality? |
|----------|---------|----------------------|
| `extraction_ref/01_PROCEDURE.md` | 10-step extraction procedure | ✅ YES — steps match the template→load workflow |
| `extraction_ref/02_CHATBOX_CONTEXT.md` | AI copilot context | ✅ YES — correct file references |
| `extraction_ref/03_SE_DERIVATION.md` | SE derivation formulas | ✅ YES — matches conversion_executor.py |
| `extraction_ref/04_CONTROLLED_VOCAB.md` | Enums and IDs | ✅ YES — matches enums.py |
| `extraction_ref/06_CSV_TEMPLATES.md` | CSV column specs | ⚠️ MOSTLY — documents 28-col template correctly but some column descriptions may reference planned features |
| `extraction_ref/07_CSV_TO_DB_MAP.md` | CSV→DB column mapping | ⚠️ CHECK — may not reflect n_treatment/n_control gap |
| `extraction_ref/11_QUALITY_CHECKLIST.md` | Per-paper QA | ✅ YES — checklist is valid |
| `extraction_ref/12_TABLE_FILL_MASTER.md` | Which tables to fill when | ⚠️ CHECK — may reference tables that aren't on the critical path |
| `docs/BOX_TO_IMPLEMENTATION_MAPPING_v2.md` | Architecture → code map | ✅ Comprehensive and accurate for System 1-3 |

---

## 8. OUTPUT TRACE: What the System Actually Produces

When you run `python scripts/run_full_model.py`:

```
Chain A → FrozenGraph (63 nodes, ≤143 edges with weights from edges_v1)
Chain B → EvidenceResult (per-edge evidence weights from edge_evidence_v1) 
Chain C → PosteriorResult (per-node posterior distributions from node_priors_v1)
Chain D → RankingResult (interventions ranked by expected cognitive benefit)
         ⤷ needs action_catalog_v1 (8 rows ✅), dose_bridges_v1 (10 rows ✅)
         ⤷ needs intervention_kernels_v1 (0 rows ❌ → mock ranking)
         ⤷ needs contraindication_rules_v1 (0 rows ❌ → no safety filtering)
Chain E → TemporalResult (projected cognitive trajectories over time)
Chain F → CompositeResult (composite scores, analytics, top-N recommendations)
Runtime → RecommendationReport (formatted for terminal or clinical display)
```

**What's missing from full functionality:**
1. `intervention_kernels_v1` (0 rows) → Chain D uses mock ranking → **recommendations are placeholder**
2. `contraindication_rules_v1` (0 rows) → no safety filtering → **all interventions marked safe**
3. Chain B scope weighting not active → model treats breast cancer evidence same as prostate → **recommendations not cancer-specific**

**What works correctly despite gaps:**
- Evidence compilation (IVW pooling) ✅
- Bayesian posterior updates ✅  
- Graph structure and edge weights ✅
- Temporal trajectory projection ✅
- Report generation ✅

---

## 9. DECISION MATRIX: What to Do Right Now

| Action | Time | Impact | Blocks Extraction? | Recommendation |
|--------|------|--------|-------------------|----------------|
| Fix n_treatment/n_control INSERT | 15 min | Low | NO | **DO NOW** — quick win |
| Backfill pub_year | 5 min | Low | NO | **DO NOW** — data quality |
| Test full pipeline run | 10 min | High | YES (validates everything) | **DO NOW** — confidence check |
| Start extracting papers | Ongoing | **HIGHEST** | N/A | **START NOW** after above 3 |
| Seed intervention_kernels_v1 | 1 hr | Med | NO | Do between papers |
| Seed contraindication_rules_v1 | 30 min | Med | NO | Do between papers |
| Expand Chain B to use more cols | 2 hrs | High | NO | Do after 10+ papers |
| Wire se_eff | 1 hr | Med | NO | Do after 10+ papers |

**TL;DR: Do the 30-minute fixes now, then start extracting. Everything else can happen in parallel.**
