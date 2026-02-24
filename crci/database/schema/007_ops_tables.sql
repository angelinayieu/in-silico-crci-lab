-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema: Operations Tables
-- Supporting tables for HITL review, policy snapshots, and
-- build provenance. Not part of the 64-table scientific spec.
-- ═══════════════════════════════════════════════════════════════

-- review_tasks: Simple HITL queue for human review
-- Written by: extraction pipeline (ATB rejection, P6 BLOCK, AMBIGUOUS)
-- Read by: human operator for adjudication
CREATE TABLE IF NOT EXISTS review_tasks (
    task_id         TEXT PRIMARY KEY,
    task_type       TEXT NOT NULL,        -- {atb_rejection, p6_block, ambiguous_parse, manual_review}
    source_stage    TEXT NOT NULL,        -- pipeline stage that generated this task
    source_entity_id TEXT NOT NULL,       -- ler_id, study_id, etc.
    source_table    TEXT NOT NULL,        -- which table the entity belongs to
    priority        INTEGER DEFAULT 1,    -- lower = higher priority
    status          TEXT NOT NULL DEFAULT 'pending',  -- {pending, in_progress, resolved, wontfix}
    assigned_to     TEXT,                 -- operator ID
    summary         TEXT NOT NULL,        -- human-readable description of what needs review
    context_json    JSONB DEFAULT '{}',   -- additional context (e.g., rejected values, ambiguity details)
    resolution      TEXT,                 -- what was decided
    resolution_json JSONB,               -- structured resolution data
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP,
    notes           TEXT
);

-- policy_snapshots: Config/policy version snapshot per extraction run
-- Written by: extraction/pipeline.py at run start
-- Read by: audit and reproducibility checks
CREATE TABLE IF NOT EXISTS policy_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,        -- extraction run or recommendation run
    snapshot_time   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    config_hash     TEXT NOT NULL,        -- hash of shared/config.py constants
    table_versions_json JSONB NOT NULL,   -- {table_name: max(version)} for all referenced tables
    code_commit_hash TEXT,                -- git commit hash
    python_version  TEXT,                 -- sys.version
    dependency_versions_json JSONB,       -- {package: version} for key dependencies
    notes           TEXT
);

-- build_manifests_v1: Compilation build provenance
-- Referenced by chain_validation_results_v1 and publication_bias_results_v1
CREATE TABLE IF NOT EXISTS build_manifests_v1 (
    build_id        TEXT PRIMARY KEY,
    build_label     TEXT NOT NULL,
    build_time      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    build_type      TEXT NOT NULL,        -- {evidence_compilation, validation_run, bias_assessment}
    input_tables_json JSONB NOT NULL,     -- tables read during build
    output_tables_json JSONB NOT NULL,    -- tables written during build
    config_snapshot_id TEXT,              -- FK to policy_snapshots
    code_commit_hash TEXT,
    status          TEXT NOT NULL DEFAULT 'ok',  -- {ok, failed, partial}
    summary_json    JSONB,               -- build summary statistics
    warnings_json   JSONB DEFAULT '[]',
    notes           TEXT,
    version         INTEGER DEFAULT 1
);

-- extraction_runs: Per-paper extraction run tracking
-- Written by: extraction/pipeline.py
-- Read by: audit, idempotency checks
CREATE TABLE IF NOT EXISTS extraction_runs (
    extraction_run_id TEXT PRIMARY KEY,
    study_id        TEXT,                 -- FK to study_registry_v1 (NULL until study registered)
    pdf_path        TEXT NOT NULL,
    pdf_hash        TEXT NOT NULL,        -- content hash for dedup
    started_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at        TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'running',  -- {running, success, partial, failed}
    extraction_mode TEXT,                 -- SHALLOW/STANDARD/DEEP
    model_id        TEXT,                 -- LLM model used
    total_tokens    INTEGER DEFAULT 0,
    total_cost_usd  REAL DEFAULT 0.0,
    policy_snapshot_id TEXT,              -- FK to policy_snapshots
    stages_completed_json JSONB DEFAULT '[]',  -- list of completed pipeline stages
    error_message   TEXT,
    notes           TEXT
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_review_tasks_status ON review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_review_tasks_type ON review_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_study ON extraction_runs(study_id);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_status ON extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_pdf_hash ON extraction_runs(pdf_hash);
