# Allocation Algorithm Reference

**Authoritative specification for send type allocation to schedule slots.**

This document defines the complete logic for distributing send types across a creator's weekly schedule, including volume tier calculations, category distribution, day-of-week adjustments, variety rules, and output formatting.

---

## ⚠️ CRITICAL: 22-Type Diversity Requirement

**A valid weekly schedule MUST use variety from the full 22-type taxonomy.**

### Mandatory Diversity Rules

| Requirement | Minimum | Description |
|-------------|---------|-------------|
| Unique Types | **10+** | At least 10 different send_type_keys across the week |
| Revenue Types | **5 of 9** | Cannot just use ppv_unlock repeatedly |
| Engagement Types | **5 of 9** | Cannot just use bump_normal repeatedly |
| Retention Types (paid) | **2 of 4** | Must include variety in retention |

### Diversity Validation (Run BEFORE finalizing)

```python
def validate_weekly_diversity(allocation: dict) -> bool:
    """
    REJECT schedules that lack type diversity.
    """
    all_types = set()
    for day in allocation.values():
        for item in day.get("items", []):
            all_types.add(item["send_type"])

    # Hard rejection criteria
    if len(all_types) < 10:
        raise ValueError(f"INVALID: Only {len(all_types)} unique types. Need 10+")

    if all_types == {"ppv_unlock", "bump_normal"}:
        raise ValueError("INVALID: Only ppv and bump. Use full 22-type system.")

    return True
```

---

## Table of Contents

1. [Volume Tier System](#volume-tier-system)
2. [Category Distribution Algorithm](#category-distribution-algorithm)
3. [Day-of-Week Adjustments](#day-of-week-adjustments)
4. [Variety and Constraint Rules](#variety-and-constraint-rules)
5. [Complete Allocation Pipeline](#complete-allocation-pipeline)
6. [Output Format Specification](#output-format-specification)
7. [Decision Trees](#decision-trees)
8. [Validation Checklist](#validation-checklist)

---

## Volume Tier System

### Tier Definitions

Volume tiers determine base daily allocation counts based on creator fan count.

| Tier | Fan Count | Revenue/Day | Engagement/Day | Retention/Day | Total/Day |
|------|-----------|-------------|----------------|---------------|-----------|
| Low | 0-999 | 3 | 3 | 1 | 7 |
| Mid | 1,000-4,999 | 4 | 4 | 2 | 10 |
| High | 5,000-14,999 | 6 | 5 | 2 | 13 |
| Ultra | 15,000+ | 8 | 6 | 3 | 17 |

### Tier Selection Algorithm

```python
def get_volume_tier(fan_count: int) -> dict:
    """
    Determine volume tier and base allocations from fan count.

    Returns:
        dict with tier name and category counts
    """
    if fan_count < 1000:
        return {
            "tier": "Low",
            "fan_range": "0-999",
            "revenue_per_day": 3,
            "engagement_per_day": 3,
            "retention_per_day": 1,
            "total_per_day": 7
        }
    elif fan_count < 5000:
        return {
            "tier": "Mid",
            "fan_range": "1K-4.9K",
            "revenue_per_day": 4,
            "engagement_per_day": 4,
            "retention_per_day": 2,
            "total_per_day": 10
        }
    elif fan_count < 15000:
        return {
            "tier": "High",
            "fan_range": "5K-14.9K",
            "revenue_per_day": 6,
            "engagement_per_day": 5,
            "retention_per_day": 2,
            "total_per_day": 13
        }
    else:
        return {
            "tier": "Ultra",
            "fan_range": "15K+",
            "revenue_per_day": 8,
            "engagement_per_day": 6,
            "retention_per_day": 3,
            "total_per_day": 17
        }
```

### Category Percentage Targets

| Category | Target % | Purpose | Notes |
|----------|----------|---------|-------|
| Revenue | 50-60% | Primary monetization | Core business driver |
| Engagement | 30-35% | Audience connection | Maintains loyalty |
| Retention | 10-15% | Subscriber maintenance | Paid pages only (full) |

**Free Page Adjustment:**
```python
def adjust_for_free_page(config: dict) -> dict:
    """
    Free pages have limited retention options.
    Reallocate retention slots to engagement.
    """
    if page_type == "free":
        # Only ppv_message and ppv_followup applicable
        # Reduce retention, increase engagement
        reallocation = config["retention_per_day"] - 1
        config["retention_per_day"] = max(1, config["retention_per_day"] - reallocation)
        config["engagement_per_day"] += reallocation
    return config
```

---

## Category Distribution Algorithm

### Revenue Allocation (50-60% of content)

Revenue sends are the primary monetization mechanism. Allocation follows strict priority and composition rules.

#### Revenue Type Hierarchy

| Priority | Send Type | Daily Max | Weekly Max | Min Between | Notes |
|----------|-----------|-----------|------------|-------------|-------|
| 1 | ppv_unlock | 4 | - | 2 hours | Core revenue driver |
| 2 | ppv_wall | 3 | - | 3 hours | FREE pages only |
| 3 | tip_goal | 2 | 3 | 4 hours | PAID pages only |
| 4 | bundle | 2 | - | 3 hours | Standard offering |
| 5 | flash_bundle | 1 | - | 6 hours | Urgency play |
| 6 | game_post | 1 | - | 4 hours | Gamification |
| 7 | first_to_tip | 1 | - | 6 hours | Competition |
| 8 | vip_program | 1 | 1 | 24 hours | Premium, weekly limit |
| 9 | snapchat_bundle | 1 | 1 | 24 hours | Nostalgia, weekly limit |

#### Revenue Composition Rules

```python
def allocate_revenue_slots(revenue_per_day: int, day_context: dict) -> list:
    """
    Allocate revenue slots following composition rules:

    MUST include: 2-3 ppv_unlock (core revenue)
    SHOULD include: 0-1 bundle OR game_post OR flash_bundle
    MAY include: 0-1 vip_program (if not posted this week)
    FREE pages: Use ppv_wall instead of tip_goal
    PAID pages: Use tip_goal instead of ppv_wall

    Args:
        revenue_per_day: Number of revenue slots to fill
        day_context: Contains week_history, day_of_week, page_type

    Returns:
        List of allocated send_type keys
    """
    allocation = []
    remaining = revenue_per_day

    # STEP 1: Allocate mandatory PPV unlock (2-3)
    ppv_count = min(3, max(2, remaining - 2))  # Leave room for variety
    for _ in range(ppv_count):
        if day_context["page_type"] == "free" and remaining > ppv_count:
            # FREE pages can use ppv_wall for some PPV slots
            allocation.append("ppv_wall")
        else:
            allocation.append("ppv_unlock")
    remaining -= ppv_count

    # STEP 2: Allocate secondary revenue type (bundle/game/flash)
    if remaining > 0:
        secondary_types = get_eligible_secondary_revenue(day_context)
        if secondary_types:
            selected = weighted_select(secondary_types, day_context["performance_scores"])
            allocation.append(selected)
            remaining -= 1

    # STEP 3: Consider premium weekly types
    if remaining > 0 and not day_context.get("vip_used_this_week"):
        if should_include_vip(day_context):
            allocation.append("vip_program")
            remaining -= 1

    if remaining > 0 and not day_context.get("snapchat_used_this_week"):
        if should_include_snapchat(day_context):
            allocation.append("snapchat_bundle")
            remaining -= 1

    # STEP 4: Fill remaining with ppv_unlock or bundles
    while remaining > 0:
        if count_in_allocation(allocation, "ppv_unlock") < 4:
            allocation.append("ppv_unlock")
        elif count_in_allocation(allocation, "bundle") < 2:
            allocation.append("bundle")
        else:
            allocation.append("ppv_unlock")  # Default fallback
        remaining -= 1

    return allocation


def get_eligible_secondary_revenue(day_context: dict) -> list:
    """
    Get eligible secondary revenue types based on daily limits.
    """
    candidates = []
    daily_counts = day_context.get("daily_counts", {})

    if daily_counts.get("bundle", 0) < 2:
        candidates.append({"type": "bundle", "weight": 1.0})
    if daily_counts.get("game_post", 0) < 1:
        candidates.append({"type": "game_post", "weight": 0.8})
    if daily_counts.get("flash_bundle", 0) < 1:
        candidates.append({"type": "flash_bundle", "weight": 0.7})
    if daily_counts.get("first_to_tip", 0) < 1:
        candidates.append({"type": "first_to_tip", "weight": 0.6})

    return candidates
```

### Engagement Allocation (30-35% of content)

Engagement sends maintain audience connection through varied touchpoints.

#### Engagement Type Distribution

| Type | Target Share | Daily Max | Min Between | Effort Level |
|------|--------------|-----------|-------------|--------------|
| bump_normal | 40% | 5 | 1 hour | Low |
| bump_descriptive | 20% | 3 | 2 hours | Medium |
| bump_text_only | 20% | 4 | 2 hours | Low |
| bump_flyer | 10% | 2 | 4 hours | High |
| dm_farm | 5% | 2 | 4 hours | Medium |
| like_farm | 5% | 1 | 24 hours | Low |
| link_drop | Variable | 3 | 2 hours | Low |
| wall_link_drop | Variable | 2 | 3 hours | Low |
| live_promo | As needed | 2 | 2 hours | Medium |

#### Engagement Composition Rules

```python
def allocate_engagement_slots(engagement_per_day: int, day_context: dict) -> list:
    """
    Allocate engagement slots with proper bump type distribution.

    Target distribution:
    - 40% bump_normal (quick, easy, frequent)
    - 20% bump_descriptive (storytelling)
    - 20% bump_text_only (no media needed)
    - 10% bump_flyer (high production)
    - 10% dm_farm/like_farm (interaction drivers)

    Plus: link_drops for active campaigns

    Args:
        engagement_per_day: Number of engagement slots to fill
        day_context: Contains active_campaigns, performance_scores

    Returns:
        List of allocated send_type keys
    """
    allocation = []
    remaining = engagement_per_day

    # STEP 1: Allocate link_drops for active campaigns
    active_campaigns = day_context.get("active_campaigns", [])
    link_drop_count = min(2, len(active_campaigns), remaining)
    for _ in range(link_drop_count):
        allocation.append("link_drop")
    remaining -= link_drop_count

    # STEP 2: Calculate bump distribution
    bump_budget = remaining

    # bump_normal: 40% of bumps
    normal_count = max(1, int(bump_budget * 0.4))
    for _ in range(min(normal_count, 5)):  # Max 5/day
        if remaining > 0:
            allocation.append("bump_normal")
            remaining -= 1

    # bump_descriptive: 20% of bumps
    descriptive_count = max(1, int(bump_budget * 0.2))
    for _ in range(min(descriptive_count, 3)):  # Max 3/day
        if remaining > 0:
            allocation.append("bump_descriptive")
            remaining -= 1

    # bump_text_only: 20% of bumps (no media needed - useful when vault limited)
    text_count = max(0, int(bump_budget * 0.2))
    for _ in range(min(text_count, 4)):  # Max 4/day
        if remaining > 0:
            allocation.append("bump_text_only")
            remaining -= 1

    # bump_flyer: 10% (high impact, high effort)
    if remaining > 0 and day_context.get("daily_counts", {}).get("bump_flyer", 0) < 2:
        allocation.append("bump_flyer")
        remaining -= 1

    # STEP 3: Interaction drivers (dm_farm, like_farm)
    if remaining > 0:
        daily_counts = day_context.get("daily_counts", {})
        if daily_counts.get("dm_farm", 0) < 2:
            allocation.append("dm_farm")
            remaining -= 1

    if remaining > 0:
        daily_counts = day_context.get("daily_counts", {})
        if daily_counts.get("like_farm", 0) < 1:
            allocation.append("like_farm")
            remaining -= 1

    # STEP 4: Fill remaining with bump_normal (most flexible)
    while remaining > 0:
        allocation.append("bump_normal")
        remaining -= 1

    return allocation
```

### Retention Allocation (10-15% of content)

Retention sends focus on subscriber maintenance. **Several types are paid-page only.**

#### Retention Type Rules

| Type | Daily Max | Page Type | Target Audience | Notes |
|------|-----------|-----------|-----------------|-------|
| expired_winback | 1 | paid only | expired | Win back lapsed subs |
| renew_on_message | 1 | paid only | renew_off | Convert to auto-renew |
| renew_on_post | 2 | paid only | all | Wall visibility |
| ppv_followup | 4 | both | non_purchasers | Auto-generated closers |

#### Retention Composition Rules

```python
def allocate_retention_slots(retention_per_day: int, page_type: str, day_context: dict) -> list:
    """
    Allocate retention slots based on page type.

    For PAID pages:
    - Daily: 1 expired_winback (win back lapsed)
    - Daily: 1 renew_on_message (target renew_off audience)
    - As needed: ppv_followup (auto-generated for PPV sends)

    For FREE pages:
    - Only ppv_followup applicable (auto-generated)

    Args:
        retention_per_day: Number of retention slots to fill
        page_type: "paid" or "free"
        day_context: Contains daily_counts, performance_scores

    Returns:
        List of allocated send_type keys
    """
    allocation = []
    remaining = retention_per_day

    if page_type == "paid":
        # STEP 1: Always include expired_winback (paid pages)
        if remaining > 0:
            allocation.append("expired_winback")
            remaining -= 1

        # STEP 2: Include renew_on_message (targeting renew_off)
        if remaining > 0:
            allocation.append("renew_on_message")
            remaining -= 1

        # STEP 3: Fill remaining with renew_on_post
        while remaining > 0:
            daily_counts = day_context.get("daily_counts", {})
            if daily_counts.get("renew_on_post", 0) < 2:
                allocation.append("renew_on_post")
            else:
                # Already at limit, use expired_winback if possible
                allocation.append("expired_winback")
            remaining -= 1

    else:  # page_type == "free"
        # ppv_followup is auto-generated, minimal manual retention for free pages
        # This shouldn't typically be called for free pages with retention quota
        while remaining > 0:
            # No applicable retention types for free pages
            # ppv_followup is generated automatically, not allocated here
            remaining -= 1  # Skip allocation

    return allocation
```

---

## Day-of-Week Adjustments

### Adjustment Matrix

| Day | Revenue Adj | Engagement Adj | Retention Adj | Rationale |
|-----|-------------|----------------|---------------|-----------|
| Monday | -1 | 0 | 0 | Lower post-weekend engagement |
| Tuesday | 0 | 0 | 0 | Standard baseline |
| Wednesday | 0 | 0 | 0 | Standard baseline |
| Thursday | 0 | 0 | 0 | Standard baseline |
| Friday | +1 | 0 | 0 | Weekend prep, payday |
| Saturday | 0 | +1 | 0 | High activity, leisure browsing |
| Sunday | +1 | 0 | 0 | High conversion, relaxed spending |

### Adjustment Algorithm

```python
def apply_day_adjustments(base_config: dict, day_of_week: str) -> dict:
    """
    Apply day-of-week adjustments to base allocation.

    Adjustments are additive. Minimum of 1 per category after adjustment.

    Args:
        base_config: Base tier allocation config
        day_of_week: "Monday", "Tuesday", etc.

    Returns:
        Adjusted config with modified category counts
    """
    config = base_config.copy()

    ADJUSTMENTS = {
        "Monday": {"revenue": -1, "engagement": 0, "retention": 0},
        "Tuesday": {"revenue": 0, "engagement": 0, "retention": 0},
        "Wednesday": {"revenue": 0, "engagement": 0, "retention": 0},
        "Thursday": {"revenue": 0, "engagement": 0, "retention": 0},
        "Friday": {"revenue": +1, "engagement": 0, "retention": 0},
        "Saturday": {"revenue": 0, "engagement": +1, "retention": 0},
        "Sunday": {"revenue": +1, "engagement": 0, "retention": 0},
    }

    adj = ADJUSTMENTS.get(day_of_week, {"revenue": 0, "engagement": 0, "retention": 0})

    # Apply adjustments with minimum floor of 1
    config["revenue_per_day"] = max(1, config["revenue_per_day"] + adj["revenue"])
    config["engagement_per_day"] = max(1, config["engagement_per_day"] + adj["engagement"])
    config["retention_per_day"] = max(1, config["retention_per_day"] + adj["retention"])

    # Recalculate total
    config["total_per_day"] = (
        config["revenue_per_day"] +
        config["engagement_per_day"] +
        config["retention_per_day"]
    )

    return config
```

### Day Characteristics Reference

| Day | Revenue Behavior | Engagement Pattern | Optimal Send Types |
|-----|------------------|--------------------|--------------------|
| Monday | Slower conversion | Catch-up browsing | bump_normal, dm_farm |
| Tuesday | Standard | Standard | Balanced mix |
| Wednesday | Standard | Mid-week peak | ppv_video, bumps |
| Thursday | Standard | Pre-weekend buildup | bundles, game_post |
| Friday | High (payday) | High activity | ppv_video, flash_bundle |
| Saturday | High conversion | Peak leisure | ppv_video, bundle, bumps |
| Sunday | Highest conversion | Extended browsing | ppv_video x3, game_post |

---

## Variety and Constraint Rules

### Rule 1: No Consecutive Same Type

**No same send_type in 2 consecutive slots.**

```python
def check_consecutive_rule(allocation: list, candidate: str, position: int) -> bool:
    """
    Verify candidate doesn't violate consecutive rule.

    Returns:
        True if candidate is valid, False if violates rule
    """
    if position == 0:
        return True  # First slot, no previous

    previous = allocation[position - 1]

    if previous == candidate:
        return False  # Same type twice in a row - REJECT

    return True
```

### Rule 2: Daily Maximum Per Type

**Maximum 2 of same send_type per day (unless type-specific limit is lower).**

```python
# Type-specific daily maximums (override default of 2)
DAILY_MAXIMUMS = {
    # Revenue
    "ppv_unlock": 4,
    "ppv_wall": 3,
    "tip_goal": 2,
    "vip_program": 1,
    "game_post": 1,
    "bundle": 2,
    "flash_bundle": 1,
    "snapchat_bundle": 1,
    "first_to_tip": 1,

    # Engagement
    "link_drop": 3,
    "wall_link_drop": 2,
    "bump_normal": 5,
    "bump_descriptive": 3,
    "bump_text_only": 4,
    "bump_flyer": 2,
    "dm_farm": 2,
    "like_farm": 1,
    "live_promo": 2,

    # Retention
    "renew_on_post": 2,
    "renew_on_message": 1,
    "ppv_followup": 4,
    "expired_winback": 1,
}

def check_daily_limit(daily_counts: dict, send_type: str) -> bool:
    """
    Check if send_type can still be added today.

    Returns:
        True if under daily limit, False if at/over limit
    """
    current_count = daily_counts.get(send_type, 0)
    max_allowed = DAILY_MAXIMUMS.get(send_type, 2)  # Default max 2

    return current_count < max_allowed
```

### Rule 3: Weekly Limits

**Certain premium types have weekly maximums.**

```python
# Weekly maximum limits
WEEKLY_MAXIMUMS = {
    "vip_program": 1,
    "snapchat_bundle": 1,
    "tip_goal": 3,
}

def check_weekly_limit(week_history: dict, send_type: str) -> bool:
    """
    Check if send_type can still be added this week.

    Returns:
        True if under weekly limit, False if at/over limit
    """
    if send_type not in WEEKLY_MAXIMUMS:
        return True  # No weekly limit for this type

    current_count = week_history.get(send_type, 0)
    max_allowed = WEEKLY_MAXIMUMS[send_type]

    return current_count < max_allowed
```

### Rule 4: Special Type Restrictions

**bundle/flash_bundle/game_post: Maximum 1 per day (combined ceiling for "special" revenue)**

```python
def check_special_revenue_limit(daily_counts: dict) -> list:
    """
    Only one "special" revenue type per day.

    Special types: bundle, flash_bundle, game_post

    Returns:
        List of still-eligible special types
    """
    special_types = ["bundle", "flash_bundle", "game_post"]
    special_used_today = sum(
        daily_counts.get(t, 0) for t in special_types
    )

    if special_used_today >= 1:
        return []  # No more special types today

    # Return only those not yet used
    return [t for t in special_types if daily_counts.get(t, 0) == 0]
```

### Rule 5: Link Drop Campaign Requirement

**link_drop only for active campaigns**

```python
def can_use_link_drop(active_campaigns: list) -> bool:
    """
    Link drops require active campaign context.

    Returns:
        True if there are active campaigns, False otherwise
    """
    return len(active_campaigns) > 0
```

### Rule 6: Page Type Restrictions

**Certain retention types are paid-page only.**

```python
PAID_ONLY_TYPES = [
    "tip_goal",
    "renew_on_post",
    "renew_on_message",
    "expired_winback",
]

FREE_ONLY_TYPES = [
    "ppv_wall",
]

def filter_by_page_type(send_types: list, page_type: str) -> list:
    """
    Remove send types not applicable to this page type.

    Returns:
        Filtered list of eligible send types
    """
    if page_type == "free":
        return [t for t in send_types if t not in PAID_ONLY_TYPES]
    elif page_type == "paid":
        return [t for t in send_types if t not in FREE_ONLY_TYPES]
    return send_types
```

---

## Complete Allocation Pipeline

### Master Allocation Algorithm

```python
def allocate_day(
    creator_id: str,
    date: str,
    volume_config: dict,
    day_context: dict
) -> dict:
    """
    Complete daily allocation pipeline.

    Pipeline stages:
    1. Get base tier allocation
    2. Apply day-of-week adjustments
    3. Apply page type adjustments
    4. Check weekly limits
    5. Allocate revenue slots
    6. Allocate engagement slots
    7. Allocate retention slots
    8. Merge and interleave
    9. Assign time slots
    10. Validate allocation

    Args:
        creator_id: Creator identifier
        date: Date string (YYYY-MM-DD)
        volume_config: Volume tier configuration
        day_context: Context including:
            - page_type: "paid" or "free"
            - week_history: Send counts this week
            - daily_counts: Send counts today (starts empty)
            - active_campaigns: List of active campaign links
            - performance_scores: Dict of send_type -> performance
            - saturation_score: Optional saturation metric
            - opportunity_score: Optional opportunity metric

    Returns:
        Allocation dict with items list
    """

    # STAGE 1: Get base tier allocation
    config = volume_config.copy()

    # STAGE 2: Apply day-of-week adjustments
    day_of_week = get_day_of_week(date)  # "Monday", "Tuesday", etc.
    config = apply_day_adjustments(config, day_of_week)

    # STAGE 3: Apply page type adjustments
    if day_context["page_type"] == "free":
        config = adjust_for_free_page(config)

    # STAGE 4: Apply saturation-based adjustments (if available)
    if day_context.get("saturation_score"):
        config = apply_saturation_adjustment(config, day_context["saturation_score"])

    # STAGE 5: Allocate revenue slots
    revenue_slots = allocate_revenue_slots(
        config["revenue_per_day"],
        day_context
    )

    # Update daily counts after revenue allocation
    for send_type in revenue_slots:
        day_context["daily_counts"][send_type] = day_context["daily_counts"].get(send_type, 0) + 1

    # STAGE 6: Allocate engagement slots
    engagement_slots = allocate_engagement_slots(
        config["engagement_per_day"],
        day_context
    )

    # Update daily counts after engagement allocation
    for send_type in engagement_slots:
        day_context["daily_counts"][send_type] = day_context["daily_counts"].get(send_type, 0) + 1

    # STAGE 7: Allocate retention slots
    retention_slots = allocate_retention_slots(
        config["retention_per_day"],
        day_context["page_type"],
        day_context
    )

    # STAGE 8: Merge and interleave by category
    all_slots = interleave_categories(revenue_slots, engagement_slots, retention_slots)

    # STAGE 9: Enforce variety rules (swap if consecutive same type)
    all_slots = enforce_variety_rules(all_slots)

    # STAGE 10: Assign time slots
    scheduled_items = assign_time_slots(all_slots, date, day_context)

    # STAGE 11: Validate allocation
    validation = validate_allocation(scheduled_items, config, day_context)

    return {
        "date": date,
        "day_of_week": day_of_week,
        "tier": config["tier"],
        "category_counts": {
            "revenue": len(revenue_slots),
            "engagement": len(engagement_slots),
            "retention": len(retention_slots),
            "total": len(all_slots)
        },
        "items": scheduled_items,
        "validation": validation
    }
```

### Category Interleaving Algorithm

```python
def interleave_categories(
    revenue: list,
    engagement: list,
    retention: list
) -> list:
    """
    Interleave categories to prevent clustering.

    Pattern: Revenue -> Engagement -> Retention -> Revenue -> ...

    Example for 10 items (4R, 4E, 2Ret):
    R1 -> E1 -> R2 -> E2 -> Ret1 -> R3 -> E3 -> R4 -> E4 -> Ret2

    Returns:
        Interleaved list of send types with category tags
    """
    result = []
    r_idx, e_idx, ret_idx = 0, 0, 0

    # Calculate interleave ratios
    total = len(revenue) + len(engagement) + len(retention)

    while len(result) < total:
        # Revenue turn
        if r_idx < len(revenue):
            result.append({
                "send_type": revenue[r_idx],
                "category": "revenue"
            })
            r_idx += 1

        # Engagement turn
        if e_idx < len(engagement) and len(result) < total:
            result.append({
                "send_type": engagement[e_idx],
                "category": "engagement"
            })
            e_idx += 1

        # Retention turn (less frequent)
        # Insert retention after every 3-4 items
        if ret_idx < len(retention) and len(result) % 4 == 3:
            result.append({
                "send_type": retention[ret_idx],
                "category": "retention"
            })
            ret_idx += 1

    # Add any remaining retention
    while ret_idx < len(retention):
        result.append({
            "send_type": retention[ret_idx],
            "category": "retention"
        })
        ret_idx += 1

    return result


def enforce_variety_rules(items: list) -> list:
    """
    Swap adjacent items if same send_type appears consecutively.

    Returns:
        List with variety rules enforced
    """
    result = items.copy()

    for i in range(1, len(result)):
        if result[i]["send_type"] == result[i-1]["send_type"]:
            # Find nearest different type to swap with
            for j in range(i+1, len(result)):
                if result[j]["send_type"] != result[i]["send_type"]:
                    result[i], result[j] = result[j], result[i]
                    break

    return result
```

### Time Slot Assignment Algorithm

```python
# Minimum time between same send type (in minutes)
MIN_TIME_BETWEEN = {
    "ppv_unlock": 120,
    "ppv_wall": 180,
    "tip_goal": 240,
    "vip_program": 1440,  # 24 hours
    "game_post": 240,
    "bundle": 180,
    "flash_bundle": 360,
    "snapchat_bundle": 1440,
    "first_to_tip": 360,
    "link_drop": 120,
    "wall_link_drop": 180,
    "bump_normal": 60,
    "bump_descriptive": 120,
    "bump_text_only": 120,
    "bump_flyer": 240,
    "dm_farm": 240,
    "like_farm": 1440,
    "live_promo": 120,
    "renew_on_post": 720,  # 12 hours
    "renew_on_message": 1440,
    "ppv_followup": 60,
    "expired_winback": 1440,
}

def assign_time_slots(
    items: list,
    date: str,
    day_context: dict
) -> list:
    """
    Assign scheduled times to each item.

    Operating hours: 8:00 AM - 11:00 PM (15 hours = 900 minutes)

    Returns:
        List of items with scheduled_time assigned
    """
    START_HOUR = 8   # 8:00 AM
    END_HOUR = 23    # 11:00 PM
    OPERATING_MINUTES = (END_HOUR - START_HOUR) * 60  # 900 minutes

    # Calculate base spacing
    item_count = len(items)
    base_spacing = OPERATING_MINUTES // (item_count + 1)

    scheduled = []
    last_times = {}  # Track last time for each send_type
    current_minute = 0

    for idx, item in enumerate(items):
        send_type = item["send_type"]

        # Calculate earliest valid time
        min_gap = MIN_TIME_BETWEEN.get(send_type, 60)

        if send_type in last_times:
            earliest = last_times[send_type] + min_gap
        else:
            earliest = 0

        # Target time based on even distribution
        target_time = base_spacing * (idx + 1)

        # Use later of target or earliest valid
        scheduled_minute = max(target_time, earliest)

        # Convert to time string
        hours = START_HOUR + (scheduled_minute // 60)
        minutes = scheduled_minute % 60
        time_str = f"{hours:02d}:{minutes:02d}"

        # Update tracking
        last_times[send_type] = scheduled_minute

        scheduled.append({
            "slot": idx + 1,
            "send_type": send_type,
            "category": item["category"],
            "scheduled_date": date,
            "scheduled_time": time_str,
            "priority": idx + 1
        })

    return scheduled
```

### Saturation-Based Adjustment

```python
def apply_saturation_adjustment(config: dict, saturation_score: float) -> dict:
    """
    Adjust allocation based on audience saturation.

    High saturation (>70): Reduce revenue, increase engagement
    Low saturation (<30): Opportunity to increase revenue

    Returns:
        Adjusted config
    """
    adjusted = config.copy()

    if saturation_score > 70:
        # Audience overexposed - pull back revenue
        adjusted["revenue_per_day"] = max(1, adjusted["revenue_per_day"] - 1)
        adjusted["engagement_per_day"] += 1

    elif saturation_score < 30:
        # Room to grow - capitalize on opportunity
        adjusted["revenue_per_day"] += 1

    # Recalculate total
    adjusted["total_per_day"] = (
        adjusted["revenue_per_day"] +
        adjusted["engagement_per_day"] +
        adjusted["retention_per_day"]
    )

    return adjusted
```

---

## Output Format Specification

### Daily Allocation Output

```python
allocation = {
    "2025-12-16": {
        "day_of_week": "Monday",
        "tier": "Mid",
        "category_counts": {
            "revenue": 3,      # Base 4, -1 for Monday
            "engagement": 4,
            "retention": 2,
            "total": 9
        },
        "items": [
            {
                "slot": 1,
                "send_type": "ppv_video",
                "category": "revenue",
                "scheduled_date": "2025-12-16",
                "scheduled_time": "08:30",
                "priority": 1
            },
            {
                "slot": 2,
                "send_type": "bump_normal",
                "category": "engagement",
                "scheduled_date": "2025-12-16",
                "scheduled_time": "09:30",
                "priority": 2
            },
            {
                "slot": 3,
                "send_type": "ppv_video",
                "category": "revenue",
                "scheduled_date": "2025-12-16",
                "scheduled_time": "11:00",
                "priority": 3
            },
            # ... remaining items
        ],
        "validation": {
            "passed": true,
            "checks": {
                "total_within_tier": true,
                "revenue_percentage": 33.3,
                "no_consecutive_duplicates": true,
                "daily_limits_respected": true,
                "time_gaps_valid": true
            }
        }
    }
}
```

### Weekly Allocation Output

```python
weekly_allocation = {
    "creator_id": "creator_123",
    "week_start": "2025-12-16",
    "week_end": "2025-12-22",
    "page_type": "paid",
    "volume_tier": "Mid",
    "total_items": 68,
    "category_totals": {
        "revenue": 30,
        "engagement": 28,
        "retention": 10
    },
    "daily_allocations": {
        "2025-12-16": { ... },  # Monday
        "2025-12-17": { ... },  # Tuesday
        "2025-12-18": { ... },  # Wednesday
        "2025-12-19": { ... },  # Thursday
        "2025-12-20": { ... },  # Friday
        "2025-12-21": { ... },  # Saturday
        "2025-12-22": { ... },  # Sunday
    },
    "weekly_limits_used": {
        "vip_program": 1,
        "snapchat_bundle": 0
    }
}
```

---

## Decision Trees

### Send Type Selection Decision Tree

```
START: Need to fill slot X

1. What category is this slot?
   |
   +-- REVENUE
   |   |
   |   +-- Is ppv_video count < 4 today?
   |   |   +-- YES: Is this slot 1, 2, or 3 of revenue? -> SELECT ppv_video
   |   |   +-- NO: Continue to secondary types
   |   |
   |   +-- Was vip_program used this week?
   |   |   +-- NO: Is this mid-week? -> CONSIDER vip_program
   |   |   +-- YES: Skip vip_program
   |   |
   |   +-- Is there a special type slot available? (bundle/flash/game)
   |   |   +-- YES: Select based on performance scores
   |   |   +-- NO: Fill with additional ppv_video or bundle
   |
   +-- ENGAGEMENT
   |   |
   |   +-- Are there active campaigns?
   |   |   +-- YES: Is link_drop < 2 today? -> SELECT link_drop
   |   |   +-- NO: Continue to bump types
   |   |
   |   +-- Apply bump distribution (40/20/20/10/10)
   |   |   +-- bump_normal: Most flexible, fills remaining
   |   |   +-- bump_descriptive: For story content
   |   |   +-- bump_text_only: When vault limited
   |   |   +-- bump_flyer: High impact announcements
   |   |
   |   +-- Need interaction driver?
   |       +-- dm_farm < 2? -> SELECT dm_farm
   |       +-- like_farm < 1? -> SELECT like_farm
   |
   +-- RETENTION
       |
       +-- Is page_type == "paid"?
       |   +-- YES: Has expired_winback been used today?
       |   |   +-- NO: SELECT expired_winback (priority 1)
       |   |   +-- YES: Has renew_on_message been used?
       |   |       +-- NO: SELECT renew_on_message (priority 2)
       |   |       +-- YES: SELECT ppv_message or renew_on_post
       |   +-- NO (free page): SELECT ppv_message
       |
       +-- Fill remaining with ppv_message

END: Return selected send_type
```

### Time Slot Assignment Decision Tree

```
START: Assign time to item at position N

1. Get send_type for this item

2. Look up MIN_TIME_BETWEEN for send_type

3. Was this send_type used earlier today?
   |
   +-- YES: Calculate earliest_valid = last_time + min_gap
   +-- NO: earliest_valid = start_of_day (08:00)

4. Calculate target_time = base_spacing * position

5. scheduled_time = MAX(target_time, earliest_valid)

6. Is scheduled_time > end_of_day (23:00)?
   |
   +-- YES: WARN - schedule overflow, adjust earlier items
   +-- NO: Continue

7. Record scheduled_time for this send_type

END: Return scheduled_time
```

### Weekly Planning Decision Tree

```
START: Plan week for creator

1. Get creator profile
   +-- fan_count -> volume_tier
   +-- page_type -> filter applicable send_types

2. FOR each day in week (Mon-Sun):
   |
   +-- Get day_of_week adjustment
   +-- Calculate adjusted category counts
   +-- Track weekly limits (vip_program, snapchat_bundle)
   |
   +-- Allocate this day
   |   +-- Revenue slots (with weekly limit checks)
   |   +-- Engagement slots (with campaign context)
   |   +-- Retention slots (with page_type filter)
   |
   +-- Update weekly_history for limit tracking

3. Validate weekly totals
   +-- Category percentages within targets?
   +-- Weekly limits respected?
   +-- Variety maintained across days?

END: Return weekly_allocation
```

---

## Validation Checklist

### Daily Validation

Before finalizing daily allocation, verify:

| Check | Rule | Action if Failed |
|-------|------|------------------|
| Total Count | Items <= tier maximum | Remove lowest priority items |
| Revenue % | Within 50-60% of total | Rebalance categories |
| Engagement % | Within 30-35% of total | Rebalance categories |
| Retention % | Within 10-15% of total | Rebalance categories |
| Consecutive Rule | No same type twice in row | Swap adjacent items |
| Daily Limits | Each type under max_per_day | Replace with alternative |
| Weekly Limits | vip/snapchat under max_per_week | Substitute different type |
| Time Gaps | All gaps >= min_time_between | Adjust schedule times |
| Page Type | No paid-only types on free pages | Remove invalid types |

### Validation Algorithm

```python
def validate_allocation(items: list, config: dict, day_context: dict) -> dict:
    """
    Comprehensive validation of daily allocation.

    Returns:
        Validation result with pass/fail and details
    """
    checks = {}

    # Check 1: Total within tier limit
    checks["total_within_tier"] = len(items) <= config["total_per_day"]

    # Check 2: Category percentages
    total = len(items)
    rev_count = sum(1 for i in items if i["category"] == "revenue")
    eng_count = sum(1 for i in items if i["category"] == "engagement")
    ret_count = sum(1 for i in items if i["category"] == "retention")

    checks["revenue_percentage"] = (rev_count / total * 100) if total > 0 else 0
    checks["revenue_in_range"] = 45 <= checks["revenue_percentage"] <= 65

    # Check 3: No consecutive duplicates
    checks["no_consecutive_duplicates"] = all(
        items[i]["send_type"] != items[i-1]["send_type"]
        for i in range(1, len(items))
    )

    # Check 4: Daily limits respected
    type_counts = {}
    for item in items:
        st = item["send_type"]
        type_counts[st] = type_counts.get(st, 0) + 1

    checks["daily_limits_respected"] = all(
        count <= DAILY_MAXIMUMS.get(st, 2)
        for st, count in type_counts.items()
    )

    # Check 5: Time gaps valid
    type_last_times = {}
    gaps_valid = True
    for item in items:
        st = item["send_type"]
        time = parse_time(item["scheduled_time"])

        if st in type_last_times:
            gap = time - type_last_times[st]
            min_gap = MIN_TIME_BETWEEN.get(st, 60)
            if gap < min_gap:
                gaps_valid = False

        type_last_times[st] = time

    checks["time_gaps_valid"] = gaps_valid

    # Check 6: Page type compliance
    if day_context["page_type"] == "free":
        checks["page_type_compliant"] = not any(
            item["send_type"] in PAID_ONLY_TYPES
            for item in items
        )
    else:
        checks["page_type_compliant"] = True

    # Overall pass/fail
    passed = all([
        checks["total_within_tier"],
        checks["revenue_in_range"],
        checks["no_consecutive_duplicates"],
        checks["daily_limits_respected"],
        checks["time_gaps_valid"],
        checks["page_type_compliant"],
    ])

    return {
        "passed": passed,
        "checks": checks
    }
```

---

## Quick Reference Tables

### Volume Tier Quick Reference

| Tier | Fans | R | E | Ret | Total |
|------|------|---|---|-----|-------|
| Low | <1K | 3 | 3 | 1 | 7 |
| Mid | 1-5K | 4 | 4 | 2 | 10 |
| High | 5-15K | 6 | 5 | 2 | 13 |
| Ultra | 15K+ | 8 | 6 | 3 | 17 |

### Day Adjustment Quick Reference

| Day | R | E | Ret |
|-----|---|---|-----|
| Mon | -1 | 0 | 0 |
| Tue-Thu | 0 | 0 | 0 |
| Fri | +1 | 0 | 0 |
| Sat | 0 | +1 | 0 |
| Sun | +1 | 0 | 0 |

### Daily Max Quick Reference

| Type | Max/Day | Type | Max/Day |
|------|---------|------|---------|
| ppv_unlock | 4 | bump_normal | 5 |
| ppv_wall | 3 | bump_descriptive | 3 |
| tip_goal | 2 | bump_text_only | 4 |
| bundle | 2 | bump_flyer | 2 |
| game_post | 1 | dm_farm | 2 |
| flash_bundle | 1 | like_farm | 1 |
| vip_program | 1 | link_drop | 3 |
| first_to_tip | 1 | ppv_followup | 4 |

---

*This document is the authoritative reference for send type allocation logic in the EROS Schedule Generator.*
