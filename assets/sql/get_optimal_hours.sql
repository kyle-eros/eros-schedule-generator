-- get_optimal_hours.sql
-- Get best performing hours from historical mass_messages data.
--
-- Parameters:
--   :creator_id (TEXT)  - Creator UUID
--   :days_back (INT)    - Days of history to analyze (default 90)
--
-- Returns: Hours ranked by average earnings with engagement metrics
--
-- Performance optimizations:
--   - Uses idx_mm_creator_time index
--   - Uses idx_mm_creator_type_analytics composite index
--   - Filters to PPV messages only for revenue analysis

WITH hourly_performance AS (
    SELECT
        mm.sending_hour,
        COUNT(*) AS message_count,
        SUM(mm.earnings) AS total_earnings,
        ROUND(AVG(mm.earnings), 2) AS avg_earnings,
        ROUND(AVG(CASE WHEN mm.sent_count > 0
            THEN (mm.viewed_count * 100.0 / mm.sent_count)
            ELSE 0 END), 2) AS avg_view_rate,
        ROUND(AVG(CASE WHEN mm.sent_count > 0
            THEN (mm.purchased_count * 100.0 / mm.sent_count)
            ELSE 0 END), 2) AS avg_purchase_rate,
        AVG(mm.price) AS avg_price,
        SUM(mm.sent_count) AS total_sent,
        SUM(mm.viewed_count) AS total_viewed,
        SUM(mm.purchased_count) AS total_purchased
    FROM mass_messages mm
    WHERE
        mm.creator_id = :creator_id
        AND mm.message_type = 'ppv'
        AND mm.sending_time >= datetime('now', '-' || COALESCE(:days_back, 90) || ' days')
        AND mm.earnings IS NOT NULL
    GROUP BY mm.sending_hour
    HAVING COUNT(*) >= 3  -- Minimum sample size for statistical relevance
)

SELECT
    hp.sending_hour,
    hp.message_count,
    hp.total_earnings,
    hp.avg_earnings,
    hp.avg_view_rate,
    hp.avg_purchase_rate,
    ROUND(hp.avg_price, 2) AS avg_price,
    hp.total_sent,
    hp.total_viewed,
    hp.total_purchased,

    -- Hour classification
    CASE
        WHEN hp.sending_hour BETWEEN 6 AND 11 THEN 'morning'
        WHEN hp.sending_hour BETWEEN 12 AND 17 THEN 'afternoon'
        WHEN hp.sending_hour BETWEEN 18 AND 22 THEN 'evening'
        ELSE 'night'
    END AS time_slot,

    -- Rank by earnings
    ROW_NUMBER() OVER (ORDER BY hp.avg_earnings DESC) AS earnings_rank,

    -- Percentile within this creator's hours
    ROUND(
        PERCENT_RANK() OVER (ORDER BY hp.avg_earnings) * 100,
        1
    ) AS earnings_percentile

FROM hourly_performance hp

ORDER BY hp.avg_earnings DESC;
