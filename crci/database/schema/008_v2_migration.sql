-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration: v2.0 Extraction Pipeline Enhancement
-- Adds columns and tables required by CRCI_Master_Spec_v2.0.md
-- and CRCI_Engineering_Appendix_v2.0.md
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. study_registry_v1 — 7 new columns
-- Engineering Appendix §A.2: study_subtype, included_study_ids_json,
-- included_k, pdf_path, canonical_text_path, file_type, parse_quality
-- Written by EX-INGEST (PDFProcessor) and EX-P0 (classifier)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE study_registry_v1
    ADD COLUMN IF NOT EXISTS study_subtype           TEXT,
    ADD COLUMN IF NOT EXISTS included_study_ids_json TEXT,
    ADD COLUMN IF NOT EXISTS included_k              INTEGER,
    ADD COLUMN IF NOT EXISTS pdf_path                TEXT,
    ADD COLUMN IF NOT EXISTS canonical_text_path     TEXT,
    ADD COLUMN IF NOT EXISTS file_type               TEXT,
    ADD COLUMN IF NOT EXISTS parse_quality           TEXT;

-- ───────────────────────────────────────────────────────────────
-- M2. edge_evidence_v1 — 3 new columns
-- Engineering Appendix §A.2: meta_source_flag, heterogeneity_json,
-- effect_size_type. (parent_meta_study_id already exists.)
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1
    ADD COLUMN IF NOT EXISTS meta_source_flag        TEXT,
    ADD COLUMN IF NOT EXISTS heterogeneity_json      TEXT,
    ADD COLUMN IF NOT EXISTS effect_size_type         TEXT;

-- ───────────────────────────────────────────────────────────────
-- M3. acquisition_queue_v1 — 7 new columns
-- Engineering Appendix §A.2: saturation_cycle_count,
-- saturation_flag, paywall_flagged, hop_source_study_id,
-- hop_depth, retrieval_status, abstract_relevance
-- ───────────────────────────────────────────────────────────────
ALTER TABLE acquisition_queue_v1
    ADD COLUMN IF NOT EXISTS saturation_cycle_count  INTEGER     DEFAULT 0,
    ADD COLUMN IF NOT EXISTS saturation_flag         BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS paywall_flagged         BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS hop_source_study_id     TEXT,
    ADD COLUMN IF NOT EXISTS hop_depth               INTEGER     DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retrieval_status        TEXT        DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS abstract_relevance      TEXT;

-- ───────────────────────────────────────────────────────────────
-- M4. study_annotations_v1 — full v2.0 schema (23 columns)
-- Engineering Appendix §A.3: complete annotation table
-- Replaces stub in ORM; adds v2.0 fields.
-- NOTE: Uses CREATE TABLE IF NOT EXISTS so safe to run on
-- databases that already have the table from ORM auto-create.
-- New columns are added via ALTER TABLE after CREATE.
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_annotations_v1 (
    annotation_id               TEXT        PRIMARY KEY,
    study_id                    TEXT        NOT NULL,
    ler_id                      TEXT,
    category                    TEXT        NOT NULL,
    consumer                    TEXT,
    target_entity_type          TEXT,
    target_entity_id            TEXT,
    content                     TEXT        NOT NULL,
    structured_data_json        TEXT,
    evidence_strength           TEXT,
    extraction_snippet          TEXT,
    maturity                    TEXT        DEFAULT 'raw',
    promoted_to                 TEXT,
    entered_by                  TEXT,
    entered_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version                     INTEGER     DEFAULT 1,
    active                      BOOLEAN     DEFAULT TRUE,
    span_id                     TEXT,
    section_label               TEXT,
    adjudication_status         TEXT        DEFAULT 'unreviewed',
    duplicate_of_annotation_id  TEXT,
    cross_agent_support_n       INTEGER     DEFAULT 1,
    extraction_mode             TEXT
);

-- Ensure v2.0-required columns exist even if table was created
-- by ORM with a subset of columns
ALTER TABLE study_annotations_v1
    ADD COLUMN IF NOT EXISTS consumer                TEXT,
    ADD COLUMN IF NOT EXISTS entered_at              TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS version                 INTEGER     DEFAULT 1,
    ADD COLUMN IF NOT EXISTS active                  BOOLEAN     DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS span_id                 TEXT,
    ADD COLUMN IF NOT EXISTS section_label           TEXT,
    ADD COLUMN IF NOT EXISTS adjudication_status     TEXT        DEFAULT 'unreviewed',
    ADD COLUMN IF NOT EXISTS duplicate_of_annotation_id TEXT,
    ADD COLUMN IF NOT EXISTS cross_agent_support_n   INTEGER     DEFAULT 1,
    ADD COLUMN IF NOT EXISTS extraction_mode         TEXT;

-- study_annotations_raw_v1 (pre-reconciliation staging)
CREATE TABLE IF NOT EXISTS study_annotations_raw_v1 (
    raw_annotation_id           TEXT        PRIMARY KEY,
    extraction_run_id           TEXT        NOT NULL,
    study_id                    TEXT        NOT NULL,
    entered_by                  TEXT        NOT NULL,
    entered_at                  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    category                    TEXT        NOT NULL,
    target_entity_type          TEXT,
    target_entity_id            TEXT,
    content                     TEXT        NOT NULL,
    structured_data_json        TEXT,
    evidence_strength           TEXT,
    extraction_snippet          TEXT,
    source_span_id              TEXT
);

-- ───────────────────────────────────────────────────────────────
-- M5. Indexes for study_annotations_v1
-- Engineering Appendix §A.3
-- ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sa_study_id
    ON study_annotations_v1(study_id);

CREATE INDEX IF NOT EXISTS idx_sa_category
    ON study_annotations_v1(category);

CREATE INDEX IF NOT EXISTS idx_sa_target
    ON study_annotations_v1(target_entity_type, target_entity_id);

CREATE INDEX IF NOT EXISTS idx_sa_maturity_active
    ON study_annotations_v1(maturity)
    WHERE active = TRUE;

-- Dedup constraint: no duplicate (study_id, category, content) triples
-- Uses md5 hash of content for efficient indexing
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_dedup
    ON study_annotations_v1(study_id, category, md5(content));

-- Additional useful indexes
CREATE INDEX IF NOT EXISTS idx_sa_adjudication
    ON study_annotations_v1(adjudication_status)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_acq_retrieval_status
    ON acquisition_queue_v1(retrieval_status);

CREATE INDEX IF NOT EXISTS idx_acq_abstract_relevance
    ON acquisition_queue_v1(abstract_relevance);

CREATE INDEX IF NOT EXISTS idx_sr_study_subtype
    ON study_registry_v1(study_subtype);

CREATE INDEX IF NOT EXISTS idx_ee_meta_source_flag
    ON edge_evidence_v1(meta_source_flag)
    WHERE meta_source_flag IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ee_effect_size_type
    ON edge_evidence_v1(effect_size_type);

-- ───────────────────────────────────────────────────────────────
-- M6. Views: pathway_evidence_audit_v1, evidence_landscape_v1
-- Engineering Appendix §A.2
-- ───────────────────────────────────────────────────────────────

-- Pathway evidence audit: per-pathway evidence summary
CREATE OR REPLACE VIEW pathway_evidence_audit_v1 AS
SELECT
    p.pathway_id,
    p.pathway_name,
    erd.edge_relation_id,
    erd.node_x_id,
    erd.node_y_id,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1)                    AS k_total,
    COUNT(DISTINCT ee.study_id)
        FILTER (WHERE ee.active = 1)                    AS n_studies,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1
                  AND ee.meta_source_flag IS NULL)       AS k_primary,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1
                  AND ee.meta_source_flag = 'POOLED_ESTIMATE') AS k_meta,
    AVG(ee.harmonized_beta)
        FILTER (WHERE ee.active = 1)                    AS mean_beta,
    AVG(ee.harmonized_se)
        FILTER (WHERE ee.active = 1)                    AS mean_se,
    CASE
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 10 THEN 'A'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 5  THEN 'B'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 2  THEN 'C'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 1  THEN 'D'
        ELSE 'F'
    END                                                 AS sufficiency_grade
FROM pathways_v1 p
JOIN edge_relations_definitions_v1 erd
    ON erd.pathway_id = p.pathway_id
LEFT JOIN edge_evidence_v1 ee
    ON ee.edge_relation_id = erd.edge_relation_id
GROUP BY p.pathway_id, p.pathway_name,
         erd.edge_relation_id, erd.node_x_id, erd.node_y_id;

-- Evidence landscape: per-edge evidence coverage summary
CREATE OR REPLACE VIEW evidence_landscape_v1 AS
SELECT
    erd.edge_relation_id,
    erd.node_x_id,
    erd.node_y_id,
    erd.relation_type,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1)                    AS k_total,
    COUNT(DISTINCT ee.study_id)
        FILTER (WHERE ee.active = 1)                    AS n_studies,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1
                  AND ee.meta_source_flag IS NULL)       AS k_primary,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1
                  AND ee.meta_source_flag = 'POOLED_ESTIMATE') AS k_meta,
    COUNT(DISTINCT ee.ler_id)
        FILTER (WHERE ee.active = 1
                  AND ee.meta_source_flag = 'FOREST_PLOT_ENTRY') AS k_forest_plot,
    COUNT(DISTINCT aq.queue_id)
        FILTER (WHERE aq.retrieval_status = 'HUMAN_NEEDED') AS n_human_needed,
    COUNT(DISTINCT aq.queue_id)
        FILTER (WHERE aq.retrieval_status = 'PENDING')  AS n_pending,
    CASE
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 10 THEN 'A'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 5  THEN 'B'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 2  THEN 'C'
        WHEN COUNT(DISTINCT ee.ler_id) FILTER (WHERE ee.active = 1) >= 1  THEN 'D'
        ELSE 'F'
    END                                                 AS sufficiency_grade
FROM edge_relations_definitions_v1 erd
LEFT JOIN edge_evidence_v1 ee
    ON ee.edge_relation_id = erd.edge_relation_id
LEFT JOIN acquisition_queue_v1 aq
    ON aq.target_edge_ids_json::text LIKE '%' || erd.edge_relation_id || '%'
GROUP BY erd.edge_relation_id, erd.node_x_id,
         erd.node_y_id, erd.relation_type;
