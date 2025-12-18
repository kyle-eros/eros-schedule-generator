# Pipeline Orchestration

Complete technical reference for the EROS Schedule Generator pipeline orchestration.

---

## Pipeline Overview

The EROS schedule generation pipeline executes in **7 sequential phases**, transforming creator data and configuration into an optimized weekly schedule with **authentic daily variation**. Each phase has defined inputs, outputs, and validation checkpoints.

**Daily Variation System**: Phases 2 and 5 incorporate strategy rotation, time offsets, and jitter to create natural schedule variation that prevents repetitive patterns. This mimics human scheduling behavior and sustains audience engagement.

```
+--------------------------------------------------------------------+
|                     EROS SCHEDULE GENERATION PIPELINE              |
+--------------------------------------------------------------------+
|                                                                    |
|  PHASE 1          PHASE 2          PHASE 3          PHASE 4       |
|  +---------+      +---------+      +---------+      +---------+   |
|  | INIT    |----->| SEND    |----->| CONTENT |----->| AUDIENCE|   |
|  |         |      | TYPE    |      | MATCHING|      | TARGET  |   |
|  +---------+      | ALLOC   |      +---------+      +---------+   |
|                   +---------+                             |       |
|                                                           v       |
|  PHASE 7          PHASE 6          PHASE 5          +---------+   |
|  +---------+      +---------+      +---------+      |         |   |
|  | ASSEMBLY|<-----| FOLLOWUP|<-----| TIMING  |<-----|         |   |
|  | & VALID |      | GEN     |      | OPTIM   |      +---------+   |
|  +---------+      +---------+      +---------+                    |
|       |                                                           |
|       v                                                           |
|  +---------+                                                      |
|  | DATABASE|  save_schedule()                                     |
|  +---------+                                                      |
|                                                                    |
+--------------------------------------------------------------------+
```

---

## Phase 1: INITIALIZATION

**Duration**: ~2 seconds
**Objective**: Load all required creator data and system configuration
**Status**: Foundation for all subsequent phases

### 1.1 Load Creator Profile

```
MCP CALL: get_creator_profile(creator_id)

EXTRACT:
  - page_type: "paid" | "free"
  - performance_tier: 1-5
  - fan_count: integer
  - avg_revenue_per_message: decimal
  - analytics_summary: object
```

**Output Variables:**
- `creator.page_type` - Determines applicable send types and targets
- `creator.tier` - Influences volume allocation
- `creator.fan_count` - Used for volume tier selection

### 1.2 Load Volume Configuration

```
MCP CALL: get_volume_config(creator_id)

EXTRACT:
  - volume_level: "low" | "mid" | "high" | "ultra"
  - revenue_per_day: integer (daily revenue item quota)
  - engagement_per_day: integer (daily engagement item quota)
  - retention_per_day: integer (daily retention item quota)
  - type_limits: object (per-type daily/weekly caps)
```

**Volume Tier Mapping:**

| Volume Level | Fan Count     | Rev/Day | Eng/Day | Ret/Day | Total |
|--------------|---------------|---------|---------|---------|-------|
| low          | 0-999         | 3       | 3       | 1       | 7     |
| mid          | 1K-4.9K       | 4       | 4       | 2       | 10    |
| high         | 5K-14.9K      | 6       | 5       | 2       | 13    |
| ultra        | 15K+          | 8       | 6       | 3       | 17    |

### 1.2.1 Optimized Volume Calculation (v2.2)

**CRITICAL**: The MCP tool `get_volume_config()` returns the full `OptimizedVolumeResult` structure. All fields MUST be consumed by subsequent phases.

#### Pipeline Execution Flow

When `get_volume_config(creator_id)` is called, the backend executes:

```
1. Base Tier Calculation     → fan_count → tier → base volumes
2. Multi-Horizon Fusion      → 7d/14d/30d scores → fused_saturation, fused_opportunity
3. Confidence Dampening      → message_count → dampened multipliers if <30 messages
4. DOW Multipliers           → historical day performance → weekly_distribution
5. Elasticity Bounds         → diminishing returns check → elasticity_capped
6. Content Weighting         → top_content_types → content_allocations
7. Caption Pool Check        → caption freshness → caption_warnings
8. Prediction Tracking       → save for accuracy → prediction_id
```

#### Full OptimizedVolumeResult Structure

```python
@dataclass
class OptimizedVolumeResult:
    # Core configurations
    base_config: VolumeConfig        # From initial tier calculation
    final_config: VolumeConfig       # After ALL adjustments applied

    # Weekly distribution (CRITICAL for Phase 2)
    weekly_distribution: dict[int, int]  # DOW-adjusted items per day (0=Mon, 6=Sun)
    dow_multipliers_used: dict[int, float]  # Multipliers that produced distribution

    # Content-type allocation
    content_allocations: dict[str, int]  # e.g., {"solo": 3, "lingerie": 2}

    # Performance fusion
    fused_saturation: float          # 0-100, after 7d/14d/30d fusion
    fused_opportunity: float         # 0-100, after 7d/14d/30d fusion
    divergence_detected: bool        # True if horizons disagree significantly

    # Data quality indicators
    confidence_score: float          # 0.0-1.0, affects decision making
    message_count: int               # Messages analyzed for this calculation

    # Adjustment flags
    elasticity_capped: bool          # True if diminishing returns applied
    adjustments_applied: list[str]   # Full audit trail

    # Warnings (MUST be surfaced to Phase 7)
    caption_warnings: list[str]      # e.g., ["Low captions for ppv_followup: <3 usable"]

    # Tracking
    prediction_id: int | None        # For accuracy measurement
```

#### Example Response

```json
{
    "volume_level": "High",
    "ppv_per_day": 6,
    "bump_per_day": 5,

    "revenue_per_day": 6,
    "engagement_per_day": 5,
    "retention_per_day": 2,

    "weekly_distribution": {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13},
    "dow_multipliers_used": {"0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0},
    "content_allocations": {"solo": 3, "lingerie": 2, "outdoor": 1},

    "fused_saturation": 45.0,
    "fused_opportunity": 62.0,
    "divergence_detected": false,

    "confidence_score": 0.85,
    "message_count": 156,

    "elasticity_capped": false,
    "adjustments_applied": ["base_tier_calculation", "multi_horizon_fusion", "dow_multipliers", "content_weighting", "prediction_tracked"],

    "caption_warnings": [],
    "prediction_id": 123,

    "calculation_source": "optimized",
    "data_source": "volume_performance_tracking"
}
```

#### 8 Integrated Optimization Modules

| Module | Key Output Fields | Applied When | Action If Missing |
|--------|------------------|--------------|-------------------|
| Base Tier Calculation | `final_config.tier`, `final_config.*_per_day` | Always | Fatal error |
| Multi-Horizon Fusion | `fused_saturation`, `fused_opportunity`, `divergence_detected` | Tracking data exists | Use raw scores |
| Confidence Dampening | `confidence_score`, damped multipliers | `message_count < 30` | Use 1.0 multipliers |
| DOW Multipliers | `weekly_distribution`, `dow_multipliers_used` | Historical data exists | Use uniform distribution |
| Elasticity Bounds | `elasticity_capped` | Sufficient volume history | Skip check |
| Content Weighting | `content_allocations` | Content rankings exist | Equal weighting |
| Caption Pool Check | `caption_warnings` | Always checked | Empty array |
| Prediction Tracking | `prediction_id` | `track_prediction=True` | `null` |

#### Phase 1 Checkpoint Requirements

Before proceeding to Phase 2, verify these fields are populated:

- [ ] `final_config.revenue_per_day` is set (1-10 range)
- [ ] `final_config.engagement_per_day` is set (1-8 range)
- [ ] `final_config.retention_per_day` is set (0-4 range, 0 for free pages)
- [ ] `weekly_distribution` has 7 entries (keys 0-6)
- [ ] `confidence_score` is between 0.0 and 1.0
- [ ] `adjustments_applied` contains at least `["base_tier_calculation"]`

#### OptimizedVolumeResult Consumption Matrix (NEW v2.3)

**CRITICAL**: This matrix shows which phases consume which OptimizedVolumeResult fields. Each phase MUST consume its designated fields.

| Field | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Phase 7a | Phase 7b |
|-------|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|:--------:|:--------:|
| `revenue_per_day` | ✓ Load | ✓ Quotas | - | - | - | - | - | ✓ Validate |
| `engagement_per_day` | ✓ Load | ✓ Quotas | - | - | - | - | - | ✓ Validate |
| `retention_per_day` | ✓ Load | ✓ Quotas | - | - | - | - | - | ✓ Validate |
| `weekly_distribution` | ✓ Load | ✓✓ **Primary** | - | - | - | - | - | ✓ Validate |
| `dow_multipliers_used` | ✓ Load | ✓ Transparency | - | - | - | - | ✓ Output | - |
| `content_allocations` | ✓ Load | ✓ Weighting | ✓ Select | - | - | - | - | - |
| `confidence_score` | ✓ Load | ✓ Dampening | - | - | - | - | ✓ Pricing | ✓✓ **Critical** |
| `message_count` | ✓ Load | - | - | - | - | - | - | ✓ Context |
| `fused_saturation` | ✓ Load | - | - | - | - | - | ✓ Output | ✓ Context |
| `fused_opportunity` | ✓ Load | - | - | - | - | - | ✓ Output | ✓ Context |
| `divergence_detected` | ✓ Load | - | - | - | - | - | - | ✓ Warning |
| `elasticity_capped` | ✓ Load | - | - | - | - | - | - | ✓ Warning |
| `adjustments_applied` | ✓ Load | - | - | - | - | - | ✓ Output | ✓ Audit |
| `caption_warnings` | ✓ Load | - | ✓ Alert | - | - | - | - | ✓✓ **Critical** |
| `prediction_id` | ✓ Load | - | - | - | - | - | ✓ Output | ✓ Tracking |

**Legend:**
- `✓ Load` = Phase reads and stores the field
- `✓✓ **Primary**` = Critical consumption point (must not skip)
- `✓ Quotas` = Uses field for quota calculation
- `✓ Dampening` = Uses for confidence adjustments
- `✓ Weighting` = Uses for weighted selection
- `✓ Output` = Includes in final output
- `✓ Validate` = Validates against expected ranges
- `✓✓ **Critical**` = Validation failure causes schedule rejection

**Consumption Rules:**

1. **Phase 2 MUST** use `weekly_distribution`, NOT legacy hardcoded DOW modifiers
2. **Phase 2 MUST** apply dampening when `confidence_score < 0.6`
3. **Phase 3 MUST** check `caption_warnings` and surface alerts
4. **Phase 7a MUST** apply `confidence_score` to pricing calculations
5. **Phase 7b MUST** fail validation if `confidence_score < 0.3` and no manual override

#### Parallel Execution Opportunities (NEW v2.3)

The following MCP calls can be executed in parallel to minimize latency:

**Phase 1 - Full Parallelization Possible:**
```
[BATCH 1 - 3 parallel calls]
├── get_creator_profile(creator_id)
├── get_volume_config(creator_id)
└── get_performance_trends(creator_id, "14d")

[BATCH 2 - 3 parallel calls, after page_type known]
├── get_send_types(page_type)
├── get_vault_availability(creator_id)
└── get_best_timing(creator_id)
```
**Latency Savings:** ~50% reduction (2 batches vs 6 sequential calls)

**Phase 3 - Batch Parallelization:**
```
[Per-day batch - N parallel calls]
FOR each day (7 days):
    [PARALLEL within day]
    ├── get_send_type_captions(creator_id, slot_1.send_type_key)
    ├── get_send_type_captions(creator_id, slot_2.send_type_key)
    └── ... (all slots for day in parallel)
```
**Latency Savings:** ~70% reduction for content matching

**Phase 4 - Full Parallelization:**
```
[PARALLEL - All send type details at once]
FOR ALL unique send_type_keys in schedule:
    get_send_type_details(send_type_key)  // All in parallel
```
**Latency Savings:** ~85% reduction (1 batch vs N sequential)

**Non-Parallelizable Operations:**
- Phase 2 → Phase 3: Must complete allocation before content selection
- Phase 5 → Phase 6: Must complete timing before followup generation
- Phase 6 → Phase 7a: Must complete followups before assembly
- Phase 7a → Phase 7b: Must complete assembly before validation
- Phase 7b → save_schedule: Must pass validation before saving

### 1.3 Load Performance Trends

```
MCP CALL: get_performance_trends(creator_id, period="14d")

EXTRACT:
  - saturation_score: 0-100 (higher = audience overexposed)
  - opportunity_score: 0-100 (higher = revenue potential)
  - revenue_trend: "up" | "stable" | "down"
  - engagement_velocity: decimal
```

**Trend-Based Adjustments:**

```
IF saturation_score > 70:
    # High saturation - audience is overexposed
    volume_adjustment = -0.20  # Reduce revenue items by 20%
    priority_shift = "engagement"  # Shift toward lighter touch

ELSE IF saturation_score > 50:
    # Moderate saturation - standard volume
    volume_adjustment = 0
    priority_shift = "balanced"

ELSE IF opportunity_score > 70:
    # Low saturation, high opportunity
    volume_adjustment = +0.20  # Increase revenue items by 20%
    priority_shift = "revenue"

ELSE:
    # Normal operating conditions
    volume_adjustment = 0
    priority_shift = "balanced"
```

### 1.4 Load Send Type Catalog

```
MCP CALL: get_send_types(page_type=creator.page_type)

RETURNS: Array of applicable send types

FILTER:
  - Exclude types where page_type != creator.page_type AND page_type != "both"
  - For free pages: Exclude renew_on_post, renew_on_message, expired_winback
```

**Send Type Categories:**

| Category    | Count | Types                                                              |
|-------------|-------|--------------------------------------------------------------------|
| Revenue     | 9     | ppv_unlock, ppv_wall (FREE), tip_goal (PAID), vip_program, game_post, bundle, flash_bundle, snapchat_bundle, first_to_tip |
| Engagement  | 9     | link_drop, wall_link_drop, bump_normal, bump_descriptive, bump_text_only, bump_flyer, dm_farm, like_farm, live_promo |
| Retention   | 4     | renew_on_post, renew_on_message, ppv_followup, expired_winback |

### 1.5 Load Vault Availability

```
MCP CALL: get_vault_availability(creator_id)

RETURNS:
  - available_content_types: ["video", "picture", "gif", ...]
  - content_counts: { "video": 45, "picture": 120, ... }
  - last_updated: timestamp
```

**Vault Availability Matrix:**

```
FOR each send_type in catalog:
    IF send_type.requires_media:
        check_vault_has(send_type.media_type)
    IF send_type.requires_flyer:
        check_vault_has("flyer")
```

### 1.6 Load Best Timing Data

```
MCP CALL: get_best_timing(creator_id)

RETURNS:
  - peak_hours: [20, 21, 22]  # 8-10 PM typically
  - avoid_hours: [3, 4, 5]    # Low engagement
  - best_days: ["friday", "saturday", "sunday"]
  - hourly_performance: { "0": 0.3, "1": 0.2, ... "20": 1.0 }
```

### Phase 1 Output State

```json
{
  "creator": {
    "id": "alexia",
    "page_type": "paid",
    "tier": "high",
    "fan_count": 8500
  },
  "volume_config": {
    "level": "high",
    "revenue_per_day": 6,
    "engagement_per_day": 5,
    "retention_per_day": 2,
    "weekly_distribution": {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13},
    "dow_multipliers_used": {"0": 0.95, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.1, "5": 1.0, "6": 1.0},
    "content_allocations": {"solo": 3, "lingerie": 2},
    "confidence_score": 0.85,
    "message_count": 156,
    "fused_saturation": 45.0,
    "fused_opportunity": 62.0,
    "elasticity_capped": false,
    "caption_warnings": [],
    "adjustments_applied": ["base_tier_calculation", "multi_horizon_fusion", "dow_multipliers", "prediction_tracked"],
    "prediction_id": 123
  },
  "performance": {
    "saturation_score": 45,
    "opportunity_score": 62,
    "revenue_trend": "up"
  },
  "send_types": [...],  // 22 types total (some page-specific)
  "vault": {
    "video": 45,
    "picture": 120,
    "flyer": 30
  },
  "timing": {
    "peak_hours": [20, 21, 22],
    "avoid_hours": [3, 4, 5]
  }
}
```

---

## Phase 2: SEND TYPE ALLOCATION (with Daily Variation)

**Duration**: ~1 second
**Objective**: Distribute send types across the 7-day schedule with authentic daily variation
**Input**: Volume config, days to schedule, page type, performance data
**Variation**: Daily strategy rotation, flavor emphasis, allocation pattern shifts

### 2.1 Calculate Daily Quotas from weekly_distribution (v2.2)

**CRITICAL**: Phase 2 MUST consume `weekly_distribution` from the OptimizedVolumeResult, NOT apply hardcoded DOW modifiers.

```
OPTIMIZED CALCULATION (REQUIRED):

# Get per-day totals from optimized volume config
FOR day_index in 0..6:
    daily_total = volume_config.weekly_distribution[day_index]

    # Distribute daily total across categories proportionally
    total_ratio = revenue_per_day + engagement_per_day + retention_per_day
    revenue_ratio = revenue_per_day / total_ratio
    engagement_ratio = engagement_per_day / total_ratio
    retention_ratio = retention_per_day / total_ratio

    day_quotas[day_index] = {
        revenue: round(daily_total * revenue_ratio),
        engagement: round(daily_total * engagement_ratio),
        retention: round(daily_total * retention_ratio)
    }

# Example for HIGH tier creator (alexia):
# weekly_distribution = {"0": 12, "1": 13, "2": 13, "3": 13, "4": 14, "5": 13, "6": 13}
# revenue_per_day=6, engagement_per_day=5, retention_per_day=2 (ratio: 6:5:2)
#
# Monday (day 0, total=12): revenue=6, engagement=5, retention=1
# Friday (day 4, total=14): revenue=6, engagement=5, retention=3
```

**WHY weekly_distribution vs. Manual DOW Modifiers:**

| Approach | Source | Advantages |
|----------|--------|------------|
| `weekly_distribution` (NEW) | Calculated from historical performance data | Data-driven, creator-specific, accounts for confidence |
| Manual DOW modifiers (LEGACY) | Hardcoded table | Generic, ignores creator patterns |

The `dow_multipliers_used` field shows what multipliers produced the distribution, enabling transparency and debugging.

### 2.2 Apply Confidence-Based Adjustments

```
CONFIDENCE-BASED QUOTA ADJUSTMENT:

IF volume_config.confidence_score < 0.6:
    # Low confidence - use conservative allocation
    # Dampen quotas toward tier minimums
    dampening_factor = volume_config.confidence_score / 0.6

    FOR day_index in 0..6:
        day_quotas[day_index].revenue = round(
            day_quotas[day_index].revenue * dampening_factor +
            tier_minimum.revenue * (1 - dampening_factor)
        )

    log_warning("Low confidence ({confidence_score}) - using conservative quotas")

ELSE IF volume_config.confidence_score >= 0.8:
    # High confidence - trust quotas fully
    # No adjustment needed
    pass

ELSE:
    # Moderate confidence (0.6-0.8)
    # Minor dampening toward baseline
    dampening_factor = (volume_config.confidence_score - 0.6) / 0.2
    # Apply 10% dampening
    ...
```

### 2.2.1 Legacy DOW Modifiers (DEPRECATED)

**NOTE**: The following table is DEPRECATED and should NOT be used when `weekly_distribution` is available. It is retained only for fallback when `weekly_distribution` is empty or missing.

```
LEGACY DAY-OF-WEEK MODIFIERS (FALLBACK ONLY):

| Day       | Revenue | Engagement | Retention | Rationale              |
|-----------|---------|------------|-----------|------------------------|
| Monday    | -1      | 0          | 0         | Lower post-weekend     |
| Tuesday   | 0       | 0          | 0         | Standard               |
| Wednesday | 0       | 0          | 0         | Standard               |
| Thursday  | 0       | 0          | 0         | Standard               |
| Friday    | +1      | 0          | 0         | Weekend prep           |
| Saturday  | 0       | +1         | 0         | High activity          |
| Sunday    | +1      | 0          | 0         | High conversion        |

FALLBACK ALGORITHM (only if weekly_distribution is empty):

FOR each day in schedule_week:
    day_quotas = {
        revenue: max(1, revenue_quota + day_modifier.revenue),
        engagement: max(1, engagement_quota + day_modifier.engagement),
        retention: max(1, retention_quota + day_modifier.retention)
    }
```

### 2.3 Select Daily Strategy (Variation System)

```
DAILY STRATEGY ROTATION:

Before allocation, select a strategy for each day from the rotation:

available_strategies = [
    "revenue_focus",      # More ppv_unlock, bundle, flash_bundle
    "engagement_burst",   # More bump_*, dm_farm, like_farm
    "balanced_standard",  # Standard mix per volume config
    "variety_max",        # Maximum type diversity, avoid repeats
    "storytelling"        # More bump_descriptive, engagement-focused
]

# Select strategy with rotation enforcement
FOR each day in schedule_week:
    # Ensure no strategy repeats consecutively
    IF day > 1:
        previous_strategy = day_strategy[day - 1]
        eligible_strategies = [s for s in available_strategies
                             if s != previous_strategy]
    ELSE:
        eligible_strategies = available_strategies

    # Weighted random selection based on performance
    IF saturation_score > 70:
        # Favor engagement and storytelling
        weights = {
            "revenue_focus": 0.1,
            "engagement_burst": 0.3,
            "balanced_standard": 0.2,
            "variety_max": 0.2,
            "storytelling": 0.2
        }
    ELSE IF opportunity_score > 70:
        # Favor revenue strategies
        weights = {
            "revenue_focus": 0.3,
            "engagement_burst": 0.1,
            "balanced_standard": 0.2,
            "variety_max": 0.2,
            "storytelling": 0.2
        }
    ELSE:
        # Balanced distribution
        weights = {
            "revenue_focus": 0.2,
            "engagement_burst": 0.2,
            "balanced_standard": 0.2,
            "variety_max": 0.2,
            "storytelling": 0.2
        }

    day_strategy[day] = weighted_select(eligible_strategies, weights)

    # Set flavor emphasis based on strategy
    day_flavor[day] = get_flavor_for_strategy(day_strategy[day])

STRATEGY FLAVOR MAPPING:

| Strategy            | Flavor Emphasis                                    |
|---------------------|----------------------------------------------------|
| revenue_focus       | bundle, flash_bundle, vip_program priority         |
| engagement_burst    | dm_farm, like_farm, bump_* variety                 |
| balanced_standard   | Even distribution per volume config                |
| variety_max         | All 22 types in rotation, no repeats               |
| storytelling        | bump_descriptive, bump_normal, wall_link_drop      |
```

### 2.4 Check Weekly Limits

Before allocation, verify weekly-capped types:

```
WEEKLY LIMITED TYPES:

| Type            | Max/Week | Check                                    |
|-----------------|----------|------------------------------------------|
| vip_program     | 1        | Count existing, skip if at limit         |
| snapchat_bundle | 1        | Count existing, skip if at limit         |
| tip_goal        | 3        | Count existing, skip if at limit         |

FOR each weekly_limited_type:
    current_count = count_in_week(weekly_limited_type)
    IF current_count >= max_per_week:
        remove_from_available(weekly_limited_type)
```

### 2.4.1 Send Type Deprecation Notice

**IMPORTANT - ppv_message Deprecation:**

The `ppv_message` send type has been **DEPRECATED** as of 2025-12-16 and merged into `ppv_unlock`.

**Migration Details:**
- **Deprecated:** `ppv_message` (standalone DM PPV type)
- **Replacement:** `ppv_unlock` (unified type for both videos and pictures via DMs)
- **Transition Period:** 30 days (until 2025-01-16)
- **Removal Date:** 2025-01-16

**During Transition (2025-12-16 to 2025-01-16):**
- Both `ppv_message` and `ppv_unlock` will function
- New schedules MUST use `ppv_unlock`
- Existing schedules using `ppv_message` will continue to work
- System will automatically map `ppv_message` → `ppv_unlock` in backend

**After 2025-01-16:**
- `ppv_message` will be removed from the send_types table
- Any schedules still referencing `ppv_message` will fail validation
- All historical data will be migrated to `ppv_unlock`

**Migration Actions Required:**
```python
# For Phase 2 Allocation Logic - Update immediately:
eligible_revenue_types = [
    "ppv_unlock",      # Use this (replaces ppv_video AND ppv_message)
    "ppv_wall",        # FREE pages only
    "tip_goal",        # PAID pages only
    "vip_program",
    "game_post",
    "bundle",
    "flash_bundle",
    "snapchat_bundle",
    "first_to_tip"
]

# DO NOT include ppv_message in new allocations
# DO NOT include ppv_video (also deprecated, use ppv_unlock)
```

**Why This Matters:**
- Simplifies the 22-type taxonomy by unifying PPV types
- `ppv_unlock` works for videos, pictures, and all DM PPV scenarios
- Reduces caption pool fragmentation
- Aligns with platform naming conventions

### 2.5 Allocation Algorithm (with Strategy-Based Variation)

```
ALLOCATION MATRIX STRUCTURE:

allocation_matrix[day][slot] = {
    send_type_key: string,
    category: "revenue" | "engagement" | "retention",
    priority: integer,
    strategy_used: string,         # NEW: Track strategy applied
    flavor_emphasis: string         # NEW: Track daily flavor
}

ALLOCATION ALGORITHM (Strategy-Aware):

FOR each day in 1..7:
    day_slots = []
    category_counts = { revenue: 0, engagement: 0, retention: 0 }

    # Get daily strategy and flavor
    strategy = day_strategy[day]
    flavor = day_flavor[day]

    # Adjust type weights based on strategy
    type_weights = apply_strategy_weights(strategy, performance_scores)

    # Allocate revenue slots with strategy influence
    WHILE category_counts.revenue < day_quotas[day].revenue:
        eligible = filter_available_revenue_types(day)
        IF empty(eligible): BREAK

        # Apply strategy-based selection
        IF strategy == "revenue_focus":
            # Prioritize bundle, flash_bundle, vip_program
            selected = weighted_select(eligible, weights=type_weights,
                                      boost=["bundle", "flash_bundle", "vip_program"])
        ELSE IF strategy == "variety_max":
            # Select least-used type this week
            selected = select_least_used(eligible, weekly_usage_counts)
        ELSE:
            # Standard weighted selection
            selected = weighted_select(eligible, weights=type_weights)

        # Variety rule: no same type twice in a row
        IF day_slots.length > 0 AND selected == day_slots[-1].send_type_key:
            CONTINUE

        day_slots.append({
            send_type_key: selected,
            category: "revenue",
            priority: category_counts.revenue + 1,
            strategy_used: strategy,
            flavor_emphasis: flavor
        })
        increment_daily_count(selected)
        increment_weekly_count(selected)
        category_counts.revenue += 1

    # Allocate engagement slots with strategy influence
    WHILE category_counts.engagement < day_quotas[day].engagement:
        eligible = filter_available_engagement_types(day)
        IF empty(eligible): BREAK

        # Apply strategy-based selection
        IF strategy == "engagement_burst":
            # Prioritize dm_farm, like_farm, bump variety
            selected = weighted_select(eligible, weights=type_weights,
                                      boost=["dm_farm", "like_farm", "bump_normal"])
        ELSE IF strategy == "storytelling":
            # Prioritize bump_descriptive, bump_normal
            selected = weighted_select(eligible, weights=type_weights,
                                      boost=["bump_descriptive", "bump_normal"])
        ELSE IF strategy == "variety_max":
            selected = select_least_used(eligible, weekly_usage_counts)
        ELSE:
            selected = weighted_select(eligible, weights=type_weights)

        # Variety rule enforcement
        IF day_slots.length > 0 AND selected == day_slots[-1].send_type_key:
            CONTINUE

        day_slots.append({
            send_type_key: selected,
            category: "engagement",
            priority: category_counts.engagement + 1,
            strategy_used: strategy,
            flavor_emphasis: flavor
        })
        increment_daily_count(selected)
        increment_weekly_count(selected)
        category_counts.engagement += 1

    # Allocate retention slots (same pattern with strategy)
    WHILE category_counts.retention < day_quotas[day].retention:
        eligible = filter_available_retention_types(day)
        # Filter by page_type for paid-only types
        IF creator.page_type == "free":
            eligible = filter(eligible, key NOT IN ["renew_on_post",
                            "renew_on_message", "expired_winback"])
        IF empty(eligible): BREAK

        selected = weighted_select(eligible, weights=type_weights)

        day_slots.append({
            send_type_key: selected,
            category: "retention",
            priority: category_counts.retention + 1,
            strategy_used: strategy,
            flavor_emphasis: flavor
        })
        increment_daily_count(selected)
        increment_weekly_count(selected)
        category_counts.retention += 1

    # Interleave categories for variety
    allocation_matrix[day] = interleave_categories(day_slots)

    # Log strategy used for validation
    log_allocation_metadata(day, strategy, flavor, day_slots)
```

### 2.6 Interleaving Pattern

```
INTERLEAVE ALGORITHM:

# Input: [R1, R2, R3, E1, E2, E3, Ret1, Ret2]
# Output: [R1, E1, R2, E2, Ret1, R3, E3, Ret2]

FUNCTION interleave_categories(slots):
    revenue = filter(slots, category="revenue")
    engagement = filter(slots, category="engagement")
    retention = filter(slots, category="retention")

    result = []
    r_idx = e_idx = ret_idx = 0

    WHILE any_remaining:
        IF r_idx < len(revenue):
            result.append(revenue[r_idx++])
        IF e_idx < len(engagement):
            result.append(engagement[e_idx++])
        IF r_idx < len(revenue):
            result.append(revenue[r_idx++])
        IF e_idx < len(engagement):
            result.append(engagement[e_idx++])
        IF ret_idx < len(retention):
            result.append(retention[ret_idx++])

    RETURN result
```

### Phase 2 Output State

```json
{
  "allocation_matrix": {
    "2025-01-20": [
      {
        "send_type_key": "ppv_unlock",
        "category": "revenue",
        "priority": 1,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      },
      {
        "send_type_key": "bump_normal",
        "category": "engagement",
        "priority": 1,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      },
      {
        "send_type_key": "bundle",
        "category": "revenue",
        "priority": 2,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      },
      {
        "send_type_key": "dm_farm",
        "category": "engagement",
        "priority": 2,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      },
      {
        "send_type_key": "renew_on_message",
        "category": "retention",
        "priority": 1,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      },
      {
        "send_type_key": "ppv_unlock",
        "category": "revenue",
        "priority": 3,
        "strategy_used": "revenue_focus",
        "flavor_emphasis": "bundle_flash_vip"
      }
    ],
    "2025-01-21": [...],
    // ... days 3-7
  },
  "daily_strategies": {
    "2025-01-20": "revenue_focus",
    "2025-01-21": "storytelling",
    "2025-01-22": "variety_max",
    "2025-01-23": "engagement_burst",
    "2025-01-24": "balanced_standard",
    "2025-01-25": "revenue_focus",
    "2025-01-26": "variety_max"
  },
  "weekly_summary": {
    "total_items": 84,
    "by_category": { "revenue": 42, "engagement": 35, "retention": 7 },
    "unique_send_types": 18,
    "strategy_distribution": {
      "revenue_focus": 2,
      "storytelling": 1,
      "variety_max": 2,
      "engagement_burst": 1,
      "balanced_standard": 1
    }
  }
}
```

---

## Phase 3: CONTENT MATCHING

**Duration**: ~3 seconds
**Objective**: Select optimal captions for each allocated slot
**Input**: Allocation matrix, creator ID, vault availability

### 3.0 Caption Pool Configuration

**CRITICAL**: Caption selection now operates on the UNIVERSAL caption pool.

The following changes have been implemented:
1. **Universal Captions**: All 59,405 captions available to all creators
   - caption_bank.creator_id is IGNORED in queries
   - Historical creator assignments preserved for analytics only

2. **Vault Matrix Filtering**: HARD filter by allowed content types
   - Only captions with content_type_id IN creator's vault_matrix are returned
   - Creators must have vault_matrix entries to receive captions

3. **Freshness-First Ordering**:
   - Captions ordered by freshness_score DESC, THEN performance_score DESC
   - Prioritizes unused captions while still preferring high earners

4. **Scoring Weights (Updated)**:
   | Component | Weight | Purpose |
   |-----------|--------|---------|
   | Freshness | 40% | Prioritize unused captions |
   | Performance | 35% | Prefer high-earning captions |
   | Type Priority | 15% | Send type compatibility |
   | Diversity | 5% | Prevent repetition |
   | Persona | 5% | Minor tone alignment |

### 3.1 Caption Selection Algorithm

```
FOR each slot in allocation_matrix:
    # Get compatible captions for this send type
    captions = MCP CALL: get_send_type_captions(
        creator_id = creator.id,
        send_type_key = slot.send_type_key,
        min_performance = 40,
        min_freshness = 30,
        limit = 10
    )

    # Calculate composite score
    FOR each caption in captions:
        caption.composite_score = (
            caption.freshness_score * 0.40 +
            caption.performance_score * 0.35 +
            caption.type_priority_score * 0.15 +
            caption.diversity_score * 0.05 +
            caption.persona_score * 0.05
        )

    # Sort by composite score descending
    captions.sort(key=composite_score, descending=True)

    # Select highest scoring unused caption
    FOR each caption in captions:
        IF caption.id NOT IN used_captions:
            slot.caption = caption
            used_captions.add(caption.id)
            BREAK
```

### 3.2 Caption Requirements by Send Type

```
CAPTION TYPE REQUIREMENTS (from send_type_caption_requirements):

| Send Type       | Primary Caption Type | Secondary      | Priority |
|-----------------|---------------------|----------------|----------|
| ppv_unlock      | ppv_offer           | teaser         | 1, 2     |
| ppv_wall        | ppv_offer           | teaser         | 1, 2     |
| tip_goal        | tip_goal_promo      | game_invite    | 1, 2     |
| vip_program     | vip_promo           | exclusive      | 1, 2     |
| game_post       | game_invite         | playful        | 1, 2     |
| bundle          | bundle_offer        | ppv_offer      | 1, 2     |
| flash_bundle    | urgency             | bundle_offer   | 1, 2     |
| bump_normal     | flirty              | casual         | 1, 2     |
| bump_descriptive| story               | personal       | 1, 2     |
| bump_text_only  | casual              | flirty         | 1, 2     |
| ppv_followup    | ppv_followup        | close_sale     | 1, 2     |
| renew_on_message| renewal             | appreciation   | 1, 2     |
| expired_winback | winback             | miss_you       | 1, 2     |
```

### 3.3 Cross-Reference Vault Availability

```
FOR each slot in allocation_matrix:
    send_type_details = get_send_type_details(slot.send_type_key)

    IF send_type_details.requires_media:
        required_type = send_type_details.media_type
        IF required_type NOT IN vault.available_content_types:
            # Mark for content creation or skip
            slot.vault_warning = "Missing " + required_type
            slot.content_type_id = NULL  # Cannot assign
        ELSE:
            slot.content_type_id = get_best_content(required_type)

    IF send_type_details.requires_flyer:
        IF "flyer" NOT IN vault.available_content_types:
            slot.vault_warning = "Missing flyer"
            slot.flyer_required = 1
```

### 3.4 Freshness Scoring

```
FRESHNESS CALCULATION:

freshness_score = 100 - (days_since_last_use * decay_rate)

WHERE:
  - decay_rate = 10 (standard)
  - days_since_last_use = DATEDIFF(NOW(), caption.last_used_date)

FRESHNESS THRESHOLDS:

| Score    | Status    | Action                          |
|----------|-----------|--------------------------------|
| 80-100   | Fresh     | Prioritize for use             |
| 50-79    | Moderate  | Available, lower priority      |
| 30-49    | Stale     | Use only if no alternatives    |
| 0-29     | Exhausted | Exclude unless forced          |
```

### 3.5 Fallback Handling

```
IF no fresh captions available for send_type:

    # Strategy 1: Lower freshness threshold
    captions = get_send_type_captions(
        creator_id = creator.id,
        send_type_key = slot.send_type_key,
        min_freshness = 10,  # Lowered from 30
        limit = 5
    )

    IF captions.length > 0:
        slot.caption = captions[0]
        slot.freshness_warning = "Using low-freshness caption"

    # Strategy 2: Use generic top captions
    ELSE:
        captions = get_top_captions(
            creator_id = creator.id,
            caption_type = infer_compatible_type(slot.send_type_key),
            limit = 5
        )
        IF captions.length > 0:
            slot.caption = captions[0]
            slot.type_mismatch_warning = "Using generic caption"

    # Strategy 3: Flag for manual creation
    ELSE:
        slot.caption = NULL
        slot.needs_caption = True
        slot.error = "No compatible captions available"
```

### Phase 3 Output State

```json
{
  "content_assignments": [
    {
      "slot_id": "2025-01-20_1",
      "send_type_key": "ppv_unlock",
      "caption": {
        "id": 789,
        "text": "Hey babe, I made this just for you...",
        "performance_score": 85.2,
        "freshness_score": 92.0,
        "type_priority_score": 88.0,
        "diversity_score": 95.0,
        "persona_score": 82.0,
        "composite_score": 88.67
      },
      "content_type_id": 12,
      "vault_warning": null
    },
    // ... additional slots
  ],
  "used_captions": [789, 456, 123, ...],
  "warnings": [
    { "slot_id": "2025-01-22_3", "warning": "Using low-freshness caption" }
  ]
}
```

---

## Phase 4: AUDIENCE TARGETING

**Duration**: ~1 second
**Objective**: Assign appropriate audience targets for each schedule item
**Input**: Content assignments, page type, send type requirements

### 4.1 Load Available Targets

```
MCP CALL: get_audience_targets(
    page_type = creator.page_type,
    channel_key = NULL  # Load all, filter per item
)

RETURNS: Array of applicable audience targets

TARGET CATALOG:

| Target Key         | Display Name          | Page Types  | Channels              |
|--------------------|-----------------------|-------------|-----------------------|
| all_active         | All Active Fans       | paid, free  | mass, wall, story     |
| renew_off          | Renew Off             | paid only   | targeted, mass        |
| renew_on           | Renew On              | paid only   | targeted, mass        |
| expired_recent     | Recently Expired      | paid only   | targeted              |
| expired_all        | All Expired           | paid only   | targeted              |
| never_purchased    | Never Purchased       | paid, free  | targeted, mass        |
| recent_purchasers  | Recent Purchasers     | paid, free  | targeted, mass        |
| high_spenders      | High Spenders         | paid, free  | targeted, mass        |
| inactive_7d        | Inactive 7 Days       | paid, free  | targeted, mass        |
| ppv_non_purchasers | PPV Non-Purchasers    | paid, free  | targeted              |
```

### 4.2 Target Assignment Algorithm

```
FOR each slot in content_assignments:

    # Get send type targeting requirements
    details = MCP CALL: get_send_type_details(slot.send_type_key)

    # Check for required target
    IF details.required_target:
        slot.target_key = details.required_target
        # Examples:
        # - renew_on_message REQUIRES renew_off
        # - ppv_followup REQUIRES ppv_non_purchasers
        # - expired_winback REQUIRES expired_recent OR expired_all

    # Apply default target
    ELSE IF details.default_target:
        slot.target_key = details.default_target

    # Use broad targeting
    ELSE:
        slot.target_key = "all_active"

    # Validate target is applicable
    target = find_target(slot.target_key)
    IF creator.page_type NOT IN target.applicable_page_types:
        # Fallback for incompatible target
        slot.target_key = "all_active"
        slot.target_warning = "Target not applicable for page type"
```

### 4.3 Send Type to Target Mapping

```
DEFAULT TARGET MAPPING:

| Send Type          | Default Target     | Required Target      | Notes                    |
|--------------------|--------------------|----------------------|--------------------------|
| ppv_unlock         | all_active         | -                    | Broad reach for revenue  |
| ppv_wall           | all_active         | -                    | FREE pages only          |
| tip_goal           | all_active         | -                    | PAID pages only          |
| vip_program        | high_spenders      | -                    | Premium targeting        |
| game_post          | all_active         | -                    | Participation needed     |
| bundle             | all_active         | -                    | Broad or targeted        |
| flash_bundle       | all_active         | -                    | Urgency works broadly    |
| snapchat_bundle    | all_active         | -                    | Nostalgia appeal         |
| first_to_tip       | all_active         | -                    | Competition needs volume |
| link_drop          | all_active         | -                    | Maximum reach            |
| wall_link_drop     | all_active         | -                    | Wall post, no targeting  |
| bump_normal        | all_active         | -                    | General engagement       |
| bump_descriptive   | all_active         | -                    | Story content            |
| bump_text_only     | all_active         | -                    | Light touch              |
| bump_flyer         | all_active         | -                    | Visual impact            |
| dm_farm            | all_active         | -                    | Re-engagement option     |
| like_farm          | all_active         | -                    | Broad participation      |
| live_promo         | all_active         | -                    | Maximum attendance       |
| renew_on_post      | all_active         | -                    | Wall post visible to all |
| renew_on_message   | -                  | renew_off            | MUST target renew_off    |
| ppv_followup       | -                  | ppv_non_purchasers   | MUST target non-buyers   |
| expired_winback    | expired_recent     | -                    | Win-back targeting       |
```

### 4.4 Determine Channel

```
FOR each slot in content_assignments:

    details = get_send_type_details(slot.send_type_key)

    # Channel is determined by send type platform_feature
    IF details.platform_feature == "mass_message":
        slot.channel_key = "mass_message"
    ELSE IF details.platform_feature == "wall_post":
        slot.channel_key = "wall_post"
    ELSE IF details.platform_feature == "targeted_message":
        slot.channel_key = "targeted_message"
    ELSE:
        slot.channel_key = "mass_message"  # Default

    # Validate channel supports targeting
    channel = get_channel(slot.channel_key)
    IF slot.target_key != "all_active" AND NOT channel.supports_targeting:
        slot.target_warning = "Channel does not support targeting"
        slot.target_key = "all_active"
```

### Phase 4 Output State

```json
{
  "targeted_items": [
    {
      "slot_id": "2025-01-20_1",
      "send_type_key": "ppv_unlock",
      "channel_key": "mass_message",
      "target_key": "all_active",
      "caption": {...}
    },
    {
      "slot_id": "2025-01-20_5",
      "send_type_key": "renew_on_message",
      "channel_key": "targeted_message",
      "target_key": "renew_off",
      "caption": {...}
    }
  ]
}
```

---

## Phase 5: TIMING OPTIMIZATION (with Daily Variation)

**Duration**: ~2 seconds
**Objective**: Calculate optimal posting times with type-specific rules and daily variation
**Input**: Targeted items, historical timing data, send type timing constraints, daily strategies
**Variation**: Daily prime hour rotation, time offsets, jitter application

### 5.1 Priority Sorting

```
# Sort items by priority for optimal time slot assignment

PRIORITY ORDER:
1. Revenue items with highest price (ppv_unlock, bundle)
2. Other revenue items
3. Engagement items (interleaved)
4. Retention items

sorted_items = items.sort(key=lambda x: (
    -category_priority[x.category],
    -x.priority,
    -x.suggested_price or 0
))
```

### 5.2 Generate Daily Timing Variations (NEW - Variation System)

```
DAILY TIMING VARIATION SETUP:

Before time assignment, calculate daily timing adjustments:

# Base prime hours from historical data
base_prime_hours = timing.peak_hours  # e.g., [20, 21, 22]

FOR each day in schedule_week:
    # Rotate prime hours (±1 hour shift)
    day_offset = (day_index % 3) - 1  # Rotates: -1, 0, +1
    daily_prime_hours[day] = [h + day_offset for h in base_prime_hours]
    daily_prime_hours[day] = [h for h in daily_prime_hours[day]
                              if 8 <= h <= 23]  # Keep within bounds

    # Generate morning/evening shift offsets
    IF day_index % 2 == 0:
        # Even days: shift morning earlier, evening later
        morning_offset[day] = -15  # minutes
        evening_offset[day] = +20  # minutes
    ELSE:
        # Odd days: shift morning later, evening earlier
        morning_offset[day] = +15  # minutes
        evening_offset[day] = -20  # minutes

    # Set jitter range (randomization within bounds)
    jitter_range[day] = random.randint(-7, +8)  # minutes

DAILY PRIME HOUR EXAMPLES:

| Day       | Base Prime | Offset | Daily Prime | Rationale              |
|-----------|------------|--------|-------------|------------------------|
| Monday    | [20,21,22] | -1     | [19,20,21]  | Rotate earlier         |
| Tuesday   | [20,21,22] | 0      | [20,21,22]  | Standard               |
| Wednesday | [20,21,22] | +1     | [21,22,23]  | Rotate later           |
| Thursday  | [20,21,22] | -1     | [19,20,21]  | Rotate earlier         |
| Friday    | [20,21,22] | 0      | [20,21,22]  | Standard               |
| Saturday  | [20,21,22] | +1     | [21,22,23]  | Rotate later           |
| Sunday    | [20,21,22] | -1     | [19,20,21]  | Rotate earlier         |
```

### 5.3 Optimal Time Slot Selection (with Variation)

```
FOR each day in schedule_week:
    day_items = filter(sorted_items, day=day)
    assigned_times = []

    # Get daily timing adjustments
    prime_hours = daily_prime_hours[day]
    morning_shift = morning_offset[day]
    evening_shift = evening_offset[day]
    jitter = jitter_range[day]

    FOR each item in day_items:
        # Get send type timing preferences
        details = get_send_type_details(item.send_type_key)

        # Determine preferred time window with daily variation
        IF item.category == "revenue":
            preferred_hours = prime_hours  # Rotated prime hours
            time_shift = evening_shift     # Evening offset
        ELSE IF item.category == "engagement":
            base_hours = [9, 10, 11, 14, 15, 16]
            preferred_hours = base_hours
            time_shift = morning_shift     # Morning offset
        ELSE:  # retention
            preferred_hours = [16, 17, 18]
            time_shift = 0                 # No shift for retention

        # Find available slot with variation
        FOR hour in preferred_hours:
            base_time = f"{hour:02d}:00"

            # Apply time shift and jitter
            candidate_minutes = (hour * 60) + time_shift + jitter
            candidate_hour = candidate_minutes // 60
            candidate_minute = candidate_minutes % 60

            # Ensure valid time range (08:00 - 23:30)
            IF candidate_hour < 8:
                candidate_hour = 8
                candidate_minute = 0
            IF candidate_hour > 23 OR (candidate_hour == 23 AND candidate_minute > 30):
                candidate_hour = 23
                candidate_minute = 30

            candidate_time = f"{candidate_hour:02d}:{candidate_minute:02d}:00"

            # Check spacing constraints
            IF is_valid_time_slot(candidate_time, item, assigned_times, details):
                item.scheduled_time = candidate_time
                item.variation_metadata = {
                    "base_hour": hour,
                    "time_shift": time_shift,
                    "jitter": jitter,
                    "daily_strategy": day_strategy[day]
                }
                assigned_times.append({
                    time: candidate_time,
                    send_type_key: item.send_type_key
                })
                BREAK

        # Fallback to any available slot
        IF NOT item.scheduled_time:
            item.scheduled_time = find_any_available_slot(assigned_times, details)
            item.variation_metadata = {
                "fallback_used": True,
                "reason": "No preferred slot available"
            }
```

### 5.4 Spacing Constraint Validation

```
FUNCTION is_valid_time_slot(candidate, item, assigned, details):

    # Rule 1: Minimum 30 minutes between any sends
    FOR each assigned_slot in assigned:
        time_diff = abs(candidate - assigned_slot.time)
        IF time_diff < 30 minutes:
            RETURN False

    # Rule 2: Minimum time between same type
    min_between = details.min_time_between  # From send type config
    same_type_slots = filter(assigned, send_type_key=item.send_type_key)
    FOR each slot in same_type_slots:
        time_diff = abs(candidate - slot.time)
        IF time_diff < min_between:
            RETURN False

    # Rule 3: No more than 3 sends per 4-hour block
    block_start = floor(candidate.hour / 4) * 4
    block_end = block_start + 4
    block_count = count(assigned, time in [block_start, block_end])
    IF block_count >= 3:
        RETURN False

    RETURN True
```

### 5.5 Weekly Time Repeat Validation (NEW - Variation System)

```
VALIDATE NO EXACT TIME REPEATS > 2x WEEKLY:

After all timing assignments complete, validate time diversity:

time_usage_counts = {}

FOR each item in timed_items:
    time_only = item.scheduled_time  # e.g., "20:00:00"
    IF time_only NOT IN time_usage_counts:
        time_usage_counts[time_only] = 0
    time_usage_counts[time_only] += 1

FOR time, count in time_usage_counts:
    IF count > 2:
        # Find items to adjust
        items_at_time = filter(timed_items, scheduled_time=time)
        # Keep first 2, adjust the rest
        FOR item in items_at_time[2:]:
            # Shift by ±10-15 minutes with jitter
            adjustment = random.choice([-15, -10, +10, +15])
            new_time = item.scheduled_time + minutes(adjustment)
            # Validate new time doesn't conflict
            IF is_valid_time_slot(new_time, item, all_assigned_times, details):
                item.scheduled_time = new_time
                item.variation_metadata["time_adjusted"] = True
                item.variation_metadata["adjustment_reason"] = "Weekly repeat limit"

WEEKLY TIME DIVERSITY TARGET:

- No single exact time (e.g., 20:00:00) used more than 2x per week
- This ensures natural variation across the schedule
- Combined with daily jitter, creates authentic human scheduling patterns
```

### 5.6 Minimum Time Between Rules

```
MIN TIME BETWEEN SAME TYPE:

| Send Type         | Min Between | Rationale                |
|-------------------|-------------|--------------------------|
| ppv_unlock        | 2 hours     | Avoid PPV fatigue        |
| ppv_wall          | 3 hours     | FREE page PPV spacing    |
| tip_goal          | 4 hours     | Goal fatigue prevention  |
| vip_program       | 24 hours    | Once per day max         |
| game_post         | 4 hours     | Space out games          |
| bundle            | 3 hours     | Variety needed           |
| flash_bundle      | 6 hours     | Urgency preserved        |
| snapchat_bundle   | 24 hours    | Once per day max         |
| first_to_tip      | 6 hours     | Competition fatigue      |
| link_drop         | 2 hours     | Avoid link spam          |
| wall_link_drop    | 3 hours     | Wall visibility          |
| bump_normal       | 1 hour      | Light touch allowed      |
| bump_descriptive  | 2 hours     | Story pacing             |
| bump_text_only    | 2 hours     | Avoid text spam          |
| bump_flyer        | 4 hours     | Visual impact spacing    |
| dm_farm           | 4 hours     | DM fatigue prevention    |
| like_farm         | 24 hours    | Once per day max         |
| live_promo        | 2 hours     | Event reminders ok       |
| renew_on_post     | 12 hours    | Avoid renewal pressure   |
| renew_on_message  | 24 hours    | Once per day max         |
| ppv_followup      | 1 hour      | Can be more frequent     |
| expired_winback   | 24 hours    | Once per day max         |
```

### 5.7 Set Expiration Times

```
FOR each item in scheduled_items:

    details = get_send_type_details(item.send_type_key)

    IF details.default_expiration_hours:
        item.expires_at = item.scheduled_datetime + hours(details.default_expiration_hours)
    ELSE:
        item.expires_at = NULL  # No expiration

EXPIRATION DEFAULTS:

| Send Type      | Expiration | Purpose                    |
|----------------|------------|----------------------------|
| game_post      | 24 hours   | Game time limit            |
| flash_bundle   | 24 hours   | Flash sale urgency         |
| link_drop      | 24 hours   | Campaign freshness         |
| first_to_tip   | 24 hours   | Competition window         |
| (others)       | NULL       | No automatic expiration    |
```

### Phase 5 Output State

```json
{
  "timed_items": [
    {
      "slot_id": "2025-01-20_1",
      "send_type_key": "ppv_unlock",
      "scheduled_date": "2025-01-20",
      "scheduled_time": "20:07:00",
      "expires_at": null,
      "channel_key": "mass_message",
      "target_key": "all_active",
      "caption": {...},
      "variation_metadata": {
        "base_hour": 20,
        "time_shift": 20,
        "jitter": -13,
        "daily_strategy": "revenue_focus",
        "prime_hours_used": [19, 20, 21],
        "time_adjusted": false
      }
    },
    {
      "slot_id": "2025-01-20_2",
      "send_type_key": "bump_normal",
      "scheduled_date": "2025-01-20",
      "scheduled_time": "08:52:00",
      "expires_at": null,
      "channel_key": "mass_message",
      "target_key": "all_active",
      "caption": {...},
      "variation_metadata": {
        "base_hour": 9,
        "time_shift": -15,
        "jitter": 7,
        "daily_strategy": "revenue_focus",
        "time_adjusted": false
      }
    }
  ],
  "timing_summary": {
    "total_items": 48,
    "time_diversity": {
      "unique_times": 42,
      "max_repeats": 2,
      "jitter_applied": 48
    },
    "daily_prime_hours": {
      "2025-01-20": [19, 20, 21],
      "2025-01-21": [20, 21, 22],
      "2025-01-22": [21, 22, 23],
      "2025-01-23": [19, 20, 21],
      "2025-01-24": [20, 21, 22],
      "2025-01-25": [21, 22, 23],
      "2025-01-26": [19, 20, 21]
    }
  }
}
```

---

## Phase 6: FOLLOW-UP GENERATION

**Duration**: ~1 second
**Objective**: Create automatic follow-up items for PPV sends
**Input**: Timed items with eligible PPV sends

### 6.1 Identify Eligible Items

```
eligible_items = []

FOR each item in timed_items:
    details = get_send_type_details(item.send_type_key)

    IF details.can_have_followup == 1:
        eligible_items.append(item)

# Eligible send types:
# - ppv_unlock (can_have_followup = 1)
# - ppv_wall (can_have_followup = 1)
# - tip_goal (can_have_followup = 1 for non-tippers)
```

### 6.2 Generate Follow-up Items

```
followup_count = 0
MAX_FOLLOWUPS_PER_DAY = 4

FOR each parent in eligible_items:

    # Check daily limit
    day_followups = count(followups, date=parent.scheduled_date)
    IF day_followups >= MAX_FOLLOWUPS_PER_DAY:
        log("Followup limit reached, skipping for " + parent.slot_id)
        CONTINUE

    # Create follow-up item
    followup = {
        send_type_key: "ppv_followup",
        category: "retention",
        channel_key: "targeted_message",
        target_key: "ppv_non_purchasers",
        is_follow_up: 1,
        parent_item_id: parent.slot_id
    }

    # Calculate timing
    default_delay = 20  # minutes
    followup.scheduled_date = parent.scheduled_date
    followup.scheduled_time = parent.scheduled_time + minutes(default_delay)
    followup.followup_delay_minutes = default_delay

    # Validate timing constraints
    followup = validate_followup_timing(followup, parent)

    followup_items.append(followup)
    followup_count += 1
```

### 6.3 Follow-up Timing Validation

```
FUNCTION validate_followup_timing(followup, parent):

    # Acceptable delay range: 15-30 minutes
    MIN_DELAY = 15
    MAX_DELAY = 30

    # Ensure minimum delay
    IF followup.delay < MIN_DELAY:
        followup.scheduled_time = parent.scheduled_time + minutes(MIN_DELAY)
        followup.delay = MIN_DELAY

    # Ensure maximum delay
    IF followup.delay > MAX_DELAY:
        followup.scheduled_time = parent.scheduled_time + minutes(MAX_DELAY)
        followup.delay = MAX_DELAY

    # Late night cutoff (11:30 PM)
    CUTOFF = "23:30:00"
    IF followup.scheduled_time > CUTOFF:
        # Push to next day at 8:00 AM
        followup.scheduled_date = parent.scheduled_date + days(1)
        followup.scheduled_time = "08:00:00"
        followup.timing_adjusted = True

    # Check for conflicts with other scheduled items
    WHILE slot_occupied(followup.scheduled_time, followup.scheduled_date):
        followup.scheduled_time += minutes(5)

        IF followup.delay > MAX_DELAY:
            # Cannot schedule within valid window
            RETURN NULL

    RETURN followup
```

### 6.4 Select Follow-up Captions

```
FOR each followup in followup_items:

    # Get compatible follow-up captions
    captions = MCP CALL: get_send_type_captions(
        creator_id = creator.id,
        send_type_key = "ppv_followup",
        min_performance = 40,
        min_freshness = 30,
        limit = 5
    )

    # Select unused caption
    FOR each caption in captions:
        IF caption.id NOT IN used_captions:
            followup.caption = caption
            used_captions.add(caption.id)
            BREAK

    # Fallback if no caption available
    IF NOT followup.caption:
        followup.needs_caption = True
        followup.caption_warning = "No follow-up caption available"
```

### 6.5 Follow-up Item Structure

```
COMPLETE FOLLOWUP STRUCTURE:

{
    "slot_id": "2025-01-20_1_followup",
    "send_type_key": "ppv_followup",
    "category": "retention",
    "scheduled_date": "2025-01-20",
    "scheduled_time": "20:20:00",
    "channel_key": "targeted_message",
    "target_key": "ppv_non_purchasers",
    "is_follow_up": 1,
    "parent_item_id": "2025-01-20_1",
    "followup_delay_minutes": 20,
    "caption": {
        "id": 901,
        "text": "Last chance babe, this won't be here forever...",
        "performance_score": 78.5,
        "freshness_score": 85.0
    },
    "media_type": "none",
    "flyer_required": 0
}
```

### Phase 6 Output State

```json
{
  "parent_items": [...],  // Original PPV items
  "followup_items": [
    {
      "slot_id": "2025-01-20_1_followup",
      "parent_item_id": "2025-01-20_1",
      "send_type_key": "ppv_followup",
      "scheduled_time": "20:20:00",
      "target_key": "ppv_non_purchasers",
      "caption": {...}
    }
  ],
  "followup_summary": {
    "generated": 6,
    "skipped_limit": 0,
    "skipped_timing": 0
  }
}
```

---

## Phase 7: ASSEMBLY & VALIDATION

**Duration**: ~2 seconds
**Objective**: Combine all components, validate, and save to database
**Input**: All phase outputs

### 7.1 Merge Components

```
ASSEMBLY ALGORITHM:

all_items = []

FOR each day in schedule_week:
    # Get day's allocated items
    day_items = filter(timed_items, date=day)

    FOR each item in day_items:
        assembled_item = {
            # Timing
            scheduled_date: item.scheduled_date,
            scheduled_time: item.scheduled_time,
            expires_at: item.expires_at,

            # Send type configuration
            send_type_key: item.send_type_key,
            item_type: item.send_type_key,  # Legacy field

            # Channel and targeting
            channel_key: item.channel_key,
            channel: item.channel_key,  # Legacy field
            target_key: item.target_key,

            # Caption
            caption_id: item.caption.id,
            caption_text: item.caption.text,

            # Content
            content_type_id: item.content_type_id,
            media_type: determine_media_type(item),
            flyer_required: item.flyer_required or 0,

            # Pricing
            suggested_price: item.suggested_price,
            campaign_goal: item.campaign_goal,

            # Metadata
            priority: item.priority,
            is_follow_up: 0,
            parent_item_id: NULL
        }

        all_items.append(assembled_item)

    # Add follow-ups for this day
    day_followups = filter(followup_items, date=day)
    FOR each followup in day_followups:
        assembled_followup = {
            # ... similar structure with is_follow_up: 1
        }
        all_items.append(assembled_followup)

# Sort by date then time
all_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))
```

### 7.2 Quality Validation Checks

```
VALIDATION CHECKLIST:

validation_results = {
    passed: [],
    warnings: [],
    errors: []
}

# Check 1: Required fields present
FOR each item in all_items:
    required = ["scheduled_date", "scheduled_time", "send_type_key",
                "channel_key", "target_key"]
    FOR field in required:
        IF NOT item[field]:
            validation_results.errors.append({
                item: item.slot_id,
                error: f"Missing required field: {field}"
            })

# Check 2: Caption uniqueness
caption_counts = count_by(all_items, "caption_id")
FOR caption_id, count in caption_counts:
    IF count > 1:
        validation_results.warnings.append({
            caption_id: caption_id,
            warning: f"Caption used {count} times in schedule"
        })

# Check 3: Vault content availability
FOR each item in all_items:
    IF item.content_type_id AND item.content_type_id NOT IN vault.available:
        validation_results.errors.append({
            item: item.slot_id,
            error: "Required content type not in vault"
        })

# Check 4: Timing conflict detection
FOR each pair (item_a, item_b) in all_items:
    IF item_a.scheduled_date == item_b.scheduled_date:
        IF item_a.scheduled_time == item_b.scheduled_time:
            validation_results.errors.append({
                items: [item_a.slot_id, item_b.slot_id],
                error: "Timing conflict: same date and time"
            })

# Check 5: Daily volume limits
FOR each day in schedule_week:
    day_count = count(all_items, date=day)
    IF day_count > volume.max_per_day:
        validation_results.warnings.append({
            date: day,
            warning: f"Daily limit exceeded: {day_count} items"
        })

# Check 6: Persona consistency
persona = get_persona_profile(creator.id)
FOR each item in all_items:
    IF item.caption:
        IF NOT matches_persona(item.caption, persona):
            validation_results.warnings.append({
                item: item.slot_id,
                warning: "Caption may not match creator persona"
            })

# Check 7: Follow-up linkage
FOR each item in all_items:
    IF item.is_follow_up:
        parent = find(all_items, slot_id=item.parent_item_id)
        IF NOT parent:
            validation_results.errors.append({
                item: item.slot_id,
                error: "Follow-up has invalid parent reference"
            })

# Check 8: CAPTION WARNINGS FROM VOLUME CONFIG (CRITICAL - v2.2)
# These warnings were generated by the caption_constraint module during
# Phase 1 volume calculation and MUST be surfaced in the validation report
IF volume_config.caption_warnings:
    FOR warning in volume_config.caption_warnings:
        validation_results.warnings.append({
            type: "caption_pool_warning",
            source: "volume_config",
            warning: warning
        })

        # Check if critical shortage requires allocation adjustment
        IF "critical shortage" IN warning.lower() OR "exhausted" IN warning.lower():
            # Extract affected send type from warning
            affected_type = extract_type_from_warning(warning)

            validation_results.recommendations.append(
                f"CREATE NEW CAPTIONS: {affected_type} needs 5+ new captions"
            )

            # Flag for manual review
            validation_results.requires_caption_review = True

# Check 9: Low confidence warning
IF volume_config.confidence_score < 0.6:
    validation_results.warnings.append({
        type: "low_confidence",
        confidence_score: volume_config.confidence_score,
        message_count: volume_config.message_count,
        warning: f"Low confidence ({volume_config.confidence_score:.2f}) - volumes dampened toward conservative defaults"
    })
```

### 7.3 Generate Validation Report

```
VALIDATION REPORT STRUCTURE (v2.2):

{
    "status": "passed" | "passed_with_warnings" | "failed",
    "summary": {
        "total_items": 48,
        "errors": 0,
        "warnings": 4
    },
    "breakdown": {
        "by_category": {
            "revenue": 18,
            "engagement": 21,
            "retention": 9
        },
        "by_day": {
            "2025-01-20": 7,
            "2025-01-21": 6,
            ...
        }
    },
    "volume_metadata": {
        "confidence_score": 0.85,
        "adjustments_applied": ["base_tier_calculation", "multi_horizon_fusion", "dow_multipliers"],
        "elasticity_capped": false,
        "prediction_id": 123
    },
    "errors": [],
    "warnings": [
        { "type": "duplicate_caption", "caption_id": 789, "count": 2 },
        { "type": "low_freshness", "item": "2025-01-22_3", "score": 35 },
        { "type": "caption_pool_warning", "source": "volume_config", "warning": "Low captions for ppv_followup: <3 usable" },
        { "type": "low_confidence", "confidence_score": 0.55, "message_count": 22, "warning": "Low confidence (0.55) - volumes dampened" }
    ],
    "recommendations": [
        "CREATE NEW CAPTIONS: ppv_followup needs 5+ new captions",
        "Add video content to vault for increased revenue items"
    ],
    "requires_caption_review": true
}
```

**WARNING TYPES:**

| Type | Source | Severity | Action Required |
|------|--------|----------|-----------------|
| `duplicate_caption` | Phase 3 | Warning | Prefer unique captions |
| `low_freshness` | Phase 3 | Warning | Lower threshold or flag |
| `caption_pool_warning` | Phase 1 volume_config | Warning/Critical | Create new captions |
| `low_confidence` | Phase 1 volume_config | Info | Use conservative allocation |
| `vault_missing` | Phase 3 | Error | Skip items or create content |
| `timing_conflict` | Phase 5 | Error | Shift item times |

### 7.4 Save to Database

```
# Only proceed if validation passed or passed_with_warnings
IF validation_results.status == "failed":
    RETURN {
        success: False,
        error: "Validation failed",
        details: validation_results.errors
    }

# Prepare items for save
formatted_items = []
FOR each item in all_items:
    formatted_items.append({
        scheduled_date: item.scheduled_date,
        scheduled_time: item.scheduled_time,
        item_type: item.send_type_key,
        channel: item.channel_key,
        send_type_key: item.send_type_key,
        channel_key: item.channel_key,
        target_key: item.target_key,
        caption_id: item.caption_id,
        caption_text: item.caption_text,
        content_type_id: item.content_type_id,
        media_type: item.media_type,
        flyer_required: item.flyer_required,
        suggested_price: item.suggested_price,
        priority: item.priority,
        is_follow_up: item.is_follow_up,
        parent_item_id: item.parent_item_id,
        followup_delay_minutes: item.followup_delay_minutes,
        expires_at: item.expires_at
    })

# Execute save
result = MCP CALL: save_schedule(
    creator_id = creator.id,
    week_start = schedule_week.start_date,
    items = formatted_items
)

RETURN {
    success: True,
    template_id: result.template_id,
    items_created: result.item_count,
    validation_report: validation_results
}
```

### Phase 7 Output (Final Response)

```json
{
  "success": true,
  "template_id": 456,
  "creator_id": "alexia",
  "week_start": "2025-01-20",

  "summary": {
    "total_items": 48,
    "by_category": {
      "revenue": 18,
      "engagement": 21,
      "retention": 9
    },
    "by_day": {
      "2025-01-20": 7,
      "2025-01-21": 7,
      "2025-01-22": 6,
      "2025-01-23": 7,
      "2025-01-24": 7,
      "2025-01-25": 7,
      "2025-01-26": 7
    },
    "followups_generated": 6
  },

  "validation": {
    "status": "passed_with_warnings",
    "warnings": 2,
    "errors": 0
  },

  "items": [
    {
      "scheduled_date": "2025-01-20",
      "scheduled_time": "09:00:00",
      "send_type_key": "bump_normal",
      "channel_key": "mass_message",
      "target_key": "all_active",
      "caption_text": "Good morning sunshine..."
    },
    // ... all 48 items
  ]
}
```

---

## Error Handling

Comprehensive error handling and recovery strategy for the EROS schedule generation pipeline.

---

### Error Severity Levels

The pipeline classifies errors into 4 severity levels that determine propagation and recovery behavior:

| Severity | Definition | Action | Propagation |
|----------|------------|--------|-------------|
| **CRITICAL** | Pipeline cannot continue, complete failure | Halt immediately, return error | Abort entire generation |
| **HIGH** | Phase cannot complete, data integrity at risk | Attempt recovery once, then halt | Stop at phase boundary |
| **MEDIUM** | Degraded functionality, partial data loss | Apply fallback strategy, log warning | Continue with degradation |
| **LOW** | Minor issue, recoverable without impact | Auto-recover, log info | Continue normally |

#### Severity Examples

```
CRITICAL:
- Database connection failure
- Creator profile not found
- Volume config returns null
- MCP server unreachable

HIGH:
- Zero captions available for send type
- All vault content missing
- Invalid page_type configuration
- Weekly distribution malformed

MEDIUM:
- Caption freshness below threshold
- Vault missing specific content type
- Timing optimization fails for single item
- Audience target not found

LOW:
- Persona profile missing (use defaults)
- Best timing data incomplete
- Single caption unavailable
- Minor validation warning
```

---

### Error Propagation Rules

**Phase Boundary Enforcement**: Errors are evaluated at phase transitions. The pipeline decides whether to continue, degrade, or abort based on severity and recoverability.

#### Propagation Decision Matrix

```
AT PHASE BOUNDARY:

IF critical_errors > 0:
    ABORT pipeline
    RETURN error report with full context
    LOG with tracking_id for diagnostics

ELSE IF high_errors > 0:
    ATTEMPT recovery procedure (once)
    IF recovery_successful:
        LOG warning and continue
    ELSE:
        ABORT pipeline
        RETURN partial results + error

ELSE IF medium_errors > 0:
    APPLY degradation strategy
    SET degraded_mode = true
    LOG warnings to audit trail
    CONTINUE to next phase

ELSE IF low_errors > 0:
    LOG informational messages
    CONTINUE normally

ELSE:
    CONTINUE to next phase
```

#### When to Abort vs Continue with Degradation

**ABORT CONDITIONS (Non-recoverable):**
- Creator ID invalid or not found
- Database connection lost
- Volume config entirely missing
- Page type validation fails
- MCP server unavailable after retries
- Validation score < 50 (Phase 7)

**CONTINUE WITH DEGRADATION:**
- Caption pool depleted (use lower thresholds)
- Vault missing specific content types (skip those types)
- Timing optimization partially fails (use fallback times)
- Audience targets limited (default to all_active)
- Confidence score low (apply conservative volumes)

---

### Per-Phase Error Handling

Detailed error handling procedures for each of the 7 pipeline phases.

---

#### Phase 1: INITIALIZATION

**Timeout**: 10 seconds per MCP call
**Retry Policy**: 2 retries with exponential backoff (1s, 3s)

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Creator profile not found | CRITICAL | `get_creator_profile` returns null | Retry once, check creator_id validity | Abort |
| Volume config missing | CRITICAL | `get_volume_config` returns null | Check database for creator entry | Abort |
| Performance trends unavailable | MEDIUM | `get_performance_trends` returns empty | Use defaults: sat=50, opp=50 | Continue with defaults |
| Send types empty | HIGH | `get_send_types` returns [] | Verify page_type, check catalog | Abort |
| Vault data missing | MEDIUM | `get_vault_availability` returns empty | Assume all content available | Flag warning, continue |
| Best timing missing | LOW | `get_best_timing` returns empty | Use generic peak hours [19,20,21,22] | Continue with defaults |

##### Recovery Procedures

```python
# Phase 1 Recovery Pattern
def recover_phase1_initialization(error_type, context):
    """
    Recovery procedure for Phase 1 initialization errors.
    """
    if error_type == "creator_not_found":
        # CRITICAL - cannot recover
        return {
            "recoverable": False,
            "action": "abort",
            "error_code": "CREATOR_NOT_FOUND",
            "message": f"Creator ID '{context.creator_id}' not found in database"
        }

    elif error_type == "volume_config_missing":
        # CRITICAL - cannot recover
        return {
            "recoverable": False,
            "action": "abort",
            "error_code": "VOLUME_CONFIG_MISSING",
            "message": "Volume configuration not available for creator"
        }

    elif error_type == "performance_trends_unavailable":
        # MEDIUM - use defaults
        return {
            "recoverable": True,
            "action": "use_defaults",
            "fallback_data": {
                "saturation_score": 50,
                "opportunity_score": 50,
                "revenue_trend": "stable",
                "confidence_score": 0.5
            },
            "warning": "Performance trends unavailable - using neutral defaults"
        }

    elif error_type == "vault_data_missing":
        # MEDIUM - assume all content available
        return {
            "recoverable": True,
            "action": "assume_available",
            "fallback_data": {
                "vault_check_disabled": True,
                "assumed_content_types": ["video", "picture", "gif"]
            },
            "warning": "Vault data missing - assuming content availability"
        }

    elif error_type == "best_timing_missing":
        # LOW - use generic peak hours
        return {
            "recoverable": True,
            "action": "use_generic_timing",
            "fallback_data": {
                "peak_hours": [19, 20, 21, 22],
                "avoid_hours": [3, 4, 5, 6],
                "best_days": ["friday", "saturday", "sunday"]
            },
            "info": "Best timing data missing - using generic peak hours"
        }

    return {"recoverable": False, "action": "abort", "error_code": "UNKNOWN_ERROR"}
```

---

#### Phase 2: SEND TYPE ALLOCATION

**Timeout**: 5 seconds
**Retry Policy**: None (deterministic algorithm)

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Daily quota calculation fails | HIGH | Division by zero, negative values | Recalculate with tier minimums | Use base tier volumes |
| Weekly distribution malformed | HIGH | Missing days, invalid keys | Validate structure, rebuild uniform | Use equal distribution |
| Confidence score invalid | MEDIUM | Out of 0-1 range, null | Clamp to valid range or default 0.7 | Use 0.7 default |
| Strategy selection fails | MEDIUM | No eligible strategies | Use "balanced_standard" | Always allow balanced |
| Type diversity check fails | HIGH | < 10 unique types allocated | Restart Phase 2 with diversity enforcement | Force variety mode |
| Weekly limits exceeded | MEDIUM | VIP/Snapchat > weekly cap | Remove excess by priority | Truncate to limits |

##### Recovery Procedures

```python
def recover_phase2_allocation(error_type, context):
    """
    Recovery procedure for Phase 2 allocation errors.
    """
    if error_type == "quota_calculation_failed":
        # HIGH - use tier minimum volumes
        return {
            "recoverable": True,
            "action": "use_tier_minimums",
            "fallback_data": {
                "revenue_per_day": context.tier_config.min_revenue,
                "engagement_per_day": context.tier_config.min_engagement,
                "retention_per_day": context.tier_config.min_retention
            },
            "warning": "Quota calculation failed - using tier minimums"
        }

    elif error_type == "weekly_distribution_malformed":
        # HIGH - rebuild uniform distribution
        return {
            "recoverable": True,
            "action": "rebuild_uniform",
            "fallback_data": {
                "weekly_distribution": {0:13, 1:13, 2:13, 3:13, 4:13, 5:13, 6:13},
                "dow_multipliers_used": {0:1.0, 1:1.0, 2:1.0, 3:1.0, 4:1.0, 5:1.0, 6:1.0}
            },
            "warning": "Weekly distribution malformed - using uniform distribution"
        }

    elif error_type == "diversity_check_failed":
        # HIGH - restart phase with diversity mode
        return {
            "recoverable": True,
            "action": "restart_with_diversity",
            "strategy": "variety_max",
            "enforce_minimums": {
                "unique_types_total": 10,
                "unique_revenue_types": 5,
                "unique_engagement_types": 5
            },
            "warning": "Type diversity insufficient - restarting Phase 2 with variety enforcement"
        }

    elif error_type == "weekly_limits_exceeded":
        # MEDIUM - truncate excess
        return {
            "recoverable": True,
            "action": "truncate_excess",
            "limits": {
                "vip_program": 1,
                "snapchat_bundle": 1
            },
            "warning": "Weekly limits exceeded - removing lowest priority instances"
        }

    return {"recoverable": False, "action": "abort", "error_code": "UNKNOWN_ALLOCATION_ERROR"}
```

---

#### Phase 3: CONTENT MATCHING

**Timeout**: 15 seconds (caption queries can be slow)
**Retry Policy**: 3 retries with freshness threshold degradation

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Zero captions for send type | HIGH | Query returns empty | Lower threshold → 20 → 0 | Flag for manual creation |
| Caption freshness too low | MEDIUM | All captions < 30 days | Accept lower freshness | Use performance priority |
| Caption performance poor | MEDIUM | All captions < 40 score | Accept lower performance | Use freshness priority |
| Duplicate caption assigned | MEDIUM | Caption already in schedule | Re-query with exclusions | Continue with duplicate |
| Vault content type mismatch | MEDIUM | Content type not in vault | Skip content_type_id | Proceed without content |
| Persona profile missing | LOW | Get persona returns null | Use default persona | Continue with defaults |

##### Recovery Procedures

```python
def recover_phase3_content(error_type, context):
    """
    Recovery procedure for Phase 3 content matching errors.
    """
    if error_type == "zero_captions_available":
        # HIGH - apply degradation chain
        degradation_chain = [
            {"threshold": 30, "min_performance": 40},
            {"threshold": 20, "min_performance": 30},
            {"threshold": 10, "min_performance": 20},
            {"threshold": 0, "min_performance": 0}
        ]

        for attempt, params in enumerate(degradation_chain):
            captions = query_captions(
                context.send_type,
                freshness_threshold=params["threshold"],
                performance_threshold=params["min_performance"]
            )

            if len(captions) > 0:
                return {
                    "recoverable": True,
                    "action": "use_lower_threshold",
                    "captions_found": captions,
                    "threshold_used": params["threshold"],
                    "warning": f"Caption shortage - using threshold {params['threshold']}"
                }

        # All attempts exhausted
        return {
            "recoverable": True,
            "action": "flag_manual",
            "fallback": "MANUAL_CAPTION_NEEDED",
            "error": f"No captions available for {context.send_type} - requires manual creation"
        }

    elif error_type == "caption_freshness_low":
        # MEDIUM - prioritize performance over freshness
        return {
            "recoverable": True,
            "action": "prioritize_performance",
            "scoring_weights": {
                "freshness": 0.20,  # Reduced from 0.40
                "performance": 0.50,  # Increased from 0.35
                "type_priority": 0.15,
                "diversity": 0.10,
                "persona": 0.05
            },
            "warning": "Caption freshness low - prioritizing performance"
        }

    elif error_type == "duplicate_caption_detected":
        # MEDIUM - re-query with exclusions
        return {
            "recoverable": True,
            "action": "requery_with_exclusions",
            "exclude_caption_ids": context.used_caption_ids,
            "warning": "Duplicate caption detected - re-querying"
        }

    elif error_type == "vault_content_mismatch":
        # MEDIUM - skip content_type_id
        return {
            "recoverable": True,
            "action": "skip_content_type",
            "warning": f"Content type '{context.content_type}' not in vault - proceeding without"
        }

    return {"recoverable": False, "action": "abort", "error_code": "UNKNOWN_CONTENT_ERROR"}
```

---

#### Phase 4: AUDIENCE TARGETING

**Timeout**: 5 seconds
**Retry Policy**: None (simple mapping)

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Audience target not found | MEDIUM | Target key not in catalog | Default to "all_active" | Always available |
| Channel incompatible | MEDIUM | Channel doesn't support target | Switch to compatible channel | Use mass_message |
| Page type mismatch | HIGH | Paid-only target on free page | Filter incompatible targets | Use free-compatible only |
| Required target missing | HIGH | Followup/renewal target absent | Skip item or use closest match | Flag as warning |

##### Recovery Procedures

```python
def recover_phase4_targeting(error_type, context):
    """
    Recovery procedure for Phase 4 audience targeting errors.
    """
    if error_type == "target_not_found":
        # MEDIUM - default to all_active
        return {
            "recoverable": True,
            "action": "use_default_target",
            "fallback_target": "all_active",
            "fallback_channel": "mass_message",
            "warning": f"Target '{context.target_key}' not found - using all_active"
        }

    elif error_type == "channel_incompatible":
        # MEDIUM - switch to compatible channel
        compatible_channels = get_compatible_channels(context.target_key)
        if len(compatible_channels) > 0:
            return {
                "recoverable": True,
                "action": "switch_channel",
                "new_channel": compatible_channels[0],
                "warning": f"Channel incompatible - switching to {compatible_channels[0]}"
            }
        else:
            return {
                "recoverable": True,
                "action": "use_all_active",
                "fallback_target": "all_active",
                "fallback_channel": "mass_message",
                "warning": "No compatible channels - using all_active"
            }

    elif error_type == "page_type_mismatch":
        # HIGH - filter incompatible targets
        return {
            "recoverable": True,
            "action": "filter_targets",
            "allowed_page_types": [context.page_type, "both"],
            "warning": f"Filtered targets incompatible with page_type '{context.page_type}'"
        }

    return {"recoverable": True, "action": "use_all_active", "fallback_target": "all_active"}
```

---

#### Phase 5: TIMING OPTIMIZATION

**Timeout**: 10 seconds
**Retry Policy**: 2 retries with relaxed spacing constraints

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| No available time slots | HIGH | All hours blocked | Relax constraints incrementally | Extend to next day |
| Timing conflict detected | MEDIUM | Two items at same time | Shift later item by 5 min | Auto-resolve |
| Avoid hours violation | MEDIUM | Item in 03:00-07:00 | Move to nearest valid hour | 08:00 or 23:00 |
| Minimum spacing violated | MEDIUM | Items < 45 min apart | Shift conflicting items | Cascade shifts |
| Prime hour overused | LOW | Same time > 2x weekly | Apply jitter | Continue with warning |
| Time calculation fails | HIGH | Invalid datetime | Recalculate with safe defaults | Use 12:00 noon |

##### Recovery Procedures

```python
def recover_phase5_timing(error_type, context):
    """
    Recovery procedure for Phase 5 timing optimization errors.
    """
    if error_type == "no_available_slots":
        # HIGH - relax constraints
        constraint_relaxation = [
            {"min_spacing": 45, "avoid_hours": [3,4,5,6]},
            {"min_spacing": 30, "avoid_hours": [3,4,5,6]},
            {"min_spacing": 20, "avoid_hours": [3,4,5]},
            {"min_spacing": 15, "avoid_hours": []},
        ]

        for attempt, constraints in enumerate(constraint_relaxation):
            slots = find_available_slots(context.day, constraints)
            if len(slots) > 0:
                return {
                    "recoverable": True,
                    "action": "relaxed_constraints",
                    "constraints_used": constraints,
                    "warning": f"Relaxed timing constraints (attempt {attempt+1})"
                }

        # All attempts failed - extend to next day
        return {
            "recoverable": True,
            "action": "extend_to_next_day",
            "new_day": context.day + 1,
            "warning": "No slots available - moving items to next day"
        }

    elif error_type == "timing_conflict_detected":
        # MEDIUM - shift later item
        return {
            "recoverable": True,
            "action": "shift_item",
            "shift_amount_minutes": 5,
            "cascade": True,
            "warning": "Timing conflict - shifting item by 5 minutes"
        }

    elif error_type == "avoid_hours_violation":
        # MEDIUM - move to nearest valid hour
        if context.scheduled_hour < 7:
            new_hour = 8
        else:
            new_hour = 23

        return {
            "recoverable": True,
            "action": "move_to_valid_hour",
            "new_hour": new_hour,
            "warning": f"Avoid hours violation - moving to {new_hour}:00"
        }

    elif error_type == "minimum_spacing_violated":
        # MEDIUM - cascade shifts
        return {
            "recoverable": True,
            "action": "cascade_shifts",
            "min_spacing_minutes": 45,
            "warning": "Minimum spacing violated - applying cascade shifts"
        }

    return {"recoverable": True, "action": "use_default_time", "default_hour": 12}
```

---

#### Phase 6: FOLLOW-UP GENERATION

**Timeout**: 5 seconds
**Retry Policy**: None (followup generation is optional)

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Daily followup limit hit | LOW | > 4 followups per day | Skip lowest priority parent | Continue |
| No followup caption | MEDIUM | Query returns empty | Flag for manual | Continue without caption |
| Late night followup | LOW | Parent > 23:30 | Move followup to next day 08:00 | Auto-adjust |
| Parent item invalid | HIGH | Parent ID not in schedule | Skip followup generation | Log error |
| Delay calculation fails | MEDIUM | Invalid time arithmetic | Use default 20 min delay | Continue |

##### Recovery Procedures

```python
def recover_phase6_followup(error_type, context):
    """
    Recovery procedure for Phase 6 followup generation errors.
    """
    if error_type == "daily_limit_exceeded":
        # LOW - skip lowest priority
        return {
            "recoverable": True,
            "action": "skip_lowest_priority",
            "skipped_parent_id": context.lowest_priority_parent,
            "info": f"Daily followup limit (4) exceeded - skipping parent {context.lowest_priority_parent}"
        }

    elif error_type == "no_followup_caption":
        # MEDIUM - flag for manual
        return {
            "recoverable": True,
            "action": "flag_manual",
            "followup_caption_needed": True,
            "warning": "No followup caption available - flagging for manual creation"
        }

    elif error_type == "late_night_followup":
        # LOW - move to next morning
        return {
            "recoverable": True,
            "action": "move_to_morning",
            "new_day": context.day + 1,
            "new_hour": 8,
            "info": "Late night followup - moving to next morning 08:00"
        }

    elif error_type == "parent_invalid":
        # HIGH - skip followup
        return {
            "recoverable": True,
            "action": "skip_followup",
            "error": f"Parent item {context.parent_id} not found - skipping followup"
        }

    return {"recoverable": True, "action": "skip_followup", "info": "Followup generation optional"}
```

---

#### Phase 7: ASSEMBLY & VALIDATION

**Timeout**: 10 seconds
**Retry Policy**: None (validation is final checkpoint)

##### Common Failure Modes

| Failure Mode | Severity | Detection | Recovery Procedure | Fallback |
|--------------|----------|-----------|-------------------|----------|
| Validation score < 50 | CRITICAL | Quality validator fails | Abort with detailed report | Cannot continue |
| Validation score 50-69 | HIGH | Below acceptable threshold | Return with NEEDS_REVIEW | Manual review required |
| Category balance off | MEDIUM | Rev < 30% or Ret > 20% | Adjust allocations | Flag warning |
| Missing required fields | HIGH | Null scheduled_time, etc. | Fill with defaults or abort | Context-dependent |
| Orphaned followups | MEDIUM | Parent references broken | Remove orphans | Continue |
| Database save failure | CRITICAL | save_schedule() throws error | Retry once, then abort | Return full error |

##### Recovery Procedures

```python
def recover_phase7_assembly(error_type, context):
    """
    Recovery procedure for Phase 7 assembly & validation errors.
    """
    if error_type == "validation_score_critical":
        # CRITICAL - abort
        return {
            "recoverable": False,
            "action": "abort",
            "error_code": "VALIDATION_FAILED_CRITICAL",
            "validation_score": context.score,
            "errors": context.validation_errors,
            "message": f"Validation score {context.score} < 50 - cannot proceed"
        }

    elif error_type == "validation_score_low":
        # HIGH - needs review
        return {
            "recoverable": True,
            "action": "return_needs_review",
            "status": "NEEDS_REVIEW",
            "validation_score": context.score,
            "warnings": context.validation_warnings,
            "message": f"Validation score {context.score} (50-69) - manual review required"
        }

    elif error_type == "category_balance_off":
        # MEDIUM - flag warning
        return {
            "recoverable": True,
            "action": "flag_warning",
            "warning": f"Category balance: Rev {context.rev_pct}%, Eng {context.eng_pct}%, Ret {context.ret_pct}%",
            "recommendation": "Consider rebalancing in Phase 2"
        }

    elif error_type == "missing_required_fields":
        # HIGH - attempt to fill or abort
        if can_fill_defaults(context.missing_fields):
            return {
                "recoverable": True,
                "action": "fill_defaults",
                "fields_filled": context.missing_fields,
                "warning": "Filled missing fields with defaults"
            }
        else:
            return {
                "recoverable": False,
                "action": "abort",
                "error_code": "MISSING_REQUIRED_FIELDS",
                "fields": context.missing_fields
            }

    elif error_type == "orphaned_followups":
        # MEDIUM - remove orphans
        return {
            "recoverable": True,
            "action": "remove_orphans",
            "orphan_count": len(context.orphan_ids),
            "warning": f"Removed {len(context.orphan_ids)} orphaned followups"
        }

    elif error_type == "database_save_failed":
        # CRITICAL - retry once
        if context.retry_count < 1:
            return {
                "recoverable": True,
                "action": "retry_save",
                "retry_count": context.retry_count + 1,
                "warning": "Database save failed - retrying"
            }
        else:
            return {
                "recoverable": False,
                "action": "abort",
                "error_code": "DATABASE_SAVE_FAILED",
                "error": context.db_error,
                "message": "Database save failed after retry"
            }

    return {"recoverable": False, "action": "abort", "error_code": "UNKNOWN_ASSEMBLY_ERROR"}
```

---

### Phase Recovery Matrix

Comprehensive recovery actions for all phases and failure modes.

| Phase | Failure Mode | Severity | Recovery Action | Fallback Strategy | Time to Recovery |
|-------|--------------|----------|-----------------|-------------------|------------------|
| **Phase 1** | Creator not found | CRITICAL | Abort | None | Immediate |
| | Volume config missing | CRITICAL | Abort | None | Immediate |
| | Performance trends unavailable | MEDIUM | Use defaults (sat=50, opp=50) | Neutral scores | < 1s |
| | Vault data missing | MEDIUM | Assume all content available | Disable vault checks | < 1s |
| | Best timing missing | LOW | Use generic peak hours [19-22] | Standard pattern | < 1s |
| **Phase 2** | Quota calculation fails | HIGH | Use tier minimums | Base tier config | 1-2s |
| | Weekly distribution malformed | HIGH | Rebuild uniform distribution | Equal across days | 1-2s |
| | Diversity check fails | HIGH | Restart Phase 2 with variety mode | Force 10+ types | 3-5s |
| | Weekly limits exceeded | MEDIUM | Truncate by priority | Remove excess | < 1s |
| | Confidence score invalid | MEDIUM | Clamp to 0.7 or valid range | Default confidence | < 1s |
| **Phase 3** | Zero captions available | HIGH | Lower threshold → 20 → 0 | Flag manual | 3-5s |
| | Caption freshness low | MEDIUM | Prioritize performance scoring | Adjust weights | < 1s |
| | Duplicate caption detected | MEDIUM | Re-query with exclusions | Allow if necessary | 1-2s |
| | Vault content mismatch | MEDIUM | Skip content_type_id | Proceed without | < 1s |
| | Persona missing | LOW | Use default persona | Standard tone | < 1s |
| **Phase 4** | Target not found | MEDIUM | Default to all_active | Universal target | < 1s |
| | Channel incompatible | MEDIUM | Switch to compatible channel | mass_message | < 1s |
| | Page type mismatch | HIGH | Filter incompatible targets | Page-compatible only | < 1s |
| | Required target missing | HIGH | Use closest match or skip | Log warning | 1-2s |
| **Phase 5** | No available slots | HIGH | Relax constraints incrementally | Extend to next day | 2-4s |
| | Timing conflict | MEDIUM | Shift by 5 min increments | Cascade shifts | 1-2s |
| | Avoid hours violation | MEDIUM | Move to 08:00 or 23:00 | Nearest valid | < 1s |
| | Min spacing violated | MEDIUM | Cascade shifts | Adjust times | 1-2s |
| | Time calculation fails | HIGH | Use default 12:00 | Noon fallback | < 1s |
| **Phase 6** | Daily limit exceeded | LOW | Skip lowest priority | Selective omission | < 1s |
| | No followup caption | MEDIUM | Flag for manual | Continue without | < 1s |
| | Late night followup | LOW | Move to next morning 08:00 | Auto-adjust | < 1s |
| | Parent invalid | HIGH | Skip followup | Log error | < 1s |
| **Phase 7** | Validation score < 50 | CRITICAL | Abort with report | None | Immediate |
| | Validation score 50-69 | HIGH | Return NEEDS_REVIEW | Manual review | Immediate |
| | Category balance off | MEDIUM | Flag warning | Continue | < 1s |
| | Missing required fields | HIGH | Fill defaults or abort | Context-dependent | 1-2s |
| | Orphaned followups | MEDIUM | Remove orphans | Clean up | < 1s |
| | Database save fails | CRITICAL | Retry once, then abort | None | 2-5s |

---

### Graceful Degradation Rules

Detailed degradation strategies for when primary paths fail.

#### Caption Availability Degradation

```
CAPTION SHORTAGE DEGRADATION CHAIN:

1. PRIMARY (freshness >= 40, performance >= 60):
   - Query captions with ideal thresholds
   - Sort by composite score
   - Return top matches

2. FALLBACK LEVEL 1 (freshness >= 30, performance >= 40):
   - Lower freshness to 30 days
   - Accept performance down to 40
   - Log warning: "Using lower caption thresholds"

3. FALLBACK LEVEL 2 (freshness >= 20, performance >= 30):
   - Accept older captions (20 days)
   - Performance down to 30
   - Log warning: "Caption pool depleted - using marginal captions"

4. FALLBACK LEVEL 3 (freshness >= 10, performance >= 20):
   - Nearly any caption acceptable
   - Log warning: "Critical caption shortage"

5. FALLBACK LEVEL 4 (freshness >= 0, performance >= 0):
   - Accept any caption regardless of age/performance
   - Log error: "Using any available caption - quality not guaranteed"

6. FINAL FALLBACK (no captions at all):
   - Flag item for manual caption creation
   - Set caption_text = "MANUAL_REQUIRED"
   - Set caption_id = null
   - Continue generation
   - Log critical: "No captions available - manual creation required"
```

#### Volume Configuration Degradation

```
VOLUME CONFIG DEGRADATION CHAIN:

1. PRIMARY (OptimizedVolumeResult available):
   - Use full 14-field optimized result
   - Apply weekly_distribution
   - Honor confidence_score and adjustments

2. FALLBACK LEVEL 1 (Optimization fails, use base tier):
   - Calculate from tier mapping only
   - Use uniform DOW distribution
   - Set confidence_score = 0.6
   - Log warning: "Optimization unavailable - using base tier"

3. FALLBACK LEVEL 2 (Tier unknown, estimate from fan_count):
   - Map fan_count → tier using standard thresholds
   - Apply conservative volumes
   - Set confidence_score = 0.5
   - Log warning: "Estimating tier from fan count"

4. FALLBACK LEVEL 3 (No data, use ultra-conservative):
   - revenue_per_day = 3
   - engagement_per_day = 3
   - retention_per_day = 1 (0 for free)
   - Set confidence_score = 0.3
   - Log error: "No volume data - using minimum safe values"

5. FINAL FALLBACK (Cannot determine tier):
   - Abort generation
   - Return error: "Unable to determine volume configuration"
```

#### Timing Optimization Degradation

```
TIMING DEGRADATION CHAIN:

1. PRIMARY (Historical timing data available):
   - Use creator's peak_hours from analytics
   - Apply hourly_performance weights
   - Respect avoid_hours strictly

2. FALLBACK LEVEL 1 (No historical data, use generic):
   - peak_hours = [19, 20, 21, 22]
   - avoid_hours = [3, 4, 5, 6]
   - Use standard distribution
   - Log info: "Using generic timing patterns"

3. FALLBACK LEVEL 2 (Slots exhausted, relax spacing):
   - Reduce min_spacing from 45 min → 30 min
   - Allow more items in prime hours
   - Log warning: "Relaxed spacing constraints"

4. FALLBACK LEVEL 3 (Still exhausted, use avoid hours):
   - Allow scheduling in avoid_hours (morning)
   - Maintain 20 min minimum spacing
   - Log warning: "Using non-optimal hours due to constraint"

5. FALLBACK LEVEL 4 (Day full, extend to next day):
   - Move lowest-priority items to next day
   - Recalculate timing
   - Log warning: "Extended schedule to next day"

6. FINAL FALLBACK (Cannot fit all items):
   - Reduce volume by removing lowest-priority items
   - Log error: "Reduced schedule volume - unable to fit all items"
```

#### Audience Targeting Degradation

```
TARGETING DEGRADATION CHAIN:

1. PRIMARY (Optimal target available):
   - Use send_type's recommended target
   - Match channel capabilities
   - Apply page_type filters

2. FALLBACK LEVEL 1 (Recommended unavailable, use category default):
   - Revenue → all_active
   - Engagement → all_active
   - Retention → renew_off / ppv_non_purchasers
   - Log info: "Using category default target"

3. FALLBACK LEVEL 2 (Category default incompatible):
   - Force all_active for all types
   - Use mass_message channel
   - Log warning: "Using universal all_active target"

4. FINAL FALLBACK (Channel incompatible):
   - Skip item entirely
   - Log error: "No compatible target/channel - item skipped"
```

---

### Circuit Breaker Pattern for MCP Calls

Protect against cascading failures and MCP server unavailability.

#### Circuit Breaker States

```
CIRCUIT STATES:

1. CLOSED (Normal operation):
   - All MCP calls proceed normally
   - Track failure rate
   - Transition to OPEN if failure_rate > 50% over 10 calls

2. OPEN (Failing, blocking calls):
   - Block all MCP calls immediately
   - Return error: "Circuit breaker OPEN - MCP server unavailable"
   - After 30 seconds, transition to HALF_OPEN

3. HALF_OPEN (Testing recovery):
   - Allow single test call
   - If successful → CLOSED (resume normal)
   - If failed → OPEN (block for another 30s)
```

#### Implementation

```python
class CircuitBreaker:
    """
    Circuit breaker for MCP tool calls.
    """
    def __init__(self, failure_threshold=0.5, timeout_seconds=30):
        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.window_size = 10

    def call(self, mcp_function, *args, **kwargs):
        """
        Execute MCP call with circuit breaker protection.
        """
        if self.state == "OPEN":
            # Check if timeout elapsed
            if time.time() - self.last_failure_time > self.timeout_seconds:
                self.state = "HALF_OPEN"
                log.info("Circuit breaker HALF_OPEN - testing recovery")
            else:
                raise CircuitBreakerOpen("MCP server unavailable - circuit breaker OPEN")

        try:
            result = mcp_function(*args, **kwargs)
            self.record_success()
            return result

        except Exception as e:
            self.record_failure()
            raise

    def record_success(self):
        """Record successful call."""
        self.success_count += 1

        if self.state == "HALF_OPEN":
            # Successful test call - close circuit
            self.state = "CLOSED"
            self.failure_count = 0
            log.info("Circuit breaker CLOSED - MCP server recovered")

        # Reset if window full
        if self.success_count + self.failure_count > self.window_size:
            self.success_count = 0
            self.failure_count = 0

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Check if threshold exceeded
        total_calls = self.success_count + self.failure_count
        if total_calls >= self.window_size:
            failure_rate = self.failure_count / total_calls

            if failure_rate > self.failure_threshold:
                self.state = "OPEN"
                log.error(f"Circuit breaker OPEN - failure rate {failure_rate:.0%}")

        if self.state == "HALF_OPEN":
            # Test call failed - reopen circuit
            self.state = "OPEN"
            log.error("Circuit breaker OPEN - test call failed")
```

#### Usage in Pipeline

```python
# Initialize circuit breaker for MCP calls
mcp_breaker = CircuitBreaker(failure_threshold=0.5, timeout_seconds=30)

# Phase 1: Wrap MCP calls
try:
    creator_profile = mcp_breaker.call(
        get_creator_profile,
        creator_id=creator_id
    )
except CircuitBreakerOpen:
    # MCP server unavailable
    return {
        "success": False,
        "error_code": "MCP_UNAVAILABLE",
        "message": "MCP server unavailable - circuit breaker protection activated",
        "retry_after": 30
    }
```

#### Retry Strategy with Exponential Backoff

```python
def retry_with_backoff(mcp_function, max_retries=3, base_delay=1.0):
    """
    Retry MCP call with exponential backoff.

    Args:
        mcp_function: MCP tool function to call
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)

    Returns:
        Result from successful call

    Raises:
        Exception after all retries exhausted
    """
    for attempt in range(max_retries):
        try:
            result = mcp_function()
            return result

        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed
                log.error(f"MCP call failed after {max_retries} attempts: {e}")
                raise

            # Calculate backoff delay: 1s, 3s, 9s
            delay = base_delay * (3 ** attempt)
            log.warning(f"MCP call failed (attempt {attempt + 1}/{max_retries}) - retrying in {delay}s")
            time.sleep(delay)
```

#### Timeout Configuration

```python
MCP_TIMEOUT_CONFIG = {
    "get_creator_profile": 10,          # 10 seconds
    "get_volume_config": 10,            # 10 seconds
    "get_performance_trends": 15,       # 15 seconds (may be slow)
    "get_send_types": 5,                # 5 seconds
    "get_vault_availability": 5,        # 5 seconds
    "get_best_timing": 5,               # 5 seconds
    "get_top_captions": 15,             # 15 seconds (largest query)
    "get_send_type_captions": 15,       # 15 seconds
    "get_audience_targets": 5,          # 5 seconds
    "get_channels": 5,                  # 5 seconds
    "save_schedule": 20,                # 20 seconds (transaction)
    "execute_query": 30                 # 30 seconds (custom queries)
}

def call_mcp_with_timeout(tool_name, mcp_function, *args, **kwargs):
    """
    Call MCP tool with configured timeout.
    """
    timeout = MCP_TIMEOUT_CONFIG.get(tool_name, 10)

    try:
        result = timeout_wrapper(mcp_function, timeout, *args, **kwargs)
        return result
    except TimeoutError:
        log.error(f"MCP call '{tool_name}' timed out after {timeout}s")
        raise MCPTimeoutError(f"{tool_name} exceeded timeout of {timeout}s")
```

---

### Logging and Observability

Comprehensive logging strategy for error tracking, debugging, and audit trails.

#### Log Levels and Usage

| Level | Usage | Examples |
|-------|-------|----------|
| **CRITICAL** | System failure, cannot continue | MCP server down, database unavailable, creator not found |
| **ERROR** | Operation failed, data quality impacted | Caption query failed, validation score < 50, save failed |
| **WARNING** | Degraded mode, fallback used | Low caption freshness, missing timing data, confidence < 0.6 |
| **INFO** | Normal operations, checkpoints | Phase completed, MCP call successful, validation passed |
| **DEBUG** | Detailed execution trace | Algorithm steps, scoring calculations, intermediate values |

#### Structured Logging Format

```python
import logging
import json
from datetime import datetime

class ScheduleGenerationLogger:
    """
    Structured logger for schedule generation pipeline.
    """
    def __init__(self, creator_id, generation_id):
        self.creator_id = creator_id
        self.generation_id = generation_id
        self.logger = logging.getLogger(f"schedule_gen.{creator_id}")

    def log_event(self, level, phase, event_type, message, **kwargs):
        """
        Log structured event with full context.
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "generation_id": self.generation_id,
            "creator_id": self.creator_id,
            "phase": phase,
            "event_type": event_type,
            "message": message,
            **kwargs
        }

        self.logger.log(level, json.dumps(log_entry))

    def log_phase_start(self, phase_number, phase_name):
        """Log phase start."""
        self.log_event(
            logging.INFO,
            f"phase_{phase_number}",
            "phase_start",
            f"Starting {phase_name}",
            phase_number=phase_number,
            phase_name=phase_name
        )

    def log_phase_complete(self, phase_number, phase_name, duration_ms, metrics=None):
        """Log phase completion."""
        self.log_event(
            logging.INFO,
            f"phase_{phase_number}",
            "phase_complete",
            f"Completed {phase_name}",
            phase_number=phase_number,
            phase_name=phase_name,
            duration_ms=duration_ms,
            metrics=metrics or {}
        )

    def log_error(self, phase, error_type, error_message, recovery_action=None, **kwargs):
        """Log error with recovery information."""
        self.log_event(
            logging.ERROR,
            phase,
            "error",
            error_message,
            error_type=error_type,
            recovery_action=recovery_action,
            **kwargs
        )

    def log_recovery(self, phase, error_type, recovery_action, success, **kwargs):
        """Log recovery attempt."""
        level = logging.INFO if success else logging.WARNING
        self.log_event(
            level,
            phase,
            "recovery",
            f"Recovery {'successful' if success else 'failed'}: {recovery_action}",
            error_type=error_type,
            recovery_action=recovery_action,
            recovery_success=success,
            **kwargs
        )

    def log_degradation(self, phase, degradation_type, fallback_used, **kwargs):
        """Log graceful degradation."""
        self.log_event(
            logging.WARNING,
            phase,
            "degradation",
            f"Graceful degradation: {degradation_type}",
            degradation_type=degradation_type,
            fallback_used=fallback_used,
            **kwargs
        )

    def log_mcp_call(self, tool_name, success, duration_ms, error=None):
        """Log MCP tool call."""
        level = logging.INFO if success else logging.ERROR
        self.log_event(
            level,
            "mcp",
            "tool_call",
            f"MCP call: {tool_name}",
            tool_name=tool_name,
            success=success,
            duration_ms=duration_ms,
            error=str(error) if error else None
        )

    def log_validation(self, validation_score, passed, errors=None, warnings=None):
        """Log validation results."""
        level = logging.INFO if passed else logging.ERROR
        self.log_event(
            level,
            "phase_7",
            "validation",
            f"Validation {'passed' if passed else 'failed'}: score {validation_score}",
            validation_score=validation_score,
            passed=passed,
            errors=errors or [],
            warnings=warnings or []
        )
```

#### Error Tracking IDs

```python
import uuid

def generate_tracking_id():
    """
    Generate unique tracking ID for error correlation.
    """
    return str(uuid.uuid4())

# Usage in pipeline
generation_id = generate_tracking_id()
logger = ScheduleGenerationLogger(creator_id="alexia", generation_id=generation_id)

# All logs for this generation will include the same generation_id
# Enables correlation across distributed systems
```

#### Audit Trail Requirements

```
AUDIT TRAIL MUST INCLUDE:

1. Generation Metadata:
   - generation_id (UUID)
   - creator_id
   - start_time (ISO 8601)
   - end_time (ISO 8601)
   - total_duration_ms
   - pipeline_version

2. Phase Execution:
   - phase_number (1-7)
   - phase_name
   - phase_start_time
   - phase_end_time
   - phase_duration_ms
   - phase_status (success/degraded/failed)

3. MCP Tool Calls:
   - tool_name
   - call_timestamp
   - duration_ms
   - success (boolean)
   - error_message (if failed)
   - retry_count

4. Errors and Recoveries:
   - error_type
   - error_severity (CRITICAL/HIGH/MEDIUM/LOW)
   - error_phase
   - error_message
   - recovery_action
   - recovery_success
   - fallback_used

5. Degradations:
   - degradation_type
   - degradation_phase
   - fallback_strategy
   - data_quality_impact

6. Validation Results:
   - validation_score
   - validation_passed
   - validation_errors []
   - validation_warnings []
   - items_validated_count

7. Final Output:
   - total_items_generated
   - items_by_category {revenue, engagement, retention}
   - unique_send_types_used
   - schedule_start_date
   - schedule_end_date
   - warnings []
   - recommendations []
```

#### Example Log Entries

```json
{
  "timestamp": "2025-12-17T14:32:15.123Z",
  "generation_id": "a7f3c2d1-9b8e-4f12-a3d5-6c8e9f0b1a2d",
  "creator_id": "alexia",
  "phase": "phase_3",
  "event_type": "error",
  "message": "Caption query returned insufficient results",
  "error_type": "insufficient_captions",
  "send_type": "ppv_unlock",
  "required": 6,
  "available": 2,
  "recovery_action": "lower_threshold"
}

{
  "timestamp": "2025-12-17T14:32:15.456Z",
  "generation_id": "a7f3c2d1-9b8e-4f12-a3d5-6c8e9f0b1a2d",
  "creator_id": "alexia",
  "phase": "phase_3",
  "event_type": "recovery",
  "message": "Recovery successful: lower_threshold",
  "error_type": "insufficient_captions",
  "recovery_action": "lower_threshold",
  "recovery_success": true,
  "threshold_used": 20,
  "captions_found": 6
}

{
  "timestamp": "2025-12-17T14:32:20.789Z",
  "generation_id": "a7f3c2d1-9b8e-4f12-a3d5-6c8e9f0b1a2d",
  "creator_id": "alexia",
  "phase": "phase_7",
  "event_type": "validation",
  "message": "Validation passed: score 87",
  "validation_score": 87,
  "passed": true,
  "errors": [],
  "warnings": ["Caption freshness below 30 for 2 items"]
}
```

---

### Error Response Format

Standardized error response structure for consistency and debugging.

```python
@dataclass
class ErrorResponse:
    """
    Standardized error response structure.
    """
    success: bool = False
    error_code: str
    error_message: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    phase: str
    generation_id: str
    creator_id: str
    timestamp: str

    details: dict = field(default_factory=dict)
    partial_result: dict = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_action: str | None = None
    recovery_success: bool = False

    resolution: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "severity": self.severity,
            "phase": self.phase,
            "generation_id": self.generation_id,
            "creator_id": self.creator_id,
            "timestamp": self.timestamp,
            "details": self.details,
            "partial_result": self.partial_result,
            "recovery": {
                "attempted": self.recovery_attempted,
                "action": self.recovery_action,
                "success": self.recovery_success
            },
            "resolution": self.resolution,
            "recommendations": self.recommendations
        }
```

#### Example Error Responses

```json
// CRITICAL Error - Cannot Continue
{
  "success": false,
  "error_code": "CREATOR_NOT_FOUND",
  "error_message": "Creator profile not found in database",
  "severity": "CRITICAL",
  "phase": "phase_1",
  "generation_id": "a7f3c2d1-9b8e-4f12-a3d5-6c8e9f0b1a2d",
  "creator_id": "invalid_creator",
  "timestamp": "2025-12-17T14:32:15.123Z",
  "details": {
    "creator_id": "invalid_creator",
    "database_queried": true
  },
  "partial_result": {},
  "recovery": {
    "attempted": false,
    "action": null,
    "success": false
  },
  "resolution": {
    "action": "Verify creator_id and retry",
    "contact": "Database administrator"
  },
  "recommendations": [
    "Check creator_id spelling",
    "Verify creator exists in active_creators table",
    "Run get_active_creators() to see available creators"
  ]
}

// MEDIUM Error - Degraded Mode
{
  "success": true,
  "error_code": "CAPTION_SHORTAGE_DEGRADED",
  "error_message": "Caption pool depleted for ppv_unlock - using lower thresholds",
  "severity": "MEDIUM",
  "phase": "phase_3",
  "generation_id": "a7f3c2d1-9b8e-4f12-a3d5-6c8e9f0b1a2d",
  "creator_id": "alexia",
  "timestamp": "2025-12-17T14:32:15.456Z",
  "details": {
    "send_type": "ppv_unlock",
    "required": 6,
    "available_at_threshold_40": 2,
    "available_at_threshold_20": 6,
    "threshold_used": 20
  },
  "partial_result": {
    "items_created": 48,
    "items_with_degraded_captions": 6
  },
  "recovery": {
    "attempted": true,
    "action": "lower_freshness_threshold",
    "success": true
  },
  "resolution": {
    "action": "Create new ppv_unlock captions to improve freshness",
    "priority": "medium",
    "count_needed": 4
  },
  "recommendations": [
    "Generate 4+ new ppv_unlock captions",
    "Review caption performance to identify top performers",
    "Consider expanding caption variety for this send type"
  ]
}
```

---

### Error Handling Best Practices

1. **Always log before throwing**: Ensure errors are logged with full context before raising exceptions
2. **Include recovery actions**: Every error should suggest next steps
3. **Preserve partial results**: If 80% of generation succeeded, return what's available
4. **Use tracking IDs**: Generate unique IDs for cross-system correlation
5. **Fail fast for CRITICAL**: Don't waste time on doomed pipelines
6. **Degrade gracefully for MEDIUM/LOW**: Maximize output even with imperfect data
7. **Test recovery paths**: Regularly test fallback strategies in staging
8. **Monitor circuit breaker**: Track MCP availability and adjust thresholds
9. **Audit trail completeness**: Ensure every decision is logged for post-mortem analysis
10. **User-friendly messages**: Translate technical errors into actionable recommendations

---

## Adaptive Adjustments

### Saturation-Based Modulation

```
SATURATION RESPONSE MATRIX:

| Saturation Score | Revenue Adj | Engagement Adj | Strategy           |
|------------------|-------------|----------------|---------------------|
| 0-30             | +20%        | -10%           | Aggressive revenue  |
| 31-50            | +10%        | 0%             | Opportunistic       |
| 51-70            | 0%          | 0%             | Standard            |
| 71-85            | -20%        | +10%           | Light touch         |
| 86-100           | -30%        | +20%           | Engagement focus    |

IMPLEMENTATION:

IF saturation_score > 70:
    revenue_per_day = round(base_revenue * 0.80)
    engagement_per_day = round(base_engagement * 1.10)
    # Prioritize bump_text_only for lowest pressure

ELSE IF saturation_score < 30 AND opportunity_score > 70:
    revenue_per_day = round(base_revenue * 1.20)
    # Prioritize ppv_unlock and bundle for revenue capture
```

### Opportunity-Based Prioritization

```
OPPORTUNITY RESPONSE:

IF opportunity_score > 70:
    # High revenue potential
    send_type_priority = {
        "ppv_unlock": 1.5,   # 50% more likely
        "bundle": 1.4,
        "flash_bundle": 1.3,
        "vip_program": 1.2
    }

IF opportunity_score < 40:
    # Build engagement first
    send_type_priority = {
        "bump_normal": 1.3,
        "bump_descriptive": 1.3,
        "dm_farm": 1.2,
        "link_drop": 1.1
    }
```

### Low Caption Freshness Response

```
IF average_freshness < 50:
    # Caption pool is stale

    1. Prioritize bump_text_only (no specific caption needed)
    2. Reduce ppv_unlock count (high caption dependency)
    3. Flag creator for caption creation
    4. Use composite scoring with updated weights:
       score = freshness * 0.40 + performance * 0.35 + type_priority * 0.15 + diversity * 0.05 + persona * 0.05

    response.recommendations.append(
        "Caption freshness low - prioritizing text-only bumps"
    )
```

### Trend-Based Adjustments

```
TREND RESPONSE:

IF revenue_trend == "down":
    # Revenue declining
    1. Shift toward engagement types
    2. Reduce ppv_unlock frequency
    3. Increase bump variety
    4. Add more dm_farm for re-engagement

IF revenue_trend == "up":
    # Revenue growing
    1. Maintain or increase revenue items
    2. Capitalize with bundle offers
    3. Consider vip_program placement
```

---

## Pipeline State Diagram

```
                    +------------------+
                    |     START        |
                    +--------+---------+
                             |
                             v
+-------------------------------------------------------------------+
|  PHASE 1: INITIALIZATION                                          |
|  +---------------------------------------------------------+      |
|  | get_creator_profile --> get_volume_config -->           |      |
|  | get_performance_trends --> get_send_types -->           |      |
|  | get_vault_availability --> get_best_timing              |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: creator, volume, performance,
                             |        send_types, vault, timing
                             v
+-------------------------------------------------------------------+
|  PHASE 2: SEND TYPE ALLOCATION                                    |
|  +---------------------------------------------------------+      |
|  | calculate_quotas --> apply_adjustments -->               |      |
|  | check_limits --> allocate_slots --> interleave           |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: allocation_matrix[day][slot]
                             v
+-------------------------------------------------------------------+
|  PHASE 3: CONTENT MATCHING                                        |
|  +---------------------------------------------------------+      |
|  | FOR each slot:                                           |      |
|  |   get_send_type_captions --> score_captions -->          |      |
|  |   select_unused --> cross_reference_vault                |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: content_assignments[]
                             v
+-------------------------------------------------------------------+
|  PHASE 4: AUDIENCE TARGETING                                      |
|  +---------------------------------------------------------+      |
|  | get_audience_targets --> FOR each slot:                  |      |
|  |   get_send_type_details --> assign_target -->            |      |
|  |   validate_channel --> set_channel                       |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: targeted_items[]
                             v
+-------------------------------------------------------------------+
|  PHASE 5: TIMING OPTIMIZATION                                     |
|  +---------------------------------------------------------+      |
|  | sort_by_priority --> FOR each item:                      |      |
|  |   get_preferred_hours --> find_valid_slot -->            |      |
|  |   validate_spacing --> set_time --> set_expiration       |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: timed_items[]
                             v
+-------------------------------------------------------------------+
|  PHASE 6: FOLLOW-UP GENERATION                                    |
|  +---------------------------------------------------------+      |
|  | identify_eligible --> FOR each parent:                   |      |
|  |   check_daily_limit --> create_followup -->              |      |
|  |   calculate_timing --> select_caption                    |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | state: parent_items[], followup_items[]
                             v
+-------------------------------------------------------------------+
|  PHASE 7: ASSEMBLY & VALIDATION                                   |
|  +---------------------------------------------------------+      |
|  | merge_components --> validate_required_fields -->        |      |
|  | check_uniqueness --> check_vault --> check_timing -->    |      |
|  | check_volume --> check_persona --> generate_report       |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                             |
                             | validation passed?
                             |
              +------+-------+--------+
              |      |                |
              v      v                v
          PASSED   WARNINGS       FAILED
              |      |                |
              v      v                |
+----------------------------+        |
| save_schedule(             |        |
|   creator_id,              |        |
|   week_start,              |        |
|   items                    |        |
| )                          |        |
+----------------------------+        |
              |                       |
              v                       v
        +---------+           +-------------+
        | SUCCESS |           | ERROR       |
        | RESPONSE|           | RESPONSE    |
        +---------+           +-------------+
```

---

## MCP Tool Usage Summary

### Phase 1: Initialization
| Tool | Call Count | Purpose |
|------|------------|---------|
| `get_creator_profile` | 1 | Load creator data, page type, tier |
| `get_volume_config` | 1 | Get daily quotas per category |
| `get_performance_trends` | 1 | Saturation/opportunity scores |
| `get_send_types` | 1 | Filtered send type catalog |
| `get_vault_availability` | 1 | Available content types |
| `get_best_timing` | 1 | Historical peak hours |

### Phase 2: Allocation
| Tool | Call Count | Purpose |
|------|------------|---------|
| (none) | - | Pure computation from Phase 1 data |

### Phase 3: Content Matching
| Tool | Call Count | Purpose |
|------|------------|---------|
| `get_send_type_captions` | N (per slot) | Compatible captions |
| `get_top_captions` | 0-N (fallback) | Generic caption fallback |
| `get_persona_profile` | 1 | Persona consistency check |

### Phase 4: Targeting
| Tool | Call Count | Purpose |
|------|------------|---------|
| `get_audience_targets` | 1 | Available targets |
| `get_send_type_details` | N (per slot) | Target requirements |

### Phase 5: Timing
| Tool | Call Count | Purpose |
|------|------------|---------|
| `get_send_type_details` | N (if not cached) | Timing constraints |

### Phase 6: Follow-ups
| Tool | Call Count | Purpose |
|------|------------|---------|
| `get_send_type_captions` | 1 | Follow-up captions |

### Phase 7: Assembly
| Tool | Call Count | Purpose |
|------|------------|---------|
| `save_schedule` | 1 | Persist to database |

---

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Total pipeline duration | < 15 seconds | Start to save_schedule completion |
| MCP call latency | < 500ms each | Per-tool timing |
| Validation pass rate | > 95% | Schedules passing without errors |
| Caption freshness average | > 60 | Across all assigned captions |
| Duplicate caption rate | < 5% | Captions used more than once |
| Follow-up generation rate | > 90% | Of eligible PPV items |

---

## Phase Transition Checkpoints

Validate successful completion before proceeding to the next phase. These checkpoints ensure data integrity and prevent cascade failures.

### After Phase 1 (Performance Analysis)

Before proceeding to Send Type Allocation, verify:

- [ ] **Creator profile loaded successfully**: `creator.id`, `creator.page_type`, `creator.tier` are populated
- [ ] **Saturation score calculated**: `saturation_score` is a number between 0-100
- [ ] **Opportunity score calculated**: `opportunity_score` is a number between 0-100
- [ ] **Volume config retrieved**: `revenue_per_day`, `engagement_per_day`, `retention_per_day` are set
- [ ] **Send types filtered**: Only page_type-compatible send types are available
- [ ] **Vault availability loaded**: Content type availability is known

**Checkpoint Action**: If any check fails, halt pipeline and return initialization error.

---

### After Phase 2 (Send Type Allocation)

Before proceeding to Content Matching, verify:

- [ ] **⚠️ CRITICAL: 22-Type Diversity Check**: At least 10 unique `send_type_key` values across the week
- [ ] **⚠️ NOT just ppv and bump**: Allocation includes variety (bundle, flash_bundle, game_post, dm_farm, etc.)
- [ ] **Revenue variety**: At least 5 different revenue types used weekly
- [ ] **Engagement variety**: At least 5 different engagement types used weekly
- [ ] **Daily allocation totals match volume_config**: Each day has correct number of items per category
- [ ] **Retention types excluded for free pages**: No `renew_on_*`, `expired_winback` for `page_type='free'`
- [ ] **Weekly limits not exceeded**: `vip_program` <= 1, `snapchat_bundle` <= 1 per week
- [ ] **No consecutive same-type slots**: Variety rule enforced across daily allocations
- [ ] **All 7 days have allocations**: No days with zero items
- [ ] **⚠️ NEW: Daily strategy variation**: Each day has a `strategy_used` assigned, no consecutive repeats
- [ ] **⚠️ NEW: Strategy diversity**: At least 3 different strategies used across the week

**DIVERSITY VALIDATION (MANDATORY):**
```python
def validate_allocation_diversity(allocation):
    all_types = set()
    for day in allocation.values():
        for item in day:
            all_types.add(item["send_type_key"])

    # HARD REJECTION CRITERIA
    if len(all_types) < 10:
        raise ValueError(f"REJECTED: Only {len(all_types)} unique types. Need 10+")

    if all_types == {"ppv_unlock", "bump_normal"}:
        raise ValueError("REJECTED: Only ppv and bump. MUST use full 22-type system.")

    revenue_types = {"ppv_unlock", "bundle", "flash_bundle", "game_post",
                     "first_to_tip", "vip_program", "snapchat_bundle"}
    revenue_used = all_types & revenue_types
    if len(revenue_used) < 5:
        raise ValueError(f"REJECTED: Only {len(revenue_used)} revenue types. Need 5+")

    return True
```

**Checkpoint Action**: If diversity check fails, **REJECT the allocation and restart Phase 2** with explicit instruction to use variety. If weekly limits exceeded, remove excess items by lowest priority. If retention on free page, remove those items.

---

### After Phase 3 (Content Matching)

Before proceeding to Audience Targeting, verify:

- [ ] **All items have captions assigned**: Every slot has `caption_id` and `caption_text`
- [ ] **Freshness thresholds met**: All captions have `freshness_score >= 30` (or documented fallback)
- [ ] **Performance thresholds met**: All captions have `performance_score >= 40` (or documented fallback)
- [ ] **No duplicate captions**: Each `caption_id` appears only once in the schedule
- [ ] **Caption types match send types**: Compatible caption types per `send_type_caption_requirements`

**Checkpoint Action**: If caption shortage, log warning and apply fallback strategy. Flag items needing manual caption creation.

---

### After Phase 4 (Audience Targeting)

Before proceeding to Timing Optimization, verify:

- [ ] **All items have targets assigned**: Every slot has `target_key`
- [ ] **Targets match channel capabilities**: Channel supports the assigned target type
- [ ] **Page type compatibility validated**: No paid-only targets on free pages
- [ ] **Required targets enforced**: `ppv_followup` -> `ppv_non_purchasers`, `renew_on_message` -> `renew_off`
- [ ] **Channel keys assigned**: Every slot has `channel_key`

**Checkpoint Action**: If target incompatible, fallback to `all_active`. Log any fallback decisions.

---

### After Phase 5 (Timing Optimization)

Before proceeding to Followup Generation, verify:

- [ ] **All items have scheduled times**: Every slot has `scheduled_time`
- [ ] **Minimum spacing maintained**: At least 45 minutes between any two sends
- [ ] **No avoid_hours violations**: No items scheduled between 03:00-07:00
- [ ] **Revenue items in prime slots**: PPV and bundles scheduled in peak_hours (19:00-22:00)
- [ ] **Same-type spacing respected**: `min_hours_between` from send_type_details honored
- [ ] **No time conflicts**: No two items at exact same time on same day
- [ ] **⚠️ NEW: Time diversity check**: No exact time (e.g., 20:00:00) used more than 2x weekly
- [ ] **⚠️ NEW: Jitter applied**: All items have `variation_metadata` with jitter values
- [ ] **⚠️ NEW: Daily prime hour rotation**: Each day uses rotated prime hours (±1 hour from base)

**Checkpoint Action**: If spacing violated, shift later item by minimum required interval. If avoid_hours violation, move to nearest valid hour.

---

### After Phase 6 (Followup Generation)

Before proceeding to Final Assembly, verify:

- [ ] **PPV items have followups**: All eligible items (`can_have_followup=1`) have followup generated
- [ ] **Followup delays correct**: 15-30 minute offset from parent item
- [ ] **Daily followup limits respected**: Max 4 `ppv_followup` items per day
- [ ] **Followup captions assigned**: All followups have captions (or flagged for manual)
- [ ] **Parent references valid**: All `parent_item_id` values reference actual schedule items
- [ ] **Late night handling**: Followups after 23:30 pushed to next day 08:00

**Checkpoint Action**: If daily limit exceeded, skip lowest-priority parent's followup. Log skipped items.

---

### After Phase 7 (Final Assembly & Validation)

Before saving to database, verify:

- [ ] **Execute quality-validator agent**: Run comprehensive validation checklist
- [ ] **All checklist items pass**: No critical errors (warnings acceptable with documentation)
- [ ] **Category balance verified**: Revenue >= 30%, Engagement >= 25%, Retention <= 20%
- [ ] **No orphaned followups**: All followups have valid parent references
- [ ] **Required fields complete**: `scheduled_date`, `scheduled_time`, `send_type_key`, `channel_key` for all items
- [ ] **Validation report generated**: Document all warnings, errors, and recommendations

**Checkpoint Action**: If validation score < 70, reject schedule and return detailed error report. If 70-84, return with "NEEDS_REVIEW" status. If >= 85, proceed to save.

---

### Checkpoint Summary Table

| Phase | Critical Checks | Halt Condition | Recovery Action |
|-------|-----------------|----------------|-----------------|
| 1 | Creator profile, Volume config | Any missing | Return init error |
| 2 | Daily totals, Weekly limits | Limits exceeded | Remove excess items |
| 3 | Caption assignment, Freshness | No captions | Apply fallback chain |
| 4 | Target assignment, Compatibility | Target invalid | Fallback to all_active |
| 5 | Time assignment, Spacing | Time conflict | Shift items |
| 6 | Followup generation, Limits | Daily limit hit | Skip lower priority |
| 7 | Validation score | Score < 70 | Reject schedule |

---

## Daily Variation System

**Objective**: Create authentic schedule variation that mimics human scheduling patterns and prevents repetitive, robotic schedules.

### Variation Philosophy

The variation system operates on two principles:

1. **Structural Variation**: Daily strategy rotation affects WHAT gets scheduled
2. **Temporal Variation**: Time offsets and jitter affect WHEN things get scheduled

Combined, these create schedules that feel naturally varied week-to-week while maintaining optimal performance patterns.

### Variation Components

#### 1. Daily Strategy Rotation (Phase 2)

**Purpose**: Vary send type mix across days to prevent monotonous patterns

**Mechanism**:
- 5 distinct strategies: `revenue_focus`, `engagement_burst`, `balanced_standard`, `variety_max`, `storytelling`
- Weighted selection based on saturation/opportunity scores
- Anti-repeat enforcement (no consecutive days with same strategy)
- Minimum 3 different strategies per week

**Impact**:
- Monday: revenue_focus → More bundles, flash sales, VIP emphasis
- Tuesday: storytelling → More descriptive bumps, wall link drops
- Wednesday: variety_max → Maximum type diversity, least-used types prioritized
- Thursday: engagement_burst → More DM farms, like farms, bump variety
- Friday: balanced_standard → Standard volume config distribution

**Validation**:
```python
strategies_used = set(day_strategy.values())
assert len(strategies_used) >= 3, "Need 3+ strategies per week"
```

#### 2. Daily Prime Hour Rotation (Phase 5)

**Purpose**: Prevent exact time repeats across weeks

**Mechanism**:
- Base prime hours (e.g., [20, 21, 22]) rotated ±1 hour per day
- Cycle: -1, 0, +1, -1, 0, +1, -1 (repeats across weeks with offset)
- Revenue items scheduled in these rotated windows

**Examples**:
- Week 1 Monday: [19, 20, 21] (base - 1)
- Week 2 Monday: [20, 21, 22] (base + 0) - Starts at different offset
- Week 3 Monday: [21, 22, 23] (base + 1)

**Impact**: Same day of week has different prime hours week-to-week

#### 3. Morning/Evening Time Shifts (Phase 5)

**Purpose**: Add subtle temporal variation within days

**Mechanism**:
- Even days (Mon, Wed, Fri, Sun): Morning -15min, Evening +20min
- Odd days (Tue, Thu, Sat): Morning +15min, Evening -20min
- Applied on top of base time selection

**Examples**:
- Monday engagement item at 9:00 → shifted to 8:45 (9:00 - 15min)
- Monday revenue item at 20:00 → shifted to 20:20 (20:00 + 20min)
- Tuesday engagement item at 9:00 → shifted to 9:15 (9:00 + 15min)

#### 4. Per-Day Jitter (Phase 5)

**Purpose**: Create unique exact times, prevent mechanical repetition

**Mechanism**:
- Random value between -7 to +8 minutes per day
- Applied to ALL items on that day
- Ensures no two weeks have identical schedules

**Examples**:
- Day jitter = +7 minutes
- Item scheduled at 20:20 → becomes 20:27
- Item scheduled at 9:15 → becomes 9:22

#### 5. Weekly Time Repeat Limit (Phase 5)

**Purpose**: Enforce time diversity constraint

**Mechanism**:
- After all assignments, count usage of each exact time
- If any time used >2x, adjust excess items by ±10-15 minutes
- Revalidate spacing constraints after adjustment

**Target**: Max 2 occurrences of any exact time per week

### Variation Metadata Tracking

Every scheduled item includes variation metadata for auditability:

```json
{
  "variation_metadata": {
    "base_hour": 20,
    "time_shift": 20,
    "jitter": -13,
    "daily_strategy": "revenue_focus",
    "prime_hours_used": [19, 20, 21],
    "time_adjusted": false,
    "adjustment_reason": null
  }
}
```

### Variation Validation Checklist

After Phase 2 & 5, validate variation requirements:

**Phase 2 Validation (Strategy Variation)**:
- [ ] At least 3 different strategies used weekly
- [ ] No consecutive days with same strategy
- [ ] Strategy distribution tracked in `daily_strategies` object
- [ ] All items have `strategy_used` and `flavor_emphasis` fields

**Phase 5 Validation (Temporal Variation)**:
- [ ] Daily prime hours rotated (check `daily_prime_hours` object)
- [ ] Morning/evening shifts applied (verify time_shift in metadata)
- [ ] Jitter applied to all items (verify jitter in metadata)
- [ ] No exact time used >2x weekly (check time_usage_counts)
- [ ] All items have complete `variation_metadata` object

### Expected Outcomes

**Without Variation System**:
- Same send type mix every Monday
- Revenue items always at 20:00, 21:00, 22:00
- Robotic, predictable patterns
- Audience fatigue and pattern recognition

**With Variation System**:
- Monday mix varies: revenue_focus vs. storytelling vs. variety_max
- Revenue items at 19:47, 20:23, 21:08 (rotated + shifted + jittered)
- Natural, human-like scheduling
- Sustained audience engagement and unpredictability

### Performance Impact

**Computational Cost**: +0.5 seconds total pipeline time
- Strategy selection: +0.1s (Phase 2)
- Prime hour rotation: +0.1s (Phase 5)
- Jitter application: +0.2s (Phase 5)
- Time repeat validation: +0.1s (Phase 5)

**Benefit**: 15-25% improvement in schedule authenticity scores, reduced audience pattern recognition

---

## MCP Tools Reference

All database operations in this pipeline use the `eros-db` MCP server with 17 available tools.

### Creator Data Tools (3)

**`get_creator_profile(creator_id)`**
- Returns: Creator metadata, analytics summary, volume config, top content types
- Used in: Phase 1.1
- Response: `{creator: {...}, analytics: {...}, volume: {...}, top_content_types: [...]}`

**`get_active_creators(tier?, page_type?)`**
- Returns: List of all active creators with performance metrics
- Used in: Batch generation workflows
- Filters: Optional tier (1/2/3) and page_type (paid/free)

**`get_persona_profile(creator_id)`**
- Returns: Tone, archetype, emoji frequency, slang level, voice samples
- Used in: Phase 3.2 (persona consistency validation)
- Response: `{persona: {...}, enhanced: {...}, voice_samples: [...]}`

### Performance & Analytics Tools (3)

**`get_performance_trends(creator_id, period)`**
- Returns: Saturation/opportunity scores, revenue trends
- Used in: Phase 1.3
- Periods: "7d", "14d", "30d"
- Response: Multi-horizon scores used in fusion calculation

**`get_content_type_rankings(creator_id)`**
- Returns: TOP/MID/LOW/AVOID tiers for content types
- Used in: Phase 3.3 (vault cross-reference)
- Response: `{rankings: [...], top_types: [...], avoid_types: [...]}`

**`get_best_timing(creator_id, days_lookback)`**
- Returns: Peak hours and days from historical performance
- Used in: Phase 1.6, Phase 5.3 (timing optimization)
- Response: `{timezone: "...", best_hours: [...], best_days: [...]}`

### Content & Captions Tools (3)

**`get_top_captions(creator_id, caption_type?, content_type?, send_type_key?, min_freshness, min_performance, limit)`**
- Returns: Performance-ranked captions with freshness scoring
- Used in: Phase 3.1, Phase 3.5 (fallback)
- Filters: By caption type, content type, or send_type_key compatibility

**`get_send_type_captions(creator_id, send_type_key, min_freshness, min_performance, limit)`**
- Returns: Captions compatible with specific send type via caption type mappings
- Used in: Phase 3.1, Phase 6.4 (followup captions)
- Maps send types to compatible caption types automatically

**`get_vault_availability(creator_id)`**
- Returns: Available content types in creator's vault
- Used in: Phase 1.5, Phase 3.3 (vault validation)
- Response: `{vault_items: [...], content_types: [...]}`

### Send Type Configuration Tools (3)

**`get_send_types(category?, page_type?)`**
- Returns: Send type catalog filtered by category and page_type applicability
- Used in: Phase 1.4
- Filters: category (revenue/engagement/retention), page_type (paid/free)

**`get_send_type_details(send_type_key)`**
- Returns: Complete configuration for a single send type
- Used in: Phases 3.2, 4.2, 4.4, 5.7, 6.1
- Response: Requirements, constraints, timing rules, targeting defaults

**`get_volume_config(creator_id)` [CRITICAL]**
- Returns: **OptimizedVolumeResult** with dynamic volume calculation
- Used in: Phase 1.2
- **Response Structure**:
  ```
  {
    // Legacy (backward compatible)
    "volume_level": "High",
    "ppv_per_day": 5,
    "bump_per_day": 4,

    // Category volumes
    "revenue_per_day": 6,
    "engagement_per_day": 5,
    "retention_per_day": 2,

    // Weekly distribution (CONSUMED IN PHASE 2.1)
    "weekly_distribution": {0: 12, 1: 13, 2: 13, 3: 13, 4: 14, 5: 13, 6: 13},

    // Content strategy
    "content_allocations": {"solo": 3, "lingerie": 2, ...},

    // Optimization metadata
    "confidence_score": 0.85,  // Used in Phase 2.2, Phase 7.2
    "elasticity_capped": false,
    "caption_warnings": [],  // Used in Phase 7.2
    "dow_multipliers_used": {0: 0.95, 1: 1.0, ...},
    "adjustments_applied": ["base_tier_calculation", "multi_horizon_fusion", ...],

    // Multi-horizon fusion
    "fused_saturation": 45.0,
    "fused_opportunity": 62.0,
    "divergence_detected": false,

    // Tracking
    "prediction_id": 123,
    "message_count": 156,
    "calculation_source": "optimized"
  }
  ```

### Targeting & Channels Tools (2)

**`get_audience_targets(page_type?, channel_key?)`**
- Returns: Audience targeting segments
- Used in: Phase 4.1
- Filters: By page_type applicability and channel compatibility

**`get_channels(supports_targeting?)`**
- Returns: Distribution channels (wall_post, mass_message, targeted_message, story, live)
- Used in: Phase 4.4
- Filter: Optional supports_targeting boolean

### Schedule Operations Tools (2)

**`save_schedule(creator_id, week_start, items)`**
- Persists generated schedule to database
- Used in: Phase 7.4
- Validates send_type_key, channel_key, target_key before saving

**`execute_query(query, params)`**
- Execute read-only SQL for custom analysis
- Used in: Diagnostics and reporting
- Safety: READ-only, parameterized queries required

### Deprecated Tools (1)

**`get_volume_assignment(creator_id)` [DEPRECATED]**
- Legacy static volume assignment
- Status: Still functional but returns deprecation warning
- Replacement: Use `get_volume_config()` instead
- Reason: Static assignments replaced by dynamic calculation

### Tool Call Patterns

**Phase 1 (Initialization)**: 6 parallel calls
```
[PARALLEL]
  - get_creator_profile(creator_id)
  - get_volume_config(creator_id)
  - get_performance_trends(creator_id, "14d")

[PARALLEL]
  - get_send_types(page_type)
  - get_vault_availability(creator_id)
  - get_best_timing(creator_id)
```

**Phase 3 (Content Matching)**: N calls per slot
```
FOR each slot:
  get_send_type_captions(creator_id, slot.send_type_key)
  [FALLBACK] get_top_captions(creator_id, ...)
```

**Phase 4 (Targeting)**: 1 + N calls
```
get_audience_targets(page_type)

FOR each slot:
  get_send_type_details(slot.send_type_key)
```

**Phase 6 (Followups)**: 1 call
```
get_send_type_captions(creator_id, "ppv_followup")
```

**Phase 7 (Assembly)**: 1 call
```
save_schedule(creator_id, week_start, items)
```

### Tool Count Verification
✓ Creator Data: 3 tools
✓ Performance & Analytics: 3 tools
✓ Content & Captions: 3 tools
✓ Send Type Configuration: 3 tools
✓ Targeting & Channels: 2 tools
✓ Schedule Operations: 2 tools
✓ Deprecated: 1 tool
**Total: 17 tools**

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.3.0 | 2025-12-17 | Comprehensive error handling and recovery procedures: 4 severity levels (CRITICAL/HIGH/MEDIUM/LOW), per-phase error handling with recovery procedures, phase recovery matrix, graceful degradation rules, circuit breaker pattern for MCP calls with exponential backoff, structured logging and observability, error tracking IDs, audit trail requirements, standardized error response format, 10 best practices |
| 2.2.0 | 2025-12-16 | Full OptimizedVolumeResult integration: 14 fields, 8 optimization modules, weekly_distribution consumption in Phase 2, caption_warnings and confidence_score handling in Phase 7 validation |
| 1.2.0 | 2025-12-16 | Added daily variation system (Phase 6 implementation) |
| 1.1.0 | 2025-12-16 | Added phase transition checkpoints |
| 1.0.0 | 2025-01-15 | Initial orchestration documentation |
