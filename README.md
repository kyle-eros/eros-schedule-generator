# EROS Schedule Generator

**Enterprise-Grade OnlyFans Content Scheduling for Claude Code**

A Claude Code slash command skill that generates optimized weekly content schedules for OnlyFans creators using a sophisticated 12-step extended pipeline with AI-enhanced semantic analysis.

```
                    ╔═══════════════════════════════════════╗
                    ║   EROS Schedule Generator v2.0        ║
                    ║   ─────────────────────────────────   ║
                    ║   36 Creators │ 19.6K Captions        ║
                    ║   66K+ Historical Messages            ║
                    ║   26,928 Lines of Code                ║
                    ╚═══════════════════════════════════════╝
```

---

## Overview

EROS (Enhanced Revenue Optimization System) is a Claude Code skill package that automates content scheduling for OnlyFans creators. It combines performance analytics, freshness scoring, persona matching, LLM-enhanced quality assessment, and business rule validation to produce optimized weekly schedules.

### Key Features

| Feature | Description |
|---------|-------------|
| **12-Step Extended Pipeline** | Complete scheduling workflow with optional LLM enhancement steps |
| **Dual Execution Modes** | Quick mode (<30 sec) or Full mode with semantic analysis (<60 sec) |
| **Vose Alias Algorithm** | O(1) weighted random selection for caption diversity |
| **Persona Matching** | 1.0-1.4x boost based on tone/emoji/slang alignment |
| **Quality Scoring** | LLM-based caption quality assessment (Full mode) |
| **Caption Enhancement** | Authenticity tweaks for natural-sounding content |
| **Context-Aware Follow-ups** | Intelligent bump message generation |
| **Freshness Decay** | 14-day exponential decay prevents caption fatigue |
| **Sub-Agent Delegation** | 7 specialized agents for advanced optimization |
| **Business Rules** | 8+ validation rules for PPV spacing, drip windows, etc. |

---

## Execution Modes

EROS supports two execution modes to balance speed and optimization depth:

| Mode | Entry Point | Time | Features |
|------|-------------|------|----------|
| **Quick Mode** | `generate_schedule.py` | <30 sec | Steps 1-9, pattern matching only |
| **Full Mode** | `prepare_llm_context.py` | <60 sec | Steps 1-9 + 4B/7B/8B, LLM semantic analysis |

### When to Use Each Mode

| Scenario | Mode | Why |
|----------|------|-----|
| Daily schedule generation | Quick | Speed is priority, pattern matching sufficient |
| Important creator launch | Full | Maximize conversion with semantic analysis |
| User requests "optimized" | Full | Full semantic analysis for best results |
| Low-confidence captions | Full | LLM helps where patterns struggle |
| High-value creator | Full | Worth the extra analysis time |

---

## 12-Step Extended Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EROS EXTENDED SCHEDULING PIPELINE                        │
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
│   │ Score captions by voice profile alignment (tone, emoji, slang)     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 4: BUILD STRUCTURE                                            │    │
│   │ Create weekly time slots based on optimal hours and volume level   │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 4B: QUALITY SCORING (Full Mode Only)                          │    │
│   │ LLM-based caption quality assessment: authenticity, hook strength, │    │
│   │ CTA effectiveness, conversion potential                            │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 5: ASSIGN CAPTIONS                                            │    │
│   │ Vose Alias weighted selection using performance + freshness        │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 6: GENERATE FOLLOW-UPS                                        │    │
│   │ Create context-aware 15-45min follow-up messages for PPVs          │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 7: APPLY DRIP WINDOWS                                         │    │
│   │ Enforce 4-8hr no-PPV zones after drip content                      │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 7B: CAPTION ENHANCEMENT (Full Mode Only)                      │    │
│   │ Authenticity tweaks: contractions, emoji calibration, slang        │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 8: APPLY PAGE TYPE RULES                                      │    │
│   │ Adjust for Paid vs Free page requirements                          │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 8B: CONTEXTUAL FOLLOW-UPS (Full Mode Only)                    │    │
│   │ Personalized bump messages based on content context                │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ STEP 9: VALIDATE & RETURN                                          │    │
│   │ Check all business rules, generate warnings, return schedule       │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│            ▼                                                                │
│   OUTPUT                                                                    │
│   ┌──────────────────┐                                                      │
│   │ List[ScheduleItem]│                                                     │
│   │ ValidationReport │                                                      │
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
├── pyproject.toml                    # Python project configuration
├── pytest.ini                        # Pytest configuration
├── .gitignore                        # Git ignore patterns
│
├── scripts/                          # Executable Python scripts (19 files, 26,928 lines)
│   │
│   │  # Core Pipeline Scripts
│   ├── generate_schedule.py          # Main 12-step pipeline orchestrator (3,082 lines)
│   ├── select_captions.py            # Vose Alias caption selection (489 lines)
│   ├── match_persona.py              # Persona matching & boost (896 lines)
│   ├── volume_optimizer.py           # Multi-factor volume optimization (1,584 lines)
│   ├── followup_generator.py         # Context-aware follow-up generation (1,070 lines)
│   ├── validate_schedule.py          # Business rule validation (935 lines)
│   ├── weights.py                    # Canonical weight calculation module (193 lines)
│   │
│   │  # LLM Integration Scripts
│   ├── prepare_llm_context.py        # Full mode entry point (974 lines)
│   ├── semantic_analysis.py          # Tone detection framework (743 lines)
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
│   ├── logging_config.py             # Centralized logging configuration (119 lines)
│   ├── content_type_loaders.py       # Wall posts, polls, previews loading (385 lines)
│   └── content_type_schedulers.py    # Content-specific scheduling logic (486 lines)
│
├── tests/                            # Test suite
│   ├── __init__.py                   # Test package init
│   ├── test_volume_optimizer.py      # Volume optimizer tests (2,183 lines, 171 tests)
│   └── test_integration.py           # Integration tests
│
├── assets/
│   └── sql/                          # SQL queries
│       ├── get_creator_profile.sql   # Creator profile query
│       ├── get_available_captions.sql # Fresh captions query
│       ├── get_optimal_hours.sql     # Best hours by revenue
│       ├── get_vault_inventory.sql   # Content availability
│       ├── get_active_creators.sql   # Active creator list
│       ├── get_performance_trends.sql # Weekly trends
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
| `generate_schedule.py` | 3,082 | Main orchestrator (all steps) |
| `select_captions.py` | 489 | Step 2: Match Content |
| `match_persona.py` | 896 | Step 3: Match Persona |
| `volume_optimizer.py` | 1,584 | Step 4: Build Structure |
| `followup_generator.py` | 1,070 | Step 6: Generate Follow-ups |
| `validate_schedule.py` | 935 | Step 9: Validate |
| `weights.py` | 193 | Canonical weight calculation |

### LLM Integration Scripts

| Script | Lines | Purpose |
|--------|-------|---------|
| `prepare_llm_context.py` | 974 | Full mode entry point - context preparation for Claude |
| `semantic_analysis.py` | 743 | Tone detection framework |
| `quality_scoring.py` | 1,295 | LLM-based caption quality assessment |

### Content Classification

| Script | Lines | Purpose |
|--------|-------|---------|
| `classify_implied_content.py` | 1,150 | Advanced content classification with inference |
| `generate_perfected_guides.py` | 1,030 | Guide generation utilities |

### Infrastructure & Utilities

| Script | Lines | Purpose |
|--------|-------|---------|
| `shared_context.py` | 289 | Shared dataclass definitions |
| `volume_validation_report.py` | 851 | Volume validation reporting |
| `verify_deployment.py` | 321 | Deployment verification |
| `utils.py` | 183 | VoseAliasSelector (O(1) weighted selection) |
| `logging_config.py` | 119 | Centralized logging configuration |
| `content_type_loaders.py` | 385 | Wall posts, polls, previews loading |
| `content_type_schedulers.py` | 486 | Content-specific scheduling logic |

### Testing

| Script | Lines | Purpose |
|--------|-------|---------|
| `test_volume_optimizer.py` | 2,183 | Volume optimizer test suite (171 tests, 95%+ coverage) |
| `test_integration.py` | - | Integration tests |

---

## Sub-Agent Architecture (v2.0)

EROS includes a sub-agent delegation system (`agent_invoker.py`) that routes specialized tasks to 7 focused agents organized by pipeline phase:

| Agent | Model | Timeout | Cache | Purpose |
|-------|-------|---------|-------|---------|
| `timezone-optimizer` | haiku | 15s | 30 days | Optimize send times across time zones |
| `onlyfans-business-analyst` | opus | 45s | 14 days | Market research and benchmarks |
| `content-strategy-optimizer` | sonnet | 30s | 7 days | Content rotation patterns |
| `volume-calibrator` | sonnet | 30s | 3 days | Saturation detection and volume |
| `revenue-optimizer` | sonnet | 30s | 7 days | Dynamic pricing recommendations |
| `multi-touch-sequencer` | opus | 45s | 1 day | 3-touch follow-up sequences |
| `validation-guardian` | sonnet | 30s | never | 15+ rule validation |

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

### Weight Calculation (Pool-Based Selection)

The new earnings-first weight system uses pool-based selection with different strategies:

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

**Discovery Bonus (DISCOVERY pool only):**
- High global earners: up to +5 points (percentile-based)
- Universal captions: +1.5 points
- High performance (>=70): +1.0 points
- Medium performance (>=50): +0.5 points

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

---

## Volume Levels

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
- Minimum 2 PPV/day for ALL creators
- Maximum 6 PPV/day for proven performers
- Performance-based progression replaces fan-count-only tiers

---

## Business Rules

### PPV Spacing
- **Minimum**: 3 hours (error if violated)
- **Recommended**: 4 hours (warning if below)

### Follow-up Rules
- Only for captions with performance_score >= 60
- Delay: 15-45 minutes after PPV
- Maximum 1 follow-up per PPV

### Drip Window Rules
- Duration: 4-8 hours after drip content
- NO PPVs within drip window
- Bumps ARE allowed within drip windows

### Validation Checklist
- PPV spacing >= 3 hours
- All captions have freshness >= 30
- Content types match vault availability
- Follow-ups are 15-45 min after parent PPV
- No PPVs within drip windows
- Daily PPV count matches volume level
- No duplicate captions in same week
- No same content type 3x consecutive

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
# Run all tests (171 tests)
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
| `generate_schedule.py` | (integrated) | - |
| `calculate_freshness.py` | (integrated) | - |

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
║   EROS Schedule Generator v2.0                                            ║
║   Built for Claude Code │ 12-Step Extended Pipeline │ AI-Enhanced         ║
║   19 Scripts │ 26,928 Lines │ 16 SQL Queries │ 171 Tests                  ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```
