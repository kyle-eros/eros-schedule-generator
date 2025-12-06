-- portfolio_summary.sql
-- Aggregate Portfolio Summary Statistics
-- Complete portfolio overview for executive reporting.
--
-- Parameters: None
--
-- Returns: Portfolio-wide aggregates, tier distribution, top performers, and health metrics

-- Portfolio-wide aggregates
WITH portfolio_totals AS (
    SELECT
        COUNT(*) AS total_creators,
        SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_creators,
        ROUND(SUM(current_total_earnings), 2) AS total_earnings,
        ROUND(SUM(current_message_net), 2) AS total_message_revenue,
        ROUND(SUM(current_subscription_net), 2) AS total_subscription_revenue,
        ROUND(SUM(current_tips_net), 2) AS total_tips_revenue,
        SUM(current_active_fans) AS total_fans,
        ROUND(AVG(current_total_earnings), 2) AS avg_earnings_per_creator,
        ROUND(AVG(current_active_fans), 0) AS avg_fans_per_creator,
        ROUND(AVG(current_avg_earnings_per_fan), 2) AS avg_earnings_per_fan,
        ROUND(AVG(current_renew_on_pct), 1) AS avg_renew_pct,
        ROUND(AVG(current_message_net / NULLIF(current_subscription_net, 0)), 2) AS avg_msg_sub_ratio
    FROM creators
    WHERE is_active = 1
),

-- Tier distribution
tier_distribution AS (
    SELECT
        performance_tier,
        COUNT(*) AS count,
        ROUND(SUM(current_total_earnings), 2) AS tier_earnings,
        ROUND(AVG(current_total_earnings), 2) AS avg_earnings,
        SUM(current_active_fans) AS tier_fans,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM creators WHERE is_active = 1), 1) AS pct_of_portfolio
    FROM creators
    WHERE is_active = 1
    GROUP BY performance_tier
),

-- Top 5 by revenue
top_by_revenue AS (
    SELECT
        page_name,
        display_name,
        ROUND(current_total_earnings, 2) AS earnings,
        current_active_fans AS fans,
        performance_tier,
        ROW_NUMBER() OVER (ORDER BY current_total_earnings DESC) AS rank
    FROM creators
    WHERE is_active = 1
    ORDER BY current_total_earnings DESC
    LIMIT 5
),

-- Top 5 by fans
top_by_fans AS (
    SELECT
        page_name,
        display_name,
        current_active_fans AS fans,
        ROUND(current_total_earnings, 2) AS earnings,
        performance_tier,
        ROW_NUMBER() OVER (ORDER BY current_active_fans DESC) AS rank
    FROM creators
    WHERE is_active = 1
    ORDER BY current_active_fans DESC
    LIMIT 5
),

-- Top 5 by efficiency
top_by_efficiency AS (
    SELECT
        page_name,
        display_name,
        ROUND(current_avg_earnings_per_fan, 2) AS efficiency,
        ROUND(current_total_earnings, 2) AS earnings,
        current_active_fans AS fans,
        performance_tier,
        ROW_NUMBER() OVER (ORDER BY current_avg_earnings_per_fan DESC) AS rank
    FROM creators
    WHERE is_active = 1
      AND current_active_fans > 100  -- Minimum fan threshold for meaningful efficiency
    ORDER BY current_avg_earnings_per_fan DESC
    LIMIT 5
),

-- Caption health portfolio-wide
caption_health AS (
    SELECT
        COUNT(*) AS total_captions,
        ROUND(AVG(freshness_score), 1) AS avg_freshness,
        SUM(CASE WHEN freshness_score >= 80 THEN 1 ELSE 0 END) AS fresh_count,
        SUM(CASE WHEN freshness_score >= 30 AND freshness_score < 80 THEN 1 ELSE 0 END) AS good_count,
        SUM(CASE WHEN freshness_score < 30 THEN 1 ELSE 0 END) AS stale_count,
        SUM(CASE WHEN freshness_score < 25 THEN 1 ELSE 0 END) AS critical_count
    FROM caption_bank
    WHERE is_active = 1
),

-- Recent PPV performance (last 30 days)
recent_ppv AS (
    SELECT
        COUNT(*) AS total_ppvs,
        ROUND(SUM(earnings), 2) AS total_revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS avg_purchase_rate,
        ROUND(AVG(view_rate) * 100, 1) AS avg_view_rate,
        COUNT(DISTINCT creator_id) AS active_senders
    FROM mass_messages
    WHERE message_type = 'ppv'
      AND sending_time >= date('now', '-30 days')
)

-- Portfolio totals section
SELECT
    'portfolio_totals' AS section,
    NULL AS identifier,
    pt.total_creators,
    pt.active_creators,
    pt.total_earnings,
    pt.total_message_revenue,
    pt.total_subscription_revenue,
    pt.total_fans,
    pt.avg_earnings_per_creator,
    pt.avg_fans_per_creator,
    pt.avg_earnings_per_fan,
    pt.avg_renew_pct,
    pt.avg_msg_sub_ratio,
    1 AS sort_order
FROM portfolio_totals pt

UNION ALL

-- Tier distribution section
SELECT
    'tier_distribution' AS section,
    'Tier ' || td.performance_tier AS identifier,
    td.count AS total_creators,
    NULL AS active_creators,
    td.tier_earnings AS total_earnings,
    td.avg_earnings AS total_message_revenue,
    NULL AS total_subscription_revenue,
    td.tier_fans AS total_fans,
    td.pct_of_portfolio AS avg_earnings_per_creator,
    NULL AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    td.performance_tier AS sort_order
FROM tier_distribution td

UNION ALL

-- Top by revenue section
SELECT
    'top_by_revenue' AS section,
    tr.page_name AS identifier,
    tr.performance_tier AS total_creators,
    tr.fans AS active_creators,
    tr.earnings AS total_earnings,
    NULL AS total_message_revenue,
    NULL AS total_subscription_revenue,
    NULL AS total_fans,
    NULL AS avg_earnings_per_creator,
    NULL AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    tr.rank AS sort_order
FROM top_by_revenue tr

UNION ALL

-- Top by fans section
SELECT
    'top_by_fans' AS section,
    tf.page_name AS identifier,
    tf.performance_tier AS total_creators,
    tf.fans AS active_creators,
    tf.earnings AS total_earnings,
    NULL AS total_message_revenue,
    NULL AS total_subscription_revenue,
    NULL AS total_fans,
    NULL AS avg_earnings_per_creator,
    NULL AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    tf.rank AS sort_order
FROM top_by_fans tf

UNION ALL

-- Top by efficiency section
SELECT
    'top_by_efficiency' AS section,
    te.page_name AS identifier,
    te.performance_tier AS total_creators,
    te.fans AS active_creators,
    te.earnings AS total_earnings,
    te.efficiency AS total_message_revenue,
    NULL AS total_subscription_revenue,
    NULL AS total_fans,
    NULL AS avg_earnings_per_creator,
    NULL AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    te.rank AS sort_order
FROM top_by_efficiency te

UNION ALL

-- Caption health section
SELECT
    'caption_health' AS section,
    NULL AS identifier,
    ch.total_captions,
    ch.fresh_count AS active_creators,
    ch.good_count AS total_earnings,
    ch.stale_count AS total_message_revenue,
    ch.critical_count AS total_subscription_revenue,
    NULL AS total_fans,
    ch.avg_freshness AS avg_earnings_per_creator,
    NULL AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    1 AS sort_order
FROM caption_health ch

UNION ALL

-- Recent PPV section
SELECT
    'recent_ppv_30d' AS section,
    NULL AS identifier,
    rp.total_ppvs AS total_creators,
    rp.active_senders AS active_creators,
    rp.total_revenue AS total_earnings,
    rp.avg_earnings AS total_message_revenue,
    NULL AS total_subscription_revenue,
    NULL AS total_fans,
    rp.avg_purchase_rate AS avg_earnings_per_creator,
    rp.avg_view_rate AS avg_fans_per_creator,
    NULL AS avg_earnings_per_fan,
    NULL AS avg_renew_pct,
    NULL AS avg_msg_sub_ratio,
    1 AS sort_order
FROM recent_ppv rp

ORDER BY
    CASE section
        WHEN 'portfolio_totals' THEN 1
        WHEN 'tier_distribution' THEN 2
        WHEN 'top_by_revenue' THEN 3
        WHEN 'top_by_fans' THEN 4
        WHEN 'top_by_efficiency' THEN 5
        WHEN 'caption_health' THEN 6
        WHEN 'recent_ppv_30d' THEN 7
    END,
    sort_order;
