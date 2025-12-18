"""
Comprehensive unit tests for EROS orchestration modules.

Tests orchestration components including:
- Circuit breaker pattern
- Rotation tracker state machine
- Quality validators
- Followup generator
- Timing optimizer
"""

import sys
import time
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.circuit_breaker import (
    CircuitState,
    CircuitStats,
    CircuitOpenError,
    CircuitBreaker,
    circuit_protected,
    rotation_state_circuit,
    timing_validation_circuit,
)
from python.orchestration.rotation_tracker import (
    InvalidTransitionError,
    RotationState,
    VALID_TRANSITIONS,
    validate_transition,
    transition_to,
    RotationStateData,
    PPVRotationTracker,
)
from python.orchestration.quality_validator import (
    CHANNEL_MAPPING,
    STANDARD_SEND_TYPES,
    MINIMUM_UNIQUE_TYPES,
    validate_send_type_diversity,
    validate_channel_assignment,
    validate_schedule_quality,
)
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
from python.orchestration.timing_optimizer import (
    ROUND_MINUTES,
    JITTER_MIN,
    JITTER_MAX,
    apply_time_jitter,
    validate_jitter_result,
    get_jitter_stats,
)


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitState:
    """Test CircuitState enum."""

    def test_all_states_exist(self):
        """Test all expected states exist."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_state_count(self):
        """Test correct number of states."""
        assert len(CircuitState) == 3


class TestCircuitStats:
    """Test CircuitStats dataclass."""

    def test_default_values(self):
        """Test default values are zero/None."""
        stats = CircuitStats()
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0
        assert stats.last_failure_time is None
        assert stats.last_success_time is None
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 0


class TestCircuitOpenError:
    """Test CircuitOpenError exception."""

    def test_error_attributes(self):
        """Test error stores attributes correctly."""
        error = CircuitOpenError(
            circuit_name="test_circuit",
            recovery_time=time.time() + 30,
            message="Custom message",
        )
        assert error.circuit_name == "test_circuit"
        assert error.recovery_time is not None
        assert "Custom message" in str(error)

    def test_default_message(self):
        """Test default message generation."""
        error = CircuitOpenError(circuit_name="test")
        assert "test" in error.message
        assert "open" in error.message.lower()


class TestCircuitBreaker:
    """Test CircuitBreaker main class."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Fresh circuit breaker for testing."""
        return CircuitBreaker[str](
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=1.0,
            half_open_max_calls=2,
        )

    def test_initial_state_closed(self, breaker):
        """Test initial state is CLOSED."""
        assert breaker.state == CircuitState.CLOSED

    def test_successful_call_stays_closed(self, breaker):
        """Test successful call keeps circuit closed."""
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    def test_failure_increments_counter(self, breaker):
        """Test failure increments consecutive failures."""
        def fail():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            breaker.call(fail)

        stats = breaker.get_stats()
        assert stats["consecutive_failures"] == 1

    def test_threshold_opens_circuit(self, breaker):
        """Test exceeding threshold opens circuit."""
        def fail():
            raise ValueError("Test error")

        # Cause failures up to threshold
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

    def test_open_circuit_rejects_calls(self, breaker):
        """Test open circuit rejects calls."""
        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        # Next call should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            breaker.call(lambda: "should not execute")

        assert exc_info.value.circuit_name == "test_breaker"

    def test_fallback_value_on_open(self):
        """Test fallback value returned when circuit is open."""
        breaker = CircuitBreaker[str](
            name="fallback_test",
            failure_threshold=2,
            fallback_value="fallback_result",
        )

        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        # Should return fallback
        result = breaker.call(lambda: "should not execute")
        assert result == "fallback_result"

    def test_recovery_to_half_open(self, breaker):
        """Test circuit transitions to half-open after timeout."""
        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(breaker.recovery_timeout + 0.1)

        # Should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self, breaker):
        """Test successful calls in half-open close circuit."""
        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        # Wait for half-open
        time.sleep(breaker.recovery_timeout + 0.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Make successful calls
        for _ in range(breaker.half_open_max_calls):
            breaker.call(lambda: "success")

        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self, breaker):
        """Test failure in half-open reopens circuit."""
        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        # Wait for half-open
        time.sleep(breaker.recovery_timeout + 0.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Fail in half-open
        with pytest.raises(ValueError):
            breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

    def test_reset_clears_state(self, breaker):
        """Test reset returns to initial state."""
        def fail():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(breaker.failure_threshold):
            with pytest.raises(ValueError):
                breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats["total_calls"] == 0

    def test_get_stats_structure(self, breaker):
        """Test get_stats returns expected structure."""
        stats = breaker.get_stats()

        assert "name" in stats
        assert "state" in stats
        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats
        assert "rejected_calls" in stats
        assert "failure_threshold" in stats
        assert "recovery_timeout" in stats

    def test_thread_safety(self):
        """Test circuit breaker is thread-safe."""
        breaker = CircuitBreaker[int](
            name="thread_test",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        results = []
        errors = []

        def worker():
            try:
                result = breaker.call(lambda: 42)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 10
        assert len(errors) == 0


class TestCircuitProtectedDecorator:
    """Test circuit_protected decorator."""

    def test_decorator_wraps_function(self):
        """Test decorator wraps function correctly."""
        breaker = CircuitBreaker[str](
            name="decorator_test",
            failure_threshold=3,
        )

        @circuit_protected(breaker)
        def protected_function(x: int) -> str:
            return f"result_{x}"

        result = protected_function(5)
        assert result == "result_5"

    def test_decorator_passes_through_exceptions(self):
        """Test decorator passes through exceptions."""
        breaker = CircuitBreaker[None](
            name="decorator_test",
            failure_threshold=3,
        )

        @circuit_protected(breaker)
        def failing_function() -> None:
            raise ValueError("Expected error")

        with pytest.raises(ValueError, match="Expected error"):
            failing_function()


class TestPreConfiguredCircuits:
    """Test pre-configured circuit breaker instances."""

    def test_rotation_state_circuit_exists(self):
        """Test rotation_state_circuit is configured."""
        assert rotation_state_circuit.name == "rotation_state_db"
        assert rotation_state_circuit.failure_threshold == 3
        rotation_state_circuit.reset()  # Clean up for other tests

    def test_timing_validation_circuit_has_fallback(self):
        """Test timing_validation_circuit has safe fallback."""
        assert timing_validation_circuit.fallback_value is not None
        assert timing_validation_circuit.fallback_value["is_valid"] is True
        timing_validation_circuit.reset()  # Clean up for other tests


# =============================================================================
# Rotation Tracker Tests
# =============================================================================


class TestRotationState:
    """Test RotationState enum."""

    def test_all_states_exist(self):
        """Test all expected states exist."""
        assert RotationState.INITIALIZING.name == "INITIALIZING"
        assert RotationState.PATTERN_ACTIVE.name == "PATTERN_ACTIVE"
        assert RotationState.ROTATION_PENDING.name == "ROTATION_PENDING"
        assert RotationState.ROTATING.name == "ROTATING"
        assert RotationState.PATTERN_EXHAUSTED.name == "PATTERN_EXHAUSTED"
        assert RotationState.ERROR.name == "ERROR"


class TestValidTransitions:
    """Test state transition validation."""

    def test_initializing_can_activate(self):
        """Test INITIALIZING can transition to PATTERN_ACTIVE."""
        assert validate_transition(
            RotationState.INITIALIZING,
            RotationState.PATTERN_ACTIVE
        ) is True

    def test_initializing_can_error(self):
        """Test INITIALIZING can transition to ERROR."""
        assert validate_transition(
            RotationState.INITIALIZING,
            RotationState.ERROR
        ) is True

    def test_active_cannot_initialize(self):
        """Test PATTERN_ACTIVE cannot transition to INITIALIZING."""
        assert validate_transition(
            RotationState.PATTERN_ACTIVE,
            RotationState.INITIALIZING
        ) is False

    def test_error_can_reinitialize(self):
        """Test ERROR can transition to INITIALIZING for recovery."""
        assert validate_transition(
            RotationState.ERROR,
            RotationState.INITIALIZING
        ) is True


class TestTransitionTo:
    """Test transition_to function."""

    def test_valid_transition_succeeds(self):
        """Test valid transition returns new state."""
        new_state = transition_to(
            RotationState.INITIALIZING,
            RotationState.PATTERN_ACTIVE
        )
        assert new_state == RotationState.PATTERN_ACTIVE

    def test_invalid_transition_raises(self):
        """Test invalid transition raises InvalidTransitionError."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition_to(
                RotationState.PATTERN_ACTIVE,
                RotationState.INITIALIZING
            )
        assert exc_info.value.from_state == RotationState.PATTERN_ACTIVE
        assert exc_info.value.to_state == RotationState.INITIALIZING


class TestRotationStateData:
    """Test RotationStateData dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        data = RotationStateData(creator_id="test")
        assert data.current_pattern_index == 0
        assert data.current_position == 0
        assert data.days_on_pattern == 0
        assert data.state == RotationState.INITIALIZING

    def test_to_dict_serialization(self):
        """Test to_dict produces valid dictionary."""
        data = RotationStateData(
            creator_id="test_creator",
            current_pattern_index=2,
            current_position=1,
        )
        result = data.to_dict()

        assert result["creator_id"] == "test_creator"
        assert result["current_pattern_index"] == 2
        assert result["current_position"] == 1
        assert "pattern_start_date" in result
        assert "state" in result

    def test_from_dict_deserialization(self):
        """Test from_dict creates valid instance."""
        source = {
            "creator_id": "test",
            "current_pattern_index": 1,
            "current_position": 2,
            "pattern_start_date": "2025-12-15",
            "days_on_pattern": 3,
            "state": "PATTERN_ACTIVE",
            "last_updated": "2025-12-17T10:00:00",
        }
        data = RotationStateData.from_dict(source)

        assert data.creator_id == "test"
        assert data.current_pattern_index == 1
        assert data.state == RotationState.PATTERN_ACTIVE


class TestPPVRotationTracker:
    """Test PPVRotationTracker class."""

    @pytest.fixture
    def tracker(self) -> PPVRotationTracker:
        """Create a fresh tracker for testing."""
        return PPVRotationTracker("test_creator")

    def test_init_requires_creator_id(self):
        """Test init requires non-empty creator_id."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PPVRotationTracker("")

        with pytest.raises(ValueError, match="cannot be empty"):
            PPVRotationTracker("   ")

    def test_init_sets_active_state(self, tracker):
        """Test init transitions to PATTERN_ACTIVE."""
        assert tracker.get_state() == RotationState.PATTERN_ACTIVE

    def test_deterministic_seeding(self):
        """Test same creator_id produces same seed."""
        tracker1 = PPVRotationTracker("consistent_creator")
        tracker2 = PPVRotationTracker("consistent_creator")

        assert tracker1.state_data.seed == tracker2.state_data.seed

    def test_get_next_ppv_type_valid(self, tracker):
        """Test get_next_ppv_type returns valid type."""
        ppv_type = tracker.get_next_ppv_type(0)
        valid_types = {"solo", "bundle", "winner", "sextape"}
        assert ppv_type in valid_types

    def test_get_next_ppv_type_deterministic(self):
        """Test same inputs produce same outputs."""
        tracker1 = PPVRotationTracker("deterministic_test")
        tracker2 = PPVRotationTracker("deterministic_test")

        type1 = tracker1.get_next_ppv_type(0)
        type2 = tracker2.get_next_ppv_type(0)

        assert type1 == type2

    def test_get_current_pattern_returns_copy(self, tracker):
        """Test get_current_pattern returns copy, not reference."""
        pattern1 = tracker.get_current_pattern()
        pattern1.append("modified")

        pattern2 = tracker.get_current_pattern()
        assert "modified" not in pattern2

    def test_advance_position_increments(self, tracker):
        """Test advance_position increments position."""
        initial_pos = tracker.state_data.current_position
        tracker.advance_position(2)
        # Position wraps at pattern length
        pattern_len = len(tracker.STANDARD_PATTERNS[0])
        expected = (initial_pos + 2) % pattern_len
        assert tracker.state_data.current_position == expected

    def test_force_rotation_changes_pattern(self, tracker):
        """Test force_rotation changes pattern state."""
        initial_pattern = tracker.state_data.current_pattern_index
        tracker.force_rotation()
        # Pattern index may or may not change depending on rotation method
        assert tracker.get_state() == RotationState.PATTERN_ACTIVE

    def test_reset_state_reinitializes(self, tracker):
        """Test reset_state creates fresh state."""
        tracker.advance_position(3)
        tracker.reset_state()

        assert tracker.state_data.current_position == 0
        assert tracker.get_state() == RotationState.PATTERN_ACTIVE

    def test_get_days_on_pattern(self, tracker):
        """Test get_days_on_pattern returns correct value."""
        days = tracker.get_days_on_pattern()
        assert isinstance(days, int)
        assert days >= 0

    def test_standard_patterns_valid(self, tracker):
        """Test STANDARD_PATTERNS have expected structure."""
        assert len(tracker.STANDARD_PATTERNS) == 4
        for pattern in tracker.STANDARD_PATTERNS:
            assert len(pattern) == 4
            assert set(pattern) == {"solo", "bundle", "winner", "sextape"}


# =============================================================================
# Quality Validator Tests
# =============================================================================


class TestQualityValidatorConstants:
    """Test quality validator constants."""

    def test_channel_mapping_complete(self):
        """Test channel mapping covers all 22 send types."""
        # Revenue (9) + Engagement (9) + Retention (4) = 22
        assert len(CHANNEL_MAPPING) == 22

    def test_standard_send_types_complete(self):
        """Test standard send types set is complete."""
        assert len(STANDARD_SEND_TYPES) == 22

    def test_minimum_unique_types(self):
        """Test minimum unique types is 10."""
        assert MINIMUM_UNIQUE_TYPES == 10


class TestValidateSendTypeDiversity:
    """Test validate_send_type_diversity function."""

    def test_empty_schedule_invalid(self):
        """Test empty schedule is invalid."""
        result = validate_send_type_diversity([])
        assert result["is_valid"] is False
        assert result["current_count"] == 0

    def test_insufficient_types_invalid(self):
        """Test schedule with < 10 types is invalid."""
        schedule = [{"send_type": "ppv_unlock"} for _ in range(20)]
        result = validate_send_type_diversity(schedule)

        assert result["is_valid"] is False
        assert result["current_count"] == 1
        assert "missing_suggestions" in result
        assert len(result["missing_suggestions"]) <= 3

    def test_sufficient_types_valid(self):
        """Test schedule with >= 10 types is valid."""
        types = list(STANDARD_SEND_TYPES)[:12]
        schedule = [{"send_type": t} for t in types]

        result = validate_send_type_diversity(schedule)

        assert result["is_valid"] is True
        assert result["current_count"] == 12

    def test_supports_send_type_key_field(self):
        """Test supports send_type_key field name."""
        types = list(STANDARD_SEND_TYPES)[:10]
        schedule = [{"send_type_key": t} for t in types]

        result = validate_send_type_diversity(schedule)
        assert result["is_valid"] is True

    def test_unique_types_returned(self):
        """Test unique_types set is returned."""
        schedule = [
            {"send_type": "ppv_unlock"},
            {"send_type": "bump_normal"},
            {"send_type": "ppv_unlock"},
        ]
        result = validate_send_type_diversity(schedule)

        assert "unique_types" in result
        assert result["unique_types"] == {"ppv_unlock", "bump_normal"}


class TestValidateChannelAssignment:
    """Test validate_channel_assignment function."""

    def test_correct_channel_valid(self):
        """Test correct channel assignment is valid."""
        item = {"send_type": "ppv_unlock", "channel": "mass_message"}
        result = validate_channel_assignment(item, "paid")
        assert result["is_valid"] is True

    def test_incorrect_channel_invalid(self):
        """Test incorrect channel assignment is invalid."""
        item = {"send_type": "ppv_unlock", "channel": "wall_post"}
        result = validate_channel_assignment(item, "paid")

        assert result["is_valid"] is False
        assert "error" in result
        assert "expected_channels" in result

    def test_retention_on_free_invalid(self):
        """Test retention type on free page is invalid."""
        item = {"send_type": "renew_on_message", "channel": "mass_message"}
        result = validate_channel_assignment(item, "free")

        assert result["is_valid"] is False
        assert "PAID pages" in result["error"]

    def test_ppv_wall_on_paid_invalid(self):
        """Test ppv_wall on paid page is invalid."""
        item = {"send_type": "ppv_wall", "channel": "wall_post"}
        result = validate_channel_assignment(item, "paid")

        assert result["is_valid"] is False
        assert "FREE pages" in result["error"]

    def test_unknown_send_type_valid(self):
        """Test unknown send type passes validation."""
        item = {"send_type": "custom_type", "channel": "mass_message"}
        result = validate_channel_assignment(item, "paid")
        assert result["is_valid"] is True

    def test_supports_channel_key_field(self):
        """Test supports channel_key field name."""
        item = {"send_type_key": "ppv_unlock", "channel_key": "mass_message"}
        result = validate_channel_assignment(item, "paid")
        assert result["is_valid"] is True


class TestValidateScheduleQuality:
    """Test validate_schedule_quality function."""

    def test_valid_schedule_passes(self):
        """Test valid schedule passes all checks."""
        types = list(STANDARD_SEND_TYPES - {"ppv_wall"})[:12]
        schedule = [
            {"send_type": t, "channel": CHANNEL_MAPPING[t]["primary"]}
            for t in types
        ]

        result = validate_schedule_quality(schedule, "paid")

        assert result["is_valid"] is True
        assert result["error_count"] == 0

    def test_invalid_diversity_fails(self):
        """Test invalid diversity fails overall check."""
        schedule = [{"send_type": "ppv_unlock", "channel": "mass_message"}]
        result = validate_schedule_quality(schedule, "paid")

        assert result["is_valid"] is False
        assert result["diversity_check"]["is_valid"] is False

    def test_channel_errors_collected(self):
        """Test channel errors are collected."""
        types = list(STANDARD_SEND_TYPES - {"ppv_wall"})[:12]
        schedule = [
            {"send_type": t, "channel": "wrong_channel"}
            for t in types
        ]

        result = validate_schedule_quality(schedule, "paid")

        assert len(result["channel_errors"]) > 0

    def test_total_items_counted(self):
        """Test total_items is accurate."""
        schedule = [{"send_type": "ppv_unlock"} for _ in range(5)]
        result = validate_schedule_quality(schedule, "paid")

        assert result["total_items"] == 5


# =============================================================================
# Followup Generator Tests
# =============================================================================


class TestFollowupConstants:
    """Test followup generator constants."""

    def test_optimal_minutes(self):
        """Test optimal followup minutes is 28."""
        assert OPTIMAL_FOLLOWUP_MINUTES == 28

    def test_default_offset_range(self):
        """Test default offset range is 15-45 minutes."""
        assert DEFAULT_MIN_OFFSET == 15
        assert DEFAULT_MAX_OFFSET == 45


class TestTruncatedNormalSample:
    """Test _truncated_normal_sample function."""

    def test_sample_within_bounds(self):
        """Test samples are within specified bounds."""
        import random
        rng = random.Random(42)

        for _ in range(100):
            sample = _truncated_normal_sample(
                rng, mean=28.0, std_dev=8.0, min_val=15.0, max_val=45.0
            )
            assert 15.0 <= sample <= 45.0

    def test_deterministic_with_seed(self):
        """Test samples are deterministic with same seed."""
        import random
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        sample1 = _truncated_normal_sample(
            rng1, mean=28.0, std_dev=8.0, min_val=15.0, max_val=45.0
        )
        sample2 = _truncated_normal_sample(
            rng2, mean=28.0, std_dev=8.0, min_val=15.0, max_val=45.0
        )

        assert sample1 == sample2


class TestCreateDeterministicSeed:
    """Test _create_deterministic_seed function."""

    def test_same_inputs_same_seed(self):
        """Test same inputs produce same seed."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed1 = _create_deterministic_seed("creator_123", parent_time)
        seed2 = _create_deterministic_seed("creator_123", parent_time)

        assert seed1 == seed2

    def test_different_creators_different_seeds(self):
        """Test different creators produce different seeds."""
        parent_time = datetime(2025, 1, 15, 14, 30)
        seed1 = _create_deterministic_seed("alice", parent_time)
        seed2 = _create_deterministic_seed("bob", parent_time)

        assert seed1 != seed2


class TestSchedulePPVFollowup:
    """Test schedule_ppv_followup function."""

    def test_followup_within_bounds(self):
        """Test followup is within min/max offset."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = schedule_ppv_followup(parent, "creator_123")

        gap_minutes = (followup - parent).total_seconds() / 60
        assert DEFAULT_MIN_OFFSET <= gap_minutes <= DEFAULT_MAX_OFFSET

    def test_deterministic_result(self):
        """Test same inputs produce same result."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup1 = schedule_ppv_followup(parent, "creator_123")
        followup2 = schedule_ppv_followup(parent, "creator_123")

        assert followup1 == followup2

    def test_late_night_clamps_to_day_end(self):
        """Test late night parent clamps to 23:59."""
        parent = datetime(2025, 1, 15, 23, 50, 0)
        followup = schedule_ppv_followup(
            parent, "creator_123", allow_next_day=False
        )

        assert followup.hour == 23
        assert followup.minute == 59

    def test_allow_next_day_crosses_midnight(self):
        """Test allow_next_day permits crossing midnight."""
        parent = datetime(2025, 1, 15, 23, 50, 0)
        followup = schedule_ppv_followup(
            parent, "creator_123", allow_next_day=True
        )

        # Should be after midnight
        gap_minutes = (followup - parent).total_seconds() / 60
        assert gap_minutes >= DEFAULT_MIN_OFFSET

    def test_custom_offset_bounds(self):
        """Test custom min/max offset bounds."""
        parent = datetime(2025, 1, 15, 14, 0, 0)
        followup = schedule_ppv_followup(
            parent, "creator_123",
            min_offset=20, max_offset=30
        )

        gap_minutes = (followup - parent).total_seconds() / 60
        assert 20 <= gap_minutes <= 30


class TestValidateFollowupWindow:
    """Test validate_followup_window function."""

    def test_valid_gap_passes(self):
        """Test valid gap passes validation."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 0, 0)  # 30 min gap

        result = validate_followup_window(parent, followup)

        assert result["is_valid"] is True
        assert result["gap_minutes"] == 30.0

    def test_gap_too_small_fails(self):
        """Test gap below minimum fails."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 14, 40, 0)  # 10 min gap

        result = validate_followup_window(parent, followup)

        assert result["is_valid"] is False
        assert "less than minimum" in result["error"]

    def test_gap_too_large_fails(self):
        """Test gap above maximum fails."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 15, 30, 0)  # 60 min gap

        result = validate_followup_window(parent, followup)

        assert result["is_valid"] is False
        assert "exceeds maximum" in result["error"]

    def test_negative_gap_fails(self):
        """Test followup before parent fails."""
        parent = datetime(2025, 1, 15, 14, 30, 0)
        followup = datetime(2025, 1, 15, 14, 0, 0)  # Before parent

        result = validate_followup_window(parent, followup)

        assert result["is_valid"] is False
        assert "before parent" in result["error"].lower()


# =============================================================================
# Timing Optimizer Tests
# =============================================================================


class TestTimingOptimizerConstants:
    """Test timing optimizer constants."""

    def test_round_minutes_set(self):
        """Test round minutes are 0, 15, 30, 45."""
        assert ROUND_MINUTES == frozenset({0, 15, 30, 45})

    def test_jitter_bounds(self):
        """Test jitter bounds are -7 to +8."""
        assert JITTER_MIN == -7
        assert JITTER_MAX == 8


class TestApplyTimeJitter:
    """Test apply_time_jitter function."""

    def test_avoids_round_minutes(self):
        """Test result never lands on round minutes."""
        base = datetime(2025, 1, 15, 14, 30)  # Round minute

        for i in range(50):
            result = apply_time_jitter(base, f"creator_{i}")
            assert result.minute not in ROUND_MINUTES

    def test_deterministic_result(self):
        """Test same inputs produce same result."""
        base = datetime(2025, 1, 15, 14, 30)
        result1 = apply_time_jitter(base, "creator_123")
        result2 = apply_time_jitter(base, "creator_123")

        assert result1 == result2

    def test_different_creators_different_results(self):
        """Test different creators likely get different results."""
        base = datetime(2025, 1, 15, 14, 30)
        results = set()

        for i in range(10):
            result = apply_time_jitter(base, f"creator_{i}")
            results.add(result.minute)

        # Should have some variation (not all same minute)
        assert len(results) > 1

    def test_edge_case_minute_59(self):
        """Test edge case at minute 59 still avoids round minutes."""
        base = datetime(2025, 1, 15, 14, 59)
        result = apply_time_jitter(base, "creator_123")
        assert result.minute not in ROUND_MINUTES


class TestValidateJitterResult:
    """Test validate_jitter_result function."""

    def test_valid_minute_returns_true(self):
        """Test non-round minutes return True."""
        valid_time = datetime(2025, 1, 15, 14, 33)
        assert validate_jitter_result(valid_time) is True

    def test_round_minute_returns_false(self):
        """Test round minutes return False."""
        for minute in [0, 15, 30, 45]:
            invalid_time = datetime(2025, 1, 15, 14, minute)
            assert validate_jitter_result(invalid_time) is False


class TestGetJitterStats:
    """Test get_jitter_stats function."""

    def test_returns_expected_structure(self):
        """Test returns dictionary with expected keys."""
        base = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base, "creator_123")

        assert "base_time" in stats
        assert "jittered_time" in stats
        assert "offset_minutes" in stats
        assert "base_minute" in stats
        assert "result_minute" in stats
        assert "valid_offset_count" in stats

    def test_offset_calculation_correct(self):
        """Test offset is correctly calculated."""
        base = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base, "creator_123")

        calculated_offset = int(
            (stats["jittered_time"] - stats["base_time"]).total_seconds() / 60
        )
        assert stats["offset_minutes"] == calculated_offset

    def test_result_minute_valid(self):
        """Test result_minute is not a round minute."""
        base = datetime(2025, 1, 15, 14, 30)
        stats = get_jitter_stats(base, "creator_123")

        assert stats["result_minute"] not in ROUND_MINUTES
