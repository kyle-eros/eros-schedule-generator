-- get_performance_trends.sql
-- Get weekly performance trends for volume adjustment decisions.
--
-- Parameters:
--   :creator_id (TEXT) - Creator UUID
--
-- Returns: Weekly aggregated performance with week-over-week change percentages
--
-- Performance optimizations:
--   - Uses idx_mm_creator_time index for date filtering
--   - CTEs for efficient weekly aggregation
--   - LAG window function for WoW calculations

WITH weekly_metrics AS (
    -- Aggregate metrics by week for last 60 days
    SELECT
        strftime('%Y-W%W', mm.sending_time) AS week_id,
        date(mm.sending_time, 'weekday 0', '-6 days') AS week_start,
        date(mm.sending_time, 'weekday 0') AS week_end,
        COUNT(*) AS message_count,
        COUNT(CASE WHEN mm.message_type = 'ppv' THEN 1 END) AS ppv_count,
        SUM(mm.earnings) AS total_earnings,
        SUM(CASE WHEN mm.message_type = 'ppv' THEN mm.earnings ELSE 0 END) AS ppv_earnings,
        ROUND(AVG(mm.earnings), 2) AS avg_earnings_per_message,
        ROUND(AVG(CASE WHEN mm.sent_count > 0
            THEN (mm.viewed_count * 100.0 / mm.sent_count)
            ELSE 0 END), 2) AS avg_view_rate,
        ROUND(AVG(CASE WHEN mm.sent_count > 0
            THEN (mm.purchased_count * 100.0 / mm.sent_count)
            ELSE 0 END), 2) AS avg_purchase_rate,
        SUM(mm.sent_count) AS total_sent,
        SUM(mm.purchased_count) AS total_purchased
    FROM mass_messages mm
    WHERE
        mm.creator_id = :creator_id
        AND mm.sending_time >= datetime('now', '-60 days')
    GROUP BY strftime('%Y-W%W', mm.sending_time)
    HAVING COUNT(*) >= 1
),

weekly_with_changes AS (
    -- Calculate week-over-week changes
    SELECT
        wm.*,

        -- Previous week values using LAG
        LAG(wm.total_earnings) OVER (ORDER BY wm.week_start) AS prev_week_earnings,
        LAG(wm.ppv_count) OVER (ORDER BY wm.week_start) AS prev_week_ppv_count,
        LAG(wm.avg_view_rate) OVER (ORDER BY wm.week_start) AS prev_week_view_rate,
        LAG(wm.avg_purchase_rate) OVER (ORDER BY wm.week_start) AS prev_week_purchase_rate,

        -- Row number for ordering
        ROW_NUMBER() OVER (ORDER BY wm.week_start DESC) AS recency_rank

    FROM weekly_metrics wm
)

SELECT
    week_id,
    week_start,
    week_end,
    message_count,
    ppv_count,
    ROUND(total_earnings, 2) AS total_earnings,
    ROUND(ppv_earnings, 2) AS ppv_earnings,
    avg_earnings_per_message,
    avg_view_rate,
    avg_purchase_rate,
    total_sent,
    total_purchased,

    -- Week-over-week earnings change percentage
    CASE
        WHEN prev_week_earnings IS NOT NULL AND prev_week_earnings > 0
        THEN ROUND(((total_earnings - prev_week_earnings) * 100.0 / prev_week_earnings), 1)
        ELSE NULL
    END AS earnings_change_pct,

    -- Week-over-week PPV count change
    CASE
        WHEN prev_week_ppv_count IS NOT NULL AND prev_week_ppv_count > 0
        THEN ROUND(((ppv_count - prev_week_ppv_count) * 100.0 / prev_week_ppv_count), 1)
        ELSE NULL
    END AS ppv_count_change_pct,

    -- Week-over-week view rate change (absolute points)
    CASE
        WHEN prev_week_view_rate IS NOT NULL
        THEN ROUND(avg_view_rate - prev_week_view_rate, 2)
        ELSE NULL
    END AS view_rate_change_pts,

    -- Week-over-week purchase rate change (absolute points)
    CASE
        WHEN prev_week_purchase_rate IS NOT NULL
        THEN ROUND(avg_purchase_rate - prev_week_purchase_rate, 2)
        ELSE NULL
    END AS purchase_rate_change_pts,

    -- Performance trend indicator
    CASE
        WHEN prev_week_earnings IS NULL THEN 'baseline'
        WHEN total_earnings > prev_week_earnings * 1.1 THEN 'growing'
        WHEN total_earnings < prev_week_earnings * 0.9 THEN 'declining'
        ELSE 'stable'
    END AS earnings_trend,

    recency_rank

FROM weekly_with_changes

ORDER BY week_start DESC

LIMIT 12;  -- Last 12 weeks (~3 months)
