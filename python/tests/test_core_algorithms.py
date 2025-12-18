"""
Tests for EROS Schedule Generator Core Algorithms.

Run with: python -m pytest python/tests/test_core_algorithms.py -v
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
    VolumeTier,
    VolumeConfig,
)
from python.matching.caption_matcher import (
    CaptionMatcher,
    Caption,
    CaptionScore,
)
from python.optimization.schedule_optimizer import (
    ScheduleOptimizer,
    ScheduleItem,
)


class TestSendTypeAllocator:
    """Tests for SendTypeAllocator."""

    def test_get_volume_tier_low(self):
        """Test LOW tier classification."""
        assert SendTypeAllocator.get_volume_tier(500) == VolumeTier.LOW
        assert SendTypeAllocator.get_volume_tier(999) == VolumeTier.LOW

    def test_get_volume_tier_mid(self):
        """Test MID tier classification."""
        assert SendTypeAllocator.get_volume_tier(1000) == VolumeTier.MID
        assert SendTypeAllocator.get_volume_tier(4999) == VolumeTier.MID

    def test_get_volume_tier_high(self):
        """Test HIGH tier classification."""
        assert SendTypeAllocator.get_volume_tier(5000) == VolumeTier.HIGH
        assert SendTypeAllocator.get_volume_tier(14999) == VolumeTier.HIGH

    def test_get_volume_tier_ultra(self):
        """Test ULTRA tier classification."""
        assert SendTypeAllocator.get_volume_tier(15000) == VolumeTier.ULTRA
        assert SendTypeAllocator.get_volume_tier(100000) == VolumeTier.ULTRA

    def test_tier_configs_exist(self):
        """Test all tier configs are defined."""
        allocator = SendTypeAllocator()
        for tier in VolumeTier:
            assert tier in allocator.TIER_CONFIGS

    def test_allocate_day_returns_items(self):
        """Test daily allocation returns items."""
        allocator = SendTypeAllocator()
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = allocator.allocate_day(
            config=config,
            day_of_week=2,  # Wednesday
            page_type="paid",
        )

        assert result is not None
        assert len(result) > 0
        # Verify items have required structure
        assert all("send_type_key" in item for item in result)
        assert all("category" in item for item in result)

    def test_allocate_week_returns_7_days(self):
        """Test weekly allocation returns all 7 days."""
        allocator = SendTypeAllocator()
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        week_start = datetime(2025, 1, 20)
        weekly = allocator.allocate_week(
            config=config,
            page_type="paid",
            week_start=week_start,
        )

        assert len(weekly) == 7

    def test_interleave_categories(self):
        """Test interleaving prevents category clustering."""
        allocator = SendTypeAllocator()

        revenue_items = [
            {"send_type_key": "ppv_video", "category": "revenue"},
            {"send_type_key": "bundle", "category": "revenue"},
        ]
        engagement_items = [
            {"send_type_key": "bump_normal", "category": "engagement"},
            {"send_type_key": "dm_farm", "category": "engagement"},
        ]
        retention_items = [
            {"send_type_key": "renew_on_post", "category": "retention"},
        ]

        result = allocator._interleave_categories(
            revenue_items,
            engagement_items,
            retention_items,
        )

        # Should not have more than 2 consecutive same category
        for i in range(2, len(result)):
            categories = [result[j]["category"] for j in range(i - 2, i + 1)]
            assert len(set(categories)) > 1 or len(categories) <= 2

    def test_daily_maximums_enforced(self):
        """Test daily maximum limits are enforced."""
        allocator = SendTypeAllocator()
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=20,  # Exceeds max of 8
            engagement_per_day=10,  # Exceeds max of 6
            retention_per_day=8,  # Exceeds max of 4
            fan_count=50000,
            page_type="paid",
        )

        result = allocator.allocate_day(
            config=config,
            day_of_week=5,  # Saturday (peak day)
            page_type="paid",
        )

        # Count by category
        category_counts = {}
        for item in result:
            cat = item["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Verify maximums are respected
        assert category_counts.get("revenue", 0) <= allocator.DAILY_MAXIMUMS["revenue"]
        assert category_counts.get("engagement", 0) <= allocator.DAILY_MAXIMUMS["engagement"]
        assert category_counts.get("retention", 0) <= allocator.DAILY_MAXIMUMS["retention"]


class TestCaptionMatcher:
    """Tests for CaptionMatcher."""

    def test_select_caption_from_pool(self):
        """Test caption selection from candidate pool."""
        matcher = CaptionMatcher()

        captions = [
            Caption(
                id=1,
                text="Hey babe, check this out..." + "x" * 250,
                type="ppv_unlock",
                performance_score=85.0,
                freshness_score=90.0,
            ),
            Caption(
                id=2,
                text="Special just for you..." + "x" * 250,
                type="ppv_teaser",
                performance_score=75.0,
                freshness_score=80.0,
            ),
        ]

        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_video",
            available_captions=captions,
        )

        assert result is not None
        assert result.caption_score.caption.id in [1, 2]
        assert result.caption_score.total_score > 0

    def test_used_caption_not_reselected_immediately(self):
        """Test used captions are tracked and deprioritized."""
        matcher = CaptionMatcher()

        captions = [
            Caption(
                id=1,
                text="Caption one..." + "x" * 100,
                type="flirty_opener",
                performance_score=85.0,
                freshness_score=90.0,
            ),
        ]

        # Select once
        result1 = matcher.select_caption("test", "bump_normal", captions)
        assert result1 is not None
        assert result1.caption_score.caption.id == 1

        # Caption is now tracked as used
        assert 1 in matcher._used_captions

    def test_calculate_score_returns_caption_score(self):
        """Test calculate_score returns CaptionScore with components."""
        matcher = CaptionMatcher()

        caption = Caption(
            id=1,
            text="Test caption for scoring",
            type="ppv_unlock",
            performance_score=80.0,
            freshness_score=75.0,
        )

        score = matcher.calculate_score(
            caption=caption,
            send_type_key="ppv_video",
            persona="playful",
        )

        assert isinstance(score, CaptionScore)
        assert score.total_score > 0
        assert "performance" in score.components
        assert "freshness" in score.components
        assert "type_priority" in score.components
        assert "persona" in score.components
        assert "diversity" in score.components

    def test_type_priority_scoring(self):
        """Test type priority scoring based on requirements list."""
        matcher = CaptionMatcher()

        # First in requirements list should get highest score
        first_score = matcher._calculate_type_priority("ppv_unlock", "ppv_video")
        # Not in requirements list should get lower score
        not_match_score = matcher._calculate_type_priority("generic", "ppv_video")

        assert first_score > not_match_score

    def test_persona_fit_scoring(self):
        """Test persona fit scoring for compatible types."""
        matcher = CaptionMatcher()

        # Caption with compatible type for seductress persona
        compatible_caption = Caption(
            id=1,
            text="Seductive test",
            type="seductive",
            performance_score=80.0,
            freshness_score=80.0,
            tone="seductive",
        )

        score = matcher._calculate_persona_fit(compatible_caption, "seductress")
        # Should get high score for match
        assert score >= 75.0

    def test_diversity_scoring_penalizes_overuse(self):
        """Test diversity score decreases with repeated type usage."""
        matcher = CaptionMatcher()

        # First use of a type should get max score
        first_score = matcher._calculate_diversity_score("ppv_unlock")
        assert first_score == 100.0

        # Simulate usage
        matcher._type_usage_count["ppv_unlock"] = 3

        # Now should be lower
        after_usage = matcher._calculate_diversity_score("ppv_unlock")
        assert after_usage < first_score

    def test_reset_usage_tracking(self):
        """Test reset clears all tracking state."""
        matcher = CaptionMatcher()

        # Add some tracking state
        matcher._used_captions.add(1)
        matcher._used_captions.add(2)
        matcher._type_usage_count["test"] = 5

        matcher.reset_usage_tracking()

        assert len(matcher._used_captions) == 0
        assert len(matcher._type_usage_count) == 0

    def test_get_usage_stats(self):
        """Test usage stats reporting."""
        matcher = CaptionMatcher()

        # Add some state
        matcher._used_captions.add(1)
        matcher._used_captions.add(2)
        matcher._type_usage_count["ppv_unlock"] = 3
        matcher._type_usage_count["casual"] = 2

        stats = matcher.get_usage_stats()

        assert stats["total_used"] == 2
        assert stats["unique_types"] == 2
        assert stats["type_distribution"]["ppv_unlock"] == 3


class TestScheduleOptimizer:
    """Tests for ScheduleOptimizer."""

    def test_prime_hour_boost(self):
        """Test prime hours get boosted scores."""
        optimizer = ScheduleOptimizer()

        # Get preferences for ppv_video
        preferences = optimizer.TIMING_PREFERENCES.get("ppv_video", {})

        # Prime hour (19 = 7 PM) - preferred for ppv_video
        prime_score = optimizer.calculate_slot_score(
            hour=19,
            day_of_week=5,  # Saturday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        # Non-prime hour (11 AM) - not in preferred hours
        regular_score = optimizer.calculate_slot_score(
            hour=11,
            day_of_week=2,  # Wednesday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        assert prime_score > regular_score

    def test_avoid_hour_penalty(self):
        """Test avoid hours get penalized."""
        optimizer = ScheduleOptimizer()

        preferences = optimizer.TIMING_PREFERENCES.get("bump_normal", {})

        # Avoid hour (4 AM) - in avoid list
        avoid_score = optimizer.calculate_slot_score(
            hour=4,
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
        )

        # Regular hour (14:00) - in preferred hours
        regular_score = optimizer.calculate_slot_score(
            hour=14,
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
        )

        assert avoid_score < regular_score

    def test_saturation_adjustment_high(self):
        """Test high saturation reduces volume."""
        optimizer = ScheduleOptimizer()

        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=80,  # Very high saturation
        )

        assert adjusted < 10  # Should reduce volume

    def test_saturation_adjustment_low(self):
        """Test low saturation increases volume."""
        optimizer = ScheduleOptimizer()

        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=20,  # Low saturation
        )

        assert adjusted > 10  # Should increase volume
        assert adjusted == 12  # 120% of 10

    def test_saturation_adjustment_moderate(self):
        """Test moderate saturation maintains volume."""
        optimizer = ScheduleOptimizer()

        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=45,  # Moderate saturation
        )

        assert adjusted == 10  # Should maintain volume

    def test_optimize_timing_returns_items(self):
        """Test timing optimization assigns times to items."""
        optimizer = ScheduleOptimizer()

        items = [
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-01-22",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
            ScheduleItem(
                send_type_key="bump_normal",
                scheduled_date="2025-01-22",
                scheduled_time="00:00",
                category="engagement",
                priority=2,
            ),
        ]

        optimized = optimizer.optimize_timing(items=items)

        assert len(optimized) == 2
        assert all(item.scheduled_time != "00:00" for item in optimized)

    def test_timing_preferences_all_21_types(self):
        """Test all 21 send types have timing preferences."""
        optimizer = ScheduleOptimizer()

        all_21_types = [
            # Revenue (7)
            "ppv_video", "vip_program", "game_post", "bundle",
            "flash_bundle", "snapchat_bundle", "first_to_tip",
            # Engagement (9)
            "link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
            "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo",
            # Retention (5)
            "renew_on_post", "renew_on_message", "ppv_message",
            "ppv_followup", "expired_winback",
        ]

        for send_type in all_21_types:
            assert send_type in optimizer.TIMING_PREFERENCES
            prefs = optimizer.TIMING_PREFERENCES[send_type]
            assert "preferred_hours" in prefs
            assert "preferred_days" in prefs
            assert "avoid_hours" in prefs
            assert "min_spacing" in prefs

    def test_min_spacing_respected(self):
        """Test minimum spacing between sends is enforced."""
        optimizer = ScheduleOptimizer()

        # Get min spacing for ppv_video
        prefs = optimizer.TIMING_PREFERENCES["ppv_video"]
        min_spacing = prefs["min_spacing"]

        assert min_spacing == 90  # PPV videos need 90 min spacing

    def test_reset_tracking(self):
        """Test tracking state is reset."""
        optimizer = ScheduleOptimizer()

        # Add some tracking state
        optimizer._assigned_times["2025-01-22"] = []

        optimizer.reset_tracking()

        assert len(optimizer._assigned_times) == 0

    def test_get_timing_stats_empty(self):
        """Test timing stats with no assignments."""
        optimizer = ScheduleOptimizer()

        stats = optimizer.get_timing_stats()

        assert stats["total_assigned"] == 0
        assert stats["hour_distribution"] == {}
        assert stats["prime_time_percentage"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
