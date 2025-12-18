-- Migration: 003_volume_performance.sql
-- Phase 3: Volume performance tracking and adaptive learning
-- Created: 2025-11-30
--
-- This migration adds the volume_performance_tracking table for tracking
-- performance metrics over time, enabling adaptive volume optimization:
-- - Performance metrics calculation (revenue, view rate, purchase rate)
-- - Trend analysis (comparison to previous periods)
-- - Saturation and opportunity scoring
-- - Historical performance tracking
-- - Recommendation generation

-- ============================================================================
-- TABLE: volume_performance_tracking
-- ============================================================================
-- Stores calculated performance metrics for creators over specific time periods.
-- Each row represents a performance snapshot for a creator at a specific date
-- and tracking period (7d, 14d, 30d), enabling trend analysis and adaptive learning.

CREATE TABLE IF NOT EXISTS volume_performance_tracking (
    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    tracking_date TEXT NOT NULL,
    tracking_period TEXT NOT NULL CHECK (tracking_period IN ('7d', '14d', '30d')),

    -- Volume Metrics
    avg_daily_volume REAL NOT NULL,
    total_messages_sent INTEGER DEFAULT 0,

    -- Performance Metrics
    avg_revenue_per_send REAL DEFAULT 0.0,
    avg_view_rate REAL DEFAULT 0.0,
    avg_purchase_rate REAL DEFAULT 0.0,
    total_earnings REAL DEFAULT 0.0,

    -- Trend Indicators (% change vs previous period)
    revenue_per_send_trend REAL DEFAULT 0.0,
    view_rate_trend REAL DEFAULT 0.0,
    purchase_rate_trend REAL DEFAULT 0.0,
    earnings_volatility REAL DEFAULT 0.0,

    -- Adaptive Signals
    saturation_score REAL DEFAULT 0.0 CHECK (saturation_score >= 0 AND saturation_score <= 100),
    opportunity_score REAL DEFAULT 0.0 CHECK (opportunity_score >= 0 AND opportunity_score <= 100),
    recommended_volume_delta INTEGER DEFAULT 0,

    -- Metadata
    calculated_at TEXT DEFAULT (datetime('now')),

    -- Foreign key to creators table (cascade delete for cleanup)
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,

    -- Ensure one record per creator/date/period combination
    UNIQUE(creator_id, tracking_date, tracking_period)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Index for time-series queries (most recent performance first)
CREATE INDEX IF NOT EXISTS idx_vpt_creator_date
ON volume_performance_tracking(creator_id, tracking_date DESC);

-- Index for finding high-signal recommendations
CREATE INDEX IF NOT EXISTS idx_vpt_signals
ON volume_performance_tracking(saturation_score DESC, opportunity_score DESC);

-- Index for tracking period analysis
CREATE INDEX IF NOT EXISTS idx_vpt_period
ON volume_performance_tracking(tracking_period, tracking_date DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: v_volume_recommendations
-- Provides actionable recommendations by joining performance tracking
-- with current volume assignments. Filters for high-signal opportunities.
CREATE VIEW IF NOT EXISTS v_volume_recommendations AS
SELECT
    vpt.*,
    va.volume_level as current_volume_level,
    va.ppv_per_day as current_ppv,
    c.page_name,
    c.display_name,
    c.current_active_fans
FROM volume_performance_tracking vpt
JOIN v_current_volume_assignments va ON vpt.creator_id = va.creator_id
JOIN creators c ON vpt.creator_id = c.creator_id
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

-- View: v_performance_trends
-- Shows performance trends for all creators with latest metrics
CREATE VIEW IF NOT EXISTS v_performance_trends AS
SELECT
    vpt.creator_id,
    c.page_name,
    c.display_name,
    va.volume_level,
    vpt.tracking_period,
    vpt.tracking_date,
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
    vpt.opportunity_score
FROM volume_performance_tracking vpt
JOIN creators c ON vpt.creator_id = c.creator_id
JOIN v_current_volume_assignments va ON vpt.creator_id = va.creator_id
WHERE vpt.tracking_date = (
    SELECT MAX(tracking_date)
    FROM volume_performance_tracking
    WHERE creator_id = vpt.creator_id
      AND tracking_period = vpt.tracking_period
)
ORDER BY c.page_name, vpt.tracking_period;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================
--
-- Post-migration steps:
-- 1. Run initial performance analysis for creators with historical data
-- 2. Verify indexes are being used with EXPLAIN QUERY PLAN
-- 3. Set up periodic analysis jobs (daily/weekly)
-- 4. Monitor signal quality and adjust thresholds as needed
--
-- Algorithm parameters (embedded in service layer):
-- - Saturation score: Detects declining performance
--   * Base: 50/100
--   * +20 if revenue_per_send declining > 15%
--   * +15 if view_rate declining > 10%
--   * +10 if purchase_rate declining > 10%
--   * +15 if earnings volatility > 0.6
--
-- - Opportunity score: Detects growth potential
--   * Base: 50/100
--   * +20 if revenue_per_send > baseline * 1.15
--   * +15 if view_rate growing > 5%
--   * +10 if purchase_rate > 5%
--   * +15 if fan_count growing > 10%
--
-- Rollback strategy:
-- DROP VIEW IF EXISTS v_performance_trends;
-- DROP VIEW IF EXISTS v_volume_recommendations;
-- DROP INDEX IF EXISTS idx_vpt_period;
-- DROP INDEX IF EXISTS idx_vpt_signals;
-- DROP INDEX IF EXISTS idx_vpt_creator_date;
-- DROP TABLE IF EXISTS volume_performance_tracking;
