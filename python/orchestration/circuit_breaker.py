"""
Circuit Breaker Pattern for Database Operations.

Implements the Circuit Breaker pattern to protect the system from cascading
failures when database operations fail repeatedly. The circuit breaker has
three states:

- CLOSED: Normal operation, requests pass through
- OPEN: Circuit is tripped, requests are rejected immediately
- HALF_OPEN: Testing recovery, limited requests allowed

The pattern prevents resource exhaustion and allows failing services to recover
while providing fallback behavior for clients.

Usage:
    from python.orchestration.circuit_breaker import (
        rotation_state_circuit,
        timing_validation_circuit,
        circuit_protected,
        CircuitBreaker,
    )

    # Using pre-configured circuits
    result = rotation_state_circuit.call(lambda: db.get_rotation_state(creator_id))

    # Using decorator
    @circuit_protected(rotation_state_circuit)
    def get_rotation_state(creator_id: str) -> dict:
        return db.query(...)
"""

from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Type Variables
# =============================================================================

T = TypeVar("T")


# =============================================================================
# Circuit State Enum
# =============================================================================


class CircuitState(Enum):
    """Represents the three states of a circuit breaker.

    States:
        CLOSED: Normal operation - requests pass through to the underlying service.
            Failures are counted, and the circuit opens after exceeding the threshold.

        OPEN: Circuit is tripped - requests are immediately rejected without calling
            the underlying service. After the recovery timeout, transitions to HALF_OPEN.

        HALF_OPEN: Testing recovery - a limited number of test requests are allowed.
            If they succeed, the circuit closes. If any fails, it opens again.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# =============================================================================
# Circuit Statistics
# =============================================================================


@dataclass
class CircuitStats:
    """Statistics tracking for circuit breaker operations.

    Tracks call counts, success/failure rates, and timing information
    for monitoring and debugging circuit breaker behavior.

    Attributes:
        total_calls: Total number of calls attempted through the circuit.
        successful_calls: Number of calls that completed successfully.
        failed_calls: Number of calls that failed (exceptions raised).
        rejected_calls: Number of calls rejected due to open circuit.
        last_failure_time: Timestamp of the most recent failure.
        last_success_time: Timestamp of the most recent success.
        consecutive_failures: Current count of consecutive failures.
        consecutive_successes: Current count of consecutive successes.
    """

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


# =============================================================================
# Circuit Open Exception
# =============================================================================


class CircuitOpenError(Exception):
    """Raised when a call is rejected due to an open circuit.

    This exception indicates that the circuit breaker has tripped and is
    not allowing requests through. The caller should handle this gracefully,
    typically by using a fallback value or notifying the user.

    Attributes:
        circuit_name: Name of the circuit that rejected the call.
        recovery_time: Estimated time when recovery will be attempted.
        message: Human-readable error description.
    """

    def __init__(
        self,
        circuit_name: str,
        recovery_time: float | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize CircuitOpenError.

        Args:
            circuit_name: Name of the circuit that rejected the call.
            recovery_time: Unix timestamp when recovery will be attempted.
            message: Optional custom error message.
        """
        self.circuit_name = circuit_name
        self.recovery_time = recovery_time
        self.message = message or f"Circuit '{circuit_name}' is open"
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return formatted error string."""
        if self.recovery_time:
            seconds_until_recovery = max(0, self.recovery_time - time.time())
            return f"{self.message} (recovery in {seconds_until_recovery:.1f}s)"
        return self.message


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================


class CircuitBreaker(Generic[T]):
    """Thread-safe circuit breaker for protecting external service calls.

    Implements the Circuit Breaker pattern with automatic state transitions:

    CLOSED -> OPEN: When consecutive failures exceed failure_threshold
    OPEN -> HALF_OPEN: Automatically after recovery_timeout seconds
    HALF_OPEN -> CLOSED: After half_open_max_calls consecutive successes
    HALF_OPEN -> OPEN: On any failure

    Example:
        circuit = CircuitBreaker[dict](
            name="db_circuit",
            failure_threshold=3,
            recovery_timeout=30,
        )

        try:
            result = circuit.call(lambda: database.query(sql))
        except CircuitOpenError:
            result = fallback_value

    Attributes:
        name: Unique identifier for this circuit breaker.
        failure_threshold: Failures required to open the circuit.
        recovery_timeout: Seconds to wait before testing recovery.
        half_open_max_calls: Successes required to close from half-open.
        fallback_value: Optional default value when circuit is open.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        fallback_value: T | None = None,
    ) -> None:
        """Initialize CircuitBreaker.

        Args:
            name: Unique identifier for this circuit breaker instance.
            failure_threshold: Number of consecutive failures before opening.
            recovery_timeout: Seconds to wait before attempting recovery.
            half_open_max_calls: Consecutive successes needed to close circuit.
            fallback_value: Value to return when circuit is open (if provided).
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.fallback_value = fallback_value

        # Internal state
        self._state = CircuitState.CLOSED
        self._opened_at: float | None = None
        self._half_open_successes: int = 0
        self._stats = CircuitStats()

        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                "circuit_name": name,
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout,
                "half_open_max_calls": half_open_max_calls,
                "has_fallback": fallback_value is not None,
            },
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state with automatic OPEN -> HALF_OPEN transition.

        Checks if the recovery timeout has elapsed when in OPEN state and
        automatically transitions to HALF_OPEN for recovery testing.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN).
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._opened_at is not None:
                    elapsed = time.time() - self._opened_at
                    if elapsed >= self.recovery_timeout:
                        self._transition_to(CircuitState.HALF_OPEN)

            return self._state

    def call(self, func: Callable[[], T]) -> T:
        """Execute a function through the circuit breaker.

        Manages the circuit breaker state machine and either:
        - Executes the function and records success/failure
        - Rejects the call if circuit is open (raises CircuitOpenError or returns fallback)

        IMPORTANT: The function is executed OUTSIDE the lock to avoid blocking
        other threads during potentially long-running operations.

        Args:
            func: Zero-argument callable to execute.

        Returns:
            Result from func, or fallback_value if circuit is open and fallback exists.

        Raises:
            CircuitOpenError: If circuit is open and no fallback_value is configured.
            Exception: Any exception raised by func is re-raised after recording failure.
        """
        # Check state and update stats atomically
        current_state = self.state  # This triggers auto-transition

        with self._lock:
            self._stats.total_calls += 1

            if current_state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                recovery_time = None
                if self._opened_at is not None:
                    recovery_time = self._opened_at + self.recovery_timeout

                logger.warning(
                    f"Call rejected by circuit '{self.name}'",
                    extra={
                        "circuit_name": self.name,
                        "state": current_state.value,
                        "rejected_calls": self._stats.rejected_calls,
                    },
                )

                if self.fallback_value is not None:
                    logger.info(
                        f"Returning fallback value for circuit '{self.name}'",
                        extra={"circuit_name": self.name},
                    )
                    return self.fallback_value
                raise CircuitOpenError(self.name, recovery_time)

        # Execute function OUTSIDE the lock to avoid blocking
        try:
            result = func()
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure(exc)
            raise

    def _record_success(self) -> None:
        """Record a successful call and handle state transitions.

        Updates statistics and transitions HALF_OPEN -> CLOSED after
        half_open_max_calls consecutive successes.
        """
        with self._lock:
            self._stats.successful_calls += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                logger.debug(
                    f"Half-open success for circuit '{self.name}'",
                    extra={
                        "circuit_name": self.name,
                        "half_open_successes": self._half_open_successes,
                        "required": self.half_open_max_calls,
                    },
                )

                if self._half_open_successes >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, exc: Exception) -> None:
        """Record a failed call and handle state transitions.

        Updates statistics and handles state transitions:
        - CLOSED -> OPEN: After failure_threshold consecutive failures
        - HALF_OPEN -> OPEN: On any failure

        Args:
            exc: The exception that caused the failure.
        """
        with self._lock:
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = datetime.now()

            logger.warning(
                f"Failure recorded for circuit '{self.name}'",
                extra={
                    "circuit_name": self.name,
                    "state": self._state.value,
                    "consecutive_failures": self._stats.consecutive_failures,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)[:200],
                },
            )

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens the circuit
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                # Check if we've exceeded the failure threshold
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state.

        Logs the transition and updates internal state tracking.
        Must be called with lock held.

        Args:
            new_state: The state to transition to.
        """
        old_state = self._state
        self._state = new_state

        # Update state-specific tracking
        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_successes = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._half_open_successes = 0
            self._stats.consecutive_failures = 0

        logger.info(
            f"Circuit '{self.name}' state transition: {old_state.value} -> {new_state.value}",
            extra={
                "circuit_name": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "total_calls": self._stats.total_calls,
                "failed_calls": self._stats.failed_calls,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get current circuit breaker statistics.

        Returns a dictionary with all statistics and current state,
        useful for monitoring and debugging.

        Returns:
            Dictionary containing circuit statistics and state information.
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,  # Use property to trigger auto-transition
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "last_failure_time": (
                    self._stats.last_failure_time.isoformat()
                    if self._stats.last_failure_time
                    else None
                ),
                "last_success_time": (
                    self._stats.last_success_time.isoformat()
                    if self._stats.last_success_time
                    else None
                ),
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "half_open_max_calls": self.half_open_max_calls,
                "has_fallback": self.fallback_value is not None,
            }

    def reset(self) -> None:
        """Reset the circuit breaker to initial CLOSED state.

        Clears all statistics and resets state. Useful for testing
        or manual intervention.
        """
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._half_open_successes = 0
            self._stats = CircuitStats()

            logger.info(
                f"Circuit '{self.name}' manually reset from {old_state.value}",
                extra={
                    "circuit_name": self.name,
                    "old_state": old_state.value,
                },
            )


# =============================================================================
# Decorator
# =============================================================================


def circuit_protected(
    circuit: CircuitBreaker[T],
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to protect a function with a circuit breaker.

    Wraps a function so all calls pass through the specified circuit breaker.
    The function must return type T (matching the circuit breaker's type).

    Example:
        @circuit_protected(rotation_state_circuit)
        def get_rotation_state(creator_id: str) -> dict | None:
            return db.query(...)

    Args:
        circuit: CircuitBreaker instance to use for protection.

    Returns:
        Decorator function that wraps the target function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return circuit.call(lambda: func(*args, **kwargs))

        return wrapper

    return decorator


# =============================================================================
# Pre-configured Circuit Breaker Instances
# =============================================================================

# Circuit breaker for rotation state database operations
# Used for tracking caption rotation and preventing over-use
rotation_state_circuit: CircuitBreaker[Any] = CircuitBreaker(
    name="rotation_state_db",
    failure_threshold=3,
    recovery_timeout=30.0,
    half_open_max_calls=3,
    fallback_value=None,
)

# Circuit breaker for timing validation operations
# Returns safe fallback that allows schedule generation to continue
timing_validation_circuit: CircuitBreaker[dict[str, Any]] = CircuitBreaker(
    name="timing_validation",
    failure_threshold=5,
    recovery_timeout=15.0,
    half_open_max_calls=3,
    fallback_value={"is_valid": True, "errors": [], "fallback": True},
)


# =============================================================================
# Export Public API
# =============================================================================

__all__ = [
    # Enums
    "CircuitState",
    # Dataclasses
    "CircuitStats",
    # Exceptions
    "CircuitOpenError",
    # Main class
    "CircuitBreaker",
    # Decorator
    "circuit_protected",
    # Pre-configured instances
    "rotation_state_circuit",
    "timing_validation_circuit",
]
