# Prediction Model Algorithm

> **Purpose**: ML-style caption performance prediction using structural, performance, temporal, and creator features
> **Version**: 3.0.0
> **Updated**: 2025-12-20
> **Status**: CANONICAL REFERENCE

## Feature Categories & Weights

```
Total Prediction Score = (
  Structural Features  * 0.40 +   // Caption structure analysis
  Performance Features * 0.30 +   // Historical performance data
  Temporal Features    * 0.20 +   // Time-based signals
  Creator Features     * 0.10     // Persona alignment
)
```

## Prediction Bounds

| Metric | Minimum | Maximum | Unit |
|--------|---------|---------|------|
| Predicted RPS | $0.00 | $50.00 | USD |
| Open Rate | 0.00 | 1.00 | Ratio |
| Conversion Rate | 0.00 | 0.50 | Ratio |

## Confidence Thresholds

| Confidence Level | Range | Action |
|------------------|-------|--------|
| HIGH | >= 0.80 | Full weight in selection |
| MEDIUM | 0.60-0.79 | Partial weight in selection |
| LOW | 0.40-0.59 | Advisory only |
| INSUFFICIENT | < 0.40 | Skip prediction |

## Feature Extraction Algorithms

### Structural Features (40% weight)

#### Caption Length Score
```
caption_length_score:
  - 250-449 chars = 100 (optimal, +107.6% RPS)
  - 200-249 chars = 85
  - 450-599 chars = 80
  - 150-199 chars = 70
  - 100-149 chars = 60
  - <100 or >600 chars = 40
```

#### Emoji Score
```
emoji_score:
  - 2-4 emojis = 100 (optimal blend)
  - 1 emoji = 80
  - 5-6 emojis = 70
  - 0 emojis = 50
  - >6 emojis = 40
```

#### CTA Score
```
cta_score:
  - Strong CTA present = 100
  - Weak/implied CTA = 70
  - No CTA = 40
```

#### Hook Strength Score
```
hook_strength_score:
  - Question hook = 100
  - Statement hook = 85
  - Emoji hook = 75
  - No clear hook = 50
```

### Performance Features (30% weight)

#### Historical RPS Score
```
historical_rps_score:
  - Based on caption's historical RPS if available
  - Normalized to 0-100 against creator's RPS distribution
```

#### Content Tier Score
```
content_tier_score:
  - TOP tier content = 100
  - MID tier content = 70
  - LOW tier content = 40
  - AVOID tier = 0 (should not be predicted)
```

#### Freshness Score
```
freshness_score:
  - Never used = 100
  - Used 30+ days ago = 80
  - Used 14-29 days ago = 60
  - Used 7-13 days ago = 40
  - Used <7 days ago = 20
```

### Temporal Features (20% weight)

#### Day of Week Score
```
day_of_week_score:
  - Weekend (Fri-Sun) = 100
  - Thursday = 85
  - Wednesday = 80
  - Tuesday = 75
  - Monday = 70
```

#### Hour of Day Score
```
hour_of_day_score:
  - Peak (6-10 PM) = 100
  - Shoulder (4-6 PM, 10 PM-12 AM) = 80
  - Midday (11 AM-4 PM) = 60
  - Morning (6-11 AM) = 50
  - Late night (12-6 AM) = 40
```

#### Recency Factor
```
recency_factor:
  - Adjust based on days_since_last_content_type
  - Long gap = higher anticipation = higher score
```

### Creator Features (10% weight)

#### Persona Match Score
```
persona_match_score:
  - Caption tone matches persona archetype = 100
  - Partial match = 70
  - Mismatch = 40
```

#### Voice Consistency Score
```
voice_consistency_score:
  - Matches creator's voice samples = 100
  - Neutral/generic = 70
  - Off-brand = 40
```

## RPS Prediction Algorithm

### Base RPS Determination
```
base_rps = CASE
  WHEN historical_rps EXISTS THEN historical_rps
  WHEN content_type_avg_rps EXISTS THEN content_type_avg_rps
  ELSE creator_avg_rps
END
```

### Prediction Multiplier Calculation
```
predicted_rps = base_rps * prediction_multiplier

prediction_multiplier = 1.0 + (
  (structural_score - 70) * 0.005 +    // +/-1.5% per 10 points
  (temporal_score - 70) * 0.003 +      // +/-0.9% per 10 points
  (freshness_bonus)                     // +0-20% for unused
)
```

### Freshness Bonus
```
freshness_bonus = CASE
  WHEN never_used THEN 0.20
  WHEN days_since_use > 30 THEN 0.10
  WHEN days_since_use > 14 THEN 0.05
  ELSE 0
END
```

## Confidence Score Calculation

```
confidence = (
  data_completeness * 0.40 +      // How much data we have
  historical_accuracy * 0.30 +    // Past prediction accuracy
  feature_reliability * 0.30      // Feature extraction quality
)
```

### Data Completeness
```
data_completeness:
  - All features available = 1.0
  - Missing 1-2 features = 0.8
  - Missing 3-4 features = 0.6
  - Missing 5+ features = 0.4
```

### Historical Accuracy
```
historical_accuracy:
  - Based on prediction_outcomes table
  - Default 0.7 if no history
```

## Self-Improvement Mechanism

### Feedback Loop

After sends complete:
1. Record actual RPS via `record_prediction_outcome()`
2. Calculate prediction error (actual - predicted)
3. Aggregate errors by feature category
4. Adjust weights via `update_prediction_weights()`
   - Increase weight for features that predicted well
   - Decrease weight for features that misled

### Weight Adjustment Formula
```
new_weight = current_weight * (1 + learning_rate * error_correlation)

learning_rate = 0.05 (conservative)
error_correlation = correlation(feature_score, rps_error)
```

### Accuracy Tracking

Track in `prediction_outcomes` table:
- `rps_error = actual_rps - predicted_rps`
- `rps_error_pct = rps_error / predicted_rps * 100`
- Weekly accuracy reports
- Feature importance drift detection

## Usage Example

```json
{
  "caption_id": 12345,
  "content_type": "b/g",
  "predicted_rps": 4.25,
  "predicted_open_rate": 0.42,
  "predicted_conversion_rate": 0.08,
  "prediction_score": 82.5,
  "confidence_score": 0.78,
  "confidence_tier": "MEDIUM",
  "feature_breakdown": {
    "structural": {"score": 88, "weight": 0.40, "contribution": 35.2},
    "performance": {"score": 75, "weight": 0.30, "contribution": 22.5},
    "temporal": {"score": 80, "weight": 0.20, "contribution": 16.0},
    "creator": {"score": 85, "weight": 0.10, "contribution": 8.5}
  },
  "key_factors": [
    "Optimal caption length (312 chars)",
    "TOP tier content type",
    "Weekend evening slot"
  ]
}
```

## Default Weights

If weight retrieval fails, use these defaults:
- Structural: 0.40
- Performance: 0.30
- Temporal: 0.20
- Creator: 0.10

## See Also

- `content-performance-predictor.md` - Agent implementation
- `caption-selection-pro.md` - Consumer of predictions
- `ppv-price-optimizer.md` - Uses predictions for pricing
- `DATA_CONTRACTS.md` - Prediction output format
