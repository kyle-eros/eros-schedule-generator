-- ============================================
-- ROLLBACK SCRIPT: Content Type Classification
-- Plan ID: 001-CONTENT-TYPE-CLASSIFICATION
-- Created: 2025-12-12
-- ============================================
-- This script restores caption_bank to pre-classification state
-- using the backup table created during Phase 2

-- Step 1: Verify backup exists
SELECT
    CASE
        WHEN COUNT(*) > 0 THEN 'Backup found: ' || COUNT(*) || ' rows'
        ELSE 'ERROR: No backup found!'
    END as status
FROM caption_bank_classification_backup_v2;

-- Step 2: Begin transaction for rollback
BEGIN TRANSACTION;

-- Step 3: Restore from backup (only for rows that were NULL before)
UPDATE caption_bank
SET
    content_type_id = (
        SELECT old_content_type_id
        FROM caption_bank_classification_backup_v2 b
        WHERE b.caption_id = caption_bank.caption_id
    ),
    classification_confidence = (
        SELECT old_classification_confidence
        FROM caption_bank_classification_backup_v2 b
        WHERE b.caption_id = caption_bank.caption_id
    ),
    classification_method = (
        SELECT old_classification_method
        FROM caption_bank_classification_backup_v2 b
        WHERE b.caption_id = caption_bank.caption_id
    )
WHERE caption_id IN (
    SELECT caption_id FROM caption_bank_classification_backup_v2
);

-- Step 4: Verify rollback
SELECT
    'Restored to NULL:' as metric,
    COUNT(*) as count
FROM caption_bank
WHERE content_type_id IS NULL;

-- Should show 19129 if successful

-- Commit if verification passes
COMMIT;

-- To rollback the transaction instead, use:
-- ROLLBACK;
