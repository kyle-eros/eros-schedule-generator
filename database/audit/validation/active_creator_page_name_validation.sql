-- ============================================================================
-- ACTIVE CREATOR PAGE_NAME VALIDATION SCRIPT
-- ============================================================================
-- Purpose: Comprehensive validation of page_name data integrity for active
--          creators in the mass_messages table. Detects fragmentation,
--          inconsistencies, and data quality issues.
--
-- Database: SQLite (eros_sd_main.db)
-- Target: 37 active creators (13 paid, 24 free)
-- Expected Result: All validations should pass (0 issues detected)
-- ============================================================================

.mode column
.headers on

-- ============================================================================
-- SECTION 1: PRIMARY FRAGMENTATION CHECK
-- ============================================================================
-- Detects active creators with multiple distinct page_name values in mass_messages.
-- Expected: 0 rows (no fragmentation)
-- Critical: Any results indicate data integrity violation requiring immediate fix

SELECT
    '=== PRIMARY FRAGMENTATION CHECK ===' AS validation_section;

SELECT
    mm.creator_id,
    c.page_name AS canonical_page_name,
    COUNT(DISTINCT mm.page_name) AS distinct_page_names,
    GROUP_CONCAT(DISTINCT mm.page_name, ' | ') AS page_name_variants,
    COUNT(*) AS total_messages,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
GROUP BY mm.creator_id, c.page_name
HAVING COUNT(DISTINCT mm.page_name) > 1
ORDER BY distinct_page_names DESC, total_messages DESC;

-- Result interpretation:
-- 0 rows = PASS: No fragmentation detected
-- >0 rows = FAIL: Fragmentation exists, manual remediation required

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✓ PASS: No fragmentation detected'
        ELSE '✗ FAIL: ' || COUNT(*) || ' creator(s) have fragmented page_names'
    END AS section_1_result
FROM (
    SELECT mm.creator_id
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
    GROUP BY mm.creator_id
    HAVING COUNT(DISTINCT mm.page_name) > 1
);

-- ============================================================================
-- SECTION 2: CASE SENSITIVITY VALIDATION
-- ============================================================================
-- Checks for case variations of page_names for the same creator_id
-- (e.g., "alexia" vs "Alexia" vs "ALEXIA")
-- Expected: 0 rows (all page_names use consistent casing)

SELECT
    '' AS separator,
    '=== CASE SENSITIVITY VALIDATION ===' AS validation_section;

SELECT
    mm.creator_id,
    c.page_name AS canonical_page_name,
    mm.page_name AS mass_message_page_name,
    COUNT(*) AS message_count,
    CASE
        WHEN mm.page_name = c.page_name THEN 'EXACT_MATCH'
        WHEN LOWER(mm.page_name) = LOWER(c.page_name) THEN 'CASE_MISMATCH'
        ELSE 'DIFFERENT_NAME'
    END AS match_type
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name IS NOT NULL
  AND LOWER(mm.page_name) = LOWER(c.page_name)
  AND mm.page_name != c.page_name  -- Case differs
GROUP BY mm.creator_id, c.page_name, mm.page_name
ORDER BY message_count DESC;

-- Result interpretation:
-- 0 rows = PASS: All page_names use consistent casing
-- >0 rows = WARNING: Case inconsistencies exist (may not affect functionality)

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✓ PASS: No case sensitivity issues detected'
        ELSE '⚠ WARNING: ' || COUNT(*) || ' case variant(s) found'
    END AS section_2_result
FROM (
    SELECT mm.creator_id, mm.page_name
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
      AND mm.page_name IS NOT NULL
      AND LOWER(mm.page_name) = LOWER(c.page_name)
      AND mm.page_name != c.page_name
    GROUP BY mm.creator_id, mm.page_name
);

-- ============================================================================
-- SECTION 3: CANONICAL NAME CONSISTENCY
-- ============================================================================
-- Verifies that mass_messages.page_name matches creators.page_name exactly
-- when creator_id is populated (foreign key integrity).
-- Expected: 0 inconsistencies

SELECT
    '' AS separator,
    '=== CANONICAL NAME CONSISTENCY ===' AS validation_section;

SELECT
    mm.creator_id,
    c.page_name AS canonical_page_name,
    mm.page_name AS mass_message_page_name,
    COUNT(*) AS inconsistent_message_count,
    ROUND(COUNT(*) * 100.0 / (
        SELECT COUNT(*)
        FROM mass_messages mm2
        WHERE mm2.creator_id = mm.creator_id
    ), 2) AS pct_of_creator_messages
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name != c.page_name  -- Name doesn't match canonical
GROUP BY mm.creator_id, c.page_name, mm.page_name
ORDER BY inconsistent_message_count DESC;

-- Result interpretation:
-- 0 rows = PASS: All page_names match canonical values
-- >0 rows = FAIL: Data integrity violation, requires normalization

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✓ PASS: All page_names match canonical values'
        ELSE '✗ FAIL: ' || SUM(message_count) || ' message(s) have non-canonical page_names'
    END AS section_3_result
FROM (
    SELECT COUNT(*) AS message_count
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
      AND mm.page_name != c.page_name
);

-- ============================================================================
-- SECTION 4: NULL PAGE_NAME CHECK
-- ============================================================================
-- Ensures no mass_messages records for active creators have NULL page_name
-- Expected: 0 rows (all messages have page_name populated)

SELECT
    '' AS separator,
    '=== NULL PAGE_NAME CHECK ===' AS validation_section;

SELECT
    mm.creator_id,
    c.page_name AS canonical_page_name,
    COUNT(*) AS null_page_name_count,
    ROUND(COUNT(*) * 100.0 / (
        SELECT COUNT(*)
        FROM mass_messages mm2
        WHERE mm2.creator_id = mm.creator_id
    ), 2) AS pct_of_creator_messages
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name IS NULL
GROUP BY mm.creator_id, c.page_name
ORDER BY null_page_name_count DESC;

-- Result interpretation:
-- 0 rows = PASS: All messages have page_name populated
-- >0 rows = FAIL: NULL values detected, data completeness issue

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✓ PASS: No NULL page_names detected'
        ELSE '✗ FAIL: ' || COUNT(*) || ' message(s) have NULL page_name'
    END AS section_4_result
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name IS NULL;

-- ============================================================================
-- SECTION 5: COVERAGE ANALYSIS
-- ============================================================================
-- Calculates percentage of mass_messages with proper creator_id linkage
-- Expected: 100% coverage for active creators

SELECT
    '' AS separator,
    '=== COVERAGE ANALYSIS ===' AS validation_section;

SELECT
    c.creator_id,
    c.page_name,
    c.page_type,
    COUNT(DISTINCT mm.message_id) AS total_messages,
    COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) AS messages_with_creator_id,
    COUNT(DISTINCT CASE WHEN mm.creator_id IS NULL THEN mm.message_id END) AS messages_without_creator_id,
    ROUND(
        COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
        COUNT(DISTINCT mm.message_id),
        2
    ) AS coverage_pct,
    CASE
        WHEN COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
             COUNT(DISTINCT mm.message_id) = 100 THEN 'PERFECT'
        WHEN COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
             COUNT(DISTINCT mm.message_id) >= 95 THEN 'EXCELLENT'
        WHEN COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
             COUNT(DISTINCT mm.message_id) >= 80 THEN 'GOOD'
        ELSE 'NEEDS_IMPROVEMENT'
    END AS coverage_grade
FROM creators c
LEFT JOIN mass_messages mm ON c.page_name = mm.page_name
WHERE c.is_active = 1
GROUP BY c.creator_id, c.page_name, c.page_type
ORDER BY coverage_pct ASC, total_messages DESC;

-- Overall coverage summary
SELECT
    COUNT(DISTINCT c.creator_id) AS total_active_creators,
    SUM(CASE WHEN coverage_pct = 100 THEN 1 ELSE 0 END) AS perfect_coverage_count,
    SUM(CASE WHEN coverage_pct >= 95 THEN 1 ELSE 0 END) AS excellent_coverage_count,
    SUM(CASE WHEN coverage_pct < 95 THEN 1 ELSE 0 END) AS needs_improvement_count,
    ROUND(AVG(coverage_pct), 2) AS avg_coverage_pct
FROM (
    SELECT
        c.creator_id,
        ROUND(
            COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
            COUNT(DISTINCT mm.message_id),
            2
        ) AS coverage_pct
    FROM creators c
    LEFT JOIN mass_messages mm ON c.page_name = mm.page_name
    WHERE c.is_active = 1
    GROUP BY c.creator_id
);

SELECT
    CASE
        WHEN AVG(coverage_pct) = 100 THEN '✓ PASS: Perfect coverage across all active creators'
        WHEN AVG(coverage_pct) >= 95 THEN '⚠ WARNING: Average coverage ' || ROUND(AVG(coverage_pct), 2) || '%'
        ELSE '✗ FAIL: Poor coverage ' || ROUND(AVG(coverage_pct), 2) || '%'
    END AS section_5_result
FROM (
    SELECT
        ROUND(
            COUNT(DISTINCT CASE WHEN mm.creator_id IS NOT NULL THEN mm.message_id END) * 100.0 /
            COUNT(DISTINCT mm.message_id),
            2
        ) AS coverage_pct
    FROM creators c
    LEFT JOIN mass_messages mm ON c.page_name = mm.page_name
    WHERE c.is_active = 1
    GROUP BY c.creator_id
);

-- ============================================================================
-- SECTION 6: SUFFIX PATTERN ANALYSIS
-- ============================================================================
-- Detects unintended suffix variations (e.g., base name with _paid, _free, _vip)
-- under the same creator_id
-- Expected: 0 suffix variations (clean base names only)

SELECT
    '' AS separator,
    '=== SUFFIX PATTERN ANALYSIS ===' AS validation_section;

WITH suffix_patterns AS (
    SELECT
        mm.creator_id,
        c.page_name AS canonical_page_name,
        mm.page_name,
        COUNT(*) AS message_count,
        CASE
            -- Common suffix patterns
            WHEN mm.page_name LIKE '%\_paid' ESCAPE '\' THEN '_paid'
            WHEN mm.page_name LIKE '%\_free' ESCAPE '\' THEN '_free'
            WHEN mm.page_name LIKE '%\_vip' ESCAPE '\' THEN '_vip'
            WHEN mm.page_name LIKE '%\_premium' ESCAPE '\' THEN '_premium'
            WHEN mm.page_name LIKE '%\_trial' ESCAPE '\' THEN '_trial'
            WHEN mm.page_name LIKE '%\_promo' ESCAPE '\' THEN '_promo'
            WHEN mm.page_name LIKE '%\_1' ESCAPE '\' THEN '_numeric'
            WHEN mm.page_name LIKE '%\_2' ESCAPE '\' THEN '_numeric'
            ELSE NULL
        END AS detected_suffix
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
      AND mm.page_name IS NOT NULL
    GROUP BY mm.creator_id, c.page_name, mm.page_name
)
SELECT
    creator_id,
    canonical_page_name,
    page_name AS variant_with_suffix,
    detected_suffix,
    message_count,
    ROUND(message_count * 100.0 / SUM(message_count) OVER (PARTITION BY creator_id), 2) AS pct_of_creator
FROM suffix_patterns
WHERE detected_suffix IS NOT NULL
ORDER BY creator_id, message_count DESC;

-- Result interpretation:
-- 0 rows = PASS: No suffix variations detected
-- >0 rows = WARNING: Suffix patterns found, may indicate naming inconsistency

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✓ PASS: No suffix variations detected'
        ELSE '⚠ WARNING: ' || COUNT(*) || ' suffix variant(s) found'
    END AS section_6_result
FROM (
    SELECT mm.page_name
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
      AND mm.page_name IS NOT NULL
      AND (
          mm.page_name LIKE '%\_paid' ESCAPE '\' OR
          mm.page_name LIKE '%\_free' ESCAPE '\' OR
          mm.page_name LIKE '%\_vip' ESCAPE '\' OR
          mm.page_name LIKE '%\_premium' ESCAPE '\' OR
          mm.page_name LIKE '%\_trial' ESCAPE '\' OR
          mm.page_name LIKE '%\_promo' ESCAPE '\' OR
          mm.page_name LIKE '%\_1' ESCAPE '\' OR
          mm.page_name LIKE '%\_2' ESCAPE '\'
      )
    GROUP BY mm.creator_id, mm.page_name
);

-- ============================================================================
-- SECTION 7: EXECUTIVE SUMMARY
-- ============================================================================
-- Single comprehensive query showing overall data quality status

SELECT
    '' AS separator,
    '=== EXECUTIVE SUMMARY ===' AS validation_section;

WITH active_creator_stats AS (
    SELECT
        COUNT(DISTINCT c.creator_id) AS total_active_creators,
        COUNT(DISTINCT CASE
            WHEN fragmentation_check.is_fragmented = 0
             AND consistency_check.has_inconsistency = 0
             AND null_check.has_nulls = 0
            THEN c.creator_id
        END) AS creators_with_clean_data,
        COUNT(DISTINCT CASE
            WHEN fragmentation_check.is_fragmented = 1
            THEN c.creator_id
        END) AS creators_with_fragmentation,
        COUNT(DISTINCT CASE
            WHEN consistency_check.has_inconsistency = 1
            THEN c.creator_id
        END) AS creators_with_inconsistency,
        COUNT(DISTINCT CASE
            WHEN null_check.has_nulls = 1
            THEN c.creator_id
        END) AS creators_with_nulls
    FROM creators c
    LEFT JOIN (
        -- Fragmentation check
        SELECT
            creator_id,
            CASE WHEN COUNT(DISTINCT page_name) > 1 THEN 1 ELSE 0 END AS is_fragmented
        FROM mass_messages
        GROUP BY creator_id
    ) fragmentation_check ON c.creator_id = fragmentation_check.creator_id
    LEFT JOIN (
        -- Consistency check
        SELECT
            mm.creator_id,
            MAX(CASE WHEN mm.page_name != c2.page_name THEN 1 ELSE 0 END) AS has_inconsistency
        FROM mass_messages mm
        INNER JOIN creators c2 ON mm.creator_id = c2.creator_id
        GROUP BY mm.creator_id
    ) consistency_check ON c.creator_id = consistency_check.creator_id
    LEFT JOIN (
        -- NULL check
        SELECT
            creator_id,
            MAX(CASE WHEN page_name IS NULL THEN 1 ELSE 0 END) AS has_nulls
        FROM mass_messages
        GROUP BY creator_id
    ) null_check ON c.creator_id = null_check.creator_id
    WHERE c.is_active = 1
)
SELECT
    datetime('now') AS validation_timestamp,
    total_active_creators,
    creators_with_clean_data,
    creators_with_fragmentation,
    creators_with_inconsistency,
    creators_with_nulls,
    ROUND(creators_with_clean_data * 100.0 / total_active_creators, 2) AS clean_data_pct,
    CASE
        WHEN creators_with_clean_data = total_active_creators THEN 'PASS ✓'
        ELSE 'FAIL ✗'
    END AS overall_status,
    CASE
        WHEN creators_with_clean_data = total_active_creators THEN 'A+'
        WHEN creators_with_clean_data >= total_active_creators * 0.95 THEN 'A'
        WHEN creators_with_clean_data >= total_active_creators * 0.90 THEN 'B'
        WHEN creators_with_clean_data >= total_active_creators * 0.80 THEN 'C'
        WHEN creators_with_clean_data >= total_active_creators * 0.70 THEN 'D'
        ELSE 'F'
    END AS data_quality_grade
FROM active_creator_stats;

-- Detailed breakdown by issue type
SELECT
    '' AS separator,
    'Issue Breakdown:' AS section;

SELECT
    'Fragmentation Issues' AS issue_type,
    COUNT(*) AS affected_creators,
    SUM(message_count) AS affected_messages
FROM (
    SELECT mm.creator_id, COUNT(*) AS message_count
    FROM mass_messages mm
    INNER JOIN creators c ON mm.creator_id = c.creator_id
    WHERE c.is_active = 1
    GROUP BY mm.creator_id
    HAVING COUNT(DISTINCT mm.page_name) > 1
)
UNION ALL
SELECT
    'Consistency Issues' AS issue_type,
    COUNT(DISTINCT mm.creator_id) AS affected_creators,
    COUNT(*) AS affected_messages
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name != c.page_name
UNION ALL
SELECT
    'NULL Page Names' AS issue_type,
    COUNT(DISTINCT mm.creator_id) AS affected_creators,
    COUNT(*) AS affected_messages
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name IS NULL
UNION ALL
SELECT
    'Case Sensitivity' AS issue_type,
    COUNT(DISTINCT mm.creator_id) AS affected_creators,
    COUNT(*) AS affected_messages
FROM mass_messages mm
INNER JOIN creators c ON mm.creator_id = c.creator_id
WHERE c.is_active = 1
  AND mm.page_name IS NOT NULL
  AND LOWER(mm.page_name) = LOWER(c.page_name)
  AND mm.page_name != c.page_name;

-- ============================================================================
-- VALIDATION COMPLETE
-- ============================================================================
-- Review all sections above. Expected results for a clean database:
-- - Section 1: 0 fragmentation issues (PASS)
-- - Section 2: 0 case sensitivity issues (PASS)
-- - Section 3: 0 consistency issues (PASS)
-- - Section 4: 0 NULL page_names (PASS)
-- - Section 5: 100% coverage (PASS)
-- - Section 6: 0 suffix variations (PASS)
-- - Section 7: Grade A+, PASS status
-- ============================================================================
