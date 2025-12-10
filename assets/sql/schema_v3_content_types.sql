-- ============================================================================
-- EROS Schema v3.0: 20+ Content Type Support
-- ============================================================================
-- Description: Database schema extensions to support 20+ OnlyFans content types
--              with new template tables for VIP posts, tip incentives, link drops,
--              engagement farming, retention campaigns, and bump variants.
--
-- Author: EROS Schedule Generator
-- Version: 3.0
-- Date: 2025-12-09
--
-- Prerequisites:
--   - Schema v2.6 must be applied (poll_bank, game_wheel_configs, free_preview_bank)
--   - Backup database before running: cp eros_sd_main.db eros_sd_main_backup_$(date +%Y%m%d_%H%M%S).db
--
-- Usage:
--   sqlite3 ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db < schema_v3_content_types.sql
-- ============================================================================

-- Enable foreign key enforcement
PRAGMA foreign_keys = ON;

-- ============================================================================
-- SECTION 1: ALTER EXISTING TABLES
-- ============================================================================

-- 1.1 Add schedulable_type column to caption_bank
-- Values: ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle, etc.
-- This enables differentiation between PPV captions and follow-up/bump captions
ALTER TABLE caption_bank ADD COLUMN schedulable_type TEXT DEFAULT 'ppv';

-- Create index for schedulable_type queries
CREATE INDEX IF NOT EXISTS idx_caption_schedulable_type
ON caption_bank(schedulable_type, is_active)
WHERE is_active = 1;

-- 1.2 Add page_type_filter to poll_bank
-- Allows filtering polls by paid/free/both page types
ALTER TABLE poll_bank ADD COLUMN page_type_filter TEXT DEFAULT 'both'
CHECK (page_type_filter IN ('paid', 'free', 'both'));

-- 1.3 Add page_type_filter to free_preview_bank
ALTER TABLE free_preview_bank ADD COLUMN page_type_filter TEXT DEFAULT 'both'
CHECK (page_type_filter IN ('paid', 'free', 'both'));

-- 1.4 Add page_type_filter to game_wheel_configs
ALTER TABLE game_wheel_configs ADD COLUMN page_type_filter TEXT DEFAULT 'both'
CHECK (page_type_filter IN ('paid', 'free', 'both'));

-- ============================================================================
-- SECTION 2: NEW TEMPLATE TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 2.1 VIP Post Templates (Paid Pages Only)
-- ----------------------------------------------------------------------------
-- VIP posts are premium content offerings exclusive to paid page subscribers
-- at elevated price points (typically $200+). These drive high-value conversions.
CREATE TABLE IF NOT EXISTS vip_post_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_hash TEXT UNIQUE NOT NULL,
    template_text TEXT NOT NULL,
    vip_tier_price REAL DEFAULT 200.00,
    tone TEXT,
    emoji_style TEXT,
    flyer_required INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 0,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    avg_conversion_rate REAL DEFAULT 0.0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'paid' CHECK (page_type_filter = 'paid'),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ----------------------------------------------------------------------------
-- 2.2 Tip Incentive Templates (First To Tip, Tip Goals)
-- ----------------------------------------------------------------------------
-- Tip incentives encourage subscriber engagement through gamification
-- Common types: first-to-tip rewards, tip goal unlocks, tip menu items
CREATE TABLE IF NOT EXISTS tip_incentive_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_hash TEXT UNIQUE NOT NULL,
    template_text TEXT NOT NULL,
    tip_goal_amount REAL,
    expiration_hours INTEGER DEFAULT 24,
    incentive_type TEXT DEFAULT 'first_to_tip' CHECK (incentive_type IN ('first_to_tip', 'tip_goal', 'tip_menu', 'tip_race')),
    tone TEXT,
    emoji_style TEXT,
    flyer_required INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 0,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    avg_conversion_rate REAL DEFAULT 0.0,
    avg_tip_amount REAL DEFAULT 0.0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'both' CHECK (page_type_filter IN ('paid', 'free', 'both')),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ----------------------------------------------------------------------------
-- 2.3 Link Drop Templates
-- ----------------------------------------------------------------------------
-- Link drops are time-sensitive shareable links for campaigns, wall posts,
-- PPVs, and bundles. They create urgency and enable cross-promotion.
CREATE TABLE IF NOT EXISTS link_drop_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_hash TEXT UNIQUE NOT NULL,
    template_text TEXT NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN ('campaign', 'wall_post', 'ppv', 'bundle', 'promo', 'other')),
    expiration_hours INTEGER DEFAULT 24,
    tone TEXT,
    emoji_style TEXT,
    flyer_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 1,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    click_through_rate REAL DEFAULT 0.0,
    conversion_rate REAL DEFAULT 0.0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'both' CHECK (page_type_filter IN ('paid', 'free', 'both')),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ----------------------------------------------------------------------------
-- 2.4 Engagement Templates (DM Farm, Like Farm, Comment Farm)
-- ----------------------------------------------------------------------------
-- Engagement farming templates encourage subscriber interaction to boost
-- algorithm visibility and build community connection.
CREATE TABLE IF NOT EXISTS engagement_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_hash TEXT UNIQUE NOT NULL,
    template_text TEXT NOT NULL,
    engagement_type TEXT NOT NULL CHECK (engagement_type IN ('dm_farm', 'like_farm', 'comment_farm', 'emoji_farm', 'question_prompt')),
    incentive_description TEXT,
    call_to_action TEXT,
    tone TEXT,
    emoji_style TEXT,
    flyer_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 1,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    avg_engagement_rate REAL DEFAULT 0.0,
    avg_response_count INTEGER DEFAULT 0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'both' CHECK (page_type_filter IN ('paid', 'free', 'both')),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ----------------------------------------------------------------------------
-- 2.5 Retention Templates (Renew On, Expired Subscriber, Churn Prevention)
-- ----------------------------------------------------------------------------
-- Retention templates target subscribers at risk of churning or already
-- expired to re-engage them with incentives and compelling messaging.
CREATE TABLE IF NOT EXISTS retention_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_hash TEXT UNIQUE NOT NULL,
    template_text TEXT NOT NULL,
    retention_type TEXT NOT NULL CHECK (retention_type IN ('renew_on_post', 'renew_on_mm', 'expired_subscriber', 'churn_prevention', 'winback', 'loyalty_reward')),
    incentive_description TEXT,
    discount_percentage REAL DEFAULT 0.0,
    urgency_level TEXT DEFAULT 'medium' CHECK (urgency_level IN ('low', 'medium', 'high', 'critical')),
    tone TEXT,
    emoji_style TEXT,
    flyer_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 1,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    avg_reactivation_rate REAL DEFAULT 0.0,
    avg_revenue_recovered REAL DEFAULT 0.0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'paid' CHECK (page_type_filter IN ('paid', 'free', 'both')),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ----------------------------------------------------------------------------
-- 2.6 Bump Variants (Flyer, Descriptive, Text-Only, Normal)
-- ----------------------------------------------------------------------------
-- Bump variants are follow-up messages sent after initial PPV to increase
-- conversion. Different styles suit different content types and price points.
CREATE TABLE IF NOT EXISTS bump_variants (
    variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_hash TEXT UNIQUE NOT NULL,
    variant_text TEXT NOT NULL,
    bump_type TEXT NOT NULL CHECK (bump_type IN ('flyer_gif', 'descriptive', 'text_only', 'normal', 'urgency', 'scarcity', 'social_proof')),
    bump_style TEXT DEFAULT 'standard' CHECK (bump_style IN ('standard', 'playful', 'urgent', 'casual', 'seductive')),
    flyer_required INTEGER DEFAULT 0,
    recommended_delay_minutes INTEGER DEFAULT 30,
    tone TEXT,
    emoji_style TEXT,
    is_active INTEGER DEFAULT 1,
    is_universal INTEGER DEFAULT 1,
    creator_id TEXT,
    times_used INTEGER DEFAULT 0,
    avg_conversion_lift REAL DEFAULT 0.0,
    performance_score REAL DEFAULT 50.0 CHECK (performance_score >= 0 AND performance_score <= 100),
    freshness_score REAL DEFAULT 100.0 CHECK (freshness_score >= 0 AND freshness_score <= 100),
    page_type_filter TEXT DEFAULT 'both' CHECK (page_type_filter IN ('paid', 'free', 'both')),
    last_used_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ============================================================================
-- SECTION 3: PERFORMANCE INDEXES
-- ============================================================================

-- VIP Post Templates indexes
CREATE INDEX IF NOT EXISTS idx_vip_active
ON vip_post_templates(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_vip_creator
ON vip_post_templates(creator_id, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_vip_selection
ON vip_post_templates(is_active, creator_id, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- Tip Incentive Templates indexes
CREATE INDEX IF NOT EXISTS idx_tip_active
ON tip_incentive_templates(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_tip_creator
ON tip_incentive_templates(creator_id, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_tip_type
ON tip_incentive_templates(incentive_type, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_tip_selection
ON tip_incentive_templates(is_active, incentive_type, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- Link Drop Templates indexes
CREATE INDEX IF NOT EXISTS idx_link_active
ON link_drop_templates(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_link_type
ON link_drop_templates(link_type, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_link_selection
ON link_drop_templates(is_active, link_type, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- Engagement Templates indexes
CREATE INDEX IF NOT EXISTS idx_engagement_type
ON engagement_templates(engagement_type, is_active);

CREATE INDEX IF NOT EXISTS idx_engagement_active
ON engagement_templates(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_engagement_selection
ON engagement_templates(is_active, engagement_type, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- Retention Templates indexes
CREATE INDEX IF NOT EXISTS idx_retention_type
ON retention_templates(retention_type, is_active);

CREATE INDEX IF NOT EXISTS idx_retention_active
ON retention_templates(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_retention_urgency
ON retention_templates(urgency_level, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_retention_selection
ON retention_templates(is_active, retention_type, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- Bump Variants indexes
CREATE INDEX IF NOT EXISTS idx_bump_type
ON bump_variants(bump_type, is_active);

CREATE INDEX IF NOT EXISTS idx_bump_active
ON bump_variants(is_active, page_type_filter);

CREATE INDEX IF NOT EXISTS idx_bump_style
ON bump_variants(bump_style, is_active)
WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_bump_selection
ON bump_variants(is_active, bump_type, freshness_score DESC, performance_score DESC)
WHERE is_active = 1;

-- ============================================================================
-- SECTION 4: UNIFIED CONTENT VIEW
-- ============================================================================

-- Drop existing view if present (for idempotent migrations)
DROP VIEW IF EXISTS all_schedulable_content;

-- Unified view for all schedulable content across all template tables
-- Enables single-query access to all content types for the schedule generator
CREATE VIEW IF NOT EXISTS all_schedulable_content AS

-- Caption bank content (PPV, follow-ups, bundles)
SELECT
    caption_id AS content_id,
    'caption_bank' AS source_table,
    caption_hash AS content_hash,
    caption_text AS content_text,
    COALESCE(schedulable_type, 'ppv') AS content_type,
    caption_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    'both' AS page_type_filter,
    last_used_date,
    created_at
FROM caption_bank
WHERE is_active = 1

UNION ALL

-- VIP post templates
SELECT
    template_id AS content_id,
    'vip_post_templates' AS source_table,
    template_hash AS content_hash,
    template_text AS content_text,
    'vip_post' AS content_type,
    NULL AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM vip_post_templates
WHERE is_active = 1

UNION ALL

-- Tip incentive templates
SELECT
    template_id AS content_id,
    'tip_incentive_templates' AS source_table,
    template_hash AS content_hash,
    template_text AS content_text,
    'tip_incentive' AS content_type,
    incentive_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM tip_incentive_templates
WHERE is_active = 1

UNION ALL

-- Link drop templates
SELECT
    template_id AS content_id,
    'link_drop_templates' AS source_table,
    template_hash AS content_hash,
    template_text AS content_text,
    'link_drop' AS content_type,
    link_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM link_drop_templates
WHERE is_active = 1

UNION ALL

-- Engagement templates
SELECT
    template_id AS content_id,
    'engagement_templates' AS source_table,
    template_hash AS content_hash,
    template_text AS content_text,
    'engagement' AS content_type,
    engagement_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM engagement_templates
WHERE is_active = 1

UNION ALL

-- Retention templates
SELECT
    template_id AS content_id,
    'retention_templates' AS source_table,
    template_hash AS content_hash,
    template_text AS content_text,
    'retention' AS content_type,
    retention_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM retention_templates
WHERE is_active = 1

UNION ALL

-- Bump variants
SELECT
    variant_id AS content_id,
    'bump_variants' AS source_table,
    variant_hash AS content_hash,
    variant_text AS content_text,
    'bump' AS content_type,
    bump_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    page_type_filter,
    last_used_date,
    created_at
FROM bump_variants
WHERE is_active = 1

UNION ALL

-- Poll bank
SELECT
    poll_id AS content_id,
    'poll_bank' AS source_table,
    poll_hash AS content_hash,
    question_text AS content_text,
    'poll' AS content_type,
    poll_category AS subtype,
    100.0 AS freshness_score,  -- Polls don't decay the same way
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    NULL AS emoji_style,
    COALESCE(page_type_filter, 'both') AS page_type_filter,
    last_used_date,
    created_at
FROM poll_bank
WHERE is_active = 1

UNION ALL

-- Free preview bank
SELECT
    preview_id AS content_id,
    'free_preview_bank' AS source_table,
    preview_hash AS content_hash,
    preview_text AS content_text,
    'free_preview' AS content_type,
    preview_type AS subtype,
    freshness_score,
    performance_score,
    times_used,
    creator_id,
    is_universal,
    tone,
    emoji_style,
    COALESCE(page_type_filter, 'both') AS page_type_filter,
    last_used_date,
    created_at
FROM free_preview_bank
WHERE is_active = 1;

-- ============================================================================
-- SECTION 5: HELPER VIEWS
-- ============================================================================

-- View for content type availability by creator
DROP VIEW IF EXISTS v_content_type_availability;

CREATE VIEW IF NOT EXISTS v_content_type_availability AS
SELECT
    content_type,
    COUNT(*) AS total_available,
    COUNT(CASE WHEN is_universal = 1 THEN 1 END) AS universal_count,
    COUNT(CASE WHEN creator_id IS NOT NULL THEN 1 END) AS creator_specific_count,
    AVG(freshness_score) AS avg_freshness,
    AVG(performance_score) AS avg_performance
FROM all_schedulable_content
GROUP BY content_type
ORDER BY total_available DESC;

-- View for schedulable content by page type
DROP VIEW IF EXISTS v_content_by_page_type;

CREATE VIEW IF NOT EXISTS v_content_by_page_type AS
SELECT
    page_type_filter,
    content_type,
    COUNT(*) AS count,
    AVG(freshness_score) AS avg_freshness,
    AVG(performance_score) AS avg_performance
FROM all_schedulable_content
GROUP BY page_type_filter, content_type
ORDER BY page_type_filter, count DESC;

-- ============================================================================
-- SECTION 6: TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Trigger to update updated_at timestamp on vip_post_templates
CREATE TRIGGER IF NOT EXISTS trg_vip_post_updated_at
AFTER UPDATE ON vip_post_templates
FOR EACH ROW
BEGIN
    UPDATE vip_post_templates
    SET updated_at = datetime('now')
    WHERE template_id = NEW.template_id;
END;

-- Trigger to update updated_at timestamp on tip_incentive_templates
CREATE TRIGGER IF NOT EXISTS trg_tip_incentive_updated_at
AFTER UPDATE ON tip_incentive_templates
FOR EACH ROW
BEGIN
    UPDATE tip_incentive_templates
    SET updated_at = datetime('now')
    WHERE template_id = NEW.template_id;
END;

-- Trigger to update updated_at timestamp on link_drop_templates
CREATE TRIGGER IF NOT EXISTS trg_link_drop_updated_at
AFTER UPDATE ON link_drop_templates
FOR EACH ROW
BEGIN
    UPDATE link_drop_templates
    SET updated_at = datetime('now')
    WHERE template_id = NEW.template_id;
END;

-- Trigger to update updated_at timestamp on engagement_templates
CREATE TRIGGER IF NOT EXISTS trg_engagement_updated_at
AFTER UPDATE ON engagement_templates
FOR EACH ROW
BEGIN
    UPDATE engagement_templates
    SET updated_at = datetime('now')
    WHERE template_id = NEW.template_id;
END;

-- Trigger to update updated_at timestamp on retention_templates
CREATE TRIGGER IF NOT EXISTS trg_retention_updated_at
AFTER UPDATE ON retention_templates
FOR EACH ROW
BEGIN
    UPDATE retention_templates
    SET updated_at = datetime('now')
    WHERE template_id = NEW.template_id;
END;

-- Trigger to update updated_at timestamp on bump_variants
CREATE TRIGGER IF NOT EXISTS trg_bump_variant_updated_at
AFTER UPDATE ON bump_variants
FOR EACH ROW
BEGIN
    UPDATE bump_variants
    SET updated_at = datetime('now')
    WHERE variant_id = NEW.variant_id;
END;

-- ============================================================================
-- SECTION 7: SCHEMA VERSION TRACKING
-- ============================================================================

-- Record this migration
INSERT OR REPLACE INTO schema_migrations (version, description, applied_at)
VALUES (
    '3.0',
    'Added 20+ content type support: schedulable_type column, page_type_filter columns, and new template tables (vip_post, tip_incentive, link_drop, engagement, retention, bump_variants) with unified content view',
    datetime('now')
);

-- ============================================================================
-- SECTION 8: VALIDATION QUERIES (Run manually to verify migration)
-- ============================================================================

/*
-- Verify new column exists on caption_bank
PRAGMA table_info(caption_bank);

-- Verify new tables were created
SELECT name FROM sqlite_master WHERE type='table' AND name IN (
    'vip_post_templates',
    'tip_incentive_templates',
    'link_drop_templates',
    'engagement_templates',
    'retention_templates',
    'bump_variants'
);

-- Verify unified view works
SELECT content_type, COUNT(*) as count
FROM all_schedulable_content
GROUP BY content_type;

-- Verify content type availability view
SELECT * FROM v_content_type_availability;

-- Check schema version
SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;
*/

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
