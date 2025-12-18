-- ============================================================================
-- Migration 012: Volume Learning Infrastructure
-- ============================================================================
--
-- Purpose:
--   Create closed-loop learning infrastructure to track volume adjustment
--   outcomes and enable algorithm self-improvement over time.
--
-- Changes:
--   1. volume_adjustment_outcomes - Links adjustments to performance results
--   2. day_of_week_performance - Per-creator DOW multipliers
--   3. volume_predictions - Prediction tracking for accuracy measurement
--   4. v_caption_pool_summary - Caption availability view
--   5. v_prediction_accuracy - Algorithm accuracy dashboard
--   6. Alter volume_calculation_log with new columns
--
-- Dependencies:
--   - Migration 011: volume_calculation_log table must exist
--   - Tables: creators, schedule_templates, caption_bank, send_types,
--             send_type_caption_requirements
--
-- Author: EROS System
-- Date: 2025-12-16
-- Version: 1.0.0
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: Volume Adjustment Outcomes Table
-- ============================================================================
-- Tracks the actual performance outcome after a volume adjustment was applied.
-- Links volume calculations to schedule template performance.

CREATE TABLE IF NOT EXISTS volume_adjustment_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Link to the volume calculation that was applied
    log_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,

    -- When this outcome was measured
    measured_at TEXT DEFAULT (datetime('now')),
    measurement_period TEXT CHECK (measurement_period IN ('7d', '14d', '30d')) DEFAULT '14d',

    -- Input metrics at time of volume calculation
    input_saturation_score REAL,
    input_opportunity_score REAL,
    input_tier TEXT,
    input_revenue_per_day INTEGER,
    input_engagement_per_day INTEGER,
    input_retention_per_day INTEGER,

    -- Outcome metrics after schedule execution
    outcome_saturation_score REAL,
    outcome_opportunity_score REAL,
    outcome_revenue_per_send REAL,
    outcome_total_revenue REAL,
    outcome_view_rate REAL,
    outcome_purchase_rate REAL,
    outcome_messages_sent INTEGER,

    -- Calculated deltas (outcome - input baseline)
    saturation_delta REAL,
    opportunity_delta REAL,
    revenue_per_send_change_pct REAL,

    -- Success classification
    -- 'improved': saturation down OR opportunity up OR revenue up
    -- 'degraded': saturation up AND revenue down
    -- 'neutral': no significant change
    outcome_classification TEXT CHECK (outcome_classification IN ('improved', 'degraded', 'neutral')),

    -- Learning signal: -1.0 to 1.0 adjustment recommendation
    -- Negative = reduce volume next time
    -- Positive = increase volume next time
    learning_signal REAL CHECK (learning_signal >= -1.0 AND learning_signal <= 1.0),

    -- Whether this outcome has been incorporated into algorithm updates
    applied_to_learning INTEGER DEFAULT 0 CHECK (applied_to_learning IN (0, 1)),
    applied_at TEXT,

    -- Foreign keys
    FOREIGN KEY (log_id) REFERENCES volume_calculation_log(log_id) ON DELETE CASCADE,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- Index for finding unapplied learning signals
CREATE INDEX IF NOT EXISTS idx_vao_learning_pending
ON volume_adjustment_outcomes(applied_to_learning, creator_id)
WHERE applied_to_learning = 0;

-- Index for creator outcome history
CREATE INDEX IF NOT EXISTS idx_vao_creator_date
ON volume_adjustment_outcomes(creator_id, measured_at DESC);

-- Index for log_id lookups (foreign key optimization)
CREATE INDEX IF NOT EXISTS idx_vao_log_id
ON volume_adjustment_outcomes(log_id);

-- ============================================================================
-- SECTION 2: Day-of-Week Performance Table
-- ============================================================================
-- Stores per-creator day-of-week performance multipliers.
-- Updated periodically from historical mass_messages data.

CREATE TABLE IF NOT EXISTS day_of_week_performance (
    dow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- Last calculation timestamp
    calculated_at TEXT DEFAULT (datetime('now')),
    lookback_days INTEGER DEFAULT 90,

    -- Day of week (0=Monday, 6=Sunday)
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6),

    -- Performance metrics for this day
    message_count INTEGER DEFAULT 0,
    avg_revenue_per_send REAL DEFAULT 0.0,
    avg_view_rate REAL DEFAULT 0.0,
    avg_purchase_rate REAL DEFAULT 0.0,
    total_earnings REAL DEFAULT 0.0,

    -- Relative performance vs weekly average
    -- 1.0 = average, >1.0 = better than average, <1.0 = worse
    relative_rps_multiplier REAL DEFAULT 1.0,

    -- Volume adjustment multiplier derived from relative performance
    -- Used to increase/decrease volume for this day
    volume_multiplier REAL DEFAULT 1.0 CHECK (volume_multiplier >= 0.5 AND volume_multiplier <= 1.5),

    -- Confidence in this multiplier (based on sample size)
    confidence_score REAL DEFAULT 0.5 CHECK (confidence_score >= 0 AND confidence_score <= 1.0),

    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    UNIQUE(creator_id, day_of_week)
);

-- Index for fast DOW lookup per creator
CREATE INDEX IF NOT EXISTS idx_dow_creator
ON day_of_week_performance(creator_id, day_of_week);

-- Index for finding stale DOW calculations
CREATE INDEX IF NOT EXISTS idx_dow_calculated_at
ON day_of_week_performance(calculated_at);

-- ============================================================================
-- SECTION 3: Volume Predictions Table
-- ============================================================================
-- Tracks predictions vs actual outcomes for algorithm accuracy measurement.

CREATE TABLE IF NOT EXISTS volume_predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- When prediction was made
    predicted_at TEXT DEFAULT (datetime('now')),

    -- Prediction inputs
    input_fan_count INTEGER,
    input_page_type TEXT,
    input_saturation REAL,
    input_opportunity REAL,

    -- Predictions
    predicted_tier TEXT,
    predicted_revenue_per_day INTEGER,
    predicted_engagement_per_day INTEGER,
    predicted_retention_per_day INTEGER,
    predicted_weekly_revenue REAL,  -- Estimated revenue from this volume
    predicted_weekly_messages INTEGER,

    -- Linked schedule (if generated)
    schedule_template_id INTEGER,
    week_start_date TEXT,

    -- Actual outcomes (filled after execution)
    actual_total_revenue REAL,
    actual_messages_sent INTEGER,
    actual_avg_rps REAL,
    outcome_measured INTEGER DEFAULT 0 CHECK (outcome_measured IN (0, 1)),
    outcome_measured_at TEXT,

    -- Prediction accuracy metrics (filled when outcome measured)
    revenue_prediction_error_pct REAL,  -- (actual - predicted) / predicted * 100
    volume_prediction_error_pct REAL,   -- Difference in messages sent vs predicted

    -- Algorithm version that made this prediction
    algorithm_version TEXT DEFAULT '2.0',

    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);

-- Index for finding unmeasured predictions
CREATE INDEX IF NOT EXISTS idx_vp_unmeasured
ON volume_predictions(outcome_measured, predicted_at)
WHERE outcome_measured = 0;

-- Index for accuracy analysis by creator
CREATE INDEX IF NOT EXISTS idx_vp_creator_accuracy
ON volume_predictions(creator_id, predicted_at DESC)
WHERE outcome_measured = 1;

-- Index for schedule template lookups
CREATE INDEX IF NOT EXISTS idx_vp_schedule_template
ON volume_predictions(schedule_template_id)
WHERE schedule_template_id IS NOT NULL;

-- Index for week-based analysis
CREATE INDEX IF NOT EXISTS idx_vp_week_start
ON volume_predictions(week_start_date);

-- ============================================================================
-- SECTION 4: Caption Pool Summary View
-- ============================================================================
-- Provides at-a-glance caption availability per creator per send type.
-- Note: Using DROP VIEW IF EXISTS followed by CREATE VIEW for idempotency
-- since SQLite does not support CREATE OR REPLACE VIEW.

DROP VIEW IF EXISTS v_caption_pool_summary;

CREATE VIEW v_caption_pool_summary AS
WITH caption_counts AS (
    SELECT
        cb.creator_id,
        st.send_type_key,
        st.category,
        COUNT(*) as total_captions,
        SUM(CASE WHEN cb.is_active = 1 THEN 1 ELSE 0 END) as active_captions,
        SUM(CASE
            WHEN cb.is_active = 1
                AND COALESCE(cb.freshness_score, 100) >= 30
            THEN 1 ELSE 0
        END) as fresh_captions,
        SUM(CASE
            WHEN cb.is_active = 1
                AND COALESCE(cb.freshness_score, 100) >= 30
                AND COALESCE(cb.performance_score, 50) >= 40
            THEN 1 ELSE 0
        END) as usable_captions,
        AVG(COALESCE(cb.freshness_score, 100)) as avg_freshness,
        AVG(COALESCE(cb.performance_score, 50)) as avg_performance
    FROM caption_bank cb
    LEFT JOIN send_type_caption_requirements stcr ON cb.caption_type = stcr.caption_type
    LEFT JOIN send_types st ON stcr.send_type_id = st.send_type_id
    WHERE st.is_active = 1
    GROUP BY cb.creator_id, st.send_type_key, st.category
)
SELECT
    cc.creator_id,
    c.page_name,
    cc.send_type_key,
    cc.category,
    cc.total_captions,
    cc.active_captions,
    cc.fresh_captions,
    cc.usable_captions,
    ROUND(cc.avg_freshness, 1) as avg_freshness,
    ROUND(cc.avg_performance, 1) as avg_performance,
    -- Sufficiency rating
    CASE
        WHEN cc.usable_captions >= 14 THEN 'abundant'   -- 2 weeks worth
        WHEN cc.usable_captions >= 7 THEN 'sufficient'  -- 1 week worth
        WHEN cc.usable_captions >= 3 THEN 'limited'     -- few days
        ELSE 'critical'                                  -- needs attention
    END as availability_status
FROM caption_counts cc
JOIN creators c ON cc.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY cc.creator_id, cc.category, cc.send_type_key;

-- ============================================================================
-- SECTION 5: Prediction Accuracy View
-- ============================================================================
-- Dashboard view for algorithm accuracy tracking.

DROP VIEW IF EXISTS v_prediction_accuracy;

CREATE VIEW v_prediction_accuracy AS
SELECT
    vp.creator_id,
    c.page_name,
    c.display_name,
    COUNT(*) as total_predictions,
    SUM(CASE WHEN vp.outcome_measured = 1 THEN 1 ELSE 0 END) as measured_predictions,

    -- Revenue prediction accuracy
    AVG(CASE WHEN vp.outcome_measured = 1 THEN ABS(vp.revenue_prediction_error_pct) END) as avg_revenue_error_pct,
    MIN(CASE WHEN vp.outcome_measured = 1 THEN vp.revenue_prediction_error_pct END) as min_revenue_error,
    MAX(CASE WHEN vp.outcome_measured = 1 THEN vp.revenue_prediction_error_pct END) as max_revenue_error,

    -- Volume prediction accuracy
    AVG(CASE WHEN vp.outcome_measured = 1 THEN ABS(vp.volume_prediction_error_pct) END) as avg_volume_error_pct,

    -- Directional accuracy (did we predict the right direction?)
    SUM(CASE
        WHEN vp.outcome_measured = 1
            AND vp.predicted_weekly_revenue > 0
            AND vp.actual_total_revenue > 0
            AND SIGN(vp.actual_total_revenue - vp.predicted_weekly_revenue) = SIGN(vp.predicted_weekly_revenue)
        THEN 1 ELSE 0
    END) * 100.0 / NULLIF(SUM(CASE WHEN vp.outcome_measured = 1 THEN 1 ELSE 0 END), 0) as directional_accuracy_pct,

    -- Recent trend (last 30 days)
    AVG(CASE
        WHEN vp.outcome_measured = 1
            AND vp.predicted_at >= datetime('now', '-30 days')
        THEN ABS(vp.revenue_prediction_error_pct)
    END) as recent_avg_error_pct,

    -- Algorithm version distribution
    GROUP_CONCAT(DISTINCT vp.algorithm_version) as algorithm_versions

FROM volume_predictions vp
JOIN creators c ON vp.creator_id = c.creator_id
GROUP BY vp.creator_id, c.page_name, c.display_name
HAVING total_predictions > 0
ORDER BY avg_revenue_error_pct ASC NULLS LAST;

-- ============================================================================
-- SECTION 6: Alter volume_calculation_log with new columns
-- ============================================================================
-- Add columns for enhanced tracking (SQLite ALTER TABLE limitations require
-- individual statements and cannot use IF NOT EXISTS, so we use a workaround)
--
-- Note: These ALTER TABLE statements will fail if the columns already exist.
-- This is expected behavior - the migration should be run once, but the
-- IF NOT EXISTS on tables/indexes provides partial idempotency.

-- Add confidence_score for tracking calculation confidence
-- Range: 0.0 (low confidence) to 1.0 (high confidence)
ALTER TABLE volume_calculation_log ADD COLUMN confidence_score REAL
    CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1.0));

-- Add caption_constrained flag for when volume was limited by caption availability
ALTER TABLE volume_calculation_log ADD COLUMN caption_constrained INTEGER DEFAULT 0
    CHECK (caption_constrained IN (0, 1));

-- Add message_count_analyzed for tracking data basis
-- Records how many historical messages were used for saturation/opportunity calculation
ALTER TABLE volume_calculation_log ADD COLUMN message_count_analyzed INTEGER;

-- Add multi_horizon flag for when multi-period analysis was used (7d + 14d + 30d)
ALTER TABLE volume_calculation_log ADD COLUMN multi_horizon_used INTEGER DEFAULT 0
    CHECK (multi_horizon_used IN (0, 1));

-- Add dow_adjusted flag for when day-of-week adjustment was applied
ALTER TABLE volume_calculation_log ADD COLUMN dow_adjusted INTEGER DEFAULT 0
    CHECK (dow_adjusted IN (0, 1));

-- Add elasticity_capped flag for when elasticity model capped volume
-- Indicates volume was reduced due to diminishing returns detection
ALTER TABLE volume_calculation_log ADD COLUMN elasticity_capped INTEGER DEFAULT 0
    CHECK (elasticity_capped IN (0, 1));

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================
-- Run these queries to verify migration success:

-- 1. Verify new tables exist
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN (
--     'volume_adjustment_outcomes',
--     'day_of_week_performance',
--     'volume_predictions'
-- );

-- 2. Verify new views exist
-- SELECT name FROM sqlite_master WHERE type='view' AND name IN (
--     'v_caption_pool_summary',
--     'v_prediction_accuracy'
-- );

-- 3. Verify new columns in volume_calculation_log
-- PRAGMA table_info(volume_calculation_log);

-- 4. Test caption pool summary view (should return data if captions exist)
-- SELECT * FROM v_caption_pool_summary LIMIT 5;

-- 5. Check new indexes exist
-- SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_vao%';
-- SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_dow%';
-- SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_vp%';

-- 6. Verify table row counts (all should be 0 initially)
-- SELECT
--     (SELECT COUNT(*) FROM volume_adjustment_outcomes) as outcomes,
--     (SELECT COUNT(*) FROM day_of_week_performance) as dow_perf,
--     (SELECT COUNT(*) FROM volume_predictions) as predictions;
