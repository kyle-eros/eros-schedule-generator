# Funnel Flow Patterns

> **Purpose**: Engagement-to-conversion funnel optimization patterns and flow scoring algorithms
> **Version**: 3.0.0
> **Updated**: 2025-12-20
> **Status**: CANONICAL REFERENCE

## Ideal Funnel Flow (Daily)

```
WARM-UP → BUILD → CONVERT → SUSTAIN

1. WARM-UP (First 1-2 sends)
   - Engagement types: bump_normal, bump_descriptive, link_drop
   - Purpose: Establish presence, generate opens

2. BUILD (Next 1-2 sends)
   - Engagement types: dm_farm, like_farm, bump_flyer
   - Purpose: Increase engagement depth, build anticipation

3. CONVERT (Peak hours)
   - Revenue types: ppv_unlock, ppv_wall, bundle
   - Purpose: Capitalize on engagement momentum

4. SUSTAIN (Throughout + End)
   - Retention types: renew_on_post, renew_on_message
   - Engagement types: bump_text_only, wall_link_drop
   - Purpose: Maintain relationship, set up tomorrow
```

## Flow Violations

Violations are detected patterns that harm conversion rates or subscriber relationships.

| Violation | Penalty | Description |
|-----------|---------|-------------|
| PPV before any engagement | -20 | Cold-start revenue push |
| Bundle as first send | -15 | Aggressive opening |
| 2+ consecutive revenue sends | -10 | Revenue clustering |
| Retention at day start | -5 | Awkward timing |
| No engagement before noon | -10 | Missing warm-up |
| PPV in off-peak hours | -5 | Suboptimal conversion timing |

## Hard Rules (Never Violate)

These rules MUST be enforced. Violations are CRITICAL.

1. **NEVER** schedule PPV as first send of the day
2. **NEVER** have 3+ consecutive revenue sends
3. **ALWAYS** have at least 1 engagement before first PPV
4. **ALWAYS** space revenue sends by minimum 2 hours

## Flow Scoring Algorithm

### Daily Funnel Score (0-100)

```
funnel_score = 100 - Σ violation_penalties

Score Interpretation:
  EXCELLENT: 90-100 (optimal flow)
  GOOD: 75-89 (minor issues)
  NEEDS_WORK: 60-74 (reordering recommended)
  POOR: <60 (mandatory reordering)
```

### Sequence Quality Metrics

```
sequence_quality = (
  warm_up_score * 0.30 +      // First sends are engagement
  build_score * 0.20 +        // Mid-sequence has variety
  convert_score * 0.30 +      // PPV at optimal times
  sustain_score * 0.20        // Day ends with relationship
)
```

#### Warm-Up Score
```
warm_up_score:
  - First 2 sends are engagement = 100
  - First send engagement, second revenue = 70
  - First send revenue = 0
```

#### Convert Score
```
convert_score:
  - All PPV in peak hours (5-10 PM) = 100
  - 75% PPV in peak = 80
  - 50% PPV in peak = 60
  - <50% PPV in peak = 40
```

#### Build Score
```
build_score:
  - 3+ different send types used = 100
  - 2 different send types = 70
  - 1 send type only = 40
```

#### Sustain Score
```
sustain_score:
  - Day ends with engagement or retention = 100
  - Day ends with revenue send = 60
```

## Violation Detection Algorithms

### PPV Before Engagement Check
```
sends = get_sends_for_day(day)
sends = sort_by_time(sends)

IF sends[0].category == 'revenue':
  violations.append({
    "type": "ppv_before_engagement",
    "penalty": -20,
    "position": 0
  })
```

### Consecutive Revenue Check
```
consecutive_revenue = 0
FOR send in sends:
  IF send.category == 'revenue':
    consecutive_revenue += 1
    IF consecutive_revenue >= 2:
      violations.append({
        "type": "consecutive_revenue",
        "penalty": -10,
        "position": send.index
      })
  ELSE:
    consecutive_revenue = 0
```

### Morning Engagement Check
```
morning_sends = [s for s in sends if s.time < '12:00']
IF not any(s.category == 'engagement' for s in morning_sends):
  violations.append({
    "type": "no_morning_engagement",
    "penalty": -10
  })
```

### PPV Timing Check
```
peak_hours = get_peak_hours(creator_id)  // Default: 17:00-22:00 (5-10 PM)

FOR send in sends:
  IF send.category == 'revenue' AND send.time not in peak_hours:
    violations.append({
      "type": "offpeak_ppv",
      "penalty": -5,
      "current_time": send.time
    })
```

## Reordering Recommendations

When `funnel_score < 75`, generate reordering recommendations:

### Move Engagement to Front
```
engagement_sends = [s for s in sends if s.category == 'engagement']
IF engagement_sends AND sends[0].category == 'revenue':
  reorder_plan.append({
    "action": "MOVE_TO_FRONT",
    "send_id": engagement_sends[0].id,
    "reason": "Warm-up before revenue"
  })
```

### Space Out Revenue Sends
```
revenue_sends = [s for s in sends if s.category == 'revenue']
FOR i in range(len(revenue_sends) - 1):
  time_gap = time_diff(revenue_sends[i+1], revenue_sends[i])
  IF time_gap < 2_hours:
    reorder_plan.append({
      "action": "INCREASE_GAP",
      "send_id": revenue_sends[i+1].id,
      "min_gap": "2 hours"
    })
```

### Move PPV to Peak Hours
```
FOR send in sends:
  IF send.category == 'revenue' AND send.time not in peak_hours:
    reorder_plan.append({
      "action": "MOVE_TO_PEAK",
      "send_id": send.id,
      "suggested_time": nearest_peak_slot(send.time)
    })
```

## Funnel Templates by Page Type

### PAID Page Funnel
```
Morning (6-10 AM):   bump_normal, wall_link_drop
Midday (11 AM-2 PM): dm_farm, like_farm
Afternoon (3-5 PM):  bump_descriptive, link_drop
Peak (6-10 PM):      ppv_unlock, ppv_wall, bundle
Late (10 PM+):       renew_on_message, bump_text_only
```

**Rationale**:
- Morning: Low-pressure engagement to establish presence
- Midday: Interactive content to build engagement
- Afternoon: Teaser content to build anticipation
- Peak: Revenue sends when subscribers are most active
- Late: Retention to maintain relationship overnight

### FREE Page Funnel
```
Morning:    bump_normal, wall_link_drop
Midday:     link_drop, live_promo
Afternoon:  bump_descriptive, dm_farm
Peak:       ppv_unlock, game_post, first_to_tip
Late:       bump_text_only
```

**Rationale**:
- No retention sends (free page doesn't have renewals)
- More engagement diversity to drive subscription conversions
- Peak focuses on conversion-oriented revenue types

## Funnel Stage Definitions

### Stage 1: WARM-UP
**Time Window**: Day start to 11:00 AM
**Send Types**:
- `bump_normal`
- `bump_descriptive`
- `link_drop`
- `wall_link_drop`

**Purpose**: Generate initial opens without asking for money.

### Stage 2: BUILD
**Time Window**: 11:00 AM to 5:00 PM
**Send Types**:
- `dm_farm`
- `like_farm`
- `bump_flyer`
- `live_promo`

**Purpose**: Deepen engagement, create conversation, build anticipation.

### Stage 3: CONVERT
**Time Window**: 5:00 PM to 10:00 PM (peak hours)
**Send Types**:
- `ppv_unlock`
- `ppv_wall`
- `bundle`
- `flash_bundle`
- `game_post`

**Purpose**: Capitalize on built-up engagement for revenue.

### Stage 4: SUSTAIN
**Time Window**: Throughout day + 10:00 PM onward
**Send Types**:
- `renew_on_post`
- `renew_on_message`
- `ppv_followup`
- `bump_text_only`

**Purpose**: Maintain subscriber relationship, set up next day.

## Flow Quality Examples

### Example 1: Excellent Flow (Score: 95)
```
Day: Monday
Sequence:
  08:00 - bump_normal (WARM-UP)
  11:30 - dm_farm (BUILD)
  15:00 - link_drop (BUILD)
  18:00 - ppv_unlock (CONVERT, peak)
  20:30 - ppv_wall (CONVERT, peak)
  22:00 - renew_on_message (SUSTAIN)

Violations: None
Score: 100 - 0 = 100
```

### Example 2: Good Flow (Score: 80)
```
Day: Tuesday
Sequence:
  09:00 - bump_descriptive (WARM-UP)
  13:00 - ppv_unlock (CONVERT, off-peak) [-5]
  17:00 - bundle (CONVERT, peak)
  19:00 - dm_farm (BUILD)

Violations:
  - PPV in off-peak hours (-5)
  - Somewhat awkward ordering (-5)

Score: 100 - 10 = 90
```

### Example 3: Poor Flow (Score: 55)
```
Day: Wednesday
Sequence:
  08:00 - ppv_unlock (CONVERT, off-peak) [-20 cold start, -5 off-peak]
  09:00 - ppv_wall (CONVERT, consecutive revenue) [-10, -5 off-peak]
  14:00 - bump_normal (WARM-UP, late)

Violations:
  - PPV before engagement (-20)
  - Consecutive revenue (-10)
  - 2x off-peak PPV (-10)
  - No morning engagement (-10)

Score: 100 - 50 = 50 (POOR - mandatory reordering)
```

## Output Format

```json
{
  "day": "Monday",
  "date": "2025-12-23",
  "original_score": 65,
  "optimized_score": 88,
  "send_count": 6,
  "sequence_summary": "ENGAGEMENT → ENGAGEMENT → REVENUE → ENGAGEMENT → REVENUE → RETENTION",
  "violations": [
    {
      "type": "offpeak_ppv",
      "penalty": -5,
      "detail": "PPV at 10:30 AM (pre-peak)",
      "recommendation": "Move to 6:00 PM slot"
    }
  ],
  "funnel_stages": {
    "warm_up": 2,
    "build": 1,
    "convert": 2,
    "sustain": 1
  }
}
```

## Decision Logic

```
IF funnel_score < 60:
  status = "POOR"
  action = "MANDATORY reordering before save"

ELSE IF funnel_score < 75:
  status = "NEEDS_WORK"
  action = "Reordering RECOMMENDED"

ELSE IF funnel_score < 90:
  status = "GOOD"
  action = "Optional optimization available"

ELSE:
  status = "EXCELLENT"
  action = "No changes needed"
```

## Integration Notes

### Peak Hours Source
- **Primary**: `get_best_timing(creator_id)` for creator-specific peaks
- **Fallback**: Default 17:00-22:00 (5-10 PM)

### Category Mapping
```
revenue_types = [
  'ppv_unlock', 'ppv_wall', 'bundle', 'flash_bundle',
  'game_post', 'first_to_tip', 'tip_goal',
  'vip_program', 'snapchat_bundle'
]

engagement_types = [
  'bump_normal', 'bump_descriptive', 'bump_text_only', 'bump_flyer',
  'link_drop', 'wall_link_drop', 'dm_farm', 'like_farm', 'live_promo'
]

retention_types = [
  'renew_on_post', 'renew_on_message', 'ppv_followup', 'expired_winback'
]
```

## See Also

- `funnel-flow-optimizer.md` - Agent implementation
- `timing-optimizer.md` - Provides timing context
- `SEND_TYPE_TAXONOMY.md` - Category classifications
- `schedule-assembler.md` - Preceding phase
