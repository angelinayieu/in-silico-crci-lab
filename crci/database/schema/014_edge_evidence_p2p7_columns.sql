-- ═══════════════════════════════════════════════════════════════
--  014 — Edge Evidence: P2–P7 Pipeline Columns
--  Source: EXTRACTION_TO_COMPUTATION_WIRING_AUDIT.md §3.1, Action 1
--
--  Adds columns required by P2 harmonization, P3 SE calibration,
--  P4 aggregation, and Chain B evidence_loader that were identified
--  as missing in the wiring audit.
--
--  Migration 013 already added: study_design, cancer_type,
--  treatment_phase, pub_year, cancer_validation_status,
--  n_treatment, n_control.
--
--  This migration adds the REMAINING columns needed for full
--  P2→P7 and Chain B pipeline operation.
--
--  NOTE: SQLite does not support ALTER TABLE ADD COLUMN IF NOT EXISTS.
--  Run via crci/database/run_migration.py which catches duplicate-column
--  errors, or use the sqlite3 CLI and ignore errors for existing columns.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. Outcome classification — Chain B τ² prior selection
--     Values: {subjective, semi_objective, biomarker}
--     Used by: Chain B evidence_compiler (Turner et al. τ² lookup)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1 ADD COLUMN outcome_type               TEXT    DEFAULT 'semi_objective';

-- ───────────────────────────────────────────────────────────────
-- M2. Scope matching — P3 Layer 2, Chain B Layer 7
--     JSON: {"cancer": 0.5, "phase": 0.5, "regimen": 0.5, ...}
--     Populated by: P2 scope_matching.py
--     Used by: P3 layer_2_scope_match, Chain B Layer 7 transportability
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1 ADD COLUMN scope_weights_json          TEXT    DEFAULT '{}';

-- ───────────────────────────────────────────────────────────────
-- M3. P3 SE calibration outputs — written by P3, read by Chain B
--     se_eff: Final 7-layer calibrated SE
--     se_layer_details_json: per-layer breakdown for provenance
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1 ADD COLUMN se_eff                      REAL;
ALTER TABLE edge_evidence_v1 ADD COLUMN se_layer_details_json       TEXT;

-- ───────────────────────────────────────────────────────────────
-- M4. v2.0 extension columns — already in ORM, ensure in DB
--     These were added to the ORM in Slice 8 but never migrated.
--     Some may already exist if DB was created from updated 002.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1 ADD COLUMN meta_source_flag            TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN heterogeneity_json          TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN effect_size_type            TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN se_derivation_level         TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN se_inflation_applied        REAL    DEFAULT 1.0;
ALTER TABLE edge_evidence_v1 ADD COLUMN se_quality_tag              TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN conversion_formula          TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN conversion_bias_risk        TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN shared_control_flag         INTEGER DEFAULT 0;
ALTER TABLE edge_evidence_v1 ADD COLUMN shared_control_study_id     TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN endpoint_vs_change          TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN comparison_arm_label        TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN verification_tier           TEXT    DEFAULT 'TIER_3';
ALTER TABLE edge_evidence_v1 ADD COLUMN verification_status         TEXT    DEFAULT 'UNVERIFIED';
ALTER TABLE edge_evidence_v1 ADD COLUMN escalation_rules_json       TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN escalation_se_inflation     REAL    DEFAULT 1.0;
ALTER TABLE edge_evidence_v1 ADD COLUMN parameter_family            TEXT;
ALTER TABLE edge_evidence_v1 ADD COLUMN freshness_w                 REAL;
ALTER TABLE edge_evidence_v1 ADD COLUMN freshness_superseded        INTEGER DEFAULT 0;
ALTER TABLE edge_evidence_v1 ADD COLUMN span_hash                   TEXT;
