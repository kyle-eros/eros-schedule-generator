---
description: Analyze creator performance trends, saturation signals, and optimization opportunities. Use PROACTIVELY before generating schedules to inform volume decisions.
allowed-tools:
  - mcp__eros-db__get_creator_profile
  - mcp__eros-db__get_performance_trends
  - mcp__eros-db__get_content_type_rankings
  - mcp__eros-db__execute_query
argument-hint: <creator_id_or_name> [period] (e.g., "grace_bennett", "creator_123", "7d")
---

# Analyze Performance Command

Analyze performance trends and saturation signals for a creator to inform scheduling decisions.

## Arguments

### Required Parameters

- `$1`: **creator_id_or_name** (required) - Creator identifier or page_name
  - Accepts: numeric ID (`123`), string ID (`creator_123`), or page_name (`grace_bennett`)
  - Case-insensitive for page_name lookups

### Optional Parameters

- `$2`: **period** - Analysis time window
  - Valid values: `7d`, `14d`, `30d`
  - Default: `14d`

## Validation Rules

| Parameter | Type | Required | Validation |
|-----------|------|----------|------------|
| creator_id_or_name | string/int | Yes | Must exist in creators table |
| period | enum | No | Must be exactly: `7d`, `14d`, or `30d` |

## Analysis Outputs

1. **Saturation Score** (0-100) - Higher = audience fatigue detected
2. **Opportunity Score** (0-100) - Higher = room for increased volume
3. **Revenue Velocity** - Recent revenue trend direction
4. **Content Type Rankings** - TOP/MID/LOW/AVOID classifications
5. **Volume Recommendations** - Suggested adjustments

## Saturation Indicators

- Declining open rates on PPV sends
- Decreasing tip amounts
- Lower engagement on bump messages
- Reduced renewal rates

## Opportunity Indicators

- Growing subscriber count
- Increasing engagement rates
- High caption freshness (many unused)
- Successful recent send types

## Output Format

The analyze command returns a structured JSON response with the following fields:

```json
{
  "creator_id": "creator_123",
  "page_name": "grace_bennett",
  "page_type": "paid",
  "analysis_period": "14d",
  "analysis_timestamp": "2025-12-17T10:30:00Z",

  "saturation_metrics": {
    "overall_score": 42,
    "interpretation": "MODERATE",
    "ppv_fatigue": 38,
    "bump_fatigue": 45,
    "open_rate_trend": -0.12,
    "tip_trend": -0.08,
    "renewal_rate_trend": 0.02
  },

  "opportunity_metrics": {
    "overall_score": 68,
    "interpretation": "HIGH",
    "subscriber_growth": 0.15,
    "engagement_trend": 0.22,
    "caption_freshness_avg": 87,
    "unused_caption_count": 234,
    "underutilized_send_types": ["flash_bundle", "game_post", "dm_farm"]
  },

  "multi_horizon_analysis": {
    "7d": {"saturation": 35, "opportunity": 72},
    "14d": {"saturation": 42, "opportunity": 68},
    "30d": {"saturation": 48, "opportunity": 61},
    "divergence_detected": false,
    "trend_direction": "improving"
  },

  "content_type_rankings": {
    "TOP": ["ppv_unlock", "bundle", "bump_normal"],
    "MID": ["flash_bundle", "tip_goal", "link_drop"],
    "LOW": ["game_post", "dm_farm", "like_farm"],
    "AVOID": ["vip_program"]
  },

  "revenue_analysis": {
    "total_30d": 12450.00,
    "velocity": "increasing",
    "velocity_pct": 0.18,
    "top_revenue_types": [
      {"type": "ppv_unlock", "revenue": 6200.00, "count": 45},
      {"type": "bundle", "revenue": 3100.00, "count": 12},
      {"type": "tip_goal", "revenue": 1850.00, "count": 28}
    ]
  },

  "volume_recommendation": {
    "current_level": "high",
    "recommended_level": "high",
    "adjustment": "maintain",
    "ppv_per_day": {"current": 3, "recommended": 3},
    "bump_per_day": {"current": 4, "recommended": 4},
    "reasoning": "Strong opportunity score with manageable saturation supports current volume."
  },

  "alerts": [
    {"severity": "INFO", "message": "Caption pool running low for bump_descriptive (12 remaining)"},
    {"severity": "WARNING", "message": "vip_program shows negative ROI - consider pausing"}
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `saturation_metrics.overall_score` | int (0-100) | Aggregate fatigue indicator |
| `saturation_metrics.interpretation` | enum | LOW (0-30), MODERATE (31-60), HIGH (61-100) |
| `opportunity_metrics.overall_score` | int (0-100) | Growth potential indicator |
| `multi_horizon_analysis` | object | Compares 7d/14d/30d trends |
| `content_type_rankings` | object | Send type performance tiers |
| `volume_recommendation.adjustment` | enum | `increase`, `maintain`, `decrease` |

## Examples

### Basic Usage
```
/eros:analyze grace_bennett
```
Analyzes grace_bennett with default 14-day period.

### With Analysis Period
```
/eros:analyze creator_123 30d
```
Analyzes creator_123 with 30-day lookback for long-term trends.

### Short-Term Analysis
```
/eros:analyze alexia 7d
```
Analyzes alexia with 7-day window to detect recent changes.

### New Creator with Limited History
```
/eros:analyze new_creator_456 7d
```
For creators with less than 14 days of data, use 7d period. The system will return partial metrics with confidence indicators for data with limited history.

### Pre-Schedule Analysis Workflow
```
/eros:analyze grace_bennett 14d
# Review saturation/opportunity scores
# Then generate schedule with informed decisions:
/eros:generate grace_bennett 2025-12-23
```

## Error Handling

### Invalid Creator ID
```
ERROR: Creator not found
Code: CREATOR_NOT_FOUND
Message: No creator found matching "invalid_name".
Resolution: Run /eros:creators to see available creators.
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
Message: get_performance_trends timed out after 30s
Resolution:
  1. Check database size and query complexity
  2. Try shorter analysis period (7d instead of 30d)
  3. Verify MCP server health with /eros:status
```

### Invalid Period Parameter
```
ERROR: Invalid period value
Code: INVALID_PERIOD
Message: Period "15d" is not valid. Must be one of: 7d, 14d, 30d
Resolution: Use only supported period values.
```

### Insufficient Data
```
WARNING: Insufficient historical data
Code: INSUFFICIENT_DATA
Message: Creator has only 5 days of activity. Results may have low confidence.
Resolution: Use 7d period for new creators, or wait for more data accumulation.
```

## Performance Expectations

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Execution Time | 2-5 seconds | Depends on analysis period and data volume |
| Database Queries | 4-6 | get_creator_profile, get_performance_trends, get_content_type_rankings, plus custom queries |
| Memory Usage | Low | Query results cached during analysis |

### Performance Factors

- **Longer periods** (30d) require more historical data processing
- **High-volume creators** with many sends take longer to analyze
- **First analysis** may be slower due to cache warming
- **Concurrent analyses** for multiple creators can be run in parallel

## Related Commands

| Command | Relationship |
|---------|--------------|
| `/eros:generate` | Run analyze BEFORE generate to inform volume decisions |
| `/eros:creators` | Use to find valid creator IDs before analysis |
| `/eros:validate` | Use after generate to validate caption quality |

### Typical Workflow

1. `/eros:creators` - Find creator to schedule
2. `/eros:analyze grace_bennett 14d` - Assess performance state
3. `/eros:generate grace_bennett 2025-12-23` - Generate informed schedule
4. `/eros:validate grace_bennett` - Validate caption quality

$ARGUMENTS

@.claude/agents/performance-analyst.md
