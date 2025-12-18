-- ============================================================================
-- Migration 007: Schedule Generator Enhancements
-- ============================================================================
-- Purpose: Add infrastructure for the EROS Schedule Generator system
-- Created: 2025-12-15
-- Blueprint: WAVE 4 - Schedule Generator SQL Infrastructure
--
-- This migration adds:
--   1. New columns to schedule_templates for algorithm tracking and validation
--   2. freshness_score column to caption_bank for usage decay tracking
--   3. schedule_generation_queue table for async schedule processing
--   4. v_schedule_ready_creators view for identifying schedulable creators
--
-- IDEMPOTENT: All operations check for existence before executing.
-- SAFE: Uses ADD COLUMN which is safe in SQLite (no data loss).
-- ============================================================================

-- ============================================================================
-- SECTION 1: schema_migrations table (ensure it exists)
-- ============================================================================
-- This table tracks applied migrations for audit and idempotency

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================================
-- SECTION 2: ALTER STATEMENTS
-- ============================================================================
-- These columns enable detailed tracking of schedule generation parameters,
-- execution logs, and quality validation scores.
--
-- IMPORTANT: SQLite does not support IF NOT EXISTS for ALTER TABLE ADD COLUMN.
-- These statements will produce "duplicate column name" errors on re-run.
-- This is EXPECTED and HARMLESS behavior.
--
-- For clean re-runs, filter the errors:
--   sqlite3 db.db ".read migration.sql" 2>&1 | grep -v "duplicate column"
--
-- The migration is considered successful even with these errors since:
--   - First run: columns are added successfully
--   - Re-run: "duplicate column" errors indicate columns already exist (success)

-- schedule_templates additions
-- Column: algorithm_params - JSON storage for algorithm configuration
--   Example: {"version": "2.1", "strategy": "balanced", "weights": {...}}
ALTER TABLE schedule_templates ADD COLUMN algorithm_params TEXT;

-- Column: agent_execution_log - JSON storage for multi-agent execution trace
--   Example: {"steps": [...], "duration_ms": 1234, "warnings": [...]}
ALTER TABLE schedule_templates ADD COLUMN agent_execution_log TEXT;

-- Column: quality_validation_score - Quality gate score from 0-100
--   Computed by Quality Guardian agent, threshold typically 70+
ALTER TABLE schedule_templates ADD COLUMN quality_validation_score REAL;

-- caption_bank addition
-- Column: freshness_score - Decay-based freshness from 0-100
--   100 = never used, decays with each use, recovers over time
ALTER TABLE caption_bank ADD COLUMN freshness_score REAL DEFAULT 100.0;

-- ============================================================================
-- SECTION 3: CREATE TABLE schedule_generation_queue
-- ============================================================================
-- Async queue for schedule generation requests.
-- Enables batch processing, priority ordering, and status tracking.
--
-- Workflow:
--   1. Request submitted -> status='pending'
--   2. Worker picks up -> status='processing', started_at set
--   3. Success -> status='completed', result_template_id linked
--   4. Failure -> status='failed', error_message populated
--
-- The UNIQUE constraint prevents duplicate requests for the same
-- creator/week while in pending or processing state.

CREATE TABLE IF NOT EXISTS schedule_generation_queue (
    -- Primary key
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Request identification
    creator_id TEXT NOT NULL,               -- FK to creators table
    week_start TEXT NOT NULL,               -- ISO format YYYY-MM-DD (Monday of target week)

    -- Priority and status
    priority INTEGER DEFAULT 5,             -- 1=highest, 10=lowest, 5=normal
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

    -- Timestamps
    requested_at TEXT DEFAULT (datetime('now')),
    started_at TEXT,                        -- When processing began
    completed_at TEXT,                      -- When processing finished (success or fail)

    -- Result tracking
    result_template_id INTEGER,             -- FK to schedule_templates on success
    error_message TEXT,                     -- Error details on failure

    -- Request metadata (optional)
    requested_by TEXT,                      -- User/system that requested generation
    request_params TEXT,                    -- JSON: custom parameters for this request

    -- Foreign keys
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (result_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);

-- ============================================================================
-- SECTION 4: CREATE INDEXES for schedule_generation_queue
-- ============================================================================

-- Primary queue processing index: find pending items by priority and request time
-- This is the main index used by the queue worker to pick up next items
CREATE INDEX IF NOT EXISTS idx_sgq_status_priority
ON schedule_generation_queue(status, priority DESC, requested_at ASC);

-- Index for finding all queue items for a specific creator
CREATE INDEX IF NOT EXISTS idx_sgq_creator
ON schedule_generation_queue(creator_id, week_start);

-- Index for cleanup queries: find completed/failed items older than X
CREATE INDEX IF NOT EXISTS idx_sgq_completed_at
ON schedule_generation_queue(completed_at)
WHERE status IN ('completed', 'failed');

-- Partial unique index to prevent duplicate pending/processing requests
-- This allows multiple completed/failed entries but only one active request
CREATE UNIQUE INDEX IF NOT EXISTS idx_sgq_unique_active
ON schedule_generation_queue(creator_id, week_start)
WHERE status IN ('pending', 'processing');

-- Index for FK column result_template_id (for join performance)
-- Partial index since most queue items won't have a result yet
CREATE INDEX IF NOT EXISTS idx_sgq_result_template
ON schedule_generation_queue(result_template_id)
WHERE result_template_id IS NOT NULL;

-- ============================================================================
-- SECTION 5: CREATE VIEW v_schedule_ready_creators
-- ============================================================================
-- This view identifies creators who are ready for automated schedule generation.
-- It joins creators with volume assignments, personas, and caption availability.
--
-- Caption readiness levels:
--   - 'ready': Has >= ppv_per_day * 7 fresh captions (full week coverage)
--   - 'limited': Has >= ppv_per_day * 3 fresh captions (partial week)
--   - 'insufficient': Below minimum threshold
--
-- Fresh caption criteria:
--   - freshness_score >= 30 (not overused recently)
--   - performance_score >= 40 (historically performs adequately)
--   - is_active = 1 (not archived)

DROP VIEW IF EXISTS v_schedule_ready_creators;

CREATE VIEW v_schedule_ready_creators AS
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
active_volume AS (
    -- Get current active volume assignment per creator
    SELECT
        va.creator_id,
        va.volume_level,
        va.ppv_per_day,
        va.bump_per_day,
        va.assigned_at
    FROM volume_assignments va
    WHERE va.is_active = 1
)
SELECT
    -- Creator identification
    c.creator_id,
    c.page_name,
    c.display_name,
    c.page_type,
    c.performance_tier,
    c.current_active_fans,

    -- Volume assignment details
    COALESCE(av.volume_level, 'Not Assigned') AS volume_level,
    COALESCE(av.ppv_per_day, 0) AS ppv_per_day,
    COALESCE(av.bump_per_day, 0) AS bump_per_day,

    -- Persona details (from original creator_personas table)
    COALESCE(cp.primary_tone, 'unknown') AS primary_tone,
    COALESCE(cp.emoji_frequency, 'moderate') AS emoji_frequency,
    cp.slang_level,

    -- Caption availability metrics
    COALESCE(cs.available_captions, 0) AS available_captions,
    COALESCE(cs.fresh_captions, 0) AS fresh_captions,

    -- Caption readiness classification
    CASE
        WHEN av.ppv_per_day IS NULL OR av.ppv_per_day = 0 THEN 'no_volume_assignment'
        WHEN COALESCE(cs.fresh_captions, 0) >= (av.ppv_per_day * 7) THEN 'ready'
        WHEN COALESCE(cs.fresh_captions, 0) >= (av.ppv_per_day * 3) THEN 'limited'
        ELSE 'insufficient'
    END AS caption_readiness,

    -- Readiness calculation details (for debugging/transparency)
    COALESCE(av.ppv_per_day, 0) * 7 AS captions_needed_full_week,
    COALESCE(av.ppv_per_day, 0) * 3 AS captions_needed_minimum,

    -- Overall schedule readiness flag
    CASE
        WHEN c.is_active = 1
             AND av.volume_level IS NOT NULL
             AND COALESCE(cs.fresh_captions, 0) >= (av.ppv_per_day * 3)
        THEN 1
        ELSE 0
    END AS is_schedule_ready

FROM creators c
LEFT JOIN active_volume av ON c.creator_id = av.creator_id
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
LEFT JOIN caption_stats cs ON c.creator_id = cs.creator_id
WHERE c.is_active = 1
ORDER BY
    c.performance_tier ASC,  -- Higher tier (lower number) first
    c.current_active_fans DESC;

-- ============================================================================
-- SECTION 6: CREATE INDEX for caption_bank freshness queries
-- ============================================================================
-- Optimize queries that filter by freshness_score and performance_score
-- This index supports the caption_stats CTE in v_schedule_ready_creators

CREATE INDEX IF NOT EXISTS idx_cb_freshness_performance
ON caption_bank(creator_id, freshness_score, performance_score)
WHERE is_active = 1;

-- ============================================================================
-- SECTION 7: CREATE TRIGGER for freshness_score decay on usage
-- ============================================================================
-- When a caption is used (last_used_date updated), reduce its freshness_score.
-- This creates natural rotation of captions in generated schedules.
--
-- Decay formula: freshness_score = freshness_score * 0.85 (15% reduction per use)
-- Minimum floor: 5.0 (never completely unusable)

DROP TRIGGER IF EXISTS trg_cb_freshness_decay_on_use;

CREATE TRIGGER trg_cb_freshness_decay_on_use
AFTER UPDATE ON caption_bank
WHEN NEW.last_used_date IS NOT NULL
     AND (OLD.last_used_date IS NULL OR NEW.last_used_date != OLD.last_used_date)
BEGIN
    UPDATE caption_bank
    SET freshness_score = MAX(5.0, COALESCE(freshness_score, 100.0) * 0.85)
    WHERE caption_id = NEW.caption_id;
END;

-- ============================================================================
-- SECTION 8: Migration metadata record
-- ============================================================================
-- Record this migration as applied (idempotent via INSERT OR REPLACE)

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '007',
    datetime('now'),
    'Schedule generator enhancements: algorithm_params, agent_execution_log, quality_validation_score columns on schedule_templates; freshness_score on caption_bank; schedule_generation_queue table; v_schedule_ready_creators view'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to verify successful application:
--
-- 1. Check new columns on schedule_templates:
--    PRAGMA table_info(schedule_templates);
--
-- 2. Check new column on caption_bank:
--    PRAGMA table_info(caption_bank);
--
-- 3. Check queue table exists:
--    SELECT * FROM schedule_generation_queue LIMIT 0;
--
-- 4. Check view works:
--    SELECT * FROM v_schedule_ready_creators LIMIT 5;
--
-- 5. Check migration recorded:
--    SELECT * FROM schema_migrations WHERE version = '007';
--
-- ============================================================================
-- IDEMPOTENCY NOTES
-- ============================================================================
-- This migration is designed to be re-runnable with the following behavior:
--
-- 1. ALTER TABLE ADD COLUMN statements:
--    - Will produce "duplicate column name" errors on re-run
--    - These errors are HARMLESS and should be ignored
--    - To suppress: sqlite3 db.db ".read file.sql" 2>&1 | grep -v "duplicate column"
--
-- 2. CREATE TABLE IF NOT EXISTS:
--    - Fully idempotent, no errors on re-run
--
-- 3. CREATE INDEX IF NOT EXISTS:
--    - Fully idempotent, no errors on re-run
--
-- 4. DROP VIEW IF EXISTS / CREATE VIEW:
--    - Fully idempotent, view is recreated each time
--
-- 5. DROP TRIGGER IF EXISTS / CREATE TRIGGER:
--    - Fully idempotent, trigger is recreated each time
--
-- 6. INSERT OR REPLACE INTO schema_migrations:
--    - Fully idempotent, updates timestamp on re-run
--
-- For production deployment, wrap execution:
--   sqlite3 "$DB_PATH" ".read $MIGRATION" 2>&1 | grep -v "duplicate column"
--   if [ ${PIPESTATUS[0]} -eq 0 ]; then echo "Migration 007 applied"; fi
--
-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
-- To rollback this migration (CAUTION: data loss for new columns):
--
-- DROP TRIGGER IF EXISTS trg_cb_freshness_decay_on_use;
-- DROP VIEW IF EXISTS v_schedule_ready_creators;
-- DROP INDEX IF EXISTS idx_cb_freshness_performance;
-- DROP INDEX IF EXISTS idx_sgq_result_template;
-- DROP INDEX IF EXISTS idx_sgq_unique_active;
-- DROP INDEX IF EXISTS idx_sgq_completed_at;
-- DROP INDEX IF EXISTS idx_sgq_creator;
-- DROP INDEX IF EXISTS idx_sgq_status_priority;
-- DROP TABLE IF EXISTS schedule_generation_queue;
--
-- Note: SQLite does not support DROP COLUMN. To remove the new columns from
-- schedule_templates and caption_bank, you would need to:
--   1. Create new tables without those columns
--   2. Copy data from old tables
--   3. Drop old tables
--   4. Rename new tables
-- This is typically not done unless strictly necessary.
--
-- DELETE FROM schema_migrations WHERE version = '007';
--
-- ============================================================================
-- END OF MIGRATION 007
-- ============================================================================
