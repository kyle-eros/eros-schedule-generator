---
title: Data Contracts - EROS Schedule Generator Pipeline
version: 2.3.0
created: 2025-12-17
description: Explicit JSON schemas for all data flowing between agents in the 9-phase schedule generation pipeline
status: authoritative
---

# Data Contracts: EROS Schedule Generator Pipeline

## Overview

This document defines the **explicit data contracts** for all data flowing between agents in the EROS Schedule Generator's 9-phase pipeline. Each agent transition specifies required fields, optional fields, validation rules, and example payloads.

### Pipeline Flow

```
Phase 1: performance-analyst → performance_metrics
Phase 2: send-type-allocator → allocation + strategy_metadata
Phase 3: content-curator → caption_assignments
Phase 4: timing-optimizer → timing_assignments
Phase 5: followup-generator → followup_items
Phase 6: authenticity-engine → humanized_items [NEW]
Phase 7: schedule-assembler → assembled_schedule
Phase 8: revenue-optimizer → priced_schedule [NEW]
Phase 9: quality-validator → validation_result
```

**Critical Note**: The `strategy_metadata` output from Phase 2 MUST be preserved through all downstream phases and passed to quality-validator for diversity validation.

---

## Common Data Types

### Date and Time Types

```typescript
type ISODate = string;              // Format: YYYY-MM-DD (e.g., "2025-12-16")
type ISOTime = string;              // Format: HH:MM:SS (e.g., "19:07:00")
type ISODateTime = string;          // Format: YYYY-MM-DDTHH:MM:SSZ (e.g., "2025-12-16T19:07:00Z")
type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;  // Monday=0, Sunday=6
```

### Enumerated Types

```typescript
// Page types
type PageType = "paid" | "free";

// Send type categories
type SendTypeCategory = "revenue" | "engagement" | "retention";

// Send type keys (22 types)
type SendTypeKey =
  // Revenue (9 types)
  | "ppv_unlock"          // Primary PPV unlock (replaces legacy ppv_video and ppv_message)
  | "ppv_wall"            // Wall PPV post (FREE pages only)
  | "tip_goal"            // Tip goal campaigns (PAID pages only, 3 modes)
  | "bundle"              // Content bundle
  | "flash_bundle"        // Time-limited bundle
  | "game_post"           // Interactive game
  | "first_to_tip"        // Tip competition
  | "vip_program"         // VIP membership upsell
  | "snapchat_bundle"     // Snapchat access package
  // Engagement (9 types)
  | "bump_normal"         // Standard conversation bump
  | "bump_descriptive"    // Detailed story bump
  | "bump_text_only"      // Text-only bump
  | "bump_flyer"          // Visual promotional bump
  | "link_drop"           // Link reminder (DM)
  | "wall_link_drop"      // Link on feed wall
  | "dm_farm"             // DM engagement cultivation
  | "like_farm"           // Like engagement boost
  | "live_promo"          // Live stream promotion
  // Retention (4 types)
  | "renew_on_post"       // Renewal reminder via post (PAID only)
  | "renew_on_message"    // Renewal reminder via DM (PAID only)
  | "ppv_followup"        // Follow-up on unopened PPV
  | "expired_winback";    // Reactivation for churned (PAID only)

// Channel keys
type ChannelKey =
  | "mass_message"       // Mass DM to segment
  | "targeted_message"   // Targeted DM to specific segment
  | "wall_post"          // Public feed post
  | "story"              // 24-hour story
  | "live";              // Live stream

// Audience target keys
type TargetKey =
  | "all_active"           // All active subscribers
  | "all_followers"        // All followers (free page)
  | "active_7d"            // Active in last 7 days
  | "active_30d"           // Active in last 30 days
  | "tippers"              // Users who have tipped
  | "high_spenders"        // Top 20% spenders
  | "ppv_non_purchasers"   // Viewed PPV but didn't buy
  | "expired_recent"       // Expired within 30 days
  | "expiring_soon"        // Expires within 7 days
  | "renew_off"            // Renewal auto-renew off
  | "renew_on"             // Renewal auto-renew on
  | "non_tippers"          // Haven't tipped on tip_goal (alias: tip_goal_non_tippers)
  | "tip_goal_non_tippers"; // Alias for non_tippers - used for tip_goal followups

// Media types
type MediaType = "none" | "picture" | "gif" | "video" | "flyer";

// Volume levels
type VolumeLevel = "LOW" | "MID" | "HIGH" | "ULTRA";

// Confidence levels
type ConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";

// Calculation sources
type CalculationSource = "optimized" | "fallback" | "static" | "unknown";

// Validation status
type ValidationStatus = "APPROVED" | "NEEDS_REVIEW" | "REJECTED";
```

---

## Phase 1: INITIALIZATION → Performance Metrics

### Agent: performance-analyst

**Inputs**:
```typescript
interface PerformanceAnalystInput {
  creator_id: string;                    // Required
  period: "7d" | "14d" | "30d";          // Default: "14d"
}
```

**Output Contract**:
```typescript
interface PerformanceMetrics {
  // Required fields
  creator_id: string;
  analysis_period: string;               // "7d", "14d", or "30d"

  // Core metrics
  metrics: {
    saturation_score: number;            // 0-100 (higher = overexposed)
    opportunity_score: number;           // 0-100 (higher = growth potential)
    fused_saturation: number;            // 0-100 (multi-horizon fusion, PREFERRED)
    fused_opportunity: number;           // 0-100 (multi-horizon fusion, PREFERRED)
    confidence_score: number;            // 0.0-1.0 (algorithm confidence)
    revenue_trend: string;               // "+8%", "0%", "-5%"
    engagement_trend: string;            // "+12%", "0%", "-3%"
    fan_growth: string;                  // "+3%", "0%", "-2%"
    elasticity_capped: boolean;          // True if volume capped by elasticity
  };

  // Algorithm metadata
  algorithm_metadata: {
    adjustments_applied: string[];       // e.g., ["base_tier", "multi_horizon_fusion", ...]
    prediction_id: number | null;        // For accuracy tracking
    calculation_source: CalculationSource; // "optimized" or "fallback"
  };

  // Content performance
  content_analysis: {
    top_performers: string[];            // e.g., ["solo", "lingerie", "tease"]
    mid_performers: string[];            // e.g., ["pov", "toy"]
    underperformers: string[];           // e.g., ["feet"]
    avoid: string[];                     // Types to skip entirely
  };

  // Status classifications
  saturation_status: "healthy" | "caution" | "saturated";
  opportunity_status: "maintain" | "moderate" | "high";
  confidence_status: ConfidenceLevel;    // "LOW", "MEDIUM", "HIGH"

  // Warnings and recommendations
  caption_warnings: string[];            // e.g., ["Low captions for ppv_followup: <3 usable"]
  recommendations: Array<{
    type: string;                        // e.g., "prioritize_content", "reduce_volume"
    action: string;                      // Human-readable action
    reason: string;                      // Justification
    impact: "low" | "medium" | "high";   // Importance
  }>;
}
```

**Example Payload**:
```json
{
  "creator_id": "alexia",
  "analysis_period": "14d",
  "metrics": {
    "saturation_score": 45,
    "opportunity_score": 62,
    "fused_saturation": 43.5,
    "fused_opportunity": 64.2,
    "confidence_score": 0.85,
    "revenue_trend": "+8%",
    "engagement_trend": "+12%",
    "fan_growth": "+3%",
    "elasticity_capped": false
  },
  "algorithm_metadata": {
    "adjustments_applied": ["base_tier", "multi_horizon_fusion", "day_of_week", "content_weighting"],
    "prediction_id": 123,
    "calculation_source": "optimized"
  },
  "content_analysis": {
    "top_performers": ["solo", "lingerie", "tease"],
    "mid_performers": ["pov", "toy"],
    "underperformers": ["feet"],
    "avoid": []
  },
  "saturation_status": "healthy",
  "opportunity_status": "moderate",
  "confidence_status": "HIGH",
  "caption_warnings": [],
  "recommendations": [
    {
      "type": "prioritize_content",
      "action": "Schedule more solo and lingerie content",
      "reason": "Top 3 performing content types",
      "impact": "high"
    }
  ]
}
```

**Validation Rules**:
- `confidence_score` must be 0.0-1.0
- `saturation_score` and `opportunity_score` must be 0-100
- `fused_saturation` and `fused_opportunity` must be 0-100
- `adjustments_applied` must contain at least `["base_tier"]`
- `calculation_source` must be one of: "optimized", "fallback", "static", "unknown"

---

## Phase 1: OptimizedVolumeResult (from get_volume_config)

### MCP Tool: get_volume_config

**Output Contract**:
```typescript
interface OptimizedVolumeResult {
  // Legacy fields (backward compatible)
  volume_level: VolumeLevel;             // "LOW", "MID", "HIGH", "ULTRA"
  ppv_per_day: number;                   // 1-8 (deprecated, use revenue_per_day)
  bump_per_day: number;                  // 1-6 (deprecated, use engagement_per_day)

  // Category volumes (REQUIRED - use these)
  revenue_per_day: number;               // 1-8 items/day
  engagement_per_day: number;            // 1-6 items/day
  retention_per_day: number;             // 0-4 items/day (0 for free pages)

  // Weekly distribution (CRITICAL - pre-computed DOW adjustments)
  weekly_distribution: {
    [key: DayOfWeek]: number;            // Day 0-6 → total items for that day
  };
  dow_multipliers_used: {
    [key: DayOfWeek]: number;            // Day 0-6 → multiplier applied (0.9-1.2)
  };

  // Content-type allocation (performance-weighted)
  content_allocations: {
    [content_type: string]: number;      // e.g., {"solo": 3, "lingerie": 2}
  };

  // Multi-horizon fusion metrics
  fused_saturation: number;              // 0-100 (7d/14d/30d fusion)
  fused_opportunity: number;             // 0-100 (7d/14d/30d fusion)
  divergence_detected: boolean;          // True if horizons disagree significantly

  // Data quality indicators
  confidence_score: number;              // 0.0-1.0 (prediction reliability)
  message_count: number;                 // Messages analyzed for calculation

  // Adjustment flags
  elasticity_capped: boolean;            // True if diminishing returns applied
  adjustments_applied: string[];         // Full audit trail

  // Warnings (MUST surface to Phase 9)
  caption_warnings: string[];            // e.g., ["Low captions for ppv_followup: <3 usable"]

  // Tracking
  prediction_id: number | null;          // For accuracy measurement
  calculation_source: CalculationSource; // "optimized" or "fallback"
  data_source: string;                   // "volume_performance_tracking" or other
}
```

**Example Payload**:
```json
{
  "volume_level": "HIGH",
  "ppv_per_day": 6,
  "bump_per_day": 5,
  "revenue_per_day": 6,
  "engagement_per_day": 5,
  "retention_per_day": 2,
  "weekly_distribution": {
    "0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13
  },
  "dow_multipliers_used": {
    "0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0
  },
  "content_allocations": {
    "solo": 3, "lingerie": 2, "outdoor": 1
  },
  "fused_saturation": 45.0,
  "fused_opportunity": 62.0,
  "divergence_detected": false,
  "confidence_score": 0.85,
  "message_count": 156,
  "elasticity_capped": false,
  "adjustments_applied": [
    "base_tier_calculation",
    "multi_horizon_fusion",
    "dow_multipliers",
    "content_weighting",
    "prediction_tracked"
  ],
  "caption_warnings": [],
  "prediction_id": 123,
  "calculation_source": "optimized",
  "data_source": "volume_performance_tracking"
}
```

**Validation Rules**:
- `weekly_distribution` must have exactly 7 entries (keys "0"-"6")
- `dow_multipliers_used` must have exactly 7 entries (keys "0"-"6")
- Sum of `weekly_distribution` values should approximately equal `(revenue_per_day + engagement_per_day + retention_per_day) * 7`
- `confidence_score` must be 0.0-1.0
- `fused_saturation` and `fused_opportunity` must be 0-100
- If `caption_warnings` is non-empty, downstream agents MUST process it

---

## Phase 2: SEND TYPE ALLOCATION → Allocation + Strategy Metadata

### Agent: send-type-allocator

**Inputs**:
```typescript
interface SendTypeAllocatorInput {
  creator_id: string;                    // Required
  week_start: ISODate;                   // Required (e.g., "2025-12-16")
  page_type: PageType;                   // Required: "paid" or "free"
  performance_metrics: PerformanceMetrics; // From performance-analyst
  volume_config: OptimizedVolumeResult;  // From get_volume_config()
  custom_focus?: SendTypeCategory;       // Optional: "revenue", "engagement", "retention"
}
```

**Output Contract**:
```typescript
interface AllocationResult {
  // Metadata
  creator_id: string;
  week_start: ISODate;
  page_type: PageType;

  // Volume configuration used
  volume_source: CalculationSource;      // "optimized" or "fallback"
  confidence_score: number;              // 0.0-1.0 from volume_config

  // Weekly distribution metadata
  weekly_distribution_used: {
    [key: DayOfWeek]: number;            // Actual per-day totals used
  };
  dow_multipliers_applied: {
    [key: DayOfWeek]: number;            // DOW multipliers that were applied
  };
  content_weights_applied: {
    [content_type: string]: number;      // Content weighting used
  };

  // Fused metrics (from OptimizedVolumeResult)
  fused_metrics: {
    saturation: number;                  // 0-100
    opportunity: number;                 // 0-100
  };

  // Daily allocations
  allocation: {
    [date: ISODate]: AllocationItem[];   // Array of items per day
  };

  // **CRITICAL**: Strategy metadata (MUST be preserved and passed to quality-validator)
  strategy_metadata: {
    [date: ISODate]: DailyStrategy;
  };

  // Summary statistics
  summary: {
    total_items: number;
    revenue_items: number;
    engagement_items: number;
    retention_items: number;
    unique_types_used: number;           // Must be >= 10
    confidence_score: number;
    confidence_level: ConfidenceLevel;
    adjustments_applied: string[];
    type_breakdown: {
      [sendType: SendTypeKey]: number;
    };
  };

  // Confidence metadata
  confidence_metadata: {
    score: number;                       // 0.0-1.0
    level: ConfidenceLevel;              // "LOW", "MEDIUM", "HIGH"
    adjustments_applied: string[];
    notes: string[];
    recommendation: "conservative" | "standard" | "optimized";
    elasticity_capped: boolean;
    caption_warnings: string[];
  };

  // Validation
  validation: {
    diversity_check: "PASSED" | "FAILED";
    unique_types: number;                // Must be >= 10
    category_balance: "PASSED" | "FAILED";
    page_type_valid: "PASSED" | "FAILED"; // Validates FREE/PAID constraints
  };
}

interface AllocationItem {
  slot: number;                          // 1-based slot number for the day
  send_type_key: SendTypeKey;            // Required
  category: SendTypeCategory;            // "revenue", "engagement", "retention"
  priority: 1 | 2 | 3;                   // 1=highest (revenue), 2=engagement, 3=retention
}

interface DailyStrategy {
  strategy_used: string;                 // e.g., "balanced_spread", "revenue_front"
  flavor_emphasis: SendTypeKey;          // Send type to emphasize this day
  flavor_avoid: SendTypeKey | null;      // Send type to de-emphasize this day
}
```

**Example Payload**:
```json
{
  "creator_id": "alexia",
  "week_start": "2025-12-16",
  "page_type": "paid",
  "volume_source": "optimized",
  "confidence_score": 0.85,
  "weekly_distribution_used": {
    "0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13
  },
  "dow_multipliers_applied": {
    "0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0
  },
  "content_weights_applied": {
    "solo": 3, "lingerie": 2, "tease": 2
  },
  "fused_metrics": {
    "saturation": 45.0,
    "opportunity": 62.0
  },
  "allocation": {
    "2025-12-16": [
      {"slot": 1, "send_type_key": "ppv_unlock", "category": "revenue", "priority": 1},
      {"slot": 2, "send_type_key": "bump_normal", "category": "engagement", "priority": 2},
      {"slot": 3, "send_type_key": "bundle", "category": "revenue", "priority": 1},
      {"slot": 4, "send_type_key": "link_drop", "category": "engagement", "priority": 2},
      {"slot": 5, "send_type_key": "tip_goal", "category": "revenue", "priority": 1}
    ],
    "2025-12-17": [
      {"slot": 1, "send_type_key": "ppv_unlock", "category": "revenue", "priority": 1},
      {"slot": 2, "send_type_key": "bump_descriptive", "category": "engagement", "priority": 2},
      {"slot": 3, "send_type_key": "game_post", "category": "revenue", "priority": 1},
      {"slot": 4, "send_type_key": "dm_farm", "category": "engagement", "priority": 2}
    ]
  },
  "strategy_metadata": {
    "2025-12-16": {
      "strategy_used": "balanced_spread",
      "flavor_emphasis": "bundle",
      "flavor_avoid": "game_post"
    },
    "2025-12-17": {
      "strategy_used": "revenue_front",
      "flavor_emphasis": "dm_farm",
      "flavor_avoid": "like_farm"
    }
  },
  "summary": {
    "total_items": 78,
    "revenue_items": 35,
    "engagement_items": 33,
    "retention_items": 10,
    "unique_types_used": 15,
    "confidence_score": 0.85,
    "confidence_level": "HIGH",
    "adjustments_applied": ["base_tier", "multi_horizon_fusion", "day_of_week", "content_weighting"],
    "type_breakdown": {
      "ppv_unlock": 10,
      "tip_goal": 8,
      "bundle": 5,
      "flash_bundle": 4,
      "bump_normal": 7,
      "bump_descriptive": 5,
      "dm_farm": 4
    }
  },
  "confidence_metadata": {
    "score": 0.85,
    "level": "HIGH",
    "adjustments_applied": ["base_tier", "multi_horizon_fusion", "day_of_week", "content_weighting"],
    "notes": ["HIGH CONFIDENCE: Strong historical data. Predictions are highly reliable."],
    "recommendation": "optimized",
    "elasticity_capped": false,
    "caption_warnings": []
  },
  "validation": {
    "diversity_check": "PASSED",
    "unique_types": 15,
    "category_balance": "PASSED",
    "page_type_valid": "PASSED"
  }
}
```

**Validation Rules**:
- `unique_types_used` must be >= 10 (minimum diversity requirement)
- `strategy_metadata` MUST be present and have entries for all 7 days
- At least 3 different `strategy_used` values across the week
- FREE pages must NOT contain `tip_goal`
- PAID pages must NOT contain `ppv_wall`
- Revenue items >= 40% of total
- Engagement items >= 25% of total
- `vip_program` count <= 1 per week
- `snapchat_bundle` count <= 1 per week

---

## Phase 3: CONTENT CURATION → Caption Assignments

### Agent: content-curator

**Inputs**:
```typescript
interface ContentCuratorInput {
  schedule_items: AllocationItem[];      // From send-type-allocator
  creator_id: string;                    // Required
  used_caption_ids: Set<number>;         // Track duplicates across week
  volume_config: OptimizedVolumeResult;  // For content_allocations and caption_warnings
}
```

**Output Contract**:
```typescript
interface CaptionAssignmentResult {
  items: CaptionAssignedItem[];

  // Metadata
  content_weighting_applied: boolean;
  caption_warnings_processed: string[]; // From volume_config
  confidence_threshold_adjustment: "none" | "relaxed" | "conservative";

  // Coverage statistics
  caption_coverage: {
    total_items: number;
    with_caption: number;
    needs_manual: number;
    coverage_rate: number;               // Percentage (0-100)
  };

  // Manual caption items (needs_manual_caption=true)
  manual_caption_items: ManualCaptionItem[];
}

interface CaptionAssignedItem extends AllocationItem {
  // Required caption assignment
  caption_id: number | null;             // Null if needs_manual_caption=true
  caption_text: string | null;           // Null if needs_manual_caption=true
  content_type: string;                  // e.g., "solo", "lingerie"

  // Caption scoring
  caption_scores: {
    performance: number;                 // 0-100
    freshness: number;                   // 0-100
    content_weight_bonus: number;        // 0-25 (from content_allocations)
    composite: number;                   // Final weighted score
  };

  // Flags
  needs_manual_caption: boolean;         // True if no automated caption found
  caption_warning?: string;              // Reason if needs_manual=true
  fallback_level?: number;               // 1-6 (6=manual)
}

interface ManualCaptionItem {
  send_type_key: SendTypeKey;
  scheduled_date: ISODate;
  scheduled_time?: ISOTime;              // May not be assigned yet
  reason: string;                        // Why manual caption is needed
}
```

**Example Payload**:
```json
{
  "items": [
    {
      "slot": 1,
      "send_type_key": "ppv_unlock",
      "category": "revenue",
      "priority": 1,
      "caption_id": 789,
      "caption_text": "Hey babe, I made this just for you...",
      "content_type": "solo",
      "caption_scores": {
        "performance": 85.2,
        "freshness": 92.0,
        "content_weight_bonus": 15.0,
        "composite": 87.92
      },
      "needs_manual_caption": false
    },
    {
      "slot": 5,
      "send_type_key": "vip_program",
      "category": "revenue",
      "priority": 1,
      "caption_id": null,
      "caption_text": null,
      "content_type": "vip",
      "caption_scores": {
        "performance": 0,
        "freshness": 0,
        "content_weight_bonus": 0,
        "composite": 0
      },
      "needs_manual_caption": true,
      "caption_warning": "No VIP captions with sufficient freshness",
      "fallback_level": 6
    }
  ],
  "content_weighting_applied": true,
  "caption_warnings_processed": [],
  "confidence_threshold_adjustment": "none",
  "caption_coverage": {
    "total_items": 78,
    "with_caption": 76,
    "needs_manual": 2,
    "coverage_rate": 97.4
  },
  "manual_caption_items": [
    {
      "send_type_key": "vip_program",
      "scheduled_date": "2025-12-18",
      "reason": "No VIP captions with sufficient freshness"
    }
  ]
}
```

**Validation Rules**:
- Each item must have either `caption_id` OR `needs_manual_caption=true`
- `caption_scores.freshness` should be >= 30 (or lower if low confidence)
- `caption_scores.performance` should be >= 40 (or lower if low confidence)
- No duplicate `caption_id` values across all items
- `caption_coverage.coverage_rate` should be >= 85% (target: 95%)

---

## Phase 4: TIMING OPTIMIZATION → Timing Assignments

### Agent: timing-optimizer

**Inputs**:
```typescript
interface TimingOptimizerInput {
  schedule_items: CaptionAssignedItem[];  // From content-curator
  creator_id: string;                     // For get_best_timing()
  volume_config: OptimizedVolumeResult;   // For dow_multipliers_used
}
```

**Output Contract**:
```typescript
interface TimingAssignmentResult {
  items: TimedItem[];

  // Timing metadata
  timing_summary: {
    unique_times: number;                // Count of unique times (should be high)
    round_minute_count: number;          // Times on :00/:15/:30/:45 (should be low)
    round_minute_percentage: string;     // e.g., "2.9%" (target: <10%)
    dow_multipliers_applied: {
      [key: DayOfWeek]: number;
    };
    validation_passed: boolean;
  };
}

interface TimedItem extends TargetedItem {
  // Required timing fields
  scheduled_date: ISODate;               // Required (was already present)
  scheduled_time: ISOTime;               // Required (e.g., "19:07:00")

  // Timing metadata
  timing_metadata: {
    base_hour: number;                   // 0-23
    jitter_applied: number;              // -7 to +8 minutes
    morning_shift: number;               // -1, 0, or +1 hour
    evening_shift: number;               // -1, 0, or +1 hour
    dow_multiplier: number;              // DOW multiplier for this day
    spacing_strategy: "evenly_spread" | "clustered_in_peaks" | "standard";
  };
}
```

**Example Payload**:
```json
{
  "items": [
    {
      "slot": 1,
      "send_type_key": "ppv_unlock",
      "category": "revenue",
      "priority": 1,
      "caption_id": 789,
      "caption_text": "Hey babe...",
      "content_type": "solo",
      "caption_scores": {"performance": 85.2, "freshness": 92.0, "content_weight_bonus": 15.0, "composite": 87.92},
      "needs_manual_caption": false,
      "channel_key": "mass_message",
      "target_key": "active_30d",
      "targeting_reason": "default_mapping",
      "scheduled_date": "2025-12-16",
      "scheduled_time": "20:07:00",
      "timing_metadata": {
        "base_hour": 20,
        "jitter_applied": 7,
        "morning_shift": 0,
        "evening_shift": 0,
        "dow_multiplier": 0.95,
        "spacing_strategy": "evenly_spread"
      }
    }
  ],
  "timing_summary": {
    "unique_times": 68,
    "round_minute_count": 2,
    "round_minute_percentage": "2.9%",
    "dow_multipliers_applied": {
      "0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0
    },
    "validation_passed": true
  }
}
```

**Validation Rules**:
- All items must have `scheduled_date` and `scheduled_time`
- `scheduled_time` format: HH:MM:SS
- Minimum 45-minute spacing between sends on same day
- No sends during 3-7 AM (avoid hours)
- Round minute percentage should be < 10%
- No time should repeat more than 2x across the week
- Jitter should be applied (-7 to +8 minutes from base time)

---

## Phase 5: FOLLOWUP GENERATION → Followup Items

### Agent: followup-generator

**Inputs**:
```typescript
interface FollowupGeneratorInput {
  schedule_items: TimedItem[];           // From timing-optimizer
  creator_id: string;                    // For caption selection
  volume_config: OptimizedVolumeResult;  // For confidence_score and caption_warnings
}
```

**Output Contract**:
```typescript
interface FollowupGenerationResult {
  // Followup items (to be merged with main schedule)
  items: FollowupItem[];

  // Generation statistics
  followups_generated: number;
  followups_skipped_for_confidence: number;
  followups_skipped_for_limit: number;    // Max 4 per day
  followups_skipped_for_captions: number; // Caption shortage

  // Configuration used
  confidence_score: number;
  effective_generation_rate: number;      // 0.0-1.0 (actual % of eligible items)
  delay_used: number;                     // Minutes (15-30)
}

interface FollowupItem {
  // Core fields
  send_type_key: "ppv_followup";         // Always ppv_followup
  category: "retention";                 // Always retention
  priority: 3;                           // Always 3 (lowest)

  // Parent linkage
  parent_item_id: number;                // Reference to parent item
  parent_send_type: SendTypeKey;         // e.g., "ppv_unlock", "tip_goal"
  is_followup: 1;                        // Always 1 (true)
  followup_delay_minutes: number;        // 15-30 (adjusted by confidence)

  // Standard fields (inherited from parent)
  scheduled_date: ISODate;
  scheduled_time: ISOTime;
  channel_key: "targeted_message";       // Always targeted_message
  target_key: TargetKey;                 // "ppv_non_purchasers" or "non_tippers"

  // Caption
  caption_id: number | null;
  caption_text: string | null;
  caption_preview: string;               // First 50 chars

  // Metadata
  generation_metadata: {
    confidence_adjusted: boolean;
    original_delay: number;              // Base delay (20 minutes)
    adjusted_delay: number;              // Actual delay after confidence adjustment
  };
}
```

**Example Payload**:
```json
{
  "items": [
    {
      "send_type_key": "ppv_followup",
      "category": "retention",
      "priority": 3,
      "parent_item_id": 123,
      "parent_send_type": "ppv_unlock",
      "is_followup": 1,
      "followup_delay_minutes": 25,
      "scheduled_date": "2025-12-16",
      "scheduled_time": "20:32:00",
      "channel_key": "targeted_message",
      "target_key": "ppv_non_purchasers",
      "caption_id": 456,
      "caption_text": "Don't miss out babe...",
      "caption_preview": "Don't miss out babe...",
      "generation_metadata": {
        "confidence_adjusted": true,
        "original_delay": 20,
        "adjusted_delay": 25
      }
    }
  ],
  "followups_generated": 6,
  "followups_skipped_for_confidence": 2,
  "followups_skipped_for_limit": 0,
  "followups_skipped_for_captions": 0,
  "confidence_score": 0.75,
  "effective_generation_rate": 0.75,
  "delay_used": 25
}
```

**Validation Rules**:
- `send_type_key` must be "ppv_followup"
- `is_followup` must be 1
- `parent_item_id` must reference a valid parent in the schedule
- `channel_key` must be "targeted_message"
- `target_key` must be "ppv_non_purchasers" (for PPV) or "non_tippers" (for tip_goal)
- `followup_delay_minutes` must be 15-30
- Max 4 followups per day
- `scheduled_time` must be parent_time + followup_delay_minutes

---

## Phase 6: AUTHENTICITY ENGINE → Humanized Items [NEW]

### Agent: authenticity-engine

**Inputs**:
```typescript
interface AuthenticityEngineInput {
  schedule_items: FollowupGenerationResult;  // From followup-generator
  creator_id: string;                        // For get_persona_profile()
  volume_config: OptimizedVolumeResult;      // For confidence_score
}
```

**Output Contract**:
```typescript
interface AuthenticityResult {
  // Humanized items
  items: HumanizedItem[];

  // Authenticity summary
  authenticity_summary: {
    items_processed: number;
    average_score: number;                   // 0-100
    items_needing_review: number;            // Score < 65
    timing_jitter_applied: number;           // Count of items with jitter
    captions_humanized: number;              // Count of captions modified
  };

  // Persona profile used
  persona_applied: {
    tone: string;                            // e.g., "playful", "seductive"
    archetype: string;                       // e.g., "girl_next_door"
    emoji_style: string;                     // e.g., "heavy", "moderate"
    slang_level: number;                     // 1-5
  };

  // Pass-through for downstream phases
  volume_config: OptimizedVolumeResult;
}

interface HumanizedItem extends TimedItem {
  // Authenticity scoring
  authenticity_score: number;                // 0-100
  needs_review: boolean;                     // True if score < 65
  review_reason?: string;                    // Why review is needed

  // Humanization flags
  timing_humanized: boolean;                 // True if jitter applied
  caption_humanized: boolean;                // True if caption modified
  original_caption_text?: string;            // Only if caption modified

  // Jitter details
  timing_jitter: {
    original_time: ISOTime;
    jitter_applied: number;                  // Minutes (-5 to +5)
    final_time: ISOTime;
  };
}
```

**Example Payload**:
```json
{
  "items": [
    {
      "slot": 1,
      "send_type_key": "ppv_unlock",
      "category": "revenue",
      "scheduled_date": "2025-12-16",
      "scheduled_time": "19:47:00",
      "caption_text": "Hey babe, I made this just for you...",
      "authenticity_score": 85,
      "needs_review": false,
      "timing_humanized": true,
      "caption_humanized": false,
      "timing_jitter": {
        "original_time": "19:45:00",
        "jitter_applied": 2,
        "final_time": "19:47:00"
      }
    }
  ],
  "authenticity_summary": {
    "items_processed": 48,
    "average_score": 82.5,
    "items_needing_review": 3,
    "timing_jitter_applied": 48,
    "captions_humanized": 2
  },
  "persona_applied": {
    "tone": "playful",
    "archetype": "girl_next_door",
    "emoji_style": "moderate",
    "slang_level": 3
  }
}
```

**Validation Rules**:
- All items must have `authenticity_score` between 0-100
- `needs_review` must be true if `authenticity_score < 65`
- `timing_jitter.jitter_applied` must be between -5 and +5 minutes
- `timing_jitter.final_time` must not land on :00, :15, :30, :45 (round minutes)

---

## Phase 7: SCHEDULE ASSEMBLY → Assembled Schedule

### Agent: schedule-assembler

**Inputs**:
```typescript
interface ScheduleAssemblerInput {
  allocation: AllocationResult;          // From send-type-allocator (includes strategy_metadata)
  captions: CaptionAssignmentResult;     // From content-curator
  channels: ChannelAssignment;           // Derived from send type configuration
  timing: TimingAssignmentResult;        // From timing-optimizer
  followups: FollowupGenerationResult;   // From followup-generator
  volume_config: OptimizedVolumeResult;  // Pass-through for quality-validator
  creator_id: string;
  week_start: ISODate;
}
```

**Output Contract**:
```typescript
interface AssembledSchedule {
  // Metadata
  creator_id: string;
  week_start: ISODate;
  template_id: number | null;            // Set after save_schedule()

  // Complete schedule items (merged from all phases)
  items: ScheduleItem[];

  // **CRITICAL**: Strategy metadata (MUST be preserved from Phase 2)
  strategy_metadata: {
    [date: ISODate]: DailyStrategy;
  };

  // Summary statistics
  summary: {
    total_items: number;
    by_category: {
      revenue: number;
      engagement: number;
      retention: number;
    };
    by_send_type: {
      [sendType: SendTypeKey]: number;
    };
    followups_generated: number;
    unique_send_types: number;           // Must be >= 10
    warnings: string[];
  };

  // Volume metadata (pass-through from Phase 1)
  volume_metadata: {
    confidence_score: number;
    confidence_level: ConfidenceLevel;
    fused_saturation: number;
    fused_opportunity: number;
    weekly_distribution: {[key: DayOfWeek]: number};
    dow_multipliers_used: {[key: DayOfWeek]: number};
    content_allocations: {[content_type: string]: number};
    adjustments_applied: string[];
    elasticity_capped: boolean;
    caption_warnings: string[];
    prediction_id: number | null;
    calculation_source: CalculationSource;
  };

  // Variation statistics (anti-pattern validation)
  variation_stats: {
    unique_times: number;
    times_on_round_minutes: number;
    round_minute_percentage: string;
    unique_daily_patterns: number;       // Must be 7 (all different)
    strategies_used: string[];
    strategy_count: number;              // Must be >= 3
    anti_pattern_score: number;          // 0-100 (target: >= 75)
    jitter_applied: boolean;
    validation_passed: boolean;
  };

  // Assembly timestamp
  assembly_timestamp: ISODateTime;
}

interface ScheduleItem {
  // Core identification
  item_id?: number;                      // Set by database after save
  scheduled_date: ISODate;               // Required
  scheduled_time: ISOTime;               // Required

  // Send type system
  send_type_key: SendTypeKey;            // Required
  item_type: SendTypeCategory;           // Legacy: "revenue", "engagement", "retention"

  // Channel and targeting
  channel_key: ChannelKey;               // Required
  target_key: TargetKey;                 // Required

  // Caption
  caption_id: number | null;
  caption_text: string | null;
  content_type_id: number;               // Foreign key to content_types

  // Requirements
  media_type: MediaType;                 // "none", "picture", "gif", "video", "flyer"
  flyer_required: 0 | 1;
  suggested_price: number | null;        // USD (e.g., 15.00)

  // Optional fields
  linked_post_url: string | null;        // For link_drop types
  expires_at: ISODateTime | null;        // For time-limited items
  campaign_goal: number | null;          // For tip_goal and campaigns

  // Followup tracking
  is_followup: 0 | 1;
  parent_item_id: number | null;
  followup_delay_minutes: number | null;

  // Metadata
  priority: 1 | 2 | 3;                   // 1=revenue, 2=engagement, 3=retention
  needs_manual_caption?: boolean;        // Flag for operator review
  caption_warning?: string;              // Reason if manual needed
}
```

**Example Payload**:
```json
{
  "creator_id": "alexia",
  "week_start": "2025-12-16",
  "template_id": null,
  "items": [
    {
      "scheduled_date": "2025-12-16",
      "scheduled_time": "20:07:00",
      "send_type_key": "ppv_unlock",
      "item_type": "revenue",
      "channel_key": "mass_message",
      "target_key": "active_30d",
      "caption_id": 789,
      "caption_text": "Hey babe, I made this just for you...",
      "content_type_id": 1,
      "media_type": "video",
      "flyer_required": 0,
      "suggested_price": 15.00,
      "linked_post_url": null,
      "expires_at": "2025-12-17T08:00:00Z",
      "campaign_goal": null,
      "is_followup": 0,
      "parent_item_id": null,
      "followup_delay_minutes": null,
      "priority": 1
    }
  ],
  "strategy_metadata": {
    "2025-12-16": {"strategy_used": "balanced_spread", "flavor_emphasis": "bundle", "flavor_avoid": "game_post"},
    "2025-12-17": {"strategy_used": "revenue_front", "flavor_emphasis": "dm_farm", "flavor_avoid": "like_farm"}
  },
  "summary": {
    "total_items": 78,
    "by_category": {"revenue": 35, "engagement": 33, "retention": 10},
    "by_send_type": {"ppv_unlock": 10, "tip_goal": 8, "bundle": 5, "bump_normal": 7},
    "followups_generated": 8,
    "unique_send_types": 15,
    "warnings": []
  },
  "volume_metadata": {
    "confidence_score": 0.85,
    "confidence_level": "HIGH",
    "fused_saturation": 43.5,
    "fused_opportunity": 64.2,
    "weekly_distribution": {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13},
    "dow_multipliers_used": {"0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0},
    "content_allocations": {"solo": 3, "lingerie": 2, "tease": 2},
    "adjustments_applied": ["base_tier", "multi_horizon_fusion", "day_of_week", "content_weighting"],
    "elasticity_capped": false,
    "caption_warnings": [],
    "prediction_id": 123,
    "calculation_source": "optimized"
  },
  "variation_stats": {
    "unique_times": 68,
    "times_on_round_minutes": 3,
    "round_minute_percentage": "4.4%",
    "unique_daily_patterns": 7,
    "strategies_used": ["balanced_spread", "revenue_front", "engagement_heavy", "evening_revenue"],
    "strategy_count": 4,
    "anti_pattern_score": 95,
    "jitter_applied": true,
    "validation_passed": true
  },
  "assembly_timestamp": "2025-12-17T10:30:00Z"
}
```

**Validation Rules**:
- All items must have: `scheduled_date`, `scheduled_time`, `send_type_key`, `channel_key`
- `strategy_metadata` MUST be present with entries for all 7 days
- `unique_send_types` must be >= 10
- `anti_pattern_score` must be >= 75
- `variation_stats.unique_daily_patterns` must be 7 (all days different)
- `variation_stats.strategy_count` must be >= 3
- Round minute percentage should be < 10%
- No time should repeat more than 2x across week

---

## Phase 8: REVENUE OPTIMIZATION → Priced Schedule [NEW]

### Agent: revenue-optimizer

**Inputs**:
```typescript
interface RevenueOptimizerInput {
  assembled_schedule: AssembledSchedule;     // From schedule-assembler
  creator_id: string;                        // For volume context
  volume_config: OptimizedVolumeResult;      // For confidence_score
}
```

**Output Contract**:
```typescript
interface RevenueOptimizationResult {
  // Priced items
  items: PricedItem[];

  // Pricing summary
  pricing_summary: {
    items_priced: number;                    // Revenue items with prices
    confidence_dampening_applied: boolean;   // True if prices adjusted
    confidence_level: ConfidenceLevel;       // "LOW", "MEDIUM", "HIGH"
    average_dampening: number;               // e.g., 0.85 = 15% reduction
    value_framing_applied: number;           // Bundle items with value framing
    first_to_tip_rotation_applied: number;   // Items with tip rotation
    positions_optimized: number;             // Items moved to peak times
  };

  // Revenue projection
  revenue_projection: {
    estimated_weekly: number;                // USD
    confidence_band: {
      low: number;                           // USD (low estimate)
      high: number;                          // USD (high estimate)
    };
  };

  // Pass-through for downstream
  volume_config: OptimizedVolumeResult;
  strategy_metadata: {                       // MUST preserve from Phase 2
    [date: ISODate]: DailyStrategy;
  };
}

interface PricedItem extends ScheduleItem {
  // Pricing fields
  optimized_price: number | null;            // Final price (or null for non-revenue)
  original_price: number | null;             // Base price before adjustments
  dampening_applied: number;                 // e.g., 0.87 = 13% reduction

  // Positioning
  position_optimized: boolean;               // True if moved to peak time
  original_time?: ISOTime;                   // Only if position changed

  // Bundle value framing (for bundle types)
  value_framing?: {
    individual_value: number;                // Sum of individual items
    bundle_price: number;                    // Discounted bundle price
    savings_percentage: number;              // e.g., 30 = 30% off
    savings_display: string;                 // e.g., "Save 30%!"
  };

  // First-to-tip rotation
  tip_rotation?: {
    day_in_rotation: number;                 // 1-7
    tip_amount: number;                      // USD
    rotation_strategy: string;               // e.g., "ascending", "random"
  };
}
```

**Example Payload**:
```json
{
  "items": [
    {
      "scheduled_date": "2025-12-16",
      "scheduled_time": "20:03:00",
      "send_type_key": "ppv_unlock",
      "category": "revenue",
      "optimized_price": 12.99,
      "original_price": 14.99,
      "dampening_applied": 0.87,
      "position_optimized": true,
      "original_time": "18:15:00",
      "authenticity_score": 85
    },
    {
      "scheduled_date": "2025-12-17",
      "scheduled_time": "19:47:00",
      "send_type_key": "bundle",
      "category": "revenue",
      "optimized_price": 29.99,
      "original_price": 35.00,
      "dampening_applied": 0.86,
      "position_optimized": false,
      "value_framing": {
        "individual_value": 45.00,
        "bundle_price": 29.99,
        "savings_percentage": 33,
        "savings_display": "Save 33%!"
      }
    }
  ],
  "pricing_summary": {
    "items_priced": 18,
    "confidence_dampening_applied": true,
    "confidence_level": "MEDIUM",
    "average_dampening": 0.85,
    "value_framing_applied": 3,
    "first_to_tip_rotation_applied": 2,
    "positions_optimized": 5
  },
  "revenue_projection": {
    "estimated_weekly": 850.00,
    "confidence_band": {
      "low": 680.00,
      "high": 1020.00
    }
  }
}
```

**Validation Rules**:
- All revenue items must have `optimized_price` set
- `dampening_applied` must be between 0.5 and 1.0
- `value_framing.savings_percentage` must be between 10 and 50
- `position_optimized` items must have `original_time` preserved
- `strategy_metadata` MUST be passed through unchanged

---

## Phase 9: QUALITY VALIDATION → Validation Result

### Agent: quality-validator

**Inputs**:
```typescript
interface QualityValidatorInput {
  schedule: AssembledSchedule;           // From schedule-assembler
  creator_id: string;
}
```

**Output Contract**:
```typescript
interface ValidationResult {
  // Overall score and status
  quality_score: number;                 // 0-100
  status: ValidationStatus;              // "APPROVED", "NEEDS_REVIEW", "REJECTED"
  confidence_level: ConfidenceLevel;     // "LOW", "MEDIUM", "HIGH"

  // Validation results by category
  validation_results: {
    completeness: ValidationCategory;
    send_types: ValidationCategory;
    captions: ValidationCategory;
    timing: ValidationCategory;
    requirements: ValidationCategory;
    volume_config: VolumeConfigValidation;
    strategy_metadata: StrategyMetadataValidation;
  };

  // Caption warnings (from volume_config)
  caption_warnings: string[];

  // Thresholds used (confidence-adjusted)
  thresholds_used: {
    min_freshness: number;
    min_performance: number;
    diversity_min: number;
    spacing_tolerance_minutes: number;
    caption_coverage_target: number;
  };

  // Recommendations for improvement
  recommendations: string[];
}

interface ValidationCategory {
  passed: boolean;
  issues: string[];                      // Critical failures
  warnings?: string[];                   // Non-critical concerns
}

interface VolumeConfigValidation extends ValidationCategory {
  metadata: {
    confidence_score: number;
    fused_saturation: number;
    fused_opportunity: number;
    weekly_distribution: {[key: DayOfWeek]: number};
    dow_multipliers_used: {[key: DayOfWeek]: number};
    content_allocations: {[content_type: string]: number};
    adjustments_applied: string[];
    elasticity_capped: boolean;
    prediction_id: number | null;
    calculation_source: CalculationSource;
  };
  info: string[];                        // Informational messages
  volume_health: "GOOD" | "REVIEW_NEEDED";
}

interface StrategyMetadataValidation extends ValidationCategory {
  strategy_summary: {
    strategies_used: string[];           // List of unique strategies
    strategy_count: number;              // Must be >= 3
    dates_validated: number;             // Must be 7
    flavor_emphases: {
      [date: ISODate]: SendTypeKey;
    };
    diversity_passed: boolean;           // True if >= 3 strategies
  };
  info: string[];                        // Informational messages
}
```

**Example Payload**:
```json
{
  "quality_score": 92,
  "status": "APPROVED",
  "confidence_level": "HIGH",
  "validation_results": {
    "completeness": {
      "passed": true,
      "issues": []
    },
    "send_types": {
      "passed": true,
      "issues": []
    },
    "captions": {
      "passed": true,
      "issues": [],
      "warnings": ["2 items need manual captions"]
    },
    "timing": {
      "passed": true,
      "issues": []
    },
    "requirements": {
      "passed": true,
      "issues": []
    },
    "volume_config": {
      "passed": true,
      "issues": [],
      "warnings": [],
      "info": [
        "Confidence: 85% (HIGH)",
        "Content weighting applied: ['solo', 'lingerie', 'tease']",
        "Prediction tracking enabled: ID 123"
      ],
      "volume_health": "GOOD",
      "metadata": {
        "confidence_score": 0.85,
        "fused_saturation": 43.5,
        "fused_opportunity": 64.2,
        "weekly_distribution": {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13},
        "dow_multipliers_used": {"0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0},
        "content_allocations": {"solo": 3, "lingerie": 2, "tease": 2},
        "adjustments_applied": ["base_tier", "multi_horizon_fusion", "day_of_week", "content_weighting"],
        "elasticity_capped": false,
        "prediction_id": 123,
        "calculation_source": "optimized"
      }
    },
    "strategy_metadata": {
      "passed": true,
      "issues": [],
      "warnings": [],
      "info": ["Strategy diversity: 4 unique strategies"],
      "strategy_summary": {
        "strategies_used": ["balanced_spread", "revenue_front", "engagement_heavy", "evening_revenue"],
        "strategy_count": 4,
        "dates_validated": 7,
        "flavor_emphases": {
          "2025-12-16": "bundle",
          "2025-12-17": "dm_farm",
          "2025-12-18": "flash_bundle",
          "2025-12-19": "game_post",
          "2025-12-20": "first_to_tip",
          "2025-12-21": "vip_program",
          "2025-12-22": "link_drop"
        },
        "diversity_passed": true
      }
    }
  },
  "caption_warnings": [],
  "thresholds_used": {
    "min_freshness": 30,
    "min_performance": 40,
    "diversity_min": 10,
    "spacing_tolerance_minutes": 0,
    "caption_coverage_target": 0.95
  },
  "recommendations": []
}
```

**Validation Rules**:
- `quality_score >= 85`: Status = "APPROVED"
- `quality_score 70-84`: Status = "NEEDS_REVIEW"
- `quality_score < 70`: Status = "REJECTED"
- If `strategy_metadata` is missing: Status = "REJECTED"
- If `strategy_count < 3`: Status = "REJECTED"
- If `unique_send_types < 10`: Status = "REJECTED"
- If only ppv_unlock and bump_normal present: Status = "REJECTED"
- If FREE page contains tip_goal: Status = "REJECTED"
- If PAID page contains ppv_wall: Status = "REJECTED"

**Confidence-Adjusted Thresholds**:
| Confidence | APPROVED Threshold | NEEDS_REVIEW Range | REJECTED Threshold |
|------------|-------------------|-------------------|-------------------|
| >= 0.8     | >= 85             | 70-84             | < 70              |
| 0.5-0.79   | >= 80             | 65-79             | < 65              |
| < 0.5      | >= 75             | 60-74             | < 60              |

---

## Error Response Schema

All agents should return errors in this standardized format:

```typescript
interface ErrorResponse {
  error: true;
  error_code: string;                    // e.g., "INVALID_PAGE_TYPE", "CAPTION_SHORTAGE"
  error_message: string;                 // Human-readable error
  agent: string;                         // Agent name that produced the error
  phase: number;                         // Pipeline phase (1-9)
  timestamp: ISODateTime;
  details?: any;                         // Optional additional context
}
```

**Example Error**:
```json
{
  "error": true,
  "error_code": "INSUFFICIENT_DIVERSITY",
  "error_message": "Schedule contains only 8 unique send types. Minimum 10 required.",
  "agent": "quality-validator",
  "phase": 9,
  "timestamp": "2025-12-17T10:35:00Z",
  "details": {
    "unique_types_found": 8,
    "unique_types_required": 10,
    "types_used": ["ppv_unlock", "bump_normal", "bundle", "link_drop", "dm_farm", "tip_goal", "renew_on_message", "ppv_followup"]
  }
}
```

---

## Supporting Tables: ppv_structure_rotation_state

### Purpose

Tracks the PPV content structure rotation state per creator to ensure variety in content presentation patterns. This prevents robotic repetition by rotating between different PPV approach styles every 3-4 days.

### Status

**PROPOSED** - Table schema documented but not yet implemented in database. Referenced in timing-optimizer agent (lines 457-488).

### Schema

```sql
CREATE TABLE IF NOT EXISTS ppv_structure_rotation_state (
    creator_id TEXT PRIMARY KEY,
    current_structure TEXT NOT NULL,           -- 'teaser', 'direct', 'story', 'urgency'
    last_rotation_date TEXT NOT NULL,          -- ISO 8601 date (YYYY-MM-DD)
    rotation_history TEXT,                     -- JSON array of last 4 structures used
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Index for efficient state queries
CREATE INDEX IF NOT EXISTS idx_ppv_rotation_updated
ON ppv_structure_rotation_state(updated_at);
```

### Structure Types

| structure_type | Description | Example Caption Style |
|----------------|-------------|----------------------|
| `teaser` | Mystery/intrigue approach | "You won't believe what I did today 🙈 Check DMs" |
| `direct` | Straightforward offer | "NEW B/G video 🔥 20 minutes $25 - unlock now" |
| `story` | Narrative/context approach | "Had the craziest day at the gym... you NEED to see what happened" |
| `urgency` | Time-limited pressure | "FLASH SALE: 50% off next 2 hours only! 💨" |

### Rotation Rules

1. **Duration**: Each structure should be used for 3-4 days before rotating (randomized threshold)
2. **Tracking**: Store last structure used and date changed in state table
3. **Randomization**: Don't follow predictable order - use weighted random selection
4. **Cross-Week**: Structure rotation should span across weekly schedule boundaries
5. **History**: Track last 4 structures to avoid immediate repetition

### Usage Example

```python
from datetime import date, timedelta
import random
import json

def track_ppv_rotation(creator_id: str, current_date: date) -> dict:
    """
    Track PPV structure rotation state for authenticity.

    Args:
        creator_id: Creator identifier
        current_date: Current schedule date

    Returns:
        {
            'current_structure': str,    # 'teaser', 'direct', 'story', 'urgency'
            'days_in_current': int,      # Days using current structure
            'next_rotation_date': date,  # When to rotate (3-4 days out)
            'rotation_history': list,    # Last 4 structures used
            'rotation_occurred': bool    # True if rotation happened this call
        }
    """
    # Query creator's structure_rotation_state table
    state = db.query("""
        SELECT current_structure, last_rotation_date, rotation_history
        FROM ppv_structure_rotation_state
        WHERE creator_id = ?
    """, (creator_id,))

    if not state:
        # Initialize for new creator
        return initialize_ppv_rotation(creator_id, current_date)

    days_in_current = (current_date - date.fromisoformat(state['last_rotation_date'])).days

    # Check if rotation needed (3-4 days threshold with randomization)
    rotation_threshold = random.randint(3, 4)

    if days_in_current >= rotation_threshold:
        # Time to rotate
        history = json.loads(state['rotation_history']) if state['rotation_history'] else []
        new_structure = get_next_ppv_structure(
            current=state['current_structure'],
            history=history
        )

        # Update state
        new_history = update_history(history, new_structure)
        db.execute("""
            UPDATE ppv_structure_rotation_state
            SET current_structure = ?,
                last_rotation_date = ?,
                rotation_history = ?,
                updated_at = datetime('now')
            WHERE creator_id = ?
        """, (new_structure, current_date.isoformat(),
              json.dumps(new_history), creator_id))

        return {
            'current_structure': new_structure,
            'days_in_current': 0,
            'next_rotation_date': current_date + timedelta(days=random.randint(3, 4)),
            'rotation_history': new_history,
            'rotation_occurred': True
        }

    # No rotation needed
    return {
        'current_structure': state['current_structure'],
        'days_in_current': days_in_current,
        'next_rotation_date': date.fromisoformat(state['last_rotation_date']) + timedelta(days=rotation_threshold),
        'rotation_history': json.loads(state['rotation_history']) if state['rotation_history'] else [],
        'rotation_occurred': False
    }


def get_next_ppv_structure(current: str, history: list) -> str:
    """
    Select next PPV structure using weighted randomization.
    Avoid structures used in last 3 rotations.
    """
    all_structures = ['teaser', 'direct', 'story', 'urgency']

    # Filter out recently used structures (last 3 in history)
    recent = set(history[-3:]) if len(history) >= 3 else set()
    available = [s for s in all_structures if s not in recent and s != current]

    # If all structures recently used, just avoid current
    if not available:
        available = [s for s in all_structures if s != current]

    # Weighted random selection (can be customized per creator)
    weights = get_structure_weights_for_creator()

    return random.choices(available, weights=[weights.get(s, 1.0) for s in available])[0]


def initialize_ppv_rotation(creator_id: str, start_date: date) -> dict:
    """Initialize PPV rotation state for new creator."""
    initial_structure = random.choice(['teaser', 'direct', 'story', 'urgency'])

    db.execute("""
        INSERT INTO ppv_structure_rotation_state
        (creator_id, current_structure, last_rotation_date, rotation_history)
        VALUES (?, ?, ?, ?)
    """, (creator_id, initial_structure, start_date.isoformat(), json.dumps([])))

    return {
        'current_structure': initial_structure,
        'days_in_current': 0,
        'next_rotation_date': start_date + timedelta(days=random.randint(3, 4)),
        'rotation_history': [],
        'rotation_occurred': False
    }


def update_history(history: list, new_structure: str) -> list:
    """Update rotation history, keeping last 4 entries."""
    updated = history + [new_structure]
    return updated[-4:]  # Keep last 4 only
```

### Integration Points

- **timing-optimizer**: Calls `track_ppv_rotation()` before timing assignment to get current structure preference
- **content-curator**: Uses structure state to filter captions matching current PPV approach style
- **schedule-assembler**: Updates rotation state after schedule finalization
- **quality-validator**: Validates that PPV structure variety is maintained across the week

### Migration Script

When implementing this table, use this migration:

```sql
-- File: database/migrations/013_ppv_structure_rotation.sql

CREATE TABLE IF NOT EXISTS ppv_structure_rotation_state (
    creator_id TEXT PRIMARY KEY,
    current_structure TEXT NOT NULL,
    last_rotation_date TEXT NOT NULL,
    rotation_history TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ppv_rotation_updated
ON ppv_structure_rotation_state(updated_at);

-- Initialize for existing creators with random structures
INSERT INTO ppv_structure_rotation_state (creator_id, current_structure, last_rotation_date, rotation_history)
SELECT
    creator_id,
    CASE (ABS(RANDOM()) % 4)
        WHEN 0 THEN 'teaser'
        WHEN 1 THEN 'direct'
        WHEN 2 THEN 'story'
        ELSE 'urgency'
    END,
    date('now', '-' || (ABS(RANDOM()) % 4) || ' days'),
    '[]'
FROM creators
WHERE active = 1
ON CONFLICT(creator_id) DO NOTHING;
```

---

## Version History

| Version | Date       | Changes |
|---------|------------|---------|
| 2.3.0   | 2025-12-18 | Updated to 9-phase pipeline: added Phase 6 (authenticity-engine) and Phase 8 (revenue-optimizer) contracts |
| 2.2.1   | 2025-12-17 | Added ppv_structure_rotation_state table documentation (proposed) |
| 2.2.0   | 2025-12-17 | Initial comprehensive data contracts documentation with full OptimizedVolumeResult integration |

---

## Notes

### Critical Data Flow Requirements

1. **strategy_metadata Preservation**: The `strategy_metadata` output from send-type-allocator (Phase 2) MUST be preserved through all downstream phases and passed to quality-validator. This is the primary mechanism for validating daily strategy diversity.

2. **OptimizedVolumeResult Pass-Through**: The volume_config from Phase 1 must be passed through all phases to quality-validator, preserving:
   - `confidence_score` for threshold adjustments
   - `caption_warnings` for caption shortage handling
   - `weekly_distribution` and `dow_multipliers_used` for validation
   - `adjustments_applied` for audit trail

3. **Page-Type Constraints**:
   - FREE pages MUST NOT contain `tip_goal`
   - PAID pages MUST NOT contain `ppv_wall`
   - Retention types (renew_on_*, expired_winback) are PAID only

4. **Diversity Requirements**:
   - Minimum 10 unique send_type_keys across the week
   - At least 4 different revenue types
   - At least 4 different engagement types
   - At least 2 different retention types (paid pages only)
   - At least 3 different daily strategies

5. **Timing Variation**:
   - Jitter applied to all times (-7 to +8 minutes)
   - < 10% of times on round minutes (:00, :15, :30, :45)
   - No time repeats more than 2x across week
   - Unique daily patterns (all 7 days different)

### Backward Compatibility

The data contracts maintain backward compatibility with legacy fields:
- `ppv_per_day` and `bump_per_day` (use `revenue_per_day`, `engagement_per_day` instead)
- `item_type` (use `send_type_key` and `category` instead)
- Raw `saturation_score` and `opportunity_score` (use `fused_saturation`, `fused_opportunity` instead)

New implementations should use the optimized fields.
