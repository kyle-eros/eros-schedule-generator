# Integrated Claude Code Sub-Agents
## eros-schedule-generator Skill Package

This document lists all Claude Code sub-agents integrated into the eros-schedule-generator workflow.

---

## Overview

The eros-schedule-generator skill integrates **7 specialized sub-agents** located in `~/.claude/agents/eros-scheduling/`. These agents are invoked via the skill workflow and can be enabled with the `--use-agents` flag during schedule generation.

**Architecture Version:** 2.0 (Consolidated - December 2025)

---

## Agent Summary Table

| Agent | Model | Purpose | Cache |
|-------|-------|---------|-------|
| timezone-optimizer | Haiku | Peak engagement windows | 30 days |
| content-strategy-optimizer | Sonnet | Content analysis + rotation | 7 days |
| volume-calibrator | Sonnet | Volume optimization + page rules | 3 days |
| revenue-optimizer | Sonnet | Pricing + revenue projections | 7 days |
| multi-touch-sequencer | Opus | 3-touch follow-up sequences | 1 day |
| validation-guardian | Sonnet | Business rule validation | Never |
| onlyfans-business-analyst | Opus | Strategic analysis + web research | 14 days |

---

## Integrated Sub-Agents

### 1. timezone-optimizer
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/timezone-optimizer.md` |
| **Model** | Haiku (fast, cost-effective) |
| **Pipeline Phase** | Phase 1 (Data Collection) |
| **Timeout** | 15 seconds |
| **Cache Duration** | 30 days |

**What it does:**
- Queries historical engagement data by hour and day of week
- Identifies peak engagement windows (Tier 1 and Tier 2)
- Identifies low-engagement windows to avoid
- Generates daily schedule templates with optimal send times
- Considers EST/PST timezone distribution
- Analyzes 90+ days of historical PPV performance

**Expected Improvement:** +10% engagement through timing optimization

---

### 2. content-strategy-optimizer (HYBRID)
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/content-strategy-optimizer.md` |
| **Model** | Sonnet (pattern recognition + reasoning) |
| **Pipeline Phase** | Phase 2 (Optimization) |
| **Timeout** | 30 seconds |
| **Cache Duration** | 7 days |

**Merges functionality from:**
- ~~content-performance-analyzer~~ (deprecated)
- ~~content-rotation-architect~~ (deprecated)

**What it does:**
- Classifies PPV captions by content type using semantic markers
- Calculates performance metrics by content category
- Identifies top 5 and bottom 5 performing content types per creator
- Updates the `top_content_types` table with fresh data
- Analyzes vault inventory and content availability
- Matches content types to creator persona/niche
- Designs weekly rotation patterns with proper spacing
- Prevents audience fatigue through strategic variety
- Generates vault warnings and recommendations

**Output:**
```json
{
  "top_performers": [...],
  "weekly_rotation": [...],
  "spacing_rules": {...},
  "vault_warnings": [...]
}
```

**Expected Improvement:** +12% retention through better variety

---

### 3. volume-calibrator (HYBRID)
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/volume-calibrator.md` |
| **Model** | Sonnet (statistical analysis) |
| **Pipeline Phase** | Phase 2 (Optimization) |
| **Timeout** | 30 seconds |
| **Cache Duration** | 3 days |

**Merges functionality from:**
- ~~ppv-volume-optimizer~~ (deprecated)
- ~~page-type-optimizer~~ (deprecated)

**What it does:**
- Loads creator profile and determines fan count bracket
- Queries volume-to-earnings correlation data
- Calculates saturation score and opportunity score
- Generates data-driven volume recommendation
- Determines page type (paid vs free) and applies appropriate rules
- Enforces weekly PPV caps for paid pages (5-7 max)
- Enforces daily PPV caps for free pages (4-6 max)
- Sets pricing floors and ceilings per page type
- Applies constraints as ceiling to data-driven recommendation

**Decision Hierarchy:**
1. Calculate data-driven recommendation (saturation analysis)
2. Load page-type constraints (caps from rules)
3. Apply constraints: final = min(recommendation, cap)
4. Document which constraint was binding

**Output:**
```json
{
  "saturation_score": 28,
  "data_driven_recommendation": {"action": "MAINTAIN", "target_volume": 4.5},
  "page_type_constraints": {"ppv_weekly_cap": 5, "price_floor": 15},
  "final_recommendation": {"ppv_per_day": 4, "constraint_binding": "page_type_weekly_cap"}
}
```

**Expected Improvement:** Prevents over-saturation, optimizes volume for earnings

---

### 4. revenue-optimizer (HYBRID)
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/revenue-optimizer.md` |
| **Model** | Sonnet (mathematical projections) |
| **Pipeline Phase** | Phase 2 (Optimization) |
| **Timeout** | 30 seconds |
| **Cache Duration** | 7 days |

**Merges functionality from:**
- ~~pricing-strategist~~ (deprecated)
- ~~revenue-forecaster~~ (deprecated)

**What it does:**
- Analyzes conversion rates by price point for each creator
- Calculates optimal pricing per content type
- Applies performance-based pricing adjustments
- Considers page type (paid vs free) modifiers
- Analyzes 30-90 day revenue trends
- Calculates revenue by source (PPV, follow-ups, tips)
- Generates conservative/expected/optimistic projections
- Identifies risk factors and opportunities
- Provides A/B test suggestions for pricing

**Output:**
```json
{
  "pricing_strategy": {...},
  "projections": {
    "conservative": {"revenue": 750, "confidence": 0.85},
    "expected": {"revenue": 1050, "confidence": 0.70},
    "optimistic": {"revenue": 1400, "confidence": 0.55}
  },
  "recommendations": [...]
}
```

**Expected Improvement:** +15-20% revenue through optimized pricing

---

### 5. multi-touch-sequencer
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/multi-touch-sequencer.md` |
| **Model** | Opus (creative writing + psychology) |
| **Pipeline Phase** | Phase 3 (Follow-up Design) |
| **Timeout** | 45 seconds |
| **Cache Duration** | 1 day |

**What it does:**
- Designs 3-touch follow-up sequences with escalating urgency
- Matches psychological triggers to creator persona
- Varies tone and approach across each touch:
  - Touch 1 (15-45 min): Soft curiosity
  - Touch 2 (18-24 hours): Playful pressure
  - Touch 3 (24-72 hours): Scarcity close
- Sets optimal timing based on content type and price
- Defines abort triggers to prevent negative engagement

**Expected Improvement:** +25% conversion recovery from non-openers

---

### 6. validation-guardian
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/validation-guardian.md` |
| **Model** | Sonnet (rule checking) |
| **Pipeline Phase** | Phase 4 (Validation) |
| **Timeout** | 30 seconds |
| **Cache Duration** | 0 (never cached) |

**What it does:**
- Performs comprehensive rule checking on generated schedules
- Categorizes issues by severity (error, warning, info)
- Generates auto-fix suggestions for violations
- Validates data integrity and consistency

**Critical Rules (7 Errors):**
- V001: PPV_SPACING >= 3 hours
- V002: FRESHNESS_MINIMUM >= 30
- V003: FOLLOW_UP_TIMING 15-45 minutes
- V004: DUPLICATE_CAPTIONS zero per week
- V005: VAULT_AVAILABILITY verified
- V006: VOLUME_COMPLIANCE within range
- V007: PRICE_BOUNDS $5-$200

**Warning Rules (7):**
- W001: PPV_SPACING_RECOMMENDED >= 4 hours
- W002: CONTENT_ROTATION max 2 consecutive
- W003: FRESHNESS_OPTIMAL >= 50
- W004: PERSONA_MATCH boost >= 1.0
- W005: PEAK_WINDOW_UTILIZATION >= 70%
- W006: BUNDLE_FREQUENCY max 2/week
- W007: CROSS_PAGE_UNIQUENESS

**Expected Improvement:** 100% business rule compliance

---

### 7. onlyfans-business-analyst
| Property | Value |
|----------|-------|
| **Location** | `~/.claude/agents/eros-scheduling/onlyfans-business-analyst.md` |
| **Model** | Opus (strategic reasoning + web research) |
| **Pipeline Phase** | Phase 1 (Data Collection) - Optional |
| **Timeout** | 45 seconds |
| **Cache Duration** | 14 days |

**What it does:**
- Executes mandatory web research for current 2025 market intelligence
- Provides tier-specific business strategy (Emerging/Growing/Established/Elite/Ultra)
- Analyzes creator niche and provides style-specific recommendations
- Validates pricing against current market benchmarks
- Identifies growth opportunities and risk factors
- Provides research-backed recommendations with citations

**When invoked:**
- Monthly strategic refresh
- When tier changes are detected
- When pricing decisions need market validation
- Before finalizing high-value creator schedules (>$5K/month)

**Expected Improvement:** Market-aligned strategy, validated benchmarks

---

## Pipeline Flow

When `--use-agents` flag is enabled, agents are invoked in phases:

```
[Schedule Request]
        |
        v
Phase 1: Data Collection (PARALLEL)
|-- timezone-optimizer (Haiku, 15s)
|-- onlyfans-business-analyst (Opus, 45s) *when strategic context needed
        |
        v
Phase 2: Optimization (SEQUENTIAL)
|-- content-strategy-optimizer (Sonnet, 30s)
|-- volume-calibrator (Sonnet, 30s)
|-- revenue-optimizer (Sonnet, 30s)
        |
        v
Phase 3: Follow-up Design
|-- multi-touch-sequencer (Opus, 45s)
        |
        v
Phase 4: Validation
|-- validation-guardian (Sonnet, 30s)
        |
        v
[Final Schedule]
```

---

## Expected Total Performance Improvement

| Aspect | Improvement | Agent Responsible |
|--------|-------------|-------------------|
| Timing optimization | +10% engagement | timezone-optimizer |
| Content variety & performance | +12% retention | content-strategy-optimizer |
| Volume optimization | Prevents saturation | volume-calibrator |
| Pricing optimization | +15-20% revenue | revenue-optimizer |
| Follow-up recovery | +25% conversions | multi-touch-sequencer |
| Business rule compliance | 100% validation | validation-guardian |
| Market-aligned strategy | Current benchmarks | onlyfans-business-analyst |
| **Total Expected Lift** | **+50-75% revenue** | All agents combined |

---

## Model Selection Rationale

| Agent | Model | Justification |
|-------|-------|---------------|
| timezone-optimizer | Haiku | Simple pattern matching from historical data |
| content-strategy-optimizer | Sonnet | Pattern recognition + sequencing logic |
| volume-calibrator | Sonnet | Statistical analysis + rule application |
| revenue-optimizer | Sonnet | Mathematical projections + pricing curves |
| multi-touch-sequencer | **Opus** | Creative writing + psychological sophistication |
| validation-guardian | Sonnet | Rule checking with contextual fixes |
| onlyfans-business-analyst | **Opus** | Web research synthesis + strategic reasoning |

**Cost Optimization:** Only 2 Opus agents for tasks requiring deep reasoning.

---

## Caching Strategy

| Agent | Cache Duration | Invalidation Trigger |
|-------|----------------|---------------------|
| timezone-optimizer | 30 days | N/A (stable patterns) |
| content-strategy-optimizer | 7 days | New content added to vault |
| volume-calibrator | 3 days | Fan count crosses bracket, PR drops >15% |
| revenue-optimizer | 7 days | Pricing change, tier change |
| multi-touch-sequencer | 1 day | Schedule-specific |
| validation-guardian | Never | Must validate each schedule |
| onlyfans-business-analyst | 14 days | Monthly refresh, tier change |

---

## Deprecated Agents

The following agents have been consolidated and moved to `~/.claude/agents/eros-scheduling/deprecated/`:

| Deprecated Agent | Merged Into |
|------------------|-------------|
| content-performance-analyzer | content-strategy-optimizer |
| content-rotation-architect | content-strategy-optimizer |
| ppv-volume-optimizer | volume-calibrator |
| page-type-optimizer | volume-calibrator |
| pricing-strategist | revenue-optimizer |
| revenue-forecaster | revenue-optimizer |

---

## Usage Example

```bash
# Generate schedule with all agents enabled
python scripts/generate_schedule.py --creator missalexa --week 2025-W50 \
  --mode full \
  --use-agents

# Or with specific features
python scripts/generate_schedule.py --creator missalexa --week 2025-W50 \
  --mode full \
  --enable-quality-scoring \
  --enable-enhancement \
  --enable-context-followups \
  --use-agents
```

---

## Technical Implementation

- **Agent Location**: `~/.claude/agents/eros-scheduling/`
- **Deprecated Agents**: `~/.claude/agents/eros-scheduling/deprecated/`
- **Cache Location**: `~/.eros/agent_cache/`
- **Fallback Behavior**: All agents have predefined fallback values if agent file doesn't exist

---

*Architecture Version 2.0 - Consolidated December 2025*
