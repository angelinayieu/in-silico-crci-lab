# Extraction Reference — Master Index

> **This folder is the single source of truth for all evidence extraction.**
> Every file the AI chatbox or human operator needs lives here.
> Always reference `extraction_ref/` — never scattered docs elsewhere.

---

## File Map

| # | File | Purpose |
|---|------|---------|
| **Guides** | | |
| 1 | [01_PROCEDURE.md](01_PROCEDURE.md) | Step-by-step extraction procedure (Steps 0–9) |
| 2 | [02_CHATBOX_CONTEXT.md](02_CHATBOX_CONTEXT.md) | Exact system prompt + pinned context for AI copilot |
| 3 | [03_SE_DERIVATION.md](03_SE_DERIVATION.md) | All SE/effect-size computation formulas |
| 4 | [04_CONTROLLED_VOCAB.md](04_CONTROLLED_VOCAB.md) | Every enum, ID format, naming convention |
| **Schemas** | | |
| 5 | [05_DB_SCHEMA.md](05_DB_SCHEMA.md) | Exact DB table columns (what the pipeline reads) |
| 6 | [06_CSV_TEMPLATES.md](06_CSV_TEMPLATES.md) | CSV template column specs (what you fill) |
| 7 | [07_CSV_TO_DB_MAP.md](07_CSV_TO_DB_MAP.md) | How CSV columns map to DB columns |
| **Lookups** | | |
| 8 | [08_NODE_IDS.md](08_NODE_IDS.md) | All 63 node IDs with labels and domains |
| 9 | [09_EDGE_IDS.md](09_EDGE_IDS.md) | All ~143 edge IDs with source→target |
| 10 | [10_INSTRUMENT_IDS.md](10_INSTRUMENT_IDS.md) | All 67 instrument IDs with names and scoring |
| **Diagrams** | | |
| 11 | [flows/extraction_pipeline.mmd](flows/extraction_pipeline.mmd) | End-to-end extraction flow |
| 12 | [flows/csv_to_db.mmd](flows/csv_to_db.mmd) | CSV → DB data flow |
| 13 | [flows/paper_decision_tree.mmd](flows/paper_decision_tree.mmd) | Paper classification decision tree |
| 14 | [flows/se_derivation.mmd](flows/se_derivation.mmd) | SE derivation decision tree |
| 15 | [flows/db_table_relationships.mmd](flows/db_table_relationships.mmd) | DB ER diagram (evidence tables) |
| 16 | [flows/seven_layer_calibration.mmd](flows/seven_layer_calibration.mmd) | 7-layer calibration pipeline |
| **History** | | |
| 17 | [EXTRACTION_LOG.md](EXTRACTION_LOG.md) | Cumulative extraction audit trail |
| **Quality** | | |
| 18 | [11_QUALITY_CHECKLIST.md](11_QUALITY_CHECKLIST.md) | Per-paper quality gate checklist |
| **Master Reference** | | |
| 19 | [12_TABLE_FILL_MASTER.md](12_TABLE_FILL_MASTER.md) | ALL 83 tables → fill mechanism, status, instructions, dependencies |
| **Retrieval** | | |
| 20 | [13_RETRIEVAL_SESSIONS.md](13_RETRIEVAL_SESSIONS.md) | AI chatbox prompts for systematic literature search (feeds Stage 0) |

---

## Quick Start

1. Open the paper PDF
2. Load `extraction_ref/02_CHATBOX_CONTEXT.md` as your system prompt
3. Follow `extraction_ref/01_PROCEDURE.md` steps 0–9
4. Look up IDs in `08_NODE_IDS.md`, `09_EDGE_IDS.md`, `10_INSTRUMENT_IDS.md`
5. If SE isn't reported, use `03_SE_DERIVATION.md`
6. Run `python scripts/load_evidence_into_db.py` to load

---

## DB Location

```
File:   crci_dev.db  (SQLite 3, project root)
Verify: python scripts/report_status.py --schema
```
