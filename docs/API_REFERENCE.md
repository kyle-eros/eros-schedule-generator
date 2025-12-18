# EROS Schedule Generator API Reference

Complete documentation for all 16 MCP (Model Context Protocol) tools available in the EROS Database Server.

**Version**: 2.3.0
**MCP Server**: `mcp/eros_db_server.py`
**Protocol**: JSON-RPC 2.0 over stdin/stdout

---

## Table of Contents

### Creator Data
1. [get_creator_profile](#1-get_creator_profile)
2. [get_active_creators](#2-get_active_creators)
3. [get_persona_profile](#3-get_persona_profile)

### Performance & Analytics
4. [get_performance_trends](#4-get_performance_trends)
5. [get_content_type_rankings](#5-get_content_type_rankings)
6. [get_best_timing](#6-get_best_timing)

### Content & Captions
7. [get_top_captions](#7-get_top_captions)
8. [get_send_type_captions](#8-get_send_type_captions)
9. [get_vault_availability](#9-get_vault_availability)

### Send Type Configuration
10. [get_send_types](#10-get_send_types)
11. [get_send_type_details](#11-get_send_type_details)
12. [get_volume_config](#12-get_volume_config)
13. [get_volume_assignment](#13-get_volume_assignment)

### Channels
14. [get_channels](#14-get_channels)

### Schedule Operations
15. [save_schedule](#15-save_schedule)
16. [execute_query](#16-execute_query)

---

## Field Naming Standards

Understanding field naming conventions is critical for working with the EROS API.

### Send Type Identification

The system uses multiple fields to identify send types. Use the correct field to avoid errors:

| Field | Type | Usage | Status | Example |
|-------|------|-------|--------|---------|
| `send_type_key` | string | **PRIMARY** - Use for all logic and comparisons | ✅ Current | `"ppv_unlock"` |
| `send_type_id` | integer | Internal database foreign key only | ✅ Current | `5` |
| `item_type` | string | Legacy field from v1.x | ⚠️ Deprecated | `"ppv"` |

### Best Practices

**✅ DO**: Use `send_type_key` in all application logic
```python
if item["send_type_key"] == "ppv_unlock":
    # Correct approach
    process_ppv_unlock(item)
```

**❌ DON'T**: Use `send_type_id` (IDs can change)
```python
if item["send_type_id"] == 5:  # Wrong - fragile, IDs may change
    process_ppv(item)
```

**❌ DON'T**: Use `item_type` (deprecated field)
```python
if item["item_type"] == "ppv":  # Wrong - deprecated field
    process_ppv(item)
```

### Migration from v1.x

If migrating from version 1.x:
- Old `item_type = "ppv"` → New `send_type_key = "ppv_unlock"`
- Old `item_type = "bump"` → New `send_type_key = "bump_normal"`
- Old `item_type = "renewal"` → New `send_type_key = "renew_on_post"`

See [DEPRECATION_GUIDE.md](DEPRECATION_GUIDE.md) for complete migration paths.

### JSON Response Example

Typical schedule item response showing all fields:
```json
{
  "schedule_item_id": 12345,
  "send_type_key": "ppv_unlock",     // ✅ Use this
  "send_type_id": 5,                  // Internal only
  "item_type": "ppv",                 // ⚠️ Deprecated
  "caption": "...",
  "scheduled_time": "2025-12-23T14:30:00Z",
  "channel": "mass_message",
  "audience_target": "all_subscribers"
}
```

**Always access via**: `item["send_type_key"]`

---

## Creator Data Tools

### 1. get_creator_profile

Get comprehensive profile for a single creator including analytics, volume assignment, and top content types.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name to look up |

#### Returns

```json
{
  "creator": {
    "creator_id": "alexia",
    "page_name": "alexia",
    "display_name": "Alexia",
    "page_type": "paid",
    "subscription_price": 9.99,
    "timezone": "America/Los_Angeles",
    "creator_group": "premium",
    "current_active_fans": 2847,
    "current_total_earnings": 127450.00,
    "performance_tier": 1,
    "persona_type": "flirty_playful",
    "is_active": 1
  },
  "analytics_summary": {
    "creator_id": "alexia",
    "period_type": "30d",
    "total_sends": 342,
    "total_earnings": 18420.50,
    "avg_earnings_per_send": 53.86,
    "avg_purchase_rate": 0.24,
    "avg_view_rate": 0.68
  },
  "volume_assignment": {
    "volume_level": "High",
    "ppv_per_day": 5,
    "bump_per_day": 4,
    "assigned_at": "2025-11-15T10:30:00",
    "assigned_reason": "Tier 1 performer with high engagement"
  },
  "top_content_types": [
    {
      "content_type": "B/G",
      "rank": 1,
      "total_earnings": 8420.00,
      "avg_earnings": 68.20,
      "performance_tier": "TOP"
    }
  ]
}
```

#### Usage Example

```python
# Via MCP tool call
result = get_creator_profile(creator_id="alexia")

# Via natural language
"Show me the full profile for alexia"
```

---

### 2. get_active_creators

Get all active creators with performance metrics, volume assignments, and tier classification.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tier` | integer | No | Optional filter by performance_tier (1-5) |
| `page_type` | string | No | Optional filter by page_type ('paid' or 'free') |

#### Returns

```json
{
  "creators": [
    {
      "creator_id": "alexia",
      "page_name": "alexia",
      "display_name": "Alexia",
      "page_type": "paid",
      "subscription_price": 9.99,
      "timezone": "America/Los_Angeles",
      "creator_group": "premium",
      "current_active_fans": 2847,
      "current_total_earnings": 127450.00,
      "performance_tier": 1,
      "persona_type": "flirty_playful",
      "volume_level": "High",
      "ppv_per_day": 5,
      "bump_per_day": 4,
      "primary_tone": "playful",
      "emoji_frequency": "high",
      "slang_level": "medium"
    }
  ],
  "count": 37
}
```

#### Usage Example

```python
# All active creators
result = get_active_creators()

# Filter by tier
result = get_active_creators(tier=1)

# Filter by page type
result = get_active_creators(page_type="paid")

# Via natural language
"Show me all tier 1 paid creators"
```

---

### 3. get_persona_profile

Get creator persona including tone, emoji style, and slang level.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |

#### Returns

```json
{
  "creator": {
    "creator_id": "alexia",
    "page_name": "alexia",
    "display_name": "Alexia",
    "persona_type": "flirty_playful"
  },
  "persona": {
    "persona_id": 12,
    "primary_tone": "playful",
    "secondary_tone": "seductive",
    "emoji_frequency": "high",
    "favorite_emojis": "😈🔥💦😏💕",
    "slang_level": "medium",
    "avg_sentiment": 0.72,
    "avg_caption_length": 145,
    "last_analyzed": "2025-12-10T08:00:00",
    "created_at": "2025-01-15T10:00:00",
    "updated_at": "2025-12-10T08:00:00"
  },
  "voice_samples": {}
}
```

#### Usage Example

```python
result = get_persona_profile(creator_id="alexia")

# Via natural language
"What is alexia's persona profile?"
```

---

## Performance & Analytics Tools

### 4. get_performance_trends

Get saturation/opportunity scores and performance trends from volume_performance_tracking.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |
| `period` | string | No | Tracking period ('7d', '14d', or '30d'). Default '14d' |

#### Returns

```json
{
  "tracking_date": "2025-12-15",
  "tracking_period": "14d",
  "avg_daily_volume": 8.5,
  "total_messages_sent": 119,
  "avg_revenue_per_send": 42.30,
  "avg_view_rate": 0.68,
  "avg_purchase_rate": 0.24,
  "total_earnings": 5033.70,
  "revenue_per_send_trend": "stable",
  "view_rate_trend": "declining",
  "purchase_rate_trend": "stable",
  "earnings_volatility": 0.18,
  "saturation_score": 42,
  "opportunity_score": 68,
  "recommended_volume_delta": 1,
  "calculated_at": "2025-12-15T06:00:00"
}
```

#### Usage Example

```python
# Default 14-day period
result = get_performance_trends(creator_id="alexia")

# Specific period
result = get_performance_trends(creator_id="alexia", period="30d")

# Via natural language
"Show performance trends for alexia over 30 days"
```

---

### 5. get_content_type_rankings

Get ranked content types (TOP/MID/LOW/AVOID) from top_content_types analysis.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |

#### Returns

```json
{
  "rankings": [
    {
      "content_type": "B/G",
      "rank": 1,
      "send_count": 48,
      "total_earnings": 8420.00,
      "avg_earnings": 175.42,
      "avg_purchase_rate": 0.32,
      "avg_rps": 68.20,
      "performance_tier": "TOP",
      "recommendation": "Use frequently - highest performer",
      "confidence_score": 0.94
    },
    {
      "content_type": "Solo",
      "rank": 2,
      "send_count": 82,
      "total_earnings": 6240.00,
      "avg_earnings": 76.10,
      "avg_purchase_rate": 0.22,
      "avg_rps": 42.30,
      "performance_tier": "TOP",
      "recommendation": "Use frequently - strong performer",
      "confidence_score": 0.89
    }
  ],
  "top_types": ["B/G", "Solo", "Toys"],
  "mid_types": ["Teasing", "Shower"],
  "low_types": ["Outdoor"],
  "avoid_types": [],
  "analysis_date": "2025-12-10"
}
```

#### Usage Example

```python
result = get_content_type_rankings(creator_id="alexia")

# Via natural language
"What are the top content types for alexia?"
```

---

### 6. get_best_timing

Get optimal posting times based on historical mass_messages performance.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |
| `days_lookback` | integer | No | Number of days to analyze (default 30) |

#### Returns

```json
{
  "timezone": "America/Los_Angeles",
  "best_hours": [
    {
      "hour": 10,
      "avg_earnings": 68.42,
      "message_count": 32,
      "total_earnings": 2189.44
    },
    {
      "hour": 14,
      "avg_earnings": 62.15,
      "message_count": 28,
      "total_earnings": 1740.20
    },
    {
      "hour": 20,
      "avg_earnings": 58.30,
      "message_count": 35,
      "total_earnings": 2040.50
    }
  ],
  "best_days": [
    {
      "day_of_week": 2,
      "day_name": "Tuesday",
      "avg_earnings": 72.50,
      "message_count": 48,
      "total_earnings": 3480.00
    },
    {
      "day_of_week": 5,
      "day_name": "Friday",
      "avg_earnings": 68.20,
      "message_count": 52,
      "total_earnings": 3546.40
    }
  ],
  "analysis_period_days": 30
}
```

#### Usage Example

```python
# Default 30-day lookback
result = get_best_timing(creator_id="alexia")

# Custom lookback period
result = get_best_timing(creator_id="alexia", days_lookback=60)

# Via natural language
"What are the best posting times for alexia?"
```

---

## Content & Captions Tools

### 7. get_top_captions

Get top-performing captions for a creator with freshness scoring based on last usage.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |
| `caption_type` | string | No | Optional filter by caption_type |
| `content_type` | string | No | Optional filter by content type name |
| `min_performance` | float | No | Minimum performance_score threshold (default 40) |
| `limit` | integer | No | Maximum number of captions to return (default 20) |
| `send_type_key` | string | No | Optional send type key to filter by compatible caption types (e.g., 'ppv_unlock', 'bump_normal') |

#### Returns

```json
{
  "captions": [
    {
      "caption_id": 1547,
      "caption_text": "Good morning babes! Just filmed the HOTTEST solo vid... who wants to see? 🔥😈",
      "schedulable_type": "mass_message",
      "caption_type": "ppv_video_promo",
      "content_type_id": 3,
      "tone": "playful",
      "is_paid_page_only": 0,
      "performance_score": 87.5,
      "content_type_name": "Solo",
      "times_used": 4,
      "caption_total_earnings": 1240.50,
      "caption_avg_earnings": 310.13,
      "caption_avg_purchase_rate": 0.28,
      "caption_avg_view_rate": 0.72,
      "creator_performance_score": 89.2,
      "first_used_date": "2025-08-10",
      "last_used_date": "2025-11-05",
      "freshness_score": 92,
      "send_type_priority": 1
    }
  ],
  "count": 15,
  "send_type_key": "ppv_unlock"
}
```

#### Usage Example

```python
# Basic usage
result = get_top_captions(creator_id="alexia")

# Filter by send type
result = get_top_captions(
    creator_id="alexia",
    send_type_key="ppv_unlock",
    min_performance=60,
    limit=10
)

# Via natural language
"Show me top captions for alexia for ppv_unlock sends"
```

---

### 8. get_send_type_captions

Get captions compatible with a specific send type for a creator. Orders by priority from send_type_caption_requirements.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |
| `send_type_key` | string | Yes | The send type key to find compatible captions for |
| `min_freshness` | float | No | Minimum freshness score threshold (default 30) |
| `min_performance` | float | No | Minimum performance_score threshold (default 40) |
| `limit` | integer | No | Maximum number of captions to return (default 10) |

#### Returns

```json
{
  "captions": [
    {
      "caption_id": 2483,
      "caption_text": "Exclusive B/G content just for you... this one is WILD 😏💦",
      "schedulable_type": "mass_message",
      "caption_type": "ppv_video_promo",
      "content_type_id": 1,
      "tone": "seductive",
      "is_paid_page_only": 0,
      "performance_score": 92.3,
      "content_type_name": "B/G",
      "times_used": 2,
      "caption_total_earnings": 1840.00,
      "caption_avg_earnings": 920.00,
      "caption_avg_purchase_rate": 0.34,
      "caption_avg_view_rate": 0.78,
      "creator_performance_score": 94.1,
      "first_used_date": "2025-09-20",
      "last_used_date": "2025-10-15",
      "freshness_score": 88,
      "send_type_priority": 1
    }
  ],
  "count": 8,
  "send_type_key": "ppv_unlock"
}
```

#### Usage Example

```python
result = get_send_type_captions(
    creator_id="alexia",
    send_type_key="ppv_unlock",
    min_freshness=50,
    min_performance=70,
    limit=5
)

# Via natural language
"Get captions for alexia that work with bump_normal sends"
```

---

### 9. get_vault_availability

Get what content types are available in creator's vault.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |

#### Returns

```json
{
  "available_content": [
    {
      "vault_id": 142,
      "content_type_id": 1,
      "has_content": 1,
      "quantity_available": 12,
      "quality_rating": 4.5,
      "notes": "Recent B/G shoots from December",
      "updated_at": "2025-12-10T14:30:00",
      "type_name": "B/G",
      "type_category": "explicit",
      "description": "Boy/Girl content",
      "priority_tier": 1,
      "is_explicit": 1
    },
    {
      "vault_id": 143,
      "content_type_id": 3,
      "has_content": 1,
      "quantity_available": 24,
      "quality_rating": 4.8,
      "notes": "High-quality solo videos",
      "updated_at": "2025-12-08T10:00:00",
      "type_name": "Solo",
      "type_category": "explicit",
      "description": "Solo content",
      "priority_tier": 1,
      "is_explicit": 1
    }
  ],
  "content_types": ["B/G", "Solo", "Toys", "Teasing"],
  "total_items": 52
}
```

#### Usage Example

```python
result = get_vault_availability(creator_id="alexia")

# Via natural language
"What content is available in alexia's vault?"
```

---

## Send Type Configuration Tools

### 10. get_send_types

Get all send types with optional filtering by category and page_type.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `category` | string | No | Optional filter by category ('revenue', 'engagement', 'retention') |
| `page_type` | string | No | Optional filter by page_type ('paid' or 'free') |

#### Returns

```json
{
  "send_types": [
    {
      "send_type_id": 1,
      "send_type_key": "ppv_unlock",
      "category": "revenue",
      "display_name": "PPV Video",
      "description": "Pay-per-view video content sold via mass message",
      "purpose": "Direct revenue generation through premium video sales",
      "strategy": "High-quality content at optimal pricing with strategic timing",
      "requires_media": 1,
      "requires_flyer": 0,
      "requires_price": 1,
      "requires_link": 0,
      "has_expiration": 1,
      "default_expiration_hours": 48,
      "can_have_followup": 1,
      "followup_delay_minutes": 20,
      "page_type_restriction": "both",
      "caption_length": "medium",
      "emoji_recommendation": "moderate",
      "max_per_day": 4,
      "max_per_week": null,
      "min_hours_between": 3,
      "sort_order": 1,
      "is_active": 1,
      "created_at": "2025-11-01T10:00:00"
    }
  ],
  "count": 21
}
```

#### Usage Example

```python
# All send types
result = get_send_types()

# Filter by category
result = get_send_types(category="revenue")

# Filter by page type
result = get_send_types(page_type="paid")

# Via natural language
"Show me all revenue send types"
```

---

### 11. get_send_type_details

Get complete details for a single send type by key, including related caption type requirements.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `send_type_key` | string | Yes | The unique key for the send type (e.g., 'ppv_unlock', 'bump_normal') |

#### Returns

```json
{
  "send_type": {
    "send_type_id": 1,
    "send_type_key": "ppv_unlock",
    "category": "revenue",
    "display_name": "PPV Video",
    "description": "Pay-per-view video content sold via mass message",
    "purpose": "Direct revenue generation through premium video sales",
    "strategy": "High-quality content at optimal pricing with strategic timing",
    "requires_media": 1,
    "requires_flyer": 0,
    "requires_price": 1,
    "requires_link": 0,
    "has_expiration": 1,
    "default_expiration_hours": 48,
    "can_have_followup": 1,
    "followup_delay_minutes": 20,
    "page_type_restriction": "both",
    "caption_length": "medium",
    "emoji_recommendation": "moderate",
    "max_per_day": 4,
    "max_per_week": null,
    "min_hours_between": 3,
    "sort_order": 1,
    "is_active": 1,
    "created_at": "2025-11-01T10:00:00"
  },
  "caption_requirements": [
    {
      "caption_type": "ppv_video_promo",
      "priority": 1,
      "notes": "Primary caption type for video PPV promotions"
    },
    {
      "caption_type": "teasing_explicit",
      "priority": 2,
      "notes": "Alternative teasing approach"
    }
  ]
}
```

#### Usage Example

```python
result = get_send_type_details(send_type_key="ppv_unlock")

# Via natural language
"Show me details for the ppv_unlock send type"
```

---

### 12. get_volume_config

Get extended volume configuration including category breakdowns and type-specific limits.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |

#### Returns

```json
{
  "volume_level": "High",
  "ppv_per_day": 5,
  "bump_per_day": 4,
  "revenue_items_per_day": 6,
  "engagement_items_per_day": 5,
  "retention_items_per_day": 2,
  "bundle_per_week": 3,
  "game_per_week": 2,
  "followup_per_day": 4,
  "assigned_at": "2025-11-15T10:30:00",
  "assigned_reason": "Tier 1 performer with high engagement"
}
```

#### Usage Example

```python
result = get_volume_config(creator_id="alexia")

# Via natural language
"What is the volume configuration for alexia?"
```

---

### 13. get_volume_assignment

Get current volume assignment for a creator.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id or page_name |

#### Returns

```json
{
  "volume_level": "High",
  "ppv_per_day": 5,
  "bump_per_day": 4,
  "assigned_at": "2025-11-15T10:30:00",
  "assigned_by": "system",
  "assigned_reason": "Tier 1 performer with high engagement",
  "notes": "Adjusted based on saturation score analysis"
}
```

#### Usage Example

```python
result = get_volume_assignment(creator_id="alexia")

# Via natural language
"What is alexia's volume assignment?"
```

---

## Channels Tools

### 14. get_channels

Get all channels with optional filtering by targeting support.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `supports_targeting` | boolean | No | Optional filter by targeting support (true/false) |

#### Returns

```json
{
  "channels": [
    {
      "channel_id": 1,
      "channel_key": "mass_message",
      "display_name": "Mass Message",
      "description": "Direct message to multiple fans simultaneously",
      "supports_targeting": 1,
      "targeting_options": {
        "subscription_status": true,
        "spending_tier": true,
        "engagement_level": true
      },
      "platform_feature": "OnlyFans Mass Messages",
      "requires_manual_send": 0,
      "is_active": 1,
      "created_at": "2025-11-01T10:00:00"
    },
    {
      "channel_id": 2,
      "channel_key": "wall_post",
      "display_name": "Wall Post",
      "description": "Public post visible to all subscribers",
      "supports_targeting": 0,
      "targeting_options": null,
      "platform_feature": "OnlyFans Feed Post",
      "requires_manual_send": 0,
      "is_active": 1,
      "created_at": "2025-11-01T10:00:00"
    }
  ],
  "count": 2
}
```

#### Usage Example

```python
# All channels
result = get_channels()

# Only channels with targeting
result = get_channels(supports_targeting=True)

# Via natural language
"Show me all channels that support targeting"
```

---

## Schedule Operations Tools

### 15. save_schedule

Save generated schedule to database. Creates a schedule_template record and inserts all schedule_items.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `creator_id` | string | Yes | The creator_id for the schedule |
| `week_start` | string | Yes | ISO format date for week start (YYYY-MM-DD) |
| `items` | array | Yes | List of schedule items (see below for item structure) |

**Item Structure:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheduled_date` | string | Yes | ISO date string (YYYY-MM-DD) |
| `scheduled_time` | string | Yes | Time string HH:MM (24-hour) |
| `item_type` | string | Yes | Legacy type ('ppv', 'bump', etc.) |
| `channel` | string | Yes | Legacy 'mass_message' or 'wall_post' |
| `send_type_key` | string | No | Send type key (resolves to send_type_id) |
| `channel_key` | string | No | Channel key (resolves to channel_id) |
| `target_key` | string | No | Audience target key (resolves to target_id) |
| `caption_id` | integer | No | Caption ID from caption_bank |
| `caption_text` | string | No | Caption text |
| `suggested_price` | float | No | Price for PPV items |
| `content_type_id` | integer | No | Content type ID |
| `flyer_required` | integer | No | 0 or 1 |
| `priority` | integer | No | Priority (default 5) |
| `linked_post_url` | string | No | URL for linked wall post |
| `expires_at` | string | No | Expiration datetime |
| `followup_delay_minutes` | integer | No | Minutes to wait for followup |
| `media_type` | string | No | 'none', 'picture', 'gif', 'video', 'flyer' |
| `campaign_goal` | float | No | Revenue goal for the item |
| `parent_item_id` | integer | No | Parent item ID for followups |

#### Returns

```json
{
  "success": true,
  "template_id": 1547,
  "items_created": 49,
  "week_start": "2025-12-16",
  "week_end": "2025-12-22",
  "warnings": []
}
```

With warnings:

```json
{
  "success": true,
  "template_id": 1548,
  "items_created": 52,
  "week_start": "2025-12-16",
  "week_end": "2025-12-22",
  "warnings": [
    "Item 12: send_type 'bump_flyer' requires flyer but flyer_required=0",
    "Item 24: Unknown target_key 'invalid_target'"
  ]
}
```

#### Usage Example

```python
result = save_schedule(
    creator_id="alexia",
    week_start="2025-12-16",
    items=[
        {
            "scheduled_date": "2025-12-16",
            "scheduled_time": "10:00",
            "item_type": "ppv",
            "channel": "mass_message",
            "send_type_key": "ppv_unlock",
            "channel_key": "mass_message",
            "target_key": "all_paid_fans",
            "caption_id": 1547,
            "caption_text": "Good morning babes! Just filmed...",
            "suggested_price": 15.00,
            "content_type_id": 3,
            "media_type": "video",
            "expires_at": "2025-12-18T10:00:00"
        },
        # ... more items
    ]
)

# Via natural language
"Save this schedule to the database"
```

---

### 16. execute_query

Execute a read-only SQL SELECT query for custom analysis.

**SECURITY**: Only SELECT queries are allowed with comprehensive SQL injection protection.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | SQL SELECT query to execute |
| `params` | array | No | Optional list of parameters for the query |

#### Security Protections

- Blocks dangerous keywords (INSERT, UPDATE, DELETE, DROP, etc.)
- Detects comment injection attempts
- Enforces query complexity limits (max 5 JOINs, 3 subqueries)
- Limits result set size (max 10,000 rows)
- Auto-injects LIMIT if not present

#### Returns

```json
{
  "results": [
    {
      "creator_id": "alexia",
      "page_name": "alexia",
      "total_earnings": 127450.00
    },
    {
      "creator_id": "miss_alexa",
      "page_name": "miss_alexa",
      "total_earnings": 98320.00
    }
  ],
  "count": 2,
  "columns": ["creator_id", "page_name", "total_earnings"]
}
```

Error response:

```json
{
  "error": "Only SELECT queries are allowed for security reasons"
}
```

#### Usage Example

```python
# Simple query
result = execute_query(
    query="SELECT creator_id, page_name, current_total_earnings FROM creators WHERE performance_tier = 1 ORDER BY current_total_earnings DESC"
)

# With parameters
result = execute_query(
    query="SELECT * FROM caption_bank WHERE creator_id = ? AND performance_score > ?",
    params=["alexia", 80]
)

# Via natural language
"Run a query to find all tier 1 creators with earnings over $100k"
```

---

## Error Handling

All tools return errors in a consistent format:

```json
{
  "error": "Creator not found: invalid_creator"
}
```

Common error types:

| Error Message | Cause | Resolution |
|---------------|-------|------------|
| `Invalid creator_id: ...` | Creator ID validation failed | Use alphanumeric, underscore, hyphen only |
| `Creator not found: ...` | Creator doesn't exist in database | Verify creator_id with `get_active_creators` |
| `Invalid send_type_key: ...` | Send type key validation failed | Check valid send type keys with `get_send_types` |
| `Send type not found: ...` | Send type doesn't exist | Use valid send_type_key from send_types table |
| `Only SELECT queries are allowed` | Non-SELECT query attempted | Use SELECT queries only with `execute_query` |
| `Query contains disallowed keyword` | Dangerous SQL keyword detected | Remove INSERT/UPDATE/DELETE/etc. keywords |

---

## Data Types & Conventions

### Date/Time Formats

- **Dates**: `YYYY-MM-DD` (e.g., "2025-12-16")
- **Times**: `HH:MM` 24-hour format (e.g., "14:30")
- **Datetimes**: `YYYY-MM-DDTHH:MM:SS` ISO 8601 (e.g., "2025-12-16T14:30:00")

### Key Naming Conventions

- **creator_id**: Alphanumeric with underscore/hyphen (e.g., "alexia", "miss_alexa")
- **send_type_key**: Snake_case (e.g., "ppv_unlock", "bump_normal")
- **channel_key**: Snake_case (e.g., "mass_message", "wall_post")
- **target_key**: Snake_case (e.g., "all_paid_fans", "high_spenders")

### Enumerations

**page_type**: `"paid"` | `"free"`
**category**: `"revenue"` | `"engagement"` | `"retention"`
**volume_level**: `"Low"` | `"Mid"` | `"High"` | `"Ultra"`
**performance_tier**: `"TOP"` | `"MID"` | `"LOW"` | `"AVOID"`
**media_type**: `"none"` | `"picture"` | `"gif"` | `"video"` | `"flyer"`

---

## Rate Limits & Performance

- **Connection Timeout**: 30 seconds
- **Busy Timeout**: 5 seconds
- **Max Query Result Rows**: 10,000
- **Max Query JOINs**: 5
- **Max Query Subqueries**: 3

---

---

## Wave 5 Python Module API

### Quality Validation

#### validate_price_length_match

Validates that PPV caption length aligns with price point for maximum Revenue Per Send.

**Module**: `python.quality.price_validator`

**Signature**:
```python
def validate_price_length_match(caption: str, price: float) -> dict[str, Any]
```

**Parameters**:
- `caption` (str): The PPV caption text to validate
- `price` (float): The PPV price point (14.99, 19.69, 24.99, 29.99)

**Returns**:
```python
{
    "is_valid": bool,
    "price": float,
    "char_count": int,
    "optimal_range": tuple[int, int],
    "tier_name": str,
    "expected_rps": int,
    "mismatch_type": str | None,  # "too_short", "too_long", or None
    "expected_rps_loss": str | None,  # e.g., "82%"
    "severity": str | None,  # "CRITICAL", "HIGH", "MEDIUM", "LOW", or None
    "message": str,
    "recommendation": str,
    "alternative_prices": list[dict]
}
```

**Example**:
```python
from python.quality.price_validator import validate_price_length_match

result = validate_price_length_match("Short caption", 19.69)
# Returns: {"is_valid": False, "severity": "CRITICAL", "expected_rps_loss": "82%", ...}

result = validate_price_length_match("A" * 300, 19.69)
# Returns: {"is_valid": True, "expected_rps": 716, ...}
```

#### get_optimal_price_for_length

Determines optimal price point for a given caption length.

**Module**: `python.quality.price_validator`

**Signature**:
```python
def get_optimal_price_for_length(char_count: int) -> dict[str, Any]
```

**Returns**:
```python
{
    "price": float,
    "tier_name": str,
    "expected_rps": int,
    "optimal_range": tuple[int, int],
    "in_range": bool,
    "recommendation": str
}
```

#### validate_bundle_value_framing

Validates that bundle captions include proper value anchoring.

**Module**: `python.quality.bundle_validator`

**Signature**:
```python
def validate_bundle_value_framing(caption: str, price: float) -> dict
```

**Parameters**:
- `caption` (str): Bundle caption text to validate
- `price` (float): Bundle price in dollars

**Returns**:
```python
{
    "is_valid": bool,
    "has_value_anchor": bool,
    "has_price_mention": bool,
    "extracted_value": float | None,
    "bundle_price": float,
    "value_ratio": float | None,
    "severity": str | None,
    "message": str,
    "recommendation": str | None,
    "note": str | None,
    "missing": list[str]
}
```

**Example**:
```python
from python.quality.bundle_validator import validate_bundle_value_framing

result = validate_bundle_value_framing(
    "Get $500 worth of content for only $14.99!",
    14.99
)
# Returns: {"is_valid": True, "value_ratio": 33.36, ...}
```

#### validate_drip_schedule_outfits

Validates outfit consistency for drip content within shoots.

**Module**: `python.quality.drip_outfit_validator`

**Signature**:
```python
def validate_drip_schedule_outfits(
    schedule: list[dict],
    content_metadata: dict
) -> dict
```

**Parameters**:
- `schedule` (list[dict]): Schedule items with send_type_key, shoot_id, outfit_id
- `content_metadata` (dict): Metadata with shoots mapping

**Returns**:
```python
{
    "is_valid": bool,
    "total_drip_items": int,
    "shoots_checked": int,
    "inconsistencies": list[dict],
    "recommendation": str | None
}
```

### Pricing

#### adjust_price_by_confidence

Adjusts prices based on volume prediction confidence scores.

**Module**: `python.pricing.confidence_pricing`

**Signature**:
```python
def adjust_price_by_confidence(base_price: float, confidence: float) -> dict[str, float | str]
```

**Parameters**:
- `base_price` (float): Original price before adjustment
- `confidence` (float): Confidence score from 0.0 to 1.0

**Returns**:
```python
{
    "base_price": float,
    "confidence": float,
    "multiplier": float,
    "calculated_price": float,
    "suggested_price": float,
    "adjustment_reason": str
}
```

**Example**:
```python
from python.pricing.confidence_pricing import adjust_price_by_confidence

result = adjust_price_by_confidence(29.99, 0.65)
# Returns: {"suggested_price": 24.99, "multiplier": 0.85, ...}
```

#### FirstToTipPriceRotator

Rotates first-to-tip prices to prevent predictability.

**Module**: `python.pricing.first_to_tip`

**Signature**:
```python
class FirstToTipPriceRotator:
    def __init__(self, creator_id: str) -> None
    def get_next_price(self) -> int
    def get_price_with_context(self) -> dict[str, int | list[int] | str]
```

**Example**:
```python
from python.pricing.first_to_tip import FirstToTipPriceRotator

rotator = FirstToTipPriceRotator("creator_123")
price = rotator.get_next_price()  # Returns: 25, 30, 35, etc.

context = rotator.get_price_with_context()
# Returns: {"price": 30, "recent_prices": [25, 30], "variation_note": "..."}
```

### Orchestration

#### get_daily_flavor

Gets the flavor profile for a date based on day of week.

**Module**: `python.orchestration.daily_flavor`

**Signature**:
```python
def get_daily_flavor(date: datetime) -> dict
```

**Returns**:
```python
{
    "name": str,
    "emphasis": str,
    "boost_types": list[str],
    "boost_multiplier": float,
    "preferred_tone": str,
    "boost_categories": list[str],
    "day_of_week": int
}
```

**Example**:
```python
from datetime import datetime
from python.orchestration.daily_flavor import get_daily_flavor

flavor = get_daily_flavor(datetime(2025, 12, 15))  # Monday
# Returns: {"name": "Playful", "boost_types": ["game_post", ...], ...}
```

#### apply_labels_to_schedule

Assigns campaign labels to schedule items for feed organization.

**Module**: `python.orchestration.label_manager`

**Signature**:
```python
def apply_labels_to_schedule(schedule: list[dict[str, Any]]) -> list[dict[str, Any]]
```

**Parameters**:
- `schedule` (list[dict]): Schedule items with send_type keys

**Returns**: Modified schedule with 'label' key added to each item

**Example**:
```python
from python.orchestration.label_manager import apply_labels_to_schedule

schedule = [
    {"send_type": "game_post", "time": "10:00"},
    {"send_type": "ppv_unlock", "time": "14:00"}
]
labeled = apply_labels_to_schedule(schedule)
# schedule[0]["label"] == "GAMES"
# schedule[1]["label"] == "PPV"
```

#### ChatterContentSync

Generates content manifests for chatter team coordination.

**Module**: `python.orchestration.chatter_sync`

**Signature**:
```python
class ChatterContentSync:
    def generate_chatter_content_manifest(
        self,
        schedule: list[dict[str, Any]],
        creator_id: str
    ) -> dict[str, Any]
```

**Returns**:
```python
{
    "creator_id": str,
    "generated_at": str,
    "total_items": int,
    "manifest_by_date": dict[str, list[dict]],
    "manifest_all": list[dict],
    "chatter_instructions": list[str]
}
```

### Analytics

#### DailyStatisticsAnalyzer

Generates automated daily performance digests with recommendations.

**Module**: `python.analytics.daily_digest`

**Signature**:
```python
class DailyStatisticsAnalyzer:
    def __init__(self, creator_id: str) -> None
    def generate_daily_digest(
        self,
        performance_data: list[dict]
    ) -> dict[str, Any]
```

**Returns**:
```python
{
    "date": str,
    "creator_id": str,
    "timeframe_summaries": dict[int, dict],
    "patterns": dict[str, Any],
    "recommendations": list[dict[str, Any]],
    "action_items": list[str],
    "top_performers": list[dict]
}
```

**Example**:
```python
from python.analytics.daily_digest import DailyStatisticsAnalyzer

analyzer = DailyStatisticsAnalyzer("alexia")
data = [
    {"date": "2025-01-15", "earnings": 5200.0, "content_type": "lingerie"},
    {"date": "2025-01-14", "earnings": 4800.0, "content_type": "bts"}
]
digest = analyzer.generate_daily_digest(data)
# Returns comprehensive analysis with patterns and recommendations
```

---

## Version History

### v2.3.0 (Current)
- Removed audience targeting system (16 tools)
- Documentation cleanup and version alignment

### v2.2.0
- Complete MCP server modularization (17 focused modules)
- Domain model architecture with frozen/slotted dataclasses
- Send type registry with O(1) lookups
- Configuration management with YAML + env overrides
- Enhanced type safety and modern Python 3.11+ patterns
- Custom exception hierarchy with error codes
- Structured logging infrastructure
- Input validation decorators

### v2.0.4
- Added `get_send_type_captions` tool
- Enhanced `get_top_captions` with send_type_key filtering
- Added `get_volume_config` for extended volume configuration
- Improved error messages and validation

### v2.0.0
- Initial MCP implementation with 11 core tools
- Added Wave 2 tools (6 new tools)
- Comprehensive security hardening
- JSON-RPC 2.0 protocol support

---

## Support & Documentation

- **User Guide**: [USER_GUIDE.md](USER_GUIDE.md)
- **Send Type Reference**: [SEND_TYPE_REFERENCE.md](SEND_TYPE_REFERENCE.md)
- **Architecture Blueprint**: [SCHEDULE_GENERATOR_BLUEPRINT.md](SCHEDULE_GENERATOR_BLUEPRINT.md)
- **Getting Started**: [GETTING_STARTED.md](GETTING_STARTED.md)

---

*EROS Schedule Generator v2.3.0*
*MCP Server Documentation*
*Last Updated: December 17, 2025*
