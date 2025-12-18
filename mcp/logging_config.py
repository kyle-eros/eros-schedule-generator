"""
EROS MCP Server Structured Logging

Provides structured JSON logging for all MCP requests and responses with:
- Unique request ID tracing
- Request/response timing information
- Slow query detection and alerting
- Configurable log levels
- JSON-formatted output for log aggregation

Configuration via environment variables:
- EROS_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
- EROS_LOG_FORMAT: Log format (json, text)
- EROS_SLOW_QUERY_MS: Slow query threshold in milliseconds (default: 500)

Log Levels:
- DEBUG: Full request/response bodies
- INFO: Request summaries with timing
- WARNING: Slow queries, retries
- ERROR: Failures with stack traces
"""

import json
import logging
import os
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

# Configuration
LOG_LEVEL = os.environ.get("EROS_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("EROS_LOG_FORMAT", "json").lower()
SLOW_QUERY_THRESHOLD_MS = int(os.environ.get("EROS_SLOW_QUERY_MS", "500"))

# Type variable for generic function decorator
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class RequestContext:
    """
    Context information for tracking a request through the system.

    Attributes:
        request_id: Unique identifier for this request.
        tool: The MCP tool being called.
        start_time: When the request started (Unix timestamp).
        params: Request parameters (sanitized for logging).
    """
    request_id: str
    tool: str
    start_time: float = field(default_factory=time.time)
    params: Dict[str, Any] = field(default_factory=dict)

    def elapsed_ms(self) -> float:
        """Calculate elapsed time in milliseconds."""
        return (time.time() - self.start_time) * 1000


class StructuredJsonFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Outputs log records as JSON objects for easy parsing by log aggregation
    systems like ELK, Splunk, or CloudWatch Logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields from record
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "tool"):
            log_entry["tool"] = record.tool
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "params"):
            log_entry["params"] = record.params
        if hasattr(record, "error_type"):
            log_entry["error_type"] = record.error_type

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_entry, default=str)


class MCPLogger:
    """
    Structured logger for MCP request/response tracking.

    Provides methods for logging requests, responses, errors, and slow queries
    with consistent structure and tracing information.

    Example:
        logger = MCPLogger("get_creator_profile")

        request_id = logger.log_request({"creator_id": "alexia"})

        try:
            result = do_work()
            logger.log_response(request_id, duration_ms=150.5, status="success")
        except Exception as e:
            logger.log_error(request_id, e)
            raise
    """

    def __init__(self, name: str = "eros_db_server"):
        """
        Initialize the MCP logger.

        Args:
            name: Logger name (typically the tool or module name).
        """
        self.logger = logging.getLogger(name)
        self._active_requests: Dict[str, RequestContext] = {}

    def generate_request_id(self) -> str:
        """
        Generate a unique request ID.

        Returns:
            A UUID-based request identifier.
        """
        return str(uuid.uuid4())[:8]

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize parameters for safe logging.

        Removes or masks sensitive information like credentials, tokens, etc.

        Args:
            params: Raw parameters dictionary.

        Returns:
            Sanitized parameters safe for logging.
        """
        sensitive_keys = {"password", "token", "secret", "key", "credential", "auth"}
        sanitized = {}

        for key, value in params.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = f"{value[:100]}... [truncated, {len(value)} chars]"
            else:
                sanitized[key] = value

        return sanitized

    def log_request(
        self,
        tool: str,
        params: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> str:
        """
        Log the start of an MCP tool request.

        Args:
            tool: The name of the tool being called.
            params: The request parameters.
            request_id: Optional custom request ID. Auto-generated if not provided.

        Returns:
            The request ID for correlation with response logging.
        """
        if request_id is None:
            request_id = self.generate_request_id()

        sanitized_params = self._sanitize_params(params)

        context = RequestContext(
            request_id=request_id,
            tool=tool,
            params=sanitized_params
        )
        self._active_requests[request_id] = context

        extra = {
            "event": "request",
            "request_id": request_id,
            "tool": tool,
            "params": sanitized_params
        }

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                f"MCP request started: tool={tool}",
                extra=extra
            )
        else:
            self.logger.info(
                f"Request: {tool}",
                extra=extra
            )

        return request_id

    def log_response(
        self,
        request_id: str,
        duration_ms: Optional[float] = None,
        status: str = "success",
        result_size: Optional[int] = None
    ) -> None:
        """
        Log the completion of an MCP tool request.

        Args:
            request_id: The request ID from log_request().
            duration_ms: Request duration in milliseconds. Auto-calculated if not provided.
            status: Response status (success, error, etc.).
            result_size: Optional size of the result in bytes.
        """
        context = self._active_requests.pop(request_id, None)

        if context and duration_ms is None:
            duration_ms = context.elapsed_ms()

        tool = context.tool if context else "unknown"

        extra = {
            "event": "response",
            "request_id": request_id,
            "tool": tool,
            "duration_ms": round(duration_ms, 3) if duration_ms else None,
            "status": status
        }

        if result_size is not None:
            extra["result_size"] = result_size

        # Check for slow query
        if duration_ms and duration_ms > SLOW_QUERY_THRESHOLD_MS:
            self.logger.warning(
                f"Slow response: {tool} took {duration_ms:.1f}ms "
                f"(threshold: {SLOW_QUERY_THRESHOLD_MS}ms)",
                extra=extra
            )
        else:
            self.logger.info(
                f"Response: {tool} completed in {duration_ms:.1f}ms" if duration_ms else f"Response: {tool}",
                extra=extra
            )

    def log_error(
        self,
        request_id: str,
        error: Exception,
        include_traceback: bool = True
    ) -> None:
        """
        Log an error during request processing.

        Args:
            request_id: The request ID from log_request().
            error: The exception that occurred.
            include_traceback: Whether to include the full traceback.
        """
        context = self._active_requests.pop(request_id, None)
        tool = context.tool if context else "unknown"
        duration_ms = context.elapsed_ms() if context else None

        extra = {
            "event": "error",
            "request_id": request_id,
            "tool": tool,
            "duration_ms": round(duration_ms, 3) if duration_ms else None,
            "status": "error",
            "error_type": type(error).__name__
        }

        if include_traceback:
            self.logger.error(
                f"Error in {tool}: {error}",
                extra=extra,
                exc_info=True
            )
        else:
            self.logger.error(
                f"Error in {tool}: {error}",
                extra=extra
            )

    def log_slow_query(
        self,
        tool: str,
        query_type: str,
        duration_ms: float,
        request_id: Optional[str] = None
    ) -> None:
        """
        Log a slow database query.

        Args:
            tool: The tool where the slow query occurred.
            query_type: Type of query (SELECT, INSERT, etc.).
            duration_ms: Query duration in milliseconds.
            request_id: Optional request ID for correlation.
        """
        extra = {
            "event": "slow_query",
            "tool": tool,
            "query_type": query_type,
            "duration_ms": round(duration_ms, 3)
        }
        if request_id:
            extra["request_id"] = request_id

        self.logger.warning(
            f"Slow query in {tool}: {query_type} took {duration_ms:.1f}ms",
            extra=extra
        )

    def log_validation_error(
        self,
        tool: str,
        field: str,
        message: str,
        request_id: Optional[str] = None
    ) -> None:
        """
        Log a validation error.

        Args:
            tool: The tool where validation failed.
            field: The field that failed validation.
            message: Validation error message.
            request_id: Optional request ID for correlation.
        """
        extra = {
            "event": "validation_error",
            "tool": tool,
            "field": field
        }
        if request_id:
            extra["request_id"] = request_id

        self.logger.warning(
            f"Validation error in {tool}: {field} - {message}",
            extra=extra
        )


# Global logger instance
_mcp_logger: Optional[MCPLogger] = None


def get_mcp_logger() -> MCPLogger:
    """
    Get the global MCP logger instance.

    Returns:
        The global MCPLogger instance.
    """
    global _mcp_logger
    if _mcp_logger is None:
        _mcp_logger = MCPLogger()
    return _mcp_logger


def setup_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None
) -> None:
    """
    Configure logging for the MCP server.

    Sets up the root logger and eros_db_server logger with the appropriate
    formatter and level.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to EROS_LOG_LEVEL env var.
        format_type: Log format (json, text). Defaults to EROS_LOG_FORMAT env var.
    """
    level = level or LOG_LEVEL
    format_type = format_type or LOG_FORMAT

    # Convert level string to logging constant
    numeric_level = getattr(logging, level, logging.INFO)

    # Get the root logger for eros_db_server
    logger = logging.getLogger("eros_db_server")
    logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)

    # Set formatter based on format type
    if format_type == "json":
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    logger.addHandler(handler)

    # Don't propagate to root logger
    logger.propagate = False

    logger.info(
        f"Logging configured: level={level}, format={format_type}",
        extra={"event": "logging_configured"}
    )


@contextmanager
def request_context(tool: str, params: Dict[str, Any]) -> Generator[str, None, None]:
    """
    Context manager for tracking a request with automatic logging.

    Logs request start and completion automatically, including timing
    and error handling.

    Args:
        tool: The MCP tool being called.
        params: Request parameters.

    Yields:
        The request ID for correlation.

    Example:
        with request_context("get_creator_profile", {"creator_id": "alexia"}) as request_id:
            result = do_work()
    """
    mcp_logger = get_mcp_logger()
    request_id = mcp_logger.log_request(tool, params)
    start_time = time.time()

    try:
        yield request_id
        duration_ms = (time.time() - start_time) * 1000
        mcp_logger.log_response(request_id, duration_ms=duration_ms, status="success")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        mcp_logger.log_error(request_id, e)
        raise


def log_tool_call(tool_name: str) -> Callable[[F], F]:
    """
    Decorator to automatically log tool calls.

    Wraps a tool function with request/response logging and timing.

    Args:
        tool_name: The name of the tool for logging.

    Returns:
        Decorated function with logging instrumentation.

    Example:
        @log_tool_call("get_creator_profile")
        def get_creator_profile(creator_id: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            mcp_logger = get_mcp_logger()
            request_id = mcp_logger.log_request(tool_name, kwargs)
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                mcp_logger.log_response(
                    request_id,
                    duration_ms=duration_ms,
                    status="success"
                )
                return result
            except Exception as e:
                mcp_logger.log_error(request_id, e)
                raise

        return wrapper  # type: ignore
    return decorator


# Thread-local storage for current request context
import threading
_request_context = threading.local()


def set_current_request_id(request_id: str) -> None:
    """Set the current request ID for the current thread."""
    _request_context.request_id = request_id


def get_current_request_id() -> Optional[str]:
    """Get the current request ID for the current thread."""
    return getattr(_request_context, 'request_id', None)


def clear_current_request_id() -> None:
    """Clear the current request ID for the current thread."""
    if hasattr(_request_context, 'request_id'):
        del _request_context.request_id
