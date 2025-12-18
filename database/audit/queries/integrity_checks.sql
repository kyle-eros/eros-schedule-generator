-- EROS Database Integrity Checks
-- Run: sqlite3 database/eros_sd_main.db < database/audit/queries/integrity_checks.sql

.mode column
.headers on

SELECT '=== EROS DATABASE INTEGRITY CHECKS ===' as report;
SELECT datetime('now') as check_time;

-- 1. Comprehensive Orphan Detection
SELECT '--- Orphan Detection ---' as section;

SELECT 'mass_messages.creator_id' as fk_path, COUNT(*) as orphans
FROM mass_messages mm
WHERE mm.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = mm.creator_id)
UNION ALL
SELECT 'mass_messages.content_type_id', COUNT(*)
FROM mass_messages mm WHERE mm.content_type_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM content_types ct WHERE ct.content_type_id = mm.content_type_id)
UNION ALL
SELECT 'caption_bank.creator_id', COUNT(*)
FROM caption_bank cb WHERE cb.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = cb.creator_id)
UNION ALL
SELECT 'caption_bank.content_type_id', COUNT(*)
FROM caption_bank cb WHERE cb.content_type_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM content_types ct WHERE ct.content_type_id = cb.content_type_id)
UNION ALL
SELECT 'vault_matrix.creator_id', COUNT(*)
FROM vault_matrix vm WHERE NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = vm.creator_id)
UNION ALL
SELECT 'vault_matrix.content_type_id', COUNT(*)
FROM vault_matrix vm WHERE NOT EXISTS (SELECT 1 FROM content_types ct WHERE ct.content_type_id = vm.content_type_id)
UNION ALL
SELECT 'scheduler_assignments.creator_id', COUNT(*)
FROM scheduler_assignments sa WHERE NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = sa.creator_id)
UNION ALL
SELECT 'scheduler_assignments.scheduler_id', COUNT(*)
FROM scheduler_assignments sa WHERE NOT EXISTS (SELECT 1 FROM schedulers s WHERE s.scheduler_id = sa.scheduler_id)
UNION ALL
SELECT 'creator_personas.creator_id', COUNT(*)
FROM creator_personas cp WHERE NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = cp.creator_id)
UNION ALL
SELECT 'creator_analytics_summary.creator_id', COUNT(*)
FROM creator_analytics_summary cas WHERE NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = cas.creator_id)
UNION ALL
SELECT 'caption_creator_performance.caption_id', COUNT(*)
FROM caption_creator_performance ccp WHERE NOT EXISTS (SELECT 1 FROM caption_bank cb WHERE cb.caption_id = ccp.caption_id)
UNION ALL
SELECT 'caption_creator_performance.creator_id', COUNT(*)
FROM caption_creator_performance ccp WHERE ccp.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = ccp.creator_id)
UNION ALL
SELECT 'wall_posts.creator_id', COUNT(*)
FROM wall_posts wp WHERE wp.creator_id IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM creators c WHERE c.creator_id = wp.creator_id)
UNION ALL
SELECT 'caption_audit_log.caption_id', COUNT(*)
FROM caption_audit_log cal WHERE NOT EXISTS (SELECT 1 FROM caption_bank cb WHERE cb.caption_id = cal.caption_id);

-- 2. NULL Value Analysis
SELECT '--- NULL Analysis ---' as section;

SELECT 'mass_messages.creator_id NULL' as field, COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM mass_messages), 2) as pct
FROM mass_messages WHERE creator_id IS NULL
UNION ALL
SELECT 'mass_messages.page_name = nan', COUNT(*),
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM mass_messages), 2)
FROM mass_messages WHERE page_name = 'nan'
UNION ALL
SELECT 'mass_messages.content_type_id NULL', COUNT(*),
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM mass_messages), 2)
FROM mass_messages WHERE content_type_id IS NULL
UNION ALL
SELECT 'caption_bank.creator_id NULL', COUNT(*),
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM caption_bank), 2)
FROM caption_bank WHERE creator_id IS NULL
UNION ALL
SELECT 'wall_posts.creator_id NULL', COUNT(*),
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM wall_posts), 2)
FROM wall_posts WHERE creator_id IS NULL;

-- 3. Duplicate Detection
SELECT '--- Duplicate Detection ---' as section;

SELECT 'caption_bank.caption_hash duplicates' as check_type,
       COUNT(*) - COUNT(DISTINCT caption_hash) as count
FROM caption_bank
UNION ALL
SELECT 'creators.page_name duplicates',
       COUNT(*) - COUNT(DISTINCT page_name)
FROM creators;

-- 4. CHECK Constraint Violations
SELECT '--- CHECK Constraint Violations ---' as section;

SELECT 'creators.page_type invalid' as check_type, COUNT(*) as violations
FROM creators WHERE page_type NOT IN ('paid', 'free')
UNION ALL
SELECT 'mass_messages.message_type invalid', COUNT(*)
FROM mass_messages WHERE message_type NOT IN ('ppv', 'free')
UNION ALL
SELECT 'creator_personas.emoji_frequency invalid', COUNT(*)
FROM creator_personas WHERE emoji_frequency IS NOT NULL
AND emoji_frequency NOT IN ('heavy', 'moderate', 'light', 'none')
UNION ALL
SELECT 'creator_personas.slang_level invalid', COUNT(*)
FROM creator_personas WHERE slang_level IS NOT NULL
AND slang_level NOT IN ('none', 'light', 'heavy')
UNION ALL
SELECT 'vault_matrix.quality_rating out of range', COUNT(*)
FROM vault_matrix WHERE quality_rating IS NOT NULL
AND (quality_rating < 1 OR quality_rating > 5);

-- 5. Primary Key Integrity
SELECT '--- Primary Key Integrity ---' as section;

SELECT 'creators.creator_id invalid UUID' as check_type, COUNT(*) as count
FROM creators
WHERE length(creator_id) != 36
   OR creator_id NOT LIKE '________-____-____-____-____________';

-- 6. Missing Relationship Coverage
SELECT '--- Missing Relationships ---' as section;

SELECT 'creators without persona' as relationship, COUNT(*) as count
FROM creators c
WHERE NOT EXISTS (SELECT 1 FROM creator_personas cp WHERE cp.creator_id = c.creator_id)
UNION ALL
SELECT 'creators without analytics', COUNT(*)
FROM creators c
WHERE NOT EXISTS (SELECT 1 FROM creator_analytics_summary cas WHERE cas.creator_id = c.creator_id)
UNION ALL
SELECT 'active creators without scheduler', COUNT(*)
FROM creators c
WHERE c.is_active = 1
AND NOT EXISTS (SELECT 1 FROM scheduler_assignments sa WHERE sa.creator_id = c.creator_id);

SELECT '=== INTEGRITY CHECKS COMPLETE ===' as report;
