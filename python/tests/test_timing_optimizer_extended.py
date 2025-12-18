"""
Extended tests for timing_optimizer module to increase coverage.

Tests cover:
- apply_time_jitter function
- validate_jitter_result function
- get_jitter_stats function
- Edge cases for round minute avoidance
- Fallback offset scenarios
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.timing_optimizer import (
    ROUND_MINUTES,
    JITTER_MIN,
    JITTER_MAX,
    FALLBACK_OFFSETS,
    apply_time_jitter,
    validate_jitter_result,
    get_jitter_stats,
    _create_deterministic_seed,
    _get_valid_offsets,
    _get_fallback_offset,
)


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_round_minutes_is_frozenset(self):
        """Test ROUND_MINUTES is immutable frozenset."""
        assert isinstance(ROUND_MINUTES, frozenset)

    def test_round_minutes_contains_expected_values(self):
        """Test ROUND_MINUTES contains 0, 15, 30, 45."""
        assert ROUND_MINUTES == frozenset({0, 15, 30, 45})

    def test_jitter_bounds(self):
        """Test jitter bounds are correctly defined."""
        assert JITTER_MIN == -7
        assert JITTER_MAX == 8

    def test_fallback_offsets_are_valid(self):
        """Test fallback offsets don't include 0."""
        assert 0 not in FALLBACK_OFFSETS
        for offset in FALLBACK_OFFSETS:
            assert isinstance(offset, int)


# =============================================================================
# Test _create_deterministic_seed
# =============================================================================


class TestCreateDeterministicSeed:
    """Tests for deterministic seed creation."""

    def test_same_inputs_same_seed(self):
        """Test same inputs produce same seed."""
        base_time = datetime(2025, 1, 15, 14, 30)
        seed1 = _create_deterministic_seed("creator_123", base_time)
        seed2 = _create_deterministic_seed("creator_123", base_time)
        assert seed1 == seed2

    def test_different_creators_different_seeds(self):
        """Test different creators produce different seeds."""
        base_time = datetime(2025, 1, 15, 14, 30)
        seed_alice = _create_deterministic_seed("alice", base_time)
        seed_bob = _create_deterministic_seed("bob", base_time)
        assert seed_alice != seed_bob

    def test_different_times_different_seeds(self):
        """Test different times produce different seeds."""
        time1 = datetime(2025, 1, 15, 14, 30)
        time2 = datetime(2025, 1, 15, 15, 30)
        seed1 = _create_deterministic_seed("creator_123", time1)
        seed2 = _create_deterministic_seed("creator_123", time2)
        assert seed1 != seed2

    def test_seed_is_integer(self):
        """Test seed is an integer."""
        base_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("creator_123", base_time)
        assert isinstance(seed, int)

    def test_seed_with_special_characters_in_creator_id(self):
        """Test seed works with special characters in creator_id."""
        base_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("creator_with_special!@#$%", base_time)
        assert isinstance(seed, int)

    def test_seed_with_empty_creator_id(self):
        """Test seed works with empty creator_id."""
        base_time = datetime(2025, 1, 15, 14, 30)
        seed = _create_deterministic_seed("", base_time)
        assert isinstance(seed, int)


# =============================================================================
# Test _get_valid_offsets
# =============================================================================


class TestGetValidOffsets:
    """Tests for valid offset calculation."""

    def test_offsets_avoid_round_minutes(self):
        """Test all returned offsets avoid round minutes."""
        for base_minute in range(60):
            offsets = _get_valid_offsets(base_minute)
            for offset in offsets:
                resulting_minute = (base_minute + offset) % 60
                assert resulting_minute not in ROUND_MINUTES

    def test_offsets_within_bounds(self):
        """Test all returned offsets are within bounds."""
        for base_minute in range(60):
            offsets = _get_valid_offsets(base_minute)
            for offset in offsets:
                assert JITTER_MIN <= offset <= JITTER_MAX

    def test_offsets_from_round_minute_exclude_zero(self):
        """Test offsets from round minute exclude zero offset."""
        for round_min in ROUND_MINUTES:
            offsets = _get_valid_offsets(round_min)
            # Zero offset would keep it at round minute
            assert 0 not in offsets or round_min not in ROUND_MINUTES

    def test_offsets_returns_list(self):
        """Test function returns a list."""
        offsets = _get_valid_offsets(30)
        assert isinstance(offsets, list)

    def test_minute_30_has_valid_offsets(self):
        """Test minute 30 has valid offsets available."""
        offsets = _get_valid_offsets(30)
        assert len(offsets) > 0
        # 30 + 3 = 33 (valid)
        assert 3 in offsets
        # 30 + 0 = 30 (invalid, round minute)
        assert 0 not in offsets

    def test_minute_14_excludes_offset_1(self):
        """Test minute 14 excludes offset 1 (would give 15)."""
        offsets = _get_valid_offsets(14)
        # 14 + 1 = 15 (round minute, invalid)
        assert 1 not in offsets
        # 14 + 2 = 16 (valid)
        assert 2 in offsets


# =============================================================================
# Test _get_fallback_offset
# =============================================================================


class TestGetFallbackOffset:
    """Tests for fallback offset calculation."""

    def test_fallback_avoids_round_minutes(self):
        """Test fallback offset avoids round minutes."""
        for base_minute in range(60):
            offset = _get_fallback_offset(base_minute)
            resulting_minute = (base_minute + offset) % 60
            assert resulting_minute not in ROUND_MINUTES

    def test_fallback_returns_integer(self):
        """Test fallback returns an integer."""
        offset = _get_fallback_offset(44)
        assert isinstance(offset, int)

    @pytest.mark.parametrize("base_minute", [0, 14, 29, 44, 59])
    def test_fallback_for_edge_minutes(self, base_minute):
        """Test fallback works for edge case minutes."""
        offset = _get_fallback_offset(base_minute)
        resulting_minute = (base_minute + offset) % 60
        assert resulting_minute not in ROUND_MINUTES


# =============================================================================
# Test apply_time_jitter
# =============================================================================


class TestApplyTimeJitter:
    """Tests for apply_time_jitter function."""

    def test_result_avoids_round_minutes(self):
        """Test jittered time never lands on round minutes."""
        base_time = datetime(2025, 1, 15, 14, 30)
        result = apply_time_jitter(base_time, "creator_123")
        assert result.minute not in ROUND_MINUTES

    def test_deterministic_results(self):
        """Test same inputs produce same output."""
        base_time = datetime(2025, 1, 15, 14, 30)
        result1 = apply_time_jitter(base_time, "creator_123")
        result2 = apply_time_jitter(base_time, "creator_123")
        assert result1 == result2

    def test_different_creators_may_differ(self):
        """Test different creators may get different jitter."""
        base_time = datetime(2025, 1, 15, 14, 30)
        result_alice = apply_time_jitter(base_time, "alice")
        result_bob = apply_time_jitter(base_time, "bob")
        # Results may or may not differ, but both should be valid
        assert result_alice.minute not in ROUND_MINUTES
        assert result_bob.minute not in ROUND_MINUTES

    def test_time_at_round_minute_is_shifted(self):
        """Test time at round minute gets shifted away."""
        for round_min in [0, 15, 30, 45]:
            base_time = datetime(2025, 1, 15, 14, round_min)
            result = apply_time_jitter(base_time, "creator_123")
            assert result.minute not in ROUND_MINUTES

    def test_time_near_59_may_wrap(self):
        """Test time at :59 may wrap to next hour."""
        base_time = datetime(2025, 1, 15, 14, 59)
        result = apply_time_jitter(base_time, "creator_123")
        assert result.minute not in ROUND_MINUTES
        # Result could be in minute 0-59 of next hour or same hour

    def test_time_near_midnight(self):
        """Test time near midnight is handled correctly."""
        base_time = datetime(2025, 1, 15, 23, 55)
        result = apply_time_jitter(base_time, "creator_123")
        assert result.minute not in ROUND_MINUTES

    def test_various_base_minutes(self):
        """Test jitter for various base minutes."""
        for minute in range(60):
            base_time = datetime(2025, 1, 15, 14, minute)
            result = apply_time_jitter(base_time, "creator_123")
            assert result.minute not in ROUND_MINUTES

    def test_preserves_date(self):
        """Test jitter preserves the date component."""
        base_time = datetime(2025, 3, 20, 14, 33)
        result = apply_time_jitter(base_time, "creator_123")
        # Date should be same or at most one day different (hour wrap)
        assert abs((result.date() - base_time.date()).days) <= 1

    def test_jitter_bounded_in_typical_cases(self):
        """Test jitter offset is typically within bounds."""
        base_time = datetime(2025, 1, 15, 14, 33)  # Non-round minute
        result = apply_time_jitter(base_time, "creator_123")
        offset_minutes = (result - base_time).total_seconds() / 60
        # Should be within reasonable bounds
        assert -15 <= offset_minutes <= 15


# =============================================================================
# Test validate_jitter_result
# =============================================================================


class TestValidateJitterResult:
    """Tests for validate_jitter_result function."""

    def test_valid_minute_returns_true(self):
        """Test valid (non-round) minute returns True."""
        valid_times = [
            datetime(2025, 1, 15, 14, 1),
            datetime(2025, 1, 15, 14, 14),
            datetime(2025, 1, 15, 14, 29),
            datetime(2025, 1, 15, 14, 44),
            datetime(2025, 1, 15, 14, 59),
        ]
        for time in valid_times:
            assert validate_jitter_result(time) is True

    def test_invalid_minute_returns_false(self):
        """Test invalid (round) minute returns False."""
        invalid_times = [
            datetime(2025, 1, 15, 14, 0),
            datetime(2025, 1, 15, 14, 15),
            datetime(2025, 1, 15, 14, 30),
            datetime(2025, 1, 15, 14, 45),
        ]
        for time in invalid_times:
            assert validate_jitter_result(time) is False

    @pytest.mark.parametrize("minute,expected", [
        (0, False),
        (1, True),
        (14, True),
        (15, False),
        (16, True),
        (29, True),
        (30, False),
        (31, True),
        (44, True),
        (45, False),
        (46, True),
        (59, True),
    ])
    def test_validate_various_minutes(self, minute, expected):
        """Test validation for various minutes."""
        time = datetime(2025, 1, 15, 14, minute)
        assert validate_jitter_result(time) is expected


# =============================================================================
# Test get_jitter_stats
# =============================================================================


class TestGetJitterStats:
    """Tests for get_jitter_stats function."""

    def test_returns_dict(self):
        """Test function returns a dictionary."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")
        assert isinstance(stats, dict)

    def test_contains_expected_keys(self):
        """Test dict contains all expected keys."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")

        expected_keys = [
            'base_time',
            'jittered_time',
            'offset_minutes',
            'base_minute',
            'result_minute',
            'valid_offset_count',
        ]
        for key in expected_keys:
            assert key in stats

    def test_base_time_preserved(self):
        """Test base_time is preserved in stats."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")
        assert stats['base_time'] == base_time

    def test_base_minute_correct(self):
        """Test base_minute is extracted correctly."""
        base_time = datetime(2025, 1, 15, 14, 33)
        stats = get_jitter_stats(base_time, "creator_123")
        assert stats['base_minute'] == 33

    def test_result_minute_valid(self):
        """Test result_minute is not a round minute."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")
        assert stats['result_minute'] not in ROUND_MINUTES

    def test_offset_matches_difference(self):
        """Test offset matches the actual difference."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")

        actual_offset = int((stats['jittered_time'] - base_time).total_seconds() / 60)
        assert stats['offset_minutes'] == actual_offset

    def test_valid_offset_count_positive(self):
        """Test valid_offset_count is non-negative."""
        base_time = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base_time, "creator_123")
        assert stats['valid_offset_count'] >= 0

    @pytest.mark.parametrize("base_minute", [0, 15, 30, 45])
    def test_stats_for_round_minutes(self, base_minute):
        """Test stats work correctly for round minute inputs."""
        base_time = datetime(2025, 1, 15, 14, base_minute)
        stats = get_jitter_stats(base_time, "creator_123")

        assert stats['base_minute'] == base_minute
        assert stats['result_minute'] not in ROUND_MINUTES


# =============================================================================
# Integration Tests
# =============================================================================


class TestJitterIntegration:
    """Integration tests for the jitter system."""

    def test_jitter_applied_to_schedule(self):
        """Test jitter can be applied to a series of scheduled times."""
        schedule_times = [
            datetime(2025, 1, 15, 10, 0),
            datetime(2025, 1, 15, 14, 30),
            datetime(2025, 1, 15, 19, 0),
            datetime(2025, 1, 15, 22, 45),
        ]

        for base_time in schedule_times:
            result = apply_time_jitter(base_time, "creator_123")
            assert validate_jitter_result(result) is True

    def test_all_minutes_in_a_day(self):
        """Test jitter works for all minutes in a day."""
        for minute in range(60):
            base_time = datetime(2025, 1, 15, 14, minute)
            result = apply_time_jitter(base_time, "creator_123")
            assert validate_jitter_result(result) is True

    def test_multiple_creators_same_time(self):
        """Test multiple creators at same time all get valid jitter."""
        base_time = datetime(2025, 1, 15, 14, 30)
        creators = ["alice", "bob", "charlie", "diana", "eve"]

        for creator in creators:
            result = apply_time_jitter(base_time, creator)
            assert validate_jitter_result(result) is True

    def test_consistency_across_calls(self):
        """Test jitter is consistent across many calls."""
        base_time = datetime(2025, 1, 15, 14, 30)
        creator = "test_creator"

        results = [apply_time_jitter(base_time, creator) for _ in range(100)]

        # All results should be identical (deterministic)
        assert all(r == results[0] for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
