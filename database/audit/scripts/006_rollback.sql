-- ROLLBACK SCRIPT: Restore archived captions from Audit 006
-- Location: audit/scripts/006_rollback.sql
-- Created: 2025-12-12
--
-- USE ONLY IF: Cleanup caused unexpected issues or data needs restoration
-- SCOPE: Reverses all 3 stages of cleanup (146 captions expected)

BEGIN TRANSACTION;

-- ============================================================
-- Pre-Rollback Status
-- ============================================================
SELECT
  'PRE_ROLLBACK_STATUS' as report,
  COUNT(*) as captions_to_restore
FROM caption_bank
WHERE is_active = 0 AND notes LIKE '%006-cleanup%';

-- ============================================================
-- Stage 1 Rollback: Restore emoji-only captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 1,
  notes = REPLACE(notes, 'ARCHIVED: 006-cleanup (emoji-only, never used)', 'RESTORED: 006-rollback'),
  updated_at = datetime('now')
WHERE is_active = 0 AND notes LIKE '%006-cleanup (emoji-only%';

SELECT 'Stage 1 Rollback Complete' as stage, changes() as rows_restored;

-- ============================================================
-- Stage 2 Rollback: Restore very short never-used captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 1,
  notes = REPLACE(notes, 'ARCHIVED: 006-cleanup (very short, never used)', 'RESTORED: 006-rollback'),
  updated_at = datetime('now')
WHERE is_active = 0 AND notes LIKE '%006-cleanup (very short, never used)%';

SELECT 'Stage 2 Rollback Complete' as stage, changes() as rows_restored;

-- ============================================================
-- Stage 3 Rollback: Restore very short no-earnings captions
-- ============================================================
UPDATE caption_bank
SET
  is_active = 1,
  notes = REPLACE(notes, 'ARCHIVED: 006-cleanup (very short, no earnings)', 'RESTORED: 006-rollback'),
  updated_at = datetime('now')
WHERE is_active = 0 AND notes LIKE '%006-cleanup (very short, no earnings)%';

SELECT 'Stage 3 Rollback Complete' as stage, changes() as rows_restored;

-- ============================================================
-- Insert rollback audit entries
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
  '0',
  '1',
  'Rollback of Audit 006 cleanup',
  'manual_rollback',
  'database-administrator',
  datetime('now')
FROM caption_bank
WHERE is_active = 1 AND notes LIKE '%006-rollback%';

SELECT 'Rollback Audit Log Complete' as stage, changes() as rows_inserted;

-- ============================================================
-- Verification Summary
-- ============================================================
SELECT
  'ROLLBACK COMPLETE' as status,
  COUNT(*) as captions_restored
FROM caption_bank
WHERE is_active = 1 AND notes LIKE '%006-rollback%';

-- Confirm no 006-cleanup records remain archived
SELECT
  'REMAINING_ARCHIVED' as check_name,
  COUNT(*) as should_be_zero,
  CASE WHEN COUNT(*) = 0 THEN 'PASS - All restored' ELSE 'PARTIAL - Some not restored' END as status
FROM caption_bank
WHERE is_active = 0 AND notes LIKE '%006-cleanup%';

-- ============================================================
-- Post-Rollback Statistics
-- ============================================================
SELECT
  'POST_ROLLBACK_STATS' as report,
  (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1) as active_captions,
  (SELECT COUNT(*) FROM caption_bank WHERE is_active = 0) as archived_captions;

COMMIT;

SELECT '========================================' as separator;
SELECT 'ROLLBACK COMPLETE' as status, datetime('now') as completed_at;
SELECT '========================================' as separator;
