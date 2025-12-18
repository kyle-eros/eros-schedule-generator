-- ============================================================================
-- Migration 008: Send Types, Channels, and Audience Targets Seed Data
-- ============================================================================
-- Purpose: Populate reference tables for the EROS Schedule Generator system
-- Created: 2025-12-15
-- Updated: 2025-12-15 (Schema alignment with 008_send_types_foundation.sql)
--
-- This migration seeds:
--   1. send_types (21 types across 3 categories: revenue, engagement, retention)
--   2. channels (5 distribution channels)
--   3. audience_targets (10 audience segments)
--
-- IMPORTANT: This file contains ONLY seed data (INSERT statements).
--            Table creation is handled by 008_send_types_foundation.sql
--
-- IDEMPOTENT: Uses INSERT OR IGNORE to prevent duplicate inserts.
-- SAFE: Read-only reference data, no schema changes.
--
-- Schema Reference (from 008_send_types_foundation.sql):
--   send_types: send_type_key, category, display_name, emoji_recommendation
--   channels: channel_key, display_name
--   audience_targets: target_key, display_name, typical_reach_percentage
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
-- SECTION 2: SEED DATA - SEND TYPES (21 types)
-- ============================================================================
-- Column mapping from foundation schema:
--   send_type_key TEXT UNIQUE NOT NULL
--   category TEXT NOT NULL CHECK (category IN ('revenue', 'engagement', 'retention'))
--   display_name TEXT NOT NULL
--   description TEXT
--   purpose TEXT
--   strategy TEXT
--   requires_media INTEGER DEFAULT 1
--   requires_flyer INTEGER DEFAULT 0
--   requires_price INTEGER DEFAULT 0
--   requires_link INTEGER DEFAULT 0
--   has_expiration INTEGER DEFAULT 0
--   default_expiration_hours INTEGER
--   can_have_followup INTEGER DEFAULT 0
--   followup_delay_minutes INTEGER DEFAULT 20
--   page_type_restriction TEXT DEFAULT 'both'
--   caption_length TEXT
--   emoji_recommendation TEXT
--   max_per_day INTEGER
--   max_per_week INTEGER
--   min_hours_between INTEGER DEFAULT 2
--   sort_order INTEGER DEFAULT 100
--   is_active INTEGER DEFAULT 1

-- ---------------------------------------------------------------------------
-- REVENUE CATEGORY (7 types)
-- ---------------------------------------------------------------------------

-- 1. ppv_video: Standard PPV video sale
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'ppv_video', 'revenue', 'PPV Video',
    'Standard PPV video sale. Primary revenue driver with long-form caption and heavy emoji usage.',
    'Direct monetization through premium video content',
    'Use compelling preview, build anticipation, include clear value proposition',
    1, 1, 1, 0,
    0, NULL, 1, 20,
    'both', 'long', 'heavy',
    4, NULL, 2, 10
);

-- 2. vip_program: VIP tier promotion
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'vip_program', 'revenue', 'VIP Program',
    'VIP tier promotion with $200 tip goal. One-time strategic post with medium caption.',
    'Convert high-value fans into VIP tier subscribers',
    'Emphasize exclusivity and special access, create FOMO',
    1, 1, 0, 0,
    0, NULL, 0, NULL,
    'both', 'medium', 'moderate',
    1, 1, 24, 20
);

-- 3. game_post: Spin-the-wheel, contests
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'game_post', 'revenue', 'Game Post',
    'Spin-the-wheel, contests, and interactive games. GIF required for engagement.',
    'Gamified engagement that drives tips and interaction',
    'Create excitement, clear rules, attractive prizes',
    1, 0, 1, 0,
    1, 24, 0, NULL,
    'both', 'medium', 'heavy',
    1, NULL, 4, 30
);

-- 4. bundle: Content bundle at set price
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'bundle', 'revenue', 'Content Bundle',
    'Content bundle at set price. Medium caption with deal-focused messaging.',
    'Increase average order value through bundled content',
    'Emphasize value and savings, list bundle contents clearly',
    1, 1, 1, 0,
    0, NULL, 0, NULL,
    'both', 'medium', 'moderate',
    2, NULL, 3, 40
);

-- 5. flash_bundle: Limited-quantity urgency bundle
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'flash_bundle', 'revenue', 'Flash Bundle',
    'Limited-quantity urgency bundle with 24-hour expiration. Creates FOMO with scarcity messaging.',
    'Drive immediate action through artificial scarcity',
    'Strong urgency language, countdown emphasis, limited availability',
    1, 1, 1, 0,
    1, 24, 0, NULL,
    'both', 'medium', 'heavy',
    1, NULL, 6, 50
);

-- 6. snapchat_bundle: Throwback Snapchat content
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'snapchat_bundle', 'revenue', 'Snapchat Bundle',
    'Throwback Snapchat content bundle. High conversion rate due to nostalgia factor.',
    'Monetize archive content through nostalgia marketing',
    'Emphasize rarity and throwback nature, exclusive access angle',
    1, 1, 1, 0,
    0, NULL, 0, NULL,
    'both', 'medium', 'moderate',
    1, 1, 24, 60
);

-- 7. first_to_tip: Gamified tip race
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'first_to_tip', 'revenue', 'First to Tip',
    'Gamified tip race with competitive element. Has 24-hour expiration and tip goal target.',
    'Create competitive engagement that drives quick tips',
    'Build excitement, clear reward for winner, time pressure',
    1, 1, 0, 0,
    1, 24, 0, NULL,
    'both', 'medium', 'heavy',
    1, NULL, 6, 70
);

-- ---------------------------------------------------------------------------
-- ENGAGEMENT CATEGORY (9 types)
-- ---------------------------------------------------------------------------

-- 8. link_drop: Repost previous campaign link
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'link_drop', 'engagement', 'Link Drop',
    'Repost previous campaign link. Short caption with no media needed (auto-preview from link).',
    'Remind fans of existing content and drive additional conversions',
    'Brief reminder message, link speaks for itself',
    0, 0, 0, 1,
    1, 24, 0, NULL,
    'both', 'short', 'light',
    3, NULL, 2, 110
);

-- 9. wall_link_drop: Wall post campaign promotion
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'wall_link_drop', 'engagement', 'Wall Link Drop',
    'Wall post campaign promotion. Unlike link_drop, requires manual GIF or picture attachment.',
    'Wall visibility for campaign promotion',
    'Eye-catching media with clear call to action',
    1, 0, 0, 1,
    0, NULL, 0, NULL,
    'both', 'short', 'light',
    2, NULL, 3, 120
);

-- 10. bump_normal: Short flirty bump with media
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'bump_normal', 'engagement', 'Normal Bump',
    'Short flirty bump with media. Quick engagement touchpoint with light emoji usage.',
    'Maintain presence and engagement between revenue sends',
    'Casual, flirty, personality-forward content',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'short', 'light',
    5, NULL, 1, 130
);

-- 11. bump_descriptive: Story-driven bump (longer)
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'bump_descriptive', 'engagement', 'Descriptive Bump',
    'Story-driven bump with longer caption. Creates deeper connection through narrative.',
    'Build emotional connection through storytelling',
    'Personal stories, behind-the-scenes, authentic moments',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'long', 'moderate',
    3, NULL, 2, 140
);

-- 12. bump_text_only: No media at all, just text
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'bump_text_only', 'engagement', 'Text-Only Bump',
    'Pure text bump with no media attachment. Feels more personal and conversational.',
    'Create intimate, personal connection without media distraction',
    'Conversational tone, questions, personal updates',
    0, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'short', 'light',
    4, NULL, 2, 150
);

-- 13. bump_flyer: Designed flyer/GIF bump
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'bump_flyer', 'engagement', 'Flyer Bump',
    'Designed flyer or GIF bump with long caption. Higher production value for special announcements.',
    'High-impact engagement with professional visuals',
    'Eye-catching flyer, announcement-style messaging',
    1, 1, 0, 0,
    0, NULL, 0, NULL,
    'both', 'long', 'moderate',
    2, NULL, 4, 160
);

-- 14. dm_farm: "DM me" engagement driver
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'dm_farm', 'engagement', 'DM Farm',
    'Direct message engagement driver. Encourages fans to initiate conversation.',
    'Generate 1:1 conversations that lead to custom content sales',
    'Open-ended questions, invitation to chat, approachable tone',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'short', 'heavy',
    2, NULL, 4, 170
);

-- 15. like_farm: "Like all posts" engagement
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'like_farm', 'engagement', 'Like Farm',
    'Encourages fans to like all posts for engagement boost. Light emoji for casual tone.',
    'Boost algorithmic visibility through engagement metrics',
    'Friendly request, reciprocity offer, simple ask',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'short', 'light',
    1, NULL, 24, 180
);

-- 16. live_promo: Livestream announcement
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'live_promo', 'engagement', 'Live Promo',
    'Livestream announcement and promotion. Requires flyer with event details.',
    'Drive attendance to live streams for tips and engagement',
    'Clear time/date, excitement building, what to expect',
    1, 1, 0, 0,
    0, NULL, 0, NULL,
    'both', 'medium', 'heavy',
    2, NULL, 2, 190
);

-- ---------------------------------------------------------------------------
-- RETENTION CATEGORY (5 types)
-- ---------------------------------------------------------------------------

-- 17. renew_on_post: Auto-renew promotion (wall)
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'renew_on_post', 'retention', 'Renew On Post',
    'Auto-renewal promotion posted to wall. Paid pages only.',
    'Encourage fans to enable auto-renewal for subscription retention',
    'Benefits of staying subscribed, upcoming content teasers',
    1, 0, 0, 1,
    0, NULL, 0, NULL,
    'paid', 'medium', 'moderate',
    2, NULL, 12, 210
);

-- 18. renew_on_message: Auto-renew targeted message
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'renew_on_message', 'retention', 'Renew On Message',
    'Targeted auto-renewal message sent directly to fans with renewal disabled. Paid pages only.',
    'Personal outreach to at-risk subscribers',
    'Personal touch, value reminder, easy action steps',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'paid', 'medium', 'moderate',
    1, NULL, 24, 220
);

-- 19. ppv_message: Mass message PPV unlock
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'ppv_message', 'retention', 'PPV Message',
    'Mass message with PPV unlock content. Adjustable pricing based on content value.',
    'Retain engagement through premium content in messages',
    'Teaser description, clear pricing, value proposition',
    1, 0, 1, 0,
    0, NULL, 1, 20,
    'both', 'medium', 'moderate',
    3, NULL, 2, 230
);

-- 20. ppv_followup: PPV close-the-sale followup
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'ppv_followup', 'retention', 'PPV Followup',
    'Close-the-sale followup sent 15-30 minutes after PPV. Targets fans who viewed but did not purchase.',
    'Convert PPV views into purchases through follow-up',
    'Soft reminder, additional teaser, limited time framing',
    0, 0, 0, 0,
    0, NULL, 0, NULL,
    'both', 'short', 'moderate',
    4, NULL, 1, 240
);

-- 21. expired_winback: Former subscriber outreach
INSERT OR IGNORE INTO send_types (
    send_type_key, category, display_name, description,
    purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link,
    has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
    page_type_restriction, caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order
) VALUES (
    'expired_winback', 'retention', 'Expired Winback',
    'Former subscriber outreach campaign. Paid pages only. Sent daily to expired fans.',
    'Re-engage lapsed subscribers and drive re-subscription',
    'Miss you messaging, what they are missing, special offer',
    1, 0, 0, 0,
    0, NULL, 0, NULL,
    'paid', 'medium', 'moderate',
    1, NULL, 24, 250
);

-- ============================================================================
-- SECTION 3: SEED DATA - CHANNELS (5 channels)
-- ============================================================================
-- Column mapping from foundation schema:
--   channel_key TEXT UNIQUE NOT NULL
--   display_name TEXT NOT NULL
--   description TEXT
--   supports_targeting INTEGER DEFAULT 0
--   targeting_options TEXT (JSON array)
--   platform_feature TEXT
--   requires_manual_send INTEGER DEFAULT 0
--   is_active INTEGER DEFAULT 1

-- 1. wall_post: Wall Post
INSERT OR IGNORE INTO channels (
    channel_key, display_name, description,
    supports_targeting, targeting_options, platform_feature,
    requires_manual_send, is_active
) VALUES (
    'wall_post', 'Wall Post',
    'Post visible to all subscribers on the creator wall. No targeting capability. Primary content distribution method.',
    0, NULL, 'post',
    0, 1
);

-- 2. mass_message: Mass Message
INSERT OR IGNORE INTO channels (
    channel_key, display_name, description,
    supports_targeting, targeting_options, platform_feature,
    requires_manual_send, is_active
) VALUES (
    'mass_message', 'Mass Message',
    'Message sent to subscriber inbox. Supports targeting by all subscribers or specific segments. Primary revenue channel.',
    1, '["all", "segment"]', 'mass_message',
    0, 1
);

-- 3. targeted_message: Targeted Message
INSERT OR IGNORE INTO channels (
    channel_key, display_name, description,
    supports_targeting, targeting_options, platform_feature,
    requires_manual_send, is_active
) VALUES (
    'targeted_message', 'Targeted Message',
    'Message sent to specific audience segments or custom lists. Advanced targeting for retention and personalization.',
    1, '["segment", "custom"]', 'targeted_message',
    0, 1
);

-- 4. story: Story
INSERT OR IGNORE INTO channels (
    channel_key, display_name, description,
    supports_targeting, targeting_options, platform_feature,
    requires_manual_send, is_active
) VALUES (
    'story', 'Story',
    'Temporary 24-hour content visible to all subscribers. No targeting capability. Good for time-sensitive announcements.',
    0, NULL, 'story',
    0, 1
);

-- 5. live: Live
INSERT OR IGNORE INTO channels (
    channel_key, display_name, description,
    supports_targeting, targeting_options, platform_feature,
    requires_manual_send, is_active
) VALUES (
    'live', 'Live',
    'Livestream session. No targeting - available to all subscribers. Requires manual execution, cannot be auto-scheduled.',
    0, NULL, 'live',
    1, 1
);

-- ============================================================================
-- SECTION 4: SEED DATA - AUDIENCE TARGETS (10 targets)
-- ============================================================================
-- Column mapping from foundation schema:
--   target_key TEXT UNIQUE NOT NULL
--   display_name TEXT NOT NULL
--   description TEXT
--   filter_type TEXT ('segment', 'behavior', 'custom')
--   filter_criteria TEXT (JSON)
--   applicable_page_types TEXT DEFAULT '["paid","free"]' (JSON array)
--   applicable_channels TEXT (JSON array)
--   typical_reach_percentage REAL
--   is_active INTEGER DEFAULT 1

-- 1. all_active: All Active Fans
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'all_active', 'All Active Fans',
    'All current active subscribers. Maximum reach for broad announcements and campaigns.',
    'segment', '{"status": "active"}',
    '["paid", "free"]', '["mass_message", "wall_post", "story"]',
    100.0, 1
);

-- 2. renew_off: Renew Off
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'renew_off', 'Renew Off',
    'Fans with auto-renewal disabled. At risk of churning. Priority target for retention campaigns.',
    'segment', '{"auto_renew": false, "status": "active"}',
    '["paid"]', '["targeted_message", "mass_message"]',
    40.0, 1
);

-- 3. renew_on: Renew On
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'renew_on', 'Renew On',
    'Fans with auto-renewal enabled. Loyal segment with higher lifetime value. Good for premium offers.',
    'segment', '{"auto_renew": true, "status": "active"}',
    '["paid"]', '["targeted_message", "mass_message"]',
    60.0, 1
);

-- 4. expired_recent: Recently Expired
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'expired_recent', 'Recently Expired',
    'Fans whose subscription expired within the last 30 days. Warm leads for winback campaigns.',
    'behavior', '{"status": "expired", "days_since_expiry": {"max": 30}}',
    '["paid"]', '["targeted_message"]',
    NULL, 1
);

-- 5. expired_all: All Expired
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'expired_all', 'All Expired',
    'All former subscribers regardless of expiration date. Larger pool for winback but lower conversion rate.',
    'behavior', '{"status": "expired"}',
    '["paid"]', '["targeted_message"]',
    NULL, 1
);

-- 6. never_purchased: Never Purchased
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'never_purchased', 'Never Purchased',
    'Fans who have never purchased any PPV content. Opportunity for first conversion with entry-level pricing.',
    'behavior', '{"ppv_purchases": 0, "status": "active"}',
    '["paid", "free"]', '["targeted_message", "mass_message"]',
    70.0, 1
);

-- 7. recent_purchasers: Recent Purchasers
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'recent_purchasers', 'Recent Purchasers',
    'Fans who purchased PPV content in the last 7 days. Warm buyers likely to purchase again.',
    'behavior', '{"last_purchase_days": {"max": 7}, "status": "active"}',
    '["paid", "free"]', '["targeted_message", "mass_message"]',
    20.0, 1
);

-- 8. high_spenders: High Spenders
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'high_spenders', 'High Spenders',
    'Top 10% of fans by total spend. VIP segment for premium offers and exclusive content.',
    'behavior', '{"spend_percentile": {"min": 90}, "status": "active"}',
    '["paid", "free"]', '["targeted_message", "mass_message"]',
    10.0, 1
);

-- 9. inactive_7d: Inactive 7 Days
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'inactive_7d', 'Inactive 7 Days',
    'Fans with no engagement in the past 7 days. Re-engagement target before they churn.',
    'behavior', '{"last_activity_days": {"min": 7}, "status": "active"}',
    '["paid", "free"]', '["targeted_message", "mass_message"]',
    30.0, 1
);

-- 10. ppv_non_purchasers: PPV Non-Purchasers
INSERT OR IGNORE INTO audience_targets (
    target_key, display_name, description,
    filter_type, filter_criteria,
    applicable_page_types, applicable_channels,
    typical_reach_percentage, is_active
) VALUES (
    'ppv_non_purchasers', 'PPV Non-Purchasers',
    'Fans who did not purchase the most recent PPV offer. Primary target for followup campaigns.',
    'custom', '{"viewed_last_ppv": true, "purchased_last_ppv": false}',
    '["paid", "free"]', '["targeted_message"]',
    NULL, 1
);

-- ============================================================================
-- SECTION 5: Migration metadata record
-- ============================================================================

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '008_seed_data',
    datetime('now'),
    'Seed data for send_types (21 types), channels (5), and audience_targets (10) reference tables'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to verify successful application:
--
-- 1. Check send_types count by category:
--    SELECT category, COUNT(*) as count FROM send_types GROUP BY category;
--    Expected: revenue=7, engagement=9, retention=5
--
-- 2. Check channels count:
--    SELECT COUNT(*) FROM channels;
--    Expected: 5
--
-- 3. Check audience_targets count:
--    SELECT COUNT(*) FROM audience_targets;
--    Expected: 10
--
-- 4. Verify all send types with correct column names:
--    SELECT send_type_key, category, display_name, emoji_recommendation, max_per_day
--    FROM send_types ORDER BY sort_order;
--
-- 5. Check migration recorded:
--    SELECT * FROM schema_migrations WHERE version = '008_seed_data';
--
-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
-- To rollback this migration (removes seed data only, preserves tables):
--
-- DELETE FROM send_types WHERE send_type_key IN (
--     'ppv_video', 'vip_program', 'game_post', 'bundle', 'flash_bundle',
--     'snapchat_bundle', 'first_to_tip', 'link_drop', 'wall_link_drop',
--     'bump_normal', 'bump_descriptive', 'bump_text_only', 'bump_flyer',
--     'dm_farm', 'like_farm', 'live_promo', 'renew_on_post', 'renew_on_message',
--     'ppv_message', 'ppv_followup', 'expired_winback'
-- );
--
-- DELETE FROM channels WHERE channel_key IN (
--     'wall_post', 'mass_message', 'targeted_message', 'story', 'live'
-- );
--
-- DELETE FROM audience_targets WHERE target_key IN (
--     'all_active', 'renew_off', 'renew_on', 'expired_recent', 'expired_all',
--     'never_purchased', 'recent_purchasers', 'high_spenders', 'inactive_7d',
--     'ppv_non_purchasers'
-- );
--
-- DELETE FROM schema_migrations WHERE version = '008_seed_data';
--
-- ============================================================================
-- END OF MIGRATION 008 SEED DATA
-- ============================================================================
