# EROS Schedule Generator

## Project Overview

AI-powered multi-agent schedule generation system for OnlyFans creators using a 22-type send taxonomy. The system orchestrates **24 specialized agents across 14 phases** to produce optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention.

**Version**: 3.0.0
**Database**: SQLite (119MB, 63 tables, 37 active creators)
**Architecture**: Multi-agent pipeline with MCP database integration (37 tools)

## Quick Start

```
# Generate schedule for a creator
"Generate a schedule for alexia"

# Generate with specific focus
"Generate a revenue-focused schedule for creator_123 starting 2025-12-16"

# Analyze performance before scheduling
"Analyze performance trends for alexia"
```

## Key Files

| Location | Purpose |
|----------|---------|
| `.claude/skills/eros-schedule-generator/SKILL.md` | Main skill entry point |
| `.claude/skills/eros-schedule-generator/ORCHESTRATION.md` | 14-phase pipeline documentation |
| `.claude/agents/` | 24 specialized agent definitions |
| `mcp/eros_db_server.py` | MCP database server (33 tools) |
| `python/` | Core Python algorithms |
| `database/eros_sd_main.db` | Production SQLite database |
| `docs/` | Comprehensive documentation (240KB+) |

## Directory Structure

```
EROS-SD-MAIN-PROJECT/
├── .claude/
│   ├── agents/                  # 24 specialized agent definitions
│   │   ├── preflight-checker.md       # Phase 0 - Validate creator readiness
│   │   ├── retention-risk-analyzer.md # Phase 0.5 - Churn analysis
│   │   ├── performance-analyst.md     # Phase 1 - Saturation/opportunity
│   │   ├── send-type-allocator.md     # Phase 2 - Daily distribution
│   │   ├── variety-enforcer.md        # Phase 2.5 - Diversity enforcement
│   │   ├── content-performance-predictor.md # Phase 2.75 - ML predictions
│   │   ├── caption-selection-pro.md   # Phase 3 - PPV-first selection
│   │   ├── attention-quality-scorer.md # Phase 3 (parallel)
│   │   ├── timing-optimizer.md        # Phase 4 - Optimal posting times
│   │   ├── followup-generator.md      # Phase 5 - Auto-generate followups
│   │   ├── followup-timing-optimizer.md # Phase 5.5 - Followup timing
│   │   ├── authenticity-engine.md     # Phase 6 - Anti-AI humanization
│   │   ├── schedule-assembler.md      # Phase 7 - Final assembly
│   │   ├── funnel-flow-optimizer.md   # Phase 7.5 - Funnel optimization
│   │   ├── revenue-optimizer.md       # Phase 8 - Pricing optimization
│   │   ├── ppv-price-optimizer.md     # Phase 8.5 - Dynamic PPV pricing
│   │   ├── schedule-critic.md         # Phase 8.5 - BLOCK authority
│   │   ├── quality-validator.md       # Phase 9 - FINAL GATE
│   │   ├── quality-validator-expert.md # Phase 9 - EXPERT consensus (parallel)
│   │   ├── anomaly-detector.md        # Phase 9.5 - Statistical detection
│   │   ├── ab-testing-orchestrator.md # Parallel - A/B experiments
│   │   ├── win-back-specialist.md     # Async - Win-back campaigns
│   │   └── caption-optimizer.md       # Utility - On-demand optimization
│   ├── commands/eros/           # Slash commands
│   │   ├── generate.md
│   │   ├── analyze.md
│   │   ├── validate.md
│   │   └── creators.md
│   ├── settings.local.json      # MCP permissions (37 tools)
│   └── skills/
│       └── eros-schedule-generator/
│           ├── SKILL.md              # Entry point (489 lines)
│           ├── ORCHESTRATION.md      # 14-phase pipeline (5,331 lines)
│           ├── DATA_CONTRACTS.md     # Agent I/O contracts (2,253 lines)
│           ├── HELPERS.md            # Utility functions (2,306 lines)
│           ├── ALLOCATION_ALGORITHM.md
│           ├── ALLOCATION_RULES.md
│           ├── OPTIMIZATION_WEIGHTS.md
│           ├── MATCHING_HEURISTICS.md
│           ├── FOLLOWUP_PATTERNS.md
│           └── REFERENCE/            # Canonical quick references
│               ├── SEND_TYPE_TAXONOMY.md
│               ├── VALIDATION_RULES.md
│               ├── CONFIDENCE_LEVELS.md
│               ├── TOOL_PATTERNS.md
│               └── CAPTION_SCORING_RULES.md
├── database/
│   ├── eros_sd_main.db          # Production SQLite (119MB, 63 tables)
│   ├── archive/                 # Archived tables (90-day retention)
│   ├── migrations/              # Schema migrations (018+)
│   ├── docs/                    # Database documentation
│   └── scripts/                 # Utility scripts (vault_matrix_sync.py)
├── docs/                        # User-facing documentation
│   ├── USER_GUIDE.md
│   ├── SCHEDULE_GENERATOR_BLUEPRINT.md
│   ├── SEND_TYPE_REFERENCE.md
│   ├── MCP_API_REFERENCE.md
│   └── GLOSSARY.md
├── mcp/
│   ├── server.py                # MCP server entry point
│   └── tools/                   # 33 MCP tool implementations
│       ├── caption.py           # 6 caption tools
│       ├── creator.py           # 3 creator tools
│       ├── performance.py       # 4 performance tools
│       ├── prediction.py        # 5 prediction tools
│       ├── churn.py             # 2 churn tools
│       ├── experiments.py       # 3 experiment tools
│       ├── volume_triggers.py   # 2 trigger tools
│       ├── send_types.py        # 3 send type tools
│       ├── schedule.py          # 1 schedule tool
│       └── query.py             # 1 query tool
└── python/                      # Core Python algorithms
    ├── volume/                  # Volume optimization
    ├── orchestration/           # Pipeline orchestration
    ├── config/                  # Configuration files
    └── ...
```

## Agent Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRE-PIPELINE VALIDATION                          │
│  ┌─────────────────┐      ┌─────────────────────────┐               │
│  │ preflight-      │ ──►  │ retention-risk-         │               │
│  │ checker (haiku) │      │ analyzer (opus)         │               │
│  │ [BLOCK if fail] │      │ [churn analysis]        │               │
│  └─────────────────┘      └─────────────────────────┘               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                         CORE PIPELINE                                │
│                                                                      │
│  Phase 1-2: ANALYSIS & ALLOCATION                                   │
│  ┌───────────────────┐    ┌─────────────────────┐                   │
│  │ performance-      │ ─► │ send-type-          │                   │
│  │ analyst (opus)    │    │ allocator (sonnet)  │                   │
│  └───────────────────┘    └──────────┬──────────┘                   │
│                                      │                               │
│  Phase 2.5-3: DIVERSITY & SELECTION  │                               │
│  ┌───────────────────┐    ┌──────────▼──────────┐                   │
│  │ variety-enforcer  │ ◄─ │ content-performance │                   │
│  │ (sonnet)          │    │ -predictor (opus)   │                   │
│  └─────────┬─────────┘    └─────────────────────┘                   │
│            │                                                         │
│            ▼                                                         │
│  ┌───────────────────┐    ┌─────────────────────┐                   │
│  │ caption-selection │ ◄──┤ attention-quality-  │ [PARALLEL]        │
│  │ -pro (sonnet)     │    │ scorer (sonnet)     │                   │
│  │ [VAULT GATE]      │    └─────────────────────┘                   │
│  └─────────┬─────────┘                                               │
│            │                                                         │
│  Phase 4-5.5: TIMING & FOLLOWUPS                                    │
│            ▼                                                         │
│  ┌───────────────────┐    ┌─────────────────────┐                   │
│  │ timing-optimizer  │ ─► │ followup-generator  │                   │
│  │ (sonnet)          │    │ (haiku)             │                   │
│  └───────────────────┘    └──────────┬──────────┘                   │
│                                      │                               │
│  ┌───────────────────┐    ┌──────────▼──────────┐                   │
│  │ followup-timing-  │ ◄─ │                     │                   │
│  │ optimizer (haiku) │    │                     │                   │
│  └─────────┬─────────┘    └─────────────────────┘                   │
│            │                                                         │
│  Phase 6-7.5: ASSEMBLY & FUNNEL                                     │
│            ▼                                                         │
│  ┌───────────────────┐    ┌─────────────────────┐                   │
│  │ authenticity-     │ ─► │ schedule-assembler  │                   │
│  │ engine (sonnet)   │    │ (haiku)             │                   │
│  │ [NO CAPTION MODS] │    └──────────┬──────────┘                   │
│  └───────────────────┘               │                               │
│                           ┌──────────▼──────────┐                   │
│                           │ funnel-flow-        │                   │
│                           │ optimizer (sonnet)  │                   │
│                           └──────────┬──────────┘                   │
│                                      │                               │
│  Phase 8-8.5: REVENUE & REVIEW       │                               │
│            ┌─────────────────────────▼─────────────────────┐        │
│            │ ┌───────────────────┐ ┌─────────────────────┐ │        │
│            │ │ revenue-optimizer │ │ ppv-price-optimizer │ │        │
│            │ │ (sonnet)          │ │ (opus)              │ │        │
│            │ └─────────┬─────────┘ └──────────┬──────────┘ │        │
│            │           │                      │            │        │
│            │           └──────────┬───────────┘            │        │
│            │                      ▼                        │        │
│            │            ┌─────────────────────┐            │        │
│            │            │ schedule-critic     │            │        │
│            │            │ (opus) [BLOCK]      │            │        │
│            │            └──────────┬──────────┘            │        │
│            └───────────────────────┼───────────────────────┘        │
│                                    │                                 │
│  Phase 9-9.5: VALIDATION           │                                 │
│            ┌───────────────────────▼───────────────────────┐        │
│            │ ┌─────────────────────┐ ┌───────────────────┐ │        │
│            │ │ quality-validator   │ │ anomaly-detector  │ │        │
│            │ │ (opus) [FINAL]      │►│ (haiku)           │ │        │
│            │ └─────────────────────┘ └─────────┬─────────┘ │        │
│            └───────────────────────────────────┼───────────┘        │
│                                                │                     │
└────────────────────────────────────────────────┼─────────────────────┘
                                                 │
                                    ┌────────────▼────────────┐
                                    │     save_schedule       │
                                    │  [ValidationCertificate]│
                                    └─────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    PARALLEL / ASYNC AGENTS                           │
│  ┌─────────────────────┐  ┌─────────────────────┐                   │
│  │ ab-testing-         │  │ win-back-specialist │                   │
│  │ orchestrator (opus) │  │ (sonnet) [ASYNC]    │                   │
│  │ [PARALLEL]          │  │                     │                   │
│  └─────────────────────┘  └─────────────────────┘                   │
│                                                                      │
│  ┌─────────────────────┐                                            │
│  │ caption-optimizer   │  [ON-DEMAND UTILITY]                       │
│  │ (sonnet)            │                                            │
│  └─────────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**BLOCKING Agents** (Can halt pipeline execution):
- `preflight-checker` (Phase 0): Creator data missing or invalid
- `schedule-critic` (Phase 8.5): Strategic issues detected
- `quality-validator` (Phase 9): Vault or AVOID tier violations

### Agent Model Distribution

| Model | Count | Agents |
|-------|-------|--------|
| **Haiku** | 6 | preflight-checker, followup-generator, followup-timing-optimizer, schedule-assembler, anomaly-detector, outcome-tracker |
| **Sonnet** | 10 | send-type-allocator, timing-optimizer, variety-enforcer, caption-selection-pro, attention-quality-scorer, authenticity-engine, funnel-flow-optimizer, revenue-optimizer, win-back-specialist, caption-optimizer |
| **Opus** | 8 | performance-analyst, quality-validator, retention-risk-analyzer, content-performance-predictor, ppv-price-optimizer, schedule-critic, ab-testing-orchestrator, quality-validator-expert |

**Model Selection Rationale**:
- **Haiku**: Fast, lightweight agents for simple validation, allocation, and assembly tasks
- **Sonnet**: Complex logic agents for optimization, selection, and validation with reasoning
- **Opus**: Strategic agents requiring deep analysis (predictions, critique, A/B testing)

## Troubleshooting Guide

### Common Issues and Solutions

| Issue | Symptom | Cause | Solution |
|-------|---------|-------|----------|
| Creator not found | `PREFLIGHT_BLOCK` error | Invalid `creator_id` | Run `get_active_creators()` to list valid IDs |
| Schedule rejected | `quality_score < 70` | Vault or AVOID violations | Check `get_vault_availability()` and `get_content_type_rankings()` |
| No captions available | `caption_coverage_rate < 50%` | Freshness threshold too strict | Relax `min_freshness` from 30 to 20 days |
| Low quality score | Multiple soft warnings | Caption repetition, timing clusters | Review `quality_validator` output for specific warnings |
| BLOCK at preflight | Missing data alert | No vault_matrix entries | Add vault entries via `vault_matrix_sync.py` |
| Confidence < 0.4 | `VERY_LOW_CONFIDENCE` flag | Insufficient historical data | System applies conservative volumes automatically |
| Timing conflicts | `spacing_violations > 0` | Items scheduled too close | Increase minimum hours between same send types |
| AVOID tier violation | Schedule rejected | Content type in AVOID tier | Check rankings, exclude AVOID types from selection |

### Diagnostic Commands

```bash
# Check creator exists and has data
get_creator_profile(creator_id="your_creator")

# Verify vault matrix has entries
get_vault_availability(creator_id="your_creator")

# Check content type rankings for AVOID tier
get_content_type_rankings(creator_id="your_creator")

# Verify caption pool has fresh captions
get_top_captions(creator_id="your_creator", min_freshness=20)

# Check active volume triggers
get_active_volume_triggers(creator_id="your_creator")
```

### Error Codes Quick Reference

| Code | Agent | Severity | Action |
|------|-------|----------|--------|
| `PREFLIGHT_BLOCK` | preflight-checker | CRITICAL | Fix creator data, re-run |
| `VAULT_VIOLATION` | caption-selection-pro | CRITICAL | Select different caption |
| `AVOID_TIER_VIOLATION` | quality-validator | CRITICAL | Exclude content type |
| `DIVERSITY_FAILED` | variety-enforcer | HIGH | Expand send type variety |
| `CRITIC_BLOCK` | schedule-critic | HIGH | Manual review required |
| `LOW_CONFIDENCE` | performance-analyst | MEDIUM | Conservative volumes applied |
| `ANOMALY_DETECTED` | anomaly-detector | WARNING | Review flagged items |
| `MCP_CONNECTION_FAILED` | skill entry | CRITICAL | Enable eros-db MCP server |
| `MCP_TOOLS_UNAVAILABLE` | skill entry | CRITICAL | Check MCP server health |

### Database Schema Quick Reference

When writing custom queries via `execute_query()`, use these CORRECT column names:

| Table | WRONG Column | CORRECT Column | Notes |
|-------|--------------|----------------|-------|
| `content_categories` | `category_name` | `display_name` | Category display text |
| `content_types` | `content_type_name` | `type_name` | Content type name |
| `send_types` | `send_type_name` | `display_name` | Send type display text |
| `creator_personas` | `tone` | `primary_tone`, `secondary_tone` | Two separate columns |
| `top_content_types` | `content_type_id` | `content_type` (TEXT) | Stores name directly, not FK |
| `vault_matrix` | `content_type` (direct) | `content_type_id` (FK) | Must JOIN to content_types |
| `v_wall_post_best_hours` | `hour_of_day` | `posting_hour` | Hour 0-23 |
| `volume_assignments` | `weekly_ppv_cap` | N/A | Column does not exist |

**IMPORTANT**:
- Table `content_type_rankings` does NOT exist. Use `top_content_types` instead.
- Weekly caps are calculated dynamically by `get_volume_config()`, not stored in `volume_assignments`.
- Always prefer MCP tools over raw SQL to avoid schema mismatches.

See: `.claude/skills/eros-schedule-generator/REFERENCE/DATABASE_SCHEMA.md` for complete reference.

## Error Handling

### Agent Error Response Format

All agents return errors in standardized format:
```json
{
  "error": true,
  "error_code": "ERROR_CODE",
  "error_message": "Human-readable description",
  "agent": "agent-name",
  "phase": 1.0,
  "timestamp": "2025-12-20T10:00:00Z",
  "recoverable": true,
  "fallback_action": "description of fallback if available"
}
```

### Severity Levels and Propagation

| Severity | Pipeline Action | Examples |
|----------|-----------------|----------|
| CRITICAL | Abort immediately | DB connection failure, creator not found, vault violation |
| HIGH | Retry once, then abort | Zero captions available, all vault entries missing |
| MEDIUM | Apply fallback, continue | Caption freshness low, timing partial failure |
| LOW | Log and continue | Persona data missing, best timing incomplete |

### BLOCK vs WARN Authority by Agent

| Agent | Can BLOCK | Can WARN | Has Fallback |
|-------|-----------|----------|--------------|
| preflight-checker | YES | YES | NO |
| schedule-critic | YES | YES | YES (manual override) |
| quality-validator | YES | YES | NO |
| variety-enforcer | NO | YES | YES (relax thresholds) |
| caption-selection-pro | NO | YES | YES (fallback hierarchy) |
| timing-optimizer | NO | YES | YES (default hours) |

**Key Principle**: Hard gates (Vault, AVOID) NEVER degrade - they always REJECT.

## 24 Specialized Agents

### Pre-Pipeline Validation (Phase 0-0.5)
1. **preflight-checker** (haiku) - Verify creator readiness, BLOCK if data missing
2. **retention-risk-analyzer** (opus) - Churn risk analysis and retention recommendations

### Core Pipeline (Phase 1-9.5)
3. **performance-analyst** (opus) - Saturation/opportunity analysis, volume triggers
4. **send-type-allocator** (sonnet) - Daily send type distribution with DOW multipliers
5. **variety-enforcer** (sonnet) - Content diversity enforcement (12+ unique types)
6. **content-performance-predictor** (opus) - ML-style RPS/conversion predictions
7. **caption-selection-pro** (sonnet) - EXPERT caption selection with vault compliance, AVOID tier exclusion, earnings-based rotation
8. **timing-optimizer** (sonnet) - Optimal posting time calculation with jitter
9. **followup-generator** (haiku) - Auto-generate PPV followups (80% rate)
10. **followup-timing-optimizer** (haiku) - Dynamic followup delay optimization
11. **authenticity-engine** (sonnet) - Validate structure for organic variation
12. **schedule-assembler** (haiku) - Final schedule structure assembly
13. **funnel-flow-optimizer** (sonnet) - Engagement-to-conversion flow optimization
14. **revenue-optimizer** (sonnet) - Price/positioning optimization with tier multipliers
15. **ppv-price-optimizer** (opus) - Dynamic PPV pricing using predictions
16. **schedule-critic** (opus) - Strategic review with BLOCK authority
17. **quality-validator** (opus) - FINAL GATE with Four-Layer Defense
18. **anomaly-detector** (haiku) - Statistical anomaly detection before save

### Parallel/Async Agents
19. **ab-testing-orchestrator** (opus) - A/B experiment management (parallel)
20. **win-back-specialist** (sonnet) - Win-back campaign generation (async)
21. **attention-quality-scorer** (sonnet) - Caption attention scoring (parallel)
22. **quality-validator-expert** (opus) - EXPERT consensus validation (parallel with quality-validator)
23. **outcome-tracker** (haiku) - Track and analyze schedule outcomes
24. **caption-optimizer** (sonnet) - On-demand caption optimization (utility)

## MCP Tools Available

All database operations use the `eros-db` MCP server (37 tools):

### Creator Data (3 tools)
- **`get_creator_profile`** - Comprehensive creator data including analytics, persona, top content types, and volume configuration
- **`get_active_creators`** - List all active creators with performance metrics and tier classification
- **`get_persona_profile`** - Creator tone, archetype, emoji style, slang level, and voice samples

### Performance & Analytics (3 tools)
- **`get_performance_trends`** - Saturation/opportunity scores with multi-horizon analysis (7d/14d/30d)
- **`get_content_type_rankings`** - TOP/MID/LOW/AVOID classifications based on performance tiers
- **`get_best_timing`** - Optimal posting times by hour and day from historical performance

### Content & Captions (3 tools)
- **`get_top_captions`** - Performance-ranked captions with freshness scoring and send type compatibility
- **`get_send_type_captions`** - Captions compatible with specific send types via caption type mappings
- **`get_vault_availability`** - Available content types in creator's vault inventory

### Send Type Configuration (3 tools)
- **`get_send_types`** - Full 22-type taxonomy filtered by category and page type
- **`get_send_type_details`** - Complete configuration for single send type including timing rules and constraints
- **`get_volume_config`** - **[CRITICAL]** Optimized volume configuration with full `OptimizedVolumeResult`:
  - Legacy fields: `volume_level`, `ppv_per_day`, `bump_per_day` (backward compatible)
  - Category volumes: `revenue_per_day`, `engagement_per_day`, `retention_per_day`
  - Weekly distribution: `weekly_distribution` (DOW-adjusted, day 0-6 mapping)
  - Content strategy: `content_allocations` (performance-weighted by content type)
  - Optimization metadata: `confidence_score`, `elasticity_capped`, `caption_warnings`
  - Multi-horizon fusion: `fused_saturation`, `fused_opportunity`, `divergence_detected`
  - DOW multipliers: `dow_multipliers_used` (per-day adjustment factors)
  - Tracking: `prediction_id`, `message_count`, `adjustments_applied` (audit trail)
  - **[v3.0 NEW]** Bump optimization: `bump_multiplier`, `bump_adjusted_engagement`, `content_category`, `bump_capped`
  - **[v3.0 NEW]** Followup scaling: `followup_volume_scaled`, `followup_rate_used`
  - 10 integrated modules: Base Tier, Multi-Horizon Fusion, Confidence Dampening, DOW Distribution, Elasticity Bounds, Content Weighting, Caption Pool Check, Prediction Tracking, Bump Multiplier, Followup Scaling

### Channels (1 tool)
- **`get_channels`** - Distribution channels (wall_post, mass_message, story, live)

### Schedule Operations (2 tools)
- **`save_schedule`** - Persist generated schedule to database with send types and channels
- **`execute_query`** - Execute read-only SQL queries for custom analysis and diagnostics

### Volume Triggers (2 tools)
- **`save_volume_triggers`** - Save performance-detected triggers that adjust content type allocations
  - Deactivates existing active triggers before inserting new ones
  - Supports trigger types: `HIGH_PERFORMER`, `TRENDING_UP`, `EMERGING_WINNER`, `SATURATING`, `AUDIENCE_FATIGUE`
  - Parameters: `creator_id`, `triggers[]` (content_type, trigger_type, adjustment_multiplier, reason, confidence, expires_at)
- **`get_active_volume_triggers`** - Retrieve active, non-expired triggers for a creator
  - Automatically filters expired triggers (`expires_at > datetime('now')`)
  - Returns trigger metadata including applied_count for tracking

### Prediction & ML (5 tools) [NEW v3.0]
- **`get_caption_predictions`** - ML-style predictions for caption performance (RPS, open rate, conversion)
- **`save_caption_prediction`** - Save prediction for outcome tracking
- **`record_prediction_outcome`** - Record actual performance for learning
- **`get_prediction_weights`** - Get current feature weights for prediction model
- **`update_prediction_weights`** - Update weights based on outcomes

### Churn & Win-Back (2 tools) [NEW v3.0]
- **`get_churn_risk_scores`** - Churn risk by subscriber segment (LOW/MODERATE/HIGH/CRITICAL)
- **`get_win_back_candidates`** - Eligible subscribers for win-back campaigns

### Attention Scoring (2 tools) [NEW v3.0]
- **`get_attention_metrics`** - Raw attention engagement metrics (hook, depth, CTA, emotion)
- **`get_caption_attention_scores`** - Pre-computed attention scores with quality tiers

### A/B Experiments (3 tools) [NEW v3.0]
- **`get_active_experiments`** - Active A/B experiments for creator
- **`save_experiment_results`** - Save experiment outcome metrics
- **`update_experiment_allocation`** - Update traffic allocation or status

### Tool Count Verification
- Creator Data: 3 tools
- Performance & Analytics: 3 tools
- Content & Captions: 3 tools
- Send Type Configuration: 3 tools
- Channels: 1 tool
- Schedule Operations: 2 tools
- Volume Triggers: 2 tools
- Prediction & ML: 5 tools [NEW]
- Churn & Win-Back: 2 tools [NEW]
- Attention Scoring: 2 tools [NEW]
- A/B Experiments: 3 tools [NEW]
- Caption Validation: 1 tool [NEW]
- Earnings-Based Selection: 2 tools [NEW]
- Deprecated (still functional): 1 tool (`get_volume_assignment`)

**Total: 37 tools**

**Note**: Tool count increased from 33 to 37 in v3.0 with additions:
- Caption Validation: validate_caption_structure (1 tool)
- Earnings-Based Selection: get_content_type_earnings_ranking, get_top_captions_by_earnings (2 tools)
- Attention Scoring: get_attention_metrics, get_caption_attention_scores (2 tools)

**Deprecation Notice**: `get_volume_assignment` remains available for backward compatibility but returns a deprecation warning. New implementations should use `get_volume_config()` which provides dynamic calculation with full `OptimizedVolumeResult` metadata instead of static assignments.

## Volume Optimization v3.0

The Volume Optimization system dynamically calculates optimal send volumes using performance data, creator characteristics, and multi-horizon analysis. Version 3.0 introduces content category-based bump multipliers and intelligent followup scaling.

### Bump Multiplier Algorithm

Content categories determine engagement multipliers based on content aesthetic and audience engagement patterns:

| Content Category | Multiplier | Rationale |
|------------------|------------|-----------|
| **lifestyle** | 1.0x | GFE content, personal connection, conversational engagement |
| **softcore** | 1.5x | Suggestive content, teasing aesthetic, moderate engagement |
| **amateur** | 2.0x | Authentic aesthetic, high engagement, community building |
| **explicit** | 2.67x | Commercial explicit content, maximum engagement potential |

**Tier Capping Logic**:
- **LOW tier**: Full multiplier applied (no cap)
- **MID/TOP tiers**: Multiplier capped at 1.5x to prevent over-saturation

**Example Calculation**:
```
Base engagement (LOW tier, amateur): 6 bumps/day
Multiplier: 2.0x (amateur category)
Adjusted: 6 * 2.0 = 12 bumps/day (no cap for LOW tier)

Base engagement (TOP tier, explicit): 4 bumps/day
Multiplier: 2.67x (explicit category)
Pre-cap: 4 * 2.67 = 10.68 bumps/day
Final: min(10.68, 4 * 1.5) = 6 bumps/day (capped at 1.5x)
```

**Database Schema**:
- `creators.content_category` - Creator's content category (FK to content_categories)
- `content_categories` table - Category definitions with multipliers and descriptions

### Followup Scaling Formula

PPV followups scale proportionally to PPV volume with intelligent capping:

```
followups = round(ppv_count * 0.80)  # 80% of PPVs get followups
followups = min(followups, tier_max, 5)  # Hard cap at 5/day
```

**Scaling Logic**:
- **Rate**: 80% of PPVs receive followup sends
- **Tier cap**: Respects tier-based maximum (varies by performance tier)
- **Hard cap**: Never exceeds 5 followups/day (system limit)

**Example**:
```
LOW tier creator with 4 PPVs:
  - Calculated: round(4 * 0.80) = 3 followups
  - Tier max: 5 (LOW tier limit)
  - Hard cap: 5 (system limit)
  - Final: min(3, 5, 5) = 3 followups/day

MID tier creator with 5 PPVs:
  - Calculated: round(5 * 0.80) = 4 followups
  - Tier max: 4 (MID tier limit)
  - Hard cap: 5 (system limit)
  - Final: min(4, 4, 5) = 4 followups/day
```

**Output Fields**:
- `followup_volume_scaled`: Final followup count after scaling
- `followup_rate_used`: Actual rate applied (0.80)
- `retention_per_day`: Includes followups + other retention sends

### Volume Triggers

Performance-based triggers automatically adjust content type allocations when specific patterns are detected.

**Trigger Types**:

| Trigger Type | Detection Criteria | Adjustment | Use Case |
|--------------|-------------------|------------|----------|
| **HIGH_PERFORMER** | RPS > $200, conversion > 6% | +20% | Proven winners deserve more volume |
| **TRENDING_UP** | WoW RPS increase > 15% | +10% | Capitalize on momentum |
| **EMERGING_WINNER** | RPS > $150, used < 3 times in 30d | +30% | New winners need testing |
| **SATURATING** | Declining engagement 3+ days | -15% | Prevent audience fatigue |
| **AUDIENCE_FATIGUE** | Open rate decline > 10% over 7d | -25% | Reduce overexposed content |

**Trigger Lifecycle**:
1. **Detection**: Performance-analyst identifies patterns during schedule generation
2. **Storage**: Saved via `save_volume_triggers()` with expiration date
3. **Application**: Applied during `get_volume_config()` calculation
4. **Expiration**: Automatically filtered out when `expires_at` passes
5. **Tracking**: `applied_count` increments each time trigger is used

**Database Schema**:
- `volume_triggers` table stores active triggers
- Fields: `creator_id`, `content_type`, `trigger_type`, `adjustment_multiplier`, `reason`, `confidence`, `expires_at`, `applied_count`
- Auto-deactivation via `expires_at > datetime('now')` filter

**Example Trigger**:
```json
{
  "content_type": "b/g_explicit",
  "trigger_type": "HIGH_PERFORMER",
  "adjustment_multiplier": 1.20,
  "reason": "RPS $245, conversion 8.2%, consistent performance",
  "confidence": 0.92,
  "expires_at": "2025-01-15T00:00:00Z"
}
```

### Integration with Volume Config

Volume Optimization v3.0 integrates seamlessly into the existing `get_volume_config()` workflow:

1. **Base Calculation**: Tier-based foundation volumes
2. **Multi-Horizon Fusion**: 7d/14d/30d saturation/opportunity analysis
3. **Confidence Dampening**: Reduce volumes when confidence is low
4. **DOW Distribution**: Day-of-week adjustments
5. **Elasticity Bounds**: Prevent extreme fluctuations
6. **Content Weighting**: Performance-based content type allocation
7. **Caption Pool Check**: Verify sufficient captions available
8. **Prediction Tracking**: Audit trail for predictions
9. **[v3.0] Bump Multiplier**: Content category-based engagement scaling
10. **[v3.0] Followup Scaling**: PPV-proportional followup calculation

**Access Pattern**:
```python
# Call get_volume_config() - all v3.0 features auto-included
volume_config = get_volume_config(creator_id="creator_123")

# Check bump optimization
print(f"Content category: {volume_config['content_category']}")
print(f"Bump multiplier: {volume_config['bump_multiplier']}")
print(f"Adjusted engagement: {volume_config['bump_adjusted_engagement']}")
print(f"Capped: {volume_config['bump_capped']}")

# Check followup scaling
print(f"PPV count: {volume_config['ppv_per_day']}")
print(f"Followups: {volume_config['followup_volume_scaled']}")
print(f"Rate used: {volume_config['followup_rate_used']}")
```

## 22 Send Types (v2.1)

### Revenue (9 types)
`ppv_unlock`, `ppv_wall`, `tip_goal`, `bundle`, `flash_bundle`, `game_post`, `first_to_tip`, `vip_program`, `snapchat_bundle`

### Engagement (9 types)
`link_drop`, `wall_link_drop`, `bump_normal`, `bump_descriptive`, `bump_text_only`, `bump_flyer`, `dm_farm`, `like_farm`, `live_promo`

### Retention (4 types)
`renew_on_post`, `renew_on_message`, `ppv_followup`, `expired_winback`

**Note**: `ppv_message` has been deprecated (is_active=0) and merged into `ppv_unlock`. Transition period ends 2025-01-16.

## Critical Constraints

- **Retention types**: Only for `paid` page types
- **PPV unlocks** (`ppv_unlock`): Max 4 per day - primary revenue sends
- **PPV followups** (`ppv_followup`): Max 5 per day - auto-generated 20-60 min after parent PPV
  - Note: PPV followups are separate from PPV unlocks (different send types)
  - Example: 4 ppv_unlock sends → up to 4 ppv_followup sends (within daily limit of 5)
- **VIP program**: Max 1 per week
- **Snapchat bundle**: Max 1 per week
- **Caption freshness**: Minimum 30-day threshold for reuse

## Caption Selection Algorithm (v2.2)

The caption selection system uses a universal pool with **Four-Layer Defense** to ensure only valid captions are selected.

### Universal Caption Access
- All **59,405 captions** are accessible to any creator
- `caption_bank.creator_id` is ignored in selection queries
- Historical creator assignments preserved for analytics only

### Four-Layer Defense Architecture

Caption selection is protected by four independent validation layers:

| Layer | Component | Responsibility | Failure Action |
|-------|-----------|----------------|----------------|
| 1 | **MCP Tools** | Database-level `vault_matrix` INNER JOIN + AVOID tier exclusion | Returns only vault-compliant, non-AVOID captions |
| 2 | **caption-selection-pro** | Post-selection validation with ValidationProof output | Rejects non-compliant, selects next best |
| 3 | **Quality-Validator Agent** | Upstream proof verification + HARD REJECTION | Rejects entire schedule if ANY violation |
| 4 | **save_schedule Gatekeeper** | ValidationCertificate requirement (Phase 1: optional) | Warns/rejects schedules without valid certificate |

### Vault Matrix Filtering (HARD FILTER)
- Only captions matching creator's `vault_matrix` content types are returned
- Content type validation happens at the database level via INNER JOIN in `get_send_type_captions()` and `get_top_captions()`
- Creators must have vault_matrix entries to receive captions
- **ZERO TOLERANCE**: Any caption with non-vault content type = schedule REJECTED

### AVOID Tier Exclusion (HARD FILTER)
- Content types in AVOID tier are NEVER scheduled
- AVOID tier is determined by `get_content_type_rankings()` based on performance tiers
- **ZERO TOLERANCE**: Any caption with AVOID tier content = schedule REJECTED

### Scoring Weights (After Hard Gates Pass)
| Component | Weight | Purpose |
|-----------|--------|---------|
| Freshness | 35% | Prioritize unused captions |
| Performance | 30% | Prefer high-earning captions |
| Character Length | 20% | Optimal 250-449 chars (+107.6% RPS) |
| Type Priority | 10% | Send type compatibility |
| Diversity | 2.5% | Prevent repetition |
| Persona | 2.5% | Minor tone alignment |

### Freshness Calculation
```
freshness_score = 100 - (days_since_last_use * 2)
```
- Never used: 100 (maximum freshness)
- Used 30 days ago: 40
- Minimum: 0

### Caption Pool Hierarchy
1. **Primary**: MCP tool returns vault-filtered, AVOID-excluded, freshness-sorted captions
2. **Fallback Level 1**: Relax freshness to >= 20 (vault + AVOID gates NEVER relax)
3. **Fallback Level 2**: Relax performance to >= 30 (vault + AVOID gates NEVER relax)
4. **Fallback Level 3**: Generic high-performers (vault + AVOID gates NEVER relax)
5. **Manual**: Flag `needs_manual_caption = true` if all fallbacks exhausted

## Vault Matrix Management

### Overview

The `vault_matrix` table controls which content types each creator can use. It acts as a hard filter during caption selection to ensure only appropriate content is scheduled.

**Architecture**: Hybrid UX approach
- **User Interface**: Google Sheets (wide format - easy to visualize and bulk edit)
- **Database Storage**: Normalized table (optimized for MCP queries)
- **Bridge**: Python import/export script (`database/scripts/vault_matrix_sync.py`)

### Creator Vault Notes

Each creator has a `vault_notes` field for vault-specific restrictions and preferences:

**Examples**:
- `"Prohibited: Face closeups due to privacy preference"`
- `"Prefers: Solo content on Mondays, B/G content Wed-Fri"`
- `"Use flirty tone, avoid explicit language in teasers"`
- `"New content: POV videos coming Feb 1st - update vault matrix"`

**Access**: Available in `get_creator_profile()` response

### Import/Export Workflow

**Export vault matrix to CSV**:
```bash
cd database/scripts
python3 vault_matrix_sync.py export --output vault_matrix.csv
```

**Edit in Google Sheets**:
- Upload CSV to Google Sheets
- Modify permissions: `1` (allowed), `0` (not allowed)
- Update `vault_notes` column with creator-specific notes
- Download as CSV when done

**Import back to database**:
```bash
# Dry-run first (preview changes)
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv --dry-run

# Apply changes
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv
```

**Documentation**: See `database/docs/VAULT_MATRIX_WORKFLOW.md` for complete guide

## Coding Standards

- Use `send_type_key` consistently (never raw `send_type_id` in logic)
- Always validate `page_type` before including retention sends
- Parameterized queries for all database operations
- Type hints required for all Python functions
- Docstrings in Google style format

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EROS_DB_PATH` | Database file location | `./database/eros_sd_main.db` |

## Related Documentation

- `docs/SCHEDULE_GENERATOR_BLUEPRINT.md` - Full architecture
- `docs/USER_GUIDE.md` - End-user documentation
- `docs/SEND_TYPE_REFERENCE.md` - Complete send type details
- `database/docs/VAULT_MATRIX_WORKFLOW.md` - Vault matrix import/export guide
- `database/audit/` - Database quality reports (93/100 score)
- `database/archive/20251220/` - Archived tables (90-day retention policy)
