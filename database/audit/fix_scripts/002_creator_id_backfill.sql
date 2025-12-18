-- =============================================================================
-- EROS Database High Priority Fix Script #002
-- =============================================================================
-- Purpose: Backfill creator_id from page_name mappings
-- Date: 2025-12-01
-- Author: Database Administrator Agent (DBA-003)
--
-- This script addresses the high-priority issue of 30,361 NULL creator_id
-- records in mass_messages (45.43% of data).
--
-- STRATEGY:
--   1. Create page_name to creator_id mapping from existing creators
--   2. Backfill mass_messages.creator_id where page_name matches
--   3. Create historical mapping table for legacy page_names
--   4. Backfill wall_posts.creator_id
--
-- PREREQUISITES:
--   1. Run 001_critical_fixes.sql first
--   2. Create backup before running
--   3. Run during maintenance window
-- =============================================================================

-- =============================================================================
-- SECTION 1: Analyze Current State
-- =============================================================================

-- Show current state of creator_id population
SELECT 'mass_messages creator_id analysis' as analysis;

SELECT
    CASE
        WHEN creator_id IS NOT NULL THEN 'Has creator_id'
        WHEN page_name IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL) THEN 'Can backfill from page_name'
        WHEN page_name IS NOT NULL THEN 'Legacy page_name (no mapping)'
        ELSE 'No creator_id or page_name'
    END as category,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM mass_messages), 2) as percentage
FROM mass_messages
GROUP BY category
ORDER BY count DESC;


-- =============================================================================
-- SECTION 2: Backfill creator_id in mass_messages
-- =============================================================================

BEGIN TRANSACTION;

-- Count records that can be backfilled
SELECT 'Records eligible for backfill' as check_type, COUNT(*) as count
FROM mass_messages m
WHERE m.creator_id IS NULL
AND m.page_name IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL);

-- Perform the backfill
UPDATE mass_messages
SET creator_id = (
    SELECT c.creator_id
    FROM creators c
    WHERE c.page_name = mass_messages.page_name
)
WHERE creator_id IS NULL
AND page_name IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL);

-- Verify backfill results
SELECT 'After backfill - NULL creator_id remaining' as check_type, COUNT(*) as count
FROM mass_messages WHERE creator_id IS NULL;

SELECT 'After backfill - creator_id coverage' as check_type,
       ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as percentage
FROM mass_messages;

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'BACKFILL_CREATOR_ID_MASS_MESSAGES',
       'Backfilled creator_id from page_name mapping in mass_messages',
       changes(), datetime('now');


-- =============================================================================
-- SECTION 3: Backfill creator_id in wall_posts
-- =============================================================================

BEGIN TRANSACTION;

-- Check current state
SELECT 'wall_posts - NULL creator_id' as check_type, COUNT(*) as count
FROM wall_posts WHERE creator_id IS NULL;

-- Check how many can be backfilled
SELECT 'wall_posts - Can backfill' as check_type, COUNT(*) as count
FROM wall_posts w
WHERE w.creator_id IS NULL
AND w.page_name IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL);

-- Perform the backfill
UPDATE wall_posts
SET creator_id = (
    SELECT c.creator_id
    FROM creators c
    WHERE c.page_name = wall_posts.page_name
)
WHERE creator_id IS NULL
AND page_name IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL);

-- Verify backfill results
SELECT 'wall_posts - After backfill NULL remaining' as check_type, COUNT(*) as count
FROM wall_posts WHERE creator_id IS NULL;

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'BACKFILL_CREATOR_ID_WALL_POSTS',
       'Backfilled creator_id from page_name mapping in wall_posts',
       changes(), datetime('now');


-- =============================================================================
-- SECTION 4: Create Historical Page Name Mapping Table
-- =============================================================================

BEGIN TRANSACTION;

-- Create mapping table for legacy page_names that no longer have active creators
CREATE TABLE IF NOT EXISTS legacy_page_name_mapping (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_page_name TEXT UNIQUE NOT NULL,
    current_creator_id TEXT,
    mapping_status TEXT NOT NULL DEFAULT 'unmapped'
        CHECK (mapping_status IN ('unmapped', 'mapped', 'retired', 'merged')),
    notes TEXT,
    record_count INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (current_creator_id) REFERENCES creators(creator_id)
);

-- Populate with unmapped page_names from mass_messages
INSERT OR IGNORE INTO legacy_page_name_mapping (
    legacy_page_name,
    mapping_status,
    record_count,
    first_seen,
    last_seen
)
SELECT
    page_name,
    'unmapped',
    COUNT(*) as record_count,
    MIN(sending_time) as first_seen,
    MAX(sending_time) as last_seen
FROM mass_messages
WHERE creator_id IS NULL
AND page_name IS NOT NULL
AND page_name NOT IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL)
GROUP BY page_name;

-- Show unmapped page_names summary
SELECT 'Legacy page_names identified' as check_type, COUNT(*) as count
FROM legacy_page_name_mapping WHERE mapping_status = 'unmapped';

-- Show top unmapped page_names by record count
SELECT 'Top 20 unmapped page_names' as section;
SELECT legacy_page_name, record_count, first_seen, last_seen
FROM legacy_page_name_mapping
WHERE mapping_status = 'unmapped'
ORDER BY record_count DESC
LIMIT 20;

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'CREATE_LEGACY_MAPPING_TABLE',
       'Created legacy_page_name_mapping table and populated with unmapped page_names',
       (SELECT COUNT(*) FROM legacy_page_name_mapping), datetime('now');


-- =============================================================================
-- SECTION 5: Final Verification
-- =============================================================================

SELECT '=== BACKFILL VERIFICATION SUMMARY ===' as section;

-- Overall coverage after backfill
SELECT 'mass_messages creator_id coverage' as metric,
       ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as percentage,
       SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) as populated,
       SUM(CASE WHEN creator_id IS NULL THEN 1 ELSE 0 END) as missing
FROM mass_messages;

SELECT 'wall_posts creator_id coverage' as metric,
       ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as percentage,
       SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) as populated,
       SUM(CASE WHEN creator_id IS NULL THEN 1 ELSE 0 END) as missing
FROM wall_posts;

-- Remaining unmapped records by category
SELECT 'Remaining unmapped records' as section;
SELECT
    CASE
        WHEN page_name IS NULL THEN 'No page_name'
        ELSE 'Legacy page_name in mapping table'
    END as category,
    COUNT(*) as count
FROM mass_messages
WHERE creator_id IS NULL
GROUP BY category;

-- =============================================================================
-- END OF BACKFILL SCRIPT #002
-- =============================================================================
