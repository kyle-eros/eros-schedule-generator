---
description: Generate an optimized weekly schedule for a creator. Use PROACTIVELY when user mentions schedules, content planning, or PPV optimization.
allowed-tools:
  - mcp__eros-db__get_creator_profile
  - mcp__eros-db__get_send_types
  - mcp__eros-db__get_volume_config
  - mcp__eros-db__get_top_captions
  - mcp__eros-db__get_send_type_captions
  - mcp__eros-db__get_best_timing
  - mcp__eros-db__get_performance_trends
  - mcp__eros-db__get_audience_targets
  - mcp__eros-db__get_persona_profile
  - mcp__eros-db__get_vault_availability
  - mcp__eros-db__save_schedule
argument-hint: <creator_id_or_name> [week_start] (e.g., "grace_bennett", "2025-12-23")
---

# Generate Schedule Command

Generate an optimized weekly schedule for the specified creator using the full 8-agent orchestration pipeline.

## Arguments

### Required Parameters

- `$1`: **creator_id_or_name** (required) - Creator identifier or page_name
  - Accepts: numeric ID (`123`), string ID (`creator_123`), or page_name (`grace_bennett`)
  - Case-insensitive for page_name lookups

### Optional Parameters

- `$2`: **week_start** - Schedule start date
  - Format: ISO date `YYYY-MM-DD`
  - Default: Next Monday from current date
  - Must be a Monday (schedules always start on Monday)

## Validation Rules

| Parameter | Type | Required | Validation |
|-----------|------|----------|------------|
| creator_id_or_name | string/int | Yes | Must exist in creators table with active status |
| week_start | ISO date | No | Must be a Monday, cannot be in the past |

## Execution

Invoke the eros-schedule-generator skill to orchestrate the complete schedule generation pipeline:

1. **Performance Analysis** - Assess saturation/opportunity scores
2. **Send Type Allocation** - Distribute 22 send types across the week
3. **Content Curation** - Select type-appropriate captions with freshness scoring
4. **Audience Targeting** - Assign correct targets per item
5. **Timing Optimization** - Calculate optimal posting times
6. **Followup Generation** - Auto-generate PPV followups
7. **Schedule Assembly** - Combine all components
8. **Quality Validation** - Ensure requirements met

## 22 Send Types Distributed

### Revenue Types (9)
- `ppv_unlock` - Primary PPV monetization
- `ppv_wall` - Wall-posted PPV content
- `tip_goal` - Tip goal campaigns
- `bundle` - Content bundles
- `flash_bundle` - Time-limited bundles
- `game_post` - Interactive game content
- `first_to_tip` - Competition-style tips
- `vip_program` - VIP membership offers (max 1/week)
- `snapchat_bundle` - Cross-platform bundles (max 1/week)

### Engagement Types (9)
- `link_drop` - DM link drops
- `wall_link_drop` - Wall-posted links
- `bump_normal` - Standard bump messages
- `bump_descriptive` - Detailed bump messages
- `bump_text_only` - Text-only bumps (no media)
- `bump_flyer` - Flyer-style bumps
- `dm_farm` - DM engagement farming
- `like_farm` - Like engagement farming
- `live_promo` - Live stream promotions

### Retention Types (4) - Paid pages only
- `renew_on_post` - Wall renewal reminders
- `renew_on_message` - DM renewal reminders
- `ppv_followup` - PPV re-engagement (max 4/day)
- `expired_winback` - Lapsed subscriber recovery

## Output Format

The generate command produces a comprehensive weekly schedule:

```json
{
  "schedule_id": "sched_20251223_grace_bennett",
  "creator_id": "creator_123",
  "page_name": "grace_bennett",
  "page_type": "paid",
  "week_start": "2025-12-23",
  "week_end": "2025-12-29",
  "generated_at": "2025-12-17T10:30:00Z",

  "volume_config": {
    "volume_level": "high",
    "ppv_per_day": 3,
    "bump_per_day": 4,
    "revenue_per_day": 4,
    "engagement_per_day": 5,
    "retention_per_day": 2,
    "total_sends_week": 77,
    "confidence_score": 0.87
  },

  "daily_breakdown": {
    "monday": {"revenue": 4, "engagement": 5, "retention": 2, "total": 11},
    "tuesday": {"revenue": 4, "engagement": 5, "retention": 2, "total": 11},
    "wednesday": {"revenue": 4, "engagement": 5, "retention": 2, "total": 11},
    "thursday": {"revenue": 4, "engagement": 5, "retention": 2, "total": 11},
    "friday": {"revenue": 5, "engagement": 6, "retention": 2, "total": 13},
    "saturday": {"revenue": 5, "engagement": 6, "retention": 2, "total": 13},
    "sunday": {"revenue": 3, "engagement": 4, "retention": 1, "total": 8}
  },

  "schedule_items": [
    {
      "item_id": "item_001",
      "day": "monday",
      "date": "2025-12-23",
      "time": "10:30",
      "send_type": "ppv_unlock",
      "category": "revenue",
      "channel": "mass_message",
      "audience_target": "active_30d",
      "caption_id": 12345,
      "caption_preview": "Hey babe, I just dropped something special...",
      "freshness_score": 100,
      "price": 15.00,
      "followups_scheduled": 2
    },
    {
      "item_id": "item_002",
      "day": "monday",
      "date": "2025-12-23",
      "time": "14:00",
      "send_type": "bump_normal",
      "category": "engagement",
      "channel": "mass_message",
      "audience_target": "non_purchasers_7d",
      "caption_id": 23456,
      "caption_preview": "Did you see what I posted earlier?",
      "freshness_score": 92
    }
  ],

  "ppv_followups": [
    {
      "parent_item_id": "item_001",
      "followup_number": 1,
      "delay_minutes": 120,
      "scheduled_time": "12:30",
      "caption_id": 34567,
      "audience_target": "non_purchasers_ppv"
    },
    {
      "parent_item_id": "item_001",
      "followup_number": 2,
      "delay_minutes": 300,
      "scheduled_time": "15:30",
      "caption_id": 34568,
      "audience_target": "non_purchasers_ppv"
    }
  ],

  "quality_validation": {
    "overall_score": 94,
    "rating": "Excellent",
    "checks_passed": 12,
    "checks_failed": 0,
    "warnings": [
      "Caption pool for bump_flyer running low (8 remaining)"
    ],
    "constraints_verified": {
      "ppv_followup_max_4_per_day": true,
      "ppv_followup_min_20min_delay": true,
      "vip_program_max_1_per_week": true,
      "snapchat_bundle_max_1_per_week": true,
      "retention_types_paid_only": true,
      "caption_freshness_30d_min": true
    }
  },

  "optimization_metadata": {
    "saturation_score_used": 42,
    "opportunity_score_used": 68,
    "dow_multipliers_applied": true,
    "elasticity_capped": false,
    "prediction_id": "pred_20251217_abc123"
  }
}
```

## Examples

### Basic Usage
```
/eros:generate grace_bennett
```
Generates schedule for grace_bennett starting next Monday.

### With Specific Start Date
```
/eros:generate creator_123 2025-12-30
```
Generates schedule for creator_123 starting December 30, 2025.

### Revenue-Focused Request
```
Generate a revenue-focused schedule for alexia starting 2025-12-23
```
Natural language triggers the skill with revenue optimization emphasis.

### New Creator Schedule
```
/eros:generate new_creator_789 2025-12-23
```
For new creators with limited history:
- Uses conservative volume settings
- Applies broader caption pool
- Includes extra quality validation
- Flags items needing manual review

### Holiday Period Schedule
```
/eros:generate grace_bennett 2025-12-23
```
For holiday weeks, the system automatically:
- Adjusts timing for holiday engagement patterns
- Increases weekend volume allocation
- Considers subscriber availability changes

## Error Handling

### Invalid Creator ID
```
ERROR: Creator not found
Code: CREATOR_NOT_FOUND
Message: No creator found matching "invalid_name".
Resolution: Run /eros:creators to see available creators.
```

### Inactive Creator
```
ERROR: Creator not active
Code: CREATOR_INACTIVE
Message: Creator "old_creator" is marked inactive.
Resolution: Verify creator status or contact admin to reactivate.
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
Message: get_volume_config timed out after 30s
Resolution:
  1. Check database size and query complexity
  2. Retry the command
  3. Verify MCP server health with /eros:status
```

### Invalid Date Format
```
ERROR: Invalid date format
Code: INVALID_DATE
Message: Date "12-23-2025" is not valid. Use YYYY-MM-DD format.
Resolution: Provide date as "2025-12-23".
```

### Not a Monday
```
ERROR: Invalid week start
Code: NOT_MONDAY
Message: Date "2025-12-24" is not a Monday.
Resolution: Schedules must start on Monday. Use "2025-12-23" instead.
```

### Past Date
```
ERROR: Date in past
Code: PAST_DATE
Message: Date "2025-12-01" is in the past.
Resolution: Choose a future Monday for week_start.
```

### Insufficient Caption Pool
```
WARNING: Low caption availability
Code: LOW_CAPTION_POOL
Message: Only 5 fresh captions available for ppv_unlock. Minimum recommended: 20.
Resolution:
  1. Add new captions to caption_bank
  2. Wait for caption freshness to reset (30 days)
  3. Proceed with manual caption selection flagged
```

### Missing Vault Matrix
```
ERROR: No vault matrix defined
Code: NO_VAULT_MATRIX
Message: Creator has no vault_matrix entries. Cannot filter captions.
Resolution: Add vault_matrix entries for creator's content types.
```

## Performance Expectations

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Execution Time | 15-45 seconds | Full 8-phase pipeline |
| Database Queries | 20-30 | Multiple tools across all phases |
| Memory Usage | Moderate | Caches caption pool and send types |

### Performance Factors

- **Creator history depth** affects analysis phase duration
- **Caption pool size** impacts content curation phase
- **Number of send types** determines allocation complexity
- **PPV followup count** adds to schedule items
- **Save operation** varies with schedule size

### Pipeline Phase Timing

| Phase | Typical Duration |
|-------|------------------|
| Performance Analysis | 2-4 seconds |
| Send Type Allocation | 1-2 seconds |
| Content Curation | 5-10 seconds |
| Audience Targeting | 1-2 seconds |
| Timing Optimization | 2-3 seconds |
| Followup Generation | 1-2 seconds |
| Schedule Assembly | 1-2 seconds |
| Quality Validation | 2-3 seconds |

## Related Commands

| Command | Relationship |
|---------|--------------|
| `/eros:analyze` | Run BEFORE generate to understand saturation/opportunity |
| `/eros:creators` | Use to find valid creator IDs |
| `/eros:validate` | Run AFTER generate to deep-validate caption quality |

### Recommended Workflow

1. `/eros:creators` - Identify target creator
2. `/eros:analyze grace_bennett 14d` - Assess performance state
3. `/eros:generate grace_bennett 2025-12-23` - Generate optimized schedule
4. `/eros:validate grace_bennett` - Validate caption quality
5. Review and approve schedule in output

### Batch Generation

To generate schedules for multiple creators:
```
/eros:generate grace_bennett 2025-12-23
/eros:generate alexia 2025-12-23
/eros:generate creator_456 2025-12-23
```

$ARGUMENTS

@.claude/skills/eros-schedule-generator/SKILL.md
