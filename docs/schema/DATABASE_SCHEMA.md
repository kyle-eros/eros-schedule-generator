# EROS Database Schema Reference

**Version**: 2.4.0
**Database**: eros_sd_main.db
**Total Tables**: 76
**Last Updated**: 2025-12-18

## Overview

Complete schema documentation for all 76 tables in the EROS Schedule Generator database. This document serves as the authoritative reference for database structure, relationships, and usage patterns.

**Database Statistics**:
- **Size**: ~250 MB
- **Active Creators**: 37
- **Total Captions**: 59,405
- **Performance Score**: 93/100 (Grade A - Excellent)
- **Last Audit**: 2025-12-12
- **Data Integrity**: 100% (post-remediation)

## Table of Contents

1. [Core Entity Tables](#core-entity-tables) (7 tables)
2. [Caption Management](#caption-management) (12 tables)
3. [Performance & Analytics](#performance--analytics) (8 tables)
4. [Send Type Configuration](#send-type-configuration) (5 tables)
5. [Volume Management](#volume-management) (10 tables)
6. [Schedule Operations](#schedule-operations) (4 tables)
7. [Content & Templates](#content--templates) (7 tables)
8. [Targeting & Channels](#targeting--channels) (3 tables)
9. [Operational Tracking](#operational-tracking) (7 tables)
10. [Backup & Archive Tables](#backup--archive-tables) (9 tables)
11. [System Tables](#system-tables) (4 tables)
12. [Schema Summary](#schema-summary)
13. [Foreign Key Relationships](#foreign-key-relationships)

---

## Core Entity Tables

### 1. creators

Primary entity table for OnlyFans creator profiles. Root entity referenced by 40+ tables.

**Schema**:
```sql
CREATE TABLE creators (
    creator_id TEXT PRIMARY KEY,
    page_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    page_type TEXT NOT NULL CHECK (page_type IN ('paid', 'free')),
    subscription_price REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    timezone TEXT DEFAULT 'America/Los_Angeles',
    creator_group TEXT,
    current_active_fans INTEGER DEFAULT 0,
    current_total_earnings REAL DEFAULT 0,
    performance_tier INTEGER CHECK (performance_tier IN (1,2,3,4)),
    persona_type TEXT,
    content_category TEXT CHECK (content_category IN ('lifestyle', 'softcore', 'amateur', 'explicit')) DEFAULT 'softcore',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `creator_id` | TEXT | Unique creator identifier (PRIMARY KEY) |
| `page_name` | TEXT | OnlyFans page handle (UNIQUE) |
| `display_name` | TEXT | Human-readable display name |
| `page_type` | TEXT | Subscription model: 'paid' or 'free' |
| `subscription_price` | REAL | Monthly subscription price (USD) |
| `timezone` | TEXT | Creator timezone (IANA format) |
| `performance_tier` | INTEGER | Performance classification (1=TOP, 4=LOW) |
| `persona_type` | TEXT | Persona archetype key (FK to personas) |
| `content_category` | TEXT | Content category for bump multiplier: 'lifestyle', 'softcore', 'amateur', 'explicit' (v3.0) |
| `is_active` | INTEGER | Active status (1=active, 0=inactive) |

**Indexes**:
- `idx_creators_page_name` - Fast lookup by page_name
- `idx_creators_tier` - Filter by performance_tier
- `idx_creators_active` - Filter by is_active
- `idx_creators_content_category` - Filter by content_category (v3.0)

**Referenced By**: personas, vault_matrix, schedule_items, volume_assignments, saturation_analysis, caption_creator_performance, message_performance, wall_posts, mass_messages, and 30+ more tables.

**Usage Notes**:
- `page_type` determines eligibility for retention send types
- `performance_tier` drives volume assignment and content allocation
- `timezone` used for optimal posting time calculation

---

### 2. personas (formerly creator_personas)

Creator personality and tone configuration for caption matching.

**Schema**:
```sql
CREATE TABLE personas (
    creator_id TEXT PRIMARY KEY,
    persona_type TEXT NOT NULL,
    tone_keywords TEXT,
    emoji_style TEXT CHECK (emoji_style IN ('minimal', 'moderate', 'heavy')),
    slang_level TEXT CHECK (slang_level IN ('none', 'light', 'moderate', 'heavy')),
    voice_sample TEXT,
    archetype_score REAL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `creator_id` | TEXT | One-to-one with creators (PRIMARY KEY, FK) |
| `persona_type` | TEXT | Archetype (flirty_playful, innocent_sweet, etc.) |
| `tone_keywords` | TEXT | JSON array of tone descriptors |
| `emoji_style` | TEXT | Emoji usage level |
| `slang_level` | TEXT | Slang intensity |
| `voice_sample` | TEXT | Example caption demonstrating voice |
| `archetype_score` | REAL | Persona match confidence (0-100) |

**Foreign Keys**:
- `creator_id` REFERENCES `creators(creator_id)`

**Usage Notes**:
- Persona matching contributes 5% to caption scoring
- `voice_sample` used for AI tone analysis
- All 37 active creators have persona profiles

---

### 3. content_categories (v3.0)

Reference table for content category classifications used in bump multiplier calculation.

**Schema**:
```sql
CREATE TABLE content_categories (
    category_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    bump_multiplier REAL NOT NULL DEFAULT 1.0,
    description TEXT
);
```

**Data**:
| category_key | display_name | bump_multiplier | description |
|--------------|--------------|-----------------|-------------|
| `lifestyle` | Lifestyle | 1.0 | Non-explicit baseline - GFE, personal connection |
| `softcore` | Softcore | 1.5 | Suggestive content - moderate engagement needs |
| `amateur` | Amateur | 2.0 | Amateur style - authentic appeal, higher engagement |
| `explicit` | Explicit | 2.67 | Explicit commercial - maximum engagement multiplier |

**Usage Notes**:
- Referenced by `creators.content_category` column
- Multipliers applied in Volume Optimization v3.0 bump calculation
- LOW tier creators: full multiplier applied
- MID/HIGH/ULTRA tiers: multiplier capped at 1.5x

**Added**: Migration 016 (v2.4.0)

---

### 4. vault_matrix

Creator content inventory tracking for caption filtering.

**Schema**:
```sql
CREATE TABLE vault_matrix (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    quantity INTEGER DEFAULT 0,
    quality_rating TEXT CHECK (quality_rating IN ('HIGH', 'MID', 'LOW')),
    last_updated TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `creator_id` | TEXT | Creator identifier (FK) |
| `content_type` | TEXT | Content type (solo, b/g, g/g, etc.) |
| `quantity` | INTEGER | Available pieces in vault |
| `quality_rating` | TEXT | Quality tier (HIGH/MID/LOW) |
| `last_updated` | TEXT | Last inventory update timestamp |

**Indexes**:
- `idx_vault_creator` - Lookup by creator
- `idx_vault_content_type` - Filter by content type

**Usage Notes**:
- **CRITICAL**: Caption selection uses vault matrix as HARD FILTER
- Only captions matching creator's vault content types are returned
- Empty vault matrix = no captions available for that creator

---

### 4. creator_analytics_summary

Aggregated performance metrics by time period.

**Schema**:
```sql
CREATE TABLE creator_analytics_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('7d', '14d', '30d', '90d')),
    total_sends INTEGER DEFAULT 0,
    total_earnings REAL DEFAULT 0,
    avg_earnings_per_send REAL DEFAULT 0,
    avg_purchase_rate REAL DEFAULT 0,
    avg_view_rate REAL DEFAULT 0,
    calculated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Used by performance-analyst agent to calculate saturation
- Multi-horizon analysis: 7d, 14d, 30d periods
- Refreshed daily

---

### 5. creator_feature_flags

Per-creator feature toggles and experimental settings.

**Schema**:
```sql
CREATE TABLE creator_feature_flags (
    creator_id TEXT PRIMARY KEY,
    dynamic_volume_enabled INTEGER DEFAULT 1,
    ppv_followup_enabled INTEGER DEFAULT 1,
    multi_horizon_fusion INTEGER DEFAULT 1,
    elasticity_bounds_enabled INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Controls feature rollout per creator
- `dynamic_volume_enabled` = use get_volume_config() vs static assignments
- All flags default to enabled for active creators

---

### 6. creator_rotation_state

Content rotation pattern management to prevent subscriber fatigue.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#rotation-state-management) for complete documentation.

**Summary**:
- Manages per-creator content rotation patterns
- Tracks `rotation_pattern` (JSON), `pattern_start_date`, `days_on_pattern`
- Current rotation state: initializing, active, paused, rotating

---

## Caption Management

The caption management system consists of 12 tables handling the universal caption pool (59,405 captions), performance tracking, classification, and audit trails.

### 7. caption_bank

Universal caption repository accessible to all creators (with vault filtering).

**Schema**:
```sql
CREATE TABLE caption_bank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption_id TEXT UNIQUE NOT NULL,
    creator_id TEXT,  -- HISTORICAL ONLY, not used in selection
    caption_text TEXT NOT NULL,
    caption_type TEXT NOT NULL,
    performance_score REAL DEFAULT 0.0,
    total_earnings REAL DEFAULT 0.0,
    total_sends INTEGER DEFAULT 0,
    avg_purchase_rate REAL DEFAULT 0.0,
    last_used_date TEXT,
    freshness_score REAL DEFAULT 100.0,
    content_type TEXT,
    media_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `caption_id` | TEXT | Unique caption identifier (UNIQUE) |
| `creator_id` | TEXT | HISTORICAL ONLY - preserved for analytics, ignored in selection |
| `caption_text` | TEXT | Actual caption content |
| `caption_type` | TEXT | Caption type (ppv_winner, ppv_bundle, link_drop, etc.) |
| `performance_score` | REAL | Weighted performance score (0-100) |
| `total_earnings` | REAL | Lifetime earnings from this caption (USD) |
| `total_sends` | INTEGER | Number of times caption has been used |
| `last_used_date` | TEXT | Last usage timestamp |
| `freshness_score` | REAL | Calculated freshness (100 - days_since_use * 2) |
| `content_type` | TEXT | Associated content type (solo, b/g, etc.) |
| `media_count` | INTEGER | Number of media pieces |

**Indexes**:
- `idx_caption_bank_caption_id` - Primary lookup
- `idx_caption_bank_type` - Filter by caption_type
- `idx_caption_bank_freshness` - Sort by freshness_score
- `idx_caption_bank_performance` - Sort by performance_score
- `idx_caption_bank_content_type` - Filter by content_type

**CRITICAL Usage Notes**:
- **Universal Access**: All 59,405 captions accessible to any creator
- **Vault Filtering**: Only captions matching creator's vault_matrix content types returned
- **creator_id Field**: Preserved for historical analytics but **IGNORED in caption selection**
- **Freshness Scoring**: `freshness_score = 100 - (days_since_last_use * 2)`
  - Never used: 100 (maximum freshness)
  - Used 30 days ago: 40
  - Minimum: 0
- **Caption Selection Weights**:
  - Freshness: 40%
  - Performance: 35%
  - Type Priority: 15%
  - Diversity: 5%
  - Persona: 5%

---

### 8. caption_classifications

Detailed caption taxonomy and quality ratings.

**Schema**:
```sql
CREATE TABLE caption_classifications (
    caption_id TEXT PRIMARY KEY,
    caption_type TEXT NOT NULL,
    sub_type TEXT,  -- DEPRECATED: Use content_category instead (v3.0)
    content_category TEXT,  -- Active: Use this for content classification
    quality_tier TEXT CHECK (quality_tier IN ('HIGH', 'MID', 'LOW')),
    has_clickbait INTEGER DEFAULT 0,
    has_urgency INTEGER DEFAULT 0,
    has_value_anchor INTEGER DEFAULT 0,
    has_cta INTEGER DEFAULT 0,
    emoji_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id)
);
```

**Usage Notes**:
- Enhances caption_bank with structural classification
- `quality_tier` influences selection probability
- Clickbait/urgency/value_anchor used for PPV structure validation

---

### 9. caption_creator_performance

Per-creator, per-caption performance tracking.

**Schema**:
```sql
CREATE TABLE caption_creator_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    caption_id TEXT NOT NULL,
    total_sends INTEGER DEFAULT 0,
    total_earnings REAL DEFAULT 0.0,
    avg_purchase_rate REAL DEFAULT 0.0,
    avg_view_rate REAL DEFAULT 0.0,
    last_used_date TEXT,
    performance_score REAL DEFAULT 0.0,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id),
    UNIQUE (creator_id, caption_id)
);
```

**Usage Notes**:
- Tracks how each caption performs for each creator
- Used to calculate personalized performance scores
- Updated after each send

---

### 10-12. Caption Audit & History Tables

**caption_audit_log**: Tracks caption creation, modification, deletion events
**caption_score_history**: Historical performance score changes over time
**caption_merge_log**: Tracks caption deduplication and merging operations

**Backup Tables** (4 tables):
- `caption_bank_backup_20251214` - Point-in-time snapshot
- `caption_bank_classification_backup` - Classification snapshot
- `caption_bank_classification_backup_v2` - Updated classification snapshot
- `caption_creator_performance_backup_20251214` - Performance snapshot

---

## Performance & Analytics

### 13. saturation_analysis

Multi-horizon saturation and opportunity scores for volume optimization.

**Schema**:
```sql
CREATE TABLE saturation_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    analysis_period TEXT NOT NULL CHECK (analysis_period IN ('7d', '14d', '30d')),
    saturation_score REAL DEFAULT 0.0,
    opportunity_score REAL DEFAULT 0.0,
    send_frequency REAL,
    revenue_per_send REAL,
    engagement_rate REAL,
    calculated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `analysis_period` | TEXT | Time horizon: '7d', '14d', '30d' |
| `saturation_score` | REAL | Saturation level (0-100, higher = more saturated) |
| `opportunity_score` | REAL | Growth opportunity (0-100, higher = more opportunity) |
| `send_frequency` | REAL | Average sends per day in period |
| `revenue_per_send` | REAL | Average revenue per send (USD) |
| `engagement_rate` | REAL | View rate * purchase rate |

**Usage Notes**:
- Used by performance-analyst agent (Phase 1)
- Multi-horizon fusion combines 7d/14d/30d scores
- Drives dynamic volume calculation
- Refreshed daily

---

### 14. message_performance

Detailed performance metrics for individual messages.

**Schema**:
```sql
CREATE TABLE message_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    message_id TEXT UNIQUE,
    send_type TEXT,
    sent_count INTEGER DEFAULT 0,
    viewed_count INTEGER DEFAULT 0,
    purchased_count INTEGER DEFAULT 0,
    earnings REAL DEFAULT 0.0,
    view_rate REAL DEFAULT 0.0,
    purchase_rate REAL DEFAULT 0.0,
    sent_date TEXT,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Granular message-level tracking
- Used to calculate caption performance scores
- Powers get_best_timing() MCP tool for optimal posting times

---

### 15. mass_messages

Historical mass message send data.

**Schema**:
```sql
CREATE TABLE mass_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT,
    page_name TEXT,
    message_id TEXT,
    sent_count INTEGER DEFAULT 0,
    viewed_count INTEGER DEFAULT 0,
    purchased_count INTEGER DEFAULT 0,
    earnings REAL DEFAULT 0.0,
    sent_date TEXT,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Historical message data imported from OnlyFans
- Used for performance trend analysis
- Backfilled creator_id in Wave 1C remediation

---

### 16. wall_posts

Wall post performance tracking.

**Schema**:
```sql
CREATE TABLE wall_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT,
    page_name TEXT,
    post_id TEXT UNIQUE,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    post_date TEXT,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Tracks engagement on wall posts
- Used for engagement rate calculations
- Less critical than message_performance

---

### 17-20. Supporting Analytics Tables

**creator_performance_30d**: 30-day rolling performance summary per creator
**day_of_week_performance**: Engagement patterns by day of week (used for DOW multipliers)
**top_content_types**: Ranked content types by creator (TOP/MID/LOW/AVOID tiers)
**creator_demographics**: Audience demographic data (age, location, subscription length)

---

## Send Type Configuration

### 21. send_types

Master table defining the 22-type send taxonomy.

**Schema**:
```sql
CREATE TABLE send_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_key TEXT UNIQUE NOT NULL,
    send_type_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('revenue', 'engagement', 'retention')),
    description TEXT,
    requires_ppv INTEGER DEFAULT 0,
    min_price REAL,
    max_price REAL,
    typical_timing TEXT,
    page_type_filter TEXT CHECK (page_type_filter IN ('paid', 'free', 'both')),
    is_active INTEGER DEFAULT 1
);
```

**22 Send Types**:

**Revenue (9 types)**:
- ppv_unlock
- ppv_wall
- tip_goal
- bundle
- flash_bundle
- game_post
- first_to_tip
- vip_program
- snapchat_bundle

**Engagement (9 types)**:
- link_drop
- wall_link_drop
- bump_normal
- bump_descriptive
- bump_text_only
- bump_flyer
- dm_farm
- like_farm
- live_promo

**Retention (4 types)**:
- renew_on_post
- renew_on_message
- ppv_followup
- expired_winback

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `send_type_key` | TEXT | Unique key (ppv_unlock, tip_goal, etc.) |
| `category` | TEXT | revenue, engagement, or retention |
| `requires_ppv` | INTEGER | 1 if requires PPV content |
| `page_type_filter` | TEXT | Eligible page types (paid/free/both) |
| `typical_timing` | TEXT | Optimal posting time guidance |

**Usage Notes**:
- **Always use send_type_key** in application logic (never send_type_id)
- `page_type_filter` enforced during schedule generation
- Retention types only for `paid` page types

---

### 22. send_type_caption_type_map

Mapping between send types and compatible caption types.

**Schema**:
```sql
CREATE TABLE send_type_caption_type_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_key TEXT NOT NULL,
    caption_type TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    FOREIGN KEY (send_type_key) REFERENCES send_types(send_type_key)
);
```

**Usage Notes**:
- Used by caption-selection-pro to find compatible captions
- `priority` field influences caption ranking
- Many-to-many relationship: one send type can have multiple caption types

---

### 23. send_type_content_compatibility

Defines which content types are compatible with each send type.

**Schema**:
```sql
CREATE TABLE send_type_content_compatibility (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_key TEXT NOT NULL,
    content_type TEXT NOT NULL,
    compatibility_score REAL DEFAULT 1.0,
    FOREIGN KEY (send_type_key) REFERENCES send_types(send_type_key)
);
```

**Usage Notes**:
- Filters content by send type requirements
- `compatibility_score` weights content type preference
- Example: ppv_bundle strongly prefers 'bundle' content type

---

### 24. content_type_taxonomy

Master list of all content types with metadata.

**Schema**:
```sql
CREATE TABLE content_type_taxonomy (
    content_type TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category TEXT,
    default_price REAL,
    is_active INTEGER DEFAULT 1
);
```

**Content Types** (18 types):
solo, lingerie, tease, bj, bg, gg, anal, toy, shower, outdoor, custom, workout, cosplay, roleplay, pov, feet, bundle, exclusive

---

### 25. caption_type_migration_map

Legacy mapping for deprecated caption type transitions.

**Usage Notes**:
- Tracks ppv_message → ppv_unlock migration
- Maintains backward compatibility during transition period
- Removal scheduled for 2025-01-16

---

## Volume Management

Volume management uses a sophisticated 10-module dynamic calculation system with multi-horizon fusion, confidence dampening, DOW distribution, elasticity bounds, bump multipliers (v3.0), and followup scaling (v3.0).

### 26. volume_predictions

Stores prediction_id records for tracking volume calculation outcomes.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#volume-prediction-system) for complete 222-line documentation.

**Summary**:
- Tracks `prediction_id`, `creator_id`, `week_start`, `predicted_volumes`
- Includes confidence scores, elasticity caps, and DOW multipliers
- Links to volume_calculation_log for audit trail

---

### 27. volume_calculation_log

Audit trail for all volume calculation invocations.

**Schema**:
```sql
CREATE TABLE volume_calculation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    calculation_timestamp TEXT DEFAULT (datetime('now')),
    input_params TEXT,  -- JSON
    output_result TEXT,  -- JSON (OptimizedVolumeResult)
    execution_time_ms REAL,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Every get_volume_config() call logged
- `output_result` contains full OptimizedVolumeResult JSON
- Used for performance monitoring and debugging

---

### 28. volume_adjustment_outcomes

Tracks manual volume adjustments and their outcomes.

**Schema**:
```sql
CREATE TABLE volume_adjustment_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    adjustment_date TEXT NOT NULL,
    original_volume INTEGER,
    adjusted_volume INTEGER,
    adjustment_reason TEXT,
    outcome_earnings REAL,
    outcome_engagement REAL,
    was_successful INTEGER,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Machine learning feedback loop
- Tracks success rate of volume changes
- Informs future confidence dampening

---

### 29. volume_triggers (v3.0)

Performance-based triggers that automatically adjust content type allocations.

**Schema**:
```sql
CREATE TABLE volume_triggers (
    trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN (
        'HIGH_PERFORMER', 'TRENDING_UP', 'EMERGING_WINNER',
        'SATURATING', 'AUDIENCE_FATIGUE'
    )),
    adjustment_multiplier REAL NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT CHECK (confidence IN ('low', 'moderate', 'high')) DEFAULT 'moderate',
    metrics_json TEXT,
    detected_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    applied_count INTEGER DEFAULT 0,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `trigger_id` | INTEGER | Auto-incrementing primary key |
| `creator_id` | TEXT | Creator this trigger applies to (FK) |
| `content_type` | TEXT | Content type being adjusted (e.g., 'b/g_explicit') |
| `trigger_type` | TEXT | Signal type: HIGH_PERFORMER, TRENDING_UP, EMERGING_WINNER, SATURATING, AUDIENCE_FATIGUE |
| `adjustment_multiplier` | REAL | Volume multiplier (e.g., 1.20 = +20%, 0.85 = -15%) |
| `reason` | TEXT | Human-readable explanation (e.g., 'RPS $245, conversion 8.2%') |
| `confidence` | TEXT | Detection confidence: low, moderate, high |
| `expires_at` | TEXT | ISO timestamp when trigger expires |
| `is_active` | INTEGER | Active status (1=active, 0=deactivated) |
| `applied_count` | INTEGER | Number of times this trigger has been applied |

**Indexes**:
- `idx_volume_triggers_creator_active` - Partial index on (creator_id) WHERE is_active = 1
- `idx_volume_triggers_expires` - Expiration filtering
- `idx_volume_triggers_type` - Filter by trigger_type

**Trigger Types**:
| Type | Detection Criteria | Typical Adjustment |
|------|-------------------|-------------------|
| HIGH_PERFORMER | RPS > $200, conversion > 6% | +20% |
| TRENDING_UP | WoW RPS increase > 15% | +10% |
| EMERGING_WINNER | RPS > $150, used < 3 times in 30d | +30% |
| SATURATING | Declining engagement 3+ days | -15% |
| AUDIENCE_FATIGUE | Open rate decline > 10% over 7d | -25% |

**Usage Notes**:
- Detected by `performance-analyst` agent during schedule generation
- Persisted via `save_volume_triggers` MCP tool
- Retrieved via `get_active_volume_triggers` MCP tool (auto-filters expired)
- Applied during `get_volume_config()` calculation
- Existing active triggers deactivated when new analysis runs

**Added**: Migration 017 (v2.4.0)

---

### 30. volume_assignments (deprecated, use volume_predictions)

Static volume assignments (legacy system).

**Deprecation Status**:
- Replaced by dynamic volume calculation (get_volume_config)
- Still functional for backward compatibility
- New schedules should use get_volume_config()

---

### 30-34. Volume Supporting Tables

**volume_assignments_archived**: Historical volume assignments
**volume_assignments_backup**: Pre-migration backup
**volume_overrides**: Manual volume overrides per creator/date
**volume_performance_tracking**: Performance outcomes by volume level

---

## Schedule Operations

### 35. schedule_items

Generated schedule items from schedule generation pipeline.

**Schema**:
```sql
CREATE TABLE schedule_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    schedule_date TEXT NOT NULL,
    schedule_time TEXT NOT NULL,
    send_type_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    audience_target TEXT,
    caption_id TEXT,
    content_type TEXT,
    price REAL,
    media_count INTEGER,
    parent_item_id INTEGER,  -- For PPV followups
    expiration_hours INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    FOREIGN KEY (send_type_key) REFERENCES send_types(send_type_key),
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id)
);
```

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `schedule_date` | TEXT | Date to send (YYYY-MM-DD) |
| `schedule_time` | TEXT | Time to send (HH:MM in creator timezone) |
| `send_type_key` | TEXT | Send type (ppv_unlock, tip_goal, etc.) |
| `channel` | TEXT | Distribution channel (mass_message, wall_post, etc.) |
| `audience_target` | TEXT | Target segment (all_fans, top_tippers, non_tippers, etc.) |
| `parent_item_id` | INTEGER | Links followup to parent PPV |
| `expiration_hours` | INTEGER | PPV expiration time (12-72 hours) |

**Usage Notes**:
- Written by schedule-assembler agent (Phase 7)
- Used by save_schedule() MCP tool
- `parent_item_id` creates followup chains

---

### 36. scheduled_sends

Actual sends executed (post-generation tracking).

**Schema**:
```sql
CREATE TABLE scheduled_sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_item_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    sent_at TEXT,
    status TEXT CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    message_id TEXT,
    error_message TEXT,
    FOREIGN KEY (schedule_item_id) REFERENCES schedule_items(id),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Tracks execution status of scheduled items
- `message_id` links to OnlyFans platform
- Used for reconciliation and error tracking

---

### 37. ppv_followup_tracking

Tracks PPV followup message timing and optimization.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#ppv-followup-tracking) for complete documentation.

**Summary**:
- Tracks parent_ppv_id, followup_time, gap_minutes
- Optimal window: 15-45 minutes
- Max 4 followups per day enforced

---

### 38. daily_activity_schedules

Pre-generated activity schedules with send slot allocations.

**Schema**:
```sql
CREATE TABLE daily_activity_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    schedule_date TEXT NOT NULL,
    send_slots TEXT,  -- JSON array of {time, send_type_key, channel}
    total_sends INTEGER,
    revenue_sends INTEGER,
    engagement_sends INTEGER,
    retention_sends INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    UNIQUE (creator_id, schedule_date)
);
```

**Usage Notes**:
- Pre-allocated daily slots for schedule generation
- `send_slots` JSON format: `[{"time": "14:00", "send_type_key": "ppv_unlock", "channel": "mass_message"}, ...]`
- Improves generation speed by pre-computing allocations

---

## Content & Templates

### 39. bump_variants

Template library for bump message variations.

**Schema**:
```sql
CREATE TABLE bump_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_name TEXT NOT NULL,
    category TEXT CHECK (category IN ('URGENT', 'STANDARD', 'LATE')),
    content_type TEXT,
    template_text TEXT NOT NULL,
    timing_min_minutes INTEGER,
    timing_max_minutes INTEGER,
    is_active INTEGER DEFAULT 1
);
```

**Bump Categories**:
- **URGENT**: 15-30 minutes (high urgency language)
- **STANDARD**: 30-60 minutes (moderate urgency)
- **LATE**: 60-120 minutes (final opportunity)

**Usage Notes**:
- 70 bump variants created in Wave 3A population
- Timing-based selection for PPV bumps
- Content type matched to original PPV

---

### 40. game_post_templates

Template library for game-style engagement posts.

**Schema**:
```sql
CREATE TABLE game_post_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_type TEXT NOT NULL,
    template_text TEXT NOT NULL,
    prize_tiers TEXT,  -- JSON
    participation_style TEXT,
    is_active INTEGER DEFAULT 1
);
```

**Game Types**: spin-the-wheel, tip-matching, trivia, bingo, raffle

**Usage Notes**:
- Used for game_post send type
- `prize_tiers` defines reward structure
- High engagement, moderate revenue potential

---

### 41. tip_incentive_templates

Template library for tip goal structures.

**Schema**:
```sql
CREATE TABLE tip_incentive_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incentive_type TEXT NOT NULL,
    template_text TEXT NOT NULL,
    suggested_goal_amount REAL,
    content_unlock_type TEXT,
    is_active INTEGER DEFAULT 1
);
```

**Incentive Types**: countdown, milestone, random-unlock, progressive-reveal

**Usage Notes**:
- Used for tip_goal send type
- `suggested_goal_amount` based on creator tier
- Higher conversion than generic PPV

---

### 42. vip_post_templates

Template library for VIP program messaging.

**Schema**:
```sql
CREATE TABLE vip_post_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vip_tier TEXT NOT NULL,
    template_text TEXT NOT NULL,
    benefits_description TEXT,
    monthly_cost REAL,
    is_active INTEGER DEFAULT 1
);
```

**VIP Tiers**: bronze, silver, gold, platinum

**Usage Notes**:
- Used for vip_program send type
- Max 1 VIP program post per week (constraint)
- High-value creator retention strategy

---

### 43. retention_templates

Template library for subscriber retention messaging.

**Schema**:
```sql
CREATE TABLE retention_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retention_type TEXT NOT NULL CHECK (retention_type IN ('renew_on_post', 'renew_on_message', 'expired_winback')),
    template_text TEXT NOT NULL,
    target_audience TEXT,
    incentive_type TEXT,
    is_active INTEGER DEFAULT 1
);
```

**Retention Types**:
- **renew_on_post**: Public wall post encouraging renewals
- **renew_on_message**: Direct message to expiring subscribers
- **expired_winback**: Re-engagement for recently expired fans

**Usage Notes**:
- Only for `paid` page types
- Target audiences: expiring_soon, expired_30d, expired_90d
- High-priority for creator retention

---

### 44-45. Link Drop & Free Preview Templates

**link_drop_templates**: Template library for link drop engagement posts
**free_preview_bank**: Free preview content inventory for paid page link drops

---

## Targeting & Channels

### 46. audience_targets

Audience segment definitions for targeted messaging.

**Schema**:
```sql
CREATE TABLE audience_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_key TEXT UNIQUE NOT NULL,
    target_name TEXT NOT NULL,
    description TEXT,
    target_query TEXT,  -- SQL WHERE clause fragment
    page_type_filter TEXT CHECK (page_type_filter IN ('paid', 'free', 'both')),
    channel_compatibility TEXT,  -- JSON array of compatible channels
    is_active INTEGER DEFAULT 1
);
```

**Audience Segments** (19 targets):
- all_fans
- top_tippers
- top_spenders
- recent_purchasers
- non_tippers
- inactive_fans
- new_subscribers
- high_engagement_fans
- expiring_soon
- expired_30d
- tip_goal_participants
- tip_goal_non_participants
- bundle_buyers
- ppv_buyers
- free_trial_users
- (and 4 more specialized segments)

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `target_key` | TEXT | Unique segment identifier |
| `target_query` | TEXT | SQL WHERE clause for filtering |
| `page_type_filter` | TEXT | Eligible page types |
| `channel_compatibility` | TEXT | JSON array of compatible channels |

**Usage Notes**:
- Used by audience-targeter agent (Phase 4)
- `target_query` executed against OnlyFans subscriber data
- Channel compatibility enforced during assignment

---

### 47. channels

Distribution channel definitions.

**Schema**:
```sql
CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_key TEXT UNIQUE NOT NULL,
    channel_name TEXT NOT NULL,
    description TEXT,
    supports_targeting INTEGER DEFAULT 0,
    requires_media INTEGER DEFAULT 0,
    typical_reach_pct REAL,
    is_active INTEGER DEFAULT 1
);
```

**5 Distribution Channels**:
1. **mass_message**: Direct message to all/targeted fans (supports targeting)
2. **wall_post**: Public wall post visible to all subscribers
3. **targeted_message**: Direct message to specific segment (supports targeting)
4. **story**: 24-hour story post (no targeting)
5. **live**: Live streaming session (no targeting)

**Key Columns**:
| Column | Type | Description |
|--------|------|-------------|
| `supports_targeting` | INTEGER | 1 if channel allows audience targeting |
| `requires_media` | INTEGER | 1 if channel requires media content |
| `typical_reach_pct` | REAL | Expected reach percentage (0-100) |

**Usage Notes**:
- `mass_message` and `targeted_message` support audience targeting
- `wall_post` has highest organic reach
- `story` and `live` have time-limited visibility

---

### 48. creator_pinned_posts

Pinned wall posts for each creator (promotional priority).

**Schema**:
```sql
CREATE TABLE creator_pinned_posts (
    creator_id TEXT PRIMARY KEY,
    post_id TEXT,
    post_type TEXT,
    pinned_at TEXT,
    expires_at TEXT,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Usage Notes**:
- Max 1 pinned post per creator at a time
- Used for high-priority promotions (bundles, VIP programs)
- Automatically expires after set duration

---

## Operational Tracking

### 49. timing_idempotency

Prevents duplicate schedule generation runs.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#timing-idempotency) for complete documentation.

**Summary**:
- Tracks operation_key (creator_id + week_start)
- Prevents accidental double-scheduling
- TTL-based cleanup for expired entries

---

### 50. timing_operation_log

Audit log for all timing-related operations.

**Schema**:
```sql
CREATE TABLE timing_operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    creator_id TEXT,
    operation_timestamp TEXT DEFAULT (datetime('now')),
    input_params TEXT,
    output_result TEXT,
    execution_time_ms REAL,
    status TEXT CHECK (status IN ('success', 'failure', 'partial'))
);
```

**Usage Notes**:
- Logs all timing-optimizer operations
- Used for performance monitoring
- Tracks get_best_timing() MCP tool calls

---

### 51. circuit_breaker_state

Circuit breaker pattern implementation for reliability.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#circuit-breaker-pattern) for complete documentation.

**Summary**:
- Tracks service_name, state (closed, open, half_open), failure_count
- Prevents cascade failures in multi-service architecture
- Auto-recovery with configurable thresholds

---

### 52. saga_execution_log

Distributed transaction tracking using saga pattern.

**Schema**: See [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md#saga-execution-log) for complete documentation.

**Summary**:
- Tracks multi-step transaction state across services
- Compensation logic for rollback scenarios
- Critical for schedule generation reliability

---

### 53-55. Agent & Import Tracking

**agent_execution_log**: Tracks all agent invocations with input/output
**import_logs**: Tracks data import operations from OnlyFans platform
**caption_integrity_issues**: Tracks detected data quality issues for manual review

---

## Backup & Archive Tables

### 56-64. Backup & Archive Tables

The database includes 9 backup and archive tables for disaster recovery and historical reference:

**Backup Tables** (preserve point-in-time snapshots):
- `caption_bank_backup_20251214` - Pre-remediation caption snapshot
- `caption_bank_classification_backup` - Classification taxonomy snapshot
- `caption_bank_classification_backup_v2` - Updated classification snapshot
- `caption_creator_performance_backup_20251214` - Performance metrics snapshot
- `volume_assignments_backup` - Static volume assignments snapshot

**Archive Tables** (long-term historical storage):
- `volume_assignments_archived` - Historical volume assignments
- `caption_bank_legacy` - Pre-migration caption format
- `caption_bank_snapshot_006` - Migration checkpoint snapshot
- `caption_bank_wave2_backup` - Wave 2 remediation checkpoint

**Temporary/Staging Tables**:
- `creator_alias_lookup` - Temporary creator name normalization
- `unlinked_message_staging` - Import reconciliation staging
- `caption_merge_log` - Deduplication audit trail

**Usage Notes**:
- Backup tables created before major migrations
- 30/90/730-day retention policy (see BACKUP_RECOVERY.md)
- Archive tables provide historical trend analysis

---

## System Tables

### 65-68. SQLite System Tables

**sqlite_sequence**: AUTO_INCREMENT counter tracking (SQLite internal)
**sqlite_stat1**: Index statistics for query optimizer (SQLite internal)

**Additional System Tables** (2):
- `creator_universal_access`: Feature flag table for universal caption access
- `game_wheel_configs`: Configuration for game wheel randomization logic

---

## Schema Summary

### Table Count by Category

| Category | Count | Purpose |
|----------|-------|---------|
| Core Entity Tables | 6 | Creators, personas, vault, demographics, flags, rotation |
| Caption Management | 12 | Caption bank, classifications, performance, audit trails |
| Performance & Analytics | 8 | Saturation, trends, message performance, analytics |
| Send Type Configuration | 5 | 22-type taxonomy, compatibility mappings, content types |
| Volume Management | 9 | Dynamic calculation, predictions, assignments, outcomes |
| Schedule Operations | 4 | Generated schedules, followup tracking, daily slots |
| Content & Templates | 7 | Bumps, tips, games, VIP, retention, link drops, previews |
| Targeting & Channels | 3 | Audience segments, channels, pinned posts |
| Operational Tracking | 7 | Timing, circuit breaker, saga logs, agent execution |
| Backup & Archive Tables | 9 | Snapshots, backups, archived data, staging |
| System Tables | 4 | SQLite internal, universal access, game configs |
| **TOTAL** | **74** | |

### Database Size Distribution

| Data Type | Approx Size | Percentage |
|-----------|-------------|------------|
| Caption Bank | ~80 MB | 32% |
| Message Performance | ~60 MB | 24% |
| Analytics & Performance | ~50 MB | 20% |
| Backups & Archives | ~30 MB | 12% |
| Templates & Configuration | ~20 MB | 8% |
| Operational Logs | ~10 MB | 4% |
| **TOTAL** | **~250 MB** | **100%** |

---

## Foreign Key Relationships

### Primary Entities

**creators.creator_id** (Referenced by 40+ tables):
- personas.creator_id (1:1)
- vault_matrix.creator_id (1:N)
- schedule_items.creator_id (1:N)
- volume_assignments.creator_id (1:N)
- saturation_analysis.creator_id (1:N)
- caption_creator_performance.creator_id (1:N)
- message_performance.creator_id (1:N)
- mass_messages.creator_id (1:N)
- wall_posts.creator_id (1:N)
- (30+ more tables)

**send_types.send_type_key** (Referenced by 8 tables):
- schedule_items.send_type_key (N:1)
- send_type_caption_type_map.send_type_key (N:N via junction)
- send_type_content_compatibility.send_type_key (N:N via junction)
- message_performance.send_type (N:1)
- (4 more tables)

**caption_bank.caption_id** (Referenced by 5 tables):
- caption_classifications.caption_id (1:1)
- caption_creator_performance.caption_id (N:N with creators)
- schedule_items.caption_id (N:1)
- caption_audit_log.caption_id (1:N)
- caption_score_history.caption_id (1:N)

### Referential Integrity

**Foreign Key Enforcement**: ✅ ENABLED (as of Wave 1A remediation)

```sql
PRAGMA foreign_keys = ON;
```

**Cascade Rules**:
- Most foreign keys use `ON DELETE RESTRICT` (prevent orphans)
- Backup tables use `ON DELETE SET NULL` (preserve historical data)
- Archive tables have no foreign keys (detached historical records)

### Orphan Prevention

**Zero Orphaned Records** (as of 2025-12-12 audit):
- ✅ All creators have persona profiles
- ✅ All creators have volume assignments
- ✅ All schedule_items link to valid creators
- ✅ All caption_creator_performance records link to valid caption_ids
- ✅ 100% referential integrity across 40+ FK relationships

---

## Database Health Metrics

### Quality Score: 93/100 (Grade A - Excellent)

**Quality Breakdown** (from 2025-12-12 audit):

| Quality Dimension | Score | Weight | Status |
|-------------------|-------|--------|--------|
| FK Enforcement | 100% | 25% | ✅ PASS |
| Creator ID Linkage | 100% | 20% | ✅ PASS (45% → 100% fixed) |
| Caption Freshness Validity | 100% | 15% | ✅ PASS |
| Performance Score Validity | 100% | 15% | ✅ PASS |
| Creator Completeness | 100% | 15% | ✅ PASS |
| Logical Data Integrity | 100% | 10% | ✅ PASS (99.9% → 100% fixed) |

### Remediation History

**Wave 1: Foundation & Data Integrity**
- Enabled foreign key enforcement (+25.0 points)
- Fixed 6 negative sent_count values
- Corrected 60 impossible view rates
- Cleaned 11,186 'nan' page_names
- Backfilled 30,361 NULL creator_id values (+9.1 points)

**Wave 2: Schema Compliance**
- Created persona for lola_reese_new
- Backfilled 198 wall_posts with creator_id
- Vault_matrix quality ratings (deferred to Phase 7)

**Wave 3: Template Population**
- Populated 6 empty critical tables with 170+ production templates
- Added 114 fresh captions for underperforming creators

**Result**: 65.9/100 → 93/100 (+27.1 points, Grade D → A)

### Current Issues

**1 CRITICAL Issue Remaining**:
- Vault_matrix quality ratings pipeline not yet implemented
- Workaround: Use performance_score and freshness_score for filtering

**3 WARNING Issues**:
- 94 unmapped legacy page_names (disconnected historical data)
- Minor data quality anomalies flagged for review in caption_integrity_issues
- Connection pooling not yet implemented (documented design ready)

---

## Performance Characteristics

### Query Performance Baselines

| Operation | Target | Current | Status |
|-----------|--------|---------|--------|
| Schedule Generation (full week) | < 2s | ~1.5s | ✅ PASS |
| get_creator_profile | < 100ms | ~50ms | ✅ PASS |
| get_top_captions | < 200ms | ~150ms | ✅ PASS |
| get_volume_config | < 150ms | ~120ms | ✅ PASS |
| save_schedule (7 days) | < 500ms | ~400ms | ✅ PASS |

### Index Coverage

**47 Strategic Indexes** deployed across all tables:

**High-Traffic Indexes**:
- `idx_caption_bank_freshness` - Caption selection (1000+ queries/day)
- `idx_creators_active` - Active creator filtering (500+ queries/day)
- `idx_schedule_items_creator_date` - Schedule lookups (300+ queries/day)
- `idx_message_performance_creator_type` - Performance analysis (200+ queries/day)

**Index Optimization**:
- All frequently-queried columns indexed
- Composite indexes for multi-column WHERE clauses
- Covering indexes for SELECT-only queries (no table lookups needed)

See [PERFORMANCE_TUNING.md](../operations/PERFORMANCE_TUNING.md) for complete index documentation and optimization guide.

---

## Related Documentation

### Operational Documentation
- **Deployment**: [DEPLOYMENT_PLAYBOOK.md](../operations/DEPLOYMENT_PLAYBOOK.md) - Complete deployment procedures
- **Backup/Recovery**: [BACKUP_RECOVERY.md](../operations/BACKUP_RECOVERY.md) - Multi-tier backup strategy
- **Performance Tuning**: [PERFORMANCE_TUNING.md](../operations/PERFORMANCE_TUNING.md) - Optimization guide (973 lines, 10/10 quality)
- **Monitoring**: [MONITORING_SETUP.md](../operations/MONITORING_SETUP.md) - Prometheus/Grafana setup

### Schema Documentation
- **PPV Structures**: [PPV_STRUCTURE_SCHEMA.md](./PPV_STRUCTURE_SCHEMA.md) - Advanced PPV, rotation, volume, saga, circuit breaker tables
- **Connection Pooling**: [CONNECTION_POOLING.md](./CONNECTION_POOLING.md) - Future connection pool architecture

### Database Audit
- **Quality Audit**: [../../database/audit/PERFECTION_AUDIT_REPORT_2025-12-12.md](../../database/audit/PERFECTION_AUDIT_REPORT_2025-12-12.md) - 93/100 quality score report
- **Integrity Report**: [../../database/audit/WAVE1_DATABASE_INTEGRITY_REPORT.md](../../database/audit/WAVE1_DATABASE_INTEGRITY_REPORT.md) - Wave 1 remediation

### API & MCP Documentation
- **MCP API Reference**: [../MCP_API_REFERENCE.md](../MCP_API_REFERENCE.md) - All 17 MCP tools with examples
- **Send Type Reference**: [../SEND_TYPE_REFERENCE.md](../SEND_TYPE_REFERENCE.md) - Complete 22-type taxonomy
- **Schedule Generator Blueprint**: [../SCHEDULE_GENERATOR_BLUEPRINT.md](../SCHEDULE_GENERATOR_BLUEPRINT.md) - Full architecture

---

## Schema Version History

| Version | Date | Changes | Migration Required |
|---------|------|---------|-------------------|
| 2.2.0 | 2025-12-17 | Comprehensive schema documentation created | No |
| 2.1.0 | 2025-12-16 | Dynamic volume system (8 modules) | Yes (migration 011) |
| 2.0.0 | 2025-12-12 | Database remediation (65.9 → 93 quality) | Yes (migrations 006-010) |
| 1.9.0 | 2025-12-10 | PPV structure validation added | No |
| 1.8.0 | 2025-12-08 | Multi-horizon fusion | Yes (migration 008) |
| 1.7.0 | 2025-12-05 | 22-type send taxonomy expansion | Yes (migration 007) |
| 1.6.0 | 2025-12-01 | Universal caption access model | Yes (migration 006) |

---

**Document Version**: 1.0
**Created**: 2025-12-17
**Next Review**: 2026-03-17

---

*Schema documentation for EROS Schedule Generator v2.2.0*
*For updates or corrections, contact: EROS Operations Team*
