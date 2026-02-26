-- ═══════════════════════════════════════════════════════════════
-- CRCI Schema Migration: Study Identity & Uniqueness
-- Adds doi_normalized column and unique indexes to prevent duplicates
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- M1. Add doi_normalized column for dedup lookups
-- This stores the normalized DOI (lowercase, no prefix) for
-- fast uniqueness checks without runtime normalization.
-- ───────────────────────────────────────────────────────────────
ALTER TABLE study_registry_v1 ADD COLUMN doi_normalized TEXT;

-- ───────────────────────────────────────────────────────────────
-- M2. Create unique indexes for persistent identifiers
-- SQLite partial unique indexes enforce uniqueness only where
-- the column is NOT NULL and NOT empty string.
-- ───────────────────────────────────────────────────────────────

-- Unique on normalized DOI (most common identifier)
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_doi_normalized_unique
ON study_registry_v1(doi_normalized)
WHERE doi_normalized IS NOT NULL AND doi_normalized != '';

-- Unique on PMID (PubMed ID)
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_pmid_unique
ON study_registry_v1(pmid)
WHERE pmid IS NOT NULL AND pmid != '';

-- Unique on PMCID (PubMed Central ID)
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_pmcid_unique
ON study_registry_v1(pmcid)
WHERE pmcid IS NOT NULL AND pmcid != '';

-- ───────────────────────────────────────────────────────────────
-- M3. Backfill doi_normalized for existing rows
-- ───────────────────────────────────────────────────────────────
UPDATE study_registry_v1
SET doi_normalized = LOWER(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(doi, 'https://doi.org/', ''),
                'http://doi.org/', ''
            ),
            'https://dx.doi.org/', ''
        ),
        'http://dx.doi.org/', ''
    )
)
WHERE doi IS NOT NULL AND doi != '';

-- ───────────────────────────────────────────────────────────────
-- M4. Add id_source column to track how study_id was derived
-- Values: 'doi', 'pmid', 'pmcid', 'hash', 'legacy'
-- ───────────────────────────────────────────────────────────────
ALTER TABLE study_registry_v1 ADD COLUMN id_source TEXT DEFAULT 'legacy';

-- ───────────────────────────────────────────────────────────────
-- M5. Unique index on edge_evidence_v1 for idempotent writes
-- Key: (study_id, edge_relation_id, profile_id, span_hash)
-- Note: span_hash is derived from source text position
-- ───────────────────────────────────────────────────────────────
ALTER TABLE edge_evidence_v1 ADD COLUMN span_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_dedup
ON edge_evidence_v1(study_id, edge_relation_id, profile_id, span_hash)
WHERE span_hash IS NOT NULL;
