---
name: eros-schedule-generator
description: |
  Generates optimized OnlyFans content schedules for creators. Use PROACTIVELY when:
  - Creating weekly schedules, generating schedules, building content plans
  - Optimizing PPV timing, scheduling mass messages, planning bumps/follow-ups
  - Analyzing creator performance, reviewing earnings, checking best hours
  - Selecting captions based on freshness, performance, and persona match
  - Calculating volume levels (Low/Mid/High/Ultra) based on fan metrics
  - Validating schedules against business rules (spacing, freshness, rotation)
  - Performing payday optimization, premium content scheduling, revenue timing
  - Conducting hook diversity analysis, caption authenticity, anti-detection patterns
  Triggers: schedule, PPV, content plan, creator analysis, captions, freshness,
  performance, weekly schedule, mass message, bump, follow-up, EROS, payday,
  hook diversity, timing variance, auto-correction, validation
allowed-tools: Read, Glob, Grep, Bash, Task
---

# EROS Schedule Generator

Generates optimized weekly content schedules for OnlyFans creators using Claude's native intelligence.

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

## Structured Output Schema

The schedule generator outputs structured data in this format:

```json
{
  "schedule": [{
    "slot_id": "mon-ppv-1",
    "day": "2025-01-06",
    "time": "10:07",
    "message_type": "ppv",
    "caption_id": 4521,
    "content_type": "solo",
    "price": 18.00,
    "persona_boost": 1.25,
    "freshness_score": 87.3,
    "hook_type": "question",
    "payday_multiplier": 1.0
  }, {
    "slot_id": "mon-ppv-2",
    "day": "2025-01-06",
    "time": "14:12",
    "message_type": "ppv",
    "caption_id": 3892,
    "content_type": "bundle",
    "price": 22.00,
    "persona_boost": 1.35,
    "freshness_score": 92.1,
    "hook_type": "tease",
    "payday_multiplier": 1.0
  }, {
    "slot_id": "mon-bump-1",
    "day": "2025-01-06",
    "time": "14:38",
    "message_type": "bump",
    "caption_id": 3892,
    "content_type": "bundle",
    "price": 22.00,
    "persona_boost": 1.35,
    "freshness_score": 92.1,
    "hook_type": "urgency",
    "payday_multiplier": 1.0
  }],
  "validation": {
    "passed": true,
    "errors": 0,
    "warnings": 1,
    "corrections_applied": 2
  },
  "metadata": {
    "creator_id": "abc123-def456-ghi789",
    "creator_name": "missalexa",
    "week": "2025-W02",
    "mode": "full",
    "generated_at": "2025-01-06T09:32:17Z"
  }
}
```

## Input Requirements

| Parameter | Format | Example | Validation | Required |
|-----------|--------|---------|------------|----------|
| creator | page_name from database | missalexa | Must exist in creators table | Yes (or creator_id) |
| creator_id | UUID string | abc123-def456 | Must exist in creators table | Yes (or creator) |
| week | ISO week format | 2025-W02 | Must match YYYY-Www pattern | Yes |
| mode | string | quick, full | Optional, defaults to "quick" | No |
| use_agents | boolean | true | Enables sub-agent delegation | No |
| min_freshness | float | 30.0 | 0-100, default 30.0 | No |

### Validation Rules

- **creator/creator_id**: At least one must be provided
- **week**: Must be valid ISO 8601 week format (YYYY-Www where ww is 01-53)
- **mode**: "quick" for fast pattern-based, "full" for LLM semantic analysis
- **Output**: Auto-saves to organized directory structure unless --stdout specified

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

## Model Selection Matrix

Different Claude models offer trade-offs for schedule generation tasks:

| Model | Use Case | Speed | Quality | Cost |
|-------|----------|-------|---------|------|
| **Haiku** | Database queries, validation checks | Fastest | Basic | Lowest |
| **Sonnet** | Standard schedule generation (recommended default) | Fast | High | Medium |
| **Opus** | Deep semantic analysis, persona matching, strategic optimization | Slower | Highest | Higher |

### Recommended Model by Task

| Task | Recommended Model | Rationale |
|------|-------------------|-----------|
| Quick mode schedule (`--mode quick`) | Sonnet | Pattern-based, speed matters |
| Full mode schedule (`--mode full`) | Sonnet or Opus | Semantic analysis benefits from reasoning |
| Persona boost calculation | Opus | Best tone/context understanding |
| Caption freshness queries | Haiku | Simple math, fast response |
| Validation rule checking | Haiku | Boolean logic, no reasoning needed |
| Creator performance analysis | Opus | Strategic insights require deep reasoning |
| Batch schedule generation | Sonnet | Balance of speed and quality |
| Debugging pipeline issues | Sonnet | Good code analysis capability |

### Expected Behavior by Model

| Aspect | Haiku | Sonnet | Opus |
|--------|-------|--------|------|
| Persona boost accuracy | 70-80% | 85-90% | 95%+ |
| Sarcasm/subtext detection | Limited | Good | Excellent |
| Hook diversity awareness | Basic | Good | Strategic |
| Payday optimization | Follows rules | Smart timing | Revenue-maximized |
| Error recovery | Rule-based | Contextual | Adaptive |

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

## Version History

### v2.1.0 (2025-12-09)
**Revenue Intelligence & Quality**
- Payday scoring: Optimizes premium content for high-value days (1st/15th)
- Hook diversity: Tracks and rotates opening hooks to prevent pattern detection
- Self-healing validation: Auto-corrects spacing, freshness, timing issues
- Timing variance: Adds +/-7-10 minute variance for authentic feel
- Smart fallbacks: Context-aware fallback values based on performance tier

### v2.0.0 (2025-12-08)
**Pool-Based Selection & Semantic Analysis**
- Pool-based caption selection with PROVEN/GLOBAL_EARNER/DISCOVERY tiers
- Vose Alias O(1) weighted random selection
- Native Claude LLM semantic analysis integration
- Persona matching with max 1.40x boost

### v1.0.0 (2025-09-01)
**Initial Release**
- 9-step schedule generation pipeline
- Basic validation and business rules
- Volume optimization by fan count

### Breaking Changes in v2.1

| Change | Impact | Migration |
|--------|--------|-----------|
| Weight formula | Now includes payday factor (55/15/15/10/5 split) | No action needed |
| Times | Include +/-7 min variance (not exact hours) | Update integrations expecting :00 minutes |
| Hook diversity | Tracked and reported in validation | Validation output includes hook_diversity_score |
| ValidationIssue | New auto_correctable, correction_action, correction_value fields | Backwards compatible |

## Documentation

Human-readable guides are located at: `~/Developer/EROS-SD-MAIN-PROJECT/docs/`

### Technical References

| Reference | Description |
|-----------|-------------|
| [references/architecture.md](./references/architecture.md) | Full pipeline architecture |
| [references/scheduling_rules.md](./references/scheduling_rules.md) | All business rules |
| [references/database-schema.md](./references/database-schema.md) | Database structure & relationships |
