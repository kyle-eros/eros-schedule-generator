# Deprecation Guide

This guide tracks deprecated features and provides migration paths for the EROS Schedule Generator.

**Version**: 2.2.0 | **Last Updated**: 2025-12-17

---

## Table of Contents

1. [ppv_message → ppv_unlock](#ppv_message--ppv_unlock-v210)
2. [get_volume_assignment → get_volume_config](#get_volume_assignment--get_volume_config-v220)

---

## ppv_message → ppv_unlock (v2.1.0)

**Deprecated**: 2025-12-16
**Removal Date**: 2025-01-16
**Replacement**: Use `ppv_unlock` for all PPV sends (both video and message)

### Why Deprecated?

The `ppv_message` send type was merged into `ppv_unlock` to simplify the 22-type taxonomy. The `ppv_unlock` type now handles both video unlocks and message-based PPV, as they share identical requirements and behavior.

### Migration Steps

1. **Update Schedule Generation Calls**
   ```python
   # Before
   send_type_key = "ppv_message"

   # After
   send_type_key = "ppv_unlock"
   ```

2. **Update Hardcoded References**
   - Search your codebase for `"ppv_message"` strings
   - Replace with `"ppv_unlock"`

3. **Database Migration** (Automatic)
   - No action required - system automatically resolves `ppv_message` → `ppv_unlock`
   - `SEND_TYPE_ALIASES` mapping handles backward compatibility

### Backward Compatibility

**During transition period (2025-12-16 to 2025-01-16)**:
- ✅ Both `ppv_message` and `ppv_unlock` work
- ✅ `ppv_message` automatically resolves to `ppv_unlock`
- ✅ No database migration required
- ✅ Existing schedules continue to function

**After 2025-01-16**:
- ❌ `ppv_message` will no longer be recognized
- ❌ Schedules using `ppv_message` will fail validation
- ⚠️ Complete migration before this date

### Testing Your Migration

```python
from python.models.send_type import resolve_send_type_key

# Verify resolution works
result = resolve_send_type_key("ppv_message")
assert result == "ppv_unlock", "Migration not working"
```

---

## get_volume_assignment → get_volume_config (v2.2.0)

**Deprecated**: 2025-12-15 (Wave 3)
**Removal Date**: v3.0.0
**Replacement**: Use `get_volume_config` for dynamic volume calculation

### Why Deprecated?

`get_volume_assignment` returned static volume assignments. `get_volume_config` provides dynamic calculation with:
- **Multi-horizon fusion** (7d/14d/30d trends)
- **Confidence dampening** for new creators
- **Day-of-week distribution** (DOW multipliers)
- **Elasticity bounds** (diminishing returns modeling)
- **Content type weighting** (performance-based allocation)
- **Caption pool validation** (ensures sufficient captions)

### Migration Steps

1. **Update MCP Tool Calls**
   ```python
   # Before
   result = get_volume_assignment(creator_id)
   volume_level = result["volume_level"]
   ppv_per_day = result["ppv_per_day"]

   # After
   result = get_volume_config(creator_id)
   volume_level = result["volume_level"]  # Backward compatible
   revenue_per_day = result["revenue_per_day"]  # New detailed breakdown
   ```

2. **Access New Features**
   ```python
   config = get_volume_config(creator_id)

   # Access category-specific limits
   revenue_sends = config["revenue_per_day"]
   engagement_sends = config["engagement_per_day"]
   retention_sends = config["retention_per_day"]

   # Access DOW distribution
   monday_sends = config["weekly_distribution"][0]
   tuesday_sends = config["weekly_distribution"][1]
   # ... day 0-6 mapping

   # Check optimization metadata
   confidence = config["confidence_score"]
   elasticity_capped = config["elasticity_capped"]
   caption_warnings = config["caption_warnings"]
   ```

### Backward Compatibility

`get_volume_assignment` remains functional but:
- Returns deprecation warning in response
- Logs deprecation notice to server
- Will be removed in v3.0.0

### Testing Your Migration

```bash
# MCP tool call should work
mcp__eros-db__get_volume_config(creator_id="alexia")

# Should return OptimizedVolumeResult with all new fields
```

### OptimizedVolumeResult Structure

The new `get_volume_config` returns:

```python
{
  # Legacy fields (backward compatible)
  "volume_level": "MID",
  "ppv_per_day": 2,
  "bump_per_day": 4,

  # Category volumes (new)
  "revenue_per_day": 3,
  "engagement_per_day": 5,
  "retention_per_day": 1,

  # Weekly distribution (new)
  "weekly_distribution": [8, 9, 8, 7, 9, 8, 7],  # Mon-Sun

  # Content strategy (new)
  "content_allocations": {
    "photo": 0.45,
    "video": 0.35,
    "text": 0.20
  },

  # Optimization metadata (new)
  "confidence_score": 0.85,
  "elasticity_capped": false,
  "caption_warnings": [],
  "fused_saturation": 0.42,
  "fused_opportunity": 0.68,
  "divergence_detected": false,
  "dow_multipliers_used": true,
  "prediction_id": "pred_123456",
  "message_count": 71998,
  "adjustments_applied": ["confidence_dampening", "dow_distribution"]
}
```

---

## Migration Support

For questions or issues during migration:
1. Check the [API Reference](API_REFERENCE.md) for updated tool documentation
2. Review [CHANGELOG.md](../CHANGELOG.md) for detailed version history
3. Consult [CLAUDE.md](../CLAUDE.md) for current system capabilities

---

*Version 2.2.0 | Last Updated: 2025-12-17*
