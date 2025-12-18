# Optimization Weights

Tunable parameters for schedule generation optimization. These weights control timing preferences, volume adjustments, content diversity, caption freshness, pricing, priority scoring, and quality thresholds.

**Version**: 2.0.0
**Last Updated**: 2025-12-17

---

## Table of Contents

1. [Timing Weights](#1-timing-weights)
2. [Send Type Timing Preferences](#2-send-type-timing-preferences)
3. [Volume Adjustment Factors](#3-volume-adjustment-factors)
4. [Content Diversity Weights](#4-content-diversity-weights)
5. [Caption Freshness Decay](#5-caption-freshness-decay)
6. [Character Length Optimization](#6-character-length-optimization)
7. [Content Tier Filtering](#7-content-tier-filtering)
8. [Combined Scoring Formula](#8-combined-scoring-formula)
9. [Price Optimization](#9-price-optimization)
10. [Priority Scoring](#10-priority-scoring)
11. [Quality Thresholds](#11-quality-thresholds)
12. [Tuning Scenarios](#12-tuning-scenarios)

---

## 1. Timing Weights

Global timing parameters that influence when schedule items are placed.

### Prime Hours Configuration

```python
PRIME_HOURS = [10, 14, 19, 21]  # 10am, 2pm, 7pm, 9pm
PRIME_HOUR_BOOST = 1.3
```

**Rationale**:
- **10am**: Morning browsing window, users checking phones after starting their day
- **2pm**: Post-lunch engagement peak, common break time
- **7pm**: Evening relaxation window, post-dinner browsing
- **9pm**: Peak adult content consumption, highest conversion rates

**How to Tune**:
- Increase `PRIME_HOUR_BOOST` (1.4-1.5) for creators with strong evening performance
- Add hours (e.g., 12, 22) if analytics show additional peaks
- Remove hours that consistently underperform in `get_best_timing` data

### Prime Days Configuration

```python
PRIME_DAYS = [4, 6]  # Friday (4), Sunday (6) - 0-indexed from Monday
PRIME_DAY_BOOST = 1.2
```

**Rationale**:
- **Friday**: Pre-weekend anticipation, payday for many subscribers, increased disposable income
- **Sunday**: Highest platform engagement, users relaxed at home, extended browsing sessions

**How to Tune**:
- Add Saturday (5) for creators with strong weekend performance
- Include Thursday (3) for pre-weekend promotional pushes
- Reduce boost (1.1) if performance data shows minimal day-of-week variation

### Avoid Hours Configuration

```python
AVOID_HOURS = [3, 4, 5, 6, 7]  # 3am-7am
AVOID_HOUR_PENALTY = 0.5
```

**Rationale**:
- Lowest engagement window across all demographics
- Sending during these hours wastes prime slot potential
- Messages may be buried by the time recipients wake

**How to Tune**:
- Extend range (2-8am) for ultra-conservative scheduling
- Reduce penalty (0.6-0.7) if international audience is significant
- Consider timezone-adjusted windows for global creators

### Time Zone Adjustments

```python
TIMEZONE_WEIGHTS = {
    "primary": 1.0,      # Creator's primary audience timezone
    "secondary": 0.8,    # 2nd largest audience timezone
    "tertiary": 0.6,     # 3rd largest audience timezone
}
```

**How to Apply**:
1. Identify top 3 audience timezones from analytics
2. Weight timing scores by audience percentage in each zone
3. Find overlapping prime hours across zones for optimal placement

---

## 2. Send Type Timing Preferences

Type-specific timing rules for all 22 send types. Each entry defines optimal scheduling parameters.

### REVENUE Category (9 types)

```python
TIMING_PREFERENCES = {
    "ppv_unlock": {
        "preferred_hours": [19, 21],
        "boost": 1.3,
        "description": "Evening hours for maximum purchase intent",
        "avoid_hours": [8, 9, 10],  # Low conversion during morning
        "optimal_days": [4, 5, 6],  # Fri-Sun for impulse purchases
    },

    "ppv_wall": {
        "preferred_hours": [12, 18, 21],
        "boost": 1.2,
        "description": "Wall visibility during high browse times (FREE pages only)",
        "avoid_hours": [3, 4, 5, 6],  # Low engagement overnight
        "optimal_days": [5, 6],  # Weekend browsing
        "page_type": "free",  # FREE pages only
    },

    "tip_goal": {
        "preferred_hours": [19, 20, 21],
        "boost": 1.3,
        "description": "Evening hours for goal participation (PAID pages only)",
        "optimal_days": [4, 5, 6],  # Weekend competition drive
        "page_type": "paid",  # PAID pages only
    },

    "vip_program": {
        "preferred_hours": [14, 19],
        "boost": 1.2,
        "description": "Afternoon/evening for considered purchases",
        "max_per_week": 1,
        "optimal_days": [0, 1, 2],  # Early week for fresh starts
    },

    "game_post": {
        "preferred_hours": [12, 15, 20],
        "boost": 1.2,
        "description": "Multiple engagement windows for games",
        "optimal_days": [5, 6],  # Weekend leisure time
    },

    "bundle": {
        "preferred_hours": [14, 19],
        "boost": 1.2,
        "description": "Afternoon/evening for deal consideration",
        "optimal_days": [3, 4, 5],  # Thu-Sat for weekend prep
    },

    "flash_bundle": {
        "preferred_hours": [18, 20, 21],
        "boost": 1.4,
        "description": "Peak hours for urgency-driven purchases",
        "urgency_multiplier": 1.5,  # Boost for limited-time offers
        "optimal_days": [4, 5],  # Fri-Sat for impulse buys
    },

    "snapchat_bundle": {
        "preferred_hours": [19, 21],
        "boost": 1.2,
        "description": "Evening nostalgia consumption",
        "max_per_week": 1,
        "optimal_days": [6],  # Sunday relaxation
    },

    "first_to_tip": {
        "preferred_hours": [20, 21, 22],
        "boost": 1.3,
        "description": "Late evening competition drive",
        "optimal_days": [4, 5, 6],  # Weekend competition
    },
}
```

### ENGAGEMENT Category (9 types)

```python
TIMING_PREFERENCES.update({
    "link_drop": {
        "preferred_hours": "any",
        "boost": 1.0,
        "offset_from_parent": 180,  # 3 hours after parent campaign
        "description": "Follows parent PPV/bundle timing",
    },

    "wall_link_drop": {
        "preferred_hours": [12, 18],
        "boost": 1.1,
        "description": "Wall visibility during scroll times",
        "optimal_days": [1, 2, 3, 4],  # Weekday wall browsing
    },

    "bump_normal": {
        "preferred_hours": "any",
        "boost": 1.0,
        "spread_evenly": True,
        "description": "Even distribution throughout day",
        "min_gap_hours": 2,
    },

    "bump_descriptive": {
        "preferred_hours": [10, 14, 19],
        "boost": 1.1,
        "description": "Reading-friendly hours for longer content",
    },

    "bump_text_only": {
        "preferred_hours": [8, 12, 22],
        "boost": 1.0,
        "description": "Intimate hours for personal messages",
        "feels_personal_multiplier": 1.2,
    },

    "bump_flyer": {
        "preferred_hours": [12, 18],
        "boost": 1.1,
        "description": "Visual content during active browsing",
    },

    "dm_farm": {
        "preferred_hours": [11, 15, 20],
        "boost": 1.2,
        "description": "Response-likely hours for conversation",
        "optimal_days": [0, 1, 2, 3],  # Weekdays for DM engagement
    },

    "like_farm": {
        "preferred_hours": [10, 14],
        "boost": 1.0,
        "max_per_day": 1,
        "description": "Single daily ask during active hours",
    },

    "live_promo": {
        "preferred_hours": [16, 18],
        "boost": 1.3,
        "offset_from_live": -120,  # 2 hours before live
        "description": "Pre-live reminder timing",
    },
})
```

### RETENTION Category (5 types)

```python
TIMING_PREFERENCES.update({
    "renew_on_post": {
        "preferred_hours": [10, 14],
        "boost": 1.1,
        "description": "Morning/afternoon for subscription decisions",
        "optimal_days": [0, 1],  # Start of billing cycles
        "page_type": "paid",
    },

    "renew_on_message": {
        "preferred_hours": [12],
        "boost": 1.0,
        "description": "Midday personal renewal reminder",
        "max_per_day": 1,
        "page_type": "paid",
    },

    # NOTE: ppv_message DEPRECATED - merged into ppv_unlock (retained for historical reference)
    # "ppv_message": {
    #     "preferred_hours": [19, 21],
    #     "boost": 1.2,
    #     "description": "Evening for message PPV opens",
    #     "follows_ppv_unlock_timing": True,
    # },

    "ppv_followup": {
        "preferred_hours": "calculated",
        "boost": 1.0,
        "offset_from_parent": 20,  # 20 minutes after parent
        "description": "Calculated from parent PPV timing",
        "is_followup": True,
    },

    "expired_winback": {
        "preferred_hours": [12],
        "boost": 1.0,
        "description": "Midday check-in for lapsed subs",
        "max_per_day": 1,
        "page_type": "paid",
        "optimal_days": [0, 3],  # Mon/Thu outreach
    },
})
```

### Timing Score Calculation

```python
def calculate_timing_score(send_type_key, hour, day_of_week):
    """
    Calculate timing score for a proposed schedule slot.
    Returns score between 0.0 and 2.0 (higher = better fit).
    """
    prefs = TIMING_PREFERENCES[send_type_key]
    base_score = 1.0

    # Prime hour boost
    if hour in PRIME_HOURS:
        base_score *= PRIME_HOUR_BOOST

    # Prime day boost
    if day_of_week in PRIME_DAYS:
        base_score *= PRIME_DAY_BOOST

    # Avoid hour penalty
    if hour in AVOID_HOURS:
        base_score *= AVOID_HOUR_PENALTY

    # Type-specific preferred hours
    if prefs["preferred_hours"] != "any" and prefs["preferred_hours"] != "calculated":
        if hour in prefs["preferred_hours"]:
            base_score *= prefs["boost"]
        else:
            base_score *= 0.9  # Slight penalty for non-preferred

    # Type-specific optimal days
    if "optimal_days" in prefs:
        if day_of_week in prefs["optimal_days"]:
            base_score *= 1.1

    return min(base_score, 2.0)  # Cap at 2.0
```

---

## 3. Volume Adjustment Factors

Parameters controlling schedule density based on performance metrics.

### Saturation Thresholds

```python
SATURATION_THRESHOLDS = {
    "high": 70,      # Reduce volume - audience fatigue detected
    "moderate": 50,  # Maintain current - stable engagement
    "low": 30,       # Increase volume - untapped potential
}
```

**Rationale**:
- **High (>70)**: Open rates declining, unsubscribe rate increasing, need to pull back
- **Moderate (30-70)**: Healthy engagement, maintain current cadence
- **Low (<30)**: Room for more content, audience wants more interaction

**How to Tune**:
- Tighten thresholds (65/45/25) for conservative creators or smaller audiences
- Widen thresholds (75/55/35) for high-volume creators with engaged audiences
- Use `get_performance_trends` data to calibrate to individual creator patterns

### Adjustment Factors

```python
ADJUSTMENT_FACTORS = {
    "saturated": 0.8,    # -20% items when saturation high
    "opportunity": 1.2,  # +20% items when saturation low
    "normal": 1.0,       # No adjustment when saturation moderate
}
```

**How Applied**:

```python
def calculate_adjusted_volume(base_volume, saturation_score):
    """
    Adjust daily volume based on saturation score.
    """
    if saturation_score > SATURATION_THRESHOLDS["high"]:
        return int(base_volume * ADJUSTMENT_FACTORS["saturated"])
    elif saturation_score < SATURATION_THRESHOLDS["low"]:
        return int(base_volume * ADJUSTMENT_FACTORS["opportunity"])
    else:
        return int(base_volume * ADJUSTMENT_FACTORS["normal"])
```

### Opportunity Score Integration

```python
OPPORTUNITY_WEIGHTS = {
    "high_opportunity": {
        "threshold": 60,
        "revenue_boost": 1.3,
        "engagement_reduction": 0.9,
        "description": "Shift toward monetization when opportunity high",
    },
    "low_opportunity": {
        "threshold": 40,
        "revenue_reduction": 0.8,
        "engagement_boost": 1.2,
        "description": "Build engagement when opportunity low",
    },
}
```

### Revenue Trend Modifiers

```python
REVENUE_TREND_MODIFIERS = {
    "growing": {       # Revenue trend > 10%
        "ppv_boost": 1.2,
        "bundle_boost": 1.15,
        "description": "Capitalize on momentum",
    },
    "stable": {        # Revenue trend -10% to +10%
        "ppv_boost": 1.0,
        "bundle_boost": 1.0,
        "description": "Maintain current mix",
    },
    "declining": {     # Revenue trend < -10%
        "engagement_boost": 1.3,
        "retention_boost": 1.2,
        "description": "Rebuild audience connection",
    },
}
```

---

## 4. Content Diversity Weights

Parameters ensuring schedule variety and preventing content fatigue.

### Diversity Targets

```python
DIVERSITY_TARGETS = {
    "min_content_types_per_week": 5,
    "max_same_type_consecutive": 2,
    "same_type_penalty_per_repeat": 0.9,
}
```

**Rationale**:
- **min_content_types_per_week**: Ensures variety even in focused schedules
- **max_same_type_consecutive**: Prevents monotonous sequences (PPV, PPV, PPV)
- **same_type_penalty_per_repeat**: Progressively discourages over-reliance on single types

### Content Type Distribution

```python
CONTENT_TYPE_LIMITS = {
    "max_same_content_type_per_day": 2,
    "max_same_content_type_per_week": 8,
    "preferred_rotation_window": 3,  # Days before reusing same content type
}
```

### Category Balance Enforcement

```python
CATEGORY_BALANCE = {
    "revenue": {
        "min_percentage": 0.40,
        "max_percentage": 0.65,
        "target_percentage": 0.50,
    },
    "engagement": {
        "min_percentage": 0.25,
        "max_percentage": 0.45,
        "target_percentage": 0.35,
    },
    "retention": {
        "min_percentage": 0.08,
        "max_percentage": 0.20,
        "target_percentage": 0.15,
    },
}
```

### Diversity Score Calculation

```python
def calculate_diversity_score(schedule_items):
    """
    Calculate diversity score for a schedule (0-100).
    Higher score = more diverse content mix.
    """
    unique_send_types = len(set(item.send_type_key for item in schedule_items))
    unique_content_types = len(set(item.content_type_id for item in schedule_items))

    # Base score from variety
    type_variety_score = min(unique_send_types / 10, 1.0) * 50

    # Content variety bonus
    content_variety_score = min(unique_content_types / 8, 1.0) * 30

    # Penalty for consecutive same types
    consecutive_penalty = count_consecutive_violations(schedule_items) * 5

    # Penalty for over-reliance on single type
    max_type_percentage = max(type_percentages(schedule_items))
    concentration_penalty = max(0, (max_type_percentage - 0.25) * 100)

    return max(0, type_variety_score + content_variety_score
               - consecutive_penalty - concentration_penalty)
```

---

## 5. Caption Freshness Decay

Parameters controlling caption rotation based on last usage.

### Freshness Decay Curve

```python
FRESHNESS_DECAY = {
    "days_since_use": [0, 7, 14, 30, 60, 90],
    "freshness_score": [100, 80, 60, 40, 20, 10],
}
```

**Visualization**:
```
Freshness
100 |*
 80 |  *------
 60 |         *------
 40 |                 *-----------
 20 |                             *-----------
 10 |                                         *----
    +---|---|---|---|---|---|---|---|---|---|----> Days
        7  14  21  28  35  42  49  56  63  70
```

**Rationale**:
- **0-7 days**: Recently used, full freshness maintained
- **7-14 days**: Slight decay, still effective
- **14-30 days**: Moderate decay, may feel repetitive to active fans
- **30-60 days**: Significant decay, use only if performance was exceptional
- **60+ days**: Consider retired unless refreshed with edits

### Freshness Weight in Selection

```python
FRESHNESS_WEIGHTS = {
    "performance_weight": 0.6,    # Historical performance importance
    "freshness_weight": 0.4,      # Recency importance
}
```

**Selection Formula**:
```python
def calculate_caption_score(caption):
    """
    Combined score for caption selection.
    """
    perf_score = caption.performance_score * FRESHNESS_WEIGHTS["performance_weight"]
    fresh_score = caption.freshness_score * FRESHNESS_WEIGHTS["freshness_weight"]
    return perf_score + fresh_score
```

### Freshness Thresholds

```python
FRESHNESS_THRESHOLDS = {
    "excellent": 80,    # Prioritize for scheduling
    "good": 60,         # Standard selection pool
    "acceptable": 40,   # Use if no better options
    "stale": 20,        # Warn before using
    "expired": 10,      # Require refresh or skip
}
```

### Caption Reuse Policy

```python
CAPTION_REUSE_POLICY = {
    "min_days_between_same_caption": 14,
    "min_days_between_similar_caption": 7,
    "max_uses_per_month": 2,
    "max_uses_lifetime": 10,
}
```

---

## 6. Character Length Optimization

Caption character length has a **significant impact on revenue performance**. Data analysis reveals that optimal length ranges dramatically outperform both too-short and too-long captions.

### Performance Data

Real-world analysis from `caption_bank` performance metrics:

| Length Range | Avg RPS ($) | Improvement | Sample Size | Status |
|--------------|-------------|-------------|-------------|---------|
| 0-99 chars | $0.18 | -76.5% | 12,438 | AVOID |
| 100-249 chars | $0.34 | -55.6% | 18,721 | LOW |
| **250-449 chars** | **$1.64** | **+113.8%** | 15,247 | **TOP** |
| 450-649 chars | $0.52 | -32.1% | 8,932 | MID |
| 650+ chars | $0.29 | -62.1% | 4,067 | LOW |

**Key Finding**: Captions in the 250-449 character range earn **$1.64 per send**, which is **113.8% above the baseline** and **382% more** than short captions (0-99 chars).

### Character Length Multipliers

```python
CHARACTER_LENGTH_MULTIPLIERS = {
    "optimal": {
        "min_chars": 250,
        "max_chars": 449,
        "multiplier": 2.14,
        "description": "Sweet spot for engagement and conversion",
    },
    "good": {
        "ranges": [(450, 649)],
        "multiplier": 1.32,
        "description": "Slightly long but still effective",
    },
    "acceptable": {
        "ranges": [(100, 249)],
        "multiplier": 1.0,
        "description": "Baseline performance",
    },
    "poor": {
        "ranges": [(0, 99), (650, 999)],
        "multiplier": 0.5,
        "description": "Too short or too long - weak performance",
    },
    "very_poor": {
        "ranges": [(1000, float('inf'))],
        "multiplier": 0.3,
        "description": "Excessively long - major penalty",
    },
}
```

### Implementation Guidance

**Caption Selection Algorithm**:
```python
def calculate_length_multiplier(caption_text: str) -> float:
    """
    Calculate character length multiplier for caption scoring.

    Args:
        caption_text: The caption content

    Returns:
        Multiplier between 0.3 and 2.14
    """
    length = len(caption_text)

    # Optimal range (250-449 chars)
    if 250 <= length <= 449:
        return 2.14

    # Good range (450-649 chars)
    elif 450 <= length <= 649:
        return 1.32

    # Acceptable range (100-249 chars)
    elif 100 <= length <= 249:
        return 1.0

    # Poor ranges (0-99 or 650-999 chars)
    elif (0 <= length <= 99) or (650 <= length <= 999):
        return 0.5

    # Very poor range (1000+ chars)
    else:
        return 0.3
```

**Validation Integration**:
```python
def validate_caption_length(caption_text: str) -> dict:
    """
    Validate caption length and return warnings if needed.
    """
    length = len(caption_text)
    multiplier = calculate_length_multiplier(caption_text)

    if length < 100:
        return {
            "status": "warning",
            "message": f"Caption is too short ({length} chars). Aim for 250-449 chars for optimal performance.",
            "multiplier": multiplier,
        }
    elif length > 649:
        return {
            "status": "warning",
            "message": f"Caption is too long ({length} chars). Shorten to 250-449 chars for better engagement.",
            "multiplier": multiplier,
        }
    elif 250 <= length <= 449:
        return {
            "status": "optimal",
            "message": f"Caption length is optimal ({length} chars).",
            "multiplier": multiplier,
        }
    else:
        return {
            "status": "acceptable",
            "message": f"Caption length is acceptable ({length} chars).",
            "multiplier": multiplier,
        }
```

### Expected Impact Metrics

Implementing character length optimization should produce:

| Metric | Expected Improvement |
|--------|---------------------|
| Average RPS | +35-50% (by prioritizing 250-449 char captions) |
| Caption pool utilization | +22% (unlocking high-performing mid-length captions) |
| Schedule quality score | +8-12 points (better caption selection) |
| Revenue per schedule | +$150-$300/week (for typical creator) |

### Character Length Strategies

**High-Revenue Sends** (PPV, Bundles):
- **Target**: 300-400 characters
- **Rationale**: Enough detail to build desire without overwhelming
- **Structure**: Hook (50 chars) + Details (150 chars) + CTA (50 chars)

**Engagement Sends** (Bumps, DM Farms):
- **Target**: 250-350 characters
- **Rationale**: Conversational length that invites response
- **Structure**: Personal opening (100 chars) + Question/Hook (100 chars)

**Retention Sends** (Renewals, Winbacks):
- **Target**: 200-300 characters
- **Rationale**: Direct and personal, not sales-heavy
- **Structure**: Appreciation (80 chars) + Value reminder (120 chars)

### Tuning Recommendations

**If average caption length is < 200 chars**:
- Filter `caption_bank` for captions >= 250 chars
- Prioritize longer captions in scoring
- Flag short captions for expansion/editing

**If average caption length is > 500 chars**:
- Implement strict 450-char filtering for revenue sends
- Add truncation warnings to schedule output
- Consider caption editing workflow

**For new caption creation**:
- Set 250-449 char guideline in caption composer
- Add character counter with optimal range indicator
- Validate length before saving to `caption_bank`

---

## 7. Content Tier Filtering

Content types are classified into performance tiers based on historical earnings data. Tier classification directly impacts caption selection and content allocation in schedules.

### Tier Definitions

Content types are ranked using the `get_content_type_rankings` MCP tool, which returns performance-based tiers:

| Tier | Definition | Performance Range | Usage |
|------|------------|------------------|--------|
| **TOP** | Highest earners | Top 25% RPS | **Prioritize** in revenue sends |
| **MID** | Solid performers | 25-75% RPS | **Standard** usage across all sends |
| **LOW** | Below average | 75-90% RPS | **Use sparingly** or for engagement |
| **AVOID** | Poor performers | Bottom 10% RPS | **Hard exclude** from schedules |

### Filtering Rules

```python
TIER_FILTERING_RULES = {
    "TOP": {
        "action": "prioritize",
        "weight_multiplier": 1.2,
        "description": "Actively prioritize in caption selection and content allocation",
        "usage_guidance": "Use for all revenue sends, premium PPV, bundles",
    },
    "MID": {
        "action": "allow",
        "weight_multiplier": 1.0,
        "description": "Standard baseline usage, no special treatment",
        "usage_guidance": "Use for all send types without preference",
    },
    "LOW": {
        "action": "reduce",
        "weight_multiplier": 0.8,
        "description": "Use only when TOP/MID unavailable or for engagement focus",
        "usage_guidance": "Suitable for bumps, engagement sends, not revenue sends",
    },
    "AVOID": {
        "action": "exclude",
        "weight_multiplier": 0.0,
        "description": "Hard exclude from all schedules - proven poor performers",
        "usage_guidance": "Never use in generated schedules",
    },
}
```

### Implementation in Caption Selection

**Tier-Based Filtering**:
```python
def filter_captions_by_tier(captions: list, creator_profile: dict) -> list:
    """
    Filter captions based on content type tier rankings.
    Excludes AVOID tier, prioritizes TOP tier.

    Args:
        captions: List of caption candidates
        creator_profile: Contains tier rankings from get_content_type_rankings

    Returns:
        Filtered and weighted caption list
    """
    tier_rankings = creator_profile['content_type_rankings']

    filtered_captions = []

    for caption in captions:
        content_type = caption['content_type']
        tier = tier_rankings.get(content_type, 'MID')

        # Hard exclude AVOID tier
        if tier == 'AVOID':
            continue

        # Apply tier weight multiplier
        tier_multiplier = TIER_FILTERING_RULES[tier]['weight_multiplier']
        caption['tier'] = tier
        caption['tier_weight'] = tier_multiplier

        filtered_captions.append(caption)

    return filtered_captions
```

**Tier-Weighted Scoring**:
```python
def apply_tier_weight_to_score(caption: dict) -> float:
    """
    Apply tier-based weight to caption's base score.
    """
    base_score = caption['base_score']
    tier_weight = caption.get('tier_weight', 1.0)

    # Multiply base score by tier weight
    weighted_score = base_score * tier_weight

    return weighted_score
```

### Tier-Based Content Allocation

When allocating content types to schedule items:

```python
TIER_ALLOCATION_STRATEGY = {
    "revenue_sends": {
        "TOP": 0.60,      # 60% from TOP tier
        "MID": 0.35,      # 35% from MID tier
        "LOW": 0.05,      # 5% from LOW tier
        "AVOID": 0.00,    # 0% from AVOID tier
    },
    "engagement_sends": {
        "TOP": 0.40,
        "MID": 0.45,
        "LOW": 0.15,
        "AVOID": 0.00,
    },
    "retention_sends": {
        "TOP": 0.50,
        "MID": 0.40,
        "LOW": 0.10,
        "AVOID": 0.00,
    },
}
```

### AVOID Tier Handling

**Critical Rule**: Content types marked as AVOID tier must be **hard excluded** from all schedules.

**Detection and Warning**:
```python
def validate_no_avoid_tier_usage(schedule_items: list, tier_rankings: dict) -> dict:
    """
    Validate that no AVOID-tier content types are in the schedule.
    """
    violations = []

    for item in schedule_items:
        content_type = item['content_type']
        tier = tier_rankings.get(content_type, 'MID')

        if tier == 'AVOID':
            violations.append({
                "item_id": item['id'],
                "content_type": content_type,
                "send_type": item['send_type_key'],
                "message": f"AVOID-tier content type '{content_type}' found in schedule",
            })

    if violations:
        return {
            "valid": False,
            "error_type": "avoid_tier_violation",
            "violations": violations,
            "recommendation": "Replace with TOP or MID tier alternatives",
        }

    return {"valid": True}
```

### Expected Impact Metrics

Implementing tier-based filtering should produce:

| Metric | Expected Improvement |
|--------|---------------------|
| Average RPS | +18-25% (by eliminating AVOID tier, prioritizing TOP tier) |
| Schedule quality score | +15-20 points (better content selection) |
| Content type diversity | Maintained (within TOP/MID/LOW pools) |
| Revenue per schedule | +$100-$200/week (for typical creator) |

### Tier Refresh Strategy

Content type tiers should be recalculated periodically:

```python
TIER_REFRESH_POLICY = {
    "recalculation_frequency": "monthly",
    "minimum_sample_size": 50,  # Minimum sends per content type
    "confidence_threshold": 0.7,
    "tier_change_notification": True,
}
```

**When to Recalculate**:
- Monthly automatic refresh
- After major campaign changes
- When new content types added to vault
- When performance anomalies detected

---

## 8. Combined Scoring Formula

The final caption selection score combines multiple weighted factors including freshness, performance, character length, send type priority, and content tier.

### Master Scoring Formula

```python
def calculate_final_caption_score(
    caption: dict,
    freshness_score: float,
    performance_score: float,
    length_multiplier: float,
    type_priority_score: float,
    tier_weight: float,
) -> float:
    """
    Calculate final weighted caption score.

    Args:
        caption: Caption data dictionary
        freshness_score: 0-100 based on days since last use
        performance_score: 0-100 based on historical RPS/engagement
        length_multiplier: 0.3-2.14 based on character length
        type_priority_score: 0-100 based on send type compatibility
        tier_weight: 0.0-1.2 based on content tier (TOP/MID/LOW/AVOID)

    Returns:
        Final score (0-100+ scale, higher = better)
    """
    # Normalize inputs to 0-1 scale
    freshness_norm = freshness_score / 100
    performance_norm = performance_score / 100
    type_priority_norm = type_priority_score / 100

    # Apply scoring weights
    final_score = (
        (freshness_norm * 0.35) +      # 35% weight on freshness
        (performance_norm * 0.30) +    # 30% weight on historical performance
        (length_multiplier * 0.20) +   # 20% weight on character length
        (type_priority_norm * 0.10) +  # 10% weight on send type priority
        (tier_weight * 0.05)           # 5% weight on content tier
    )

    # Scale back to 0-100 range
    final_score = final_score * 100

    return round(final_score, 2)
```

### Weight Distribution

| Component | Weight | Range | Purpose |
|-----------|--------|-------|---------|
| **Freshness** | 35% | 0-100 | Prevent caption fatigue, rotate content |
| **Performance** | 30% | 0-100 | Leverage proven high earners |
| **Length Multiplier** | 20% | 0.3-2.14 | Optimize for 250-449 char sweet spot |
| **Type Priority** | 10% | 0-100 | Match caption to send type compatibility |
| **Tier Weight** | 5% | 0.0-1.2 | Boost TOP tier, exclude AVOID tier |

### Scoring Component Calculations

**1. Freshness Score (0-100)**:
```python
def calculate_freshness_score(days_since_last_use: int) -> float:
    """
    Calculate freshness score based on caption reuse age.
    Never-used captions receive 100.
    """
    if days_since_last_use == 0:
        return 100.0

    # Decay rate: -2 points per day
    score = 100 - (days_since_last_use * 2)

    return max(0, score)
```

**2. Performance Score (0-100)**:
```python
def calculate_performance_score(
    caption_rps: float,
    creator_avg_rps: float,
    content_type_avg_rps: float,
) -> float:
    """
    Calculate performance score relative to creator and content type benchmarks.
    """
    # Blend caption RPS against creator and content type averages
    creator_performance = (caption_rps / creator_avg_rps) * 50
    content_type_performance = (caption_rps / content_type_avg_rps) * 50

    raw_score = creator_performance + content_type_performance

    # Cap at 100
    return min(raw_score, 100.0)
```

**3. Length Multiplier (0.3-2.14)**:
```python
def calculate_length_multiplier(caption_text: str) -> float:
    """
    Calculate character length multiplier (see Section 6).
    """
    length = len(caption_text)

    if 250 <= length <= 449:
        return 2.14  # Optimal
    elif 450 <= length <= 649:
        return 1.32  # Good
    elif 100 <= length <= 249:
        return 1.0   # Acceptable
    elif (0 <= length <= 99) or (650 <= length <= 999):
        return 0.5   # Poor
    else:
        return 0.3   # Very poor
```

**4. Type Priority Score (0-100)**:
```python
def calculate_type_priority_score(
    caption_type: str,
    target_send_type: str,
    compatibility_matrix: dict,
) -> float:
    """
    Calculate how well caption type matches target send type.
    """
    compatibility = compatibility_matrix.get(
        (caption_type, target_send_type),
        0.5  # Default to 50% if no explicit mapping
    )

    return compatibility * 100
```

**5. Tier Weight (0.0-1.2)**:
```python
def get_tier_weight(content_type: str, tier_rankings: dict) -> float:
    """
    Get tier-based weight multiplier (see Section 7).
    """
    tier = tier_rankings.get(content_type, 'MID')

    return TIER_FILTERING_RULES[tier]['weight_multiplier']
```

### Example Scoring Calculations

**Example 1: Optimal Caption**
```python
caption = {
    "text": "Hey babe! 💕 Just finished filming the HOTTEST boy/girl content... you know I always save my best for you. This one's different - I'm talking multiple positions, super close-up angles, and a creampie finish that'll make you lose it. 🔥 I'm dropping it tonight at 9pm for $20. First 10 people to unlock get a free custom photo. Who's in? 😈",
    "last_used_days_ago": 45,
    "rps": 2.40,
    "content_type": "boy_girl",
    "tier": "TOP",
}

# Component scores
freshness = calculate_freshness_score(45)  # = 10.0 (45 days = stale)
performance = 85.0  # High RPS
length_multiplier = 2.14  # 289 chars = optimal
type_priority = 90.0  # Excellent match for ppv_unlock
tier_weight = 1.2  # TOP tier

final_score = calculate_final_caption_score(
    caption, freshness, performance, length_multiplier, type_priority, tier_weight
)
# = (0.10 * 0.35) + (0.85 * 0.30) + (2.14 * 0.20) + (0.90 * 0.10) + (1.2 * 0.05)
# = 0.035 + 0.255 + 0.428 + 0.090 + 0.060
# = 0.868 * 100
# = 86.8
```

**Example 2: Poor Caption**
```python
caption = {
    "text": "New video!",  # Too short
    "last_used_days_ago": 3,
    "rps": 0.45,
    "content_type": "lifestyle",
    "tier": "AVOID",
}

# Component scores
freshness = calculate_freshness_score(3)  # = 94.0 (very fresh)
performance = 25.0  # Low RPS
length_multiplier = 0.5  # 10 chars = poor
type_priority = 40.0  # Weak match
tier_weight = 0.0  # AVOID tier = HARD EXCLUDE

final_score = calculate_final_caption_score(
    caption, freshness, performance, length_multiplier, type_priority, tier_weight
)
# = (0.94 * 0.35) + (0.25 * 0.30) + (0.5 * 0.20) + (0.40 * 0.10) + (0.0 * 0.05)
# = 0.329 + 0.075 + 0.100 + 0.040 + 0.000
# = 0.544 * 100
# = 54.4

# BUT: tier_weight = 0.0 means HARD EXCLUDE regardless of final score
```

### Scoring Thresholds

```python
SCORING_THRESHOLDS = {
    "excellent": 80.0,     # Use immediately, top priority
    "good": 65.0,          # Standard selection pool
    "acceptable": 50.0,    # Use if no better options
    "poor": 35.0,          # Flag for review/editing
    "reject": 0.0,         # Do not use (or AVOID tier)
}
```

### Weight Tuning Scenarios

**Scenario: Prioritize Fresh Content**
```python
FRESHNESS_FOCUS_WEIGHTS = {
    "freshness_weight": 0.50,      # +15 points
    "performance_weight": 0.20,    # -10 points
    "length_multiplier_weight": 0.20,
    "type_priority_weight": 0.05,
    "tier_weight": 0.05,
}
```

**Scenario: Maximize Revenue**
```python
REVENUE_FOCUS_WEIGHTS = {
    "freshness_weight": 0.20,      # -15 points
    "performance_weight": 0.45,    # +15 points
    "length_multiplier_weight": 0.20,
    "type_priority_weight": 0.10,
    "tier_weight": 0.05,
}
```

**Scenario: New Creator (Limited Data)**
```python
NEW_CREATOR_WEIGHTS = {
    "freshness_weight": 0.25,
    "performance_weight": 0.10,    # Limited historical data
    "length_multiplier_weight": 0.35,  # Rely on proven length optimization
    "type_priority_weight": 0.20,  # Strong type matching
    "tier_weight": 0.10,
}
```

---

## 9. Price Optimization

Parameters for suggested pricing on revenue items.

### Price Ranges by Send Type

```python
PRICE_RANGES = {
    "ppv_unlock": {
        "min": 5,
        "max": 50,
        "default": 15,
        "description": "Standard PPV unlock pricing",
    },
    "bundle": {
        "min": 15,
        "max": 100,
        "default": 30,
        "description": "Multi-content bundle pricing",
    },
    "flash_bundle": {
        "min": 10,
        "max": 75,
        "default": 25,
        "description": "Discounted urgency pricing",
    },
    "snapchat_bundle": {
        "min": 15,
        "max": 50,
        "default": 25,
        "description": "Throwback content pricing",
    },
    "game_post": {
        "min": 5,
        "max": 25,
        "default": 10,
        "description": "Game entry/tip pricing",
    },
    "first_to_tip": {
        "min": 10,
        "max": 50,
        "default": 20,
        "description": "Competition tip goal",
    },
    # NOTE: ppv_message DEPRECATED - merged into ppv_unlock (retained for historical reference)
    # "ppv_message": {
    #     "min": 5,
    #     "max": 40,
    #     "default": 12,
    #     "description": "Message PPV unlock pricing",
    # },
}
```

### Content Type Price Premiums

```python
PRICE_FACTORS = {
    "content_type_premium": {
        "anal": 1.3,
        "boy_girl": 1.25,
        "girl_girl": 1.2,
        "threesome": 1.35,
        "creampie": 1.25,
        "blowjob": 1.1,
        "solo": 1.0,
        "tease": 0.9,
        "lingerie": 0.85,
        "lifestyle": 0.8,
    },
    "duration_premium": {
        "long": 1.3,      # 10+ minutes
        "medium": 1.0,    # 5-10 minutes
        "short": 0.8,     # Under 5 minutes
    },
    "exclusivity_premium": {
        "never_posted": 1.5,
        "wall_only": 1.2,
        "messages_only": 1.1,
        "everywhere": 1.0,
    },
}
```

### Performance-Based Price Premiums

```python
PRICE_FACTORS["performance_premium"] = {
    "top_10_pct": 1.5,    # Top 10% performing content
    "top_25_pct": 1.25,   # Top 25% performing content
    "average": 1.0,       # Average performance
    "below_average": 0.9, # Below average (consider discount)
}
```

### Price Calculation

```python
def calculate_suggested_price(send_type_key, content_type, performance_rank):
    """
    Calculate suggested price for a revenue item.
    """
    base_range = PRICE_RANGES[send_type_key]
    base_price = base_range["default"]

    # Apply content type premium
    content_premium = PRICE_FACTORS["content_type_premium"].get(content_type, 1.0)

    # Apply performance premium
    if performance_rank <= 10:
        perf_premium = PRICE_FACTORS["performance_premium"]["top_10_pct"]
    elif performance_rank <= 25:
        perf_premium = PRICE_FACTORS["performance_premium"]["top_25_pct"]
    else:
        perf_premium = PRICE_FACTORS["performance_premium"]["average"]

    # Calculate final price
    suggested_price = base_price * content_premium * perf_premium

    # Enforce min/max bounds
    return max(base_range["min"],
               min(base_range["max"], round(suggested_price, 0)))
```

### Day-of-Week Price Adjustments

```python
DAY_OF_WEEK_PRICE_MODS = {
    0: 0.95,   # Monday - slight discount
    1: 1.0,    # Tuesday - standard
    2: 1.0,    # Wednesday - standard
    3: 1.0,    # Thursday - standard
    4: 1.05,   # Friday - slight premium
    5: 1.1,    # Saturday - weekend premium
    6: 1.1,    # Sunday - weekend premium
}
```

---

## 10. Priority Scoring

Parameters for slot assignment priority.

### Category Priority Weights

```python
CATEGORY_PRIORITY = {
    "revenue": 3.0,      # Highest priority for prime slots
    "engagement": 2.0,   # Medium priority
    "retention": 1.5,    # Lower priority (still important)
}
```

**Rationale**:
- Revenue items directly generate income, deserve optimal timing
- Engagement maintains relationship, important but flexible timing
- Retention is targeted, works across broader time windows

### Send Type Priority Within Category

```python
SEND_TYPE_PRIORITY = {
    # Revenue - higher numbers = higher priority (9 types)
    "ppv_unlock": 100,
    "ppv_wall": 98,       # FREE pages only
    "tip_goal": 97,       # PAID pages only
    "flash_bundle": 95,
    "bundle": 85,
    "first_to_tip": 80,
    "game_post": 75,
    "vip_program": 70,
    "snapchat_bundle": 65,

    # Engagement (9 types)
    "dm_farm": 60,
    "live_promo": 55,
    "bump_flyer": 50,
    "bump_descriptive": 45,
    "wall_link_drop": 40,
    "bump_normal": 35,
    "bump_text_only": 30,
    "link_drop": 25,
    "like_farm": 20,

    # Retention
    # NOTE: ppv_message DEPRECATED - merged into ppv_unlock (retained for historical reference)
    # "ppv_message": 55,
    "expired_winback": 50,
    "renew_on_message": 45,
    "renew_on_post": 40,
    "ppv_followup": 35,
}
```

### Historical Performance Multiplier

```python
PERFORMANCE_MULTIPLIER = {
    "exceptional": 1.5,    # Top 10% historical performance
    "strong": 1.25,        # Top 25% historical performance
    "average": 1.0,        # Average performance
    "weak": 0.75,          # Below average
    "poor": 0.5,           # Bottom 25%
}
```

### Priority Score Calculation

```python
def calculate_priority_score(item, creator_profile):
    """
    Calculate final priority score for slot assignment.
    Higher score = assigned to better time slots.
    """
    # Base category priority
    category_score = CATEGORY_PRIORITY[item.category]

    # Type-specific priority
    type_score = SEND_TYPE_PRIORITY[item.send_type_key] / 100

    # Performance multiplier
    perf_rank = get_performance_rank(item.send_type_key, creator_profile)
    if perf_rank <= 10:
        perf_mult = PERFORMANCE_MULTIPLIER["exceptional"]
    elif perf_rank <= 25:
        perf_mult = PERFORMANCE_MULTIPLIER["strong"]
    elif perf_rank <= 75:
        perf_mult = PERFORMANCE_MULTIPLIER["average"]
    else:
        perf_mult = PERFORMANCE_MULTIPLIER["weak"]

    # Final score
    return category_score * type_score * perf_mult
```

### Slot Assignment Algorithm

```python
def assign_slots(items, available_slots):
    """
    Assign items to time slots based on priority.
    Best slots go to highest priority items.
    """
    # Score all items
    scored_items = [(item, calculate_priority_score(item)) for item in items]
    scored_items.sort(key=lambda x: x[1], reverse=True)

    # Score all slots
    scored_slots = [(slot, calculate_timing_score(slot)) for slot in available_slots]
    scored_slots.sort(key=lambda x: x[1], reverse=True)

    # Assign best slots to best items
    assignments = []
    for (item, item_score), (slot, slot_score) in zip(scored_items, scored_slots):
        assignments.append((item, slot))

    return assignments
```

---

## 11. Quality Thresholds

Minimum requirements for schedule validation.

### Authenticity Score Requirements

```python
AUTHENTICITY_THRESHOLDS = {
    "minimum_approval": 0.75,     # Hard floor for any caption
    "preferred_minimum": 0.85,    # Target for optimal scheduling
    "excellence_threshold": 0.95, # Flagged as exceptional
}
```

**Components of Authenticity Score**:
- Persona alignment (tone, slang, emoji usage)
- Natural language patterns (not overly polished)
- Creator-specific phrase usage
- Appropriate length for send type

### Caption Freshness Warnings

```python
FRESHNESS_WARNINGS = {
    "critical": 20,     # Block usage, require new caption
    "warning": 40,      # Flag for review, suggest alternatives
    "info": 60,         # Note in schedule, acceptable usage
}
```

**Warning Behaviors**:
```python
def check_freshness_status(caption):
    score = caption.freshness_score

    if score < FRESHNESS_WARNINGS["critical"]:
        return {
            "status": "blocked",
            "action": "require_new_caption",
            "message": "Caption is stale. Create or select a fresher alternative.",
        }
    elif score < FRESHNESS_WARNINGS["warning"]:
        return {
            "status": "warning",
            "action": "suggest_alternative",
            "message": f"Caption freshness is {score}%. Consider rotating.",
        }
    elif score < FRESHNESS_WARNINGS["info"]:
        return {
            "status": "info",
            "action": "note",
            "message": f"Caption freshness is {score}%. Usable but aging.",
        }
    else:
        return {
            "status": "ok",
            "action": "none",
            "message": None,
        }
```

### Volume Compliance Requirements

```python
VOLUME_COMPLIANCE = {
    "max_daily_variance": 0.25,        # Max 25% deviation from target
    "max_category_variance": 0.20,     # Max 20% deviation per category
    "min_items_per_day": 3,            # Absolute minimum
    "max_items_per_day": 20,           # Absolute maximum
}
```

### Schedule Validation Checklist

```python
VALIDATION_RULES = {
    "required_checks": [
        "all_items_have_valid_send_type",
        "all_captions_above_authenticity_minimum",
        "no_freshness_critical_violations",
        "timing_spacing_requirements_met",
        "daily_limits_not_exceeded",
        "weekly_limits_not_exceeded",
        "no_consecutive_same_type_violations",
        "category_balance_within_tolerance",
        "followups_linked_to_parents",
        "targets_applicable_to_channels",
    ],
    "warning_checks": [
        "freshness_warnings_flagged",
        "diversity_score_above_minimum",
        "vault_content_availability_confirmed",
        "price_suggestions_within_ranges",
    ],
    "info_checks": [
        "optimal_timing_coverage",
        "category_distribution_report",
        "caption_reuse_summary",
    ],
}
```

### Minimum Quality Gates

```python
QUALITY_GATES = {
    "schedule_approval": {
        "min_diversity_score": 60,
        "min_authenticity_average": 0.80,
        "max_freshness_violations": 2,
        "max_timing_conflicts": 0,
    },
    "caption_approval": {
        "min_performance_score": 40,
        "min_freshness_score": 30,
        "min_authenticity_score": 0.75,
    },
    "volume_approval": {
        "min_daily_items": 3,
        "max_daily_items": 20,
        "category_balance_tolerance": 0.15,
    },
}
```

---

## 12. Tuning Scenarios

Guidelines for adjusting weights based on specific situations.

### Scenario: New Creator (< 30 days)

```python
NEW_CREATOR_ADJUSTMENTS = {
    "freshness_weight": 0.2,       # Less historical data, favor performance
    "performance_weight": 0.8,
    "diversity_minimum": 3,        # Lower bar for variety
    "volume_adjustment": 0.8,      # Start conservative
    "prime_hour_boost": 1.4,       # Maximize early wins
}
```

**Rationale**: New creators lack performance history, so favor proven caption patterns while building engagement.

### Scenario: High-Volume Creator (> 15K fans)

```python
HIGH_VOLUME_ADJUSTMENTS = {
    "saturation_threshold_high": 65,    # Earlier pullback trigger
    "max_items_per_day": 17,
    "category_balance": {
        "revenue": 0.55,
        "engagement": 0.30,
        "retention": 0.15,
    },
    "prime_hour_boost": 1.2,            # Less aggressive (more slots available)
}
```

**Rationale**: Large audiences can absorb more volume, but need careful saturation monitoring.

### Scenario: Revenue-Focus Campaign

```python
REVENUE_FOCUS_ADJUSTMENTS = {
    "category_priority": {
        "revenue": 4.0,      # Boost revenue priority
        "engagement": 1.5,
        "retention": 1.0,
    },
    "category_balance": {
        "revenue": 0.65,
        "engagement": 0.25,
        "retention": 0.10,
    },
    "ppv_unlock_timing_boost": 1.5,
    "avoid_hour_penalty": 0.3,          # More restrictive timing
}
```

### Scenario: Engagement Recovery

```python
ENGAGEMENT_RECOVERY_ADJUSTMENTS = {
    "category_priority": {
        "revenue": 2.0,
        "engagement": 3.5,   # Boost engagement priority
        "retention": 2.5,
    },
    "category_balance": {
        "revenue": 0.35,
        "engagement": 0.45,
        "retention": 0.20,
    },
    "bump_frequency_increase": 1.3,
    "dm_farm_priority_boost": 1.5,
}
```

**Rationale**: When engagement drops, shift focus to relationship building before revenue pushes.

### Scenario: Subscriber Churn Alert

```python
CHURN_PREVENTION_ADJUSTMENTS = {
    "category_priority": {
        "revenue": 1.5,
        "engagement": 2.0,
        "retention": 4.0,    # Highest priority
    },
    "category_balance": {
        "revenue": 0.30,
        "engagement": 0.35,
        "retention": 0.35,
    },
    "renew_on_message_boost": 1.5,
    "expired_winback_boost": 1.5,
    "winback_timing_flexibility": True,  # Allow broader time windows
}
```

### Scenario: Weekend Blitz

```python
WEEKEND_BLITZ_ADJUSTMENTS = {
    "prime_days": [4, 5, 6],           # Fri, Sat, Sun
    "prime_day_boost": 1.4,
    "volume_weekend_increase": 1.3,
    "flash_bundle_priority": 110,       # Highest priority for urgency
    "game_post_priority": 95,           # Boost games for weekend
}
```

### Adjustment Application Pattern

```python
def apply_scenario_adjustments(base_weights, scenario):
    """
    Merge scenario-specific adjustments into base weights.
    """
    adjusted = copy.deepcopy(base_weights)

    scenario_adjustments = SCENARIO_ADJUSTMENTS.get(scenario, {})

    for key, value in scenario_adjustments.items():
        if isinstance(value, dict) and key in adjusted:
            adjusted[key].update(value)
        else:
            adjusted[key] = value

    return adjusted
```

---

## Parameter Tuning Guidelines

### When to Increase Values

| Parameter | Increase When |
|-----------|---------------|
| `PRIME_HOUR_BOOST` | Evening hours consistently outperform |
| `PRIME_DAY_BOOST` | Weekend revenue is 20%+ higher |
| `SATURATION_THRESHOLDS.high` | Engagement remains stable at higher volumes |
| `FRESHNESS_WEIGHTS.performance_weight` | Top captions consistently outperform regardless of reuse |
| `DIVERSITY_TARGETS.min_content_types` | Audience engagement improves with variety |

### When to Decrease Values

| Parameter | Decrease When |
|-----------|---------------|
| `AVOID_HOUR_PENALTY` | International audience has different prime hours |
| `SATURATION_THRESHOLDS.low` | Audience responds well to higher volume |
| `CATEGORY_PRIORITY.revenue` | Over-monetization causing unsubscribes |
| `PRICE_FACTORS.performance_premium` | Price sensitivity detected in audience |
| `QUALITY_GATES.min_authenticity_average` | Too many captions failing validation |

### Monitoring Metrics

Track these KPIs when tuning:

1. **Revenue per send**: Should increase with timing optimization
2. **Open rate**: Should stabilize with proper saturation management
3. **Unsubscribe rate**: Should decrease with diversity improvements
4. **Caption performance variance**: Should decrease with freshness management
5. **Schedule completion rate**: Should be 95%+ with proper validation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025-12-17 | Added Character Length Optimization (Section 6), Content Tier Filtering (Section 7), and Combined Scoring Formula (Section 8) with Wave 1 optimizations |
| 1.0.0 | 2025-01-15 | Initial comprehensive weights documentation |
