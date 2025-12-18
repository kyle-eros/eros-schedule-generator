-- EROS Database High Priority Fixes
-- Severity: P1 - Execute after critical fixes
--
-- Run: sqlite3 database/eros_sd_main.db < database/audit/fix_scripts/002_high_priority.sql
--
-- PREREQUISITE: Create backup and run 001_critical.sql first!

.mode column
.headers on

SELECT '=== EROS DATABASE HIGH PRIORITY FIXES ===' as report;
SELECT datetime('now') as execution_time;

-- Enable foreign keys for this session
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Fix 1: Backfill mass_messages.creator_id from page_name where possible
SELECT '--- Fix 1: Backfilling mass_messages.creator_id ---' as step;

-- Count records that CAN be backfilled
SELECT COUNT(*) as can_be_backfilled
FROM mass_messages mm
WHERE mm.creator_id IS NULL
AND mm.page_name IS NOT NULL
AND mm.page_name != 'nan'
AND EXISTS (SELECT 1 FROM creators c WHERE c.page_name = mm.page_name);

-- Perform the backfill
UPDATE mass_messages
SET creator_id = (
    SELECT c.creator_id
    FROM creators c
    WHERE c.page_name = mass_messages.page_name
)
WHERE creator_id IS NULL
AND page_name IS NOT NULL
AND page_name != 'nan'
AND page_name IN (SELECT page_name FROM creators);

SELECT changes() as records_fixed;

-- Verify remaining NULL creator_ids
SELECT COUNT(*) as remaining_null_creator_id
FROM mass_messages WHERE creator_id IS NULL;

-- Fix 2: Backfill wall_posts.creator_id from page_name
SELECT '--- Fix 2: Backfilling wall_posts.creator_id ---' as step;

-- Count records that CAN be backfilled
SELECT COUNT(*) as can_be_backfilled
FROM wall_posts wp
WHERE wp.creator_id IS NULL
AND wp.page_name IS NOT NULL
AND EXISTS (SELECT 1 FROM creators c WHERE c.page_name = wp.page_name);

-- Perform the backfill
UPDATE wall_posts
SET creator_id = (
    SELECT c.creator_id
    FROM creators c
    WHERE c.page_name = wall_posts.page_name
)
WHERE creator_id IS NULL
AND page_name IS NOT NULL
AND page_name IN (SELECT page_name FROM creators);

SELECT changes() as records_fixed;

COMMIT;

-- Report on unmapped page_names (for investigation)
SELECT '--- Unmapped Page Names (top 20) ---' as section;

SELECT
    page_name,
    COUNT(*) as record_count,
    MIN(sending_time) as first_seen,
    MAX(sending_time) as last_seen
FROM mass_messages
WHERE creator_id IS NULL
AND page_name IS NOT NULL
AND page_name NOT IN (SELECT page_name FROM creators)
GROUP BY page_name
ORDER BY record_count DESC
LIMIT 20;

SELECT '=== HIGH PRIORITY FIXES COMPLETE ===' as report;
