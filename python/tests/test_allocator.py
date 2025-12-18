"""
Unit tests for SendTypeAllocator.

Tests volume tier calculation, daily allocation logic,
weekly distribution, and category constraints.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
    VolumeTier,
)


class TestVolumeTierCalculation:
    """Tests for volume tier classification."""

    def test_get_volume_tier_zero_fans(self):
        """Test tier for zero fans."""
        assert SendTypeAllocator.get_volume_tier(0) == VolumeTier.LOW

    def test_get_volume_tier_low_boundary_lower(self):
        """Test LOW tier lower boundary (0)."""
        assert SendTypeAllocator.get_volume_tier(0) == VolumeTier.LOW

    def test_get_volume_tier_low_boundary_upper(self):
        """Test LOW tier upper boundary (999)."""
        assert SendTypeAllocator.get_volume_tier(999) == VolumeTier.LOW

    def test_get_volume_tier_mid_boundary_lower(self):
        """Test MID tier lower boundary (1000)."""
        assert SendTypeAllocator.get_volume_tier(1000) == VolumeTier.MID

    def test_get_volume_tier_mid_boundary_upper(self):
        """Test MID tier upper boundary (4999)."""
        assert SendTypeAllocator.get_volume_tier(4999) == VolumeTier.MID

    def test_get_volume_tier_high_boundary_lower(self):
        """Test HIGH tier lower boundary (5000)."""
        assert SendTypeAllocator.get_volume_tier(5000) == VolumeTier.HIGH

    def test_get_volume_tier_high_boundary_upper(self):
        """Test HIGH tier upper boundary (14999)."""
        assert SendTypeAllocator.get_volume_tier(14999) == VolumeTier.HIGH

    def test_get_volume_tier_ultra_boundary_lower(self):
        """Test ULTRA tier lower boundary (15000)."""
        assert SendTypeAllocator.get_volume_tier(15000) == VolumeTier.ULTRA

    def test_get_volume_tier_ultra_very_high(self):
        """Test ULTRA tier with very high fan count."""
        assert SendTypeAllocator.get_volume_tier(1000000) == VolumeTier.ULTRA

    @pytest.mark.parametrize("fan_count,expected_tier", [
        (0, VolumeTier.LOW),
        (500, VolumeTier.LOW),
        (999, VolumeTier.LOW),
        (1000, VolumeTier.MID),
        (2500, VolumeTier.MID),
        (4999, VolumeTier.MID),
        (5000, VolumeTier.HIGH),
        (10000, VolumeTier.HIGH),
        (14999, VolumeTier.HIGH),
        (15000, VolumeTier.ULTRA),
        (50000, VolumeTier.ULTRA),
    ])
    def test_get_volume_tier_parametrized(self, fan_count: int, expected_tier: VolumeTier):
        """Parametrized test for volume tier boundaries."""
        assert SendTypeAllocator.get_volume_tier(fan_count) == expected_tier


class TestTierConfigurations:
    """Tests for tier configuration structures."""

    def test_all_tiers_have_configs(self):
        """Test that all VolumeTier values have configurations."""
        allocator = SendTypeAllocator()
        for tier in VolumeTier:
            assert tier in allocator.TIER_CONFIGS

    def test_tier_configs_have_paid_and_free(self):
        """Test tier configs include both page types."""
        allocator = SendTypeAllocator()
        for tier in VolumeTier:
            config = allocator.TIER_CONFIGS[tier]
            assert "paid" in config
            assert "free" in config

    def test_tier_configs_have_all_categories(self):
        """Test tier configs include all category counts."""
        allocator = SendTypeAllocator()
        for tier in VolumeTier:
            for page_type in ["paid", "free"]:
                config = allocator.TIER_CONFIGS[tier][page_type]
                assert "revenue" in config
                assert "engagement" in config
                assert "retention" in config

    def test_tier_configs_volumes_increase(self):
        """Test that volumes increase with tier."""
        allocator = SendTypeAllocator()

        low_total = sum(allocator.TIER_CONFIGS[VolumeTier.LOW]["paid"].values())
        mid_total = sum(allocator.TIER_CONFIGS[VolumeTier.MID]["paid"].values())
        high_total = sum(allocator.TIER_CONFIGS[VolumeTier.HIGH]["paid"].values())
        ultra_total = sum(allocator.TIER_CONFIGS[VolumeTier.ULTRA]["paid"].values())

        assert low_total <= mid_total <= high_total <= ultra_total


class TestDailyAllocation:
    """Tests for daily allocation logic."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        """Fresh allocator instance."""
        return SendTypeAllocator()

    def test_allocate_day_returns_list(self, allocator, sample_volume_config):
        """Test allocate_day returns list of items."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,
            page_type="paid",
        )
        assert isinstance(result, list)

    def test_allocate_day_items_have_required_keys(self, allocator, sample_volume_config):
        """Test each item has required keys."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,
            page_type="paid",
        )

        required_keys = {"send_type_key", "category", "priority", "requires_caption", "requires_media"}
        for item in result:
            assert required_keys.issubset(item.keys())

    def test_allocate_day_categories_correct(self, allocator, sample_volume_config):
        """Test items have valid categories."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,
            page_type="paid",
        )

        valid_categories = {"revenue", "engagement", "retention"}
        for item in result:
            assert item["category"] in valid_categories

    def test_allocate_day_monday_adjustment(self, allocator, sample_volume_config):
        """Test Monday has reduced volume (day adjustment -1)."""
        monday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=0,  # Monday
            page_type="paid",
        )

        wednesday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,  # Wednesday (no adjustment)
            page_type="paid",
        )

        # Monday should have fewer or equal items
        assert len(monday_result) <= len(wednesday_result)

    def test_allocate_day_friday_adjustment(self, allocator, sample_volume_config):
        """Test Friday has increased volume (day adjustment +1)."""
        friday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=4,  # Friday
            page_type="paid",
        )

        wednesday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,  # Wednesday
            page_type="paid",
        )

        # Friday should have more or equal items
        assert len(friday_result) >= len(wednesday_result)

    def test_allocate_day_saturday_adjustment(self, allocator, sample_volume_config):
        """Test Saturday has increased volume (day adjustment +1)."""
        saturday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=5,  # Saturday
            page_type="paid",
        )

        wednesday_result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,  # Wednesday
            page_type="paid",
        )

        assert len(saturday_result) >= len(wednesday_result)


class TestDailyMaximums:
    """Tests for daily maximum constraints."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_revenue_daily_maximum(self, allocator):
        """Test revenue daily maximum is enforced."""
        assert allocator.DAILY_MAXIMUMS["revenue"] == 8

    def test_engagement_daily_maximum(self, allocator):
        """Test engagement daily maximum is enforced."""
        assert allocator.DAILY_MAXIMUMS["engagement"] == 6

    def test_retention_daily_maximum(self, allocator):
        """Test retention daily maximum is enforced."""
        assert allocator.DAILY_MAXIMUMS["retention"] == 4

    def test_allocate_day_respects_revenue_max(self, allocator):
        """Test allocation does not exceed revenue maximum."""
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=20,  # Way above max
            engagement_per_day=6,
            retention_per_day=3,
            fan_count=50000,
            page_type="paid",
        )

        result = allocator.allocate_day(config, day_of_week=5, page_type="paid")
        revenue_count = sum(1 for item in result if item["category"] == "revenue")

        assert revenue_count <= allocator.DAILY_MAXIMUMS["revenue"]

    def test_allocate_day_respects_engagement_max(self, allocator):
        """Test allocation does not exceed engagement maximum."""
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=6,
            engagement_per_day=20,  # Way above max
            retention_per_day=3,
            fan_count=50000,
            page_type="paid",
        )

        result = allocator.allocate_day(config, day_of_week=5, page_type="paid")
        engagement_count = sum(1 for item in result if item["category"] == "engagement")

        assert engagement_count <= allocator.DAILY_MAXIMUMS["engagement"]

    def test_allocate_day_respects_retention_max(self, allocator):
        """Test allocation does not exceed retention maximum."""
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=6,
            engagement_per_day=5,
            retention_per_day=20,  # Way above max
            fan_count=50000,
            page_type="paid",
        )

        result = allocator.allocate_day(config, day_of_week=5, page_type="paid")
        retention_count = sum(1 for item in result if item["category"] == "retention")

        assert retention_count <= allocator.DAILY_MAXIMUMS["retention"]


class TestWeeklyDistribution:
    """Tests for weekly allocation distribution."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_allocate_week_returns_7_days(self, allocator, sample_volume_config):
        """Test weekly allocation returns 7 days."""
        week_start = datetime(2025, 12, 15)  # Monday
        result = allocator.allocate_week(
            config=sample_volume_config,
            page_type="paid",
            week_start=week_start,
        )

        assert len(result) == 7

    def test_allocate_week_dates_sequential(self, allocator, sample_volume_config):
        """Test weekly dates are sequential."""
        week_start = datetime(2025, 12, 15)
        result = allocator.allocate_week(
            config=sample_volume_config,
            page_type="paid",
            week_start=week_start,
        )

        dates = sorted(result.keys())
        for i in range(len(dates) - 1):
            current = datetime.strptime(dates[i], "%Y-%m-%d")
            next_date = datetime.strptime(dates[i + 1], "%Y-%m-%d")
            assert (next_date - current).days == 1

    def test_allocate_week_items_have_dates(self, allocator, sample_volume_config):
        """Test items have scheduled_date populated."""
        week_start = datetime(2025, 12, 15)
        result = allocator.allocate_week(
            config=sample_volume_config,
            page_type="paid",
            week_start=week_start,
        )

        for date_str, items in result.items():
            for item in items:
                assert item["scheduled_date"] == date_str

    def test_allocate_week_items_have_day_of_week(self, allocator, sample_volume_config):
        """Test items have day_of_week populated."""
        week_start = datetime(2025, 12, 15)
        result = allocator.allocate_week(
            config=sample_volume_config,
            page_type="paid",
            week_start=week_start,
        )

        for date_str, items in result.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            expected_dow = date_obj.weekday()
            for item in items:
                assert item["day_of_week"] == expected_dow


class TestCategoryInterleaving:
    """Tests for category interleaving logic."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_interleave_empty_lists(self, allocator):
        """Test interleaving with empty lists."""
        result = allocator._interleave_categories([], [], [])
        assert result == []

    def test_interleave_single_category(self, allocator):
        """Test interleaving with only one category."""
        revenue = [{"category": "revenue", "send_type_key": "ppv_unlock"}]
        result = allocator._interleave_categories(revenue, [], [])
        assert len(result) == 1
        assert result[0]["category"] == "revenue"

    def test_interleave_two_categories(self, allocator):
        """Test interleaving with two categories."""
        revenue = [{"category": "revenue", "send_type_key": "ppv_unlock"}]
        engagement = [{"category": "engagement", "send_type_key": "bump_normal"}]
        result = allocator._interleave_categories(revenue, engagement, [])

        assert len(result) == 2
        # Should alternate
        assert result[0]["category"] == "revenue"
        assert result[1]["category"] == "engagement"

    def test_interleave_all_categories(self, allocator):
        """Test interleaving with all three categories."""
        revenue = [
            {"category": "revenue", "send_type_key": "ppv_unlock"},
            {"category": "revenue", "send_type_key": "bundle"},
        ]
        engagement = [
            {"category": "engagement", "send_type_key": "bump_normal"},
            {"category": "engagement", "send_type_key": "dm_farm"},
        ]
        retention = [
            {"category": "retention", "send_type_key": "renew_on_post"},
        ]

        result = allocator._interleave_categories(revenue, engagement, retention)

        assert len(result) == 5
        # All categories should be represented in the result
        categories_in_result = {item["category"] for item in result}
        assert "revenue" in categories_in_result
        assert "engagement" in categories_in_result
        assert "retention" in categories_in_result
        # No more than 2 consecutive same category (prevents clustering)
        for i in range(len(result) - 2):
            cats = [result[i]["category"], result[i + 1]["category"], result[i + 2]["category"]]
            # All three should not be the same
            assert len(set(cats)) >= 2

    def test_interleave_prevents_clustering(self, allocator, sample_volume_config):
        """Test that interleaving prevents same-category clustering."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=5,  # Saturday
            page_type="paid",
        )

        # Check no more than 2 consecutive same category
        for i in range(len(result) - 2):
            categories = [result[i]["category"], result[i + 1]["category"], result[i + 2]["category"]]
            # All three should not be the same
            if len(result) >= 3:
                assert len(set(categories)) >= 2 or len(result) < 3


class TestSendTypeCategories:
    """Tests for send type category definitions."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_revenue_types_free_count(self, allocator):
        """Test FREE page revenue types list has 8 types (includes ppv_wall)."""
        assert len(allocator.REVENUE_TYPES_FREE) == 8

    def test_revenue_types_paid_count(self, allocator):
        """Test PAID page revenue types list has 8 types (includes tip_goal)."""
        assert len(allocator.REVENUE_TYPES_PAID) == 8

    def test_engagement_types_count(self, allocator):
        """Test engagement types list has 9 types."""
        assert len(allocator.ENGAGEMENT_TYPES) == 9

    def test_retention_types_count(self, allocator):
        """Test retention types list has 4 types."""
        assert len(allocator.RETENTION_TYPES) == 4

    def test_all_22_types_covered(self, allocator):
        """Test all 22 types are accounted for (9 revenue + 9 engagement + 4 retention)."""
        # 9 unique revenue types: ppv_unlock, ppv_wall (free), tip_goal (paid),
        # vip_program, game_post, bundle, flash_bundle, snapchat_bundle, first_to_tip
        # ppv_wall and tip_goal are mutually exclusive by page type
        # So each page type sees 8 revenue types
        total_types = (
            8 +  # Revenue types per page (8 each, with 1 unique per page type = 9 total unique)
            len(allocator.ENGAGEMENT_TYPES) +
            len(allocator.RETENTION_TYPES) +
            1  # +1 for the page-type-specific revenue type not in the count
        )
        assert total_types == 22

    def test_revenue_types_include_ppv_unlock(self, allocator):
        """Test ppv_unlock is in both revenue type lists."""
        assert "ppv_unlock" in allocator.REVENUE_TYPES_FREE
        assert "ppv_unlock" in allocator.REVENUE_TYPES_PAID

    def test_ppv_wall_only_in_free(self, allocator):
        """Test ppv_wall is only in FREE page revenue types."""
        assert "ppv_wall" in allocator.REVENUE_TYPES_FREE
        assert "ppv_wall" not in allocator.REVENUE_TYPES_PAID

    def test_tip_goal_only_in_paid(self, allocator):
        """Test tip_goal is only in PAID page revenue types."""
        assert "tip_goal" in allocator.REVENUE_TYPES_PAID
        assert "tip_goal" not in allocator.REVENUE_TYPES_FREE

    def test_engagement_types_include_bump_normal(self, allocator):
        """Test bump_normal is in engagement types."""
        assert "bump_normal" in allocator.ENGAGEMENT_TYPES

    def test_retention_types_include_renew_on_post(self, allocator):
        """Test renew_on_post is in retention types."""
        assert "renew_on_post" in allocator.RETENTION_TYPES

    def test_get_revenue_types_for_page_free(self, allocator):
        """Test get_revenue_types_for_page returns correct types for FREE pages."""
        free_types = allocator.get_revenue_types_for_page("free")
        assert "ppv_wall" in free_types
        assert "tip_goal" not in free_types

    def test_get_revenue_types_for_page_paid(self, allocator):
        """Test get_revenue_types_for_page returns correct types for PAID pages."""
        paid_types = allocator.get_revenue_types_for_page("paid")
        assert "tip_goal" in paid_types
        assert "ppv_wall" not in paid_types


class TestMediaRequirements:
    """Tests for media requirement assignment."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_ppv_unlock_requires_media(self, allocator, sample_volume_config):
        """Test ppv_unlock requires media."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,
            page_type="paid",
        )

        ppv_items = [item for item in result if item["send_type_key"] == "ppv_unlock"]
        for item in ppv_items:
            assert item["requires_media"] is True

    def test_bundle_requires_media(self, allocator, sample_volume_config):
        """Test bundle requires media."""
        result = allocator.allocate_day(
            config=sample_volume_config,
            day_of_week=2,
            page_type="paid",
        )

        bundle_items = [item for item in result if item["send_type_key"] == "bundle"]
        for item in bundle_items:
            assert item["requires_media"] is True


class TestWeeklyMaximums:
    """Tests for weekly maximum constraints."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_weekly_revenue_maximum(self, allocator):
        """Test weekly revenue maximum is defined."""
        assert allocator.WEEKLY_MAXIMUMS["revenue"] == 45

    def test_weekly_engagement_maximum(self, allocator):
        """Test weekly engagement maximum is defined."""
        assert allocator.WEEKLY_MAXIMUMS["engagement"] == 35

    def test_weekly_retention_maximum(self, allocator):
        """Test weekly retention maximum is defined."""
        assert allocator.WEEKLY_MAXIMUMS["retention"] == 20


class TestEdgeCases:
    """Edge case tests for allocator."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator()

    def test_allocate_day_with_zero_counts(self, allocator):
        """Test allocation with zero volume counts."""
        config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=0,
            engagement_per_day=0,
            retention_per_day=0,
            fan_count=100,
            page_type="paid",
        )

        result = allocator.allocate_day(config, day_of_week=2, page_type="paid")
        assert result == []

    def test_allocate_day_with_only_revenue(self, allocator):
        """Test allocation with only revenue volume."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=3,
            engagement_per_day=0,
            retention_per_day=0,
            fan_count=2500,
            page_type="paid",
        )

        result = allocator.allocate_day(config, day_of_week=2, page_type="paid")
        assert all(item["category"] == "revenue" for item in result)

    def test_volume_config_total_per_day(self, sample_volume_config):
        """Test VolumeConfig total_per_day property."""
        expected = (
            sample_volume_config.revenue_per_day +
            sample_volume_config.engagement_per_day +
            sample_volume_config.retention_per_day
        )
        assert sample_volume_config.total_per_day == expected
