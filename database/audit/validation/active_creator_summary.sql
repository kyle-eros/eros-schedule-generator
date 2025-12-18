-- ============================================================================
-- ACTIVE CREATOR PAGE_NAME VALIDATION - EXECUTIVE SUMMARY
-- ============================================================================
-- Purpose: Fast single-query validation to answer "Are all active creators clean?"
-- Execution Time: <1 second
-- Expected Result: PASS status with 37/37 clean creators
-- ============================================================================

.mode column
.headers on
.width 30 15 15 10

-- ============================================================================
-- QUICK STATUS CHECK
-- ============================================================================

SELECT '=== ACTIVE CREATOR PAGE_NAME VALIDATION SUMMARY ===' AS report_header;
SELECT datetime('now') AS validation_timestamp;

-- Main validation summary
WITH validation_metrics AS (
    SELECT
        c.creator_id,
        c.page_name AS canonical_name,
        c.page_type,
        -- Fragmentation check
        (
            SELECT COUNT(DISTINCT mm1.page_name)
            FROM mass_messages mm1
            WHERE mm1.creator_id = c.creator_id
        ) AS distinct_page_names,
        -- Consistency check
        (
            SELECT COUNT(*)
            FROM mass_messages mm2
            WHERE mm2.creator_id = c.creator_id
              AND mm2.page_name != c.page_name
        ) AS inconsistent_messages,
        -- NULL check
        (
            SELECT COUNT(*)
            FROM mass_messages mm3
            WHERE mm3.creator_id = c.creator_id
              AND mm3.page_name IS NULL
        ) AS null_page_names,
        -- Total messages
        (
            SELECT COUNT(*)
            FROM mass_messages mm4
            WHERE mm4.creator_id = c.creator_id
        ) AS total_messages
    FROM creators c
    WHERE c.is_active = 1
),
summary_stats AS (
    SELECT
        COUNT(*) AS total_active_creators,
        SUM(CASE
            WHEN distinct_page_names = 1
             AND inconsistent_messages = 0
             AND null_page_names = 0
            THEN 1
            ELSE 0
        END) AS creators_with_perfect_mapping,
        SUM(CASE WHEN distinct_page_names > 1 THEN 1 ELSE 0 END) AS creators_with_fragmentation,
        SUM(CASE WHEN inconsistent_messages > 0 THEN 1 ELSE 0 END) AS creators_with_inconsistency,
        SUM(CASE WHEN null_page_names > 0 THEN 1 ELSE 0 END) AS creators_with_nulls,
        SUM(total_messages) AS total_messages_analyzed
    FROM validation_metrics
)
SELECT
    total_active_creators,
    creators_with_perfect_mapping AS clean_creators,
    creators_with_fragmentation AS fragmented_creators,
    creators_with_inconsistency AS inconsistent_creators,
    creators_with_nulls AS creators_with_null_names,
    total_messages_analyzed,
    CASE
        WHEN creators_with_perfect_mapping = total_active_creators THEN 'PASS ✓'
        ELSE 'FAIL ✗'
    END AS overall_status,
    ROUND(creators_with_perfect_mapping * 100.0 / total_active_creators, 1) || '%' AS clean_pct,
    CASE
        WHEN creators_with_perfect_mapping = total_active_creators THEN 'A+'
        WHEN creators_with_perfect_mapping >= total_active_creators * 0.95 THEN 'A'
        WHEN creators_with_perfect_mapping >= total_active_creators * 0.90 THEN 'B'
        WHEN creators_with_perfect_mapping >= total_active_creators * 0.80 THEN 'C'
        ELSE 'F'
    END AS data_quality_grade
FROM summary_stats;

-- ============================================================================
-- QUICK METRICS TABLE
-- ============================================================================

SELECT '' AS separator;
SELECT '=== QUICK METRICS ===' AS metrics_header;

WITH validation_metrics AS (
    SELECT
        c.creator_id,
        c.page_name,
        c.page_type,
        (SELECT COUNT(DISTINCT mm1.page_name) FROM mass_messages mm1 WHERE mm1.creator_id = c.creator_id) AS distinct_names,
        (SELECT COUNT(*) FROM mass_messages mm2 WHERE mm2.creator_id = c.creator_id AND mm2.page_name != c.page_name) AS inconsistent,
        (SELECT COUNT(*) FROM mass_messages mm3 WHERE mm3.creator_id = c.creator_id AND mm3.page_name IS NULL) AS nulls,
        (SELECT COUNT(*) FROM mass_messages mm4 WHERE mm4.creator_id = c.creator_id) AS total_msgs
    FROM creators c
    WHERE c.is_active = 1
)
SELECT
    'Total Active Creators' AS metric,
    COUNT(*) AS value,
    '—' AS status
FROM validation_metrics
UNION ALL
SELECT
    'Creators with 1:1 Mapping' AS metric,
    SUM(CASE WHEN distinct_names = 1 AND inconsistent = 0 AND nulls = 0 THEN 1 ELSE 0 END) AS value,
    CASE
        WHEN SUM(CASE WHEN distinct_names = 1 AND inconsistent = 0 AND nulls = 0 THEN 1 ELSE 0 END) = COUNT(*)
        THEN '✓ PERFECT'
        ELSE '✗ ISSUES'
    END AS status
FROM validation_metrics
UNION ALL
SELECT
    'Fragmentation Issues' AS metric,
    SUM(CASE WHEN distinct_names > 1 THEN 1 ELSE 0 END) AS value,
    CASE
        WHEN SUM(CASE WHEN distinct_names > 1 THEN 1 ELSE 0 END) = 0
        THEN '✓ CLEAN'
        ELSE '✗ FOUND'
    END AS status
FROM validation_metrics
UNION ALL
SELECT
    'Consistency Issues' AS metric,
    SUM(CASE WHEN inconsistent > 0 THEN 1 ELSE 0 END) AS value,
    CASE
        WHEN SUM(CASE WHEN inconsistent > 0 THEN 1 ELSE 0 END) = 0
        THEN '✓ CLEAN'
        ELSE '✗ FOUND'
    END AS status
FROM validation_metrics
UNION ALL
SELECT
    'NULL Page Names' AS metric,
    SUM(CASE WHEN nulls > 0 THEN 1 ELSE 0 END) AS value,
    CASE
        WHEN SUM(CASE WHEN nulls > 0 THEN 1 ELSE 0 END) = 0
        THEN '✓ CLEAN'
        ELSE '✗ FOUND'
    END AS status
FROM validation_metrics
UNION ALL
SELECT
    'Total Messages Analyzed' AS metric,
    SUM(total_msgs) AS value,
    '—' AS status
FROM validation_metrics;

-- ============================================================================
-- ISSUE DETAIL (only shows if problems exist)
-- ============================================================================

SELECT '' AS separator;
SELECT '=== CREATORS WITH ISSUES (if any) ===' AS issues_header;

WITH validation_metrics AS (
    SELECT
        c.creator_id,
        c.page_name,
        c.page_type,
        (SELECT COUNT(DISTINCT mm1.page_name) FROM mass_messages mm1 WHERE mm1.creator_id = c.creator_id) AS distinct_names,
        (SELECT COUNT(*) FROM mass_messages mm2 WHERE mm2.creator_id = c.creator_id AND mm2.page_name != c.page_name) AS inconsistent,
        (SELECT COUNT(*) FROM mass_messages mm3 WHERE mm3.creator_id = c.creator_id AND mm3.page_name IS NULL) AS nulls,
        (SELECT COUNT(*) FROM mass_messages mm4 WHERE mm4.creator_id = c.creator_id) AS total_msgs
    FROM creators c
    WHERE c.is_active = 1
)
SELECT
    creator_id,
    page_name,
    page_type,
    distinct_names AS distinct_page_names,
    inconsistent AS inconsistent_messages,
    nulls AS null_page_names,
    total_msgs AS total_messages,
    CASE
        WHEN distinct_names > 1 THEN 'FRAGMENTED'
        WHEN inconsistent > 0 THEN 'INCONSISTENT'
        WHEN nulls > 0 THEN 'HAS_NULLS'
        ELSE 'UNKNOWN_ISSUE'
    END AS issue_type
FROM validation_metrics
WHERE distinct_names > 1
   OR inconsistent > 0
   OR nulls > 0
ORDER BY
    CASE issue_type
        WHEN 'FRAGMENTED' THEN 1
        WHEN 'INCONSISTENT' THEN 2
        WHEN 'HAS_NULLS' THEN 3
        ELSE 4
    END,
    total_msgs DESC;

-- Show message if no issues found
SELECT
    CASE
        WHEN (
            SELECT COUNT(*)
            FROM creators c
            WHERE c.is_active = 1
              AND (
                  (SELECT COUNT(DISTINCT mm1.page_name) FROM mass_messages mm1 WHERE mm1.creator_id = c.creator_id) > 1
                  OR (SELECT COUNT(*) FROM mass_messages mm2 WHERE mm2.creator_id = c.creator_id AND mm2.page_name != c.page_name) > 0
                  OR (SELECT COUNT(*) FROM mass_messages mm3 WHERE mm3.creator_id = c.creator_id AND mm3.page_name IS NULL) > 0
              )
        ) = 0
        THEN 'No issues detected - all active creators have clean page_name data ✓'
        ELSE 'Issues found above - see detailed validation script for full analysis'
    END AS result_message;

-- ============================================================================
-- FINAL STATUS
-- ============================================================================

SELECT '' AS separator;
SELECT '=== FINAL VALIDATION RESULT ===' AS final_header;

WITH validation_result AS (
    SELECT
        CASE
            WHEN (
                SELECT COUNT(*)
                FROM creators c
                WHERE c.is_active = 1
                  AND (
                      (SELECT COUNT(DISTINCT mm1.page_name) FROM mass_messages mm1 WHERE mm1.creator_id = c.creator_id) > 1
                      OR (SELECT COUNT(*) FROM mass_messages mm2 WHERE mm2.creator_id = c.creator_id AND mm2.page_name != c.page_name) > 0
                      OR (SELECT COUNT(*) FROM mass_messages mm3 WHERE mm3.creator_id = c.creator_id AND mm3.page_name IS NULL) > 0
                  )
            ) = 0
            THEN 1
            ELSE 0
        END AS is_clean
)
SELECT
    CASE is_clean
        WHEN 1 THEN 'DATABASE STATUS: CLEAN ✓'
        ELSE 'DATABASE STATUS: ISSUES DETECTED ✗'
    END AS status,
    CASE is_clean
        WHEN 1 THEN 'All 37 active creators have perfect 1:1 page_name mapping'
        ELSE 'Run active_creator_page_name_validation.sql for detailed analysis'
    END AS recommendation,
    datetime('now') AS validated_at
FROM validation_result;

-- ============================================================================
-- VALIDATION COMPLETE
-- ============================================================================
-- This summary provides an immediate yes/no answer to data quality.
-- For detailed diagnostics, run: active_creator_page_name_validation.sql
-- ============================================================================
