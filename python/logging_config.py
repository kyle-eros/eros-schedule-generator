"""
EROS Logging Configuration.

Provides structured JSON logging for the EROS scheduling system.
Supports both development (human-readable) and production (JSON) modes.

Usage:
    from python.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing schedule", extra={"creator_id": "abc123"})

Environment Variables:
    EROS_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    EROS_LOG_FORMAT: 'json' for structured logging, 'text' for human-readable
    EROS_LOG_FILE: Optional file path for logging output
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Produces JSON log entries with consistent structure:
    {
        "timestamp": "2025-01-15T10:30:00.123456Z",
        "level": "INFO",
        "logger": "python.optimization.schedule_optimizer",
        "module": "schedule_optimizer",
        "function": "optimize_timing",
        "line": 42,
        "message": "Optimizing schedule",
        "extra": {"creator_id": "abc123", "items_count": 15}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log entry
        """
        # Build base log object
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'taskName', 'message'
        }

        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith('_')
        }

        if extra_fields:
            log_obj["extra"] = extra_fields

        return json.dumps(log_obj, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development.

    Produces colored, human-readable log entries:
    2025-01-15 10:30:00 [INFO] schedule_optimizer: Optimizing schedule (creator_id=abc123)
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",      # Reset
    }

    def __init__(self, use_colors: bool = True) -> None:
        """Initialize TextFormatter.

        Args:
            use_colors: Whether to use ANSI color codes
        """
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as human-readable text.

        Args:
            record: The log record to format

        Returns:
            Formatted string representation of the log entry
        """
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Get color codes
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
        else:
            color = ""
            reset = ""

        # Build base message
        base_msg = f"{timestamp} {color}[{record.levelname:8}]{reset} {record.module}: {record.getMessage()}"

        # Add extra fields if present
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'taskName', 'message'
        }

        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith('_')
        }

        if extra_fields:
            extras_str = ", ".join(f"{k}={v}" for k, v in extra_fields.items())
            base_msg += f" ({extras_str})"

        # Add exception info if present
        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return base_msg


class ContextAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that adds context to all log messages.

    Usage:
        logger = ContextAdapter(base_logger, {"creator_id": "abc123"})
        logger.info("Processing")  # Automatically includes creator_id
    """

    def process(
        self,
        msg: str,
        kwargs: Any  # type: ignore[override]  # Using Any for kwargs to match parent signature flexibility
    ) -> tuple[str, Any]:
        """Process log message to add context.

        Args:
            msg: The log message
            kwargs: Keyword arguments

        Returns:
            Tuple of (message, kwargs) with context added
        """
        # Merge context into extra
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


# Module-level configuration
_configured = False
_root_logger_name = "eros"


def configure_logging(
    level: str | None = None,
    format_type: str | None = None,
    log_file: str | None = None
) -> None:
    """Configure logging for the EROS system.

    This function should be called once at application startup.
    Subsequent calls will be ignored unless force=True.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Default: from EROS_LOG_LEVEL env var, or INFO
        format_type: 'json' or 'text'
                     Default: from EROS_LOG_FORMAT env var, or 'text'
        log_file: Optional file path for log output
                  Default: from EROS_LOG_FILE env var, or None (stderr only)
    """
    global _configured

    if _configured:
        return

    # Get configuration from environment if not provided
    level = level or os.environ.get("EROS_LOG_LEVEL", "INFO")
    format_type = format_type or os.environ.get("EROS_LOG_FORMAT", "text")
    log_file = log_file or os.environ.get("EROS_LOG_FILE")

    # Validate and convert level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create root EROS logger
    root_logger = logging.getLogger(_root_logger_name)
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Select formatter
    formatter: logging.Formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter(use_colors=True)

    # Add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(numeric_level)
    root_logger.addHandler(stderr_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        # Always use JSON for file output
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified module.

    The logger will be a child of the root EROS logger, ensuring
    consistent configuration across the application.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Starting optimization", extra={"items": 15})
    """
    # Ensure logging is configured
    if not _configured:
        configure_logging()

    # Create logger as child of root EROS logger
    if name.startswith("python."):
        # Use full path for python modules
        logger_name = f"{_root_logger_name}.{name}"
    else:
        logger_name = f"{_root_logger_name}.{name}"

    return logging.getLogger(logger_name)


def get_context_logger(
    name: str,
    **context: Any
) -> ContextAdapter:
    """Get a logger with persistent context.

    Creates a logger adapter that automatically includes the specified
    context in all log messages.

    Args:
        name: Module name (typically __name__)
        **context: Key-value pairs to include in all log messages

    Returns:
        Logger adapter with context

    Example:
        logger = get_context_logger(__name__, creator_id="abc123")
        logger.info("Processing schedule")  # Includes creator_id automatically
    """
    base_logger = get_logger(name)
    return ContextAdapter(base_logger, context)


# =============================================================================
# Convenience functions for common logging patterns
# =============================================================================


def log_operation_start(
    logger: logging.Logger,
    operation: str,
    **context: Any
) -> None:
    """Log the start of an operation.

    Args:
        logger: Logger instance
        operation: Name of the operation
        **context: Additional context to log
    """
    logger.info(
        f"Starting {operation}",
        extra={"operation": operation, "phase": "start", **context}
    )


def log_operation_end(
    logger: logging.Logger,
    operation: str,
    duration_ms: float | None = None,
    **context: Any
) -> None:
    """Log the end of an operation.

    Args:
        logger: Logger instance
        operation: Name of the operation
        duration_ms: Optional duration in milliseconds
        **context: Additional context to log
    """
    extra = {"operation": operation, "phase": "end", **context}
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms

    logger.info(f"Completed {operation}", extra=extra)


def log_fallback(
    logger: logging.Logger,
    operation: str,
    fallback_reason: str,
    fallback_action: str,
    **context: Any
) -> None:
    """Log a fallback scenario with warning level.

    Use this instead of silent failures to track when fallback logic
    is triggered.

    Args:
        logger: Logger instance
        operation: Name of the operation that triggered fallback
        fallback_reason: Why the fallback was needed
        fallback_action: What action was taken as fallback
        **context: Additional context to log
    """
    logger.warning(
        f"Fallback triggered for {operation}: {fallback_reason}",
        extra={
            "operation": operation,
            "fallback_reason": fallback_reason,
            "fallback_action": fallback_action,
            **context
        }
    )


# =============================================================================
# Export public API
# =============================================================================

__all__ = [
    "JSONFormatter",
    "TextFormatter",
    "ContextAdapter",
    "configure_logging",
    "get_logger",
    "get_context_logger",
    "log_operation_start",
    "log_operation_end",
    "log_fallback",
]
