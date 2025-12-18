"""
EROS Observability Module.

Provides metrics collection, timing instrumentation, and performance tracking
for the EROS schedule generation system.

Key Components:
    - MetricsCollector: Thread-safe metrics collection singleton
    - timed: Decorator for automatic function timing
    - counted: Decorator for function call counting
    - with_error_tracking: Decorator for error rate monitoring

Usage:
    from python.observability import metrics, timed, counted

    # Automatic timing instrumentation
    @timed("caption_selection")
    def select_caption(...):
        ...

    # Manual metrics recording
    metrics.record_timing("custom_operation", duration_ms=45.5)
    metrics.increment("api_calls", tags={"endpoint": "volume"})
"""

from python.observability.metrics import (
    MetricsCollector,
    MetricType,
    get_metrics,
    reset_metrics,
    record_timing,
    increment,
    histogram,
    timed,
    counted,
    with_error_tracking,
)

__all__ = [
    # Core classes
    "MetricsCollector",
    "MetricType",
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
