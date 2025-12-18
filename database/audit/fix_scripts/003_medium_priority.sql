-- EROS Database Medium Priority Fixes
-- Severity: P2 - Execute during maintenance window
--
-- Run: sqlite3 database/eros_sd_main.db < database/audit/fix_scripts/003_medium_priority.sql
--
-- PREREQUISITE: Create backup and run 001, 002 first!

.mode column
.headers on

SELECT '=== EROS DATABASE MEDIUM PRIORITY FIXES ===' as report;
SELECT datetime('now') as execution_time;

-- Enable foreign keys for this session
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Fix 1: Create missing persona for lola_reese_new
SELECT '--- Fix 1: Creating missing persona ---' as step;

-- Check current state
SELECT c.creator_id, c.page_name, 'needs persona' as status
FROM creators c
WHERE c.page_name = 'lola_reese_new'
AND NOT EXISTS (SELECT 1 FROM creator_personas cp WHERE cp.creator_id = c.creator_id);

-- Insert persona with default values
INSERT OR IGNORE INTO creator_personas (
    creator_id,
    primary_tone,
    emoji_frequency,
    slang_level,
    avg_sentiment,
    avg_caption_length,
    created_at,
    updated_at
)
SELECT
    c.creator_id,
    'playful',       -- Default primary tone
    'moderate',      -- Default emoji frequency
    'light',         -- Default slang level
    0.5,             -- Neutral sentiment
    100,             -- Average caption length
    datetime('now'),
    datetime('now')
FROM creators c
WHERE c.page_name = 'lola_reese_new'
AND NOT EXISTS (SELECT 1 FROM creator_personas cp WHERE cp.creator_id = c.creator_id);

SELECT changes() as personas_created;

-- Fix 2: Create missing scheduler assignment for lola_reese_new
SELECT '--- Fix 2: Creating missing scheduler assignment ---' as step;

-- Find an active scheduler to assign
SELECT scheduler_id, name FROM schedulers WHERE is_active = 1 LIMIT 1;

-- Insert scheduler assignment (to first active scheduler)
INSERT OR IGNORE INTO scheduler_assignments (
    scheduler_id,
    creator_id,
    is_primary,
    assigned_at,
    tier,
    status
)
SELECT
    (SELECT scheduler_id FROM schedulers WHERE is_active = 1 LIMIT 1),
    c.creator_id,
    1,
    datetime('now'),
    'Med',
    'active'
FROM creators c
WHERE c.page_name = 'lola_reese_new'
AND NOT EXISTS (
    SELECT 1 FROM scheduler_assignments sa
    WHERE sa.creator_id = c.creator_id
);

SELECT changes() as assignments_created;

COMMIT;

-- Fix 3: Database maintenance (VACUUM)
SELECT '--- Fix 3: Running ANALYZE ---' as step;

-- Update query planner statistics
ANALYZE;

SELECT '--- Database Maintenance ---' as step;
SELECT 'Run VACUUM manually during low-traffic period' as note;
SELECT 'Command: sqlite3 database/eros_sd_main.db "VACUUM;"' as command;

-- Report current fragmentation
SELECT
    (SELECT page_count FROM pragma_page_count()) as total_pages,
    (SELECT freelist_count FROM pragma_freelist_count()) as free_pages,
    ROUND(100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                  (SELECT page_count FROM pragma_page_count()), 2) as fragmentation_pct;

SELECT '=== MEDIUM PRIORITY FIXES COMPLETE ===' as report;

-- Final verification
SELECT '--- Final Verification ---' as section;

SELECT 'creators without persona' as check_type, COUNT(*) as count
FROM creators c
WHERE NOT EXISTS (SELECT 1 FROM creator_personas cp WHERE cp.creator_id = c.creator_id)
UNION ALL
SELECT 'active creators without scheduler', COUNT(*)
FROM creators c
WHERE c.is_active = 1
AND NOT EXISTS (SELECT 1 FROM scheduler_assignments sa WHERE sa.creator_id = c.creator_id);
