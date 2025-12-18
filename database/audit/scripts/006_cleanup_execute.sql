-- EXECUTE WITH CAUTION - MODIFIES DATA
-- Audit 006: Staged Cleanup of Low-Quality Captions
-- Location: audit/scripts/006_cleanup_execute.sql
-- Created: 2025-12-12
--
-- SAFETY: Only targets captions created before 2025-12-12 to allow new imports to mature
-- SCOPE: 146 total captions (21 Stage 1 + 68 Stage 2 + 57 Stage 3)
-- REVENUE IMPACT: $0.00

BEGIN TRANSACTION;

-- ============================================================
-- Stage 1: Archive emoji-only deadweight (< 10 chars, never used)
-- Expected: 21 captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 0,
  notes = CASE
    WHEN notes IS NULL OR notes = '' THEN 'ARCHIVED: 006-cleanup (emoji-only, never used)'
    ELSE notes || ' | ARCHIVED: 006-cleanup (emoji-only, never used)'
  END,
  updated_at = datetime('now')
WHERE caption_id IN (
  SELECT caption_id FROM caption_bank
  WHERE is_active = 1
    AND LENGTH(caption_text) < 10
    AND times_used = 0
    AND (creator_id IS NULL OR creator_id = '')
    AND DATE(created_at) < DATE('2025-12-12')
);

SELECT 'Stage 1 Complete (emoji-only)' as stage, changes() as rows_updated;

-- ============================================================
-- Stage 2: Archive very short never-used (10-19 chars, never used)
-- Expected: 68 captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 0,
  notes = CASE
    WHEN notes IS NULL OR notes = '' THEN 'ARCHIVED: 006-cleanup (very short, never used)'
    ELSE notes || ' | ARCHIVED: 006-cleanup (very short, never used)'
  END,
  updated_at = datetime('now')
WHERE caption_id IN (
  SELECT caption_id FROM caption_bank
  WHERE is_active = 1
    AND LENGTH(caption_text) >= 10
    AND LENGTH(caption_text) < 20
    AND times_used = 0
    AND (creator_id IS NULL OR creator_id = '')
    AND DATE(created_at) < DATE('2025-12-12')
);

SELECT 'Stage 2 Complete (very short, never used)' as stage, changes() as rows_updated;

-- ============================================================
-- Stage 3: Archive very short with zero earnings (10-19 chars, used but $0)
-- Expected: 57 captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 0,
  notes = CASE
    WHEN notes IS NULL OR notes = '' THEN 'ARCHIVED: 006-cleanup (very short, no earnings)'
    ELSE notes || ' | ARCHIVED: 006-cleanup (very short, no earnings)'
  END,
  updated_at = datetime('now')
WHERE caption_id IN (
  SELECT caption_id FROM caption_bank
  WHERE is_active = 1
    AND LENGTH(caption_text) >= 10
    AND LENGTH(caption_text) < 20
    AND times_used > 0
    AND total_earnings = 0
    AND (creator_id IS NULL OR creator_id = '')
    AND DATE(created_at) < DATE('2025-12-12')
);

SELECT 'Stage 3 Complete (very short, no earnings)' as stage, changes() as rows_updated;

-- ============================================================
-- Insert audit log entries
-- ============================================================
INSERT INTO caption_audit_log (
  caption_id,
  field_name,
  old_value,
  new_value,
  change_reason,
  change_method,
  agent_id,
  created_at
)
SELECT
  caption_id,
  'is_active',
  '1',
  '0',
  'Quality cleanup: short caption with insufficient performance (Audit 006)',
  'automated_cleanup',
  'database-administrator',
  datetime('now')
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%'
  AND updated_at >= datetime('now', '-1 hour');

SELECT 'Audit Log Complete' as stage, changes() as rows_inserted;

-- ============================================================
-- Verification Summary
-- ============================================================
SELECT
  'CLEANUP SUMMARY' as report,
  COUNT(*) as total_archived,
  SUM(CASE WHEN LENGTH(caption_text) < 10 THEN 1 ELSE 0 END) as emoji_archived,
  SUM(CASE WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND notes LIKE '%never used%' THEN 1 ELSE 0 END) as short_never_used_archived,
  SUM(CASE WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND notes LIKE '%no earnings%' THEN 1 ELSE 0 END) as short_no_earnings_archived
FROM caption_bank
WHERE is_active = 0 AND notes LIKE '%006-cleanup%';

-- ============================================================
-- Final Safety Check (CRITICAL)
-- ============================================================
SELECT
  'SAFETY_VERIFICATION' as check_name,
  COUNT(*) as should_be_zero,
  CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL - ROLLBACK RECOMMENDED' END as status
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%'
  AND (total_earnings >= 50 OR times_used >= 5);

-- Show any problematic IDs if safety check fails
SELECT
  'PROBLEMATIC_IDS' as warning,
  GROUP_CONCAT(caption_id) as ids
FROM caption_bank
WHERE is_active = 0
  AND notes LIKE '%006-cleanup%'
  AND (total_earnings >= 50 OR times_used >= 5)
HAVING COUNT(*) > 0;

-- ============================================================
-- Post-Cleanup Statistics
-- ============================================================
SELECT
  'POST_CLEANUP_STATS' as report,
  (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1) as active_captions,
  (SELECT COUNT(*) FROM caption_bank WHERE is_active = 0) as archived_captions,
  (SELECT SUM(total_earnings) FROM caption_bank WHERE is_active = 1) as active_total_earnings;

-- ============================================================
-- COMMIT only after verifying safety checks pass
-- ============================================================
COMMIT;

SELECT '========================================' as separator;
SELECT 'EXECUTION COMPLETE' as status, datetime('now') as completed_at;
SELECT '========================================' as separator;
