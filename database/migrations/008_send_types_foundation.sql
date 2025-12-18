-- ============================================================================
-- Migration: 008_send_types_foundation.sql
-- Version: 1.0.0
-- Created: 2025-12-15
--
-- Purpose: Foundation tables for the EROS Schedule Generator send type system.
--          Supports 21 different send types across 3 categories (Revenue,
--          Engagement, Retention), 5 channels, and 10 audience targets.
--
-- Tables Created:
--   - send_types: Defines all PPV, bump, and engagement message types
--   - channels: Delivery channels (mass_message, wall_post, etc.)
--   - audience_targets: Targeting segments for message delivery
--
-- Dependencies: None (foundation migration)
-- ============================================================================

-- ============================================================================
-- TABLE: send_types
-- Defines all 21 send types with their requirements, constraints, and behavior
-- ============================================================================
CREATE TABLE IF NOT EXISTS send_types (
    send_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_key TEXT UNIQUE NOT NULL,  -- e.g., 'ppv_video', 'bump_normal'
    category TEXT NOT NULL CHECK (category IN ('revenue', 'engagement', 'retention')),
    display_name TEXT NOT NULL,
    description TEXT,
    purpose TEXT,
    strategy TEXT,

    -- Requirements
    requires_media INTEGER DEFAULT 1,  -- 0=no, 1=yes
    requires_flyer INTEGER DEFAULT 0,
    requires_price INTEGER DEFAULT 0,
    requires_link INTEGER DEFAULT 0,

    -- Behavior
    has_expiration INTEGER DEFAULT 0,
    default_expiration_hours INTEGER,
    can_have_followup INTEGER DEFAULT 0,
    followup_delay_minutes INTEGER DEFAULT 20,

    -- Page type restriction
    page_type_restriction TEXT DEFAULT 'both' CHECK (page_type_restriction IN ('paid', 'free', 'both')),

    -- Caption guidance
    caption_length TEXT CHECK (caption_length IN ('short', 'medium', 'long')),
    emoji_recommendation TEXT CHECK (emoji_recommendation IN ('none', 'light', 'moderate', 'heavy')),

    -- Constraints
    max_per_day INTEGER,
    max_per_week INTEGER,
    min_hours_between INTEGER DEFAULT 2,

    -- Metadata
    sort_order INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================================
-- TABLE: channels
-- Delivery channels for sending content to subscribers
-- ============================================================================
CREATE TABLE IF NOT EXISTS channels (
    channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_key TEXT UNIQUE NOT NULL,  -- e.g., 'mass_message', 'wall_post'
    display_name TEXT NOT NULL,
    description TEXT,
    supports_targeting INTEGER DEFAULT 0,
    targeting_options TEXT,  -- JSON array of supported targeting
    platform_feature TEXT,  -- OF feature name
    requires_manual_send INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================================
-- TABLE: audience_targets
-- Targeting segments for message delivery
-- ============================================================================
CREATE TABLE IF NOT EXISTS audience_targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_key TEXT UNIQUE NOT NULL,  -- e.g., 'all_active', 'renew_off'
    display_name TEXT NOT NULL,
    description TEXT,
    filter_type TEXT,  -- 'segment', 'behavior', 'custom'
    filter_criteria TEXT,  -- JSON criteria
    applicable_page_types TEXT DEFAULT '["paid","free"]',  -- JSON array
    applicable_channels TEXT,  -- JSON array of channel_keys
    typical_reach_percentage REAL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================================
-- INDEXES
-- Performance optimization for common query patterns
-- ============================================================================

-- send_types indexes
CREATE INDEX IF NOT EXISTS idx_send_types_category
    ON send_types(category);

CREATE INDEX IF NOT EXISTS idx_send_types_page_type
    ON send_types(page_type_restriction);

CREATE INDEX IF NOT EXISTS idx_send_types_active
    ON send_types(is_active);

-- Composite index for schedule generation queries (active types by category, sorted)
CREATE INDEX IF NOT EXISTS idx_send_types_schedule_selection
    ON send_types(is_active, category, page_type_restriction, sort_order)
    WHERE is_active = 1;

-- channels indexes
CREATE INDEX IF NOT EXISTS idx_channels_active
    ON channels(is_active);

-- audience_targets indexes
CREATE INDEX IF NOT EXISTS idx_audience_targets_active
    ON audience_targets(is_active);

-- Index for filtering targets by page type applicability
CREATE INDEX IF NOT EXISTS idx_audience_targets_page_type
    ON audience_targets(applicable_page_types)
    WHERE is_active = 1;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
