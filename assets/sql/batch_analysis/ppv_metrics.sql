-- ppv_metrics.sql
-- Phase 3: PPV Performance Deep Dive
-- Overall PPV metrics, monthly trends, and week-over-week comparison.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Comprehensive PPV performance analysis
--
-- Benchmarks:
--   - View rate: <40% POOR | 40-60% AVG | 60-80% GOOD | >80% EXCELLENT
--   - Purchase rate: <5% POOR | 5-15% AVG | 15-25% GOOD | >25% EXCELLENT
--   - Revenue/send: <$0.50 POOR | $0.50-1.50 AVG | $1.50-3.00 GOOD | >$3.00 EXCELLENT

-- Overall PPV metrics
WITH overall_metrics AS (
    SELECT
        COUNT(*) AS total_ppvs,
        SUM(earnings) AS total_revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(view_rate) * 100, 1) AS view_rate_pct,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate_pct,
        ROUND(AVG(revenue_per_send), 3) AS avg_rps,
        ROUND(AVG(price), 2) AS avg_price,
        MIN(sending_time) AS first_ppv_date,
        MAX(sending_time) AS last_ppv_date,
        SUM(sent_count) AS total_sent,
        SUM(purchased_count) AS total_purchased
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
),

-- Monthly trend analysis (last 6 months)
monthly_trends AS (
    SELECT
        strftime('%Y-%m', sending_time) AS month,
        COUNT(*) AS ppv_count,
        SUM(earnings) AS revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate,
        ROUND(AVG(revenue_per_send), 2) AS rps
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
    GROUP BY strftime('%Y-%m', sending_time)
    ORDER BY month DESC
    LIMIT 6
),

-- Week-over-week comparison
weekly_comparison AS (
    SELECT
        'current_week' AS period,
        COUNT(*) AS ppvs,
        SUM(earnings) AS revenue,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate,
        ROUND(AVG(revenue_per_send), 2) AS rps
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
      AND sending_time >= date('now', '-7 days')

    UNION ALL

    SELECT
        'previous_week' AS period,
        COUNT(*) AS ppvs,
        SUM(earnings) AS revenue,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate,
        ROUND(AVG(revenue_per_send), 2) AS rps
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
      AND sending_time >= date('now', '-14 days')
      AND sending_time < date('now', '-7 days')
)

-- Combine all results with section identifiers
SELECT
    'overall' AS section,
    NULL AS sort_order,
    om.total_ppvs AS metric_int,
    om.total_revenue AS metric_float,
    om.avg_earnings AS metric_float2,
    om.view_rate_pct AS rate1,
    om.purchase_rate_pct AS rate2,
    om.avg_rps AS rate3,
    om.avg_price AS price,
    CASE
        WHEN om.view_rate_pct > 80 THEN 'EXCELLENT'
        WHEN om.view_rate_pct >= 60 THEN 'GOOD'
        WHEN om.view_rate_pct >= 40 THEN 'AVG'
        ELSE 'POOR'
    END AS view_rate_rating,
    CASE
        WHEN om.purchase_rate_pct > 25 THEN 'EXCELLENT'
        WHEN om.purchase_rate_pct >= 15 THEN 'GOOD'
        WHEN om.purchase_rate_pct >= 5 THEN 'AVG'
        ELSE 'POOR'
    END AS purchase_rate_rating,
    CASE
        WHEN om.avg_rps > 3.00 THEN 'EXCELLENT'
        WHEN om.avg_rps >= 1.50 THEN 'GOOD'
        WHEN om.avg_rps >= 0.50 THEN 'AVG'
        ELSE 'POOR'
    END AS rps_rating
FROM overall_metrics om

UNION ALL

SELECT
    'monthly' AS section,
    ROW_NUMBER() OVER (ORDER BY mt.month DESC) AS sort_order,
    mt.ppv_count AS metric_int,
    mt.revenue AS metric_float,
    mt.avg_earnings AS metric_float2,
    mt.purchase_rate AS rate1,
    mt.rps AS rate2,
    NULL AS rate3,
    NULL AS price,
    mt.month AS view_rate_rating,
    NULL AS purchase_rate_rating,
    NULL AS rps_rating
FROM monthly_trends mt

UNION ALL

SELECT
    'weekly_comparison' AS section,
    CASE WHEN wc.period = 'current_week' THEN 1 ELSE 2 END AS sort_order,
    wc.ppvs AS metric_int,
    wc.revenue AS metric_float,
    NULL AS metric_float2,
    wc.purchase_rate AS rate1,
    wc.rps AS rate2,
    NULL AS rate3,
    NULL AS price,
    wc.period AS view_rate_rating,
    NULL AS purchase_rate_rating,
    NULL AS rps_rating
FROM weekly_comparison wc

ORDER BY
    CASE section
        WHEN 'overall' THEN 1
        WHEN 'monthly' THEN 2
        WHEN 'weekly_comparison' THEN 3
    END,
    sort_order;
