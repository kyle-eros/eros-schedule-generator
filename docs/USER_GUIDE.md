# EROS Schedule Generator User Guide

> Complete user guide for generating optimized OnlyFans content schedules using the AI-powered multi-agent system.

**Version:** 2.3.0 | **Updated:** 2025-12-18

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Understanding the System](#understanding-the-system)
4. [Generating Schedules](#generating-schedules)
5. [Output Formats](#output-formats)
6. [Customization Options](#customization-options)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)
10. [Support](#support)
11. [Additional Resources](#additional-resources)

---

## Introduction

The EROS Schedule Generator is an intelligent multi-agent system designed to create optimized weekly content schedules for OnlyFans creators. It leverages historical performance data, persona matching, and timing optimization to maximize engagement and revenue.

### Key Features

- **Data-Driven Scheduling**: Analyzes 71,998+ historical mass messages to identify optimal patterns
- **Persona-Matched Captions**: Ensures authentic voice alignment with creator personas
- **Volume Calibration**: Adapts send frequency based on saturation/opportunity signals
- **Content Type Optimization**: Prioritizes TOP/MID performers, avoids underperforming types
- **Freshness Scoring**: Rotates captions to maintain subscriber engagement
- **Multi-Format Export**: Outputs in CSV, JSON, and markdown formats

---

## Quick Start

### Option 1: Using the Skill Command

Simply ask Claude to generate a schedule:

```
Generate a schedule for [creator_name]
```

Or invoke the skill directly:

```
/eros-schedule-generator
```

### Option 2: Specifying Parameters

For more control:

```
Generate a schedule for miss_alexa for the week of December 23, 2025
```

### Option 3: Batch Generation

Generate schedules for multiple creators:

```
Generate schedules for all tier 1 creators
```

---

## Understanding the System

### Multi-Agent Architecture

The system deploys 22 specialized agents across 14 phases:

| Phase | Agent | Role | Model |
|-------|-------|------|-------|
| 1 | **Performance Analyst** | Analyzes trends and saturation signals | Sonnet |
| 2 | **Send Type Allocator** | Distributes send types across daily slots | Sonnet |
| 3 | **Caption Selection Pro** | Selects and ranks captions | Sonnet |
| 4 | **Timing Optimizer** | Determines optimal posting times | Sonnet |
| 5 | **Followup Generator** | Auto-generates PPV follow-ups | Sonnet |
| 6 | **Authenticity Engine** | Anti-AI detection and humanization | Sonnet |
| 7 | **Schedule Assembler** | Constructs final schedule | Sonnet |
| 8 | **Revenue Optimizer** | Price and positioning optimization | Sonnet |
| 9 | **Quality Validator** | Final approval gate | Sonnet |

### Data Sources

The system pulls from:

- **Creators Table**: 37 active creators with profiles and tier classifications
- **Captions Table**: 58,763 captions with performance scores
- **Mass Messages Table**: 71,998 historical sends with engagement metrics
- **Content Types**: Rankings from TOP to AVOID per creator
- **Vault Availability**: Real-time content inventory

### Performance Metrics

Key metrics used for optimization:

- **Performance Score**: 0-100 composite of engagement metrics
- **Freshness Score**: `100 - (days_since_last_use * 2)`
- **Saturation Signal**: High send frequency with declining engagement
- **Opportunity Score**: Underutilized content types with high potential

---

## Generating Schedules

### Single Creator Schedule

```
Generate a weekly schedule for miss_alexa
```

The system will:
1. Retrieve creator profile and performance data
2. Analyze content type rankings and saturation signals
3. Select top-performing captions with freshness scoring
4. Determine optimal posting times based on historical success
5. Auto-generate PPV followups
6. Apply anti-AI humanization to ensure authentic voice
7. Assemble schedule respecting volume limits
8. Optimize pricing and positioning for revenue items
9. Validate quality and completeness

### Batch Generation

Generate for multiple creators:

```
Generate schedules for creators in tier 1
```

Available filters:
- By tier: `tier 1`, `tier 2`, `tier 3`, `tier 4`, `tier 5`
- By page type: `paid`, `free`
- All active: `all active creators`

### Custom Date Range

Specify the target week:

```
Generate schedule for miss_alexa for week of January 6, 2025
```

---

## Output Formats

### Standard Output

Each schedule includes:

```
SCHEDULE: [Creator Name]
Week: [Start Date] - [End Date]
Volume Level: [1-5]

═══════════════════════════════════════════════════════════════════════

MONDAY [Date]
────────────────────────────────────────────────────────────────────────

[Time] | [Type] | [Channel]
Caption: "[Caption text]"
Content Type: [Type] | Price: $[Amount]
[Flyer indicator if required]

...
```

### CSV Export

For spreadsheet integration:

| scheduled_date | scheduled_time | item_type | channel | caption_text | content_type | suggested_price |
|---------------|----------------|-----------|---------|--------------|--------------|-----------------|
| 2025-12-16 | 10:00 | PPV | mass_message | ... | Solo | 15.00 |

### JSON Export

For programmatic access:

```json
{
  "creator_id": "miss_alexa",
  "week_start": "2025-12-16",
  "items": [
    {
      "scheduled_date": "2025-12-16",
      "scheduled_time": "10:00",
      "item_type": "PPV",
      "channel": "mass_message",
      "caption_text": "...",
      "content_type": "Solo",
      "suggested_price": 15.00
    }
  ]
}
```

---

## Customization Options

### Send Type Filtering (NEW in v2.0)

Focus on specific send types:

```
Generate schedule for miss_alexa using only ppv_unlock and bundle types
```

Or filter by category:

```
Generate revenue-focused schedule for miss_alexa
```

Available categories:
- **Revenue**: PPV videos, bundles, games, VIP (7 types)
- **Engagement**: Bumps, link drops, farms, live promos (9 types)
- **Retention**: Renewal messages, PPV follow-ups, winbacks (5 types)

### Include/Exclude Features

Control retention and follow-ups:

```
Generate schedule for miss_alexa without retention types
```

```
Generate schedule for miss_alexa with follow-ups disabled
```

Options:
- `include_retention`: true/false (auto for paid pages)
- `include_followups`: true/false (auto-generate PPV follow-ups)

### Volume Override

Adjust the send frequency:

```
Generate schedule for miss_alexa with volume level 4
```

Volume levels:
- **Level 1**: Conservative (2-3 PPV/day)
- **Level 2**: Moderate (3-4 PPV/day)
- **Level 3**: Standard (4-5 PPV/day)
- **Level 4**: Aggressive (5-6 PPV/day)
- **Level 5**: Maximum (6-7 PPV/day)

### Content Type Focus

Emphasize specific content:

```
Generate schedule focusing on B/G content for miss_alexa
```

### Exclude Content Types

Avoid certain content:

```
Generate schedule for miss_alexa excluding Solo content
```

### Time Slot Preferences

Specify timing preferences:

```
Generate schedule with morning focus for miss_alexa
```

Time windows:
- **Morning**: 8:00 AM - 12:00 PM
- **Afternoon**: 12:00 PM - 5:00 PM
- **Evening**: 5:00 PM - 9:00 PM
- **Late Night**: 9:00 PM - 2:00 AM

---

## Best Practices

### 1. Review Saturation Signals

Before generating, check if the creator shows saturation:

```
What are the performance trends for miss_alexa?
```

High saturation + declining engagement = reduce volume.

### 2. Maintain Caption Freshness

The system automatically applies freshness scoring, but you can request:

```
Generate schedule using only captions not used in 30+ days
```

### 3. Respect Content Availability

The system checks vault availability, but verify inventory for planned content types:

```
What content types are available in miss_alexa's vault?
```

### 4. Monitor Performance Weekly

Track schedule effectiveness:

```
How did last week's schedule perform for miss_alexa?
```

### 5. Adjust Based on Results

If engagement drops:
- Reduce volume level
- Focus on TOP content types
- Increase caption freshness threshold

---

## Troubleshooting

### Common Issues

#### "No captions available for send type X" (NEW in v2.0)

**Cause**: No captions match the required caption types for this send type.

**Solution**:
1. Check send type requirements in the [Send Type Reference](SEND_TYPE_REFERENCE.md)
2. Lower `min_performance` or `min_freshness` thresholds
3. Check caption type mappings:
```
What caption types are needed for ppv_unlock?
```
4. Add new captions with required caption types

**Example**:
```
Send type 'bump_descriptive' requires caption_type 'descriptive_tease' or 'sexting_response'
```

#### "Send type not available for page type" (NEW in v2.0)

**Cause**: Attempting to use a paid-only send type on a free page.

**Solution**:
- Retention types (`renew_on_post`, `renew_on_message`, `expired_winback`) are paid page only
- Use `get_send_types(page_type='free')` to see available types
- Filter schedule to appropriate send types

**Example**:
```
Generate schedule for [free_page] using only 'both' page type send types
```

#### "Volume constraints exceeded" (NEW in v2.0)

**Cause**: Schedule exceeds `max_per_day` limit for a send type.

**Solution**:
1. Check send type max_per_day in [Send Type Reference](SEND_TYPE_REFERENCE.md)
2. Reduce quantity of that send type
3. Distribute across more days
4. Adjust volume configuration

**Example**:
```
Send type 'vip_program' max is 1 per day, attempted 2
```

#### "No captions found for creator"

**Cause**: Creator has no captions meeting the minimum performance threshold (40+).

**Solution**: Lower the threshold or add new captions:
```
Show all captions for [creator] regardless of performance
```

#### "Insufficient content types available"

**Cause**: Creator's vault lacks diversity in content types.

**Solution**: Check vault availability and plan content production:
```
What content types are missing from [creator]'s vault?
```

#### "Schedule generation failed"

**Cause**: Database connectivity issue or missing creator data.

**Solution**: Verify creator exists in database:
```
Show profile for [creator_name]
```

#### "Low quality score on validation"

**Cause**: Generated schedule didn't meet quality thresholds.

**Solution**: Review quality report and adjust parameters. Common fixes:
- Increase caption diversity
- Adjust volume level
- Focus on higher-performing content types

### Error Messages

| Error | Meaning | Resolution |
|-------|---------|------------|
| `Creator not found` | Invalid creator_id | Verify spelling, check `get_active_creators` |
| `No performance data` | New creator | Allow 30+ days of history to accumulate |
| `Timing data insufficient` | Limited send history | Use default timing slots |
| `Send type incompatible` | Page type mismatch | Check send type page_type_restriction |
| `Caption type mismatch` | No compatible captions | Add captions with required caption_type |
| `Max per day exceeded` | Volume constraint violation | Reduce send type quantity |

---

## FAQ

### How far back does the system analyze?

Default is 30 days, configurable up to 90 days for established patterns.

### Can I save a schedule to the database?

Yes, schedules are automatically saved via `save_schedule` with template ID for tracking.

### How does freshness scoring work?

```
Freshness = 100 - (days_since_last_use × 2)
```

A caption used 10 days ago has freshness of 80. Captions below 40 freshness are deprioritized.

### What determines optimal timing?

Historical mass message performance by hour and day of week, weighted by recency. The system identifies time slots with highest average engagement for each creator.

### How is volume calibrated?

Volume level is determined by:
1. Creator's historical send frequency
2. Current saturation signals (high frequency + declining engagement = reduce)
3. Opportunity signals (underutilized high-potential periods = increase)
4. Manual override when specified

### Can I preview without saving?

Yes, specify:
```
Generate schedule preview for miss_alexa (don't save)
```

### How do I update creator personas?

Personas are derived from historical caption analysis. To refresh:
```
Analyze persona for [creator] based on recent captions
```

---

## Support

For issues or feature requests:

1. Check this guide's troubleshooting section
2. Review the [Blueprint Documentation](SCHEDULE_GENERATOR_BLUEPRINT.md)
3. Examine the [Skill Documentation](../.claude/skills/eros-schedule-generator/SKILL.md)

---

## Wave 5 Advanced Features

### Price-Length Optimization

**CRITICAL**: Research shows that caption length directly impacts Revenue Per Send (RPS). Mismatched price-length combinations can result in up to 82% RPS loss.

#### Optimal Price-Length Matrix

| Price Point | Character Range | Expected RPS | Use Case |
|------------|-----------------|--------------|----------|
| $14.99 | 0-249 chars | 469 RPS | Impulse buy - quick, punchy captions |
| $19.69 | 250-449 chars | 716 RPS | OPTIMAL - balanced value perception |
| $24.99 | 450-599 chars | 565 RPS | Premium - detailed narrative required |
| $29.99 | 600-749 chars | 278 RPS | High premium - extensive description |

#### Critical Warnings

- **$19.69 with <250 chars**: 82% RPS loss (CRITICAL)
- **$14.99 with >250 chars**: 35% RPS loss (over-explanation)
- **$24.99 with <450 chars**: 60% RPS loss (insufficient value justification)

**Usage**: The system automatically validates price-length alignment during schedule generation and warns of critical mismatches.

### Confidence-Based Pricing

Adjusts prices based on volume prediction confidence for optimal conversion rates.

#### Confidence Tiers

| Confidence Score | Tier | Price Multiplier | Use Case |
|-----------------|------|------------------|----------|
| 0.80 - 1.00 | High | 1.00 (100%) | Established creator - maintain premium pricing |
| 0.60 - 0.79 | Medium | 0.85 (85%) | Growing creator - slight discount |
| 0.40 - 0.59 | Low | 0.70 (70%) | Newer creator - optimize conversion |
| 0.00 - 0.39 | Very Low | 0.60 (60%) | New creator - maximize reach |

**Example**: A creator with confidence score of 0.65 selling a $29.99 item would receive an adjusted price of $24.99 ($29.99 × 0.85, rounded to nearest standard price point).

**Usage**: Automatically applied during schedule generation based on the creator's historical data volume and prediction confidence.

### Daily Flavor Rotation

Creates authentic schedule variation by applying different thematic emphases each day of the week.

#### Weekly Flavor Calendar

| Day | Flavor | Emphasis | Boost Multiplier | Boosted Send Types |
|-----|--------|----------|------------------|-------------------|
| Monday | Playful | Games | 1.5x | game_post, game_wheel, first_to_tip |
| Tuesday | Seductive | Solo | 1.4x | ppv_solo, bump_descriptive |
| Wednesday | Wild | Explicit | 1.4x | ppv_sextape, ppv_b_g |
| Thursday | Throwback | Bundles | 1.5x | ppv_bundle, bundle_wall |
| Friday | Freaky | Fetish | 1.3x | ppv_special, niche_content |
| Saturday | Sext | Drip | 1.5x | bump_drip, drip_set |
| Sunday | Self-Care | GFE | 1.4x | gfe_message, engagement_post |

**How It Works**: The system automatically boosts matching send types on their designated days while maintaining overall daily volume targets through normalization.

**Benefits**:
- Prevents schedule monotony
- Creates predictable subscriber expectations
- Maintains authentic variety across the week

### Campaign Label System

Organizes feed content with standardized labels for campaign management.

#### Label Categories

| Label | Send Types | Purpose |
|-------|-----------|---------|
| GAMES | game_post, spin_the_wheel, prize_wheel | Game-based engagement |
| BUNDLES | bundle, bundle_wall, ppv_bundle | Content bundle offerings |
| FIRST TO TIP | first_to_tip | Tip-based incentive sends |
| PPV | ppv_unlock, ppv_wall, ppv_solo, ppv_sextape | Pay-per-view content |
| RENEW ON | renew_on | Renewal reminder sends |
| RETENTION | expired_winback | Subscriber retention |
| VIP | vip_program, snapchat_bundle | Premium program sends |

**Usage**: Labels are automatically assigned during schedule generation to all eligible items for feed organization.

### Chatter Content Sync

Generates synchronized content manifests for chatter team coordination.

**Features**:
- Filters schedule items relevant to DM operations
- Groups items by date for easier coordination
- Includes special handling notes for different send types
- Provides coordination instructions

**Chatter-Relevant Send Types**:
- dm_farm
- ppv_unlock
- expired_winback
- vip_program
- first_to_tip

**Special Notes Generated**:
- First-to-tip: "Monitor for first tipper - award $XX content"
- VIP program: "VIP campaign - premium engagement required"
- High spenders: "High-value audience - personalized responses recommended"
- Expired winback: "Expired sub winback - be extra engaging"

### Daily Statistics Automation

Automated performance analysis across multiple timeframes with actionable recommendations.

#### Analysis Timeframes

- **Short-term (30 days)**: Current performance trends
- **Medium-term (180 days)**: Seasonal patterns
- **Long-term (365 days)**: Year-over-year comparison

#### Pattern Detection

The system automatically identifies:
- Top-performing content types
- Optimal caption length patterns (250-449 char sweet spot)
- Best posting hours and days
- Underperforming content types
- Frequency gaps (high performers being underutilized)

#### Recommendation Categories

| Category | Priority Levels | Example Actions |
|----------|----------------|-----------------|
| Content | HIGH, MEDIUM | "Prioritize B/G and Solo content types" |
| Caption | HIGH, MEDIUM | "Increase caption length to 250-449 range" |
| Timing | MEDIUM | "Focus posting at 10:00, 14:00, 20:00" |
| Volume | HIGH, MEDIUM | "Reduce volume of Selfie content" |

**Usage**: Run daily statistics analysis before generating schedules to inform content strategy decisions.

### Quality Validators

#### Drip Outfit Consistency

Validates that all drip content from the same photoshoot uses matching outfits.

**Validation Levels**:
- ERROR: Outfit mismatch within shoot (blocks schedule)
- WARNING: Missing shoot_id or outfit metadata (allows with warning)

**Benefits**: Prevents jarring outfit changes within coordinated drip campaigns, maintains visual consistency.

#### Bundle Value Framing

Validates that bundle captions include proper value anchoring patterns.

**Required Elements**:
- Value anchor: "$X worth", "$X value", "$X of content"
- Price mention: "only $X", "just $X", "for $X"

**Example Valid Caption**: "Get $500 worth of my hottest content for only $14.99!"

**Value Ratio**: System calculates and reports value ratio (e.g., 33x for $500 worth at $15 price).

---

## Additional Resources

- [Send Type Reference Guide](SEND_TYPE_REFERENCE.md) - Complete guide to all 21 send types
- [Schedule Generator Blueprint](SCHEDULE_GENERATOR_BLUEPRINT.md) - System architecture and design
- [Enhanced Send Type Architecture](ENHANCED_SEND_TYPE_ARCHITECTURE.md) - Technical implementation details
- [Glossary](GLOSSARY.md) - Complete glossary of all domain terms

---

*Version 2.3.0 | Last Updated: 2025-12-18*
