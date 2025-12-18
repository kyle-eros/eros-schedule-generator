"""
EROS MCP Server Database Connection Management

Provides secure database connection handling with:
- Connection pooling with configurable size and overflow
- Connection health checks (ping on checkout)
- Connection max age (automatic recycling)
- Proper pool overflow handling
- Integration with Prometheus metrics

Configuration via environment variables:
- EROS_DB_PATH: Database file location
- EROS_DB_POOL_SIZE: Pool size (default: 10)
- EROS_DB_POOL_OVERFLOW: Max overflow connections (default: 5)
- EROS_DB_POOL_TIMEOUT: Checkout timeout in seconds (default: 30)
- EROS_DB_CONN_MAX_AGE: Max connection age in seconds (default: 300)
"""

import asyncio
import logging
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty, Full
from typing import Generator, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("eros_db_server.connection")

# Database path configuration - Dynamic path resolution for portability
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_DB_PATH = str(PROJECT_ROOT / "database" / "eros_sd_main.db")


def validate_db_path(path: str) -> str:
    """
    Validate database path for security and accessibility.

    Prevents path traversal attacks and ensures the database file exists
    and is readable.

    Args:
        path: Path to database file.

    Returns:
        Validated absolute path.

    Raises:
        FileNotFoundError: If database file does not exist.
        PermissionError: If database file is not readable.
        ValueError: If path contains traversal attempts or invalid characters.
    """
    # Check for empty path
    if not path:
        raise ValueError("Database path cannot be empty")

    # Resolve to absolute path
    abs_path = os.path.abspath(path)

    # Check path traversal attempts
    if ".." in path:
        raise ValueError(f"Path traversal not allowed: {path}")

    # Check file exists
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Database not found: {abs_path}")

    # Check file is readable
    if not os.access(abs_path, os.R_OK):
        raise PermissionError(f"Database not readable: {abs_path}")

    # Check it's a file (not a directory)
    if not os.path.isfile(abs_path):
        raise ValueError(f"Database path must be a file: {abs_path}")

    logger.debug(f"Database path validated: {abs_path}")
    return abs_path


# Validate and set database path
DB_PATH = validate_db_path(os.environ.get("EROS_DB_PATH", DEFAULT_DB_PATH))

# Pool configuration from environment
POOL_SIZE = int(os.environ.get("EROS_DB_POOL_SIZE", "10"))
POOL_OVERFLOW = int(os.environ.get("EROS_DB_POOL_OVERFLOW", "5"))
POOL_TIMEOUT = float(os.environ.get("EROS_DB_POOL_TIMEOUT", "30.0"))
CONN_MAX_AGE = int(os.environ.get("EROS_DB_CONN_MAX_AGE", "300"))

# Connection configuration
DB_CONNECTION_TIMEOUT = 30.0
DB_BUSY_TIMEOUT = 5000  # milliseconds


class PooledConnection:
    """
    Wrapper around a SQLite connection with pool metadata.

    Tracks creation time and last use for connection lifecycle management.
    Uses a unique ID for identity tracking in the connection pool.
    """

    _id_counter = 0
    _id_lock = threading.Lock()

    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize a pooled connection wrapper.

        Args:
            connection: The underlying SQLite connection.
        """
        with PooledConnection._id_lock:
            PooledConnection._id_counter += 1
            self._id = PooledConnection._id_counter

        self.connection = connection
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.use_count = 0

    def is_expired(self, max_age: int = CONN_MAX_AGE) -> bool:
        """Check if connection has exceeded max age."""
        return (time.time() - self.created_at) > max_age

    def touch(self) -> None:
        """Update last used timestamp and increment use count."""
        self.last_used_at = time.time()
        self.use_count += 1

    @property
    def id(self) -> int:
        """Return unique connection ID."""
        return self._id


class ConnectionPool:
    """
    Thread-safe SQLite connection pool with health checks and automatic recycling.

    Features:
    - Configurable pool size with overflow handling
    - Connection health checks on checkout
    - Automatic connection recycling after max age
    - Prometheus metrics integration
    - Thread-safe operations

    Example:
        pool = ConnectionPool(db_path="./database/eros_sd_main.db")

        with pool.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM creators")
            rows = cursor.fetchall()

        pool.close()
    """

    def __init__(
        self,
        db_path: str = DB_PATH,
        pool_size: int = POOL_SIZE,
        max_overflow: int = POOL_OVERFLOW,
        checkout_timeout: float = POOL_TIMEOUT,
        connection_max_age: int = CONN_MAX_AGE,
        enable_health_check: bool = True,
    ):
        """
        Initialize the connection pool.

        Args:
            db_path: Path to the SQLite database file.
            pool_size: Number of connections to maintain in the pool.
            max_overflow: Maximum number of overflow connections allowed.
            checkout_timeout: Timeout in seconds for acquiring a connection.
            connection_max_age: Maximum age in seconds before recycling.
            enable_health_check: Whether to verify connections before returning.
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.checkout_timeout = checkout_timeout
        self.connection_max_age = connection_max_age
        self.enable_health_check = enable_health_check

        # Thread-safe pool storage
        self._pool: Queue[PooledConnection] = Queue(maxsize=pool_size)
        self._lock = threading.RLock()
        self._overflow_count = 0
        self._total_connections = 0
        self._active_connections: dict[int, PooledConnection] = {}

        # Statistics
        self._connections_created = 0
        self._connections_recycled = 0
        self._connections_failed = 0
        self._health_check_failures = 0

        # Pre-populate pool
        self._initialize_pool()

        logger.info(
            f"Connection pool initialized: size={pool_size}, "
            f"max_overflow={max_overflow}, db_path={db_path}"
        )

    def _initialize_pool(self) -> None:
        """Pre-populate the pool with initial connections."""
        for _ in range(min(self.pool_size, 3)):  # Start with 3 connections
            try:
                conn = self._create_connection()
                self._pool.put_nowait(conn)
            except Exception as e:
                logger.warning(f"Failed to pre-populate pool: {e}")

    def _create_connection(self) -> PooledConnection:
        """
        Create a new pooled connection with security pragmas.

        Returns:
            PooledConnection wrapper with configured SQLite connection.

        Raises:
            sqlite3.Error: If connection creation fails.
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=DB_CONNECTION_TIMEOUT)
            conn.row_factory = sqlite3.Row

            # Security and integrity pragmas
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA secure_delete = ON")
            conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT}")

            # Performance optimizations
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")

            # Validate connection
            conn.execute("SELECT 1").fetchone()

            pooled = PooledConnection(connection=conn)

            with self._lock:
                self._connections_created += 1
                self._total_connections += 1

            # Update metrics if available
            try:
                from mcp.metrics import record_connection_created, update_pool_metrics
                record_connection_created()
                self._update_metrics()
            except ImportError:
                pass

            logger.debug("Database connection created")
            return pooled

        except sqlite3.Error as e:
            with self._lock:
                self._connections_failed += 1

            try:
                from mcp.metrics import record_connection_failed
                record_connection_failed()
            except ImportError:
                pass

            logger.error(f"Failed to create connection: {e}")
            raise

    def _health_check(self, pooled: PooledConnection) -> bool:
        """
        Verify a connection is still valid.

        Args:
            pooled: The pooled connection to check.

        Returns:
            True if connection is healthy, False otherwise.
        """
        if not self.enable_health_check:
            return True

        try:
            pooled.connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error as e:
            logger.warning(f"Connection health check failed: {e}")
            with self._lock:
                self._health_check_failures += 1
            return False

    def _should_recycle(self, pooled: PooledConnection) -> bool:
        """
        Check if a connection should be recycled.

        Args:
            pooled: The pooled connection to check.

        Returns:
            True if connection should be recycled, False otherwise.
        """
        if pooled.is_expired(self.connection_max_age):
            logger.debug(
                f"Connection expired after {time.time() - pooled.created_at:.1f}s"
            )
            return True
        return False

    def _recycle_connection(self, pooled: PooledConnection) -> None:
        """
        Close and clean up an expired connection.

        Args:
            pooled: The pooled connection to recycle.
        """
        try:
            pooled.connection.close()
        except sqlite3.Error:
            pass

        with self._lock:
            self._connections_recycled += 1
            self._total_connections -= 1

        try:
            from mcp.metrics import record_connection_recycled
            record_connection_recycled()
        except ImportError:
            pass

        logger.debug("Connection recycled")

    def _update_metrics(self) -> None:
        """Update Prometheus pool metrics."""
        try:
            from mcp.metrics import update_pool_metrics
            with self._lock:
                available = self._pool.qsize()
                in_use = self._total_connections - available
                update_pool_metrics(
                    pool_size=self.pool_size,
                    available=available,
                    in_use=in_use,
                    overflow=self._overflow_count
                )
        except ImportError:
            pass

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Acquire a connection from the pool with automatic return.

        This is the preferred method for getting connections. The connection
        is automatically returned to the pool when the context exits.

        Yields:
            sqlite3.Connection: A database connection with row factory configured.

        Raises:
            TimeoutError: If no connection is available within timeout.
            sqlite3.Error: If connection acquisition fails.

        Example:
            with pool.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM creators")
                rows = cursor.fetchall()
        """
        pooled = None
        is_overflow = False

        try:
            # Try to get from pool
            try:
                pooled = self._pool.get(timeout=self.checkout_timeout)

                # Check if connection needs recycling
                if self._should_recycle(pooled) or not self._health_check(pooled):
                    self._recycle_connection(pooled)
                    pooled = self._create_connection()

            except Empty:
                # Pool exhausted, try overflow
                with self._lock:
                    if self._overflow_count < self.max_overflow:
                        self._overflow_count += 1
                        is_overflow = True
                        logger.debug(
                            f"Creating overflow connection "
                            f"({self._overflow_count}/{self.max_overflow})"
                        )
                    else:
                        raise TimeoutError(
                            f"Connection pool exhausted. "
                            f"Pool size: {self.pool_size}, "
                            f"Overflow: {self._overflow_count}/{self.max_overflow}"
                        )

                pooled = self._create_connection()

            pooled.touch()
            with self._lock:
                self._active_connections[pooled.id] = pooled

            self._update_metrics()
            yield pooled.connection

        except sqlite3.Error as e:
            logger.error(f"Database error in pool: {e}")
            if pooled:
                try:
                    pooled.connection.rollback()
                except sqlite3.Error:
                    pass
            raise

        finally:
            if pooled:
                with self._lock:
                    self._active_connections.pop(pooled.id, None)

                if is_overflow:
                    # Close overflow connections instead of returning to pool
                    with self._lock:
                        self._overflow_count -= 1
                    try:
                        pooled.connection.close()
                        self._total_connections -= 1
                    except sqlite3.Error:
                        pass
                    logger.debug("Overflow connection closed")
                else:
                    # Return to pool
                    try:
                        self._pool.put_nowait(pooled)
                    except Full:
                        # Pool is full, close connection
                        try:
                            pooled.connection.close()
                            with self._lock:
                                self._total_connections -= 1
                        except sqlite3.Error:
                            pass

                self._update_metrics()

    def close(self) -> None:
        """
        Close all connections in the pool.

        Should be called during application shutdown.
        """
        logger.info("Closing connection pool...")

        # Close active connections
        with self._lock:
            for pooled in list(self._active_connections.values()):
                try:
                    pooled.connection.close()
                except sqlite3.Error:
                    pass
            self._active_connections.clear()

        # Drain and close pool
        while True:
            try:
                pooled = self._pool.get_nowait()
                try:
                    pooled.connection.close()
                except sqlite3.Error:
                    pass
            except Empty:
                break

        with self._lock:
            self._total_connections = 0
            self._overflow_count = 0

        logger.info("Connection pool closed")

    def get_stats(self) -> dict:
        """
        Get current pool statistics.

        Returns:
            Dictionary containing pool statistics.
        """
        with self._lock:
            return {
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "available": self._pool.qsize(),
                "total_connections": self._total_connections,
                "overflow_in_use": self._overflow_count,
                "active_connections": len(self._active_connections),
                "connections_created": self._connections_created,
                "connections_recycled": self._connections_recycled,
                "connections_failed": self._connections_failed,
                "health_check_failures": self._health_check_failures,
                "connection_max_age": self.connection_max_age,
            }


# Global pool instance (lazy initialization)
_global_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """
    Get or create the global connection pool.

    Returns:
        The global ConnectionPool instance.
    """
    global _global_pool
    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                _global_pool = ConnectionPool()
    return _global_pool


def close_pool() -> None:
    """Close the global connection pool."""
    global _global_pool
    with _pool_lock:
        if _global_pool is not None:
            _global_pool.close()
            _global_pool = None


# =============================================================================
# Legacy API (backward compatibility)
# =============================================================================

def get_db_path() -> str:
    """
    Get the configured database path.

    Returns:
        The database file path.
    """
    return DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """
    Create a database connection with row factory for dict-like access.

    Note:
        For new code, prefer using db_connection() context manager or
        the ConnectionPool directly for better resource management.

    Returns:
        sqlite3.Connection: Connection with row factory and security settings.

    Raises:
        sqlite3.Error: If database connection fails.
    """
    # Create connection with timeout
    conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
    conn.row_factory = sqlite3.Row

    # Security and integrity pragmas
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT}")

    # Validate connection
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as e:
        conn.close()
        raise sqlite3.Error(f"Database connection validation failed: {str(e)}")

    logger.debug("Database connection established with security settings")
    return conn


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections with automatic cleanup.

    For simple use cases, this uses direct connections. For high-concurrency
    scenarios, consider using get_pool().get_connection() instead.

    Yields:
        sqlite3.Connection: Connection with row factory and security settings.

    Raises:
        sqlite3.Error: If database connection fails.

    Example:
        with db_connection() as conn:
            cursor = conn.execute("SELECT * FROM creators WHERE creator_id = ?", (cid,))
            row = cursor.fetchone()
    """
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {str(e)}")


@contextmanager
def pooled_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for pooled database connections.

    Uses the global connection pool for efficient connection reuse.
    Recommended for high-concurrency scenarios.

    Yields:
        sqlite3.Connection: A pooled connection with row factory.

    Raises:
        TimeoutError: If no connection is available within timeout.
        sqlite3.Error: If database operation fails.

    Example:
        with pooled_connection() as conn:
            cursor = conn.execute("SELECT * FROM creators")
            rows = cursor.fetchall()
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        yield conn


# =============================================================================
# Pool Health and Monitoring
# =============================================================================


def get_pool_health() -> dict:
    """
    Get comprehensive pool health status for monitoring.

    Returns:
        Dictionary containing pool health metrics and status:
            - status: 'healthy', 'degraded', or 'unhealthy'
            - utilization: Percentage of pool capacity in use
            - stats: Full pool statistics
            - warnings: List of any warning conditions
    """
    pool = get_pool()
    stats = pool.get_stats()

    warnings = []
    status = "healthy"

    # Calculate utilization
    total_capacity = stats["pool_size"] + stats["max_overflow"]
    in_use = stats["active_connections"] + stats["overflow_in_use"]
    utilization = (in_use / total_capacity * 100) if total_capacity > 0 else 0

    # Check warning conditions
    if utilization > 80:
        warnings.append(f"High pool utilization: {utilization:.1f}%")
        status = "degraded"

    if stats["overflow_in_use"] > 0:
        warnings.append(f"Overflow connections in use: {stats['overflow_in_use']}")
        if stats["overflow_in_use"] >= stats["max_overflow"]:
            status = "degraded"

    if stats["health_check_failures"] > 5:
        warnings.append(f"Multiple health check failures: {stats['health_check_failures']}")
        status = "degraded"

    if stats["connections_failed"] > 0:
        warnings.append(f"Connection failures detected: {stats['connections_failed']}")

    # Check for complete exhaustion
    if in_use >= total_capacity:
        status = "unhealthy"
        warnings.append("Pool completely exhausted")

    return {
        "status": status,
        "utilization": round(utilization, 1),
        "stats": stats,
        "warnings": warnings,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


def warm_pool(count: int = 3) -> int:
    """
    Pre-warm the connection pool by creating and validating connections.

    This reduces latency for initial requests by ensuring connections
    are already created and validated in the pool.

    Args:
        count: Number of connections to warm (default 3).

    Returns:
        Number of connections successfully warmed.
    """
    pool = get_pool()
    warmed = 0

    for _ in range(count):
        try:
            with pool.get_connection() as conn:
                # Validate connection with a simple query
                conn.execute("SELECT 1").fetchone()
                warmed += 1
        except Exception as e:
            logger.warning(f"Failed to warm connection: {e}")

    logger.info(f"Pool warmed with {warmed}/{count} connections")
    return warmed


def reset_pool() -> None:
    """
    Reset the global connection pool by closing all connections and reinitializing.

    Use this for recovery from pool corruption or after configuration changes.
    Warning: This will interrupt any active connections.
    """
    global _global_pool
    with _pool_lock:
        if _global_pool is not None:
            logger.warning("Resetting connection pool - closing all connections")
            _global_pool.close()
            _global_pool = None
        # Reinitialize
        _global_pool = ConnectionPool()
        logger.info("Connection pool reset complete")


def get_pool_metrics_for_prometheus() -> dict:
    """
    Get pool metrics formatted for Prometheus export.

    Returns:
        Dictionary with metric names and values suitable for Prometheus.
    """
    stats = get_pool().get_stats()
    return {
        "mcp_db_pool_size": stats["pool_size"],
        "mcp_db_pool_available": stats["available"],
        "mcp_db_pool_in_use": stats["active_connections"],
        "mcp_db_pool_overflow": stats["overflow_in_use"],
        "mcp_db_pool_total_connections": stats["total_connections"],
        "mcp_db_connections_created_total": stats["connections_created"],
        "mcp_db_connections_recycled_total": stats["connections_recycled"],
        "mcp_db_connections_failed_total": stats["connections_failed"],
        "mcp_db_health_check_failures_total": stats["health_check_failures"],
    }
