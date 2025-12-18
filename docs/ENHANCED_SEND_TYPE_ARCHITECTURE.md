# Enhanced Send Type Architecture

> Technical architecture documentation for the comprehensive 21-type send system that replaces the simplified ppv/bump model.

**Version:** 2.2.0 | **Updated:** 2025-12-16

## Table of Contents

1. [Overview](#overview)
2. [Send Type Taxonomy](#1-send-type-taxonomy)
3. [Enhanced Database Schema](#2-enhanced-database-schema)
4. [Seed Data](#3-seed-data)
5. [Send Type to Caption Type Mapping](#4-send-type-to-caption-type-mapping)
6. [Enhanced Pipeline Workflow](#5-enhanced-pipeline-workflow)
7. [Updated MCP Server Tools](#6-updated-mcp-server-tools)
8. [Volume Assignment Enhancement](#7-volume-assignment-enhancement)
9. [Output Format Enhancement](#8-output-format-enhancement)
10. [Migration Plan](#9-migration-plan)
11. [Summary](#10-summary)

---

## Overview

This document defines a comprehensive send type system that supports all 21 distinct content scheduling types used in OnlyFans page management, replacing the simplified `ppv`/`bump` model with a full-featured taxonomy.

---

## 1. Send Type Taxonomy

### Category Structure

```
SEND_TYPES
├── REVENUE (7 types)
│   ├── ppv_video          # Standard PPV video sale
│   ├── vip_program        # VIP tier promotion ($200 tip)
│   ├── game_post          # Spin-the-wheel, contests
│   ├── bundle             # Content bundle at set price
│   ├── flash_bundle       # Limited-quantity urgency bundle
│   ├── snapchat_bundle    # Throwback Snapchat content
│   └── first_to_tip       # Gamified tip race
│
├── ENGAGEMENT (9 types)
│   ├── link_drop          # Repost previous campaign link
│   ├── wall_link_drop     # Wall post campaign promotion
│   ├── bump_normal        # Short flirty bump with media
│   ├── bump_descriptive   # Story-driven bump (longer)
│   ├── bump_text_only     # No media, just text
│   ├── bump_flyer         # Designed flyer/GIF bump
│   ├── dm_farm            # "DM me" engagement driver
│   ├── like_farm          # "Like all posts" engagement
│   └── live_promo         # Livestream announcement
│
└── RETENTION (5 types)
    ├── renew_on_post      # Auto-renew promotion (wall)
    ├── renew_on_message   # Auto-renew targeted message
    ├── ppv_message        # Mass message PPV unlock
    ├── ppv_followup       # PPV close-the-sale followup
    └── expired_winback    # Former subscriber outreach
```

### Send Type Reference Table

| send_type_key | Category | Display Name | Requires Media | Requires Flyer | Has Price | Expires | Page Type |
|---------------|----------|--------------|----------------|----------------|-----------|---------|-----------|
| `ppv_video` | revenue | PPV Video | YES | Paid: YES | YES | NO | both |
| `vip_program` | revenue | VIP Post | YES | YES | NO (tip) | NO | both |
| `game_post` | revenue | Game Post | YES (GIF) | YES | YES | YES | both |
| `bundle` | revenue | Bundle Post | YES | YES | YES | NO | both |
| `flash_bundle` | revenue | Flash Bundle | YES | YES | YES | YES | both |
| `snapchat_bundle` | revenue | Snapchat Bundle | YES | YES | YES | NO | both |
| `first_to_tip` | revenue | First To Tip | YES | YES | NO (tip) | YES (24h) | both |
| `link_drop` | engagement | Link Drop | NO (auto) | NO | NO | YES (24h) | both |
| `wall_link_drop` | engagement | Wall Link Drop | YES | YES | NO | YES | both |
| `bump_normal` | engagement | Normal Bump | YES | NO | NO | NO | both |
| `bump_descriptive` | engagement | Descriptive Bump | YES | NO | NO | NO | both |
| `bump_text_only` | engagement | Text Only Bump | NO | NO | NO | NO | both |
| `bump_flyer` | engagement | Flyer/GIF Bump | YES | YES | NO | NO | both |
| `dm_farm` | engagement | DM Farm | YES | Optional | NO | NO | both |
| `like_farm` | engagement | Like Farm | YES | Optional | NO | NO | both |
| `live_promo` | engagement | Live Promo | YES | YES | NO | YES | both |
| `renew_on_post` | retention | Renew On Post | YES | Optional | NO | NO | paid |
| `renew_on_message` | retention | Renew On Message | YES | Optional | NO | NO | paid |
| `ppv_message` | retention | PPV Message | YES | Optional | YES | NO | both |
| `ppv_followup` | retention | PPV Follow Up | Optional | NO | NO | NO | both |
| `expired_winback` | retention | Expired Sub Msg | YES | YES | NO | NO | paid |

---

## 2. Enhanced Database Schema

### New Table: `send_types`

```sql
CREATE TABLE send_types (
    send_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_key TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('revenue', 'engagement', 'retention')),
    display_name TEXT NOT NULL,
    description TEXT,
    purpose TEXT,
    strategy TEXT,

    -- Requirements
    requires_media INTEGER DEFAULT 1,
    requires_flyer INTEGER DEFAULT 0,
    requires_price INTEGER DEFAULT 0,
    requires_link INTEGER DEFAULT 0,

    -- Behavior
    has_expiration INTEGER DEFAULT 0,
    default_expiration_hours INTEGER,
    can_have_followup INTEGER DEFAULT 0,
    followup_delay_minutes INTEGER,

    -- Page restrictions
    page_type_restriction TEXT CHECK (page_type_restriction IN ('paid', 'free', 'both')) DEFAULT 'both',

    -- Caption requirements
    caption_length TEXT CHECK (caption_length IN ('short', 'medium', 'long')) DEFAULT 'medium',
    emoji_recommendation TEXT CHECK (emoji_recommendation IN ('none', 'light', 'moderate', 'heavy')) DEFAULT 'moderate',

    -- Scheduling constraints
    max_per_day INTEGER DEFAULT 10,
    max_per_week INTEGER DEFAULT 50,
    min_hours_between INTEGER DEFAULT 2,

    -- Metadata
    sort_order INTEGER DEFAULT 50,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### New Table: `channels`

```sql
CREATE TABLE channels (
    channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_key TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,

    -- Targeting capabilities
    supports_targeting INTEGER DEFAULT 0,
    targeting_options TEXT, -- JSON array of available targets

    -- Technical
    platform_feature TEXT, -- OF feature name
    requires_manual_send INTEGER DEFAULT 0,

    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### New Table: `audience_targets`

```sql
CREATE TABLE audience_targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_key TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,

    -- Filtering criteria
    filter_type TEXT NOT NULL, -- 'subscription_status', 'engagement', 'purchase_history', 'renewal_status'
    filter_criteria TEXT, -- JSON filter definition

    -- Applicability
    applicable_page_types TEXT DEFAULT 'both', -- 'paid', 'free', 'both'
    applicable_channels TEXT, -- JSON array of channel_keys

    -- Estimated reach (cached)
    typical_reach_percentage REAL,

    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Enhanced: `schedule_items` (Migration)

```sql
-- Add new columns to schedule_items
ALTER TABLE schedule_items ADD COLUMN send_type_id INTEGER REFERENCES send_types(send_type_id);
ALTER TABLE schedule_items ADD COLUMN channel_id INTEGER REFERENCES channels(channel_id);
ALTER TABLE schedule_items ADD COLUMN target_id INTEGER REFERENCES audience_targets(target_id);
ALTER TABLE schedule_items ADD COLUMN linked_post_url TEXT;
ALTER TABLE schedule_items ADD COLUMN expires_at TEXT;
ALTER TABLE schedule_items ADD COLUMN parent_send_id INTEGER REFERENCES schedule_items(item_id);
ALTER TABLE schedule_items ADD COLUMN is_followup INTEGER DEFAULT 0;
ALTER TABLE schedule_items ADD COLUMN followup_delay_minutes INTEGER;
ALTER TABLE schedule_items ADD COLUMN media_type TEXT CHECK (media_type IN ('none', 'picture', 'gif', 'video', 'flyer'));
ALTER TABLE schedule_items ADD COLUMN campaign_goal REAL;

-- Update item_type to use send_type_key (backward compatible)
-- item_type remains for legacy, send_type_id is authoritative
```

### New Table: `send_type_caption_requirements`

```sql
CREATE TABLE send_type_caption_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_id INTEGER NOT NULL REFERENCES send_types(send_type_id),
    caption_type TEXT NOT NULL, -- Links to caption_bank.caption_type
    priority INTEGER DEFAULT 5, -- 1=primary, 5=secondary, 10=avoid
    notes TEXT,
    UNIQUE(send_type_id, caption_type)
);
```

### New Table: `send_type_content_compatibility`

```sql
CREATE TABLE send_type_content_compatibility (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_id INTEGER NOT NULL REFERENCES send_types(send_type_id),
    content_type_id INTEGER NOT NULL REFERENCES content_types(content_type_id),
    compatibility TEXT CHECK (compatibility IN ('required', 'recommended', 'allowed', 'discouraged', 'forbidden')) DEFAULT 'allowed',
    notes TEXT,
    UNIQUE(send_type_id, content_type_id)
);
```

---

## 3. Seed Data

### Send Types Seed

```sql
INSERT INTO send_types (send_type_key, category, display_name, purpose, strategy, requires_media, requires_flyer, requires_price, has_expiration, default_expiration_hours, can_have_followup, caption_length, emoji_recommendation, max_per_day, page_type_restriction, sort_order) VALUES

-- REVENUE TYPES (1-7)
('ppv_video', 'revenue', 'PPV Video',
 'Selling a specific video',
 'Paid pages: Must be campaigns with GIF/picture flyer. Free pages: Can be post unlocks. Long, descriptive, sexy caption with emojis.',
 1, 1, 1, 0, NULL, 1, 'long', 'heavy', 5, 'both', 1),

('vip_program', 'revenue', 'VIP Post',
 'Promotes the VIP Program ($200 tip) for exclusive content access',
 'Post once with a flyer; never repost. Set as campaign starting at $1,000 goal, expanding in $1,000 increments up to $10,000.',
 1, 1, 0, 0, NULL, 0, 'medium', 'moderate', 1, 'both', 2),

('game_post', 'revenue', 'Game Post',
 'A buying opportunity presented as a game (e.g., Spin the Wheel) with chance to win prizes',
 'Campaign style with set price to play. Almost always uses a GIF.',
 1, 1, 1, 1, 24, 0, 'medium', 'heavy', 2, 'both', 3),

('bundle', 'revenue', 'Bundle Post',
 'Offering a content bundle at a set price',
 'Advertise the deal value. Keep it sexy and eye-catching, not overly salesy. Use a GIF or picture flyer.',
 1, 1, 1, 0, NULL, 1, 'medium', 'moderate', 3, 'both', 4),

('flash_bundle', 'revenue', 'Flash Bundle',
 'A limited-quantity bundle to create urgency',
 'Campaign style with generic graphic or model GIF/picture.',
 1, 1, 1, 1, 24, 0, 'medium', 'heavy', 2, 'both', 5),

('snapchat_bundle', 'revenue', 'Snapchat Bundle',
 'Bundle advertised as old Snapchat nudes (e.g., from age 18-19)',
 'High conversion rate. Use a throwback picture with the Snapchat text bar as the flyer.',
 1, 1, 1, 0, NULL, 0, 'medium', 'moderate', 1, 'both', 6),

('first_to_tip', 'revenue', 'First To Tip',
 'A gamified post where the goal matches the exact tip amount',
 'Visually enticing caption and flyer. Set to expire after 24 hours (or longer for higher goals).',
 1, 1, 0, 1, 24, 0, 'short', 'heavy', 2, 'both', 7),

-- ENGAGEMENT TYPES (8-16)
('link_drop', 'engagement', 'Link Drop',
 'Pushes a previous post back to fans feeds (similar to a retweet)',
 'Short caption promoting a campaign or buying opportunity with the link to that post. Always expire after 24 hours. Post preview generates automatically if done correctly.',
 0, 0, 0, 1, 24, 0, 'short', 'light', 5, 'both', 10),

('wall_link_drop', 'engagement', 'Wall Post Link Drop',
 'Promote a specific wall campaign',
 'Caption + Link. Must manually add a GIF/picture from the same scene (no auto-preview). Great for pushing wall tips.',
 1, 1, 0, 1, 24, 0, 'short', 'light', 3, 'both', 11),

('bump_normal', 'engagement', 'Normal Bump',
 'Entice fans to DM you',
 'Cute/flirty picture. Caption should sound like a horny girl but keep it short.',
 1, 0, 0, 0, NULL, 0, 'short', 'moderate', 6, 'both', 12),

('bump_descriptive', 'engagement', 'Descriptive Bump',
 'Similar to normal bumps, but drives DMs through storytelling',
 'Uses a longer, sexually descriptive caption.',
 1, 0, 0, 0, NULL, 0, 'long', 'moderate', 4, 'both', 13),

('bump_text_only', 'engagement', 'Text Only Bump',
 'Quick engagement without media',
 'Short, flirty, cute text. Example: wyd right now daddy',
 0, 0, 0, 0, NULL, 0, 'short', 'heavy', 8, 'both', 14),

('bump_flyer', 'engagement', 'Flyer/GIF Bump',
 'High-visibility bump',
 'Longer sexual caption paired with a designed flyer or GIF for maximum attention.',
 1, 1, 0, 0, NULL, 0, 'long', 'heavy', 4, 'both', 15),

('dm_farm', 'engagement', 'DM Farm Post',
 'Get fans to DM immediately (e.g., for a free surprise or because you are active now)',
 'GIF, picture, or flyer. Emoji incentives work best here.',
 1, 0, 0, 0, NULL, 0, 'short', 'heavy', 3, 'both', 16),

('like_farm', 'engagement', 'Like Farm Post',
 'Boosts engagement metrics',
 'Encourage fans to Like all posts in exchange for a free incentive.',
 1, 0, 0, 0, NULL, 0, 'short', 'moderate', 2, 'both', 17),

('live_promo', 'engagement', 'Live Promo Post',
 'Notify fans of an upcoming livestream',
 'Use a livestream flyer with the specific time and info in the caption.',
 1, 1, 0, 1, NULL, 0, 'medium', 'moderate', 2, 'both', 18),

-- RETENTION TYPES (17-21)
('renew_on_post', 'retention', 'Renew On Post',
 'Convince fans to turn on auto-renewal',
 'Enticing caption with the auto-renew link. Can use GIFs, pictures, or videos. Link format: https://onlyfans.com/USERNAME?enable_renew=1',
 1, 0, 0, 0, NULL, 0, 'medium', 'moderate', 2, 'paid', 20),

('renew_on_message', 'retention', 'Renew On Message',
 'Sent specifically to fans with auto-renewal off',
 'Offer a free prize/incentive to click the renewal link.',
 1, 0, 0, 0, NULL, 0, 'medium', 'heavy', 2, 'paid', 21),

('ppv_message', 'retention', 'PPV/Unlock Message',
 'Mass message to fans with a locked post',
 'Fully adjustable pricing. Can use a flyer, picture, GIF, or video.',
 1, 0, 1, 0, NULL, 1, 'long', 'heavy', 5, 'both', 22),

('ppv_followup', 'retention', 'PPV Follow Up',
 'Sent 10-30 minutes after a PPV message to close the sale',
 'Bump, convince, or entice. Examples: I cant believe I just sent this, or offering a free nude if they buy immediately.',
 0, 0, 0, 0, NULL, 0, 'short', 'moderate', 5, 'both', 23),

('expired_winback', 'retention', 'Expired Subscriber Message',
 'Win back former fans',
 'Run daily. Message must match current subscriber campaign/incentive. Always send with picture/GIF flyers.',
 1, 1, 0, 0, NULL, 0, 'medium', 'moderate', 1, 'paid', 24);
```

### Channels Seed

```sql
INSERT INTO channels (channel_key, display_name, description, supports_targeting, targeting_options, platform_feature) VALUES
('wall_post', 'Wall Post', 'Public post on creator wall/feed', 0, NULL, 'post'),
('mass_message', 'Mass Message', 'Message to all active subscribers', 1, '["all_fans", "recent_purchasers", "high_spenders", "inactive"]', 'mass_message'),
('targeted_message', 'Targeted Message', 'Message to specific audience segment', 1, '["renew_off", "expired", "never_purchased", "purchased_specific"]', 'mass_message'),
('story', 'Story', 'Temporary story post (24h)', 0, NULL, 'story'),
('live', 'Live Stream', 'Live broadcast', 0, NULL, 'live');
```

### Audience Targets Seed

```sql
INSERT INTO audience_targets (target_key, display_name, description, filter_type, filter_criteria, applicable_page_types) VALUES
('all_active', 'All Active Subscribers', 'All currently subscribed fans', 'subscription_status', '{"status": "active"}', 'both'),
('renew_off', 'Auto-Renew Off', 'Fans with auto-renewal disabled', 'renewal_status', '{"auto_renew": false, "status": "active"}', 'paid'),
('renew_on', 'Auto-Renew On', 'Fans with auto-renewal enabled', 'renewal_status', '{"auto_renew": true, "status": "active"}', 'paid'),
('expired_recent', 'Recently Expired', 'Expired within last 30 days', 'subscription_status', '{"status": "expired", "days_since": 30}', 'paid'),
('expired_all', 'All Expired', 'All former subscribers', 'subscription_status', '{"status": "expired"}', 'paid'),
('never_purchased', 'Never Purchased', 'Subscribers who never bought PPV', 'purchase_history', '{"total_purchases": 0}', 'both'),
('recent_purchasers', 'Recent Purchasers', 'Purchased in last 7 days', 'purchase_history', '{"purchased_within_days": 7}', 'both'),
('high_spenders', 'High Spenders', 'Top 20% by spend', 'purchase_history', '{"percentile": 80}', 'both'),
('inactive_7d', 'Inactive 7 Days', 'No activity in 7 days', 'engagement', '{"inactive_days": 7}', 'both'),
('ppv_non_purchasers', 'PPV Non-Purchasers', 'Received but did not buy specific PPV', 'purchase_history', '{"specific_ppv_purchased": false}', 'both');
```

---

## 4. Send Type to Caption Type Mapping

```sql
-- Map which caption_types work best for each send_type
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes) VALUES
-- PPV Video
(1, 'ppv_unlock', 1, 'Primary caption type for PPV'),
(1, 'descriptive_tease', 3, 'Alternative for variety'),

-- VIP Program
(2, 'tip_request', 1, 'VIP tip solicitation'),
(2, 'exclusive_offer', 2, 'Emphasize exclusivity'),

-- Game Post
(3, 'engagement_hook', 1, 'Game participation driver'),

-- Bundle
(4, 'ppv_unlock', 1, 'Bundle offer caption'),
(4, 'exclusive_offer', 2, 'Deal emphasis'),

-- Flash Bundle
(5, 'ppv_unlock', 1, 'Urgency-focused unlock'),
(5, 'exclusive_offer', 1, 'Limited time offer'),

-- Snapchat Bundle
(6, 'ppv_unlock', 1, 'Throwback content offer'),

-- First to Tip
(7, 'tip_request', 1, 'Competition driver'),
(7, 'engagement_hook', 2, 'Gamification'),

-- Link Drop
(8, 'engagement_hook', 1, 'Short promotional'),
(8, 'flirty_opener', 2, 'Attention grab'),

-- Wall Link Drop
(9, 'engagement_hook', 1, 'Wall promotion'),

-- Normal Bump
(10, 'flirty_opener', 1, 'Short flirty'),
(10, 'engagement_hook', 2, 'DM driver'),

-- Descriptive Bump
(11, 'descriptive_tease', 1, 'Story-driven'),
(11, 'sexting_response', 2, 'Narrative style'),

-- Text Only Bump
(12, 'flirty_opener', 1, 'Text only'),

-- Flyer/GIF Bump
(13, 'descriptive_tease', 1, 'Long-form with visual'),
(13, 'ppv_unlock', 2, 'Teaser style'),

-- DM Farm
(14, 'engagement_hook', 1, 'DM solicitation'),
(14, 'flirty_opener', 1, 'Active now style'),

-- Like Farm
(15, 'engagement_hook', 1, 'Like request'),

-- Live Promo
(16, 'engagement_hook', 1, 'Event announcement'),

-- Renew On Post
(17, 'renewal_pitch', 1, 'Auto-renew push'),

-- Renew On Message
(18, 'renewal_pitch', 1, 'Targeted renewal'),
(18, 'exclusive_offer', 2, 'Incentive offer'),

-- PPV Message
(19, 'ppv_unlock', 1, 'Mass message PPV'),
(19, 'descriptive_tease', 2, 'Teaser variant'),

-- PPV Follow Up
(20, 'ppv_followup', 1, 'Close the sale'),
(20, 'flirty_opener', 2, 'Soft follow up'),

-- Expired Winback
(21, 'renewal_pitch', 1, 'Win back messaging'),
(21, 'exclusive_offer', 1, 'Re-sub incentive');
```

---

## 5. Enhanced Pipeline Workflow

### Updated Schedule Generation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENHANCED SCHEDULE GENERATOR                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: CONTEXT GATHERING                                          │
│  ────────────────────────────                                        │
│  • Load creator profile (page_type, tier, persona)                   │
│  • Load volume assignment (items per day by category)                │
│  • Load send_types applicable to page_type                           │
│  • Load performance trends & saturation signals                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: SEND TYPE ALLOCATION                                       │
│  ─────────────────────────────                                       │
│  For each day in schedule:                                           │
│    REVENUE SLOTS:                                                    │
│      • 2-3 ppv_video (primary revenue)                               │
│      • 1 bundle OR flash_bundle OR game (variety)                    │
│      • 0-1 vip_program (if not recently posted)                      │
│                                                                      │
│    ENGAGEMENT SLOTS:                                                 │
│      • 2-4 bumps (mix of normal, descriptive, text_only)             │
│      • 1-2 link_drops (promote active campaigns)                     │
│      • 0-1 dm_farm OR like_farm (engagement boost)                   │
│                                                                      │
│    RETENTION SLOTS (if paid page):                                   │
│      • 1 renew_on_message (to renew_off segment)                     │
│      • 1 expired_winback (daily for paid pages)                      │
│      • PPV follow-ups auto-generated for each PPV                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: CONTENT MATCHING                                           │
│  ──────────────────────────                                          │
│  For each allocated slot:                                            │
│    1. Query send_type_caption_requirements for caption_types         │
│    2. Query caption_bank filtered by:                                │
│       - creator_id match                                             │
│       - caption_type in allowed types                                │
│       - freshness_score >= threshold                                 │
│       - performance_score >= threshold                               │
│    3. Cross-reference with vault_availability                        │
│    4. Select caption with highest combined score                     │
│    5. Match to content_type from vault                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: CHANNEL & TARGET ASSIGNMENT                                │
│  ────────────────────────────────────                                │
│  For each item:                                                      │
│    • Determine channel based on send_type.platform_feature           │
│    • Assign audience_target based on send_type:                      │
│      - Revenue items → all_active                                    │
│      - Renew messages → renew_off                                    │
│      - Expired winback → expired_recent                              │
│      - PPV followup → ppv_non_purchasers                             │
│    • Set linked_post_url for link_drops                              │
│    • Set expires_at for expiring types                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5: TIMING OPTIMIZATION                                        │
│  ─────────────────────────────                                       │
│  Apply timing rules by send_type:                                    │
│    • Revenue PPVs: Prime hours (7pm, 9pm, 10am, 2pm)                 │
│    • Bumps: Distributed 45-90 min after PPVs                         │
│    • Link drops: 2-4 hours after original post                       │
│    • PPV followups: 15-30 min after parent PPV                       │
│    • Retention messages: Off-peak hours (less intrusive)             │
│    • Expired winback: Consistent daily time                          │
│                                                                      │
│  Respect constraints:                                                │
│    • min_hours_between per send_type                                 │
│    • max_per_day limits                                              │
│    • No same send_type back-to-back                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 6: FOLLOW-UP GENERATION                                       │
│  ──────────────────────────────                                      │
│  For each PPV (ppv_video, ppv_message, bundle):                      │
│    • Generate ppv_followup item at +20 minutes                       │
│    • Set parent_send_id to original PPV                              │
│    • Select follow-up caption (ppv_followup type)                    │
│    • Target: ppv_non_purchasers (those who saw but didn't buy)       │
│                                                                      │
│  For each link_drop:                                                 │
│    • Set linked_post_url to campaign being promoted                  │
│    • Set expires_at to 24 hours                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 7: VALIDATION & OUTPUT                                        │
│  ─────────────────────────────                                       │
│  Validate:                                                           │
│    • All required fields populated                                   │
│    • Media requirements met per send_type                            │
│    • Flyer requirements flagged                                      │
│    • Page type restrictions honored                                  │
│    • Caption authenticity score >= 65                                │
│                                                                      │
│  Output:                                                             │
│    • Save to schedule_items with full metadata                       │
│    • Generate markdown summary by day                                │
│    • Flag items needing manual attention (flyer creation)            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Updated MCP Server Tools

### New Tool: `get_send_types`

```python
def get_send_types(category: str = None, page_type: str = None) -> dict:
    """Get all send types, optionally filtered by category and page type."""
    query = """
        SELECT * FROM send_types
        WHERE is_active = 1
    """
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if page_type:
        query += " AND page_type_restriction IN (?, 'both')"
        params.append(page_type)
    query += " ORDER BY sort_order"
    # ...
```

### New Tool: `get_send_type_captions`

```python
def get_send_type_captions(
    creator_id: str,
    send_type_key: str,
    min_freshness: float = 30,
    min_performance: float = 40,
    limit: int = 10
) -> dict:
    """Get captions appropriate for a specific send type."""
    query = """
        SELECT cb.*, stcr.priority as type_priority
        FROM caption_bank cb
        JOIN send_type_caption_requirements stcr ON cb.caption_type = stcr.caption_type
        JOIN send_types st ON stcr.send_type_id = st.send_type_id
        WHERE st.send_type_key = ?
          AND (cb.creator_id = ? OR cb.creator_id IS NULL)
          AND cb.freshness_score >= ?
          AND cb.performance_score >= ?
          AND cb.is_active = 1
        ORDER BY stcr.priority ASC, cb.performance_score DESC
        LIMIT ?
    """
    # ...
```

### New Tool: `get_audience_targets`

```python
def get_audience_targets(page_type: str = None, channel: str = None) -> dict:
    """Get available audience targeting options."""
    # ...
```

### Enhanced: `save_schedule`

```python
def save_schedule(creator_id: str, week_start: str, items: list) -> dict:
    """
    Save schedule with enhanced send type support.

    Each item should include:
    - send_type_key: The send type (e.g., 'ppv_video', 'bump_normal')
    - channel_key: The channel (e.g., 'mass_message', 'wall_post')
    - target_key: Optional audience target (e.g., 'renew_off')
    - linked_post_url: For link_drop types
    - expires_at: For expiring types
    - parent_item_id: For follow-up types
    """
    # ...
```

---

## 7. Volume Assignment Enhancement

### Updated Volume Configuration

```sql
-- Enhanced volume_assignments to support send type categories
ALTER TABLE volume_assignments ADD COLUMN revenue_items_per_day INTEGER DEFAULT 3;
ALTER TABLE volume_assignments ADD COLUMN engagement_items_per_day INTEGER DEFAULT 4;
ALTER TABLE volume_assignments ADD COLUMN retention_items_per_day INTEGER DEFAULT 2;

-- Breakdown by specific types
ALTER TABLE volume_assignments ADD COLUMN ppv_per_day INTEGER DEFAULT 3;
ALTER TABLE volume_assignments ADD COLUMN bundle_per_week INTEGER DEFAULT 3;
ALTER TABLE volume_assignments ADD COLUMN game_per_week INTEGER DEFAULT 2;
ALTER TABLE volume_assignments ADD COLUMN bump_per_day INTEGER DEFAULT 4;
ALTER TABLE volume_assignments ADD COLUMN link_drop_per_day INTEGER DEFAULT 2;
ALTER TABLE volume_assignments ADD COLUMN dm_farm_per_day INTEGER DEFAULT 1;
```

### Volume Tier Defaults

| Tier | PPV/Day | Bundles/Week | Games/Week | Bumps/Day | Link Drops/Day | Retention/Day |
|------|---------|--------------|------------|-----------|----------------|---------------|
| Low (0-999 fans) | 2 | 1 | 1 | 2 | 1 | 1 |
| Mid (1K-4.9K) | 3 | 2 | 1 | 3 | 2 | 2 |
| High (5K-14.9K) | 4 | 3 | 2 | 4 | 3 | 2 |
| Ultra (15K+) | 5 | 4 | 2 | 5 | 4 | 3 |

---

## 8. Output Format Enhancement

### Schedule Item JSON Structure

```json
{
  "item_id": 12345,
  "scheduled_date": "2025-12-16",
  "scheduled_time": "19:00",

  "send_type": {
    "key": "ppv_video",
    "category": "revenue",
    "display_name": "PPV Video"
  },

  "channel": {
    "key": "mass_message",
    "display_name": "Mass Message"
  },

  "target": {
    "key": "all_active",
    "display_name": "All Active Subscribers"
  },

  "content": {
    "caption_id": 5678,
    "caption_text": "...",
    "content_type": "boy_girl",
    "media_type": "video"
  },

  "pricing": {
    "suggested_price": 15.00,
    "campaign_goal": null
  },

  "requirements": {
    "flyer_required": true,
    "media_required": true,
    "link_required": false
  },

  "timing": {
    "expires_at": null,
    "followups": [
      {
        "delay_minutes": 20,
        "send_type": "ppv_followup"
      }
    ]
  },

  "parent_item_id": null,
  "is_followup": false,
  "priority": 1
}
```

---

## 9. Migration Plan

### Phase 1: Schema Creation
1. Create `send_types` table
2. Create `channels` table
3. Create `audience_targets` table
4. Create mapping tables
5. Insert seed data

### Phase 2: Schedule Items Enhancement
1. Add new columns to `schedule_items`
2. Create indexes for new foreign keys
3. Backfill existing items (map `ppv` → `ppv_video`, `bump` → `bump_normal`)

### Phase 3: MCP Server Updates
1. Add new tools (`get_send_types`, `get_send_type_captions`, etc.)
2. Update `save_schedule` to handle new fields
3. Add validation for send type requirements

### Phase 4: Pipeline Updates
1. Update skill definition with new phases
2. Create send type allocation agent
3. Update content curator for send type matching
4. Add follow-up generation logic

### Phase 5: Validation
1. Test all 21 send types can be scheduled
2. Verify channel/target combinations
3. Validate follow-up generation
4. Test page type restrictions

---

## 10. Summary

This enhanced architecture transforms the schedule generator from a simple 2-type system (`ppv`/`bump`) to a comprehensive 21-type system that accurately reflects how OnlyFans pages are actually managed. Key improvements:

| Aspect | Before | After |
|--------|--------|-------|
| Send Types | 2 | 21 |
| Channels | 2 | 5 |
| Audience Targeting | None | 10 segments |
| Caption Matching | Generic | Type-specific |
| Follow-up Generation | Manual | Automatic |
| Page Type Rules | Ignored | Enforced |
| Expiration Handling | None | Automatic |

The system now supports the full operational complexity of professional OnlyFans page management.

---

*Version 2.2.0 | Last Updated: 2025-12-16*
