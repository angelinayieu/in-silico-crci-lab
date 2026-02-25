-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration: Modules 2-5 (Verification, Missingness,
-- Shared Control, Freshness)
-- CONVERSION_VALIDITY_AND_HARDENING.md Modules 2, 3, 4, 5
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. edge_evidence_v1 — Verification escalation (Module 2)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS verification_tier       TEXT DEFAULT 'TIER_3',
    ADD COLUMN IF NOT EXISTS verification_status     TEXT DEFAULT 'UNVERIFIED',
    ADD COLUMN IF NOT EXISTS escalation_rules_json   TEXT,      -- JSON array of rule IDs
    ADD COLUMN IF NOT EXISTS escalation_se_inflation REAL DEFAULT 1.0;

-- ───────────────────────────────────────────────────────────────
-- M2. extraction_completeness_v1 — Missingness provenance (Module 3)
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extraction_completeness_v1 (
    completeness_id    TEXT    NOT NULL,
    study_id           TEXT    NOT NULL,
    component_id       TEXT    NOT NULL,
    component_label    TEXT,
    missingness_code   TEXT    NOT NULL,  -- PRESENT, ABSENT_IN_PAPER, etc.
    missingness_detail TEXT,
    agent_id           TEXT,
    corrective_action  TEXT,             -- search, reparse, rerun_agent, etc.
    created_at         TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    PRIMARY KEY (completeness_id)
);

CREATE INDEX IF NOT EXISTS idx_ec_study_id
    ON extraction_completeness_v1 (study_id);

CREATE INDEX IF NOT EXISTS idx_ec_missingness_code
    ON extraction_completeness_v1 (missingness_code)
    WHERE missingness_code != 'PRESENT';

CREATE INDEX IF NOT EXISTS idx_ec_component
    ON extraction_completeness_v1 (component_id, missingness_code);

-- ───────────────────────────────────────────────────────────────
-- M3. edge_evidence_v1 — Comparison arm label for SC-1 (Module 4.1)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS comparison_arm_label TEXT;

-- ───────────────────────────────────────────────────────────────
-- M4. study_registry_v1 — Multi-arm trial metadata (Module 4.1)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE study_registry_v1
    ADD COLUMN IF NOT EXISTS multi_arm      BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS n_arms         INTEGER,
    ADD COLUMN IF NOT EXISTS trial_registry_id TEXT;

-- ───────────────────────────────────────────────────────────────
-- M5. edge_evidence_v1 — Freshness provenance (Module 5)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS parameter_family       TEXT,
    ADD COLUMN IF NOT EXISTS freshness_w             REAL,
    ADD COLUMN IF NOT EXISTS freshness_superseded    BOOLEAN DEFAULT FALSE;

-- ───────────────────────────────────────────────────────────────
-- M6. Indexes for verification and freshness queries
-- ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ee_verification_status
    ON edge_evidence_v1 (verification_status)
    WHERE verification_status != 'UNVERIFIED';

CREATE INDEX IF NOT EXISTS idx_ee_parameter_family
    ON edge_evidence_v1 (parameter_family)
    WHERE parameter_family IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sr_trial_registry
    ON study_registry_v1 (trial_registry_id)
    WHERE trial_registry_id IS NOT NULL;
