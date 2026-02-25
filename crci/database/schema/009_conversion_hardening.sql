-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration: Conversion Validity & SE Derivation Cascade
-- CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4 + Module 6
-- Adds columns for SE derivation tracking, conversion provenance,
-- shared-control handling, and endpoint/change classification.
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. edge_evidence_v1 — SE derivation cascade columns
-- CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4
-- Tracks which level of the 6-level SE cascade was used,
-- the inflation factor applied, and SE quality classification.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS se_derivation_level   TEXT,   -- L1, L2a, L2b, L2c, L3a, L3b, L4a, L4b, L5, L6
    ADD COLUMN IF NOT EXISTS se_inflation_applied   REAL,   -- inflation factor (1.00-1.50)
    ADD COLUMN IF NOT EXISTS se_quality_tag         TEXT;   -- DIRECT, DERIVED_EXACT, DERIVED_PVAL, etc.

-- ───────────────────────────────────────────────────────────────
-- M2. edge_evidence_v1 — Conversion provenance columns
-- CONVERSION_VALIDITY_AND_HARDENING.md Module 1 Rule R4
-- Every conversion logs: source_type, target_type, formula_used,
-- fields_present, fields_missing, se_inflation_applied,
-- conversion_bias_risk.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS conversion_formula     TEXT,   -- formula ID (M1-SMD-d, M1-LOG-OR, etc.)
    ADD COLUMN IF NOT EXISTS conversion_bias_risk   TEXT;   -- NONE, LOW, MODERATE, HIGH, VERY_HIGH, BLOCKED

-- ───────────────────────────────────────────────────────────────
-- M3. edge_evidence_v1 — Shared control & dependency columns
-- CONVERSION_VALIDITY_AND_HARDENING.md Module 4
-- SC-1: shared control group detection and handling
-- CL-1/CL-2: cohort lineage tracking
-- CS-1: endpoint vs change score classification
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS shared_control_flag        BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS shared_control_study_id    TEXT,
    ADD COLUMN IF NOT EXISTS endpoint_vs_change         TEXT;   -- ENDPOINT, CHANGE, UNCLEAR

-- ───────────────────────────────────────────────────────────────
-- M4. study_registry_v1 — Cohort lineage columns
-- CONVERSION_VALIDITY_AND_HARDENING.md Module 4.2
-- CL-1: Only ONE paper per lineage contributes to IVW pooling.
-- CL-2: Non-selected papers flagged as SUPPLEMENTARY.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE study_registry_v1
    ADD COLUMN IF NOT EXISTS cohort_lineage_id   TEXT,   -- FK to self-group
    ADD COLUMN IF NOT EXISTS lineage_role         TEXT;   -- PRIMARY, SUPPLEMENTARY, FOLLOW_UP

-- ───────────────────────────────────────────────────────────────
-- M5. Indexes for efficient cascade-level queries
-- ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ee_se_derivation_level
    ON edge_evidence_v1 (se_derivation_level)
    WHERE se_derivation_level IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ee_conversion_bias_risk
    ON edge_evidence_v1 (conversion_bias_risk)
    WHERE conversion_bias_risk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ee_shared_control
    ON edge_evidence_v1 (shared_control_study_id)
    WHERE shared_control_flag = TRUE;

CREATE INDEX IF NOT EXISTS idx_sr_cohort_lineage
    ON study_registry_v1 (cohort_lineage_id)
    WHERE cohort_lineage_id IS NOT NULL;
