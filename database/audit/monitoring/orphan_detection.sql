-- =============================================================================
-- EROS Database Orphan Record Detection
-- =============================================================================
-- Purpose: Identify orphan records and broken relationships across tables
-- Author: Database Administrator Agent (DBA-003)
--
-- USAGE:
--   sqlite3 database/eros_sd_main.db < database/audits/monitoring/orphan_detection.sql
--
-- This script checks for:
--   1. Records referencing non-existent parent records (orphans)
--   2. Parent records with no child records (unused references)
--   3. Cross-table relationship integrity
-- =============================================================================

SELECT '============================================';
SELECT 'EROS Database Orphan Detection Report';
SELECT 'Generated: ' || datetime('now');
SELECT '============================================';
SELECT '';

-- =============================================================================
-- SECTION 1: Orphan creator_id References
-- =============================================================================

SELECT '--- Orphan creator_id References ---';
SELECT '';

-- mass_messages with invalid creator_id
SELECT 'mass_messages orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM mass_messages m
        WHERE m.creator_id IS NOT NULL
        AND m.creator_id NOT IN (SELECT creator_id FROM creators));

-- caption_bank with invalid creator_id
SELECT 'caption_bank orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM caption_bank c
        WHERE c.creator_id IS NOT NULL
        AND c.creator_id NOT IN (SELECT creator_id FROM creators));

-- caption_creator_performance with invalid creator_id
SELECT 'caption_creator_performance orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM caption_creator_performance ccp
        WHERE ccp.creator_id IS NOT NULL
        AND ccp.creator_id NOT IN (SELECT creator_id FROM creators));

-- wall_posts with invalid creator_id
SELECT 'wall_posts orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM wall_posts w
        WHERE w.creator_id IS NOT NULL
        AND w.creator_id NOT IN (SELECT creator_id FROM creators));

-- creator_personas with invalid creator_id
SELECT 'creator_personas orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM creator_personas cp
        WHERE cp.creator_id NOT IN (SELECT creator_id FROM creators));

-- scheduler_assignments with invalid creator_id
SELECT 'scheduler_assignments orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM scheduler_assignments sa
        WHERE sa.creator_id NOT IN (SELECT creator_id FROM creators));

-- vault_matrix with invalid creator_id
SELECT 'vault_matrix orphan creator_ids: ' ||
       (SELECT COUNT(*)
        FROM vault_matrix v
        WHERE v.creator_id NOT IN (SELECT creator_id FROM creators));

SELECT '';

-- =============================================================================
-- SECTION 2: Orphan caption_id References
-- =============================================================================

SELECT '--- Orphan caption_id References ---';
SELECT '';

-- Note: mass_messages.caption_id is TEXT (UUID) while caption_bank.caption_id is INTEGER
-- This represents a schema mismatch that prevents proper FK relationship

SELECT 'caption_creator_performance orphan caption_ids: ' ||
       (SELECT COUNT(*)
        FROM caption_creator_performance ccp
        WHERE ccp.caption_id NOT IN (SELECT caption_id FROM caption_bank));

SELECT 'caption_audit_log orphan caption_ids: ' ||
       (SELECT COUNT(*)
        FROM caption_audit_log cal
        WHERE cal.caption_id NOT IN (SELECT caption_id FROM caption_bank));

SELECT '';

-- =============================================================================
-- SECTION 3: Orphan content_type_id References
-- =============================================================================

SELECT '--- Orphan content_type_id References ---';
SELECT '';

SELECT 'caption_bank orphan content_type_ids: ' ||
       (SELECT COUNT(*)
        FROM caption_bank cb
        WHERE cb.content_type_id IS NOT NULL
        AND cb.content_type_id NOT IN (SELECT content_type_id FROM content_types));

SELECT 'mass_messages orphan content_type_ids: ' ||
       (SELECT COUNT(*)
        FROM mass_messages m
        WHERE m.content_type_id IS NOT NULL
        AND m.content_type_id NOT IN (SELECT content_type_id FROM content_types));

SELECT 'wall_posts orphan content_type_ids: ' ||
       (SELECT COUNT(*)
        FROM wall_posts w
        WHERE w.content_type_id IS NOT NULL
        AND w.content_type_id NOT IN (SELECT content_type_id FROM content_types));

SELECT '';

-- =============================================================================
-- SECTION 4: Orphan scheduler_id References
-- =============================================================================

SELECT '--- Orphan scheduler_id References ---';
SELECT '';

SELECT 'scheduler_assignments orphan scheduler_ids: ' ||
       (SELECT COUNT(*)
        FROM scheduler_assignments sa
        WHERE sa.scheduler_id NOT IN (SELECT scheduler_id FROM schedulers));

SELECT '';

-- =============================================================================
-- SECTION 5: Creators Without Related Records
-- =============================================================================

SELECT '--- Creators Missing Related Records ---';
SELECT '';

-- Creators without personas
SELECT 'Creators without persona: ';
SELECT COALESCE(
    (SELECT GROUP_CONCAT(c.page_name, ', ')
     FROM creators c
     LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
     WHERE cp.creator_id IS NULL),
    '(none)');

-- Creators without scheduler assignments
SELECT 'Creators without scheduler assignment: ';
SELECT COALESCE(
    (SELECT GROUP_CONCAT(c.page_name, ', ')
     FROM creators c
     LEFT JOIN scheduler_assignments sa ON c.creator_id = sa.creator_id
     WHERE sa.creator_id IS NULL),
    '(none)');

-- Creators without analytics summary
SELECT 'Creators without analytics summary: ';
SELECT COALESCE(
    (SELECT GROUP_CONCAT(c.page_name, ', ')
     FROM creators c
     LEFT JOIN creator_analytics_summary cas ON c.creator_id = cas.creator_id
     WHERE cas.creator_id IS NULL),
    '(none)');

-- Creators without vault_matrix entries
SELECT 'Creators without vault_matrix entries: ';
SELECT COALESCE(
    (SELECT GROUP_CONCAT(c.page_name, ', ')
     FROM creators c
     LEFT JOIN vault_matrix v ON c.creator_id = v.creator_id
     WHERE v.creator_id IS NULL),
    '(none)');

SELECT '';

-- =============================================================================
-- SECTION 6: Unmapped Page Names
-- =============================================================================

SELECT '--- Unmapped Page Names in mass_messages ---';
SELECT '';

SELECT 'Distinct unmapped page_names: ' ||
       (SELECT COUNT(DISTINCT page_name)
        FROM mass_messages
        WHERE page_name NOT IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL)
        AND page_name IS NOT NULL
        AND page_name <> 'nan');

SELECT '';
SELECT 'Top 10 unmapped page_names by record count:';

SELECT page_name || ': ' || COUNT(*) as unmapped_page_name
FROM mass_messages
WHERE page_name NOT IN (SELECT page_name FROM creators WHERE page_name IS NOT NULL)
AND page_name IS NOT NULL
AND page_name <> 'nan'
GROUP BY page_name
ORDER BY COUNT(*) DESC
LIMIT 10;

SELECT '';

-- =============================================================================
-- SECTION 7: Summary Statistics
-- =============================================================================

SELECT '============================================';
SELECT 'ORPHAN DETECTION SUMMARY';
SELECT '============================================';

SELECT 'Total orphan records detected: ' ||
(
    (SELECT COUNT(*) FROM mass_messages m WHERE m.creator_id IS NOT NULL AND m.creator_id NOT IN (SELECT creator_id FROM creators)) +
    (SELECT COUNT(*) FROM caption_bank c WHERE c.creator_id IS NOT NULL AND c.creator_id NOT IN (SELECT creator_id FROM creators)) +
    (SELECT COUNT(*) FROM caption_creator_performance ccp WHERE ccp.creator_id IS NOT NULL AND ccp.creator_id NOT IN (SELECT creator_id FROM creators)) +
    (SELECT COUNT(*) FROM caption_creator_performance ccp WHERE ccp.caption_id NOT IN (SELECT caption_id FROM caption_bank)) +
    (SELECT COUNT(*) FROM caption_bank cb WHERE cb.content_type_id IS NOT NULL AND cb.content_type_id NOT IN (SELECT content_type_id FROM content_types))
);

SELECT 'Creators with incomplete relationships: ' ||
(
    (SELECT COUNT(*) FROM creators c LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id WHERE cp.creator_id IS NULL) +
    (SELECT COUNT(*) FROM creators c LEFT JOIN scheduler_assignments sa ON c.creator_id = sa.creator_id WHERE sa.creator_id IS NULL)
);

SELECT '';
SELECT '============================================';

-- =============================================================================
-- END OF ORPHAN DETECTION
-- =============================================================================
