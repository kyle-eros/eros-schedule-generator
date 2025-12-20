# EROS Schedule Generator

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Claude Code](https://img.shields.io/badge/claude--code-2025-purple)
![Status](https://img.shields.io/badge/status-production-brightgreen)

AI-powered multi-agent schedule generation system for OnlyFans creators using a 22-type send taxonomy. The system orchestrates 22 specialized agents across 14 phases to produce optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention.

## Overview

EROS (Engagement and Revenue Optimization System) is an intelligent scheduling platform that analyzes historical performance data from 71,998+ mass messages across 37 active creators to generate data-driven weekly content schedules. The system leverages machine learning, persona matching, and timing optimization to maximize creator revenue while maintaining authentic audience engagement.

## Key Features

- **22 Specialized AI Agents Working in Concert** - Multi-agent pipeline with performance analysis, content curation, timing optimization, authenticity engine, and quality validation
- **22 Distinct Send Types Across 3 Categories** - Revenue (9 types), Engagement (9 types), Retention (4 types)
- **Anti-AI Humanization** - Authenticity engine ensures captions pass platform AI detection while maintaining persona consistency
- **ML-Optimized Timing Recommendations** - Historical analysis of 71,998+ messages to identify peak engagement windows
- **Performance-Driven Content Selection** - TOP/MID/LOW/AVOID rankings with freshness scoring to prevent caption fatigue
- **Automated PPV Followup Generation** - Smart followup sequences with configurable delays
- **Multi-Format Export** - CSV, JSON, and markdown output for seamless integration

## Quick Start

### Prerequisites

- Claude Code MAX subscription
- Python 3.11+
- SQLite database (included: 250MB, 85 tables)

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

**Pre-Pipeline Validation (Phase 0-0.5)**
- Phase 0: **Preflight Check** - Validate creator readiness
- Phase 0.5: **Retention Risk Analysis** - Churn analysis and retention recommendations

**Core Pipeline (Phase 1-9.5)**
- Phase 1: **Performance Analysis** - Saturation/opportunity scoring
- Phase 2: **Send Type Allocation** - Category-based distribution
- Phase 2.5: **Variety Enforcement** - Content diversity enforcement
- Phase 2.75: **Performance Prediction** - ML-style predictions
- Phase 3: **Content Curation** - Caption selection with freshness scoring
- Phase 4: **Timing Optimization** - Optimal posting windows
- Phase 5: **Followup Generation** - Auto-generate PPV followups
- Phase 5.5: **Followup Timing** - Dynamic followup delays
- Phase 6: **Authenticity Engine** - Anti-AI humanization
- Phase 7: **Schedule Assembly** - Final schedule structure creation
- Phase 7.5: **Funnel Flow** - Engagement-to-conversion optimization
- Phase 8: **Revenue Optimization** - Pricing and positioning
- Phase 8.5: **Price & Review** - PPV pricing + schedule critic
- Phase 9: **Quality Validation** - FINAL GATE with vault compliance
- Phase 9.5: **Anomaly Detection** - Statistical anomaly detection

### 22 Specialized Agents

| Agent | Model | Phase | Responsibility |
|-------|-------|-------|----------------|
| preflight-checker | Haiku | 0 | Validate creator readiness (BLOCK) |
| retention-risk-analyzer | Opus | 0.5 | Churn analysis |
| performance-analyst | Sonnet | 1 | Volume calibration |
| send-type-allocator | Haiku | 2 | Daily distribution |
| variety-enforcer | Sonnet | 2.5 | Diversity enforcement |
| content-performance-predictor | Opus | 2.75 | ML predictions |
| caption-selection-pro | Sonnet | 3 | Caption selection (VAULT GATE) |
| attention-quality-scorer | Sonnet | 3 | Attention scoring (parallel) |
| timing-optimizer | Haiku | 4 | Posting times |
| followup-generator | Haiku | 5 | PPV followups |
| followup-timing-optimizer | Haiku | 5.5 | Followup timing |
| authenticity-engine | Sonnet | 6 | Anti-AI humanization |
| schedule-assembler | Haiku | 7 | Schedule assembly |
| funnel-flow-optimizer | Sonnet | 7.5 | Funnel optimization |
| revenue-optimizer | Sonnet | 8 | Revenue optimization |
| ppv-price-optimizer | Opus | 8.5 | Dynamic PPV pricing |
| schedule-critic | Opus | 8.5 | Strategic review (BLOCK) |
| quality-validator | Sonnet | 9 | FINAL GATE validation |
| anomaly-detector | Haiku | 9.5 | Anomaly detection |
| ab-testing-orchestrator | Opus | Parallel | A/B experiments |
| win-back-specialist | Sonnet | Async | Win-back campaigns |
| caption-optimizer | Sonnet | Utility | On-demand optimization |

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Step-by-step onboarding guide |
| [User Guide](docs/USER_GUIDE.md) | Comprehensive user documentation |
| [API Reference](docs/API_REFERENCE.md) | Complete MCP tool documentation (18 tools) |
| [Send Type Reference](docs/SEND_TYPE_REFERENCE.md) | All 22 send types with examples |
| [Architecture Blueprint](docs/SCHEDULE_GENERATOR_BLUEPRINT.md) | System design and technical details |
| [Enhanced Send Type System](docs/ENHANCED_SEND_TYPE_ARCHITECTURE.md) | v2.0 send type implementation |

## Project Structure

```
EROS-SD-MAIN-PROJECT/
├── .claude/
│   ├── skills/eros-schedule-generator/    # Main skill entry point
│   └── agents/                             # 22 specialized agent definitions
├── mcp/
│   └── eros_db_server.py                   # MCP server (18 database tools)
├── python/
│   ├── analytics/                          # Performance scoring algorithms
│   ├── caption/                            # Caption selection logic
│   └── orchestration/                      # Batch processing
├── database/
│   └── eros_sd_main.db                     # Production SQLite (250MB)
├── docs/                                   # Comprehensive documentation
└── README.md                               # This file
```

## Database

**Size**: 250MB
**Tables**: 85 (37 active)
**Creators**: 37 active
**Captions**: 58,763
**Mass Messages**: 71,998
**Quality Score**: 93/100

### Key Tables

- `creators` - Creator profiles with performance tiers
- `caption_bank` - 58,763 captions with performance scores
- `send_types` - 22 send type configurations
- `mass_messages` - Historical performance data
- `volume_performance_tracking` - Saturation/opportunity metrics
- `top_content_types` - Content rankings (TOP/MID/LOW/AVOID)

## Technology Stack

- **Runtime**: Claude Code MAX (Sonnet 4.5)
- **Database**: SQLite 3
- **MCP**: Model Context Protocol for database integration
- **Python**: 3.11+ for core algorithms
- **Export Formats**: CSV, JSON, Markdown

## Requirements

### System Requirements

- Claude Code MAX subscription (required for multi-agent orchestration)
- Python 3.11 or higher
- SQLite 3 (included)
- 300MB disk space

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EROS_DB_PATH` | Database file location | `./database/eros_sd_main.db` |

## Version History

### v3.0.0 (Current)
- Removed audience targeting system (manual in OnlyFans platform)
- Added authenticity-engine agent (Phase 6) for anti-AI humanization
- Added revenue-optimizer agent (Phase 8) for pricing optimization
- Expanded pipeline to 14 phases with 22 specialized agents
- Consolidated from 17 to 16 MCP tools
- Documentation sync and version alignment

### v2.2.0
- Version consistency standardization across all files
- Enhanced send type system with 22 types
- Comprehensive API documentation
- Improved caption selection with priority ordering
- Volume configuration with category breakdowns

### v2.0.0
- Multi-agent architecture
- MCP database integration
- 16 database tools
- Performance-driven content selection

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

**Built with Claude Code MAX** | **Powered by Anthropic Sonnet 4.5** | **Version 3.0.0**
