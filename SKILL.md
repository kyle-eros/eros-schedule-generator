---
name: eros-schedule-generator
version: 3.2.0
category: Business Automation
tags:
  - onlyfans
  - scheduling
  - content-management
  - ppv
  - revenue-optimization
  - mass-messages
  - creator-analytics
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
triggers:
  - schedule
  - generate schedule
  - weekly schedule
  - content plan
  - PPV
  - mass message
  - bump
  - follow-up
  - captions
  - freshness
  - persona match
  - volume level
  - payday optimization
  - hook diversity
  - timing variance
  - validation
  - EROS
  - creator analysis
  - creator performance
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Task
---

# EROS Schedule Generator v3.2.0

Generates optimized weekly content schedules for OnlyFans creators using Claude's native intelligence.

## System Overview

The EROS Schedule Generator is a production-grade scheduling system that generates 100% unique, revenue-optimized weekly schedules for 36+ OnlyFans creators managing a $438K+ portfolio.

**Key Features:**
- **20 Schedulable Content Types** across 4 priority tiers (Tier 1-4)
- **31 Validation Rules** (V001-V018 core + V020-V032 extended)
- **Pool-Based Caption Selection** with PROVEN/GLOBAL_EARNER/DISCOVERY stratification
- **Schedule Uniqueness Engine** with timing variance and fingerprinting
- **Self-Healing Validation** with auto-correction for 10 issue types
- **Hook Rotation & Anti-Detection** preventing platform pattern detection
- **SemanticBoostCache** for persisting Claude's semantic analysis between sessions
- **Schema Validation** on startup ensuring database compatibility

## 9-Step Schedule Generation Pipeline

The system follows a comprehensive 9-step process to generate each weekly schedule:

### Step 1: ANALYZE
Load creator profile and performance metrics from database:
- Creator metadata (page_name, creator_id, page_type, fan_count)
- Historical performance data (avg_earnings, purchase_rates, peak_hours)
- Creator persona (primary_tone, emoji_frequency, slang_level)
- Volume level calculation: Low/Mid/High/Ultra based on fan count

### Step 2: MATCH CONTENT
Filter available content by vault availability:
- Query vault_matrix table for creator's available content types
- Load allowed_content_types list (e.g., [1, 3, 5, 8] for solo, bundle, sextape, bg)
- Apply page type restrictions (4 paid-only types vs 16 both-page types)
- Generate placeholder slots for content types without captions

### Step 3: MATCH PERSONA
Score captions by voice profile match (1.0-1.4x boost):
- Load creator_personas table for tone matching
- Calculate persona_boost for each caption:
  - Primary tone match: 1.20x
  - Emoji frequency match: 1.10x (cumulative)
  - Slang level match: 1.10x (cumulative)
  - Maximum combined: 1.40x (capped)
  - No match penalty: 0.95x
- Store persona_boost for weight calculation

### Step 4: BUILD STRUCTURE
Create weekly time slots based on volume level and content types:
- Generate 7 days × (2-6 PPVs/day) = 14-42 PPV slots
- Add follow-up slots 15-45 minutes after each PPV
- Add feed/wall content slots (vip_post, link_drop, normal_post_bump, etc.)
- Add engagement slots (dm_farm, like_farm, text_only_bump)
- Add retention slots (renew_on_mm, expired_subscriber) for days 5-7
- Apply timing variance: 85% of slots get ±7-10 minute randomization

### Step 5: ASSIGN CAPTIONS
Weighted random selection using Vose Alias Method:
- Load stratified pools per content type:
  - **PROVEN**: creator_times_used >= 3 AND creator_avg_earnings > 0
  - **GLOBAL_EARNER**: global_times_used >= 3 AND global_avg_earnings > 0
  - **DISCOVERY**: All others (new imports, under-tested)
- Calculate weight per caption:
  ```
  Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)
  ```
- Select captions using slot tier:
  - **Premium slots** (6PM, 9PM): PROVEN pool only
  - **Standard slots**: PROVEN + GLOBAL_EARNER pools
  - **Discovery slots**: DISCOVERY pool with import prioritization
- Detect hook types and apply SAME_HOOK_PENALTY (0.7x) for consecutive same hooks
- Track used caption_ids to prevent duplicates within week

### Step 6: GENERATE FOLLOW-UPS
Create bump messages 15-45 min after parent PPV:
- Identify PPV items with has_follow_up = True
- Generate ppv_follow_up slot 15-45 min after parent
- Link via parent_item_id for validation tracking
- Use same caption_id as parent PPV (hook type may differ)

### Step 7: APPLY DRIP WINDOWS
Enforce no-PPV zones if enabled (optional):
- Check if creator has drip_windows enabled
- Apply blackout periods (e.g., 12AM-6AM, creator-specific)
- Shift slots outside blackout windows while maintaining spacing
- Preserve relative timing relationships

### Step 8: APPLY PAGE TYPE RULES
Paid vs free page adjustments:
- **Paid Page**: All 20 content types available
- **Free Page**: Filter out 4 paid-only types:
  - vip_post (VIP tier promotion)
  - renew_on_post (renewal reminder on feed)
  - renew_on_mm (renewal reminder via mass message)
  - expired_subscriber (win-back for expired subs)
- Apply content type constraints (min_spacing_hours, max_daily, max_weekly)
- Generate placeholders with theme_guidance for slots without captions

### Step 9: VALIDATE
Check all 31 business rules with auto-correction:
- Run core validation (V001-V018):
  - PPV spacing >= 3 hours (ERROR if < 3, WARNING if < 4)
  - Freshness >= 30.0 (ERROR if < 25, WARNING if < 30)
  - Follow-up timing 15-45 minutes (auto-correct to 25 min)
  - No duplicate captions in same week
  - Content type rotation (no 3x consecutive same)
  - Hook rotation and diversity (V015, V016)
- Run extended validation (V020-V032):
  - Page type compliance (V020)
  - Content type spacing rules (V021, V022, V026, V027)
  - Engagement and retention limits (V023, V024, V025, V028)
  - Bump variant rotation (V029)
  - Content type rotation (V030)
  - Placeholder warnings (V031)
  - Performance score minimum (V032)
- Apply auto-corrections (max 2 passes):
  - Move slots to resolve spacing violations
  - Swap captions for freshness/duplicates
  - Adjust follow-up timing
  - Remove items for page type violations
- Generate schedule fingerprint (SHA-256, 16 chars)
- Calculate uniqueness score (0-100)
- Return validated schedule with metrics

**Output:** Complete 7-day schedule with 14-42 content items, all validation checks passed, uniqueness score 70-100.

## Quick Start

### Standard Schedule (Full Mode - Default)
```bash
# Full semantic analysis (default)
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/{creator}/{week}.md
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www

# Quick mode (pattern-based, faster, no semantic analysis)
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www --quick

# Print to console instead of saving
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www --stdout
```

### Enhanced Context Preparation (Full Semantic Analysis)
```bash
# Prepare full context for Claude's semantic analysis (default)
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/context/{creator}/{week}_context.md
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www

# Quick context (minimal, pattern-based)
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --quick

# Print to console instead of saving
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --stdout

# Specify output directory for semantic cache
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --semantic-output-dir /path/to/dir
```

### Semantic Cache Operations
```bash
# Load semantic boosts from a file
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www \
    --semantic-file ~/.eros/schedules/semantic/{creator}/{week}_semantic.json

# Check if semantic cache exists before generation
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www --check-semantic-cache
```

After running, Claude will:
1. Read the output context containing creator profile and captions
2. Apply semantic reasoning to analyze captions needing tone/persona matching
3. **MUST run `generate_schedule.py`** to complete the schedule generation

---

## !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
## !! STOP - READ THIS BEFORE GENERATING ANY SCHEDULE !!
## !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

```
+============================================================================+
|                                                                            |
|   ██████  ████████  ██████  ██████      ██                                 |
|   ██         ██    ██    ██ ██   ██     ██                                 |
|   ███████    ██    ██    ██ ██████      ██                                 |
|        ██    ██    ██    ██ ██                                             |
|   ██████     ██     ██████  ██          ██                                 |
|                                                                            |
|   YOU MUST RUN generate_schedule.py TO CREATE SCHEDULES                    |
|                                                                            |
|   NEVER manually write schedule tables, slots, or captions.                |
|   The script enforces business rules you cannot replicate manually.        |
|                                                                            |
+============================================================================+
```

### FORBIDDEN ACTIONS (Will produce invalid schedules)

| Action | Why It's Wrong | Consequence |
|--------|---------------|-------------|
| Manually writing schedule tables | Bypasses vault filtering | Schedules content creator doesn't have |
| Manually assigning captions to slots | Bypasses exclusion rules | Uses banned content types/keywords |
| Manually calculating times | Bypasses validation | Spacing violations, timing errors |
| Generating markdown schedules without running script | Bypasses ALL business logic | Completely invalid output |

---

## REQUIRED WORKFLOW DIAGRAM

```
+---------------------------+
| User: "Generate schedule" |
+---------------------------+
            |
            v
+------------------------------------------+
| STEP 1: Run prepare_llm_context.py       |
| $ python scripts/prepare_llm_context.py  |
|   --creator NAME --week YYYY-Www         |
|   --mode full --stdout                   |
+------------------------------------------+
            |
            v
+------------------------------------------+
| STEP 2: Claude Semantic Analysis         |
| - Read the output context                |
| - Analyze tone/persona of captions       |
| - Assign persona boost scores            |
| - DO NOT generate schedule yet!          |
+------------------------------------------+
            |
            v
+=============================================+
|| STEP 3: RUN generate_schedule.py          ||
|| $ python scripts/generate_schedule.py     ||
||   --creator NAME --week YYYY-Www          ||
||                                           ||
|| THIS STEP IS MANDATORY                    ||
|| THIS STEP CANNOT BE SKIPPED               ||
|| THIS STEP CREATES THE ACTUAL SCHEDULE     ||
+=============================================+
            |
            v
+------------------------------------------+
| STEP 4: Review Generated Output          |
| - Check saved file at:                   |
|   ~/Developer/EROS-SD-MAIN-PROJECT/      |
|   schedules/{creator}/{week}.md          |
| - Verify validation passed               |
+------------------------------------------+
```

---

## EXECUTION CHECKLIST (ALL BOXES MUST BE CHECKED)

Before considering the task complete, verify EVERY item:

- [ ] **1. CONTEXT PREPARED** - Ran `prepare_llm_context.py` with `--mode full`
- [ ] **2. SEMANTIC ANALYSIS** - Read and analyzed the context output
- [ ] **3. SCRIPT EXECUTED** - Ran `generate_schedule.py` (NOT manually generated)
- [ ] **4. OUTPUT VERIFIED** - Confirmed file saved to correct location
- [ ] **5. VALIDATION PASSED** - Checked for errors/warnings in output

### CRITICAL: Step 3 Verification

After running `generate_schedule.py`, you MUST see output like:

```
Schedule saved to: ~/Developer/EROS-SD-MAIN-PROJECT/schedules/{creator}/{week}.md
Validation: PASSED (0 errors, X warnings, Y corrections)
```

If you do NOT see this output, the schedule was NOT generated correctly.

---

## WHY generate_schedule.py IS NON-NEGOTIABLE

The script performs operations that CANNOT be replicated manually:

### 1. Database-Driven Caption Selection
```python
# Pool-based selection with performance tiers
PROVEN_EARNERS     # Top performers for this creator
GLOBAL_EARNERS     # Cross-portfolio top performers
DISCOVERY          # Fresh/untested captions
```

### 2. Vault Matrix Filtering
```python
# Only selects content the creator actually HAS
vault_matrix JOIN creators WHERE has_content = 1
```

### 3. Content Restriction Enforcement
```python
# Excludes banned keywords and restricted content types
excluded_keywords: ["specific", "banned", "terms"]
restricted_content_types: ["types", "not", "allowed"]
```

### 4. Weighted Random Selection (Vose Alias Algorithm)
```python
# O(1) selection with performance-based weights
weight = (0.55 * performance) + (0.15 * freshness) +
         (0.15 * persona_boost) + (0.10 * payday) + (0.05 * diversity)
```

### 5. Self-Healing Validation
```python
# Auto-corrects issues before output
if spacing < 4_hours: auto_adjust_time()
if freshness < 30: replace_caption()
if consecutive_types: rotate_content()
```

**Manual schedule generation bypasses ALL of these protections.**

---

## ANTI-PATTERN: What NOT To Do

```markdown
# WRONG - DO NOT DO THIS

"Here's the schedule I generated for missalexa:

| Day | Time | Type | Caption |
|-----|------|------|---------|
| Mon | 10:00 | PPV | Caption text here... |
| Mon | 14:00 | Bump | Another caption... |
..."

# This is INVALID because:
# - No vault filtering applied
# - No content restrictions checked
# - No proper caption selection
# - No validation performed
# - No file saved to tracking location
```

### CORRECT PATTERN

```bash
# CORRECT - Always run the script

$ python scripts/generate_schedule.py --creator missalexa --week 2025-W50

# Output:
# Loading creator profile...
# Selecting captions from pools...
# Applying business rules...
# Running validation...
# Schedule saved to: ~/Developer/EROS-SD-MAIN-PROJECT/schedules/missalexa/2025-W50.md
# Validation: PASSED (0 errors, 2 warnings, 1 correction)
```

---

## QUICK REFERENCE: Command Syntax

### Full Mode - Default (With Semantic Analysis)
```bash
# Default: Full semantic analysis
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www
```

### Quick Mode (Pattern-Based, No Semantic Analysis)
```bash
# Add --quick for faster pattern-based generation
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www --quick
```

### With Context Preparation (Advanced)
```bash
# Step 1: Prepare context (optional, for manual review)
python scripts/prepare_llm_context.py --creator CREATOR_NAME --week YYYY-Www --stdout

# Step 2: [Claude analyzes output - DO NOT generate schedule manually]

# Step 3: Generate schedule with script
python scripts/generate_schedule.py --creator CREATOR_NAME --week YYYY-Www
```

---

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
| mode | string | quick, full | Optional, defaults to "full" | No |
| --quick | flag | --quick | Shorthand for --mode quick | No |
| --semantic-file | path | path/to/file.json | Load pre-computed semantic boosts | No |
| --check-semantic-cache | flag | --check-semantic-cache | Check if semantic cache exists | No |
| use_agents | boolean | true | Enables sub-agent delegation | No |
| min_freshness | float | 30.0 | 0-100, default 30.0 | No |

### Validation Rules

- **creator/creator_id**: At least one must be provided
- **week**: Must be valid ISO 8601 week format (YYYY-Www where ww is 01-53)
- **mode**: "full" for LLM semantic analysis (default), "quick" for fast pattern-based
- **--quick**: Shorthand flag that sets mode to "quick"
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
| Production / default | Full | `python scripts/generate_schedule.py --creator NAME --week YYYY-Www` |
| Quick draft / testing | Quick | `python scripts/generate_schedule.py --creator NAME --week YYYY-Www --quick` |
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

## Validation Rules (31 Total)

The schedule generator validates against 31 business rules organized in two categories:

### Core Validation Rules (V001-V018)
- **V001 PPV_SPACING**: PPVs must be 3+ hours apart (4 recommended)
- **V002 FRESHNESS_MINIMUM**: All captions must have freshness >= 30
- **V003 FOLLOW_UP_TIMING**: Follow-ups must be 15-45 min after parent
- **V004 DUPLICATE_CAPTIONS**: No duplicate captions in same week
- **V005 VAULT_AVAILABILITY**: Content types should be in vault
- **V006 VOLUME_COMPLIANCE**: Daily PPV count should match target
- **V007 PRICE_BOUNDS**: Pricing within acceptable ranges
- **V008 WALL_POST_SPACING**: Wall posts must be 2+ hours apart
- **V009 PREVIEW_PPV_LINKAGE**: Previews must be 1-3h before linked PPV
- **V010 POLL_SPACING**: Polls must be 2+ days apart
- **V011 POLL_DURATION**: Poll duration must be 24/48/72h
- **V012 GAME_WHEEL_VALIDITY**: Only one game wheel per week
- **V013 WALL_POST_VOLUME**: Max 4 wall posts per day
- **V014 POLL_VOLUME**: Max 3 polls per week
- **V015 HOOK_ROTATION**: Warn on consecutive same hook types
- **V016 HOOK_DIVERSITY**: Info if < 4 hook types used in week
- **V017 CONTENT_ROTATION**: Warn on 3+ consecutive same content type
- **V018 EMPTY_SCHEDULE**: Check for empty schedules

### Extended Content Type Rules (V020-V032)

Note: V019 is intentionally skipped for compatibility.

- **V020 PAGE_TYPE_VIOLATION**: Paid-only content on free page (ERROR, auto-correctable: remove_item)
- **V021 VIP_POST_SPACING**: Min 24h between VIP posts (ERROR, auto-correctable: move_slot)
- **V022 LINK_DROP_SPACING**: Min 4h between link drops (WARNING, auto-correctable: move_slot)
- **V023 ENGAGEMENT_DAILY_LIMIT**: Max 2 engagement posts per day (WARNING, auto-correctable: move_to_next_day)
- **V024 ENGAGEMENT_WEEKLY_LIMIT**: Max 10 engagement posts per week (WARNING, auto-correctable: remove_item)
- **V025 RETENTION_TIMING**: Retention content on days 5-7 optimal (INFO)
- **V026 BUNDLE_SPACING**: Min 24h between bundles (ERROR, auto-correctable: move_slot)
- **V027 FLASH_BUNDLE_SPACING**: Min 48h between flash bundles (ERROR, auto-correctable: move_slot)
- **V028 GAME_POST_WEEKLY**: Max 1 game post per week (WARNING, auto-correctable: remove_item)
- **V029 BUMP_VARIANT_ROTATION**: No 3x consecutive same bump type (WARNING, auto-correctable: swap_content_type)
- **V030 CONTENT_TYPE_ROTATION**: No 3x consecutive same type (INFO)
- **V031 PLACEHOLDER_WARNING**: Slot has no caption (INFO)
- **V032 PERFORMANCE_MINIMUM**: Performance score below minimum threshold (WARNING)

### Auto-Correction Capabilities

The validation system includes self-healing capabilities for common issues:

**Auto-Correctable Issues:**
1. PPV spacing violations (<3hr) → Move to next valid slot
2. Duplicate captions → Swap with unused caption of same type
3. Freshness below 30 → Swap with fresher caption
4. Follow-up timing outside 15-45min → Adjust to 25 minutes
5. Page type violations → Remove item or change page type
6. VIP post spacing violations → Move to valid slot
7. Engagement limit exceeded → Move to next day or remove
8. Bundle/Flash bundle spacing → Move to valid slot
9. Game post exceeded → Remove excess items
10. Bump variant rotation violations → Swap content type

**Not Auto-Correctable (require human judgment):**
- Content rotation patterns
- Pricing decisions
- Volume targets
- Retention timing (info only)
- Placeholder content (info only)

## Validation Checklist

Before returning a schedule, verify:
- [ ] PPV spacing >= 3 hours (V001)
- [ ] All captions have freshness >= 30 (V002)
- [ ] Content types match vault availability (V005)
- [ ] Follow-ups 15-45 min after parent PPV (V003)
- [ ] Daily PPV count matches volume level (V006)
- [ ] No duplicate captions in same week (V004)
- [ ] Page type compliance for paid-only content (V020)
- [ ] Content type spacing rules enforced (V021, V022, V026, V027)
- [ ] Engagement and retention limits respected (V023, V024, V028)
- [ ] Hook diversity and rotation (V015, V016)
- [ ] No 3x consecutive same content type (V017, V029, V030)

## Schedule Uniqueness Engine

Every creator receives a 100% unique schedule through a two-tier intelligence system:

### Tier 1 - Data-Driven Uniqueness

**Timing Variance (7-10 minutes):**
- Applied to 85% of slots (VARIANCE_PROBABILITY = 0.85)
- Randomization range: -10 to +10 minutes
- Creates organic, non-robotic posting patterns
- Prevents platform detection of automated scheduling

**Historical Weighting:**
Multi-factor weight calculation based on creator's historical patterns:
- **Performance Weight (60%)**: Base performance score or earnings data
- **Recency Weight (20%)**: Timing bonus from historical peak hours
- **Diversity Weight (20%)**: Content type variety bonuses

**Cross-Week Deduplication:**
- 4-week lookback period (RECENT_WEEKS_LOOKBACK = 4)
- Tracks recently used caption IDs
- Penalties for captions used in last 28 days
- Ensures fresh content rotation

**Schedule Fingerprinting:**
- SHA-256 hash of schedule content + timing
- Truncated to 16 characters for storage
- Duplicate detection across recent weeks
- Automatic re-shuffling if duplicate found (max 5 attempts)

### Tier 2 - LLM Reasoning Intelligence

**Semantic Caption Matching:**
- Claude analyzes caption tone, emotion, and brand voice
- Context-aware persona boost scoring (0.95x - 1.40x)
- Sarcasm and subtext detection for authenticity
- Cultural moment and audience fit analysis

**Dynamic Content Sequencing:**
- Hook type rotation to prevent patterns (7 hook types)
- SAME_HOOK_PENALTY (0.7x) for consecutive same hooks
- Engagement psychology-based ordering
- Follow-up strategy optimization

**Uniqueness Metrics:**
- `fingerprint`: 16-char SHA-256 hash identifying schedule
- `uniqueness_score`: 0-100 score based on freshness and diversity
- `timing_variance_applied`: Count of slots with variance
- `historical_weight_factor`: Average historical weighting applied
- `cross_week_duplicates`: Captions also used in recent weeks
- `content_type_distribution`: Slot count per content type

### Key Configuration Constants

```python
# Timing Variance
TIMING_VARIANCE_MIN = -10        # minutes
TIMING_VARIANCE_MAX = 10         # minutes
VARIANCE_PROBABILITY = 0.85      # 85% of slots

# Historical Weighting
PERFORMANCE_WEIGHT = 0.6         # 60%
RECENCY_WEIGHT = 0.2             # 20%
DIVERSITY_WEIGHT = 0.2           # 20%

# Cross-Week Deduplication
RECENT_WEEKS_LOOKBACK = 4        # 28 days
HISTORICAL_DAYS_LOOKBACK = 90    # 3 months
MIN_SENDS_FOR_PATTERN = 5        # Reliable pattern threshold
```

## Pool-Based Caption Selection

### Stratified Pool Classification

Captions are organized into 3 performance-based pools per content type:

**PROVEN Pool:**
- Criteria: `creator_times_used >= 3 AND creator_avg_earnings > 0`
- Contains: Captions with proven performance for THIS creator
- Usage: Premium slots (prime time 6PM, 9PM)
- Weight: Based on actual creator earnings data

**GLOBAL_EARNER Pool:**
- Criteria: `creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0`
- Contains: Captions that earn globally but untested for this creator
- Usage: Standard PPV slots
- Weight: Based on global earnings (20% discount vs proven)

**DISCOVERY Pool:**
- Criteria: All others (new imports, under-tested, no earnings)
- Contains: Fresh content for testing and diversification
- Usage: Discovery slots for experimentation
- Weight: Based on performance score proxy (50% discount)

### Weight Formula

```
Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)
```

**Earnings Component (60%):**
- PROVEN: Uses creator_avg_earnings
- GLOBAL_EARNER: Uses global_avg_earnings with 20% discount
- DISCOVERY: Uses performance_score as proxy with 50% discount

**Freshness Component (15%):**
- Half-life: 14 days
- Formula: `freshness = 100 * e^(-days * ln(2) / 14)`
- Minimum threshold: 30.0 for scheduling

**Persona Boost Component (15%):**
- Primary tone match: 1.20x
- Emoji frequency match: 1.10x (cumulative)
- Slang level match: 1.10x (cumulative)
- Maximum combined: 1.40x (capped)
- No match penalty: 0.95x

**Discovery Bonus (10%):**
- Recent imports (<30 days): 1.5x boost
- External imports: 1.2x boost
- High global earners: 1.3x boost
- Under-tested content (<3 uses): 1.5x boost

### Slot Type Selection Strategy

| Slot Type | Pools Used | When Applied | Selection Logic |
|-----------|------------|--------------|-----------------|
| **Premium** | PROVEN only | Peak hours (6PM, 9PM) | Highest earners, fallback to PROVEN+GLOBAL if needed |
| **Standard** | PROVEN + GLOBAL_EARNER | Normal PPV slots | Weighted mix, fallback to DISCOVERY if exhausted |
| **Discovery** | DISCOVERY | Exploration slots | Recent imports prioritized, fallback to GLOBAL |

### Hook Type Anti-Detection (Phase 3)

**7 Hook Types Detected:**
1. **curiosity**: Questions, teasers, "guess what"
2. **personal**: "Miss you", personal connection
3. **exclusivity**: "Just for you", VIP language
4. **recency**: "Just finished", time-based urgency
5. **question**: Direct questions to engage
6. **direct**: Clear CTA, transactional
7. **teasing**: Flirty, playful, suggestive

**Rotation Enforcement:**
- `SAME_HOOK_PENALTY = 0.7`: 30% weight reduction for consecutive same hooks
- Validation warning (V015) for 2x consecutive same hook
- Info notice (V016) if < 4 hook types used in full week
- Promotes natural variation and authenticity

### Vose Alias Method Selection

O(1) selection time after O(n) preprocessing:
1. Build probability distribution from weights
2. Create alias table for weighted random selection
3. Select caption in constant time regardless of pool size
4. Ensures proper statistical distribution over many selections

## Configuration Files

The system uses externalized configuration for all business rules and settings.

### Primary Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `business_rules.yaml` | Selection config, volume tiers, spacing rules | `config/business_rules.yaml` |
| `content_type_mapping.yaml` | Content type definitions and constraints | `config/content_type_mapping.yaml` |

### Key Configuration Parameters

**Selection Settings** (`config/business_rules.yaml`):
```yaml
selection:
  exclusion_days: 60        # Hard exclusion window for recently used captions
  pool_limit: 500           # Maximum captions to load in unified pool
  min_performance_score: 20.0
  performance_warning_threshold: 30.0
  allow_low_performance_on_exhaustion: true
```

**Volume Tiers** (from `config/business_rules.yaml`):
| Tier | Fan Range | PPV/Day | Bump/Day |
|------|-----------|---------|----------|
| Low | <1,000 | 2-3 | 2-3 |
| Mid | 1,000-4,999 | 3-4 | 2-3 |
| High | 5,000-14,999 | 4-5 | 3-4 |
| Ultra | 15,000+ | 5-6 | 4-5 |

### Semantic Boost Cache

Claude's semantic analysis results are persisted to enable reuse across sessions:

**Cache Location:**
```
~/.eros/schedules/semantic/{creator_name}/{week}_semantic.json
```

**Environment Variable Override:**
```bash
export EROS_SEMANTIC_CACHE_PATH="/custom/path/to/cache"
```

**Cache Format:**
```json
{
  "creator_name": "grace_bennett",
  "week": "2025-W50",
  "generated_at": "2025-12-10T14:30:00",
  "semantic_results": [
    {
      "caption_id": 12345,
      "detected_tone": "bratty",
      "persona_boost": 1.25,
      "quality_score": 0.80,
      "reasoning": "Strong bratty undertones with playful hook"
    }
  ]
}
```

## Troubleshooting

### Common Errors and Resolutions

| Error | Cause | Resolution |
|-------|-------|------------|
| `CreatorNotFoundError` | Invalid creator_id | Check creators table for valid page_name |
| `CaptionExhaustionError` | All captions below freshness threshold | Wait 7-14 days for recovery, or add new captions |
| `VaultEmptyError` | No content in vault for content type | Update vault_matrix table |
| `ValidationError` | Business rule violation | Check error message, adjust schedule parameters |
| `SchemaValidationError` | Database missing required columns | Run schema migration or update database |

### CaptionExhaustionError

**Symptoms:** Schedule generation fails with "All captions below freshness threshold"

**Causes:**
- All captions have been used within the freshness decay window (14 days default)
- Creator has very limited caption pool
- High-volume scheduling depleted fresh captions

**Solutions:**
1. Wait 7-14 days for freshness scores to recover naturally
2. Add new captions to the caption_bank table
3. Temporarily lower minimum freshness (use `--min-freshness 25`)
4. Check if creator should be on a lower volume tier

### Schema Validation Failures

**Symptoms:** Script fails on startup with "Database schema validation failed"

**Causes:**
- Database was created with older schema version
- Required columns missing (e.g., `secondary_tone`)
- Database file corrupted or inaccessible

**Solutions:**
1. Check missing columns reported in error message
2. Run schema migration: `python scripts/database.py --migrate`
3. Verify database path: `echo $EROS_DATABASE_PATH`
4. Test database access: `sqlite3 "$EROS_DATABASE_PATH" ".tables"`

### Low Persona Boost Coverage

**Symptoms:** Most captions getting 1.0x boost instead of 1.1-1.4x

**Causes:**
- Creator persona not set in `creator_personas` table
- Captions lack tone metadata
- Semantic analysis not run (quick mode)

**Solutions:**
1. Verify persona exists: `SELECT * FROM creator_personas WHERE creator_id = ?`
2. Run full mode instead of quick: remove `--quick` flag
3. Run `prepare_llm_context.py` and save semantic results
4. Load semantic cache: `--semantic-file path/to/cache.json`

### PPV Spacing Violations

**Symptoms:** Validation errors about PPV spacing < 3 hours

**Causes:**
- Too many PPVs scheduled for available time slots
- Volume tier too high for creator's content availability
- Manual slot overrides conflicting with spacing rules

**Solutions:**
1. Reduce volume tier: `--volume Low` or `--volume Mid`
2. Reduce PPV count per day in business_rules.yaml
3. Check auto-correction attempted (should move slots automatically)
4. Review validation output for specific slot conflicts

### Database Connection Issues

```bash
# Verify database path
echo $EROS_DATABASE_PATH

# Test connection
sqlite3 "$EROS_DATABASE_PATH" "SELECT COUNT(*) FROM creators WHERE is_active=1;"

# Check file permissions
ls -la "$EROS_DATABASE_PATH"

# Verify schema
python scripts/database.py --validate-schema
```

### Debug Commands

```bash
# Run with verbose logging
python scripts/generate_schedule.py --creator NAME --week YYYY-Www --verbose

# Check semantic cache existence
python scripts/generate_schedule.py --creator NAME --week YYYY-Www --check-semantic-cache

# List available content types
python scripts/generate_schedule.py --list-content-types --page-type paid

# Validate existing schedule file
python scripts/validate_schedule.py --input schedule.json --verbose
```

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

**Note**: Previous versions saved to `~/.eros/schedules/`. Set `EROS_SCHEDULES_PATH` environment variable to customize the output location.

### CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Auto-save to default location |
| `--stdout` | Print to console (old default behavior) |
| `--output path.md` | Save to specified file path |
| `--output-dir dir/` | Batch mode: save to specified directory |

### Content Type Selection (Phase 5B)

| Flag | Behavior |
|------|----------|
| `--content-types TYPE...` | Specific content types to include (e.g., `ppv bundle vip_post`) |
| `--page-type paid\|free` | Override page type (usually auto-detected) |
| `--volume Low\|Mid\|High\|Ultra` | Override volume level (usually auto-calculated) |
| `--no-placeholders` | Skip slots without available captions |
| `--list-content-types` | List all available content types and exit |

## Unified Entry Point (Phase 5B)

The `generate_full_schedule()` function provides a single-call solution for complete schedule generation with all 20+ content types:

### Python API

```python
from generate_schedule import generate_full_schedule

# Generate with all valid content types for creator's page
result = generate_full_schedule(
    creator_name="missalexa",
    week="2025-W50"
)

# Generate with specific content types only
result = generate_full_schedule(
    creator_name="missalexa",
    week="2025-W50",
    content_types={"ppv", "bundle", "vip_post", "dm_farm"},
    include_placeholders=True
)

# Override page type and volume
result = generate_full_schedule(
    creator_name="missalexa",
    week="2025-W50",
    page_type_override="paid",
    volume_override="High"
)

print(f"Generated {len(result.items)} items")
print(f"Placeholders: {result.metadata.get('placeholders', 0)}")
```

### CLI Usage

```bash
# Full schedule with all content types (default)
python scripts/generate_schedule.py --creator missalexa --week 2025-W50

# Specific content types only
python scripts/generate_schedule.py --creator missalexa --week 2025-W50 \
    --content-types ppv bundle vip_post dm_farm

# List available content types
python scripts/generate_schedule.py --list-content-types --week 2025-W50

# List content types for specific page type
python scripts/generate_schedule.py --list-content-types --page-type paid --week 2025-W50

# Override volume level
python scripts/generate_schedule.py --creator missalexa --week 2025-W50 --volume High
```

### Content Type Registry (20 Types)

The system supports 20 schedulable content types organized in 4 priority tiers:

| Tier | Types | Purpose | Count |
|------|-------|---------|-------|
| Tier 1 | ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle | Direct Revenue | 5 |
| Tier 2 | vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post, game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo | Feed/Wall | 10 |
| Tier 3 | dm_farm, like_farm, text_only_bump | Engagement | 3 |
| Tier 4 | renew_on_mm, expired_subscriber | Retention | 2 |

#### Tier 1 - Direct Revenue (Priority 1)
- **ppv**: Pay-per-view mass message with locked content (3h spacing, 5/day, 35/week)
- **ppv_follow_up**: Bump message 15-45 min after PPV (15min spacing, 5/day, 35/week)
- **bundle**: Multi-piece content bundle at discount (24h spacing, 1/day, 3/week)
- **flash_bundle**: Limited-time bundle with urgency (48h spacing, 1/day, 2/week)
- **snapchat_bundle**: Premium Snapchat access bundle (48h spacing, 1/day, 2/week)

#### Tier 2 - Feed/Wall (Priority 2)
- **vip_post**: Exclusive VIP tier content post - **PAID ONLY** (24h spacing, 1/day, 3/week)
- **first_to_tip**: Campaign with specific tip goal (12h spacing, 1/day, 3/week)
- **link_drop**: Link to external content or promotion (4h spacing, 3/day, 21/week)
- **normal_post_bump**: Regular feed post with engagement focus (2h spacing, 4/day, 28/week)
- **renew_on_post**: Subscription renewal reminder post - **PAID ONLY** (24h spacing, 1/day, 2/week)
- **game_post**: Interactive game or contest post (168h spacing, 1/day, 1/week)
- **flyer_gif_bump**: Visual bump with flyer or GIF (4h spacing, 2/day, 14/week)
- **descriptive_bump**: Detailed content description post (4h spacing, 2/day, 14/week)
- **wall_link_drop**: Link drop directly on feed wall (4h spacing, 2/day, 14/week)
- **live_promo**: Promotion for upcoming live stream (24h spacing, 1/day, 3/week)

#### Tier 3 - Engagement (Priority 3)
- **dm_farm**: Direct message to encourage engagement (12h spacing, 2/day, 10/week)
- **like_farm**: Post designed to maximize likes (12h spacing, 2/day, 10/week)
- **text_only_bump**: Text-only mass message bump (4h spacing, 2/day, 14/week)

#### Tier 4 - Retention (Priority 4)
- **renew_on_mm**: Renewal reminder via mass message - **PAID ONLY** (24h spacing, 1/day, 2/week)
- **expired_subscriber**: Win-back message for expired subscribers - **PAID ONLY** (72h spacing, 1/day, 2/week)

#### Page Type Restrictions
- **Paid Only**: vip_post, renew_on_post, renew_on_mm, expired_subscriber (4 types)
- **Both Pages**: All other 16 content types (ppv, bundle, dm_farm, like_farm, link_drop, etc.)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DATABASE_PATH` | ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db | Database location |
| `EROS_SCHEDULES_PATH` | ~/Developer/EROS-SD-MAIN-PROJECT/schedules | Default output directory for schedules |
| `EROS_MIN_PPV_SPACING_HOURS` | 4 | Minimum PPV spacing |
| `EROS_FRESHNESS_HALF_LIFE_DAYS` | 14.0 | Freshness decay rate |
| `EROS_FRESHNESS_MINIMUM_SCORE` | 30.0 | Minimum for scheduling |

## Database Reference

### Quick Schema Lookup

The skill includes a helper function to get key table schemas:

```python
from database import get_schema_info

schema = get_schema_info()
print(schema["creators"])  # ['creator_id', 'page_name', 'display_name', ...]
```

### Key Database Tables

| Table | Records | Purpose | Key Columns |
|-------|---------|---------|-------------|
| creators | 36 | Creator profiles | creator_id, page_name, display_name, page_type, current_active_fans |
| creator_personas | 35 | Voice profiles | creator_id, primary_tone, secondary_tone, emoji_frequency, slang_level |
| caption_bank | 19,590 | Caption library | caption_id, caption_text, performance_score, freshness_score, tone |
| vault_matrix | 1,188 | Content inventory | creator_id, content_type_id, has_content |
| content_types | 33 | Content categories | content_type_id, type_name, priority_tier |
| mass_messages | 66,826 | Historical performance | creator_id, sending_time, sending_hour, earnings |
| volume_assignments | 36 | Volume levels | creator_id, volume_level, ppv_per_day, bump_per_day |

### Common Query Patterns

**Get creator by name:**
```sql
SELECT * FROM creators
WHERE page_name = 'grace_bennett' OR display_name = 'Grace Bennett';
```

**Get persona for matching:**
```sql
SELECT primary_tone, secondary_tone, emoji_frequency, slang_level
FROM creator_personas
WHERE creator_id = ?;
```

**Get vault content types:**
```sql
SELECT vm.content_type_id, ct.type_name
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ? AND vm.has_content = 1;
```

**Get schedulable captions:**
```sql
SELECT cb.caption_id, cb.caption_text, cb.performance_score, cb.freshness_score
FROM caption_bank cb
WHERE cb.is_active = 1
  AND cb.freshness_score >= 30
  AND (cb.creator_id = ? OR cb.is_universal = 1)
ORDER BY cb.performance_score DESC, cb.freshness_score DESC
LIMIT 500;
```

**Get best performing hours (90-day lookback):**
```sql
SELECT sending_hour, COUNT(*) as count, AVG(earnings) as avg_earnings
FROM mass_messages
WHERE creator_id = ? AND message_type = 'ppv'
  AND sending_time >= datetime('now', '-90 days')
GROUP BY sending_hour
HAVING COUNT(*) >= 3
ORDER BY avg_earnings DESC
LIMIT 10;
```

### Full Schema Documentation

For complete schema documentation including:
- All 36+ tables with full column descriptions
- Constraints, indexes, and triggers
- Data quality notes and warnings
- Views and common queries
- Pipeline-to-table mapping

See: [references/database-schema.md](./references/database-schema.md)

## Version History

### v3.2.0 (2025-12-10)
**Comprehensive Fixes + Semantic Cache + Schema Validation**

**Validation System:**
- FIXED: Now enforces full 31 validation rules (V001-V018 core + V020-V032 extended)
- NEW: V032 PERFORMANCE_MINIMUM rule for low-scoring captions
- Accurate rule documentation reflecting actual implementation

**Configuration:**
- NEW: Externalized selection config to `config/business_rules.yaml`
- NEW: Volume tier thresholds corrected: Low <1K, Mid 1-5K, High 5-15K, Ultra 15K+
- PPV counts: Low=2-3/day, Mid=3-4/day, High=4-5/day, Ultra=5-6/day

**Semantic Analysis:**
- NEW: `SemanticBoostCache` for persisting Claude's analysis between sessions
- NEW: `--semantic-file` CLI option to load pre-computed semantic boosts
- NEW: `--check-semantic-cache` to verify cache existence before generation
- Cache location: `~/.eros/schedules/semantic/{creator}/{week}_semantic.json`

**Schema & Database:**
- NEW: Schema validation on startup via `validate_schema()`
- NEW: `SchemaValidationError` for missing required columns
- NEW: `secondary_tone` field support in creator personas
- 2025 pricing rates applied via content type normalization

**Troubleshooting:**
- NEW: Comprehensive troubleshooting section with common errors
- Documented solutions for CaptionExhaustionError, schema validation failures
- Debug commands for database connectivity and semantic cache

### v3.1.0 (2025-12-09)
**Unified Entry Point & 20 Content Types (Phase 5B)**
- NEW: `generate_full_schedule()` unified entry point for complete schedule generation
- NEW: `list_content_types()` helper to display all available content types
- NEW: `print_schedule_summary()` for formatted schedule output
- NEW CLI flags: `--content-types`, `--page-type`, `--volume`, `--no-placeholders`, `--list-content-types`
- Support for 20 schedulable content types across 4 priority tiers
- Content type filtering based on page type (paid vs free)
- Automatic placeholder generation for slots without captions

### v3.0.0 (2025-12-09)
**Full Mode Default & Enhanced Workflow**
- BREAKING: Default mode changed from "quick" to "full"
- Added `--quick` flag for backwards compatibility (shorthand for `--mode quick`)
- Full semantic analysis now runs by default for production-quality schedules
- Quick mode remains available for drafts and testing via `--quick` flag

### v2.1.0 (2025-12-09)
**Pool-Based Earnings + Schedule Uniqueness + Extended Validation**

**Caption Selection System:**
- Pool-based selection with 3 tiers: PROVEN, GLOBAL_EARNER, DISCOVERY
- Stratified pools per content type based on creator-specific earnings
- Weight formula: Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)
- Vose Alias Method for O(1) weighted random selection

**Schedule Uniqueness Engine:**
- Timing variance: 7-10 minute randomization (85% of slots)
- Historical weighting: 60% performance + 20% recency + 20% diversity
- Cross-week deduplication: 4-week lookback with freshness penalties
- Schedule fingerprinting: SHA-256 hash for duplicate detection
- Uniqueness score: 0-100 based on freshness, diversity, and variance

**Hook Detection & Anti-Detection:**
- 7 hook types: curiosity, personal, exclusivity, recency, question, direct, teasing
- SAME_HOOK_PENALTY: 0.7x weight for consecutive same hooks
- Validation rules V015/V016 for hook rotation and diversity

**Extended Validation (31 Rules Total):**
- V001-V018: Core validation rules (existing)
- V020-V032: Extended content type rules (V019 intentionally skipped)
- Auto-correction for 10 issue types including spacing, duplicates, page type violations
- Self-healing validation with max 2 passes

**Content Type Registry:**
- 20 schedulable content types across 4 tiers
- Content type constraints: min_spacing_hours, max_daily, max_weekly
- Page type filtering: 4 paid-only types, 16 both-page types
- Specialized loaders per content type with theme guidance

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

### Breaking Changes in v3.2

| Change | Impact | Migration |
|--------|--------|-----------|
| Schema validation | Scripts may fail if DB missing `secondary_tone` column | Add column or use `--skip-schema-validation` |
| 31 validation rules | V032 now enforced for performance scores | Review performance_warning_threshold in config |
| Config externalization | Some hardcoded values now in YAML | Use env vars or config file overrides |

### Breaking Changes in v3.1

| Change | Impact | Migration |
|--------|--------|-----------|
| New exports | `generate_full_schedule`, `list_content_types`, `print_schedule_summary` added to `__all__` | No action needed - additive |
| Summary output | Schedule summary now printed to stderr after generation | Suppress with logging config if unwanted |

### Breaking Changes in v3.0

| Change | Impact | Migration |
|--------|--------|-----------|
| Default mode | Changed from "quick" to "full" | Add `--quick` flag to maintain old behavior |
| Full analysis by default | Schedules now include semantic analysis | No action if you want higher quality |
| --quick flag | New flag for pattern-based generation | Use `--quick` instead of relying on default |

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
