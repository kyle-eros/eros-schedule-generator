---
name: eros-schedule-generator
version: 2.0.0
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

When a user asks to generate a schedule, execute this workflow:

### Standard Schedule (Quick Mode)

```bash
# Generate schedule using pattern matching (fast)
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www
```

### Enhanced Schedule (Full Semantic Analysis)

```bash
# Step 1: Prepare context for semantic analysis
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --mode full
```

After running Step 1, I (Claude) will:
1. Read the output context containing creator profile and captions
2. Apply semantic reasoning to analyze captions needing tone/persona matching
3. Generate an optimized schedule with enhanced persona boosts
4. Output the complete enhanced schedule

## Native Claude LLM Integration

This skill leverages Claude Code's built-in intelligence rather than external API calls.

### How It Works

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

### When to Use Each Mode

| Scenario | Mode | Command |
|----------|------|---------|
| Quick check / draft schedule | Quick | `python scripts/generate_schedule.py --creator NAME --week YYYY-Www` |
| Important creator / launch | Full | `python scripts/prepare_llm_context.py --creator NAME --week YYYY-Www --mode full` |
| User requests "optimized" | Full | Use prepare_llm_context.py |
| High-value creator ($5K+/mo) | Full | Always use semantic analysis |
| Many low-confidence captions | Full | Pattern matching struggling |

## Hybrid Agent Orchestration (v2.0)

When using `--mode hybrid`, the pipeline outputs structured agent requests that Claude can process via Task tool.

### Agent Request Detection

Look for these markers in Python output:
```
<<<AGENT_REQUEST>>>
{
  "type": "AGENT_REQUEST",
  "request_id": "req_timezone-optimizer_abc123",
  "agent_name": "timezone-optimizer",
  "agent_model": "haiku",
  "context": {...}
}
<<<END_AGENT_REQUEST>>>
```

### Orchestration Workflow

1. **Run initial Python**:
   ```bash
   python scripts/generate_schedule.py --creator NAME --week YYYY-Www --mode hybrid
   ```

2. **Detect agent requests** in stderr output

3. **Invoke agents via Task tool**:
   - Read agent file from `~/.claude/agents/eros-scheduling/{agent_name}.md`
   - Include context from the request
   - Use subagent_type matching the agent name

4. **Write results** to `/tmp/eros_pipeline/{session_id}_agent_results.json`:
   ```json
   {
     "responses": [
       {"request_id": "req_...", "agent_name": "...", "success": true, "result": {...}}
     ]
   }
   ```

5. **Resume Python**:
   ```bash
   python scripts/generate_schedule.py --resume --session-id {id}
   ```

### Available Agents (v2.0)

| Agent | Model | Purpose |
|-------|-------|---------|
| timezone-optimizer | Haiku | Calculate optimal send times |
| volume-calibrator | Sonnet | Page-type volume constraints |
| content-strategy-optimizer | Sonnet | Content rotation strategy |
| revenue-optimizer | Sonnet | Pricing + revenue projection |
| multi-touch-sequencer | Opus | Follow-up sequences |
| validation-guardian | Sonnet | Business rule validation |
| onlyfans-business-analyst | Opus | Market research + strategy |

## Semantic Analysis Guidelines

When I process the context from prepare_llm_context.py, I apply these guidelines:

### Tone Detection (Beyond Keywords)

| Tone | Surface Signals | Deeper Signals | Common Misreads |
|------|-----------------|----------------|-----------------|
| playful | "hehe", teasing | Building anticipation, flirty energy | Can seem bratty |
| aggressive | "now", demands | Urgency, dominance assertion | Can seem direct |
| sweet | "miss you", affection | Genuine warmth, vulnerability | Can seem seductive |
| dominant | "I decide", control | Power dynamics, authority | Can seem aggressive |
| bratty | "whatever", sarcasm | Playful demands, fake annoyance | Can seem dismissive |
| seductive | "craving", allure | Mystery, anticipation building | Can seem sweet |
| direct | "offer", "unlock" | Transactional, clear CTA | Usually accurate |

### Sarcasm Detection

Key indicators of sarcasm (tone inversion):
- eye-roll emoji + positive words = actually bratty/playful, not sincere
- "I guess" + generous offer = bratty teasing
- "Fine..." + gift = playfully reluctant
- Exaggerated compliance = bratty

### Persona Boost Guidelines

| Match Quality | Boost Range | Criteria |
|--------------|-------------|----------|
| Perfect | 1.35-1.40 | Tone + style + emoji all align with persona |
| Excellent | 1.25-1.35 | Clear tone match, compatible style |
| Good | 1.15-1.25 | Tone matches, minor style variance |
| Acceptable | 1.00-1.15 | No major conflicts, neutral fit |
| Poor | 0.90-1.00 | Noticeable mismatch |
| Bad | 0.80-0.90 | Significant persona conflict |

### Anti-AI Humanization Checks

When evaluating captions, I also check for authentic human voice:

**Red Flags (Lower the boost):**
- Overly formal language ("I would like to offer you...")
- Perfect grammar with no personality quirks
- Generic phrases that could apply to anyone
- Repetitive sentence structures
- Missing contractions ("do not" instead of "don't")

**Authenticity Markers (Higher boost):**
- Personality-specific catchphrases
- Natural emoji usage matching creator's style
- Casual contractions and informal grammar
- Conversational tone like a real DM
- Imperfect punctuation matching texting style

## Complete Workflow Example

### User Request
"Generate an optimized schedule for missalexa for next week"

### Step 1: Prepare Context
```bash
python scripts/prepare_llm_context.py --creator missalexa --week 2025-W50 --mode full
```

### Step 2: Claude Analyzes (Automatic)
I read the output and:
1. Review creator's persona profile (primary tone, emoji usage, slang level)
2. Analyze each caption needing semantic analysis
3. Detect true tone beyond keyword patterns
4. Assign optimized persona boosts

### Step 3: Generate Enhanced Schedule
I produce output like:

```markdown
# Enhanced Schedule: Miss Alexa
## Week: 2025-12-09 to 2025-12-15

### Monday 2025-12-09

| Time | Type | Caption ID | Content | Price | Boost | Analysis |
|------|------|------------|---------|-------|-------|----------|
| 10:00 | PPV | 15234 | solo | $14.99 | 1.38x | Perfect bratty tone with sarcasm |
| 14:15 | Bump | - | - | - | - | Follow-up for 10:00 PPV |
| 14:30 | PPV | 18976 | bundle | $24.99 | 1.30x | Playful teasing matches persona |
| 15:00 | Bump | - | - | - | - | Follow-up for 14:30 PPV |
| 19:00 | PPV | 12445 | winner | $19.99 | 1.25x | Sweet undertone, good variety |

### Tuesday 2025-12-10
...

### Weekly Summary
- Total PPVs: 21
- Total Bumps: 21
- Avg Persona Boost: 1.28x
- Captions Enhanced: 18
- Projected Revenue: $XXX (based on historical conversion)

### Validation
- [x] PPV Spacing >= 4 hours
- [x] No duplicate captions
- [x] All freshness >= 30
- [x] Content type rotation
- [x] Follow-ups 15-45 min after PPV
```

## Enhanced 12-Step Pipeline (v2.0)

The pipeline now supports two modes: **Quick** (pattern-only) and **Full** (with LLM-assisted quality scoring and enhancement).

### Pipeline Steps

| Phase | Step | Name | Quick Mode | Full Mode |
|-------|------|------|------------|-----------|
| **Data Gathering** | 1 | ANALYZE | ✅ Load creator profile | ✅ Load creator profile |
| | 2 | MATCH CONTENT | ✅ Filter by vault + freshness | ✅ Filter by vault + freshness |
| | 3 | PREPARE POOL | ✅ Top captions | ✅ Top 60 for evaluation |
| **Quality Assessment** | 4 | QUALITY SCORING | ❌ Skip | ✅ LLM evaluates caption effectiveness |
| | 5 | MATCH PERSONA | ✅ Pattern-based boost | ✅ Persona boost + quality weights |
| **Schedule Building** | 6 | BUILD STRUCTURE | ✅ Create weekly time slots | ✅ Create weekly time slots |
| | 7 | ASSIGN CAPTIONS | ✅ Vose Alias weighted selection | ✅ Quality-weighted selection |
| | 8 | ENHANCE CAPTIONS | ❌ Skip | ✅ Minor LLM tweaks for authenticity |
| **Follow-ups & Validation** | 9 | GENERATE FOLLOW-UPS | ✅ Generic bumps | ✅ Context-aware bumps |
| | 10 | APPLY DRIP WINDOWS | ✅ If enabled | ✅ If enabled |
| | 11 | APPLY PAGE TYPE RULES | ✅ If enabled | ✅ If enabled |
| | 12 | VALIDATE | ✅ Check all rules | ✅ Check all rules |

### Quality Scoring (Step 4)

LLM evaluates each caption on 4 factors:

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| Authenticity | 35% | Sounds human, not AI-generated (HIGHEST PRIORITY) |
| Hook Strength | 25% | First line grabs attention, creates FOMO |
| CTA Effectiveness | 20% | Clear call-to-action, easy to understand |
| Conversion Potential | 20% | Uses urgency, scarcity, emotional appeal |

Score classifications:
- **Excellent** (0.75+): Full weight, premium slots
- **Good** (0.50-0.74): Normal selection
- **Acceptable** (0.30-0.49): Reduced weight (0.85x)
- **Poor** (<0.30): FILTERED OUT

### Caption Enhancement (Step 8)

Minor tweaks to improve authenticity without changing content:

| Category | Example Before | Example After |
|----------|----------------|---------------|
| Contractions | "do not miss this" | "don't miss this" |
| Emoji Match | "Check this out" (0 emoji) | "Check this out 🔥" (if heavy user) |
| Casual Punctuation | "Hey. Are you ready." | "Hey... are you ready" |
| Pet Name Rotation | "babe" (repeated) | "baby", "hun", "love" |

**Safety Rules:**
- Maximum 15% change in length
- 85%+ of original words preserved
- Automatic rollback if changes exceed thresholds
- Never modify prices, CTAs, or core message

### Context-Aware Follow-ups (Step 9)

Replaces generic bumps with personalized messages based on:
- Original PPV content type
- Creator's tone and emoji style
- Time of day and day of week
- PPV price (high-value gets faster follow-up)

Example:
```
# OLD (generic)
"Have you seen this yet?"

# NEW (context-aware)
"did you see this one babe? 👀 it's one of my favorites..."
```

## Scripts Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `generate_schedule.py` | Main pipeline (quick/full modes) | All schedule generation |
| `prepare_llm_context.py` | Full context for semantic analysis | Production schedules |
| `quality_scoring.py` | LLM-based caption quality assessment | Full mode quality scoring |
| `caption_enhancer.py` | Minor caption tweaks for authenticity | Full mode enhancement |
| `followup_generator.py` | Context-aware follow-up messages | Full mode follow-ups |
| `select_captions.py` | Caption selection with quality weights | Testing caption selection |
| `apply_llm_insights.py` | Apply external analysis results | Feedback loop |
| `analyze_creator.py` | Creator performance brief | Understanding metrics |
| `match_persona.py` | Test persona matching | Debugging boost issues |
| `validate_schedule.py` | Check business rules | Post-generation validation |
| `calculate_freshness.py` | Update freshness scores | Database maintenance |

### CLI Mode Flags

```bash
# Quick mode (pattern-only, <30 seconds)
python generate_schedule.py --creator NAME --week YYYY-Www --mode quick

# Full mode (with LLM, <60 seconds)
python generate_schedule.py --creator NAME --week YYYY-Www --mode full

# Full mode with specific features
python generate_schedule.py --creator NAME --week YYYY-Www \
  --mode full \
  --enable-quality-scoring \
  --enable-enhancement \
  --enable-context-followups
```

## Critical Business Rules

### PPV Spacing
- **Minimum**: 3 hours (ERROR if violated)
- **Recommended**: 4 hours (WARNING if below)
- Spacing enforced via `select_spaced_hours_strict()` in generate_schedule.py

### Freshness Scoring
```
freshness = 100 * e^(-days * ln(2) / 14)

# Examples:
# - 0 days: 100% fresh
# - 7 days: ~70.7% fresh
# - 14 days: 50% fresh (half-life)
# - 28 days: 25% fresh
```
- Half-life: 14 days
- Minimum for scheduling: 30
- Heavy use penalty: -10 per use above 5
- Winner bonus: +15 for performance >= 80
- New caption boost: +20 if never used

### Weight Calculation

**Quick Mode (Pattern-Only):**
```
weight = (performance_score * 0.6 + freshness_score * 0.4) * persona_boost
```

**Full Mode (With Quality Scoring):**
```
weight = (performance_score * 0.4 + freshness_score * 0.2 + quality_score * 0.4) * persona_boost * quality_modifier
```

Quality modifiers:
- Excellent (score >= 0.75): 1.0x
- Good (score >= 0.50): 1.0x
- Acceptable (score >= 0.30): 0.85x
- Poor (score < 0.30): FILTERED OUT

### Persona Matching Boosts
| Match Type | Boost |
|------------|-------|
| Primary tone match | 1.20x |
| Secondary tone match | 1.10x |
| Emoji frequency match | 1.05x |
| Slang level match | 1.05x |
| Sentiment alignment | 1.05x |
| **Maximum combined** | **1.40x** |

### Follow-up Rules
- Only for PPVs (not bumps or drips)
- Delay: 15-45 minutes after PPV (randomized)
- Maximum 1 follow-up per PPV

### Content Rotation
- NEVER same content type consecutively
- Rotation order: solo > bundle > winner > sextape > bg > gg > toy_play > custom

## Volume Level Assignment

**Performance-Based Tier System (v2.0)**

Volume is now determined by performance metrics, not just fan count:

| Tier | PPV/Day | Weekly | Criteria |
|------|---------|--------|----------|
| Base | 2 | 14 | Default minimum floor (all creators) |
| Growth | 3 | 21 | Conv >0.10% OR $/PPV >$40 |
| Scale | 4 | 28 | Conv >0.25% AND $/PPV >$50 |
| High | 5 | 35 | Conv >0.35% AND $/PPV >$65 |
| Ultra | 6 | 42 | Conv >0.40% AND $/PPV >$75 AND >$75K rev |

**Key Changes from v1.0:**
- Minimum 2 PPV/day for ALL creators (was 2-3 for small accounts)
- Maximum 6 PPV/day for proven performers (was 5)
- Performance-based progression replaces fan-count-only tiers
- New tier names: Base, Growth, Scale, High, Ultra

## Database Connection

All scripts connect to SQLite at:
- Primary: `~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db`
- Fallback: `~/.eros/eros.db`

## Output Formats

### Schedule Item Structure
```python
@dataclass
class ScheduleItem:
    item_id: int
    creator_id: str
    scheduled_date: str      # YYYY-MM-DD
    scheduled_time: str      # HH:MM
    item_type: str           # ppv, bump, wall_post
    channel: str             # mass_message, wall_post
    caption_id: int
    caption_text: str
    suggested_price: float
    content_type_id: int
    freshness_score: float
    performance_score: float
    is_follow_up: bool = False
    parent_item_id: int | None = None
```

## Validation Checklist

Before returning a schedule, verify:

- [ ] PPV spacing >= 3 hours (hard minimum)
- [ ] All captions have freshness >= 30
- [ ] Content types match vault availability
- [ ] Follow-ups are 15-45 min after parent PPV
- [ ] No PPVs within drip windows (if enabled)
- [ ] Daily PPV count matches volume level
- [ ] No duplicate captions in same week

## Quality Targets

### With Semantic Analysis (Full Mode)

| Metric | Target | Expected |
|--------|--------|----------|
| Captions with boost > 1.0 | 75%+ | 85-95% |
| Perfect persona matches (1.35+) | 25%+ | 30-40% |
| Avg boost for schedule | 1.20+ | 1.25-1.35 |
| False tone detections | <15% | <10% |

### Pattern-Only (Quick Mode)

| Metric | Target | Expected |
|--------|--------|----------|
| Captions with boost > 1.0 | 70%+ | 85-90% |
| Perfect persona matches | 15%+ | 20-25% |
| Avg boost for schedule | 1.10+ | 1.15-1.20 |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `CreatorNotFoundError` | Invalid creator_id | Check creators table |
| `CaptionExhaustionError` | All captions < freshness 30 | Wait for freshness recovery |
| `VaultEmptyError` | No content in vault | Update vault_matrix |
| `ValidationError` | Business rule violation | Check validation issues |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DATABASE_PATH` | ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db | Database location |
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

## References

For detailed documentation, see:
- `references/architecture.md` - Full pipeline architecture
- `references/scheduling_rules.md` - All business rules and thresholds
- `references/database_performance.md` - Query performance analysis
- `references/extraction_map.md` - Code extraction mapping
- `CLAUDE_LLM_INTEGRATION_PLAN.md` - Original integration design

## Performance Targets

- Schedule generation: < 2 seconds (quick mode)
- Context preparation: < 3 seconds (full mode)
- Schedule generation with agents: < 45 seconds (full mode + agents)
- Query execution: < 100ms each
- Memory usage: < 100MB

## Sub-Agent Integration (v2.0 Consolidated Architecture)

The schedule generator delegates to **7 specialized sub-agents** for enhanced optimization.
Enable with `--use-agents` flag.

### Available Agents

| Agent | Model | Phase | Purpose |
|-------|-------|-------|---------|
| `timezone-optimizer` | Haiku | 1 | Calculate optimal send times from historical data |
| `content-strategy-optimizer` | Sonnet | 2 | Content analysis + persona-matched rotation patterns |
| `volume-calibrator` | Sonnet | 2 | Saturation detection + page-type volume constraints |
| `revenue-optimizer` | Sonnet | 2 | Dynamic pricing + revenue projections |
| `multi-touch-sequencer` | Opus | 3 | 3-touch follow-up sequences with psychology |
| `validation-guardian` | Sonnet | 4 | 15+ rule validation with auto-fix suggestions |
| `onlyfans-business-analyst` | Opus | 1* | Strategic analysis with web research (*optional) |

### Agent Location

All agents are located at: `~/.claude/agents/eros-scheduling/`

### Usage

```bash
# Quick mode with agents
python generate_schedule.py --creator missalexa --week 2025-W50 --use-agents

# Full mode with all enhancements and agents
python generate_schedule.py --creator missalexa --week 2025-W50 \
  --mode full \
  --enable-quality-scoring \
  --enable-enhancement \
  --enable-context-followups \
  --use-agents
```

### Agent Invocation Flow (4-Phase Pipeline)

When `--use-agents` is enabled:

**Phase 1: Data Collection (Parallel)**
- **timezone-optimizer** (Haiku, 15s) - Peak engagement windows
- **onlyfans-business-analyst** (Opus, 45s) - Market research *when strategic context needed*

**Phase 2: Optimization (Sequential)**
- **content-strategy-optimizer** (Sonnet, 30s) - Content analysis + rotation design
- **volume-calibrator** (Sonnet, 30s) - Volume recommendations with page-type constraints
- **revenue-optimizer** (Sonnet, 30s) - Pricing strategy + revenue projections

**Phase 3: Follow-up Design**
- **multi-touch-sequencer** (Opus, 45s) - 3-touch follow-up sequences

**Phase 4: Validation**
- **validation-guardian** (Sonnet, 30s) - Comprehensive rule validation

### Hybrid Agent Details

**content-strategy-optimizer** merges:
- ~~content-performance-analyzer~~ (content type classification)
- ~~content-rotation-architect~~ (rotation patterns)

**volume-calibrator** merges:
- ~~ppv-volume-optimizer~~ (saturation detection)
- ~~page-type-optimizer~~ (paid/free page rules)

**revenue-optimizer** merges:
- ~~pricing-strategist~~ (dynamic pricing)
- ~~revenue-forecaster~~ (revenue projections)

### Fallback Behavior

If an agent is unavailable:
- A warning is logged to stderr
- Default/fallback values are used from local scripts
- Schedule generation continues with remaining agents
- Final output is flagged with "degraded" status

### Expected Impact

| Metric | Without Agents | With Agents | Improvement |
|--------|----------------|-------------|-------------|
| Pricing accuracy | Static tiers | Dynamic per content | +15-20% revenue |
| Follow-up recovery | Single touch | 3-touch sequence | +25% conversions |
| Timing optimization | Fixed windows | Creator-specific | +10% engagement |
| Content variety | Manual rotation | Persona-aware | +12% retention |
| Volume optimization | Fixed brackets | Saturation-aware | Prevents over-send |
| Validation coverage | 8 rules | 15+ rules | Fewer errors |
| Market alignment | Outdated benchmarks | 2025 research | Current pricing |
