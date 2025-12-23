"""
Retry Logic with Exponential Backoff.

Provides decorators and utilities for retrying transient failures
with configurable backoff strategies.
"""
import time
import random
import sqlite3
from functools import wraps
from typing import Callable, Tuple, TypeVar, Type, Optional, Union
import logging

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable)

# Default exceptions that are safe to retry
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    sqlite3.OperationalError,
    sqlite3.InterfaceError,
    TimeoutError,
    ConnectionError,
)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
) -> Callable[[F], F]:
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.5)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        jitter: Random jitter factor ±percentage (default: 0.1 = ±10%)
        retryable_exceptions: Tuple of exceptions to retry on

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(max_attempts=3, base_delay=1.0)
        def fetch_data():
            return db.query("SELECT * FROM table")
    """
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        logger.warning(
                            f"Retry exhausted for {func.__name__} after "
                            f"{max_attempts} attempts. Final error: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    jitter_amount = delay * jitter * (2 * random.random() - 1)
                    actual_delay = max(0, delay + jitter_amount)

                    logger.info(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                        f"after {actual_delay:.2f}s. Error: {e}"
                    )

                    time.sleep(actual_delay)

            # Should not reach here, but safety fallback
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper  # type: ignore
    return decorator


def retry_call(
    func: Callable[..., F],
    args: tuple = (),
    kwargs: Optional[dict] = None,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
) -> F:
    """
    Retry a function call with exponential backoff (non-decorator version).

    Args:
        func: Function to call
        args: Positional arguments for func
        kwargs: Keyword arguments for func
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for exponential backoff
        jitter: Random jitter factor
        retryable_exceptions: Tuple of exceptions to retry on

    Returns:
        Result from func

    Example:
        result = retry_call(db.query, args=("SELECT * FROM table",), max_attempts=3)
    """
    if kwargs is None:
        kwargs = {}
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS

    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_attempts - 1:
                logger.warning(
                    f"Retry exhausted for {func.__name__} after "
                    f"{max_attempts} attempts"
                )
                raise

            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            jitter_amount = delay * jitter * (2 * random.random() - 1)
            actual_delay = max(0, delay + jitter_amount)

            logger.info(
                f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                f"after {actual_delay:.2f}s"
            )

            time.sleep(actual_delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")


__all__ = [
    "with_retry",
    "retry_call",
    "RETRYABLE_EXCEPTIONS",
]
