-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration: QA Gate Quarantine Table
-- DEEP_AUDIT_FINDINGS.md Tier 2: Remove Poison Defaults
-- Records rejected by TB-QA gates (QA-1..QA-5) are stored here
-- for audit/debugging. Never pooled by P3/P4.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS edge_evidence_quarantine_v1 (
    quarantine_id         TEXT PRIMARY KEY,
    extraction_run_id     TEXT NOT NULL,
    paper_id              TEXT,
    study_id              TEXT,
    edge_relation_id      TEXT,

    -- Raw extracted values (pre-harmonization)
    effect_value          REAL,
    se                    REAL,
    ci_lower              REAL,
    ci_upper              REAL,
    p_value               REAL,
    n                     INTEGER,
    label_type            TEXT,
    original_text         TEXT,
    grouping_id           TEXT,

    -- Rejection metadata
    reject_gate           TEXT NOT NULL,     -- QA-1, QA-2, etc.
    reject_reason         TEXT NOT NULL,     -- NO_PRECISION_SOURCE, etc.
    reject_details        TEXT,              -- Human-readable context

    -- Audit
    quarantined_at        TEXT NOT NULL,
    version               INTEGER DEFAULT 1,
    active                INTEGER DEFAULT 1
);

-- Index for querying rejections by gate and reason
CREATE INDEX IF NOT EXISTS idx_quarantine_gate
    ON edge_evidence_quarantine_v1(reject_gate, reject_reason);

-- Index for querying by extraction run
CREATE INDEX IF NOT EXISTS idx_quarantine_run
    ON edge_evidence_quarantine_v1(extraction_run_id);

-- Index for querying by paper
CREATE INDEX IF NOT EXISTS idx_quarantine_paper
    ON edge_evidence_quarantine_v1(paper_id);
