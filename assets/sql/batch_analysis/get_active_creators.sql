-- get_active_creators.sql
-- Fetch all active creators with key metrics for batch analysis.
--
-- Parameters: None
--
-- Returns: All 36 active creators with key metrics sorted by earnings DESC
--
-- Performance optimizations:
--   - Uses idx_creators_active partial index
--   - Uses idx_creators_active_earnings composite index
--   - Single-pass aggregation with scalar subqueries

SELECT
    c.creator_id,
    c.page_name,
    c.display_name,
    c.page_type,
    c.subscription_price,
    c.timezone,
    c.current_active_fans,
    c.current_total_earnings,
    c.current_message_net,
    c.current_subscription_net,
    c.current_tips_net,
    c.current_avg_earnings_per_fan,
    c.current_renew_on_pct,
    c.current_of_ranking,
    c.performance_tier,
    c.metrics_snapshot_date,
    c.persona_type,
    c.account_age_days,

    -- Volume level calculation
    CASE
        WHEN c.current_active_fans < 1000 THEN 'Low'
        WHEN c.current_active_fans < 5000 THEN 'Mid'
        WHEN c.current_active_fans < 15000 THEN 'High'
        ELSE 'Ultra'
    END AS volume_level,

    -- Persona summary (joined)
    p.primary_tone,
    p.emoji_frequency,
    p.slang_level,

    -- PPV count last 30 days (scalar subquery)
    (
        SELECT COUNT(*)
        FROM mass_messages mm
        WHERE mm.creator_id = c.creator_id
          AND mm.message_type = 'ppv'
          AND mm.sending_time >= date('now', '-30 days')
    ) AS ppv_count_30d,

    -- Revenue last 30 days
    (
        SELECT COALESCE(SUM(mm.earnings), 0)
        FROM mass_messages mm
        WHERE mm.creator_id = c.creator_id
          AND mm.message_type = 'ppv'
          AND mm.sending_time >= date('now', '-30 days')
    ) AS ppv_revenue_30d

FROM creators c
LEFT JOIN creator_personas p ON c.creator_id = p.creator_id

WHERE c.is_active = 1

ORDER BY c.current_total_earnings DESC;
