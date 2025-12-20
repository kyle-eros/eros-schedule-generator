# MCP Tool Invocation Patterns

Quick reference for common tool calling sequences in the EROS schedule generation pipeline.

**Version**: 3.0.0

---

## Available MCP Tools (33 Total)

### Creator Data (3 tools)
- `get_creator_profile` - Comprehensive creator data with analytics
- `get_active_creators` - List all active creators
- `get_persona_profile` - Creator tone, archetype, voice

### Performance & Analytics (3 tools)
- `get_performance_trends` - Saturation/opportunity scores
- `get_content_type_rankings` - TOP/MID/LOW/AVOID tiers
- `get_best_timing` - Optimal posting times

### Content & Captions (3 tools)
- `get_top_captions` - Performance-ranked captions
- `get_send_type_captions` - Captions for specific send type
- `get_vault_availability` - Available content types

### Send Type Configuration (3 tools)
- `get_send_types` - 22-type taxonomy
- `get_send_type_details` - Single send type config
- `get_volume_config` - Dynamic volume optimization (10 modules)

### Channels (1 tool)
- `get_channels` - Distribution channels

### Schedule Operations (2 tools)
- `save_schedule` - Persist schedule to database
- `execute_query` - Custom SQL analysis

### Volume Triggers (2 tools)
- `save_volume_triggers` - Persist performance-detected triggers
- `get_active_volume_triggers` - Retrieve active triggers

### Deprecated (1 tool)
- `get_volume_assignment` - Use `get_volume_config()` instead

### Prediction & ML (5 tools)
- `get_caption_predictions` - ML predictions for caption performance
- `save_caption_prediction` - Save prediction for tracking
- `record_prediction_outcome` - Record actual vs predicted
- `get_prediction_weights` - Feature weights for model
- `update_prediction_weights` - Update model weights

### Churn & Win-Back (2 tools)
- `get_churn_risk_scores` - Churn risk by segment
- `get_win_back_candidates` - Win-back campaign candidates

### Attention Scoring (2 tools)
- `get_attention_metrics` - Raw attention metrics
- `get_caption_attention_scores` - Pre-computed attention scores

### A/B Experiments (3 tools)
- `get_active_experiments` - Active experiments
- `save_experiment_results` - Save experiment outcomes
- `update_experiment_allocation` - Update traffic allocation

### Caption Validation (1 tool)
- `validate_caption_structure` - Validate caption against structural rules

### Earnings-Based Selection (2 tools)
- `get_content_type_earnings_ranking` - Content types ranked by earnings
- `get_top_captions_by_earnings` - Top captions by earnings with exclusion support

---

## Common Invocation Sequences

### Phase 1: Performance Analysis
```
1. get_creator_profile(creator_id)
   └─> Extract: page_type, performance_tier, fan_count

2. get_performance_trends(creator_id, period="14d")
   └─> Extract: saturation_score, opportunity_score

3. get_content_type_rankings(creator_id)
   └─> Extract: TOP/MID/LOW/AVOID tiers

4. get_volume_config(creator_id)
   └─> Extract: revenue/engagement/retention per day, weekly distribution

5. get_active_volume_triggers(creator_id)
   └─> Extract: Active adjustments (HIGH_PERFORMER, TRENDING_UP, etc.)

6. save_volume_triggers(creator_id, triggers[])
   └─> Persist new triggers detected from performance analysis
```

### Phase 2: Send Type Allocation
```
1. get_send_types(page_type=<page_type>)
   └─> Filter: Available send types for creator's page type

2. get_volume_config(creator_id)
   └─> Extract: Daily volume targets, DOW multipliers

3. get_content_type_rankings(creator_id)
   └─> Extract: AVOID types to exclude from scheduling
```

### Phase 3: Caption Selection
```
1. get_vault_availability(creator_id)
   └─> Extract: Available content types (vault filter)

2. get_content_type_rankings(creator_id)
   └─> Extract: AVOID types (hard exclusion)

3. get_send_type_captions(creator_id, send_type_key, min_freshness=30)
   └─> Returns: Vault-filtered, AVOID-excluded, freshness-sorted captions

4. get_persona_profile(creator_id)
   └─> Extract: Tone, emoji style for caption selection
```

### Phase 7: Schedule Assembly
```
1. get_channels(supports_targeting=true)
   └─> Extract: Available channels (mass_message, wall_post, etc.)

2. save_schedule(creator_id, week_start, items[])
   └─> Persist: Complete schedule with send types and channels
```

---

## Required Tool Calls by Phase

| Phase | Agent | Mandatory Tools |
|-------|-------|-----------------|
| 1 | performance-analyst | `get_creator_profile`, `get_performance_trends`, `get_content_type_rankings`, `get_volume_config` |
| 2 | send-type-allocator | `get_volume_config`, `get_send_types` |
| 3 | caption-selection-pro | `get_vault_availability`, `get_content_type_rankings`, `get_send_type_captions` |
| 4 | timing-optimizer | `get_best_timing`, `get_creator_profile` (timezone) |
| 5 | followup-generator | None (uses schedule-assembler output) |
| 6 | authenticity-engine | `get_persona_profile` |
| 7 | schedule-assembler | `get_channels`, `save_schedule` |
| 8 | revenue-optimizer | `get_content_type_rankings` |
| 9 | quality-validator | `get_vault_availability`, `get_content_type_rankings`, `get_active_volume_triggers` |

---

## Error Handling Patterns

### Empty Results
```python
# Pattern: Use fallback defaults
result = get_performance_trends(creator_id, "14d")

if not result or result.get("error"):
    # New creator or insufficient data
    saturation_score = 50  # Neutral
    opportunity_score = 50  # Neutral
    confidence_score = 0.3  # Low confidence
```

### Creator Not Found
```python
# Pattern: Verify creator exists first
creators = get_active_creators()
creator_ids = [c["creator_id"] for c in creators["creators"]]

if creator_id not in creator_ids:
    raise ValueError(f"Creator {creator_id} not found or inactive")
```

### Invalid Send Type Key
```python
# Pattern: Validate against available send types
send_types = get_send_types(page_type="paid")
valid_keys = [st["send_type_key"] for st in send_types["send_types"]]

if send_type_key not in valid_keys:
    raise ValueError(f"Invalid send_type_key: {send_type_key}")
```

### Insufficient Captions
```python
# Pattern: Relax filters progressively
captions = get_send_type_captions(creator_id, send_type_key, min_freshness=30)

if captions["count"] < 3:
    # Fallback: Relax freshness
    captions = get_send_type_captions(creator_id, send_type_key, min_freshness=20)

if captions["count"] < 1:
    # Fallback: Use top captions without send_type filter
    captions = get_top_captions(creator_id, min_performance=40, limit=10)
```

---

## Anti-patterns

### 1. Using Deprecated Tools
```python
# WRONG: Deprecated tool
volume = get_volume_assignment(creator_id)

# RIGHT: Use dynamic volume config
volume = get_volume_config(creator_id)
```

### 2. Skipping Vault Filtering
```python
# WRONG: Bypassing vault matrix
captions = execute_query("SELECT * FROM caption_bank WHERE performance_score > 50")

# RIGHT: Use tools with built-in vault filtering
captions = get_send_type_captions(creator_id, send_type_key)
```

### 3. Ignoring AVOID Tier
```python
# WRONG: Not checking AVOID tier
rankings = get_content_type_rankings(creator_id)
# (then using content types without checking avoid_types)

# RIGHT: Exclude AVOID tier explicitly
rankings = get_content_type_rankings(creator_id)
avoid_types = rankings["avoid_types"]
# Filter out AVOID types before caption selection
```

### 4. Manual SQL for Standard Queries
```python
# WRONG: Manual SQL for common queries
result = execute_query("SELECT * FROM creators WHERE creator_id = ?", [creator_id])

# RIGHT: Use dedicated tool
profile = get_creator_profile(creator_id)
```

### 5. Not Using Volume Triggers
```python
# WRONG: Ignoring active volume triggers
volume = get_volume_config(creator_id)
# (then allocating without checking triggers)

# RIGHT: Check and apply active triggers
triggers = get_active_volume_triggers(creator_id)
for trigger in triggers["triggers"]:
    # Apply adjustment_multiplier to content_type volume
    adjust_volume(trigger["content_type"], trigger["adjustment_multiplier"])
```

### 6. Hardcoded Volume Values
```python
# WRONG: Hardcoded volume
ppv_per_day = 4  # Static value

# RIGHT: Dynamic calculation
volume = get_volume_config(creator_id)
ppv_per_day = volume["revenue_items_per_day"]  # Optimized value
```

---

## Tool Call Verification Checklist

Before proceeding to analysis, confirm:
- [ ] `get_creator_profile` returned valid creator data with `page_type`
- [ ] `get_performance_trends` returned saturation/opportunity scores
- [ ] `get_content_type_rankings` returned tier classifications
- [ ] `get_volume_config` returned `OptimizedVolumeResult` with `confidence_score`

**Failure Mode**: If any tool returns an error, log the error and use conservative defaults. Do NOT proceed without attempting ALL tool calls.

---

## Notes

- Always use `send_type_key` consistently (never raw `send_type_id` in logic)
- Always validate `page_type` before including retention sends
- Caption tools automatically apply vault matrix and AVOID tier filtering
- Volume triggers MUST be persisted via `save_volume_triggers()` after detection
- Use `get_volume_config()` for all volume decisions (not deprecated `get_volume_assignment`)
