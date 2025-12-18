# Follow-up Patterns

Guide for generating and scheduling follow-up messages in EROS schedules.

## Send Types That Generate Follow-ups

Only specific send types support automatic follow-up generation:

| Parent Type | Follow-up Type | Default Delay | Target Audience | Channel |
|-------------|----------------|---------------|-----------------|---------|
| ppv_unlock | ppv_followup | 20 minutes | ppv_non_purchasers | targeted_message |
| ppv_wall | ppv_followup | 20 minutes | ppv_non_purchasers | targeted_message |
| tip_goal | ppv_followup | 20 minutes | tip_goal_non_tippers | targeted_message |

### Identification

Send types with follow-up capability have `can_have_followup = 1` in the database.

```sql
SELECT send_type_key, can_have_followup
FROM send_types
WHERE can_have_followup = 1;

-- Returns:
-- ppv_unlock   | 1
-- ppv_wall     | 1
-- tip_goal     | 1
```

---

## Follow-up Generation Algorithm

### Step 1: Identify Eligible Items

```
FOR each item in schedule:
    IF item.send_type.can_have_followup == 1:
        eligible_items.append(item)
```

### Step 2: Create Follow-up Item

```
FOR each eligible_item in eligible_items:
    followup = new ScheduleItem()
    followup.send_type = "ppv_followup"
    followup.parent_send_id = eligible_item.id
    followup.is_follow_up = 1
    followup.channel = "targeted_message"
```

### Step 3: Set Parent Reference

```
followup.parent_item_id = eligible_item.id

// This creates the relationship:
// eligible_item (ppv_unlock) -> followup (ppv_followup)
```

### Step 4: Calculate Timing

```
base_delay = 20  // minutes (default)
acceptable_range = [15, 30]  // minutes

// Calculate follow-up time
followup.scheduled_time = eligible_item.scheduled_time + base_delay

// Validate within acceptable range
IF followup.scheduled_time < eligible_item.scheduled_time + 15:
    followup.scheduled_time = eligible_item.scheduled_time + 15

IF followup.scheduled_time > eligible_item.scheduled_time + 30:
    followup.scheduled_time = eligible_item.scheduled_time + 30
```

### Step 5: Assign Target Audience

```
followup.target_key = "ppv_non_purchasers"

// This ensures follow-up only reaches:
// - Subscribers who saw the original PPV
// - Subscribers who did NOT purchase
```

### Step 6: Select Follow-up Caption

```
// Query compatible captions
captions = get_send_type_captions(
    creator_id = creator.id,
    send_type_key = "ppv_followup",
    min_performance = 40,
    min_freshness = 30
)

// Select best available
followup.caption_id = captions[0].id
followup.caption_text = captions[0].text
```

---

## Caption Selection for Follow-ups

### Compatible Caption Types

Follow-up messages require specific caption types designed for urgency:

| Caption Type | Priority | Typical Length | Purpose |
|--------------|----------|----------------|---------|
| ppv_followup | 1 (Primary) | Short (<100 chars) | Standard follow-up |
| close_sale | 2 (Secondary) | Short (<100 chars) | Urgency/FOMO |

### Selection Query

```sql
SELECT c.caption_id, c.caption_text, c.performance_score
FROM captions c
JOIN send_type_caption_requirements stcr
    ON c.caption_type = stcr.caption_type
WHERE stcr.send_type_key = 'ppv_followup'
    AND c.creator_id = :creator_id
    AND c.performance_score >= 40
ORDER BY stcr.priority ASC, c.performance_score DESC
LIMIT 1;
```

### Caption Characteristics

**Effective follow-up captions:**
- Length: Under 100 characters
- Tone: Urgent but not pushy
- Message: Creates FOMO, limited time/availability
- Emoji: Moderate use (fire, eyes, arrow)

**Example follow-up captions:**
- "Still thinking about it? Only a few left..."
- "Don't miss out babe, this won't last..."
- "Last chance before it's gone..."

### Freshness Scoring

Follow-up captions are scored for freshness to prevent repetition:

```
freshness_score = 100 - (days_since_last_use * 10)

// Caption unused for 7+ days: score = 30+
// Caption used yesterday: score = 90
// Caption used today: score = 100 (may be deprioritized)
```

---

## Timing Rules

### Default Delay

- **Standard delay**: 20 minutes after parent send
- **Purpose**: Allows time for purchase decision

### Acceptable Range

| Minimum | Default | Maximum |
|---------|---------|---------|
| 15 minutes | 20 minutes | 30 minutes |

### Time Boundary Handling

**Late Night Rule**: Never schedule follow-ups past 11:30 PM.

```
cutoff_time = "23:30"  // 11:30 PM

IF followup.scheduled_time > cutoff_time:
    // Push to next day
    followup.scheduled_date = next_day
    followup.scheduled_time = "08:00"  // 8:00 AM

    // Log the adjustment
    log("Follow-up pushed to next day due to late timing")
```

**Example scenario:**
- Parent PPV scheduled at 11:15 PM
- Normal follow-up would be 11:35 PM (past cutoff)
- Adjusted follow-up: 8:00 AM next day

### Conflict Resolution

If follow-up timing conflicts with other scheduled items:

```
WHILE slot_occupied(followup.scheduled_time):
    followup.scheduled_time += 5  // Add 5 minutes

    IF followup.scheduled_time > parent_time + 30:
        // Exceeded maximum delay
        SKIP follow-up generation
        log("Could not schedule follow-up within valid window")
```

---

## Follow-up Item Structure

### Database Fields

```json
{
    "schedule_item_id": 12345,
    "template_id": 100,
    "scheduled_date": "2025-01-15",
    "scheduled_time": "14:20",
    "send_type_id": 20,
    "send_type_key": "ppv_followup",
    "channel_id": 3,
    "channel_key": "targeted_message",
    "target_id": 10,
    "target_key": "ppv_non_purchasers",
    "caption_id": 5678,
    "caption_text": "Last chance babe...",
    "is_follow_up": 1,
    "parent_item_id": 12344,
    "followup_delay_minutes": 20
}
```

### Relationship to Parent

```
Parent Item (ppv_unlock)
├── schedule_item_id: 12344
├── scheduled_time: 14:00
├── can_have_followup: 1
└── generated_followup_id: 12345

Follow-up Item (ppv_followup)
├── schedule_item_id: 12345
├── scheduled_time: 14:20
├── is_follow_up: 1
├── parent_item_id: 12344
└── followup_delay_minutes: 20
```

---

## Generation Rules Summary

### Always Generate Follow-up When:

1. Parent send_type has `can_have_followup = 1`
2. Valid time slot available within 15-30 min window
3. Not exceeding ppv_followup daily max (4/day)
4. Follow-up captions available for creator

### Never Generate Follow-up When:

1. Parent send_type has `can_have_followup = 0`
2. Would exceed 11:30 PM same-day cutoff (push to next day instead)
3. Would exceed ppv_followup daily limit
4. No compatible follow-up captions available
5. Parent item is itself a follow-up (no cascading)

### Validation Checklist

Before saving follow-up:

- [ ] Parent item has can_have_followup = 1
- [ ] Follow-up time is 15-30 min after parent
- [ ] Target is ppv_non_purchasers
- [ ] Caption type is ppv_followup or close_sale
- [ ] Daily ppv_followup count < 4
- [ ] Time respects 11:30 PM cutoff
- [ ] parent_item_id correctly set
- [ ] is_follow_up = 1

---

## Multiple Follow-ups Per Day

### Daily Limit

Maximum of 4 ppv_followup items per day (matching max_per_day for the type).

### Distribution Example

For a schedule with 3 PPV sends:

| Time | Parent Type | Follow-up Time |
|------|-------------|----------------|
| 10:00 | ppv_unlock | 10:20 |
| 14:00 | ppv_wall | 14:20 |
| 18:00 | tip_goal | 18:20 |

Total follow-ups: 3 (within daily limit of 4)

### When Limit is Reached

```
IF daily_followup_count >= 4:
    // Skip follow-up generation for remaining PPV items
    log("Follow-up limit reached, skipping for item: " + parent_id)

    // Optional: Prioritize highest-value PPV for follow-ups
    // based on price or expected conversion
```

---

## Performance Tracking

### Metrics to Monitor

- Follow-up conversion rate (views to purchases)
- Optimal delay timing analysis
- Caption effectiveness by follow-up
- Time-of-day conversion patterns

### Adjustment Based on Data

```
IF followup_conversion_rate > baseline:
    // Current timing effective
    MAINTAIN delay settings

IF followup_conversion_rate < baseline:
    // Consider adjustments
    IF delay < 20:
        INCREASE delay (more decision time)
    IF delay > 20:
        DECREASE delay (more urgency)
```
