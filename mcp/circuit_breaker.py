"""
Circuit Breaker Pattern for MCP Database Operations.

Prevents cascade failures by detecting unhealthy database states
and failing fast instead of overwhelming the connection pool.
"""
from enum import Enum
from time import time
from typing import Any, Callable, TypeVar, Optional
import threading
import os
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation - requests pass through
    OPEN = "open"          # Failing - reject requests immediately
    HALF_OPEN = "half_open"  # Testing recovery - limited requests


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    """Circuit breaker for database operations.

    Configuration via environment variables:
    - EROS_CB_FAILURE_THRESHOLD: Failures before opening (default: 5)
    - EROS_CB_TIMEOUT: Seconds before trying half-open (default: 60)
    - EROS_CB_SUCCESS_THRESHOLD: Successes to close from half-open (default: 2)
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: Optional[int] = None,
        timeout: Optional[int] = None,
        success_threshold: Optional[int] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold or int(
            os.environ.get("EROS_CB_FAILURE_THRESHOLD", "5")
        )
        self.timeout = timeout or int(
            os.environ.get("EROS_CB_TIMEOUT", "60")
        )
        self.success_threshold = success_threshold or int(
            os.environ.get("EROS_CB_SUCCESS_THRESHOLD", "2")
        )

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = threading.RLock()

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Any exception from func (after recording failure)
        """
        with self.lock:
            if self.state == CircuitState.OPEN:
                time_since_failure = time() - (self.last_failure_time or 0)
                if time_since_failure >= self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' entering HALF_OPEN state"
                    )
                else:
                    retry_after = self.timeout - time_since_failure
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {retry_after:.1f}s",
                        retry_after=retry_after
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self) -> None:
        """Record successful execution."""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' CLOSED - recovery successful"
                    )
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        """Record failed execution."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time()

            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' returned to OPEN - "
                    f"recovery failed: {error}"
                )
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker '{self.name}' OPEN - "
                    f"{self.failure_count} consecutive failures"
                )

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state for health checks."""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.failure_threshold,
                "timeout": self.timeout,
                "last_failure_time": self.last_failure_time,
            }

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' manually reset")


# Pre-configured circuit breakers for common operations
db_circuit_breaker = CircuitBreaker(name="database")
mcp_circuit_breaker = CircuitBreaker(name="mcp_tools", failure_threshold=3, timeout=30)


__all__ = [
    "CircuitState",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "db_circuit_breaker",
    "mcp_circuit_breaker",
]
