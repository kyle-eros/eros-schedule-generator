-- Migration 006: Caption Performance Automatic Update Triggers
-- Purpose: Automatically update caption_bank metrics when mass_messages earnings are recorded
-- Created: 2025-12-01
-- Status: APPLIED

-- ============================================================================
-- PRE-REQUISITE: Create schema_migrations table if needed
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================================
-- TRIGGER 1: Update caption_bank on INSERT with earnings
-- ============================================================================
-- When a new message is inserted with earnings and a linked caption_id,
-- automatically update the caption_bank statistics.

CREATE TRIGGER IF NOT EXISTS trg_mm_caption_performance_insert
AFTER INSERT ON mass_messages
WHEN NEW.caption_id IS NOT NULL AND NEW.earnings > 0
BEGIN
    UPDATE caption_bank
    SET times_used = times_used + 1,
        total_earnings = total_earnings + NEW.earnings,
        avg_earnings = (total_earnings + NEW.earnings) / (times_used + 1),
        last_used_date = date(NEW.sending_time),
        updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id;
END;

-- ============================================================================
-- TRIGGER 2: Update caption_bank on UPDATE with initial earnings
-- ============================================================================
-- When an existing message's earnings are set for the first time
-- (from NULL/0 to a positive value), increment times_used and add earnings.

CREATE TRIGGER IF NOT EXISTS trg_mm_caption_performance_update
AFTER UPDATE ON mass_messages
WHEN NEW.caption_id IS NOT NULL
  AND (OLD.earnings IS NULL OR OLD.earnings = 0)
  AND NEW.earnings > 0
BEGIN
    UPDATE caption_bank
    SET times_used = times_used + 1,
        total_earnings = total_earnings + NEW.earnings,
        avg_earnings = (total_earnings + NEW.earnings) / (times_used + 1),
        last_used_date = COALESCE(date(NEW.sending_time), last_used_date),
        updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id;
END;

-- ============================================================================
-- TRIGGER 3: Handle earnings corrections/updates
-- ============================================================================
-- When earnings are modified on an already-recorded message,
-- adjust the totals by the delta (new - old). Handles corrections & refunds.

CREATE TRIGGER IF NOT EXISTS trg_mm_caption_earnings_correction
AFTER UPDATE ON mass_messages
WHEN NEW.caption_id IS NOT NULL
  AND OLD.earnings IS NOT NULL
  AND OLD.earnings > 0
  AND NEW.earnings IS NOT NULL
  AND NEW.earnings != OLD.earnings
BEGIN
    UPDATE caption_bank
    SET total_earnings = total_earnings + (NEW.earnings - OLD.earnings),
        avg_earnings = CASE
            WHEN times_used > 0 THEN (total_earnings + (NEW.earnings - OLD.earnings)) / times_used
            ELSE 0.0
        END,
        updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id;
END;

-- ============================================================================
-- TRIGGER 4: Update caption_creator_performance on INSERT
-- ============================================================================
-- Maintain per-creator, per-caption performance statistics.
-- Uses UPDATE-then-conditional-INSERT pattern to handle the partial unique index.

CREATE TRIGGER IF NOT EXISTS trg_mm_caption_creator_performance_insert
AFTER INSERT ON mass_messages
WHEN NEW.caption_id IS NOT NULL AND NEW.creator_id IS NOT NULL AND NEW.earnings > 0
BEGIN
    -- First try to update existing record
    UPDATE caption_creator_performance
    SET times_used = times_used + 1,
        total_earnings = total_earnings + NEW.earnings,
        last_used_date = date(NEW.sending_time),
        updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id AND creator_id = NEW.creator_id;

    -- Insert new record only if no existing record was updated
    INSERT INTO caption_creator_performance (
        caption_id, creator_id, times_used, total_earnings,
        first_used_date, last_used_date, created_at, updated_at
    )
    SELECT NEW.caption_id, NEW.creator_id, 1, NEW.earnings,
           date(NEW.sending_time), date(NEW.sending_time),
           datetime('now'), datetime('now')
    WHERE changes() = 0;
END;

-- ============================================================================
-- TRIGGER 5: Update caption_creator_performance on UPDATE
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_mm_caption_creator_performance_update
AFTER UPDATE ON mass_messages
WHEN NEW.caption_id IS NOT NULL
  AND NEW.creator_id IS NOT NULL
  AND (OLD.earnings IS NULL OR OLD.earnings = 0)
  AND NEW.earnings > 0
BEGIN
    -- First try to update existing record
    UPDATE caption_creator_performance
    SET times_used = times_used + 1,
        total_earnings = total_earnings + NEW.earnings,
        last_used_date = date(NEW.sending_time),
        updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id AND creator_id = NEW.creator_id;

    -- Insert new record only if no existing record was updated
    INSERT INTO caption_creator_performance (
        caption_id, creator_id, times_used, total_earnings,
        first_used_date, last_used_date, created_at, updated_at
    )
    SELECT NEW.caption_id, NEW.creator_id, 1, NEW.earnings,
           date(NEW.sending_time), date(NEW.sending_time),
           datetime('now'), datetime('now')
    WHERE changes() = 0;
END;

-- ============================================================================
-- Index for trigger performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_mm_caption_earnings
ON mass_messages(caption_id, earnings)
WHERE caption_id IS NOT NULL AND earnings > 0;

-- ============================================================================
-- Migration metadata
-- ============================================================================

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES ('006', datetime('now'), 'Caption performance automatic update triggers');
