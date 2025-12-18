"""
EROS Metrics Collection Module.

Provides centralized metrics collection for performance tracking,
function call counting, execution time histograms, and error rate monitoring.

This module implements a thread-safe singleton pattern for collecting metrics
across the EROS schedule generation system. Metrics can be exported for
monitoring dashboards, logging, or performance analysis.

Key Features:
    - Thread-safe metric recording
    - Automatic timing with decorators
    - Histogram bucketing for latency distribution
    - Error rate tracking with context
    - Tag-based metric grouping
    - Export to various formats (dict, JSON)

Example:
    from python.observability.metrics import get_metrics, timed, counted

    # Using decorators
    @timed("my_function")
    @counted("my_function_calls")
    def my_function():
        pass

    # Manual recording
    metrics = get_metrics()
    metrics.record_timing("custom_op", 45.5, tags={"type": "ppv"})
    metrics.increment("requests", tags={"status": "success"})

    # Get summary
    summary = metrics.get_summary()
    print(f"Total calls: {summary['counters']['my_function_calls']}")
"""

from __future__ import annotations

import functools
import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar, ParamSpec

from python.logging_config import get_logger

logger = get_logger(__name__)

# Type variables for decorator typing
P = ParamSpec("P")
T = TypeVar("T")


class MetricType(Enum):
    """Types of metrics supported by the collector."""

    COUNTER = "counter"      # Monotonically increasing value
    TIMING = "timing"        # Duration measurements in milliseconds
    HISTOGRAM = "histogram"  # Value distribution with buckets
    GAUGE = "gauge"          # Point-in-time value


@dataclass
class TimingStats:
    """Statistics for timing measurements.

    Attributes:
        count: Number of measurements
        total_ms: Sum of all durations in milliseconds
        min_ms: Minimum duration observed
        max_ms: Maximum duration observed
        buckets: Distribution buckets for histogram view
    """

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    buckets: dict[str, int] = field(default_factory=dict)

    # Histogram bucket boundaries in milliseconds
    BUCKET_BOUNDARIES: tuple[float, ...] = (
        1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
    )

    @property
    def mean_ms(self) -> float:
        """Calculate mean duration in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    def record(self, duration_ms: float) -> None:
        """Record a timing measurement.

        Args:
            duration_ms: Duration in milliseconds
        """
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

        # Update histogram bucket
        bucket = self._get_bucket(duration_ms)
        self.buckets[bucket] = self.buckets.get(bucket, 0) + 1

    def _get_bucket(self, duration_ms: float) -> str:
        """Determine the histogram bucket for a duration.

        Args:
            duration_ms: Duration in milliseconds

        Returns:
            Bucket label string
        """
        for boundary in self.BUCKET_BOUNDARIES:
            if duration_ms <= boundary:
                return f"le_{boundary}ms"
        return f"gt_{self.BUCKET_BOUNDARIES[-1]}ms"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else None,
            "max_ms": round(self.max_ms, 2),
            "buckets": self.buckets,
        }


@dataclass
class ErrorStats:
    """Statistics for error tracking.

    Attributes:
        total_calls: Total number of function calls
        error_count: Number of calls that raised exceptions
        errors_by_type: Count of errors by exception type
        last_error: Most recent error message
        last_error_time: Timestamp of most recent error
    """

    total_calls: int = 0
    error_count: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None
    last_error_time: str | None = None

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        return (self.error_count / self.total_calls * 100) if self.total_calls > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return 100.0 - self.error_rate

    def record_call(self) -> None:
        """Record a function call."""
        self.total_calls += 1

    def record_error(self, error: Exception) -> None:
        """Record an error occurrence.

        Args:
            error: The exception that was raised
        """
        self.error_count += 1
        error_type = type(error).__name__
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.last_error = str(error)
        self.last_error_time = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "total_calls": self.total_calls,
            "error_count": self.error_count,
            "error_rate_percent": round(self.error_rate, 2),
            "success_rate_percent": round(self.success_rate, 2),
            "errors_by_type": self.errors_by_type,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time,
        }


class MetricsCollector:
    """Thread-safe singleton for collecting application metrics.

    This class implements the singleton pattern to ensure a single
    metrics collection point across the application. All operations
    are thread-safe using a lock.

    Example:
        metrics = MetricsCollector.get_instance()
        metrics.increment("api_calls")
        metrics.record_timing("db_query", 45.5)
    """

    _instance: MetricsCollector | None = None
    _lock = threading.Lock()

    def __new__(cls) -> MetricsCollector:
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize metrics storage.

        Called once when the singleton is created.
        """
        self._counters: dict[str, int] = defaultdict(int)
        self._timings: dict[str, TimingStats] = defaultdict(TimingStats)
        self._errors: dict[str, ErrorStats] = defaultdict(ErrorStats)
        self._gauges: dict[str, float] = {}
        self._tags: dict[str, dict[str, Any]] = defaultdict(dict)
        self._start_time = datetime.now(timezone.utc)
        self._data_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> MetricsCollector:
        """Get the singleton instance.

        Returns:
            The MetricsCollector singleton
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        Primarily for testing purposes. Clears all collected metrics.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._initialize()

    def increment(
        self,
        name: str,
        value: int = 1,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Counter name
            value: Amount to increment (default: 1)
            tags: Optional tags for metric grouping
        """
        with self._data_lock:
            key = self._make_key(name, tags)
            self._counters[key] += value
            if tags:
                self._tags[key] = tags

    def record_timing(
        self,
        name: str,
        duration_ms: float,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Record a timing measurement.

        Args:
            name: Timing metric name
            duration_ms: Duration in milliseconds
            tags: Optional tags for metric grouping
        """
        with self._data_lock:
            key = self._make_key(name, tags)
            self._timings[key].record(duration_ms)
            if tags:
                self._tags[key] = tags

    def record_error(
        self,
        name: str,
        error: Exception,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Record an error occurrence.

        Args:
            name: Error tracking metric name
            error: The exception that occurred
            tags: Optional tags for metric grouping
        """
        with self._data_lock:
            key = self._make_key(name, tags)
            self._errors[key].record_error(error)
            if tags:
                self._tags[key] = tags

    def record_call(
        self,
        name: str,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Record a function call (for error rate calculation).

        Args:
            name: Error tracking metric name
            tags: Optional tags for metric grouping
        """
        with self._data_lock:
            key = self._make_key(name, tags)
            self._errors[key].record_call()
            if tags:
                self._tags[key] = tags

    def set_gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Set a gauge metric value.

        Args:
            name: Gauge metric name
            value: Current value
            tags: Optional tags for metric grouping
        """
        with self._data_lock:
            key = self._make_key(name, tags)
            self._gauges[key] = value
            if tags:
                self._tags[key] = tags

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, Any] | None = None
    ) -> None:
        """Record a value in a histogram (alias for record_timing).

        Args:
            name: Histogram metric name
            value: Value to record
            tags: Optional tags for metric grouping
        """
        self.record_timing(name, value, tags)

    def _make_key(self, name: str, tags: dict[str, Any] | None) -> str:
        """Create a unique key from name and tags.

        Args:
            name: Metric name
            tags: Optional tags

        Returns:
            Unique string key
        """
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def get_counter(self, name: str, tags: dict[str, Any] | None = None) -> int:
        """Get current counter value.

        Args:
            name: Counter name
            tags: Optional tags

        Returns:
            Current counter value
        """
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)

    def get_timing(
        self,
        name: str,
        tags: dict[str, Any] | None = None
    ) -> TimingStats | None:
        """Get timing statistics.

        Args:
            name: Timing metric name
            tags: Optional tags

        Returns:
            TimingStats or None if not found
        """
        key = self._make_key(name, tags)
        return self._timings.get(key)

    def get_error_stats(
        self,
        name: str,
        tags: dict[str, Any] | None = None
    ) -> ErrorStats | None:
        """Get error statistics.

        Args:
            name: Error metric name
            tags: Optional tags

        Returns:
            ErrorStats or None if not found
        """
        key = self._make_key(name, tags)
        return self._errors.get(key)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all collected metrics.

        Returns:
            Dictionary containing all metrics organized by type
        """
        with self._data_lock:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

            return {
                "uptime_seconds": round(uptime, 2),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "counters": dict(self._counters),
                "timings": {
                    name: stats.to_dict()
                    for name, stats in self._timings.items()
                },
                "errors": {
                    name: stats.to_dict()
                    for name, stats in self._errors.items()
                },
                "gauges": dict(self._gauges),
            }

    def to_json(self, indent: int = 2) -> str:
        """Export metrics as JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation of all metrics
        """
        return json.dumps(self.get_summary(), indent=indent)

    def log_summary(self) -> None:
        """Log a summary of collected metrics."""
        summary = self.get_summary()
        logger.info(
            "Metrics summary",
            extra={
                "uptime_seconds": summary["uptime_seconds"],
                "counter_count": len(summary["counters"]),
                "timing_count": len(summary["timings"]),
                "error_count": len(summary["errors"]),
            }
        )


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        The MetricsCollector singleton
    """
    return MetricsCollector.get_instance()


def reset_metrics() -> None:
    """Reset all collected metrics.

    Primarily for testing purposes.
    """
    MetricsCollector.reset_instance()


def record_timing(
    name: str,
    duration_ms: float,
    tags: dict[str, Any] | None = None
) -> None:
    """Record a timing measurement to the global collector.

    Args:
        name: Timing metric name
        duration_ms: Duration in milliseconds
        tags: Optional tags for metric grouping
    """
    get_metrics().record_timing(name, duration_ms, tags)


def increment(
    name: str,
    value: int = 1,
    tags: dict[str, Any] | None = None
) -> None:
    """Increment a counter in the global collector.

    Args:
        name: Counter name
        value: Amount to increment (default: 1)
        tags: Optional tags for metric grouping
    """
    get_metrics().increment(name, value, tags)


def histogram(
    name: str,
    value: float,
    tags: dict[str, Any] | None = None
) -> None:
    """Record a value in a histogram in the global collector.

    Args:
        name: Histogram metric name
        value: Value to record
        tags: Optional tags for metric grouping
    """
    get_metrics().histogram(name, value, tags)


# =============================================================================
# Decorators
# =============================================================================


def timed(
    name: str | None = None,
    tags: dict[str, Any] | None = None,
    log_slow_threshold_ms: float | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to automatically time function execution.

    Records execution time in milliseconds to the global metrics collector.

    Args:
        name: Metric name (defaults to function name)
        tags: Optional tags for metric grouping
        log_slow_threshold_ms: If set, log warning when execution exceeds this

    Returns:
        Decorated function

    Example:
        @timed("caption_selection", log_slow_threshold_ms=100)
        def select_caption(...):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        metric_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                get_metrics().record_timing(metric_name, elapsed_ms, tags)

                if log_slow_threshold_ms and elapsed_ms > log_slow_threshold_ms:
                    logger.warning(
                        f"Slow execution: {metric_name}",
                        extra={
                            "function": metric_name,
                            "duration_ms": round(elapsed_ms, 2),
                            "threshold_ms": log_slow_threshold_ms,
                        }
                    )

        return wrapper
    return decorator


def counted(
    name: str | None = None,
    tags: dict[str, Any] | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to count function calls.

    Records call count to the global metrics collector.

    Args:
        name: Metric name (defaults to function name)
        tags: Optional tags for metric grouping

    Returns:
        Decorated function

    Example:
        @counted("api_calls", tags={"endpoint": "volume"})
        def get_volume(...):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        metric_name = name or f"{func.__module__}.{func.__name__}_calls"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            get_metrics().increment(metric_name, 1, tags)
            return func(*args, **kwargs)

        return wrapper
    return decorator


def with_error_tracking(
    name: str | None = None,
    tags: dict[str, Any] | None = None,
    reraise: bool = True
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to track error rates for a function.

    Records both total calls and errors to calculate error rates.

    Args:
        name: Metric name (defaults to function name)
        tags: Optional tags for metric grouping
        reraise: Whether to re-raise caught exceptions (default: True)

    Returns:
        Decorated function

    Example:
        @with_error_tracking("db_operations")
        def query_database(...):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        metric_name = name or f"{func.__module__}.{func.__name__}_errors"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            metrics = get_metrics()
            metrics.record_call(metric_name, tags)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                metrics.record_error(metric_name, e, tags)
                logger.error(
                    f"Error in {metric_name}: {e}",
                    extra={
                        "function": metric_name,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )
                if reraise:
                    raise
                # When not reraising, we cannot return a valid T, so we return None
                # The caller must handle None return when using reraise=False
                return None  # type: ignore[return-value]

        return wrapper
    return decorator


# =============================================================================
# Context Manager for Timing
# =============================================================================


class TimingContext:
    """Context manager for timing code blocks.

    Example:
        with TimingContext("db_query") as timer:
            result = execute_query()

        print(f"Query took {timer.elapsed_ms}ms")
    """

    def __init__(
        self,
        name: str,
        tags: dict[str, Any] | None = None,
        log_on_exit: bool = False
    ):
        """Initialize timing context.

        Args:
            name: Metric name
            tags: Optional tags for metric grouping
            log_on_exit: Whether to log timing when context exits
        """
        self.name = name
        self.tags = tags
        self.log_on_exit = log_on_exit
        self.start_time: float | None = None
        self.end_time: float | None = None

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000

    def __enter__(self) -> TimingContext:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record metric."""
        self.end_time = time.perf_counter()
        get_metrics().record_timing(self.name, self.elapsed_ms, self.tags)

        if self.log_on_exit:
            logger.debug(
                f"Timing: {self.name}",
                extra={
                    "operation": self.name,
                    "duration_ms": round(self.elapsed_ms, 2),
                }
            )


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Core classes
    "MetricsCollector",
    "MetricType",
    "TimingStats",
    "ErrorStats",
    "TimingContext",
    # Singleton access
    "get_metrics",
    "reset_metrics",
    # Convenience functions
    "record_timing",
    "increment",
    "histogram",
    # Decorators
    "timed",
    "counted",
    "with_error_tracking",
]
