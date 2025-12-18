# Allocation Rules

Guidelines for distributing send types across the weekly schedule.

---

## ⚠️ CRITICAL: 22-Type Diversity Requirement

**Every weekly schedule MUST include variety from the full 22-type taxonomy.**

### Hard Rules (Violations = Schedule REJECTED)

1. **Minimum 10 unique send_type_keys** across the week
2. **Cannot use ONLY ppv_unlock and bump_normal** - this is INVALID
3. **Revenue variety**: At least 5 different revenue types weekly
4. **Engagement variety**: At least 5 different engagement types weekly
5. **Retention variety** (paid pages): At least 2 different retention types

### Type Distribution Target

| Category | Types Available | Minimum to Use Weekly |
|----------|-----------------|----------------------|
| Revenue | 9 types (page-specific) | 5 types |
| Engagement | 9 types | 5 types |
| Retention | 4 types (paid only) | 2 types |

---

## Volume Tier Defaults

Volume allocation is determined by creator fan count and performance tier.

| Tier | Fan Count | Revenue/Day | Engagement/Day | Retention/Day | Total/Day |
|------|-----------|-------------|----------------|---------------|-----------|
| Low | 0-999 | 3 | 3 | 1 | 7 |
| Mid | 1K-4.9K | 4 | 4 | 2 | 10 |
| High | 5K-14.9K | 6 | 5 | 2 | 13 |
| Ultra | 15K+ | 8 | 6 | 3 | 17 |

### Tier Selection Logic

```
IF fan_count < 1000:
    tier = "Low"
ELSE IF fan_count < 5000:
    tier = "Mid"
ELSE IF fan_count < 15000:
    tier = "High"
ELSE:
    tier = "Ultra"
```

---

## Category Balance Rules

### Target Distribution

| Category | Percentage | Purpose |
|----------|------------|---------|
| Revenue | 50-60% | Primary monetization driver |
| Engagement | 30-35% | Maintain audience connection |
| Retention | 10-15% | Subscriber maintenance (paid pages only) |

### Free Page Adjustment

For **free pages**, retention sends are reduced or eliminated since retention-specific types (renew_on_post, renew_on_message, expired_winback) only apply to paid pages.

Free page distribution:
- Revenue: 55-65%
- Engagement: 35-45%
- Retention: 0-5% (only ppv_followup applicable for free pages)

---

## Daily Allocation Algorithm

### Step 1: Determine Base Volume

```
1. Get creator's volume configuration via get_volume_config() MCP tool
2. Extract base counts: revenue_per_day, engagement_per_day, retention_per_day
3. Calculate total_sends = revenue + engagement + retention
```

### Step 2: Apply Day-of-Week Adjustments

```
CASE day_of_week:
    Friday:
        revenue_per_day += 1  // Weekend prep
    Saturday:
        engagement_per_day += 1  // High activity day
    Sunday:
        revenue_per_day += 1  // High conversion day
    Monday:
        revenue_per_day -= 1  // Lower engagement
```

### Step 3: Check Weekly Limits

Before allocating specific types, check weekly maximums:

```
FOR each send_type with max_per_week limit:
    count_this_week = COUNT(items WHERE send_type AND week)
    IF count_this_week >= max_per_week:
        EXCLUDE send_type from today's allocation
```

Weekly-limited types:
- vip_program: max 1/week
- snapchat_bundle: max 1/week

### Step 4: Allocate Revenue Slots

```
revenue_slots = []
available_revenue_types = [ppv_unlock, ppv_wall, tip_goal, vip_program, game_post,
                           bundle, flash_bundle, snapchat_bundle, first_to_tip]
# Filter by page_type: ppv_wall (FREE only), tip_goal (PAID only)

WHILE len(revenue_slots) < revenue_per_day:
    // Filter by daily limits
    eligible = [t for t in available_revenue_types
                WHERE daily_count(t) < max_per_day]

    // Prioritize by performance score
    selected = weighted_random_select(eligible, weights=performance_scores)

    // Check variety rules
    IF len(revenue_slots) > 0 AND selected == revenue_slots[-1]:
        CONTINUE  // No same type twice in a row

    revenue_slots.append(selected)
    increment_daily_count(selected)
```

### Step 5: Allocate Engagement Slots

```
engagement_slots = []
available_engagement_types = [link_drop, wall_link_drop, bump_normal,
                              bump_descriptive, bump_text_only, bump_flyer,
                              dm_farm, like_farm, live_promo]

WHILE len(engagement_slots) < engagement_per_day:
    eligible = [t for t in available_engagement_types
                WHERE daily_count(t) < max_per_day]

    selected = weighted_random_select(eligible, weights=performance_scores)

    IF len(engagement_slots) > 0 AND selected == engagement_slots[-1]:
        CONTINUE

    engagement_slots.append(selected)
    increment_daily_count(selected)
```

### Step 6: Allocate Retention Slots

```
retention_slots = []
available_retention_types = [ppv_followup]

// Add paid-only types if applicable
IF page_type == "paid":
    available_retention_types += [renew_on_post, renew_on_message,
                                   expired_winback]

WHILE len(retention_slots) < retention_per_day:
    eligible = [t for t in available_retention_types
                WHERE daily_count(t) < max_per_day]

    selected = weighted_random_select(eligible, weights=performance_scores)

    IF len(retention_slots) > 0 AND selected == retention_slots[-1]:
        CONTINUE

    retention_slots.append(selected)
    increment_daily_count(selected)
```

### Step 7: Merge and Schedule

```
all_slots = revenue_slots + engagement_slots + retention_slots

// Interleave categories for variety
scheduled_items = interleave_by_category(all_slots)

// Assign times respecting min_time_between constraints
FOR item in scheduled_items:
    item.scheduled_time = find_next_valid_slot(item.send_type)
```

---

## Day-of-Week Adjustments

### Adjustment Table

| Day | Revenue | Engagement | Retention | Rationale |
|-----|---------|------------|-----------|-----------|
| Monday | -1 | 0 | 0 | Lower post-weekend engagement |
| Tuesday | 0 | 0 | 0 | Standard day |
| Wednesday | 0 | 0 | 0 | Standard day |
| Thursday | 0 | 0 | 0 | Standard day |
| Friday | +1 | 0 | 0 | Weekend prep, pre-pay period |
| Saturday | 0 | +1 | 0 | High activity, leisure browsing |
| Sunday | +1 | 0 | 0 | High conversion, relaxed spending |

### Implementation Notes

- Adjustments are additive to base tier values
- Minimum of 1 per category after adjustment
- Adjustments can be overridden by saturation_score data

---

## Variety Rules

### Consecutive Send Rule

**No same send_type in 2 consecutive slots.**

```
IF previous_item.send_type == current_item.send_type:
    REJECT current_item
    SELECT alternative send_type
```

### Daily Maximum Rule

**Maximum 2 of same send_type per day** (unless type-specific limit is lower).

```
FOR each send_type:
    IF daily_count(send_type) >= 2:
        EXCLUDE from remaining slots
    IF daily_count(send_type) >= send_type.max_per_day:
        EXCLUDE from remaining slots
```

### Special Type Limits

| Send Type | Daily Limit | Weekly Limit |
|-----------|-------------|--------------|
| bundle | 1 | - |
| flash_bundle | 1 | - |
| game_post | 1 | - |
| vip_program | 1 | 1 |
| snapchat_bundle | 1 | 1 |
| like_farm | 1 | - |

### Category Interleaving

To prevent category clustering, interleave items:

```
PATTERN: Revenue -> Engagement -> Retention -> Revenue -> ...

// Example for 10 items (4R, 4E, 2Ret):
// R1 -> E1 -> R2 -> E2 -> Ret1 -> R3 -> E3 -> R4 -> E4 -> Ret2
```

---

## Time Spacing Requirements

### Minimum Time Between Same Type

| Send Type | Min Between |
|-----------|-------------|
| ppv_unlock | 2 hours |
| ppv_wall | 3 hours |
| tip_goal | 4 hours |
| vip_program | 24 hours |
| game_post | 4 hours |
| bundle | 3 hours |
| flash_bundle | 6 hours |
| snapchat_bundle | 24 hours |
| first_to_tip | 6 hours |
| link_drop | 2 hours |
| wall_link_drop | 3 hours |
| bump_normal | 1 hour |
| bump_descriptive | 2 hours |
| bump_text_only | 2 hours |
| bump_flyer | 4 hours |
| dm_farm | 4 hours |
| like_farm | 24 hours |
| live_promo | 2 hours |
| renew_on_post | 12 hours |
| renew_on_message | 24 hours |
| ppv_followup | 1 hour |
| expired_winback | 24 hours |

### Time Slot Selection Algorithm

```
FUNCTION find_next_valid_slot(send_type, existing_schedule):
    last_same_type = find_last_occurrence(send_type, existing_schedule)
    min_gap = send_type.min_time_between

    IF last_same_type EXISTS:
        earliest_valid = last_same_type.time + min_gap
    ELSE:
        earliest_valid = schedule_start_time  // Usually 8:00 AM

    // Find next available slot
    FOR slot in available_time_slots:
        IF slot.time >= earliest_valid:
            IF not conflicts_with_adjacent(slot, send_type):
                RETURN slot

    RETURN None  // No valid slot found
```

---

## Saturation-Based Adjustments

When saturation_score data is available from performance tracking:

### High Saturation (Score > 70)

```
IF saturation_score > 70:
    // Audience is overexposed
    revenue_per_day -= 1
    engagement_per_day += 1
    // Shift toward lighter touch
```

### Low Saturation (Score < 30)

```
IF saturation_score < 30:
    // Opportunity to increase volume
    revenue_per_day += 1
    // Capitalize on engagement headroom
```

### Opportunity Score Integration

```
IF opportunity_score > 60:
    // High potential for revenue
    PRIORITIZE: ppv_unlock, bundle, flash_bundle

IF opportunity_score < 40:
    // Focus on engagement building
    PRIORITIZE: bump_normal, bump_descriptive, dm_farm
```

---

## Validation Checklist

Before finalizing daily allocation:

- [ ] Total items <= tier maximum
- [ ] Revenue items within 50-60% of total
- [ ] Engagement items within 30-35% of total
- [ ] Retention items within 10-15% of total
- [ ] No weekly limits exceeded
- [ ] No daily limits exceeded per type
- [ ] No consecutive same-type items
- [ ] All time gaps meet minimum requirements
- [ ] Paid-only types excluded for free pages
- [ ] Follow-ups scheduled for eligible items
