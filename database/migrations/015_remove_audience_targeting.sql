-- Migration: 015_remove_audience_targeting.sql
-- Purpose: Remove audience targeting system (targeting done manually in OnlyFans)
-- Version: 2.2.0 -> 2.3.0
-- Updated: 2025-12-18 - Fixed column list to match actual schema

-- Step 1: Recreate schedule_items WITHOUT target_id (SQLite doesn't support DROP COLUMN)
-- Actual schema columns (excluding target_id at position 22):
CREATE TABLE schedule_items_new AS
SELECT
    item_id, template_id, creator_id, scheduled_date, scheduled_time,
    item_type, channel, caption_id, caption_text, suggested_price,
    content_type_id, flyer_required, parent_item_id, is_follow_up,
    drip_set_id, drip_position, status, actual_earnings, priority,
    notes, send_type_id, channel_id, linked_post_url, expires_at,
    followup_delay_minutes, media_type, campaign_goal
FROM schedule_items;

DROP TABLE schedule_items;
ALTER TABLE schedule_items_new RENAME TO schedule_items;

-- Step 2: Recreate indexes (excluding target index)
CREATE INDEX idx_schedule_items_template ON schedule_items(template_id);
CREATE INDEX idx_schedule_items_creator ON schedule_items(creator_id);
CREATE INDEX idx_schedule_items_date ON schedule_items(scheduled_date);
CREATE INDEX idx_schedule_items_send_type ON schedule_items(send_type_id);
CREATE INDEX idx_schedule_items_channel_id ON schedule_items(channel_id);
CREATE INDEX idx_schedule_items_expires ON schedule_items(expires_at);
CREATE INDEX idx_schedule_items_parent ON schedule_items(parent_item_id);

-- Step 3: Drop audience_targets table and indexes
DROP INDEX IF EXISTS idx_audience_targets_active;
DROP INDEX IF EXISTS idx_audience_targets_page_type;
DROP TABLE IF EXISTS audience_targets;

-- Step 4: Recreate v_schedule_items_full view WITHOUT audience_targets
DROP VIEW IF EXISTS v_schedule_items_full;
CREATE VIEW v_schedule_items_full AS
SELECT
    si.*,
    st.send_type_key,
    st.display_name AS send_type_name,
    st.category,
    ch.channel_key,
    ch.display_name AS channel_name,
    cb.caption_text AS original_caption,
    ct.type_name AS content_type_name
FROM schedule_items si
LEFT JOIN send_types st ON si.send_type_id = st.send_type_id
LEFT JOIN channels ch ON si.channel_id = ch.channel_id
LEFT JOIN caption_bank cb ON si.caption_id = cb.caption_id
LEFT JOIN content_types ct ON si.content_type_id = ct.content_type_id;
