# EROS Scheduling Business Rules Reference

## Overview

This document captures all business rules, thresholds, and constraints used in the EROS schedule generation pipeline. These rules have been extracted from the codebase and represent the operational logic for OnlyFans content scheduling.

**Version 2.1 Updates:**
- 12 new extended validation rules (V020-V031)
- 20+ content type support with constraint matrix
- Hook detection and rotation for anti-detection
- Page type compliance validation
- 30 total validation rules (V001-V018, V020-V031)

---

## Table of Contents

1. [PPV Spacing Rules](#1-ppv-spacing-rules)
2. [Follow-up Timing Rules](#2-follow-up-timing-rules)
3. [Drip Window Rules](#3-drip-window-rules)
4. [Volume Level Brackets](#4-volume-level-brackets)
5. [Freshness Thresholds](#5-freshness-thresholds)
6. [Persona Matching Boost Factors](#6-persona-matching-boost-factors)
7. [Content Rotation Pattern](#7-content-rotation-pattern)
8. [Performance Scoring](#8-performance-scoring)
9. [Weight Calculation for Selection](#9-weight-calculation-for-selection)
10. [Page Type Rules](#10-page-type-rules)
11. [Timing Rules](#11-timing-rules)
12. [Validation Severity Levels](#12-validation-severity-levels)
13. [Database Triggers & Auto-Updates](#13-database-triggers--auto-updates)
14. [Feature Flag Defaults](#14-feature-flag-defaults)
15. [Error Thresholds](#15-error-thresholds)
16. **[Extended Validation Rules (V020-V031)](#16-extended-validation-rules-v020-v031)** ⭐ NEW
17. **[Content Type Constraints Reference](#17-content-type-constraints-reference)** ⭐ NEW
18. **[Hook Detection and Rotation](#18-hook-detection-and-rotation)** ⭐ NEW
19. **[Page Type Compliance](#19-page-type-compliance)** ⭐ NEW
20. **[Validation Rule Summary (All 30 Rules)](#20-validation-rule-summary-all-30-rules)** ⭐ NEW

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

## 16. Extended Validation Rules (V020-V031)

### Content Type Constraint Validation

EROS Schedule Generator v2.1 introduces 12 extended validation rules to support 20+ content types with sophisticated constraints.

**Rule Summary:**

| Code | Name | Description | Severity | Auto-Fix |
|------|------|-------------|----------|----------|
| V020 | PAGE_TYPE_VIOLATION | Paid-only content on free page | ERROR | remove_item |
| V021 | VIP_POST_SPACING | Min 24h between VIP posts | ERROR | move_slot |
| V022 | LINK_DROP_SPACING | Min 4h between link drops | WARNING | move_slot |
| V023 | ENGAGEMENT_DAILY_LIMIT | Max 2 engagement posts/day | WARNING | move_to_next_day |
| V024 | ENGAGEMENT_WEEKLY_LIMIT | Max 10 engagement posts/week | WARNING | remove_item |
| V025 | RETENTION_TIMING | Retention content on days 5-7 | INFO | - |
| V026 | BUNDLE_SPACING | Min 24h between bundles | ERROR | move_slot |
| V027 | FLASH_BUNDLE_SPACING | Min 48h between flash bundles | ERROR | move_slot |
| V028 | GAME_POST_WEEKLY | Max 1 game post/week | WARNING | remove_item |
| V029 | BUMP_VARIANT_ROTATION | No 3x consecutive same bump | WARNING | swap_content_type |
| V030 | CONTENT_TYPE_ROTATION | No 3x consecutive same type | INFO | - |
| V031 | PLACEHOLDER_WARNING | Slot has no caption | INFO | - |

### V020: Page Type Violation

**Rule:** Content types with `page_type_filter = "paid"` cannot be scheduled on free pages.

**Paid-Only Content Types:**
- `vip_post` - VIP tier exclusive content
- `renew_on_post` - Subscription renewal reminders (feed)
- `renew_on_mm` - Subscription renewal reminders (mass message)
- `expired_subscriber` - Win-back messages for expired subs

**Auto-Correction:** Remove item from schedule (cannot fix page type mismatch).

### V021: VIP Post Spacing

**Rule:** VIP posts must be spaced at least 24 hours apart.

**Rationale:** VIP posts are $200+ tier content announcements that need spacing to maintain exclusivity and perceived value.

**Auto-Correction:** Move second VIP post to 24h + 15min after first.

### V022: Link Drop Spacing

**Rule:** Link drops (both `link_drop` and `wall_link_drop`) must be spaced at least 4 hours apart.

**Rationale:** Prevents appearing spammy and gives each link proper visibility.

**Auto-Correction:** Move second link drop to 4h + 15min after first.

### V023/V024: Engagement Limits

**Rule:** Engagement content (`dm_farm`, `like_farm`) limited to:
- **Daily:** Maximum 2 per day
- **Weekly:** Maximum 10 per week

**Rationale:** Maintains authenticity and avoids overly promotional appearance.

**Auto-Correction:**
- Daily violations: Move excess to next day
- Weekly violations: Remove excess items

### V025: Retention Timing

**Rule:** Retention content (`renew_on_post`, `renew_on_mm`) should be scheduled on days 5-7 of the week (Friday-Sunday).

**Rationale:** Renewal messages are most effective toward end of week when subscribers are closer to renewal dates.

**Severity:** INFO (recommendation, not enforced)

### V026/V027: Bundle Spacing

**Rules:**
- **Regular bundles:** 24 hours minimum spacing
- **Flash bundles:** 48 hours minimum spacing
- **Snapchat bundles:** 48 hours minimum spacing

**Rationale:** Maintains perceived value and avoids discount fatigue.

**Auto-Correction:** Move subsequent bundle to required spacing + 15min buffer.

### V028: Game Post Weekly Limit

**Rule:** Maximum 1 game post (spin the wheel, etc.) per week.

**Rationale:** Maintains special nature of gamification and avoids fatigue.

**Auto-Correction:** Remove excess game posts (keep first chronologically).

### V029: Bump Variant Rotation

**Rule:** No 3 consecutive bump messages of the same type.

**Bump Types:**
- `flyer_gif_bump`
- `descriptive_bump`
- `text_only_bump`
- `normal_post_bump`

**Rationale:** Rotating bump variants maintains authenticity and avoids predictable patterns.

**Auto-Correction:** Swap third consecutive bump to alternative bump type.

### V030: Content Type Rotation

**Rule:** No 3 consecutive items of the same content type (any type).

**Rationale:** Content variety improves engagement and prevents subscriber fatigue.

**Severity:** INFO (recommendation for non-bump types, enforced for bumps via V029)

### V031: Placeholder Warning

**Rule:** Warn when schedule slots have no caption assigned.

**Indicators:**
- `has_caption = False`
- `caption_id = None` and `caption_text = ""`

**Severity:** INFO (informational only, requires manual caption entry)

---

## 17. Content Type Constraints Reference

### Complete 20-Type Constraint Matrix

| Tier | Type ID | Channel | Page Filter | Min Spacing | Max Daily | Max Weekly | Follow-up |
|------|---------|---------|-------------|-------------|-----------|------------|-----------|
| 1 | ppv | mass_message | both | 3.0h | 5 | 35 | Yes |
| 1 | ppv_follow_up | mass_message | both | 0.25h | 5 | 35 | No |
| 1 | bundle | mass_message | both | 24.0h | 1 | 3 | Yes |
| 1 | flash_bundle | mass_message | both | 48.0h | 1 | 2 | Yes |
| 1 | snapchat_bundle | mass_message | both | 48.0h | 1 | 2 | Yes |
| 2 | vip_post | feed | **paid** | 24.0h | 1 | 3 | No |
| 2 | first_to_tip | feed | both | 12.0h | 1 | 3 | No |
| 2 | link_drop | feed | both | 4.0h | 3 | 21 | No |
| 2 | normal_post_bump | feed | both | 2.0h | 4 | 28 | No |
| 2 | renew_on_post | feed | **paid** | 24.0h | 1 | 2 | No |
| 2 | game_post | feed | both | 168.0h | 1 | 1 | No |
| 2 | flyer_gif_bump | feed | both | 4.0h | 2 | 14 | No |
| 2 | descriptive_bump | feed | both | 4.0h | 2 | 14 | No |
| 2 | wall_link_drop | feed | both | 4.0h | 2 | 14 | No |
| 2 | live_promo | feed | both | 24.0h | 1 | 3 | No |
| 3 | dm_farm | direct | both | 12.0h | 2 | 10 | No |
| 3 | like_farm | feed | both | 12.0h | 2 | 10 | No |
| 3 | text_only_bump | mass_message | both | 4.0h | 2 | 14 | No |
| 4 | renew_on_mm | mass_message | **paid** | 24.0h | 1 | 2 | No |
| 4 | expired_subscriber | direct | **paid** | 72.0h | 1 | 2 | No |

### Content Type Tiers

**Tier 1 - Direct Revenue:**
Primary monetization content types: PPV, bundles, flash sales.

**Tier 2 - Feed/Wall:**
Wall posts, bumps, promotional content, VIP announcements.

**Tier 3 - Engagement:**
Engagement farming, community interaction, casual messaging.

**Tier 4 - Retention:**
Subscriber renewal reminders, win-back campaigns.

### Channel Distribution

| Channel | Type Count | Content Types |
|---------|------------|---------------|
| mass_message | 7 | ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle, text_only_bump, renew_on_mm |
| feed | 11 | vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post, game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo, like_farm |
| direct | 2 | dm_farm, expired_subscriber |

---

## 18. Hook Detection and Rotation

### Phase 3 Anti-Detection System

EROS v2.1 implements caption hook detection to prevent algorithm-detectable patterns.

**Hook Types:**

| Hook Type | Pattern Examples | Usage Strategy |
|-----------|------------------|----------------|
| curiosity | "Guess what...", "You won't believe..." | Question-based intrigue |
| personal | "I was thinking...", "Just for you..." | Intimate direct address |
| exclusivity | "Only my VIPs...", "Special for..." | Scarcity and status |
| recency | "Just filmed...", "Fresh from..." | Time-sensitive urgency |
| question | "Want to see...", "Ready for...?" | Direct engagement query |
| direct | "Unlock now", "Available now" | Clear CTA |
| teasing | "Something special...", "I have a surprise..." | Anticipation building |

### Hook Rotation Rules

**V015: HOOK_ROTATION**
- **Severity:** WARNING
- **Rule:** No 2+ consecutive PPVs with same hook type
- **Detection:** Pattern matching on `caption_text` field
- **Penalty:** 0.70x weight penalty during selection if same hook as previous slot

**V016: HOOK_DIVERSITY**
- **Severity:** INFO
- **Rule:** Recommend 4+ different hook types in a 7-day week
- **Target:** Natural variation in messaging patterns
- **Measurement:** Count unique hook types across all PPV captions

### Hook Detection Logic

**Pattern Matching:**
```python
# Pseudo-code for hook detection
def detect_hook_type(caption_text):
    """
    Pattern-based hook type detection.
    Returns: (HookType, confidence_score)
    """
    if matches_pattern(caption_text, CURIOSITY_PATTERNS):
        return HookType.CURIOSITY, confidence
    elif matches_pattern(caption_text, PERSONAL_PATTERNS):
        return HookType.PERSONAL, confidence
    # ... etc
```

**Confidence Threshold:** 0.6 minimum confidence for classification

---

## 19. Page Type Compliance

### Paid vs Free Page Rules

**Page Type Filter Values:**
- `paid` - Only valid on paid subscription pages
- `free` - Only valid on free pages (currently no free-only types)
- `both` - Valid on any page type

### Paid-Only Content Types

The following content types require `page_type = "paid"`:

| Type ID | Rationale |
|---------|-----------|
| vip_post | VIP tier content only exists on paid pages |
| renew_on_post | Renewal reminders target existing paid subscribers |
| renew_on_mm | Renewal reminders target existing paid subscribers |
| expired_subscriber | Win-back campaigns target former paid subscribers |

**Validation:** V020 (PAGE_TYPE_VIOLATION) enforces this at schedule generation.

### Free Page Adjustments

When `page_type = "free"`:
- Price caps adjusted (typically 70% of paid page pricing)
- Volume increased (+20% more messages)
- Follow-up frequency increased (more aggressive)
- Wall post mix shifts to more free teasers

---

## 20. Validation Rule Summary (All 30 Rules)

### Core Validation Rules (V001-V019)

| Code | Rule Name | Severity | Auto-Fix |
|------|-----------|----------|----------|
| V001 | PPV_SPACING | ERROR/WARNING | move_slot |
| V002 | FRESHNESS_MINIMUM | ERROR/WARNING | swap_caption |
| V003 | FOLLOW_UP_TIMING | WARNING | adjust_timing |
| V004 | DUPLICATE_CAPTIONS | ERROR | swap_caption |
| V005 | VAULT_AVAILABILITY | WARNING | - |
| V006 | VOLUME_COMPLIANCE | WARNING | - |
| V007 | PRICE_BOUNDS | WARNING | - |
| V008 | WALL_POST_SPACING | ERROR/WARNING | move_slot |
| V009 | PREVIEW_PPV_LINKAGE | ERROR/WARNING | move_slot |
| V010 | POLL_SPACING | ERROR/WARNING | move_slot |
| V011 | POLL_DURATION | ERROR | - |
| V012 | GAME_WHEEL_VALIDITY | WARNING | - |
| V013 | WALL_POST_VOLUME | WARNING | - |
| V014 | POLL_VOLUME | WARNING | - |
| V015 | HOOK_ROTATION | WARNING | - |
| V016 | HOOK_DIVERSITY | INFO | - |
| V017 | CONTENT_ROTATION | INFO | - |
| V018 | EMPTY_SCHEDULE | WARNING | - |

### Extended Validation Rules (V020-V031)

See section 16 above for complete details.

**Total Validation Rules:** 30 (V001-V018 + V020-V031)

**Note:** V019 is reserved for future use.

---

## Version

- **Document Version:** 2.1
- **Created:** 2025-12-02
- **Updated:** 2025-12-09
- **Source:** EROS CLI Codebase Analysis - v2.1 Pool-Based Earnings
