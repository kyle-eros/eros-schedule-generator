-- Wave 2: Timing & Scheduling Precision
-- Database Migration: Rotation State Tables
-- SQLite-compatible schema

-- =============================================================================
-- Creator Rotation State Table
-- Tracks PPV rotation patterns per creator for authentic scheduling
-- =============================================================================

CREATE TABLE IF NOT EXISTS creator_rotation_state (
    creator_id TEXT PRIMARY KEY,
    rotation_pattern TEXT NOT NULL,           -- JSON stored as TEXT, parsed at application layer
    pattern_start_date TEXT NOT NULL,         -- ISO 8601 datetime string
    days_on_pattern INTEGER DEFAULT 0,
    current_state TEXT DEFAULT 'initializing', -- RotationState enum value
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Index for efficient state queries
CREATE INDEX IF NOT EXISTS idx_rotation_state_updated
ON creator_rotation_state(updated_at);

-- Index for finding creators in specific states
CREATE INDEX IF NOT EXISTS idx_rotation_current_state
ON creator_rotation_state(current_state);

-- =============================================================================
-- Pinned Post Tracking Table
-- Manages pinned post rotation with 72-hour lifecycle
-- =============================================================================

CREATE TABLE IF NOT EXISTS creator_pinned_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    pin_start TEXT NOT NULL,                  -- ISO 8601 datetime
    pin_end TEXT NOT NULL,                    -- ISO 8601 datetime (pin_start + 72 hours)
    priority REAL DEFAULT 0.0,                -- Based on estimated revenue
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(creator_id, post_id)
);

-- Index for finding active pins per creator
CREATE INDEX IF NOT EXISTS idx_pinned_posts_creator_active
ON creator_pinned_posts(creator_id, is_active);

-- Index for finding expired pins
CREATE INDEX IF NOT EXISTS idx_pinned_posts_pin_end
ON creator_pinned_posts(pin_end);

-- =============================================================================
-- Link Drop Expiration Tracking Table
-- Tracks 24-hour expiration for link drops
-- =============================================================================

CREATE TABLE IF NOT EXISTS link_drop_expiration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_item_id TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,             -- ISO 8601 datetime
    expiration_time TEXT NOT NULL,            -- ISO 8601 datetime (scheduled + 24 hours)
    is_expired INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Index for finding non-expired link drops
CREATE INDEX IF NOT EXISTS idx_link_drop_creator_expired
ON link_drop_expiration(creator_id, is_expired);

-- Index for checking expiration times
CREATE INDEX IF NOT EXISTS idx_link_drop_expiration_time
ON link_drop_expiration(expiration_time);

-- =============================================================================
-- Timing Operation Log Table (Observability)
-- Structured logging for timing events
-- =============================================================================

CREATE TABLE IF NOT EXISTS timing_operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,                 -- rotation_change, followup_scheduled, jitter_applied, etc.
    creator_id TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,            -- ISO 8601 datetime
    event_details TEXT NOT NULL,              -- JSON stored as TEXT
    duration_ms REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Index for querying events by type and creator
CREATE INDEX IF NOT EXISTS idx_timing_log_type_creator
ON timing_operation_log(event_type, creator_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_timing_log_timestamp
ON timing_operation_log(event_timestamp);

-- =============================================================================
-- Idempotency Record Table
-- Prevents duplicate timing operations
-- =============================================================================

CREATE TABLE IF NOT EXISTS timing_idempotency (
    operation_key TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    result TEXT,                              -- JSON stored as TEXT
    executed_at TEXT NOT NULL,                -- ISO 8601 datetime
    expires_at TEXT NOT NULL                  -- ISO 8601 datetime
);

-- Index for cleanup of expired records
CREATE INDEX IF NOT EXISTS idx_idempotency_expires
ON timing_idempotency(expires_at);

-- =============================================================================
-- Circuit Breaker State Table
-- Tracks circuit breaker states for monitoring
-- =============================================================================

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    name TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'closed',     -- closed, open, half_open
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_failure_time TEXT,                   -- ISO 8601 datetime
    last_success_time TEXT,                   -- ISO 8601 datetime
    last_state_change TEXT,                   -- ISO 8601 datetime
    updated_at TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- Saga Execution Log Table
-- Tracks saga executions for debugging and recovery
-- =============================================================================

CREATE TABLE IF NOT EXISTS saga_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saga_id TEXT NOT NULL,                    -- UUID for saga instance
    creator_id TEXT NOT NULL,
    status TEXT NOT NULL,                     -- pending, in_progress, completed, compensating, failed, rolled_back
    steps_completed TEXT,                     -- JSON array of completed step names
    failed_step TEXT,
    error_message TEXT,
    compensation_errors TEXT,                 -- JSON array
    execution_time_ms REAL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Index for querying saga executions by creator
CREATE INDEX IF NOT EXISTS idx_saga_log_creator
ON saga_execution_log(creator_id);

-- Index for finding incomplete sagas
CREATE INDEX IF NOT EXISTS idx_saga_log_status
ON saga_execution_log(status);

-- =============================================================================
-- PPV Followup Tracking Table
-- Tracks followup timing for validation
-- =============================================================================

CREATE TABLE IF NOT EXISTS ppv_followup_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    parent_ppv_id TEXT NOT NULL,
    parent_time TEXT NOT NULL,                -- ISO 8601 datetime
    followup_time TEXT NOT NULL,              -- ISO 8601 datetime
    gap_minutes REAL NOT NULL,
    ppv_type TEXT NOT NULL,
    is_optimal_window INTEGER DEFAULT 0,      -- 1 if 15-45 min
    created_at TEXT DEFAULT (datetime('now'))
);

-- Index for querying followups by creator
CREATE INDEX IF NOT EXISTS idx_followup_creator
ON ppv_followup_tracking(creator_id);

-- Index for analyzing timing patterns
CREATE INDEX IF NOT EXISTS idx_followup_gap
ON ppv_followup_tracking(gap_minutes);

-- =============================================================================
-- View: Active Rotation States
-- =============================================================================

CREATE VIEW IF NOT EXISTS v_active_rotation_states AS
SELECT
    creator_id,
    rotation_pattern,
    pattern_start_date,
    days_on_pattern,
    current_state,
    updated_at,
    CAST((julianday('now') - julianday(pattern_start_date)) AS INTEGER) as actual_days_since_start
FROM creator_rotation_state
WHERE current_state != 'error';

-- =============================================================================
-- View: Expiring Link Drops (next 1 hour)
-- =============================================================================

CREATE VIEW IF NOT EXISTS v_expiring_link_drops AS
SELECT
    id,
    schedule_item_id,
    creator_id,
    scheduled_time,
    expiration_time,
    CAST((julianday(expiration_time) - julianday('now')) * 24 * 60 AS INTEGER) as minutes_until_expiration
FROM link_drop_expiration
WHERE is_expired = 0
  AND datetime(expiration_time) <= datetime('now', '+1 hour')
ORDER BY expiration_time;

-- =============================================================================
-- View: Circuit Breaker Health
-- =============================================================================

CREATE VIEW IF NOT EXISTS v_circuit_breaker_health AS
SELECT
    name,
    state,
    failure_count,
    success_count,
    CASE
        WHEN failure_count + success_count > 0
        THEN ROUND(CAST(success_count AS REAL) / (failure_count + success_count) * 100, 2)
        ELSE 100.0
    END as success_rate_pct,
    last_failure_time,
    last_success_time,
    CAST((julianday('now') - julianday(last_state_change)) * 24 * 60 AS INTEGER) as minutes_in_state
FROM circuit_breaker_state;

-- =============================================================================
-- Migration Complete
-- =============================================================================
