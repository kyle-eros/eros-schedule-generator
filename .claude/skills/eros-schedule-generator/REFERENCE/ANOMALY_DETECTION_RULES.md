# Anomaly Detection Rules

> **Purpose**: Statistical anomaly detection thresholds and algorithms for schedule validation
> **Version**: 3.0.0
> **Updated**: 2025-12-20
> **Status**: CANONICAL REFERENCE

## Anomaly Categories

### ERROR (BLOCK save)

Anomalies that indicate data integrity issues or critical violations. These MUST block schedule save.

| Anomaly Type | Threshold | Description |
|--------------|-----------|-------------|
| Price Outlier | > 3 standard deviations | Price far outside normal range |
| Volume Extreme | > 2x daily normal | Unusual send volume |
| Unknown Content Type | Content type not in rankings | Invalid content reference |
| Duplicate Caption | Same caption_id twice in day | Data integrity issue |
| Time Conflict | 2+ sends at exact same time | Scheduling conflict |

### WARNING (Advisory, allow save)

Anomalies that suggest potential issues but do not indicate data corruption.

| Anomaly Type | Threshold | Description |
|--------------|-----------|-------------|
| Time Clustering | > 4 sends in 2-hour window | Potential subscriber fatigue |
| Revenue Concentration | > 70% revenue in single day | Unbalanced monetization |
| Low Freshness Week | Avg freshness < 40 | Stale content risk |
| Content Repetition | Same content type > 40% | Low variety |
| Off-Peak Heavy | > 60% sends outside peak | Suboptimal timing |

### OPPORTUNITY (Optimization hints)

Patterns that suggest missed optimization potential.

| Anomaly Type | Detection | Description |
|--------------|-----------|-------------|
| Underutilized Performer | TOP tier used < 2x/week | Missing revenue potential |
| Peak Slot Empty | No sends in 7-9 PM window | Missed engagement window |
| Weekend Light | < 50% weekday volume | Growth opportunity |
| New Content Available | Unused vault entries | Fresh content potential |

## Statistical Thresholds

### Z-Score Thresholds

```
z_score = (value - mean) / standard_deviation

ERROR:   |z_score| > 3.0
WARNING: |z_score| > 2.0
NORMAL:  |z_score| <= 2.0
```

### Minimum Sample Requirements

- **Standard Deviation Calculation**: 30-day rolling window
- **Minimum Sample Size**: 10 data points for statistical validity
- **Outlier Definition**:
  - > 2σ for warnings
  - > 3σ for errors

## Detection Algorithms

### Price Anomaly Detection

```
FOR each PPV item:
  creator_price_stats = get_price_statistics(creator_id, 30_days)
  z_score = (item.price - creator_price_stats.mean) / creator_price_stats.std

  IF z_score > 3 OR z_score < -3:
    ANOMALY(ERROR, "price_outlier", {
      price: item.price,
      mean: creator_price_stats.mean,
      std: creator_price_stats.std,
      z_score: z_score
    })
  ELSE IF z_score > 2 OR z_score < -2:
    ANOMALY(WARNING, "price_unusual", {
      price: item.price,
      mean: creator_price_stats.mean,
      std: creator_price_stats.std,
      z_score: z_score
    })
```

**Example Output**:
```json
{
  "type": "price_outlier",
  "severity": "ERROR",
  "details": {
    "price": 45.00,
    "mean": 15.50,
    "std": 4.25,
    "z_score": 6.94
  },
  "recommendation": "Verify intentional high price or adjust to $15-25 range"
}
```

### Volume Anomaly Detection

```
daily_volumes = count_sends_per_day(schedule)
volume_config = get_volume_config(creator_id)

FOR each day, count in daily_volumes:
  expected = volume_config.daily_total
  ratio = count / expected

  IF ratio > 2.0:
    ANOMALY(ERROR, "volume_extreme", {
      day: day,
      actual: count,
      expected: expected,
      ratio: ratio
    })
  ELSE IF ratio > 1.5:
    ANOMALY(WARNING, "volume_high", {
      day: day,
      actual: count,
      expected: expected,
      ratio: ratio
    })
  ELSE IF ratio < 0.5:
    ANOMALY(WARNING, "volume_low", {
      day: day,
      actual: count,
      expected: expected,
      ratio: ratio
    })
```

**Thresholds**:
- **ERROR**: > 2x expected (e.g., 12 sends when expecting 6)
- **WARNING (high)**: 1.5-2x expected
- **WARNING (low)**: < 0.5x expected
- **NORMAL**: 0.5-1.5x expected

### Time Clustering Detection

```
FOR each day in schedule:
  sends = get_sends_for_day(day)
  sends = sort_by_time(sends)

  // Sliding 2-hour window
  FOR i in range(len(sends) - 3):
    window_sends = sends[i:i+4]
    time_span = time_diff(window_sends[-1], window_sends[0])

    IF time_span <= 2_hours AND len(window_sends) >= 4:
      ANOMALY(WARNING, "time_clustering", {
        day: day,
        window_start: window_sends[0].time,
        window_end: window_sends[-1].time,
        count: len(window_sends)
      })
```

**Detection Logic**:
- Use sliding window of 4 sends
- Calculate time span between first and last in window
- If span ≤ 2 hours with 4+ sends → cluster detected

**Rationale**: 4+ notifications in 2 hours risks subscriber fatigue.

### Duplicate Detection

```
seen_captions = {}
seen_times = {}

FOR each item in schedule:
  day_key = item.scheduled_date

  // Check duplicate captions within same day
  IF (day_key, item.caption_id) in seen_captions:
    ANOMALY(ERROR, "duplicate_caption", {
      caption_id: item.caption_id,
      day: day_key,
      positions: [seen_captions[(day_key, item.caption_id)], item.index]
    })
  seen_captions[(day_key, item.caption_id)] = item.index

  // Check time conflicts
  time_key = (day_key, item.scheduled_time)
  IF time_key in seen_times:
    ANOMALY(ERROR, "time_conflict", {
      time: item.scheduled_time,
      day: day_key,
      conflicting_items: [seen_times[time_key], item.index]
    })
  seen_times[time_key] = item.index
```

**Two-Pass Detection**:
1. **Caption duplicates**: Same caption_id appearing twice on same day
2. **Time conflicts**: Multiple items scheduled at identical time

Both are ERROR-level violations.

### Revenue Concentration Detection

```
daily_revenue = {}
FOR each item in schedule:
  IF item.category == 'revenue':
    daily_revenue[item.day] += item.suggested_price

total_revenue = sum(daily_revenue.values())
FOR day, revenue in daily_revenue.items():
  concentration_pct = (revenue / total_revenue) * 100

  IF concentration_pct > 70:
    ANOMALY(WARNING, "revenue_concentration", {
      day: day,
      revenue: revenue,
      total_revenue: total_revenue,
      concentration_pct: concentration_pct
    })
```

**Threshold**: > 70% of weekly revenue in a single day suggests imbalanced monetization.

### Content Repetition Detection

```
content_type_counts = count_by_content_type(schedule)
total_sends = len(schedule)

FOR content_type, count in content_type_counts.items():
  percentage = (count / total_sends) * 100

  IF percentage > 40:
    ANOMALY(WARNING, "content_repetition", {
      content_type: content_type,
      count: count,
      total_sends: total_sends,
      percentage: percentage
    })
```

**Threshold**: Single content type exceeding 40% of schedule indicates low variety.

### Opportunity Detection Algorithms

#### Underutilized High Performers
```
top_types = get_top_content_types(creator_id, limit=5)
schedule_types = count_content_types(schedule)

FOR content_type in top_types:
  IF schedule_types.get(content_type, 0) < 2:
    ANOMALY(OPPORTUNITY, "underutilized_performer", {
      content_type: content_type,
      tier: "TOP",
      current_count: schedule_types.get(content_type, 0),
      suggested_minimum: 2
    })
```

**Rationale**: TOP tier content should appear at least 2x per week.

#### Empty Peak Slots
```
peak_hours = range(19, 22)  // 7-10 PM
FOR day in schedule_days:
  day_sends = get_sends_for_day(day)
  peak_sends = [s for s in day_sends if s.hour in peak_hours]

  IF len(peak_sends) == 0:
    ANOMALY(OPPORTUNITY, "peak_slot_empty", {
      day: day,
      peak_window: "7-10 PM"
    })
```

**Rationale**: Every day should have at least one send during peak engagement hours.

#### Weekend Light Detection
```
weekday_count = count_sends(schedule, days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
weekend_count = count_sends(schedule, days=['Sat', 'Sun'])

weekend_ratio = weekend_count / weekday_count * (5/2)  // Normalize for day count

IF weekend_ratio < 0.5:
  ANOMALY(OPPORTUNITY, "weekend_light", {
    weekday_count: weekday_count,
    weekend_count: weekend_count,
    normalized_ratio: weekend_ratio
  })
```

**Rationale**: Weekends typically have higher engagement; under-scheduling is a missed opportunity.

#### New Content Available
```
vault_types = get_vault_content_types(creator_id)
used_types = get_used_content_types(schedule)

unused_types = [t for t in vault_types if t not in used_types]

FOR content_type in unused_types:
  vault_count = count_vault_entries(creator_id, content_type)
  ANOMALY(OPPORTUNITY, "new_content_available", {
    content_type: content_type,
    vault_entries: vault_count,
    last_used: "never",
    suggestion: "Test new content type with 1-2 sends"
  })
```

## Decision Logic

```
IF error_count > 0:
  status = "BLOCKED"
  action = "REJECT schedule, return to schedule-assembler"

ELSE IF warning_count > 5:
  status = "PASS_WITH_WARNINGS"
  action = "ALLOW save with prominent warnings"

ELSE:
  status = "PASS"
  action = "ALLOW save, include opportunities in report"
```

## Output Format

```json
{
  "anomaly_status": "PASS" | "BLOCKED" | "PASS_WITH_WARNINGS",
  "summary": {
    "error_count": 0,
    "warning_count": 2,
    "opportunity_count": 3,
    "items_analyzed": 42
  },
  "errors": [],
  "warnings": [
    {
      "type": "time_clustering",
      "severity": "WARNING",
      "day": "Tuesday",
      "details": {
        "window_start": "18:00",
        "window_end": "19:45",
        "send_count": 4
      },
      "recommendation": "Spread sends over 3+ hour window",
      "impact": "Potential subscriber notification fatigue"
    }
  ],
  "opportunities": [
    {
      "type": "underutilized_performer",
      "content_type": "lingerie",
      "current_usage": 1,
      "suggested_minimum": 3,
      "potential_impact": "+$50-100 weekly revenue"
    }
  ],
  "statistics": {
    "price_mean": 16.50,
    "price_std": 4.25,
    "volume_expected": 6.0,
    "volume_actual_avg": 5.8,
    "freshness_avg": 72.5
  }
}
```

## Statistical Context Requirements

### Price Statistics
- **Window**: 30-day rolling average
- **Fields**: mean, standard_deviation, min, max
- **Minimum samples**: 10 PPV sends

### Volume Statistics
- **Source**: `get_volume_config()` expected daily total
- **Comparison**: Actual vs. expected ratio

### Freshness Statistics
- **Calculation**: Average freshness score across all selected captions
- **Scale**: 0-100 (100 = never used)

## Error Handling

| Error Condition | Fallback Action |
|-----------------|-----------------|
| Missing historical data | Use conservative thresholds, note in report |
| Calculation overflow | Cap z-scores at ±5, log warning |
| MCP failures | Proceed with limited detection, flag incomplete analysis |
| Empty schedule | Return immediate ERROR for empty input |

## Z-Score Examples

### Example 1: Normal Price
```
price = $18.00
mean = $16.50
std = $4.25
z_score = (18.00 - 16.50) / 4.25 = 0.35

Result: NORMAL (|0.35| < 2.0)
```

### Example 2: Warning Price
```
price = $28.00
mean = $16.50
std = $4.25
z_score = (28.00 - 16.50) / 4.25 = 2.71

Result: WARNING (2.0 < |2.71| < 3.0)
```

### Example 3: Error Price
```
price = $45.00
mean = $16.50
std = $4.25
z_score = (45.00 - 16.50) / 4.25 = 6.71

Result: ERROR (|6.71| > 3.0)
```

## See Also

- `anomaly-detector.md` - Agent implementation
- `quality-validator.md` - Preceding validation phase
- `performance-analyst.md` - Source of trend data
- `VALIDATION_RULES.md` - Rule-based validation
