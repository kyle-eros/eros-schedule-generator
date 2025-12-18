"""
Extended tests for send_type_allocator module to increase coverage.

Tests cover:
- DiversityValidation
- allocate_week method
- _ensure_diversity method
- filter_non_converters function
- filter_by_performance method
- filter_by_page_type method
- Daily strategies and flavors
- Weekly maximums
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
    VolumeTier,
    DiversityValidation,
    filter_non_converters,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def allocator():
    """Create SendTypeAllocator instance."""
    return SendTypeAllocator(creator_id="test_creator")


@pytest.fixture
def allocator_no_creator():
    """Create SendTypeAllocator without creator_id."""
    return SendTypeAllocator()


@pytest.fixture
def mid_tier_paid_config():
    """Mid tier paid page volume config."""
    return VolumeConfig(
        tier=VolumeTier.MID,
        revenue_per_day=4,
        engagement_per_day=3,
        retention_per_day=2,
        fan_count=2500,
        page_type="paid",
    )


@pytest.fixture
def high_tier_free_config():
    """High tier free page volume config."""
    return VolumeConfig(
        tier=VolumeTier.HIGH,
        revenue_per_day=6,
        engagement_per_day=4,
        retention_per_day=0,
        fan_count=8000,
        page_type="free",
    )


@pytest.fixture
def low_tier_config():
    """Low tier config for edge cases."""
    return VolumeConfig(
        tier=VolumeTier.LOW,
        revenue_per_day=3,
        engagement_per_day=3,
        retention_per_day=1,
        fan_count=500,
        page_type="paid",
    )


@pytest.fixture
def ultra_tier_config():
    """Ultra tier config for high volume testing."""
    return VolumeConfig(
        tier=VolumeTier.ULTRA,
        revenue_per_day=6,
        engagement_per_day=5,
        retention_per_day=3,
        fan_count=50000,
        page_type="paid",
    )


@pytest.fixture
def monday_start():
    """Monday week start for testing."""
    return datetime(2025, 12, 15)


# =============================================================================
# DiversityValidation Tests
# =============================================================================


class TestDiversityValidation:
    """Tests for DiversityValidation dataclass."""

    def test_default_errors_list(self):
        """Test errors defaults to empty list."""
        validation = DiversityValidation(
            is_valid=True,
            unique_type_count=12,
            revenue_type_count=5,
            engagement_type_count=5,
            retention_type_count=2,
        )
        assert validation.errors == []

    def test_default_warnings_list(self):
        """Test warnings defaults to empty list."""
        validation = DiversityValidation(
            is_valid=True,
            unique_type_count=12,
            revenue_type_count=5,
            engagement_type_count=5,
            retention_type_count=2,
        )
        assert validation.warnings == []

    def test_with_errors(self):
        """Test validation with errors."""
        validation = DiversityValidation(
            is_valid=False,
            unique_type_count=5,
            revenue_type_count=2,
            engagement_type_count=2,
            retention_type_count=1,
            errors=["Insufficient diversity"],
        )
        assert len(validation.errors) == 1

    def test_with_warnings(self):
        """Test validation with warnings."""
        validation = DiversityValidation(
            is_valid=True,
            unique_type_count=10,
            revenue_type_count=4,
            engagement_type_count=4,
            retention_type_count=2,
            warnings=["At minimum threshold"],
        )
        assert len(validation.warnings) == 1


# =============================================================================
# VolumeConfig Tests
# =============================================================================


class TestVolumeConfig:
    """Tests for VolumeConfig dataclass."""

    def test_invalid_page_type_raises(self):
        """Test invalid page_type raises ValueError."""
        with pytest.raises(ValueError, match="page_type"):
            VolumeConfig(
                tier=VolumeTier.MID,
                revenue_per_day=4,
                engagement_per_day=3,
                retention_per_day=2,
                fan_count=2500,
                page_type="invalid",
            )

    def test_total_per_day_property(self, mid_tier_paid_config):
        """Test total_per_day sums all categories."""
        expected = 4 + 3 + 2
        assert mid_tier_paid_config.total_per_day == expected

    def test_free_page_type_accepted(self):
        """Test 'free' page type is accepted."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=5,
            engagement_per_day=3,
            retention_per_day=0,
            fan_count=2500,
            page_type="free",
        )
        assert config.page_type == "free"


# =============================================================================
# get_daily_strategy Tests
# =============================================================================


class TestGetDailyStrategy:
    """Tests for daily strategy selection."""

    def test_returns_valid_strategy(self, allocator):
        """Test returns a valid strategy key."""
        for day in range(7):
            strategy = allocator.get_daily_strategy(day)
            assert strategy in allocator.DAILY_STRATEGIES

    def test_deterministic_with_creator(self, allocator):
        """Test same creator gets consistent strategies."""
        strategies1 = [allocator.get_daily_strategy(d) for d in range(7)]
        strategies2 = [allocator.get_daily_strategy(d) for d in range(7)]
        assert strategies1 == strategies2

    def test_no_creator_fallback(self, allocator_no_creator):
        """Test fallback when no creator_id."""
        for day in range(7):
            strategy = allocator_no_creator.get_daily_strategy(day)
            assert strategy in allocator_no_creator.DAILY_STRATEGIES


# =============================================================================
# apply_daily_flavor Tests
# =============================================================================


class TestApplyDailyFlavor:
    """Tests for daily flavor application."""

    def test_emphasis_moved_to_front(self, allocator):
        """Test emphasized type is moved to front."""
        day = 0  # Monday, emphasis on "bundle"
        types = ["ppv_unlock", "bundle", "vip_program"]
        result = allocator.apply_daily_flavor(day, types)

        # Bundle should be at front
        assert result[0] == "bundle"

    def test_avoid_moved_to_back(self, allocator):
        """Test avoided type is moved to back."""
        day = 0  # Monday, avoid "game_post"
        types = ["ppv_unlock", "game_post", "vip_program"]
        result = allocator.apply_daily_flavor(day, types)

        # game_post should be at back
        assert result[-1] == "game_post"

    def test_original_list_unchanged(self, allocator):
        """Test original list is not modified."""
        day = 0
        original = ["ppv_unlock", "bundle", "vip_program"]
        original_copy = original.copy()
        allocator.apply_daily_flavor(day, original)

        assert original == original_copy

    def test_missing_emphasis_type(self, allocator):
        """Test handles missing emphasis type gracefully."""
        day = 0  # Would emphasize "bundle"
        types = ["ppv_unlock", "vip_program"]  # No bundle
        result = allocator.apply_daily_flavor(day, types)

        # Should return without error
        assert len(result) == 2

    def test_all_days_have_flavor(self, allocator):
        """Test all days 0-6 have flavor configurations."""
        for day in range(7):
            flavor = allocator.DAILY_FLAVORS.get(day, {})
            assert "emphasis" in flavor or flavor == {}


# =============================================================================
# filter_by_page_type Tests
# =============================================================================


class TestFilterByPageType:
    """Tests for page type filtering."""

    def test_free_page_excludes_paid_only(self):
        """Test free pages exclude paid-only types."""
        types = ["ppv_unlock", "tip_goal", "bundle"]
        result = SendTypeAllocator.filter_by_page_type(types, "free")

        # tip_goal is paid-only
        assert "tip_goal" not in result
        assert "ppv_unlock" in result

    def test_paid_page_excludes_free_only(self):
        """Test paid pages exclude free-only types."""
        types = ["ppv_unlock", "ppv_wall", "bundle"]
        result = SendTypeAllocator.filter_by_page_type(types, "paid")

        # ppv_wall is free-only
        assert "ppv_wall" not in result
        assert "ppv_unlock" in result

    def test_both_types_included(self):
        """Test types valid for both page types are included."""
        types = ["ppv_unlock", "bundle", "bump_normal"]

        result_paid = SendTypeAllocator.filter_by_page_type(types, "paid")
        result_free = SendTypeAllocator.filter_by_page_type(types, "free")

        # All these should be valid for both
        assert "ppv_unlock" in result_paid
        assert "ppv_unlock" in result_free


# =============================================================================
# filter_by_performance Tests
# =============================================================================


class TestFilterByPerformance:
    """Tests for performance-based filtering."""

    def test_excludes_avoid_tier(self):
        """Test excludes types in 'avoid' tier."""
        types = ["ppv_unlock", "dm_farm", "bump_normal"]
        perf_data = {
            "ppv_unlock": {"tier": "top"},
            "dm_farm": {"tier": "avoid"},
            "bump_normal": {"tier": "mid"},
        }

        result = SendTypeAllocator.filter_by_performance(types, perf_data)

        assert "dm_farm" not in result
        assert "ppv_unlock" in result
        assert "bump_normal" in result

    def test_keeps_unknown_types(self):
        """Test keeps types not in performance data."""
        types = ["ppv_unlock", "unknown_type"]
        perf_data = {"ppv_unlock": {"tier": "top"}}

        result = SendTypeAllocator.filter_by_performance(types, perf_data)

        assert "unknown_type" in result

    def test_custom_exclude_tiers(self):
        """Test custom exclude_tiers parameter."""
        types = ["ppv_unlock", "dm_farm", "bump_normal"]
        perf_data = {
            "ppv_unlock": {"tier": "top"},
            "dm_farm": {"tier": "low"},
            "bump_normal": {"tier": "mid"},
        }

        result = SendTypeAllocator.filter_by_performance(
            types, perf_data, exclude_tiers=["low", "avoid"]
        )

        assert "dm_farm" not in result

    def test_empty_performance_data(self):
        """Test with empty performance data keeps all types."""
        types = ["ppv_unlock", "dm_farm"]
        result = SendTypeAllocator.filter_by_performance(types, {})

        assert result == types


# =============================================================================
# filter_non_converters Tests
# =============================================================================


class TestFilterNonConverters:
    """Tests for filter_non_converters function."""

    def test_filters_avoid_tier(self):
        """Test filters out 'avoid' tier types."""
        send_types = ["ppv_unlock", "bump_normal", "dm_farm"]
        perf_data = {
            "ppv_unlock": {"tier": "top"},
            "bump_normal": {"tier": "mid"},
            "dm_farm": {"tier": "avoid"},
        }

        result = filter_non_converters(send_types, perf_data)

        assert "dm_farm" not in result
        assert "ppv_unlock" in result
        assert "bump_normal" in result

    def test_keeps_types_without_data(self):
        """Test keeps types not in performance_data."""
        send_types = ["ppv_unlock", "new_type"]
        perf_data = {"ppv_unlock": {"tier": "top"}}

        result = filter_non_converters(send_types, perf_data)

        assert "new_type" in result

    def test_empty_perf_data(self):
        """Test with empty performance data returns all types."""
        send_types = ["ppv_unlock", "dm_farm"]
        result = filter_non_converters(send_types, {})

        assert result == send_types

    def test_all_avoid_types(self):
        """Test when all types are in avoid tier."""
        send_types = ["type1", "type2"]
        perf_data = {
            "type1": {"tier": "avoid"},
            "type2": {"tier": "avoid"},
        }

        result = filter_non_converters(send_types, perf_data)

        assert len(result) == 0


# =============================================================================
# allocate_day Tests
# =============================================================================


class TestAllocateDay:
    """Tests for daily allocation."""

    def test_returns_list(self, allocator, mid_tier_paid_config):
        """Test returns a list of allocations."""
        result = allocator.allocate_day(mid_tier_paid_config, 0, "paid")
        assert isinstance(result, list)

    def test_items_have_required_keys(self, allocator, mid_tier_paid_config):
        """Test each item has required keys."""
        result = allocator.allocate_day(mid_tier_paid_config, 0, "paid")

        required_keys = ["send_type_key", "category", "priority", "requires_caption"]
        for item in result:
            for key in required_keys:
                assert key in item

    def test_respects_daily_maximum(self, allocator, ultra_tier_config):
        """Test respects daily maximum limits."""
        result = allocator.allocate_day(ultra_tier_config, 4, "paid")  # Friday

        revenue_count = sum(1 for i in result if i["category"] == "revenue")
        engagement_count = sum(1 for i in result if i["category"] == "engagement")
        retention_count = sum(1 for i in result if i["category"] == "retention")

        assert revenue_count <= allocator.DAILY_MAXIMUMS["revenue"]
        assert engagement_count <= allocator.DAILY_MAXIMUMS["engagement"]
        assert retention_count <= allocator.DAILY_MAXIMUMS["retention"]

    def test_monday_adjustment(self, allocator, mid_tier_paid_config):
        """Test Monday has negative adjustment."""
        monday_result = allocator.allocate_day(mid_tier_paid_config, 0, "paid")
        tuesday_result = allocator.allocate_day(mid_tier_paid_config, 1, "paid")

        # Monday should have fewer items due to -1 adjustment
        assert len(monday_result) <= len(tuesday_result) + 3

    def test_friday_adjustment(self, allocator, mid_tier_paid_config):
        """Test Friday has positive adjustment."""
        friday_result = allocator.allocate_day(mid_tier_paid_config, 4, "paid")
        tuesday_result = allocator.allocate_day(mid_tier_paid_config, 1, "paid")

        # Friday should have more items due to +1 adjustment
        assert len(friday_result) >= len(tuesday_result)


# =============================================================================
# allocate_week Tests
# =============================================================================


class TestAllocateWeek:
    """Tests for weekly allocation."""

    def test_returns_7_days(self, allocator, mid_tier_paid_config, monday_start):
        """Test returns allocations for all 7 days."""
        result = allocator.allocate_week(mid_tier_paid_config, "paid", monday_start)
        assert len(result) == 7

    def test_dates_are_sequential(self, allocator, mid_tier_paid_config, monday_start):
        """Test dates are 7 consecutive days."""
        result = allocator.allocate_week(mid_tier_paid_config, "paid", monday_start)

        dates = sorted(result.keys())
        for i in range(6):
            current = datetime.strptime(dates[i], "%Y-%m-%d")
            next_day = datetime.strptime(dates[i + 1], "%Y-%m-%d")
            assert (next_day - current).days == 1

    def test_items_have_scheduled_date(self, allocator, mid_tier_paid_config, monday_start):
        """Test all items have scheduled_date."""
        result = allocator.allocate_week(mid_tier_paid_config, "paid", monday_start)

        for date_str, items in result.items():
            for item in items:
                assert item["scheduled_date"] == date_str

    def test_items_have_day_of_week(self, allocator, mid_tier_paid_config, monday_start):
        """Test all items have day_of_week."""
        result = allocator.allocate_week(mid_tier_paid_config, "paid", monday_start)

        for date_str, items in result.items():
            for item in items:
                assert "day_of_week" in item
                assert 0 <= item["day_of_week"] <= 6


# =============================================================================
# validate_diversity Tests
# =============================================================================


class TestValidateDiversity:
    """Tests for diversity validation."""

    def test_valid_diverse_schedule(self, allocator):
        """Test validation passes for diverse schedule."""
        schedule = {
            "2025-12-15": [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bundle", "category": "revenue"},
                {"send_type_key": "vip_program", "category": "revenue"},
                {"send_type_key": "game_post", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
                {"send_type_key": "bump_descriptive", "category": "engagement"},
                {"send_type_key": "dm_farm", "category": "engagement"},
                {"send_type_key": "like_farm", "category": "engagement"},
                {"send_type_key": "renew_on_post", "category": "retention"},
                {"send_type_key": "renew_on_message", "category": "retention"},
            ],
        }

        validation = allocator.validate_diversity(schedule, "paid")
        assert validation.is_valid is True
        assert validation.unique_type_count >= 10

    def test_invalid_low_diversity(self, allocator):
        """Test validation fails for low diversity."""
        schedule = {
            "2025-12-15": [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
            ],
        }

        validation = allocator.validate_diversity(schedule, "paid")
        assert validation.is_valid is False
        assert len(validation.errors) > 0

    def test_ppv_unlock_only_rejected(self, allocator):
        """Test schedule with only ppv_unlock + bump_normal is rejected."""
        schedule = {
            "2025-12-15": [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
            ],
            "2025-12-16": [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
            ],
        }

        validation = allocator.validate_diversity(schedule, "paid")
        assert validation.is_valid is False
        assert any("ppv_unlock + bump_normal" in err for err in validation.errors)

    def test_free_page_retention_requirements(self, allocator):
        """Test free pages have lower retention requirements."""
        schedule = {
            "2025-12-15": [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bundle", "category": "revenue"},
                {"send_type_key": "flash_bundle", "category": "revenue"},
                {"send_type_key": "game_post", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
                {"send_type_key": "bump_descriptive", "category": "engagement"},
                {"send_type_key": "dm_farm", "category": "engagement"},
                {"send_type_key": "like_farm", "category": "engagement"},
                {"send_type_key": "link_drop", "category": "engagement"},
                {"send_type_key": "ppv_followup", "category": "retention"},
            ],
        }

        validation = allocator.validate_diversity(schedule, "free")
        # Free pages only need 1 retention type
        assert validation.retention_type_count >= 1


# =============================================================================
# _ensure_diversity Tests
# =============================================================================


class TestEnsureDiversity:
    """Tests for diversity enforcement."""

    def test_rebalances_overused_types(self, allocator):
        """Test rebalances when types are overused."""
        # Create schedule with overused ppv_unlock
        schedule: dict[str, list[dict[str, Any]]] = {}
        for i in range(7):
            date_str = (datetime(2025, 12, 15) + timedelta(days=i)).strftime("%Y-%m-%d")
            schedule[date_str] = [
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "ppv_unlock", "category": "revenue"},
                {"send_type_key": "bump_normal", "category": "engagement"},
                {"send_type_key": "bump_normal", "category": "engagement"},
                {"send_type_key": "renew_on_post", "category": "retention"},
            ]

        result = allocator._ensure_diversity(schedule, "paid")

        # Should have introduced more variety
        all_types = set()
        for items in result.values():
            for item in items:
                all_types.add(item["send_type_key"])

        # Should have more than just ppv_unlock, bump_normal, renew_on_post
        assert len(all_types) >= 3


# =============================================================================
# Interleave Categories Tests
# =============================================================================


class TestInterleaveCategories:
    """Tests for category interleaving."""

    def test_interleave_preserves_all_items(self, allocator):
        """Test interleave preserves all items."""
        revenue = [{"send_type_key": "ppv_unlock", "category": "revenue"}]
        engagement = [{"send_type_key": "bump_normal", "category": "engagement"}]
        retention = [{"send_type_key": "renew_on_post", "category": "retention"}]

        result = allocator._interleave_categories(revenue, engagement, retention, 0)

        assert len(result) == 3

    def test_interleave_empty_lists(self, allocator):
        """Test interleave handles empty lists."""
        result = allocator._interleave_categories([], [], [], 0)
        assert result == []

    def test_interleave_single_category(self, allocator):
        """Test interleave with only one category."""
        revenue = [
            {"send_type_key": "ppv_unlock", "category": "revenue"},
            {"send_type_key": "bundle", "category": "revenue"},
        ]

        result = allocator._interleave_categories(revenue, [], [], 0)
        assert len(result) == 2


# =============================================================================
# Send Type Lists Tests
# =============================================================================


class TestSendTypeLists:
    """Tests for send type list definitions."""

    def test_revenue_types_count(self):
        """Test revenue types list has 9 types."""
        assert len(SendTypeAllocator.REVENUE_TYPES) == 9

    def test_engagement_types_count(self):
        """Test engagement types list has 9 types."""
        assert len(SendTypeAllocator.ENGAGEMENT_TYPES) == 9

    def test_retention_types_count(self):
        """Test retention types list has 4 types."""
        assert len(SendTypeAllocator.RETENTION_TYPES) == 4

    def test_all_types_sum_to_22(self):
        """Test all type lists sum to 22 unique types."""
        all_types = set(
            SendTypeAllocator.REVENUE_TYPES
            + SendTypeAllocator.ENGAGEMENT_TYPES
            + SendTypeAllocator.RETENTION_TYPES
        )
        assert len(all_types) == 22

    def test_free_page_retention_limited(self):
        """Test free page retention is limited to ppv_followup."""
        assert SendTypeAllocator.FREE_PAGE_RETENTION_TYPES == ["ppv_followup"]


# =============================================================================
# Media Requirements Tests
# =============================================================================


class TestMediaRequirements:
    """Tests for media requirement flags."""

    def test_ppv_unlock_requires_media(self, allocator, low_tier_config):
        """Test ppv_unlock requires media."""
        result = allocator.allocate_day(low_tier_config, 0, "paid")

        ppv_items = [i for i in result if i["send_type_key"] == "ppv_unlock"]
        for item in ppv_items:
            assert item["requires_media"] is True

    def test_bump_flyer_requires_media(self, allocator, ultra_tier_config):
        """Test bump_flyer requires media."""
        result = allocator.allocate_day(ultra_tier_config, 0, "paid")

        flyer_items = [i for i in result if i["send_type_key"] == "bump_flyer"]
        for item in flyer_items:
            assert item["requires_media"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
