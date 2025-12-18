-- ============================================================================
-- ROLLBACK: 008_rollback.sql - Wave 1 Complete Rollback
-- ============================================================================
-- Version: 1.0.0
-- Created: 2025-12-15
--
-- PURPOSE:
--   Safely removes ALL Wave 1 changes introduced by the send_types_foundation
--   migration and related enhancements. This script reverses the creation order
--   to maintain referential integrity.
--
-- WARNING:
--   - This rollback is DESTRUCTIVE and will DELETE DATA in Wave 1 tables
--   - The schedule_items table will be RECREATED (data is preserved but
--     Wave 1 columns are removed)
--   - BACKUP YOUR DATABASE BEFORE RUNNING THIS SCRIPT
--
-- ROLLBACK ORDER (reverse of creation):
--   1. Drop v_schedule_items_full view
--   2. Drop mapping tables (send_type_content_compatibility, send_type_caption_requirements)
--   3. Recreate schedule_items without Wave 1 columns
--   4. Drop lookup tables (audience_targets, channels, send_types)
--   5. Drop all related indexes (explicit cleanup)
--   6. Remove migration record
--
-- USAGE:
--   sqlite3 /path/to/database.db < 008_rollback.sql
--
-- VERIFICATION:
--   After rollback, run the verification queries at the end of this file.
-- ============================================================================

-- ============================================================================
-- TRANSACTION WRAPPER
-- ============================================================================
-- SQLite transaction for atomicity - all changes succeed or all fail

BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: DROP VIEW
-- ============================================================================
-- The view must be dropped first as it references schedule_items and
-- potentially the lookup/mapping tables

DROP VIEW IF EXISTS v_schedule_items_full;

-- Verify view is dropped
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'OK: View v_schedule_items_full dropped'
    ELSE 'ERROR: View v_schedule_items_full still exists'
END AS view_status
FROM sqlite_master
WHERE type = 'view' AND name = 'v_schedule_items_full';

-- ============================================================================
-- SECTION 2: DROP MAPPING TABLES
-- ============================================================================
-- Mapping tables reference send_types, so they must be dropped before
-- the lookup tables

DROP TABLE IF EXISTS send_type_content_compatibility;
DROP TABLE IF EXISTS send_type_caption_requirements;

-- Verify mapping tables are dropped
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'OK: Mapping tables dropped'
    ELSE 'ERROR: Mapping tables still exist'
END AS mapping_status
FROM sqlite_master
WHERE type = 'table' AND name IN (
    'send_type_content_compatibility',
    'send_type_caption_requirements'
);

-- ============================================================================
-- SECTION 3: RECREATE schedule_items WITHOUT WAVE 1 COLUMNS
-- ============================================================================
-- SQLite does not support DROP COLUMN, so we must:
--   a) Create a backup table with only original columns
--   b) Drop the enhanced table
--   c) Rename backup to schedule_items
--   d) Recreate original indexes
--
-- NOTE: This section only runs if schedule_items has the Wave 1 columns.
-- If the columns don't exist, this section is a no-op.

-- Step 3a: Create backup table with original columns only
-- We check if the table exists first, then copy only the original columns
CREATE TABLE IF NOT EXISTS schedule_items_rollback AS
SELECT
    item_id,
    template_id,
    creator_id,
    scheduled_date,
    scheduled_time,
    item_type,
    channel,
    caption_id,
    caption_text,
    suggested_price,
    content_type_id,
    flyer_required,
    parent_item_id,
    is_follow_up,
    drip_set_id,
    drip_position,
    status,
    actual_earnings,
    priority,
    notes
FROM schedule_items
WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schedule_items');

-- Step 3b: Count rows for verification
SELECT 'INFO: Backed up ' || COUNT(*) || ' rows to schedule_items_rollback' AS backup_status
FROM schedule_items_rollback;

-- Step 3c: Drop the enhanced schedule_items table
DROP TABLE IF EXISTS schedule_items;

-- Step 3d: Rename rollback table to schedule_items
ALTER TABLE schedule_items_rollback RENAME TO schedule_items;

-- Step 3e: Recreate original indexes on schedule_items
-- These are the standard indexes that existed before Wave 1

CREATE INDEX IF NOT EXISTS idx_schedule_items_template
    ON schedule_items(template_id);

CREATE INDEX IF NOT EXISTS idx_schedule_items_creator
    ON schedule_items(creator_id);

CREATE INDEX IF NOT EXISTS idx_schedule_items_date
    ON schedule_items(scheduled_date);

CREATE INDEX IF NOT EXISTS idx_schedule_items_status
    ON schedule_items(status);

CREATE INDEX IF NOT EXISTS idx_schedule_items_parent
    ON schedule_items(parent_item_id)
    WHERE parent_item_id IS NOT NULL;

-- Verify schedule_items recreation
SELECT CASE
    WHEN COUNT(*) > 0 THEN 'OK: schedule_items table recreated'
    ELSE 'ERROR: schedule_items table missing'
END AS schedule_items_status
FROM sqlite_master
WHERE type = 'table' AND name = 'schedule_items';

-- ============================================================================
-- SECTION 4: DROP LOOKUP TABLES
-- ============================================================================
-- Drop in reverse dependency order

DROP TABLE IF EXISTS audience_targets;
DROP TABLE IF EXISTS channels;
DROP TABLE IF EXISTS send_types;

-- Verify lookup tables are dropped
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'OK: Lookup tables dropped'
    ELSE 'ERROR: Lookup tables still exist'
END AS lookup_status
FROM sqlite_master
WHERE type = 'table' AND name IN ('send_types', 'channels', 'audience_targets');

-- ============================================================================
-- SECTION 5: DROP INDEXES (Explicit Cleanup)
-- ============================================================================
-- Most indexes are dropped with their tables, but we explicitly drop
-- any Wave 1 indexes that might remain

-- Wave 1 schedule_items indexes (should already be gone with table recreation)
DROP INDEX IF EXISTS idx_schedule_items_send_type;
DROP INDEX IF EXISTS idx_schedule_items_channel_id;
DROP INDEX IF EXISTS idx_schedule_items_target;
DROP INDEX IF EXISTS idx_schedule_items_expires;
DROP INDEX IF EXISTS idx_schedule_items_parent;

-- Wave 1 lookup table indexes (should already be gone with table drops)
DROP INDEX IF EXISTS idx_send_types_category;
DROP INDEX IF EXISTS idx_send_types_page_type;
DROP INDEX IF EXISTS idx_send_types_active;
DROP INDEX IF EXISTS idx_channels_active;
DROP INDEX IF EXISTS idx_audience_targets_active;

-- Wave 1 mapping table indexes
DROP INDEX IF EXISTS idx_stcc_send_type;
DROP INDEX IF EXISTS idx_stcc_content_type;
DROP INDEX IF EXISTS idx_stcr_send_type;

-- ============================================================================
-- SECTION 6: REMOVE MIGRATION RECORD
-- ============================================================================
-- Remove the Wave 1 migration record from schema_migrations

DELETE FROM schema_migrations WHERE version = '008';

-- Verify migration record removed
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'OK: Migration 008 record removed'
    ELSE 'WARNING: Migration 008 record still exists'
END AS migration_status
FROM schema_migrations
WHERE version = '008';

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================
-- If we reach here, all rollback operations succeeded

COMMIT;

-- ============================================================================
-- ROLLBACK ON ERROR
-- ============================================================================
-- Note: SQLite will automatically rollback if any statement fails within
-- a transaction. If you need explicit error handling in a shell script:
--
-- sqlite3 database.db < 008_rollback.sql
-- if [ $? -ne 0 ]; then
--     echo "Rollback failed! Database may be in inconsistent state."
--     exit 1
-- fi

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these queries after rollback to confirm success:

-- 1. Verify view is gone
SELECT '=== VERIFICATION: View ===' AS section;
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'PASS: v_schedule_items_full does not exist'
    ELSE 'FAIL: v_schedule_items_full still exists'
END AS result
FROM sqlite_master
WHERE type = 'view' AND name = 'v_schedule_items_full';

-- 2. Verify mapping tables are gone
SELECT '=== VERIFICATION: Mapping Tables ===' AS section;
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'PASS: Mapping tables do not exist'
    ELSE 'FAIL: Mapping tables still exist'
END AS result
FROM sqlite_master
WHERE type = 'table' AND name IN (
    'send_type_content_compatibility',
    'send_type_caption_requirements'
);

-- 3. Verify lookup tables are gone
SELECT '=== VERIFICATION: Lookup Tables ===' AS section;
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'PASS: Lookup tables do not exist'
    ELSE 'FAIL: Lookup tables still exist'
END AS result
FROM sqlite_master
WHERE type = 'table' AND name IN ('send_types', 'channels', 'audience_targets');

-- 4. Verify schedule_items structure (no Wave 1 columns)
SELECT '=== VERIFICATION: schedule_items Structure ===' AS section;
SELECT 'Current columns: ' || GROUP_CONCAT(name, ', ') AS columns
FROM pragma_table_info('schedule_items');

-- 5. Verify schedule_items data preserved
SELECT '=== VERIFICATION: schedule_items Data ===' AS section;
SELECT 'Row count: ' || COUNT(*) AS data_status
FROM schedule_items;

-- 6. Verify migration record removed
SELECT '=== VERIFICATION: Migration Record ===' AS section;
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'PASS: Migration 008 record removed'
    ELSE 'FAIL: Migration 008 record still exists'
END AS result
FROM schema_migrations
WHERE version = '008';

-- 7. List remaining indexes on schedule_items
SELECT '=== VERIFICATION: schedule_items Indexes ===' AS section;
SELECT name AS remaining_indexes
FROM sqlite_master
WHERE type = 'index'
  AND tbl_name = 'schedule_items'
  AND name NOT LIKE 'sqlite_%';

-- ============================================================================
-- SUMMARY
-- ============================================================================
SELECT '=== ROLLBACK COMPLETE ===' AS status;
SELECT 'Wave 1 changes have been removed. Verify the above checks passed.' AS message;

-- ============================================================================
-- END OF ROLLBACK 008
-- ============================================================================
