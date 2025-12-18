"""
Wave 2 Advanced Timing Tests

Comprehensive test suite for concurrent operations, boundary conditions,
recovery scenarios, and state transitions in the EROS timing system.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, List, Set, Tuple, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from ..orchestration.timing_saga import Wave2TimingSaga, SagaStatus
from ..orchestration.idempotency import IdempotencyGuard
from ..orchestration.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
)
from ..orchestration.rotation_tracker import (
    PPVRotationTracker,
    RotationState,
    VALID_TRANSITIONS,
    validate_transition,
    transition_to,
    InvalidTransitionError,
)
from ..orchestration.followup_generator import schedule_ppv_followup
from ..orchestration.timing_validator import validate_no_consecutive_same_style
from ..orchestration.timing_optimizer import apply_time_jitter


class TestConcurrency:
    """Tests for thread safety and concurrent operations."""

    def test_idempotency_guard_thread_safety(self) -> None:
        """Verify idempotency guard handles 100 concurrent calls correctly.

        All threads call check_and_store() with same operation/params.
        Exactly one should be non-duplicate (the first), rest are duplicates.
        """
        guard = IdempotencyGuard()
        operation = "test_operation"
        params = {"key": "value", "id": 12345}

        results: List[bool] = []
        errors: List[Exception] = []
        lock = threading.Lock()

        def check_operation(thread_id: int) -> bool:
            try:
                # check_and_store returns tuple[bool, Optional[Any]]
                # First element is is_duplicate
                is_duplicate, _ = guard.check_and_store(
                    operation, params, f"result_{thread_id}"
                )
                return is_duplicate
            except Exception as e:
                with lock:
                    errors.append(e)
                return False

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(check_operation, i) for i in range(100)]
            for future in as_completed(futures):
                results.append(future.result())

        # Exactly one non-duplicate (first call), rest are duplicates
        non_duplicates = sum(1 for r in results if not r)
        duplicates = sum(1 for r in results if r)

        assert non_duplicates == 1, f"Expected exactly 1 non-duplicate, got {non_duplicates}"
        assert duplicates == 99, f"Expected 99 duplicates, got {duplicates}"
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_circuit_breaker_thread_safety(self) -> None:
        """Verify circuit breaker handles concurrent failures correctly.

        Launch 50 concurrent threads that cause failures.
        Circuit should eventually open and reject some calls.
        """
        breaker = CircuitBreaker(
            name="test_concurrent_breaker",
            failure_threshold=5,
            recovery_timeout=1
        )

        executed_count = [0]  # Use list for thread-safe mutation
        rejected_count = [0]
        lock = threading.Lock()

        def cause_failure() -> None:
            try:
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("Simulated failure")))
            except CircuitOpenError:
                with lock:
                    rejected_count[0] += 1
            except ValueError:
                with lock:
                    executed_count[0] += 1

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(cause_failure) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        # Circuit should be open after enough failures
        assert breaker.state == CircuitState.OPEN, (
            f"Expected circuit to be OPEN, got {breaker.state}"
        )
        # Not all calls should have executed (some rejected after circuit opened)
        assert rejected_count[0] > 0 or executed_count[0] < 50, (
            "Expected some calls to be rejected after circuit opened"
        )

    def test_rotation_tracker_concurrent_updates(self) -> None:
        """Verify rotation tracker handles concurrent access correctly.

        Create 100 different trackers with different creator IDs.
        Run concurrent get_next_ppv_type(0) calls.
        All results should be valid PPV types.
        """
        valid_ppv_types: Set[str] = {"solo", "bundle", "winner", "sextape"}
        results: List[str] = []
        errors: List[Exception] = []

        def get_rotation_type(creator_id: str) -> str:
            try:
                tracker = PPVRotationTracker(creator_id=creator_id)
                return tracker.get_next_ppv_type(0)
            except Exception as e:
                errors.append(e)
                return ""

        creator_ids = [f"creator_{i}" for i in range(100)]

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(get_rotation_type, cid) for cid in creator_ids
            ]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        # All results should be valid PPV types
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert all(r in valid_ppv_types for r in results), (
            f"Invalid PPV types found: {set(results) - valid_ppv_types}"
        )


class TestBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    def test_followup_at_2359(self) -> None:
        """Test followup scheduling when parent is at 23:30.

        With allow_next_day=False, followup must stay on same day.
        The followup should be within 15-45 min window OR clamped to 23:59.
        """
        parent_time = datetime(2025, 1, 15, 23, 30)

        followup = schedule_ppv_followup(
            parent_ppv_time=parent_time,
            creator_id="test_boundary_creator",
            allow_next_day=False,
        )

        # Must be same date
        assert followup.date() == parent_time.date(), (
            f"Followup date {followup.date()} should match parent date {parent_time.date()}"
        )

        # Gap must be valid: either in 15-45 min window OR clamped because it would exceed midnight
        gap_minutes = (followup - parent_time).total_seconds() / 60
        assert 15 <= gap_minutes <= 45 or (followup.hour == 23 and followup.minute == 59), (
            f"Followup gap should be 15-45 min or clamped to 23:59, got {gap_minutes:.0f} min at {followup.strftime('%H:%M')}"
        )

    def test_followup_at_2350_with_next_day(self) -> None:
        """Test followup scheduling when parent is at 23:50 with next day allowed.

        Gap should be within 15-45 minutes even if it crosses midnight.
        """
        parent_time = datetime(2025, 1, 15, 23, 50)

        followup = schedule_ppv_followup(
            parent_ppv_time=parent_time,
            creator_id="test_nextday_creator",
            allow_next_day=True,
        )

        gap = (followup - parent_time).total_seconds() / 60

        assert 15 <= gap <= 45, (
            f"Followup gap should be 15-45 minutes, got {gap:.1f} minutes"
        )

    def test_empty_schedule_validation(self) -> None:
        """Test validation with empty schedule list.

        Empty schedule should be considered valid.
        """
        result = validate_no_consecutive_same_style([])

        assert result["is_valid"] is True, (
            "Empty schedule should be valid"
        )

    def test_single_item_schedule(self) -> None:
        """Test validation with single PPV item.

        Single item schedule should be valid regardless of style.
        """
        single_item = {
            "is_ppv": True,
            "ppv_style": "winner",
            "hour": 14
        }

        result = validate_no_consecutive_same_style([single_item])

        assert result["is_valid"] is True, (
            "Single item schedule should be valid"
        )

    def test_rotation_on_day_zero(self) -> None:
        """Test rotation tracker behavior on day zero.

        New tracker should return valid type immediately.
        """
        valid_ppv_types: Set[str] = {"solo", "bundle", "winner", "sextape"}
        unique_creator_id = f"creator_{uuid.uuid4().hex[:8]}"

        tracker = PPVRotationTracker(creator_id=unique_creator_id)
        result = tracker.get_next_ppv_type(0)

        assert result in valid_ppv_types, (
            f"Day zero should return valid PPV type, got '{result}'"
        )

    def test_jitter_at_minute_zero(self) -> None:
        """Test time jitter when base time is at :00.

        Jittered result should avoid round minutes (:00, :15, :30, :45).
        """
        base_time = datetime(2025, 1, 15, 14, 0)
        round_minutes = {0, 15, 30, 45}

        jittered = apply_time_jitter(base_time, creator_id="test_minute_zero")

        assert jittered.minute not in round_minutes, (
            f"Jittered time {jittered.strftime('%H:%M')} should avoid round minutes"
        )

    def test_jitter_at_minute_59(self) -> None:
        """Test time jitter when base time is at :59.

        Jittered result should avoid round minutes.
        """
        base_time = datetime(2025, 1, 15, 14, 59)
        round_minutes = {0, 15, 30, 45}

        jittered = apply_time_jitter(base_time, creator_id="test_minute_59")

        assert jittered.minute not in round_minutes, (
            f"Jittered time {jittered.strftime('%H:%M')} should avoid round minutes"
        )


class TestRecovery:
    """Tests for error recovery and saga patterns."""

    @pytest.mark.asyncio
    async def test_saga_compensation_on_failure(self) -> None:
        """Test saga rollback when a step fails.

        Mock _generate_followups to raise Exception.
        Saga should rollback and record completed/failed steps.
        """
        saga = Wave2TimingSaga(creator_id="test_saga_creator")

        with patch.object(
            saga,
            "_generate_followups",
            side_effect=Exception("Simulated followup generation failure"),
        ):
            result = await saga.execute([{"id": "1", "scheduled_time": datetime.now()}])

        assert result.status == SagaStatus.ROLLED_BACK, (
            f"Expected ROLLED_BACK status, got {result.status}"
        )
        assert len(result.completed_steps) > 0, (
            "Expected some completed steps before failure"
        )
        assert result.failed_step is not None, (
            "Expected failed_step to be recorded"
        )

    @pytest.mark.asyncio
    async def test_saga_timeout_handling(self) -> None:
        """Test saga behavior when a step times out.

        Mock a step to sleep 60 seconds (exceeds 30s timeout).
        Saga should fail or rollback with timeout message.
        """
        saga = Wave2TimingSaga(creator_id="test_timeout_creator")

        # Use sync time.sleep since asyncio.to_thread wraps sync functions
        def slow_step(*args, **kwargs):
            time.sleep(60)

        with patch.object(saga, "_validate_schedule", side_effect=slow_step):
            result = await saga.execute([{"id": "1", "scheduled_time": datetime.now()}])

        assert result.status in [SagaStatus.ROLLED_BACK, SagaStatus.FAILED], (
            f"Expected ROLLED_BACK or FAILED status, got {result.status}"
        )
        assert result.error is not None and "timed out" in result.error.lower(), (
            f"Expected 'timed out' in error message, got: {result.error}"
        )

    def test_circuit_breaker_recovery(self) -> None:
        """Test circuit breaker state transitions through full cycle.

        1. Cause failures -> OPEN
        2. Wait for recovery timeout -> HALF_OPEN
        3. Successful calls -> CLOSED
        """
        breaker = CircuitBreaker(
            name="test_recovery_breaker",
            failure_threshold=2,
            recovery_timeout=1
        )

        # Cause 3 failures to open the circuit
        for _ in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("Simulated failure")))
            except (ValueError, CircuitOpenError):
                pass

        assert breaker.state == CircuitState.OPEN, (
            f"Expected OPEN state after failures, got {breaker.state}"
        )

        # Wait for recovery timeout
        time.sleep(1.5)

        # Next call should transition to HALF_OPEN
        try:
            breaker.call(lambda: "success")  # Successful call
        except CircuitOpenError:
            pass

        # After timeout, state should be HALF_OPEN or CLOSED (if success counted)
        assert breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED], (
            f"Expected HALF_OPEN or CLOSED after recovery timeout, got {breaker.state}"
        )

        # Additional successful calls to fully close
        for _ in range(3):
            try:
                breaker.call(lambda: "success")
            except CircuitOpenError:
                pass

        assert breaker.state == CircuitState.CLOSED, (
            f"Expected CLOSED state after successful calls, got {breaker.state}"
        )

    def test_idempotency_expiration(self) -> None:
        """Test idempotency guard respects TTL expiration.

        Create guard with ttl_minutes=0 (immediate expiration).
        Second store with same params should NOT be duplicate.
        """
        guard = IdempotencyGuard(ttl_minutes=0)
        operation = "expiring_operation"
        params = {"key": "value"}

        # First call - not a duplicate (check_and_store returns tuple[bool, Optional[Any]])
        is_dup_first, _ = guard.check_and_store(operation, params, "result_1")
        assert is_dup_first is False, "First call should not be duplicate"

        # Wait for expiration
        time.sleep(0.1)

        # Second call - should NOT be duplicate due to expiration
        is_dup_second, _ = guard.check_and_store(operation, params, "result_2")
        assert is_dup_second is False, (
            "Second call should not be duplicate after TTL expiration"
        )


class TestStateTransitions:
    """Tests for state machine transitions."""

    def test_valid_state_transitions(self) -> None:
        """Test all valid transitions defined in VALID_TRANSITIONS.

        Every transition in VALID_TRANSITIONS should return True.
        """
        for from_state, valid_targets in VALID_TRANSITIONS.items():
            for target_state in valid_targets:
                result = validate_transition(from_state, target_state)
                assert result is True, (
                    f"Transition from {from_state} to {target_state} should be valid"
                )

    def test_invalid_state_transitions(self) -> None:
        """Test that invalid transitions are properly rejected.

        Specific invalid transitions should return False and raise errors.
        """
        # INITIALIZING -> ROTATING should be invalid (must go through PATTERN_ACTIVE first)
        result = validate_transition(RotationState.INITIALIZING, RotationState.ROTATING)
        assert result is False, (
            "INITIALIZING -> ROTATING should be invalid"
        )

        # ROTATING -> ROTATION_PENDING should be invalid (ROTATING can only go to PATTERN_ACTIVE or ERROR)
        result = validate_transition(
            RotationState.ROTATING,
            RotationState.ROTATION_PENDING,
        )
        assert result is False, (
            "ROTATING -> ROTATION_PENDING should be invalid"
        )

        # transition_to() should raise InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            transition_to(RotationState.INITIALIZING, RotationState.ROTATING)

    def test_error_recovery_transition(self) -> None:
        """Test that ERROR state can only transition to INITIALIZING.

        Error recovery should restart the state machine from INITIALIZING.
        """
        error_transitions = VALID_TRANSITIONS[RotationState.ERROR]

        # VALID_TRANSITIONS values are sets, not lists
        assert error_transitions == {RotationState.INITIALIZING}, (
            f"ERROR state should only transition to INITIALIZING, "
            f"got {error_transitions}"
        )
