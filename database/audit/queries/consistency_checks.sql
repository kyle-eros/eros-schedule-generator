-- EROS Database Consistency Checks
-- Run: sqlite3 database/eros_sd_main.db < database/audit/queries/consistency_checks.sql

.mode column
.headers on

SELECT '=== EROS DATABASE CONSISTENCY CHECKS ===' as report;
SELECT datetime('now') as check_time;

-- 1. Score Range Violations
SELECT '--- Score Range Analysis ---' as section;

SELECT 'caption_bank.performance_score' as field,
       COUNT(*) as total,
       SUM(CASE WHEN performance_score < 0 THEN 1 ELSE 0 END) as below_zero,
       SUM(CASE WHEN performance_score > 100 THEN 1 ELSE 0 END) as above_100,
       MIN(performance_score) as min_val,
       MAX(performance_score) as max_val
FROM caption_bank
UNION ALL
SELECT 'caption_bank.freshness_score',
       COUNT(*),
       SUM(CASE WHEN freshness_score < 0 THEN 1 ELSE 0 END),
       SUM(CASE WHEN freshness_score > 100 THEN 1 ELSE 0 END),
       MIN(freshness_score),
       MAX(freshness_score)
FROM caption_bank
UNION ALL
SELECT 'caption_creator_performance.performance_score',
       COUNT(*),
       SUM(CASE WHEN performance_score < 0 THEN 1 ELSE 0 END),
       SUM(CASE WHEN performance_score > 100 THEN 1 ELSE 0 END),
       MIN(performance_score),
       MAX(performance_score)
FROM caption_creator_performance;

-- 2. Negative Value Detection
SELECT '--- Negative Values ---' as section;

SELECT 'mass_messages.sent_count < 0' as issue, COUNT(*) as count
FROM mass_messages WHERE sent_count < 0
UNION ALL
SELECT 'mass_messages.viewed_count < 0', COUNT(*)
FROM mass_messages WHERE viewed_count < 0
UNION ALL
SELECT 'mass_messages.purchased_count < 0', COUNT(*)
FROM mass_messages WHERE purchased_count < 0
UNION ALL
SELECT 'mass_messages.earnings < 0', COUNT(*)
FROM mass_messages WHERE earnings < 0
UNION ALL
SELECT 'caption_bank.times_used < 0', COUNT(*)
FROM caption_bank WHERE times_used < 0
UNION ALL
SELECT 'caption_bank.total_earnings < 0', COUNT(*)
FROM caption_bank WHERE total_earnings < 0;

-- 3. Logical Impossibilities
SELECT '--- Logical Impossibilities ---' as section;

SELECT 'viewed_count > sent_count' as issue, COUNT(*) as count
FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0
UNION ALL
SELECT 'purchased_count > viewed_count', COUNT(*)
FROM mass_messages WHERE purchased_count > viewed_count AND viewed_count > 0;

-- 4. View Rate Anomalies (sample)
SELECT '--- View Rate Anomalies (>100%) ---' as section;

SELECT message_id, page_name, sent_count, viewed_count,
       ROUND(view_rate * 100, 2) as view_rate_pct
FROM mass_messages
WHERE view_rate > 1.0
ORDER BY view_rate DESC
LIMIT 10;

-- 5. Temporal Consistency
SELECT '--- Temporal Consistency ---' as section;

SELECT 'caption_bank date inversions' as check_type, COUNT(*) as count
FROM caption_bank
WHERE first_used_date IS NOT NULL
AND last_used_date IS NOT NULL
AND last_used_date < first_used_date
UNION ALL
SELECT 'caption_creator_performance date inversions', COUNT(*)
FROM caption_creator_performance
WHERE first_used_date IS NOT NULL
AND last_used_date IS NOT NULL
AND last_used_date < first_used_date;

-- 6. Cross-Table Consistency
SELECT '--- Cross-Table Consistency ---' as section;

SELECT
    SUM(CASE WHEN ccp_sum IS NULL AND cb.times_used > 0 THEN 1 ELSE 0 END) as missing_ccp_records,
    SUM(CASE WHEN ccp_sum IS NOT NULL AND cb.times_used != ccp_sum THEN 1 ELSE 0 END) as times_mismatch,
    COUNT(*) as total_captions_with_usage
FROM caption_bank cb
LEFT JOIN (
    SELECT caption_id, SUM(times_used) as ccp_sum
    FROM caption_creator_performance
    GROUP BY caption_id
) ccp ON cb.caption_id = ccp.caption_id
WHERE cb.times_used > 0;

-- 7. Business Rule: Performance Tier Classification
SELECT '--- Performance Tier vs Score ---' as section;

SELECT performance_tier,
       MIN(performance_score) as min_score,
       MAX(performance_score) as max_score,
       ROUND(AVG(performance_score), 2) as avg_score,
       COUNT(*) as count,
       SUM(CASE WHEN performance_score >= 80 THEN 1 ELSE 0 END) as winners_by_score,
       SUM(CASE WHEN performance_score < 40 THEN 1 ELSE 0 END) as losers_by_score
FROM caption_bank
WHERE is_active = 1
GROUP BY performance_tier
ORDER BY performance_tier;

-- 8. Exhausted Captions Still Active
SELECT '--- Exhausted Captions (times_used >= 25, still active) ---' as section;

SELECT COUNT(*) as count
FROM caption_bank
WHERE times_used >= 25 AND is_active = 1;

-- 9. PPV vs Free Earnings Logic
SELECT '--- Message Type Earnings Analysis ---' as section;

SELECT message_type,
       COUNT(*) as total,
       SUM(CASE WHEN earnings > 0 THEN 1 ELSE 0 END) as with_earnings,
       SUM(CASE WHEN earnings = 0 THEN 1 ELSE 0 END) as zero_earnings,
       ROUND(AVG(CASE WHEN earnings > 0 THEN earnings END), 2) as avg_when_has_earnings,
       MAX(earnings) as max_earnings
FROM mass_messages
GROUP BY message_type;

-- 10. Stale Analytics
SELECT '--- Stale Analytics (>7 days) ---' as section;

SELECT COUNT(*) as stale_analytics_count,
       MIN(calculated_at) as oldest,
       MAX(calculated_at) as newest
FROM creator_analytics_summary
WHERE calculated_at < datetime('now', '-7 days');

SELECT '=== CONSISTENCY CHECKS COMPLETE ===' as report;
