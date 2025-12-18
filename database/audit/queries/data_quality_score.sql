-- EROS Database Data Quality Score Calculator
-- Run: sqlite3 database/eros_sd_main.db < database/audit/queries/data_quality_score.sql

.mode column
.headers on

SELECT '=== EROS DATA QUALITY SCORE ===' as report;
SELECT datetime('now') as check_time;

WITH quality_checks AS (
    -- Check 1: FK enforcement (weight: 25%)
    SELECT
        'fk_enforcement' as check_name,
        CASE (SELECT * FROM pragma_foreign_keys())
            WHEN 1 THEN 100.0
            ELSE 0.0
        END as score,
        25 as weight,
        'Foreign key enforcement status' as description

    UNION ALL
    -- Check 2: creator_id linkage in mass_messages (weight: 20%)
    SELECT
        'mm_creator_linkage',
        ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2),
        20,
        'Mass messages with valid creator_id'
    FROM mass_messages

    UNION ALL
    -- Check 3: Caption freshness validity (weight: 15%)
    SELECT
        'caption_freshness_valid',
        ROUND(100.0 * SUM(CASE WHEN freshness_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2),
        15,
        'Captions with valid freshness scores'
    FROM caption_bank WHERE is_active = 1

    UNION ALL
    -- Check 4: Performance score validity (weight: 15%)
    SELECT
        'performance_score_valid',
        ROUND(100.0 * SUM(CASE WHEN performance_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2),
        15,
        'Captions with valid performance scores'
    FROM caption_bank

    UNION ALL
    -- Check 5: Creator completeness (weight: 15%)
    SELECT
        'creator_completeness',
        ROUND(100.0 * SUM(CASE
            WHEN page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL
            THEN 1 ELSE 0 END) / COUNT(*), 2),
        15,
        'Creators with complete required fields'
    FROM creators

    UNION ALL
    -- Check 6: Logical data integrity (weight: 10%)
    SELECT
        'logical_integrity',
        ROUND(100.0 * (1.0 - (
            (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) +
            (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)
        ) / CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2),
        10,
        'Records without logical impossibilities'
)

SELECT '--- Individual Check Scores ---' as section;

SELECT
    check_name,
    score || '%' as score,
    weight || '%' as weight,
    description
FROM quality_checks;

SELECT '--- Overall Quality Score ---' as section;

SELECT
    ROUND(SUM(score * weight) / SUM(weight), 2) as overall_score,
    CASE
        WHEN SUM(score * weight) / SUM(weight) >= 90 THEN 'A - Excellent'
        WHEN SUM(score * weight) / SUM(weight) >= 80 THEN 'B - Good'
        WHEN SUM(score * weight) / SUM(weight) >= 70 THEN 'C - Acceptable'
        WHEN SUM(score * weight) / SUM(weight) >= 60 THEN 'D - Needs Improvement'
        ELSE 'F - Critical Issues'
    END as grade
FROM quality_checks;

SELECT '=== SCORE CALCULATION COMPLETE ===' as report;
