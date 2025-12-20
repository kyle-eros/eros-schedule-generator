-- Migration 017: Create volume_triggers table for performance-based adjustments
-- Part of Volume Optimization v3.0 (Wave 1)
--
-- Purpose: Store content-specific volume triggers detected by performance-analyst
-- Triggers adjust allocation multipliers for specific content types

CREATE TABLE IF NOT EXISTS volume_triggers (
    trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN (
        'HIGH_PERFORMER',      -- RPS > $200, conversion > 6%: +20%
        'TRENDING_UP',         -- WoW RPS increase > 15%: +10%
        'EMERGING_WINNER',     -- RPS > $150, used < 3 times in 30d: +30%
        'SATURATING',          -- Declining engagement 3+ days: -15%
        'AUDIENCE_FATIGUE'     -- Open rate decline > 10% over 7d: -25%
    )),
    adjustment_multiplier REAL NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'moderate' CHECK (confidence IN ('low', 'moderate', 'high')),
    metrics_json TEXT,  -- JSON blob with supporting metrics
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    applied_count INTEGER DEFAULT 0,  -- Track how many times trigger was used

    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- Index for efficient lookup of active triggers per creator
CREATE INDEX IF NOT EXISTS idx_volume_triggers_creator_active
    ON volume_triggers(creator_id, is_active) WHERE is_active = 1;

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_volume_triggers_expires
    ON volume_triggers(expires_at);

-- Index for trigger type analysis
CREATE INDEX IF NOT EXISTS idx_volume_triggers_type
    ON volume_triggers(trigger_type, is_active);

-- Verification query (run after migration)
-- SELECT name FROM sqlite_master WHERE type='table' AND name='volume_triggers';
