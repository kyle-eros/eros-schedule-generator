# Analytics Algorithms Reference

This document describes the algorithms and formulas used in the EROS analytics engine
for caption selection, freshness calculation, and persona matching.

## Table of Contents

1. [Weight Calculation Formula](#weight-calculation-formula)
2. [Vose Alias Method](#vose-alias-method)
3. [Freshness Score Calculation](#freshness-score-calculation)
4. [Persona Boost Factors](#persona-boost-factors)
5. [Performance Metrics](#performance-metrics)
6. [Data Sources](#data-sources)

---

## Weight Calculation Formula

The caption selection weight combines performance history with freshness and persona matching.

### Formula

```
final_weight = (performance_score * 0.6 + freshness_score * 0.4) * persona_boost
```

### Components

| Component | Weight | Range | Description |
|-----------|--------|-------|-------------|
| `performance_score` | 60% | 0-100 | Historical earnings performance |
| `freshness_score` | 40% | 0-100 | How recently the caption was used |
| `persona_boost` | multiplier | 1.0-1.4 | Voice profile alignment |

### Example Calculation

```
Caption with:
  - performance_score = 75
  - freshness_score = 90
  - persona_boost = 1.20 (primary tone match)

Combined Score = (75 * 0.6) + (90 * 0.4) = 45 + 36 = 81
Final Weight = 81 * 1.20 = 97.2
```

### Weight Distribution Impact

| Scenario | Perf | Fresh | Boost | Weight |
|----------|------|-------|-------|--------|
| High performer, fresh | 90 | 95 | 1.0 | 92.0 |
| Winner with tone match | 85 | 80 | 1.20 | 99.6 |
| Average, very fresh | 50 | 100 | 1.05 | 73.5 |
| Old winner | 95 | 40 | 1.0 | 73.0 |
| Perfect match, moderate | 60 | 70 | 1.40 | 89.6 |

---

## Vose Alias Method

The Vose Alias Method provides O(1) selection time after O(n) preprocessing,
making it ideal for weighted random selection of captions.

### Algorithm Overview

1. **Preprocessing Phase (O(n)):**
   - Normalize weights to probabilities (multiply by n, divide by sum)
   - Partition items into "small" (prob < 1) and "large" (prob >= 1)
   - Build alias table by pairing small items with large items

2. **Selection Phase (O(1)):**
   - Pick random index i in [0, n-1]
   - Generate random value r in [0, 1]
   - If r < prob[i], return item[i]
   - Otherwise, return item[alias[i]]

### Why Vose Alias?

| Method | Preprocessing | Selection | Memory |
|--------|--------------|-----------|---------|
| Linear Search | O(1) | O(n) | O(n) |
| Binary Search | O(n) | O(log n) | O(n) |
| **Vose Alias** | O(n) | **O(1)** | O(n) |

For caption selection where we:
- Have ~500 eligible captions
- Need to select 30+ captions per week
- Run multiple times per schedule generation

The O(1) selection time provides significant performance benefits.

### Implementation Details

```python
class VoseAliasSelector:
    def __init__(self, items, weight_func):
        # Build probability and alias tables
        weights = [weight_func(item) for item in items]
        total = sum(weights)
        prob = [w * n / total for w in weights]

        # Partition into small and large
        small = [i for i, p in enumerate(prob) if p < 1.0]
        large = [i for i, p in enumerate(prob) if p >= 1.0]

        # Build alias table
        while small and large:
            l = small.pop()
            g = large.pop()
            self.prob[l] = prob[l]
            self.alias[l] = g
            prob[g] = (prob[g] + prob[l]) - 1.0
            (small if prob[g] < 1.0 else large).append(g)

    def select(self):
        i = random.randint(0, n - 1)
        return items[i] if random.random() < prob[i] else items[alias[i]]
```

### Reference

Keith Schwarz, "Darts, Dice, and Coins: Sampling from a Discrete Distribution"
https://www.keithschwarz.com/darts-dice-coins/

---

## Freshness Score Calculation

Freshness prevents overuse of high-performing captions by applying exponential decay
based on time since last use.

### Decay Formula

```
freshness = 100 * e^(-days * ln(2) / half_life)
```

Where:
- `days` = days since last use
- `half_life` = 14 days (configurable)
- Result is clamped to [0, 100]

### Decay Curve

| Days Since Use | Freshness Score |
|----------------|-----------------|
| 0 | 100.0 |
| 7 | 70.7 |
| 14 | 50.0 |
| 21 | 35.4 |
| 28 | 25.0 |
| 42 | 12.5 |

### Adjustment Factors

Freshness can be modified by additional factors:

| Adjustment | Effect | Condition |
|------------|--------|-----------|
| Heavy Use Penalty | -10 per use | times_used > 5 |
| Winner Bonus | +15 | performance_score >= 80 |
| New Caption Boost | +20 | never used (last_used_date IS NULL) |

### Example Calculation

```python
def calculate_freshness(days_since_use, times_used, performance_score, last_used_date):
    # Base exponential decay
    half_life = 14.0
    if days_since_use is None:
        base = 100.0  # Never used
    else:
        decay = math.exp(-days_since_use * math.log(2) / half_life)
        base = 100.0 * decay

    # Apply adjustments
    adjustments = 0.0

    # Heavy use penalty
    if times_used > 5:
        adjustments -= (times_used - 5) * 10

    # Winner bonus
    if performance_score >= 80:
        adjustments += 15

    # New caption boost
    if last_used_date is None:
        adjustments += 20

    return max(0.0, min(100.0, base + adjustments))
```

---

## Persona Boost Factors

Persona matching aligns caption voice with creator profile to improve authenticity.

### Boost Components

| Match Type | Boost | Cumulative | Example |
|------------|-------|------------|---------|
| Primary Tone | 1.20x | 1.20x | playful matches playful |
| Secondary Tone | 1.10x | 1.10x | sweet matches alt tone |
| Emoji Frequency | 1.05x | 1.26x | heavy matches heavy |
| Slang Level | 1.05x | 1.32x | light matches light |
| Sentiment Alignment | 1.05x | 1.39x | within 0.25 of avg |
| **Maximum Cap** | - | **1.40x** | All matches capped |

### Tone Detection (Text-Based)

When caption tone is not stored in database, text analysis detects tone:

```python
TONE_KEYWORDS = {
    "playful": ["hehe", "haha", "tease", "fun", "naughty"],
    "aggressive": ["now", "demand", "obey", "worship", "submit"],
    "sweet": ["baby", "honey", "love", "darling", "miss you"],
    "dominant": ["control", "power", "boss", "master", "permission"],
    "bratty": ["whatever", "duh", "omg", "totally", "deserve"],
    "seductive": ["seduce", "tempt", "desire", "crave", "fantasy"],
    "direct": ["exclusive", "deal", "unlock", "sale", "offer"]
}
```

Detection uses word boundary matching and phrase detection:
- Single words: `\b{keyword}\b` pattern
- Phrases: substring matching with 2x weight

### Sentiment Alignment

Sentiment scoring uses word lists:

```python
POSITIVE_WORDS = ["love", "amazing", "perfect", "exclusive", "special"]
NEGATIVE_WORDS = ["miss", "hurry", "limited", "final", "ending"]

def calculate_sentiment(text):
    positive = count_matches(text, POSITIVE_WORDS)
    negative = count_matches(text, NEGATIVE_WORDS)
    total = positive + negative
    if total == 0:
        return 0.5  # Neutral
    return 0.3 + (positive / total * 0.5)  # Range: 0.3-0.8
```

Alignment check:
```python
def check_alignment(caption_sentiment, persona_sentiment, tolerance=0.25):
    return abs(caption_sentiment - persona_sentiment) <= tolerance
```

### Boost Calculation Example

```
Creator Persona:
  - primary_tone: "playful"
  - emoji_frequency: "heavy"
  - slang_level: "light"
  - avg_sentiment: 0.55

Caption Analysis:
  - detected_tone: "playful" (matches primary)
  - emoji_style: "heavy" (matches)
  - slang_level: "light" (matches)
  - sentiment: 0.60 (within 0.25 of 0.55)

Boost Calculation:
  1.00 * 1.20 (primary tone) = 1.20
  1.20 * 1.05 (emoji) = 1.26
  1.26 * 1.05 (slang) = 1.32
  1.32 * 1.05 (sentiment) = 1.39

Final Boost: 1.39x (under 1.40 cap)
```

---

## Performance Metrics

### Creator Performance Metrics

| Metric | Formula | Source |
|--------|---------|--------|
| Total Earnings | SUM(earnings) | mass_messages |
| Avg Earnings/Message | AVG(earnings) WHERE type='ppv' | mass_messages |
| View Rate | viewed_count / sent_count | mass_messages |
| Purchase Rate | purchased_count / sent_count | mass_messages |
| Avg Earnings/Fan | total_earnings / active_fans | creators |

### Caption Performance Metrics

| Metric | Formula | Source |
|--------|---------|--------|
| Performance Score | Weighted avg of historical earnings | caption_bank |
| Times Used | COUNT of schedule assignments | caption_bank |
| Avg Earnings | Mean earnings when caption used | mass_messages |

### Best Hours Analysis

Query aggregates by `sending_hour`:
```sql
SELECT
    sending_hour,
    COUNT(*) as message_count,
    AVG(earnings) as avg_earnings,
    AVG(view_rate) as avg_view_rate
FROM mass_messages
WHERE creator_id = ? AND message_type = 'ppv'
GROUP BY sending_hour
HAVING COUNT(*) >= 3  -- Statistical relevance
ORDER BY avg_earnings DESC
```

### Week-over-Week Trends

```sql
WITH weekly_metrics AS (
    SELECT
        strftime('%Y-W%W', sending_time) AS week_id,
        SUM(earnings) as total_earnings,
        LAG(SUM(earnings)) OVER (ORDER BY week_id) as prev_week
    FROM mass_messages
    GROUP BY week_id
)
SELECT
    week_id,
    total_earnings,
    ROUND((total_earnings - prev_week) * 100.0 / prev_week, 1) as change_pct
FROM weekly_metrics
```

---

## Data Sources

### Primary Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `creators` | Creator profiles | creator_id, page_name, current_active_fans |
| `creator_personas` | Voice profiles | primary_tone, emoji_frequency, slang_level |
| `caption_bank` | Caption inventory | caption_id, performance_score, freshness_score |
| `mass_messages` | Historical sends | earnings, sending_hour, view_rate |
| `vault_matrix` | Content availability | content_type_id, has_content, quantity |
| `content_types` | Content categories | type_name, priority_tier |

### Key Indexes

| Index | Table | Purpose |
|-------|-------|---------|
| idx_mm_creator_time | mass_messages | Date range queries |
| idx_mm_creator_type_analytics | mass_messages | Performance analysis |
| idx_caption_creator_perf | caption_bank | Caption selection |
| idx_vault_creator | vault_matrix | Inventory lookups |

### Query Performance Targets

All analytics queries target < 100ms execution:

| Query | Target | Typical |
|-------|--------|---------|
| get_creator_profile.sql | < 10ms | 4ms |
| get_available_captions.sql | < 50ms | 4ms |
| get_optimal_hours.sql | < 50ms | 4ms |
| get_vault_inventory.sql | < 50ms | 12ms |
| get_performance_trends.sql | < 100ms | 4ms |

---

## Algorithm Selection Rationale

### Why Exponential Decay for Freshness?

- **Smooth transition**: No abrupt cliff at threshold
- **Configurable half-life**: Easy to tune decay rate
- **Natural interpretation**: "50% fresh after 2 weeks"
- **Mathematical simplicity**: Single parameter control

### Why 60/40 Performance/Freshness Split?

- **Performance matters more**: Historical winners should be weighted
- **Freshness prevents staleness**: Ensures variety for fans
- **Tuned from production data**: Balances engagement vs variety

### Why 1.40x Maximum Boost Cap?

- **Prevents runaway selection**: No single caption dominates
- **Preserves variety**: Even perfect matches don't guarantee selection
- **Tested threshold**: Provides meaningful differentiation without imbalance

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-02 | Initial analytics engine implementation |
