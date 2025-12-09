---
name: eros-schedule-generator
description: |
  Generate optimized OnlyFans content schedules for creators. Use PROACTIVELY when asked to:
  - Create a weekly schedule, generate a schedule, build a content plan
  - Optimize PPV timing, schedule mass messages, plan bumps/follow-ups
  - Analyze creator performance, review earnings, check best hours
  - Select captions based on freshness and performance scores
  - Match captions to creator persona (tone, emoji, slang)
  - Calculate volume levels (Low/Mid/High/Ultra) based on fan count
  - Validate schedule against business rules (spacing, freshness, drip windows)
  Triggers: schedule, PPV, content plan, creator analysis, captions, freshness, performance
allowed-tools: Read, Glob, Grep, Bash, Task
---

# EROS Schedule Generator

Generate optimized weekly content schedules for OnlyFans creators using Claude's native intelligence.

## Quick Start

### Standard Schedule (Quick Mode)
```bash
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/{creator}/{week}.md
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www

# Print to console instead of saving
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www --stdout
```

### Enhanced Schedule (Full Semantic Analysis)
```bash
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/context/{creator}/{week}_context.md
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --mode full

# Print to console instead of saving
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --mode full --stdout
```

After running, Claude will:
1. Read the output context containing creator profile and captions
2. Apply semantic reasoning to analyze captions needing tone/persona matching
3. Generate an optimized schedule with enhanced persona boosts

## Native Claude LLM Integration

```
User Request: "Generate schedule for missalexa"
                    |
                    v
+-------------------------------------------+
| 1. prepare_llm_context.py                 |
|    - Loads creator profile & persona      |
|    - Identifies captions needing analysis |
|    - Outputs structured markdown context  |
+-------------------------------------------+
                    |
                    v
+-------------------------------------------+
| 2. Claude's Native Semantic Analysis      |
|    - Reads context as conversation data   |
|    - Applies semantic tone detection      |
|    - Detects sarcasm, subtext, emotion    |
|    - Assigns optimized persona boosts     |
+-------------------------------------------+
                    |
                    v
+-------------------------------------------+
| 3. Enhanced Schedule Generation           |
|    - Selects best-matched captions        |
|    - Applies proper 4-hour PPV spacing    |
|    - Ensures content type rotation        |
|    - Outputs complete weekly schedule     |
+-------------------------------------------+
```

## Mode Selection

| Scenario | Mode | Command |
|----------|------|---------|
| Quick check / draft | Quick | `python scripts/generate_schedule.py --creator NAME --week YYYY-Www` |
| Production / high-value creator | Full | `python scripts/prepare_llm_context.py --creator NAME --week YYYY-Www --mode full` |
| With agent orchestration | Agents | Add `--use-agents` flag |

## Semantic Analysis Guidelines

When processing context, apply these guidelines for tone detection:

| Tone | Surface Signals | Deeper Signals |
|------|-----------------|----------------|
| playful | "hehe", teasing | Building anticipation, flirty energy |
| aggressive | "now", demands | Urgency, dominance assertion |
| sweet | "miss you", affection | Genuine warmth, vulnerability |
| dominant | "I decide", control | Power dynamics, authority |
| bratty | "whatever", sarcasm | Playful demands, fake annoyance |
| seductive | "craving", allure | Mystery, anticipation building |
| direct | "offer", "unlock" | Transactional, clear CTA |

**Sarcasm indicators:** eye-roll emoji + positive words, "I guess" + generous offer, "Fine..." + gift

**Persona Boost Ranges:**
- Perfect match: 1.35-1.40x
- Excellent: 1.25-1.35x
- Good: 1.15-1.25x
- Acceptable: 1.00-1.15x

## Critical Business Rules

### PPV Spacing
- **Minimum**: 3 hours (ERROR if violated)
- **Recommended**: 4 hours (WARNING if below)

### Freshness Scoring
- Half-life: 14 days
- Minimum for scheduling: 30
- Formula: `freshness = 100 * e^(-days * ln(2) / 14)`

### Content Rotation
- NEVER same content type consecutively
- Order: solo > bundle > winner > sextape > bg > gg > toy_play > custom

### Follow-ups
- Only for PPVs (not bumps/drips)
- Delay: 15-45 minutes after PPV
- Maximum 1 follow-up per PPV

## Validation Checklist

Before returning a schedule, verify:
- [ ] PPV spacing >= 3 hours
- [ ] All captions have freshness >= 30
- [ ] Content types match vault availability
- [ ] Follow-ups 15-45 min after parent PPV
- [ ] Daily PPV count matches volume level
- [ ] No duplicate captions in same week

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `CreatorNotFoundError` | Invalid creator_id | Check creators table |
| `CaptionExhaustionError` | All captions < freshness 30 | Wait for freshness recovery |
| `VaultEmptyError` | No content in vault | Update vault_matrix |
| `ValidationError` | Business rule violation | Check validation issues |

## Output Behavior

By default, schedules auto-save to organized directories:

| Script | Default Output Location |
|--------|------------------------|
| `generate_schedule.py` | `~/Developer/EROS-SD-MAIN-PROJECT/schedules/{creator}/{YYYY-Www}.md` |
| `prepare_llm_context.py` | `~/Developer/EROS-SD-MAIN-PROJECT/schedules/context/{creator}/{YYYY-Www}_context.md` |

### CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Auto-save to default location |
| `--stdout` | Print to console (old default behavior) |
| `--output path.md` | Save to specified file path |
| `--output-dir dir/` | Batch mode: save to specified directory |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DATABASE_PATH` | ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db | Database location |
| `EROS_SCHEDULES_PATH` | ~/Developer/EROS-SD-MAIN-PROJECT/schedules | Default output directory for schedules |
| `EROS_MIN_PPV_SPACING_HOURS` | 4 | Minimum PPV spacing |
| `EROS_FRESHNESS_HALF_LIFE_DAYS` | 14.0 | Freshness decay rate |
| `EROS_FRESHNESS_MINIMUM_SCORE` | 30.0 | Minimum for scheduling |

## Key Database Tables

| Table | Records | Purpose |
|-------|---------|---------|
| creators | 36 | Creator profiles |
| caption_bank | 19,590 | Caption library |
| mass_messages | 66,826 | Historical performance |
| creator_personas | 35 | Voice profiles |
| vault_matrix | 1,188 | Content inventory |
| content_types | 33 | Content categories |

## Documentation

Human-readable guides are located at: `~/Developer/EROS-SD-MAIN-PROJECT/docs/`

### Technical References

| Reference | Description |
|-----------|-------------|
| [references/architecture.md](./references/architecture.md) | Full pipeline architecture |
| [references/scheduling_rules.md](./references/scheduling_rules.md) | All business rules |
| [references/database-schema.md](./references/database-schema.md) | Database structure & relationships |
