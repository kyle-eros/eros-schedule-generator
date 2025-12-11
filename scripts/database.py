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
    "get_schema_info",
    "validate_schema",
    "get_table_columns",
    "get_column_safe",
    "SchemaValidationError",
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


class SchemaValidationError(Exception):
    """Raised when database schema doesn't match expected structure."""

    def __init__(self, missing_columns: dict[str, list[str]]) -> None:
        self.missing_columns = missing_columns
        issues = []
        for table, columns in missing_columns.items():
            issues.append(f"  {table}: missing {columns}")
        issues_str = "\n".join(issues)
        super().__init__(
            f"Database schema validation failed:\n{issues_str}\n\n"
            "Run database migrations or update expected schema."
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


def get_schema_info() -> dict[str, list[str]]:
    """
    Return key table schemas for reference.

    This provides a quick reference for the most important tables and their
    columns used by the EROS Schedule Generator. For full schema documentation,
    see references/database-schema.md.

    Returns:
        Dict mapping table name to list of column names.

    Example:
        >>> schema = get_schema_info()
        >>> print(schema["creators"])
        ['creator_id', 'page_name', 'display_name', ...]
    """
    return {
        "creators": [
            "creator_id",
            "page_name",
            "display_name",
            "page_type",
            "current_active_fans",
            "is_active",
            "notes",
            "current_total_earnings",
            "avg_purchase_rate",
        ],
        "creator_personas": [
            "persona_id",
            "creator_id",
            "primary_tone",
            "secondary_tone",
            "emoji_frequency",
            "slang_level",
            "avg_sentiment",
        ],
        "caption_bank": [
            "caption_id",
            "caption_text",
            "caption_type",
            "content_type_id",
            "schedulable_type",
            "performance_score",
            "freshness_score",
            "tone",
            "emoji_style",
            "is_active",
            "creator_id",
            "is_universal",
        ],
        "vault_matrix": [
            "vault_id",
            "creator_id",
            "content_type_id",
            "has_content",
            "quantity_available",
        ],
        "content_types": [
            "content_type_id",
            "type_name",
            "type_category",
            "priority_tier",
        ],
        "mass_messages": [
            "message_id",
            "creator_id",
            "caption_id",
            "sending_time",
            "sending_hour",
            "message_type",
            "earnings",
            "purchase_rate",
        ],
        "volume_assignments": [
            "assignment_id",
            "creator_id",
            "volume_level",
            "ppv_per_day",
            "bump_per_day",
            "is_active",
        ],
    }


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    """
    Get list of column names for a table from the database.

    Includes both regular columns and generated (computed) columns by using
    PRAGMA table_xinfo which shows all column types including VIRTUAL and STORED.

    Args:
        conn: Database connection with row_factory set.
        table_name: Name of the table to inspect.

    Returns:
        List of column names in the table.

    Raises:
        sqlite3.Error: If table doesn't exist or query fails.

    Example:
        >>> conn = get_database_connection()
        >>> columns = get_table_columns(conn, "creators")
        >>> "creator_id" in columns
        True
    """
    # Use table_xinfo to include generated columns (VIRTUAL and STORED)
    cursor = conn.execute(f"PRAGMA table_xinfo({table_name})")
    return [row[1] for row in cursor.fetchall()]


def validate_schema(
    conn: sqlite3.Connection | None = None,
    raise_on_error: bool = False,
) -> dict[str, list[str]]:
    """
    Validate that required columns exist in the database schema.

    Checks the actual database schema against the expected columns used by
    the EROS Schedule Generator. Returns a dict of tables with missing columns,
    or raises SchemaValidationError if raise_on_error is True.

    Args:
        conn: Database connection. If None, creates a new connection.
        raise_on_error: If True, raise SchemaValidationError on mismatches.
            If False (default), return dict of missing columns.

    Returns:
        Dict mapping table names to lists of missing column names.
        Empty dict if all columns are present.

    Raises:
        SchemaValidationError: If raise_on_error=True and columns are missing.
        DatabaseNotFoundError: If database not found.
        sqlite3.Error: If database access fails.

    Example:
        >>> missing = validate_schema()
        >>> if missing:
        ...     print(f"Schema issues: {missing}")
        >>> # Or raise on error:
        >>> validate_schema(raise_on_error=True)
    """
    import logging

    logger = logging.getLogger(__name__)

    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    try:
        expected_schema = get_schema_info()
        missing_columns: dict[str, list[str]] = {}

        for table_name, expected_cols in expected_schema.items():
            try:
                actual_cols = set(get_table_columns(conn, table_name))
                missing = [col for col in expected_cols if col not in actual_cols]
                if missing:
                    missing_columns[table_name] = missing
                    logger.warning(
                        f"Schema validation: table '{table_name}' missing columns: {missing}"
                    )
                else:
                    logger.debug(f"Schema validation: table '{table_name}' OK")
            except sqlite3.Error as e:
                # Table might not exist
                missing_columns[table_name] = [f"(table error: {e})"]
                logger.error(f"Schema validation: table '{table_name}' error: {e}")

        if missing_columns and raise_on_error:
            raise SchemaValidationError(missing_columns)

        if not missing_columns:
            logger.info("Schema validation passed - all expected columns present")

        return missing_columns

    finally:
        if close_conn:
            try:
                conn.close()
            except Exception:
                pass


def get_column_safe(
    row: sqlite3.Row,
    column_name: str,
    default: any = None,
) -> any:
    """
    Safely get a column value from a Row, returning default if missing.

    This utility function provides a fallback mechanism for queries that might
    encounter missing columns due to schema variations. Use this when accessing
    optional columns that may not exist in all database versions.

    Args:
        row: sqlite3.Row object from a query result.
        column_name: Name of the column to access.
        default: Value to return if column doesn't exist (default: None).

    Returns:
        Column value if present, otherwise the default value.

    Example:
        >>> # Safe access with default
        >>> secondary_tone = get_column_safe(row, "secondary_tone", "playful")
        >>> # Will return "playful" if column doesn't exist
    """
    try:
        return row[column_name]
    except (IndexError, KeyError):
        return default


# Module-level constant for backwards compatibility
# This is resolved at import time but won't raise if database not found
DB_PATH = _get_database_path_safe()
