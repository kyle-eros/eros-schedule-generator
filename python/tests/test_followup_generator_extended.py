"""
Extended tests for followup_generator module to increase coverage.

Tests cover:
- schedule_ppv_followup function
- validate_followup_window function
- _truncated_normal_sample function
- _create_deterministic_seed function
- Day boundary handling
- Edge cases and error conditions
"""

import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.followup_generator import (
    OPTIMAL_FOLLOWUP_MINUTES,
    DEFAULT_STD_DEV,
    DEFAULT_MIN_OFFSET,
    DEFAULT_MAX_OFFSET,
    MAX_REJECTION_ATTEMPTS,
    schedule_ppv_followup,
    validate_followup_window,
    _truncated_normal_sample,
    _create_deterministic_seed,
)


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_optimal_followup_minutes(self):
        """Test optimal followup minutes is 28."""
        assert OPTIMAL_FOLLOWUP_MINUTES == 28

    def test_default_std_dev(self):
        """Test default standard deviation is 8.0."""
        assert DEFAULT_STD_DEV == 8.0

    def test_default_min_offset(self):
        """Test default min offset is 15."""
        assert DEFAULT_MIN_OFFSET == 15

    def test_default_max_offset(self):
        """Test default max offset is 45."""
        assert DEFAULT_MAX_OFFSET == 45

    def test_max_rejection_attempts(self):
        """Test max rejection attempts is 100."""
        assert MAX_REJECTION_ATTEMPTS == 100


# =============================================================================
# Test _create_deterministic_seed
# =============================================================================


class TestCreateDeterministicSeed:
    """Tests for deterministic seed creation."""

    def test_same_inputs_same_seed(self):
        """Test same inputs produce same seed."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed1 = _create_deterministic_seed("creator_123", parent_time)
        seed2 = _create_deterministic_seed("creator_123", parent_time)
        assert seed1 == seed2

    def test_different_creators_different_seeds(self):
        """Test different creators produce different seeds."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed_alice = _create_deterministic_seed("alice", parent_time)
        seed_bob = _create_deterministic_seed("bob", parent_time)
        assert seed_alice != seed_bob

    def test_different_times_different_seeds(self):
        """Test different times produce different seeds."""
        seed1 = _create_deterministic_seed("creator_123", datetime(2025, 1, 15, 14, 30))
        seed2 = _create_deterministic_seed("creator_123", datetime(2025, 1, 15, 15, 30))
        assert seed1 != seed2

    def test_seed_is_integer(self):
        """Test seed is an integer."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("creator_123", parent_time)
        assert isinstance(seed, int)

    def test_seed_positive(self):
        """Test seed is positive."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("creator_123", parent_time)
        assert seed >= 0

    def test_seed_with_empty_creator_id(self):
        """Test seed works with empty creator_id."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("", parent_time)
        assert isinstance(seed, int)

    def test_seed_with_unicode_creator_id(self):
        """Test seed works with unicode characters."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("creator_with_unicode_char", parent_time)
        assert isinstance(seed, int)


# =============================================================================
# Test _truncated_normal_sample
# =============================================================================


class TestTruncatedNormalSample:
    """Tests for truncated normal distribution sampling."""

    def test_sample_within_bounds(self):
        """Test sample is always within bounds."""
        rng = random.Random(42)
        for _ in range(100):
            sample = _truncated_normal_sample(rng, 28.0, 8.0, 15.0, 45.0)
            assert 15.0 <= sample <= 45.0

    def test_sample_mean_near_expected(self):
        """Test samples average near the mean."""
        rng = random.Random(42)
        samples = [_truncated_normal_sample(rng, 28.0, 8.0, 15.0, 45.0) for _ in range(1000)]
        avg = sum(samples) / len(samples)
        # Average should be near 28, within a few minutes
        assert 24 < avg < 32

    def test_narrow_bounds(self):
        """Test with very narrow bounds."""
        rng = random.Random(42)
        sample = _truncated_normal_sample(rng, 30.0, 8.0, 29.0, 31.0)
        assert 29.0 <= sample <= 31.0

    def test_deterministic_with_seed(self):
        """Test same seed produces same sequence."""
        samples1 = []
        samples2 = []

        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        for _ in range(10):
            samples1.append(_truncated_normal_sample(rng1, 28.0, 8.0, 15.0, 45.0))
            samples2.append(_truncated_normal_sample(rng2, 28.0, 8.0, 15.0, 45.0))

        assert samples1 == samples2

    def test_fallback_to_uniform(self):
        """Test fallback to uniform when normal fails."""
        # Use very tight bounds that might trigger fallback
        rng = random.Random(42)
        sample = _truncated_normal_sample(rng, 50.0, 1.0, 15.0, 16.0, max_attempts=1)
        assert 15.0 <= sample <= 16.0


# =============================================================================
# Test schedule_ppv_followup
# =============================================================================


class TestSchedulePPVFollowup:
    """Tests for PPV followup scheduling."""

    def test_returns_datetime(self):
        """Test returns a datetime object."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result = schedule_ppv_followup(parent_time, "creator_123")
        assert isinstance(result, datetime)

    def test_followup_after_parent(self):
        """Test followup is always after parent."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result = schedule_ppv_followup(parent_time, "creator_123")
        assert result > parent_time

    def test_within_default_bounds(self):
        """Test followup is within default bounds."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result = schedule_ppv_followup(parent_time, "creator_123")

        gap_minutes = (result - parent_time).total_seconds() / 60
        assert DEFAULT_MIN_OFFSET <= gap_minutes <= DEFAULT_MAX_OFFSET

    def test_custom_bounds(self):
        """Test custom min/max offset bounds."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result = schedule_ppv_followup(
            parent_time, "creator_123",
            min_offset=20,
            max_offset=30
        )

        gap_minutes = (result - parent_time).total_seconds() / 60
        assert 20 <= gap_minutes <= 30

    def test_deterministic(self):
        """Test same inputs produce same output."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result1 = schedule_ppv_followup(parent_time, "creator_123")
        result2 = schedule_ppv_followup(parent_time, "creator_123")
        assert result1 == result2

    def test_different_creators_may_differ(self):
        """Test different creators may get different followups."""
        parent_time = datetime(2025, 1, 15, 14, 30, 0)
        result_alice = schedule_ppv_followup(parent_time, "alice")
        result_bob = schedule_ppv_followup(parent_time, "bob")
        # May or may not be equal, but both should be valid
        assert isinstance(result_alice, datetime)
        assert isinstance(result_bob, datetime)


# =============================================================================
# Test Day Boundary Handling
# =============================================================================


class TestDayBoundaryHandling:
    """Tests for day boundary handling."""

    def test_late_night_raises_valueerror(self):
        """Test late night parent raises ValueError when gap too short."""
        parent_time = datetime(2025, 1, 15, 23, 50, 0)
        # With only 9 minutes to 23:59, should raise ValueError
        with pytest.raises(ValueError, match="Cannot schedule followup"):
            schedule_ppv_followup(parent_time, "creator_123")

    def test_allow_next_day_true(self):
        """Test allow_next_day=True allows crossing midnight."""
        parent_time = datetime(2025, 1, 15, 23, 50, 0)
        result = schedule_ppv_followup(
            parent_time, "creator_123",
            allow_next_day=True
        )

        # Should allow crossing to next day
        assert isinstance(result, datetime)
        # Gap should still be within bounds
        gap_minutes = (result - parent_time).total_seconds() / 60
        assert DEFAULT_MIN_OFFSET <= gap_minutes <= DEFAULT_MAX_OFFSET

    def test_very_late_raises_valueerror(self):
        """Test very late parent with short gap raises ValueError."""
        # Parent at 23:50 with min_offset=15 leaves only 9 minutes to 23:59
        # This should raise ValueError when gap is < min_offset
        parent_time = datetime(2025, 1, 15, 23, 50, 0)

        # With min_offset=15, we can only have 9 minutes to 23:59
        # This should raise ValueError
        with pytest.raises(ValueError, match="Cannot schedule followup"):
            schedule_ppv_followup(
                parent_time, "creator_123",
                min_offset=15,  # Need 15 minutes but only 9 available
            )

    def test_exactly_at_boundary(self):
        """Test parent exactly at 23:45 (15 min to midnight)."""
        parent_time = datetime(2025, 1, 15, 23, 45, 0)
        # With min_offset=15, we have exactly 14 minutes to 23:59
        # This should raise ValueError
        with pytest.raises(ValueError, match="Cannot schedule followup"):
            schedule_ppv_followup(
                parent_time, "creator_123",
                min_offset=15,
            )


# =============================================================================
# Test validate_followup_window
# =============================================================================


class TestValidateFollowupWindow:
    """Tests for followup window validation."""

    def test_valid_window(self):
        """Test valid followup window."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 0, 0)  # 30 min gap

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is True
        assert result['gap_minutes'] == 30.0

    def test_too_early_followup(self):
        """Test followup that is too early."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 14, 40, 0)  # 10 min gap

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is False
        assert 'error' in result
        assert 'less than minimum' in result['error']

    def test_too_late_followup(self):
        """Test followup that is too late."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 30, 0)  # 60 min gap

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is False
        assert 'error' in result
        assert 'exceeds maximum' in result['error']

    def test_followup_before_parent(self):
        """Test followup before parent time."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 14, 0, 0)  # Before parent

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is False
        assert 'error' in result
        assert 'before' in result['error'].lower()

    def test_exact_min_boundary(self):
        """Test exactly at minimum boundary."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 14, 45, 0)  # Exactly 15 min

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is True
        assert result['gap_minutes'] == 15.0

    def test_exact_max_boundary(self):
        """Test exactly at maximum boundary."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 15, 0)  # Exactly 45 min

        result = validate_followup_window(parent, followup)

        assert result['is_valid'] is True
        assert result['gap_minutes'] == 45.0

    def test_custom_bounds(self):
        """Test with custom min/max offsets."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 0, 0)  # 30 min gap

        # With tighter bounds, should fail
        result = validate_followup_window(parent, followup, min_offset=10, max_offset=20)

        assert result['is_valid'] is False
        assert result['gap_minutes'] == 30.0

    def test_gap_minutes_always_included(self):
        """Test gap_minutes is always in result."""
        parent = datetime(2025, 1, 15, 14, 30, 0)

        for followup in [
            datetime(2025, 1, 15, 14, 0, 0),   # Before parent
            datetime(2025, 1, 15, 14, 40, 0),  # Too early
            datetime(2025, 1, 15, 15, 0, 0),   # Valid
            datetime(2025, 1, 15, 16, 0, 0),   # Too late
        ]:
            result = validate_followup_window(parent, followup)
            assert 'gap_minutes' in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestFollowupIntegration:
    """Integration tests for followup generation."""

    def test_generated_followup_validates(self):
        """Test generated followup passes validation."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = schedule_ppv_followup(parent, "creator_123")

        result = validate_followup_window(parent, followup)
        assert result['is_valid'] is True

    def test_multiple_followups_same_parent(self):
        """Test multiple different creators from same parent."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        creators = ["alice", "bob", "charlie", "diana"]

        for creator in creators:
            followup = schedule_ppv_followup(parent, creator)
            result = validate_followup_window(parent, followup)
            assert result['is_valid'] is True

    def test_distribution_near_optimal(self):
        """Test distribution centers near optimal 28 minutes."""
        parent = datetime(2025, 1, 15, 14, 0, 0)
        gaps = []

        for i in range(100):
            followup = schedule_ppv_followup(parent, f"creator_{i}")
            gap = (followup - parent).total_seconds() / 60
            gaps.append(gap)

        avg_gap = sum(gaps) / len(gaps)
        # Average should be near optimal (28), within a few minutes
        assert 22 < avg_gap < 34


# =============================================================================
# Edge Cases
# =============================================================================


class TestFollowupEdgeCases:
    """Edge case tests for followup generation."""

    def test_midnight_parent(self):
        """Test parent at midnight."""
        parent = datetime(2025, 1, 15, 0, 0, 0)
        followup = schedule_ppv_followup(parent, "creator_123")

        result = validate_followup_window(parent, followup)
        assert result['is_valid'] is True

    def test_noon_parent(self):
        """Test parent at noon."""
        parent = datetime(2025, 1, 15, 12, 0, 0)
        followup = schedule_ppv_followup(parent, "creator_123")

        result = validate_followup_window(parent, followup)
        assert result['is_valid'] is True

    def test_with_seconds_and_microseconds(self):
        """Test parent with non-zero seconds and microseconds."""
        parent = datetime(2025, 1, 15, 14, 30, 45, 123456)
        followup = schedule_ppv_followup(parent, "creator_123")

        assert isinstance(followup, datetime)
        assert followup > parent

    def test_consistency_across_many_calls(self):
        """Test consistency across many calls."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        results = [schedule_ppv_followup(parent, "creator_123") for _ in range(100)]

        # All results should be identical (deterministic)
        assert all(r == results[0] for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
