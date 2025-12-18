#!/usr/bin/env python3
"""
EROS MCP Database Server - Load and Stress Testing Suite

This module provides comprehensive load and stress tests for the MCP server to validate:
1. Concurrent request handling (10, 50, 100 concurrent requests)
2. Database connection pooling under load
3. Performance benchmarks (p95 latency requirements)
4. Memory usage and leak detection under sustained load
5. Connection limits and pool exhaustion behavior

Performance Requirements (p95 latency):
- get_creator_profile: < 100ms
- get_top_captions: < 200ms for 100 captions
- save_schedule: < 500ms for 50 items

Run with: pytest mcp/test_load_stress.py -v --tb=short
"""

import asyncio
import gc
import os
import sqlite3
import statistics
import sys
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tool functions - organized by domain
from mcp.tools.creator import (
    get_active_creators,
    get_creator_profile,
    get_persona_profile,
    get_vault_availability,
)
from mcp.tools.caption import get_top_captions, get_send_type_captions
from mcp.tools.performance import (
    get_best_timing,
    get_volume_assignment,
    get_performance_trends,
    get_content_type_rankings,
)
from mcp.tools.send_types import get_send_types, get_send_type_details, get_volume_config
from mcp.tools.targeting import get_channels, get_audience_targets
from mcp.tools.schedule import save_schedule
from mcp.tools.query import execute_query

# Server handler functions
from mcp.server import handle_request

# Connection and database helpers
from mcp.connection import db_connection, get_db_connection


# =============================================================================
# CONFIGURATION AND CONSTANTS
# =============================================================================

# Performance requirements (milliseconds)
PERFORMANCE_REQUIREMENTS = {
    "get_creator_profile": 100,  # p95 < 100ms
    "get_top_captions": 200,     # p95 < 200ms for 100 captions
    "save_schedule": 500,        # p95 < 500ms for 50 items
    "get_active_creators": 150,  # p95 < 150ms
    "get_send_types": 50,        # p95 < 50ms
    "execute_query": 100,        # p95 < 100ms for simple queries
}

# Concurrency levels for stress testing
CONCURRENCY_LEVELS = [10, 50, 100]

# Memory leak detection threshold (bytes)
MEMORY_LEAK_THRESHOLD = 10 * 1024 * 1024  # 10MB

# Maximum acceptable connection pool exhaustion wait time (seconds)
MAX_POOL_WAIT_TIME = 30.0


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def valid_creator_id() -> Optional[str]:
    """Get a valid creator_id from the database for testing."""
    result = get_active_creators()
    if result.get("creators") and len(result["creators"]) > 0:
        return result["creators"][0]["creator_id"]
    return None


@pytest.fixture(scope="module")
def test_schedule_items() -> list[dict[str, Any]]:
    """Generate test schedule items for save_schedule testing."""
    items = []
    base_date = "2020-01-06"  # Use a past date to avoid conflicts
    send_types = [
        "ppv_unlock", "ppv_wall", "tip_goal", "bump_normal",
        "bump_descriptive", "link_drop", "dm_farm", "renew_on_post",
        "ppv_followup", "like_farm"
    ]

    for i in range(50):
        hour = 9 + (i % 12)  # 9 AM to 8 PM
        minute = (i * 7) % 60  # Varied minutes
        items.append({
            "scheduled_date": base_date,
            "scheduled_time": f"{hour:02d}:{minute:02d}",
            "send_type_key": send_types[i % len(send_types)],
            "channel_key": "mass_message",
            "target_key": "all_fans",
            "caption_text": f"Test caption {i} for load testing",
            "suggested_price": 10.00 if "ppv" in send_types[i % len(send_types)] else None,
            "priority": (i % 5) + 1
        })
    return items


@pytest.fixture(scope="module")
def large_schedule_items() -> list[dict[str, Any]]:
    """Generate 1000+ schedule items for extreme load testing."""
    items = []
    send_types = [
        "ppv_unlock", "ppv_wall", "tip_goal", "bump_normal",
        "bump_descriptive", "link_drop", "dm_farm", "renew_on_post",
        "ppv_followup", "like_farm"
    ]

    for day in range(7):
        base_date = f"2020-01-{6 + day:02d}"
        for i in range(150):  # 150 items per day = 1050 total
            hour = 6 + (i % 18)  # 6 AM to 11 PM
            minute = (i * 3) % 60
            items.append({
                "scheduled_date": base_date,
                "scheduled_time": f"{hour:02d}:{minute:02d}",
                "send_type_key": send_types[i % len(send_types)],
                "channel_key": "mass_message",
                "target_key": "all_fans",
                "caption_text": f"Large schedule test {day}-{i}",
                "priority": (i % 5) + 1
            })
    return items


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def calculate_percentile(data: list[float], percentile: float) -> float:
    """
    Calculate the percentile value from a list of measurements.

    Args:
        data: List of measurements.
        percentile: Percentile to calculate (0-100).

    Returns:
        The percentile value.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = (percentile / 100) * (len(sorted_data) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_data):
        return sorted_data[-1]
    weight = index - lower
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


def measure_execution_time(func: Callable, *args, **kwargs) -> tuple[Any, float]:
    """
    Measure the execution time of a function.

    Args:
        func: Function to execute.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        Tuple of (result, execution_time_ms).
    """
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    execution_time_ms = (end_time - start_time) * 1000
    return result, execution_time_ms


def run_concurrent_calls(
    func: Callable,
    args_list: list[tuple],
    max_workers: int
) -> list[tuple[Any, float, Optional[Exception]]]:
    """
    Execute multiple function calls concurrently using ThreadPoolExecutor.

    Args:
        func: Function to call.
        args_list: List of argument tuples for each call.
        max_workers: Maximum concurrent workers.

    Returns:
        List of tuples (result, execution_time_ms, exception).
    """
    results = []

    def timed_call(args):
        try:
            result, exec_time = measure_execution_time(func, *args)
            return (result, exec_time, None)
        except Exception as e:
            return (None, 0.0, e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(timed_call, args) for args in args_list]
        for future in as_completed(futures):
            results.append(future.result())

    return results


async def async_run_concurrent(
    func: Callable,
    args_list: list[tuple],
    concurrency: int
) -> list[tuple[Any, float, Optional[Exception]]]:
    """
    Execute multiple function calls with async concurrency control.

    Uses asyncio to manage concurrency but calls sync functions via
    run_in_executor.

    Args:
        func: Synchronous function to call.
        args_list: List of argument tuples.
        concurrency: Maximum concurrent calls.

    Returns:
        List of (result, exec_time_ms, exception) tuples.
    """
    semaphore = asyncio.Semaphore(concurrency)
    loop = asyncio.get_event_loop()

    async def limited_call(args):
        async with semaphore:
            try:
                result, exec_time = await loop.run_in_executor(
                    None,
                    lambda: measure_execution_time(func, *args)
                )
                return (result, exec_time, None)
            except Exception as e:
                return (None, 0.0, e)

    tasks = [limited_call(args) for args in args_list]
    return await asyncio.gather(*tasks)


# =============================================================================
# CONCURRENT REQUEST HANDLING TESTS
# =============================================================================


class TestConcurrentRequests:
    """Test suite for concurrent request handling."""

    @pytest.mark.load
    @pytest.mark.parametrize("concurrency", CONCURRENCY_LEVELS)
    def test_concurrent_get_active_creators(self, concurrency: int):
        """
        Test concurrent get_active_creators calls.

        Verifies that the server can handle multiple simultaneous requests
        without errors or significant performance degradation.

        Capacity limit: Tested up to 100 concurrent requests.
        """
        args_list = [()] * concurrency
        results = run_concurrent_calls(get_active_creators, args_list, concurrency)

        # Count successful calls
        success_count = sum(
            1 for r, _, e in results
            if e is None and "creators" in (r or {})
        )
        error_count = len(results) - success_count

        # Extract timing data
        exec_times = [t for _, t, e in results if e is None]

        # Assert high success rate (allow 5% failure under heavy load)
        min_success_rate = 0.95
        actual_rate = success_count / len(results)
        assert actual_rate >= min_success_rate, (
            f"Success rate {actual_rate:.2%} below {min_success_rate:.2%} "
            f"with {concurrency} concurrent requests"
        )

        # Log performance metrics
        if exec_times:
            p50 = calculate_percentile(exec_times, 50)
            p95 = calculate_percentile(exec_times, 95)
            p99 = calculate_percentile(exec_times, 99)
            print(f"\nConcurrency {concurrency}: p50={p50:.1f}ms, p95={p95:.1f}ms, p99={p99:.1f}ms")

    @pytest.mark.load
    @pytest.mark.parametrize("concurrency", CONCURRENCY_LEVELS)
    def test_concurrent_get_creator_profile(self, valid_creator_id: Optional[str], concurrency: int):
        """
        Test concurrent get_creator_profile calls.

        Uses a single valid creator_id to stress test the profile retrieval
        with multiple concurrent requests.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available for testing")

        args_list = [(valid_creator_id,)] * concurrency
        results = run_concurrent_calls(get_creator_profile, args_list, concurrency)

        success_count = sum(
            1 for r, _, e in results
            if e is None and "creator" in (r or {})
        )

        exec_times = [t for _, t, e in results if e is None]

        min_success_rate = 0.95
        actual_rate = success_count / len(results)
        assert actual_rate >= min_success_rate, (
            f"Success rate {actual_rate:.2%} below threshold "
            f"for {concurrency} concurrent get_creator_profile calls"
        )

        if exec_times:
            p95 = calculate_percentile(exec_times, 95)
            print(f"\nget_creator_profile concurrent ({concurrency}): p95={p95:.1f}ms")

    @pytest.mark.load
    @pytest.mark.parametrize("concurrency", CONCURRENCY_LEVELS)
    def test_concurrent_get_send_types(self, concurrency: int):
        """
        Test concurrent get_send_types calls.

        This is a lightweight operation that should handle high concurrency
        with minimal performance impact.
        """
        args_list = [()] * concurrency
        results = run_concurrent_calls(get_send_types, args_list, concurrency)

        success_count = sum(
            1 for r, _, e in results
            if e is None and "send_types" in (r or {})
        )

        min_success_rate = 0.98  # Higher threshold for lightweight operation
        actual_rate = success_count / len(results)
        assert actual_rate >= min_success_rate

    @pytest.mark.load
    @pytest.mark.parametrize("concurrency", [10, 50])
    def test_concurrent_mixed_operations(
        self,
        valid_creator_id: Optional[str],
        concurrency: int
    ):
        """
        Test concurrent mixed read operations.

        Simulates realistic workload with various operations running simultaneously.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Build mixed operation list
        operations = []
        for i in range(concurrency):
            op_type = i % 5
            if op_type == 0:
                operations.append((get_active_creators, ()))
            elif op_type == 1:
                operations.append((get_creator_profile, (valid_creator_id,)))
            elif op_type == 2:
                operations.append((get_send_types, ()))
            elif op_type == 3:
                operations.append((get_channels, ()))
            else:
                operations.append((get_audience_targets, ()))

        # Execute concurrently
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            def execute_op(op):
                func, args = op
                try:
                    result, exec_time = measure_execution_time(func, *args)
                    return (result, exec_time, None)
                except Exception as e:
                    return (None, 0.0, e)

            futures = [executor.submit(execute_op, op) for op in operations]
            for future in as_completed(futures):
                results.append(future.result())

        # Check success rate
        success_count = sum(1 for r, _, e in results if e is None and r is not None)
        actual_rate = success_count / len(results)
        assert actual_rate >= 0.95, f"Mixed operations success rate {actual_rate:.2%}"


# =============================================================================
# DATABASE CONNECTION POOLING TESTS
# =============================================================================


class TestConnectionPooling:
    """Test suite for database connection pooling behavior."""

    @pytest.mark.load
    def test_connection_reuse_under_load(self):
        """
        Verify connections are properly managed under load.

        SQLite doesn't have traditional connection pooling, but we verify
        that connections are properly opened and closed without leaks.
        """
        connection_count = 0
        original_get_conn = get_db_connection

        def counting_get_conn():
            nonlocal connection_count
            connection_count += 1
            return original_get_conn()

        # Execute multiple operations and count connections
        with patch("mcp.connection.get_db_connection", counting_get_conn):
            for _ in range(50):
                result = get_active_creators()
                assert "error" not in result

        # Each operation should create one connection
        # (SQLite doesn't pool, so this verifies no connection leaks)
        assert connection_count == 50, f"Expected 50 connections, got {connection_count}"

    @pytest.mark.load
    def test_concurrent_connection_handling(self):
        """
        Test that concurrent connections don't interfere with each other.

        Verifies SQLite's busy timeout handles concurrent access correctly.
        """
        num_concurrent = 20

        def execute_read_query(query_id: int) -> tuple[bool, str]:
            try:
                result = execute_query(f"SELECT {query_id} as id, COUNT(*) as cnt FROM creators")
                if "error" in result:
                    return False, result["error"]
                return True, f"Query {query_id} succeeded"
            except Exception as e:
                return False, str(e)

        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [
                executor.submit(execute_read_query, i)
                for i in range(num_concurrent)
            ]
            results = [f.result() for f in as_completed(futures)]

        success_count = sum(1 for success, _ in results if success)
        assert success_count == num_concurrent, (
            f"Expected all {num_concurrent} queries to succeed, "
            f"got {success_count}"
        )

    @pytest.mark.load
    def test_connection_cleanup_on_error(self):
        """
        Verify connections are properly cleaned up even on errors.

        This test verifies that the MCP server's db_connection context manager
        properly closes connections even when operations fail. We don't track
        at the sqlite3.connect level because the import happens before our patch.
        Instead, we verify the server handles errors gracefully by checking
        subsequent operations still work.
        """
        # Execute operations that will fail (creator not found)
        for _ in range(10):
            result = get_creator_profile("nonexistent_creator")
            assert "error" in result

        # Verify connections are still working after errors
        # If connections weren't being cleaned up, we'd see timeouts/errors
        result = get_active_creators()
        assert "error" not in result, "Connection pool exhausted after error handling"
        assert "creators" in result

        # Also verify we can still execute queries
        result = execute_query("SELECT COUNT(*) as cnt FROM creators")
        assert "error" not in result
        assert "results" in result


# =============================================================================
# PERFORMANCE BENCHMARK TESTS
# =============================================================================


class TestPerformanceBenchmarks:
    """Test suite for performance benchmarks with p95 latency requirements."""

    @pytest.mark.benchmark
    def test_get_creator_profile_p95(self, valid_creator_id: Optional[str]):
        """
        Benchmark get_creator_profile with p95 < 100ms requirement.

        Runs 100 iterations and validates p95 latency.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        num_iterations = 100
        exec_times = []

        for _ in range(num_iterations):
            _, exec_time = measure_execution_time(get_creator_profile, valid_creator_id)
            exec_times.append(exec_time)

        p95 = calculate_percentile(exec_times, 95)
        requirement = PERFORMANCE_REQUIREMENTS["get_creator_profile"]

        print(f"\nget_creator_profile benchmark ({num_iterations} iterations):")
        print(f"  p50: {calculate_percentile(exec_times, 50):.2f}ms")
        print(f"  p95: {p95:.2f}ms (requirement: <{requirement}ms)")
        print(f"  p99: {calculate_percentile(exec_times, 99):.2f}ms")
        print(f"  min: {min(exec_times):.2f}ms")
        print(f"  max: {max(exec_times):.2f}ms")

        assert p95 < requirement, (
            f"get_creator_profile p95 ({p95:.2f}ms) exceeds "
            f"requirement (<{requirement}ms)"
        )

    @pytest.mark.benchmark
    def test_get_top_captions_p95(self, valid_creator_id: Optional[str]):
        """
        Benchmark get_top_captions with p95 < 200ms for 100 captions.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        num_iterations = 50
        exec_times = []

        for _ in range(num_iterations):
            _, exec_time = measure_execution_time(
                get_top_captions,
                valid_creator_id,
                limit=100
            )
            exec_times.append(exec_time)

        p95 = calculate_percentile(exec_times, 95)
        requirement = PERFORMANCE_REQUIREMENTS["get_top_captions"]

        print(f"\nget_top_captions (100 captions) benchmark ({num_iterations} iterations):")
        print(f"  p95: {p95:.2f}ms (requirement: <{requirement}ms)")

        assert p95 < requirement, (
            f"get_top_captions p95 ({p95:.2f}ms) exceeds "
            f"requirement (<{requirement}ms)"
        )

    @pytest.mark.benchmark
    def test_save_schedule_p95(
        self,
        valid_creator_id: Optional[str],
        test_schedule_items: list[dict[str, Any]]
    ):
        """
        Benchmark save_schedule with p95 < 500ms for 50 items.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        num_iterations = 20  # Fewer iterations as this is a write operation
        exec_times = []

        # Use different week_start dates to avoid conflicts
        base_week = 2020

        for i in range(num_iterations):
            week_start = f"{base_week}-{(i % 12) + 1:02d}-{((i * 7) % 28) + 1:02d}"
            _, exec_time = measure_execution_time(
                save_schedule,
                valid_creator_id,
                week_start,
                test_schedule_items
            )
            exec_times.append(exec_time)

        p95 = calculate_percentile(exec_times, 95)
        requirement = PERFORMANCE_REQUIREMENTS["save_schedule"]

        print(f"\nsave_schedule (50 items) benchmark ({num_iterations} iterations):")
        print(f"  p95: {p95:.2f}ms (requirement: <{requirement}ms)")

        assert p95 < requirement, (
            f"save_schedule p95 ({p95:.2f}ms) exceeds "
            f"requirement (<{requirement}ms)"
        )

    @pytest.mark.benchmark
    def test_execute_query_p95(self):
        """
        Benchmark execute_query for simple SELECT queries.
        """
        num_iterations = 100
        exec_times = []

        for _ in range(num_iterations):
            _, exec_time = measure_execution_time(
                execute_query,
                "SELECT COUNT(*) as cnt FROM creators WHERE is_active = 1"
            )
            exec_times.append(exec_time)

        p95 = calculate_percentile(exec_times, 95)
        requirement = PERFORMANCE_REQUIREMENTS["execute_query"]

        print(f"\nexecute_query benchmark ({num_iterations} iterations):")
        print(f"  p95: {p95:.2f}ms (requirement: <{requirement}ms)")

        assert p95 < requirement

    @pytest.mark.benchmark
    def test_get_send_types_p95(self):
        """
        Benchmark get_send_types with p95 < 50ms.
        """
        num_iterations = 100
        exec_times = []

        for _ in range(num_iterations):
            _, exec_time = measure_execution_time(get_send_types)
            exec_times.append(exec_time)

        p95 = calculate_percentile(exec_times, 95)
        requirement = PERFORMANCE_REQUIREMENTS["get_send_types"]

        print(f"\nget_send_types benchmark ({num_iterations} iterations):")
        print(f"  p95: {p95:.2f}ms (requirement: <{requirement}ms)")

        assert p95 < requirement


# =============================================================================
# MEMORY USAGE AND LEAK DETECTION TESTS
# =============================================================================


class TestMemoryUsage:
    """Test suite for memory usage and leak detection."""

    @pytest.mark.memory
    def test_no_memory_leak_under_sustained_load(self, valid_creator_id: Optional[str]):
        """
        Verify no memory leaks under sustained load.

        Runs 1000 iterations of various operations and checks that memory
        usage doesn't grow significantly.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Force garbage collection before starting
        gc.collect()

        # Start memory tracking
        tracemalloc.start()

        # Record initial memory
        snapshot1 = tracemalloc.take_snapshot()

        # Run sustained load
        num_iterations = 1000
        for i in range(num_iterations):
            # Mix of operations
            if i % 5 == 0:
                get_active_creators()
            elif i % 5 == 1:
                get_creator_profile(valid_creator_id)
            elif i % 5 == 2:
                get_send_types()
            elif i % 5 == 3:
                get_channels()
            else:
                execute_query("SELECT 1")

            # Periodic GC to simulate real-world conditions
            if i % 100 == 0:
                gc.collect()

        # Force final GC
        gc.collect()

        # Take final snapshot
        snapshot2 = tracemalloc.take_snapshot()

        # Stop tracking
        tracemalloc.stop()

        # Analyze memory growth
        stats = snapshot2.compare_to(snapshot1, "lineno")

        # Calculate total memory growth
        total_growth = sum(stat.size_diff for stat in stats if stat.size_diff > 0)

        print(f"\nMemory analysis after {num_iterations} iterations:")
        print(f"  Total memory growth: {total_growth / 1024:.2f} KB")
        print(f"  Threshold: {MEMORY_LEAK_THRESHOLD / 1024:.2f} KB")

        # Top memory consumers
        if stats:
            print("\nTop 5 memory consumers:")
            for stat in stats[:5]:
                print(f"  {stat}")

        assert total_growth < MEMORY_LEAK_THRESHOLD, (
            f"Memory growth ({total_growth / 1024:.2f}KB) exceeds threshold "
            f"({MEMORY_LEAK_THRESHOLD / 1024:.2f}KB)"
        )

    @pytest.mark.memory
    def test_large_result_set_memory(self, valid_creator_id: Optional[str]):
        """
        Test memory handling with large result sets.

        Verifies that fetching large amounts of data doesn't cause
        excessive memory consumption.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        gc.collect()
        tracemalloc.start()

        snapshot1 = tracemalloc.take_snapshot()

        # Fetch large caption sets
        for _ in range(10):
            result = get_top_captions(valid_creator_id, limit=1000)
            # Don't hold reference to result
            del result
            gc.collect()

        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_growth = sum(stat.size_diff for stat in stats if stat.size_diff > 0)

        # Should not retain large amounts of memory after processing
        assert total_growth < MEMORY_LEAK_THRESHOLD, (
            f"Large result set memory not properly released: "
            f"{total_growth / 1024:.2f}KB retained"
        )


# =============================================================================
# CONNECTION LIMITS AND POOL EXHAUSTION TESTS
# =============================================================================


class TestConnectionLimits:
    """Test suite for connection limits and pool exhaustion behavior."""

    @pytest.mark.stress
    def test_high_connection_concurrency(self):
        """
        Test behavior under high connection concurrency.

        Simulates 100 simultaneous database connections to test
        SQLite's busy timeout handling.
        """
        num_connections = 100

        results = []

        def open_and_query():
            start_time = time.perf_counter()
            try:
                conn = get_db_connection()
                cursor = conn.execute("SELECT COUNT(*) FROM creators")
                cursor.fetchone()
                conn.close()
                wait_time = time.perf_counter() - start_time
                return (True, wait_time)
            except Exception as e:
                wait_time = time.perf_counter() - start_time
                return (False, wait_time, str(e))

        with ThreadPoolExecutor(max_workers=num_connections) as executor:
            futures = [executor.submit(open_and_query) for _ in range(num_connections)]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for r in results if r[0])
        wait_times = [r[1] for r in results if r[0]]

        print(f"\nHigh concurrency test ({num_connections} connections):")
        print(f"  Success rate: {success_count}/{num_connections}")
        if wait_times:
            print(f"  Max wait time: {max(wait_times):.3f}s")
            print(f"  Avg wait time: {statistics.mean(wait_times):.3f}s")

        # Most connections should succeed
        assert success_count >= num_connections * 0.9, (
            f"Too many connection failures: {num_connections - success_count}"
        )

        # Wait times should be reasonable
        if wait_times:
            assert max(wait_times) < MAX_POOL_WAIT_TIME, (
                f"Max wait time ({max(wait_times):.2f}s) exceeds threshold"
            )

    @pytest.mark.stress
    def test_sustained_high_load(self, valid_creator_id: Optional[str]):
        """
        Test sustained high load over extended period.

        Runs 60 seconds of continuous concurrent operations.
        """
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        duration_seconds = 30  # 30 seconds of sustained load
        concurrency = 20

        start_time = time.time()
        total_operations = 0
        errors = []

        def continuous_operation():
            operations = 0
            op_errors = []
            while time.time() - start_time < duration_seconds:
                try:
                    op_type = operations % 3
                    if op_type == 0:
                        get_active_creators()
                    elif op_type == 1:
                        get_creator_profile(valid_creator_id)
                    else:
                        get_send_types()
                    operations += 1
                except Exception as e:
                    op_errors.append(str(e))
                    operations += 1
            return operations, op_errors

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(continuous_operation) for _ in range(concurrency)]
            for future in as_completed(futures):
                ops, errs = future.result()
                total_operations += ops
                errors.extend(errs)

        elapsed = time.time() - start_time
        ops_per_second = total_operations / elapsed
        error_rate = len(errors) / total_operations if total_operations > 0 else 0

        print(f"\nSustained load test ({duration_seconds}s, {concurrency} workers):")
        print(f"  Total operations: {total_operations}")
        print(f"  Operations/second: {ops_per_second:.1f}")
        print(f"  Error count: {len(errors)}")
        print(f"  Error rate: {error_rate:.2%}")

        # Error rate should be low
        assert error_rate < 0.01, f"Error rate ({error_rate:.2%}) too high"

        # Should maintain reasonable throughput
        min_ops_per_second = 50  # Minimum expected throughput
        assert ops_per_second > min_ops_per_second, (
            f"Throughput ({ops_per_second:.1f} ops/s) below minimum "
            f"({min_ops_per_second} ops/s)"
        )

    @pytest.mark.stress
    def test_connection_recovery_after_errors(self):
        """
        Test that connections recover properly after errors.
        """
        # First, cause some intentional errors
        for _ in range(10):
            result = get_creator_profile("nonexistent_creator")
            assert "error" in result

        # Then verify normal operations still work
        result = get_active_creators()
        assert "error" not in result, "Server failed to recover after errors"
        assert "creators" in result


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not stress"])
