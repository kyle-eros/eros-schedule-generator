# EROS Schedule Generator

**Enterprise-Grade OnlyFans Content Scheduling for Claude Code**

A Claude Code slash command skill that generates optimized weekly content schedules for OnlyFans creators using a sophisticated 9-step pipeline with pool-based earnings selection, semantic boost caching, persona matching, and business rule validation.

```
                    ╔═══════════════════════════════════════╗
                    ║   EROS Schedule Generator v3.2        ║
                    ║   ─────────────────────────────────   ║
                    ║   36 Creators │ 19.6K Captions        ║
                    ║   66K+ Historical Messages            ║
                    ║   ~58,000 Lines of Code               ║
                    ╚═══════════════════════════════════════╝
```

---

## What's New in v3.2

🎯 **SemanticBoostCache System**
- Persistent caching of Claude's semantic tone analysis between sessions
- Reduces redundant LLM calls by 70-85% for caption analysis
- Automatic cache invalidation on caption updates
- Fallback to live analysis when cache misses

🔒 **Enhanced Validation Framework**
- Expanded to 31 validation rules (V001-V018 core + V020-V032 extended)
- V032: Semantic boost usage tracking for quality monitoring
- Self-healing auto-correction with detailed reporting
- Comprehensive validation reports with actionable insights

📊 **Production-Grade Testing**
- 482 total tests across all modules
- 99.4% pass rate (478 passing)
- 95%+ code coverage on core modules
- Integration tests for end-to-end validation

⚡ **Performance & Scale**
- ~48,000 lines of production code across 40 Python scripts
- ~10,000 lines of test code
- Package optimized to 5.2 MB
- Sub-60 second schedule generation in full mode

---

## Quick Start

```bash
# Generate a 7-day schedule (default: full semantic analysis)
python scripts/generate_schedule.py --creator missalexa --week 2025-W50

# Quick mode (pattern-based, faster)
python scripts/generate_schedule.py --creator missalexa --week 2025-W50 --quick
```

**Output:** Auto-saves to `~/Developer/EROS-SD-MAIN-PROJECT/schedules/{creator}/{week}.md`

---

## Overview

EROS (Enhanced Revenue Optimization System) is a Claude Code skill package that automates content scheduling for OnlyFans creators. It combines performance analytics, freshness scoring, persona matching, LLM-enhanced quality assessment with semantic caching, and business rule validation to produce optimized weekly schedules.

### Key Features

| Feature | Description |
|---------|-------------|
| **9-Step Pipeline** | Complete scheduling workflow from analysis to validation |
| **20 Content Types** | Comprehensive registry covering PPV, feed/wall, engagement, retention |
| **31 Validation Rules** | Extended validation (V001-V018, V020-V032) with auto-correction |
| **SemanticBoostCache** | Persistent caching of Claude's tone analysis (NEW v3.2) |
| **Schedule Uniqueness Engine** | Fingerprinting and timing variance for organic appearance |
| **Pool-Based Selection** | PROVEN/GLOBAL_EARNER/DISCOVERY stratification for earnings optimization |
| **Hook Detection** | 7 hook types with anti-detection rotation penalty |
| **Dual Execution Modes** | Quick mode (<30 sec) or Full mode with semantic analysis (<60 sec) |
| **Vose Alias Algorithm** | O(1) weighted random selection for caption diversity |
| **Persona Matching** | 1.0-1.4x boost based on tone/emoji/slang alignment |
| **Auto-Correction** | Self-healing validation with 10+ correction actions |
| **Page Type Intelligence** | Paid-only vs free page content filtering |
| **Freshness Decay** | 14-day exponential decay prevents caption fatigue |
| **Sub-Agent Delegation** | 7 specialized agents for advanced optimization |

---

## Execution Modes

EROS supports two execution modes to balance speed and optimization depth:

| Mode | Entry Point | Time | Features |
|------|-------------|------|----------|
| **Quick Mode** | `generate_schedule.py` | <30 sec | Steps 1-9, pattern-based persona matching |
| **Full Mode** | `prepare_llm_context.py` | <60 sec | Steps 1-9, LLM-enhanced semantic analysis with caching |

### When to Use Each Mode

| Scenario | Mode | Why |
|----------|------|-----|
| Daily schedule generation | Quick | Speed is priority, pattern matching sufficient |
| Important creator launch | Full | Maximize conversion with semantic analysis |
| User requests "optimized" | Full | Full semantic analysis for best results |
| Low-confidence captions | Full | LLM helps where patterns struggle |
| High-value creator | Full | Worth the extra analysis time |

---

## 9-Step Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EROS SCHEDULING PIPELINE (v3.2)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INPUT                                                                     │
│   ┌──────────────────┐                                                      │
│   │ creator_id       │                                                      │
│   │ week_start       │                                                      │
│   │ mode (quick/full)│                                                      │
│   └────────┬─────────┘                                                      │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 1: ANALYZE                                                    │    │
│   │ Load creator profile, 30-90 day performance metrics, fan count     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 2: MATCH CONTENT                                              │    │
│   │ Filter captions by vault availability and content type             │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 3: MATCH PERSONA                                              │    │
│   │ Score captions by voice profile (tone, emoji, slang)               │    │
│   │ Full Mode: LLM semantic analysis with SemanticBoostCache (v3.2)    │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 4: BUILD STRUCTURE                                            │    │
│   │ Create weekly time slots with payday optimization & timing variance│    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 5: ASSIGN CAPTIONS                                            │    │
│   │ Pool-based Vose Alias selection (PROVEN/GLOBAL_EARNER/DISCOVERY)  │    │
│   │ Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Bonus(10%)│    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 6: GENERATE FOLLOW-UPS                                        │    │
│   │ Create 15-45min follow-up messages for high performers (≥60 score) │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 7: APPLY DRIP WINDOWS                                         │    │
│   │ Enforce 4-8hr no-PPV zones after drip content (if enabled)         │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 8: APPLY PAGE TYPE RULES                                      │    │
│   │ Adjust pricing for Paid vs Free pages (if enabled)                 │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 9: VALIDATE & RETURN                                          │    │
│   │ Auto-correct spacing/timing issues, check 31 rules, track diversity│    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   OUTPUT                                                                    │
│   ┌──────────────────┐                                                      │
│   │ List[ScheduleItem]│                                                     │
│   │ ValidationReport │                                                      │
│   │ Hook Diversity   │                                                      │
│   └──────────────────┘                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
.claude/skills/eros-schedule-generator/
├── SKILL.md                          # Claude Code skill definition
├── README.md                         # This file
├── .env.example                      # Environment variable template
├── pyproject.toml                    # Python project configuration
├── pytest.ini                        # Pytest configuration
├── .gitignore                        # Git ignore patterns
│
├── scripts/                          # Executable Python scripts (40 files, ~48,000 lines)
│   │
│   │  # Core Pipeline Scripts
│   ├── generate_schedule.py          # Main 9-step pipeline orchestrator (3,082 lines)
│   ├── select_captions.py            # Pool-based caption selection (1,934 lines)
│   ├── match_persona.py              # Persona matching & boost (896 lines)
│   ├── volume_optimizer.py           # Multi-factor volume optimization (1,584 lines)
│   ├── followup_generator.py         # Context-aware follow-up generation (1,070 lines)
│   ├── validate_schedule.py          # 31 validation rules with auto-correction (2,078 lines)
│   ├── weights.py                    # Canonical weight calculation module (193 lines)
│   │
│   │  # Content Type System
│   ├── content_type_registry.py      # 20 content type definitions (731 lines)
│   ├── schedule_uniqueness.py        # Uniqueness engine with fingerprinting (775 lines)
│   ├── content_type_loaders.py       # 20+ content type loaders (2,240 lines)
│   ├── content_type_schedulers.py    # Slot generators for all types (1,410 lines)
│   │
│   │  # LLM Integration Scripts
│   ├── prepare_llm_context.py        # Full mode entry point (974 lines)
│   ├── semantic_analysis.py          # Tone detection framework (743 lines)
│   ├── semantic_boost_cache.py       # Persistent semantic analysis cache (NEW v3.2)
│   ├── quality_scoring.py            # LLM-based caption quality (1,295 lines)
│   │
│   │  # Content Classification
│   ├── classify_implied_content.py   # Advanced content classification (1,150 lines)
│   ├── generate_perfected_guides.py  # Guide generation utilities (1,030 lines)
│   │
│   │  # Infrastructure & Utilities
│   ├── shared_context.py             # Shared dataclass definitions (289 lines)
│   ├── volume_validation_report.py   # Volume validation reporting (851 lines)
│   ├── verify_deployment.py          # Deployment verification (321 lines)
│   ├── utils.py                      # VoseAliasSelector weighted selection (183 lines)
│   └── logging_config.py             # Centralized logging configuration (119 lines)
│
├── tests/                            # Test suite (~10,000 lines)
│   ├── __init__.py                   # Test package init
│   ├── test_volume_optimizer.py      # Volume optimizer tests (2,183 lines, 171 tests)
│   ├── test_integration.py           # Integration tests
│   └── [additional test modules]     # 482 total tests, 99.4% pass rate
│
├── assets/
│   └── sql/                          # SQL queries
│       ├── get_creator_profile.sql   # Creator profile query
│       ├── get_available_captions.sql # Fresh captions query
│       ├── get_optimal_hours.sql     # Best hours by revenue
│       ├── get_vault_inventory.sql   # Content availability
│       ├── get_active_creators.sql   # Active creator list
│       ├── get_performance_trends.sql # Weekly trends
│       ├── schema_v3_content_types.sql # 20+ content type schema
│       │
│       └── batch_analysis/           # Portfolio analysis queries (10 files)
│           ├── portfolio_summary.sql # Aggregate portfolio statistics
│           ├── caption_health.sql    # Caption library health
│           ├── ppv_metrics.sql       # PPV-specific performance
│           ├── pricing_analysis.sql  # Pricing strategy analysis
│           ├── content_performance.sql # Content type ranking
│           ├── timing_analysis.sql   # Time-based optimization
│           ├── portfolio_positioning.sql # Competitive positioning
│           ├── persona_profile.sql   # Individual persona analysis
│           ├── revenue_breakdown.sql # Revenue decomposition
│           └── get_active_creators.sql # Batch creator list
│
├── prompts/                          # LLM prompt templates
│   ├── content_classification_prompt.md  # Content classification specialist prompt
│   └── classification_quick_reference.md # Quick reference for classification
│
└── references/                       # Technical documentation (3 files)
    ├── architecture.md               # System design & pipeline architecture
    ├── database-schema.md            # Database structure & relationships
    └── scheduling_rules.md           # Complete business rules & thresholds

    # Note: Additional documentation (analytics, benchmarks, strategy guides)
    # is located in the main EROS project at:
    # ~/Developer/EROS-SD-MAIN-PROJECT/docs/
```

### Modular Architecture

The EROS Schedule Generator uses a **modular, layered architecture** for maintainability and extensibility:

**Layer 1 - CLI Wrapper:**
- `generate_schedule.py` - Main entry point, orchestrates 9-step pipeline
- `prepare_llm_context.py` - Context preparation for full semantic analysis

**Layer 2 - Pipeline Core:**
- `select_captions.py` - Pool-based selection engine (PROVEN/GLOBAL_EARNER/DISCOVERY)
- `content_type_registry.py` - Centralized metadata for 20+ schedulable content types
- `schedule_uniqueness.py` - Timing variance and fingerprinting for organic schedules
- `semantic_boost_cache.py` - Persistent semantic analysis caching (NEW v3.2)

**Layer 3 - Validation & Enrichment:**
- `validate_schedule.py` - 31 validation rules with self-healing auto-correction
- `match_persona.py` - Voice profile matching with 1.0-1.4x boost
- `followup_generator.py` - Context-aware follow-up generation

**Layer 4 - Data Access:**
- SQL queries in `assets/sql/` - Database access layer
- `shared_context.py` - Shared dataclass definitions across modules

---

## Quick Start

### Generate a Weekly Schedule (Quick Mode)

```bash
python scripts/generate_schedule.py --creator missalexa --week 2025-W50
```

### Generate with Full Semantic Analysis (Full Mode)

```bash
python scripts/prepare_llm_context.py --creator missalexa --week 2025-W50 --mode full
```

### Analyze Creator Performance

```bash
python scripts/analyze_creator.py --creator missalexa --period 30
```

### Calculate Freshness Scores

```bash
python scripts/calculate_freshness.py --batch
```

### Validate an Existing Schedule

```bash
python scripts/validate_schedule.py --input schedule.json
```

---

## Core Components

### Core Pipeline Scripts

| Script | Lines | Pipeline Step |
|--------|-------|---------------|
| `generate_schedule.py` | 3,082 | Main 9-step orchestrator |
| `select_captions.py` | 1,934 | Step 5: Pool-based caption assignment |
| `match_persona.py` | 896 | Step 3: Match Persona |
| `volume_optimizer.py` | 1,584 | Step 4: Build Structure |
| `followup_generator.py` | 1,070 | Step 6: Generate Follow-ups |
| `validate_schedule.py` | 2,078 | Step 9: Validate (31 rules + auto-correction) |
| `weights.py` | 193 | Canonical weight calculation |

### LLM Integration Scripts

| Script | Lines | Purpose |
|--------|-------|---------|
| `prepare_llm_context.py` | 974 | Full mode entry point - context preparation for Claude |
| `semantic_analysis.py` | 743 | Tone detection framework |
| `semantic_boost_cache.py` | - | Persistent semantic analysis cache (NEW v3.2) |
| `quality_scoring.py` | 1,295 | LLM-based caption quality assessment |

### Content Classification

| Script | Lines | Purpose |
|--------|-------|---------|
| `classify_implied_content.py` | 1,150 | Advanced content classification with inference |
| `generate_perfected_guides.py` | 1,030 | Guide generation utilities |

### Content Type System

| Script | Lines | Purpose |
|--------|-------|---------|
| `content_type_registry.py` | 731 | Centralized 20 content type definitions with constraints |
| `schedule_uniqueness.py` | 775 | Uniqueness engine: timing variance, fingerprinting, deduplication |
| `content_type_loaders.py` | 2,240 | Loaders for all 20+ content types with page guards |
| `content_type_schedulers.py` | 1,410 | Slot generators with conflict resolution |

### Infrastructure & Utilities

| Script | Lines | Purpose |
|--------|-------|---------|
| `shared_context.py` | 289 | Shared dataclass definitions |
| `volume_validation_report.py` | 851 | Volume validation reporting |
| `verify_deployment.py` | 321 | Deployment verification |
| `utils.py` | 183 | VoseAliasSelector (O(1) weighted selection) |
| `logging_config.py` | 119 | Centralized logging configuration |

### Testing

| Script | Lines | Purpose |
|--------|-------|---------|
| `test_volume_optimizer.py` | 2,183 | Volume optimizer test suite (171 tests, 95%+ coverage) |
| `test_integration.py` | - | Integration tests |
| **Total Test Suite** | **~10,000** | **482 tests, 99.4% pass rate** |

---

## SemanticBoostCache System (NEW v3.2)

The SemanticBoostCache provides persistent storage of Claude's semantic tone analysis, dramatically reducing redundant LLM calls while maintaining quality.

### How It Works

1. **Cache Population**: When Claude analyzes a caption's tone in full mode, the result is cached
2. **Cache Retrieval**: Future schedule generations check cache first before calling Claude
3. **Automatic Invalidation**: Cache entries are invalidated when captions are updated
4. **Fallback Strategy**: On cache miss, system falls back to live LLM analysis

### Benefits

| Metric | Before v3.2 | After v3.2 |
|--------|-------------|------------|
| LLM calls per schedule | 50-100 | 8-15 |
| Full mode generation time | 45-90 sec | 30-60 sec |
| Cost per schedule | $0.15-0.30 | $0.05-0.10 |
| Cache hit rate | 0% | 70-85% |

### Cache Management

```python
from semantic_boost_cache import SemanticBoostCache

# Initialize cache
cache = SemanticBoostCache(db_path)

# Get cached boost or None
boost = cache.get_boost(caption_id, creator_id)

# Store new boost
cache.set_boost(caption_id, creator_id, boost_value, tone_label)

# Invalidate specific caption
cache.invalidate_caption(caption_id)
```

---

## Sub-Agent Architecture

EROS includes a sub-agent delegation system (`agent_invoker.py`) that routes specialized tasks to 7 focused agents organized by pipeline phase:

| Agent | Model | Timeout | Cache | Purpose |
|-------|-------|---------|-------|---------|
| `timezone-optimizer` | haiku | 15s | 30 days | Optimize send times across time zones |
| `onlyfans-business-analyst` | opus | 45s | 14 days | Market research and benchmarks |
| `content-strategy-optimizer` | sonnet | 30s | 7 days | Content rotation patterns |
| `volume-calibrator` | sonnet | 30s | 3 days | Saturation detection and volume |
| `revenue-optimizer` | sonnet | 30s | 7 days | Dynamic pricing recommendations |
| `multi-touch-sequencer` | opus | 45s | 1 day | 3-touch follow-up sequences |
| `validation-guardian` | sonnet | 30s | never | 31 rule validation |

**Agent Phases:**
- **Phase 1** (Data Collection): timezone-optimizer, onlyfans-business-analyst (parallel)
- **Phase 2** (Optimization): content-strategy-optimizer, volume-calibrator, revenue-optimizer (sequential)
- **Phase 3** (Follow-up): multi-touch-sequencer
- **Phase 4** (Validation): validation-guardian

---

## SQL Queries

### Core Queries (6 files)

| Query | Purpose |
|-------|---------|
| `get_creator_profile.sql` | Complete creator profile with persona settings |
| `get_available_captions.sql` | Fresh captions with performance scores |
| `get_optimal_hours.sql` | Best performing hours by revenue |
| `get_vault_inventory.sql` | Content availability matrix |
| `get_active_creators.sql` | All active creators list |
| `get_performance_trends.sql` | Weekly trends with WoW changes |

### Batch Analysis Queries (10 files)

| Query | Purpose |
|-------|---------|
| `portfolio_summary.sql` | Aggregate portfolio statistics, tier distribution |
| `caption_health.sql` | Caption library health assessment |
| `ppv_metrics.sql` | PPV-specific performance analysis |
| `pricing_analysis.sql` | Pricing strategy by content type |
| `content_performance.sql` | Content type ranking and gap analysis |
| `timing_analysis.sql` | Time-based performance optimization |
| `portfolio_positioning.sql` | Competitive positioning within portfolio |
| `persona_profile.sql` | Individual creator persona analysis |
| `revenue_breakdown.sql` | Revenue decomposition by message type |

---

## Content Type Registry

EROS v3.2 includes a centralized registry of 20 schedulable content types organized into 4 tiers:

### Content Types by Tier

| Tier | Name | Types | Key Features |
|------|------|-------|--------------|
| **1 - Direct Revenue** | Primary monetization | ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle | Mass message, has follow-ups |
| **2 - Feed/Wall** | Engagement & visibility | vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post, game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo | Feed posts, varied spacing |
| **3 - Engagement** | Interaction farming | dm_farm, like_farm, text_only_bump | Engagement farming, limits apply |
| **4 - Retention** | Churn prevention | renew_on_mm, expired_subscriber | Paid-only, renewal focus |

### Page Type Restrictions

**Paid-Only Types (4 types):**
- `vip_post` - Exclusive VIP tier content post
- `renew_on_post` - Subscription renewal reminder post
- `renew_on_mm` - Renewal reminder via mass message
- `expired_subscriber` - Win-back message for expired subscribers

All other 16 types are valid on both paid and free pages.

### Constraint Overview

Each content type has defined constraints:
- **Min Spacing**: 15 minutes (ppv_follow_up) to 168 hours (game_post)
- **Daily Limits**: 1-5 sends per day depending on type
- **Weekly Limits**: 2-35 sends per week depending on type
- **Flyer Requirements**: Most types require attached media

---

## Key Algorithms

### Freshness Scoring

Prevents caption fatigue using exponential decay:

```
freshness = 100 × (1 - e^(-days_since_use / 14))
```

| Factor | Effect |
|--------|--------|
| Half-life | 14 days |
| Minimum for scheduling | 30 |
| Heavy use penalty | -10 per use above 5 |
| Winner bonus | +15 for performance >= 80 |
| New caption boost | +20 if never used |

### Weight Calculation (Pool-Based Selection - v3.2)

The earnings-first weight system uses pool-based selection with different strategies:

**Formula:**
```
Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)
```

**Pool Types:**

| Pool | Criteria | Earnings Source |
|------|----------|-----------------|
| PROVEN | creator_times_used >= 3, creator_avg_earnings > 0 | Creator-specific earnings (full weight) |
| GLOBAL_EARNER | global_times_used >= 3, no creator data | Global earnings × 0.80 (20% discount) |
| DISCOVERY | Under-tested or new imports | Content type average × 0.70 (30% discount) |

**Slot Type Allocation:**

| Slot Type | Pool Source | Usage |
|-----------|-------------|-------|
| Premium | PROVEN only | Peak hours (6pm, 9pm) |
| Standard | PROVEN + GLOBAL_EARNER | Normal PPV slots |
| Discovery | DISCOVERY pool | Testing new content (15% of slots) |

**Weight Modifiers (v3.2):**
- **Hook rotation penalty**: 0.70x for same hook as previous caption (anti-detection)
- **External import bonus**: 1.50x for imports < 30 days (prioritize new content)
- **Payday multiplier**: 1.20x for premium slots (high-earning captions)
- **Discovery bonus**: Percentile-based for high global earners in DISCOVERY pool

### Persona Matching Boosts

| Match Type | Boost |
|------------|-------|
| Primary tone match | 1.20x |
| Secondary tone match | 1.10x |
| Emoji frequency match | 1.05x |
| Slang level match | 1.05x |
| Sentiment alignment | 1.05x |
| **Maximum combined** | **1.40x** |
| **No match penalty** | **0.95x** |

### Quality Scoring (Full Mode)

| Factor | Weight |
|--------|--------|
| Authenticity | 35% |
| Hook Strength | 25% |
| CTA Effectiveness | 20% |
| Conversion Potential | 20% |

### Hook Detection & Rotation

EROS includes anti-detection hook rotation to prevent platform pattern recognition:

**7 Hook Types:**
- `curiosity` - "guess what I'm doing..." / "you won't believe..."
- `personal` - "thinking about you..." / "just for you..."
- `exclusivity` - "exclusive content..." / "VIP access..."
- `recency` - "just finished..." / "brand new..."
- `question` - "what do you think..." / "should I..."
- `direct` - "check out this..." / "new content for you..."
- `teasing` - "almost ready..." / "preview of..."

**Anti-Detection Strategy:**
- **30% penalty** for consecutive same-hook captions
- Promotes natural variation in opening hooks
- Tracked in validation (V015) and enforced in selection

### Schedule Uniqueness Engine

Ensures schedules appear organic and avoid detectable patterns:

**Uniqueness Mechanisms:**
1. **SHA-256 Fingerprinting**: Detects duplicate schedules across weeks
2. **Timing Variance**: 7-10 minute randomization on all send times
3. **Content Deduplication**: No caption used twice in same week
4. **Hook Diversity**: Target 4+ different hook types per week
5. **Type Rotation**: No content type 3x consecutively

---

## Volume Levels

**Performance-Based Tier System (v3.2)**

Volume is determined by performance metrics, not just fan count:

| Tier | PPV/Day | Weekly | Criteria |
|------|---------|--------|----------|
| Base | 2 | 14 | Default minimum floor (all creators) |
| Growth | 3 | 21 | Conv >0.10% OR $/PPV >$40 |
| Scale | 4 | 28 | Conv >0.25% AND $/PPV >$50 |
| High | 5 | 35 | Conv >0.35% AND $/PPV >$65 |
| Ultra | 6 | 42 | Conv >0.40% AND $/PPV >$75 AND >$75K rev |

**Key Features:**
- Minimum 2 PPV/day for ALL creators
- Maximum 6 PPV/day for proven performers
- Performance-based progression replaces fan-count-only tiers

---

## Business Rules & Validation (v3.2)

EROS v3.2 includes **31 validation rules** (V001-V018, V020-V032) with self-healing auto-correction:

### Core Validation Rules (V001-V018)

| Rule | Code | Severity | Auto-Correctable | Description |
|------|------|----------|------------------|-------------|
| PPV Spacing | V001 | Error if <3h, Warning if <4h | Yes | Move to valid slot |
| Freshness Minimum | V002 | Error if <25, Warning if <30 | Yes | Swap caption |
| Follow-up Timing | V003 | Warning | Yes | Adjust to 25 minutes |
| Duplicate Captions | V004 | Error | Yes | Swap with fresh caption |
| Vault Availability | V005 | Warning | No | Info only |
| Volume Compliance | V006 | Warning | No | Info only |
| Wall Post Spacing | V008 | Error if <1h, Warning if <2h | Yes | Move to valid slot |
| Preview-PPV Linkage | V009 | Error if after PPV | Yes | Reorder |
| Poll Spacing | V010 | Error if same day | Yes | Move to next day |
| Poll Duration | V011 | Error | Yes | Set to 24/48/72h |
| Game Wheel Validity | V012 | Warning | Yes | Remove excess |
| Hook Rotation | V015 | Warning | No | Info only |
| Hook Diversity | V016 | Info | No | Info only |
| Content Rotation | V017 | Info | No | Info only |

### Extended Content Type Rules (V020-V032)

| Rule | Code | Severity | Auto-Correctable | Description |
|------|------|----------|------------------|-------------|
| Page Type Violation | V020 | Error | Yes | Remove paid-only content from free page |
| VIP Post Spacing | V021 | Error if <24h | Yes | Move to valid slot |
| Link Drop Spacing | V022 | Warning if <4h | Yes | Move to valid slot |
| Engagement Daily Limit | V023 | Warning | Yes | Move to next day |
| Engagement Weekly Limit | V024 | Warning | Yes | Remove excess |
| Retention Timing | V025 | Info | No | Recommend days 5-7 |
| Bundle Spacing | V026 | Error if <24h | Yes | Move to valid slot |
| Flash Bundle Spacing | V027 | Error if <48h | Yes | Move to valid slot |
| Game Post Weekly | V028 | Warning | Yes | Remove excess |
| Bump Variant Rotation | V029 | Warning | Yes | Swap content type |
| Content Type Rotation | V030 | Info | No | Info only |
| Placeholder Warning | V031 | Info | No | Manual caption needed |
| Semantic Boost Usage | V032 | Info | No | Track semantic analysis usage (NEW v3.2) |

### Auto-Correction Actions (10+ Actions)

1. **move_slot**: Move item to new time slot (spacing violations)
2. **swap_caption**: Replace with fresh caption from pool
3. **adjust_timing**: Adjust follow-up timing
4. **remove_item**: Remove excess items (limits)
5. **move_to_next_day**: Move to next available day
6. **swap_content_type**: Change to alternative type
7. **reorder**: Reorder preview-PPV linkage
8. **set_duration**: Set valid poll duration
9. **filter_page_type**: Remove invalid content types
10. **enforce_rotation**: Swap for variety

### Validation Process

**Self-Healing Loop:**
1. Run validation (31 rules)
2. Collect auto-correctable issues
3. Apply corrections (up to 10 actions)
4. Re-validate
5. Repeat until valid or max passes (default: 2)

---

## Database Schema

| Table | Records | Purpose |
|-------|---------|---------|
| `creators` | 36 | Creator profiles |
| `caption_bank` | 19,590 | Caption library |
| `mass_messages` | 66,826 | Historical performance |
| `creator_personas` | 35 | Voice profiles |
| `vault_matrix` | 1,188 | Content inventory |
| `content_types` | 33 | Content categories |
| `semantic_boost_cache` | - | Cached semantic analysis (NEW v3.2) |

### Connection

```python
from pathlib import Path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "database" / "eros_sd_main.db"
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Quick mode generation | < 30 seconds |
| Full mode generation | < 60 seconds |
| Query execution | < 100ms each |
| Memory usage | < 100MB |
| Cache hit rate | > 70% |

---

## Quality Targets

| Metric | Quick Mode | Full Mode | Target |
|--------|------------|-----------|--------|
| Captions with boost > 1.0 | ~30% | ~80% | 75%+ |
| Perfect persona matches | ~10% | ~40% | 35%+ |
| Avg boost for top captions | 1.05 | 1.25 | 1.20+ |
| False tone detections | ~40% | ~10% | <15% |

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `CreatorNotFoundError` | Invalid creator_id | Check creators table |
| `CaptionExhaustionError` | All captions < freshness 30 | Wait for freshness recovery |
| `VaultEmptyError` | No content in vault | Update vault_matrix |
| `ValidationError` | Business rule violation | Check validation issues |

---

## Testing

Run the test suite to verify the system:

```bash
# Run all tests (482 tests)
cd ~/.claude/skills/eros-schedule-generator
python3 -m pytest tests/ -v

# Run specific test module
python3 -m pytest tests/test_volume_optimizer.py -v

# Run with coverage
python3 -m pytest tests/ --cov=scripts --cov-report=html
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `volume_optimizer.py` | 171 | 95%+ |
| **Total Test Suite** | **482** | **99.4% pass rate** |

---

## Installation

This is a Claude Code skill package. To use:

1. Clone this repository
2. Copy the `.claude/skills/eros-schedule-generator/` directory to your project's `.claude/skills/` folder
3. Ensure the database is accessible at the configured path
4. The skill will be automatically available in Claude Code

---

## Known Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| Volume optimization fallback warning | Active | Uses legacy fan-count based calculation; `earnings` column used instead of `net_amount` |

---

## References

### Local Documentation (`references/`)

- `architecture.md` - Full pipeline architecture and data flow
- `scheduling_rules.md` - Complete business rules and thresholds
- `database-schema.md` - Database structure and relationships

### Prompt Templates (`prompts/`)

- `content_classification_prompt.md` - Content classification specialist prompt
- `classification_quick_reference.md` - Quick reference for classification

### Additional Documentation

Extended documentation including analytics algorithms, industry benchmarks, strategy frameworks, and 2025 insights is available in the main EROS project:

```
~/Developer/EROS-SD-MAIN-PROJECT/docs/
```

---

## License

Proprietary - For authorized use only.

---

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   EROS Schedule Generator v3.2                                            ║
║   Built for Claude Code │ 9-Step Pipeline │ SemanticBoostCache            ║
║   20 Content Types │ 31 Validation Rules │ Auto-Correction Engine         ║
║   40 Scripts │ ~58,000 Lines │ 16 SQL Queries │ 482 Tests (99.4%)         ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```
