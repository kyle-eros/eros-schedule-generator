# PPV Pricing Rules

> **Purpose**: Dynamic PPV pricing optimization rules and adjustment algorithms
> **Version**: 3.0.0
> **Updated**: 2025-12-20
> **Status**: CANONICAL REFERENCE

## Hard Price Bounds

| Boundary | Value | Enforcement |
|----------|-------|-------------|
| **Floor** | $5.00 | Never price below this (HARD LIMIT) |
| **Ceiling** | $50.00 | Never exceed this (HARD LIMIT) |
| **Default** | Creator base price | Used when no optimization applies |

## Pricing Adjustment Rules

| Adjustment Type | Range | Trigger Condition |
|-----------------|-------|-------------------|
| Prediction Bonus | +10-25% | Predicted RPS > creator median |
| Time Premium | +15% | Weekend evenings (Fri-Sun, 6-10 PM) |
| Time Discount | -10% | Weekday mornings (Mon-Fri, 6-10 AM) |
| Scarcity Premium | +20% | First use of content type in 14+ days |
| Performance Premium | +15% | TOP tier content type |
| Freshness Premium | +10% | Caption never used before |
| Bundle Discount | -15% | Part of multi-PPV bundle |

## Never Adjust Conditions

DO NOT apply pricing optimization when:
- Creator has < 1000 subscribers (keep defaults)
- Active A/B price experiments are running
- Content types are in AVOID tier (should not be scheduled)

## Base Price Determination

```
base_price = creator.default_ppv_price OR content_type.avg_price OR $15.00
```

**Priority order**:
1. Creator's configured default PPV price
2. Historical average for this content type
3. System default ($15.00)

## Adjustment Stack (Multiplicative)

```
final_price = base_price * (1 + Σ adjustments)

adjustments = [
  prediction_adjustment,    // -0.10 to +0.25
  timing_adjustment,        // -0.10 to +0.15
  scarcity_adjustment,      // 0 to +0.20
  performance_adjustment,   // 0 to +0.15
  freshness_adjustment,     // 0 to +0.10
  bundle_adjustment         // -0.15 to 0
]

// Apply bounds after calculation
final_price = max($5.00, min($50.00, round(final_price, 0)))
```

**Order of Operations**:
1. Start with base price
2. Calculate all applicable adjustments
3. Sum adjustments (multiplicative)
4. Apply multiplier to base price
5. Enforce floor ($5.00) and ceiling ($50.00)
6. Round to nearest dollar

## Prediction Bonus Calculation

```
IF predicted_rps exists:
  median_rps = get_creator_median_rps(creator_id)

  IF predicted_rps > median_rps * 1.5:
    prediction_adjustment = +0.25  // Exceptional prediction
  ELSE IF predicted_rps > median_rps * 1.2:
    prediction_adjustment = +0.15  // Strong prediction
  ELSE IF predicted_rps > median_rps:
    prediction_adjustment = +0.10  // Above average
  ELSE IF predicted_rps < median_rps * 0.7:
    prediction_adjustment = -0.10  // Below average
  ELSE:
    prediction_adjustment = 0      // Neutral
```

**Confidence Requirement**:
- Only apply prediction bonus if `confidence_score > 0.6`
- Low confidence predictions are ignored for pricing

## Time Premium Rules

### Weekend Evening Premium (+15%)
```
IF day_of_week IN ['Friday', 'Saturday', 'Sunday']:
  IF time >= '18:00' AND time <= '22:00':
    timing_adjustment = +0.15
```

### Weekday Morning Discount (-10%)
```
IF day_of_week IN ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
  IF time >= '06:00' AND time <= '10:00':
    timing_adjustment = -0.10
```

### Neutral Timing (0%)
All other time slots receive no adjustment.

## Scarcity Premium Triggers

```
days_since_content_type = get_days_since_last_use(content_type)

IF days_since_content_type >= 14:
  scarcity_adjustment = +0.20
ELSE:
  scarcity_adjustment = 0
```

**Rationale**: Content not seen in 2+ weeks generates higher anticipation and willingness to pay.

## Performance Tier Adjustments

```
content_tier = get_content_type_tier(creator_id, content_type)

IF content_tier == 'TOP':
  performance_adjustment = +0.15
ELSE IF content_tier == 'MID':
  performance_adjustment = +0.05
ELSE:
  performance_adjustment = 0
```

**Note**: AVOID tier content should never reach pricing stage (rejected earlier).

## Freshness Premium

```
IF caption_never_used == TRUE:
  freshness_adjustment = +0.10
ELSE:
  freshness_adjustment = 0
```

**Rationale**: Brand new captions create novelty value.

## Bundle Discount

```
IF is_part_of_bundle == TRUE:
  bundle_adjustment = -0.15
ELSE:
  bundle_adjustment = 0
```

**Rationale**: Multi-PPV bundles need competitive pricing to drive bulk purchases.

## Pricing Examples

### Example 1: High-Performer, Weekend Evening
```
base_price = $15.00
predicted_rps = $4.50 (median: $2.80)
day = Saturday
time = 8:00 PM
content_tier = TOP
caption_never_used = TRUE

Adjustments:
  prediction_bonus = +0.25 (exceptional: 4.50 > 2.80 * 1.5)
  time_premium = +0.15 (weekend evening)
  performance = +0.15 (TOP tier)
  freshness = +0.10 (never used)
  Total = +0.65

final_price = $15.00 * (1 + 0.65) = $24.75 → rounds to $25.00
```

### Example 2: Below-Average, Weekday Morning
```
base_price = $18.00
predicted_rps = $1.50 (median: $2.80)
day = Tuesday
time = 9:00 AM
content_tier = MID
caption_used_before = TRUE

Adjustments:
  prediction_penalty = -0.10 (below: 1.50 < 2.80 * 0.7)
  time_discount = -0.10 (weekday morning)
  performance = +0.05 (MID tier)
  Total = -0.15

final_price = $18.00 * (1 - 0.15) = $15.30 → rounds to $15.00
```

### Example 3: Bundle with Scarcity
```
base_price = $12.00
is_bundle = TRUE
days_since_content = 21 days
content_tier = TOP

Adjustments:
  bundle_discount = -0.15 (part of bundle)
  scarcity = +0.20 (21 days > 14)
  performance = +0.15 (TOP tier)
  Total = +0.20

final_price = $12.00 * (1 + 0.20) = $14.40 → rounds to $14.00
```

## Decision Thresholds

| Scenario | Action | Price Impact |
|----------|--------|--------------|
| High-confidence prediction (>0.8) | Apply full adjustment | +10-25% |
| Medium confidence (0.6-0.8) | Apply partial adjustment | +5-15% |
| Low confidence (<0.6) | Skip prediction bonus | 0% |
| No prediction available | Use timing + performance only | Variable |
| Subscriber count <1000 | Skip optimization | 0% |

## Validation Checks

After calculating final prices, validate the distribution:

### Price Variety Check
```
IF all_same_price(prices):
  WARN "Price variety low - consider differentiation"
```

### Price Spread Check
```
IF max(prices) - min(prices) > $30:
  WARN "Price spread large - verify intentional"
```

### High-Price Concentration Check
```
IF count(prices > $30) > 2:
  WARN "Multiple high-price items - verify subscriber tier"
```

## Output Format

```json
{
  "item_index": 0,
  "send_type": "ppv_unlock",
  "content_type": "b/g",
  "base_price": 15.00,
  "optimized_price": 22.00,
  "adjustments": [
    {"type": "prediction_bonus", "value": 0.25, "reason": "Predicted RPS $4.50 vs median $2.80"},
    {"type": "time_premium", "value": 0.15, "reason": "Saturday 8 PM peak slot"},
    {"type": "scarcity_premium", "value": 0.20, "reason": "First b/g in 18 days"}
  ],
  "total_adjustment": 0.47,
  "confidence": 0.85
}
```

## Error Handling

| Error Condition | Fallback Action |
|-----------------|-----------------|
| Missing predictions | Proceed with timing/performance only |
| Missing creator profile | Use default bounds ($5-$50), log warning |
| MCP tool failures | Keep original prices, flag for review |
| Out-of-bounds calculation | Enforce floor/ceiling, log adjustment |

## See Also

- `ppv-price-optimizer.md` - Agent implementation
- `PREDICTION_MODEL.md` - ML prediction algorithms
- `content-performance-predictor.md` - Prediction source
- `revenue-optimizer.md` - Base price setting phase
