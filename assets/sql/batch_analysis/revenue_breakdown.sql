-- revenue_breakdown.sql
-- Phase 2: Revenue Architecture Analysis
-- Comprehensive revenue breakdown with benchmark metrics.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Complete revenue breakdown with ratios and benchmarks
--
-- Benchmarks:
--   - Message:Sub ratio: <1 POOR | 1-2 AVG | 2-3 GOOD | >3 EXCELLENT
--   - Earnings/fan: <$5 POOR | $5-15 AVG | $15-30 GOOD | >$30 EXCELLENT
--   - Renew-on %: <15% POOR | 15-25% AVG | 25-40% GOOD | >40% EXCELLENT

SELECT
    c.page_name,
    c.display_name,
    c.page_type,
    c.performance_tier,
    c.current_of_ranking,
    c.current_active_fans,
    c.current_new_fans,
    c.current_expired_fan_change,
    c.current_fans_renew_on,
    ROUND(c.current_renew_on_pct, 1) AS renew_on_pct,

    -- Revenue breakdown
    ROUND(c.current_total_earnings, 2) AS total_earnings,
    ROUND(c.current_subscription_net, 2) AS subscription_revenue,
    ROUND(c.current_message_net, 2) AS message_revenue,
    ROUND(c.current_tips_net, 2) AS tips_revenue,
    ROUND(c.current_posts_net, 2) AS posts_revenue,
    ROUND(c.current_streams_net, 2) AS streams_revenue,

    -- Revenue percentages
    ROUND(c.current_message_net * 100.0 / NULLIF(c.current_total_earnings, 0), 1) AS message_pct,
    ROUND(c.current_subscription_net * 100.0 / NULLIF(c.current_total_earnings, 0), 1) AS subscription_pct,
    ROUND(c.current_tips_net * 100.0 / NULLIF(c.current_total_earnings, 0), 1) AS tips_pct,

    -- Key ratios
    ROUND(c.current_message_net / NULLIF(c.current_subscription_net, 0), 2) AS message_sub_ratio,
    ROUND(c.current_avg_earnings_per_fan, 2) AS earnings_per_fan,
    ROUND(c.current_avg_spend_per_spender, 2) AS spend_per_spender,

    -- Benchmark ratings
    CASE
        WHEN c.current_message_net / NULLIF(c.current_subscription_net, 0) > 3 THEN 'EXCELLENT'
        WHEN c.current_message_net / NULLIF(c.current_subscription_net, 0) >= 2 THEN 'GOOD'
        WHEN c.current_message_net / NULLIF(c.current_subscription_net, 0) >= 1 THEN 'AVG'
        ELSE 'POOR'
    END AS msg_sub_rating,

    CASE
        WHEN c.current_avg_earnings_per_fan > 30 THEN 'EXCELLENT'
        WHEN c.current_avg_earnings_per_fan >= 15 THEN 'GOOD'
        WHEN c.current_avg_earnings_per_fan >= 5 THEN 'AVG'
        ELSE 'POOR'
    END AS earnings_per_fan_rating,

    CASE
        WHEN c.current_renew_on_pct > 40 THEN 'EXCELLENT'
        WHEN c.current_renew_on_pct >= 25 THEN 'GOOD'
        WHEN c.current_renew_on_pct >= 15 THEN 'AVG'
        ELSE 'POOR'
    END AS renew_on_rating,

    -- Metadata
    c.current_contribution_pct,
    c.current_avg_subscription_length,
    c.metrics_snapshot_date

FROM creators c
WHERE c.creator_id = ?;
