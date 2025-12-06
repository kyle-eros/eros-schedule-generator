"""Centralized logging configuration for EROS Schedule Generator.

This module provides a unified logging setup that can be imported by all
scripts in the package. It supports console output, optional file logging,
and configurable log levels.

Usage:
    from logging_config import configure_logging, logger

    # Use default configuration
    logger.info("Schedule generation started")

    # Or configure with custom settings
    custom_logger = configure_logging(
        level="DEBUG",
        log_file=Path("/tmp/eros.log")
    )
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def configure_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None,
    logger_name: str = "eros"
) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            Defaults to INFO.
        log_file: Optional file path for file logging. If provided,
            logs will be written to both console and file.
        format_string: Custom format string for log messages.
            Defaults to timestamp, level, logger name, and message.
        logger_name: Name for the logger instance. Defaults to "eros".

    Returns:
        Configured logger instance.

    Example:
        >>> logger = configure_logging(level="DEBUG")
        >>> logger.debug("This is a debug message")
        2025-01-01 10:00:00,000 [DEBUG] eros: This is a debug message
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Create handlers list
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr)
    ]

    if log_file:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    # Configure root logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    # Get and return named logger
    return logging.getLogger(logger_name)


def get_logger(name: str = "eros") -> logging.Logger:
    """Get a logger instance with the given name.

    This is a convenience function for getting child loggers
    that inherit from the main eros logger.

    Args:
        name: Logger name. Will be prefixed with "eros." if not
            already prefixed.

    Returns:
        Logger instance.

    Example:
        >>> logger = get_logger("schedule")
        >>> logger.info("Generating schedule")
        2025-01-01 10:00:00,000 [INFO] eros.schedule: Generating schedule
    """
    if not name.startswith("eros"):
        name = f"eros.{name}"
    return logging.getLogger(name)


# Create default logger for import
logger = configure_logging()

# Module-level convenience functions
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical


__all__ = [
    "configure_logging",
    "get_logger",
    "logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
]
