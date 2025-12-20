-- Migration 018: Pipeline Supercharge - 9 New Tables
-- Part of EROS v3.0.0 (Pipeline Supercharge)
--
-- Purpose: Create tables for 14-phase pipeline with prediction, churn,
-- experiments, and attention scoring capabilities.
--
-- New Tables:
--   1. caption_predictions - ML-style caption performance predictions
--   2. prediction_outcomes - Actual vs predicted for feedback loop
--   3. prediction_weights - Feature weights for prediction model
--   4. churn_risk_scores - Subscriber churn risk analysis
--   5. win_back_campaigns - Win-back campaign tracking
--   6. ab_experiments - A/B experiment definitions
--   7. experiment_variants - Experiment variant configurations
--   8. experiment_results - Experiment outcome metrics
--   9. caption_attention_scores - Attention quality scores per caption

-- =============================================================================
-- TABLE 1: caption_predictions
-- ML-style performance predictions for captions before scheduling
-- =============================================================================
CREATE TABLE IF NOT EXISTS caption_predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    caption_id INTEGER NOT NULL,
    schedule_id INTEGER,  -- NULL until scheduled

    -- Predicted metrics
    predicted_rps REAL NOT NULL,  -- Predicted revenue per send
    predicted_open_rate REAL,     -- Predicted open rate (0.0-1.0)
    predicted_conversion_rate REAL,  -- Predicted conversion rate (0.0-1.0)

    -- Confidence and scoring
    confidence_score REAL NOT NULL DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    prediction_score REAL NOT NULL,  -- Composite prediction score (0-100)

    -- Feature values used (JSON blob for reproducibility)
    features_json TEXT NOT NULL,  -- {"structural": 0.8, "performance": 0.7, ...}

    -- Metadata
    model_version TEXT NOT NULL DEFAULT 'v1.0.0',
    predicted_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign keys
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_id) REFERENCES weekly_schedule_templates(template_id) ON DELETE SET NULL
);

-- Index for efficient lookup by creator and caption
CREATE INDEX IF NOT EXISTS idx_caption_predictions_creator
    ON caption_predictions(creator_id, predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_caption_predictions_caption
    ON caption_predictions(caption_id);

CREATE INDEX IF NOT EXISTS idx_caption_predictions_schedule
    ON caption_predictions(schedule_id) WHERE schedule_id IS NOT NULL;


-- =============================================================================
-- TABLE 2: prediction_outcomes
-- Actual performance vs predicted for feedback loop learning
-- =============================================================================
CREATE TABLE IF NOT EXISTS prediction_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL,

    -- Actual metrics
    actual_rps REAL NOT NULL,
    actual_open_rate REAL,
    actual_conversion_rate REAL,

    -- Accuracy metrics
    rps_error REAL NOT NULL,  -- actual - predicted
    rps_error_pct REAL,       -- percentage error

    -- Timing
    sent_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key
    FOREIGN KEY (prediction_id) REFERENCES caption_predictions(prediction_id) ON DELETE CASCADE
);

-- Index for feedback loop queries
CREATE INDEX IF NOT EXISTS idx_prediction_outcomes_prediction
    ON prediction_outcomes(prediction_id);

CREATE INDEX IF NOT EXISTS idx_prediction_outcomes_recorded
    ON prediction_outcomes(recorded_at DESC);


-- =============================================================================
-- TABLE 3: prediction_weights
-- Feature weights for the prediction model (self-improving)
-- =============================================================================
CREATE TABLE IF NOT EXISTS prediction_weights (
    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT NOT NULL,
    feature_category TEXT NOT NULL CHECK (feature_category IN (
        'structural',    -- Caption structure features (length, emoji, CTA)
        'performance',   -- Historical performance features (RPS, tier)
        'temporal',      -- Time-based features (DOW, time, recency)
        'creator'        -- Creator-specific features (persona, voice)
    )),

    -- Weight values
    current_weight REAL NOT NULL DEFAULT 1.0,
    previous_weight REAL,
    initial_weight REAL NOT NULL DEFAULT 1.0,

    -- Learning metadata
    adjustment_count INTEGER NOT NULL DEFAULT 0,
    last_adjustment REAL,  -- Delta from last update
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),

    -- Constraints
    min_weight REAL NOT NULL DEFAULT 0.1,
    max_weight REAL NOT NULL DEFAULT 3.0,
    is_active INTEGER NOT NULL DEFAULT 1,

    -- Unique constraint on feature name
    UNIQUE(feature_name)
);

-- Initial feature weights (default values)
INSERT OR IGNORE INTO prediction_weights (feature_name, feature_category, current_weight, initial_weight) VALUES
    ('caption_length', 'structural', 1.0, 1.0),
    ('emoji_count', 'structural', 0.8, 0.8),
    ('has_cta', 'structural', 1.2, 1.2),
    ('hook_strength', 'structural', 1.1, 1.1),
    ('historical_rps', 'performance', 1.5, 1.5),
    ('content_tier', 'performance', 1.3, 1.3),
    ('freshness_score', 'performance', 1.0, 1.0),
    ('day_of_week', 'temporal', 0.9, 0.9),
    ('hour_of_day', 'temporal', 0.9, 0.9),
    ('days_since_use', 'temporal', 1.0, 1.0),
    ('persona_match', 'creator', 0.7, 0.7),
    ('voice_consistency', 'creator', 0.8, 0.8);


-- =============================================================================
-- TABLE 4: churn_risk_scores
-- Subscriber churn risk analysis by segment
-- =============================================================================
CREATE TABLE IF NOT EXISTS churn_risk_scores (
    risk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- Segment identification
    segment_name TEXT NOT NULL,  -- e.g., 'high_spenders', 'new_subscribers', 'at_risk'
    segment_criteria_json TEXT,  -- JSON criteria defining segment

    -- Risk metrics
    risk_score REAL NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')),
    subscriber_count INTEGER NOT NULL DEFAULT 0,

    -- Contributing factors
    churn_factors_json TEXT,  -- JSON array of factors
    top_churn_reason TEXT,

    -- Recommendations
    retention_strategy TEXT,
    recommended_actions_json TEXT,

    -- Timing
    analysis_date TEXT NOT NULL DEFAULT (date('now')),
    expires_at TEXT NOT NULL,

    -- Foreign key
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- Index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_churn_risk_creator_date
    ON churn_risk_scores(creator_id, analysis_date DESC);

CREATE INDEX IF NOT EXISTS idx_churn_risk_tier
    ON churn_risk_scores(risk_tier, risk_score DESC);


-- =============================================================================
-- TABLE 5: win_back_campaigns
-- Win-back campaign tracking for lapsed subscribers
-- =============================================================================
CREATE TABLE IF NOT EXISTS win_back_campaigns (
    campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- Campaign details
    campaign_type TEXT NOT NULL CHECK (campaign_type IN (
        'LAPSED',      -- 30+ days inactive
        'DECLINED',    -- Subscription declined/cancelled
        'INACTIVE'     -- 15-30 days inactive
    )),
    campaign_name TEXT NOT NULL,

    -- Offer details
    discount_percent INTEGER,
    bundle_offer_json TEXT,  -- Special bundle details
    message_template TEXT,

    -- Targeting
    target_segment TEXT,
    target_count INTEGER NOT NULL DEFAULT 0,

    -- Status
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'SCHEDULED', 'ACTIVE', 'COMPLETED', 'CANCELLED'
    )),

    -- Performance
    sent_count INTEGER DEFAULT 0,
    opened_count INTEGER DEFAULT 0,
    converted_count INTEGER DEFAULT 0,
    revenue_generated REAL DEFAULT 0.0,

    -- Timing
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- Index for campaign management
CREATE INDEX IF NOT EXISTS idx_win_back_creator_status
    ON win_back_campaigns(creator_id, status);

CREATE INDEX IF NOT EXISTS idx_win_back_type
    ON win_back_campaigns(campaign_type, status);


-- =============================================================================
-- TABLE 6: ab_experiments
-- A/B experiment definitions
-- =============================================================================
CREATE TABLE IF NOT EXISTS ab_experiments (
    experiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- Experiment details
    experiment_name TEXT NOT NULL,
    experiment_type TEXT NOT NULL CHECK (experiment_type IN (
        'caption_style',    -- Testing caption variations
        'timing_slots',     -- Testing posting times
        'price_points',     -- Testing PPV pricing
        'content_order',    -- Testing content sequencing
        'followup_delay'    -- Testing followup timing
    )),
    hypothesis TEXT,

    -- Configuration
    traffic_allocation REAL NOT NULL DEFAULT 0.5 CHECK (traffic_allocation > 0 AND traffic_allocation <= 1.0),
    min_sample_size INTEGER NOT NULL DEFAULT 100,

    -- Statistical settings
    significance_level REAL NOT NULL DEFAULT 0.05,  -- p-value threshold
    minimum_detectable_effect REAL DEFAULT 0.05,    -- 5% minimum effect

    -- Status
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED'
    )),

    -- Winner (set when completed)
    winning_variant_id INTEGER,
    winner_confidence REAL,

    -- Timing
    start_date TEXT,
    end_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- Index for experiment management
CREATE INDEX IF NOT EXISTS idx_ab_experiments_creator_status
    ON ab_experiments(creator_id, status);

CREATE INDEX IF NOT EXISTS idx_ab_experiments_type
    ON ab_experiments(experiment_type, status);


-- =============================================================================
-- TABLE 7: experiment_variants
-- Experiment variant configurations
-- =============================================================================
CREATE TABLE IF NOT EXISTS experiment_variants (
    variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,

    -- Variant details
    variant_name TEXT NOT NULL,  -- e.g., 'control', 'variation_a', 'variation_b'
    variant_description TEXT,
    is_control INTEGER NOT NULL DEFAULT 0,

    -- Configuration (JSON for flexibility)
    variant_config_json TEXT NOT NULL,  -- {"caption_style": "direct"} or {"price": 15}

    -- Traffic allocation within experiment
    allocation_percent REAL NOT NULL DEFAULT 50.0,

    -- Performance tracking
    sample_count INTEGER NOT NULL DEFAULT 0,
    conversions INTEGER NOT NULL DEFAULT 0,
    total_revenue REAL NOT NULL DEFAULT 0.0,

    -- Status
    is_active INTEGER NOT NULL DEFAULT 1,

    -- Foreign key
    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id) ON DELETE CASCADE
);

-- Index for variant lookup
CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment
    ON experiment_variants(experiment_id);

CREATE INDEX IF NOT EXISTS idx_experiment_variants_active
    ON experiment_variants(experiment_id, is_active) WHERE is_active = 1;


-- =============================================================================
-- TABLE 8: experiment_results
-- Experiment outcome metrics
-- =============================================================================
CREATE TABLE IF NOT EXISTS experiment_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL,

    -- Metrics
    metric_name TEXT NOT NULL,  -- 'conversion_rate', 'rps', 'open_rate', etc.
    metric_value REAL NOT NULL,
    sample_size INTEGER NOT NULL,

    -- Statistical analysis
    standard_error REAL,
    confidence_interval_low REAL,
    confidence_interval_high REAL,

    -- Comparison to control
    vs_control_lift REAL,       -- Percentage lift vs control
    vs_control_p_value REAL,    -- Statistical significance
    is_significant INTEGER,     -- 1 if p_value < significance_level

    -- Timing
    measurement_date TEXT NOT NULL DEFAULT (date('now')),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign keys
    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(variant_id) ON DELETE CASCADE
);

-- Index for result queries
CREATE INDEX IF NOT EXISTS idx_experiment_results_experiment
    ON experiment_results(experiment_id, measurement_date DESC);

CREATE INDEX IF NOT EXISTS idx_experiment_results_variant
    ON experiment_results(variant_id, metric_name);


-- =============================================================================
-- TABLE 9: caption_attention_scores
-- Attention quality scores per caption
-- =============================================================================
CREATE TABLE IF NOT EXISTS caption_attention_scores (
    attention_id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,

    -- Component scores (0-100 each)
    hook_score REAL NOT NULL CHECK (hook_score >= 0 AND hook_score <= 100),
    depth_score REAL NOT NULL CHECK (depth_score >= 0 AND depth_score <= 100),
    cta_score REAL NOT NULL CHECK (cta_score >= 0 AND cta_score <= 100),
    emotion_score REAL NOT NULL CHECK (emotion_score >= 0 AND emotion_score <= 100),

    -- Composite attention score (weighted average)
    -- Formula: (hook * 0.35) + (depth * 0.25) + (cta * 0.25) + (emotion * 0.15)
    attention_score REAL NOT NULL CHECK (attention_score >= 0 AND attention_score <= 100),

    -- Quality classification
    quality_tier TEXT NOT NULL CHECK (quality_tier IN ('LOW', 'MEDIUM', 'HIGH', 'EXCEPTIONAL')),

    -- Analysis metadata
    analysis_version TEXT NOT NULL DEFAULT 'v1.0.0',
    analyzed_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Cached metrics for efficiency
    word_count INTEGER,
    sentence_count INTEGER,
    avg_sentence_length REAL,

    -- Foreign keys
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id) ON DELETE CASCADE,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,

    -- Unique constraint per caption-creator pair
    UNIQUE(caption_id, creator_id)
);

-- Index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_caption_attention_creator
    ON caption_attention_scores(creator_id, attention_score DESC);

CREATE INDEX IF NOT EXISTS idx_caption_attention_quality
    ON caption_attention_scores(quality_tier, attention_score DESC);

CREATE INDEX IF NOT EXISTS idx_caption_attention_caption
    ON caption_attention_scores(caption_id);


-- =============================================================================
-- Verification Queries (run after migration)
-- =============================================================================
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'caption_predictions';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'prediction_outcomes';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'prediction_weights';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'churn_risk_scores';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'win_back_campaigns';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ab_experiments';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'experiment_variants';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'experiment_results';
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'caption_attention_scores';
-- SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('caption_predictions', 'prediction_outcomes', 'prediction_weights', 'churn_risk_scores', 'win_back_campaigns', 'ab_experiments', 'experiment_variants', 'experiment_results', 'caption_attention_scores');
