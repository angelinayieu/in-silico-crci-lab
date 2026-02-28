-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration 013: Template ↔ DB Alignment
-- 
-- Adds columns to edge_evidence_v1 that were previously in the 
-- extraction CSV template but silently dropped or inserted via
-- SQLite loose INSERT. Now they are properly declared.
--
-- Also adds 4 missing columns to profile_data_streams_v1 that
-- exist in the DB schema spec but were absent from the CSV template.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. edge_evidence_v1 — study-level metadata columns
-- These were being written by load_evidence_into_db.py via INSERT
-- but never formally declared in the schema or ORM.
-- Also adds n_treatment / n_control which were silently dropped.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS study_design               TEXT;

ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS cancer_type                 TEXT;

ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS treatment_phase             TEXT;

ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS pub_year                    INTEGER;

ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS cancer_validation_status    TEXT;

-- Previously silently dropped from CSV — now stored properly
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS n_treatment                 INTEGER;

ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS n_control                   INTEGER;

-- ───────────────────────────────────────────────────────────────
-- M2. profile_data_streams_v1 — missing protocol columns
-- These exist in the DB schema spec (05_TABLE_SCHEMAS.md) and 
-- the CREATE TABLE in 002_class_b_evidence.sql, but were absent
-- from the CSV template.  Adding here for safety on old DBs.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE profile_data_streams_v1
    ADD COLUMN IF NOT EXISTS translation_status          TEXT;

ALTER TABLE profile_data_streams_v1
    ADD COLUMN IF NOT EXISTS schedule_pattern_spec       TEXT;

ALTER TABLE profile_data_streams_v1
    ADD COLUMN IF NOT EXISTS timestamp_source            TEXT;

ALTER TABLE profile_data_streams_v1
    ADD COLUMN IF NOT EXISTS days_collected_value        REAL;

-- ───────────────────────────────────────────────────────────────
-- M3. population_norms_v1 — age_range column
-- Used in extraction templates to capture age range metadata.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE population_norms_v1
    ADD COLUMN IF NOT EXISTS age_range                   TEXT;

-- ───────────────────────────────────────────────────────────────
-- M4. instrument_evidence_v1 — cancer_validated column
-- Captures whether the instrument has been validated in cancer
-- populations (yes / no / partial).
-- ───────────────────────────────────────────────────────────────
ALTER TABLE instrument_evidence_v1
    ADD COLUMN IF NOT EXISTS cancer_validated             TEXT;

-- ───────────────────────────────────────────────────────────────
-- M5. node_priors_v1 — extraction metadata columns
-- source_type: type of evidence backing the prior (meta-analysis, single study, expert)
-- n_contributing: number of studies contributing to the prior estimate
-- ───────────────────────────────────────────────────────────────
ALTER TABLE node_priors_v1
    ADD COLUMN IF NOT EXISTS source_type                 TEXT;

ALTER TABLE node_priors_v1
    ADD COLUMN IF NOT EXISTS n_contributing              INTEGER;

-- ───────────────────────────────────────────────────────────────
-- M6. biomarker_correlations_v1 — sample size and correlation type
-- N: sample size for the correlation estimate
-- partial_or_zero: whether correlation is partial, zero-order, or set to zero
-- ───────────────────────────────────────────────────────────────
ALTER TABLE biomarker_correlations_v1
    ADD COLUMN IF NOT EXISTS N                           INTEGER;

ALTER TABLE biomarker_correlations_v1
    ADD COLUMN IF NOT EXISTS partial_or_zero             TEXT;

-- ───────────────────────────────────────────────────────────────
-- M7. temporal_evidence_v1 — edge_relation_id
-- Extracted temporal data is edge-specific (ER_* IDs from edge_relations_definitions_v1),
-- not merely action-level. This supplements the existing action_id column.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE temporal_evidence_v1
    ADD COLUMN IF NOT EXISTS edge_relation_id            TEXT;
