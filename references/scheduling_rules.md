# EROS Scheduling Business Rules Reference

## Overview

This document captures all business rules, thresholds, and constraints used in the EROS schedule generation pipeline. These rules have been extracted from the codebase and represent the operational logic for OnlyFans content scheduling.

---

## 1. PPV Spacing Rules

### Minimum Spacing Between PPVs

| Rule | Threshold | Severity |
|------|-----------|----------|
| Hard minimum | 3 hours | Error - blocks schedule |
| Recommended minimum | 4 hours | Warning - flagged for review |
| Optimal spacing | 4-6 hours | Info - best practice |

**Configuration:**
```bash
EROS_MIN_PPV_SPACING_HOURS=4  # Default
```

**Validation Logic:**
```python
def validate_ppv_spacing(items):
    """
    Rule: PPV messages must be at least MIN_PPV_SPACING_HOURS apart.
    """
    ppvs = sorted([i for i in items if i.item_type == 'ppv'], key=lambda x: x.scheduled_time)

    for i in range(1, len(ppvs)):
        gap_hours = (ppvs[i].scheduled_time - ppvs[i-1].scheduled_time).total_seconds() / 3600
        if gap_hours < 3:
            return ValidationError(f"PPV spacing too close: {gap_hours:.1f} hours")
        if gap_hours < 4:
            return ValidationWarning(f"PPV spacing below recommended: {gap_hours:.1f} hours")

    return ValidationSuccess()
```

---

## 2. Follow-up Timing Rules

### Bump Message Timing After PPV

| Parameter | Value | Notes |
|-----------|-------|-------|
| Minimum delay | 15 minutes | Earliest follow-up |
| Maximum delay | 45 minutes | Latest follow-up |
| Random range | 15-45 min | Uniform distribution |

**Prerequisites for Follow-up:**
- Parent PPV caption must have `performance_score >= 60`
- Feature flag `enable_follow_ups` must be enabled
- Maximum 1 follow-up per PPV

**Logic:**
```python
def calculate_followup_time(ppv_item):
    """
    Rule: Follow-ups occur 15-45 minutes after PPV.
    Only for high-performing captions (score >= 60).
    """
    if ppv_item.caption.performance_score < 60:
        return None

    delay_minutes = random.randint(15, 45)
    return ppv_item.scheduled_time + timedelta(minutes=delay_minutes)
```

---

## 3. Drip Window Rules

### No-PPV Zones After Drip Content

| Parameter | Value | Notes |
|-----------|-------|-------|
| Window start | Drip send time | Immediate |
| Window duration | 4-8 hours | Configurable |
| Default window | 6 hours | Middle of range |

**Drip Window Behavior:**
- PPVs scheduled within drip window are rescheduled
- Bumps ARE allowed within drip windows
- Multiple drip items can create overlapping windows

**Logic:**
```python
DRIP_WINDOW_MIN_HOURS = 4
DRIP_WINDOW_MAX_HOURS = 8

def apply_drip_windows(items):
    """
    Rule: No PPVs within 4-8 hours after drip content.
    Prevents subscriber fatigue from content overload.
    """
    drip_items = [i for i in items if i.is_drip_content]

    for drip in drip_items:
        window_end = drip.scheduled_time + timedelta(hours=DRIP_WINDOW_MAX_HOURS)

        for item in items:
            if item.item_type == 'ppv':
                if drip.scheduled_time < item.scheduled_time < window_end:
                    # Reschedule to 30 minutes after window
                    item.scheduled_time = window_end + timedelta(minutes=30)
                    item.rescheduled_reason = 'drip_window_conflict'

    return items
```

---

## 4. Volume Level Brackets

### PPV/Day Targets by Fan Count

| Volume Level | Fan Count | PPV/Day | Bump/Day | Total Messages |
|--------------|-----------|---------|----------|----------------|
| **Low** | < 1,000 | 2-3 | 2-3 | 4-6 |
| **Mid** | 1,000 - 5,000 | 4-5 | 4-5 | 8-10 |
| **High** | 5,000 - 15,000 | 6-8 | 6-8 | 12-16 |
| **Ultra** | 15,000+ | 8-10 | 8-10 | 16-20 |

**Assignment Logic:**
```python
def determine_volume_level(active_fans):
    """
    Rule: Volume level determined by current active fan count.
    """
    if active_fans < 1000:
        return VolumeLevel.LOW
    elif active_fans < 5000:
        return VolumeLevel.MID
    elif active_fans < 15000:
        return VolumeLevel.HIGH
    else:
        return VolumeLevel.ULTRA

def get_daily_targets(volume_level):
    """Returns (ppv_per_day, bump_per_day) tuple."""
    targets = {
        VolumeLevel.LOW: (2, 2),
        VolumeLevel.MID: (4, 4),
        VolumeLevel.HIGH: (7, 7),
        VolumeLevel.ULTRA: (9, 9),
    }
    return targets.get(volume_level, (4, 4))
```

**Assignment Reasons:**
- `fan_count_bracket` - Automatic assignment based on fan count
- `manual_override` - Manual assignment by admin
- `adaptive_adjustment` - System adjusted based on performance

---

## 5. Freshness Thresholds

### Caption Freshness Scoring

| Parameter | Value | Notes |
|-----------|-------|-------|
| Half-life | 14 days | Time to decay to 50% |
| Minimum for scheduling | 30 | Below this = not used |
| Exhaustion threshold | 25 | Below this = exhausted |
| Fresh caption | 100 | Never used |

**Configuration:**
```bash
EROS_FRESHNESS_HALF_LIFE_DAYS=14.0
EROS_FRESHNESS_EXHAUSTION_THRESHOLD=25
EROS_FRESHNESS_MINIMUM_SCORE=30.0
```

**Freshness Formula:**
```python
def calculate_freshness(last_used_date, reference_date=None):
    """
    Formula: freshness = 100 * (0.5 ^ (days_since_used / half_life))

    Examples:
    - Never used: 100.0
    - Used 7 days ago: 70.7
    - Used 14 days ago: 50.0
    - Used 28 days ago: 25.0
    - Used 42 days ago: 12.5
    """
    if last_used_date is None:
        return 100.0

    days_since = (reference_date or date.today()) - last_used_date
    half_life = 14.0

    freshness = 100.0 * (0.5 ** (days_since.days / half_life))
    return round(freshness, 2)
```

**Freshness Categories:**
| Score Range | Category | Action |
|-------------|----------|--------|
| 80-100 | Fresh | Prioritize for scheduling |
| 50-79 | Good | Normal selection pool |
| 30-49 | Aging | Lower priority |
| 25-29 | Stale | Avoid, needs rest |
| 0-24 | Exhausted | Not schedulable |

---

## 6. Persona Matching Boost Factors

### Voice Profile Matching

| Match Type | Boost Factor | Cumulative |
|------------|--------------|------------|
| Primary tone match | 1.20x | 1.20x |
| Emoji frequency match | 1.10x | 1.32x |
| Slang level match | 1.10x | 1.45x |
| **Maximum boost** | **1.40x** | Capped |

**Tone Options:**
- `playful` - Fun, flirty, teasing
- `aggressive` - Bold, demanding, provocative
- `sweet` - Gentle, affectionate, loving
- `dominant` - Commanding, assertive, controlling
- `bratty` - Mischievous, demanding attention
- `seductive` - Sultry, enticing, mysterious

**Emoji Frequency:**
- `heavy` - Emojis in every message
- `moderate` - 2-3 emojis per message
- `light` - Occasional single emoji
- `none` - No emojis used

**Slang Level:**
- `none` - Formal, proper English
- `light` - Casual abbreviations (u, ur, etc.)
- `heavy` - Heavy slang and internet speak

**Boost Calculation:**
```python
def calculate_persona_boost(caption, persona):
    """
    Maximum combined boost: 1.40x
    """
    boost = 1.0

    if caption.tone == persona.primary_tone:
        boost *= 1.20

    if caption.emoji_style == persona.emoji_frequency:
        boost *= 1.10

    if caption.slang_level == persona.slang_level:
        boost *= 1.10

    return min(boost, 1.40)  # Cap at 1.40x
```

---

## 7. Content Rotation Pattern

### Recommended Daily Content Mix

| Position | Content Type | Notes |
|----------|--------------|-------|
| 1 | solo | Start with standard solo content |
| 2 | bundle | Multi-piece value offering |
| 3 | winner | High-performing rerun |
| 4 | sextape | Premium content |
| 5+ | Rotate | Continue pattern |

**Rotation Logic:**
```python
CONTENT_ROTATION = ['solo', 'bundle', 'winner', 'sextape']

def get_content_type_for_slot(slot_number):
    """
    Rule: Rotate through content types in order.
    Provides variety and prevents content fatigue.
    """
    index = (slot_number - 1) % len(CONTENT_ROTATION)
    return CONTENT_ROTATION[index]
```

**Content Type Categories:**
| Category | Types | Priority |
|----------|-------|----------|
| Solo | solo, selfie, lingerie | 1 (Standard) |
| Couples | bg, gg, bgg | 1 (Premium) |
| Acts | anal, creampie, squirt | 2 (Specialty) |
| Interactive | joi, dick_ratings | 3 (Custom) |
| Special | cosplay, fetish | 3 (Niche) |

---

## 8. Performance Scoring

### Caption Performance Categories

| Score Range | Tier | Label | Action |
|-------------|------|-------|--------|
| 80-100 | 1 | Winner | High priority, eligible for reruns |
| 60-79 | 2 | Good | Normal selection |
| 40-59 | 3 | Standard | Baseline pool |
| 0-39 | 4 | Loser | Avoid, may deactivate |

**Performance Score Factors:**
```python
def calculate_performance_score(caption):
    """
    Composite score based on:
    - avg_earnings (40% weight)
    - avg_purchase_rate (35% weight)
    - avg_view_rate (25% weight)
    """
    # Normalize to 0-100 scale
    earnings_score = min(caption.avg_earnings / 200 * 100, 100)  # Cap at $200 = 100
    purchase_score = caption.avg_purchase_rate * 100  # Already 0-1 scale
    view_score = caption.avg_view_rate * 100  # Already 0-1 scale

    return (earnings_score * 0.40) + (purchase_score * 0.35) + (view_score * 0.25)
```

---

## 9. Weight Calculation for Selection

### Combined Selection Weight

**Formula:**
```
weight = (performance_score * 0.6 + freshness_score * 0.4) * persona_boost
```

**Configuration:**
```bash
EROS_PERFORMANCE_WEIGHT=0.6
EROS_FRESHNESS_WEIGHT=0.4
```

**Example Calculations:**
| Caption | Perf Score | Fresh Score | Persona Boost | Final Weight |
|---------|------------|-------------|---------------|--------------|
| A | 90 | 80 | 1.20 | (90*0.6 + 80*0.4) * 1.20 = 103.2 |
| B | 70 | 100 | 1.00 | (70*0.6 + 100*0.4) * 1.00 = 82.0 |
| C | 50 | 50 | 1.40 | (50*0.6 + 50*0.4) * 1.40 = 70.0 |
| D | 80 | 30 | 1.10 | (80*0.6 + 30*0.4) * 1.10 = 66.0 |

---

## 10. Page Type Rules

### Paid vs Free Page Differences

| Rule | Paid Pages | Free Pages |
|------|------------|------------|
| PPV Price Range | $5 - $50 | $3 - $25 |
| Daily PPV Volume | Base volume | +20% volume |
| Bump Frequency | Standard | Higher |
| Wall Post Mix | Mix paid/free | Mostly free teasers |
| Follow-up Rate | Standard | Aggressive |

**Price Adjustment Logic:**
```python
def adjust_price_for_page_type(suggested_price, page_type):
    """
    Free pages have lower price ceiling.
    """
    if page_type == 'free':
        # Cap at $25 for free pages
        return min(suggested_price * 0.7, 25.0)
    else:
        # Paid pages can go up to $50
        return min(suggested_price, 50.0)
```

---

## 11. Timing Rules

### Best Hours for Scheduling

**Default Best Hours (if no analytics):**
```python
DEFAULT_BEST_HOURS = [10, 14, 18, 21]  # 10am, 2pm, 6pm, 9pm
```

**Analytics-Based Hours:**
```sql
-- Query best hours from analytics
SELECT best_mm_hours FROM creator_analytics_summary
WHERE creator_id = ? AND period_type = '30d';

-- JSON format: [{"hour": 21, "avg_earnings": 156.50, "count": 45}, ...]
```

**Day-of-Week Weighting:**
| Day | Typical Performance | Notes |
|-----|---------------------|-------|
| Friday | Highest | Weekend buildup |
| Saturday | Very High | Peak engagement |
| Sunday | High | Weekend continues |
| Monday | Medium | Work week starts |
| Tuesday | Low | Midweek dip |
| Wednesday | Low | Midweek dip |
| Thursday | Medium | Weekend approaching |

---

## 12. Validation Severity Levels

### Validation Issue Categories

| Severity | Behavior | Examples |
|----------|----------|----------|
| **Error** | Blocks schedule generation | PPV < 3hr spacing, exhausted caption |
| **Warning** | Allows but flags for review | PPV < 4hr spacing, stale caption |
| **Info** | Informational only | Non-optimal hour, low persona match |

**Validation Chain:**
```python
validators = [
    SpacingValidator(min_hours=4),      # PPV spacing
    FreshnessValidator(min_score=30),   # Caption freshness
    ContentValidator(),                  # Vault matching
    TimingValidator(),                   # Hour validation
    VolumeValidator(),                   # Daily limits
]

composite = CompositeValidator(validators)
result = composite.validate(schedule_items, context)

if not result.is_valid:
    raise ScheduleValidationError(result.errors)
```

---

## 13. Database Triggers & Auto-Updates

### Automatic Performance Updates

**When mass_message is inserted with earnings > 0:**
```sql
-- Updates caption_bank
UPDATE caption_bank
SET times_used = times_used + 1,
    total_earnings = total_earnings + NEW.earnings,
    avg_earnings = (total_earnings + NEW.earnings) / (times_used + 1),
    last_used_date = date(NEW.sending_time)
WHERE caption_id = NEW.caption_id;
```

**When caption is used:**
- `times_used` increments
- `total_earnings` accumulates
- `avg_earnings` recalculates
- `last_used_date` updates
- `freshness_score` decays on next calculation

---

## 14. Feature Flag Defaults

### All Feature Flags (Default: False)

| Flag | Description | Impact if Enabled |
|------|-------------|-------------------|
| enable_follow_ups | Generate follow-up bumps | +1 bump per qualifying PPV |
| enable_drip_windows | Enforce drip windows | PPVs rescheduled around drips |
| enable_type_rotation | Rotate content types | Enforces rotation pattern |
| enable_am_pm_split | Separate strategies | Different rules AM vs PM |
| enable_page_type_rules | Apply page type rules | Paid/free differentiation |
| enable_scheduler_targets | Use quotas | Enforce daily targets |
| enable_volume_strategy | Volume-based scheduling | Use volume assignments |
| enable_analytics_slots | Analytics-driven slots | Use best hours data |
| enable_ai_intelligence | AI briefs | Generate AI insights |
| enable_ai_scoring | AI scoring | AI rates captions |
| enable_ai_optimization | AI optimization | AI adjusts schedule |

---

## 15. Error Thresholds

### Schedule Generation Failures

| Condition | Threshold | Result |
|-----------|-----------|--------|
| No schedulable captions | 0 fresh captions | `CaptionExhaustionError` |
| Empty vault | No content types | `VaultEmptyError` |
| Creator not found | Invalid ID | `CreatorNotFoundError` |
| All validations fail | 100% error rate | `ValidationError` |

---

## Summary Tables

### Quick Reference: Key Thresholds

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| Min PPV spacing | 4 hours | `EROS_MIN_PPV_SPACING_HOURS` |
| Freshness half-life | 14 days | `EROS_FRESHNESS_HALF_LIFE_DAYS` |
| Freshness minimum | 30 | `EROS_FRESHNESS_MINIMUM_SCORE` |
| Exhaustion threshold | 25 | `EROS_FRESHNESS_EXHAUSTION_THRESHOLD` |
| Performance weight | 0.6 | `EROS_PERFORMANCE_WEIGHT` |
| Freshness weight | 0.4 | `EROS_FRESHNESS_WEIGHT` |
| Follow-up delay min | 15 min | (hardcoded) |
| Follow-up delay max | 45 min | (hardcoded) |
| Drip window | 4-8 hours | (hardcoded) |
| Max persona boost | 1.40x | (hardcoded) |

### Quick Reference: Volume Targets

| Volume Level | Fan Count | PPV/Day | Bump/Day |
|--------------|-----------|---------|----------|
| Low | < 1,000 | 2-3 | 2-3 |
| Mid | 1,000 - 5,000 | 4-5 | 4-5 |
| High | 5,000 - 15,000 | 6-8 | 6-8 |
| Ultra | 15,000+ | 8-10 | 8-10 |

### Quick Reference: Performance Tiers

| Score | Tier | Label | Eligibility |
|-------|------|-------|-------------|
| 80+ | 1 | Winner | Follow-ups, reruns |
| 60-79 | 2 | Good | Follow-ups |
| 40-59 | 3 | Standard | Normal pool |
| < 40 | 4 | Loser | Avoid |

---

## Version

- **Document Version:** 1.0
- **Created:** 2025-12-02
- **Source:** EROS CLI Codebase Analysis
