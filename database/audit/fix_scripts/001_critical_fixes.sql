-- =============================================================================
-- EROS Database Critical Fix Script #001
-- =============================================================================
-- Purpose: Address CRITICAL and HIGH priority data integrity issues
-- Date: 2025-12-01
-- Author: Database Administrator Agent (DBA-003)
--
-- IMPORTANT: Run these fixes in order. Each section is wrapped in a transaction
-- for atomic rollback capability.
--
-- PREREQUISITES:
--   1. Create backup: sqlite3 eros_sd_main.db ".backup eros_sd_main_backup_001.db"
--   2. Verify backup integrity
--   3. Run during low-traffic period
-- =============================================================================

-- =============================================================================
-- SECTION 1: Clean 'nan' page_names (HIGH Priority)
-- =============================================================================
-- Issue: Python pandas exported string 'nan' instead of NULL
-- Impact: 11,186 records with invalid page_name
-- Risk: LOW - Converting to NULL improves data quality
-- =============================================================================

BEGIN TRANSACTION;

-- Verify count before fix
SELECT 'BEFORE: nan page_names in mass_messages' as check_type, COUNT(*) as count
FROM mass_messages WHERE page_name = 'nan';

-- Apply fix
UPDATE mass_messages
SET page_name = NULL
WHERE page_name = 'nan';

-- Verify count after fix
SELECT 'AFTER: nan page_names in mass_messages' as check_type, COUNT(*) as count
FROM mass_messages WHERE page_name = 'nan';

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'FIX_NAN_PAGE_NAMES', 'Converted nan string to NULL in mass_messages.page_name',
       11186, datetime('now');


-- =============================================================================
-- SECTION 2: Fix Negative sent_count (HIGH Priority)
-- =============================================================================
-- Issue: 6 records have negative sent_count values
-- Impact: Analytics calculations produce invalid results
-- Risk: LOW - Negative counts are definitionally invalid
-- =============================================================================

BEGIN TRANSACTION;

-- Verify records before fix
SELECT 'BEFORE: Negative sent_count records' as check_type, COUNT(*) as count
FROM mass_messages WHERE sent_count < 0;

-- Apply fix - set negative values to 0
UPDATE mass_messages
SET sent_count = 0
WHERE sent_count < 0;

-- Verify after fix
SELECT 'AFTER: Negative sent_count records' as check_type, COUNT(*) as count
FROM mass_messages WHERE sent_count < 0;

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'FIX_NEGATIVE_SENT_COUNT', 'Set negative sent_count to 0 in mass_messages',
       6, datetime('now');


-- =============================================================================
-- SECTION 3: Fix Impossible View Rates (HIGH Priority)
-- =============================================================================
-- Issue: 60 records where viewed_count > sent_count (impossible)
-- Impact: View rate calculations exceed 100%
-- Risk: LOW - Capping to sent_count is conservative correction
-- =============================================================================

BEGIN TRANSACTION;

-- Verify records before fix
SELECT 'BEFORE: Impossible view rates' as check_type, COUNT(*) as count
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0;

-- Sample of affected records
SELECT message_id, page_name, sent_count, viewed_count,
       ROUND(100.0 * viewed_count / sent_count, 2) as invalid_view_rate
FROM mass_messages
WHERE viewed_count > sent_count AND sent_count > 0
LIMIT 5;

-- Apply fix - cap viewed_count at sent_count
UPDATE mass_messages
SET viewed_count = sent_count
WHERE viewed_count > sent_count AND sent_count > 0;

-- Verify after fix
SELECT 'AFTER: Impossible view rates' as check_type, COUNT(*) as count
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0;

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'FIX_IMPOSSIBLE_VIEW_RATES', 'Capped viewed_count at sent_count in mass_messages',
       60, datetime('now');


-- =============================================================================
-- SECTION 4: Create Missing Persona for lola_reese_new (MEDIUM Priority)
-- =============================================================================
-- Issue: Creator exists without persona record
-- Impact: Caption matching falls back to generic defaults
-- Risk: MEDIUM - Using placeholder values that should be customized
-- =============================================================================

BEGIN TRANSACTION;

-- Verify the creator exists and lacks persona
SELECT 'Creator without persona' as check_type, c.creator_id, c.page_name, c.display_name
FROM creators c
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
WHERE cp.creator_id IS NULL;

-- Insert default persona (values should be reviewed and customized)
INSERT INTO creator_personas (
    creator_id,
    primary_tone,
    secondary_tone,
    emoji_frequency,
    slang_level,
    signature_phrases,
    communication_style,
    created_at,
    updated_at
)
SELECT
    c.creator_id,
    'playful',           -- Default primary tone
    'seductive',         -- Default secondary tone
    'moderate',          -- Default emoji frequency
    'light',             -- Default slang level
    '[]',                -- Empty signature phrases (JSON array)
    'conversational',    -- Default communication style
    datetime('now'),
    datetime('now')
FROM creators c
WHERE c.page_name = 'lola_reese_new'
AND NOT EXISTS (
    SELECT 1 FROM creator_personas cp
    WHERE cp.creator_id = c.creator_id
);

-- Verify persona was created
SELECT 'Persona created' as check_type, creator_id, primary_tone, emoji_frequency
FROM creator_personas
WHERE creator_id = (SELECT creator_id FROM creators WHERE page_name = 'lola_reese_new');

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'CREATE_MISSING_PERSONA', 'Created default persona for lola_reese_new',
       1, datetime('now');


-- =============================================================================
-- SECTION 5: Create Missing Scheduler Assignment (MEDIUM Priority)
-- =============================================================================
-- Issue: Creator exists without scheduler assignment
-- Impact: Workload reporting incomplete
-- Risk: MEDIUM - Requires manual assignment to correct scheduler
-- =============================================================================

BEGIN TRANSACTION;

-- Verify the creator lacks assignment
SELECT 'Creator without assignment' as check_type, c.creator_id, c.page_name
FROM creators c
LEFT JOIN scheduler_assignments sa ON c.creator_id = sa.creator_id
WHERE sa.creator_id IS NULL;

-- Get a default scheduler (first active scheduler with capacity)
-- NOTE: This should be reviewed and assigned to appropriate scheduler
INSERT INTO scheduler_assignments (
    creator_id,
    scheduler_id,
    tier,
    status,
    notes,
    assigned_at
)
SELECT
    c.creator_id,
    (SELECT scheduler_id FROM schedulers WHERE is_active = 1 ORDER BY scheduler_id LIMIT 1),
    'bronze',            -- Default tier
    'active',            -- Active status
    'Auto-assigned by DBA-003 audit fix - review required',
    datetime('now')
FROM creators c
WHERE c.page_name = 'lola_reese_new'
AND NOT EXISTS (
    SELECT 1 FROM scheduler_assignments sa
    WHERE sa.creator_id = c.creator_id
);

-- Verify assignment was created
SELECT 'Assignment created' as check_type, sa.creator_id, sa.scheduler_id, s.scheduler_name
FROM scheduler_assignments sa
JOIN schedulers s ON sa.scheduler_id = s.scheduler_id
WHERE sa.creator_id = (SELECT creator_id FROM creators WHERE page_name = 'lola_reese_new');

COMMIT;

-- Log the change
INSERT INTO agent_execution_log (agent_id, action_type, details, records_affected, timestamp)
SELECT 'DBA-003', 'CREATE_MISSING_ASSIGNMENT', 'Created default scheduler assignment for lola_reese_new',
       1, datetime('now');


-- =============================================================================
-- VERIFICATION QUERIES - Run after all fixes
-- =============================================================================

SELECT '=== POST-FIX VERIFICATION ===' as section;

SELECT 'nan page_names remaining' as check, COUNT(*) as count
FROM mass_messages WHERE page_name = 'nan'
UNION ALL
SELECT 'Negative sent_count remaining', COUNT(*)
FROM mass_messages WHERE sent_count < 0
UNION ALL
SELECT 'Impossible view rates remaining', COUNT(*)
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0
UNION ALL
SELECT 'Creators without persona', COUNT(*)
FROM creators c LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id WHERE cp.creator_id IS NULL
UNION ALL
SELECT 'Creators without scheduler', COUNT(*)
FROM creators c LEFT JOIN scheduler_assignments sa ON c.creator_id = sa.creator_id WHERE sa.creator_id IS NULL;

-- =============================================================================
-- END OF CRITICAL FIX SCRIPT #001
-- =============================================================================
