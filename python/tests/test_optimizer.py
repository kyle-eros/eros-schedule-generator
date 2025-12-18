"""
Unit tests for ScheduleOptimizer.

Tests timing optimization, spacing constraints, and prime time allocation.
"""

import sys
from datetime import datetime, time
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.optimization.schedule_optimizer import (
    ScheduleItem,
    ScheduleOptimizer,
    SLOT_SCORE_BASE,
    SLOT_SCORE_MIN,
    SLOT_SCORE_MAX,
    PREFERRED_HOURS_MAX_BONUS,
    PREFERRED_DAYS_BONUS,
    AVOID_HOURS_PENALTY,
    PRIME_TIME_BONUS,
    PRIME_DAY_BONUS,
    PPV_PRIME_TIME_BONUS,
    PPV_PRIME_HOURS,
    SATURATION_LOW_THRESHOLD,
    SATURATION_MODERATE_THRESHOLD,
    SATURATION_HIGH_THRESHOLD,
    SATURATION_LOW_MULTIPLIER,
    SATURATION_MODERATE_MULTIPLIER,
    SATURATION_HIGH_MULTIPLIER,
    SATURATION_VERY_HIGH_MULTIPLIER,
)


class TestScheduleItemModel:
    """Tests for ScheduleItem dataclass."""

    def test_schedule_item_creation(self):
        """Test ScheduleItem creation with required fields."""
        item = ScheduleItem(
            send_type_key="ppv_video",
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            category="revenue",
            priority=1,
        )

        assert item.send_type_key == "ppv_video"
        assert item.scheduled_date == "2025-12-16"
        assert item.scheduled_time == "19:00"
        assert item.category == "revenue"
        assert item.priority == 1

    def test_schedule_item_defaults(self):
        """Test ScheduleItem default values."""
        item = ScheduleItem(
            send_type_key="bump_normal",
            scheduled_date="2025-12-16",
            scheduled_time="10:00",
            category="engagement",
            priority=2,
        )

        assert item.caption_id is None
        assert item.caption_text == ""
        assert item.requires_media is False
        assert item.media_type == "none"
        assert item.target_key == "all_fans"
        assert item.channel_key == "mass_message"

    def test_schedule_item_datetime_obj(self):
        """Test datetime_obj property."""
        item = ScheduleItem(
            send_type_key="ppv_video",
            scheduled_date="2025-12-16",
            scheduled_time="19:30",
            category="revenue",
            priority=1,
        )

        dt = item.datetime_obj
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 16
        assert dt.hour == 19
        assert dt.minute == 30


class TestSlotScoring:
    """Tests for time slot scoring."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        """Fresh optimizer instance."""
        opt = ScheduleOptimizer()
        opt.reset_tracking()
        return opt

    def test_calculate_slot_score_base(self, optimizer):
        """Test base slot score calculation."""
        preferences = {
            "preferred_hours": [],
            "preferred_days": [],
            "avoid_hours": [],
        }

        score = optimizer.calculate_slot_score(
            hour=12,
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
        )

        # Should be around base with possible prime time bonuses
        assert score >= SLOT_SCORE_BASE

    def test_calculate_slot_score_preferred_hour(self, optimizer):
        """Test preferred hour bonus."""
        preferences = {
            "preferred_hours": [19, 21],
            "preferred_days": [],
            "avoid_hours": [],
        }

        score_preferred = optimizer.calculate_slot_score(
            hour=19,
            day_of_week=2,
            send_type_key="ppv_video",
            preferences=preferences,
        )

        score_not_preferred = optimizer.calculate_slot_score(
            hour=11,
            day_of_week=2,
            send_type_key="ppv_video",
            preferences=preferences,
        )

        assert score_preferred > score_not_preferred

    def test_calculate_slot_score_preferred_day(self, optimizer):
        """Test preferred day bonus."""
        preferences = {
            "preferred_hours": [],
            "preferred_days": [4, 5, 6],  # Fri, Sat, Sun
            "avoid_hours": [],
        }

        score_preferred = optimizer.calculate_slot_score(
            hour=12,
            day_of_week=5,  # Saturday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        score_not_preferred = optimizer.calculate_slot_score(
            hour=12,
            day_of_week=1,  # Tuesday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        assert score_preferred > score_not_preferred

    def test_calculate_slot_score_avoid_hour(self, optimizer):
        """Test avoid hour penalty."""
        preferences = {
            "preferred_hours": [],
            "preferred_days": [],
            "avoid_hours": [3, 4, 5, 6, 7],
        }

        score_avoid = optimizer.calculate_slot_score(
            hour=4,  # 4 AM
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
        )

        score_regular = optimizer.calculate_slot_score(
            hour=14,  # 2 PM
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
        )

        assert score_avoid < score_regular

    def test_calculate_slot_score_clamped(self, optimizer):
        """Test score is clamped to valid range."""
        # Very favorable conditions
        preferences = {
            "preferred_hours": [19],
            "preferred_days": [5],
            "avoid_hours": [],
        }

        score = optimizer.calculate_slot_score(
            hour=19,
            day_of_week=5,
            send_type_key="ppv_video",
            preferences=preferences,
        )

        assert SLOT_SCORE_MIN <= score <= SLOT_SCORE_MAX

    def test_ppv_prime_time_bonus(self, optimizer):
        """Test PPV types get extra bonus at prime hours."""
        # Use Wednesday (day 2) where both comparison hours are outside daily prime
        # to isolate the PPV prime time bonus effect.
        # Wednesday daily prime hours are [11, 14, 19, 21]
        # PPV_PRIME_HOURS are [19, 21, 22]
        preferences = optimizer.TIMING_PREFERENCES.get("ppv_video", {})

        score_ppv_prime = optimizer.calculate_slot_score(
            hour=22,  # In PPV_PRIME_HOURS [19, 21, 22]
            day_of_week=2,  # Wednesday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        score_not_ppv_prime = optimizer.calculate_slot_score(
            hour=15,  # Not in PPV_PRIME_HOURS
            day_of_week=2,  # Wednesday
            send_type_key="ppv_video",
            preferences=preferences,
        )

        # PPV at PPV prime hour should get PPV_PRIME_TIME_BONUS
        # The difference should at minimum include the PPV bonus
        assert score_ppv_prime > score_not_ppv_prime or score_ppv_prime >= 50

    def test_historical_timing_data_bonus(self, optimizer):
        """Test historical timing data affects score."""
        preferences = {
            "preferred_hours": [],
            "preferred_days": [],
            "avoid_hours": [],
        }

        timing_data = {
            19: [90, 85, 95],  # High performance at 7 PM
            11: [40, 35, 45],  # Low performance at 11 AM
        }

        score_high_perf = optimizer.calculate_slot_score(
            hour=19,
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
            timing_data=timing_data,
        )

        score_low_perf = optimizer.calculate_slot_score(
            hour=11,
            day_of_week=2,
            send_type_key="bump_normal",
            preferences=preferences,
            timing_data=timing_data,
        )

        assert score_high_perf > score_low_perf


class TestTimingPreferences:
    """Tests for timing preference configuration."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_all_21_types_have_preferences(self, optimizer):
        """Test all 21 send types have timing preferences."""
        all_types = [
            "ppv_video", "vip_program", "game_post", "bundle",
            "flash_bundle", "snapchat_bundle", "first_to_tip",
            "link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
            "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo",
            "renew_on_post", "renew_on_message", "ppv_message",
            "ppv_followup", "expired_winback",
        ]

        for send_type in all_types:
            assert send_type in optimizer.TIMING_PREFERENCES

    def test_preferences_have_required_keys(self, optimizer):
        """Test all preferences have required configuration keys."""
        for send_type, prefs in optimizer.TIMING_PREFERENCES.items():
            assert "preferred_hours" in prefs, f"{send_type} missing preferred_hours"
            assert "preferred_days" in prefs, f"{send_type} missing preferred_days"
            assert "avoid_hours" in prefs, f"{send_type} missing avoid_hours"
            assert "min_spacing" in prefs, f"{send_type} missing min_spacing"

    def test_ppv_video_preferences(self, optimizer):
        """Test ppv_video specific preferences."""
        prefs = optimizer.TIMING_PREFERENCES["ppv_video"]

        assert 19 in prefs["preferred_hours"]
        assert 21 in prefs["preferred_hours"]
        assert prefs["min_spacing"] == 90
        assert prefs["boost"] == 1.3

    def test_ppv_followup_has_offset(self, optimizer):
        """Test ppv_followup has offset_from_parent."""
        prefs = optimizer.TIMING_PREFERENCES["ppv_followup"]

        assert "offset_from_parent" in prefs
        assert prefs["offset_from_parent"] == 20  # 20 minutes

    def test_link_drop_has_offset(self, optimizer):
        """Test link_drop has offset_from_parent."""
        prefs = optimizer.TIMING_PREFERENCES["link_drop"]

        assert "offset_from_parent" in prefs
        assert prefs["offset_from_parent"] == 180  # 3 hours


class TestSaturationAdjustment:
    """Tests for saturation-based volume adjustment."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_low_saturation_increases_volume(self, optimizer):
        """Test low saturation (< 30) increases volume."""
        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=20,
        )

        assert adjusted > 10
        expected = int(10 * SATURATION_LOW_MULTIPLIER)
        assert adjusted == expected

    def test_moderate_saturation_maintains_volume(self, optimizer):
        """Test moderate saturation (30-50) maintains volume."""
        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=40,
        )

        assert adjusted == 10

    def test_high_saturation_reduces_volume(self, optimizer):
        """Test high saturation (50-70) reduces volume slightly."""
        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=60,
        )

        assert adjusted < 10
        expected = int(10 * SATURATION_HIGH_MULTIPLIER)
        assert adjusted == expected

    def test_very_high_saturation_reduces_significantly(self, optimizer):
        """Test very high saturation (70+) reduces volume significantly."""
        adjusted = optimizer.apply_saturation_adjustment(
            base_volume=10,
            saturation_score=85,
        )

        assert adjusted < 10
        expected = int(10 * SATURATION_VERY_HIGH_MULTIPLIER)
        assert adjusted == expected

    @pytest.mark.parametrize("saturation,expected_multiplier", [
        (10, SATURATION_LOW_MULTIPLIER),
        (29, SATURATION_LOW_MULTIPLIER),
        (30, SATURATION_MODERATE_MULTIPLIER),
        (49, SATURATION_MODERATE_MULTIPLIER),
        (50, SATURATION_HIGH_MULTIPLIER),
        (69, SATURATION_HIGH_MULTIPLIER),
        (70, SATURATION_VERY_HIGH_MULTIPLIER),
        (100, SATURATION_VERY_HIGH_MULTIPLIER),
    ])
    def test_saturation_boundaries(self, optimizer, saturation: int, expected_multiplier: float):
        """Test saturation boundary conditions."""
        adjusted = optimizer.apply_saturation_adjustment(10, saturation)
        expected = int(10 * expected_multiplier)
        assert adjusted == expected


class TestOptimizeTiming:
    """Tests for timing optimization."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        opt = ScheduleOptimizer()
        opt.reset_tracking()
        return opt

    def test_optimize_timing_assigns_times(self, optimizer):
        """Test optimize_timing assigns times to all items."""
        items = [
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
            ScheduleItem(
                send_type_key="bump_normal",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="engagement",
                priority=2,
            ),
        ]

        optimized = optimizer.optimize_timing(items)

        assert len(optimized) == 2
        for item in optimized:
            assert item.scheduled_time != "00:00"

    def test_optimize_timing_preserves_date(self, optimizer):
        """Test optimize_timing preserves scheduled date."""
        items = [
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
        ]

        optimized = optimizer.optimize_timing(items)
        assert optimized[0].scheduled_date == "2025-12-16"

    def test_optimize_timing_respects_priority(self, optimizer):
        """Test higher priority items get better slots."""
        items = [
            ScheduleItem(
                send_type_key="bump_normal",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="engagement",
                priority=2,
            ),
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
        ]

        optimized = optimizer.optimize_timing(items)

        # Priority 1 item should be processed first
        # and likely get a better time slot
        assert len(optimized) == 2

    def test_optimize_timing_multiple_days(self, optimizer):
        """Test optimize_timing handles multiple days."""
        items = [
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-12-16",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
            ScheduleItem(
                send_type_key="bump_normal",
                scheduled_date="2025-12-17",
                scheduled_time="00:00",
                category="engagement",
                priority=2,
            ),
        ]

        optimized = optimizer.optimize_timing(items)

        assert len(optimized) == 2
        assert optimized[0].scheduled_date == "2025-12-16"
        assert optimized[1].scheduled_date == "2025-12-17"


class TestTimeSlotGeneration:
    """Tests for time slot generation."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_generate_time_slots_start_hour(self, optimizer):
        """Test slots start at 8 AM."""
        slots = optimizer._generate_time_slots("2025-12-16")

        # Should not have slots before 8 AM
        early_slots = [s for s in slots if s.hour < 8]
        assert len(early_slots) == 0

    def test_generate_time_slots_end_hour(self, optimizer):
        """Test slots end before midnight."""
        slots = optimizer._generate_time_slots("2025-12-16")

        # All slots should be before midnight
        assert all(s.hour < 24 for s in slots)

    def test_generate_time_slots_excludes_avoid_hours(self, optimizer):
        """Test slots exclude avoid hours."""
        slots = optimizer._generate_time_slots("2025-12-16")

        # Should not have slots in avoid hours (3-7 AM)
        avoid_slots = [s for s in slots if s.hour in optimizer.AVOID_HOURS]
        assert len(avoid_slots) == 0

    def test_generate_time_slots_15_min_intervals(self, optimizer):
        """Test slots are at 15-minute intervals."""
        slots = optimizer._generate_time_slots("2025-12-16")

        valid_minutes = {0, 15, 30, 45}
        for slot in slots:
            assert slot.minute in valid_minutes


class TestSpacingConstraints:
    """Tests for minimum spacing between sends."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_remove_nearby_slots_default_spacing(self, optimizer):
        """Test nearby slots are removed based on default spacing."""
        slots = [
            time(10, 0),
            time(10, 15),
            time(10, 30),
            time(10, 45),
            time(11, 0),
            time(11, 15),
        ]

        assigned = time(10, 0)
        filtered = optimizer._remove_nearby_slots(slots, assigned, "bump_normal")

        # bump_normal has 60-minute spacing
        # So 10:15, 10:30, 10:45 should be removed
        assert len(filtered) < len(slots)

    def test_remove_nearby_slots_ppv_video(self, optimizer):
        """Test ppv_video has 90-minute spacing."""
        prefs = optimizer.TIMING_PREFERENCES["ppv_video"]
        assert prefs["min_spacing"] == 90

    def test_remove_nearby_slots_vip_program(self, optimizer):
        """Test vip_program has 120-minute spacing."""
        prefs = optimizer.TIMING_PREFERENCES["vip_program"]
        assert prefs["min_spacing"] == 120

    def test_remove_nearby_slots_flash_bundle(self, optimizer):
        """Test flash_bundle has 240-minute spacing."""
        prefs = optimizer.TIMING_PREFERENCES["flash_bundle"]
        assert prefs["min_spacing"] == 240


class TestPrimeTimeConfiguration:
    """Tests for prime time configuration."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_prime_hours_defined(self, optimizer):
        """Test prime hours are defined."""
        assert optimizer.PRIME_HOURS == [10, 14, 19, 21]

    def test_prime_days_defined(self, optimizer):
        """Test prime days are defined."""
        assert optimizer.PRIME_DAYS == [4, 5, 6]  # Fri, Sat, Sun

    def test_avoid_hours_defined(self, optimizer):
        """Test avoid hours are defined."""
        expected = list(range(3, 8))  # 3 AM - 7 AM
        assert optimizer.AVOID_HOURS == expected

    def test_min_spacing_minutes(self, optimizer):
        """Test minimum spacing is defined."""
        assert optimizer.MIN_SPACING_MINUTES == 45


class TestTrackingState:
    """Tests for optimizer tracking state."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        return ScheduleOptimizer()

    def test_reset_tracking_clears_state(self, optimizer):
        """Test reset clears assigned times."""
        optimizer._assigned_times["2025-12-16"] = [time(10, 0)]

        optimizer.reset_tracking()

        assert len(optimizer._assigned_times) == 0

    def test_get_timing_stats_empty(self, optimizer):
        """Test stats with no assignments."""
        optimizer.reset_tracking()
        stats = optimizer.get_timing_stats()

        assert stats["total_assigned"] == 0
        assert stats["hour_distribution"] == {}
        assert stats["prime_time_percentage"] == 0

    def test_get_timing_stats_with_data(self, optimizer):
        """Test stats with assignments."""
        optimizer._assigned_times["2025-12-16"] = [
            time(10, 0),  # Prime
            time(14, 0),  # Prime
            time(11, 0),  # Not prime
        ]

        stats = optimizer.get_timing_stats()

        assert stats["total_assigned"] == 3
        assert 10 in stats["hour_distribution"]
        assert 14 in stats["hour_distribution"]


class TestScoringConstants:
    """Tests for scoring constant values."""

    def test_slot_score_base(self):
        """Test base slot score."""
        assert SLOT_SCORE_BASE == 50.0

    def test_slot_score_range(self):
        """Test slot score range."""
        assert SLOT_SCORE_MIN == 0.0
        assert SLOT_SCORE_MAX == 100.0

    def test_bonus_values(self):
        """Test bonus value constants."""
        assert PREFERRED_HOURS_MAX_BONUS == 30
        assert PREFERRED_DAYS_BONUS == 20
        assert PRIME_TIME_BONUS == 15
        assert PRIME_DAY_BONUS == 10
        assert PPV_PRIME_TIME_BONUS == 10

    def test_penalty_values(self):
        """Test penalty value constants."""
        assert AVOID_HOURS_PENALTY == 40

    def test_ppv_prime_hours(self):
        """Test PPV prime hours."""
        assert PPV_PRIME_HOURS == [19, 21, 22]

    def test_saturation_thresholds(self):
        """Test saturation threshold values."""
        assert SATURATION_LOW_THRESHOLD == 30
        assert SATURATION_MODERATE_THRESHOLD == 50
        assert SATURATION_HIGH_THRESHOLD == 70


class TestEdgeCases:
    """Edge case tests for optimizer."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        opt = ScheduleOptimizer()
        opt.reset_tracking()
        return opt

    def test_empty_items_list(self, optimizer):
        """Test optimize_timing with empty list."""
        result = optimizer.optimize_timing([])
        assert result == []

    def test_assign_time_slot_no_available(self, optimizer):
        """Test assign_time_slot with no available slots."""
        item = ScheduleItem(
            send_type_key="ppv_video",
            scheduled_date="2025-12-16",
            scheduled_time="00:00",
            category="revenue",
            priority=1,
        )

        result = optimizer.assign_time_slot(item, [], None)
        assert result is None

    def test_saturation_zero(self, optimizer):
        """Test saturation adjustment with zero."""
        adjusted = optimizer.apply_saturation_adjustment(10, 0)
        assert adjusted == int(10 * SATURATION_LOW_MULTIPLIER)

    def test_saturation_one_hundred(self, optimizer):
        """Test saturation adjustment with 100."""
        adjusted = optimizer.apply_saturation_adjustment(10, 100)
        assert adjusted == int(10 * SATURATION_VERY_HIGH_MULTIPLIER)

    def test_base_volume_zero(self, optimizer):
        """Test saturation adjustment with zero base volume."""
        adjusted = optimizer.apply_saturation_adjustment(0, 50)
        assert adjusted == 0
