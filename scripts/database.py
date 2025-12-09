#!/usr/bin/env python3
"""
Database Configuration - Single source of truth for EROS database access.

This module provides centralized database path resolution and connection
management. All other modules should import from here instead of
duplicating the path resolution logic.

Usage:
    from database import DB_PATH, get_database_path, get_database_connection

    # Get path only
    path = get_database_path()

    # Get connection (cached per thread)
    conn = get_database_connection()

    # Context manager for auto-cleanup
    with get_connection() as conn:
        cursor = conn.execute("SELECT ...")

Environment Variable:
    EROS_DATABASE_PATH - Override default database location

Standard Locations (checked in order):
    1. $EROS_DATABASE_PATH (if set)
    2. ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db
    3. ~/Documents/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db
    4. ~/.eros/eros.db (fallback)
"""

import os
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

__all__ = [
    "DB_PATH",
    "HOME_DIR",
    "get_database_path",
    "get_database_connection",
    "get_connection",
    "DatabaseNotFoundError",
]

# Base paths
HOME_DIR = Path.home()

# Standard database locations (checked in order)
_DEFAULT_LOCATIONS = [
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]


class DatabaseNotFoundError(FileNotFoundError):
    """Raised when no valid EROS database can be found."""

    def __init__(self, searched_paths: list[Path]) -> None:
        self.searched_paths = searched_paths
        paths_str = "\n  - ".join(str(p) for p in searched_paths)
        super().__init__(
            f"EROS database not found. Searched:\n  - {paths_str}\n\n"
            "Set EROS_DATABASE_PATH environment variable or place database in a standard location."
        )


def get_database_path() -> Path:
    """
    Resolve database path from environment or standard locations.

    Returns:
        Path to the EROS database file.

    Raises:
        DatabaseNotFoundError: If no valid database found.
    """
    # Check environment variable first
    env_path = os.environ.get("EROS_DATABASE_PATH", "")
    if env_path:
        env_path_obj = Path(env_path)
        if env_path_obj.exists():
            return env_path_obj
        # If env var set but file doesn't exist, still include in error
        candidates = [env_path_obj] + _DEFAULT_LOCATIONS
    else:
        candidates = _DEFAULT_LOCATIONS

    # Check each candidate
    for path in candidates:
        if path.exists():
            return path

    # No database found - raise with all searched paths
    raise DatabaseNotFoundError(candidates)


def _get_database_path_safe() -> Path:
    """
    Get database path, falling back to first default if not found.

    This is used for the module-level DB_PATH constant to avoid
    raising exceptions at import time.
    """
    try:
        return get_database_path()
    except DatabaseNotFoundError:
        # Fall back to first default location for backwards compatibility
        env_path = os.environ.get("EROS_DATABASE_PATH", "")
        if env_path:
            return Path(env_path)
        return _DEFAULT_LOCATIONS[0]


# Thread-local connection pool
_connection_pool: dict[int, sqlite3.Connection] = {}
_pool_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_database_connection() -> sqlite3.Connection:
    """
    Get a cached database connection with Row factory.

    This connection is cached and reused across calls. For thread-safe
    usage, use get_connection() context manager instead.

    Returns:
        sqlite3.Connection with Row factory enabled.

    Raises:
        DatabaseNotFoundError: If database not found.
        sqlite3.Error: If connection fails.
    """
    conn = sqlite3.connect(str(get_database_path()))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a thread-local database connection via context manager.

    This provides thread-safe database access with connection pooling.
    Connections are reused within the same thread.

    Usage:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM creators")
            rows = cursor.fetchall()

    Yields:
        sqlite3.Connection with Row factory enabled.

    Raises:
        DatabaseNotFoundError: If database not found.
        sqlite3.Error: If connection fails.
    """
    thread_id = threading.get_ident()

    with _pool_lock:
        if thread_id not in _connection_pool:
            conn = sqlite3.connect(str(get_database_path()))
            conn.row_factory = sqlite3.Row
            _connection_pool[thread_id] = conn

    try:
        yield _connection_pool[thread_id]
    except Exception:
        # On error, remove connection from pool to get fresh one next time
        with _pool_lock:
            if thread_id in _connection_pool:
                try:
                    _connection_pool[thread_id].close()
                except Exception:
                    pass
                del _connection_pool[thread_id]
        raise


def close_all_connections() -> None:
    """
    Close all pooled connections.

    Call this during cleanup or before exiting to ensure all
    database connections are properly closed.
    """
    with _pool_lock:
        for conn in _connection_pool.values():
            try:
                conn.close()
            except Exception:
                pass
        _connection_pool.clear()

    # Also clear the cached connection
    get_database_connection.cache_clear()


# Module-level constant for backwards compatibility
# This is resolved at import time but won't raise if database not found
DB_PATH = _get_database_path_safe()
