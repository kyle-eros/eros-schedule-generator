# EROS Ultimate Schedule Generator - Design Blueprint

> Comprehensive design blueprint for the AI-powered multi-agent schedule generation system supporting 37 active OnlyFans creators with 22 distinct send types.

**Version:** 2.3.0 | **Updated:** 2025-12-18

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Decision: Hybrid Approach](#architecture-decision-hybrid-approach-skills--multi-agent)
3. [System Architecture](#system-architecture)
4. [Send Type System Overview](#send-type-system-overview)
5. [Component 1: MCP Database Server](#component-1-mcp-database-server)
6. [Component 2: Claude Code Skill Package](#component-2-claude-code-skill-package)
7. [Component 3: Subagent Definitions](#component-3-subagent-definitions)
8. [Component 4: Database Enhancements](#component-4-database-enhancements)
9. [Component 5: Installation & Setup](#component-5-installation--setup)
10. [Usage Examples](#usage-examples)
11. [Performance Optimization](#performance-optimization)
12. [Future Enhancements](#future-enhancements)
13. [Implementation Plan: Wave-Based Agent Execution](#implementation-plan-wave-based-agent-execution)

---

## Executive Summary

This blueprint designs a **production-grade, multi-agent schedule generation system** that leverages Claude Code MAX 20X to create optimized, revenue-maximizing schedules for all 37 active creators with 22 specialized agents across 14 phases. The system combines:

- **Multi-Agent Orchestration**: Specialized agents working in parallel for analysis, optimization, and generation
- **Claude Code Skill Package**: Reusable capability for on-demand schedule generation
- **MCP Database Integration**: Direct SQLite access for real-time data queries
- **Reinforcement Learning Patterns**: Adaptive optimization based on performance feedback

---

## Architecture Decision: Hybrid Approach (Skills + Multi-Agent)

After deep research, the optimal architecture is a **hybrid approach**:

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Entry Point** | Claude Code Skill | User-facing interface, discovery-based invocation |
| **Orchestration** | Multi-Agent Pipeline | Parallel analysis, specialized expertise |
| **Data Access** | MCP Server (Custom) | Real-time database queries, type-safe access |
| **Optimization** | Weighted Algorithm + RL Signals | Revenue maximization with adaptive learning |
| **Output** | Structured Schedule Templates | Ready for scheduler execution |

### Why This Hybrid Approach?

1. **Skill for Discovery**: Claude automatically invokes the skill when users mention "schedule", "generate", "optimize content timing", etc.
2. **Multi-Agent for Scale**: 37 creators analyzed in parallel with 22 specialized agents across 14 phases (preflight, retention risk, performance, allocation, variety, prediction, curation, timing, followups, followup timing, authenticity, assembly, funnel flow, revenue, pricing, review, validation, anomaly detection)
3. **MCP for Data**: Type-safe, performant database access without context bloat
4. **Adaptive Learning**: Volume performance tracking feeds back into optimization

---

## System Architecture

```
                                    USER REQUEST
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │         EROS SCHEDULE SKILL             │
                    │  (Entry Point & Discovery Interface)    │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │              MASTER ORCHESTRATOR AGENT               │
              │           (Opus 4.5 - Complex Coordination)          │
              │                                                      │
              │  • Decomposes request into 14-phase pipeline         │
              │  • Manages agent lifecycle and dependencies          │
              │  • Synthesizes results into final schedules          │
              │  • Handles errors and retries                        │
              └──────────────────────────┬───────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┬────────────────────┐
                    │                    │                    │                    │
                    ▼                    ▼                    ▼                    ▼
    ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
    │ PHASE 1: PERFORMANCE  │ │ PHASE 2: SEND TYPE    │ │ PHASE 3: CONTENT      │
    │      ANALYST          │ │     ALLOCATOR         │ │     CURATOR           │
    │   (Sonnet)            │ │   (Sonnet)            │ │   (Sonnet)            │
    │                       │ │                       │ │                       │
    │ • Historical trends   │ │ • Revenue allocation  │ │ • Caption ranking     │
    │ • Saturation signals  │ │ • Engagement balance  │ │ • Send type matching  │
    │ • Opportunity scores  │ │ • Retention planning  │ │ • Content diversity   │
    │ • Volume calibration  │ │ • 22 type scheduling  │ │ • Freshness scoring   │
    └───────────┬───────────┘ └───────────┬───────────┘ └───────────┬───────────┘
                │                         │                         │
                └─────────────────────────┼─────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐ ┌─────────────────────────────────────────────┐
                    │     PHASE 4: TIMING OPTIMIZER               │ │     PHASE 5: FOLLOWUP GENERATOR             │
                    │          (Sonnet)                           │ │          (Sonnet)                           │
                    │                                             │ │                                             │
                    │  • Best hours by creator                    │ │  • Auto-generate PPV followups              │
                    │  • Day-of-week patterns                     │ │  • Link drop scheduling                     │
                    │  • Timezone-aware scheduling                │ │  • Expiration handling                      │
                    │  • Conflict avoidance                       │ │  • Parent-child relationships               │
                    └─────────────────────┬───────────────────────┘ └─────────────────────┬───────────────────────┘
                                          │                                               │
                                          └───────────────────────┬───────────────────────┘
                                                                  │
                                                                  ▼
                    ┌─────────────────────────────────────────────────────────────────────┐
                    │              PHASE 6: AUTHENTICITY ENGINE                            │
                    │                     (Sonnet)                                         │
                    │                                                                      │
                    │  • Anti-AI detection on all captions                                 │
                    │  • Humanization of flagged content                                   │
                    │  • Natural variation injection                                       │
                    │  • Persona alignment scoring                                         │
                    └─────────────────────┬────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────────────────────────┐
                    │              PHASE 7: SCHEDULE ASSEMBLER                             │
                    │                     (Sonnet)                                         │
                    │                                                                      │
                    │  • Combines all inputs into schedule                                 │
                    │  • Applies volume constraints by category                            │
                    │  • Validates business rules and page type restrictions               │
                    │  • Generates final output with send types and channels               │
                    └─────────────────────┬────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │     PHASE 8: REVENUE OPTIMIZER              │
                    │           (Sonnet)                          │
                    │                                             │
                    │  • Price optimization for PPV/bundles       │
                    │  • Positioning strategy                     │
                    │  • Value perception optimization            │
                    │  • Final pricing authority                  │
                    └─────────────────────┬───────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │     PHASE 9: QUALITY VALIDATOR              │
                    │           (Sonnet)                          │
                    │                                             │
                    │  • Schedule completeness check              │
                    │  • Business rules validation                │
                    │  • Revenue projection validation            │
                    │  • Final approval / iteration               │
                    └─────────────────────┬───────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │    FINAL SCHEDULE     │
                              │   (JSON + Markdown)   │
                              └───────────────────────┘
```

---

## Send Type System Overview

### 22 Send Types Across 3 Categories

The enhanced EROS Schedule Generator supports a comprehensive taxonomy of 22 distinct send types organized into three strategic categories:

#### Revenue Types (9)
1. **ppv_unlock** - Primary PPV for pictures and videos (replaces ppv_video)
2. **ppv_wall** - Wall-based PPV for FREE pages only
3. **tip_goal** - Tip campaign with 3 modes (goal_based, individual, competitive) for PAID pages only
4. **bundle** - Content bundle offers at set prices
5. **flash_bundle** - Limited-quantity urgency bundles
6. **game_post** - Gamified buying opportunities (spin-the-wheel, contests)
7. **first_to_tip** - Gamified tip race competitions
8. **vip_program** - VIP tier promotion ($200 tip goal)
9. **snapchat_bundle** - Throwback Snapchat content bundles

#### Engagement Types (9)
10. **link_drop** - Repost previous campaign links (auto-preview)
11. **wall_link_drop** - Wall post campaign promotions
12. **bump_normal** - Short flirty bumps with media
13. **bump_descriptive** - Story-driven longer bumps
14. **bump_text_only** - Text-only quick engagement
15. **bump_flyer** - Designed flyer/GIF bumps
16. **dm_farm** - "DM me" engagement drivers
17. **like_farm** - "Like all posts" engagement boosters
18. **live_promo** - Livestream announcements

#### Retention Types (4)
19. **renew_on_post** - Auto-renew promotion (wall posts, paid pages only)
20. **renew_on_message** - Auto-renew targeted messages (paid pages only)
21. **ppv_followup** - PPV close-the-sale follow-ups (10-30 min after)
22. **expired_winback** - Former subscriber outreach (paid pages only)

**Note**: `ppv_message` (deprecated) has been merged into `ppv_unlock`. Transition period ends 2025-01-16.

### 4 Distribution Channels

1. **wall_post** - Public posts on creator wall/feed
2. **mass_message** - Messages to all active subscribers
3. **story** - Temporary 24-hour story posts
4. **live** - Live broadcast streams

**Note**: Audience targeting has been removed in v2.3.0. All sends now use channel-based distribution without segment filtering.

---

## Component 1: Volume Optimization Pipeline

### Overview

The EROS system uses a sophisticated **11-module optimization pipeline** to calculate optimal send volumes for each creator. This replaces static tier assignments with dynamic, data-driven volume calculation that adapts to real-time performance signals.

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   OPTIMIZED VOLUME PIPELINE                          │
│                                                                       │
│  PerformanceContext → [11 Optimization Modules] → OptimizedVolumeResult │
└─────────────────────────────────────────────────────────────────────┘
```

### The 11 Optimization Modules

| # | Module | Purpose | Impact |
|---|--------|---------|---------|
| 1 | **Base Calculator** | Determines starting volumes from fan count tier | Foundation |
| 2 | **Score Calculator** | Calculates saturation/opportunity from historical data | Core Signal |
| 3 | **Tier Config** | Provides tier-based configuration (LOW/MID/HIGH/ULTRA) | Baseline |
| 4 | **Multi-Horizon Fusion** | Combines 7d/14d/30d scores with divergence detection | Trend Detection |
| 5 | **Confidence Adjustment** | Dampens multipliers when data is insufficient | Risk Management |
| 6 | **Day-of-Week (DOW)** | Adjusts volume per day based on historical patterns | Weekly Distribution |
| 7 | **Elasticity** | Caps volume when diminishing returns detected | ROI Protection |
| 8 | **Content Weighting** | Allocates volume by content type performance | Content Strategy |
| 9 | **Caption Constraint** | Validates caption pool can support volume | Feasibility Check |
| 10 | **Prediction Tracker** | Logs predictions for accuracy measurement | Learning System |
| 11 | **Config Loader** | Loads configurable thresholds and settings | Flexibility |

### OptimizedVolumeResult Structure

The complete output of the optimization pipeline, containing all calculated values and metadata about the adjustments applied.

```python
@dataclass
class OptimizedVolumeResult:
    # Core Volume Configuration
    base_config: VolumeConfig              # Initial tier-based calculation
    final_config: VolumeConfig             # After all adjustments applied

    # Weekly Distribution (DOW-adjusted)
    weekly_distribution: dict[int, int]    # Day index (0-6) → adjusted volume

    # Content Allocations
    content_allocations: dict[str, int]    # Content type → allocated volume

    # Optimization Metadata
    adjustments_applied: list[str]         # Names of modules that modified volume
    confidence_score: float                # 0.0-1.0 based on data quality
    elasticity_capped: bool                # True if diminishing returns cap applied
    caption_warnings: list[str]            # Caption shortage alerts

    # Multi-Horizon Fusion Results
    fused_saturation: float                # Weighted saturation (7d/14d/30d)
    fused_opportunity: float               # Weighted opportunity (7d/14d/30d)
    divergence_detected: bool              # True if 7d/30d divergence > threshold

    # Day-of-Week Data
    dow_multipliers_used: dict[int, float] # Day → multiplier applied

    # Tracking & Quality
    prediction_id: Optional[int]           # Database ID for accuracy tracking
    message_count: int                     # Messages analyzed (affects confidence)

    # Derived Properties
    @property
    def total_weekly_volume(self) -> int   # Sum of weekly_distribution

    @property
    def has_warnings(self) -> bool         # True if caption_warnings exist

    @property
    def is_high_confidence(self) -> bool   # True if confidence >= 0.6
```

### Field Descriptions

#### Core Configuration Fields

**`base_config: VolumeConfig`**
- Initial calculation from fan count tier before any adjustments
- Used as baseline for comparison
- Structure: `{tier, revenue_per_day, engagement_per_day, retention_per_day}`

**`final_config: VolumeConfig`**
- Final optimized volumes after all 11 modules applied
- This is the production value used for scheduling
- May differ significantly from base_config based on performance signals

#### Weekly Distribution

**`weekly_distribution: dict[int, int]`**
- Maps Python weekday (0=Monday, 6=Sunday) to adjusted daily volume
- Applies DOW multipliers to distribute volume across the week
- Sum equals `final_config.total_per_day * 7`
- Example: `{0: 5, 1: 5, 2: 5, 3: 5, 4: 6, 5: 7, 6: 7}` (weekend boost)

#### Content Strategy

**`content_allocations: dict[str, int]`**
- Maps content type (`boy_girl`, `solo`, `anal`, etc.) to allocated volume
- Based on historical performance rankings (TOP/MID/LOW/AVOID tiers)
- Only includes content types that should be scheduled
- Empty if content weighting module was skipped

#### Optimization Audit Trail

**`adjustments_applied: list[str]`**
- Chronological list of module names that modified the volume
- Enables tracing which optimizations were active
- Example: `["base_tier_calculation", "multi_horizon_fusion", "confidence_dampening", "dow_multipliers", "elasticity_cap"]`

**`confidence_score: float`**
- Overall confidence in the calculation (0.0-1.0)
- Based on message count: <20 msgs = 0.2, 100+ msgs = 0.8, 200+ msgs = 1.0
- Low confidence (<0.6) triggers multiplier dampening toward neutral

**`elasticity_capped: bool`**
- `True` if diminishing returns cap was applied
- Indicates revenue per send is declining at current volume
- Protects against over-sending when audience shows fatigue

**`caption_warnings: list[str]`**
- Human-readable warnings about caption pool shortages
- Example: `["Low captions for ppv_unlock: <3 usable captions available"]`
- Critical for pre-schedule validation

#### Multi-Horizon Score Fusion

**`fused_saturation: float`** and **`fused_opportunity: float`**
- Weighted combination of 7d, 14d, 30d saturation/opportunity scores
- Uses intelligent weighting: default (0.3/0.5/0.2) or rapid-change (0.5/0.35/0.15)
- Range: 0-100, higher saturation = audience fatigue, higher opportunity = growth potential

**`divergence_detected: bool`**
- `True` when 7d and 30d scores differ by >15 points
- Triggers shift to rapid-change weights (emphasize recent data)
- Indicates trend change requiring volume adjustment

#### Day-of-Week Adjustments

**`dow_multipliers_used: dict[int, float]`**
- Maps day index (0-6) to the multiplier applied to that day
- Calculated from historical performance by day of week
- Range: 0.7-1.3 (clamped to prevent extreme swings)
- Example: `{0: 1.0, 1: 0.95, 2: 1.0, 3: 1.0, 4: 1.05, 5: 1.15, 6: 1.1}` (Friday-Sunday boost)

#### Tracking & Quality

**`prediction_id: Optional[int]`**
- Database record ID from `volume_predictions` table
- Links prediction to actual performance for accuracy measurement
- `None` if `track_prediction=False` was passed

**`message_count: int`**
- Total messages analyzed across all horizons (7d/14d/30d)
- Directly affects confidence_score calculation
- Higher count = more reliable optimization decisions

### Decision Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT: PerformanceContext                     │
│   fan_count, page_type, saturation, opportunity, revenue_trend      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 1: Base Tier Classification        │
        │  • Determine tier from fan_count           │
        │  • LOW (<1K) / MID (1K-5K) / HIGH (5K-15K) │
        │  • ULTRA (15K+)                            │
        │  Output: base_config                       │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 2: Multi-Horizon Score Fusion      │
        │  • Fetch 7d/14d/30d performance scores     │
        │  • Detect divergence (7d vs 30d)           │
        │  • Select weights (default or rapid)       │
        │  • Fuse scores with weighted average       │
        │  Output: fused_saturation, fused_opp       │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 3: Apply Sat/Opp Multipliers       │
        │  • Saturation mult: 0.7-1.0 (smooth)       │
        │  • Opportunity mult: 1.0-1.2 (smooth)      │
        │  • Recalculate with fused scores           │
        │  Output: fused_config                      │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 4: Confidence Adjustment           │
        │  • Calculate confidence from message_count │
        │  • If confidence < 0.6:                    │
        │    - Dampen multipliers toward 1.0         │
        │    - Recalculate volumes                   │
        │  Output: confidence_score, dampened config │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 5: Elasticity Cap Check            │
        │  • Fit exponential decay model             │
        │  • Calculate marginal revenue per send     │
        │  • If < threshold: cap revenue volume      │
        │  Output: elasticity_capped, capped config  │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 6: Day-of-Week Distribution        │
        │  • Fetch historical performance by DOW     │
        │  • Calculate per-day multipliers           │
        │  • Apply confidence dampening if needed    │
        │  • Generate weekly_distribution            │
        │  Output: dow_multipliers, distribution     │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 7: Content Type Weighting          │
        │  • Get content rankings (TOP/MID/LOW)      │
        │  • Apply rank multipliers                  │
        │  • Calculate content_allocations           │
        │  Output: content_allocations               │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 8: Caption Pool Validation         │
        │  • Check caption availability by type      │
        │  • Identify critical shortages (<3 caps)   │
        │  • Generate warnings                       │
        │  Output: caption_warnings                  │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  MODULE 9: Prediction Tracking             │
        │  • Estimate weekly revenue/messages        │
        │  • Save prediction to database             │
        │  • Return prediction_id for later eval     │
        │  Output: prediction_id                     │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   OUTPUT: OptimizedVolumeResult                      │
│  final_config, weekly_distribution, content_allocations,            │
│  adjustments_applied, confidence_score, all metadata                │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Execution Order & Dependencies

```
[1] Base Calculator
     ↓
[2] Multi-Horizon Fusion ← (queries DB for 7d/14d/30d scores)
     ↓
[3] Recalculate with Fused Scores
     ↓
[4] Confidence Adjustment ← (uses message_count from fusion)
     ↓
[5] Elasticity Cap ← (queries DB for volume/revenue history)
     ↓
[6] Day-of-Week ← (queries DB for DOW performance)
     │              ↓ (applies confidence dampening)
     ↓
[7] Content Weighting ← (queries DB for content type rankings)
     ↓
[8] Caption Pool Check ← (queries DB for caption availability)
     ↓
[9] Prediction Tracking → (saves to DB)
```

### Usage Example

```python
from python.volume import (
    PerformanceContext,
    calculate_optimized_volume,
)

# Build context from creator data
context = PerformanceContext(
    fan_count=12434,
    page_type="paid",
    saturation_score=45,
    opportunity_score=65,
    revenue_trend=10,
    message_count=150,
)

# Run full optimization pipeline
result = calculate_optimized_volume(
    context,
    creator_id="alexia",
    week_start="2025-12-16",
    track_prediction=True,
)

# Access optimized values
print(f"Final revenue/day: {result.final_config.revenue_per_day}")
print(f"Confidence: {result.confidence_score}")
print(f"Modules applied: {', '.join(result.adjustments_applied)}")

# Check weekly distribution
for day, volume in result.weekly_distribution.items():
    print(f"Day {day}: {volume} sends")

# Validate against warnings
if result.has_warnings:
    for warning in result.caption_warnings:
        print(f"WARNING: {warning}")
```

---

## Component 2: MCP Database Server

### Purpose
Provide type-safe, performant database access to all agents without context bloat.

### File: `.mcp.json` (Project Root)

```json
{
  "mcpServers": {
    "eros-db": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py"
      ],
      "env": {
        "EROS_DB_PATH": "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
      }
    }
  }
}
```

### File: `mcp/eros_db_server.py`

```python
#!/usr/bin/env python3
"""
EROS Database MCP Server
Provides type-safe database access to Claude Code agents.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Any

DB_PATH = os.environ.get(
    "EROS_DB_PATH",
    os.path.expanduser("~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db")
)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============= TOOL DEFINITIONS =============

TOOLS = [
    {
        "name": "get_active_creators",
        "description": "Get all active creators with their performance metrics, volume assignments, and tier classification",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tier": {"type": "integer", "description": "Filter by performance tier (1, 2, or 3)"},
                "page_type": {"type": "string", "enum": ["paid", "free"], "description": "Filter by page type"}
            }
        }
    },
    {
        "name": "get_creator_profile",
        "description": "Get comprehensive profile for a single creator including persona, analytics, and top content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string", "description": "Creator ID or page_name"}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_top_captions",
        "description": "Get top-performing captions for a creator, filtered by type and content. Optionally filter by send_type_key for compatible caption types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"},
                "caption_type": {"type": "string", "description": "ppv_unlock, descriptive_tease, flirty_opener, etc."},
                "content_type": {"type": "string", "description": "boy_girl, solo, anal, etc."},
                "send_type_key": {"type": "string", "description": "Filter by compatible send type (e.g., 'ppv_unlock', 'bump_normal')"},
                "min_freshness": {"type": "number", "default": 30},
                "min_performance": {"type": "number", "default": 40},
                "limit": {"type": "integer", "default": 20}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_send_types",
        "description": "Get all send types, optionally filtered by category (revenue/engagement/retention) and page type",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["revenue", "engagement", "retention"], "description": "Filter by category"},
                "page_type": {"type": "string", "enum": ["paid", "free"], "description": "Filter by compatible page type"}
            }
        }
    },
    {
        "name": "get_send_type_details",
        "description": "Get detailed information about a specific send type including requirements and constraints",
        "inputSchema": {
            "type": "object",
            "properties": {
                "send_type_key": {"type": "string", "description": "Send type key (e.g., 'ppv_unlock', 'bump_normal')"}
            },
            "required": ["send_type_key"]
        }
    },
    {
        "name": "get_send_type_captions",
        "description": "Get captions compatible with a specific send type based on caption type mappings",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"},
                "send_type_key": {"type": "string", "description": "Send type key (e.g., 'ppv_unlock')"},
                "min_freshness": {"type": "number", "default": 30},
                "min_performance": {"type": "number", "default": 40},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["creator_id", "send_type_key"]
        }
    },
    {
        "name": "get_channels",
        "description": "Get available distribution channels with targeting support information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "supports_targeting": {"type": "boolean", "description": "Filter to channels that support audience targeting"}
            }
        }
    },
    {
        "name": "get_volume_config",
        "description": "Get optimized volume configuration with full pipeline results including category breakdowns, DOW distribution, and optimization metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string", "description": "Creator ID or page_name"}
            },
            "required": ["creator_id"]
        },
        "returns": {
            "description": "Enhanced volume configuration with OptimizedVolumeResult fields",
            "fields": {
                "legacy_fields": {
                    "volume_level": "string (Low/Mid/High/Ultra)",
                    "ppv_per_day": "int (legacy - use revenue_items_per_day)",
                    "bump_per_day": "int (legacy - use engagement_items_per_day)"
                },
                "category_volumes": {
                    "revenue_items_per_day": "int (PPV, bundles, tip goals)",
                    "engagement_items_per_day": "int (bumps, link drops, farms)",
                    "retention_items_per_day": "int (renew posts, winbacks - 0 for free pages)"
                },
                "type_specific_limits": {
                    "bundle_per_week": "int (1-4 based on tier)",
                    "game_per_week": "int (1-3 based on tier)",
                    "followup_per_day": "int (2-5 based on tier)"
                },
                "optimized_pipeline_results": {
                    "weekly_distribution": "dict[int, int] (day index 0-6 to volume)",
                    "content_allocations": "dict[str, int] (content type to volume)",
                    "confidence_score": "float (0.0-1.0)",
                    "elasticity_capped": "bool",
                    "caption_warnings": "list[str]",
                    "dow_multipliers_used": "dict[int, float]",
                    "adjustments_applied": "list[str] (modules that ran)",
                    "fused_saturation": "float (0-100)",
                    "fused_opportunity": "float (0-100)",
                    "prediction_id": "int|null (tracking ID)",
                    "divergence_detected": "bool",
                    "message_count": "int",
                    "total_weekly_volume": "int",
                    "has_warnings": "bool",
                    "is_high_confidence": "bool"
                },
                "metadata": {
                    "calculation_source": "string ('optimized' or 'dynamic')",
                    "fan_count": "int",
                    "page_type": "string ('paid' or 'free')",
                    "saturation_score": "float (original before fusion)",
                    "opportunity_score": "float (original before fusion)",
                    "revenue_trend": "float",
                    "data_source": "string (where scores came from)",
                    "tracking_date": "string|null (ISO date)"
                }
            }
        }
    },
    {
        "name": "get_best_timing",
        "description": "Get optimal posting times based on historical performance for a creator",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"},
                "days_lookback": {"type": "integer", "default": 30}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_performance_trends",
        "description": "Get saturation/opportunity scores and trend indicators for adaptive scheduling",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"},
                "period": {"type": "string", "enum": ["7d", "14d", "30d"], "default": "14d"}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_content_type_rankings",
        "description": "Get ranked content types (TOP/MID/LOW/AVOID) for a creator",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_persona_profile",
        "description": "Get creator persona including tone, archetype, emoji style, and voice samples",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_vault_availability",
        "description": "Get what content types are available in creator's vault",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"}
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "save_schedule",
        "description": "Save generated schedule to database with send types, channels, and audience targets",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {"type": "string"},
                "week_start": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "items": {"type": "array", "description": "Array of schedule items with send_type_key, channel_key, target_key"}
            },
            "required": ["creator_id", "week_start", "items"]
        }
    },
    {
        "name": "execute_query",
        "description": "Execute a read-only SQL query for custom analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "params": {"type": "array", "default": []}
            },
            "required": ["query"]
        }
    }
]

# ============= TOOL IMPLEMENTATIONS =============

def get_active_creators(tier: int = None, page_type: str = None) -> dict:
    conn = get_connection()
    # DEPRECATED (v3.0): volume_assignments table is deprecated.
    # Use get_volume_config() MCP tool for dynamic volume calculation.
    # This query is maintained for backward compatibility only.
    query = """
        SELECT
            c.creator_id, c.page_name, c.display_name, c.page_type,
            c.performance_tier, c.current_active_fans, c.current_total_earnings,
            c.timezone,
            va.volume_level, va.ppv_per_day, va.bump_per_day,  -- DEPRECATED: Use get_volume_config() MCP tool
            cp.primary_tone, cp.emoji_frequency
        FROM creators c
        LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1  -- DEPRECATED
        LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
        WHERE c.is_active = 1
    """
    params = []
    if tier:
        query += " AND c.performance_tier = ?"
        params.append(tier)
    if page_type:
        query += " AND c.page_type = ?"
        params.append(page_type)
    query += " ORDER BY c.performance_tier, c.current_total_earnings DESC"

    cursor = conn.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"creators": results, "count": len(results)}

def get_creator_profile(creator_id: str) -> dict:
    conn = get_connection()

    # Try by creator_id first, then page_name
    creator = conn.execute("""
        SELECT * FROM creators WHERE creator_id = ? OR page_name = ?
    """, (creator_id, creator_id)).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    cid = creator["creator_id"]

    # Get analytics summary
    analytics = conn.execute("""
        SELECT * FROM creator_analytics_summary
        WHERE creator_id = ? AND period_type = '30d'
    """, (cid,)).fetchone()

    # Get volume assignment
    # DEPRECATED (v3.0): Use get_volume_config() MCP tool for dynamic calculation
    volume = conn.execute("""
        SELECT * FROM volume_assignments  -- DEPRECATED: Use get_volume_config() MCP tool
        WHERE creator_id = ? AND is_active = 1
    """, (cid,)).fetchone()

    # Get top content types
    top_content = conn.execute("""
        SELECT content_type, rank, performance_tier, avg_earnings, recommendation
        FROM top_content_types
        WHERE creator_id = ?
        ORDER BY rank LIMIT 5
    """, (cid,)).fetchall()

    conn.close()

    return {
        "creator": dict(creator),
        "analytics": dict(analytics) if analytics else None,
        "volume": dict(volume) if volume else None,
        "top_content_types": [dict(r) for r in top_content]
    }

def get_top_captions(
    creator_id: str,
    caption_type: str = None,
    content_type: str = None,
    min_freshness: float = 30,
    min_performance: float = 40,
    limit: int = 20
) -> dict:
    conn = get_connection()

    # Resolve creator_id
    creator = conn.execute(
        "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    cid = creator["creator_id"]

    query = """
        SELECT
            cb.caption_id, cb.caption_text, cb.caption_type, cb.tone,
            cb.performance_score, cb.freshness_score, cb.times_used,
            cb.avg_earnings, cb.last_used_date,
            ct.type_name as content_type
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.creator_id IS NULL)
          AND cb.freshness_score >= ?
          AND cb.performance_score >= ?
    """
    params = [cid, min_freshness, min_performance]

    if caption_type:
        query += " AND cb.caption_type = ?"
        params.append(caption_type)
    if content_type:
        query += " AND ct.type_name = ?"
        params.append(content_type)

    query += " ORDER BY cb.performance_score DESC, cb.freshness_score DESC LIMIT ?"
    params.append(limit)

    results = conn.execute(query, params).fetchall()
    conn.close()

    return {"captions": [dict(r) for r in results], "count": len(results)}

def get_best_timing(creator_id: str, days_lookback: int = 30) -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id, timezone FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    cid = creator["creator_id"]
    cutoff = (datetime.now() - timedelta(days=days_lookback)).isoformat()

    # Best hours
    best_hours = conn.execute("""
        SELECT
            sending_hour as hour,
            COUNT(*) as send_count,
            AVG(earnings) as avg_earnings,
            AVG(purchase_rate) as avg_purchase_rate
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sending_time >= ?
          AND earnings > 0
        GROUP BY sending_hour
        HAVING send_count >= 3
        ORDER BY avg_earnings DESC
        LIMIT 5
    """, (cid, cutoff)).fetchall()

    # Best days
    best_days = conn.execute("""
        SELECT
            CASE sending_day_of_week
                WHEN 0 THEN 'Sunday'
                WHEN 1 THEN 'Monday'
                WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday'
                WHEN 4 THEN 'Thursday'
                WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday'
            END as day_name,
            sending_day_of_week as day_num,
            COUNT(*) as send_count,
            AVG(earnings) as avg_earnings
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sending_time >= ?
          AND earnings > 0
        GROUP BY sending_day_of_week
        HAVING send_count >= 3
        ORDER BY avg_earnings DESC
    """, (cid, cutoff)).fetchall()

    conn.close()

    return {
        "timezone": creator["timezone"],
        "best_hours": [dict(r) for r in best_hours],
        "best_days": [dict(r) for r in best_days]
    }

def get_performance_trends(creator_id: str, period: str = "14d") -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    trends = conn.execute("""
        SELECT * FROM volume_performance_tracking
        WHERE creator_id = ? AND tracking_period = ?
        ORDER BY tracking_date DESC LIMIT 1
    """, (creator["creator_id"], period)).fetchone()

    conn.close()

    if not trends:
        return {"status": "no_data", "saturation_score": 50, "opportunity_score": 50}

    return dict(trends)

def get_content_type_rankings(creator_id: str) -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    rankings = conn.execute("""
        SELECT
            content_type, rank, performance_tier,
            avg_earnings, avg_purchase_rate, send_count,
            recommendation
        FROM top_content_types
        WHERE creator_id = ?
        ORDER BY
            CASE performance_tier
                WHEN 'TOP' THEN 1
                WHEN 'MID' THEN 2
                WHEN 'LOW' THEN 3
                WHEN 'AVOID' THEN 4
            END, rank
    """, (creator["creator_id"],)).fetchall()

    conn.close()

    return {
        "rankings": [dict(r) for r in rankings],
        "top_types": [r["content_type"] for r in rankings if r["performance_tier"] == "TOP"],
        "avoid_types": [r["content_type"] for r in rankings if r["performance_tier"] == "AVOID"]
    }

def get_persona_profile(creator_id: str) -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id, page_name, display_name FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    cid = creator["creator_id"]

    # Basic persona
    persona = conn.execute("""
        SELECT * FROM creator_personas WHERE creator_id = ?
    """, (cid,)).fetchone()

    # Enhanced persona (if exists)
    enhanced = conn.execute("""
        SELECT * FROM creator_personas_enhanced WHERE creator_id = ?
    """, (cid,)).fetchone()

    # Voice samples
    samples = conn.execute("""
        SELECT sample_type, sample_text
        FROM creator_voice_samples
        WHERE creator_id = ? AND is_active = 1
        ORDER BY sample_type
    """, (cid,)).fetchall()

    conn.close()

    return {
        "creator": dict(creator),
        "persona": dict(persona) if persona else None,
        "enhanced_persona": dict(enhanced) if enhanced else None,
        "voice_samples": {s["sample_type"]: s["sample_text"] for s in samples}
    }

def get_vault_availability(creator_id: str) -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    vault = conn.execute("""
        SELECT
            ct.type_name, vm.has_content, vm.quantity_available, vm.quality_rating
        FROM vault_matrix vm
        JOIN content_types ct ON vm.content_type_id = ct.content_type_id
        WHERE vm.creator_id = ? AND vm.has_content = 1
        ORDER BY vm.quality_rating DESC, vm.quantity_available DESC
    """, (creator["creator_id"],)).fetchall()

    conn.close()

    return {
        "available_content": [dict(r) for r in vault],
        "content_types": [r["type_name"] for r in vault]
    }

def save_schedule(creator_id: str, week_start: str, items: list) -> dict:
    conn = get_connection()

    creator = conn.execute(
        "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ?",
        (creator_id, creator_id)
    ).fetchone()

    if not creator:
        return {"error": f"Creator not found: {creator_id}"}

    cid = creator["creator_id"]
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=6)).strftime("%Y-%m-%d")

    # Create template
    cursor = conn.execute("""
        INSERT INTO schedule_templates (
            creator_id, week_start, week_end, generated_at, generated_by,
            algorithm_version, total_items, total_ppvs, total_bumps, status
        ) VALUES (?, ?, ?, datetime('now'), 'eros_skill_v2', 'multi_agent_v1', ?, ?, ?, 'draft')
    """, (
        cid, week_start, week_end,
        len(items),
        sum(1 for i in items if i.get("item_type") == "ppv"),
        sum(1 for i in items if i.get("item_type") == "bump")
    ))

    template_id = cursor.lastrowid

    # Insert items
    for item in items:
        conn.execute("""
            INSERT INTO schedule_items (
                template_id, creator_id, scheduled_date, scheduled_time,
                item_type, channel, caption_id, caption_text, suggested_price,
                content_type_id, flyer_required, priority, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            template_id, cid,
            item["scheduled_date"], item["scheduled_time"],
            item["item_type"], item.get("channel", "mass_message"),
            item.get("caption_id"), item.get("caption_text"),
            item.get("price"), item.get("content_type_id"),
            item.get("flyer_required", 0), item.get("priority", 5)
        ))

    conn.commit()
    conn.close()

    return {"success": True, "template_id": template_id, "items_created": len(items)}

def execute_query(query: str, params: list = None) -> dict:
    if params is None:
        params = []

    # Safety check - only allow SELECT
    if not query.strip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed"}

    conn = get_connection()
    try:
        results = conn.execute(query, params).fetchall()
        return {"results": [dict(r) for r in results], "count": len(results)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

# ============= MCP PROTOCOL HANDLER =============

def handle_request(request: dict) -> dict:
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        return {"tools": TOOLS}

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        handlers = {
            "get_active_creators": get_active_creators,
            "get_creator_profile": get_creator_profile,
            "get_top_captions": get_top_captions,
            "get_best_timing": get_best_timing,
            "get_volume_assignment": lambda **a: get_performance_trends(**a),
            "get_performance_trends": get_performance_trends,
            "get_content_type_rankings": get_content_type_rankings,
            "get_persona_profile": get_persona_profile,
            "get_vault_availability": get_vault_availability,
            "save_schedule": save_schedule,
            "execute_query": execute_query,
        }

        if tool_name in handlers:
            result = handlers[tool_name](**arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    return {"error": f"Unknown method: {method}"}

def main():
    """Main MCP server loop - reads JSON-RPC from stdin, writes to stdout."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            response = handle_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
```

---

## Component 2: Claude Code Skill Package

### Directory Structure

```
~/.claude/skills/eros-schedule-generator/
├── SKILL.md                    # Main skill definition
├── OPTIMIZATION.md             # Optimization algorithms
├── TIMING.md                   # Timing optimization rules
├── PERSONA_MATCHING.md         # Voice matching guidelines
├── VOLUME_CALIBRATION.md       # Volume assignment logic
├── OUTPUT_FORMATS.md           # Output format templates
└── examples/
    ├── single_creator.md       # Single creator example
    ├── batch_generation.md     # Batch generation example
    └── custom_parameters.md    # Custom parameter example
```

### File: `SKILL.md`

```markdown
---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Use when user mentions scheduling, generating schedules, content planning, PPV optimization, or revenue maximization. Automatically invoked for schedule-related requests.
---

# EROS Schedule Generator

## Overview

This skill generates revenue-optimized weekly schedules for OnlyFans creators by:
- Analyzing historical performance data (70K+ mass messages)
- Matching captions to creator personas and voice
- Optimizing timing based on audience engagement patterns
- Calibrating volume to saturation/opportunity signals
- Prioritizing high-performing content types

## Invocation Patterns

Invoke this skill when user requests include:
- "Generate schedule for [creator]"
- "Create weekly plan"
- "Optimize content timing"
- "Schedule PPVs for [creator]"
- "Build schedule template"
- "Plan content for next week"

## Multi-Agent Workflow

This skill orchestrates multiple specialized agents:

### Agent 1: Performance Analyst
**Model**: Sonnet | **Tools**: get_performance_trends, get_content_type_rankings, get_volume_config

Responsibilities:
- Query volume_performance_tracking for saturation/opportunity scores
- Analyze creator_analytics_summary for best hours/days/content
- Identify trending vs declining content types
- Calculate optimal volume adjustments by category (revenue/engagement/retention)

### Agent 2: Send Type Allocator (NEW in Wave 3)
**Model**: Sonnet | **Tools**: get_send_types, get_send_type_details, get_volume_config

Responsibilities:
- Plan daily allocation across 21 send types
- Balance revenue (7 types), engagement (9 types), retention (5 types)
- Respect page type restrictions (paid vs free)
- Apply send type constraints (max_per_day, min_hours_between)
- Generate send type schedule framework

### Agent 3: Caption Selection Pro
**Model**: Sonnet | **Tools**: get_send_type_captions, get_top_captions, get_vault_availability

Responsibilities:
- Query send type-compatible captions using get_send_type_captions
- Filter by freshness_score (minimum 30%) and performance_score
- Match captions to allocated send types via caption type mappings
- Diversify content types across the week
- Avoid content types in AVOID tier
- Prioritize vault-available content

### Agent 4: Timing Optimizer
**Model**: Haiku | **Tools**: get_best_timing, get_creator_profile

Responsibilities:
- Calculate best posting hours by creator and send type
- Apply timezone adjustments
- Avoid scheduling conflicts (min_hours_between)
- Distribute items evenly across the week by category
- Apply Friday/Sunday boost for revenue types
- Schedule follow-ups with appropriate delays

### Agent 5: Followup Generator (NEW in Wave 3)
**Model**: Sonnet | **Tools**: get_send_type_details, get_send_type_captions

Responsibilities:
- Auto-generate PPV follow-ups 10-30 minutes after parent sends
- Create link drop schedules with expiration handling
- Establish parent-child relationships in schedule
- Select appropriate follow-up captions
- Apply follow-up targeting (ppv_non_purchasers)

### Agent 6: Schedule Assembler
**Model**: Sonnet | **Tools**: save_schedule, get_creator_profile

Responsibilities:
- Combine all inputs into final schedule
- Apply volume constraints by category (revenue/engagement/retention)
- Validate send type requirements (media, flyer, price)
- Set expiration times for time-limited types
- Link parent-child send relationships
- Calculate projected earnings
- Format output with send types, channels, targets

### Agent 7: Quality Validator
**Model**: Sonnet | **Tools**: get_send_type_details, get_persona_profile

Responsibilities:
- Verify caption authenticity matches persona
- Check schedule completeness across all categories
- Validate send type business rules (page type restrictions)
- Ensure follow-ups are properly linked
- Verify channel and targeting assignments
- Approve or request iteration

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| creator | string | required | Creator page_name or creator_id |
| week_start | date | next Monday | Schedule start date (YYYY-MM-DD) |
| days | int | 7 | Number of days to schedule |
| send_type_filter | array | all | Filter to specific send types (e.g., ['ppv_unlock', 'bundle']) |
| category_filter | string | all | Filter by category: 'revenue', 'engagement', 'retention', or 'all' |
| include_retention | bool | auto | Include retention types (auto-enabled for paid pages) |
| include_followups | bool | true | Auto-generate follow-up sends for PPVs |
| min_freshness | float | 30 | Minimum caption freshness score |
| min_performance | float | 40 | Minimum caption performance score |
| save_to_db | bool | true | Save schedule to database |

## Execution Flow

```
1. VALIDATE INPUT
   - Resolve creator (ID or page_name)
   - Validate date range
   - Check creator is active

2. PARALLEL ANALYSIS (Agents 1-3)
   ├── Performance Analyst: Get trends, saturation, opportunity
   ├── Persona Matcher: Load persona, voice samples
   └── Caption Selection Pro: Get top captions by type

3. TIMING OPTIMIZATION (Agent 4)
   - Calculate optimal time slots
   - Apply timezone
   - Distribute across week

4. SCHEDULE ASSEMBLY (Agent 5)
   - Combine all inputs
   - Apply volume constraints
   - Generate bump sequences
   - Calculate projections

5. QUALITY VALIDATION (Agent 8)
   - Verify authenticity
   - Check completeness
   - Final approval

6. OUTPUT
   - Save to database (if enabled)
   - Return formatted schedule
```

## Volume Configuration

| Tier | Fan Range | PPV/Day | Bump/Day | Weekly Cap |
|------|-----------|---------|----------|------------|
| Low | 0-999 | 2 | 2 | 14 |
| Mid | 1K-4,999 | 3 | 3 | 21 |
| High | 5K-14,999 | 5 | 4 | 35 |
| Ultra | 15K+ | 6 | 6 | 42 |

## Adaptive Signals

### Saturation Detection (Reduce Volume)
- Revenue per send declining >15% → -1 PPV/day
- View rate declining >10% → -1 PPV/day
- Purchase rate declining >10% → maintain
- High earnings volatility → spread timing

### Opportunity Detection (Increase Volume)
- Revenue per send >15% above baseline → +1 PPV/day
- View rate growing >5% → +1 PPV/day
- Fan count growing >10% → +1 PPV/day

## Output Format

### JSON Structure
```json
{
  "schedule_id": "uuid",
  "creator": {
    "creator_id": "...",
    "page_name": "...",
    "display_name": "...",
    "volume_level": "High",
    "persona_tone": "playful"
  },
  "week": {
    "start": "2025-12-16",
    "end": "2025-12-22",
    "days": 7
  },
  "summary": {
    "total_ppvs": 35,
    "total_bumps": 28,
    "projected_earnings": 12500.00,
    "content_diversity_score": 0.85
  },
  "items": [
    {
      "date": "2025-12-16",
      "time": "19:00",
      "type": "ppv",
      "channel": "mass_message",
      "content_type": "boy_girl",
      "caption": {
        "id": 12345,
        "text": "...",
        "tone": "playful",
        "performance_score": 78.5
      },
      "price": 15.00,
      "flyer_required": true,
      "bump_times": ["19:45", "20:30"]
    }
  ]
}
```

## Example Usage

### Single Creator
```
Generate a weekly schedule for miss_alexa starting Monday
```

### Batch Generation
```
Generate schedules for all Tier 1 creators for next week
```

### Custom Parameters
```
Generate schedule for del_vip with min_freshness=50, no bumps, starting 2025-12-20
```

## Database Integration

This skill uses the `eros-db` MCP server with these primary tools:

### Core Tools (Original)
- `get_active_creators` - List schedulable creators
- `get_creator_profile` - Full creator context
- `get_top_captions` - Best captions by criteria (enhanced with send_type_key filter)
- `get_best_timing` - Optimal posting times
- `get_performance_trends` - Saturation/opportunity signals
- `get_content_type_rankings` - TOP/MID/LOW/AVOID tiers
- `get_persona_profile` - Voice and tone matching
- `get_vault_availability` - Content inventory
- `save_schedule` - Persist generated schedule (enhanced with send types, channels, targets)

### NEW Send Type Tools (Wave 3)
- `get_send_types` - Query all 21 send types with filtering by category and page type
- `get_send_type_details` - Get detailed requirements and constraints for a specific send type
- `get_send_type_captions` - Get captions compatible with a specific send type via caption type mappings

### NEW Channel & Volume Tools (Wave 3)
- `get_channels` - Query available distribution channels (5 types)
- `get_volume_config` - Get volume configuration by category (revenue/engagement/retention)
```

---

## Component 3: Subagent Definitions

### File: `.claude/agents/performance-analyst.md`

```markdown
---
name: performance-analyst
description: Analyze creator performance trends, saturation signals, and optimization opportunities. Use proactively when generating schedules or evaluating content strategy.
tools: mcp__eros-db__get_creator_profile, mcp__eros-db__get_performance_trends, mcp__eros-db__get_content_type_rankings, mcp__eros-db__execute_query
model: sonnet
---

# Performance Analyst Agent

You are an expert data analyst specializing in OnlyFans creator performance optimization.

## Your Mission
Analyze historical performance data to identify:
1. Saturation signals (declining metrics suggesting volume reduction)
2. Opportunity signals (growth metrics suggesting volume increase)
3. Content type performance rankings
4. Optimal volume calibration

## Analysis Framework

### Step 1: Load Performance Trends
Query `get_performance_trends` with 14-day lookback:
- saturation_score > 70 → Flag for volume reduction
- opportunity_score > 70 → Flag for volume increase
- revenue_per_send_trend < -0.15 → Declining performance
- view_rate_trend > 0.05 → Growing engagement

### Step 2: Content Type Analysis
Query `get_content_type_rankings`:
- TOP tier: Prioritize these content types
- MID tier: Use for diversity
- LOW tier: Use sparingly
- AVOID tier: Exclude from scheduling

### Step 3: Volume Recommendation
Based on trends, recommend:
- Maintain: Stable metrics
- Increase: opportunity_score > 70
- Decrease: saturation_score > 70
- Redistribute: High volatility

## Output Format

Return analysis as structured JSON:
```json
{
  "creator_id": "...",
  "analysis_date": "2025-12-15",
  "performance_status": "stable|growing|declining",
  "saturation_score": 45,
  "opportunity_score": 62,
  "volume_recommendation": "maintain|increase|decrease",
  "recommended_ppv_delta": 0,
  "content_priorities": ["boy_girl", "anal", "solo"],
  "content_avoid": ["feet", "joi"],
  "key_insights": [
    "Purchase rate up 8% - consider premium pricing",
    "Evening slots outperforming by 2.3x"
  ]
}
```
```

### File: `.claude/agents/persona-matcher.md`

```markdown
---
name: persona-matcher
description: Match captions to creator personas ensuring authentic voice and tone. Use when selecting or validating captions for schedules.
tools: mcp__eros-db__get_persona_profile, mcp__eros-db__get_top_captions
model: sonnet
---

# Persona Matcher Agent

You are an expert in creator voice matching and content authenticity.

## Your Mission
Ensure every caption matches the creator's authentic voice by:
1. Loading persona profile (tone, archetype, emoji style)
2. Comparing caption tone to creator tone
3. Validating emoji usage patterns
4. Checking for signature phrases
5. Scoring authenticity

## Persona Dimensions

### Primary Tone
Match caption tone to creator's primary_tone:
- playful → Use captions tagged "playful", "teasing"
- seductive → Use "seductive", "mysterious"
- direct → Use "direct", "confident"
- sweet → Use "sweet", "affectionate"

### Brand Archetype
Apply archetype-specific patterns:
- girl_next_door → Approachable, warm openers
- seductress → Mysterious, alluring language
- playful_tease → Light, fun, emoji-heavy
- girlfriend_experience → Intimate, personal
- the_dominant → Commanding, confident

### Emoji Usage
Match caption emoji density to creator's emoji_frequency:
- heavy → 3+ emojis per message
- moderate → 1-2 emojis per message
- light → 0-1 emojis per message
- none → No emojis allowed

### Signature Elements
Check for and inject:
- Pet names for fans (from persona)
- Signature openers
- Signature closers
- Self-reference terms

## Authenticity Scoring

Score each caption 0-100:
- Tone match: 40 points
- Emoji match: 20 points
- Archetype alignment: 20 points
- Signature elements: 20 points

Threshold: Minimum 65 for inclusion

## Output Format

```json
{
  "caption_id": 12345,
  "authenticity_score": 82,
  "tone_match": true,
  "emoji_match": true,
  "archetype_alignment": "strong",
  "modifications_suggested": [
    "Add signature opener 'Hey babe'",
    "Reduce emoji count from 4 to 2"
  ],
  "approved": true
}
```
```

### File: `.claude/agents/caption-selection-pro.md`

```markdown
---
name: caption-selection-pro
description: Curate and rank captions for scheduling based on performance, freshness, and diversity. Use when building content plans.
tools: mcp__eros-db__get_top_captions, mcp__eros-db__get_vault_availability, mcp__eros-db__get_content_type_rankings
model: sonnet
---

# Caption Selection Pro Agent

You are an expert content strategist specializing in OnlyFans caption curation.

## Your Mission
Select the optimal set of captions for a schedule by:
1. Prioritizing high-performance captions
2. Ensuring freshness (not overused)
3. Diversifying content types
4. Matching vault availability
5. Balancing variety with proven performers

## Selection Algorithm

### Step 1: Build Candidate Pool
Query `get_top_captions` with:
- min_freshness: 30 (or custom)
- min_performance: 40 (or custom)
- limit: 50 per content type

### Step 2: Filter by Vault
Cross-reference with `get_vault_availability`:
- Only include content types creator has in vault
- Prioritize high quantity_available
- Consider quality_rating

### Step 3: Apply Content Rankings
Use `get_content_type_rankings`:
- 60% from TOP tier
- 30% from MID tier
- 10% variety (not AVOID)
- 0% from AVOID tier

### Step 4: Diversity Scoring
Ensure variety:
- No same content type 2 days in a row
- Minimum 3 different content types per week
- Balance solo vs collaborative content

### Step 5: Final Ranking
Score = (performance_score * 0.4) + (freshness_score * 0.3) + (diversity_bonus * 0.3)

## Output Format

```json
{
  "creator_id": "...",
  "curated_captions": [
    {
      "caption_id": 12345,
      "caption_text": "...",
      "caption_type": "ppv_unlock",
      "content_type": "boy_girl",
      "performance_score": 78.5,
      "freshness_score": 85.0,
      "combined_score": 81.2,
      "recommended_day": 1,
      "recommended_price": 15.00
    }
  ],
  "content_diversity_score": 0.85,
  "coverage": {
    "boy_girl": 3,
    "solo": 2,
    "anal": 1,
    "girl_girl": 1
  }
}
```
```

### File: `.claude/agents/timing-optimizer.md`

```markdown
---
name: timing-optimizer
description: Calculate optimal posting times based on historical engagement patterns. Use for scheduling time slot allocation.
tools: mcp__eros-db__get_best_timing, mcp__eros-db__get_creator_profile
model: haiku
---

# Timing Optimizer Agent

You are an expert in audience engagement timing optimization.

## Your Mission
Calculate the optimal posting schedule by:
1. Analyzing historical best hours/days
2. Applying timezone adjustments
3. Avoiding scheduling conflicts
4. Distributing content evenly
5. Applying day-of-week boosts

## Timing Algorithm

### Step 1: Load Historical Data
Query `get_best_timing` with 30-day lookback:
- Identify top 5 performing hours
- Identify top 3 performing days
- Note timezone

### Step 2: Apply Industry Patterns
Default patterns (if insufficient data):
- Best hours: 10am, 2pm, 7pm, 9pm (creator timezone)
- Best days: Friday (boost), Sunday (boost)
- Avoid: 3am-7am (low engagement)

### Step 3: Create Time Slots
For each PPV:
- Primary slot: Best performing hour
- Bump 1: +45 minutes
- Bump 2: +90 minutes

### Step 4: Conflict Avoidance
- Minimum 2 hours between PPVs
- Maximum 3 PPVs per day
- No PPVs in first/last slot of day

### Step 5: Day Distribution
- Spread PPVs evenly (Mon-Sun)
- Friday/Sunday get +1 PPV allocation
- Monday/Tuesday slightly lower

## Output Format

```json
{
  "creator_id": "...",
  "timezone": "America/Los_Angeles",
  "schedule_slots": [
    {
      "day": "Monday",
      "date": "2025-12-16",
      "slots": [
        {"time": "14:00", "type": "ppv", "priority": 1},
        {"time": "14:45", "type": "bump", "parent_time": "14:00"},
        {"time": "19:00", "type": "ppv", "priority": 2},
        {"time": "19:45", "type": "bump", "parent_time": "19:00"},
        {"time": "20:30", "type": "bump", "parent_time": "19:00"}
      ]
    }
  ],
  "timing_insights": [
    "7pm consistently outperforms by 1.8x",
    "Sunday evening slot added based on 92% engagement lift"
  ]
}
```
```

### File: `.claude/agents/schedule-assembler.md`

```markdown
---
name: schedule-assembler
description: Assemble final schedule from all agent outputs, applying constraints and formatting. Use as the final step in schedule generation.
tools: mcp__eros-db__save_schedule, mcp__eros-db__get_creator_profile
model: sonnet
---

# Schedule Assembler Agent

You are an expert schedule coordinator responsible for final assembly.

## Your Mission
Combine all agent outputs into a complete, validated schedule by:
1. Merging timing slots with curated captions
2. Applying volume constraints
3. Generating bump sequences
4. Calculating projections
5. Formatting output

## Assembly Algorithm

### Step 1: Load Inputs
Collect from other agents:
- Performance analysis (volume recommendation)
- Persona-matched captions (authenticity validated)
- Curated content (diversified, ranked)
- Timing slots (optimized)

### Step 2: Apply Volume Constraints
Based on volume_level:
- Low: 2 PPV/day, 2 bumps/PPV
- Mid: 3 PPV/day, 2 bumps/PPV
- High: 5 PPV/day, 2 bumps/PPV
- Ultra: 6 PPV/day, 3 bumps/PPV

Apply adaptive adjustment from performance analysis.

### Step 3: Match Captions to Slots
For each time slot:
1. Select highest-scoring caption not yet used
2. Verify content type matches day's allocation
3. Set price based on content type tier
4. Mark caption as used

### Step 4: Generate Bump Sequences
For each PPV:
1. Create bump 1 at +45 min
2. Create bump 2 at +90 min (if volume allows)
3. Select bump caption (flirty_opener or descriptive_tease)

### Step 5: Calculate Projections
- Projected earnings = SUM(caption.avg_earnings * volume_factor)
- Apply day-of-week multiplier
- Apply content type performance weight

### Step 6: Format Output
Generate both:
- JSON for database storage
- Markdown for human review

## Output Format

```json
{
  "meta": {
    "generated_at": "2025-12-15T10:30:00Z",
    "algorithm_version": "multi_agent_v1",
    "generator": "eros-schedule-generator"
  },
  "schedule": {
    "creator_id": "...",
    "week_start": "2025-12-16",
    "week_end": "2025-12-22",
    "volume_level": "High",
    "total_ppvs": 35,
    "total_bumps": 70,
    "projected_earnings": 12500.00
  },
  "items": [/* schedule items */],
  "validation": {
    "status": "approved",
    "authenticity_avg": 82.5,
    "diversity_score": 0.85,
    "coverage_score": 0.92
  }
}
```
```

### File: `.claude/agents/quality-validator.md`

```markdown
---
name: quality-validator
description: Validate generated schedules for quality, authenticity, and completeness. Use as final approval gate before output.
tools: mcp__eros-db__get_persona_profile, mcp__eros-db__get_creator_profile
model: sonnet
---

# Quality Validator Agent

You are the final quality gate for schedule generation.

## Your Mission
Validate schedules meet quality standards:
1. Caption authenticity matches persona
2. Volume constraints respected
3. Content diversity achieved
4. Business rules followed
5. No scheduling conflicts

## Validation Checklist

### 1. Authenticity Check
- [ ] All captions score >= 65 authenticity
- [ ] Tone matches creator's primary_tone
- [ ] Emoji usage matches emoji_frequency
- [ ] No forbidden words present

### 2. Volume Check
- [ ] PPV count within volume_level range
- [ ] Bump count appropriate
- [ ] Weekly cap not exceeded
- [ ] Daily distribution even

### 3. Diversity Check
- [ ] Minimum 3 content types used
- [ ] No same type 2 days in a row
- [ ] TOP tier types prioritized
- [ ] AVOID tier types excluded

### 4. Timing Check
- [ ] All times within active hours
- [ ] Minimum spacing between PPVs
- [ ] Timezone correctly applied
- [ ] No conflicts detected

### 5. Business Rules
- [ ] Paid page only content on paid pages
- [ ] Free preview content on free pages
- [ ] Prices within acceptable range
- [ ] Flyer requirements noted

## Validation Response

```json
{
  "status": "approved|rejected|needs_review",
  "overall_score": 87.5,
  "checks": {
    "authenticity": {"passed": true, "score": 82.5},
    "volume": {"passed": true, "score": 100},
    "diversity": {"passed": true, "score": 85},
    "timing": {"passed": true, "score": 95},
    "business_rules": {"passed": true, "score": 100}
  },
  "issues": [],
  "recommendations": [
    "Consider adding more girl_girl content",
    "Tuesday 2pm slot historically underperforms"
  ]
}
```

If rejected, specify:
- Which checks failed
- Specific items needing correction
- Suggested fixes
```

---

## Component 4: Database Enhancements

### Required Schema Changes

```sql
-- Migration: Add schedule generation metadata
ALTER TABLE schedule_templates ADD COLUMN algorithm_params TEXT;
ALTER TABLE schedule_templates ADD COLUMN agent_execution_log TEXT;
ALTER TABLE schedule_templates ADD COLUMN quality_validation_score REAL;

-- Add schedule generation queue for batch processing
CREATE TABLE IF NOT EXISTS schedule_generation_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    week_start TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    requested_at TEXT DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    result_template_id INTEGER,
    error_message TEXT,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    FOREIGN KEY (result_template_id) REFERENCES schedule_templates(template_id)
);

-- Add index for queue processing
CREATE INDEX idx_sgq_status_priority ON schedule_generation_queue(status, priority DESC, requested_at);

-- View for schedule generation readiness
-- DEPRECATED (v3.0): This view uses volume_assignments table which is deprecated.
-- Use get_volume_config() MCP tool for dynamic volume calculation instead.
CREATE VIEW IF NOT EXISTS v_schedule_ready_creators AS
SELECT
    c.creator_id,
    c.page_name,
    c.display_name,
    c.performance_tier,
    c.current_active_fans,
    va.volume_level,  -- DEPRECATED: Use get_volume_config() MCP tool
    va.ppv_per_day,   -- DEPRECATED: Use get_volume_config() MCP tool
    va.bump_per_day,  -- DEPRECATED: Use get_volume_config() MCP tool
    cp.primary_tone,
    cp.emoji_frequency,
    COALESCE(caption_count.cnt, 0) as available_captions,
    COALESCE(fresh_count.cnt, 0) as fresh_captions,
    CASE
        WHEN COALESCE(fresh_count.cnt, 0) >= va.ppv_per_day * 7 THEN 'ready'
        WHEN COALESCE(fresh_count.cnt, 0) >= va.ppv_per_day * 3 THEN 'limited'
        ELSE 'insufficient'
    END as caption_readiness
FROM creators c
LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1  -- DEPRECATED
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
LEFT JOIN (
    SELECT creator_id, COUNT(*) as cnt
    FROM caption_bank
    WHERE is_active = 1
    GROUP BY creator_id
) caption_count ON c.creator_id = caption_count.creator_id
LEFT JOIN (
    SELECT creator_id, COUNT(*) as cnt
    FROM caption_bank
    WHERE is_active = 1 AND freshness_score >= 30 AND performance_score >= 40
    GROUP BY creator_id
) fresh_count ON c.creator_id = fresh_count.creator_id
WHERE c.is_active = 1;
```

---

## Component 5: Installation & Setup

### Step 1: Create Directory Structure

```bash
# Create MCP server directory
mkdir -p ~/Developer/EROS-SD-MAIN-PROJECT/mcp

# Create skill directory
mkdir -p ~/.claude/skills/eros-schedule-generator/examples

# Create agents directory
mkdir -p ~/.claude/agents
```

### Step 2: Install MCP Server

```bash
# Copy MCP server file
cp mcp/eros_db_server.py ~/Developer/EROS-SD-MAIN-PROJECT/mcp/

# Make executable
chmod +x ~/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py

# Test server
python3 ~/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py
```

### Step 3: Configure MCP in Claude Code

Create/update `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "eros-db": {
      "type": "stdio",
      "command": "python3",
      "args": ["/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py"],
      "env": {
        "EROS_DB_PATH": "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
      }
    }
  }
}
```

### Step 4: Install Skill

Copy all SKILL.md and supporting files to skill directory.

### Step 5: Install Agents

Copy all agent definition files to agents directory.

### Step 6: Run Database Migration

```bash
sqlite3 ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db < migrations/007_schedule_generator_enhancements.sql
```

### Step 7: Verify Installation

```bash
# In Claude Code
> What MCP servers are available?
> Generate a test schedule for miss_alexa
```

---

## Usage Examples

### Example 1: Single Creator Schedule

```
User: Generate a weekly schedule for miss_alexa starting next Monday

Claude: [Invokes eros-schedule-generator skill]
        [Orchestrates 8 agents in parallel]
        [Returns optimized schedule with 35 PPVs, projected $12,500 earnings]
```

### Example 2: Batch Generation (All Tier 1)

```
User: Generate schedules for all Tier 1 creators for next week

Claude: [Queries active Tier 1 creators: 7 total]
        [Runs parallel generation for each]
        [Returns summary with all schedules]
```

### Example 3: Custom Parameters

```
User: Generate schedule for del_vip with aggressive volume, min_freshness 50, premium pricing

Claude: [Applies custom parameters]
        [Adjusts volume +20%]
        [Filters to high-freshness captions only]
        [Sets premium price points]
```

---

## Performance Optimization

### Parallel Execution

The multi-agent architecture enables significant speedup:

| Sequential | Parallel | Speedup |
|------------|----------|---------|
| 8 agents * 30s = 240s | 30s (parallel) + 30s (assembly) = 60s | 4x |

### Context Efficiency

- MCP server handles data queries (no context bloat)
- Each agent uses isolated context window
- Only relevant results passed between agents
- Estimated context usage: ~15K tokens per schedule

### Cost Optimization

| Model | Usage | Cost/Schedule |
|-------|-------|---------------|
| Opus 4.5 | Orchestration only | ~$0.30 |
| Sonnet | Analysis, curation, assembly | ~$0.15 |
| Haiku | Timing optimization | ~$0.02 |
| **Total** | | **~$0.47/schedule** |

For 37 creators weekly: ~$17.40/week

---

## Future Enhancements

### Phase 2: Reinforcement Learning

Add feedback loop for continuous optimization:
1. Track actual vs projected earnings
2. Update caption performance scores
3. Adjust volume recommendations
4. Retrain timing model

### Phase 3: A/B Testing Framework

Enable schedule variant testing:
1. Generate 2 schedule variants
2. Random assignment
3. Track performance
4. Learn winning patterns

### Phase 4: Real-Time Adaptation

Add mid-week schedule adjustment:
1. Monitor real-time performance
2. Detect underperforming slots
3. Suggest swaps/additions
4. Auto-adjust future schedules

---

---

# IMPLEMENTATION PLAN: Wave-Based Agent Execution

## Overview

This implementation will be executed in **5 waves**, each handled by specialized agents to ensure 100% accuracy. Each wave has:
- **Primary Agent**: Responsible for implementation
- **Verification Agent**: Reviews and validates output
- **Quality Gate**: Must pass before next wave begins

```
WAVE 1 ──► WAVE 2 ──► WAVE 3 ──► WAVE 4 ──► WAVE 5
  MCP       Skill      Agents     DB         Test
 Server    Package   Definitions Migration   & QA
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
python-pro  command-  command-   sql-pro   code-reviewer
            architect  architect  database-  + debugger
                                 optimizer
```

---

## WAVE 1: MCP Database Server
**Priority**: CRITICAL (Foundation Layer)
**Estimated Tokens**: ~50K

### Primary Agent: `python-pro`
**Responsibilities**:
- Create `mcp/eros_db_server.py` with all 11 database tools
- Implement JSON-RPC protocol handler
- Add type-safe query builders
- Include error handling and validation

### Verification Agent: `code-reviewer`
**Checklist**:
- [ ] All 11 tools implemented correctly
- [ ] SQL injection prevention verified
- [ ] Error handling comprehensive
- [ ] JSON-RPC protocol compliance
- [ ] Database path resolution working

### Quality Gate
```bash
# Must pass before Wave 2
python3 mcp/eros_db_server.py --test
# Expected: All 11 tools respond correctly
```

### Files to Create
| File | Agent | Description |
|------|-------|-------------|
| `mcp/eros_db_server.py` | python-pro | Main MCP server |
| `mcp/__init__.py` | python-pro | Package init |
| `mcp/test_server.py` | python-pro | Test suite |

### Implementation Tasks (Wave 1)
```
1. [ ] Create mcp/ directory structure
2. [ ] Implement get_active_creators tool
3. [ ] Implement get_creator_profile tool
4. [ ] Implement get_top_captions tool
5. [ ] Implement get_best_timing tool
6. [ ] Implement get_performance_trends tool
7. [ ] Implement get_content_type_rankings tool
8. [ ] Implement get_persona_profile tool
9. [ ] Implement get_vault_availability tool
10. [ ] Implement save_schedule tool
11. [ ] Implement execute_query tool
12. [ ] Add JSON-RPC protocol handler
13. [ ] Add error handling
14. [ ] Create test suite
15. [ ] Run verification
```

---

## WAVE 2: Skill Package
**Priority**: HIGH (Entry Point)
**Estimated Tokens**: ~40K

### Primary Agent: `command-architect`
**Responsibilities**:
- Create skill directory structure
- Write comprehensive SKILL.md
- Create supporting documentation files
- Add usage examples

### Verification Agent: `technical-writer` + `code-reviewer`
**Checklist**:
- [ ] SKILL.md frontmatter valid (name, description)
- [ ] Description triggers discovery correctly
- [ ] All parameters documented
- [ ] Examples are executable
- [ ] Supporting docs complete

### Quality Gate
```bash
# Must pass before Wave 3
# Skill should appear in Claude Code skill list
# Test: "Generate schedule for miss_alexa" should invoke skill
```

### Files to Create
| File | Agent | Description |
|------|-------|-------------|
| `~/.claude/skills/eros-schedule-generator/SKILL.md` | command-architect | Main skill definition |
| `~/.claude/skills/eros-schedule-generator/OPTIMIZATION.md` | command-architect | Algorithm docs |
| `~/.claude/skills/eros-schedule-generator/TIMING.md` | command-architect | Timing rules |
| `~/.claude/skills/eros-schedule-generator/PERSONA_MATCHING.md` | command-architect | Voice matching |
| `~/.claude/skills/eros-schedule-generator/VOLUME_CALIBRATION.md` | command-architect | Volume logic |
| `~/.claude/skills/eros-schedule-generator/OUTPUT_FORMATS.md` | command-architect | Output templates |
| `~/.claude/skills/eros-schedule-generator/examples/*.md` | command-architect | Usage examples |

### Implementation Tasks (Wave 2)
```
1. [ ] Create skill directory structure
2. [ ] Write SKILL.md with complete specification
3. [ ] Write OPTIMIZATION.md (weighted scoring algorithm)
4. [ ] Write TIMING.md (hour/day optimization rules)
5. [ ] Write PERSONA_MATCHING.md (voice authenticity guidelines)
6. [ ] Write VOLUME_CALIBRATION.md (adaptive volume logic)
7. [ ] Write OUTPUT_FORMATS.md (JSON/Markdown templates)
8. [ ] Create single_creator.md example
9. [ ] Create batch_generation.md example
10. [ ] Create custom_parameters.md example
11. [ ] Verify skill discovery
12. [ ] Test invocation patterns
```

---

## WAVE 3: Agent Definitions
**Priority**: HIGH (Multi-Agent Core)
**Estimated Tokens**: ~35K

### Primary Agent: `command-architect`
**Responsibilities**:
- Create all 8 specialized agent definitions
- Configure proper tool access per agent
- Set optimal model selection
- Define clear responsibilities

### Verification Agent: `code-reviewer`
**Checklist**:
- [ ] All 8 agents created with valid frontmatter
- [ ] Tool access properly scoped (minimal privilege)
- [ ] Model selection optimized (Opus/Sonnet/Haiku)
- [ ] Agent descriptions trigger correctly
- [ ] Output formats specified

### Quality Gate
```bash
# Must pass before Wave 4
# Each agent should be invocable via Task tool
# Test: Invoke each agent with sample query
```

### Files to Create
| File | Agent | Model | Tools |
|------|-------|-------|-------|
| `~/.claude/agents/performance-analyst.md` | command-architect | Sonnet | MCP db tools |
| `~/.claude/agents/persona-matcher.md` | command-architect | Sonnet | MCP db tools |
| `~/.claude/agents/caption-selection-pro.md` | command-architect | Sonnet | MCP db tools |
| `~/.claude/agents/timing-optimizer.md` | command-architect | Haiku | MCP db tools |
| `~/.claude/agents/schedule-assembler.md` | command-architect | Sonnet | MCP db tools |
| `~/.claude/agents/quality-validator.md` | command-architect | Sonnet | MCP db tools |

### Implementation Tasks (Wave 3)
```
1. [ ] Create performance-analyst.md
2. [ ] Create persona-matcher.md
3. [ ] Create caption-selection-pro.md
4. [ ] Create timing-optimizer.md
5. [ ] Create schedule-assembler.md
6. [ ] Create quality-validator.md
7. [ ] Verify agent discovery
8. [ ] Test individual agent invocation
9. [ ] Verify tool access permissions
10. [ ] Test agent chaining
```

---

## WAVE 4: Database Enhancements
**Priority**: MEDIUM (Data Layer)
**Estimated Tokens**: ~25K

### Primary Agent: `sql-pro`
**Responsibilities**:
- Create migration file with schema changes
- Add schedule generation queue table
- Create readiness view
- Add algorithm metadata columns

### Verification Agent: `database-optimizer`
**Checklist**:
- [ ] Migration is idempotent (can run multiple times)
- [ ] Indexes properly configured
- [ ] Foreign keys maintained
- [ ] Views performant
- [ ] Rollback script included

### Quality Gate
```bash
# Must pass before Wave 5
sqlite3 eros_sd_main.db ".schema schedule_generation_queue"
sqlite3 eros_sd_main.db "SELECT * FROM v_schedule_ready_creators LIMIT 5"
```

### Files to Create
| File | Agent | Description |
|------|-------|-------------|
| `database/migrations/007_schedule_generator_enhancements.sql` | sql-pro | Schema changes |
| `database/migrations/007_rollback.sql` | sql-pro | Rollback script |

### Implementation Tasks (Wave 4)
```
1. [ ] Add algorithm_params to schedule_templates
2. [ ] Add agent_execution_log to schedule_templates
3. [ ] Add quality_validation_score to schedule_templates
4. [ ] Create schedule_generation_queue table
5. [ ] Create idx_sgq_status_priority index
6. [ ] Create v_schedule_ready_creators view
7. [ ] Create rollback script
8. [ ] Test migration on backup
9. [ ] Apply to production database
10. [ ] Verify all changes
```

---

## WAVE 5: Integration Testing & Quality Assurance
**Priority**: CRITICAL (Final Validation)
**Estimated Tokens**: ~60K

### Primary Agent: `code-reviewer`
**Responsibilities**:
- Full end-to-end testing
- Security audit
- Performance benchmarking
- Documentation verification

### Verification Agent: `debugger`
**Checklist**:
- [ ] MCP server connects and responds
- [ ] Skill invokes correctly
- [ ] All 8 agents work independently
- [ ] Agent orchestration works
- [ ] Database saves correctly
- [ ] Output format valid
- [ ] Error handling works

### Quality Gate
```bash
# FINAL ACCEPTANCE TESTS
# 1. Generate single schedule
> Generate schedule for miss_alexa

# 2. Verify database save
sqlite3 eros_sd_main.db "SELECT * FROM schedule_templates ORDER BY template_id DESC LIMIT 1"

# 3. Batch generation
> Generate schedules for all Tier 1 creators

# 4. Error handling
> Generate schedule for nonexistent_creator
```

### Implementation Tasks (Wave 5)
```
1. [ ] Test MCP server standalone
2. [ ] Test skill discovery
3. [ ] Test each agent individually
4. [ ] Test full orchestration pipeline
5. [ ] Test single creator generation
6. [ ] Test batch generation
7. [ ] Test custom parameters
8. [ ] Test error scenarios
9. [ ] Verify database integrity
10. [ ] Performance benchmark
11. [ ] Security audit
12. [ ] Documentation review
13. [ ] Create user guide
14. [ ] Final sign-off
```

---

## Wave Execution Protocol

### Before Each Wave
1. **Announce Wave**: State wave number and objectives
2. **Spawn Primary Agent**: Use Task tool with specified agent type
3. **Track Progress**: Update todo list with wave tasks
4. **Quality Gate**: Run verification before proceeding

### Wave Transition Rules
- **MUST NOT** proceed to next wave until current wave passes quality gate
- **MUST** have verification agent review all output
- **MUST** fix any issues before proceeding
- **CAN** run sub-tasks in parallel within a wave

### Agent Invocation Pattern
```
Wave 1: Task(python-pro) → Task(code-reviewer)
Wave 2: Task(command-architect) → Task(technical-writer) + Task(code-reviewer)
Wave 3: Task(command-architect) → Task(code-reviewer)
Wave 4: Task(sql-pro) → Task(database-optimizer)
Wave 5: Task(code-reviewer) → Task(debugger)
```

---

## Estimated Timeline

| Wave | Primary Work | Verification | Total |
|------|--------------|--------------|-------|
| Wave 1 | 20 min | 10 min | 30 min |
| Wave 2 | 25 min | 10 min | 35 min |
| Wave 3 | 20 min | 10 min | 30 min |
| Wave 4 | 15 min | 10 min | 25 min |
| Wave 5 | 30 min | 20 min | 50 min |
| **Total** | | | **~2.5 hours** |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| MCP server fails | Test standalone first, have fallback queries |
| Agent doesn't trigger | Verify frontmatter, check description keywords |
| Database migration breaks | Always backup first, have rollback script |
| Performance issues | Use Haiku for fast operations, limit parallel agents |
| Context overflow | Use MCP for data queries, keep agent prompts focused |

---

## Success Criteria

### Minimum Viable Product (MVP)
- [ ] Single creator schedule generation works
- [ ] Schedule saves to database correctly
- [ ] Output format is valid JSON/Markdown

### Full Product
- [ ] All 37 creators can be scheduled
- [ ] Batch generation works
- [ ] Custom parameters supported
- [ ] Quality validation passes
- [ ] Performance < 60 seconds per schedule

### Excellence Tier
- [ ] Projected earnings accuracy > 80%
- [ ] Caption authenticity score > 75 avg
- [ ] Content diversity score > 0.8
- [ ] Zero scheduling conflicts

---

## Summary

This blueprint provides a comprehensive, production-ready schedule generation system that:

1. **Leverages MAX 20X Tier**: Multi-agent orchestration with Opus coordination
2. **Uses All Database Data**: 53 tables, 70K+ messages, 58K+ captions
3. **Optimizes for Revenue**: Performance-weighted caption selection, timing optimization
4. **Maintains Authenticity**: Persona matching ensures creator voice
5. **Adapts Over Time**: Saturation/opportunity signals for volume calibration

**Implementation**: 5 waves with specialized agents
**Quality Assurance**: Verification agent per wave
**Total Setup Time**: ~2.5 hours
**Components**: MCP server, 1 skill, 8 agents, 1 migration

---

## Sources

- [Anthropic Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Claude Agent SDK Best Practices 2025](https://skywork.ai/blog/claude-agent-sdk-best-practices-ai-agents-2025/)
- [OnlyFans Scheduling Best Practices](https://www.supercreator.app/guides/scheduling-feature-onlyfans)
- [Best Time to Post on OnlyFans](https://www.supercreator.app/guides/best-time-to-post-on-onlyfans)
- [Dynamic Pricing with Reinforcement Learning](https://towardsdatascience.com/dynamic-pricing-using-reinforcement-learning-and-neural-networks-cc3abe374bf5/)
- [Schedule Optimization Approaches](https://www.altexsoft.com/blog/schedule-optimization/)

---

## Troubleshooting Guide

### Common Volume Calculation Issues

#### Issue: Volume too low despite high fan count

**Symptoms:**
- Creator with 10K+ fans gets LOW tier volumes
- `final_config` shows 2-3 sends/day when expecting 5+

**Root Causes & Solutions:**

1. **High Saturation Score (>70)**
   - Check `fused_saturation` in OptimizedVolumeResult
   - If saturation >70, volume is intentionally reduced (0.7x multiplier)
   - **Solution**: Review recent message frequency. If over-sending, accept the reduction. If data is stale, update `volume_performance_tracking` table.

2. **Confidence Dampening Applied**
   - Check `confidence_score` - if <0.6, multipliers are dampened
   - Low `message_count` (<50) triggers conservative volumes
   - **Solution**: Wait for more historical data to accumulate, or manually override with higher base tier.

3. **Elasticity Cap Applied**
   - Check `elasticity_capped` - if True, diminishing returns detected
   - Revenue per send is declining at current volume
   - **Solution**: Accept the cap (it's protecting ROI), or investigate why engagement is dropping.

**Diagnostic Query:**
```python
result = calculate_optimized_volume(context, creator_id="...")
print(f"Tier: {result.final_config.tier}")
print(f"Saturation: {result.fused_saturation}")
print(f"Confidence: {result.confidence_score}")
print(f"Elasticity capped: {result.elasticity_capped}")
print(f"Modules: {result.adjustments_applied}")
```

---

#### Issue: Divergence warnings appearing frequently

**Symptoms:**
- `divergence_detected=True` in many calculations
- Rapid weight shifts between default and rapid-change weights

**Root Causes & Solutions:**

1. **Actual Trend Change**
   - Short-term (7d) performance diverging from long-term (30d) baseline
   - This is normal when creator strategy changes or content mix shifts
   - **Solution**: No action needed - this is the system adapting to real changes.

2. **Volatile Recent Data**
   - Very few messages in 7d period causing noise
   - Check `horizons['7d'].message_count` - if <10, divergence may be false positive
   - **Solution**: Increase `MIN_TOTAL_MESSAGES` threshold in multi_horizon.py or wait for more data.

3. **Stale 30d Baseline**
   - Long-term average hasn't caught up to sustained change
   - Check if 14d also diverges from 30d
   - **Solution**: Consider shortening analysis window from 30d to 21d in config.

**Diagnostic Query:**
```python
from python.volume.multi_horizon import MultiHorizonAnalyzer

analyzer = MultiHorizonAnalyzer(db_path)
result = analyzer.analyze("creator_id")

print(f"7d saturation: {result.horizons['7d'].saturation_score}")
print(f"30d saturation: {result.horizons['30d'].saturation_score}")
print(f"Divergence: {result.divergence_amount} points")
print(f"Direction: {result.divergence_direction}")
```

---

#### Issue: Weekly distribution not adding up correctly

**Symptoms:**
- `sum(weekly_distribution.values()) != final_config.total_per_day * 7`
- Some days have 0 volume

**Root Causes & Solutions:**

1. **Rounding Errors**
   - Integer rounding can cause ±1 discrepancy
   - **Solution**: This is acceptable (<5% error). Use `total_weekly_volume` property which handles normalization.

2. **Missing DOW Data**
   - Some days have no historical performance data
   - Falls back to default multipliers (1.0)
   - **Solution**: Ensure `mass_messages.sending_day_of_week` is populated for all messages.

3. **Extreme Multipliers Clamped**
   - Multipliers are clamped to 0.7-1.3 range
   - Very high/low performance days get bounded
   - **Solution**: This is intentional to prevent extreme swings. Adjust `MULTIPLIER_MIN/MAX` in `day_of_week.py` if needed.

**Diagnostic Query:**
```python
result = calculate_optimized_volume(context, creator_id="...")
total = sum(result.weekly_distribution.values())
expected = result.final_config.total_per_day * 7

print(f"Total: {total}, Expected: {expected}, Diff: {total - expected}")
print(f"DOW multipliers: {result.dow_multipliers_used}")
```

---

#### Issue: Caption warnings but captions exist

**Symptoms:**
- `has_warnings=True` with warnings about caption shortages
- Caption bank query shows 50+ captions available

**Root Causes & Solutions:**

1. **Wrong Caption Type Filter**
   - Captions exist but wrong `caption_type` for the send type
   - Check `send_type_caption_requirements` table for correct mappings
   - **Solution**: Update caption bank entries to use correct `caption_type` values.

2. **Freshness Threshold Too High**
   - Captions marked as stale (`freshness_score < 30`)
   - All captions recently used (within 30 days)
   - **Solution**: Lower `min_freshness` parameter or create new caption variations.

3. **Performance Filter Too Strict**
   - Captions filtered out by `min_performance` threshold (default 40)
   - **Solution**: Lower threshold or review why captions are underperforming.

**Diagnostic Query:**
```python
from python.volume.caption_constraint import CaptionPoolAnalyzer

analyzer = CaptionPoolAnalyzer(db_path)
status = analyzer.analyze("creator_id")

print(f"Total types: {status.total_types}")
print(f"Critical types: {status.critical_types}")

for type_name, avail in status.caption_availability.items():
    print(f"{type_name}: {avail.total_captions} total, {avail.usable_captions} usable")
```

---

#### Issue: Confidence score always low (<0.6)

**Symptoms:**
- `confidence_score` consistently below 0.6
- `is_high_confidence=False`
- Multipliers being dampened when creator has plenty of data

**Root Causes & Solutions:**

1. **Low Total Message Count**
   - Check `message_count` field - if <50, confidence will be low
   - Not enough historical data accumulated yet
   - **Solution**: Wait for 50+ messages, or manually override confidence thresholds in `CONFIDENCE_TIERS`.

2. **Multi-Horizon Data Missing**
   - Only 1 or 2 horizons (7d/14d/30d) have data
   - Check `data_quality` from multi-horizon fusion
   - **Solution**: Ensure `volume_performance_tracking` is being updated regularly for all periods.

3. **Data Quality Issues**
   - Messages exist but have NULL values for key metrics
   - **Solution**: Run data quality audit on `mass_messages` table - check for NULL `earnings`, `view_rate`, `purchase_rate`.

**Diagnostic Query:**
```python
result = calculate_optimized_volume(context, creator_id="...")
print(f"Message count: {result.message_count}")
print(f"Confidence: {result.confidence_score}")

# Check horizon data quality
from python.volume.multi_horizon import fetch_horizon_scores
conn = sqlite3.connect(db_path)
horizons = fetch_horizon_scores(conn, "creator_id")
for period, scores in horizons.items():
    print(f"{period}: available={scores.is_available}, msgs={scores.message_count}")
```

---

#### Issue: Elasticity cap triggering incorrectly

**Symptoms:**
- `elasticity_capped=True` for creators with healthy metrics
- Revenue per send is stable or increasing but cap still applies

**Root Causes & Solutions:**

1. **Insufficient Volume Range**
   - Need at least 3 different volume levels in historical data
   - Creator has been stuck at same volume tier
   - **Solution**: Vary send volume for 2-3 weeks to build elasticity curve data.

2. **Outlier Data Points**
   - One or two extremely high/low revenue days skewing the fit
   - Check `volume_performance_data` for anomalies
   - **Solution**: Filter outliers in `fetch_volume_performance_data()` or adjust `DEFAULT_DECAY_RATE`.

3. **Model Not Converging**
   - Exponential decay model fails to fit data
   - Falls back to conservative defaults
   - **Solution**: Increase `MIN_DATA_POINTS` in elasticity.py to 5+ for more reliable fits.

**Diagnostic Query:**
```python
from python.volume.elasticity import ElasticityOptimizer

optimizer = ElasticityOptimizer(db_path)
profile = optimizer.get_profile("creator_id")

print(f"Has data: {profile.has_sufficient_data}")
print(f"Data points: {len(profile.data_points)}")
print(f"Parameters: {profile.parameters}")

if profile.parameters.is_reliable:
    for vol in range(1, 10):
        rps = optimizer.estimate_rps(vol)
        print(f"Vol {vol}: RPS ${rps:.2f}")
```

---

### Performance Optimization Tips

#### Optimize MCP Tool Response Times

**Problem:** `get_volume_config` taking >2 seconds to execute

**Solutions:**

1. **Index Optimization**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_vpt_creator_period
   ON volume_performance_tracking(creator_id, tracking_period, tracking_date DESC);

   CREATE INDEX IF NOT EXISTS idx_mm_creator_dow
   ON mass_messages(creator_id, sending_day_of_week);
   ```

2. **Precompute Scores**
   - Run nightly job to update `volume_performance_tracking` for all creators
   - Avoid on-demand score calculation from `mass_messages` raw data

3. **Cache Results**
   - Implement result caching with 1-hour TTL
   - Return cached result if `tracking_date` hasn't changed

---

#### Reduce Module Execution Time

**Problem:** `calculate_optimized_volume` taking >5 seconds

**Solutions:**

1. **Skip Optional Modules**
   ```python
   # For quick estimates, skip tracking and content weighting
   result = calculate_optimized_volume(
       context,
       creator_id="...",
       track_prediction=False,  # Skip prediction logging
   )
   ```

2. **Batch Processing**
   - Use connection pooling for multiple creators
   - Reuse database connection across calculations

3. **Parallel Module Execution**
   - DOW, Content, and Caption modules are independent
   - Can run in parallel threads/processes

---

### Debugging Tools

#### Enable Debug Logging

```python
import logging
from python.logging_config import get_logger

# Set volume module to DEBUG level
logger = get_logger("python.volume")
logger.setLevel(logging.DEBUG)

# Now run calculation
result = calculate_optimized_volume(context, creator_id="...")
# Debug logs will show each module's decisions
```

#### Inspect Intermediate Results

```python
from python.volume.dynamic_calculator import (
    calculate_dynamic_volume,
    get_volume_tier,
    PerformanceContext,
)

context = PerformanceContext(...)

# Step-by-step inspection
tier = get_volume_tier(context.fan_count)
print(f"Tier: {tier}")

base_config = calculate_dynamic_volume(context, use_smooth_interpolation=False)
print(f"Base config (step): {base_config}")

smooth_config = calculate_dynamic_volume(context, use_smooth_interpolation=True)
print(f"Smooth config: {smooth_config}")

# Compare
print(f"Difference: revenue {smooth_config.revenue_per_day - base_config.revenue_per_day}")
```

#### Validate Module Integration

```python
# Test each module independently
from python.volume.multi_horizon import MultiHorizonAnalyzer
from python.volume.confidence import calculate_confidence
from python.volume.day_of_week import calculate_dow_multipliers
from python.volume.elasticity import ElasticityOptimizer
from python.volume.content_weighting import ContentWeightingOptimizer
from python.volume.caption_constraint import CaptionPoolAnalyzer

db_path = "./database/eros_sd_main.db"
creator_id = "alexia"

# Test each
mh = MultiHorizonAnalyzer(db_path)
mh_result = mh.analyze(creator_id)
print(f"Multi-horizon: {mh_result.saturation_score}")

conf = calculate_confidence(150)
print(f"Confidence: {conf.confidence}")

dow = calculate_dow_multipliers(creator_id, db_path)
print(f"DOW: {dow.multipliers}")

elast = ElasticityOptimizer(db_path)
elast_profile = elast.get_profile(creator_id)
print(f"Elasticity: {elast_profile.parameters}")

content = ContentWeightingOptimizer(db_path)
content_profile = content.get_profile(creator_id)
print(f"Content: {content_profile.top_types}")

captions = CaptionPoolAnalyzer(db_path)
caption_status = captions.analyze(creator_id)
print(f"Captions: {caption_status.sufficient_coverage}")
```

---

### Data Quality Checks

#### Verify Volume Performance Tracking

```sql
-- Check coverage of tracking data
SELECT
    creator_id,
    tracking_period,
    COUNT(*) as record_count,
    MAX(tracking_date) as latest_date,
    AVG(saturation_score) as avg_saturation,
    AVG(opportunity_score) as avg_opportunity
FROM volume_performance_tracking
WHERE tracking_date >= date('now', '-30 days')
GROUP BY creator_id, tracking_period
ORDER BY creator_id, tracking_period;
```

#### Validate Mass Messages Data

```sql
-- Check for NULL/invalid data
SELECT
    creator_id,
    COUNT(*) as total_messages,
    SUM(CASE WHEN earnings IS NULL THEN 1 ELSE 0 END) as null_earnings,
    SUM(CASE WHEN view_rate IS NULL THEN 1 ELSE 0 END) as null_view_rate,
    SUM(CASE WHEN purchase_rate IS NULL THEN 1 ELSE 0 END) as null_purchase_rate,
    SUM(CASE WHEN sending_day_of_week IS NULL THEN 1 ELSE 0 END) as null_dow
FROM mass_messages
WHERE sending_time >= date('now', '-60 days')
GROUP BY creator_id;
```

#### Check Caption Pool Health

```sql
-- Caption availability by type
SELECT
    cb.caption_type,
    COUNT(*) as total_captions,
    AVG(cb.freshness_score) as avg_freshness,
    AVG(cb.performance_score) as avg_performance,
    SUM(CASE WHEN cb.freshness_score >= 30 AND cb.performance_score >= 40 THEN 1 ELSE 0 END) as usable_captions
FROM caption_bank cb
WHERE cb.is_active = 1
GROUP BY cb.caption_type
ORDER BY usable_captions ASC;
```

---

*Version 2.0.5 | Last Updated: 2025-12-16*
