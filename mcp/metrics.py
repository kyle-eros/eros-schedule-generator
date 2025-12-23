"""
EROS MCP Server Prometheus Metrics

Provides comprehensive metrics collection for monitoring MCP server performance,
database operations, and request handling. Metrics are exposed via HTTP endpoint
for Prometheus scraping.

Metrics Categories:
- Request metrics: Total requests, latency, active connections
- Error metrics: Error counts by type and tool
- Database metrics: Connection pool status, query latency

Usage:
    from mcp.metrics import (
        start_metrics_server,
        REQUEST_COUNT,
        REQUEST_LATENCY,
        track_request,
    )

    # Start metrics HTTP server (typically at startup)
    start_metrics_server(port=9090)

    # Use decorator for automatic instrumentation
    @track_request("get_creator_profile")
    def get_creator_profile(creator_id: str):
        ...

    # Or manual instrumentation
    with REQUEST_LATENCY.labels(tool='my_tool').time():
        result = execute_tool()
"""

import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional, TypeVar

# Prometheus client - graceful degradation if not installed
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        start_http_server,
        REGISTRY,
        CollectorRegistry,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create stub classes for graceful degradation
    class StubMetric:
        """Stub metric that does nothing when Prometheus is not available."""
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def dec(self, amount=1):
            pass
        def set(self, value):
            pass
        def observe(self, value):
            pass
        def time(self):
            return contextmanager(lambda: (yield))()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    Counter = Histogram = Gauge = Info = StubMetric
    start_http_server = lambda port: None
    REGISTRY = None
    CollectorRegistry = None


logger = logging.getLogger("eros_db_server.metrics")

# Configuration
METRICS_PORT = int(os.environ.get("EROS_METRICS_PORT", "9090"))
METRICS_ENABLED = os.environ.get("EROS_METRICS_ENABLED", "true").lower() == "true"

# Type variable for generic function decorator
F = TypeVar('F', bound=Callable[..., Any])


# =============================================================================
# Request Metrics
# =============================================================================

REQUEST_COUNT = Counter(
    'mcp_requests_total',
    'Total number of MCP tool requests',
    ['tool', 'status']
)

REQUEST_LATENCY = Histogram(
    'mcp_request_latency_seconds',
    'MCP tool request latency in seconds',
    ['tool'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

ACTIVE_REQUESTS = Gauge(
    'mcp_active_requests',
    'Number of currently active MCP requests',
    ['tool']
)

REQUEST_IN_PROGRESS = Gauge(
    'mcp_requests_in_progress',
    'Number of MCP requests currently being processed'
)


# =============================================================================
# Error Metrics
# =============================================================================

ERROR_COUNT = Counter(
    'mcp_errors_total',
    'Total number of MCP errors',
    ['tool', 'error_type']
)

VALIDATION_ERRORS = Counter(
    'mcp_validation_errors_total',
    'Total number of input validation errors',
    ['tool', 'field']
)


# =============================================================================
# Database Metrics
# =============================================================================

DB_POOL_SIZE = Gauge(
    'mcp_db_pool_size',
    'Total size of the database connection pool'
)

DB_POOL_AVAILABLE = Gauge(
    'mcp_db_pool_available',
    'Number of available connections in the pool'
)

DB_POOL_IN_USE = Gauge(
    'mcp_db_pool_in_use',
    'Number of connections currently in use'
)

DB_POOL_OVERFLOW = Gauge(
    'mcp_db_pool_overflow',
    'Number of overflow connections created'
)

DB_CONNECTIONS_CREATED = Counter(
    'mcp_db_connections_created_total',
    'Total number of database connections created'
)

DB_CONNECTIONS_RECYCLED = Counter(
    'mcp_db_connections_recycled_total',
    'Total number of database connections recycled'
)

DB_CONNECTIONS_FAILED = Counter(
    'mcp_db_connections_failed_total',
    'Total number of failed database connection attempts'
)

QUERY_LATENCY = Histogram(
    'mcp_query_latency_seconds',
    'Database query latency in seconds',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

QUERY_COUNT = Counter(
    'mcp_queries_total',
    'Total number of database queries executed',
    ['query_type', 'status']
)

SLOW_QUERIES = Counter(
    'mcp_slow_queries_total',
    'Total number of queries exceeding slow query threshold',
    ['tool']
)


# =============================================================================
# Rate Limiting Metrics
# =============================================================================

RATE_LIMIT_HITS = Counter(
    'mcp_rate_limit_hits_total',
    'Total number of rate limit rejections',
    ['tool', 'limit_type']
)

RATE_LIMIT_TOKENS = Gauge(
    'mcp_rate_limit_tokens_available',
    'Number of tokens currently available in rate limit bucket',
    ['tool']
)


# =============================================================================
# Server Info
# =============================================================================

if PROMETHEUS_AVAILABLE:
    SERVER_INFO = Info(
        'mcp_server',
        'Information about the MCP server'
    )
else:
    SERVER_INFO = StubMetric()


# =============================================================================
# Helper Functions and Decorators
# =============================================================================

def start_metrics_server(port: Optional[int] = None) -> bool:
    """
    Start the Prometheus metrics HTTP server.

    Args:
        port: Port to bind to. Defaults to METRICS_PORT env var or 9090.

    Returns:
        True if server started successfully, False otherwise.
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not installed. Metrics collection disabled.")
        return False

    if not METRICS_ENABLED:
        logger.info("Metrics collection disabled via EROS_METRICS_ENABLED=false")
        return False

    actual_port = port or METRICS_PORT
    try:
        start_http_server(actual_port, addr='127.0.0.1')
        logger.info(f"Prometheus metrics server started on port {actual_port}")

        # Set server info
        SERVER_INFO.info({
            'version': '3.0.0',
            'name': 'eros-db-server',
            'protocol_version': '2024-11-05'
        })

        return True
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        return False


def track_request(tool_name: str) -> Callable[[F], F]:
    """
    Decorator to track metrics for an MCP tool function.

    Automatically tracks:
    - Request count (started, success, error)
    - Request latency
    - Active request gauge
    - Error counts by type

    Args:
        tool_name: The name of the tool being tracked.

    Returns:
        Decorated function with metrics instrumentation.

    Example:
        @track_request("get_creator_profile")
        def get_creator_profile(creator_id: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            REQUEST_COUNT.labels(tool=tool_name, status='started').inc()
            REQUEST_IN_PROGRESS.inc()
            ACTIVE_REQUESTS.labels(tool=tool_name).inc()

            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                REQUEST_COUNT.labels(tool=tool_name, status='success').inc()
                return result
            except Exception as e:
                error_type = type(e).__name__
                ERROR_COUNT.labels(tool=tool_name, error_type=error_type).inc()
                REQUEST_COUNT.labels(tool=tool_name, status='error').inc()
                raise
            finally:
                duration = time.perf_counter() - start_time
                REQUEST_LATENCY.labels(tool=tool_name).observe(duration)
                REQUEST_IN_PROGRESS.dec()
                ACTIVE_REQUESTS.labels(tool=tool_name).dec()

                # Track slow requests (> 500ms)
                if duration > 0.5:
                    SLOW_QUERIES.labels(tool=tool_name).inc()
                    logger.warning(
                        f"Slow request detected: tool={tool_name}, "
                        f"duration={duration:.3f}s"
                    )

        return wrapper  # type: ignore
    return decorator


@contextmanager
def track_query(query_type: str) -> Generator[None, None, None]:
    """
    Context manager to track database query metrics.

    Args:
        query_type: Type of query (e.g., 'select', 'insert', 'update').

    Yields:
        None

    Example:
        with track_query('select'):
            cursor.execute("SELECT * FROM creators")
    """
    start_time = time.perf_counter()
    try:
        yield
        QUERY_COUNT.labels(query_type=query_type, status='success').inc()
    except Exception:
        QUERY_COUNT.labels(query_type=query_type, status='error').inc()
        raise
    finally:
        duration = time.perf_counter() - start_time
        QUERY_LATENCY.labels(query_type=query_type).observe(duration)


def record_validation_error(tool: str, field: str) -> None:
    """
    Record a validation error for a specific field.

    Args:
        tool: The tool name where validation failed.
        field: The field that failed validation.
    """
    VALIDATION_ERRORS.labels(tool=tool, field=field).inc()


def update_pool_metrics(
    pool_size: int,
    available: int,
    in_use: int,
    overflow: int = 0
) -> None:
    """
    Update database connection pool metrics.

    Args:
        pool_size: Total configured pool size.
        available: Number of available connections.
        in_use: Number of connections currently in use.
        overflow: Number of overflow connections created.
    """
    DB_POOL_SIZE.set(pool_size)
    DB_POOL_AVAILABLE.set(available)
    DB_POOL_IN_USE.set(in_use)
    DB_POOL_OVERFLOW.set(overflow)


def record_connection_created() -> None:
    """Record that a new database connection was created."""
    DB_CONNECTIONS_CREATED.inc()


def record_connection_recycled() -> None:
    """Record that a database connection was recycled."""
    DB_CONNECTIONS_RECYCLED.inc()


def record_connection_failed() -> None:
    """Record that a database connection attempt failed."""
    DB_CONNECTIONS_FAILED.inc()


# =============================================================================
# Metrics Summary Helper
# =============================================================================

def get_metrics_summary() -> dict[str, Any]:
    """
    Get a summary of current metrics values.

    Useful for debugging and health checks without requiring
    Prometheus endpoint access.

    Returns:
        Dictionary containing current metric values.
    """
    if not PROMETHEUS_AVAILABLE:
        return {"status": "prometheus_not_available"}

    # Note: This is a simplified summary. Full metrics are available via
    # the Prometheus HTTP endpoint.
    return {
        "status": "available",
        "metrics_enabled": METRICS_ENABLED,
        "metrics_port": METRICS_PORT,
        "prometheus_available": PROMETHEUS_AVAILABLE,
    }
