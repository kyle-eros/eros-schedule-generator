-- EROS Database Critical Fixes
-- Severity: P0/P1 - Execute with backup first
--
-- Run: sqlite3 database/eros_sd_main.db < database/audit/fix_scripts/001_critical.sql
--
-- PREREQUISITE: Create backup first!
-- sqlite3 database/eros_sd_main.db ".backup database/backups/eros_sd_main_$(date +%Y%m%d_%H%M%S).db"

.mode column
.headers on

SELECT '=== EROS DATABASE CRITICAL FIXES ===' as report;
SELECT datetime('now') as execution_time;

-- Enable foreign keys for this session
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Fix 1: Clean 'nan' page_names (11,186 records)
SELECT '--- Fix 1: Cleaning nan page_names ---' as step;

SELECT COUNT(*) as records_to_fix FROM mass_messages WHERE page_name = 'nan';

UPDATE mass_messages SET page_name = NULL WHERE page_name = 'nan';

SELECT changes() as records_fixed;

-- Fix 2: Fix negative sent_count (6 records)
SELECT '--- Fix 2: Fixing negative sent_count ---' as step;

SELECT COUNT(*) as records_to_fix FROM mass_messages WHERE sent_count < 0;

UPDATE mass_messages SET sent_count = 0 WHERE sent_count < 0;

SELECT changes() as records_fixed;

-- Fix 3: Fix impossible view rates (viewed > sent) - 60 records
SELECT '--- Fix 3: Fixing viewed_count > sent_count ---' as step;

SELECT COUNT(*) as records_to_fix
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0;

UPDATE mass_messages
SET viewed_count = sent_count
WHERE viewed_count > sent_count AND sent_count > 0;

SELECT changes() as records_fixed;

-- Fix 4: Fix impossible purchase rates (purchased > viewed)
SELECT '--- Fix 4: Fixing purchased_count > viewed_count ---' as step;

SELECT COUNT(*) as records_to_fix
FROM mass_messages WHERE purchased_count > viewed_count AND viewed_count > 0;

UPDATE mass_messages
SET purchased_count = viewed_count
WHERE purchased_count > viewed_count AND viewed_count > 0;

SELECT changes() as records_fixed;

COMMIT;

SELECT '=== CRITICAL FIXES COMPLETE ===' as report;
SELECT '=== Run data_quality_score.sql to verify improvement ===' as next_step;
