-- ───────────────────────────────────────────────────────────────
-- 015_retrieval_enhanced.sql
-- Purpose: Extend acquisition_queue_v1 for multi-source retrieval
--          with cross-resolved identifiers and retrieval audit trail.
-- Run AFTER: 008_v2_migration.sql (which adds retrieval_status, etc.)
-- ───────────────────────────────────────────────────────────────

-- Cross-resolved identifiers (populated by id_resolver.resolve_doi)
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS pmcid               TEXT;
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS openalex_id          TEXT;

-- Best known OA PDF URL (from OpenAlex or Unpaywall resolution)
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS best_oa_url          TEXT;

-- JSON array of RetrievalAttemptRecord objects for full audit trail
-- e.g. [{"source":"europe_pmc","status":"failed","duration_ms":234}, ...]
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS retrieval_attempts_json TEXT;

-- Relative path to saved file (e.g. "data/manual_uploads/pdfs/10.1002_pon.4370.pdf")
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS file_path            TEXT;

-- Index for batch processing by retrieval_status
CREATE INDEX IF NOT EXISTS idx_aq_retrieval_status_enhanced
    ON acquisition_queue_v1(retrieval_status)
    WHERE retrieval_status IN (
        'PENDING', 'RESOLVING', 'RESOLVED', 'RETRIEVING',
        'RETRIEVED', 'PAYWALLED', 'RETRIEVAL_FAILED', 'VALIDATION_FAILED'
    );
