# EROS MCP API Reference

Comprehensive technical documentation for the EROS Database Server MCP (Model Context Protocol) implementation.

**Version**: 2.2.0
**Protocol**: JSON-RPC 2.0 over stdin/stdout
**Server**: `mcp/eros_db_server.py`
**Type Definitions**: `mcp/types.py`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tool Registry](#tool-registry)
4. [Creator Data Tools](#creator-data-tools)
5. [Performance & Analytics Tools](#performance--analytics-tools)
6. [Content & Caption Tools](#content--caption-tools)
7. [Send Type Configuration Tools](#send-type-configuration-tools)
8. [Targeting & Channel Tools](#targeting--channel-tools)
9. [Schedule Operations Tools](#schedule-operations-tools)
10. [Query Execution Tool](#query-execution-tool)
11. [Error Handling](#error-handling)
12. [Security](#security)
13. [Type System](#type-system)

---

## Overview

The EROS MCP Server provides 17 tools for interacting with the EROS Schedule Generator database. All tools follow a consistent pattern:

- **Input Validation**: All parameters validated before database operations
- **Error Handling**: Consistent error response format
- **Type Safety**: TypedDict definitions for all return types
- **Security**: Comprehensive SQL injection protection
- **Performance**: Connection pooling and query optimization

### Protocol Specification

The server implements the Model Context Protocol (MCP) using JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_creator_profile",
    "arguments": {
      "creator_id": "alexia"
    }
  },
  "id": 1
}
```

Response format:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{...json response...}"
      }
    ]
  },
  "id": 1
}
```

---

## Architecture

### Module Structure

```
mcp/
├── eros_db_server.py          # Main server entry point
├── types.py                   # TypedDict definitions (NEW)
├── connection.py              # Database connection management
├── protocol.py                # JSON-RPC protocol handler
├── server.py                  # MCP server implementation
├── tools/
│   ├── base.py               # Tool decorator and registry
│   ├── creator.py            # Creator data tools (4 tools)
│   ├── caption.py            # Caption tools (2 tools)
│   ├── performance.py        # Performance tools (4 tools)
│   ├── send_types.py         # Send type tools (3 tools)
│   ├── targeting.py          # Targeting tools (2 tools)
│   ├── schedule.py           # Schedule tools (1 tool)
│   └── query.py              # Query tool (1 tool)
└── utils/
    ├── helpers.py            # Helper functions
    └── security.py           # Input validation
```

### Tool Registration Pattern

All tools use the `@mcp_tool` decorator for automatic registration:

```python
from mcp.tools.base import mcp_tool

@mcp_tool(
    name="tool_name",
    description="Tool description",
    schema={
        "type": "object",
        "properties": {...},
        "required": [...]
    }
)
def tool_function(param: str) -> dict:
    """
    Function docstring in Google style.

    Args:
        param: Parameter description.

    Returns:
        Return value description.

    Raises:
        ValueError: Error conditions.
    """
    pass
```

### Database Connection Management

The server uses context managers for safe connection handling:

```python
from mcp.connection import db_connection, get_db_connection

# Context manager (auto-close)
with db_connection() as conn:
    cursor = conn.execute("SELECT ...", params)

# Manual management
conn = get_db_connection()
try:
    # ... operations ...
finally:
    conn.close()
```

**Connection Configuration**:
- **Timeout**: 30 seconds
- **Busy Timeout**: 5 seconds
- **Row Factory**: `sqlite3.Row` (dictionary access)
- **Check Same Thread**: Disabled for MCP compatibility

---

## Tool Registry

### get_all_tools()

Returns metadata for all registered tools in MCP format.

**Location**: `mcp/tools/base.py`

**Signature**:
```python
def get_all_tools() -> list[dict[str, Any]]
```

**Returns**:
```python
[
    {
        "name": "tool_name",
        "description": "Tool description",
        "inputSchema": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
]
```

### dispatch_tool()

Dispatches tool calls to registered handlers.

**Location**: `mcp/tools/base.py`

**Signature**:
```python
def dispatch_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]
```

**Raises**:
- `KeyError`: If tool not found
- `TypeError`: If arguments invalid

---

## Creator Data Tools

### get_creator_profile

Get comprehensive profile for a single creator including analytics, volume assignment, and top content types.

**Module**: `mcp.tools.creator`
**Function**: `get_creator_profile(creator_id: str) -> dict[str, Any]`
**Return Type**: `CreatorProfile`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen; max 100 chars |

#### Implementation Details

1. **Input Validation**: Uses `validate_creator_id()` from security module
2. **Creator Resolution**: Accepts both `creator_id` and `page_name`
3. **Data Aggregation**: Joins multiple tables:
   - `creators` (base info)
   - `creator_analytics_summary` (30-day metrics)
   - `top_content_types` (most recent analysis)
4. **Volume Calculation**: Calls `get_volume_config()` for dynamic volume
5. **Connection Management**: Manual with try-finally

#### Return Structure

```python
{
    "creator": CreatorInfo,          # Basic creator data
    "analytics_summary": AnalyticsSummary | None,  # 30d metrics
    "volume_assignment": VolumeAssignment,  # Volume config
    "top_content_types": List[ContentTypeRanking]  # Performance tiers
}
```

#### Error Responses

| Error | Cause | HTTP Equivalent |
|-------|-------|-----------------|
| `Invalid creator_id: ...` | Validation failed | 400 Bad Request |
| `Creator not found: ...` | ID doesn't exist | 404 Not Found |

#### Example Usage

```python
# Python call
result = get_creator_profile(creator_id="alexia")

# Natural language (via Claude)
"Show me the full profile for alexia"
```

---

### get_active_creators

Get all active creators with performance metrics, volume assignments, and tier classification.

**Module**: `mcp.tools.creator`
**Function**: `get_active_creators(tier: Optional[int] = None, page_type: Optional[str] = None) -> dict[str, Any]`
**Return Type**: `ActiveCreatorsResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `tier` | integer | No | Must be 1-5 |
| `page_type` | string | No | Must be "paid" or "free" |

#### Implementation Details

1. **Filtering**: Optional tier and page_type filters
2. **Data Join**: Joins `creators` and `creator_personas` tables
3. **Ordering**: Sorted by `current_total_earnings DESC`
4. **Active Filter**: Only returns creators where `is_active = 1`
5. **Connection Management**: Context manager (`db_connection()`)

#### SQL Query Structure

```sql
SELECT
    c.*,
    cp.primary_tone,
    cp.emoji_frequency,
    cp.slang_level
FROM creators c
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
WHERE c.is_active = 1
    [AND c.performance_tier = ?]
    [AND c.page_type = ?]
ORDER BY c.current_total_earnings DESC
```

#### Return Structure

```python
{
    "creators": List[CreatorListItem],  # List of creator records
    "count": int                        # Total count
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `page_type must be 'paid' or 'free'` | Invalid page_type value |

---

### get_persona_profile

Get creator persona including tone, emoji style, and slang level.

**Module**: `mcp.tools.creator`
**Function**: `get_persona_profile(creator_id: str) -> dict[str, Any]`
**Return Type**: `PersonaProfile`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |

#### Implementation Details

1. **Creator Resolution**: Resolves creator_id or page_name
2. **Persona Lookup**: Retrieves from `creator_personas` table
3. **Voice Samples**: Currently returns empty dict (table not yet implemented)
4. **Connection Management**: Manual with try-finally

#### Return Structure

```python
{
    "creator": {
        "creator_id": str,
        "page_name": str,
        "display_name": str,
        "persona_type": str
    },
    "persona": PersonaData | None,
    "voice_samples": {}  # Reserved for future use
}
```

#### Persona Fields

| Field | Type | Description |
|-------|------|-------------|
| `persona_id` | int | Primary key |
| `primary_tone` | str | Main personality tone |
| `secondary_tone` | str | Secondary tone |
| `emoji_frequency` | str | "low" / "medium" / "high" |
| `favorite_emojis` | str | Common emoji string |
| `slang_level` | str | "low" / "medium" / "high" |
| `avg_sentiment` | float | Sentiment score 0-1 |
| `avg_caption_length` | int | Average characters |
| `last_analyzed` | str | Last analysis timestamp |

---

### get_vault_availability

Get what content types are available in creator's vault.

**Module**: `mcp.tools.creator`
**Function**: `get_vault_availability(creator_id: str) -> dict[str, Any]`
**Return Type**: `VaultAvailabilityResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |

#### Implementation Details

1. **Creator Resolution**: Uses `resolve_creator_id()` helper
2. **Vault Query**: Joins `vault_matrix` and `content_types` tables
3. **Filtering**: Only returns items where `has_content = 1`
4. **Ordering**: By `priority_tier ASC`, then `quantity_available DESC`
5. **Aggregation**: Calculates total available items

#### SQL Query Structure

```sql
SELECT
    vm.*,
    ct.type_name,
    ct.type_category,
    ct.description,
    ct.priority_tier,
    ct.is_explicit
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ? AND vm.has_content = 1
ORDER BY ct.priority_tier ASC, vm.quantity_available DESC
```

#### Return Structure

```python
{
    "available_content": List[VaultItem],  # Detailed vault entries
    "content_types": List[str],            # Simple type names
    "total_items": int                     # Sum of quantities
}
```

---

## Performance & Analytics Tools

### get_performance_trends

Get saturation/opportunity scores and performance trends from volume_performance_tracking.

**Module**: `mcp.tools.performance`
**Function**: `get_performance_trends(creator_id: str, period: str = "14d") -> dict[str, Any]`
**Return Type**: `PerformanceTrends`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |
| `period` | string | No | Must be "7d", "14d", or "30d" |

#### Implementation Details

1. **Period Validation**: Restricts to 7d/14d/30d
2. **Creator Resolution**: Uses `resolve_creator_id()` helper
3. **Latest Record**: Returns most recent tracking record for period
4. **Null Handling**: Returns None values if no data found
5. **Connection Management**: Manual with try-finally

#### Saturation & Opportunity Scores

**Saturation Score** (0-100):
- 0-30: Low saturation, can increase volume
- 31-60: Moderate saturation, stable
- 61-100: High saturation, reduce volume

**Opportunity Score** (0-100):
- 0-30: Low opportunity, content/targeting issues
- 31-60: Moderate opportunity
- 61-100: High opportunity, expand volume

#### Return Structure

```python
{
    "tracking_date": str,               # Date of analysis
    "tracking_period": str,             # "7d" | "14d" | "30d"
    "avg_daily_volume": float,          # Messages per day
    "total_messages_sent": int,         # Total in period
    "avg_revenue_per_send": float,      # Average $ per message
    "avg_view_rate": float,             # 0-1 (fraction viewed)
    "avg_purchase_rate": float,         # 0-1 (fraction purchased)
    "total_earnings": float,            # Total $ earned
    "revenue_per_send_trend": str | None,    # "increasing" | "stable" | "declining"
    "view_rate_trend": str | None,           # "increasing" | "stable" | "declining"
    "purchase_rate_trend": str | None,       # "increasing" | "stable" | "declining"
    "earnings_volatility": float | None,     # Coefficient of variation
    "saturation_score": float | None,        # 0-100
    "opportunity_score": float | None,       # 0-100
    "recommended_volume_delta": int | None,  # +/- suggested change
    "calculated_at": str                     # Calculation timestamp
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `period must be '7d', '14d', or '30d'` | Invalid period parameter |
| `Creator not found: ...` | Invalid creator_id |

---

### get_content_type_rankings

Get ranked content types (TOP/MID/LOW/AVOID) from top_content_types analysis.

**Module**: `mcp.tools.performance`
**Function**: `get_content_type_rankings(creator_id: str) -> dict[str, Any]`
**Return Type**: `ContentTypeRankingsResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |

#### Implementation Details

1. **Latest Analysis**: Queries most recent `analysis_date` for creator
2. **Ranking Order**: Sorted by `rank ASC`
3. **Tier Categorization**: Groups by `performance_tier` field
4. **Connection Management**: Manual with try-finally

#### Performance Tiers

| Tier | Criteria | Recommendation |
|------|----------|----------------|
| **TOP** | Avg earnings > $60, confidence > 0.75 | Use frequently |
| **MID** | Avg earnings $30-60, confidence > 0.60 | Use regularly |
| **LOW** | Avg earnings $15-30 or low confidence | Use sparingly |
| **AVOID** | Avg earnings < $15 or very low confidence | Avoid |

#### Return Structure

```python
{
    "rankings": List[ContentTypeRanking],  # Full ranking data
    "top_types": List[str],                # Type names only
    "mid_types": List[str],                # Type names only
    "low_types": List[str],                # Type names only
    "avoid_types": List[str],              # Type names only
    "analysis_date": str                   # Date of analysis
}
```

#### ContentTypeRanking Fields

| Field | Type | Description |
|-------|------|-------------|
| `content_type` | str | Content type name |
| `rank` | int | 1-based ranking |
| `send_count` | int | Number of sends |
| `total_earnings` | float | Total $ earned |
| `avg_earnings` | float | Average $ per send |
| `avg_purchase_rate` | float | Purchase rate 0-1 |
| `avg_rps` | float | Revenue per send |
| `performance_tier` | str | TOP/MID/LOW/AVOID |
| `recommendation` | str | Usage guidance |
| `confidence_score` | float | 0-1 confidence |

---

### get_best_timing

Get optimal posting times based on historical mass_messages performance.

**Module**: `mcp.tools.performance`
**Function**: `get_best_timing(creator_id: str, days_lookback: int = 30) -> dict[str, Any]`
**Return Type**: `BestTimingResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |
| `days_lookback` | integer | No | Default 30 days |

#### Implementation Details

1. **Creator Resolution**: Resolves and retrieves timezone
2. **Hour Analysis**: Groups by `sending_hour` (0-23)
3. **Day Analysis**: Groups by `sending_day_of_week` (0-6)
4. **Filters**: Only PPV messages with earnings > 0
5. **Ordering**: By `avg_earnings DESC`
6. **Day Names**: Maps day_of_week integers to names

#### SQL Query Structure

```sql
-- Best Hours
SELECT
    sending_hour AS hour,
    AVG(earnings) AS avg_earnings,
    COUNT(*) AS message_count,
    SUM(earnings) AS total_earnings
FROM mass_messages
WHERE creator_id = ?
    AND message_type = 'ppv'
    AND sending_time >= ?
    AND earnings > 0
GROUP BY sending_hour
ORDER BY avg_earnings DESC

-- Best Days
SELECT
    sending_day_of_week AS day_of_week,
    AVG(earnings) AS avg_earnings,
    COUNT(*) AS message_count,
    SUM(earnings) AS total_earnings
FROM mass_messages
WHERE creator_id = ?
    AND message_type = 'ppv'
    AND sending_time >= ?
    AND earnings > 0
GROUP BY sending_day_of_week
ORDER BY avg_earnings DESC
```

#### Return Structure

```python
{
    "timezone": str,                    # Creator timezone
    "best_hours": List[TimingHour],     # Hour performance
    "best_days": List[TimingDay],       # Day performance
    "analysis_period_days": int         # Lookback period
}
```

#### Day of Week Mapping

| day_of_week | day_name |
|-------------|----------|
| 0 | Sunday |
| 1 | Monday |
| 2 | Tuesday |
| 3 | Wednesday |
| 4 | Thursday |
| 5 | Friday |
| 6 | Saturday |

---

### get_volume_assignment

Get current volume assignment for a creator (DEPRECATED).

**Module**: `mcp.tools.performance`
**Function**: `get_volume_assignment(creator_id: str) -> dict[str, Any]`
**Status**: DEPRECATED in favor of `get_volume_config()`

#### Deprecation Notice

This function now calls `get_volume_config()` internally and returns a subset of fields for backward compatibility. The response includes a deprecation warning:

```python
{
    "_deprecated": True,
    "_message": "get_volume_assignment is deprecated. Use get_volume_config() for dynamic calculation with full metadata."
}
```

#### Migration Path

**Old Code**:
```python
result = get_volume_assignment(creator_id="alexia")
ppv_per_day = result["ppv_per_day"]
```

**New Code**:
```python
result = get_volume_config(creator_id="alexia")
ppv_per_day = result["ppv_per_day"]  # Still available
revenue_per_day = result["revenue_items_per_day"]  # Enhanced field
```

---

## Content & Caption Tools

### get_top_captions

Get top-performing captions for a creator with freshness scoring based on last usage.

**Module**: `mcp.tools.caption`
**Function**: `get_top_captions(...) -> dict[str, Any]`
**Return Type**: `TopCaptionsResponse`

#### Parameters

| Name | Type | Required | Validation | Default |
|------|------|----------|------------|---------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen | - |
| `caption_type` | string | No | - | None |
| `content_type` | string | No | - | None |
| `min_performance` | float | No | - | 40.0 |
| `limit` | integer | No | - | 20 |
| `send_type_key` | string | No | Alphanumeric, underscore, hyphen | None |

#### Implementation Details

1. **Input Validation**: Validates both creator_id and send_type_key
2. **Send Type Resolution**: If send_type_key provided, resolves to send_type_id
3. **Caption Requirements**: Joins with `send_type_caption_requirements` if send_type_key
4. **Freshness Calculation**: `100 - (days_since_last_use * 2)`, capped at 0-100
5. **Ordering**: By priority (if send_type), then freshness DESC, then performance DESC
6. **Performance Filter**: Only returns captions with `performance_score >= min_performance`

#### Freshness Score Algorithm

```python
if last_used_date is None:
    freshness_score = 100  # Never used = maximum freshness
else:
    days_since = (today - last_used_date).days
    freshness_score = max(0, min(100, 100 - (days_since * 2)))
```

**Examples**:
- Never used: 100
- Used 10 days ago: 80
- Used 30 days ago: 40
- Used 50+ days ago: 0

#### SQL Query Structure (with send_type_key)

```sql
SELECT
    cb.*,
    ct.type_name AS content_type_name,
    ccp.*,
    stcr.priority AS send_type_priority,
    CASE
        WHEN ccp.last_used_date IS NULL THEN 100
        ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
    END AS freshness_score
FROM caption_bank cb
INNER JOIN send_type_caption_requirements stcr
    ON cb.caption_type = stcr.caption_type
    AND stcr.send_type_id = ?
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN caption_creator_performance ccp
    ON cb.caption_id = ccp.caption_id
    AND ccp.creator_id = ?
WHERE cb.is_active = 1
    AND cb.performance_score >= ?
    [AND cb.caption_type = ?]
    [AND ct.type_name = ?]
ORDER BY stcr.priority ASC, freshness_score DESC, cb.performance_score DESC
LIMIT ?
```

#### Return Structure

```python
{
    "captions": List[CaptionData],  # Caption list with scoring
    "count": int,                   # Number returned
    "send_type_key": str | None     # Echo send_type if provided
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `Invalid creator_id: ...` | Creator ID validation failed |
| `Invalid send_type_key: ...` | Send type key validation failed |
| `Creator not found: ...` | Creator doesn't exist |
| `Send type not found: ...` | Invalid send_type_key |

---

### get_send_type_captions

Get captions compatible with a specific send type for a creator. Orders by priority from send_type_caption_requirements.

**Module**: `mcp.tools.caption`
**Function**: `get_send_type_captions(...) -> dict[str, Any]`
**Return Type**: `SendTypeCaptionsResponse`

#### Parameters

| Name | Type | Required | Validation | Default |
|------|------|----------|------------|---------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen | - |
| `send_type_key` | string | Yes | Alphanumeric, underscore, hyphen | - |
| `min_freshness` | float | No | - | 30.0 |
| `min_performance` | float | No | - | 40.0 |
| `limit` | integer | No | - | 10 |

#### Implementation Details

1. **Input Validation**: Validates creator_id and send_type_key
2. **Send Type Resolution**: Resolves send_type_key to send_type_id
3. **Caption Filtering**: Filters by both freshness and performance thresholds
4. **Priority Ordering**: Uses priority from `send_type_caption_requirements`
5. **Freshness Filtering**: Applies freshness threshold in WHERE clause

#### Difference from get_top_captions

| Feature | get_top_captions | get_send_type_captions |
|---------|------------------|------------------------|
| send_type_key | Optional | Required |
| Freshness threshold | No filter | min_freshness filter |
| Default limit | 20 | 10 |
| Primary use | Exploration | Specific send type |

#### Return Structure

```python
{
    "captions": List[CaptionData],  # Filtered caption list
    "count": int,                   # Number returned
    "send_type_key": str            # Echo send_type_key
}
```

#### Error Responses

Same as `get_top_captions` plus:
- `Send type not found: ...` (Always checked, never optional)

---

## Send Type Configuration Tools

### get_send_types

Get all send types with optional filtering by category and page_type.

**Module**: `mcp.tools.send_types`
**Function**: `get_send_types(category: Optional[str] = None, page_type: Optional[str] = None) -> dict[str, Any]`
**Return Type**: `SendTypesResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `category` | string | No | Must be "revenue", "engagement", or "retention" |
| `page_type` | string | No | Must be "paid" or "free" |

#### Implementation Details

1. **Active Filter**: Only returns send types where `is_active = 1`
2. **Category Filter**: Exact match on category field
3. **Page Type Filter**: Matches `page_type_restriction` or "both"
4. **Ordering**: By `sort_order ASC`
5. **Connection Management**: Context manager

#### Page Type Restriction Logic

```python
if page_type == "paid":
    # Returns send types where page_type_restriction IN ("paid", "both")
if page_type == "free":
    # Returns send types where page_type_restriction IN ("free", "both")
```

#### SQL Query Structure

```sql
SELECT
    send_type_id,
    send_type_key,
    category,
    display_name,
    description,
    purpose,
    strategy,
    requires_media,
    requires_flyer,
    requires_price,
    requires_link,
    has_expiration,
    default_expiration_hours,
    can_have_followup,
    followup_delay_minutes,
    page_type_restriction,
    caption_length,
    emoji_recommendation,
    max_per_day,
    max_per_week,
    min_hours_between,
    sort_order,
    is_active,
    created_at
FROM send_types
WHERE is_active = 1
    [AND category = ?]
    [AND (page_type_restriction = ? OR page_type_restriction = 'both')]
ORDER BY sort_order ASC
```

#### Return Structure

```python
{
    "send_types": List[SendTypeData],  # Complete send type records
    "count": int                       # Total count
}
```

#### Send Type Categories

| Category | Count | Purpose |
|----------|-------|---------|
| **revenue** | 9 | Direct revenue generation |
| **engagement** | 9 | Engagement and discovery |
| **retention** | 4 | Subscriber retention |

**Total**: 22 send types (as of v2.1)

#### Error Responses

| Error | Cause |
|-------|-------|
| `category must be 'revenue', 'engagement', or 'retention'` | Invalid category |
| `page_type must be 'paid' or 'free'` | Invalid page_type |

---

### get_send_type_details

Get complete details for a single send type by key, including related caption type requirements.

**Module**: `mcp.tools.send_types`
**Function**: `get_send_type_details(send_type_key: str) -> dict[str, Any]`
**Return Type**: `SendTypeDetailsResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `send_type_key` | string | Yes | Alphanumeric, underscore, hyphen; max 50 chars |

#### Implementation Details

1. **Input Validation**: Uses `validate_key_input()` from security module
2. **Send Type Lookup**: Retrieves complete send type record
3. **Caption Requirements**: Joins with `send_type_caption_requirements`
4. **Priority Ordering**: Caption requirements sorted by priority ASC
5. **Connection Management**: Manual with try-finally

#### Caption Requirements Join

The `send_type_caption_requirements` table maps send types to compatible caption types with priority:

| Field | Type | Description |
|-------|------|-------------|
| `caption_type` | str | Caption type identifier |
| `priority` | int | 1 = highest priority |
| `notes` | str | Usage notes |

**Example**:
```python
# ppv_unlock caption requirements
[
    {"caption_type": "ppv_video_promo", "priority": 1, "notes": "Primary"},
    {"caption_type": "teasing_explicit", "priority": 2, "notes": "Alternative"}
]
```

#### Return Structure

```python
{
    "send_type": SendTypeData,              # Complete send type record
    "caption_requirements": List[CaptionRequirement]  # Compatible captions
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `Invalid send_type_key: ...` | Validation failed |
| `Send type not found: ...` | Key doesn't exist |

---

### get_volume_config

Get extended volume configuration including category breakdowns (revenue/engagement/retention items per day) and type-specific limits.

**Module**: `mcp.tools.send_types`
**Function**: `get_volume_config(creator_id: str) -> dict[str, Any]`
**Return Type**: `VolumeConfigResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |

#### Implementation Details

This is the most complex tool in the MCP server, integrating multiple calculation modules:

1. **Creator Resolution**: Resolves creator_id and retrieves fan_count, page_type
2. **Score Retrieval**: Attempts to get scores from `volume_performance_tracking`
3. **Fallback Calculation**: If no tracking data, calculates on-demand from `mass_messages`
4. **Default Scores**: If no data at all, uses neutral scores (50/50)
5. **Performance Context**: Builds `PerformanceContext` object
6. **Optimized Calculation**: Attempts full 8-module optimized volume calculation
7. **Dynamic Fallback**: Falls back to basic dynamic calculation if optimized fails
8. **Type-Specific Limits**: Calculates bundle/game/followup limits from tier

#### Calculation Pipeline

```
1. Creator Data Retrieval
   ↓
2. Score Source Selection
   ├─ volume_performance_tracking (preferred)
   ├─ calculate_scores_from_db() (fallback)
   └─ default values (50/50)
   ↓
3. Performance Context Creation
   ↓
4. Volume Calculation Attempt
   ├─ calculate_optimized_volume() (full pipeline)
   │  ├─ Base tier calculation
   │  ├─ Multi-horizon fusion
   │  ├─ Confidence dampening
   │  ├─ DOW distribution
   │  ├─ Elasticity bounds
   │  ├─ Content weighting
   │  ├─ Caption pool check
   │  └─ Prediction tracking
   │  ↓
   └─ calculate_dynamic_volume() (fallback)
      ↓
5. Type-Specific Limit Calculation
   ↓
6. Response Assembly
```

#### Optimized Volume Result Fields

When `calculation_source == "optimized"`, the response includes:

| Field Group | Fields | Description |
|-------------|--------|-------------|
| **Legacy** | `volume_level`, `ppv_per_day`, `bump_per_day` | Backward compatibility |
| **Categories** | `revenue_items_per_day`, `engagement_items_per_day`, `retention_items_per_day` | Daily targets |
| **Type Limits** | `bundle_per_week`, `game_per_week`, `followup_per_day` | Send type limits |
| **Weekly Distribution** | `weekly_distribution` | 7-element array (Mon-Sun) |
| **Content Allocation** | `content_allocations` | Dict of content_type → count |
| **Confidence** | `confidence_score`, `is_high_confidence` | Prediction confidence |
| **Elasticity** | `elasticity_capped`, `adjustments_applied` | Bound enforcement |
| **Warnings** | `caption_warnings`, `has_warnings` | Caption pool issues |
| **Multi-Horizon** | `fused_saturation`, `fused_opportunity`, `divergence_detected` | Fused scores |
| **DOW** | `dow_multipliers_used` | Day-of-week adjustments |
| **Tracking** | `prediction_id`, `message_count` | Audit trail |

#### Type-Specific Limit Calculation

```python
# Based on tier
tier_map = {
    "Low": {"bundle": 1, "game": 1, "followup": 2},
    "Mid": {"bundle": 2, "game": 2, "followup": 3},
    "High": {"bundle": 3, "game": 2, "followup": 4},
    "Ultra": {"bundle": 4, "game": 3, "followup": 5}
}

# Followup is min of revenue_per_day and tier max
followup_per_day = min(revenue_per_day, tier_map[tier]["followup"])
```

#### Return Structure (Optimized)

```python
{
    # Legacy fields
    "volume_level": str,              # "Low" | "Mid" | "High" | "Ultra"
    "ppv_per_day": int,               # Backward compat
    "bump_per_day": int,              # Backward compat

    # Category volumes
    "revenue_items_per_day": int,     # Revenue sends per day
    "engagement_items_per_day": int,  # Engagement sends per day
    "retention_items_per_day": int,   # Retention sends per day

    # Type-specific limits
    "bundle_per_week": int,           # Bundle limit
    "game_per_week": int,             # Game post limit
    "followup_per_day": int,          # PPV followup limit

    # Optimized volume fields
    "weekly_distribution": List[int], # [Mon, Tue, Wed, Thu, Fri, Sat, Sun]
    "content_allocations": Dict[str, int],  # content_type → count
    "confidence_score": float,        # 0-1
    "elasticity_capped": bool,        # True if bounds applied
    "caption_warnings": List[str],    # Warning messages
    "dow_multipliers_used": List[float],  # Day multipliers
    "adjustments_applied": List[str],     # Adjustment log
    "fused_saturation": float,        # Multi-horizon fusion
    "fused_opportunity": float,       # Multi-horizon fusion
    "prediction_id": str,             # UUID
    "divergence_detected": bool,      # Horizon divergence
    "message_count": int,             # Total messages
    "total_weekly_volume": int,       # Sum of weekly_distribution
    "has_warnings": bool,             # Any warnings
    "is_high_confidence": bool,       # confidence >= 0.70

    # Metadata
    "calculation_source": str,        # "optimized" | "dynamic"
    "fan_count": int,                 # Current fans
    "page_type": str,                 # "paid" | "free"
    "saturation_score": float,        # Original score
    "opportunity_score": float,       # Original score
    "revenue_trend": float,           # Trend value
    "data_source": str,               # Score source
    "tracking_date": str | None       # Score date
}
```

#### Return Structure (Dynamic Fallback)

```python
{
    # Standard fields (same as optimized)
    "volume_level": str,
    "ppv_per_day": int,
    "bump_per_day": int,
    "revenue_items_per_day": int,
    "engagement_items_per_day": int,
    "retention_items_per_day": int,
    "bundle_per_week": int,
    "game_per_week": int,
    "followup_per_day": int,

    # Limited metadata
    "calculation_source": "dynamic",  # Indicates fallback
    "fan_count": int,
    "page_type": str,
    "saturation_score": float,
    "opportunity_score": float,
    "revenue_trend": float,
    "data_source": str,
    "tracking_date": str | None,
    "fallback_reason": str            # Why optimized failed
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `Creator not found: ...` | Invalid creator_id |

---

## Targeting & Channel Tools

### get_channels

Get all channels with optional filtering by targeting support.

**Module**: `mcp.tools.targeting`
**Function**: `get_channels(supports_targeting: Optional[bool] = None) -> dict[str, Any]`
**Return Type**: `ChannelsResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `supports_targeting` | boolean | No | - |

#### Implementation Details

1. **Active Filter**: Only returns channels where `is_active = 1`
2. **Targeting Filter**: Optional filter by `supports_targeting` field
3. **JSON Parsing**: Parses `targeting_options` JSON field
4. **Ordering**: By `channel_id ASC`
5. **Connection Management**: Manual with try-finally

#### Available Channels

| channel_key | display_name | supports_targeting |
|-------------|--------------|-------------------|
| `mass_message` | Mass Message | Yes |
| `wall_post` | Wall Post | No |
| `targeted_message` | Targeted Message | Yes |
| `story` | Story | No |
| `live` | Live Stream | No |

#### targeting_options JSON

For channels with `supports_targeting = 1`:

```json
{
    "subscription_status": true,
    "spending_tier": true,
    "engagement_level": true,
    "custom_lists": true
}
```

#### Return Structure

```python
{
    "channels": List[ChannelData],  # Channel configurations
    "count": int                    # Total count
}
```

---

### get_audience_targets

Get audience targets filtered by page_type and/or channel_key using JSON array matching.

**Module**: `mcp.tools.targeting`
**Function**: `get_audience_targets(page_type: Optional[str] = None, channel_key: Optional[str] = None) -> dict[str, Any]`
**Return Type**: `AudienceTargetsResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `page_type` | string | No | Must be "paid" or "free" |
| `channel_key` | string | No | Alphanumeric, underscore, hyphen |

#### Implementation Details

1. **Input Validation**: Validates channel_key if provided
2. **JSON Array Matching**: Uses LIKE for JSON array matching (SQLite compatible)
3. **Active Filter**: Only returns targets where `is_active = 1`
4. **JSON Parsing**: Parses all JSON fields in response
5. **Connection Management**: Manual with try-finally

#### JSON Array Matching Logic

SQLite doesn't have native JSON array contains, so LIKE is used:

```sql
-- Match page_type in applicable_page_types array
WHERE (applicable_page_types LIKE '%"paid"%' OR applicable_page_types LIKE "%'paid'%")

-- Match channel_key in applicable_channels array
WHERE (applicable_channels LIKE '%"mass_message"%' OR applicable_channels LIKE "%'mass_message'%")
```

This matches both double-quoted and single-quoted JSON strings.

#### Available Audience Targets

| target_key | display_name | filter_type |
|------------|--------------|-------------|
| `all_paid_fans` | All Paid Fans | subscription_status |
| `all_free_fans` | All Free Fans | subscription_status |
| `high_spenders` | High Spenders | spending_behavior |
| `recent_purchasers` | Recent Purchasers | purchase_recency |
| `never_purchased` | Never Purchased | purchase_history |
| `high_engagers` | High Engagers | engagement_level |
| `at_risk` | At Risk | churn_prediction |
| `new_subscribers` | New Subscribers | subscription_age |
| `long_term_fans` | Long-term Fans | subscription_age |
| `expired_fans` | Expired Fans | subscription_status |

#### filter_criteria Examples

```python
# High spenders
{
    "min_spending_30d": 100,
    "subscription_status": "active"
}

# Recent purchasers
{
    "purchased_within_days": 7,
    "subscription_status": "active"
}

# At risk
{
    "days_since_purchase": 30,
    "view_rate_30d": "<0.3",
    "subscription_status": "active"
}
```

#### Return Structure

```python
{
    "targets": List[AudienceTargetData],  # Target configurations
    "count": int                          # Total count
}
```

---

## Schedule Operations Tools

### save_schedule

Save generated schedule to database. Creates a schedule_template record and inserts all schedule_items.

**Module**: `mcp.tools.schedule`
**Function**: `save_schedule(creator_id: str, week_start: str, items: list[dict]) -> dict[str, Any]`
**Return Type**: `SaveScheduleResponse`

#### Parameters

| Name | Type | Required | Validation |
|------|------|----------|------------|
| `creator_id` | string | Yes | Alphanumeric, underscore, hyphen |
| `week_start` | string | Yes | ISO date format YYYY-MM-DD |
| `items` | array | Yes | List of schedule items (see below) |

#### Schedule Item Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheduled_date` | string | Yes | ISO date YYYY-MM-DD |
| `scheduled_time` | string | Yes | Time HH:MM (24-hour) |
| `item_type` | string | Yes | Legacy type (e.g., "ppv", "bump") |
| `channel` | string | Yes | Legacy "mass_message" or "wall_post" |
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
| `expires_at` | string | No | Expiration datetime ISO format |
| `followup_delay_minutes` | integer | No | Minutes to wait for followup |
| `media_type` | string | No | "none", "picture", "gif", "video", "flyer" |
| `campaign_goal` | float | No | Revenue goal for the item |
| `parent_item_id` | integer | No | Parent item ID for followups |

#### Implementation Details

1. **Input Validation**: Validates creator_id
2. **Creator Resolution**: Resolves and validates creator existence
3. **Week End Calculation**: Calculates week_end as week_start + 6 days
4. **Pre-loading**: Loads all lookup tables (send_types, channels, targets)
5. **Template Creation**: Uses UPSERT (ON CONFLICT) to create/update template
6. **Item Deletion**: Deletes existing items for template (supports updates)
7. **Key Resolution**: Resolves all _key fields to _id fields
8. **Flyer Validation**: Warns if send type requires flyer but flyer_required=0
9. **Followup Detection**: Auto-sets is_follow_up=1 if parent_item_id present
10. **Transaction**: Uses implicit transaction with rollback on error

#### SQL Operations

```sql
-- Create/update template
INSERT INTO schedule_templates (
    creator_id, week_start, week_end, generated_at,
    generated_by, algorithm_version, total_items,
    total_ppvs, total_bumps, status
) VALUES (?, ?, ?, datetime('now'), 'mcp_server', '2.0', ?, ?, ?, 'draft')
ON CONFLICT(creator_id, week_start) DO UPDATE SET
    week_end = excluded.week_end,
    generated_at = datetime('now'),
    total_items = excluded.total_items,
    total_ppvs = excluded.total_ppvs,
    total_bumps = excluded.total_bumps,
    status = 'draft'

-- Delete existing items
DELETE FROM schedule_items WHERE template_id = ?

-- Insert items
INSERT INTO schedule_items (
    template_id, creator_id, scheduled_date, scheduled_time,
    item_type, channel, caption_id, caption_text,
    suggested_price, content_type_id, flyer_required, priority, status,
    send_type_id, channel_id, target_id,
    linked_post_url, expires_at, followup_delay_minutes,
    media_type, campaign_goal, parent_item_id, is_follow_up
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

#### Validation Warnings

The function returns warnings for validation issues without failing:

| Warning | Condition |
|---------|-----------|
| `send_type '{key}' requires flyer but flyer_required=0` | Flyer requirement mismatch |
| `Unknown send_type_key '{key}'` | Invalid send type key |
| `Unknown channel_key '{key}'` | Invalid channel key |
| `Unknown target_key '{key}'` | Invalid audience target key |

#### Return Structure

```python
{
    "success": bool,                # Always true if no exception
    "template_id": int,             # Created/updated template ID
    "items_created": int,           # Number of items inserted
    "week_start": str,              # Echo week_start
    "week_end": str,                # Calculated week_end
    "warnings": List[str] | None    # Validation warnings (if any)
}
```

#### Error Responses

| Error | Cause |
|-------|-------|
| `Invalid creator_id: ...` | Validation failed |
| `Creator not found: ...` | Creator doesn't exist |
| `week_start must be in YYYY-MM-DD format` | Invalid date format |
| `Database error: ...` | SQLite error during save |

---

## Query Execution Tool

### execute_query

Execute a read-only SQL SELECT query for custom analysis.

**Module**: `mcp.tools.query`
**Function**: `execute_query(query: str, params: Optional[list] = None) -> dict[str, Any]`
**Return Type**: `QueryExecutionResponse`

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | SQL SELECT query to execute |
| `params` | array | No | Optional list of parameters for the query |

#### Security Protections

This is the most security-sensitive tool in the MCP server. Multiple layers of protection:

1. **Query Type Restriction**: Only SELECT queries allowed
2. **Keyword Blocking**: Blocks dangerous keywords
3. **Comment Injection Detection**: Blocks `/*`, `*/`, `--` patterns
4. **Complexity Limits**: Enforces JOIN and subquery limits
5. **Result Set Limits**: Max 10,000 rows
6. **Auto-LIMIT Injection**: Adds LIMIT if not present
7. **LIMIT Validation**: Validates existing LIMIT doesn't exceed max

#### Blocked Keywords

```python
dangerous_keywords = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "ANALYZE"
]
```

#### Security Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_QUERY_JOINS` | 5 | Prevent complex joins |
| `MAX_QUERY_SUBQUERIES` | 3 | Prevent nested subqueries |
| `MAX_QUERY_RESULT_ROWS` | 10,000 | Prevent large result sets |

#### Implementation Details

1. **Query Logging**: Logs first 100 chars of query (sanitized)
2. **Normalization**: Converts query to uppercase for checks
3. **SELECT Verification**: Must start with "SELECT"
4. **Keyword Check**: Scans for dangerous keywords
5. **Comment Check**: Detects comment injection patterns
6. **Complexity Check**: Counts JOINs and subqueries
7. **LIMIT Injection**: Adds LIMIT if missing
8. **LIMIT Validation**: Validates existing LIMIT value
9. **Execution**: Executes with parameterized query
10. **Column Extraction**: Extracts column names from cursor

#### Security Validation Flow

```
1. Log query preview
   ↓
2. Check starts with SELECT
   ↓
3. Check for dangerous keywords
   ↓
4. Check for comment injection
   ↓
5. Count JOINs (max 5)
   ↓
6. Count subqueries (max 3)
   ↓
7. Check/inject LIMIT (max 10,000)
   ↓
8. Execute query
   ↓
9. Return results
```

#### Return Structure

```python
{
    "results": List[Dict[str, Any]],  # Query result rows
    "count": int,                     # Number of rows returned
    "columns": List[str]              # Column names
}
```

#### Error Responses

| Error | Cause | Prevention |
|-------|-------|------------|
| `Only SELECT queries are allowed` | Non-SELECT query | Use SELECT only |
| `Query contains disallowed keyword: {keyword}` | Dangerous keyword found | Remove write operations |
| `Query contains disallowed comment syntax` | Comment injection attempt | Remove comments |
| `Query exceeds maximum JOIN limit` | Too many JOINs | Simplify query |
| `Query exceeds maximum subquery limit` | Too many subqueries | Flatten query |
| `Query LIMIT exceeds maximum` | LIMIT > 10,000 | Reduce LIMIT |
| `Query execution error: {error}` | SQLite error | Check SQL syntax |

#### Example Queries

```sql
-- Simple query
SELECT creator_id, page_name, current_total_earnings
FROM creators
WHERE performance_tier = 1
ORDER BY current_total_earnings DESC

-- With JOIN
SELECT c.creator_id, c.page_name, COUNT(m.message_id) AS message_count
FROM creators c
JOIN mass_messages m ON c.creator_id = m.creator_id
WHERE m.sending_time >= date('now', '-7 days')
GROUP BY c.creator_id
ORDER BY message_count DESC

-- With parameters
SELECT * FROM caption_bank
WHERE creator_id = ?
    AND performance_score > ?
    AND last_used_date < date('now', '-30 days')
LIMIT 50
```

---

## Error Handling

### Standard Error Response Format

All tools return errors in a consistent format:

```python
{
    "error": str  # Human-readable error message
}
```

### Error Categories

| Category | HTTP Equivalent | Examples |
|----------|-----------------|----------|
| **Validation Error** | 400 Bad Request | Invalid creator_id format |
| **Not Found** | 404 Not Found | Creator/send type doesn't exist |
| **Security Error** | 403 Forbidden | Dangerous SQL keyword detected |
| **Database Error** | 500 Internal Server Error | SQLite error during operation |

### Common Error Messages

| Error Message | Tool(s) | Resolution |
|---------------|---------|------------|
| `Invalid creator_id: ...` | Most tools | Use alphanumeric, underscore, hyphen only; max 100 chars |
| `Creator not found: ...` | Most tools | Verify creator_id with `get_active_creators` |
| `Invalid send_type_key: ...` | Caption/send type tools | Check valid send_type_keys with `get_send_types` |
| `Send type not found: ...` | Caption/send type tools | Use valid send_type_key from send_types table |
| `Invalid channel_key: ...` | Targeting tools | Check valid channel_keys with `get_channels` |
| `Only SELECT queries are allowed` | execute_query | Use SELECT queries only |
| `Query contains disallowed keyword: {keyword}` | execute_query | Remove write operation keywords |
| `Query contains disallowed comment syntax` | execute_query | Remove `--`, `/*`, `*/` from query |
| `page_type must be 'paid' or 'free'` | Multiple tools | Use "paid" or "free" only |
| `category must be 'revenue', 'engagement', or 'retention'` | get_send_types | Use valid category |
| `period must be '7d', '14d', or '30d'` | get_performance_trends | Use valid period |
| `week_start must be in YYYY-MM-DD format` | save_schedule | Use ISO date format |
| `Database error: ...` | Multiple tools | Check database connection and SQL syntax |

### Error Handling Best Practices

1. **Check Error Field**: Always check for `"error"` key in response
2. **Log Errors**: Log full error message for debugging
3. **User-Friendly Messages**: Convert technical errors to user-friendly messages
4. **Retry Logic**: Implement retry for database errors
5. **Validation**: Validate inputs before calling tools

#### Example Error Handling

```python
# Python example
result = get_creator_profile(creator_id="alexia")

if "error" in result:
    logger.error(f"Error getting creator profile: {result['error']}")
    if "not found" in result["error"].lower():
        return "Creator doesn't exist"
    elif "invalid" in result["error"].lower():
        return "Invalid creator ID format"
    else:
        return "Database error occurred"
else:
    # Process successful result
    creator = result["creator"]
```

---

## Security

### Input Validation

All user inputs are validated before database operations using the security module:

**Module**: `mcp.utils.security`

#### validate_creator_id()

```python
def validate_creator_id(creator_id: str) -> tuple[bool, Optional[str]]
```

**Validation Rules**:
- Not empty
- Max length: 100 characters
- Pattern: `^[a-zA-Z0-9_-]+$` (alphanumeric, underscore, hyphen)

**Returns**: `(is_valid: bool, error_message: str | None)`

#### validate_key_input()

```python
def validate_key_input(key: str, key_name: str = "key") -> tuple[bool, Optional[str]]
```

**Validation Rules**:
- Not empty
- Max length: 50 characters
- Pattern: `^[a-zA-Z0-9_-]+$` (alphanumeric, underscore, hyphen)

**Returns**: `(is_valid: bool, error_message: str | None)`

#### validate_string_length()

```python
def validate_string_length(
    value: str,
    max_length: int,
    field_name: str = "field"
) -> tuple[bool, Optional[str]]
```

**Validation Rules**:
- Length <= max_length

**Returns**: `(is_valid: bool, error_message: str | None)`

### SQL Injection Protection

Multiple layers of SQL injection protection:

1. **Parameterized Queries**: All queries use parameterized statements
2. **Input Validation**: All inputs validated before queries
3. **Query Whitelisting**: execute_query restricted to SELECT only
4. **Keyword Blocking**: Dangerous keywords blocked
5. **Comment Filtering**: Comment injection patterns blocked

#### Parameterized Query Example

```python
# SAFE: Parameterized query
cursor = conn.execute(
    "SELECT * FROM creators WHERE creator_id = ?",
    (creator_id,)
)

# UNSAFE: String concatenation (NEVER DO THIS)
cursor = conn.execute(
    f"SELECT * FROM creators WHERE creator_id = '{creator_id}'"
)
```

### Security Constants

**Module**: `mcp.utils.security`

```python
MAX_INPUT_LENGTH_CREATOR_ID = 100
MAX_INPUT_LENGTH_KEY = 50
MAX_QUERY_JOINS = 5
MAX_QUERY_SUBQUERIES = 3
MAX_QUERY_RESULT_ROWS = 10000
```

### Connection Security

- **Same Thread Check**: Disabled for MCP compatibility
- **Timeout**: 30 seconds to prevent hanging
- **Busy Timeout**: 5 seconds for lock contention
- **Read-Only Mode**: Not enforced (allows schedule saves)

### Logging

All security-relevant events are logged:

```python
import logging
logger = logging.getLogger("eros_db_server")

# Input validation failures
logger.warning(f"Invalid creator_id: {error_msg}")

# Blocked queries
logger.warning(f"Blocked query with dangerous keyword: {keyword}")

# Query execution
logger.info(f"execute_query called: {query_preview}")
logger.info(f"execute_query successful: returned {count} rows")

# Errors
logger.error(f"Query execution error: {error}")
```

---

## Type System

### TypedDict Definitions

All return types are defined using TypedDict in `mcp/types.py`.

**Module**: `mcp.types`

### Benefits

1. **Type Safety**: Static type checking with mypy
2. **IDE Support**: Autocomplete and inline documentation
3. **Documentation**: Self-documenting return structures
4. **Validation**: Runtime type validation (optional)

### Usage Example

```python
from mcp.types import CreatorProfile, CreatorInfo, AnalyticsSummary

def get_creator_profile(creator_id: str) -> CreatorProfile:
    """
    Get comprehensive profile for a single creator.

    Args:
        creator_id: The creator_id or page_name to look up.

    Returns:
        CreatorProfile with nested types.
    """
    # Implementation...
    return {
        "creator": creator_info,        # Type: CreatorInfo
        "analytics_summary": analytics,  # Type: AnalyticsSummary
        "volume_assignment": volume,     # Type: VolumeAssignment
        "top_content_types": content     # Type: List[ContentTypeRanking]
    }
```

### Type Hierarchy

```
mcp.types
├── Creator Data Types
│   ├── CreatorInfo
│   ├── AnalyticsSummary
│   ├── VolumeAssignment
│   ├── ContentTypeRanking
│   ├── CreatorProfile
│   ├── CreatorListItem
│   ├── ActiveCreatorsResponse
│   ├── PersonaData
│   └── PersonaProfile
├── Performance & Analytics Types
│   ├── PerformanceTrends
│   ├── ContentTypeRankingsResponse
│   ├── TimingHour
│   ├── TimingDay
│   └── BestTimingResponse
├── Content & Caption Types
│   ├── CaptionData
│   ├── TopCaptionsResponse
│   ├── SendTypeCaptionsResponse
│   ├── VaultItem
│   └── VaultAvailabilityResponse
├── Send Type Configuration Types
│   ├── SendTypeData
│   ├── SendTypesResponse
│   ├── CaptionRequirement
│   ├── SendTypeDetailsResponse
│   └── VolumeConfigResponse
├── Targeting & Channel Types
│   ├── ChannelData
│   ├── ChannelsResponse
│   ├── AudienceTargetData
│   └── AudienceTargetsResponse
├── Schedule Operations Types
│   ├── ScheduleItem
│   └── SaveScheduleResponse
├── Query Execution Types
│   └── QueryExecutionResponse
└── Error Response Type
    └── ErrorResponse
```

### Type Checking

Enable type checking with mypy:

```bash
# Install mypy
pip install mypy

# Run type checking
mypy mcp/tools/
```

**mypy.ini Configuration**:

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

---

## Version History

### v2.2.0 (Current)
- Added comprehensive TypedDict definitions in `mcp/types.py`
- Enhanced docstrings for all tool functions
- Created detailed MCP API Reference documentation
- Improved error documentation with cause and resolution
- Added security documentation

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

## Related Documentation

- **User Guide**: [USER_GUIDE.md](USER_GUIDE.md) - End-user documentation
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md) - Tool usage examples
- **Send Type Reference**: [SEND_TYPE_REFERENCE.md](SEND_TYPE_REFERENCE.md) - Complete send type details
- **Architecture Blueprint**: [SCHEDULE_GENERATOR_BLUEPRINT.md](SCHEDULE_GENERATOR_BLUEPRINT.md) - System architecture
- **Getting Started**: [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide

---

*EROS Schedule Generator MCP API Reference v2.2.0*
*Last Updated: December 17, 2025*
