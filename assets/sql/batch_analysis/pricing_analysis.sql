-- pricing_analysis.sql
-- Phase 6: Pricing Strategy Analysis
-- Price tier performance and optimal pricing by content type.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Performance by price tier and optimal price by content type
--
-- Pricing Psychology Notes:
--   - Use .99 endings (increases conversion 24%)
--   - Sweet spots: $4.99, $9.99, $14.99, $19.99
--   - Test ceiling per fan incrementally
--   - Premium content: 50-100% above baseline

-- Price tier performance
WITH price_tiers AS (
    SELECT
        CASE
            WHEN price <= 5 THEN '$1-5'
            WHEN price <= 10 THEN '$6-10'
            WHEN price <= 15 THEN '$11-15'
            WHEN price <= 20 THEN '$16-20'
            WHEN price <= 25 THEN '$21-25'
            WHEN price <= 30 THEN '$26-30'
            ELSE '$30+'
        END AS price_tier,
        MIN(price) AS tier_min_price,
        COUNT(*) AS count,
        SUM(earnings) AS total_revenue,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS purchase_rate_pct,
        ROUND(AVG(revenue_per_send), 3) AS rps,
        ROUND(AVG(view_rate) * 100, 1) AS view_rate_pct
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
      AND price > 0
    GROUP BY
        CASE
            WHEN price <= 5 THEN '$1-5'
            WHEN price <= 10 THEN '$6-10'
            WHEN price <= 15 THEN '$11-15'
            WHEN price <= 20 THEN '$16-20'
            WHEN price <= 25 THEN '$21-25'
            WHEN price <= 30 THEN '$26-30'
            ELSE '$30+'
        END
),

-- Optimal price by content type
optimal_by_content AS (
    SELECT
        ct.type_name,
        ct.type_category,
        ROUND(AVG(mm.price), 2) AS avg_price,
        ROUND(AVG(mm.earnings), 2) AS avg_earnings,
        ROUND(AVG(mm.purchase_rate) * 100, 1) AS purchase_rate_pct,
        COUNT(*) AS sample_size,
        -- Calculate price elasticity zone
        CASE
            WHEN AVG(mm.purchase_rate) > 0.20 THEN 'CAN_INCREASE'
            WHEN AVG(mm.purchase_rate) < 0.08 THEN 'CONSIDER_DECREASE'
            ELSE 'OPTIMAL_RANGE'
        END AS pricing_recommendation
    FROM mass_messages mm
    JOIN content_types ct ON mm.content_type_id = ct.content_type_id
    WHERE mm.creator_id = ?
      AND mm.message_type = 'ppv'
      AND mm.price > 0
    GROUP BY ct.content_type_id
    HAVING COUNT(*) >= 3
),

-- Price sensitivity analysis (compare low vs high price performance)
price_sensitivity AS (
    SELECT
        CASE WHEN price <= 15 THEN 'low_price' ELSE 'high_price' END AS price_segment,
        COUNT(*) AS count,
        ROUND(AVG(earnings), 2) AS avg_earnings,
        ROUND(AVG(purchase_rate) * 100, 1) AS avg_purchase_rate,
        ROUND(SUM(earnings), 2) AS total_revenue
    FROM mass_messages
    WHERE creator_id = ?
      AND message_type = 'ppv'
      AND price > 0
    GROUP BY CASE WHEN price <= 15 THEN 'low_price' ELSE 'high_price' END
)

-- Price tier section
SELECT
    'price_tier' AS section,
    pt.price_tier AS key_text,
    pt.count,
    pt.total_revenue,
    pt.avg_earnings,
    pt.purchase_rate_pct,
    pt.rps,
    pt.view_rate_pct,
    NULL AS pricing_recommendation,
    pt.tier_min_price AS sort_key
FROM price_tiers pt

UNION ALL

-- Optimal by content section
SELECT
    'optimal_by_content' AS section,
    oc.type_name AS key_text,
    oc.sample_size AS count,
    NULL AS total_revenue,
    oc.avg_earnings,
    oc.purchase_rate_pct,
    NULL AS rps,
    NULL AS view_rate_pct,
    oc.pricing_recommendation,
    oc.avg_earnings AS sort_key
FROM optimal_by_content oc

UNION ALL

-- Price sensitivity section
SELECT
    'sensitivity' AS section,
    ps.price_segment AS key_text,
    ps.count,
    ps.total_revenue,
    ps.avg_earnings,
    ps.avg_purchase_rate AS purchase_rate_pct,
    NULL AS rps,
    NULL AS view_rate_pct,
    NULL AS pricing_recommendation,
    CASE ps.price_segment WHEN 'low_price' THEN 1 ELSE 2 END AS sort_key
FROM price_sensitivity ps

ORDER BY
    CASE section
        WHEN 'price_tier' THEN 1
        WHEN 'optimal_by_content' THEN 2
        WHEN 'sensitivity' THEN 3
    END,
    sort_key;
