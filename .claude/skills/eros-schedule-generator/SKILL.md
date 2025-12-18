---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Use PROACTIVELY when user mentions scheduling, generating schedules, content planning, PPV optimization, or revenue maximization. Automatically invoked for schedule-related requests.
version: 2.3.0
model: sonnet
triggers:
  - generate a schedule
  - create weekly schedule
  - schedule for
  - PPV schedule
  - content schedule
  - revenue optimization
  - engagement schedule
  - retention schedule
---

## MCP Tool Usage Mandate

**CRITICAL ENFORCEMENT DIRECTIVE**

This skill REQUIRES actual MCP tool invocations. Generating schedules without database queries is PROHIBITED.

### Enforcement Rules

1. **No Hallucinated Data**: Every data point must originate from an MCP tool response
2. **Tool Count Tracking**: Each phase must log `tools_invoked` count
3. **Checkpoint Verification**: Before advancing phases, verify `tools_invoked > 0`
4. **Failure on Zero Tools**: If any phase completes with `tools_invoked == 0`, HALT execution

### Phase-to-Tool Mapping

| Phase | Agent | Required Tools |
|-------|-------|----------------|
| 1 | performance-analyst | get_creator_profile, get_volume_config, get_performance_trends, get_vault_availability |
| 2 | send-type-allocator | get_send_types, get_volume_config |
| 3 | content-curator | get_send_type_captions, get_top_captions |
| 4 | timing-optimizer | get_best_timing |
| 5 | followup-generator | get_send_type_details |
| 6 | authenticity-engine | get_persona_profile |
| 7 | schedule-assembler | get_channels, get_creator_profile |
| 8 | revenue-optimizer | get_send_type_details, get_volume_config |
| 9 | quality-validator | get_creator_profile, get_persona_profile, save_schedule |

### Verification Protocol

At each checkpoint, output:
```
TOOLS_INVOKED: N
TOOLS_EXPECTED: M
STATUS: [PASS/FAIL]
```

If STATUS == FAIL, do NOT proceed to next phase.

---

# EROS Schedule Generator

## Purpose

Orchestrates the 22-type schedule generation system for OnlyFans creators, producing optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention. The system leverages performance analytics, caption freshness scoring, and type-specific timing rules to maximize creator earnings while maintaining authentic communication patterns.

---

## ⚠️ CRITICAL: 22-Type Diversity Requirement

**A valid schedule MUST include variety from the full 22-type taxonomy. Schedules containing only `ppv_unlock` and `bump_normal` are INVALID and must be rejected.**

### Minimum Diversity Requirements

| Category | Minimum Types | Available Types |
|----------|---------------|-----------------|
| Revenue | **5 of 9** | ppv_unlock, ppv_wall (FREE), tip_goal (PAID), bundle, flash_bundle, game_post, first_to_tip, vip_program, snapchat_bundle |
| Engagement | **5 of 9** | bump_normal, bump_descriptive, bump_text_only, bump_flyer, link_drop, wall_link_drop, dm_farm, like_farm, live_promo |
| Retention (paid) | **2 of 4** | renew_on_message, renew_on_post, expired_winback, ppv_followup |

### Diversity Validation Checklist
- [ ] **10+ unique send_type_keys** across the weekly schedule
- [ ] **NOT just ppv and bump** - schedule uses full type variety
- [ ] **All 3 categories represented** (revenue, engagement, retention for paid pages)
- [ ] **Weekly limits respected** (vip_program ≤1, snapchat_bundle ≤1)

---

## When to Use

Invoke this skill when the user requests any of the following:

- "Generate a schedule for [creator]"
- "Create weekly schedule for [creator] starting [date]"
- "Schedule [creator] with focus on [revenue/engagement/retention]"
- "Generate PPV-heavy schedule for [creator]"
- "Build next week's content plan for [creator]"
- "Optimize [creator]'s posting schedule"
- Any request involving schedule creation, content planning, or send allocation

## Parameters

| Parameter | Required | Type | Default | Description |
|-----------|----------|------|---------|-------------|
| `creator_id` | Yes | string | - | Creator identifier or page_name (e.g., "alexia", "creator_123") |
| `week_start` | No | string (ISO date) | Next Monday | Schedule start date in YYYY-MM-DD format |
| `send_types` | No | array[string] | All applicable | Specific send_type_keys to include (e.g., ["ppv_unlock", "bump_normal"]) |
| `include_retention` | No | boolean | true (paid pages) | Include retention category items |
| `include_followups` | No | boolean | true | Auto-generate followup items for PPV sends |
| `category_focus` | No | string | balanced | Primary category: "revenue", "engagement", "retention", or "balanced" |

---

## Multi-Agent Workflow

The schedule generation process coordinates nine specialized agents across 9 phases, each responsible for a distinct aspect of the workflow.

### 1. performance-analyst (Phase 1)
**Role**: Analyze creator performance trends and saturation levels
**Inputs**: Creator ID, performance period (7d/14d/30d)
**Outputs**: Saturation score, opportunity score, trend indicators, revenue velocity
**Tools**: `get_performance_trends`, `get_creator_profile`

### 2. send-type-allocator (Phase 2)
**Role**: Distribute send types across daily slots based on volume configuration
**Inputs**: Volume config, performance analysis, category focus
**Outputs**: Daily allocation map with send_type_keys per day
**Tools**: `get_volume_config`, `get_send_types`

### 3. content-curator (Phase 3)
**Role**: Select type-appropriate captions using send_type_key matching
**Inputs**: Allocated send types, creator persona, vault availability
**Outputs**: Caption assignments with performance and freshness scores
**Tools**: `get_send_type_captions`, `get_top_captions`, `get_persona_profile`

### 4. timing-optimizer (Phase 4)
**Role**: Calculate optimal posting times with type-specific rules
**Inputs**: Historical performance data, send type timing constraints
**Outputs**: Scheduled times with spacing validation
**Tools**: `get_best_timing`, `get_send_type_details`

### 5. followup-generator (Phase 5)
**Role**: Auto-generate followup items for PPV sends
**Inputs**: PPV schedule items, followup delay configuration
**Outputs**: Linked followup items with parent references
**Tools**: `get_send_type_details` (for ppv_followup configuration)

### 6. authenticity-engine (Phase 6) [NEW]
**Role**: Apply anti-AI humanization and persona consistency
**Inputs**: Schedule items with captions, creator persona
**Outputs**: Humanized items with authenticity scores
**Tools**: `get_persona_profile`

### 7. schedule-assembler (Phase 7)
**Role**: Combine all components into final schedule structure
**Inputs**: All agent outputs including authenticity results, creator profile, week parameters
**Outputs**: Complete schedule ready for optimization
**Tools**: `get_channels`, `get_creator_profile`

### 8. revenue-optimizer (Phase 8) [NEW]
**Role**: Optimize pricing and positioning for maximum revenue
**Inputs**: Assembled schedule, volume config
**Outputs**: Priced items with positioning recommendations
**Tools**: `get_send_type_details`, `get_volume_config`

### 9. quality-validator (Phase 9)
**Role**: Validate requirements, authenticity, and completeness (FINAL GATE)
**Inputs**: Optimized schedule, business rules
**Outputs**: Validation report, corrected schedule if needed
**Tools**: `get_creator_profile`, `get_persona_profile`, `save_schedule`

---

## Execution Flow

### Phase 1: INITIALIZATION
**Duration**: ~2 seconds
**Objective**: Load all required creator data and calculate dynamic volume configuration

```
1.1 Load creator profile
    - get_creator_profile(creator_id)
    - Extract: page_type, performance_tier, current_active_fans, analytics summary

1.2 Load volume configuration (DYNAMIC CALCULATION)
    - get_volume_config(creator_id)
    - Volume is calculated dynamically based on:
      * Fan count → tier (LOW/MID/HIGH/ULTRA)
      * Saturation score → volume reduction (0.7-1.0x)
      * Opportunity score → volume increase (1.0-1.2x)
      * Revenue trend → adjustment (-1/0/+1)
    - Extract: daily limits per category, type-specific caps

1.3 Load performance trends
    - get_performance_trends(creator_id, period="14d")
    - Extract: saturation_score, opportunity_score, revenue_trend
    - Note: These scores feed into dynamic volume calculation

1.4 Load send type catalog
    - get_send_types(page_type)
    - Filter by page_type applicability

1.5 Load vault availability
    - get_vault_availability(creator_id)
    - Map available content types to send requirements

IMPORTANT: Static volume_assignments table is DEPRECATED.
Volume is now calculated dynamically by get_volume_config().
```

#### 1.2.1 Optimized Volume Pipeline (REQUIRED)

When `get_volume_config()` is called, it returns the full `OptimizedVolumeResult` with these fields:

**Legacy Fields (backward compatible):**
```json
{
    "volume_level": "High",
    "ppv_per_day": 5,
    "bump_per_day": 4
}
```

**NEW Optimized Fields (MUST be consumed):**
```json
{
    "revenue_per_day": 6,
    "engagement_per_day": 5,
    "retention_per_day": 2,
    "weekly_distribution": {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13},
    "content_allocations": {"solo": 3, "lingerie": 2, "outdoor": 1},
    "confidence_score": 0.85,
    "elasticity_capped": false,
    "caption_warnings": [],
    "dow_multipliers_used": {"0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0},
    "adjustments_applied": ["base_tier_calculation", "multi_horizon_fusion", "dow_multipliers", "prediction_tracked"],
    "fused_saturation": 45.0,
    "fused_opportunity": 62.0,
    "divergence_detected": false,
    "prediction_id": 123,
    "message_count": 156,
    "calculation_source": "optimized",
    "data_source": "volume_performance_tracking"
}
```

**8 Integrated Optimization Modules:**

| Module | Key Fields | Purpose | Indicator |
|--------|-----------|---------|-----------|
| Base Tier Calculation | `final_config.*` | Calculate volume from fan count tier | Always applied |
| Multi-Horizon Fusion | `fused_saturation`, `fused_opportunity`, `divergence_detected` | 7d/14d/30d score fusion for smoother trends | `adjustments_applied` contains `multi_horizon_fusion` |
| Confidence Dampening | `confidence_score`, `message_count` | Dampen multipliers for new creators (<30 messages) | `adjustments_applied` contains `confidence_dampening` |
| DOW Multipliers | `weekly_distribution`, `dow_multipliers_used` | Day-of-week volume distribution | `adjustments_applied` contains `dow_multipliers` |
| Elasticity Bounds | `elasticity_capped` | Cap volume if diminishing returns detected | Boolean flag `true` when capped |
| Content Weighting | `content_allocations` | Performance-based content type allocation | `adjustments_applied` contains `content_weighting` |
| Caption Pool Check | `caption_warnings` | Alert for caption shortages | Non-empty array when issues detected |
| Prediction Tracking | `prediction_id` | Track for accuracy measurement | `adjustments_applied` contains `prediction_tracked` |

#### 1.2.2 Confidence-Based Decision Criteria

The `confidence_score` (0.0-1.0) indicates reliability of the volume calculation:

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 0.8-1.0 | High confidence | Trust calculated volumes fully |
| 0.6-0.79 | Moderate confidence | Minor dampening applied |
| 0.4-0.59 | Low confidence | Significant dampening, use conservative defaults |
| < 0.4 | Very low confidence | New creator mode, minimal aggressive sends |

**Decision Points Using confidence_score:**

1. **Revenue Allocation**: If `confidence_score < 0.6`, cap `revenue_per_day` at tier minimum
2. **PPV Pricing**: If `confidence_score < 0.5`, use lower end of price range
3. **Followup Aggressiveness**: If `confidence_score < 0.6`, reduce followup generation to 50%
4. **Validation Strictness**: If `confidence_score < 0.7`, lower freshness threshold by 10 points

**Example:**
```python
if volume_config.confidence_score < 0.6:
    # Low confidence - be conservative
    revenue_quota = min(revenue_quota, tier_minimum.revenue)
    followup_rate = 0.5
    freshness_threshold -= 10

    validation_notes.append(
        f"Low confidence ({volume_config.confidence_score:.2f}) - "
        "using conservative allocation"
    )
```

### Phase 2: SEND TYPE ALLOCATION
**Duration**: ~1 second
**Objective**: Distribute send types across the 7-day schedule

#### 2.0.1 Use weekly_distribution for Per-Day Allocation

**IMPORTANT**: Instead of applying uniform `revenue_per_day` to all 7 days, use the `weekly_distribution` from OptimizedVolumeResult:

```python
# OLD approach (DEPRECATED):
for day in range(7):
    daily_quota = volume_config.revenue_per_day  # Same for all days

# NEW approach (REQUIRED):
for day in range(7):
    daily_quota = volume_config.weekly_distribution[day]  # DOW-adjusted
```

**weekly_distribution Values:**
- Keys: 0-6 (Monday=0, Sunday=6)
- Values: Total items for that day (already DOW-adjusted)

**Example (HIGH tier creator, base 13/day):**
```json
"weekly_distribution": {
    "0": 12,  // Monday - slightly reduced (post-weekend recovery)
    "1": 13,  // Tuesday - baseline
    "2": 13,  // Wednesday - baseline
    "3": 13,  // Thursday - baseline
    "4": 14,  // Friday - weekend prep boost (+10%)
    "5": 13,  // Saturday - high activity
    "6": 13   // Sunday - baseline
}
```

**Note**: Keys are strings in JSON format. The sum equals 91 items/week (vs 91 at uniform 13/day).
DOW multipliers are applied relative to the base daily volume from the tier calculation.

The `dow_multipliers_used` field shows the multipliers that produced this distribution for transparency.

```
2.1 Calculate daily quotas
    - Use weekly_distribution[day] for total items per day
    - Distribute across categories using revenue_per_day, engagement_per_day, retention_per_day ratios
    - Apply content_allocations for content type weighting

2.2 Apply category focus weighting
    - If category_focus specified, adjust quotas (1.5x focus, 0.75x others)

2.3 Distribute across days
    - Spread high-value sends (PPV) to optimal days (typically Tue-Thu)
    - Place engagement items in supporting slots
    - Add retention items to subscriber renewal windows

2.4 Validate against limits
    - Ensure no day exceeds max_items_per_day
    - Check type-specific frequency limits (e.g., max 1 vip_program/week)
```

### Phase 3: CONTENT MATCHING
**Duration**: ~3 seconds
**Objective**: Select optimal captions for each allocated slot

```
3.1 For each allocated send:
    - get_send_type_captions(creator_id, send_type_key)
    - Score by: (freshness_score * 0.40) + (performance_score * 0.35) + (type_priority * 0.15) + (diversity * 0.05) + (persona * 0.05)
    - Select top candidate not used in last 7 days

3.2 Apply persona consistency
    - get_persona_profile(creator_id)
    - Validate caption tone, emoji style, slang level match

3.3 Fallback handling
    - If no fresh caption available, select from get_top_captions
    - Flag items requiring new caption creation
```

### Phase 4: TIMING OPTIMIZATION
**Duration**: ~2 seconds
**Objective**: Calculate optimal times with type-specific rules

```
5.1 Load historical performance
    - get_best_timing(creator_id)
    - Extract: peak hours by day, avoid hours

5.2 Apply type-specific rules
    - PPV sends: Peak engagement hours (typically 8-10 PM)
    - Bumps: Early morning (7-9 AM) or late night (11 PM-1 AM)
    - Retention: Late afternoon (4-6 PM)

5.3 Calculate spacing
    - Minimum 2 hours between same-type sends
    - Minimum 30 minutes between any sends
    - No more than 3 sends per 4-hour block

5.4 Set expiration times
    - Apply default_expiration_hours from send type config
    - Adjust for flash bundles (shorter) vs standard PPV (longer)
```

### Phase 5: FOLLOW-UP GENERATION
**Duration**: ~1 second
**Objective**: Create automatic followup items for PPV sends

```
5.1 Identify PPV items requiring followups
    - Filter: send_type_category = "revenue"
    - Check: generates_followup = true

5.2 Generate followup items
    - send_type_key: "ppv_followup"
    - scheduled_time: parent_time + followup_delay_minutes
    - is_follow_up: 1
    - parent_item_id: reference to parent

5.3 Select followup captions
    - get_send_type_captions(creator_id, "ppv_followup")
    - Match to parent content type context
```

### Phase 6: AUTHENTICITY ENGINE [NEW]
**Duration**: ~1 second
**Objective**: Apply anti-AI humanization and persona consistency

```
6.1 Load persona profile
    - get_persona_profile(creator_id)
    - Extract: tone, archetype, emoji_style, slang_level

6.2 Humanize captions
    - Apply timing jitter (+-5 minutes)
    - Inject natural language variation
    - Add persona-specific emoji patterns
    - Remove AI-detectable patterns

6.3 Calculate authenticity scores
    - Score each item 0-100
    - Flag items below 65 for review
    - Apply slang level adjustments
```

### Phase 7: SCHEDULE ASSEMBLY
**Duration**: ~1 second
**Objective**: Combine all components into final schedule structure

```
7.1 Assemble schedule items
    - Merge: allocation + caption + target + timing + followups + authenticity
    - Add metadata: priority, media_type, flyer_required

7.2 Apply expiration rules
    - Set expires_at for time-sensitive sends
    - Validate expiration windows

7.3 Merge authenticity results
    - Integrate humanized captions
    - Preserve authenticity scores
```

### Phase 8: REVENUE OPTIMIZATION [NEW]
**Duration**: ~1 second
**Objective**: Optimize pricing and positioning for maximum revenue

```
8.1 Load revenue context
    - get_volume_config(creator_id) for confidence_score
    - get_send_type_details for pricing rules

8.2 Apply dynamic pricing
    - Calculate prices based on content type performance
    - Apply confidence dampening for new creators
    - Set bundle value framing

8.3 Optimize positioning
    - Place high-value items at peak times
    - Apply first-to-tip day rotation
    - Balance revenue distribution across week
```

### Phase 9: QUALITY VALIDATION (FINAL GATE)
**Duration**: ~2 seconds
**Objective**: Validate requirements and save to database

```
9.1 Run quality checks
    - Validate all required fields present
    - Check caption uniqueness across schedule
    - Verify vault has required content types
    - Confirm timing conflicts resolved
    - Validate 22-type diversity requirements

9.2 Generate validation report
    - Items by category breakdown
    - Coverage gaps identified
    - Recommendations for improvement
    - Include caption_warnings from volume_config

9.3 Save to database
    - save_schedule(creator_id, week_start, items)
    - Return: template_id, item_ids, summary
```

#### 7.2.1 Handling Caption Warnings

When `caption_warnings` from OptimizedVolumeResult is non-empty, the schedule generator MUST:

1. **Surface warnings to quality-validator**: Pass warnings to Phase 9 validation
2. **Log warnings in validation report**: Include in final summary
3. **Adjust allocation if critical**: If warnings mention "critical shortage":
   - Reduce allocation for affected send types by 50%
   - Flag items for manual caption review
   - Add to `validation.recommendations`

**Warning Types:**

| Warning Pattern | Severity | Action |
|-----------------|----------|--------|
| "Low captions for X: <3 usable" | Critical | Reduce X allocation by 50% |
| "Insufficient freshness for X" | Warning | Use lower freshness threshold (min 20) |
| "Caption pool exhausted for X" | Critical | Skip X or flag for caption creation |
| "High reuse rate for X" | Warning | Log warning, proceed with caution |

**Example Integration:**
```python
if volume_config.caption_warnings:
    for warning in volume_config.caption_warnings:
        if "critical shortage" in warning.lower() or "exhausted" in warning.lower():
            # Reduce allocation for affected type
            affected_type = extract_type_from_warning(warning)
            quotas[affected_type] = int(quotas[affected_type] * 0.5)
            validation_recommendations.append(
                f"Create new captions for {affected_type}"
            )
        elif "insufficient freshness" in warning.lower():
            # Lower freshness threshold for this type
            freshness_thresholds[affected_type] = max(20, freshness_thresholds[affected_type] - 15)

        # Always log to validation report
        validation_warnings.append(warning)
```

**Validation Report Format with Caption Warnings:**
```json
{
  "validation": {
    "status": "passed_with_warnings",
    "warnings": [
      "Low captions for ppv_followup: <3 usable",
      "Insufficient freshness for bump_descriptive"
    ],
    "adjustments_made": [
      "Reduced ppv_followup allocation from 8 to 4",
      "Lowered freshness threshold for bump_descriptive to 20"
    ],
    "recommendations": [
      "Create 5+ new ppv_followup captions",
      "Review bump_descriptive caption rotation"
    ]
  }
}
```

---

## Output Format

### Schedule Item Structure

```json
{
  "item_id": 12345,
  "scheduled_date": "2025-01-20",
  "scheduled_time": "20:00:00",

  "send_type": {
    "key": "ppv_unlock",
    "category": "revenue",
    "display_name": "PPV Video"
  },

  "channel": {
    "key": "mass_message",
    "display_name": "Mass Message"
  },

  "target": {
    "key": "active_30d",
    "display_name": "Active Last 30 Days"
  },

  "caption": {
    "id": 789,
    "text": "Hey babe, I made this just for you...",
    "performance_score": 85.2,
    "freshness_score": 92.0
  },

  "timing": {
    "scheduled_date": "2025-01-20",
    "scheduled_time": "20:00:00",
    "expires_at": "2025-01-21T08:00:00Z"
  },

  "requirements": {
    "media_type": "video",
    "flyer_required": false,
    "suggested_price": 15.00
  },

  "followups": [
    {
      "send_type_key": "ppv_followup",
      "delay_minutes": 180,
      "caption_id": 901
    }
  ],

  "metadata": {
    "priority": 1,
    "is_follow_up": false,
    "parent_item_id": null
  }
}
```

### Schedule Summary Response

```json
{
  "template_id": 456,
  "creator_id": "alexia",
  "week_start": "2025-01-20",
  "total_items": 42,

  "breakdown": {
    "revenue": 14,
    "engagement": 21,
    "retention": 7
  },

  "daily_counts": {
    "2025-01-20": 6,
    "2025-01-21": 7,
    "2025-01-22": 6,
    "2025-01-23": 6,
    "2025-01-24": 6,
    "2025-01-25": 5,
    "2025-01-26": 6
  },

  "validation": {
    "status": "passed",
    "warnings": [],
    "recommendations": []
  }
}
```

---

## MCP Tools Available

### Creator Data (3 tools)
| Tool | Purpose |
|------|---------|
| `get_active_creators` | List all active creators with performance metrics and tier classification |
| `get_creator_profile` | Load creator analytics, tier, and page type |
| `get_persona_profile` | Tone, emoji style, slang level for consistency |

### Performance & Analytics (3 tools)
| Tool | Purpose |
|------|---------|
| `get_best_timing` | Optimal posting times from history |
| `get_content_type_rankings` | TOP/MID/LOW/AVOID content types |
| `get_performance_trends` | Saturation, opportunity scores, trends |

### Content & Captions (3 tools)
| Tool | Purpose |
|------|---------|
| `get_send_type_captions` | Captions compatible with specific send type |
| `get_top_captions` | High-performing captions with freshness |
| `get_vault_availability` | Available content in creator's vault |

### Send Type Configuration (3 tools)
| Tool | Purpose |
|------|---------|
| `get_send_type_details` | Complete config for a single send type |
| `get_send_types` | All send types filtered by page_type |
| `get_volume_config` | Get daily limits per category and type caps |

### Channels (1 tool)
| Tool | Purpose |
|------|---------|
| `get_channels` | Available channels with targeting support |

### Schedule Operations (2 tools)
| Tool | Purpose |
|------|---------|
| `execute_query` | Execute read-only SQL queries for custom analysis and diagnostics |
| `save_schedule` | Persist schedule to database |

---

## Send Type Categories

### REVENUE (9 types)
Primary goal: Direct monetization

| Key | Display Name | Description |
|-----|--------------|-------------|
| `ppv_unlock` | PPV Unlock | Premium content (pics/videos) for purchase |
| `ppv_wall` | PPV Wall | Wall-posted PPV (FREE pages only) |
| `tip_goal` | Tip Goal | Goal-based tipping (PAID pages only) |
| `vip_program` | VIP Program | Exclusive membership upsell |
| `game_post` | Game Post | Interactive paid games |
| `bundle` | Bundle | Multi-content package |
| `flash_bundle` | Flash Bundle | Time-limited bundle offer |
| `snapchat_bundle` | Snapchat Bundle | Snapchat access package |
| `first_to_tip` | First to Tip | Tip competition incentive |

### ENGAGEMENT (9 types)
Primary goal: Increase interaction and visibility

| Key | Display Name | Description |
|-----|--------------|-------------|
| `link_drop` | Link Drop | Link to profile/content |
| `wall_link_drop` | Wall Link Drop | Link on feed wall |
| `bump_normal` | Bump Normal | Standard conversation bump |
| `bump_descriptive` | Bump Descriptive | Detailed conversation bump |
| `bump_text_only` | Bump Text Only | Text-only interaction |
| `bump_flyer` | Bump Flyer | Visual promotional bump |
| `dm_farm` | DM Farm | DM engagement cultivation |
| `like_farm` | Like Farm | Like engagement cultivation |
| `live_promo` | Live Promo | Live stream promotion |

### RETENTION (4 types)
Primary goal: Reduce churn and reactivate

| Key | Display Name | Description |
|-----|--------------|-------------|
| `renew_on_post` | Renew on Post | Renewal reminder via post |
| `renew_on_message` | Renew on Message | Renewal reminder via DM |
| `ppv_followup` | PPV Followup | Follow-up on unopened PPV |
| `expired_winback` | Expired Winback | Reactivation for churned subs |

---

## Quality Checklist

Before finalizing any schedule, validate:

- [ ] All items have valid send_type_key from approved list
- [ ] Caption types match send type requirements (send_type_caption_requirements)
- [ ] Audience targets are appropriate for page_type and channel
- [ ] Timing respects spacing rules (min 30 min between sends)
- [ ] Daily item counts within volume_config limits
- [ ] Revenue items placed at peak performance times
- [ ] Follow-ups generated for all eligible PPV sends
- [ ] No duplicate captions within the same week
- [ ] Vault contains required content types
- [ ] Persona consistency maintained across all captions

---

## Error Handling

### Common Issues and Resolution

| Error | Cause | Resolution |
|-------|-------|------------|
| No captions available | Freshness filter too strict | Reduce min_freshness threshold |
| Volume exceeded | Too many items allocated | Reduce category_focus intensity |
| Invalid channel | Channel not applicable to send type | Verify channel compatibility with get_channels |
| Timing conflict | Multiple items at same time | Increase minimum spacing |
| Missing content type | Vault doesn't have required media | Flag for content creation |

### Graceful Degradation

1. If caption freshness low: Use top performers with warning
2. If vault incomplete: Skip items requiring unavailable content
3. If timing constrained: Spread items to adjacent days

---

## Examples

### Basic Schedule Generation
```
User: Generate a schedule for alexia

Response: Creates balanced 7-day schedule using all defaults:
- Revenue: ~2/day (14 total)
- Engagement: ~3/day (21 total)
- Retention: ~1/day (7 total)
```

### Revenue-Focused Schedule
```
User: Generate PPV-heavy schedule for alexia starting 2025-01-20

Response: Creates revenue-optimized schedule:
- Revenue: ~3/day (21 total) with PPV at peak times
- Engagement: ~2/day (14 total) as support
- Retention: ~1/day (7 total)
- Extra followups for all PPV items
```

### Custom Send Type Selection
```
User: Create schedule for alexia with only bump_normal and ppv_unlock

Response: Creates targeted schedule:
- Only specified send types allocated
- Volume scaled to type-specific limits
- Followups generated for PPV items only
```

---

## MAX 20X Tier Optimizations

When operating under MAX 20X subscription tier, the schedule generator leverages enhanced capabilities for superior schedule quality.

### Parallel Agent Execution

Enable concurrent execution of independent agents to reduce pipeline latency:

```
PARALLEL EXECUTION MAP:

Phase 1 (Initialization):
  [PARALLEL] get_creator_profile + get_volume_config + get_performance_trends
  [PARALLEL] get_send_types + get_vault_availability + get_best_timing

Phase 3-4 (Content + Targeting):
  content-curator → timing-optimizer → followup-generator
  (These agents operate on different data and can run simultaneously)
```

### Enhanced Reasoning for Complex Decisions

Apply extended reasoning chains for critical decision points:

1. **Saturation Analysis**: Deep analysis of 14-day trends with multi-factor scoring
2. **Caption Selection**: Evaluate top 20 candidates with weighted scoring across 5 dimensions
3. **Timing Optimization**: Consider historical performance by hour AND day-of-week combination
4. **Constraint Resolution**: When conflicts arise, reason through multiple resolution strategies

### Extended Context for Full Week Optimization

Leverage full conversation context to maintain consistency:

- Track all caption selections across the 7-day schedule to maximize diversity
- Maintain running totals of send type allocations for balanced distribution
- Cross-reference timing assignments to identify optimal spacing patterns
- Accumulate warnings and recommendations for comprehensive final report

### Premium Scheduling Algorithms

Enable advanced scheduling features:

| Feature | Standard | MAX 20X |
|---------|----------|---------|
| Caption freshness threshold | 30 days | Dynamic (adapts to pool size) |
| Timing slot granularity | 1 hour | 15 minutes |
| Diversity scoring | Basic | Multi-dimensional (type, content, tone) |
| Fallback strategies | 2 levels | 4 levels with graceful degradation |
| Validation depth | Standard checklist | Extended 25-point validation |
| Recommendation engine | Basic | Predictive with historical patterns |

### Adaptive Volume Optimization

Dynamic adjustment based on real-time performance signals:

```
IF saturation_score > 70 AND opportunity_score < 40:
    # Apply conservative strategy with enhanced engagement
    revenue_multiplier = 0.75
    engagement_multiplier = 1.25
    shift_to_lighter_sends = True

ELSE IF saturation_score < 30 AND opportunity_score > 70:
    # Apply aggressive strategy with premium content
    revenue_multiplier = 1.30
    engagement_multiplier = 1.0
    prioritize_high_performers = True

ELSE:
    # Apply balanced optimization
    apply_standard_allocation()
```

### Quality Assurance Enhancement

Extended validation with proactive issue resolution:

1. **Pre-validation**: Check constraints BEFORE allocation, not just after
2. **Progressive refinement**: Each agent refines previous agent's output
3. **Conflict resolution**: Automatic reallocation when constraints conflict
4. **Confidence scoring**: Each schedule item includes a quality confidence score

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.3.0 | 2025-12-18 | Removed audience targeting system, consolidated to 16 MCP tools, documentation cleanup |
| 2.2.0 | 2025-12-16 | Full OptimizedVolumeResult integration: 13 fields, 8 optimization modules, confidence scoring, DOW multipliers, caption warnings handling |
| 2.1.0 | 2025-12-16 | PPV restructuring: ppv_unlock, ppv_wall, tip_goal, 22-type system |
| 2.0.6 | 2025-12-16 | Wave 6: Testing & Validation - 410 tests, 62.78% coverage, comprehensive test suite, quality gates |
| 2.0.5 | 2025-12-16 | Wave 5: Documentation Excellence - README.md, GETTING_STARTED.md, API_REFERENCE.md, GLOSSARY.md, standardized headers |
| 2.0.4 | 2025-12-16 | Wave 4: Agent & Skill Perfection - 8 agent definitions, proactive triggers, MAX 20X optimizations, orchestration checkpoints |
| 2.0.3 | 2025-12-15 | Wave 3: MCP Modularization & Domain Models - 17 modular tools, SendTypeRegistry, frozen dataclasses, configuration management |
| 2.0.2 | 2025-12-15 | Wave 2: Type Safety & Code Quality - Modern type hints, custom exceptions, structured logging, input validation decorators |
| 2.0.1 | 2025-12-15 | Wave 1: Security Hardening - SQL injection protection, input validation, foreign key enforcement, database integrity |
| 2.0.0 | 2025-01-15 | Enhanced Send Type System - 21-type taxonomy, 5 channels, MCP integration |
| 1.5.0 | 2024-11-01 | Added multi-agent workflow |
| 1.0.0 | 2024-08-01 | Initial release |
