-- =============================================================================
-- EROS Database Data Quality Score Calculator
-- =============================================================================
-- Purpose: Calculate comprehensive data quality score with detailed breakdown
-- Author: Database Administrator Agent (DBA-003)
--
-- USAGE:
--   sqlite3 database/eros_sd_main.db < database/audits/monitoring/data_quality_score.sql
--
-- SCORING METHODOLOGY:
--   - FK Enforcement (25%): 0 if disabled, 100 if enabled
--   - Creator ID Linkage (20%): % of mass_messages with creator_id
--   - Caption Freshness Validity (15%): % of active captions with valid freshness
--   - Performance Score Validity (15%): % of captions with valid performance score
--   - Creator Completeness (15%): % of creators with all required fields
--   - Logical Integrity (10%): % of records without logical errors
-- =============================================================================

SELECT '============================================';
SELECT 'EROS Database Data Quality Score Report';
SELECT 'Generated: ' || datetime('now');
SELECT '============================================';
SELECT '';

-- =============================================================================
-- Individual Quality Checks with Details
-- =============================================================================

SELECT '--- Quality Check Breakdown ---';
SELECT '';

-- Check 1: FK Enforcement
SELECT 'Check 1: Foreign Key Enforcement';
SELECT '  Status: ' || CASE (SELECT foreign_keys FROM pragma_foreign_keys())
    WHEN 1 THEN 'ENABLED (100%)'
    ELSE 'DISABLED (0%)'
END;
SELECT '  Weight: 25%';
SELECT '  Impact: Referential integrity protection';
SELECT '';

-- Check 2: Creator ID Linkage
SELECT 'Check 2: Creator ID Linkage (mass_messages)';
SELECT '  Total Records: ' || (SELECT COUNT(*) FROM mass_messages);
SELECT '  With creator_id: ' || (SELECT COUNT(*) FROM mass_messages WHERE creator_id IS NOT NULL);
SELECT '  Missing creator_id: ' || (SELECT COUNT(*) FROM mass_messages WHERE creator_id IS NULL);
SELECT '  Score: ' || ROUND(100.0 * (SELECT COUNT(*) FROM mass_messages WHERE creator_id IS NOT NULL) /
                                   (SELECT COUNT(*) FROM mass_messages), 2) || '%';
SELECT '  Weight: 20%';
SELECT '';

-- Check 3: Caption Freshness Validity
SELECT 'Check 3: Caption Freshness Score Validity';
SELECT '  Active Captions: ' || (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1);
SELECT '  Valid Freshness (0-100): ' || (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1 AND freshness_score BETWEEN 0 AND 100);
SELECT '  Invalid Freshness: ' || (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1 AND (freshness_score < 0 OR freshness_score > 100));
SELECT '  Score: ' || ROUND(100.0 * (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1 AND freshness_score BETWEEN 0 AND 100) /
                                   (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1), 2) || '%';
SELECT '  Weight: 15%';
SELECT '';

-- Check 4: Performance Score Validity
SELECT 'Check 4: Performance Score Validity';
SELECT '  Total Captions: ' || (SELECT COUNT(*) FROM caption_bank);
SELECT '  Valid Performance (0-100): ' || (SELECT COUNT(*) FROM caption_bank WHERE performance_score BETWEEN 0 AND 100);
SELECT '  Invalid Performance: ' || (SELECT COUNT(*) FROM caption_bank WHERE performance_score < 0 OR performance_score > 100);
SELECT '  Score: ' || ROUND(100.0 * (SELECT COUNT(*) FROM caption_bank WHERE performance_score BETWEEN 0 AND 100) /
                                   (SELECT COUNT(*) FROM caption_bank), 2) || '%';
SELECT '  Weight: 15%';
SELECT '';

-- Check 5: Creator Completeness
SELECT 'Check 5: Creator Data Completeness';
SELECT '  Total Creators: ' || (SELECT COUNT(*) FROM creators);
SELECT '  Complete Records: ' || (SELECT COUNT(*) FROM creators WHERE page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL);
SELECT '  Incomplete Records: ' || (SELECT COUNT(*) FROM creators WHERE page_name IS NULL OR display_name IS NULL OR page_type IS NULL);
SELECT '  Score: ' || ROUND(100.0 * (SELECT COUNT(*) FROM creators WHERE page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL) /
                                   (SELECT COUNT(*) FROM creators), 2) || '%';
SELECT '  Weight: 15%';
SELECT '';

-- Check 6: Logical Data Integrity
SELECT 'Check 6: Logical Data Integrity';
SELECT '  Total mass_messages: ' || (SELECT COUNT(*) FROM mass_messages);
SELECT '  Impossible view rates: ' || (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0);
SELECT '  Negative sent_count: ' || (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0);
SELECT '  Score: ' || ROUND(100.0 * (1.0 -
    ((SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) +
     (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)) /
    CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2) || '%';
SELECT '  Weight: 10%';
SELECT '';

-- =============================================================================
-- Overall Quality Score Calculation
-- =============================================================================

SELECT '============================================';
SELECT 'OVERALL DATA QUALITY SCORE';
SELECT '============================================';

WITH quality_metrics AS (
    -- FK Enforcement
    SELECT 'fk_enforcement' as check_name,
           CASE (SELECT foreign_keys FROM pragma_foreign_keys()) WHEN 1 THEN 100.0 ELSE 0.0 END as score,
           25 as weight

    UNION ALL
    -- Creator ID Linkage
    SELECT 'creator_id_linkage',
           ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2),
           20
    FROM mass_messages

    UNION ALL
    -- Caption Freshness
    SELECT 'caption_freshness',
           ROUND(100.0 * SUM(CASE WHEN freshness_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2),
           15
    FROM caption_bank WHERE is_active = 1

    UNION ALL
    -- Performance Score
    SELECT 'performance_score',
           ROUND(100.0 * SUM(CASE WHEN performance_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2),
           15
    FROM caption_bank

    UNION ALL
    -- Creator Completeness
    SELECT 'creator_completeness',
           ROUND(100.0 * SUM(CASE
               WHEN page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL
               THEN 1 ELSE 0 END) / COUNT(*), 2),
           15
    FROM creators

    UNION ALL
    -- Logical Integrity
    SELECT 'logical_integrity',
           ROUND(100.0 * (1.0 - (
               (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) +
               (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)
           ) / CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2),
           10
)
SELECT
    'Score: ' || ROUND(SUM(score * weight) / SUM(weight), 2) || '/100'
FROM quality_metrics;

SELECT '';

-- Grade interpretation
WITH quality_metrics AS (
    SELECT 'fk_enforcement' as check_name,
           CASE (SELECT foreign_keys FROM pragma_foreign_keys()) WHEN 1 THEN 100.0 ELSE 0.0 END as score,
           25 as weight
    UNION ALL
    SELECT 'creator_id_linkage', ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 20 FROM mass_messages
    UNION ALL
    SELECT 'caption_freshness', ROUND(100.0 * SUM(CASE WHEN freshness_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM caption_bank WHERE is_active = 1
    UNION ALL
    SELECT 'performance_score', ROUND(100.0 * SUM(CASE WHEN performance_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM caption_bank
    UNION ALL
    SELECT 'creator_completeness', ROUND(100.0 * SUM(CASE WHEN page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM creators
    UNION ALL
    SELECT 'logical_integrity', ROUND(100.0 * (1.0 - ((SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) + (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)) / CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2), 10
)
SELECT 'Grade: ' ||
    CASE
        WHEN (SELECT ROUND(SUM(score * weight) / SUM(weight), 2) FROM quality_metrics) >= 90 THEN 'A (Excellent)'
        WHEN (SELECT ROUND(SUM(score * weight) / SUM(weight), 2) FROM quality_metrics) >= 80 THEN 'B (Good)'
        WHEN (SELECT ROUND(SUM(score * weight) / SUM(weight), 2) FROM quality_metrics) >= 70 THEN 'C (Acceptable)'
        WHEN (SELECT ROUND(SUM(score * weight) / SUM(weight), 2) FROM quality_metrics) >= 60 THEN 'D (Needs Improvement)'
        ELSE 'F (Critical - Immediate Action Required)'
    END;

SELECT '';
SELECT '============================================';

-- =============================================================================
-- END OF DATA QUALITY SCORE CALCULATOR
-- =============================================================================
