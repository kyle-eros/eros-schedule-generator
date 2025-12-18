-- =============================================================================
-- EROS Schedule Generator - Volume Dashboard Views
-- =============================================================================
-- Purpose: SQL views supporting Volume Optimization Dashboard KPIs
-- Version: 1.0.0
-- Created: 2025-12-17
--
-- These views calculate metrics for monitoring schedule generation quality,
-- constraint compliance, and prediction accuracy.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- VIEW: v_campaign_frequency_adherence
-- -----------------------------------------------------------------------------
-- Purpose: Calculates compliance with send type frequency rules per creator
--
-- Checks three constraint types:
--   1. max_per_day - Maximum sends of this type per day
--   2. max_per_week - Maximum sends of this type per week
--   3. min_hours_between - Minimum gap between consecutive sends
--
-- Target: >= 90% compliance
-- Alert: < 75% compliance
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_campaign_frequency_adherence AS
WITH daily_send_counts AS (
    -- Count sends per creator, per send type, per day
    SELECT
        si.creator_id,
        si.scheduled_date,
        st.send_type_key,
        st.send_type_id,
        st.max_per_day,
        st.max_per_week,
        st.min_hours_between,
        COUNT(*) AS daily_count
    FROM schedule_items si
    JOIN send_types st ON si.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si.template_id = stp.template_id
    WHERE stp.status IN ('approved', 'queued', 'completed')
      AND st.is_active = 1
    GROUP BY si.creator_id, si.scheduled_date, st.send_type_key, st.send_type_id
),
weekly_send_counts AS (
    -- Count sends per creator, per send type, per week
    SELECT
        si.creator_id,
        stp.week_start,
        st.send_type_key,
        st.send_type_id,
        st.max_per_week,
        COUNT(*) AS weekly_count
    FROM schedule_items si
    JOIN send_types st ON si.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si.template_id = stp.template_id
    WHERE stp.status IN ('approved', 'queued', 'completed')
      AND st.is_active = 1
      AND st.max_per_week IS NOT NULL
    GROUP BY si.creator_id, stp.week_start, st.send_type_key, st.send_type_id
),
time_gap_violations AS (
    -- Identify violations of min_hours_between constraint
    SELECT
        si1.creator_id,
        si1.scheduled_date,
        st.send_type_key,
        COUNT(*) AS gap_violations
    FROM schedule_items si1
    JOIN schedule_items si2 ON si1.creator_id = si2.creator_id
        AND si1.send_type_id = si2.send_type_id
        AND si1.item_id < si2.item_id
        AND si1.scheduled_date = si2.scheduled_date
    JOIN send_types st ON si1.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si1.template_id = stp.template_id
    WHERE stp.status IN ('approved', 'queued', 'completed')
      AND st.min_hours_between IS NOT NULL
      AND (
          (julianday(si2.scheduled_date || ' ' || si2.scheduled_time) -
           julianday(si1.scheduled_date || ' ' || si1.scheduled_time)) * 24
      ) < st.min_hours_between
    GROUP BY si1.creator_id, si1.scheduled_date, st.send_type_key
),
daily_violations AS (
    -- Identify max_per_day violations
    SELECT
        creator_id,
        scheduled_date,
        send_type_key,
        daily_count,
        max_per_day,
        CASE WHEN daily_count > COALESCE(max_per_day, 999) THEN 1 ELSE 0 END AS is_violation
    FROM daily_send_counts
),
weekly_violations AS (
    -- Identify max_per_week violations
    SELECT
        creator_id,
        week_start,
        send_type_key,
        weekly_count,
        max_per_week,
        CASE WHEN weekly_count > max_per_week THEN 1 ELSE 0 END AS is_violation
    FROM weekly_send_counts
)
SELECT
    c.creator_id,
    c.page_name,
    c.display_name,
    -- Daily constraint compliance
    COUNT(DISTINCT dv.scheduled_date || '-' || dv.send_type_key) AS total_daily_checks,
    SUM(dv.is_violation) AS daily_violations,
    -- Weekly constraint compliance
    COALESCE((SELECT COUNT(*) FROM weekly_violations wv WHERE wv.creator_id = c.creator_id), 0) AS weekly_violation_count,
    -- Time gap compliance
    COALESCE((SELECT SUM(gap_violations) FROM time_gap_violations tgv WHERE tgv.creator_id = c.creator_id), 0) AS time_gap_violations,
    -- Overall compliance rate
    ROUND(
        100.0 * (
            1.0 - (
                (COALESCE(SUM(dv.is_violation), 0) +
                 COALESCE((SELECT SUM(is_violation) FROM weekly_violations wv WHERE wv.creator_id = c.creator_id), 0) +
                 COALESCE((SELECT SUM(gap_violations) FROM time_gap_violations tgv WHERE tgv.creator_id = c.creator_id), 0))
                / NULLIF(COUNT(DISTINCT dv.scheduled_date || '-' || dv.send_type_key) +
                         COALESCE((SELECT COUNT(*) FROM weekly_violations wv WHERE wv.creator_id = c.creator_id), 0), 0)
            )
        ), 2
    ) AS compliance_rate_pct,
    -- Status indicator
    CASE
        WHEN (SUM(dv.is_violation) +
              COALESCE((SELECT SUM(is_violation) FROM weekly_violations wv WHERE wv.creator_id = c.creator_id), 0)) = 0
        THEN 'compliant'
        WHEN ROUND(100.0 * (1.0 - (SUM(dv.is_violation) / NULLIF(COUNT(*), 0))), 2) >= 75
        THEN 'warning'
        ELSE 'critical'
    END AS status
FROM creators c
LEFT JOIN daily_violations dv ON c.creator_id = dv.creator_id
WHERE c.is_active = 1
GROUP BY c.creator_id, c.page_name, c.display_name
ORDER BY compliance_rate_pct ASC NULLS LAST;


-- -----------------------------------------------------------------------------
-- VIEW: v_volume_prediction_accuracy
-- -----------------------------------------------------------------------------
-- Purpose: Aggregates prediction accuracy metrics from volume_predictions
--
-- Calculates Mean Absolute Percentage Error (MAPE) for:
--   - Revenue predictions
--   - Volume (message count) predictions
--
-- Target: MAPE < 15%
-- Alert: MAPE > 25%
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_volume_prediction_accuracy AS
WITH measured_predictions AS (
    -- Only include predictions that have been measured
    SELECT
        vp.prediction_id,
        vp.creator_id,
        vp.predicted_at,
        vp.week_start_date,
        vp.predicted_weekly_revenue,
        vp.predicted_weekly_messages,
        vp.actual_total_revenue,
        vp.actual_messages_sent,
        vp.revenue_prediction_error_pct,
        vp.volume_prediction_error_pct,
        vp.algorithm_version,
        -- Calculate absolute percentage errors
        ABS(vp.revenue_prediction_error_pct) AS abs_revenue_error,
        ABS(vp.volume_prediction_error_pct) AS abs_volume_error
    FROM volume_predictions vp
    WHERE vp.outcome_measured = 1
      AND vp.actual_total_revenue > 0  -- Avoid division by zero
      AND vp.predicted_at >= datetime('now', '-90 days')  -- Last 90 days only
),
creator_accuracy AS (
    -- Calculate per-creator accuracy metrics
    SELECT
        mp.creator_id,
        COUNT(*) AS prediction_count,
        -- Revenue MAPE
        ROUND(AVG(mp.abs_revenue_error), 2) AS revenue_mape,
        -- Volume MAPE
        ROUND(AVG(mp.abs_volume_error), 2) AS volume_mape,
        -- Best and worst predictions
        MIN(mp.abs_revenue_error) AS best_revenue_prediction,
        MAX(mp.abs_revenue_error) AS worst_revenue_prediction,
        -- Recent trend (last 30 days vs previous)
        ROUND(AVG(CASE WHEN mp.predicted_at >= datetime('now', '-30 days')
                       THEN mp.abs_revenue_error END), 2) AS recent_mape,
        ROUND(AVG(CASE WHEN mp.predicted_at < datetime('now', '-30 days')
                       THEN mp.abs_revenue_error END), 2) AS prior_mape,
        -- Algorithm versions used
        GROUP_CONCAT(DISTINCT mp.algorithm_version) AS algorithm_versions,
        -- Latest prediction date
        MAX(mp.week_start_date) AS latest_prediction_week
    FROM measured_predictions mp
    GROUP BY mp.creator_id
)
SELECT
    ca.creator_id,
    c.page_name,
    c.display_name,
    ca.prediction_count,
    ca.revenue_mape,
    ca.volume_mape,
    ca.best_revenue_prediction,
    ca.worst_revenue_prediction,
    ca.recent_mape,
    ca.prior_mape,
    -- Trend direction
    CASE
        WHEN ca.recent_mape IS NULL OR ca.prior_mape IS NULL THEN 'insufficient_data'
        WHEN ca.recent_mape < ca.prior_mape THEN 'improving'
        WHEN ca.recent_mape > ca.prior_mape THEN 'degrading'
        ELSE 'stable'
    END AS accuracy_trend,
    -- Status based on MAPE thresholds
    CASE
        WHEN ca.revenue_mape <= 15 THEN 'on_target'
        WHEN ca.revenue_mape <= 25 THEN 'warning'
        ELSE 'critical'
    END AS status,
    ca.algorithm_versions,
    ca.latest_prediction_week
FROM creator_accuracy ca
JOIN creators c ON ca.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY ca.revenue_mape ASC;


-- -----------------------------------------------------------------------------
-- VIEW: v_bump_ratio_compliance
-- -----------------------------------------------------------------------------
-- Purpose: Evaluates daily bump-to-PPV ratios against acceptable thresholds
--
-- Acceptable ratio range: 1.0 to 2.0 (bumps per PPV)
-- - Ratio < 1.0: Under-engaging, may lead to perceived spam
-- - Ratio > 2.0: Over-engaging, may dilute monetization
--
-- Target: >= 85% of days compliant
-- Alert: < 70% of days compliant
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_bump_ratio_compliance AS
WITH daily_category_counts AS (
    -- Count sends by category (revenue vs engagement) per creator per day
    SELECT
        si.creator_id,
        si.scheduled_date,
        st.category,
        COUNT(*) AS send_count
    FROM schedule_items si
    JOIN send_types st ON si.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si.template_id = stp.template_id
    WHERE stp.status IN ('approved', 'queued', 'completed')
      AND st.is_active = 1
      AND st.category IN ('revenue', 'engagement')
    GROUP BY si.creator_id, si.scheduled_date, st.category
),
daily_ratios AS (
    -- Pivot to get revenue and engagement counts side by side
    SELECT
        creator_id,
        scheduled_date,
        COALESCE(SUM(CASE WHEN category = 'engagement' THEN send_count END), 0) AS bump_count,
        COALESCE(SUM(CASE WHEN category = 'revenue' THEN send_count END), 0) AS ppv_count,
        -- Calculate ratio (bumps per PPV)
        CASE
            WHEN SUM(CASE WHEN category = 'revenue' THEN send_count END) > 0
            THEN ROUND(
                CAST(SUM(CASE WHEN category = 'engagement' THEN send_count END) AS REAL) /
                SUM(CASE WHEN category = 'revenue' THEN send_count END),
                2
            )
            ELSE NULL  -- No PPVs scheduled
        END AS bump_ppv_ratio
    FROM daily_category_counts
    GROUP BY creator_id, scheduled_date
),
compliance_check AS (
    SELECT
        dr.creator_id,
        dr.scheduled_date,
        dr.bump_count,
        dr.ppv_count,
        dr.bump_ppv_ratio,
        -- Compliance check: ratio between 1.0 and 2.0
        CASE
            WHEN dr.ppv_count = 0 THEN NULL  -- Exclude days with no PPVs
            WHEN dr.bump_ppv_ratio >= 1.0 AND dr.bump_ppv_ratio <= 2.0 THEN 1
            ELSE 0
        END AS is_compliant,
        -- Detailed status
        CASE
            WHEN dr.ppv_count = 0 THEN 'no_ppv'
            WHEN dr.bump_ppv_ratio < 1.0 THEN 'under_engaged'
            WHEN dr.bump_ppv_ratio > 2.0 THEN 'over_engaged'
            ELSE 'compliant'
        END AS ratio_status
    FROM daily_ratios dr
)
SELECT
    cc.creator_id,
    c.page_name,
    c.display_name,
    -- Daily detail (for drill-down)
    cc.scheduled_date,
    cc.bump_count,
    cc.ppv_count,
    cc.bump_ppv_ratio,
    cc.is_compliant,
    cc.ratio_status
FROM compliance_check cc
JOIN creators c ON cc.creator_id = c.creator_id
WHERE c.is_active = 1
  AND cc.ppv_count > 0  -- Only include days with PPVs
ORDER BY cc.creator_id, cc.scheduled_date DESC;


-- -----------------------------------------------------------------------------
-- VIEW: v_bump_ratio_compliance_summary
-- -----------------------------------------------------------------------------
-- Purpose: Aggregated compliance summary per creator for dashboard display
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_bump_ratio_compliance_summary AS
SELECT
    creator_id,
    page_name,
    display_name,
    COUNT(*) AS total_days,
    SUM(is_compliant) AS compliant_days,
    ROUND(100.0 * SUM(is_compliant) / COUNT(*), 2) AS compliance_rate_pct,
    ROUND(AVG(bump_ppv_ratio), 2) AS avg_ratio,
    MIN(bump_ppv_ratio) AS min_ratio,
    MAX(bump_ppv_ratio) AS max_ratio,
    -- Status based on compliance rate thresholds
    CASE
        WHEN ROUND(100.0 * SUM(is_compliant) / COUNT(*), 2) >= 85 THEN 'on_target'
        WHEN ROUND(100.0 * SUM(is_compliant) / COUNT(*), 2) >= 70 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_bump_ratio_compliance
GROUP BY creator_id, page_name, display_name
ORDER BY compliance_rate_pct ASC;


-- -----------------------------------------------------------------------------
-- VIEW: v_followup_limit_utilization
-- -----------------------------------------------------------------------------
-- Purpose: Tracks utilization of the 4-per-day PPV followup capacity
--
-- Target: 75-100% utilization
-- Alert: < 50% utilization (missed revenue opportunities)
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_followup_limit_utilization AS
WITH daily_followups AS (
    SELECT
        si.creator_id,
        si.scheduled_date,
        COUNT(*) AS followup_count,
        4 AS max_followups  -- System-defined limit
    FROM schedule_items si
    JOIN send_types st ON si.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si.template_id = stp.template_id
    WHERE st.send_type_key = 'ppv_followup'
      AND stp.status IN ('approved', 'queued', 'completed')
    GROUP BY si.creator_id, si.scheduled_date
)
SELECT
    df.creator_id,
    c.page_name,
    c.display_name,
    df.scheduled_date,
    df.followup_count,
    df.max_followups,
    ROUND(100.0 * df.followup_count / df.max_followups, 2) AS utilization_pct,
    -- Status based on utilization thresholds
    CASE
        WHEN df.followup_count >= 3 THEN 'optimal'  -- 75%+
        WHEN df.followup_count >= 2 THEN 'acceptable'  -- 50%+
        ELSE 'underutilized'  -- < 50%
    END AS status
FROM daily_followups df
JOIN creators c ON df.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY df.creator_id, df.scheduled_date DESC;


-- -----------------------------------------------------------------------------
-- VIEW: v_weekly_limit_violations
-- -----------------------------------------------------------------------------
-- Purpose: Detects breaches of weekly limits on VIP program and Snapchat bundle
--
-- Target: 0 violations
-- Alert: > 0 violations (requires immediate investigation)
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_weekly_limit_violations AS
WITH weekly_counts AS (
    SELECT
        si.creator_id,
        stp.week_start,
        st.send_type_key,
        st.max_per_week,
        COUNT(*) AS actual_count
    FROM schedule_items si
    JOIN send_types st ON si.send_type_id = st.send_type_id
    JOIN schedule_templates stp ON si.template_id = stp.template_id
    WHERE st.send_type_key IN ('vip_program', 'snapchat_bundle')
      AND st.max_per_week IS NOT NULL
      AND stp.status IN ('draft', 'approved', 'queued', 'completed')
    GROUP BY si.creator_id, stp.week_start, st.send_type_key, st.max_per_week
)
SELECT
    wc.creator_id,
    c.page_name,
    c.display_name,
    wc.week_start,
    wc.send_type_key,
    wc.max_per_week,
    wc.actual_count,
    wc.actual_count - wc.max_per_week AS excess_count,
    CASE
        WHEN wc.actual_count > wc.max_per_week THEN 'VIOLATION'
        ELSE 'compliant'
    END AS status
FROM weekly_counts wc
JOIN creators c ON wc.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY
    CASE WHEN wc.actual_count > wc.max_per_week THEN 0 ELSE 1 END,
    wc.week_start DESC;


-- -----------------------------------------------------------------------------
-- VIEW: v_game_type_revenue_variance
-- -----------------------------------------------------------------------------
-- Purpose: Measures earnings consistency across game post configurations
--
-- Uses Coefficient of Variation (CV = StdDev / Mean)
-- Target: CV < 0.50 (consistent performance)
-- Alert: CV > 0.75 (high variance, investigate)
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_game_type_revenue_variance AS
WITH game_earnings AS (
    SELECT
        mm.creator_id,
        ct.type_name AS content_type,
        mm.earnings,
        mm.sending_time
    FROM mass_messages mm
    JOIN content_types ct ON mm.content_type_id = ct.content_type_id
    WHERE ct.type_name LIKE '%game%'
       OR ct.type_name LIKE '%wheel%'
       OR ct.type_name LIKE '%spin%'
),
game_stats AS (
    SELECT
        ge.creator_id,
        ge.content_type,
        COUNT(*) AS send_count,
        ROUND(AVG(ge.earnings), 2) AS avg_earnings,
        ROUND(
            SQRT(
                SUM((ge.earnings - (SELECT AVG(earnings) FROM game_earnings ge2
                                    WHERE ge2.creator_id = ge.creator_id
                                    AND ge2.content_type = ge.content_type))
                    * (ge.earnings - (SELECT AVG(earnings) FROM game_earnings ge2
                                      WHERE ge2.creator_id = ge.creator_id
                                      AND ge2.content_type = ge.content_type)))
                / COUNT(*)
            ), 2
        ) AS stddev_earnings
    FROM game_earnings ge
    GROUP BY ge.creator_id, ge.content_type
    HAVING COUNT(*) >= 3  -- Minimum sample size
)
SELECT
    gs.creator_id,
    c.page_name,
    c.display_name,
    gs.content_type,
    gs.send_count,
    gs.avg_earnings,
    gs.stddev_earnings,
    -- Coefficient of Variation
    CASE
        WHEN gs.avg_earnings > 0
        THEN ROUND(gs.stddev_earnings / gs.avg_earnings, 3)
        ELSE NULL
    END AS coefficient_of_variation,
    -- Status based on CV thresholds
    CASE
        WHEN gs.avg_earnings = 0 THEN 'no_revenue'
        WHEN (gs.stddev_earnings / gs.avg_earnings) <= 0.50 THEN 'consistent'
        WHEN (gs.stddev_earnings / gs.avg_earnings) <= 0.75 THEN 'moderate_variance'
        ELSE 'high_variance'
    END AS status
FROM game_stats gs
JOIN creators c ON gs.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY coefficient_of_variation DESC NULLS LAST;


-- -----------------------------------------------------------------------------
-- VIEW: v_bayesian_estimate_accuracy
-- -----------------------------------------------------------------------------
-- Purpose: Validates Bayesian performance estimates vs actual outcomes
--
-- Compares caption_bank.performance_score (Bayesian estimate) against
-- actual earnings from mass_messages for captions with sufficient usage.
--
-- Target: > 85% accuracy
-- Alert: < 70% accuracy
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_bayesian_estimate_accuracy AS
WITH caption_actuals AS (
    -- Get actual performance for captions with sufficient usage
    SELECT
        cb.caption_id,
        cb.creator_id,
        cb.performance_score AS bayesian_estimate,
        ccp.times_used,
        ccp.avg_earnings AS actual_avg_earnings,
        ccp.performance_score AS actual_performance_score
    FROM caption_bank cb
    JOIN caption_creator_performance ccp ON cb.caption_id = ccp.caption_id
    WHERE cb.is_active = 1
      AND ccp.times_used >= 5  -- Minimum observations for reliable comparison
      AND cb.performance_score IS NOT NULL
      AND ccp.performance_score IS NOT NULL
),
accuracy_calc AS (
    SELECT
        ca.creator_id,
        COUNT(*) AS caption_count,
        -- MAPE of Bayesian vs Actual
        ROUND(
            AVG(ABS(ca.bayesian_estimate - ca.actual_performance_score) /
                NULLIF(ca.actual_performance_score, 0)) * 100,
            2
        ) AS mape_pct,
        -- Correlation-style accuracy (1 - normalized error)
        ROUND(
            100.0 - AVG(ABS(ca.bayesian_estimate - ca.actual_performance_score) /
                        NULLIF(ca.actual_performance_score, 0)) * 100,
            2
        ) AS accuracy_pct,
        -- Directional accuracy (did estimate rank correctly?)
        ROUND(
            100.0 * SUM(
                CASE
                    WHEN (ca.bayesian_estimate > 50 AND ca.actual_performance_score > 50) OR
                         (ca.bayesian_estimate <= 50 AND ca.actual_performance_score <= 50)
                    THEN 1 ELSE 0
                END
            ) / COUNT(*),
            2
        ) AS directional_accuracy_pct
    FROM caption_actuals ca
    GROUP BY ca.creator_id
)
SELECT
    ac.creator_id,
    c.page_name,
    c.display_name,
    ac.caption_count,
    ac.mape_pct,
    ac.accuracy_pct,
    ac.directional_accuracy_pct,
    -- Status based on accuracy thresholds
    CASE
        WHEN ac.accuracy_pct >= 85 THEN 'on_target'
        WHEN ac.accuracy_pct >= 70 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM accuracy_calc ac
JOIN creators c ON ac.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY ac.accuracy_pct ASC;


-- -----------------------------------------------------------------------------
-- VIEW: v_trait_recommendation_lift
-- -----------------------------------------------------------------------------
-- Purpose: Measures revenue lift from using TOP-tier content recommendations
--
-- Compares average earnings from TOP-tier content vs overall baseline
--
-- Target: > 20% lift
-- Alert: < 5% lift
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_trait_recommendation_lift AS
WITH content_performance AS (
    SELECT
        mm.creator_id,
        tct.performance_tier,
        mm.earnings,
        mm.message_id
    FROM mass_messages mm
    JOIN content_types ct ON mm.content_type_id = ct.content_type_id
    LEFT JOIN top_content_types tct ON mm.creator_id = tct.creator_id
        AND ct.type_name = tct.content_type
        AND tct.analysis_date = (
            SELECT MAX(analysis_date)
            FROM top_content_types
            WHERE creator_id = mm.creator_id
        )
    WHERE mm.earnings IS NOT NULL
      AND mm.sending_time >= datetime('now', '-30 days')
),
lift_calculation AS (
    SELECT
        cp.creator_id,
        -- TOP tier performance
        COUNT(CASE WHEN cp.performance_tier = 'TOP' THEN 1 END) AS top_tier_sends,
        ROUND(AVG(CASE WHEN cp.performance_tier = 'TOP' THEN cp.earnings END), 2) AS top_tier_avg_earnings,
        -- Baseline (all sends)
        COUNT(*) AS total_sends,
        ROUND(AVG(cp.earnings), 2) AS baseline_avg_earnings,
        -- Lift calculation
        CASE
            WHEN AVG(cp.earnings) > 0 AND AVG(CASE WHEN cp.performance_tier = 'TOP' THEN cp.earnings END) IS NOT NULL
            THEN ROUND(
                ((AVG(CASE WHEN cp.performance_tier = 'TOP' THEN cp.earnings END) - AVG(cp.earnings))
                 / AVG(cp.earnings)) * 100,
                2
            )
            ELSE NULL
        END AS lift_pct
    FROM content_performance cp
    GROUP BY cp.creator_id
    HAVING COUNT(CASE WHEN cp.performance_tier = 'TOP' THEN 1 END) >= 5  -- Minimum TOP sends
)
SELECT
    lc.creator_id,
    c.page_name,
    c.display_name,
    lc.top_tier_sends,
    lc.top_tier_avg_earnings,
    lc.total_sends,
    lc.baseline_avg_earnings,
    lc.lift_pct,
    -- Status based on lift thresholds
    CASE
        WHEN lc.lift_pct IS NULL THEN 'insufficient_data'
        WHEN lc.lift_pct >= 20 THEN 'on_target'
        WHEN lc.lift_pct >= 5 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM lift_calculation lc
JOIN creators c ON lc.creator_id = c.creator_id
WHERE c.is_active = 1
ORDER BY lc.lift_pct DESC NULLS LAST;


-- -----------------------------------------------------------------------------
-- VIEW: v_volume_dashboard_summary
-- -----------------------------------------------------------------------------
-- Purpose: Executive summary view combining all KPIs for dashboard display
-- -----------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_volume_dashboard_summary AS
SELECT
    'campaign_frequency_adherence' AS metric_name,
    'Compliance' AS category,
    ROUND(AVG(compliance_rate_pct), 2) AS current_value,
    90.0 AS target_value,
    75.0 AS alert_threshold,
    '%' AS unit,
    CASE
        WHEN AVG(compliance_rate_pct) >= 90 THEN 'on_target'
        WHEN AVG(compliance_rate_pct) >= 75 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_campaign_frequency_adherence
WHERE compliance_rate_pct IS NOT NULL

UNION ALL

SELECT
    'bump_ratio_compliance' AS metric_name,
    'Compliance' AS category,
    ROUND(AVG(compliance_rate_pct), 2) AS current_value,
    85.0 AS target_value,
    70.0 AS alert_threshold,
    '%' AS unit,
    CASE
        WHEN AVG(compliance_rate_pct) >= 85 THEN 'on_target'
        WHEN AVG(compliance_rate_pct) >= 70 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_bump_ratio_compliance_summary

UNION ALL

SELECT
    'volume_prediction_mape' AS metric_name,
    'Accuracy' AS category,
    ROUND(AVG(revenue_mape), 2) AS current_value,
    15.0 AS target_value,
    25.0 AS alert_threshold,
    '%' AS unit,
    CASE
        WHEN AVG(revenue_mape) <= 15 THEN 'on_target'
        WHEN AVG(revenue_mape) <= 25 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_volume_prediction_accuracy

UNION ALL

SELECT
    'weekly_limit_violations' AS metric_name,
    'Compliance' AS category,
    CAST(COUNT(CASE WHEN status = 'VIOLATION' THEN 1 END) AS REAL) AS current_value,
    0.0 AS target_value,
    0.0 AS alert_threshold,
    'count' AS unit,
    CASE
        WHEN COUNT(CASE WHEN status = 'VIOLATION' THEN 1 END) = 0 THEN 'on_target'
        ELSE 'critical'
    END AS status
FROM v_weekly_limit_violations

UNION ALL

SELECT
    'bayesian_estimate_accuracy' AS metric_name,
    'Accuracy' AS category,
    ROUND(AVG(accuracy_pct), 2) AS current_value,
    85.0 AS target_value,
    70.0 AS alert_threshold,
    '%' AS unit,
    CASE
        WHEN AVG(accuracy_pct) >= 85 THEN 'on_target'
        WHEN AVG(accuracy_pct) >= 70 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_bayesian_estimate_accuracy

UNION ALL

SELECT
    'trait_recommendation_lift' AS metric_name,
    'Revenue' AS category,
    ROUND(AVG(lift_pct), 2) AS current_value,
    20.0 AS target_value,
    5.0 AS alert_threshold,
    '%' AS unit,
    CASE
        WHEN AVG(lift_pct) >= 20 THEN 'on_target'
        WHEN AVG(lift_pct) >= 5 THEN 'warning'
        ELSE 'critical'
    END AS status
FROM v_trait_recommendation_lift
WHERE lift_pct IS NOT NULL;
