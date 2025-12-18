# MCP Server Connection Pooling Architecture

Version: 1.0.0
Last Updated: 2025-12-17

## Overview

This document details the database connection management architecture for the EROS MCP Server, including the connection pool implementation, configuration options, and optimization recommendations.

---

## Table of Contents

1. [Current Architecture](#current-architecture)
2. [Connection Pool Implementation](#connection-pool-implementation)
3. [Configuration Options](#configuration-options)
4. [Usage Patterns](#usage-patterns)
5. [Health Checks and Monitoring](#health-checks-and-monitoring)
6. [Optimization Recommendations](#optimization-recommendations)
7. [Troubleshooting](#troubleshooting)

---

## Current Architecture

### Module Structure

```
mcp/
  connection.py      # Connection pool and management
  eros_db_server.py  # Tool implementations (uses direct connections)
  metrics.py         # Prometheus metrics for pool monitoring
  tools/             # Modular tool implementations
```

### Connection Flow

```
Tool Request
    |
    v
get_db_connection() or db_connection()
    |
    v
sqlite3.connect() with security pragmas
    |
    v
Execute query
    |
    v
Close connection (not pooled)
```

### Current Limitations

1. **No Connection Reuse**: Each request creates a new connection
2. **Connection Overhead**: SQLite PRAGMAs executed on every connect
3. **No Pool Metrics**: Pool statistics not exposed to Prometheus
4. **Manual Cleanup**: Connections must be explicitly closed

---

## Connection Pool Implementation

### `ConnectionPool` Class (mcp/connection.py)

A thread-safe SQLite connection pool with comprehensive lifecycle management.

```python
class ConnectionPool:
    """
    Features:
    - Configurable pool size with overflow handling
    - Connection health checks on checkout
    - Automatic connection recycling after max age
    - Prometheus metrics integration
    - Thread-safe operations
    """
```

### Key Components

| Component | Description |
|-----------|-------------|
| `PooledConnection` | Wrapper tracking creation time, use count |
| `_pool: Queue` | Thread-safe FIFO queue of available connections |
| `_active_connections` | Dict tracking in-use connections |
| `_overflow_count` | Current overflow connections in use |

### Pool Lifecycle

1. **Initialization**: Pre-populate with 3 connections
2. **Checkout**: Get connection from pool or create overflow
3. **Health Check**: Validate connection before returning
4. **Recycling**: Close expired connections (max age exceeded)
5. **Return**: Add connection back to pool or close if overflow

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DB_PATH` | `./database/eros_sd_main.db` | Database file location |
| `EROS_DB_POOL_SIZE` | `10` | Number of connections in pool |
| `EROS_DB_POOL_OVERFLOW` | `5` | Maximum overflow connections |
| `EROS_DB_POOL_TIMEOUT` | `30.0` | Checkout timeout (seconds) |
| `EROS_DB_CONN_MAX_AGE` | `300` | Connection recycle age (seconds) |

### Recommended Values by Workload

| Workload | Pool Size | Overflow | Max Age | Notes |
|----------|-----------|----------|---------|-------|
| Light (< 10 req/s) | 5 | 2 | 600 | Longer-lived connections |
| Normal (10-50 req/s) | 10 | 5 | 300 | Default configuration |
| Heavy (> 50 req/s) | 20 | 10 | 180 | More connections, faster recycling |

### SQLite Connection Pragmas

Applied to every connection for security and performance:

```python
conn.execute("PRAGMA foreign_keys = ON")     # Referential integrity
conn.execute("PRAGMA secure_delete = ON")    # Overwrite deleted data
conn.execute("PRAGMA busy_timeout = 5000")   # Wait for locks (5s)
conn.execute("PRAGMA journal_mode = WAL")    # Write-ahead logging
conn.execute("PRAGMA synchronous = NORMAL")  # Balanced durability
```

---

## Usage Patterns

### Preferred: Context Manager with Pool

```python
from mcp.connection import pooled_connection

def get_creator_data(creator_id: str):
    with pooled_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM creators WHERE creator_id = ?",
            (creator_id,)
        )
        return cursor.fetchone()
# Connection automatically returned to pool
```

### Alternative: Direct Pool Access

```python
from mcp.connection import get_pool

pool = get_pool()
stats = pool.get_stats()
print(f"Pool utilization: {stats['active_connections']}/{stats['pool_size']}")

with pool.get_connection() as conn:
    # Use connection
    pass
```

### Legacy: Non-pooled Connection

```python
from mcp.connection import db_connection

# Creates new connection (not from pool)
with db_connection() as conn:
    cursor = conn.execute("SELECT 1")
# Connection closed, not returned to pool
```

### Comparison of Methods

| Method | Pool? | Auto-cleanup | Recommended |
|--------|-------|--------------|-------------|
| `pooled_connection()` | Yes | Yes | Yes - production |
| `pool.get_connection()` | Yes | Yes | Yes - when stats needed |
| `db_connection()` | No | Yes | Tests only |
| `get_db_connection()` | No | No | Avoid |

---

## Health Checks and Monitoring

### Connection Health Check

Executed on checkout when `enable_health_check=True`:

```python
def _health_check(self, pooled: PooledConnection) -> bool:
    """Verify connection is still valid."""
    try:
        pooled.connection.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
```

### Pool Statistics

Available via `pool.get_stats()`:

```python
{
    "pool_size": 10,
    "max_overflow": 5,
    "available": 7,
    "total_connections": 10,
    "overflow_in_use": 0,
    "active_connections": 3,
    "connections_created": 15,
    "connections_recycled": 5,
    "connections_failed": 0,
    "health_check_failures": 1,
    "connection_max_age": 300
}
```

### Prometheus Metrics

When Prometheus is enabled, these metrics are exposed:

| Metric | Type | Description |
|--------|------|-------------|
| `mcp_db_connections_created_total` | Counter | Total connections created |
| `mcp_db_connections_recycled_total` | Counter | Connections recycled due to age |
| `mcp_db_connections_failed_total` | Counter | Failed connection attempts |
| `mcp_db_pool_size` | Gauge | Current pool size |
| `mcp_db_pool_available` | Gauge | Available connections |
| `mcp_db_pool_in_use` | Gauge | Connections currently in use |
| `mcp_db_pool_overflow` | Gauge | Current overflow count |

### Health Check Endpoint

```bash
# Pool health status
curl http://localhost:9090/metrics | grep mcp_db_pool
```

---

## Optimization Recommendations

### 1. Enable Connection Pooling in Tools

**Current State**: Most tools use `get_db_connection()` directly.

**Recommended**: Migrate to `pooled_connection()` context manager.

**Migration Example**:

```python
# Before (creates new connection each call)
def get_creator_profile(creator_id: str):
    conn = get_db_connection()
    try:
        # ... queries ...
    finally:
        conn.close()

# After (uses pooled connection)
def get_creator_profile(creator_id: str):
    with pooled_connection() as conn:
        # ... queries ...
```

### 2. Tune Pool Size for Workload

```bash
# Monitor connection usage
sqlite3 database/eros_sd_main.db "PRAGMA compile_options;" | grep THREAD

# Adjust based on concurrent tool calls
export EROS_DB_POOL_SIZE=15
export EROS_DB_POOL_OVERFLOW=5
```

### 3. Enable WAL Mode

Already enabled in connection pragmas. Verify:

```sql
PRAGMA journal_mode;
-- Should return: wal
```

### 4. Implement Connection Warming

Pre-create connections at startup to reduce first-request latency:

```python
def warm_pool(pool: ConnectionPool, count: int = 3):
    """Pre-warm pool with active connections."""
    connections = []
    for _ in range(count):
        with pool.get_connection() as conn:
            conn.execute("SELECT 1")
            connections.append(True)
    return len(connections)
```

### 5. Monitor Pool Exhaustion

Alert when pool is frequently exhausted:

```python
stats = pool.get_stats()
utilization = stats['active_connections'] / stats['pool_size']
if utilization > 0.8:
    logger.warning(f"Pool utilization high: {utilization:.0%}")
```

---

## Troubleshooting

### Connection Timeout Errors

**Symptom**: `TimeoutError: Connection pool exhausted`

**Causes**:
1. Pool too small for workload
2. Connections not being returned (resource leak)
3. Long-running queries blocking pool

**Solutions**:
```bash
# Increase pool size
export EROS_DB_POOL_SIZE=20
export EROS_DB_POOL_OVERFLOW=10

# Check for connection leaks
# Look for get_db_connection() without close()
grep -r "get_db_connection\(\)" mcp/ | grep -v "finally.*close"
```

### Stale Connections

**Symptom**: `sqlite3.OperationalError: database is locked`

**Causes**:
1. Connection max age too high
2. Health checks disabled
3. WAL checkpoint needed

**Solutions**:
```bash
# Reduce max age
export EROS_DB_CONN_MAX_AGE=180

# Force checkpoint
sqlite3 database/eros_sd_main.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Performance Degradation

**Symptom**: Slow queries, high latency

**Diagnosis**:
```python
stats = pool.get_stats()
print(f"Created: {stats['connections_created']}")
print(f"Recycled: {stats['connections_recycled']}")
print(f"Failed: {stats['connections_failed']}")
```

**Solutions**:
1. Check if connections are being recycled too frequently
2. Increase max age if recycling is excessive
3. Add indexes for slow queries
4. Enable query logging

### Memory Issues

**Symptom**: Growing memory usage

**Causes**:
1. Too many pooled connections
2. Large result sets not being cleaned up
3. Overflow connections not being released

**Solutions**:
```bash
# Reduce pool size
export EROS_DB_POOL_SIZE=5
export EROS_DB_POOL_OVERFLOW=2

# Monitor with metrics
curl http://localhost:9090/metrics | grep mcp_db_pool
```

---

## Migration Checklist

To migrate from direct connections to pooled connections:

- [ ] Update imports: `from mcp.connection import pooled_connection`
- [ ] Replace `conn = get_db_connection()` with `with pooled_connection() as conn:`
- [ ] Remove explicit `conn.close()` calls (handled by context manager)
- [ ] Add pool warm-up to server startup
- [ ] Configure environment variables for workload
- [ ] Enable Prometheus metrics monitoring
- [ ] Add pool health check to readiness endpoint
- [ ] Update tests to use mock pool

---

## Related Documentation

- `mcp/connection.py` - Connection pool implementation
- `mcp/metrics.py` - Prometheus metrics integration
- `mcp/eros_db_server.py` - Legacy tool implementations
- `docs/MCP_API_REFERENCE.md` - MCP tool documentation
