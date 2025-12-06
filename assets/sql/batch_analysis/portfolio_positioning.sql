-- portfolio_positioning.sql
-- Phase 9: Portfolio Positioning Analysis
-- Rank creator within portfolio and compare to tier benchmarks.
--
-- Parameters:
--   ? - creator_id (TEXT) for creator-specific view
--
-- Returns: Portfolio rankings and tier comparison stats

-- Portfolio rankings with percentiles
WITH portfolio_ranks AS (
    SELECT
        c.creator_id,
        c.page_name,
        c.display_name,
        c.performance_tier,
        c.page_type,

        -- Earnings metrics
        ROUND(c.current_total_earnings, 2) AS earnings,
        RANK() OVER (ORDER BY c.current_total_earnings DESC) AS earnings_rank,
        ROUND(PERCENT_RANK() OVER (ORDER BY c.current_total_earnings DESC) * 100, 1) AS earnings_percentile,

        -- Fan metrics
        c.current_active_fans AS fans,
        RANK() OVER (ORDER BY c.current_active_fans DESC) AS fans_rank,
        ROUND(PERCENT_RANK() OVER (ORDER BY c.current_active_fans DESC) * 100, 1) AS fans_percentile,

        -- Efficiency metrics
        ROUND(c.current_avg_earnings_per_fan, 2) AS efficiency,
        RANK() OVER (ORDER BY c.current_avg_earnings_per_fan DESC) AS efficiency_rank,
        ROUND(PERCENT_RANK() OVER (ORDER BY c.current_avg_earnings_per_fan DESC) * 100, 1) AS efficiency_percentile,

        -- Message revenue
        ROUND(c.current_message_net, 2) AS message_revenue,
        RANK() OVER (ORDER BY c.current_message_net DESC) AS message_rank,

        -- Retention
        ROUND(c.current_renew_on_pct, 1) AS renew_pct,
        RANK() OVER (ORDER BY c.current_renew_on_pct DESC) AS retention_rank,

        -- Total active creators for context
        (SELECT COUNT(*) FROM creators WHERE is_active = 1) AS total_creators

    FROM creators c
    WHERE c.is_active = 1
),

-- Tier comparison stats
tier_stats AS (
    SELECT
        performance_tier,
        COUNT(*) AS count,
        ROUND(AVG(current_total_earnings), 2) AS avg_earnings,
        ROUND(AVG(current_active_fans), 0) AS avg_fans,
        ROUND(AVG(current_avg_earnings_per_fan), 2) AS avg_efficiency,
        ROUND(AVG(current_renew_on_pct), 1) AS avg_renew_pct,
        ROUND(AVG(current_message_net), 2) AS avg_message_revenue,
        ROUND(SUM(current_total_earnings), 2) AS tier_total_earnings,
        ROUND(MIN(current_total_earnings), 2) AS min_earnings,
        ROUND(MAX(current_total_earnings), 2) AS max_earnings
    FROM creators
    WHERE is_active = 1
    GROUP BY performance_tier
)

-- Creator-specific positioning (if creator_id provided)
SELECT
    'creator_position' AS section,
    pr.page_name AS identifier,
    pr.display_name,
    pr.performance_tier,
    pr.page_type,
    pr.earnings,
    pr.earnings_rank,
    pr.earnings_percentile,
    pr.fans,
    pr.fans_rank,
    pr.fans_percentile,
    pr.efficiency,
    pr.efficiency_rank,
    pr.efficiency_percentile,
    pr.message_revenue,
    pr.message_rank,
    pr.renew_pct,
    pr.retention_rank,
    pr.total_creators,
    -- Performance tier context
    ts.avg_earnings AS tier_avg_earnings,
    ts.avg_fans AS tier_avg_fans,
    ts.avg_efficiency AS tier_avg_efficiency,
    -- Above/below tier average
    ROUND((pr.earnings - ts.avg_earnings) / NULLIF(ts.avg_earnings, 0) * 100, 1) AS vs_tier_earnings_pct,
    ROUND((pr.fans - ts.avg_fans) / NULLIF(ts.avg_fans, 0) * 100, 1) AS vs_tier_fans_pct,
    ROUND((pr.efficiency - ts.avg_efficiency) / NULLIF(ts.avg_efficiency, 0) * 100, 1) AS vs_tier_efficiency_pct
FROM portfolio_ranks pr
LEFT JOIN tier_stats ts ON pr.performance_tier = ts.performance_tier
WHERE pr.creator_id = ?

UNION ALL

-- Tier summary section (always included for context)
SELECT
    'tier_summary' AS section,
    'Tier ' || ts.performance_tier AS identifier,
    NULL AS display_name,
    ts.performance_tier,
    NULL AS page_type,
    ts.avg_earnings AS earnings,
    NULL AS earnings_rank,
    NULL AS earnings_percentile,
    ts.avg_fans AS fans,
    NULL AS fans_rank,
    NULL AS fans_percentile,
    ts.avg_efficiency AS efficiency,
    NULL AS efficiency_rank,
    NULL AS efficiency_percentile,
    ts.avg_message_revenue AS message_revenue,
    NULL AS message_rank,
    ts.avg_renew_pct AS renew_pct,
    NULL AS retention_rank,
    ts.count AS total_creators,
    ts.tier_total_earnings AS tier_avg_earnings,
    ts.min_earnings AS tier_avg_fans,
    ts.max_earnings AS tier_avg_efficiency,
    NULL AS vs_tier_earnings_pct,
    NULL AS vs_tier_fans_pct,
    NULL AS vs_tier_efficiency_pct
FROM tier_stats ts

ORDER BY
    CASE section WHEN 'creator_position' THEN 1 ELSE 2 END,
    performance_tier;
