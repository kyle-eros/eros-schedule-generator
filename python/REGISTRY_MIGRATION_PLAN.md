# Registry Migration Plan

## Overview

This document outlines the migration from hardcoded send type taxonomy lists to the centralized SendTypeRegistry. This migration improves maintainability, eliminates duplication, and ensures all code uses the canonical database configuration.

## Current Hardcoded Locations

### 1. python/allocation/send_type_allocator.py (Lines 101-129)

**Current Implementation:**
```python
# Send type pools by category (21 database send types)
REVENUE_TYPES = [
    "ppv_video",
    "vip_program",
    "game_post",
    "bundle",
    "flash_bundle",
    "snapchat_bundle",
    "first_to_tip"
]

ENGAGEMENT_TYPES = [
    "link_drop",
    "wall_link_drop",
    "bump_normal",
    "bump_descriptive",
    "bump_text_only",
    "bump_flyer",
    "dm_farm",
    "like_farm",
    "live_promo"
]

RETENTION_TYPES = [
    "renew_on_post",
    "renew_on_message",
    "ppv_message",
    "ppv_followup",
    "expired_winback"
]
```

**Replacement Strategy:**
```python
from python.registry import SendTypeRegistry

class SendTypeAllocator:
    def __init__(self, registry: SendTypeRegistry | None = None):
        """Initialize allocator with send type registry.

        Args:
            registry: Optional pre-loaded registry (uses singleton if None)
        """
        self._registry = registry or SendTypeRegistry()

    def _allocate_revenue(self, count: int, page_type: str, day_of_week: int):
        """Allocate revenue-focused send types."""
        revenue_keys = self._registry.get_keys_by_category("revenue")

        # Filter by page type compatibility
        compatible_types = [
            key for key in revenue_keys
            if self._is_page_compatible(key, page_type)
        ]

        # Allocate from compatible types
        for i in range(count):
            send_type = compatible_types[i % len(compatible_types)]
            # ... rest of logic
```

**Benefits:**
- Dynamic loading from database
- Automatic page type filtering
- Single source of truth
- No manual list maintenance

### 2. python/optimization/schedule_optimizer.py (Lines 121-276)

**Current Implementation:**
```python
# Timing preferences by send type - 21 database send types
TIMING_PREFERENCES: dict[str, dict[str, Any]] = {
    "ppv_video": {
        "preferred_hours": [19, 21],
        "preferred_days": [4, 5, 6],
        "avoid_hours": [3, 4, 5, 6, 7, 8],
        "min_spacing": 90,
        "boost": 1.3,
    },
    # ... 20 more entries
}
```

**Replacement Strategy:**
```python
from python.registry import SendTypeRegistry

class ScheduleOptimizer:
    def __init__(self, registry: SendTypeRegistry | None = None):
        """Initialize optimizer with send type registry.

        Args:
            registry: Optional pre-loaded registry (uses singleton if None)
        """
        self._registry = registry or SendTypeRegistry()
        self._assigned_times: dict[str, list[time]] = {}

    def assign_time_slot(
        self,
        item: ScheduleItem,
        available_slots: list[time],
        timing_data: dict[int, list[int]] | None = None
    ) -> time | None:
        """Assign optimal time slot for item."""
        if not available_slots:
            return None

        # Get timing preferences from registry
        preferences = self._registry.get_timing_preferences(item.send_type_key)

        # Rest of logic remains the same
        scored_slots = []
        date_obj = datetime.strptime(item.scheduled_date, "%Y-%m-%d")
        day_of_week = date_obj.weekday()

        for slot in available_slots:
            score = self.calculate_slot_score(
                slot.hour,
                day_of_week,
                item.send_type_key,
                preferences,
                timing_data
            )
            scored_slots.append((slot, score))

        # ... rest unchanged
```

**Benefits:**
- Centralized timing configuration
- Database-driven preferences
- Easier A/B testing of timing strategies
- No code changes for timing adjustments

## Migration Steps

### Phase 1: Backward Compatible Integration (Completed)
- ✅ Create domain models package (python/models/)
- ✅ Create registry package (python/registry/)
- ✅ Implement SendTypeRegistry singleton
- ✅ Add database loading methods

### Phase 2: Update Allocator (Next Wave)
1. Add registry parameter to SendTypeAllocator.__init__()
2. Replace REVENUE_TYPES with registry.get_keys_by_category("revenue")
3. Replace ENGAGEMENT_TYPES with registry.get_keys_by_category("engagement")
4. Replace RETENTION_TYPES with registry.get_keys_by_category("retention")
5. Add page type compatibility filtering
6. Update unit tests to inject mock registry

### Phase 3: Update Optimizer (Next Wave)
1. Add registry parameter to ScheduleOptimizer.__init__()
2. Replace TIMING_PREFERENCES lookups with registry.get_timing_preferences()
3. Remove hardcoded TIMING_PREFERENCES dictionary
4. Update unit tests to inject mock registry

### Phase 4: Update Other Modules (Next Wave)
1. Search for other hardcoded send type references
2. Update python/matching/caption_matcher.py if needed
3. Update validation logic in python/validators.py
4. Update any documentation with hardcoded lists

### Phase 5: Database Schema Enhancement (Future)
1. Create timing_preferences table in database
2. Migrate hardcoded timing data to database
3. Update registry to load timing from database
4. Remove fallback timing logic

## Testing Strategy

### Unit Tests
```python
def test_allocator_with_registry():
    """Test allocator uses registry for send types."""
    # Create mock registry
    mock_registry = Mock(spec=SendTypeRegistry)
    mock_registry.get_keys_by_category.return_value = ["ppv_video", "bundle"]

    # Inject into allocator
    allocator = SendTypeAllocator(registry=mock_registry)

    # Verify registry is used
    result = allocator._allocate_revenue(2, "paid", 4)
    mock_registry.get_keys_by_category.assert_called_with("revenue")
```

### Integration Tests
```python
def test_full_pipeline_with_registry():
    """Test complete schedule generation with registry."""
    # Load registry from test database
    conn = sqlite3.connect(":memory:")
    setup_test_schema(conn)

    registry = SendTypeRegistry()
    registry.load_from_database(conn)

    # Create pipeline components with registry
    allocator = SendTypeAllocator(registry=registry)
    optimizer = ScheduleOptimizer(registry=registry)

    # Run full pipeline
    schedule = generate_schedule(allocator, optimizer)

    # Verify all send types are valid
    for item in schedule:
        assert registry.is_valid_key(item.send_type_key)
```

## Rollback Plan

If issues arise during migration:

1. **Immediate Rollback**: Keep original class constants as fallbacks
```python
def _get_revenue_types(self) -> list[str]:
    """Get revenue send types (registry-first with fallback)."""
    if self._registry:
        try:
            return self._registry.get_keys_by_category("revenue")
        except Exception as e:
            logger.warning(f"Registry lookup failed: {e}, using fallback")

    # Fallback to hardcoded list
    return ["ppv_video", "vip_program", "game_post", ...]
```

2. **Feature Flag**: Add environment variable to control registry usage
```python
USE_SEND_TYPE_REGISTRY = os.getenv("USE_SEND_TYPE_REGISTRY", "true").lower() == "true"

if USE_SEND_TYPE_REGISTRY:
    revenue_types = registry.get_keys_by_category("revenue")
else:
    revenue_types = self.REVENUE_TYPES  # Hardcoded fallback
```

## Success Metrics

- ✅ Zero hardcoded send type lists in production code
- ✅ All send types loaded from database
- ✅ 100% test coverage for registry integration
- ✅ No performance degradation (registry caches data)
- ✅ Backward compatible during migration

## Timeline

- **Wave 3** (Current): Registry implementation and documentation
- **Wave 4**: Allocator migration
- **Wave 5**: Optimizer migration
- **Wave 6**: Cleanup and hardcoded list removal

## Related Files

- `/python/models/send_type.py` - Domain models
- `/python/registry/send_type_registry.py` - Registry implementation
- `/python/allocation/send_type_allocator.py` - Allocator to migrate
- `/python/optimization/schedule_optimizer.py` - Optimizer to migrate
- `/database/migrations/008_send_types_foundation.sql` - Database schema
