-- ============================================================================
-- EROS Caption Type Taxonomy Migration v2
-- Migration: 006_caption_type_taxonomy_migration.sql
-- Purpose: Migrate caption_type and send_type to new standardized taxonomy
-- Author: Claude Code (SQL Pro)
-- Created: 2025-12-12
-- ============================================================================
--
-- NEW TAXONOMY:
-- caption_type_v2: ppv_unlock, bundle, tip_campaign, link_drop, feed_bump,
--                  dm_farm, like_farm, renewal_reminder, expired_winback,
--                  live_promo, descriptive_tease, text_only, normal_bump,
--                  ppv_followup, general
-- send_type_v2:    mass_message, wall_post, auto_message, campaign_message,
--                  followup_message, drip_message, segment_message, direct_message
-- is_paid_page_only: 1 for renewal_reminder and expired_winback types
--
-- SAFETY: This migration uses new columns (v2 suffix) to preserve existing data
-- ============================================================================

-- ============================================================================
-- PHASE 1: SCHEMA EXTENSION (Safe - adds columns without modifying existing)
-- ============================================================================

-- Add new columns if they don't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a workaround

-- Check and add caption_type_v2
SELECT CASE
    WHEN COUNT(*) = 0 THEN 'NEEDS_COLUMN'
    ELSE 'COLUMN_EXISTS'
END as caption_type_v2_status
FROM pragma_table_info('caption_bank')
WHERE name = 'caption_type_v2';

-- Add the columns (run these manually if columns don't exist)
-- ALTER TABLE caption_bank ADD COLUMN caption_type_v2 TEXT;
-- ALTER TABLE caption_bank ADD COLUMN send_type_v2 TEXT;
-- ALTER TABLE caption_bank ADD COLUMN is_paid_page_only INTEGER DEFAULT 0;

-- ============================================================================
-- PHASE 2: CREATE MIGRATION MAPPING TABLE
-- ============================================================================

-- Drop existing mapping table if it exists (for re-runs)
DROP TABLE IF EXISTS caption_type_migration_map;

-- Create mapping table with composite primary key
-- Uses empty string '_NULL_' sentinel for NULL matching since SQLite PKs can't be NULL
CREATE TABLE caption_type_migration_map (
    old_caption_type TEXT NOT NULL,
    old_send_type TEXT NOT NULL,           -- '_NULL_' represents NULL, '_EMPTY_' represents ''
    new_caption_type TEXT NOT NULL,
    new_send_type TEXT NOT NULL,
    is_paid_page_only INTEGER NOT NULL DEFAULT 0,
    mapping_notes TEXT,                     -- Documentation for mapping rationale
    PRIMARY KEY (old_caption_type, old_send_type)
);

-- ============================================================================
-- PHASE 3: POPULATE MAPPING RULES
-- ============================================================================

-- Insert mapping rules based on current data analysis
-- Format: (old_caption_type, old_send_type, new_caption_type, new_send_type, is_paid_page_only, notes)

INSERT INTO caption_type_migration_map VALUES
-- PPV Solo mappings (18,361 + 50 + 14 + 4 + 4 records)
('ppv_solo', 'mass_message_ppv', 'ppv_unlock', 'mass_message', 0, 'Primary PPV content'),
('ppv_solo', 'mass_message_bump', 'normal_bump', 'mass_message', 0, 'PPV follow-up bump'),
('ppv_solo', 'renewal_reminder', 'renewal_reminder', 'auto_message', 1, 'Paid page only - renewal'),
('ppv_solo', 'mass_message_ppv_followup', 'ppv_followup', 'followup_message', 0, 'PPV follow-up sequence'),
('ppv_solo', 'tip_campaign', 'tip_campaign', 'campaign_message', 0, 'Tip-based campaign'),

-- General mappings (1,207 + 1 records)
('general', 'mass_message_ppv', 'general', 'mass_message', 0, 'Generic PPV message'),
('general', 'tip_campaign', 'tip_campaign', 'campaign_message', 0, 'General tip campaign'),

-- Bump Short mappings (895 + 109 + 98 + 39 + 15 + 4 records)
('bump_short', 'mass_message_bump', 'normal_bump', 'mass_message', 0, 'Short bump reminder'),
('bump_short', 'renewal_reminder', 'renewal_reminder', 'auto_message', 1, 'Paid page only - renewal'),
('bump_short', 'mass_message_ppv_followup', 'ppv_followup', 'followup_message', 0, 'Short follow-up'),
('bump_short', 'tip_campaign', 'tip_campaign', 'campaign_message', 0, 'Tip campaign bump'),
('bump_short', 'mass_message_ppv', 'ppv_unlock', 'mass_message', 0, 'Short PPV bump'),
('bump_short', 'expired_winback', 'expired_winback', 'auto_message', 1, 'Paid page only - winback'),

-- PPV mappings (312 + 8 records)
('ppv', 'mass_message_ppv', 'ppv_unlock', 'mass_message', 0, 'Standard PPV'),
('ppv', 'tip_campaign', 'tip_campaign', 'campaign_message', 0, 'PPV tip campaign'),

-- Engagement mappings (113 + 40 records)
('engagement', 'mass_message_bump', 'dm_farm', 'mass_message', 0, 'DM engagement farming'),
('engagement', 'mass_message_ppv', 'dm_farm', 'mass_message', 0, 'Engagement with PPV'),

-- Teaser mappings (54 + 29 records)
('teaser', 'mass_message_bump', 'descriptive_tease', 'mass_message', 0, 'Teaser bump content'),
('teaser', 'mass_message_ppv', 'descriptive_tease', 'mass_message', 0, 'Teaser PPV content'),

-- Promo mappings (14 + 12 + 1 records)
('promo', 'mass_message_ppv', 'live_promo', 'mass_message', 0, 'Promotional PPV'),
('promo', 'mass_message_bump', 'live_promo', 'mass_message', 0, 'Promotional bump'),
('promo', 'expired_winback', 'expired_winback', 'auto_message', 1, 'Paid page only - promo winback'),

-- Bump mappings (13 records)
('bump', 'wall_post_bump', 'feed_bump', 'wall_post', 0, 'Wall/feed bump post'),

-- ============================================================================
-- FALLBACK MAPPINGS (for edge cases and future-proofing)
-- ============================================================================

-- Fallbacks for NULL/empty send_type scenarios
('ppv_solo', '_NULL_', 'ppv_unlock', 'mass_message', 0, 'Fallback: NULL send_type'),
('ppv_solo', '_EMPTY_', 'ppv_unlock', 'mass_message', 0, 'Fallback: empty send_type'),
('general', '_NULL_', 'general', 'mass_message', 0, 'Fallback: NULL send_type'),
('general', '_EMPTY_', 'general', 'mass_message', 0, 'Fallback: empty send_type'),
('bump_short', '_NULL_', 'normal_bump', 'mass_message', 0, 'Fallback: NULL send_type'),
('bump_short', '_EMPTY_', 'normal_bump', 'mass_message', 0, 'Fallback: empty send_type'),
('ppv', '_NULL_', 'ppv_unlock', 'mass_message', 0, 'Fallback: NULL send_type'),
('ppv', '_EMPTY_', 'ppv_unlock', 'mass_message', 0, 'Fallback: empty send_type'),
('engagement', '_NULL_', 'dm_farm', 'mass_message', 0, 'Fallback: NULL send_type'),
('engagement', '_EMPTY_', 'dm_farm', 'mass_message', 0, 'Fallback: empty send_type'),
('teaser', '_NULL_', 'descriptive_tease', 'mass_message', 0, 'Fallback: NULL send_type'),
('teaser', '_EMPTY_', 'descriptive_tease', 'mass_message', 0, 'Fallback: empty send_type'),
('promo', '_NULL_', 'live_promo', 'mass_message', 0, 'Fallback: NULL send_type'),
('promo', '_EMPTY_', 'live_promo', 'mass_message', 0, 'Fallback: empty send_type'),
('bump', '_NULL_', 'normal_bump', 'mass_message', 0, 'Fallback: NULL send_type'),
('bump', '_EMPTY_', 'normal_bump', 'mass_message', 0, 'Fallback: empty send_type'),

-- Universal fallback for completely unknown caption_types
('_UNKNOWN_', '_ANY_', 'general', 'mass_message', 0, 'Universal fallback');

-- ============================================================================
-- PHASE 4: MIGRATION UPDATE QUERY
-- ============================================================================

-- Main migration update using COALESCE and CASE for edge case handling
-- This query handles:
-- 1. Direct mapping matches (most records)
-- 2. NULL send_type values (maps to _NULL_ sentinel)
-- 3. Empty string send_type values (maps to _EMPTY_ sentinel)
-- 4. Unmapped combinations (falls back to _UNKNOWN_/_ANY_ mapping)

UPDATE caption_bank
SET
    caption_type_v2 = COALESCE(
        -- First try: exact match on both columns
        (SELECT m.new_caption_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = caption_bank.send_type),
        -- Second try: NULL send_type fallback
        (SELECT m.new_caption_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_NULL_'
           AND caption_bank.send_type IS NULL),
        -- Third try: empty string send_type fallback
        (SELECT m.new_caption_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_EMPTY_'
           AND caption_bank.send_type = ''),
        -- Final fallback: universal default
        'general'
    ),
    send_type_v2 = COALESCE(
        -- First try: exact match on both columns
        (SELECT m.new_send_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = caption_bank.send_type),
        -- Second try: NULL send_type fallback
        (SELECT m.new_send_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_NULL_'
           AND caption_bank.send_type IS NULL),
        -- Third try: empty string send_type fallback
        (SELECT m.new_send_type
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_EMPTY_'
           AND caption_bank.send_type = ''),
        -- Final fallback: universal default
        'mass_message'
    ),
    is_paid_page_only = COALESCE(
        -- First try: exact match on both columns
        (SELECT m.is_paid_page_only
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = caption_bank.send_type),
        -- Second try: NULL send_type fallback
        (SELECT m.is_paid_page_only
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_NULL_'
           AND caption_bank.send_type IS NULL),
        -- Third try: empty string send_type fallback
        (SELECT m.is_paid_page_only
         FROM caption_type_migration_map m
         WHERE m.old_caption_type = caption_bank.caption_type
           AND m.old_send_type = '_EMPTY_'
           AND caption_bank.send_type = ''),
        -- Final fallback: not paid page only
        0
    ),
    updated_at = datetime('now')
WHERE caption_type_v2 IS NULL;  -- Only update unmigrated records (idempotent)

-- ============================================================================
-- PHASE 5: CREATE INDEXES FOR NEW COLUMNS
-- ============================================================================

-- Drop indexes if they exist (for re-runs)
DROP INDEX IF EXISTS idx_caption_type_v2;
DROP INDEX IF EXISTS idx_send_type_v2;
DROP INDEX IF EXISTS idx_paid_page_only;
DROP INDEX IF EXISTS idx_caption_v2_selection;

-- Create indexes for new taxonomy columns
CREATE INDEX idx_caption_type_v2 ON caption_bank(caption_type_v2) WHERE is_active = 1;
CREATE INDEX idx_send_type_v2 ON caption_bank(send_type_v2) WHERE is_active = 1;
CREATE INDEX idx_paid_page_only ON caption_bank(is_paid_page_only) WHERE is_paid_page_only = 1;

-- Composite index for common query patterns
CREATE INDEX idx_caption_v2_selection ON caption_bank(
    is_active,
    caption_type_v2,
    send_type_v2,
    freshness_score DESC,
    performance_score DESC
) WHERE is_active = 1;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
