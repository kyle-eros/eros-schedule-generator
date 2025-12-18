"""
Idempotency Guard for Timing Operations.

Provides thread-safe idempotency protection for schedule generation operations,
preventing duplicate executions within a configurable time window.

This module implements:
- IdempotencyRecord: Dataclass for storing operation results with TTL
- IdempotencyGuard: Thread-safe guard for preventing duplicate operations
- @idempotent decorator: Function decorator for automatic idempotency protection

Usage:
    @idempotent(operation_name="generate_timing")
    def calculate_optimal_timing(creator_id: str, date: str) -> dict:
        # Expensive operation that should not be repeated
        ...

    # Or use the guard directly:
    guard = IdempotencyGuard(ttl_minutes=60)
    is_duplicate, cached_result = guard.check_and_store(
        operation="timing_calc",
        params={"creator_id": "abc123"},
        result=calculated_result
    )
"""

from __future__ import annotations

import functools
import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, TypeVar, ParamSpec, cast

# Type variables for decorator typing
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation execution.

    Stores the result of an operation along with timing metadata
    for TTL-based expiration.

    Attributes:
        operation_key: SHA256-based unique key for the operation
        result: The cached result of the operation
        executed_at: Timestamp when the operation was executed
        expires_at: Timestamp when this record expires
    """

    operation_key: str
    result: Any
    executed_at: datetime
    expires_at: datetime


class IdempotencyGuard:
    """Thread-safe guard for preventing duplicate operation executions.

    Maintains an in-memory cache of operation results with automatic
    TTL-based expiration and thread-safe access.

    Attributes:
        ttl_minutes: Time-to-live for cached results in minutes
        _records: Dictionary mapping operation keys to IdempotencyRecords
        _lock: Reentrant lock for thread safety

    Examples:
        >>> guard = IdempotencyGuard(ttl_minutes=60)
        >>> is_dup, result = guard.check_and_store(
        ...     "generate_timing",
        ...     {"creator_id": "abc123"},
        ...     {"optimal_hour": 14}
        ... )
        >>> is_dup
        False
        >>> # Second call with same params returns cached result
        >>> is_dup, result = guard.check_and_store(
        ...     "generate_timing",
        ...     {"creator_id": "abc123"},
        ...     {"optimal_hour": 15}  # This result won't be stored
        ... )
        >>> is_dup
        True
        >>> result
        {'optimal_hour': 14}
    """

    def __init__(self, ttl_minutes: int = 60) -> None:
        """Initialize the IdempotencyGuard.

        Args:
            ttl_minutes: Time-to-live for cached results in minutes.
                Defaults to 60 minutes.
        """
        self.ttl_minutes = ttl_minutes
        self._records: dict[str, IdempotencyRecord] = {}
        self._lock = threading.RLock()

    def _generate_key(self, operation: str, params: dict[str, Any]) -> str:
        """Generate a unique key for an operation and its parameters.

        Creates a deterministic SHA256 hash from the operation name and
        normalized parameter dictionary.

        Args:
            operation: Name of the operation being performed
            params: Dictionary of parameters for the operation

        Returns:
            First 32 characters of the SHA256 hash as a hex string
        """
        normalized = json.dumps(params, sort_keys=True, default=str)
        content = f"{operation}:{normalized}"
        hash_bytes = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return hash_bytes[:32]

    def check_and_store(
        self,
        operation: str,
        params: dict[str, Any],
        result: Any
    ) -> tuple[bool, Optional[Any]]:
        """Check for existing result and store new result if not duplicate.

        Performs cleanup of expired records, then checks if an identical
        operation has been executed within the TTL window. If found,
        returns the cached result. Otherwise, stores the new result.

        Args:
            operation: Name of the operation being performed
            params: Dictionary of parameters for the operation
            result: The result to store if this is not a duplicate

        Returns:
            Tuple of (is_duplicate, cached_result):
                - (True, cached_result) if duplicate operation found
                - (False, None) if this is a new operation (result was stored)
        """
        with self._lock:
            now = datetime.now()

            # First, cleanup expired records
            self._cleanup_expired(now)

            # Generate key for this operation
            key = self._generate_key(operation, params)

            # Check for existing record
            existing = self._records.get(key)
            if existing is not None:
                return (True, existing.result)

            # Store new record
            expires_at = now + timedelta(minutes=self.ttl_minutes)
            record = IdempotencyRecord(
                operation_key=key,
                result=result,
                executed_at=now,
                expires_at=expires_at
            )
            self._records[key] = record

            return (False, None)

    def is_duplicate(self, operation: str, params: dict[str, Any]) -> bool:
        """Check if an operation would be a duplicate.

        Performs a read-only check without storing any result.

        Args:
            operation: Name of the operation being performed
            params: Dictionary of parameters for the operation

        Returns:
            True if a matching operation exists in cache, False otherwise
        """
        with self._lock:
            now = datetime.now()
            key = self._generate_key(operation, params)
            existing = self._records.get(key)

            if existing is None:
                return False

            # Check if expired
            if existing.expires_at <= now:
                return False

            return True

    def invalidate(self, operation: str, params: dict[str, Any]) -> bool:
        """Invalidate a cached operation result.

        Removes the cached result for the specified operation and parameters,
        allowing subsequent calls to execute fresh.

        Args:
            operation: Name of the operation to invalidate
            params: Dictionary of parameters for the operation

        Returns:
            True if a record was invalidated, False if no record existed
        """
        with self._lock:
            key = self._generate_key(operation, params)
            if key in self._records:
                del self._records[key]
                return True
            return False

    def _cleanup_expired(self, now: datetime) -> int:
        """Remove all expired records from the cache.

        Args:
            now: Current timestamp for expiration comparison

        Returns:
            Number of records that were removed
        """
        expired_keys = [
            key for key, record in self._records.items()
            if record.expires_at <= now
        ]
        for key in expired_keys:
            del self._records[key]
        return len(expired_keys)


# Global timing guard instance for decorator use
_timing_guard = IdempotencyGuard(ttl_minutes=60)


def idempotent(
    operation_name: Optional[str] = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for making functions idempotent.

    Wraps a function to prevent duplicate executions within the TTL window.
    Uses the global _timing_guard instance for caching.

    Args:
        operation_name: Optional name for the operation. If not provided,
            uses the decorated function's qualified name.

    Returns:
        Decorator function that wraps the target function

    Examples:
        >>> @idempotent(operation_name="calculate_timing")
        ... def expensive_calculation(creator_id: str, date: str) -> dict:
        ...     # This will only execute once per unique (creator_id, date)
        ...     # within the TTL window
        ...     return {"result": "calculated"}
        ...
        >>> # First call executes
        >>> result1 = expensive_calculation("abc123", "2025-01-01")
        >>> # Second call with same args returns cached result
        >>> result2 = expensive_calculation("abc123", "2025-01-01")
        >>> result1 is result2  # Same cached result
        True
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Determine operation name
            op_name = operation_name if operation_name else func.__qualname__

            # Build params dict from args and kwargs
            params: dict[str, Any] = {"args": args, "kwargs": kwargs}

            # Check if this is a duplicate operation
            if _timing_guard.is_duplicate(op_name, params):
                # Get the cached result
                key = _timing_guard._generate_key(op_name, params)
                with _timing_guard._lock:
                    record = _timing_guard._records.get(key)
                    if record is not None:
                        return cast(R, record.result)

            # Execute the function
            result = func(*args, **kwargs)

            # Store the result
            _timing_guard.check_and_store(op_name, params, result)

            return result

        return wrapper

    return decorator


def get_timing_guard() -> IdempotencyGuard:
    """Get the global timing guard instance.

    Provides access to the global guard for direct manipulation
    or inspection.

    Returns:
        The global IdempotencyGuard instance
    """
    return _timing_guard


def reset_timing_guard() -> None:
    """Reset the global timing guard.

    Clears all cached records from the global timing guard.
    Primarily useful for testing purposes.
    """
    global _timing_guard
    _timing_guard = IdempotencyGuard(ttl_minutes=60)


__all__ = [
    # Dataclass
    "IdempotencyRecord",
    # Main class
    "IdempotencyGuard",
    # Decorator
    "idempotent",
    # Global guard access
    "get_timing_guard",
    "reset_timing_guard",
    # Global instance
    "_timing_guard",
]
