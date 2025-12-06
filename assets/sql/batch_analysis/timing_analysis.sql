-- timing_analysis.sql
-- Phase 4: Timing Optimization Analysis
-- Hourly, daily, and combined heatmap performance.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Performance breakdowns by hour, day, and hour+day combinations
--
-- Industry Timing Benchmarks:
--   - Peak window: 6-10 PM local time
--   - Best days: Sunday > Friday > Saturday
--   - Avoid: Monday morning, mid-week early AM

-- Hourly performance
WITH hourly_perf AS (
    SELECT
        sending_hour,
        COUNT(*) AS count,
        SUM(earnings) AS total_revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(view_rate) * 100, 1) AS view_rate_pct,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate_pct,
        ROUND(AVG(revenue_per_send), 3) AS rps
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
    GROUP BY sending_hour
    HAVING COUNT(*) >= 2
),

-- Day-of-week performance
daily_perf AS (
    SELECT
        sending_day_of_week AS day_num,
        CASE sending_day_of_week
            WHEN 0 THEN 'Sunday'
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
        END AS day_name,
        COUNT(*) AS count,
        SUM(earnings) AS total_revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate_pct
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
    GROUP BY sending_day_of_week
),

-- Hour+Day heatmap (Top 15 combinations)
heatmap AS (
    SELECT
        sending_day_of_week AS day_num,
        CASE sending_day_of_week
            WHEN 0 THEN 'Sun'
            WHEN 1 THEN 'Mon'
            WHEN 2 THEN 'Tue'
            WHEN 3 THEN 'Wed'
            WHEN 4 THEN 'Thu'
            WHEN 5 THEN 'Fri'
            WHEN 6 THEN 'Sat'
        END AS day_abbrev,
        sending_hour AS hour,
        COUNT(*) AS count,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate_pct
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
    GROUP BY sending_day_of_week, sending_hour
    HAVING COUNT(*) >= 2
    ORDER BY avg_earnings DESC
    LIMIT 15
)

-- Combine results with section identifiers
SELECT
    'hourly' AS section,
    hp.sending_hour AS key_int,
    NULL AS key_text,
    hp.count,
    hp.total_revenue,
    hp.avg_earnings,
    hp.view_rate_pct,
    hp.purchase_rate_pct,
    hp.rps,
    RANK() OVER (ORDER BY hp.avg_earnings DESC) AS rank_by_earnings
FROM hourly_perf hp

UNION ALL

SELECT
    'daily' AS section,
    dp.day_num AS key_int,
    dp.day_name AS key_text,
    dp.count,
    dp.total_revenue,
    dp.avg_earnings,
    NULL AS view_rate_pct,
    dp.purchase_rate_pct,
    NULL AS rps,
    RANK() OVER (ORDER BY dp.avg_earnings DESC) AS rank_by_earnings
FROM daily_perf dp

UNION ALL

SELECT
    'heatmap' AS section,
    hm.hour AS key_int,
    hm.day_abbrev AS key_text,
    hm.count,
    NULL AS total_revenue,
    hm.avg_earnings,
    NULL AS view_rate_pct,
    hm.purchase_rate_pct,
    NULL AS rps,
    ROW_NUMBER() OVER (ORDER BY hm.avg_earnings DESC) AS rank_by_earnings
FROM heatmap hm

ORDER BY
    CASE section
        WHEN 'hourly' THEN 1
        WHEN 'daily' THEN 2
        WHEN 'heatmap' THEN 3
    END,
    rank_by_earnings;
