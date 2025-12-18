-- ============================================================================
-- Migration: 009_ppv_restructure.sql
-- Version: 1.0.0
-- Created: 2025-12-16
--
-- Purpose: Restructure PPV send types to support expanded revenue capabilities.
--          This migration renames ppv_video to ppv_unlock, adds ppv_wall for
--          free pages, adds tip_goal for paid pages, and deprecates ppv_message.
--
-- Changes:
--   1. Rename ppv_video -> ppv_unlock (unified PPV for pictures and videos)
--   2. Add ppv_wall send type (FREE pages only, wall-based PPV)
--   3. Add tip_goal send type (PAID pages only, tip campaigns)
--   4. Add tip_goal columns to schedule_items (tip_goal_mode, goal_amount)
--   5. Mark ppv_message as deprecated (30-day transition period)
--   6. Add caption requirements for new send types
--   7. Add content compatibility for new send types
--
-- Before: 21 send types (7 revenue, 9 engagement, 5 retention)
-- After:  22 send types (9 revenue, 9 engagement, 4 retention*)
--         *ppv_message remains active during 30-day transition
--
-- Dependencies: 008_send_types_foundation.sql, 008_send_types_seed_data.sql
-- ============================================================================

-- ============================================================================
-- SECTION 1: Ensure schema_migrations table exists
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================================
-- SECTION 2: Rename ppv_video to ppv_unlock
-- ============================================================================
-- Rationale: ppv_unlock better describes the unified PPV functionality that
-- supports both pictures and videos. The previous name implied video-only.

UPDATE send_types
SET send_type_key = 'ppv_unlock',
    display_name = 'PPV Unlock',
    description = 'Primary PPV for pictures and videos. Main revenue driver with compelling preview and clear value proposition.'
WHERE send_type_key = 'ppv_video';

-- Update caption requirements to reflect the rename
UPDATE send_type_caption_requirements
SET notes = 'Primary caption type for PPV unlock sends'
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'ppv_unlock')
  AND caption_type = 'ppv_video';

-- ============================================================================
-- SECTION 3: Add ppv_wall send type (FREE pages only)
-- ============================================================================
-- Purpose: Wall-based PPV for free pages. Posts locked content directly on the
-- wall rather than via mass message. Requires flyer for visual appeal.

INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order, is_active
) VALUES (
    'ppv_wall', 'revenue', 'PPV Wall Post',
    'Wall-based PPV for free pages. Posts locked content on wall with flyer preview.',
    'Revenue from wall PPV posts on free pages',
    'Post locked content on wall with eye-catching flyer. Visible to all visitors.',
    1, 1, 1, 0,
    0, NULL, 1, 20,
    'free', 'medium', 'moderate',
    3, NULL, 3, 15, 1
);

-- ============================================================================
-- SECTION 4: Add tip_goal send type (PAID pages only)
-- ============================================================================
-- Purpose: Tip campaign with three modes: goal_based (collective goal),
-- individual (per-person tips), competitive (tip race). Supports 24-hour
-- expiration for urgency.

INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order, is_active
) VALUES (
    'tip_goal', 'revenue', 'Tip Goal',
    'Tip campaign with goal-based, individual, or competitive modes. Creates engagement through gamification.',
    'Revenue from tip campaigns with clear goal targets',
    'Create tip goal campaigns with clear rewards. Use goal_based for collective goals, individual for per-person rewards, competitive for tip races.',
    1, 0, 1, 0,
    1, 24, 0, NULL,
    'paid', 'medium', 'heavy',
    2, NULL, 4, 18, 1
);

-- ============================================================================
-- SECTION 5: Add columns to schedule_items for tip_goal support
-- ============================================================================
-- These columns enable tip goal mode tracking and goal amount specification.
--
-- IMPORTANT: SQLite does not support IF NOT EXISTS for ALTER TABLE ADD COLUMN.
-- "duplicate column name" errors on re-run are EXPECTED and HARMLESS.

-- Column: tip_goal_mode - Specifies the type of tip goal campaign
--   goal_based: Collective goal where all tips contribute to a single target
--   individual: Per-person tip target for individual rewards
--   competitive: Tip race where highest tipper wins
ALTER TABLE schedule_items ADD COLUMN tip_goal_mode TEXT CHECK (tip_goal_mode IN ('goal_based', 'individual', 'competitive'));

-- Column: goal_amount - Target tip amount in USD
--   Used in conjunction with tip_goal_mode to specify the goal target
--   Example: 100.00 for a $100 collective goal
ALTER TABLE schedule_items ADD COLUMN goal_amount REAL;

-- ============================================================================
-- SECTION 6: Mark ppv_message as deprecated
-- ============================================================================
-- Rationale: ppv_message functionality is now covered by ppv_unlock.
-- Keeping is_active=1 for 30-day rollback capability.
-- After transition period (2025-01-16), set is_active=0.

UPDATE send_types
SET description = 'DEPRECATED: Merged into ppv_unlock. Will be removed after 30-day transition period (2025-01-16). Use ppv_unlock for all PPV sends.',
    is_active = 1
WHERE send_type_key = 'ppv_message';

-- ============================================================================
-- SECTION 7: Add send_type_caption_requirements for new types
-- ============================================================================
-- Define which caption types are compatible with each new send type.
-- Priority: 1=primary (best match), 2=good, 3=acceptable, 4=secondary, 5=fallback

-- ppv_wall caption requirements
INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_video', 1, 'Primary caption type for PPV wall posts'
FROM send_types WHERE send_type_key = 'ppv_wall';

INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_message', 2, 'Fallback PPV captions with large inventory'
FROM send_types WHERE send_type_key = 'ppv_wall';

INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle', 3, 'Bundle-style captions can work for wall PPV'
FROM send_types WHERE send_type_key = 'ppv_wall';

-- tip_goal caption requirements
INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'first_to_tip', 1, 'Gamified tip competition captions are ideal'
FROM send_types WHERE send_type_key = 'tip_goal';

INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'vip_program', 2, 'VIP-style captions work for goal-based campaigns'
FROM send_types WHERE send_type_key = 'tip_goal';

INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'game_post', 3, 'Game post captions can be adapted for tip goals'
FROM send_types WHERE send_type_key = 'tip_goal';

-- Update ppv_unlock to also accept ppv_video captions (for backward compatibility)
INSERT OR IGNORE INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_video', 1, 'Primary caption type for PPV unlock sends'
FROM send_types WHERE send_type_key = 'ppv_unlock';

-- ============================================================================
-- SECTION 8: Add send_type_content_compatibility for new types
-- ============================================================================
-- Define which content types are compatible with each new send type.
-- Using the same pattern as ppv_video: most content types are 'allowed',
-- high-value content is 'recommended'.

-- ppv_wall content compatibility (copy from ppv_unlock/ppv_video pattern)
INSERT OR IGNORE INTO send_type_content_compatibility (send_type_id, content_type_id, compatibility, notes)
SELECT
    (SELECT send_type_id FROM send_types WHERE send_type_key = 'ppv_wall'),
    content_type_id,
    compatibility,
    'Content compatibility inherited from PPV unlock pattern'
FROM send_type_content_compatibility
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'ppv_unlock');

-- tip_goal content compatibility (broad compatibility for tip campaigns)
INSERT OR IGNORE INTO send_type_content_compatibility (send_type_id, content_type_id, compatibility, notes)
SELECT
    (SELECT send_type_id FROM send_types WHERE send_type_key = 'tip_goal'),
    content_type_id,
    'allowed',
    'Tip goals can feature any content type as reward'
FROM send_type_content_compatibility
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'ppv_unlock')
GROUP BY content_type_id;

-- ============================================================================
-- SECTION 9: Create indexes for new columns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_schedule_items_tip_goal_mode
ON schedule_items(tip_goal_mode)
WHERE tip_goal_mode IS NOT NULL;

-- ============================================================================
-- SECTION 10: Update sort_order for logical grouping
-- ============================================================================
-- Ensure new revenue types are grouped appropriately in the sort order.

UPDATE send_types SET sort_order = 10 WHERE send_type_key = 'ppv_unlock';
UPDATE send_types SET sort_order = 15 WHERE send_type_key = 'ppv_wall';
UPDATE send_types SET sort_order = 18 WHERE send_type_key = 'tip_goal';

-- ============================================================================
-- SECTION 11: Migration metadata record
-- ============================================================================

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '009_ppv_restructure',
    datetime('now'),
    'PPV restructure: rename ppv_video->ppv_unlock, add ppv_wall (free pages), add tip_goal (paid pages), deprecate ppv_message, add tip_goal columns to schedule_items'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to verify successful application:
--
-- 1. Check send_types count by category:
--    SELECT category, COUNT(*) as count FROM send_types WHERE is_active = 1 GROUP BY category;
--    Expected: revenue=9, engagement=9, retention=5 (ppv_message still active during transition)
--
-- 2. Verify ppv_unlock rename:
--    SELECT send_type_key, display_name FROM send_types WHERE send_type_id = 1;
--    Expected: ppv_unlock, PPV Unlock
--
-- 3. Verify new send types exist:
--    SELECT send_type_key, page_type_restriction FROM send_types WHERE send_type_key IN ('ppv_wall', 'tip_goal');
--    Expected: ppv_wall/free, tip_goal/paid
--
-- 4. Check deprecated ppv_message:
--    SELECT send_type_key, is_active, description FROM send_types WHERE send_type_key = 'ppv_message';
--    Expected: is_active=1, description contains 'DEPRECATED'
--
-- 5. Verify new columns on schedule_items:
--    PRAGMA table_info(schedule_items);
--    Expected: tip_goal_mode and goal_amount columns present
--
-- 6. Check caption requirements for new types:
--    SELECT st.send_type_key, stcr.caption_type, stcr.priority
--    FROM send_type_caption_requirements stcr
--    JOIN send_types st ON st.send_type_id = stcr.send_type_id
--    WHERE st.send_type_key IN ('ppv_wall', 'tip_goal')
--    ORDER BY st.send_type_key, stcr.priority;
--
-- 7. Check migration recorded:
--    SELECT * FROM schema_migrations WHERE version = '009_ppv_restructure';
--
-- ============================================================================
-- IDEMPOTENCY NOTES
-- ============================================================================
-- This migration is designed to be re-runnable with the following behavior:
--
-- 1. UPDATE statements for ppv_unlock rename:
--    - Idempotent: re-running updates the same row to the same values
--
-- 2. INSERT OR IGNORE for new send types:
--    - Idempotent: ignores insert if send_type_key already exists
--
-- 3. ALTER TABLE ADD COLUMN statements:
--    - Will produce "duplicate column name" errors on re-run
--    - These errors are HARMLESS and should be ignored
--    - To suppress: sqlite3 db.db ".read file.sql" 2>&1 | grep -v "duplicate column"
--
-- 4. INSERT OR IGNORE for caption requirements:
--    - Idempotent: unique constraint prevents duplicates
--
-- 5. CREATE INDEX IF NOT EXISTS:
--    - Fully idempotent, no errors on re-run
--
-- 6. INSERT OR REPLACE for schema_migrations:
--    - Fully idempotent, updates timestamp on re-run
--
-- ============================================================================
-- ROLLBACK SCRIPT (Emergency Reversal)
-- ============================================================================
-- CAUTION: Only use if critical issues are discovered within 30-day transition.
-- This rollback restores the pre-migration state.
--
-- -- Step 1: Rename ppv_unlock back to ppv_video
-- UPDATE send_types
-- SET send_type_key = 'ppv_video',
--     display_name = 'PPV Video',
--     description = 'Standard PPV video sale. Primary revenue driver with long-form caption and heavy emoji usage.'
-- WHERE send_type_key = 'ppv_unlock';
--
-- -- Step 2: Remove new send types
-- DELETE FROM send_type_content_compatibility
-- WHERE send_type_id IN (SELECT send_type_id FROM send_types WHERE send_type_key IN ('ppv_wall', 'tip_goal'));
--
-- DELETE FROM send_type_caption_requirements
-- WHERE send_type_id IN (SELECT send_type_id FROM send_types WHERE send_type_key IN ('ppv_wall', 'tip_goal'));
--
-- DELETE FROM send_types WHERE send_type_key IN ('ppv_wall', 'tip_goal');
--
-- -- Step 3: Restore ppv_message description
-- UPDATE send_types
-- SET description = 'Mass message with PPV unlock content. Adjustable pricing based on content value.',
--     is_active = 1
-- WHERE send_type_key = 'ppv_message';
--
-- -- Step 4: Drop index (optional, does not affect functionality)
-- DROP INDEX IF EXISTS idx_schedule_items_tip_goal_mode;
--
-- -- Step 5: Note on columns
-- -- SQLite does not support DROP COLUMN. The tip_goal_mode and goal_amount columns
-- -- will remain but can be ignored. To fully remove them, table recreation is required.
--
-- -- Step 6: Remove migration record
-- DELETE FROM schema_migrations WHERE version = '009_ppv_restructure';
--
-- ============================================================================
-- POST-TRANSITION CLEANUP (Run after 2025-01-16)
-- ============================================================================
-- After the 30-day transition period, run these statements to complete the
-- deprecation of ppv_message:
--
-- -- Deactivate ppv_message
-- UPDATE send_types SET is_active = 0 WHERE send_type_key = 'ppv_message';
--
-- -- Verify final counts
-- SELECT category, COUNT(*) as count FROM send_types WHERE is_active = 1 GROUP BY category;
-- Expected: revenue=9, engagement=9, retention=4
--
-- ============================================================================
-- END OF MIGRATION 009
-- ============================================================================
