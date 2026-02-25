# Table Fill Order

**Purpose:** Documents which database tables are populated at each stage of the
pipeline, so you can verify a table is ready before writing code that reads it.

**Cross-referenced by:** `CLAUDE.md` step 1g, `FILE_CONTEXT_MANIFEST.md`

---

## Stage 0 — Before Any Extraction Run (Seeds / Class A)

These are populated once by the seed loader (`scripts/setup_database.py --seed`)
and updated by manual human curation. They are INPUTS to extraction, not outputs.

| Table | Source File | How to Populate |
|-------|------------|-----------------|
| `nodes_v1` | `crci/database/seeds/nodes.csv` | `python scripts/setup_database.py --seed` |
| `edges_v1` | `registries/EDGE_REGISTRY.csv` → `crci/database/seeds/edge_relations.csv` | Same seed script |
| `instruments_v1` | `crci/database/seeds/instruments.csv` | Same seed script |
| `measures_v1` | `crci/database/seeds/measures.csv` | Same seed script |
| `pathways_v1` | `crci/database/seeds/pathways.csv` | Same seed script |

**⚠ After editing any registry CSV**, regenerate seeds:
```bash
python scripts/generate_derived_seeds.py
python scripts/setup_database.py --seed
```

---

## Stage 1 — EX-P0 Triage (runs first per paper)

Populated by `crci/extraction/p0_triage/runner.py` (⚠ not yet implemented).

| Table | Written By | Notes |
|-------|-----------|-------|
| `extraction_runs` | `pipeline.py` | One row per run; idempotency check |
| `study_registry_v1` | `p0_triage/pdf_ingestion.py` | Paper metadata, file paths, parse quality |
| `paper_map_v1` | `p0_triage/pdf_ingestion.py` | Section spans, page ranges |
| `acquisition_queue_v1` | `p0_triage/relevance_screening.py` | Retrieval status updates |

---

## Stage 2 — EX-P1 Multi-Agent Extraction

Populated by 9 specialist agents in `crci/extraction/p1_extraction/`.  
(⚠ runner.py not yet implemented)

| Table | Written By | Notes |
|-------|-----------|-------|
| `study_annotations_v1` | All 9 agents (AG01–AG09) | Primary extraction output |
| `raw_extraction_log` | `p1_extraction/runner.py` | Per-field extraction audit |

---

## Stage 3 — EX-TB Trust Boundary

Populated by `crci/extraction/tb_trust_boundary/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `edge_evidence_v1` Layer 1 cols | `tb_trust_boundary/runner.py` | Writes `tb_parse_status`, `beta_validated`, `se_validated`, `inflation_factor` etc. |
| `review_tasks_v1` | `tb_trust_boundary/runner.py` | ATB rejections, AMBIGUOUS flags |

---

## Stage 4 — EX-P2 Harmonization

Populated by `crci/extraction/p2_harmonization/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `edge_evidence_v1` Layer 2 cols | `p2_harmonization/runner.py` | Writes `beta_sd_sd`, `se_sd_sd`, `conversion_rule_id`, `w_scope` etc. |
| `harmonization_log_v1` | `p2_harmonization/runner.py` | Conversion decisions audit |

---

## Stage 5 — EX-P3 Seven-Layer Calibration

Populated by `crci/extraction/p3_heterogeneity/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `edge_evidence_v1` Layer 3 cols | `p3_heterogeneity/runner.py` | Writes `SE_eff`, `m_design`, `m_GRADE`, `tau_sq`, `w_fresh` etc. |
| `calibration_log_v1` | `p3_heterogeneity/runner.py` | Per-layer multiplier audit |

---

## Stage 6 — EX-P4 Aggregation

Populated by `crci/extraction/p4_aggregation/` and `p4b_publication_bias/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `edge_evidence_v1` Layer 4 cols | `p4_aggregation/runner.py` | Writes `pooling_status`, `dcr_decision`, `pooled_edge_contribution` |
| `pooled_estimates_v1` | `p4_aggregation/meta_analyzer.py` | IVW-pooled β̂ per edge |
| `publication_bias_log_v1` | `p4b_publication_bias/runner.py` | Egger test, trim-fill results |

---

## Stage 7 — EX-P5 Sufficiency Gate

Populated by `crci/extraction/p5_sufficiency/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `sufficiency_log_v1` | `p5_sufficiency/runner.py` | Per-edge PASS/FAIL/INSUFFICIENT |
| `edge_deployment_queue_v1` | `p5_sufficiency/runner.py` | Edges cleared for deployment |

---

## Stage 8 — EX-P6 Deployment

Populated by `crci/extraction/p6_deployment/`.

| Table | Written By | Notes |
|-------|-----------|-------|
| `deployed_parameters_v1` | `p6_deployment/runner.py` | Runtime-readable parameters |
| `deployment_log_v1` | `p6_deployment/runner.py` | Deployment audit trail |
| `prior_matrices_v1` | `p6_deployment/prior_writer.py` | Context-matched Bayesian priors |

---

## Manual Upload Path (Bypasses P0–P6)

When using the manual CSV upload system, data lands in `edge_evidence_v1`
Layer 0 columns only. Layers 1–5 are left NULL and processed when the pipeline
is eventually run against that paper.

```
data/manual_uploads/structured/[doi-slug]/*.csv
  → python scripts/run_manual_import.py --type csv
  → crci/retrieval/manual_upload_watcher.py
  → edge_evidence_v1 (Layer 0 only)
  → trust boundary queue (future)
```

---

## Summary: Dependency Order

```
Stage 0 (seeds) → Stage 1 (P0) → Stage 2 (P1) → Stage 3 (TB)
  → Stage 4 (P2) → Stage 5 (P3) → Stage 6 (P4+P4B)
  → Stage 7 (P5) → Stage 8 (P6)
```

A table from Stage N cannot be populated until all Stage < N tables exist
and contain at least one row for the paper being processed.
