-- Post-cleanup analysis with FIXED before/after comparison
-- Location: audit/queries/006_post_cleanup_analysis.sql
-- Audit: 006 Short Captions Cleanup
-- Generated: 2025-12-12

-- Fix #1 Applied: Both CTEs now filter for LENGTH < 20 to compare same population

-- =============================================================================
-- SECTION 1: Before/After Comparison (FIXED)
-- =============================================================================

WITH before_counts AS (
  SELECT
    COUNT(*) as total_before,
    SUM(CASE WHEN LENGTH(caption_text) < 10 THEN 1 ELSE 0 END) as emoji_before,
    SUM(CASE WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 THEN 1 ELSE 0 END) as very_short_before
  FROM caption_bank_snapshot_006
),
after_counts AS (
  SELECT
    COUNT(*) as total_after,
    SUM(CASE WHEN LENGTH(caption_text) < 10 THEN 1 ELSE 0 END) as emoji_after,
    SUM(CASE WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 THEN 1 ELSE 0 END) as very_short_after
  FROM caption_bank
  WHERE is_active = 1
    AND LENGTH(caption_text) < 20  -- FIX: Match snapshot population
)
SELECT
  'BEFORE/AFTER COMPARISON' as report_section,
  b.total_before as short_captions_before,
  a.total_after as short_captions_after,
  (b.total_before - a.total_after) as archived_count,
  ROUND((b.total_before - a.total_after) * 100.0 / b.total_before, 2) as pct_archived,
  b.emoji_before,
  a.emoji_after,
  (b.emoji_before - a.emoji_after) as emoji_archived,
  b.very_short_before,
  a.very_short_after,
  (b.very_short_before - a.very_short_after) as very_short_archived
FROM before_counts b, after_counts a;

-- =============================================================================
-- SECTION 2: Validation Queries
-- =============================================================================

-- 1. Verify no high-performers archived
SELECT
  'HIGH_PERFORMER_CHECK' as check_name,
  COUNT(*) as should_be_zero
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%'
  AND (total_earnings >= 50 OR times_used >= 5);

-- 2. Verify reasonable archive count
SELECT
  'ARCHIVE_COUNT' as check_name,
  COUNT(*) as total_archived
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%';

-- 3. Verify quality score maintained
SELECT
  'QUALITY_METRICS' as check_name,
  ROUND(AVG(performance_score), 2) as avg_performance,
  COUNT(*) as active_count,
  ROUND(AVG(LENGTH(caption_text)), 1) as avg_length
FROM caption_bank
WHERE is_active = 1;

-- 4. Verify audit log entries
SELECT
  'AUDIT_LOG' as check_name,
  COUNT(*) as audit_entries
FROM caption_audit_log
WHERE change_reason LIKE '%Audit 006%';

-- 5. Verify snapshot integrity
SELECT
  'SNAPSHOT_INTEGRITY' as check_name,
  COUNT(*) as snapshot_rows
FROM caption_bank_snapshot_006;

-- =============================================================================
-- SECTION 3: Additional Analytics
-- =============================================================================

-- Breakdown of what was archived by category
SELECT
  'ARCHIVED_BREAKDOWN' as report_section,
  CASE
    WHEN LENGTH(caption_text) < 10 THEN 'Emoji-only (<10 chars)'
    WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 THEN 'Very Short (10-19 chars)'
    ELSE 'Other'
  END as category,
  COUNT(*) as count,
  COALESCE(SUM(total_earnings), 0) as total_revenue_lost
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%'
GROUP BY
  CASE
    WHEN LENGTH(caption_text) < 10 THEN 'Emoji-only (<10 chars)'
    WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 THEN 'Very Short (10-19 chars)'
    ELSE 'Other'
  END
ORDER BY count DESC;

-- Remaining short captions (preserved due to performance)
SELECT
  'PRESERVED_SHORT_CAPTIONS' as report_section,
  COUNT(*) as preserved_count,
  SUM(CASE WHEN total_earnings >= 50 THEN 1 ELSE 0 END) as high_earners,
  SUM(CASE WHEN times_used >= 5 THEN 1 ELSE 0 END) as frequently_used,
  ROUND(SUM(total_earnings), 2) as total_preserved_revenue
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20;
