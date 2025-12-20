# EROS Schedule Generator

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Claude Code](https://img.shields.io/badge/claude--code-opus--4.5-purple)
![Status](https://img.shields.io/badge/status-production-brightgreen)
![Agents](https://img.shields.io/badge/agents-24-orange)
![MCP Tools](https://img.shields.io/badge/mcp--tools-33-teal)

AI-powered multi-agent schedule generation system for OnlyFans creators using a 22-type send taxonomy. The system orchestrates **24 specialized agents** across **14 phases** to produce optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention.

## Overview

EROS (Engagement and Revenue Optimization System) is an intelligent scheduling platform that analyzes historical performance data from **73,613+ mass messages** across **37 active creators** to generate data-driven weekly content schedules. The system leverages machine learning, persona matching, and timing optimization to maximize creator revenue while maintaining authentic audience engagement.

### System Statistics

| Metric | Value |
|--------|-------|
| **Specialized Agents** | 24 agents (6 Haiku, 10 Sonnet, 8 Opus) |
| **Pipeline Phases** | 14 phases (0 → 9.5) |
| **MCP Tools** | 33 database tools |
| **Send Types** | 22 active types (9 revenue, 9 engagement, 4 retention) |
| **Database Size** | ~300MB (72 tables + 37 views = 109 objects) |
| **Caption Pool** | 59,405 performance-scored captions |
| **Historical Messages** | 73,613 mass messages analyzed |
| **Content Types** | 37 distinct content types |
| **Code Base** | 66,118 lines of Python algorithms |

## Key Features

### Core Capabilities

- **24 Specialized AI Agents in Concert** - Multi-agent pipeline with performance analysis, content curation, timing optimization, authenticity engine, and quality validation
- **Four-Layer Defense System** - Vault compliance + AVOID tier exclusion + validation proofs + certification requirements ensure only appropriate content is scheduled
- **ML-Powered Performance Prediction** - Real-time RPS and conversion predictions with feedback loops for continuous learning
- **Anti-AI Humanization** - Authenticity engine ensures captions pass platform AI detection while maintaining persona consistency
- **Dynamic Volume Optimization** - Content category-based bump multipliers (1.0x-2.67x) with intelligent followup scaling (80% of PPVs)
- **A/B Testing Orchestration** - Built-in experiment framework for testing send types, pricing, and timing strategies
- **Churn Risk Analysis** - Proactive retention analysis with automated win-back campaign generation

### Advanced Features

- **22 Distinct Send Types Across 3 Categories** - Revenue (9 types), Engagement (9 types), Retention (4 types)
- **Earnings-Based Caption Rotation** - Prioritize high-performing captions using actual revenue data
- **ML-Optimized Timing Recommendations** - Historical analysis of 73,613+ messages to identify peak engagement windows
- **Performance-Driven Content Selection** - TOP/MID/LOW/AVOID rankings with freshness scoring to prevent caption fatigue
- **Automated PPV Followup Generation** - Smart followup sequences with configurable delays (20-60 minutes)
- **Multi-Format Export** - CSV, JSON, and markdown output for seamless integration
- **Volume Trigger System** - Automated adjustments based on HIGH_PERFORMER, TRENDING_UP, SATURATING, and AUDIENCE_FATIGUE signals

## Quick Start

### Prerequisites

- Claude Code MAX subscription (Opus 4.5)
- Python 3.11+
- SQLite database (included: ~300MB, 109 objects)

### Basic Usage

Generate a schedule for a creator:

```bash
/eros:generate alexia
```

Analyze creator performance before scheduling:

```bash
/eros:analyze alexia
```

List all active creators:

```bash
/eros:creators
```

### Advanced Usage

Generate with specific focus:

```bash
# Revenue-focused schedule
Generate a revenue-focused schedule for alexia starting 2025-12-16

# Volume override
Generate schedule for alexia with volume level 4

# Category filtering
Generate schedule for alexia using only revenue types
```

## System Architecture

### 14-Phase Pipeline

The system executes through a carefully orchestrated 14-phase pipeline with multiple blocking checkpoints:

#### Pre-Pipeline Validation (Phase 0-0.5)
| Phase | Name | Agent | Authority |
|-------|------|-------|-----------|
| 0 | **Preflight Check** | preflight-checker (Haiku) | BLOCK if data missing |
| 0.5 | **Retention Risk Analysis** | retention-risk-analyzer (Opus) | - |

#### Analysis & Allocation (Phase 1-2.75)
| Phase | Name | Agent | Key Output |
|-------|------|-------|------------|
| 1 | **Performance Analysis** | performance-analyst (Opus) | Volume triggers, saturation scores |
| 2 | **Send Type Allocation** | send-type-allocator (Sonnet) | Daily distribution with DOW multipliers |
| 2.5 | **Variety Enforcement** | variety-enforcer (Sonnet) | 12+ unique send types enforced |
| 2.75 | **Performance Prediction** | content-performance-predictor (Opus) | ML-style RPS/conversion predictions |

#### Content Selection (Phase 3)
| Phase | Name | Agent | Authority |
|-------|------|-------|-----------|
| 3 | **Caption Selection** | caption-selection-pro (Sonnet) | VAULT GATE (Four-Layer Defense) |
| 3 | **Attention Scoring** | attention-quality-scorer (Sonnet, parallel) | Quality tier classification |

#### Timing & Followups (Phase 4-5.5)
| Phase | Name | Agent | Key Feature |
|-------|------|-------|-------------|
| 4 | **Timing Optimization** | timing-optimizer (Sonnet) | Historical best times + jitter |
| 5 | **Followup Generation** | followup-generator (Haiku) | 80% PPV followup rate |
| 5.5 | **Followup Timing** | followup-timing-optimizer (Haiku) | 20-60 minute delays |

#### Assembly & Optimization (Phase 6-8.5)
| Phase | Name | Agent | Purpose |
|-------|------|-------|---------|
| 6 | **Authenticity Engine** | authenticity-engine (Sonnet) | Anti-AI humanization (NO caption mods) |
| 7 | **Schedule Assembly** | schedule-assembler (Haiku) | Final structure creation |
| 7.5 | **Funnel Flow** | funnel-flow-optimizer (Sonnet) | Engagement → conversion optimization |
| 8 | **Revenue Optimization** | revenue-optimizer (Sonnet) | Pricing with tier multipliers |
| 8.5 | **Price Optimization** | ppv-price-optimizer (Opus) | Dynamic PPV pricing |
| 8.5 | **Schedule Review** | schedule-critic (Opus) | BLOCK authority for strategic issues |

#### Final Validation (Phase 9-9.5)
| Phase | Name | Agent | Authority |
|-------|------|-------|-----------|
| 9 | **Quality Validation** | quality-validator (Opus) | FINAL GATE - rejects vault/AVOID violations |
| 9 | **Expert Consensus** | quality-validator-expert (Opus, parallel) | Expert validation consensus |
| 9.5 | **Anomaly Detection** | anomaly-detector (Haiku) | Statistical anomaly flagging |

### Four-Layer Defense System

The caption selection process employs a defense-in-depth strategy to ensure only appropriate content is scheduled:

| Layer | Component | Validation Type | Failure Action |
|-------|-----------|-----------------|----------------|
| **Layer 1** | MCP Tools | Database-level vault_matrix INNER JOIN + AVOID tier exclusion | Returns only compliant captions |
| **Layer 2** | caption-selection-pro | Post-selection validation with ValidationProof | Rejects non-compliant, selects next best |
| **Layer 3** | quality-validator | Upstream proof verification + HARD REJECTION | Rejects entire schedule if ANY violation |
| **Layer 4** | save_schedule | ValidationCertificate requirement (Phase 1: optional) | Warns/rejects schedules without certificate |

**Key Principles**:
- Vault compliance and AVOID tier exclusion are HARD GATES that never degrade
- Each layer operates independently, providing redundancy
- Any violation at any layer results in schedule rejection
- Fallback hierarchy applies only AFTER hard gates pass

### 24 Specialized Agents

| # | Agent | Model | Phase | Responsibility | Authority |
|---|-------|-------|-------|----------------|-----------|
| 1 | preflight-checker | Haiku | 0 | Validate creator data & readiness | BLOCK |
| 2 | retention-risk-analyzer | Opus | 0.5 | Churn risk analysis & retention recommendations | - |
| 3 | performance-analyst | Opus | 1 | Saturation/opportunity analysis, volume triggers | - |
| 4 | send-type-allocator | Sonnet | 2 | Daily send type distribution with DOW multipliers | - |
| 5 | variety-enforcer | Sonnet | 2.5 | Content diversity enforcement (12+ unique types) | - |
| 6 | content-performance-predictor | Opus | 2.75 | ML-style RPS/conversion predictions | - |
| 7 | caption-selection-pro | Sonnet | 3 | Expert caption selection with vault compliance | VAULT GATE |
| 8 | attention-quality-scorer | Sonnet | 3 (parallel) | Caption attention scoring | - |
| 9 | timing-optimizer | Sonnet | 4 | Optimal posting time calculation with jitter | - |
| 10 | followup-generator | Haiku | 5 | Auto-generate PPV followups (80% rate) | - |
| 11 | followup-timing-optimizer | Haiku | 5.5 | Dynamic followup delay optimization | - |
| 12 | authenticity-engine | Sonnet | 6 | Anti-AI humanization, organic variation | - |
| 13 | schedule-assembler | Haiku | 7 | Final schedule structure assembly | - |
| 14 | funnel-flow-optimizer | Sonnet | 7.5 | Engagement-to-conversion flow optimization | - |
| 15 | revenue-optimizer | Sonnet | 8 | Price/positioning optimization with tier multipliers | - |
| 16 | ppv-price-optimizer | Opus | 8.5 | Dynamic PPV pricing using predictions | - |
| 17 | schedule-critic | Opus | 8.5 | Strategic review with BLOCK authority | BLOCK |
| 18 | quality-validator | Opus | 9 | FINAL GATE with Four-Layer Defense | BLOCK |
| 19 | quality-validator-expert | Opus | 9 (parallel) | Expert consensus validation | - |
| 20 | anomaly-detector | Haiku | 9.5 | Statistical anomaly detection before save | - |
| 21 | ab-testing-orchestrator | Opus | Parallel | A/B experiment management | - |
| 22 | win-back-specialist | Sonnet | Async | Win-back campaign generation | - |
| 23 | outcome-tracker | Haiku | Async | Track and analyze schedule outcomes (7 days post) | - |
| 24 | caption-optimizer | Sonnet | Utility | On-demand caption optimization | - |

**Model Distribution**: 6 Haiku (fast validation/assembly) • 10 Sonnet (complex optimization) • 8 Opus (strategic analysis/blocking)

## 22 Send Types

The system manages 22 distinct send types organized into 3 strategic categories:

### Revenue Generation (9 types)

| Send Type | Description | Max/Day | Revenue Impact |
|-----------|-------------|---------|----------------|
| `ppv_unlock` | Primary revenue send with locked content | 4 | High (direct conversion) |
| `ppv_wall` | Wall-posted PPV for wall page types | 3 | High (public visibility) |
| `tip_goal` | Gamified tipping with unlock incentive | 2 | Medium-High |
| `bundle` | Multi-content package deals | 2 | High (increased AOV) |
| `flash_bundle` | Time-limited bundle promotions | 1 | Very High (urgency) |
| `game_post` | Interactive games with tips | 1 | Medium |
| `first_to_tip` | Competitive tipping incentive | 1 | Medium |
| `vip_program` | Tiered subscription offering | 1/week | High (recurring) |
| `snapchat_bundle` | External platform bundle | 1/week | Medium |

### Engagement (9 types)

| Send Type | Description | Max/Day | Purpose |
|-----------|-------------|---------|---------|
| `link_drop` | Message-based link sharing | 3 | Drive external traffic |
| `wall_link_drop` | Wall-posted link sharing | 2 | Public engagement |
| `bump_normal` | Standard content bump with media | 4 | Re-engage subscribers |
| `bump_descriptive` | Text-heavy descriptive bump | 3 | Content storytelling |
| `bump_text_only` | Text-only bump (no media) | 2 | Low-friction engagement |
| `bump_flyer` | Visual promotional bump | 2 | Event promotion |
| `dm_farm` | DM engagement farming | 2 | Conversation starter |
| `like_farm` | Like engagement farming | 2 | Algorithm boost |
| `live_promo` | Live stream promotion | 1 | Event awareness |

### Retention (4 types)

| Send Type | Description | Max/Day | Page Type Restriction |
|-----------|-------------|---------|----------------------|
| `renew_on_post` | Renewal incentive via wall post | 2 | Paid pages only |
| `renew_on_message` | Renewal incentive via DM | 2 | Paid pages only |
| `ppv_followup` | Follow-up to PPV unlock (auto-generated) | 5 | All page types |
| `expired_winback` | Win-back campaign for expired subs | 1 | Paid pages only |

**Note**: `ppv_message` (deprecated) has been merged into `ppv_unlock`. Database contains 23 types but only 22 are active.

## MCP Tools (33 Database Tools)

The system provides 33 specialized tools for database integration via Model Context Protocol:

### Tool Categories

| Category | Count | Tools |
|----------|-------|-------|
| **Creator Data** | 4 | `get_active_creators`, `get_creator_profile`, `get_persona_profile`, `get_vault_availability` |
| **Caption Tools** | 7 | `get_top_captions`, `get_send_type_captions`, `validate_caption_structure`, `get_attention_metrics`, `get_caption_attention_scores`, `get_content_type_earnings_ranking`, `get_top_captions_by_earnings` |
| **Performance & Analytics** | 4 | `get_performance_trends`, `get_content_type_rankings`, `get_best_timing`, `get_active_volume_triggers` |
| **Send Type Configuration** | 3 | `get_send_types`, `get_send_type_details`, `get_volume_config` |
| **Prediction & ML** | 5 | `get_caption_predictions`, `save_caption_prediction`, `record_prediction_outcome`, `get_prediction_weights`, `update_prediction_weights` |
| **Churn & Win-Back** | 2 | `get_churn_risk_scores`, `get_win_back_candidates` |
| **A/B Experiments** | 3 | `get_active_experiments`, `save_experiment_results`, `update_experiment_allocation` |
| **Volume Triggers** | 2 | `save_volume_triggers`, `get_active_volume_triggers` |
| **Schedule Operations** | 2 | `save_schedule`, `execute_query` |
| **Channels** | 1 | `get_channels` |

**Total**: 33 tools

### Critical Tools

- **`get_volume_config`** - Dynamic volume optimization with 10 integrated modules: Base Tier, Multi-Horizon Fusion, Confidence Dampening, DOW Distribution, Elasticity Bounds, Content Weighting, Caption Pool Check, Prediction Tracking, Bump Multiplier (v3.0), Followup Scaling (v3.0)
- **`get_vault_availability`** - Hard filter for content type compliance (Four-Layer Defense)
- **`get_content_type_rankings`** - TOP/MID/LOW/AVOID tier classification with performance data
- **`get_top_captions`** - Performance-ranked captions with freshness scoring and vault filtering
- **`save_schedule`** - Persist schedules with ValidationCertificate requirement (Phase 1: optional)

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Step-by-step onboarding guide |
| [User Guide](docs/USER_GUIDE.md) | Comprehensive user documentation |
| [MCP API Reference](docs/MCP_API_REFERENCE.md) | Complete tool documentation (33 tools) |
| [Send Type Reference](docs/SEND_TYPE_REFERENCE.md) | All 22 send types with examples |
| [Architecture Blueprint](docs/SCHEDULE_GENERATOR_BLUEPRINT.md) | System design and technical details |
| [Orchestration Guide](.claude/skills/eros-schedule-generator/ORCHESTRATION.md) | 14-phase pipeline documentation (5,333 lines) |

## Project Structure

```
EROS-SD-MAIN-PROJECT/
├── .claude/
│   ├── agents/                              # 24 specialized agent definitions
│   ├── commands/eros/                       # Slash commands (generate, analyze, validate)
│   ├── settings.local.json                  # MCP permissions (33 tools)
│   └── skills/eros-schedule-generator/
│       ├── SKILL.md                         # Entry point (490 lines)
│       ├── ORCHESTRATION.md                 # 14-phase pipeline (5,333 lines)
│       ├── DATA_CONTRACTS.md                # Agent I/O contracts (2,253 lines)
│       ├── HELPERS.md                       # Utility functions (2,306 lines)
│       └── REFERENCE/                       # Canonical quick references
│           ├── SEND_TYPE_TAXONOMY.md
│           ├── VALIDATION_RULES.md
│           ├── CONFIDENCE_LEVELS.md
│           ├── TOOL_PATTERNS.md
│           └── CAPTION_SCORING_RULES.md
├── mcp/
│   ├── server.py                            # MCP server entry point
│   └── tools/                               # 33 MCP tool implementations
│       ├── caption.py                       # 7 caption tools
│       ├── creator.py                       # 4 creator tools
│       ├── performance.py                   # 4 performance tools
│       ├── prediction.py                    # 5 prediction tools
│       ├── churn.py                         # 2 churn tools
│       ├── experiments.py                   # 3 experiment tools
│       ├── volume_triggers.py               # 2 trigger tools
│       ├── send_types.py                    # 3 send type tools
│       ├── schedule.py                      # 2 schedule tools
│       └── query.py                         # 1 query tool
├── python/                                  # 66,118 lines of core algorithms
│   ├── volume/                              # Volume optimization (9,604 lines)
│   ├── orchestration/                       # Pipeline orchestration (7,827 lines)
│   ├── analytics/                           # Performance analysis
│   ├── caption/                             # Caption selection logic
│   └── config/                              # Configuration files
├── database/
│   ├── eros_sd_main.db                      # Production SQLite (~300MB)
│   ├── migrations/                          # 28 schema migrations
│   ├── docs/                                # Database documentation
│   └── scripts/                             # Utility scripts (vault_matrix_sync.py)
├── docs/                                    # Comprehensive documentation (764KB)
│   ├── USER_GUIDE.md
│   ├── SCHEDULE_GENERATOR_BLUEPRINT.md
│   ├── SEND_TYPE_REFERENCE.md
│   ├── MCP_API_REFERENCE.md
│   └── GLOSSARY.md
└── README.md                                # This file
```

## Database

| Metric | Value |
|--------|-------|
| **Size** | ~300MB (294MB main + WAL files) |
| **Database Objects** | 109 total (72 base tables + 37 views) |
| **Active Creators** | 37 with performance data |
| **Caption Pool** | 59,405 performance-scored captions |
| **Mass Messages** | 73,613 historical messages |
| **Content Types** | 37 distinct types |
| **Schema Migrations** | 28 migrations applied |

### Key Tables

- **`creators`** - Creator profiles with performance tiers, personas, and volume configuration
- **`caption_bank`** - 59,405 captions with performance scores, freshness tracking, and send type compatibility
- **`send_types`** - 22 active send type configurations (23 in DB, `ppv_message` deprecated)
- **`mass_messages`** - 73,613+ historical performance records for ML training
- **`vault_matrix`** - Creator-specific content type permissions (hard filter for compliance)
- **`volume_performance_tracking`** - Multi-horizon saturation/opportunity metrics (7d/14d/30d)
- **`top_content_types`** - Performance rankings (TOP/MID/LOW/AVOID tiers)
- **`volume_triggers`** - Automated performance-based volume adjustments
- **`caption_predictions`** - ML prediction tracking with feedback loops
- **`churn_risk_scores`** - Subscriber churn analysis by segment
- **`ab_experiments`** - A/B testing framework for optimization

### Database Quality

- **Normalization**: 3NF with strategic denormalization for performance
- **Indexes**: Comprehensive indexing on all query patterns
- **Constraints**: Foreign keys, unique constraints, and check constraints enforced
- **Migrations**: Full migration history with rollback support (28 migrations)

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Runtime** | Claude Code MAX (Opus 4.5) | Multi-agent orchestration with 24 specialized agents |
| **Database** | SQLite 3 | Production database (~300MB, 109 objects) |
| **Integration** | Model Context Protocol (MCP) | 33 specialized database tools |
| **Core Algorithms** | Python 3.11+ | 66,118 lines of volume optimization, analytics, and orchestration |
| **Agent Models** | Haiku (6), Sonnet (10), Opus (8) | Distributed intelligence across pipeline phases |
| **Export Formats** | CSV, JSON, Markdown | Seamless integration with external systems |
| **Documentation** | Markdown (764KB) | Comprehensive guides, references, and API docs |

## Requirements

### System Requirements

| Requirement | Version/Details |
|-------------|-----------------|
| **Claude Code MAX** | Opus 4.5 subscription (required for multi-agent orchestration) |
| **Python** | 3.11 or higher |
| **SQLite** | 3.x (included in repository) |
| **Disk Space** | 500MB minimum (300MB database + code/docs) |
| **Memory** | 4GB RAM recommended for optimal performance |

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EROS_DB_PATH` | Database file location | `./database/eros_sd_main.db` |

### Setup

1. Ensure Claude Code MAX subscription is active
2. Verify Python 3.11+ is installed: `python3 --version`
3. Configure MCP permissions in `.claude/settings.local.json` (33 tools enabled)
4. Database is ready to use (no migration required for clean install)

## Version History

### v3.0.0 (Current - December 2025)

**Major Architecture Changes**:
- Expanded agent count from 22 to **24 specialized agents**
- Expanded MCP tools from 18 to **33 database tools**
- Added **Four-Layer Defense** system for caption validation (vault compliance + AVOID tier exclusion)
- Removed audience targeting system (now manual in OnlyFans platform)

**New Agents**:
- `quality-validator-expert` (Opus) - Expert consensus validation (Phase 9 parallel)
- `outcome-tracker` (Haiku) - Track and analyze schedule outcomes 7 days post-deployment

**New MCP Tool Categories**:
- **Prediction & ML** (5 tools): Caption performance predictions with feedback loops
- **Churn & Win-Back** (2 tools): Churn risk scoring and win-back candidate identification
- **Attention Scoring** (2 tools): Caption attention metrics and quality scoring
- **A/B Experiments** (3 tools): Experiment management and results tracking
- **Earnings-Based Selection** (2 tools): Content type earnings ranking and top captions by earnings
- **Caption Validation** (1 tool): Structure validation for caption compliance

**Enhanced Features**:
- **Bump Multiplier Algorithm** (v3.0): Content category-based engagement scaling (1.0x-2.67x)
- **Followup Scaling** (v3.0): PPV-proportional followup calculation (80% rate)
- **Volume Triggers**: Automated performance-based adjustments (HIGH_PERFORMER, TRENDING_UP, SATURATING, AUDIENCE_FATIGUE)
- **Multi-Horizon Fusion**: 7d/14d/30d saturation/opportunity analysis in volume optimization

**Documentation**:
- Comprehensive documentation sync and version alignment across all files
- ORCHESTRATION.md expanded to 5,333 lines covering all 14 phases
- Complete audit and cleanup of outdated references
- Added REFERENCE/ directory with canonical quick references

### v2.3.0 (November 2025)
- Removed audience targeting system completely
- Updated all documentation to reflect manual targeting workflow
- Schema migrations to archive targeting tables
- Performance optimizations in volume optimization module

### v2.2.0 (October 2025)
- Version consistency standardization across all files
- Enhanced send type system with 22 types
- Comprehensive API documentation
- Improved caption selection with priority ordering
- Volume configuration with category breakdowns

### v2.0.0 (September 2025)
- Multi-agent architecture implementation
- MCP database integration (initial 16 tools)
- Performance-driven content selection
- Four-tier content ranking system (TOP/MID/LOW/AVOID)

## License

Proprietary - EROS Development Team
All rights reserved.

## Support

For issues, questions, or feature requests:

1. Check the [User Guide](docs/USER_GUIDE.md) troubleshooting section
2. Review the [API Reference](docs/API_REFERENCE.md)
3. Consult the [Architecture Blueprint](docs/SCHEDULE_GENERATOR_BLUEPRINT.md)

## Contributing

This is a proprietary system. Contributions are managed internally by the EROS Development Team.

---

<div align="center">

**Built with Claude Code MAX** | **Powered by Anthropic Opus 4.5** | **Version 3.0.0**

*24 Specialized Agents • 14 Pipeline Phases • 33 MCP Tools • 59,405 Captions*

</div>
