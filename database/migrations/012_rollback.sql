-- ============================================================================
-- Rollback Script for Migration 012: Volume Learning Infrastructure
-- ============================================================================
--
-- Purpose:
--   Reverses all changes made by migration 012_volume_learning.sql
--
-- Reversals:
--   1. Drop v_prediction_accuracy view
--   2. Drop v_caption_pool_summary view
--   3. Drop volume_predictions table (and indexes)
--   4. Drop day_of_week_performance table (and indexes)
--   5. Drop volume_adjustment_outcomes table (and indexes)
--   6. Remove added columns from volume_calculation_log
--
-- WARNING:
--   - This will DELETE all data in the learning tables
--   - Column removal in SQLite requires table rebuild (see Section 6)
--   - Back up database before running: cp eros_sd_main.db eros_sd_main.db.backup
--
-- Author: EROS System
-- Date: 2025-12-16
-- Version: 1.0.0
-- ============================================================================

-- ============================================================================
-- PRE-ROLLBACK: Backup data if needed
-- ============================================================================
-- Run these queries BEFORE rollback to preserve any learning data:
--
-- -- Export volume_adjustment_outcomes
-- .headers on
-- .mode csv
-- .output volume_adjustment_outcomes_backup.csv
-- SELECT * FROM volume_adjustment_outcomes;
-- .output stdout
--
-- -- Export day_of_week_performance
-- .output day_of_week_performance_backup.csv
-- SELECT * FROM day_of_week_performance;
-- .output stdout
--
-- -- Export volume_predictions
-- .output volume_predictions_backup.csv
-- SELECT * FROM volume_predictions;
-- .output stdout
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: Drop Views
-- ============================================================================

DROP VIEW IF EXISTS v_prediction_accuracy;
DROP VIEW IF EXISTS v_caption_pool_summary;

-- ============================================================================
-- SECTION 2: Drop Indexes (explicit drop before table drop for clarity)
-- ============================================================================

-- volume_predictions indexes
DROP INDEX IF EXISTS idx_vp_unmeasured;
DROP INDEX IF EXISTS idx_vp_creator_accuracy;
DROP INDEX IF EXISTS idx_vp_schedule_template;
DROP INDEX IF EXISTS idx_vp_week_start;

-- day_of_week_performance indexes
DROP INDEX IF EXISTS idx_dow_creator;
DROP INDEX IF EXISTS idx_dow_calculated_at;

-- volume_adjustment_outcomes indexes
DROP INDEX IF EXISTS idx_vao_learning_pending;
DROP INDEX IF EXISTS idx_vao_creator_date;
DROP INDEX IF EXISTS idx_vao_log_id;

-- ============================================================================
-- SECTION 3: Drop Tables
-- ============================================================================

DROP TABLE IF EXISTS volume_predictions;
DROP TABLE IF EXISTS day_of_week_performance;
DROP TABLE IF EXISTS volume_adjustment_outcomes;

-- ============================================================================
-- SECTION 4: Remove columns from volume_calculation_log
-- ============================================================================
-- SQLite does not support DROP COLUMN directly (prior to SQLite 3.35.0).
-- For maximum compatibility, we rebuild the table without the new columns.
--
-- Note: If your SQLite version is 3.35.0+ (2021-03-12), you could use:
--   ALTER TABLE volume_calculation_log DROP COLUMN confidence_score;
--   ALTER TABLE volume_calculation_log DROP COLUMN caption_constrained;
--   ... etc.
--
-- The following uses the table rebuild approach for compatibility:

-- Step 4.1: Create temporary table with original schema (pre-migration 012)
CREATE TABLE volume_calculation_log_backup AS
SELECT
    log_id,
    creator_id,
    calculated_at,
    fan_count,
    page_type,
    saturation_score,
    opportunity_score,
    tier,
    revenue_per_day,
    engagement_per_day,
    retention_per_day,
    schedule_template_id,
    data_source,
    calculation_version,
    notes
FROM volume_calculation_log;

-- Step 4.2: Drop the modified table
DROP TABLE volume_calculation_log;

-- Step 4.3: Recreate original table structure (from migration 011)
CREATE TABLE volume_calculation_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    calculated_at TEXT DEFAULT (datetime('now')),

    -- Input metrics used for calculation
    fan_count INTEGER,
    page_type TEXT CHECK (page_type IN ('paid', 'free')),
    saturation_score REAL CHECK (saturation_score IS NULL OR (saturation_score >= 0 AND saturation_score <= 100)),
    opportunity_score REAL CHECK (opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 100)),

    -- Calculated outputs
    tier TEXT CHECK (tier IN ('low', 'mid', 'high', 'ultra')),
    revenue_per_day INTEGER CHECK (revenue_per_day IS NULL OR revenue_per_day >= 0),
    engagement_per_day INTEGER CHECK (engagement_per_day IS NULL OR engagement_per_day >= 0),
    retention_per_day INTEGER CHECK (retention_per_day IS NULL OR retention_per_day >= 0),

    -- Relationship to schedule that used this calculation
    schedule_template_id INTEGER,

    -- Metadata for debugging and analysis
    data_source TEXT DEFAULT 'dynamic' CHECK (data_source IN ('dynamic', 'cached_tracking', 'calculated_on_demand', 'fallback')),
    calculation_version TEXT DEFAULT '1.0',
    notes TEXT,

    -- Foreign keys
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);

-- Step 4.4: Restore data from backup
INSERT INTO volume_calculation_log (
    log_id,
    creator_id,
    calculated_at,
    fan_count,
    page_type,
    saturation_score,
    opportunity_score,
    tier,
    revenue_per_day,
    engagement_per_day,
    retention_per_day,
    schedule_template_id,
    data_source,
    calculation_version,
    notes
)
SELECT
    log_id,
    creator_id,
    calculated_at,
    fan_count,
    page_type,
    saturation_score,
    opportunity_score,
    tier,
    revenue_per_day,
    engagement_per_day,
    retention_per_day,
    schedule_template_id,
    data_source,
    calculation_version,
    notes
FROM volume_calculation_log_backup;

-- Step 4.5: Recreate original indexes
CREATE INDEX IF NOT EXISTS idx_vcl_creator_date
ON volume_calculation_log(creator_id, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_vcl_schedule
ON volume_calculation_log(schedule_template_id)
WHERE schedule_template_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vcl_tier
ON volume_calculation_log(tier, calculated_at DESC);

-- Step 4.6: Drop backup table
DROP TABLE volume_calculation_log_backup;

COMMIT;

-- ============================================================================
-- POST-ROLLBACK VERIFICATION
-- ============================================================================
-- Run these queries to verify rollback success:

-- 1. Verify tables are dropped
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN (
--     'volume_adjustment_outcomes',
--     'day_of_week_performance',
--     'volume_predictions'
-- );
-- -- Expected: Empty result

-- 2. Verify views are dropped
-- SELECT name FROM sqlite_master WHERE type='view' AND name IN (
--     'v_caption_pool_summary',
--     'v_prediction_accuracy'
-- );
-- -- Expected: Empty result

-- 3. Verify volume_calculation_log has original columns only
-- PRAGMA table_info(volume_calculation_log);
-- -- Expected: 15 columns (no confidence_score, caption_constrained, etc.)

-- 4. Verify indexes are recreated
-- SELECT name FROM sqlite_master
-- WHERE type='index' AND tbl_name='volume_calculation_log';
-- -- Expected: idx_vcl_creator_date, idx_vcl_schedule, idx_vcl_tier

-- 5. Verify data integrity
-- SELECT COUNT(*) as row_count FROM volume_calculation_log;
-- -- Expected: Same count as before rollback

-- ============================================================================
-- ALTERNATIVE: SQLite 3.35.0+ Column Drop Approach
-- ============================================================================
-- If running SQLite 3.35.0 or later, you can replace Section 4 with:
--
-- ALTER TABLE volume_calculation_log DROP COLUMN confidence_score;
-- ALTER TABLE volume_calculation_log DROP COLUMN caption_constrained;
-- ALTER TABLE volume_calculation_log DROP COLUMN message_count_analyzed;
-- ALTER TABLE volume_calculation_log DROP COLUMN multi_horizon_used;
-- ALTER TABLE volume_calculation_log DROP COLUMN dow_adjusted;
-- ALTER TABLE volume_calculation_log DROP COLUMN elasticity_capped;
--
-- Check version with: SELECT sqlite_version();
-- ============================================================================
