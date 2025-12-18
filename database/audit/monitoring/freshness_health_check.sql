-- Daily Freshness Health Check
-- Run this daily to monitor creator freshness levels
-- Usage: sqlite3 $EROS_DATABASE_PATH < freshness_health_check.sql

.headers on
.mode box

SELECT '=== FRESHNESS HEALTH CHECK - ' || date('now') || ' ===' as report_header;

-- Section 1: Crisis Creators (avg < 20)
SELECT 
    'CRISIS CREATORS (avg < 20)' as section,
    c.page_name,
    c.performance_tier as tier,
    ROUND(AVG(cb.freshness_score), 2) as avg_freshness,
    COUNT(CASE WHEN cb.freshness_score >= 30 THEN 1 END) as schedulable_count,
    COUNT(cb.caption_id) as total_captions,
    CASE WHEN cua.enabled = 1 THEN 'YES' ELSE 'NO' END as universal_access
FROM creators c
LEFT JOIN caption_bank cb ON c.creator_id = cb.creator_id
LEFT JOIN creator_universal_access cua ON c.creator_id = cua.creator_id
WHERE c.is_active = 1
GROUP BY c.page_name, c.performance_tier, cua.enabled
HAVING AVG(cb.freshness_score) < 20
ORDER BY avg_freshness ASC;

-- Section 2: Warning Creators (20 <= avg < 30)
SELECT 
    'WARNING CREATORS (20-30)' as section,
    c.page_name,
    c.performance_tier as tier,
    ROUND(AVG(cb.freshness_score), 2) as avg_freshness,
    COUNT(CASE WHEN cb.freshness_score >= 30 THEN 1 END) as schedulable_count,
    COUNT(cb.caption_id) as total_captions
FROM creators c
LEFT JOIN caption_bank cb ON c.creator_id = cb.creator_id
WHERE c.is_active = 1
GROUP BY c.page_name, c.performance_tier
HAVING AVG(cb.freshness_score) >= 20 AND AVG(cb.freshness_score) < 30
ORDER BY avg_freshness ASC;

-- Section 3: Overall Portfolio Health
SELECT 
    'PORTFOLIO SUMMARY' as section,
    COUNT(DISTINCT c.creator_id) as total_active_creators,
    ROUND(AVG(avg_fresh), 2) as portfolio_avg_freshness,
    SUM(CASE WHEN avg_fresh < 10 THEN 1 ELSE 0 END) as critical_count,
    SUM(CASE WHEN avg_fresh >= 10 AND avg_fresh < 20 THEN 1 ELSE 0 END) as severe_count,
    SUM(CASE WHEN avg_fresh >= 20 AND avg_fresh < 30 THEN 1 ELSE 0 END) as warning_count,
    SUM(CASE WHEN avg_fresh >= 30 THEN 1 ELSE 0 END) as healthy_count
FROM creators c
LEFT JOIN (
    SELECT 
        creator_id,
        AVG(freshness_score) as avg_fresh
    FROM caption_bank
    GROUP BY creator_id
) cb ON c.creator_id = cb.creator_id
WHERE c.is_active = 1;

-- Section 4: Universal Caption Pool Status
SELECT 
    'UNIVERSAL POOL' as section,
    COUNT(*) as total_universal,
    ROUND(AVG(freshness_score), 2) as avg_freshness,
    COUNT(CASE WHEN freshness_score >= 30 THEN 1 END) as schedulable
FROM caption_bank
WHERE is_universal = 1 AND is_active = 1;

-- Section 5: Dead Inventory Alert
SELECT 
    'DEAD INVENTORY' as section,
    page_name,
    COUNT(*) as dead_count
FROM caption_bank
WHERE freshness_score = 0.0 AND is_active = 1
GROUP BY page_name
HAVING COUNT(*) >= 10
ORDER BY dead_count DESC;
