-- ============================================================================
-- Migration 011: Transition from Static to Dynamic Volume Assignments
-- ============================================================================
--
-- Purpose:
--   Replace static volume_assignments table with dynamic calculation based on
--   real-time creator metrics (fan_count, page_type, saturation/opportunity scores).
--   Volume levels are now computed on-demand during schedule generation.
--
-- Changes:
--   1. Archive existing volume_assignments for audit trail
--   2. Create volume_calculation_log table for tracking dynamic calculations
--   3. Add performance index on volume_performance_tracking
--   4. Drop views dependent on volume_assignments
--   5. Recreate v_performance_trends without volume_assignments dependency
--   6. Update v_schedule_ready_creators to use dynamic calculation
--   7. (Manual) Drop volume_assignments table after verification
--
-- Rollback Strategy:
--   1. Restore volume_assignments from volume_assignments_archived
--   2. Recreate original views from backup definitions below
--   3. Drop new tables/views created by this migration
--
-- Author: EROS System
-- Date: 2025-12-16
-- Version: 1.0.0
-- ============================================================================

-- ============================================================================
-- SECTION 0: Pre-Migration Validation
-- ============================================================================
-- Run these queries BEFORE migration to verify current state:
--
-- SELECT COUNT(*) as total_assignments FROM volume_assignments;
-- SELECT COUNT(*) as active_assignments FROM volume_assignments WHERE is_active = 1;
-- SELECT volume_level, COUNT(*) as count FROM volume_assignments WHERE is_active = 1 GROUP BY volume_level;
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: Archive Existing Assignments
-- ============================================================================
-- Preserves full audit trail of all historical volume assignments
-- Includes timestamp of when archive was created

CREATE TABLE IF NOT EXISTS volume_assignments_archived AS
SELECT
    assignment_id,
    creator_id,
    volume_level,
    ppv_per_day,
    bump_per_day,
    assigned_at,
    assigned_by,
    assigned_reason,
    is_active,
    notes,
    datetime('now') as archived_at,
    '011_dynamic_volume' as migration_source
FROM volume_assignments;

-- Verify archive was created successfully
-- Expected: Same count as original table
-- SELECT COUNT(*) FROM volume_assignments_archived;

-- ============================================================================
-- SECTION 2: Create Volume Calculation Log Table
-- ============================================================================
-- Lightweight audit table for tracking dynamic volume calculations
-- Links calculations to schedule generations for traceability

CREATE TABLE IF NOT EXISTS volume_calculation_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    calculated_at TEXT DEFAULT (datetime('now')),

    -- Input metrics used for calculation
    fan_count INTEGER,
    page_type TEXT CHECK (page_type IN ('paid', 'free')),
    saturation_score REAL CHECK (saturation_score IS NULL OR (saturation_score >= 0 AND saturation_score <= 100)),
    opportunity_score REAL CHECK (opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 100)),

    -- Calculated outputs
    tier TEXT CHECK (tier IN ('low', 'mid', 'high', 'ultra')),
    revenue_per_day INTEGER CHECK (revenue_per_day IS NULL OR revenue_per_day >= 0),
    engagement_per_day INTEGER CHECK (engagement_per_day IS NULL OR engagement_per_day >= 0),
    retention_per_day INTEGER CHECK (retention_per_day IS NULL OR retention_per_day >= 0),

    -- Relationship to schedule that used this calculation
    schedule_template_id INTEGER,

    -- Metadata for debugging and analysis
    data_source TEXT DEFAULT 'dynamic' CHECK (data_source IN ('dynamic', 'cached_tracking', 'calculated_on_demand', 'fallback')),
    calculation_version TEXT DEFAULT '1.0',
    notes TEXT,

    -- Foreign keys
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);

-- Index for efficient lookups by creator and date (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_vcl_creator_date
ON volume_calculation_log(creator_id, calculated_at DESC);

-- Index for finding calculations linked to specific schedules
CREATE INDEX IF NOT EXISTS idx_vcl_schedule
ON volume_calculation_log(schedule_template_id)
WHERE schedule_template_id IS NOT NULL;

-- Index for tier-based analysis
CREATE INDEX IF NOT EXISTS idx_vcl_tier
ON volume_calculation_log(tier, calculated_at DESC);

-- ============================================================================
-- SECTION 3: Add Missing Index on volume_performance_tracking
-- ============================================================================
-- Optimizes lookups by creator_id + tracking_period + tracking_date
-- This is the primary query pattern for fetching latest performance data

CREATE INDEX IF NOT EXISTS idx_vpt_creator_period_date
ON volume_performance_tracking(creator_id, tracking_period, tracking_date DESC);

-- ============================================================================
-- SECTION 4: Drop Dependent Views
-- ============================================================================
-- These views reference volume_assignments and must be dropped before table removal
-- Original definitions preserved in comments for rollback

-- Original v_volume_recommendations:
-- CREATE VIEW v_volume_recommendations AS
-- SELECT
--     vpt.*,
--     va.volume_level as current_volume_level,
--     va.ppv_per_day as current_ppv,
--     c.page_name,
--     c.display_name,
--     c.current_active_fans
-- FROM volume_performance_tracking vpt
-- JOIN v_current_volume_assignments va ON vpt.creator_id = va.creator_id
-- JOIN creators c ON vpt.creator_id = c.creator_id
-- WHERE vpt.tracking_period = '14d'
--   AND (vpt.saturation_score > 70 OR vpt.opportunity_score > 70)
--   AND vpt.tracking_date = (
--       SELECT MAX(tracking_date)
--       FROM volume_performance_tracking
--       WHERE creator_id = vpt.creator_id
--         AND tracking_period = '14d'
--   )
-- ORDER BY
--     CASE
--         WHEN vpt.saturation_score > 70 THEN vpt.saturation_score
--         ELSE vpt.opportunity_score
--     END DESC;

DROP VIEW IF EXISTS v_volume_recommendations;

-- Original v_performance_trends:
-- CREATE VIEW v_performance_trends AS
-- SELECT
--     vpt.creator_id,
--     c.page_name,
--     c.display_name,
--     va.volume_level,
--     vpt.tracking_period,
--     vpt.tracking_date,
--     vpt.avg_daily_volume,
--     vpt.total_messages_sent,
--     vpt.avg_revenue_per_send,
--     vpt.avg_view_rate,
--     vpt.avg_purchase_rate,
--     vpt.total_earnings,
--     vpt.revenue_per_send_trend,
--     vpt.view_rate_trend,
--     vpt.purchase_rate_trend,
--     vpt.earnings_volatility,
--     vpt.saturation_score,
--     vpt.opportunity_score
-- FROM volume_performance_tracking vpt
-- JOIN creators c ON vpt.creator_id = c.creator_id
-- JOIN v_current_volume_assignments va ON vpt.creator_id = va.creator_id
-- WHERE vpt.tracking_date = (
--     SELECT MAX(tracking_date)
--     FROM volume_performance_tracking
--     WHERE creator_id = vpt.creator_id
--       AND tracking_period = vpt.tracking_period
-- )
-- ORDER BY c.page_name, vpt.tracking_period;

DROP VIEW IF EXISTS v_performance_trends;

-- Original v_current_volume_assignments:
-- CREATE VIEW v_current_volume_assignments AS
-- SELECT
--     va.assignment_id,
--     va.creator_id,
--     va.volume_level,
--     va.ppv_per_day,
--     va.bump_per_day,
--     va.assigned_at,
--     va.assigned_by,
--     va.assigned_reason,
--     va.notes,
--     c.page_name,
--     c.display_name,
--     c.page_type,
--     c.current_active_fans,
--     c.performance_tier,
--     c.current_total_earnings
-- FROM volume_assignments va
-- JOIN creators c ON va.creator_id = c.creator_id
-- WHERE va.is_active = 1
-- ORDER BY c.page_name;

DROP VIEW IF EXISTS v_current_volume_assignments;

-- Original v_volume_assignment_stats:
-- CREATE VIEW v_volume_assignment_stats AS
-- SELECT
--     volume_level,
--     COUNT(*) as creator_count,
--     AVG(ppv_per_day) as avg_ppv_per_day,
--     AVG(bump_per_day) as avg_bump_per_day,
--     AVG(c.current_active_fans) as avg_fans,
--     SUM(c.current_total_earnings) as total_earnings
-- FROM volume_assignments va
-- JOIN creators c ON va.creator_id = c.creator_id
-- WHERE va.is_active = 1
-- GROUP BY volume_level
-- ORDER BY
--     CASE volume_level
--         WHEN 'Low' THEN 1
--         WHEN 'Mid' THEN 2
--         WHEN 'High' THEN 3
--         WHEN 'Ultra' THEN 4
--     END;

DROP VIEW IF EXISTS v_volume_assignment_stats;

-- Original v_schedule_ready_creators references volume_assignments
-- Will be recreated with dynamic calculation logic

DROP VIEW IF EXISTS v_schedule_ready_creators;

-- ============================================================================
-- SECTION 5: Recreate v_performance_trends WITHOUT volume_assignments
-- ============================================================================
-- Now pulls all data from volume_performance_tracking and creators tables
-- No longer depends on static volume assignments

CREATE VIEW IF NOT EXISTS v_performance_trends AS
SELECT
    vpt.tracking_id,
    vpt.creator_id,
    vpt.tracking_date,
    vpt.tracking_period,
    vpt.avg_daily_volume,
    vpt.total_messages_sent,
    vpt.avg_revenue_per_send,
    vpt.avg_view_rate,
    vpt.avg_purchase_rate,
    vpt.total_earnings,
    vpt.revenue_per_send_trend,
    vpt.view_rate_trend,
    vpt.purchase_rate_trend,
    vpt.earnings_volatility,
    vpt.saturation_score,
    vpt.opportunity_score,
    vpt.recommended_volume_delta,
    c.page_name,
    c.display_name,
    c.current_active_fans,
    c.page_type,
    c.performance_tier
FROM volume_performance_tracking vpt
JOIN creators c ON vpt.creator_id = c.creator_id
WHERE vpt.tracking_date = (
    SELECT MAX(tracking_date)
    FROM volume_performance_tracking
    WHERE creator_id = vpt.creator_id
    AND tracking_period = vpt.tracking_period
);

-- ============================================================================
-- SECTION 6: Recreate v_volume_recommendations WITHOUT volume_assignments
-- ============================================================================
-- Uses volume_calculation_log for recent calculations instead of static assignments

CREATE VIEW IF NOT EXISTS v_volume_recommendations AS
SELECT
    vpt.tracking_id,
    vpt.creator_id,
    vpt.tracking_date,
    vpt.tracking_period,
    vpt.avg_daily_volume,
    vpt.total_messages_sent,
    vpt.avg_revenue_per_send,
    vpt.avg_view_rate,
    vpt.avg_purchase_rate,
    vpt.total_earnings,
    vpt.revenue_per_send_trend,
    vpt.view_rate_trend,
    vpt.purchase_rate_trend,
    vpt.earnings_volatility,
    vpt.saturation_score,
    vpt.opportunity_score,
    vpt.recommended_volume_delta,
    -- Dynamic volume info from most recent calculation (if exists)
    vcl.tier as current_volume_tier,
    vcl.revenue_per_day as current_revenue_sends,
    vcl.engagement_per_day as current_engagement_sends,
    vcl.retention_per_day as current_retention_sends,
    c.page_name,
    c.display_name,
    c.current_active_fans,
    c.page_type
FROM volume_performance_tracking vpt
JOIN creators c ON vpt.creator_id = c.creator_id
LEFT JOIN (
    SELECT
        creator_id,
        tier,
        revenue_per_day,
        engagement_per_day,
        retention_per_day
    FROM volume_calculation_log
    WHERE log_id IN (
        SELECT MAX(log_id)
        FROM volume_calculation_log
        GROUP BY creator_id
    )
) vcl ON vpt.creator_id = vcl.creator_id
WHERE vpt.tracking_period = '14d'
  AND (vpt.saturation_score > 70 OR vpt.opportunity_score > 70)
  AND vpt.tracking_date = (
      SELECT MAX(tracking_date)
      FROM volume_performance_tracking
      WHERE creator_id = vpt.creator_id
        AND tracking_period = '14d'
  )
ORDER BY
    CASE
        WHEN vpt.saturation_score > 70 THEN vpt.saturation_score
        ELSE vpt.opportunity_score
    END DESC;

-- ============================================================================
-- SECTION 7: Recreate v_schedule_ready_creators with Dynamic Calculation
-- ============================================================================
-- Uses fan count brackets to dynamically determine volume tier
-- Matches the logic in the schedule generator skill

CREATE VIEW IF NOT EXISTS v_schedule_ready_creators AS
WITH caption_stats AS (
    -- Aggregate caption counts per creator
    SELECT
        cb.creator_id,
        COUNT(*) AS available_captions,
        SUM(
            CASE
                WHEN COALESCE(cb.freshness_score, 100.0) >= 30.0
                     AND COALESCE(cb.performance_score, 50.0) >= 40.0
                     AND cb.is_active = 1
                THEN 1
                ELSE 0
            END
        ) AS fresh_captions
    FROM caption_bank cb
    WHERE cb.is_active = 1
    GROUP BY cb.creator_id
),
dynamic_volume AS (
    -- Calculate dynamic volume tier based on fan count
    -- Thresholds: low (<500), mid (500-2000), high (2000-5000), ultra (5000+)
    SELECT
        c.creator_id,
        CASE
            WHEN c.current_active_fans < 500 THEN 'low'
            WHEN c.current_active_fans < 2000 THEN 'mid'
            WHEN c.current_active_fans < 5000 THEN 'high'
            ELSE 'ultra'
        END AS volume_tier,
        -- Revenue sends per day by tier
        CASE
            WHEN c.current_active_fans < 500 THEN 2
            WHEN c.current_active_fans < 2000 THEN 3
            WHEN c.current_active_fans < 5000 THEN 4
            ELSE 5
        END AS revenue_per_day,
        -- Engagement sends per day by tier
        CASE
            WHEN c.current_active_fans < 500 THEN 2
            WHEN c.current_active_fans < 2000 THEN 3
            WHEN c.current_active_fans < 5000 THEN 4
            ELSE 5
        END AS engagement_per_day,
        -- Retention sends per day (only for paid pages)
        CASE
            WHEN c.page_type = 'free' THEN 0
            WHEN c.current_active_fans < 500 THEN 1
            WHEN c.current_active_fans < 2000 THEN 1
            WHEN c.current_active_fans < 5000 THEN 2
            ELSE 2
        END AS retention_per_day
    FROM creators c
    WHERE c.is_active = 1
)
SELECT
    -- Creator identification
    c.creator_id,
    c.page_name,
    c.display_name,
    c.page_type,
    c.performance_tier,
    c.current_active_fans,

    -- Dynamic volume details
    dv.volume_tier AS volume_level,
    dv.revenue_per_day,
    dv.engagement_per_day,
    dv.retention_per_day,
    (dv.revenue_per_day + dv.engagement_per_day + dv.retention_per_day) AS total_sends_per_day,

    -- Persona details
    COALESCE(cp.primary_tone, 'unknown') AS primary_tone,
    COALESCE(cp.emoji_frequency, 'moderate') AS emoji_frequency,
    cp.slang_level,

    -- Caption availability metrics
    COALESCE(cs.available_captions, 0) AS available_captions,
    COALESCE(cs.fresh_captions, 0) AS fresh_captions,

    -- Caption readiness classification (based on revenue sends only for PPV coverage)
    CASE
        WHEN dv.revenue_per_day = 0 THEN 'no_volume'
        WHEN COALESCE(cs.fresh_captions, 0) >= (dv.revenue_per_day * 7) THEN 'ready'
        WHEN COALESCE(cs.fresh_captions, 0) >= (dv.revenue_per_day * 3) THEN 'limited'
        ELSE 'insufficient'
    END AS caption_readiness,

    -- Readiness calculation details
    dv.revenue_per_day * 7 AS captions_needed_full_week,
    dv.revenue_per_day * 3 AS captions_needed_minimum,

    -- Overall schedule readiness flag
    CASE
        WHEN c.is_active = 1
             AND COALESCE(cs.fresh_captions, 0) >= (dv.revenue_per_day * 3)
        THEN 1
        ELSE 0
    END AS is_schedule_ready

FROM creators c
JOIN dynamic_volume dv ON c.creator_id = dv.creator_id
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
LEFT JOIN caption_stats cs ON c.creator_id = cs.creator_id
WHERE c.is_active = 1
ORDER BY
    c.performance_tier ASC,
    c.current_active_fans DESC;

-- ============================================================================
-- SECTION 8: Create v_dynamic_volume_assignments (replacement for legacy view)
-- ============================================================================
-- Provides backward compatibility for any code expecting v_current_volume_assignments
-- Uses dynamic calculation instead of static table

CREATE VIEW IF NOT EXISTS v_dynamic_volume_assignments AS
SELECT
    c.creator_id,
    -- Dynamic tier calculation
    CASE
        WHEN c.current_active_fans < 500 THEN 'Low'
        WHEN c.current_active_fans < 2000 THEN 'Mid'
        WHEN c.current_active_fans < 5000 THEN 'High'
        ELSE 'Ultra'
    END AS volume_level,
    -- Dynamic PPV per day (maps to revenue sends)
    CASE
        WHEN c.current_active_fans < 500 THEN 2
        WHEN c.current_active_fans < 2000 THEN 3
        WHEN c.current_active_fans < 5000 THEN 4
        ELSE 5
    END AS ppv_per_day,
    -- Dynamic bump per day (maps to engagement sends)
    CASE
        WHEN c.current_active_fans < 500 THEN 2
        WHEN c.current_active_fans < 2000 THEN 3
        WHEN c.current_active_fans < 5000 THEN 4
        ELSE 5
    END AS bump_per_day,
    -- Retention per day (new field, only for paid)
    CASE
        WHEN c.page_type = 'free' THEN 0
        WHEN c.current_active_fans < 500 THEN 1
        WHEN c.current_active_fans < 2000 THEN 1
        WHEN c.current_active_fans < 5000 THEN 2
        ELSE 2
    END AS retention_per_day,
    -- Metadata
    'dynamic' AS assigned_by,
    'fan_count_bracket' AS assigned_reason,
    datetime('now') AS calculated_at,
    -- Creator details
    c.page_name,
    c.display_name,
    c.page_type,
    c.current_active_fans,
    c.performance_tier,
    c.current_total_earnings
FROM creators c
WHERE c.is_active = 1
ORDER BY c.page_name;

COMMIT;

-- ============================================================================
-- SECTION 9: Drop Legacy Table (MANUAL EXECUTION REQUIRED)
-- ============================================================================
-- CAUTION: Execute ONLY after verifying:
--   1. Archive contains all expected records
--   2. New views are functioning correctly
--   3. MCP tools have been updated to use dynamic calculation
--   4. No application code references volume_assignments directly
--
-- Verification queries to run before dropping:
--
-- -- Check archive completeness
-- SELECT
--     (SELECT COUNT(*) FROM volume_assignments) as original_count,
--     (SELECT COUNT(*) FROM volume_assignments_archived) as archived_count;
--
-- -- Verify new views work
-- SELECT COUNT(*) FROM v_performance_trends;
-- SELECT COUNT(*) FROM v_dynamic_volume_assignments;
-- SELECT COUNT(*) FROM v_schedule_ready_creators;
--
-- -- Test dynamic calculation matches expected distribution
-- SELECT
--     volume_level,
--     COUNT(*) as creator_count,
--     AVG(ppv_per_day) as avg_ppv,
--     AVG(bump_per_day) as avg_bump
-- FROM v_dynamic_volume_assignments
-- GROUP BY volume_level
-- ORDER BY
--     CASE volume_level
--         WHEN 'Low' THEN 1
--         WHEN 'Mid' THEN 2
--         WHEN 'High' THEN 3
--         WHEN 'Ultra' THEN 4
--     END;
--
-- ONLY after all verifications pass, run:
-- DROP TABLE IF EXISTS volume_assignments;

-- ============================================================================
-- POST-MIGRATION VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to confirm success:

-- 1. Verify archive was created with all records
-- SELECT COUNT(*) as archived_records FROM volume_assignments_archived;

-- 2. Verify new log table exists and is empty
-- SELECT COUNT(*) as log_entries FROM volume_calculation_log;

-- 3. Verify new index exists
-- SELECT name FROM sqlite_master
-- WHERE type='index' AND name='idx_vpt_creator_period_date';

-- 4. Verify views were recreated
-- SELECT name FROM sqlite_master
-- WHERE type='view' AND name IN (
--     'v_performance_trends',
--     'v_volume_recommendations',
--     'v_schedule_ready_creators',
--     'v_dynamic_volume_assignments'
-- );

-- 5. Test v_performance_trends returns data
-- SELECT COUNT(*) FROM v_performance_trends;

-- 6. Test v_schedule_ready_creators with dynamic volumes
-- SELECT page_name, volume_level, revenue_per_day, caption_readiness
-- FROM v_schedule_ready_creators
-- LIMIT 5;

-- 7. Compare dynamic tier distribution to archived static assignments
-- SELECT
--     'Dynamic' as source,
--     volume_level,
--     COUNT(*) as count
-- FROM v_dynamic_volume_assignments
-- GROUP BY volume_level
-- UNION ALL
-- SELECT
--     'Archived' as source,
--     volume_level,
--     COUNT(*) as count
-- FROM volume_assignments_archived
-- WHERE is_active = 1
-- GROUP BY volume_level
-- ORDER BY source,
--     CASE volume_level
--         WHEN 'Low' THEN 1
--         WHEN 'Mid' THEN 2
--         WHEN 'High' THEN 3
--         WHEN 'Ultra' THEN 4
--     END;

-- ============================================================================
-- ROLLBACK SCRIPT
-- ============================================================================
-- If rollback is needed, execute the following in order:
--
-- BEGIN TRANSACTION;
--
-- -- 1. Drop new views
-- DROP VIEW IF EXISTS v_dynamic_volume_assignments;
-- DROP VIEW IF EXISTS v_schedule_ready_creators;
-- DROP VIEW IF EXISTS v_volume_recommendations;
-- DROP VIEW IF EXISTS v_performance_trends;
--
-- -- 2. Restore original views (definitions preserved in Section 4 comments)
-- -- [Copy view definitions from Section 4 comments]
--
-- -- 3. Restore volume_assignments from archive (if dropped)
-- -- CREATE TABLE volume_assignments AS
-- -- SELECT
-- --     assignment_id, creator_id, volume_level, ppv_per_day, bump_per_day,
-- --     assigned_at, assigned_by, assigned_reason, is_active, notes
-- -- FROM volume_assignments_archived;
--
-- -- 4. Drop new tables
-- DROP TABLE IF EXISTS volume_calculation_log;
--
-- -- 5. Remove new index
-- DROP INDEX IF EXISTS idx_vpt_creator_period_date;
--
-- COMMIT;
-- ============================================================================
