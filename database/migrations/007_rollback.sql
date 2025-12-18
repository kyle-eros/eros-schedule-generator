-- ============================================================================
-- Rollback Script for Migration 007: Schedule Generator Enhancements
-- ============================================================================
-- Purpose: Undo the changes made by 007_schedule_generator_enhancements.sql
-- Created: 2025-12-15
--
-- CAUTION: This rollback has limitations due to SQLite constraints:
--   - SQLite does NOT support DROP COLUMN
--   - The new columns (algorithm_params, agent_execution_log, quality_validation_score,
--     freshness_score) will REMAIN but can be ignored
--   - If full column removal is required, see manual steps at bottom
--
-- This script will:
--   1. Drop the freshness decay trigger
--   2. Drop the schedule_ready_creators view
--   3. Drop all queue-related indexes
--   4. Drop the schedule_generation_queue table
--   5. Remove the migration record
--
-- ============================================================================

-- ============================================================================
-- SECTION 1: DROP TRIGGER
-- ============================================================================
DROP TRIGGER IF EXISTS trg_cb_freshness_decay_on_use;

-- ============================================================================
-- SECTION 2: DROP VIEW
-- ============================================================================
DROP VIEW IF EXISTS v_schedule_ready_creators;

-- ============================================================================
-- SECTION 3: DROP INDEXES
-- ============================================================================
-- Caption bank index for freshness queries
DROP INDEX IF EXISTS idx_cb_freshness_performance;

-- Schedule generation queue indexes
DROP INDEX IF EXISTS idx_sgq_unique_active;
DROP INDEX IF EXISTS idx_sgq_completed_at;
DROP INDEX IF EXISTS idx_sgq_creator;
DROP INDEX IF EXISTS idx_sgq_status_priority;

-- ============================================================================
-- SECTION 4: DROP TABLE
-- ============================================================================
DROP TABLE IF EXISTS schedule_generation_queue;

-- ============================================================================
-- SECTION 5: REMOVE MIGRATION RECORD
-- ============================================================================
DELETE FROM schema_migrations WHERE version = '007';

-- ============================================================================
-- VERIFICATION
-- ============================================================================
-- After running this rollback, verify:
--
-- 1. Trigger removed:
--    SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_cb_freshness_decay_on_use';
--    (Should return nothing)
--
-- 2. View removed:
--    SELECT name FROM sqlite_master WHERE type='view' AND name='v_schedule_ready_creators';
--    (Should return nothing)
--
-- 3. Table removed:
--    SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_generation_queue';
--    (Should return nothing)
--
-- 4. Migration record removed:
--    SELECT * FROM schema_migrations WHERE version = '007';
--    (Should return nothing)
--
-- ============================================================================
-- MANUAL COLUMN REMOVAL (IF REQUIRED)
-- ============================================================================
-- SQLite does not support DROP COLUMN directly. If you must remove the new
-- columns from schedule_templates and caption_bank, follow these steps:
--
-- For schedule_templates:
-- -------------------------
-- 1. CREATE TABLE schedule_templates_new AS
--    SELECT template_id, creator_id, week_start, week_end, generated_at,
--           generated_by, algorithm_version, total_items, total_ppvs, total_bumps,
--           projected_earnings, status, scheduler_id, actual_earnings,
--           completion_rate, notes
--    FROM schedule_templates;
--
-- 2. DROP TABLE schedule_templates;
--
-- 3. ALTER TABLE schedule_templates_new RENAME TO schedule_templates;
--
-- 4. Recreate indexes:
--    CREATE INDEX idx_template_creator ON schedule_templates(creator_id);
--    CREATE INDEX idx_template_week ON schedule_templates(week_start);
--    CREATE INDEX idx_template_status ON schedule_templates(status);
--
-- For caption_bank (freshness_score column):
-- ------------------------------------------
-- Similar process - create new table without freshness_score, copy data,
-- drop old table, rename new table, recreate indexes.
--
-- WARNING: Manual column removal is destructive and should be done with
-- extreme caution. Always backup the database first!
--
-- ============================================================================
-- END OF ROLLBACK
-- ============================================================================
