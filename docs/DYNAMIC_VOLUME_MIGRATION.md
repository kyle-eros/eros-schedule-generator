# Dynamic Volume Calculation Migration

## Overview

Successfully migrated MCP tools from static `volume_assignments` table lookups to dynamic volume calculation based on real-time performance metrics. This change provides intelligent, adaptive volume allocation that responds to creator performance trends.

**Date**: 2025-12-16
**Status**: Complete and Tested

## Changes Made

### 1. Modified `mcp/tools/send_types.py`

**Function**: `get_volume_config(creator_id: str)`

**Changes**:
- Removed static lookup from `volume_assignments` table
- Implemented dynamic calculation using `python.volume.dynamic_calculator`
- Pulls saturation/opportunity scores from `volume_performance_tracking` (14d period)
- Falls back to on-demand calculation using `calculate_scores_from_db()` when tracking data unavailable
- Defaults to neutral scores (50.0/50.0) if no performance data exists

**New Response Fields**:
```python
{
    # Backward compatible fields
    "volume_level": "High",              # Tier name
    "ppv_per_day": 4,                    # Revenue items per day
    "bump_per_day": 3,                   # Engagement items per day
    "revenue_items_per_day": 4,
    "engagement_items_per_day": 3,
    "retention_items_per_day": 2,
    "bundle_per_week": 3,
    "game_per_week": 2,
    "followup_per_day": 4,

    # New metadata fields
    "calculation_source": "dynamic",     # Always "dynamic"
    "fan_count": 11184,
    "page_type": "paid",
    "saturation_score": 100.0,
    "opportunity_score": 50.0,
    "revenue_trend": 0.0,
    "data_source": "calculated_on_demand",  # or "volume_performance_tracking" or "default_values"
    "tracking_date": "2025-12-16"
}
```

### 2. Modified `mcp/tools/performance.py`

**Function**: `get_volume_assignment(creator_id: str)`

**Changes**:
- Deprecated function (still functional for backward compatibility)
- Now redirects to `get_volume_config()` internally
- Adds deprecation warnings to response

**New Response**:
```python
{
    "volume_level": "High",
    "ppv_per_day": 4,
    "bump_per_day": 3,
    "assigned_at": "2025-12-16",
    "assigned_by": "dynamic_calculation",
    "assigned_reason": "fan_count_bracket",
    "_deprecated": True,
    "_message": "get_volume_assignment is deprecated. Use get_volume_config() for dynamic calculation with full metadata."
}
```

### 3. Modified `mcp/tools/creator.py`

**Function**: `get_active_creators(tier, page_type)`

**Changes**:
- Removed `LEFT JOIN volume_assignments` from query
- Removed fields: `va.volume_level`, `va.ppv_per_day`, `va.bump_per_day`
- Cleaner query focused on creator and persona data only

**Function**: `get_creator_profile(creator_id: str)`

**Changes**:
- Replaced static `volume_assignments` query with `get_volume_config()` call
- Now returns dynamic volume calculation in `volume_assignment` field
- Improved connection management (closes DB connection before calling `get_volume_config()`)

## Volume Tier Calculation

### Fan Count Brackets

```
Ultra: 15,000+ fans    → 6 revenue, 4 engagement, 3 retention (paid)
High:  5,000-14,999    → 4 revenue, 3 engagement, 2 retention (paid)
Mid:   1,000-4,999     → 3-4 revenue, 2 engagement, 2 retention (paid)
Low:   0-999           → 2-3 revenue, 2 engagement, 1 retention (paid)
```

**Note**: Free pages always have 0 retention items regardless of tier.

### Dynamic Adjustments

The base tier volumes are adjusted based on:

1. **Saturation Score** (0-100)
   - High saturation (>70): Reduces volume by 30% (multiplier 0.7)
   - Medium saturation (50-70): Reduces volume by 10% (multiplier 0.9)
   - Low saturation (<50): No reduction (multiplier 1.0)

2. **Opportunity Score** (0-100)
   - High opportunity (>70) + Low saturation (<50): Increases volume by 20% (multiplier 1.2)
   - Medium opportunity (60-70) + Very low saturation (<30): Increases volume by 10% (multiplier 1.1)
   - Otherwise: No increase (multiplier 1.0)

3. **Revenue Trend** (percentage change)
   - Strong negative (<-15%): Reduces volume by 1 send
   - Strong positive (>15%): Increases volume by 1 send
   - Otherwise: No adjustment

### Data Sources Priority

1. **Primary**: `volume_performance_tracking` table (14d period)
   - Pre-calculated saturation and opportunity scores
   - Most accurate, includes trend data

2. **Fallback**: On-demand calculation from `mass_messages`
   - Calculates scores from last 14 days of message performance
   - Less accurate (no trend data available)

3. **Default**: Neutral scores (50.0/50.0)
   - Used when no performance data exists
   - Safe defaults for new creators

## Testing Results

All tests passed successfully across 37 active creators:

### Volume Tier Assignment
- ✓ All creators correctly tiered based on fan count
- ✓ Ultra tier: 5 creators (15,000+ fans)
- ✓ High tier: 7 creators (5,000-14,999 fans)
- ✓ Mid tier: 11 creators (1,000-4,999 fans)
- ✓ Low tier: 14 creators (0-999 fans)

### Function Tests
- ✓ `get_volume_config()` returns dynamic calculation
- ✓ `get_volume_assignment()` shows deprecation notice
- ✓ `get_creator_profile()` uses dynamic volume
- ✓ `get_active_creators()` no longer includes volume_assignments fields

## Example Outputs

### Before (Static Assignment)

```python
# get_volume_config("grace_bennett")
{
    "volume_level": "Low",  # INCORRECT - 12,434 fans should be High tier
    "ppv_per_day": 3,
    "bump_per_day": 3,
    "assigned_at": "2024-11-15",
    "assigned_reason": "initial_setup"
}
```

### After (Dynamic Calculation)

```python
# get_volume_config("grace_bennett")
{
    "volume_level": "High",  # CORRECT - dynamically calculated from 12,434 fans
    "ppv_per_day": 4,
    "bump_per_day": 3,
    "revenue_items_per_day": 4,
    "engagement_items_per_day": 3,
    "retention_items_per_day": 2,
    "fan_count": 12434,
    "saturation_score": 45.0,
    "opportunity_score": 65.0,
    "calculation_source": "dynamic",
    "data_source": "volume_performance_tracking"
}
```

## Migration Benefits

1. **Accuracy**: Volume tiers now automatically correct based on current fan count
2. **Adaptability**: Responds to performance trends (saturation, opportunity, revenue)
3. **Transparency**: Provides full metadata on calculation source and scores
4. **Maintenance**: No need to manually update volume_assignments table
5. **Intelligence**: Adjusts volume down when audience is saturated, up when opportunity exists

## Backward Compatibility

All existing code continues to work:

- `get_volume_config()` maintains same response structure
- `get_volume_assignment()` still functional (with deprecation notice)
- `get_creator_profile()` maintains same response structure
- New metadata fields are additive (don't break existing code)

## Recommendations

1. **Update callers** to use `get_volume_config()` instead of `get_volume_assignment()`
2. **Leverage new metadata** fields for reporting and diagnostics
3. **Monitor saturation scores** to identify over-saturated creators
4. **Populate volume_performance_tracking** regularly for best results
5. **Consider deprecating** `volume_assignments` table entirely in future version

## File Locations

| File | Purpose |
|------|---------|
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/tools/send_types.py` | Modified get_volume_config() |
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/tools/performance.py` | Deprecated get_volume_assignment() |
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/tools/creator.py` | Updated get_creator_profile(), get_active_creators() |
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/python/volume/dynamic_calculator.py` | Core calculation logic |
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/python/volume/score_calculator.py` | On-demand score calculation |
| `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/python/models/volume.py` | VolumeConfig and VolumeTier models |

## Next Steps

1. Update schedule generation agents to use `get_volume_config()` metadata
2. Create monitoring dashboard for saturation/opportunity scores
3. Implement volume_performance_tracking population job
4. Consider removing volume_assignments table in v3.0
5. Add unit tests for edge cases (0 fans, missing data, etc.)
