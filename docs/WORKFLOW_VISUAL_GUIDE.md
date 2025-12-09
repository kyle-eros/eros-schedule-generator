# EROS Schedule Generator - Visual Workflow Guide

## The Big Picture

```
+------------------+     +-------------------+     +------------------+
|                  |     |                   |     |                  |
|   YOU (User)     | --> |   Claude Code     | --> |  Final Schedule  |
|   "Generate      |     |   Skill Package   |     |  (Optimized)     |
|   schedule for   |     |                   |     |                  |
|   missalexa"     |     |                   |     |                  |
+------------------+     +-------------------+     +------------------+
```

---

## Full Mode: End-to-End Workflow

```
                              FULL MODE WORKFLOW

    +================================================================+
    |  PHASE 1: CONTEXT PREPARATION (prepare_llm_context.py)         |
    +================================================================+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  1. LOAD CREATOR PROFILE                                      |
    |     - page_name, display_name, page_type                      |
    |     - active_fans count                                       |
    |     - content notes & restrictions                            |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  2. LOAD PERSONA PROFILE                                      |
    |     - primary_tone (playful, bratty, seductive, etc.)         |
    |     - secondary_tone                                          |
    |     - emoji_frequency (none, light, moderate, heavy)          |
    |     - slang_level (none, light, heavy)                        |
    |     - avg_sentiment (0.0 - 1.0)                               |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  3. CALCULATE VOLUME LEVEL (MultiFactorVolumeOptimizer)       |
    |     Factors:                                                  |
    |     - Fan count bracket (base)                                |
    |     - Performance tier (revenue contribution)                 |
    |     - Conversion rate                                         |
    |     - Niche/persona type                                      |
    |     - Subscription price                                      |
    |     - Account age                                             |
    |                                                               |
    |     Output: Low/Mid/High/Ultra + PPV per day (2-5)            |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  4. GET BEST HOURS                                            |
    |     - Query mass_messages for avg earnings by hour            |
    |     - Last 90 days of data                                    |
    |     - Top 8 performing hours                                  |
    |     - Fallback: (10, 14, 18, 20, 21)                          |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  5. LOAD CAPTION POOL                                         |
    |     - Filter: is_active = 1                                   |
    |     - Filter: freshness_score >= 30                           |
    |     - Filter: creator_id match OR is_universal = 1            |
    |     - Order by: performance_score DESC                        |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  6. PATTERN-BASED ANALYSIS (for each caption)                 |
    |     - detect_tone_from_text() - keyword matching              |
    |     - detect_slang_level_from_text()                          |
    |     - calculate_sentiment()                                   |
    |     - calculate_pattern_confidence() (0.0 - 1.0)              |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  7. FLAG CAPTIONS NEEDING SEMANTIC ANALYSIS                   |
    |     Flags if:                                                 |
    |     - No stored tone + confidence < 60%                       |
    |     - Very low confidence < 40%                               |
    |     - Competing tone signals                                  |
    |     - High performer (70+) with low persona match (<1.10x)    |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  8. OUTPUT STRUCTURED MARKDOWN CONTEXT                        |
    |     Saved to: ~/Developer/EROS-SD-MAIN-PROJECT/               |
    |               schedules/context/{creator}/{week}_context.md   |
    +---------------------------------------------------------------+
                                    |
                                    v
    +================================================================+
    |  PHASE 2: CLAUDE'S NATIVE SEMANTIC ANALYSIS                    |
    +================================================================+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  9. CLAUDE READS CONTEXT (as conversation data)               |
    |     Claude now has:                                           |
    |     - Full creator profile & persona                          |
    |     - Captions needing analysis with text                     |
    |     - Pattern scores as baseline                              |
    |     - Instructions for semantic evaluation                    |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  10. SEMANTIC TONE DETECTION                                  |
    |      Claude evaluates beyond keywords:                        |
    |      - Detects sarcasm (eye-roll + positive = bratty)         |
    |      - Understands subtext & context                          |
    |      - Identifies emotional undertones                        |
    |      - Catches nuance patterns miss                           |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  11. PERSONA MATCH SCORING                                    |
    |                                                               |
    |      +------------------------+--------+                      |
    |      | Factor                 | Boost  |                      |
    |      +------------------------+--------+                      |
    |      | Primary tone match     | +0.20  |                      |
    |      | Secondary tone match   | +0.10  |                      |
    |      | Emoji usage match      | +0.05  |                      |
    |      | Slang level match      | +0.05  |                      |
    |      +------------------------+--------+                      |
    |      | Base: 1.0x | Max: 1.40x         |                      |
    |      +------------------------+--------+                      |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  12. CONTENT QUALITY SCORING                                  |
    |                                                               |
    |      +-------------------+--------+                           |
    |      | Element           | Weight |                           |
    |      +-------------------+--------+                           |
    |      | Hook strength     | 30%    |                           |
    |      | Urgency/scarcity  | 20%    |                           |
    |      | Call-to-action    | 30%    |                           |
    |      | Emotional tone    | 20%    |                           |
    |      +-------------------+--------+                           |
    +---------------------------------------------------------------+
                                    |
                                    v
    +================================================================+
    |  PHASE 3: SCHEDULE GENERATION (generate_schedule.py)           |
    +================================================================+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 1: ANALYZE                                              |
    |  Load creator profile and volume settings                     |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 2: MATCH CONTENT                                        |
    |  Filter captions by vault availability (vault_matrix table)   |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 3: MATCH PERSONA                                        |
    |  Score captions by voice profile match (1.0x - 1.4x boost)    |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 4: BUILD STRUCTURE                                      |
    |  Create weekly time slots based on:                           |
    |  - Best performing hours                                      |
    |  - PPV per day (from volume level)                            |
    |  - 4+ hour spacing between PPVs                               |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 5: ASSIGN CAPTIONS (Vose Alias Weighted Selection)      |
    |                                                               |
    |  Weight = Performance x Freshness x Persona Boost             |
    |                                                               |
    |  Vose Alias Algorithm: O(1) weighted random selection         |
    |  - Builds probability table once                              |
    |  - Each selection is constant time                            |
    |  - No caption used twice in same week                         |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 6: GENERATE FOLLOW-UPS                                  |
    |  - Only for PPVs (not bumps/drips)                            |
    |  - 15-45 minute delay (randomized)                            |
    |  - Maximum 1 follow-up per PPV                                |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 7: APPLY DRIP WINDOWS (if enabled)                      |
    |  - 4-8 hour windows with NO buying opportunities              |
    |  - Builds anticipation                                        |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 8: APPLY PAGE TYPE RULES (if enabled)                   |
    |  - Paid page: Standard pricing                                |
    |  - Free page: Adjusted pricing matrix                         |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  STEP 9: VALIDATE                                             |
    |                                                               |
    |  +-----------------------------+------------+                 |
    |  | Rule                        | Threshold  |                 |
    |  +-----------------------------+------------+                 |
    |  | PPV spacing                 | >= 3 hours |                 |
    |  | Freshness                   | >= 30      |                 |
    |  | Content type rotation       | No 3x same |                 |
    |  | Follow-up timing            | 15-45 min  |                 |
    |  | No duplicate captions       | Per week   |                 |
    |  +-----------------------------+------------+                 |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |  OUTPUT: FINAL SCHEDULE                                       |
    |                                                               |
    |  Saved to: ~/Developer/EROS-SD-MAIN-PROJECT/                  |
    |            schedules/{creator}/{week}.md                      |
    |                                                               |
    |  Contains:                                                    |
    |  - 7-day schedule with time slots                             |
    |  - Caption ID, content type, price for each                   |
    |  - Persona boost scores                                       |
    |  - Follow-up messages                                         |
    |  - Weekly summary stats                                       |
    +---------------------------------------------------------------+
```

---

## Data Flow Diagram

```
+------------------+
|    DATABASE      |
| eros_sd_main.db  |
+------------------+
        |
        | creators (36)
        | creator_personas (35)
        | caption_bank (19,590)
        | mass_messages (66,826)
        | vault_matrix (1,188)
        | content_types (33)
        v
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|  prepare_llm_    | --> |  Claude Native   | --> |  generate_       |
|  context.py      |     |  Analysis        |     |  schedule.py     |
|                  |     |                  |     |                  |
| - Load profile   |     | - Semantic tone  |     | - Build slots    |
| - Load persona   |     | - Persona match  |     | - Assign caps    |
| - Load captions  |     | - Quality score  |     | - Add follow-ups |
| - Pattern detect |     | - Boost calc     |     | - Validate       |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        v                        v                        v
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|   {week}_        |     |  Enhanced        |     |   {week}.md      |
|   context.md     |     |  Caption Scores  |     |   (Schedule)     |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
```

---

## Quick Reference: Commands

```
QUICK MODE (pattern-only, faster):
python scripts/generate_schedule.py --creator NAME --week YYYY-Www

FULL MODE (semantic analysis, recommended):
python scripts/prepare_llm_context.py --creator NAME --week YYYY-Www --mode full

WITH AGENTS (sub-agent orchestration):
python scripts/prepare_llm_context.py --creator NAME --week YYYY-Www --use-agents
```

---

## Key Files

```
~/.claude/skills/eros-schedule-generator/
├── SKILL.md                    # Skill definition & triggers
├── scripts/
│   ├── prepare_llm_context.py  # Phase 1: Context preparation
│   ├── generate_schedule.py    # Phase 3: 9-step pipeline
│   ├── match_persona.py        # Persona matching logic
│   ├── volume_optimizer.py     # Multi-factor volume calc
│   ├── weights.py              # Caption weighting
│   ├── utils.py                # Vose Alias selector
│   ├── validate_schedule.py    # Business rule validation
│   ├── followup_generator.py   # Follow-up message creation
│   ├── quality_scoring.py      # Content quality scoring
│   └── caption_enhancer.py     # Caption enhancement
└── docs/
    └── WORKFLOW_VISUAL_GUIDE.md  # This file
```

---

## Volume Levels Quick Reference

```
+--------+-------------+---------+-------------+
| Level  | Fan Count   | PPV/Day | Weekly PPVs |
+--------+-------------+---------+-------------+
| Low    | < 1,000     |    2    |     14      |
| Mid    | 1K - 5K     |    3    |     21      |
| High   | 5K - 15K    |    4    |     28      |
| Ultra  | 15K+        |    5    |     35      |
+--------+-------------+---------+-------------+
```

---

## Persona Boost Ranges

```
+------------------+--------------+
| Match Quality    | Boost Range  |
+------------------+--------------+
| Perfect match    | 1.35 - 1.40x |
| Excellent        | 1.25 - 1.35x |
| Good             | 1.15 - 1.25x |
| Acceptable       | 1.00 - 1.15x |
+------------------+--------------+
```

---

## Timing Rules

```
+---------------------------+------------------+
| Rule                      | Value            |
+---------------------------+------------------+
| PPV Minimum Spacing       | 3 hours (ERROR)  |
| PPV Recommended Spacing   | 4 hours (WARN)   |
| Follow-up Delay           | 15-45 minutes    |
| Drip Window Duration      | 4-8 hours        |
| Freshness Half-Life       | 14 days          |
| Freshness Minimum         | 30               |
+---------------------------+------------------+
```
