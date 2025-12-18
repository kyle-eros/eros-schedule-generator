-- =============================================================================
-- EROS Database Maintenance Script #003
-- =============================================================================
-- Purpose: Database optimization and index cleanup
-- Date: 2025-12-01
-- Author: Database Administrator Agent (DBA-003)
--
-- This script performs routine database maintenance including:
--   1. VACUUM to reduce fragmentation (19.37% -> ~0%)
--   2. ANALYZE to update query planner statistics
--   3. Index review and optimization recommendations
--
-- PREREQUISITES:
--   1. Run 001_critical_fixes.sql and 002_creator_id_backfill.sql first
--   2. Create backup before running
--   3. Run during low-traffic period (VACUUM locks the database)
--   4. Ensure sufficient disk space (2x database size)
-- =============================================================================

-- =============================================================================
-- SECTION 1: Pre-Maintenance Stats
-- =============================================================================

SELECT '=== PRE-MAINTENANCE DATABASE STATS ===' as section;

-- Current fragmentation
SELECT
    (SELECT page_count FROM pragma_page_count()) as total_pages,
    (SELECT freelist_count FROM pragma_freelist_count()) as free_pages,
    ROUND(100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                  (SELECT page_count FROM pragma_page_count()), 2) as fragmentation_pct;

-- Current database size
SELECT 'Database size (pages)' as metric, page_count FROM pragma_page_count();
SELECT 'Page size (bytes)' as metric, page_size FROM pragma_page_size();


-- =============================================================================
-- SECTION 2: Update Statistics (ANALYZE)
-- =============================================================================
-- ANALYZE updates sqlite_stat1 table with row distribution statistics
-- This helps the query planner make better index choices
-- =============================================================================

ANALYZE;

SELECT 'ANALYZE completed - statistics updated' as status;


-- =============================================================================
-- SECTION 3: VACUUM Database
-- =============================================================================
-- VACUUM rebuilds the database file, reclaiming free pages and defragmenting
-- WARNING: This locks the database and requires 2x disk space temporarily
-- =============================================================================

-- Note: VACUUM cannot be run inside a transaction
-- It must be run as a standalone command

VACUUM;

SELECT 'VACUUM completed - database defragmented' as status;


-- =============================================================================
-- SECTION 4: Post-Maintenance Stats
-- =============================================================================

SELECT '=== POST-MAINTENANCE DATABASE STATS ===' as section;

-- New fragmentation (should be ~0%)
SELECT
    (SELECT page_count FROM pragma_page_count()) as total_pages,
    (SELECT freelist_count FROM pragma_freelist_count()) as free_pages,
    ROUND(100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                  (SELECT page_count FROM pragma_page_count()), 2) as fragmentation_pct;

-- New database size
SELECT 'Database size (pages)' as metric, page_count FROM pragma_page_count();


-- =============================================================================
-- SECTION 5: Index Health Report
-- =============================================================================

SELECT '=== INDEX HEALTH REPORT ===' as section;

-- Index usage statistics from sqlite_stat1
SELECT
    tbl as table_name,
    idx as index_name,
    stat as statistics
FROM sqlite_stat1
WHERE idx IS NOT NULL
ORDER BY tbl, idx;

-- Index column composition
SELECT '=== INDEX DEFINITIONS ===' as section;

SELECT
    name as index_name,
    tbl_name as table_name,
    CASE
        WHEN sql LIKE '%WHERE%' THEN 'Partial Index'
        WHEN sql LIKE '%UNIQUE%' THEN 'Unique Index'
        ELSE 'Standard Index'
    END as index_type
FROM sqlite_master
WHERE type = 'index'
AND sql IS NOT NULL
ORDER BY tbl_name, name;


-- =============================================================================
-- SECTION 6: Recommendations for Index Optimization
-- =============================================================================

SELECT '=== INDEX OPTIMIZATION RECOMMENDATIONS ===' as section;

-- Tables with many indexes relative to row count
SELECT
    m.tbl_name as table_name,
    COUNT(*) as index_count,
    CASE m.tbl_name
        WHEN 'creators' THEN 36
        WHEN 'caption_bank' THEN 19590
        WHEN 'mass_messages' THEN 66826
        WHEN 'caption_creator_performance' THEN 11069
        WHEN 'vault_matrix' THEN 1188
        ELSE 0
    END as approx_rows,
    CASE
        WHEN m.tbl_name = 'creators' AND COUNT(*) > 4 THEN 'REVIEW: Many indexes for small table'
        WHEN COUNT(*) > 10 THEN 'NOTE: Consider consolidating if queries overlap'
        ELSE 'OK'
    END as recommendation
FROM sqlite_master m
WHERE m.type = 'index'
AND m.sql IS NOT NULL
GROUP BY m.tbl_name
ORDER BY index_count DESC;

-- Log maintenance completion
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
VALUES ('DBA-003', 'MAINTENANCE_COMPLETE',
        'Ran ANALYZE and VACUUM, updated statistics, reviewed indexes',
        0, datetime('now'));

-- =============================================================================
-- END OF MAINTENANCE SCRIPT #003
-- =============================================================================
