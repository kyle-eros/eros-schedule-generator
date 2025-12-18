-- EROS Database Weekly Health Check
-- Run: sqlite3 database/eros_sd_main.db < database/audit/queries/weekly_health_check.sql

.mode column
.headers on

SELECT '=== EROS DATABASE HEALTH CHECK ===' as report;
SELECT datetime('now') as check_time;

-- 1. Database Fragmentation
SELECT '--- Fragmentation Analysis ---' as section;
SELECT
    (SELECT page_count FROM pragma_page_count()) as total_pages,
    (SELECT freelist_count FROM pragma_freelist_count()) as free_pages,
    ROUND(100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                  (SELECT page_count FROM pragma_page_count()), 2) as fragmentation_pct,
    CASE
        WHEN 100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                     (SELECT page_count FROM pragma_page_count()) > 25
        THEN 'VACUUM RECOMMENDED'
        ELSE 'OK'
    END as status;

-- 2. FK Enforcement Status
SELECT '--- Foreign Key Status ---' as section;
SELECT
    'foreign_keys' as pragma,
    CASE (SELECT * FROM pragma_foreign_keys())
        WHEN 1 THEN 'ENABLED'
        ELSE 'DISABLED - CRITICAL'
    END as status;

-- 3. Integrity Check
SELECT '--- Integrity Check ---' as section;
SELECT * FROM pragma_integrity_check() LIMIT 1;

-- 4. Orphaned Records Summary
SELECT '--- Orphan Detection ---' as section;
SELECT
    'mass_messages.creator_id orphans' as check_type,
    COUNT(*) as count,
    CASE WHEN COUNT(*) > 0 THEN 'HIGH' ELSE 'OK' END as severity
FROM mass_messages mm
WHERE mm.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = mm.creator_id)
UNION ALL
SELECT 'wall_posts.creator_id orphans', COUNT(*),
    CASE WHEN COUNT(*) > 0 THEN 'HIGH' ELSE 'OK' END
FROM wall_posts wp
WHERE wp.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = wp.creator_id);

-- 5. NULL Creator ID Check
SELECT '--- NULL Creator IDs ---' as section;
SELECT
    'mass_messages.creator_id NULL' as field,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM mass_messages), 2) as pct
FROM mass_messages WHERE creator_id IS NULL
UNION ALL
SELECT 'wall_posts.creator_id NULL', COUNT(*),
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM wall_posts), 2)
FROM wall_posts WHERE creator_id IS NULL;

-- 6. Data Anomalies
SELECT '--- Data Anomalies ---' as section;
SELECT
    'negative sent_count' as anomaly,
    COUNT(*) as count
FROM mass_messages WHERE sent_count < 0
UNION ALL
SELECT 'viewed > sent', COUNT(*)
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0
UNION ALL
SELECT 'page_name = nan', COUNT(*)
FROM mass_messages WHERE page_name = 'nan';

-- 7. Stale Analytics
SELECT '--- Stale Analytics ---' as section;
SELECT
    creator_id,
    page_name,
    period_type,
    calculated_at,
    ROUND(julianday('now') - julianday(calculated_at), 1) as days_old
FROM creator_analytics_summary
WHERE calculated_at < datetime('now', '-7 days')
ORDER BY calculated_at
LIMIT 10;

-- 8. Missing Relationships
SELECT '--- Missing Relationships ---' as section;
SELECT
    c.creator_id,
    c.page_name,
    'missing persona' as issue
FROM creators c
WHERE NOT EXISTS (SELECT 1 FROM creator_personas cp WHERE cp.creator_id = c.creator_id)
UNION ALL
SELECT
    c.creator_id,
    c.page_name,
    'missing scheduler assignment'
FROM creators c
WHERE c.is_active = 1
AND NOT EXISTS (SELECT 1 FROM scheduler_assignments sa WHERE sa.creator_id = c.creator_id);

SELECT '=== HEALTH CHECK COMPLETE ===' as report;
