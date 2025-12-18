-- Migration 009: Add Missing Columns to caption_bank
-- Purpose: Add columns required by eros_sync.py and caption_import_pipeline.py
-- Created: 2025-12-15
-- Status: APPLIED (2025-12-15)
--
-- Fixes error: "table caption_bank has no column named classification_confidence"
--
-- Missing columns identified from insert statements in:
--   - /Users/kylemerriman/Projects/SIMPLE-onlyfans-archiver/eros_sync.py
--   - /Users/kylemerriman/Projects/SIMPLE-onlyfans-archiver/caption_import_pipeline.py
--   - /Users/kylemerriman/Projects/SIMPLE-onlyfans-archiver/exports/scraped_captions_export.csv

-- ============================================================================
-- PRE-REQUISITE: Ensure schema_migrations table exists
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================================
-- CHECK: Verify migration has not already been applied
-- ============================================================================
-- If this migration has already been applied, the INSERT will fail silently
-- due to the PRIMARY KEY constraint on version.

-- ============================================================================
-- ADD MISSING COLUMNS TO caption_bank
-- ============================================================================

-- classification_confidence: Confidence score for content type classification (0.0-1.0)
ALTER TABLE caption_bank ADD COLUMN classification_confidence REAL DEFAULT 0.5;

-- classification_method: Method used for classification (e.g., 'scraper_import', 'manual', 'ai')
ALTER TABLE caption_bank ADD COLUMN classification_method TEXT DEFAULT 'unknown';

-- first_used_date: Date when caption was first used
ALTER TABLE caption_bank ADD COLUMN first_used_date TEXT;

-- page_name: Creator's page name / username
ALTER TABLE caption_bank ADD COLUMN page_name TEXT;

-- is_universal: Whether caption can be used across all creators (1 = yes, 0 = no)
ALTER TABLE caption_bank ADD COLUMN is_universal INTEGER DEFAULT 0;

-- emoji_style: Emoji usage pattern (none, minimal, moderate, heavy)
ALTER TABLE caption_bank ADD COLUMN emoji_style TEXT DEFAULT 'none';

-- slang_level: Amount of slang/informal language (none, light, heavy)
ALTER TABLE caption_bank ADD COLUMN slang_level TEXT DEFAULT 'none';

-- source: Origin of the caption (e.g., 'scraped', 'manual', 'imported')
ALTER TABLE caption_bank ADD COLUMN source TEXT DEFAULT 'unknown';

-- imported_at: Timestamp when caption was imported
ALTER TABLE caption_bank ADD COLUMN imported_at TEXT;

-- created_by: System/user that created the caption
ALTER TABLE caption_bank ADD COLUMN created_by TEXT DEFAULT 'system';

-- created_at: Timestamp when record was created (standard audit column)
-- Note: SQLite doesn't allow non-constant defaults in ALTER TABLE, so we use NULL default
-- and update existing rows separately
ALTER TABLE caption_bank ADD COLUMN created_at TEXT;

-- notes: Optional notes/comments about the caption
ALTER TABLE caption_bank ADD COLUMN notes TEXT;

-- is_wall_eligible: Whether caption can be used for wall posts
ALTER TABLE caption_bank ADD COLUMN is_wall_eligible INTEGER DEFAULT 1;

-- wall_post_count: Number of times used in wall posts
ALTER TABLE caption_bank ADD COLUMN wall_post_count INTEGER DEFAULT 0;

-- avg_purchase_rate: Average purchase rate for PPV messages using this caption
ALTER TABLE caption_bank ADD COLUMN avg_purchase_rate REAL DEFAULT 0.0;

-- avg_view_rate: Average view rate for messages using this caption
ALTER TABLE caption_bank ADD COLUMN avg_view_rate REAL DEFAULT 0.0;

-- performance_tier: Performance tier classification (1-5, 5 being best)
ALTER TABLE caption_bank ADD COLUMN performance_tier INTEGER DEFAULT 3;

-- required_content_tags: JSON array of required content tags
ALTER TABLE caption_bank ADD COLUMN required_content_tags TEXT;

-- excluded_content_tags: JSON array of excluded content tags
ALTER TABLE caption_bank ADD COLUMN excluded_content_tags TEXT;

-- ============================================================================
-- BACKFILL DEFAULT VALUES FOR NON-CONSTANT COLUMNS
-- ============================================================================

-- Set created_at to current timestamp for existing rows
UPDATE caption_bank SET created_at = datetime('now') WHERE created_at IS NULL;

-- ============================================================================
-- CREATE INDEXES FOR NEW COLUMNS
-- ============================================================================

-- Index on page_name for creator-specific queries
CREATE INDEX IF NOT EXISTS idx_cb_page_name ON caption_bank(page_name);

-- Index on source for filtering by origin
CREATE INDEX IF NOT EXISTS idx_cb_source ON caption_bank(source);

-- Index on is_universal for universal caption queries
CREATE INDEX IF NOT EXISTS idx_cb_is_universal ON caption_bank(is_universal);

-- Index on classification_method for filtering by classification type
CREATE INDEX IF NOT EXISTS idx_cb_classification_method ON caption_bank(classification_method);

-- Index on created_by for auditing
CREATE INDEX IF NOT EXISTS idx_cb_created_by ON caption_bank(created_by);

-- Index on is_wall_eligible for wall post caption selection
CREATE INDEX IF NOT EXISTS idx_cb_wall_eligible ON caption_bank(is_wall_eligible) WHERE is_wall_eligible = 1;

-- ============================================================================
-- RECORD MIGRATION
-- ============================================================================

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('009', 'Add missing columns to caption_bank for eros_sync.py compatibility');

-- ============================================================================
-- VERIFICATION QUERIES (run these after migration to verify success)
-- ============================================================================
-- SELECT name FROM pragma_table_info('caption_bank') ORDER BY name;
-- SELECT * FROM schema_migrations WHERE version = '009';
