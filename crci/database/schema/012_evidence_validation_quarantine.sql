-- ═══════════════════════════════════════════════════════════════
--  012 — Evidence Validation Quarantine
--  Source: IMPLEMENTATION_SLICES.md Slice 0, Gap 2
--
--  Separate from edge_evidence_quarantine_v1 (009_qa_quarantine.sql)
--  which captures QA-gate rejections during LLM extraction.
--
--  This table captures rows that fail STRUCTURAL VALIDATION at the
--  evidence writer level: unknown study_design key, missing required
--  field, invalid edge_relation_id, etc.
--
--  Rows here are NEVER promoted to edge_evidence_v1 until manually
--  reviewed and re-submitted.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS evidence_validation_quarantine_v1 (
    quarantine_id       TEXT PRIMARY KEY,
    study_id            TEXT,
    edge_relation_id    TEXT,
    source_path         TEXT NOT NULL,        -- 'llm' | 'manual_csv' | 'bulk_loader'
    raw_payload_json    TEXT NOT NULL,         -- complete row as submitted (JSON)
    validation_errors   TEXT NOT NULL,         -- JSON array of error strings
    quarantine_reason   TEXT NOT NULL,         -- primary category: 'missing_study_design' | 'unknown_edge_id' | ...
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at         TEXT,                  -- NULL until manually fixed and re-submitted
    resolved_by         TEXT                   -- 'manual_resubmit' | 'auto_retry'
);

-- Index for quick lookup of unresolved quarantine rows
CREATE INDEX IF NOT EXISTS idx_evq_unresolved
    ON evidence_validation_quarantine_v1 (resolved_at)
    WHERE resolved_at IS NULL;

-- Index for study-level quarantine review
CREATE INDEX IF NOT EXISTS idx_evq_study
    ON evidence_validation_quarantine_v1 (study_id);
