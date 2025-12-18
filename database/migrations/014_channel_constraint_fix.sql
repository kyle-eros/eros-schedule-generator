-- ============================================================================
-- Migration 014: Channel Constraint Fix
-- ============================================================================
-- Purpose: Expand channel CHECK constraint to allow all 5 channel types
-- Created: 2025-12-18
--
-- This migration:
--   1. Recreates schedule_items table with expanded CHECK constraint
--   2. Current CHECK: ('mass_message', 'wall_post')
--   3. New CHECK: ('mass_message', 'wall_post', 'targeted_message', 'story', 'live')
--
-- WHY TABLE RECREATION:
--   SQLite does not support ALTER TABLE to modify CHECK constraints.
--   Must recreate the table with the new constraint.
--
-- SAFE: All data is preserved through table recreation pattern.
-- BACKUP RECOMMENDED: Back up database before running.
-- ============================================================================

-- Start transaction for atomic operation
BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: Drop dependent view
-- ============================================================================
DROP VIEW IF EXISTS v_schedule_items_full;

-- ============================================================================
-- SECTION 2: Create new table with expanded CHECK constraint
-- ============================================================================
CREATE TABLE schedule_items_new (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    scheduled_datetime TEXT GENERATED ALWAYS AS (scheduled_date || ' ' || scheduled_time) STORED,
    day_of_week INTEGER GENERATED ALWAYS AS (CAST(strftime('%w', scheduled_date) AS INTEGER)) STORED,
    item_type TEXT NOT NULL,
    -- UPDATED CHECK CONSTRAINT: Now includes all 5 channel types
    channel TEXT NOT NULL CHECK (channel IN ('mass_message', 'wall_post', 'targeted_message', 'story', 'live')),
    caption_id INTEGER,
    caption_text TEXT,
    suggested_price REAL,
    content_type_id INTEGER,
    flyer_required INTEGER DEFAULT 0,
    parent_item_id INTEGER,
    is_follow_up INTEGER DEFAULT 0,
    drip_set_id TEXT,
    drip_position INTEGER,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'sent', 'skipped')),
    actual_earnings REAL,
    priority INTEGER DEFAULT 5,
    notes TEXT,
    send_type_id INTEGER REFERENCES send_types(send_type_id),
    channel_id INTEGER REFERENCES channels(channel_id),
    target_id INTEGER REFERENCES audience_targets(target_id),
    linked_post_url TEXT,
    expires_at TEXT,
    followup_delay_minutes INTEGER,
    media_type TEXT CHECK (media_type IN ('none', 'picture', 'gif', 'video', 'flyer')),
    campaign_goal REAL,
    FOREIGN KEY (template_id) REFERENCES schedule_templates(template_id),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id),
    FOREIGN KEY (content_type_id) REFERENCES content_types(content_type_id),
    FOREIGN KEY (parent_item_id) REFERENCES schedule_items(item_id)
);

-- ============================================================================
-- SECTION 3: Copy all data from old table
-- ============================================================================
-- Note: Generated columns (scheduled_datetime, day_of_week) are automatically
-- computed during INSERT and should not be included in the column list
INSERT INTO schedule_items_new (
    item_id, template_id, creator_id, scheduled_date, scheduled_time,
    item_type, channel, caption_id, caption_text, suggested_price,
    content_type_id, flyer_required, parent_item_id, is_follow_up,
    drip_set_id, drip_position, status, actual_earnings, priority, notes,
    send_type_id, channel_id, target_id, linked_post_url, expires_at,
    followup_delay_minutes, media_type, campaign_goal
)
SELECT
    item_id, template_id, creator_id, scheduled_date, scheduled_time,
    item_type, channel, caption_id, caption_text, suggested_price,
    content_type_id, flyer_required, parent_item_id, is_follow_up,
    drip_set_id, drip_position, status, actual_earnings, priority, notes,
    send_type_id, channel_id, target_id, linked_post_url, expires_at,
    followup_delay_minutes, media_type, campaign_goal
FROM schedule_items;

-- ============================================================================
-- SECTION 4: Drop old table and rename new table
-- ============================================================================
DROP TABLE schedule_items;
ALTER TABLE schedule_items_new RENAME TO schedule_items;

-- ============================================================================
-- SECTION 5: Recreate all 9 indexes
-- ============================================================================

-- Index 1: Template ID (for schedule lookup)
CREATE INDEX idx_items_template ON schedule_items(template_id);

-- Index 2: Status + Date (for pending items query)
CREATE INDEX idx_items_status ON schedule_items(status, scheduled_date);

-- Index 3: DateTime (for chronological queries)
CREATE INDEX idx_items_datetime ON schedule_items(scheduled_datetime);

-- Index 4: Creator + Date + Status (for creator schedule view)
CREATE INDEX idx_items_creator_date ON schedule_items(creator_id, scheduled_date, status);

-- Index 5: Send Type ID (for send type analysis)
CREATE INDEX idx_schedule_items_send_type ON schedule_items(send_type_id);

-- Index 6: Channel ID (for channel analysis)
CREATE INDEX idx_schedule_items_channel_id ON schedule_items(channel_id);

-- Index 7: Target ID (for audience targeting)
CREATE INDEX idx_schedule_items_target ON schedule_items(target_id);

-- Index 8: Expires At (partial - only non-null values)
CREATE INDEX idx_schedule_items_expires ON schedule_items(expires_at)
WHERE expires_at IS NOT NULL;

-- Index 9: Parent Item ID (partial - only non-null values, for followups)
CREATE INDEX idx_schedule_items_parent ON schedule_items(parent_item_id)
WHERE parent_item_id IS NOT NULL;

-- ============================================================================
-- SECTION 6: Recreate v_schedule_items_full view
-- ============================================================================
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
-- SECTION 7: Record migration in schema_migrations
-- ============================================================================
INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '014',
    datetime('now'),
    'Expand channel CHECK constraint to allow all 5 channel types (mass_message, wall_post, targeted_message, story, live)'
);

-- Commit transaction
COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================
-- 1. Verify new constraint:
--    INSERT INTO schedule_items (template_id, creator_id, scheduled_date, scheduled_time, item_type, channel)
--    VALUES (1, 'test', '2025-01-01', '10:00', 'test', 'targeted_message');
--    -- Should succeed (previously would fail)
--
-- 2. Verify old constraint values still work:
--    INSERT INTO schedule_items (template_id, creator_id, scheduled_date, scheduled_time, item_type, channel)
--    VALUES (1, 'test', '2025-01-01', '10:00', 'test', 'mass_message');
--    -- Should succeed
--
-- 3. Verify invalid values still rejected:
--    INSERT INTO schedule_items (template_id, creator_id, scheduled_date, scheduled_time, item_type, channel)
--    VALUES (1, 'test', '2025-01-01', '10:00', 'test', 'invalid_channel');
--    -- Should fail with CHECK constraint
--
-- 4. Verify row count preserved:
--    SELECT COUNT(*) FROM schedule_items;
--
-- 5. Verify all 9 indexes exist:
--    SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='schedule_items';
--
-- 6. Verify view works:
--    SELECT * FROM v_schedule_items_full LIMIT 1;
--
-- 7. Verify migration recorded:
--    SELECT * FROM schema_migrations WHERE version = '014';
--
-- ============================================================================
-- END OF MIGRATION 014
-- ============================================================================
