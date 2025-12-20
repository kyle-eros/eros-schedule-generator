---
name: eros-creators
model: haiku
description: List all active creators with performance metrics and tier classification. Use to find valid creator IDs before running other commands.
allowed-tools:
  - mcp__eros-db__get_active_creators
argument-hint: [tier] [page_type] (e.g., "1", "paid", "2 free")
---

# List Creators Command

Display all active creators with their key metrics and volume assignments.

## Arguments

### Optional Parameters

- `$1`: **tier** - Filter by performance tier
  - Valid values: `1`, `2`, `3`, `4`, `5`
  - Tier 1 = highest performers, Tier 5 = lowest performers
  - Default: all tiers

- `$2`: **page_type** - Filter by page monetization type
  - Valid values: `paid`, `free`
  - Default: all types

## Validation Rules

| Parameter | Type | Required | Validation |
|-----------|------|----------|------------|
| tier | integer | No | Must be 1, 2, 3, 4, or 5 |
| page_type | enum | No | Must be exactly `paid` or `free` |

## Output Format

```json
{
  "query_timestamp": "2025-12-17T10:30:00Z",
  "filters_applied": {
    "tier": null,
    "page_type": null
  },
  "total_count": 37,
  "creators": [
    {
      "creator_id": "creator_123",
      "page_name": "grace_bennett",
      "page_type": "paid",
      "status": "active",
      "performance_tier": 1,
      "volume_level": "high",
      "metrics": {
        "total_revenue_30d": 15420.00,
        "active_subs": 1247,
        "avg_ppv_revenue": 12.50,
        "open_rate_avg": 0.68,
        "renewal_rate": 0.82
      },
      "last_schedule_date": "2025-12-16"
    },
    {
      "creator_id": "creator_456",
      "page_name": "alexia",
      "page_type": "paid",
      "status": "active",
      "performance_tier": 1,
      "volume_level": "high",
      "metrics": {
        "total_revenue_30d": 12890.00,
        "active_subs": 985,
        "avg_ppv_revenue": 11.20,
        "open_rate_avg": 0.72,
        "renewal_rate": 0.78
      },
      "last_schedule_date": "2025-12-16"
    }
  ],
  "tier_summary": {
    "tier_1": {"count": 5, "avg_revenue": 14200.00},
    "tier_2": {"count": 8, "avg_revenue": 8500.00},
    "tier_3": {"count": 12, "avg_revenue": 4200.00},
    "tier_4": {"count": 7, "avg_revenue": 1800.00},
    "tier_5": {"count": 5, "avg_revenue": 650.00}
  }
}
```

## Output Columns

| Column | Description |
|--------|-------------|
| creator_id | Unique identifier (use in other commands) |
| page_name | Display name (also usable as identifier) |
| page_type | `paid` or `free` monetization model |
| performance_tier | 1-5 ranking (1 = top performer) |
| volume_level | Current volume: `low`, `medium`, `high`, `very_high` |
| total_revenue_30d | Recent 30-day revenue |
| active_subs | Current active subscriber count |
| last_schedule_date | Most recent schedule generation date |

## Performance Tiers Explained

| Tier | Percentile | Characteristics |
|------|------------|-----------------|
| 1 | Top 15% | Highest revenue, best engagement, premium volume |
| 2 | 15-35% | Strong performers, high volume potential |
| 3 | 35-60% | Average performers, moderate volume |
| 4 | 60-85% | Below average, conservative volume |
| 5 | Bottom 15% | Lowest performers, minimal volume |

## Examples

### Basic Usage - List All Creators
```
/eros:creators
```
Returns all 37 active creators sorted by performance tier.

### Filter by Tier
```
/eros:creators 1
```
Returns only Tier 1 (top performing) creators.

```
/eros:creators 3
```
Returns Tier 3 (average performing) creators.

### Filter by Page Type
```
/eros:creators paid
```
Returns all paid page creators (note: page_type can be used as first argument).

```
/eros:creators free
```
Returns all free page creators.

### Combined Filters
```
/eros:creators 2 paid
```
Returns Tier 2 creators with paid pages only.

```
/eros:creators 1 free
```
Returns top-tier free page creators.

### Find Specific Creator
After listing, use the creator_id or page_name in other commands:
```
/eros:creators
# Find "grace_bennett" in results
/eros:analyze grace_bennett
/eros:generate grace_bennett 2025-12-23
```

### Discover New Creators to Schedule
```
/eros:creators 1
# Review which Tier 1 creators haven't been scheduled recently
# Check last_schedule_date column
```

## Error Handling

### Invalid Tier Value
```
ERROR: Invalid tier value
Code: INVALID_TIER
Message: Tier "6" is not valid. Must be 1, 2, 3, 4, or 5.
Resolution: Use tier values 1-5 only.
```

### Invalid Page Type
```
ERROR: Invalid page type
Code: INVALID_PAGE_TYPE
Message: Page type "premium" is not valid. Must be "paid" or "free".
Resolution: Use exactly "paid" or "free".
```

### Database Connection Failure
```
ERROR: Database connection failed
Code: DB_CONNECTION_ERROR
Message: Unable to connect to eros_sd_main.db
Resolution:
  1. Verify database file exists at ./database/eros_sd_main.db
  2. Check EROS_DB_PATH environment variable
  3. Ensure MCP eros-db server is running
```

### MCP Tool Timeout
```
ERROR: MCP tool timeout
Code: MCP_TIMEOUT
Message: get_active_creators timed out after 30s
Resolution:
  1. Retry the command
  2. Verify MCP server health
  3. Check database connectivity
```

### No Results Found
```
INFO: No creators match filters
Code: NO_RESULTS
Message: No active creators found matching tier=5, page_type=free
Resolution: Try broader filters or check if creators exist with those criteria.
```

## Performance Expectations

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Execution Time | 1-2 seconds | Single database query |
| Database Queries | 1 | get_active_creators |
| Memory Usage | Low | Returns summary data only |

### Performance Factors

- **No filters** returns all creators (fastest after initial cache)
- **Tier filter** uses indexed column (fast)
- **Page type filter** uses indexed column (fast)
- **Combined filters** still fast due to small dataset (37 creators)

## Related Commands

| Command | Relationship |
|---------|--------------|
| `/eros:analyze` | Use creator_id from this list to analyze performance |
| `/eros:generate` | Use creator_id from this list to generate schedules |
| `/eros:validate` | Use creator_id from this list to validate captions |

### Typical Workflow

1. `/eros:creators` - Browse available creators
2. `/eros:creators 1` - Focus on top performers
3. `/eros:analyze grace_bennett` - Deep dive on selected creator
4. `/eros:generate grace_bennett 2025-12-23` - Generate schedule

### Finding Creators Needing Schedules

```
/eros:creators
# Sort mentally by last_schedule_date
# Identify creators not scheduled in past 7 days
# Prioritize by tier (1 first, then 2, etc.)
```

$ARGUMENTS
