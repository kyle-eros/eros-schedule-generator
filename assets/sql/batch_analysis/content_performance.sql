-- content_performance.sql
-- Phase 5: Content Type Performance Analysis
-- Content ranking and gap analysis comparing vault vs usage.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Performance by content type and content gap analysis

-- Content performance ranking
WITH content_perf AS (
    SELECT
        ct.content_type_id,
        ct.type_name,
        ct.type_category,
        COUNT(mm.message_id) AS uses,
        SUM(mm.earnings) AS total_revenue,
        ROUND(AVG(mm.earnings), 2) AS avg_earnings,
        ROUND(AVG(mm.view_rate) * 100, 1) AS view_rate_pct,
        ROUND(AVG(mm.purchase_rate) * 100, 1) AS purchase_rate_pct,
        ROUND(AVG(mm.price), 2) AS avg_price,
        ROUND(AVG(mm.revenue_per_send), 3) AS avg_rps
    FROM mass_messages mm
    JOIN content_types ct ON mm.content_type_id = ct.content_type_id
    WHERE mm.creator_id = ?
      AND mm.message_type = 'ppv'
    GROUP BY ct.content_type_id
),

-- Content gap analysis (vault vs usage)
content_gaps AS (
    SELECT
        ct.content_type_id,
        ct.type_name,
        ct.type_category,
        COALESCE(vm.has_content, 0) AS in_vault,
        COALESCE(vm.quantity_available, 0) AS quantity,
        vm.quality_rating,
        COALESCE(cp.uses, 0) AS times_used,
        cp.avg_earnings,
        CASE
            WHEN vm.has_content = 1 AND COALESCE(cp.uses, 0) = 0 THEN 'UNTAPPED'
            WHEN vm.has_content = 0 AND COALESCE(cp.avg_earnings, 0) > 50 THEN 'NEEDS_CONTENT'
            WHEN COALESCE(cp.uses, 0) > 15 AND COALESCE(cp.avg_earnings, 0) < 30 THEN 'OVERUSED'
            WHEN vm.has_content = 1 AND COALESCE(cp.uses, 0) > 0 AND COALESCE(cp.avg_earnings, 0) >= 50 THEN 'HIGH_PERFORMER'
            WHEN vm.has_content = 1 AND COALESCE(cp.uses, 0) > 0 THEN 'ACTIVE'
            ELSE 'INACTIVE'
        END AS status
    FROM content_types ct
    LEFT JOIN vault_matrix vm ON ct.content_type_id = vm.content_type_id
        AND vm.creator_id = ?
    LEFT JOIN content_perf cp ON ct.content_type_id = cp.content_type_id
)

-- Content performance section
SELECT
    'performance' AS section,
    cp.type_name,
    cp.type_category,
    cp.uses,
    cp.total_revenue,
    cp.avg_earnings,
    cp.view_rate_pct,
    cp.purchase_rate_pct,
    cp.avg_price,
    cp.avg_rps,
    NULL AS in_vault,
    NULL AS quantity,
    NULL AS quality_rating,
    NULL AS status,
    RANK() OVER (ORDER BY cp.avg_earnings DESC) AS rank_by_earnings
FROM content_perf cp

UNION ALL

-- Content gap section
SELECT
    'gap_analysis' AS section,
    cg.type_name,
    cg.type_category,
    cg.times_used AS uses,
    NULL AS total_revenue,
    cg.avg_earnings,
    NULL AS view_rate_pct,
    NULL AS purchase_rate_pct,
    NULL AS avg_price,
    NULL AS avg_rps,
    cg.in_vault,
    cg.quantity,
    cg.quality_rating,
    cg.status,
    CASE cg.status
        WHEN 'UNTAPPED' THEN 1
        WHEN 'NEEDS_CONTENT' THEN 2
        WHEN 'OVERUSED' THEN 3
        WHEN 'HIGH_PERFORMER' THEN 4
        WHEN 'ACTIVE' THEN 5
        ELSE 6
    END AS rank_by_earnings
FROM content_gaps cg
WHERE cg.status IN ('UNTAPPED', 'NEEDS_CONTENT', 'OVERUSED', 'HIGH_PERFORMER')

ORDER BY
    CASE section WHEN 'performance' THEN 1 ELSE 2 END,
    rank_by_earnings;
