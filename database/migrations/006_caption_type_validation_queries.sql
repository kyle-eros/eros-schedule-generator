-- ============================================================================
-- EROS Caption Type Taxonomy Migration - VALIDATION QUERIES
-- Companion to: 006_caption_type_taxonomy_migration.sql
-- Purpose: Validate migration success and identify issues
-- Author: Claude Code (SQL Pro)
-- Created: 2025-12-12
-- ============================================================================

-- ============================================================================
-- PRE-MIGRATION VALIDATION (Run BEFORE migration)
-- ============================================================================

-- 1. Count total records to migrate
SELECT 'PRE-MIGRATION: Total Records' as check_name,
       COUNT(*) as count
FROM caption_bank;

-- 2. Identify all unique type combinations (should match mapping table)
SELECT 'PRE-MIGRATION: Type Combinations' as check_name,
       caption_type,
       send_type,
       COUNT(*) as count
FROM caption_bank
GROUP BY caption_type, send_type
ORDER BY count DESC;

-- 3. Check for NULL caption_type (should be 0 - it's NOT NULL)
SELECT 'PRE-MIGRATION: NULL caption_type' as check_name,
       COUNT(*) as count
FROM caption_bank
WHERE caption_type IS NULL;

-- 4. Check for NULL/empty send_type values
SELECT 'PRE-MIGRATION: NULL/Empty send_type' as check_name,
       SUM(CASE WHEN send_type IS NULL THEN 1 ELSE 0 END) as null_count,
       SUM(CASE WHEN send_type = '' THEN 1 ELSE 0 END) as empty_count
FROM caption_bank;

-- ============================================================================
-- UNMAPPED COMBINATIONS DETECTION
-- ============================================================================

-- 5. Find any combinations NOT in the mapping table
-- This query identifies gaps in our mapping rules
SELECT 'UNMAPPED COMBINATIONS' as check_name,
       cb.caption_type,
       cb.send_type,
       COUNT(*) as affected_records
FROM caption_bank cb
LEFT JOIN caption_type_migration_map m
    ON m.old_caption_type = cb.caption_type
   AND m.old_send_type = COALESCE(cb.send_type, '_NULL_')
WHERE m.old_caption_type IS NULL
GROUP BY cb.caption_type, cb.send_type
ORDER BY affected_records DESC;

-- 6. Alternative unmapped detection (handles empty strings too)
SELECT 'UNMAPPED WITH EMPTY HANDLING' as check_name,
       cb.caption_type,
       cb.send_type,
       COUNT(*) as affected_records
FROM caption_bank cb
WHERE NOT EXISTS (
    SELECT 1 FROM caption_type_migration_map m
    WHERE m.old_caption_type = cb.caption_type
      AND (
          m.old_send_type = cb.send_type
          OR (m.old_send_type = '_NULL_' AND cb.send_type IS NULL)
          OR (m.old_send_type = '_EMPTY_' AND cb.send_type = '')
      )
)
GROUP BY cb.caption_type, cb.send_type;

-- ============================================================================
-- POST-MIGRATION VALIDATION (Run AFTER migration)
-- ============================================================================

-- 7. Check for NULLs in new columns (should be 0 after successful migration)
SELECT 'POST-MIGRATION: NULL Check' as check_name,
       SUM(CASE WHEN caption_type_v2 IS NULL THEN 1 ELSE 0 END) as null_caption_type_v2,
       SUM(CASE WHEN send_type_v2 IS NULL THEN 1 ELSE 0 END) as null_send_type_v2,
       SUM(CASE WHEN is_paid_page_only IS NULL THEN 1 ELSE 0 END) as null_is_paid_page_only
FROM caption_bank;

-- 8. Verify all records migrated
SELECT 'POST-MIGRATION: Migration Coverage' as check_name,
       COUNT(*) as total_records,
       SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) as migrated_records,
       ROUND(100.0 * SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as pct_migrated
FROM caption_bank;

-- 9. Distribution of new caption_type_v2 values
SELECT 'POST-MIGRATION: caption_type_v2 Distribution' as check_name,
       caption_type_v2,
       COUNT(*) as count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as pct
FROM caption_bank
GROUP BY caption_type_v2
ORDER BY count DESC;

-- 10. Distribution of new send_type_v2 values
SELECT 'POST-MIGRATION: send_type_v2 Distribution' as check_name,
       send_type_v2,
       COUNT(*) as count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as pct
FROM caption_bank
GROUP BY send_type_v2
ORDER BY count DESC;

-- 11. Paid page only records (should be renewal_reminder and expired_winback)
SELECT 'POST-MIGRATION: Paid Page Only Records' as check_name,
       caption_type_v2,
       send_type_v2,
       COUNT(*) as count
FROM caption_bank
WHERE is_paid_page_only = 1
GROUP BY caption_type_v2, send_type_v2
ORDER BY count DESC;

-- 12. Verify paid page types are correctly flagged
SELECT 'POST-MIGRATION: Paid Page Type Verification' as check_name,
       caption_type_v2,
       SUM(CASE WHEN is_paid_page_only = 1 THEN 1 ELSE 0 END) as paid_only_count,
       SUM(CASE WHEN is_paid_page_only = 0 THEN 1 ELSE 0 END) as not_paid_only_count
FROM caption_bank
WHERE caption_type_v2 IN ('renewal_reminder', 'expired_winback')
GROUP BY caption_type_v2;

-- ============================================================================
-- MAPPING COMPARISON (Shows old -> new transformation)
-- ============================================================================

-- 13. Full mapping comparison report
SELECT 'MAPPING COMPARISON' as check_name,
       cb.caption_type as old_caption_type,
       cb.send_type as old_send_type,
       cb.caption_type_v2 as new_caption_type,
       cb.send_type_v2 as new_send_type,
       cb.is_paid_page_only,
       COUNT(*) as count
FROM caption_bank cb
GROUP BY cb.caption_type, cb.send_type, cb.caption_type_v2, cb.send_type_v2, cb.is_paid_page_only
ORDER BY count DESC;

-- 14. Records that fell back to default (general/mass_message)
SELECT 'FALLBACK RECORDS' as check_name,
       caption_type,
       send_type,
       COUNT(*) as count
FROM caption_bank
WHERE caption_type_v2 = 'general'
  AND send_type_v2 = 'mass_message'
  AND caption_type != 'general'  -- Exclude legitimate 'general' mappings
GROUP BY caption_type, send_type;

-- ============================================================================
-- DATA INTEGRITY CHECKS
-- ============================================================================

-- 15. Verify new values are in allowed taxonomy
SELECT 'INVALID caption_type_v2 VALUES' as check_name,
       caption_type_v2,
       COUNT(*) as count
FROM caption_bank
WHERE caption_type_v2 NOT IN (
    'ppv_unlock', 'bundle', 'tip_campaign', 'link_drop', 'feed_bump',
    'dm_farm', 'like_farm', 'renewal_reminder', 'expired_winback',
    'live_promo', 'descriptive_tease', 'text_only', 'normal_bump',
    'ppv_followup', 'general'
)
GROUP BY caption_type_v2;

-- 16. Verify new send_type values are in allowed taxonomy
SELECT 'INVALID send_type_v2 VALUES' as check_name,
       send_type_v2,
       COUNT(*) as count
FROM caption_bank
WHERE send_type_v2 NOT IN (
    'mass_message', 'wall_post', 'auto_message', 'campaign_message',
    'followup_message', 'drip_message', 'segment_message', 'direct_message'
)
GROUP BY send_type_v2;

-- 17. Cross-check: is_paid_page_only should ONLY be 1 for specific types
SELECT 'UNEXPECTED PAID PAGE ONLY FLAGS' as check_name,
       caption_type_v2,
       COUNT(*) as count
FROM caption_bank
WHERE is_paid_page_only = 1
  AND caption_type_v2 NOT IN ('renewal_reminder', 'expired_winback')
GROUP BY caption_type_v2;

-- ============================================================================
-- PERFORMANCE IMPACT CHECK
-- ============================================================================

-- 18. Index usage verification (run EXPLAIN QUERY PLAN on common queries)
-- Example query that should use new indexes:
EXPLAIN QUERY PLAN
SELECT caption_id, caption_text, caption_type_v2, send_type_v2
FROM caption_bank
WHERE is_active = 1
  AND caption_type_v2 = 'ppv_unlock'
  AND send_type_v2 = 'mass_message'
ORDER BY freshness_score DESC, performance_score DESC
LIMIT 50;

-- ============================================================================
-- SUMMARY REPORT QUERY
-- ============================================================================

-- 19. Generate comprehensive migration summary
WITH stats AS (
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) as migrated,
        SUM(CASE WHEN caption_type_v2 IS NULL THEN 1 ELSE 0 END) as not_migrated,
        SUM(CASE WHEN is_paid_page_only = 1 THEN 1 ELSE 0 END) as paid_only,
        COUNT(DISTINCT caption_type) as old_type_count,
        COUNT(DISTINCT caption_type_v2) as new_type_count,
        COUNT(DISTINCT send_type) as old_send_count,
        COUNT(DISTINCT send_type_v2) as new_send_count
    FROM caption_bank
)
SELECT
    '=== MIGRATION SUMMARY ===' as report,
    total as total_records,
    migrated as migrated_records,
    not_migrated as unmigrated_records,
    ROUND(100.0 * migrated / total, 2) as migration_pct,
    paid_only as paid_page_only_records,
    old_type_count || ' -> ' || new_type_count as caption_type_consolidation,
    old_send_count || ' -> ' || new_send_count as send_type_consolidation
FROM stats;

-- ============================================================================
-- END OF VALIDATION QUERIES
-- ============================================================================
