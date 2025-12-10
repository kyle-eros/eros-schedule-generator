# EROS Caption Selection Prompt
# Version: 2.1.0
# Purpose: Guide LLM reasoning for optimal caption selection during schedule generation

---

## OBJECTIVE

Select the optimal caption from a stratified pool for a given schedule slot, maximizing:
1. Revenue potential (earnings weight)
2. Content freshness (recency of use)
3. Creator voice authenticity (persona match)
4. Engagement diversity (hook rotation)

---

## POOL-BASED SELECTION STRATEGY

### Pool Definitions

**PROVEN Pool**
- Criteria: `creator_times_used >= 3 AND creator_avg_earnings > 0`
- Contains: Captions with verified earnings for THIS specific creator
- Trust Level: Highest - data-backed performer

**GLOBAL_EARNER Pool**
- Criteria: `creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0`
- Contains: Captions that earn well globally but are untested for this creator
- Trust Level: Medium - cross-portfolio signal

**DISCOVERY Pool**
- Criteria: All others (new imports, under-tested, no earnings data)
- Contains: Fresh content for testing and diversification
- Trust Level: Lower - requires experimentation

---

## SLOT TYPE MATCHING

### Premium Slots (Peak Hours: 6PM, 9PM)

**Selection Criteria:**
- Use PROVEN pool ONLY
- Prioritize captions with highest `creator_avg_earnings`
- Require `persona_boost >= 1.20`
- Freshness should be >= 50 for optimal performance

**Reasoning:**
Peak hours have maximum audience engagement. Use only battle-tested content with proven revenue performance for this creator.

### Standard Slots (Normal PPV Hours: 10AM, 2PM)

**Selection Criteria:**
- Use PROVEN + GLOBAL_EARNER pools
- Balance earnings with freshness
- Accept `persona_boost >= 1.10`
- Freshness >= 30 (minimum threshold)

**Reasoning:**
Standard slots balance revenue optimization with content freshness. Global earners provide diversification while maintaining revenue floor.

### Discovery Slots (Testing: Variable Hours)

**Selection Criteria:**
- Use DISCOVERY pool primarily
- Prioritize recent imports (< 30 days)
- Weight external imports higher (cross-platform content)
- Accept lower persona_boost (learning opportunity)

**Reasoning:**
Discovery slots test new content to build the PROVEN pool. Fresh imports have highest potential for becoming future winners.

---

## WEIGHT CALCULATION

### Formula
```
Final Weight = (Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)) * Penalties
```

### Component Breakdown

**Earnings Component (60%)**
```python
# For PROVEN pool:
earnings_score = (creator_avg_earnings / max_earnings_in_pool) * 100

# For GLOBAL_EARNER pool:
earnings_score = (global_avg_earnings / max_earnings_in_pool) * 100 * 0.80  # 20% discount

# For DISCOVERY pool:
earnings_score = (performance_score / 100) * 100 * 0.50  # 50% discount
```

**Freshness Component (15%)**
```python
# Half-life: 14 days
freshness_score = 100 * (0.5 ** (days_since_used / 14))

# Examples:
# Never used: 100.0
# 7 days ago: 70.7
# 14 days ago: 50.0
# 28 days ago: 25.0
```

**Persona Component (15%)**
```python
# Base boost factors:
# Primary tone match: 1.20x
# Emoji frequency match: +0.10x (cumulative)
# Slang level match: +0.10x (cumulative)
# Maximum: 1.40x (capped)
# No match: 0.95x penalty

persona_score = (persona_boost / 1.40) * 100
```

**Discovery Bonus (10%)**
```python
# Bonuses for DISCOVERY pool:
# Recent import (< 30 days): 1.5x
# External import: 1.2x
# High global earner: 1.3x
# Under-tested (< 3 uses): 1.5x
```

### Penalties

**Same Hook Penalty**
```python
# If caption has same hook_type as previous slot:
penalty = 0.70  # 30% reduction

# Applied to prevent consecutive same hooks
```

**Content Type Variety Penalty**
```python
# If same content_type as last 2 slots:
penalty = 0.85  # 15% reduction

# Encourages content rotation
```

---

## HOOK DIVERSITY REQUIREMENTS

### Hook Type Definitions

| Hook Type | Pattern Examples | Best For |
|-----------|------------------|----------|
| curiosity | "Guess what...", "You won't believe..." | Building anticipation |
| personal | "I miss you", "Thinking about you" | Emotional connection |
| exclusivity | "Only for VIPs", "Special for you" | Status/scarcity appeal |
| recency | "Just filmed", "Fresh content" | Time-sensitive urgency |
| question | "Want to see?", "Ready for...?" | Direct engagement |
| direct | "Unlock now", "Available now" | Clear conversion CTA |
| teasing | "Something special...", "Surprise" | Building anticipation |

### Rotation Rules

1. **Never** use same hook type 3x consecutively
2. **Warn** on 2x consecutive same hook (V015)
3. **Target** 4+ unique hook types per week (V016)
4. **Apply** 0.7x penalty for consecutive same hook

---

## PERSONA MATCHING GUIDELINES

### Tone Detection

When analyzing caption tone, look for:

**Playful**
- Keywords: "hehe", "lol", "babe", teasing language
- Energy: Light, flirty, fun
- Emoji style: Heart eyes, kiss, playful faces

**Sweet**
- Keywords: "miss you", "love", affection terms
- Energy: Warm, genuine, vulnerable
- Emoji style: Hearts, sparkles, gentle

**Seductive**
- Keywords: Allure, mystery, "come see", anticipation
- Energy: Sultry, enticing, suggestive
- Emoji style: Fire, lips, seductive faces

**Aggressive**
- Keywords: Demands, urgency, "now", commands
- Energy: Bold, assertive, provocative
- Emoji style: Fire, explosions, intensity

**Bratty**
- Keywords: "Whatever", sarcasm, playful demands
- Energy: Mischievous, attention-seeking
- Emoji style: Eye roll, tongue out, dismissive

### Boost Calculation Example

```
Creator Persona: playful, moderate emoji, light slang

Caption: "hehe guess what I filmed for you today babe"
- Primary tone: playful -> MATCH -> 1.20x
- Emoji frequency: none in text -> PARTIAL -> +0.05x
- Slang level: "babe" = light -> MATCH -> +0.10x
- Combined: 1.35x

Caption: "Unlock this content now. Available for limited time."
- Primary tone: direct -> NO MATCH -> 1.00x
- Emoji frequency: none -> MISS -> +0.00x
- Slang level: formal -> MISS -> 0.95x penalty
- Combined: 0.95x
```

---

## SELECTION DECISION TREE

```
START
  |
  v
What slot type?
  |
  +-- Premium (6PM, 9PM)
  |     |
  |     v
  |   Load PROVEN pool only
  |     |
  |     v
  |   Filter: freshness >= 50, persona_boost >= 1.20
  |     |
  |     v
  |   Sort by: earnings_score DESC
  |     |
  |     v
  |   Apply hook penalty if same as previous
  |     |
  |     v
  |   SELECT top candidate
  |
  +-- Standard (10AM, 2PM)
  |     |
  |     v
  |   Load PROVEN + GLOBAL_EARNER pools
  |     |
  |     v
  |   Filter: freshness >= 30, persona_boost >= 1.10
  |     |
  |     v
  |   Calculate combined weight
  |     |
  |     v
  |   Apply Vose Alias selection
  |     |
  |     v
  |   SELECT weighted random candidate
  |
  +-- Discovery
        |
        v
      Load DISCOVERY pool
        |
        v
      Apply discovery bonuses (imports, untested)
        |
        v
      Calculate combined weight
        |
        v
      SELECT weighted random candidate
```

---

## OUTPUT FORMAT

When providing caption selection reasoning, structure as:

```json
{
  "slot_id": "mon-ppv-1",
  "slot_type": "premium",
  "selected_caption": {
    "caption_id": 4521,
    "pool": "proven",
    "earnings_score": 85.2,
    "freshness_score": 87.3,
    "persona_boost": 1.32,
    "hook_type": "curiosity",
    "final_weight": 72.4
  },
  "reasoning": "Selected proven caption with strong earnings history ($82 avg). Hook type provides variety from previous 'personal' hook. Persona boost of 1.32x indicates strong voice match.",
  "alternatives_considered": 3,
  "penalties_applied": []
}
```

---

## COMMON EDGE CASES

### Pool Exhaustion
If primary pool is exhausted:
1. Log warning
2. Fall back to next pool tier
3. Continue selection with adjusted weights

### Low Freshness Week
If all captions < 30 freshness:
1. Raise `CaptionExhaustionError`
2. Recommend waiting for freshness recovery
3. Calculate days until recovery

### Hook Type Conflict
If no captions available without hook penalty:
1. Accept penalty as necessary
2. Log warning (V015)
3. Select best available with penalty applied

### Persona Mismatch
If no high-persona-boost captions:
1. Accept lower boost captions
2. Prioritize earnings over persona
3. Note mismatch in semantic_analysis

---

## REMEMBER

Caption selection is automated via `generate_schedule.py`. This prompt guides the **reasoning** behind selection, not manual selection.

The script handles:
- Database queries
- Pool stratification
- Weight calculations
- Vose Alias selection
- Validation enforcement

Your role is to understand and explain the selection logic, not execute it manually.
