-- DRY RUN: Preview captions to be archived
-- Audit 006: Staged Cleanup of Low-Quality Captions
-- DO NOT EXECUTE UPDATE - REVIEW ONLY
-- Created: 2025-12-12

-- ============================================================
-- Stage 1: Emoji-only deadweight (never used, < 10 chars)
-- ============================================================
SELECT
  'STAGE_1_EMOJI_DEADWEIGHT' as stage,
  COUNT(*) as affected_count
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 10
  AND times_used = 0
  AND (creator_id IS NULL OR creator_id = '');

-- Preview Stage 1 records
SELECT
  caption_id,
  caption_text,
  LENGTH(caption_text) as char_count,
  times_used,
  total_earnings,
  created_at
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 10
  AND times_used = 0
  AND (creator_id IS NULL OR creator_id = '');

-- ============================================================
-- Stage 2: Very short with zero usage (10-19 chars, never used)
-- ============================================================
SELECT
  'STAGE_2_VERY_SHORT_NEVER_USED' as stage,
  COUNT(*) as affected_count
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 10
  AND LENGTH(caption_text) < 20
  AND times_used = 0
  AND (creator_id IS NULL OR creator_id = '');

-- Preview Stage 2 records (sample up to 20)
SELECT
  caption_id,
  caption_text,
  LENGTH(caption_text) as char_count,
  times_used,
  total_earnings,
  created_at
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 10
  AND LENGTH(caption_text) < 20
  AND times_used = 0
  AND (creator_id IS NULL OR creator_id = '')
LIMIT 20;

-- ============================================================
-- Stage 3: Very short with usage but zero earnings
-- ============================================================
SELECT
  'STAGE_3_VERY_SHORT_NO_EARNINGS' as stage,
  COUNT(*) as affected_count
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 10
  AND LENGTH(caption_text) < 20
  AND times_used > 0
  AND total_earnings = 0
  AND (creator_id IS NULL OR creator_id = '');

-- Preview Stage 3 records (sample up to 20)
SELECT
  caption_id,
  caption_text,
  LENGTH(caption_text) as char_count,
  times_used,
  total_earnings,
  created_at
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 10
  AND LENGTH(caption_text) < 20
  AND times_used > 0
  AND total_earnings = 0
  AND (creator_id IS NULL OR creator_id = '')
LIMIT 20;

-- ============================================================
-- TOTAL cleanup count (all stages combined)
-- ============================================================
SELECT
  'TOTAL_CLEANUP_CANDIDATES' as summary,
  (
    SELECT COUNT(*) FROM caption_bank
    WHERE is_active = 1 AND LENGTH(caption_text) < 10 AND times_used = 0 AND (creator_id IS NULL OR creator_id = '')
  ) + (
    SELECT COUNT(*) FROM caption_bank
    WHERE is_active = 1 AND LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND times_used = 0 AND (creator_id IS NULL OR creator_id = '')
  ) + (
    SELECT COUNT(*) FROM caption_bank
    WHERE is_active = 1 AND LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND times_used > 0 AND total_earnings = 0 AND (creator_id IS NULL OR creator_id = '')
  ) as total_count;

-- ============================================================
-- SAFETY CHECK: Ensure no high-performers are affected
-- ============================================================
SELECT
  'SAFETY_CHECK_HIGH_PERFORMERS' as check_name,
  COUNT(*) as should_be_zero
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20
  AND (
    times_used = 0
    OR (times_used > 0 AND total_earnings = 0)
  )
  AND (creator_id IS NULL OR creator_id = '')
  AND (
    total_earnings >= 50
    OR (times_used >= 5 AND performance_score >= 60)
    OR (times_used > 0 AND total_earnings / times_used >= 30)
  );

-- ============================================================
-- Additional Safety Checks
-- ============================================================

-- Check if any candidates have creator assignments
SELECT
  'SAFETY_CHECK_CREATOR_ASSIGNED' as check_name,
  COUNT(*) as should_be_zero
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20
  AND (times_used = 0 OR (times_used > 0 AND total_earnings = 0))
  AND creator_id IS NOT NULL
  AND creator_id != '';

-- Check revenue at risk (should be $0.00)
SELECT
  'REVENUE_AT_RISK' as check_name,
  COALESCE(SUM(total_earnings), 0) as total_earnings_at_risk
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20
  AND (times_used = 0 OR (times_used > 0 AND total_earnings = 0))
  AND (creator_id IS NULL OR creator_id = '');

-- Breakdown by character length
SELECT
  'LENGTH_DISTRIBUTION' as report,
  CASE
    WHEN LENGTH(caption_text) < 5 THEN '< 5 chars'
    WHEN LENGTH(caption_text) < 10 THEN '5-9 chars'
    WHEN LENGTH(caption_text) < 15 THEN '10-14 chars'
    WHEN LENGTH(caption_text) < 20 THEN '15-19 chars'
  END as length_bucket,
  COUNT(*) as count
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20
  AND (times_used = 0 OR (times_used > 0 AND total_earnings = 0))
  AND (creator_id IS NULL OR creator_id = '')
GROUP BY length_bucket
ORDER BY length_bucket;

-- ============================================================
-- Summary Table
-- ============================================================
SELECT '========================================' as separator;
SELECT 'DRY RUN SUMMARY' as report_name, datetime('now') as run_time;
SELECT '========================================' as separator;
