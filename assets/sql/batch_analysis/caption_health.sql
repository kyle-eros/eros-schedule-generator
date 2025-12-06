-- caption_health.sql
-- Phase 7: Caption Intelligence Analysis
-- Caption library health, top performers, underperformers, and tone effectiveness.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Caption health metrics, top/bottom performers, and tone analysis

-- Caption library health summary
WITH caption_health_summary AS (
    SELECT
        COUNT(*) AS total_captions,
        ROUND(AVG(cb.freshness_score), 1) AS avg_freshness,
        SUM(CASE WHEN cb.freshness_score < 25 THEN 1 ELSE 0 END) AS critical_stale,
        SUM(CASE WHEN cb.freshness_score < 30 THEN 1 ELSE 0 END) AS stale,
        SUM(CASE WHEN cb.freshness_score >= 30 AND cb.freshness_score < 50 THEN 1 ELSE 0 END) AS needs_refresh,
        SUM(CASE WHEN cb.freshness_score >= 50 AND cb.freshness_score < 80 THEN 1 ELSE 0 END) AS good,
        SUM(CASE WHEN cb.freshness_score >= 80 THEN 1 ELSE 0 END) AS fresh,
        ROUND(AVG(ccp.avg_earnings), 2) AS avg_caption_earnings
    FROM caption_creator_performance ccp
    JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
    WHERE ccp.creator_id = ?
      AND cb.is_active = 1
),

-- Top performing captions (top 10)
top_captions AS (
    SELECT
        cb.caption_id,
        SUBSTR(cb.caption_text, 1, 60) AS preview,
        cb.tone,
        cb.caption_type,
        ROUND(cb.performance_score, 1) AS performance_score,
        ROUND(cb.freshness_score, 1) AS freshness_score,
        ccp.times_used,
        ROUND(ccp.avg_earnings, 2) AS avg_earnings,
        ROUND(ccp.total_earnings, 2) AS total_earnings
    FROM caption_creator_performance ccp
    JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
    WHERE ccp.creator_id = ?
      AND cb.is_active = 1
    ORDER BY ccp.avg_earnings DESC
    LIMIT 10
),

-- Underperforming captions (bottom 10 with usage)
bottom_captions AS (
    SELECT
        cb.caption_id,
        SUBSTR(cb.caption_text, 1, 50) AS preview,
        cb.tone,
        ccp.times_used,
        ROUND(ccp.avg_earnings, 2) AS avg_earnings,
        ROUND(cb.freshness_score, 1) AS freshness_score,
        CASE
            WHEN ccp.times_used >= 5 AND ccp.avg_earnings < 20 THEN 'RETIRE'
            WHEN ccp.times_used >= 3 AND ccp.avg_earnings < 30 THEN 'REVIEW'
            ELSE 'MONITOR'
        END AS recommendation
    FROM caption_creator_performance ccp
    JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
    WHERE ccp.creator_id = ?
      AND cb.is_active = 1
      AND ccp.times_used >= 3
    ORDER BY ccp.avg_earnings ASC
    LIMIT 10
),

-- Tone effectiveness analysis
tone_effectiveness AS (
    SELECT
        cb.tone,
        COUNT(*) AS count,
        ROUND(AVG(ccp.avg_earnings), 2) AS avg_earnings,
        ROUND(AVG(cb.freshness_score), 1) AS avg_freshness,
        SUM(ccp.times_used) AS total_uses
    FROM caption_creator_performance ccp
    JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
    WHERE ccp.creator_id = ?
      AND cb.tone IS NOT NULL
      AND cb.is_active = 1
    GROUP BY cb.tone
    HAVING COUNT(*) >= 2
)

-- Health summary section
SELECT
    'health_summary' AS section,
    NULL AS caption_id,
    NULL AS preview,
    NULL AS tone,
    chs.total_captions AS metric_int1,
    chs.fresh AS metric_int2,
    chs.stale AS metric_int3,
    chs.critical_stale AS metric_int4,
    chs.avg_freshness AS metric_float1,
    chs.avg_caption_earnings AS metric_float2,
    NULL AS recommendation,
    1 AS sort_order
FROM caption_health_summary chs

UNION ALL

-- Top captions section
SELECT
    'top_performers' AS section,
    tc.caption_id,
    tc.preview,
    tc.tone,
    tc.times_used AS metric_int1,
    tc.performance_score AS metric_int2,
    tc.freshness_score AS metric_int3,
    NULL AS metric_int4,
    tc.avg_earnings AS metric_float1,
    tc.total_earnings AS metric_float2,
    NULL AS recommendation,
    ROW_NUMBER() OVER (ORDER BY tc.avg_earnings DESC) AS sort_order
FROM top_captions tc

UNION ALL

-- Bottom captions section
SELECT
    'underperformers' AS section,
    bc.caption_id,
    bc.preview,
    bc.tone,
    bc.times_used AS metric_int1,
    NULL AS metric_int2,
    bc.freshness_score AS metric_int3,
    NULL AS metric_int4,
    bc.avg_earnings AS metric_float1,
    NULL AS metric_float2,
    bc.recommendation,
    ROW_NUMBER() OVER (ORDER BY bc.avg_earnings ASC) AS sort_order
FROM bottom_captions bc

UNION ALL

-- Tone effectiveness section
SELECT
    'tone_effectiveness' AS section,
    NULL AS caption_id,
    NULL AS preview,
    te.tone,
    te.count AS metric_int1,
    te.total_uses AS metric_int2,
    NULL AS metric_int3,
    NULL AS metric_int4,
    te.avg_earnings AS metric_float1,
    te.avg_freshness AS metric_float2,
    NULL AS recommendation,
    ROW_NUMBER() OVER (ORDER BY te.avg_earnings DESC) AS sort_order
FROM tone_effectiveness te

ORDER BY
    CASE section
        WHEN 'health_summary' THEN 1
        WHEN 'top_performers' THEN 2
        WHEN 'underperformers' THEN 3
        WHEN 'tone_effectiveness' THEN 4
    END,
    sort_order;
