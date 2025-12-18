-- ============================================================================
-- Rollback 014: Revert Channel Constraint Fix
-- ============================================================================
-- Purpose: Restore original channel CHECK constraint (mass_message, wall_post only)
-- Created: 2025-12-18
--
-- WARNING: This rollback will FAIL if any rows exist with channel values
-- 'targeted_message', 'story', or 'live'. You must first:
--   1. Update those rows to use 'mass_message' or 'wall_post', OR
--   2. Delete those rows
--
-- Example pre-rollback cleanup:
--   UPDATE schedule_items SET channel = 'mass_message'
--   WHERE channel IN ('targeted_message', 'story', 'live');
-- ============================================================================

-- Start transaction for atomic operation
BEGIN TRANSACTION;

-- ============================================================================
-- SECTION 1: Drop dependent view
-- ============================================================================
DROP VIEW IF EXISTS v_schedule_items_full;

-- ============================================================================
-- SECTION 2: Create table with original CHECK constraint
-- ============================================================================
CREATE TABLE schedule_items_old (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    scheduled_datetime TEXT GENERATED ALWAYS AS (scheduled_date || ' ' || scheduled_time) STORED,
    day_of_week INTEGER GENERATED ALWAYS AS (CAST(strftime('%w', scheduled_date) AS INTEGER)) STORED,
    item_type TEXT NOT NULL,
    -- ORIGINAL CHECK CONSTRAINT: Only 2 channel types
    channel TEXT NOT NULL CHECK (channel IN ('mass_message', 'wall_post')),
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
-- SECTION 3: Copy data (will FAIL if incompatible channel values exist)
-- ============================================================================
INSERT INTO schedule_items_old (
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
-- SECTION 4: Drop new table and rename old table
-- ============================================================================
DROP TABLE schedule_items;
ALTER TABLE schedule_items_old RENAME TO schedule_items;

-- ============================================================================
-- SECTION 5: Recreate all 9 indexes
-- ============================================================================
CREATE INDEX idx_items_template ON schedule_items(template_id);
CREATE INDEX idx_items_status ON schedule_items(status, scheduled_date);
CREATE INDEX idx_items_datetime ON schedule_items(scheduled_datetime);
CREATE INDEX idx_items_creator_date ON schedule_items(creator_id, scheduled_date, status);
CREATE INDEX idx_schedule_items_send_type ON schedule_items(send_type_id);
CREATE INDEX idx_schedule_items_channel_id ON schedule_items(channel_id);
CREATE INDEX idx_schedule_items_target ON schedule_items(target_id);
CREATE INDEX idx_schedule_items_expires ON schedule_items(expires_at)
WHERE expires_at IS NOT NULL;
CREATE INDEX idx_schedule_items_parent ON schedule_items(parent_item_id)
WHERE parent_item_id IS NOT NULL;

-- ============================================================================
-- SECTION 6: Recreate v_schedule_items_full view
-- ============================================================================
CREATE VIEW v_schedule_items_full AS
SELECT
    si.item_id, si.template_id, si.creator_id, si.scheduled_date, si.scheduled_time,
    si.item_type, si.channel, si.caption_id, si.caption_text, si.suggested_price,
    si.content_type_id, si.flyer_required, si.parent_item_id, si.is_follow_up,
    si.drip_set_id, si.drip_position, si.status, si.actual_earnings, si.priority,
    si.notes, si.send_type_id, si.channel_id, si.target_id, si.linked_post_url,
    si.expires_at, si.followup_delay_minutes, si.media_type, si.campaign_goal,
    st.send_type_key, st.category AS send_category, st.display_name AS send_type_name,
    st.requires_media, st.requires_flyer AS type_requires_flyer, st.requires_price,
    st.has_expiration, st.can_have_followup,
    ch.channel_key, ch.display_name AS channel_name, ch.supports_targeting,
    at.target_key, at.display_name AS target_name, at.typical_reach_percentage
FROM schedule_items si
LEFT JOIN send_types st ON si.send_type_id = st.send_type_id
LEFT JOIN channels ch ON si.channel_id = ch.channel_id
LEFT JOIN audience_targets at ON si.target_id = at.target_id;

-- ============================================================================
-- SECTION 7: Remove migration record
-- ============================================================================
DELETE FROM schema_migrations WHERE version = '014';

-- Commit transaction
COMMIT;

-- ============================================================================
-- END OF ROLLBACK 014
-- ============================================================================
