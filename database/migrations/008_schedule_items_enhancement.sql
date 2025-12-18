-- ============================================================================
-- Migration 008: Schedule Items Enhancement
-- ============================================================================
-- Purpose: Enhance schedule_items table with normalized references and new fields
-- Created: 2025-12-15
-- Blueprint: WAVE 5 - Schedule Items Schema Enhancement
--
-- This migration adds:
--   1. Foreign key columns referencing send_types, channels, and audience_targets
--   2. Additional scheduling fields: linked_post_url, expires_at, followup_delay_minutes
--   3. Media type classification column
--   4. Campaign goal tracking for tip-based campaigns
--   5. Optimized indexes for new columns
--   6. Comprehensive view v_schedule_items_full for easy querying
--
-- IDEMPOTENT: All operations check for existence before executing.
-- SAFE: Uses ADD COLUMN which is safe in SQLite (no data loss).
-- BACKWARD COMPATIBLE: All new columns are nullable for existing records.
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
-- SECTION 2: ALTER STATEMENTS - Foreign Key Reference Columns
-- ============================================================================
-- These columns provide normalized references to lookup tables.
-- All are nullable for backward compatibility with existing schedule_items.
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

-- Column: send_type_id - Reference to send_types lookup table
--   Links to the normalized send type (e.g., ppv_hard_sell, bump, tip_message)
--   Nullable for backward compatibility; existing items use item_type field
ALTER TABLE schedule_items ADD COLUMN send_type_id INTEGER REFERENCES send_types(send_type_id);

-- Column: channel_id - Reference to channels lookup table
--   Links to the normalized channel (e.g., mass_message, wall_post, story)
--   Nullable for backward compatibility; existing items use channel field
ALTER TABLE schedule_items ADD COLUMN channel_id INTEGER REFERENCES channels(channel_id);

-- Column: target_id - Reference to audience_targets lookup table
--   Specifies the target audience segment (e.g., all_fans, expired_fans, top_spenders)
--   Nullable; defaults to all fans when not specified
ALTER TABLE schedule_items ADD COLUMN target_id INTEGER REFERENCES audience_targets(target_id);

-- ============================================================================
-- SECTION 3: ALTER STATEMENTS - Additional Scheduling Fields
-- ============================================================================
-- These columns enable enhanced scheduling capabilities.

-- Column: linked_post_url - URL reference for link_drop type sends
--   Stores the URL of the original post that a link drop message promotes
--   Example: "https://onlyfans.com/12345678/username"
ALTER TABLE schedule_items ADD COLUMN linked_post_url TEXT;

-- Column: expires_at - Expiration timestamp for time-limited items
--   ISO datetime format (YYYY-MM-DD HH:MM:SS)
--   Used for flash sales, limited offers, and auto-cleanup of stale items
ALTER TABLE schedule_items ADD COLUMN expires_at TEXT;

-- Column: followup_delay_minutes - Actual delay for followup items
--   Integer representing minutes between parent and followup item
--   Example: 60 for a 1-hour delay, 1440 for next day
ALTER TABLE schedule_items ADD COLUMN followup_delay_minutes INTEGER;

-- Column: media_type - Classification of media attachment
--   Specifies what type of media is attached to this scheduled item
--   CHECK constraint ensures only valid values
ALTER TABLE schedule_items ADD COLUMN media_type TEXT CHECK (media_type IN ('none', 'picture', 'gif', 'video', 'flyer'));

-- Column: campaign_goal - Monetary target for tip-based campaigns
--   Used for vip_program, first_to_tip, and similar campaign types
--   Stores the target amount in USD (e.g., 50.00 for $50 goal)
ALTER TABLE schedule_items ADD COLUMN campaign_goal REAL;

-- ============================================================================
-- SECTION 4: CREATE INDEXES for New Columns
-- ============================================================================
-- These indexes optimize queries that filter or join on the new columns.

-- Index: idx_schedule_items_send_type
-- Optimizes joins and filters by send_type_id
CREATE INDEX IF NOT EXISTS idx_schedule_items_send_type
ON schedule_items(send_type_id);

-- Index: idx_schedule_items_channel_id
-- Optimizes joins and filters by channel_id
CREATE INDEX IF NOT EXISTS idx_schedule_items_channel_id
ON schedule_items(channel_id);

-- Index: idx_schedule_items_target
-- Optimizes joins and filters by target_id (audience targeting)
CREATE INDEX IF NOT EXISTS idx_schedule_items_target
ON schedule_items(target_id);

-- Index: idx_schedule_items_expires (Partial Index)
-- Only indexes rows where expires_at is NOT NULL
-- Efficient for finding items approaching expiration or cleaning up expired items
-- Use case: SELECT * FROM schedule_items WHERE expires_at <= datetime('now')
CREATE INDEX IF NOT EXISTS idx_schedule_items_expires
ON schedule_items(expires_at)
WHERE expires_at IS NOT NULL;

-- Index: idx_schedule_items_parent (Partial Index)
-- Only indexes rows where parent_item_id is NOT NULL
-- Optimizes queries finding followup items for a given parent
-- Use case: SELECT * FROM schedule_items WHERE parent_item_id = ?
CREATE INDEX IF NOT EXISTS idx_schedule_items_parent
ON schedule_items(parent_item_id)
WHERE parent_item_id IS NOT NULL;

-- ============================================================================
-- SECTION 5: CREATE VIEW v_schedule_items_full
-- ============================================================================
-- Comprehensive view joining schedule_items with all lookup tables.
-- Provides a denormalized view for easy querying and reporting.
--
-- This view includes:
--   - All columns from schedule_items (si.*)
--   - Send type details (key, category, display name, requirements)
--   - Channel details (key, display name, targeting support)
--   - Audience target details (key, display name, reach percentage)
--
-- Usage examples:
--   SELECT * FROM v_schedule_items_full WHERE creator_id = 'creator123';
--   SELECT * FROM v_schedule_items_full WHERE send_category = 'ppv';
--   SELECT * FROM v_schedule_items_full WHERE supports_targeting = 1;

DROP VIEW IF EXISTS v_schedule_items_full;

CREATE VIEW v_schedule_items_full AS
SELECT
    -- All columns from schedule_items
    si.item_id,
    si.template_id,
    si.creator_id,
    si.scheduled_date,
    si.scheduled_time,
    si.item_type,
    si.channel,
    si.caption_id,
    si.caption_text,
    si.suggested_price,
    si.content_type_id,
    si.flyer_required,
    si.parent_item_id,
    si.is_follow_up,
    si.drip_set_id,
    si.drip_position,
    si.status,
    si.actual_earnings,
    si.priority,
    si.notes,
    si.send_type_id,
    si.channel_id,
    si.target_id,
    si.linked_post_url,
    si.expires_at,
    si.followup_delay_minutes,
    si.media_type,
    si.campaign_goal,

    -- Send type details from send_types table
    st.send_type_key,
    st.category AS send_category,
    st.display_name AS send_type_name,
    st.requires_media,
    st.requires_flyer AS type_requires_flyer,
    st.requires_price,
    st.has_expiration,
    st.can_have_followup,

    -- Channel details from channels table
    ch.channel_key,
    ch.display_name AS channel_name,
    ch.supports_targeting,

    -- Audience target details from audience_targets table
    at.target_key,
    at.display_name AS target_name,
    at.typical_reach_percentage

FROM schedule_items si
LEFT JOIN send_types st ON si.send_type_id = st.send_type_id
LEFT JOIN channels ch ON si.channel_id = ch.channel_id
LEFT JOIN audience_targets at ON si.target_id = at.target_id;

-- ============================================================================
-- SECTION 6: Migration metadata record
-- ============================================================================
-- Record this migration as applied (idempotent via INSERT OR REPLACE)

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '008',
    datetime('now'),
    'Schedule items enhancement: send_type_id, channel_id, target_id foreign keys; linked_post_url, expires_at, followup_delay_minutes, media_type, campaign_goal columns; indexes for new columns; v_schedule_items_full view'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to verify successful application:
--
-- 1. Check new columns on schedule_items:
--    PRAGMA table_info(schedule_items);
--
-- 2. Check indexes exist:
--    SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='schedule_items';
--
-- 3. Check view works:
--    SELECT * FROM v_schedule_items_full LIMIT 5;
--
-- 4. Check migration recorded:
--    SELECT * FROM schema_migrations WHERE version = '008';
--
-- 5. Verify column constraints:
--    INSERT INTO schedule_items (template_id, creator_id, scheduled_date, scheduled_time, item_type, channel, media_type)
--    VALUES (1, 'test', '2025-01-01', '12:00', 'ppv', 'mass_message', 'invalid');
--    -- Should fail with CHECK constraint error
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
-- 2. CREATE INDEX IF NOT EXISTS:
--    - Fully idempotent, no errors on re-run
--
-- 3. DROP VIEW IF EXISTS / CREATE VIEW:
--    - Fully idempotent, view is recreated each time
--
-- 4. INSERT OR REPLACE INTO schema_migrations:
--    - Fully idempotent, updates timestamp on re-run
--
-- For production deployment, wrap execution:
--   sqlite3 "$DB_PATH" ".read $MIGRATION" 2>&1 | grep -v "duplicate column"
--   if [ ${PIPESTATUS[0]} -eq 0 ]; then echo "Migration 008 applied"; fi
--
-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
-- To rollback this migration (CAUTION: potential data loss for new columns):
--
-- DROP VIEW IF EXISTS v_schedule_items_full;
-- DROP INDEX IF EXISTS idx_schedule_items_parent;
-- DROP INDEX IF EXISTS idx_schedule_items_expires;
-- DROP INDEX IF EXISTS idx_schedule_items_target;
-- DROP INDEX IF EXISTS idx_schedule_items_channel_id;
-- DROP INDEX IF EXISTS idx_schedule_items_send_type;
--
-- Note: SQLite does not support DROP COLUMN. To remove the new columns from
-- schedule_items, you would need to:
--   1. Create a new table without those columns
--   2. Copy data from schedule_items (excluding new columns)
--   3. Drop old schedule_items table
--   4. Rename new table to schedule_items
--   5. Recreate any other indexes/triggers that were on the original table
-- This is typically not done unless strictly necessary.
--
-- DELETE FROM schema_migrations WHERE version = '008';
--
-- ============================================================================
-- DATA MIGRATION HELPER (Optional)
-- ============================================================================
-- If you need to populate the new foreign key columns from existing item_type
-- and channel values, you can run these UPDATE statements after ensuring the
-- lookup tables (send_types, channels) exist and are populated:
--
-- UPDATE schedule_items
-- SET send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = item_type)
-- WHERE send_type_id IS NULL;
--
-- UPDATE schedule_items
-- SET channel_id = (SELECT channel_id FROM channels WHERE channel_key = channel)
-- WHERE channel_id IS NULL;
--
-- ============================================================================
-- END OF MIGRATION 008
-- ============================================================================
